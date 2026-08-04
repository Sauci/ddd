"""Resolving the data objects of a workspace and checking the interfaces for consistency.

This is the front end: it turns what the loader read into a :class:`~ddd.ir.DataDictionary`
and reports every disagreement on the way. It knows nothing about c or about a2l - the only
thing it hands to the backends is the dictionary.
"""

from __future__ import annotations

import dataclasses
import math
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass

from ddd.diagnostics import DiagnosticBag, Location
from ddd.ir import ComponentDeclaration, DataDictionary, ResolvedComponent, ResolvedObject
from ddd.loading import LoadedComponent, LoadedType, Workspace
from ddd.models import (
    Axis,
    Curve,
    DataObject,
    Datatype,
    Declaration,
    EnumConversion,
    Map,
    ObjectKind,
    Scope,
    Shape,
    check_shape,
    conversion_range,
    format_number,
    format_shape,
    is_reserved_identifier,
    resolve_export,
)
from ddd.naming import check_names

_A2L_MAX_DIMENSIONS = 3
"""Dimensions ``MATRIX_DIM`` can carry in the a2l version DDD writes (ASAP2 1.6.1)."""

_INT_MIN, _INT_MAX = -(2**31), 2**31 - 1
"""Range of a c ``int`` on the 32 bit targets DDD generates for; bounds every enumerator."""


@dataclass(frozen=True, slots=True)
class _ComparedField:
    """One property two declarations of the same object are compared on.

    ``value`` is what has to match, ``describe`` is how the finding phrases it. Keeping the
    two together is the point: a field cannot be compared without being explainable, and
    adding one is a single entry instead of an edit in three places.
    """

    name: str
    value: Callable[[DataObject], object]
    describe: Callable[[DataObject], str]
    optional: bool = False
    """When set, a declaration that omits the property agrees with whatever the other says.

    Used for properties that have a derived default: a consumer that simply does not repeat
    the producer's limits is not disagreeing with them.
    """


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


def _a2l_presentation(definition: DataObject) -> dict[str, str | None]:
    """The a2l options only the producer decides.

    ``export`` is not among them: any component may ask for an object to reach the a2l, so
    two declarations differing about it are not disagreeing - see
    :func:`~ddd.models.objects.resolve_export`. How the object is *displayed* has no such
    answer, since two format strings cannot both be used.
    """
    a2l = definition.a2l
    return {"format": a2l.format, "display_identifier": a2l.display_identifier}


def _describe_a2l(definition: DataObject) -> str:
    stated = [f"{key}='{value}'" for key, value in _a2l_presentation(definition).items() if value]
    return ", ".join(stated) or "unset"


def _conversion_value(definition: DataObject) -> object:
    """What two declarations of one object have to agree on in their conversion.

    An enumerator's ``description`` is documentation, not interface: the two spellings the
    file format offers (the mapping shorthand and the list of objects) cannot even carry the
    same information. ``enum-conflict`` owns the agreement of the enumerators themselves and
    deliberately ignores descriptions, so comparing the raw dump here would report a
    mismatch that check does not see, on declarations that generate identical code.
    """
    conversion = definition.conversion
    if isinstance(conversion, EnumConversion):
        return ("enum", conversion.name, _enum_key(conversion))
    return conversion.model_dump(mode="json")


# What every component sharing an object has to agree on: a disagreement is an error.
_INTERFACE_FIELDS = (
    _ComparedField("kind", lambda d: d.kind.value, lambda d: d.kind.value),
    _ComparedField("datatype", lambda d: d.datatype.value, lambda d: d.datatype.value),
    _ComparedField("unit", lambda d: d.unit, lambda d: f"'{d.unit}'"),
    _ComparedField("shape", lambda d: d.declared_shape, _describe_shape),
    _ComparedField("conversion", _conversion_value, lambda d: d.conversion.describe()),
    _ComparedField(
        "limits",
        lambda d: d.limits.as_tuple() if d.limits is not None else None,
        _describe_limits,
        optional=True,
    ),
    _ComparedField("references", lambda d: d.references, _describe_references),
    # Not optional, unlike limits, and it cannot be: the key is required on every definition,
    # so there is no silence to interpret. Every component that reads the object gets the
    # qualifier in its own header, which means every description of it has to agree.
    _ComparedField("volatile", lambda d: d.volatile, lambda d: str(d.volatile).lower()),
)

# What only shapes the generated a2l entry: the producer wins, the others get a warning that
# says so. One field is left, and the two that used to sit here left for opposite reasons.
#
# ``init`` is a claim over somebody else's storage rather than a losing opinion, so stating one
# in a consumer is refused outright as ``consumer-storage``. ``volatile`` went the other way:
# it reaches every consumer's header as a type qualifier and tells their code whether the value
# can change under it, which makes it interface, and a disagreement an error.
#
# What is left of the a2l block is presentation - a format string, a display name - where two
# values genuinely cannot both be used and there is no reason to stop a build over it.
_STORAGE_FIELDS = (_ComparedField("a2l", _a2l_presentation, _describe_a2l),)


def _differing(
    fields: tuple[_ComparedField, ...], reference: DataObject, other: DataObject
) -> list[_ComparedField]:
    differing = []
    for field in fields:
        mine, theirs = field.value(reference), field.value(other)
        if field.optional and (mine is None or theirs is None):
            continue
        if mine != theirs:
            differing.append(field)
    return differing


def _spell_out(fields: list[_ComparedField], reference: DataObject, other: DataObject) -> str:
    return ", ".join(
        f"{field.name}: {field.describe(other)} != {field.describe(reference)}" for field in fields
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

    @property
    def component_name(self) -> str:
        return self.owner.name

    @property
    def scope(self) -> Scope:
        return self.declaration.scope

    @property
    def definition(self) -> DataObject:
        return self.declaration.definition

    @property
    def name(self) -> str:
        return self.declaration.definition.name

    @property
    def condition(self) -> str | None:
        return self.declaration.condition

    def location(self, suffix: str = "") -> Location:
        return self.owner.declaration_location(self.index, suffix)


@dataclass(frozen=True, slots=True)
class Variable:
    """A resolved data object: one storage location plus all its users."""

    name: str
    definition: DataObject
    """The effective definition, taken from the producing component."""

    shape: Shape
    """The resolved array shape; for a curve or map it comes from the axes."""

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
            limits=definition.physical_limits(),
            shape=self.shape,
            init=definition.init,
            volatile=definition.volatile,
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
            # An undeclared structure has no members to follow; it is reported as unknown-type.
            return ()
        chain.append(name)
        for member in entry.structure.members:
            nested = member.type
            if nested is None:
                continue
            found = walk(nested)
            if found:
                return found
        chain.pop()
        return ()

    return walk(start)


def _resolve_component(loaded: LoadedComponent) -> ResolvedComponent:
    """The component and its interface, in the order the author wrote it."""
    seen: set[str] = set()
    declarations = []
    for declaration in loaded.component.declarations:
        name = declaration.definition.name
        if name in seen:  # a duplicate declaration is reported and then ignored
            continue
        seen.add(name)
        declarations.append(
            ComponentDeclaration(
                name=name, scope=declaration.scope, condition=declaration.condition
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
        self._refs: dict[str, list[DeclarationRef]] = defaultdict(list)
        self._effective: dict[str, DataObject] = {}
        """The definition that counts for each name: the producer's, once known."""

    def run(self) -> DataDictionary:
        workspace = self._workspace
        self._check_types()
        self._check_component_names()
        for loaded in workspace.components:
            self._collect_component(loaded)

        ordered = sorted(self._refs.items())
        self._check_enumerator_collisions(ordered)

        # The producer owns the definition, so ownership has to be settled before anything
        # that reads a definition - in particular before curves and maps look up their axes.
        owners = {name: self._select_producer(name, refs) for name, refs in ordered}
        self._effective = {name: (owners[name] or refs[0]).definition for name, refs in ordered}
        shapes = {
            name: self._resolve_shape(self._effective[name], owners[name] or refs[0])
            for name, refs in ordered
        }

        variables = [
            self._build_variable(name, refs, owners[name], self._effective[name], shapes[name])
            for name, refs in ordered
        ]
        self._check_similar_names(variables)
        if workspace.naming is not None:
            # Only the names of data objects: a component name lives in another namespace and a
            # convention written for variables would reject every one of them.
            check_names(
                {name: refs[0].location("definition.name") for name, refs in ordered},
                workspace.naming,
                self._bag,
            )

        known = self._enums.by_name
        return DataDictionary(
            name=workspace.name,
            description=workspace.description,
            source=workspace.root.name,
            components=tuple(_resolve_component(loaded) for loaded in workspace.components),
            objects=tuple(variable.resolve() for variable in variables),
            enums=tuple(enum for enum, _ in (known[key] for key in sorted(known))),
        )

    def _check_types(self) -> None:
        """Every nested structure is declared, and no structure contains itself.

        Both are refused rather than resolved as far as possible. A member whose structure is
        unknown has no size, so every offset after it in the enclosing structure would be wrong
        and the generated addresses would silently point at the wrong bytes; a structure that
        contains itself has no size at all.
        """
        declared = {entry.name: entry for entry in self._workspace.types}
        for entry in self._workspace.types:
            for index, member in enumerate(entry.structure.members):
                nested = member.type
                if nested is None:
                    continue
                if nested not in declared:
                    self._bag.add(
                        "unknown-type",
                        f"member '{member.name}' nests structured datatype '{nested}', which no "
                        f"file of this project declares",
                        entry.location(f"members[{index}]"),
                    )

        # Keyed on the participants of the cycle rather than on the structure the walk started
        # from. Those differ: a sound structure nesting a recursive one reaches the same cycle,
        # and keying on the start would report it once per route into it.
        reported: set[frozenset[str]] = set()
        for entry in self._workspace.types:
            cycle = _nesting_cycle(entry.name, declared)
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

    def _collect_component(self, loaded: LoadedComponent) -> None:
        component = loaded.component
        if is_reserved_identifier(component.name):
            self._bag.add(
                "reserved-identifier",
                f"component name '{component.name}' is reserved by the c language",
                loaded.location("component.name"),
            )
        if not component.declarations:
            self._bag.add(
                "empty-component",
                f"component '{component.name}' declares no variable",
                loaded.location(),
            )

        seen: dict[str, DeclarationRef] = {}
        for index, declaration in enumerate(component.declarations):
            ref = DeclarationRef(loaded, index, declaration)
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

    def _check_declaration(self, ref: DeclarationRef) -> None:
        definition = ref.definition
        location = ref.location("definition")

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

        self._check_init(definition, ref.location("definition.init"))
        self._check_limits(definition, ref.location("definition.limits"))

        conversion = definition.conversion
        if isinstance(conversion, EnumConversion):
            self._register_enum(conversion, ref.location("definition.conversion"))
            self._check_enum_fits(definition, conversion, location)

    def _check_init(self, definition: DataObject, location: Location) -> None:
        datatype = definition.datatype
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
        low, high = conversion_range(definition.conversion, definition.datatype)
        limits = definition.limits
        if _below(limits.min, low) or _above(limits.max, high):
            self._bag.add(
                "limits-out-of-range",
                f"limits [{format_number(limits.min)}, {format_number(limits.max)}] exceed the "
                f"range [{format_number(low)}, {format_number(high)}] that "
                f"{definition.datatype.value} can represent with this conversion",
                location,
            )

    def _register_enum(self, conversion: EnumConversion, location: Location) -> None:
        known = self._enums.by_name.get(conversion.name)
        if known is None:
            self._enums.by_name[conversion.name] = (conversion, location)
            self._check_enum_names(conversion, location)
            self._check_enum_values(conversion, location)
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

    def _check_enum_values(self, conversion: EnumConversion, location: Location) -> None:
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
        # extension, so it is caught here rather than in the customer's build.
        outside = [
            enumerator
            for enumerator in conversion.enumerators
            if not (_INT_MIN <= enumerator.value <= _INT_MAX)
        ]
        if outside:
            spelled = ", ".join(f"{e.name}={e.value}" for e in outside)
            self._bag.add(
                "init-invalid",
                f"enumerator(s) {spelled} of enum '{conversion.name}' do not fit into a c "
                f"'int', which every enumerator has to",
                location,
            )

    def _check_enum_fits(
        self, definition: DataObject, conversion: EnumConversion, location: Location
    ) -> None:
        datatype = definition.datatype
        outside = [
            enumerator
            for enumerator in conversion.enumerators
            if not (datatype.raw_min <= enumerator.value <= datatype.raw_max)
        ]
        if outside:
            names = ", ".join(f"{e.name}={e.value}" for e in outside)
            self._bag.add(
                "init-invalid",
                f"enumerator(s) {names} of enum '{conversion.name}' do not fit into "
                f"{datatype.value}",
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

    def _resolve_shape(self, definition: DataObject, reference: DeclarationRef) -> Shape:
        """The storage shape of an object; for a curve or map it follows from its axes."""
        if isinstance(definition, Axis) and definition.input is not None:
            self._lookup(definition.input, ObjectKind.MEASUREMENT, "input", definition, reference)

        if isinstance(definition, Curve):
            axis = self._lookup(definition.axis, ObjectKind.AXIS, "axis", definition, reference)
            return (axis.size,) if isinstance(axis, Axis) else ()

        if isinstance(definition, Map):
            x_axis = self._lookup(
                definition.x_axis, ObjectKind.AXIS, "x_axis", definition, reference
            )
            y_axis = self._lookup(
                definition.y_axis, ObjectKind.AXIS, "y_axis", definition, reference
            )
            if isinstance(x_axis, Axis) and isinstance(y_axis, Axis):
                # A map is stored row wise: the x index runs fastest, so it is the last one.
                return (y_axis.size, x_axis.size)
            return ()

        shape = definition.declared_shape
        return shape if shape is not None else ()

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

    def _build_variable(
        self,
        name: str,
        refs: list[DeclarationRef],
        producer: DeclarationRef | None,
        definition: DataObject,
        shape: Shape,
    ) -> Variable:
        reference = producer or refs[0]

        for ref in refs:
            if ref.definition.declared_shape is None:
                self._check_init_shape(ref, shape)
            if ref is not reference:
                self._compare(reference, ref)

        consumers = [ref for ref in refs if ref.scope is Scope.INPUT]
        if producer is not None and producer.scope is Scope.OUTPUT and not consumers:
            self._bag.add(
                "unused-output",
                f"'{name}' is written by component '{producer.component_name}' but read by nobody",
                producer.location(),
            )

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
            producer=producer,
            declarations=tuple(refs),
            condition=reference.condition,
        )

    def _check_init_shape(self, ref: DeclarationRef, shape: Shape) -> None:
        """Init shape of a curve or map, which is only known once the axes are resolved."""
        init = ref.definition.init
        if not isinstance(init, tuple) or not shape:
            return
        problem = check_shape(init, shape)
        if problem is not None:
            self._bag.add(
                "init-invalid",
                f"'{ref.name}' has the shape {format_shape(shape)} given by its axes: {problem}",
                ref.location("definition.init"),
            )

    def _compare(self, reference: DeclarationRef, other: DeclarationRef) -> None:
        """Compare two declarations of the same data object."""
        note = [("reference declaration", reference.location("definition"))]

        interface = _differing(_INTERFACE_FIELDS, reference.definition, other.definition)
        if interface:
            self._bag.add(
                "definition-mismatch",
                f"'{other.name}' is declared differently by component '{other.component_name}' "
                f"than by '{reference.component_name}' "
                f"({_spell_out(interface, reference.definition, other.definition)})",
                other.location("definition"),
                notes=note,
            )

        storage = _differing(_STORAGE_FIELDS, reference.definition, other.definition)
        if storage:
            named = " and ".join(field.name for field in storage)
            self._bag.add(
                "storage-mismatch",
                f"'{other.name}': component '{other.component_name}' specifies a different "
                f"{named} than '{reference.component_name}' "
                f"({_spell_out(storage, reference.definition, other.definition)}); "
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

    def _check_similar_names(self, variables: list[Variable]) -> None:
        groups: dict[str, list[str]] = defaultdict(list)
        for variable in variables:
            groups[variable.name.lower()].append(variable.name)
        by_name = {variable.name: variable for variable in variables}
        for names in groups.values():
            if len(names) < 2:
                continue
            first, *rest = names
            for name in rest:
                variable = by_name[name]
                self._bag.add(
                    "name-similar",
                    f"'{name}' and '{first}' differ only in upper/lower case",
                    variable.declarations[0].location("definition.name"),
                    notes=[
                        ("other variable", by_name[first].declarations[0].location("definition"))
                    ],
                )


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


def _below(value: float, limit: float) -> bool:
    return value < limit and not math.isclose(value, limit, rel_tol=1e-9, abs_tol=0.0)


def _above(value: float, limit: float) -> bool:
    return value > limit and not math.isclose(value, limit, rel_tol=1e-9, abs_tol=0.0)
