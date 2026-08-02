"""What a build tells an editor about the project it configured.

A build knows two things no description file records: which project description DDD is
actually run on, and under which severity policy. Neither is discoverable from the
``*.ddd.json`` files themselves. In the collected mode of ``ddd_generate`` the project
description is not even in the source tree - it is written into the build directory out of the
c link closure, so which components belong together is a property of the build rather than of
any file somebody wrote.

This module is the hand-off. ``ddd build-info`` writes it at configure time, for the same
reason ``SCHEMA_DIRECTORY`` writes the json schemas at configure time: nothing in the build
consumes either, and both exist so that a tool outside the build can see what the build sees.

Two properties are deliberate and easy to lose:

* **The project description is recorded, never read.** In the collected mode it is produced by
  ``file(GENERATE)``, which runs at the end of a configure run - after the process that writes
  this file. Requiring it to exist would fail every first configure.
* **The file is not named** ``*.ddd.json``. That extension means "a DDD description file", the
  ``file-extension`` check enforces it, and ``file-kind`` would then reject this content for
  having none of the four top level keys. It is a document *about* a project, not one.
"""

from __future__ import annotations

import json
from typing import Final

from pydantic import BaseModel, ConfigDict

BUILD_INFO_FORMAT: Final = 1
"""Version of the document format itself.

Raised only when the shape of the document changes, so that a reader older than the build that
wrote the file can say so instead of misreading it. The same discipline as the data dictionary,
for the same reason: these two are the documents DDD produces rather than reads.
"""

BUILD_INFO_FILENAME: Final = "ddd-build.json"
"""What a build system writes, and therefore what a tool looks for."""


class BuildInfo(BaseModel):
    """How one build target is configured to run DDD."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        use_attribute_docstrings=True,
        title="DDD build information",
    )

    format: int = BUILD_INFO_FORMAT
    """Version of this document format, raised only when its shape changes."""

    project: str
    """Absolute path of the project description the build runs DDD on.

    Absolute because this file lives in the build tree while the project it names may be in
    the source tree, or may itself be generated somewhere else again.
    """

    image: str = ""
    """Build target this was written for.

    What tells two of these apart: a component linked into both a firmware and a test binary
    belongs to two projects, and they need not agree about it.
    """

    strict: bool = False
    """Whether the build reports warnings as errors."""

    severity: tuple[str, ...] = ()
    """Severity overrides the build applies, as ``check=severity``, in the order given.

    Carried because a tool that ignores them reports a different set of findings than the
    build does, which is worse than reporting none at all.
    """


def build_info_text(info: BuildInfo) -> str:
    """The document as it is written out.

    One function so that what a build writes and what anything else produces cannot differ,
    the same arrangement the published json schemas use.
    """
    return json.dumps(info.model_dump(mode="json"), indent=2) + "\n"
