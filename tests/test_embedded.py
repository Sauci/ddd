"""Tests for the types and constants a component declares inside its own description.

Declaring them there co-locates a library's contract in one file; it scopes nothing. The
entries are exactly those of the standalone files, the names join the same project wide
registries, and every check applies unchanged - so what is tested here is the seam: the model
accepting the two keys, the loader registering both homes into one namespace, the pointers
landing inside the component, and the outputs not knowing which home declared a name.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from conftest import (
    EXAMPLES,
    checks,
    component,
    declare,
    messages,
    project,
    render_files,
    run_analysis,
    write_tree,
)
from ddd.analysis import analyze
from ddd.diagnostics import DiagnosticBag, SeverityPolicy
from ddd.loading import load_workspace
from ddd.lsp.hover import describe_constant
from ddd.lsp.navigation import constant_at, definition, index, references, rename_problem
from ddd.lsp.ranges import Document, read
from ddd.models import ComponentFile


def scalar_type(name: str, **extra: Any) -> dict[str, Any]:
    return {"type": "scalar", "name": name, "datatype": "uint16", "conversion": {}, **extra}


def struct_type(name: str, *members: dict[str, Any]) -> dict[str, Any]:
    return {"type": "struct", "name": name, "members": list(members)}


def value_member(name: str, **extra: Any) -> dict[str, Any]:
    return {"name": name, "member": "value", "datatype": "uint16", "conversion": {}, **extra}


def typed_member(name: str, typename: str) -> dict[str, Any]:
    return {"name": name, "member": "value", "typename": typename}


def constant(name: str, value: int = 8) -> dict[str, Any]:
    return {"name": name, "value": value}


class TestTheModel:
    def test_a_component_may_declare_types_and_constants(self) -> None:
        model = ComponentFile.model_validate(
            component(
                "Lib",
                types=[scalar_type("Speed_t", unit="rpm")],
                constants=[constant("CELLS")],
            )
        )
        assert model.component.types is not None
        assert model.component.types[0].name == "Speed_t"
        assert model.component.constants is not None
        assert model.component.constants[0].value == 8

    @pytest.mark.parametrize("key", ["types", "constants"])
    def test_an_empty_list_is_refused(self, key: str) -> None:
        """Publishing nothing is done by leaving the key out, not by an empty list."""
        with pytest.raises(ValidationError, match="at least 1"):
            ComponentFile.model_validate(component("Lib", **{key: []}))

    @pytest.mark.parametrize(
        ("key", "entries"),
        [("units", ["rpm"]), ("sections", [{"section": ".x"}]), ("typo", [])],
    )
    def test_a_key_a_component_does_not_take_is_refused(self, key: str, entries: Any) -> None:
        """``units`` and ``sections`` are project wide vocabularies; neither has a home here."""
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            ComponentFile.model_validate(component("Lib", **{key: entries}))

    def test_two_entries_of_one_component_cannot_share_a_type_name(self) -> None:
        """The rule of a types file, applied to the inline home unchanged."""
        with pytest.raises(ValidationError, match="'T_t' is already declared in this file"):
            ComponentFile.model_validate(
                component("Lib", types=[scalar_type("T_t"), scalar_type("T_t")])
            )


class TestLoading:
    def test_embedded_entries_join_the_registries_with_component_pointers(self, tree: Path) -> None:
        write_tree(
            tree,
            {
                "lib.ddd.json": component(
                    "Lib", types=[scalar_type("Speed_t")], constants=[constant("CELLS")]
                )
            },
        )
        workspace = load_workspace(tree / "lib.ddd.json", DiagnosticBag())
        assert workspace is not None
        (declared_type,) = workspace.types
        assert declared_type.location("name").pointer == "component.types[0].name"
        (declared_constant,) = workspace.constants
        assert declared_constant.location().pointer == "component.constants[0]"

    def test_a_standalone_file_cannot_redeclare_an_embedded_name(self, tree: Path) -> None:
        """Embedded loads first here, so the standalone declaration is the duplicate."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "lib.ddd.json", "shared.ddd.json"),
                "lib.ddd.json": component("Lib", types=[scalar_type("Speed_t")]),
                "shared.ddd.json": {"types": [scalar_type("Speed_t")]},
            },
        )
        assert checks(bag) == ["duplicate-type"]
        rendered = messages(bag)
        assert "shared.ddd.json#types[0]: error[duplicate-type]" in rendered
        assert "lib.ddd.json#component.types[0]: first declared here" in rendered

    def test_a_component_cannot_redeclare_a_standalone_name(self, tree: Path) -> None:
        """The other order: the standalone file declared first, the embedded entry loses."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "shared.ddd.json", "lib.ddd.json"),
                "shared.ddd.json": {"constants": [constant("CELLS")]},
                "lib.ddd.json": component("Lib", constants=[constant("CELLS", 12)]),
            },
        )
        assert checks(bag) == ["duplicate-constant"]
        rendered = messages(bag)
        assert "lib.ddd.json#component.constants[0]: error[duplicate-constant]" in rendered
        assert "shared.ddd.json#constants[0]: first declared here" in rendered

    def test_two_components_cannot_embed_the_same_name(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", types=[scalar_type("Speed_t")]),
                "b.ddd.json": component("B", types=[scalar_type("Speed_t")]),
            },
        )
        assert checks(bag) == ["duplicate-type"]
        rendered = messages(bag)
        assert "b.ddd.json#component.types[0]: error[duplicate-type]" in rendered
        assert "a.ddd.json#component.types[0]: first declared here" in rendered

    def test_one_component_cannot_embed_a_constant_twice(self, tree: Path) -> None:
        """Within one list the registry answers, exactly as within one constants file."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", constants=[constant("N", 4), constant("N", 5)]),
            },
        )
        assert checks(bag) == ["duplicate-constant"]
        rendered = messages(bag)
        assert "a.ddd.json#component.constants[1]: error[duplicate-constant]" in rendered
        assert "a.ddd.json#component.constants[0]: first declared here" in rendered

    def test_a_refused_duplicate_component_registers_nothing(self, tree: Path) -> None:
        """A component that is refused whole contributes no types and no constants either."""
        write_tree(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "again.ddd.json"),
                "a.ddd.json": component("A"),
                "again.ddd.json": component(
                    "A", types=[scalar_type("Speed_t")], constants=[constant("N")]
                ),
            },
        )
        bag = DiagnosticBag()
        workspace = load_workspace(tree / "project.ddd.json", bag)
        assert workspace is not None
        assert checks(bag) == ["duplicate-component"]
        assert workspace.types == ()
        assert workspace.constants == ()


class TestALoneComponent:
    """The designed benefit of the inline home: a self-contained library file resolves alone."""

    def library(self) -> dict[str, Any]:
        return component(
            "Pump",
            declare("local", "Inlet", typename="Sensor_t"),
            declare("local", "Cells", dimensions=["PRESSURE_CELLS"]),
            declare("local", "Trend", dimensions=["SHARED_SIZE"], section=".calib"),
            types=[
                struct_type("Sensor_t", value_member("raw"), typed_member("cooked", "Temp_t")),
                scalar_type("Temp_t", unit="degC"),
            ],
            constants=[constant("PRESSURE_CELLS")],
        )

    def test_it_lists_cleanly_with_only_the_external_findings_left(self, tree: Path) -> None:
        """The embedded struct and constant resolve; what stays open genuinely is not here."""
        dictionary, bag = run_analysis(tree, {"lib.ddd.json": self.library()}, "lib.ddd.json")
        assert dictionary is not None
        assert {entry.name for entry in dictionary.listed} == {
            "Inlet.raw",
            "Inlet.cooked",
            "Cells",
        }
        assert dictionary.by_name["Cells"].spelled_shape == ("PRESSURE_CELLS",)
        assert [entry.name for entry in dictionary.constants] == ["PRESSURE_CELLS"]
        # Only the references a lone component cannot answer remain: the constant and the
        # section that live in files a project would include beside it.
        assert sorted(checks(bag)) == ["unknown-constant", "unknown-section"]

    def test_the_example_pump_resolves_alone(self) -> None:
        """The shipped example keeps proving it: ``ddd list pump.ddd.json`` answers.

        The example has not adopted ids, so ``missing-id`` is silenced here the way
        ``conftest.run_analysis`` silences it for every other fixture: it is not one of the
        cross-file gaps this test is about, unlike the sibling test above, which resolves an
        equivalent library through ``run_analysis`` and so is silenced the same way already.
        """
        bag = DiagnosticBag(SeverityPolicy.from_strings(["missing-id=ignore"]))
        workspace = load_workspace(EXAMPLES / "vocabulary" / "pump.ddd.json", bag)
        assert workspace is not None
        dictionary = analyze(workspace, bag)
        assert {entry.name for entry in dictionary.listed} == {
            "PumpSpeed",
            "ManifoldPressure",
            "TorqueLimit",
        }
        assert dictionary.by_name["TorqueLimit"].unit == "Nm"
        assert all(check.startswith("unknown-") for check in checks(bag))


class TestResolution:
    def test_another_component_resolves_through_an_embedded_type(self, tree: Path) -> None:
        """Co-location does not scope: any component of the project may name the entries."""
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "lib.ddd.json", "app.ddd.json"),
                "lib.ddd.json": component(
                    "Lib",
                    declare("output", "Inlet", typename="Sensor_t", volatile=True),
                    types=[struct_type("Sensor_t", value_member("raw"))],
                    constants=[constant("CELLS", 3)],
                ),
                "app.ddd.json": component(
                    "App",
                    declare("input", "Inlet", typename="Sensor_t", volatile=True),
                    declare("local", "Buffer", dimensions=["CELLS"]),
                ),
            },
        )
        assert dictionary is not None
        assert not checks(bag)
        assert dictionary.comparable["Inlet.raw"].consumers == ("App",)
        assert dictionary.by_name["Buffer"].shape == (3,)

    def test_the_checks_reach_into_the_embedded_lists(self, tree: Path) -> None:
        """Reserved names, collisions and units are screened wherever the entry lives."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "units.ddd.json", "lib.ddd.json"),
                "units.ddd.json": {"units": ["rpm"]},
                "lib.ddd.json": component(
                    "Lib",
                    declare("local", "Clash"),
                    types=[scalar_type("int"), scalar_type("Odd_t", unit="mph")],
                    constants=[constant("register"), constant("Clash")],
                ),
            },
        )
        assert sorted(checks(bag)) == [
            "name-collision",
            "reserved-identifier",
            "reserved-identifier",
            "unknown-unit",
        ]
        rendered = messages(bag)
        assert "lib.ddd.json#component.types[0].name: error[reserved-identifier]" in rendered
        assert "lib.ddd.json#component.constants[0].name: error[reserved-identifier]" in rendered
        assert "lib.ddd.json#component.types[1].unit: error[unknown-unit]" in rendered
        assert "lib.ddd.json#component.constants[1]: constant declared here" in rendered

    def test_a_schema_finding_inside_an_entry_carries_no_union_tag(self, tree: Path) -> None:
        """``component.types[0].limits``, not ``component.types[0].scalar.limits``."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "lib.ddd.json"),
                "lib.ddd.json": component(
                    "Lib", types=[scalar_type("T_t", limits={"min": 9, "max": 1})]
                ),
            },
        )
        assert checks(bag) == ["schema"]
        assert "lib.ddd.json#component.types[0].limits: error[schema]" in messages(bag)


class TestTheOutputsCannotTellTheHomesApart:
    """One project embeds, an equivalent one includes; every artefact is byte-identical.

    The strongest statement of "pure co-location" this suite can make: the dictionary does
    not record which home declared a name, so nothing rendered from it can differ.
    """

    def embedded(self) -> dict[str, Any]:
        return {
            "p.ddd.json": project("P", "comp.ddd.json"),
            "comp.ddd.json": component(
                "Comp",
                declare("local", "Inlet", typename="Sensor_t"),
                declare("local", "Cells", dimensions=["CELLS"], init=2),
                declare("local", "Speed", typename="Speed_t", volatile=True),
                types=[
                    struct_type(
                        "Sensor_t",
                        value_member("raw", unit="kPa"),
                        value_member("age", datatype="uint8"),
                    ),
                    scalar_type(
                        "Speed_t",
                        unit="rpm",
                        conversion={"kind": "linear", "factor": 0.25, "offset": 0.0},
                    ),
                ],
                constants=[{"name": "CELLS", "value": 4, "description": "manifold cells"}],
            ),
        }

    def standalone(self) -> dict[str, Any]:
        files = self.embedded()
        declared = files["comp.ddd.json"]["component"]
        files["types.ddd.json"] = {"types": declared.pop("types")}
        files["constants.ddd.json"] = {"constants": declared.pop("constants")}
        files["p.ddd.json"] = project("P", "comp.ddd.json", "types.ddd.json", "constants.ddd.json")
        return files

    def rendered(self, base: Path, files: dict[str, Any]) -> dict[str, str]:
        dictionary, bag = run_analysis(base, files, "p.ddd.json")
        assert dictionary is not None
        assert not checks(bag)
        return {
            generated.path.name: generated.content
            for generated in render_files(dictionary, base / "out")
        }

    def test_the_c_and_the_a2l_are_byte_identical(self, tmp_path: Path) -> None:
        first = self.rendered(tmp_path / "embedded", self.embedded())
        second = self.rendered(tmp_path / "standalone", self.standalone())
        assert set(first) == set(second)
        for name in sorted(first):
            assert first[name] == second[name], f"{name} differs between the two homes"

    def test_even_the_dumped_dictionaries_are_identical(self, tmp_path: Path) -> None:
        """What ``ddd dump`` archives records no declaring file, so no format bump either."""
        first, _ = run_analysis(tmp_path / "embedded", self.embedded(), "p.ddd.json")
        second, _ = run_analysis(tmp_path / "standalone", self.standalone(), "p.ddd.json")
        assert first is not None and second is not None
        assert first.model_dump_json(indent=2) == second.model_dump_json(indent=2)


class TestTheEditor:
    def library(self, tmp_path: Path) -> Path:
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "lib.ddd.json", "app.ddd.json"),
                "lib.ddd.json": component(
                    "Lib",
                    declare("output", "Inlet", typename="Sensor_t", volatile=True),
                    types=[struct_type("Sensor_t", value_member("raw", dimensions=["CELLS"]))],
                    constants=[{"name": "CELLS", "value": 4, "description": "cells"}],
                ),
                "app.ddd.json": component(
                    "App",
                    declare("input", "Inlet", typename="Sensor_t", volatile=True),
                    declare("local", "Buffer", dimensions=["CELLS"]),
                ),
            },
        )
        return tmp_path / "p.ddd.json"

    def index_of(self, root: Path) -> Any:
        return index(load_workspace(root, DiagnosticBag()))

    def test_a_typename_in_another_file_leads_to_the_embedded_type(self, tmp_path: Path) -> None:
        built = self.index_of(self.library(tmp_path))
        consumer = tmp_path / "app.ddd.json"
        (site,) = definition(
            built, read(consumer, {}), consumer, "component.interface[0].definition.typename"
        )
        assert site.path == tmp_path / "lib.ddd.json"
        assert site.pointer == "component.types[0]"

    def test_a_dimension_in_another_file_leads_to_the_embedded_constant(
        self, tmp_path: Path
    ) -> None:
        built = self.index_of(self.library(tmp_path))
        consumer = tmp_path / "app.ddd.json"
        (site,) = definition(
            built,
            read(consumer, {}),
            consumer,
            "component.interface[1].definition.dimensions[0]",
        )
        assert site.path == tmp_path / "lib.ddd.json"
        assert site.pointer == "component.constants[0]"

    def test_the_entries_answer_from_inside_the_embedded_lists(self, tmp_path: Path) -> None:
        """On the entry's own name, definition is a self jump and references find every use."""
        built = self.index_of(self.library(tmp_path))
        library = tmp_path / "lib.ddd.json"
        document = read(library, {})
        (site,) = definition(built, document, library, "component.types[0].name")
        assert site.pointer == "component.types[0]"
        found = references(built, document, "component.constants[0].name")
        assert {(place.path.name, place.pointer) for place in found} == {
            ("lib.ddd.json", "component.constants[0]"),
            ("lib.ddd.json", "component.types[0].members[0].dimensions[0]"),
            ("app.ddd.json", "component.interface[1].definition.dimensions[0]"),
        }

    def test_hover_reads_the_embedded_entries(self, tmp_path: Path) -> None:
        """The name under the cursor is recognised, and the resolved answer exists for it."""
        root = self.library(tmp_path)
        library = tmp_path / "lib.ddd.json"
        document = read(library, {})
        assert constant_at(document, "component.constants[0].name") == "CELLS"
        assert constant_at(document, "component.types[0].members[0].dimensions[0]") == "CELLS"
        workspace = load_workspace(root, DiagnosticBag())
        assert workspace is not None
        dictionary = analyze(workspace, DiagnosticBag())
        described = describe_constant(dictionary, "CELLS")
        assert described is not None
        assert "**CELLS** = 4" in described

    def test_renaming_onto_an_embedded_name_is_refused(self, tmp_path: Path) -> None:
        """The registries feed the refusal, so the home of the occupant changes nothing."""
        built = self.index_of(self.library(tmp_path))
        assert rename_problem(built, "Sensor_t") == (
            "'Sensor_t' is the name of the type 'Sensor_t', which shares c's namespace with "
            "the variables"
        )
        assert rename_problem(built, "CELLS") == (
            "'CELLS' is the name of the declared constant 'CELLS', which shares c's "
            "namespace with the variables"
        )

    def test_a_diagnostic_range_lands_on_the_embedded_key(self) -> None:
        """The pointer of an embedded finding underlines the key it names."""
        text = (
            '{\n  "component": {\n    "name": "Lib",\n    "interface": [],\n'
            '    "types": [\n      { "type": "scalar", "name": "int",\n'
            '        "datatype": "uint16", "conversion": {} }\n    ]\n  }\n}\n'
        )
        document = Document(text)
        span = document.range_of("component.types[0].name")
        assert span["start"]["line"] == 5
        assert text.splitlines()[5][span["start"]["character"] :].startswith('"name": "int"')
