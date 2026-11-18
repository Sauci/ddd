"""Check the ddd a release installs from the wheel it uploads, as whoever installs it meets it.

``.github/workflows/publish.yml`` builds the wheel it uploads, installs it into a fresh virtual
environment and runs this against that installation, before anything is uploaded. The one look
a release used to take at its artefact was a listing of the wheel's names for ``index.html``:
the wheel was never installed, so whatever only an installation shows - a path the package
works out, a file the wheel leaves behind, a dependency it does not declare - showed first on
the machine of whoever installed it. Each check runs the installed ``ddd`` as a program, in an
empty directory, and holds what it answers to the wheel itself:

* ``ddd --version`` answers ``ddd <version>``, the version the run publishes - on a release, its
  tag's - and the wheel's own metadata states that version too;
* ``ddd templates-dir`` answers a directory holding exactly the templates the wheel carries;
* ``ddd cmake-dir`` answers a directory whose ``Ddd.cmake`` is the wheel's, and that module
  states the version as ``DDD_MODULE_VERSION``, which it compares with what ``ddd --version``
  prints, refusing a ``ddd`` of any other;
* ``ddd gui`` starts, prints its address, and serves there the ``index.html`` the wheel carries.

It lives here, and not in the workflow, for the reason ``site_versions.py`` does: a rule nothing
can run is a rule nothing can check. ``tests/test_documentation.py`` runs it against the tool
itself.

Not part of the ``ddd`` package: it is release machinery, run by the runner's own python, and it
imports nothing of the installation it checks.
"""

from __future__ import annotations

import email
import http.client
import re
import subprocess
import sys
import tempfile
import threading
import urllib.request
import zipfile
from collections.abc import Sequence
from pathlib import Path

TIMEOUT = 60.0
"""Seconds each answer is waited for. A first run compiles the package's modules, which takes a
few; what this bounds is a hang."""

TEMPLATES = "ddd/templates/"
"""Where the wheel carries the example templates, which ``ddd templates-dir`` points at."""

MODULE = "ddd/cmake/Ddd.cmake"
"""Where the wheel carries the cmake module, in the directory ``ddd cmake-dir`` prints."""

PAGE = "ddd/gui/static/index.html"
"""The page ``ddd gui`` serves at its address, compiled into the wheel by the release build."""

SERVING = re.compile(r"ddd gui \(preview\) serving (http://127\.0\.0\.1:\d+/\S*)")
"""The line ``ddd gui`` prints on its standard output once it listens, naming its address."""


def carried(wheel: Path) -> tuple[str, dict[str, bytes]]:
    """The version a wheel's metadata states, and the files of it the checks compare with."""
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        metadata = [name for name in names if re.fullmatch(r"[^/]+\.dist-info/METADATA", name)]
        if len(metadata) != 1:
            raise ValueError(f"{wheel.name} holds {len(metadata)} METADATA files, and a wheel one")
        version = email.message_from_bytes(archive.read(metadata[0]))["Version"]
        files = {
            name: archive.read(name)
            for name in names
            if (name.startswith(TEMPLATES) or name in (MODULE, PAGE)) and not name.endswith("/")
        }
    if version is None:
        raise ValueError(f"the metadata of {wheel.name} states no version")
    return str(version), files


def answer(ddd: Sequence[str], where: Path, *arguments: str) -> tuple[str | None, str]:
    """What ``ddd <arguments>`` prints, run in ``where``; None and why, when it fails."""
    command = " ".join(("ddd", *arguments))
    try:
        done = subprocess.run(
            [*ddd, *arguments],
            cwd=where,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return None, f"{command} cannot be run: {error}"
    if done.returncode != 0:
        return None, f"{command} exits {done.returncode}, saying {done.stderr.strip()!r}"
    return done.stdout.strip(), ""


def listed(directory: Path) -> dict[str, bytes]:
    """Every file under ``directory``, by its path relative to it, with its bytes."""
    return {
        path.relative_to(directory).as_posix(): path.read_bytes()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def fetched(address: str) -> bytes:
    """The body ``ddd gui`` answers at ``address``, asked as a browser asks: following a redirect
    with the cookies it was given, and directly, since a proxy the environment names has no
    business with the loopback."""
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor()
    )
    with opener.open(address, timeout=TIMEOUT) as response:
        body: bytes = response.read()
    return body


def served(ddd: Sequence[str], where: Path, page: bytes) -> list[str]:
    """What is wrong with what ``ddd gui`` serves at the address it prints: nothing, for the page
    the wheel carries. The server is stopped before this returns."""
    with tempfile.TemporaryFile() as errors:
        try:
            process = subprocess.Popen(
                [*ddd, "gui", "--no-browser"],
                cwd=where,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=errors,
                encoding="utf-8",
                errors="replace",
            )
        except OSError as error:
            return [f"ddd gui cannot be run: {error}"]
        printed: list[str] = []

        def read_the_address() -> None:
            assert process.stdout is not None
            printed.append(process.stdout.readline())

        reader = threading.Thread(target=read_the_address, daemon=True)
        reader.start()
        reader.join(TIMEOUT)
        # What it had printed by now: once it is stopped below, the reader reads the end of its
        # output too, which would read as though it had exited by itself.
        line = printed[0].strip() if printed else None
        found: list[str] = []
        try:
            address = None if line is None else SERVING.fullmatch(line)
            if address is not None:
                try:
                    if fetched(address.group(1)) != page:
                        found.append(f"the page ddd gui serves is not the {PAGE} the wheel carries")
                except (OSError, http.client.HTTPException) as error:
                    found.append(f"ddd gui does not answer at the address it printed: {error}")
        finally:
            process.terminate()
            try:
                exit_code = process.wait(TIMEOUT)
            except subprocess.TimeoutExpired:
                process.kill()
                exit_code = process.wait()
            reader.join(TIMEOUT)
            assert process.stdout is not None
            process.stdout.close()
        if address is None:
            errors.seek(0)
            said = errors.read().decode("utf-8", errors="replace").strip()
            if line is None:
                why = f"printed no address within {TIMEOUT:g} seconds"
            elif not line:
                why = f"exits {exit_code} without printing its address"
            else:
                why = f"printed {line!r} where its address was to be"
            found.append(f"ddd gui {why}, saying {said!r}")
        return found


def problems(wheel: Path, version: str, ddd: Sequence[str]) -> list[str]:
    """What is wrong with the installation ``ddd`` runs, held to ``wheel`` and ``version``:
    nothing, for one that answers as the release it was installed from."""
    stated, files = carried(wheel)
    templates = {
        name.removeprefix(TEMPLATES): data
        for name, data in files.items()
        if name.startswith(TEMPLATES)
    }
    found = []
    if stated != version:
        found.append(f"the wheel states version {stated}, and the release is {version}")
    module = files.get(MODULE)
    stating = rf'^set\(DDD_MODULE_VERSION "{re.escape(version)}"\)$'.encode()
    if module is not None and not re.search(stating, module, re.MULTILINE):
        found.append(
            f"the wheel's {MODULE} does not state DDD_MODULE_VERSION {version}, so the module "
            f"refuses the ddd it is installed with"
        )
    with tempfile.TemporaryDirectory() as empty:
        where = Path(empty)
        said, why = answer(ddd, where, "--version")
        if said is None:
            found.append(why)
        elif said != f"ddd {version}":
            found.append(f"ddd --version answers {said!r}, and the release is {version}")
        said, why = answer(ddd, where, "templates-dir")
        if not templates:
            found.append(f"the wheel carries no templates under {TEMPLATES}")
        elif said is None:
            found.append(why)
        elif not Path(said).is_dir() or listed(Path(said)) != templates:
            found.append(
                f"ddd templates-dir answers {said!r}, which does not hold exactly the "
                f"{len(templates)} templates the wheel carries"
            )
        said, why = answer(ddd, where, "cmake-dir")
        if module is None:
            found.append(f"the wheel carries no {MODULE}")
        elif said is None:
            found.append(why)
        elif not (Path(said) / "Ddd.cmake").is_file():
            found.append(f"ddd cmake-dir answers {said!r}, which holds no Ddd.cmake")
        elif (Path(said) / "Ddd.cmake").read_bytes() != module:
            found.append(f"ddd cmake-dir answers {said!r}, whose Ddd.cmake is not the wheel's")
        page = files.get(PAGE)
        if page is None:
            found.append(f"the wheel carries no {PAGE}, so ddd gui has nothing to serve")
        else:
            found.extend(served(ddd, where, page))
    return found


def main(argv: Sequence[str] | None = None) -> int:
    """``<wheel> <version> <ddd> [<argument>...]``; the exit code. Each problem is printed as an
    error the runner annotates the step with, on a line of its own."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    match arguments:
        case [wheel, version, *ddd] if ddd:
            pass
        case _:
            print(
                f"usage: {Path(__file__).name} <wheel> <version> <ddd> [<argument>...]",
                file=sys.stderr,
            )
            return 2
    try:
        found = problems(Path(wheel), version, ddd)
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        found = [f"{wheel} cannot be read as a wheel: {error}"]
    for problem in found:
        print("::error::" + " ".join(problem.split()))
    if not found:
        print(f"{Path(wheel).name}, installed, answers as ddd {version}")
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())
