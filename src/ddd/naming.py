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
    canonical: str | None = None
    """The token this part matched, as the convention spells it.

    Only differs from ``text`` under a case insensitive convention, and exists so that the
    meaning of a token is still found when the author typed it in another case.
    """

    @property
    def ok(self) -> bool:
        return self.problem is None

    @property
    def meaning(self) -> str:
        if self.segment is None:
            return ""
        return self.segment.meaning_of(self.canonical or self.text)


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
    plan, missing = _best_plan(texts, convention)
    return Inspection(
        name=name,
        convention=convention,
        parts=tuple(_judge_all(texts, plan, convention)),
        missing=missing,
    )


def explain(name: str, convention: NamingConvention) -> Inspection:
    """Alias of :func:`inspect`, for the reading rather than the judging use."""
    return inspect(name, convention)


def complete(prefix: str, convention: NamingConvention) -> list[str]:
    """The names that ``prefix`` could grow into, one segment further.

    A prefix ending in the separator asks for the next segment; otherwise the last piece is
    treated as partially typed and filtered on. Only positions that are reachable *given the
    parts already typed* are offered, so a completion never proposes a name the same
    convention would then reject.

    A free (pattern) position has no vocabulary of its own. Once what stands there is
    acceptable, the offer moves on to what may follow it, which is what makes
    ``val_Inlet<TAB>`` propose the qualifiers rather than nothing at all.
    """
    ends_open = prefix.endswith(convention.separator)
    head = prefix[: -len(convention.separator)] if ends_open else prefix
    pieces = _split(head, convention) if head else []
    typed = "" if ends_open else (pieces.pop() if pieces else "")

    stem = convention.separator.join([*pieces, ""]) if pieces else ""
    matcher = _fold(typed, convention)
    here = [
        value
        for value in _vocabulary_at(pieces, convention)
        if _fold(value, convention).startswith(matcher)
    ]
    if here:
        # The token is offered as the convention spells it, which under a case insensitive
        # convention also teaches the canonical spelling of what was typed.
        return [f"{stem}{value}" for value in here]

    if typed and _accepts(pieces, typed, convention):
        separator = convention.separator
        return [
            f"{stem}{typed}{separator}{value}"
            for value in _vocabulary_at([*pieces, typed], convention)
        ]
    return []


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
                message += f" - did you mean {or_list(part.suggestions)}?"
            bag.add("naming", message, location, notes=[(inspection.underline(), None)])
        for segment in inspection.missing:
            bag.add(
                "naming",
                f"'{name}' stops before the {segment.name} part, which "
                f"'{convention.name}' requires",
                location,
            )


def or_list(values: tuple[str, ...]) -> str:
    """``'val' or 'flg'``: the quotes are presentation, so they are added at the end."""
    return " or ".join(f"'{value}'" for value in values)


def _split(name: str, convention: NamingConvention) -> list[str]:
    return name.split(convention.separator) if name else []


def _layouts(count: int, convention: NamingConvention) -> list[list[Segment]]:
    """Every way the convention can spread exactly ``count`` parts over its segments.

    Two things vary: how many of the trailing optional segments a name uses, and how many
    parts the repeatable one swallows. Both are enumerated instead of decided in advance,
    because deciding greedily gets ``val_Inlet_Temperature`` wrong - the last subject is
    handed to the qualifier, which then rejects a name the convention allows. The caller
    keeps the layout the name actually fits.

    Layouts with more optional segments come first, so that when a part could be read either
    as a vocabulary token or as free text, the vocabulary wins and the explanation of the
    name says what it means.
    """
    required = [segment for segment in convention.segments if not segment.optional]
    optional = [segment for segment in convention.segments if segment.optional]

    layouts: list[list[Segment]] = []
    for used in range(len(optional), -1, -1):
        included = required + optional[:used]
        position = next((i for i, s in enumerate(included) if s.repeatable), None)
        if position is None:
            if len(included) == count:
                layouts.append(included)
            continue
        stretch = count - len(included) + 1
        if stretch >= 1:
            repeated = [included[position]] * stretch
            layouts.append(included[:position] + repeated + included[position + 1 :])
    return layouts


def _judge_all(texts: list[str], plan: list[Segment], convention: NamingConvention) -> list[Part]:
    parts: list[Part] = []
    offset = 0
    for index, text in enumerate(texts):
        segment = plan[index] if index < len(plan) else None
        parts.append(_judge(text, offset, segment, convention))
        offset += len(text) + len(convention.separator)
    return parts


def _best_plan(
    texts: list[str], convention: NamingConvention
) -> tuple[list[Segment], tuple[Segment, ...]]:
    """The layout that fits ``texts``, or the one that explains best why none does."""
    best: tuple[int, list[Segment]] | None = None
    for plan in _layouts(len(texts), convention):
        problems = sum(1 for part in _judge_all(texts, plan, convention) if not part.ok)
        if problems == 0:
            return plan, ()
        if best is None or problems < best[0]:
            best = (problems, plan)
    if best is not None:
        return best[1], ()

    # The name is too short for any layout: report the required segments it stops before.
    # A repeatable segment still has to appear at least once - "repeatable" widens how many
    # parts it may take, it does not make it optional.
    required = [segment for segment in convention.segments if not segment.optional]
    return required[: len(texts)], tuple(required[len(texts) :])


def _vocabulary_at(pieces: list[str], convention: NamingConvention) -> list[str]:
    """The tokens that may stand after ``pieces``, under every layout they still fit."""
    index = len(pieces)
    values: list[str] = []
    seen: set[str] = set()
    for count in range(index + 1, index + 1 + len(convention.segments)):
        for plan in _layouts(count, convention):
            if not _fits(pieces, plan, convention):
                continue
            for value in plan[index].values:
                if value not in seen:
                    seen.add(value)
                    values.append(value)
    return values


def _fits(pieces: list[str], plan: list[Segment], convention: NamingConvention) -> bool:
    """Whether the already typed parts are all acceptable under ``plan``."""
    return all(part.ok for part in _judge_all(pieces, plan, convention))


def _accepts(pieces: list[str], text: str, convention: NamingConvention) -> bool:
    """Whether ``text`` is acceptable right after ``pieces`` under some layout."""
    candidate = [*pieces, text]
    return any(
        _fits(candidate, plan, convention)
        for count in range(len(candidate), len(candidate) + len(convention.segments))
        for plan in _layouts(count, convention)
    )


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
    folded = {_fold(value, convention): value for value in values}
    matched = folded.get(_fold(text, convention))
    if matched is not None:
        return Part(text, offset, segment, canonical=matched)
    return Part(
        text,
        offset,
        segment,
        problem=f"'{text}' is not a known {segment.name} ({_listing(values)})",
        suggestions=_closest(text, values, convention),
    )


def _closest(text: str, values: tuple[str, ...], convention: NamingConvention) -> tuple[str, ...]:
    """The tokens closest to what was typed, as bare values.

    Unquoted on purpose: this is data, and the json output carries it verbatim. The quotes
    belong to the sentence the text renderer builds around it.
    """
    folded = {_fold(value, convention): value for value in values}
    matches = difflib.get_close_matches(
        _fold(text, convention), folded, n=_MAX_SUGGESTIONS, cutoff=0.6
    )
    return tuple(folded[match] for match in matches)


def _listing(values: tuple[str, ...], limit: int = 8) -> str:
    shown = ", ".join(values[:limit])
    return shown if len(values) <= limit else f"{shown}, ... ({len(values)} in total)"


def _fold(text: str, convention: NamingConvention) -> str:
    return text if convention.case_sensitive else text.lower()
