"""Which declarations of one variable a change of one key reaches, and which of them refuse it.

:func:`ddd.lsp.edits.settle` is the rule behind both the language server's "Apply this unit to N
other declarations" and the unit panel of ``ddd gui``, so each case here is a sentence about what
either of them may write.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from conftest import component, declare, project, scalar_type, struct_type, types, write_tree
from ddd.diagnostics import DiagnosticBag
from ddd.loading import load_workspace
from ddd.lsp.edits import Settled, Settlement, Unsettled, settle
from ddd.lsp.navigation import Index, Site, index
from ddd.lsp.ranges import Document


def built(tmp_path: Path, **files: Any) -> Index:
    """The index of a project including every file given, as the language server builds it."""
    write_tree(tmp_path, {"p.ddd.json": project("P", *files), **files})
    workspace = load_workspace(tmp_path / "p.ddd.json", DiagnosticBag())
    assert workspace is not None
    return index(workspace)


def site_in(built_index: Index, file: str, name: str = "Speed") -> Site:
    """The site the index records for ``name`` in ``file``."""
    return next(site for site in built_index.declarations[name] if site.path.name == file)


def settled(built_index: Index, key: str, raw: str | None, name: str = "Speed") -> Settlement:
    cache: dict[Path, Document] = {}
    return settle(built_index, name, key, raw, cache)


class TestWhatChanges:
    def test_a_declaration_stating_another_value_is_given_this_one(self, tmp_path: Path) -> None:
        idx = built(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="1/min")),
                "c.ddd.json": component("C", declare("input", "Speed", unit="rpm")),
            },
        )
        assert settled(idx, "unit", '"rpm"') == Settlement(
            (Settled(site_in(idx, "b.ddd.json"), '"rpm"'),), ()
        )

    def test_a_declaration_stating_nothing_is_given_the_value(self, tmp_path: Path) -> None:
        idx = built(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed")),
            },
        )
        assert settled(idx, "unit", '"rpm"').changes == (
            Settled(site_in(idx, "b.ddd.json"), '"rpm"'),
        )

    def test_no_value_takes_the_key_out_where_it_is_stated(self, tmp_path: Path) -> None:
        idx = built(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed")),
            },
        )
        assert settled(idx, "unit", None) == Settlement(
            (Settled(site_in(idx, "a.ddd.json"), None),), ()
        )

    def test_when_every_declaration_agrees_nothing_changes(self, tmp_path: Path) -> None:
        idx = built(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="rpm")),
            },
        )
        assert settled(idx, "unit", '"rpm"') == Settlement((), ())

    def test_a_name_nothing_declares_settles_nothing(self, tmp_path: Path) -> None:
        idx = built(
            tmp_path, **{"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))}
        )
        assert settled(idx, "unit", '"rpm"', name="Torque") == Settlement((), ())

    def test_a_reader_leaving_its_limits_to_the_producer_is_left_alone(
        self, tmp_path: Path
    ) -> None:
        """Limits are the one key silence agrees with: the checker counts a consumer that states
        none as deferring to its producer, so spreading a range into it settles nothing."""
        idx = built(
            tmp_path,
            **{
                "a.ddd.json": component(
                    "A", declare("output", "Speed", limits={"min": 0, "max": 10})
                ),
                "b.ddd.json": component("B", declare("input", "Speed")),
            },
        )
        raw = json.dumps({"min": 0, "max": 20})
        assert settled(idx, "limits", raw).changes == (Settled(site_in(idx, "a.ddd.json"), raw),)


class TestWhatRefuses:
    def test_a_declaration_whose_type_fixes_another_unit_refuses(self, tmp_path: Path) -> None:
        idx = built(
            tmp_path,
            **{
                "types.ddd.json": types(scalar_type("Speed_t", unit="rpm")),
                "a.ddd.json": component("A", declare("output", "Speed", typename="Speed_t")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="%")),
            },
        )
        assert settled(idx, "unit", '"%"') == Settlement(
            (), (Unsettled(site_in(idx, "a.ddd.json"), "type", "Speed_t"),)
        )

    def test_a_declaration_whose_type_fixes_the_same_unit_agrees(self, tmp_path: Path) -> None:
        idx = built(
            tmp_path,
            **{
                "types.ddd.json": types(scalar_type("Speed_t", unit="rpm")),
                "a.ddd.json": component("A", declare("output", "Speed", typename="Speed_t")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="%")),
            },
        )
        assert settled(idx, "unit", '"rpm"') == Settlement(
            (Settled(site_in(idx, "b.ddd.json"), '"rpm"'),), ()
        )

    def test_a_structure_has_no_unit_to_agree_with(self, tmp_path: Path) -> None:
        idx = built(
            tmp_path,
            **{
                "types.ddd.json": types(struct_type("Sample_t")),
                "a.ddd.json": component("A", declare("output", "Speed", typename="Sample_t")),
                "b.ddd.json": component("B", declare("input", "Speed", typename="Sample_t")),
            },
        )
        assert settled(idx, "unit", None) == Settlement((), ())
        assert [refused.reason for refused in settled(idx, "unit", '"%"').unsettled] == [
            "type",
            "type",
        ]

    def test_a_kind_without_the_key_refuses_it(self, tmp_path: Path) -> None:
        idx = built(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("output", "Speed")),
                "b.ddd.json": component("B", declare("input", "Speed")),
            },
        )
        # Only an axis has a size.
        assert [refused.reason for refused in settled(idx, "size", "4").unsettled] == [
            "kind",
            "kind",
        ]

    def test_a_key_the_kind_requires_is_not_taken_out(self, tmp_path: Path) -> None:
        idx = built(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("output", "Speed")),
                "b.ddd.json": component("B", declare("input", "Speed")),
            },
        )
        # Every definition states volatile: without it the file would not load.
        assert [refused.reason for refused in settled(idx, "volatile", None).unsettled] == [
            "kind",
            "kind",
        ]

    def test_a_declaration_its_file_no_longer_holds_is_unreachable(self, tmp_path: Path) -> None:
        idx = built(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="%")),
            },
        )
        write_tree(tmp_path, {"b.ddd.json": component("B", declare("input", "Torque"))})
        assert settled(idx, "unit", '"rpm"') == Settlement(
            (), (Unsettled(site_in(idx, "b.ddd.json"), "unreachable"),)
        )
