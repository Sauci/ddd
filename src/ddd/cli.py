"""Command line interface of DDD."""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from ddd import __version__
from ddd.analysis import analyze
from ddd.backends import (
    A2lBackend,
    A2lOptions,
    Backend,
    ByteOrder,
    CBackend,
    COptions,
    WriteStatus,
    addressed_symbols,
    example_template_directory,
    load_address_map,
    render,
    write,
)
from ddd.build_info import BuildInfo, build_info_text
from ddd.compare import compare, renames
from ddd.diagnostics import (
    CHECKS,
    DiagnosticBag,
    Location,
    Severity,
    SeverityPolicy,
    UnknownCheckError,
)
from ddd.identity import UNREADABLE, assign
from ddd.ir import Comparable, DataDictionary
from ddd.loading import load_dictionary, load_workspace
from ddd.models import (
    ComponentFile,
    ConstantsFile,
    ProjectFile,
    RastersFile,
    SectionsFile,
    TypesFile,
    UnitsFile,
    format_number,
    format_shape,
    raw_reading,
)
from ddd.models.schema import PublishedSchema
from ddd.plugins import (
    PLUGIN_NAME_PATTERN,
    Plugin,
    PluginInvalidError,
    PluginNotFoundError,
    backend_of,
    load_plugin,
    run_compare_hooks,
)

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 2

GENERATOR = f"ddd {__version__}"
BUILT_IN_ARTEFACTS = ("c", "a2l", "all")


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
    if reconfigure is not None:  # pragma: no branch - absent only on a replaced stream
        with contextlib.suppress(OSError, ValueError):
            reconfigure(encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point of the ``ddd`` command; returns the process exit code."""
    _write_utf8(sys.stdout)
    _write_utf8(sys.stderr)
    arguments = list(sys.argv[1:] if argv is None else argv)
    parser = _build_parser(_plugin_artefact(arguments))
    args = parser.parse_args(arguments)
    try:
        handler: Any = args.handler
        return int(handler(args))
    except UnknownCheckError as error:
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
        if name not in BUILT_IN_ARTEFACTS and PLUGIN_NAME_PATTERN.match(name):
            return name
    return None


def _build_parser(plugin_artefact: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ddd",
        description=(
            "Data dictionary for the global variables of a component based "
            "embedded software project."
        ),
    )
    parser.add_argument("-v", "--version", action="version", version=f"ddd {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser(
        "check", help="verify the consistency of the interfaces of a project"
    )
    _add_common_arguments(check)
    check.add_argument(
        "--baseline",
        type=Path,
        help="also verify that the project can still replace this published dictionary",
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
            "address map. 'all' produces both in one run; 'a2l' is the run a build repeats "
            "after linking, when the addresses are known but the c must not change."
        ),
    )
    # One subparser per artefact rather than steering flags on a single command: the two
    # backends do not want the same options, and a flag pair like --no-a2l/--a2l-only would
    # leave every run carrying the other backend's options as noise it must not use.
    artefacts = generate.add_subparsers(
        dest="artefact", required=True, metavar="{c,a2l,all,<plugin>}"
    )
    for name, description, with_c, with_a2l in (
        ("c", "render the c sources from the project's jinja2 templates", True, False),
        ("a2l", "write the a2l file, with the addresses --address-map carries", False, True),
        ("all", "render the c sources and write the a2l file in one run", True, True),
    ):
        _add_generate_arguments(
            artefacts.add_parser(name, help=description), with_c=with_c, with_a2l=with_a2l
        )
    if plugin_artefact is not None:
        extra = artefacts.add_parser(
            plugin_artefact, help="write the artefact the plugin of that name provides"
        )
        _add_generate_arguments(extra, with_c=False, with_a2l=False)
        extra.set_defaults(plugin_artefact=plugin_artefact)

    listing = subparsers.add_parser("list", help="list the global variables of a project")
    _add_common_arguments(listing)
    listing.set_defaults(handler=_command_list)

    dump = subparsers.add_parser(
        "dump", help="print the resolved data dictionary, the contract the backends consume"
    )
    _add_common_arguments(dump)
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
            "directory holding a build of this project; repeatable. Without it the usual "
            "build directory names next to the workspace are searched"
        ),
    )
    lsp.set_defaults(handler=_command_lsp)

    build_info = subparsers.add_parser(
        "build-info",
        help="record how a build configured DDD, for an editor to pick up",
        description=(
            "Writes the project description a build runs DDD on, and the severity policy it "
            "applies, into a small json file. A build system calls this at configure time so "
            "that an editor can report what the build reports. The project description is "
            "recorded rather than read: with CMake it is often generated later in the same "
            "configure run, out of the link graph."
        ),
    )
    build_info.add_argument("project", type=Path, help="project or component description file")
    build_info.add_argument(
        "-o", "--output", type=Path, required=True, help="file to write the result to"
    )
    build_info.add_argument("--image", default="", help="name of the build target this belongs to")
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
    schema.add_argument("kind", choices=[*sorted(_SCHEMA_MODELS), SCHEMA_ALL])
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

    sources = subparsers.add_parser(
        "sources",
        help="list every description file a project is built out of",
        description=(
            "Prints one absolute path per line: the project file and every file it includes "
            "however deeply. A build system needs exactly this "
            "to know when the generated files are out of date, because a project pulls its "
            "components in through 'includes' and none of them is named on the command line."
        ),
    )
    sources.add_argument("project", type=Path, help="project or component description file")
    sources.add_argument("--format", choices=["text", "json"], default="text", help="output format")
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

    return parser


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("project", type=Path, help="project or component description file")
    _add_policy_arguments(parser)


def _add_generate_arguments(
    parser: argparse.ArgumentParser, *, with_c: bool, with_a2l: bool
) -> None:
    """The options of one ``generate`` artefact; only the selected backends contribute any."""
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
            required=True,
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
            help="declare input variables const in the consumer headers",
        )
    if with_a2l:
        parser.add_argument(
            "--byte-order",
            choices=[order.value for order in ByteOrder],
            default=ByteOrder.LITTLE.value,
            help="byte order reported in the a2l file, default: %(default)s",
        )
        parser.add_argument(
            "--address-map",
            type=Path,
            help="json file mapping variable names to their address in the target",
        )
    parser.add_argument(
        "--dry-run", action="store_true", help="report what would be written, write nothing"
    )
    parser.add_argument(
        "--force", action="store_true", help="generate even if the consistency check fails"
    )
    parser.set_defaults(handler=_command_generate, render_c=with_c, render_a2l=with_a2l)


def _add_policy_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-W",
        "--severity",
        action="append",
        default=[],
        metavar="CHECK=SEVERITY",
        help="change the severity of a check (error, warning, info, ignore); repeatable",
    )
    parser.add_argument("--strict", action="store_true", help="report warnings as errors")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="output format")


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


def _plugins_from_arguments(
    specs: Sequence[str], bag: DiagnosticBag | None = None
) -> tuple[Plugin, ...]:
    """The plugins ``--plugin`` names, loaded relative to the working directory.

    A failure is a usage error rather than a finding: there is no project file to locate it
    in, and the mistake is on the command line. The checks are registered on ``bag`` when
    one is given, so that a provisional override can be verified against them.
    """
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
    resolved, bag = _analyze(args)
    dictionary = resolved.dictionary if resolved is not None else None
    # With a baseline, one command answers both questions and returns one exit code, which
    # is what a ci job wants: is the project consistent, and is it still a replacement?
    if resolved is not None and args.baseline is not None:
        baseline = _read_baseline(args.baseline, bag)
        if baseline is not None:
            compare(baseline, resolved.dictionary, bag, location=Location(args.project))
            run_compare_hooks(
                resolved.plugins,
                baseline,
                resolved.dictionary,
                bag,
                resolved.locate,
                Location(args.project),
            )
    _report(bag, args.format)
    if args.format == "json":
        return EXIT_FINDINGS if bag.has_errors else EXIT_OK
    if dictionary is not None and not len(bag):
        count = len(dictionary.listed)
        components = len(dictionary.components)
        print(
            f"ok: {count} variable{'s' if count != 1 else ''} in "
            f"{components} component{'s' if components != 1 else ''} are consistent",
            file=sys.stderr,
        )
    return EXIT_FINDINGS if bag.has_errors else EXIT_OK


def _command_compare(args: argparse.Namespace) -> int:
    policy = SeverityPolicy.from_strings(args.severity, strict=args.strict)
    bag = DiagnosticBag(policy)
    # The baseline is a delivery that has already gone out; its own findings are not this
    # run's business. The candidate's are, which is why only it shares the bag - checking a
    # project description and comparing it are both reported by one `ddd compare`.
    baseline = _read_baseline(args.baseline, bag)
    candidate = _read_dictionary(args.candidate, bag)
    if baseline is None or candidate is None:
        _report(bag, args.format)
        return EXIT_FINDINGS

    plugins = candidate.plugins
    if args.plugin:
        if candidate.from_description:
            msg = (
                "--plugin names the plugins of an archived dictionary; a project description "
                "names its own"
            )
            raise ValueError(msg)
        plugins = _plugins_from_arguments(args.plugin, bag)
    bag.policy.verify(bag.registered)

    location = Location(args.candidate)
    paired = compare(baseline, candidate.dictionary, bag, location=location)
    run_compare_hooks(plugins, baseline, candidate.dictionary, bag, candidate.locate, location)
    if args.renames is not None:
        # Written whether or not the comparison found errors: a delivery that cannot be
        # accepted still needs its renames listed, so that whoever fixes it knows what moved.
        args.renames.write_text(json.dumps(renames(paired), indent=2) + "\n", encoding="utf-8")
    _report(bag, args.format)
    if args.format != "json":
        # The file names, not the project names: two deliveries of one project share a name.
        verdict = "cannot" if bag.has_errors else "can"
        print(
            f"{args.candidate.name} {verdict} replace {args.baseline.name}",
            file=sys.stderr,
        )
    return EXIT_FINDINGS if bag.has_errors else EXIT_OK


def _check_address_coverage(
    dictionary: DataDictionary, addresses: dict[str, int], path: Path, bag: DiagnosticBag
) -> None:
    """Report the objects a supplied address map does not cover, and the entries nobody wants.

    Only when a map was given: without one every address is zero on purpose, because that is
    the run a build makes before it has linked anything. With one, a symbol the map does not
    carry silently became address zero - and the map is written by a linker script or a patch
    tool against the names of one build, so a renamed variable or a stale file covers some of
    the objects and not the rest. What comes out is an a2l pointing a calibration tool at
    0x00000000, which reads and writes something, and nothing in the run said so.

    The entries that match nothing are named in a note rather than as a finding of their own:
    they are usually the other half of the same mistake - the old spelling of the symbol that
    has just gone missing - and reading them together is what identifies a rename.
    """
    carried = addressed_symbols(dictionary)
    missing = [symbol for symbol in carried if symbol not in addresses]
    if not missing:
        return
    unused = sorted(set(addresses) - set(carried))
    notes: list[tuple[str, Location | None]] = []
    if unused:
        notes.append((f"the map also carries {_listed(unused)}, which the a2l does not", None))
    bag.add(
        "address-missing",
        f"the address map has no entry for {_listed(missing)}; "
        f"{'it reaches' if len(missing) == 1 else 'they reach'} the a2l at address 0",
        Location(path),
        notes=notes,
    )


_LISTED_LIMIT = 5
"""How many names a finding spells out before it starts counting instead."""


def _listed(names: list[str]) -> str:
    """``'A', 'B' and 3 others``: enough to recognise, never a screenful."""
    spelled = ", ".join(f"'{name}'" for name in names[:_LISTED_LIMIT])
    rest = len(names) - _LISTED_LIMIT
    return f"{spelled} and {rest} other{'s' if rest != 1 else ''}" if rest > 0 else spelled


def _command_generate(args: argparse.Namespace) -> int:
    resolved, bag = _analyze(args)
    dictionary = resolved.dictionary if resolved is not None else None
    if dictionary is None:
        _report(bag, args.format)
        return EXIT_FINDINGS
    assert resolved is not None  # dictionary is only set from resolved; narrows it for mypy

    addresses = load_address_map(args.address_map) if getattr(args, "address_map", None) else {}
    if args.render_a2l and args.address_map is not None:
        # Before the gate below, so that a --strict build stops rather than writing a file
        # whose addresses it has just been told are incomplete.
        _check_address_coverage(dictionary, addresses, args.address_map, bag)
    if bag.has_errors and not args.force:
        _report(bag, args.format)
        return EXIT_FINDINGS

    backends: list[Backend] = []
    if args.render_c:
        backends.append(
            CBackend(args.template_dir, COptions(const_inputs=args.const_inputs), GENERATOR)
        )
    if args.render_a2l:
        backends.append(
            A2lBackend(
                A2lOptions(byte_order=ByteOrder(args.byte_order), addresses=addresses),
                GENERATOR,
            )
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
        backends.append(backend_of(plugin, dictionary, GENERATOR))
    files = render(dictionary, backends, args.output_dir)
    try:
        results = write(files, dry_run=args.dry_run)
    except OSError as error:
        # The output directory is the one thing a caller gets wrong regularly - a path that
        # is a file, or one nothing may be written to. Naming it beats the bare errno text.
        msg = f"cannot write into '{args.output_dir.as_posix()}': {error.strerror or error}"
        raise OSError(msg) from None

    if args.format == "json":
        payload = _diagnostics_payload(bag)
        payload["generated"] = [
            {"path": result.path.as_posix(), "status": result.status.value} for result in results
        ]
        print(json.dumps(payload, indent=2))
    else:
        _report(bag, args.format)
        prefix = "would write" if args.dry_run else "wrote"
        for result in results:
            if result.status is WriteStatus.UNCHANGED:
                print(f"unchanged   {result.path.as_posix()}", file=sys.stderr)
            else:
                print(
                    f"{prefix:<11} {result.path.as_posix()} ({result.status.value})",
                    file=sys.stderr,
                )
    return EXIT_FINDINGS if bag.has_errors else EXIT_OK


def _command_list(args: argparse.Namespace) -> int:
    resolved, bag = _analyze(args)
    dictionary = resolved.dictionary if resolved is not None else None
    if dictionary is None:
        _report(bag, args.format)
        return EXIT_FINDINGS

    if args.format == "json":
        print(
            json.dumps(
                {
                    "project": dictionary.name,
                    "components": [
                        component.model_dump(mode="json") for component in dictionary.components
                    ],
                    "variables": [entry.model_dump(mode="json") for entry in dictionary.listed],
                    **_diagnostics_payload(bag),
                },
                indent=2,
            )
        )
    else:
        _print_table(dictionary)
        _report(bag, args.format)
    return EXIT_FINDINGS if bag.has_errors else EXIT_OK


def _command_dump(args: argparse.Namespace) -> int:
    """Emit the data dictionary itself, so that another tool can generate from it.

    stdout carries the dictionary and nothing else, in both formats: ``ddd dump > baseline.json``
    is the documented way to archive a delivery, so a second json document must not appear
    there. ``--format json`` therefore selects the format of the *diagnostics*, which go to
    stderr - where they also stay out of the way of a pipe.
    """
    resolved, bag = _analyze(args)
    dictionary = resolved.dictionary if resolved is not None else None
    if dictionary is not None:
        print(dictionary.model_dump_json(indent=2))
    _report(bag, args.format, stream=sys.stderr)
    if dictionary is None:
        return EXIT_FINDINGS
    return EXIT_FINDINGS if bag.has_errors else EXIT_OK


def _command_id(args: argparse.Namespace) -> int:
    """Stamp identities into description files, reporting what was written."""
    written = 0
    skipped: list[Path] = []
    for path in args.files:
        count = assign(path)
        if count == UNREADABLE:
            skipped.append(path)
        else:
            written += count
    for path in skipped:
        print(f"{path}: not readable as json, skipped", file=sys.stderr)
    print(f"wrote {written} id{'' if written == 1 else 's'}", file=sys.stderr)
    return EXIT_FINDINGS if skipped else EXIT_OK


_SCHEMA_MODELS: dict[str, type[BaseModel]] = {
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
    # by_alias so that the key is '$schema' rather than the python attribute name, and
    # PublishedSchema so that what an editor shows is documentation rather than python.
    published = _SCHEMA_MODELS[kind].model_json_schema(
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
    definitions: dict[str, Any] = schema.setdefault("$defs", {})
    targets = [
        node
        for node in (schema, *definitions.values())
        if "extensions" in node.get("properties", {})
    ]
    properties: dict[str, Any] = {}
    for plugin in plugins:
        model = plugin.project_model if on_project else plugin.object_model
        if model is None:
            continue
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

    return serve(args.build_directory)


def _command_build_info(args: argparse.Namespace) -> int:
    # Built rather than recorded blindly: a typo in a severity override would otherwise be
    # copied into the file as a policy nobody can apply, and would surface at build time
    # instead of here, while the project is being configured.
    SeverityPolicy.from_strings(args.severity, strict=args.strict)
    info = BuildInfo(
        # Absolute, because whoever reads this file is not in the directory the build ran in.
        project=args.project.resolve().as_posix(),
        image=args.image,
        strict=args.strict,
        severity=tuple(args.severity),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # newline="" for the same reason the schemas use it: a file committed or compared across
    # platforms must not differ by its line endings alone.
    args.output.write_text(build_info_text(info), encoding="utf-8", newline="")
    print(f"wrote {args.output.as_posix()}", file=sys.stderr)
    return EXIT_OK


def _write_schema(path: Path, kind: str, plugins: Sequence[Plugin] = ()) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # newline="" keeps the line endings as written on every platform, the same discipline the
    # generated sources follow: a schema committed from Windows must not differ from the same
    # schema committed from linux.
    path.write_text(schema_text(kind, plugins), encoding="utf-8", newline="")
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
        for kind in sorted(_SCHEMA_MODELS):
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
    directory = example_template_directory()
    if directory is None:
        print("ddd: the example templates are not part of this installation", file=sys.stderr)
        return EXIT_USAGE
    print(directory.as_posix())
    return EXIT_OK


def _command_sources(args: argparse.Namespace) -> int:
    """The files the project is made of, for the dependency list of a build system.

    Deliberately tolerant: a project whose interfaces disagree still has a well defined set
    of source files, and a build system asking what to watch should get an answer even while
    the project does not check out. Only a root file that cannot be read at all is fatal,
    and the exit code says so in both output formats.
    """
    bag = DiagnosticBag()
    workspace = load_workspace(args.project, bag)
    if args.format == "json":
        payload = {
            "sources": [path.as_posix() for path in workspace.sources()]
            if workspace is not None
            else [],
            **_diagnostics_payload(bag),
        }
        print(json.dumps(payload, indent=2))
        return EXIT_FINDINGS if workspace is None else EXIT_OK
    if workspace is None:
        _report(bag, "text")
        return EXIT_FINDINGS
    for path in workspace.sources():
        print(path.as_posix())
    return EXIT_OK


def _command_checks(args: argparse.Namespace) -> int:
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
                    }
                    for info in infos
                ],
                indent=2,
            )
        )
        return EXIT_OK
    width = max(len(info.identifier) for info in infos)
    for info in infos:
        fixed = "" if info.overridable else " (fixed)"
        print(
            f"{info.identifier:<{width}}  {info.default_severity.value:<7}  "
            f"{info.description}{fixed}"
        )
    return EXIT_OK


@dataclass(frozen=True, slots=True)
class Resolved:
    """A dictionary and what a plugin's hook needs beside it.

    A description resolved on the spot keeps its plugins and can point a finding at a
    declaration; an archived dump has neither, so its plugins come from ``--plugin`` and a
    finding points at the file.
    """

    dictionary: DataDictionary
    plugins: tuple[Plugin, ...]
    locate: Callable[[str], Location | None]
    from_description: bool


def _analyze(args: argparse.Namespace) -> tuple[Resolved | None, DiagnosticBag]:
    policy = SeverityPolicy.from_strings(args.severity, strict=args.strict)
    bag = DiagnosticBag(policy)
    workspace = load_workspace(args.project, bag)
    if workspace is None or bag.has_errors:
        return None, bag
    bag.policy.verify(bag.registered)
    dictionary = analyze(workspace, bag)
    return Resolved(dictionary, workspace.plugins, workspace.locate, True), bag


def _read_dictionary(path: Path, bag: DiagnosticBag) -> Resolved | None:
    """A dumped dictionary, or a project/component description resolved into one.

    Accepting both is what makes the command usable in a pipeline: the baseline is normally
    an archived dump, while the candidate is the project sitting in the working tree.
    """
    if _holds_a_description(path):
        workspace = load_workspace(path, bag)
        if workspace is None or bag.has_errors:
            return None
        return Resolved(analyze(workspace, bag), workspace.plugins, workspace.locate, True)
    dictionary = load_dictionary(path, bag)
    if dictionary is None:
        return None
    return Resolved(dictionary, (), lambda _: Location(path), False)


def _read_baseline(path: Path, bag: DiagnosticBag) -> DataDictionary | None:
    """Resolve the baseline side of a comparison, in a bag of its own.

    A baseline given as a project description has to be analysed to become a dictionary, and
    that analysis produces findings about *that* delivery: files that are not part of the
    project under check, an output nobody read two releases ago. Reported here they would be
    attributed to this run, printed twice when both sides are the same tree, and would fail a
    clean project because of its predecessor. Only the errors that stop the baseline from
    being read at all are carried over, because those explain a comparison that cannot happen.
    """
    own = DiagnosticBag(bag.policy)
    resolved = _read_dictionary(path, own)
    if resolved is not None and not own.has_errors:
        return resolved.dictionary
    for diagnostic in own.sorted:
        if diagnostic.severity is Severity.ERROR:
            bag.add(
                diagnostic.check,
                f"in the baseline: {diagnostic.message}",
                diagnostic.location,
                diagnostic.notes,
            )
    return None


def _holds_a_description(path: Path) -> bool:
    """True for a project or component file; a broken file is left to the reader to report.

    ``utf-8-sig`` for the reason the loader reads with it: a description file carrying a byte
    order mark is accepted by ``ddd check``, and sniffing it with plain utf-8 would misroute
    it here as a dumped dictionary.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(data, dict) and ("project" in data or "component" in data)


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


def _init_cell(entry: Comparable) -> str:
    """The raw init of one row and, where the conversion gives it one, its physical reading.

    Raw first, because raw is what the file states and the generated c carries verbatim; the
    reading in parentheses is the forward conversion, which every raw scalar has. A nested
    init is abbreviated to ``[...]``, because the table is one line per variable and a map's
    worth of numbers belongs to the hover and the calibration tool. Text output only: the
    json payload of ``ddd list`` is a published shape and carries the raw value as data.
    """
    init = entry.init
    if init is None:
        return "-"
    if isinstance(init, tuple):
        return "[...]"
    reading = raw_reading(entry.conversion, init, entry.unit)
    stated = format_number(init)
    return f"{stated} (= {reading})" if reading is not None else stated


def _print_table(dictionary: DataDictionary) -> None:
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
    widths = [max(len(row[column]) for row in rows) for column in range(len(rows[0]))]
    for row in rows:
        cells = (value.ljust(width) for value, width in zip(row, widths, strict=True))
        print("  ".join(cells).rstrip())
