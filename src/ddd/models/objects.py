"""The data objects a component can declare: measurements and calibration data."""

from __future__ import annotations

from collections.abc import Container, Iterable
from enum import StrEnum
from typing import Annotated, Any, Final, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, model_validator

from ddd.models.common import (
    A2lFormat,
    Datatype,
    DatatypeRef,
    Identifier,
    Number,
    Real,
    format_number,
)
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
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        use_attribute_docstrings=True,
    )


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

    @property
    def exported(self) -> bool:
        """Whether the object reaches the a2l, with an unstated ``export`` read as yes.

        The tri-state belongs to the *authored* side, where "not stated" is what lets several
        components be asked - see :func:`resolve_export`. Everything downstream wants a plain
        answer, and reading ``None`` as ``False`` is the wrong one: a dictionary that omits the
        a2l block altogether is a perfectly good dictionary, and one a generator DDD does not
        ship is allowed to hand over. It used to export such an object and has to keep doing so.
        """
        return self.export is not False

    @property
    def effective(self) -> tuple[bool, str | None, str | None]:
        """The a2l entry as it will actually be, for comparing two of them."""
        return (self.exported, self.format, self.display_identifier)


MEANING_KEYS: Final = ("unit", "conversion", "limits")
"""What says how a raw number is read: the keys a scalar type exists to fix once.

Written directly on the thing that has them, or fixed by a named type - never both. Which of
the two an author picks is a matter of whether the answer is shared: a unit written on one
member of one structure says it once, and a ``Speed_t`` says it for every component that names
it. The rule against restating is what keeps "where is this object's unit written down" a
question with one answer.
"""


def refuse_restating(datatype: DatatypeRef, stated: Container[str]) -> None:
    """Refuse stating what a named type already fixes; an error rather than an override.

    The same rule wherever a datatype can be named - on a declaration and on a structure member
    alike - because the confusion it prevents is the same one. An override rule would make the
    answer to "where is this unit written down" be "in one of two places, and you have to know
    which of them wins".

    Only the meaning keys are refused here. The rest of the difference between a scalar type and
    a structure - a structure has no room for a unit at all - needs to know which kind of type
    the name refers to, and that is a check rather than a contract rule.
    """
    if isinstance(datatype, Datatype):
        return
    restated = [key for key in MEANING_KEYS if key in stated]
    if restated:
        listed = ", ".join(f"'{key}'" for key in restated)
        msg = (
            f"'{datatype}' is a declared type and already fixes what this value means, so "
            f"{listed} may not be stated here as well"
        )
        raise ValueError(msg)


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

    datatype: DatatypeRef
    """Storage of one element: a base datatype, or the name of a type the project declares.

    One key names a type here exactly as it does on a structure member. Naming a structure is
    what makes this object a structured one; naming a scalar type is what lets several
    components agree about a value by naming it rather than by each copying out its unit, its
    scaling and its limits - and a declaration that names a type may not restate any of them.
    """

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

    volatile: bool
    """Whether the c declaration carries ``volatile``; stated on every definition.

    Required, with no default, and on every kind rather than on measurements alone. Both
    follow from what the qualifier does, which is to forbid the compiler to assume it already
    knows the value.

    A measurement needs it when something outside the reading component's control writes the
    variable - an interrupt, a second core, a peripheral. A calibration object needs it when
    the calibration tool is to change the value in a running ecu: without it the compiler is
    entitled to use the initialiser in place of a read wherever it can see it - within one
    translation unit at every optimisation level, ``-O0`` included, and across them under link
    time optimisation - and, where the load does survive, to serve two reads from one of them.
    Either way the tool writes a new value the software does not pick up.

    Interface rather than storage, because it reaches every component that reads the object:
    their header declares it ``extern volatile``, which is what tells their code not to cache
    the value and not to expect two reads to agree. Every declaration of one object therefore
    has to say the same thing, and a disagreement is an error.

    There is no default because there is no answer DDD could derive - unlike ``limits``, which
    follow from the datatype and the conversion. The two answers have different costs and only
    the project knows which it is paying: ``true`` keeps a value tunable and, on a typical
    toolchain, moves a calibration object out of read-only memory; ``false`` keeps it in flash
    and lets the optimiser cache it. Saying nothing would pick one of them silently, and the
    one it picked would be wrong roughly as often as not.
    """

    kind: ObjectKind
    """Which sort of object this is; stated on every definition.

    It also decides which further keys the definition may carry: ``dimensions`` on a
    measurement or a value block, ``size`` and ``input`` on an axis, ``axis`` on a curve,
    ``x_axis`` and ``y_axis`` on a map, and none of them on a parameter.
    """

    @property
    def is_calibration(self) -> bool:
        return self.kind.is_calibration

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

    @property
    def declared_type(self) -> str | None:
        """The type this definition names, or nothing if its datatype is a base one."""
        return None if isinstance(self.datatype, Datatype) else self.datatype

    @property
    def storage(self) -> Datatype:
        """The base datatype this object is stored as.

        Only ever asked of a definition the analysis has already resolved: one that named a
        type has had it filled in, and one that named a type nobody declares was reported and
        dropped before anything got this far. The assertion is what says so to a reader and to
        a type checker, rather than each caller quietly narrowing the union again.
        """
        assert isinstance(self.datatype, Datatype)
        return self.datatype

    @model_validator(mode="after")
    def _enum_requires_integer(self) -> DataObject:
        if isinstance(self.datatype, Datatype) and (
            isinstance(self.conversion, EnumConversion) and not self.datatype.is_integer
        ):
            msg = (
                f"enum conversion '{self.conversion.name}' requires an integer datatype, "
                f"got '{self.datatype.value}'"
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _a_named_type_is_not_restated(self) -> DataObject:
        refuse_restating(self.datatype, self.model_fields_set)
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
        """Explicit limits, or the full range implied by datatype and conversion.

        Only ever asked of a definition whose datatype is a base one: a definition naming a type
        has its datatype, unit, conversion and limits filled in from that type by the analysis
        before anything reads them.
        """
        if self.limits is not None:
            return self.limits
        low, high = conversion_range(self.conversion, self.storage)
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

_VARIANTS: Final[dict[str, type[DataObject]]] = {
    str(get_args(variant.model_fields["kind"].annotation)[0]): variant
    for variant in get_args(get_args(AnyDataObject)[0])
}
"""Each ``kind`` value and the model that describes it - see :func:`definition_keys`."""


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


def definition_keys(kind: str) -> tuple[frozenset[str], frozenset[str]]:
    """Which keys a definition of that kind accepts, and which of them it must state.

    Derived from the variants rather than listed, for the reason every list in this file is
    derived: a key added to a model is covered here the moment it exists, and one that moves
    between models cannot be left behind in a copy of the answer.

    The caller is an editor offering to change one key of one definition. Both halves are what
    stops it offering an edit that produces a file the loader then refuses - removing a key the
    kind requires, or writing one the kind does not have.
    """
    variant = _VARIANTS.get(kind)
    if variant is None:
        # A kind the file states and DDD does not know. The loader has its own opinion about
        # that; here it simply means nothing can be said, which every caller reads as "offer
        # nothing" rather than as an error of its own.
        return (frozenset(), frozenset())
    fields = variant.model_fields
    return (
        frozenset(fields),
        frozenset(name for name, field in fields.items() if field.is_required()),
    )


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
