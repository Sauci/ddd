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

from ddd.build_info import BUILD_INFO_FILENAME, BUILD_INFO_FORMAT, BuildInfo

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
        found.update(path for path in directory.rglob(BUILD_INFO_FILENAME) if path.is_file())
    return sorted(found)


def load_builds(paths: Iterable[Path]) -> list[BuildInfo]:
    """Read the records, skipping any this version cannot make sense of.

    Skipped rather than reported: these files are written by a build, not by a person, so a
    malformed one is not a mistake somebody can fix in the editor that would be showing the
    complaint. A record from a newer DDD is the same story - it carries keys this version does
    not know, which is exactly what the format stamp is there to tell us.
    """
    builds = []
    for path in paths:
        try:
            info = BuildInfo.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, ValueError):
            continue
        # A record carrying keys this version does not know is already refused above, the
        # objects being closed. This catches the other shape of "newer": the same keys with a
        # meaning that has moved on, which only the stamp can say.
        if info.format > BUILD_INFO_FORMAT:
            continue
        builds.append(info)
    return builds


def discover(root: Path, configured: Sequence[Path] = ()) -> list[BuildInfo]:
    """Every project a build in this workspace is configured to generate."""
    return load_builds(build_files(root, configured))
