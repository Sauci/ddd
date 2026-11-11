"""What a fix writes, asked of the project over a matrix of declarations.

The cases of the other suites each name one shape: a float under an enumeration, a string beside
a unit. This one holds the rule itself over every pair of a set of declarations that disagree in
every way a definition can disagree without being refused - what is offered, to an editor and to
the page, leaves every file it writes loading, and what a declaration would be once a key is
written is judged as the project judges it: by reading the file and analysing it, which is what
``ddd gui`` counts a file loaded by. A fix that writes a file the project refuses stops it being
analysed, and every further fix is refused until somebody mends the file by hand.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from conftest import MODE_T, TEXT, built_of, component, declare, project, write_tree
from ddd.analysis import analyze
from ddd.diagnostics import DiagnosticBag, Severity
from ddd.editing import Operation, edit_text
from ddd.finding_fixes import fixes_for
from ddd.loading import load_workspace
from ddd.lsp.edits import PROPAGATED_KEYS, actions, loading_problem
from ddd.lsp.navigation import LOAD_CHECKS
from ddd.lsp.ranges import Document, read
from ddd.models import ComponentFile, definition_problem
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
    "f64": {"datatype": "float64"},
    "f64-half": {
        "datatype": "float64",
        "conversion": {"kind": "linear", "factor": 0.5},
    },
    "u16-double": {"datatype": "uint16", "conversion": {"kind": "linear", "factor": 2}},
}
"""Declarations of one variable that load, each in a corner of what a definition may not say: a
float beside an enumeration, a string beside a unit or limits or without its dimension, an array
and a scalar, a scaling and an identity - and a double beside a scaling, whose limits run past
the largest float there is, which the models take and the analysis refuses. Every pair of them is
a writer and a reader that disagree about something."""


def not_loaded(text: str, where: Path) -> list[str]:
    """What reading and analysing a component description files that keeps the file from loading,
    as ``ddd gui`` counts it - an error of one of :data:`ddd.lsp.navigation.LOAD_CHECKS` - or
    nothing where it loads.

    The loader and the analysis both, because ``schema`` is filed by both: the models say what the
    keys of a definition may hold together, and the analysis says the rest that asks nothing of
    the project - limits that are not finite, a shape past the caps - and no severity turns either
    down. The description is the one file of a project of its own, written under ``where``, so that
    what is judged is the definition.
    """
    write_tree(where, {"p.ddd.json": project("P", "c.ddd.json"), "c.ddd.json": text})
    bag = DiagnosticBag()
    workspace = load_workspace(where / "p.ddd.json", bag)
    if workspace is not None and not _refusals(bag):
        analyze(workspace, bag)
    return _refusals(bag)


def _refusals(bag: DiagnosticBag) -> list[str]:
    return [
        finding.message
        for finding in bag
        if finding.check in LOAD_CHECKS and finding.severity is Severity.ERROR
    ]


def description(variant: str, scope: str) -> str:
    """One component declaring ``V`` as the variant says, as a description file."""
    return json.dumps(component("C", declare(scope, "V", **VARIANTS[variant])), indent=2)


@pytest.mark.parametrize("variant", VARIANTS)
def test_every_variant_loads_on_its_own(tmp_path: Path, variant: str) -> None:
    assert not_loaded(description(variant, "output"), tmp_path) == []
    assert not_loaded(description(variant, "input"), tmp_path) == []


def test_the_oracle_refuses_what_the_analysis_alone_refuses(tmp_path: Path) -> None:
    """A double under a factor of two is a file the models take: ``ComponentFile`` reads it, and
    the analysis is what says its limits are not finite. The matrix is no judge of a rule if the
    thing it judges by cannot tell the two apart."""
    refused = component(
        "C", declare("output", "V", "float64", conversion={"kind": "linear", "factor": 2})
    )
    ComponentFile.model_validate(refused)
    assert not_loaded(json.dumps(refused), tmp_path) == [
        "the limits derived from 'float64' and this conversion are not finite"
    ]


@pytest.mark.parametrize(
    "stated",
    [
        {"dimensions": [1] * 65},
        {"dimensions": [10_000, 1_001]},
        {"dimensions": [4_000, 4_000]},
        {"kind": "axis", "size": 10_000_001},
    ],
    ids=["65-dimensions", "past-the-elements", "two-large-ones", "axis"],
)
def test_a_shape_past_the_caps_is_said_as_the_analysis_files_it(
    tmp_path: Path, stated: dict[str, Any]
) -> None:
    """The caps are the analysis's, and a definition says them before it is written: in the
    sentence the analysis files, which is what the page shows and what ``ddd check`` reports."""
    entry = declare("output", "V", "uint8", **stated)
    said = definition_problem(entry["definition"])
    assert said is not None
    assert not_loaded(json.dumps(component("C", entry)), tmp_path) == [said]


def test_the_limits_are_said_before_the_shape_as_the_analysis_files_them(tmp_path: Path) -> None:
    """A declaration whose limits are refused is dropped and its shape is never weighed: the
    analysis files the limits alone, and a definition says them first."""
    entry = declare(
        "output", "V", "float64", conversion={"kind": "linear", "factor": 2}, dimensions=[1] * 65
    )
    said = definition_problem(entry["definition"])
    assert said == "the limits derived from 'float64' and this conversion are not finite"
    assert not_loaded(json.dumps(component("C", entry)), tmp_path) == [said]


@pytest.mark.parametrize("writer", VARIANTS)
def test_every_fix_offered_leaves_every_file_it_writes_loading(tmp_path: Path, writer: str) -> None:
    """The editor's actions over the whole declaration, and the page's buttons for the finding on
    it, at the writer and at each reader of it: each applied, and every file it writes read and
    analysed by the project."""
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
                    if not_loaded(text, tmp_path / "judged"):
                        refused.append(f"{writer} / {reader}: {action['title']} writes {file}")
            for fix in fixes_for("definition-mismatch", path, DEFINITION, {}, built):
                for change in fix.changes:
                    wrote += 1
                    text = change.path.read_text(encoding="utf-8")
                    if not_loaded(edit_text(text, change.operations), tmp_path / "judged"):
                        refused.append(
                            f"{writer} / {reader}: {fix.title} writes {change.path.name}"
                        )
    assert wrote, "a matrix that offers nothing proves nothing"
    assert not refused, "\n".join(refused)


def test_what_a_declaration_would_be_is_judged_as_the_project_judges_it(tmp_path: Path) -> None:
    """Every key one variant states, written into another or taken out of it where the other
    states it: the answer of :func:`ddd.lsp.edits.loading_problem` and the project's own, over the
    text the edit engine leaves, are one - in both directions, so a rule the models or the
    analysis hold that the answer misses fails here as surely as a file it refuses without cause -
    and what it says is among what the project files."""
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
                filed = not_loaded(edit_text(text, [operation]), tmp_path)
                problem = loading_problem(document, DEFINITION, key, raw)
                would_load += not filed
                would_not += bool(filed)
                if (problem is None) != (not filed):
                    disagreed.append(f"{source} -> {target}: {key} {raw!r}: files {filed}")
                elif problem is not None and not any(problem in message for message in filed):
                    disagreed.append(f"{source} -> {target}: {key} {raw!r}: says {problem!r}")
    assert would_load and would_not, "the matrix has to hold both answers"
    assert not disagreed, "\n".join(disagreed)
