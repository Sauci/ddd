"""Reading a side of a comparison: a delivery as it was handed over.

``ddd compare`` and ``ddd check --baseline`` take a baseline and a candidate, each of which is
either a dictionary somebody archived or a project description that has to be analysed to become
one. ``ddd gui`` compares the open project against a baseline the reader names, and needs the
same reading of what a baseline is - so it lives here rather than in the command, where the page
would have had to copy it.

What makes the copy dangerous is not the reading but the policy around it: a baseline is analysed
in a bag of its own, without ``--strict`` however strict the run asking is, and only its errors
are carried over, with what the run did not run of it. :func:`read_baseline` says why at length.
A second implementation would have
drifted from that the first time either side changed.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from ddd.diagnostics import (
    CHECKS,
    STANDALONE_POLICY,
    DiagnosticBag,
    Location,
    Severity,
    SeverityPolicy,
    where,
)

if TYPE_CHECKING:
    from pydantic import BaseModel

    from ddd.compare import Pairing
    from ddd.ir import DataDictionary
    from ddd.plugins import Plugin, PluginError

BASELINE_PREFIX: Final = "in the baseline: "
"""What marks an error carried over from the baseline's own analysis, so that it reads as the
predecessor's rather than as this run's. Named here rather than spelled twice: a caller putting
one of these into a sentence that has already said which delivery it is about
(:mod:`ddd.gui.compare`'s refusal banner) has to take it off again, and matching a prefix nobody
owns is how that sort of thing goes wrong."""


class Refusal(StrEnum):
    """Why a reader came back with nothing, as the reader itself knows it: which of the two
    readers the file reached, and how far it got.

    What a caller has to have in order to tell a person why the file they named is not a
    delivery. Re-derived instead - by classifying one diagnostic out of a bag the caller did not
    fill - a description whose ``includes`` names a file that is not there was called "neither a
    dictionary nor a description", which reads as *you named the wrong file* and is answered by
    replacing one whose only fault is the missing include.
    """

    NOT_JSON = "not-json"
    """The file holds no json object at all, or none this tool will read - a duplicate key, a
    ``NaN``, bytes that are not utf-8.

    A file whose bytes could not be read at all comes back as this too:
    :func:`~ddd.loading.read_json_document` answers ``None`` for both "without saying a word
    about why not", and it is the *reader* the caller is asking, not the filesystem. A caller
    that has to tell those two apart settles it before asking, by opening the file itself -
    which is what :mod:`ddd.gui.compare` does to answer *unreadable*.
    """

    DESCRIPTION = "description"
    """A project or component description that did not become a dictionary: a file it includes
    that is not there, a name that does not validate, a plugin that refused, an analysis that
    reported an error. It is the right kind of file, and it is broken."""

    DICTIONARY = "dictionary"
    """A dumped dictionary this DDD could not read: one from a newer DDD, or one whose fields do
    not match the contract. Also the right kind of file - :func:`holds_a_dictionary` says how
    that is known before anything is validated."""

    NEITHER = "neither"
    """Valid json and neither of the two: no ``project``, no ``component``, no ``format``. The
    one refusal that really does mean the reader named the wrong file."""


@dataclass(slots=True)
class Reading:
    """What one read of a delivery turned out to be, beside the findings it reported.

    Filled in as the read goes, the way ``bag`` is, and for the same reason: the reader is the
    only thing that knows, and a caller working it out afterwards is guessing. A caller with
    nothing to say about a refusal passes none and pays nothing.
    """

    refusal: Refusal | None = None
    """Why nothing came back, or ``None`` while nothing has been refused."""


@dataclass(frozen=True, slots=True)
class Resolved:
    """A dictionary and what a plugin's hook needs beside it.

    A description resolved on the spot keeps its plugins and the settings it states, and can
    point a finding at a declaration; an archived dump has neither plugins nor declarations,
    so its plugins come from ``--plugin``, a finding points at the file, and its settings are
    read back from the blocks it carries.
    """

    dictionary: DataDictionary
    plugins: tuple[Plugin, ...]
    locate: Callable[[str], Location | None]
    from_description: bool
    sources: tuple[Path, ...]
    """Every file this side was read out of, resolved: a project and its whole include tree,
    or the single file an archived dump was read from.

    What a caller has to know before it writes anything - ``ddd compare --renames`` and
    ``ddd dump -o`` refuse a path naming one of these rather than writing over a file the
    delivery was read from - and before it trusts anything it kept: this is the set whose
    staleness makes a reading of this side stale, which is how :mod:`ddd.gui.compare` decides
    a cached baseline has to be read again."""

    settings: Callable[[Plugin], BaseModel | None]
    """The settings a hook of this side is handed for a plugin: for a description, a shallow
    copy of the instance its project block was validated into while the files were read
    (:meth:`~ddd.loading.Workspace.settings`), the one its dictionary's dump of the settings
    was written from; for an archived dump, the block it carries validated against the
    plugin's project model (:func:`~ddd.plugins.settings_of`), which is all there is of it.

    Never the dictionary's dump of a block a description states, read back: a model reads its
    dump back only as far as the dump keeps what it read - a field it excludes, a validator
    that does not hand back what it is given, a strict field the dump writes as a string - and
    a default drawn afresh would be drawn again."""

    alone: bool = False
    """Whether this side is one component file, read without a project around it.

    What a dictionary cannot say of itself, and what ``compare`` has to be told: the readers it
    records for an object are the component's own and nobody else's, because the run was not
    shown the rest. A project description is whole. An archived dump is graded as whole too,
    though a ``dump --standalone`` of a component is partial: it carries no mark saying so, the
    mark is a change of the format, and a dump is compared as it always was."""


def read_dictionary(
    path: Path,
    bag: DiagnosticBag,
    reading: Reading | None = None,
    *,
    floor_when_alone: bool = False,
    run_plugins: bool = True,
) -> Resolved | None:
    """A dumped dictionary, or a project/component description resolved into one.

    Accepting both is what makes the command usable in a pipeline: the baseline is normally
    an archived dump, while the candidate is the project sitting in the working tree.

    ``reading`` is where this says *why* it answers ``None``, for a caller that has to put that
    in words - which of the two readers met the file, and how far it got. A caller with nothing
    to say about a refusal leaves it out.

    ``floor_when_alone`` has a file that is one component, read without a project around it,
    read under the floor ``ddd check --standalone`` reads one under
    (:data:`~ddd.diagnostics.STANDALONE_POLICY`), whether or not the run said so: what the
    component was never shown is not a fault of the component. Taken before anything is loaded,
    since the loader reports some of what the floor silences, and set on ``bag`` itself: its
    policy is replaced by the floor under the overrides it held, and stays so after the read,
    so a caller hands it a bag of its own, as :func:`read_baseline` does.

    ``run_plugins`` false reads a description as ``--no-plugins`` asks, importing no plugin it
    names (:func:`~ddd.loading.load_workspace`); a dumped dictionary runs none either way.
    """
    from ddd.analysis import analyze
    from ddd.loading import load_dictionary, load_workspace, read_json_document
    from ddd.plugins import settings_of

    account = Reading() if reading is None else reading
    document = read_json_document(path)
    if holds_a_description(document):
        if floor_when_alone and _is_a_component(document):
            bag.policy = _with_the_floor(bag.policy)
        # What this file reported, not what the bag held when it came: a baseline's carried
        # errors share the bag of the run, and a candidate that was refused for them was never
        # analysed, so its own findings and its renames were withheld from a run that reports
        # a candidate's everything.
        held = bag.count(Severity.ERROR)
        workspace = load_workspace(path, bag, run_plugins=run_plugins)
        if workspace is None or bag.count(Severity.ERROR) > held:
            account.refusal = Refusal.DESCRIPTION
            return None
        return Resolved(
            analyze(workspace, bag),
            workspace.plugins,
            workspace.locate,
            True,
            workspace.sources(),
            workspace.settings,
            alone=not workspace.projects,
        )
    if document is not None and not holds_a_dictionary(document):
        # Neither: ``format`` has a default, so a file stating only a name validates as an empty
        # dictionary - every object of the other side an addition, or a removal - and is a
        # delivery of nothing. Said here, once, for every caller.
        bag.add(
            "schema",
            "the file is neither a dumped dictionary nor a project or component description: it "
            "states no `format`, no `project` and no `component`",
            where(path),
        )
        account.refusal = Refusal.NEITHER
        return None
    # Handed the document this already read rather than leaving the reader to read it again:
    # a dumped dictionary is the file a build archives whole, and the 45 MB one of a thousand
    # object project costs about a third of a second per pass, twice over in a comparison.
    dictionary = load_dictionary(path, bag, document)
    if dictionary is None:
        account.refusal = _unread(document)
        return None
    archived = where(path)
    return Resolved(
        dictionary,
        (),
        lambda _: archived,
        False,
        (archived.path,),
        lambda plugin: settings_of(plugin, dictionary.extensions),
    )


def _is_a_component(document: dict[str, Any] | None) -> bool:
    """True for a file whose top level states a component: the one the loader reads alone. A file
    stating a project as well is refused, whichever floor it was read under."""
    return document is not None and "component" in document


def _with_the_floor(policy: SeverityPolicy) -> SeverityPolicy:
    """``policy`` under the floor of a component read alone, an explicit override of its own
    keeping the last word, as ``ddd check --standalone`` has it."""
    floor = SeverityPolicy.from_strings(STANDALONE_POLICY, strict=False, standalone=True)
    return SeverityPolicy({**floor.overrides, **policy.overrides}, policy.strict, True)


def _unread(document: dict[str, Any] | None) -> Refusal:
    """Which refusal a file the dump reader could not read is: the sniff again, now that the
    reader has had its say, and never a classification of what it happened to report. A file
    that is json and states no ``format`` never gets here: it is neither, and was refused
    before the reader was asked."""
    return Refusal.NOT_JSON if document is None else Refusal.DICTIONARY


def relaxations(policy: SeverityPolicy) -> dict[str, Severity]:
    """The overrides of ``policy`` that grade a check below the grade it has by default, and
    none of the rest: what a project says it can live with, as against what it asks of itself.

    A promotion - ``-W unused-output=error``, and ``--strict`` with it, which this leaves out
    altogether - is a run asking to be told about *its own* findings more loudly; a relaxation
    is the project's decision about a check, and one project has one decision. A check of a
    plugin has no grade here to compare with, since the plugin that registers it is not loaded
    yet, and what nothing grades lower than ``ignore`` is kept whichever it is.
    """
    return {
        check: severity
        for check, severity in policy.overrides.items()
        if severity is Severity.IGNORE
        or (check in CHECKS and severity.rank > CHECKS[check].default_severity.rank)
    }


def read_baseline(
    path: Path,
    bag: DiagnosticBag,
    standalone: bool = False,
    reading: Reading | None = None,
    *,
    run_plugins: bool = True,
) -> Resolved | None:
    """Resolve the baseline side of a comparison, in a bag of its own.

    A baseline given as a project description has to be analysed to become a dictionary, and
    that analysis produces findings about *that* delivery: files that are not part of the
    project under check, an output nobody read two releases ago. Reported here they would be
    attributed to this run, printed twice when both sides are the same tree, and would fail a
    clean project because of its predecessor. Its warnings are its own, however strict this
    run is, so the baseline is analysed without ``--strict``; only its errors are carried over,
    prefixed, so that a broken baseline is visible. A candidate given as a dump is still
    compared against whatever resolved, because a delivery that cannot be accepted still needs
    its differences listed; a candidate given as a description is analysed all the same, and a
    broken baseline withholds nothing of it - its findings and its renames are reported beside
    the carried errors, which count against the verdict and not against the candidate's reading
    (:func:`read_dictionary`).

    A promotion of ``-W`` does not reach it, for the same reason and against the same objection:
    the overrides used to be shared, so ``-W unused-output=error`` - a run asking to be told
    about *its own* unread outputs - promoted a warning about a predecessor into an error,
    carried it over as ``in the baseline:`` and refused a verdict about the delivery. A
    relaxation does (:func:`relaxations`): a project that decided it can live with a finding
    decided it of the delivery it compares against as much as of its own, and a project that
    relaxes ``missing-producer`` could not otherwise compare its branch against its trunk.
    ``standalone`` reaches it too, the floor a component read on its own sets: that is a
    statement about how the file was handed over, and the baseline was handed over the same way. A
    baseline that *is* one component file is read under that floor whether or not the run said
    so - ``ddd compare`` has no flag to say it with - so that one file is read one way by every
    caller: against the floor, the component's own input nobody was shown the producer of was
    an error of the baseline.

    ``run_plugins`` false reads it as ``--no-plugins`` asks, as the candidate is read. That a
    plugin of the baseline did not run is this run's doing rather than the baseline's, so its
    ``plugin-skipped`` is carried over beside the errors, prefixed as they are and graded as
    the run grades its own, and the plugin is noted on ``bag`` as not run
    (:meth:`~ddd.diagnostics.DiagnosticBag.skip`), which checks it registers being unknown.
    """
    floor = SeverityPolicy.from_strings(
        STANDALONE_POLICY if standalone else (), strict=False, standalone=standalone
    )
    own = DiagnosticBag(
        SeverityPolicy({**floor.overrides, **relaxations(bag.policy)}, False, standalone)
    )
    resolved = read_dictionary(path, own, reading, floor_when_alone=True, run_plugins=run_plugins)
    for diagnostic in own.sorted:
        if diagnostic.severity is Severity.ERROR:
            bag.add(
                diagnostic.check,
                f"{BASELINE_PREFIX}{diagnostic.message}",
                diagnostic.location,
                diagnostic.notes,
                # At the severity the baseline's own analysis gave it, which is the project's
                # relaxations over the check's own grade and never this run's promotions:
                # "the run fails on them" (4.1) is what makes a comparison against an
                # untrustworthy dictionary visible.
                severity=diagnostic.severity,
            )
        elif diagnostic.check == "plugin-skipped":
            bag.add(
                diagnostic.check,
                f"{BASELINE_PREFIX}{diagnostic.message}",
                diagnostic.location,
                diagnostic.notes,
            )
    for spelling in own.skipped:
        bag.skip(spelling)
    return resolved


def holds_a_description(document: dict[str, Any] | None) -> bool:
    """True for a project or component file; a broken file is left to the reader to report.

    A file :func:`read_json_document` could not read at all answers ``False`` rather than
    raising, because this is only a sniff: whichever reader the file actually reaches is what
    has something to say about it, and it reads the file again to say it.
    """
    return document is not None and ("project" in document or "component" in document)


def holds_a_dictionary(document: dict[str, Any] | None) -> bool:
    """True for a file ``ddd dump`` wrote, by the one key every dump stamps.

    ``format`` is what a dictionary declares itself with, and the only field
    :func:`~ddd.loading.load_dictionary` reads before validating anything - so that a dictionary
    from a newer DDD is told it is one rather than judged against a contract it was never
    written to. A file carrying it is that reader's, however badly it reads; one carrying
    neither it nor a description's own key belongs to nobody, which is what a reader who has
    simply named the wrong file is told. Like :func:`holds_a_description`, only a sniff: it
    decides whose refusal a file's is, never whether it loads.
    """
    return document is not None and "format" in document


@dataclass(frozen=True, slots=True)
class Comparison:
    """What :func:`compare_deliveries` made of one pair: the pairing, and whether the candidate
    can replace the baseline."""

    paired: Pairing
    """What :func:`ddd.compare.compare` paired, for ``renames`` to read back."""

    verdict: bool
    """``True`` exactly when no finding of the run is an error, whoever's it is: the
    candidate's own, those the baseline carries over, and the comparison's (SPEC 4.1)."""


def compare_deliveries(
    baseline: Resolved,
    candidate: Resolved,
    bag: DiagnosticBag,
    *,
    location: Location,
    baseline_location: Location | None = None,
    plugins: Sequence[Plugin] | None = None,
    on_plugin_error: Callable[[PluginError], None] | None = None,
    held_elsewhere: int = 0,
) -> Comparison:
    """Whether ``candidate`` can replace ``baseline``: the comparison, then the plugins' own
    comparison rules, then the verdict - the one place that order is written.

    ``ddd compare``, ``ddd check --baseline`` and the Compare tab each ran their own copy, and
    the copies disagreed: the tab did not count the project's own errors, and called a delivery
    that both commands exit 1 on one that can replace. What differs between the callers is a
    parameter here and nothing else:

    - ``bag`` is where the comparison's findings go. The commands' holds the candidate's own
      and the baseline's carried errors too, which is what their exit code answers by. The
      tab keeps three lists apart, so what it keeps elsewhere is ``held_elsewhere``, a count
      of errors that bear on the verdict and are not in ``bag``.
    - ``plugins`` are the hooks to run, where they are not the candidate's own: an archived
      dictionary names none, so ``ddd compare --plugin`` supplies them.
    - ``on_plugin_error`` is what a hook that raises becomes. Left out, it is raised, which is
      a usage error on the command line; the tab files it as a finding instead, because the
      server promises findings and never an exception. Either way the verdict refuses: rules
      that never finished grading are not ones a "can replace" may rest on.
    """
    from ddd.compare import compare
    from ddd.plugins import PluginError, run_compare_hooks

    paired = compare(
        baseline.dictionary,
        candidate.dictionary,
        bag,
        location=location,
        baseline_alone=baseline.alone,
        candidate_analysed=candidate.from_description,
    )
    refused = False
    try:
        run_compare_hooks(
            candidate.plugins if plugins is None else plugins,
            baseline.dictionary,
            candidate.dictionary,
            candidate.settings,
            bag,
            candidate.locate,
            location,
            baseline_location,
        )
    except PluginError as error:
        if on_plugin_error is None:
            raise
        on_plugin_error(error)
        refused = True
    verdict = not (refused or held_elsewhere or bag.has_errors)
    return Comparison(paired, verdict)
