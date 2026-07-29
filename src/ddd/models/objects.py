"""The data objects a component can declare: measurements and calibration data."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Literal, get_args

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, PositiveInt, model_validator

from ddd.models.common import A2lFormat, Datatype, Identifier, Number, Real, format_number
from ddd.models.conversion import IDENTITY, Conversion, EnumConversion, conversion_range

type InitValue = bool | int | Real | tuple[InitValue, ...]
"""A scalar, or a (nested) sequence of scalars matching the shape of the object."""

type Shape = tuple[int, ...]


class ObjectKind(StrEnum):
    """What sort of data object a definition describes."""

    MEASUREMENT = "measurement"
    """An online value the software writes and the calibration tool only reads."""

    PARAMETER = "parameter"
    """A single calibratable constant."""

    VALUE_BLOCK = "value_block"
    """An array of calibratable constants."""

    CURVE = "curve"
    """A one dimensional calibratable table over one axis."""

    MAP = "map"
    """A two dimensional calibratable table over two axes."""

    AXIS = "axis"
    """Shared axis points a curve or map is interpolated over."""

    @property
    def is_calibration(self) -> bool:
        """Everything but a measurement is calibration data and therefore ``const``."""
        return self is not ObjectKind.MEASUREMENT


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Limits(_Frozen):
    """Physical lower/upper limit of a data object."""

    min: Number
    max: Number

    @model_validator(mode="after")
    def _ordered(self) -> Limits:
        if self.min > self.max:
            msg = f"min ({format_number(self.min)}) is greater than max ({format_number(self.max)})"
            raise ValueError(msg)
        return self

    def as_tuple(self) -> tuple[float, float]:
        return (self.min, self.max)


class A2lObjectOptions(_Frozen):
    """What a declaration asks of the a2l backend. Only that backend interprets it."""

    export: bool = True
    """Set to ``false`` to keep the object out of the a2l file."""

    format: A2lFormat | None = None
    """a2l ``FORMAT`` string, e.g. ``"%8.3"``: total width, then decimal places."""

    display_identifier: Identifier | None = None
    """Alternative name shown by the calibration tool."""


class DataObject(_Frozen):
    """Attributes shared by every kind of data object."""

    name: Identifier
    datatype: Datatype
    description: str = ""
    unit: str = ""
    """Physical unit, e.g. ``"Hz"``.  Free text, but must match between components."""

    init: InitValue | None = None
    """Raw initial value.  ``null`` leaves the object zero initialised by the startup code.

    A scalar given for an array shaped object initialises every element with that value.
    """

    conversion: Conversion = IDENTITY
    limits: Limits | None = None
    """Physical limits; derived from ``datatype`` and ``conversion`` when omitted."""

    a2l: A2lObjectOptions = A2lObjectOptions()

    kind: ObjectKind

    @property
    def is_calibration(self) -> bool:
        return self.kind.is_calibration

    @property
    def volatile(self) -> bool:
        """Only a measurement can be volatile; overridden by :class:`Measurement`."""
        return False

    @property
    def declared_shape(self) -> Shape | None:
        """The shape as far as the definition itself knows it.

        ``None`` for curves and maps, whose shape follows from the axes they refer to
        and is therefore only known once the whole project is resolved.
        """
        return ()

    @property
    def references(self) -> dict[str, str]:
        """Names of other data objects this one refers to, keyed by the field name."""
        return {}

    @model_validator(mode="after")
    def _enum_requires_integer(self) -> DataObject:
        if isinstance(self.conversion, EnumConversion) and not self.datatype.is_integer:
            msg = (
                f"enum conversion '{self.conversion.name}' requires an integer datatype, "
                f"got '{self.datatype.value}'"
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _init_matches_shape(self) -> DataObject:
        shape = self.declared_shape
        # A scalar init is always accepted: for an array it initialises every element.
        if shape is not None and isinstance(self.init, tuple):
            problem = check_shape(self.init, shape)
            if problem is not None:
                raise ValueError(problem)
        return self

    def physical_limits(self) -> Limits:
        """Explicit limits, or the full range implied by datatype and conversion."""
        if self.limits is not None:
            return self.limits
        low, high = conversion_range(self.conversion, self.datatype)
        return Limits(min=low, max=high)

    def scalar_values(self) -> tuple[float | int | bool, ...]:
        """All raw init values, flattened; empty when no init is given."""
        if self.init is None:
            return ()
        return tuple(flatten(self.init))


class Measurement(DataObject):
    """An online value: written by the software, only measured by the calibration tool."""

    kind: Literal[ObjectKind.MEASUREMENT] = ObjectKind.MEASUREMENT
    dimensions: tuple[PositiveInt, ...] = ()
    """Array dimensions; empty for a scalar."""

    is_volatile: Annotated[bool, Field(alias="volatile")] = False

    @property
    def volatile(self) -> bool:
        return self.is_volatile

    @property
    def declared_shape(self) -> Shape:
        return self.dimensions


class Parameter(DataObject):
    """A single calibratable constant."""

    kind: Literal[ObjectKind.PARAMETER] = ObjectKind.PARAMETER


class ValueBlock(DataObject):
    """An array of calibratable constants."""

    kind: Literal[ObjectKind.VALUE_BLOCK] = ObjectKind.VALUE_BLOCK
    dimensions: Annotated[tuple[PositiveInt, ...], Field(min_length=1)]

    @property
    def declared_shape(self) -> Shape:
        return self.dimensions


class Axis(DataObject):
    """Shared axis points; several curves and maps may be interpolated over one axis."""

    kind: Literal[ObjectKind.AXIS] = ObjectKind.AXIS
    size: PositiveInt
    """Number of axis points."""

    input: Identifier | None = None
    """Measurement that indexes the axis; the a2l input quantity."""

    @property
    def declared_shape(self) -> Shape:
        return (self.size,)

    @property
    def references(self) -> dict[str, str]:
        return {"input": self.input} if self.input else {}


class Curve(DataObject):
    """A one dimensional calibratable table."""

    kind: Literal[ObjectKind.CURVE] = ObjectKind.CURVE
    axis: Identifier
    """Name of the axis object the curve is interpolated over."""

    @property
    def declared_shape(self) -> None:
        return None

    @property
    def references(self) -> dict[str, str]:
        return {"axis": self.axis}


class Map(DataObject):
    """A two dimensional calibratable table, stored as ``[y][x]``."""

    kind: Literal[ObjectKind.MAP] = ObjectKind.MAP
    x_axis: Identifier
    y_axis: Identifier

    @property
    def declared_shape(self) -> None:
        return None

    @property
    def references(self) -> dict[str, str]:
        return {"x_axis": self.x_axis, "y_axis": self.y_axis}


def _default_kind(data: Any) -> Any:
    """A definition without ``kind`` is a measurement, as in the original file format."""
    if isinstance(data, dict) and "kind" not in data:
        data = dict(data)
        data["kind"] = ObjectKind.MEASUREMENT.value
    return data


AnyDataObject = Annotated[
    Measurement | Parameter | ValueBlock | Curve | Map | Axis,
    Field(discriminator="kind"),
    BeforeValidator(_default_kind),
]
"""Any data object; the discriminator ``kind`` defaults to ``measurement``."""


def format_shape(shape: Shape) -> str:
    """``"[4][2]"`` for a 4x2 array, ``""`` for a scalar; for diagnostics and listings."""
    return "".join(f"[{dimension}]" for dimension in shape)


def check_shape(value: InitValue, shape: Shape) -> str | None:
    """Validate a nested init value against an array shape."""
    if not shape:
        if isinstance(value, tuple):
            return "init is a list but the object is a scalar"
        return None
    if not isinstance(value, tuple):
        return f"init must be a list of {shape[0]} elements or a single scalar value"
    if len(value) != shape[0]:
        return f"init has {len(value)} elements, expected {shape[0]}"
    for element in value:
        problem = check_shape(element, shape[1:])
        if problem is not None:
            return problem
    return None


def flatten(value: InitValue) -> list[float | int | bool]:
    if isinstance(value, tuple):
        return [scalar for element in value for scalar in flatten(element)]
    return [value]


def broadcast(value: InitValue, shape: Shape) -> InitValue:
    """Expand a scalar init over ``shape``; a nested value is returned unchanged."""
    if isinstance(value, tuple):
        return value
    if not shape:
        return value
    return tuple(broadcast(value, shape[1:]) for _ in range(shape[0]))


def discriminator_tags(*unions: Any) -> frozenset[str]:
    """The ``kind`` values of every variant of the given tagged unions.

    pydantic names the selected variant in the location of a validation error
    (``definition.measurement.datatype``). Deriving the set from the unions themselves means
    a new variant is covered without anyone remembering to add its tag somewhere else.
    """
    tags: set[str] = set()
    for union in unions:
        annotated, *_ = get_args(union)
        for variant in get_args(annotated):
            tags.add(str(variant.model_fields["kind"].default))
    return frozenset(tags)
