"""Answering the question ``ddd check`` was never asked: can the open project stand in for a
delivery already handed out?

``ddd compare`` and ``ddd check --baseline`` ask this on the command line, against a candidate
and a baseline both named there. The page only ever has one candidate - the project it has
open - so this is narrower on purpose: the reader names a baseline, and the answer is read
against the revision the session already analysed. Nothing here re-reads or re-analyses the
candidate; ``revision.dictionary`` is what the session resolved for :mod:`ddd.gui.session`'s own
purposes, and comparing it a second time would mean two copies of "how a candidate becomes a
dictionary" agreeing by coincidence rather than by construction.

Reading the baseline is not this module's to reinvent either: :func:`ddd.deliveries.read_baseline`
is Task 1's shared policy - a bag of its own, ``-W`` never reaching it, only its errors carried
over - and using anything else here would drift from ``ddd compare`` the first time either side
changed.

**A comparison is :func:`ddd.compare.compare` and then
:func:`ddd.plugins.run_compare_hooks`**, in that order, which is what both
``ddd compare`` and ``ddd check --baseline`` do. The second half is not an extra: the thirteen
built-in comparison checks grade what every delivery has, and a plugin's comparison rules grade
what *this* project stamps on it - a layout key a dataset is keyed on, a version that has to
rise with the bytes. Running the first half alone answered "can replace" for a delivery the
command exits 1 on, and lost ``missing-plugin``, which the hooks file and which exists to say
that a rule did not run at all. Running them needs the candidate's plugins, which is why
:class:`~ddd.gui.session.Revision` carries the whole :class:`~ddd.deliveries.Resolved` the
session's analysis produced rather than its dictionary alone.

**A note on what a comparison's findings are filed on.** :func:`~ddd.lsp.diagnostics.group_findings`
is the same function that turns a session's own analysis into rows the page can draw, and it is
reused unchanged, per the same reasoning that keeps :func:`~ddd.gui.api._finding` unchanged: a
comparison finding must not route differently from a consistency finding for no visible reason.
That function's ``_mirrors`` step files a second copy of a finding at each location one of its
notes points to - right for a session, where both locations are always files of the open project,
so that neither side of an in-project disagreement looks unmarked. A comparison's own findings
never trigger it: every one of them carries the single ``location`` this module passes to
:func:`ddd.compare.compare`, and none of them attaches a note with a location of its own (checked
against the table in ``ddd/compare.py``: every note it builds is ``(text, None)``). It *can* fire
on the errors :func:`~ddd.deliveries.read_baseline` forwards, prefixed ``"in the baseline: "``,
because those are the baseline's own analysis handed back unchanged - a ``multiple-producers``
found while reading a baseline given as a multi-file project description carries a note pointing
at the *other* file that also produces the object, and both copies are the baseline's, whatever
either happens to be named.

**Whatever it happens to be named is the part a path check cannot settle.** A baseline is read
under the session root, and the candidate's own files are under it too - a reader may legally
point ``?baseline=`` at the project it already has open, which is the very first thing anyone
compares against. When they do, a baseline finding's file coincides with a real file of
``revision.files``, id for id and path for path. Filing baseline findings through the same
``Filed`` list the comparison's own findings use, and letting the api layer resolve a route for
every entry by asking "is this file one of ``revision.files``", answered that question wrong:
a message that says "in the baseline: ..." got a live link into the open project, because the
open project and the baseline happened to be read from the same file. **The two are kept apart
instead**: :attr:`Compared.findings` is what :func:`ddd.compare.compare` itself reported, routed
normally, and :attr:`Compared.baseline_findings` is everything :func:`~ddd.deliveries.read_baseline`
forwarded, always answered ``route: None`` by the caller - marked as the baseline's by which
list it is in, not by where its path happens to resolve to.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from ddd.compare import compare, renames
from ddd.deliveries import Resolved, read_baseline
from ddd.diagnostics import (
    CHECKS,
    CheckInfo,
    Diagnostic,
    DiagnosticBag,
    SeverityPolicy,
    where,
)
from ddd.gui.session import Filed, Revision, stamped
from ddd.lsp.diagnostics import group_findings
from ddd.plugins import PluginError, run_compare_hooks

_NOT_JSON_CHECKS: Final = frozenset({"json-syntax"})
"""The check the loader files when the bytes are not valid json - or not valid utf-8, which is
the same refusal one step earlier, reported through the same check.

``file-not-found`` never reaches :func:`_refusal_reason`: :func:`_read` has already opened the
file once by the time it asks ``read_baseline`` to read it as a dictionary or a description, so
a reason of that kind was already raised, from that probe, as *unreadable* - the message
:func:`_read` builds itself rather than one this looks up."""

_COMPARISON_CHECKS: Final = frozenset(
    identifier for identifier, info in CHECKS.items() if info.comparison
)
"""Every check :func:`ddd.compare.compare` can file, read from the registry's own flag rather
than listed again - the same reasoning :data:`ddd.diagnostics.STANDALONE_POLICY` gives for
deriving its own list instead of naming checks by hand."""


@dataclass(frozen=True, slots=True)
class Cached:
    """One baseline this session has resolved, and what would make it stale."""

    resolved: Resolved
    """The side of the comparison :func:`~ddd.deliveries.read_baseline` produced."""

    forwarded: tuple[Diagnostic, ...]
    """Every diagnostic that read forwarded ("in the baseline: ..."), captured once so that a
    cache hit still reports them without reading the file again."""

    stamps: dict[Path, tuple[int, int] | None]
    """The stamp of every file the read was made out of, as :func:`~ddd.gui.session.stamped`
    takes them - :attr:`ddd.deliveries.Resolved.sources`, which is the whole include tree and
    the plugins for a description and the one file for an archived dump."""


type BaselineCache = dict[Path, Cached]
"""Every baseline this session has resolved, by its resolved path - one entry each, the newest
read of it holding the entry.

**What is cached is the whole delivery, not the file that names it.** Keyed on the named file
and a fingerprint of it, an edit to a file that file *includes* left the key untouched and a
stale verdict was served; and comparing a project against itself - "the very first thing anyone
compares against" (spec §3) - answered *cannot replace* or *can*, depending on nothing but
whether the entry happened to be warm. A cache "in the strict sense: discarding it changes speed
and nothing else" (spec §4) may not decide an answer, so an entry is used only while every file
it was read out of still carries the stamp it was read at.

Nothing is kept for a baseline that did not resolve: a refusal is not a delivery, and one held
here would go stale the moment the reader fixed the file it is about.
"""


class BaselineRefusedError(ValueError):
    """Why ``?baseline=`` could not be read as one, for the route to answer 400 with.

    Every reason the spec names is a message a reader can act on rather than a bare refusal:
    the path they typed is the thing they have to fix, and only the message says how.
    """


@dataclass(frozen=True, slots=True)
class Compared:
    """Whether the open project can replace a baseline, and everything the page draws about it."""

    verdict: bool
    """``True`` when no finding of severity error, in either list below, survived its policy."""

    findings: tuple[Filed, ...]
    """Every finding ``ddd.compare.compare`` itself reported, filed on the candidate exactly as
    a revision's own findings are, and routed the same way through ``_finding``."""

    baseline_findings: tuple[Filed, ...]
    """Every error the baseline's own analysis reported, forwarded here prefixed ``"in the
    baseline: "``. Never routed by the caller, whatever file one of these happens to sit at -
    a baseline given as a project description can share files, ids and paths with the open
    project, and being in this list rather than in ``findings`` is what marks a finding as the
    baseline's, not where it resolves to."""

    renames: tuple[dict[str, str], ...]
    """Every object the two sides agree is one and the same but call differently now, as
    :func:`ddd.compare.renames` already shapes them - what ``ddd compare --renames`` writes."""


def compared(revision: Revision, baseline: Path, root: Path, cache: BaselineCache) -> Compared:
    """Compare what ``revision`` resolved to against the baseline named at ``baseline``, under
    every rule the command's own exit code answers by - the built-in comparison checks and the
    project's plugins' own.

    ``root`` is the session's own root, the one directory a baseline is ever allowed to be read
    from: a path :func:`_resolved_baseline` finds outside it is refused with its reason instead
    of being clamped to something inside it, which would silently compare against a delivery
    nobody named. ``cache`` is owned by the caller - the route itself keeps nothing between two
    requests - and is only ever read and added to here.
    """
    candidate = revision.resolved
    if candidate is None:
        # The caller (`Api._compare`) already answers this before it ever reaches here, the way
        # `_values` and `_value_plan` answer their own "the project did not resolve" without
        # calling into a helper that cannot do anything about it either. Kept as a real check
        # and not an assertion so that a caller who does not guard it is told why, in a sentence,
        # rather than by a type error at the call to `compare` two lines down.
        raise ValueError(
            "the open project did not resolve, so it cannot be compared against a baseline"
        )
    resolved, forwarded = _resolved_baseline(baseline, root, cache)

    # The baseline's own errors, in a bag of their own: kept apart from `compare`'s own findings
    # from the moment they are read, exactly so that they are never routed as though they were
    # about the open project - see the module docstring's note on what this list is.
    baseline_bag = DiagnosticBag()
    for diagnostic in forwarded:
        # Replayed rather than re-derived: a cache hit skips reading the baseline again, and its
        # errors are read back from what the first read forwarded, at the severity that read
        # gave them - the same "no `-W` of this run reaches them" rule `read_baseline` documents.
        # `baseline_bag`'s own policy plays no part in this: every one of these calls states its
        # severity, which is the one thing `DiagnosticBag.add` never asks the policy to resolve.
        baseline_bag.add(
            diagnostic.check,
            diagnostic.message,
            diagnostic.location,
            diagnostic.notes,
            severity=diagnostic.severity,
        )
    baseline_grouped: dict[Path, list[Diagnostic]] = {}
    group_findings(baseline_bag, revision.project, baseline_grouped)
    baseline_findings = tuple(
        Filed(path, found) for path in sorted(baseline_grouped) for found in baseline_grouped[path]
    )

    compare_bag = DiagnosticBag(_policy_of(revision))
    # The candidate's own plugin checks, so that a finding one of their comparison rules files
    # is graded by the policy above rather than by `SeverityPolicy.resolve`'s fallback for a
    # check it has never heard of, which is `Severity.ERROR` whatever the plugin declared.
    compare_bag.register(revision.checks)
    location = where(revision.project)
    paired = compare(resolved.dictionary, candidate.dictionary, compare_bag, location=location)
    try:
        # What both commands do next, and what this did not: `compare()` grades the thirteen
        # built-in comparison checks, and every rule a plugin states about a replacement -
        # ``layout/key-changed``, that a dataset keyed on an entry now reads an orphan - is run
        # from here. Missed, the verdict was a confident "can replace" with a hole in it, and
        # ``missing-plugin``, which exists to close that hole, was missed with it.
        run_compare_hooks(
            candidate.plugins,
            resolved.dictionary,
            candidate.dictionary,
            compare_bag,
            candidate.locate,
            location,
            where(baseline),
        )
    except PluginError as error:
        # A hook raising is a defect of the plugin rather than of either delivery. ``ddd
        # compare`` answers a usage error; the server promises findings and never an exception,
        # so it is filed as one here, the way `ddd.lsp.diagnostics._run` files the same defect
        # met while analysing. `plugin-invalid` is an error, so the verdict refuses rather than
        # answering one the plugin's own rules never graded.
        compare_bag.add("plugin-invalid", str(error), location)
    compare_grouped: dict[Path, list[Diagnostic]] = {}
    group_findings(compare_bag, revision.project, compare_grouped)
    findings = tuple(
        Filed(path, found) for path in sorted(compare_grouped) for found in compare_grouped[path]
    )

    verdict = not compare_bag.has_errors and not baseline_bag.has_errors
    return Compared(verdict, findings, baseline_findings, tuple(renames(paired)))


def _policy_of(revision: Revision) -> SeverityPolicy:
    """The severity policy to grade ``compare``'s own findings with: the session's own, not a
    new control the route invents.

    A revision with no build record analysing it is checked under the defaults, the same run
    ``_analysed`` makes for it. One with several is checked under the *strictest* reading any
    of them would give a comparison check - the worst of what each build's own ``-W`` and
    ``--strict`` would resolve it to, one check at a time, not the first build's answer alone.
    A build's own filename or discovery order must not decide a verdict: two records disagreeing
    about ``changed-interface``'s severity used to make the same comparison pass or fail by
    which one happened to sort first, which is not a property of the delivery being compared. A
    delivery any one of the project's builds would refuse is not one to call acceptable, so the
    strictest reading is the one taken - at the cost that a project whose images genuinely
    disagree is told an error where one image alone would have said warning.

    Running the comparison once per build and showing a row each, the way ``_analysed`` keeps
    two images that disagree as two findings, is not done here: a comparison finding is not
    "this build's opinion of a consistency rule" the way `group_findings`'s own docstring means
    it, and multiplying every one of them by the number of images is a part of its own rather
    than a tie-break for this one.
    """
    policies = [
        SeverityPolicy.from_strings(list(build.severity), strict=build.strict)
        for build in revision.builds
    ]
    if not policies:
        return SeverityPolicy()
    return SeverityPolicy(
        {
            check: min((policy.resolve(check, info) for policy in policies), key=lambda s: s.rank)
            for check, info in _graded(revision).items()
        }
    )


def _graded(revision: Revision) -> dict[str, CheckInfo]:
    """Every check this comparison can file and the registry entry to grade it by: the built-in
    comparison checks, and the comparison checks the project's own plugins register.

    The plugins' are not in :data:`ddd.diagnostics.CHECKS` and never will be - a plugin's checks
    live on the bag that loaded it, so that two projects checked in one process cannot leak one
    into the other - so they are read from ``revision.checks``, which is that registration as
    the session kept it. Left out, a build's ``-W layout/key-changed=warning`` would be resolved
    against nothing and the finding reported at the fallback severity instead of the stated one.
    """
    plugins = {info.identifier: info for info in revision.checks if info.comparison}
    return {identifier: CHECKS[identifier] for identifier in _COMPARISON_CHECKS} | plugins


def _resolved_baseline(
    path: Path, root: Path, cache: BaselineCache
) -> tuple[Resolved, tuple[Diagnostic, ...]]:
    """Read the baseline at ``path``, confined to ``root``, through the cache.

    Confinement is checked before anything is read, on the resolved path alone - a path that
    does not exist yet still resolves - so that a reader who typed one outside the root is told
    that and nothing about the file itself. ``Path.resolve()`` then ``is_relative_to`` is the
    reading :func:`~ddd.gui.session.find_projects` already gives its own root, followed rather
    than invented a second time.

    An entry already held is used only while every file it was read out of still carries the
    stamp it was read at - :func:`~ddd.gui.session.stamped`, the session's own reading of "has
    this file changed", asked of the baseline's files as the poller asks it of the candidate's.
    A file a wildcard include would match only once it exists is noticed when something else
    changes, which is the limit the session already states for the open project.
    """
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise BaselineRefusedError(
            f"the baseline '{resolved.as_posix()}' is outside the session root '{root.as_posix()}'"
        )
    hit = cache.get(resolved)
    if hit is None or stamped(hit.stamps) != hit.stamps:
        hit = _read(resolved)
        cache[resolved] = hit
    return hit.resolved, hit.forwarded


def _read(path: Path) -> Cached:
    """The baseline at ``path``, read and stamped, or the reason it is not one.

    The open is a probe and reads nothing: it answers *unreadable* - a file that is not there,
    a directory, one whose permissions refuse - before ``read_baseline`` is asked for a reading
    that would report it as something else entirely. Reading the bytes here as well, which is
    what the fingerprint key used to need, meant the 45 MB dump of a thousand object project
    went through twice.
    """
    try:
        with path.open("rb"):
            pass
    except OSError as error:
        raise BaselineRefusedError(
            f"the baseline '{path.as_posix()}' is unreadable: {error}"
        ) from (error)
    own = DiagnosticBag()
    found = read_baseline(path, own)
    forwarded = tuple(own.sorted)
    if found is None:
        raise BaselineRefusedError(_refusal_reason(path, forwarded))
    return Cached(found, forwarded, stamped(found.sources))


def _refusal_reason(path: Path, diagnostics: tuple[Diagnostic, ...]) -> str:
    """Which of the spec's remaining reasons a baseline that did not resolve was refused for -
    "outside the root" and "unreadable" are both settled before this is ever called.

    ``read_baseline`` never returns ``None`` without having forwarded at least one error first -
    ``read_dictionary`` adds one before every ``return None`` of its own, whichever of its two
    readers meets the file - so ``diagnostics`` is never empty here. Classified by the check
    that fired rather than by re-reading the file a second way: anything other than
    ``json-syntax`` - most often ``schema``, a file that parsed but validates as neither shape -
    is the fourth reason the spec names: a perfectly valid json file that is simply something
    else.
    """
    check = diagnostics[0].check
    if check in _NOT_JSON_CHECKS:
        return f"the baseline '{path.as_posix()}' is not valid json: {diagnostics[0].message}"
    return (
        f"the baseline '{path.as_posix()}' is neither a dictionary nor a description: "
        f"{diagnostics[0].message}"
    )
