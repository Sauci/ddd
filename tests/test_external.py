"""External types: names DDD does not declare, defined by a hand written header.

An ``external`` entry names a c type and the header that defines it; only a structure member
may name one, as opaque storage. What is tested here is the whole road: the contract rules of
the entry and its header spelling, the opaque member refusals, resolution without a leaf, the
generated c with its include lines, the a2l staying silent about the member, the alignment
estimate declining to guess, and the editor answering with the name and the header.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from conftest import (
    checks,
    component,
    declare,
    messages,
    project,
    render_files,
    run_analysis,
    write_tree,
)
from ddd.diagnostics import DiagnosticBag
from ddd.ir import DICTIONARY_FORMAT, ResolvedMember
from ddd.loading import load_workspace
from ddd.models import ExternalType, TypesFile

ROOT = Path(__file__).resolve().parents[1]


def external(name: str = "Drv_t", header: str = "drv.h", **extra: Any) -> dict[str, Any]:
    return {"type": "external", "name": name, "header": header, **extra}


def val(name: str, datatype: str = "uint16", **extra: Any) -> dict[str, Any]:
    storage: dict[str, Any] = (
        {} if "typename" in extra else {"datatype": datatype, "conversion": {"kind": "identity"}}
    )
    return {"name": name, "member": "value", **storage, **extra}


def struct(name: str, *members: dict[str, Any]) -> dict[str, Any]:
    return {"type": "struct", "name": name, "members": list(members)}


def types(*entries: dict[str, Any]) -> dict[str, Any]:
    return {"types": list(entries)}


def opaque_project(**member_extra: Any) -> dict[str, Any]:
    """A project with one struct holding one external member and one plain one."""
    return {
        "project.ddd.json": project("P", "t.ddd.json", "a.ddd.json"),
        "t.ddd.json": types(
            external(),
            struct("S_t", val("opaque", typename="Drv_t", **member_extra), val("plain")),
        ),
        "a.ddd.json": component("A", declare("local", "X", typename="S_t")),
    }


class TestTheEntry:
    """The contract of the ``external`` entry itself."""

    def test_the_three_spellings_of_a_header_are_accepted(self) -> None:
        for header in ("my_driver.h", "<os_types.h>", "drivers/status.h", "<sys/types.h>"):
            model = TypesFile.model_validate(types(external(header=header)))
            entry = model.types[0]
            assert isinstance(entry, ExternalType)
            assert entry.header == header

    def test_a_description_is_optional_and_kept(self) -> None:
        model = TypesFile.model_validate(types(external(description="the vendor's word")))
        assert model.types[0].description == "the vendor's word"

    @pytest.mark.parametrize(
        "header",
        [
            "",  # empty: nothing to include
            "my driver.h",  # whitespace unbalances the generated line
            '"my_driver.h"',  # the quoted form is spelled bare
            "<os_types.h",  # an angle form that never closes
            "<>",  # an angle form around nothing
            "<a<b>.h>",  # an angle bracket inside the angle form
            "my>driver.h",  # an angle bracket in the quoted form
            "my<driver.h",
        ],
    )
    def test_a_header_spelling_that_cannot_be_included_is_refused(self, header: str) -> None:
        with pytest.raises(ValidationError):
            TypesFile.model_validate(types(external(header=header)))

    def test_the_header_is_required(self) -> None:
        with pytest.raises(ValidationError, match="header"):
            TypesFile.model_validate(types({"type": "external", "name": "Drv_t"}))

    def test_the_name_follows_the_type_name_rules(self) -> None:
        """A base datatype spelling and a non-identifier die exactly as on the other kinds."""
        with pytest.raises(ValidationError, match="spells a base datatype"):
            TypesFile.model_validate(types(external(name="uint16")))
        with pytest.raises(ValidationError):
            TypesFile.model_validate(types(external(name="not a name")))

    def test_a_key_of_the_other_kinds_is_refused(self) -> None:
        """An external type has no storage of its own to describe."""
        with pytest.raises(ValidationError):
            TypesFile.model_validate(types(external(datatype="uint16")))

    def test_two_entries_of_one_file_cannot_share_a_name(self) -> None:
        with pytest.raises(ValidationError, match="already declared in this file"):
            TypesFile.model_validate(types(external("Twice_t"), struct("Twice_t", val("v"))))


class TestOpaqueMembers:
    """A member naming an external type is opaque storage: no meaning, no a2l block."""

    def test_a_stated_a2l_block_is_refused_where_it_is_written(self, tree: Path) -> None:
        _, bag = run_analysis(tree, opaque_project(a2l={"export": True}))
        assert checks(bag) == ["schema"]
        assert "t.ddd.json#types[1].members[0].a2l:" in messages(bag)
        assert "no record for the 'a2l' block to shape" in messages(bag)

    @pytest.mark.parametrize(
        "stated",
        [
            {"unit": "kPa"},
            {"conversion": {"kind": "identity"}},
            {"limits": {"min": 0, "max": 1}},
        ],
    )
    def test_meaning_keys_are_refused_by_the_contract(
        self, tree: Path, stated: dict[str, Any]
    ) -> None:
        """The rule every ``typename`` member already has; an external name changes nothing."""
        _, bag = run_analysis(tree, opaque_project(**stated))
        assert checks(bag) == ["schema"]
        assert "t.ddd.json#types[1].members[0]:" in messages(bag)
        assert "already fixes what this value means" in messages(bag)

    def test_a_bits_member_cannot_name_one(self, tree: Path) -> None:
        files = opaque_project()
        files["t.ddd.json"]["types"][1]["members"][0] = {
            "name": "opaque",
            "member": "bits",
            "typename": "Drv_t",
            "bits": 2,
        }
        _, bag = run_analysis(tree, files)
        assert checks(bag) == ["schema"]
        assert "a bitfield needs a base integer datatype" in messages(bag)

    def test_dimensions_are_allowed(self, tree: Path) -> None:
        dictionary, bag = run_analysis(tree, opaque_project(dimensions=[4]))
        assert checks(bag) == []
        assert dictionary is not None
        member = dictionary.types[0].members[0]
        assert member.dimensions == (4,)

    def test_a_definition_naming_an_external_type_is_type_kind(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "t.ddd.json", "a.ddd.json"),
                "t.ddd.json": types(external()),
                "a.ddd.json": component("A", declare("local", "X", typename="Drv_t")),
            },
        )
        assert checks(bag) == ["type-kind"]
        rendered = messages(bag)
        assert "'X' is declared as 'Drv_t', but that is an external type" in rendered
        assert "only a structure member may name one" in rendered
        assert "declared here" in rendered, "the note points at the entry"


class TestResolution:
    """An external member resolves to opaque storage: verbatim in the c, absent everywhere else."""

    def test_the_member_produces_no_leaf(self, tree: Path) -> None:
        dictionary, bag = run_analysis(tree, opaque_project())
        assert checks(bag) == []
        assert dictionary is not None
        assert [leaf.path for leaf in dictionary.leaves] == ["X.plain"]
        assert [instance.name for instance in dictionary.instances] == ["X"]

    def test_the_dump_records_the_name_and_the_header(self, tree: Path) -> None:
        """The dump shape: ``external`` and ``header`` beside null storage, format still 5."""
        dictionary, _ = run_analysis(tree, opaque_project())
        assert dictionary is not None
        dumped = json.loads(dictionary.model_dump_json())
        assert dumped["format"] == DICTIONARY_FORMAT == 5
        member = dumped["types"][0]["members"][0]
        assert member["external"] == "Drv_t"
        assert member["header"] == "drv.h"
        assert member["datatype"] is None
        assert member["type"] is None

    def test_the_dictionary_contract_keeps_the_pair_together(self) -> None:
        with pytest.raises(ValidationError, match="stated together"):
            ResolvedMember(name="m", external="Drv_t")
        with pytest.raises(ValidationError, match="stated together"):
            ResolvedMember(name="m", header="drv.h")
        with pytest.raises(ValidationError, match="opaque storage"):
            ResolvedMember(name="m", external="Drv_t", header="drv.h", datatype="uint8")
        with pytest.raises(ValidationError, match="opaque storage"):
            ResolvedMember(name="m", external="Drv_t", header="drv.h", type="S_t")

    def test_an_array_of_structures_still_skips_the_member(self, tree: Path) -> None:
        files = opaque_project()
        files["a.ddd.json"] = component("A", declare("local", "X", typename="S_t", dimensions=[2]))
        dictionary, bag = run_analysis(tree, files)
        assert checks(bag) == []
        assert dictionary is not None
        assert [leaf.path for leaf in dictionary.leaves] == ["X[0].plain", "X[1].plain"]

    def test_a_structure_of_only_external_members_resolves_with_no_leaf(self, tree: Path) -> None:
        """Legal, and honestly empty: the variable exists, and nothing reaches list or a2l."""
        files = opaque_project()
        files["t.ddd.json"] = types(external(), struct("S_t", val("opaque", typename="Drv_t")))
        dictionary, bag = run_analysis(tree, files)
        assert checks(bag) == []
        assert dictionary is not None
        assert [instance.name for instance in dictionary.instances] == ["X"]
        assert dictionary.leaves == ()
        rendered = render_files(dictionary, tree / "out")
        a2l = next(file.content for file in rendered if file.path.name == "P.a2l")
        assert "GROUP" not in a2l, "a component whose only object is opaque exports nothing"

    def test_a_component_may_embed_an_external_type(self, tree: Path) -> None:
        """The inline home works exactly like the standalone one, pointer included."""
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    declare("local", "X", typename="S_t"),
                    types=[external(), struct("S_t", val("opaque", typename="Drv_t"))],
                ),
            },
        )
        assert checks(bag) == []
        assert dictionary is not None
        assert dictionary.types[0].members[0].header == "drv.h"

    def test_two_files_cannot_declare_one_external_name(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "one.ddd.json", "two.ddd.json", "a.ddd.json"),
                "one.ddd.json": types(external()),
                "two.ddd.json": types(external(header="other.h")),
                "a.ddd.json": component("A", declare("local", "X")),
            },
        )
        assert "duplicate-type" in checks(bag)

    def test_a_variable_cannot_take_an_external_name(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "t.ddd.json", "a.ddd.json"),
                "t.ddd.json": types(external()),
                "a.ddd.json": component("A", declare("local", "Drv_t")),
            },
        )
        assert checks(bag) == ["name-collision"]
        assert "also the name of a type" in messages(bag)

    def test_a_reserved_external_name_is_reported(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "t.ddd.json", "a.ddd.json"),
                "t.ddd.json": types(external(name="int")),
                "a.ddd.json": component("A", declare("local", "X")),
            },
        )
        assert checks(bag) == ["reserved-identifier"]

    def test_a_unit_vocabulary_has_nothing_to_check_on_one(self, tree: Path) -> None:
        """An external type states no unit; declaring a vocabulary must not trip over it."""
        files = opaque_project()
        files["project.ddd.json"] = project("P", "u.ddd.json", "t.ddd.json", "a.ddd.json")
        files["u.ddd.json"] = {"units": ["kPa"]}
        _, bag = run_analysis(tree, files)
        assert checks(bag) == []


class TestAlignmentEstimate:
    """A structure containing an external member gets no section-alignment estimate."""

    def section(self, alignment: int = 2) -> dict[str, Any]:
        return {"sections": [{"section": ".fast", "access": "read-write", "alignment": alignment}]}

    def test_the_estimate_declines_rather_than_guesses(self, tree: Path) -> None:
        """A uint64 beside the external member would need 8, but the whole is unknown."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "s.ddd.json", "t.ddd.json", "a.ddd.json"),
                "s.ddd.json": self.section(),
                "t.ddd.json": types(
                    external(),
                    struct("S_t", val("wide", "uint64"), val("opaque", typename="Drv_t")),
                ),
                "a.ddd.json": component(
                    "A", declare("local", "X", typename="S_t", section=".fast")
                ),
            },
        )
        assert checks(bag) == []

    def test_without_the_external_member_the_estimate_still_fires(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "s.ddd.json", "t.ddd.json", "a.ddd.json"),
                "s.ddd.json": self.section(),
                "t.ddd.json": types(struct("S_t", val("wide", "uint64"))),
                "a.ddd.json": component(
                    "A", declare("local", "X", typename="S_t", section=".fast")
                ),
            },
        )
        assert checks(bag) == ["section-alignment"]

    def test_the_unknown_propagates_through_nesting(self, tree: Path) -> None:
        """A structure nesting one that holds an external member is just as unknown."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "s.ddd.json", "t.ddd.json", "a.ddd.json"),
                "s.ddd.json": self.section(),
                "t.ddd.json": types(
                    external(),
                    struct("Inner_t", val("opaque", typename="Drv_t")),
                    struct("Outer_t", val("wide", "uint64"), val("inner", typename="Inner_t")),
                ),
                "a.ddd.json": component(
                    "A", declare("local", "X", typename="Outer_t", section=".fast")
                ),
            },
        )
        assert checks(bag) == []

    def test_a_definition_naming_the_external_type_gets_no_estimate_either(
        self, tree: Path
    ) -> None:
        """The declaration is refused as type-kind; the section walk stays silent about it."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "s.ddd.json", "t.ddd.json", "a.ddd.json"),
                "s.ddd.json": self.section(),
                "t.ddd.json": types(external()),
                "a.ddd.json": component(
                    "A", declare("local", "X", typename="Drv_t", section=".fast")
                ),
            },
        )
        assert checks(bag) == ["type-kind"]

    def test_a_cycle_on_the_way_is_not_mistaken_for_an_external(self, tree: Path) -> None:
        """The walk does not follow a name twice; the cycle keeps its own finding."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "s.ddd.json", "t.ddd.json", "a.ddd.json"),
                "s.ddd.json": self.section(),
                "t.ddd.json": types(
                    struct("A_t", val("wide", "uint64"), val("b", typename="B_t")),
                    struct("B_t", val("a", typename="A_t")),
                ),
                "a.ddd.json": component(
                    "A", declare("local", "X", typename="A_t", section=".fast")
                ),
            },
        )
        assert "type-cycle" in checks(bag)

    def test_an_unknown_member_type_estimates_from_the_rest(self, tree: Path) -> None:
        """An unknown name is not an external one: the walk skips it and keeps its answer."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "s.ddd.json", "t.ddd.json", "a.ddd.json"),
                "s.ddd.json": self.section(),
                "t.ddd.json": types(
                    struct("S_t", val("wide", "uint64"), val("gone", typename="Ghost_t"))
                ),
                "a.ddd.json": component(
                    "A", declare("local", "X", typename="S_t", section=".fast")
                ),
            },
        )
        assert "unknown-type" in checks(bag)
        assert "section-alignment" in checks(bag)


class TestGeneratedC:
    """The member verbatim in the struct, and the headers offered and emitted as includes."""

    def rich_project(self) -> dict[str, Any]:
        """Three external types over two headers, one member an array, one struct placed."""
        return {
            "project.ddd.json": project("P", "s.ddd.json", "t.ddd.json", "a.ddd.json"),
            "s.ddd.json": {
                "sections": [{"section": ".fast", "access": "read-write", "alignment": 8}]
            },
            "t.ddd.json": types(
                external("DriverStatus_t", "zeta/driver.h"),
                external("OsHandle_t", "<os_types.h>"),
                external("OsMutex_t", "<os_types.h>"),
                struct(
                    "S_t",
                    val("status", typename="DriverStatus_t"),
                    val("log", typename="DriverStatus_t", dimensions=[4]),
                    val("handle", typename="OsHandle_t"),
                    val("lock", typename="OsMutex_t"),
                    val("plain"),
                ),
            ),
            "a.ddd.json": component("A", declare("local", "X", typename="S_t", section=".fast")),
        }

    def generated(self, tree: Path, name: str = "ddd_types.h") -> str:
        dictionary, bag = run_analysis(tree, self.rich_project())
        assert checks(bag) == []
        assert dictionary is not None
        out = tree / "out"
        files = {file.path.name: file for file in render_files(dictionary, out)}
        return files[name].content

    def test_the_member_is_declared_verbatim(self, tree: Path) -> None:
        header = self.generated(tree)
        assert "    DriverStatus_t status;" in header
        assert "    DriverStatus_t log[4];" in header
        assert "    OsHandle_t handle;" in header

    def test_the_headers_are_included_deduplicated_and_sorted(self, tree: Path) -> None:
        """Two types of one header cost one line; the order is the spelling's, said so."""
        header = self.generated(tree)
        assert header.count("#include <os_types.h>") == 1
        assert header.count('#include "zeta/driver.h"') == 1
        # '<' sorts before a letter, so the angle form leads; both come after <stdint.h>.
        assert (
            header.index("#include <stdint.h>")
            < header.index("#include <os_types.h>")
            < header.index('#include "zeta/driver.h"')
            < header.index("typedef struct")
        )

    def test_the_output_is_byte_deterministic(self, tree: Path) -> None:
        dictionary, _ = run_analysis(tree, self.rich_project())
        assert dictionary is not None
        first = render_files(dictionary, tree / "one")
        second = render_files(dictionary, tree / "two")
        for a, b in zip(first, second, strict=True):
            assert a.content.encode("utf-8") == b.content.encode("utf-8")

    def test_a_project_without_externals_emits_no_include_block(self, tree: Path) -> None:
        dictionary, _ = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X")),
            },
        )
        assert dictionary is not None
        (generated,) = [
            file
            for file in render_files(dictionary, tree / "out")
            if file.path.name == "ddd_types.h"
        ]
        assert "headers defining the external types" not in generated.content


class TestA2l:
    """An external member reaches no a2l: no record, and no GROUP reference."""

    def test_the_member_is_absent_and_its_siblings_are_not(self, tree: Path) -> None:
        dictionary, bag = run_analysis(tree, opaque_project())
        assert checks(bag) == []
        assert dictionary is not None
        files = {file.path.name: file for file in render_files(dictionary, tree / "out")}
        a2l = files["P.a2l"].content
        assert "X.plain" in a2l, "the sibling member keeps its record and its group entry"
        assert "X.opaque" not in a2l
        assert "Drv_t" not in a2l
        assert "drv.h" not in a2l


class TestTheEditor:
    """Hover says the name and the header; navigation and rename treat the name as a type."""

    def workspace_files(self) -> dict[str, Any]:
        return {
            "p.ddd.json": project("P", "t.ddd.json", "a.ddd.json"),
            "t.ddd.json": types(
                external("Drv_t", "drv.h", description="the vendor's status word"),
                struct("S_t", val("opaque", typename="Drv_t"), val("plain")),
            ),
            "a.ddd.json": component("A", declare("output", "X", typename="S_t")),
        }

    def served(self, tree: Path, path: Path, pointer: str) -> Any:
        from ddd.lsp.ranges import Document
        from ddd.lsp.server import Server
        from test_lsp import build_record, framed, sent

        build_record(tree, tree / "p.ddd.json")
        position = Document(path.read_text(encoding="utf-8")).range_of(pointer)["start"]
        request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "textDocument/hover",
            "params": {"textDocument": {"uri": path.as_uri()}, "position": position},
        }
        writer = io.BytesIO()
        Server(framed(request), writer, root=tree).run()
        (answer,) = sent(writer)
        return answer["result"]

    def test_hover_on_the_entry_shows_the_name_and_the_header(self, tree: Path) -> None:
        write_tree(tree, self.workspace_files())
        result = self.served(tree, tree / "t.ddd.json", "types[0].name")
        rendered = result["contents"]["value"]
        assert "**Drv_t**" in rendered
        assert "`drv.h`" in rendered
        assert "the vendor's status word" in rendered

    def test_hover_on_a_member_naming_one_shows_the_same(self, tree: Path) -> None:
        write_tree(tree, self.workspace_files())
        result = self.served(tree, tree / "t.ddd.json", "types[1].members[0].typename")
        assert "**Drv_t**" in result["contents"]["value"]
        assert "external type, defined by `drv.h`" in result["contents"]["value"]

    def test_hover_on_a_struct_entry_still_says_nothing(self, tree: Path) -> None:
        """A struct is not an external type, and the entry declares no variable to describe."""
        write_tree(tree, self.workspace_files())
        assert self.served(tree, tree / "t.ddd.json", "types[1].name") is None

    def test_hover_on_a_declaration_typename_still_describes_the_variable(self, tree: Path) -> None:
        """The structured hover of a declaration survives the external answer being tried."""
        write_tree(tree, self.workspace_files())
        result = self.served(
            tree, tree / "a.ddd.json", "component.interface[0].definition.typename"
        )
        assert "**X**" in result["contents"]["value"]

    def test_describe_external_without_a_description_stops_at_the_header(self, tree: Path) -> None:
        from ddd.lsp.hover import describe_external
        from ddd.lsp.navigation import workspaces

        files = self.workspace_files()
        files["t.ddd.json"]["types"][0].pop("description")
        write_tree(tree, files)
        projects = workspaces([], tree / "t.ddd.json", tree)
        described = describe_external(projects, "Drv_t")
        assert described == "**Drv_t** — external type, defined by `drv.h`"
        assert describe_external(projects, "S_t") is None

    def test_type_at_answers_from_the_entry_and_from_a_typename(self, tree: Path) -> None:
        from ddd.lsp.navigation import type_at
        from ddd.lsp.ranges import Document

        write_tree(tree, self.workspace_files())
        document = Document((tree / "t.ddd.json").read_text(encoding="utf-8"))
        assert type_at(document, "types[0].header") == "Drv_t"
        assert type_at(document, "types[1].members[0].typename") == "Drv_t"
        assert type_at(document, "types") is None

    def test_type_at_survives_an_entry_without_a_name(self) -> None:
        from ddd.lsp.navigation import type_at
        from ddd.lsp.ranges import Document

        document = Document(json.dumps({"types": [{"type": "external", "header": "x.h"}]}))
        assert type_at(document, "types[0].type") is None

    def test_navigation_reaches_the_entry_and_back(self, tree: Path) -> None:
        from ddd.lsp.navigation import definition, index, references
        from ddd.lsp.ranges import Document

        write_tree(tree, self.workspace_files())
        workspace = load_workspace(tree / "p.ddd.json", DiagnosticBag())
        assert workspace is not None
        built = index(workspace)
        document = Document((tree / "t.ddd.json").read_text(encoding="utf-8"))
        # From the member's typename to the entry that declares the external type.
        (site,) = definition(built, document, tree / "t.ddd.json", "types[1].members[0].typename")
        assert site.pointer == "types[0]"
        # From the entry, every member that names it.
        found = references(built, document, "types[0].name")
        assert {place.pointer for place in found} == {"types[0]", "types[1].members[0].typename"}

    def test_a_rename_onto_the_external_name_is_refused(self, tree: Path) -> None:
        from ddd.lsp.navigation import index, rename_problem

        write_tree(tree, self.workspace_files())
        workspace = load_workspace(tree / "p.ddd.json", DiagnosticBag())
        assert workspace is not None
        refused = rename_problem(index(workspace), "Drv_t")
        assert refused is not None
        assert "the name of the type 'Drv_t'" in refused


class TestTheShippedExample:
    """``examples/structures`` teaches the feature and stays check-clean."""

    def test_the_example_declares_an_external_type(self) -> None:
        declared = json.loads(
            (ROOT / "examples" / "structures" / "types.ddd.json").read_text(encoding="utf-8")
        )
        entry = next(item for item in declared["types"] if item["type"] == "external")
        assert entry["name"] == "DriverStatus_t"
        assert entry["header"] == "driver_status.h"
        assert (ROOT / "examples" / "structures" / "include" / "driver_status.h").is_file()

    def test_the_published_types_schema_knows_the_kind(self) -> None:
        schema = (ROOT / "schemas" / "ddd_types.schema.json").read_text(encoding="utf-8")
        assert '"external"' in schema
        assert "header" in schema
