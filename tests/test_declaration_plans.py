"""What a component may add to its interface, and what each change of one takes."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from conftest import component, declare, project, write_tree
from ddd.declaration_plans import (
    KINDS,
    SCOPES,
    Declarable,
    DeclarationRefusalError,
    declarable,
    declare_object,
    form_for,
    read_object,
    remove_declaration,
    scopes_for,
)
from ddd.diagnostics import DiagnosticBag
from ddd.editing import Operation, edit_text
from ddd.identity import OBJECT_ID_LENGTH
from ddd.loading import load_workspace
from ddd.lsp.navigation import Index, index
from ddd.lsp.ranges import Document

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
CONTROLLER = EXAMPLES / "demo" / "components" / "controller.ddd.json"


@pytest.fixture
def demo() -> Index:
    workspace = load_workspace(EXAMPLES / "demo" / "demo.ddd.json", DiagnosticBag())
    assert workspace is not None
    return index(workspace)


@pytest.fixture
def cache() -> dict[Path, Document]:
    return {}


class TestWhatMayBeRead:
    def test_every_name_the_project_has_that_this_file_has_not(
        self, demo: Index, cache: dict[Path, Document]
    ) -> None:
        # Measured against examples/demo as it stands: Controller declares 14 of the project's
        # 23 names, so these 9 are what it could read, each with the component producing it.
        assert declarable(demo, CONTROLLER, cache) == (
            Declarable("BlockA", "value_block", "UserInterface"),
            Declarable("CurveB", "curve", "UserInterface"),
            Declarable("Diagnosis", "measurement", "SensorHub"),
            Declarable("FlagA", "measurement", "SensorHub"),
            Declarable("ValueC", "measurement", "SensorHub"),
            Declarable("ValueD", "measurement", "SensorHub"),
            Declarable("ValueI", "measurement", "UserInterface"),
            Declarable("ValueJ", "measurement", "EventLogger"),
            Declarable("ValueK", "measurement", "EventLogger"),
        )

    def test_a_name_nothing_produces_names_no_producer(
        self, tmp_path: Path, cache: dict[Path, Document]
    ) -> None:
        # Its own project, because every name of examples/demo is produced by something.
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("input", "Orphan")),
                "b.ddd.json": component("B"),
            },
        )
        workspace = load_workspace(tmp_path / "p.ddd.json", DiagnosticBag())
        assert workspace is not None
        built = index(workspace)
        assert declarable(built, tmp_path / "b.ddd.json", cache) == (
            Declarable("Orphan", "measurement", None),
        )


class TestWhichScopesANameMayTake:
    def test_a_name_with_a_producer_may_only_be_read(self, demo: Index) -> None:
        assert scopes_for(demo, "ValueC") == ("input",)

    def test_a_name_without_one_may_be_produced_or_read(self, tmp_path: Path) -> None:
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("input", "Orphan")),
            },
        )
        workspace = load_workspace(tmp_path / "p.ddd.json", DiagnosticBag())
        assert workspace is not None
        built = index(workspace)
        assert scopes_for(built, "Orphan") == ("output", "input")

    def test_a_name_the_project_has_never_seen_may_take_all_three(self, demo: Index) -> None:
        assert scopes_for(demo, "Pressure") == SCOPES


class TestWhatAKindAsksFor:
    def test_every_kind_asks_for_what_the_models_require(self, demo: Index) -> None:
        # Read from definition_keys rather than listed here, so a key added to a model shows up
        # as a failure of this test rather than as a form that cannot make a loadable file.
        required = {
            kind: {offer.key for offer in form_for(demo, kind) if offer.carried[0].required}
            for kind in KINDS
        }
        assert required == {
            "measurement": {"volatile"},
            "parameter": {"volatile"},
            "value_block": {"volatile", "dimensions"},
            "curve": {"volatile", "axis"},
            "map": {"volatile", "x_axis", "y_axis"},
            "axis": {"volatile", "size"},
        }

    def test_a_kind_offers_the_editors_the_chooser_already_draws(self, demo: Index) -> None:
        editors = {offer.key: offer.editor for offer in form_for(demo, "axis")}
        assert editors["size"] == "size"
        assert editors["unit"] == "unit"
        assert editors["input"] == "name"

    def test_a_kind_nothing_declares_asks_for_nothing(self, demo: Index) -> None:
        # definition_keys answers two empty sets for a kind it does not know, and the endpoint
        # refuses before reaching here - so this is the branch a broken caller would take.
        assert form_for(demo, "nonsense") == ()


class TestReadingWhatTheProjectHas:
    def test_a_reader_carries_the_producer_s_definition_without_its_id_and_init(
        self, demo, cache, tmp_path
    ) -> None:
        # The rule this whole verb rests on, measured rather than assumed: across every
        # variable more than one component of examples/demo declares, a reader's definition is
        # the producer's less `id` and `init`, with nothing of its own.
        plan = read_object(demo, CONTROLLER, "ValueC", "input", cache)
        (edit,) = plan.edits
        (operation,) = edit.operations
        assert edit.path == CONTROLLER
        assert operation.op == "insert"
        assert operation.pointer == "component.interface[14]"
        written = json.loads(operation.raw or "")
        assert written["scope"] == "input"
        producer = json.loads(
            (EXAMPLES / "demo" / "components" / "sensor_hub.ddd.json").read_text(encoding="utf-8")
        )["component"]["interface"]
        stated = next(
            entry["definition"] for entry in producer if entry["definition"]["name"] == "ValueC"
        )
        assert written["definition"] == {
            key: value for key, value in stated.items() if key not in {"id", "init"}
        }

    def test_the_edit_writes_a_declaration_the_file_can_be_read_back_from(
        self, demo, cache
    ) -> None:
        # The layout is the edit engine's, not this module's: `insertion` lays a value out the
        # way the place it goes is laid out. Asserted by applying it and parsing the result.
        plan = read_object(demo, CONTROLLER, "ValueC", "input", cache)
        after = edit_text(CONTROLLER.read_text(encoding="utf-8"), plan.edits[0].operations)
        interface = json.loads(after)["component"]["interface"]
        assert len(interface) == 15
        assert interface[-1]["definition"]["name"] == "ValueC"
        assert '"name": "ValueC",\n' in after  # a key per line, as the file spells one

    def test_a_name_the_project_does_not_declare_is_not_found(self, demo, cache) -> None:
        with pytest.raises(DeclarationRefusalError) as refused:
            read_object(demo, CONTROLLER, "Nope", "input", cache)
        assert (refused.value.code, refused.value.message) == (
            "not-found",
            "the project declares no 'Nope'",
        )

    def test_a_name_this_component_already_declares_is_refused(self, demo, cache) -> None:
        with pytest.raises(DeclarationRefusalError) as refused:
            read_object(demo, CONTROLLER, "ValueA", "input", cache)
        assert refused.value.code == "invalid"
        assert refused.value.message == "this component already declares 'ValueA'"

    def test_a_scope_the_name_may_not_take_is_refused(self, demo, cache) -> None:
        # ValueC has a producer, so offering `output` here would make a multiple-producers.
        with pytest.raises(DeclarationRefusalError) as refused:
            read_object(demo, CONTROLLER, "ValueC", "output", cache)
        assert refused.value.message == "'ValueC' may not be declared 'output' here"

    def test_a_name_with_no_producer_is_read_from_the_declaration_there_is(
        self, tmp_path, cache
    ) -> None:
        # Nothing produces Orphan, so there is no producer's definition to carry - the one
        # declaration that does exist is what a second component reads it as.
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("input", "Orphan", unit="rpm")),
                "b.ddd.json": component("B"),
            },
        )
        built = index(load_workspace(tmp_path / "p.ddd.json", DiagnosticBag()))
        plan = read_object(built, tmp_path / "b.ddd.json", "Orphan", "input", cache)
        written = json.loads(plan.edits[0].operations[0].raw or "")
        assert written["definition"]["unit"] == "rpm"

    def test_an_owner_the_file_no_longer_declares_since_the_index_was_built_is_not_found(
        self, tmp_path, cache
    ) -> None:
        # The index can be older than the file: built once, read from again on every call.
        # A pointer it recorded that the owner's file no longer holds is exactly what "the
        # project declares no X" already means - there is nothing left there to carry.
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "X")),
                "b.ddd.json": component("B"),
            },
        )
        built = index(load_workspace(tmp_path / "p.ddd.json", DiagnosticBag()))
        write_tree(tmp_path, {"a.ddd.json": component("A")})
        with pytest.raises(DeclarationRefusalError) as refused:
            read_object(built, tmp_path / "b.ddd.json", "X", "input", cache)
        assert (refused.value.code, refused.value.message) == (
            "not-found",
            "the project declares no 'X'",
        )


class TestDeclaringSomethingNew:
    def test_a_producer_is_stamped_with_a_fresh_id_after_its_name(self, demo, cache) -> None:
        plan = declare_object(
            demo,
            CONTROLLER,
            "output",
            {
                "name": "Pressure",
                "kind": "measurement",
                "datatype": "uint16",
                "conversion": {"kind": "identity"},
                "volatile": False,
            },
            cache,
        )
        written = json.loads(plan.edits[0].operations[0].raw or "")
        assert list(written["definition"])[:2] == ["name", "id"]
        assert len(written["definition"]["id"]) == OBJECT_ID_LENGTH

    def test_a_reader_and_a_local_are_not_stamped(self, demo, cache) -> None:
        for scope in ("input", "local"):
            plan = declare_object(
                demo,
                CONTROLLER,
                scope,
                {
                    "name": "Pressure",
                    "kind": "measurement",
                    "datatype": "uint16",
                    "conversion": {"kind": "identity"},
                    "volatile": False,
                },
                cache,
            )
            written = json.loads(plan.edits[0].operations[0].raw or "")
            assert "id" not in written["definition"]

    def test_a_name_the_project_refuses_is_refused_in_the_editor_s_own_words(
        self, demo, cache
    ) -> None:
        for name, why in (
            ("ValueA", "'ValueA' is already declared by this project"),
            ("int", "'int' is reserved by c or by a header DDD generates"),
            ("no spaces", "'no spaces' is not a usable c identifier"),
            (
                "STATE_OFF",
                "'STATE_OFF' is an enumerator of enum 'StateA_t', which shares c's namespace "
                "with the variables",
            ),
        ):
            with pytest.raises(DeclarationRefusalError) as refused:
                declare_object(
                    demo,
                    CONTROLLER,
                    "output",
                    {"name": name, "kind": "measurement", "volatile": False},
                    cache,
                )
            assert (refused.value.code, refused.value.message) == ("invalid", why)

    def test_a_kind_that_is_not_one_of_the_six_is_refused(self, demo, cache) -> None:
        with pytest.raises(DeclarationRefusalError) as refused:
            declare_object(
                demo, CONTROLLER, "output", {"name": "Pressure", "kind": "signal"}, cache
            )
        assert refused.value.message == (
            "'signal' is not a kind: measurement, parameter, value_block, curve, map, axis"
        )

    def test_a_definition_without_a_name_or_a_kind_is_refused(self, demo, cache) -> None:
        for definition in ({"kind": "measurement"}, {"name": "Pressure"}, {"name": 4}):
            with pytest.raises(DeclarationRefusalError) as refused:
                declare_object(demo, CONTROLLER, "output", definition, cache)
            assert refused.value.message == "a definition states a 'name' and a 'kind'"

    def test_a_scope_that_is_not_one_of_the_three_is_refused(self, demo, cache) -> None:
        with pytest.raises(DeclarationRefusalError) as refused:
            declare_object(
                demo,
                CONTROLLER,
                "sideways",
                {"name": "Pressure", "kind": "measurement", "volatile": False},
                cache,
            )
        assert refused.value.message == "'sideways' is not a scope: output, input, local"

    def test_a_required_key_left_out_is_refused_before_a_file_is_written(self, demo, cache) -> None:
        with pytest.raises(DeclarationRefusalError) as refused:
            declare_object(
                demo,
                CONTROLLER,
                "output",
                {"name": "Pressure", "kind": "value_block", "volatile": False},
                cache,
            )
        assert refused.value.message == "a value_block must state 'dimensions'"

    def test_a_key_the_kind_has_not_is_refused(self, demo, cache) -> None:
        with pytest.raises(DeclarationRefusalError) as refused:
            declare_object(
                demo,
                CONTROLLER,
                "output",
                {"name": "Pressure", "kind": "parameter", "volatile": False, "size": 4},
                cache,
            )
        assert refused.value.message == "a parameter has no 'size' to state"

    def test_an_id_sent_by_the_page_is_refused_rather_than_written(self, demo, cache) -> None:
        # The server mints it, so a client that states one is either confused or forging an
        # identity another object already carries.
        with pytest.raises(DeclarationRefusalError) as refused:
            declare_object(
                demo,
                CONTROLLER,
                "output",
                {
                    "name": "Pressure",
                    "kind": "measurement",
                    "volatile": False,
                    "id": "aaaaaaaaaaaa",
                },
                cache,
            )
        assert refused.value.message == "an id is this server's to mint, not the page's"

    def test_a_stated_datatype_with_no_conversion_is_refused_rather_than_planned(
        self, demo, cache
    ) -> None:
        # The one rule none of the checks above can see: `datatype` and `conversion` cross two
        # keys, which `definition_keys`' required set cannot express - only the models catch
        # it, and they have to catch it here, before a plan is made, or `declare_object` would
        # hand back a plan whose own file then fails to load.
        with pytest.raises(DeclarationRefusalError) as refused:
            declare_object(
                demo,
                CONTROLLER,
                "output",
                {
                    "name": "Pressure",
                    "kind": "measurement",
                    "datatype": "uint16",
                    "volatile": False,
                },
                cache,
            )
        assert (refused.value.code, refused.value.message) == (
            "invalid",
            "a 'datatype' comes with a 'conversion': the identity "
            '({"kind": "identity"}) is an answer to state, not a default to fall into',
        )

    def test_a_stated_datatype_with_its_conversion_is_planned(self, demo, cache) -> None:
        # The same definition, complete - the models have nothing left to refuse, so this is
        # the plan the test above's definition was one key away from.
        plan = declare_object(
            demo,
            CONTROLLER,
            "output",
            {
                "name": "Pressure",
                "kind": "measurement",
                "datatype": "uint16",
                "conversion": {"kind": "identity"},
                "volatile": False,
            },
            cache,
        )
        written = json.loads(plan.edits[0].operations[0].raw or "")
        assert written["definition"]["conversion"] == {"kind": "identity"}

    def test_what_is_written_parses_and_loads(self, demo, cache, tmp_path) -> None:
        # The end of the verb's promise: a file the loader reads back without a complaint.
        plan = declare_object(
            demo,
            CONTROLLER,
            "output",
            {
                "name": "Pressure",
                "kind": "axis",
                "description": "Declared from the interface",
                "datatype": "uint16",
                "conversion": {"kind": "identity"},
                "size": 8,
                "volatile": False,
            },
            cache,
        )
        after = edit_text(CONTROLLER.read_text(encoding="utf-8"), plan.edits[0].operations)
        written = tmp_path / "demo"
        shutil.copytree(EXAMPLES / "demo", written)
        (written / "components" / "controller.ddd.json").write_text(after, encoding="utf-8")
        bag = DiagnosticBag()
        load_workspace(written / "demo.ddd.json", bag)
        # A pristine examples/demo loads with nothing reported, so anything here is this
        # declaration's doing. `DiagnosticBag.sorted` is how a bag is read.
        assert [finding.check for finding in bag.sorted] == []


class TestRemovingADeclaration:
    def test_the_declaration_goes_and_the_rest_stay(self, demo, cache) -> None:
        plan = remove_declaration(demo, CONTROLLER, "ValueA", cache)
        (edit,) = plan.edits
        assert edit.operations == (Operation("remove", "component.interface[0]"),)
        after = edit_text(CONTROLLER.read_text(encoding="utf-8"), edit.operations)
        names = [
            entry["definition"]["name"] for entry in json.loads(after)["component"]["interface"]
        ]
        assert len(names) == 13
        assert "ValueA" not in names

    def test_a_name_this_file_does_not_declare_is_not_found(self, demo, cache) -> None:
        with pytest.raises(DeclarationRefusalError) as refused:
            remove_declaration(demo, CONTROLLER, "ValueI", cache)
        assert (refused.value.code, refused.value.message) == (
            "not-found",
            "controller.ddd.json declares no 'ValueI'",
        )

    def test_a_file_with_no_interface_is_not_found(self, tmp_path, cache) -> None:
        # A project file rather than a component: it has no `component.interface` to change,
        # and the endpoint's own guard is a component check, so this is what reaching here
        # with the wrong file answers.
        write_tree(tmp_path, {"p.ddd.json": project("P")})
        built = index(load_workspace(tmp_path / "p.ddd.json", DiagnosticBag()))
        with pytest.raises(DeclarationRefusalError) as refused:
            remove_declaration(built, tmp_path / "p.ddd.json", "ValueA", cache)
        assert refused.value.code == "not-found"
        assert refused.value.message == "p.ddd.json declares no interface"
