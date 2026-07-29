"""Turning the data dictionary into the flat structures the c templates read."""

from __future__ import annotations

from dataclasses import dataclass

from ddd.backends.c.literals import (
    c_type,
    declarator_suffix,
    doc_comment,
    guard_name,
    initializer_of,
    sanitize_comment,
)
from ddd.backends.c.options import COptions
from ddd.backends.c.types import needs_stdbool, needs_stdint
from ddd.ir import DataDictionary, ResolvedComponent, ResolvedObject
from ddd.models import EnumConversion, ObjectKind, Scope

UNRESOLVED_GROUP = "<unresolved>"


@dataclass(frozen=True, slots=True)
class ObjectView:
    """One data object, prepared for the c templates."""

    name: str
    kind: ObjectKind
    c_type: str
    array_suffix: str
    qualifier: str
    """``"volatile "``, ``"const "`` or the empty string."""

    initializer: str | None
    comment: str | None
    condition: str | None
    owner: str
    consumers: tuple[str, ...]

    @property
    def definition(self) -> str:
        """``volatile uint16_t Speed[4] = { ... }``, without the trailing semicolon."""
        text = f"{self.qualifier}{self.c_type} {self.name}{self.array_suffix}"
        if self.initializer is not None:
            text += f" = {self.initializer}"
        return text

    def declaration(self, *, const: bool = False) -> str:
        """``extern const volatile uint16_t Speed[4]``, without the trailing semicolon."""
        # Calibration data already carries const, adding a second one does not compile.
        prefix = "const " if const and "const " not in self.qualifier else ""
        return f"extern {prefix}{self.qualifier}{self.c_type} {self.name}{self.array_suffix}"


@dataclass(frozen=True, slots=True)
class ComponentGroup:
    """The data objects owned by one component, split into ram and calibration data."""

    name: str
    description: str
    measurements: tuple[ObjectView, ...]
    calibration: tuple[ObjectView, ...]

    @property
    def variables(self) -> tuple[ObjectView, ...]:
        return self.measurements + self.calibration


@dataclass(frozen=True, slots=True)
class DeclarationView:
    """One entry of a component header."""

    variable: ObjectView
    condition: str | None
    const: bool

    @property
    def line(self) -> str:
        return self.variable.declaration(const=self.const) + ";"


@dataclass(frozen=True, slots=True)
class ComponentHeaderView:
    """The interface header generated for one component."""

    name: str
    description: str
    guard: str
    filename: str
    outputs: tuple[DeclarationView, ...]
    inputs: tuple[DeclarationView, ...]
    locals: tuple[DeclarationView, ...]

    @property
    def is_empty(self) -> bool:
        return not (self.outputs or self.inputs or self.locals)


@dataclass(frozen=True, slots=True)
class EnumeratorView:
    """One enumerator, with its documentation already safe to put in a comment."""

    name: str
    value: int
    description: str


@dataclass(frozen=True, slots=True)
class EnumView:
    """One ``typedef enum`` of the generated types header."""

    name: str
    enumerators: tuple[EnumeratorView, ...]


@dataclass(frozen=True, slots=True)
class CodeModel:
    """Everything the c templates need."""

    project: str
    source: str
    generator: str
    options: COptions
    enums: tuple[EnumView, ...]
    groups: tuple[ComponentGroup, ...]
    headers: tuple[ComponentHeaderView, ...]
    needs_stdint: bool
    needs_stdbool: bool

    @property
    def types_guard(self) -> str:
        return guard_name(self.options.prefix, "types")

    @property
    def globals_guard(self) -> str:
        return guard_name(self.options.prefix, "globals")


def build_code_model(dictionary: DataDictionary, options: COptions, generator: str) -> CodeModel:
    """Turn the dictionary into the flat structures used by the templates."""
    views = {entry.name: _object_view(entry) for entry in dictionary.objects}

    groups = [
        group
        for group in (
            _group(
                component.name,
                component.description,
                dictionary.owned_by(component.name),
                views,
            )
            for component in dictionary.components
        )
        if group is not None
    ]
    unresolved = _group(
        UNRESOLVED_GROUP,
        "objects that no component declares as output",
        dictionary.unowned(),
        views,
    )
    if unresolved is not None:
        groups.append(unresolved)

    return CodeModel(
        project=dictionary.name,
        source=dictionary.source,
        generator=generator,
        options=options,
        enums=tuple(_enum_view(enum) for enum in dictionary.enums),
        groups=tuple(groups),
        headers=tuple(_header(component, views, options) for component in dictionary.components),
        needs_stdint=needs_stdint(dictionary.datatypes),
        needs_stdbool=needs_stdbool(dictionary.datatypes),
    )


def _enum_view(enum: EnumConversion) -> EnumView:
    return EnumView(
        name=enum.name,
        enumerators=tuple(
            EnumeratorView(
                name=enumerator.name,
                value=enumerator.value,
                # Every text that reaches a comment is defused here rather than in the
                # template: a '*/' in a description would otherwise end the comment and
                # leave the rest of it as code.
                description=sanitize_comment(enumerator.description),
            )
            for enumerator in enum.enumerators
        ),
    )


def _group(
    name: str,
    description: str,
    owned: tuple[ResolvedObject, ...],
    views: dict[str, ObjectView],
) -> ComponentGroup | None:
    if not owned:
        return None
    ordered = sorted(owned, key=lambda entry: entry.name)
    return ComponentGroup(
        name=name,
        description=sanitize_comment(description),
        measurements=tuple(
            views[entry.name] for entry in ordered if entry.kind is ObjectKind.MEASUREMENT
        ),
        calibration=tuple(views[entry.name] for entry in ordered if entry.is_calibration),
    )


def _object_view(entry: ResolvedObject) -> ObjectView:
    if entry.is_calibration:
        qualifier = "const "
    elif entry.volatile:
        qualifier = "volatile "
    else:
        qualifier = ""
    return ObjectView(
        name=entry.name,
        kind=entry.kind,
        c_type=c_type(entry),
        array_suffix=declarator_suffix(entry.shape),
        qualifier=qualifier,
        initializer=initializer_of(entry),
        comment=doc_comment(entry),
        condition=entry.condition,
        owner=entry.owner or UNRESOLVED_GROUP,
        consumers=entry.consumers,
    )


def _header(
    component: ResolvedComponent, views: dict[str, ObjectView], options: COptions
) -> ComponentHeaderView:
    buckets: dict[Scope, list[DeclarationView]] = {scope: [] for scope in Scope}
    for declaration in component.declarations:
        # Every declared name has an entry: the analysis dropped duplicates from both lists.
        buckets[declaration.scope].append(
            DeclarationView(
                variable=views[declaration.name],
                condition=declaration.condition,
                const=options.const_inputs and declaration.scope is Scope.INPUT,
            )
        )
    return ComponentHeaderView(
        name=component.name,
        description=sanitize_comment(component.description),
        # 'component' keeps this guard out of the space of the shared headers: without it a
        # component named 'types' would define DDD_TYPES_H before including ddd_types.h,
        # and the whole types header would preprocess away.
        guard=guard_name(options.prefix, "component", component.name),
        filename=options.component_header(component.name),
        outputs=tuple(buckets[Scope.OUTPUT]),
        inputs=tuple(buckets[Scope.INPUT]),
        locals=tuple(buckets[Scope.LOCAL]),
    )
