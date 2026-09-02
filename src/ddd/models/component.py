"""Contract for the software component description file."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ddd.models.common import FileRoot, Identifier
from ddd.models.constants import ConstantDeclaration
from ddd.models.objects import AnyDataObject
from ddd.models.types import AnyType, check_distinct_type_names


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
    """One entry of the ``interface`` list of a component."""

    model_config = ConfigDict(frozen=True, extra="forbid", use_attribute_docstrings=True)

    scope: Scope
    """Direction of the declaration, which is what makes the interfaces check each other.

    Exactly one component may produce a name - declare it ``output`` or ``local`` - and that
    component's definition is the one the project uses. Every ``input`` declaring the same
    name has to agree with it on datatype, unit, conversion, limits and shape.
    """

    condition: str | None = None
    """C preprocessor expression wrapping the generated declaration, e.g. ``defined(FEAT_X)``.

    One expression, written as it would appear after ``#if``. It is emitted verbatim into the
    generated files, so it cannot span lines and cannot contain ``#``, ``//``, ``/*`` or
    ``*/`` - each of which would let a description file put arbitrary directives, or live
    code, into somebody else's build.
    """

    definition: AnyDataObject
    """The data object being declared; its ``kind`` decides which keys it carries."""

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

    raster: str | None = None
    """Default measurement raster for every variable this component produces.

    The common case stated once: a component updates nearly all of its measurements in one
    task, and repeating that on several hundred definitions would bury the handful of
    exceptions, which state their own ``raster``. It applies to what this component
    produces and to nothing it reads - the raster follows the producer - and it reaches no
    calibration object, since no daq list carries one.
    """

    interface: tuple[Declaration, ...]
    """The data interface: everything the component produces, consumes or keeps to itself.

    Required with no default, so that a component with nothing to declare says so with an
    empty list rather than by a key that might merely have been forgotten - the same
    reasoning that makes ``volatile`` and ``kind`` required on a definition.
    """

    types: Annotated[tuple[AnyType, ...], Field(min_length=1)] | None = None
    """Declared types this component publishes, each entry exactly as a types file writes it.

    Declaring them here co-locates a library's contract in one file; it does not scope it.
    The names join the same project wide namespace as the types of the standalone files,
    every consistency check applies to them unchanged, and any component of the project may
    name them. Types shared between several components, with no single owner to live inside,
    stay in a standalone types file.
    """

    constants: Annotated[tuple[ConstantDeclaration, ...], Field(min_length=1)] | None = None
    """Declared constants this component publishes, each entry exactly as a constants file
    writes it.

    Co-located for the reason ``types`` may be, and no more scoped than they are: the names
    join the same project wide namespace as the constants of the standalone files, and any
    shape of any component names one where it would state a number. ``units`` and
    ``sections`` remain project wide vocabularies and have no place inside a component.
    """

    @model_validator(mode="after")
    def _type_names_are_distinct(self) -> Component:
        if self.types is not None:
            check_distinct_type_names(self.types)
        return self


class ComponentFile(FileRoot):
    """Root object of a ``*.ddd.json`` software component description.

    ``component`` is the top level key that makes this a component file rather than a project
    or a types file; DDD decides what a file is from that key alone, so exactly one of them
    appears here.
    """

    model_config = ConfigDict(title="DDD component description")

    component: Component
    """The component this file describes; the key that identifies the file as a component."""
