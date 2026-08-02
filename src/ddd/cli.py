"""Command line interface of DDD."""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from collections.abc import Sequence
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
    example_template_directory,
    load_address_map,
    render,
    write,
)
from ddd.build_info import BuildInfo, build_info_text
from ddd.compare import compare
from ddd.diagnostics import (
    CHECKS,
    DiagnosticBag,
    Location,
    Severity,
    SeverityPolicy,
    UnknownCheckError,
)
from ddd.ir import DataDictionary
from ddd.loading import load_convention, load_dictionary, load_workspace
from ddd.models import ComponentFile, NamingFile, ProjectFile, TypesFile, format_shape
from ddd.models.schema import PublishedSchema
from ddd.naming import Inspection, complete, inspect, or_list

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 2

GENERATOR = f"ddd {__version__}"


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
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        handler: Any = args.handler
        return int(handler(args))
    except UnknownCheckError as error:
        print(f"ddd: {error}", file=sys.stderr)
        return EXIT_USAGE
    except (OSError, ValueError) as error:
        print(f"ddd: {error}", file=sys.stderr)
        return EXIT_USAGE


def _build_parser() -> argparse.ArgumentParser:
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
    _add_policy_arguments(compare_parser)
    compare_parser.set_defaults(handler=_command_compare)

    generate = subparsers.add_parser(
        "generate", help="generate the c sources and the a2l file of a project"
    )
    _add_common_arguments(generate)
    generate.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        required=True,
        help="directory the generated files are written to",
    )
    generate.add_argument(
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
            "extension, so ddd_globals.c.jinja2 produces ddd_globals.c; a name starting with "
            "an underscore is a helper that renders nothing on its own, and a name "
            "containing {component} is rendered once per component. 'ddd templates-dir' "
            "prints a set of example templates to copy from"
        ),
    )
    generate.add_argument(
        "--const-inputs",
        action="store_true",
        help="declare input variables const in the consumer headers",
    )
    generate.add_argument("--no-a2l", action="store_true", help="do not write an a2l file")
    generate.add_argument(
        "--byte-order",
        choices=[order.value for order in ByteOrder],
        default=ByteOrder.LITTLE.value,
        help="byte order reported in the a2l file, default: %(default)s",
    )
    generate.add_argument(
        "--address-map",
        type=Path,
        help="json file mapping variable names to their address in the target, for the a2l file",
    )
    generate.add_argument(
        "--dry-run", action="store_true", help="report what would be written, write nothing"
    )
    generate.add_argument(
        "--force", action="store_true", help="generate even if the consistency check fails"
    )
    generate.set_defaults(handler=_command_generate)

    listing = subparsers.add_parser("list", help="list the global variables of a project")
    _add_common_arguments(listing)
    listing.set_defaults(handler=_command_list)

    dump = subparsers.add_parser(
        "dump", help="print the resolved data dictionary, the contract the backends consume"
    )
    _add_common_arguments(dump)
    dump.set_defaults(handler=_command_dump)

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
    schema.set_defaults(handler=_command_schema)

    name_parser = subparsers.add_parser(
        "name",
        help="check and explain names against a naming convention",
        description=(
            "Splits every given name into its segments, says which part is wrong if any is, "
            "and spells out what each part means."
        ),
    )
    name_parser.add_argument("names", nargs="+", metavar="NAME", help="the names to look at")
    name_parser.add_argument(
        "-c", "--convention", type=Path, required=True, help="the naming convention file"
    )
    name_parser.add_argument(
        "--format", choices=["text", "json"], default="text", help="output format"
    )
    name_parser.set_defaults(handler=_command_name)

    complete_parser = subparsers.add_parser(
        "complete",
        help="list the names a prefix may grow into, for shell completion",
        description=(
            "Prints one candidate per line and always exits zero: a completion that fails "
            "loudly is worse than one that offers nothing."
        ),
    )
    complete_parser.add_argument("prefix", nargs="?", default="", help="what has been typed")
    complete_parser.add_argument(
        "-c", "--convention", type=Path, required=True, help="the naming convention file"
    )
    complete_parser.set_defaults(handler=_command_complete)

    sources = subparsers.add_parser(
        "sources",
        help="list every description file a project is built out of",
        description=(
            "Prints one absolute path per line: the project file, every file it includes "
            "however deeply, and the naming convention. A build system needs exactly this "
            "to know when the generated files are out of date, because a project pulls its "
            "components in through 'includes' and none of them is named on the command line."
        ),
    )
    sources.add_argument("project", type=Path, help="project or component description file")
    sources.set_defaults(handler=_command_sources)

    checks = subparsers.add_parser("checks", help="list the available consistency checks")
    checks.add_argument("--format", choices=["text", "json"], default="text", help="output format")
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


def _command_check(args: argparse.Namespace) -> int:
    dictionary, bag = _analyze(args)
    # With a baseline, one command answers both questions and returns one exit code, which
    # is what a ci job wants: is the project consistent, and is it still a replacement?
    if dictionary is not None and args.baseline is not None:
        baseline = _read_baseline(args.baseline, bag)
        if baseline is not None:
            compare(baseline, dictionary, bag, location=Location(args.project))
    _report(bag, args.format)
    if args.format == "json":
        return EXIT_FINDINGS if bag.has_errors else EXIT_OK
    if dictionary is not None and not len(bag):
        count = len(dictionary.objects)
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

    compare(baseline, candidate, bag, location=Location(args.candidate))
    _report(bag, args.format)
    if args.format != "json":
        # The file names, not the project names: two deliveries of one project share a name.
        verdict = "cannot" if bag.has_errors else "can"
        print(
            f"{args.candidate.name} {verdict} replace {args.baseline.name}",
            file=sys.stderr,
        )
    return EXIT_FINDINGS if bag.has_errors else EXIT_OK


def _command_generate(args: argparse.Namespace) -> int:
    dictionary, bag = _analyze(args)
    if dictionary is None or (bag.has_errors and not args.force):
        _report(bag, args.format)
        return EXIT_FINDINGS

    backends: list[Backend] = [
        CBackend(args.template_dir, COptions(const_inputs=args.const_inputs), GENERATOR)
    ]
    if not args.no_a2l:
        backends.append(
            A2lBackend(
                A2lOptions(
                    byte_order=ByteOrder(args.byte_order),
                    addresses=load_address_map(args.address_map) if args.address_map else {},
                ),
                GENERATOR,
            )
        )
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
    dictionary, bag = _analyze(args)
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
                    "variables": [entry.model_dump(mode="json") for entry in dictionary.objects],
                    "diagnostics": [d.to_dict() for d in bag.sorted],
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
    dictionary, bag = _analyze(args)
    if dictionary is not None:
        print(dictionary.model_dump_json(indent=2))
    _report(bag, args.format, stream=sys.stderr)
    if dictionary is None:
        return EXIT_FINDINGS
    return EXIT_FINDINGS if bag.has_errors else EXIT_OK


_SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "project": ProjectFile,
    "component": ComponentFile,
    "naming": NamingFile,
    "types": TypesFile,
    "dictionary": DataDictionary,
}

SCHEMA_ALL = "all"
"""``ddd schema all -o DIR`` writes every schema at once, for a project to commit."""

SCHEMA_FILENAME = "ddd_{kind}.schema.json"
"""How ``all`` names each file, so that a ``$schema`` path is predictable and stable."""


def _command_name(args: argparse.Namespace) -> int:
    bag = DiagnosticBag()
    convention = load_convention(args.convention, bag)
    if convention is None:
        _report(bag, "text")
        return EXIT_USAGE

    inspections = [inspect(name, convention) for name in args.names]
    if args.format == "json":
        print(json.dumps([_inspection_payload(i) for i in inspections], indent=2))
    else:
        for inspection in inspections:
            _print_inspection(inspection)
    return EXIT_OK if all(i.ok for i in inspections) else EXIT_FINDINGS


def _command_complete(args: argparse.Namespace) -> int:
    bag = DiagnosticBag()
    convention = load_convention(args.convention, bag)
    if convention is None:
        return EXIT_OK
    for candidate in complete(args.prefix, convention):
        print(candidate)
    return EXIT_OK


def _print_inspection(inspection: Inspection) -> None:
    if inspection.ok:
        print(f"{inspection.name}  ({inspection.convention.name})")
        for part in inspection.parts:
            segment = part.segment
            role = segment.name if segment else "?"
            meaning = part.meaning or (segment.description if segment else "")
            print(f"  {part.text:<24} {role:<12} {meaning}")
        return
    print(inspection.underline())
    for part in inspection.problems:
        suggestion = f" - did you mean {or_list(part.suggestions)}?" if part.suggestions else ""
        print(f"  {part.problem}{suggestion}")
    for segment in inspection.missing:
        print(f"  the {segment.name} part is missing: {segment.description or 'required'}")


def _inspection_payload(inspection: Inspection) -> dict[str, Any]:
    return {
        "name": inspection.name,
        "ok": inspection.ok,
        "convention": inspection.convention.name,
        "parts": [
            {
                "text": part.text,
                "start": part.start,
                "segment": part.segment.name if part.segment else None,
                "meaning": part.meaning,
                "problem": part.problem,
                "suggestions": list(part.suggestions),
            }
            for part in inspection.parts
        ],
        "missing": [segment.name for segment in inspection.missing],
    }


def schema_text(kind: str) -> str:
    """The json schema of one file format, as it is written out.

    One function so that a file on disk and the answer to ``ddd schema`` can never differ -
    which is what lets a test tell a project its committed schemas have gone stale.
    """
    # by_alias so that the key is '$schema' rather than the python attribute name, and
    # PublishedSchema so that what an editor shows is documentation rather than python.
    published = _SCHEMA_MODELS[kind].model_json_schema(
        by_alias=True, schema_generator=PublishedSchema
    )
    return json.dumps(published, indent=2) + "\n"


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


def _write_schema(path: Path, kind: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # newline="" keeps the line endings as written on every platform, the same discipline the
    # generated sources follow: a schema committed from Windows must not differ from the same
    # schema committed from linux.
    path.write_text(schema_text(kind), encoding="utf-8", newline="")
    print(f"wrote {path.as_posix()}", file=sys.stderr)


def _command_schema(args: argparse.Namespace) -> int:
    if args.kind == SCHEMA_ALL:
        if args.output is None:
            msg = (
                f"'{SCHEMA_ALL}' writes several files, so it needs a directory: "
                f"ddd schema {SCHEMA_ALL} -o schemas"
            )
            raise ValueError(msg)
        for kind in sorted(_SCHEMA_MODELS):
            _write_schema(args.output / SCHEMA_FILENAME.format(kind=kind), kind)
        return EXIT_OK

    if args.output:
        _write_schema(args.output, args.kind)
    else:
        print(schema_text(args.kind), end="")
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
    the project does not check out. Only a root file that cannot be read at all is fatal.
    """
    bag = DiagnosticBag()
    workspace = load_workspace(args.project, bag)
    if workspace is None:
        _report(bag, "text")
        return EXIT_FINDINGS
    for path in workspace.sources():
        print(path.as_posix())
    return EXIT_OK


def _command_checks(args: argparse.Namespace) -> int:
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
                    for info in CHECKS.values()
                ],
                indent=2,
            )
        )
        return EXIT_OK
    width = max(len(name) for name in CHECKS)
    for info in CHECKS.values():
        fixed = "" if info.overridable else " (fixed)"
        print(
            f"{info.identifier:<{width}}  {info.default_severity.value:<7}  "
            f"{info.description}{fixed}"
        )
    return EXIT_OK


def _analyze(args: argparse.Namespace) -> tuple[DataDictionary | None, DiagnosticBag]:
    policy = SeverityPolicy.from_strings(args.severity, strict=args.strict)
    bag = DiagnosticBag(policy)
    workspace = load_workspace(args.project, bag)
    if workspace is None or bag.has_errors:
        return None, bag
    return analyze(workspace, bag), bag


def _read_dictionary(path: Path, bag: DiagnosticBag) -> DataDictionary | None:
    """A dumped dictionary, or a project/component description resolved into one.

    Accepting both is what makes the command usable in a pipeline: the baseline is normally
    an archived dump, while the candidate is the project sitting in the working tree.
    """
    if _holds_a_description(path):
        workspace = load_workspace(path, bag)
        if workspace is None or bag.has_errors:
            return None
        return analyze(workspace, bag)
    return load_dictionary(path, bag)


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
    dictionary = _read_dictionary(path, own)
    if dictionary is not None and not own.has_errors:
        return dictionary
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
    """True for a project or component file; a broken file is left to the reader to report."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
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


def _print_table(dictionary: DataDictionary) -> None:
    rows = [("VARIABLE", "KIND", "DATATYPE", "UNIT", "SHAPE", "PRODUCER", "CONSUMERS")]
    for entry in dictionary.objects:
        owner = entry.owner or "<unresolved>"
        rows.append(
            (
                entry.name,
                entry.kind.value,
                entry.datatype.value,
                entry.unit or "-",
                format_shape(entry.shape) or "-",
                f"{owner}{' (local)' if entry.local else ''}",
                ", ".join(entry.consumers) or "-",
            )
        )
    widths = [max(len(row[column]) for row in rows) for column in range(len(rows[0]))]
    for row in rows:
        cells = (value.ljust(width) for value, width in zip(row, widths, strict=True))
        print("  ".join(cells).rstrip())
