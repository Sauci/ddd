"""How the pydantic contracts are turned into the json schemas DDD publishes.

``ddd schema`` exists so that an editor bound to a description file can offer completion,
hover documentation and as-you-type validation. Pydantic's own output is a faithful
description of the *constraints* but a poor carrier of the *documentation*, and this module
closes the three gaps that cost the most at the point where somebody is actually writing a
file:

* **The dialect is not stated.** Pydantic emits draft 2020-12 but does not say so, leaving
  every validator to guess. A published contract says which dialect it is written in.
* **Docstrings are reStructuredText.** They are written for the api documentation, where
  ``:class:`Foo``` becomes a link. A json schema description is rendered as markdown, so the
  same text reaches an author as the literal characters ``:class:`Foo```, naming a python
  class the author of a ``*.ddd.json`` file cannot see and has no use for.
* **Enumerated values carry no documentation at all.** Pydantic keeps the docstring of the
  enum *class* and drops the one written under each member, so hovering ``"kind": "curve"``
  says nothing about what a curve is - on exactly the keys where a closed set of values makes
  hover documentation most useful.

The per-value documentation is published twice, because no single spelling reaches every
editor. It is appended to the ``description`` as a markdown list, which every editor shows
because every editor shows a description; and it is repeated in ``enumDescriptions``, the
parallel array the json language service behind VS Code reads to document each entry of the
completion dropdown. ``enumDescriptions`` is not part of the specification, which costs
nothing: json schema requires an unknown keyword to be ignored, so a validator sees the same
contract either way.
"""

from __future__ import annotations

import ast
import inspect
import re
import textwrap
from enum import Enum
from functools import cache
from typing import Any

from pydantic.json_schema import GenerateJsonSchema, JsonSchemaMode, JsonSchemaValue
from pydantic_core import core_schema

_ROLE = re.compile(r":[a-z]+(?::[a-z]+)*:`([^`]*)`")
"""A reStructuredText interpreted role, e.g. ``:class:`Foo``` or ``:py:data:`BAR```."""

_LITERAL_BLOCK = re.compile(r"::(\s*\n)")
"""The ``::`` that introduces a literal block in rST; in markdown the indent alone does it."""


def _role_text(target: str) -> str:
    """What Sphinx would have displayed for the target of a role.

    The three spellings that appear in these contracts: an explicit label
    (``:doc:`the project file <project>```), an abbreviated reference (``:data:`~a.b.C```,
    shown as ``C``), and a plain one, shown as written.
    """
    target = target.strip()
    if target.endswith(">") and "<" in target:
        label, _, reference = target.partition("<")
        target = label.strip() or reference[:-1].strip()
    if target.startswith("~"):
        return target[1:].rsplit(".", 1)[-1]
    return target


def as_markdown(text: str) -> str:
    """Render a docstring written for Sphinx as the markdown an editor will show.

    Double backticks need no translation: rST spells inline literals the way markdown spells
    a code span, which is why the contracts are written with them throughout.
    """
    text = _ROLE.sub(lambda match: f"``{_role_text(match.group(1))}``", text)
    return _LITERAL_BLOCK.sub(r":\1", text)


def member_docstrings(cls: type) -> dict[str, str]:
    """The docstring written under each member of a class, keyed by member name.

    Python keeps no attribute docstrings at runtime - the string under ``VALUE = "value"`` is
    evaluated and discarded - so they are read back out of the source, which is the same thing
    pydantic's ``use_attribute_docstrings`` does for model fields. Enum members are not model
    fields, so nothing did it for them.

    An interpreter with no source to read is not an error: it returns nothing and the schema
    is published without the per-value documentation rather than not published at all.
    """
    try:
        source = textwrap.dedent(inspect.getsource(cls))
        (node,) = ast.parse(source).body
    except (OSError, TypeError, SyntaxError, ValueError):
        return {}
    if not isinstance(node, ast.ClassDef):
        return {}

    documented: dict[str, str] = {}
    assigned: str | None = None
    for statement in node.body:
        if (
            assigned is not None
            and isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Constant)
            and isinstance(statement.value.value, str)
        ):
            documented[assigned] = inspect.cleandoc(statement.value.value)
            assigned = None
            continue
        assigned = _assigned_name(statement)
    return documented


def _assigned_name(statement: ast.stmt) -> str | None:
    """The name a simple assignment binds, which a following string would document."""
    if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
        target = statement.targets[0]
        return target.id if isinstance(target, ast.Name) else None
    if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
        return statement.target.id
    return None


@cache
def value_documentation(enum_type: type[Enum]) -> dict[str, str]:
    """One line of documentation per member of an enum, keyed by the value it serialises to.

    Two sources, in order. A member may document itself through a ``schema_description``
    property, which is how a set of values whose documentation is *derivable* states it once:
    the size and range of every datatype are already known to the model, and a docstring
    repeating them would be a second copy to keep true. Everything else is prose, and prose
    belongs in the docstring under the member, where the api documentation shows it too.
    """
    from_source = member_docstrings(enum_type)
    documented: dict[str, str] = {}
    for member in enum_type:
        described = getattr(member, "schema_description", None) or from_source.get(member.name, "")
        if described:
            documented[str(member.value)] = " ".join(described.split())
    return documented


class PublishedSchema(GenerateJsonSchema):
    """The json schema generator behind ``ddd schema``.

    What it adds is documentation and metadata, and the one thing it changes about validation
    it changes towards the loader: the conversion union is published as ``anyOf`` rather than
    ``oneOf``, because its ``kind`` may be left out and an empty block then matches more than
    one variant. The loader reads that block as the identity, so a validator has to accept it
    too; the published schema and the loader cannot disagree about whether a file is valid.
    """

    def generate(
        self, schema: core_schema.CoreSchema, mode: JsonSchemaMode = "validation"
    ) -> JsonSchemaValue:
        published = super().generate(schema, mode=mode)
        _document(published)
        # The dialect leads the document, the way a reader expects to find it, and the title
        # follows: what an editor puts at the top of the hover before anything else.
        return {"$schema": self.schema_dialect, **published}

    def tagged_union_schema(self, schema: core_schema.TaggedUnionSchema) -> JsonSchemaValue:
        """Publish a union whose tag may be omitted as ``anyOf``.

        A data object states its ``kind``, so its variants never overlap and ``oneOf`` says
        exactly that. A conversion may leave ``kind`` out, and ``{}`` - the identity - then
        satisfies the identity variant and the linear one alike, which ``oneOf`` refuses and
        the loader accepts.
        """
        result = super().tagged_union_schema(schema)
        if "oneOf" in result and set(schema["choices"]) == {"identity", "linear", "enum"}:
            result["anyOf"] = result.pop("oneOf")
        return result

    def enum_schema(self, schema: core_schema.EnumSchema) -> JsonSchemaValue:
        """Record what each individual value means, not just which values are allowed.

        Only the machine readable half is written here. Pydantic re-applies the docstring of
        the enum *class* over ``description`` after this returns, so the prose half is
        composed later, in :func:`_document`, out of what this leaves behind.

        All of the values or none of them: a dropdown in which some entries explain themselves
        and the rest are silent reads as a broken tool rather than as a partly documented one,
        so an enum that is missing a line anywhere is published the way pydantic wrote it.
        """
        result = super().enum_schema(schema)
        documented = value_documentation(schema["cls"])
        values = [str(value) for value in result["enum"]]
        if not all(value in documented for value in values):
            return result
        # Parallel to 'enum' and in the same order: that is the contract the json language
        # service reads it under, and a shifted entry would document the wrong value.
        result["enumDescriptions"] = [documented[value] for value in values]
        return result

    def literal_schema(self, schema: core_schema.LiteralSchema) -> JsonSchemaValue:
        """Document a fixed value as the enum it was taken from documents it.

        This is what reaches the discriminator of a tagged union: each variant of a data
        object pins ``kind`` to one value, and pydantic renders that as a bare ``const``. The
        key deciding which shape the whole object has is the last one that should hover blank,
        and what it means is already written under the member of the enum.
        """
        result = super().literal_schema(schema)
        expected = schema["expected"]
        if len(expected) != 1 or not isinstance(expected[0], Enum):
            return result
        described = value_documentation(type(expected[0])).get(str(expected[0].value), "")
        if described:
            result["description"] = described
        return result


def _document(node: Any) -> None:
    """Turn a finished schema into the documentation an editor shows, in place.

    Two passes over one document: every description is rendered as markdown, and every
    enumerated value that has documentation gets it spelled out in the description of the key
    it belongs to. Both spellings of the value documentation come from the one array, so they
    cannot describe the values differently.
    """
    if isinstance(node, dict):
        _describe_values(node)
        description = node.get("description")
        if isinstance(description, str):
            node["description"] = as_markdown(description)
        for value in node.values():
            _document(value)
    elif isinstance(node, list):
        for value in node:
            _document(value)


def _describe_values(node: dict[str, Any]) -> None:
    """Append the per-value documentation of an enum to its description, as a markdown list."""
    values = node.get("enum")
    documented = node.get("enumDescriptions")
    if not isinstance(values, list) or not isinstance(documented, list):
        return
    listed = "\n".join(
        f"* ``{value}`` - {text}" for value, text in zip(values, documented, strict=True)
    )
    node["description"] = f"{node.get('description', '')}\n\n{listed}".strip()
