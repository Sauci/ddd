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
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, replace
from typing import Any, Final

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
from ddd.plugins import resolve_blocks, run_check_hooks

_A2L_MAX_DIMENSIONS = 3
"""Dimensions ``MATRIX_DIM`` can carry in the a2l version DDD writes (ASAP2 1.6.1)."""

_MAX_TYPE_NESTING = 64
"""How many levels of structure DDD reads.

A level is one structure: a structure whose members all hold values is one level deep, and
one nesting an *n* level structure is *n* + 1 - a scalar, an external type and a name nobody
declares are not structures and add no level. The limit exists because the walks over a
structure descend one call per level, so a chain a few hundred deep ends the run in python's
``RecursionError`` - a traceback rather than a finding - and no c compiler would accept the
generated header anyway.
"""

_MAX_ELEMENTS = 10_000_000
"""How many elements one array holds.

The dictionary, the a2l and the generated code carry every element, so a shape is not a
number DDD can hold at arm's length: the c backend broadcasts a scalar ``init`` into one
literal per element, and every element of an array of structures is spread out into leaves of
its own. An array of a billion is a run that writes no file and reports no finding for as
long as anybody cares to wait, so the shape is refused where it is written instead. The limit
sits well past any array a description means to state, and already past what a build would
enjoy - ten million literals is a generated file no compiler is happy with - because a shape
larger than this is a constant that resolved to the wrong number rather than storage anybody
planned.
"""

_MAX_LEAVES = 100_000
"""How many leaves an array of structures contributes.

A leaf is one value member of one element, and it reaches the dictionary as an object of its
own, the a2l as a record of its own and ``ddd list`` as a row of its own, because no single
address describes ``cell[0].raw`` and ``cell[1].raw`` at once. Far below
:data:`_MAX_ELEMENTS`, and for the reason the two differ in the outputs: an array of values
is one declaration and one ``MATRIX_DIM`` however long it is, where an array of structures
costs the outputs one entry per member per element.
"""

_INT_MIN, _INT_MAX = -(2**31), 2**31 - 1
"""Range of a c ``int`` on the 32 bit targets DDD generates for; bounds every enumerator."""

_EXPECTED_KIND: Final = {
    "axis": ObjectKind.AXIS,
    "x_axis": ObjectKind.AXIS,
    "y_axis": ObjectKind.AXIS,
    "input": ObjectKind.MEASUREMENT,
}
"""What each reference key of :attr:`~ddd.models.objects.DataObject.references` must name.

Every key a definition can carry is in here, because a reference whose kind nothing checks
would reach the a2l as an ``AXIS_PTS_REF`` pointing at a table, which a calibration tool
accepts and then misreads."""


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

    An identity or a linear conversion is compared in full, by
    :func:`~ddd.models.conversion.conversion_identity` - kind and parameters both. An enum
    compares by its name alone: the enumerators, descriptions included, are
    ``enum-conflict``'s to agree on, and folding them in here as well would turn one mistake
    into two findings - the second of which cannot even say what it means, because this field
    explains itself by calling :meth:`~ddd.models.conversion.EnumConversion.describe`, which
    names the enum and nothing else, so a reordered or revalued enumerator used to print
    identical text on both sides of the mismatch.
    """
    conversion = definition.conversion
    if conversion is None:
        # A structured declaration: the type carries the meaning, so there is no conversion
        # here to disagree about, and every declaration of the object says the same nothing.
        return None
    if isinstance(conversion, EnumConversion):
        return ("enum", conversion.name)
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
class _Cause:
    """Why a type is unusable: the check that says so, whether it was reported, and where."""

    check: str
    reported: bool
    location: Location


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

    @property
    def key(self) -> tuple[str, int]:
        """What identifies the declaration across the run: its component and its index."""
        return (self.component_name, self.index)

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
    extensions: dict[str, dict[str, Any]]

    @property
    def is_local(self) -> bool:
        return self.producer is not None and self.producer.scope is Scope.LOCAL

    @property
    def consumers(self) -> tuple[str, ...]:
        return tuple(
            sorted(ref.component_name for ref in self.declarations if ref.scope is Scope.INPUT)
        )

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
            id=definition.id,
            extensions=self.extensions,
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

    Walked with an explicit stack rather than by recursion, because this one runs over every
    declared type - the ones :data:`_MAX_TYPE_NESTING` refused included, since they still
    reach the dictionary as declarations - and so cannot lean on that cap the way the walks
    inside the analysis do.
    """
    ordered: list[LoadedType] = []
    placed: set[str] = set()
    walking: set[str] = set()
    stack: list[tuple[str, Iterator[str]]] = []

    for start in sorted(declared):
        if start in placed:
            continue
        walking.add(start)
        stack.append((start, iter(_nested_names(declared[start]))))
        while stack:
            name, pending = stack[-1]
            nested = next(pending, None)
            if nested is None:
                stack.pop()
                walking.discard(name)
                entry = declared[name]
                if entry.structure is not None:
                    ordered.append(entry)
                placed.add(name)
            elif nested in declared and nested not in placed and nested not in walking:
                walking.add(nested)
                stack.append((nested, iter(_nested_names(declared[nested]))))
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


def _nested_names(entry: LoadedType) -> list[str]:
    """The names the members of a structure nest, in the order the members are written."""
    return [nested for _, _, nested in _nested_types(entry)]


def _nesting_cycle(
    start: str, declared: dict[str, LoadedType], settled: set[str]
) -> tuple[str, ...]:
    """The chain of nested structures leading from ``start`` back to a name already on it.

    Returns the cycle itself rather than a bare yes, because the chain is the only useful part
    of the finding: ``A -> B -> C -> A`` says which member to remove, where "A is recursive"
    leaves the reader to work out how. An undeclared name met on the way has no members to
    follow and is not one; it is reported as ``unknown-type``.

    ``start`` is a declared name - the walk is run once per declared type. Walked with an
    explicit stack, because the chain leading *into* a cycle is as long as somebody wrote it:
    a type that nests itself has no depth at all, so :data:`_MAX_TYPE_NESTING` refuses nothing
    here and a recursive walk would run out of stack before it found the cycle to report.

    Nesting is not a tree, though: two members of one structure can nest the same name, which
    doubles as a route to whatever *it* nests, and so on - so sharing a few levels deep costs
    as much again as walking it out in full would for each route, and enough levels of it is
    exponential. ``settled`` is what stops that: the classic three-colour walk's black, a name
    added to it only once every name it nests, however deep, has been walked without meeting
    the chain that was open at the time. A settled name can never be *on* a cycle - reaching
    one from it would mean that walk had met the chain first, rather than running out of names
    to try - so it is skipped wherever it is met rather than walked again. It is the caller's
    to keep, and shared rather than made fresh here, because the sharing this guards against is
    not only within one ``start``'s own walk: :meth:`_Analysis._check_types` keeps one
    ``settled`` across every ``start`` in its pass, so a name one type's search has already
    cleared is not walked again from the next. A cycle only reachable from that next type is
    still found regardless - reaching it at all means walking its members, and a name only
    joins ``settled`` once its own walk found none, so nothing on an unreported cycle ever is.
    ``on_chain`` mirrors ``chain`` for the plainer reason that a long chain with nothing shared
    to remember still walks every name on it once: searching the list for each of those cost
    the square of the chain's length, where a set costs one.
    """
    chain: list[str] = [start]
    on_chain: set[str] = {start}
    stack: list[Iterator[str]] = [iter(_nested_names(declared[start]))]
    while stack:
        nested = next(stack[-1], None)
        if nested is None:
            stack.pop()
            name = chain.pop()
            on_chain.discard(name)
            settled.add(name)
        elif nested in on_chain:
            return (*chain[chain.index(nested) :], nested)
        elif nested in settled:
            continue
        elif nested in declared:
            chain.append(nested)
            on_chain.add(nested)
            stack.append(iter(_nested_names(declared[nested])))
    return ()


def _nesting_depths(declared: dict[str, LoadedType]) -> tuple[dict[str, int], set[str]]:
    """How many levels deep each declared type nests, and separately, which never bottom out.

    Levels as :data:`_MAX_TYPE_NESTING` counts them: a structure whose members all hold values
    is one level, a structure nesting an *n* level structure is *n* + 1, and anything that is
    not a structure - a scalar, an external type, a name no file declares - is no level at
    all. A type that nests itself, however far down, is left out of the depths rather than
    given a number: it has no bottom, it is reported as ``type-cycle``, and a second finding
    about it would say the same mistake twice under another identifier. It is put in the
    second set instead, together with every type that nests it - the mark travels outwards as
    each name on the path is popped - because that fact matters beyond the finding: a walk
    that does not know to stop at a cyclic type has as little a bottom to reach as the type
    does. Returned rather than resolved into a finding here, because that is
    :meth:`_Analysis._refuse_deep_nesting`'s to make - this function only answers the question
    its name asks.

    Walked with an explicit stack, for the very reason the answer is wanted: a recursive walk
    over a chain deep enough to be worth reporting is the traceback this exists to prevent.
    """
    depths: dict[str, int] = {}
    cyclic: set[str] = set()
    stack: list[tuple[str, Iterator[str]]] = []

    for start in sorted(declared):
        if start in depths or start in cyclic:
            continue
        chain: set[str] = {start}
        stack.append((start, iter(_nested_names(declared[start]))))
        while stack:
            name, pending = stack[-1]
            nested = next(pending, None)
            if nested is None:
                stack.pop()
                chain.discard(name)
                names = _nested_names(declared[name])
                if any(found in cyclic for found in names):
                    # Whatever reaches a cycle has no bottom either, so the mark travels up
                    # the chain as each name on it is popped.
                    cyclic.add(name)
                elif declared[name].structure is None:
                    depths[name] = 0
                else:
                    depths[name] = 1 + max((depths.get(n, 0) for n in names), default=0)
            elif nested in chain:
                cyclic.add(nested)
            elif nested in declared and nested not in depths and nested not in cyclic:
                chain.add(nested)
                stack.append((nested, iter(_nested_names(declared[nested]))))
    return depths, cyclic


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
        self._plugins = {plugin.name: plugin for plugin in workspace.plugins}
        """The plugins in play, by name; what resolves a block."""
        self._enums = _EnumRegistry()
        self._types = {entry.name: entry for entry in workspace.types}
        """Every type the project declares, by name - structures and scalars alike."""
        self._constants = {entry.name: entry for entry in workspace.constants}
        """Every constant the project declares, by name; a shape names one of them."""
        self._poisoned_types: dict[str, _Cause] = {}
        """Types no variable can resolve as: they nest each other recursively, or a member
        of theirs, however deeply nested, names a type nobody declares or carries a
        conversion that was refused. The finding sits at the member or at the type; a
        declaration naming such a type is dropped, so nothing downstream reasons about a
        leaf it cannot have. Each carries the cause that poisoned it, so that a variable of
        the type can say, when the cause was silenced, what nobody reported."""
        self._unwalkable_types: set[str] = set()
        """A type no walk may descend into: it nests deeper than :data:`_MAX_TYPE_NESTING`,
        or it never bottoms out at all, which is what nesting a cycle means.

        Kept apart from the poison because it says a second thing about them that poison does
        not. Everything else that is unusable is unusable about its leaves - a walk over it
        terminates, and the alignment estimate for one still answers from the members it does
        understand - while these are the ones a walk cannot reach the bottom of at all: the
        over-deep ones because :data:`_MAX_TYPE_NESTING` is where DDD stops reading, the
        cyclic ones because there is no bottom to reach. Both are computed once, by
        :func:`_nesting_depths`, and every type nesting one of them is added here too, in
        :meth:`_refuse_deep_nesting` - the same walk-safety invariant a poisoned type gives
        the rest of the analysis, stated over "unwalkable" instead of "unusable"."""
        self._type_leaves: dict[str, int] = {}
        """How many leaves one variable of each declared type contributes, by name.

        Filled by :meth:`_check_types`, and holding an entry for every type a variable can
        still be declared as: a type left out of it - one poisoned before the count, or one
        nesting such a type - is one no declaration resolves as, so :meth:`_shape_fits` never
        asks about a name that is missing here."""
        self._external_reach: dict[str, bool] = {}
        """Whether a variable of a type contains an external member, for each name walked so far.

        Filled by :meth:`_reaches_external` as the placement checks ask it, and never
        invalidated: the answer is a property of the declared nesting, which nothing changes
        after the types are read. What keeps the alignment estimate linear - see that method
        for why one walk answers for every type under the one it starts at."""
        self._census: dict[str, list[DeclarationRef]] = defaultdict(list)
        """Every declaration that is not a duplicate, in load order, whether or not it resolved.

        What ownership is decided over. A declaration the analysis could not resolve is still
        a declaration: a consumer of an object whose producer names an unknown type is not
        reading something nobody produces, and an output whose only reader was dropped is
        not unread. Erasing dropped declarations from the census made both findings fire,
        each pointing at the file the mistake was not in."""
        self._dropped: dict[tuple[str, int], bool] = {}
        """The declarations that were dropped as unresolvable, and whether a finding said why.

        ``True`` when the cause was reported at whatever severity, ``False`` when it was
        silenced; a silenced cause is what :meth:`_refuse` and :meth:`_drop_for_type` turn
        into ``incomplete-project``, because an absence nothing mentions is the one way this
        tool is wrong without anybody being told."""
        self._refs: dict[str, list[DeclarationRef]] = defaultdict(list)
        self._effective: dict[str, DataObject] = {}
        """The definition that counts for each name: the producer's, once known."""
        self._via: dict[str, tuple[str, str]] = {}
        """For a name absent because of what it refers to, the reference key and its target.

        The absence is discovered in a fixpoint over references and reported after it, so
        which reference took the name down has to be carried between the two: it is what
        lets the finding sit at the ``axis`` or the ``input`` key rather than at the whole
        declaration, which by itself says nothing about why the object went."""
        self._dangling: dict[str, str] = {}
        """For a name absent because its own reference was refused and the refusal silenced,
        the check that was silenced.

        What tells the two absences apart in the report: a target that *did not* resolve was
        declared and dropped, and its own declaration is where to look, while one that *does
        not* resolve names nothing at all, and the check nobody reported is the whole story.
        Set only for a silenced refusal, and always beside the :attr:`_via` entry that names
        it, so it is also what says that entry is the one the report wants."""

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

        # Ownership is decided over every declaration, dropped ones included, because the
        # producer owns the definition and a dropped producer is still the one that claimed
        # it. It has to be settled before anything that reads a definition - in particular
        # before curves and maps look up their axes.
        owners = {
            name: self._select_producer(name, refs) for name, refs in sorted(self._census.items())
        }
        absent = self._absent(ordered, owners)
        self._report_absences(absent, owners)
        resolved = [(name, refs) for name, refs in ordered if name not in absent]
        shapes = {name: self._resolve_shape(self._effective[name]) for name, _ in resolved}
        resolved = self._refuse_wide_maps(resolved, shapes, owners)

        structured = [(name, refs) for name, refs in resolved if self._is_structured(name)]
        plain = [(name, refs) for name, refs in resolved if not self._is_structured(name)]
        reaching_a2l = self._a2l_closure(resolved)
        variables = [
            self._build_variable(
                name,
                refs,
                owners[name],
                self._effective[name],
                shapes[name],
                reaches_a2l=name in reaching_a2l,
            )
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

        extensions = resolve_blocks(self._plugins, workspace.project_extensions, on_project=True)
        dictionary = DataDictionary(
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
            plugins=tuple(sorted(self._plugins)),
            extensions=extensions,
        )
        # Inside the analysis rather than beside it, so that nothing that analyses a project -
        # the cli, the language server, a test - can forget to run them. A hook sees the whole
        # dictionary, and every built-in finding is already in the bag.
        run_check_hooks(workspace.plugins, dictionary, self._bag, workspace.locate)
        return dictionary

    def _a2l_closure(self, resolved: list[tuple[str, list[DeclarationRef]]]) -> set[str]:
        """The objects the a2l carries: the exported ones and, transitively, what they refer to.

        The closure the a2l backend takes over the dictionary - an exported curve pulls its
        axis in, and the axis the measurement it is indexed by, whatever their own ``export``
        says, because a reference to an absent object would be an invalid file rather than a
        smaller one - computed here so that a finding about reaching the file asks the question
        the backend answers.

        Every reference met here resolves: a name whose target is absent, or names nothing at
        all, is itself absent and is not among the resolved names this walks.
        """
        reached = {
            name
            for name, refs in resolved
            if resolve_export(ref.definition.a2l.export for ref in refs)
        }
        pending = list(reached)
        while pending:
            for referenced in self._effective[pending.pop()].references.values():
                if referenced not in reached:
                    reached.add(referenced)
                    pending.append(referenced)
        return reached

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
                assert member.datatype is not None
                location = entry.location(f"members[{index}].conversion")
                self._register_enum(member.conversion, location, member.datatype)
                raw_min, raw_max = _member_raw_range(member)
                self._check_enum_fits(
                    member.conversion, raw_min, raw_max, member.datatype.value, location
                )

    def _check_member_limits(self, entry: LoadedType) -> None:
        """A member's stated limits are held to its storage, as a declaration's are.

        The same finding ``_check_limits`` reports on a definition: limits wider than the
        datatype and the conversion can represent reach the a2l as a range the calibration
        tool offers and the storage cannot hold.
        """
        structure = entry.structure
        if structure is None:
            return
        for index, member in enumerate(structure.members):
            if member.limits is None or member.datatype is None:
                continue
            assert member.conversion is not None
            low, high = physical_range(member.conversion, *_member_raw_range(member))
            self._check_limits_fit(
                member.limits,
                low,
                high,
                member.datatype,
                entry.location(f"members[{index}].limits"),
            )

    def _check_scalar_type(self, entry: LoadedType) -> None:
        """A scalar type's own limits and enum, answered where the type is declared.

        Once, and whether or not a declaration names it. What a type fixes is the type's to
        answer: asking every declaration instead reported one mistake once per component, at
        files whose authors cannot fix it - the limits are not written there and may not be -
        and said nothing at all about a type the project has declared and nobody names yet.
        The members of a structure are already checked here for the same reason, by
        :meth:`_register_member_enums` and :meth:`_check_member_limits`.
        """
        declared = entry.declared
        if not isinstance(declared, ScalarType):
            return
        datatype = declared.datatype
        conversion = declared.conversion
        if isinstance(conversion, EnumConversion):
            location = entry.location("conversion")
            self._register_enum(conversion, location, datatype)
            self._check_enum_fits(
                conversion, datatype.raw_min, datatype.raw_max, datatype.value, location
            )
        if declared.limits is not None:
            low, high = conversion_range(conversion, datatype)
            self._check_limits_fit(declared.limits, low, high, datatype, entry.location("limits"))

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
        if name in self._unwalkable_types:
            # The placement checks ask this of every declaration that states a section,
            # dropped ones included, which is the one walk that still starts at a type the
            # nesting cap refused, or one that nests a cycle without crossing the cap itself
            # - and the chain under either is what no walk here may follow. Met at the start
            # of a walk and never below it: a type nesting an unwalkable one is unwalkable as
            # well, so nothing that gets past this line meets one further down.
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

        Memoised in :attr:`_external_reach`, because the answer closes upwards: a type reaches
        an external member exactly when one of the types its members name does, so the one
        walk that answers for a type has answered for every type under it as well. That is
        what makes the estimate linear. :meth:`_type_alignment` asks this at every type it
        visits and the placement checks start it again for every declaration that states a
        section, so answered afresh each time it was a walk of the whole graph per type per
        declaration - seconds of it on a project of a few hundred deeply nested structures.

        A name already on ``seen`` is one this walk reached by a second route: a diamond,
        which the ``any`` below has already got past, so the answer for it was no. It is not
        followed again, exactly as in :meth:`_poison_of`, and a cycle is not this walk's
        business either way - it is reported as ``type-cycle``.

        Unguarded by :attr:`_unwalkable_types`, and safe without it: the walk is entered from
        :meth:`_type_alignment` and nowhere else, straight after that guard, so it always
        starts at a walkable name, and the recursion below never leaves that set - a walkable
        name has no unwalkable name under it, because :meth:`_refuse_deep_nesting` and the
        cyclic union it makes mark every type that nests an unwalkable one as unwalkable too.
        """
        if name in seen:
            return False
        cached = self._external_reach.get(name)
        if cached is not None:
            return cached
        seen.add(name)
        entry = self._types.get(name)
        if entry is None:
            return False
        if entry.external is not None:
            answer = True
        else:
            answer = any(
                self._reaches_external(nested, seen) for _, _, nested in _nested_types(entry)
            )
        self._external_reach[name] = answer
        return answer

    def _check_types(self) -> None:
        """Every nested structure is declared, nests no more than DDD reads, and not itself.

        All three are refused rather than resolved as far as possible. A member whose structure
        is unknown has no size, so every offset after it in the enclosing structure would be
        wrong and the generated addresses would silently point at the wrong bytes; a structure
        that contains itself has no size at all; and one nesting deeper than
        :data:`_MAX_TYPE_NESTING` is more than the walks below can follow.
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
            self._check_member_limits(entry)
            self._check_scalar_type(entry)
            for index, member, nested in _nested_types(entry):
                target = declared.get(nested)
                if target is None:
                    location = entry.location(f"members[{index}]")
                    reported = (
                        self._bag.add(
                            "unknown-type",
                            f"member '{member.name}' names datatype '{nested}', which is neither "
                            f"a base datatype nor a type any file of this project declares"
                            f"{self._nearest_type(nested)}",
                            location,
                        )
                        is not None
                    )
                    self._poisoned_types.setdefault(
                        entry.name, _Cause("unknown-type", reported, location)
                    )

        # Before the cycle walk and everything after it: what those walk into is what the cap
        # bounds, so a type too deep to follow has to be poisoned before anybody follows it.
        depths, cyclic = _nesting_depths(declared)
        self._refuse_deep_nesting(depths, cyclic)

        # After the depth refusal, because the count walks the nesting graph and so may only
        # start at a type a walk can reach the bottom of; the depths it reports in are that
        # walk's answer as well.
        self._type_leaves = self._leaves_of_types()
        self._refuse_wide_types(depths)

        # Keyed on the participants of the cycle rather than on the structure the walk started
        # from. Those differ: a sound structure nesting a recursive one reaches the same cycle,
        # and keying on the start would report it once per route into it - so the cause is made
        # when the cycle is first met and reused by every later type that reaches it.
        causes: dict[frozenset[str], _Cause] = {}
        # One `settled` for the whole pass, not one per start: it is what keeps a name shared
        # between types from being walked again for every type that shares it - see
        # `_nesting_cycle`.
        settled: set[str] = set()
        for entry in self._workspace.types:
            cycle = _nesting_cycle(entry.name, declared, settled)
            if not cycle:
                continue
            cause = causes.get(frozenset(cycle))
            if cause is None:
                # At the structure the cycle closes on rather than the one the walk started
                # from, for the same reason.
                location = declared[cycle[0]].location()
                cause = _Cause(
                    "type-cycle",
                    self._bag.add(
                        "type-cycle",
                        f"structured datatypes nest each other: {' -> '.join(cycle)}",
                        location,
                    )
                    is not None,
                    location,
                )
                causes[frozenset(cycle)] = cause
            # Every type whose walk reaches the cycle is unusable: it has no size, so a
            # variable of it cannot be flattened. Poisoned here, refused at resolution.
            self._poisoned_types.setdefault(entry.name, cause)

        for entry in self._workspace.types:
            self._refuse_infinite_type_limits(entry)
        # Propagated the way the cycles are: a sound structure nesting a broken one has the
        # same unresolvable leaves, and a variable of either is dropped at resolution, saying
        # what poisoned the inner one.
        for entry in self._workspace.types:
            cause = self._poison_of(entry.name, set())
            if cause is not None:
                self._poisoned_types.setdefault(entry.name, cause)

    def _refuse_deep_nesting(self, depths: dict[str, int], cyclic: set[str]) -> None:
        """A structure nesting deeper than DDD reads is refused, and so is every one over it.

        Reported once, at the innermost type that is already too deep - the one whose own
        nesting crosses the limit - because every type nesting that one is too deep for
        exactly the same reason, and a finding per level would answer one mistake with
        hundreds. All of them are poisoned with that one cause, so a variable of any of them
        is dropped the way a variable of a recursive structure is, and so that no walk after
        this one descends a chain the stack cannot take: a type this leaves alone nests at
        most :data:`_MAX_TYPE_NESTING` levels, and following it to the bottom is safe.

        ``cyclic`` is folded into :attr:`_unwalkable_types` here too, without a cause of its
        own: a type that nests a cycle has no depth, so the loop below never meets it, and it
        is reported as ``type-cycle`` a few lines below this method's caller rather than as
        ``schema`` here. What it needs from this method is only the same walk-safety mark the
        over-deep types get, not a second finding - the invariant a later walk relies on is
        "unwalkable", not "why".
        """
        self._unwalkable_types.update(cyclic)
        deep: dict[str, _Cause] = {}
        # In depth order, so that a type over the limit meets the cause of the nested type
        # that is over it as well before it would make one of its own.
        for entry in sorted(self._workspace.types, key=lambda item: depths.get(item.name, 0)):
            depth = depths.get(entry.name, 0)
            if depth <= _MAX_TYPE_NESTING:
                # A type with no depth at all is one that nests itself, or nests a cycle -
                # folded into the guard set above already, and left to the cycle walk below
                # for its finding; it is not this one's to answer.
                continue
            cause = next((deep[name] for name in _nested_names(entry) if name in deep), None)
            if cause is None:
                location = entry.location()
                # What the bag made of the finding rather than what this check's severity is
                # today, exactly as :meth:`_refuse_infinite_type_limits` asks it.
                reported = (
                    self._bag.add(
                        "schema",
                        f"structure '{entry.name}' nests {depth} levels deep; DDD reads at "
                        f"most {_MAX_TYPE_NESTING}",
                        location,
                    )
                    is not None
                )
                cause = _Cause("schema", reported, location)
            deep[entry.name] = cause
            self._unwalkable_types.add(entry.name)
            self._poisoned_types.setdefault(entry.name, cause)

    def _leaves_of_types(self) -> dict[str, int]:
        """How many leaves one variable of each declared type would contribute, by name.

        Counted over the nesting graph and never by spreading an instance out, which is the
        whole point of counting at all: two members of one structure may nest the same type,
        so the routes an instance takes double at every level that shares a name, and a
        ladder of twenty such levels is a million leaves that a walk over the *instance*
        would visit one at a time. Here every type is counted once, from the bottom up, and
        the answer for a member is multiplied by the elements of that member rather than
        walked once per element.

        A type already refused when this runs - poisoned, or one of the ones no walk may
        descend into - is skipped rather than counted: no variable resolves as it, so it has
        no leaves to contribute, and the two sets are also where the cyclic types are, which
        have no bottom to count from. A type nesting one of those has no count either, and
        that answer is recorded like any other so a shared name is not re-walked for every
        route into it; it is left out of the result, which is sound because every such type
        is poisoned by the end of :meth:`_check_types` - by :meth:`_poison_of`, which walks
        the same graph - so nothing declares a variable of one.

        Walked with an explicit stack, like the depths and for the same reason: the graph is
        as deep as :data:`_MAX_TYPE_NESTING` allows, and this walk is what a run has instead
        of the traceback.
        """
        # A snapshot, and nothing below poisons anything, so it stays the answer throughout.
        refused = self._poisoned_types.keys() | self._unwalkable_types
        walked: dict[str, int | None] = {}
        stack: list[tuple[str, Iterator[str]]] = []
        for start in sorted(self._types):
            if start in walked or start in refused:
                continue
            stack.append((start, iter(_nested_names(self._types[start]))))
            while stack:
                name, pending = stack[-1]
                nested = next(pending, None)
                if nested is None:
                    stack.pop()
                    walked[name] = self._leaves_of(self._types[name], walked)
                elif nested not in walked and nested not in refused:
                    stack.append((nested, iter(_nested_names(self._types[nested]))))
        return {name: count for name, count in walked.items() if count is not None}

    def _leaves_of(self, entry: LoadedType, walked: dict[str, int | None]) -> int | None:
        """The leaves one variable of this type contributes, from the answers for what it nests.

        Counted the way :meth:`_flatten` spreads a variable out, which is what the number has
        to describe: a member naming an external type is opaque storage and contributes no
        leaf at all, a member holding a value contributes exactly one however many dimensions
        it has - an array of values is one record with a ``MATRIX_DIM`` - and only a member
        nesting a structure multiplies, contributing that structure's leaves once per element.
        A scalar type is one leaf and an external type is none, which is what a member naming
        either is worth to the structure above it.

        ``None`` when a name it nests has no answer, which is what a name refused before the
        count leaves behind; the caller records that as the answer for this type too. Every
        dimension resolves here, because a member dimensioned by a constant nobody declares
        poisons its structure before this runs, and a poisoned type is not counted.
        """
        structure = entry.structure
        if structure is None:
            return 0 if entry.external is not None else 1
        total = 0
        for member in structure.members:
            if self._member_external(member) is not None:
                continue
            nested = self._member_structure(member)
            if nested is None:
                total += 1
                continue
            count = walked.get(nested)
            if count is None:
                return None
            total += count * math.prod(self._numeric_shape(member.dimensions))
        return total

    def _refuse_wide_types(self, depths: dict[str, int]) -> None:
        """A structure of more leaves than the outputs carry, and every one over it, is refused.

        Refused at the type rather than at each variable of it, for the reason the nesting cap
        is: the type is unusable, and saying so once where it is declared beats saying it at
        every declaration that names it. Reported at the innermost type that is already too
        wide - a type nesting it has at least as many leaves for exactly the same reason -
        and all of them are poisoned with that one cause, so a variable of any of them is
        dropped the way a variable of a recursive structure is.

        A type with no count is one that was refused before the count and is poisoned
        already; the limit has nothing to add about it.
        """
        wide: dict[str, _Cause] = {}
        # In depth order, so that a type over the limit meets the cause of the nested type
        # that is over it as well before it would make one of its own.
        for entry in sorted(self._workspace.types, key=lambda item: depths.get(item.name, 0)):
            leaves = self._type_leaves.get(entry.name, 0)
            if leaves <= _MAX_LEAVES:
                continue
            cause = next((wide[name] for name in _nested_names(entry) if name in wide), None)
            if cause is None:
                location = entry.location()
                # What the bag made of the finding rather than what this check's severity is
                # today, exactly as :meth:`_refuse_infinite_type_limits` asks it.
                reported = (
                    self._bag.add(
                        "schema",
                        f"structure '{entry.name}' has {leaves} leaves; DDD carries at most "
                        f"{_MAX_LEAVES}",
                        location,
                    )
                    is not None
                )
                cause = _Cause("schema", reported, location)
            wide[entry.name] = cause
            self._poisoned_types.setdefault(entry.name, cause)

    def _poison_of(self, name: str, seen: set[str]) -> _Cause | None:
        """What makes a variable of that type unresolvable, if anything does.

        The type's own cause when it has one; else the first cause found walking its nested
        structures. A cycle is not this walk's business - it is reported and recorded as
        ``type-cycle`` before this runs - so a name already seen is not followed again. A
        nested name nobody declares was recorded as ``unknown-type`` on the type naming it, so
        the walk only ever gets past a name this project declares.

        Still recursive, and bounded by the cap rather than by an explicit stack: it stops at
        the first poisoned name, and by the time it runs a name that is not poisoned nests at
        most :data:`_MAX_TYPE_NESTING` levels - one deeper, or one on a cycle, was poisoned by
        the two walks above.
        """
        if name in seen:
            return None
        seen.add(name)
        cause = self._poisoned_types.get(name)
        if cause is not None:
            return cause
        for _, _, nested in _nested_types(self._types[name]):
            found = self._poison_of(nested, seen)
            if found is not None:
                return found
        return None

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
                location = entry.location("conversion")
                # What the bag made of the finding, rather than what this check's severity is
                # today: a variable of the type is to say what nobody said, and whether
                # anybody did is the bag's answer to give.
                reported = (
                    self._bag.add("schema", _infinite_limits_message(datatype), location)
                    is not None
                )
                self._poisoned_types.setdefault(entry.name, _Cause("schema", reported, location))
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
                location = entry.location(f"members[{index}].conversion")
                reported = (
                    self._bag.add("schema", _infinite_limits_message(member.datatype), location)
                    is not None
                )
                self._poisoned_types.setdefault(entry.name, _Cause("schema", reported, location))

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
                    location = entry.location(f"members[{position}].dimensions[{index}]")
                    reported = (
                        self._bag.add(
                            "unknown-constant",
                            f"member '{member.name}' of structure '{entry.name}' is dimensioned "
                            f"by '{dimension}', which is not a constant any file of this "
                            f"project declares{self._nearest_constant(dimension)}",
                            location,
                        )
                        is not None
                    )
                    self._poisoned_types.setdefault(
                        entry.name, _Cause("unknown-constant", reported, location)
                    )

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
        ref: DeclarationRef,
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

        The drop is recorded against the declaration rather than the name, because a name may
        be declared by several components and only some of those declarations dropped.
        """
        reported = self._bag.add(check, message, location, notes) is not None
        self._dropped[ref.key] = self._dropped.get(ref.key, False) or reported
        if reported:
            return
        self._bag.add(
            "incomplete-project",
            f"the declaration of '{ref.name}' by component '{ref.component_name}' is not in "
            f"the data dictionary: the {check} that says why is not reported, so nothing "
            f"reading the dictionary - the listing, the dump, every backend - carries it either",
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
                    ref,
                )
                resolves = False
        return resolves

    def _shape_fits(self, ref: DeclarationRef) -> bool:
        """Whether the array this declaration describes is one the outputs could carry.

        Asked once the shape has resolved to numbers and the type it names is known, which is
        the earliest either limit can be applied, and before anything expands the shape: the
        c backend broadcasts a scalar ``init`` into one literal per element, and a structured
        variable is flattened into one leaf per member per element. Both used to be reached
        with whatever the file said, so an array of a billion was a run with no output and no
        end rather than a finding.

        Two limits, because the two arrays cost the outputs differently. An array of values
        is one declaration and one ``MATRIX_DIM`` however long it is, so only
        :data:`_MAX_ELEMENTS` speaks about it; an array of structures is spread out, so it is
        weighed in leaves first - the tighter and the more telling of the two answers - and
        by its elements after, which is what still bounds the element paths of a structure
        whose members are every one of them opaque and so contributes no leaf at all.

        Reported where the shape is written, which is ``size`` on an axis and ``dimensions``
        everywhere else, and routed through :meth:`_refuse` so that the declaration is
        dropped and the objects referring to it follow it out.
        """
        definition = ref.definition
        spelled = definition.declared_shape
        if spelled is None:
            # A curve or a map is shaped by its axes, and each axis is an array of its own,
            # weighed here when its own declaration is collected. That bounds a curve, whose
            # shape is one axis, but not a map, whose shape is the product of two - only
            # known once every axis has resolved, which `_refuse_wide_maps` weighs once `run`
            # has turned axes into numbers.
            return True
        elements = math.prod(self._numeric_shape(spelled))
        location = ref.location(
            "definition.size" if isinstance(definition, Axis) else "definition.dimensions"
        )
        named = definition.declared_type
        if named is not None and self._is_structure(named):
            # Present for every structure a declaration can still resolve as: one refused
            # before the count was poisoned, and this declaration was dropped at its type.
            leaves = elements * self._type_leaves[named]
            if leaves > _MAX_LEAVES:
                self._refuse(
                    "schema",
                    f"'{ref.name}' would contribute {leaves} leaves; DDD carries at most "
                    f"{_MAX_LEAVES}",
                    location,
                    ref,
                )
                return False
        if elements > _MAX_ELEMENTS:
            self._refuse(
                "schema",
                f"'{ref.name}' has {elements} elements; DDD carries at most {_MAX_ELEMENTS}",
                location,
                ref,
            )
            return False
        return True

    def _refuse_wide_maps(
        self,
        resolved: list[tuple[str, list[DeclarationRef]]],
        shapes: dict[str, tuple[Shape, WrittenShape]],
        owners: dict[str, DeclarationRef | None],
    ) -> list[tuple[str, list[DeclarationRef]]]:
        """Drop a map whose two axes multiply past `_MAX_ELEMENTS`, keeping everything else.

        `_shape_fits` weighs every other shape while a declaration is still being collected,
        but a curve and a map write no `declared_shape` of their own and pass through it
        unweighed. A curve is safe left that way: its one axis already passed `_shape_fits`
        at the cap on its own account, so the curve's shape can never exceed it either. A map
        is not - each axis is bounded, but their product is not, and the product is only a
        number once `_resolve_shape` has turned both axes into one, which `run` does after
        ownership and `_effective` are settled. So this runs as a second pass over
        `resolved`, the earliest point a map's shape is known, rather than moving
        `_shape_fits` itself to after axis resolution and reworking how a drop there reaches
        referrers.

        Refused at the owning declaration's whole `definition`: a map states no field a
        finding could sit at the way `dimensions` or an axis's `size` can. The name is
        dropped from what is returned exactly as one absent for any other reason is, so
        nothing after this builds a variable, an a2l record or a generated literal for it -
        and nothing needs re-running, because a map is never a reference target and `schema`
        is a fixed error, always reported.
        """
        oversized: set[str] = set()
        for name, refs in resolved:
            definition = self._effective[name]
            if definition.declared_shape is not None:
                continue
            elements = math.prod(shapes[name][0])
            if elements <= _MAX_ELEMENTS:
                continue
            oversized.add(name)
            owner = owners[name] or refs[0]
            self._refuse(
                "schema",
                f"{definition.kind.value} '{name}' would hold {elements} elements over its "
                f"axes; DDD carries at most {_MAX_ELEMENTS}",
                owner.location("definition"),
                owner,
            )
        return [(name, refs) for name, refs in resolved if name not in oversized]

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
                ref,
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
                ref,
                notes=[("declared here", declared.location())],
            )
            return None
        if isinstance(entry, StructType):
            if named in self._poisoned_types:
                # A variable of a structure whose leaves cannot be resolved cannot be resolved
                # either; what poisoned the structure decides whether anything says so.
                self._drop_for_type(ref, named)
                return None
            # Kept as it was written. A structured variable has no single datatype, no limits
            # and no initial value, so it takes a road of its own from here on; what it shares
            # with every other declaration - who owns it, who reads it, what it is called - is
            # settled on the way by exactly the same checks.
            return ref if self._structure_fits(ref, named, declared) else None
        if named in self._poisoned_types:
            # The refused conversion sits at the scalar type; a variable of it has no limits
            # to resolve, so it goes the same way a structured one does.
            self._drop_for_type(ref, named)
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

    def _drop_for_type(self, ref: DeclarationRef, named: str) -> None:
        """Drop a declaration of a poisoned type, and say so when nothing else did.

        The cycle, the unknown member type or the refused conversion is reported at the type,
        and a second finding here would only repeat it with a worse location. Unless the
        first was silenced: then the variable would simply be gone, from the listing, the
        dump and every backend, and the one place that can say so is this declaration.
        """
        cause = self._poisoned_types[named]
        self._dropped[ref.key] = cause.reported
        if cause.reported:
            return
        self._bag.add(
            "incomplete-project",
            f"the declaration of '{ref.name}' by component '{ref.component_name}' is not in "
            f"the data dictionary: it names the type '{named}', and the {cause.check} that "
            f"says why the type is unusable is not reported, so nothing reading the "
            f"dictionary - the listing, the dump, every backend - carries it either",
            ref.location("definition.typename"),
            notes=[("the type is unusable from here", cause.location)],
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
            ref,
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
        # Not routed through _refuse: schema cannot be overridden, so the second finding
        # _refuse writes when a cause is silenced would describe what cannot happen here.
        # Whether the drop is explained is still read off the call rather than assumed.
        self._dropped[ref.key] = (
            self._bag.add(
                "schema", _infinite_limits_message(datatype), ref.location("definition.conversion")
            )
            is not None
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
            previous = seen.get(original.name)
            if previous is not None:
                # Decided on the name alone, before resolution: a second copy of a name whose
                # first copy could not resolve is still a second copy.
                self._bag.add(
                    "duplicate-declaration",
                    f"component '{component.name}' declares '{original.name}' twice "
                    f"(as {previous.scope.value} and as {original.scope.value})",
                    original.location(),
                    notes=[("first declared here", previous.location())],
                )
                continue
            seen[original.name] = original
            ref = self._resolve_type(original)
            # The resolved form goes into the census when there is one: ownership is decided
            # over the census, and what the owning declaration says the object is has to be
            # the definition with the type it names filled in.
            self._census[original.name].append(original if ref is None else ref)
            if ref is None:
                # Its datatype names nothing this project declares, or a type that was
                # refused, and the finding sits there. The declaration is dropped - every
                # later check would be reasoning about a value with no storage - but what
                # needs neither storage nor shape still runs: the name it takes, and the
                # claims a consumer may not make.
                assert original.key in self._dropped
                self._check_declared_name(original)
                continue
            if not self._shape_resolves(ref):
                # A dimension names a constant nobody declares, which is now reported. The
                # declaration is dropped the way one naming an unknown type is - an array
                # of no known length is storage nothing downstream can reason about - but
                # every check that does not need the resolved shape still runs: an init
                # outside the datatype is wrong whatever the shape turns out to be, and
                # silencing unknown-constant must not silence that.
                self._check_declaration(ref)
                continue
            if not self._shape_fits(ref):
                # More elements, or more leaves, than anything downstream could carry. The
                # declaration is dropped for the same reason as above and the checks that do
                # not need the shape still run, which is also what keeps the refusal ahead of
                # every expansion: what an init says is read here, and never broadcast.
                self._check_declaration(ref)
                continue
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

        if not ref.scope.is_producer:
            # Reported where the claim is written rather than where it is overruled: the
            # producer may be in a file this author has never opened, and the fix is here.
            for key, check, what in _PRODUCER_KEYS:
                if getattr(definition, key) not in (None, {}):
                    self._bag.add(
                        check,
                        f"'{definition.name}': {what} is decided by the component that "
                        f"produces the variable, not by '{ref.component_name}', which reads it",
                        ref.location(f"definition.{key}"),
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

        if ref.resolved is not None:
            # The limits and the conversion were filled in from the scalar type this names,
            # and the type has already answered for both where it is declared - once, at the
            # file that would have to be edited. Repeating them here would report one mistake
            # once per component and point every copy at a key nobody wrote. What is the
            # declaration's own is its ``init``, checked above.
            return

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
        self._check_limits_fit(definition.limits, low, high, definition.storage, location)

    def _check_limits_fit(
        self, limits: Limits, low: float, high: float, datatype: Datatype, location: Location
    ) -> None:
        """Report limits the storage cannot hold, in one spelling wherever they are written.

        Three places write a datatype, a conversion and limits side by side - a declaration, a
        structure member and a scalar type - and the mistake is the same one in all three: the
        a2l carries a range the calibration tool offers and the storage cannot take. Shaped
        like :meth:`_check_enum_fits`, whose callers vary the bounds the same way.
        """
        if _below(limits.min, low) or _above(limits.max, high):
            self._bag.add(
                "limits-out-of-range",
                f"limits [{format_number(limits.min)}, {format_number(limits.max)}] exceed the "
                f"range [{format_number(low)}, {format_number(high)}] that "
                f"{datatype.value} can represent with this conversion",
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
        if conversion_identity(previous) != conversion_identity(conversion):
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
        """Determine the owning declaration and report every ownership violation.

        The owner is the first producer that resolved, not simply the first producer. The
        census carries dropped declarations, and the owner is the one the object is built
        from: taking the first in load order would let a dropped producer stand in for one
        beside it that resolved, :meth:`_absent` would read that owner as dropped, and the
        object would be left out whole. Whether it reaches the dictionary at all would then
        turn on which file the project lists first, which says nothing about either
        declaration. Only when every producer was dropped is the owner the first of them,
        and the name is absent - the true answer, because no declaration is left saying what
        the object is.

        The findings above are read over the whole census either way, dropped declarations
        included, and ``multiple-producers`` and ``local-conflict`` still name the first
        declaration in load order: they are about what the project declares, and which of
        those declarations the tool can then build from is a separate question.
        """
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

        owning = [ref for ref in producers if ref.key not in self._dropped] or producers
        return owning[0] if owning else None

    def _absent(
        self,
        ordered: list[tuple[str, list[DeclarationRef]]],
        owners: dict[str, DeclarationRef | None],
    ) -> dict[str, bool]:
        """The names that resolve to no object, each with whether a finding says why.

        Four ways in: every declaration of the name was dropped; the declaration that owns
        it was, in which case the consumers' copies describe storage nothing defines; a
        reference of its own names nothing, or names an object of the wrong kind; or,
        transitively, it refers to an absent name - a curve over a dropped axis cannot
        resolve its shape, and an axis whose ``input`` is a dropped measurement would leave a
        dangling name in the a2l. The finding for the root sits at the root cause, and a name
        that goes transitively is dropped without one of its own - ``unknown-reference``
        would claim that nobody declares the target, which is false. What every entry carries
        is whether that root finding was reported: an absence whose cause was silenced is the
        one this tool has to say out loud.

        Two phases, because a flag is only sound over the finished set. The set grows pass by
        pass, and a name met in an early pass can refer to one that goes only in a later one:
        a map over an axis dropped for a reported reason and an axis that goes because its
        ``input`` went silently reads as explained if it is judged while that second axis
        still looks present, and it is never judged again. So the first phase settles which
        names are absent and decides nothing else, and the second weighs every reference of
        each name once the set is whole. That second phase iterates as well, because the
        flags follow the references too - the map's answer needs the axis's, which needs the
        measurement's - and no order over the names walks every chain forwards.

        Fills ``_effective`` on the way, for exactly the names that have a definition to
        offer: the owner's, else the first surviving declaration's.
        """
        absent: dict[str, bool] = {}
        for name, refs in self._census.items():
            if name not in self._refs:
                # Not one declaration of it survived - a surviving one is in ``_refs`` - so the
                # drops are the whole story, and one explained drop explains the name.
                absent[name] = any(self._dropped[ref.key] for ref in refs)
        for name, refs in ordered:
            owner = owners[name]
            if owner is not None and owner.key in self._dropped:
                absent[name] = self._dropped[owner.key]
                continue
            self._effective[name] = (owner or refs[0]).definition

        # A reference nobody resolves drops the referrer, for the reason a dropped referent
        # does: a curve without its axis has no shape, and an axis naming an absent
        # measurement would leave a dangling name in the a2l. Decided here, over every name
        # with an effective definition - a name without one was already dropped, and
        # declared but dropped gets no second finding here - so that the drop propagates
        # like any other, and every reference of a name is weighed rather than only the
        # first bad one, because two unknown axes are two mistakes to fix. What the name
        # keeps is whether any of its refusals was reported.
        own: dict[str, bool] = {}
        for name, refs in ordered:
            definition = self._effective.get(name)
            if definition is None:
                continue  # dropped: it is a seed above, with the flag its drop gave it
            reference = owners[name] or refs[0]
            for key, target in definition.references.items():
                refused = self._refuse_reference(definition, key, target, reference)
                if refused is not None:
                    absent[name] = own[name] = own.get(name, False) or refused
                else:
                    # ``reference`` is the owner when there is one, else the first surviving
                    # declaration - a referrer with no producer of its own is judged by
                    # whichever component declared it first.
                    self._check_local_reference(definition, key, target, reference)

        # The seeds above carry their own flag, decided by what was dropped or refused. What
        # follows settles the names that go transitively: one reference to an absent name is
        # enough, and the flag each is entered with - explained, until the second phase says
        # otherwise - is never read here, only the membership is.
        transitive: list[str] = []
        settled = False
        while not settled:
            settled = True
            for name, definition in self._effective.items():
                if name in absent:
                    continue
                if any(target in absent for target in definition.references.values()):
                    absent[name] = True
                    transitive.append(name)
                    settled = False
        # Both absences the references decide are weighed here: a name that went with a target
        # of its own, and one whose own reference was refused. A map with a reported x_axis
        # and a y_axis that went silently is absent twice over, and half explained is not
        # explained, so the two answers have to meet.
        weighed = sorted({*transitive, *own})
        settled = False
        while not settled:
            settled = True
            for name in weighed:
                gone = [
                    (key, target)
                    for key, target in self._effective[name].references.items()
                    if target in absent
                ]
                # Kept for the report: which of the names this definition refers to took it
                # down, so the absence can be said at the key that names it. The silenced one,
                # because that is the absence nothing else mentions - unless a refusal of its
                # own was silenced, which is already in ``_via`` and outranks these: an absent
                # target at least leaves a declaration to look at, where a refused reference
                # leaves nothing but the check nobody reported.
                silenced = next(((key, target) for key, target in gone if not absent[target]), None)
                if silenced is not None and name not in self._dangling:
                    self._via[name] = silenced
                # Every absent target weighed, not the first one met: a map over two absent
                # axes is explained only if both of them were, or the key order of a
                # definition would decide whether the map's own absence is ever said. A
                # name's own refusals fold with any, because a reported refusal names the
                # object itself, so it is never silently absent, while a half-explained
                # absence through other objects is not explained.
                explained = own.get(name, True) and all(absent[target] for _, target in gone)
                if explained != absent[name]:
                    absent[name] = explained
                    settled = False
        return absent

    def _refuse_reference(
        self, definition: DataObject, key: str, target: str, reference: DeclarationRef
    ) -> bool | None:
        """Refuse a reference that names no object, or one of the wrong kind.

        ``None`` when there is nothing to say: the target is there and is what the key
        requires, or some component does declare it and it was dropped - the fixpoint takes
        the referrer with it, and ``unknown-reference`` would claim that nobody declares the
        target, which is false. Otherwise the finding is written where the name is, and what
        comes back is whether the bag reported it. A silenced refusal is the one the absence
        report has to say out loud, so the reference and the check are kept for it - the
        first silenced one, because a name is absent once however many of its references are
        wrong, while each of those references is a mistake of its own and is reported.
        """
        found = self._effective.get(target)
        if found is None:
            if target in self._census:
                return None
            check = "unknown-reference"
            message = (
                f"{definition.kind.value} '{definition.name}' refers to '{target}' as its "
                f"{key}, but no component declares '{target}'"
            )
        elif found.kind is not _EXPECTED_KIND[key]:
            check = "reference-kind"
            message = (
                f"the {key} of {definition.kind.value} '{definition.name}' must be of kind "
                f"'{_EXPECTED_KIND[key].value}', but '{target}' is of kind '{found.kind.value}'"
            )
        else:
            return None
        location = reference.location(f"definition.{key}")
        reported = self._bag.add(check, message, location) is not None
        if not reported:
            self._via.setdefault(definition.name, (key, target))
            self._dangling.setdefault(definition.name, check)
        return reported

    def _check_local_reference(
        self,
        definition: DataObject,
        key: str,
        target: str,
        reference: DeclarationRef,
    ) -> None:
        """A reference into another component's local object is a use, and is refused as one.

        Section 2.1 promises that a local object is used by nobody else; comparing
        declarations alone kept that promise only for declarations. A curve of one component
        bound to an axis another declared local compiles, links and reaches the a2l bound to
        that private axis, which is exactly the coupling the scope forbids. Reported where the
        reference is written, with a note at the local declaration, and nothing is dropped:
        as between two declarations, the finding is the ownership violation, not a missing
        object. The local declaration is read from the census, in load order, the way the
        declaration-form finding reads it, so that which file the project lists first cannot
        decide whether the reference is reported.
        """
        locals_ = [ref for ref in self._census.get(target, []) if ref.scope is Scope.LOCAL]
        if not locals_:
            return
        if locals_[0].component_name == reference.component_name:
            return
        self._bag.add(
            "local-conflict",
            f"'{target}' is local to component '{locals_[0].component_name}' but is also used "
            f"as the {key} of '{definition.name}' by component '{reference.component_name}'",
            reference.location(f"definition.{key}"),
            notes=[("declared local here", locals_[0].location())],
        )

    def _report_absences(
        self, absent: dict[str, bool], owners: dict[str, DeclarationRef | None]
    ) -> None:
        """One ``incomplete-project`` per declaration the dictionary omits for a silenced cause.

        The root of each absence already said so where it was dropped, if anything said so at
        all. What nothing said yet is the rest: a curve over an axis that went, the consumers
        of an object whose producer went. Each surviving declaration of such a name is named,
        at the reference that pulled the object down where there is one, at the declaration
        otherwise, so that no declaration leaves the dictionary in silence. A name that went
        with its producer carries a note at that producing declaration: the finding sits in a
        file whose author wrote nothing wrong, and the file to look at is the other one.

        Only the declarations that survived: a dropped one is not in ``_refs``, and its own
        finding was written where it was dropped, so reading the census here would report it
        a second time.
        """
        for name in sorted(absent):
            if absent[name]:
                continue
            refs = self._refs.get(name, [])
            owner = owners[name]
            # By identity, not by equality: two declarations of one name can carry the same
            # fields, and the reference that pulled the object down belongs to the owning
            # declaration alone.
            first = next((ref for ref in refs if ref is owner), refs[0] if refs else None)
            via = self._via.get(name)
            dangling = self._dangling.get(name)
            # Where the object went, when it went with its producer: this declaration is
            # sound, and the file to look at is the one that owns the object.
            notes = (
                [("the declaration that produces it did not resolve", owner.location())]
                if owner is not None and owner.key in self._dropped
                else []
            )
            for ref in refs:
                if ref is first and via is not None:
                    key, target = via
                    # Two absences with two different things to do about them: a target that
                    # was declared and dropped leaves a declaration to look at, while one
                    # this reference cannot resolve at all leaves only the silenced check.
                    cause = (
                        f"does not resolve, and the {dangling} that says why is not reported"
                        if dangling is not None
                        else "did not resolve, and the finding that says why is not reported"
                    )
                    self._bag.add(
                        "incomplete-project",
                        f"'{name}' is not in the data dictionary: its {key} '{target}' {cause}",
                        ref.location(f"definition.{key}"),
                    )
                else:
                    self._bag.add(
                        "incomplete-project",
                        f"'{name}' is declared by component '{ref.component_name}' but is not "
                        f"in the data dictionary: it did not resolve, and the finding that "
                        f"says why is not reported",
                        ref.location("definition"),
                        notes=notes,
                    )

    def _resolve_shape(self, definition: DataObject) -> tuple[Shape, WrittenShape]:
        """The storage shape of an object, as numbers and as the project spells it.

        For a curve or map both follow from its axes, the spelling included: the axis is
        where that dimension is written down, so an axis sized by a constant carries the
        constant's name into every curve and map interpolated over it. Every named
        dimension resolves here, because a declaration or type whose shape does not was
        dropped before ownership was settled, and so is every axis: one that nobody
        declares, or that is not an axis, was refused in :meth:`_absent` and took the object
        being shaped here with it.
        """
        if isinstance(definition, Curve):
            axis = self._effective[definition.axis]
            assert isinstance(axis, Axis)
            return ((self._dimension_value(axis.size),), (axis.size,))

        if isinstance(definition, Map):
            x_axis = self._effective[definition.x_axis]
            y_axis = self._effective[definition.y_axis]
            assert isinstance(x_axis, Axis)
            assert isinstance(y_axis, Axis)
            # A map is stored row wise: the x index runs fastest, so it is the last one.
            return (
                (self._dimension_value(y_axis.size), self._dimension_value(x_axis.size)),
                (y_axis.size, x_axis.size),
            )

        shape = definition.declared_shape
        # Only a curve or a map defers to its axes, and both returned above.
        assert shape is not None
        return (self._numeric_shape(shape), shape)

    def _consumers(self, name: str) -> list[DeclarationRef]:
        """Who reads the object, over the census: a reader that was dropped still reads it."""
        return [ref for ref in self._census.get(name, []) if ref.scope is Scope.INPUT]

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

        # The surviving declarations, where the census answers the finding below: the
        # dictionary lists the readers it carries, and a dropped one is not among them.
        consumers = [ref for ref in refs if ref.scope is Scope.INPUT]
        self._check_unused(name, producer, self._consumers(name))

        named = definition.declared_type
        assert named is not None
        structure = self._types[named].declared
        assert isinstance(structure, StructType)

        spelled = definition.declared_shape or ()
        instance = ResolvedInstance(
            name=name,
            id=definition.id,
            extensions=resolve_blocks(self._plugins, definition.extensions, on_project=False),
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
                        instance_id=instance.id,
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
        *,
        reaches_a2l: bool,
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

        self._check_unused(name, producer, self._consumers(name))

        # Asked of the a2l's own closure rather than of this object's export: an object kept
        # out of the file is still in it when an exported curve or axis refers to it, and it
        # is then still too many dimensions for a MATRIX_DIM.
        if len(shape) > _A2L_MAX_DIMENSIONS and reaches_a2l:
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
            extensions=resolve_blocks(self._plugins, definition.extensions, on_project=False),
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

        Only ever asked of an object that resolved, so the shape from the axes is a real
        shape: a curve whose axis nobody declares is not here to be asked.
        """
        init = ref.definition.init
        if not isinstance(init, tuple):
            # A scalar init fills every element of whatever the shape is; nothing to check.
            return
        declared = ref.definition.declared_shape
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


_PRODUCER_KEYS: Final = (
    ("init", "consumer-storage", "the initial value"),
    ("section", "consumer-storage", "the memory section"),
    ("raster", "consumer-raster", "the measurement raster"),
    ("id", "consumer-identity", "the identity"),
    ("extensions", "consumer-extension", "what a plugin knows about the variable"),
)
"""The keys only a producing declaration may state, with the check a consumer stating one
earns and how the finding names the key. One rule, five keys: what an object starts as,
where it lives, which event updates it, which earlier delivery it continues, and what a
plugin knows about it are all decided by the component that produces it."""


def _member_raw_range(member: Member) -> tuple[float, float]:
    """The raw values a member's storage holds: its bitfield's, or its datatype's."""
    assert member.datatype is not None
    if member.bits is not None:
        return bitfield_range(member.datatype, member.bits)
    return (member.datatype.raw_min, member.datatype.raw_max)


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
