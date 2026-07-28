"""Validating, explaining and completing variable names against a naming convention.

Three jobs, one walk over the segments:

* :func:`inspect` splits a name and says, per segment, whether it belongs there. It reports
  the *position* of the offending part, so a message can underline it rather than shrug at
  the whole name.
* :func:`explain` turns a well formed name into what each of its parts means, which is what
  makes an unfamiliar label readable.
* :func:`complete` lists what may come next after a partially typed name, which is what a
  shell completion needs.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

from ddd.diagnostics import DiagnosticBag, Location
from ddd.models.naming import NamingConvention, Segment

_MAX_SUGGESTIONS = 3


@dataclass(frozen=True, slots=True)
class Part:
    """One piece of a name, and the verdict on it."""

    text: str
    start: int
    """Offset of this piece in the whole name, so a caret can be put under it."""

    segment: Segment | None
    """The position it was checked against; ``None`` when the name has more parts than the
    convention describes."""

    problem: str | None = None
    suggestions: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.problem is None

    @property
    def meaning(self) -> str:
        if self.segment is None:
            return ""
        return self.segment.meaning_of(self.text)


@dataclass(frozen=True, slots=True)
class Inspection:
    """What a convention makes of one name."""

    name: str
    convention: NamingConvention
    parts: tuple[Part, ...] = ()
    missing: tuple[Segment, ...] = ()
    """Required positions the name stops short of."""

    @property
    def ok(self) -> bool:
        return not self.missing and all(part.ok for part in self.parts)

    @property
    def problems(self) -> tuple[Part, ...]:
        return tuple(part for part in self.parts if not part.ok)

    def underline(self) -> str:
        """The name with carets under the parts that are wrong.

        This is the whole point of splitting into segments: a rejected name shows *where* it
        is wrong, not merely that it is.
        """
        marks = [" "] * len(self.name)
        for part in self.problems:
            for offset in range(part.start, min(part.start + len(part.text), len(self.name))):
                marks[offset] = "^"
        return f"{self.name}\n{''.join(marks).rstrip()}"


def inspect(name: str, convention: NamingConvention) -> Inspection:
    """Split ``name`` and judge every part against the segment at its position."""
    texts = _split(name, convention)
    plan = _positions(len(texts), convention)

    parts: list[Part] = []
    offset = 0
    for index, text in enumerate(texts):
        segment = plan[index] if index < len(plan) else None
        parts.append(_judge(text, offset, segment, convention))
        offset += len(text) + len(convention.separator)

    # A repeatable segment still has to appear at least once: "repeatable" widens how many
    # parts it may take, it does not make it optional.
    required = [segment for segment in convention.segments[len(plan) :] if not segment.optional]
    return Inspection(name=name, convention=convention, parts=tuple(parts), missing=tuple(required))


def explain(name: str, convention: NamingConvention) -> Inspection:
    """Alias of :func:`inspect`, for the reading rather than the judging use."""
    return inspect(name, convention)


def complete(prefix: str, convention: NamingConvention) -> list[str]:
    """The names that ``prefix`` could grow into, one segment further.

    A prefix ending in the separator asks for the next segment; otherwise the last piece is
    treated as partially typed and filtered on. A free (pattern) segment has nothing to offer,
    so the result is empty - the caller keeps typing.
    """
    ends_open = prefix.endswith(convention.separator)
    head = prefix[: -len(convention.separator)] if ends_open else prefix
    pieces = _split(head, convention) if head else []
    typed = "" if ends_open else (pieces.pop() if pieces else "")

    index = len(pieces)
    plan = _positions(index + 1, convention)
    if index >= len(plan):
        return []
    segment = plan[index]

    stem = convention.separator.join([*pieces, ""]) if pieces else ""
    matcher = _fold(typed, convention)
    candidates = [value for value in segment.values if _fold(value, convention).startswith(matcher)]
    return [f"{stem}{value}" for value in candidates]


def check_names(
    names: dict[str, Location | None], convention: NamingConvention, bag: DiagnosticBag
) -> None:
    """Report every name that the convention rejects, pointing at the offending part."""
    for name, location in names.items():
        inspection = inspect(name, convention)
        if inspection.ok:
            continue
        for part in inspection.problems:
            message = part.problem or ""
            if part.suggestions:
                message += f" - did you mean {' or '.join(part.suggestions)}?"
            bag.add("naming", message, location, notes=[(inspection.underline(), None)])
        for segment in inspection.missing:
            bag.add(
                "naming",
                f"'{name}' stops before the {segment.name} part, which "
                f"'{convention.name}' requires",
                location,
            )


# -- the walk ---------------------------------------------------------------


def _split(name: str, convention: NamingConvention) -> list[str]:
    return name.split(convention.separator) if name else []


def _positions(count: int, convention: NamingConvention) -> list[Segment]:
    """The segment that governs each of ``count`` positions.

    A repeatable segment stretches to swallow the pieces the fixed ones do not need, which is
    how a convention allows a multi word descriptive part without listing every length.
    """
    segments = list(convention.segments)
    repeatable = next((s for s in segments if s.repeatable), None)
    if repeatable is None:
        return segments[:count]

    index = segments.index(repeatable)
    after = len(segments) - index - 1
    stretch = max(1, count - index - after)
    plan = segments[:index] + [repeatable] * stretch + segments[index + 1 :]
    return plan[:count]


def _judge(text: str, offset: int, segment: Segment | None, convention: NamingConvention) -> Part:
    if segment is None:
        return Part(
            text=text,
            start=offset,
            segment=None,
            problem=(
                f"'{text}' is one part too many; the convention "
                f"'{convention.name}' ends after {convention.segment_names[-1]}"
            ),
        )
    if not text:
        return Part(text, offset, segment, problem=f"the {segment.name} part is empty")

    if segment.pattern is not None:
        if re.fullmatch(segment.pattern, text) is None:
            return Part(
                text,
                offset,
                segment,
                problem=(f"'{text}' does not match the {segment.name} pattern {segment.pattern}"),
            )
        return Part(text, offset, segment)

    values = segment.values
    if _fold(text, convention) in {_fold(value, convention) for value in values}:
        return Part(text, offset, segment)
    return Part(
        text,
        offset,
        segment,
        problem=f"'{text}' is not a known {segment.name} ({_listing(values)})",
        suggestions=_closest(text, values, convention),
    )


def _closest(text: str, values: tuple[str, ...], convention: NamingConvention) -> tuple[str, ...]:
    folded = {_fold(value, convention): value for value in values}
    matches = difflib.get_close_matches(
        _fold(text, convention), folded, n=_MAX_SUGGESTIONS, cutoff=0.6
    )
    return tuple(f"'{folded[match]}'" for match in matches)


def _listing(values: tuple[str, ...], limit: int = 8) -> str:
    shown = ", ".join(values[:limit])
    return shown if len(values) <= limit else f"{shown}, ... ({len(values)} in total)"


def _fold(text: str, convention: NamingConvention) -> str:
    return text if convention.case_sensitive else text.lower()
