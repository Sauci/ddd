"""Conversions between the raw (implementation) and the physical value of a data object.

The three variants form a tagged union discriminated on ``kind``, and each one answers the
same three questions - the interface :class:`ConversionRule` spells out. It is a Protocol
rather than a base class because the variants are pydantic models whose only shared state is
their tag: inheritance would put a ``kind`` field where each variant needs its own literal.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from ddd.models.common import Datatype, Identifier, Real, format_number


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


class Enumerator(_Frozen):
    """One named value of an enum conversion, and what that value means."""

    name: Identifier
    """C identifier of the enumerator; enumerators of all enums share one c namespace."""

    value: int
    """The raw value; every enumerator of one enum needs a value of its own."""

    description: str = ""
    """What the value means; documentation, not interface."""


class IdentityConversion(_Frozen):
    """``physical == raw``; the default for every variable."""

    kind: Literal["identity"] = "identity"

    def to_physical(self, raw: float) -> float:
        return raw

    def to_raw(self, physical: float) -> float:
        return physical

    def describe(self) -> str:
        return "identity"


class LinearConversion(_Frozen):
    """``physical = raw * factor + offset``, the scaling of a fixed point value."""

    kind: Literal["linear"] = "linear"
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


class EnumConversion(_Frozen):
    """A verbal conversion table; the raw value *is* the physical value.

    Accepts both the explicit form::

        {"kind": "enum", "name": "StateA",
         "enumerators": [{"name": "STATE_OFF", "value": 0}]}

    and the mapping shorthand::

        {"kind": "enum", "name": "StateA", "enumerators": {"STATE_OFF": 0}}
    """

    kind: Literal["enum"] = "enum"
    name: Identifier
    """C identifier of the generated ``typedef enum``; shared enums must agree everywhere."""

    enumerators: Annotated[tuple[Enumerator, ...], Field(min_length=1)]
    """The named values, either as objects or as a ``{"NAME": value}`` mapping."""

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

    def to_physical(self, raw: float) -> float:
        return raw

    def to_raw(self, physical: float) -> float:
        return physical

    def describe(self) -> str:
        return f"enum({self.name})"


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
    IdentityConversion | LinearConversion | EnumConversion,
    Field(discriminator="kind"),
    BeforeValidator(_infer_kind),
]
"""Raw to physical conversion; ``kind`` may be omitted when the shape is unambiguous."""

IDENTITY = IdentityConversion()


def conversion_identity(conversion: Conversion) -> object:
    """What two spellings of one conversion have to agree on to be the same conversion.

    An enumerator's ``description`` is documentation, not interface: the two spellings the
    file format offers - the mapping shorthand and the list of objects - cannot even carry
    the same text, and two conversions differing only in it mean the same mapping. The
    ordered name and value pairs do count, exactly as ``enum-conflict`` counts them, and
    everything else compares as written, because ``linear`` with factor 1 is deliberately
    not the identity. One function for both questions - declarations inside a project, and
    one object across two deliveries - so the two can never drift over what a conversion is.
    """
    if isinstance(conversion, EnumConversion):
        return (
            "enum",
            conversion.name,
            tuple((entry.name, entry.value) for entry in conversion.enumerators),
        )
    return conversion.model_dump(mode="json")


def physical_range(conversion: Conversion, raw_min: float, raw_max: float) -> tuple[float, float]:
    """The physical range a raw range covers, in the order a reader expects.

    Takes the raw ends rather than a datatype, because they do not always come from one: a
    bitfield's ends come from its width, and offering a two bit field over the whole range of
    the ``uint16`` carrying it would be an invitation to enter a value it cannot hold.
    """
    if isinstance(conversion, EnumConversion):
        values = conversion.values
        return float(min(values)), float(max(values))
    low = conversion.to_physical(raw_min)
    high = conversion.to_physical(raw_max)
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
    """
    if isinstance(conversion, LinearConversion):
        return f"{format_number(conversion.to_physical(raw))} {unit}".rstrip()
    if isinstance(conversion, EnumConversion):
        return next((item.name for item in conversion.enumerators if item.value == raw), None)
    return None
