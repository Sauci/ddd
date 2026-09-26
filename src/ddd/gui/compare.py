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
because those are the baseline's own analysis handed back unchanged - a ``duplicate-component``
found while reading a baseline given as a multi-file project description carries a note pointing
at the *other* baseline file, and both the primary location and that note's are inside the
baseline, never inside the open project.

Filing that mirror anyway - rather than special-casing it away - is the considered choice: the
primary copy already sits at a path the page cannot open (it is not one of ``revision.files``,
so :func:`~ddd.gui.api._finding` resolves no source for it and answers ``route: None``, exactly
as it already does for a finding whose file did not load or names no place); the mirror is the
same fact, truthfully reported at the *other* baseline file the note is about. Collapsing the
note's location before grouping - so the mirror lands on the candidate's own project file
instead - would trade a truthful, inert row for one that looks like it is about the open
project when it is not, which is worse. A row the page cannot open is not a defect here: it is
what "this finding is about the baseline, not about a file you have open" looks like once it
reaches the wire, and the contract already has words for it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from ddd.compare import compare, renames
from ddd.deliveries import Resolved, read_baseline
from ddd.diagnostics import Diagnostic, DiagnosticBag, SeverityPolicy, where
from ddd.editing import fingerprint
from ddd.gui.session import Filed, Revision
from ddd.lsp.diagnostics import group_findings

_NOT_JSON_CHECKS: Final = frozenset({"json-syntax"})
"""The check the loader files when the bytes are not valid json - or not valid utf-8, which is
the same refusal one step earlier, reported through the same check.

``file-not-found`` never reaches :func:`_refusal_reason`: :func:`_resolved_baseline` has
already read the file's bytes once by the time it asks ``read_baseline`` to read it as a
dictionary or a description, so a reason of that kind was already raised, from that first
read, as *unreadable* - the message :func:`_resolved_baseline` builds itself rather than
one this looks up."""

type BaselineCache = dict[tuple[Path, str], tuple[Resolved | None, tuple[Diagnostic, ...]]]
"""Every baseline this session has resolved, keyed by its resolved path *and* the fingerprint it
was read at - never the path alone, which would go on serving a stale delivery after a re-dump.

The value is what :func:`~ddd.deliveries.read_baseline` produced: the resolved side of the
comparison (``None`` when it was refused), and every diagnostic it forwarded ("in the baseline:
..."), captured once so a cache hit still reports them without reading the file again.
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
    """``True`` when no finding of severity error survived the session's own policy."""

    findings: tuple[Filed, ...]
    """Every finding the comparison reported, grouped onto the files each belongs on exactly as
    a revision's own findings are."""

    renames: tuple[dict[str, str], ...]
    """Every object the two sides agree is one and the same but call differently now, as
    :func:`ddd.compare.renames` already shapes them - what ``ddd compare --renames`` writes."""


def compared(revision: Revision, baseline: Path, root: Path, cache: BaselineCache) -> Compared:
    """Compare ``revision``'s dictionary against the baseline named at ``baseline``.

    ``root`` is the session's own root, the one directory a baseline is ever allowed to be read
    from: a path :func:`_resolved_baseline` finds outside it is refused with its reason instead
    of being clamped to something inside it, which would silently compare against a delivery
    nobody named. ``cache`` is owned by the caller - the route itself keeps nothing between two
    requests - and is only ever read and added to here.
    """
    dictionary = revision.dictionary
    if dictionary is None:
        # The caller (`Api._compare`) already answers this before it ever reaches here, the way
        # `_values` and `_value_plan` answer their own "the project did not resolve" without
        # calling into a helper that cannot do anything about it either. Kept as a real check
        # and not an assertion so that a caller who does not guard it is told why, in a sentence,
        # rather than by a type error at the call to `compare` two lines down.
        raise ValueError(
            "the open project did not resolve, so it cannot be compared against a baseline"
        )
    resolved, forwarded = _resolved_baseline(baseline, root, cache)
    bag = DiagnosticBag(_policy_of(revision))
    for diagnostic in forwarded:
        # Replayed rather than re-derived: a cache hit skips reading the baseline again, and its
        # errors are read back from what the first read forwarded, at the severity that read
        # gave them - the same "no `-W` of this run reaches them" rule `read_baseline` documents.
        bag.add(
            diagnostic.check,
            diagnostic.message,
            diagnostic.location,
            diagnostic.notes,
            severity=diagnostic.severity,
        )
    location = where(revision.project)
    paired = compare(resolved.dictionary, dictionary, bag, location=location)
    grouped: dict[Path, list[Diagnostic]] = {}
    group_findings(bag, revision.project, grouped)
    findings = tuple(Filed(path, found) for path in sorted(grouped) for found in grouped[path])
    return Compared(not bag.has_errors, findings, tuple(renames(paired)))


def _policy_of(revision: Revision) -> SeverityPolicy:
    """The severity policy to grade a comparison's findings with: the session's own, not a new
    control the route invents.

    A revision with no build record analysing it is checked under the defaults, the same run
    ``_analysed`` makes for it; one with a build record is checked under the first one's
    ``-W`` and ``--strict``, the way a project named by exactly one build is checked everywhere
    else in this file. A project two build records disagree about already reports two copies of
    a consistency finding when they grade a check differently (`group_findings`'s own docstring);
    resolving that same disagreement for a check no build record has ever named is not something
    a single verdict can answer either way, so the first record is the one that governs here.
    """
    if not revision.builds:
        return SeverityPolicy()
    build = revision.builds[0]
    return SeverityPolicy.from_strings(list(build.severity), strict=build.strict)


def _resolved_baseline(
    path: Path, root: Path, cache: BaselineCache
) -> tuple[Resolved, tuple[Diagnostic, ...]]:
    """Read the baseline at ``path``, confined to ``root``, through the cache.

    Confinement is checked before anything is read, on the resolved path alone - a path that
    does not exist yet still resolves - so that a reader who typed one outside the root is told
    that and nothing about the file itself. ``Path.resolve()`` then ``is_relative_to`` is the
    reading :func:`~ddd.gui.session.find_projects` already gives its own root, followed rather
    than invented a second time.
    """
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise BaselineRefusedError(
            f"the baseline '{resolved.as_posix()}' is outside the session root '{root.as_posix()}'"
        )
    try:
        data = resolved.read_bytes()
    except OSError as error:
        raise BaselineRefusedError(
            f"the baseline '{resolved.as_posix()}' is unreadable: {error}"
        ) from error
    key = (resolved, fingerprint(data))
    hit = cache.get(key)
    if hit is None:
        own = DiagnosticBag()
        found = read_baseline(resolved, own)
        hit = (found, tuple(own.sorted))
        cache[key] = hit
    found, forwarded = hit
    if found is None:
        raise BaselineRefusedError(_refusal_reason(resolved, forwarded))
    return found, forwarded


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
