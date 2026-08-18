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
from ddd.backends.c.types import C_TYPE, needs_stdbool, needs_stdint
from ddd.ir import (
    DataDictionary,
    ResolvedComponent,
    ResolvedInstance,
    ResolvedObject,
    ResolvedStruct,
)
from ddd.models import EnumConversion, ObjectKind, Scope

UNRESOLVED_GROUP = "<unresolved>"


@dataclass(frozen=True, slots=True)
class ObjectView:
    """One data object, prepared for the c templates."""

    name: str
    kind: ObjectKind
    c_type: str
    array_suffix: str
    constant: bool
    """Whether the object is calibration data, which is generated ``const``."""

    volatile: bool
    """Whether the declaration carries ``volatile``, which the object states for itself."""

    initializer: str | None
    comment: str | None
    condition: str | None
    owner: str
    consumers: tuple[str, ...]

    section: str | None = None
    """Linker section the producing declaration placed the object in, or ``None``.

    The name alone: how a section attribute is spelled - ``__attribute__``, a pragma - is
    the toolchain's business and therefore the templates', exactly like the rest of the
    house style.
    """

    @property
    def qualifier(self) -> str:
        """``"const volatile "``, ``"const "``, ``"volatile "`` or the empty string.

        The two are independent and both are ordinary for calibration data: ``const`` says the
        software never writes it, ``volatile`` says something outside the software does. Built
        from the two answers rather than chosen between them, because a chain of ``elif`` is
        how ``const`` used to silently swallow the ``volatile`` a parameter asked for.
        """
        return ("const " if self.constant else "") + ("volatile " if self.volatile else "")

    @property
    def definition(self) -> str:
        """``volatile uint16_t Speed[4] = { ... }``, without the trailing semicolon."""
        text = f"{self.qualifier}{self.c_type} {self.name}{self.array_suffix}"
        if self.initializer is not None:
            text += f" = {self.initializer}"
        return text

    def declaration(self, *, const: bool = False) -> str:
        """``extern const volatile uint16_t Speed[4]``, without the trailing semicolon."""
        # Calibration data already carries const, and c refuses a repeated qualifier.
        prefix = "const " if const and not self.constant else ""
        return f"extern {prefix}{self.qualifier}{self.c_type} {self.name}{self.array_suffix}"


@dataclass(frozen=True, slots=True)
class MemberView:
    """One member of a structure, prepared for the c templates."""

    name: str
    c_type: str
    """The spelling of the member's type: ``uint16_t``, or the name of another structure."""

    array_suffix: str
    bits: int | None
    comment: str | None

    @property
    def declaration(self) -> str:
        """``uint16_t history[8]`` or ``uint16_t ready : 1``, without the semicolon.

        Composed here rather than in the template because the width of a bitfield goes after
        the declarator and not after the type, which is a rule about c rather than about house
        style - and getting it wrong produces a header that does not compile.
        """
        text = f"{self.c_type} {self.name}{self.array_suffix}"
        return f"{text} : {self.bits}" if self.bits is not None else text


@dataclass(frozen=True, slots=True)
class StructView:
    """One structure, prepared for the c templates."""

    name: str
    comment: str | None
    members: tuple[MemberView, ...]


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
    """A normalised include guard offered to the template, which may ignore it."""

    outputs: tuple[DeclarationView, ...]
    inputs: tuple[DeclarationView, ...]
    locals: tuple[DeclarationView, ...]

    @property
    def is_empty(self) -> bool:
        return not (self.outputs or self.inputs or self.locals)


@dataclass(frozen=True, slots=True)
class ConstantView:
    """One declared constant, for the templates to emit however the house style spells one.

    The shipped example templates write each as a ``#define`` in the types header, so that
    the arrays the generated code dimensions by the name compile against the same header
    that declares them.
    """

    name: str
    value: int
    description: str
    """Already safe to put in a comment; empty when the constant states none."""


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
    constants: tuple[ConstantView, ...]
    """The declared constants, in name order; empty when the project declares none.

    Offered so the templates can emit them - an object dimensioned by a constant spells the
    constant's name in its definition and every declaration, and that name has to be
    declared before the first array that uses it.
    """

    enums: tuple[EnumView, ...]
    structures: tuple[StructView, ...]
    """The structures the project declares, each after every structure it nests.

    A template may loop over them and write each one out as it comes: c needs a nested
    structure to be complete first, and the order here already guarantees it.
    """

    groups: tuple[ComponentGroup, ...]
    sections: tuple[SectionGroup, ...]
    """Placed objects grouped per linker section, strictest alignment first; empty when the
    project places nothing."""

    headers: tuple[ComponentHeaderView, ...]
    needs_stdint: bool
    needs_stdbool: bool

    def guard(self, *parts: str) -> str:
        """An include guard built out of ``parts``, e.g. ``model.guard('ddd', 'globals')``.

        Offered rather than imposed: a template that wants a guard of its own writes one, and
        this only spares it the normalisation - upper casing, replacing what is not a letter
        or a digit, and keeping a leading digit out of the macro name.
        """
        return guard_name(*parts)


@dataclass(frozen=True, slots=True)
class SectionGroup:
    """Every placed object of one linker section, strictest alignment first.

    The order is the point: data of one section emitted strictest first packs without
    padding, and names break ties so that the output is deterministic. Objects without a
    section are not here - they stay in their component's group and the toolchain's default
    placement.
    """

    name: str
    objects: tuple[ObjectView, ...]


def _section_groups(
    dictionary: DataDictionary, views: dict[str, ObjectView]
) -> tuple[SectionGroup, ...]:
    structures = {entry.name: entry for entry in dictionary.types}

    def alignment(name: str) -> int:
        # The dictionary's types are dependency ordered and acyclic by construction, and a
        # placed instance names a structure the analysis resolved: the lookup cannot miss.
        entry = structures[name]
        strictest = 1
        for member in entry.members:
            if member.datatype is not None:
                strictest = max(strictest, member.datatype.size)
            else:
                assert member.type is not None
                strictest = max(strictest, alignment(member.type))
        return strictest

    def needed(entry: ResolvedObject | ResolvedInstance) -> int:
        if isinstance(entry, ResolvedInstance):
            return alignment(entry.type)
        return entry.datatype.size

    placed: dict[str, list[tuple[int, str]]] = {}
    entries: tuple[ResolvedObject | ResolvedInstance, ...] = (
        *dictionary.objects,
        *dictionary.instances,
    )
    for entry in entries:
        if entry.section is not None:
            placed.setdefault(entry.section, []).append((needed(entry), entry.name))
    return tuple(
        SectionGroup(
            name=name,
            objects=tuple(
                views[object_name]
                for _, object_name in sorted(placed[name], key=lambda pair: (-pair[0], pair[1]))
            ),
        )
        for name in sorted(placed)
    )


def build_code_model(dictionary: DataDictionary, options: COptions, generator: str) -> CodeModel:
    """Turn the dictionary into the flat structures used by the templates."""
    views: dict[str, ObjectView] = {entry.name: _object_view(entry) for entry in dictionary.objects}
    views.update({entry.name: _instance_view(entry) for entry in dictionary.instances})

    groups = [
        group
        for group in (
            _group(
                component.name,
                component.description,
                dictionary.owned_by(component.name) + dictionary.instances_owned_by(component.name),
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
        constants=tuple(
            ConstantView(
                name=entry.name,
                value=entry.value,
                description=sanitize_comment(entry.description),
            )
            for entry in dictionary.constants
        ),
        enums=tuple(_enum_view(enum) for enum in dictionary.enums),
        structures=tuple(_struct_view(entry) for entry in dictionary.types),
        groups=tuple(groups),
        sections=_section_groups(dictionary, views),
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


def _struct_view(entry: ResolvedStruct) -> StructView:
    return StructView(
        name=entry.name,
        comment=sanitize_comment(entry.description) or None,
        members=tuple(
            MemberView(
                name=member.name,
                # One of the two is always set: a member is spelled with a base datatype or it
                # is another structure, and the analysis has already worked out which.
                c_type=C_TYPE[member.datatype] if member.datatype is not None else str(member.type),
                array_suffix=declarator_suffix(member.shape),
                bits=member.bits,
                comment=sanitize_comment(member.description) or None,
            )
            for member in entry.members
        ),
    )


def _group(
    name: str,
    description: str,
    owned: tuple[ResolvedObject | ResolvedInstance, ...],
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


def _instance_view(entry: ResolvedInstance) -> ObjectView:
    """A structured variable, which declares exactly like any other - with a longer type name.

    It has no initialiser: what a structure starts as is written by the code that starts it,
    which is why the contract refuses ``init`` on one.
    """
    return ObjectView(
        name=entry.name,
        kind=entry.kind,
        c_type=entry.type,
        # The spelled shape, so an array dimensioned by a constant is declared by its name.
        array_suffix=declarator_suffix(entry.spelled_shape),
        constant=entry.is_calibration,
        volatile=entry.volatile,
        initializer=None,
        comment=sanitize_comment(entry.description) or None,
        condition=entry.condition,
        owner=entry.owner or UNRESOLVED_GROUP,
        consumers=entry.consumers,
        section=entry.section,
    )


def _object_view(entry: ResolvedObject) -> ObjectView:
    return ObjectView(
        name=entry.name,
        kind=entry.kind,
        c_type=c_type(entry),
        # The spelled shape, so an array dimensioned by a constant is declared by its name;
        # the initialiser below still lays its braces out over the numeric shape.
        array_suffix=declarator_suffix(entry.spelled_shape),
        constant=entry.is_calibration,
        volatile=entry.volatile,
        initializer=initializer_of(entry),
        comment=doc_comment(entry),
        condition=entry.condition,
        owner=entry.owner or UNRESOLVED_GROUP,
        consumers=entry.consumers,
        section=entry.section,
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
        guard=guard_name("ddd", "component", component.name),
        outputs=tuple(buckets[Scope.OUTPUT]),
        inputs=tuple(buckets[Scope.INPUT]),
        locals=tuple(buckets[Scope.LOCAL]),
    )
