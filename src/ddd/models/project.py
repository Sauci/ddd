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

    includes: tuple[str, ...] = ()
    """Paths to component or sub-project files, relative to this file.

    Shell style wildcards (``*``, ``?``, ``**``) are expanded; the kind of every
    included file is detected from its top level key.
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
