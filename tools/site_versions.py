"""Write the version index of the documentation site.

``.github/workflows/docs.yml`` calls this after it has copied the build it produced into the
directory that build owns.  The site keeps one directory per version, so the index has to be
rewritten from what is on disk rather than appended to: the menu on every page reads it,
including the pages of versions published long before this one.

It lives here, and not in the workflow, because it decides which version a reader arriving at
the root of the site lands on - and a decision nothing can run is a decision nothing can
check.  As a heredoc it crowned the newest tag whatever it was, so publishing ``v0.10.0rc1``
would have redirected the site at a release candidate and labelled it "(stable)" in the menu.
``tests/test_documentation.py`` pins the orderings that matter now.

Not part of the ``ddd`` package: it is release machinery, it ships in the sdist rather than in
the wheel, and nothing the tool does at run time reads it.
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Sequence
from pathlib import Path

# A version directory: `v` and the numbers, then whatever a prerelease adds after them.
VERSION = re.compile(r"v(\d+(?:\.\d+)*)(.*)")


def order(name: str) -> tuple[tuple[int, ...], bool, str]:
    """Sort key: newest first under ``reverse=True``, a prerelease behind its release.

    The numbers are compared as numbers, so ``v0.10.0`` is newer than ``v0.9.0`` where a
    string comparison would have it the other way round.  Having no suffix ranks above having
    one, which is what puts ``v0.10.0`` ahead of ``v0.10.0rc1``; between two prereleases of one
    version the suffix decides, so ``rc2`` precedes ``rc1``.

    A directory whose name is not a version sorts to the end rather than raising: the site is
    a branch anybody can push to, and one stray directory should not take the index down.
    """
    match = VERSION.fullmatch(name)
    if not match:
        return ((), False, name)
    numbers = tuple(int(part) for part in match.group(1).split("."))
    return (numbers, match.group(2) == "", match.group(2))


def is_a_release(name: str) -> bool:
    """Whether the tag names a release rather than a candidate for one.

    Everything after the numbers is what makes ``v0.10.0rc1`` a prerelease; the tag carries no
    other mark the site can read, and the GitHub flag saying so is not on disk here.
    """
    return re.fullmatch(r"v\d+(?:\.\d+)*", name) is not None


def published(site: Path) -> list[str]:
    """The version directories of the site, newest first."""
    return sorted(
        (entry.name for entry in site.iterdir() if entry.is_dir() and entry.name.startswith("v")),
        key=order,
        reverse=True,
    )


def stable_of(tags: Sequence[str]) -> str:
    """The version the root of the site redirects to, given the tags newest first.

    The newest *release*, which is not the newest tag: a reader arriving without a version in
    the url wants the one they can install and rely on, not a release candidate that happens
    to have been published last.  A candidate stays in the menu, under its own version.

    Before the first release there is nothing else to land on, so ``latest`` - master's own
    documentation - is where the root points, as it did before any tag existed.
    """
    return next((tag for tag in tags if is_a_release(tag)), "latest")


def redirect(stable: str) -> str:
    """The page at the root of the site: a meta refresh to the version worth landing on."""
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "  <head>\n"
        '    <meta charset="utf-8">\n'
        f'    <meta http-equiv="refresh" content="0; url=./{stable}/">\n'
        f'    <link rel="canonical" href="./{stable}/">\n'
        "    <title>DDD documentation</title>\n"
        "  </head>\n"
        "  <body>\n"
        f'    <p>Redirecting to <a href="./{stable}/">the {stable} documentation</a>.</p>\n'
        "  </body>\n"
        "</html>\n"
    )


def write_index(site: Path) -> str:
    """Rewrite ``versions.json`` and the root redirect; return the line the run prints."""
    tags = published(site)
    versions = (["latest"] if (site / "latest").is_dir() else []) + tags
    stable = stable_of(tags)
    (site / "versions.json").write_text(
        json.dumps({"stable": stable, "versions": versions}, indent=2) + "\n", encoding="utf-8"
    )
    (site / "index.html").write_text(redirect(stable), encoding="utf-8")
    return f"stable is {stable}, versions are {', '.join(versions)}"


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 1:
        print(f"usage: {Path(__file__).name} <site directory>", file=sys.stderr)
        return 2
    print(write_index(Path(arguments[0])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
