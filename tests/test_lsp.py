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
        published = {
            uri_to_path(message["params"]["uri"]).name: message["params"]["diagnostics"]
            for message in sent(writer)
        }
        assert published["component_b.ddd.json"][0]["code"] == "multiple-producers"
        # The file that was not opened is published too, which is the point.
        assert published["component_c.ddd.json"][0]["code"] == "definition-mismatch"

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
        published = {
            uri_to_path(message["params"]["uri"]).name: message["params"]["diagnostics"]
            for message in sent(writer)
        }
        assert published["a.ddd.json"][0]["code"] == "missing-producer"

        # Somebody produces it now, so the project is clean and the squiggle has to go.
        write_tree(tmp_path, {"a.ddd.json": component("A", declare("output", "Shared"))})
        writer = io.BytesIO()
        server.writer = writer
        server.refresh(tmp_path / "a.ddd.json")
        withdrawn = {
            uri_to_path(message["params"]["uri"]).name: message["params"]["diagnostics"]
            for message in sent(writer)
        }
        assert withdrawn == {"a.ddd.json": [], "b.ddd.json": []}

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

    def test_a_request_it_cannot_serve_is_refused_rather_than_ignored(self, tmp_path: Path) -> None:
        """A client still waiting for an answer looks exactly like a server that has died."""
        writer = io.BytesIO()
        Server(
            framed({"jsonrpc": "2.0", "id": 9, "method": "textDocument/rename"}),
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
