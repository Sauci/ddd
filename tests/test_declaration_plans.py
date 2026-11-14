"""What a component may add to its interface, and what each change of one takes."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from conftest import (
    LOCAL_BESIDE_OUTPUT,
    STRING_TYPE_BESIDE_SCALAR,
    built_of,
    component,
    declare,
    project,
    write_tree,
)
from ddd.analysis import PRODUCER_KEYS, analyze
from ddd.declaration_plans import (
    CARRIED_BY_A_READER,
    KINDS,
    PRODUCING_SCOPES,
    SCOPES,
    Declarable,
    DeclarationPlan,
    DeclarationRefusalError,
    declarable,
    declare_object,
    describe_declaration,
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
from ddd.models.component import Scope

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
CONTROLLER = EXAMPLES / "demo" / "components" / "controller.ddd.json"

TAG_PLUGIN = '''
"""The smallest plugin that gives a definition an ``extensions`` block to state."""

from pydantic import BaseModel, ConfigDict

from ddd.plugins import Plugin


class Tag(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    tag: str


PLUGIN = Plugin(name="tag", object_model=Tag)
'''


@pytest.fixture
def demo() -> Index:
    workspace = load_workspace(EXAMPLES / "demo" / "demo.ddd.json", DiagnosticBag())
    assert workspace is not None
    return index(workspace)


@pytest.fixture
def copied_demo(tmp_path: Path) -> tuple[Index, Path]:
    """A writable copy of examples/demo and its index, for a test that applies what it plans.

    The example itself is never written to, so a plan made against ``CONTROLLER`` cannot be
    applied where it points; a plan made against the copy can.
    """
    root = tmp_path / "demo"
    shutil.copytree(EXAMPLES / "demo", root)
    workspace = load_workspace(root / "demo.ddd.json", DiagnosticBag())
    assert workspace is not None
    return index(workspace), root


@pytest.fixture
def cache() -> dict[Path, Document]:
    return {}


def checks_after(base: Path, plan: DeclarationPlan, root: str = "p.ddd.json") -> list[str]:
    """Every check the project reports once that plan has been written into it.

    The whole of what these verbs promise, in one helper: ``ddd gui`` writes the files a person
    writes by hand, so whether it kept the promise is whatever ``ddd check`` says about what it
    wrote - not whether the loader could parse it back. ``DiagnosticBag.sorted`` is how a bag is
    read, and the bag carries the loader's findings and the analysis' alike.
    """
    (edit,) = plan.edits
    edit.path.write_text(
        edit_text(edit.path.read_text(encoding="utf-8"), edit.operations),
        encoding="utf-8",
        newline="",
    )
    bag = DiagnosticBag()
    workspace = load_workspace(base / root, bag)
    if workspace is not None:
        analyze(workspace, bag)
    return [finding.check for finding in bag.sorted]


class TestWhatMayBeRead:
    def test_every_name_the_project_shares_that_this_file_has_not(
        self, demo: Index, cache: dict[Path, Document]
    ) -> None:
        # Measured against examples/demo as it stands: Controller declares 14 of the project's
        # 23 names, and of the 9 it does not, five are another component's locals - BlockA,
        # CurveB, Diagnosis, ValueD and ValueK - which no other component may declare. These 4
        # are what it could read, each with the component producing it.
        assert declarable(demo, CONTROLLER, cache) == (
            Declarable("FlagA", "measurement", "SensorHub"),
            Declarable("ValueC", "measurement", "SensorHub"),
            Declarable("ValueI", "measurement", "UserInterface"),
            Declarable("ValueJ", "measurement", "EventLogger"),
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

    def test_a_name_another_component_keeps_local_is_not_offered(
        self, tmp_path: Path, cache: dict[Path, Document]
    ) -> None:
        # Review finding: `Loc` is W's `local`, which keeps it from every other component, and
        # it was offered to R with the one scope `input` - which is `local-conflict` exactly, a
        # local beside another declaration. What W *outputs* is still R's to read.
        built, root = built_of(tmp_path, **LOCAL_BESIDE_OUTPUT)
        assert declarable(built, root / "r.ddd.json", cache) == (
            Declarable("Out", "measurement", "W"),
        )

    def test_a_local_another_component_already_reads_is_not_offered_either(
        self, tmp_path: Path, cache: dict[Path, Document]
    ) -> None:
        # A project already holding a reader beside the local reports `local-conflict`, and the
        # analysis files it again for each further declaration beside the local: a third
        # component reading the name is one more error, so the name is not offered to it either.
        built, root = built_of(
            tmp_path,
            **{
                "w.ddd.json": component("W", declare("local", "Loc", id="aaaaaaaaaaaa")),
                "x.ddd.json": component("X", declare("input", "Loc")),
                "r.ddd.json": component("R"),
            },
        )
        assert declarable(built, root / "r.ddd.json", cache) == ()


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

    def test_a_name_another_component_keeps_local_may_take_none(self, tmp_path: Path) -> None:
        # A local is its component's alone, so any other declaration of it - a reader's no less
        # than a second producer's - is a `local-conflict`, and no scope is the answer. A name
        # beside it that is only written is still read.
        built, _ = built_of(tmp_path, **LOCAL_BESIDE_OUTPUT)
        assert scopes_for(built, "Loc") == ()
        assert scopes_for(built, "Out") == ("input",)


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


class TestWhatOnlyAProducerMayState:
    """The two sets this module derives rather than restates, pinned where they are derived."""

    def test_a_reader_drops_exactly_the_keys_the_analysis_reserves(self) -> None:
        # Not a list written out here: the set is read from `PRODUCER_KEYS`, the analysis' own
        # public name for it, so a sixth key added there fails nothing and is dropped at once,
        # and a copy written beside it fails this.
        reserved = {key for key, _, _ in PRODUCER_KEYS}
        assert reserved == CARRIED_BY_A_READER
        assert sorted(reserved) == ["extensions", "id", "init", "raster", "section"]

    def test_a_local_is_a_producer_as_much_as_an_output_is(self) -> None:
        producing = {scope.value for scope in Scope if scope.is_producer}
        assert producing == PRODUCING_SCOPES
        assert sorted(producing) == ["local", "output"]


class TestReadingWhatTheProjectHas:
    def test_a_reader_carries_the_producer_s_definition_without_its_id_and_init(
        self, demo, cache, tmp_path
    ) -> None:
        # What the rule comes to on examples/demo, where `id` and `init` are the only two of
        # the five its producers state: a reader's definition is ValueC's less those two, with
        # nothing of its own. The test below is the one that says where the five come from.
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

    def test_a_reader_carries_none_of_the_five_keys_only_a_producer_may_state(
        self, tmp_path, cache
    ) -> None:
        # Review finding: the rule above was measured across the examples, where every producer
        # stating a `section`, a `raster` or an `extensions` block is `local` - and a local is
        # never declarable elsewhere, so the measurement could not see them. A producer stating
        # all five, which the examples have nowhere, is what says whether the set is right.
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project(
                    "P",
                    "rasters.ddd.json",
                    "sections.ddd.json",
                    "a.ddd.json",
                    "b.ddd.json",
                    plugins=["tag_plugin.py"],
                ),
                "rasters.ddd.json": {"rasters": [{"raster": "10ms", "event": 1, "cycle": "10ms"}]},
                "sections.ddd.json": {
                    "sections": [{"section": ".fast_ram", "access": "read-write", "alignment": 4}]
                },
                "tag_plugin.py": TAG_PLUGIN,
                "a.ddd.json": component(
                    "A",
                    declare(
                        "output",
                        "Sig",
                        id="aaaaaaaaaaaa",
                        init=0,
                        section=".fast_ram",
                        raster="10ms",
                        extensions={"tag": {"tag": "t"}},
                    ),
                ),
                "b.ddd.json": component("B"),
            },
        )
        built = index(load_workspace(tmp_path / "p.ddd.json", DiagnosticBag()))
        producer = json.loads((tmp_path / "a.ddd.json").read_text(encoding="utf-8"))
        stated = producer["component"]["interface"][0]["definition"]
        # The fixture states all five, so this cannot pass on a producer that states fewer.
        assert set(stated) >= CARRIED_BY_A_READER
        plan = read_object(built, tmp_path / "b.ddd.json", "Sig", "input", cache)
        written = json.loads(plan.edits[0].operations[0].raw or "")
        assert set(written["definition"]) & CARRIED_BY_A_READER == set()
        assert written["definition"] == {
            key: value for key, value in stated.items() if key not in CARRIED_BY_A_READER
        }
        # And the point of dropping them: each one carried would be a finding of its own -
        # `consumer-storage`, `consumer-raster`, `consumer-identity`, `consumer-extension` -
        # on the file `ddd gui` has just written.
        assert checks_after(tmp_path, plan) == []

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

    def test_a_local_this_component_keeps_is_one_it_already_declares(self, demo, cache) -> None:
        # A local of this file's own is not another component's: it is refused as a name the
        # file already declares, not as one kept by the component that asks.
        with pytest.raises(DeclarationRefusalError) as refused:
            read_object(demo, CONTROLLER, "ParameterA", "input", cache)
        assert refused.value.message == "this component already declares 'ParameterA'"

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

    def test_reading_a_name_nothing_produces_as_its_producer_repairs_it_outright(
        self, tmp_path, cache
    ) -> None:
        # Review finding: `scopes_for` offers `output` first for a name nothing produces, and
        # the page defaults to the first - so this is the repair of a `missing-producer`, and
        # an unstamped one would trade that error for a `missing-id` instead of ending it.
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("input", "Orphan", unit="rpm")),
                "b.ddd.json": component("B"),
            },
        )
        built = index(load_workspace(tmp_path / "p.ddd.json", DiagnosticBag()))
        assert scopes_for(built, "Orphan")[0] == "output"
        plan = read_object(built, tmp_path / "b.ddd.json", "Orphan", "output", cache)
        written = json.loads(plan.edits[0].operations[0].raw or "")
        assert list(written["definition"])[:2] == ["name", "id"]
        assert len(written["definition"]["id"]) == OBJECT_ID_LENGTH
        assert checks_after(tmp_path, plan) == []

    def test_reading_an_object_a_condition_wraps_carries_the_condition(
        self, tmp_path: Path, cache: dict[Path, Document]
    ) -> None:
        # The reader "agrees with its producer by construction", and the condition is the one
        # part of the producer's entry that is no part of its definition: a plan copying the
        # definition alone left `condition-mismatch` on both files.
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "w.ddd.json", "r.ddd.json"),
                "w.ddd.json": component(
                    "W", declare("output", "Cond", id="aaaaaaaaaaaa", condition="defined(FEATURE)")
                ),
                "r.ddd.json": component("R"),
            },
        )
        built = index(load_workspace(tmp_path / "p.ddd.json", DiagnosticBag()))
        plan = read_object(built, tmp_path / "r.ddd.json", "Cond", "input", cache)
        written = json.loads(plan.edits[0].operations[0].raw or "")
        assert written["condition"] == "defined(FEATURE)"
        assert list(written) == ["scope", "condition", "definition"]
        assert checks_after(tmp_path, plan) == []

    @pytest.mark.parametrize("scope", SCOPES)
    def test_a_name_another_component_keeps_local_is_refused_in_every_scope(
        self, tmp_path: Path, cache: dict[Path, Document], scope: str
    ) -> None:
        # Review finding: reading it was planned as an `input`, written, and reported by
        # `ddd check` as `'Loc' is local to component 'W' but is also declared as input by
        # component 'R'`, in a project that reported nothing. The refusal says why, in the
        # sentence the check uses for what it is.
        built, root = built_of(tmp_path, **LOCAL_BESIDE_OUTPUT)
        with pytest.raises(DeclarationRefusalError) as refused:
            read_object(built, root / "r.ddd.json", "Loc", scope, cache)
        assert (refused.value.code, refused.value.message) == (
            "invalid",
            "'Loc' is local to component 'W', so no other component may declare it",
        )

    def test_the_component_named_is_the_first_to_keep_the_name_local(
        self, tmp_path: Path, cache: dict[Path, Document]
    ) -> None:
        # Two components keeping one name local is a `local-conflict` of its own, and the check
        # names the first the project lists, as the refusal does: `v` is listed before `w`.
        built, root = built_of(
            tmp_path,
            **{
                "v.ddd.json": component("V", declare("local", "Loc", id="aaaaaaaaaaaa")),
                "w.ddd.json": component("W", declare("local", "Loc", id="bbbbbbbbbbbb")),
                "r.ddd.json": component("R"),
            },
        )
        with pytest.raises(DeclarationRefusalError) as refused:
            read_object(built, root / "r.ddd.json", "Loc", "input", cache)
        assert refused.value.message == (
            "'Loc' is local to component 'V', so no other component may declare it"
        )

    def test_nothing_the_form_offers_is_a_finding_once_it_is_written(
        self, copied_demo: tuple[Index, Path], cache: dict[Path, Document]
    ) -> None:
        # The harm itself, over a project that reports nothing: each name Controller is offered,
        # read in each scope it is offered, is written and the project asked what it says. Five
        # of the nine names it was offered were another component's locals and said
        # `local-conflict`, so nothing the form offers may make the project say anything.
        built, root = copied_demo
        controller = root / "components" / "controller.ddd.json"
        original = controller.read_text(encoding="utf-8")
        offered = [
            (entry.name, scope)
            for entry in declarable(built, controller, cache)
            for scope in scopes_for(built, entry.name)
        ]
        assert ("ValueC", "input") in offered
        brings: dict[tuple[str, str], list[str]] = {}
        for name, scope in offered:
            plan = read_object(built, controller, name, scope, cache)
            found = checks_after(root, plan, "demo.ddd.json")
            if found:
                brings[name, scope] = found
            controller.write_text(original, encoding="utf-8", newline="")
        assert brings == {}

    def test_an_owner_the_file_no_longer_declares_since_the_index_was_built_is_stale(
        self, tmp_path, cache
    ) -> None:
        """The index can be older than the file: built once, read from again on every call. A
        place it recorded that the owner's file no longer holds an object at is the owner's file
        changed since the analysis, as a place holding another object is, below: the index still
        names the producer, and a reader who took the name from it is told to wait for the
        analysis, never that the project declares no such name."""
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
            "stale",
            "a.ddd.json changed since the project was analysed, so 'X' cannot be declared here "
            "until the project is analysed again",
        )

    def test_an_owner_whose_place_holds_another_declaration_since_the_index_was_built_is_stale(
        self, tmp_path, cache
    ) -> None:
        """A declaration put in above the owner after the index was built: read at the pointer
        the index recorded, the reader would carry that one's definition - its name too - into a
        file no fingerprint of the owner's guards, being the only file written."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "X", unit="rpm")),
                "b.ddd.json": component("B"),
            },
        )
        built = index(load_workspace(tmp_path / "p.ddd.json", DiagnosticBag()))
        above = declare("output", "Y", unit="Nm")
        write_tree(tmp_path, {"a.ddd.json": component("A", above, declare("output", "X"))})
        with pytest.raises(DeclarationRefusalError) as refused:
            read_object(built, tmp_path / "b.ddd.json", "X", "input", cache)
        assert (refused.value.code, refused.value.message) == (
            "stale",
            "a.ddd.json changed since the project was analysed, so 'X' cannot be declared here "
            "until the project is analysed again",
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

    def test_a_local_is_stamped_too_and_only_a_reader_is_not(self, demo, cache) -> None:
        # Review finding: this used to pin `local` as unstamped, which `Scope.is_producer` and
        # `identity._PRODUCING` both contradict - a local owns its object exclusively, and
        # `scopes_for` offers it for every brand new name, so an unstamped one would be a
        # `missing-id` the moment it was written.
        stamped = {}
        for scope in SCOPES:
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
            stamped[scope] = "id" in written["definition"]
        assert stamped == {"output": True, "input": False, "local": True}

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

    def test_limits_that_are_not_finite_are_refused_rather_than_planned(self, demo, cache) -> None:
        # The models take a float64 under a factor of two; the analysis files it as `schema` from
        # the definition alone, so it is refused here, in the analysis's sentence, before a plan
        # is made - not left for the file it is written into to be counted as one that did not
        # load.
        with pytest.raises(DeclarationRefusalError) as refused:
            declare_object(
                demo,
                CONTROLLER,
                "output",
                {
                    "name": "Pressure",
                    "kind": "measurement",
                    "datatype": "float64",
                    "conversion": {"kind": "linear", "factor": 2},
                    "volatile": False,
                },
                cache,
            )
        assert (refused.value.code, refused.value.message) == (
            "invalid",
            "the limits derived from 'float64' and this conversion are not finite",
        )

    def test_a_string_type_without_its_one_dimension_is_refused_rather_than_planned(
        self, tmp_path, cache
    ) -> None:
        # The type is the project's, so the models take the definition and the analysis refuses
        # the file it is written into (`schema`). The plan knows the project, and says so first.
        built, root = built_of(tmp_path, **STRING_TYPE_BESIDE_SCALAR)
        stated = {"name": "Label", "kind": "measurement", "typename": "Text_t", "volatile": False}
        with pytest.raises(DeclarationRefusalError) as refused:
            declare_object(built, root / "w.ddd.json", "local", stated, cache)
        assert (refused.value.code, refused.value.message) == (
            "invalid",
            "'Label' is declared as 'Text_t', which is a string: a string states exactly one "
            "dimension, its length in bytes, got none; an array of strings is written as an "
            "array of structures with a string member",
        )

    def test_a_string_type_with_its_one_dimension_is_planned(self, tmp_path, cache) -> None:
        built, root = built_of(tmp_path, **STRING_TYPE_BESIDE_SCALAR)
        stated = {
            "name": "Label",
            "kind": "measurement",
            "typename": "Text_t",
            "dimensions": [8],
            "volatile": False,
        }
        plan = declare_object(built, root / "w.ddd.json", "local", stated, cache)
        assert json.loads(plan.edits[0].operations[0].raw or "")["definition"]["dimensions"] == [8]

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

    @pytest.mark.parametrize(
        ("scope", "reported"),
        [("local", []), ("output", ["unused-output"]), ("input", ["missing-producer"])],
    )
    def test_what_is_written_says_nothing_about_itself_to_the_checks(
        self, copied_demo, cache, scope, reported
    ) -> None:
        # Review finding: this used to load the result and stop there, which is what let three
        # bugs through - a file can parse perfectly and still be a finding. A pristine
        # examples/demo analyses with nothing reported, so whatever is reported here is this
        # declaration's doing, and each of the three answers below is a statement about how
        # complete the *project* now is, never about the shape of what was written: an object
        # only this component may touch completes it, a producer nobody reads yet is the
        # consumer spec 2 says to add with the second verb, and a reader with no producer is
        # the same sentence the other way round. Nothing here is a `missing-id`, a `schema` or
        # a `consumer-*`, which are the ways a written file is wrong in itself.
        built, root = copied_demo
        plan = declare_object(
            built,
            root / "components" / "controller.ddd.json",
            scope,
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
        assert checks_after(root, plan, "demo.ddd.json") == reported


class TestDescribingADeclaration:
    """A declaration's description is its own: two components may describe one variable in
    their own words, so it is set at one declaration, in its file, and never carried."""

    def test_a_description_is_one_set_at_the_declarations_own_key(self, demo, cache) -> None:
        plan = describe_declaration(demo, CONTROLLER, "ParameterA", "A calibratable gain", cache)
        (edit,) = plan.edits
        assert edit.path == CONTROLLER
        (operation,) = edit.operations
        assert operation.op == "set"
        assert operation.pointer.endswith(".definition.description")
        assert operation.raw == '"A calibratable gain"'
        text = CONTROLLER.read_text(encoding="utf-8")
        after = edit_text(text, edit.operations)

        def definition(of: str) -> dict[str, object]:
            interface = json.loads(of)["component"]["interface"]
            return next(
                e["definition"] for e in interface if e["definition"]["name"] == "ParameterA"
            )

        assert definition(after)["description"] == "A calibratable gain"
        rest = {k: v for k, v in definition(after).items() if k != "description"}
        assert rest == {k: v for k, v in definition(text).items() if k != "description"}

    def test_a_declaration_stating_none_gains_one(self, tmp_path, cache) -> None:
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
            },
        )
        built = index(load_workspace(tmp_path / "p.ddd.json", DiagnosticBag()))
        plan = describe_declaration(built, tmp_path / "a.ddd.json", "Speed", "Shaft speed", cache)
        (edit,) = plan.edits
        after = edit_text((tmp_path / "a.ddd.json").read_text(encoding="utf-8"), edit.operations)
        stated = json.loads(after)["component"]["interface"][0]["definition"]
        assert stated["description"] == "Shaft speed"

    def test_the_empty_text_takes_the_key_away(self, demo, cache) -> None:
        # The model's default is the empty text, so a description of none is no key at all.
        plan = describe_declaration(demo, CONTROLLER, "ParameterA", "", cache)
        (edit,) = plan.edits
        (operation,) = edit.operations
        assert operation.op == "remove"
        assert operation.pointer.endswith(".definition.description")
        assert operation.raw is None
        after = edit_text(CONTROLLER.read_text(encoding="utf-8"), edit.operations)
        interface = json.loads(after)["component"]["interface"]
        stated = next(e["definition"] for e in interface if e["definition"]["name"] == "ParameterA")
        assert "description" not in stated

    def test_the_empty_text_where_none_is_stated_has_nothing_to_remove(
        self, tmp_path, cache
    ) -> None:
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed")),
            },
        )
        built = index(load_workspace(tmp_path / "p.ddd.json", DiagnosticBag()))
        with pytest.raises(DeclarationRefusalError) as refused:
            describe_declaration(built, tmp_path / "a.ddd.json", "Speed", "", cache)
        assert (refused.value.code, refused.value.message) == (
            "invalid",
            "a.ddd.json states no description of 'Speed', so there is none to remove",
        )

    def test_a_name_this_file_does_not_declare_is_not_found(self, demo, cache) -> None:
        with pytest.raises(DeclarationRefusalError) as refused:
            describe_declaration(demo, CONTROLLER, "ValueI", "x", cache)
        assert (refused.value.code, refused.value.message) == (
            "not-found",
            "controller.ddd.json declares no 'ValueI'",
        )

    def test_a_name_another_component_declares_is_not_this_files(self, demo, cache) -> None:
        # ValueA is the sensor hub's, which the controller reads: each describes it in its own
        # words, so the declaration is the one in the file asked.
        hub = EXAMPLES / "demo" / "components" / "sensor_hub.ddd.json"
        plan = describe_declaration(demo, hub, "ValueA", "Hub words", cache)
        assert plan.edits[0].path == hub

    def test_a_declaration_put_in_above_it_since_the_analysis_is_stale(
        self, tmp_path, cache
    ) -> None:
        one = declare("output", "One", description="one")
        other = declare("output", "Other")
        write_tree(
            tmp_path,
            {"p.ddd.json": project("P", "a.ddd.json"), "a.ddd.json": component("A", one)},
        )
        built = index(load_workspace(tmp_path / "p.ddd.json", DiagnosticBag()))
        write_tree(tmp_path, {"a.ddd.json": component("A", other, one)})
        with pytest.raises(DeclarationRefusalError) as refused:
            describe_declaration(built, tmp_path / "a.ddd.json", "One", "new", cache)
        assert (refused.value.code, refused.value.message) == (
            "stale",
            "a.ddd.json changed since the project was analysed, so the description of 'One' "
            "cannot be set until the project is analysed again",
        )


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
