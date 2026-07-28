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
    model_config = ConfigDict(frozen=True, extra="forbid")


class ComponentDeclaration(_Frozen):
    """One entry of a component interface, in the order the component declared it."""

    name: Identifier
    scope: Scope
    condition: str | None = None


class ResolvedComponent(_Frozen):
    """A component and the objects it declares."""

    name: Identifier
    description: str = ""
    source: str = ""
    """Path of the description file, for reference in generated comments."""

    declarations: tuple[ComponentDeclaration, ...] = ()


class ResolvedObject(_Frozen):
    """One data object, with every derived property already worked out."""

    name: Identifier
    kind: ObjectKind
    datatype: Datatype
    description: str = ""
    unit: str = ""

    conversion: Conversion
    limits: Limits
    """Always present: the explicit limits, or the range the datatype and conversion imply."""

    shape: tuple[PositiveInt, ...] = ()
    """Storage shape, empty for a scalar; for a curve or a map it comes from its axes.

    Every dimension is at least one, like the ``dimensions`` and ``size`` it derives from.
    """

    init: InitValue | None = None
    volatile: bool = False
    condition: str | None = None
    """Preprocessor condition of the producing declaration, if any."""

    references: dict[str, str] = Field(default_factory=dict)
    """Other objects this one refers to, keyed by field name (``axis``, ``x_axis``, ...)."""

    owner: str | None = None
    """Component owning the object; ``None`` only when the project is inconsistent."""

    consumers: tuple[str, ...] = ()
    local: bool = False
    """Owned exclusively by ``owner``; no other component may declare it."""

    a2l: A2lObjectOptions = A2lObjectOptions()
    """What the author asked for in the ``a2l`` block. Only the a2l backend interprets it."""

    @property
    def is_calibration(self) -> bool:
        return self.kind.is_calibration


class DataDictionary(_Frozen):
    """The resolved data of one project."""

    name: Identifier
    description: str = ""
    source: str = ""
    """Name of the root description file, for reference in generated comments."""

    components: tuple[ResolvedComponent, ...] = ()
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
