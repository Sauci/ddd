"""One object's values, as the grid shows them."""

from __future__ import annotations

from pathlib import Path

import pytest

from ddd.diagnostics import DiagnosticBag
from ddd.gui.session import Session
from ddd.loading import load_workspace
from ddd.lsp.navigation import Index, index
from ddd.object_values import AXIS_REFERENCES, grid_of

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


@pytest.fixture
def demo() -> tuple[object, Index]:
    """The demo's resolved dictionary and its index: what a grid is read from."""
    session = Session(EXAMPLES / "demo")
    session.open(EXAMPLES / "demo" / "demo.ddd.json")
    revision = session.revision
    assert revision is not None and revision.dictionary is not None
    built = index(load_workspace(EXAMPLES / "demo" / "demo.ddd.json", DiagnosticBag()))
    try:
        yield revision.dictionary, built
    finally:
        session.stop()


class TestWhatTheGridShows:
    def test_a_curve_is_one_row_against_one_axis(self, demo) -> None:
        dictionary, built = demo
        grid = grid_of(dictionary, built, "CurveA")
        assert (grid.kind, grid.datatype, grid.unit) == ("curve", "uint16", "ms")
        assert grid.shape == (6,)
        assert grid.stated == "array"
        assert grid.rows == ((1200, 900, 800, 750, 700, 650),)
        assert [(a.position, a.name, a.unit) for a in grid.axes] == [("axis", "AxisA", "Hz")]
        assert grid.axes[0].breakpoints == (0, 3200, 6400, 12800, 19200, 32000)
        assert grid.owner == "Controller"
        assert grid.file is not None and grid.file.endswith("controller.ddd.json")

    def test_a_map_is_rows_of_its_y_axis_and_columns_of_its_x(self, demo) -> None:
        # The order the file already uses: MapA's shape is (4, 6), which is AxisB by AxisA.
        dictionary, built = demo
        grid = grid_of(dictionary, built, "MapA")
        assert grid.shape == (4, 6)
        assert len(grid.rows) == 4 and all(len(row) == 6 for row in grid.rows)
        assert grid.rows[1] == (18, 22, 26, 28, 30, 28)
        assert [(a.position, a.name) for a in grid.axes] == [
            ("x_axis", "AxisA"),
            ("y_axis", "AxisB"),
        ]

    def test_an_axis_lays_against_no_axis_of_its_own(self, demo) -> None:
        # AxisA's references are {"input": "ValueE"} - a reference that is not an axis. A grid
        # laid against every reference would draw ValueE as AxisA's own breakpoints.
        dictionary, built = demo
        grid = grid_of(dictionary, built, "AxisA")
        assert grid.axes == ()
        assert grid.rows == ((0, 3200, 6400, 12800, 19200, 32000),)

    def test_a_value_block_has_a_shape_and_no_axes(self, demo) -> None:
        dictionary, built = demo
        grid = grid_of(dictionary, built, "BlockA")
        assert (grid.kind, grid.shape, grid.axes) == ("value_block", (8,), ())
        assert grid.rows == ((0, 12, 28, 52, 84, 124, 180, 255),)
        assert grid.file is not None and grid.file.endswith("user_interface.ddd.json")

    def test_a_scalar_init_is_that_value_in_every_element(self, demo) -> None:
        dictionary, built = demo
        grid = grid_of(dictionary, built, "CurveB")
        assert grid.stated == "scalar"
        assert grid.rows == ((200, 200, 200, 200, 200, 200),)

    def test_a_text_init_is_no_grid_at_all(self, demo) -> None:
        dictionary, built = demo
        grid = grid_of(dictionary, built, "SoftwareLabel")
        assert (grid.stated, grid.rows) == ("text", ())

    def test_an_absent_init_is_zeros_and_says_so(self, tmp_path) -> None:
        # Every shaped object of examples/demo states an init, so this writes its own project:
        # a value block whose producer states none, which the startup code zeroes.
        from conftest import component, declare, project, write_tree

        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    declare(
                        "output", "Spare", kind="value_block", datatype="uint8", dimensions=[4]
                    ),
                ),
            },
        )
        session = Session(tmp_path)
        session.open(tmp_path / "p.ddd.json")
        revision = session.revision
        assert revision is not None and revision.dictionary is not None
        built = index(load_workspace(tmp_path / "p.ddd.json", DiagnosticBag()))
        grid = grid_of(revision.dictionary, built, "Spare")
        session.stop()
        assert (grid.stated, grid.rows) == ("none", ((0, 0, 0, 0),))

    def test_a_two_dimensional_object_with_no_init_is_a_grid_of_zeros(self, tmp_path) -> None:
        # The other arm of the same filling: a shape with two dimensions, which nothing in
        # examples/demo pairs with a scalar or an absent init.
        from conftest import component, declare, project, write_tree

        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    declare(
                        "output", "Plane", kind="value_block", datatype="uint8", dimensions=[2, 3]
                    ),
                ),
            },
        )
        session = Session(tmp_path)
        session.open(tmp_path / "p.ddd.json")
        revision = session.revision
        assert revision is not None and revision.dictionary is not None
        built = index(load_workspace(tmp_path / "p.ddd.json", DiagnosticBag()))
        try:
            grid = grid_of(revision.dictionary, built, "Plane")
        finally:
            session.stop()
        assert (grid.stated, grid.shape) == ("none", (2, 3))
        assert grid.rows == ((0, 0, 0), (0, 0, 0))

    def test_the_resolved_limits_travel_with_it(self, demo) -> None:
        dictionary, built = demo
        grid = grid_of(dictionary, built, "CurveA")
        assert (grid.minimum, grid.maximum) == (0.0, 655.35)

    def test_a_name_the_project_has_not_is_not_found(self, demo) -> None:
        from ddd.object_values import ValueRefusalError

        dictionary, built = demo
        with pytest.raises(ValueRefusalError) as refused:
            grid_of(dictionary, built, "Nope")
        assert (refused.value.code, refused.value.message) == (
            "not-found",
            "the project declares no 'Nope'",
        )

    def test_only_the_three_axis_references_are_axes(self) -> None:
        assert AXIS_REFERENCES == ("axis", "x_axis", "y_axis")
