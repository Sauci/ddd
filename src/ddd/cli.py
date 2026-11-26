"""Command line interface of DDD."""

from __future__ import annotations

import argparse
import contextlib
import contextvars
import errno
import json
import os
import re
import sys
import unicodedata
from collections.abc import Callable, Iterator, Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ddd import __version__
from ddd.deliveries import Resolved, compare_deliveries, read_baseline, read_dictionary
from ddd.diagnostics import (
    CHECKS,
    STANDALONE_POLICY,
    DiagnosticBag,
    Location,
    Severity,
    SeverityPolicy,
    UnknownCheckError,
    where,
)
from ddd.names import (
    BUILT_IN_ARTEFACTS,
    BUILT_IN_GENERATED,
    BYTE_ORDERS,
    PLUGIN_NAME_PATTERN,
    SCHEMA_KINDS,
)

if TYPE_CHECKING:
    from pydantic import BaseModel

    from ddd.addresses import Placed
    from ddd.backends import Backend, ConditionalObject, GeneratedFile, WriteStatus
    from ddd.elf import Image
    from ddd.ir import Comparable, DataDictionary
    from ddd.plugins import Plugin

# Everything else this module needs is imported by the function that needs it, and the
# paragraph above says which few are not. `ddd --version` and `ddd --help` are answered by
# argparse before any handler runs, and a cmake configure step asks for the version once per
# project while a pre-commit hook asks per file; reaching ddd.models to answer either costs
# about a third of a second of pydantic building contracts the answer never looks at. The
# names argparse needs while it is still deciding what was asked for are in :mod:`ddd.names`,
# which imports nothing, and ddd.diagnostics comes with the package itself.

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 2
EXIT_INTERRUPTED = 130
"""What a shell reports for a command killed by SIGINT, and what Ctrl-C ends a run with.

Distinct from the findings and usage codes on purpose: a script that stops a long run by hand
must not read the result as a project with errors.
"""

CONST_INPUTS_REMOVED = (
    "--const-inputs was removed in 0.12.0: the header it wrote declared an input const while "
    "the input's definition is not const. C leaves such a pair of declarations undefined, so "
    "an optimising compiler may hand the reader a stale value. Generate the headers without it."
)

GENERATOR = f"ddd {__version__}"

_FORMAT_HELP = "output format"
"""What ``--format`` says on a command whose whole output it chooses.

``dump`` says something else: there stdout is the dictionary in either format and the switch
reaches the diagnostics on stderr alone, so "output format" would read as a promise about the
document a build archives.
"""

_PYELFTOOLS_MISSING = (
    "reading an ELF image needs pyelftools, which is not installed: "
    "pip install 'pyelftools>=0.32,<1'"
)
"""The usage error a command reading an image answers without pyelftools: ``ddd tool from-elf``,
and ``ddd generate`` given ``--image``. It is a dependency, so only a broken installation lacks
it, and the command says how to mend one rather than raising."""


def _image_reader() -> Callable[[Path], Image]:
    """:func:`ddd.elf.open_image`, for a command about to read an image.

    The one place a missing pyelftools becomes the usage error :data:`_PYELFTOOLS_MISSING`
    rather than a traceback: ``ddd tool from-elf`` asks for it, and ``ddd generate`` given
    ``--image``. Imported on that call and not before, like everything else this module needs,
    so that no other run pays for pyelftools or needs it.
    """
    try:
        from ddd.elf import open_image
    except ModuleNotFoundError as error:
        # The name is the module the import stopped at - `elftools.common` as often as
        # `elftools` - so the package decides, not the whole name.
        if (error.name or "").partition(".")[0] != "elftools":
            raise
        raise ValueError(_PYELFTOOLS_MISSING) from None
    return open_image


def cmake_module_directory() -> Path | None:
    """Directory holding ``Ddd.cmake``, inside the installed package or in a source checkout."""
    candidates = (Path(__file__).parent / "cmake", Path(__file__).resolve().parents[2] / "cmake")
    return next((path for path in candidates if (path / "Ddd.cmake").is_file()), None)


def _write_utf8(stream: Any) -> None:
    """Make a stream carry utf-8, whatever the console happens to be set to.

    A description may hold any unit or any language, and on Windows a redirected stdout
    defaults to the ANSI codepage: a degree sign in a unit would end the run with a codec
    error instead of a listing. The generated files are utf-8 too, so this only makes the
    terminal agree with them.
    """
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is not None:
        with contextlib.suppress(OSError, ValueError):
            reconfigure(encoding="utf-8")


class _Watched:
    """A standard stream while :func:`main` runs, noting a reader that went away.

    A closed pipe is a write the system refuses because nothing reads the other end any more,
    and the exception says only that, not which stream it was: the stream that met it knows, at
    its own write or flush, and nothing else does. Windows refuses that write with ``EINVAL``, a
    plain :class:`OSError` that reads as an invalid argument; from a stream's own write or flush
    it is the closed pipe, raised as the :class:`BrokenPipeError` it is, while an ``EINVAL`` of
    anything else still means what it says. Everything but a write and a flush is the stream's.
    """

    def __init__(self, stream: Any) -> None:
        self.stream = stream
        self.lost_its_reader = False

    def write(self, text: str) -> Any:
        try:
            return self.stream.write(text)
        except OSError as error:
            self._met(error)
            raise

    def flush(self) -> None:
        # A stream with no flush has nothing to flush: `None`, which a descriptor closed before
        # the interpreter started leaves, or a test's that is only the buffer a server reads.
        flush = getattr(self.stream, "flush", None)
        if flush is None:
            return
        try:
            flush()
        except OSError as error:
            self._met(error)
            raise

    def _met(self, error: OSError) -> None:
        if isinstance(error, BrokenPipeError):
            self.lost_its_reader = True
        elif sys.platform == "win32" and error.errno == errno.EINVAL:
            self.lost_its_reader = True
            raise BrokenPipeError(errno.EPIPE, os.strerror(errno.EPIPE)) from error

    def __getattr__(self, name: str) -> Any:
        return getattr(self.stream, name)


@contextlib.contextmanager
def _watching() -> Iterator[tuple[_Watched, _Watched]]:
    """Both standard streams, each a :class:`_Watched` of itself while the run lasts.

    Given back as the run ends, flushed first. Python flushes both once more as the interpreter
    ends, past every clause of :func:`main`, and a stream that still points at a pipe whose
    reader went away fails there again: ``Exception ignored``, and an exit code of 120 in place
    of the run's own. So once either has lost its reader both are pointed at the null device,
    the recipe python's own documentation gives, and what they still hold goes nowhere. A stream
    that is ``None`` stays ``None``, which a ``print`` writes nothing to already.
    """
    given = sys.stdout, sys.stderr
    watched = _Watched(given[0]), _Watched(given[1])
    sys.stdout, sys.stderr = (
        None if stream is None else watch for stream, watch in zip(given, watched, strict=True)
    )
    try:
        yield watched
    finally:
        for watch in watched:
            with contextlib.suppress(OSError, ValueError):
                watch.flush()
        if any(watch.lost_its_reader for watch in watched):
            null = os.open(os.devnull, os.O_WRONLY)
            for stream in given:
                # A stream with no descriptor - `None`, a test's capture - has none to point.
                with contextlib.suppress(AttributeError, OSError, ValueError):
                    os.dup2(null, stream.fileno())
            os.close(null)
        sys.stdout, sys.stderr = given


def _flush(*streams: _Watched) -> None:
    """Flush each in turn, raising what the first to fail met."""
    for stream in streams:
        stream.flush()


_VERDICT: contextvars.ContextVar[int] = contextvars.ContextVar("verdict", default=EXIT_OK)
"""The code the command that runs decided it ends at, for :func:`main` to end a run at when its
output meets a closed pipe."""


def _verdict(code: int) -> int:
    """Decide that the run ends at ``code``, and return it.

    Called before the command prints anything that can meet a closed pipe - its report, its
    listing, its dictionary - so that a reader who stops early takes nothing of the verdict with
    them: ``ddd check p --format json | head -1`` still fails a project with errors under
    ``set -o pipefail``. A command that judges nothing decides nothing, and ends at 0.
    """
    _VERDICT.set(code)
    return code


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point of the ``ddd`` command; returns the process exit code."""
    _write_utf8(sys.stdout)
    _write_utf8(sys.stderr)
    arguments = list(sys.argv[1:] if argv is None else argv)
    parser = _build_parser(_plugin_artefact(arguments))
    _VERDICT.set(EXIT_OK)
    with _watching() as watched:
        try:
            try:
                args = parser.parse_args(arguments)
                handler: Any = args.handler
                code = int(handler(args))
            except SystemExit:
                # `--version`, `--help` and a command line argparse refuses itself: it printed
                # and left, and what it printed is flushed here as well.
                _flush(*watched)
                raise
            # Flushed inside the run, so that a closed pipe met by what is still buffered is
            # answered by the clauses below; flushed as the interpreter ended, it met none.
            _flush(*watched)
            return code
        except KeyboardInterrupt:
            # Ctrl-C during a long run, or during a plugin's hook, which re-raises it rather than
            # blaming the plugin for it. One line instead of the thirty a traceback costs, and a
            # code of its own so that a caller does not read a stopped run as a failed check.
            print("ddd: interrupted", file=sys.stderr)
            return EXIT_INTERRUPTED
        except BrokenPipeError:
            # `ddd schema component | head -1`: the reader stopped reading, which is what a pager
            # and `head` do, and nothing about it is this run's error - reported as a usage error
            # it failed a paging script on the tool's side under `set -o pipefail`. Nor does it
            # say anything of the project: the run ends at what its command decided before it
            # printed (`_verdict`), so a check that found errors fails however early its reader
            # stopped. A stderr that lost its reader is never 0, since the report owed there was
            # not made: 1 where an error stands to say so, and 2 where none does. What either
            # stream still holds goes to the null device as the run ends (`_watching`).
            verdict = _VERDICT.get()
            stderr = watched[1]
            if stderr.lost_its_reader and verdict != EXIT_FINDINGS:
                return EXIT_USAGE
            return verdict
        except UnknownCheckError as error:
            # UnknownCheckError is a ValueError, listed first only to keep its own wording apart
            # from the clause below; being one, `_reported_on_failure` already covers it too.
            print(f"ddd: {error}", file=sys.stderr)
            return EXIT_USAGE
        except (OSError, ValueError) as error:
            print(f"ddd: {error}", file=sys.stderr)
            return EXIT_USAGE


def _plugin_artefact(arguments: Sequence[str]) -> str | None:
    """The artefact of a ``ddd generate`` run that is not a built-in one, off the raw arguments.

    argparse wants every subcommand registered before it parses, and the plugins that provide
    an artefact are known only once the project is read - which is itself an argument. So the
    name is read here and registered as a subcommand of its own; whether a plugin provides it
    is decided after the project is loaded, as a usage error naming what the project does
    provide.
    """
    if len(arguments) >= 2 and arguments[0] == "generate":
        name = arguments[1]
        if name not in BUILT_IN_ARTEFACTS and re.fullmatch(PLUGIN_NAME_PATTERN, name):
            return name
    return None


class _Parser(argparse.ArgumentParser):
    """A parser that spells its options out, for this command and every subcommand of it.

    argparse accepts any unambiguous prefix of a long option by default, so ``--stand`` and
    ``--dict`` were as good as ``--standalone`` and ``--dictionary`` - until a second option
    starting with those letters is added, and every script that took the offer breaks with
    argparse's "ambiguous option" as its only clue. What a command accepts is part of the
    tool's interface ([the changelog's preamble]); what it happens not to be ambiguous about
    today is not, and an abbreviation nobody published is not worth that trap.

    A subcommand is a parser of its own, built by ``add_parser`` from the class of the parser
    that owns the subparsers rather than from its settings, so ``allow_abbrev`` has to be
    carried by the class to reach ``ddd check --standalone`` and the options of an artefact.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(allow_abbrev=False, **kwargs)


def _build_parser(plugin_artefact: str | None = None) -> argparse.ArgumentParser:
    parser = _Parser(
        prog="ddd",
        description=(
            "Data dictionary for the global variables of a component based "
            "embedded software project."
        ),
    )
    parser.add_argument("-v", "--version", action="version", version=f"ddd {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser(
        "check",
        help="verify the consistency of the interfaces of a project",
        description=(
            "Verifies the consistency of the interfaces of a project. A project's plugins "
            "run: every module the project names is imported, unless --no-plugins is given."
        ),
    )
    _add_common_arguments(check)
    check.add_argument(
        "--baseline",
        type=Path,
        help="also verify that the project can still replace this published dictionary",
    )
    _add_standalone_argument(check, "check")
    _add_no_plugins_argument(
        check, "; with --baseline, the baseline's too, reported as the baseline's"
    )
    check.set_defaults(handler=_command_check)

    compare_parser = subparsers.add_parser(
        "compare",
        help="report whether one delivery can replace another",
        description=(
            "Compares two data dictionaries, or two project descriptions, or one of each. "
            "The question is directional: can CANDIDATE stand in for BASELINE?"
        ),
    )
    compare_parser.add_argument("baseline", type=Path, help="the published dictionary or project")
    compare_parser.add_argument("candidate", type=Path, help="the delivery to judge")
    compare_parser.add_argument(
        "--renames",
        type=Path,
        help="also write the old-to-new name pairs here, for migrating datasets and recordings",
    )
    _add_plugin_argument(compare_parser)
    _add_no_plugins_argument(
        compare_parser,
        "; a description on either side runs none, the baseline's reported as the baseline's, "
        "and --plugin is refused beside it",
    )
    _add_policy_arguments(compare_parser)
    compare_parser.set_defaults(handler=_command_compare)

    generate = subparsers.add_parser(
        "generate",
        help="generate the c sources and the a2l file of a project",
        description=(
            "Generates the artefacts of a project, each out of the same resolved data "
            "dictionary. The artefact is part of the command, so every run states what it "
            "produces and carries only the options of that artefact: only a run that "
            "renders c takes a template directory, only one that writes the a2l takes an "
            "address map or an image. 'all' produces both, and the artefact of every plugin "
            "the project names that provides one, and takes --without to leave one of the "
            "built-in artefacts out of that; 'a2l' is the run a build repeats "
            "after linking, when the addresses are known but the c must not change."
        ),
    )
    # One subparser per artefact rather than steering flags on a single command: the two
    # backends do not want the same options, and a flag pair like --no-a2l/--a2l-only would
    # leave every run carrying the other backend's options as noise it must not use.
    artefacts = generate.add_subparsers(
        dest="artefact", required=True, metavar="{c,a2l,all,<plugin>}"
    )
    for name, description, with_c, with_a2l, with_plugins in (
        ("c", "render the c sources from the project's jinja2 templates", True, False, False),
        (
            "a2l",
            "write the a2l file, with the addresses --address-map or --image gives",
            False,
            True,
            False,
        ),
        (
            "all",
            "render the c sources, write the a2l file and produce the plugins' artefacts",
            True,
            True,
            True,
        ),
    ):
        _add_generate_arguments(
            artefacts.add_parser(name, help=description),
            with_c=with_c,
            with_a2l=with_a2l,
            with_plugins=with_plugins,
            # Only a run composing several artefacts has anything to subtract, and 'all' is
            # the only one there is.
            with_exclusions=with_plugins,
        )
    if plugin_artefact is not None:
        extra = artefacts.add_parser(
            plugin_artefact, help="write the artefact the plugin of that name provides"
        )
        _add_generate_arguments(extra, with_c=False, with_a2l=False)
        extra.set_defaults(plugin_artefact=plugin_artefact)

    listing = subparsers.add_parser("list", help="list the global variables of a project")
    _add_common_arguments(listing)
    _add_standalone_argument(listing, "list")
    _add_no_plugins_argument(listing)
    listing.set_defaults(handler=_command_list)

    dump = subparsers.add_parser(
        "dump", help="print the resolved data dictionary, the contract the backends consume"
    )
    _add_common_arguments(
        dump,
        format_help=(
            "format of the diagnostics, which go to stderr on this command; the dictionary "
            "is json either way"
        ),
    )
    dump.add_argument(
        "-o",
        "--output",
        type=Path,
        help=(
            "write the dictionary to this file instead of stdout, leaving the file untouched "
            "when its content would not change"
        ),
    )
    _add_standalone_argument(dump, "dump")
    _add_no_plugins_argument(dump)
    dump.set_defaults(handler=_command_dump)

    identity = subparsers.add_parser(
        "id",
        help="write an identity into every producing declaration that has none",
        description=(
            "Stamps an 'id' into each declaration of scope 'output' or 'local' that does "
            "not carry one, editing the files in place. An identity is what lets a later "
            "'ddd compare' report a rename as a rename. A declaration that already has one "
            "is left alone, so a second run changes nothing."
        ),
    )
    identity.add_argument("files", type=Path, nargs="+", help="the description files to stamp")
    identity.add_argument(
        "--assign",
        action="store_true",
        required=True,
        help="write the ids; required, so that no run edits a file by accident",
    )
    identity.set_defaults(handler=_command_id)

    lsp = subparsers.add_parser(
        "lsp",
        help="run the language server, so an editor can report what a build reports",
        description=(
            "Speaks the Language Server Protocol on stdin and stdout. It reports the "
            "consistency checks while a description file is being written, which a json "
            "schema cannot do: whether an axis names a declared axis, whether exactly one "
            "component produces a name, whether two components agree on a unit. Which "
            "project a file belongs to is read from the 'ddd-build.json' that "
            "ddd_generate writes, so the editor and the build apply the same severities."
        ),
    )
    lsp.add_argument(
        "-b",
        "--build-directory",
        type=Path,
        action="append",
        default=[],
        metavar="DIR",
        help=(
            "directory holding a build of this project; repeatable. A relative one is read "
            "against each workspace folder, and without one the usual build directory names "
            "are searched in each, the directory the server is started in standing for the "
            "folders while the editor names none"
        ),
    )
    _add_no_plugins_argument(lsp, "; at every read the server makes")
    lsp.set_defaults(handler=_command_lsp)

    gui = subparsers.add_parser(
        "gui",
        help=(
            "preview: edit a project's description files in a browser, on this computer by default"
        ),
        description=(
            "Preview. Serves a browser interface over one project's description files, and "
            "opens the browser on it. The server binds the loopback address of this computer "
            "alone by default; --host widens that, for a container. Every change is written "
            "into the description files in their own layout and checked with the same "
            "analysis as ddd check. It runs until it is interrupted, and its options are not "
            "yet part of the stable interface."
        ),
    )
    gui.add_argument(
        "project",
        nargs="?",
        type=Path,
        metavar="PROJECT",
        help=(
            "the project description to open; without it the start page lists the projects "
            "found under the current directory"
        ),
    )
    gui.add_argument(
        "-b",
        "--build-directory",
        type=Path,
        action="append",
        default=[],
        metavar="DIR",
        help=(
            "directory holding a build of the project, whose severities apply; repeatable. "
            "Without it the usual build directory names are searched"
        ),
    )
    gui.add_argument(
        "--host",
        default="127.0.0.1",
        metavar="ADDRESS",
        help=(
            "IPv4 address to listen on: 127.0.0.1, the default, which answers this computer "
            "alone, or 0.0.0.0, every interface, which a container gives its host once the same "
            "port is published - or a name that resolves to one of the two; any other is refused"
        ),
    )
    gui.add_argument(
        "--port",
        type=_port,
        default=0,
        metavar="N",
        help=(
            "port to serve on; the default, 0, lets the system pick a free one, refused "
            "when --host answers beyond this computer's loopback"
        ),
    )
    gui.add_argument(
        "--no-browser",
        action="store_true",
        help="print the address without opening a browser on it",
    )
    gui.set_defaults(handler=_command_gui)

    build_info = subparsers.add_parser(
        "build-info",
        help="record how a build configured DDD, for the language server and ddd gui to pick up",
        description=(
            "Writes the project description a build runs DDD on, and the severity policy it "
            "applies, into a small json file. A build system calls this at configure time so "
            "that the language server and ddd gui can report what the build reports. The "
            "project description is recorded rather than read: with CMake it is often "
            "generated later in the same configure run, out of the link graph."
        ),
    )
    build_info.add_argument("project", type=Path, help="project or component description file")
    build_info.add_argument(
        "-o", "--output", type=Path, required=True, help="file to write the result to"
    )
    build_info.add_argument("--image", default="", help="name of the build target this belongs to")
    build_info.add_argument(
        "--origin",
        choices=("collected", "given"),
        default="collected",
        help=(
            "where the project description came from: 'given' to the build as a file somebody "
            "wrote, which stamps the record format 2 and which ddd gui then edits, or "
            "'collected' by the build out of the link closure of the image, written again at "
            "every configure (the default), which ddd gui refuses to write into"
        ),
    )
    build_info.add_argument(
        "-W",
        "--severity",
        action="append",
        default=[],
        metavar="CHECK=SEVERITY",
        help="severity override the build applies; repeatable",
    )
    build_info.add_argument(
        "--strict", action="store_true", help="the build reports warnings as errors"
    )
    build_info.set_defaults(handler=_command_build_info)

    schema = subparsers.add_parser(
        "schema",
        help="print the json schema of a file format",
        description=(
            "Prints the json schema of one file format, or writes every schema into a "
            "directory with 'all'. Committing those files and pointing the '$schema' key of "
            "each description at the matching one is what gives an editor completion, hover "
            "documentation and validation while a description file is being written."
        ),
    )
    schema.add_argument("kind", choices=[*SCHEMA_KINDS, SCHEMA_ALL])
    schema.add_argument(
        "-o",
        "--output",
        type=Path,
        help=(
            "write to this file instead of stdout; with 'all' it is the directory the "
            f"schemas are written into, each named '{SCHEMA_FILENAME.format(kind='<kind>')}'"
        ),
    )
    _add_plugin_argument(schema)
    schema.set_defaults(handler=_command_schema)

    artefact_listing = subparsers.add_parser(
        "artefacts",
        help="list the artefacts a project can generate",
        description=(
            "Prints the artefacts 'ddd generate' accepts for this project: the built-in "
            "'c' and 'a2l', and the name of every plugin the project names that provides "
            "one. What each artefact writes is not listed here, because a plugin's file "
            "names follow from the resolved project rather than from the plugin alone; "
            "'ddd generate all --dry-run' reports those. A plugin providing no backend is "
            "no artefact of its own, and is named in a note rather than passed over: its "
            "block is still part of what the project's templates render under 'c'. Named "
            "with --plugin instead of a project, it answers the same question for a build "
            "that has not assembled its project description yet."
        ),
    )
    artefact_listing.add_argument(
        "project", type=Path, nargs="?", help="project or component description file"
    )
    _add_plugin_argument(artefact_listing)
    artefact_listing.add_argument(
        "--format", choices=["text", "json"], default="text", help="output format"
    )
    artefact_listing.set_defaults(handler=_command_artefacts)

    sources = subparsers.add_parser(
        "sources",
        help="list every file a project is built out of, its plugins' modules included",
        description=(
            "Prints one absolute path per line: the project file, every file it includes "
            "however deeply, and the module of every plugin those files name. A build system "
            "needs exactly this "
            "to know when the generated files are out of date, because a project pulls its "
            "components in through 'includes' and names its plugins under 'plugins', and "
            "none of them is named on the command line."
        ),
    )
    sources.add_argument("project", type=Path, help="project or component description file")
    sources.add_argument("--format", choices=["text", "json"], default="text", help="output format")
    sources.add_argument(
        "-W",
        "--severity",
        action="append",
        default=[],
        metavar="CHECK=SEVERITY",
        help="change the severity of a check the findings are reported with; repeatable",
    )
    sources.add_argument(
        "--strict", action="store_true", help="report warnings as errors, as the build does"
    )
    _add_no_plugins_argument(
        sources,
        "; a plugin named by a dotted module name is then left out of the listing, since locating "
        "its file imports the packages above it",
    )
    sources.set_defaults(handler=_command_sources)

    checks = subparsers.add_parser("checks", help="list the available consistency checks")
    checks.add_argument("--format", choices=["text", "json"], default="text", help="output format")
    _add_plugin_argument(checks)
    checks.set_defaults(handler=_command_checks)

    cmake = subparsers.add_parser(
        "cmake-dir", help="print the directory containing the cmake integration module"
    )
    cmake.set_defaults(handler=_command_cmake_dir)

    templates = subparsers.add_parser(
        "templates-dir",
        help="print the directory containing the example c templates",
        description=(
            "The c sources are rendered from templates the project provides, so that their "
            "house style is the project's own. The templates printed here are a working set "
            "to copy into a project and change, not a default: nothing falls back to them."
        ),
    )
    templates.set_defaults(handler=_command_templates_dir)

    tool = subparsers.add_parser(
        "tool",
        help="run a tool of the toolbox, used once on the way into DDD or out of it",
        description=(
            "The toolbox holds what is run once rather than in every build: a tool that turns "
            "something a project already has into DDD descriptions, or DDD descriptions into "
            "something else. Each tool is a command of its own under this one."
        ),
    )
    # No metavar: argparse then spells the tools out, so that `ddd tool` alone lists them, as
    # `ddd` alone lists its commands.
    tools = tool.add_subparsers(dest="tool", required=True)
    from_elf = tools.add_parser(
        "from-elf",
        help="print the DDD declarations of C variables a linked ELF image describes",
        description=(
            "Reads a linked ELF image and its DWARF debug information, and prints as json the "
            "declaration of every C variable named or matched: its kind, datatype, shape, "
            "enumerators, structure members, initial value and section, as the image states "
            "them. What an image does not state - a unit, a description, limits, a scaling, "
            "whether an array is a curve, whether a raw value is the physical one - is left out, "
            "and said once. DDD itself checks every "
            "entry, as 'ddd check --standalone' checks a component, before it is printed. "
            "Needs an image built with debug information (-g)."
        ),
    )
    from_elf.add_argument(
        "image", type=Path, help="the linked ELF image, built with debug information (-g)"
    )
    from_elf.add_argument(
        "symbols",
        nargs="+",
        metavar="SYMBOL",
        help=(
            "a C variable, by name or by a pattern in shell glob syntax, prefixed with UNIT: "
            "to take it from one compilation unit, for a static several units define"
        ),
    )
    from_elf.add_argument(
        "--component",
        metavar="NAME",
        help=(
            "print a component file of this name, holding the types its structures need, "
            "rather than a list of interface entries"
        ),
    )
    from_elf.add_argument(
        "--identity-conversions",
        action="store_true",
        help=(
            "write the identity as the conversion of every entry and member that is not an "
            "enum, on your word that its raw value is its physical one: an image does not say "
            "so, so by default no conversion is written, and 'ddd check' asks the author for "
            "one"
        ),
    )
    from_elf.add_argument(
        "--scope",
        choices=["output", "local", "input"],
        default="output",
        help=(
            "the scope of every entry; input leaves out the initial value and the section, "
            "which a consumer does not state"
        ),
    )
    from_elf.add_argument(
        "-o",
        "--output",
        type=Path,
        help=(
            "write the declarations to this file instead of stdout, leaving the file untouched "
            "when its content would not change"
        ),
    )
    from_elf.add_argument(
        "--force",
        action="store_true",
        help=(
            "write the declarations that were described even where others were not; the exit "
            "code still reports the errors"
        ),
    )
    from_elf.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help=(
            "format of the diagnostics, which go to stderr on this command; the declarations "
            "are json either way"
        ),
    )
    from_elf.set_defaults(handler=_command_tool_from_elf)

    return parser


def _add_common_arguments(
    parser: argparse.ArgumentParser, *, format_help: str = _FORMAT_HELP
) -> None:
    parser.add_argument("project", type=Path, help="project or component description file")
    _add_policy_arguments(parser, format_help=format_help)


def _add_generate_arguments(
    parser: argparse.ArgumentParser,
    *,
    with_c: bool,
    with_a2l: bool,
    with_plugins: bool = False,
    with_exclusions: bool = False,
) -> None:
    """The options of one ``generate`` artefact; only the selected backends contribute any.

    A plugin's backend takes no option of its own, so ``with_plugins`` adds none: it only says
    that the run produces the plugins' artefacts after the built-in ones, which is what ``all``
    means and no other artefact does.
    """
    _add_common_arguments(parser)
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        required=True,
        help="directory the generated files are written to",
    )
    if with_c:
        parser.add_argument(
            "-t",
            "--template-dir",
            type=Path,
            # Required wherever c is rendered, but on the artefact that can subtract the c it
            # cannot be enforced here: --without c is read after parsing, so _selected() below
            # asks for it only once it knows the c survived.
            required=not with_exclusions,
            # No reStructuredText inline markup in this text: the documentation inserts every
            # help string into a page as markup, where a lone asterisk opens an emphasis that
            # never closes. See test_no_help_string_carries_markup_characters.
            help=(
                "directory holding the jinja2 templates of the c sources. Every file in it "
                "ending in .jinja2 is rendered to a file named like the template without that "
                "extension, so ddd_globals.c.jinja2 produces ddd_globals.c; a name starting "
                "with an underscore is a helper that renders nothing on its own, and a name "
                "containing {component} is rendered once per component. 'ddd templates-dir' "
                "prints a set of example templates to copy from"
            ),
        )
        parser.add_argument(
            "--const-inputs",
            action="store_true",
            # Parsed only so that it can be refused in a sentence of its own; see _selected.
            help=argparse.SUPPRESS,
        )
    if with_a2l:
        parser.add_argument(
            "--byte-order",
            choices=list(BYTE_ORDERS),
            # No default here: the handler resolves it, so that a run which subtracted the a2l
            # can tell an option it must refuse from one the parser filled in.
            default=None,
            help=(
                f"byte order reported in the a2l file, default: {BYTE_ORDERS[0]}, or the "
                "image's with --image"
            ),
        )
        parser.add_argument(
            "--address-map",
            type=Path,
            help="json file mapping variable names to their address in the target",
        )
        parser.add_argument(
            "--image",
            type=Path,
            help=(
                "linked ELF image whose DWARF debug information gives every address the a2l "
                "carries, and its byte order"
            ),
        )
        parser.add_argument(
            "--a2l-module-fragment",
            type=Path,
            metavar="FILE",
            help=(
                "text file pasted verbatim at the head of the a2l's MODULE: what the a2l cannot "
                "state itself, such as the A2ML its IF_DATA are written in, and, where the "
                "project declares no named constant, a MOD_PAR carrying EPK, ADDR_EPK and "
                "MEMORY_SEGMENT"
            ),
        )
    if with_exclusions:
        parser.add_argument(
            "--without",
            action="append",
            choices=list(BUILT_IN_GENERATED),
            default=[],
            help=(
                "leave one of the built-in artefacts out of this run, repeatable. The plugins' "
                "artefacts are produced either way, so 'generate all --without a2l' is how a "
                "build that writes the a2l later, once the addresses are known, asks for "
                "everything else"
            ),
        )
    parser.add_argument(
        "--dictionary",
        type=Path,
        metavar="FILE",
        help=(
            "also write the resolved data dictionary, the text ddd dump prints, to this file, in "
            "the same write as the artefacts: all of them or none"
        ),
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="report what would be written, write nothing"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "generate in spite of the errors of the analysis; a file that cannot be read or "
            "checked against its format leaves nothing to generate"
        ),
    )
    parser.set_defaults(
        handler=_command_generate,
        render_c=with_c,
        render_a2l=with_a2l,
        render_plugins=with_plugins,
    )


def _add_policy_arguments(
    parser: argparse.ArgumentParser, *, format_help: str = _FORMAT_HELP
) -> None:
    parser.add_argument(
        "-W",
        "--severity",
        action="append",
        default=[],
        metavar="CHECK=SEVERITY",
        help="change the severity of a check (error, warning, info, ignore); repeatable",
    )
    parser.add_argument("--strict", action="store_true", help="report warnings as errors")
    parser.add_argument("--format", choices=["text", "json"], default="text", help=format_help)


def _add_standalone_argument(parser: argparse.ArgumentParser, verb: str) -> None:
    """``--standalone``, spelled once for every command a component may be handed to alone."""
    parser.add_argument(
        "--standalone",
        action="store_true",
        help=(
            f"{verb} a component on its own: hold back the checks that need every component "
            "of a project, as the editor does for a file no build claims; -W still applies"
        ),
    )


def _add_no_plugins_argument(parser: argparse.ArgumentParser, more: str = "") -> None:
    """``--no-plugins``, spelled once for every command that reads a project without needing what
    its plugins do; ``more`` is what the command says of it beyond that."""
    parser.add_argument(
        "--no-plugins",
        action="store_true",
        help=(
            "import none of the plugins the project names, reporting each as plugin-skipped, a "
            f"warning: its checks do not run and its blocks are not validated{more}"
        ),
    )


def _add_plugin_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--plugin",
        action="append",
        default=[],
        metavar="MODULE",
        help=(
            "load this plugin, a .py path relative to the working directory or a module "
            "name; repeatable. For a run that reads no project description, which names "
            "its own plugins"
        ),
    )


def _verify_overrides(bag: DiagnosticBag, plugins: Sequence[Plugin] = ()) -> None:
    """Hold every ``-W`` naming a plugin's check to the checks the run's plugins register.

    ``plugins`` are the ones whose checks are not on the bag already: a baseline's, which ran
    on a bag of its own. Their checks are checks this run knows - an override naming one of
    them, ``-W layout/removed-entry=ignore`` beside the ``missing-plugin`` the same run
    reports about that plugin, was refused as naming a check no loaded plugin registers,
    which is the opposite of what happened. Registered only where nothing has claimed the
    identifier yet: a check both sides declare keeps the candidate's own, because the
    candidate's plugins are the ones that report through this bag. While a plugin the run names
    was skipped (``--no-plugins``, :attr:`~ddd.diagnostics.DiagnosticBag.skipped`), which checks
    it registers is not known, and the override is accepted unverified.
    """
    for plugin in plugins:
        bag.register(info for info in plugin.checks if info.identifier not in bag.registered)
    bag.policy.verify(bag.registered, bag.skipped)


def _plugins_from_arguments(
    specs: Sequence[str], bag: DiagnosticBag | None = None
) -> tuple[Plugin, ...]:
    """The plugins ``--plugin`` names, loaded relative to the working directory.

    A failure is a usage error rather than a finding: there is no project file to locate it
    in, and the mistake is on the command line. The checks are registered on ``bag`` when
    one is given, so that a provisional override can be verified against them.
    """
    from ddd.plugins import PluginInvalidError, PluginNotFoundError, load_plugin

    plugins: list[Plugin] = []
    for spelling in specs:
        try:
            plugin = load_plugin(spelling, Path.cwd())
        except (PluginNotFoundError, PluginInvalidError) as error:
            raise ValueError(str(error)) from None
        known = next((entry for entry in plugins if entry.name == plugin.name), None)
        if known is plugin:
            continue
        if known is not None:
            msg = f"plugin '{plugin.name}' is named twice by --plugin, by different modules"
            raise ValueError(msg)
        plugins.append(plugin)
        if bag is not None:
            bag.register(plugin.checks)
    return tuple(plugins)


def _command_check(args: argparse.Namespace) -> int:
    # The plugins of a run with a baseline include the baseline's own - loaded for its
    # analysis, on a bag of its own - and those are known only once it has been read. So a
    # `-W` naming a plugin's check is verified below rather than at the end of the analysis,
    # which is where a run without a baseline verifies it.
    resolved, bag = _analyze(args, verify=args.baseline is None)
    dictionary = resolved.dictionary if resolved is not None else None
    # With a baseline, one command answers both questions and returns one exit code, which
    # is what a ci job wants: is the project consistent, and is it still a replacement?
    if args.baseline is not None:
        with _reported_on_failure(bag, args.format):
            # Not read at all when the project did not resolve: its errors are what this run
            # has to say, and a comparison against them would say nothing. The overrides are
            # still held to what did load, so a typo is reported by the run that made it.
            baseline = (
                read_baseline(
                    args.baseline,
                    bag,
                    getattr(args, "standalone", False),
                    run_plugins=not args.no_plugins,
                )
                if resolved is not None
                else None
            )
            _verify_overrides(bag, () if baseline is None else baseline.plugins)
            if resolved is not None and baseline is not None:
                compare_deliveries(
                    baseline,
                    resolved,
                    bag,
                    location=where(args.project),
                    baseline_location=where(args.baseline),
                )
    code = _verdict(EXIT_FINDINGS if bag.has_errors else EXIT_OK)
    _report(bag, args.format)
    if args.format == "json":
        return code
    if dictionary is not None and not len(bag):
        count = len(dictionary.listed)
        components = len(dictionary.components)
        print(
            f"ok: {count} variable{'s' if count != 1 else ''} in "
            f"{components} component{'s' if components != 1 else ''} "
            f"{'is' if count == 1 else 'are'} consistent",
            file=sys.stderr,
        )
    return code


def _command_compare(args: argparse.Namespace) -> int:
    from ddd.compare import renames

    if args.plugin and args.no_plugins:
        msg = "--plugin cannot be given together with --no-plugins, which runs no plugin"
        raise ValueError(msg)
    policy = SeverityPolicy.from_strings(args.severity, strict=args.strict)
    bag = DiagnosticBag(policy)
    # The baseline is a delivery that has already gone out; its own findings are not this
    # run's business. The candidate's are, which is why only it shares the bag - checking a
    # project description and comparing it are both reported by one `ddd compare`.
    with _reported_on_failure(bag, args.format):
        baseline = read_baseline(args.baseline, bag, run_plugins=not args.no_plugins)
        candidate = read_dictionary(args.candidate, bag, run_plugins=not args.no_plugins)
        if baseline is None or candidate is None:
            code = _verdict(EXIT_FINDINGS)
            _report(bag, args.format)
            return code

        plugins = candidate.plugins
        if args.plugin:
            if candidate.from_description:
                msg = (
                    "--plugin names the plugins of an archived dictionary; a project "
                    "description names its own"
                )
                raise ValueError(msg)
            plugins = _plugins_from_arguments(args.plugin, bag)
        _verify_overrides(bag, baseline.plugins)

        compared = compare_deliveries(
            baseline,
            candidate,
            bag,
            location=where(args.candidate),
            baseline_location=where(args.baseline),
            plugins=plugins,
        )
        if args.renames is not None:
            _refuse_a_source(args.renames, "--renames", *candidate.sources, *baseline.sources)
            # Written whether or not the comparison found errors: a delivery that cannot be
            # accepted still needs its renames listed, so that whoever fixes it knows what
            # moved.
            try:
                args.renames.write_text(
                    json.dumps(renames(compared.paired), indent=2) + "\n",
                    encoding="utf-8",
                    newline="",
                )
            except OSError as error:
                msg = (
                    f"cannot write the --renames file '{args.renames.as_posix()}': "
                    f"{error.strerror or error}"
                )
                raise OSError(msg) from None
    code = _verdict(EXIT_FINDINGS if bag.has_errors else EXIT_OK)
    _report(bag, args.format)
    if args.format != "json":
        # The file names, not the project names: two deliveries of one project share a name.
        # And when the two file names coincide as well - which they do whenever the
        # deliveries are kept in a directory each - the names say nothing at all
        # ("pressure.ddd.json can replace pressure.ddd.json"), so the line falls back to the
        # paths as they were typed, which is what tells them apart.
        verdict = "cannot" if bag.has_errors else "can"
        candidate, baseline = args.candidate.name, args.baseline.name
        if candidate == baseline:
            candidate, baseline = args.candidate.as_posix(), args.baseline.as_posix()
        print(f"{candidate} {verdict} replace {baseline}", file=sys.stderr)
    return code


def _check_address_coverage(
    carried: tuple[str, ...], addresses: dict[str, int], path: Path, bag: DiagnosticBag
) -> None:
    """Report the objects a supplied address map does not cover, and the entries nobody wants.

    Only when a map with entries was given: without one, or with an empty one, every address
    is zero by construction, and nothing is reported or failed, ``--strict`` included. That is
    the run a build makes before it has linked anything, and as well a step after the link
    whose map holds no entry. With entries, a symbol the map does not
    carry silently became address zero - and the map is written by a linker script or a patch
    tool against the names of one build, so a renamed variable or a stale file covers some of
    the objects and not the rest. What comes out is an a2l pointing a calibration tool at
    0x00000000, which reads and writes something, and nothing in the run said so.

    The entries that match nothing are named in a note rather than as a finding of their own:
    they are usually the other half of the same mistake - the old spelling of the symbol that
    has just gone missing - and reading them together is what identifies a rename. The
    symbols the recipe of the build page sweeps up along the way are in that note too,
    including any whose address no ``ECU_ADDRESS`` could hold: ``weigh_addresses`` weighs an
    address only for a symbol this list carries, because no other one is ever formatted into
    anything, and this note is where the rest are accounted for.
    """
    if not addresses:
        # An empty map is every address zero by construction, and it is not failed under
        # --strict either: the run a build makes before it has linked reads one, the cmake
        # module seeding it so that the build has a file to depend on, and a strict first build
        # that failed on it could never reach the step that fills the map. The step after the
        # link reads one too when nothing was extracted into the map, and passes the same
        # way. A map that names some objects and not others is another thing, and is
        # reported below.
        return
    missing = [symbol for symbol in carried if symbol not in addresses]
    if not missing:
        return
    unused = sorted(set(addresses) - set(carried))
    notes: list[tuple[str, Location | None]] = []
    if unused:
        notes.append((f"the map also carries {_listed(unused)}, which the a2l does not", None))
    bag.add(
        "address-missing",
        f"the address map has no entry for {_at_address_0(missing)}",
        where(path),
        notes=notes,
    )


def _check_image_coverage(
    carried: tuple[str, ...], placed: Placed, path: Path, bag: DiagnosticBag
) -> None:
    """Report the objects an image does not place, and why, as a map's missing ones are.

    The finding is the map's, ``address-missing``, for the same harm - a symbol of the a2l at
    address 0, which a calibration tool reads and writes as readily as any other - without the
    map's early return: an image is never the run a build makes before it has linked. Each
    reason is a note, said once however many symbols share it - every member of a variable the
    image lacks does - for the symbols the finding names; the rest are counted, as a map's are,
    so that an image whose definition file was compiled without ``-g``, every symbol of the
    project missing from its debug information, still gives a finding a few lines long.
    """
    missing = [symbol for symbol in carried if symbol in placed.reasons]
    if not missing:
        return
    reasons = dict.fromkeys(placed.reasons[symbol] for symbol in missing[:_LISTED_LIMIT])
    bag.add(
        "address-missing",
        f"the image has no address for {_at_address_0(missing)}",
        where(path),
        notes=[(reason, None) for reason in reasons],
    )


def _check_image_agreement(
    dictionary: DataDictionary, placed: Placed, image: Image, path: Path, bag: DiagnosticBag
) -> None:
    """Report each placed variable the image holds otherwise than its description states.

    The image is the one place the run sees the C the build compiled, which a project's own
    templates write and anybody may edit, so what the generator promises of it is held there.
    """
    from ddd.agreement import disagreements

    for found in disagreements(dictionary, placed, image):
        bag.add(
            "elf-mismatch", found.message, where(path), notes=[(note, None) for note in found.notes]
        )


def _leave_out(
    absent: Sequence[ConditionalObject],
    dictionary: DataDictionary,
    lacking: str,
    path: Path,
    reasons: Mapping[str, str],
    bag: DiagnosticBag,
) -> tuple[frozenset[str], tuple[str, ...]]:
    """Say, at ``info``, which objects the a2l leaves out because the build compiled them out.

    ``absent`` are the conditional objects the source holds nothing of. One finding per
    condition, the objects it guards named as ``address-missing`` names its own. ``lacking``
    is how the source says it holds nothing for them - ``the image has no address for`` or
    ``the address map has no entry for`` - and ``reasons`` is why, for an image, which a map
    does not give.

    A curve or a map over an axis among them goes with it, which the build holds and the file
    cannot describe: a finding for each such axis names it, the condition it went under and
    what goes with it. It says all of that itself, since the findings print by severity, this
    warning before the information naming the axis, which a project may ignore. What comes
    back is the symbols left out, and the ones that still reach the file, which are the ones
    ``address-missing`` is about: the writer's own selection under them, so that what only an
    axis among them pulled in, such as an ``export: false`` measurement, is not among them.
    """
    for condition in dict.fromkeys(entry.condition for entry in absent):
        objects = [entry for entry in absent if entry.condition == condition]
        names = [entry.name for entry in objects]
        plural = len(names) != 1
        reasons_given = dict.fromkeys(
            reasons[symbol]
            for entry in objects[:_LISTED_LIMIT]
            for symbol in entry.symbols[:1]
            if symbol in reasons
        )
        bag.add(
            "condition-left-out",
            f"{lacking} {_listed(names)}, which {'are' if plural else 'is'} only present in "
            f"the build when '{condition}'; {'they are' if plural else 'it is'} left out of "
            "the a2l",
            where(path),
            notes=[(reason, None) for reason in reasons_given],
        )
    from ddd.backends import addressed_symbols, dragged_with

    left_out = frozenset(symbol for entry in absent for symbol in entry.symbols)
    dragged = dragged_with(dictionary, left_out)
    condition_of = {symbol: entry.condition for entry in absent for symbol in entry.symbols}
    going: dict[str, list[str]] = {}
    for name, axes in dragged.items():
        for axis in axes:
            going.setdefault(axis, []).append(name)
    for axis in sorted(going):
        names = going[axis]
        plural = len(names) != 1
        bag.add(
            "reference-left-out",
            f"{_listed(names)} {'refer' if plural else 'refers'} to the axis '{axis}', which is "
            f"only present in the build when '{condition_of[axis]}' and is left out of the a2l; "
            f"the a2l cannot describe {'them' if plural else 'it'} without the axis, so "
            f"{'they are' if plural else 'it is'} left out too",
            where(path),
        )
    return left_out, addressed_symbols(dictionary, left_out)


def _at_address_0(missing: list[str]) -> str:
    """``'A', 'B' and 3 others; they reach the a2l at address 0``: how ``address-missing`` ends,
    whichever source left the symbols out."""
    reach = "it reaches" if len(missing) == 1 else "they reach"
    return f"{_listed(missing)}; {reach} the a2l at address 0"


_LISTED_LIMIT = 5
"""How many names a finding spells out before it starts counting instead."""


def _listed(names: list[str]) -> str:
    """``'A', 'B' and 3 others``: enough to recognise, never a screenful."""
    spelled = ", ".join(f"'{name}'" for name in names[:_LISTED_LIMIT])
    rest = len(names) - _LISTED_LIMIT
    return f"{spelled} and {rest} other{'s' if rest != 1 else ''}" if rest > 0 else spelled


def _selected(args: argparse.Namespace) -> None:
    """Apply ``--without`` and refuse a run the subtraction has made incoherent.

    Subtracting a built-in artefact is the same as never having selected it, so clearing the
    render flag is the whole of it; a plugin's artefact has no such flag and is therefore
    untouched, which is the point. What the subparsers can no longer check for themselves is
    checked here instead: an artefact that is gone must not be given its options, and one that
    stayed must still have them. The a2l's addresses come from one source, a map or an image,
    which is refused here too, before anything is read.
    """
    if getattr(args, "const_inputs", False):
        raise ValueError(CONST_INPUTS_REMOVED)
    for artefact in getattr(args, "without", ()):
        setattr(args, f"render_{artefact}", False)

    template_dir = getattr(args, "template_dir", None)
    if args.render_c and template_dir is None:
        msg = "the c sources are part of this run, so -t/--template-dir is required"
        raise ValueError(msg)
    for option, given, artefact in (
        ("-t/--template-dir", template_dir is not None, "c"),
        ("--byte-order", getattr(args, "byte_order", None) is not None, "a2l"),
        ("--address-map", getattr(args, "address_map", None) is not None, "a2l"),
        ("--image", getattr(args, "image", None) is not None, "a2l"),
        (
            "--a2l-module-fragment",
            getattr(args, "a2l_module_fragment", None) is not None,
            "a2l",
        ),
    ):
        if given and not getattr(args, f"render_{artefact}"):
            msg = f"{option} belongs to the {artefact} artefact, left out by --without"
            raise ValueError(msg)
    if getattr(args, "address_map", None) is not None and getattr(args, "image", None) is not None:
        msg = "--image and --address-map are two sources of the a2l's addresses; give one of them"
        raise ValueError(msg)


def _displayed_path(path: Path, output_dir: Path) -> str:
    """``path`` the way the reader would type it, rooted at the ``-o`` they actually gave.

    ``render`` hands every file back resolved against ``output_dir`` resolved once, so that an
    alias, an escape, or a directory junction cannot hide behind a spelling that looks
    different from the real location it names or clashes with. Once that is settled the reader
    is better served by the path the way they would type it themselves than by the resolved
    one - the same trade ``Location.render`` already makes for a diagnostic - so this measures
    ``path`` against ``output_dir`` resolved and reattaches it to ``output_dir`` exactly as
    typed: relative to the current directory if ``-o`` was relative, and following a junction
    or a symbolic link as typed rather than naming the real directory it lands on - which is
    the whole of the reason this exists, and is as true of an absolute ``-o`` as of a relative
    one, so neither spelling is treated specially here. Only a path ``relative_to`` cannot
    place under the resolved directory falls back to itself: the on-disk failure path hands
    this the raw text of an ``OSError``, which is not a path ``render`` has already vetted.
    """
    with contextlib.suppress(ValueError):
        # Joined as paths rather than as text: a join collapses the "." that a bare
        # ``-o .``, or a failure reported on the output directory itself, would
        # otherwise leave in the spelling.
        return (output_dir / path.relative_to(output_dir.resolve())).as_posix()
    return path.as_posix()


def _written(status: WriteStatus, shown: str, prefix: str = "wrote") -> str:
    """One line of the text report of a written file, as ``generate`` and ``dump -o`` print it.

    ``prefix`` is what the run did to a file it did not leave alone - ``would write`` on a dry
    run - padded so that the paths line up under ``unchanged``. A file the run took back
    carries no status in parentheses: ``removed`` is the whole of what happened to it.
    """
    from ddd.backends import WriteStatus

    if status is WriteStatus.UNCHANGED:
        return f"unchanged   {shown}"
    if status is WriteStatus.REMOVED:
        return f"{'would remove' if prefix.startswith('would') else 'removed':<11} {shown}"
    return f"{prefix:<11} {shown} ({status.value})"


def _dictionary_text(dictionary: DataDictionary) -> str:
    """The dictionary as ``dump`` publishes it, final newline included.

    One text wherever it goes - printed by ``dump``, written by ``dump -o``, or written beside
    the artefacts by ``generate --dictionary`` - so that no two of them can differ.
    """
    return dictionary.model_dump_json(indent=2) + "\n"


def _dictionary_file(
    dictionary: DataDictionary, path: Path, artefacts: Sequence[GeneratedFile], output_dir: Path
) -> GeneratedFile:
    """``generate --dictionary``: the dictionary as one more file of the run's single write.

    Written with the artefacts rather than after them, so that all of them are written or none
    is: a run that fails leaves the last dictionary describing the artefacts still beside it,
    and a failure on the dictionary takes back the artefacts the run had created. The path is
    the one typed, relative to the working directory like every path on the command line
    rather than a file a backend names inside the output directory, so it is resolved before
    it is weighed against the files the backends claim; a clash is refused before anything is
    written, as :func:`~ddd.backends.base.render` refuses two backends claiming one file. The
    name the run's manifest is kept under in the output directory is refused the same way: a
    dictionary written there would be taken, by the next run, for the record of what was written.
    """
    from ddd.backends import DICTIONARY_ARTEFACT, GeneratedFile
    from ddd.backends.base import MANIFEST_NAME

    if path.resolve() in {artefact.path for artefact in artefacts}:
        msg = (
            f"the dictionary and an artefact of this run would both write '{path.name}'; "
            "give --dictionary another file"
        )
        raise ValueError(msg)
    if path.resolve() == output_dir.resolve() / MANIFEST_NAME:
        msg = (
            f"the dictionary would be written as '{MANIFEST_NAME}', which is the name the "
            "manifest of this run is kept under; give --dictionary another file"
        )
        raise ValueError(msg)
    return GeneratedFile(path, _dictionary_text(dictionary), DICTIONARY_ARTEFACT)


def _command_generate(args: argparse.Namespace) -> int:
    from ddd.addresses import addresses_from_image, load_address_map
    from ddd.backends import (
        DICTIONARY_ARTEFACT,
        A2lBackend,
        A2lOptions,
        ByteOrder,
        CBackend,
        COptions,
        Manifest,
        RemovalError,
        addressed_symbols,
        conditional_objects,
        describe_write_failure,
        load_module_fragment,
        render,
        weigh_addresses,
        write,
    )
    from ddd.plugins import backend_of

    _selected(args)

    resolved, bag = _analyze(args)
    if resolved is None:
        code = _verdict(EXIT_FINDINGS)
        _report(bag, args.format)
        return code
    dictionary = resolved.dictionary

    with _reported_on_failure(bag, args.format):
        # Before the findings gate below, so that a command line which would write nothing is
        # reported as the usage error it is, whatever state the project happens to be in. Asked
        # after the analysis rather than at parse time, because only the resolved project knows
        # whether a plugin provides an artefact.
        produces_plugin_artefact = getattr(args, "render_plugins", False) and any(
            plugin.backend is not None for plugin in resolved.plugins
        )
        if not (
            args.render_c
            or args.render_a2l
            or produces_plugin_artefact
            or getattr(args, "plugin_artefact", None) is not None
            or args.dictionary is not None
        ):
            msg = (
                "this run would write nothing: what --without left of it is the plugins' "
                "artefacts, and this project provides none"
            )
            raise ValueError(msg)

        # Read with the address source, before the findings gate: a file the run cannot take is
        # a usage error whatever state the project is in. _selected has seen to it that the
        # option is only here for a run that writes the a2l.
        fragment_path: Path | None = getattr(args, "a2l_module_fragment", None)
        fragment = None if fragment_path is None else load_module_fragment(fragment_path)

        # Guarded on the artefact, not just on the option: a run that does not write the a2l
        # has no use for the map and must not be killed by one it was never going to read.
        wants_addresses = args.render_a2l and getattr(args, "address_map", None) is not None
        addresses: dict[str, int] = {}
        links: dict[str, tuple[str, int]] = {}
        left_out: frozenset[str] = frozenset()
        byte_order: str | None = getattr(args, "byte_order", None)
        image_path: Path | None = getattr(args, "image", None)
        alignment: int | None = None
        if image_path is not None:
            # Only a run writing the a2l gets here with an image: _selected refused it to the
            # others, as it refuses them the map. The symbols are the a2l's, as for a map.
            carried = addressed_symbols(dictionary)
            image = _image_reader()(image_path)
            # The image states its byte order, so an option saying the other one is a mistake
            # about the target, which an a2l of the wrong order would only hide.
            if byte_order not in (None, image.byte_order):
                msg = (
                    f"--byte-order {byte_order} contradicts '{image_path.as_posix()}', which "
                    f"is {image.byte_order} endian"
                )
                raise ValueError(msg)
            byte_order = image.byte_order
            if image.machine is not None:
                from ddd.toolbox.mapping import alignment_cap

                # The ABI the image was built for says how a 64 bit scalar is aligned; the
                # table is the one the image's structures are weighed with (``ddd tool
                # from-elf``), and a machine it holds none for keeps the fixed values.
                alignment = alignment_cap(image.machine, image.flags)
            if image.load_relative:
                bag.add(
                    "image-load-relative",
                    "the image is position independent, so the addresses the a2l states are "
                    "offsets from where it loads",
                    where(image_path),
                    notes=[
                        (
                            "a project that adds its load base when it reads the a2l is right, "
                            "and one that does not finds every address wrong",
                            None,
                        )
                    ],
                )
            placed = addresses_from_image(image, carried)
            addresses = placed.addresses
            links = placed.links
            weigh_addresses(addresses, carried, image_path.as_posix())
            # An object is compiled out where the image defines none of it, not where it
            # holds it and cannot place a part, or holds it in a way that is a defect.
            left_out, reaching = _leave_out(
                [
                    entry
                    for entry in conditional_objects(dictionary)
                    if all(symbol in placed.absent for symbol in entry.symbols)
                ],
                dictionary,
                "the image has no address for",
                image_path,
                placed.reasons,
                bag,
            )
            _check_image_coverage(reaching, placed, image_path, bag)
            _check_image_agreement(dictionary, placed, image, image_path, bag)
        elif wants_addresses:
            # The symbols the a2l of this run will state an address for, read once: they
            # decide both which entries of the map are held to what an ECU_ADDRESS can hold
            # and which objects the map leaves uncovered.
            carried = addressed_symbols(dictionary)
            addresses = load_address_map(args.address_map)
            weigh_addresses(addresses, carried, args.address_map.as_posix())
            # Before the gate below, so that a --strict build stops rather than writing a
            # file whose addresses it has just been told are incomplete.
            # A map that names something has been through the link: a conditional object it
            # names no part of, nor the object itself as a symbol lister writes a structure,
            # is a feature the build left out, which is no hole in it.
            left_out, reaching = _leave_out(
                [
                    entry
                    for entry in conditional_objects(dictionary)
                    if addresses
                    and entry.name not in addresses
                    and not any(symbol in addresses for symbol in entry.symbols)
                ],
                dictionary,
                "the address map has no entry for",
                args.address_map,
                {},
                bag,
            )
            _check_address_coverage(reaching, addresses, args.address_map, bag)
        if args.render_a2l and byte_order is None:
            # Neither the option nor an image said it: the a2l states little endian because
            # something has to be stated, and a big endian target that forgot to say so would
            # otherwise get a file whose every multi byte value a tool reads swapped.
            bag.add(
                "byte-order-defaulted",
                f"no --byte-order and no --image was given, so the a2l states "
                f"{ByteOrder(BYTE_ORDERS[0]).a2l}, {BYTE_ORDERS[0]} endian, as a default; a big "
                f"endian target needs --byte-order big (the BYTE_ORDER of ddd_generate in "
                f"cmake), and an image states its own",
            )
        if bag.has_errors and not args.force:
            code = _verdict(EXIT_FINDINGS)
            _report(bag, args.format)
            return code

        backends: list[Backend] = []
        if args.render_c:
            backends.append(CBackend(args.template_dir, COptions(), GENERATOR))
        if args.render_a2l:
            backends.append(
                A2lBackend(
                    A2lOptions(
                        byte_order=ByteOrder(byte_order or BYTE_ORDERS[0]),
                        alignment_cap=alignment,
                        addresses=addresses,
                        links=links,
                        left_out=left_out,
                        # An image is a source whatever it places, the finding naming what it
                        # does not; a map is one once it has an entry, as for that finding.
                        has_address_source=image_path is not None or bool(addresses),
                        module_fragment=fragment,
                    ),
                    GENERATOR,
                )
            )
        if getattr(args, "render_plugins", False):
            # After the built-in backends and in the order the project names the plugins,
            # which is the order their hooks run in; the renderer refuses a path two backends
            # claim.
            backends.extend(
                backend_of(plugin, resolved.settings(plugin), GENERATOR)
                for plugin in resolved.plugins
                if plugin.backend is not None
            )
        name = getattr(args, "plugin_artefact", None)
        if name is not None:
            plugin = next((entry for entry in resolved.plugins if entry.name == name), None)
            if plugin is None:
                provided = _listed([entry.name for entry in resolved.plugins if entry.backend])
                msg = (
                    f"'{name}' is not an artefact of this project; it provides: "
                    f"{provided or 'no plugin artefact'}"
                )
                raise ValueError(msg)
            backends.append(backend_of(plugin, resolved.settings(plugin), GENERATOR))
        files = render(dictionary, backends, args.output_dir)
        # What this run produced into the directory it writes to, which is what decides the
        # files of earlier runs it may take back: the artefacts it did not produce - the a2l
        # of a `--without a2l`, the c of a post-link `generate a2l`, a plugin the project
        # stopped naming - keep theirs, because this run says nothing about them.
        produced = {backend.name for backend in backends}
        # Weighed on a dry run as well, which would otherwise say it would write over a file
        # the run read: the guard is on what the run names, not on what it goes on to do.
        reads = _files_the_run_read(
            resolved,
            image_path,
            args.address_map if wants_addresses else None,
            fragment_path,
            args.template_dir if args.render_c else None,
        )
        for file in files:
            _refuse_a_source(
                file.path,
                f"the {file.artefact} artefact",
                *reads,
                advice="give -o a directory of its own",
            )
        if args.dictionary is not None:
            _refuse_a_directory(args.dictionary, "--dictionary")
            _refuse_a_source(args.dictionary, "--dictionary", *reads)
            files.append(_dictionary_file(dictionary, args.dictionary, files, args.output_dir))
            produced.add(DICTIONARY_ARTEFACT)
        try:
            results = write(
                files, dry_run=args.dry_run, manifest=Manifest(args.output_dir, produced)
            )
        except RemovalError as error:
            # Said as a removal rather than as a write: the file exists, this run was deleting
            # it, and the advice a failed write carries - the path is too long for the
            # platform - is advice about a path that does not exist yet.
            shown = _displayed_path(Path(str(error.filename)), args.output_dir)
            msg = f"cannot remove '{shown}': {error.strerror or error}"
            raise OSError(msg) from None
        except OSError as error:
            # The target is the one thing a caller gets wrong regularly - a path that is a
            # directory, or one nothing may be written to. Naming the file beats the bare
            # errno text, and beats naming the directory, which is usually fine.
            target = (
                _displayed_path(Path(error.filename), args.output_dir)
                if error.filename
                else args.output_dir.as_posix()
            )
            raise OSError(describe_write_failure(error, target)) from None

    code = _verdict(EXIT_FINDINGS if bag.has_errors else EXIT_OK)
    if args.format == "json":
        payload = _diagnostics_payload(bag)
        payload["generated"] = [
            {"path": _displayed_path(result.path, args.output_dir), "status": result.status.value}
            for result in results
        ]
        print(json.dumps(payload, indent=2))
    else:
        _report(bag, args.format)
        prefix = "would write" if args.dry_run else "wrote"
        for result in results:
            shown = _displayed_path(result.path, args.output_dir)
            print(_written(result.status, shown, prefix), file=sys.stderr)
    return code


def _command_list(args: argparse.Namespace) -> int:
    resolved, bag = _analyze(args)
    if resolved is None:
        code = _verdict(EXIT_FINDINGS)
        _report(bag, args.format)
        return code
    dictionary = resolved.dictionary

    code = _verdict(EXIT_FINDINGS if bag.has_errors else EXIT_OK)
    if args.format == "json":
        print(
            json.dumps(
                {
                    "project": dictionary.name,
                    "components": [
                        component.model_dump(mode="json") for component in dictionary.components
                    ],
                    # `name` in front of the record itself, because a leaf's is a property of
                    # the model rather than a field of it: a leaf row carried `path` and no
                    # `name` at all, so a script keying the rows on `name` - the key the other
                    # shape of row has always had, and the one the table is sorted by - dropped
                    # every member of every structured variable in silence. First, as it
                    # already was on a plain object, where it repeats what the record states.
                    "variables": [
                        {"name": entry.name, **entry.model_dump(mode="json")}
                        for entry in dictionary.listed
                    ],
                    **_diagnostics_payload(bag),
                },
                indent=2,
            )
        )
    else:
        _print_table(dictionary)
        # Before the findings, as `sources` and `artefacts` already flush: redirected into
        # one file, stdout is block buffered and stderr is not, so the table arrived after
        # every finding of the run - which is not the order anybody reads a log in.
        sys.stdout.flush()
        _report(bag, args.format)
    return code


def _command_dump(args: argparse.Namespace) -> int:
    """Emit the data dictionary itself, so that another tool can generate from it.

    stdout carries the dictionary and nothing else, in both formats: ``ddd dump > baseline.json``
    is the documented way to archive a delivery, so a second json document must not appear
    there. ``--format json`` therefore selects the format of the *diagnostics*, which go to
    stderr - where they also stay out of the way of a pipe. ``-o`` moves the dictionary into a
    file, the findings and the exit code staying what they were; see
    :func:`_write_dictionary`.
    """
    resolved, bag = _analyze(args, stream=sys.stderr)
    if resolved is None:
        code = _verdict(EXIT_FINDINGS)
        _report(bag, args.format, stream=sys.stderr)
        return code
    code = _verdict(EXIT_FINDINGS if bag.has_errors else EXIT_OK)
    if args.output is None:
        print(_dictionary_text(resolved.dictionary), end="")
        # The findings go to stderr, the dictionary to stdout, and `ddd dump p.ddd.json > log
        # 2>&1` sends both to one file where only stdout is buffered: flushed here, the
        # document is where the reader expects it rather than under the findings about it.
        sys.stdout.flush()
        _report(bag, args.format, stream=sys.stderr)
    else:
        _write_dictionary(resolved, args.output, bag, args.format)
    return code


def _command_tool_from_elf(args: argparse.Namespace) -> int:
    """``ddd tool from-elf``: the DDD declarations of the C variables a linked ELF image holds.

    stdout carries the declarations and nothing else, as ``dump``'s carries the dictionary, and
    the findings go to stderr in either format. Nothing is written while an error stands unless
    ``--force`` asks for what was described; the exit code reports the errors either way, so
    that a script reads the verdict from the code rather than from the presence of the output.

    The command line is judged whole before the image is read: a malformed ``SYMBOL`` or an
    ``-o`` naming the image is a usage error however large the image, and whatever the image
    would have been found to hold.
    """
    open_image = _image_reader()
    from ddd.loading import resolve_path
    from ddd.models.common import C_IDENTIFIER_PATTERN, IDENTIFIER_MAX_LENGTH
    from ddd.toolbox.from_elf import describe, document_text
    from ddd.toolbox.selection import wanted

    component = args.component
    if component is not None and (
        not re.fullmatch(C_IDENTIFIER_PATTERN, component) or len(component) > IDENTIFIER_MAX_LENGTH
    ):
        msg = (
            f"--component takes a C identifier of at most {IDENTIFIER_MAX_LENGTH} characters, "
            f"not '{component}'"
        )
        raise ValueError(msg)
    for text in args.symbols:
        wanted(text)
    if args.output is not None:
        _refuse_a_directory(args.output, "-o")
        _refuse_a_source(args.output, "-o", resolve_path(args.image))
    image = open_image(args.image)
    bag = DiagnosticBag()
    description = describe(
        image,
        args.symbols,
        scope=args.scope,
        component=component,
        identity=args.identity_conversions,
        bag=bag,
    )
    if bag.has_errors and not args.force:
        code = _verdict(EXIT_FINDINGS)
        _report(bag, args.format, stream=sys.stderr)
        return code
    text = document_text(description, component)
    code = _verdict(EXIT_FINDINGS if bag.has_errors else EXIT_OK)
    if args.output is None:
        print(text, end="")
        sys.stdout.flush()
        _report(bag, args.format, stream=sys.stderr)
    else:
        _write_output(args.output, lambda: text, bag, args.format, resolve_path(args.image))
    return code


def _write_dictionary(
    resolved: Resolved, path: Path, bag: DiagnosticBag, output_format: str
) -> None:
    """``dump -o``: the dictionary into ``path``, reported the way ``generate`` reports a file.

    The text is exactly what stdout would have carried, and the findings, the stream they go to
    and the exit code of the analysis stay what they were; stdout is left empty, the file
    written is reported beside the findings, and a target that cannot be written is a usage
    error. The file goes through the writer ``generate`` uses - staged, the same bytes on every
    platform, and left untouched when its content would not change, so that a build step
    reading it does not run again for nothing. A redirection offers none of that: the shell
    empties the target before the tool has even started, and Windows PowerShell re-encodes
    whatever it is handed. The write sits in a block of its own, so a target that cannot be
    written is reported after the findings of the run, as ``generate`` reports one.
    """
    _write_output(
        path,
        lambda: _dictionary_text(resolved.dictionary),
        bag,
        output_format,
        *resolved.sources,
    )


def _write_output(
    path: Path,
    text: Callable[[], str],
    bag: DiagnosticBag,
    output_format: str,
    *sources: Path,
) -> None:
    """One text into ``path``, reported the way ``generate`` reports a file: what ``dump -o``
    and ``tool from-elf -o`` write through.

    ``text`` is made inside the reported block, as the dictionary always was, so that a failure
    to make it is reported after the findings of the run exactly as a failure to write it is.
    A path naming a directory, or a file the run read - ``sources`` - is refused.
    """
    from ddd.backends import GeneratedFile, describe_write_failure, write

    with _reported_on_failure(bag, output_format, sys.stderr):
        _refuse_a_directory(path, "-o")
        _refuse_a_source(path, "-o", *sources)
        content = text()
        try:
            (result,) = write([GeneratedFile(path, content)])
        except OSError as error:
            raise OSError(describe_write_failure(error, path.as_posix())) from None
    shown = path.as_posix()
    if output_format == "json":
        payload = _diagnostics_payload(bag)
        payload["generated"] = [{"path": shown, "status": result.status.value}]
        print(json.dumps(payload, indent=2), file=sys.stderr)
        return
    _report(bag, output_format)
    print(_written(result.status, shown), file=sys.stderr)


def _command_id(args: argparse.Namespace) -> int:
    """Stamp identities into description files, reporting what was written.

    Every file on the command line is attempted, and the ones that could not be used are
    reported after the total rather than instead of it: a run over a directory of
    descriptions must not stop at the first file it cannot read - or, just as ordinarily,
    cannot write - leaving everything after it unstamped and saying nothing about what it
    did before.
    """
    from ddd.identity import UNREADABLE, UNWRITABLE, assign

    written = 0
    skipped: list[tuple[Path, str]] = []
    for path in args.files:
        count = assign(path)
        if count == UNREADABLE:
            skipped.append((path, "not readable as json, skipped"))
        elif count == UNWRITABLE:
            skipped.append((path, "cannot be written, skipped"))
        else:
            written += count
    code = _verdict(EXIT_FINDINGS if skipped else EXIT_OK)
    for path, reason in skipped:
        print(f"{path}: {reason}", file=sys.stderr)
    print(f"wrote {written} id{'' if written == 1 else 's'}", file=sys.stderr)
    return code


def schema_models() -> dict[str, type[BaseModel]]:
    """The contract behind each name of :data:`ddd.names.SCHEMA_KINDS`.

    A function rather than a table, so that building the parser - which needs the names and
    nothing else - does not build every model in the package to learn them.
    """

    from ddd.ir import DataDictionary
    from ddd.models import (
        ComponentFile,
        ConstantsFile,
        ProjectFile,
        RastersFile,
        SectionsFile,
        TypesFile,
        UnitsFile,
    )

    return {
        "project": ProjectFile,
        "component": ComponentFile,
        "types": TypesFile,
        "units": UnitsFile,
        "sections": SectionsFile,
        "rasters": RastersFile,
        "constants": ConstantsFile,
        "dictionary": DataDictionary,
    }


SCHEMA_ALL = "all"
"""``ddd schema all -o DIR`` writes every schema at once, for a project to commit."""

SCHEMA_FILENAME = "ddd_{kind}.schema.json"
"""How ``all`` names each file, so that a ``$schema`` path is predictable and stable."""


def schema_text(kind: str, plugins: Sequence[Plugin] = ()) -> str:
    """The json schema of one file format, as it is written out.

    One function so that a file on disk and the answer to ``ddd schema`` can never differ -
    which is what lets a test tell a project its committed schemas have gone stale. With
    plugins, the ``extensions`` property of a definition and of the project closes over their
    models; the dictionary schema stays open, a dump being a produced document.
    """
    from ddd.models.schema import PublishedSchema

    # by_alias so that the key is '$schema' rather than the python attribute name, and
    # PublishedSchema so that what an editor shows is documentation rather than python.
    published = schema_models()[kind].model_json_schema(
        by_alias=True, schema_generator=PublishedSchema
    )
    if plugins and kind in ("component", "project"):
        _close_extensions(published, plugins, on_project=kind == "project")
    return json.dumps(published, indent=2) + "\n"


def _close_extensions(
    schema: dict[str, Any], plugins: Sequence[Plugin], *, on_project: bool
) -> None:
    """Replace every open ``extensions`` property by one closed over the plugins' models.

    Each plugin's model is rendered by the same generator that documents the built-in
    models, its nested definitions hoisted into the root ``$defs`` under the plugin's name so
    that two plugins declaring an ``Entry`` cannot collide. A plugin declaring no model for
    this kind is left out, which is what makes a block for it invalid in the editor - the
    same answer the loader gives. The nodes to close are collected before any hoisting, so a
    plugin's own model - however nested - may freely declare a field named ``extensions`` of
    its own without that field being mistaken for the block it is itself contributing to.
    """
    from ddd.models.schema import PublishedSchema
    from ddd.plugins import block_model, guarding_plugin_model

    definitions: dict[str, Any] = schema.setdefault("$defs", {})
    targets = [
        node
        for node in (schema, *definitions.values())
        if "extensions" in node.get("properties", {})
    ]
    properties: dict[str, Any] = {}
    for plugin in plugins:
        model = block_model(plugin, on_project=on_project)
        if model is None:
            continue
        with guarding_plugin_model(plugin.name, "rendering the schema of its own model"):
            rendered = model.model_json_schema(
                ref_template=f"#/$defs/{plugin.name}.{{model}}", schema_generator=PublishedSchema
            )
        rendered.pop("$schema", None)
        for name, definition in rendered.pop("$defs", {}).items():
            definitions[f"{plugin.name}.{name}"] = definition
        properties[plugin.name] = rendered
    for node in targets:
        extensions = node["properties"]["extensions"]
        node["properties"]["extensions"] = {
            "type": "object",
            "description": extensions.get("description", ""),
            "properties": properties,
            "additionalProperties": False,
        }


def _command_lsp(args: argparse.Namespace) -> int:
    # Imported here rather than at the top of the module: the server pulls in the loader, the
    # analysis and the range machinery, and every other command would pay for that import
    # without ever using it.
    from ddd.lsp.server import serve

    return serve(args.build_directory, run_plugins=not args.no_plugins)


def _command_gui(args: argparse.Namespace) -> int:
    # Imported here, like the language server: the server brings up the loader, the analysis
    # and the edit engine, which no other command should pay for.
    from ddd.gui.server import run

    return int(
        run(
            args.project,
            args.build_directory,
            args.port,
            host=args.host,
            open_browser=not args.no_browser,
        )
    )


def _port(text: str) -> int:
    """A port to serve on: a number from 0, which lets the system pick one, to 65535."""
    if not (text.isascii() and text.isdecimal()) or int(text) > 65535:
        raise argparse.ArgumentTypeError(f"{text!r} is not a port number from 0 to 65535")
    return int(text)


def _command_build_info(args: argparse.Namespace) -> int:
    # Built rather than recorded blindly: a typo in a severity override would otherwise be
    # copied into the file as a policy nobody can apply, and would surface at build time
    # instead of here, while the project is being configured.
    from ddd.backends import GeneratedFile, describe_write_failure, write
    from ddd.build_info import BuildInfo, build_info_text

    SeverityPolicy.from_strings(args.severity, strict=args.strict)
    info = BuildInfo(
        # Absolute, because whoever reads this file is not in the directory the build ran in.
        project=args.project.resolve().as_posix(),
        image=args.image,
        origin=args.origin,
        strict=args.strict,
        severity=tuple(args.severity),
    )
    # The description it names is a file this command refers to rather than reads, and it is
    # the one it must not replace; any other description is refused by its name.
    _refuse_a_directory(args.output, "-o")
    _refuse_a_source(args.output, "-o", args.project)
    _refuse_a_description_name(args.output)
    try:
        # The writer a dumped dictionary goes through: staged beside the target, the same bytes
        # on every platform, and left untouched when the record would not change, so that a build
        # reading it does not run again for nothing.
        (result,) = write([GeneratedFile(args.output, build_info_text(info))])
    except OSError as error:
        raise OSError(describe_write_failure(error, args.output.as_posix())) from None
    print(_written(result.status, args.output.as_posix()), file=sys.stderr)
    return EXIT_OK


def _write_schema(path: Path, kind: str, plugins: Sequence[Plugin] = ()) -> None:
    # Guarded like every other file this tool writes: `ddd schema all -o afile.txt` answered
    # `[WinError 183] Cannot create a file when that file already exists: 'afile.txt'`, which
    # is the mkdir talking about a file the caller named as a directory, and says neither.
    from ddd.backends import describe_write_failure

    _refuse_a_description_name(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # newline="" keeps the line endings as written on every platform, the same discipline
        # the generated sources follow: a schema committed from Windows must not differ from
        # the same schema committed from linux.
        path.write_text(schema_text(kind, plugins), encoding="utf-8", newline="")
    except OSError as error:
        raise OSError(describe_write_failure(error, path.as_posix())) from None
    print(f"wrote {path.as_posix()}", file=sys.stderr)


def _command_schema(args: argparse.Namespace) -> int:
    plugins = _plugins_from_arguments(args.plugin)
    if args.kind == SCHEMA_ALL:
        if args.output is None:
            msg = (
                f"'{SCHEMA_ALL}' writes several files, so it needs a directory: "
                f"ddd schema {SCHEMA_ALL} -o schemas"
            )
            raise ValueError(msg)
        for kind in SCHEMA_KINDS:
            _write_schema(args.output / SCHEMA_FILENAME.format(kind=kind), kind, plugins)
        return EXIT_OK

    if args.output:
        _write_schema(args.output, args.kind, plugins)
    else:
        print(schema_text(args.kind, plugins), end="")
    return EXIT_OK


def _command_cmake_dir(args: argparse.Namespace) -> int:
    """Print the directory to add to CMAKE_MODULE_PATH before ``include(Ddd)``."""
    directory = cmake_module_directory()
    if directory is None:
        print("ddd: the cmake integration module is not part of this installation", file=sys.stderr)
        return EXIT_USAGE
    print(directory.as_posix())
    return EXIT_OK


def _command_templates_dir(args: argparse.Namespace) -> int:
    """Print the directory holding the example templates, to copy into a project."""
    from ddd.backends import example_template_directory

    directory = example_template_directory()
    if directory is None:
        print("ddd: the example templates are not part of this installation", file=sys.stderr)
        return EXIT_USAGE
    print(directory.as_posix())
    return EXIT_OK


def _command_artefacts(args: argparse.Namespace) -> int:
    """The artefacts this project can be asked to generate, by name.

    Tolerant in the same way as ``sources`` and for the same reason: which artefacts exist
    follows from the plugins a project names, not from whether its interfaces agree, and a
    build asking what it can produce deserves an answer while the project is still being
    fixed. Only a root file that cannot be read at all is fatal: a plugin whose model raises
    is a ``plugin-invalid`` finding beside the listing.

    The files an artefact writes are deliberately not reported. A plugin decides them from
    the resolved dictionary, so they are knowable only once the project has been assembled,
    which is exactly what ``ddd generate all --dry-run`` does.
    """
    from ddd.loading import load_workspace

    bag = DiagnosticBag()
    if args.project is not None and args.plugin:
        msg = "--plugin cannot be given together with a project, which names its own plugins"
        raise ValueError(msg)

    if args.project is None:
        plugins: tuple[Plugin, ...] = _plugins_from_arguments(args.plugin)
        unreadable = False
    else:
        workspace = load_workspace(args.project, bag, plugin_defects_are_findings=True)
        plugins = () if workspace is None else workspace.plugins
        unreadable = workspace is None

    # Nothing at all when the root file could not be read: the built-in pair exists whatever
    # happens, but the question asked was what *this* project generates, and that is unanswered.
    # Reporting half of it would invite a build to act on an answer DDD does not have.
    listed: list[dict[str, str]] = []
    silent: list[str] = []
    if not unreadable:
        listed = [{"name": name, "kind": "built-in"} for name in BUILT_IN_GENERATED]
        listed += [
            {"name": plugin.name, "kind": "plugin"}
            for plugin in plugins
            if plugin.backend is not None
        ]
        # A plugin with no backend is not an artefact, but leaving it out in silence reads as
        # the plugin having failed to load, and calling it one that generates nothing reads as
        # a plugin with no effect. Neither is true: its block is part of the vocabulary the
        # project's own templates render, so the note says where its output comes from.
        silent = [plugin.name for plugin in plugins if plugin.backend is None]

    code = _verdict(EXIT_FINDINGS if unreadable else EXIT_OK)
    if args.format == "json":
        payload = {
            "artefacts": listed,
            "plugins_without_artefact": silent,
            **_diagnostics_payload(bag),
        }
        print(json.dumps(payload, indent=2))
        return code
    if unreadable:
        _report(bag, "text")
        return code
    width = max(len(entry["name"]) for entry in listed)
    for entry in listed:
        print(f"{entry['name']:<{width}}  {entry['kind']}")
    if silent:
        one = len(silent) == 1
        # After the listing, which goes to stdout: the note is commentary, like every other
        # line this tool writes about what it did, and the two must not interleave.
        sys.stdout.flush()
        print(
            f"note: the project also names {_listed(silent)}, which "
            f"{'provides' if one else 'provide'} no artefact of its own; the c artefact "
            f"renders any template reading such a plugin's block",
            file=sys.stderr,
        )
    # Flushed again unconditionally: the note above only flushes when it is printed, and the
    # listing (stdout) must not interleave with the findings (stderr) that follow it either way,
    # in a buffered pipe.
    sys.stdout.flush()
    _report(bag, "text")
    return code


def _command_sources(args: argparse.Namespace) -> int:
    """The files the project is made of, for the dependency list of a build system.

    Deliberately tolerant: a project whose interfaces disagree still has a well defined set
    of source files, and a build system asking what to watch should get an answer even while
    the project does not check out. Only a root file that cannot be read at all is fatal,
    and the exit code says so in both output formats. A finding beyond that - a missing
    include, say - is still reported, beside the listing rather than instead of it: on
    stderr in text, already carried by the diagnostics document in json.

    What the project names is listed whether or not it loaded: a plugin that stopped
    importing (``plugin-invalid``), is missing (``plugin-not-found``), or whose model raises
    (``plugin-invalid``) is a finding beside the listing, and its file stays among the
    sources where one is known, so that the build which hears of the defect also hears of its
    repair. ``-W`` and ``--strict`` mean what they mean on ``check``: they grade what is
    reported, never what is listed, and the exit code stays 0.
    """
    from ddd.loading import load_workspace

    # The policy the build runs under, so that a check it relaxed is not reported here either:
    # the findings only say what the other commands would say of the same project.
    bag = DiagnosticBag(SeverityPolicy.from_strings(args.severity, strict=args.strict))
    workspace = load_workspace(
        args.project, bag, plugin_defects_are_findings=True, run_plugins=not args.no_plugins
    )
    code = _verdict(EXIT_FINDINGS if workspace is None else EXIT_OK)
    if args.format == "json":
        payload = {
            "sources": [path.as_posix() for path in workspace.sources()]
            if workspace is not None
            else [],
            **_diagnostics_payload(bag),
        }
        print(json.dumps(payload, indent=2))
        return code
    if workspace is None:
        _report(bag, "text")
        return code
    for path in workspace.sources():
        print(path.as_posix())
    sys.stdout.flush()
    _report(bag, "text")
    return code


def _command_checks(args: argparse.Namespace) -> int:
    """List the registry: identifier, default severity, and what sets a check apart.

    ``(fixed)`` says the severity cannot be relaxed; ``(project)`` says the check needs every
    component of a project, which is what ``--standalone`` holds it back for; ``(comparison)``
    says it grades a delivery comparison rather than one project. The three are independent in
    principle, so a check carrying more than one lists them together, in the order ``CheckInfo``
    declares the underlying flags in. JSON carries the same facts as ``overridable``,
    ``needs_every_component`` and ``comparison`` on every entry, so a build script can tell them
    apart without parsing the text markers.
    """
    plugins = _plugins_from_arguments(args.plugin)
    infos = [*CHECKS.values(), *(info for plugin in plugins for info in plugin.checks)]
    if args.format == "json":
        print(
            json.dumps(
                [
                    {
                        "check": info.identifier,
                        "default_severity": info.default_severity.value,
                        "description": info.description,
                        "overridable": info.overridable,
                        "needs_every_component": info.needs_every_component,
                        "comparison": info.comparison,
                    }
                    for info in infos
                ],
                indent=2,
            )
        )
        return EXIT_OK
    width = max(len(info.identifier) for info in infos)
    for info in infos:
        markers = [
            label
            for keep, label in (
                (not info.overridable, "fixed"),
                (info.needs_every_component, "project"),
                (info.comparison, "comparison"),
            )
            if keep
        ]
        marked = f" ({', '.join(markers)})" if markers else ""
        print(
            f"{info.identifier:<{width}}  {info.default_severity.value:<7}  "
            f"{info.description}{marked}"
        )
    return EXIT_OK


def _analyze(
    args: argparse.Namespace, stream: Any = None, *, verify: bool = True
) -> tuple[Resolved | None, DiagnosticBag]:
    """Load and analyse ``args.project`` under the run's policy.

    ``verify`` is left to the caller by ``ddd check --baseline`` alone, which knows the
    plugins of the run only once the baseline has been read as well.
    """
    from ddd.analysis import analyze
    from ddd.loading import load_workspace

    # The standalone policy goes first, so that an explicit -W on the same run overrides it:
    # the flag sets the floor for a component read alone, the caller still has the last word.
    standalone = list(STANDALONE_POLICY) if getattr(args, "standalone", False) else []
    policy = SeverityPolicy.from_strings(
        args.severity, floor=standalone, strict=args.strict, standalone=bool(standalone)
    )
    bag = DiagnosticBag(policy)
    # The load is inside the block too: a plugin's model that raises while a block is validated
    # is a usage error like a hook that raises, and the findings gathered before it are the
    # project's, printed first - in json, as the document the format promises.
    with _reported_on_failure(bag, args.format, stream):
        workspace = load_workspace(
            args.project, bag, run_plugins=not getattr(args, "no_plugins", False)
        )
        if workspace is None:
            # Nothing was read, so nothing says which plugins this project names: holding a
            # `-W` naming one of their checks to an empty registry would blame the command
            # line for a file the run could not open.
            return None, bag
        # An override naming a plugin check is verified once the project is read - only then
        # is it known which plugins loaded - so this has to sit inside the block: the
        # load-time findings gathered by then are reported before the usage error, as
        # `compare` already does. Before the gate below rather than after it, because the
        # plugins are loaded by the time an include goes missing: verified afterwards, a typo
        # on the command line surfaced only on the first run that happened to load cleanly,
        # which is the run that no longer needed telling.
        if verify:
            _verify_overrides(bag)
        if bag.has_errors:
            return None, bag
        # A plugin hook that raises is a usage error naming the plugin (section 3.11); the
        # findings collected before the hook ran are the project's, and are printed first.
        dictionary = analyze(workspace, bag)
    resolved = Resolved(
        dictionary,
        workspace.plugins,
        workspace.locate,
        True,
        workspace.sources(),
        workspace.settings,
        skipped=workspace.skipped,
    )
    return resolved, bag


def _refuse_a_directory(path: Path, option: str) -> None:
    """Refuse an output path with no file name of its own, in the tool's own words.

    ``-o .``, ``-o ..`` and ``-o C:/`` name a place rather than a file. The writer stages
    every file beside its target, and a path with no final component has nothing to stage
    beside: what came out was python's ``WindowsPath('.') has an empty name``, printed as the
    whole of what the run had to say about a mistake as ordinary as a missing file name.
    """
    if not path.name:
        msg = f"{option} names a directory, '{path.as_posix()}'; give it a file to write"
        raise ValueError(msg)


def _files_the_run_read(
    resolved: Resolved,
    image: Path | None,
    address_map: Path | None,
    fragment: Path | None,
    template_dir: Path | None,
) -> frozenset[Path]:
    """Every file ``generate`` read, which nothing it writes may be.

    The descriptions and the plugins - what the project is made of - and with them what the
    artefacts are made from: the image, the address map, the a2l module fragment and every
    template under the template directory, at any depth, a helper included, since a template
    reaches any of them by name. Nothing else there is read: a run that writes into its own
    template directory finds its earlier output beside the templates, and writes it again.
    Resolved as the sources are, to be compared with a path resolved the same way.
    """
    from ddd.backends.c.backend import TEMPLATE_SUFFIX
    from ddd.loading import resolve_path

    reads = set(resolved.sources)
    reads.update(resolve_path(path) for path in (image, address_map, fragment) if path is not None)
    if template_dir is not None:
        reads.update(
            resolve_path(path)
            for path in template_dir.rglob(f"*{TEMPLATE_SUFFIX}")
            if path.is_file()
        )
    return frozenset(reads)


def _refuse_a_description_name(path: Path) -> None:
    """Refuse an output path named as a description, for the commands that never read one.

    ``ddd schema component -o a.ddd.json`` and ``ddd build-info P -o a.ddd.json`` replaced a
    hand-written description with a schema or a record, and neither had read the file to be
    compared with. No schema (``ddd_<kind>.schema.json``) and no record (``ddd-build.json``) is
    named so, which is what makes the name enough to refuse.
    """
    from ddd.loading import DDD_SUFFIX

    if path.name.lower().endswith(DDD_SUFFIX):
        msg = (
            f"-o names a description, '{path.as_posix()}', and what this command writes is "
            f"not one; give it another name"
        )
        raise ValueError(msg)


def _refuse_a_source(
    path: Path, option: str, *sources: Path, advice: str = "give it a file of its own"
) -> None:
    """Refuse an output path that names a file this run read; a usage error naming it.

    ``-o``, ``--renames`` and ``--dictionary`` each name a file on the command line, and the
    obvious way to get one wrong is to complete the name of a description sitting in the same
    directory: the run then replaced a hand-written source with the dictionary or with a list
    of renames, reported `wrote ...` and exited 0, and the next command over the project read
    whatever had landed there. Nothing DDD writes is ever a file it read, so the pair is
    always a mistake rather than a request, and it is refused before anything is written.

    Compared on the resolved path, as the sources themselves are, so that an alias, a
    relative spelling or a junction cannot slip past the comparison.
    """
    from ddd.loading import resolve_path

    if resolve_path(path) in set(sources):
        msg = f"{option} would write over '{path.as_posix()}', which this run reads; {advice}"
        raise ValueError(msg)


def _diagnostics_payload(bag: DiagnosticBag) -> dict[str, Any]:
    return {
        "diagnostics": [diagnostic.to_dict() for diagnostic in bag.sorted],
        "summary": {
            severity.value: bag.count(severity)
            for severity in (Severity.ERROR, Severity.WARNING, Severity.INFO)
        },
    }


def _report(bag: DiagnosticBag, output_format: str, stream: Any = None) -> None:
    """Print the findings; ``stream`` overrides where the machine readable form goes."""
    if output_format == "json":
        print(json.dumps(_diagnostics_payload(bag), indent=2), file=stream)
        return
    root = Path.cwd()
    for diagnostic in bag.sorted:
        print(diagnostic.render(root), file=sys.stderr)
    if len(bag):
        print(bag.summary(), file=sys.stderr)


@contextlib.contextmanager
def _reported_on_failure(
    bag: DiagnosticBag, output_format: str, stream: Any = None
) -> Iterator[None]:
    """Print the findings gathered so far if what follows turns into a usage error.

    Every command analyses first and produces something second - a rename list, an address
    map read, the artefacts - and ``main`` turns a failure of the second half into one line
    and exit 2. Without this the findings of the first half were gone with it, and the run
    that failed is exactly the run whose findings the reader needs. ``stream`` is forwarded
    to ``_report`` unchanged, so a caller whose successful report does not go to stdout - only
    ``dump``, today - keeps that promise on the failing path too.

    ``check``, ``compare``, ``generate`` and ``dump -o`` - the commands that produce something
    after the analysis - each wrap the whole of it in one such block, not the particular calls
    someone thought could fail: a usage error can come from any statement in between,
    including one nobody expected to raise, and the one that surprises us is exactly the one
    this has to cover. ``list``, ``artefacts``, ``sources`` and a ``dump`` to stdout have
    nothing fallible after their analysis today and so establish no block; a step added to one
    of them later belongs inside a block of its own.
    """
    try:
        yield
    except (OSError, ValueError):
        # A stdout that fails while the findings are printed must not turn into a second
        # attempt; the original error is what `main` still has to report.
        with contextlib.suppress(OSError, ValueError):
            _report(bag, output_format, stream)
        raise


def _init_cell(entry: Comparable) -> str:
    """The raw init of one row and, where the conversion gives it one, its physical reading.

    Raw first, because raw is what the file states and the generated c carries verbatim; the
    reading in parentheses is the forward conversion, which every raw scalar has. A nested
    init is abbreviated to ``[...]``, because the table is one line per variable and a map's
    worth of numbers belongs to the hover and the calibration tool. Text output only: the
    json payload of ``ddd list`` is a published shape and carries the raw value as data.
    """
    from ddd.models import format_number, raw_reading

    init = entry.init
    if init is None:
        return "-"
    if isinstance(init, str):
        # Quoted, so that text cannot be mistaken for a number, and spelled the way json
        # spells it, which is the way the file does; a string has no reading to add.
        return json.dumps(init)
    if isinstance(init, tuple):
        return "[...]"
    reading = raw_reading(entry.conversion, init, entry.unit)
    stated = format_number(init)
    return f"{stated} (= {reading})" if reading is not None else stated


def _display_width(text: str) -> int:
    """Columns a terminal spends on ``text``, which is not always its number of code points.

    The table padded with ``str.ljust``, which counts code points: a unit such as ``温度`` is
    two of them and four columns wide, so its row got the padding of a two-column cell and
    every cell after it started two columns right of its header. The East Asian width property
    is what says which characters are drawn double width - ``W`` for the ones that always are,
    ``F`` for the full width forms of characters that also have a half width one - and it is
    the rule every terminal and every pager applies. ``°C``, ``µs`` and the accented letters a
    description is otherwise likely to carry are narrow and unaffected.
    """
    return sum(2 if unicodedata.east_asian_width(character) in "WF" else 1 for character in text)


def _print_table(dictionary: DataDictionary) -> None:
    from ddd.models import format_shape

    rows = [("VARIABLE", "KIND", "DATATYPE", "UNIT", "SHAPE", "INIT", "PRODUCER", "CONSUMERS")]
    for entry in dictionary.listed:
        owner = entry.owner or "<unresolved>"
        rows.append(
            (
                entry.name,
                entry.kind.value,
                entry.datatype.value,
                entry.unit or "-",
                # As the project spells it: a dimension stated as a constant shows its name,
                # which is also how the generated code declares the array.
                format_shape(entry.spelled_shape) or "-",
                _init_cell(entry),
                f"{owner}{' (local)' if entry.local else ''}",
                ", ".join(entry.consumers) or "-",
            )
        )
    widths = [max(_display_width(row[column]) for row in rows) for column in range(len(rows[0]))]
    for row in rows:
        # Padded by hand rather than with `str.ljust`, which counts code points and would
        # leave a wide cell pushing the rest of its row to the right.
        cells = (
            value + " " * (width - _display_width(value))
            for value, width in zip(row, widths, strict=True)
        )
        print("  ".join(cells).rstrip())
