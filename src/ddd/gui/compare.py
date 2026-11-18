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
is Task 1's shared policy - a bag of its own, the project's relaxations reaching it and no
promotion of any ``-W``, only its errors carried over - and using anything else here would drift
from ``ddd compare`` the first time either side changed.

**A comparison is :func:`ddd.deliveries.compare_deliveries`**, the one function ``ddd compare`` and
``ddd check --baseline`` call as well: :func:`ddd.compare.compare`, then
:func:`ddd.plugins.run_compare_hooks`, then the verdict. Three copies of that order were written
once and disagreed - the page's answered "can replace" for a delivery the command exits 1 on,
because it left out the hooks, and then because its verdict did not count the project's own
errors. The second half is not an extra: the thirteen built-in comparison checks grade what every
delivery has, and a plugin's comparison rules grade what *this* project stamps on it - a layout
key a dataset is keyed on, a version that has to rise with the bytes - and ``missing-plugin`` is
filed by the hooks, to say that a rule did not run at all. Running them needs the candidate's
plugins, which is why :class:`~ddd.gui.session.Revision` carries the whole
:class:`~ddd.deliveries.Resolved` the session's analysis produced rather than its dictionary
alone.

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

**Whatever it happens to be named is the part a path check cannot settle.** A baseline is named
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

from ddd.compare import renames
from ddd.deliveries import (
    BASELINE_PREFIX,
    Reading,
    Refusal,
    Resolved,
    compare_deliveries,
    read_baseline,
    relaxations,
)
from ddd.diagnostics import (
    CHECKS,
    CheckInfo,
    Diagnostic,
    DiagnosticBag,
    Severity,
    SeverityPolicy,
    where,
)
from ddd.gui.session import Filed, Revision, _named_by, stamped
from ddd.lsp.diagnostics import group_findings
from ddd.plugins import PluginError

_REASONS: Final[dict[Refusal, str]] = {
    Refusal.NOT_JSON: "is not valid json",
    Refusal.DESCRIPTION: "is a description that could not be read",
    Refusal.DICTIONARY: "is a dumped dictionary that could not be read",
    Refusal.NEITHER: "is neither a dictionary nor a description",
}
"""What each of the reader's own refusals is called on the page, one entry per
:class:`~ddd.deliveries.Refusal` - the words are this layer's, the classification is not.

``Refusal.NOT_JSON`` covers a file whose bytes could not be read at all as well, which this
never sees: :func:`_read` opens the file first and answers *unreadable* itself, so by the time
the reader is asked the bytes are known to be there."""

_COMPARISON_CHECKS: Final = frozenset(
    identifier for identifier, info in CHECKS.items() if info.comparison
)
"""Every check whose grade the comparison owns, read from the registry's own flag rather
than listed again - the same reasoning :data:`ddd.diagnostics.STANDALONE_POLICY` gives for
deriving its own list instead of naming checks by hand. ``missing-producer``, which ``compare``
also files - of a dumped candidate, and of one analysed under the floor of ``--standalone`` - is
not one of them, and is never filed here: the open project is a description analysed under no
floor, and its analysis has said it."""


@dataclass(frozen=True, slots=True)
class Cached:
    """One baseline this session has resolved, and what would make it stale."""

    resolved: Resolved
    """The side of the comparison :func:`~ddd.deliveries.read_baseline` produced."""

    forwarded: tuple[Diagnostic, ...]
    """Every diagnostic that read forwarded ("in the baseline: ..."), captured once so that a
    cache hit still reports them without reading the file again."""

    relaxed: dict[str, Severity]
    """The relaxations of the project this baseline was read under
    (:func:`~ddd.deliveries.relaxations`): a read under other ones is another read."""

    verified: bool
    """Whether every file the read was made out of carried, when the read ended, the very stamp it
    was given *before* the read began - the order :mod:`ddd.gui.session` keeps for the open
    project, "before, never after", and the equality its poll uses. A write that moves a file's
    modification time or size while the read goes on is told, whatever time it gives the file; one
    that leaves both exactly as they were is not, here as it is not for the session. An entry
    that cannot say so is read again rather than served: it still names the files it was made of,
    which is what the next read stamps beforehand."""

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

MAX_BASELINES: Final = 4
"""How many baselines the cache keeps, the one read longest ago falling off.

Every entry holds a whole :class:`~ddd.ir.DataDictionary` - "the 45 MB one of a thousand object
project", as :mod:`ddd.deliveries` sizes it - and the cache lives as long as the server, which
is a day. Re-asking one baseline costs a single entry however many times it is re-read, but
nothing bounded how many *paths* a session could name, and ``ddd gui --host`` lets somebody else
name them. Four is past what a reader flips between while comparing; the undo stack is bounded
at :data:`~ddd.gui.session.MAX_UNDO` for the same reason, and a cache in the strict sense may be
discarded at will.
"""


class BaselineRefusedError(ValueError):
    """Why ``?baseline=`` could not be read as one, for the route to answer 400 with.

    Every reason is a message a reader can act on rather than a bare refusal: the path they
    typed is the thing they have to fix, and only the message says how. Which reason it is comes
    from whoever settled it - this module for a path outside the root or one that will not open,
    and :class:`ddd.deliveries.Refusal` for everything past that.
    """


@dataclass(frozen=True, slots=True)
class Compared:
    """Whether the open project can replace a baseline, and everything the page draws about it."""

    verdict: bool
    """``True`` when no finding of severity error survived its policy: the project's own
    (:attr:`own_errors`), those the baseline carries over, and the comparison's."""

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

    own_errors: int
    """How many errors the open project has of its own, which the verdict counts as ``ddd compare``
    exit code does: what the state's count of errors is, so that a reader told "cannot replace"
    of a project whose comparison found nothing is told why."""


def compared(revision: Revision, baseline: Path, root: Path, cache: BaselineCache) -> Compared:
    """Compare what ``revision`` resolved to against the baseline named at ``baseline``, under
    every rule the command's own exit code answers by - the built-in comparison checks and the
    project's plugins' own.

    ``root`` is the session's own root, the one directory a baseline may be *named* in: a path
    :func:`_resolved_baseline` finds outside it is refused with its reason instead of being
    clamped to something inside it, which would silently compare against a delivery nobody
    named. What that file includes is read wherever it points, as ``ddd compare`` reads it -
    :func:`_resolved_baseline` says why. ``cache`` is owned by the caller - the route itself
    keeps nothing between two requests - and this only ever reads it, adds to it and drops from
    it what :data:`MAX_BASELINES` puts over the edge.
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
    resolved, forwarded = _resolved_baseline(baseline, root, cache, _relaxed_by(revision))

    # The baseline's own errors, in a bag of their own: kept apart from `compare`'s own findings
    # from the moment they are read, exactly so that they are never routed as though they were
    # about the open project - see the module docstring's note on what this list is.
    baseline_bag = DiagnosticBag()
    for diagnostic in forwarded:
        # Replayed rather than re-derived: a cache hit skips reading the baseline again, and its
        # errors are read back from what the first read forwarded, at the severity that read
        # gave them - under the relaxations of the project and no promotion of any `-W`, the rule
        # `read_baseline` documents.
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

    def refused(error: PluginError) -> None:
        # A hook raising is a defect of the plugin rather than of either delivery. ``ddd
        # compare`` answers a usage error; the server promises findings and never an exception,
        # so it is filed as one here, the way `ddd.lsp.diagnostics._run` files the same defect
        # met while analysing. `plugin-invalid` is an error, so the verdict refuses rather than
        # answering one the plugin's own rules never graded.
        compare_bag.add("plugin-invalid", str(error), location)

    # What both commands do, from the one place that order is written: `compare()` grades the
    # thirteen built-in comparison checks, and every rule a plugin states about a replacement -
    # ``layout/key-changed``, that a dataset keyed on an entry now reads an orphan - is run
    # after it, with ``missing-plugin``, which exists to close the hole a skipped rule leaves.
    # Missed, the verdict was a confident "can replace" with a hole in it.
    own_errors = _own_errors(revision)
    comparison = compare_deliveries(
        resolved,
        candidate,
        compare_bag,
        location=location,
        baseline_location=where(baseline),
        on_plugin_error=refused,
        # The two lists the verdict also answers for, which this keeps apart from the bag: the
        # candidate's own errors and the baseline's carried ones, as the commands' one bag holds.
        held_elsewhere=own_errors + baseline_bag.count(Severity.ERROR),
    )
    compare_grouped: dict[Path, list[Diagnostic]] = {}
    group_findings(compare_bag, revision.project, compare_grouped)
    findings = tuple(
        Filed(path, found) for path in sorted(compare_grouped) for found in compare_grouped[path]
    )

    return Compared(
        comparison.verdict,
        findings,
        baseline_findings,
        tuple(renames(comparison.paired)),
        own_errors,
    )


def _own_errors(revision: Revision) -> int:
    """How many findings of severity error the open project has of its own: what the state counts
    of it, whichever build graded them, and so what ``ddd check`` exits 1 on.

    Counted from the revision's findings rather than computed again under :func:`_policy_of`,
    which grades ``compare``'s own checks and no other: the project's own are graded by each
    build's own run, and a project whose builds disagree about a check keeps the finding of the
    build that grades it an error - the one any build would refuse the delivery for.
    """
    return sum(1 for filed in revision.findings if filed.diagnostic.severity is Severity.ERROR)


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


def _relaxed_by(revision: Revision) -> dict[str, Severity]:
    """What a description baseline is read under: the relaxations every build of the project
    makes, each at the strictest grade any build gives it - a check one build does not relax is
    one the project does not, as :func:`_policy_of` takes the strictest reading of a comparison
    check. Never a promotion, for the reason ``ddd compare`` gives (:func:`read_baseline`)."""
    each = [
        relaxations(SeverityPolicy.from_strings(list(build.severity), strict=build.strict))
        for build in revision.builds
    ]
    if not each:
        return {}
    return {
        check: min((one[check] for one in each), key=lambda severity: severity.rank)
        for check in set.intersection(*(set(one) for one in each))
    }


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
    path: Path, root: Path, cache: BaselineCache, relaxed: dict[str, Severity]
) -> tuple[Resolved, tuple[Diagnostic, ...]]:
    """Read the baseline named at ``path``, which must be under ``root``, through the cache.

    Confinement is checked before anything is read, on the resolved path alone - a path that
    does not exist yet still resolves - so that a reader who typed one outside the root is told
    that and nothing about the file itself. ``Path.resolve()`` then ``is_relative_to`` is the
    reading :func:`~ddd.gui.session.find_projects` already gives its own root, followed rather
    than invented a second time; a path that will not resolve at all is *unreadable*, which is
    what it is.

    **It confines the file the reader names, and not the files that file includes.** A
    description under the root whose ``includes`` point above it is read, and a finding of its
    own comes back filed at a path outside the root. That is deliberate: the include tree is how
    a project is composed and it is that project's own business - ``ddd compare`` reads it the
    same way, and holding the tree to this root here would be a second reading of "which files
    is a delivery made of", diverging from the command the first time either changed. It is also
    not the file-read primitive spec §3 weighs: reaching one needs a description under the root
    that *already* points where the reader wants to look, which whoever can reach the port
    cannot put there - ``POST /api/edit`` writes description files of the open project and
    nothing else.

    An entry already held is used only while every file it was read out of still carries the
    stamp it was read at - :func:`~ddd.gui.session.stamped`, the session's own reading of "has
    this file changed", asked of the baseline's files as the poller asks it of the candidate's.
    A file a wildcard include would match only once it exists is noticed when something else
    changes, which is the limit the session already states for the open project.
    """
    try:
        resolved = path.resolve()
    except (OSError, ValueError, RuntimeError, RecursionError) as error:
        # Resolving is not total, and it is the first thing reader input meets: a NUL inside the
        # path raises `ValueError` out of the stat behind it - and `parse_qs` decodes `%00` into
        # a real one, so it arrives over the wire; on Windows, from python 3.13 on, resolving
        # hands such a path back as it is instead, and `_read`'s open refuses it - while a path
        # the filesystem refuses outright raises `OSError`, and on python 3.12 a loop of links
        # `RuntimeError` and a chain of about a thousand `RecursionError` (a `RuntimeError`
        # already, named for the reader). None is one of the three below, and unanswered here
        # each left a traceback in the terminal and a 500 telling the reader to go and read it.
        # Named as typed, because there is no resolved spelling of a path that would not resolve.
        raise BaselineRefusedError(
            f"the baseline '{path.as_posix()}' is unreadable: {error}"
        ) from error
    if not resolved.is_relative_to(root):
        raise BaselineRefusedError(
            f"the baseline '{resolved.as_posix()}' is outside the session root '{root.as_posix()}'"
        )
    hit = cache.get(resolved)
    if (
        hit is None
        or not hit.verified
        or hit.relaxed != relaxed
        or stamped(hit.stamps) != hit.stamps
    ):
        # Stamped before the read, by the files the last read of it was made of - an entry that
        # was not kept still says which - and, for a first read, by the files the description
        # names itself (:func:`~ddd.gui.session._named_by`, as the session opens a project), so
        # that a flat project is kept from its first read. Compared with the stamps after it by
        # equality, as the session compares a revision's: no window and no clock, so a write
        # that moves the time or the size, an older time and a file dated ahead included, is told.
        known = tuple(_named_by(resolved)) if hit is None else tuple(hit.stamps)
        hit = _read(resolved, relaxed, known)
        # Taken out and put back rather than assigned in place, so that the entry dropped below
        # is the one read longest ago: updating a key leaves it where it first went in.
        cache.pop(resolved, None)
        cache[resolved] = hit
        while len(cache) > MAX_BASELINES:
            del cache[next(iter(cache))]
    return hit.resolved, hit.forwarded


def _read(path: Path, relaxed: dict[str, Severity], known: tuple[Path, ...]) -> Cached:
    """The baseline at ``path``, read and stamped, or the reason it is not one.

    ``known`` are the files stamped with ``path`` before this read begins
    (:attr:`Cached.verified`): those the last read of it was made of, or, for a first read, those
    the file names itself (:func:`~ddd.gui.session._named_by`).

    The open is a probe and reads nothing: it answers *unreadable* - a file that is not there,
    a directory, one whose permissions refuse, a path no file can bear - before
    ``read_baseline`` is asked for a reading that would report it as something else entirely.
    ``open`` raises ``ValueError`` rather than ``OSError`` for a path holding a NUL, which
    resolving hands back as it is on Windows from python 3.13 on, where elsewhere it raises
    (:func:`_resolved_baseline`): refused here as unreadable all the same, the route's ``400``
    (12:M1). Reading the bytes here as well, which is what the fingerprint key used to need,
    meant the 45 MB dump of a thousand object project went through twice on every read. A first
    read still parses it twice, once to learn what it names (:func:`~ddd.gui.session._named_by`)
    and once in ``read_baseline``, a cost paid once per baseline the cache does not hold.
    """
    try:
        with path.open("rb"):
            pass
    except (OSError, ValueError) as error:
        raise BaselineRefusedError(
            f"the baseline '{path.as_posix()}' is unreadable: {error}"
        ) from (error)
    before = stamped((path, *known))
    # The bag the carried errors are forwarded into, graded by the project's relaxations as
    # ``ddd compare``'s own bag is: that is where `read_baseline` takes them from.
    own = DiagnosticBag(SeverityPolicy(dict(relaxed)))
    reading = Reading()
    try:
        found = read_baseline(path, own, reading=reading)
    except PluginError as error:
        # A description's own plugins are loaded and run while it is read - `load_workspace`
        # validates each `extensions` block against its plugin's model, and `analyze` runs the
        # check hooks - and a defect in one raises instead of reporting. Only a description can
        # reach this: a dump runs no hook of anybody's. Refused as the description it is, with
        # what the plugin did as the detail, where spec §6 promises a reason and a traceback in
        # the terminal was what a reader got.
        raise BaselineRefusedError(_refused(path, Refusal.DESCRIPTION, str(error))) from error
    forwarded = tuple(own.sorted)
    if found is None:
        # `read_dictionary` records one before every `return None` of its own, whichever of its
        # two readers met the file, so there is always a reason here to put into words.
        assert reading.refusal is not None
        raise BaselineRefusedError(_refusal_reason(path, reading.refusal, forwarded))
    after = stamped(found.sources)
    verified = all(file in before and before[file] == stamp for file, stamp in after.items())
    return Cached(found, forwarded, dict(relaxed), verified, after)


def _refusal_reason(path: Path, refusal: Refusal, diagnostics: tuple[Diagnostic, ...]) -> str:
    """Why a baseline that did not resolve was refused, in the reader's own words - "outside the
    root" and "unreadable" are both settled before this is ever called.

    The reason comes from :class:`~ddd.deliveries.Refusal`, which the reader sets as it goes,
    and never from classifying one diagnostic out of a bag this did not fill: that told a
    description with a missing include, and a dump from a newer DDD, that they were "neither a
    dictionary nor a description" - the one refusal that means *you named the wrong file*, said
    of two files that were exactly the right kind and merely broken.

    The detail is the first error the read reported, which is the one a reader acts on, with
    :data:`~ddd.deliveries.BASELINE_PREFIX` taken off: that prefix marks a finding shown beside
    a run's own findings, and inside a sentence that has already named the baseline it reads as
    a stutter. ``read_baseline`` never answers ``None`` without forwarding at least one error
    first, so there is always one.
    """
    return _refused(path, refusal, diagnostics[0].message.removeprefix(BASELINE_PREFIX))


def _refused(path: Path, refusal: Refusal, detail: str) -> str:
    """One refusal, in the one shape all of them take: which file, which reason, what happened."""
    return f"the baseline '{path.as_posix()}' {_REASONS[refusal]}: {detail}"
