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
  having none of the top level keys a description may have. It is a document *about* a
  project, not one.
"""

from __future__ import annotations

import json
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict

BUILD_INFO_FORMAT: Final = 2
"""Version of the document format itself.

Raised only when the shape of the document changes, so that a reader older than the build that
wrote the file can say so instead of misreading it. The same discipline as the data dictionary,
for the same reason: these two are the documents DDD produces rather than reads.

The highest format this DDD understands, which it reads along with every one below it. A record
is stamped 2 only where it carries ``origin``, which says the description was given to the build
as ``PROJECT``: the record's object is closed, so a reader that does not know that key fails the
record, and a DDD from 0.11.0 on declines a record stamped past its format as written by a newer
DDD and says so, where an older one skips it in silence, as it skips any record it cannot
validate. A record of a collected description has no such key, keeps the shape of format 1, and
is stamped 1: every DDD that read a record before reads it still.
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

    format: int = 1
    """Version of this document format, raised only when its shape changes.

    Stamped 2 where ``origin`` is written, and 1 where it is not: what the build writes is read
    by every DDD that could read a record of that shape.
    """

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

    origin: Literal["collected", "given"] = "collected"
    """Where the project description came from: ``given`` to the build as ``PROJECT``, a file
    somebody wrote and the build only reads, or ``collected`` by ``ddd_generate`` out of the link
    closure of the image, written into the build tree again at every configure.

    Written only for a given one, which stamps the record 2. A record without it, as every record
    of format 1 is, is a collected description: what ``ddd gui`` takes it for, and refuses to
    write into. Not named ``description``, which is a declaration's free text in the description
    files.
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
    data = info.model_dump(mode="json")
    if info.origin == "collected":
        # Kept out, so that the record of a collected description is the one every DDD reads.
        del data["origin"]
    else:
        data["format"] = BUILD_INFO_FORMAT
    return json.dumps(data, indent=2) + "\n"
