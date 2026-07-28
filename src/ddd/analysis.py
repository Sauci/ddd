"""Resolving the data objects of a workspace and checking the interfaces for consistency.

This is the front end: it turns what the loader read into a :class:`~ddd.ir.DataDictionary`
and reports every disagreement on the way. It knows nothing about c or about a2l - the only
thing it hands to the backends is the dictionary.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass

from ddd.diagnostics import DiagnosticBag, Location
from ddd.ir import ComponentDeclaration, DataDictionary, ResolvedComponent, ResolvedObject
from ddd.loading import LoadedComponent, Workspace
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
)
from ddd.naming import check_names


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


# What every component sharing an object has to agree on: a disagreement is an error.
_INTERFACE_FIELDS = (
    _ComparedField("kind", lambda d: d.kind.value, lambda d: d.kind.value),
    _ComparedField("datatype", lambda d: d.datatype.value, lambda d: d.datatype.value),
    _ComparedField("unit", lambda d: d.unit, lambda d: f"'{d.unit}'"),
    _ComparedField("shape", lambda d: d.declared_shape, _describe_shape),
    _ComparedField(
        "conversion",
        lambda d: d.conversion.model_dump(mode="json"),
        lambda d: d.conversion.describe(),
    ),
    _ComparedField("limits", lambda d: d.physical_limits().as_tuple(), _describe_limits),
    _ComparedField("references", lambda d: d.references, _describe_references),
)

# What only shapes the generated storage: the producer wins, the others get a warning.
_STORAGE_FIELDS = (
    _ComparedField("init", lambda d: d.init, lambda d: "none" if d.init is None else repr(d.init)),
    _ComparedField("volatile", lambda d: d.volatile, lambda d: str(d.volatile).lower()),
)


def _differing(
    fields: tuple[_ComparedField, ...], reference: DataObject, other: DataObject
) -> list[_ComparedField]:
    return [field for field in fields if field.value(reference) != field.value(other)]


def _spell_out(fields: list[_ComparedField], reference: DataObject, other: DataObject) -> str:
    return ", ".join(
        f"{field.name}: {field.describe(other)} != {field.describe(reference)}" for field in fields
    )


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
            a2l=definition.a2l,
        )


def analyze(workspace: Workspace, bag: DiagnosticBag) -> DataDictionary:
    """Run every consistency check and resolve the data objects of the project."""
    refs_by_name: dict[str, list[DeclarationRef]] = defaultdict(list)
    enums: dict[str, tuple[EnumConversion, Location]] = {}

    for loaded in workspace.components:
        _collect_component(loaded, bag, refs_by_name, enums)

    ordered = sorted(refs_by_name.items())

    # The producer owns the definition, so ownership has to be settled before anything
    # that reads a definition - in particular before curves and maps look up their axes.
    owners = {name: _select_producer(name, refs, bag) for name, refs in ordered}
    effective = {name: (owners[name] or refs[0]).definition for name, refs in ordered}
    shapes = {
        name: _resolve_shape(effective[name], effective, owners[name] or refs[0], bag)
        for name, refs in ordered
    }

    variables = [
        _build_variable(name, refs, owners[name], effective[name], shapes[name], bag)
        for name, refs in ordered
    ]
    _check_similar_names(variables, bag)
    if workspace.naming is not None:
        # Only the names of data objects: a component name lives in another namespace and a
        # convention written for variables would reject every one of them.
        check_names(
            {name: refs[0].location("definition.name") for name, refs in ordered},
            workspace.naming,
            bag,
        )

    return DataDictionary(
        name=workspace.name,
        description=workspace.description,
        source=workspace.root.name,
        components=tuple(_resolve_component(loaded) for loaded in workspace.components),
        objects=tuple(variable.resolve() for variable in variables),
        enums=tuple(enum for enum, _ in (enums[key] for key in sorted(enums))),
    )


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


# -- per component checks ---------------------------------------------------


def _collect_component(
    loaded: LoadedComponent,
    bag: DiagnosticBag,
    refs_by_name: dict[str, list[DeclarationRef]],
    enums: dict[str, tuple[EnumConversion, Location]],
) -> None:
    component = loaded.component
    if is_reserved_identifier(component.name):
        bag.add(
            "reserved-identifier",
            f"component name '{component.name}' is reserved by the c language",
            loaded.location("component.name"),
        )
    if not component.declarations:
        bag.add(
            "empty-component",
            f"component '{component.name}' declares no variable",
            loaded.location(),
        )

    seen: dict[str, DeclarationRef] = {}
    for index, declaration in enumerate(component.declarations):
        ref = DeclarationRef(loaded, index, declaration)
        previous = seen.get(ref.name)
        if previous is not None:
            bag.add(
                "duplicate-declaration",
                f"component '{component.name}' declares '{ref.name}' twice "
                f"(as {previous.scope.value} and as {ref.scope.value})",
                ref.location(),
                notes=[("first declared here", previous.location())],
            )
            continue
        seen[ref.name] = ref
        refs_by_name[ref.name].append(ref)

        _check_declaration(ref, bag, enums)


def _check_declaration(
    ref: DeclarationRef,
    bag: DiagnosticBag,
    enums: dict[str, tuple[EnumConversion, Location]],
) -> None:
    definition = ref.definition
    location = ref.location("definition")

    if is_reserved_identifier(definition.name):
        bag.add(
            "reserved-identifier",
            f"variable name '{definition.name}' is reserved by the c language",
            ref.location("definition.name"),
        )

    _check_init(definition, ref.location("definition.init"), bag)
    _check_limits(definition, ref.location("definition.limits"), bag)

    conversion = definition.conversion
    if isinstance(conversion, EnumConversion):
        _register_enum(conversion, ref.location("definition.conversion"), bag, enums)
        _check_enum_fits(definition, conversion, location, bag)


def _check_init(definition: DataObject, location: Location, bag: DiagnosticBag) -> None:
    datatype = definition.datatype
    for value in definition.scalar_values():
        if datatype is Datatype.BOOL:
            if not isinstance(value, bool) and value not in (0, 1):
                bag.add(
                    "init-invalid",
                    f"init value {format_number(value)} is not a valid bool",
                    location,
                )
            continue
        if datatype.is_integer and isinstance(value, float):
            bag.add(
                "init-invalid",
                f"init value {format_number(value)} is not an integer, "
                f"but '{definition.name}' has datatype {datatype.value}",
                location,
            )
            continue
        if not (datatype.raw_min <= value <= datatype.raw_max):
            bag.add(
                "init-invalid",
                f"init value {format_number(value)} does not fit into {datatype.value} "
                f"({format_number(datatype.raw_min)} .. {format_number(datatype.raw_max)})",
                location,
            )


def _check_limits(definition: DataObject, location: Location, bag: DiagnosticBag) -> None:
    if definition.limits is None:
        return
    low, high = conversion_range(definition.conversion, definition.datatype)
    limits = definition.limits
    if _below(limits.min, low) or _above(limits.max, high):
        bag.add(
            "limits-out-of-range",
            f"limits [{format_number(limits.min)}, {format_number(limits.max)}] exceed the "
            f"range [{format_number(low)}, {format_number(high)}] that {definition.datatype.value}"
            f" can represent with this conversion",
            location,
        )


def _register_enum(
    conversion: EnumConversion,
    location: Location,
    bag: DiagnosticBag,
    enums: dict[str, tuple[EnumConversion, Location]],
) -> None:
    known = enums.get(conversion.name)
    if known is None:
        enums[conversion.name] = (conversion, location)
        _check_enum_values(conversion, location, bag)
        return
    previous, previous_location = known
    if _enum_key(previous) != _enum_key(conversion):
        bag.add(
            "enum-conflict",
            f"enum '{conversion.name}' is defined with different enumerators",
            location,
            notes=[
                (f"here: {_enum_summary(conversion)}", None),
                (f"first defined as: {_enum_summary(previous)}", previous_location),
            ],
        )


def _check_enum_values(conversion: EnumConversion, location: Location, bag: DiagnosticBag) -> None:
    by_value: dict[int, list[str]] = defaultdict(list)
    for enumerator in conversion.enumerators:
        by_value[enumerator.value].append(enumerator.name)
    for value, names in sorted(by_value.items()):
        if len(names) > 1:
            bag.add(
                "enum-duplicate-value",
                f"enum '{conversion.name}': {', '.join(names)} all have the value {value}",
                location,
            )


def _check_enum_fits(
    definition: DataObject,
    conversion: EnumConversion,
    location: Location,
    bag: DiagnosticBag,
) -> None:
    datatype = definition.datatype
    outside = [
        enumerator
        for enumerator in conversion.enumerators
        if not (datatype.raw_min <= enumerator.value <= datatype.raw_max)
    ]
    if outside:
        names = ", ".join(f"{e.name}={e.value}" for e in outside)
        bag.add(
            "init-invalid",
            f"enumerator(s) {names} of enum '{conversion.name}' do not fit into {datatype.value}",
            location,
        )


# -- ownership --------------------------------------------------------------


def _select_producer(
    name: str, refs: list[DeclarationRef], bag: DiagnosticBag
) -> DeclarationRef | None:
    """Determine the owning declaration and report every ownership violation."""
    producers = [ref for ref in refs if ref.scope.is_producer]
    locals_ = [ref for ref in refs if ref.scope is Scope.LOCAL]
    consumers = [ref for ref in refs if ref.scope is Scope.INPUT]

    if locals_ and len(refs) > 1:
        for other in refs:
            if other is locals_[0]:
                continue
            bag.add(
                "local-conflict",
                f"'{name}' is local to component '{locals_[0].component_name}' but is also "
                f"declared as {other.scope.value} by component '{other.component_name}'",
                other.location(),
                notes=[("declared local here", locals_[0].location())],
            )
    elif len(producers) > 1:
        first, *rest = producers
        for other in rest:
            bag.add(
                "multiple-producers",
                f"'{name}' is written by component '{other.component_name}' and by "
                f"component '{first.component_name}'; exactly one writer is allowed",
                other.location(),
                notes=[("also written here", first.location())],
            )
    elif not producers:
        for consumer in consumers:
            bag.add(
                "missing-producer",
                f"'{name}' is read by component '{consumer.component_name}' but no component "
                f"declares it as output",
                consumer.location(),
            )

    return producers[0] if producers else None


# -- references and shapes --------------------------------------------------


def _resolve_shape(
    definition: DataObject,
    effective: dict[str, DataObject],
    reference: DeclarationRef,
    bag: DiagnosticBag,
) -> Shape:
    """The storage shape of an object; for a curve or map it follows from its axes."""
    if isinstance(definition, Axis) and definition.input is not None:
        _lookup(
            definition.input,
            ObjectKind.MEASUREMENT,
            "input",
            definition,
            effective,
            reference,
            bag,
        )

    if isinstance(definition, Curve):
        axis = _lookup(
            definition.axis, ObjectKind.AXIS, "axis", definition, effective, reference, bag
        )
        return (axis.size,) if isinstance(axis, Axis) else ()

    if isinstance(definition, Map):
        x_axis = _lookup(
            definition.x_axis, ObjectKind.AXIS, "x_axis", definition, effective, reference, bag
        )
        y_axis = _lookup(
            definition.y_axis, ObjectKind.AXIS, "y_axis", definition, effective, reference, bag
        )
        if isinstance(x_axis, Axis) and isinstance(y_axis, Axis):
            # A map is stored row wise: the x index runs fastest, so it is the last one.
            return (y_axis.size, x_axis.size)
        return ()

    shape = definition.declared_shape
    return shape if shape is not None else ()


def _lookup(
    target: str,
    expected: ObjectKind,
    field: str,
    definition: DataObject,
    effective: dict[str, DataObject],
    reference: DeclarationRef,
    bag: DiagnosticBag,
) -> DataObject | None:
    """Resolve a reference to another data object and report what is wrong with it."""
    found = effective.get(target)
    if found is None:
        bag.add(
            "unknown-reference",
            f"{definition.kind.value} '{definition.name}' refers to '{target}' as its "
            f"{field}, but no component declares '{target}'",
            reference.location(f"definition.{field}"),
        )
        return None
    if found.kind is not expected:
        bag.add(
            "reference-kind",
            f"the {field} of {definition.kind.value} '{definition.name}' must be of kind "
            f"'{expected.value}', but '{target}' is of kind '{found.kind.value}'",
            reference.location(f"definition.{field}"),
        )
        return None
    return found


# -- per variable checks ----------------------------------------------------


def _build_variable(
    name: str,
    refs: list[DeclarationRef],
    producer: DeclarationRef | None,
    definition: DataObject,
    shape: Shape,
    bag: DiagnosticBag,
) -> Variable:
    reference = producer or refs[0]

    for ref in refs:
        if ref.definition.declared_shape is None:
            _check_init_shape(ref, shape, bag)
        if ref is not reference:
            _compare(reference, ref, bag)

    consumers = [ref for ref in refs if ref.scope is Scope.INPUT]
    if producer is not None and producer.scope is Scope.OUTPUT and not consumers:
        bag.add(
            "unused-output",
            f"'{name}' is written by component '{producer.component_name}' but read by nobody",
            producer.location(),
        )

    return Variable(
        name=name,
        definition=definition,
        shape=shape,
        producer=producer,
        declarations=tuple(refs),
        condition=reference.condition,
    )


def _check_init_shape(ref: DeclarationRef, shape: Shape, bag: DiagnosticBag) -> None:
    """Init shape of a curve or map, which is only known once the axes are resolved."""
    init = ref.definition.init
    if not isinstance(init, tuple) or not shape:
        return
    problem = check_shape(init, shape)
    if problem is not None:
        bag.add(
            "init-invalid",
            f"'{ref.name}' has the shape {format_shape(shape)} given by its axes: {problem}",
            ref.location("definition.init"),
        )


def _compare(reference: DeclarationRef, other: DeclarationRef, bag: DiagnosticBag) -> None:
    """Compare two declarations of the same data object."""
    note = [("reference declaration", reference.location("definition"))]

    interface = _differing(_INTERFACE_FIELDS, reference.definition, other.definition)
    if interface:
        bag.add(
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
        bag.add(
            "storage-mismatch",
            f"'{other.name}': component '{other.component_name}' specifies a different "
            f"{named} than '{reference.component_name}' "
            f"({_spell_out(storage, reference.definition, other.definition)}); "
            f"the value of '{reference.component_name}' is used",
            other.location("definition"),
            notes=note,
        )

    if reference.condition != other.condition:
        bag.add(
            "condition-mismatch",
            f"'{other.name}': component '{other.component_name}' uses condition "
            f"{_condition(other.condition)} while '{reference.component_name}' uses "
            f"{_condition(reference.condition)}",
            other.location("condition") if other.condition else other.location(),
            notes=[("reference declaration", reference.location())],
        )


def _check_similar_names(variables: list[Variable], bag: DiagnosticBag) -> None:
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
            bag.add(
                "name-similar",
                f"'{name}' and '{first}' differ only in upper/lower case",
                variable.declarations[0].location("definition.name"),
                notes=[("other variable", by_name[first].declarations[0].location("definition"))],
            )


# -- small helpers ----------------------------------------------------------


def _condition(condition: str | None) -> str:
    return f"'{condition}'" if condition else "no condition"


def _enum_key(conversion: EnumConversion) -> tuple[tuple[str, int], ...]:
    return tuple((e.name, e.value) for e in conversion.enumerators)


def _enum_summary(conversion: EnumConversion) -> str:
    return ", ".join(f"{e.name}={e.value}" for e in conversion.enumerators)


def _below(value: float, limit: float) -> bool:
    return value < limit and not math.isclose(value, limit, rel_tol=1e-9, abs_tol=0.0)


def _above(value: float, limit: float) -> bool:
    return value > limit and not math.isclose(value, limit, rel_tol=1e-9, abs_tol=0.0)
