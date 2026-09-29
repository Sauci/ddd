"""What a change of the root project's ``includes`` would break, as the analysis itself says.

Transport-neutral, like :mod:`ddd.shared_plans`: nothing here knows about http or the session,
and nothing here imports :mod:`ddd.gui`. It is for the gui to call and never calls the gui, so
findings arrive as ``(path, diagnostic)`` pairs - the shape
:func:`ddd.project_shared.shared_rows` takes for the same reason - rather than as the session's
own ``Filed``.

No rule here says which kinds of file a project may do without. :func:`new_errors` counts the
errors of two analyses of one project, the second with the root's list changed, place by place,
and what the second has more of somewhere is what the change would break.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from ddd.diagnostics import Diagnostic, Severity

type Pair = tuple[Path, Diagnostic]
"""A finding and the file it is shown on, as :func:`ddd.project_shared.shared_rows` takes them."""

_ENTRY: Final = re.compile(r"project\.includes\[(\d+)\]")
"""The pointer the loader files a finding about one of a project's own ``includes`` entries at,
the entry's index captured. Matched whole, by ``fullmatch``."""


def new_errors(
    project: Path,
    before: Sequence[Pair],
    before_includes: Sequence[str],
    after: Sequence[Pair],
    after_includes: Sequence[str],
) -> tuple[Pair, ...]:
    """The errors ``after`` has more of than ``before``, place by place, in ``after``'s order:
    what a change of the root's ``includes`` would break.

    ``before`` is what the project reports with ``before_includes`` as its root's list, and
    ``after`` what it reports with ``after_includes``; ``project`` is the root's own file.

    Errors only, after each run's severity policy: the line ``ddd check`` draws between a
    project that passes and one that fails. A warning a change brings is for the reader to see
    once it is made, not a reason to call the change breaking.

    Counted, not matched: each error of ``after``, taken in its own order, uses up one of
    ``before``'s under the same key - see :func:`_key` - and one with none left to use up is
    new. So an error at a place that had none of its check is new, and so is a second one where
    the project has one; and which of two alike is the new one is the same every time, the one
    ``after`` lists later.

    ``before`` is counted whole, whatever the severity: every key carries its finding's, so only
    an error the project has now can be used up by an error of ``after``. The filter on
    ``after`` is a statement in a loop rather than a comprehension's, which coverage.py counts
    no branch in.
    """
    had = Counter(_key(diagnostic, project, before_includes) for _, diagnostic in before)
    fresh: list[Pair] = []
    for found in after:
        _, diagnostic = found
        if diagnostic.severity is not Severity.ERROR:
            continue
        key = _key(diagnostic, project, after_includes)
        if had[key] > 0:
            had[key] -= 1
            continue
        fresh.append(found)
    return tuple(fresh)


def _key(diagnostic: Diagnostic, project: Path, includes: Sequence[str]) -> tuple[object, ...]:
    """What an error is counted as: its check, its severity and its place - never its wording
    where it has a place of its own.

    A message may name what else the project holds: the writers of a variable, in an order the
    reading sets, or a constant spelled nearly like the one a shape names. Once a file is gone
    the same error at the same place can read differently - two writers left of three name
    another pair, the near miss is no longer suggested - and keyed by its message, as
    :func:`~ddd.lsp.diagnostics.finding_identity` keys a finding for the editor, it would read
    as new: removing one of three writers, on the way to ending their conflict, would be refused
    for the conflict the other two still have.
    """
    return (diagnostic.check, diagnostic.severity, _place(diagnostic, project, includes))


def _place(diagnostic: Diagnostic, project: Path, includes: Sequence[str]) -> tuple[object, ...]:
    """Where :func:`_key` says an error is: the file and pointer of a placed finding; the entry
    it names for one on the root's own ``includes``; and for one on a whole file, or on no place
    at all, its message as well, since nothing narrower tells two of those apart. The first word
    of each says which of the four it is, so that no two of them can ever be taken for one.

    An entry is keyed by what it says rather than by its position, because removing one moves
    every later one up. The root's entries only: a sub-project keeps its own list, so its
    entries keep their places. And only an index ``includes`` reaches, since a shorter list
    cannot say which entry a finding names.

    For ddd's own checks that arm decides nothing where ``before`` comes from runs that were all
    analysed: the only findings they file at a root entry are the loader's, and a read that
    reports an error is never analysed, so such a ``before`` has no error at one, and an error at
    one afterwards is new whichever way it is keyed. It is right for an error an analysis files
    at an entry - a plugin's check may, and a later check of ddd's might - where a key by
    position would read the same error as new once an earlier entry went.

    One guard per statement: joined with ``and``, coverage.py records one branch for the whole
    condition, and a guard no test reached would pass the gate unexercised.
    """
    location = diagnostic.location
    if location is None:
        return ("nowhere", diagnostic.message)
    if not location.pointer:
        return ("file", location.path, diagnostic.message)
    place = ("at", location.path, location.pointer)
    if location.path != project:
        return place
    entry = _ENTRY.fullmatch(location.pointer)
    if entry is None:
        return place
    index = int(entry.group(1))
    if index >= len(includes):
        return place
    return ("entry", includes[index])
