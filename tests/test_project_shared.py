"""A project's constants as the Shared files tab shows them."""

from __future__ import annotations

from pathlib import Path

from conftest import built_of, write_tree
from ddd.diagnostics import Diagnostic, Location, Severity
from ddd.lsp.navigation import _DIMENSION_KEY
from ddd.lsp.ranges import Document
from ddd.project_shared import (
    _DECLARATION_SHAPE,
    _MEMBER_SHAPE,
    constant_row,
    constant_string,
    constant_text,
    constant_uses,
    located_on_constant,
    shared_rows,
)

# `p.ddd.json` is deliberately absent from every tree below: `conftest.built_of` writes it
# itself, from the other files it is handed, so a tree naming its own would fight the helper
# over the one file that matters least to the test reading it.
TWO_HOMES = {
    "c.ddd.json": {
        "constants": [
            {"name": "TREND_SAMPLES", "value": 16, "description": "slots of a trend buffer"}
        ]
    },
    "a.ddd.json": {
        "component": {
            "name": "A",
            "constants": [{"name": "CELLS", "value": 2.0}],
            "interface": [
                {
                    "scope": "output",
                    "definition": {
                        "kind": "measurement",
                        "name": "Trend",
                        "datatype": "uint16",
                        "unit": "rpm",
                        "conversion": {"kind": "identity"},
                        "volatile": False,
                        "dimensions": ["TREND_SAMPLES"],
                    },
                }
            ],
        }
    },
}

# The second of the three places a shape is written: a curve's shared axis states its length as
# `size` rather than as a `dimensions` entry. No file under examples/ happens to declare one
# whose size names a constant, so this is written by hand rather than copied - see the
# implementation report for the measurement that shows examples/vocabulary/pump.ddd.json holds
# neither this nor `_WITH_A_STRUCTURE` below.
_WITH_AN_AXIS = {
    "c.ddd.json": {
        "constants": [
            {"name": "TREND_SAMPLES", "value": 16, "description": "slots of a trend buffer"}
        ]
    },
    "a.ddd.json": {
        "component": {
            "name": "A",
            "interface": [
                {
                    "scope": "output",
                    "definition": {
                        "kind": "axis",
                        "name": "TrendAxis",
                        "datatype": "uint16",
                        "unit": "rpm",
                        "conversion": {"kind": "identity"},
                        "volatile": False,
                        "size": "TREND_SAMPLES",
                    },
                }
            ],
        }
    },
}

# The third place: a structure member's `dimensions`. A member carries no component of its own,
# so this structure is declared in a types file no component owns - the shape
# `test_a_structure_members_dimension_is_a_use_naming_its_structure` is written to see.
_WITH_A_STRUCTURE = {
    "c.ddd.json": {
        "constants": [
            {"name": "TREND_SAMPLES", "value": 16, "description": "slots of a trend buffer"}
        ]
    },
    "t.ddd.json": {
        "types": [
            {
                "type": "struct",
                "name": "Sample_t",
                "members": [
                    {
                        "name": "history",
                        "member": "value",
                        "datatype": "uint16",
                        "conversion": {"kind": "identity"},
                        "dimensions": ["TREND_SAMPLES"],
                    }
                ],
            }
        ]
    },
}

# Two components declaring the same variable name - one producing it, one reading it - each
# restating `dimensions`. `declarations_of` returns one `Declared` per component under the one
# name "Trend", and `constant_uses` has to tell them apart by site rather than take whichever it
# finds first, or a use in "B" would be reported as one in "A".
_TWO_DECLARATIONS = {
    "c.ddd.json": {
        "constants": [
            {"name": "TREND_SAMPLES", "value": 16, "description": "slots of a trend buffer"}
        ]
    },
    "a.ddd.json": {
        "component": {
            "name": "A",
            "interface": [
                {
                    "scope": "output",
                    "definition": {
                        "kind": "measurement",
                        "name": "Trend",
                        "datatype": "uint16",
                        "unit": "rpm",
                        "conversion": {"kind": "identity"},
                        "volatile": False,
                        "dimensions": ["TREND_SAMPLES"],
                    },
                }
            ],
        }
    },
    "b.ddd.json": {
        "component": {
            "name": "B",
            "interface": [
                {
                    "scope": "input",
                    "definition": {
                        "kind": "measurement",
                        "name": "Trend",
                        "datatype": "uint16",
                        "unit": "rpm",
                        "conversion": {"kind": "identity"},
                        "volatile": False,
                        "dimensions": ["TREND_SAMPLES"],
                    },
                }
            ],
        }
    },
}


class TestTheRows:
    def test_every_constant_of_both_homes_is_a_row(self, tmp_path: Path) -> None:
        """A reader looking for CELLS does not know whether a constants file or a component's own
        list declares it, so one table holds both."""
        built, _ = built_of(tmp_path, **TWO_HOMES)
        cache: dict[Path, Document] = {}
        rows = shared_rows(built, (), cache)
        assert [(row.kind, row.name, row.value) for row in rows] == [
            ("constant", "CELLS", "2.0"),
            ("constant", "TREND_SAMPLES", "16"),
        ]

    def test_a_fractional_value_keeps_the_spelling_its_author_wrote(self, tmp_path: Path) -> None:
        """`2.0` is a fractional constant and `2` a whole one - `ConstantValue` refuses a whole
        number in its fractional arm - so a row showing `2` would name a different constant, and
        an edit built from that row would retype it."""
        built, _ = built_of(tmp_path, **TWO_HOMES)
        cache: dict[Path, Document] = {}
        assert constant_row(built, "CELLS", (), cache).value == "2.0"

    def test_a_row_counts_the_shapes_that_name_it(self, tmp_path: Path) -> None:
        built, _ = built_of(tmp_path, **TWO_HOMES)
        cache: dict[Path, Document] = {}
        assert {row.name: row.uses for row in shared_rows(built, (), cache)} == {
            "CELLS": 0,
            "TREND_SAMPLES": 1,
        }

    def test_a_row_counts_a_finding_filed_at_a_shape_that_names_it(self, tmp_path: Path) -> None:
        """`dimension-value` is filed at the shape, never at the entry, and is about nothing but
        the constant's value: a table counting only the entry's own findings would show nothing
        for the one finding a reader of this tab came to act on."""
        built, _ = built_of(tmp_path, **TWO_HOMES)
        cache: dict[Path, Document] = {}
        at_the_shape = Diagnostic(
            check="dimension-value",
            severity=Severity.ERROR,
            message="whose value is no array length",
            location=Location(
                tmp_path / "a.ddd.json", "component.interface[0].definition.dimensions[0]"
            ),
        )
        rows = {
            row.name: row.findings
            for row in shared_rows(built, [(tmp_path / "a.ddd.json", at_the_shape)], cache)
        }
        assert rows == {"CELLS": 0, "TREND_SAMPLES": 1}

    def test_a_row_counts_a_finding_filed_inside_its_own_entry(self, tmp_path: Path) -> None:
        built, _ = built_of(tmp_path, **TWO_HOMES)
        cache: dict[Path, Document] = {}
        at_the_entry = Diagnostic(
            check="duplicate-constant",
            severity=Severity.ERROR,
            message="declared more than once",
            location=Location(tmp_path / "c.ddd.json", "constants[0].name"),
        )
        rows = {
            row.name: row.findings
            for row in shared_rows(built, [(tmp_path / "c.ddd.json", at_the_entry)], cache)
        }
        assert rows["TREND_SAMPLES"] == 1

    def test_findings_are_read_once_however_many_rows_there_are(self, tmp_path: Path) -> None:
        """The api hands this a generator. Walked once per row, every row after the first would
        count nothing."""
        built, _ = built_of(tmp_path, **TWO_HOMES)
        cache: dict[Path, Document] = {}
        at_the_entry = Diagnostic(
            check="duplicate-constant",
            severity=Severity.ERROR,
            message="declared more than once",
            location=Location(tmp_path / "c.ddd.json", "constants[0].name"),
        )
        given = iter([(tmp_path / "c.ddd.json", at_the_entry)])
        rows = {row.name: row.findings for row in shared_rows(built, given, cache)}
        assert rows["TREND_SAMPLES"] == 1

    def test_a_finding_with_no_place_belongs_to_no_constant(self, tmp_path: Path) -> None:
        built, _ = built_of(tmp_path, **TWO_HOMES)
        about_the_project = Diagnostic(
            check="no-components", severity=Severity.ERROR, message="none", location=None
        )
        assert not located_on_constant(
            built, "TREND_SAMPLES", tmp_path / "p.ddd.json", about_the_project
        )

    def test_a_finding_in_another_file_belongs_to_no_constant(self, tmp_path: Path) -> None:
        """The pointer can match while the file does not: two components number their
        declarations from zero."""
        built, _ = built_of(tmp_path, **TWO_HOMES)
        elsewhere = Diagnostic(
            check="dimension-value",
            severity=Severity.ERROR,
            message="whose value is no array length",
            location=Location(
                tmp_path / "c.ddd.json", "component.interface[0].definition.dimensions[0]"
            ),
        )
        assert not located_on_constant(built, "TREND_SAMPLES", tmp_path / "c.ddd.json", elsewhere)

    def test_a_finding_about_a_name_with_no_entry_and_no_use_belongs_to_no_constant(
        self, tmp_path: Path
    ) -> None:
        """Most findings a run reports are not about any given constant at all - an
        `unknown-type` here, a `duplicate-component` there. A name neither declared nor named by
        any shape leaves nothing in `places` to walk, which is the loop's other arm: every other
        test in this class hands it at least one place to check."""
        built, _ = built_of(tmp_path, **TWO_HOMES)
        unrelated = Diagnostic(
            check="unknown-type",
            severity=Severity.ERROR,
            message="names no type any file declares",
            location=Location(
                tmp_path / "a.ddd.json", "component.interface[0].definition.typename"
            ),
        )
        assert not located_on_constant(built, "SPARE_CELLS", tmp_path / "a.ddd.json", unrelated)

    def test_a_finding_on_a_name_nothing_declares_still_belongs_to_it(self, tmp_path: Path) -> None:
        """`unknown-constant` is filed at a shape naming a constant that does not exist. The
        question is still whether the finding is about that name, and the answer is still yes -
        it is what sends the reader to the pre-filled add form."""
        files = {
            **TWO_HOMES,
            "a.ddd.json": {
                "component": {
                    "name": "A",
                    "interface": [
                        {
                            "scope": "output",
                            "definition": {
                                "kind": "measurement",
                                "name": "Trend",
                                "datatype": "uint16",
                                "unit": "rpm",
                                "conversion": {"kind": "identity"},
                                "volatile": False,
                                "dimensions": ["MISSING_CELLS"],
                            },
                        }
                    ],
                }
            },
        }
        built, _ = built_of(tmp_path, **files)
        undeclared = Diagnostic(
            check="unknown-constant",
            severity=Severity.ERROR,
            message="which is not a constant any file of this project declares",
            location=Location(
                tmp_path / "a.ddd.json", "component.interface[0].definition.dimensions[0]"
            ),
        )
        assert located_on_constant(built, "MISSING_CELLS", tmp_path / "a.ddd.json", undeclared)


class TestOneConstantsPanel:
    def test_its_value_and_description_are_read_from_its_entry(self, tmp_path: Path) -> None:
        built, _ = built_of(tmp_path, **TWO_HOMES)
        cache: dict[Path, Document] = {}
        assert constant_text(built, "TREND_SAMPLES", "value", cache) == "16"
        assert (
            constant_string(built, "TREND_SAMPLES", "description", cache)
            == "slots of a trend buffer"
        )

    def test_a_key_the_entry_has_not_reads_empty(self, tmp_path: Path) -> None:
        built, _ = built_of(tmp_path, **TWO_HOMES)
        cache: dict[Path, Document] = {}
        assert constant_string(built, "CELLS", "description", cache) == ""

    def test_a_key_the_entry_has_not_reads_empty_as_text_too(self, tmp_path: Path) -> None:
        """The same absent `description` `constant_string` reads above, read through
        `constant_text` instead: the two call different `Document` methods - `value_at` against
        `raw_at` - so each needs its own case to reach its own `None`."""
        built, _ = built_of(tmp_path, **TWO_HOMES)
        cache: dict[Path, Document] = {}
        assert constant_text(built, "CELLS", "description", cache) == ""

    def test_a_key_holding_something_other_than_a_string_reads_empty_as_a_string(
        self, tmp_path: Path
    ) -> None:
        """A file that changed since the analysis can have anything at that key; the panel draws
        prose there, and a number would arrive as one."""
        built, _ = built_of(tmp_path, **TWO_HOMES)
        cache: dict[Path, Document] = {}
        assert constant_string(built, "TREND_SAMPLES", "value", cache) == ""

    def test_a_name_the_index_does_not_hold_reads_empty(self, tmp_path: Path) -> None:
        """The api looks a name up before it asks, so this arm is only reachable from a test -
        which is where `ddd.project_types` covers its own."""
        built, _ = built_of(tmp_path, **TWO_HOMES)
        cache: dict[Path, Document] = {}
        assert constant_text(built, "NOTHING", "value", cache) == ""
        assert constant_string(built, "NOTHING", "description", cache) == ""
        assert constant_uses(built, "NOTHING", cache) == ()

    def test_a_use_names_the_variable_and_the_component_it_is_in(self, tmp_path: Path) -> None:
        built, _ = built_of(tmp_path, **TWO_HOMES)
        cache: dict[Path, Document] = {}
        used = constant_uses(built, "TREND_SAMPLES", cache)
        assert [(use.kind, use.name, use.component) for use in used] == [("variable", "Trend", "A")]
        assert used[0].site.pointer == "component.interface[0].definition.dimensions[0]"

    def test_an_axis_size_is_a_use_like_a_dimension(self, tmp_path: Path) -> None:
        """A curve's axis states its length as `size`, which is the second of the three places a
        shape is written."""
        built, _ = built_of(tmp_path, **_WITH_AN_AXIS)
        cache: dict[Path, Document] = {}
        used = constant_uses(built, "TREND_SAMPLES", cache)
        assert [(use.kind, use.name) for use in used] == [("variable", "TrendAxis")]
        assert used[0].site.pointer.endswith(".size")

    def test_a_structure_members_dimension_is_a_use_naming_its_structure(
        self, tmp_path: Path
    ) -> None:
        """The third place. A member carries no component: its structure may be declared in a
        types file no component owns, so the structure's name is what locates it."""
        built, _ = built_of(tmp_path, **_WITH_A_STRUCTURE)
        cache: dict[Path, Document] = {}
        used = constant_uses(built, "TREND_SAMPLES", cache)
        assert [(use.kind, use.name, use.component) for use in used] == [
            ("member", "Sample_t.history", None)
        ]

    def test_a_member_whose_own_name_has_drifted_is_not_a_use(self, tmp_path: Path) -> None:
        """A different drift than the declaration's below: `_MEMBER_SHAPE` still matches the
        pointer - the structure and the member are both still there - but the member's own `name`
        is gone, so there is nothing left to call the member `history` of `Sample_t`."""
        built, _ = built_of(tmp_path, **_WITH_A_STRUCTURE)
        write_tree(
            tmp_path,
            {
                "t.ddd.json": {
                    "types": [
                        {
                            "type": "struct",
                            "name": "Sample_t",
                            "members": [
                                {
                                    "member": "value",
                                    "datatype": "uint16",
                                    "conversion": {"kind": "identity"},
                                    "dimensions": ["TREND_SAMPLES"],
                                }
                            ],
                        }
                    ]
                }
            },
        )
        cache: dict[Path, Document] = {}
        assert constant_uses(built, "TREND_SAMPLES", cache) == ()

    def test_two_declarations_of_one_variable_keep_their_own_components(
        self, tmp_path: Path
    ) -> None:
        """Two components may each declare a variable of the same name - one producing it, one
        reading it - and both may restate its `dimensions`. Keyed by name alone,
        `declarations_of` returns both, and the first found would swallow the second: this pins
        the site filter that tells them apart, the one `ddd.project_types.uses_of` needed the
        identical test for - `test_project_types.py`'s own
        `test_a_declaration_naming_a_type_comes_with_its_component_and_role`."""
        built, _ = built_of(tmp_path, **_TWO_DECLARATIONS)
        cache: dict[Path, Document] = {}
        used = constant_uses(built, "TREND_SAMPLES", cache)
        assert [(use.kind, use.name, use.component) for use in used] == [
            ("variable", "Trend", "A"),
            ("variable", "Trend", "B"),
        ]

    def test_a_use_whose_declaration_has_moved_is_left_out(self, tmp_path: Path) -> None:
        """The index recorded where the analysis read it; the file has changed since. The next
        revision lists it where it went, and a panel naming a declaration that is not there is
        worse than one row short."""
        built, _ = built_of(tmp_path, **TWO_HOMES)
        (tmp_path / "a.ddd.json").write_text(
            '{"component": {"name": "A", "interface": []}}', encoding="utf-8"
        )
        cache: dict[Path, Document] = {}
        assert constant_uses(built, "TREND_SAMPLES", cache) == ()

    def test_a_declaration_renamed_since_is_not_a_use(self, tmp_path: Path) -> None:
        """A different drift than the declaration losing its name above: the name at the
        recorded site now belongs to nobody the index ever declared, rather than to nobody at
        all, so `declarations_of` is asked about a name it never indexed and `next` falls
        through to `None` instead of finding a site to compare."""
        built, _ = built_of(tmp_path, **TWO_HOMES)
        write_tree(
            tmp_path,
            {
                "a.ddd.json": {
                    "component": {
                        "name": "A",
                        "interface": [
                            {
                                "scope": "output",
                                "definition": {
                                    "kind": "measurement",
                                    "name": "Renamed",
                                    "datatype": "uint16",
                                    "unit": "rpm",
                                    "conversion": {"kind": "identity"},
                                    "volatile": False,
                                    "dimensions": ["TREND_SAMPLES"],
                                },
                            }
                        ],
                    }
                }
            },
        )
        cache: dict[Path, Document] = {}
        assert constant_uses(built, "TREND_SAMPLES", cache) == ()


def test_the_two_shape_patterns_match_what_the_index_calls_a_shape() -> None:
    """One authority, two readings of it: `_DIMENSION_KEY` decides where a constant may be named,
    and a pointer this module fails to recognise is a use the panel silently drops."""
    pointers = [
        "component.interface[0].definition.dimensions[0]",
        "component.interface[3].definition.size",
        "types[0].members[1].dimensions[0]",
        "component.types[2].members[0].dimensions[4]",
        "component.interface[0].definition.unit",
        "constants[0].value",
        "component.interface[0].definition.dimensions[0].extra",
    ]
    for pointer in pointers:
        mine = _DECLARATION_SHAPE.match(pointer) or _MEMBER_SHAPE.match(pointer)
        assert bool(mine) == bool(_DIMENSION_KEY.match(pointer)), pointer
