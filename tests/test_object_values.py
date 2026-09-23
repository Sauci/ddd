"""One object's values, as the grid shows them."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import component, declare, project, write_tree
from ddd.diagnostics import DiagnosticBag
from ddd.editing import edit_text
from ddd.gui.session import Session
from ddd.loading import load_workspace
from ddd.lsp.navigation import Index, index
from ddd.object_values import AXIS_REFERENCES, ValuePlan, ValueRefusalError, grid_of, set_cell

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

    def test_a_shapeless_object_has_an_empty_shape_and_no_rows(self, demo) -> None:
        # ValueA is a plain scalar measurement: shape () is normal for most of a project -
        # sensor_hub states its init as 0 - and a shapeless object has no cell for a value
        # to sit in, so the empty grid is the answer, not a crash and not a refusal.
        dictionary, built = demo
        grid = grid_of(dictionary, built, "ValueA")
        assert grid.shape == ()
        assert grid.rows == ()
        assert grid.stated == "scalar"

    def test_a_shapeless_object_with_no_init_says_none_too(self, demo) -> None:
        # The same shapeless case, the other way its producer can leave init: ValueC states
        # none at all, so it draws the same "none" a shaped object with no init draws -
        # shape alone does not collapse that distinction, only rows.
        dictionary, built = demo
        grid = grid_of(dictionary, built, "ValueC")
        assert (grid.shape, grid.rows, grid.stated) == ((), (), "none")

    def test_an_axis_with_no_init_gives_no_breakpoints(self, tmp_path) -> None:
        # An axis's own producer may state no init at all, legal like any other object's -
        # and the curve over it still reads: the grid degrades to indices, not a crash.
        from conftest import component, declare, project, write_tree

        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    declare("local", "AxisX", kind="axis", size=3),
                    declare("local", "CurveX", kind="curve", axis="AxisX", init=[1, 2, 3]),
                ),
            },
        )
        session = Session(tmp_path)
        session.open(tmp_path / "p.ddd.json")
        revision = session.revision
        assert revision is not None and revision.dictionary is not None
        built = index(load_workspace(tmp_path / "p.ddd.json", DiagnosticBag()))
        try:
            grid = grid_of(revision.dictionary, built, "CurveX")
        finally:
            session.stop()
        assert [(a.position, a.name) for a in grid.axes] == [("axis", "AxisX")]
        assert grid.axes[0].breakpoints == ()

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


class TestChangingOne:
    def test_a_curve_cell_is_one_operation_at_its_index(self, demo) -> None:
        dictionary, built = demo
        plan = set_cell(dictionary, built, "CurveA", "[2]", 750, {})
        (edit,) = plan.edits
        (operation,) = edit.operations
        assert operation.op == "set"
        assert operation.pointer.endswith(".definition.init[2]")
        assert operation.raw == "750"
        after = edit_text(edit.path.read_text(encoding="utf-8"), edit.operations)
        written = _definition_of(after, "CurveA")["init"]
        assert written == [1200, 900, 750, 750, 700, 650]

    def test_a_map_cell_names_its_row_and_its_column(self, demo) -> None:
        dictionary, built = demo
        plan = set_cell(dictionary, built, "MapA", "[1][3]", 99, {})
        (edit,) = plan.edits
        assert edit.operations[0].pointer.endswith(".definition.init[1][3]")
        after = edit_text(edit.path.read_text(encoding="utf-8"), edit.operations)
        rows = _definition_of(after, "MapA")["init"]
        assert rows[1] == [18, 22, 26, 99, 30, 28]
        assert rows[0] == [20, 24, 28, 30, 32, 30]

    def test_a_scalar_init_is_written_out_whole_on_the_first_change(self, demo) -> None:
        # CurveB states `init: 200`, which stands for every element. Changing one means the
        # object gains an explicit array, and the preview has to show that rather than let a
        # reader discover it later.
        dictionary, built = demo
        plan = set_cell(dictionary, built, "CurveB", "[4]", 111, {})
        (operation,) = plan.edits[0].operations
        assert operation.pointer.endswith(".definition.init")
        assert json.loads(operation.raw or "") == [200, 200, 200, 200, 111, 200]

    def test_a_two_dimensional_cell_is_written_into_the_whole_array(self, tmp_path) -> None:
        # The whole-array branch's two dimensional arm needs an object that is both two
        # dimensional and not yet a written array - nothing in examples/demo is both: MapA is
        # two dimensional but its init is already an array, and CurveB's init is a scalar but
        # it is one dimensional. Plane, the same fixture
        # test_a_two_dimensional_object_with_no_init_is_a_grid_of_zeros already builds, is both.
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
            plan = set_cell(revision.dictionary, built, "Plane", "[1][2]", 7, {})
        finally:
            session.stop()
        (operation,) = plan.edits[0].operations
        assert operation.pointer.endswith(".definition.init")
        assert json.loads(operation.raw or "") == [[0, 0, 0], [0, 0, 7]]

    def test_the_change_goes_to_the_producer_s_own_file(self, demo) -> None:
        # BlockA is produced by UserInterface, and that is where its values live, whichever
        # component's page the reader came from.
        dictionary, built = demo
        plan = set_cell(dictionary, built, "BlockA", "[0]", 5, {})
        assert plan.edits[0].path.name == "user_interface.ddd.json"

    @pytest.mark.parametrize(
        ("name", "at", "raw", "says"),
        [
            (
                "SoftwareLabel",
                "[0]",
                1,
                "'SoftwareLabel' is initialised with text, not with a grid",
            ),
            ("CurveA", "[9]", 1, "'[9]' is past the end of this object"),
            ("CurveA", "[1][2]", 1, "'[1][2]' is not an element of this object"),
            ("CurveA", "two", 1, "'two' is not an element of this object"),
            (
                "CurveA",
                "[2]",
                70000,
                "70000 does not fit into uint16 (0 .. 65535)",
            ),
            (
                "CurveA",
                "[2]",
                7.5,
                "7.5 is written as a fractional number, but 'CurveA' has the integer "
                "datatype uint16",
            ),
        ],
    )
    def test_what_is_refused_and_in_which_words(self, demo, name, at, raw, says) -> None:
        dictionary, built = demo
        with pytest.raises(ValueRefusalError) as refused:
            set_cell(dictionary, built, name, at, raw, {})
        assert (refused.value.code, refused.value.message) == ("invalid", says)

    def test_a_name_the_project_has_not_is_not_found(self, demo) -> None:
        dictionary, built = demo
        with pytest.raises(ValueRefusalError) as refused:
            set_cell(dictionary, built, "Nope", "[0]", 1, {})
        assert refused.value.code == "not-found"

    def test_a_value_outside_the_limits_is_stored_rather_than_refused(self, tmp_path) -> None:
        # The rule the global constraints name, and the one place this module is deliberately
        # more permissive than a reader might expect: the analysis weighs an init against the
        # datatype and never against the object's limits (`limits-out-of-range` weighs the
        # limits against the storage instead), so a grid stricter than `ddd check` would leave
        # cells a person wrote by hand that it could not edit. Its own project, because every
        # shaped object of examples/demo has limits as wide as its datatype.
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    declare(
                        "output",
                        "Narrow",
                        kind="value_block",
                        datatype="uint8",
                        dimensions=[2],
                        limits={"min": 0, "max": 10},
                        init=[1, 2],
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
            grid = grid_of(revision.dictionary, built, "Narrow")
            # Far outside the declared range, and stored all the same.
            plan = set_cell(revision.dictionary, built, "Narrow", "[0]", 200, {})
            # Outside the datatype, and refused.
            with pytest.raises(ValueRefusalError) as refused:
                set_cell(revision.dictionary, built, "Narrow", "[0]", 300, {})
        finally:
            session.stop()
        assert (grid.minimum, grid.maximum) == (0, 10)
        assert plan.edits[0].operations[0].raw == "200"
        assert refused.value.message == "300 does not fit into uint8 (0 .. 255)"

    def test_a_value_nothing_produces_cannot_be_set(self, tmp_path) -> None:
        # A name only read, so the dictionary has no producer to write into.
        from conftest import component, declare, project, write_tree

        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A", declare("input", "Orphan", kind="value_block", dimensions=[2])
                ),
            },
        )
        session = Session(tmp_path)
        session.open(tmp_path / "p.ddd.json")
        revision = session.revision
        assert revision is not None and revision.dictionary is not None
        built = index(load_workspace(tmp_path / "p.ddd.json", DiagnosticBag()))
        try:
            with pytest.raises(ValueRefusalError) as refused:
                set_cell(revision.dictionary, built, "Orphan", "[0]", 1, {})
        finally:
            session.stop()
        assert refused.value.message == "nothing produces 'Orphan', so it has no values to set"

    def test_a_shapeless_object_has_no_cell_to_change(self, demo) -> None:
        # ValueA is a plain scalar measurement with no dimensions at all - legal and common,
        # the same object TestWhatTheGridShows reads against. Unlike a curve, a map or a
        # value block it has no cell for a value to sit in, so set_cell refuses it outright,
        # checked before `at` is ever weighed against the empty shape.
        dictionary, built = demo
        with pytest.raises(ValueRefusalError) as refused:
            set_cell(dictionary, built, "ValueA", "", 1, {})
        assert (refused.value.code, refused.value.message) == (
            "invalid",
            "'ValueA' has no cell for a value to sit in",
        )

    def test_a_boolean_cell_takes_0_or_1_and_nothing_else(self, tmp_path) -> None:
        # analysis._check_init's own boolean arm, mirrored: a bool or a literal 0/1 passes,
        # anything else is refused in the same words - a datatype none of this module's other
        # tests reach.
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    declare(
                        "output",
                        "FlagsA",
                        kind="value_block",
                        datatype="boolean",
                        dimensions=[2],
                        init=[False, True],
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
            plan = set_cell(revision.dictionary, built, "FlagsA", "[0]", 1, {})
            with pytest.raises(ValueRefusalError) as refused:
                set_cell(revision.dictionary, built, "FlagsA", "[0]", 2, {})
        finally:
            session.stop()
        assert isinstance(plan, ValuePlan)
        assert plan.edits[0].operations[0].raw == "1"
        assert refused.value.message == "2 is not a valid bool"

    def test_a_float_past_its_precision_rounds_to_zero_and_is_refused(self, tmp_path) -> None:
        # Inside float32's magnitude and past its precision: the storage would hold zero, not
        # the value written, and analysis._check_init refuses it in the same words.
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    declare(
                        "output",
                        "Tiny",
                        kind="value_block",
                        datatype="float32",
                        dimensions=[2],
                        init=[0.1, 0.2],
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
            with pytest.raises(ValueRefusalError) as refused:
                set_cell(revision.dictionary, built, "Tiny", "[0]", 1e-50, {})
        finally:
            session.stop()
        assert refused.value.message == "1e-50 rounds to zero in float32"


def _definition_of(text: str, name: str) -> dict[str, object]:
    """One declaration's definition out of a component's json text."""
    interface = json.loads(text)["component"]["interface"]
    return next(e["definition"] for e in interface if e["definition"]["name"] == name)
