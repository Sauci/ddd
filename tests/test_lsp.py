"""The language server: what an editor is told, and how it is framed on the way.

The checks themselves are tested everywhere else in this suite. What is tested here is the
translation - a pointer becoming a range, a build record becoming a project, a finding
becoming something an editor can draw and click - and the protocol the translation travels on.
"""

from __future__ import annotations

import io
import json
import os
import queue
import re
import shutil
import sys
from collections import Counter
from collections.abc import Callable, Sequence
from functools import partial
from pathlib import Path
from typing import Any, ClassVar, Final

import pytest
from generate_project import generate

from conftest import (
    DEMO,
    DOUBLE_BESIDE_SCALED,
    EXAMPLES,
    FLOAT_BESIDE_ENUM,
    INCONSISTENT,
    STRING_TYPE_BESIDE_GRID,
    STRING_TYPE_BESIDE_SCALAR,
    TEXT,
    UNIT_BESIDE_TEXT,
    answered,
    build_record,
    built_of,
    checks,
    component,
    declare,
    directory_link,
    framed,
    project,
    scalar_type,
    sent,
    session,
    struct_type,
    types,
    value_member,
    without_ids,
    write_tree,
)
from ddd.build_info import BUILD_INFO_FILENAME, BUILD_INFO_FORMAT, BuildInfo
from ddd.cli import EXIT_OK, main
from ddd.diagnostics import Diagnostic, DiagnosticBag, Location, Severity
from ddd.editing import INVALID, EditError, Operation, edit_text
from ddd.finding_fixes import CODE_NOT_TOUCHED
from ddd.loading import load_workspace
from ddd.lsp import diagnostics as service
from ddd.lsp import navigation
from ddd.lsp import server as server_module
from ddd.lsp.discovery import build_files, discover, load_builds
from ddd.lsp.protocol import (
    INVALID_PARAMS,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    REQUEST_FAILED,
    SERVER_NOT_INITIALIZED,
    MessageError,
    ProtocolError,
    error,
    notification,
    read_message,
    response,
)
from ddd.lsp.ranges import Document, differs_from_disk, read
from ddd.lsp.server import Server, uri_to_path
from ddd.lsp.units import (
    PlannedEdit,
    UnitPlan,
    UnitRefusalError,
    rename_unit,
    text_edits,
    unit_drift,
    unit_project,
)
from test_variable_keys import edited


def raw_frame(body: bytes) -> bytes:
    """One correctly framed message with exactly this body, however broken the body is."""
    return b"Content-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body


def published(stream: io.BytesIO) -> dict[str, list[dict[str, Any]]]:
    """The diagnostics the server published, keyed by the uri they went out under.

    The uri string and not the file it names: a client matches a publication to an open
    editor by comparing that string, so two spellings of one file are two resources to it and
    a test that compares the files behind them cannot see a publication going to the wrong
    one. Keying by ``.name`` hid exactly that for every test in this file.

    Filtered rather than taken wholesale: the server also logs, and a log line has no uri.
    """
    return {
        message["params"]["uri"]: message["params"]["diagnostics"]
        for message in sent(stream)
        if message.get("method") == "textDocument/publishDiagnostics"
    }


END: Final = (
    {"jsonrpc": "2.0", "id": 99, "method": "shutdown"},
    {"jsonrpc": "2.0", "method": "exit"},
)
"""How a client ends a session it means to end, which ``run`` answers with 0."""

UNSEEN_RENAME: Final = (
    "reader_two.ddd.json has unsaved changes this rename would not see; save it and rename again"
)
"""What a rename is refused with while one document of the reach differs from its file."""

EMPTY_RENAME: Final = "nothing on disk spells that name, so this rename would change nothing"
"""What a rename that rewrites nothing is refused with."""

WITHHELD: Final = (
    "no quick fix is offered: a.ddd.json did not load, so the rest of the project cannot be "
    "edited around it; fix it and try again"
)
"""What the log says, once, while ``a.ddd.json`` did not load and the quick fixes are withheld."""

DROPPED: Final = component("D", declare("output", "Speed", "uint99"))
"""A component a ``schema`` error drops as it is read: ``uint99`` is no datatype."""

ERRING: Final = component("E", declare("local", "Kept", extensions={"layout": {"key": 1}}))
"""A component that loads with an error, ``unknown-extension``: its block is for a plugin the
project does not load, as a project's is while that plugin does not import."""


class TestFraming:
    """Bytes on a pipe, which is the one place a mistake corrupts everything after it."""

    def test_a_message_survives_the_round_trip(self) -> None:
        assert sent(framed({"jsonrpc": "2.0", "method": "exit"})) == [
            {"jsonrpc": "2.0", "method": "exit"}
        ]

    def test_the_length_is_counted_in_bytes_not_characters(self) -> None:
        """A unit is free text, and one degree sign would put every later message out of step."""
        stream = framed({"method": "x", "params": {"unit": "°C"}}, {"method": "second"})
        assert [message["method"] for message in sent(stream)] == ["x", "second"]

    def test_headers_the_server_does_not_care_about_are_skipped(self) -> None:
        body = b'{"method":"ping"}'
        stream = io.BytesIO(
            b"Content-Type: application/vscode-jsonrpc; charset=utf-8\r\n"
            b"Content-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body
        )
        assert read_message(stream) == {"method": "ping"}

    def test_a_closed_stream_is_the_end_of_the_conversation(self) -> None:
        assert read_message(io.BytesIO(b"")) is None

    def test_a_header_block_with_no_length_cannot_be_followed(self) -> None:
        """Nothing says where the body ends, and guessing would desynchronise the stream."""
        assert read_message(io.BytesIO(b"Content-Type: text/plain\r\n\r\n{}")) is None

    def test_a_body_that_is_not_json_keeps_the_frame_boundary(self) -> None:
        """The length was honoured, so the next frame is still readable; the fault carries
        the json-rpc code the answer has to use."""
        stream = io.BytesIO(raw_frame(b"{ not json") + raw_frame(b'{"method":"after"}'))
        with pytest.raises(MessageError) as caught:
            read_message(stream)
        assert caught.value.code == PARSE_ERROR
        assert read_message(stream) == {"method": "after"}

    def test_a_body_that_is_not_utf8_is_the_same_fault(self) -> None:
        with pytest.raises(MessageError) as caught:
            read_message(io.BytesIO(raw_frame(b"\xff\xfe{}")))
        assert caught.value.code == PARSE_ERROR

    def test_a_batch_body_is_refused_with_the_code_it_defines(self) -> None:
        with pytest.raises(MessageError) as caught:
            read_message(io.BytesIO(raw_frame(b"[]")))
        assert caught.value.code == INVALID_REQUEST

    def test_a_length_that_is_not_a_number_cannot_be_followed(self) -> None:
        """No believable length means no body boundary, and everything after it would be
        read out of step; this one is fatal where the body faults above are not."""
        stream = io.BytesIO(b"Content-Length: banana\r\n\r\n{}")
        with pytest.raises(ProtocolError, match="banana"):
            read_message(stream)

    def test_the_three_message_shapes(self) -> None:
        assert response(1, None) == {"jsonrpc": "2.0", "id": 1, "result": None}
        assert error(2, METHOD_NOT_FOUND, "no") == {
            "jsonrpc": "2.0",
            "id": 2,
            "error": {"code": METHOD_NOT_FOUND, "message": "no"},
        }
        assert notification("m", {"a": 1}) == {"jsonrpc": "2.0", "method": "m", "params": {"a": 1}}


class TestADocumentThatDiffersFromItsFile:
    """What a buffer parses to against what its file parses to, never the text of either."""

    @staticmethod
    def on_disk(tmp_path: Path, content: bytes) -> Path:
        path = tmp_path / "a.ddd.json"
        path.write_bytes(content)
        return path

    @pytest.mark.parametrize(
        ("disk", "buffer"),
        [
            (b'{"a": [1, 2]}', '{"a": [1, 2]}'),
            (b'{\r\n  "a": [1, 2]\r\n}', '{\n  "a": [1, 2]\n}'),
            (b'{"a": [1, 2]}', '{\n    "a": [ 1,\n 2 ]\n}'),
            (b'\xef\xbb\xbf{"a": 1}', '{"a": 1}'),
        ],
        ids=["same", "crlf-against-lf", "reformatted", "byte-order-mark"],
    )
    def test_the_same_document_does_not_differ(
        self, tmp_path: Path, disk: bytes, buffer: str
    ) -> None:
        assert not differs_from_disk(self.on_disk(tmp_path, disk), buffer)

    @pytest.mark.parametrize(
        ("disk", "buffer"),
        [
            (b'{"a": 1}', '{"a": 2}'),
            (b'{"a": 1}', '{"a": 1, "b": 1}'),
            (b'{"a": 1, "b": 2}', '{"b": 2, "a": 1}'),
            (b'{"a": 1}', '{"a": true}'),
            (b'{"a": 1}', '{"a": 1.0}'),
            (b'{"a": 1}', '{"a": 1'),
            (b'{"a": 1', '{"a": 1'),
            (b'{"a": 1}', ""),
        ],
        ids=[
            "value",
            "member",
            "order",
            "true-for-one",
            "float-for-int",
            "buffer-unparsed",
            "both-unparsed",
            "empty-buffer",
        ],
    )
    def test_a_document_that_says_something_else_differs(
        self, tmp_path: Path, disk: bytes, buffer: str
    ) -> None:
        assert differs_from_disk(self.on_disk(tmp_path, disk), buffer)

    def test_a_buffer_nested_too_deeply_to_parse_differs(self, tmp_path: Path) -> None:
        path = self.on_disk(tmp_path, b"[]")
        assert differs_from_disk(path, "[" * 100_000 + "]" * 100_000)

    def test_a_file_that_is_not_there_or_not_text_differs(self, tmp_path: Path) -> None:
        assert differs_from_disk(tmp_path / "gone.ddd.json", "{}")
        assert differs_from_disk(self.on_disk(tmp_path, b"\xff\xfe{}"), "{}")


class TestRanges:
    def test_a_uri_round_trips_a_path_that_needed_escaping(self, tmp_path: Path) -> None:
        """The server publishes under ``Path.as_uri()`` and reads what a client sends back.

        Those two have to be inverses or the editor cannot match a finding to the document it
        is looking at. ``url2pathname`` already unescapes, so unescaping before calling it
        decoded a percent sequence twice and named a different file: ``a%20b.ddd.json`` came
        back as ``a b.ddd.json``.
        """
        path = tmp_path / "a%20b.ddd.json"
        path.write_text("{}", encoding="utf-8")
        assert uri_to_path(path.as_uri()) == path

    def test_a_uri_still_decodes_the_escaping_a_client_applies(self, tmp_path: Path) -> None:
        """The other direction of the same rule: a space really is sent as ``%20``."""
        path = tmp_path / "a b.ddd.json"
        path.write_text("{}", encoding="utf-8")
        assert uri_to_path(path.as_uri()) == path

    @pytest.mark.parametrize("escaped", ["c%3A", "C%3A"])
    def test_the_escaped_drive_colon_a_windows_client_sends_is_read_as_a_drive(
        self, escaped: str
    ) -> None:
        """VS Code sends ``file:///c%3A/...``: a lower-case drive with the colon escaped.

        ``url2pathname`` looks for a literal colon before it unquotes, so the escaped one was
        read as no drive at all, and the path came back relative - ``/c:/git/x`` - which names
        no file and cannot be turned back into a uri. The server died on the first didOpen.
        """
        literal = escaped.replace("%3A", ":")
        decoded = uri_to_path(f"file:///{escaped}/git/x/a.ddd.json")
        assert decoded == uri_to_path(f"file:///{literal}/git/x/a.ddd.json")
        # Spelled through ``as_posix`` so that the decoding is pinned on both platforms: on
        # posix the two spellings unquote alike whatever the function does with a drive, so
        # the equality above holds there even when nothing has been decoded as a drive at
        # all. ``C:/git/x/...`` on windows, ``/c:/git/x/...`` on posix, and a drive letter
        # keeps whatever case it arrived in.
        assert decoded.as_posix().lower().endswith("c:/git/x/a.ddd.json")
        if os.name == "nt":
            assert decoded.is_absolute()
            # ``as_uri`` keeps the drive letter's case, so compare case-blind.
            assert decoded.as_uri().lower() == "file:///c:/git/x/a.ddd.json"

    def test_a_drive_looking_segment_after_a_host_is_not_mistaken_for_a_drive(self) -> None:
        """``file://server/share/...`` is a network share, whose first path segment is a
        share name, not a drive letter - a share may be called ``c%3A`` just as readily as
        anything else. Substituting there asked ``url2pathname`` to parse a share name as a
        Windows drive, which is not what it is."""
        found = uri_to_path("file://server/c%3A/a.ddd.json")
        # Written out rather than computed from ``url2pathname``, which is the fallback this
        # function takes here: an expectation built from it says only that the code ran the
        # line it ran, and would follow the function anywhere.
        assert found.as_posix() == "//server/c:/a.ddd.json"

    def test_a_drive_colon_with_nothing_after_it_is_left_to_url2pathname(self) -> None:
        """VS Code always sends more path after the drive - ``file:///c%3A/...`` - so a
        colon with nothing following it at all is not a shape any client is known to send,
        and guessing it is a bare drive root is a guess this function is not in a position
        to make."""
        assert uri_to_path("file:///c%3A").as_posix() == "/c:"

    def test_a_byte_order_mark_is_read_the_way_the_loader_reads_one(self, tmp_path: Path) -> None:
        """``ddd check`` accepts a BOM on purpose; the editor has to agree with it.

        Several Windows editors and PowerShell redirection put one in front of a file, which
        is why the loader reads ``utf-8-sig``. Read as plain utf-8 the document does not parse
        at all, and every span table comes out empty: findings collapse onto the first
        character and hover, go to definition, rename and the code actions all answer nothing -
        on a file the command line calls perfectly good.
        """
        path = tmp_path / "a.ddd.json"
        write_tree(tmp_path, {"a.ddd.json": component("A", declare("local", "X"))})
        path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8-sig")
        document = read(path, {})
        assert document.value_at("component.name") == "A"
        assert document.range_of("component.name") != {
            "start": {"line": 0, "character": 0},
            "end": {"line": 0, "character": 0},
        }

    """A pointer is what DDD reports; a range is what an editor can draw."""

    DOCUMENT = (
        '{\n  "component": {\n    "name": "A",\n'
        '    "interface": [\n      {"scope": "output"},\n'
        '      {"scope": "input", "condition": null}\n    ],\n'
        '    "empty": {},\n    "none": [],\n    "flag": true\n  }\n}\n'
    )

    def test_a_member_is_underlined_from_its_key(self) -> None:
        """Underlining the value alone leaves the reader to look left for the key."""
        found = Document(self.DOCUMENT).range_of("component.interface[1].condition")
        line = self.DOCUMENT.splitlines()[5]
        assert found["start"]["line"] == found["end"]["line"] == 5
        assert line[found["start"]["character"] : found["end"]["character"]] == '"condition": null'

    @pytest.mark.parametrize(
        "pointer",
        ["component", "component.name", "component.interface", "component.empty",
         "component.none", "component.flag", ""],
    )  # fmt: skip
    def test_every_shape_of_value_is_located(self, pointer: str) -> None:
        assert Document(self.DOCUMENT).range_of(pointer)["end"] != {"line": 0, "character": 0}

    def test_an_unknown_pointer_falls_back_to_its_parent(self) -> None:
        """A finding shown one level up beats a finding nobody sees."""
        document = Document(self.DOCUMENT)
        assert document.range_of("component.interface[0].absent") == document.range_of(
            "component.interface[0]"
        )

    def test_an_index_is_stripped_as_readily_as_a_key(self) -> None:
        document = Document(self.DOCUMENT)
        assert document.range_of("component.interface[7]") == document.range_of(
            "component.interface"
        )

    def test_a_file_that_is_not_json_puts_everything_at_the_top(self) -> None:
        """Caught mid edit: the json-syntax finding carries its own line and column."""
        assert Document("{not json").range_of("component") == {
            "start": {"line": 0, "character": 0},
            "end": {"line": 0, "character": 0},
        }

    def test_a_document_nested_beyond_what_python_can_read_answers_nothing(self) -> None:
        """``RecursionError`` is caught the same way a plain ``ValueError`` is: there is no
        data to read and no spans to offer, exactly as for a file caught mid edit."""
        document = Document("[" * 100_000 + "]" * 100_000)
        assert document.data is None
        assert document.value_at("component") is None
        assert document.range_of("component") == {
            "start": {"line": 0, "character": 0},
            "end": {"line": 0, "character": 0},
        }

    def test_a_pointer_naming_nothing_has_no_value_to_point_at(self) -> None:
        """The three views of a value all answer nothing for a pointer that is not there."""
        document = Document(self.DOCUMENT)
        assert document.value_range_of("component.absent") is None
        assert document.text_range_of("component.absent") is None
        assert document.raw_at("component.absent") is None

    def test_an_escaped_quote_does_not_end_a_string(self) -> None:
        document = Document('{\n  "a": "say \\" here",\n  "b": 1\n}')
        assert document.range_of("b")["start"]["line"] == 2

    def test_columns_are_counted_the_way_the_protocol_counts_them(self) -> None:
        """utf-16 code units, not python characters.

        The two differ from the first character outside the basic plane, and the difference is
        the whole underline: counted as python characters, every column after an emoji in a
        description is one too far left.
        """
        text = '{"\U0001f600": 1, "after": 2}'
        assert text.index('"after"') == 9  # what a python index would have said
        assert Document(text).range_of("after")["start"]["character"] == 10


class TestDiscovery:
    """Which projects exist is a question only the build tree can answer."""

    def test_the_usual_build_directory_names_are_searched(self, tmp_path: Path) -> None:
        record = build_record(tmp_path, tmp_path / "p.ddd.json")
        assert build_files(tmp_path) == [record]

    def test_a_configured_directory_wins_over_the_usual_names(self, tmp_path: Path) -> None:
        build_record(tmp_path, tmp_path / "p.ddd.json")
        elsewhere = tmp_path / "out-of-tree"
        elsewhere.mkdir()
        assert build_files(tmp_path, [elsewhere]) == []

    def test_a_workspace_with_no_build_yields_nothing(self, tmp_path: Path) -> None:
        assert build_files(tmp_path) == []
        assert discover(tmp_path) == []

    def test_a_record_is_read_back(self, tmp_path: Path) -> None:
        build_record(tmp_path, tmp_path / "p.ddd.json")
        (found,) = discover(tmp_path)
        assert found.image == "firmware.elf"
        assert found.project == (tmp_path / "p.ddd.json").as_posix()

    @pytest.mark.parametrize(
        "content", ["not json at all", '{"project": 7}', "{}", '{"format": "newer"}', "[2]"]
    )
    def test_a_record_that_makes_no_sense_is_skipped_in_silence(
        self, tmp_path: Path, content: str
    ) -> None:
        """Written by a build rather than by a person, so there is nobody to report it to."""
        path = tmp_path / BUILD_INFO_FILENAME
        path.write_text(content, encoding="utf-8")
        refused: dict[Path, str] = {}
        assert load_builds([path], refused) == []
        assert refused == {}

    @pytest.mark.parametrize("extra", [{}, {"colour": "blue"}])
    def test_a_record_from_a_newer_ddd_is_skipped_with_both_formats_named(
        self, tmp_path: Path, extra: dict[str, str]
    ) -> None:
        """Whether or not its keys are ones this version knows, since a newer record is exactly
        one that may carry keys it does not. Skipped in silence, its project was analysed under
        the default severities with nothing to say why - which is most likely to happen while a
        team is upgrading DDD."""
        newer = BUILD_INFO_FORMAT + 1
        path = build_record(tmp_path, tmp_path / "p.ddd.json", format=newer, **extra)
        refused: dict[Path, str] = {}
        assert load_builds([path], refused) == []
        assert refused == {path: NEWER_RECORD}

    def test_a_record_that_cannot_be_read_is_skipped(self, tmp_path: Path) -> None:
        assert load_builds([tmp_path / "absent.json"]) == []

    @pytest.mark.parametrize(
        ("override", "reason"),
        [
            (["no-such-check=ignore"], "unknown check 'no-such-check'"),
            (["unused-output"], "expected 'check=severity', got 'unused-output'"),
        ],
    )
    def test_a_record_naming_a_check_this_version_has_not_got_is_skipped(
        self, tmp_path: Path, override: list[str], reason: str
    ) -> None:
        """The severity side of "written by a newer DDD".

        The keys are all known, so the record validates; one of their values names a check
        this version has not got. Building the policy from it raised out of the first refresh
        that reached it and took the server with it - a record written by a newer ``ddd`` in
        the build tree while the editor runs an older one.
        """
        path = build_record(tmp_path, tmp_path / "p.ddd.json", severity=override)
        refused: dict[Path, str] = {}
        assert load_builds([path], refused) == []
        assert refused == {path: reason}

    def test_a_record_skipped_for_its_severities_is_said_out_loud(self, tmp_path: Path) -> None:
        """Skipped silently it looks exactly like a workspace nobody configured a build in."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("input", "X")),
            },
        )
        build_record(tmp_path, tmp_path / "p.ddd.json", severity=["no-such-check=ignore"])
        writer = io.BytesIO()
        server = Server(io.BytesIO(), writer, root=tmp_path)
        server.refresh(tmp_path / "a.ddd.json")
        said = [
            message["params"]["message"]
            for message in sent(writer)
            if message.get("method") == "window/logMessage"
        ]
        assert said == [
            f"{tmp_path / 'build' / 'ddd' / 'firmware.elf' / BUILD_INFO_FILENAME}: unknown check "
            "'no-such-check'; this record is ignored, so the project it names is not analysed"
        ]
        # and the server carries on, answering for the file that was opened through the
        # project above it, which is what it does for any file no usable record claims
        drawn = published(writer)[(tmp_path / "a.ddd.json").as_uri()]
        assert [entry["code"] for entry in drawn] == ["missing-producer"]

    def test_a_record_from_a_newer_ddd_is_said_out_loud(self, tmp_path: Path) -> None:
        write_tree(tmp_path, {"p.ddd.json": project("P")})
        record = build_record(
            tmp_path, tmp_path / "p.ddd.json", format=BUILD_INFO_FORMAT + 1, colour="blue"
        )
        writer = io.BytesIO()
        Server(io.BytesIO(), writer, root=tmp_path).refresh(tmp_path / "p.ddd.json")
        said = [
            message["params"]["message"]
            for message in sent(writer)
            if message.get("method") == "window/logMessage"
        ]
        assert said == [
            f"{record}: {NEWER_RECORD}; this record is ignored, so the project it names is not "
            "analysed"
        ]

    def test_a_record_naming_its_project_by_a_relative_path_is_said_out_loud(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``ddd build-info`` writes the path absolute, because whoever reads the record is not
        in the directory the build ran in. A hand-made record naming it relative was taken and
        analysed from the server's working directory, and with a check no plugin registers, the
        finding filed at that path had no uri: the first open ended the session. Opened from
        the directory the path is relative to, as it was, so that the path names a file."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("input", "X")),
            },
        )
        record = build_record(
            tmp_path,
            tmp_path / "p.ddd.json",
            severity=["nosuch/check=ignore"],
            project="p.ddd.json",
        )
        monkeypatch.chdir(tmp_path)
        opened = tmp_path / "a.ddd.json"
        writer = io.BytesIO()
        stream = session(
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didOpen",
                "params": {"textDocument": {"uri": opened.as_uri()}},
            },
            *END,
        )
        assert Server(stream, writer, root=tmp_path).run() == 0
        said = [
            message["params"]["message"]
            for message in sent(writer)
            if message.get("method") == "window/logMessage"
        ]
        assert said == [
            f"{record}: its project 'p.ddd.json' is a relative path, which a build never writes: "
            "it names a different file from each directory the record is read in; this record is "
            "ignored, so the project it names is not analysed"
        ]
        # Checked as any file no usable record claims is, through the project above it.
        drawn = published(writer)[opened.as_uri()]
        assert [entry["code"] for entry in drawn] == ["missing-producer"]


NEWER_RECORD = (
    f"written in format {BUILD_INFO_FORMAT + 1} by a newer DDD, and this one understands up to "
    f"format {BUILD_INFO_FORMAT}"
)
"""Why a build record one format newer than this version reads is refused."""


EXITING_CHECK_PLUGIN = """
import sys

from ddd.plugins import CheckContext, Plugin


def check(context: CheckContext) -> None:
    sys.exit(0)


PLUGIN = Plugin(name="exiting", check=check)
"""

REGISTERING_PLUGIN = """
from ddd.diagnostics import CheckInfo, Severity
from ddd.plugins import CheckContext, Plugin


def check(context: CheckContext) -> None:
    return None


PLUGIN = Plugin(
    name="demo",
    checks=(CheckInfo("demo/tagged", Severity.WARNING, "a demonstration check"),),
    check=check,
)
"""

EXITING_MODEL_PLUGIN = """
import sys

from pydantic import BaseModel, field_validator

from ddd.plugins import Plugin


class Tag(BaseModel):
    tag: str

    @field_validator("tag")
    @classmethod
    def own_code(cls, value: str) -> str:
        sys.exit(9)


PLUGIN = Plugin(name="exiting", object_model=Tag)
"""


class TestDiagnostics:
    """What the editor draws, and on which file."""

    def test_a_project_lights_up_every_file_it_covers(self, tmp_path: Path) -> None:
        """Two components disagreeing is one finding on each side; publishing only the saved
        file would leave half of every disagreement invisible."""
        build_record(tmp_path, INCONSISTENT)
        reports = service.collect(discover(tmp_path))
        named = {path.name: findings for path, findings in reports.items()}
        assert named["component_b.ddd.json"][0]["code"] == "multiple-producers"
        assert named["component_c.ddd.json"][0]["code"] == "definition-mismatch"
        # and the project file itself is covered, with nothing to say about it
        assert named["project.ddd.json"] == []

    def test_both_sides_of_a_conflict_are_marked(self, tmp_path: Path) -> None:
        """Neither declaration of a duplicated output is the wrong one.

        ``ddd check`` reports the conflict once, with a note at the other declaration, which
        is right for a list read whole. In an editor a file with no finding on it looks
        correct, so reporting only one side says the other component is fine - and it is not.
        """
        build_record(tmp_path, INCONSISTENT)
        reports = service.collect(discover(tmp_path))
        marked = {
            path.name
            for path, findings in reports.items()
            if any(entry["code"] == "multiple-producers" for entry in findings)
        }
        assert marked == {"component_a.ddd.json", "component_b.ddd.json"}

    def test_a_mirrored_finding_lands_on_the_other_declaration(self, tmp_path: Path) -> None:
        """At the place the note pointed at, not at the top of the file it is in."""
        build_record(tmp_path, INCONSISTENT)
        reports = service.collect(discover(tmp_path))
        producer = next(path for path in reports if path.name == "component_a.ddd.json")
        conflict = next(
            entry for entry in reports[producer] if entry["code"] == "multiple-producers"
        )
        primary = next(
            entry
            for path, findings in reports.items()
            if path.name == "component_b.ddd.json"
            for entry in findings
            if entry["code"] == "multiple-producers"
        )
        # The same message on both, because it already names both components.
        assert conflict["message"] == primary["message"]
        # The copy carries no notes: they read in one direction and it points the other way.
        assert "relatedInformation" not in conflict
        assert "relatedInformation" in primary

    def test_a_finding_is_not_mirrored_onto_itself(self) -> None:
        """A note pointing where the finding already is would double it in place."""
        location = Location(Path("a.ddd.json"), "component.interface[0]")
        finding = Diagnostic(
            "duplicate-declaration", Severity.ERROR, "twice", location, (("here", location),)
        )
        assert service._mirrors(finding) == []

    def test_a_finding_with_nowhere_to_be_has_nothing_to_mirror(self) -> None:
        finding = Diagnostic("include-empty", Severity.ERROR, "nothing matched", None)
        assert service._mirrors(finding) == []

    def test_a_finding_points_at_the_other_declaration(self, tmp_path: Path) -> None:
        build_record(tmp_path, INCONSISTENT)
        reports = service.collect(discover(tmp_path))
        # The one reported against component_b; the copy on component_a carries no notes.
        finding = next(
            entry
            for path, findings in reports.items()
            if path.name == "component_b.ddd.json"
            for entry in findings
            if entry["code"] == "multiple-producers"
        )
        (related,) = finding["relatedInformation"]
        assert related["location"]["uri"].endswith("component_a.ddd.json")
        assert related["message"] == "also written here"

    def test_the_severity_policy_of_the_build_is_applied(self, tmp_path: Path) -> None:
        """Otherwise the editor and the build disagree about the same working tree."""
        build_record(tmp_path, INCONSISTENT, severity=["multiple-producers=info"])
        reports = service.collect(discover(tmp_path))
        finding = next(
            entry
            for findings in reports.values()
            for entry in findings
            if entry["code"] == "multiple-producers"
        )
        assert finding["severity"] == 3  # information, not error

    def test_a_file_no_build_claims_is_checked_through_the_project_above_it(
        self, tmp_path: Path
    ) -> None:
        """The state of every checkout nobody has configured a build in.

        Read on its own, a component has no types, so a declaration naming one resolves to
        nothing and the variable disappears from the run - silently, because the check that
        would have said so is one of those a lone file cannot answer. Finding the project
        restores the whole answer, and it is the same one the jumps and the hover give.
        """
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "t.ddd.json", "components/a.ddd.json"),
                "t.ddd.json": {
                    "types": [
                        {
                            "type": "struct",
                            "name": "S_t",
                            "members": [
                                {
                                    "name": "v",
                                    "member": "value",
                                    "datatype": "uint8",
                                    "conversion": {},
                                }
                            ],
                        }
                    ]
                },
                "components/a.ddd.json": component("A", declare("output", "X", typename="S_t")),
            },
        )
        document = tmp_path / "components" / "a.ddd.json"
        reports = service.collect([], [document], tmp_path)
        # The project's own file is in the report, which is how it was reached at all.
        assert (tmp_path / "p.ddd.json") in reports
        codes = {entry["code"] for findings in reports.values() for entry in findings}
        assert "unknown-type" not in codes
        # 'missing-id' needs no other component either, so full project context reports it
        # exactly as standalone mode would - unlike 'unknown-type', it is not one of the
        # checks that context was needed to answer.
        assert codes == {"unused-output", "missing-id"}

    def test_a_component_two_images_share_is_not_underlined_twice(self, tmp_path: Path) -> None:
        """Every build is run, and a component linked into two images is in both. The two runs
        filed their findings against the same files, so every squiggle was drawn twice and the
        Problems count doubled, with nothing to tell the two apart."""
        build_record(tmp_path, INCONSISTENT)
        alone = discover(tmp_path)
        build_record(tmp_path, INCONSISTENT, image="test.elf")
        assert len(discover(tmp_path)) == 2
        assert service.collect(discover(tmp_path)) == service.collect(alone)

    def test_two_images_that_disagree_both_have_their_say(self, tmp_path: Path) -> None:
        """Only an identical finding is dropped. Where the policies differ the two really are
        two findings, and which image reports the error is what the reader needs to see."""
        build_record(tmp_path, INCONSISTENT)
        build_record(tmp_path, INCONSISTENT, image="test.elf", severity=["unused-output=error"])
        reports = service.collect(discover(tmp_path))
        drawn = reports[INCONSISTENT.parent / "component_a.ddd.json"]
        assert sorted(entry["severity"] for entry in drawn if entry["code"] == "unused-output") == [
            1,
            2,
        ]

    def test_a_project_file_no_build_claims_is_checked_as_the_project_it_is(self) -> None:
        """The standalone policy is for "a component read alone"; a project file is not one.

        Nothing includes a project file, so the search above it finds nothing and it used to
        fall through to the policy that silences the nine checks the project is the only thing
        able to answer - in the state every unconfigured checkout is in.
        """
        reports = service.collect([], [INCONSISTENT], INCONSISTENT.parent)
        codes = {entry["code"] for findings in reports.values() for entry in findings}
        assert codes == {
            "multiple-producers",
            "definition-mismatch",
            "missing-producer",
            "local-conflict",
            "unused-output",
        }

    def test_a_file_no_project_claims_falls_back_to_reading_it_alone(self, tmp_path: Path) -> None:
        """A thin answer, but the only honest one when there is nothing else to read."""
        write_tree(tmp_path, {"lonely.ddd.json": component("A", declare("local", "X"))})
        document = tmp_path / "lonely.ddd.json"
        reports = service.collect([], [document], tmp_path)
        assert set(reports) == {document}

    def test_a_file_no_build_claims_says_nothing_the_file_cannot_answer(
        self, tmp_path: Path
    ) -> None:
        """Read alone, a component has inputs nobody writes, outputs nobody reads and axes
        declared in files nobody handed over. All three are true by construction, and all
        three were reported by an editor that had simply not been shown the other files."""
        write_tree(
            tmp_path,
            {
                "lonely.ddd.json": component(
                    "Lonely",
                    declare("input", "NobodyWrites"),
                    declare("output", "NobodyReads"),
                    declare(
                        "output", "Curve", kind="curve", axis="AxisElsewhere", datatype="uint8"
                    ),
                )
            },
        )
        reports = service.collect([], [tmp_path / "lonely.ddd.json"])
        # 'NobodyReads' and 'Curve' are both producing declarations with no 'id', and that
        # finding needs no other component to be right, so it survives where the three
        # project-wide checks above do not.
        assert {entry["code"] for findings in reports.values() for entry in findings} == {
            "missing-id"
        }

    def test_what_one_file_can_decide_is_still_reported(self, tmp_path: Path) -> None:
        """Silencing the project-wide checks must not leave standalone mode saying nothing."""
        write_tree(
            tmp_path,
            {
                "lonely.ddd.json": component(
                    "Lonely", declare("output", "Value", datatype="uint8", init=999)
                )
            },
        )
        reports = service.collect([], [tmp_path / "lonely.ddd.json"])
        assert {entry["code"] for findings in reports.values() for entry in findings} == {
            "init-invalid",
            "missing-id",
        }

    def test_every_check_that_needs_the_whole_project_is_silenced(self) -> None:
        """The guard on the mistake that produced this rule.

        ``missing-producer`` was silenced by hand and ``unused-output`` - the same mistake
        seen from the other end - was not, so an editor reported it about every output of
        every component it had not been given the rest of.
        """
        from ddd.diagnostics import CHECKS

        needed = {name for name, check in CHECKS.items() if check.needs_every_component}
        assert needed == {entry.split("=")[0] for entry in service.STANDALONE_POLICY}
        assert needed, "the rule is derived from the registry; nothing marked means no guard"

    def test_a_file_a_build_already_covers_is_not_read_twice(self, tmp_path: Path) -> None:
        build_record(tmp_path, INCONSISTENT)
        covered = INCONSISTENT.parent / "component_a.ddd.json"
        with_document = service.collect(discover(tmp_path), [covered])
        assert with_document == service.collect(discover(tmp_path))

    def test_a_project_that_did_not_read_is_not_resolved(self, tmp_path: Path) -> None:
        """The two phases, as ``ddd check`` runs them.

        There is no point resolving references between files that could not all be read, so a
        file caught mid edit shows its own mistake rather than a screenful of consequences.
        """
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": {"component": {"name": "A", "nonsense": 1}},
            },
        )
        build_record(tmp_path, tmp_path / "p.ddd.json")
        reports = service.collect(discover(tmp_path))
        assert {entry["code"] for findings in reports.values() for entry in findings} == {"schema"}

    def test_a_root_that_cannot_be_read_still_reports_why(self, tmp_path: Path) -> None:
        absent = tmp_path / "absent.ddd.json"
        reports = service.collect([], [absent])
        assert reports[absent][0]["code"] == "file-not-found"

    def test_a_finding_about_no_particular_place_lands_on_the_root(self, tmp_path: Path) -> None:
        bag = DiagnosticBag()
        bag.add("include-empty", "matched nothing")
        grouped: dict[Path, list[Diagnostic]] = {}
        service.group_findings(bag, tmp_path / "root.ddd.json", grouped)
        assert list(grouped) == [tmp_path / "root.ddd.json"]

    def test_a_note_with_nowhere_to_point_lands_on_the_file_of_its_finding(
        self, tmp_path: Path
    ) -> None:
        """Every piece of related information carries a location, so one is given: the first
        line of the file the finding itself is on, which is what the docstring always claimed.

        It was sending ``""`` instead, which a client reads as ``file:///`` - a note the
        reader can click, landing nowhere near the project.
        """
        finding = Diagnostic("schema", Severity.ERROR, "bad name", None, (("try harder", None),))
        published = service._as_lsp(finding, {}, tmp_path / "a.ddd.json")
        (related,) = published["relatedInformation"]
        assert related["message"] == "try harder"
        assert related["location"]["uri"] == (tmp_path / "a.ddd.json").as_uri()

    def test_a_file_that_cannot_be_read_still_gets_a_range(self, tmp_path: Path) -> None:
        gone = tmp_path / "gone.json"
        finding = Diagnostic("schema", Severity.ERROR, "unreadable", Location(gone, "a.b"))
        assert service._as_lsp(finding, {}, gone)["range"]["start"] == {"line": 0, "character": 0}

    def test_a_hook_that_exits_is_reported_and_the_server_keeps_running(
        self, tmp_path: Path
    ) -> None:
        """``sys.exit()`` in a hook is not a ``PluginError`` by itself - only wrapped as one at
        the ``_call`` boundary - so before that wrapping this used to propagate out of
        ``collect`` as a bare ``SystemExit`` and end the server process. The project promises
        findings and never an exception; this project file opened with no build claiming it is
        exactly what an editor hands the server on the first keystroke of a new file."""
        write_tree(
            tmp_path,
            {
                "tools/exiting_plugin.py": EXITING_CHECK_PLUGIN,
                "project.ddd.json": project("P", "a.ddd.json", plugins=["tools/exiting_plugin.py"]),
                "a.ddd.json": component("A", declare("local", "X")),
            },
        )
        document = tmp_path / "project.ddd.json"
        reports = service.collect([], [document])
        # collect() returned at all, rather than the process going down with it: the server
        # keeps running.
        findings = reports[document]
        plugin_invalid = [entry for entry in findings if entry["code"] == "plugin-invalid"]
        assert len(plugin_invalid) == 1
        assert (
            "plugin 'exiting' failed in its check hook: SystemExit(0)"
            in plugin_invalid[0]["message"]
        )

    def test_a_model_that_exits_does_not_take_the_search_for_a_project_down(
        self, tmp_path: Path
    ) -> None:
        """Which project covers an open component is a search: every candidate above it is
        loaded and asked, and loading one runs the models its plugins declare over every
        ``extensions`` block in it. The squiggles, the hovers and the jumps all go through that
        search, so a plugin defect met there has to end as an answer - here, the component read
        on its own - rather than as an exception nobody catches."""
        write_tree(
            tmp_path,
            {
                "tools/exiting_plugin.py": EXITING_MODEL_PLUGIN,
                "project.ddd.json": project("P", "a.ddd.json", plugins=["tools/exiting_plugin.py"]),
                "a.ddd.json": component(
                    "A", declare("local", "X", extensions={"exiting": {"tag": "t"}})
                ),
            },
        )
        document = tmp_path / "a.ddd.json"
        found = navigation.resolve_projects(document, tmp_path)
        assert found.projects == ()
        assert list(found.failed) == [tmp_path / "project.ddd.json"]
        reports = service.collect([], [document], tmp_path)
        assert document in reports

    def test_a_project_that_could_not_be_read_is_named_even_with_no_build_record(
        self, tmp_path: Path
    ) -> None:
        """A component opened in an unconfigured tree is checked through the project above it,
        and a plugin defect makes that project unreadable. Answering with the standalone
        analysis alone would be the quietest possible failure: a thin set of findings, no sign
        that a fuller answer exists, and nothing anywhere naming the plugin that is broken.
        The finding goes on the project file, where the defect is, and the component still
        gets the analysis it can have."""
        write_tree(
            tmp_path,
            {
                "tools/exiting_plugin.py": EXITING_MODEL_PLUGIN,
                "project.ddd.json": project("P", "a.ddd.json", plugins=["tools/exiting_plugin.py"]),
                "a.ddd.json": component(
                    "A", declare("local", "X", extensions={"exiting": {"tag": "t"}})
                ),
            },
        )
        document = tmp_path / "a.ddd.json"
        reports = service.collect([], [document], tmp_path)
        (broken,) = reports[tmp_path / "project.ddd.json"]
        assert broken["code"] == "plugin-invalid"
        assert "plugin 'exiting' failed validating an 'extensions' block" in broken["message"]
        # and the component is still checked for what one file can settle
        assert [entry["code"] for entry in reports[document]] == ["missing-id"]

    def test_a_project_that_could_not_be_read_reports_its_files_once(self, tmp_path: Path) -> None:
        """A read that a plugin defect stops has already reported on every file it read - the
        blocks are validated once the whole tree is in - so the findings of an open file are
        in hand while the project covers, by its own account, nothing but itself. Counting the
        loaded files alone left the open one looking unchecked, so it was checked again on its
        own and every finding on it was published twice, on the same line."""
        write_tree(
            tmp_path,
            {
                "tools/exiting_plugin.py": EXITING_MODEL_PLUGIN,
                "project.ddd.json": project(
                    "P", "a.ddd.json", "b.ddd.json", plugins=["tools/exiting_plugin.py"]
                ),
                "a.ddd.json": component("A", declare("nonsense", "X")),
                "b.ddd.json": component(
                    "B", declare("local", "Y", extensions={"exiting": {"tag": "t"}})
                ),
            },
        )
        build_record(tmp_path, tmp_path / "project.ddd.json")
        document = tmp_path / "a.ddd.json"
        reports = service.collect(discover(tmp_path), [document], tmp_path)
        assert [entry["code"] for entry in reports[document]] == ["schema"]
        assert [entry["code"] for entry in reports[tmp_path / "project.ddd.json"]] == [
            "plugin-invalid"
        ]


class TestRuns:
    """What the GUI reads from an analysis: the findings, the files, and the dictionary."""

    def test_a_project_run_keeps_the_dictionary_it_resolved(self) -> None:
        run = service.run_project(DEMO)
        assert run.dictionary is not None
        assert run.dictionary.name == "DemoDevice"
        assert DEMO.resolve() in run.covered
        assert not run.bag.has_errors

    def test_a_read_that_reported_an_error_resolves_nothing(self, tmp_path: Path) -> None:
        write_tree(tmp_path, {"p.ddd.json": project("P", "a.ddd.json"), "a.ddd.json": "{"})
        run = service.run_project(tmp_path / "p.ddd.json")
        assert run.dictionary is None
        assert "json-syntax" in checks(run.bag)

    def test_a_root_that_cannot_be_read_covers_itself_alone(self, tmp_path: Path) -> None:
        absent = tmp_path / "absent.ddd.json"
        run = service.run_project(absent)
        assert run.dictionary is None
        assert run.covered == frozenset({absent})

    def test_a_build_run_applies_the_builds_severities(self, tmp_path: Path) -> None:
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Unread")),
            },
        )
        info = BuildInfo(
            project=(tmp_path / "p.ddd.json").as_posix(), severity=("unused-output=error",)
        )
        run = service.run_build(info)
        assert run.dictionary is not None
        assert [d.severity for d in run.bag if d.check == "unused-output"] == [Severity.ERROR]

    def test_a_plugin_that_raises_during_the_analysis_leaves_no_dictionary(
        self, tmp_path: Path
    ) -> None:
        write_tree(
            tmp_path,
            {
                "tools/exiting_plugin.py": EXITING_CHECK_PLUGIN,
                "p.ddd.json": project("P", "a.ddd.json", plugins=["tools/exiting_plugin.py"]),
                "a.ddd.json": component("A", declare("local", "X")),
            },
        )
        run = service.run_project(tmp_path / "p.ddd.json")
        assert run.dictionary is None
        assert "plugin-invalid" in checks(run.bag)

    def test_the_old_answers_are_the_runs_answers(self) -> None:
        bag, covered = service.analyse(BuildInfo(project=DEMO.as_posix()))
        assert covered == service.run_project(DEMO).covered
        assert not bag.has_errors

    def test_a_project_run_keeps_the_index_of_what_it_read(self) -> None:
        run = service.run_project(DEMO)
        assert run.index is not None
        assert sorted(site.path.name for site in run.index.declarations["ValueA"]) == [
            "controller.ddd.json",
            "sensor_hub.ddd.json",
        ]

    def test_a_root_that_cannot_be_read_has_no_index(self, tmp_path: Path) -> None:
        assert service.run_project(tmp_path / "absent.ddd.json").index is None


class TestTheOverrideReachesRunProjectAndRunBuild:
    """``includes`` has to thread through ``_run`` from both of its callers.

    Every other test of ``run_project`` and ``run_build`` passes no override, so a thread
    silently dropped inside ``_run`` itself, or inside either function on its way there,
    would still leave every one of those lines covered. Only a run that actually changes
    what the root loads catches that: a component carrying a finding is there by default
    and gone once ``includes=[]`` replaces the root's own list.
    """

    @staticmethod
    def _tree(tmp_path: Path) -> Path:
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Unread")),
            },
        )
        return tmp_path / "p.ddd.json"

    def test_run_project_applies_the_override(self, tmp_path: Path) -> None:
        root = self._tree(tmp_path)
        assert "unused-output" in checks(service.run_project(root).bag)
        assert "unused-output" not in checks(service.run_project(root, includes=[]).bag)

    def test_run_build_applies_the_override(self, tmp_path: Path) -> None:
        root = self._tree(tmp_path)
        info = BuildInfo(project=root.as_posix())
        assert "unused-output" in checks(service.run_build(info).bag)
        assert "unused-output" not in checks(service.run_build(info, includes=[]).bag)


class TestTheProjectIsReadOnce:
    """How often a refresh and a request read the project above the document.

    The search for a containing project loads every candidate and asks it whether it includes
    the document - and then threw the answer away, so the caller loaded the winner a second
    time to do anything with it: twice per save in ``collect``, and twice more in the first
    hover after one, through ``workspaces``. A flat directory of two hundred components cost
    half a second per save and 2.2 seconds for that hover, against 0.7 for ``ddd check`` of
    the whole project. Counted rather than timed, because what was wrong is the number of
    reads and not how fast the machine that does them is.
    """

    def loads(self, monkeypatch: pytest.MonkeyPatch) -> list[Path]:
        """Every file the server reads a workspace out of, in order, wherever it does it."""
        seen: list[Path] = []

        def spy(path: Path, bag: DiagnosticBag) -> Any:
            seen.append(path)
            return load_workspace(path, bag)

        monkeypatch.setattr(navigation, "load_workspace", spy)
        monkeypatch.setattr(service, "load_workspace", spy)
        return seen

    def workspace(self, tmp_path: Path) -> Path:
        write_tree(
            tmp_path,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "X")),
                "b.ddd.json": component("B", declare("input", "X")),
            },
        )
        return tmp_path / "a.ddd.json"

    def test_a_refresh_reads_it_once(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        document = self.workspace(tmp_path)
        seen = self.loads(monkeypatch)
        reports = service.collect([], [document], tmp_path)
        assert document in reports, "the document was checked through the project above it"
        assert seen.count(tmp_path / "project.ddd.json") == 1, seen

    def test_a_request_after_it_reads_it_once(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        document = self.workspace(tmp_path)
        seen = self.loads(monkeypatch)
        found = navigation.workspaces([], document, tmp_path)
        assert len(found) == 1, "the project above the document is what answers"
        assert seen.count(tmp_path / "project.ddd.json") == 1, seen

    def test_a_project_whose_read_reported_an_error_is_not_analysed(self, tmp_path: Path) -> None:
        """The guard the second phase has always had, now that the read it guards is the one
        the search did: there is no point resolving references between files that could not
        all be read, and the reader's own finding is what says so."""
        write_tree(
            tmp_path,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("input", "X")),
                "b.ddd.json": component("B", declare("nonsense", "X")),
            },
        )
        reports = service.collect([], [tmp_path / "a.ddd.json"], tmp_path)
        assert [entry["code"] for entry in reports[tmp_path / "b.ddd.json"]] == ["schema"]
        assert reports[tmp_path / "a.ddd.json"] == [], (
            "the analysis ran over a project one of whose files did not read"
        )

    def test_a_hook_that_exits_under_the_containing_project_is_reported(
        self, tmp_path: Path
    ) -> None:
        """The document is checked through the project above it, so a hook that ends the
        process is met there as readily as under a build record - and has to end as a finding
        on the project file rather than as an exception nobody catches."""
        write_tree(
            tmp_path,
            {
                "tools/exiting_plugin.py": EXITING_CHECK_PLUGIN,
                "project.ddd.json": project("P", "a.ddd.json", plugins=["tools/exiting_plugin.py"]),
                "a.ddd.json": component("A", declare("local", "X")),
            },
        )
        reports = service.collect([], [tmp_path / "a.ddd.json"], tmp_path)
        findings = reports[tmp_path / "project.ddd.json"]
        assert [entry["code"] for entry in findings] == ["plugin-invalid"]
        assert "check hook: SystemExit(0)" in findings[0]["message"]


class TestNavigation:
    """The jumps that leave the file, which is every jump worth having."""

    def workspace(self, tmp_path: Path) -> Path:
        """Two components sharing a variable, and a project that ties them together."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component(
                    "A", declare("output", "Shared"), declare("local", "Private")
                ),
                "b.ddd.json": component("B", declare("input", "Shared")),
            },
        )
        return tmp_path / "p.ddd.json"

    def index_of(self, root: Path) -> Any:
        from ddd.lsp.navigation import index

        return index(load_workspace(root, DiagnosticBag()))

    def test_an_input_leads_to_whoever_writes_it(self, tmp_path: Path) -> None:
        """The question an author actually has, and the one a schema can never answer."""
        from ddd.lsp.navigation import definition

        built = self.index_of(self.workspace(tmp_path))
        consumer = tmp_path / "b.ddd.json"
        document = read(consumer, {})
        pointer = "component.interface[0].definition.name"
        (site,) = definition(built, document, consumer, pointer)
        assert site.path == tmp_path / "a.ddd.json"
        assert site.pointer == "component.interface[0].definition"

    def test_a_local_counts_as_its_own_producer(self, tmp_path: Path) -> None:
        from ddd.lsp.navigation import definition

        root = self.workspace(tmp_path)
        producer = tmp_path / "a.ddd.json"
        document = read(producer, {})
        (site,) = definition(
            self.index_of(root), document, producer, "component.interface[1].definition.name"
        )
        assert site.pointer == "component.interface[1].definition"

    def test_references_reach_both_sides(self, tmp_path: Path) -> None:
        from ddd.lsp.navigation import references

        root = self.workspace(tmp_path)
        consumer = tmp_path / "b.ddd.json"
        document = read(consumer, {})
        found = references(self.index_of(root), document, "component.interface[0].definition.name")
        assert {site.path.name for site in found} == {"a.ddd.json", "b.ddd.json"}

    def test_a_reference_key_jumps_as_a_name_does(self, tmp_path: Path) -> None:
        """``axis`` names an object declared somewhere else entirely."""
        from ddd.lsp.navigation import definition

        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    declare("output", "Axis", kind="axis", size=4),
                    declare("output", "Curve", kind="curve", axis="Axis"),
                ),
            },
        )
        path = tmp_path / "a.ddd.json"
        (site,) = definition(
            self.index_of(tmp_path / "p.ddd.json"),
            read(path, {}),
            path,
            "component.interface[1].definition.axis",
        )
        assert site.pointer == "component.interface[0].definition"

    def test_a_nested_structure_leads_to_its_declaration(self, tmp_path: Path) -> None:
        from ddd.lsp.navigation import definition, references

        types = {
            "types": [
                {
                    "type": "struct",
                    "name": "Inner_t",
                    "members": [
                        {"name": "v", "member": "value", "datatype": "uint8", "conversion": {}}
                    ],
                },
                {
                    "type": "struct",
                    "name": "Outer_t",
                    "members": [{"name": "inner", "member": "value", "typename": "Inner_t"}],
                },
            ]
        }
        write_tree(tmp_path, {"p.ddd.json": project("P", "t.ddd.json"), "t.ddd.json": types})
        path = tmp_path / "t.ddd.json"
        built = self.index_of(tmp_path / "p.ddd.json")
        document = read(path, {})
        (site,) = definition(built, document, path, "types[1].members[0].typename")
        assert site.pointer == "types[0]"
        assert {found.pointer for found in references(built, document, "types[0].name")} == {
            "types[0]",
            "types[1].members[0].typename",
        }

    def test_a_scalar_type_is_indexed_although_it_has_no_members(self, tmp_path: Path) -> None:
        """It can be jumped to like any other type; there is simply nothing inside it to use."""
        from ddd.lsp.navigation import definition

        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "t.ddd.json"),
                "t.ddd.json": {
                    "types": [
                        {
                            "type": "scalar",
                            "name": "Speed_t",
                            "datatype": "uint16",
                            "unit": "rpm",
                            "conversion": {},
                        },
                        {
                            "type": "struct",
                            "name": "S_t",
                            "members": [{"name": "v", "member": "value", "typename": "Speed_t"}],
                        },
                    ]
                },
            },
        )
        path = tmp_path / "t.ddd.json"
        built = self.index_of(tmp_path / "p.ddd.json")
        (site,) = definition(built, read(path, {}), path, "types[1].members[0].typename")
        assert site.pointer == "types[0]"

    def test_a_declaration_naming_a_type_jumps_to_the_type(self, tmp_path: Path) -> None:
        """The type is what is under the pointer, so that is where the jump goes.

        A base datatype names no file and falls through to the ordinary jump, which lands on
        the declaration that produces the object - the behaviour a reader resting on ``uint16``
        already expects.
        """
        from ddd.lsp.navigation import definition, references

        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "t.ddd.json", "a.ddd.json"),
                "t.ddd.json": {
                    "types": [
                        {
                            "type": "scalar",
                            "name": "Speed_t",
                            "datatype": "uint16",
                            "unit": "rpm",
                            "conversion": {},
                        }
                    ]
                },
                "a.ddd.json": component("A", declare("output", "S", typename="Speed_t")),
            },
        )
        path = tmp_path / "a.ddd.json"
        built = self.index_of(tmp_path / "p.ddd.json")
        document = read(path, {})
        pointer = "component.interface[0].definition.typename"
        (site,) = definition(built, document, path, pointer)
        assert site.path == tmp_path / "t.ddd.json"
        # And the declaration counts as a use of the type, so find-references lists it.
        assert {found.pointer for found in references(built, document, pointer)} == {
            "types[0]",
            pointer,
        }

    def test_a_base_datatype_answers_about_the_object_rather_than_a_type(
        self, tmp_path: Path
    ) -> None:
        """``uint16`` names nothing this project declares, so the question is the ordinary one.

        Falling through rather than answering nothing is what keeps the jump and the hover
        agreeing from every position inside a declaration.
        """
        from ddd.lsp.navigation import references

        root = self.workspace(tmp_path)
        path = tmp_path / "b.ddd.json"
        found = references(
            self.index_of(root), read(path, {}), "component.interface[0].definition.typename"
        )
        assert {site.path.name for site in found} == {"a.ddd.json", "b.ddd.json"}

    def test_references_on_an_unknown_typename_fall_back_to_the_object(
        self, tmp_path: Path
    ) -> None:
        """A name no types file declares still answers with the object's declarations."""
        from ddd.lsp.navigation import references

        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X", typename="Nowhere_t")),
            },
        )
        path = tmp_path / "a.ddd.json"
        found = references(
            self.index_of(tmp_path / "p.ddd.json"),
            read(path, {}),
            "component.interface[0].definition.typename",
        )
        assert {site.pointer for site in found} == {"component.interface[0].definition"}

    def test_an_unknown_name_leads_nowhere_rather_than_anywhere(self, tmp_path: Path) -> None:
        from ddd.lsp.navigation import definition, references

        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("input", "Nobody")),
                "t.ddd.json": {
                    "types": [
                        {
                            "type": "struct",
                            "name": "T_t",
                            "members": [{"name": "n", "member": "value", "typename": "Absent_t"}],
                        }
                    ]
                },
            },
        )
        built = self.index_of(tmp_path / "p.ddd.json")
        path = tmp_path / "a.ddd.json"
        # An input nobody writes: the jump has nowhere to go, which is the same thing the
        # missing-producer check reports about it.
        assert (
            definition(built, read(path, {}), path, "component.interface[0].definition.name") == []
        )
        types = tmp_path / "t.ddd.json"
        document = read(types, {})
        assert definition(built, document, types, "types[0].members[0].typename") == []
        assert references(built, document, "types[0].members[0].typename") == []

    def test_an_include_leads_to_the_file_it_names(self, tmp_path: Path) -> None:
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A"),
            },
        )
        from ddd.lsp.navigation import definition

        root = tmp_path / "p.ddd.json"
        (site,) = definition(self.index_of(root), read(root, {}), root, "project.includes[0]")
        assert site.path.parent == tmp_path
        assert site.pointer == ""

    def test_a_path_that_names_nothing_leads_nowhere(self, tmp_path: Path) -> None:
        from ddd.lsp.navigation import definition

        write_tree(tmp_path, {"p.ddd.json": project("P", "absent.ddd.json")})
        root = tmp_path / "p.ddd.json"
        assert definition(self.index_of(root), read(root, {}), root, "project.includes[0]") == []

    def test_a_wildcard_include_leads_to_every_file_it_matches(self, tmp_path: Path) -> None:
        """The ordinary way to write one: a jump that needed them spelled out would miss it."""
        from ddd.lsp.navigation import definition

        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "components/*.ddd.json"),
                "components/a.ddd.json": component("A"),
                "components/b.ddd.json": component("B"),
            },
        )
        root = tmp_path / "p.ddd.json"
        found = definition(self.index_of(root), read(root, {}), root, "project.includes[0]")
        assert {site.path.name for site in found} == {"a.ddd.json", "b.ddd.json"}

    def test_an_include_that_cannot_be_relative_leads_nowhere(self, tmp_path: Path) -> None:
        """A description is somebody's input, so an absolute pattern has to be survivable."""
        from ddd.lsp.navigation import definition

        write_tree(tmp_path, {"p.ddd.json": project("P", "/absolute/elsewhere.ddd.json")})
        root = tmp_path / "p.ddd.json"
        assert definition(self.index_of(root), read(root, {}), root, "project.includes[0]") == []

    @pytest.mark.parametrize("pointer", ["component.name", "component", ""])
    def test_a_cursor_outside_any_declaration_offers_no_jump(
        self, tmp_path: Path, pointer: str
    ) -> None:
        """A component name, the whole component, whitespace: nowhere to go from any of them."""
        from ddd.lsp.navigation import definition, references

        root = self.workspace(tmp_path)
        path = tmp_path / "b.ddd.json"
        document = read(path, {})
        assert definition(self.index_of(root), document, path, pointer) == []
        assert references(self.index_of(root), document, pointer) == []

    @pytest.mark.parametrize(
        "pointer",
        [
            "component.interface[0].definition.name",
            "component.interface[0].definition.datatype",
            "component.interface[0].definition",
            "component.interface[0].scope",
            "component.interface[0]",
        ],
    )
    def test_a_jump_answers_from_anywhere_the_hover_does(
        self, tmp_path: Path, pointer: str
    ) -> None:
        """The two have to agree, and they did not.

        A hover that said "written by A" from a position where "go to definition" then found
        nothing is the inconsistency, not the jump from a datatype.
        """
        from ddd.lsp.navigation import definition

        root = self.workspace(tmp_path)
        path = tmp_path / "b.ddd.json"
        (site,) = definition(self.index_of(root), read(path, {}), path, pointer)
        assert site.path == tmp_path / "a.ddd.json"

    def test_a_jump_answers_from_a_position_holding_no_string_at_all(self, tmp_path: Path) -> None:
        """A number is as much a part of the declaration as a name is."""
        from ddd.lsp.navigation import definition

        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component(
                    "A", declare("output", "Shared", limits={"min": 0, "max": 100})
                ),
                "b.ddd.json": component(
                    "B", declare("input", "Shared", limits={"min": 0, "max": 100})
                ),
            },
        )
        path = tmp_path / "b.ddd.json"
        (site,) = definition(
            self.index_of(tmp_path / "p.ddd.json"),
            read(path, {}),
            path,
            "component.interface[0].definition.limits.min",
        )
        assert site.path == tmp_path / "a.ddd.json"

    def test_a_file_no_build_claims_is_navigated_on_its_own(self, tmp_path: Path) -> None:
        from ddd.lsp.navigation import workspaces

        self.workspace(tmp_path)
        alone = tmp_path / "a.ddd.json"
        (found,) = workspaces([], alone)
        assert alone in found.workspace.sources()

    def test_a_document_that_is_in_no_project_at_all_yields_nothing(self, tmp_path: Path) -> None:
        from ddd.lsp.navigation import workspaces

        assert workspaces([], tmp_path / "absent.ddd.json") == []

    def test_the_project_that_contains_the_file_is_the_one_used(self, tmp_path: Path) -> None:
        from ddd.build_info import BuildInfo
        from ddd.lsp.navigation import workspaces

        root = self.workspace(tmp_path)
        other = tmp_path / "other"
        write_tree(other, {"q.ddd.json": project("Q")})
        builds = [
            BuildInfo(project=(other / "q.ddd.json").as_posix()),
            BuildInfo(project=root.as_posix()),
        ]
        (found,) = workspaces(builds, tmp_path / "a.ddd.json")
        assert found.workspace.name == "P"

    def test_files_of_one_name_are_told_apart_by_as_much_of_their_paths_as_it_takes(
        self,
    ) -> None:
        """A file is named by its name, as a refusal always named it, unless another of the list
        shares that name: then by its path from the first directory up that the two do not share,
        and in full where nothing short of that does, as for a file at the root."""
        named = navigation.told_apart(
            [
                Path("/w/one/units.ddd.json"),
                Path("/w/two/units.ddd.json"),
                Path("/w/a.ddd.json"),
                Path("/a/x/v.ddd.json"),
                Path("/b/x/v.ddd.json"),
                Path("/v.ddd.json"),
            ]
        )
        assert named == [
            "one/units.ddd.json",
            "two/units.ddd.json",
            "a.ddd.json",
            "a/x/v.ddd.json",
            "b/x/v.ddd.json",
            "/v.ddd.json",
        ]


class TestHover:
    """What the project made of a variable, which is not what the file under the cursor says."""

    def resolved(self, tmp_path: Path, *declarations: dict[str, Any], **extra: Any) -> Any:
        from ddd.build_info import BuildInfo
        from ddd.lsp.hover import resolve

        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", *declarations, **extra),
            },
        )
        info = BuildInfo(project=(tmp_path / "p.ddd.json").as_posix())
        return resolve(navigation.workspaces([info], tmp_path / "a.ddd.json"))

    def structured(self, tmp_path: Path) -> Any:
        from ddd.build_info import BuildInfo
        from ddd.lsp.hover import resolve

        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "t.ddd.json", "a.ddd.json"),
                "t.ddd.json": {
                    "types": [
                        {
                            "type": "scalar",
                            "name": "Temp_t",
                            "datatype": "uint16",
                            "unit": "degC",
                            "conversion": {"factor": 0.1, "offset": -40},
                        },
                        {
                            "type": "struct",
                            "name": "Sensor_t",
                            "description": "Everything one sensor measures",
                            "members": [
                                {"name": "latest", "member": "value", "typename": "Temp_t"},
                                {
                                    "name": "history",
                                    "member": "value",
                                    "datatype": "uint16",
                                    "conversion": {},
                                    "dimensions": [4],
                                },
                                {
                                    "name": "ready",
                                    "member": "bits",
                                    "datatype": "uint16",
                                    "conversion": {},
                                    "bits": 1,
                                },
                            ],
                        },
                    ]
                },
                "a.ddd.json": component(
                    "A",
                    declare(
                        "output",
                        "Inlet",
                        typename="Sensor_t",
                        volatile=True,
                        description="The inlet sensor as this ecu sees it",
                    ),
                ),
            },
        )
        info = BuildInfo(project=(tmp_path / "p.ddd.json").as_posix())
        return resolve(navigation.workspaces([info], tmp_path / "a.ddd.json"))

    def test_a_component_finds_the_project_above_it_when_no_build_claims_it(
        self, tmp_path: Path
    ) -> None:
        """Otherwise a structured declaration resolves to nothing in an unconfigured tree.

        A component read on its own has no types at all, so ``Sensor_t`` names nothing, the
        declaration is dropped and there is no variable left to describe. That is the ordinary
        state of a checkout nobody has run cmake in, which is where an editor is most useful.

        A search rather than a guess: the project is loaded and asked whether it includes this
        file, so one that does not is discarded however close it sits.
        """
        from ddd.lsp.hover import describe, resolve

        dictionary = self.structured(tmp_path)
        assert dictionary is not None
        # Same document, but resolved with no build record at all.
        found = resolve(navigation.workspaces([], tmp_path / "a.ddd.json", tmp_path))
        assert found is not None
        assert describe(found, "Inlet") is not None

    def test_the_project_may_be_a_directory_or_more_above_the_component(
        self, tmp_path: Path
    ) -> None:
        """The ordinary layout: a project at the top, its components in a folder beneath it."""
        from ddd.lsp.hover import describe, resolve

        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "components/a.ddd.json"),
                "components/a.ddd.json": component("A", declare("local", "Deep")),
            },
        )
        found = resolve(navigation.workspaces([], tmp_path / "components" / "a.ddd.json", tmp_path))
        assert found is not None
        assert describe(found, "Deep") is not None

    def test_a_component_no_project_claims_is_still_read_on_its_own(self, tmp_path: Path) -> None:
        """A thin answer, but a real one: the file is what there is."""
        from ddd.lsp.hover import describe, resolve

        write_tree(tmp_path, {"lonely.ddd.json": component("A", declare("local", "X"))})
        found = resolve(navigation.workspaces([], tmp_path / "lonely.ddd.json", tmp_path))
        assert found is not None
        assert describe(found, "X") is not None

    def test_a_project_that_does_not_include_the_document_is_not_used(self, tmp_path: Path) -> None:
        """Proximity is not membership, which is why each candidate is asked rather than assumed."""
        from ddd.lsp.hover import describe, resolve

        write_tree(
            tmp_path,
            {
                "other.ddd.json": project("Other", "elsewhere.ddd.json"),
                "elsewhere.ddd.json": component("B", declare("local", "Y")),
                "mine.ddd.json": component("A", declare("local", "X")),
            },
        )
        found = resolve(navigation.workspaces([], tmp_path / "mine.ddd.json", tmp_path))
        assert found is not None
        # Read on its own, so it knows X and has never heard of Y.
        assert describe(found, "X") is not None
        assert describe(found, "Y") is None

    def test_a_structured_variable_is_described_by_its_members(self, tmp_path: Path) -> None:
        """Which is the whole reason for hovering one.

        The file under the cursor says ``"typename": "Sensor_t"`` and stops there; what is
        inside that name lives in another file, and what each member *means* - the unit and
        the limits the project worked out - is in neither.

        It used to answer nothing at all: a structured variable is not among the objects, and
        that is the only place the hover looked.
        """
        from ddd.lsp.hover import describe

        described = describe(self.structured(tmp_path), "Inlet")
        assert described is not None
        assert "**Inlet** — measurement, `Sensor_t`" in described
        assert "The inlet sensor as this ecu sees it" in described
        assert "| volatile | yes |" in described
        assert "**3 members**" in described
        # The storage as c spells it, and the meaning the project resolved.
        assert "| `latest` | `uint16` | degC | -40 .. 6513.5 |" in described
        assert "| `history` | `uint16[4]` |" in described
        assert "| `ready` | `uint16:1` | *none* | 0 .. 1 |" in described

    def test_a_structured_variable_answers_from_anywhere_inside_the_declaration(
        self, tmp_path: Path
    ) -> None:
        """The same rule every other declaration follows, and the position people land on."""
        from ddd.lsp.hover import describe
        from ddd.lsp.navigation import subject_at

        dictionary = self.structured(tmp_path)
        path = tmp_path / "a.ddd.json"
        document = read(path, {})
        for pointer in (
            "component.interface[0]",
            "component.interface[0].definition",
            "component.interface[0].definition.datatype",
            "component.interface[0].definition.volatile",
        ):
            name = subject_at(document, pointer)
            assert name == "Inlet", pointer
            assert describe(dictionary, name) is not None, pointer

    def test_an_array_of_structures_says_so(self, tmp_path: Path) -> None:
        from ddd.build_info import BuildInfo
        from ddd.lsp.hover import describe, resolve

        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "t.ddd.json", "a.ddd.json"),
                "t.ddd.json": {
                    "types": [
                        {
                            "type": "struct",
                            "name": "Cell_t",
                            "members": [
                                {
                                    "name": "raw",
                                    "member": "value",
                                    "datatype": "uint16",
                                    "conversion": {},
                                }
                            ],
                        }
                    ]
                },
                "a.ddd.json": component(
                    "A", declare("local", "Pack", typename="Cell_t", dimensions=[2])
                ),
            },
        )
        info = BuildInfo(project=(tmp_path / "p.ddd.json").as_posix())
        projects = navigation.workspaces([info], tmp_path / "a.ddd.json")
        described = describe(resolve(projects), "Pack")
        assert described is not None
        assert "| shape | `[2]` |" in described
        assert "| `[0].raw` |" in described

    def test_a_structured_variable_with_a_condition_says_so(self, tmp_path: Path) -> None:
        from ddd.build_info import BuildInfo
        from ddd.lsp.hover import describe, resolve

        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "t.ddd.json", "a.ddd.json"),
                "t.ddd.json": {
                    "types": [
                        {
                            "type": "struct",
                            "name": "S_t",
                            "members": [
                                {
                                    "name": "v",
                                    "member": "value",
                                    "datatype": "uint8",
                                    "conversion": {},
                                }
                            ],
                        }
                    ]
                },
                "a.ddd.json": component(
                    "A",
                    declare("local", "X", typename="S_t", condition="defined(FEAT)"),
                ),
            },
        )
        info = BuildInfo(project=(tmp_path / "p.ddd.json").as_posix())
        described = describe(resolve(navigation.workspaces([info], tmp_path / "a.ddd.json")), "X")
        assert described is not None
        assert "| condition | `defined(FEAT)` |" in described
        assert "Local to **A**." in described

    def test_a_curve_reports_what_its_axis_decided(self, tmp_path: Path) -> None:
        """The shape and the span come from the axis; the file says neither."""
        from ddd.lsp.hover import describe

        dictionary = self.resolved(
            tmp_path,
            declare("output", "Axis", kind="axis", size=3, datatype="uint16", init=[0, 50, 100]),
            declare("output", "Curve", kind="curve", datatype="uint8", axis="Axis", unit="ms"),
        )
        described = describe(dictionary, "Curve")
        assert "`[3]`" in described
        assert "| axis | `Axis` — 0 .. 100 |" in described

    def test_limits_say_when_nothing_has_been_narrowed(self, tmp_path: Path) -> None:
        """Whether they were written or worked out is gone by now; that they are the whole
        range is the part worth knowing, because it is what a calibration tool will offer."""
        from ddd.lsp.hover import describe

        dictionary = self.resolved(
            tmp_path,
            declare("output", "Whole", datatype="uint8"),
            declare("output", "Narrow", datatype="uint8", limits={"min": 0, "max": 100}),
        )
        assert "the full range of the datatype" in describe(dictionary, "Whole")
        assert "the full range of the datatype" not in describe(dictionary, "Narrow")

    @pytest.mark.parametrize(
        ("scope", "expected"),
        [("output", "read by *nobody*"), ("local", "Local to **A**")],
    )
    def test_who_writes_it_and_who_reads_it(
        self, tmp_path: Path, scope: str, expected: str
    ) -> None:
        from ddd.lsp.hover import describe

        dictionary = self.resolved(tmp_path, declare(scope, "Value"))
        assert expected in describe(dictionary, "Value")

    def test_a_reader_is_named(self, tmp_path: Path) -> None:
        from ddd.build_info import BuildInfo
        from ddd.lsp.hover import describe, resolve

        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Value")),
                "b.ddd.json": component("B", declare("input", "Value")),
            },
        )
        info = BuildInfo(project=(tmp_path / "p.ddd.json").as_posix())
        dictionary = resolve(navigation.workspaces([info], tmp_path / "a.ddd.json"))
        assert "Written by **A**, read by **B**." in describe(dictionary, "Value")

    def test_an_object_nobody_produces_says_so(self, tmp_path: Path) -> None:
        from ddd.lsp.hover import describe

        dictionary = self.resolved(tmp_path, declare("input", "Orphan"))
        assert "*No component produces this.*" in describe(dictionary, "Orphan")

    def test_the_optional_facts_appear_only_when_there_are_any(self, tmp_path: Path) -> None:
        from ddd.lsp.hover import describe

        dictionary = self.resolved(
            tmp_path,
            declare("output", "Bare", datatype="uint8"),
            declare(
                "output",
                "Full",
                datatype="uint8",
                condition="defined(FEAT_X)",
                volatile=True,
                unit="Hz",
                dimensions=[2],
            ),
        )
        bare, full = describe(dictionary, "Bare"), describe(dictionary, "Full")
        assert "| unit | *none* |" in bare
        assert "shape" not in bare and "condition" not in bare
        assert "| unit | `Hz` |" in full
        assert "| condition | `defined(FEAT_X)` |" in full
        # Volatility is not an optional fact: every definition states it, so the row is always
        # drawn. Leaving it out when it is false would make "no" and "nobody said" look alike,
        # which is the confusion the required key exists to end.
        assert "| volatile | no |" in bare
        assert "| volatile | yes |" in full

    def test_a_verbal_conversion_lists_what_the_numbers_mean(self, tmp_path: Path) -> None:
        from ddd.lsp.hover import describe

        dictionary = self.resolved(
            tmp_path,
            declare(
                "output",
                "State",
                datatype="uint8",
                conversion={"kind": "enum", "name": "StateA", "enumerators": {"OFF": 0, "ON": 1}},
            ),
        )
        described = describe(dictionary, "State")
        assert "**StateA**: `0` OFF · `1` ON" in described

    def test_a_long_enumeration_is_cut_short(self, tmp_path: Path) -> None:
        """A hover is a reminder, not a header file."""
        from ddd.lsp.hover import MAX_ENUMERATORS, describe

        count = MAX_ENUMERATORS + 3
        dictionary = self.resolved(
            tmp_path,
            declare(
                "output",
                "Many",
                datatype="uint8",
                conversion={
                    "kind": "enum",
                    "name": "ManyA",
                    "enumerators": {f"V{index}": index for index in range(count)},
                },
            ),
        )
        assert "… 3 more" in describe(dictionary, "Many")

    def test_init_values_are_drawn_in_physical_units(self, tmp_path: Path) -> None:
        from ddd.lsp.hover import describe

        dictionary = self.resolved(
            tmp_path,
            declare(
                "output",
                "Block",
                kind="value_block",
                datatype="uint8",
                dimensions=[4],
                unit="%",
                conversion={"factor": 0.5},
                init=[0, 40, 80, 120],
            ),
        )
        described = describe(dictionary, "Block")
        assert "▁▃▆█" in described
        assert "0 .. 60 %" in described  # raw 120 through factor 0.5

    def test_a_map_is_drawn_one_row_at_a_time(self, tmp_path: Path) -> None:
        """Sharing one scale, so a row can be compared with the one above it."""
        from ddd.lsp.hover import describe

        dictionary = self.resolved(
            tmp_path,
            declare("output", "X", kind="axis", size=2, datatype="uint8", init=[0, 1]),
            declare("output", "Y", kind="axis", size=2, datatype="uint8", init=[0, 1]),
            declare(
                "output",
                "Surface",
                kind="map",
                datatype="uint8",
                x_axis="X",
                y_axis="Y",
                init=[[0, 1], [7, 8]],
            ),
        )
        # One row per row of the map, and the second sits higher than the first because both
        # are drawn against the same scale.
        assert "▁▂\n██" in describe(dictionary, "Surface")

    def test_a_flat_init_is_stated_rather_than_drawn(self, tmp_path: Path) -> None:
        """A row of identical bars looks like a reading of the data rather than its absence."""
        from ddd.lsp.hover import describe

        dictionary = self.resolved(
            tmp_path,
            declare("output", "Flat", kind="value_block", datatype="uint8", dimensions=[4], init=7),
        )
        described = describe(dictionary, "Flat")
        assert "```text" not in described
        # Identity: physical equals raw, so there is no reading to add.
        assert described.endswith("init `7`")

    def test_a_flat_list_init_is_stated_in_physical_units(self, tmp_path: Path) -> None:
        """A list stating one value four times is stated once, as always; only a *scalar*
        init carries the raw value with its reading, because only there is the raw value
        the whole of what the file says."""
        from ddd.lsp.hover import describe

        dictionary = self.resolved(
            tmp_path,
            declare(
                "output",
                "FlatList",
                kind="value_block",
                datatype="uint8",
                dimensions=[4],
                unit="%",
                conversion={"factor": 0.5},
                init=[80, 80, 80, 80],
            ),
        )
        assert describe(dictionary, "FlatList").endswith("init `40` %")

    def test_a_scalar_init_states_its_physical_reading(self, tmp_path: Path) -> None:
        """Raw first, because raw is what ``init`` is and what the generated c carries; the
        reading beside it is the forward conversion, which every raw value has."""
        from ddd.lsp.hover import describe

        dictionary = self.resolved(
            tmp_path,
            declare(
                "output",
                "Temperature",
                datatype="uint16",
                unit="degC",
                conversion={"factor": 0.05},
                init=800,
            ),
        )
        assert "init `800` = 40 degC" in describe(dictionary, "Temperature")

    def test_a_scalar_init_without_a_unit_reads_bare(self, tmp_path: Path) -> None:
        from ddd.lsp.hover import describe

        dictionary = self.resolved(
            tmp_path,
            declare("output", "Ratio", datatype="uint16", conversion={"factor": 0.05}, init=800),
        )
        assert describe(dictionary, "Ratio").endswith("init `800` = 40")

    def test_a_reading_shows_no_float_artifacts(self, tmp_path: Path) -> None:
        """0.1 has no exact binary float, so 3 raw counts compute as 0.30000000000000004;
        the tail is the arithmetic's, not the reading's, and is rounded away."""
        from ddd.lsp.hover import describe

        dictionary = self.resolved(
            tmp_path,
            declare(
                "output", "Offset", datatype="uint8", unit="V", conversion={"factor": 0.1}, init=3
            ),
        )
        assert "init `3` = 0.3 V" in describe(dictionary, "Offset")

    def test_an_enum_init_reads_as_its_enumerator(self, tmp_path: Path) -> None:
        from ddd.lsp.hover import describe

        dictionary = self.resolved(
            tmp_path,
            declare(
                "output",
                "State",
                conversion={
                    "kind": "enum",
                    "name": "StateH",
                    "enumerators": {"STATE_OK": 0, "STATE_FAULT": 15},
                },
                init=15,
            ),
        )
        assert "init `15` = STATE_FAULT" in describe(dictionary, "State")

    def test_an_enum_init_outside_the_table_stays_raw(self, tmp_path: Path) -> None:
        """A value the enum does not name has no reading; inventing one would be a claim."""
        from ddd.lsp.hover import describe

        dictionary = self.resolved(
            tmp_path,
            declare(
                "output",
                "State",
                conversion={
                    "kind": "enum",
                    "name": "StateH",
                    "enumerators": {"STATE_OK": 0, "STATE_FAULT": 15},
                },
                init=14,
            ),
        )
        assert describe(dictionary, "State").endswith("init `14`")

    def test_an_object_with_no_init_is_not_drawn(self, tmp_path: Path) -> None:
        from ddd.lsp.hover import describe

        dictionary = self.resolved(tmp_path, declare("output", "Empty", datatype="uint8"))
        assert "```text" not in describe(dictionary, "Empty")

    def test_a_reference_that_is_not_an_axis_carries_no_span(self, tmp_path: Path) -> None:
        """The input of an axis names a measurement, whose init is one value."""
        from ddd.lsp.hover import describe

        dictionary = self.resolved(
            tmp_path,
            declare("output", "Speed", datatype="uint8", init=3),
            declare("output", "Axis", kind="axis", size=2, datatype="uint8", input="Speed"),
        )
        assert "| input | `Speed` |" in describe(dictionary, "Axis")

    def test_the_description_the_author_wrote_is_carried_over(self, tmp_path: Path) -> None:
        from ddd.lsp.hover import describe

        dictionary = self.resolved(
            tmp_path, declare("output", "Value", description="Engine speed, filtered")
        )
        assert "Engine speed, filtered" in describe(dictionary, "Value")

    @pytest.mark.parametrize(
        "pointer",
        [
            "component.interface[1].definition.name",
            "component.interface[1].definition.datatype",
            "component.interface[1].scope",
            "component.interface[1]",
        ],
    )
    def test_a_hover_anywhere_in_a_declaration_is_about_that_object(
        self, tmp_path: Path, pointer: str
    ) -> None:
        """Hunting for the one key that answers is not a game worth playing."""
        from ddd.lsp.navigation import subject_at

        write_tree(
            tmp_path,
            {
                "a.ddd.json": component(
                    "A",
                    declare("output", "Axis", kind="axis", size=2, datatype="uint8"),
                    declare("output", "Curve", kind="curve", datatype="uint8", axis="Axis"),
                )
            },
        )
        document = read(tmp_path / "a.ddd.json", {})
        assert subject_at(document, pointer) == "Curve"

    def test_a_reference_still_wins_over_the_declaration_holding_it(self, tmp_path: Path) -> None:
        """On the axis of a curve, the thing under the pointer is the axis."""
        from ddd.lsp.navigation import subject_at

        write_tree(
            tmp_path,
            {
                "a.ddd.json": component(
                    "A",
                    declare("output", "Axis", kind="axis", size=2, datatype="uint8"),
                    declare("output", "Curve", kind="curve", datatype="uint8", axis="Axis"),
                )
            },
        )
        document = read(tmp_path / "a.ddd.json", {})
        assert subject_at(document, "component.interface[1].definition.axis") == "Axis"

    @pytest.mark.parametrize("pointer", ["component.name", "component", ""])
    def test_outside_a_declaration_there_is_no_subject(self, tmp_path: Path, pointer: str) -> None:
        from ddd.lsp.navigation import subject_at

        write_tree(tmp_path, {"a.ddd.json": component("A", declare("output", "X"))})
        assert subject_at(read(tmp_path / "a.ddd.json", {}), pointer) is None

    def test_a_declaration_still_being_written_has_no_subject(self) -> None:
        """Caught mid edit: the pointer is built rather than scanned, so it may lead nowhere."""
        from ddd.lsp.navigation import subject_at

        document = Document('{"component": {"interface": [{"scope": "input"}]}}')
        assert subject_at(document, "component.interface[0].scope") is None

    def test_a_name_no_component_declares_has_nothing_to_show(self, tmp_path: Path) -> None:
        from ddd.lsp.hover import describe

        assert describe(self.resolved(tmp_path, declare("output", "Value")), "Absent") is None

    def test_a_document_in_no_project_resolves_to_nothing(self, tmp_path: Path) -> None:
        from ddd.lsp.hover import resolve

        assert resolve(navigation.workspaces([], tmp_path / "absent.ddd.json")) is None

    def test_a_string_init_draws_no_rows(self, tmp_path: Path) -> None:
        """Nothing numeric to draw: the string flattens to no values, so the rows are none."""
        from ddd.lsp.hover import rows

        dictionary = self.resolved(
            tmp_path,
            declare(
                "output",
                "Label",
                datatype="uint8",
                kind="value_block",
                conversion={"kind": "string"},
                dimensions=[16],
                init="V1.2.3",
            ),
        )
        assert rows(dictionary.by_name["Label"]) == []

    def test_a_string_init_is_stated_as_text(self, tmp_path: Path) -> None:
        """Quoted as the file spells it; no reading to add, nothing to draw."""
        from ddd.lsp.hover import describe

        dictionary = self.resolved(
            tmp_path,
            declare(
                "output",
                "Label",
                datatype="uint8",
                kind="value_block",
                conversion={"kind": "string"},
                dimensions=[16],
                init="V1.2.3",
            ),
        )
        described = describe(dictionary, "Label")
        assert "| conversion | `string` |" in described
        assert described.endswith('init `"V1.2.3"`')
        assert "```" not in described

    def test_the_scale_is_the_one_it_is_given(self) -> None:
        """Passed in rather than taken from the row, so that rows can be compared."""
        from ddd.lsp.hover import BARS, sparkline

        assert sparkline([0.0, 5.0, 10.0], 0.0, 10.0) == f"{BARS[0]}{BARS[4]}{BARS[-1]}"
        # The same row against a wider scale sits lower, which is the whole point.
        assert sparkline([0.0, 5.0, 10.0], 0.0, 20.0) == f"{BARS[0]}{BARS[2]}{BARS[4]}"


def apply_edits(path: Path, edits: list[dict[str, Any]]) -> str:
    """What a client would write, so a test can check the result rather than the offsets.

    Ranges may span lines - removing a member takes the newline before or after it with them -
    so positions are turned into offsets and the edits applied last first. Columns are read as
    plain character counts, which is the same as the utf-16 the protocol asks for as long as
    the fixtures stay ascii.
    """
    text = path.read_text(encoding="utf-8")
    starts = [0]
    for line in text.splitlines(keepends=True):
        starts.append(starts[-1] + len(line))

    def offset(position: dict[str, int]) -> int:
        return starts[position["line"]] + position["character"]

    for edit in sorted(edits, key=lambda e: offset(e["range"]["start"]), reverse=True):
        text = (
            text[: offset(edit["range"]["start"])]
            + edit["newText"]
            + text[offset(edit["range"]["end"]) :]
        )
    return text


UNIT_PLACES = [
    ("a.ddd.json", "component.interface[0].definition.unit"),
    ("b.ddd.json", "component.interface[0].definition.unit"),
    ("a.ddd.json", "component.types[0].unit"),
    ("a.ddd.json", "component.types[1].members[0].unit"),
    ("types.ddd.json", "types[0].unit"),
    ("types.ddd.json", "types[1].members[0].unit"),
    ("units.ddd.json", "units[0].unit"),
]
"""Every kind of place :func:`unit_places` spells ``rpm``: a declaration on either side, a scalar
type and a structure member in a component's own list and in a types file, and its vocabulary
entry, an object."""


def unit_places(base: Path) -> Path:
    """A project stating ``rpm`` in every kind of place a unit is stated, and listing it in its
    vocabulary as an object - and ``Nm`` as a spelling on its own, stated by one member."""
    write_tree(
        base,
        {
            "p.ddd.json": project(
                "P", "units.ddd.json", "types.ddd.json", "a.ddd.json", "b.ddd.json"
            ),
            "units.ddd.json": {"units": [{"unit": "rpm", "description": "speed"}, "Nm"]},
            "types.ddd.json": types(
                scalar_type("Speed_t", unit="rpm"),
                struct_type(
                    "Pair_t",
                    value_member("speed", unit="rpm"),
                    value_member("torque", unit="Nm"),
                ),
            ),
            "a.ddd.json": component(
                "A",
                declare("output", "Speed", unit="rpm"),
                types=[
                    scalar_type("Idle_t", unit="rpm"),
                    struct_type("Spin_t", value_member("idle", unit="rpm")),
                ],
            ),
            "b.ddd.json": component("B", declare("input", "Speed", unit="rpm")),
        },
    )
    return base / "p.ddd.json"


def rewritten_by(changes: dict[str, list[dict[str, Any]]]) -> dict[str, str]:
    """Every file an edit changes, by name, as a client leaves it."""
    return {
        uri_to_path(uri).name: apply_edits(uri_to_path(uri), edits)
        for uri, edits in changes.items()
    }


def reconciled(offered: list[dict[str, Any]]) -> list[str]:
    """What each reconcile fix offered changes, after pinning that its title ends saying, in the
    page's words, that the code of the readers is not touched."""
    titles = [action["title"] for action in offered]
    assert all(title.endswith(CODE_NOT_TOUCHED) for title in titles), titles
    return [title.removesuffix(CODE_NOT_TOUCHED) for title in titles]


class TestRename:
    """Rewriting a name everywhere the project writes it."""

    def workspace(self, tmp_path: Path) -> Path:
        """A producer, a consumer, and an axis whose input quantity names the same object."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    declare("output", "Speed", "uint16"),
                    declare("output", "Ax", "uint16", kind="axis", size=3, input="Speed"),
                    declare(
                        "output",
                        "Mode",
                        "uint8",
                        conversion={
                            "kind": "enum",
                            "name": "Mode_t",
                            "enumerators": [{"name": "MODE_OFF", "value": 0}],
                        },
                    ),
                ),
                "b.ddd.json": component("B", declare("input", "Speed", "uint16")),
            },
        )
        return tmp_path / "p.ddd.json"

    def index_of(self, root: Path) -> Any:
        from ddd.lsp.navigation import index

        return index(load_workspace(root, DiagnosticBag()))

    def test_every_mention_is_rewritten_including_the_references(self, tmp_path: Path) -> None:
        """A rename that misses the axis leaves the project naming something gone."""
        from ddd.lsp.navigation import rename_edits

        root = self.workspace(tmp_path)
        path = tmp_path / "b.ddd.json"
        cache: dict[Path, Document] = {}
        edits = rename_edits(
            self.index_of(root),
            read(path, cache),
            "component.interface[0].definition.name",
            "EngineSpeed",
            cache,
        )
        rewritten = {
            uri_to_path(uri): apply_edits(uri_to_path(uri), found)
            for uri, found in edits.changes.items()
        }
        assert {path.name for path in rewritten} == {"a.ddd.json", "b.ddd.json"}
        produced = json.loads(rewritten[tmp_path / "a.ddd.json"])["component"]["interface"]
        assert produced[0]["definition"]["name"] == "EngineSpeed"
        assert produced[1]["definition"]["input"] == "EngineSpeed"
        assert "Speed" not in rewritten[tmp_path / "b.ddd.json"].replace("EngineSpeed", "")

    @pytest.mark.parametrize(
        "pointer",
        [
            "component.interface[2].definition.conversion.name",
            "component.interface[2].definition.conversion.enumerators[0].name",
        ],
    )
    def test_an_enum_name_and_an_enumerator_open_no_rename_box(
        self, tmp_path: Path, pointer: str
    ) -> None:
        """The subject was the last segment of the pointer, so both of these passed as the
        object's name: the box opened, and the rename answered an empty edit - or renamed a
        variable of that name somewhere else instead."""
        from ddd.lsp.navigation import renameable_at

        self.workspace(tmp_path)
        assert renameable_at(read(tmp_path / "a.ddd.json", {}), pointer) is None

    @pytest.mark.parametrize("key", ["name", "size", "typename"])
    def test_a_plugins_own_key_is_not_a_rename_subject(self, tmp_path: Path, key: str) -> None:
        """An extensions block may spell any key, and three of them are names DDD renames."""
        from ddd.lsp.navigation import renameable_at

        write_tree(
            tmp_path,
            {
                "a.ddd.json": component(
                    "A", declare("local", "X", extensions={"tag": {key: "Whatever"}})
                )
            },
        )
        pointer = f"component.interface[0].definition.extensions.tag.{key}"
        assert renameable_at(read(tmp_path / "a.ddd.json", {}), pointer) is None

    def test_a_rename_onto_an_enum_a_types_file_declares_is_refused(self) -> None:
        """``occupied`` was filled from the conversions of declarations only, so an enum on a
        structure member registered nothing and the rename went through - to be reported as a
        name collision by the next check, over every file it had just rewritten."""
        from ddd.lsp.navigation import index, rename_problem

        root = EXAMPLES / "structures" / "project.ddd.json"
        built = index(load_workspace(root, DiagnosticBag()))
        assert "enumerator of enum 'SensorMode_t'" in str(rename_problem(built, "MODE_IDLE"))
        assert "name of enum 'SensorMode_t'" in str(rename_problem(built, "SensorMode_t"))

    def test_only_the_characters_between_the_quotes_are_replaced(self, tmp_path: Path) -> None:
        """Whatever else a project puts on the line is left exactly as it was."""
        from ddd.lsp.navigation import rename_edits

        root = self.workspace(tmp_path)
        path = tmp_path / "b.ddd.json"
        cache: dict[Path, Document] = {}
        edits = rename_edits(
            self.index_of(root),
            read(path, cache),
            "component.interface[0].definition.name",
            "X",
            cache,
        )
        rewritten = apply_edits(path, edits.changes[path.as_uri()])
        assert '"name": "X"' in rewritten
        assert json.loads(rewritten)  # still json, quotes intact

    def vocabulary(self, tmp_path: Path) -> Path:
        """A type nested by a member and two declarations, and a constant sizing two arrays."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project(
                    "P", "types.ddd.json", "constants.ddd.json", "a.ddd.json", "b.ddd.json"
                ),
                "types.ddd.json": {
                    "types": [
                        {
                            "type": "scalar",
                            "name": "Temp_t",
                            "datatype": "uint16",
                            "unit": "degC",
                            "conversion": {"factor": 0.1},
                        },
                        {
                            "type": "struct",
                            "name": "Sensor_t",
                            "members": [
                                {"name": "value", "member": "value", "typename": "Temp_t"},
                                {
                                    "name": "history",
                                    "member": "value",
                                    "datatype": "uint8",
                                    "conversion": {},
                                    "dimensions": ["N"],
                                },
                            ],
                        },
                    ]
                },
                "constants.ddd.json": {"constants": [{"name": "N", "value": 4}]},
                "a.ddd.json": component(
                    "A",
                    declare("output", "Inlet", typename="Sensor_t"),
                    declare("output", "Buf", "uint8", dimensions=["N"]),
                ),
                "b.ddd.json": component("B", declare("input", "Inlet", typename="Sensor_t")),
            },
        )
        return tmp_path / "p.ddd.json"

    def renamed(self, tmp_path: Path, source: str, pointer: str, name: str) -> dict[str, str]:
        """The files a rename from this position rewrites, by name, with the edits applied."""
        from ddd.lsp.navigation import rename_edits

        root = self.vocabulary(tmp_path)
        path = tmp_path / source
        cache: dict[Path, Document] = {}
        edits = rename_edits(self.index_of(root), read(path, cache), pointer, name, cache)
        return {
            uri_to_path(uri).name: apply_edits(uri_to_path(uri), found)
            for uri, found in edits.changes.items()
        }

    @pytest.mark.parametrize(
        ("source", "pointer"),
        [
            ("types.ddd.json", "types[1].name"),
            ("b.ddd.json", "component.interface[0].definition.typename"),
        ],
    )
    def test_a_type_is_renamed_where_it_is_declared_and_wherever_it_is_named(
        self, tmp_path: Path, source: str, pointer: str
    ) -> None:
        """From its declaration or from any typename spelling it: the same three files."""
        rewritten = self.renamed(tmp_path, source, pointer, "Probe_t")
        assert set(rewritten) == {"types.ddd.json", "a.ddd.json", "b.ddd.json"}
        assert json.loads(rewritten["types.ddd.json"])["types"][1]["name"] == "Probe_t"
        for name in ("a.ddd.json", "b.ddd.json"):
            interface = json.loads(rewritten[name])["component"]["interface"]
            assert interface[0]["definition"]["typename"] == "Probe_t"
            assert "Sensor_t" not in rewritten[name]

    def test_a_type_a_member_nests_is_renamed_in_the_member_too(self, tmp_path: Path) -> None:
        rewritten = self.renamed(tmp_path, "types.ddd.json", "types[1].members[0].typename", "T_t")
        types = json.loads(rewritten["types.ddd.json"])["types"]
        assert types[0]["name"] == "T_t"
        assert types[1]["members"][0]["typename"] == "T_t"
        assert set(rewritten) == {"types.ddd.json"}

    @pytest.mark.parametrize(
        ("source", "pointer"),
        [
            ("constants.ddd.json", "constants[0].name"),
            ("a.ddd.json", "component.interface[1].definition.dimensions[0]"),
            ("types.ddd.json", "types[1].members[1].dimensions[0]"),
        ],
    )
    def test_a_constant_is_renamed_where_it_is_declared_and_in_every_dimension(
        self, tmp_path: Path, source: str, pointer: str
    ) -> None:
        rewritten = self.renamed(tmp_path, source, pointer, "SLOTS")
        assert set(rewritten) == {"constants.ddd.json", "a.ddd.json", "types.ddd.json"}
        assert json.loads(rewritten["constants.ddd.json"])["constants"][0]["name"] == "SLOTS"
        buffer = json.loads(rewritten["a.ddd.json"])["component"]["interface"][1]["definition"]
        assert buffer["dimensions"] == ["SLOTS"]
        member = json.loads(rewritten["types.ddd.json"])["types"][1]["members"][1]
        assert member["dimensions"] == ["SLOTS"]

    def test_a_type_nothing_declares_renames_its_uses_alone(self, tmp_path: Path) -> None:
        """The loader has reported unknown-type already; the rename keeps the files agreeing."""
        from ddd.lsp.navigation import rename_edits

        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Inlet", typename="Ghost_t")),
            },
        )
        path = tmp_path / "a.ddd.json"
        cache: dict[Path, Document] = {}
        edits = rename_edits(
            self.index_of(tmp_path / "p.ddd.json"),
            read(path, cache),
            "component.interface[0].definition.typename",
            "Seen_t",
            cache,
        )
        assert {uri_to_path(uri).name for uri in edits.changes} == {"a.ddd.json"}

    def test_a_constant_nothing_declares_renames_its_uses_alone(self, tmp_path: Path) -> None:
        """The sibling of the type case above, and until the consolidation nothing pinned it.
        `rename_sites` answers both kinds from one arm, so an ablation of that arm killed only the
        type test - the constant half was exercised and unnamed. `unknown-constant` is already
        reported; the rename still has to keep every file spelling it agreeing."""
        from ddd.lsp.navigation import rename_edits

        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Gain", dimensions=["GHOST"])),
            },
        )
        path = tmp_path / "a.ddd.json"
        cache: dict[Path, Document] = {}
        edits = rename_edits(
            self.index_of(tmp_path / "p.ddd.json"),
            read(path, cache),
            "component.interface[0].definition.dimensions[0]",
            "SEEN",
            cache,
        )
        assert {uri_to_path(uri).name for uri in edits.changes} == {"a.ddd.json"}

    def test_a_position_holding_a_number_starts_no_rename(self, tmp_path: Path) -> None:
        """A constant's value is a number; a rename box over it would rename nothing."""
        from ddd.lsp.navigation import RenameEdits, rename_edits, renameable_at

        root = self.vocabulary(tmp_path)
        path = tmp_path / "constants.ddd.json"
        document = read(path, {})
        assert renameable_at(document, "constants[0].value") is None
        found = rename_edits(self.index_of(root), document, "constants[0].value", "X", {})
        assert found == RenameEdits(changes={}, drifted=())

    def test_a_type_may_not_be_renamed_to_a_base_datatype_spelling(self, tmp_path: Path) -> None:
        """The loader refuses UINT16 as a type name, so the rename has to, before writing."""
        from ddd.lsp.navigation import rename_problem

        built = self.index_of(self.vocabulary(tmp_path))
        assert rename_problem(built, "UINT16", "type") is not None
        assert "base datatype" in str(rename_problem(built, "UINT16", "type"))
        assert rename_problem(built, "Probe_t", "type") is None
        # A variable may still not take a type's name, and a type may not take a variable's.
        assert "already" in str(rename_problem(built, "Inlet", "type"))

    def test_a_rename_from_a_position_naming_nothing_edits_nothing(self, tmp_path: Path) -> None:
        from ddd.lsp.navigation import RenameEdits, rename_edits

        root = self.workspace(tmp_path)
        path = tmp_path / "b.ddd.json"
        found = rename_edits(self.index_of(root), read(path, {}), "component.name", "X", {})
        assert found == RenameEdits(changes={}, drifted=())

    def test_a_mention_that_is_not_a_string_is_skipped(self, tmp_path: Path) -> None:
        """Belt and braces: the index and the text are read at the same moment, but a file
        rewritten between the two would otherwise put an edit over a number - and is reported
        as drifted for the same reason a moved declaration is: the pointer no longer names
        what the rename was asked to touch."""
        from ddd.lsp.navigation import Index, RenameEdits, Site, rename_edits

        write_tree(tmp_path, {"a.ddd.json": component("A", declare("output", "Speed"))})
        path = tmp_path / "a.ddd.json"
        built = Index(
            mentions={"Speed": [Site(path, "component.interface[0].definition.dimensions")]}
        )
        cache: dict[Path, Document] = {}
        found = rename_edits(
            built, read(path, cache), "component.interface[0].definition.name", "X", cache
        )
        assert found == RenameEdits(changes={}, drifted=(path,))

    @pytest.mark.parametrize(
        ("name", "because"),
        [
            ("2Bad", "not a usable c identifier"),
            ("has space", "not a usable c identifier"),
            ("int", "reserved"),
            ("uint16_t", "reserved"),
            ("Ax", "already declared"),
            ("Mode_t", "the name of enum 'Mode_t'"),
            ("MODE_OFF", "an enumerator of enum 'Mode_t'"),
        ],
    )
    def test_a_name_that_would_break_the_project_is_refused(
        self, tmp_path: Path, name: str, because: str
    ) -> None:
        """Checked before a single file is touched: a rename writes into several at once, and
        the c compiler only notices an unusable name a build later."""
        from ddd.lsp.navigation import rename_problem

        problem = rename_problem(self.index_of(self.workspace(tmp_path)), name)
        assert problem is not None
        assert because in problem

    def test_a_usable_name_is_not_refused(self, tmp_path: Path) -> None:
        from ddd.lsp.navigation import rename_problem

        assert rename_problem(self.index_of(self.workspace(tmp_path)), "EngineSpeed") is None

    def test_a_name_longer_than_the_contract_allows_is_refused(self, tmp_path: Path) -> None:
        from ddd.lsp.navigation import rename_problem
        from ddd.models import IDENTIFIER_MAX_LENGTH

        too_long = "A" * (IDENTIFIER_MAX_LENGTH + 1)
        assert rename_problem(self.index_of(self.workspace(tmp_path)), too_long) is not None

    @pytest.mark.parametrize(("source", "pointer"), UNIT_PLACES)
    def test_a_unit_is_a_rename_subject_wherever_it_is_spelled(
        self, tmp_path: Path, source: str, pointer: str
    ) -> None:
        unit_places(tmp_path)
        assert navigation.renameable_at(read(tmp_path / source, {}), pointer) == ("unit", "rpm")

    def test_a_vocabulary_entry_that_is_the_spelling_alone_is_a_rename_subject(
        self, tmp_path: Path
    ) -> None:
        unit_places(tmp_path)
        document = read(tmp_path / "units.ddd.json", {})
        assert navigation.renameable_at(document, "units[1]") == ("unit", "Nm")

    @pytest.mark.parametrize("pointer", ["units[0]", "units[0].description"])
    def test_an_entry_written_as_an_object_is_renamed_from_its_unit_alone(
        self, tmp_path: Path, pointer: str
    ) -> None:
        """The editor opens its box over the range this names, and neither the object nor its
        description is a spelling to type over."""
        unit_places(tmp_path)
        assert navigation.renameable_at(read(tmp_path / "units.ddd.json", {}), pointer) is None

    def test_neither_the_empty_unit_nor_a_plugins_own_unit_is_a_rename_subject(
        self, tmp_path: Path
    ) -> None:
        """A dimensionless value states no unit, so there is no spelling to rename; and an
        extensions block may spell any key, ``unit`` among them."""
        write_tree(
            tmp_path,
            {
                "a.ddd.json": component(
                    "A", declare("local", "Ratio", unit="", extensions={"tag": {"unit": "rpm"}})
                )
            },
        )
        document = read(tmp_path / "a.ddd.json", {})
        definition = "component.interface[0].definition"
        assert navigation.renameable_at(document, f"{definition}.unit") is None
        assert navigation.renameable_at(document, f"{definition}.extensions.tag.unit") is None

    def test_a_file_that_loaded_with_an_error_is_unreadable_but_not_unloaded(
        self, tmp_path: Path
    ) -> None:
        """A units file listing a unit twice loads, with a duplicate-unit error: it stays in the
        index, where a plan can reach both entries. A component its schema refuses does not."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "units.ddd.json", "a.ddd.json"),
                "units.ddd.json": {"units": ["rpm", "RPM", "RPM"]},
                "a.ddd.json": component("A", declare("output", "Speed", "uint99", unit="rpm")),
            },
        )
        (loaded,) = navigation.workspaces([], tmp_path / "units.ddd.json", tmp_path)
        assert [path.name for path in loaded.unreadable] == ["a.ddd.json", "units.ddd.json"]
        assert [path.name for path in loaded.unloaded] == ["a.ddd.json"]


PLACED = {
    "s.ddd.json": {"sections": [{"section": ".calib", "access": "read-write", "alignment": 4}]},
    "a.ddd.json": component("A", declare("output", "X", section=".calib")),
}
"""A sections file declaring ``.calib``, and one definition placing data in it."""

TIMED = {
    "r.ddd.json": {"rasters": [{"raster": "10ms", "event": 1, "cycle": "10ms"}]},
    "a.ddd.json": component("A", declare("output", "X", raster="10ms"), raster="10ms"),
}
"""A rasters file declaring ``10ms``, a component naming it as its own default, and a
definition naming it too."""


TWO_RASTERS = {
    "r.ddd.json": {
        "rasters": [
            {"raster": "10ms", "event": 1, "cycle": "10ms"},
            {"raster": "20ms", "event": 2, "cycle": "20ms"},
        ]
    },
    "a.ddd.json": component("A", declare("output", "X", raster="10ms"), raster="10ms"),
}
"""A rasters file declaring ``10ms`` and ``20ms``, and a component naming ``10ms`` as its own
default."""


CALIB_TWICE = {
    "s.ddd.json": {"sections": [{"section": "calib", "access": "read-write", "alignment": 4}]},
    "a.ddd.json": component("A", declare("output", "calib")),
}
"""A section and a variable spelled the same way - the two namespaces that share nothing."""


class TestSectionsAndRasters:
    """The index learns the two vocabularies the loader always collected: a definition placing
    data in a section, or updated on a raster, now leads somewhere - and both are renameable
    like the four kinds the index already knew."""

    def test_a_section_is_indexed_with_every_definition_placing_data_in_it(
        self, tmp_path: Path
    ) -> None:
        built, _root = built_of(tmp_path, **PLACED)
        assert set(built.sections) == {".calib"}
        assert [site.pointer for site in built.section_uses[".calib"]] == [
            "component.interface[0].definition.section"
        ]

    def test_a_raster_named_by_a_component_is_a_use_like_one_named_by_a_definition(
        self, tmp_path: Path
    ) -> None:
        # `Component.raster` is the default for every variable the component produces - a use
        # that is not inside a definition at all, which no constant use ever was.
        built, _root = built_of(tmp_path, **TIMED)
        assert [site.pointer for site in built.raster_uses["10ms"]] == [
            "component.raster",
            "component.interface[0].definition.raster",
        ]

    def test_a_section_key_written_as_a_number_is_no_rename_subject(self, tmp_path: Path) -> None:
        # The model already validates `section` to `str | None`, so a non-string can never reach
        # `index()` - a number there fails the whole file's schema and the declaration is simply
        # absent, which `index()`'s own `is not None` guard need not defend against. Drift is real
        # one layer up, where a save can overwrite the key after the workspace this index answers
        # for was read: `renameable_at` reads the document as it stands, and a number there is no
        # spelling of anything to rename.
        from ddd.lsp.navigation import renameable_at

        _built, root = built_of(tmp_path, **PLACED)
        cache: dict[Path, Document] = {}
        edited(root / "a.ddd.json", lambda definition: definition.__setitem__("section", 4))
        assert (
            renameable_at(
                read(root / "a.ddd.json", cache), "component.interface[0].definition.section"
            )
            is None
        )

    def test_a_section_may_share_a_spelling_with_a_variable(self, tmp_path: Path) -> None:
        # A section's name is a linker string written into an attribute, not a c identifier, so
        # it does not join the namespace `occupied` guards and a project may spell both the
        # same way.
        built, _root = built_of(tmp_path, **CALIB_TWICE)
        assert "calib" not in built.occupied
        assert "calib" in built.sections

    def test_a_section_is_renameable_from_its_own_entry_and_from_a_use(
        self, tmp_path: Path
    ) -> None:
        # Both ends, because a rename that reached the entry and not the uses would leave every
        # definition placing data in a section nothing declares.
        from ddd.lsp.navigation import rename_sites, renameable_at

        built, root = built_of(tmp_path, **PLACED)
        cache: dict[Path, Document] = {}
        assert renameable_at(read(root / "s.ddd.json", cache), "sections[0].section") == (
            "section",
            ".calib",
        )
        assert renameable_at(
            read(root / "a.ddd.json", cache), "component.interface[0].definition.section"
        ) == ("section", ".calib")
        assert [site.pointer for site in rename_sites(built, "section", ".calib")] == [
            "sections[0].section",
            "component.interface[0].definition.section",
        ]

    def test_a_raster_is_renameable_from_its_own_entry_and_from_a_use(self, tmp_path: Path) -> None:
        # The same two ends as a section, plus the component's own default: a rename that left
        # it alone would leave a component still handing out the old name to what it produces.
        from ddd.lsp.navigation import rename_sites, renameable_at

        built, root = built_of(tmp_path, **TIMED)
        cache: dict[Path, Document] = {}
        assert renameable_at(read(root / "r.ddd.json", cache), "rasters[0].raster") == (
            "raster",
            "10ms",
        )
        assert renameable_at(read(root / "a.ddd.json", cache), "component.raster") == (
            "raster",
            "10ms",
        )
        assert renameable_at(
            read(root / "a.ddd.json", cache), "component.interface[0].definition.raster"
        ) == ("raster", "10ms")
        assert [site.pointer for site in rename_sites(built, "raster", "10ms")] == [
            "rasters[0].raster",
            "component.raster",
            "component.interface[0].definition.raster",
        ]

    def test_a_section_nothing_declares_renames_its_uses_alone(self, tmp_path: Path) -> None:
        """A definition may name a section no file declares - `unknown-section` reports it
        already - and the rename still has to keep every file that names it agreeing, the same
        precedent a typename nothing declares sets."""
        from ddd.lsp.navigation import rename_sites

        built, _root = built_of(
            tmp_path, **{"a.ddd.json": component("A", declare("output", "X", section=".nowhere"))}
        )
        assert ".nowhere" not in built.sections
        assert [site.pointer for site in rename_sites(built, "section", ".nowhere")] == [
            "component.interface[0].definition.section"
        ]

    def test_a_raster_nothing_declares_renames_its_uses_alone(self, tmp_path: Path) -> None:
        """The same as a section nothing declares, for a raster: `unknown-raster` reports it,
        and the rename still reaches the one place that names it."""
        from ddd.lsp.navigation import rename_sites

        built, _root = built_of(
            tmp_path, **{"a.ddd.json": component("A", declare("output", "X", raster="20ms"))}
        )
        assert "20ms" not in built.rasters
        assert [site.pointer for site in rename_sites(built, "raster", "20ms")] == [
            "component.interface[0].definition.raster"
        ]

    def test_a_raster_is_judged_as_the_a2l_short_name_it_is(self, tmp_path: Path) -> None:
        """`10ms` starts with a digit, which no c identifier may. The rule that refuses it is a
        constant's, and a raster does not share that namespace.

        Judged against an empty project rather than against ``TIMED``: ``TIMED`` already declares
        a raster called ``10ms``, which would be refused as a name the project declares already -
        the very next check ``_raster_problem`` makes - and prove nothing about the c identifier
        rule this test is about.
        """
        from ddd.lsp.navigation import rename_problem

        built, _ = built_of(tmp_path)
        assert rename_problem(built, "10ms", "raster") is None

    def test_a_raster_may_not_take_a_name_the_project_declares(self, tmp_path: Path) -> None:
        from ddd.lsp.navigation import rename_problem

        built, _ = built_of(tmp_path, **TWO_RASTERS)
        problem = rename_problem(built, "20ms", "raster")
        assert problem is not None
        # Not just `"20ms" in problem`: that also holds of the c-identifier refusal `"20ms"`
        # drew before this arm existed, so it would pass without the arm this test is for.
        assert "is already a raster this project declares" in problem

    def test_a_raster_name_longer_than_the_model_allows_is_refused(self, tmp_path: Path) -> None:
        """Unlike a section's, a raster's name has a length the model states -
        ``RASTER_NAME_LENGTH`` - and that is what refuses a name past it here, not
        ``IDENTIFIER_MAX_LENGTH``, which bounds a c identifier and is a different number for a
        different reason."""
        from ddd.lsp.navigation import rename_problem
        from ddd.models.common import RASTER_NAME_LENGTH

        built, _ = built_of(tmp_path)
        too_long = "1" * (RASTER_NAME_LENGTH + 1)
        problem = rename_problem(built, too_long, "raster")
        assert problem is not None
        # Not just `too_long in problem`: a digit-led name this long is also refused by the
        # c-identifier rule, for starting with a digit rather than for its length. The reason
        # has to be the raster one, or this passes without the arm it exists to pin.
        assert "is not a usable raster name" in problem

    def test_a_raster_name_with_an_excluded_character_is_refused(self, tmp_path: Path) -> None:
        """The length is not why: ``10 ms`` is five characters, well inside the limit. A
        short-circuiting ``or`` records one branch for the whole ``if``, not one per operand, so
        a case only the pattern half refuses is the one thing that proves it runs at all -
        nothing here was refused for its length alone before this test existed."""
        from ddd.lsp.navigation import rename_problem

        built, _ = built_of(tmp_path)
        problem = rename_problem(built, "10 ms", "raster")
        assert problem is not None
        assert "is not a usable raster name" in problem

    def test_a_raster_name_may_not_trail_a_newline(self, tmp_path: Path) -> None:
        """``re.fullmatch`` is the check, not ``re.match``: a plain ``match`` stops needing to
        satisfy ``$`` right before a trailing newline and would accept everything before it, so
        a rasters file whose entry ended its line early would still fail to load."""
        from ddd.lsp.navigation import rename_problem

        built, _ = built_of(tmp_path)
        problem = rename_problem(built, "10ms\n", "raster")
        assert problem is not None
        assert "is not a usable raster name" in problem

    def test_a_raster_name_may_hold_a_character_no_section_name_would(self, tmp_path: Path) -> None:
        """``RASTER_NAME_PATTERN`` admits any printable ASCII but a space; ``SECTION_NAME_PATTERN``
        is narrower - letters, digits, underscore, dot and dollar sign - and would refuse the
        hyphen here, which no rule of a raster's own excludes."""
        from ddd.lsp.navigation import rename_problem

        built, _ = built_of(tmp_path)
        assert rename_problem(built, "10-ms", "raster") is None


class TestARasterNameIsWrittenAsJson:
    """10:I9. A raster's name is any printable ASCII but a space, a quote and a backslash among
    it, and the rename wrote it raw between the quotes: a quote ended the string, so no file it
    rewrote parsed, and a backslash began an escape, so the name read back was another. It is
    written as json spells it now, and read back it is the name typed."""

    @pytest.mark.parametrize(
        "name", ['a"b', "a\\b", "a\\nb"], ids=["quote", "backslash", "backslash-n"]
    )
    def test_a_raster_renamed_onto_a_quote_or_a_backslash_reads_back_as_typed(
        self, tmp_path: Path, name: str
    ) -> None:
        from ddd.lsp.navigation import rename_edits, rename_problem

        built, root = built_of(tmp_path, **TIMED)
        assert rename_problem(built, name, "raster") is None
        cache: dict[Path, Document] = {}
        edits = rename_edits(
            built, read(root / "r.ddd.json", cache), "rasters[0].raster", name, cache
        )
        rewritten = rewritten_by(edits.changes)
        assert set(rewritten) == {"r.ddd.json", "a.ddd.json"}
        write_tree(root, rewritten)
        bag = DiagnosticBag()
        workspace = load_workspace(root / "p.ddd.json", bag)
        assert [found.check for found in bag if found.severity is Severity.ERROR] == []
        assert workspace is not None
        assert [raster.raster for raster in workspace.rasters] == [name]
        (loaded,) = workspace.components
        assert loaded.component.raster == name
        assert loaded.component.interface[0].definition.raster == name


UNDER_A_CONDITION: Final = {
    "c.ddd.json": {"constants": [{"name": "CELLS", "value": 4}, {"name": "ROWS", "value": 2}]},
    "w.ddd.json": component(
        "W", declare("output", "Big", dimensions=["CELLS"], condition="CELLS > 2")
    ),
}
"""10:I10's trigger: ``Big`` sized by ``CELLS`` and declared only where ``CELLS > 2``, beside a
second constant, ``ROWS``, that a condition may spell as well."""


def sized_under(condition: str) -> dict[str, Any]:
    """:data:`UNDER_A_CONDITION`'s component, ``Big`` declared under ``condition`` instead."""
    return component("W", declare("output", "Big", dimensions=["CELLS"], condition=condition))


class TestAConditionSpellingAConstant:
    """10:I10. The shipped templates define each constant as a macro in the types header, so a
    ``condition`` may spell one, and ``#if`` reads a name nothing defines as 0: a rename that left
    the condition spelling the old name compiled the object out, with every check clean. The index
    records the word apart from the shapes, and the rename rewrites that word, and no other."""

    def renamed(self, tmp_path: Path, w: Any) -> dict[str, str]:
        """The files renaming ``CELLS`` to ``SLOT_COUNT`` from its entry rewrites, by name, with the
        edits applied, ``w`` the component declaring ``Big`` - its json, or its text."""
        from ddd.lsp.navigation import rename_edits

        built, root = built_of(tmp_path, **{**UNDER_A_CONDITION, "w.ddd.json": w})
        cache: dict[Path, Document] = {}
        edits = rename_edits(
            built, read(root / "c.ddd.json", cache), "constants[0].name", "SLOT_COUNT", cache
        )
        assert edits.drifted == ()
        return rewritten_by(edits.changes)

    @staticmethod
    def big(text: str) -> dict[str, Any]:
        """``Big``'s declaration, out of the text of the component declaring it."""
        declared: dict[str, Any] = json.loads(text)["component"]["interface"][0]
        return declared

    def test_the_index_records_a_condition_s_word_apart_from_the_shapes(
        self, tmp_path: Path
    ) -> None:
        """A shape's string is the name and nothing else, and a condition is an expression: a
        reader of the shapes that met a condition among them would write the new name over all of
        it."""
        built, _root = built_of(tmp_path, **UNDER_A_CONDITION)
        assert {
            name: [(site.path.name, site.pointer) for site in sites]
            for name, sites in built.condition_uses.items()
        } == {"CELLS": [("w.ddd.json", "component.interface[0].condition")]}
        assert [site.pointer for site in built.constant_uses["CELLS"]] == [
            "component.interface[0].definition.dimensions[0]"
        ]

    @pytest.mark.parametrize(
        ("source", "pointer"),
        [
            ("c.ddd.json", "constants[0].name"),
            ("w.ddd.json", "component.interface[0].definition.dimensions[0]"),
        ],
        ids=["entry", "dimension"],
    )
    def test_a_rename_rewrites_a_condition_spelling_the_constant(
        self, tmp_path: Path, source: str, pointer: str
    ) -> None:
        from ddd.lsp.navigation import rename_edits

        built, root = built_of(tmp_path, **UNDER_A_CONDITION)
        cache: dict[Path, Document] = {}
        edits = rename_edits(built, read(root / source, cache), pointer, "SLOTS", cache)
        rewritten = rewritten_by(edits.changes)
        assert set(rewritten) == {"c.ddd.json", "w.ddd.json"}
        big = self.big(rewritten["w.ddd.json"])
        assert (big["condition"], big["definition"]["dimensions"]) == ("SLOTS > 2", ["SLOTS"])

    @pytest.mark.parametrize(
        ("condition", "after"),
        [
            ("defined(CELLS) && CELLS > ROWS", "defined(SLOT_COUNT) && SLOT_COUNT > ROWS"),
            ("CELLS>2", "SLOT_COUNT>2"),
            ("MAX_CELLS > CELLS", "MAX_CELLS > SLOT_COUNT"),
            ("CELLS_MAX > CELLS", "CELLS_MAX > SLOT_COUNT"),
            ("CELLS2 > CELLS", "CELLS2 > SLOT_COUNT"),
            ("cells > CELLS", "cells > SLOT_COUNT"),
            ("CELLS$1 > CELLS", "CELLS$1 > SLOT_COUNT"),
            (
                "\N{LATIN SMALL LETTER E WITH ACUTE}CELLS > CELLS",
                "\N{LATIN SMALL LETTER E WITH ACUTE}CELLS > SLOT_COUNT",
            ),
            (
                "\N{MATHEMATICAL BOLD CAPITAL A}CELLS > CELLS",
                "\N{MATHEMATICAL BOLD CAPITAL A}CELLS > SLOT_COUNT",
            ),
            (
                "CELLS\N{COMBINING ACUTE ACCENT} > CELLS",
                "CELLS\N{COMBINING ACUTE ACCENT} > SLOT_COUNT",
            ),
            (
                "CELLS\N{COMBINING DOTTED GRAVE ACCENT} > CELLS",
                "CELLS\N{COMBINING DOTTED GRAVE ACCENT} > SLOT_COUNT",
            ),
            (
                "CELLS\N{COMBINING RIGHT ARROW ABOVE} > CELLS",
                "CELLS\N{COMBINING RIGHT ARROW ABOVE} > SLOT_COUNT",
            ),
            (
                "CELLS\N{COMBINING LIGATURE LEFT HALF} > CELLS",
                "CELLS\N{COMBINING LIGATURE LEFT HALF} > SLOT_COUNT",
            ),
            ("defined(ROWS) &&\tCELLS > 2", "defined(ROWS) &&\tSLOT_COUNT > 2"),
            ('__has_include("x.h") && CELLS > 2', '__has_include("x.h") && SLOT_COUNT > 2'),
        ],
        ids=[
            "every-word",
            "no-space",
            "underscore-before",
            "underscore-after",
            "digit-after",
            "other-case",
            "dollar",
            "other-script",
            "astral-letter",
            "combining-mark",
            "combining-mark-supplement",
            "combining-mark-for-symbols",
            "combining-half-mark",
            "escaped-tab",
            "escaped-quotes",
        ],
    )
    def test_the_constant_s_word_is_rewritten_and_no_other(
        self, tmp_path: Path, condition: str, after: str
    ) -> None:
        """Every word of the condition that is the constant, and nothing else: not another
        constant, not a longer identifier holding it - gcc and clang take a letter of any script
        and a dollar sign in one, and C11's Annex D a combining mark after the first character -
        and not the escapes json writes for a tab or a quote before it, which put the word further
        along in the file than in the condition. Written by ``json.dumps``, a letter beyond the
        basic plane is the two escapes of a surrogate pair, and is one letter all the same."""
        rewritten = self.renamed(tmp_path, sized_under(condition))
        assert self.big(rewritten["w.ddd.json"])["condition"] == after

    def test_a_word_json_spells_with_an_escape_is_rewritten_whole(self, tmp_path: Path) -> None:
        """``C\\u0045LLS`` is ``CELLS`` as json reads it, so the condition spells the constant,
        and the edit covers the escape with the rest of the word."""
        text = json.dumps(sized_under("CELLS > 2"), indent=2).replace(
            '"CELLS > 2"', '"C\\u0045LLS > 2"'
        )
        assert '"condition": "SLOT_COUNT > 2"' in self.renamed(tmp_path, text)["w.ddd.json"]

    @pytest.mark.parametrize(
        "since",
        [
            sized_under("ROWS > 2"),
            component("W", declare("output", "Big", dimensions=["CELLS"])),
        ],
        ids=["respelled", "taken-away"],
    )
    def test_a_condition_that_no_longer_spells_it_is_reported_drifted(
        self, tmp_path: Path, since: dict[str, Any]
    ) -> None:
        """The index read the condition as the analysis did, and the file has changed since - the
        condition respelled, or taken away: the rename names the file rather than leave the old
        name, or rewrite another word."""
        from ddd.lsp.navigation import rename_edits

        built, root = built_of(tmp_path, **UNDER_A_CONDITION)
        write_tree(root, {"w.ddd.json": since})
        cache: dict[Path, Document] = {}
        edits = rename_edits(
            built, read(root / "c.ddd.json", cache), "constants[0].name", "SLOTS", cache
        )
        assert [path.name for path in edits.drifted] == ["w.ddd.json"]

    def test_a_word_no_file_declares_as_a_constant_is_the_build_s(self, tmp_path: Path) -> None:
        """A word of a condition is a constant only where the project declares one of that name;
        any other is a macro the build defines, or none. A shape naming a constant nothing
        declares is ``unknown-constant``, and its rename reaches the shapes alone."""
        from ddd.lsp.navigation import rename_edits

        ghost = component(
            "W", declare("output", "Big", dimensions=["GHOST"], condition="GHOST > 2")
        )
        built, root = built_of(tmp_path, **{"w.ddd.json": ghost})
        assert built.condition_uses == {}
        cache: dict[Path, Document] = {}
        edits = rename_edits(
            built,
            read(root / "w.ddd.json", cache),
            "component.interface[0].definition.dimensions[0]",
            "SEEN",
            cache,
        )
        big = self.big(rewritten_by(edits.changes)["w.ddd.json"])
        assert (big["condition"], big["definition"]["dimensions"]) == ("GHOST > 2", ["SEEN"])

    def test_a_raster_spelled_like_a_constant_leaves_the_condition_alone(
        self, tmp_path: Path
    ) -> None:
        """A raster's name is no macro, so no condition spells one, whatever constant shares its
        spelling."""
        from ddd.lsp.navigation import rename_edits

        built, root = built_of(
            tmp_path,
            **{
                **UNDER_A_CONDITION,
                "r.ddd.json": {"rasters": [{"raster": "CELLS", "event": 1, "cycle": "10ms"}]},
                "w.ddd.json": component(
                    "W",
                    declare(
                        "output", "Big", dimensions=["CELLS"], condition="CELLS > 2", raster="CELLS"
                    ),
                ),
            },
        )
        cache: dict[Path, Document] = {}
        edits = rename_edits(
            built, read(root / "r.ddd.json", cache), "rasters[0].raster", "R10", cache
        )
        big = self.big(rewritten_by(edits.changes)["w.ddd.json"])
        assert (big["definition"]["raster"], big["condition"]) == ("R10", "CELLS > 2")


class TestAUnitPlanAsTextEdits:
    """A unit's plan as an editor applies it, and the buffers that keep it from being made."""

    def vocabulary(self, tmp_path: Path) -> Path:
        write_tree(tmp_path, {"units.ddd.json": {"units": ["rpm", {"unit": "Nm"}, "degC", "kPa"]}})
        return tmp_path / "units.ddd.json"

    @pytest.mark.parametrize(
        "operations",
        [
            pytest.param((Operation("set", "units[0]", '"1/min"'),), id="replaced"),
            pytest.param((Operation("set", "units[1].unit", '"N.m"'),), id="replaced-in-an-object"),
            pytest.param(
                (Operation("set", "units[1].description", '"torque"'),), id="member-added"
            ),
            pytest.param((Operation("insert", "units[4]", '"bar"'),), id="inserted"),
            pytest.param((Operation("remove", "units[1]"),), id="removed"),
            pytest.param(
                (Operation("remove", "units[3]"), Operation("remove", "units[2]")),
                id="neighbours-removed-last-first",
            ),
            pytest.param(
                (Operation("remove", "units[2]"), Operation("remove", "units[2]")),
                id="neighbours-removed-in-turn",
            ),
            pytest.param(
                (
                    Operation("set", "units[0]", '"1/min"'),
                    Operation("remove", "units[3]"),
                    Operation("remove", "units[2]"),
                ),
                id="replaced-and-removed",
            ),
        ],
    )
    def test_a_client_applying_the_edits_writes_what_the_engine_writes(
        self, tmp_path: Path, operations: tuple[Operation, ...]
    ) -> None:
        """The engine makes a file's operations in turn, each on the text the last one left; a
        client applies a file's edits at once, to the text as it stands. The file has to come
        out the same, or the editor and ddd gui would write two different things."""
        path = self.vocabulary(tmp_path)
        plan = UnitPlan((PlannedEdit(path, operations),))
        (edits,) = text_edits(plan, {}).values()
        assert apply_edits(path, edits) == edit_text(path.read_text(encoding="utf-8"), operations)

    def test_neighbouring_entries_taken_out_are_one_edit(self, tmp_path: Path) -> None:
        """Each removal takes one comma, and against the text as it stands the two would both
        claim the one between them: two overlapping edits, which a client refuses whole."""
        path = self.vocabulary(tmp_path)
        removed = (Operation("remove", "units[3]"), Operation("remove", "units[2]"))
        (edits,) = text_edits(UnitPlan((PlannedEdit(path, removed),)), {}).values()
        assert len(edits) == 1
        assert json.loads(apply_edits(path, edits))["units"] == ["rpm", {"unit": "Nm"}]

    def test_the_edit_is_made_in_the_buffer_on_screen(self, tmp_path: Path) -> None:
        """The client applies it to what it shows, which one blank line puts a line lower."""
        path = self.vocabulary(tmp_path)
        disk = path.read_text(encoding="utf-8")
        plan = UnitPlan((PlannedEdit(path, (Operation("set", "units[0]", '"1/min"'),)),))
        (edits,) = text_edits(plan, {path: Document("\n" + disk)}).values()
        on_disk = Document(disk).value_range_of("units[0]")
        assert on_disk is not None
        assert edits[0]["range"]["start"]["line"] == on_disk["start"]["line"] + 1

    def test_a_file_the_plan_creates_is_no_text_edit(self, tmp_path: Path) -> None:
        """Only an adoption creates a file, and only ddd gui adopts: an edit of a file that is
        not there would be one no client can apply."""
        created = PlannedEdit(
            tmp_path / "units.ddd.json",
            (Operation("set", "", '{"units": ["rpm"]}'),),
            creates=True,
        )
        with pytest.raises(EditError) as refused:
            text_edits(UnitPlan((created,)), {})
        assert refused.value.code == INVALID

    def built(self, tmp_path: Path) -> Any:
        workspace = load_workspace(unit_places(tmp_path), DiagnosticBag())
        assert workspace is not None
        return navigation.index(workspace)

    def test_a_unit_where_the_index_found_it_has_not_drifted(self, tmp_path: Path) -> None:
        """Its entry an object or the spelling alone, wherever it is stated."""
        built = self.built(tmp_path)
        assert unit_drift(built, "rpm", {}) == ()
        assert unit_drift(built, "Nm", {}) == ()

    def test_a_buffer_that_moved_a_stated_unit_has_drifted(self, tmp_path: Path) -> None:
        built = self.built(tmp_path)
        b = tmp_path / "b.ddd.json"
        moved = json.dumps(
            component(
                "B", declare("input", "Other", unit="Nm"), declare("input", "Speed", unit="rpm")
            ),
            indent=2,
        )
        assert unit_drift(built, "rpm", {b: Document(moved)}) == (b,)

    def test_a_buffer_that_moved_a_vocabulary_entry_has_drifted(self, tmp_path: Path) -> None:
        built = self.built(tmp_path)
        units = tmp_path / "units.ddd.json"
        moved = Document(json.dumps({"units": ["Nm", {"unit": "rpm", "description": "speed"}]}))
        assert unit_drift(built, "rpm", {units: moved}) == (units,)
        assert unit_drift(built, "Nm", {units: moved}) == (units,)

    def test_the_files_a_name_drifted_in_are_named_once_each_in_path_order(
        self, tmp_path: Path
    ) -> None:
        """What every plan pointing by the index asks of the places it points at: each file
        whose text no longer holds the name at one of them, once however many of its places
        moved, in the order of the files' paths whatever the order of the places."""
        files = [tmp_path / f"{letter}.ddd.json" for letter in "fedcba"]
        held = Document(json.dumps({"name": "X", "typename": "X"}))
        moved = Document(json.dumps({"name": "Y", "typename": "Y"}))
        sites = [navigation.Site(path, key) for path in files for key in ("name", "typename")]
        assert navigation.drift(sites, "X", dict.fromkeys(files, moved)) == tuple(reversed(files))
        some = {**dict.fromkeys(files, held), files[0]: moved, files[3]: moved}
        assert navigation.drift(sites, "X", some) == (files[3], files[0])
        assert navigation.drift(sites, "X", dict.fromkeys(files, held)) == ()


class TestPropagating:
    """Giving the other declarations of one object the value under the cursor."""

    def built(self, tmp_path: Path, **files: Any) -> Any:
        write_tree(tmp_path, {"p.ddd.json": project("P", *files), **files})
        return self.built_from(tmp_path / "p.ddd.json")

    def built_from(self, root: Path) -> Any:
        from ddd.lsp.navigation import index

        workspace = load_workspace(root, DiagnosticBag())
        assert workspace is not None
        return index(workspace)

    def offer(self, tmp_path: Path, source: str, pointer: str, **files: Any) -> Any:
        from ddd.lsp.edits import actions

        built = self.built(tmp_path, **files)
        cache: dict[Path, Document] = {}
        path = tmp_path / source
        return actions(built, path, read(path, cache), pointer, cache), cache

    def test_a_value_replaces_the_one_the_others_hold(self, tmp_path: Path) -> None:
        offered, _ = self.offer(
            tmp_path,
            "a.ddd.json",
            "component.interface[0].definition.unit",
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="1/min")),
            },
        )
        assert reconciled(offered)[0] == "Apply this unit to 1 other declaration of 'Speed'"
        (edits,) = offered[0]["edit"]["changes"].values()
        assert edits[0]["newText"] == '"rpm"'

    def test_a_key_its_own_kind_requires_is_never_removed(self, tmp_path: Path) -> None:
        """The state every migration passes through: one file not yet updated, the rest right.

        The offer that settles it is to take the key. The offer to remove it from everybody
        else settles it too, on paper, and leaves a project whose files no longer load - which
        is why an edit is measured against what the loader will accept, not only against what
        the other declarations say.
        """
        write_tree(tmp_path, {"p.ddd.json": project("P", "a.ddd.json", "b.ddd.json")})
        write_tree(tmp_path, {"a.ddd.json": component("A", declare("output", "S", volatile=True))})
        incomplete = component("B", declare("input", "S"))
        del incomplete["component"]["interface"][0]["definition"]["volatile"]
        write_tree(tmp_path, {"b.ddd.json": incomplete})
        from ddd.lsp.edits import actions

        built = self.built_from(tmp_path / "p.ddd.json")
        cache: dict[Path, Document] = {}
        path = tmp_path / "b.ddd.json"
        offered = actions(
            built, path, read(path, cache), "component.interface[0].definition", cache, UNSTAMPED
        )
        titles = reconciled(offered)
        assert titles == ["Use the volatile declared in a"]

    def test_a_key_the_other_kind_does_not_have_is_not_written_into_it(
        self, tmp_path: Path
    ) -> None:
        """Two declarations disagreeing about ``kind`` is its own finding, not a key to spread.

        A curve's ``axis`` written into the measurement somebody else declared produces a file
        the loader refuses, and removing it from the curve produces another - so on a pair
        this far apart the honest answer is to offer nothing and let the mismatch be read.

        Asked from both ends, because the two ends run different code: the curve reaches the
        other declaration through ``_propagate``, while the measurement reaches back through
        ``_adopt``, and only one of those was guarded when the guard was first written.
        """
        files = {
            "a.ddd.json": component(
                "A",
                declare("output", "S", kind="curve", axis="Ax"),
                declare("output", "Ax", kind="axis", size=3),
            ),
            "b.ddd.json": component("B", declare("input", "S")),
        }
        from_curve, _ = self.offer(
            tmp_path, "a.ddd.json", "component.interface[0].definition.axis", **files
        )
        assert from_curve == []
        from_measurement, _ = self.offer(
            tmp_path, "b.ddd.json", "component.interface[0].definition", **files
        )
        assert from_measurement == []

    def test_the_kind_is_never_offered(self, tmp_path: Path) -> None:
        """The one key whose value decides which other keys are allowed.

        Writing the producer's ``kind`` into the consumer would leave keys the new kind
        forbids and drop keys it requires, and the file would stop loading rather than stop
        disagreeing - a schema error, which no severity setting can turn down.
        """
        offered, _ = self.offer(
            tmp_path,
            "b.ddd.json",
            "component.interface[0].definition.kind",
            **{
                "a.ddd.json": component("A", declare("output", "Speed", kind="parameter")),
                "b.ddd.json": component("B", declare("input", "Speed", kind="measurement")),
            },
        )
        assert offered == []

    def test_a_key_the_others_lack_is_inserted(self, tmp_path: Path) -> None:
        """The usual mismatch: the other declaration simply never mentioned it."""
        offered, _ = self.offer(
            tmp_path,
            "a.ddd.json",
            "component.interface[0].definition.unit",
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed")),
            },
        )
        spread = next(a for a in offered if a["title"].startswith("Apply"))
        (edits,) = spread["edit"]["changes"].values()
        rewritten = apply_edits(tmp_path / "b.ddd.json", edits)
        declared = json.loads(rewritten)["component"]["interface"][0]["definition"]
        assert declared["unit"] == "rpm"

    def test_a_missing_key_is_not_read_from_a_buffer_where_the_pointer_has_drifted(
        self, tmp_path: Path
    ) -> None:
        """`_missing` reads every other declaration to see which keys it lacks; a buffer with
        a declaration inserted above must not be read at the disk's now wrong position, or a
        key only the wrong declaration states looks like one 'Speed' is missing."""
        from ddd.lsp.edits import _missing

        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed")),
                "b.ddd.json": component("B", declare("input", "Speed")),
            },
        )
        built = self.built_from(tmp_path / "p.ddd.json")
        a_path = tmp_path / "a.ddd.json"
        b_path = tmp_path / "b.ddd.json"
        # B's buffer gained a declaration in front of the one the index knows.
        drifted = json.dumps(
            component("B", declare("input", "Other", unit="Hz"), declare("input", "Speed")),
            indent=2,
        )
        cache: dict[Path, Document] = {b_path: Document(drifted)}
        absent = _missing(
            built, a_path, read(a_path, cache), "Speed", "component.interface[0].definition", cache
        )
        assert absent == [], "'unit' is 'Other's, not the drifted 'Speed' declaration's"

    def test_a_value_is_copied_as_written_rather_than_re_serialised(self, tmp_path: Path) -> None:
        """A conversion arrives looking the way its author typed it, not the way json.dumps
        would have; otherwise a one line fix reformats somebody's file."""
        from ddd.lsp.edits import actions
        from ddd.lsp.navigation import index

        write_tree(tmp_path, {"p.ddd.json": project("P", "a.ddd.json", "b.ddd.json")})
        (tmp_path / "a.ddd.json").write_text(
            '{"component": {"name": "A", "interface": [{"scope": "output", "definition":'
            ' {"name": "S", "kind": "measurement", "datatype": "uint8",'
            ' "conversion": { "kind": "linear", "factor": 0.25 }}}]}}',
            encoding="utf-8",
        )
        write_tree(tmp_path, {"b.ddd.json": component("B", declare("input", "S"))})
        built = index(load_workspace(tmp_path / "p.ddd.json", DiagnosticBag()))
        cache: dict[Path, Document] = {}
        path = tmp_path / "a.ddd.json"
        offered = actions(
            built,
            path,
            read(path, cache),
            "component.interface[0].definition.conversion",
            cache,
        )
        spread = next(a for a in offered if a["title"].startswith("Apply"))
        (edits,) = spread["edit"]["changes"].values()
        assert '{ "kind": "linear", "factor": 0.25 }' in edits[0]["newText"]

    def test_an_object_written_on_one_line_stays_on_one_line(self, tmp_path: Path) -> None:
        from ddd.lsp.edits import actions
        from ddd.lsp.navigation import index

        write_tree(tmp_path, {"p.ddd.json": project("P", "a.ddd.json", "b.ddd.json")})
        write_tree(tmp_path, {"a.ddd.json": component("A", declare("output", "S", unit="rpm"))})
        (tmp_path / "b.ddd.json").write_text(
            '{"component": {"name": "B", "interface": [{"scope": "input", "definition":'
            ' {"name": "S", "kind": "measurement", "datatype": "uint8",'
            ' "conversion": {}, "volatile": false}}]}}\n',
            encoding="utf-8",
        )
        built = index(load_workspace(tmp_path / "p.ddd.json", DiagnosticBag()))
        cache: dict[Path, Document] = {}
        path = tmp_path / "a.ddd.json"
        offered = actions(
            built, path, read(path, cache), "component.interface[0].definition.unit", cache
        )
        spread = next(entry for entry in offered if entry["title"].startswith("Apply"))
        (edits,) = spread["edit"]["changes"].values()
        rewritten = apply_edits(tmp_path / "b.ddd.json", edits)
        assert rewritten.count("\n") == 1  # still one line, plus the trailing newline
        assert json.loads(rewritten)["component"]["interface"][0]["definition"]["unit"] == "rpm"

    def test_the_action_carries_the_finding_it_settles(self, tmp_path: Path) -> None:
        """What puts the lightbulb on the squiggle rather than leaving the fix to be guessed."""
        from ddd.lsp.edits import actions

        built = self.built(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="1/min")),
            },
        )
        cache: dict[Path, Document] = {}
        path = tmp_path / "a.ddd.json"
        reported = [
            {"code": "definition-mismatch", "source": "ddd", "message": "differ"},
            {"code": "unused-output", "source": "ddd", "message": "unrelated"},
        ]
        (action,) = actions(
            built,
            path,
            read(path, cache),
            "component.interface[0].definition.unit",
            cache,
            reported,
        )
        # Only the finding this actually settles: claiming to fix an unrelated one would put
        # the lightbulb on a squiggle it does nothing about.
        assert [entry["code"] for entry in action["diagnostics"]] == ["definition-mismatch"]

    def test_a_reconcile_fix_says_the_readers_code_is_not_touched(self, tmp_path: Path) -> None:
        """The check goes green once the descriptions agree, and the readers keep the scale they
        were written with: the editor's titles say so after what they change, as the page's do."""
        offered, _ = self.offer(
            tmp_path,
            "b.ddd.json",
            "component.interface[0].definition.unit",
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="1/min")),
            },
        )
        assert [action["title"] for action in offered] == [
            "Use the unit declared in a (the code of the readers is not touched)",
            "Apply this unit to 1 other declaration of 'Speed' (the code of the readers is not "
            "touched)",
        ]

    def test_an_action_with_nothing_to_settle_carries_no_finding(self, tmp_path: Path) -> None:
        offered, _ = self.offer(
            tmp_path,
            "a.ddd.json",
            "component.interface[0].definition.unit",
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="1/min")),
            },
        )
        (action,) = offered
        assert "diagnostics" not in action

    def test_a_consumer_is_offered_the_producer_value_first(self, tmp_path: Path) -> None:
        """The direction that reads naturally from a component that only reads the variable.

        Offering it only the other way round means a consumer's fix is to redefine data it
        does not own, which is the opposite of the rule the rest of the tool is built on.
        """
        offered, _ = self.offer(
            tmp_path,
            "b.ddd.json",
            "component.interface[0].definition.unit",
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="1/min")),
            },
        )
        assert reconciled(offered) == [
            "Use the unit declared in a",
            "Apply this unit to 1 other declaration of 'Speed'",
        ]

    def test_the_producer_is_offered_its_own_value_first(self, tmp_path: Path) -> None:
        offered, _ = self.offer(
            tmp_path,
            "a.ddd.json",
            "component.interface[0].definition.unit",
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="1/min")),
            },
        )
        assert reconciled(offered)[0] == "Apply this unit to 1 other declaration of 'Speed'"

    def test_taking_the_producer_value_edits_only_this_file(self, tmp_path: Path) -> None:
        offered, _ = self.offer(
            tmp_path,
            "b.ddd.json",
            "component.interface[0].definition.unit",
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="1/min")),
            },
        )
        (uri,) = offered[0]["edit"]["changes"]
        assert uri_to_path(uri).name == "b.ddd.json"
        rewritten = apply_edits(tmp_path / "b.ddd.json", offered[0]["edit"]["changes"][uri])
        assert json.loads(rewritten)["component"]["interface"][0]["definition"]["unit"] == "rpm"

    def test_a_consumer_lacking_a_key_takes_it_from_the_producer(self, tmp_path: Path) -> None:
        offered, _ = self.offer(
            tmp_path,
            "b.ddd.json",
            "component.interface[0].definition",
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed")),
            },
        )
        assert reconciled(offered)[0] == "Use the unit declared in a"

    def test_with_no_single_producer_only_the_outward_fix_is_offered(self, tmp_path: Path) -> None:
        """Two producers is its own finding, and not one to guess a value through."""
        offered, _ = self.offer(
            tmp_path,
            "c.ddd.json",
            "component.interface[0].definition.unit",
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("output", "Speed", unit="rpm")),
                "c.ddd.json": component("C", declare("input", "Speed", unit="1/min")),
            },
        )
        assert reconciled(offered) == ["Apply this unit to 2 other declarations of 'Speed'"]

    def test_a_key_nobody_else_states_can_be_removed(self, tmp_path: Path) -> None:
        """Two declarations disagree just as much when one of them says nothing.

        Spreading the value and dropping it settle the finding equally well, and which one an
        author wants is not something to decide for them.
        """
        offered, _ = self.offer(
            tmp_path,
            "b.ddd.json",
            "component.interface[0].definition.unit",
            **{
                "a.ddd.json": component("A", declare("output", "Speed")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="rpm")),
            },
        )
        assert reconciled(offered) == [
            "Remove this unit, which a does not declare",
            "Apply this unit to 1 other declaration of 'Speed'",
        ]
        rewritten = apply_edits(
            tmp_path / "b.ddd.json", next(iter(offered[0]["edit"]["changes"].values()))
        )
        assert "unit" not in json.loads(rewritten)["component"]["interface"][0]["definition"]

    def test_a_key_somebody_else_states_is_not_offered_for_removal(self, tmp_path: Path) -> None:
        """Removing it would settle nothing: the other declaration would still have one."""
        offered, _ = self.offer(
            tmp_path,
            "b.ddd.json",
            "component.interface[0].definition.unit",
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="1/min")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="rpm")),
            },
        )
        assert not any(action["title"].startswith("Remove") for action in offered)

    def test_removal_says_so_generically_when_there_is_no_producer(self, tmp_path: Path) -> None:
        offered, _ = self.offer(
            tmp_path,
            "b.ddd.json",
            "component.interface[0].definition.unit",
            **{
                "a.ddd.json": component("A", declare("input", "Speed")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="rpm")),
            },
        )
        assert (
            reconciled(offered)[0] == "Remove this unit, which no other declaration of 'Speed' has"
        )

    @pytest.mark.parametrize("key", ["unit", "limits"])
    def test_removing_a_member_takes_exactly_one_comma_with_it(
        self, tmp_path: Path, key: str
    ) -> None:
        """Whichever comma is the joining one: the member's own, or the previous member's when
        it is the last thing in the object."""
        from ddd.lsp.edits import _erase

        write_tree(
            tmp_path,
            {
                "a.ddd.json": component(
                    "A", declare("output", "S", unit="rpm", limits={"min": 0, "max": 1})
                )
            },
        )
        path = tmp_path / "a.ddd.json"
        document = read(path, {})
        edit = _erase(document, "component.interface[0].definition", key)
        assert edit is not None
        rewritten = apply_edits(path, [edit])
        declared = json.loads(rewritten)["component"]["interface"][0]["definition"]
        assert key not in declared
        assert declared["name"] == "S"

    def test_the_only_member_of_an_object_is_not_removed(self) -> None:
        """What to leave between the braces is a judgement about style, not about the data."""
        from ddd.lsp.edits import _erase

        document = Document('{"component": {"interface": [{"definition": {"unit": "rpm"}}]}}')
        assert _erase(document, "component.interface[0].definition", "unit") is None

    def test_a_key_that_is_not_there_is_not_removed(self) -> None:
        from ddd.lsp.edits import _erase

        document = Document('{"component": {"interface": [{"definition": {"name": "S"}}]}}')
        assert _erase(document, "component.interface[0].definition", "unit") is None

    def test_a_declaration_missing_a_key_is_offered_the_one_the_others_agree_on(
        self, tmp_path: Path
    ) -> None:
        """The direction the first version could not go.

        A declaration with no ``unit`` has none to give, so asking for a fix there offered
        nothing at all - and the only file that would offer one was a file already correct.
        """
        offered, _ = self.offer(
            tmp_path,
            "a.ddd.json",
            "component.interface[0].definition",
            **{
                "a.ddd.json": component("A", declare("output", "Speed")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="rpm")),
                "c.ddd.json": component("C", declare("input", "Speed", unit="rpm")),
            },
        )
        assert reconciled(offered) == [
            # The producer's silence, sent out - and the value the others agree on, brought in.
            "Remove the unit from 2 other declarations of 'Speed'",
            "Take the unit the other declarations of 'Speed' state",
        ]
        take = offered[1]
        (edits,) = take["edit"]["changes"].values()
        rewritten = apply_edits(tmp_path / "a.ddd.json", edits)
        assert json.loads(rewritten)["component"]["interface"][0]["definition"]["unit"] == "rpm"

    def test_a_key_the_others_disagree_about_is_not_taken(self, tmp_path: Path) -> None:
        """Which of two answers is right is a question, and answering it silently is not help.

        Sending this declaration's silence out is still offered: that settles the finding
        without choosing between them.
        """
        offered, _ = self.offer(
            tmp_path,
            "a.ddd.json",
            "component.interface[0].definition",
            **{
                "a.ddd.json": component("A", declare("output", "Speed")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="rpm")),
                "c.ddd.json": component("C", declare("input", "Speed", unit="1/min")),
            },
        )
        assert reconciled(offered) == ["Remove the unit from 2 other declarations of 'Speed'"]

    def test_one_value_the_others_spell_differently_is_still_the_answer_they_agree_on(
        self, tmp_path: Path
    ) -> None:
        """Two spellings of one conversion are one answer, not two.

        The checker files nothing between those two declarations, so counting their spellings
        would withhold the fix from declarations it calls settled. The declaration asked at is
        one being written - a ``datatype`` whose ``conversion`` is not there yet, which is the
        state the fix is for - so it is spelled out by hand: `declare` fills a conversion in for
        every measurement.
        """
        without = {
            "scope": "output",
            "definition": {
                "name": "Speed",
                "datatype": "uint8",
                "kind": "measurement",
                "volatile": False,
            },
        }
        offered, _ = self.offer(
            tmp_path,
            "a.ddd.json",
            "component.interface[0].definition",
            **{
                "a.ddd.json": component("A", without),
                "b.ddd.json": component(
                    "B", declare("input", "Speed", conversion={"kind": "linear", "factor": 2})
                ),
                "c.ddd.json": component(
                    "C", declare("input", "Speed", conversion={"factor": 2, "offset": 0})
                ),
            },
        )
        assert reconciled(offered) == [
            # Taken first: a declaration the loader dropped is in nobody's producer list, so
            # this reads as a consumer, which is offered somebody else's answer first.
            "Take the conversion the other declarations of 'Speed' state",
            # And taken only. Sending this declaration's silence out - "Remove the conversion
            # from 2 other declarations of 'Speed'" - is no longer offered: `b` and `c` each
            # state a `datatype`, which comes with its conversion, so the removal would leave
            # both files refused with "a 'datatype' comes with a 'conversion'".
        ]
        take = offered[0]
        (edits,) = take["edit"]["changes"].values()
        rewritten = apply_edits(tmp_path / "a.ddd.json", edits)
        # The first spelling the index lists, written verbatim as every value here is.
        assert json.loads(rewritten)["component"]["interface"][0]["definition"]["conversion"] == {
            "kind": "linear",
            "factor": 2,
        }

    def test_nothing_is_offered_when_everybody_already_agrees(self, tmp_path: Path) -> None:
        """A fix that changes nothing teaches a reader to stop looking at the lightbulb."""
        offered, _ = self.offer(
            tmp_path,
            "a.ddd.json",
            "component.interface[0].definition.unit",
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="rpm")),
            },
        )
        assert offered == []

    def test_no_action_offers_to_rewrite_a_value_that_already_means_the_same(
        self, tmp_path: Path
    ) -> None:
        """`ddd gui` has compared meaning since part 3; the editor now does too, so a lightbulb
        that rewrote a line to the value it already had is gone."""
        offered, _ = self.offer(
            tmp_path,
            "b.ddd.json",
            "component.interface[0].definition.conversion",
            **{
                "a.ddd.json": component(
                    "A", declare("output", "Speed", conversion={"kind": "linear", "factor": 2})
                ),
                "b.ddd.json": component(
                    "B", declare("input", "Speed", conversion={"factor": 2, "offset": 0})
                ),
            },
        )
        assert [entry["title"] for entry in offered] == []

    def test_nothing_is_offered_when_nobody_else_declares_it(self, tmp_path: Path) -> None:
        offered, _ = self.offer(
            tmp_path,
            "a.ddd.json",
            "component.interface[0].definition.unit",
            **{"a.ddd.json": component("A", declare("local", "Speed", unit="rpm"))},
        )
        assert offered == []

    @pytest.mark.parametrize("pointer", ["component.interface[0].scope", "component.name", ""])
    def test_outside_a_definition_nothing_is_offered(self, tmp_path: Path, pointer: str) -> None:
        offered, _ = self.offer(
            tmp_path,
            "a.ddd.json",
            pointer,
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="1/min")),
            },
        )
        assert offered == []

    @pytest.mark.parametrize(
        "pointer",
        [
            "component.interface[0].definition",
            "component.interface[0].definition.name",
            "component.interface[0].definition.description",
            "component.interface[0].definition.limits.min",
        ],
    )
    def test_asking_anywhere_in_a_declaration_offers_every_differing_key(
        self, tmp_path: Path, pointer: str
    ) -> None:
        """The finding is drawn over the whole declaration, so that is where a pointer lands.

        Requiring somebody to have found the offending key first asks them to do the diagnosis
        the fix exists for - and leaves the menu to whatever else claims the shortcut.
        """
        offered, _ = self.offer(
            tmp_path,
            "a.ddd.json",
            pointer,
            **{
                "a.ddd.json": component(
                    "A",
                    declare(
                        "output",
                        "Speed",
                        "sint16",
                        unit="rpm",
                        limits={"min": 0, "max": 100},
                        description="ours",
                    ),
                ),
                "b.ddd.json": component("B", declare("input", "Speed", "uint16", unit="1/min")),
            },
        )
        # b states no limits, and a declaration that omits them defers to the one that states
        # them - the checker's rule - so the limits are not a disagreement to settle.
        assert reconciled(offered) == [
            "Apply this datatype to 1 other declaration of 'Speed'",
            "Apply this unit to 1 other declaration of 'Speed'",
        ]

    @pytest.mark.parametrize("source", ["prod.ddd.json", "cons.ddd.json"])
    def test_limits_one_side_leaves_out_are_not_offered_from_either(
        self, tmp_path: Path, source: str
    ) -> None:
        """Omitted limits defer to whoever states them, which is agreement to the checker.

        ``ddd check`` reports nothing on this project, so a lightbulb offering to spread the
        consumer's range into the producer, or to strip it, was a fix on a clean declaration -
        and taking either changed the range the a2l publishes without a finding before or after.
        """
        offered, _ = self.offer(
            tmp_path,
            source,
            "component.interface[0].definition",
            **{
                "prod.ddd.json": component("P", declare("output", "T", unit="rpm")),
                "cons.ddd.json": component(
                    "C", declare("input", "T", unit="rpm", limits={"min": 0, "max": 100})
                ),
            },
        )
        assert [action["title"] for action in offered] == []

    def test_two_stated_limits_that_differ_are_still_reconciled(self, tmp_path: Path) -> None:
        """Only two stated ranges can disagree, and those are offered both ways."""
        files = {
            "prod.ddd.json": component(
                "P", declare("output", "T", unit="rpm", limits={"min": 0, "max": 100})
            ),
            "cons.ddd.json": component(
                "C", declare("input", "T", unit="rpm", limits={"min": 0, "max": 80})
            ),
        }
        consumer, _ = self.offer(
            tmp_path, "cons.ddd.json", "component.interface[0].definition", **files
        )
        assert reconciled(consumer) == [
            "Use the limits declared in prod",
            "Apply this limits to 1 other declaration of 'T'",
        ]
        producer, _ = self.offer(
            tmp_path, "prod.ddd.json", "component.interface[0].definition", **files
        )
        assert reconciled(producer) == [
            "Apply this limits to 1 other declaration of 'T'",
        ]

    def test_a_key_of_its_own_offers_only_that_key(self, tmp_path: Path) -> None:
        """Asked precisely, answered precisely: a name is a rename and a description is a
        component's own words, so neither is offered even from inside the definition."""
        offered, _ = self.offer(
            tmp_path,
            "a.ddd.json",
            "component.interface[0].definition.unit",
            **{
                "a.ddd.json": component(
                    "A", declare("output", "Speed", "sint16", unit="rpm", description="ours")
                ),
                "b.ddd.json": component("B", declare("input", "Speed", "uint16", unit="1/min")),
            },
        )
        assert [action["title"].split()[2] for action in offered] == ["unit"]

    def test_a_declaration_being_written_offers_nothing(self, tmp_path: Path) -> None:
        """No name yet, so there is nothing to look the other declarations up by."""
        from ddd.lsp.edits import actions
        from ddd.lsp.navigation import Index

        write_tree(tmp_path, {"a.ddd.json": component("A", declare("output", "S", unit="rpm"))})
        path = tmp_path / "a.ddd.json"
        document = Document('{"component": {"interface": [{"definition": {"unit": "rpm"}}]}}')
        assert actions(Index(), path, document, "component.interface[0].definition.unit", {}) == []

    def test_something_that_is_not_an_object_states_no_keys(self) -> None:
        """These are read from disk a moment after the loader saw them; a file rewritten in
        between must not take the server down."""
        from ddd.lsp.edits import interface_keys

        assert interface_keys({"unit": "rpm", "name": "S"}) == ["unit"]
        assert interface_keys(7) == []
        assert interface_keys(None) == []

    def test_a_declaration_without_a_key_can_send_that_out(self, tmp_path: Path) -> None:
        """The mirror of spreading a value, and the direction that was missing longest.

        A declaration with no unit could take one from the producer but never say "none of you
        should have one either", so the only fix on offer changed this file rather than the
        one the author had decided was wrong.
        """
        offered, _ = self.offer(
            tmp_path,
            "b.ddd.json",
            "component.interface[0].definition",
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="Hz")),
                "b.ddd.json": component("B", declare("input", "Speed")),
            },
        )
        assert reconciled(offered) == [
            "Use the unit declared in a",
            "Remove the unit from 1 other declaration of 'Speed'",
        ]
        (edits,) = offered[1]["edit"]["changes"].values()
        rewritten = apply_edits(tmp_path / "a.ddd.json", edits)
        assert "unit" not in json.loads(rewritten)["component"]["interface"][0]["definition"]

    def test_a_target_whose_key_cannot_be_cut_out_is_left_alone(self, tmp_path: Path) -> None:
        from ddd.lsp.edits import _remove_elsewhere
        from ddd.lsp.navigation import Index, Site

        (tmp_path / "b.ddd.json").write_text(
            '{"component": {"interface": [{"definition": {"unit": "rpm"}}]}}', encoding="utf-8"
        )
        elsewhere = Site(tmp_path / "b.ddd.json", "component.interface[0].definition")
        document = Document('{"component": {"interface": [{"definition": {"name": "S"}}]}}')
        assert (
            _remove_elsewhere(
                Index(declarations={"S": [elsewhere]}),
                Site(tmp_path / "a.ddd.json", "component.interface[0].definition"),
                document,
                "S",
                "unit",
                {},
            )
            is None
        )

    def test_a_key_that_cannot_be_cut_out_is_not_offered_for_removal(self, tmp_path: Path) -> None:
        """A measurement states its volatility, so there is no version of it without one.

        The decision's refusal reached through the builder: ``settled_at`` answers ``Unsettled``
        for a removal that would leave out a key the kind requires, and nothing is offered
        rather than an edit the loader would refuse. The only other declaration says nothing
        about the key, so the "somebody else still states it" guard is not what answers here.

        ``here``'s own file is written, and its document read from it: these builders re-read
        the site from disk through ``settled_at``, so a ``Site`` whose file was never written is
        ``unreachable`` before any refusal of theirs is asked. The one refusal left in the
        spelling - an only child, with no comma to take - is ``_erase``'s, and is reached
        through ``_protocol_action`` rather than through a decision at all.
        """
        from ddd.lsp.edits import _remove_here
        from ddd.lsp.navigation import Index, Site

        write_tree(
            tmp_path,
            {
                "a.ddd.json": component("A", declare("output", "S")),
                "b.ddd.json": '{"component": {"interface": [{"definition": {"name": "S"}}]}}',
            },
        )
        here = Site(tmp_path / "a.ddd.json", "component.interface[0].definition")
        elsewhere = Site(tmp_path / "b.ddd.json", "component.interface[0].definition")
        cache: dict[Path, Document] = {}
        assert (
            _remove_here(
                Index(declarations={"S": [elsewhere]}),
                here,
                read(here.path, cache),
                "S",
                "volatile",
                cache,
            )
            is None
        )

    def test_there_is_nowhere_to_put_the_producer_value_in_a_definition_with_no_kind(
        self, tmp_path: Path
    ) -> None:
        """A definition stating nothing but the name it is found by states no ``kind`` either,
        and which keys a definition may hold is its kind's answer: nothing is known here, so
        nothing is written. ``here``'s file is written like the producer's, since a site whose
        file is not there is ``unreachable`` before this is asked."""
        from ddd.lsp.edits import _from_producer
        from ddd.lsp.navigation import Index, Site

        write_tree(
            tmp_path,
            {
                "a.ddd.json": component("A", declare("output", "S", unit="rpm")),
                "b.ddd.json": '{"component": {"interface": [{"definition": {"name": "S"}}]}}',
            },
        )
        producer = Site(tmp_path / "a.ddd.json", "component.interface[0].definition")
        here = Site(tmp_path / "b.ddd.json", "component.interface[0].definition")
        cache: dict[Path, Document] = {}
        assert (
            _from_producer(
                Index(producers={"S": [producer]}),
                here,
                read(here.path, cache),
                "S",
                "unit",
                cache,
            )
            is None
        )

    def test_there_is_nothing_to_take_into_a_definition_with_no_kind(self, tmp_path: Path) -> None:
        """The same answer for the consensus among the others: what the other declarations
        agree on is not written into a definition whose kind is unknown, however unanimous
        they are."""
        from ddd.lsp.edits import _adopt
        from ddd.lsp.navigation import Index, Site

        write_tree(
            tmp_path,
            {
                "a.ddd.json": '{"component": {"interface": [{"definition": {"name": "S"}}]}}',
                "b.ddd.json": component("B", declare("input", "S", unit="rpm")),
            },
        )
        elsewhere = Site(tmp_path / "b.ddd.json", "component.interface[0].definition")
        here = Site(tmp_path / "a.ddd.json", "component.interface[0].definition")
        cache: dict[Path, Document] = {}
        assert (
            _adopt(
                Index(declarations={"S": [elsewhere]}),
                here,
                read(here.path, cache),
                "S",
                "unit",
                cache,
            )
            is None
        )

    def test_assigning_the_value_already_stated_changes_nothing(self) -> None:
        """`_assign`'s own guarantee, kept for its own sake now that every caller happens to
        check it first: `_adopt` only calls where the target states nothing, `_from_producer`
        only where the two values differ, and `_propagate` only for a site `settle` already
        found to disagree. Asked to write what a declaration already states, there is still
        nothing for `_assign` itself to do."""
        from ddd.lsp.edits import _assign

        document = Document(
            '{"component": {"interface": [{"definition": '
            '{"name": "S", "kind": "measurement", "unit": "rpm"}}]}}'
        )
        assert _assign(document, "component.interface[0].definition", "unit", '"rpm"') is None

    def test_a_definition_that_is_not_an_object_is_left_alone(self, tmp_path: Path) -> None:
        """Belt and braces around the insertion: there is nowhere to insert into."""
        from ddd.lsp.edits import _insert

        document = Document('{"component": {"interface": [{"definition": 7}]}}')
        assert _insert(document, "component.interface[0].definition", "unit", '"rpm"') is None

    def test_a_declaration_naming_a_type_is_offered_no_unit(self, tmp_path: Path) -> None:
        """The type fixes the unit of every declaration naming it, and the loader refuses one
        stated beside it: the producer's unit is not offered to such a declaration."""
        offered, _ = self.offer(
            tmp_path,
            "b.ddd.json",
            "component.interface[0].definition",
            **{
                "types.ddd.json": types(scalar_type("Speed_t", unit="1/min")),
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", typename="Speed_t")),
            },
        )
        mine = (tmp_path / "b.ddd.json").as_uri()
        assert [
            action["title"]
            for action in offered
            if "unit" in action["title"] and mine in action["edit"]["changes"]
        ] == []

    def test_a_declaration_stating_no_type_explicitly_is_offered_the_unit(
        self, tmp_path: Path
    ) -> None:
        """An explicit ``null`` names no type, for the loader and so for the offer: a plain
        declaration that happens to state ``"typename": null`` beside its ``datatype`` is
        offered the producer's unit exactly like one that leaves ``typename`` out altogether.

        ``declare()`` drops ``datatype`` the moment ``typename`` is among its keyword
        arguments - it assumes a caller naming ``typename`` at all means storage by type - so
        this declaration is written out by hand.
        """
        offered, _ = self.offer(
            tmp_path,
            "b.ddd.json",
            "component.interface[0].definition",
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component(
                    "B",
                    {
                        "scope": "input",
                        "definition": {
                            "name": "Speed",
                            "datatype": "uint8",
                            "conversion": {"kind": "identity"},
                            "typename": None,
                            "kind": "measurement",
                            "volatile": False,
                        },
                    },
                ),
            },
        )
        (use_unit,) = [
            action
            for action, changes in zip(offered, reconciled(offered), strict=True)
            if changes == "Use the unit declared in a"
        ]
        (edits,) = use_unit["edit"]["changes"].values()
        rewritten = apply_edits(tmp_path / "b.ddd.json", edits)
        declared = json.loads(rewritten)["component"]["interface"][0]["definition"]
        assert declared["unit"] == "rpm"


class TestPositions:
    """Turning where the cursor is into what it is on."""

    TEXT = '{\n  "component": {\n    "name": "A",\n    "flag": true\n  }\n}\n'

    def test_the_innermost_value_wins(self) -> None:
        """A cursor inside a member is on that member, not on everything containing it."""
        document = Document(self.TEXT)
        assert document.pointer_at({"line": 2, "character": 6}) == "component.name"

    def test_a_cursor_outside_any_value_is_on_nothing(self) -> None:
        assert Document("").pointer_at({"line": 0, "character": 0}) == ""

    def test_a_position_past_the_end_of_a_line_stops_at_the_line(self) -> None:
        document = Document(self.TEXT)
        assert document.pointer_at({"line": 3, "character": 999}) == "component"

    def test_a_position_past_the_end_of_the_document_is_clamped(self) -> None:
        assert Document(self.TEXT).pointer_at({"line": 99, "character": 0}) == ""

    def test_a_column_is_read_in_utf16_as_it_is_written(self) -> None:
        """The round trip: a range this module produced has to come back to its own pointer."""
        text = '{"\U0001f600": 1, "after": 2}'
        document = Document(text)
        start = document.range_of("after")["start"]
        assert document.pointer_at(start) == "after"

    def test_an_offset_becomes_the_position_the_protocol_counts(self) -> None:
        """Public because the edit engine hands out offsets and the quick fixes send positions."""
        document = Document('{\n  "unit": "°C 😀",\n  "a": 1\n}')
        offset = document.text.index('"a"')
        assert document.position(offset) == {"line": 2, "character": 2}
        after_emoji = document.text.index('",\n  "a"')
        assert document.position(after_emoji)["character"] == len('  "unit": "°C 😀') + 1


# The scanner ``ddd.lsp.ranges`` walked the text with before it matched regular expressions,
# copied from that module verbatim but for its names, as the oracle the tests below compare
# ``Document`` with. Kept because the rewrite claims answers identical to this walk's, on every
# text, and only the walk itself can say what it answered: an oracle written afresh could share
# the rewrite's mistakes, and one that is the code under test agrees with any change.

_REFERENCE_WHITESPACE: Final = " \t\n\r"
_REFERENCE_LITERAL_END: Final = ",}] \t\n\r"


def _reference_line_starts(text: str) -> list[int]:
    starts = [0]
    starts.extend(index + 1 for index, character in enumerate(text) if character == "\n")
    return starts


def _reference_decoded(key: str) -> str:
    """A member's key as json means it, from the source text that spells it.

    ``"na\\u006de"`` is ``name``, and every pointer this module is asked about was built from
    the parsed document, where it already is. Taken as written, the key named nothing: a
    finding about it fell back to the enclosing object's range, and ``ddd id --assign``
    skipped such a declaration in silence, having computed an insertion for a pointer the
    document has not got.

    The parse is skipped where there is no escape to decode, which is every key of every
    description anybody writes: json's own parser has already accepted this text, so what
    comes back here is the same string it put in the document.
    """
    return str(json.loads(f'"{key}"')) if "\\" in key else key


class _ReferenceScanner:
    """A recursive descent walk over known-good json, recording where each value sits."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0
        self.spans: dict[str, tuple[int, int]] = {}
        self.texts: dict[str, tuple[int, int]] = {}
        """Where the characters of a string value sit, without the quotes around them."""
        self.values: dict[str, tuple[int, int]] = {}
        """Where a value sits, of whatever shape, without the key in front of it."""
        self._skip_whitespace()

    def value(self, pointer: str, start: int | None = None) -> None:
        begin = self.pos
        character = self.text[self.pos]
        if character == "{":
            self._object(pointer)
        elif character == "[":
            self._array(pointer)
        elif character == '"':
            self._string()
            # Between the quotes: begin is the opening one, pos is just past the closing one.
            self.texts[pointer] = (begin + 1, self.pos - 1)
        else:
            self._literal()
        self.spans[pointer] = (begin if start is None else start, self.pos)
        self.values[pointer] = (begin, self.pos)

    def _object(self, pointer: str) -> None:
        self.pos += 1
        self._skip_whitespace()
        if self.text[self.pos] == "}":
            self.pos += 1
            return
        while True:
            self._skip_whitespace()
            key_start = self.pos
            key = _reference_decoded(self._string())
            self._skip_whitespace()
            self.pos += 1  # the ':'
            self._skip_whitespace()
            # The key is part of the span, so that the underline says which key is meant.
            self.value(f"{pointer}.{key}" if pointer else key, key_start)
            self._skip_whitespace()
            if self.text[self.pos] == ",":
                self.pos += 1
                continue
            self.pos += 1  # the '}'
            return

    def _array(self, pointer: str) -> None:
        self.pos += 1
        self._skip_whitespace()
        if self.text[self.pos] == "]":
            self.pos += 1
            return
        index = 0
        while True:
            self._skip_whitespace()
            self.value(f"{pointer}[{index}]")
            index += 1
            self._skip_whitespace()
            if self.text[self.pos] == ",":
                self.pos += 1
                continue
            self.pos += 1  # the ']'
            return

    def _string(self) -> str:
        self.pos += 1  # the opening quote
        start = self.pos
        while self.text[self.pos] != '"':
            # A backslash consumes whatever follows it, so an escaped quote does not end the
            # string. What comes back is the raw source text, because the offsets have to
            # stay offsets into it; a key is decoded by the caller, which builds a pointer
            # out of it rather than a span.
            self.pos += 2 if self.text[self.pos] == "\\" else 1
        text = self.text[start : self.pos]
        self.pos += 1  # the closing quote
        return text

    def _literal(self) -> None:
        """A number, ``true``, ``false`` or ``null``: everything up to what can follow one.

        The end of the text ends it too. Inside an object or an array a literal is always
        followed by a comma or a bracket, but a document that *is* a literal - ``7`` is legal
        json, if not a legal description - has nothing after it, and walking off the end took
        the whole server down with it.
        """
        while self.pos < len(self.text) and self.text[self.pos] not in _REFERENCE_LITERAL_END:
            self.pos += 1

    def _skip_whitespace(self) -> None:
        while self.pos < len(self.text) and self.text[self.pos] in _REFERENCE_WHITESPACE:
            self.pos += 1


class _ReferenceScan:
    """What ``Document`` recorded of a text when it walked it: its ``__init__``, verbatim but for
    its names and for its comments, which the module keeps.

    A class, as ``Document`` is, so that the two are called alike: whether a document is too deep
    for the scan depends on the frames above the scan too, and on python 3.14 a call through a
    class's ``__init__`` spends one frame of the recursion limit more than a call of a function
    does. A function in this one's place, with the walk the same in both, read some of the shapes
    below one level deeper than ``Document`` did.
    """

    def __init__(self, text: str) -> None:
        self.text = text
        self._line_starts = _reference_line_starts(text)
        try:
            self.data: Any = json.loads(text)
            scanner = _ReferenceScanner(text)
            scanner.value("")
        except (ValueError, RecursionError):
            self.data = None
            self._spans: dict[str, tuple[int, int]] = {}
            self._texts: dict[str, tuple[int, int]] = {}
            self._values: dict[str, tuple[int, int]] = {}
        else:
            self._spans = scanner.spans
            self._texts = scanner.texts
            self._values = scanner.values


def scanned_alike(text: str) -> None:
    """``Document(text)`` answers what the walk recorded: the same document, the same line index,
    and for every value it found the same place, key and quotes in or out.

    Read through what the callers read - ``span_of``, ``value_span_of``, ``raw_at``,
    ``text_range_of`` - but for two things compared as recorded: the pointers found, which no
    public answer lists, so that none is found that the walk did not find; and the line index,
    which ``position`` and ``pointer_at`` read, compared whole rather than at every offset.
    """
    document = Document(text)
    reference = _ReferenceScan(text)
    # repr rather than ==, which a NaN fails against itself and which takes 1 for 1.0 and True.
    assert repr(document.data) == repr(reference.data)
    assert document._line_starts == reference._line_starts
    assert document._spans.keys() == reference._spans.keys()
    assert document._values.keys() == reference._values.keys()
    assert document._texts.keys() == reference._texts.keys()
    for pointer, span in reference._spans.items():
        assert document.span_of(pointer) == span
        start, end = reference._values[pointer]
        assert document.value_span_of(pointer) == (start, end)
        assert document.raw_at(pointer) == text[start:end]
        inner = reference._texts.get(pointer)
        assert document.text_range_of(pointer) == (
            None
            if inner is None
            else {"start": document.position(inner[0]), "end": document.position(inner[1])}
        )


def deepest(reads: Callable[[str], bool], nested: Callable[[int], str]) -> int:
    """The deepest of ``nested``'s documents ``reads`` reads, between 1 and 2,000 levels: each
    level costs the scan stack, and from some depth on it gives up.

    Searched with this thread's trace function set aside, as a reader's interpreter runs: a
    traced call spends stack of its own, and not alike for the scan and the walk, which make
    different calls. Under coverage's tracer - this suite's, on python 3.12 and 3.13, which
    trace with ``sys.settrace``; 3.14 records lines through ``sys.monitoring`` instead - the
    scan gave up one level before the walk on every shape, where untraced the two agree (CI's
    ubuntu and windows runners on 3.12 and 3.13, and the ``ddd:dev`` image's 3.12.14 traced
    and not)."""
    tracer = sys.gettrace()
    sys.settrace(None)
    try:
        low, high = 1, 2_000
        while low < high:
            middle = (low + high + 1) // 2
            if reads(nested(middle)):
                low = middle
            else:
                high = middle - 1
        return low
    finally:
        sys.settrace(tracer)


def lower(frames: int, reads: Callable[[str], bool]) -> Callable[[str], bool]:
    """``reads``, called ``frames`` frames further down the stack than it would be."""
    for _ in range(frames):
        reads = partial(_called, reads)
    return reads


def _called(reads: Callable[[str], bool], text: str) -> bool:
    return reads(text)


class TestTheScanAnswersAsTheWalkDid:
    """``Document`` finds where each value sits with regular expressions, matched at a position,
    where it once walked the text a character at a time; every answer is the walk's, compared
    here with the walk itself (``_ReferenceScan``)."""

    @pytest.mark.parametrize(
        "path",
        sorted(EXAMPLES.rglob("*.json")),
        ids=lambda path: path.relative_to(EXAMPLES).as_posix(),
    )
    def test_every_example(self, path: Path) -> None:
        scanned_alike(path.read_text(encoding="utf-8-sig"))

    def test_every_file_of_a_generated_project(self, tmp_path: Path) -> None:
        """Its project description, its units file and its ten components, at three hundred
        declarations: half the outputs without an id, and half the places of readers taken by
        outputs nobody reads."""
        generate(tmp_path / "p", 300, "many", missing_ids=0.5, unread=0.5)
        files = sorted((tmp_path / "p").rglob("*.json"))
        assert len(files) == 12
        for path in files:
            scanned_alike(path.read_text(encoding="utf-8"))

    @pytest.mark.parametrize(
        "text",
        [
            # An escaped quote mid-string; an escaped backslash right before a closing quote, in
            # a value and in a key; an escaped backslash and then an escaped quote.
            r'{"a": "say \" here", "b": "ends in \\", "c\\": "\\", "d": "\\\"", "e": 1}',
            # \u escapes, in keys and values, a surrogate pair among them, and text outside
            # ascii and outside the basic plane written as itself.
            '{"na\\u006de": "\\u00b0C", "°C": "😀 \\ud83d\\ude00",\n "\\u00e9t\\u00e9": ["é", 1]}',
            # Empty objects and arrays, with and without whitespace inside them.
            '{"a": {}, "b": [], "c": [{}, []], "d": { }, "e": [\n ], "f": {"g": [[], {}]}}',
            "{}",
            "[]",
            # A literal that ends the text, alone or after whitespace, and literals of each kind.
            "7",
            " -12.5e+3",
            "true",
            "null\n",
            "[NaN, Infinity, -Infinity, 1E5, -0.0, 0, true, false, null]",
            # Whitespace of all four kinds, everywhere json allows it.
            ' \t\n\r{ \t\n\r"a" \t\n\r: \t\n\r1 \t\n\r, \t\n\r"b" \t\n\r: \t\n\r'
            '[ \t\n\r2 \t\n\r, \t\n\r"x" \t\n\r] \t\n\r} \t\n\r',
            # Line ends of two characters.
            '{\r\n  "a": 1,\r\n  "b": [\r\n    "x",\r\n    true\r\n  ]\r\n}\r\n',
            # Strings holding what ends a literal, an object or an array, and a key spelled twice.
            '{"a": "{[,:]} ", "b": "\\"}{\\"", "a": {"c": "\\/\\b\\f\\n\\r\\t"}}',
            # Text that does not parse.
            "",
            "{not json",
            '{"a": 1,}',
            "[1, 2",
            "\ufeff{}",
            # Nested past the scan's depth, though not past the parse's.
            "[" * 1_000 + "]" * 1_000,
        ],
        ids=[
            "escaped-quotes-and-backslashes",
            "u-escapes-and-text-outside-ascii",
            "empty-objects-and-arrays",
            "an-empty-object",
            "an-empty-array",
            "a-number-alone",
            "a-number-after-whitespace",
            "true-alone",
            "null-and-a-line-end",
            "literals-of-each-kind",
            "whitespace-of-all-four-kinds",
            "crlf",
            "structure-inside-strings-and-a-key-twice",
            "empty",
            "not-json",
            "a-trailing-comma",
            "unclosed",
            "a-byte-order-mark",
            "nested-past-the-scan",
        ],
    )
    def test_a_written_case(self, text: str) -> None:
        scanned_alike(text)

    def test_a_document_nested_past_the_scan_reads_as_nothing_though_it_parses(self) -> None:
        """The case above, said outright: the parse reads it, the scan gives up, and the
        ``RecursionError`` is caught, so there is no data and no span, as for text that does
        not parse."""
        text = "[" * 1_000 + "]" * 1_000
        assert json.loads(text) is not None
        document = Document(text)
        assert document.data is None
        assert document.span_of("") is None

    @pytest.mark.parametrize(
        "nested",
        [
            lambda depth: "[" * depth + "]" * depth,
            lambda depth: "[" * depth + "1" + "]" * depth,
            lambda depth: "[" * depth + '"s"' + "]" * depth,
            lambda depth: '{"a":' * depth + "{}" + "}" * depth,
            lambda depth: '{"a": ' * depth + "true" + " }" * depth,
            lambda depth: '{"\\u0061":' * depth + "{}" + "}" * depth,
            lambda depth: '[{"a":' * depth + "[]" + "}]" * depth,
        ],
        ids=[
            "arrays",
            "arrays-round-a-number",
            "arrays-round-a-string",
            "objects",
            "objects-round-a-literal",
            "objects-under-an-escaped-key",
            "objects-in-arrays",
        ],
    )
    @pytest.mark.parametrize("frames", [0, 1, 2, 3])
    def test_the_scan_gives_up_at_the_depth_the_walk_gave_up_at(
        self, nested: Callable[[int], str], frames: int
    ) -> None:
        """Where a document is nested too deeply depends on how much stack each level costs, and
        that is unchanged: the deepest document of each shape the scan reads is the deepest the
        walk read, each called from the same depth of the stack. From four depths in a row: a
        frame spent more or less at the deepest point moves that limit at one depth of every
        two for a shape whose levels cost two frames, and at one of every four for one whose
        levels cost four.

        The walk's own limit is asserted to lie strictly inside the search's bounds first: a
        walk that read every depth up to the last bound, or none past the first, would answer
        the bound itself, and the two would agree without either having given up anywhere."""
        walked = deepest(lower(frames, lambda text: bool(_ReferenceScan(text)._spans)), nested)
        assert 1 < walked < 2_000
        assert (
            deepest(lower(frames, lambda text: Document(text).span_of("") is not None), nested)
            == walked
        )


class TestServer:
    """The loop, which is the only part a test can reach only through the protocol."""

    def test_a_document_opened_under_the_clients_spelling_of_its_uri_is_analysed(
        self, tmp_path: Path
    ) -> None:
        """The uri a client sends is not the one ``Path.as_uri()`` writes.

        VS Code on Windows opens ``file:///c%3A/...``; read as a relative path, the server
        analysed a file that does not exist and then exited trying to publish under it. The
        answer has to be diagnostics for the real file, under a uri naming that file, and a
        server that is still running afterwards.
        """
        write_tree(
            tmp_path,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("input", "X")),
            },
        )
        path = tmp_path / "a.ddd.json"
        # The client's spelling: the drive lower-cased and its colon escaped. Without a drive
        # (posix) there is nothing to respell and the uri is the server's own.
        spelled = re.sub(
            r"^file:///([A-Za-z]):", lambda m: f"file:///{m.group(1).lower()}%3A", path.as_uri()
        )
        stream = framed(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"rootUri": spelled.rsplit("/", 1)[0]},
            },
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didOpen",
                "params": {
                    "textDocument": {
                        "uri": spelled,
                        "languageId": "json",
                        "version": 1,
                        "text": path.read_text(encoding="utf-8"),
                    }
                },
            },
            {"jsonrpc": "2.0", "id": 2, "method": "shutdown"},
            {"jsonrpc": "2.0", "method": "exit"},
        )
        writer = io.BytesIO()
        assert Server(stream, writer, root=tmp_path).run() == 0
        # Compared as strings, which is how a client matches a publication to what it shows:
        # resolving both sides first is what let the spelling defect sit green for a year.
        assert [finding["code"] for finding in published(writer)[spelled]] == ["missing-producer"]
        assert list(published(writer)) == [spelled]

    def handshake(self, tmp_path: Path) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"workspaceFolders": [{"uri": tmp_path.as_uri()}]},
        }

    def opened(self, path: Path) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {"textDocument": {"uri": path.as_uri()}},
        }

    def test_opening_a_file_of_another_project_keeps_this_ones_findings(
        self, tmp_path: Path
    ) -> None:
        """A refresh withdraws what its own run reported on, and nothing else.

        With no record, a run covers the document and the project above it. The other
        project's file is outside it, so its empty answer is not "fixed": the run never looked.
        One refresh per document, driven message by message, so that no later batching of
        refreshes can make this pass without the rule.
        """
        write_tree(
            tmp_path,
            {
                "one/p.ddd.json": project("One", "a.ddd.json"),
                "one/a.ddd.json": component("A", declare("input", "X")),
                "two/p.ddd.json": project("Two", "b.ddd.json"),
                "two/b.ddd.json": component("B", declare("input", "Y")),
            },
        )
        a, b = tmp_path / "one" / "a.ddd.json", tmp_path / "two" / "b.ddd.json"
        writer = io.BytesIO()
        server = Server(io.BytesIO(), writer, root=tmp_path)
        assert server._handle(self.handshake(tmp_path))
        assert server._handle(self.opened(a))
        assert server._handle(self.opened(b))
        final = published(writer)
        assert [d["code"] for d in final[b.as_uri()]] == ["missing-producer"]
        assert [d["code"] for d in final[a.as_uri()]] == ["missing-producer"], (
            "a's error was withdrawn"
        )
        # What was kept is still withdrawable: fixing a and saving it empties its list.
        write_tree(
            tmp_path,
            {
                "one/p.ddd.json": project("One", "a.ddd.json", "c.ddd.json"),
                "one/c.ddd.json": component("C", declare("output", "X")),
            },
        )
        writer = io.BytesIO()
        server.writer = writer
        saved = {"textDocument": {"uri": a.as_uri()}}
        assert server._handle({"jsonrpc": "2.0", "method": "textDocument/didSave", "params": saved})
        assert published(writer)[a.as_uri()] == []

    def test_the_demos_sub_project_component_shows_what_ddd_check_shows(
        self, tmp_path: Path
    ) -> None:
        """The outermost description that includes a document answers for it.

        ``subsystems/logging`` is a sub-project of the demo, and its component reads values the
        demo's other components produce. Checked under the sub-project alone, the nearest
        description, a clean tree showed errors in the component for values that
        the demo's other components do write; ``ddd check`` of the top project is clean.
        """
        demo = tmp_path / "demo"
        shutil.copytree(EXAMPLES / "demo", demo)
        logger = demo / "subsystems" / "logging" / "event_logger.ddd.json"
        writer = io.BytesIO()
        server = Server(io.BytesIO(), writer, root=demo)
        assert server._handle(self.handshake(demo))
        assert server._handle(self.opened(logger))
        assert main(["check", str(demo / "demo.ddd.json")]) == EXIT_OK  # the tree is clean
        errors = [
            d["code"] for d in published(writer).get(logger.as_uri(), []) if d["severity"] == 1
        ]
        assert errors == [], f"a clean project shows {errors}"

    def test_a_deleted_file_is_withdrawn_once_and_not_refreshed(self, tmp_path: Path) -> None:
        """A pull that changes one file and deletes another, with nothing open.

        The deleted file's findings leave the screen with one empty list, and no run is
        started from its path: that run is what reported a file that is not there.
        """
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("input", "X")),
                "b.ddd.json": component("B", declare("input", "Y")),
            },
        )
        a, b = tmp_path / "a.ddd.json", tmp_path / "b.ddd.json"
        writer = io.BytesIO()
        server = Server(io.BytesIO(), writer, root=tmp_path)
        assert server._handle(self.handshake(tmp_path))
        assert server._handle(self.opened(a))
        assert [d["code"] for d in published(writer)[b.as_uri()]] == ["missing-producer"]
        server._handle(
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didClose",
                "params": {"textDocument": {"uri": a.as_uri()}},
            }
        )
        b.unlink()
        writer = io.BytesIO()
        server.writer = writer
        assert server._handle(
            {
                "jsonrpc": "2.0",
                "method": "workspace/didChangeWatchedFiles",
                "params": {"changes": [{"uri": b.as_uri(), "type": 3}]},
            }
        )
        assert published(writer) == {b.as_uri(): []}
        # Once: a later refresh does not empty it again.
        server._handle(self.opened(a))
        withdrawals = [
            m
            for m in sent(writer)
            if m.get("method") == "textDocument/publishDiagnostics"
            and m["params"]["uri"] == b.as_uri()
        ]
        assert [m["params"]["diagnostics"] for m in withdrawals] == [[]]

    def test_an_open_document_not_on_disk_keeps_its_findings(self, tmp_path: Path) -> None:
        """A new file, not yet saved, is checked from its buffer and is not a deleted one."""
        draft = tmp_path / "new.ddd.json"
        writer = io.BytesIO()
        server = Server(io.BytesIO(), writer, root=tmp_path)
        assert server._handle(self.handshake(tmp_path))
        message = self.opened(draft)
        message["params"]["textDocument"]["text"] = json.dumps(
            component("N", declare("input", "X"))
        )
        assert server._handle(message)
        assert not draft.exists()
        kept = [
            m["params"]["diagnostics"]
            for m in sent(writer)
            if m.get("method") == "textDocument/publishDiagnostics"
            and m["params"]["uri"] == draft.as_uri()
        ]
        assert kept
        assert kept[-1], "findings of an open, unsaved document were emptied"

    def test_opening_the_project_file_does_not_withdraw_the_project_wide_findings(
        self, tmp_path: Path
    ) -> None:
        """A squiggle that disappears when the reader opens another file is worse than none.

        The component was reached through the project above it and reported everything; the
        project file, reached as a root, used to be read under the policy for a lone
        component, so the second refresh republished the same files without the two checks the
        project exists to answer.
        """
        tree = tmp_path / "inconsistent"
        shutil.copytree(INCONSISTENT.parent, tree)
        stream = framed(
            self.handshake(tree),
            self.opened(tree / "component_c.ddd.json"),
            self.opened(tree / "project.ddd.json"),
            {"jsonrpc": "2.0", "id": 2, "method": "shutdown"},
            {"jsonrpc": "2.0", "method": "exit"},
        )
        writer = io.BytesIO()
        assert Server(stream, writer, root=tree).run() == 0
        # The last word on each file, which is what stays on screen.
        final = published(writer)
        drawn = {
            name: {entry["code"] for entry in final[(tree / name).as_uri()]}
            for name in ("component_a.ddd.json", "component_c.ddd.json")
        }
        assert "missing-producer" in drawn["component_c.ddd.json"]
        assert "unused-output" in drawn["component_a.ddd.json"]

    def test_opening_a_document_deeper_than_the_scanner_walks_does_not_end_the_server(
        self, tmp_path: Path
    ) -> None:
        """A document python can read and the span scanner cannot used to end the server on
        the first didOpen, before any publication and before the shutdown answer."""
        deep = tmp_path / "deep.ddd.json"
        deep.write_text("[" * 600 + "]" * 600, encoding="utf-8")
        stream = framed(
            self.handshake(tmp_path),
            self.opened(deep),
            {"jsonrpc": "2.0", "id": 2, "method": "shutdown"},
            {"jsonrpc": "2.0", "method": "exit"},
        )
        writer = io.BytesIO()
        assert Server(stream, writer, root=tmp_path).run() == 0
        assert [entry["code"] for entry in published(writer)[deep.as_uri()]] == ["file-kind"]

    def test_a_request_without_params_is_refused_rather_than_fatal(self, tmp_path: Path) -> None:
        """One badly shaped message is not the end of the conversation, framing or not.

        The loop already survives a body that is not a request. A body that *is* one, framed
        correctly, and simply missing the ``params`` an editor always sends used to raise a
        KeyError straight out of the loop - so a client with one bug took every DDD finding
        off the screen until somebody restarted the server.
        """
        writer = io.BytesIO()
        stream = session(
            {"jsonrpc": "2.0", "id": 7, "method": "textDocument/hover"},
            {"jsonrpc": "2.0", "id": 8, "method": "shutdown"},
            {"jsonrpc": "2.0", "method": "exit"},
        )
        assert Server(stream, writer, root=tmp_path).run() == 0
        answers = {message["id"]: message for message in answered(writer) if "id" in message}
        assert answers[7]["error"]["code"] == INVALID_PARAMS
        # And the conversation went on: the request after it was answered normally.
        assert answers[8]["result"] is None

    def test_a_notification_without_params_is_survived_too(self, tmp_path: Path) -> None:
        """A notification gets no reply by definition, so the only thing to prove is the loop."""
        writer = io.BytesIO()
        stream = session(
            {"jsonrpc": "2.0", "method": "textDocument/didOpen"},
            {"jsonrpc": "2.0", "id": 9, "method": "shutdown"},
            {"jsonrpc": "2.0", "method": "exit"},
        )
        assert Server(stream, writer, root=tmp_path).run() == 0
        assert any(message.get("id") == 9 for message in answered(writer))

    def test_repeating_a_request_does_no_more_reading_than_asking_once(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A hover is a keypress, and it used to rescan the build tree and reload every project.

        Worse, it did so several times over: the external type lookup and the resolution each
        walked the projects from scratch. Nothing on disk can have changed between two hovers -
        the server reads files at open and at save and says so in its capabilities - so the
        second one is entitled to the first one's answer.
        """
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "Speed", "uint16")),
            },
        )
        build_record(tmp_path, tmp_path / "p.ddd.json")
        document = tmp_path / "a.ddd.json"
        pointer = "component.interface[0].definition.name"
        position = Document(document.read_text(encoding="utf-8")).range_of(pointer)["start"]
        asked = self.navigation_request("textDocument/hover", document, position)

        loads: list[Path] = []
        original = navigation.load_workspace

        def counted(path: Path, bag: Any) -> Any:
            loads.append(path)
            return original(path, bag)

        monkeypatch.setattr(navigation, "load_workspace", counted)

        def reads(*requests: dict[str, Any]) -> int:
            loads.clear()
            Server(session(*requests), io.BytesIO(), root=tmp_path).run()
            return len(loads)

        once = reads(asked)
        assert once > 0
        assert reads(asked, asked) == once

    def test_two_documents_share_one_walk_of_the_build_tree(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The records are the project's, not the document's: found once, used for both files."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Shared", "uint16")),
                "b.ddd.json": component("B", declare("input", "Shared", "uint16")),
            },
        )
        build_record(tmp_path, tmp_path / "p.ddd.json")
        walks: list[Path] = []
        original = server_module.build_files

        def counted(root: Path, configured: Any = ()) -> Any:
            walks.append(root)
            return original(root, configured)

        monkeypatch.setattr(server_module, "build_files", counted)
        asked = [
            self.navigation_request(
                "textDocument/hover",
                tmp_path / name,
                Document((tmp_path / name).read_text(encoding="utf-8")).range_of(
                    "component.interface[0].definition.name"
                )["start"],
            )
            for name in ("a.ddd.json", "b.ddd.json")
        ]
        Server(session(*asked), io.BytesIO(), root=tmp_path).run()
        assert len(walks) == 1

    def test_a_save_picks_up_what_changed_on_disk(self, tmp_path: Path) -> None:
        """The other half of caching an answer: the moment it has to be thrown away."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("input", "Shared")),
            },
        )
        # missing-id is silenced the way the build itself would silence any check that is
        # noise for this project: through the record, not by giving the fixture an identity
        # that has nothing to do with what this test demonstrates.
        build_record(tmp_path, tmp_path / "p.ddd.json", severity=["missing-id=ignore"])
        writer = io.BytesIO()
        server = Server(io.BytesIO(), writer, root=tmp_path)
        server.refresh(tmp_path / "a.ddd.json")
        a_uri = (tmp_path / "a.ddd.json").as_uri()
        assert published(writer)[a_uri][0]["code"] == "missing-producer"

        write_tree(tmp_path, {"a.ddd.json": component("A", declare("local", "Shared"))})
        writer = io.BytesIO()
        server.writer = writer
        server.refresh(tmp_path / "a.ddd.json")
        assert published(writer)[a_uri] == []

    def test_it_announces_what_it_can_do(self, tmp_path: Path) -> None:
        writer = io.BytesIO()
        Server(framed(self.handshake(tmp_path)), writer, root=tmp_path).run()
        (answer,) = sent(writer)
        assert answer["result"]["capabilities"]["textDocumentSync"]["save"] is True
        assert answer["result"]["serverInfo"]["name"] == "ddd"

    def test_opening_a_file_publishes_the_findings_of_its_project(self, tmp_path: Path) -> None:
        build_record(tmp_path, INCONSISTENT)
        writer = io.BytesIO()
        opened = INCONSISTENT.parent / "component_b.ddd.json"
        Server(session(self.opened(opened)), writer, root=tmp_path).run()
        drawn = published(writer)
        beside = INCONSISTENT.parent / "component_c.ddd.json"
        assert drawn[opened.as_uri()][0]["code"] == "multiple-producers"
        # The file that was not opened is published too, which is the point.
        assert drawn[beside.as_uri()][0]["code"] == "definition-mismatch"

    def test_a_configured_build_directory_is_where_the_records_are_looked_for(
        self, tmp_path: Path
    ) -> None:
        """``ddd.buildDirectories`` is the extension's only setting; this is what it buys.

        The record sits where none of the usual names would be searched - the patterns are
        ``build``, ``out`` and ``cmake-build-*`` directly under the workspace folder - and the
        project file sits beside the component rather than above it, so no walk upwards finds
        it either: the configured directory is the only route from the open document to the
        project. The control below is the same open without it, where the component is checked
        on its own and ``missing-producer`` is one of the checks a standalone file is spared.
        """
        write_tree(
            tmp_path,
            {
                "proj/p.ddd.json": project("P", "../src/a.ddd.json"),
                "src/a.ddd.json": component("A", declare("input", "Shared")),
            },
        )
        elsewhere = tmp_path / "elsewhere"
        build_record(elsewhere, tmp_path / "proj" / "p.ddd.json", severity=["missing-id=ignore"])
        opened = tmp_path / "src" / "a.ddd.json"

        writer = io.BytesIO()
        Server(
            session(self.opened(opened)),
            writer,
            root=tmp_path,
            build_directories=[elsewhere],
        ).run()
        assert [entry["code"] for entry in published(writer)[opened.as_uri()]] == [
            "missing-producer"
        ]

        bare = io.BytesIO()
        Server(session(self.opened(opened)), bare, root=tmp_path).run()
        assert not published(bare).get(opened.as_uri())

    def test_the_command_hands_its_build_directories_to_the_server(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The other end of the same setting: ``ddd lsp -b DIR``, as the extension spawns it.

        Fed a real document rather than an empty stream, which returns from the loop before
        anything is discovered at all - so the argument is followed from the command line
        through ``serve`` to the publication a client would draw.
        """
        from ddd.cli import EXIT_OK, main

        class Stream:
            def __init__(self, buffer: io.BytesIO) -> None:
                self.buffer = buffer

        write_tree(
            tmp_path,
            {
                "proj/p.ddd.json": project("P", "../src/a.ddd.json"),
                "src/a.ddd.json": component("A", declare("input", "Shared")),
            },
        )
        elsewhere = tmp_path / "elsewhere"
        build_record(elsewhere, tmp_path / "proj" / "p.ddd.json", severity=["missing-id=ignore"])
        opened = tmp_path / "src" / "a.ddd.json"
        wire = io.BytesIO()
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("sys.stdin", Stream(session(self.opened(opened))))
        monkeypatch.setattr("sys.stdout", Stream(wire))
        assert main(["lsp", "-b", str(elsewhere)]) == EXIT_OK
        assert [entry["code"] for entry in published(wire)[opened.as_uri()]] == ["missing-producer"]

    def logged(self, stream: io.BytesIO) -> list[str]:
        return [
            message["params"]["message"]
            for message in sent(stream)
            if message.get("method") == "window/logMessage"
        ]

    def test_finding_no_build_record_is_said_rather_than_left_to_be_guessed(
        self, tmp_path: Path
    ) -> None:
        """Silence is the failure mode: a file no build claims is still checked, but only for
        what one file settles, so a missing record looks exactly like a clean project."""
        write_tree(tmp_path, {"a.ddd.json": component("A", declare("input", "X"))})
        writer = io.BytesIO()
        Server(io.BytesIO(), writer, root=tmp_path).refresh(tmp_path / "a.ddd.json")
        (said,) = self.logged(writer)
        assert "no ddd-build.json found" in said

    def test_a_record_naming_a_project_that_is_not_there_is_called_out(
        self, tmp_path: Path
    ) -> None:
        """How this goes wrong in practice: a record written inside a container names a path
        that exists only in the container, and is then found, read and quietly of no use."""
        build_record(tmp_path, Path("/work/build/somewhere/firmware.ddd.json"))
        write_tree(tmp_path, {"a.ddd.json": component("A", declare("input", "X"))})
        writer = io.BytesIO()
        Server(io.BytesIO(), writer, root=tmp_path).refresh(tmp_path / "a.ddd.json")
        (said,) = self.logged(writer)
        assert "no such file" in said
        # And nothing is published against the phantom: a finding on a file nobody can open
        # says the record is stale in the one place a reader cannot act on it.
        assert not any(published(writer).values())

    def test_a_usable_record_is_named_once_rather_than_every_save(self, tmp_path: Path) -> None:
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X")),
            },
        )
        build_record(tmp_path, tmp_path / "p.ddd.json")
        writer = io.BytesIO()
        server = Server(io.BytesIO(), writer, root=tmp_path)
        server.refresh(tmp_path / "a.ddd.json")
        server.refresh(tmp_path / "a.ddd.json")
        said = self.logged(writer)
        assert len(said) == 1
        assert "firmware.elf" in said[0]

    def test_a_finding_that_is_fixed_is_withdrawn(self, tmp_path: Path) -> None:
        """An empty list is how the protocol says so; leaving the file out leaves the squiggle."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("input", "Shared")),
                "b.ddd.json": component("B", declare("input", "Shared")),
            },
        )
        # missing-id is silenced through the record, the same way the build itself would
        # silence any check that is noise for this project, not by giving the fixture an
        # identity that has nothing to do with what this test demonstrates.
        build_record(tmp_path, tmp_path / "p.ddd.json", severity=["missing-id=ignore"])
        writer = io.BytesIO()
        server = Server(io.BytesIO(), writer, root=tmp_path)
        server.refresh(tmp_path / "a.ddd.json")
        assert (
            published(writer)[(tmp_path / "a.ddd.json").as_uri()][0]["code"] == "missing-producer"
        )

        # Somebody produces it now, so the project is clean and the squiggle has to go.
        write_tree(tmp_path, {"a.ddd.json": component("A", declare("output", "Shared"))})
        writer = io.BytesIO()
        server.writer = writer
        server.refresh(tmp_path / "a.ddd.json")
        assert published(writer) == {
            (tmp_path / "a.ddd.json").as_uri(): [],
            (tmp_path / "b.ddd.json").as_uri(): [],
        }

    def test_saving_refreshes_as_opening_does(self, tmp_path: Path) -> None:
        """The same publication an open gives, so "refreshes" means what the name says.

        Asserted on what was published rather than on something having been sent: the server
        logs while it refreshes, and a log line satisfies "it answered" on a save that
        publishes nothing at all.
        """
        build_record(tmp_path, INCONSISTENT)
        writer = io.BytesIO()
        saved_file = INCONSISTENT.parent / "component_b.ddd.json"
        saved = dict(self.opened(saved_file), method="textDocument/didSave")
        Server(session(saved), writer, root=tmp_path).run()
        drawn = published(writer)
        assert [finding["code"] for finding in drawn[saved_file.as_uri()]] == ["multiple-producers"]
        beside = INCONSISTENT.parent / "component_c.ddd.json"
        assert drawn[beside.as_uri()][0]["code"] == "definition-mismatch"

    def test_shutdown_is_answered_and_exit_ends_the_loop(self, tmp_path: Path) -> None:
        writer = io.BytesIO()
        stream = session(
            {"jsonrpc": "2.0", "id": 4, "method": "shutdown"},
            {"jsonrpc": "2.0", "method": "exit"},
            {"jsonrpc": "2.0", "id": 5, "method": "initialize", "params": {}},
        )
        assert Server(stream, writer, root=tmp_path).run() == 0
        # Only the shutdown was answered: nothing after exit is read.
        assert [message["id"] for message in answered(writer)] == [4]

    def navigation_request(self, method: str, path: Path, position: dict[str, int]) -> dict:
        return {
            "jsonrpc": "2.0",
            "id": 7,
            "method": method,
            "params": {"textDocument": {"uri": path.as_uri()}, "position": position},
        }

    def shared_workspace(self, tmp_path: Path) -> Path:
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Shared")),
                "b.ddd.json": component("B", declare("input", "Shared")),
            },
        )
        build_record(tmp_path, tmp_path / "p.ddd.json")
        return tmp_path / "b.ddd.json"

    def test_it_offers_to_navigate(self, tmp_path: Path) -> None:
        writer = io.BytesIO()
        Server(framed(self.handshake(tmp_path)), writer, root=tmp_path).run()
        capabilities = sent(writer)[0]["result"]["capabilities"]
        assert capabilities["definitionProvider"] is True
        assert capabilities["referencesProvider"] is True
        assert capabilities["hoverProvider"] is True

    def test_definition_answers_with_the_producing_declaration(self, tmp_path: Path) -> None:
        consumer = self.shared_workspace(tmp_path)
        position = Document(consumer.read_text(encoding="utf-8")).range_of(
            "component.interface[0].definition.name"
        )["start"]
        writer = io.BytesIO()
        Server(
            session(self.navigation_request("textDocument/definition", consumer, position)),
            writer,
            root=tmp_path,
        ).run()
        (answer,) = answered(writer)
        (found,) = answer["result"]
        assert found["uri"] == (tmp_path / "a.ddd.json").as_uri()

    def test_references_answer_with_every_declaration(self, tmp_path: Path) -> None:
        consumer = self.shared_workspace(tmp_path)
        position = Document(consumer.read_text(encoding="utf-8")).range_of(
            "component.interface[0].definition.name"
        )["start"]
        writer = io.BytesIO()
        Server(
            session(self.navigation_request("textDocument/references", consumer, position)),
            writer,
            root=tmp_path,
        ).run()
        (answer,) = answered(writer)
        assert {found["uri"] for found in answer["result"]} == {
            (tmp_path / name).as_uri() for name in ("a.ddd.json", "b.ddd.json")
        }

    def hovered(self, tmp_path: Path, path: Path, pointer: str) -> Any:
        position = Document(path.read_text(encoding="utf-8")).range_of(pointer)["start"]
        writer = io.BytesIO()
        Server(
            session(self.navigation_request("textDocument/hover", path, position)),
            writer,
            root=tmp_path,
        ).run()
        (answer,) = answered(writer)
        return answer["result"]

    def test_hover_answers_with_markdown(self, tmp_path: Path) -> None:
        consumer = self.shared_workspace(tmp_path)
        result = self.hovered(tmp_path, consumer, "component.interface[0].definition.name")
        assert result["contents"]["kind"] == "markdown"
        assert "**Shared**" in result["contents"]["value"]
        # Written by A even though the hover happened in B, which is the point of resolving.
        assert "Written by **A**" in result["contents"]["value"]

    def test_hover_on_something_that_is_not_a_variable_says_nothing(self, tmp_path: Path) -> None:
        consumer = self.shared_workspace(tmp_path)
        assert self.hovered(tmp_path, consumer, "component.name") is None

    def test_hover_works_from_any_key_of_a_declaration(self, tmp_path: Path) -> None:
        """Not only from the name, which is what asking on a datatype used to give: nothing."""
        consumer = self.shared_workspace(tmp_path)
        result = self.hovered(tmp_path, consumer, "component.interface[0].definition.datatype")
        assert "**Shared**" in result["contents"]["value"]

    def test_hover_on_a_reference_to_nothing_says_nothing(self, tmp_path: Path) -> None:
        """The cursor is on a name, but no component declares it - the very case the
        unknown-reference finding is about, so the hover has nothing to add to it."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    declare("output", "Curve", kind="curve", datatype="uint8", axis="Absent"),
                ),
            },
        )
        build_record(tmp_path, tmp_path / "p.ddd.json")
        result = self.hovered(
            tmp_path, tmp_path / "a.ddd.json", "component.interface[0].definition.axis"
        )
        assert result is None

    def test_hover_with_no_project_to_resolve_says_nothing(self, tmp_path: Path) -> None:
        """No build record and a file that will not load on its own."""
        lonely = tmp_path / "gone.ddd.json"
        writer = io.BytesIO()
        Server(
            session(
                self.navigation_request("textDocument/hover", lonely, {"line": 0, "character": 0})
            ),
            writer,
            root=tmp_path,
        ).run()
        (answer,) = answered(writer)
        assert answer["result"] is None

    def test_it_offers_to_rename(self, tmp_path: Path) -> None:
        writer = io.BytesIO()
        Server(framed(self.handshake(tmp_path)), writer, root=tmp_path).run()
        capabilities = sent(writer)[0]["result"]["capabilities"]
        assert capabilities["renameProvider"] == {"prepareProvider": True}

    def rename_request(self, path: Path, pointer: str, name: str) -> dict[str, Any]:
        position = Document(path.read_text(encoding="utf-8")).range_of(pointer)["start"]
        return {
            "jsonrpc": "2.0",
            "id": 11,
            "method": "textDocument/rename",
            "params": {
                "textDocument": {"uri": path.as_uri()},
                "position": position,
                "newName": name,
            },
        }

    def test_rename_answers_with_edits_in_every_file(self, tmp_path: Path) -> None:
        consumer = self.shared_workspace(tmp_path)
        writer = io.BytesIO()
        Server(
            session(
                self.rename_request(consumer, "component.interface[0].definition.name", "Renamed")
            ),
            writer,
            root=tmp_path,
        ).run()
        (answer,) = answered(writer)
        assert set(answer["result"]["changes"]) == {
            (tmp_path / name).as_uri() for name in ("a.ddd.json", "b.ddd.json")
        }

    def test_rename_to_an_unusable_name_is_refused_with_a_reason(self, tmp_path: Path) -> None:
        """An error rather than an empty edit: an empty edit looks like a rename that did
        nothing, where a refusal an editor can show tells the author what to type instead."""
        consumer = self.shared_workspace(tmp_path)
        writer = io.BytesIO()
        Server(
            session(self.rename_request(consumer, "component.interface[0].definition.name", "int")),
            writer,
            root=tmp_path,
        ).run()
        (answer,) = answered(writer)
        assert "reserved" in answer["error"]["message"]

    def half_read_workspace(self, tmp_path: Path) -> Path:
        """A project one file of which does not load, which is an ordinary mid-edit state."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json", "c.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed", "uint99", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed")),
                "c.ddd.json": component("C", declare("input", "Speed", unit="rpm")),
            },
        )
        build_record(tmp_path, tmp_path / "p.ddd.json")
        return tmp_path / "b.ddd.json"

    def test_a_rename_is_refused_while_a_file_of_the_project_did_not_load(
        self, tmp_path: Path
    ) -> None:
        """Indexed as if the dropped file had never declared anything, the rename rewrote the
        rest of the project around it and left the producer holding the old name - the
        half-renamed project the drift refusal already exists to prevent."""
        consumer = self.half_read_workspace(tmp_path)
        writer = io.BytesIO()
        Server(
            session(
                self.rename_request(consumer, "component.interface[0].definition.name", "Renamed")
            ),
            writer,
            root=tmp_path,
        ).run()
        (answer,) = answered(writer)
        assert answer["error"]["code"] == REQUEST_FAILED
        assert "a.ddd.json" in answer["error"]["message"]

    def quick_fix_request(self, path: Path) -> dict[str, Any]:
        """The client asking for the quick fixes at the unit of ``path``'s first declaration,
        sending no finding, as it asks at every move of the caret."""
        span = Document(path.read_text(encoding="utf-8")).range_of(
            "component.interface[0].definition.unit"
        )
        return {
            "jsonrpc": "2.0",
            "id": 13,
            "method": "textDocument/codeAction",
            "params": {
                "textDocument": {"uri": path.as_uri()},
                "range": span,
                "context": {"diagnostics": []},
            },
        }

    def test_no_quick_fix_is_offered_while_a_file_of_the_project_did_not_load(
        self, tmp_path: Path
    ) -> None:
        """The same hole seen through the lightbulb: it offered to remove the unit of 'Speed'
        as one no other declaration has, while the unloaded producer declares exactly that.

        Refused with an error, it was a failed request at every move of the caret, which is when
        a client asks, naming no file. None is offered instead, and the log says why."""
        self.half_read_workspace(tmp_path)
        writer = io.BytesIO()
        Server(
            session(self.quick_fix_request(tmp_path / "c.ddd.json")), writer, root=tmp_path
        ).run()
        said, answer = answered(writer)
        assert answer == response(13, [])
        assert said == notification("window/logMessage", {"type": 3, "message": WITHHELD})

    def half_read_server(self, tmp_path: Path) -> Server:
        """A server over :meth:`half_read_workspace`, driven message by message so that each
        save is a refresh of its own, with ``c.ddd.json`` open."""
        self.half_read_workspace(tmp_path)
        server = Server(io.BytesIO(), io.BytesIO(), root=tmp_path)
        assert server._handle(self.handshake(tmp_path))
        assert server._handle(self.opened(tmp_path / "c.ddd.json"))
        return server

    def asked_for_fixes(self, server: Server, path: Path) -> tuple[list[str], list[str]]:
        """What the log said for one quick-fix request at ``path``'s unit, and the titles of the
        fixes it offered."""
        writer = io.BytesIO()
        server.writer = writer
        assert server._handle(self.quick_fix_request(path))
        messages = sent(writer)
        (answer,) = [message for message in messages if message.get("id") == 13]
        logged = [
            message["params"]["message"]
            for message in messages
            if message.get("method") == "window/logMessage"
        ]
        return logged, reconciled(answer["result"])

    def saved(self, server: Server, path: Path) -> None:
        """The client saving ``path``, which refreshes."""
        saving = {"textDocument": {"uri": path.as_uri()}}
        assert server._handle(
            {"jsonrpc": "2.0", "method": "textDocument/didSave", "params": saving}
        )

    def producer_saved(self, server: Server, tmp_path: Path, datatype: str) -> None:
        """``a.ddd.json`` written with ``datatype`` for its producer and saved: ``uint99`` breaks
        it, ``uint16`` mends it."""
        producer = component("A", declare("output", "Speed", datatype, unit="rpm"))
        write_tree(tmp_path, {"a.ddd.json": producer})
        self.saved(server, tmp_path / "a.ddd.json")

    def test_why_no_quick_fix_is_offered_is_said_once_while_it_stands(self, tmp_path: Path) -> None:
        """Said at the first request the unread file empties, and again only once the project
        has been found read whole and is then found broken anew: at every request it is the
        flood the error answers were, and once a session would hide the second break."""
        server = self.half_read_server(tmp_path)
        elsewhere = tmp_path / "c.ddd.json"
        assert self.asked_for_fixes(server, elsewhere) == ([WITHHELD], [])
        assert self.asked_for_fixes(server, elsewhere) == ([], []), "said again while it stands"
        self.saved(server, elsewhere)  # a refresh that finds the project broken still
        assert self.asked_for_fixes(server, elsewhere) == ([], []), (
            "said again after a refresh that found it broken"
        )
        self.producer_saved(server, tmp_path, "uint16")
        assert self.asked_for_fixes(server, elsewhere) == (
            [],
            ["Apply this unit to 1 other declaration of 'Speed'"],
        )
        self.producer_saved(server, tmp_path, "uint99")
        assert self.asked_for_fixes(server, elsewhere) == ([WITHHELD], []), (
            "not said again once the project broke anew"
        )

    def test_a_second_break_is_said_though_no_request_came_between_it_and_the_mend(
        self, tmp_path: Path
    ) -> None:
        """The mend and the second break are both saved, and no request for the quick fixes comes
        between the two. The refresh that reads the mend is what lets the second break be said:
        had only a request found the project whole, the first break's sentence would still stand,
        and the second break would be the one hidden."""
        server = self.half_read_server(tmp_path)
        elsewhere = tmp_path / "c.ddd.json"
        assert self.asked_for_fixes(server, elsewhere) == ([WITHHELD], [])
        self.producer_saved(server, tmp_path, "uint16")
        self.producer_saved(server, tmp_path, "uint99")
        assert self.asked_for_fixes(server, elsewhere) == ([WITHHELD], [])

    def test_a_project_that_cannot_be_read_at_all_is_not_found_read_whole(
        self, tmp_path: Path
    ) -> None:
        """A refresh that cannot read the project description at all has not found the project
        read whole. Once the description reads again with the same file still unread, the first
        break is the one standing, and it is not said a second time."""
        server = self.half_read_server(tmp_path)
        elsewhere, described = tmp_path / "c.ddd.json", tmp_path / "p.ddd.json"
        assert self.asked_for_fixes(server, elsewhere) == ([WITHHELD], [])
        kept = described.read_text(encoding="utf-8")
        described.write_text('{"project": ', encoding="utf-8")
        self.saved(server, described)
        described.write_text(kept, encoding="utf-8")
        self.saved(server, described)
        assert self.asked_for_fixes(server, elsewhere) == ([], [])

    def unread_project(self, tmp_path: Path, files: dict[str, Any]) -> Path:
        """A project of ``c.ddd.json`` and of ``files``, each included under its key and written
        from its value - a description, bytes, or nothing at all, which leaves its include naming
        no file - with a build record. Returns ``c.ddd.json``, which states ``rpm``."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "c.ddd.json", *files),
                "c.ddd.json": component("C", declare("input", "Speed", unit="rpm")),
                **{name: text for name, text in files.items() if isinstance(text, dict)},
            },
        )
        for name, text in files.items():
            if isinstance(text, bytes):
                (tmp_path / name).write_bytes(text)
        build_record(tmp_path, tmp_path / "p.ddd.json")
        return tmp_path / "c.ddd.json"

    @pytest.mark.parametrize(
        ("files", "reason"),
        [
            (
                {"a.ddd.json": DROPPED},
                "a.ddd.json did not load, so the rest of the project cannot be edited around it; "
                "fix it and try again",
            ),
            (
                {"missing.ddd.json": None},
                "missing.ddd.json did not load, so the rest of the project cannot be edited around "
                "it; fix it and try again",
            ),
            (
                {"bad.ddd.json": b'{"component": "\xff\xfe"}'},
                "bad.ddd.json did not load, so the rest of the project cannot be edited around it; "
                "fix it and try again",
            ),
            (
                {"one/x.ddd.json": DROPPED, "two/x.ddd.json": DROPPED},
                "one/x.ddd.json, two/x.ddd.json did not load, so the rest of the project cannot be "
                "edited around them; fix them and try again",
            ),
            (
                {"e.ddd.json": ERRING},
                "e.ddd.json has an error that stops the project being analysed, so the rest of the "
                "project cannot be edited around it; fix it and try again",
            ),
            (
                {"a.ddd.json": DROPPED, "e.ddd.json": ERRING, "f.ddd.json": ERRING},
                "a.ddd.json did not load and e.ddd.json, f.ddd.json have an error that stops the "
                "project being analysed, so the rest of the project cannot be edited around them; "
                "fix them and try again",
            ),
            (
                {"one/x.ddd.json": DROPPED, "two/x.ddd.json": ERRING},
                "one/x.ddd.json did not load and two/x.ddd.json has an error that stops the "
                "project being analysed, so the rest of the project cannot be edited around them; "
                "fix them and try again",
            ),
            (
                {"bad.ddd.json": b'{"component": '},
                "bad.ddd.json did not load, so the rest of the project cannot be edited around it; "
                "fix it and try again",
            ),
            (
                {"z/a.ddd.json": DROPPED, "b/z.ddd.json": DROPPED},
                "a.ddd.json, z.ddd.json did not load, so the rest of the project cannot be edited "
                "around them; fix them and try again",
            ),
        ],
        ids=[
            "did-not-load",
            "an-include-naming-no-file",
            "not-utf-8",
            "two-of-one-name",
            "loaded-with-an-error",
            "both",
            "one-name-both",
            "not-json",
            "listed-by-name",
        ],
    )
    def test_the_reason_says_what_each_unread_file_is(
        self, tmp_path: Path, files: dict[str, Any], reason: str
    ) -> None:
        """The reason the rename refusal and the quick fixes' log line both give. A file that did
        not load is said not to have, and one that loaded with an error to have an error, which
        stops the analysis but not the read: said of both, "stopped the project reading it" was
        untrue of the second. A file an include names that cannot be read is that file, not the
        project description the finding sits in, which read; and two files of one name are told
        apart by their paths."""
        elsewhere = self.unread_project(tmp_path, files)
        writer = io.BytesIO()
        Server(session(self.quick_fix_request(elsewhere)), writer, root=tmp_path).run()
        said, answer = answered(writer)
        assert answer == response(13, [])
        assert said["params"]["message"] == f"no quick fix is offered: {reason}"

    def test_what_the_read_only_informs_of_withholds_no_fix(self, tmp_path: Path) -> None:
        """Only an error stops an edit. A units file listing no unit loads, and the read says so
        as information, ``empty-vocabulary``: nothing is withheld and nothing is said."""
        elsewhere = self.unread_project(tmp_path, {"units.ddd.json": {"units": []}})
        writer = io.BytesIO()
        Server(session(self.quick_fix_request(elsewhere)), writer, root=tmp_path).run()
        assert answered(writer) == [response(13, [])]

    def test_an_entry_naming_several_files_keeps_the_error_it_reports(self, tmp_path: Path) -> None:
        """Which of a pattern's files could not be read, the read says in its message alone. The
        error stays the description's, then, as one it has rather than one that stopped it
        loading, which it did not."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "c.ddd.json", "parts/*.ddd.json"),
                "c.ddd.json": component("C", declare("input", "Speed", unit="rpm")),
                "parts/good.ddd.json": component("G", declare("local", "Fine")),
            },
        )
        (tmp_path / "parts" / "bad.ddd.json").write_bytes(b'{"component": "\xff\xfe"}')
        build_record(tmp_path, tmp_path / "p.ddd.json")
        writer = io.BytesIO()
        Server(
            session(self.quick_fix_request(tmp_path / "c.ddd.json")), writer, root=tmp_path
        ).run()
        said, _ = answered(writer)
        assert said["params"]["message"] == (
            "no quick fix is offered: p.ddd.json has an error that stops the project being "
            "analysed, so the rest of the project cannot be edited around it; fix it and try again"
        )

    @pytest.mark.parametrize(
        ("files", "unread"),
        [
            (
                {"one/x.ddd.json": DROPPED, "two/x.ddd.json": DROPPED},
                "one/x.ddd.json, two/x.ddd.json",
            ),
            ({"missing.ddd.json": None}, "missing.ddd.json"),
        ],
        ids=["two-of-one-name", "an-include-naming-no-file"],
    )
    def test_a_unit_rename_names_each_file_that_did_not_load(
        self, tmp_path: Path, files: dict[str, Any], unread: str
    ) -> None:
        """The unit plans name the files that did not load by the same rule, and are told of an
        include naming no file by that file."""
        elsewhere = self.unread_project(tmp_path, files)
        writer = io.BytesIO()
        Server(
            session(
                self.rename_request(elsewhere, "component.interface[0].definition.unit", "1/min")
            ),
            writer,
            root=tmp_path,
        ).run()
        (answer,) = answered(writer)
        assert answer["error"] == {
            "code": REQUEST_FAILED,
            "message": f"{unread} did not load, so renaming 'rpm' could not reach every place it "
            "is stated",
        }

    def test_a_file_that_did_not_load_in_two_images_is_said_once(self, tmp_path: Path) -> None:
        """Both images hold the file, so both withhold the fixes for one reason, in the same
        words: one line, rather than one per image."""
        listed = ["a.ddd.json", "b.ddd.json", "c.ddd.json"]
        self.linked(
            tmp_path,
            {"one": listed, "two": listed},
            {
                "a.ddd.json": component("A", declare("output", "Speed", "uint99", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed")),
                "c.ddd.json": component("C", declare("input", "Speed", unit="rpm")),
            },
            records=True,
        )
        elsewhere = tmp_path / "c.ddd.json"
        found = Server(io.BytesIO(), io.BytesIO(), root=tmp_path)._projects_of(elsewhere)
        assert [loaded.path.name for loaded in found] == ["one.ddd.json", "two.ddd.json"]
        writer = io.BytesIO()
        Server(session(self.quick_fix_request(elsewhere)), writer, root=tmp_path).run()
        said, answer = answered(writer)
        assert answer == response(13, [])
        assert said["params"]["message"] == WITHHELD

    def test_preparing_a_rename_says_where_the_box_goes(self, tmp_path: Path) -> None:
        consumer = self.shared_workspace(tmp_path)
        position = Document(consumer.read_text(encoding="utf-8")).range_of(
            "component.interface[0].definition.name"
        )["start"]
        writer = io.BytesIO()
        Server(
            session(self.navigation_request("textDocument/prepareRename", consumer, position)),
            writer,
            root=tmp_path,
        ).run()
        (answer,) = answered(writer)
        assert answer["result"]["placeholder"] == "Shared"

    def vocabulary_workspace(self, tmp_path: Path) -> Path:
        """A types file whose structure two components name, and a constant they size by."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "types.ddd.json", "constants.ddd.json", "a.ddd.json"),
                "types.ddd.json": {
                    "types": [
                        {
                            "type": "struct",
                            "name": "Sensor_t",
                            "members": [
                                {
                                    "name": "v",
                                    "member": "value",
                                    "datatype": "uint8",
                                    "conversion": {},
                                }
                            ],
                        }
                    ]
                },
                "constants.ddd.json": {"constants": [{"name": "N", "value": 4}]},
                "a.ddd.json": component(
                    "A",
                    declare("output", "Inlet", typename="Sensor_t"),
                    declare("output", "Buf", "uint8", dimensions=["N"]),
                ),
            },
        )
        return tmp_path

    @pytest.mark.parametrize(
        ("source", "pointer", "placeholder"),
        [
            ("types.ddd.json", "types[0].name", "Sensor_t"),
            ("a.ddd.json", "component.interface[0].definition.typename", "Sensor_t"),
            ("constants.ddd.json", "constants[0].name", "N"),
            ("a.ddd.json", "component.interface[1].definition.dimensions[0]", "N"),
        ],
    )
    def test_preparing_a_rename_of_a_type_or_a_constant_says_where_the_box_goes(
        self, tmp_path: Path, source: str, pointer: str, placeholder: str
    ) -> None:
        base = self.vocabulary_workspace(tmp_path)
        path = base / source
        position = Document(path.read_text(encoding="utf-8")).range_of(pointer)["start"]
        writer = io.BytesIO()
        Server(
            session(self.navigation_request("textDocument/prepareRename", path, position)),
            writer,
            root=base,
        ).run()
        (answer,) = answered(writer)
        assert answer["result"]["placeholder"] == placeholder

    def test_renaming_a_type_rewrites_its_declaration_and_every_typename(
        self, tmp_path: Path
    ) -> None:
        base = self.vocabulary_workspace(tmp_path)
        writer = io.BytesIO()
        Server(
            session(self.rename_request(base / "types.ddd.json", "types[0].name", "Probe_t")),
            writer,
            root=base,
        ).run()
        (answer,) = answered(writer)
        assert set(answer["result"]["changes"]) == {
            (base / name).as_uri() for name in ("types.ddd.json", "a.ddd.json")
        }

    @pytest.mark.parametrize(
        "pointer", ["component.interface[0].definition.datatype", "component.name"]
    )
    def test_preparing_a_rename_away_from_a_name_is_declined(
        self, tmp_path: Path, pointer: str
    ) -> None:
        """The editor opens its box over the range this returns, so a range several lines from
        the pointer would be worse than no box at all - even though hovering answers here."""
        consumer = self.shared_workspace(tmp_path)
        position = Document(consumer.read_text(encoding="utf-8")).range_of(pointer)["start"]
        writer = io.BytesIO()
        Server(
            session(self.navigation_request("textDocument/prepareRename", consumer, position)),
            writer,
            root=tmp_path,
        ).run()
        (answer,) = answered(writer)
        assert answer["result"] is None

    def test_a_file_in_two_projects_is_edited_once(self, tmp_path: Path) -> None:
        """Two overlapping rewrites of one range is not a duplicate an editor tolerates."""
        write_tree(
            tmp_path,
            {
                "one.ddd.json": project("One", "a.ddd.json"),
                "two.ddd.json": project("Two", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "Shared")),
            },
        )
        for name in ("one", "two"):
            record = tmp_path / "build" / name / BUILD_INFO_FILENAME
            record.parent.mkdir(parents=True, exist_ok=True)
            record.write_text(
                json.dumps({"project": (tmp_path / f"{name}.ddd.json").as_posix()}),
                encoding="utf-8",
            )
        writer = io.BytesIO()
        Server(
            session(
                self.rename_request(
                    tmp_path / "a.ddd.json", "component.interface[0].definition.name", "Other"
                )
            ),
            writer,
            root=tmp_path,
        ).run()
        (answer,) = answered(writer)
        (edits,) = answer["result"]["changes"].values()
        assert len(edits) == 1

    @pytest.mark.parametrize(("source", "pointer"), [*UNIT_PLACES, ("units.ddd.json", "units[1]")])
    def test_preparing_a_rename_of_a_unit_puts_the_box_over_its_spelling(
        self, tmp_path: Path, source: str, pointer: str
    ) -> None:
        unit_places(tmp_path)
        path = tmp_path / source
        document = Document(path.read_text(encoding="utf-8"))
        position = document.range_of(pointer)["start"]
        writer = io.BytesIO()
        Server(
            session(self.navigation_request("textDocument/prepareRename", path, position)),
            writer,
            root=tmp_path,
        ).run()
        (answer,) = answered(writer)
        assert answer["result"] == {
            "range": document.text_range_of(pointer),
            "placeholder": document.value_at(pointer),
        }

    def renamed_unit(self, tmp_path: Path, source: str, pointer: str, name: str) -> Any:
        """The server's answer to a rename asked at ``pointer`` in ``source``."""
        writer = io.BytesIO()
        Server(
            session(self.rename_request(tmp_path / source, pointer, name)),
            writer,
            root=tmp_path,
        ).run()
        (answer,) = answered(writer)
        return answer

    @pytest.mark.parametrize(("source", "pointer"), UNIT_PLACES)
    def test_a_unit_is_renamed_everywhere_from_wherever_it_is_spelled(
        self, tmp_path: Path, source: str, pointer: str
    ) -> None:
        """The same four files whichever place the rename starts from, and afterwards no file
        states the old spelling; the vocabulary's entry keeps its description."""
        unit_places(tmp_path)
        answer = self.renamed_unit(tmp_path, source, pointer, "1/min")
        rewritten = rewritten_by(answer["result"]["changes"])
        assert set(rewritten) == {"units.ddd.json", "types.ddd.json", "a.ddd.json", "b.ddd.json"}
        assert not any('"rpm"' in text for text in rewritten.values())
        assert sum(text.count('"1/min"') for text in rewritten.values()) == len(UNIT_PLACES)
        assert json.loads(rewritten["units.ddd.json"])["units"] == [
            {"unit": "1/min", "description": "speed"},
            "Nm",
        ]

    def test_a_unit_listed_as_a_spelling_alone_is_renamed_from_its_entry(
        self, tmp_path: Path
    ) -> None:
        unit_places(tmp_path)
        answer = self.renamed_unit(tmp_path, "units.ddd.json", "units[1]", "N.m")
        rewritten = rewritten_by(answer["result"]["changes"])
        assert set(rewritten) == {"units.ddd.json", "types.ddd.json"}
        assert json.loads(rewritten["units.ddd.json"])["units"][1] == "N.m"
        pair = json.loads(rewritten["types.ddd.json"])["types"][1]
        assert pair["members"][1]["unit"] == "N.m"

    def test_renaming_onto_a_listed_unit_merges_the_two_spellings(self, tmp_path: Path) -> None:
        """Two spellings of one unit are what a rename of a unit is for: the old one's entry
        is taken out, and the entry that stays keeps its description."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "units.ddd.json", "a.ddd.json", "b.ddd.json"),
                "units.ddd.json": {
                    "units": [{"unit": "rpm", "description": "speed"}, "1/min", "Nm"]
                },
                "a.ddd.json": component(
                    "A",
                    declare("output", "Speed", unit="1/min"),
                    declare("output", "Idle", unit="rpm"),
                ),
                "b.ddd.json": component("B", declare("input", "Speed", unit="1/min")),
            },
        )
        answer = self.renamed_unit(
            tmp_path, "b.ddd.json", "component.interface[0].definition.unit", "rpm"
        )
        rewritten = rewritten_by(answer["result"]["changes"])
        assert set(rewritten) == {"units.ddd.json", "a.ddd.json", "b.ddd.json"}
        assert json.loads(rewritten["units.ddd.json"])["units"] == [
            {"unit": "rpm", "description": "speed"},
            "Nm",
        ]
        assert "1/min" not in rewritten["a.ddd.json"] + rewritten["b.ddd.json"]

    def test_a_unit_listed_twice_is_merged_at_both_of_its_entries(self, tmp_path: Path) -> None:
        """The units file loaded, though with a duplicate-unit error, so the rename reaches
        both entries - and the two neighbours taken out come to the client as one edit."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "units.ddd.json", "a.ddd.json"),
                "units.ddd.json": {"units": ["rpm", "RPM", "RPM"]},
                "a.ddd.json": component("A", declare("output", "Speed", unit="RPM")),
            },
        )
        answer = self.renamed_unit(
            tmp_path, "a.ddd.json", "component.interface[0].definition.unit", "rpm"
        )
        changes = answer["result"]["changes"]
        rewritten = rewritten_by(changes)
        assert json.loads(rewritten["units.ddd.json"])["units"] == ["rpm"]
        speed = json.loads(rewritten["a.ddd.json"])["component"]["interface"][0]
        assert speed["definition"]["unit"] == "rpm"
        assert len(changes[(tmp_path / "units.ddd.json").as_uri()]) == 1

    def refusal_of(self, document: Path, old: str, new: str) -> UnitRefusalError:
        """The plan's own refusal of this rename, which is what the server has to answer."""
        (loaded,) = navigation.workspaces([], document, document.parent)
        built = navigation.index(loaded.workspace)
        project = unit_project(loaded.path, loaded.unloaded, {})
        with pytest.raises(UnitRefusalError) as refused:
            rename_unit(built, project, old, new, {})
        return refused.value

    @pytest.mark.parametrize("name", ["", " 1/min", "rpm"])
    def test_a_unit_rename_the_plan_refuses_is_answered_with_its_reason(
        self, tmp_path: Path, name: str
    ) -> None:
        """No spelling at all, one with spaces around it, and the spelling it has already."""
        unit_places(tmp_path)
        a = tmp_path / "a.ddd.json"
        answer = self.renamed_unit(
            tmp_path, "a.ddd.json", "component.interface[0].definition.unit", name
        )
        refusal = self.refusal_of(a, "rpm", name)
        assert refusal.code == "invalid"
        assert answer["error"] == {"code": REQUEST_FAILED, "message": refusal.message}

    def test_a_unit_rename_is_refused_while_a_file_of_the_project_did_not_load(
        self, tmp_path: Path
    ) -> None:
        """The file that did not load may state the unit too, and nothing could reach it."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "units.ddd.json", "a.ddd.json", "b.ddd.json"),
                "units.ddd.json": {"units": ["rpm"]},
                "a.ddd.json": component("A", declare("output", "Speed", "uint99", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="rpm")),
            },
        )
        answer = self.renamed_unit(
            tmp_path, "b.ddd.json", "component.interface[0].definition.unit", "1/min"
        )
        refusal = self.refusal_of(tmp_path / "b.ddd.json", "rpm", "1/min")
        assert refusal.code == "unreadable"
        assert "a.ddd.json" in refusal.message
        assert answer["error"] == {"code": REQUEST_FAILED, "message": refusal.message}

    def unit_rename_in_a_buffer(
        self, tmp_path: Path, opened: Path, text: str, asked: Path, name: str
    ) -> dict[str, Any]:
        """The answer to a rename of the unit of ``asked``'s first declaration, while ``opened``
        holds ``text`` unsaved."""
        shown = text if asked == opened else asked.read_text(encoding="utf-8")
        at = Document(shown).range_of("component.interface[0].definition.unit")["start"]
        stream = framed(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"rootUri": tmp_path.as_uri()},
            },
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didOpen",
                "params": {
                    "textDocument": {
                        "uri": opened.as_uri(),
                        "languageId": "json",
                        "version": 1,
                        "text": text,
                    }
                },
            },
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "textDocument/rename",
                "params": {
                    "textDocument": {"uri": asked.as_uri()},
                    "position": at,
                    "newName": name,
                },
            },
            {"jsonrpc": "2.0", "id": 3, "method": "shutdown"},
            {"jsonrpc": "2.0", "method": "exit"},
        )
        writer = io.BytesIO()
        assert Server(stream, writer, root=tmp_path).run() == 0
        return next(message for message in sent(writer) if message.get("id") == 2)

    def test_renaming_a_unit_the_project_neither_states_nor_lists_is_refused(
        self, tmp_path: Path
    ) -> None:
        """Typed into a buffer and not saved: the project the index read has no such unit."""
        unit_places(tmp_path)
        a = tmp_path / "a.ddd.json"
        typed = a.read_text(encoding="utf-8").replace('"unit": "rpm"', '"unit": "rpmx"', 1)
        answer = self.unit_rename_in_a_buffer(tmp_path, a, typed, a, "1/min")
        refusal = self.refusal_of(a, "rpmx", "1/min")
        assert refusal.code == "not-found"
        assert answer["error"] == {"code": REQUEST_FAILED, "message": refusal.message}

    def test_a_unit_rename_is_refused_while_a_buffer_has_moved_the_unit(
        self, tmp_path: Path
    ) -> None:
        """The plan's pointers are the disk's: made in B's buffer, where a declaration was put
        in front, the rename would respell 'Other' and leave 'Speed' as it was."""
        unit_places(tmp_path)
        moved = json.dumps(
            component(
                "B", declare("input", "Other", unit="Nm"), declare("input", "Speed", unit="rpm")
            ),
            indent=2,
        )
        answer = self.unit_rename_in_a_buffer(
            tmp_path, tmp_path / "b.ddd.json", moved, tmp_path / "a.ddd.json", "1/min"
        )
        assert answer["error"]["code"] == REQUEST_FAILED
        assert answer["error"]["message"].startswith("b.ddd.json has unsaved changes")
        assert "result" not in answer

    def test_a_rename_from_a_reader_reaches_the_other_images_reader(self, tmp_path: Path) -> None:
        """A writer linked into two images, each with a reader of its own. Started from the
        reader of image one, a rename visited the projects holding that reader alone, so it
        rewrote the writer and left image two's reader naming an object gone - started from the
        writer, the same rename reached all three."""
        write_tree(
            tmp_path,
            {
                "one.ddd.json": project("One", "writer.ddd.json", "reader_one.ddd.json"),
                "two.ddd.json": project("Two", "writer.ddd.json", "reader_two.ddd.json"),
                "writer.ddd.json": component("W", declare("output", "Speed")),
                "reader_one.ddd.json": component("R1", declare("input", "Speed")),
                "reader_two.ddd.json": component("R2", declare("input", "Speed")),
            },
        )
        build_record(tmp_path, tmp_path / "one.ddd.json", image="one.elf")
        build_record(tmp_path, tmp_path / "two.ddd.json", image="two.elf")
        reader_one = tmp_path / "reader_one.ddd.json"
        writer = io.BytesIO()
        request = self.rename_request(
            reader_one, "component.interface[0].definition.name", "Velocity"
        )
        Server(framed(self.handshake(tmp_path), request, *END), writer, root=tmp_path).run()
        answer = next(m for m in sent(writer) if m.get("id") == 11)
        touched = set(answer["result"].get("changes", {})) | {
            c["textDocument"]["uri"] for c in answer["result"].get("documentChanges", [])
        }
        assert (tmp_path / "reader_two.ddd.json").as_uri() in touched, (
            f"half renamed: {sorted(touched)}"
        )

    def linked(
        self,
        tmp_path: Path,
        images: dict[str, list[str]],
        files: dict[str, Any],
        *,
        records: bool,
    ) -> Path:
        """``files``, and a description of each image of ``images`` including the files it names,
        project ``One`` for image ``one``. Returns the directory holding the descriptions.

        With ``records`` it is one of their own, each image having a record, as a build tree holds
        a collected description, so that only the records find them; without, it is the
        workspace, beside the files they include, where the search above a file finds them.
        """
        where = "images/" if records else ""
        up = "../" if records else ""
        write_tree(
            tmp_path,
            {
                **{
                    f"{where}{image}.ddd.json": project(
                        image.title(), *(f"{up}{name}" for name in included)
                    )
                    for image, included in images.items()
                },
                **files,
            },
        )
        described = tmp_path / where
        if records:
            for image in images:
                build_record(tmp_path, described / f"{image}.ddd.json", image=f"{image}.elf")
        return described

    def two_images(self, tmp_path: Path, *, records: bool = True) -> Path:
        """A writer and the vocabularies shared by two images, and a reader of each image's own:
        SPEC 7.2's component linked into two images. Each reader reads the writer's ``Speed`` in
        ``rpm`` and names the shared type, constant, section and raster. Both images check clean,
        and ``reader_one.ddd.json`` is in image one alone, which reaches image two only through
        a file the two share. Returns the directory holding the descriptions (:meth:`linked`).
        """
        shared = [
            "types.ddd.json",
            "constants.ddd.json",
            "s.ddd.json",
            "r.ddd.json",
            "units.ddd.json",
            "writer.ddd.json",
        ]
        return self.linked(
            tmp_path,
            {"one": [*shared, "reader_one.ddd.json"], "two": [*shared, "reader_two.ddd.json"]},
            {
                "types.ddd.json": types(struct_type("Sensor_t", value_member("v", unit="rpm"))),
                "constants.ddd.json": {"constants": [{"name": "N", "value": 4}]},
                "s.ddd.json": PLACED["s.ddd.json"],
                "r.ddd.json": TIMED["r.ddd.json"],
                "units.ddd.json": {"units": ["rpm"]},
                "writer.ddd.json": component("W", declare("output", "Speed", unit="rpm")),
                **{
                    f"reader_{image}.ddd.json": component(
                        f"R_{image}",
                        declare("input", "Speed", unit="rpm"),
                        declare("local", "Probe", typename="Sensor_t"),
                        declare("local", "Buf", dimensions=["N"], section=".calib", raster="10ms"),
                    )
                    for image in ("one", "two")
                },
            },
            records=records,
        )

    def three_images(self, tmp_path: Path, *, records: bool = True) -> Path:
        """Three images in a chain, every one of them checking clean. Image one holds a writer of
        ``Speed`` in ``rpm`` and its reader; image two the writer and a bridge reading it; image
        three the bridge, a writer of its own and a reader of that one. Images one and three
        share no file: a rename started in image one reaches image three only through the bridge,
        which image two's edits rewrite and image one's do not. Returns the directory holding the
        descriptions (:meth:`linked`)."""
        reads = declare("input", "Speed", unit="rpm")
        return self.linked(
            tmp_path,
            {
                "one": ["writer.ddd.json", "reader_one.ddd.json"],
                "two": ["writer.ddd.json", "bridge.ddd.json"],
                "three": ["bridge.ddd.json", "writer_three.ddd.json", "reader_three.ddd.json"],
            },
            {
                "writer.ddd.json": component("W", declare("output", "Speed", unit="rpm")),
                "reader_one.ddd.json": component("R_one", reads),
                "bridge.ddd.json": component("Bridge", reads),
                "writer_three.ddd.json": component(
                    "W_three", declare("output", "Speed", unit="rpm")
                ),
                "reader_three.ddd.json": component("R_three", reads),
            },
            records=records,
        )

    def opened_holding(self, path: Path, text: str) -> dict[str, Any]:
        """The client opening ``path`` with ``text`` in its buffer, unsaved."""
        return {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {
                "textDocument": {
                    "uri": path.as_uri(),
                    "languageId": "json",
                    "version": 1,
                    "text": text,
                }
            },
        }

    def answer_to(
        self, tmp_path: Path, request: dict[str, Any], *before: dict[str, Any]
    ) -> dict[str, Any]:
        """The server's answer to ``request``, asked after ``before`` in a session the client
        ends."""
        writer = io.BytesIO()
        stream = framed(self.handshake(tmp_path), *before, request, *END)
        assert Server(stream, writer, root=tmp_path).run() == 0
        return next(message for message in sent(writer) if message.get("id") == request["id"])

    RENAMES: Final = (
        ("component.interface[0].definition.name", "Velocity"),
        ("component.interface[1].definition.typename", "Probe_t"),
        ("component.interface[2].definition.dimensions[0]", "SLOTS"),
        ("component.interface[2].definition.section", ".cal"),
        ("component.interface[2].definition.raster", "20ms"),
        ("component.interface[0].definition.unit", "1/min"),
    )
    """Each kind of rename, asked in :meth:`two_images`'s reader: a variable, a type, a constant,
    a section, a raster and a unit."""

    @pytest.mark.parametrize(
        ("pointer", "name"),
        RENAMES,
        ids=["variable", "type", "constant", "section", "raster", "unit"],
    )
    @pytest.mark.parametrize("records", [True, False], ids=["records", "searched"])
    def test_every_kind_of_rename_reaches_every_image_holding_a_file_it_touches(
        self, tmp_path: Path, pointer: str, name: str, records: bool
    ) -> None:
        """Each rename starts in image one alone and touches a file image two holds too, so image
        two is renamed with it: afterwards both images check as clean as before, which a rename
        stopping at image one leaves image two reading a name nothing declares."""
        images = self.two_images(tmp_path, records=records)
        checked = [str(images / image) for image in ("one.ddd.json", "two.ddd.json")]
        assert [main(["check", image]) for image in checked] == [EXIT_OK, EXIT_OK]
        reader_one = tmp_path / "reader_one.ddd.json"
        answer = self.answer_to(tmp_path, self.rename_request(reader_one, pointer, name))
        rewritten = rewritten_by(answer["result"]["changes"])
        assert "reader_two.ddd.json" in rewritten, f"half renamed: {sorted(rewritten)}"
        write_tree(tmp_path, rewritten)
        assert [main(["check", image]) for image in checked] == [EXIT_OK, EXIT_OK], "half renamed"

    @pytest.mark.parametrize(
        ("pointer", "name"), [RENAMES[0], RENAMES[-1]], ids=["variable", "unit"]
    )
    @pytest.mark.parametrize("records", [True, False], ids=["records", "searched"])
    def test_a_rename_goes_on_from_every_project_it_reaches_until_none_is_new(
        self, tmp_path: Path, pointer: str, name: str, records: bool
    ) -> None:
        """Image three shares no file with image one: the rename reaches it through the bridge,
        which image two's edits rewrite and image one's do not. A closure going on from the
        document's projects alone stops at image two, and leaves image three's writer and reader
        apart from the bridge it just rewrote."""
        images = self.three_images(tmp_path, records=records)
        checked = [str(images / f"{image}.ddd.json") for image in ("one", "two", "three")]
        assert [main(["check", image]) for image in checked] == [EXIT_OK] * 3
        reader_one = tmp_path / "reader_one.ddd.json"
        answer = self.answer_to(tmp_path, self.rename_request(reader_one, pointer, name))
        rewritten = rewritten_by(answer["result"]["changes"])
        assert "reader_three.ddd.json" in rewritten, f"stopped short: {sorted(rewritten)}"
        write_tree(tmp_path, rewritten)
        assert [main(["check", image]) for image in checked] == [EXIT_OK] * 3, "half renamed"

    def test_a_condition_two_images_share_has_its_word_rewritten_once(self, tmp_path: Path) -> None:
        """10:I10 through F2, from the constants file: the writer guarding ``Big`` with
        ``CELLS > 2`` is in both images, so each image's edits rewrite the condition's word at the
        same place, and the answer carries it once - twice, a client writes the longer name over
        the start of itself. Both images check clean before and after, as they did with the
        condition left behind: only the condition's own text tells."""
        images = self.linked(
            tmp_path,
            {
                "one": ["c.ddd.json", "w.ddd.json", "reader_one.ddd.json"],
                "two": ["c.ddd.json", "w.ddd.json"],
            },
            {
                **UNDER_A_CONDITION,
                "reader_one.ddd.json": component(
                    "R", declare("local", "Buf", dimensions=["CELLS"])
                ),
            },
            records=True,
        )
        checked = [str(images / image) for image in ("one.ddd.json", "two.ddd.json")]
        assert [main(["check", image]) for image in checked] == [EXIT_OK, EXIT_OK]
        constants = tmp_path / "c.ddd.json"
        answer = self.answer_to(
            tmp_path, self.rename_request(constants, "constants[0].name", "SLOT_COUNT")
        )
        rewritten = rewritten_by(answer["result"]["changes"])
        assert set(rewritten) == {"c.ddd.json", "w.ddd.json", "reader_one.ddd.json"}
        big = json.loads(rewritten["w.ddd.json"])["component"]["interface"][0]
        assert (big["condition"], big["definition"]["dimensions"]) == (
            "SLOT_COUNT > 2",
            ["SLOT_COUNT"],
        )
        write_tree(tmp_path, rewritten)
        assert [main(["check", image]) for image in checked] == [EXIT_OK, EXIT_OK]

    @pytest.mark.parametrize(("records", "image"), [(True, "two.elf"), (False, "two.ddd.json")])
    def test_a_name_another_image_declares_is_refused_naming_that_image(
        self, tmp_path: Path, records: bool, image: str
    ) -> None:
        """Image two's reader keeps a 'Taken' of its own, which image one has never heard of. The
        rename is refused before anything is written, and the refusal says which image declares
        the name: asked from image one, 'this project' alone sends the reader looking in theirs.
        """
        self.two_images(tmp_path, records=records)
        reader_one = tmp_path / "reader_one.ddd.json"
        write_tree(
            tmp_path,
            {
                "reader_two.ddd.json": component(
                    "R_two", declare("input", "Speed", unit="rpm"), declare("local", "Taken")
                )
            },
        )
        request = self.rename_request(reader_one, "component.interface[0].definition.name", "Taken")
        assert self.answer_to(tmp_path, request)["error"] == {
            "code": REQUEST_FAILED,
            "message": (
                f"in {image}, which this rename reaches too: 'Taken' is already declared by this "
                "project"
            ),
        }

    @pytest.mark.parametrize("outside", [False, True], ids=["in-the-folder", "outside-it"])
    def test_a_description_is_named_apart_from_another_of_its_file_name(
        self, tmp_path: Path, outside: bool
    ) -> None:
        """Both images' descriptions are called ``project.ddd.json``, each in a folder of its own,
        and their records name no image. Named by its file name, image two's description reads
        as image one's: it is named by its path in the workspace folder instead, and in full
        where it lies outside it."""
        workspace = tmp_path / "workspace"
        two = (tmp_path / "elsewhere" if outside else workspace / "two") / "project.ddd.json"
        up = Path(os.path.relpath(workspace, two.parent)).as_posix()
        write_tree(
            tmp_path,
            {
                "workspace/one/project.ddd.json": project(
                    "One", "../writer.ddd.json", "../reader_one.ddd.json"
                ),
                str(two.relative_to(tmp_path)): project(
                    "Two", f"{up}/writer.ddd.json", f"{up}/reader_two.ddd.json"
                ),
                "workspace/writer.ddd.json": component("W", declare("output", "Speed")),
                "workspace/reader_one.ddd.json": component("R_one", declare("input", "Speed")),
                "workspace/reader_two.ddd.json": component(
                    "R_two", declare("input", "Speed"), declare("local", "Taken")
                ),
            },
        )
        for image, described in (("one", workspace / "one" / "project.ddd.json"), ("two", two)):
            record = workspace / "build" / image / BUILD_INFO_FILENAME
            record.parent.mkdir(parents=True)
            record.write_text(json.dumps({"project": described.as_posix()}), encoding="utf-8")
        request = self.rename_request(
            workspace / "reader_one.ddd.json", "component.interface[0].definition.name", "Taken"
        )
        named = two.resolve().as_posix() if outside else "two/project.ddd.json"
        assert self.answer_to(workspace, request)["error"]["message"] == (
            f"in {named}, which this rename reaches too: 'Taken' is already declared by this "
            "project"
        )

    @pytest.mark.parametrize(
        ("pointer", "name", "because"),
        [
            (
                "component.interface[0].definition.name",
                "Velocity",
                "did not load, so the rest of the project cannot be edited around it",
            ),
            (
                "component.interface[0].definition.unit",
                "1/min",
                "did not load, so renaming 'rpm' could not reach every place it is stated",
            ),
        ],
        ids=["variable", "unit"],
    )
    def test_a_file_another_image_could_not_load_refuses_the_rename_naming_that_image(
        self, tmp_path: Path, pointer: str, name: str, because: str
    ) -> None:
        """Image two's reader does not load, so nothing can say what it names: rewriting the
        writer the two images share would leave it reading a name that is gone."""
        self.two_images(tmp_path)
        reader_one = tmp_path / "reader_one.ddd.json"
        write_tree(
            tmp_path,
            {"reader_two.ddd.json": component("R_two", declare("input", "Speed", "uint99"))},
        )
        refused = self.answer_to(tmp_path, self.rename_request(reader_one, pointer, name))
        assert refused["error"]["code"] == REQUEST_FAILED
        assert refused["error"]["message"].startswith(
            f"in two.elf, which this rename reaches too: reader_two.ddd.json {because}"
        )

    @pytest.mark.parametrize(
        ("pointer", "name"), [RENAMES[0], RENAMES[-1]], ids=["variable", "unit"]
    )
    def test_a_buffer_of_another_image_that_moved_a_site_refuses_the_rename(
        self, tmp_path: Path, pointer: str, name: str
    ) -> None:
        """Image two's reader is open with a declaration put in front of the one the index
        knows, which is drift the rename has to see wherever it reaches."""
        self.two_images(tmp_path)
        reader_one = tmp_path / "reader_one.ddd.json"
        reader_two = tmp_path / "reader_two.ddd.json"
        interface = json.loads(reader_two.read_text(encoding="utf-8"))["component"]["interface"]
        moved = json.dumps(
            component("R_two", declare("local", "Other", unit="Nm"), *interface), indent=2
        )
        refused = self.answer_to(
            tmp_path,
            self.rename_request(reader_one, pointer, name),
            self.opened_holding(reader_two, moved),
        )
        assert refused["error"]["code"] == REQUEST_FAILED
        assert refused["error"]["message"].startswith("reader_two.ddd.json has unsaved changes")

    def test_a_file_whose_buffer_moved_its_declaration_still_leads_to_the_other_image(
        self, tmp_path: Path
    ) -> None:
        """The writer's buffer moved 'Speed', so no edit of it is computed - but the rename
        touches it all the same, and image two holds it: image two is asked its refusals too,
        and its reader that does not load is answered, which saving the writer would not
        clear."""
        self.two_images(tmp_path)
        reader_one = tmp_path / "reader_one.ddd.json"
        write_tree(
            tmp_path,
            {"reader_two.ddd.json": component("R_two", declare("input", "Speed", "uint99"))},
        )
        moved = json.dumps(
            component("W", declare("local", "Other"), declare("output", "Speed", unit="rpm")),
            indent=2,
        )
        refused = self.answer_to(
            tmp_path,
            self.rename_request(reader_one, *self.RENAMES[0]),
            self.opened_holding(tmp_path / "writer.ddd.json", moved),
        )
        assert refused["error"]["message"].startswith(
            "in two.elf, which this rename reaches too: reader_two.ddd.json did not load"
        )

    def descriptions_read(self, monkeypatch: pytest.MonkeyPatch) -> list[Path]:
        """Every file the server reads a workspace out of from now on, resolved, in order."""
        seen: list[Path] = []

        def spy(path: Path, bag: DiagnosticBag) -> Any:
            seen.append(path.resolve())
            return load_workspace(path, bag)

        monkeypatch.setattr(navigation, "load_workspace", spy)
        return seen

    @pytest.mark.parametrize("records", [True, False], ids=["records", "searched"])
    def test_a_rename_reads_each_description_at_most_once(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, records: bool
    ) -> None:
        """Which projects hold a file the rename touches is asked of the projects already read,
        and a description is read only where no read of it is in hand. Asked file by file, the
        search reads every build's project - and without a record every description above the
        file - once for each file the rename touches. A project found again, holding another of
        those files, is not indexed and asked again either."""
        images = self.two_images(tmp_path, records=records)
        reader_one = tmp_path / "reader_one.ddd.json"
        writer = io.BytesIO()
        server = Server(io.BytesIO(), writer, root=tmp_path)
        assert server._handle(self.handshake(tmp_path))
        seen = self.descriptions_read(monkeypatch)
        indexed: list[Path] = []

        def index(workspace: Any) -> Any:
            indexed.append(workspace.root)
            return navigation.index(workspace)

        monkeypatch.setattr(server_module, "index", index)
        assert server._handle(self.rename_request(reader_one, *self.RENAMES[0]))
        (answer,) = (message for message in sent(writer) if message.get("id") == 11)
        assert (tmp_path / "reader_two.ddd.json").as_uri() in answer["result"]["changes"]
        assert seen.count((images / "two.ddd.json").resolve()) == 1
        again = sorted(path.name for path, count in Counter(seen).items() if count > 1)
        assert again == [], f"read more than once for one rename: {again}"
        assert sorted(path.name for path in indexed) == ["one.ddd.json", "two.ddd.json"]

    def test_the_projects_an_earlier_request_read_are_not_read_again(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A jump before the rename read the projects of the document, which are kept until the
        next refresh; the rename starts from those rather than reading them again. Image two was
        read by that search too and dropped, not holding the document, so the rename reads it."""
        images = self.two_images(tmp_path)
        reader_one = tmp_path / "reader_one.ddd.json"
        position = Document(reader_one.read_text(encoding="utf-8")).range_of(
            "component.interface[0].definition.name"
        )["start"]
        writer = io.BytesIO()
        server = Server(io.BytesIO(), writer, root=tmp_path)
        assert server._handle(self.handshake(tmp_path))
        assert server._handle(
            self.navigation_request("textDocument/definition", reader_one, position)
        )
        seen = self.descriptions_read(monkeypatch)
        assert server._handle(self.rename_request(reader_one, *self.RENAMES[0]))
        (answer,) = (message for message in sent(writer) if message.get("id") == 11)
        assert (tmp_path / "reader_two.ddd.json").as_uri() in answer["result"]["changes"]
        assert seen == [(images / "two.ddd.json").resolve()]

    def test_a_rename_that_touches_no_file_reads_no_description(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """At a position naming nothing renameable a rename computes no edit, so it touches no
        file and reaches no other project. With the document's projects kept from a jump, it has
        nothing left to read - where it read image two, to ask it which of no files it held. It is
        refused rather than answered with an empty edit, which a client applies without a word."""
        self.two_images(tmp_path)
        reader_one = tmp_path / "reader_one.ddd.json"
        position = Document(reader_one.read_text(encoding="utf-8")).range_of(
            "component.interface[0].definition.name"
        )["start"]
        writer = io.BytesIO()
        server = Server(io.BytesIO(), writer, root=tmp_path)
        assert server._handle(self.handshake(tmp_path))
        assert server._handle(
            self.navigation_request("textDocument/definition", reader_one, position)
        )
        seen = self.descriptions_read(monkeypatch)
        assert server._handle(self.rename_request(reader_one, "component.name", "Other"))
        (answer,) = (message for message in sent(writer) if message.get("id") == 11)
        assert answer["error"] == {"code": REQUEST_FAILED, "message": EMPTY_RENAME}
        assert seen == []

    def test_a_code_action_on_an_unknown_unit_offers_the_vocabulary_fixes(
        self, tmp_path: Path
    ) -> None:
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "units.ddd.json", "a.ddd.json"),
                "units.ddd.json": {"units": ["rpm", "Nm"]},
                "a.ddd.json": component("A", declare("output", "Speed", unit="RPM")),
            },
        )
        a = tmp_path / "a.ddd.json"
        span = Document(a.read_text(encoding="utf-8")).range_of(
            "component.interface[0].definition.unit"
        )
        writer = io.BytesIO()
        Server(
            session(
                {
                    "jsonrpc": "2.0",
                    "id": 13,
                    "method": "textDocument/codeAction",
                    "params": {
                        "textDocument": {"uri": a.as_uri()},
                        "range": span,
                        "context": {"diagnostics": UNLISTED},
                    },
                }
            ),
            writer,
            root=tmp_path,
        ).run()
        (answer,) = answered(writer)
        added, renamed = answer["result"]
        assert added["title"] == "Add 'RPM' to the vocabulary"
        assert list(added["edit"]["changes"]) == [(tmp_path / "units.ddd.json").as_uri()]
        assert renamed["title"] == "Rename 'RPM' to 'rpm' everywhere"
        assert list(renamed["edit"]["changes"]) == [a.as_uri()]

    def test_it_offers_quick_fixes(self, tmp_path: Path) -> None:
        from ddd.lsp.edits import QUICK_FIX

        writer = io.BytesIO()
        Server(framed(self.handshake(tmp_path)), writer, root=tmp_path).run()
        capabilities = sent(writer)[0]["result"]["capabilities"]
        assert capabilities["codeActionProvider"] == {"codeActionKinds": [QUICK_FIX]}

    def test_a_code_action_propagates_the_value_under_the_cursor(self, tmp_path: Path) -> None:
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="1/min")),
            },
        )
        build_record(tmp_path, tmp_path / "p.ddd.json")
        producer = tmp_path / "a.ddd.json"
        span = Document(producer.read_text(encoding="utf-8")).range_of(
            "component.interface[0].definition.unit"
        )
        writer = io.BytesIO()
        Server(
            session(
                {
                    "jsonrpc": "2.0",
                    "id": 13,
                    "method": "textDocument/codeAction",
                    "params": {
                        "textDocument": {"uri": producer.as_uri()},
                        "range": span,
                        "context": {"diagnostics": []},
                    },
                }
            ),
            writer,
            root=tmp_path,
        ).run()
        (answer,) = answered(writer)
        (action,) = answer["result"]
        assert "Apply this unit" in action["title"]
        assert list(action["edit"]["changes"]) == [(tmp_path / "b.ddd.json").as_uri()]

    def test_a_body_that_is_not_json_does_not_end_the_conversation(self, tmp_path: Path) -> None:
        """One malformed frame used to kill the server; now it is one refusal on the wire,
        and the hover that follows it is answered as if nothing had happened."""
        consumer = self.shared_workspace(tmp_path)
        position = Document(consumer.read_text(encoding="utf-8")).range_of(
            "component.interface[0].definition.name"
        )["start"]
        follow_up = framed(
            self.navigation_request("textDocument/hover", consumer, position)
        ).getvalue()
        writer = io.BytesIO()
        stream = io.BytesIO(session().getvalue() + raw_frame(b"{ not json") + follow_up)
        assert Server(stream, writer, root=tmp_path).run() == 0
        refusal, answer = answered(writer)
        assert refusal["error"]["code"] == PARSE_ERROR
        assert refusal["id"] is None
        assert "**Shared**" in answer["result"]["contents"]["value"]

    def test_a_batch_request_does_not_end_the_conversation(self, tmp_path: Path) -> None:
        consumer = self.shared_workspace(tmp_path)
        position = Document(consumer.read_text(encoding="utf-8")).range_of(
            "component.interface[0].definition.name"
        )["start"]
        follow_up = framed(
            self.navigation_request("textDocument/hover", consumer, position)
        ).getvalue()
        writer = io.BytesIO()
        stream = io.BytesIO(
            session().getvalue() + raw_frame(b'[{"jsonrpc": "2.0", "id": 1}]') + follow_up
        )
        assert Server(stream, writer, root=tmp_path).run() == 0
        refusal, answer = answered(writer)
        assert refusal["error"]["code"] == INVALID_REQUEST
        assert refusal["id"] is None
        assert answer["result"] is not None

    def test_a_corrupt_length_header_ends_the_run_cleanly(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Framing lost is unrecoverable: one line on stderr, no traceback - and nothing on
        the wire, which carries protocol frames and nothing else."""
        writer = io.BytesIO()
        stream = io.BytesIO(b"Content-Length: banana\r\n\r\n{}")
        assert Server(stream, writer, root=tmp_path).run() == 1
        err = capsys.readouterr().err
        assert err.startswith("ddd: ")
        assert "Content-Length" in err
        assert err.count("\n") == 1
        assert writer.getvalue() == b""

    def test_a_request_it_cannot_serve_is_refused_rather_than_ignored(self, tmp_path: Path) -> None:
        """A client still waiting for an answer looks exactly like a server that has died."""
        writer = io.BytesIO()
        Server(
            session({"jsonrpc": "2.0", "id": 9, "method": "textDocument/completion"}),
            writer,
            root=tmp_path,
        ).run()
        (answer,) = answered(writer)
        assert answer["error"]["code"] == METHOD_NOT_FOUND

    def test_a_notification_it_does_not_know_is_simply_ignored(self, tmp_path: Path) -> None:
        """``didClose`` is now one the server knows; ``willSave`` still is not."""
        writer = io.BytesIO()
        Server(
            session({"jsonrpc": "2.0", "method": "textDocument/willSave", "params": {}}),
            writer,
            root=tmp_path,
        ).run()
        assert answered(writer) == []

    @pytest.mark.parametrize("key", ["workspaceFolders", "rootUri"])
    def test_the_workspace_root_is_taken_from_either_spelling(
        self, tmp_path: Path, key: str
    ) -> None:
        params: dict[str, Any] = (
            {"workspaceFolders": [{"uri": tmp_path.as_uri()}]}
            if key == "workspaceFolders"
            else {"rootUri": tmp_path.as_uri()}
        )
        server = Server(io.BytesIO(), io.BytesIO())
        server._initialise(params)
        assert server.root == tmp_path

    def test_a_client_that_offers_no_root_leaves_the_default(self, tmp_path: Path) -> None:
        server = Server(io.BytesIO(), io.BytesIO(), root=tmp_path)
        server._initialise({})
        assert server.root == tmp_path

    def test_the_command_serves_on_stdin_and_stdout(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from ddd.cli import EXIT_OK, main

        class Stream:
            def __init__(self, buffer: io.BytesIO) -> None:
                self.buffer = buffer

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("sys.stdin", Stream(io.BytesIO()))
        monkeypatch.setattr("sys.stdout", Stream(io.BytesIO()))
        assert main(["lsp", "-b", str(tmp_path)]) == EXIT_OK

    def test_a_position_is_read_from_the_editors_buffer_not_the_disk(self, tmp_path: Path) -> None:
        """The client applies an edit to what is on screen, so that is what the edit must be
        computed against. The disk is what the *analysis* reads - that promise stays - but a
        rename computed from a stale file and applied to a buffer with one extra line rewrote
        five characters of an unrelated line."""
        write_tree(
            tmp_path,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed")),
                "b.ddd.json": component("B", declare("input", "Speed")),
            },
        )
        disk = (tmp_path / "b.ddd.json").read_text(encoding="utf-8")
        on_disk = Document(disk).text_range_of("component.interface[0].definition.name")
        assert on_disk is not None
        # The unsaved buffer: one blank line inserted at the top, nothing else changed.
        buffer = "\n" + disk
        in_buffer = {
            "line": on_disk["start"]["line"] + 1,
            "character": on_disk["start"]["character"],
        }
        uri = (tmp_path / "b.ddd.json").as_uri()
        stream = framed(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"rootUri": tmp_path.as_uri()},
            },
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didOpen",
                "params": {
                    "textDocument": {"uri": uri, "languageId": "json", "version": 3, "text": buffer}
                },
            },
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "textDocument/prepareRename",
                "params": {"textDocument": {"uri": uri}, "position": in_buffer},
            },
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "textDocument/rename",
                "params": {
                    "textDocument": {"uri": uri},
                    "position": in_buffer,
                    "newName": "Velocity",
                },
            },
            {"jsonrpc": "2.0", "id": 4, "method": "shutdown"},
            {"jsonrpc": "2.0", "method": "exit"},
        )
        writer = io.BytesIO()
        assert Server(stream, writer, root=tmp_path).run() == 0
        answers = {m["id"]: m for m in sent(writer) if "id" in m}
        # prepareRename answers at the buffer's line, and the placeholder is the name there.
        assert answers[2]["result"]["placeholder"] == "Speed"
        assert answers[2]["result"]["range"]["start"]["line"] == in_buffer["line"]
        edits = answers[3]["result"]["changes"]
        # b.ddd.json is edited where the buffer has the name, one line below the disk.
        edit_in_b = edits[uri][0]
        assert edit_in_b["range"]["start"]["line"] == on_disk["start"]["line"] + 1
        assert edit_in_b["newText"] == "Velocity"
        # a.ddd.json is not open, so its edit is computed from the disk.
        on_disk_a = Document((tmp_path / "a.ddd.json").read_text(encoding="utf-8")).text_range_of(
            "component.interface[0].definition.name"
        )
        assert edits[(tmp_path / "a.ddd.json").as_uri()][0]["range"] == on_disk_a

    def test_the_findings_are_the_disks_while_the_buffer_says_otherwise(
        self, tmp_path: Path
    ) -> None:
        """The other half of the promise above, which nothing pinned.

        Positions come from the buffer because that is what an edit is applied to; the
        analysis reads the files, because what a build compiles is what is saved. An unsaved
        edit that would fix - or cause - a finding therefore changes nothing until it is
        saved, and a server that analysed the buffer instead would draw a squiggle on a
        project that is fine on disk, or withdraw one from a project that is not.
        """
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("input", "Shared")),
            },
        )
        build_record(tmp_path, tmp_path / "p.ddd.json", severity=["missing-id=ignore"])
        # The buffer produces the other finding of the pair: an output nobody reads.
        buffer = json.dumps(component("A", declare("output", "Shared")), indent=2)
        uri = (tmp_path / "a.ddd.json").as_uri()
        writer = io.BytesIO()
        Server(
            session(
                {
                    "jsonrpc": "2.0",
                    "method": "textDocument/didOpen",
                    "params": {
                        "textDocument": {
                            "uri": uri,
                            "languageId": "json",
                            "version": 1,
                            "text": buffer,
                        }
                    },
                }
            ),
            writer,
            root=tmp_path,
        ).run()
        assert [entry["code"] for entry in published(writer)[uri]] == ["missing-producer"]

    def test_a_change_notification_replaces_the_buffer_and_a_close_forgets_it(
        self, tmp_path: Path
    ) -> None:
        write_tree(
            tmp_path,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "Speed")),
            },
        )
        disk = (tmp_path / "a.ddd.json").read_text(encoding="utf-8")
        on_disk = Document(disk).text_range_of("component.interface[0].definition.name")
        assert on_disk is not None
        uri = (tmp_path / "a.ddd.json").as_uri()
        two_lines_down = {
            "line": on_disk["start"]["line"] + 2,
            "character": on_disk["start"]["character"],
        }
        stream = framed(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"rootUri": tmp_path.as_uri()},
            },
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didOpen",
                "params": {
                    "textDocument": {"uri": uri, "languageId": "json", "version": 1, "text": disk}
                },
            },
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didChange",
                "params": {
                    "textDocument": {"uri": uri, "version": 2},
                    "contentChanges": [{"text": "\n\n" + disk}],
                },
            },
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "textDocument/prepareRename",
                "params": {"textDocument": {"uri": uri}, "position": two_lines_down},
            },
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didClose",
                "params": {"textDocument": {"uri": uri}},
            },
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "textDocument/prepareRename",
                "params": {"textDocument": {"uri": uri}, "position": two_lines_down},
            },
            {"jsonrpc": "2.0", "id": 4, "method": "shutdown"},
            {"jsonrpc": "2.0", "method": "exit"},
        )
        writer = io.BytesIO()
        assert Server(stream, writer, root=tmp_path).run() == 0
        answers = {m["id"]: m for m in sent(writer) if "id" in m}
        assert answers[2]["result"]["placeholder"] == "Speed"  # the changed buffer
        assert answers[3]["result"] is None  # closed: the disk again, where that line is not a name

    def test_an_incremental_change_fragment_is_not_stored_as_the_whole_document(
        self, tmp_path: Path
    ) -> None:
        """The server asks for full-content synchronisation (``change: 1``); a
        ``contentChanges`` entry that carries a ``range`` is an incremental edit sent anyway,
        and its ``text`` is a fragment, not the document. Storing it as the whole buffer would
        answer every later request against a few characters instead of a description file."""
        write_tree(
            tmp_path,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "Speed")),
            },
        )
        disk = (tmp_path / "a.ddd.json").read_text(encoding="utf-8")
        on_disk = Document(disk).text_range_of("component.interface[0].definition.name")
        assert on_disk is not None
        uri = (tmp_path / "a.ddd.json").as_uri()
        stream = framed(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"rootUri": tmp_path.as_uri()},
            },
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didOpen",
                "params": {
                    "textDocument": {"uri": uri, "languageId": "json", "version": 1, "text": disk}
                },
            },
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didChange",
                "params": {
                    "textDocument": {"uri": uri, "version": 2},
                    "contentChanges": [
                        {
                            "range": {
                                "start": {"line": 0, "character": 0},
                                "end": {"line": 0, "character": 0},
                            },
                            "text": "x",
                        }
                    ],
                },
            },
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "textDocument/prepareRename",
                "params": {"textDocument": {"uri": uri}, "position": on_disk["start"]},
            },
            {"jsonrpc": "2.0", "id": 3, "method": "shutdown"},
            {"jsonrpc": "2.0", "method": "exit"},
        )
        writer = io.BytesIO()
        assert Server(stream, writer, root=tmp_path).run() == 0
        answer = next(m for m in sent(writer) if m.get("id") == 2)
        # Unaffected by the fragment: the buffer is still the text the didOpen carried.
        assert answer["result"]["placeholder"] == "Speed"

    def test_a_rename_is_refused_while_a_buffer_has_moved_the_declaration(
        self, tmp_path: Path
    ) -> None:
        """The index describes the disk; a buffer with a declaration inserted above has the
        object one entry further down. Editing at the disk's pointer would rename whatever now
        sits there, so the rename is refused rather than applied to every file but that one -
        an editor that rewrote the other files and left this buffer untouched, with no
        message, would be a project half renamed and a reader with no reason to notice."""
        write_tree(
            tmp_path,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed")),
                "b.ddd.json": component("B", declare("input", "Speed")),
            },
        )
        a_uri = (tmp_path / "a.ddd.json").as_uri()
        b_uri = (tmp_path / "b.ddd.json").as_uri()
        a_disk = (tmp_path / "a.ddd.json").read_text(encoding="utf-8")
        at_name = Document(a_disk).text_range_of("component.interface[0].definition.name")
        assert at_name is not None
        # B's buffer gained a declaration in front of the one the index knows.
        drifted = json.dumps(
            component("B", declare("input", "Other"), declare("input", "Speed")), indent=2
        )
        stream = framed(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"rootUri": tmp_path.as_uri()},
            },
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didOpen",
                "params": {
                    "textDocument": {
                        "uri": b_uri,
                        "languageId": "json",
                        "version": 1,
                        "text": drifted,
                    }
                },
            },
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "textDocument/rename",
                "params": {
                    "textDocument": {"uri": a_uri},
                    "position": at_name["start"],
                    "newName": "Velocity",
                },
            },
            {"jsonrpc": "2.0", "id": 3, "method": "shutdown"},
            {"jsonrpc": "2.0", "method": "exit"},
        )
        writer = io.BytesIO()
        assert Server(stream, writer, root=tmp_path).run() == 0
        answer = next(m for m in sent(writer) if m.get("id") == 2)
        assert answer["error"]["code"] == REQUEST_FAILED
        assert answer["error"]["message"] == (
            "b.ddd.json has unsaved changes this rename would not see; save it and rename again"
        )
        assert "result" not in answer

    def test_a_rename_with_an_unsaved_mention_open_is_refused_naming_the_document(
        self, tmp_path: Path
    ) -> None:
        """C's buffer says 'Speed', typed and not saved: the index is the disk's, so a rename of
        the disk's 'Speed' would leave that mention behind, and the save would then be an
        unknown reference. It is refused, naming the buffer's file, whatever the rename's
        subject: the rename is asked from B, which holds nothing the buffer changed."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json", "c.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed")),
                "b.ddd.json": component("B", declare("input", "Speed")),
                "c.ddd.json": component("C", declare("input", "Other")),
            },
        )
        c = tmp_path / "c.ddd.json"
        unsaved = c.read_text(encoding="utf-8").replace('"Other"', '"Speed"')
        request = self.rename_request(
            tmp_path / "b.ddd.json", "component.interface[0].definition.name", "Velocity"
        )
        answer = self.answer_to(tmp_path, request, self.opened_holding(c, unsaved))
        assert answer["error"] == {
            "code": REQUEST_FAILED,
            "message": "c.ddd.json has unsaved changes this rename would not see; save it and "
            "rename again",
        }

    @pytest.mark.parametrize(
        ("pointer", "name"), [RENAMES[0], RENAMES[-1]], ids=["variable", "unit"]
    )
    def test_a_buffer_of_another_image_that_differs_refuses_the_rename_naming_it(
        self, tmp_path: Path, pointer: str, name: str
    ) -> None:
        """Image two's reader has a mention typed and not saved, which the rename started from
        image one's reader does not see: the refusal is about the buffer, so it is not worded
        as a refusal from image two."""
        self.two_images(tmp_path)
        reader_two = tmp_path / "reader_two.ddd.json"
        unsaved = reader_two.read_text(encoding="utf-8").replace('"R_two"', '"R_two_renamed"')
        refused = self.answer_to(
            tmp_path,
            self.rename_request(tmp_path / "reader_one.ddd.json", pointer, name),
            self.opened_holding(reader_two, unsaved),
        )
        assert refused["error"] == {"code": REQUEST_FAILED, "message": UNSEEN_RENAME}

    @pytest.mark.parametrize(
        ("pointer", "name"), [RENAMES[0], RENAMES[-1]], ids=["variable", "unit"]
    )
    def test_a_buffer_of_a_project_reached_late_refuses_the_rename(
        self, tmp_path: Path, pointer: str, name: str
    ) -> None:
        """Image three's reader is in no project the rename starts from: it is reached through
        the bridge, once image two's edits are known, and its buffer refuses the rename all the
        same."""
        self.three_images(tmp_path)
        reader_three = tmp_path / "reader_three.ddd.json"
        unsaved = reader_three.read_text(encoding="utf-8").replace('"R_three"', '"R_3"')
        refused = self.answer_to(
            tmp_path,
            self.rename_request(tmp_path / "reader_one.ddd.json", pointer, name),
            self.opened_holding(reader_three, unsaved),
        )
        assert refused["error"]["message"].startswith("reader_three.ddd.json has unsaved changes")

    def test_a_buffer_of_a_file_no_reached_project_holds_does_not_refuse_the_rename(
        self, tmp_path: Path
    ) -> None:
        """Notes the workspace keeps beside the project, open and unsaved, are no part of what
        the rename reads or writes."""
        self.two_images(tmp_path)
        write_tree(tmp_path, {"elsewhere.ddd.json": component("E", declare("input", "Other"))})
        elsewhere = tmp_path / "elsewhere.ddd.json"
        unsaved = elsewhere.read_text(encoding="utf-8").replace('"Other"', '"Another"')
        answer = self.answer_to(
            tmp_path,
            self.rename_request(
                tmp_path / "reader_one.ddd.json",
                "component.interface[0].definition.name",
                "Velocity",
            ),
            self.opened_holding(elsewhere, unsaved),
        )
        assert "error" not in answer

    @pytest.mark.parametrize("newline", ["\r\n", "\n"], ids=["crlf", "lf"])
    def test_a_buffer_that_is_its_file_does_not_refuse_the_rename(
        self, tmp_path: Path, newline: str
    ) -> None:
        """The file is written with CRLF line ends and the buffer is what the client sends for
        it, with LF: they are the same document, and a refusal at every line end would refuse
        every rename on Windows."""
        consumer = self.shared_workspace(tmp_path)
        on_disk = consumer.read_text(encoding="utf-8")
        consumer.write_bytes(on_disk.replace("\n", newline).encode("utf-8"))
        answer = self.answer_to(
            tmp_path,
            self.rename_request(consumer, "component.interface[0].definition.name", "Renamed"),
            self.opened_holding(consumer, on_disk),
        )
        assert set(answer["result"]["changes"]) == {
            (tmp_path / name).as_uri() for name in ("a.ddd.json", "b.ddd.json")
        }

    def test_a_buffer_that_declares_the_name_the_rename_is_onto_is_refused(
        self, tmp_path: Path
    ) -> None:
        """A name only a buffer declares passes the project's own check, which reads the disk:
        the rename then merges two objects as soon as the buffer is saved."""
        self.shared_workspace(tmp_path)
        a = tmp_path / "a.ddd.json"
        b = tmp_path / "b.ddd.json"
        unsaved = b.read_text(encoding="utf-8").replace('"Shared"', '"Velocity"')
        answer = self.answer_to(
            tmp_path,
            self.rename_request(a, "component.interface[0].definition.name", "Velocity"),
            self.opened_holding(b, unsaved),
        )
        assert answer["error"] == {
            "code": REQUEST_FAILED,
            "message": "b.ddd.json has unsaved changes this rename would not see; save it and "
            "rename again",
        }

    def test_the_description_of_the_project_is_a_document_of_it_too(self, tmp_path: Path) -> None:
        """An include typed into the project's own buffer and not saved is a file the rename
        does not read."""
        consumer = self.shared_workspace(tmp_path)
        described = tmp_path / "p.ddd.json"
        unsaved = described.read_text(encoding="utf-8").replace('"a.ddd.json"', '"c.ddd.json"')
        answer = self.answer_to(
            tmp_path,
            self.rename_request(consumer, "component.interface[0].definition.name", "Renamed"),
            self.opened_holding(described, unsaved),
        )
        assert answer["error"]["message"].startswith("p.ddd.json has unsaved changes")

    def test_a_buffer_that_does_not_parse_refuses_the_rename(self, tmp_path: Path) -> None:
        """Mid edit, a buffer is often no json at all: what it will say once it parses is
        unknown, so it differs from the file."""
        consumer = self.shared_workspace(tmp_path)
        other = tmp_path / "a.ddd.json"
        answer = self.answer_to(
            tmp_path,
            self.rename_request(consumer, "component.interface[0].definition.name", "Renamed"),
            self.opened_holding(other, other.read_text(encoding="utf-8")[:-3]),
        )
        assert answer["error"]["message"].startswith("a.ddd.json has unsaved changes")

    def test_every_document_that_differs_is_named_in_path_order(self, tmp_path: Path) -> None:
        consumer = self.shared_workspace(tmp_path)
        a = tmp_path / "a.ddd.json"
        buffers = [
            self.opened_holding(path, path.read_text(encoding="utf-8").replace("Shared", "X"))
            for path in (consumer, a)
        ]
        answer = self.answer_to(
            tmp_path,
            self.rename_request(consumer, "component.interface[0].definition.name", "Renamed"),
            *buffers,
        )
        assert answer["error"]["message"] == (
            "a.ddd.json, b.ddd.json have unsaved changes this rename would not see; save them "
            "and rename again"
        )

    @pytest.mark.parametrize(
        ("pointer", "name"), [RENAMES[0], RENAMES[-1]], ids=["variable", "unit"]
    )
    def test_a_rename_in_a_file_no_project_reads_is_refused_not_answered_empty(
        self, tmp_path: Path, pointer: str, name: str
    ) -> None:
        """A file that is on screen and not on disk is read by no project, so there is nothing
        to plan: the rename used to be answered with no edit at all, which a client applies
        without a word."""
        write_tree(tmp_path, {"new.ddd.json": component("N", declare("input", "X", unit="rpm"))})
        new = tmp_path / "new.ddd.json"
        request = self.rename_request(new, pointer, name)
        typed = new.read_text(encoding="utf-8")
        new.unlink()
        answer = self.answer_to(tmp_path, request, self.opened_holding(new, typed))
        assert answer["error"] == {"code": REQUEST_FAILED, "message": EMPTY_RENAME}

    @pytest.mark.parametrize(
        ("pointer", "name", "changed"),
        [
            (RENAMES[0][0], "Velocity", "moved a declaration"),
            (RENAMES[-1][0], "1/min", "moved or respelled a unit"),
        ],
        ids=["variable", "unit"],
    )
    def test_a_file_saved_since_it_was_read_still_refuses_the_rename_as_drifted(
        self, tmp_path: Path, pointer: str, name: str, changed: str
    ) -> None:
        """No buffer differs here: the reader was saved after the server read the project, with
        a declaration put in front of the one the index knows. It is the drift refusal that
        answers, since no open document is there to name."""
        self.two_images(tmp_path)
        reader_one = tmp_path / "reader_one.ddd.json"
        writer = io.BytesIO()
        server = Server(io.BytesIO(), writer, root=tmp_path)
        assert server._handle(self.handshake(tmp_path))
        request = self.rename_request(reader_one, pointer, name)
        position = request["params"]["position"]
        assert server._handle(
            self.navigation_request("textDocument/definition", reader_one, position)
        )
        interface = json.loads(reader_one.read_text(encoding="utf-8"))["component"]["interface"]
        write_tree(
            tmp_path,
            {
                "reader_one.ddd.json": component(
                    "R_one", declare("local", "Other", unit="Nm"), *interface
                )
            },
        )
        assert server._handle(self.rename_request(reader_one, pointer.replace("[0]", "[1]"), name))
        (answer,) = (message for message in sent(writer) if message.get("id") == 11)
        assert answer["error"] == {
            "code": REQUEST_FAILED,
            "message": f"reader_one.ddd.json has unsaved changes that {changed} this rename "
            "would touch; save it and rename again",
        }

    def test_a_rename_started_in_a_drifted_buffer_is_refused_rather_than_applied_elsewhere(
        self, tmp_path: Path
    ) -> None:
        """The file the rename started from is not exempt from its own refusal. The position
        the client sends resolves against C's buffer well enough - the box opened over
        'Speed' just as it should - but the index's site for C still points at the entry the
        inserted declaration displaced, so the same drift applies to the very file the request
        came from, and the whole rename is refused rather than applied to A and B, which were
        clean."""
        write_tree(
            tmp_path,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json", "c.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed")),
                "b.ddd.json": component("B", declare("input", "Speed")),
                "c.ddd.json": component("C", declare("input", "Speed")),
            },
        )
        b_uri = (tmp_path / "b.ddd.json").as_uri()
        c_uri = (tmp_path / "c.ddd.json").as_uri()
        # C's buffer gained a declaration in front of the one the index knows; the rename is
        # asked for at Speed's position *in that buffer*, one entry further down than the disk.
        drifted = json.dumps(
            component("C", declare("input", "Other"), declare("input", "Speed")), indent=2
        )
        in_buffer = Document(drifted).text_range_of("component.interface[1].definition.name")
        assert in_buffer is not None
        stream = framed(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"rootUri": tmp_path.as_uri()},
            },
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didOpen",
                "params": {
                    "textDocument": {
                        "uri": b_uri,
                        "languageId": "json",
                        "version": 1,
                        "text": (tmp_path / "b.ddd.json").read_text(encoding="utf-8"),
                    }
                },
            },
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didOpen",
                "params": {
                    "textDocument": {
                        "uri": c_uri,
                        "languageId": "json",
                        "version": 1,
                        "text": drifted,
                    }
                },
            },
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "textDocument/rename",
                "params": {
                    "textDocument": {"uri": c_uri},
                    "position": in_buffer["start"],
                    "newName": "Velocity",
                },
            },
            {"jsonrpc": "2.0", "id": 3, "method": "shutdown"},
            {"jsonrpc": "2.0", "method": "exit"},
        )
        writer = io.BytesIO()
        assert Server(stream, writer, root=tmp_path).run() == 0
        answer = next(m for m in sent(writer) if m.get("id") == 2)
        assert answer["error"]["code"] == REQUEST_FAILED
        assert "c.ddd.json" in answer["error"]["message"]
        assert "result" not in answer

    def test_no_quick_fix_is_offered_while_another_buffer_has_moved_the_declaration(
        self, tmp_path: Path
    ) -> None:
        write_tree(
            tmp_path,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="Hz")),
            },
        )
        a_uri = (tmp_path / "a.ddd.json").as_uri()
        b_uri = (tmp_path / "b.ddd.json").as_uri()
        a_disk = (tmp_path / "a.ddd.json").read_text(encoding="utf-8")
        at_unit = Document(a_disk).range_of("component.interface[0].definition.unit")
        drifted = json.dumps(
            component(
                "B", declare("input", "Other", unit="Hz"), declare("input", "Speed", unit="Hz")
            ),
            indent=2,
        )
        stream = framed(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"rootUri": tmp_path.as_uri()},
            },
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didOpen",
                "params": {
                    "textDocument": {
                        "uri": b_uri,
                        "languageId": "json",
                        "version": 1,
                        "text": drifted,
                    }
                },
            },
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "textDocument/codeAction",
                "params": {
                    "textDocument": {"uri": a_uri},
                    "range": at_unit,
                    "context": {"diagnostics": []},
                },
            },
            {"jsonrpc": "2.0", "id": 3, "method": "shutdown"},
            {"jsonrpc": "2.0", "method": "exit"},
        )
        writer = io.BytesIO()
        assert Server(stream, writer, root=tmp_path).run() == 0
        answer = next(m for m in sent(writer) if m.get("id") == 2)
        # B is the only other declaration, and it cannot be read at its indexed pointer: no
        # fix can claim to have reconciled with "the other declarations" that unattributably.
        assert answer["result"] == []

    def test_a_client_that_takes_versioned_edits_is_told_which_version_they_are_for(
        self, tmp_path: Path
    ) -> None:
        """Without a version the client applies the edit to whatever the buffer holds by the
        time it arrives; with one it refuses an edit computed for a text it no longer has."""
        write_tree(
            tmp_path,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed")),
                "b.ddd.json": component("B", declare("input", "Speed")),
            },
        )
        a_uri = (tmp_path / "a.ddd.json").as_uri()
        b_uri = (tmp_path / "b.ddd.json").as_uri()
        b_text = (tmp_path / "b.ddd.json").read_text(encoding="utf-8")
        at_name = Document((tmp_path / "a.ddd.json").read_text(encoding="utf-8")).text_range_of(
            "component.interface[0].definition.name"
        )
        assert at_name is not None
        stream = framed(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "rootUri": tmp_path.as_uri(),
                    "capabilities": {"workspace": {"workspaceEdit": {"documentChanges": True}}},
                },
            },
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didOpen",
                "params": {
                    "textDocument": {
                        "uri": b_uri,
                        "languageId": "json",
                        "version": 7,
                        "text": b_text,
                    }
                },
            },
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "textDocument/rename",
                "params": {
                    "textDocument": {"uri": a_uri},
                    "position": at_name["start"],
                    "newName": "Velocity",
                },
            },
            {"jsonrpc": "2.0", "id": 3, "method": "shutdown"},
            {"jsonrpc": "2.0", "method": "exit"},
        )
        writer = io.BytesIO()
        assert Server(stream, writer, root=tmp_path).run() == 0
        answer = next(m for m in sent(writer) if m.get("id") == 2)
        assert "changes" not in answer["result"]
        versions = {
            change["textDocument"]["uri"]: change["textDocument"]["version"]
            for change in answer["result"]["documentChanges"]
        }
        assert versions == {a_uri: None, b_uri: 7}
        assert all(change["edits"] for change in answer["result"]["documentChanges"])

    @pytest.mark.parametrize(
        "capabilities",
        [
            "nonsense",
            {"workspace": "nonsense"},
            {"workspace": {"workspaceEdit": "nonsense"}},
            {"workspace": {"workspaceEdit": {}}},
        ],
    )
    def test_anything_short_of_the_exact_announcement_keeps_the_plain_changes_form(
        self, tmp_path: Path, capabilities: Any
    ) -> None:
        """Each guard in ``_initialise`` refuses a shape one step short of the real
        announcement: capabilities not a dict, workspace not a dict, workspaceEdit not a dict,
        and workspaceEdit a dict that never actually says ``documentChanges: true``. Short of
        the exact shape, the client gets the ``changes`` form, which is the only one it has
        said it can apply.
        """
        write_tree(
            tmp_path,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed")),
            },
        )
        path = tmp_path / "a.ddd.json"
        stream = framed(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"rootUri": tmp_path.as_uri(), "capabilities": capabilities},
            },
            self.rename_request(path, "component.interface[0].definition.name", "Velocity"),
            {"jsonrpc": "2.0", "id": 3, "method": "shutdown"},
            {"jsonrpc": "2.0", "method": "exit"},
        )
        writer = io.BytesIO()
        assert Server(stream, writer, root=tmp_path).run() == 0
        answer = next(m for m in sent(writer) if m.get("id") == 11)
        assert "changes" in answer["result"]
        assert "documentChanges" not in answer["result"]

    ANNOUNCED: ClassVar[dict[str, Any]] = {
        "workspace": {"workspaceEdit": {"documentChanges": True, "changeAnnotationSupport": {}}}
    }

    def edit_answers(self, tmp_path: Path, capabilities: Any, files: int) -> dict[str, Any]:
        """The rename of ``Speed``, which reaches ``files`` files, and the quick fix that
        applies its unit to the other declarations, which reach one file fewer, answered to a
        client that announced ``capabilities``."""
        names = ["a", "b", "c"][:files]
        write_tree(
            tmp_path,
            {
                "project.ddd.json": project("P", *(f"{n}.ddd.json" for n in names)),
                "a.ddd.json": component("A", declare("output", "Speed", unit="Hz")),
                "b.ddd.json": component("B", declare("input", "Speed")),
                "c.ddd.json": component("C", declare("input", "Speed")),
            },
        )
        a_text = (tmp_path / "a.ddd.json").read_text(encoding="utf-8")
        stream = framed(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"rootUri": tmp_path.as_uri(), "capabilities": capabilities},
            },
            self.rename_request(
                tmp_path / "a.ddd.json", "component.interface[0].definition.name", "Velocity"
            ),
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "textDocument/codeAction",
                "params": {
                    "textDocument": {"uri": (tmp_path / "a.ddd.json").as_uri()},
                    "range": Document(a_text).range_of("component.interface[0].definition"),
                    "context": {"diagnostics": []},
                },
            },
            {"jsonrpc": "2.0", "id": 3, "method": "shutdown"},
            {"jsonrpc": "2.0", "method": "exit"},
        )
        writer = io.BytesIO()
        assert Server(stream, writer, root=tmp_path).run() == 0
        sent_back = sent(writer)
        fixes = next(m for m in sent_back if m.get("id") == 2)["result"]
        fix = next((f for f in fixes if f["title"].startswith("Apply this unit")), {})
        return {
            "rename": next(m for m in sent_back if m.get("id") == 11)["result"],
            "fix": fix.get("edit"),
            "title": fix.get("title"),
        }

    @pytest.mark.parametrize("answer", ["rename", "fix"])
    def test_an_edit_reaching_two_files_asks_the_client_to_confirm_it(
        self, tmp_path: Path, answer: str
    ) -> None:
        """10:I11. A client applies a code action's edit and saves every file it touches, so
        an edit across files is marked for the preview, and every edit of it names the mark."""
        got = self.edit_answers(tmp_path, self.ANNOUNCED, 3)
        edit = got[answer]
        assert "changes" not in edit
        assert len(edit["documentChanges"]) == (3 if answer == "rename" else 2)
        (identifier,) = edit["changeAnnotations"]
        note = edit["changeAnnotations"][identifier]
        assert note["needsConfirmation"] is True
        assert note["label"] == ("Rename" if answer == "rename" else got["title"])
        assert all(
            text_edit["annotationId"] == identifier
            for change in edit["documentChanges"]
            for text_edit in change["edits"]
        )

    @pytest.mark.parametrize("answer", ["rename", "fix"])
    @pytest.mark.parametrize(
        "capabilities",
        [
            {"workspace": {"workspaceEdit": {"documentChanges": True}}},
            {"workspace": {"workspaceEdit": {"changeAnnotationSupport": {}}}},
            {
                "workspace": {
                    "workspaceEdit": {"documentChanges": True, "changeAnnotationSupport": 1}
                }
            },
        ],
    )
    def test_a_client_short_of_either_capability_is_sent_no_annotation(
        self, tmp_path: Path, answer: str, capabilities: Any
    ) -> None:
        """An annotated edit exists only inside ``documentChanges``, and an annotation is
        outside what a client that did not announce it negotiated."""
        edit = self.edit_answers(tmp_path, capabilities, 3)[answer]
        assert "changeAnnotations" not in edit
        assert "annotationId" not in json.dumps(edit)
        assert ("documentChanges" in edit) is bool(
            capabilities["workspace"]["workspaceEdit"].get("documentChanges")
        )

    @pytest.mark.parametrize("answer", ["rename", "fix"])
    def test_an_edit_reaching_one_file_stays_unannotated(self, tmp_path: Path, answer: str) -> None:
        edit = self.edit_answers(tmp_path, self.ANNOUNCED, 1 if answer == "rename" else 2)[answer]
        assert len(edit["documentChanges"]) == 1
        assert "changeAnnotations" not in edit
        assert "annotationId" not in json.dumps(edit)

    def test_a_removal_is_not_offered_while_another_declaration_is_unreadable(
        self, tmp_path: Path
    ) -> None:
        """The title says no other declaration has this key, which this can only claim having
        read every one of them. B's real declaration still says "rpm" once you look past the
        decoy in front of it - drifted out of reach is not the same as agreeing."""
        write_tree(
            tmp_path,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="rpm")),
            },
        )
        a_uri = (tmp_path / "a.ddd.json").as_uri()
        b_uri = (tmp_path / "b.ddd.json").as_uri()
        a_disk = (tmp_path / "a.ddd.json").read_text(encoding="utf-8")
        at_unit = Document(a_disk).range_of("component.interface[0].definition.unit")
        # B's buffer gained a declaration in front of the one the index knows; both the decoy
        # and the real declaration say "rpm", but only the pointer has drifted.
        drifted = json.dumps(
            component(
                "B", declare("input", "Other", unit="rpm"), declare("input", "Speed", unit="rpm")
            ),
            indent=2,
        )
        stream = framed(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"rootUri": tmp_path.as_uri()},
            },
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didOpen",
                "params": {
                    "textDocument": {
                        "uri": b_uri,
                        "languageId": "json",
                        "version": 1,
                        "text": drifted,
                    }
                },
            },
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "textDocument/codeAction",
                "params": {
                    "textDocument": {"uri": a_uri},
                    "range": at_unit,
                    "context": {"diagnostics": []},
                },
            },
            {"jsonrpc": "2.0", "id": 3, "method": "shutdown"},
            {"jsonrpc": "2.0", "method": "exit"},
        )
        writer = io.BytesIO()
        assert Server(stream, writer, root=tmp_path).run() == 0
        answer = next(m for m in sent(writer) if m.get("id") == 2)
        # A already states "rpm", so nothing is missing for it to adopt, and the removal this
        # docstring is about cannot claim uniqueness while B sits behind a moved declaration.
        assert answer["result"] == []

    def test_adopting_the_others_value_is_not_offered_while_one_of_them_is_unreadable(
        self, tmp_path: Path
    ) -> None:
        """The title says the other declarations state this value, which this can only claim
        having read every one of them. B alone is not "the other declarations" when C, the
        third, could not be read at all."""
        write_tree(
            tmp_path,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json", "c.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="Hz")),
                "c.ddd.json": component("C", declare("input", "Speed", unit="Hz")),
            },
        )
        a_uri = (tmp_path / "a.ddd.json").as_uri()
        c_uri = (tmp_path / "c.ddd.json").as_uri()
        a_disk = (tmp_path / "a.ddd.json").read_text(encoding="utf-8")
        at_definition = Document(a_disk).range_of("component.interface[0].definition")
        # C's buffer gained a declaration in front of the one the index knows.
        drifted = json.dumps(
            component(
                "C", declare("input", "Other", unit="Hz"), declare("input", "Speed", unit="Hz")
            ),
            indent=2,
        )
        stream = framed(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"rootUri": tmp_path.as_uri()},
            },
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didOpen",
                "params": {
                    "textDocument": {
                        "uri": c_uri,
                        "languageId": "json",
                        "version": 1,
                        "text": drifted,
                    }
                },
            },
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "textDocument/codeAction",
                "params": {
                    "textDocument": {"uri": a_uri},
                    "range": at_definition,
                    "context": {"diagnostics": []},
                },
            },
            {"jsonrpc": "2.0", "id": 3, "method": "shutdown"},
            {"jsonrpc": "2.0", "method": "exit"},
        )
        writer = io.BytesIO()
        assert Server(stream, writer, root=tmp_path).run() == 0
        answer = next(m for m in sent(writer) if m.get("id") == 2)
        for action in answer["result"]:
            assert not action["title"].startswith("Take the unit"), action["title"]

    def alone(self, tmp_path: Path) -> Path:
        """A reader no record claims, no description includes and no project holds, beside a
        writer of its input that it knows nothing of: 10:I5's trigger, one folder with no project
        file and no record. It states a variable, a type, a constant, a section, a raster, a unit
        and a local (:attr:`RENAMES`, and the local at interface 2)."""
        write_tree(
            tmp_path,
            {
                "writer.ddd.json": component("W", declare("output", "Speed", unit="rpm")),
                "reader.ddd.json": component(
                    "R",
                    declare("input", "Speed", unit="rpm"),
                    declare("local", "Probe", typename="Sensor_t"),
                    declare("local", "Buf", dimensions=["N"], section=".calib", raster="10ms"),
                ),
            },
        )
        return tmp_path / "reader.ddd.json"

    NO_PROJECT: Final = (
        "no project is known for reader.ddd.json: only a local variable can be renamed without "
        "one, because a rename has to reach every file that spells the name - put a project "
        "file above it that includes it, or configure the build (ddd-build.json)"
    )

    @pytest.mark.parametrize(
        ("pointer", "name"),
        RENAMES,
        ids=["variable", "type", "constant", "section", "raster", "unit"],
    )
    def test_with_no_project_known_every_rename_but_a_locals_is_refused(
        self, tmp_path: Path, pointer: str, name: str
    ) -> None:
        """F2 on an input, a type, a constant, a section, a raster or a unit of a component read
        on its own rewrote that one file and said nothing, while its writer, a file away, kept the
        old name. A unit is planned elsewhere (``_rename_unit``) and is refused the same."""
        reader = self.alone(tmp_path)
        answer = self.answer_to(tmp_path, self.rename_request(reader, pointer, name))
        assert answer["error"] == {"code": REQUEST_FAILED, "message": self.NO_PROJECT}
        assert "result" not in answer

    def test_an_output_with_no_project_known_is_refused_too(self, tmp_path: Path) -> None:
        """The finding's own trigger: F2 on a writer's output, with its reader beside it."""
        self.alone(tmp_path)
        request = self.rename_request(
            tmp_path / "writer.ddd.json", "component.interface[0].definition.name", "Velocity"
        )
        answer = self.answer_to(tmp_path, request)
        assert answer["error"] == {
            "code": REQUEST_FAILED,
            "message": self.NO_PROJECT.replace("reader.ddd.json", "writer.ddd.json"),
        }

    @pytest.mark.parametrize("position", [1, 2], ids=["a local typed", "a local sized"])
    def test_with_no_project_known_a_locals_rename_goes_through(
        self, tmp_path: Path, position: int
    ) -> None:
        """A local is spelled in the file declaring it and nowhere else, which is all a component
        read on its own has."""
        reader = self.alone(tmp_path)
        request = self.rename_request(
            reader, f"component.interface[{position}].definition.name", "Renamed"
        )
        answer = self.answer_to(tmp_path, request)
        assert set(answer["result"]["changes"]) == {reader.as_uri()}
        assert '"Renamed"' in rewritten_by(answer["result"]["changes"])["reader.ddd.json"]

    def test_a_name_that_is_a_locals_in_one_file_and_not_in_another_is_not_a_locals(
        self, tmp_path: Path
    ) -> None:
        """What is local is what every declaration of the name states: one file declaring a
        local and an output of one name has an output, which a reader elsewhere may name."""
        write_tree(
            tmp_path,
            {
                "reader.ddd.json": component(
                    "R", declare("local", "Speed"), declare("output", "Speed")
                )
            },
        )
        request = self.rename_request(
            tmp_path / "reader.ddd.json", "component.interface[0].definition.name", "Velocity"
        )
        answer = self.answer_to(tmp_path, request)
        assert answer["error"]["message"] == self.NO_PROJECT

    def test_a_build_record_naming_the_component_as_its_description_is_a_project(
        self, tmp_path: Path
    ) -> None:
        """An image of one component: the record claims it, so what the rename reaches is known
        - the component itself."""
        reader = self.alone(tmp_path)
        build_record(tmp_path, reader, image="reader.elf")
        loaded = navigation.workspaces(discover(tmp_path), reader, tmp_path)
        assert not navigation.is_alone(reader, loaded, discover(tmp_path))
        request = self.rename_request(reader, "component.interface[0].definition.name", "Rate")
        answer = self.answer_to(tmp_path, request)
        assert set(answer["result"]["changes"]) == {reader.as_uri()}

    def test_a_reference_naming_nothing_is_not_a_locals_rename(self, tmp_path: Path) -> None:
        """A name no declaration states states no scope, so nothing says it is spelled here
        alone."""
        write_tree(
            tmp_path,
            {
                "reader.ddd.json": component(
                    "R", declare("local", "Curve", kind="curve", datatype="uint8", axis="Absent")
                )
            },
        )
        request = self.rename_request(
            tmp_path / "reader.ddd.json", "component.interface[0].definition.axis", "Gone"
        )
        answer = self.answer_to(tmp_path, request)
        assert answer["error"]["message"] == self.NO_PROJECT

    def test_a_project_file_read_alone_is_a_known_project(self, tmp_path: Path) -> None:
        """What the read alone answers for a description naming components: the project, whole,
        which is no ignorance of what a rename reaches."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed")),
            },
        )
        loaded = navigation.workspaces([], tmp_path / "p.ddd.json")
        assert not navigation.is_alone(tmp_path / "p.ddd.json", loaded, [])
        (single,) = navigation.workspaces([], tmp_path / "a.ddd.json")
        assert single.path == tmp_path / "p.ddd.json"
        assert not navigation.is_alone(tmp_path / "a.ddd.json", [single], [])

    def test_a_component_read_on_its_own_is_alone(self, tmp_path: Path) -> None:
        reader = self.alone(tmp_path)
        loaded = navigation.workspaces([], reader, tmp_path)
        assert navigation.is_alone(reader, loaded, [])
        assert not navigation.is_alone(reader, [], [])

    def test_with_a_project_file_above_the_same_rename_edits_every_file(
        self, tmp_path: Path
    ) -> None:
        """The control: the finding's folder with a project file beside the pair."""
        self.alone(tmp_path)
        write_tree(tmp_path, {"p.ddd.json": project("P", "writer.ddd.json", "reader.ddd.json")})
        request = self.rename_request(
            tmp_path / "writer.ddd.json", "component.interface[0].definition.name", "Velocity"
        )
        answer = self.answer_to(tmp_path, request)
        assert set(answer["result"]["changes"]) == {
            (tmp_path / name).as_uri() for name in ("writer.ddd.json", "reader.ddd.json")
        }

    def stopped(self, tmp_path: Path, *, above: str = "") -> Path:
        """A project, in ``above`` below the workspace, whose plugin stops the read of its
        description, including a component with a shared output. Returns the component."""
        write_tree(
            tmp_path,
            {
                f"{above}tools/exiting_plugin.py": EXITING_MODEL_PLUGIN,
                f"{above}project.ddd.json": project(
                    "P", "a.ddd.json", "b.ddd.json", plugins=["tools/exiting_plugin.py"]
                ),
                f"{above}a.ddd.json": component("A", declare("output", "Speed")),
                f"{above}b.ddd.json": component(
                    "B",
                    declare("input", "Speed"),
                    declare("local", "X", extensions={"exiting": {"tag": "t"}}),
                ),
            },
        )
        return tmp_path / f"{above}a.ddd.json"

    REASON: Final = "plugin 'exiting' failed validating an 'extensions' block"

    def test_a_description_above_that_could_not_be_read_is_named_with_its_reason(
        self, tmp_path: Path
    ) -> None:
        """Read alone, the component would answer 'no project is known', which is not what is
        wrong: a project holds it, and a plugin stops that project's read."""
        document = self.stopped(tmp_path)
        request = self.rename_request(document, "component.interface[0].definition.name", "V")
        message = self.answer_to(tmp_path, request)["error"]["message"]
        assert message.startswith("project.ddd.json could not be read, so this rename cannot ")
        assert self.REASON in message
        assert "no project is known" not in message

    def test_a_description_that_could_not_be_read_is_named_after_a_hover_read_the_projects(
        self, tmp_path: Path
    ) -> None:
        """The projects of a document are kept until the next refresh, and a hover asks for them:
        the rename that follows finds them read, and still names what stopped one."""
        document = self.stopped(tmp_path)
        hover = {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "textDocument/hover",
            "params": {
                "textDocument": {"uri": document.as_uri()},
                "position": Document(document.read_text(encoding="utf-8")).range_of(
                    "component.interface[0].definition.name"
                )["start"],
            },
        }
        request = self.rename_request(document, "component.interface[0].definition.name", "V")
        message = self.answer_to(tmp_path, request, hover)["error"]["message"]
        assert message.startswith("project.ddd.json could not be read")
        assert self.REASON in message

    def test_the_first_of_two_descriptions_that_could_not_be_read_is_the_one_named(
        self, tmp_path: Path
    ) -> None:
        """One refusal, and the same one whichever order the reads happened in: by path."""
        document = self.stopped(tmp_path)
        shutil.copy(tmp_path / "project.ddd.json", tmp_path / "another.ddd.json")
        request = self.rename_request(document, "component.interface[0].definition.name", "V")
        message = self.answer_to(tmp_path, request)["error"]["message"]
        assert message.startswith("another.ddd.json could not be read")

    def test_a_description_that_could_not_be_read_refuses_a_locals_rename_too(
        self, tmp_path: Path
    ) -> None:
        """The refusal comes before any closure, whatever the kind: a rename that half-applies to
        an image whose description a plugin stops is the half-renamed project."""
        write_tree(
            tmp_path,
            {
                "tools/exiting_plugin.py": EXITING_MODEL_PLUGIN,
                "project.ddd.json": project("P", "a.ddd.json", plugins=["tools/exiting_plugin.py"]),
                "a.ddd.json": component(
                    "A",
                    declare("local", "X", extensions={"exiting": {"tag": "t"}}),
                    declare("local", "Y"),
                ),
            },
        )
        request = self.rename_request(
            tmp_path / "a.ddd.json", "component.interface[1].definition.name", "Z"
        )
        message = self.answer_to(tmp_path, request)["error"]["message"]
        assert message.startswith("project.ddd.json could not be read")

    def test_a_unit_rename_is_refused_for_a_description_that_could_not_be_read(
        self, tmp_path: Path
    ) -> None:
        write_tree(
            tmp_path,
            {
                "tools/exiting_plugin.py": EXITING_MODEL_PLUGIN,
                "project.ddd.json": project("P", "a.ddd.json", plugins=["tools/exiting_plugin.py"]),
                "a.ddd.json": component(
                    "A",
                    declare("local", "X", extensions={"exiting": {"tag": "t"}}),
                    declare("local", "Y", unit="rpm"),
                ),
            },
        )
        request = self.rename_request(
            tmp_path / "a.ddd.json", "component.interface[1].definition.unit", "1/min"
        )
        message = self.answer_to(tmp_path, request)["error"]["message"]
        assert message.startswith("project.ddd.json could not be read")
        assert self.REASON in message

    def test_a_record_naming_a_description_that_could_not_be_read_names_its_image(
        self, tmp_path: Path
    ) -> None:
        """Where a build record names the description, its image names it too."""
        document = self.stopped(tmp_path, above="images/")
        build_record(tmp_path, tmp_path / "images/project.ddd.json", image="one.elf")
        request = self.rename_request(document, "component.interface[0].definition.name", "V")
        message = self.answer_to(tmp_path, request)["error"]["message"]
        assert message.startswith(
            "images/project.ddd.json of the image one.elf could not be read, so this rename "
        )
        assert self.REASON in message

    def test_a_description_the_closure_meets_and_cannot_read_refuses_the_rename(
        self, tmp_path: Path
    ) -> None:
        """Image one reads, and the rename started in its reader reaches the shared writer, a
        file a second description holds and a plugin stops: the rename would rewrite image one
        and leave the second reading a name nothing declares. It is refused, naming that
        description."""
        write_tree(
            tmp_path,
            {
                "tools/exiting_plugin.py": EXITING_MODEL_PLUGIN,
                "one/one.ddd.json": project("One", "../shared/writer.ddd.json", "reader.ddd.json"),
                "one/reader.ddd.json": component("R", declare("input", "Speed")),
                "shared/writer.ddd.json": component("W", declare("output", "Speed")),
                "shared/two.ddd.json": project(
                    "Two",
                    "writer.ddd.json",
                    "other.ddd.json",
                    plugins=["../tools/exiting_plugin.py"],
                ),
                "shared/other.ddd.json": component(
                    "O", declare("local", "X", extensions={"exiting": {"tag": "t"}})
                ),
            },
        )
        request = self.rename_request(
            tmp_path / "one/reader.ddd.json", "component.interface[0].definition.name", "V"
        )
        message = self.answer_to(tmp_path, request)["error"]["message"]
        assert message.startswith(
            "shared/two.ddd.json could not be read, so this rename cannot tell what it reaches: "
        )
        assert self.REASON in message

    def shared_units(self, tmp_path: Path, *, stopped: bool) -> Path:
        """Image one, in ``one/``, and a units file in ``shared/`` that a second description
        holds too, which a plugin stops where ``stopped``. Returns image one's reader."""
        write_tree(
            tmp_path,
            {
                "tools/exiting_plugin.py": EXITING_MODEL_PLUGIN,
                "one/one.ddd.json": project("One", "../shared/units.ddd.json", "reader.ddd.json"),
                "one/reader.ddd.json": component("R", declare("input", "Speed", unit="rpm")),
                "shared/units.ddd.json": {"units": ["rpm"]},
                "shared/two.ddd.json": project(
                    "Two",
                    "units.ddd.json",
                    *(["other.ddd.json"] if stopped else []),
                    plugins=["../tools/exiting_plugin.py"],
                ),
                **(
                    {
                        "shared/other.ddd.json": component(
                            "O", declare("local", "X", extensions={"exiting": {"tag": "t"}})
                        )
                    }
                    if stopped
                    else {}
                ),
            },
        )
        return tmp_path / "one/reader.ddd.json"

    def test_a_unit_rename_meets_a_description_the_closure_could_not_read(
        self, tmp_path: Path
    ) -> None:
        """The units file the rename rewrites is one a second description holds, and a plugin
        stops that description: refused naming it, as a variable's rename is."""
        reader = self.shared_units(tmp_path, stopped=True)
        request = self.rename_request(reader, "component.interface[0].definition.unit", "1/min")
        message = self.answer_to(tmp_path, request)["error"]["message"]
        assert message.startswith(
            "shared/two.ddd.json could not be read, so this rename cannot tell what it reaches: "
        )
        assert self.REASON in message

    def test_a_unit_rename_goes_through_once_the_description_is_mended(
        self, tmp_path: Path
    ) -> None:
        """The control of the test above."""
        reader = self.shared_units(tmp_path, stopped=False)
        request = self.rename_request(reader, "component.interface[0].definition.unit", "1/min")
        answer = self.answer_to(tmp_path, request)
        assert set(answer["result"]["changes"]) == {
            (tmp_path / name).as_uri() for name in ("one/reader.ddd.json", "shared/units.ddd.json")
        }

    def test_the_closure_reads_on_once_the_description_it_could_not_read_is_mended(
        self, tmp_path: Path
    ) -> None:
        """The control of the test above: the same trees, the plugin's block mended."""
        write_tree(
            tmp_path,
            {
                "tools/exiting_plugin.py": EXITING_MODEL_PLUGIN,
                "one/one.ddd.json": project("One", "../shared/writer.ddd.json", "reader.ddd.json"),
                "one/reader.ddd.json": component("R", declare("input", "Speed")),
                "shared/writer.ddd.json": component("W", declare("output", "Speed")),
                "shared/two.ddd.json": project(
                    "Two", "writer.ddd.json", plugins=["../tools/exiting_plugin.py"]
                ),
            },
        )
        request = self.rename_request(
            tmp_path / "one/reader.ddd.json", "component.interface[0].definition.name", "V"
        )
        answer = self.answer_to(tmp_path, request)
        assert set(answer["result"]["changes"]) == {
            (tmp_path / name).as_uri() for name in ("one/reader.ddd.json", "shared/writer.ddd.json")
        }

    def test_the_server_asks_for_the_full_text_on_every_change(self, tmp_path: Path) -> None:
        stream = framed(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"rootUri": tmp_path.as_uri()},
            },
            {"jsonrpc": "2.0", "method": "exit"},
        )
        writer = io.BytesIO()
        Server(stream, writer, root=tmp_path).run()
        sync = sent(writer)[0]["result"]["capabilities"]["textDocumentSync"]
        assert sync == {"openClose": True, "change": 1, "save": True}


UNSTAMPED = [{"code": "missing-id", "source": "ddd", "message": "has no 'id'"}]


class TestOfferingAnIdentity:
    """The code action behind ``missing-id``: give this object an id, here, now.

    ``ddd id --assign`` stamps a whole file from the command line. In an editor the useful
    grain is one declaration - the one whose squiggle you are looking at - so the action is
    offered per declaration and carries the finding it settles.
    """

    def built(self, tmp_path: Path, **files: Any) -> Any:
        from ddd.lsp.navigation import index

        write_tree(tmp_path, {"p.ddd.json": project("P", *files), **files})
        return index(load_workspace(tmp_path / "p.ddd.json", DiagnosticBag()))

    def test_a_producing_declaration_without_an_id_is_offered_one(self, tmp_path: Path) -> None:
        from ddd.lsp.edits import actions
        from ddd.models.common import OBJECT_ID_PATTERN

        built = self.built(tmp_path, **{"a.ddd.json": component("A", declare("local", "Speed"))})
        cache: dict[Path, Document] = {}
        path = tmp_path / "a.ddd.json"
        offered = actions(
            built, path, read(path, cache), "component.interface[0].definition", cache, UNSTAMPED
        )
        (giving,) = [entry for entry in offered if "id" in entry["title"]]
        (edits,) = giving["edit"]["changes"].values()
        written = json.loads(apply_edits(path, edits))
        stamped = written["component"]["interface"][0]["definition"]["id"]
        assert re.fullmatch(OBJECT_ID_PATTERN, stamped)

    def test_an_id_stated_as_null_is_replaced_by_the_offer(self, tmp_path: Path) -> None:
        """What ``ddd dump`` writes of an unstamped object, and what ``missing-id`` reports as it
        reports the key's absence: the offer fills the ``null`` in rather than adding a second
        ``id``."""
        from ddd.lsp.edits import actions
        from ddd.models.common import OBJECT_ID_PATTERN

        built = self.built(
            tmp_path, **{"a.ddd.json": component("A", declare("local", "Speed", id=None))}
        )
        cache: dict[Path, Document] = {}
        path = tmp_path / "a.ddd.json"
        offered = actions(
            built, path, read(path, cache), "component.interface[0].definition", cache, UNSTAMPED
        )
        (giving,) = [entry for entry in offered if "id" in entry["title"]]
        (edits,) = giving["edit"]["changes"].values()
        written = apply_edits(path, edits)
        assert "null" not in written
        stamped = json.loads(written)["component"]["interface"][0]["definition"]["id"]
        assert re.fullmatch(OBJECT_ID_PATTERN, stamped)

    def test_the_offer_writes_what_ddd_id_writes(self, tmp_path: Path) -> None:
        """The editor, the page and the command put an id in one place: right after the name."""
        from ddd.lsp.edits import actions

        files = {"a.ddd.json": component("A", declare("local", "Speed"))}
        built = self.built(tmp_path / "editor", **files)
        cache: dict[Path, Document] = {}
        path = tmp_path / "editor" / "a.ddd.json"
        offered = actions(
            built, path, read(path, cache), "component.interface[0].definition", cache, UNSTAMPED
        )
        (giving,) = [entry for entry in offered if "id" in entry["title"]]
        (edits,) = giving["edit"]["changes"].values()
        write_tree(tmp_path / "command", files)
        assert main(["id", "--assign", str(tmp_path / "command" / "a.ddd.json")]) == EXIT_OK
        by_the_command = (tmp_path / "command" / "a.ddd.json").read_text(encoding="utf-8")
        assert without_ids(apply_edits(path, edits)) == without_ids(by_the_command)

    def test_the_offer_carries_the_finding_it_settles(self, tmp_path: Path) -> None:
        """Which is what puts the lightbulb on the squiggle rather than leaving it to be found."""
        from ddd.lsp.edits import actions

        built = self.built(tmp_path, **{"a.ddd.json": component("A", declare("local", "Speed"))})
        cache: dict[Path, Document] = {}
        path = tmp_path / "a.ddd.json"
        reported = [{"code": "missing-id", "source": "ddd", "message": "has no 'id'"}]
        offered = actions(
            built, path, read(path, cache), "component.interface[0].definition", cache, reported
        )
        (giving,) = [entry for entry in offered if "id" in entry["title"]]
        assert [entry["code"] for entry in giving["diagnostics"]] == ["missing-id"]

    def test_a_declaration_that_already_states_one_is_offered_nothing(self, tmp_path: Path) -> None:
        from ddd.lsp.edits import actions

        built = self.built(
            tmp_path,
            **{"a.ddd.json": component("A", declare("local", "Speed", id="k7m2q9xr4t8w"))},
        )
        cache: dict[Path, Document] = {}
        path = tmp_path / "a.ddd.json"
        offered = actions(
            built, path, read(path, cache), "component.interface[0].definition", cache, UNSTAMPED
        )
        assert [entry for entry in offered if "id" in entry["title"]] == []

    def test_a_consumer_is_offered_nothing(self, tmp_path: Path) -> None:
        """An identity is the producer's to state; consumer-identity refuses one here."""
        from ddd.lsp.edits import actions

        built = self.built(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("output", "Speed", id="k7m2q9xr4t8w")),
                "b.ddd.json": component("B", declare("input", "Speed")),
            },
        )
        cache: dict[Path, Document] = {}
        path = tmp_path / "b.ddd.json"
        offered = actions(
            built, path, read(path, cache), "component.interface[0].definition", cache, UNSTAMPED
        )
        assert [entry for entry in offered if "id" in entry["title"]] == []


UNLISTED = [
    {"code": "unknown-unit", "source": "ddd", "message": "is not a unit this project declares"}
]


class TestFixingAnUnknownUnit:
    """The code actions behind ``unknown-unit``: put the unit into the vocabulary, or respell it
    everywhere as a unit the vocabulary lists - the plans ``ddd gui`` makes, as text edits."""

    AT_THE_UNIT = "component.interface[0].definition.unit"

    def stating(self, tmp_path: Path, unit: str, *vocabulary: Any) -> Path:
        """A producer declaring two variables in ``unit`` and a reader of one, and a vocabulary
        of ``vocabulary`` when it lists anything."""
        files: dict[str, Any] = {
            "a.ddd.json": component(
                "A", declare("output", "Speed", unit=unit), declare("output", "Idle", unit=unit)
            ),
            "b.ddd.json": component("B", declare("input", "Speed", unit=unit)),
        }
        if vocabulary:
            files["units.ddd.json"] = {"units": list(vocabulary)}
        write_tree(tmp_path, {"p.ddd.json": project("P", *files), **files})
        return tmp_path / "p.ddd.json"

    def offered(
        self,
        root: Path,
        source: str = "a.ddd.json",
        pointer: str = AT_THE_UNIT,
        cache: dict[Path, Document] | None = None,
        reported: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        from ddd.lsp.edits import actions

        cache = {} if cache is None else cache
        reported = UNLISTED if reported is None else reported
        workspace = load_workspace(root, DiagnosticBag())
        assert workspace is not None
        built = navigation.index(workspace)
        path = root.parent / source
        project = unit_project(root, (), cache)
        return actions(built, path, read(path, cache), pointer, cache, reported, project)

    def titles(self, offered: list[dict[str, Any]]) -> list[str]:
        return [action["title"] for action in offered]

    def test_an_unknown_unit_is_offered_the_vocabulary_and_each_close_spelling(
        self, tmp_path: Path
    ) -> None:
        """One rename per spelling the finding suggests, in the order it names them: closest
        first, a tie by spelling."""
        offered = self.offered(self.stating(tmp_path, "rpms", "rpm", "rps", "rpm2", "Nm"))
        assert self.titles(offered) == [
            "Add 'rpms' to the vocabulary",
            "Rename 'rpms' to 'rpm' everywhere",
            "Rename 'rpms' to 'rps' everywhere",
            "Rename 'rpms' to 'rpm2' everywhere",
        ]
        assert all(action["diagnostics"] == UNLISTED for action in offered)

    @pytest.mark.parametrize(
        ("vocabulary", "added"),
        [
            (("rpm", "Nm"), "rpms"),
            (("rpm", {"unit": "Nm", "description": "torque"}), {"unit": "rpms", "description": ""}),
        ],
    )
    def test_adding_appends_the_unit_in_the_form_the_vocabulary_is_written_in(
        self, tmp_path: Path, vocabulary: tuple[Any, ...], added: Any
    ) -> None:
        root = self.stating(tmp_path, "rpms", *vocabulary)
        (adding,) = [a for a in self.offered(root) if a["title"].startswith("Add")]
        rewritten = rewritten_by(adding["edit"]["changes"])
        assert json.loads(rewritten["units.ddd.json"])["units"] == [*vocabulary, added]

    def test_renaming_respells_the_unit_everywhere_it_is_stated(self, tmp_path: Path) -> None:
        root = self.stating(tmp_path, "rpms", "rpm", "Nm")
        (renaming,) = [a for a in self.offered(root) if a["title"].startswith("Rename")]
        rewritten = rewritten_by(renaming["edit"]["changes"])
        assert set(rewritten) == {"a.ddd.json", "b.ddd.json"}
        assert rewritten["a.ddd.json"].count('"unit": "rpm"') == 2
        assert rewritten["b.ddd.json"].count('"unit": "rpm"') == 1

    def test_a_unit_a_type_states_is_offered_the_same(self, tmp_path: Path) -> None:
        """A unit is written on a scalar type as often as on a declaration."""
        files: dict[str, Any] = {
            "units.ddd.json": {"units": ["rpm", "Nm"]},
            "types.ddd.json": types(scalar_type("Speed_t", unit="rpms")),
        }
        write_tree(tmp_path, {"p.ddd.json": project("P", *files), **files})
        offered = self.offered(tmp_path / "p.ddd.json", "types.ddd.json", "types[0].unit")
        assert self.titles(offered) == [
            "Add 'rpms' to the vocabulary",
            "Rename 'rpms' to 'rpm' everywhere",
        ]

    def test_a_unit_in_another_case_is_offered_the_spelling_the_vocabulary_lists(
        self, tmp_path: Path
    ) -> None:
        """The design's own example: 'RPM' against a vocabulary listing 'rpm'."""
        root = self.stating(tmp_path, "RPM", "rpm", "Nm")
        offered = self.offered(root)
        assert self.titles(offered) == [
            "Add 'RPM' to the vocabulary",
            "Rename 'RPM' to 'rpm' everywhere",
        ]
        rewritten = rewritten_by(offered[1]["edit"]["changes"])
        assert "RPM" not in rewritten["a.ddd.json"] + rewritten["b.ddd.json"]

    def test_a_unit_nothing_in_the_vocabulary_is_close_to_is_offered_no_rename(
        self, tmp_path: Path
    ) -> None:
        """The finding suggests nothing, and neither does the lightbulb."""
        offered = self.offered(self.stating(tmp_path, "bar", "rpm", "Nm"))
        assert self.titles(offered) == ["Add 'bar' to the vocabulary"]

    def test_nothing_is_offered_unless_the_finding_was_reported(self, tmp_path: Path) -> None:
        """Which keeps the offer inside the project's own severity policy, as the identity's."""
        root = self.stating(tmp_path, "rpms", "rpm", "Nm")
        assert self.offered(root, reported=[]) == []

    def test_nothing_is_offered_without_the_project_to_plan_in(self, tmp_path: Path) -> None:
        from ddd.lsp.edits import actions

        root = self.stating(tmp_path, "rpms", "rpm", "Nm")
        workspace = load_workspace(root, DiagnosticBag())
        assert workspace is not None
        path = tmp_path / "a.ddd.json"
        cache: dict[Path, Document] = {}
        offered = actions(
            navigation.index(workspace),
            path,
            read(path, cache),
            self.AT_THE_UNIT,
            cache,
            UNLISTED,
        )
        assert offered == []

    def test_a_unit_the_vocabulary_lists_by_now_is_offered_nothing(self, tmp_path: Path) -> None:
        """The finding came from an older save; the vocabulary lists the unit now."""
        assert self.offered(self.stating(tmp_path, "rpm", "rpm", "Nm")) == []

    def test_a_plan_the_project_refuses_is_not_offered(self, tmp_path: Path) -> None:
        """No units file to add the unit to, and no vocabulary to be close to: a finding from
        before the units file was taken out of the project."""
        assert self.offered(self.stating(tmp_path, "rpms")) == []

    def test_a_rename_the_plan_refuses_is_not_offered(self, tmp_path: Path) -> None:
        """The buffer spells a unit the project on disk does not state, so there is nothing
        of it to rename yet - while adding it is a plan like any other."""
        root = self.stating(tmp_path, "rpms", "rpm", "rps", "rpm2", "Nm")
        a = tmp_path / "a.ddd.json"
        typed = json.dumps(
            component(
                "A", declare("output", "Speed", unit="rpms"), declare("output", "Idle", unit="rpmx")
            ),
            indent=2,
        )
        offered = self.offered(
            root, pointer="component.interface[1].definition.unit", cache={a: Document(typed)}
        )
        assert self.titles(offered) == ["Add 'rpmx' to the vocabulary"]

    def test_a_units_file_caught_halfway_through_an_edit_is_offered_no_addition(
        self, tmp_path: Path
    ) -> None:
        """Its buffer is no json the engine can place an entry in, and no edit is better than
        one that lands somewhere else."""
        root = self.stating(tmp_path, "rpms", "rpm", "Nm")
        units = tmp_path / "units.ddd.json"
        offered = self.offered(root, cache={units: Document('{"units": ["rpm", "Nm"')})
        assert self.titles(offered) == ["Rename 'rpms' to 'rpm' everywhere"]

    def test_no_rename_is_offered_while_a_buffer_has_moved_the_unit(self, tmp_path: Path) -> None:
        root = self.stating(tmp_path, "rpms", "rpm", "Nm")
        b = tmp_path / "b.ddd.json"
        moved = json.dumps(
            component(
                "B", declare("input", "Other", unit="Nm"), declare("input", "Speed", unit="rpms")
            ),
            indent=2,
        )
        offered = self.offered(root, cache={b: Document(moved)})
        assert self.titles(offered) == ["Add 'rpms' to the vocabulary"]


class TestFrameLengths:
    def test_a_negative_length_cannot_be_followed(self) -> None:
        """A minus sign is not a count of bytes, and ``read(-1)`` would read to the end of the
        stream, which on a live pipe is never."""
        stream = io.BytesIO(b"Content-Length: -1\r\n\r\n{}")
        with pytest.raises(ProtocolError, match="-1"):
            read_message(stream)

    @pytest.mark.parametrize("spelling", [b"1_2", b"+7", b"0x10"])
    def test_a_length_python_would_read_and_a_client_never_writes(self, spelling: bytes) -> None:
        """``int()`` takes python's own spellings of a number, and ``1_2`` is twelve to it.

        Twelve bytes is not what the client counted, so the frame ends in the middle of the
        body and every header after it is read out of the tail of a message: observed as one
        parse error and then a silent exit with the next request never answered. The header is
        a count of bytes in decimal digits and nothing else.
        """
        stream = io.BytesIO(b"Content-Length: " + spelling + b"\r\n\r\n{}")
        with pytest.raises(ProtocolError, match=re.escape(spelling.decode())):
            read_message(stream)


class TestSymlinkedWorkspace:
    def test_a_document_opened_through_a_symlink_is_covered_by_its_build(
        self, tmp_path: Path
    ) -> None:
        """The loader resolves every path it reads; the client's path may be a symlink to it."""
        from ddd.build_info import BuildInfo

        real = tmp_path / "real"
        write_tree(
            real,
            {
                "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "X")),
                "b.ddd.json": component("B", declare("input", "X")),
            },
        )
        link = tmp_path / "link"
        link.symlink_to(real, target_is_directory=True)
        info = BuildInfo(project=(real / "p.ddd.json").as_posix())
        found = navigation.workspaces([info], link / "a.ddd.json")
        assert [len(loaded.workspace.components) for loaded in found] == [2]


class TestTheClientsSpelling:
    """A client's path need not be the one ``resolve()`` gives for the file it names.

    A workspace opened through a junction, a ``subst`` drive, a mapped drive, a symlinked
    directory or with a different case spells every path in it differently from the disk. The
    loader resolves everything it reads, and a client keys what it draws on the uri *string* it
    sent - so what the server says about a document it was handed has to come back in the
    words it was handed in.
    """

    def linked(self, tmp_path: Path) -> tuple[Path, Path]:
        """A small project, and a second spelling of the directory holding it."""
        real = tmp_path / "real"
        write_tree(
            real,
            {
                "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                # 'Own' is read by nobody and carries no id, so a.ddd.json has two findings
                # of its own; 'Shared' is produced by b, so it has none from the project.
                "a.ddd.json": component("A", declare("input", "Shared"), declare("output", "Own")),
                "b.ddd.json": component("B", declare("output", "Shared", id="k7m2q9xr4t8w")),
            },
        )
        link = tmp_path / "link"
        directory_link(link, real)
        return real, link

    def test_a_document_is_published_under_the_uri_it_arrived_as(self, tmp_path: Path) -> None:
        """Published under the resolved path, the squiggles go to a resource the editor is
        not showing: the document on screen keeps none of its findings."""
        _, link = self.linked(tmp_path)
        opened = link / "a.ddd.json"
        stream = framed(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"workspaceFolders": [{"uri": link.as_uri()}]},
            },
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didOpen",
                "params": {"textDocument": {"uri": opened.as_uri()}},
            },
            {"jsonrpc": "2.0", "id": 2, "method": "shutdown"},
            {"jsonrpc": "2.0", "method": "exit"},
        )
        writer = io.BytesIO()
        assert Server(stream, writer, root=link).run() == 0
        assert opened.as_uri() in published(writer)

    def test_a_document_is_not_found_to_be_its_own_containing_project(self, tmp_path: Path) -> None:
        """The candidate is resolved and the document was not, so every file matched itself -
        and was then analysed a second time as a project of one, whose inputs nobody writes."""
        _, link = self.linked(tmp_path)
        found = navigation.resolve_projects(link / "a.ddd.json", link)
        assert [loaded.path.name for loaded in found.projects] == ["p.ddd.json"]

    def test_the_findings_are_the_projects_and_are_not_doubled(self, tmp_path: Path) -> None:
        """What the two defects add up to on screen: the file read as its own project
        reported a missing producer for an input the project does produce."""
        opened = self.linked(tmp_path)[1] / "a.ddd.json"
        reports = service.collect([], [opened], opened.parent)
        codes = [entry["code"] for findings in reports.values() for entry in findings]
        assert sorted(codes) == ["missing-id", "unused-output"]

    def test_an_edit_is_addressed_to_the_document_on_screen(self, tmp_path: Path) -> None:
        """A rename keyed by the resolved path is applied to a second, unopened copy of the
        file, and the one the reader is looking at keeps the old name."""
        _, link = self.linked(tmp_path)
        opened = link / "a.ddd.json"
        position = Document(opened.read_text(encoding="utf-8")).range_of(
            "component.interface[1].definition.name"
        )["start"]
        writer = io.BytesIO()
        stream = session(
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didOpen",
                "params": {"textDocument": {"uri": opened.as_uri()}},
            },
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "textDocument/rename",
                "params": {
                    "textDocument": {"uri": opened.as_uri()},
                    "position": position,
                    "newName": "Renamed",
                },
            },
        )
        Server(stream, writer, root=link).run()
        answer = next(message for message in answered(writer) if message.get("id") == 3)
        assert list(answer["result"]["changes"]) == [opened.as_uri()]

    def test_a_file_the_client_never_opened_is_answered_under_its_resolved_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The resolved path is the only spelling anybody knows for such a file, and the only one
        a uri can be built from when the path is relative: ``as_uri`` refuses a relative path,
        and the refusal ended the session."""
        monkeypatch.chdir(tmp_path)
        server = Server(io.BytesIO(), io.BytesIO(), root=tmp_path)
        assert server._uri(Path("p.ddd.json")) == (tmp_path / "p.ddd.json").resolve().as_uri()

    def test_a_file_the_client_opened_is_answered_in_its_words_with_no_uri_built(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Built whether it was wanted or not, the uri of a relative path raised even where the
        client had said how it spells the file."""
        monkeypatch.chdir(tmp_path)
        server = Server(io.BytesIO(), io.BytesIO(), root=tmp_path)
        server._spelled[(tmp_path / "p.ddd.json").resolve()] = "file:///c%3A/work/p.ddd.json"
        assert server._uri(Path("p.ddd.json")) == "file:///c%3A/work/p.ddd.json"


class TestWorkspaceFolders:
    def test_the_folder_containing_the_document_bounds_the_search(self, tmp_path: Path) -> None:
        """A multi-root workspace: the project lives in the second folder, not the first."""
        other = tmp_path / "other"
        other.mkdir()
        home = tmp_path / "home"
        write_tree(
            home,
            {
                "p.ddd.json": project("P", "components/a.ddd.json"),
                "components/a.ddd.json": component("A", declare("local", "Deep")),
            },
        )
        server = server_module.Server(io.BytesIO(), io.BytesIO(), root=tmp_path)
        server._initialise({"workspaceFolders": [{"uri": other.as_uri()}, {"uri": home.as_uri()}]})
        found = server._projects_of(home / "components" / "a.ddd.json")
        assert [loaded.workspace.name for loaded in found] == ["P"]
        # A document under no folder at all falls back to the first, as before.
        assert server._root_for(Path("/nowhere/x.ddd.json")) == other


class TestUriHosts:
    def test_a_host_is_kept(self) -> None:
        """``file://server/share/...`` is how a client spells a network share."""
        found = server_module.uri_to_path("file://myserver/share/p.ddd.json")
        assert found == Path("//myserver/share/p.ddd.json")

    def test_localhost_is_no_host(self) -> None:
        found = server_module.uri_to_path("file://localhost/tmp/p.ddd.json")
        assert found == Path("/tmp/p.ddd.json")


class TestErasingADuplicatedKey:
    def test_a_key_stated_twice_is_cut_where_it_is_written(self) -> None:
        """The parsed object keeps a key's first position; the text keeps its last. The
        neighbours have to be read off the text, or the cut runs backwards."""
        from ddd.lsp.edits import _erase
        from ddd.lsp.ranges import Document

        text = (
            '{"component": {"name": "A", "interface": [{"scope": "output", "definition": '
            '{"name": "Foo", "kind": "measurement", "unit": "V", "datatype": "uint8", '
            '"unit": "Hz"}}]}}'
        )
        edit = _erase(Document(text), "component.interface[0].definition", "unit")
        assert edit is not None
        start, end = edit["range"]["start"], edit["range"]["end"]
        assert (start["line"], start["character"]) < (end["line"], end["character"])


class TestWhatAReconcileActionSettles:
    def test_a_storage_mismatch_is_not_claimed_by_an_interface_fix(self, tmp_path: Path) -> None:
        """The reconcile actions carry interface keys; a disagreement about the a2l
        presentation is not settled by any of them and must not be marked as if it were."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component(
                    "A", declare("output", "Speed", unit="rpm", a2l={"format": "%5.2"})
                ),
                "b.ddd.json": component(
                    "B", declare("input", "Speed", unit="1/min", a2l={"format": "%8.0"})
                ),
            },
        )
        build_record(tmp_path, tmp_path / "p.ddd.json")
        consumer = tmp_path / "b.ddd.json"
        span = Document(consumer.read_text(encoding="utf-8")).range_of(
            "component.interface[0].definition"
        )
        reported = [{"code": "definition-mismatch"}, {"code": "storage-mismatch"}]
        writer = io.BytesIO()
        server_module.Server(
            session(
                {
                    "jsonrpc": "2.0",
                    "id": 14,
                    "method": "textDocument/codeAction",
                    "params": {
                        "textDocument": {"uri": consumer.as_uri()},
                        "range": span,
                        "context": {"diagnostics": reported},
                    },
                }
            ),
            writer,
            root=tmp_path,
        ).run()
        (answer,) = answered(writer)
        assert answer["result"], "the unit disagreement is still offered a fix"
        for action in answer["result"]:
            assert [entry["code"] for entry in action["diagnostics"]] == ["definition-mismatch"]


AT_A_DECLARATION: Final = "component.interface[0].definition"
"""Where a finding about a declaration is drawn, and so where an editor asks for its fixes: over
the whole definition, whichever key is wrong."""

MISMATCH_REPORTED: Final = ({"code": "definition-mismatch", "source": "ddd", "message": "differs"},)
"""What a client sends with its request on a ``definition-mismatch``: the finding it is about."""


def offered_at(
    tmp_path: Path,
    source: str,
    files: dict[str, Any],
    reported: Sequence[dict[str, Any]] = (),
    buffers: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """What the editor offers on the declaration of ``source``, in a project of ``files`` written
    under ``tmp_path``, the client having sent ``reported``; ``buffers`` are documents open with a
    text the disk does not hold, by file name."""
    from ddd.lsp.edits import actions

    built, _ = built_of(tmp_path, **files)
    cache: dict[Path, Document] = {
        tmp_path / name: Document(json.dumps(text, indent=2))
        for name, text in (buffers or {}).items()
    }
    path = tmp_path / source
    return actions(built, path, read(path, cache), AT_A_DECLARATION, cache, reported)


def mismatches(root: Path) -> list[str]:
    """What the project written under ``root`` files as ``definition-mismatch``, in its words."""
    from ddd.analysis import analyze

    bag = DiagnosticBag()
    workspace = load_workspace(root / "p.ddd.json", bag)
    assert workspace is not None, [entry.render() for entry in bag]
    analyze(workspace, bag)
    return [entry.message for entry in bag if entry.check == "definition-mismatch"]


def preferred(offered: list[dict[str, Any]]) -> list[str]:
    """What the preferred fixes among the reconcile fixes offered change, by :func:`reconciled`."""
    return [
        change
        for change, action in zip(reconciled(offered), offered, strict=True)
        if action.get("isPreferred")
    ]


class TestAFixThatWouldNotLoad:
    """A quick fix is offered only where every file it writes still loads.

    What the loader refuses of a definition is the models' to say - an enumeration on a float, a
    string beside a unit - and no kind's key list and no storage rule says it: a fix that writes
    one leaves a file that stops loading, the project is no longer analysed, and every further
    fix is refused until somebody mends it by hand.
    """

    def titles(self, tmp_path: Path, source: str, **files: Any) -> list[str]:
        return reconciled(offered_at(tmp_path, source, files))

    def test_a_datatype_is_not_taken_from_a_float_writer_beside_an_enumeration(
        self, tmp_path: Path
    ) -> None:
        """The preferred fix of the reader, and one the loader then refuses: 'enum conversion
        'Mode_t' requires an integer datatype, got 'float32''."""
        assert "Use the datatype declared in w" not in self.titles(
            tmp_path, "r.ddd.json", **FLOAT_BESIDE_ENUM
        )

    def test_an_enumeration_is_not_given_to_the_float_writer(self, tmp_path: Path) -> None:
        assert "Apply this conversion to 1 other declaration of 'V'" not in self.titles(
            tmp_path, "r.ddd.json", **FLOAT_BESIDE_ENUM
        )

    def test_a_float_is_not_given_to_the_reader_of_an_enumeration(self, tmp_path: Path) -> None:
        assert "Apply this datatype to 1 other declaration of 'V'" not in self.titles(
            tmp_path, "w.ddd.json", **FLOAT_BESIDE_ENUM
        )

    def test_a_unit_is_not_taken_by_a_string_reader(self, tmp_path: Path) -> None:
        """'a string has no unit, got 'rpm''."""
        assert "Use the unit declared in w" not in self.titles(
            tmp_path, "r.ddd.json", **UNIT_BESIDE_TEXT
        )

    def test_a_string_is_not_given_to_a_writer_stating_a_unit(self, tmp_path: Path) -> None:
        assert "Apply this conversion to 1 other declaration of 'V'" not in self.titles(
            tmp_path, "r.ddd.json", **UNIT_BESIDE_TEXT
        )

    def test_the_fixes_that_leave_every_file_loading_are_still_offered(
        self, tmp_path: Path
    ) -> None:
        assert self.titles(tmp_path / "reader", "r.ddd.json", **FLOAT_BESIDE_ENUM) == [
            "Apply this datatype to 1 other declaration of 'V'",
            "Use the conversion declared in w",
        ]
        assert self.titles(tmp_path / "writer", "w.ddd.json", **FLOAT_BESIDE_ENUM) == [
            "Apply this conversion to 1 other declaration of 'V'"
        ]

    def test_no_fix_is_preferred_where_the_owner_s_way_is_withheld(self, tmp_path: Path) -> None:
        """The slot is the fix the ownership rule orders first, the one the lightbulb applies on
        its own: the reader's is the writer's datatype, which the loader refuses under the
        enumeration. The first fix left sends the reader's datatype out, into the writer's file,
        and none is preferred in its place."""
        offered = offered_at(tmp_path, "r.ddd.json", FLOAT_BESIDE_ENUM, MISMATCH_REPORTED)
        assert preferred(offered) == []
        assert reconciled(offered) == [
            "Apply this datatype to 1 other declaration of 'V'",
            "Use the conversion declared in w",
        ]

    def test_a_fix_is_offered_for_the_declarations_that_load_and_not_for_the_one_that_does_not(
        self, tmp_path: Path
    ) -> None:
        """An editor offers what it can: of two readers, one reads text and the writer's datatype
        would stop it loading, so the fix reaches the other and says so."""
        files = {
            "w.ddd.json": component("W", declare("output", "V", "uint16")),
            "r1.ddd.json": component(
                "R1", declare("input", "V", "uint8", conversion=TEXT, dimensions=[8])
            ),
            "r2.ddd.json": component("R2", declare("input", "V", "uint32")),
        }
        offered = offered_at(tmp_path, "w.ddd.json", files)
        (spread,) = [entry for entry in offered if "datatype" in entry["title"]]
        assert reconciled([spread]) == ["Apply this datatype to 1 other declaration of 'V'"]
        assert [uri_to_path(uri).name for uri in spread["edit"]["changes"]] == ["r2.ddd.json"]

    def test_a_dimension_is_not_taken_away_from_a_string(self, tmp_path: Path) -> None:
        """'a string states exactly one dimension, its length in bytes, got none': the writer
        states no dimension, so the reader is its only declaration that does, and taking it away
        settles the disagreement on paper."""
        files = {
            "w.ddd.json": component("W", declare("output", "V", "uint8")),
            "r.ddd.json": component(
                "R", declare("input", "V", "uint8", conversion=TEXT, dimensions=[8])
            ),
        }
        assert self.titles(tmp_path, "r.ddd.json", **files) == [
            "Use the conversion declared in w",
            "Apply this dimensions to 1 other declaration of 'V'",
        ]

    def test_the_lightbulb_the_server_answers_offers_only_what_loads(self, tmp_path: Path) -> None:
        """Through the protocol, as an editor asks: the reader's declaration, with the finding it
        carries, is offered what still loads - and none of it is preferred, the fix the owner's
        way being the one withheld."""
        write_tree(tmp_path, {"p.ddd.json": project("P", *FLOAT_BESIDE_ENUM), **FLOAT_BESIDE_ENUM})
        build_record(tmp_path, tmp_path / "p.ddd.json")
        reader = tmp_path / "r.ddd.json"
        span = Document(reader.read_text(encoding="utf-8")).range_of(AT_A_DECLARATION)
        writer = io.BytesIO()
        server_module.Server(
            session(
                {
                    "jsonrpc": "2.0",
                    "id": 15,
                    "method": "textDocument/codeAction",
                    "params": {
                        "textDocument": {"uri": reader.as_uri()},
                        "range": span,
                        "context": {"diagnostics": [{"code": "definition-mismatch"}]},
                    },
                }
            ),
            writer,
            root=tmp_path,
        ).run()
        (answer,) = answered(writer)
        assert [action["title"] for action in answer["result"] if action.get("isPreferred")] == []
        assert reconciled(answer["result"]) == [
            "Apply this datatype to 1 other declaration of 'V'",
            "Use the conversion declared in w",
        ]

    def test_a_value_the_other_readers_agree_on_is_not_adopted_by_a_string(
        self, tmp_path: Path
    ) -> None:
        """The reader that states no unit may adopt one the others state - until it reads text.
        What is offered instead is what still loads: the writer's conversion, the text sent to
        the one declaration that can hold it, and the unit taken out of the reader that states
        it."""
        files = {
            "w.ddd.json": component("W", declare("output", "V", "uint8", dimensions=[8])),
            "r.ddd.json": component(
                "R", declare("input", "V", "uint8", conversion=TEXT, dimensions=[8])
            ),
            "q.ddd.json": component(
                "Q", declare("input", "V", "uint8", dimensions=[8], unit="rpm")
            ),
        }
        assert self.titles(tmp_path, "r.ddd.json", **files) == [
            "Use the conversion declared in w",
            "Apply this conversion to 1 other declaration of 'V'",
            "Remove the unit from 1 other declaration of 'V'",
        ]

    def test_a_key_is_taken_out_of_the_declarations_that_can_do_without_it(
        self, tmp_path: Path
    ) -> None:
        """A writer stating no dimension may ask the others to state none, and the one that reads
        text is not asked: it is left to state the one dimension a string is."""
        files = {
            "w.ddd.json": component("W", declare("output", "V", "uint8")),
            "r1.ddd.json": component(
                "R1", declare("input", "V", "uint8", conversion=TEXT, dimensions=[8])
            ),
            "r2.ddd.json": component("R2", declare("input", "V", "uint8", dimensions=[8])),
        }
        offered = offered_at(tmp_path, "w.ddd.json", files)
        (removal,) = [entry for entry in offered if entry["title"].startswith("Remove the")]
        assert reconciled([removal]) == ["Remove the dimensions from 1 other declaration of 'V'"]
        assert [uri_to_path(uri).name for uri in removal["edit"]["changes"]] == ["r2.ddd.json"]

    def test_a_datatype_is_not_taken_from_a_double_writer_beside_a_scaled_reader(
        self, tmp_path: Path
    ) -> None:
        """The models take the writer's float64 under the reader's factor of two, and the analysis
        files it as ``schema`` - 'the limits derived from 'float64' and this conversion are not
        finite' - which no severity turns down: the reader's first fix, and not one to offer."""
        assert "Use the datatype declared in w" not in self.titles(
            tmp_path, "r.ddd.json", **DOUBLE_BESIDE_SCALED
        )

    def test_a_scaling_is_not_given_to_the_double_writer(self, tmp_path: Path) -> None:
        assert "Apply this conversion to 1 other declaration of 'V'" not in self.titles(
            tmp_path, "r.ddd.json", **DOUBLE_BESIDE_SCALED
        )

    def test_a_double_is_not_given_to_the_scaled_reader(self, tmp_path: Path) -> None:
        assert "Apply this datatype to 1 other declaration of 'V'" not in self.titles(
            tmp_path, "w.ddd.json", **DOUBLE_BESIDE_SCALED
        )

    def test_the_fixes_that_keep_the_limits_finite_are_still_offered(self, tmp_path: Path) -> None:
        assert self.titles(tmp_path / "reader", "r.ddd.json", **DOUBLE_BESIDE_SCALED) == [
            "Apply this datatype to 1 other declaration of 'V'",
            "Use the conversion declared in w",
        ]
        assert self.titles(tmp_path / "writer", "w.ddd.json", **DOUBLE_BESIDE_SCALED) == [
            "Apply this conversion to 1 other declaration of 'V'"
        ]

    def test_a_dimension_is_not_taken_out_of_a_declaration_naming_a_string_type(
        self, tmp_path: Path
    ) -> None:
        """The type says the bytes are text, which no definition does: the models take a
        declaration of it with no dimension, and the analysis files ``schema`` once it is written -
        'a string states exactly one dimension, its length in bytes, got none'."""
        assert self.titles(tmp_path / "reader", "r.ddd.json", **STRING_TYPE_BESIDE_SCALAR) == [
            "Apply this dimensions to 1 other declaration of 'V'"
        ]
        assert self.titles(tmp_path / "writer", "w.ddd.json", **STRING_TYPE_BESIDE_SCALAR) == [
            "Take the dimensions the other declarations of 'V' state"
        ]

    def test_the_dimensions_of_a_grid_are_not_given_to_a_declaration_naming_a_string_type(
        self, tmp_path: Path
    ) -> None:
        assert self.titles(tmp_path / "reader", "r.ddd.json", **STRING_TYPE_BESIDE_GRID) == [
            "Apply this dimensions to 1 other declaration of 'V'"
        ]
        assert self.titles(tmp_path / "writer", "w.ddd.json", **STRING_TYPE_BESIDE_GRID) == []

    def test_a_buffer_holding_a_key_twice_is_answered_and_the_server_goes_on(
        self, tmp_path: Path
    ) -> None:
        """The buffer is read as python reads json, which takes a key typed twice and keeps the
        last; the value an action would spread is its text, and the loader refuses that text as
        ``json-syntax``. What the server used to do about it was exit: it answers, leaves that
        action out, and the next request is read."""
        files = {
            "w.ddd.json": component(
                "W", declare("output", "V", "float32", limits={"min": 0, "max": 100})
            ),
            "r.ddd.json": component(
                "R", declare("input", "V", "float32", limits={"min": 0, "max": 50})
            ),
        }
        write_tree(tmp_path, {"p.ddd.json": project("P", *files), **files})
        build_record(tmp_path, tmp_path / "p.ddd.json")
        reader = tmp_path / "r.ddd.json"
        typed = reader.read_text(encoding="utf-8").replace('"max": 50', '"max": 50, "max": 60')
        assert typed != reader.read_text(encoding="utf-8")
        writer = io.BytesIO()
        server_module.Server(
            session(
                {
                    "jsonrpc": "2.0",
                    "method": "textDocument/didOpen",
                    "params": {
                        "textDocument": {"uri": reader.as_uri(), "version": 1, "text": typed}
                    },
                },
                {
                    "jsonrpc": "2.0",
                    "id": 15,
                    "method": "textDocument/codeAction",
                    "params": {
                        "textDocument": {"uri": reader.as_uri()},
                        "range": Document(typed).range_of(AT_A_DECLARATION),
                        "context": {"diagnostics": []},
                    },
                },
                {"jsonrpc": "2.0", "id": 99, "method": "shutdown"},
                {"jsonrpc": "2.0", "method": "exit"},
            ),
            writer,
            root=tmp_path,
        ).run()
        replies = {message["id"]: message for message in answered(writer) if "id" in message}
        assert reconciled(replies[15]["result"]) == ["Use the limits declared in w"]
        assert 99 in replies, "the server read the request after it"


WRITER_NAMES_A_TYPE: Final = {
    "t.ddd.json": types(scalar_type("Speed_t", "uint8", unit="rpm")),
    "w.ddd.json": component("W", declare("output", "V", typename="Speed_t")),
    "r.ddd.json": component("R", declare("input", "V", "uint8", unit="krpm")),
}
"""A writer meaning rpm through the type it names, and a reader stating krpm: the type stores the
reader's byte under the reader's identity, so the unit is all the two disagree about."""

READER_NAMES_A_TYPE: Final = {
    "t.ddd.json": types(scalar_type("Krpm_t", "uint8", unit="krpm")),
    "w.ddd.json": component("W", declare("output", "V", "uint8", unit="rpm")),
    "r.ddd.json": component("R", declare("input", "V", typename="Krpm_t")),
}
"""The other way round: the writer states rpm, and the reader means krpm through its type."""

TWO_READERS_ONE_THROUGH_A_TYPE: Final = {
    "t.ddd.json": types(scalar_type("Krpm_t", "uint8", unit="krpm")),
    "w.ddd.json": component("W", declare("output", "V", "uint8")),
    "r1.ddd.json": component("R1", declare("input", "V", "uint8", unit="rpm")),
    "r2.ddd.json": component("R2", declare("input", "V", typename="Krpm_t")),
}
"""A writer stating no unit, a reader stating rpm, and a reader meaning krpm through its type: the
readers state two units between them, and the writer's silence is neither."""


class TestAKeyATypeStates:
    """10:I8. A declaration naming a declared type states, as the checks read it, every key the
    type fixes, though its file holds none of them: a writer naming a type gives its reader the
    type's unit, and no fix takes a key out of the declarations around a type stating it, which
    would go on stating it whatever the others lose."""

    def test_a_reader_is_offered_the_unit_its_writer_s_type_states(self, tmp_path: Path) -> None:
        """The writer's file says nothing of a unit and the writer means rpm. Read from the file
        alone, the reader's one fix took its own unit out, under a title saying the writer
        declares none, and that fix was the preferred one."""
        offered = offered_at(tmp_path, "r.ddd.json", WRITER_NAMES_A_TYPE, MISMATCH_REPORTED)
        assert reconciled(offered) == ["Use the unit declared in w"]
        assert preferred(offered) == ["Use the unit declared in w"]
        assert [entry["code"] for entry in offered[0]["diagnostics"]] == ["definition-mismatch"]

    def test_taking_the_unit_the_type_states_settles_the_mismatch(self, tmp_path: Path) -> None:
        """Applied, and the project analysed again: the reader states what the writer means, and
        nothing differs. The removal it replaces left the reader stating no unit against rpm."""
        (fix,) = offered_at(tmp_path, "r.ddd.json", WRITER_NAMES_A_TYPE, MISMATCH_REPORTED)
        for name, text in rewritten_by(fix["edit"]["changes"]).items():
            (tmp_path / name).write_text(text, encoding="utf-8", newline="")
        assert mismatches(tmp_path) == []

    def test_the_writer_is_offered_no_removal_its_type_would_undo(self, tmp_path: Path) -> None:
        """From the writer, the reader was offered to lose its unit, 'Remove the unit from 1 other
        declaration': the writer's type goes on stating rpm, and the two went on disagreeing."""
        assert offered_at(tmp_path, "w.ddd.json", WRITER_NAMES_A_TYPE, MISMATCH_REPORTED) == []
        # And not because nothing differs: the checker files the unit between the two.
        assert [s for s in mismatches(tmp_path) if "(unit: 'krpm' != 'rpm')" in s] != []

    def test_a_reader_agreeing_with_its_writer_s_type_keeps_its_unit(self, tmp_path: Path) -> None:
        """The reader means rpm, as the writer's type does, and disagrees about its volatility:
        its unit was offered out all the same, 'which w does not declare', and taking it made the
        two disagree about the unit too."""
        files = {
            **WRITER_NAMES_A_TYPE,
            "r.ddd.json": component("R", declare("input", "V", "uint8", unit="rpm", volatile=True)),
        }
        assert reconciled(offered_at(tmp_path, "r.ddd.json", files, MISMATCH_REPORTED)) == [
            "Use the volatile declared in w",
            "Apply this volatile to 1 other declaration of 'V'",
        ]

    def test_the_writer_keeps_its_unit_while_its_reader_s_type_states_one(
        self, tmp_path: Path
    ) -> None:
        """The second shape, from the writer: it was offered to take its own unit out, as a unit
        nobody else states, and that fix was preferred, while the reader's type goes on stating
        krpm."""
        assert offered_at(tmp_path, "w.ddd.json", READER_NAMES_A_TYPE, MISMATCH_REPORTED) == []
        # And not because nothing differs: the checker files the unit between the two.
        assert [s for s in mismatches(tmp_path) if "(unit: 'krpm' != 'rpm')" in s] != []

    def test_a_reader_naming_a_type_is_offered_no_removal_from_its_writer(
        self, tmp_path: Path
    ) -> None:
        """The second shape, from the reader: the writer was offered to lose its unit, 'Remove the
        unit from 1 other declaration', the one declaration it could not reach being the reader's
        own, whose type states krpm."""
        assert offered_at(tmp_path, "r.ddd.json", READER_NAMES_A_TYPE, MISMATCH_REPORTED) == []
        # And not because nothing differs: the checker files the unit between the two.
        assert [s for s in mismatches(tmp_path) if "(unit: 'krpm' != 'rpm')" in s] != []

    def test_a_writer_keeps_its_unit_while_another_reader_s_type_states_one(
        self, tmp_path: Path
    ) -> None:
        """The reader asked at states no unit and names no type, the writer states rpm, and a
        second reader means krpm through its type. Taking the writer's unit out to match this
        reader's silence leaves the second stating krpm against none: the type that keeps the key
        is another declaration's, and no removal is offered beside it. Taking the writer's unit
        still is."""
        files = {
            "t.ddd.json": types(scalar_type("Krpm_t", "uint8", unit="krpm")),
            "w.ddd.json": component("W", declare("output", "V", "uint8", unit="rpm")),
            "r.ddd.json": component("R", declare("input", "V", "uint8")),
            "q.ddd.json": component("Q", declare("input", "V", typename="Krpm_t")),
        }
        offered = offered_at(tmp_path, "r.ddd.json", files, MISMATCH_REPORTED)
        assert reconciled(offered) == ["Use the unit declared in w"]

    @pytest.mark.parametrize(
        ("files", "source"),
        [
            pytest.param(WRITER_NAMES_A_TYPE, "r.ddd.json", id="the-writer-s-type-from-the-reader"),
            pytest.param(WRITER_NAMES_A_TYPE, "w.ddd.json", id="the-writer-s-type-from-the-writer"),
            pytest.param(READER_NAMES_A_TYPE, "w.ddd.json", id="the-reader-s-type-from-the-writer"),
            pytest.param(READER_NAMES_A_TYPE, "r.ddd.json", id="the-reader-s-type-from-the-reader"),
        ],
    )
    def test_no_key_is_removed_beside_a_type_a_buffer_has_moved(
        self, tmp_path: Path, files: dict[str, Any], source: str
    ) -> None:
        """The types file is open with another type inserted above the one the index found, as a
        reader adding one leaves it before saving. What the type states is then not known, which
        is neither its value nor its silence: read as silence, every removal above came back, two
        of them preferred. Nothing is offered beside it, as nothing is beside a declaration whose
        buffer has moved it."""
        (named,) = files["t.ddd.json"]["types"]
        moved = types(scalar_type("Other_t", "uint8", unit="Hz"), named)
        buffers = {"t.ddd.json": moved}
        assert offered_at(tmp_path, source, files, MISMATCH_REPORTED, buffers) == []

    def test_a_writer_takes_no_unit_its_readers_disagree_about(self, tmp_path: Path) -> None:
        """The writer states no unit, one reader states rpm, and the other means krpm through its
        type. Read from the files alone the readers agreed, and the writer was offered to take the
        rpm 'the other declarations' state, though one of them means krpm and goes on meaning it."""
        assert (
            offered_at(tmp_path, "w.ddd.json", TWO_READERS_ONE_THROUGH_A_TYPE, MISMATCH_REPORTED)
            == []
        )

    def test_a_writer_takes_no_unit_while_a_buffer_has_moved_a_reader_s_type(
        self, tmp_path: Path
    ) -> None:
        """What the second reader's type states is not known while its entry has moved, and so
        neither is the agreement the title would claim: the consensus is withheld, as it is while
        a buffer has moved one of the declarations it is drawn from."""
        moved = types(
            scalar_type("Other_t", "uint8", unit="rpm"), scalar_type("Krpm_t", "uint8", unit="krpm")
        )
        buffers = {"t.ddd.json": moved}
        files = TWO_READERS_ONE_THROUGH_A_TYPE
        assert offered_at(tmp_path, "w.ddd.json", files, MISMATCH_REPORTED, buffers) == []


class TestWhichFixIsPreferred:
    """The fix a lightbulb applies by itself is the one the ownership rule orders first: the
    producer's answer taken, at a reader, and the producer's own sent out, at the producer. Where
    that one is withheld, none is preferred, since the next in the list goes the other way round."""

    def test_a_reader_prefers_its_producer_s_value_and_the_producer_its_own(
        self, tmp_path: Path
    ) -> None:
        files = {
            "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
            "b.ddd.json": component("B", declare("input", "Speed", unit="Hz")),
        }
        reader = offered_at(tmp_path, "b.ddd.json", files, MISMATCH_REPORTED)
        assert (reconciled(reader), preferred(reader)) == (
            ["Use the unit declared in a", "Apply this unit to 1 other declaration of 'Speed'"],
            ["Use the unit declared in a"],
        )
        producer = offered_at(tmp_path, "a.ddd.json", files, MISMATCH_REPORTED)
        assert (reconciled(producer), preferred(producer)) == (
            ["Apply this unit to 1 other declaration of 'Speed'"],
            ["Apply this unit to 1 other declaration of 'Speed'"],
        )

    def test_a_reader_s_own_value_sent_out_is_not_preferred(self, tmp_path: Path) -> None:
        """The producer states no unit, and both readers state rpm: this reader cannot take the
        producer's silence while the other keeps its unit, and what is left is its own unit sent
        out, into the producer's file - offered, and not applied by itself."""
        files = {
            "a.ddd.json": component("A", declare("output", "Speed")),
            "b.ddd.json": component("B", declare("input", "Speed", unit="rpm")),
            "c.ddd.json": component("C", declare("input", "Speed", unit="rpm")),
        }
        offered = offered_at(tmp_path, "b.ddd.json", files, MISMATCH_REPORTED)
        assert (reconciled(offered), preferred(offered)) == (
            ["Apply this unit to 1 other declaration of 'Speed'"],
            [],
        )

    def test_two_producers_prefer_no_fix(self, tmp_path: Path) -> None:
        """Two components write the variable and disagree: neither owns it, so neither one's value
        sent over the other's is a fix to apply by itself, where the producer asked was preferred
        its own, overwriting the other writer."""
        files = {
            "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
            "b.ddd.json": component("B", declare("output", "Speed", unit="Hz")),
        }
        offered = offered_at(tmp_path, "b.ddd.json", files, MISMATCH_REPORTED)
        assert (reconciled(offered), preferred(offered)) == (
            ["Apply this unit to 1 other declaration of 'Speed'", "Use the unit declared in a"],
            [],
        )

    def test_no_producer_prefers_no_fix(self, tmp_path: Path) -> None:
        """Nobody writes the variable, and of its two readers one states a unit: no owner's way
        exists, so taking the unit out is offered and not applied by itself, where it was
        preferred."""
        files = {
            "a.ddd.json": component("A", declare("input", "Speed", unit="rpm")),
            "b.ddd.json": component("B", declare("input", "Speed")),
        }
        offered = offered_at(tmp_path, "a.ddd.json", files, MISMATCH_REPORTED)
        assert (reconciled(offered), preferred(offered)) == (
            [
                "Remove this unit, which no other declaration of 'Speed' has",
                "Apply this unit to 1 other declaration of 'Speed'",
            ],
            [],
        )


class TestMessagesTheClientGetsWrong:
    """Somebody else's bytes, in the shapes a client actually sends them wrong.

    None of these is a defect in the checks, and every one of them used to end the
    conversation - which costs the reader every DDD finding on screen until the client gives
    up restarting the server.
    """

    def shutdown(self) -> tuple[dict[str, Any], dict[str, Any]]:
        return (
            {"jsonrpc": "2.0", "id": 99, "method": "shutdown"},
            {"jsonrpc": "2.0", "method": "exit"},
        )

    def test_a_code_action_whose_context_is_null_is_refused_rather_than_fatal(
        self, tmp_path: Path
    ) -> None:
        """``params.get("context", {})`` defends against the key being absent and not against
        it being there and null, which is what a client sending no diagnostics may write."""
        writer = io.BytesIO()
        stream = session(
            {
                "jsonrpc": "2.0",
                "id": 11,
                "method": "textDocument/codeAction",
                "params": {
                    "textDocument": {"uri": (tmp_path / "a.ddd.json").as_uri()},
                    "range": {
                        "start": {"line": 0, "character": 0},
                        "end": {"line": 0, "character": 0},
                    },
                    "context": None,
                },
            },
            *self.shutdown(),
        )
        assert Server(stream, writer, root=tmp_path).run() == 0
        answers = {message["id"]: message for message in answered(writer) if "id" in message}
        assert answers[11]["error"]["code"] == INVALID_PARAMS
        assert answers[99]["result"] is None

    def test_a_workspace_folder_without_a_uri_is_refused_rather_than_fatal(
        self, tmp_path: Path
    ) -> None:
        """``initialize`` is the first message of every session: ending on it means the client
        never gets a capabilities answer and the server dies before it has served anything.

        A refused handshake leaves the session unopened rather than half open, so the client
        may send a well formed one and be served from there.
        """
        writer = io.BytesIO()
        stream = framed(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"workspaceFolders": [{"name": "x"}]},
            },
            {"jsonrpc": "2.0", "id": 2, "method": "initialize", "params": {}},
            *self.shutdown(),
        )
        assert Server(stream, writer, root=tmp_path).run() == 0
        answers = {message["id"]: message for message in sent(writer) if "id" in message}
        assert answers[1]["error"]["code"] == INVALID_PARAMS
        assert answers[2]["result"]["serverInfo"]["name"] == "ddd"
        assert answers[99]["result"] is None

    def test_a_notification_the_server_cannot_read_is_answered_with_nothing(
        self, tmp_path: Path
    ) -> None:
        """A notification never gets a reply, which is what the loop's own comment says.

        It was sending one anyway, carrying ``"id": null``, and vscode-jsonrpc draws that in
        the output channel as an error the reader has no message to act on.
        """
        writer = io.BytesIO()
        stream = session({"jsonrpc": "2.0", "method": "textDocument/didOpen"}, *self.shutdown())
        assert Server(stream, writer, root=tmp_path).run() == 0
        assert [message for message in answered(writer) if "error" in message] == []

    def test_a_document_under_another_scheme_is_refused_rather_than_made_relative(
        self, tmp_path: Path
    ) -> None:
        """``untitled:Untitled-1`` has no path on disk, and reading one out of it names a
        phantom file under the server's working directory that a finding is then published
        for. Nothing on disk is nothing this server can say anything about."""
        writer = io.BytesIO()
        stream = session(
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didOpen",
                "params": {
                    "textDocument": {
                        "uri": "untitled:Untitled-1",
                        "languageId": "json",
                        "version": 1,
                        "text": "{}",
                    }
                },
            },
            {
                "jsonrpc": "2.0",
                "id": 12,
                "method": "textDocument/hover",
                "params": {
                    "textDocument": {"uri": "untitled:Untitled-1"},
                    "position": {"line": 0, "character": 0},
                },
            },
            *self.shutdown(),
        )
        assert Server(stream, writer, root=tmp_path).run() == 0
        assert published(writer) == {}
        answers = {message["id"]: message for message in answered(writer) if "id" in message}
        assert answers[12]["error"]["code"] == INVALID_PARAMS
        assert "untitled:Untitled-1" in answers[12]["error"]["message"]
        assert answers[99]["result"] is None


class TestTheLifecycle:
    """When the server is willing to serve, and what it says when it is not.

    The protocol puts a beginning and an end on the conversation and says what happens outside
    them, for a reason a diagnostics server feels as much as any other: a request served before
    `initialize` is served against workspace folders the client has not sent yet, and one
    served after `shutdown` is work done for a client that has stopped listening.
    """

    def opened(self, path: Path) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {"textDocument": {"uri": path.as_uri()}},
        }

    def published_for(self, root: Path) -> dict[str, list[dict[str, Any]]]:
        """What the same open publishes when it arrives in the order the protocol asks for."""
        writer = io.BytesIO()
        Server(
            framed(
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                self.opened(root / "a.ddd.json"),
            ),
            writer,
            root=root,
        ).run()
        return published(writer)

    def hover(self, path: Path, request_id: int) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "textDocument/hover",
            "params": {
                "textDocument": {"uri": path.as_uri()},
                "position": {"line": 0, "character": 0},
            },
        }

    def test_exiting_without_shutting_down_first_is_not_a_clean_exit(self, tmp_path: Path) -> None:
        """The protocol says so in as many words, and it is the one thing an exit code can
        tell the client: a server told to stop without being told to wind down stopped for a
        reason nobody planned, and a client that restarts it is right to."""
        stream = framed(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "method": "exit"},
        )
        assert Server(stream, io.BytesIO(), root=tmp_path).run() == 1

    def test_exiting_after_shutting_down_is_a_clean_exit(self, tmp_path: Path) -> None:
        stream = framed(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "shutdown"},
            {"jsonrpc": "2.0", "method": "exit"},
        )
        assert Server(stream, io.BytesIO(), root=tmp_path).run() == 0

    def test_a_request_before_initialize_is_refused_and_the_session_goes_on(
        self, tmp_path: Path
    ) -> None:
        """-32002 is the code the protocol reserves for exactly this, and the conversation
        proceeds normally the moment the client does send its `initialize`."""
        writer = io.BytesIO()
        stream = framed(
            self.hover(tmp_path / "a.ddd.json", 7),
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "shutdown"},
            {"jsonrpc": "2.0", "method": "exit"},
        )
        assert Server(stream, writer, root=tmp_path).run() == 0
        answers = {message["id"]: message for message in sent(writer) if "id" in message}
        assert answers[7]["error"]["code"] == SERVER_NOT_INITIALIZED
        assert answers[1]["result"]["serverInfo"]["name"] == "ddd"

    def test_a_notification_before_initialize_is_dropped(self, tmp_path: Path) -> None:
        """A notification never gets an answer, so the only thing to do with one that arrives
        too early is nothing - and the file is not analysed against a workspace the client has
        not described yet."""
        (tmp_path / "a.ddd.json").write_text('{"nope": 1}', encoding="utf-8")
        assert self.published_for(tmp_path), "the control: opened in order this file lights up"
        writer = io.BytesIO()
        stream = framed(
            self.opened(tmp_path / "a.ddd.json"),
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "shutdown"},
            {"jsonrpc": "2.0", "method": "exit"},
        )
        assert Server(stream, writer, root=tmp_path).run() == 0
        assert published(writer) == {}

    def test_a_request_after_shutdown_is_refused(self, tmp_path: Path) -> None:
        """The client has said it wants nothing more; anything it sends after that is a bug on
        its side, and serving it is work for a reader who has closed the window."""
        writer = io.BytesIO()
        stream = framed(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "shutdown"},
            self.hover(tmp_path / "a.ddd.json", 8),
            {"jsonrpc": "2.0", "method": "exit"},
        )
        assert Server(stream, writer, root=tmp_path).run() == 0
        answers = {message["id"]: message for message in sent(writer) if "id" in message}
        assert answers[8]["error"]["code"] == INVALID_REQUEST

    def test_a_notification_after_shutdown_is_dropped(self, tmp_path: Path) -> None:
        (tmp_path / "a.ddd.json").write_text('{"nope": 1}', encoding="utf-8")
        assert self.published_for(tmp_path), "the control: opened in order this file lights up"
        writer = io.BytesIO()
        stream = framed(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "shutdown"},
            self.opened(tmp_path / "a.ddd.json"),
            {"jsonrpc": "2.0", "method": "exit"},
        )
        assert Server(stream, writer, root=tmp_path).run() == 0
        assert published(writer) == {}

    def test_initializing_twice_is_refused(self, tmp_path: Path) -> None:
        """The second one would re-point the workspace folders under every answer already
        given, so the protocol makes it an invalid request rather than a second beginning."""
        writer = io.BytesIO()
        stream = framed(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 3, "method": "shutdown"},
            {"jsonrpc": "2.0", "method": "exit"},
        )
        assert Server(stream, writer, root=tmp_path).run() == 0
        answers = {message["id"]: message for message in sent(writer) if "id" in message}
        assert answers[1]["result"]["serverInfo"]["name"] == "ddd"
        assert answers[2]["error"]["code"] == INVALID_REQUEST

    def test_exit_without_initialize_still_exits(self, tmp_path: Path) -> None:
        """A client that gave up before saying hello still gets a server that goes away; the
        protocol names this case so that such a server is not left running."""
        assert Server(framed({"jsonrpc": "2.0", "method": "exit"}), io.BytesIO()).run() == 1


class TestADefectInAnsweringOneMessage:
    """10:I13 and decision 10.1: a defect in answering one message costs that answer, not the
    session.

    The front end reports through findings rather than raising, but what translates them is code
    like any other, and a hover that raised ended the session: every finding on screen went with
    it, and a client gives up restarting a server that the next hover ends again. Each test makes
    one handler raise, as a defect would.
    """

    @staticmethod
    def defect(*_: Any) -> None:
        """A handler failing as a defect of the server would, whatever it is asked."""
        msg = "a defect of the server's own"
        raise RuntimeError(msg)

    def hover(self, path: Path) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "textDocument/hover",
            "params": {
                "textDocument": {"uri": path.as_uri()},
                "position": {"line": 0, "character": 0},
            },
        }

    def test_a_request_the_server_fails_on_is_answered_and_the_session_goes_on(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Answered with the protocol's internal error, -32603, naming the method and the fault,
        with the trace on stderr, which is the server's log; and the next message is read."""
        monkeypatch.setattr(Server, "_hover", self.defect)
        writer = io.BytesIO()
        stream = session(self.hover(tmp_path / "a.ddd.json"), *END)
        assert Server(stream, writer, root=tmp_path).run() == 0
        failed, ended = answered(writer)
        assert failed == error(
            7,
            -32603,
            "textDocument/hover failed on a defect of ddd (RuntimeError: a defect of the server's "
            "own); the trace is in the server's log",
        )
        assert ended == response(99, None)
        trace = capsys.readouterr().err
        assert trace.startswith(
            "ddd: textDocument/hover failed on a defect of this server, and the session goes on\n"
            "Traceback (most recent call last):\n"
        )
        assert trace.endswith("RuntimeError: a defect of the server's own\n")

    def test_a_notification_the_server_fails_on_is_answered_with_nothing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A notification never gets an answer, a failed one included: the trace on stderr is all
        there is of it, and the next message is read. A relative record ended the session on the
        first ``didOpen``, which is a notification. The document is open, with the text every
        client sends, and not on disk yet: a path that is neither is not checked at all."""
        monkeypatch.setattr(Server, "refresh", self.defect)
        opened = {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {"textDocument": {"uri": (tmp_path / "a.ddd.json").as_uri(), "text": ""}},
        }
        writer = io.BytesIO()
        assert Server(session(opened, *END), writer, root=tmp_path).run() == 0
        assert answered(writer) == [response(99, None)]
        trace = capsys.readouterr().err
        assert trace.startswith(
            "ddd: textDocument/didOpen failed on a defect of this server, and the session goes "
            "on\nTraceback (most recent call last):\n"
        )
        assert trace.endswith("RuntimeError: a defect of the server's own\n")

    def test_an_interrupt_still_ends_the_run(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The net is for defects, and an interrupt is not one: it is no ``Exception``, and it
        still ends the run."""

        def interrupted(*_: Any) -> None:
            raise KeyboardInterrupt

        monkeypatch.setattr(Server, "_hover", interrupted)
        stream = session(self.hover(tmp_path / "a.ddd.json"), *END)
        with pytest.raises(KeyboardInterrupt):
            Server(stream, io.BytesIO(), root=tmp_path).run()


class TestHoversThatEndedTheSession:
    """10:I13: hovers that raised out of the session, each now answered with what the object is.

    Asked through a session, as a client asks: each of these ended it.
    """

    def hovered(self, tmp_path: Path, *declarations: dict[str, Any]) -> str:
        """What a hover on the name of the last of ``declarations`` answers, in a project above
        the component declaring them."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", *declarations),
            },
        )
        path = tmp_path / "a.ddd.json"
        position = Document(path.read_text(encoding="utf-8")).range_of(
            f"component.interface[{len(declarations) - 1}].definition.name"
        )["start"]
        request = {
            "jsonrpc": "2.0",
            "id": 12,
            "method": "textDocument/hover",
            "params": {"textDocument": {"uri": path.as_uri()}, "position": position},
        }
        writer = io.BytesIO()
        assert Server(session(request, *END), writer, root=tmp_path).run() == 0
        (answer,) = [message for message in answered(writer) if message.get("id") == 12]
        described: str = answer["result"]["contents"]["value"]
        return described

    def test_an_init_that_states_no_value_draws_nothing(self, tmp_path: Path) -> None:
        """A parameter whose ``init`` is ``[]``, which the checks report as ``init-invalid``: a
        scalar has no dimension to take the width of a row from, so the rows were cut at a width
        of nothing. There is nothing to draw, and nothing is drawn."""
        described = self.hovered(
            tmp_path, declare("output", "K", "uint8", kind="parameter", init=[])
        )
        assert described.startswith("**K** — parameter, `uint8`")
        assert described.endswith("| volatile | no |")

    def test_an_axis_whose_init_states_no_point_has_no_span(self, tmp_path: Path) -> None:
        """The same init on an axis, met from the curve it gives a shape: the span of its points
        was asked of no points."""
        described = self.hovered(
            tmp_path,
            declare("output", "X", "uint8", kind="axis", size=2, init=[]),
            declare("output", "K", "uint8", kind="curve", axis="X", init=[1, 2]),
        )
        assert "| axis | `X` |" in described

    def test_a_float64_block_spanning_more_than_a_float_holds_is_drawn(
        self, tmp_path: Path
    ) -> None:
        """A valid project whose init runs from ``-1.7e308`` to ``1.7e308``: both are doubles and
        the distance between them is not, so the span was infinite and the highest value's
        position was NaN. Each bar is drawn where it falls."""
        described = self.hovered(
            tmp_path,
            declare(
                "output",
                "K",
                "float64",
                kind="value_block",
                dimensions=[3],
                init=[-1.7e308, 1.7e308, 0],
            ),
        )
        assert main(["check", str(tmp_path / "p.ddd.json")]) == EXIT_OK
        assert described.endswith("```text\n▁█▅\n-1.7e+308 .. 1.7e+308\n```")


class TestWhatTheServerSaysAboutARecord:
    """The three answers to "which project is this file checked through"."""

    def test_a_junction_under_the_build_tree_yields_one_record(self, tmp_path: Path) -> None:
        """``rglob`` walks a junction as if it were a directory - python 3.13 keeps ``**`` out
        of a symlink and a junction is not one - so a loop under ``build/`` produced a
        different spelling of the same record per level: twenty-two records, twenty-two log
        lines and every finding of the project published twenty-two times.

        Windows is where this bites: on posix ``**`` declines to follow the link at all, and
        the one record is found by the short way round.
        """
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X")),
            },
        )
        build_record(tmp_path, tmp_path / "p.ddd.json")
        directory_link(tmp_path / "build" / "loop", tmp_path / "build")
        assert build_files(tmp_path) == [
            tmp_path / "build" / "ddd" / "firmware.elf" / BUILD_INFO_FILENAME
        ]

    def test_the_log_says_a_file_under_a_project_is_checked_through_it(
        self, tmp_path: Path
    ) -> None:
        """The line used to say every file is checked on its own, which denies exactly the
        findings the next message publishes: a component under a project file is checked
        through that project, record or no record."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("input", "X")),
            },
        )
        writer = io.BytesIO()
        Server(io.BytesIO(), writer, root=tmp_path).refresh(tmp_path / "a.ddd.json")
        (said,) = [
            message["params"]["message"]
            for message in sent(writer)
            if message.get("method") == "window/logMessage"
        ]
        assert "no ddd-build.json found" in said
        assert "a project" in said
        # The very finding the old wording said would not be reported.
        assert [
            entry["code"] for entry in published(writer)[(tmp_path / "a.ddd.json").as_uri()]
        ] == ["missing-producer"]

    def test_a_record_naming_a_plugin_check_nobody_registers_is_reported(
        self, tmp_path: Path
    ) -> None:
        """``ddd check -W layout/no-such=ignore`` refuses the run with a usage error; the
        server took the same record, kept the override provisional and never held it to the
        plugins that loaded, so a build silencing a check by a name nothing registers looked
        exactly like a build silencing one that exists."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X")),
            },
        )
        build_record(tmp_path, tmp_path / "p.ddd.json", severity=["layout/no-such=ignore"])
        reports = service.collect(discover(tmp_path))
        published_for = reports[tmp_path / "p.ddd.json"]
        assert [entry["code"] for entry in published_for] == ["plugin-invalid"]
        assert "layout/no-such" in published_for[0]["message"]

    def test_a_record_naming_a_plugin_check_that_is_registered_is_honoured(
        self, tmp_path: Path
    ) -> None:
        """The control: the same shape of override, for a check a loaded plugin does register,
        goes on working and reports nothing about itself."""
        write_tree(
            tmp_path,
            {
                "tools/registering_plugin.py": REGISTERING_PLUGIN,
                "p.ddd.json": project("P", "a.ddd.json", plugins=["tools/registering_plugin.py"]),
                "a.ddd.json": component("A", declare("local", "X")),
            },
        )
        build_record(tmp_path, tmp_path / "p.ddd.json", severity=["demo/tagged=ignore"])
        reports = service.collect(discover(tmp_path))
        assert "plugin-invalid" not in {
            entry["code"] for findings in reports.values() for entry in findings
        }


class TestHoveringOnADeclaredType:
    """The type's own entry, which until now answered only for an external type.

    A reader in a types file gets the same nothing for every name they point at, while the
    identical name pointed at from a component describes the variable that names it. Both
    positions are about the type; one of them has no variable to describe instead.
    """

    def workspace(self, tmp_path: Path) -> list[Any]:
        from ddd.build_info import BuildInfo

        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "t.ddd.json", "a.ddd.json"),
                "t.ddd.json": {
                    "types": [
                        {
                            "type": "scalar",
                            "name": "Temperature_t",
                            "description": "a temperature as this ecu stores one",
                            "datatype": "uint16",
                            "unit": "degC",
                            "conversion": {"factor": 0.1, "offset": -40},
                        },
                        {
                            "type": "struct",
                            "name": "Sample_t",
                            "description": "one reading and how good it is",
                            "members": [
                                {
                                    "name": "value",
                                    "member": "value",
                                    "typename": "Temperature_t",
                                },
                                {
                                    "name": "quality",
                                    "member": "value",
                                    "datatype": "uint8",
                                    "conversion": {},
                                },
                                {
                                    "name": "history",
                                    "member": "value",
                                    "datatype": "uint8",
                                    "conversion": {},
                                    "dimensions": [4],
                                },
                                {
                                    "name": "ready",
                                    "member": "bits",
                                    "datatype": "uint8",
                                    "conversion": {},
                                    "bits": 1,
                                },
                            ],
                        },
                    ]
                },
                "a.ddd.json": component(
                    "A", declare("output", "Inlet", typename="Sample_t", description="the inlet")
                ),
            },
        )
        info = BuildInfo(project=(tmp_path / "p.ddd.json").as_posix())
        return list(navigation.workspaces([info], tmp_path / "t.ddd.json"))

    def hovered(self, tmp_path: Path, name: str, pointer: str) -> Any:
        projects = self.workspace(tmp_path)
        path = tmp_path / name
        document = Document(path.read_text(encoding="utf-8"))
        position = document.range_of(pointer)["start"]
        writer = io.BytesIO()
        Server(
            session(
                {
                    "jsonrpc": "2.0",
                    "id": 7,
                    "method": "textDocument/hover",
                    "params": {
                        "textDocument": {"uri": path.as_uri()},
                        "position": position,
                    },
                }
            ),
            writer,
            root=tmp_path,
        ).run()
        assert projects
        (answer,) = answered(writer)
        return answer["result"]

    def test_a_structures_own_entry_describes_it(self, tmp_path: Path) -> None:
        result = self.hovered(tmp_path, "t.ddd.json", "types[1].name")
        assert result is not None
        rendered = result["contents"]["value"]
        assert "**Sample_t**" in rendered
        assert "one reading and how good it is" in rendered
        assert "**4 members**" in rendered
        assert "`Temperature_t`" in rendered
        assert "`uint8`" in rendered
        # Spelled as the file spells it: an array carries its dimensions and a bitfield its
        # width, which is what tells a reader what the member costs.
        assert "`uint8[4]`" in rendered
        assert "`uint8:1`" in rendered

    def test_a_scalar_types_own_entry_describes_it(self, tmp_path: Path) -> None:
        rendered = self.hovered(tmp_path, "t.ddd.json", "types[0].name")["contents"]["value"]
        assert "**Temperature_t**" in rendered
        assert "`uint16`" in rendered
        assert "degC" in rendered

    def test_a_typename_inside_a_types_file_describes_the_type_it_names(
        self, tmp_path: Path
    ) -> None:
        """The member says ``"typename": "Temperature_t"`` and the type is declared six lines
        above it; there is no variable here for the old answer to describe instead."""
        rendered = self.hovered(tmp_path, "t.ddd.json", "types[1].members[0].typename")["contents"][
            "value"
        ]
        assert "**Temperature_t**" in rendered

    def test_a_typename_on_a_declaration_still_describes_the_variable(self, tmp_path: Path) -> None:
        """The control, and the reason the type answer is a fallback rather than a winner:
        from a component, what a reader is asking about is the variable."""
        rendered = self.hovered(
            tmp_path, "a.ddd.json", "component.interface[0].definition.typename"
        )["contents"]["value"]
        assert "**Inlet**" in rendered

    def test_a_name_no_project_declares_as_a_type_says_nothing(self, tmp_path: Path) -> None:
        from ddd.lsp.hover import describe_type

        assert describe_type(self.workspace(tmp_path), "Nothing_t") is None


class TestInsertingAKey:
    """Where a quick fix puts a key a definition does not have, and how far in."""

    def document(self, separator: str) -> Any:
        """One declaration whose last member is written over several lines.

        ``separator`` goes inside a description above it: a line break to ``str.splitlines()``
        and an ordinary character to everything that counts positions.
        """
        return Document(
            "{\n"
            '  "component": {\n'
            '    "name": "A",\n'
            f'    "description": "before{separator}after",\n'
            '    "interface": [\n'
            "      {\n"
            '        "scope": "output",\n'
            '        "definition": {\n'
            '          "name": "Speed",\n'
            '          "kind": "measurement",\n'
            '          "datatype": "uint8",\n'
            '          "conversion": {\n'
            '            "kind": "identity"\n'
            "          }\n"
            "        }\n"
            "      }\n"
            "    ]\n"
            "  }\n"
            "}"
        )

    @pytest.mark.parametrize("separator", ["", "\u2028", "\x85"])
    def test_the_indentation_is_the_one_of_the_line_positions_count(self, separator: str) -> None:
        """``str.splitlines()`` breaks on a dozen characters a newline is not - a form feed, a
        NEL, U+2028 - while every position this server hands out counts ``\n`` alone. One of
        them in a description above the declaration put the two out of step, and the key was
        inserted with the indentation of the line before: the last member here is written over
        several lines, so that is twelve spaces where the closing brace stands at ten.
        """
        from ddd.lsp.edits import _insert

        edit = _insert(
            self.document(separator), "component.interface[0].definition", "unit", '"rpm"'
        )
        assert edit is not None
        assert edit["newText"] == ',\n          "unit": "rpm"'


class TestHoverMarkdownThatHoldsMarkdown:
    """A unit and a condition are free text, and two of its characters are markdown.

    A backtick ends the code span the value sits in and a pipe ends the table cell, whatever
    it sits in - so a unit an editor accepts without complaint (``ddd check --standalone``
    passes it) drew a table with the row split in two and the rest of the value loose in it.
    """

    def described(self, tmp_path: Path, **definition: Any) -> str:
        from ddd.build_info import BuildInfo
        from ddd.lsp.hover import describe, resolve

        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "Speed", **definition)),
            },
        )
        info = BuildInfo(project=(tmp_path / "p.ddd.json").as_posix())
        dictionary = resolve(navigation.workspaces([info], tmp_path / "a.ddd.json"))
        assert dictionary is not None
        rendered = describe(dictionary, "Speed")
        assert rendered is not None
        return rendered

    def rows_of(self, rendered: str) -> dict[str, str]:
        """Each table row as the editor's markdown parser divides it, by its label.

        Split on the unescaped pipes alone, which is exactly what a renderer does: a row that
        carries one too many is a row with a cell the author did not write.
        """
        rows = {}
        for line in rendered.splitlines():
            cells = re.split(r"(?<!\\)\|", line)
            if len(cells) == 4 and cells[1].strip() not in {"", "---"}:
                rows[cells[1].strip()] = cells[2].strip()
        return rows

    def test_a_unit_holding_a_backtick_and_a_pipe_stays_in_its_cell(self, tmp_path: Path) -> None:
        rendered = self.described(tmp_path, unit="a`b|c")
        assert self.rows_of(rendered)["unit"] == "``a`b\\|c``"

    def test_a_condition_holding_a_pipe_stays_in_its_cell(self, tmp_path: Path) -> None:
        """``#if defined(A) || defined(B)`` is an ordinary condition to write."""
        rendered = self.described(tmp_path, condition="defined(A) || defined(B)")
        assert self.rows_of(rendered)["condition"] == "`defined(A) \\|\\| defined(B)`"

    def test_a_unit_that_is_only_a_backtick_is_still_a_span(self, tmp_path: Path) -> None:
        """A span whose text begins or ends with a backtick needs a space inside the fence,
        or the fence swallows it."""
        assert self.rows_of(self.described(tmp_path, unit="`"))["unit"] == "`` ` ``"

    def test_an_ordinary_unit_is_left_alone(self, tmp_path: Path) -> None:
        assert self.rows_of(self.described(tmp_path, unit="rpm"))["unit"] == "`rpm`"


class TestAWatchedFileChanging:
    """A file changed on disk by something other than the editor.

    The extension watches `**/*.ddd.json` and says why in as many words: a save is not the
    only way a description changes - a build writes them, and a branch switch rewrites them
    all - and neither of those is a document event. The notification it sends for them had no
    branch in the server at all, so the findings and the jumps went on describing the files as
    they were until somebody happened to save one.
    """

    def workspace(self, tmp_path: Path) -> None:
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Shared")),
                "b.ddd.json": component("B", declare("input", "Shared")),
            },
        )
        build_record(tmp_path, tmp_path / "p.ddd.json")

    def changed(self, *paths: Path) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "method": "workspace/didChangeWatchedFiles",
            "params": {"changes": [{"uri": path.as_uri(), "type": 2} for path in paths]},
        }

    def opened(self, path: Path) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {
                "textDocument": {
                    "uri": path.as_uri(),
                    "languageId": "json",
                    "version": 1,
                    "text": path.read_text(encoding="utf-8"),
                }
            },
        }

    def test_the_open_document_is_checked_again(self, tmp_path: Path) -> None:
        self.workspace(tmp_path)
        consumer = tmp_path / "b.ddd.json"
        producer = tmp_path / "a.ddd.json"
        writer = io.BytesIO()
        server = Server(io.BytesIO(), writer, root=tmp_path)
        assert server._handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        assert server._handle(self.opened(consumer))
        # Nothing is wrong yet, and a file with nothing wrong is published only to withdraw
        # what it said last time.
        assert consumer.as_uri() not in published(writer)

        write_tree(tmp_path, {"a.ddd.json": component("A", declare("output", "Other"))})
        writer = io.BytesIO()
        server.writer = writer
        assert server._handle(self.changed(producer))
        assert [entry["code"] for entry in published(writer)[consumer.as_uri()]] == [
            "missing-producer"
        ]

    def test_a_change_with_nothing_open_still_republishes_the_project(self, tmp_path: Path) -> None:
        """A branch switch while no description is open: the Problems list is still on screen
        and still describes the files as they were."""
        self.workspace(tmp_path)
        writer = io.BytesIO()
        server = Server(io.BytesIO(), writer, root=tmp_path)
        assert server._handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        write_tree(tmp_path, {"a.ddd.json": component("A", declare("output", "Other"))})
        assert server._handle(self.changed(tmp_path / "a.ddd.json"))
        drawn = published(writer)[(tmp_path / "b.ddd.json").as_uri()]
        assert [entry["code"] for entry in drawn] == ["missing-producer"]

    def test_a_notification_carrying_no_change_changes_nothing(self, tmp_path: Path) -> None:
        self.workspace(tmp_path)
        writer = io.BytesIO()
        server = Server(io.BytesIO(), writer, root=tmp_path)
        assert server._handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        assert server._handle(self.changed())
        assert published(writer) == {}


class Arrivals:
    """An inbox handing :meth:`Server._serve` what was read off the stream, arrival by arrival.

    What one arrival holds is queued together, as the reading thread queues what a client sent at
    once: the server takes the first, and the rest are behind it. The next arrival lands only when
    the server asks for more with this one all taken, where a queue makes it wait, so what a later
    arrival holds had not been sent while the server handled the ones before. That is the client's
    timing, said by the test rather than left to a race between two threads.
    """

    def __init__(self, writer: io.BytesIO, *arrivals: Sequence[Any]) -> None:
        self.writer = writer
        self.coming = [list(arrival) for arrival in arrivals]
        self.queued: list[Any] = []
        self.landed: list[list[dict[str, Any]]] = []
        """What the server had written when each arrival landed."""
        self.taken = 0
        """How many things the server has taken so far."""

    def get(self) -> Any:
        if not self.queued:
            self.landed.append(sent(self.writer))
            self.queued = self.coming.pop(0)
        self.taken += 1
        return self.queued.pop(0)

    def qsize(self) -> int:
        return len(self.queued)


class Typing(Arrivals):
    """Arrivals while the reader goes on typing: behind each ``didChange`` the server takes,
    another lands, ``keystrokes`` more in all, as a client sends one at every key."""

    def __init__(self, writer: io.BytesIO, *arrivals: Sequence[Any], keystrokes: int) -> None:
        super().__init__(writer, *arrivals)
        self.keystrokes = keystrokes

    def get(self) -> Any:
        taken = super().get()
        if taken.get("method") == "textDocument/didChange" and self.keystrokes:
            self.keystrokes -= 1
            self.queued.append(taken)
        return taken


class TestDocumentsMarkedTogetherAreCheckedTogether:
    """10:I12: the documents that messages queued together mark are checked together, each
    project once.

    A save reaches the server twice, as a ``didSave`` and as the watch event the extension sends
    for the file the editor wrote, and the event checked every open document on its own: ten
    documents open, and the project was analysed once for the save and ten times more for the
    event that followed it, while every hover and rename waited behind them. Most of these hand
    the server what was read arrival by arrival (:class:`Arrivals`), so that what came together
    is the test's to say.
    """

    def tabs(self, tmp_path: Path) -> list[Path]:
        """Ten open documents, the components of the one project a build record names, each
        reading what nobody writes."""
        names = [f"c{number}.ddd.json" for number in range(10)]
        write_tree(
            tmp_path,
            {"p.ddd.json": project("P", *names)}
            | {
                name: component(f"C{number}", declare("input", f"V{number}"))
                for number, name in enumerate(names)
            },
        )
        build_record(tmp_path, tmp_path / "p.ddd.json", severity=["missing-id=ignore"])
        return [tmp_path / name for name in names]

    def hello(self, tmp_path: Path) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"workspaceFolders": [{"uri": tmp_path.as_uri()}]},
        }

    def opened(self, path: Path) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {
                "textDocument": {
                    "uri": path.as_uri(),
                    "languageId": "json",
                    "version": 1,
                    "text": path.read_text(encoding="utf-8"),
                }
            },
        }

    def saved(self, path: Path) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "method": "textDocument/didSave",
            "params": {"textDocument": {"uri": path.as_uri()}},
        }

    def watched(self, path: Path) -> dict[str, Any]:
        """The watch event the extension sends for a file the editor saved."""
        return {
            "jsonrpc": "2.0",
            "method": "workspace/didChangeWatchedFiles",
            "params": {"changes": [{"uri": path.as_uri(), "type": 2}]},
        }

    def typed(self, path: Path) -> dict[str, Any]:
        """A keystroke in ``path``, which the server keeps and checks nothing for."""
        return {
            "jsonrpc": "2.0",
            "method": "textDocument/didChange",
            "params": {
                "textDocument": {"uri": path.as_uri(), "version": 2},
                "contentChanges": [{"text": path.read_text(encoding="utf-8")}],
            },
        }

    def hover(self, path: Path) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "textDocument/hover",
            "params": {
                "textDocument": {"uri": path.as_uri()},
                "position": {"line": 0, "character": 0},
            },
        }

    def analyses(self, monkeypatch: pytest.MonkeyPatch, inbox: Arrivals) -> Counter[int]:
        """Every analysis a check runs, counted by the arrival it ran in, the first being 1."""
        ran: Counter[int] = Counter()
        original = service.analyze

        def counted(*args: Any, **kwargs: Any) -> Any:
            ran[len(inbox.landed)] += 1
            return original(*args, **kwargs)

        monkeypatch.setattr(service, "analyze", counted)
        return ran

    def test_a_save_and_its_watch_event_queued_together_are_one_analysis(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """So are the ``didOpen`` of ten documents, which an editor sends for the files a rename
        rewrites; and each check is published before the server waits for what has not arrived."""
        tabs = self.tabs(tmp_path)
        writer = io.BytesIO()
        inbox = Arrivals(
            writer,
            [self.hello(tmp_path), *map(self.opened, tabs)],
            [self.saved(tabs[0]), self.watched(tabs[0])],
            END,
        )
        ran = self.analyses(monkeypatch, inbox)
        assert Server(io.BytesIO(), writer, root=tmp_path)._serve(inbox) == 0
        assert ran == Counter({1: 1, 2: 1})
        checked = inbox.landed[2][len(inbox.landed[1]) :]
        assert sorted(message["params"]["uri"] for message in checked) == sorted(
            tab.as_uri() for tab in tabs
        )
        assert {
            entry["code"] for message in checked for entry in message["params"]["diagnostics"]
        } == {"missing-producer"}

    def test_a_save_and_its_watch_event_apart_are_one_analysis_each(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The watch event lands after the save was checked, so it is a check of its own."""
        tabs = self.tabs(tmp_path)
        writer = io.BytesIO()
        inbox = Arrivals(
            writer,
            [self.hello(tmp_path), *map(self.opened, tabs)],
            [self.saved(tabs[0])],
            [self.watched(tabs[0])],
            END,
        )
        ran = self.analyses(monkeypatch, inbox)
        assert Server(io.BytesIO(), writer, root=tmp_path)._serve(inbox) == 0
        assert ran == Counter({1: 1, 2: 1, 3: 1})

    def test_each_project_is_analysed_once_however_many_of_its_documents_are_open(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Five documents open in each of two projects no record names, each found above its
        files: their ``didOpen`` are one analysis of each, and so is a watch event. Nothing in
        them is an error, which would stop an analysis of the project a second time anyway."""
        names = [f"c{number}.ddd.json" for number in range(5)]
        tree: dict[str, Any] = {}
        for folder in ("one", "two"):
            tree[f"{folder}/p.ddd.json"] = project(folder.title(), *names)
            for number, name in enumerate(names):
                tree[f"{folder}/{name}"] = component(f"C{number}", declare("local", f"V{number}"))
        write_tree(tmp_path, tree)
        tabs = [tmp_path / folder / name for folder in ("one", "two") for name in names]
        writer = io.BytesIO()
        inbox = Arrivals(
            writer,
            [self.hello(tmp_path), *map(self.opened, tabs)],
            [self.watched(tabs[0])],
            END,
        )
        ran = self.analyses(monkeypatch, inbox)
        assert Server(io.BytesIO(), writer, root=tmp_path)._serve(inbox) == 0
        assert ran == Counter({1: 2, 2: 2})

    def test_each_document_is_searched_for_within_its_own_workspace_folder(
        self, tmp_path: Path
    ) -> None:
        """Two workspace folders, a document open in each and its project a directory above it:
        checked together, each search above is bounded by the folder holding its document, as
        when each was checked by itself."""
        write_tree(
            tmp_path,
            {
                "one/p.ddd.json": project("One", "sub/a.ddd.json"),
                "one/sub/a.ddd.json": component("A", declare("input", "X")),
                "two/p.ddd.json": project("Two", "sub/b.ddd.json"),
                "two/sub/b.ddd.json": component("B", declare("input", "Y")),
            },
        )
        a, b = tmp_path / "one" / "sub" / "a.ddd.json", tmp_path / "two" / "sub" / "b.ddd.json"
        hello = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "workspaceFolders": [
                    {"uri": (tmp_path / "one").as_uri()},
                    {"uri": (tmp_path / "two").as_uri()},
                ]
            },
        }
        writer = io.BytesIO()
        inbox = Arrivals(writer, [hello, self.opened(a), self.opened(b)], END)
        assert Server(io.BytesIO(), writer, root=tmp_path)._serve(inbox) == 0
        final = published(writer)
        assert [entry["code"] for entry in final[a.as_uri()]] == ["missing-producer"]
        assert [entry["code"] for entry in final[b.as_uri()]] == ["missing-producer"]

    def test_a_request_queued_behind_them_is_answered_once_they_are_checked(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An answer may be about what the check finds, so the check comes first, before the
        keystroke still queued behind the request."""
        tabs = self.tabs(tmp_path)
        writer = io.BytesIO()
        inbox = Arrivals(
            writer,
            [self.hello(tmp_path), *map(self.opened, tabs)],
            [self.saved(tabs[0]), self.watched(tabs[0]), self.hover(tabs[0]), self.typed(tabs[0])],
            END,
        )
        ran = self.analyses(monkeypatch, inbox)
        assert Server(io.BytesIO(), writer, root=tmp_path)._serve(inbox) == 0
        assert ran == Counter({1: 1, 2: 1})
        during = inbox.landed[2][len(inbox.landed[1]) :]
        assert [message.get("method", message.get("id")) for message in during] == [
            "textDocument/publishDiagnostics"
        ] * 10 + [7]

    def test_the_check_is_not_held_while_keystrokes_keep_coming(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Due once what was queued behind the save is handled: held until the queue empties, it
        would wait for as long as the reader goes on typing."""
        tabs = self.tabs(tmp_path)
        writer = io.BytesIO()
        opening = [self.hello(tmp_path), *map(self.opened, tabs)]
        inbox = Typing(
            writer, opening, [self.saved(tabs[0]), self.typed(tabs[1])], END, keystrokes=50
        )
        taken: list[int] = []
        original = service.analyze

        def counted(*args: Any, **kwargs: Any) -> Any:
            taken.append(inbox.taken)
            return original(*args, **kwargs)

        monkeypatch.setattr(service, "analyze", counted)
        assert Server(io.BytesIO(), writer, root=tmp_path)._serve(inbox) == 0
        assert taken == [len(opening), len(opening) + 2]

    def test_a_check_withdraws_only_the_files_it_reported_on(self, tmp_path: Path) -> None:
        """10:I1's rule holds for a check of what arrived together: opening a file of another
        project keeps this one's findings."""
        write_tree(
            tmp_path,
            {
                "one/p.ddd.json": project("One", "a.ddd.json"),
                "one/a.ddd.json": component("A", declare("input", "X")),
                "two/p.ddd.json": project("Two", "b.ddd.json"),
                "two/b.ddd.json": component("B", declare("input", "Y")),
            },
        )
        a, b = tmp_path / "one" / "a.ddd.json", tmp_path / "two" / "b.ddd.json"
        writer = io.BytesIO()
        inbox = Arrivals(writer, [self.hello(tmp_path), self.opened(a)], [self.opened(b)], END)
        assert Server(io.BytesIO(), writer, root=tmp_path)._serve(inbox) == 0
        final = published(writer)
        assert [entry["code"] for entry in final[b.as_uri()]] == ["missing-producer"]
        assert [entry["code"] for entry in final[a.as_uri()]] == ["missing-producer"], (
            "a's error was withdrawn"
        )

    def test_a_defect_in_a_check_costs_that_check_alone(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Answered as a defect in a notification is (10:I13): with nothing, and its trace on
        stderr, naming the messages that marked the documents. The next message is handled, and
        the documents are not checked again for it."""
        tabs = self.tabs(tmp_path)
        checked: list[tuple[Path, ...]] = []
        original = Server.refresh

        def refresh(server: Server, *documents: Path) -> None:
            checked.append(documents)
            if len(checked) == 1:
                msg = "a defect of the server's own"
                raise RuntimeError(msg)
            original(server, *documents)

        monkeypatch.setattr(Server, "refresh", refresh)
        writer = io.BytesIO()
        inbox = Arrivals(
            writer,
            [self.hello(tmp_path), self.saved(tabs[0]), self.watched(tabs[0])],
            [self.saved(tabs[1])],
            END,
        )
        assert Server(io.BytesIO(), writer, root=tmp_path)._serve(inbox) == 0
        trace = capsys.readouterr().err
        assert trace.startswith(
            "ddd: textDocument/didSave, workspace/didChangeWatchedFiles failed on a defect of this "
            "server, and the session goes on\nTraceback (most recent call last):\n"
        )
        assert trace.count("Traceback") == 1
        assert trace.endswith("RuntimeError: a defect of the server's own\n")
        assert checked == [(tabs[0].resolve(),), (tabs[1].resolve(),)]
        assert [message["id"] for message in sent(writer) if "id" in message] == [1, 99]
        assert [entry["code"] for entry in published(writer)[tabs[1].as_uri()]] == [
            "missing-producer"
        ]

    def test_broken_framing_ends_the_run_once_what_came_before_it_is_checked(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The check of a document marked before the break is still owed when the break ends the
        run with 1, said once on stderr."""
        tabs = self.tabs(tmp_path)
        writer = io.BytesIO()
        broken = ProtocolError("Content-Length is not a count of bytes")
        inbox = Arrivals(writer, [self.hello(tmp_path), self.opened(tabs[0]), broken])
        assert Server(io.BytesIO(), writer, root=tmp_path)._serve(inbox) == 1
        assert capsys.readouterr().err == f"ddd: {broken}\n"
        assert [entry["code"] for entry in published(writer)[tabs[0].as_uri()]] == [
            "missing-producer"
        ]

    def test_broken_framing_seen_by_the_reading_thread_still_ends_the_run(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Read ahead on a thread of its own, a session whose framing breaks still ends with 1,
        said once, and the document it opened first is checked: whether the break was already
        queued behind the ``didOpen`` or not."""
        tabs = self.tabs(tmp_path)
        writer = io.BytesIO()
        stream = io.BytesIO(
            framed(self.hello(tmp_path), self.opened(tabs[0])).getvalue()
            + b"Content-Length: banana\r\n\r\n{}"
        )
        assert Server(stream, writer, root=tmp_path).run() == 1
        err = capsys.readouterr().err
        assert err.startswith("ddd: Content-Length is not a count of bytes: 'banana'")
        assert err.count("\n") == 1
        assert [entry["code"] for entry in published(writer)[tabs[0].as_uri()]] == [
            "missing-producer"
        ]

    @pytest.mark.parametrize(
        ("end", "code"),
        [(None, 0), ({"jsonrpc": "2.0", "method": "exit"}, 1)],
        ids=["the stream ending", "an exit with no shutdown"],
    )
    def test_the_check_owed_when_the_run_ends_is_made(
        self, tmp_path: Path, end: dict[str, Any] | None, code: int
    ) -> None:
        """As every message was checked before the next was read, when they were read in turn."""
        tabs = self.tabs(tmp_path)
        writer = io.BytesIO()
        inbox = Arrivals(writer, [self.hello(tmp_path), self.opened(tabs[0]), end])
        assert Server(io.BytesIO(), writer, root=tmp_path)._serve(inbox) == code
        assert [entry["code"] for entry in published(writer)[tabs[0].as_uri()]] == [
            "missing-producer"
        ]

    def test_a_watch_event_that_checks_nothing_still_drops_what_was_read(
        self, tmp_path: Path
    ) -> None:
        """Nothing open, and the one file it reports deleted: no check runs, and a jump asked
        afterwards reads the project as the disk now holds it, not as it was read before."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Shared")),
                "b.ddd.json": component("B", declare("input", "Shared")),
            },
        )
        a, b = tmp_path / "a.ddd.json", tmp_path / "b.ddd.json"
        position = Document(b.read_text(encoding="utf-8")).range_of(
            "component.interface[0].definition.name"
        )["start"]
        jump = {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "textDocument/definition",
            "params": {"textDocument": {"uri": b.as_uri()}, "position": position},
        }
        writer = io.BytesIO()
        server = Server(io.BytesIO(), writer, root=tmp_path)
        assert server._handle(self.hello(tmp_path))
        assert server._handle(jump)
        assert [found["uri"] for found in sent(writer)[-1]["result"]] == [a.as_uri()]
        a.unlink()
        assert server._handle(
            {
                "jsonrpc": "2.0",
                "method": "workspace/didChangeWatchedFiles",
                "params": {"changes": [{"uri": a.as_uri(), "type": 3}]},
            }
        )
        assert server._handle(jump)
        assert sent(writer)[-1] == response(7, [])

    def test_a_document_another_project_reported_on_is_searched_for_all_the_same(
        self, tmp_path: Path
    ) -> None:
        """Three descriptions side by side, ``q2`` holding both documents: ``q3`` holds the second
        too, and is analysed for it, though ``q2``'s run reported on it already."""
        write_tree(
            tmp_path,
            {
                "q1.ddd.json": project("Q1", "d1.ddd.json", "x.ddd.json"),
                "q2.ddd.json": project("Q2", "d1.ddd.json", "d2.ddd.json"),
                "q3.ddd.json": project("Q3", "d2.ddd.json", "y.ddd.json"),
                "d1.ddd.json": component("D1", declare("local", "One")),
                "d2.ddd.json": component("D2", declare("local", "Two")),
                "x.ddd.json": component("X", declare("local", "Three")),
                "y.ddd.json": component("Y", declare("input", "Nobody")),
            },
        )
        documents = [tmp_path / "d1.ddd.json", tmp_path / "d2.ddd.json"]
        reports = service.collect([], documents, tmp_path)
        assert [entry["code"] for entry in reports[tmp_path / "y.ddd.json"]] == ["missing-producer"]

    def test_each_description_above_the_documents_is_read_once(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Ten documents of one project above them, each searched for: the search for the first
        reads the description, and the nine after it find it read."""
        names = [f"c{number}.ddd.json" for number in range(10)]
        write_tree(
            tmp_path,
            {"p.ddd.json": project("P", *names)}
            | {
                name: component(f"C{number}", declare("local", "V"))
                for number, name in enumerate(names)
            },
        )
        seen: list[Path] = []
        original = navigation.load_workspace

        def counted(path: Path, bag: DiagnosticBag) -> Any:
            seen.append(path)
            return original(path, bag)

        monkeypatch.setattr(navigation, "load_workspace", counted)
        reports = service.collect([], [tmp_path / name for name in names], tmp_path)
        assert set(reports) >= {tmp_path / name for name in names}
        assert seen.count(tmp_path / "p.ddd.json") == 1, seen

    def test_a_document_no_project_answers_for_is_read_alone_only_where_none_reported_on_it(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``d2`` lies outside the directory of the description that includes it, so no search
        above it finds one. Checked with ``d1``, that description's run reports on it, and
        whichever of the two came first ``d2`` is not analysed on its own as well."""
        write_tree(
            tmp_path,
            {
                "images/q.ddd.json": project("Q", "d1.ddd.json", "../shared/d2.ddd.json"),
                "images/d1.ddd.json": component("D1", declare("output", "Speed")),
                "shared/d2.ddd.json": component("D2", declare("input", "Speed")),
            },
        )
        d1, d2 = tmp_path / "images" / "d1.ddd.json", tmp_path / "shared" / "d2.ddd.json"
        analysed: list[Path] = []
        original = service.analyze

        def counted(workspace: Any, bag: DiagnosticBag) -> Any:
            analysed.append(workspace.root.resolve())
            return original(workspace, bag)

        monkeypatch.setattr(service, "analyze", counted)
        service.collect([], [d2], tmp_path)
        assert analysed == [d2.resolve()], "checked by itself, it is read on its own"
        for order in ([d2, d1], [d1, d2]):
            analysed.clear()
            assert d2 in service.collect([], order, tmp_path)
            assert analysed == [(tmp_path / "images" / "q.ddd.json").resolve()], order

    def test_the_reading_thread_hands_over_what_it_cannot_follow(self, tmp_path: Path) -> None:
        """A frame holding no message is answered on the server's thread, which alone writes, and
        broken framing ends the reading there; both are handed over, after what came before."""
        hello = self.hello(tmp_path)
        stream = io.BytesIO(
            framed(hello).getvalue() + raw_frame(b"{ not json") + b"Content-Length: banana\r\n\r\n"
        )
        inbox: queue.SimpleQueue[Any] = queue.SimpleQueue()
        Server(stream, io.BytesIO(), root=tmp_path)._read(inbox)
        message, unparsed, broken = inbox.get_nowait(), inbox.get_nowait(), inbox.get_nowait()
        assert message == hello
        assert isinstance(unparsed, MessageError)
        assert unparsed.code == PARSE_ERROR
        assert isinstance(broken, ProtocolError)
        assert inbox.empty()

    def test_anything_else_the_stream_raises_reaches_the_caller(self, tmp_path: Path) -> None:
        """As it did when the stream was read in turn: the reading thread hands it over, and the
        server raises it."""

        class Broken(io.BytesIO):
            def readline(self, size: int | None = -1) -> bytes:
                msg = "the pipe broke"
                raise OSError(msg)

        inbox: queue.SimpleQueue[Any] = queue.SimpleQueue()
        server = Server(Broken(), io.BytesIO(), root=tmp_path)
        server._read(inbox)
        fault = inbox.get_nowait()
        assert inbox.empty()
        with pytest.raises(OSError, match="the pipe broke"):
            server._serve(Arrivals(io.BytesIO(), [fault]))

    def test_the_command_ends_cleanly_while_the_client_holds_its_stdin_open(
        self, tmp_path: Path
    ) -> None:
        """The reading thread is still waiting for a frame after ``exit``, and the interpreter
        closes ``sys.stdin`` on its way out: waiting for the lock that read holds, it aborts the
        process, so a stop the client prepared for would end in a core dump. Run from the
        sources this suite imports, whatever else is installed."""
        import subprocess

        frames = framed(self.hello(tmp_path), *END).getvalue()
        sources = Path(server_module.__file__).parents[2]
        path = os.pathsep.join(filter(None, [str(sources), os.environ.get("PYTHONPATH")]))
        with subprocess.Popen(
            [sys.executable, "-m", "ddd", "lsp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=tmp_path,
            env={**os.environ, "PYTHONPATH": path},
        ) as process:
            assert process.stdin is not None
            assert process.stdout is not None
            process.stdin.write(frames)
            process.stdin.flush()
            ended = process.wait(timeout=120)
            wire = process.stdout.read()
        assert ended == 0
        assert [message["id"] for message in sent(io.BytesIO(wire))] == [1, 99]

    def test_the_command_reads_a_stdin_descriptor_through_a_reader_of_its_own(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Over the same descriptor, so that what the interpreter closes on its way out is not
        what the reading thread waits in. The file is closed once that thread has read it to its
        end, so that no later file given the same descriptor is read in its place."""
        import threading

        class Stream:
            def __init__(self, buffer: Any) -> None:
                self.buffer = buffer

        readers: list[Any] = []
        reading: list[threading.Thread] = []

        class Recorded(Server):
            def __init__(self, reader: Any, *args: Any, **kwargs: Any) -> None:
                readers.append(reader)
                super().__init__(reader, *args, **kwargs)

            def _read(self, inbox: Any) -> None:
                reading.append(threading.current_thread())
                super()._read(inbox)

        frames = tmp_path / "frames"
        frames.write_bytes(framed(self.hello(tmp_path), *END).getvalue())
        wire = io.BytesIO()
        monkeypatch.setattr(server_module, "Server", Recorded)
        with frames.open("rb") as stdin:
            monkeypatch.setattr("sys.stdin", Stream(stdin))
            monkeypatch.setattr("sys.stdout", Stream(wire))
            assert server_module.serve() == 0
            (reader,) = readers
            assert reader is not stdin
            assert reader.fileno() == stdin.fileno()
            (thread,) = reading
            thread.join()
        assert [message["id"] for message in sent(wire)] == [1, 99]


class TestAHoverResolvesOncePerCheck:
    """10:I12: the dictionary a hover answers from is kept per description until what was read
    from disk is dropped, where every hover resolved the whole project again."""

    def workspace(self, tmp_path: Path, *extra: str) -> Path:
        """``b`` reading what ``a`` writes, in a project a build record names, which also includes
        each of ``extra``."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json", *extra),
                "a.ddd.json": component("A", declare("output", "Speed")),
                "b.ddd.json": component("B", declare("input", "Speed")),
            },
        )
        build_record(tmp_path, tmp_path / "p.ddd.json")
        return tmp_path / "b.ddd.json"

    def hover(self, path: Path) -> dict[str, Any]:
        position = Document(path.read_text(encoding="utf-8")).range_of(
            "component.interface[0].definition.name"
        )["start"]
        return {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "textDocument/hover",
            "params": {"textDocument": {"uri": path.as_uri()}, "position": position},
        }

    def test_hovers_between_two_checks_resolve_the_project_once(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from ddd.lsp import hover

        consumer = self.workspace(tmp_path)
        resolved: list[Any] = []
        original = hover.analyze

        def counted(workspace: Any, bag: DiagnosticBag) -> Any:
            resolved.append(workspace)
            return original(workspace, bag)

        monkeypatch.setattr(hover, "analyze", counted)
        writer = io.BytesIO()
        server = Server(io.BytesIO(), writer, root=tmp_path)
        assert server._handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        assert server._handle(self.hover(consumer))
        assert server._handle(self.hover(consumer))
        assert len(resolved) == 1
        saving = {"textDocument": {"uri": consumer.as_uri()}}
        assert server._handle(
            {"jsonrpc": "2.0", "method": "textDocument/didSave", "params": saving}
        )
        assert server._handle(self.hover(consumer))
        assert len(resolved) == 2, "a check drops the dictionary with the rest of what was read"
        answers = [message["result"] for message in sent(writer) if message.get("id") == 7]
        assert len(answers) == 3
        assert answers[0] == answers[1] == answers[2]
        assert "Written by **A**, read by **B**." in answers[0]["contents"]["value"]

    def test_a_hover_in_a_project_whose_read_reported_an_error_answers_all_the_same(
        self, tmp_path: Path
    ) -> None:
        """A check analyses no such project, so the hover's dictionary is not the check's: the
        hover resolves what did load, as it always has."""
        consumer = self.workspace(tmp_path, "c.ddd.json")
        write_tree(tmp_path, {"c.ddd.json": component("C", declare("nonsense", "X"))})
        writer = io.BytesIO()
        server = Server(io.BytesIO(), writer, root=tmp_path)
        assert server._handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        opened = {"textDocument": {"uri": consumer.as_uri()}}
        assert server._handle(
            {"jsonrpc": "2.0", "method": "textDocument/didOpen", "params": opened}
        )
        assert "schema" in {
            entry["code"] for entry in published(writer)[(tmp_path / "c.ddd.json").as_uri()]
        }
        assert server._handle(self.hover(consumer))
        (answer,) = [message["result"] for message in sent(writer) if message.get("id") == 7]
        assert "Written by **A**, read by **B**." in answer["contents"]["value"]

    def test_a_hover_in_a_document_no_project_can_be_read_for_says_nothing(
        self, tmp_path: Path
    ) -> None:
        """A new document, open and not saved yet: the cursor is on a name it declares, and there
        is no project to resolve, not even the document read on its own."""
        draft = tmp_path / "draft.ddd.json"
        text = json.dumps(component("D", declare("output", "Speed")))
        writer = io.BytesIO()
        server = Server(io.BytesIO(), writer, root=tmp_path)
        assert server._handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        opened = {"textDocument": {"uri": draft.as_uri(), "version": 1, "text": text}}
        assert server._handle(
            {"jsonrpc": "2.0", "method": "textDocument/didOpen", "params": opened}
        )
        position = Document(text).range_of("component.interface[0].definition.name")["start"]
        asked = {"textDocument": {"uri": draft.as_uri()}, "position": position}
        assert server._handle(
            {"jsonrpc": "2.0", "id": 7, "method": "textDocument/hover", "params": asked}
        )
        assert not draft.exists()
        assert sent(writer)[-1] == response(7, None)
