"""Conversions between the raw (implementation) and the physical value of a data object.

The four variants form a tagged union discriminated on ``kind``, and each one answers the
same three questions - the interface :class:`ConversionRule` spells out. It is a Protocol
rather than a base class because the variants are pydantic models whose only shared state is
their tag: inheritance would put a ``kind`` field where each variant needs its own literal.
"""

from __future__ import annotations

from collections.abc import Iterable
from math import isclose
from typing import Annotated, Any, Final, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from ddd.models.common import (
    C_IDENTIFIER_PATTERN,
    IDENTIFIER_MAX_LENGTH,
    Datatype,
    Identifier,
    Real,
    format_number,
)


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", use_attribute_docstrings=True)


@runtime_checkable
class ConversionRule(Protocol):
    """What every conversion variant can do, whatever its kind."""

    def to_physical(self, raw: float) -> float:
        """The physical value a raw value stands for."""
        ...

    def to_raw(self, physical: float) -> float:
        """The raw value needed to represent a physical one."""
        ...

    def describe(self) -> str:
        """A short phrase naming the rule, for diagnostics."""
        ...


ENUMERATOR_VALUE_MIN: Final = -(2**63)
ENUMERATOR_VALUE_MAX: Final = 2**64 - 1
"""What an enumerator's value is bounded to: what 64 bits hold, signed or unsigned.

Named rather than written twice because the mapping shorthand publishes its own value
schema (:func:`_publish_mapping_form`), and a bound the two forms disagreed about would be
exactly the drift that finding was about.
"""


class Enumerator(_Frozen):
    """One named value of an enum conversion, and what that value means."""

    name: Identifier
    """C identifier of the enumerator; enumerators of all enums share one c namespace."""

    value: Annotated[int, Field(strict=True, ge=ENUMERATOR_VALUE_MIN, le=ENUMERATOR_VALUE_MAX)]
    """The raw value; two enumerators of one enum sharing one is reported as a warning.

    ``enum-duplicate-value``, a warning rather than a refusal, because it is legal c and
    occasionally meant as an alias - but the a2l table then offers a calibration tool two
    names for one reading.

    Bounded to what 64 bits can hold - no datatype DDD offers stores more - so a value no
    storage could ever represent is refused here rather than overflowing a comparison once
    it is checked against the c ``int`` every enumerator has to fit, or against the
    datatype carrying it.

    A whole number written without a decimal point: ``4``, not ``4.0``, which the published
    schema accepts and the loader refuses.
    """

    description: str = ""
    """What the value means; documentation, not interface."""


class IdentityConversion(_Frozen):
    """``physical == raw``; stated like any other conversion, ``{}`` its shortest spelling.

    Not a default: a definition naming storage by ``datatype`` states this one where raw and
    physical are the same number, so that the claim is written down rather than left to
    silence.
    """

    kind: Literal["identity"] = "identity"
    """The tag of this kind, which may be left out: an empty block is the identity."""

    def to_physical(self, raw: float) -> float:
        return raw

    def to_raw(self, physical: float) -> float:
        return physical

    def describe(self) -> str:
        return "identity"


class LinearConversion(_Frozen):
    """``physical = raw * factor + offset``, the scaling of a fixed point value."""

    kind: Literal["linear"] = "linear"
    """The tag of this kind, which may be left out: a block stating ``factor`` or ``offset``
    is linear."""

    factor: Real = 1.0
    """Scaling; must not be zero, or nothing could be converted back."""

    offset: Real = 0.0
    """What raw zero stands for, in the physical unit."""

    @model_validator(mode="after")
    def _factor_not_zero(self) -> LinearConversion:
        if self.factor == 0.0:
            msg = "factor must not be zero"
            raise ValueError(msg)
        return self

    def to_physical(self, raw: float) -> float:
        return raw * self.factor + self.offset

    def to_raw(self, physical: float) -> float:
        return (physical - self.offset) / self.factor

    def describe(self) -> str:
        return f"linear(factor={format_number(self.factor)}, offset={format_number(self.offset)})"


def _publish_mapping_form(schema: dict[str, Any]) -> None:
    """Let the schema accept the mapping ``_expand_mapping`` turns into the list.

    The list is what the model holds, so it is what pydantic publishes; the shorthand is what
    the loader accepts, so an editor validating a file has to accept it as well.

    With the rules each half of an entry is held to, which the list form publishes through
    :class:`Enumerator` and this one used to leave out: a key is a c identifier and a value
    is a number 64 bits hold, so ``{"1bad": 0}`` and a value past the bound were accepted by
    an editor bound to the schema and refused by ``ddd check``.
    """
    listed = {key: schema.pop(key) for key in ("type", "items", "minItems") if key in schema}
    schema["anyOf"] = [
        listed,
        {
            "type": "object",
            "propertyNames": {
                "pattern": C_IDENTIFIER_PATTERN,
                "minLength": 1,
                "maxLength": IDENTIFIER_MAX_LENGTH,
            },
            "additionalProperties": {
                "type": "integer",
                "minimum": ENUMERATOR_VALUE_MIN,
                "maximum": ENUMERATOR_VALUE_MAX,
            },
            "minProperties": 1,
            "description": 'The enumerators as a ``{"NAME": value}`` mapping.',
        },
    ]


class EnumConversion(_Frozen):
    """A verbal conversion table; the raw value *is* the physical value.

    Accepts both the explicit form::

        {"kind": "enum", "name": "StateA",
         "enumerators": [{"name": "STATE_OFF", "value": 0}]}

    and the mapping shorthand::

        {"kind": "enum", "name": "StateA", "enumerators": {"STATE_OFF": 0}}
    """

    kind: Literal["enum"] = "enum"
    """The tag of this kind, which may be left out: a block stating ``enumerators`` or a
    ``name`` is an enum."""

    name: Identifier
    """C identifier of the generated ``typedef enum``; shared enums must agree everywhere."""

    enumerators: Annotated[
        tuple[Enumerator, ...], Field(min_length=1, json_schema_extra=_publish_mapping_form)
    ]
    """The named values, either as objects or as a ``{"NAME": value}`` mapping.

    Two of them may not carry the same name, which the mapping form cannot express twice and
    the list form can: the generated enumeration would not compile, and a calibration tool
    reading the generated table of labels would have two answers for one. Two names sharing a
    *value* is a different matter - it is the C idiom for an alias, reported as
    ``enum-duplicate-value`` rather than refused.
    """

    @model_validator(mode="before")
    @classmethod
    def _expand_mapping(cls, data: Any) -> Any:
        if isinstance(data, dict):
            enumerators = data.get("enumerators")
            if isinstance(enumerators, dict):
                data = dict(data)
                data["enumerators"] = [
                    {"name": name, "value": value} for name, value in enumerators.items()
                ]
        return data

    @model_validator(mode="after")
    def _unique_names(self) -> EnumConversion:
        seen: set[str] = set()
        for enumerator in self.enumerators:
            if enumerator.name in seen:
                msg = f"duplicate enumerator name '{enumerator.name}'"
                raise ValueError(msg)
            seen.add(enumerator.name)
        return self

    @property
    def values(self) -> tuple[int, ...]:
        return tuple(enumerator.value for enumerator in self.enumerators)

    def spell_enumerators(self, entries: Iterable[Enumerator] | None = None) -> str:
        """``NAME=value`` pairs in written order: every enumerator, or the ones handed in.

        The one spelling of the three findings that quote enumerators - ``enum-conflict``
        inside a project, the delivery comparison across two, and the ``init-invalid`` that
        names the enumerators outside a datatype, which passes the subset - so that a reader
        meets the same list wherever an enumeration is quoted.
        """
        listed = self.enumerators if entries is None else entries
        return ", ".join(f"{entry.name}={entry.value}" for entry in listed)

    def to_physical(self, raw: float) -> float:
        return raw

    def to_raw(self, physical: float) -> float:
        return physical

    def describe(self) -> str:
        return f"enum({self.name})"


class StringConversion(_Frozen):
    """Bytes read as text: each element of the array holds one character code.

    Stated on a ``uint8`` or ``sint8`` array of one dimension; the rules sit beside the
    datatype because the same pair is written in three places. ``kind`` is required here,
    unlike on the other three kinds: a string has no key of its own to be inferred from,
    and ``{}`` is the identity.

    The two mappings are the identity on one byte, so that the derived limits of a string
    are the raw range of its datatype - which is what the a2l record states - and nothing
    that ranges a conversion has to know that a string exists. A byte has no reading of its
    own, so no reading is produced for it, as for the identity.
    """

    kind: Literal["string"]
    """The tag of this kind, which is required: a string has no key of its own to be
    recognised by, so nothing else would tell it from the identity."""

    def to_physical(self, raw: float) -> float:
        return raw

    def to_raw(self, physical: float) -> float:
        return physical

    def describe(self) -> str:
        return "string"


def _infer_kind(data: Any) -> Any:
    """Allow ``kind`` to be omitted when the shape of the object is unambiguous."""
    if isinstance(data, dict) and "kind" not in data:
        data = dict(data)
        if "enumerators" in data or "name" in data:
            data["kind"] = "enum"
        elif "factor" in data or "offset" in data:
            data["kind"] = "linear"
        else:
            data["kind"] = "identity"
    return data


Conversion = Annotated[
    IdentityConversion | LinearConversion | EnumConversion | StringConversion,
    Field(discriminator="kind"),
    BeforeValidator(_infer_kind),
]
"""Raw to physical conversion; ``kind`` may be omitted when the shape is unambiguous, which
a string never is."""

IDENTITY = IdentityConversion()


def conversion_identity(conversion: Conversion) -> object:
    """What two spellings of one conversion have to agree on to be the same conversion.

    An enumerator's ``description`` is documentation, not interface: the two spellings the
    file format offers - the mapping shorthand and the list of objects - cannot even carry
    the same text, and two conversions differing only in it mean the same mapping. The
    ordered name and value pairs do count, exactly as ``enum-conflict`` counts them, and
    everything else compares as written, because ``linear`` with factor 1 is deliberately
    not the identity. This is what a delivery comparison compares and what ``enum-conflict``
    holds two declarations of one enum to; the in-project interface table narrows an enum to
    its name instead (:func:`conversion_interface_value`), the enumerators being
    ``enum-conflict``'s there.
    """
    if isinstance(conversion, EnumConversion):
        return (
            "enum",
            conversion.name,
            tuple((entry.name, entry.value) for entry in conversion.enumerators),
        )
    return conversion.model_dump(mode="json")


def conversion_interface_value(conversion: Conversion) -> object:
    """What two declarations of one object, within a project, have to agree on about a conversion.

    An identity or a linear conversion is compared in full, by :func:`conversion_identity` -
    kind and parameters both, completed the way the models complete them: ``{"factor": 2}``
    and ``{"kind": "linear", "factor": 2, "offset": 0}`` agree. An enum narrows to its name
    alone: the enumerators, descriptions included, are ``enum-conflict``'s to agree on, and
    folding them in here as well would turn one mistake into two findings - the second of
    which cannot even say what it means, because a definition explains itself by calling
    :meth:`EnumConversion.describe`, which names the enum and nothing else, so a reordered or
    revalued enumerator used to print identical text on both sides of the mismatch.

    Used by :func:`ddd.analysis._conversion_value` for ``definition-mismatch``, and by
    :mod:`ddd.variable_keys` to decide which declarations of a variable already agree about a
    conversion before the panel of ``ddd gui`` offers to settle it - the checker and the panel
    must not disagree about what counts as one conversion.
    """
    if isinstance(conversion, EnumConversion):
        return ("enum", conversion.name)
    return conversion_identity(conversion)


SIGNIFICANT_DIGITS: Final = 12
"""How many digits of a computed physical value are the value rather than the arithmetic.

A decimal factor has no exact binary float, so the product of a raw end and a factor carries a
tail that belongs to the arithmetic and not to the number anybody wrote: 255 counts of 0.03
compute as ``7.6499999999999995``, and 32767 of 0.1 as ``3276.7000000000003``. Twelve digits
erase that tail while a genuinely long value still shows itself as approximate - the width
:func:`raw_reading` has always spelled a reading at, used here so that a limit and a reading
of the same raw count are the same number."""


def round_physical(value: float) -> float:
    """One computed physical value, with the tail of the arithmetic taken off it.

    A whole number passes through untouched, because there is no tail to take off one and
    making it a float would cost digits rather than save them: the identity hands back the raw
    count it was given, and the largest ``uint64`` count is exact as an ``int`` and wrong by
    one as a ``float``. Only a linear conversion multiplies, and its factor is always a float,
    so everything this has to round arrives as one.

    Infinities and NaN pass through as well: ``f"{inf:.12g}"`` is ``inf``, which reads back as
    itself, so the callers that ask whether a derived range stayed finite still get an answer.
    """
    if isinstance(value, int):
        return value
    return float(f"{value:.{SIGNIFICANT_DIGITS}g}")


RELATIVE_TOLERANCE: Final = 1e-9
"""How close two physical values have to be before the difference is the arithmetic's.

Wide enough to absorb the rounding above and the float a decimal literal parses to, narrow
enough that a limit anybody stated on purpose is still a different number."""


def is_below(value: float, limit: float) -> bool:
    """Whether ``value`` is under ``limit`` by more than the arithmetic could account for.

    The one tolerance the tool weighs a derived limit with, in the two places that weigh one:
    :mod:`ddd.analysis`, deciding whether stated limits exceed what a datatype and conversion
    can represent, and :mod:`ddd.compare`, deciding whether a candidate narrowed them. Both
    compare a number somebody wrote against a number this module computed, and computing it
    goes through a float: ``7.65`` typed by hand is not bit for bit the ``7.65`` that 255
    counts of 0.03 produce, however each of them is rounded. A relative tolerance is what
    makes the two the same number, and having one spelling of it is what keeps the check that
    reports narrowing and the check that reports an impossible limit from disagreeing about
    which values are equal.
    """
    return value < limit and not isclose(value, limit, rel_tol=RELATIVE_TOLERANCE, abs_tol=0.0)


def is_above(value: float, limit: float) -> bool:
    """Whether ``value`` is over ``limit`` by more than the arithmetic could account for."""
    return value > limit and not isclose(value, limit, rel_tol=RELATIVE_TOLERANCE, abs_tol=0.0)


def physical_range(conversion: Conversion, raw_min: float, raw_max: float) -> tuple[float, float]:
    """The physical range a raw range covers, in the order a reader expects.

    Takes the raw ends rather than a datatype, because they do not always come from one: a
    bitfield's ends come from its width, and offering a two bit field over the whole range of
    the ``uint16`` carrying it would be an invitation to enter a value it cannot hold.

    Both ends are rounded the way :func:`raw_reading` rounds a reading, and for the same
    reason: the range is written into the A2L and into the dumped dictionary, where a
    calibration tool enforces it and an engineer reads it. Unrounded, a ``uint8`` under
    ``{"factor": 0.03}`` stated an upper limit of ``7.6499999999999995`` - below the physical
    value of its own largest raw count - and a tool holding data to the limits it reads
    refused the value the description implies.
    """
    if isinstance(conversion, EnumConversion):
        values = conversion.values
        return float(min(values)), float(max(values))
    low = round_physical(conversion.to_physical(raw_min))
    high = round_physical(conversion.to_physical(raw_max))
    return (low, high) if low <= high else (high, low)


def conversion_range(conversion: Conversion, datatype: Datatype) -> tuple[float, float]:
    """The physical range covered by the full raw range of ``datatype``."""
    return physical_range(conversion, datatype.raw_min, datatype.raw_max)


def raw_reading(conversion: Conversion, raw: float, unit: str = "") -> str | None:
    """What one raw value reads as, or ``None`` where the raw value already says it.

    The forward direction only, which is always defined: every raw value has exactly one
    physical image under a linear conversion, while most physical values are the image of no
    raw count at all. Under the identity the physical value *is* the raw one, and an enum
    names only the values of its table - both answer ``None`` rather than repeat the number
    they were given. The unit rides along on a linear reading because the physical value is
    the one it belongs to; an enumerator name carries no unit.

    The reading is rounded the way a derived limit is, to :data:`SIGNIFICANT_DIGITS` digits.
    A decimal factor has no exact binary float, so 3 raw counts of 0.1 compute as
    0.30000000000000004 - an artifact of the arithmetic, not part of the reading. Twelve
    digits erase it while a genuinely long value still shows itself as approximate.
    """
    if isinstance(conversion, LinearConversion):
        return f"{format_number(round_physical(conversion.to_physical(raw)))} {unit}".rstrip()
    if isinstance(conversion, EnumConversion):
        return next((item.name for item in conversion.enumerators if item.value == raw), None)
    return None
