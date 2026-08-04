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

from pydantic import BaseModel, ConfigDict, Field, PositiveInt

from ddd.models.common import Datatype, Identifier
from ddd.models.component import Scope
from ddd.models.conversion import Conversion, EnumConversion
from ddd.models.objects import A2lObjectOptions, InitValue, Limits, ObjectKind


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

    Every dimension is at least one, like the ``dimensions`` and ``size`` it derives from.
    """

    init: InitValue | None = None
    """Raw initial value, nested to match ``shape``; ``null`` means zero initialised."""

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


DICTIONARY_FORMAT = 1
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

    @property
    def by_name(self) -> dict[str, ResolvedObject]:
        return {entry.name: entry for entry in self.objects}

    @property
    def datatypes(self) -> set[Datatype]:
        return {entry.datatype for entry in self.objects}

    def owned_by(self, component: str) -> tuple[ResolvedObject, ...]:
        return tuple(entry for entry in self.objects if entry.owner == component)

    def unowned(self) -> tuple[ResolvedObject, ...]:
        """Objects no component declares as output; only possible with a forced generation."""
        return tuple(entry for entry in self.objects if entry.owner is None)
