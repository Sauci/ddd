"""Turning the data dictionary into the flat structures the a2l template reads.

The mapping follows ASAM MCD-2 MC (ASAP2) 1.6.1:

* a measurement becomes a ``MEASUREMENT``
* a parameter, value block, curve and map become a ``CHARACTERISTIC`` of type ``VALUE``,
  ``VAL_BLK``, ``CURVE`` and ``MAP``; an axis becomes an ``AXIS_PTS``
* a curve or map refers to its axes with an ``AXIS_DESCR`` of attribute ``COM_AXIS`` and an
  ``AXIS_PTS_REF``, so the axis points are stored once and shared
* maps are deposited row wise: the c declaration is ``[y][x]``, the x index runs fastest,
  which ASAM calls ``ROW_DIR``
* a linear conversion becomes a ``COMPU_METHOD`` of type ``RAT_FUNC``.  Its
  ``COEFFS a b c d e f`` describe ``raw = (a*phys^2 + b*phys + c) / (d*phys^2 + e*phys + f)``,
  so ``phys = raw * factor + offset`` is written as ``COEFFS 0 1 -offset 0 0 factor``
* an enum conversion becomes a ``COMPU_METHOD`` of type ``TAB_VERB`` plus a ``COMPU_VTAB``
* every component becomes a ``GROUP`` referencing the objects it declares
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ddd.backends.a2l.options import A2lOptions
from ddd.backends.a2l.types import A2L_TYPE
from ddd.ir import DataDictionary, ResolvedComponent, ResolvedLeaf, ResolvedObject
from ddd.models import (
    Conversion,
    Datatype,
    EnumConversion,
    IdentityConversion,
    LinearConversion,
    ObjectKind,
    format_number,
)

NO_COMPU_METHOD = "NO_COMPU_METHOD"
NO_INPUT_QUANTITY = "NO_INPUT_QUANTITY"

A2L_MATRIX_DIM_RANK = 3
"""Number of dimensions ``MATRIX_DIM`` carries in ASAP2 1.6.1."""

_CHARACTERISTIC_TYPE = {
    ObjectKind.PARAMETER: "VALUE",
    ObjectKind.VALUE_BLOCK: "VAL_BLK",
    ObjectKind.CURVE: "CURVE",
    ObjectKind.MAP: "MAP",
}


@dataclass(frozen=True, slots=True)
class CompuVtabView:
    name: str
    description: str
    entries: tuple[tuple[int, str], ...]


@dataclass(frozen=True, slots=True)
class CompuMethodView:
    name: str
    description: str
    conversion_type: str
    format: str
    unit: str
    coeffs: tuple[str, ...] | None = None
    vtab: str | None = None


@dataclass(frozen=True, slots=True)
class RecordLayoutView:
    name: str
    entry: str
    """The single layout line, e.g. ``FNC_VALUES 1 UBYTE ROW_DIR DIRECT``."""


@dataclass(frozen=True, slots=True)
class MeasurementView:
    name: str
    description: str
    datatype: str
    compu_method: str
    lower: str
    upper: str
    address: str
    matrix_dim: str | None
    format: str | None
    display_identifier: str | None
    component: str
    condition: str | None
    """Preprocessor condition of the object; a2l cannot express it, so it is a comment."""


@dataclass(frozen=True, slots=True)
class AxisDescrView:
    attribute: str
    input_quantity: str
    compu_method: str
    max_points: int
    lower: str
    upper: str
    axis_ref: str


@dataclass(frozen=True, slots=True)
class CharacteristicView:
    name: str
    description: str
    type: str
    address: str
    deposit: str
    compu_method: str
    lower: str
    upper: str
    matrix_dim: str | None
    format: str | None
    display_identifier: str | None
    axis_descrs: tuple[AxisDescrView, ...]
    condition: str | None


@dataclass(frozen=True, slots=True)
class AxisPtsView:
    name: str
    description: str
    address: str
    input_quantity: str
    deposit: str
    compu_method: str
    max_points: int
    lower: str
    upper: str
    format: str | None
    display_identifier: str | None
    condition: str | None


@dataclass(frozen=True, slots=True)
class SystemConstantView:
    """One ``SYSTEM_CONSTANT`` of the ``MOD_PAR``: a declared constant, value as a string.

    The format quotes both halves, so the value travels as text; every record still spells
    its sizes as resolved numbers, because a ``MATRIX_DIM`` accepts no symbol where it
    expects a count.
    """

    name: str
    value: str


@dataclass(frozen=True, slots=True)
class GroupView:
    name: str
    description: str
    measurements: tuple[str, ...]
    characteristics: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class A2lModel:
    project: str
    description: str
    module: str
    generator: str
    version: str
    byte_order: str
    system_constants: tuple[SystemConstantView, ...]
    """One per declared constant, in name order; the ``MOD_PAR`` is written only when the
    project declares any."""

    compu_methods: tuple[CompuMethodView, ...]
    compu_vtabs: tuple[CompuVtabView, ...]
    record_layouts: tuple[RecordLayoutView, ...]
    measurements: tuple[MeasurementView, ...]
    characteristics: tuple[CharacteristicView, ...]
    axis_pts: tuple[AxisPtsView, ...]
    groups: tuple[GroupView, ...]


def build_a2l_model(dictionary: DataDictionary, options: A2lOptions, generator: str) -> A2lModel:
    """Turn the dictionary into the flat structures used by the a2l template."""
    return _A2lModelBuilder(dictionary, options).build(generator)


class _A2lModelBuilder:
    """Builds the whole a2l model of one dictionary.

    The compu methods and record layouts are *accumulated* while the objects are walked -
    every object may contribute one, and identical ones are shared - so they are state of
    the run rather than something each record can be handed separately. The set of exported
    names and the options belong to the same run, which is why they live here too.
    """

    def __init__(self, dictionary: DataDictionary, options: A2lOptions) -> None:
        self._dictionary = dictionary
        self._options = options
        self._by_name = dictionary.by_name
        self._exported = self._resolve_exported()
        self._instances_exported = {
            entry.name: entry.a2l.exported for entry in dictionary.instances
        }
        self._methods = _CompuMethodBuilder()
        self._layouts = _RecordLayoutBuilder()

    def build(self, generator: str) -> A2lModel:
        dictionary = self._dictionary
        measurements: list[MeasurementView] = []
        characteristics: list[CharacteristicView] = []
        axis_pts: list[AxisPtsView] = []

        for entry in dictionary.objects:
            if entry.name not in self._exported:
                continue
            if entry.kind is ObjectKind.MEASUREMENT:
                measurements.append(self._measurement(entry))
            elif entry.kind is ObjectKind.AXIS:
                axis_pts.append(self._axis_pts(entry))
            else:
                characteristics.append(self._characteristic(entry))

        for leaf in dictionary.leaves:
            if not self._carries(leaf):
                continue
            if leaf.kind is ObjectKind.MEASUREMENT:
                measurements.append(self._measurement(leaf))
            else:
                characteristics.append(self._leaf_characteristic(leaf))

        groups = [
            group
            for group in (self._group(component) for component in dictionary.components)
            if group is not None
        ]

        return A2lModel(
            project=dictionary.name,
            description=dictionary.description or dictionary.name,
            module=dictionary.name,
            generator=generator,
            version=self._options.version,
            byte_order=self._options.byte_order.a2l,
            system_constants=tuple(
                SystemConstantView(name=entry.name, value=str(entry.value))
                for entry in dictionary.constants
            ),
            compu_methods=self._methods.methods(),
            compu_vtabs=self._methods.vtabs(),
            record_layouts=self._layouts.layouts(),
            measurements=tuple(measurements),
            characteristics=tuple(characteristics),
            axis_pts=tuple(axis_pts),
            groups=tuple(groups),
        )

    def _resolve_exported(self) -> set[str]:
        """Names that end up in the a2l, including what an exported object refers to.

        Every reference an exported record makes has to resolve inside the same file: an
        ``AXIS_PTS_REF`` to an axis that was kept out, or an input quantity naming a
        measurement that was, is a dangling reference and makes the file invalid rather than
        smaller. An object is therefore pulled back in by whoever points at it, transitively -
        a curve pulls its axis, and that axis pulls the measurement it is indexed by.
        """
        by_name = self._by_name
        names = {entry.name for entry in self._dictionary.objects if entry.a2l.exported}
        pending = list(names)
        while pending:
            # Everything in `names` is a key of `by_name`: the initial set comes from the
            # objects themselves, and the only other way in is the membership test below.
            entry = by_name[pending.pop()]
            for referenced in entry.references.values():
                if referenced not in names and referenced in by_name:
                    names.add(referenced)
                    pending.append(referenced)
        return names

    def _carries(self, leaf: ResolvedLeaf) -> bool:
        """Whether this member can be described at all, and was asked to be.

        A bitfield cannot. ``&s.ready`` does not compile, so no build can report an address for
        it, and ``SYMBOL_LINK`` carries a byte offset with nowhere to put a bit position -
        leaving the mask out means the whole word and writing zero means nothing, so both are
        wrong answers dressed up as output. Such a member waits for a build that reports where
        its bits are; the analysis says so once per object it happens to.
        """
        if leaf.bits is not None:
            return False
        return leaf.a2l.exported and self._instances_exported.get(leaf.instance, True)

    def _leaf_characteristic(self, leaf: ResolvedLeaf) -> CharacteristicView:
        """A calibratable member, which is a ``VALUE`` or a ``VAL_BLK`` and never a curve.

        A member refers to no other object - a structure cannot hold an axis reference - so the
        two table shapes cannot arise here and there is no ``AXIS_DESCR`` to write.
        """
        return CharacteristicView(
            name=leaf.path,
            description=leaf.description or leaf.path,
            type="VAL_BLK" if leaf.shape else "VALUE",
            address=self._options.address_of(leaf.path),
            deposit=self._layouts.values(leaf.datatype),
            compu_method=self._methods.reference(leaf),
            lower=format_number(leaf.limits.min),
            upper=format_number(leaf.limits.max),
            matrix_dim=_matrix_dim(leaf) if leaf.shape else None,
            format=leaf.a2l.format,
            display_identifier=leaf.a2l.display_identifier,
            axis_descrs=(),
            condition=leaf.condition,
        )

    def _measurement(self, entry: ResolvedObject | ResolvedLeaf) -> MeasurementView:
        return MeasurementView(
            name=entry.name,
            description=entry.description or entry.name,
            datatype=A2L_TYPE[entry.datatype],
            compu_method=self._methods.reference(entry),
            lower=format_number(entry.limits.min),
            upper=format_number(entry.limits.max),
            address=self._options.address_of(entry.name),
            matrix_dim=_matrix_dim(entry),
            format=entry.a2l.format,
            display_identifier=entry.a2l.display_identifier,
            component=entry.owner or "",
            condition=entry.condition,
        )

    def _characteristic(self, entry: ResolvedObject) -> CharacteristicView:
        references = entry.references
        axes = [references[key] for key in ("axis", "x_axis", "y_axis") if key in references]
        return CharacteristicView(
            name=entry.name,
            description=entry.description or entry.name,
            type=_CHARACTERISTIC_TYPE[entry.kind],
            address=self._options.address_of(entry.name),
            deposit=self._layouts.values(entry.datatype),
            compu_method=self._methods.reference(entry),
            lower=format_number(entry.limits.min),
            upper=format_number(entry.limits.max),
            matrix_dim=_matrix_dim(entry) if entry.kind is ObjectKind.VALUE_BLOCK else None,
            format=entry.a2l.format,
            display_identifier=entry.a2l.display_identifier,
            axis_descrs=tuple(
                descr
                for name in axes
                if (descr := self._axis_descr(self._by_name.get(name), name)) is not None
            ),
            condition=entry.condition,
        )

    def _axis_descr(self, axis: ResolvedObject | None, name: str) -> AxisDescrView | None:
        if axis is None:
            return None
        return AxisDescrView(
            attribute="COM_AXIS",
            input_quantity=axis.references.get("input") or NO_INPUT_QUANTITY,
            compu_method=self._methods.reference(axis),
            max_points=axis.shape[0] if axis.shape else 0,
            lower=format_number(axis.limits.min),
            upper=format_number(axis.limits.max),
            axis_ref=name,
        )

    def _axis_pts(self, entry: ResolvedObject) -> AxisPtsView:
        return AxisPtsView(
            name=entry.name,
            description=entry.description or entry.name,
            address=self._options.address_of(entry.name),
            input_quantity=entry.references.get("input") or NO_INPUT_QUANTITY,
            deposit=self._layouts.axis(entry.datatype),
            compu_method=self._methods.reference(entry),
            max_points=entry.shape[0] if entry.shape else 0,
            lower=format_number(entry.limits.min),
            upper=format_number(entry.limits.max),
            format=entry.a2l.format,
            display_identifier=entry.a2l.display_identifier,
            condition=entry.condition,
        )

    def _group(self, component: ResolvedComponent) -> GroupView | None:
        """What one component contributes to the file, by name.

        A structured variable contributes its members rather than itself: there is no record
        called ``Inlet``, so a group naming it would be a reference to nothing - and a
        calibration tool drops one of those without a word.
        """
        by_name = self._by_name
        declared = {entry.name for entry in component.declarations}
        names = [entry.name for entry in component.declarations if entry.name in self._exported]
        measurements = [n for n in names if by_name[n].kind is ObjectKind.MEASUREMENT]
        characteristics = [n for n in names if by_name[n].kind is not ObjectKind.MEASUREMENT]
        for leaf in self._dictionary.leaves:
            if leaf.instance not in declared or not self._carries(leaf):
                continue
            target = measurements if leaf.kind is ObjectKind.MEASUREMENT else characteristics
            target.append(leaf.path)
        if not measurements and not characteristics:
            return None
        return GroupView(
            name=component.name,
            description=component.description or component.name,
            measurements=tuple(measurements),
            characteristics=tuple(characteristics),
        )


def _matrix_dim(entry: ResolvedObject | ResolvedLeaf) -> str | None:
    """``MATRIX_DIM x y z``, where ``x`` is the index that runs fastest.

    The dictionary carries the shape in c declaration order, in which the *last* index runs
    fastest: ``uint8_t t[2][3]`` is two rows of three. ASAP2 lists the fastest index first,
    so the dimensions are reversed here - emitting them unchanged would describe a
    transposed object and every calibration tool would address the wrong element. 1.6.1
    wants exactly three values, so the unused dimensions are filled with 1; an object with
    more than three dimensions keeps all of them, which only 1.7 can read (the analysis
    reports it as ``a2l-unrepresentable``).
    """
    if not entry.shape:
        return None
    dims = list(reversed(entry.shape))
    dims += [1] * (A2L_MATRIX_DIM_RANK - len(dims))
    return " ".join(str(dim) for dim in dims)


class _RecordLayoutBuilder:
    """Creates one RECORD_LAYOUT per datatype and storage category."""

    def __init__(self) -> None:
        self._layouts: dict[str, RecordLayoutView] = {}

    def values(self, datatype: Datatype) -> str:
        return self._add(
            f"RL_VALUES_{A2L_TYPE[datatype]}", f"FNC_VALUES 1 {A2L_TYPE[datatype]} ROW_DIR DIRECT"
        )

    def axis(self, datatype: Datatype) -> str:
        return self._add(
            f"RL_AXIS_{A2L_TYPE[datatype]}", f"AXIS_PTS_X 1 {A2L_TYPE[datatype]} INDEX_INCR DIRECT"
        )

    def _add(self, name: str, entry: str) -> str:
        self._layouts.setdefault(name, RecordLayoutView(name, entry))
        return name

    def layouts(self) -> tuple[RecordLayoutView, ...]:
        return tuple(sorted(self._layouts.values(), key=lambda layout: layout.name))


class _CompuMethodBuilder:
    """Creates one COMPU_METHOD per distinct (conversion, unit) combination."""

    def __init__(self) -> None:
        self._methods: dict[object, CompuMethodView] = {}
        self._vtabs: dict[str, CompuVtabView] = {}
        self._names: set[str] = set()

    def reference(self, entry: ResolvedObject | ResolvedLeaf) -> str:
        conversion = entry.conversion
        unit = entry.unit
        if isinstance(conversion, IdentityConversion) and not unit:
            return NO_COMPU_METHOD

        key = _conversion_key(conversion, unit)
        existing = self._methods.get(key)
        if existing is not None:
            return existing.name

        method = self._create(conversion, unit, entry.datatype)
        self._methods[key] = method
        return method.name

    def _create(self, conversion: Conversion, unit: str, datatype: Datatype) -> CompuMethodView:
        if isinstance(conversion, EnumConversion):
            vtab = self._vtab(conversion)
            return CompuMethodView(
                name=self._unique(f"CM_{conversion.name}"),
                description=f"verbal conversion for {conversion.name}",
                conversion_type="TAB_VERB",
                format="%8.0",
                unit=unit,
                vtab=vtab.name,
            )
        if isinstance(conversion, LinearConversion):
            return CompuMethodView(
                name=self._unique(f"CM_LIN_{_slug(unit)}"),
                description=(
                    f"phys = raw * {format_number(conversion.factor)}"
                    f" + {format_number(conversion.offset)}"
                ),
                conversion_type="RAT_FUNC",
                format=_default_format(datatype, conversion),
                unit=unit,
                coeffs=(
                    "0",
                    "1",
                    format_number(-conversion.offset),
                    "0",
                    "0",
                    format_number(conversion.factor),
                ),
            )
        return CompuMethodView(
            name=self._unique(f"CM_IDENT_{_slug(unit)}"),
            description=f"physical value in {unit}" if unit else "identity",
            conversion_type="IDENTICAL",
            format=_default_format(datatype, conversion),
            unit=unit,
        )

    def _vtab(self, conversion: EnumConversion) -> CompuVtabView:
        name = f"VTAB_{conversion.name}"
        existing = self._vtabs.get(name)
        if existing is not None:
            return existing
        vtab = CompuVtabView(
            name=self._unique(name),
            description=f"values of {conversion.name}",
            entries=tuple((e.value, e.name) for e in conversion.enumerators),
        )
        self._vtabs[name] = vtab
        return vtab

    def _unique(self, base: str) -> str:
        candidate = base
        index = 1
        while candidate in self._names:
            index += 1
            candidate = f"{base}_{index}"
        self._names.add(candidate)
        return candidate

    def methods(self) -> tuple[CompuMethodView, ...]:
        return tuple(sorted(self._methods.values(), key=lambda method: method.name))

    def vtabs(self) -> tuple[CompuVtabView, ...]:
        return tuple(sorted(self._vtabs.values(), key=lambda vtab: vtab.name))


def _conversion_key(conversion: Conversion, unit: str) -> object:
    if isinstance(conversion, EnumConversion):
        return ("enum", conversion.name, unit)
    if isinstance(conversion, LinearConversion):
        return ("linear", conversion.factor, conversion.offset, unit)
    return ("identity", unit)


def _default_format(datatype: Datatype, conversion: Conversion) -> str:
    integral = datatype.is_integer or datatype is Datatype.BOOLEAN
    if isinstance(conversion, LinearConversion):
        integral = integral and conversion.factor.is_integer() and conversion.offset.is_integer()
    return "%8.0" if integral else "%8.3"


_UNIT_WORDS = {
    "%": "PCT",
    "°": "DEG",
    "µ": "MICRO",
    "Ω": "OHM",
    "/": "_PER_",
    "*": "_",
    ".": "_",
    "^": "",
    "-": "_",
}


def _slug(unit: str) -> str:
    """Turn a unit such as ``m/s^2`` into the identifier fragment ``M_PER_S2``."""
    text = "".join(_UNIT_WORDS.get(character, character) for character in unit)
    text = re.sub(r"[^0-9A-Za-z_]+", "_", text).upper()
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "NONE"


def a2l_string(text: str) -> str:
    """Escape a string for an a2l double quoted literal.

    Backslash and quote are escaped, and every control character - carriage return and tab
    as much as newline - becomes a space: a literal that spans a line makes some parsers
    stop mid-file and others read the rest of the record as text.
    """
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return "".join(
        " " if character < " " or character == "\x7f" else character for character in escaped
    )
