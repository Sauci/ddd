"""Contract for the software component description file."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator

from ddd.models.common import FileRoot, Identifier
from ddd.models.objects import AnyDataObject


class Scope(StrEnum):
    """Direction of a variable with respect to the declaring component."""

    INPUT = "input"
    """The component reads the variable; another component has to produce it."""

    OUTPUT = "output"
    """The component writes the variable; exactly one component may do so."""

    LOCAL = "local"
    """The component owns the variable exclusively; no other component may use it."""

    @property
    def is_producer(self) -> bool:
        return self is Scope.OUTPUT or self is Scope.LOCAL


class Declaration(BaseModel):
    """One entry of the ``declarations`` list of a component."""

    model_config = ConfigDict(frozen=True, extra="forbid", use_attribute_docstrings=True)

    scope: Scope
    """Direction of the declaration: ``input``, ``output`` or ``local``."""

    condition: str | None = None
    """C preprocessor expression wrapping the generated declaration, e.g. ``defined(FEAT_X)``."""

    definition: AnyDataObject
    """The data object being declared."""

    @field_validator("condition")
    @classmethod
    def _condition_is_a_single_expression(cls, value: str | None) -> str | None:
        """One preprocessor expression, and nothing that could end or start something else.

        The text is emitted verbatim into ``#if <condition>`` and into the trailing
        ``#endif /* <condition> */`` of every generated file, and into a comment in the a2l.
        A line break would put arbitrary directives inside the guarded region, and a comment
        marker would close the trailer early and leave whatever follows as live code -
        neither of which the author of a description file should be able to do to somebody
        else's build.
        """
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            return None
        if "\n" in stripped or "\r" in stripped:
            msg = "a condition is a single expression and cannot contain a line break"
            raise ValueError(msg)
        for token in ("/*", "*/", "//", "#"):
            if token in stripped:
                msg = f"a condition cannot contain '{token}'"
                raise ValueError(msg)
        return stripped


class Component(BaseModel):
    """The interface specification of one software component."""

    model_config = ConfigDict(frozen=True, extra="forbid", use_attribute_docstrings=True)

    name: Identifier
    """Name of the component; every component of a project needs a distinct one."""

    description: str = ""
    """Free text describing the component, offered to the c templates."""

    declarations: tuple[Declaration, ...] = ()
    """The data interface: everything the component produces, consumes or keeps to itself."""


class ComponentFile(FileRoot):
    """Root object of a ``*.json`` software component description."""

    component: Component
