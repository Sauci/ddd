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
from ddd.ir import DataDictionary, ResolvedComponent, ResolvedObject
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
    compu_methods: tuple[CompuMethodView, ...]
    compu_vtabs: tuple[CompuVtabView, ...]
    record_layouts: tuple[RecordLayoutView, ...]
    measurements: tuple[MeasurementView, ...]
    characteristics: tuple[CharacteristicView, ...]
    axis_pts: tuple[AxisPtsView, ...]
    groups: tuple[GroupView, ...]


def build_a2l_model(dictionary: DataDictionary, options: A2lOptions, generator: str) -> A2lModel:
    """Turn the dictionary into the flat structures used by the a2l template.

    An axis referenced by an exported curve or map is always exported, even when its own
    ``a2l.export`` is false: an ``AXIS_PTS_REF`` without the ``AXIS_PTS`` it points at would
    not be a valid a2l file.
    """
    by_name = dictionary.by_name
    exported = _exported(dictionary)
    methods = _CompuMethodBuilder()
    layouts = _RecordLayoutBuilder()

    measurements: list[MeasurementView] = []
    characteristics: list[CharacteristicView] = []
    axis_pts: list[AxisPtsView] = []

    for entry in dictionary.objects:
        if entry.name not in exported:
            continue
        if entry.kind is ObjectKind.MEASUREMENT:
            measurements.append(_measurement(entry, methods, options))
        elif entry.kind is ObjectKind.AXIS:
            axis_pts.append(_axis_pts(entry, methods, layouts, options))
        else:
            characteristics.append(_characteristic(entry, by_name, methods, layouts, options))

    groups = [
        group
        for group in (_group(component, exported, by_name) for component in dictionary.components)
        if group is not None
    ]

    return A2lModel(
        project=dictionary.name,
        description=dictionary.description or dictionary.name,
        module=dictionary.name,
        generator=generator,
        version=options.version,
        byte_order=options.byte_order.a2l,
        compu_methods=methods.methods(),
        compu_vtabs=methods.vtabs(),
        record_layouts=layouts.layouts(),
        measurements=tuple(measurements),
        characteristics=tuple(characteristics),
        axis_pts=tuple(axis_pts),
        groups=tuple(groups),
    )


def _exported(dictionary: DataDictionary) -> set[str]:
    """Names that end up in the a2l, including axes pulled in by curves and maps."""
    names = {entry.name for entry in dictionary.objects if entry.a2l.export}
    for entry in dictionary.objects:
        if entry.name in names and entry.kind in (ObjectKind.CURVE, ObjectKind.MAP):
            names.update(entry.references.values())
    return names


def _measurement(
    entry: ResolvedObject, methods: _CompuMethodBuilder, options: A2lOptions
) -> MeasurementView:
    return MeasurementView(
        name=entry.name,
        description=entry.description or entry.name,
        datatype=A2L_TYPE[entry.datatype],
        compu_method=methods.reference(entry),
        lower=format_number(entry.limits.min),
        upper=format_number(entry.limits.max),
        address=options.address_of(entry.name),
        matrix_dim=_matrix_dim(entry),
        format=entry.a2l.format,
        display_identifier=entry.a2l.display_identifier,
        component=entry.owner or "",
        condition=entry.condition,
    )


def _characteristic(
    entry: ResolvedObject,
    by_name: dict[str, ResolvedObject],
    methods: _CompuMethodBuilder,
    layouts: _RecordLayoutBuilder,
    options: A2lOptions,
) -> CharacteristicView:
    references = entry.references
    axes = [references[key] for key in ("axis", "x_axis", "y_axis") if key in references]
    return CharacteristicView(
        name=entry.name,
        description=entry.description or entry.name,
        type=_CHARACTERISTIC_TYPE[entry.kind],
        address=options.address_of(entry.name),
        deposit=layouts.values(entry.datatype),
        compu_method=methods.reference(entry),
        lower=format_number(entry.limits.min),
        upper=format_number(entry.limits.max),
        matrix_dim=_matrix_dim(entry) if entry.kind is ObjectKind.VALUE_BLOCK else None,
        format=entry.a2l.format,
        display_identifier=entry.a2l.display_identifier,
        axis_descrs=tuple(
            descr
            for name in axes
            if (descr := _axis_descr(by_name.get(name), name, methods)) is not None
        ),
        condition=entry.condition,
    )


def _axis_descr(
    axis: ResolvedObject | None, name: str, methods: _CompuMethodBuilder
) -> AxisDescrView | None:
    if axis is None:
        return None
    return AxisDescrView(
        attribute="COM_AXIS",
        input_quantity=axis.references.get("input") or NO_INPUT_QUANTITY,
        compu_method=methods.reference(axis),
        max_points=axis.shape[0] if axis.shape else 0,
        lower=format_number(axis.limits.min),
        upper=format_number(axis.limits.max),
        axis_ref=name,
    )


def _axis_pts(
    entry: ResolvedObject,
    methods: _CompuMethodBuilder,
    layouts: _RecordLayoutBuilder,
    options: A2lOptions,
) -> AxisPtsView:
    return AxisPtsView(
        name=entry.name,
        description=entry.description or entry.name,
        address=options.address_of(entry.name),
        input_quantity=entry.references.get("input") or NO_INPUT_QUANTITY,
        deposit=layouts.axis(entry.datatype),
        compu_method=methods.reference(entry),
        max_points=entry.shape[0] if entry.shape else 0,
        lower=format_number(entry.limits.min),
        upper=format_number(entry.limits.max),
        format=entry.a2l.format,
        display_identifier=entry.a2l.display_identifier,
        condition=entry.condition,
    )


def _group(
    component: ResolvedComponent, exported: set[str], by_name: dict[str, ResolvedObject]
) -> GroupView | None:
    names = [entry.name for entry in component.declarations if entry.name in exported]
    if not names:
        return None
    return GroupView(
        name=component.name,
        description=component.description or component.name,
        measurements=tuple(n for n in names if by_name[n].kind is ObjectKind.MEASUREMENT),
        characteristics=tuple(n for n in names if by_name[n].kind is not ObjectKind.MEASUREMENT),
    )


def _matrix_dim(entry: ResolvedObject) -> str | None:
    return " ".join(str(dim) for dim in entry.shape) if entry.shape else None


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

    def reference(self, entry: ResolvedObject) -> str:
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
    integral = datatype.is_integer or datatype is Datatype.BOOL
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
    """Escape a string for an a2l double quoted literal."""
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
