"""The data dictionary: the contract between the front end and the backends.

Everything before this module - loading, resolving, checking - produces a
:class:`DataDictionary`. Everything after it - the c backend, the a2l backend, whatever
comes next - consumes one and nothing else. A backend therefore never reaches into the
loader or the analysis; if it needs to know something, that something is a field here.

The contract is a pydantic model rather than a plain dataclass on purpose:

* it can be written out and read back (``ddd dump``), so a third party can generate from a
  data dictionary without importing python at all,
* it publishes a json schema (``ddd schema dictionary``), which is what makes "interface"
  more than a word,
* and it validates what a producer hands over, so a bug in the analysis surfaces here
  instead of halfway through a jinja template.

Everything in here is resolved: limits are filled in, the shape of a curve is the size of
its axis, and the definition is the one of the producing component. A backend never has to
repeat that work, and two backends can never disagree about it.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, model_validator

from ddd.models.common import Datatype, Identifier
from ddd.models.component import Scope
from ddd.models.constants import ConstantDeclaration
from ddd.models.conversion import Conversion, EnumConversion
from ddd.models.objects import A2lObjectOptions, Dimension, InitValue, Limits, ObjectKind


def _check_dimensions_match(shape: tuple[int, ...], dimensions: tuple[int | str, ...]) -> None:
    """Refuse a spelled shape that does not describe the numeric one beside it.

    ``dimensions`` is ``shape`` again, spelling by spelling, so the two agree dimension for
    dimension or the document contradicts itself. Empty is allowed whatever the shape: a
    dictionary from format 3 or older spelled every dimension as its number and carries no
    ``dimensions`` at all.
    """
    if dimensions and len(dimensions) != len(shape):
        msg = (
            f"'dimensions' spells {len(dimensions)} dimension(s) but 'shape' has "
            f"{len(shape)}; the two describe the same shape and must agree"
        )
        raise ValueError(msg)


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", use_attribute_docstrings=True)


class ComponentDeclaration(_Frozen):
    """One entry of a component interface, in the order the component declared it.

    A reference to an object rather than the object itself: the definition lives once, under
    ``objects``, and is the one the producing component gave. Two components declaring the
    same name appear here twice and in ``objects`` once.
    """

    name: Identifier
    """Name of the declared object; a key into the ``objects`` list of the dictionary."""

    scope: Scope
    """How this component uses the object: ``input``, ``output`` or ``local``."""

    condition: str | None = None
    """Preprocessor expression this component guarded the declaration with, if any."""


class ResolvedComponent(_Frozen):
    """A component and the objects it declares."""

    name: Identifier
    """Name of the component, unique within the project."""

    description: str = ""
    """Free text from the component description, offered to the templates."""

    source: str = ""
    """Path of the description file, for reference in generated comments."""

    declarations: tuple[ComponentDeclaration, ...] = ()
    """The interface of the component, in the order it declared it."""


class ResolvedObject(_Frozen):
    """One data object, with every derived property already worked out."""

    name: Identifier
    """Name of the object, unique across the whole project; its c and a2l identifier."""

    kind: ObjectKind
    """Which sort of object this is, taken from the definition that produced it."""

    datatype: Datatype
    """Storage type of one element."""

    description: str = ""
    """What the object is; the a2l long identifier and the comment in the generated c."""

    unit: str = ""
    """Physical unit, as the declaring components agreed on it."""

    conversion: Conversion
    """Always present: the declared conversion, or the identity when none was given."""

    limits: Limits
    """Always present: the explicit limits, or the range the datatype and conversion imply."""

    shape: tuple[PositiveInt, ...] = ()
    """Storage shape, empty for a scalar; for a curve or a map it comes from its axes.

    Every dimension is at least one, like the ``dimensions`` and ``size`` it derives from,
    and every dimension is a resolved number: a dimension stated as the name of a declared
    constant carries its value here and its name in ``dimensions``.
    """

    dimensions: tuple[Dimension, ...] = ()
    """The shape again, each dimension spelled the way the project spells it.

    Parallel to ``shape``: the same dimensions in the same order, each the number itself or
    the name of the declared constant that states it - the name under which the generated
    code declares the array. Empty exactly when ``shape`` is empty; a dictionary from
    format 3 or older leaves it empty, every dimension then being spelled as its number.
    """

    init: InitValue | None = None
    """Raw initial value, nested to match ``shape``; ``null`` means zero initialised."""

    section: str | None = None
    """Linker section the producing declaration placed the object in; ``null`` for the
    toolchain's defaults."""

    volatile: bool = False
    """Generate the object ``volatile``: stated by every declaration, on every kind.

    Calibration data carries it as ``const volatile``, which is what a value the calibration
    tool changes in a running ecu needs - see the field of the same name on the authored
    definition. The default is kept although a definition may no longer omit it, so that a
    dictionary dumped by an older DDD still reads back; that is what ``DICTIONARY_FORMAT``
    exists to make safe.
    """

    condition: str | None = None
    """Preprocessor condition of the producing declaration, if any."""

    references: dict[str, str] = Field(default_factory=dict)
    """Other objects this one refers to, keyed by field name (``axis``, ``x_axis``, ...)."""

    owner: str | None = None
    """Component owning the object; ``None`` only when the project is inconsistent."""

    consumers: tuple[str, ...] = ()
    """Components declaring the object as an input, sorted; empty when nothing reads it."""

    local: bool = False
    """Owned exclusively by ``owner``; no other component may declare it."""

    a2l: A2lObjectOptions = A2lObjectOptions()
    """What the author asked for in the ``a2l`` block. Only the a2l backend interprets it."""

    @property
    def is_calibration(self) -> bool:
        return self.kind.is_calibration

    @property
    def spelled_shape(self) -> tuple[int | str, ...]:
        """The shape as the project spells it: ``dimensions`` where recorded, else the numbers."""
        return self.dimensions if self.dimensions else tuple(self.shape)

    @property
    def written_shape(self) -> tuple[tuple[int | str, int], ...]:
        """Each dimension as its (spelling, value) pair.

        What two deliveries compare: a name and its value are different spellings of one
        size, so a dimension that changes either half is a changed interface.
        """
        return tuple(zip(self.spelled_shape, self.shape, strict=True))

    @model_validator(mode="after")
    def _dimensions_spell_the_shape(self) -> ResolvedObject:
        _check_dimensions_match(self.shape, self.dimensions)
        return self


class ResolvedMember(_Frozen):
    """One member of a structure, as the c templates need it to declare the member.

    Only what a declaration takes. The meaning of the member - its unit, its conversion, its
    limits - travels with the *leaf* instead, because that is the form the a2l consumes and
    there is no second place a reader should have to look.
    """

    name: Identifier
    """Name of the member, as it is written in the c struct."""

    description: str = ""
    """What the member is, for a comment beside its declaration."""

    datatype: Datatype | None = None
    """Storage of the member when it is a base one; ``None`` when it names a structure."""

    type: str | None = None
    """Name of the structure this member is, when it is one; ``None`` when it is a datatype."""

    shape: tuple[Dimension, ...] = ()
    """Array dimensions, empty for a scalar, each spelled the way the member spells it.

    A number, or the name of a declared constant, which is the spelling the member is
    declared with. The numeric value of a named dimension is in the dictionary's
    ``constants``, and every leaf of an instantiated structure carries its resolved numeric
    shape - a member is the declaration side of the answer, a leaf the resolved one.
    """

    bits: int | None = None
    """Width in bits when the member is a c bitfield; ``None`` when it is not."""


class ResolvedStruct(_Frozen):
    """One structure, in an order a c file can be written out in.

    The order of :attr:`DataDictionary.types` matters and is not alphabetical: a structure
    appears after every structure it nests, because a c compiler needs the nested one to be
    complete first. The members keep the order the author wrote them in, which is the order the
    compiler lays them out.
    """

    name: Identifier
    """Name of the structure, which is the name of the generated typedef."""

    description: str = ""
    """What the structure is, for a comment above it."""

    members: tuple[ResolvedMember, ...] = ()
    """The members, in declaration order."""


class ResolvedInstance(_Frozen):
    """One variable whose datatype is a structure.

    Kept apart from :class:`ResolvedObject` rather than widening it: an object with no datatype
    and no limits would turn every reader of those two fields into a branch, and they are read
    unconditionally in a dozen places on the strength of always being there.
    """

    name: Identifier
    """Name of the variable; its c identifier and the root of every leaf path."""

    type: str
    """Name of the structure it is, which is the c type of the declaration."""

    kind: ObjectKind
    """``measurement`` or ``parameter``: what the whole object is, and so how it is qualified."""

    description: str = ""
    """What the object is; the comment in the generated c."""

    shape: tuple[PositiveInt, ...] = ()
    """Array dimensions of the variable itself, empty for a single structure.

    An array of structures reaches the a2l as its elements: there is no one address that
    describes ``cell[0].raw`` and ``cell[1].raw`` at once, so each element contributes its own
    leaves at its own path. Every dimension is a resolved number; the spelling is in
    ``dimensions``.
    """

    dimensions: tuple[Dimension, ...] = ()
    """The shape again, each dimension spelled the way the declaration spells it.

    Parallel to ``shape`` exactly as on a plain object: the number, or the name of the
    declared constant the generated code declares the array by. Empty in a dictionary from
    format 3 or older.
    """

    volatile: bool = False
    """Whether the declaration carries ``volatile``, which qualifies the whole object."""

    section: str | None = None
    """Linker section the whole structure is placed in; its members have no placement
    of their own."""

    condition: str | None = None
    """Preprocessor condition of the producing declaration, if any."""

    owner: str | None = None
    """Component owning the object; ``None`` only when the project is inconsistent."""

    consumers: tuple[str, ...] = ()
    """Components declaring the object as an input, sorted."""

    local: bool = False
    """Owned exclusively by ``owner``; no other component may declare it."""

    a2l: A2lObjectOptions = A2lObjectOptions()
    """What the whole object asks of the a2l; a member may ask for more of its own."""

    @property
    def is_calibration(self) -> bool:
        return self.kind.is_calibration

    @property
    def spelled_shape(self) -> tuple[int | str, ...]:
        """The shape as the project spells it: ``dimensions`` where recorded, else the numbers."""
        return self.dimensions if self.dimensions else tuple(self.shape)

    @model_validator(mode="after")
    def _dimensions_spell_the_shape(self) -> ResolvedInstance:
        _check_dimensions_match(self.shape, self.dimensions)
        return self


class ResolvedLeaf(_Frozen):
    """One member of one structured variable, at the end of one access path.

    The flattening. A structure reaches the a2l as an object per member rather than as an a2l
    structure, so this is the form that backend consumes - an ordinary object in every respect
    but its name, which is a path rather than an identifier.
    """

    path: str
    """The c expression that reads this member: ``Inlet.latest.value``, ``Inlet.cell[2].raw``.

    Both the name the a2l gives the object and the symbol it links it to. Written the way it
    would be written in c, so that a reader of the a2l, of the generated c and of a map file is
    looking at one string rather than at three spellings of one thing.
    """

    instance: Identifier
    """Name of the variable this leaf belongs to, which is the root of :attr:`path`."""

    kind: ObjectKind
    """Taken from the variable: every leaf of one object has the storage class of the whole."""

    datatype: Datatype
    """Storage of one element."""

    description: str = ""
    """What this member is; the a2l long identifier."""

    unit: str = ""
    """Physical unit, from the member or from the type it names."""

    conversion: Conversion
    """Always present: the member's conversion, or the identity when none was given."""

    limits: Limits
    """Always present: stated, or derived from the storage - a bitfield's from its width."""

    shape: tuple[PositiveInt, ...] = ()
    """Array dimensions of this member; empty for a scalar.

    Every dimension is a resolved number, because this is the form the a2l consumes; a
    dimension the member spells as a constant name carries that name in ``dimensions``.
    """

    dimensions: tuple[Dimension, ...] = ()
    """The shape again, each dimension spelled the way the member spells it.

    Parallel to ``shape`` exactly as on a plain object. Empty in a dictionary from format 3
    or older.
    """

    bits: int | None = None
    """Width in bits when the member is a c bitfield.

    Such a leaf has no address of its own - ``&s.ready`` does not compile - so it reaches no
    a2l until a build tells DDD both where the word is and which bits inside it to read.
    """

    volatile: bool = False
    """From the variable, which carries the qualifier for all of its members at once."""

    section: str | None = None
    """Linker section of the structure this member belongs to; a member has no placement
    of its own."""

    condition: str | None = None
    """Preprocessor condition of the producing declaration, if any."""

    owner: str | None = None
    """Component owning the variable this leaf belongs to."""

    consumers: tuple[str, ...] = ()
    """Components declaring the variable as an input, sorted."""

    local: bool = False
    """Owned exclusively by ``owner``."""

    a2l: A2lObjectOptions = A2lObjectOptions()
    """The member's own a2l options; a member may be kept out of the file on its own."""

    @property
    def name(self) -> str:
        """The name this member is published under, which is its path.

        A leaf is an object to everything downstream - it is compared, counted and listed like
        one - and the path is what it is called in the a2l. Having it answer to ``name`` is
        what lets one comparison serve both without a second spelling of every rule.
        """
        return self.path

    @property
    def init(self) -> None:
        """Never stated: what a structure starts as is written by the code that starts it."""
        return None

    @property
    def references(self) -> dict[str, str]:
        """None: a structure member cannot name an axis, so it refers to no other object."""
        return {}

    @property
    def is_calibration(self) -> bool:
        return self.kind.is_calibration

    @property
    def spelled_shape(self) -> tuple[int | str, ...]:
        """The shape as the project spells it: ``dimensions`` where recorded, else the numbers."""
        return self.dimensions if self.dimensions else tuple(self.shape)

    @property
    def written_shape(self) -> tuple[tuple[int | str, int], ...]:
        """Each dimension as its (spelling, value) pair, exactly as on a plain object."""
        return tuple(zip(self.spelled_shape, self.shape, strict=True))

    @model_validator(mode="after")
    def _dimensions_spell_the_shape(self) -> ResolvedLeaf:
        _check_dimensions_match(self.shape, self.dimensions)
        return self


Comparable = ResolvedObject | ResolvedLeaf
"""What one delivery offers another: a plain object, or a member of a structured one.

The two are compared, counted and listed identically, because to a consumer they are the same
kind of thing - a place with a datatype, a unit and limits, which can be removed, retyped or
rescaled. They differ only in what they are called, and a leaf answers to its path.
"""


DICTIONARY_FORMAT = 4
"""Version of the dictionary format itself.

A dumped dictionary is meant to be archived next to a delivery and read back by a later
version of DDD, possibly years on. Stamping the format is what lets that later version say
"this file is newer than I understand" instead of misreading it or rejecting it for a
missing field. It changes only when the shape of the document changes, not with the tool.
"""


class DataDictionary(_Frozen):
    """The resolved data of one project.

    What ``ddd dump`` writes and every backend reads. Unlike the description files, this one
    is produced rather than authored: every derived property is already worked out, so a
    consumer never has to repeat the resolution and two consumers can never disagree about it.
    """

    model_config = ConfigDict(title="DDD data dictionary")

    format: int = DICTIONARY_FORMAT
    """Version of this document format, raised only when the shape of the document changes.

    Stamped so that a dictionary archived next to a delivery can be read back years later by
    a version of DDD that can say "this file is newer than I understand" rather than misread
    it. It does not follow the version of the tool.
    """

    name: Identifier
    """Name of the project, from the root project description."""

    description: str = ""
    """Free text from the root project description."""

    source: str = ""
    """Name of the root description file, for reference in generated comments."""

    components: tuple[ResolvedComponent, ...] = ()
    """Every component of the project, including those of its sub-projects."""

    objects: tuple[ResolvedObject, ...] = ()
    """Sorted by name, so that every backend produces a stable output."""

    enums: tuple[EnumConversion, ...] = ()
    """Distinct enumerations used by the objects, sorted by name."""

    constants: tuple[ConstantDeclaration, ...] = ()
    """The named constants the project declares, sorted by name.

    Recorded whole - name, value and description - so that a generator consuming the
    dictionary can emit them the way the shipped templates do, and so that a dimension
    spelled by name stays resolvable after the description files have moved on.
    """

    types: tuple[ResolvedStruct, ...] = ()
    """The structures the project declares, each after every structure it nests.

    Dependency order rather than alphabetical, because a template that simply loops over them
    has to be able to write them out as they come: c needs a nested structure to be complete
    before the one that contains it.
    """

    instances: tuple[ResolvedInstance, ...] = ()
    """Variables whose datatype is a structure, sorted by name."""

    leaves: tuple[ResolvedLeaf, ...] = ()
    """Every member of every structured variable, flattened, sorted by path.

    Written out rather than worked out on demand, because the dictionary is a produced
    document: a generator DDD does not ship reads it without importing python, and no backend
    should repeat resolution the analysis has already done.
    """

    @property
    def by_name(self) -> dict[str, ResolvedObject]:
        return {entry.name: entry for entry in self.objects}

    @property
    def comparable(self) -> dict[str, Comparable]:
        """Every object one delivery offers another, keyed by the name it offers it under.

        The members of a structured variable are in here as ordinary objects under their access
        paths, because that is what they are to a consumer: ``Inlet.latest.value`` is a place
        with a datatype and a unit, and it can be removed, retyped or rescaled exactly as any
        other can. Leaving them out made a delivery that dropped every structure look identical
        to the one before it.
        """
        entries: tuple[Comparable, ...] = (*self.objects, *self.leaves)
        return {entry.name: entry for entry in entries}

    @property
    def datatypes(self) -> set[Datatype]:
        """Every base datatype the generated c has to be able to spell.

        The members of the structures count. A project whose only ``uint8`` sits inside one
        would otherwise get a header spelling ``uint8_t`` that never includes ``<stdint.h>``.
        """
        return (
            {entry.datatype for entry in self.objects}
            | {leaf.datatype for leaf in self.leaves}
            | {
                member.datatype
                for structure in self.types
                for member in structure.members
                if member.datatype is not None
            }
        )

    @property
    def listed(self) -> tuple[Comparable, ...]:
        """What the tool counts and lists: the plain objects and the structured members.

        A summary that counted only the plain ones told a project with four objects that it
        had two, which is the sort of quiet wrongness that costs somebody an afternoon.
        """
        return tuple(sorted(self.comparable.values(), key=lambda entry: entry.name))

    def instances_owned_by(self, component: str) -> tuple[ResolvedInstance, ...]:
        """The structured variables one component owns, in the order they are published."""
        return tuple(entry for entry in self.instances if entry.owner == component)

    def owned_by(self, component: str) -> tuple[ResolvedObject, ...]:
        return tuple(entry for entry in self.objects if entry.owner == component)

    def unowned(self) -> tuple[ResolvedObject | ResolvedInstance, ...]:
        """Every variable no component declares as output; only possible when
        ``missing-producer`` is relaxed or the generation forced.

        The structured variables belong here as much as the plain ones: the project wide file
        defines an object no component owns like any other, and leaving an instance out
        generated headers that declared it ``extern`` over storage that nowhere existed.
        """
        entries: tuple[ResolvedObject | ResolvedInstance, ...] = (*self.objects, *self.instances)
        return tuple(entry for entry in entries if entry.owner is None)
