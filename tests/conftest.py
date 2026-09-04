"""Shared helpers for the DDD test suite."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import pytest

from ddd.analysis import analyze
from ddd.backends import (
    A2lBackend,
    A2lOptions,
    Backend,
    ByteOrder,
    CBackend,
    COptions,
    GeneratedFile,
    render,
)
from ddd.diagnostics import DiagnosticBag, SeverityPolicy
from ddd.ir import DataDictionary
from ddd.loading import load_workspace

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
DEMO = EXAMPLES / "demo" / "demo.ddd.json"
INCONSISTENT = EXAMPLES / "inconsistent" / "project.ddd.json"


def project(name: str = "TestProject", *includes: str, **extra: Any) -> dict[str, Any]:
    return {"project": {"name": name, "includes": list(includes), **extra}}


def component(name: str, *declarations: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return {"component": {"name": name, "interface": list(declarations), **extra}}


def declare(
    scope: str, name: str, datatype: str = "uint8", condition: str | None = None, **definition: Any
) -> dict[str, Any]:
    # kind and volatile are required on a definition; a test that does not care is declaring a
    # non-volatile measurement, so both are filled in here and overridden by whatever the
    # caller passes in **definition. A test *about* a missing key writes its json by hand.
    storage: dict[str, Any] = (
        {}
        if "typename" in definition
        else {"datatype": datatype, "conversion": {"kind": "identity"}}
    )
    entry: dict[str, Any] = {
        "scope": scope,
        "definition": {
            "name": name,
            **storage,
            "kind": "measurement",
            "volatile": False,
            **definition,
        },
    }
    if condition is not None:
        entry["condition"] = condition
    return entry


def write_tree(base: Path, files: Mapping[str, Any]) -> Path:
    """Write a mapping of relative path -> json document (or raw string).

    ``newline=""`` so a fixture ends its lines the way this file spells them, rather than the
    way the platform would. Without it ``write_text`` translates every ``
`` to ``os.linesep``,
    so on Windows every fixture arrives as crlf - which silently weakens a test that means to
    write an lf file and check something preserves it, because the file was never lf to begin
    with.
    """
    for relative, content in files.items():
        path = base / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        written = content if isinstance(content, str) else json.dumps(content, indent=2)
        path.write_text(written, encoding="utf-8", newline="")
    return base


def run_analysis(
    base: Path,
    files: Mapping[str, Any],
    root: str = "project.ddd.json",
    severities: Iterable[str] = (),
    *,
    strict: bool = False,
) -> tuple[DataDictionary | None, DiagnosticBag]:
    write_tree(base, files)
    # `missing-id` is an adoption nudge: it fires on every producing declaration with no `id`,
    # and no fixture in this suite has adopted one, so left at its default it would fire on
    # nearly every test in the suite and couple all of them to this one feature. Silenced here
    # instead; a test exercising the check itself passes its own `missing-id=...` override,
    # which sits after this default in the tuple and so wins - `from_strings` keeps the last
    # entry it sees for a repeated check.
    bag = DiagnosticBag(
        SeverityPolicy.from_strings(("missing-id=ignore", *severities), strict=strict)
    )
    workspace = load_workspace(base / root, bag)
    if workspace is None or bag.has_errors:
        return None, bag
    return analyze(workspace, bag), bag


def checks(bag: DiagnosticBag) -> list[str]:
    return [diagnostic.check for diagnostic in bag]


def messages(bag: DiagnosticBag) -> str:
    return "\n".join(diagnostic.render() for diagnostic in bag)


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    return tmp_path


TEMPLATES = EXAMPLES / "templates"
"""The example c templates, which the tests render with unless one says otherwise.

The tool ships no default templates - a project provides its own - so the suite has to name
a directory the same way a project does. Using the shipped examples means the tests also
keep those examples working.
"""


def build_backends(**options: Any) -> list[Backend]:
    """The backend list a `ddd generate` run with these options would use."""
    template_dir = options.pop("template_dir", TEMPLATES)
    const_inputs = options.pop("const_inputs", False)
    emit_a2l = options.pop("emit_a2l", True)
    byte_order = options.pop("byte_order", ByteOrder.LITTLE)
    addresses = options.pop("addresses", None)
    if options:
        msg = f"unknown backend option(s): {sorted(options)}"
        raise TypeError(msg)
    backends: list[Backend] = [CBackend(template_dir, COptions(const_inputs=const_inputs))]
    if emit_a2l:
        backends.append(A2lBackend(A2lOptions(byte_order=byte_order, addresses=addresses or {})))
    return backends


def render_files(
    dictionary: DataDictionary, output_dir: Path, **options: Any
) -> list[GeneratedFile]:
    return render(dictionary, build_backends(**options), output_dir)
