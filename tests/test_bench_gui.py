"""``tools/bench_gui.py``: every measure of the server half, on a small generated project."""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path

import bench_gui
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
        "findings page",
        "findings of a file",
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


def test_the_findings_are_asked_a_page_from_the_first_and_the_first_component_s_whole(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``findings page`` asks the Findings tab's first page - a hundred from the first - and
    ``findings of a file`` every finding of the first component's file, sorted, as its page asks
    them: no limit."""
    made = generate(tmp_path / "p", 120, "many", missing_ids=0.5, unread=0.5)
    asked = []
    original = Api.handle

    def spying(self, method, path, query, body):
        if path == "/api/findings":
            asked.append(dict(query))
        return original(self, method, path, query, body)

    monkeypatch.setattr(Api, "handle", spying)
    taken = {each.name: each for each in measure(made.project)}
    first = sorted((made.project.parent / "components").glob("*.ddd.json"))[0]
    assert asked == [
        {"offset": ["0"], "limit": ["100"]},
        {"file": [first.resolve().as_posix()]},
    ]
    assert taken["findings page"].size is not None
    assert taken["findings of a file"].size is not None


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


def test_open_the_analysis_and_the_edit_are_timed_until_their_analysis_has_landed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The session analyses on a thread of its own, so a measure ending where its request
    returns times the request alone: ``open``, ``analysis`` and ``edit analysed`` each end once
    the session has settled - its analysis landed - and ``edit answered`` ends before."""
    made = generate(tmp_path / "p", 120, "many")
    happened: list[str] = []

    def recording(name: str, real):
        def recorded(*arguments, **keywords):
            answer = real(*arguments, **keywords)
            happened.append(name)
            return answer

        return recorded

    def posting(real):
        def posted(self, method, path, query, body):
            answer = real(self, method, path, query, body)
            if method == "POST":
                happened.append(path)
            return answer

        return posted

    monkeypatch.setattr(Session, "open", recording("open", Session.open))
    monkeypatch.setattr(Session, "poll", recording("poll", Session.poll))
    monkeypatch.setattr(Session, "settled", recording("settled", Session.settled))
    monkeypatch.setattr(Api, "handle", posting(Api.handle))
    monkeypatch.setattr(bench_gui, "_elapsed", recording("timed", bench_gui._elapsed))
    measure(made.project)
    assert happened == [
        *("open", "settled", "timed"),  # open
        *["timed"] * 11,  # each endpoint, the two of findings, the two panels, the judged removal
        *("poll", "settled", "timed"),  # analysis
        *("/api/edit", "timed"),  # edit answered
        *("settled", "timed"),  # edit analysed
        "/api/undo",
    ]


def test_the_analyser_it_starts_has_ended_when_it_returns(tmp_path: Path) -> None:
    """``measure`` runs once per project of a run, so the analyser and the poller it starts end
    with it rather than outlive it, one pair a project."""

    def running() -> list[str]:
        names = ("ddd-gui-analyse", "ddd-gui-poll")
        return sorted(thread.name for thread in threading.enumerate() if thread.name in names)

    made = generate(tmp_path / "p", 120, "many")
    before = running()
    measure(made.project)
    assert running() == before


def test_the_session_it_measures_polls_an_hour_apart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Its own poller never polls while a run lasts: ``analysis`` polls for itself, and a poller
    noticing the moved file first would leave that poll nothing to notice."""
    made = generate(tmp_path / "p", 120, "many")
    intervals: list[float] = []
    real = Session.start

    def starting(self: Session) -> None:
        intervals.append(self.poll_interval)
        real(self)

    monkeypatch.setattr(Session, "start", starting)
    measure(made.project)
    assert intervals == [3600]
