"""What every key of a variable offers the panel of ``ddd gui``, and the kinds the index records."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from conftest import component, declare, project, scalar_type, types, write_tree
from ddd.diagnostics import DiagnosticBag
from ddd.loading import load_workspace
from ddd.lsp.edits import PROPAGATED_KEYS
from ddd.lsp.navigation import Index, index
from ddd.variable_keys import DATATYPES, EDITORS, KEY_ORDER, Carried, InPlay, offers
from ddd.variables import declarations_of


def built(tmp_path: Path, **files: Any) -> Index:
    """The index of a project of these files, named by a project description of the same name."""
    write_tree(tmp_path, {"p.ddd.json": project("P", *files), **files})
    workspace = load_workspace(tmp_path / "p.ddd.json", DiagnosticBag())
    assert workspace is not None
    return index(workspace)


def offered(idx: Index, name: str, key: str) -> Any:
    """The one offer for ``key`` among those made for ``name``'s declarations."""
    return next(offer for offer in offers(idx, declarations_of(idx, name, {})) if offer.key == key)


def edited(path: Path, change: Any) -> None:
    """Change the first declaration's definition in place, as a save from an editor would."""
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data["component"]["interface"][0]["definition"])
    path.write_text(json.dumps(data, indent=2), encoding="utf-8", newline="")


def one_of_each(tmp_path: Path) -> Index:
    """A component declaring one object of every kind.

    The axis-shaped ones refer to `Points`.
    """
    return built(
        tmp_path,
        **{
            "a.ddd.json": component(
                "A",
                declare("output", "Speed", unit="rpm"),
                declare("output", "Points", kind="axis", size=4),
                declare("output", "Torque", kind="curve", axis="Points"),
                declare("output", "Grid", kind="map", x_axis="Points", y_axis="Points"),
                declare("output", "Block", kind="value_block", dimensions=[3, 4]),
                declare("output", "Gain", kind="parameter"),
            )
        },
    )


class TestKinds:
    def test_every_object_is_recorded_with_the_kind_it_states(self, tmp_path: Path) -> None:
        assert one_of_each(tmp_path).kinds == {
            "Speed": "measurement",
            "Points": "axis",
            "Torque": "curve",
            "Grid": "map",
            "Block": "value_block",
            "Gain": "parameter",
        }

    def test_a_name_two_components_declare_keeps_the_kind_of_the_first(
        self, tmp_path: Path
    ) -> None:
        # Declarations that disagree about their kind are two objects under one name, which
        # `definition-mismatch` reports and no chooser settles: the index records one kind, and
        # the first component the project lists is the one it reads it from.
        idx = built(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", kind="parameter")),
            },
        )
        assert idx.kinds == {"Speed": "measurement"}


class TestTheKeysOffered:
    def test_every_propagated_key_is_offered_once_in_the_models_own_order(
        self, tmp_path: Path
    ) -> None:
        made = offers(one_of_each(tmp_path), declarations_of(one_of_each(tmp_path), "Speed", {}))
        assert [offer.key for offer in made] == list(KEY_ORDER)
        assert set(KEY_ORDER) == PROPAGATED_KEYS
        assert set(EDITORS) == PROPAGATED_KEYS

    def test_the_eleven_datatypes_are_what_a_datatype_may_be(self, tmp_path: Path) -> None:
        assert offered(one_of_each(tmp_path), "Speed", "datatype").choices == (
            "boolean",
            "uint8",
            "sint8",
            "uint16",
            "sint16",
            "uint32",
            "sint32",
            "uint64",
            "sint64",
            "float32",
            "float64",
        )
        assert offered(one_of_each(tmp_path), "Speed", "datatype").choices == DATATYPES


class TestWhatAKindCarries:
    def test_a_measurement_may_hold_dimensions_and_must_hold_its_volatile(
        self, tmp_path: Path
    ) -> None:
        idx = one_of_each(tmp_path)
        assert offered(idx, "Speed", "dimensions").carried == (
            Carried(allowed=True, required=False),
        )
        assert offered(idx, "Speed", "volatile").carried == (Carried(allowed=True, required=True),)
        assert offered(idx, "Speed", "size").carried == (Carried(allowed=False, required=False),)

    def test_a_value_block_must_hold_the_dimensions_a_measurement_may_leave_out(
        self, tmp_path: Path
    ) -> None:
        idx = one_of_each(tmp_path)
        assert offered(idx, "Block", "dimensions").carried == (
            Carried(allowed=True, required=True),
        )

    def test_an_axis_holds_a_size_it_must_state_and_an_input_it_need_not(
        self, tmp_path: Path
    ) -> None:
        idx = one_of_each(tmp_path)
        assert offered(idx, "Points", "size").carried == (Carried(allowed=True, required=True),)
        assert offered(idx, "Points", "input").carried == (Carried(allowed=True, required=False),)

    def test_a_curve_holds_its_axis_and_a_map_both_of_its_own(self, tmp_path: Path) -> None:
        idx = one_of_each(tmp_path)
        assert offered(idx, "Torque", "axis").carried == (Carried(allowed=True, required=True),)
        assert offered(idx, "Grid", "x_axis").carried == (Carried(allowed=True, required=True),)
        assert offered(idx, "Grid", "y_axis").carried == (Carried(allowed=True, required=True),)
        assert offered(idx, "Grid", "axis").carried == (Carried(allowed=False, required=False),)

    def test_a_parameter_holds_none_of_the_shaped_keys(self, tmp_path: Path) -> None:
        idx = one_of_each(tmp_path)
        for key in ("dimensions", "size", "input", "axis", "x_axis", "y_axis"):
            assert offered(idx, "Gain", key).carried == (Carried(allowed=False, required=False),)

    def test_the_storage_a_declaration_uses_is_one_it_may_not_be_left_without(
        self, tmp_path: Path
    ) -> None:
        # `definition_keys` derives what a kind requires from the models' fields, where every
        # one of these three is optional: a definition states either a datatype with its
        # conversion or the name of a type that fixes both. Offering to strip the one the
        # declaration actually uses would write a file the loader refuses.
        idx = built(
            tmp_path,
            **{
                "types.ddd.json": types(scalar_type("Speed_t", unit="rpm")),
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", typename="Speed_t")),
            },
        )
        assert offered(idx, "Speed", "datatype").carried == (
            Carried(allowed=True, required=True),
            Carried(allowed=True, required=False),
        )
        assert offered(idx, "Speed", "conversion").carried == (
            Carried(allowed=True, required=True),
            Carried(allowed=True, required=False),
        )
        assert offered(idx, "Speed", "typename").carried == (
            Carried(allowed=True, required=False),
            Carried(allowed=True, required=True),
        )

    def test_a_declaration_whose_file_lost_its_datatype_requires_neither_storage_key(
        self, tmp_path: Path
    ) -> None:
        # The same drift as the kind below, for the storage a declaration uses: edited down to
        # neither a `datatype` nor a `typename`, there is nothing left for either to require.
        idx = built(
            tmp_path, **{"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))}
        )
        edited(tmp_path / "a.ddd.json", lambda definition: definition.pop("datatype"))
        assert offered(idx, "Speed", "datatype").carried == (Carried(allowed=True, required=False),)
        assert offered(idx, "Speed", "typename").carried == (Carried(allowed=True, required=False),)

    def test_a_declaration_whose_file_lost_its_kind_carries_nothing(self, tmp_path: Path) -> None:
        # The index was built from a file that loaded; what a declaration states is read again
        # from the file as it stands now, which may have moved on. A kind this reader does not
        # know means "offer nothing" rather than an error of its own.
        idx = built(
            tmp_path, **{"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))}
        )
        edited(tmp_path / "a.ddd.json", lambda definition: definition.pop("kind"))
        assert offered(idx, "Speed", "unit").carried == (Carried(allowed=False, required=False),)

    def test_a_kind_written_as_a_number_carries_nothing_either(self, tmp_path: Path) -> None:
        idx = built(
            tmp_path, **{"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))}
        )
        edited(tmp_path / "a.ddd.json", lambda definition: definition.__setitem__("kind", 3))
        assert offered(idx, "Speed", "unit").carried == (Carried(allowed=False, required=False),)


class TestWhatIsInPlay:
    def test_each_value_is_listed_once_with_the_components_stating_it(self, tmp_path: Path) -> None:
        idx = built(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="%")),
                "c.ddd.json": component("C", declare("input", "Speed", unit="%")),
            },
        )
        assert offered(idx, "Speed", "unit").values == (
            InPlay(raw='"rpm"', components=("A",), producer=True),
            InPlay(raw='"%"', components=("B", "C"), producer=False),
        )

    def test_the_producers_value_comes_first_however_the_project_lists_it(
        self, tmp_path: Path
    ) -> None:
        idx = built(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("input", "Speed", unit="%")),
                "b.ddd.json": component("B", declare("output", "Speed", unit="rpm")),
            },
        )
        assert offered(idx, "Speed", "unit").values == (
            InPlay(raw='"rpm"', components=("B",), producer=True),
            InPlay(raw='"%"', components=("A",), producer=False),
        )

    def test_a_value_a_named_type_fixes_is_in_play_like_any_other(self, tmp_path: Path) -> None:
        idx = built(
            tmp_path,
            **{
                "types.ddd.json": types(scalar_type("Speed_t", unit="rpm")),
                "a.ddd.json": component("A", declare("output", "Speed", typename="Speed_t")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="%")),
            },
        )
        assert offered(idx, "Speed", "unit").values == (
            InPlay(raw='"rpm"', components=("A",), producer=True),
            InPlay(raw='"%"', components=("B",), producer=False),
        )

    def test_one_value_written_two_ways_is_one_value_in_play(self, tmp_path: Path) -> None:
        # A conversion is an object, and an object's keys may be written in any order: the two
        # declarations below mean the same linear conversion, which `definition-mismatch` does
        # not report and the panel does not offer to settle. The spelling carried is the
        # producer's, so that applying it leaves the producer's own file alone.
        idx = built(
            tmp_path,
            **{
                "a.ddd.json": component(
                    "A",
                    declare(
                        "output",
                        "Speed",
                        conversion={"kind": "linear", "factor": 2, "offset": 0},
                    ),
                ),
                "b.ddd.json": component(
                    "B",
                    declare(
                        "input",
                        "Speed",
                        conversion={"offset": 0, "factor": 2, "kind": "linear"},
                    ),
                ),
            },
        )
        values = offered(idx, "Speed", "conversion").values
        assert [(value.components, value.producer) for value in values] == [(("A", "B"), True)]
        assert json.loads(values[0].raw) == {"kind": "linear", "factor": 2, "offset": 0}
        assert list(json.loads(values[0].raw)) == ["kind", "factor", "offset"]

    def test_a_key_nobody_states_has_nothing_in_play(self, tmp_path: Path) -> None:
        idx = built(tmp_path, **{"a.ddd.json": component("A", declare("output", "Speed"))})
        assert offered(idx, "Speed", "unit").values == ()


class TestWhatDisagrees:
    def test_two_values_in_play_disagree(self, tmp_path: Path) -> None:
        idx = built(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="%")),
            },
        )
        assert offered(idx, "Speed", "unit").disagrees is True

    def test_one_value_beside_a_declaration_stating_none_disagrees(self, tmp_path: Path) -> None:
        idx = built(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed")),
            },
        )
        assert offered(idx, "Speed", "unit").disagrees is True

    def test_limits_left_out_defer_rather_than_disagree(self, tmp_path: Path) -> None:
        idx = built(
            tmp_path,
            **{
                "a.ddd.json": component(
                    "A", declare("output", "Speed", limits={"min": 0, "max": 100})
                ),
                "b.ddd.json": component("B", declare("input", "Speed")),
            },
        )
        assert offered(idx, "Speed", "limits").disagrees is False

    def test_two_ranges_disagree_like_any_other_two_values(self, tmp_path: Path) -> None:
        idx = built(
            tmp_path,
            **{
                "a.ddd.json": component(
                    "A", declare("output", "Speed", limits={"min": 0, "max": 100})
                ),
                "b.ddd.json": component(
                    "B", declare("input", "Speed", limits={"min": 0, "max": 50})
                ),
            },
        )
        assert offered(idx, "Speed", "limits").disagrees is True

    def test_a_key_nobody_states_does_not_disagree(self, tmp_path: Path) -> None:
        idx = built(tmp_path, **{"a.ddd.json": component("A", declare("output", "Speed"))})
        assert offered(idx, "Speed", "unit").disagrees is False

    def test_a_declaration_whose_kind_cannot_hold_the_key_is_not_asked(
        self, tmp_path: Path
    ) -> None:
        # Two kinds under one name are two objects, which `definition-mismatch` reports; the
        # `dimensions` of the measurement is not made a disagreement by the parameter beside it,
        # which has no dimensions to state.
        idx = built(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("output", "Speed", dimensions=[4])),
                "b.ddd.json": component("B", declare("input", "Speed", kind="parameter")),
            },
        )
        assert offered(idx, "Speed", "dimensions").disagrees is False


class TestWhatAnEditorOffers:
    def test_a_name_is_chosen_from_the_objects_of_the_kind_the_key_takes(
        self, tmp_path: Path
    ) -> None:
        idx = one_of_each(tmp_path)
        for key in ("axis", "x_axis", "y_axis"):
            assert offered(idx, "Torque", key).editor == "name"
            assert offered(idx, "Torque", key).choices == ("Points",)
        assert offered(idx, "Points", "input").choices == ("Speed",)

    def test_a_typename_is_chosen_from_the_types_the_project_declares(self, tmp_path: Path) -> None:
        idx = built(
            tmp_path,
            **{
                "types.ddd.json": types(scalar_type("Speed_t", unit="rpm"), scalar_type("Raw_t")),
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
            },
        )
        offer = offered(idx, "Speed", "typename")
        assert (offer.editor, offer.choices) == ("typename", ("Raw_t", "Speed_t"))

    def test_a_size_is_chosen_from_the_constants_the_project_declares(self, tmp_path: Path) -> None:
        idx = built(
            tmp_path,
            **{
                "constants.ddd.json": {"constants": [{"name": "CELLS", "value": 4}]},
                "a.ddd.json": component("A", declare("output", "Points", kind="axis", size=4)),
            },
        )
        offer = offered(idx, "Points", "size")
        assert (offer.editor, offer.choices) == ("size", ("CELLS",))

    def test_the_keys_the_page_writes_itself_list_nothing(self, tmp_path: Path) -> None:
        idx = one_of_each(tmp_path)
        assert [
            (offered(idx, "Speed", key).editor, offered(idx, "Speed", key).choices)
            for key in ("unit", "volatile", "limits", "conversion", "dimensions")
        ] == [
            ("unit", ()),
            ("volatile", ()),
            ("limits", ()),
            ("none", ()),
            ("none", ()),
        ]
