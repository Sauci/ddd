"""Shared helpers for the DDD test suite."""

from __future__ import annotations

import io
import json
import os
import re
import threading
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final

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
from ddd.build_info import BUILD_INFO_FILENAME, BuildInfo, build_info_text
from ddd.diagnostics import DiagnosticBag, SeverityPolicy
from ddd.gui.session import Revision, Session, Snapshot
from ddd.ir import DataDictionary
from ddd.loading import load_workspace
from ddd.lsp.navigation import Index, index
from ddd.lsp.protocol import read_message, write_message
from ddd.models.common import OBJECT_ID_ALPHABET, OBJECT_ID_LENGTH

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


MODE_T: Final = {
    "kind": "enum",
    "name": "Mode_t",
    "enumerators": [{"name": "MODE_OFF", "value": 0}, {"name": "MODE_ON", "value": 1}],
}
"""An enumeration, which storage that is not an integer cannot hold exactly: a float32 that is
given it stops loading."""

TEXT: Final = {"kind": "string"}
"""Bytes read as text: stated on a byte datatype and one dimension, and with no unit and no limits -
anything else a declaration is given beside it stops loading."""


FLOAT_BESIDE_ENUM: Final = {
    "w.ddd.json": component("W", declare("output", "V", "float32")),
    "r.ddd.json": component("R", declare("input", "V", "uint8", conversion=MODE_T)),
}
"""A writer storing a float and a reader whose enumeration needs an integer to hold it: of the
fixes the two of them are offered, one writes the float under the enumeration, another the
enumeration into the float writer, and the rest leave both files loading."""

UNIT_BESIDE_TEXT: Final = {
    "w.ddd.json": component("W", declare("output", "V", "uint8", unit="rpm", dimensions=[8])),
    "r.ddd.json": component("R", declare("input", "V", "uint8", conversion=TEXT, dimensions=[8])),
}
"""A writer stating a unit and a reader that reads text, which has none to state: the unit written
into the reader, and the text into the writer, stop a file loading."""

DOUBLE_BESIDE_SCALED: Final = {
    "w.ddd.json": component("W", declare("output", "V", "float64")),
    "r.ddd.json": component(
        "R", declare("input", "V", "uint16", conversion={"kind": "linear", "factor": 2})
    ),
}
"""A writer storing a double and a reader that doubles a 16 bit integer: each loads, and the
double under the reader's factor - or the factor over the double - has limits past the largest
float there is. The models take either file; the analysis refuses it (``schema``, which no
severity turns down), and only a rule it applies to the definition alone tells the fix that
writes it from one that loads."""


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


TEXT_TYPE: Final = scalar_type("Text_t", "uint8", conversion=TEXT)
"""A type that says its bytes are text. What a declaration naming it has to state - exactly one
dimension, and no display format - is the analysis's to say, with the type beside the declaration:
no definition holds it."""

STRING_TYPE_BESIDE_SCALAR: Final = {
    "t.ddd.json": types(TEXT_TYPE),
    "w.ddd.json": component("W", declare("output", "V", "uint8")),
    "r.ddd.json": component("R", declare("input", "V", typename="Text_t", dimensions=[8])),
}
"""A writer storing one byte and a reader naming a string type, with the one dimension it states.
Each loads. Taking that dimension out of the reader, which the writer does not state, leaves a
string of none: the models take it, for the type is nobody's but the project's, and the analysis
files ``schema`` once the file is written."""

STRING_TYPE_BESIDE_GRID: Final = {
    "t.ddd.json": types(TEXT_TYPE),
    "w.ddd.json": component("W", declare("output", "V", "uint8", dimensions=[2, 4])),
    "r.ddd.json": component("R", declare("input", "V", typename="Text_t", dimensions=[8])),
}
"""The same reader beside a writer that states two dimensions: giving the reader the writer's
dimensions leaves a string of two, which an array of strings is not allowed to be."""


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


def without_ids(text: str) -> str:
    """A description with every id it states, twelve characters, spelled as one placeholder.

    What two writers made of one file differs in nothing but the ids they minted, when each put
    its id in the same place: the text of the one is the text of the other once those are
    taken out.
    """
    return re.sub(rf'"id": "[{OBJECT_ID_ALPHABET}]{{{OBJECT_ID_LENGTH}}}"', '"id": "<id>"', text)


def built_of(tmp_path: Path, **files: Any) -> tuple[Index, Path]:
    """The index of a project including every file given, and the root they were written under."""
    write_tree(tmp_path, {"p.ddd.json": project("P", *files), **files})
    workspace = load_workspace(tmp_path / "p.ddd.json", DiagnosticBag())
    assert workspace is not None
    return index(workspace), tmp_path


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


def looped(first: Path, second: Path) -> None:
    """Two links naming each other, so that nothing is ever found through either. Made with
    :func:`directory_link`, which is a junction on Windows - where no link can name itself, a
    junction's target having to exist when it is made, and its own name not to.

    A path through them is one python 3.12's ``Path.resolve`` raises ``RuntimeError`` on, on
    POSIX and on Windows alike, where 3.13's walks past it: the loop a local user can make
    anywhere they can write, and hand to ``ddd gui`` or ``ddd check`` as a path."""
    second.mkdir()
    directory_link(first, second)
    second.rmdir()
    directory_link(second, first)


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


def collected_project(
    root: Path,
    *descriptions: Path,
    image: str = "fw",
    name: str = "Fw",
    plugins: Sequence[Path] = (),
    build: str = "b",
    source: Path | None = None,
    cache: bool = True,
) -> Path:
    """The project description ``ddd_generate`` collects out of ``image``'s link closure when no
    ``PROJECT`` is given, and the build record beside it, both where a build tree configured in
    ``root / build`` leaves them: ``<build>/ddd/<image>/``, the default output directory, ``build``
    being ``.`` for an in-source build. Written as the module writes them - the description in the
    layout ``file(GENERATE)`` renders, naming each of ``descriptions`` by its absolute path as
    ``ddd_add_component`` registered it, and each of ``plugins`` as ``PLUGINS`` names one, and the
    record as ``ddd build-info`` writes it: both files byte for byte what CMake 4.4.3 and Ninja
    wrote, configuring two components registered on what ``fw`` links and
    ``ddd_generate(fw NAME Fw)``, which is ``b/ddd/fw/Fw.ddd.json``, the default here.

    Unless ``cache`` is false, the tree's ``CMakeCache.txt`` too, reduced to the two entries
    naming its trees, spelled as CMake spells them: ``CMAKE_CACHEFILE_DIR``, the build tree, and
    ``CMAKE_HOME_DIRECTORY``, the source tree it was configured from - ``source``, ``root`` by
    default. Returns the project description."""
    tree = root / build
    directory = tree / "ddd" / image
    directory.mkdir(parents=True, exist_ok=True)
    if cache:
        configured = root if source is None else source
        (tree / "CMakeCache.txt").write_text(
            "# This is the CMakeCache file.\n"
            f"CMAKE_CACHEFILE_DIR:INTERNAL={tree.as_posix()}\n"
            f"CMAKE_HOME_DIRECTORY:INTERNAL={configured.as_posix()}\n",
            encoding="utf-8",
            newline="",
        )
    described = directory / f"{name}.ddd.json"
    listed = ""
    if descriptions:
        joined = '",\n      "'.join(path.as_posix() for path in descriptions)
        listed = f'\n      "{joined}"\n    '
    named = ""
    if plugins:
        joined = '", "'.join(path.as_posix() for path in plugins)
        named = f'"{joined}"'
    described.write_text(
        "{\n"
        '  "project": {\n'
        f'    "name": "{name}",\n'
        f'    "description": "Collected from the link closure of {image} by ddd_generate()",\n'
        f'    "plugins": [{named}],\n'
        f'    "includes": [{listed}]\n'
        "  }\n"
        "}\n",
        encoding="utf-8",
        newline="",
    )
    record = BuildInfo(project=described.as_posix(), image=image)
    (directory / BUILD_INFO_FILENAME).write_text(
        build_info_text(record), encoding="utf-8", newline=""
    )
    return described


def membership(root: Path, tree: str = "b", build: str = "the build of fw") -> str:
    """What a change writing under the build tree of :func:`collected_project`'s project is
    refused with, ``tree`` being where nothing is written, relative to ``root``: which files
    belong to the project is the build's, and decided by ``ddd_add_component``."""
    under = (root / tree).resolve().as_posix()
    return (
        f"Fw.ddd.json is generated by {build} at every configure, so which files belong to it is "
        f"ddd_add_component's to say, and nothing under {under} is written from here"
    )


def lying_under(root: Path, name: str, tree: str = "b") -> str:
    """The refusal of a change of the file ``name`` alone, lying under the build tree of
    :func:`collected_project`'s project: the file named, and the tree."""
    under = (root / tree).resolve().as_posix()
    return (
        f"{name} lies under {under}, where Fw.ddd.json is generated by the build of fw at every "
        "configure: which files belong to it is ddd_add_component's to say, and nothing there is "
        "written from here"
    )


def offered_beside(root: Path, name: str, beside: str, tree: str = "b") -> str:
    """The refusal of a new file ``name`` in :func:`collected_project`'s project, offering it
    beside ``beside`` - the posix path of a description the build collects from the source tree -
    with the line registering it there, its placeholder for the reader to fill."""
    return (
        f"{membership(root, tree)}; create {name} beside {beside} instead, and add "
        f"ddd_add_component(<target> JSON {name}) to the CMakeLists.txt there, replacing <target> "
        "with your component's target"
    )


# The session of `ddd gui`, for the suites that open a project in one: the api's, the server's
# and the session's own, and the plans' that apply an edit through it.


def first_revision(root: Path, project_file: Path) -> Revision:
    """The newest revision once opening ``project_file`` is done, in a session on ``root`` that
    nobody started: such a session makes every analysis opening asks for before
    :meth:`~ddd.gui.session.Session.open` returns, which answers nothing of its own. One for a flat
    project, so revision 1; two where the first read a file opening does not stamp - a
    sub-project's, as on examples/demo, or a plugin - and its revision asked for the second, so
    revision 2."""
    session = Session(root)
    session.open(project_file)
    revision = session.revision
    assert revision is not None
    return revision


class Gated(Session):
    """A session whose analyses are counted, announce that they have begun, and wait at a gate
    the test opens: what lets a test land an edit while an analysis runs without sleeping."""

    def __init__(self, root: Path, build_directories: Sequence[Path] = ()) -> None:
        # Polling an hour apart: the poller start() starts never polls while a test runs.
        super().__init__(root, build_directories, poll_interval=3600)
        self.begun = threading.Semaphore(0)
        self.gate = threading.Event()
        self.analyses = 0

    def _analysed(self, project: Path) -> Revision:
        self.analyses += 1
        self.begun.release()
        assert self.gate.wait(timeout=10), "the test never opened the gate"
        return super()._analysed(project)


def begun(session: Gated) -> None:
    """Wait until one more analysis has begun."""
    assert session.begun.acquire(timeout=10), "no analysis began"


def landed(session: Session) -> Snapshot:
    """What the session says once no analysis is asked for or running, failing the test where ten
    seconds pass first: :meth:`~ddd.gui.session.Session.settled` answers the newest revision on a
    timeout too, so a revision being there says nothing of whether the analysis landed."""
    session.settled(timeout=10)
    snapshot = session.snapshot()
    assert not snapshot.analysing, "the analysis never landed"
    return snapshot


def stopped(session: Session) -> None:
    """Stop the session, failing the test rather than hanging the suite where its threads do not
    end: :meth:`~ddd.gui.session.Session.stop` joins them without a timeout."""
    stopping = threading.Thread(target=session.stop, name="stopping", daemon=True)
    stopping.start()
    stopping.join(timeout=10)
    assert not stopping.is_alive(), "the session did not stop"
