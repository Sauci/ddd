"""Turning the data dictionary into the flat structures the c templates read."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ddd.backends.c.literals import (
    c_constant_literal,
    c_type,
    doc_comment,
    guard_name,
    initializer_of,
    sanitize_comment,
    storage_suffix,
)
from ddd.backends.c.options import COptions
from ddd.backends.c.types import C_TYPE, needs_stdbool, needs_stdint
from ddd.ir import (
    DataDictionary,
    ResolvedComponent,
    ResolvedInstance,
    ResolvedMember,
    ResolvedObject,
    ResolvedStruct,
)
from ddd.models import (
    Datatype,
    EnumConversion,
    ObjectKind,
    PointCounts,
    Scope,
    format_shape,
    stored_counts,
)

UNRESOLVED_GROUP = "<unresolved>"


@dataclass(frozen=True, slots=True)
class ObjectView:
    """One data object, prepared for the c templates."""

    name: str
    kind: ObjectKind
    c_type: str
    """The ISO spelling of the object's type: ``uint16_t``, or the declared type of a
    structured variable. The example templates render this one."""

    datatype: str
    """The type as the description spells it: ``uint16``, ``boolean``, or the declared type
    of a structured variable. A project whose platform header already provides these names -
    AUTOSAR's ``Platform_Types.h`` spells them exactly like the dictionary - renders this
    field where the example templates render ``c_type``, and needs no mapping at all."""

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

    dimensions: tuple[int | str, ...] = ()
    """The object's shape as the description spells it, in declaration order: ``(11, 8)`` or
    ``("NY", "NX")`` for a map, ``()`` for a scalar. What ``array_suffix`` was rendered from,
    so a template computing anything from the shape does not parse the suffix back apart."""

    point_counts: tuple[int | str, ...] = ()
    """The counts a table stores ahead of its values, in storage order - x, then y - spelled
    like ``dimensions``; ``()`` for every object that stores none. When it is not empty,
    ``array_suffix`` and ``initializer`` already describe the flat storage."""

    extensions: dict[str, dict[str, Any]] = field(default_factory=dict)
    """The blocks of the project's plugins, keyed by plugin name, exactly as the dictionary
    carries them - a project whose c carries a table derived from a block renders it here."""

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
    """The ISO spelling of the member's type: ``uint16_t``, or the name of another structure
    or external type."""

    datatype: str
    """The member's type as the description spells it: a base datatype name like ``uint16``,
    or - identically to ``c_type`` - the name of another structure or external type, whose
    spelling was the project's own to begin with."""

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
    value: int | float
    """The number the description wrote, as a whole number of either sign or as a float.

    The value, not the spelling: ``2.50`` arrives here as ``2.5`` and ``1e3`` as ``1000.0``,
    since what a description states is a number and what jinja renders is its shortest
    spelling that reads back as the same one. What the spelling did settle is the type, a
    point or an exponent making the value fractional.

    Rendered with ``{{ constant.value }}`` it is the number and nothing else - ``8``,
    ``-40``, ``1.5`` - which is what a template wants that does its own formatting, a
    suffix of the project's own or a cast. It is not always a c literal of the value it
    spells: past the range of a signed ``long long`` there is no such literal to write out,
    so ``{{ constant.literal }}`` beside it is the one to render where the value is simply
    to be emitted.
    """

    description: str
    """Already safe to put in a comment; empty when the constant states none."""

    @property
    def literal(self) -> str:
        """The value as a c literal of the narrowest type that holds it.

        ``8`` and ``-40`` and ``1.5`` come back as themselves; the two ends of the 64 bit
        range do not, because bare they are not the values they read as. C has no negative
        literal, so ``-9223372036854775808`` is a unary minus over a literal too large for
        any signed type - which is a constraint violation, and the reason every
        ``<stdint.h>`` spells ``INT64_MIN`` as ``(-9223372036854775807LL - 1)`` - and
        ``18446744073709551615`` has no signed type at all, so a compiler reads it as
        unsigned and says so. This is the same spelling an ``init`` of that value reaches
        the generated c with.
        """
        return c_constant_literal(self.value)


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
    external_includes: tuple[str, ...] = ()
    """The headers of the external types in use, deduplicated and ready to emit.

    One entry per distinct header named by an external member of any structure of the
    project, spelled the way the ``#include`` line wants it: ``"my_driver.h"`` with the
    quotes for the quoted form, ``<os_types.h>`` as written for the angle form. Sorted by
    the authored spelling, so the output is deterministic; empty when no structure has an
    external member. The example templates emit them in the types header, after the
    standard includes and before the first structure that needs them.
    """

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
    # One answer per type name, kept: the walk below meets a type once per route to it, and a
    # structure holding two of the next one has two routes to every level under it - a project
    # of twenty such levels cost a million visits, and each level after that twice the one
    # before. The types are acyclic by construction, so an answer, once had, is the answer.
    weighed: dict[str, int] = {}

    def alignment(name: str) -> int:
        # The dictionary's types are dependency ordered and acyclic by construction, and a
        # placed instance names a structure the analysis resolved: the lookup cannot miss.
        known = weighed.get(name)
        if known is not None:
            return known
        entry = structures[name]
        strictest = 1
        for member in entry.members:
            if member.datatype is not None:
                strictest = max(strictest, member.datatype.size)
            elif member.type is not None:
                strictest = max(strictest, alignment(member.type))
            # An external member's alignment is unknown, so it contributes nothing to this
            # ordering; the order stays deterministic, which is all the packing heuristic
            # promises - the compiler's word on the real layout is final either way.
        weighed[name] = strictest
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


def _by_owner(dictionary: DataDictionary) -> dict[str, list[ResolvedObject | ResolvedInstance]]:
    """Every owned variable of the project under the component that owns it.

    One walk over the project rather than one per component. Asking the dictionary for the
    objects of a component scans every object there is, and asking it once per component made
    the largest phase of a generation quadratic: a thousand components of fifty objects was
    forty-four million comparisons, four seconds where a hundred components took a twentieth
    of one. The order inside each bucket is the dictionary's own, objects before instances,
    which is what asking twice used to produce - and a group sorts by name anyway.
    """
    owned: dict[str, list[ResolvedObject | ResolvedInstance]] = {}
    entries: tuple[ResolvedObject | ResolvedInstance, ...] = (
        *dictionary.objects,
        *dictionary.instances,
    )
    for entry in entries:
        if entry.owner is not None:
            owned.setdefault(entry.owner, []).append(entry)
    return owned


def build_code_model(dictionary: DataDictionary, options: COptions, generator: str) -> CodeModel:
    """Turn the dictionary into the flat structures used by the templates."""
    views: dict[str, ObjectView] = {entry.name: _object_view(entry) for entry in dictionary.objects}
    views.update({entry.name: _instance_view(entry) for entry in dictionary.instances})

    owned = _by_owner(dictionary)
    groups = [
        group
        for group in (
            _group(
                component.name,
                component.description,
                tuple(owned.get(component.name, ())),
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
        external_includes=_external_includes(dictionary),
    )


def _external_includes(dictionary: DataDictionary) -> tuple[str, ...]:
    """The distinct external-type headers of the project, in the emitted spelling.

    Deduplicated by the authored spelling and sorted by it, so that two external types
    sharing one header cost one include line and the order never depends on which structure
    happened to name one first. The quoted form gains its quotes here - the description
    spells the name bare - and the angle form passes through as written.
    """
    spellings = sorted(
        {
            member.header
            for structure in dictionary.types
            for member in structure.members
            if member.header is not None
        }
    )
    return tuple(
        spelling if spelling.startswith("<") else f'"{spelling}"' for spelling in spellings
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
                c_type=_member_type(member, C_TYPE.__getitem__),
                datatype=_member_type(member, lambda datatype: datatype.value),
                array_suffix=format_shape(member.dimensions),
                bits=member.bits,
                comment=sanitize_comment(member.description) or None,
            )
            for member in entry.members
        ),
    )


def _member_type(member: ResolvedMember, spell: Callable[[Datatype], str]) -> str:
    """The spelling of a member's type: a base datatype, a structure, or an external name.

    ``spell`` decides how a base datatype is written - the ISO table for ``c_type``, the
    datatype's own name for ``datatype``. An external one is spelled verbatim either way -
    the header the types header includes is what defines it, and so is the name of a
    structure: under ``--force`` that name may be one nothing declares, which the run has
    already reported as ``unknown-type`` and which the compiler will ask for in its turn.
    """
    if member.datatype is not None:
        return spell(member.datatype)
    if member.external is not None:
        return member.external
    assert member.type is not None  # the contract states exactly one of the three
    return member.type


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
    return _view(
        entry,
        c_type=entry.type,
        datatype=entry.type,
        initializer=None,
        comment=sanitize_comment(entry.description) or None,
    )


def _object_view(entry: ResolvedObject) -> ObjectView:
    # The initialiser lays its braces out over the numeric shape, whatever the spelling.
    return _view(
        entry,
        c_type=c_type(entry),
        datatype=entry.datatype.value,
        initializer=initializer_of(entry),
        comment=doc_comment(entry),
    )


def _view(
    entry: ResolvedObject | ResolvedInstance,
    *,
    c_type: str,
    datatype: str,
    initializer: str | None,
    comment: str | None,
) -> ObjectView:
    """What a plain object and a structured variable share, which is everything but the four
    values that say what the thing is."""
    return ObjectView(
        name=entry.name,
        kind=entry.kind,
        c_type=c_type,
        datatype=datatype,
        # The spelled shape, so an array dimensioned by a constant is declared by its name; a
        # table keeping its counts in front is declared flat.
        array_suffix=storage_suffix(entry),
        constant=entry.is_calibration,
        volatile=entry.volatile,
        initializer=initializer,
        comment=comment,
        condition=entry.condition,
        owner=entry.owner or UNRESOLVED_GROUP,
        consumers=entry.consumers,
        section=entry.section,
        dimensions=tuple(entry.spelled_shape),
        point_counts=(
            stored_counts(entry.kind, entry.spelled_shape)
            if isinstance(entry, ResolvedObject) and entry.point_counts is PointCounts.LEADING
            else ()
        ),
        extensions=entry.extensions,
    )


def _header(
    component: ResolvedComponent, views: dict[str, ObjectView], options: COptions
) -> ComponentHeaderView:
    buckets: dict[Scope, list[DeclarationView]] = {scope: [] for scope in Scope}
    for declaration in component.declarations:
        # Every name here has a view: the analysis keeps a declaration out of the component's
        # list whenever it keeps the object out of the dictionary - duplicates and
        # unresolvable declarations alike - so the interface never names what did not resolve.
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
