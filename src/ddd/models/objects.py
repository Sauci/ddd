"""The data objects a component can declare: measurements and calibration data."""

from __future__ import annotations

from collections.abc import Container, Iterable
from enum import StrEnum
from typing import Annotated, Any, Final, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ddd.models.common import (
    A2lFormat,
    Datatype,
    Identifier,
    Number,
    ObjectId,
    Real,
    TypeName,
    format_number,
)
from ddd.models.conversion import Conversion, EnumConversion, conversion_range

type InitValue = bool | int | Real | tuple[InitValue, ...]
"""A scalar, or a (nested) sequence of scalars matching the shape of the object."""

type Shape = tuple[int, ...]
"""A fully numeric array shape, as the analysis resolves it."""

Dimension = Annotated[int, Field(strict=True, ge=1)] | Identifier
"""One array dimension as a definition writes it: a number, or the name of a constant.

An integer of at least 1, or the name of a constant the project declares.  Strict on the
integer side so that the two spellings stay two: without it, a quoted
``"8"`` - which is neither a number nor an identifier - would be quietly read as the number,
and the file would say something its author did not write.
"""

type WrittenShape = tuple[int | str, ...]
"""An array shape as it is written: each dimension a number or the name of a constant."""


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


def refuse_restating(typename: str, stated: Container[str]) -> None:
    """Refuse stating what a named type already fixes; an error rather than an override.

    The same rule wherever a type can be named - on a declaration and on a structure member
    alike - because the confusion it prevents is the same one. An override rule would make the
    answer to "where is this unit written down" be "in one of two places, and you have to know
    which of them wins".

    Only the meaning keys are refused here. The rest of the difference between a scalar type and
    a structure - a structure has no room for a unit at all - needs to know which kind of type
    the name refers to, and that is a check rather than a contract rule.
    """
    restated = [key for key in MEANING_KEYS if key in stated]
    if restated:
        listed = ", ".join(f"'{key}'" for key in restated)
        msg = (
            f"'{typename}' is a declared type and already fixes what this value means, so "
            f"{listed} may not be stated here as well"
        )
        raise ValueError(msg)


def refuse_enum_on_non_integer(datatype: Datatype | None, conversion: Conversion | None) -> None:
    """Refuse an enum conversion on storage that cannot hold an enumerator exactly.

    The same rule wherever a ``datatype`` and a ``conversion`` are stated side by side - on a
    definition, on a structure member and on a scalar type - shared the way
    :func:`refuse_restating` is, because letting one of the three accept what the others
    refuse would make the verdict depend on where the same pair happens to be written.
    ``boolean`` does not count as an integer datatype: an enumerator is an exact integer,
    which a float cannot promise to hold and a truth value has no room for.
    """
    if (
        isinstance(datatype, Datatype)
        and isinstance(conversion, EnumConversion)
        and not datatype.is_integer
    ):
        msg = (
            f"enum conversion '{conversion.name}' requires an integer datatype, "
            f"got '{datatype.value}'"
        )
        raise ValueError(msg)


def check_storage_named_once(datatype: Datatype | None, typename: str | None) -> None:
    """Refuse a definition that names its storage twice, or not at all.

    The same rule wherever storage is named - on a definition and on a structure member
    alike - shared the way :func:`refuse_restating` is: two keys stating one storage leaves
    a reader guessing which of them counts, and neither stating it leaves nothing to
    allocate.
    """
    if (datatype is None) == (typename is None):
        msg = (
            "storage is named exactly once: 'datatype' for a base datatype, 'typename' "
            "for a type the project declares"
        )
        raise ValueError(msg)


def check_conversion_stated(datatype: Datatype | None, conversion: Conversion | None) -> None:
    """Refuse base storage that states no conversion; the identity is an answer, not a default.

    The same rule wherever a base ``datatype`` is stated - on a definition and on a structure
    member alike - because the forgotten scaling it prevents is the same one: a fixed point
    value silently displayed as raw counts, with nothing looking broken.
    """
    if datatype is not None and conversion is None:
        msg = (
            "a 'datatype' comes with a 'conversion': the identity "
            '({"kind": "identity"}) is an answer to state, not a default to fall into'
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

    id: ObjectId | None = None
    """Identity of this object, which survives its name.

    Written by the component that produces the object and by nothing else: a consumer stating
    one is refused as ``consumer-identity``, on the reasoning that makes ``section`` and
    ``init`` producer keys. It links this object to itself in an earlier delivery, so that
    ``ddd compare`` reports a rename as a rename rather than as a removal and an unrelated
    addition, and so that a name freed by a rename cannot be quietly claimed by something
    else.

    Nothing inside a project reads it: the producer and its consumers go on binding by name,
    and the generated c and a2l never mention it. Optional, so that a project adopts it one
    component at a time; ``missing-id`` says where it has not.
    """

    extensions: dict[str, dict[str, Any]] = Field(default_factory=dict)
    """Blocks owned by the project's plugins, keyed by plugin name.

    ``{"layout": {"key": 12, "version": 3}}``: what a plugin the project names needs to know
    about this object and DDD does not. Each block is validated against the model of the
    plugin that owns it and carried into the dictionary in resolved form; a block naming no
    loaded plugin is ``unknown-extension``. Only the producing declaration states one - a
    consumer stating one is ``consumer-extension``, on the reasoning that makes ``section``
    and ``id`` producer keys: a block says what the object *is*.
    """

    datatype: Datatype | None = None
    """Storage of one element, one of the eleven base datatypes.

    Exactly one of ``datatype`` and ``typename`` is stated. Two keys rather than one union,
    so that the published schema says ``datatype`` is one of eleven values - an editor
    completes and documents exactly them, and a mistyped one is refused as it is typed - and
    so that a declaration tells its reader at a glance whether storage is base or declared.
    """

    typename: TypeName | None = None
    """Name of a type the project declares, stated instead of ``datatype``.

    Naming a structure is what makes this object a structured one; naming a scalar type is
    what lets several components agree about a value by naming it rather than by each copying
    out its unit, its scaling and its limits - and a declaration that names a type may not
    restate any of them.
    """

    description: str = ""
    """What the object is, offered to the c templates and used as the a2l long identifier."""

    unit: str = ""
    """Physical unit, e.g. ``"Hz"``.

    Free text, so DDD does not know that ``rpm`` and ``1/min`` are the same thing; it only
    checks that every component declaring this object spells the unit the same way.
    """

    section: str | None = None
    """Linker section the object is placed in, named in the project's sections file.

    A storage key like ``init``: the producer states it, a consumer stating one claims
    storage it does not own (``consumer-storage``), and a structured object is placed whole.
    Left out, the object goes wherever the toolchain's defaults put it.
    """

    raster: str | None = None
    """Measurement raster the object is updated in, named in the project's rasters file.

    A producer key like ``section``: the producing component's task is what updates the
    value, so a consumer stating one is refused as ``consumer-raster``, and a structured
    variable carries one raster for all of its members. Left out, the producing component's
    default applies; left out there too, the a2l describes the object without saying which
    daq event carries it, and the calibration tool decides.

    At the top level rather than inside ``a2l``, although only that backend reads it today:
    which task updates a value is an engineering claim about the data, the way ``section``
    is, and not a presentation choice.
    """

    init: InitValue | None = None
    """Raw initial value, in the stored domain rather than the physical one.

    ``null`` leaves the object zero initialised by the startup code. For an array shaped
    object, either a nested list matching the shape exactly, or a single scalar, which
    initialises every element with that value.
    """

    conversion: Conversion | None = None
    """How a raw value maps to a physical one: identity, linear scaling or an enumeration.

    Required wherever storage is named by ``datatype``, although the identity would be
    derivable: raw equalling physical is an engineering claim about the data, not a
    formatting accident, and a forgotten scaling on a fixed point value displays raw counts
    without anything looking broken. A definition naming a ``typename`` states no conversion
    - the type fixes it. ``kind`` may be left out when the keys make it unambiguous:
    ``factor`` or ``offset`` means ``linear``, ``enumerators`` or ``name`` means ``enum``,
    and ``{}`` means ``identity``.
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
    def declared_shape(self) -> WrittenShape | None:
        """The shape as far as the definition itself writes it, spelling and all.

        ``None`` for curves and maps, whose shape follows from the axes they refer to
        and is therefore only known once the whole project is resolved.  A dimension stated
        as the name of a constant stays that name here: declarations compare as written,
        and the numeric value is the analysis's to resolve.
        """
        return ()

    @property
    def references(self) -> dict[str, str]:
        """Names of other data objects this one refers to, keyed by the field name."""
        return {}

    @property
    def declared_type(self) -> str | None:
        """The type this definition names, or nothing if its storage is a base datatype."""
        return self.typename

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
        refuse_enum_on_non_integer(self.datatype, self.conversion)
        return self

    @model_validator(mode="after")
    def _storage_is_named_exactly_once(self) -> DataObject:
        check_storage_named_once(self.datatype, self.typename)
        return self

    @model_validator(mode="after")
    def _base_storage_states_its_conversion(self) -> DataObject:
        check_conversion_stated(self.datatype, self.conversion)
        return self

    @model_validator(mode="after")
    def _a_named_type_is_not_restated(self) -> DataObject:
        if self.typename is not None:
            refuse_restating(self.typename, self.model_fields_set)
        return self

    def __hash__(self) -> int:
        """A frozen model hashes by default from all its fields, and ``extensions`` may hold
        whatever a plugin put there - a list inside a block, say - which pydantic cannot hash.

        Leaving it out of the hash costs nothing a caller would notice: two definitions equal
        in every field, ``extensions`` included, still hash equal, since equality is coarser
        than this - the only thing a hash has to promise.
        """
        return hash(
            (type(self), *(value for key, value in self.__dict__.items() if key != "extensions"))
        )

    # The shape of a stated ``init`` is deliberately not validated here. Only part of the
    # answer is written in the file - a curve or a map takes its shape from axes another
    # declaration owns - so the analysis checks every kind in one place and reports every
    # wrong shape as ``init-invalid``, one identifier instead of two severities.

    def physical_limits(self) -> Limits:
        """Explicit limits, or the full range implied by datatype and conversion.

        Only ever asked of a definition whose datatype is a base one: a definition naming a type
        has its datatype, unit, conversion and limits filled in from that type by the analysis
        before anything reads them.
        """
        if self.limits is not None:
            return self.limits
        assert self.conversion is not None
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
    dimensions: tuple[Dimension, ...] = ()
    """Array dimensions; empty for a scalar.

    Each an integer of at least 1, or the name of a constant the project declares, in a
    constants file or in a component - ``[3, 4]`` and ``["PRESSURE_CELLS", 4]`` are both
    shapes.
    """

    @property
    def declared_shape(self) -> WrittenShape:
        return self.dimensions


class Parameter(DataObject):
    """A single calibratable constant."""

    kind: Literal[ObjectKind.PARAMETER]


class ValueBlock(DataObject):
    """An array of calibratable constants."""

    kind: Literal[ObjectKind.VALUE_BLOCK]
    dimensions: Annotated[tuple[Dimension, ...], Field(min_length=1)]
    """Array dimensions in c declaration order; a value block is never a scalar.

    Each an integer of at least 1, or the name of a constant the project declares, mixed
    freely.
    """

    @property
    def declared_shape(self) -> WrittenShape:
        return self.dimensions


class Axis(DataObject):
    """Shared axis points; several curves and maps may be interpolated over one axis."""

    kind: Literal[ObjectKind.AXIS]
    size: Dimension
    """Number of axis points: an integer of at least 1, or the name of a declared
    constant."""

    input: Identifier | None = None
    """Measurement that indexes the axis; the a2l input quantity."""

    @property
    def declared_shape(self) -> WrittenShape:
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


def spelled_dimensions(definition: DataObject) -> list[tuple[str, str]]:
    """Every dimension a definition spells as a constant name, with the key it is under.

    ``(name, pointer suffix)`` pairs, so that a finding or a jump about the constant lands
    on the entry that names it rather than on the definition as a whole. A measurement or a
    value block spells its ``dimensions``, an axis its ``size``, and a curve or a map
    spells no dimension of its own - its shape is the axes' business. One walk for the
    analysis and the editor alike, so the two can never disagree about where a name is
    spelled.
    """
    found: list[tuple[str, str]] = []
    if isinstance(definition, Measurement | ValueBlock):
        found.extend(
            (dimension, f"dimensions[{index}]")
            for index, dimension in enumerate(definition.dimensions)
            if isinstance(dimension, str)
        )
    elif isinstance(definition, Axis) and isinstance(definition.size, str):
        found.append((definition.size, "size"))
    return found


def format_shape(shape: WrittenShape) -> str:
    """``"[4][2]"`` for a 4x2 array, ``""`` for a scalar; for diagnostics and listings.

    A dimension spelled as the name of a constant renders as that name -
    ``"[PRESSURE_CELLS]"`` - because the spelling is what the reader wrote and what the
    generated code carries.
    """
    return "".join(f"[{dimension}]" for dimension in shape)


def check_shape(value: InitValue, shape: Shape) -> str | None:
    """Validate a nested init value against an array shape."""
    if not shape:
        if isinstance(value, tuple):
            return "init is a list but the object is a scalar"
        return None
    if not isinstance(value, tuple):
        # Only the init as a whole may be a scalar, which then fills every element; a scalar
        # inside a nested list describes no shape, so it is refused rather than broadcast.
        return (
            f"init must be a list of {shape[0]} elements; only the whole init may be a "
            f"single scalar"
        )
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
    """The discriminator values of every variant of the given tagged unions.

    pydantic names the selected variant in the location of a validation error
    (``definition.measurement.datatype``, ``types[0].scalar.limits``). Deriving the set from
    the unions themselves means a new variant is covered without anyone remembering to add
    its tag somewhere else - and the discriminating field is read from each union's own
    ``Field(discriminator=...)``, because the unions do not agree on its name: the data
    objects and the conversions discriminate on ``kind``, the declared types on ``type``.
    """
    tags: set[str] = set()
    for union in unions:
        annotated, *metadata = get_args(union)
        discriminator = next(
            entry.discriminator for entry in metadata if getattr(entry, "discriminator", None)
        )
        for variant in get_args(annotated):
            # The tag is the single value of the variant's ``Literal[...]`` discriminator,
            # read from the annotation rather than a default so it does not depend on the
            # field carrying one - the data object kinds are required, the conversion kinds
            # default.
            (literal,) = get_args(variant.model_fields[discriminator].annotation)
            tags.add(str(literal))
    return frozenset(tags)
