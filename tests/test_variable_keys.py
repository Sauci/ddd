"""What every key of a variable offers the panel of ``ddd gui``, and the kinds the index records."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from conftest import component, declare, project, run_analysis, scalar_type, types, write_tree
from ddd.diagnostics import DiagnosticBag
from ddd.loading import load_workspace
from ddd.lsp.edits import PROPAGATED_KEYS
from ddd.lsp.navigation import Index, index
from ddd.variable_keys import (
    DATATYPES,
    EDITORS,
    KEY_ORDER,
    Carried,
    InPlay,
    offer_for,
    offers,
    unit_refusal,
)
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

    def test_a_declaration_writing_an_explicit_null_states_nothing_there(
        self, tmp_path: Path
    ) -> None:
        # `null` is how a file says a key holds nothing, and the loader reads it as absent -
        # `ddd check` accepts an explicit `"typename": null` beside a real datatype. Read as a
        # key that is stated, the panel offered to strip the storage this declaration actually
        # uses and withheld the one holding nothing, exactly backwards, and taking that offer
        # would have written a file the loader refuses.
        idx = built(
            tmp_path, **{"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))}
        )
        edited(tmp_path / "a.ddd.json", lambda definition: definition.update({"typename": None}))
        assert offered(idx, "Speed", "datatype").carried == (Carried(allowed=True, required=True),)
        assert offered(idx, "Speed", "typename").carried == (Carried(allowed=True, required=False),)

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

    def test_a_conversion_the_models_complete_is_one_value_with_what_it_completes_to(
        self, tmp_path: Path
    ) -> None:
        # `{"factor": 2}` is the conversion `{"kind": "linear", "factor": 2, "offset": 0}` by
        # `definition-mismatch`'s own account - the models infer the rest - so the panel has to
        # group them the same way, or it marks a row red the checker files no finding about.
        idx = built(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("output", "Speed", conversion={"factor": 2})),
                "b.ddd.json": component(
                    "B",
                    declare(
                        "input",
                        "Speed",
                        conversion={"kind": "linear", "factor": 2, "offset": 0},
                    ),
                ),
            },
        )
        offer = offered(idx, "Speed", "conversion")
        assert [(value.components, value.producer) for value in offer.values] == [
            (("A", "B"), True)
        ]
        assert offer.disagrees is False

    def test_limits_the_model_resolves_the_same_are_one_value(self, tmp_path: Path) -> None:
        idx = built(
            tmp_path,
            **{
                "a.ddd.json": component(
                    "A", declare("output", "Speed", limits={"min": 0, "max": 100})
                ),
                "b.ddd.json": component(
                    "B", declare("input", "Speed", limits={"min": 0.0, "max": 100.0})
                ),
            },
        )
        offer = offered(idx, "Speed", "limits")
        assert [(value.components, value.producer) for value in offer.values] == [
            (("A", "B"), True)
        ]
        assert offer.disagrees is False

    def test_two_enum_conversions_of_one_name_group_by_the_name_alone(self, tmp_path: Path) -> None:
        # Reordered and redescribed enumerators are `enum-conflict`'s to report, not this
        # panel's: :func:`~ddd.models.conversion.conversion_interface_value` narrows an enum to
        # its name, exactly as `definition-mismatch` does.
        idx = built(
            tmp_path,
            **{
                "a.ddd.json": component(
                    "A",
                    declare(
                        "output",
                        "Speed",
                        conversion={
                            "kind": "enum",
                            "name": "StateA",
                            "enumerators": [
                                {"name": "OFF", "value": 0},
                                {"name": "ON", "value": 1},
                            ],
                        },
                    ),
                ),
                "b.ddd.json": component(
                    "B",
                    declare(
                        "input",
                        "Speed",
                        conversion={
                            "kind": "enum",
                            "name": "StateA",
                            "enumerators": [
                                {"name": "ON", "value": 1, "description": "engaged"},
                                {"name": "OFF", "value": 0},
                            ],
                        },
                    ),
                ),
            },
        )
        offer = offered(idx, "Speed", "conversion")
        assert [(value.components, value.producer) for value in offer.values] == [
            (("A", "B"), True)
        ]
        assert offer.disagrees is False

    def test_a_conversion_the_models_refuse_falls_back_to_its_own_text(
        self, tmp_path: Path
    ) -> None:
        # A definition mid-edit may hold a conversion the models refuse outright - `factor: 0`
        # cannot convert back - and the panel still has to draw a row for what is on disk
        # rather than pretend the key states nothing.
        idx = built(
            tmp_path,
            **{"a.ddd.json": component("A", declare("output", "Speed", conversion={"factor": 2}))},
        )
        edited(
            tmp_path / "a.ddd.json",
            lambda definition: definition.__setitem__(
                "conversion", {"kind": "linear", "factor": 0}
            ),
        )
        values = offered(idx, "Speed", "conversion").values
        assert len(values) == 1
        assert json.loads(values[0].raw) == {"kind": "linear", "factor": 0}
        assert values[0].components == ("A",)
        assert values[0].producer is True

    def test_limits_the_models_refuse_fall_back_to_their_own_text(self, tmp_path: Path) -> None:
        # The same drift as the conversion above, for limits: a `min` above the `max` is
        # refused outright, and the panel still has to draw a row for what is on disk.
        idx = built(
            tmp_path,
            **{
                "a.ddd.json": component(
                    "A", declare("output", "Speed", limits={"min": 0, "max": 100})
                )
            },
        )
        edited(
            tmp_path / "a.ddd.json",
            lambda definition: definition.__setitem__("limits", {"min": 100, "max": 0}),
        )
        values = offered(idx, "Speed", "limits").values
        assert len(values) == 1
        assert json.loads(values[0].raw) == {"min": 100, "max": 0}
        assert values[0].components == ("A",)
        assert values[0].producer is True

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

    def test_two_ranges_one_double_holds_disagree_as_the_checker_files_them(
        self, tmp_path: Path
    ) -> None:
        """3:M9. Past 2^53 a double holds every other whole number: the two maxima were read as
        one, the row showed one value and no disagreement, and ``ddd check`` filed the two."""
        idx = built(
            tmp_path,
            **{
                "a.ddd.json": component(
                    "A", declare("output", "Speed", "uint64", limits={"min": 0, "max": 2**53 + 1})
                ),
                "b.ddd.json": component(
                    "B", declare("input", "Speed", "uint64", limits={"min": 0, "max": 2**53})
                ),
            },
        )
        offer = offered(idx, "Speed", "limits")
        assert [(value.components, value.producer) for value in offer.values] == [
            (("A",), True),
            (("B",), False),
        ]
        assert offer.disagrees is True

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

    def test_another_components_local_is_not_offered_to_an_axis_or_an_input(
        self, tmp_path: Path
    ) -> None:
        """13:I6. A local is the owner's alone: chosen from another component's declaration, the
        offer wrote a ``local-conflict``."""
        files = {
            "a.ddd.json": component(
                "A",
                declare("local", "Mine", kind="axis", size=4),
                declare("local", "Hidden"),
            ),
            "b.ddd.json": component(
                "B",
                declare("output", "Points", kind="axis", size=4),
                declare("output", "Speed"),
                declare("output", "Torque", kind="curve", axis="Points"),
                declare("output", "Gain", kind="axis", size=4, input="Speed"),
            ),
        }
        idx = built(tmp_path, **files)
        assert offered(idx, "Torque", "axis").choices == ("Gain", "Points")
        assert offered(idx, "Gain", "input").choices == ("Speed",)

    def test_what_was_offered_beside_the_local_was_what_the_check_refuses(
        self, tmp_path: Path
    ) -> None:
        files = {
            "a.ddd.json": component("A", declare("local", "Mine", kind="axis", size=4)),
            "b.ddd.json": component("B", declare("output", "Torque", kind="curve", axis="Mine")),
        }
        _, bag = run_analysis(
            tmp_path, {"p.ddd.json": project("P", *files), **files}, root="p.ddd.json"
        )
        assert "local-conflict" in [diagnostic.check for diagnostic in bag]

    def test_an_offer_for_no_components_declaration_lists_every_object(
        self, tmp_path: Path
    ) -> None:
        """A type's panel has no component to compare the owner of a local with."""
        idx = built(
            tmp_path,
            **{"a.ddd.json": component("A", declare("local", "Mine", kind="axis", size=4))},
        )
        assert offer_for(idx, "axis", None, required=False).choices == ("Mine",)

    def test_a_file_is_one_component_so_files_are_what_is_compared(self, tmp_path: Path) -> None:
        """A second file naming a component is refused ``duplicate-component`` and never loaded,
        so the index holds one file for each component name: the owner of a local is one file."""
        files = {
            "a.ddd.json": component("A", declare("local", "Mine", kind="axis", size=4)),
            "a2.ddd.json": component("A", declare("output", "Torque", kind="curve", axis="Mine")),
        }
        _, bag = run_analysis(
            tmp_path, {"p.ddd.json": project("P", *files), **files}, root="p.ddd.json"
        )
        assert "duplicate-component" in [diagnostic.check for diagnostic in bag]
        workspace = load_workspace(tmp_path / "p.ddd.json", DiagnosticBag())
        assert workspace is not None
        names = list(index(workspace).components.values())
        assert len(names) == len(set(names))

    def test_a_component_is_offered_its_own_locals(self, tmp_path: Path) -> None:
        idx = built(
            tmp_path,
            **{
                "a.ddd.json": component(
                    "A",
                    declare("local", "Mine", kind="axis", size=4),
                    declare("output", "Torque", kind="curve", axis="Mine"),
                ),
            },
        )
        assert offered(idx, "Torque", "axis").choices == ("Mine",)

    def test_a_variable_the_owner_shares_with_another_is_not_offered_the_local(
        self, tmp_path: Path
    ) -> None:
        idx = built(
            tmp_path,
            **{
                "a.ddd.json": component(
                    "A",
                    declare("local", "Mine", kind="axis", size=4),
                    declare("output", "Points", kind="axis", size=4),
                    declare("output", "Torque", kind="curve", axis="Points"),
                ),
                "b.ddd.json": component(
                    "B", declare("input", "Torque", kind="curve", axis="Points")
                ),
            },
        )
        assert offered(idx, "Torque", "axis").choices == ("Points",)

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


class TestAUnitWithSpacesAroundIt:
    """15:M10: a unit settled with a space around it was written, while the Units tab refuses that
    spelling - and without a units file no finding said the project now held two spellings of one
    unit."""

    @pytest.mark.parametrize(
        ("raw", "unit"),
        [
            pytest.param('"V "', "V ", id="after"),
            pytest.param('" V"', " V", id="before"),
            pytest.param('"\\tV"', "\tV", id="a-tab"),
        ],
    )
    def test_is_refused_in_the_units_tabs_words(self, raw: str, unit: str) -> None:
        assert unit_refusal(raw) == f"'{unit}' has spaces around it"

    @pytest.mark.parametrize("raw", ['"V"', '"m s"', '""', "5", "null"])
    def test_anything_else_is_no_spaces_refusal(self, raw: str) -> None:
        assert unit_refusal(raw) is None


SPEED_T = types(scalar_type("Speed_t", "uint16", unit="rpm"))
"""What a reader naming it states by name: ``uint16``, the identity and ``rpm``."""

SPELLED = {"datatype": "uint16", "unit": "rpm", "conversion": {"kind": "identity"}}
"""The same three, spelled out where a type would fix them."""


def pair(**declarations: Any) -> dict[str, Any]:
    """Files of a project: ``declarations`` maps a component's name to its declaration of ``V``."""
    return {
        "t.ddd.json": SPEED_T,
        "x.ddd.json": types(scalar_type("Rate_t", "uint16", unit="rpm")),
        "u.ddd.json": types(scalar_type("Torque_t", "uint8", unit="rpm")),
        "e.ddd.json": types({"type": "external", "name": "Drv_t", "header": "drv.h"}),
        **{f"c_{name}.ddd.json": component(name, entry) for name, entry in declarations.items()},
    }


# What the panel says of a key, held against what `ddd check` files about the same pair:
# (panel's key, the word `definition-mismatch` names it by, the files, the panel's `disagrees`,
# and the checks `ddd check` files). The panel's `typename` is what the check reads as `datatype`:
# both are the question of which type a declaration is.
PAIRS = {
    "a producer spelling what a reader's type fixes": (
        "typename",
        "datatype",
        pair(
            W=declare("output", "V", **SPELLED),
            R=declare("input", "V", typename="Speed_t"),
        ),
        False,
        [],
    ),
    "a producer naming the type a reader spells": (
        "typename",
        "datatype",
        pair(
            W=declare("output", "V", typename="Speed_t"),
            R=declare("input", "V", **SPELLED),
        ),
        False,
        [],
    ),
    "a reader naming the type another spells, one producer": (
        "typename",
        "datatype",
        pair(
            W=declare("output", "V", **SPELLED),
            R=declare("input", "V", typename="Speed_t"),
            S=declare("input", "V", **SPELLED),
            T=declare("input", "V", typename="Speed_t"),
        ),
        False,
        [],
    ),
    "readers alone, one naming the type and one spelling it": (
        "typename",
        "datatype",
        pair(
            R=declare("input", "V", typename="Speed_t"),
            S=declare("input", "V", **SPELLED),
        ),
        False,
        [],
    ),
    "two types of one meaning": (
        "typename",
        "datatype",
        pair(
            W=declare("output", "V", typename="Speed_t"),
            R=declare("input", "V", typename="Rate_t"),
        ),
        True,  # the names differ, and the panel's typename row settles which one
        [],
    ),
    "two types of two meanings": (
        "typename",
        "datatype",
        pair(
            W=declare("output", "V", typename="Speed_t"),
            R=declare("input", "V", typename="Torque_t"),
        ),
        True,
        ["definition-mismatch"],
    ),
    "a type beside a datatype of another meaning": (
        "datatype",
        "datatype",
        pair(
            W=declare("output", "V", **{**SPELLED, "datatype": "uint8"}),
            R=declare("input", "V", typename="Speed_t"),
        ),
        True,  # one name only, so the typename row is silent; the datatype row says what differs
        ["definition-mismatch"],
    ),
    "a datatype beside the datatype a type fixes, spelled the same": (
        "datatype",
        "datatype",
        pair(
            W=declare("output", "V", **SPELLED),
            R=declare("input", "V", typename="Speed_t"),
        ),
        False,
        [],
    ),
    "an external type beside a scalar": (
        "typename",
        "datatype",
        pair(
            W=declare("output", "V", **SPELLED),
            R=declare("input", "V", typename="Drv_t"),
        ),
        False,  # one name only; the check files `type-kind` for the external type instead
        ["type-kind"],
    ),
    "a unit of no text beside none": (
        "unit",
        "unit",
        pair(
            W=declare("output", "V", unit=""),
            R=declare("input", "V"),
        ),
        False,
        [],
    ),
    "a unit beside none": (
        "unit",
        "unit",
        pair(
            W=declare("output", "V", unit="rpm"),
            R=declare("input", "V"),
        ),
        True,
        ["definition-mismatch"],
    ),
    "two units": (
        "unit",
        "unit",
        pair(
            W=declare("output", "V", unit="rpm"),
            R=declare("input", "V", unit="%"),
        ),
        True,
        ["definition-mismatch"],
    ),
    "limits past 2^53, one apart": (
        "limits",
        "limits",
        pair(
            W=declare("output", "V", "uint64", limits={"min": 0, "max": 2**53 + 1}),
            R=declare("input", "V", "uint64", limits={"min": 0, "max": 2**53}),
        ),
        True,
        ["definition-mismatch"],
    ),
    "limits spelled two ways": (
        "limits",
        "limits",
        pair(
            W=declare("output", "V", limits={"min": 0, "max": 100}),
            R=declare("input", "V", limits={"min": 0.0, "max": 100.0}),
        ),
        False,
        [],
    ),
}


def filed_about(bag: Any, word: str) -> list[str]:
    """What ``ddd check`` files about ``word`` of ``V``: a ``definition-mismatch`` naming it, and
    ``type-kind``, which refuses a declaration of an external type whatever its neighbours say."""
    return [
        diagnostic.check
        for diagnostic in bag
        if diagnostic.check == "type-kind"
        or (diagnostic.check == "definition-mismatch" and f"({word}:" in diagnostic.message)
    ]


class TestThePanelAgreesWithTheCheck:
    @pytest.mark.parametrize("name", PAIRS)
    def test_the_panels_word_is_the_checks(self, tmp_path: Path, name: str) -> None:
        key, word, files, disagrees, filed = PAIRS[name]
        _, bag = run_analysis(
            tmp_path, {"p.ddd.json": project("P", *files), **files}, root="p.ddd.json"
        )
        assert filed_about(bag, word) == filed
        idx = built(tmp_path, **files)
        assert offered(idx, "V", key).disagrees is disagrees

    def test_kind_has_no_row_though_the_check_names_it(self, tmp_path: Path) -> None:
        """No edit carries ``kind``, so the panel offers no row to disagree on."""
        files = pair(
            W=declare("output", "V"),
            R=declare("input", "V", kind="parameter"),
        )
        _, bag = run_analysis(
            tmp_path, {"p.ddd.json": project("P", *files), **files}, root="p.ddd.json"
        )
        assert any(
            diagnostic.check == "definition-mismatch" and "(kind:" in diagnostic.message
            for diagnostic in bag
        )
        assert "kind" not in KEY_ORDER
