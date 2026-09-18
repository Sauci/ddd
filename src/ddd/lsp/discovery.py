"""Finding the projects a build configured, from what it left in the build tree.

The server cannot work this out from the description files, and the reason is in
:mod:`ddd.build_info`: without ``PROJECT`` the project description is collected out of the c
link graph and written into the build tree, so which components belong together is a property
of the build. What is discovered here is the record that build wrote.

The editor opens the *source* directory, so the build tree has to be found first. There is no
right answer to where it is - out of tree builds can be anywhere - so a client that knows says
so, and otherwise the usual names are tried. Getting this wrong costs the project-aware
findings and nothing else: an unfound build means standalone mode, not a broken server.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict

from ddd.build_info import BUILD_INFO_FILENAME, BUILD_INFO_FORMAT, BuildInfo
from ddd.diagnostics import SeverityPolicy, UnknownCheckError

BUILD_DIRECTORY_PATTERNS: Final = ("build", "out", "cmake-build-*")
"""Where a build tree usually sits, relative to the directory the editor opened."""


def build_files(root: Path, configured: Sequence[Path] = ()) -> list[Path]:
    """Every build record under the configured directories, or under the usual ones.

    Sorted, so that two runs over one workspace report the same projects in the same order and
    a diagnostic does not move between images from one save to the next.
    """
    directories = list(configured) or [
        candidate
        for pattern in BUILD_DIRECTORY_PATTERNS
        for candidate in sorted(root.glob(pattern))
        if candidate.is_dir()
    ]
    found: set[Path] = set()
    for directory in directories:
        # Resolved before it is counted, or one record is several. ``rglob`` walks a junction
        # as though it were a directory - python 3.13 keeps ``**`` out of a symlink, and a
        # junction is not one - so a link pointing anywhere above itself yields a new spelling
        # of every record under it per level. One `mklink /J build\\loop build` turned one
        # record into twenty-two: twenty-two announcements, and every finding of the project
        # published twenty-two times over.
        found.update(
            path.resolve() for path in directory.rglob(BUILD_INFO_FILENAME) if path.is_file()
        )
    return sorted(found)


class _Stamp(BaseModel):
    """The format a build record says it is in, read without the rest of it.

    Read the way :class:`ddd.build_info.BuildInfo` reads it, so a record is refused as newer by
    exactly the format it would otherwise have been validated as.
    """

    model_config = ConfigDict(extra="ignore")

    format: int = BUILD_INFO_FORMAT


def load_builds(paths: Iterable[Path], refused: dict[Path, str] | None = None) -> list[BuildInfo]:
    """Read the records, skipping any this version cannot use.

    A malformed record is skipped in silence: these files are written by a build, not by a
    person, so a broken one is not a mistake somebody can fix in the editor that would be
    showing the complaint.

    A record this version cannot use although nothing is wrong with it is skipped with the
    reason written into ``refused``, for a caller that has somewhere to say it - the language
    server's log, the start page of ``ddd gui``. Skipped in silence, such a record looks exactly
    like a workspace nobody ever configured a build in, and its project is analysed under the
    default severities with nothing to say why. Both shapes of it are what a team meets while
    its builds and its editors run different versions of DDD:

    * a record written by a newer DDD, in a format higher than this version reads. The stamp is
      read on its own, before the record is validated: a newer record is exactly one that may
      carry keys this version does not know, and the record's objects being closed, those keys
      fail its validation before the stamp could say why;
    * a record whose severities name a check this version has not got: the keys all validate
      and the stamp says nothing. It used to be fatal - building the policy raised out of the
      first refresh that reached it, so a record written by a newer ``ddd`` in the build tree
      ended the editor's server on the first document opened.
    """
    reasons = {} if refused is None else refused
    builds = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
            stamp = _Stamp.model_validate_json(text).format
        except (OSError, UnicodeDecodeError, ValueError):
            continue
        if stamp > BUILD_INFO_FORMAT:
            reasons[path] = (
                f"written in format {stamp} by a newer DDD, and this one understands up to "
                f"format {BUILD_INFO_FORMAT}"
            )
            continue
        try:
            info = BuildInfo.model_validate_json(text)
        except ValueError:
            continue
        try:
            SeverityPolicy.from_strings(list(info.severity), strict=info.strict)
        except UnknownCheckError as fault:
            reasons[path] = str(fault)
            continue
        builds.append(info)
    return builds


def discover(
    root: Path, configured: Sequence[Path] = (), refused: dict[Path, str] | None = None
) -> list[BuildInfo]:
    """Every project a build in this workspace is configured to generate."""
    return load_builds(build_files(root, configured), refused)
