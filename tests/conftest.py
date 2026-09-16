"""Shared helpers for the DDD test suite."""

from __future__ import annotations

import io
import json
import os
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
from ddd.build_info import BUILD_INFO_FILENAME
from ddd.diagnostics import DiagnosticBag, SeverityPolicy
from ddd.ir import DataDictionary
from ddd.loading import load_workspace
from ddd.lsp.protocol import read_message, write_message

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


# One family for the other half of a description - the types a declaration names. Five test
# modules each had their own spelling of these four builders (`val`/`value`/`value_member`,
# `struct`/`structure`/`struct_type`, ...), differing only in the names they defaulted to, so
# a change to what a member or a type entry needs had to be made five times and a reader
# moving between two files had to learn both. Every name defaults, so a test that does not
# care about it says nothing; a test that asserts on a name passes it.


def value_member(name: str = "value", datatype: str = "uint16", **extra: Any) -> dict[str, Any]:
    """A member holding one value, with the storage keys a ``typename`` would supply itself."""
    storage: dict[str, Any] = (
        {} if "typename" in extra else {"datatype": datatype, "conversion": {"kind": "identity"}}
    )
    return {"name": name, "member": "value", **storage, **extra}


def bits_member(
    name: str = "flag", datatype: str = "uint16", bits: int = 1, **extra: Any
) -> dict[str, Any]:
    """A bitfield member: the same, plus the width in bits."""
    storage: dict[str, Any] = (
        {} if "typename" in extra else {"datatype": datatype, "conversion": {"kind": "identity"}}
    )
    return {"name": name, "member": "bits", **storage, "bits": bits, **extra}


def struct_type(name: str = "Sample_t", *members: dict[str, Any], **extra: Any) -> dict[str, Any]:
    """One ``struct`` entry of a types file; with no members it holds a single value."""
    return {
        "type": "struct",
        "name": name,
        "members": list(members) or [value_member()],
        **extra,
    }


def scalar_type(name: str = "Sample_t", datatype: str = "uint16", **extra: Any) -> dict[str, Any]:
    """One ``scalar`` entry: a name for what a number means."""
    meaning: dict[str, Any] = {} if "conversion" in extra else {"conversion": {"kind": "identity"}}
    return {"type": "scalar", "name": name, "datatype": datatype, **meaning, **extra}


def types(*entries: dict[str, Any]) -> dict[str, Any]:
    """A types file holding these entries."""
    return {"types": list(entries)}


def write_tree(base: Path, files: Mapping[str, Any]) -> Path:
    """Write a mapping of relative path -> json document (or raw string).

    ``newline=""`` so a fixture ends its lines the way this file spells them, rather than the
    way the platform would. Without it ``write_text`` translates every line ending to
    ``os.linesep``, so on Windows every fixture arrives as crlf - which silently weakens a
    test that means to write an lf file and check something preserves it, because the file was
    never lf to begin with.
    """
    for relative, content in files.items():
        path = base / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        written = content if isinstance(content, str) else json.dumps(content, indent=2)
        path.write_text(written, encoding="utf-8", newline="")
    return base


def directory_link(link: Path, target: Path) -> None:
    """A second spelling of a directory, made the way the platform allows unprivileged.

    What a test about two spellings of one path needs is a path whose ``resolve()`` is a
    different path, and every platform has one; only the word for it differs. ``symlink_to``
    needs ``SeCreateSymbolicLinkPrivilege`` on Windows, which an ordinary account does not
    hold, so a junction is made there - any account may make one, and ``mklink /J`` is a
    ``cmd`` builtin nothing else needs.

    Here rather than in one suite because the alternative is a test that skips: the case a
    junction was written for was exercised on the windows cells of the matrix and reported
    skipped on the ubuntu ones, which is success without having run.
    """
    if os.name == "nt":
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
    else:
        link.symlink_to(target, target_is_directory=True)


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


# The language-server side of a fixture. Three test modules besides tests/test_lsp.py ask a
# server a question - a constant's hover, an external type's, a project's findings - and each
# imported these from that module, which meant importing its 5 000 lines and its fixtures to
# frame one message. They describe the wire and the build record, neither of which belongs to
# the server tests in particular.


def framed(*messages: dict[str, Any]) -> io.BytesIO:
    """The messages as a client would put them on the wire."""
    stream = io.BytesIO()
    for message in messages:
        write_message(stream, message)
    stream.seek(0)
    return stream


def session(*messages: dict[str, Any]) -> io.BytesIO:
    """A whole conversation: the handshake a client opens with, then these messages.

    The server refuses anything that arrives before ``initialize`` - the protocol reserves a
    code for exactly that - so a test that means to exercise a request says hello first, as
    every client does. Empty ``params`` leaves the workspace folder the server was constructed
    with in place, which is the one these tests set up.
    """
    return framed({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {}}, *messages)


def sent(stream: io.BytesIO) -> list[dict[str, Any]]:
    """Everything the server wrote, read back off the wire."""
    stream.seek(0)
    received = []
    while (message := read_message(stream)) is not None:
        received.append(message)
    return received


def answered(stream: io.BytesIO) -> list[dict[str, Any]]:
    """What the server said in answer to everything after the handshake."""
    return sent(stream)[1:]


def build_record(base: Path, project_file: Path, image: str = "firmware.elf", **extra: Any) -> Path:
    """A ``ddd-build.json`` where a build would have left one, one directory per image."""
    path = base / "build" / "ddd" / image / BUILD_INFO_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"format": 1, "project": project_file.as_posix(), "image": image, **extra}
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path
