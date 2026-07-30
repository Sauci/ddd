"""Contract for the project description file."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ddd.models.common import FileRoot, Identifier


class Project(BaseModel):
    """A project is a named list of components and/or sub-projects."""

    model_config = ConfigDict(frozen=True, extra="forbid", use_attribute_docstrings=True)

    name: Identifier
    """Name of the project; also the a2l project and module name."""

    description: str = ""
    """Free text describing the project."""

    naming: str | None = None
    """Path to the naming convention every declared name has to follow, relative to this file.

    A convention belongs to the project rather than to the command line: whoever checks the
    project should get the same verdict as whoever wrote it.
    """

    includes: tuple[str, ...] = ()
    """Paths to component or sub-project files, relative to this file.

    Shell style wildcards (``*``, ``?``, ``**``) are expanded; the kind of every
    included file is detected from its top level key.
    """


class ProjectFile(FileRoot):
    """Root object of a ``*.json`` project description."""

    project: Project
