"""Checks that the documentation still describes the tool that exists.

Prose rots quietly. These tests pin the few facts that are cheap to verify mechanically -
the names of the checks, the commands, the object kinds - so a rename cannot leave the
README and the SPEC describing a previous version of DDD.
"""

from __future__ import annotations

import argparse
import json
import re
import tomllib
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

import jsonschema
import pytest
from pydantic import BaseModel

from ddd import __version__
from ddd.cli import _build_parser
from ddd.diagnostics import CHECKS
from ddd.models import Datatype, ObjectKind

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")
SPEC = (ROOT / "SPEC.md").read_text(encoding="utf-8")
DOCS_WORKFLOW = (ROOT / ".github" / "workflows" / "docs.yml").read_text(encoding="utf-8")
PUBLISH_WORKFLOW = (ROOT / ".github" / "workflows" / "publish.yml").read_text(encoding="utf-8")
DOCS_URL = "https://sauci.github.io/ddd/"


def commands() -> list[str]:
    """The subcommands the parser actually offers.

    argparse has no public accessor for the choices of a subparser action, so this reaches
    for the action itself. It is a test helper: if a future argparse moves it, this fails
    loudly here instead of quietly weakening a documentation check.
    """
    parser = _build_parser()
    action = next(
        action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
    )
    return sorted(action.choices)


class TestChecks:
    @pytest.mark.parametrize("check", sorted(CHECKS))
    def test_every_check_is_named_in_the_readme(self, check: str) -> None:
        assert f"`{check}`" in README

    @pytest.mark.parametrize("check", sorted(CHECKS))
    def test_every_check_is_named_in_the_spec(self, check: str) -> None:
        assert f"`{check}`" in SPEC

    def test_the_readme_invents_no_check(self) -> None:
        """A check named in the README but not registered would be an empty promise."""
        claimed = set(re.findall(r"`([a-z][a-z0-9]*(?:-[a-z0-9]+)+)`", README))
        # Only names that look like check identifiers are considered; command line flags and
        # file names contain other characters.
        unknown = {name for name in claimed if name not in CHECKS and "-" in name}
        assert unknown <= {
            "const-inputs",
            "dry-run",
            "address-map",
            "byte-order",
            "output-dir",
            "cmake-dir",
            "no-cov",
            "cov-fail-under",
            "no-propagate-headers",
            "ddd-compile",
            "ddd-tool",
        }, f"README mentions unknown checks: {sorted(unknown)}"


class TestCommands:
    @pytest.mark.parametrize("command", commands())
    def test_every_command_is_documented_in_the_readme(self, command: str) -> None:
        assert f"ddd {command}" in README or f"`{command}`" in README

    def test_the_command_list_is_what_the_spec_promises(self) -> None:
        assert set(commands()) == {
            "check",
            "compare",
            "generate",
            "list",
            "dump",
            "schema",
            "build-info",
            "lsp",
            "checks",
            "cmake-dir",
            "templates-dir",
            "sources",
        }


class TestConcepts:
    @pytest.mark.parametrize("kind", sorted(ObjectKind))
    def test_every_object_kind_is_documented(self, kind: ObjectKind) -> None:
        assert f"`{kind.value}`" in README
        assert f"`{kind.value}`" in SPEC

    @pytest.mark.parametrize("datatype", sorted(Datatype))
    def test_every_datatype_is_documented(self, datatype: Datatype) -> None:
        assert f"`{datatype.value}`" in README
        assert f"`{datatype.value}`" in SPEC

    def test_the_readme_points_at_files_that_exist(self) -> None:
        """A dead link in the README is a lie about where the code lives."""
        for target in re.findall(r"\]\((?!https?:)([^)#]+)", README):
            assert (ROOT / target).exists(), f"README links to a missing path: {target}"

    def test_the_spec_points_at_files_that_exist(self) -> None:
        for target in re.findall(r"\]\((?!https?:)([^)#]+)", SPEC):
            assert (ROOT / target).exists(), f"SPEC links to a missing path: {target}"


def spec_headings() -> list[tuple[int, str]]:
    """Every markdown heading of the SPEC with its level, code blocks excluded."""
    headings = []
    fenced = False
    for line in SPEC.splitlines():
        if line.startswith("```"):
            fenced = not fenced
        elif not fenced and (found := re.match(r"(#{1,5}) (.+)", line)):
            headings.append((len(found.group(1)), found.group(2)))
    return headings


def anchor_of(heading: str) -> str:
    """The anchor GitHub derives from a heading, which is what every SPEC link targets.

    Lower case, emphasis markers dropped, punctuation removed, spaces turned into
    hyphens - the slug of the *rendered* text. Pinned by examples in the tests below,
    because every internal link of the SPEC silently stops working if this drifts from
    what GitHub actually does.
    """
    text = heading.replace("*", "").lower()
    return re.sub(r"\s", "-", re.sub(r"[^\w\s-]", "", text))


def spec_links() -> list[tuple[str, str]]:
    """Every internal link of the SPEC, as (visible text, anchor)."""
    return re.findall(r"\[([^\]]+)\]\(#([A-Za-z0-9-]+)\)", SPEC)


def spec_toc() -> list[tuple[str, str]]:
    """The entries of the table of contents, in order, as (visible text, anchor)."""
    top = SPEC.split("\n## ", 1)[0]
    return re.findall(r"^\s*[*-] \[([^\]]+)\]\(#([a-z0-9-]+)\)$", top, flags=re.MULTILINE)


class TestSpecCrossReferences:
    """The SPEC's section links and its table of contents, kept honest mechanically.

    The anchors are derived from heading text, so a retitled or renumbered section breaks
    every link to it without any renderer saying so; and the table of contents is a second
    copy of the outline, which is to say a second thing that can quietly disagree with the
    first. Neither failure shows up in a rendered preview, which is why both are pinned
    here.
    """

    @pytest.mark.parametrize(
        ("heading", "anchor"),
        [
            ("3.3.1 One object, several declarations", "331-one-object-several-declarations"),
            ("3.5 Memory placement *(planned)*", "35-memory-placement-planned"),
            ("5.2 A2L", "52-a2l"),
            ("1.1 Requirement words", "11-requirement-words"),
        ],
    )
    def test_the_anchor_rule_is_the_one_github_applies(self, heading: str, anchor: str) -> None:
        assert anchor_of(heading) == anchor

    def test_every_link_resolves_to_a_heading(self) -> None:
        """A broken anchor renders exactly like a working one; only a click tells them apart."""
        anchors = {anchor_of(text) for _, text in spec_headings()}
        dangling = [(text, target) for text, target in spec_links() if target not in anchors]
        assert not dangling, f"SPEC links that resolve to no heading: {dangling}"

    def test_the_table_of_contents_is_the_outline(self) -> None:
        """Every heading, in order, both directions: nothing missing, nothing stale.

        The list is maintained with the editor's table-of-contents generator, which starts
        at the document title and descends to the deepest level; this pins that whatever
        regenerates it keeps covering all of them.
        """
        outline = [(text, anchor_of(text)) for _, text in spec_headings()]
        assert spec_toc() == outline, (
            "the table of contents and the headings have come apart; regenerate the list at "
            "the top of SPEC.md from the section headings"
        )

    def test_a_numbered_link_points_at_the_section_it_names(self) -> None:
        """``[section 3.6](#36-...)`` states the number twice; renumbering can break the
        two apart, and the link then reads right while landing wrong."""
        for text, target in spec_links():
            numbered = re.match(r"(?:section )?(\d+(?:\.\d+)*)(?: |$)", text)
            if numbered:
                digits = numbered.group(1).replace(".", "")
                assert target.startswith(f"{digits}-"), (
                    f"the link [{text}] points at #{target}, "
                    f"which is not section {numbered.group(1)}"
                )


class TestPackaging:
    """What a customer receives has to match what the sources say it is."""

    def test_the_version_is_the_same_in_both_places(self) -> None:
        """The banner of every generated file carries it, and the release tag is checked
        against it, so a drift between the package and the module is a released lie."""
        metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        assert metadata["project"]["version"] == __version__

    def test_the_editor_extension_carries_the_same_version(self) -> None:
        """The extension is a launcher for a server this package ships, so a version of its
        own would be a second number to explain, and the one a user quotes in a bug report."""
        manifest = json.loads(
            (ROOT / "editors" / "vscode" / "package.json").read_text(encoding="utf-8")
        )
        assert manifest["version"] == __version__

    def test_the_declared_license_file_exists(self) -> None:
        metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        license_file = metadata["project"]["license"]["file"]
        assert (ROOT / license_file).is_file(), "the declared license file is not in the tree"

    def test_the_extension_is_installed_from_where_the_documentation_says(self) -> None:
        """The ``.vsix`` on the release is the only way in, so every page has to say so.

        The extension was never published to the Visual Studio Marketplace: the step that
        would have done it failed on both releases that ran it, and the publisher it needs
        lives in an Azure DevOps organisation nobody set up. Four pages nonetheless told a
        customer to search the Extensions view and linked an item page that answers 404.
        The release asset is what actually exists, and it is what they now name.
        """
        manifest = json.loads(
            (ROOT / "editors" / "vscode" / "package.json").read_text(encoding="utf-8")
        )
        # The item page, derived the way the marketplace addresses an extension. The *manage*
        # url is a different thing and stays: the developer documentation cites it as the
        # prerequisite of publishing there, which is guidance for a maintainer rather than an
        # install instruction pointed at a customer.
        item = f"items?itemName={manifest['publisher']}.{manifest['name']}"
        pages = [
            ROOT / "README.md",
            ROOT / "editors" / "vscode" / "README.md",
            ROOT / "docs" / "editor_integration.rst",
            ROOT / "docs" / "developer_documentation.rst",
        ]
        for page in pages:
            text = page.read_text(encoding="utf-8")
            assert item not in text, (
                f"{page.name} still sends a customer to the marketplace item page, which "
                f"has no extension on it and no workflow putting one there"
            )
            assert "ddd-<version>.vsix" in text, (
                f"{page.name} does not name the .vsix on the release, which is the only "
                f"way the extension can be installed"
            )

    def test_a_release_does_not_publish_the_extension_to_the_marketplace(self) -> None:
        """The decision, pinned where re-adding it would have to argue with something.

        The step existed, needed a ``VSCE_PAT`` nobody had, and failed on every release it
        ran on while the rest of the pipeline reported success around it. Restoring it means
        creating the publisher first - and, before that, putting the four pages above back.
        """
        assert "vsce" not in PUBLISH_WORKFLOW, (
            "the release publishes the extension to the marketplace again, but nothing "
            "installs it from there and no page tells anybody to"
        )
        assert "VSCE_PAT" not in PUBLISH_WORKFLOW, (
            "the marketplace token is back in the workflow with nothing to authenticate"
        )

    def test_the_release_carries_the_built_extension(self) -> None:
        """What replaced the marketplace: the ``.vsix`` still has to reach somebody.

        Removing the publish step must not take the packaging and the upload with it - a
        permanent url needing no account and no network policy exception is the whole of how
        the extension is installed now.
        """
        body = PUBLISH_WORKFLOW.split("\n  extension:\n", 1)[1]
        # Up to the next job, which is the next key at the indentation a job name sits at.
        extension = re.split(r"\n  [a-z][\w-]*:\n", body, maxsplit=1)[0]
        assert "npm run package" in extension, "the release no longer builds the .vsix"
        assert "gh release upload" in extension, (
            "the release no longer attaches the .vsix, so nothing ships the extension"
        )

    def test_the_extension_carries_the_license_it_declares(self) -> None:
        """``vsce`` packages nothing from outside the extension directory, so the root
        LICENSE never reaches the .vsix, and whoever unpacks one would find a licence it
        names and does not carry. The copy beside the manifest has to stay a copy."""
        extension = ROOT / "editors" / "vscode"
        manifest = json.loads((extension / "package.json").read_text(encoding="utf-8"))
        assert manifest["license"] == "MIT"
        shipped = (extension / "LICENSE").read_text(encoding="utf-8").splitlines()
        assert shipped == (ROOT / "LICENSE").read_text(encoding="utf-8").splitlines(), (
            "editors/vscode/LICENSE has drifted from the licence the project is under"
        )

    def test_everything_the_readme_tells_the_user_to_install_is_shipped(self) -> None:
        """`ddd cmake-dir` is documented, so the module has to travel in the wheel rather
        than existing only in a git checkout."""
        metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        wheel = metadata["tool"]["hatch"]["build"]["targets"]["wheel"]
        for source in ("cmake/Ddd.cmake",):
            assert source in wheel["force-include"], f"{source} is not shipped in the wheel"
            assert (ROOT / source).is_file()

    def test_no_dependency_list_is_both_dynamic_and_static(self) -> None:
        """Declaring a field dynamic *and* stating it is an error the build backend refuses.

        It costs nothing here and fails nothing locally - the tests import the package from
        ``src`` - so it surfaces only when somebody installs the project, which in practice
        means in ci or on a customer's machine.
        """
        metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        project = metadata["project"]
        for field in project.get("dynamic", []):
            assert field not in project, (
                f"'{field}' is listed in [project].dynamic and also stated statically; the "
                f"metadata hook refuses that and every install of this project fails"
            )

    def test_every_requirements_file_is_declared_and_shipped(self) -> None:
        """The dependency lists live in requirements files, read by a metadata hook.

        A file the hook names but the sdist leaves out makes that sdist unbuildable, and the
        failure only shows up for whoever installs from it - which is nobody until a customer
        does.
        """
        metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        hook = metadata["tool"]["hatch"]["metadata"]["hooks"]["requirements_txt"]
        named = list(hook["files"])
        for group in hook["optional-dependencies"].values():
            named.extend(group)
        shipped = metadata["tool"]["hatch"]["build"]["targets"]["sdist"]["include"]
        # The sdist patterns are anchored with a leading slash, so an unanchored name does
        # not also sweep in a same-named file somewhere deeper in the tree.
        shipped = {pattern.lstrip("/") for pattern in shipped}
        for name in named:
            assert (ROOT / name).is_file(), f"{name} is declared but missing from the tree"
            assert name in shipped, f"{name} is not in the sdist, which cannot then be built"

    def test_the_runtime_requirements_are_what_the_package_imports(self) -> None:
        """The two runtime dependencies are a deliberate claim of the README, so a third one
        appearing in requirements.txt has to be a decision rather than a drive-by addition."""
        listed = {
            re.split(r"[<>=!~ ]", line, maxsplit=1)[0].lower()
            for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        }
        assert listed == {"pydantic", "jinja2"}


class TestCommandLineHelp:
    """The help strings become markup, so they have to be safe as markup."""

    def test_no_help_string_carries_markup_characters(self) -> None:
        """autoprogram inserts every help string into the reference page as rST.

        A lone asterisk opens an emphasis that never closes, a backtick opens an
        interpreted role, and a pipe opens a substitution: each is a build warning, and the
        documentation image builds with -W, so each fails the build. The text is prose meant
        for a terminal, so the rule is simply to keep those characters out of it.
        """
        offenders = []

        def walk(parser: argparse.ArgumentParser, prefix: str) -> None:
            for action in parser._actions:
                if action.help and re.search(r"[*`|]", action.help):
                    name = " ".join(action.option_strings) or action.dest
                    offenders.append(f"{prefix} {name}")
                if isinstance(action, argparse._SubParsersAction):
                    for command, sub in action.choices.items():
                        walk(sub, f"{prefix} {command}")

        walk(_build_parser(), "ddd")
        assert not offenders, (
            f"help text carrying reStructuredText inline markup: {offenders}. Rewrite it "
            f"without * ` or |, which the generated command line reference cannot escape."
        )


def published_kinds() -> list[str]:
    """The file formats ``ddd schema`` publishes, which is what these tests are about."""
    from ddd.cli import _SCHEMA_MODELS

    return sorted(_SCHEMA_MODELS)


def published(kind: str) -> dict[str, Any]:
    """One published schema, exactly as ``ddd schema`` writes it."""
    from ddd.cli import schema_text

    loaded: dict[str, Any] = json.loads(schema_text(kind))
    return loaded


def objects_in(schema: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Every object in a schema that has properties, named for a failure message."""
    return [("<root>", schema), *schema.get("$defs", {}).items()]


def descriptions_in(node: object) -> list[str]:
    """Every description anywhere in a schema, which is everything an editor will show."""
    if isinstance(node, dict):
        found = [node["description"]] if isinstance(node.get("description"), str) else []
        return found + [text for value in node.values() for text in descriptions_in(value)]
    if isinstance(node, list):
        return [text for value in node for text in descriptions_in(value)]
    return []


def enumerations_in(node: object) -> list[dict[str, Any]]:
    """Every closed set of values in a schema, wherever it sits."""
    if isinstance(node, dict):
        found = [node] if isinstance(node.get("enum"), list) else []
        return found + [entry for value in node.values() for entry in enumerations_in(value)]
    if isinstance(node, list):
        return [entry for value in node for entry in enumerations_in(value)]
    return []


class TestPublishedSchemas:
    """The schemas are the editor integration, so what they carry is a promise.

    Everything here is checked against what ``ddd schema`` actually writes rather than against
    the models, because the file is what an editor reads and the two are only the same for as
    long as nothing between them drops anything.
    """

    def test_the_file_roots_allow_the_editor_binding(self) -> None:
        """Every root, not a hand-kept list of them: a new file kind joins the guard by
        subclassing ``FileRoot``, instead of silently shipping without the ``$schema`` key."""
        from ddd.models.common import FileRoot

        roots = FileRoot.__subclasses__()
        assert len(roots) >= 6, f"expected every file root, found {roots}"
        for model in roots:
            schema = model.model_json_schema(by_alias=True)
            assert "$schema" in schema["properties"], f"{model.__name__} rejects $schema"

    @pytest.mark.parametrize("kind", published_kinds())
    def test_every_schema_states_the_dialect_it_is_written_in(self, kind: str) -> None:
        """A contract that does not say which dialect it speaks leaves a validator guessing."""
        assert published(kind)["$schema"] == "https://json-schema.org/draft/2020-12/schema"

    @pytest.mark.parametrize("kind", published_kinds())
    def test_every_schema_is_titled_for_the_person_reading_it(self, kind: str) -> None:
        """The title heads the hover, so it names the file format rather than a python class."""
        title = published(kind)["title"]
        assert title.startswith("DDD "), f"{kind} is titled {title!r}"

    @pytest.mark.parametrize("kind", published_kinds())
    def test_every_authored_field_carries_hover_documentation(self, kind: str) -> None:
        """A field without a description is a blank tooltip in every editor.

        ``kind`` is exempt only where it is a fixed tag with nothing behind it: the ones that
        select a data object are documented, and checked below.
        """
        undocumented = [
            f"{name}.{field}"
            for name, definition in objects_in(published(kind))
            for field, spec in definition.get("properties", {}).items()
            if "description" not in spec and field != "kind"
        ]
        assert not undocumented, (
            f"fields with a blank editor tooltip: {undocumented}. Add an attribute "
            f"docstring; use_attribute_docstrings carries it into the schema."
        )

    @pytest.mark.parametrize("kind", published_kinds())
    def test_every_enumerated_value_says_what_it_means(self, kind: str) -> None:
        """A closed set of values is where hover documentation is worth the most.

        Which datatype to pick, or what a curve is as against a value block, is exactly the
        question an author has while typing - and the answer is already written under the
        member of the enum, so failing to carry it here throws away documentation that exists.
        """
        for enumeration in enumerations_in(published(kind)):
            values = enumeration["enum"]
            documented = enumeration.get("enumDescriptions")
            assert documented is not None, f"{values} is published with no per-value docs"
            assert len(documented) == len(values), f"{values} and its docs are not parallel"
            assert all(documented), f"{values} has a blank entry: {documented}"
            for value, text in zip(values, documented, strict=True):
                assert f"``{value}`` - {text}" in enumeration["description"], (
                    f"the description of {values} does not spell out {value!r}; the two "
                    f"spellings of the value documentation have come apart"
                )

    def test_every_kind_of_data_object_documents_its_own_tag(self) -> None:
        """``kind`` decides the shape of the whole definition, so it is the worst blank hover."""
        from ddd.models import ObjectKind

        schema = published("component")
        tagged = {
            definition["properties"]["kind"]["const"]: definition["properties"]["kind"]
            for definition in schema["$defs"].values()
            if "const" in definition.get("properties", {}).get("kind", {})
        }
        for object_kind in ObjectKind:
            assert object_kind.value in tagged, f"{object_kind.value} is not a variant"
            assert tagged[object_kind.value].get("description"), (
                f"'kind': '{object_kind.value}' hovers blank"
            )

    @pytest.mark.parametrize("kind", published_kinds())
    def test_no_description_reaches_an_editor_as_markup_it_cannot_render(self, kind: str) -> None:
        """The docstrings are written as rST for the api documentation; a schema shows markdown.

        An interpreted role left in place arrives as the literal characters ``:class:`Foo```,
        which is noise at best and, since it names something in the python sources, points a
        reader at code they do not have.
        """
        offenders = [
            text for text in descriptions_in(published(kind)) if re.search(r":\w+:`", text)
        ]
        assert not offenders, f"reStructuredText roles left in {kind}: {offenders}"

    @pytest.mark.parametrize("kind", published_kinds())
    def test_no_description_sends_the_reader_into_the_python_sources(self, kind: str) -> None:
        """Whoever reads these writes json; a dotted module path is an answer to nobody."""
        offenders = [text for text in descriptions_in(published(kind)) if "ddd.models" in text]
        assert not offenders, f"{kind} refers the reader to python: {offenders}"


class Undocumented(StrEnum):
    """A set of values whose members say nothing about themselves.

    Defined here rather than found in the sources, because every enum the product publishes is
    documented - which is exactly what makes the path taken when one is not hard to reach.
    """

    RED = "red"
    GREEN = "green"


class PartlyDocumented(StrEnum):
    """One member with a docstring under it and one without."""

    KNOWN = "known"
    """What this one is for."""

    UNKNOWN = "unknown"


class Tagged(BaseModel):
    """A model over both, to see what a generator makes of them."""

    shade: Undocumented
    tag: Literal[Undocumented.RED] = Undocumented.RED


class TestCarryingTheDocumentationAcross:
    """The machinery behind :class:`PublishedSchema`, at the edges the contracts do not reach."""

    @pytest.mark.parametrize(
        ("written", "shown"),
        [
            (":class:`Limits`", "``Limits``"),
            (":data:`~ddd.models.common.Identifier`", "``Identifier``"),
            (":doc:`the project file <project>`", "``the project file``"),
            (":doc:`<project>`", "``project``"),
            ("nothing to do here", "nothing to do here"),
        ],
    )
    def test_a_role_becomes_the_text_sphinx_would_have_shown(
        self, written: str, shown: str
    ) -> None:
        from ddd.models.schema import as_markdown

        assert as_markdown(written) == shown

    def test_the_marker_of_an_rst_literal_block_does_not_reach_the_reader(self) -> None:
        """In markdown the indent alone makes the block, so the ``::`` is just two characters."""
        from ddd.models.schema import as_markdown

        assert as_markdown("accepts this form::\n\n    {}\n") == "accepts this form:\n\n    {}\n"

    def test_a_member_with_no_docstring_is_left_out(self) -> None:
        from ddd.models.schema import value_documentation

        assert value_documentation(PartlyDocumented) == {"known": "What this one is for."}

    def test_annotated_assignments_are_read_as_well_as_plain_ones(self) -> None:
        """Enum members are assigned, model fields are annotated; both carry a docstring."""
        from ddd.models import Project
        from ddd.models.schema import member_docstrings

        assert "also the a2l project and module name" in member_docstrings(Project)["name"]

    def test_a_class_with_no_readable_source_documents_nothing(self) -> None:
        """A schema published without the per-value docs beats a schema not published at all."""
        from ddd.models.schema import member_docstrings

        assert member_docstrings(type("Built", (), {})) == {}

    def test_something_that_is_not_a_class_documents_nothing(self) -> None:
        from ddd.models.schema import member_docstrings

        assert member_docstrings(commands) == {}  # type: ignore[arg-type]

    def test_an_undocumented_set_of_values_is_published_as_pydantic_wrote_it(self) -> None:
        """No half measure: silence is better than a dropdown that explains only some entries."""
        from ddd.models.schema import PublishedSchema

        schema = Tagged.model_json_schema(schema_generator=PublishedSchema)
        assert schema["$defs"]["Undocumented"]["enum"] == ["red", "green"]
        assert "enumDescriptions" not in schema["$defs"]["Undocumented"]
        assert "description" not in schema["properties"]["tag"]


class TestCommittedSchemas:
    """The schemas in ``schemas/`` are generated, committed and pointed at by the examples.

    Committing a derived artefact is a deliberate exception to how the rest of this
    repository works, and it is made for one reason: an editor cannot bind a description
    file to a schema that is not there, so cloning the project or unpacking the sdist has to
    be enough to get completion and validation on the examples. The price of the exception is
    that it can go stale, which is what these tests are for.
    """

    def test_every_committed_schema_is_current(self) -> None:
        from ddd.cli import _SCHEMA_MODELS, SCHEMA_FILENAME, schema_text

        for kind in sorted(_SCHEMA_MODELS):
            path = ROOT / "schemas" / SCHEMA_FILENAME.format(kind=kind)
            assert path.is_file(), f"{path.name} is missing; run: ddd schema all -o schemas"
            assert path.read_text(encoding="utf-8") == schema_text(kind), (
                f"{path.name} is out of date with the models. Regenerate it with "
                f"'ddd schema all -o schemas' and commit the result."
            )

    def test_every_example_points_at_a_schema_that_exists(self) -> None:
        """A dangling ``$schema`` is worse than none: the editor reports it on every open."""
        bound = 0
        for path in sorted((ROOT / "examples").rglob("*.ddd.json")):
            document = json.loads(path.read_text(encoding="utf-8"))
            reference = document.get("$schema")
            assert reference is not None, f"{path.name} carries no $schema binding"
            target = (path.parent / reference).resolve()
            assert target.is_file(), f"{path.name} points at {reference}, which does not exist"
            # and it points at the schema of the kind it actually is
            kind = next(
                key
                for key in ("project", "component", "types", "units", "sections", "constants")
                if key in document
            )
            assert target.name == f"ddd_{kind}.schema.json", (
                f"{path.name} is a {kind} file but points at {target.name}"
            )
            bound += 1
        assert bound, "no examples were checked; has the layout changed?"

    def test_the_examples_validate_against_their_own_schemas(self) -> None:
        """What an editor does with the binding, done here so it cannot silently break.

        jsonschema is a development dependency rather than something this skips without, which
        is the whole point: skipping is how a check that guards an integration stops running
        without anybody deciding that it should.
        """
        for path in sorted((ROOT / "examples").rglob("*.ddd.json")):
            document = json.loads(path.read_text(encoding="utf-8"))
            schema = json.loads((path.parent / document["$schema"]).read_text(encoding="utf-8"))
            jsonschema.validate(document, schema)


class TestPackagedResources:
    """Paths into the installed package, which a source checkout can hide being wrong.

    ``ddd templates-dir`` and ``ddd cmake-dir`` look for files that are force-included into
    the wheel. Both fall back to the repository layout, so a miscounted ``parents[n]`` still
    works in a checkout and fails only once somebody installs the wheel - which is to say,
    only for a customer.
    """

    def test_the_package_root_is_the_ddd_package(self) -> None:
        import ddd
        from ddd.backends.c.backend import package_root

        assert package_root() == Path(ddd.__file__).resolve().parent

    def test_the_wheel_ships_what_those_commands_look_for(self) -> None:
        """Each force-included destination has to be where the lookup expects to find it."""
        metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        destinations = set(
            metadata["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"].values()
        )
        assert "ddd/templates" in destinations, "ddd templates-dir would find nothing installed"
        assert "ddd/cmake/Ddd.cmake" in destinations, "ddd cmake-dir would find nothing installed"


class TestContinuousIntegration:
    """The classifiers are a public claim about what this package runs on."""

    def test_every_advertised_python_version_is_tested(self) -> None:
        """A version advertised on the index but absent from the matrix is untested support.

        Adding a classifier costs one line and nothing checks it, so the claim and the
        evidence drift apart silently - in the direction of claiming more.
        """
        metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        advertised = {
            classifier.rsplit("::", 1)[1].strip()
            for classifier in metadata["project"]["classifiers"]
            if classifier.startswith("Programming Language :: Python ::")
        }
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        listed = re.search(r"python-version: \[([^]]*)\]", workflow)
        assert listed is not None, "the ci matrix no longer lists the python versions"
        tested = set(re.findall(r"\d+\.\d+", listed.group(1)))
        assert tested == advertised, (
            f"ci tests python {sorted(tested)} but the package advertises {sorted(advertised)}"
        )


class TestPublishedDocumentation:
    """The documentation is a deliverable with an address, published by ci.

    The two properties pinned here are the ones that fail silently. Everything else about
    ``docs.yml`` announces itself: a build that cannot find its input, or an upload of a
    directory that was never written, is a red run.
    """

    def test_the_published_address_is_the_same_everywhere(self) -> None:
        """A customer reaches the documentation through the package metadata on the index.

        Nothing resolves that url at build time, so a wrong one is a 404 with the product's
        name on it, found by whoever was trying to read the manual.
        """
        metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        developer_documentation = (ROOT / "docs" / "developer_documentation.rst").read_text(
            encoding="utf-8"
        )
        assert metadata["project"]["urls"]["Documentation"] == DOCS_URL
        assert DOCS_URL in README
        assert DOCS_URL in developer_documentation

    def test_the_published_build_treats_warnings_as_errors(self) -> None:
        """Dropping ``-W`` costs nothing visible and quietly ends the guarantee.

        The reference pages are generated from the sources, so a renamed option or a removed
        field turns into a warning about a reference that no longer resolves. With warnings as
        errors that is a failed run; without it the page is published with the section simply
        missing, which nobody notices, because the documentation still builds.
        """
        command = next(line for line in DOCS_WORKFLOW.splitlines() if "sphinx-build" in line)
        assert "-W" in command.split(), (
            f"the published documentation is built without -W: {command.strip()}"
        )

    def test_only_master_and_a_release_are_ever_published(self) -> None:
        """The deploy job names the two things it publishes rather than only an event.

        A pull request from a fork proposes arbitrary content and runs on this workflow
        definition. Guarding the deployment by event alone would leave opening one enough to
        publish somebody else's revision as the product's documentation - and ``pull_request``
        is neither of the two conditions below, which is the whole point of spelling them out.
        """
        deploy = DOCS_WORKFLOW.split("\n  deploy:\n", 1)[1]
        condition = next(line for line in deploy.splitlines() if line.strip().startswith("if:"))
        assert "github.ref == 'refs/heads/master'" in condition, (
            f"the deployment is not guarded by the branch: {condition.strip()}"
        )
        assert "github.event_name == 'release'" in condition, (
            f"a release does not deploy its own documentation: {condition.strip()}"
        )

    def test_the_deployment_is_read_back_from_the_site_it_published_to(self) -> None:
        """The archive branch and the served site are two publishes, and they can disagree.

        The branch is a git push and the site is an artifact handed to Pages, so nothing
        makes them agree by construction. When they parted, every step of every job still
        reported success: ``v0.6.0`` sat in the archive, named in the version index beside
        it, while the site went on serving a build assembled before the release existed -
        a complete set of documentation at a url that answered 404, with nothing red
        anywhere to say so, and the version menu never offering it.

        So the run ends by reading back what it just published, which is the only statement
        about the site that is made from outside the machinery that writes it.
        """
        deploy = DOCS_WORKFLOW.split("actions/deploy-pages", 1)
        assert len(deploy) == 2, "the workflow no longer deploys exactly once"
        after = deploy[1]
        assert "versions.json" in after and "${SLOT}" in after, (
            "nothing after the deployment checks that the site serves the version just "
            "published, so a site one build behind reports success"
        )
        assert "cb=" in after, (
            "the read back is cacheable, so an edge answering for the previous build passes"
        )

    def test_a_release_tag_has_to_carry_its_prefix(self) -> None:
        """The ``v`` is load bearing, and both workflows have to insist on it.

        A release is published under a directory named after its tag, and the version menu
        lists only the directories starting with ``v``. So a tag of ``0.5.0`` deploys a
        complete copy of the documentation to a url nothing links to, leaves the root
        redirecting at ``latest``, and reports success. It happened once, because the
        version check stripped an optional ``v`` before comparing and so accepted both
        spellings; what caught it was an unrelated environment rule.
        """
        assert '"$GITHUB_REF_NAME" != "v$version"' in PUBLISH_WORKFLOW, (
            "the release tag is compared without its prefix, which accepts a tag the "
            "documentation site cannot publish under"
        )
        assert "v[0-9]*)" in DOCS_WORKFLOW, (
            "the deployment no longer refuses a tag the version menu would never list"
        )

    def test_nothing_is_published_under_an_unchecked_tag(self) -> None:
        """The tag check lives in one job, so every job that publishes has to be behind it.

        The extension job names the .vsix it uploads after the tag. Left needing only the
        test job it ran beside the check rather than after it, which for an upload onto a
        published release is the wrong side to be on.
        """
        extension = PUBLISH_WORKFLOW.split("\n  extension:\n", 1)[1]
        needs = next(line for line in extension.splitlines() if line.strip().startswith("needs:"))
        assert "build" in needs, (
            f"the extension is published without waiting for the tag check: {needs.strip()}"
        )

    def test_the_archive_history_is_not_published(self) -> None:
        """The site is assembled in a git working tree, and only the tree gets uploaded.

        Past versions are restored from the ``gh-pages`` branch, so the directory handed to
        the upload is a checkout: it carries the branch's whole history, and on a first run
        the credentials the push authenticated with are sitting in its remote url. Publishing
        that changes nothing a reader can see, which is exactly why it has to be pinned here.
        """
        steps = DOCS_WORKFLOW.split("upload-pages-artifact")
        assert len(steps) == 2, "the workflow no longer uploads exactly one Pages artifact"
        assert "rm -rf site/.git" in steps[0], (
            "the archive's git directory is uploaded to the Pages site along with the html"
        )
