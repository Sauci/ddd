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
        "enum-duplicate-value",
        "local-conflict",
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
where counted per place it read as new.

Each reports a clash between declarations, which a removal can resolve or move but never make,
and each is placed so:

* ``multiple-producers``: on every writer but the first read, mirrored onto the first.
* ``definition-mismatch``, ``storage-mismatch`` and ``condition-mismatch``: on every declaration
  but the reference - the owner, a ``local`` writer or else the writer whose component name sorts
  first, and with no writer the first read - mirrored onto the reference; stated limits against
  the owner's where it states any, else against the first read that does.
* ``local-conflict``: on every declaration of a local object but the first ``local`` one read,
  mirrored onto it; and on a reference into it, as the referrer's owner or first read writes it.
* ``name-collision``: on the first read declaration of a variable whose name a type, an enum, an
  enumerator or a constant takes as well; on every component but the first read whose name
  differs from it only in case; on every enum defining an enumerator an earlier one read does.
* ``name-similar``: on the first read declaration of every name but the first in name order of
  those differing only in case, mirrored onto the first read declaration of the first.
* ``duplicate-id``: on the declarations of every object but the first in name order carrying one
  id, mirrored onto the first declaration read of the first that carries it.
* ``duplicate-event``: on every raster claiming one event but the one whose name sorts first,
  mirrored onto it.
* ``enum-conflict``: on every copy of an enum differing from the first met - a types file's
  before any component's, components' in the order read - mirrored onto it.
* ``enum-duplicate-value``: on the first copy of an enum met, and on no other.

Counted per check, they cannot tell apart two clashes of one check that swap, one resolved as
another is reported. A removal makes no clash, and one reported that was not - a reader who
agreed with the writer gone disagreeing with the one left - counts as an error more.

Not ``unused-output``, although it sits on the owner: a removal does make new ones - the last
reader gone - and, counted per check, one made would hide behind one taken away. Nor any plugin's
check, nor any check added later: where each files is not known here, and per place is the
default that refuses a harmless change where an error moves, but hides a new one only where
another of its check went from the same place.
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
    its severity, and its place unless ddd places the check by order - see
    :data:`REATTRIBUTED` - but never its wording where it has a place of its own.

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
