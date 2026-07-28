"""Contract for the software component description file."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator

from ddd.models.common import Identifier
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

    model_config = ConfigDict(frozen=True, extra="forbid")

    scope: Scope
    condition: str | None = None
    """C preprocessor expression wrapping the generated declaration, e.g. ``defined(FEAT_X)``."""

    definition: AnyDataObject

    @field_validator("condition")
    @classmethod
    def _blank_condition_is_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class Component(BaseModel):
    """The interface specification of one software component."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Identifier
    description: str = ""
    declarations: tuple[Declaration, ...] = ()


class ComponentFile(BaseModel):
    """Root object of a ``*.json`` software component description."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    component: Component
