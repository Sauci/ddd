"""The data objects a component can declare: measurements and calibration data."""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum
from typing import Annotated, Any, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, model_validator

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
    model_config = ConfigDict(frozen=True, extra="forbid", use_attribute_docstrings=True)


class Limits(_Frozen):
    """Physical lower/upper limit of a data object."""

    min: Number
    """Smallest physical value the object may take."""

    max: Number
    """Largest physical value the object may take; at least ``min``."""

    @model_validator(mode="after")
    def _ordered(self) -> Limits:
        if self.min > self.max:
            msg = f"min ({format_number(self.min)}) is greater than max ({format_number(self.max)})"
            raise ValueError(msg)
        return self

    def as_tuple(self) -> tuple[float, float]:
        return (self.min, self.max)


class A2lObjectOptions(_Frozen):
    """What a declaration asks of the a2l backend. Only that backend interprets it.

    Nothing here changes the generated c or the meaning of the object; a project that
    generates no a2l can leave the whole block out.
    """

    export: bool | None = None
    """Whether the object belongs in the a2l file; omitted, it does.

    The one a2l option any component may state, not only the producer. Which signals a
    calibration engineer needs to see is not a property of whoever happens to write the
    variable: a component reading a value from a library it does not own has as good a claim
    to measuring it.

    Stated by several, the answer is yes if any of them says so - see :func:`resolve_export`.
    """

    format: A2lFormat | None = None
    """a2l ``FORMAT`` string, e.g. ``"%8.3"``: total width, then decimal places."""

    display_identifier: Identifier | None = None
    """Alternative name shown by the calibration tool."""


def resolve_export(stated: Iterable[bool | None]) -> bool:
    """Whether an object reaches the a2l, given what every component said about it.

    Anyone may ask for it and nobody may veto, which is the safe direction rather than the
    tidy one: an object in the a2l that nobody looks at costs a longer file, while one missing
    from it costs somebody a measurement they cannot take and a delivery to wait for.

    Order independent on purpose. Two consumers can then never conflict, so there is no
    finding to invent for a disagreement between them and no dependence on which components a
    given image happens to link.
    """
    values = [value for value in stated if value is not None]
    # Nothing stated at all is the default, which is to export.
    return any(values) if values else True


class DataObject(_Frozen):
    """Attributes shared by every kind of data object."""

    name: Identifier
    """C identifier of the object; also its name in the a2l."""

    datatype: Datatype
    """Storage type of one element, from ``boolean`` through the integers to ``float64``."""

    description: str = ""
    """What the object is, offered to the c templates and used as the a2l long identifier."""

    unit: str = ""
    """Physical unit, e.g. ``"Hz"``.

    Free text, so DDD does not know that ``rpm`` and ``1/min`` are the same thing; it only
    checks that every component declaring this object spells the unit the same way.
    """

    init: InitValue | None = None
    """Raw initial value, in the stored domain rather than the physical one.

    ``null`` leaves the object zero initialised by the startup code. For an array shaped
    object, either a nested list matching the shape exactly, or a single scalar, which
    initialises every element with that value.
    """

    conversion: Conversion = IDENTITY
    """How a raw value maps to a physical one: identity, linear scaling or an enumeration.

    ``kind`` may be left out when the keys make it unambiguous: ``factor`` or ``offset`` means
    ``linear``, ``enumerators`` or ``name`` means ``enum``, and nothing at all means
    ``identity``, which is also what an object without a conversion gets.
    """

    limits: Limits | None = None
    """Physical limits of the object, in the unit given by ``unit``.

    Omitted, they are derived from ``datatype`` and ``conversion``: the whole range the
    storage can hold, converted. State them to say that the software handles less than that,
    which is what stops a calibration tool offering a value the software cannot take.
    """

    a2l: A2lObjectOptions = A2lObjectOptions()
    """What this object asks of the a2l file: whether to export it, how to display it.

    Only the a2l backend reads it, so a project that generates no a2l can leave it out
    entirely.
    """

    kind: ObjectKind
    """Which sort of object this is; stated on every definition.

    It also decides which further keys the definition may carry: ``dimensions`` and
    ``volatile`` on a measurement, ``dimensions`` on a value block, ``size`` and ``input`` on
    an axis, ``axis`` on a curve, ``x_axis`` and ``y_axis`` on a map, and none of them on a
    parameter.
    """

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

    kind: Literal[ObjectKind.MEASUREMENT]
    dimensions: tuple[PositiveInt, ...] = ()
    """Array dimensions; empty for a scalar."""

    is_volatile: Annotated[bool, Field(alias="volatile")] = False
    """Generate the variable ``volatile``, for values written by an interrupt or by hardware.

    Interface rather than storage, because it reaches every component that reads the variable:
    their header declares it ``extern volatile``, which is what tells their code not to cache
    it and not to expect two reads to agree. Every declaration of one variable therefore has
    to say the same thing, and a disagreement is an error.

    Left out it is ``false``, and that is a claim rather than a silence - unlike ``limits``,
    which a declaration may omit because DDD derives them from the datatype and the
    conversion. There is nothing to derive here: a component whose description does not say a
    variable is volatile is a component whose author was never told, and that is exactly the
    thing an interface description exists to prevent.
    """

    @property
    def volatile(self) -> bool:
        return self.is_volatile

    @property
    def declared_shape(self) -> Shape:
        return self.dimensions


class Parameter(DataObject):
    """A single calibratable constant."""

    kind: Literal[ObjectKind.PARAMETER]


class ValueBlock(DataObject):
    """An array of calibratable constants."""

    kind: Literal[ObjectKind.VALUE_BLOCK]
    dimensions: Annotated[tuple[PositiveInt, ...], Field(min_length=1)]
    """Array dimensions in c declaration order; a value block is never a scalar."""

    @property
    def declared_shape(self) -> Shape:
        return self.dimensions


class Axis(DataObject):
    """Shared axis points; several curves and maps may be interpolated over one axis."""

    kind: Literal[ObjectKind.AXIS]
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

    kind: Literal[ObjectKind.CURVE]
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

    kind: Literal[ObjectKind.MAP]
    x_axis: Identifier
    """Name of the axis whose index runs fastest; the last dimension of the c array."""

    y_axis: Identifier
    """Name of the axis selecting the row; the first dimension of the c array."""

    @property
    def declared_shape(self) -> None:
        return None

    @property
    def references(self) -> dict[str, str]:
        return {"x_axis": self.x_axis, "y_axis": self.y_axis}


AnyDataObject = Annotated[
    Measurement | Parameter | ValueBlock | Curve | Map | Axis,
    Field(discriminator="kind"),
]
"""Any data object, told apart by its required ``kind``.

``kind`` is stated on every definition rather than defaulting to ``measurement``: the default
made a bare ``{"name", "datatype"}`` match two variants at once, which a strict json schema
validator - the editor binding a file to ``ddd schema`` - reports as an ambiguity. Requiring
it keeps the published schema and the loader in agreement, at the cost of one more line on a
measurement.
"""


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
            # The tag is the single value of the variant's ``Literal[...]`` discriminator,
            # read from the annotation rather than a default so it does not depend on the
            # field carrying one - the data object kinds are required, the conversion kinds
            # default.
            (literal,) = get_args(variant.model_fields["kind"].annotation)
            tags.add(str(literal))
    return frozenset(tags)
