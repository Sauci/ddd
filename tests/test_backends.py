"""Tests of the boundary itself: the contract, the backend protocol, and who knows what."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from conftest import DEMO, TEMPLATES, component, declare, project, run_analysis
from ddd.backends import A2lBackend, Backend, CBackend, GeneratedFile, render
from ddd.backends.a2l.types import A2L_TYPE
from ddd.backends.c.types import C_TYPE
from ddd.ir import DataDictionary
from ddd.models import Datatype, ObjectKind

SOURCE = Path(__file__).resolve().parents[1] / "src" / "ddd"


def imported_modules(path: Path) -> set[str]:
    """Every ``ddd.*`` module the given source file imports."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("ddd"):
            modules.add(node.module)
        elif isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names if alias.name.startswith("ddd"))
    return modules


def runtime_imported_modules(path: Path) -> set[str]:
    """Every ``ddd.*`` module a source file imports outside an ``if TYPE_CHECKING:`` block."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    guarded: set[int] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.If)
            and isinstance(node.test, ast.Name)
            and node.test.id == "TYPE_CHECKING"
        ):
            guarded.update(id(child) for child in ast.walk(node))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if id(node) in guarded:
            continue
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("ddd"):
            modules.add(node.module)
        elif isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names if alias.name.startswith("ddd"))
    return modules


class TestLayering:
    """The split is only real if the import graph enforces it."""

    def test_the_core_contracts_know_no_output_format(self) -> None:
        # reserved.py is the documented exception: which names a c compiler claims is a
        # property of the input contract, because generating c is not optional. It is a file
        # of its own precisely so that this guard stays strict about everything else.
        text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (SOURCE / "models").glob("*.py")
            if path.name != "reserved.py"
        )
        # Spellings that belong to one output format only. "measurement" is not among them:
        # that is DDD's own word for an online value and part of the input file format - the
        # a2l keyword MEASUREMENT just happens to coincide with it.
        for word in ("uint16_t", "int8_t", "UWORD", "SBYTE", "COMPU_", "AXIS_PTS", "stdint"):
            assert word not in text, f"{word} leaked into ddd.models"

    def test_the_front_end_does_not_import_a_backend(self) -> None:
        for name in ("loading.py", "analysis.py", "ir.py", "diagnostics.py"):
            imports = imported_modules(SOURCE / name)
            assert not [module for module in imports if module.startswith("ddd.backends")], (
                f"{name} imports a backend"
            )

    def test_a_backend_does_not_import_the_front_end_internals(self) -> None:
        forbidden = {"ddd.loading", "ddd.analysis"}
        for path in SOURCE.joinpath("backends").rglob("*.py"):
            leaked = imported_modules(path) & forbidden
            assert not leaked, f"{path.name} reaches into {sorted(leaked)}"

    def test_the_backends_do_not_import_each_other(self) -> None:
        for path in SOURCE.joinpath("backends", "c").rglob("*.py"):
            assert not [m for m in imported_modules(path) if m.startswith("ddd.backends.a2l")]
        for path in SOURCE.joinpath("backends", "a2l").rglob("*.py"):
            assert not [m for m in imported_modules(path) if m.startswith("ddd.backends.c")]

    def test_both_backends_satisfy_the_protocol(self) -> None:
        assert isinstance(CBackend(TEMPLATES), Backend)
        assert isinstance(A2lBackend(), Backend)

    def test_every_datatype_is_spelled_by_every_backend(self) -> None:
        assert set(C_TYPE) == set(Datatype)
        assert set(A2L_TYPE) == set(Datatype)

    def test_the_discriminator_tags_are_derived_from_the_unions(self) -> None:
        """The loader hides these from diagnostics; a new variant must not be forgotten."""
        from ddd.loading import _UNION_TAGS

        assert {kind.value for kind in ObjectKind} <= _UNION_TAGS
        assert {"identity", "linear", "enum"} <= _UNION_TAGS
        assert all(isinstance(tag, str) for tag in _UNION_TAGS)

    def test_the_contract_carries_no_presentation_logic(self) -> None:
        """How a finding is phrased belongs to the checker, not to the file format."""
        text = (SOURCE / "models" / "objects.py").read_text(encoding="utf-8")
        for word in ("describe_field", "interface_signature", "storage_signature"):
            assert word not in text

    def test_the_plugin_api_sees_what_a_backend_sees(self) -> None:
        """A plugin gets the dictionary and the diagnostics: not the loader, not the analysis,
        and no backend at runtime - the Backend protocol is named under TYPE_CHECKING only."""
        imports = runtime_imported_modules(SOURCE / "plugins.py")
        assert not imports & {"ddd.loading", "ddd.analysis"}, imports
        assert not [module for module in imports if module.startswith("ddd.backends")], imports


class TestContract:
    def test_the_dictionary_round_trips_through_json(self, tree: Path) -> None:
        dictionary, _ = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    declare("local", "Ax", "uint16", kind="axis", size=3, input="M"),
                    declare("local", "M", "uint16", unit="Hz", conversion={"factor": 0.5}),
                    declare("local", "C", "uint8", kind="curve", axis="Ax", init=[1, 2, 3]),
                ),
            },
        )
        assert dictionary is not None
        again = DataDictionary.model_validate_json(dictionary.model_dump_json())
        assert again == dictionary

    def test_a_backend_generates_the_same_from_a_reloaded_dictionary(self, tree: Path) -> None:
        """A third party feeding `ddd dump` output back in must get identical output."""
        dictionary, _ = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X", "uint16", init=7)),
            },
        )
        assert dictionary is not None
        reloaded = DataDictionary.model_validate(json.loads(dictionary.model_dump_json()))
        direct = _contents(render(dictionary, [CBackend(TEMPLATES), A2lBackend()], tree / "a"))
        indirect = _contents(render(reloaded, [CBackend(TEMPLATES), A2lBackend()], tree / "b"))
        assert direct == indirect

    def test_everything_is_resolved_for_the_backends(self, tree: Path) -> None:
        """A backend never has to derive anything: limits and shapes are already there."""
        dictionary, _ = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    declare("local", "Ax", "uint16", kind="axis", size=4),
                    declare("local", "C", "uint8", kind="curve", axis="Ax"),
                ),
            },
        )
        assert dictionary is not None
        curve = dictionary.by_name["C"]
        assert curve.shape == (4,)  # taken from the axis, not left to the backend
        assert curve.limits.min == 0  # filled in from datatype and conversion
        assert curve.limits.max == 255

    def test_the_contract_publishes_a_schema(self) -> None:
        schema = DataDictionary.model_json_schema()
        assert schema["additionalProperties"] is False
        assert set(schema["properties"]) == {
            "format",
            "name",
            "description",
            "source",
            "components",
            "objects",
            "enums",
            "constants",
            "rasters",
            "types",
            "instances",
            "leaves",
            "plugins",
            "extensions",
        }


class TestDriver:
    def test_backends_can_be_selected_one_by_one(self, tree: Path) -> None:
        dictionary, _ = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X")),
            },
        )
        assert dictionary is not None
        c_only = _names(render(dictionary, [CBackend(TEMPLATES)], tree / "gen"))
        a2l_only = _names(render(dictionary, [A2lBackend()], tree / "gen"))
        assert not [name for name in c_only if name.endswith(".a2l")]
        assert a2l_only == {"P.a2l"}

    def test_a_third_backend_needs_no_change_anywhere(self, tree: Path) -> None:
        """The point of the split: a new output format is a new object, nothing else."""

        class CsvBackend:
            name = "csv"

            def generate(self, dictionary: DataDictionary, output_dir: Path) -> list[GeneratedFile]:
                rows = "\n".join(
                    f"{e.name},{e.datatype.value},{e.owner}" for e in dictionary.objects
                )
                return [GeneratedFile(output_dir / "dictionary.csv", rows + "\n")]

        assert isinstance(CsvBackend(), Backend)
        dictionary, _ = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X", "uint16")),
            },
        )
        assert dictionary is not None
        files = render(dictionary, [CsvBackend()], tree / "gen")
        assert files[0].content == "X,uint16,A\n"

    def test_two_backends_claiming_one_path_is_refused(self, tree: Path) -> None:
        class Greedy:
            name = "greedy"

            def generate(self, dictionary: DataDictionary, output_dir: Path) -> list[GeneratedFile]:
                return [GeneratedFile(output_dir / "ddd_types.h", "")]

        dictionary, _ = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X")),
            },
        )
        assert dictionary is not None
        with pytest.raises(ValueError, match="would both write"):
            render(dictionary, [CBackend(TEMPLATES), Greedy()], tree / "gen")


def _contents(files: list[GeneratedFile]) -> dict[str, str]:
    return {file.path.name: file.content for file in files}


def _names(files: list[GeneratedFile]) -> set[str]:
    return {file.path.name for file in files}


def test_the_demo_dictionary_round_trips(tmp_path: Path) -> None:
    """The dictionary of the real example survives a write and a read."""
    from ddd.analysis import analyze
    from ddd.diagnostics import DiagnosticBag
    from ddd.loading import load_workspace

    bag = DiagnosticBag()
    workspace = load_workspace(DEMO, bag)
    assert workspace is not None
    dictionary = analyze(workspace, bag)
    target = tmp_path / "dump.json"
    target.write_text(dictionary.model_dump_json(indent=2), encoding="utf-8")
    assert DataDictionary.model_validate_json(target.read_text(encoding="utf-8")) == dictionary


class TestTemplateErrorReporting:
    """What jinja says, turned into the one line a template author can act on."""

    def test_an_error_without_a_traceback_still_names_the_template(self) -> None:
        """No frame to read a line off; the message goes out without one rather than not at
        all. The lined variants are covered end to end through the cli."""
        from jinja2 import TemplateError

        from ddd.backends.base import describe_template_error

        described = describe_template_error("x.c.jinja2", TemplateError("boom"))
        assert described == "cannot render template 'x.c.jinja2': boom"

    def test_a_per_component_render_names_its_component(self) -> None:
        """One template, many renders: without the component the author cannot tell which
        of them tripped over data only that component has."""
        from jinja2 import TemplateError

        from ddd.backends.base import describe_template_error

        described = describe_template_error(
            "{component}.h.jinja2", TemplateError("boom"), component="Beta"
        )
        assert described == (
            "cannot render template '{component}.h.jinja2' for component 'Beta': boom"
        )


class TestObjectViewComposition:
    """``.definition`` is documented template api, kept whole for templates that want the
    one-liner; the shipped example composes from the parts instead, to put a section
    attribute between the declarator and the initialiser."""

    def view(self, **overrides: object) -> object:
        from ddd.backends.c.model import ObjectView
        from ddd.models import ObjectKind

        parts: dict[str, object] = {
            "name": "Gain",
            "kind": ObjectKind.PARAMETER,
            "c_type": "uint16_t",
            "datatype": "uint16",
            "array_suffix": "[4]",
            "constant": True,
            "volatile": False,
            "initializer": "{ 1U, 2U, 3U, 4U }",
            "comment": None,
            "condition": None,
            "owner": "A",
            "consumers": (),
        }
        parts.update(overrides)
        return ObjectView(**parts)  # type: ignore[arg-type]

    def test_the_one_liner_carries_the_initializer(self) -> None:
        assert self.view().definition == "const uint16_t Gain[4] = { 1U, 2U, 3U, 4U }"

    def test_the_one_liner_without_an_initializer_stops_at_the_declarator(self) -> None:
        assert self.view(initializer=None).definition == "const uint16_t Gain[4]"
