"""What a change of the root project's ``includes`` would break, as the analysis itself says.

Transport-neutral, like :mod:`ddd.shared_plans`: nothing here knows about http or the session,
and nothing here imports :mod:`ddd.gui`. It is for the gui to call and never calls the gui, so
findings arrive as ``(path, diagnostic)`` pairs - the shape
:func:`ddd.project_shared.shared_rows` takes for the same reason - rather than as the session's
own ``Filed``.

No rule here says which kinds of file a project may do without. :func:`new_errors` counts the
errors of two analyses of one project, the second with the root's list changed, and what the
second has more of is what the change would break.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from ddd.diagnostics import Diagnostic, Severity
from ddd.lsp.diagnostics import finding_identity

type Pair = tuple[Path, Diagnostic]
"""A finding and the file it is shown on, as :func:`ddd.project_shared.shared_rows` takes them."""

REATTRIBUTED: Final = frozenset(
    {
        "condition-mismatch",
        "definition-mismatch",
        "duplicate-event",
        "duplicate-id",
        "enum-conflict",
        "multiple-producers",
        "name-collision",
        "name-similar",
        "storage-mismatch",
    }
)
"""The checks :func:`new_errors` counts per check and severity rather than per place: those whose
findings ddd places among the declarations that clash by an order a change of the list can
change - the order it read the project in, which declaration owns an object, or which of the
clashing names sorts first - so that a removal moves an error the project has to another place,
where counted per place it read as new. Each is placed so:

* ``multiple-producers``: on every writer but the first read, mirrored onto the first.
* ``definition-mismatch``, ``storage-mismatch`` and ``condition-mismatch``: on every declaration
  but the reference - the owner, a ``local`` writer or else the writer whose component name sorts
  first, and with no writer the first read - mirrored onto the reference; stated limits against
  the owner's where it states any, else against the first read that does.
* ``name-collision``: on the first read declaration of a variable whose name a type, an enum, an
  enumerator or a constant takes as well; on every component but the first read whose name
  differs from it only in case; on every enum defining an enumerator an earlier one read does;
  and on a constant's own entry where an enum, an enumerator, a type or the member of a structure
  takes its name, mirrored onto that - an enum's first copy met, or the first enum met to define
  the enumerator, both by order.
* ``name-similar``: on the first read declaration of every name but the first in name order of
  those differing only in case, mirrored onto the first read declaration of the first.
* ``duplicate-id``: on the declarations of every object but the first in name order carrying one
  id, mirrored onto the first declaration read of the first that carries it.
* ``duplicate-event``: on every raster claiming one event but the one whose name sorts first,
  mirrored onto it.
* ``enum-conflict``: on every copy of an enum differing from the first met - a types file's
  before any component's, components' in the order read - mirrored onto it.

Each reports a clash between declarations. A removal can resolve one or move one, and it can
relabel one - a local declaration gone, its other writers' ``local-conflict`` reported as
``multiple-producers`` - or re-count one against a new reference: a new owner, a new first read
where nothing writes the object, a new first declaration stating limits where the owner states
none, a new first copy of an enum or a new first definer of an enumerator, which more
declarations differ from than differed from the one before. A relabel or a re-count is counted
like any error of the check it is reported under, and measured, it is refused where it raises
that check's count alone - a local gone from beside its two writers, two readers disagreeing
with a new owner, two with a new first read, two with a new first declaration of limits, one
more copy of an enum differing from a new first one, one more copy colliding with a new first
definer of its enumerator - and allowed where the count stays, or where as many errors of the
check leave with the file.

A removal can also bring in a clash the analysis never compared. Counted per check, it is refused
where nothing of its check leaves with the file, and hidden where as many errors of its check
leave. It comes in two ways. One is a second declaration of a name, which the loader drops while
the first is there and reads once it is gone. That needs a build lowering the ``duplicate-*``
check the loader answers so, each an error by default: under the default the read reports an
error, which leaves the revision unanalysed and so never judged. Measured with the check reported
as a warning for a second component, type and raster, and for a component as an information and
not at all as well. The other is an object the analysis refused, a map too wide over its axes,
which a new owner of one of them lets it compare. Every such case measured is refused counted per
place, and the cost is accepted all the same, because counting per place refuses the removal a
reader makes to end a conflict of two writers, when their readers' disagreement moves onto the
writer left - the case ``test_ending_a_conflict_of_writers_keeps_the_readers_disagreement`` pins,
which fails with ``definition-mismatch`` out of this set.
``test_a_relaxed_duplicate_let_in_hides_its_clash_behind_one_leaving`` pins the cost.

Counted per check, they cannot tell apart two clashes of one check that swap: one resolved as
another is reported leaves the count as it was, and the change is allowed - a reader that agreed
with the owner removed takes the place of the other writer's disagreement with it.

Not ``local-conflict``, although its declarations are placed by the first local read: on a
reference it sits at whatever owns the referrer, and a removal that hands an object to another
owner binds that owner's references afresh - a curve left to a writer that draws it over another
component's private axis is a conflict the project did not have. Nor ``enum-duplicate-value``,
checked on the first copy of an enum met and on no other: a removal can put a copy nobody checked
first. Counted per place instead, a harmless move of either is refused - two locals read in
another order, the first of two identical copies gone - which needs a project that fails that
check already. Nor, for the same first copy, ``init-invalid``, which an enumerator outside a
c ``int`` earns there and on no other copy, so that a removal can make one; nor
``reserved-identifier``, which an enum's name earns on its first copy met and an enumerator on
the first copy of each enum defining it, so that a removal can move one but not make one - and
counted per place, that move is refused.

Nor ddd's other checks that follow an object's owner - ``unknown-reference``, ``reference-kind``,
``a2l-unrepresentable``, the ``schema`` of a map too wide over its axes and ``incomplete-project``,
which read the owner's own definition, and ``point-counts-unrepresentable`` and
``point-counts-mismatch``, which read where the owning component keeps its point counts: a new
owner can make one the project did not have. Nor ``unused-output``, although it sits on the
owner: a removal does make new ones - the last reader gone - and, counted per check, one made
would hide behind one taken away. Nor any plugin's check, nor any check added later: where each
files is not known here, and per place is the default that refuses a harmless change where an
error moves, but hides a new one only where another of its check went from the same place.
"""


def new_errors(before: Sequence[Pair], after: Sequence[Pair]) -> tuple[Pair, ...]:
    """The errors ``after`` has more of than ``before``, in ``after``'s order: what a change of
    the root's ``includes`` would break, ``before`` being what the project reports now and
    ``after`` what it would report with the list changed.

    Errors only, after each run's severity policy: the line ``ddd check`` draws between a
    project that passes and one that fails. A warning a change brings is for the reader to see
    once it is made, not a reason to call the change breaking.

    Counted, not matched, in two passes over ``after``. First each error ``before`` has word for
    word - :func:`~ddd.lsp.diagnostics.finding_identity` - uses that one up; then each error left
    uses up one of ``before``'s still unused under the same :func:`_key`, and one with none left
    to use up is new. Word for word first, so that where a place that had one error has two, the
    error reported is the one the project does not have: taken by key alone in ``after``'s order,
    a new error listed first used up the old one's key, and the old one was quoted as new.

    The errors ``before`` has word for word are set aside first, wherever ``after`` lists them.
    Of the rest, where the count of a place, or of a check counted per check, rose, the ones
    listed past what is left of that count are reported, in the order a revision lists them. So
    what is reported is not an error ``before`` has word for word - of what a revision lists,
    which never holds one identity twice, :func:`~ddd.lsp.diagnostics.group_findings` dropping a
    repeat; given one error twice where ``before`` has it once, the second is reported. Nor is it
    always one the project lacks: where the count rose because an error the project has moved
    there, re-worded, that is what can be reported. Measured: two locals of one variable read in
    another order report its reader's conflict, now worded against the other local, and removing
    the writer two readers agreed with reports both readers' disagreement with the writer left, as
    filed on that writer's own file.

    ``before`` is counted whole, whatever the severity: every key carries its finding's, so only
    an error the project has now can be used up by an error of ``after``. The filters are
    statements in loops rather than comprehensions', which coverage.py counts no branch in.
    """
    identities = Counter(finding_identity(diagnostic) for _, diagnostic in before)
    keys = Counter(_key(diagnostic) for _, diagnostic in before)
    unmatched: list[Pair] = []
    for found in after:
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


def _key(diagnostic: Diagnostic) -> tuple[object, ...]:
    """What an error no error of ``before`` matches word for word is counted as: its check and
    its severity, and its place unless the check is one of :data:`REATTRIBUTED`, but never its
    wording where it has a place of its own.

    A message may name what else the project holds: the writers of a variable, in an order the
    reading sets, or a constant spelled nearly like the one a shape names. Once a file is gone
    the same error at the same place can read differently - the near miss is no longer
    suggested - and keyed by its message, as the editor keys a finding, it would read as new.

    Counted per place, a check cannot see an error whose meaning changes while its place stays:
    one gone and another come at one pointer read as the one the project had.
    """
    if diagnostic.check in REATTRIBUTED:
        return (diagnostic.check, diagnostic.severity)
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
