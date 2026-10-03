"""``tools/bench_gui.py``: every measure of the server half, on a small generated project."""

from __future__ import annotations

import inspect
import json
import re
import threading
from pathlib import Path

import bench_gui
import pytest
from bench_gui import NAMES, main, measure
from generate_project import UNITS, generate

from conftest import landed, stopped
from ddd.gui.api import Api, Reply
from ddd.gui.session import Revision, Session
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
        "rename plan",
        "state while analysing",
        "plan while analysing",
        "edit while analysing",
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
    assert len(edited) == 2  # once idle, and once while an analysis runs
    for body in edited:
        operation = json.loads(body)["changes"][0]["operations"][0]
        assert json.loads(operation["raw"]) == expected


def planned(made_project: Path, monkeypatch: pytest.MonkeyPatch) -> list[dict[str, list[str]]]:
    """Every query ``measure`` asks ``GET /api/unit-plan`` with, over ``made_project``."""
    asked = []
    original = Api.handle

    def spying(self, method, path, query, body):
        if path == "/api/unit-plan":
            asked.append(dict(query))
        return original(self, method, path, query, body)

    monkeypatch.setattr(Api, "handle", spying)
    measure(made_project)
    return asked


def test_the_rename_plan_is_asked_once_of_the_first_unit_when_every_file_states_every_unit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every component of this generated project states every unit, so every unit is stated in
    as many files and the first by spelling is renamed - to itself followed by 2, which nothing
    uses."""
    made = generate(tmp_path / "p", 120, "many")
    texts = [path.read_text(encoding="utf-8") for path in (tmp_path / "p").glob("components/*")]
    assert all(f'"unit": "{unit}"' in text for unit in UNITS for text in texts)
    assert planned(made.project, monkeypatch) == [
        {"action": ["rename"], "unit": ["A"], "to": ["A2"]}
    ]


def test_the_rename_plan_asks_for_the_unit_stated_in_the_most_files_by_a_name_nobody_uses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Counted in files, not in statements, and renamed to a spelling the project neither states
    nor lists: ``rpm`` is stated in all four files, though ``kPa`` is stated more often in one
    alone; ``rpm2`` is stated and ``rpm3`` listed, so the plan renames ``rpm`` to ``rpm4``."""
    made = generate(tmp_path / "p", 120, "many")
    first, *others = sorted((tmp_path / "p" / "components").glob("*.ddd.json"))
    text = re.sub(r'"unit": "[^"]+"', '"unit": "kPa"', first.read_text(encoding="utf-8"))
    text = text.replace('"unit": "kPa"', '"unit": "rpm"', 1).replace(
        '"unit": "kPa"', '"unit": "rpm2"', 1
    )
    first.write_text(text, encoding="utf-8")
    for other in others:
        moved = other.read_text(encoding="utf-8").replace('"unit": "kPa"', '"unit": "Nm"')
        other.write_text(moved, encoding="utf-8")
    units = made.project.parent / "units.ddd.json"
    vocabulary = json.loads(units.read_text(encoding="utf-8"))
    vocabulary["units"].append("rpm3")
    units.write_text(json.dumps(vocabulary, indent=2) + "\n", encoding="utf-8")

    def stating(unit: str) -> list[int]:
        """How often each component file states ``unit``."""
        return [
            path.read_text(encoding="utf-8").count(f'"unit": "{unit}"') for path in (first, *others)
        ]

    assert all(stating("rpm"))
    kpa = stating("kPa")
    assert kpa[0] > sum(stating("rpm"))
    assert not any(kpa[1:])
    assert planned(made.project, monkeypatch) == [
        {"action": ["rename"], "unit": ["rpm"], "to": ["rpm4"]}
    ]


def test_a_refused_rename_plan_ends_the_run_once_the_edit_is_undone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A refusal is no plan: its time would read as one."""
    made = generate(tmp_path / "p", 120, "many")
    before = {path: path.read_bytes() for path in sorted((tmp_path / "p").rglob("*.json"))}
    original = Api.handle
    refusal = {"error": "unreadable", "message": "a refusal made up for the test"}

    def refusing(self, method, path, query, body):
        if path == "/api/unit-plan":
            return Reply(409, refusal)
        return original(self, method, path, query, body)

    monkeypatch.setattr(Api, "handle", refusing)
    with pytest.raises(RuntimeError) as raised:
        measure(made.project)
    assert str(raised.value) == f"the benchmark's own rename plan was refused: {refusal}"
    assert {path: path.read_bytes() for path in sorted((tmp_path / "p").rglob("*.json"))} == before


def test_open_the_analysis_and_the_edit_are_timed_until_their_analysis_has_landed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The session analyses on a thread of its own, so a measure ending where its request
    returns times the request alone: ``open``, ``analysis`` and ``edit analysed`` each end once
    the session has settled - its analysis landed - and ``edit answered`` ends before. ``rename
    plan`` is timed after the edit's analysis has landed and before the undo. Then, over the
    second session, each measure under load is asked once an analysis has begun
    (:func:`bench_gui._analysing`), and the session settles before the next one asks its own;
    the edit is undone last.

    Recorded on this thread alone: the second session's poller polls on a thread of its own,
    whenever its second comes round."""
    made = generate(tmp_path / "p", 120, "many")
    happened: list[str] = []

    def recording(name: str, real):
        def recorded(*arguments, **keywords):
            answer = real(*arguments, **keywords)
            if threading.current_thread() is threading.main_thread():
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
    monkeypatch.setattr(bench_gui, "_analysing", recording("analysing", bench_gui._analysing))
    measure(made.project)
    assert happened == [
        *("open", "settled", "timed"),  # open
        *["timed"] * 11,  # each endpoint, the two of findings, the two panels, the judged removal
        *("poll", "settled", "timed"),  # analysis
        *("/api/edit", "timed"),  # edit answered
        *("settled", "timed"),  # edit analysed
        "timed",  # rename plan
        "/api/undo",
        *("open", "settled"),  # the second session, opened untimed
        *("poll", "analysing", "timed", "settled"),  # state while analysing
        *("poll", "analysing", "timed", "settled"),  # plan while analysing, once derived
        *("poll", "analysing", "/api/edit", "timed", "settled"),  # edit while analysing
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


def test_the_first_session_polls_an_hour_apart_and_the_second_as_ddd_gui_does(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The first session's poller never polls while a run lasts: ``analysis`` polls for itself,
    and a poller noticing the moved file first would leave that poll nothing to notice. The
    second's polls at the interval ``ddd gui`` runs its own at - the session's default, which
    ``ddd.gui.server.run`` leaves as it is - so that its rounds fall among the measures under
    load as they fall among a reader's requests."""
    made = generate(tmp_path / "p", 120, "many")
    intervals: list[float] = []
    real = Session.start

    def starting(self: Session) -> None:
        intervals.append(self.poll_interval)
        real(self)

    monkeypatch.setattr(Session, "start", starting)
    measure(made.project)
    default = inspect.signature(Session).parameters["poll_interval"].default
    assert intervals == [3600, default]
    assert default == 1.0


def test_the_plan_under_load_settles_the_middle_variables_unit_on_the_next_unit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The plan a variable's panel asks while a reader picks a unit: the edit's own change, the
    next unit after the middle variable's own, previewed on every declaration of it."""
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
    asked = []
    original = Api.handle

    def spying(self, method, path, query, body):
        if path == "/api/settle":
            asked.append(dict(query))
        return original(self, method, path, query, body)

    monkeypatch.setattr(Api, "handle", spying)
    taken = {each.name: each for each in measure(made.project)}
    assert asked == [{"name": [variable], "key": ["unit"], "raw": [json.dumps(expected)]}]
    assert taken["plan while analysing"].size is not None


class _Gate(Session):
    """A session whose analyses each wait at a gate the test opens, once they have begun."""

    gate: threading.Event
    entered: int

    def _analysed(self, project: Path) -> Revision:
        self.entered += 1
        assert self.gate.wait(timeout=10), "the test never opened the gate"
        return super()._analysed(project)


class _HeldWatched(bench_gui._Watched, _Gate):
    """The benchmark's own session, its analyses held at a gate past the moment it says that
    each has begun: ``_Watched`` comes first, so it says so before the gate holds the analysis."""

    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.gate = threading.Event()
        self.entered = 0


def test_analysing_returns_once_the_analysis_it_asks_for_has_begun(tmp_path: Path) -> None:
    """And before it lands: held at the gate, it has begun - entered, the second after
    opening's - the session says it is analysing, and the revision is still the one before."""
    made = generate(tmp_path / "p", 120, "many")
    session = _HeldWatched(made.project.parent)
    session.gate.set()
    session.start()
    try:
        session.open(made.project)
        before = landed(session).revision
        assert before is not None and session.entered == 1
        session.gate.clear()
        target = sorted((made.project.parent / "components").glob("*.ddd.json"))[0]
        bench_gui._analysing(session, target, 0.0)
        assert session.entered == 2
        snapshot = session.snapshot()
        assert snapshot.analysing and snapshot.revision is before
        session.gate.set()
        after = landed(session).revision
        assert after is not None and after.number == before.number + 1
    finally:
        session.gate.set()
        stopped(session)


def test_analysing_ends_the_run_where_no_analysis_begins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A poll that asks for nothing, and no poller to notice the file either: waited for as
    long as ``_BEGUN_SECONDS`` says, then refused rather than waited for for good."""
    made = generate(tmp_path / "p", 120, "many")
    session = bench_gui._Watched(made.project.parent)
    session.open(made.project)
    monkeypatch.setattr(session, "poll", lambda: False)
    monkeypatch.setattr(bench_gui, "_BEGUN_SECONDS", 0.01)
    target = sorted((made.project.parent / "components").glob("*.ddd.json"))[0]
    with pytest.raises(RuntimeError) as raised:
        bench_gui._analysing(session, target, 0.0)
    assert str(raised.value) == f"{target} was moved forward, but no analysis began"


def test_a_rename_plan_that_raises_leaves_the_project_as_it_was(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The edit before it is undone all the same: a request raising is not a refusal, and ends
    the run with what it raised."""
    made = generate(tmp_path / "p", 120, "many")
    before = {path: path.read_bytes() for path in sorted((tmp_path / "p").rglob("*.json"))}
    original = Api.handle

    def raising(self, method, path, query, body):
        if path == "/api/unit-plan":
            raise OSError("a failure made up for the test")
        return original(self, method, path, query, body)

    monkeypatch.setattr(Api, "handle", raising)
    with pytest.raises(OSError, match=r"^a failure made up for the test$"):
        measure(made.project)
    assert {path: path.read_bytes() for path in sorted((tmp_path / "p").rglob("*.json"))} == before


def test_a_refused_plan_under_load_ends_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A refusal is no plan, as for the rename: its time would read as one."""
    made = generate(tmp_path / "p", 120, "many")
    before = {path: path.read_bytes() for path in sorted((tmp_path / "p").rglob("*.json"))}
    original = Api.handle
    refusal = {"error": "unreadable", "message": "a refusal made up for the test"}

    def refusing(self, method, path, query, body):
        if path == "/api/settle":
            return Reply(409, refusal)
        return original(self, method, path, query, body)

    monkeypatch.setattr(Api, "handle", refusing)
    with pytest.raises(RuntimeError) as raised:
        measure(made.project)
    assert str(raised.value) == f"the benchmark's own plan was refused: {refusal}"
    assert {path: path.read_bytes() for path in sorted((tmp_path / "p").rglob("*.json"))} == before


def test_a_refused_edit_ends_the_run_with_nothing_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Refused while an analysis runs, as the first one could be idle: no edit, so nothing to
    undo, and its time would read as an edit's."""
    made = generate(tmp_path / "p", 120, "many")
    before = {path: path.read_bytes() for path in sorted((tmp_path / "p").rglob("*.json"))}
    original = Api.handle
    refusal = {"error": "stale", "message": "a refusal made up for the test"}
    edits: list[bytes | None] = []

    def refusing(self, method, path, query, body):
        if path == "/api/edit":
            edits.append(body)
            if len(edits) == 2:
                return Reply(409, refusal)
        return original(self, method, path, query, body)

    monkeypatch.setattr(Api, "handle", refusing)
    with pytest.raises(RuntimeError) as raised:
        measure(made.project)
    assert str(raised.value) == f"the benchmark's own edit was refused: {refusal}"
    assert len(edits) == 2
    assert {path: path.read_bytes() for path in sorted((tmp_path / "p").rglob("*.json"))} == before


class _HeldUnderLoad(bench_gui._Watched, _Gate):
    """The benchmark's own session, each analysis a measure under load is asked beside held at a
    gate past the moment it says it has begun: the gate stands open for opening's analysis, is
    closed as :func:`bench_gui._analysing` is called (:func:`held_under_load`'s wrapper), and is
    opened again as the session is next asked to settle - so that, unless a test opens it
    sooner, every such analysis is still running when its measure's answer comes back."""

    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.gate = threading.Event()
        self.gate.set()
        self.entered = 0

    def settled(self, timeout: float | None) -> Revision | None:
        self.gate.set()
        return super().settled(timeout)


UNDER_LOAD = ("state while analysing", "plan while analysing", "edit while analysing")


def held_under_load(monkeypatch: pytest.MonkeyPatch, late: str | None) -> None:
    """``measure`` made over :class:`_HeldUnderLoad`: each measure under load answered while its
    analysis is held, but for the one named ``late``, whose request lets its analysis go and
    waits for it to land before it is answered."""
    sessions: list[_HeldUnderLoad] = []

    class Held(_HeldUnderLoad):
        def __init__(self, root: Path) -> None:
            super().__init__(root)
            sessions.append(self)

    armed: list[str] = []
    order = iter(UNDER_LOAD)
    analysing = bench_gui._analysing

    def closing(session: _HeldUnderLoad, target: Path, into: float) -> None:
        session.gate.clear()
        analysing(session, target, into)
        armed.append(next(order))

    original = Api.handle

    def handling(self, method, path, query, body):
        if armed and armed.pop() == late:
            sessions[0].gate.set()
            landed(sessions[0])
        return original(self, method, path, query, body)

    monkeypatch.setattr(bench_gui, "_Watched", Held)
    monkeypatch.setattr(bench_gui, "_analysing", closing)
    monkeypatch.setattr(Api, "handle", handling)


def test_a_measure_under_load_answered_while_its_analysis_runs_is_a_figure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each answered with its analysis held at the gate, so still running: none refused."""
    made = generate(tmp_path / "p", 120, "many")
    held_under_load(monkeypatch, None)
    taken = {each.name: each for each in measure(made.project)}
    assert [taken[name].refused for name in UNDER_LOAD] == [None, None, None]


@pytest.mark.parametrize("late", UNDER_LOAD)
def test_a_measure_under_load_answered_once_its_analysis_had_ended_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, late: str
) -> None:
    """Ruling F3: asked halfway through by the clock, a measure can still come back once its
    analysis has landed, and its time would read as one taken while an analysis ran. Refused
    with the sentence saying so, the other two kept, and the project left as it was found - the
    edit's own refusal included, undone like the edit it is."""
    made = generate(tmp_path / "p", 120, "many")
    before = {path: path.read_bytes() for path in sorted((tmp_path / "p").rglob("*.json"))}
    held_under_load(monkeypatch, late)
    taken = {each.name: each for each in measure(made.project)}
    assert {name: taken[name].refused for name in UNDER_LOAD} == {
        name: (
            "answered once its analysis had ended, so no figure of a request answered while "
            "one runs"
            if name == late
            else None
        )
        for name in UNDER_LOAD
    }
    assert {path: path.read_bytes() for path in sorted((tmp_path / "p").rglob("*.json"))} == before


def test_the_command_line_writes_a_refused_figure_as_its_sentence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """In the figure's place, in the table and in the json alike: never its time."""
    made = generate(tmp_path / "p", 120, "many")
    held_under_load(monkeypatch, "plan while analysing")
    written = tmp_path / "rows.json"
    assert main([str(made.project), "--json", str(written)]) == 0
    sentence = (
        "answered once its analysis had ended, so no figure of a request answered while one runs"
    )
    lines = capsys.readouterr().out.splitlines()
    assert [line for line in lines if "| plan while analysing |" in line] == [
        f"| p | plan while analysing | {sentence} | |"
    ]
    rows = json.loads(written.read_text(encoding="utf-8"))
    assert [row for row in rows if row["measure"] == "plan while analysing"] == [
        {
            "project": "p",
            "measure": "plan while analysing",
            "ms": None,
            "bytes": None,
            "refused": sentence,
        }
    ]
    assert all(
        row["refused"] is None and isinstance(row["ms"], int)
        for row in rows
        if row["measure"] != "plan while analysing"
    )


def test_each_measure_under_load_is_asked_halfway_through_its_analysis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each waited for once its analysis has begun for half of what the run's own ``analysis``
    took: asked at the analysis's first moment, at 100,000 declarations the analysis was still
    reading files and the poller's next round had not begun, which is not where a reader's
    requests meet it. The wait is the clock's (``time.sleep``), nothing the session locks."""
    made = generate(tmp_path / "p", 120, "many")
    waited: list[float] = []
    real = bench_gui.time.sleep
    monkeypatch.setattr(bench_gui.time, "sleep", lambda seconds: waited.append(seconds) or real(0))
    taken = {each.name: each for each in measure(made.project)}
    assert waited == [taken["analysis"].milliseconds / 2_000] * 3
