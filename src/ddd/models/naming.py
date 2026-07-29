"""Contract for a naming convention: what a well formed variable name is made of.

A convention describes a name as an ordered sequence of *segments* separated by a fixed
string, and says for each segment what may appear there - either a controlled vocabulary of
tokens with their meanings, or a pattern. That shape is what makes the two things worth
having possible at all:

* a name can be **completed**, because at any position the tool knows the allowed tokens,
* a bad name can be **located**, because the tool knows which segment is at fault rather
  than only that the whole name failed to match some regular expression.

A single regular expression for the whole name could validate, but could neither complete nor
point.
"""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ddd.models.common import Identifier


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Token(_Frozen):
    """One allowed value of a segment, with what it stands for."""

    value: str = Field(min_length=1)
    description: str = ""

    @model_validator(mode="after")
    def _no_whitespace_inside(self) -> Token:
        """A token is one piece of an identifier, so it cannot contain a space.

        That it cannot contain the *separator* either is checked by the convention, which is
        the only thing that knows what the separator is.
        """
        if any(character.isspace() for character in self.value):
            msg = f"token '{self.value}' contains whitespace"
            raise ValueError(msg)
        return self


class Segment(_Frozen):
    """One position in a name.

    Either ``tokens`` or ``pattern`` has to be given: a segment with neither would accept
    anything, which is the same as not describing it at all.
    """

    name: Identifier
    """What this position means, used in messages and in the explanation of a name."""

    description: str = ""
    tokens: tuple[Token, ...] = ()
    """The controlled vocabulary of this position; completions come from here."""

    pattern: str | None = None
    """A regular expression for a free position, e.g. the descriptive part of a name."""

    optional: bool = False
    """A trailing position that a name may leave out."""

    repeatable: bool = False
    """The position may be filled more than once, e.g. a multi word descriptive part."""

    @model_validator(mode="after")
    def _describes_something(self) -> Segment:
        if not self.tokens and self.pattern is None:
            msg = f"segment '{self.name}' needs either tokens or a pattern"
            raise ValueError(msg)
        if self.tokens and self.pattern is not None:
            msg = f"segment '{self.name}' has both tokens and a pattern; use one"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _pattern_compiles(self) -> Segment:
        """A pattern is compiled while the file is read, not while a name is judged.

        Left to the first name, a typo in the expression would surface as a crash in the
        middle of a check run rather than as a located finding about the convention.
        """
        if self.pattern is not None:
            try:
                re.compile(self.pattern)
            except re.error as error:
                msg = f"segment '{self.name}' has an invalid pattern: {error}"
                raise ValueError(msg) from None
        return self

    @model_validator(mode="after")
    def _tokens_are_unique(self) -> Segment:
        seen: set[str] = set()
        for token in self.tokens:
            if token.value in seen:
                msg = f"segment '{self.name}' lists '{token.value}' twice"
                raise ValueError(msg)
            seen.add(token.value)
        return self

    @property
    def values(self) -> tuple[str, ...]:
        return tuple(token.value for token in self.tokens)

    def meaning_of(self, value: str) -> str:
        return next((t.description for t in self.tokens if t.value == value), "")


class NamingConvention(_Frozen):
    """The rules a variable name has to follow."""

    name: str = Field(min_length=1)
    description: str = ""

    separator: str = Field(default="_", min_length=1)
    """What joins the segments; also what a name is split on."""

    segments: Annotated[tuple[Segment, ...], Field(min_length=1)]

    case_sensitive: bool = True

    @model_validator(mode="after")
    def _optional_segments_come_last(self) -> NamingConvention:
        seen_optional = False
        for segment in self.segments:
            if segment.optional:
                seen_optional = True
            elif seen_optional:
                msg = (
                    f"segment '{segment.name}' is required but follows an optional one, so a "
                    f"name could not be split unambiguously"
                )
                raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _tokens_avoid_the_separator(self) -> NamingConvention:
        """A token containing the separator could never match.

        A name is split on the separator before its parts are judged, so such a token would
        be offered by the completion and rejected by the check - the tool contradicting
        itself. The rule lives here rather than on the token because only the convention
        knows what the separator is.
        """
        for segment in self.segments:
            for token in segment.tokens:
                if self.separator in token.value:
                    msg = (
                        f"token '{token.value}' of segment '{segment.name}' contains the "
                        f"separator '{self.separator}', so no name could ever match it"
                    )
                    raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _at_most_one_repeatable(self) -> NamingConvention:
        repeatable = [segment.name for segment in self.segments if segment.repeatable]
        if len(repeatable) > 1:
            msg = f"only one segment may be repeatable, got {', '.join(repeatable)}"
            raise ValueError(msg)
        return self

    @property
    def segment_names(self) -> tuple[str, ...]:
        return tuple(segment.name for segment in self.segments)


class NamingFile(_Frozen):
    """Root object of a ``*.ddd.json`` naming convention description."""

    naming: NamingConvention
