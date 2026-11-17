"""One ``compare_deliveries``, which ``ddd compare``, ``ddd check --baseline`` and the Compare tab
all call, and so one verdict on one pair.

Each caller used to run its own copy of "compare, then the plugins' hooks, then the verdict", and
the copies disagreed: the tab did not count the project's own errors, and said "can replace" of a
candidate both commands exit 1 on. These tests put the three on one pair and hold them to one
answer.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, ClassVar

import pytest

from conftest import component, declare, project, write_tree
from ddd.cli import EXIT_FINDINGS, EXIT_OK, main
from ddd.compare import renames
from ddd.deliveries import (
    Comparison,
    Reading,
    Refusal,
    compare_deliveries,
    read_baseline,
    read_dictionary,
    relaxations,
)
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


def _read_of(path: Path, *, relaxing: tuple[str, ...] = ()) -> tuple[Any, DiagnosticBag]:
    """What ``read_baseline`` makes of ``path`` for a run that was given ``-W``."""
    bag = DiagnosticBag(SeverityPolicy.from_strings(relaxing))
    return read_baseline(path, bag), bag


# A project that holds an input nobody produces, and an output nobody reads: the first is an
# error of its own analysis, the second a warning.
UNPRODUCED: dict[str, object] = {
    "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
    "a.ddd.json": component("A", declare("output", "Lonely", unit="rpm")),
    "b.ddd.json": component("B", declare("input", "Ghost", unit="rpm")),
}


class TestADumpFromAFailingProject:
    """``ddd dump`` exits 1 on a project with an input nobody produces and writes the file all
    the same; compared as a candidate it used to be a ``changed-owner`` warning and a verdict
    of "can replace"."""

    def _dumps(self, tmp_path: Path) -> tuple[Path, Path]:
        write_tree(tmp_path / "old", CLEAN)
        write_tree(tmp_path / "new", _without(CLEAN, "a.ddd.json"))
        write_tree(tmp_path / "new", {"a.ddd.json": component("A")})
        base, broken = tmp_path / "base.json", tmp_path / "broken.json"
        assert main(["dump", str(tmp_path / "old" / "p.ddd.json"), "-o", str(base)]) == EXIT_OK
        assert main(["dump", str(tmp_path / "new" / "p.ddd.json"), "-o", str(broken)]) == (
            EXIT_FINDINGS
        )
        return base, broken

    def test_ddd_compare_cannot_replace(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        base, broken = self._dumps(tmp_path)
        capsys.readouterr()
        assert main(["compare", str(base), str(broken)]) == EXIT_FINDINGS
        report = capsys.readouterr().err
        assert "error[missing-producer]: 'Speed' is read by B" in report
        assert "broken.json cannot replace base.json" in report

    def test_it_is_said_once_and_the_producer_that_left_is_not_told_beside_it(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        base, broken = self._dumps(tmp_path)
        capsys.readouterr()
        main(["compare", str(base), str(broken), "--format", "json"])
        found = [d["check"] for d in json.loads(capsys.readouterr().out)["diagnostics"]]
        assert found == ["missing-producer"]

    def test_two_dumps_that_fail_alike_hold_no_change(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _, broken = self._dumps(tmp_path)
        again = tmp_path / "again.json"
        assert main(["dump", str(tmp_path / "new" / "p.ddd.json"), "-o", str(again)]) == (
            EXIT_FINDINGS
        )
        capsys.readouterr()
        assert main(["compare", str(broken), str(again)]) == EXIT_OK

    def test_a_description_that_lost_the_producer_is_told_by_its_analysis_alone(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write_tree(tmp_path / "old", CLEAN)
        write_tree(tmp_path / "new", {**CLEAN, "a.ddd.json": component("A")})
        capsys.readouterr()
        argv = [str(tmp_path / "old" / "p.ddd.json"), str(tmp_path / "new" / "p.ddd.json")]
        assert main(["compare", *argv]) == EXIT_FINDINGS
        report = capsys.readouterr().err
        assert report.count("[missing-producer]") == 1
        assert "changed-owner" not in report

    def test_a_project_that_relaxes_the_check_has_chosen_to_hold_such_objects(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        base, broken = self._dumps(tmp_path)
        capsys.readouterr()
        assert main(["compare", str(base), str(broken), "-W", "missing-producer=ignore"]) == EXIT_OK
        assert "missing-producer" not in capsys.readouterr().err


def _versions(tmp_path: Path) -> tuple[Path, Path]:
    """One component, in two versions: the second reads one more input, which nobody in the file
    produces - what a supplier's next release of a component does."""
    write_tree(
        tmp_path,
        {
            "v1.ddd.json": component("C", declare("input", "Speed", unit="rpm")),
            "v2.ddd.json": component(
                "C", declare("input", "Speed", unit="rpm"), declare("input", "Torque", unit="Nm")
            ),
        },
    )
    return tmp_path / "v1.ddd.json", tmp_path / "v2.ddd.json"


class TestTwoVersionsOfAComponentWithInputs:
    """The release-to-release comparison of a component read alone, which is ``check --baseline
    --standalone``'s: what one file cannot know is not a fault of it."""

    def test_two_standalone_dumps_compare_clean_when_the_second_reads_one_more_input(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        one, two = _versions(tmp_path)
        first, second = tmp_path / "d1.json", tmp_path / "d2.json"
        assert main(["dump", str(one), "--standalone", "-o", str(first)]) == EXIT_OK
        assert main(["dump", str(two), "--standalone", "-o", str(second)]) == EXIT_OK
        capsys.readouterr()
        assert main(["compare", str(first), str(second)]) == EXIT_OK
        report = capsys.readouterr().err
        assert "missing-producer" not in report
        assert "d2.json can replace d1.json" in report

    def test_check_baseline_standalone_is_the_command_that_judges_the_two_files(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        one, two = _versions(tmp_path)
        assert main(["check", str(two), "--baseline", str(one), "--standalone"]) == EXIT_OK

    def test_compare_reads_a_component_candidate_as_a_projects_file_is_read(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Only the baseline is read under the floor: the candidate's own inputs are the
        candidate's own errors, which is why the supplier uses the command with the option."""
        one, two = _versions(tmp_path)
        assert main(["compare", str(one), str(two)]) == EXIT_FINDINGS
        assert "error[missing-producer]: 'Torque' is read by component 'C'" in (
            capsys.readouterr().err
        )


class TestABrokenBaselineWithholdsNothingOfTheCandidates:
    """The baseline's carried errors stop nothing: a description candidate is analysed, and all
    its findings and its renames are reported, as ``ddd check --baseline`` reports them."""

    def _trees(self, tmp_path: Path) -> tuple[Path, Path]:
        write_tree(
            tmp_path / "old",
            {
                "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component(
                    "A", declare("output", "Old", unit="rpm", id="aaaaaaaaaaaa")
                ),
                "b.ddd.json": component(
                    "B", declare("input", "Old", unit="rpm"), declare("input", "Ghost", unit="rpm")
                ),
            },
        )
        write_tree(
            tmp_path / "new",
            {
                "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    declare("output", "New", unit="rpm", id="aaaaaaaaaaaa"),
                    declare("output", "Lonely", unit="rpm"),
                ),
                "b.ddd.json": component("B", declare("input", "New", unit="rpm")),
            },
        )
        return tmp_path / "old" / "p.ddd.json", tmp_path / "new" / "p.ddd.json"

    def test_the_candidates_warnings_are_reported(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        old, new = self._trees(tmp_path)
        assert main(["compare", str(old), str(new)]) == EXIT_FINDINGS
        report = capsys.readouterr().err
        assert "in the baseline: 'Ghost' is read by component 'B'" in report
        assert "warning[unused-output]: 'Lonely'" in report
        assert "error[renamed-read-object]" in report

    def test_check_baseline_reports_the_same_findings_of_the_candidate(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        old, new = self._trees(tmp_path)
        main(["compare", str(old), str(new)])
        compared = capsys.readouterr().err
        main(["check", str(new), "--baseline", str(old)])
        checked = capsys.readouterr().err

        def findings(report: str) -> list[str]:
            return sorted(line for line in report.splitlines() if "[" in line and ": " in line)

        assert findings(compared) == findings(checked)

    def test_the_renames_are_written(self, tmp_path: Path) -> None:
        old, new = self._trees(tmp_path)
        written = tmp_path / "renames.json"
        assert main(["compare", str(old), str(new), "--renames", str(written)]) == EXIT_FINDINGS
        assert json.loads(written.read_text(encoding="utf-8")) == [
            {"id": "aaaaaaaaaaaa", "from": "Old", "to": "New"}
        ]

    def test_a_baseline_that_cannot_be_read_still_has_the_candidates_findings_reported(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Decision 5.2's other branch: nothing to compare, so no verdict - and the candidate,
        analysed all the same, says what it has of its own."""
        _, new = self._trees(tmp_path)
        assert main(["compare", str(tmp_path / "gone.json"), str(new)]) == EXIT_FINDINGS
        report = capsys.readouterr().err
        assert "error[file-not-found]: in the baseline:" in report
        assert "warning[unused-output]: 'Lonely'" in report
        assert "replace" not in report

    def test_a_candidate_that_is_itself_broken_still_stops_at_its_own_errors(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """What the baseline does not excuse: a candidate whose own files do not load is not
        analysed, as it was not before."""
        old, new = self._trees(tmp_path)
        (tmp_path / "new" / "a.ddd.json").write_text("{not json", encoding="utf-8")
        written = tmp_path / "renames.json"
        assert main(["compare", str(old), str(new), "--renames", str(written)]) == EXIT_FINDINGS
        assert not written.exists()
        assert "error[json-syntax]" in capsys.readouterr().err


class TestADescriptionBaselineTakesTheProjectsRelaxationsAlone:
    """A project that builds with ``-W missing-producer=ignore`` can compare its branch against
    its trunk: the relaxation reaches the baseline's own analysis. A promotion never does."""

    def _trees(self, tmp_path: Path) -> tuple[Path, Path]:
        write_tree(tmp_path / "old", UNPRODUCED)
        write_tree(tmp_path / "new", UNPRODUCED)
        return tmp_path / "old" / "p.ddd.json", tmp_path / "new" / "p.ddd.json"

    def test_without_the_relaxation_the_baselines_error_is_carried(self, tmp_path: Path) -> None:
        old, new = self._trees(tmp_path)
        assert main(["compare", str(old), str(new)]) == EXIT_FINDINGS

    @pytest.mark.parametrize("severity", ["ignore", "warning", "info"])
    def test_ddd_compare_under_the_projects_w_has_a_verdict(
        self, tmp_path: Path, severity: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        old, new = self._trees(tmp_path)
        argv = ["compare", str(old), str(new), "-W", f"missing-producer={severity}"]
        assert main(argv) == EXIT_OK
        report = capsys.readouterr().err
        assert "in the baseline" not in report
        assert " can replace " in report and "cannot replace" not in report

    def test_ddd_check_baseline_takes_it_too(self, tmp_path: Path) -> None:
        old, new = self._trees(tmp_path)
        argv = ["check", str(new), "--baseline", str(old), "-W", "missing-producer=ignore"]
        assert main(argv) == EXIT_OK

    def test_a_promotion_does_not_reach_the_baseline(self, tmp_path: Path) -> None:
        """What ``-W unused-output=error`` says about this run's own outputs: the baseline's
        unread output is its own, as it always was, and the run's strictness is no more its."""
        write_tree(
            tmp_path / "old",
            {
                **CLEAN,
                "a.ddd.json": component(
                    "A",
                    declare("output", "Speed", unit="rpm"),
                    declare("output", "Lonely", unit="rpm"),
                ),
            },
        )
        write_tree(tmp_path / "new", CLEAN)
        old, new = tmp_path / "old" / "p.ddd.json", tmp_path / "new" / "p.ddd.json"
        assert main(["compare", str(old), str(new), "-W", "unused-output=error"]) == EXIT_OK

    def test_an_override_equal_to_the_checks_grade_is_not_a_relaxation_and_the_floor_stands(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``-W missing-producer=error`` states what the check already is: it must not take the
        last word over the floor a component baseline is read under."""
        write_tree(
            tmp_path,
            {**CLEAN, "baseline.ddd.json": component("B", declare("input", "Speed", unit="rpm"))},
        )
        argv = [
            "compare",
            str(tmp_path / "baseline.ddd.json"),
            str(tmp_path / "p.ddd.json"),
            "-W",
            "missing-producer=error",
        ]
        assert main(argv) == EXIT_OK
        assert "in the baseline" not in capsys.readouterr().err

    def test_the_relaxations_of_a_policy_are_the_overrides_below_the_checks_own_grade(self) -> None:
        policy = SeverityPolicy.from_strings(
            [
                "missing-producer=ignore",
                "unused-output=error",
                "definition-mismatch=warning",
                "missing-id=warning",
                "demo/rule=ignore",
                "demo/mild=warning",
                "demo/other=error",
            ],
            strict=True,
        )
        assert relaxations(policy) == {
            "missing-producer": Severity.IGNORE,
            "definition-mismatch": Severity.WARNING,
            "demo/rule": Severity.IGNORE,
        }

    def test_what_is_read_is_the_same_whichever_way_it_is_asked(self, tmp_path: Path) -> None:
        write_tree(tmp_path, UNPRODUCED)
        resolved, bag = _read_of(tmp_path / "p.ddd.json", relaxing=("missing-producer=ignore",))
        assert resolved is not None and len(bag) == 0


class TestAJsonHoldingOnlyANameIsNoDelivery:
    """A lone ``name`` used to validate as an empty dictionary, the stamp of the format being a
    field with a default: every object of the other side was an addition, or a removal. A file
    that is neither a dump nor a description is refused, on either side."""

    def _almost(self, tmp_path: Path) -> Path:
        write_tree(tmp_path, {**CLEAN, "almost.json": {"name": "P"}})
        return tmp_path / "almost.json"

    def test_as_a_baseline_it_is_refused(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        almost = self._almost(tmp_path)
        assert main(["compare", str(almost), str(tmp_path / "p.ddd.json")]) == EXIT_FINDINGS
        report = capsys.readouterr().err
        assert "neither a dumped dictionary nor a project or component description" in report
        assert "can replace" not in report

    def test_as_a_candidate_it_is_refused(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        almost = self._almost(tmp_path)
        assert main(["compare", str(tmp_path / "p.ddd.json"), str(almost)]) == EXIT_FINDINGS
        report = capsys.readouterr().err
        assert "neither a dumped dictionary nor a project or component description" in report
        assert "can replace" not in report

    def test_the_reader_says_which_refusal_it_is(self, tmp_path: Path) -> None:
        almost = self._almost(tmp_path)
        reading = Reading()
        assert read_dictionary(almost, DiagnosticBag(), reading) is None
        assert reading.refusal is Refusal.NEITHER

    def test_a_dump_with_no_objects_still_reads(self, tmp_path: Path) -> None:
        write_tree(tmp_path, {"p.ddd.json": project("Empty")})
        dump = tmp_path / "empty.json"
        assert main(["dump", str(tmp_path / "p.ddd.json"), "-o", str(dump)]) == EXIT_OK
        assert json.loads(dump.read_text(encoding="utf-8"))["format"] >= 4
        bag = DiagnosticBag()
        resolved = read_dictionary(dump, bag)
        assert resolved is not None and len(bag) == 0
