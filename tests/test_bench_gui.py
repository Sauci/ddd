"""``tools/bench_gui.py``: every measure of the server half, on a small generated project."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from bench_gui import NAMES, main, measure
from generate_project import generate

from ddd.gui.api import Api
from ddd.gui.session import Session
from ddd.variables import declarations_of


def node_at(document, pointer: str):
    """The object or list entry ``pointer`` names in ``document``, dotted with ``[index]`` for a
    list entry, exactly as a :class:`~ddd.lsp.navigation.Site` spells one."""
    node = document
    for part in pointer.split("."):
        if "[" in part:
            key, index = part[:-1].split("[")
            node = node[key][int(index)]
        else:
            node = node[part]
    return node


def test_every_measure_is_taken_in_order_with_its_size(tmp_path: Path) -> None:
    made = generate(tmp_path / "p", 600, "many", missing_ids=0.5, unread=0.5)
    taken = measure(made.project)
    assert [each.name for each in taken] == list(NAMES)
    assert all(each.milliseconds >= 0 for each in taken)
    sized = {each.name for each in taken if each.size is not None}
    assert sized == {
        "state",
        "graph",
        "units",
        "types",
        "shared",
        "files",
        "variable",
        "unit",
        "remove judged",
        "edit answered",
    }


def test_the_project_is_left_as_it_was_generated(tmp_path: Path) -> None:
    made = generate(tmp_path / "p", 600, "many")
    before = {path: path.read_bytes() for path in sorted((tmp_path / "p").rglob("*.json"))}
    measure(made.project)
    assert {path: path.read_bytes() for path in sorted((tmp_path / "p").rglob("*.json"))} == before


def test_the_command_line_prints_one_row_per_measure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    made = generate(tmp_path / "p", 600, "large")
    assert main([str(made.project)]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[:2] == ["| project | measure | ms | bytes |", "| --- | --- | --- | --- |"]
    assert [line.split(" | ")[1] for line in lines[2:]] == list(NAMES)


def test_a_project_with_no_component_file_is_refused(tmp_path: Path) -> None:
    made = generate(tmp_path / "p", 120, "many")
    document = json.loads(made.project.read_text(encoding="utf-8"))
    document["project"]["includes"] = ["units.ddd.json"]
    made.project.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError) as raised:
        measure(made.project)
    assert str(raised.value) == f"{made.project} has no component file for the benchmark to touch"


def test_a_project_with_fewer_than_two_units_is_refused(tmp_path: Path) -> None:
    made = generate(tmp_path / "p", 120, "many")
    for component in sorted((tmp_path / "p" / "components").glob("*.ddd.json")):
        text = re.sub(r'"unit": "[^"]+"', '"unit": "rpm"', component.read_text(encoding="utf-8"))
        component.write_text(text, encoding="utf-8")
    with pytest.raises(RuntimeError) as raised:
        measure(made.project)
    assert str(raised.value) == (
        f"{made.project} states 1 unit(s); the benchmark needs at least two, so the edit has "
        "another one to move the declaration to"
    )


def test_a_declaration_with_no_unit_of_its_own_is_refused(tmp_path: Path) -> None:
    made = generate(tmp_path / "p", 120, "many")
    session = Session(made.project.parent)
    session.open(made.project)
    built = session.revision.index
    assert built is not None
    variables = sorted(built.declarations)
    variable = variables[len(variables) // 2]
    site = declarations_of(built, variable, {})[0].site
    document = json.loads(site.path.read_text(encoding="utf-8"))
    del node_at(document, site.pointer)["unit"]
    site.path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError) as raised:
        measure(made.project)
    assert str(raised.value) == (
        f"{variable!r}'s first declaration in {made.project} does not state its own unit, "
        "which the benchmark needs to choose the edit's own change"
    )


def test_remove_judged_asks_to_remove_the_roots_first_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ruling 1: the root's first entry, not its last."""
    made = generate(tmp_path / "p", 120, "many")
    judged = []
    original = Api.handle

    def spying(self, method, path, query, body):
        if path == "/api/files-plan":
            judged.append(dict(query))
        return original(self, method, path, query, body)

    monkeypatch.setattr(Api, "handle", spying)
    measure(made.project)
    assert judged == [
        {
            "action": ["remove"],
            "path": [(made.project.parent / "units.ddd.json").resolve().as_posix()],
        }
    ]


def test_the_edit_moves_to_the_next_unit_of_the_projects_own_sorted_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ruling 2: the next unit of the project's own ``revision.index.units``, sorted, wrapping -
    not the generator's own unsorted ``UNITS``."""
    made = generate(tmp_path / "p", 120, "many")
    session = Session(made.project.parent)
    session.open(made.project)
    built = session.revision.index
    assert built is not None
    variables = sorted(built.declarations)
    variable = variables[len(variables) // 2]
    current = json.loads(declarations_of(built, variable, {})[0].stated["unit"])
    units = sorted(built.units)
    expected = units[(units.index(current) + 1) % len(units)]

    edited = []
    original = Api.handle

    def spying(self, method, path, query, body):
        if method == "POST" and path == "/api/edit":
            edited.append(body)
        return original(self, method, path, query, body)

    monkeypatch.setattr(Api, "handle", spying)
    measure(made.project)
    assert len(edited) == 1
    operation = json.loads(edited[0])["changes"][0]["operations"][0]
    assert json.loads(operation["raw"]) == expected
