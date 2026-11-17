"""One ``compare_deliveries``, which ``ddd compare``, ``ddd check --baseline`` and the Compare tab
all call, and so one verdict on one pair.

Each caller used to run its own copy of "compare, then the plugins' hooks, then the verdict", and
the copies disagreed: the tab did not count the project's own errors, and said "can replace" of a
candidate both commands exit 1 on. These tests put the three on one pair and hold them to one
answer.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, ClassVar

import pytest

from conftest import component, declare, project, write_tree
from ddd.cli import EXIT_FINDINGS, EXIT_OK, main
from ddd.compare import renames
from ddd.deliveries import Comparison, compare_deliveries, read_dictionary
from ddd.diagnostics import DiagnosticBag, Location, Severity, SeverityPolicy
from ddd.gui.api import Api
from ddd.gui.session import Session
from ddd.plugins import CompareContext, Plugin, PluginError
from test_gui_api import Reply, get, posix

CLEAN: dict[str, object] = {
    "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
    "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
    "b.ddd.json": component("B", declare("input", "Speed", unit="rpm")),
}
"""A project with nothing to report: the baseline every case below is compared against, and the
candidate each of them changes in one place."""


def _without(files: dict[str, object], *names: str) -> dict[str, object]:
    return {key: value for key, value in files.items() if key not in names}


# What a candidate can have wrong of its own while the comparison finds nothing at all: the
# delivery's interface is what the baseline's was, and the project still has errors.
OWN_ERRORS: dict[str, dict[str, object]] = {
    "a reader that disagrees with its producer": {
        "b.ddd.json": component("B", declare("input", "Speed", unit="km/h"))
    },
    "a reader of nothing": {
        "b.ddd.json": component(
            "B", declare("input", "Speed", unit="rpm"), declare("input", "Ghost")
        )
    },
    "a short init": {
        "a.ddd.json": component(
            "A",
            declare("output", "Speed", unit="rpm"),
            declare("local", "T", dimensions=[3], init=[1, 2]),
        )
    },
}
"""``definition-mismatch``, ``missing-producer`` and ``init-invalid``: the three the review's
trigger names, none of which ``compare`` reports."""


def _baseline(tmp_path: Path) -> Path:
    """A dump of :data:`CLEAN` of another tree than the candidate's, kept under the root the tab
    names baselines in."""
    write_tree(tmp_path / "old", CLEAN)
    dump = tmp_path / "new" / "baseline.dictionary.json"
    assert main(["dump", str(tmp_path / "old" / "p.ddd.json"), "-o", str(dump)]) == EXIT_OK
    return dump


def _candidate(tmp_path: Path, change: dict[str, object]) -> Api:
    root = tmp_path / "new"
    write_tree(root, {**CLEAN, **change})
    session = Session(root)
    session.open(root / "p.ddd.json")
    return Api(session, root / "p.ddd.json", wait_seconds=0.05)


def _the_three(tmp_path: Path, baseline: Path, api: Api) -> tuple[int, int, Reply]:
    """What ``ddd compare``, ``ddd check --baseline`` and ``GET /api/compare`` say of one pair."""
    candidate = api.session.root / "p.ddd.json"
    return (
        main(["compare", str(baseline), str(candidate)]),
        main(["check", str(candidate), "--baseline", str(baseline)]),
        get(api, "/api/compare", baseline=baseline.as_posix()),
    )


class TestTheCandidatesOwnErrors:
    @pytest.mark.parametrize("case", sorted(OWN_ERRORS))
    def test_a_candidate_with_an_error_of_its_own_cannot_replace_on_any_of_the_three(
        self, tmp_path: Path, case: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        baseline = _baseline(tmp_path)
        api = _candidate(tmp_path, OWN_ERRORS[case])
        compared, checked, reply = _the_three(tmp_path, baseline, api)
        assert compared == EXIT_FINDINGS
        assert checked == EXIT_FINDINGS
        assert reply.status == 200
        assert reply.body["verdict"] is False
        # No error of the comparison itself: what is wrong is the project's own, and the
        # reply says how much of it there is rather than leaving the page to guess.
        assert [f for f in reply.body["findings"] if f["severity"] == "error"] == []
        revision = api.session.revision
        assert revision is not None
        own = sum(1 for filed in revision.findings if filed.diagnostic.severity is Severity.ERROR)
        assert own >= 1
        assert reply.body["own_errors"] == own

    def test_a_clean_candidate_is_told_it_has_none_of_its_own(self, tmp_path: Path) -> None:
        baseline = _baseline(tmp_path)
        api = _candidate(tmp_path, {})
        reply = get(api, "/api/compare", baseline=baseline.as_posix())
        assert reply.body["verdict"] is True
        assert reply.body["own_errors"] == 0

    def test_two_builds_that_disagree_give_the_verdict_the_state_counts(
        self, tmp_path: Path
    ) -> None:
        """One build relaxing ``definition-mismatch`` and one not: the revision holds the error
        of the build that does not, which is what the state counts, and ``ddd check --baseline``
        under that build's own ``-W`` exits 1. The tab answered ``true`` from the first build's
        policy alone."""
        from conftest import build_record

        baseline = _baseline(tmp_path)
        root = tmp_path / "new"
        write_tree(root, {**CLEAN, **OWN_ERRORS["a reader that disagrees with its producer"]})
        build_record(
            root, root / "p.ddd.json", image="aaa", severity=["definition-mismatch=warning"]
        )
        build_record(root, root / "p.ddd.json", image="zzz")
        session = Session(root)
        session.open(root / "p.ddd.json")
        api = Api(session, root / "p.ddd.json", wait_seconds=0.05)
        reply = get(api, "/api/compare", baseline=baseline.as_posix())
        assert reply.body["verdict"] is False
        assert reply.body["own_errors"] >= 1
        strict = main(["check", str(root / "p.ddd.json"), "--baseline", str(baseline)])
        relaxed = main(
            [
                "check",
                str(root / "p.ddd.json"),
                "--baseline",
                str(baseline),
                "-W",
                "definition-mismatch=warning",
            ]
        )
        assert (strict, relaxed) == (EXIT_FINDINGS, EXIT_OK)


class TestOneVerdictOnOnePair:
    @pytest.mark.parametrize(
        "change",
        [
            {},
            {"a.ddd.json": component("A", declare("output", "Speed", "uint16", unit="rpm"))},
            {"a.ddd.json": component("A", declare("output", "Other", unit="rpm"))},
            *OWN_ERRORS.values(),
        ],
        ids=["identical", "a changed datatype", "a removed object", *sorted(OWN_ERRORS)],
    )
    def test_the_three_callers_agree(self, tmp_path: Path, change: dict[str, object]) -> None:
        baseline = _baseline(tmp_path)
        api = _candidate(tmp_path, change)
        compared, checked, reply = _the_three(tmp_path, baseline, api)
        assert reply.status == 200
        assert compared == checked
        assert (compared == EXIT_OK) is reply.body["verdict"]


class TestAComponentBaselineReadAlone:
    """A baseline that is one component file is read alone, for every caller: with the floor
    ``check --standalone`` reads one with, so that an input nobody was shown the producer of
    is not an error of the baseline."""

    def _tree(self, tmp_path: Path) -> Path:
        write_tree(
            tmp_path,
            {
                **CLEAN,
                "baseline.ddd.json": component("B", declare("input", "Speed", unit="rpm")),
            },
        )
        return tmp_path / "baseline.ddd.json"

    def test_ddd_compare_reads_it_with_the_floor(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        baseline = self._tree(tmp_path)
        assert main(["compare", str(baseline), str(tmp_path / "p.ddd.json")]) == EXIT_OK
        assert "in the baseline" not in capsys.readouterr().err

    def test_check_baseline_reads_it_with_the_floor_without_being_told_so(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        baseline = self._tree(tmp_path)
        assert main(["check", str(tmp_path / "p.ddd.json"), "--baseline", str(baseline)]) == EXIT_OK
        assert "in the baseline" not in capsys.readouterr().err

    def test_the_tab_reads_it_with_the_floor(self, tmp_path: Path) -> None:
        baseline = self._tree(tmp_path)
        session = Session(tmp_path)
        session.open(tmp_path / "p.ddd.json")
        api = Api(session, tmp_path / "p.ddd.json", wait_seconds=0.05)
        reply = get(api, "/api/compare", baseline=baseline.as_posix())
        assert reply.status == 200
        assert reply.body["baseline_findings"] == []
        assert reply.body["verdict"] is True

    def test_the_tab_grades_a_gone_output_as_the_commands_do(self, tmp_path: Path) -> None:
        """Read alone, an output the component stopped offering is ``removed-object`` and not
        a claim that no component read it; the candidate here has dropped ``Speed``."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "b.ddd.json"),
                "b.ddd.json": component("B", declare("input", "Other", unit="rpm")),
                "baseline.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
            },
        )
        session = Session(tmp_path)
        session.open(tmp_path / "p.ddd.json")
        api = Api(session, tmp_path / "p.ddd.json", wait_seconds=0.05)
        reply = get(api, "/api/compare", baseline=posix(tmp_path, "baseline.ddd.json"))
        removed = [f for f in reply.body["findings"] if f["check"] == "removed-object"]
        assert len(removed) == 1
        assert "no component read it" not in removed[0]["message"]


class TestCompareDeliveries:
    def _sides(self, tmp_path: Path) -> tuple[Any, Any]:
        write_tree(tmp_path, CLEAN)
        bag = DiagnosticBag()
        resolved = read_dictionary(tmp_path / "p.ddd.json", bag)
        assert resolved is not None
        return resolved, resolved

    def test_it_is_compare_and_then_the_hooks(self, tmp_path: Path) -> None:
        baseline, candidate = self._sides(tmp_path)
        bag = DiagnosticBag()
        found = compare_deliveries(
            baseline, candidate, bag, location=Location(tmp_path / "p.ddd.json")
        )
        assert isinstance(found, Comparison)
        assert found.verdict is True
        assert len(bag) == 0

    def test_the_verdict_counts_the_errors_the_bag_already_held(self, tmp_path: Path) -> None:
        baseline, candidate = self._sides(tmp_path)
        bag = DiagnosticBag()
        bag.add("definition-mismatch", "the project's own", Location(tmp_path / "p.ddd.json"))
        found = compare_deliveries(
            baseline, candidate, bag, location=Location(tmp_path / "p.ddd.json")
        )
        assert found.verdict is False

    def test_the_verdict_counts_errors_held_outside_the_bag(self, tmp_path: Path) -> None:
        baseline, candidate = self._sides(tmp_path)
        found = compare_deliveries(
            baseline,
            candidate,
            DiagnosticBag(),
            location=Location(tmp_path / "p.ddd.json"),
            held_elsewhere=1,
        )
        assert found.verdict is False

    def test_a_plugin_that_raises_is_raised_unless_the_caller_takes_it(
        self, tmp_path: Path
    ) -> None:
        baseline, candidate = self._sides(tmp_path)

        def broken(context: CompareContext) -> None:
            raise RuntimeError("this hook is broken")

        plugins = (Plugin(name="demo", compare=broken),)
        location = Location(tmp_path / "p.ddd.json")
        with pytest.raises(PluginError):
            compare_deliveries(
                baseline, candidate, DiagnosticBag(), location=location, plugins=plugins
            )
        taken: list[PluginError] = []
        found = compare_deliveries(
            baseline,
            candidate,
            DiagnosticBag(),
            location=location,
            plugins=plugins,
            on_plugin_error=taken.append,
        )
        assert len(taken) == 1
        # The hook did not finish, so there is no verdict a reader may rely on: the caller that
        # took the error files it, and the verdict says so by refusing.
        assert found.verdict is False

    def test_the_pairing_is_handed_back_for_the_renames(self, tmp_path: Path) -> None:
        baseline, candidate = self._sides(tmp_path)
        found = compare_deliveries(
            baseline, candidate, DiagnosticBag(), location=Location(tmp_path / "p.ddd.json")
        )
        assert renames(found.paired) == []


class TestTheBaselinesOwnErrors:
    """A baseline whose own components disagree carries its errors into every caller's verdict,
    and the floor of a component read alone is for a component file only."""

    BROKEN: ClassVar[dict[str, object]] = {
        "p.ddd.json": project("P", "b.ddd.json"),
        "b.ddd.json": component("B", declare("input", "Speed", unit="rpm")),
    }

    def test_every_caller_refuses_a_clean_candidate_against_a_broken_baseline(
        self, tmp_path: Path
    ) -> None:
        write_tree(tmp_path / "old", self.BROKEN)
        api = _candidate(tmp_path, {})
        baseline = tmp_path / "old" / "p.ddd.json"
        candidate = api.session.root / "p.ddd.json"
        # The baseline is a description, so the commands do not attempt the comparison at all
        # and exit 1 on its errors; the tab reports them beside it and refuses.
        assert main(["compare", str(baseline), str(candidate)]) == EXIT_FINDINGS
        assert main(["check", str(candidate), "--baseline", str(baseline)]) == EXIT_FINDINGS
        shutil.copytree(tmp_path / "old", api.session.root / "old")
        reply = get(api, "/api/compare", baseline=posix(api.session.root, "old/p.ddd.json"))
        assert reply.body["verdict"] is False
        assert reply.body["own_errors"] == 0
        assert reply.body["baseline_findings"] != []

    def test_a_project_baseline_keeps_the_errors_the_floor_would_silence_of_a_component(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write_tree(tmp_path, {**self.BROKEN, **{"q.ddd.json": CLEAN["p.ddd.json"]}})
        write_tree(tmp_path, {key: value for key, value in CLEAN.items() if key != "p.ddd.json"})
        assert main(["compare", str(tmp_path / "p.ddd.json"), str(tmp_path / "q.ddd.json")]) == (
            EXIT_FINDINGS
        )
        assert "in the baseline: 'Speed' is read by component 'B'" in capsys.readouterr().err

    def test_an_override_of_the_bag_keeps_the_last_word_over_the_floor(
        self, tmp_path: Path
    ) -> None:
        write_tree(tmp_path, {"c.ddd.json": component("B", declare("input", "Speed"))})
        bag = DiagnosticBag(SeverityPolicy.from_strings(["missing-producer=error"]))
        assert read_dictionary(tmp_path / "c.ddd.json", bag, floor_when_alone=True) is not None
        assert [d.check for d in bag] == ["missing-producer"]
        silent = DiagnosticBag()
        read_dictionary(tmp_path / "c.ddd.json", silent, floor_when_alone=True)
        assert len(silent) == 0

    def test_the_strictness_of_the_bag_survives_the_floor(self, tmp_path: Path) -> None:
        wide = declare("output", "X", limits={"min": 0, "max": 300})
        write_tree(tmp_path, {"c.ddd.json": component("B", wide)})
        relaxed = DiagnosticBag()
        read_dictionary(tmp_path / "c.ddd.json", relaxed, floor_when_alone=True)
        strict = DiagnosticBag(SeverityPolicy.from_strings([], strict=True))
        read_dictionary(tmp_path / "c.ddd.json", strict, floor_when_alone=True)
        assert sorted(d.check for d in relaxed) == ["limits-out-of-range", "missing-id"]
        assert strict.has_errors and not relaxed.has_errors
