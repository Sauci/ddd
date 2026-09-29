"""What a change of the root project's ``includes`` would break, as the analysis itself says.

Transport-neutral, like :mod:`ddd.shared_plans`: nothing here knows about http or the session,
and nothing here imports :mod:`ddd.gui`. It is for the gui to call and never calls the gui, so
findings arrive as ``(path, diagnostic)`` pairs - the shape
:func:`ddd.project_shared.shared_rows` takes for the same reason - rather than as the session's
own ``Filed``.

No rule here says which kinds of file a project may do without. :func:`new_errors` compares the
errors of two analyses of one project, the second with the root's list changed, so what breaks
is whatever the checks say breaks, and a check added later is weighed without anyone
remembering this module exists.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from ddd.diagnostics import Diagnostic, Severity
from ddd.lsp.diagnostics import finding_identity

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
    """The errors ``after`` has that ``before`` does not, in ``after``'s order: what a change of
    the root's ``includes`` would break.

    ``before`` is what the project reports with ``before_includes`` as its root's list, and
    ``after`` what it reports with ``after_includes``; ``project`` is the root's own file.

    Errors only, after each run's severity policy: the line ``ddd check`` draws between a
    project that passes and one that fails. A warning a change brings is for the reader to see
    once it is made, not a reason to call the change breaking.

    ``before`` is read whole, whatever the severity: every key carries its finding's, so only an
    error the project has now can match an error of ``after``, and a filter there would change
    what is held without changing the answer. The filter on ``after`` is a statement in a loop
    rather than a comprehension's, which coverage.py counts no branch in.
    """
    had = {_key(diagnostic, project, before_includes) for _, diagnostic in before}
    fresh: list[Pair] = []
    for found in after:
        _, diagnostic = found
        if diagnostic.severity is not Severity.ERROR:
            continue
        if _key(diagnostic, project, after_includes) in had:
            continue
        fresh.append(found)
    return tuple(fresh)


def _key(diagnostic: Diagnostic, project: Path, includes: Sequence[str]) -> tuple[object, ...]:
    """What makes two findings the same one across a change of ``includes``:
    :func:`ddd.lsp.diagnostics.finding_identity`, save that a finding on one of the root's own
    entries is keyed by the entry it names rather than by its position - removing an entry moves
    every later one up, and the same finding would otherwise read as new.

    The root's entries only: a sub-project keeps its own list, so its entries keep their places.
    And only an index ``includes`` reaches, since a shorter list cannot say which entry a
    finding names.

    One guard per statement, each answering the finding's own identity: joined with ``and``,
    coverage.py records one branch for the whole condition, and a guard no test reached would
    pass the gate unexercised.
    """
    identity = finding_identity(diagnostic)
    location = diagnostic.location
    if location is None:
        return identity
    if location.path != project:
        return identity
    entry = _ENTRY.fullmatch(location.pointer)
    if entry is None:
        return identity
    index = int(entry.group(1))
    if index >= len(includes):
        return identity
    return (diagnostic.check, diagnostic.severity, includes[index], diagnostic.message)
