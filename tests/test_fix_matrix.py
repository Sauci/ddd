"""What a fix writes, asked of the loader over a matrix of declarations.

The cases of the other suites each name one shape: a float under an enumeration, a string beside
a unit. This one holds the rule itself over every pair of a set of declarations that disagree in
every way a definition can disagree without being refused - what is offered, to an editor and to
the page, leaves every file it writes loading, and what a declaration would be once a key is
written is judged as the loader judges it. A fix that writes a file the loader refuses stops the
project being analysed, and every further fix is refused until somebody mends the file by hand.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from conftest import MODE_T, TEXT, built_of, component, declare
from ddd.editing import Operation, edit_text
from ddd.finding_fixes import fixes_for
from ddd.loading import parse_json_text
from ddd.lsp.edits import PROPAGATED_KEYS, actions, loading_problem
from ddd.lsp.ranges import Document, read
from ddd.models import ComponentFile
from test_lsp import rewritten_by

DEFINITION = "component.interface[0].definition"

VARIANTS: dict[str, dict[str, Any]] = {
    "u16": {"datatype": "uint16"},
    "f32": {"datatype": "float32"},
    "u8-rpm": {"datatype": "uint8", "unit": "rpm"},
    "u16-scaled": {
        "datatype": "uint16",
        "conversion": {"kind": "linear", "factor": 0.5},
        "limits": {"min": 0, "max": 100},
    },
    "u8-enum": {"datatype": "uint8", "conversion": MODE_T},
    "u16-enum": {"datatype": "uint16", "conversion": MODE_T},
    "u8-text": {"datatype": "uint8", "conversion": TEXT, "dimensions": [8]},
    "s8-text": {"datatype": "sint8", "conversion": TEXT, "dimensions": [4]},
    "u8-block": {"datatype": "uint8", "dimensions": [8]},
    "u8-block-rpm": {"datatype": "uint8", "dimensions": [8], "unit": "rpm"},
    "u8-block-limits": {"datatype": "uint8", "dimensions": [8], "limits": {"min": 0, "max": 9}},
    "f32-limits": {"datatype": "float32", "limits": {"min": 0, "max": 1}},
}
"""Declarations of one variable that load, each in a corner of what a definition may not say: a
float beside an enumeration, a string beside a unit or limits or without its dimension, an array
and a scalar, a scaling and an identity. Every pair of them is a writer and a reader that
disagree about something."""


def loads(text: str) -> bool:
    """Whether the loader takes a component description: what ``ddd check`` files as ``schema``
    otherwise, which no severity turns down."""
    try:
        ComponentFile.model_validate(parse_json_text(text))
    except ValueError:
        return False
    return True


def description(variant: str, scope: str) -> str:
    """One component declaring ``V`` as the variant says, as a description file."""
    return json.dumps(component("C", declare(scope, "V", **VARIANTS[variant])), indent=2)


@pytest.mark.parametrize("variant", VARIANTS)
def test_every_variant_loads_on_its_own(variant: str) -> None:
    assert loads(description(variant, "output"))
    assert loads(description(variant, "input"))


@pytest.mark.parametrize("writer", VARIANTS)
def test_every_fix_offered_leaves_every_file_it_writes_loading(tmp_path: Path, writer: str) -> None:
    """The editor's actions over the whole declaration, and the page's buttons for the finding on
    it, at the writer and at each reader of it: each applied, and every file it writes read by
    the loader."""
    wrote = 0
    refused: list[str] = []
    for reader in VARIANTS:
        if reader == writer:
            continue
        built, root = built_of(
            tmp_path / reader,
            **{
                "w.ddd.json": component("W", declare("output", "V", **VARIANTS[writer])),
                "r.ddd.json": component("R", declare("input", "V", **VARIANTS[reader])),
            },
        )
        for name in ("w.ddd.json", "r.ddd.json"):
            path = root / name
            cache: dict[Path, Document] = {}
            for action in actions(built, path, read(path, cache), DEFINITION, cache):
                for file, text in rewritten_by(action["edit"]["changes"]).items():
                    wrote += 1
                    if not loads(text):
                        refused.append(f"{writer} / {reader}: {action['title']} writes {file}")
            for fix in fixes_for("definition-mismatch", path, DEFINITION, {}, built):
                for change in fix.changes:
                    wrote += 1
                    text = change.path.read_text(encoding="utf-8")
                    if not loads(edit_text(text, change.operations)):
                        refused.append(
                            f"{writer} / {reader}: {fix.title} writes {change.path.name}"
                        )
    assert wrote, "a matrix that offers nothing proves nothing"
    assert not refused, "\n".join(refused)


def test_what_a_declaration_would_be_is_judged_as_the_loader_judges_it() -> None:
    """Every key one variant states, written into another or taken out of it where the other
    states it: the answer of :func:`ddd.lsp.edits.loading_problem` and the loader's own, over the
    text the edit engine leaves, are one - in both directions, so a rule the models hold that the
    answer misses fails here as surely as a file it refuses without cause."""
    would_load = would_not = 0
    disagreed: list[str] = []
    for target in VARIANTS:
        text = description(target, "input")
        document = Document(text)
        for source in VARIANTS:
            donor = Document(description(source, "output"))
            for key in sorted(PROPAGATED_KEYS):
                pointer = f"{DEFINITION}.{key}"
                raw = donor.raw_at(pointer)
                if raw is None and document.raw_at(pointer) is None:
                    continue
                operation = Operation("remove" if raw is None else "set", pointer, raw)
                after = loads(edit_text(text, [operation]))
                judged = loading_problem(document, DEFINITION, key, raw) is None
                would_load += after
                would_not += not after
                if judged != after:
                    disagreed.append(f"{source} -> {target}: {key} {raw!r}: loads {after}")
    assert would_load and would_not, "the matrix has to hold both answers"
    assert not disagreed, "\n".join(disagreed)
