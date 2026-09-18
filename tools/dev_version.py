"""Stamp a development version into the checkout ci builds.

``.github/workflows/ci.yml`` publishes a development build of the last commit of every push to
master, and of every push to this repository's own pull requests, to TestPyPI, so that such a
commit installs with ``pip install`` - its compiled pages included, and no node anywhere.  Its
``dev-build`` job runs this in its own checkout before it builds; ``dev-publish`` checks what it
is handed, and writes the run's summary from what it checked.  Nothing this rewrites is ever
committed.

The version is ``<next patch>.dev<run number>``: after 0.10.0, run 57 builds ``0.10.1.dev57``.
The commit cannot be part of it - PEP 440 refuses ``0.10.0-<sha>``, and PyPI and TestPyPI both
refuse a local label such as ``0.10.0+g<sha>`` - so the build's metadata carries it instead, as
the ``Commit`` url of ``[project.urls]``, and the summary of the run maps the version to it.  The
base is the *next* patch because ``0.10.0.dev57`` would sort before 0.10.0, beneath the release
the commit came after.  The run number grows across every branch, so every run publishes a
version of its own; a re-run keeps its number, which is what lets the upload skip the files the
first attempt already made.

``ddd --version`` keeps its format, ``ddd <version>``: ``cmake/Ddd.cmake`` compares what it
prints with its own ``DDD_MODULE_VERSION`` by exact string, and refuses a tool that differs.  So
the version is written into the three places the installed package compares at run time:
``pyproject.toml``, which names the distribution; ``src/ddd/__init__.py``, whose ``__version__``
is what ``ddd --version`` prints; and ``cmake/Ddd.cmake``, which the wheel carries as
``ddd/cmake/Ddd.cmake``.

It lives here, and not in the workflow, for the reason ``site_versions.py`` does: a rule nothing
can run is a rule nothing can check.  ``tests/test_documentation.py`` runs this one.

Not part of the ``ddd`` package: it is release machinery, it ships in the sdist rather than in
the wheel, and nothing the tool does at run time reads it.
"""

from __future__ import annotations

import re
import sys
import tomllib
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
"""The checkout this script is part of, which is the one it stamps from the command line."""

RELEASE = re.compile(r"\d+(?:\.\d+)*")
"""A version of numbers alone: the only kind with a next patch to build towards."""

COMMIT = re.compile(r"[0-9a-f]{40}")
"""A commit the way ci names one: the forty hexadecimal digits of its sha."""


def next_development(version: str, run: int) -> str:
    """The version run ``run`` builds after release ``version``: its next patch, ``.dev<run>``.

    Only a version of numbers alone has a next patch.  A release candidate such as ``0.11.0rc1``
    has two next versions - its next candidate and its release - and ``0.11.0.dev57`` would sort
    before the candidate itself; a development, post or local release is nothing a commit of
    master states.  Each is refused rather than guessed at.
    """
    if not RELEASE.fullmatch(version):
        raise ValueError(
            f"cannot number a development build after {version!r}: only a version of numbers "
            f"alone, such as 0.10.0, has a next patch to build towards"
        )
    *head, last = (int(part) for part in version.split("."))
    return ".".join(str(part) for part in (*head, last + 1)) + f".dev{run}"


def replaced_once(text: str, pattern: str, replacement: str, where: Path) -> str:
    """``text`` with the one line ``pattern`` matches replaced; none, or two, is refused.

    Two would mean the pattern does not say which line it means, and none that the file no
    longer states the version the package does - either way, a rewrite that guessed would
    publish spellings that disagree, which is what ``cmake/Ddd.cmake`` refuses.
    """
    rewritten, count = re.subn(pattern, lambda _: replacement, text, flags=re.MULTILINE)
    if count != 1:
        raise ValueError(f"{where}: {count} lines match {pattern}, and one is what is rewritten")
    return rewritten


def stamp(root: Path, run: str, commit: str) -> str:
    """Write the development version and the commit into the checkout at ``root``.

    Returns the version.  Everything is worked out before anything is written, and the project
    table is read back as toml first, so a refusal leaves the checkout as it found it.  The
    files are written with lf endings, which is what ``.gitattributes`` checks every file out
    with, on windows too.
    """
    if not (run.isascii() and run.isdecimal()):
        raise ValueError(f"the run number is a whole number, not {run!r}")
    if not COMMIT.fullmatch(commit):
        raise ValueError(f"the commit is the forty hexadecimal digits of its sha, not {commit!r}")
    package = root / "src" / "ddd" / "__init__.py"
    project = root / "pyproject.toml"
    module = root / "cmake" / "Ddd.cmake"
    texts = {path: path.read_text(encoding="utf-8") for path in (package, project, module)}
    stated = re.search(r'^__version__ = "([^"]*)"$', texts[package], flags=re.MULTILINE)
    if stated is None:
        raise ValueError(f"{package} states no __version__ to number a development build after")
    version = next_development(stated.group(1), int(run))
    urls = tomllib.loads(texts[project])["project"].get("urls", {})
    if "Homepage" not in urls:
        raise ValueError(f"{project} names no Homepage for the commit's url to be under")
    url = f"{urls['Homepage']}/commit/{commit}"
    current = re.escape(stated.group(1))
    rewritten = {
        package: replaced_once(
            texts[package], f'^__version__ = "{current}"$', f'__version__ = "{version}"', package
        ),
        project: replaced_once(
            replaced_once(
                texts[project], f'^version = "{current}"$', f'version = "{version}"', project
            ),
            r"^\[project\.urls\]$",
            f'[project.urls]\nCommit = "{url}"',
            project,
        ),
        module: replaced_once(
            texts[module],
            rf'^set\(DDD_MODULE_VERSION "{current}"\)$',
            f'set(DDD_MODULE_VERSION "{version}")',
            module,
        ),
    }
    metadata = tomllib.loads(rewritten[project])["project"]
    if (metadata["version"], metadata["urls"].get("Commit")) != (version, url):
        raise ValueError(f"{project} does not read back as {version}, built from {url}")
    for path, text in rewritten.items():
        path.write_text(text, encoding="utf-8", newline="\n")
    return version


def main(argv: Sequence[str] | None = None, root: Path = ROOT) -> int:
    """``stamp <run number> <commit>``; the exit code."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    try:
        match arguments:
            case ["stamp", run, commit]:
                print(stamp(root, run, commit))
            case _:
                print(f"usage: {Path(__file__).name} stamp <run number> <commit>", file=sys.stderr)
                return 2
    except ValueError as error:
        print(f"{Path(__file__).name}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
