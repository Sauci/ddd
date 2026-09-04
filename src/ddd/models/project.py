"""Contract for the project description file."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from ddd.models.common import FileRoot, Identifier


class Project(BaseModel):
    """A project is a named list of components and/or sub-projects."""

    model_config = ConfigDict(frozen=True, extra="forbid", use_attribute_docstrings=True)

    name: Identifier
    """Name of the project; also the a2l project and module name."""

    description: str = ""
    """Free text describing the project."""

    includes: tuple[str, ...] = ()
    """Paths to component, types, units, sections, constants or sub-project files,
    relative to this file.

    Shell style wildcards (``*``, ``?``, ``**``) are expanded; the kind of every
    included file is detected from its top level key.
    """

    plugins: tuple[Annotated[str, StringConstraints(min_length=1)], ...] = ()
    """Plugins that extend DDD for this project, in the order their hooks run.

    Each entry is a ``.py`` path relative to this file - a plugin the project keeps in its
    own repository - or a dotted module name imported from the environment - one installed as
    a distribution. A plugin acts on a project because the project names it, never because
    it happens to be installed. A sub-project may name plugins too; the set in play is the
    union, because the blocks a plugin interprets may sit in any component.
    """

    extensions: dict[str, dict[str, Any]] = Field(default_factory=dict)
    """The settings of each plugin, keyed by plugin name: ``{"layout": {"max_key": 4095}}``.

    Validated against the plugin's project model, defaults filled in, and carried into the
    dictionary so that a comparison over an archived dump still knows them. A plugin's
    settings are stated by one project file; a second file stating them is a ``schema``
    finding, the way a second file declaring a section is refused.
    """


class ProjectFile(FileRoot):
    """Root object of a ``*.ddd.json`` project description.

    ``project`` is the top level key that makes this a project file rather than a component
    or a types file; DDD decides what a file is from that key alone, so exactly one of them
    appears here.
    """

    model_config = ConfigDict(title="DDD project description")

    project: Project
    """The project this file describes; the key that identifies the file as a project."""
