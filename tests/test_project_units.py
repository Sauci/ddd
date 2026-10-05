"""A unit's places as its panel lists them: each variable with its component and its role."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import pytest

from conftest import (
    component,
    declare,
    project,
    struct_type,
    types,
    value_member,
    write_tree,
)
from ddd.diagnostics import Diagnostic, DiagnosticBag, Location, Severity
from ddd.findings_by_file import FindingsByFile, Pair
from ddd.loading import load_workspace
from ddd.lsp.navigation import Index, index
from ddd.lsp.ranges import Document
from ddd.project_units import places_of, unit_findings

UNIT = "component.interface[0].definition.unit"

FILES = {
    "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json", "types.ddd.json"),
    "a.ddd.json": component(
        "Alpha", declare("output", "Speed", unit="rpm"), declare("local", "Idle", unit="rpm")
    ),
    "b.ddd.json": component("Beta", declare("input", "Speed", unit="rpm")),
    "types.ddd.json": types(struct_type("Sample_t", value_member("speed", unit="rpm"))),
}


def indexed(tmp_path: Path) -> Index:
    write_tree(tmp_path, FILES)
    workspace = load_workspace(tmp_path / "p.ddd.json", DiagnosticBag())
    assert workspace is not None
    return index(workspace)


def listed(built: Index, cache: dict[Path, Document], changed: set[str]) -> list[tuple]:
    """``rpm``'s places, the files named in ``changed`` answered as changed since the analysis."""
    return [
        (place.stated.site.path.name, place.stated.name, place.component, place.role)
        for place in places_of(built, "rpm", cache, lambda path: path.name in changed)
    ]


def test_a_variable_on_a_file_unchanged_since_is_named_by_the_index_unread(tmp_path: Path) -> None:
    """Its component and role are what the analysis loaded there, and its file is never parsed:
    a unit stated in every file of a project was every file parsed, for two strings each."""
    built = indexed(tmp_path)
    cache: dict[Path, Document] = {}
    assert listed(built, cache, set()) == [
        ("a.ddd.json", "Speed", "Alpha", "produces"),
        ("a.ddd.json", "Idle", "Alpha", "local"),
        ("b.ddd.json", "Speed", "Beta", "reads"),
        ("types.ddd.json", "Sample_t.speed", None, None),
    ]
    assert cache == {}


def test_a_variable_on_a_file_changed_since_is_read_as_the_file_now_states_it(
    tmp_path: Path,
) -> None:
    """Its component and role as the file now states them, and one it no longer declares where
    the index recorded it left out."""
    built = indexed(tmp_path)
    write_tree(
        tmp_path,
        {
            "a.ddd.json": component(
                "Renamed", declare("input", "Speed", unit="rpm"), declare("local", "Other")
            )
        },
    )
    assert listed(built, {}, {"a.ddd.json"}) == [
        ("a.ddd.json", "Speed", "Renamed", "reads"),
        ("b.ddd.json", "Speed", "Beta", "reads"),
        ("types.ddd.json", "Sample_t.speed", None, None),
    ]


@pytest.mark.parametrize("changed", [set(), {"a.ddd.json", "b.ddd.json"}])
def test_each_file_holding_a_variable_is_asked_about_once(
    tmp_path: Path, changed: set[str]
) -> None:
    """However many of its places a file holds, and never a file holding none but a type's or a
    member's, whose places name no component."""
    built = indexed(tmp_path)
    asked: list[str] = []

    def since(path: Path) -> bool:
        asked.append(path.name)
        return path.name in changed

    places_of(built, "rpm", {}, since)
    assert asked == ["a.ddd.json", "b.ddd.json"]


def test_a_unit_s_findings_ask_each_file_once_however_many_places_it_holds(
    tmp_path: Path,
) -> None:
    """`a.ddd.json` holds two places of `rpm` and is named once: each file named is a path
    resolved, and the 12,500 places of the first unit of a generated project of 100,000
    declarations lie in its 3,333 component files."""
    built = indexed(tmp_path)
    named: list[str] = []

    class Counted(FindingsByFile):
        def on_any(self, paths: Iterable[Path]) -> list[Pair]:
            listed_paths = list(paths)
            named.extend(path.name for path in listed_paths)
            return super().on_any(listed_paths)

    a = (tmp_path / "a.ddd.json").resolve()
    found = Diagnostic("unknown-unit", Severity.ERROR, "not listed", Location(a, UNIT))
    assert unit_findings(built, "rpm", Counted([(a, found)])) == [(a, found)]
    assert sorted(named) == ["a.ddd.json", "b.ddd.json", "types.ddd.json"]
