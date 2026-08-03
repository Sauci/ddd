"""The language server: what an editor is told, and how it is framed on the way.

The checks themselves are tested everywhere else in this suite. What is tested here is the
translation - a pointer becoming a range, a build record becoming a project, a finding
becoming something an editor can draw and click - and the protocol the translation travels on.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest

from conftest import INCONSISTENT, component, declare, project, write_tree
from ddd.build_info import BUILD_INFO_FILENAME
from ddd.diagnostics import Diagnostic, DiagnosticBag, Location, Severity
from ddd.loading import load_workspace
from ddd.lsp import diagnostics as service
from ddd.lsp.discovery import build_files, discover, load_builds
from ddd.lsp.protocol import (
    METHOD_NOT_FOUND,
    error,
    notification,
    read_message,
    response,
    write_message,
)
from ddd.lsp.ranges import Document, read
from ddd.lsp.server import Server, uri_to_path


def framed(*messages: dict[str, Any]) -> io.BytesIO:
    """The messages as a client would put them on the wire."""
    stream = io.BytesIO()
    for message in messages:
        write_message(stream, message)
    stream.seek(0)
    return stream


def published(stream: io.BytesIO) -> dict[str, list[dict[str, Any]]]:
    """The diagnostics the server published, keyed by file name.

    Filtered rather than taken wholesale: the server also logs, and a log line has no uri.
    """
    return {
        uri_to_path(message["params"]["uri"]).name: message["params"]["diagnostics"]
        for message in sent(stream)
        if message.get("method") == "textDocument/publishDiagnostics"
    }


def sent(stream: io.BytesIO) -> list[dict[str, Any]]:
    """Everything the server wrote, read back off the wire."""
    stream.seek(0)
    received = []
    while (message := read_message(stream)) is not None:
        received.append(message)
    return received


def build_record(base: Path, project_file: Path, **extra: Any) -> Path:
    """A ``ddd-build.json`` where a build would have left one."""
    path = base / "build" / "ddd" / "firmware.elf" / BUILD_INFO_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"format": 1, "project": project_file.as_posix(), "image": "firmware.elf", **extra}
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


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

    def test_the_three_message_shapes(self) -> None:
        assert response(1, None) == {"jsonrpc": "2.0", "id": 1, "result": None}
        assert error(2, METHOD_NOT_FOUND, "no") == {
            "jsonrpc": "2.0",
            "id": 2,
            "error": {"code": METHOD_NOT_FOUND, "message": "no"},
        }
        assert notification("m", {"a": 1}) == {"jsonrpc": "2.0", "method": "m", "params": {"a": 1}}


class TestRanges:
    """A pointer is what DDD reports; a range is what an editor can draw."""

    DOCUMENT = (
        '{\n  "component": {\n    "name": "A",\n'
        '    "declarations": [\n      {"scope": "output"},\n'
        '      {"scope": "input", "condition": null}\n    ],\n'
        '    "empty": {},\n    "none": [],\n    "flag": true\n  }\n}\n'
    )

    def test_a_member_is_underlined_from_its_key(self) -> None:
        """Underlining the value alone leaves the reader to look left for the key."""
        found = Document(self.DOCUMENT).range_of("component.declarations[1].condition")
        line = self.DOCUMENT.splitlines()[5]
        assert found["start"]["line"] == found["end"]["line"] == 5
        assert line[found["start"]["character"] : found["end"]["character"]] == '"condition": null'

    @pytest.mark.parametrize(
        "pointer",
        ["component", "component.name", "component.declarations", "component.empty",
         "component.none", "component.flag", ""],
    )  # fmt: skip
    def test_every_shape_of_value_is_located(self, pointer: str) -> None:
        assert Document(self.DOCUMENT).range_of(pointer)["end"] != {"line": 0, "character": 0}

    def test_an_unknown_pointer_falls_back_to_its_parent(self) -> None:
        """A finding shown one level up beats a finding nobody sees."""
        document = Document(self.DOCUMENT)
        assert document.range_of("component.declarations[0].absent") == document.range_of(
            "component.declarations[0]"
        )

    def test_an_index_is_stripped_as_readily_as_a_key(self) -> None:
        document = Document(self.DOCUMENT)
        assert document.range_of("component.declarations[7]") == document.range_of(
            "component.declarations"
        )

    def test_a_file_that_is_not_json_puts_everything_at_the_top(self) -> None:
        """Caught mid edit: the json-syntax finding carries its own line and column."""
        assert Document("{not json").range_of("component") == {
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
        location = Location(Path("a.ddd.json"), "component.declarations[0]")
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
        assert {entry["code"] for findings in reports.values() for entry in findings} == set()

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
            "init-invalid"
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

    def test_a_note_with_nowhere_to_point_keeps_its_text(self) -> None:
        """Every piece of related information carries a location, so one is invented."""
        finding = Diagnostic("naming", Severity.ERROR, "bad name", None, (("try harder", None),))
        published = service._as_lsp(finding, {})
        (related,) = published["relatedInformation"]
        assert related["message"] == "try harder"
        assert related["location"]["uri"] == ""

    def test_a_file_that_cannot_be_read_still_gets_a_range(self, tmp_path: Path) -> None:
        finding = Diagnostic(
            "schema", Severity.ERROR, "unreadable", Location(tmp_path / "gone.json", "a.b")
        )
        assert service._as_lsp(finding, {})["range"]["start"] == {"line": 0, "character": 0}


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
        pointer = "component.declarations[0].definition.name"
        (site,) = definition(built, document, consumer, pointer)
        assert site.path == tmp_path / "a.ddd.json"
        assert site.pointer == "component.declarations[0].definition"

    def test_a_local_counts_as_its_own_producer(self, tmp_path: Path) -> None:
        from ddd.lsp.navigation import definition

        root = self.workspace(tmp_path)
        producer = tmp_path / "a.ddd.json"
        document = read(producer, {})
        (site,) = definition(
            self.index_of(root), document, producer, "component.declarations[1].definition.name"
        )
        assert site.pointer == "component.declarations[1].definition"

    def test_references_reach_both_sides(self, tmp_path: Path) -> None:
        from ddd.lsp.navigation import references

        root = self.workspace(tmp_path)
        consumer = tmp_path / "b.ddd.json"
        document = read(consumer, {})
        found = references(
            self.index_of(root), document, "component.declarations[0].definition.name"
        )
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
            "component.declarations[1].definition.axis",
        )
        assert site.pointer == "component.declarations[0].definition"

    def test_a_nested_structure_leads_to_its_declaration(self, tmp_path: Path) -> None:
        from ddd.lsp.navigation import definition, references

        types = {
            "types": [
                {
                    "name": "Inner_t",
                    "members": [
                        {"name": "v", "member": "value", "kind": "measurement", "datatype": "uint8"}
                    ],
                },
                {
                    "name": "Outer_t",
                    "members": [{"name": "inner", "member": "struct", "type": "Inner_t"}],
                },
            ]
        }
        write_tree(tmp_path, {"p.ddd.json": project("P", "t.ddd.json"), "t.ddd.json": types})
        path = tmp_path / "t.ddd.json"
        built = self.index_of(tmp_path / "p.ddd.json")
        document = read(path, {})
        (site,) = definition(built, document, path, "types[1].members[0].type")
        assert site.pointer == "types[0]"
        assert {found.pointer for found in references(built, document, "types[0].name")} == {
            "types[0]",
            "types[1].members[0].type",
        }

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
                            "name": "T_t",
                            "members": [{"name": "n", "member": "struct", "type": "Absent_t"}],
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
            definition(built, read(path, {}), path, "component.declarations[0].definition.name")
            == []
        )
        types = tmp_path / "t.ddd.json"
        document = read(types, {})
        assert definition(built, document, types, "types[0].members[0].type") == []
        assert references(built, document, "types[0].members[0].type") == []

    @pytest.mark.parametrize("pointer", ["project.includes[0]", "project.naming"])
    def test_a_path_leads_to_the_file_it_names(self, tmp_path: Path, pointer: str) -> None:
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", naming="c.ddd.json"),
                "a.ddd.json": component("A"),
                "c.ddd.json": {
                    "naming": {
                        "name": "C",
                        "segments": [{"name": "part", "pattern": "^[A-Za-z]+$"}],
                    }
                },
            },
        )
        from ddd.lsp.navigation import definition

        root = tmp_path / "p.ddd.json"
        (site,) = definition(self.index_of(root), read(root, {}), root, pointer)
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
            "component.declarations[0].definition.name",
            "component.declarations[0].definition.datatype",
            "component.declarations[0].definition",
            "component.declarations[0].scope",
            "component.declarations[0]",
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
            "component.declarations[0].definition.limits.min",
        )
        assert site.path == tmp_path / "a.ddd.json"

    def test_a_file_no_build_claims_is_navigated_on_its_own(self, tmp_path: Path) -> None:
        from ddd.lsp.navigation import workspaces

        self.workspace(tmp_path)
        alone = tmp_path / "a.ddd.json"
        (found,) = workspaces([], alone)
        assert alone in found.sources()

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
        assert found.name == "P"


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
        return resolve([info], tmp_path / "a.ddd.json")

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
        dictionary = resolve([info], tmp_path / "a.ddd.json")
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
        assert "shape" not in bare and "condition" not in bare and "volatile" not in bare
        assert "| unit | `Hz` |" in full
        assert "| condition | `defined(FEAT_X)` |" in full
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
        assert "init `7`" in described
        assert "```text" not in described

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
            "component.declarations[1].definition.name",
            "component.declarations[1].definition.datatype",
            "component.declarations[1].scope",
            "component.declarations[1]",
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
        assert subject_at(document, "component.declarations[1].definition.axis") == "Axis"

    @pytest.mark.parametrize("pointer", ["component.name", "component", ""])
    def test_outside_a_declaration_there_is_no_subject(self, tmp_path: Path, pointer: str) -> None:
        from ddd.lsp.navigation import subject_at

        write_tree(tmp_path, {"a.ddd.json": component("A", declare("output", "X"))})
        assert subject_at(read(tmp_path / "a.ddd.json", {}), pointer) is None

    def test_a_declaration_still_being_written_has_no_subject(self) -> None:
        """Caught mid edit: the pointer is built rather than scanned, so it may lead nowhere."""
        from ddd.lsp.navigation import subject_at

        document = Document('{"component": {"declarations": [{"scope": "input"}]}}')
        assert subject_at(document, "component.declarations[0].scope") is None

    def test_a_name_no_component_declares_has_nothing_to_show(self, tmp_path: Path) -> None:
        from ddd.lsp.hover import describe

        assert describe(self.resolved(tmp_path, declare("output", "Value")), "Absent") is None

    def test_a_document_in_no_project_resolves_to_nothing(self, tmp_path: Path) -> None:
        from ddd.lsp.hover import resolve

        assert resolve([], tmp_path / "absent.ddd.json") is None

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
            "component.declarations[0].definition.name",
            "EngineSpeed",
            cache,
        )
        rewritten = {
            uri_to_path(uri): apply_edits(uri_to_path(uri), found) for uri, found in edits.items()
        }
        assert {path.name for path in rewritten} == {"a.ddd.json", "b.ddd.json"}
        produced = json.loads(rewritten[tmp_path / "a.ddd.json"])["component"]["declarations"]
        assert produced[0]["definition"]["name"] == "EngineSpeed"
        assert produced[1]["definition"]["input"] == "EngineSpeed"
        assert "Speed" not in rewritten[tmp_path / "b.ddd.json"].replace("EngineSpeed", "")

    def test_only_the_characters_between_the_quotes_are_replaced(self, tmp_path: Path) -> None:
        """Whatever else a project puts on the line is left exactly as it was."""
        from ddd.lsp.navigation import rename_edits

        root = self.workspace(tmp_path)
        path = tmp_path / "b.ddd.json"
        cache: dict[Path, Document] = {}
        edits = rename_edits(
            self.index_of(root),
            read(path, cache),
            "component.declarations[0].definition.name",
            "X",
            cache,
        )
        rewritten = apply_edits(path, edits[path.as_uri()])
        assert '"name": "X"' in rewritten
        assert json.loads(rewritten)  # still json, quotes intact

    def test_a_rename_from_a_position_naming_nothing_edits_nothing(self, tmp_path: Path) -> None:
        from ddd.lsp.navigation import rename_edits

        root = self.workspace(tmp_path)
        path = tmp_path / "b.ddd.json"
        assert rename_edits(self.index_of(root), read(path, {}), "component.name", "X", {}) == {}

    def test_a_mention_that_is_not_a_string_is_skipped(self, tmp_path: Path) -> None:
        """Belt and braces: the index and the text are read at the same moment, but a file
        rewritten between the two would otherwise put an edit over a number."""
        from ddd.lsp.navigation import Index, Site, rename_edits

        write_tree(tmp_path, {"a.ddd.json": component("A", declare("output", "Speed"))})
        path = tmp_path / "a.ddd.json"
        built = Index(
            mentions={"Speed": [Site(path, "component.declarations[0].definition.dimensions")]}
        )
        cache: dict[Path, Document] = {}
        found = rename_edits(
            built, read(path, cache), "component.declarations[0].definition.name", "X", cache
        )
        assert found == {}

    @pytest.mark.parametrize(
        ("name", "because"),
        [
            ("2Bad", "not a usable c identifier"),
            ("has space", "not a usable c identifier"),
            ("int", "reserved"),
            ("uint16_t", "reserved"),
            ("Ax", "already declared"),
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
        from ddd.lsp.navigation import index

        write_tree(tmp_path, {"p.ddd.json": project("P", *files), **files})
        return index(load_workspace(tmp_path / "p.ddd.json", DiagnosticBag()))

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
            "component.declarations[0].definition.unit",
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="1/min")),
            },
        )
        assert offered[0]["title"] == "Apply this unit to 1 other declaration of 'Speed'"
        (edits,) = offered[0]["edit"]["changes"].values()
        assert edits[0]["newText"] == '"rpm"'

    def test_a_key_the_others_lack_is_inserted(self, tmp_path: Path) -> None:
        """The usual mismatch: the other declaration simply never mentioned it."""
        offered, _ = self.offer(
            tmp_path,
            "a.ddd.json",
            "component.declarations[0].definition.unit",
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed")),
            },
        )
        spread = next(a for a in offered if a["title"].startswith("Apply"))
        (edits,) = spread["edit"]["changes"].values()
        rewritten = apply_edits(tmp_path / "b.ddd.json", edits)
        declared = json.loads(rewritten)["component"]["declarations"][0]["definition"]
        assert declared["unit"] == "rpm"

    def test_a_value_is_copied_as_written_rather_than_re_serialised(self, tmp_path: Path) -> None:
        """A conversion arrives looking the way its author typed it, not the way json.dumps
        would have; otherwise a one line fix reformats somebody's file."""
        from ddd.lsp.edits import actions
        from ddd.lsp.navigation import index

        write_tree(tmp_path, {"p.ddd.json": project("P", "a.ddd.json", "b.ddd.json")})
        (tmp_path / "a.ddd.json").write_text(
            '{"component": {"name": "A", "declarations": [{"scope": "output", "definition":'
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
            "component.declarations[0].definition.conversion",
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
            '{"component": {"name": "B", "declarations": [{"scope": "input", "definition":'
            ' {"name": "S", "kind": "measurement", "datatype": "uint8"}}]}}\n',
            encoding="utf-8",
        )
        built = index(load_workspace(tmp_path / "p.ddd.json", DiagnosticBag()))
        cache: dict[Path, Document] = {}
        path = tmp_path / "a.ddd.json"
        offered = actions(
            built, path, read(path, cache), "component.declarations[0].definition.unit", cache
        )
        spread = next(entry for entry in offered if entry["title"].startswith("Apply"))
        (edits,) = spread["edit"]["changes"].values()
        rewritten = apply_edits(tmp_path / "b.ddd.json", edits)
        assert rewritten.count("\n") == 1  # still one line, plus the trailing newline
        assert json.loads(rewritten)["component"]["declarations"][0]["definition"]["unit"] == "rpm"

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
            "component.declarations[0].definition.unit",
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
            "component.declarations[0].definition.unit",
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
            "component.declarations[0].definition.unit",
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
            "component.declarations[0].definition.unit",
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
            "component.declarations[0].definition.unit",
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="1/min")),
            },
        )
        (uri,) = offered[0]["edit"]["changes"]
        assert uri_to_path(uri).name == "b.ddd.json"
        rewritten = apply_edits(tmp_path / "b.ddd.json", offered[0]["edit"]["changes"][uri])
        assert json.loads(rewritten)["component"]["declarations"][0]["definition"]["unit"] == "rpm"

    def test_a_consumer_lacking_a_key_takes_it_from_the_producer(self, tmp_path: Path) -> None:
        offered, _ = self.offer(
            tmp_path,
            "b.ddd.json",
            "component.declarations[0].definition",
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
            "component.declarations[0].definition.unit",
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
            "component.declarations[0].definition.unit",
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
        assert "unit" not in json.loads(rewritten)["component"]["declarations"][0]["definition"]

    def test_a_key_somebody_else_states_is_not_offered_for_removal(self, tmp_path: Path) -> None:
        """Removing it would settle nothing: the other declaration would still have one."""
        offered, _ = self.offer(
            tmp_path,
            "b.ddd.json",
            "component.declarations[0].definition.unit",
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
            "component.declarations[0].definition.unit",
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
        edit = _erase(document, "component.declarations[0].definition", key)
        assert edit is not None
        rewritten = apply_edits(path, [edit])
        declared = json.loads(rewritten)["component"]["declarations"][0]["definition"]
        assert key not in declared
        assert declared["name"] == "S"

    def test_the_only_member_of_an_object_is_not_removed(self) -> None:
        """What to leave between the braces is a judgement about style, not about the data."""
        from ddd.lsp.edits import _erase

        document = Document('{"component": {"declarations": [{"definition": {"unit": "rpm"}}]}}')
        assert _erase(document, "component.declarations[0].definition", "unit") is None

    def test_a_key_that_is_not_there_is_not_removed(self) -> None:
        from ddd.lsp.edits import _erase

        document = Document('{"component": {"declarations": [{"definition": {"name": "S"}}]}}')
        assert _erase(document, "component.declarations[0].definition", "unit") is None

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
            "component.declarations[0].definition",
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
        assert json.loads(rewritten)["component"]["declarations"][0]["definition"]["unit"] == "rpm"

    def test_a_key_the_others_disagree_about_is_not_taken(self, tmp_path: Path) -> None:
        """Which of two answers is right is a question, and answering it silently is not help.

        Sending this declaration's silence out is still offered: that settles the finding
        without choosing between them.
        """
        offered, _ = self.offer(
            tmp_path,
            "a.ddd.json",
            "component.declarations[0].definition",
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
            "component.declarations[0].definition.unit",
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
            "component.declarations[0].definition.unit",
            **{"a.ddd.json": component("A", declare("local", "Speed", unit="rpm"))},
        )
        assert offered == []

    @pytest.mark.parametrize("pointer", ["component.declarations[0].scope", "component.name", ""])
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
            "component.declarations[0].definition",
            "component.declarations[0].definition.name",
            "component.declarations[0].definition.description",
            "component.declarations[0].definition.limits.min",
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
        assert [action["title"] for action in offered] == [
            "Apply this datatype to 1 other declaration of 'Speed'",
            "Apply this unit to 1 other declaration of 'Speed'",
            "Apply this limits to 1 other declaration of 'Speed'",
            # b has no limits, so dropping them settles the finding as well as spreading them.
            "Remove this limits, which no other declaration of 'Speed' has",
        ]

    def test_a_key_of_its_own_offers_only_that_key(self, tmp_path: Path) -> None:
        """Asked precisely, answered precisely: a name is a rename and a description is a
        component's own words, so neither is offered even from inside the definition."""
        offered, _ = self.offer(
            tmp_path,
            "a.ddd.json",
            "component.declarations[0].definition.unit",
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
        document = Document('{"component": {"declarations": [{"definition": {"unit": "rpm"}}]}}')
        assert (
            actions(Index(), path, document, "component.declarations[0].definition.unit", {}) == []
        )

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
            "component.declarations[0].definition",
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
        assert "unit" not in json.loads(rewritten)["component"]["declarations"][0]["definition"]

    def test_a_target_whose_key_cannot_be_cut_out_is_left_alone(self, tmp_path: Path) -> None:
        from ddd.lsp.edits import _remove_elsewhere
        from ddd.lsp.navigation import Index, Site

        (tmp_path / "b.ddd.json").write_text(
            '{"component": {"declarations": [{"definition": {"unit": "rpm"}}]}}', encoding="utf-8"
        )
        elsewhere = Site(tmp_path / "b.ddd.json", "component.declarations[0].definition")
        document = Document('{"component": {"declarations": [{"definition": {"name": "S"}}]}}')
        assert (
            _remove_elsewhere(
                Index(declarations={"S": [elsewhere]}),
                Site(tmp_path / "a.ddd.json", "component.declarations[0].definition"),
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
        elsewhere = Site(tmp_path / "b.ddd.json", "component.declarations[0].definition")
        document = Document('{"component": {"declarations": [{"definition": {"unit": "rpm"}}]}}')
        assert (
            _remove_here(
                Index(declarations={"S": [elsewhere]}),
                Site(tmp_path / "a.ddd.json", "component.declarations[0].definition"),
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
        producer = Site(tmp_path / "a.ddd.json", "component.declarations[0].definition")
        document = Document('{"component": {"declarations": [{"definition": {}}]}}')
        assert (
            _from_producer(
                Index(producers={"S": [producer]}),
                Site(tmp_path / "b.ddd.json", "component.declarations[0].definition"),
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
        elsewhere = Site(tmp_path / "b.ddd.json", "component.declarations[0].definition")
        document = Document('{"component": {"declarations": [{"definition": {}}]}}')
        assert (
            _adopt(
                Index(declarations={"S": [elsewhere]}),
                Site(tmp_path / "a.ddd.json", "component.declarations[0].definition"),
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

        document = Document('{"component": {"declarations": [{"definition": 7}]}}')
        assert _insert(document, "component.declarations[0].definition", "unit", '"rpm"') is None


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


class TestServer:
    """The loop, which is the only part a test can reach only through the protocol."""

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
        Server(framed(self.opened(opened)), writer, root=tmp_path).run()
        drawn = published(writer)
        assert drawn["component_b.ddd.json"][0]["code"] == "multiple-producers"
        # The file that was not opened is published too, which is the point.
        assert drawn["component_c.ddd.json"][0]["code"] == "definition-mismatch"

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
        build_record(tmp_path, tmp_path / "p.ddd.json")
        writer = io.BytesIO()
        server = Server(io.BytesIO(), writer, root=tmp_path)
        server.refresh(tmp_path / "a.ddd.json")
        assert published(writer)["a.ddd.json"][0]["code"] == "missing-producer"

        # Somebody produces it now, so the project is clean and the squiggle has to go.
        write_tree(tmp_path, {"a.ddd.json": component("A", declare("output", "Shared"))})
        writer = io.BytesIO()
        server.writer = writer
        server.refresh(tmp_path / "a.ddd.json")
        assert published(writer) == {"a.ddd.json": [], "b.ddd.json": []}

    def test_saving_refreshes_as_opening_does(self, tmp_path: Path) -> None:
        build_record(tmp_path, INCONSISTENT)
        writer = io.BytesIO()
        saved = dict(self.opened(INCONSISTENT), method="textDocument/didSave")
        Server(framed(saved), writer, root=tmp_path).run()
        assert sent(writer)

    def test_shutdown_is_answered_and_exit_ends_the_loop(self, tmp_path: Path) -> None:
        writer = io.BytesIO()
        stream = framed(
            {"jsonrpc": "2.0", "id": 4, "method": "shutdown"},
            {"jsonrpc": "2.0", "method": "exit"},
            {"jsonrpc": "2.0", "id": 5, "method": "initialize", "params": {}},
        )
        assert Server(stream, writer, root=tmp_path).run() == 0
        # Only the shutdown was answered: nothing after exit is read.
        assert [message["id"] for message in sent(writer)] == [4]

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
            "component.declarations[0].definition.name"
        )["start"]
        writer = io.BytesIO()
        Server(
            framed(self.navigation_request("textDocument/definition", consumer, position)),
            writer,
            root=tmp_path,
        ).run()
        (answer,) = sent(writer)
        (found,) = answer["result"]
        assert uri_to_path(found["uri"]).name == "a.ddd.json"

    def test_references_answer_with_every_declaration(self, tmp_path: Path) -> None:
        consumer = self.shared_workspace(tmp_path)
        position = Document(consumer.read_text(encoding="utf-8")).range_of(
            "component.declarations[0].definition.name"
        )["start"]
        writer = io.BytesIO()
        Server(
            framed(self.navigation_request("textDocument/references", consumer, position)),
            writer,
            root=tmp_path,
        ).run()
        (answer,) = sent(writer)
        assert {uri_to_path(found["uri"]).name for found in answer["result"]} == {
            "a.ddd.json",
            "b.ddd.json",
        }

    def hovered(self, tmp_path: Path, path: Path, pointer: str) -> Any:
        position = Document(path.read_text(encoding="utf-8")).range_of(pointer)["start"]
        writer = io.BytesIO()
        Server(
            framed(self.navigation_request("textDocument/hover", path, position)),
            writer,
            root=tmp_path,
        ).run()
        (answer,) = sent(writer)
        return answer["result"]

    def test_hover_answers_with_markdown(self, tmp_path: Path) -> None:
        consumer = self.shared_workspace(tmp_path)
        result = self.hovered(tmp_path, consumer, "component.declarations[0].definition.name")
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
        result = self.hovered(tmp_path, consumer, "component.declarations[0].definition.datatype")
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
            tmp_path, tmp_path / "a.ddd.json", "component.declarations[0].definition.axis"
        )
        assert result is None

    def test_hover_with_no_project_to_resolve_says_nothing(self, tmp_path: Path) -> None:
        """No build record and a file that will not load on its own."""
        lonely = tmp_path / "gone.ddd.json"
        writer = io.BytesIO()
        Server(
            framed(
                self.navigation_request("textDocument/hover", lonely, {"line": 0, "character": 0})
            ),
            writer,
            root=tmp_path,
        ).run()
        (answer,) = sent(writer)
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
            framed(
                self.rename_request(
                    consumer, "component.declarations[0].definition.name", "Renamed"
                )
            ),
            writer,
            root=tmp_path,
        ).run()
        (answer,) = sent(writer)
        changed = {uri_to_path(uri).name for uri in answer["result"]["changes"]}
        assert changed == {"a.ddd.json", "b.ddd.json"}

    def test_rename_to_an_unusable_name_is_refused_with_a_reason(self, tmp_path: Path) -> None:
        """An error rather than an empty edit: an empty edit looks like a rename that did
        nothing, where a refusal an editor can show tells the author what to type instead."""
        consumer = self.shared_workspace(tmp_path)
        writer = io.BytesIO()
        Server(
            framed(
                self.rename_request(consumer, "component.declarations[0].definition.name", "int")
            ),
            writer,
            root=tmp_path,
        ).run()
        (answer,) = sent(writer)
        assert "reserved" in answer["error"]["message"]

    def test_preparing_a_rename_says_where_the_box_goes(self, tmp_path: Path) -> None:
        consumer = self.shared_workspace(tmp_path)
        position = Document(consumer.read_text(encoding="utf-8")).range_of(
            "component.declarations[0].definition.name"
        )["start"]
        writer = io.BytesIO()
        Server(
            framed(self.navigation_request("textDocument/prepareRename", consumer, position)),
            writer,
            root=tmp_path,
        ).run()
        (answer,) = sent(writer)
        assert answer["result"]["placeholder"] == "Shared"

    @pytest.mark.parametrize(
        "pointer", ["component.declarations[0].definition.datatype", "component.name"]
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
            framed(self.navigation_request("textDocument/prepareRename", consumer, position)),
            writer,
            root=tmp_path,
        ).run()
        (answer,) = sent(writer)
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
            framed(
                self.rename_request(
                    tmp_path / "a.ddd.json", "component.declarations[0].definition.name", "Other"
                )
            ),
            writer,
            root=tmp_path,
        ).run()
        (answer,) = sent(writer)
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
            "component.declarations[0].definition.unit"
        )
        writer = io.BytesIO()
        Server(
            framed(
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
        (answer,) = sent(writer)
        (action,) = answer["result"]
        assert "Apply this unit" in action["title"]
        (uri,) = action["edit"]["changes"]
        assert uri_to_path(uri).name == "b.ddd.json"

    def test_a_request_it_cannot_serve_is_refused_rather_than_ignored(self, tmp_path: Path) -> None:
        """A client still waiting for an answer looks exactly like a server that has died."""
        writer = io.BytesIO()
        Server(
            framed({"jsonrpc": "2.0", "id": 9, "method": "textDocument/completion"}),
            writer,
            root=tmp_path,
        ).run()
        (answer,) = sent(writer)
        assert answer["error"]["code"] == METHOD_NOT_FOUND

    def test_a_notification_it_does_not_know_is_simply_ignored(self, tmp_path: Path) -> None:
        writer = io.BytesIO()
        Server(
            framed({"jsonrpc": "2.0", "method": "textDocument/didClose", "params": {}}),
            writer,
            root=tmp_path,
        ).run()
        assert sent(writer) == []

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
