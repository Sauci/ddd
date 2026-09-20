"""What every key of a variable offers the panel of ``ddd gui``, and the kinds the index records."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from conftest import component, declare, project, write_tree
from ddd.diagnostics import DiagnosticBag
from ddd.loading import load_workspace
from ddd.lsp.navigation import Index, index


def built(tmp_path: Path, **files: Any) -> Index:
    """The index of a project of these files, named by a project description of the same name."""
    write_tree(tmp_path, {"p.ddd.json": project("P", *files), **files})
    workspace = load_workspace(tmp_path / "p.ddd.json", DiagnosticBag())
    assert workspace is not None
    return index(workspace)


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
