"""What a component may add to its interface, and what each change of one takes."""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import component, declare, project, write_tree
from ddd.declaration_plans import KINDS, SCOPES, Declarable, declarable, form_for, scopes_for
from ddd.diagnostics import DiagnosticBag
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
