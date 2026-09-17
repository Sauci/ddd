"""The language server: what an editor is told, and how it is framed on the way.

The checks themselves are tested everywhere else in this suite. What is tested here is the
translation - a pointer becoming a range, a build record becoming a project, a finding
becoming something an editor can draw and click - and the protocol the translation travels on.
"""

from __future__ import annotations

import io
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

import pytest

from conftest import (
    EXAMPLES,
    INCONSISTENT,
    answered,
    build_record,
    component,
    declare,
    directory_link,
    framed,
    project,
    sent,
    session,
    write_tree,
)
from ddd.build_info import BUILD_INFO_FILENAME
from ddd.diagnostics import Diagnostic, DiagnosticBag, Location, Severity
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
from ddd.lsp.ranges import Document, read
from ddd.lsp.server import Server, uri_to_path


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

    @pytest.mark.parametrize("content", ["not json at all", '{"project": 7}', "{}"])
    def test_a_record_that_makes_no_sense_is_skipped(self, tmp_path: Path, content: str) -> None:
        """Written by a build rather than by a person, so there is nobody to report it to."""
        path = tmp_path / BUILD_INFO_FILENAME
        path.write_text(content, encoding="utf-8")
        assert load_builds([path]) == []

    def test_a_record_from_a_newer_ddd_is_skipped(self, tmp_path: Path) -> None:
        path = build_record(tmp_path, tmp_path / "p.ddd.json", format=99)
        assert load_builds([path]) == []

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
        service._group(bag, tmp_path / "root.ddd.json", grouped)
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
        assert offered[0]["title"] == "Apply this unit to 1 other declaration of 'Speed'"
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
        titles = [entry["title"] for entry in offered]
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
        assert [action["title"] for action in offered] == [
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
        assert offered[0]["title"] == "Apply this unit to 1 other declaration of 'Speed'"

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
        assert offered[0]["title"] == "Use the unit declared in a"

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
        assert [action["title"] for action in offered] == [
            "Apply this unit to 2 other declarations of 'Speed'"
        ]

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
        assert [action["title"] for action in offered] == [
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
        assert offered[0]["title"] == "Remove this unit, which no other declaration of 'Speed' has"

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
        assert [action["title"] for action in offered] == [
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
        assert [action["title"] for action in offered] == [
            "Remove the unit from 2 other declarations of 'Speed'"
        ]

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
        assert [action["title"] for action in offered] == [
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
        assert [action["title"] for action in consumer] == [
            "Use the limits declared in prod",
            "Apply this limits to 1 other declaration of 'T'",
        ]
        producer, _ = self.offer(
            tmp_path, "prod.ddd.json", "component.interface[0].definition", **files
        )
        assert [action["title"] for action in producer] == [
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
        assert [action["title"] for action in offered] == [
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
        """Nothing to leave behind: it is the only member, so there is no comma to take."""
        from ddd.lsp.edits import _remove_here
        from ddd.lsp.navigation import Index, Site

        write_tree(tmp_path, {"b.ddd.json": component("B", declare("input", "S"))})
        elsewhere = Site(tmp_path / "b.ddd.json", "component.interface[0].definition")
        document = Document('{"component": {"interface": [{"definition": {"unit": "rpm"}}]}}')
        assert (
            _remove_here(
                Index(declarations={"S": [elsewhere]}),
                Site(tmp_path / "a.ddd.json", "component.interface[0].definition"),
                document,
                "S",
                "unit",
                {},
            )
            is None
        )

    def test_there_is_nowhere_to_put_the_producer_value_in_an_empty_definition(
        self, tmp_path: Path
    ) -> None:
        from ddd.lsp.edits import _from_producer
        from ddd.lsp.navigation import Index, Site

        write_tree(tmp_path, {"a.ddd.json": component("A", declare("output", "S", unit="rpm"))})
        producer = Site(tmp_path / "a.ddd.json", "component.interface[0].definition")
        document = Document('{"component": {"interface": [{"definition": {}}]}}')
        assert (
            _from_producer(
                Index(producers={"S": [producer]}),
                Site(tmp_path / "b.ddd.json", "component.interface[0].definition"),
                document,
                "S",
                "unit",
                {},
            )
            is None
        )

    def test_there_is_nothing_to_take_into_a_definition_with_no_members(
        self, tmp_path: Path
    ) -> None:
        from ddd.lsp.edits import _adopt
        from ddd.lsp.navigation import Index, Site

        write_tree(tmp_path, {"b.ddd.json": component("B", declare("input", "S", unit="rpm"))})
        elsewhere = Site(tmp_path / "b.ddd.json", "component.interface[0].definition")
        document = Document('{"component": {"interface": [{"definition": {}}]}}')
        assert (
            _adopt(
                Index(declarations={"S": [elsewhere]}),
                Site(tmp_path / "a.ddd.json", "component.interface[0].definition"),
                document,
                "S",
                "unit",
                {},
            )
            is None
        )

    def test_a_definition_that_is_not_an_object_is_left_alone(self, tmp_path: Path) -> None:
        """Belt and braces around the insertion: there is nowhere to insert into."""
        from ddd.lsp.edits import _insert

        document = Document('{"component": {"interface": [{"definition": 7}]}}')
        assert _insert(document, "component.interface[0].definition", "unit", '"rpm"') is None


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
        original = server_module.discover

        def counted(root: Path, configured: Any = (), refused: Any = None) -> Any:
            walks.append(root)
            return original(root, configured, refused)

        monkeypatch.setattr(server_module, "discover", counted)
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

    def test_a_quick_fix_is_refused_while_a_file_of_the_project_did_not_load(
        self, tmp_path: Path
    ) -> None:
        """The same hole seen through the lightbulb: it offered to remove the unit of 'Speed'
        as one no other declaration has, while the unloaded producer declares exactly that."""
        self.half_read_workspace(tmp_path)
        elsewhere = tmp_path / "c.ddd.json"
        span = Document(elsewhere.read_text(encoding="utf-8")).range_of(
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
                        "textDocument": {"uri": elsewhere.as_uri()},
                        "range": span,
                        "context": {"diagnostics": []},
                    },
                }
            ),
            writer,
            root=tmp_path,
        ).run()
        (answer,) = answered(writer)
        assert answer["error"]["code"] == REQUEST_FAILED
        assert "a.ddd.json" in answer["error"]["message"]

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
        assert "b.ddd.json" in answer["error"]["message"]
        assert "result" not in answer

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
