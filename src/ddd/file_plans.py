"""What a change of the root project's ``includes`` would break, as the analysis itself says.

Transport-neutral, like :mod:`ddd.shared_plans`: nothing here knows about http or the session,
and nothing here imports :mod:`ddd.gui`. It is for the gui to call and never calls the gui, so
findings arrive as ``(path, diagnostic)`` pairs - the shape
:func:`ddd.project_shared.shared_rows` takes for the same reason - rather than as the session's
own ``Filed``.

No rule here says which kinds of file a project may do without. :func:`new_errors` counts the
errors of two analyses of one project, the second with the root's list changed, place by place,
and what the second has more of is what the change would break. It counts a finding where
``ddd check`` reports it, not again at each place an editor is shown a mirror of it, as far as
:func:`_as_reported` can tell the two apart.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from ddd.diagnostics import Diagnostic, Location, Severity
from ddd.lsp.diagnostics import finding_identity

type Pair = tuple[Path, Diagnostic]
"""A finding and the file it is shown on, as :func:`ddd.project_shared.shared_rows` takes them."""


def new_errors(before: Sequence[Pair], after: Sequence[Pair]) -> tuple[Pair, ...]:
    """The errors ``after`` has more of than ``before``, in ``after``'s order: what a change of
    the root's ``includes`` would break, ``before`` being what the project reports now and
    ``after`` what it would report with the list changed.

    Errors only, after each run's severity policy: the line ``ddd check`` draws between a
    project that passes and one that fails. A warning a change brings is for the reader to see
    once it is made, not a reason to call the change breaking.

    Of what each side lists, what it reports is counted - what :func:`_as_reported` leaves, which
    for ddd's own checks is each finding where ``ddd check`` reports it, and not again at each
    place a note of it points to, where an editor is shown a mirror of it. Where a note points
    at a declaration ddd picks by an order a removal can change - the owner, the first
    declaration read, the name sorting first - the mirrors move with it, and counted, they read
    as new errors where the findings stayed where they were.

    Counted, not matched, in two passes over the errors ``after`` reports. First each one
    ``before`` reports word for word - :func:`~ddd.lsp.diagnostics.finding_identity` - uses that
    one up; then each one left uses up one ``before`` reports, still unused, under the same
    :func:`_key` - its check, severity and place - and one with none left to use up is new. Word
    for word first, so that where a place that had one error has two, the error reported is the
    one the project does not have: taken by key alone in ``after``'s order, a new error listed
    first used up the old one's key, and the old one was quoted as new.

    Per place costs something both ways. ddd reports some findings on declarations it picks by
    an order a removal can change - the owner, the order it reads the project in, the first
    declaration read of a name, the first local, the first copy of an enum met - and a harmless
    removal that moves one is refused wherever the move raises the count of its check and
    severity at a place, quoting the error the project has, reworded where its words name that
    order. Measured, so is a removal that relabels an error - a local gone, its other writers'
    ``local-conflict`` reported as ``multiple-producers`` - or re-counts one against a new
    reference, each quoting an error the project would really have. The other way, a new error
    is hidden only where an error of its check and severity leaves the same place - with the
    same message, where the place is a whole file or none - or where it has the shape of a
    mirror (see :func:`_as_reported`). A check filing every finding at one place, as a plugin's
    may, hides there up to as many new errors as leave. ddd's own checks reach the first way
    too, measured: where a build lowers ``duplicate-component`` or ``duplicate-type``, removing
    the first declaration lets in the one the loader dropped, and a reader's disagreement at its
    declaration changes what it is about while its place stays. Of ddd's own checks under the
    default severities, no case of it was found.

    What is reported is never a mirror :func:`_as_reported` tells, and never, word for word, an
    error ``before`` reports: a revision never lists one identity twice,
    :func:`~ddd.lsp.diagnostics.group_findings` filing each once, and the first pass sets each
    of those aside - given one twice where ``before`` reports it once, the second is reported.
    It can have the words of a mirror ``before`` lists, which is not counted: measured, an
    enum's first copy met, read later and differing from the copy met first now, is reported in
    the words of the mirror it was shown.

    Of ``before``, warnings are counted too: every key carries its finding's severity, so only
    an error the project has now can be used up by an error of ``after``. The filters are
    statements in loops rather than comprehensions', which coverage.py counts no branch in.
    """
    had = _as_reported(before)
    identities = Counter(finding_identity(diagnostic) for _, diagnostic in had)
    keys = Counter(_key(diagnostic) for _, diagnostic in had)
    unmatched: list[Pair] = []
    for found in _as_reported(after):
        _, diagnostic = found
        if diagnostic.severity is not Severity.ERROR:
            continue
        identity = finding_identity(diagnostic)
        if identities[identity] > 0:
            identities[identity] -= 1
            keys[_key(diagnostic)] -= 1
            continue
        unmatched.append(found)
    fresh: list[Pair] = []
    for found in unmatched:
        key = _key(found[1])
        if keys[key] > 0:
            keys[key] -= 1
            continue
        fresh.append(found)
    return tuple(fresh)


def _as_reported(pairs: Sequence[Pair]) -> list[Pair]:
    """``pairs`` less what is shaped like a mirror :func:`~ddd.lsp.diagnostics.group_findings`
    adds of a finding, so that an editor marks both sides of a clash: the finding again, without
    notes, at each other place a note of it points to.

    A mirror is told by its shape, as :func:`~ddd.lsp.diagnostics._mirrors` makes one: no notes,
    at the place a note of a finding of its check, severity and message points to - a note with
    a place other than that finding's own, of a finding with a place.

    The shape is a mirror's alone where no finding a run reports has the check, severity,
    message and place of another's mirror, which holds of ddd's own checks: each note they make
    that has a place points at another place its finding is about - the owner, the first read,
    the first copy met - and none of them reports a finding of that check and message there. A
    plugin's check can, and then ``group_findings``, filing one identity once, files the finding
    and a mirror as one: the finding can go uncounted, and mirrors of it be counted in its stead.
    """
    copied: set[tuple[str, Severity, str, Location]] = set()
    for _, diagnostic in pairs:
        placed = diagnostic.location
        if placed is None:
            continue
        for _, noted in diagnostic.notes:
            if noted is None:
                continue
            if noted == placed:
                continue
            copied.add((diagnostic.check, diagnostic.severity, diagnostic.message, noted))
    reported: list[Pair] = []
    for found in pairs:
        diagnostic = found[1]
        if diagnostic.notes:
            reported.append(found)
            continue
        shape = (diagnostic.check, diagnostic.severity, diagnostic.message, diagnostic.location)
        if shape in copied:
            continue
        reported.append(found)
    return reported


def _key(diagnostic: Diagnostic) -> tuple[object, ...]:
    """What an error no error of ``before`` matches word for word is counted as: its check, its
    severity and its place, but never its wording where it has a place of its own.

    A message may name what else the project holds: the writers of a variable, in an order the
    reading sets, or a constant spelled nearly like the one a shape names. Once a file is gone
    the same error at the same place can read differently - the near miss is no longer
    suggested - and keyed by its message, as the editor keys a finding, it would read as new.

    Counted per place, a check cannot see an error whose meaning changes while its place stays:
    one gone and another come at one pointer read as the one the project had.
    """
    return (diagnostic.check, diagnostic.severity, _place(diagnostic))


def _place(diagnostic: Diagnostic) -> tuple[object, ...]:
    """Where an error is: the file and pointer of a placed finding; and for one on a whole file,
    or on no place at all, its message as well, since nothing narrower tells two of those apart.
    The three are of three lengths, so that none can ever be taken for another.

    A finding at one of the root's own ``includes`` entries is placed by its position like any
    other, although removing an entry moves every later one up. ddd files there only while it
    reads the project, and a run whose read reports an error is never analysed, so where every
    run of ``before`` was analysed no error of ddd's own sits at an entry, and one there after the
    change is new whichever way it is keyed. A plugin's check is not told the list a run was
    given, only able to read the one in the file, which the change leaves as it was: keyed by
    the entry the changed list has at that position, its unchanged finding would read as new.
    """
    location = diagnostic.location
    if location is None:
        return (diagnostic.message,)
    if not location.pointer:
        return (location.path, location.pointer, diagnostic.message)
    return (location.path, location.pointer)
