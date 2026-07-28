"""Command line interface of DDD."""

from __future__ import annotations

import argparse
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
    load_address_map,
    render,
    write,
)
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
from ddd.models import ComponentFile, NamingFile, ProjectFile, format_shape
from ddd.naming import Inspection, complete, inspect

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 2

GENERATOR = f"ddd {__version__}"


def cmake_module_directory() -> Path | None:
    """Directory holding ``Ddd.cmake``, inside the installed package or in a source checkout."""
    candidates = (Path(__file__).parent / "cmake", Path(__file__).resolve().parents[2] / "cmake")
    return next((path for path in candidates if (path / "Ddd.cmake").is_file()), None)


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point of the ``ddd`` command; returns the process exit code."""
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


# -- argument parsing -------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ddd",
        description=(
            "Data dictionary for the global variables of a component based "
            "embedded software project."
        ),
    )
    parser.add_argument("--version", action="version", version=f"ddd {__version__}")
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
        "--prefix",
        default="ddd",
        help="base name of the shared files, default: %(default)s",
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

    schema = subparsers.add_parser("schema", help="print the json schema of a file format")
    schema.add_argument("kind", choices=sorted(_SCHEMA_MODELS))
    schema.add_argument("-o", "--output", type=Path, help="write to this file instead of stdout")
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

    checks = subparsers.add_parser("checks", help="list the available consistency checks")
    checks.add_argument("--format", choices=["text", "json"], default="text", help="output format")
    checks.set_defaults(handler=_command_checks)

    cmake = subparsers.add_parser(
        "cmake-dir", help="print the directory containing the cmake integration module"
    )
    cmake.set_defaults(handler=_command_cmake_dir)

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


# -- commands ---------------------------------------------------------------


def _command_check(args: argparse.Namespace) -> int:
    dictionary, bag = _analyze(args)
    # With a baseline, one command answers both questions and returns one exit code, which
    # is what a ci job wants: is the project consistent, and is it still a replacement?
    if dictionary is not None and args.baseline is not None:
        baseline = _read_dictionary(args.baseline, bag)
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
    baseline = _read_dictionary(args.baseline, bag)
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
        CBackend(COptions(prefix=args.prefix, const_inputs=args.const_inputs), GENERATOR)
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
    results = write(files, dry_run=args.dry_run)

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
    """Emit the data dictionary itself, so that another tool can generate from it."""
    dictionary, bag = _analyze(args)
    if dictionary is None:
        _report(bag, "text")
        return EXIT_FINDINGS
    print(dictionary.model_dump_json(indent=2))
    if args.format != "json":
        _report(bag, "text")
    return EXIT_FINDINGS if bag.has_errors else EXIT_OK


_SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "project": ProjectFile,
    "component": ComponentFile,
    "naming": NamingFile,
    "dictionary": DataDictionary,
}


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
        suggestion = f" - did you mean {' or '.join(part.suggestions)}?" if part.suggestions else ""
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


def _command_schema(args: argparse.Namespace) -> int:
    model = _SCHEMA_MODELS[args.kind]
    text = json.dumps(model.model_json_schema(), indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {args.output.as_posix()}", file=sys.stderr)
    else:
        print(text)
    return EXIT_OK


def _command_cmake_dir(args: argparse.Namespace) -> int:
    """Print the directory to add to CMAKE_MODULE_PATH before ``include(Ddd)``."""
    directory = cmake_module_directory()
    if directory is None:
        print("ddd: the cmake integration module is not part of this installation", file=sys.stderr)
        return EXIT_USAGE
    print(directory.as_posix())
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


# -- shared helpers ---------------------------------------------------------


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


def _report(bag: DiagnosticBag, output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(_diagnostics_payload(bag), indent=2))
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
