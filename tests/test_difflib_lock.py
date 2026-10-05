"""``ddd.difflib_lock``: each of ddd's three calls into difflib is made holding the one lock, for
itself alone, and lets it go as it returns.

Recorded, not raced: difflib's own ``SequenceMatcher`` and ``get_close_matches`` are wrapped so
that each notes whether the lock is held as it is called. No thread is started and nothing waits.
"""

from __future__ import annotations

import difflib
from collections.abc import Iterator
from typing import Any

import pytest

from ddd import analysis
from ddd.analysis import close_units
from ddd.difflib_lock import ONE_THREAD_IN_DIFFLIB
from ddd.variables import Hunk, hunks


def recorded(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, bool]]:
    """Every matcher made and every ``ratio()``, ``get_opcodes()`` and ``get_close_matches``
    asked from now on, in order, each with whether the lock was held as it was."""
    held: list[tuple[str, bool]] = []
    matcher = difflib.SequenceMatcher
    close = difflib.get_close_matches

    class Recording(matcher):
        def __init__(self, *arguments: Any, **keywords: Any) -> None:
            held.append(("made", ONE_THREAD_IN_DIFFLIB.locked()))
            super().__init__(*arguments, **keywords)

        def ratio(self) -> float:
            held.append(("ratio", ONE_THREAD_IN_DIFFLIB.locked()))
            return super().ratio()

        def get_opcodes(self) -> list[tuple[str, int, int, int, int]]:
            held.append(("get_opcodes", ONE_THREAD_IN_DIFFLIB.locked()))
            return super().get_opcodes()

    def recording(*arguments: Any, **keywords: Any) -> list[str]:
        held.append(("get_close_matches", ONE_THREAD_IN_DIFFLIB.locked()))
        return close(*arguments, **keywords)

    monkeypatch.setattr(difflib, "SequenceMatcher", Recording)
    monkeypatch.setattr(difflib, "get_close_matches", recording)
    return held


class Vocabulary(tuple[str, ...]):
    """Spellings that note whether the lock is held each time one of them is taken."""

    def __new__(cls, *spellings: str) -> Vocabulary:
        made = super().__new__(cls, spellings)
        made.taken = []
        return made

    taken: list[bool]

    def __iter__(self) -> Iterator[str]:
        for spelling in super().__iter__():
            self.taken.append(ONE_THREAD_IN_DIFFLIB.locked())
            yield spelling


def test_a_unit_is_compared_with_each_spelling_holding_the_lock_and_lets_it_go_between(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One ``ratio()`` at a time: the lock is free each time the next spelling is taken, never
    held through the whole vocabulary."""
    held = recorded(monkeypatch)
    spellings = Vocabulary("Nm", "rpm", "rps")
    assert close_units("rpms", spellings) == ("rpm", "rps")
    assert held == [("made", True), ("ratio", True)] * 3
    assert spellings.taken == [False, False, False]
    assert not ONE_THREAD_IN_DIFFLIB.locked()


def test_a_name_is_suggested_holding_the_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    """``get_close_matches`` makes and asks a matcher of its own for each candidate: all of it
    inside the one call, and the lock let go once it returns."""
    held = recorded(monkeypatch)
    assert analysis._did_you_mean("rmp", ("Nm", "rpm"), cutoff=0.5) == " - did you mean 'rpm'?"
    assert held[0] == ("get_close_matches", True)
    assert ("ratio", True) in held
    assert all(locked for _, locked in held)
    assert not ONE_THREAD_IN_DIFFLIB.locked()


def test_the_lines_a_change_replaces_are_diffed_holding_the_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The matcher made and its opcodes read in one hold, the hunks made from them after it."""
    held = recorded(monkeypatch)
    assert hunks("A\nB\nC\n", "A\nC\n") == (Hunk(2, ("B",), ()),)
    assert held == [("made", True), ("get_opcodes", True)]
    assert not ONE_THREAD_IN_DIFFLIB.locked()
