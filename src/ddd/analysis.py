"""Resolving the data objects of a workspace and checking the interfaces for consistency.

This is the front end: it turns what the loader read into a :class:`~ddd.ir.DataDictionary`
and reports every disagreement on the way. It knows nothing about c or about a2l - the only
thing it hands to the backends is the dictionary.
"""

from __future__ import annotations

import dataclasses
import difflib
import math
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, replace

from ddd.compare import ComparedField, differing, spell_out
from ddd.diagnostics import DiagnosticBag, Location
from ddd.ir import (
    ComponentDeclaration,
    DataDictionary,
    ResolvedComponent,
    ResolvedInstance,
    ResolvedLeaf,
    ResolvedMember,
    ResolvedObject,
    ResolvedRaster,
    ResolvedStruct,
)
from ddd.loading import LoadedComponent, LoadedRaster, LoadedType, Workspace
from ddd.models import (
    MEMBER_OBJECT_KINDS,
    Axis,
    Conversion,
    Curve,
    DataObject,
    Datatype,
    Declaration,
    EnumConversion,
    ExternalType,
    Limits,
    Map,
    Member,
    ObjectKind,
    ScalarType,
    Scope,
    Shape,
    StructType,
    WrittenShape,
    bitfield_range,
    check_shape,
    conversion_identity,
    conversion_range,
    format_number,
    format_shape,
    is_reserved_identifier,
    physical_range,
    resolve_export,
    spelled_dimensions,
)

_A2L_MAX_DIMENSIONS = 3
"""Dimensions ``MATRIX_DIM`` can carry in the a2l version DDD writes (ASAP2 1.6.1)."""

_INT_MIN, _INT_MAX = -(2**31), 2**31 - 1
"""Range of a c ``int`` on the 32 bit targets DDD generates for; bounds every enumerator."""


def _describe_shape(definition: DataObject) -> str:
    shape = definition.declared_shape
    if shape is None:
        return "from the axes"
    return format_shape(shape) or "scalar"


def _describe_limits(definition: DataObject) -> str:
    low, high = definition.physical_limits().as_tuple()
    return f"[{format_number(low)}, {format_number(high)}]"


def _describe_references(definition: DataObject) -> str:
    references = definition.references
    if not references:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(references.items()))


def _conversion_value(definition: DataObject) -> object:
    """What two declarations of one object have to agree on in their conversion.

    An enumerator's ``description`` is documentation, not interface: the two spellings the
    file format offers (the mapping shorthand and the list of objects) cannot even carry the
    same information. ``enum-conflict`` owns the agreement of the enumerators themselves and
    deliberately ignores descriptions, so comparing the raw dump here would report a
    mismatch that check does not see, on declarations that generate identical code. The
    description free projection itself is :func:`~ddd.models.conversion.conversion_identity`,
    shared with the delivery comparison so the two answers cannot drift apart.
    """
    conversion = definition.conversion
    if conversion is None:
        # A structured declaration: the type carries the meaning, so there is no conversion
        # here to disagree about, and every declaration of the object says the same nothing.
        return None
    return conversion_identity(conversion)


# What every component sharing an object has to agree on: a disagreement is an error.
_INTERFACE_FIELDS: tuple[ComparedField[DataObject], ...] = (
    ComparedField("kind", lambda d: d.kind.value, lambda d: d.kind.value),
    ComparedField(
        "datatype",
        lambda d: str(d.datatype if d.datatype is not None else d.typename),
        lambda d: str(d.datatype if d.datatype is not None else d.typename),
    ),
    ComparedField("unit", lambda d: d.unit, lambda d: f"'{d.unit}'"),
    ComparedField("shape", lambda d: d.declared_shape, _describe_shape),
    ComparedField(
        "conversion",
        _conversion_value,
        lambda d: d.conversion.describe() if d.conversion is not None else "none",
    ),
    # ``limits`` are not in the table: a declaration may omit them, so the resolved answer is
    # not always the reference declaration's - see :meth:`_Analysis._limits_reference`, which
    # settles whose stated limits count and compares every other stated set against those.
    ComparedField("references", lambda d: d.references, _describe_references),
    # Not optional, unlike limits, and it cannot be: the key is required on every definition,
    # so there is no silence to interpret. Every component that reads the object gets the
    # qualifier in its own header, which means every description of it has to agree.
    ComparedField("volatile", lambda d: d.volatile, lambda d: str(d.volatile).lower()),
)

# What only shapes the generated a2l entry: the producer wins, the others get a warning that
# says so. Two fields are left, and the two that used to sit here left for opposite reasons.
#
# ``init`` is a claim over somebody else's storage rather than a losing opinion, so stating one
# in a consumer is refused outright as ``consumer-storage``. ``volatile`` went the other way:
# it reaches every consumer's header as a type qualifier and tells their code whether the value
# can change under it, which makes it interface, and a disagreement an error.
#
# What is left of the a2l block is presentation - a format string, a display name - where two
# values genuinely cannot both be used and there is no reason to stop a build over it.
# ``export`` is not among them: any component may ask for an object to reach the a2l, so two
# declarations differing about it are not disagreeing - see
# :func:`~ddd.models.objects.resolve_export`. Both fields are optional the way ``limits``
# defer: a declaration that leaves one unstated is leaving it to whoever states it, and only
# two *stated* answers can disagree.
_STORAGE_FIELDS: tuple[ComparedField[DataObject], ...] = (
    ComparedField(
        "a2l format",
        lambda d: d.a2l.format,
        lambda d: f"'{d.a2l.format}'",
        optional=True,
    ),
    ComparedField(
        "a2l display_identifier",
        lambda d: d.a2l.display_identifier,
        lambda d: f"'{d.a2l.display_identifier}'",
        optional=True,
    ),
)


@dataclass(slots=True)
class _EnumRegistry:
    """Every enum of the project, and the c identifiers its enumerators occupy.

    The enumerators matter beyond their own enum: they are emitted into one shared header
    and live in c's ordinary identifier namespace, so two enums contributing the same
    enumerator - or an enumerator with the same name as a variable - produce a header that
    does not compile.
    """

    by_name: dict[str, tuple[EnumConversion, Location]] = dataclasses.field(default_factory=dict)
    enumerators: dict[str, tuple[str, Location]] = dataclasses.field(default_factory=dict)
    """Enumerator name -> (name of the enum that introduced it, where it was declared)."""


@dataclass(frozen=True, slots=True)
class DeclarationRef:
    """One declaration, together with the component it belongs to."""

    owner: LoadedComponent
    index: int
    declaration: Declaration
    resolved: DataObject | None = None
    """The definition with the type it names filled in, once that has been worked out.

    Everything downstream reads :attr:`definition` and never learns that a type was involved,
    which is what keeps the comparison tables, the backends and ``compare`` untouched by the
    feature.
    """

    @property
    def component_name(self) -> str:
        return self.owner.name

    @property
    def scope(self) -> Scope:
        return self.declaration.scope

    @property
    def definition(self) -> DataObject:
        return self.declaration.definition if self.resolved is None else self.resolved

    @property
    def name(self) -> str:
        return self.declaration.definition.name

    @property
    def condition(self) -> str | None:
        return self.declaration.condition

    def location(self, suffix: str = "") -> Location:
        return self.owner.declaration_location(self.index, suffix)


def _resolved_raster(producer: DeclarationRef | None, definition: DataObject) -> str | None:
    """The raster of a variable: the producing declaration's own key, else its component's.

    Two authored levels and no third: the producer's own key wins, the producing component's
    default answers for everything it did not single out, and a variable nobody gave a raster
    keeps none. A consumer's default is not consulted at all - the raster follows the
    producer, because it is the producing task that updates the value - and a calibration
    object takes no default, since no daq list carries one.

    A plain variable resolves through :class:`Variable` and a structured one does not go
    through it at all, so the rule lives here rather than in either: it is the central claim
    of the feature and has one edit site.
    """
    if definition.raster is not None:
        return definition.raster
    if producer is None or definition.is_calibration:
        return None
    return producer.owner.component.raster


@dataclass(frozen=True, slots=True)
class Variable:
    """A resolved data object: one storage location plus all its users."""

    name: str
    definition: DataObject
    """The effective definition, taken from the producing component."""

    shape: Shape
    """The resolved array shape, fully numeric; for a curve or map it comes from the axes."""

    dimensions: WrittenShape
    """The same shape as the producer spells it: numbers, or names of declared constants.

    For a curve or a map the spelling of the axis's ``size`` carries over, because the axis
    is where that dimension is written down.
    """

    limits: Limits
    """The resolved physical limits: the producer's stated ones, else the first stated set
    in load order, else the range the datatype and the conversion imply."""

    producer: DeclarationRef | None
    declarations: tuple[DeclarationRef, ...]
    condition: str | None

    @property
    def is_local(self) -> bool:
        return self.producer is not None and self.producer.scope is Scope.LOCAL

    @property
    def consumers(self) -> tuple[str, ...]:
        return tuple(ref.component_name for ref in self.declarations if ref.scope is Scope.INPUT)

    @property
    def exported(self) -> bool:
        """Whether the a2l carries this object, asked of every component that declares it."""
        return resolve_export(ref.definition.a2l.export for ref in self.declarations)

    @property
    def raster(self) -> str | None:
        """The raster of the producing declaration, else its component's default."""
        return _resolved_raster(self.producer, self.definition)

    def resolve(self) -> ResolvedObject:
        """The public form of this variable, as the backends receive it."""
        definition = self.definition
        return ResolvedObject(
            name=self.name,
            kind=definition.kind,
            datatype=definition.datatype,
            description=definition.description,
            unit=definition.unit,
            conversion=definition.conversion,
            limits=self.limits,
            shape=self.shape,
            dimensions=self.dimensions,
            init=definition.init,
            volatile=definition.volatile,
            section=definition.section,
            raster=self.raster,
            condition=self.condition,
            references=definition.references,
            owner=self.producer.component_name if self.producer else None,
            consumers=self.consumers,
            local=self.is_local,
            # The producer's presentation, but everybody's answer on whether to export: the
            # resolved block therefore states export outright, so a backend never has to know
            # that "unstated" once meant "yes".
            a2l=definition.a2l.model_copy(update={"export": self.exported}),
        )


def analyze(workspace: Workspace, bag: DiagnosticBag) -> DataDictionary:
    """Run every consistency check and resolve the data objects of the project."""
    return _Analysis(workspace, bag).run()


def _element_paths(dimensions: Shape) -> list[str]:
    """``()`` -> ``['']``; ``(2,)`` -> ``['[0]', '[1]']``; ``(2, 2)`` -> the four in c order.

    Only an array *of structures* is spread out this way. An array of values keeps one leaf and
    is described by a ``MATRIX_DIM``, but the members of ``cell[0]`` and ``cell[1]`` sit a whole
    structure apart, so no single record can describe both.
    """
    paths = [""]
    for size in dimensions:
        paths = [f"{prefix}[{index}]" for prefix in paths for index in range(size)]
    return paths


def _ordered_structures(declared: dict[str, LoadedType]) -> list[LoadedType]:
    """The structures, each after every structure it nests.

    c needs a nested structure to be complete before the one containing it, and a template that
    loops over the list has to be able to write them out as they come - jinja cannot sort them.
    Alphabetical order does not do it: ``Sensor_t`` sorts before ``Status_t`` and nests it.

    A depth first walk in name order, so the result is stable whichever way the includes
    happened to expand. The graph is known to be acyclic by the time this runs; a cycle is
    reported by :meth:`_Analysis._check_types` and the structures in it are left out.
    """
    ordered: list[LoadedType] = []
    placed: set[str] = set()
    walking: set[str] = set()

    def visit(name: str) -> None:
        entry = declared.get(name)
        if entry is None or name in placed or name in walking:
            return
        walking.add(name)
        for _, _, nested in _nested_types(entry):
            visit(nested)
        walking.discard(name)
        if entry.structure is not None:
            ordered.append(entry)
        placed.add(name)

    for name in sorted(declared):
        visit(name)
    return ordered


def _nested_types(entry: LoadedType) -> list[tuple[int, Member, str]]:
    """The members of a structure that name a type, with their position.

    A member whose datatype is one of the base ones names nothing, and a scalar type nests
    nothing either - only a structure has members of its own. Both are told apart by the caller,
    which has the declared types to hand; here the question is only which members name a name.
    """
    structure = entry.structure
    if structure is None:
        return []
    return [
        (index, member, member.typename)
        for index, member in enumerate(structure.members)
        if member.typename is not None
    ]


def _nesting_cycle(start: str, declared: dict[str, LoadedType]) -> tuple[str, ...]:
    """The chain of nested structures leading from ``start`` back to a name already on it.

    Returns the cycle itself rather than a bare yes, because the chain is the only useful part
    of the finding: ``A -> B -> C -> A`` says which member to remove, where "A is recursive"
    leaves the reader to work out how.
    """
    chain: list[str] = []

    def walk(name: str) -> tuple[str, ...]:
        if name in chain:
            return (*chain[chain.index(name) :], name)
        entry = declared.get(name)
        if entry is None:
            # An undeclared type has no members to follow; it is reported as unknown-type.
            return ()
        chain.append(name)
        for _, _, nested in _nested_types(entry):
            found = walk(nested)
            if found:
                return found
        chain.pop()
        return ()

    return walk(start)


def _resolve_component(loaded: LoadedComponent, kept: set[tuple[str, int]]) -> ResolvedComponent:
    """The component and its interface, in the order the author wrote it.

    Only the declarations the analysis kept. One that was dropped - a duplicate of an
    earlier one, an unknown type or constant, a poisoned structure, a curve over a dropped
    axis - is left out here exactly as it was left out of resolution, so a consumer of
    ``declarations`` never meets a name that no ``objects`` or ``instances`` entry answers.
    """
    declarations = []
    for index, declaration in enumerate(loaded.component.interface):
        if (loaded.name, index) not in kept:
            continue
        declarations.append(
            ComponentDeclaration(
                name=declaration.definition.name,
                scope=declaration.scope,
                condition=declaration.condition,
            )
        )
    return ResolvedComponent(
        name=loaded.name,
        description=loaded.component.description,
        source=loaded.path.name,
        declarations=tuple(declarations),
    )


class _Analysis:
    """One run of the checks over one workspace.

    The findings, the enums and the declarations of every component are state that nearly
    every check reads or adds to. Held here rather than handed from parameter to parameter,
    which is also what :class:`ddd.loading._Loader` does with the same problem: adding a
    check then means adding a method, not threading another argument through a call chain.
    """

    def __init__(self, workspace: Workspace, bag: DiagnosticBag) -> None:
        self._workspace = workspace
        self._bag = bag
        self._enums = _EnumRegistry()
        self._types = {entry.name: entry for entry in workspace.types}
        """Every type the project declares, by name - structures and scalars alike."""
        self._constants = {entry.name: entry for entry in workspace.constants}
        """Every constant the project declares, by name; a shape names one of them."""
        self._poisoned_types: set[str] = set()
        """Types no variable can resolve as: they nest each other recursively, or a member
        of theirs, however deeply nested, names a type nobody declares or carries a
        conversion that was refused. The finding sits at the member or at the type; a
        declaration naming such a type is dropped, so nothing downstream reasons about a
        leaf it cannot have."""
        self._dropped: set[str] = set()
        """Names of the declarations that were dropped as unresolvable, whatever the reason.

        What :meth:`_unresolved` starts from: a name in here with no surviving declaration
        resolves to no object at all, and whatever refers to it is dropped along with it
        rather than reported a second time."""
        self._refs: dict[str, list[DeclarationRef]] = defaultdict(list)
        self._effective: dict[str, DataObject] = {}
        """The definition that counts for each name: the producer's, once known."""

    def run(self) -> DataDictionary:
        workspace = self._workspace
        self._check_constant_names()
        self._check_types()
        self._check_units()
        self._check_sections()
        self._check_rasters()
        self._check_project_names()
        self._check_component_names()
        for loaded in workspace.components:
            self._collect_component(loaded)

        ordered = sorted(self._refs.items())
        self._check_enumerator_collisions(ordered)
        self._check_type_name_collisions(ordered)
        self._check_constant_collisions(ordered)
        self._check_identity_collisions(ordered)

        # The producer owns the definition, so ownership has to be settled before anything
        # that reads a definition - in particular before curves and maps look up their axes.
        owners = {name: self._select_producer(name, refs) for name, refs in ordered}
        self._effective = {name: (owners[name] or refs[0]).definition for name, refs in ordered}
        unresolved = self._unresolved()
        resolved = [(name, refs) for name, refs in ordered if name not in unresolved]
        shapes = {
            name: self._resolve_shape(self._effective[name], owners[name] or refs[0])
            for name, refs in resolved
        }

        structured = [(name, refs) for name, refs in resolved if self._is_structured(name)]
        plain = [(name, refs) for name, refs in resolved if not self._is_structured(name)]
        variables = [
            self._build_variable(name, refs, owners[name], self._effective[name], shapes[name])
            for name, refs in plain
        ]
        instances = [
            self._build_instance(name, refs, owners[name], self._effective[name])
            for name, refs in structured
        ]
        self._check_similar_names(ordered)

        # Only the declarations whose object resolved: the dictionary's component interfaces
        # must never name an object its `objects` and `instances` lists do not carry.
        kept = {(ref.component_name, ref.index) for _, refs in resolved for ref in refs}
        known = self._enums.by_name
        return DataDictionary(
            name=workspace.name,
            description=workspace.description,
            source=workspace.root.name,
            components=tuple(_resolve_component(loaded, kept) for loaded in workspace.components),
            objects=tuple(variable.resolve() for variable in variables),
            enums=tuple(enum for enum, _ in (known[key] for key in sorted(known))),
            constants=tuple(entry.declared for entry in workspace.constants),
            rasters=tuple(
                ResolvedRaster(
                    raster=loaded.declared.raster,
                    event=loaded.declared.event,
                    cycle=loaded.declared.cycle,
                    cycle_ns=loaded.declared.cycle_ns,
                    description=loaded.declared.description,
                )
                for loaded in self._workspace.rasters
            ),
            types=tuple(self._resolve_struct(entry) for entry in _ordered_structures(self._types)),
            instances=tuple(instance for instance, _ in instances),
            leaves=tuple(
                sorted((leaf for _, leaves in instances for leaf in leaves), key=lambda x: x.path)
            ),
        )

    def _register_member_enums(self, entry: LoadedType) -> None:
        """An enumeration a member names is one the types header has to declare.

        A member's conversion reaches the a2l as a ``COMPU_VTAB``, and its enumerators are c
        identifiers like any others: they need the same typedef, and the same screening against
        the names everything else takes.
        """
        structure = entry.structure
        if structure is None:
            return
        for index, member in enumerate(structure.members):
            if isinstance(member.conversion, EnumConversion):
                self._register_enum(
                    member.conversion, entry.location(f"members[{index}].conversion")
                )

    def _is_structure(self, named: str) -> bool:
        """Whether that type name is a structure; false for a scalar and for one nobody declared."""
        declared = self._types.get(named)
        return declared is not None and isinstance(declared.declared, StructType)

    def _is_structured(self, name: str) -> bool:
        """Whether the object of that name is a structure rather than a value."""
        named = self._effective[name].declared_type
        return named is not None and self._is_structure(named)

    def _resolve_struct(self, entry: LoadedType) -> ResolvedStruct:
        """One declared structure, in the form the c templates declare it from."""
        structure = entry.declared
        assert isinstance(structure, StructType)
        return ResolvedStruct(
            name=structure.name,
            description=structure.description,
            members=tuple(self._resolve_member(member) for member in structure.members),
        )

    def _resolve_member(self, member: Member) -> ResolvedMember:
        """One member as the dictionary records it, its storage worked out from the registry."""
        external = self._member_external(member)
        return ResolvedMember(
            name=member.name,
            description=member.description,
            datatype=self._member_storage(member),
            type=self._member_structure(member),
            external=member.typename if external is not None else None,
            header=external.header if external is not None else None,
            dimensions=member.dimensions,
            bits=member.bits,
        )

    def _declared_of(self, member: Member) -> StructType | ScalarType | ExternalType | None:
        """The declared type a member names, or nothing - it names none, or an unknown one.

        The lookup only; each caller narrows the answer to the kind of type it is after.
        """
        if member.typename is None:
            return None
        declared = self._types.get(member.typename)
        return declared.declared if declared is not None else None

    def _member_storage(self, member: Member) -> Datatype | None:
        """The base datatype a member is spelled with, or nothing when it is a structure."""
        if member.typename is None:
            return member.datatype
        entry = self._declared_of(member)
        return entry.datatype if isinstance(entry, ScalarType) else None

    def _member_structure(self, member: Member) -> str | None:
        """The structure a member is, or nothing when it is spelled with a datatype."""
        entry = self._declared_of(member)
        return member.typename if isinstance(entry, StructType) else None

    def _member_external(self, member: Member) -> ExternalType | None:
        """The external type a member names, or nothing when DDD declares its storage itself."""
        entry = self._declared_of(member)
        return entry if isinstance(entry, ExternalType) else None

    def _check_units(self) -> None:
        """Every stated unit is in the vocabulary, where the project declares one.

        Declared nowhere, units stay free text and nothing here runs: the vocabulary is an
        opt-in. Declared anywhere, every spelling is checked where it is written - on a
        declaration, on a structure member, on a scalar type - because one quantity spelled
        two ways is invisible per object: each object agrees with itself, the a2l grows one
        ``COMPU_METHOD`` per spelling, and the calibration tool shows two units for one
        quantity. The empty unit is always allowed; a dimensionless value states no unit
        rather than a spelling of one.
        """
        vocabulary = {entry.unit for entry in self._workspace.units}
        if not vocabulary:
            return

        def check(unit: str, where: Location) -> None:
            if unit and unit not in vocabulary:
                nearest = _did_you_mean(unit, sorted(vocabulary), cutoff=0.5)
                self._bag.add(
                    "unknown-unit",
                    f"'{unit}' is not a unit this project declares{nearest}",
                    where,
                )

        for loaded in self._workspace.components:
            for index, declaration in enumerate(loaded.component.interface):
                check(
                    declaration.definition.unit,
                    loaded.declaration_location(index, "definition.unit"),
                )
        for entry in self._workspace.types:
            scalar = entry.declared
            if isinstance(scalar, ScalarType):
                check(scalar.unit, entry.location("unit"))
                continue
            structure = entry.structure
            if structure is None:
                # An external type: DDD does not see its meaning, so it states no unit.
                continue
            for position, member in enumerate(structure.members):
                check(member.unit, entry.location(f"members[{position}].unit"))

    def _check_sections(self) -> None:
        """Every stated section is declared, writable enough, and aligned enough.

        A section is a reference rather than a spelling: naming one no file declares is
        ``unknown-section`` whether or not any sections file exists, because a section
        without declared properties would be a name the two checks below can say nothing
        about. The authority rule is not here - a consumer stating a section is refused as
        ``consumer-storage`` where the claim is written.
        """
        declared = {entry.section: entry.declared for entry in self._workspace.sections}
        for loaded in self._workspace.components:
            for index, declaration in enumerate(loaded.component.interface):
                definition = declaration.definition
                named = definition.section
                if named is None:
                    continue
                where = loaded.declaration_location(index, "definition.section")
                entry = declared.get(named)
                if entry is None:
                    nearest = _did_you_mean(named, sorted(declared), cutoff=0.5)
                    self._bag.add(
                        "unknown-section",
                        f"'{definition.name}' is placed in '{named}', which is not a section "
                        f"any file of this project declares{nearest}",
                        where,
                    )
                    continue
                if definition.kind is ObjectKind.MEASUREMENT and not entry.writable:
                    self._bag.add(
                        "section-access",
                        f"'{definition.name}' is a measurement, which the software writes, "
                        f"but '{named}' is read-only",
                        where,
                    )
                needed = self._alignment_of(definition)
                if needed is not None and needed > entry.alignment:
                    self._bag.add(
                        "section-alignment",
                        f"'{definition.name}' needs an alignment of {needed}, but '{named}' "
                        f"guarantees {entry.alignment}",
                        where,
                    )

    def _check_rasters(self) -> None:
        """Every named raster is declared, and every declared one has an event of its own.

        A raster is a reference rather than a spelling, so naming one no file declares is
        ``unknown-raster`` whether or not any rasters file exists: an event nothing describes
        is a name the a2l could only write as a number nobody chose. The authority rule is
        not here - a consumer naming one is refused as ``consumer-raster`` where the claim is
        written.
        """
        declared = {entry.raster: entry for entry in self._workspace.rasters}
        seen: dict[int, LoadedRaster] = {}
        for entry in self._workspace.rasters:
            first = seen.setdefault(entry.declared.event, entry)
            if first is not entry:
                self._bag.add(
                    "duplicate-event",
                    f"raster '{entry.raster}' and raster '{first.raster}' both claim event "
                    f"{entry.declared.event}; one event carries one raster",
                    entry.location(),
                    notes=[("also claims this event", first.location())],
                )

        for loaded in self._workspace.components:
            default = loaded.component.raster
            if default is not None and default not in declared:
                nearest = _did_you_mean(default, sorted(declared), cutoff=0.5)
                self._bag.add(
                    "unknown-raster",
                    f"component '{loaded.name}' measures in '{default}', which is not a "
                    f"raster any file of this project declares{nearest}",
                    loaded.location("component.raster"),
                )
            for index, declaration in enumerate(loaded.component.interface):
                definition = declaration.definition
                named = definition.raster
                if named is None or named in declared:
                    continue
                nearest = _did_you_mean(named, sorted(declared), cutoff=0.5)
                self._bag.add(
                    "unknown-raster",
                    f"'{definition.name}' is measured in '{named}', which is not a raster "
                    f"any file of this project declares{nearest}",
                    loaded.declaration_location(index, "definition.raster"),
                )

    def _alignment_of(self, definition: DataObject) -> int | None:
        """The alignment an object needs, as far as the description can tell.

        A base datatype needs its own size. A structure needs the strictest of its members,
        walked through nested structures; the compiler's word on the real layout is final,
        which is why the finding this feeds is a warning rather than an error. An object
        whose type resolves to nothing has been reported already and needs no second finding.
        """
        if definition.datatype is not None:
            return definition.datatype.size
        assert definition.typename is not None
        return self._type_alignment(definition.typename, seen=set())

    def _type_alignment(self, name: str, seen: set[str]) -> int | None:
        if name in seen:  # a cycle is reported as type-cycle; no alignment to give
            return None
        seen.add(name)
        loaded = self._types.get(name)
        if loaded is None:
            return None
        entry = loaded.declared
        if isinstance(entry, ExternalType):
            # DDD does not see the layout, so there is nothing to estimate - and a structure
            # containing such a member gets no estimate either, which _reaches_external says.
            return None
        if isinstance(entry, ScalarType):
            return entry.datatype.size
        if self._reaches_external(name, set()):
            # One unknown member unknowns the whole: the strictest of the others is not an
            # estimate of the structure's need, only of part of it, and a warning built on
            # that would blame a section for a number the description never stated.
            return None
        strictest = 1
        for member in entry.members:
            if member.datatype is not None:
                strictest = max(strictest, member.datatype.size)
                continue
            assert member.typename is not None
            nested = self._type_alignment(member.typename, seen)
            if nested is not None:
                strictest = max(strictest, nested)
        return strictest

    def _reaches_external(self, name: str, seen: set[str]) -> bool:
        """Whether a variable of that type contains an external member, however deeply.

        A cycle is not this walk's business - it is reported as ``type-cycle`` - so a name
        already seen is simply not followed again, exactly as in :meth:`_members_resolve`.
        """
        if name in seen:
            return False
        seen.add(name)
        entry = self._types.get(name)
        if entry is None:
            return False
        if entry.external is not None:
            return True
        return any(self._reaches_external(nested, seen) for _, _, nested in _nested_types(entry))

    def _check_types(self) -> None:
        """Every nested structure is declared, and no structure contains itself.

        Both are refused rather than resolved as far as possible. A member whose structure is
        unknown has no size, so every offset after it in the enclosing structure would be wrong
        and the generated addresses would silently point at the wrong bytes; a structure that
        contains itself has no size at all.
        """
        declared = self._types
        for entry in self._workspace.types:
            if is_reserved_identifier(entry.name):
                self._bag.add(
                    "reserved-identifier",
                    f"type name '{entry.name}' is reserved by the c language",
                    entry.location("name"),
                )
            self._check_member_names(entry)
            self._check_member_dimensions(entry)
            self._check_opaque_members(entry)
            self._register_member_enums(entry)
            for index, member, nested in _nested_types(entry):
                target = declared.get(nested)
                if target is None:
                    self._bag.add(
                        "unknown-type",
                        f"member '{member.name}' names datatype '{nested}', which is neither a "
                        f"base datatype nor a type any file of this project declares"
                        f"{self._nearest_type(nested)}",
                        entry.location(f"members[{index}]"),
                    )

        # Keyed on the participants of the cycle rather than on the structure the walk started
        # from. Those differ: a sound structure nesting a recursive one reaches the same cycle,
        # and keying on the start would report it once per route into it.
        reported: set[frozenset[str]] = set()
        for entry in self._workspace.types:
            cycle = _nesting_cycle(entry.name, declared)
            if cycle:
                # Every type whose walk reaches the cycle is unusable: it has no size, so a
                # variable of it cannot be flattened. Poisoned here, refused at resolution.
                self._poisoned_types.add(entry.name)
            if not cycle or frozenset(cycle) in reported:
                continue
            reported.add(frozenset(cycle))
            # At the structure the cycle closes on rather than the one the walk started from,
            # for the same reason.
            self._bag.add(
                "type-cycle",
                f"structured datatypes nest each other: {' -> '.join(cycle)}",
                declared[cycle[0]].location(),
            )

        for entry in self._workspace.types:
            self._refuse_infinite_type_limits(entry)
        # Propagated the way the cycles are: a sound structure nesting a broken one has the
        # same unresolvable leaves, and a variable of either is dropped at resolution.
        unresolvable = {
            entry.name
            for entry in self._workspace.types
            if not self._members_resolve(entry.name, set())
        }
        self._poisoned_types |= unresolvable

    def _refuse_infinite_type_limits(self, entry: LoadedType) -> None:
        """A type whose derived limits are not finite is refused at its ``conversion``.

        The refusal a definition gets - see :meth:`_limits_stay_finite` - at the two places a
        types file writes a datatype and conversion pair: on a scalar type, and on a structure
        member. A refused type poisons itself, so no variable resolves as it.
        """
        declared = entry.declared
        if isinstance(declared, ScalarType):
            datatype = declared.datatype
            if not _derived_range_is_finite(
                declared.conversion, datatype.raw_min, datatype.raw_max
            ):
                self._bag.add(
                    "schema", _infinite_limits_message(datatype), entry.location("conversion")
                )
                self._poisoned_types.add(entry.name)
            return
        if not isinstance(declared, StructType):
            # An external type states no datatype and no conversion: nothing to derive.
            return
        for index, member in enumerate(declared.members):
            if member.datatype is None:
                continue
            assert member.conversion is not None
            raw_min, raw_max = (
                bitfield_range(member.datatype, member.bits)
                if member.bits is not None
                else (member.datatype.raw_min, member.datatype.raw_max)
            )
            if not _derived_range_is_finite(member.conversion, raw_min, raw_max):
                self._bag.add(
                    "schema",
                    _infinite_limits_message(member.datatype),
                    entry.location(f"members[{index}].conversion"),
                )
                self._poisoned_types.add(entry.name)

    def _members_resolve(self, name: str, seen: set[str]) -> bool:
        """Whether every leaf a variable of that type would have can be resolved.

        False when a member, however deeply nested, names a type nobody declares or one whose
        conversion was refused; the finding already sits at that member or type. A cycle is
        not this walk's business - it is reported and dropped as ``type-cycle`` - so a name
        already seen is simply not followed again.
        """
        if name in seen:
            return True
        seen.add(name)
        entry = self._types.get(name)
        if entry is None or name in self._poisoned_types:
            return False
        return all(self._members_resolve(nested, seen) for _, _, nested in _nested_types(entry))

    def _check_member_dimensions(self, entry: LoadedType) -> None:
        """Every constant a member's shape names is declared, or the type is unusable.

        Reported at the dimension entry that names it, exactly as on a declaration, and the
        structure is poisoned the way one nesting an unknown type is: a member of no known
        length leaves the structure without a size, so no variable can resolve as it.
        """
        structure = entry.structure
        if structure is None:
            return
        for position, member in enumerate(structure.members):
            for index, dimension in enumerate(member.dimensions):
                if isinstance(dimension, str) and dimension not in self._constants:
                    self._bag.add(
                        "unknown-constant",
                        f"member '{member.name}' of structure '{entry.name}' is dimensioned "
                        f"by '{dimension}', which is not a constant any file of this "
                        f"project declares{self._nearest_constant(dimension)}",
                        entry.location(f"members[{position}].dimensions[{index}]"),
                    )
                    self._poisoned_types.add(entry.name)

    def _check_opaque_members(self, entry: LoadedType) -> None:
        """A member naming an external type is opaque storage, so its ``a2l`` block is refused.

        The contract already refuses ``unit``, ``conversion`` and ``limits`` beside any
        ``typename``; the ``a2l`` block is legal beside a scalar type - presentation stays
        the member's own - which is why the refusal has to live here, where the registry says
        which kind of type the name refers to. No record exists for the block to shape: an
        opaque member reaches no a2l at all, because the format cannot describe storage
        whose layout DDD does not know.
        """
        structure = entry.structure
        if structure is None:
            return
        for position, member in enumerate(structure.members):
            named = self._member_external(member)
            if named is None or "a2l" not in member.model_fields_set:
                continue
            self._bag.add(
                "schema",
                f"member '{member.name}' of structure '{entry.name}' names the external type "
                f"'{named.name}', which DDD cannot see into: the member reaches no a2l, so "
                f"there is no record for the 'a2l' block to shape",
                entry.location(f"members[{position}].a2l"),
            )

    def _check_member_names(self, entry: LoadedType) -> None:
        """Every member of a structure becomes a c identifier in the generated types header.

        Screened like the enumerators, and for the same reason: a member named ``int`` or
        ``__x`` puts a declaration in the struct that a compiler refuses or the implementation
        owns, which would otherwise surface as a message about a generated file.
        """
        structure = entry.structure
        if structure is None:
            return
        for position, member in enumerate(structure.members):
            if is_reserved_identifier(member.name):
                self._bag.add(
                    "reserved-identifier",
                    f"member '{member.name}' of structure '{entry.name}' is reserved by the "
                    f"c language",
                    entry.location(f"members[{position}].name"),
                )

    def _check_constant_names(self) -> None:
        """A declared constant becomes an identifier of the generated code, so it is
        screened like one.

        The templates receive every declared constant to emit - the shipped examples spell
        each as a preprocessor definition - and an array dimensioned by one carries the name
        in every declaration, so a constant called ``int`` or ``__N`` breaks every file that
        spells it.
        """
        for entry in self._workspace.constants:
            if is_reserved_identifier(entry.name):
                self._bag.add(
                    "reserved-identifier",
                    f"constant name '{entry.name}' is reserved by the c language",
                    entry.location("name"),
                )

    def _check_project_names(self) -> None:
        """The project name is an identifier the outputs carry, so it is screened like one.

        It names the a2l ``PROJECT`` and ``MODULE`` and reaches the generated banners, exactly
        as a component name names a header; a project called ``register`` deserves the same
        located finding.
        """
        for loaded in self._workspace.projects:
            if is_reserved_identifier(loaded.name):
                self._bag.add(
                    "reserved-identifier",
                    f"project name '{loaded.name}' is reserved by the c language",
                    Location(loaded.path, "project.name"),
                )

    def _check_component_names(self) -> None:
        """Component names that differ only in case cannot both be generated.

        Each component gets a header named after it, so 'Sensor' and 'SENSOR' ask for two
        files that are the same file on a case insensitive filesystem and for the same
        include guard everywhere. Reporting it here gives the author a located finding
        instead of letting the generator fail late with a message about a path.
        """
        by_lowercase: dict[str, list[LoadedComponent]] = defaultdict(list)
        for loaded in self._workspace.components:
            by_lowercase[loaded.name.lower()].append(loaded)
        for group in by_lowercase.values():
            first, *rest = group
            for other in rest:
                self._bag.add(
                    "name-collision",
                    f"components '{other.name}' and '{first.name}' differ only in upper/lower "
                    f"case, so they ask for the same generated header",
                    other.location("component.name"),
                    notes=[("other component", first.location("component.name"))],
                )

    def _check_type_name_collisions(self, ordered: list[tuple[str, list[DeclarationRef]]]) -> None:
        """A type name and a variable name cannot both be had.

        Every declared type becomes a typedef in the generated header, and c keeps a typedef
        name at file scope in the same namespace as the variables - the identical argument the
        enum names already go through, and the reason they are checked.
        """
        for name, refs in ordered:
            declared = self._types.get(name)
            if declared is None:
                continue
            self._bag.add(
                "name-collision",
                f"'{name}' is declared as a variable and is also the name of a type; the types "
                f"header makes that a typedef name, which c keeps in the same namespace as the "
                f"variable",
                refs[0].location("definition.name"),
                notes=[("type declared here", declared.location())],
            )

    def _check_enumerator_collisions(self, ordered: list[tuple[str, list[DeclarationRef]]]) -> None:
        """A variable cannot share a name with anything else the generated headers declare.

        At file scope c keeps variables, enumerators and typedef names in one namespace, and
        both of the others come out of the types header the globals header includes. Either
        clash produces a translation unit that does not compile, which is a message about a
        generated file somebody then has to trace back to the description that caused it.
        """
        for name, refs in ordered:
            where = refs[0].location("definition.name")
            known = self._enums.enumerators.get(name)
            if known is not None:
                enum_name, location = known
                self._bag.add(
                    "name-collision",
                    f"'{name}' is declared as a variable and is also an enumerator of enum "
                    f"'{enum_name}'; both become the same c identifier",
                    where,
                    notes=[("enumerator declared here", location)],
                )
            declared = self._enums.by_name.get(name)
            if declared is not None:
                self._bag.add(
                    "name-collision",
                    f"'{name}' is declared as a variable and is also the name of an enum; the "
                    f"types header makes that a typedef name, which c keeps in the same "
                    f"namespace as the variable",
                    where,
                    notes=[("enum declared here", declared[1])],
                )

    def _check_constant_collisions(self, ordered: list[tuple[str, list[DeclarationRef]]]) -> None:
        """A declared constant cannot share a name with anything else the headers declare.

        The constant reaches the generated code as an identifier of its own, in the same
        file scope namespace as the variables, the typedef names and the enumerators - and
        the example templates emit it as a preprocessor definition, which replaces the other
        occupant textually wherever it appears. Exactly the pairs of the specification are
        compared: a constant against a data object, an enum, an enumerator and a declared
        type.
        """
        by_name = dict(ordered)
        for name in sorted(self._constants):
            entry = self._constants[name]
            refs = by_name.get(name)
            if refs:
                self._bag.add(
                    "name-collision",
                    f"'{name}' is declared as a variable and is also a declared constant; "
                    f"both become the same c identifier",
                    refs[0].location("definition.name"),
                    notes=[("constant declared here", entry.location())],
                )
            known = self._enums.enumerators.get(name)
            if known is not None:
                enum_name, location = known
                self._bag.add(
                    "name-collision",
                    f"'{name}' is a declared constant and also an enumerator of enum "
                    f"'{enum_name}'; both become the same c identifier",
                    entry.location(),
                    notes=[("enumerator declared here", location)],
                )
            declared_enum = self._enums.by_name.get(name)
            if declared_enum is not None:
                self._bag.add(
                    "name-collision",
                    f"'{name}' is a declared constant and also the name of an enum; both "
                    f"become the same c identifier",
                    entry.location(),
                    notes=[("enum declared here", declared_enum[1])],
                )
            declared_type = self._types.get(name)
            if declared_type is not None:
                self._bag.add(
                    "name-collision",
                    f"'{name}' is a declared constant and also the name of a type; both "
                    f"become the same c identifier",
                    entry.location(),
                    notes=[("type declared here", declared_type.location())],
                )

    def _check_identity_collisions(
        self, ordered: Sequence[tuple[str, list[DeclarationRef]]]
    ) -> None:
        """Two objects claiming one identity, which is a copied declaration nine times in ten.

        Reported on the second one in name order rather than on both, so the finding names a
        place to edit; the first is named in the message. The one that keeps the id is the
        one the comparison of a later delivery would pair, and choosing that by file order
        would make the report depend on the order of the includes.
        """
        seen: dict[str, DeclarationRef] = {}
        for name, refs in ordered:
            for ref in refs:
                identity = ref.definition.id
                if identity is None or not ref.scope.is_producer:
                    continue
                first_ref = seen.setdefault(identity, ref)
                if first_ref.name != name:
                    self._bag.add(
                        "duplicate-id",
                        f"'{name}' carries the id '{identity}', which '{first_ref.name}' "
                        f"already carries; an id is one object's alone, and two objects "
                        f"sharing one make a later comparison pair the wrong pair",
                        ref.location("definition.id"),
                        notes=[
                            ("first carries the id here", first_ref.location("definition.id")),
                        ],
                    )

    def _nearest_type(self, named: str) -> str:
        """`` - did you mean 'uint16'?``, or nothing when nothing is close.

        A mistyped base datatype dies in the contract - under ``datatype`` it is not one of
        the eleven, under ``typename`` a bare base name is refused - so what reaches here is
        the rest: a transposition like ``unit16`` written as a ``typename``, or a type name
        somebody misremembered. Both are answered by the same question.
        """
        candidates = tuple(datatype.value for datatype in Datatype) + tuple(sorted(self._types))
        return _did_you_mean(named.lower(), candidates, cutoff=0.6)

    def _nearest_constant(self, named: str) -> str:
        """`` - did you mean 'PRESSURE_CELLS'?``, or nothing when nothing is close.

        The constant cutoff is the type one: a constant is a full identifier rather than a
        short spelling like a unit, so a loose match would suggest names that share little
        more than a prefix.
        """
        return _did_you_mean(named, tuple(sorted(self._constants)), cutoff=0.6)

    def _refuse(
        self,
        check: str,
        message: str,
        location: Location,
        name: str,
        notes: Sequence[tuple[str, Location | None]] = (),
    ) -> None:
        """Report why a declaration cannot resolve, and what the silence costs when it is not.

        Every finding routed through here drops the declaration: an array of no known length,
        a variable of a type nobody declares, a structure used where its shape does not fit -
        none of them is something anything downstream can reason about. Dropping is right, and
        it does not depend on the severity the finding is given, which is where relaxing one
        turns into a hazard: with the cause silenced, ``ddd list`` prints a table one row short
        and exits zero, and ``ddd dump`` archives a dictionary the variable is missing from.

        So the consequence is reported even when the cause is not - and only then, because a
        finding that already says the declaration could not resolve does not want it twice.
        """
        if self._bag.add(check, message, location, notes) is not None:
            return
        self._bag.add(
            "incomplete-project",
            f"'{name}' is not in the data dictionary: the {check} that says why is not "
            f"reported, so nothing reading the dictionary - the listing, the dump, every "
            f"backend - carries it either",
            location,
        )

    def _shape_resolves(self, ref: DeclarationRef) -> bool:
        """Whether every constant this declaration's shape names is declared.

        Reported where the name is written - the dimension entry, or the ``size`` key - and
        a declaration whose shape does not resolve is dropped the way one naming an unknown
        type is: a dimension without a value is storage without a size, and everything
        downstream would be reasoning about an array of no known length.
        """
        resolves = True
        for named, key in spelled_dimensions(ref.definition):
            if named not in self._constants:
                self._refuse(
                    "unknown-constant",
                    f"'{ref.name}' is dimensioned by '{named}', which is not a constant any "
                    f"file of this project declares{self._nearest_constant(named)}",
                    ref.location(f"definition.{key}"),
                    ref.name,
                )
                resolves = False
        return resolves

    def _dimension_value(self, dimension: int | str) -> int:
        """The number a dimension resolves to; a name looks its constant up.

        Only ever asked once the spelling has resolved: a declaration or a type whose shape
        names an unknown constant was reported and dropped before anything got this far.
        """
        if isinstance(dimension, int):
            return dimension
        return self._constants[dimension].value

    def _numeric_shape(self, shape: WrittenShape) -> Shape:
        """The shape with every named dimension resolved to its number."""
        return tuple(self._dimension_value(dimension) for dimension in shape)

    def _resolve_type(self, ref: DeclarationRef) -> DeclarationRef | None:
        """Fill in the type a declaration names, or report that it names nothing.

        Done before anything else looks at the declaration, because a definition whose type is
        unknown has no datatype: every later check on it would be reasoning about nothing. What
        comes out the other side is an ordinary definition with its storage and its meaning
        spelled out, so nothing downstream needs to know a type was ever involved.
        """
        definition = ref.declaration.definition
        named = definition.declared_type
        if named is None:
            return ref if self._limits_stay_finite(ref) else None
        declared = self._types.get(named)
        if declared is None:
            self._refuse(
                "unknown-type",
                f"'{ref.name}' is declared as '{named}', which is neither a base datatype nor a "
                f"type any file of this project declares{self._nearest_type(named)}",
                ref.location("definition.typename"),
                ref.name,
            )
            return None
        entry = declared.declared
        if isinstance(entry, ExternalType):
            # The same family of refusal a structure gets for a kind that does not fit: the
            # type is perfectly good, and the use made of it is not. DDD knows neither the
            # layout nor the meaning of an external type, so a whole variable of one is a
            # definition the checks could say nothing about.
            self._refuse(
                "type-kind",
                f"'{ref.name}' is declared as '{named}', but that is an external type, whose "
                f"layout and meaning DDD does not know; only a structure member may name one",
                ref.location("definition"),
                ref.name,
                notes=[("declared here", declared.location())],
            )
            return None
        if isinstance(entry, StructType):
            if named in self._poisoned_types:
                # The cycle, the unknown member type or the refused conversion is already
                # reported at the type; a variable of a structure whose leaves cannot be
                # resolved cannot be either, and a second finding here would only repeat the
                # first with a worse location.
                return None
            # Kept as it was written. A structured variable has no single datatype, no limits
            # and no initial value, so it takes a road of its own from here on; what it shares
            # with every other declaration - who owns it, who reads it, what it is called - is
            # settled on the way by exactly the same checks.
            return ref if self._structure_fits(ref, named, declared) else None
        if named in self._poisoned_types:
            # The refused conversion is already reported at the scalar type; a variable of it
            # has no limits to resolve, and a second finding here would repeat the first.
            return None
        # A scalar type fixes what the value means and nothing about the variable, so only the
        # four it fixes are filled in. The definition already refused to restate any of them.
        return replace(
            ref,
            resolved=definition.model_copy(
                update={
                    "datatype": entry.datatype,
                    "unit": entry.unit,
                    "conversion": entry.conversion,
                    "limits": entry.limits,
                }
            ),
        )

    def _structure_fits(self, ref: DeclarationRef, named: str, declared: LoadedType) -> bool:
        """Whether this declaration can be the structure it names.

        Three of the keys a definition may carry have no meaning on a structured one, and each
        is refused rather than ignored. ``init``, because what a structure starts as is written
        by the code that starts it and the contract has no form for stating it per member; and
        every kind but the two, because a curve, a map, an axis or a value block refers to
        other objects or is an array of one datatype, and a structure is neither.

        ``dimensions`` is *not* refused: an array of structures contributes its elements, each
        at its own path, which is the same thing an array of them inside a structure does.
        """
        definition = ref.declaration.definition
        problem: str | None = None
        if definition.kind not in MEMBER_OBJECT_KINDS:
            offered = " or ".join(f"'{kind.value}'" for kind in MEMBER_OBJECT_KINDS)
            problem = (
                f"the kind '{definition.kind.value}' refers to other objects or is an array "
                f"of one datatype, and a structure is neither; a structured object is "
                f"{offered}"
            )
        elif definition.init is not None:
            problem = "the initial value of a structure is written by the code that starts it"
        if problem is None:
            return True
        self._refuse(
            "type-kind",
            f"'{ref.name}' is declared as the structure '{named}', but {problem}",
            ref.location("definition"),
            ref.name,
            notes=[("declared here", declared.location())],
        )
        return False

    def _limits_stay_finite(self, ref: DeclarationRef) -> bool:
        """Refuse a datatype and conversion pair whose derived limits are not finite.

        ``float64`` under a factor of 1.8 runs past the largest float there is. Limits of
        infinity are not a range the dictionary, the a2l or a calibration tool can carry, so
        the pair is refused where it is written rather than resolved into an object every
        output would choke on; the declaration is dropped and the run reports the rest.
        """
        definition = ref.declaration.definition
        datatype = definition.datatype
        assert datatype is not None
        assert definition.conversion is not None
        if _derived_range_is_finite(definition.conversion, datatype.raw_min, datatype.raw_max):
            return True
        self._bag.add(
            "schema", _infinite_limits_message(datatype), ref.location("definition.conversion")
        )
        return False

    def _collect_component(self, loaded: LoadedComponent) -> None:
        component = loaded.component
        if is_reserved_identifier(component.name):
            self._bag.add(
                "reserved-identifier",
                f"component name '{component.name}' is reserved by the c language",
                loaded.location("component.name"),
            )
        if not component.interface:
            self._bag.add(
                "empty-component",
                f"component '{component.name}' declares no variable",
                loaded.location(),
            )

        seen: dict[str, DeclarationRef] = {}
        for index, declaration in enumerate(component.interface):
            original = DeclarationRef(loaded, index, declaration)
            ref = self._resolve_type(original)
            if ref is None:
                # Its datatype names nothing this project declares, or a type that was
                # refused, and the finding sits there. The declaration is dropped - every
                # later check would be reasoning about a value with no storage - but what
                # needs neither storage nor shape still runs: the name it takes, and the
                # claims a consumer may not make.
                self._dropped.add(original.name)
                self._check_declared_name(original)
                continue
            if not self._shape_resolves(ref):
                # A dimension names a constant nobody declares, which is now reported. The
                # declaration is dropped the way one naming an unknown type is - an array
                # of no known length is storage nothing downstream can reason about - but
                # every check that does not need the resolved shape still runs: an init
                # outside the datatype is wrong whatever the shape turns out to be, and
                # silencing unknown-constant must not silence that.
                self._dropped.add(ref.name)
                self._check_declaration(ref)
                continue
            previous = seen.get(ref.name)
            if previous is not None:
                self._bag.add(
                    "duplicate-declaration",
                    f"component '{component.name}' declares '{ref.name}' twice "
                    f"(as {previous.scope.value} and as {ref.scope.value})",
                    ref.location(),
                    notes=[("first declared here", previous.location())],
                )
                continue
            seen[ref.name] = ref
            self._refs[ref.name].append(ref)
            self._check_declaration(ref)

    def _check_declared_name(self, ref: DeclarationRef) -> None:
        """The checks that need neither the storage nor the shape of the declaration.

        Split out so a declaration that is dropped because its type resolves to nothing
        still gets them: whether the name is reserved, whether a consumer claims something it
        does not own, and whether a raster sits on a kind no daq list carries are questions
        about the declaration alone, and silencing the finding that dropped it must not
        silence these.
        """
        definition = ref.definition

        if is_reserved_identifier(definition.name):
            self._bag.add(
                "reserved-identifier",
                f"variable name '{definition.name}' is reserved by the c language",
                ref.location("definition.name"),
            )

        if not ref.scope.is_producer and definition.init is not None:
            # Reported where the claim is written rather than where it is overruled: the
            # producer may be in a file this author has never opened, and the fix is here.
            self._bag.add(
                "consumer-storage",
                f"'{definition.name}': the initial value is decided by the component that "
                f"produces the variable, not by '{ref.component_name}', which reads it",
                ref.location("definition.init"),
            )

        if not ref.scope.is_producer and definition.section is not None:
            self._bag.add(
                "consumer-storage",
                f"'{definition.name}': the memory section is decided by the component that "
                f"produces the variable, not by '{ref.component_name}', which reads it",
                ref.location("definition.section"),
            )

        if not ref.scope.is_producer and definition.raster is not None:
            self._bag.add(
                "consumer-raster",
                f"'{definition.name}': the measurement raster is decided by the component "
                f"that produces the variable, not by '{ref.component_name}', which reads it",
                ref.location("definition.raster"),
            )

        if not ref.scope.is_producer and definition.id is not None:
            self._bag.add(
                "consumer-identity",
                f"'{definition.name}': the identity is decided by the component that "
                f"produces the variable, not by '{ref.component_name}', which reads it",
                ref.location("definition.id"),
            )

        if ref.scope.is_producer and definition.id is None:
            # Info, and optional, because the key is an adoption: a project that has migrated
            # turns this into its gate with -W missing-id=error, and one that has not is not
            # stopped by a run that reports something it has not started doing.
            self._bag.add(
                "missing-id",
                f"'{definition.name}' has no 'id', so a later delivery that renames it "
                f"reports a removal and an unrelated addition; 'ddd id --assign' writes one",
                ref.location("definition.name"),
            )

        if definition.raster is not None and definition.is_calibration:
            self._bag.add(
                "raster-kind",
                f"'{definition.name}' ({definition.kind.value}) states the raster "
                f"'{definition.raster}', but no daq list carries a calibration object",
                ref.location("definition.raster"),
            )

    def _check_declaration(self, ref: DeclarationRef) -> None:
        definition = ref.definition
        location = ref.location("definition")

        self._check_declared_name(ref)

        if definition.declared_type is not None and self._is_structure(definition.declared_type):
            # A structured object has no single storage, so there is nothing here to check it
            # against: its members carry the datatype, the conversion and the limits, and are
            # checked as the leaves they become. Its own keys were checked when it resolved.
            return

        self._check_init(definition, ref.location("definition.init"))
        self._check_limits(definition, ref.location("definition.limits"))

        conversion = definition.conversion
        if isinstance(conversion, EnumConversion):
            datatype = definition.storage
            self._register_enum(conversion, ref.location("definition.conversion"), datatype)
            self._check_enum_fits(
                conversion, datatype.raw_min, datatype.raw_max, datatype.value, location
            )

    def _check_init(self, definition: DataObject, location: Location) -> None:
        datatype = definition.storage
        for value in definition.scalar_values():
            if datatype is Datatype.BOOLEAN:
                if not isinstance(value, bool) and value not in (0, 1):
                    self._bag.add(
                        "init-invalid",
                        f"init value {format_number(value)} is not a valid bool",
                        location,
                    )
                continue
            if datatype.is_integer and isinstance(value, float):
                # format_number renders 2.0 as "2", which would read as a contradiction, so
                # the value is spelled the way it was written in the file.
                self._bag.add(
                    "init-invalid",
                    f"init value {value!r} is written as a fractional number, "
                    f"but '{definition.name}' has the integer datatype {datatype.value}",
                    location,
                )
                continue
            if not (datatype.raw_min <= value <= datatype.raw_max):
                self._bag.add(
                    "init-invalid",
                    f"init value {format_number(value)} does not fit into {datatype.value} "
                    f"({format_number(datatype.raw_min)} .. {format_number(datatype.raw_max)})",
                    location,
                )

    def _check_limits(self, definition: DataObject, location: Location) -> None:
        if definition.limits is None:
            return
        assert definition.conversion is not None
        low, high = conversion_range(definition.conversion, definition.storage)
        limits = definition.limits
        if _below(limits.min, low) or _above(limits.max, high):
            self._bag.add(
                "limits-out-of-range",
                f"limits [{format_number(limits.min)}, {format_number(limits.max)}] exceed the "
                f"range [{format_number(low)}, {format_number(high)}] that "
                f"{definition.storage.value} can represent with this conversion",
                location,
            )

    def _register_enum(
        self, conversion: EnumConversion, location: Location, storage: Datatype | None = None
    ) -> None:
        known = self._enums.by_name.get(conversion.name)
        if known is None:
            self._enums.by_name[conversion.name] = (conversion, location)
            self._check_enum_names(conversion, location)
            self._check_enum_values(conversion, location, storage)
            return
        previous, previous_location = known
        if _enum_key(previous) != _enum_key(conversion):
            self._bag.add(
                "enum-conflict",
                f"enum '{conversion.name}' is defined with different enumerators",
                location,
                notes=[
                    (f"here: {_enum_summary(conversion)}", None),
                    (f"first defined as: {_enum_summary(previous)}", previous_location),
                ],
            )
        elif _documentation_rank(conversion) > _documentation_rank(previous):
            # Same enumerators, but this declaration documents more of them. Picking the
            # better documented variant rather than the first one keeps the generated types
            # header independent of the order the project happens to include its components in.
            self._enums.by_name[conversion.name] = (conversion, location)

    def _check_enum_names(self, conversion: EnumConversion, location: Location) -> None:
        """The enum type name and its enumerators become c identifiers in the types header."""
        if is_reserved_identifier(conversion.name):
            self._bag.add(
                "reserved-identifier",
                f"enum name '{conversion.name}' is reserved by the c language",
                location,
            )
        for enumerator in conversion.enumerators:
            if is_reserved_identifier(enumerator.name):
                self._bag.add(
                    "reserved-identifier",
                    f"enumerator '{enumerator.name}' of enum '{conversion.name}' is reserved "
                    f"by the c language",
                    location,
                )
            previous = self._enums.enumerators.get(enumerator.name)
            if previous is not None:
                enum_name, previous_location = previous
                self._bag.add(
                    "name-collision",
                    f"enumerator '{enumerator.name}' is defined by enum '{conversion.name}' "
                    f"and by enum '{enum_name}'; enumerators of different enums share one c "
                    f"namespace",
                    location,
                    notes=[("first defined here", previous_location)],
                )
                continue
            self._enums.enumerators[enumerator.name] = (conversion.name, location)

    def _check_enum_values(
        self, conversion: EnumConversion, location: Location, storage: Datatype | None
    ) -> None:
        by_value: dict[int, list[str]] = defaultdict(list)
        for enumerator in conversion.enumerators:
            by_value[enumerator.value].append(enumerator.name)
        for value, names in sorted(by_value.items()):
            if len(names) > 1:
                self._bag.add(
                    "enum-duplicate-value",
                    f"enum '{conversion.name}': {', '.join(names)} all have the value {value}",
                    location,
                )

        # C requires every enumerator to be representable as an 'int' (C11 6.7.2.2), which on
        # an embedded target is 32 bits wide. A larger value only compiles as a vendor
        # extension, so it is caught here rather than in the customer's build. A value that
        # does not even fit the declared storage already earns its finding against that
        # storage, so it is skipped here: one bad value, one finding.
        self._check_enum_fits(
            conversion,
            _INT_MIN,
            _INT_MAX,
            "a c 'int', which every enumerator has to",
            location,
            except_outside=(storage.raw_min, storage.raw_max) if storage is not None else None,
        )

    def _check_enum_fits(
        self,
        conversion: EnumConversion,
        lo: float,
        hi: float,
        phrase: str,
        location: Location,
        *,
        except_outside: tuple[float, float] | None = None,
    ) -> None:
        """Report the enumerators outside ``lo .. hi``, phrased for what they do not fit into.

        One shape for two bounds: the c ``int`` every enumerator has to be representable in,
        and the declared storage of the one object naming the enum. A value outside
        ``except_outside`` is reported against that bound instead and skipped here.
        """
        outside = [e for e in conversion.enumerators if not (lo <= e.value <= hi)]
        if except_outside is not None:
            first, last = except_outside
            outside = [e for e in outside if first <= e.value <= last]
        if outside:
            spelled = ", ".join(f"{e.name}={e.value}" for e in outside)
            self._bag.add(
                "init-invalid",
                f"enumerator(s) {spelled} of enum '{conversion.name}' do not fit into {phrase}",
                location,
            )

    def _select_producer(self, name: str, refs: list[DeclarationRef]) -> DeclarationRef | None:
        """Determine the owning declaration and report every ownership violation."""
        producers = [ref for ref in refs if ref.scope.is_producer]
        locals_ = [ref for ref in refs if ref.scope is Scope.LOCAL]
        consumers = [ref for ref in refs if ref.scope is Scope.INPUT]

        if locals_ and len(refs) > 1:
            for other in refs:
                if other is locals_[0]:
                    continue
                self._bag.add(
                    "local-conflict",
                    f"'{name}' is local to component '{locals_[0].component_name}' but is also "
                    f"declared as {other.scope.value} by component '{other.component_name}'",
                    other.location(),
                    notes=[("declared local here", locals_[0].location())],
                )
        elif len(producers) > 1:
            first, *rest = producers
            for other in rest:
                self._bag.add(
                    "multiple-producers",
                    f"'{name}' is written by component '{other.component_name}' and by "
                    f"component '{first.component_name}'; exactly one writer is allowed",
                    other.location(),
                    notes=[("also written here", first.location())],
                )
        elif not producers:
            for consumer in consumers:
                self._bag.add(
                    "missing-producer",
                    f"'{name}' is read by component '{consumer.component_name}' but no "
                    f"component declares it as output",
                    consumer.location(),
                )

        return producers[0] if producers else None

    def _unresolved(self) -> set[str]:
        """The names that resolve to no object, dropped declarations and their dependents.

        The seed is every name whose declarations were all dropped - unknown type or
        constant, poisoned structure - and the finding for each of those already sits at the
        root cause. An object *referring* to such a name joins the set, transitively: a
        curve over a dropped axis cannot resolve its shape, and an axis whose ``input`` is a
        dropped measurement would leave a dangling name in the a2l. Both are dropped without
        a finding of their own - ``unknown-reference`` would claim that nobody declares the
        target, which is false, and the one finding at the root already covers the chain.
        """
        dropped = {name for name in self._dropped if name not in self._effective}
        settled = False
        while not settled:
            settled = True
            for name, definition in self._effective.items():
                if name in dropped:
                    continue
                if any(target in dropped for target in definition.references.values()):
                    dropped.add(name)
                    settled = False
        return dropped

    def _resolve_shape(
        self, definition: DataObject, reference: DeclarationRef
    ) -> tuple[Shape, WrittenShape]:
        """The storage shape of an object, as numbers and as the project spells it.

        For a curve or map both follow from its axes, the spelling included: the axis is
        where that dimension is written down, so an axis sized by a constant carries the
        constant's name into every curve and map interpolated over it. Every named
        dimension resolves here, because a declaration or type whose shape does not was
        dropped before ownership was settled.
        """
        if isinstance(definition, Axis) and definition.input is not None:
            self._lookup(definition.input, ObjectKind.MEASUREMENT, "input", definition, reference)

        if isinstance(definition, Curve):
            axis = self._lookup(definition.axis, ObjectKind.AXIS, "axis", definition, reference)
            if isinstance(axis, Axis):
                return ((self._dimension_value(axis.size),), (axis.size,))
            return ((), ())

        if isinstance(definition, Map):
            x_axis = self._lookup(
                definition.x_axis, ObjectKind.AXIS, "x_axis", definition, reference
            )
            y_axis = self._lookup(
                definition.y_axis, ObjectKind.AXIS, "y_axis", definition, reference
            )
            if isinstance(x_axis, Axis) and isinstance(y_axis, Axis):
                # A map is stored row wise: the x index runs fastest, so it is the last one.
                return (
                    (self._dimension_value(y_axis.size), self._dimension_value(x_axis.size)),
                    (y_axis.size, x_axis.size),
                )
            return ((), ())

        shape = definition.declared_shape
        # Only a curve or a map defers to its axes, and both returned above.
        assert shape is not None
        return (self._numeric_shape(shape), shape)

    def _lookup(
        self,
        target: str,
        expected: ObjectKind,
        field: str,
        definition: DataObject,
        reference: DeclarationRef,
    ) -> DataObject | None:
        """Resolve a reference to another data object and report what is wrong with it."""
        found = self._effective.get(target)
        if found is None:
            self._bag.add(
                "unknown-reference",
                f"{definition.kind.value} '{definition.name}' refers to '{target}' as its "
                f"{field}, but no component declares '{target}'",
                reference.location(f"definition.{field}"),
            )
            return None
        if found.kind is not expected:
            self._bag.add(
                "reference-kind",
                f"the {field} of {definition.kind.value} '{definition.name}' must be of kind "
                f"'{expected.value}', but '{target}' is of kind '{found.kind.value}'",
                reference.location(f"definition.{field}"),
            )
            return None
        return found

    def _check_unused(
        self, name: str, producer: DeclarationRef | None, consumers: list[DeclarationRef]
    ) -> None:
        """An output no component reads: legal, and said out loud rather than left to linger."""
        if producer is not None and producer.scope is Scope.OUTPUT and not consumers:
            self._bag.add(
                "unused-output",
                f"'{name}' is written by component '{producer.component_name}' but read by nobody",
                producer.location(),
            )

    def _build_instance(
        self,
        name: str,
        refs: list[DeclarationRef],
        producer: DeclarationRef | None,
        definition: DataObject,
    ) -> tuple[ResolvedInstance, list[ResolvedLeaf]]:
        """One structured variable, plus the members it reaches the a2l as.

        The cross component checks are the ones every other object gets, and they run before
        this: who produces it, who reads it, whether the declarations agree. What is left here
        is the shape of the answer, which is two answers - the c declares one variable, and the
        a2l describes one object per member.
        """
        reference = producer or refs[0]
        for ref in refs:
            if ref is not reference:
                self._compare(reference, ref)

        consumers = [ref for ref in refs if ref.scope is Scope.INPUT]
        self._check_unused(name, producer, consumers)

        named = definition.declared_type
        assert named is not None
        structure = self._types[named].declared
        assert isinstance(structure, StructType)

        spelled = definition.declared_shape or ()
        instance = ResolvedInstance(
            name=name,
            type=named,
            kind=definition.kind,
            description=definition.description,
            shape=self._numeric_shape(spelled),
            dimensions=spelled,
            volatile=definition.volatile,
            section=definition.section,
            raster=_resolved_raster(producer, definition),
            condition=reference.condition,
            owner=producer.component_name if producer else None,
            consumers=tuple(sorted(ref.component_name for ref in consumers)),
            local=producer is not None and producer.scope is Scope.LOCAL,
            a2l=definition.a2l.model_copy(
                update={"export": resolve_export(ref.definition.a2l.export for ref in refs)}
            ),
        )
        leaves: list[ResolvedLeaf] = []
        for suffix in _element_paths(instance.shape):
            self._flatten(instance, structure, f"{name}{suffix}", leaves, reference)
        # The same question _build_variable asks of a plain object, asked of every leaf that
        # reaches the a2l: a member is an a2l object of its own, so a member with too many
        # dimensions gets exactly the MATRIX_DIM a plain object with too many would.
        for leaf in leaves:
            carried = instance.a2l.exported and leaf.a2l.exported
            if carried and len(leaf.shape) > _A2L_MAX_DIMENSIONS:
                self._bag.add(
                    "a2l-unrepresentable",
                    f"'{leaf.path}' has {len(leaf.shape)} dimensions, but the MATRIX_DIM of "
                    f"ASAP2 1.6.1 carries {_A2L_MAX_DIMENSIONS}; the extra dimensions are "
                    f"written out and only a 1.7 reader understands them",
                    reference.location("definition"),
                )
        return instance, leaves

    def _flatten(
        self,
        instance: ResolvedInstance,
        structure: StructType,
        path: str,
        out: list[ResolvedLeaf],
        reference: DeclarationRef,
    ) -> None:
        """Walk one structure, adding a leaf for every member that holds a value.

        A member that is itself a structure contributes its own members instead, at a longer
        path; an *array* of structures contributes them once per element, because there is no
        one address that describes ``cell[0].raw`` and ``cell[1].raw`` at the same time. An
        array of values is left whole: the a2l describes that with a ``MATRIX_DIM``.
        """
        for member in structure.members:
            if self._member_external(member) is not None:
                # Opaque storage: the member reaches the generated structure verbatim and
                # nothing else. DDD knows neither its layout nor its meaning, so there is no
                # leaf to resolve and nothing for the a2l to describe.
                continue
            here = f"{path}.{member.name}"
            nested = self._member_nested_structure(member)
            if nested is None:
                datatype, unit, conversion, limits = self._member_meaning(member)
                out.append(
                    ResolvedLeaf(
                        path=here,
                        instance=instance.name,
                        kind=instance.kind,
                        datatype=datatype,
                        description=member.description,
                        unit=unit,
                        conversion=conversion,
                        limits=limits,
                        shape=self._numeric_shape(member.dimensions),
                        dimensions=member.dimensions,
                        bits=member.bits,
                        volatile=instance.volatile,
                        section=instance.section,
                        raster=instance.raster,
                        condition=instance.condition,
                        owner=instance.owner,
                        consumers=instance.consumers,
                        local=instance.local,
                        # Both answers, resolved into the one the leaf is published under.
                        # The whole object's export reaches its members the way its storage
                        # class does: an instance kept out of the a2l takes every member
                        # with it, and a leaf carrying only the member's own opinion left
                        # the two halves for the a2l backend to put back together - so
                        # everything else, ``ddd compare`` included, read one half and
                        # believed it.
                        a2l=member.a2l.model_copy(
                            update={"export": instance.a2l.exported and member.a2l.exported}
                        ),
                    )
                )
                continue
            for suffix in _element_paths(self._numeric_shape(member.dimensions)):
                self._flatten(instance, nested, f"{here}{suffix}", out, reference)

    def _member_nested_structure(self, member: Member) -> StructType | None:
        """The structure a member is, or nothing when it holds a value of its own."""
        entry = self._declared_of(member)
        return entry if isinstance(entry, StructType) else None

    def _member_meaning(self, member: Member) -> tuple[Datatype, str, Conversion, Limits]:
        """What a value member holds and how to read it, from the member or from its type."""
        if member.typename is None:
            assert member.datatype is not None
            assert member.conversion is not None
            return (member.datatype, member.unit, member.conversion, member.physical_limits())
        entry = self._types[member.typename].declared
        assert isinstance(entry, ScalarType)
        limits = entry.limits
        if limits is None:
            low, high = conversion_range(entry.conversion, entry.datatype)
            limits = Limits(min=low, max=high)
        return (entry.datatype, entry.unit, entry.conversion, limits)

    def _build_variable(
        self,
        name: str,
        refs: list[DeclarationRef],
        producer: DeclarationRef | None,
        definition: DataObject,
        shapes: tuple[Shape, WrittenShape],
    ) -> Variable:
        shape, dimensions = shapes
        reference = producer or refs[0]
        limits_reference = self._limits_reference(refs, producer)

        for ref in refs:
            self._check_init_shape(ref, shape)
            if ref is not reference:
                self._compare(reference, ref)
            if limits_reference is not None and ref is not limits_reference:
                self._compare_limits(limits_reference, ref)

        self._check_unused(name, producer, [ref for ref in refs if ref.scope is Scope.INPUT])

        # Asked of every declaration, not of the producer's: an object the producer kept out
        # of the a2l is still in it if a consumer asked for it, and it is then still too many
        # dimensions for a MATRIX_DIM. Reading definition.a2l.export here would say "unstated"
        # is "not exported", which is backwards.
        exported = resolve_export(ref.definition.a2l.export for ref in refs)
        if len(shape) > _A2L_MAX_DIMENSIONS and exported:
            self._bag.add(
                "a2l-unrepresentable",
                f"'{name}' has {len(shape)} dimensions, but the MATRIX_DIM of ASAP2 1.6.1 "
                f"carries {_A2L_MAX_DIMENSIONS}; the extra dimensions are written out and only "
                f"a 1.7 reader understands them",
                reference.location("definition"),
            )

        return Variable(
            name=name,
            definition=definition,
            shape=shape,
            dimensions=dimensions,
            limits=(
                limits_reference.definition.physical_limits()
                if limits_reference is not None
                else definition.physical_limits()
            ),
            producer=producer,
            declarations=tuple(refs),
            condition=reference.condition,
        )

    def _limits_reference(
        self, refs: list[DeclarationRef], producer: DeclarationRef | None
    ) -> DeclarationRef | None:
        """The declaration whose stated limits the object resolves to; none states any.

        Omitting limits defers to whoever states them, so the resolved answer is the
        producer's when it states limits, else the first stated set in load order - and every
        other declaration that states limits is compared against that reference by
        :meth:`_compare_limits`. Only when nobody states any are the limits derived from the
        datatype and the conversion.
        """
        if producer is not None and producer.definition.limits is not None:
            return producer
        return next((ref for ref in refs if ref.definition.limits is not None), None)

    def _compare_limits(self, reference: DeclarationRef, other: DeclarationRef) -> None:
        """One declaration's stated limits against the stated set the object resolves to."""
        resolved = reference.definition.limits
        assert resolved is not None  # stating limits is what made it the reference
        stated = other.definition.limits
        if stated is None or stated.as_tuple() == resolved.as_tuple():
            return
        self._bag.add(
            "definition-mismatch",
            f"'{other.name}' is declared differently by component '{other.component_name}' "
            f"than by '{reference.component_name}' "
            f"(limits: {_describe_limits(other.definition)} != "
            f"{_describe_limits(reference.definition)})",
            other.location("definition"),
            notes=[("reference declaration", reference.location("definition"))],
        )

    def _check_init_shape(self, ref: DeclarationRef, resolved: Shape) -> None:
        """The shape of a stated init against the shape of the object.

        Checked here rather than in the contract, because only one of the two shapes is
        written in the file: a measurement or a value block declares its dimensions, while a
        curve or a map takes its shape from axes that are only known once the whole project
        is resolved. One check for both keeps the finding one identifier, ``init-invalid``.
        """
        init = ref.definition.init
        if not isinstance(init, tuple):
            # A scalar init fills every element of whatever the shape is; nothing to check.
            return
        declared = ref.definition.declared_shape
        if declared is None and not resolved:
            # A curve or map whose axes did not resolve; that is already reported.
            return
        # The declaration's own shape, resolved to numbers: an init is counted against the
        # value of a dimension, however that dimension happens to be spelled.
        shape = self._numeric_shape(declared) if declared is not None else resolved
        problem = check_shape(init, shape)
        if problem is None:
            return
        described = (
            f" has the shape {format_shape(shape)} given by its axes" if declared is None else ""
        )
        self._bag.add(
            "init-invalid",
            f"'{ref.name}'{described}: {problem}",
            ref.location("definition.init"),
        )

    def _compare(self, reference: DeclarationRef, other: DeclarationRef) -> None:
        """Compare two declarations of the same data object."""
        note = [("reference declaration", reference.location("definition"))]

        interface = differing(_INTERFACE_FIELDS, reference.definition, other.definition)
        if interface:
            self._bag.add(
                "definition-mismatch",
                f"'{other.name}' is declared differently by component '{other.component_name}' "
                f"than by '{reference.component_name}' "
                f"({spell_out(interface, reference.definition, other.definition)})",
                other.location("definition"),
                notes=note,
            )

        storage = differing(_STORAGE_FIELDS, reference.definition, other.definition)
        if storage:
            named = " and ".join(field.name for field in storage)
            self._bag.add(
                "storage-mismatch",
                f"'{other.name}': component '{other.component_name}' specifies a different "
                f"{named} than '{reference.component_name}' "
                f"({spell_out(storage, reference.definition, other.definition)}); "
                f"the value of '{reference.component_name}' is used",
                other.location("definition"),
                notes=note,
            )

        if reference.condition != other.condition:
            self._bag.add(
                "condition-mismatch",
                f"'{other.name}': component '{other.component_name}' uses condition "
                f"{_condition(other.condition)} while '{reference.component_name}' uses "
                f"{_condition(reference.condition)}",
                other.location("condition") if other.condition else other.location(),
                notes=[("reference declaration", reference.location())],
            )

    def _check_similar_names(self, ordered: list[tuple[str, list[DeclarationRef]]]) -> None:
        """Two object names differing only in case, plain and structured objects alike.

        Compared over every resolved object rather than over the plain variables only: a
        measurement ``sensor`` beside a structured object ``Sensor`` is exactly the confusion
        the check exists for, and the reader tripping over it does not care which of the two
        happens to name a structure.
        """
        groups: dict[str, list[str]] = defaultdict(list)
        for name, _ in ordered:
            groups[name.lower()].append(name)
        by_name = dict(ordered)
        for names in groups.values():
            if len(names) < 2:
                continue
            first, *rest = names
            for name in rest:
                self._bag.add(
                    "name-similar",
                    f"'{name}' and '{first}' differ only in upper/lower case",
                    by_name[name][0].location("definition.name"),
                    notes=[("other variable", by_name[first][0].location("definition"))],
                )


def _did_you_mean(name: str, candidates: Sequence[str], *, cutoff: float) -> str:
    """`` - did you mean 'Nm'?``: the suggestion suffix, empty when nothing is close enough.

    The cutoff stays with the caller: a unit or section is a short spelling and matches
    loosely at 0.5, a type name is longer and wants the stricter 0.6.
    """
    matches = difflib.get_close_matches(name, candidates, n=3, cutoff=cutoff)
    return f" - did you mean {_or_list(tuple(matches))}?" if matches else ""


def _or_list(values: tuple[str, ...]) -> str:
    """``'Nm' or 'rpm'``: how a did-you-mean suggestion spells its candidates."""
    return " or ".join(f"'{value}'" for value in values)


def _condition(condition: str | None) -> str:
    return f"'{condition}'" if condition else "no condition"


def _enum_key(conversion: EnumConversion) -> tuple[tuple[str, int], ...]:
    return tuple((e.name, e.value) for e in conversion.enumerators)


def _documentation_rank(conversion: EnumConversion) -> tuple[int, tuple[str, ...]]:
    """How well an enum is documented, as a totally ordered, order independent key."""
    descriptions = tuple(e.description for e in conversion.enumerators)
    return (sum(1 for text in descriptions if text), descriptions)


def _enum_summary(conversion: EnumConversion) -> str:
    return ", ".join(f"{e.name}={e.value}" for e in conversion.enumerators)


def _derived_range_is_finite(conversion: Conversion, raw_min: float, raw_max: float) -> bool:
    """Whether the physical range of that raw range under that conversion stays finite."""
    low, high = physical_range(conversion, raw_min, raw_max)
    return math.isfinite(low) and math.isfinite(high)


def _infinite_limits_message(datatype: Datatype) -> str:
    """One spelling for the three places a datatype and conversion pair can be written."""
    return f"the limits derived from '{datatype.value}' and this conversion are not finite"


def _below(value: float, limit: float) -> bool:
    return value < limit and not math.isclose(value, limit, rel_tol=1e-9, abs_tol=0.0)


def _above(value: float, limit: float) -> bool:
    return value > limit and not math.isclose(value, limit, rel_tol=1e-9, abs_tol=0.0)
