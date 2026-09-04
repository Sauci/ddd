"""The example plugin: each rule, the case that fires it, the nearest case that does not."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from conftest import EXAMPLES, component, declare, project, write_tree
from ddd.cli import EXIT_FINDINGS, EXIT_OK, main

PLUGIN = (EXAMPLES / "plugins" / "ddd_layout.py").resolve()
LAYOUT = EXAMPLES / "layout" / "project.ddd.json"


def stamped(name: str, key: int, version: int, **definition: Any) -> dict[str, Any]:
    return declare(
        "local", name, extensions={"layout": {"key": key, "version": version}}, **definition
    )


def delivery(base: Path, name: str, *declarations: dict[str, Any], **settings: Any) -> str:
    extensions = {"extensions": {"layout": settings}} if settings else {}
    write_tree(
        base,
        {
            f"{name}.ddd.json": project(
                "P", f"{name}-a.ddd.json", plugins=[str(PLUGIN)], **extensions
            ),
            f"{name}-a.ddd.json": component("A", *declarations),
        },
    )
    return str(base / f"{name}.ddd.json")


def compared(base: Path, old: tuple, new: tuple, capsys: pytest.CaptureFixture[str]) -> str:
    before, after = delivery(base, "old", *old), delivery(base, "new", *new)
    main(["compare", before, after, "-W", "missing-id=ignore"])
    return capsys.readouterr().err


class TestTheExampleProject:
    def test_it_checks_clean(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["check", str(LAYOUT), "-W", "missing-id=ignore"]) == EXIT_OK
        assert "are consistent" in capsys.readouterr().err

    def test_its_dictionary_records_the_plugin(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["dump", str(LAYOUT), "-W", "missing-id=ignore"]) == EXIT_OK
        dictionary = json.loads(capsys.readouterr().out)
        assert dictionary["plugins"] == ["layout"]
        assert dictionary["extensions"] == {"layout": {"max_key": 4095}}
        keys = {entry["name"]: entry["extensions"] for entry in dictionary["objects"]}
        assert keys["EngineHours"] == {"layout": {"key": 12, "version": 3}}


class TestWithinOneDelivery:
    def test_two_objects_claiming_one_key(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        root = delivery(tree, "p", stamped("X", 1, 1), stamped("Y", 1, 1))
        assert main(["check", root, "-W", "missing-id=ignore"]) == EXIT_FINDINGS
        captured = capsys.readouterr().err
        assert (
            "p-a.ddd.json#component.interface[1]: error[layout/duplicate-key]: 'Y' claims key 1, "
            "which 'X' already claims" in captured
        )
        assert "p-a.ddd.json#component.interface[0]: first claimed here" in captured

    def test_a_key_above_max_key(self, tree: Path, capsys: pytest.CaptureFixture[str]) -> None:
        root = delivery(tree, "p", stamped("X", 100, 1), max_key=99)
        assert main(["check", root, "-W", "missing-id=ignore"]) == EXIT_FINDINGS
        assert (
            "error[layout/key-out-of-range]: 'X' claims key 100, above the project's max_key of 99"
            in capsys.readouterr().err
        )

    def test_distinct_keys_within_range_are_clean(self, tree: Path) -> None:
        root = delivery(tree, "p", stamped("X", 1, 1), stamped("Y", 2, 1), declare("local", "Z"))
        assert main(["check", root, "-W", "missing-id=ignore"]) == EXIT_OK


class TestBetweenDeliveries:
    def test_a_changed_layout_with_the_same_version(self, tree: Path, capsys) -> None:
        err = compared(
            tree,
            (stamped("X", 1, 2, datatype="uint8"),),
            (stamped("X", 1, 2, datatype="uint16"),),
            capsys,
        )
        assert (
            "error[layout/version-not-bumped]: 'X' (key 1) changed its layout and kept version 2"
            in err
        )

    def test_a_changed_layout_with_a_lower_version(self, tree: Path, capsys) -> None:
        err = compared(
            tree,
            (stamped("X", 1, 2, datatype="uint8"),),
            (stamped("X", 1, 1, datatype="uint16"),),
            capsys,
        )
        assert (
            "error[layout/version-not-bumped]: 'X' (key 1) changed its layout and went from "
            "version 2 to 1" in err
        )

    def test_a_changed_layout_with_a_higher_version_is_clean(self, tree: Path, capsys) -> None:
        err = compared(
            tree,
            (stamped("X", 1, 2, datatype="uint8"),),
            (stamped("X", 1, 3, datatype="uint16"),),
            capsys,
        )
        assert "layout/" not in err

    def test_a_changed_unit_is_a_changed_layout(self, tree: Path, capsys) -> None:
        err = compared(
            tree, (stamped("X", 1, 1, unit="s"),), (stamped("X", 1, 1, unit="ms"),), capsys
        )
        assert "layout/version-not-bumped" in err

    def test_a_changed_version_with_the_same_layout(self, tree: Path, capsys) -> None:
        err = compared(tree, (stamped("X", 1, 1),), (stamped("X", 1, 2),), capsys)
        assert (
            "warning[layout/needless-version]: 'X' (key 1) went from version 1 to 2 with the "
            "same layout" in err
        )

    def test_a_changed_description_is_not_a_changed_layout(self, tree: Path, capsys) -> None:
        err = compared(tree, (stamped("X", 1, 1),), (stamped("X", 1, 1, description="d"),), capsys)
        assert "layout/" not in err

    def test_a_key_now_naming_a_different_object_by_name(self, tree: Path, capsys) -> None:
        err = compared(tree, (stamped("X", 1, 1),), (stamped("Y", 1, 1),), capsys)
        assert "error[layout/reused-key]: key 1 was 'X' and is now 'Y', a different object" in err

    def test_a_key_now_naming_a_different_object_by_id(self, tree: Path, capsys) -> None:
        old = (stamped("X", 1, 1, id="aaaaaaaaaaaa"),)
        new = (stamped("X", 1, 1, id="bbbbbbbbbbbb"),)
        assert "layout/reused-key" in compared(tree, old, new, capsys)

    def test_a_renamed_object_keeps_its_key_by_id(self, tree: Path, capsys) -> None:
        old = (stamped("X", 1, 1, id="aaaaaaaaaaaa"),)
        new = (stamped("Y", 1, 1, id="aaaaaaaaaaaa"),)
        err = compared(tree, old, new, capsys)
        assert "layout/reused-key" not in err
        assert "renamed-object" in err

    def test_an_object_under_a_different_key(self, tree: Path, capsys) -> None:
        old = (stamped("X", 1, 1, id="aaaaaaaaaaaa"),)
        new = (stamped("X", 2, 1, id="aaaaaaaaaaaa"),)
        err = compared(tree, old, new, capsys)
        assert (
            "error[layout/key-changed]: 'X' carried key 1 and now carries 2; its entry under "
            "1 is orphaned" in err
        )
        assert "layout/removed-entry" not in err

    def test_a_key_that_is_gone(self, tree: Path, capsys) -> None:
        err = compared(tree, (stamped("X", 1, 1),), (declare("local", "X"),), capsys)
        assert "warning[layout/removed-entry]: key 1 ('X') is gone" in err

    def test_a_structured_variable_is_compared_by_its_leaves(self, tree: Path, capsys) -> None:
        def files(name: str, datatype: str) -> dict[str, Any]:
            return {
                f"{name}.ddd.json": project(
                    "P", f"{name}-t.ddd.json", f"{name}-a.ddd.json", plugins=[str(PLUGIN)]
                ),
                f"{name}-t.ddd.json": {
                    "types": [
                        {
                            "type": "struct",
                            "name": "Pair_t",
                            "members": [
                                {
                                    "name": "a",
                                    "member": "value",
                                    "datatype": datatype,
                                    "conversion": {"kind": "identity"},
                                }
                            ],
                        }
                    ]
                },
                f"{name}-a.ddd.json": component("A", stamped("P", 7, 1, typename="Pair_t")),
            }

        write_tree(tree, {**files("old", "uint8"), **files("new", "uint16")})
        main(
            [
                "compare",
                str(tree / "old.ddd.json"),
                str(tree / "new.ddd.json"),
                "-W",
                "missing-id=ignore",
            ]
        )
        assert "layout/version-not-bumped" in capsys.readouterr().err

    def test_reordered_members_are_a_changed_layout(self, tree: Path, capsys) -> None:
        datatypes = {"a": "uint8", "b": "uint16"}

        def files(name: str, order: tuple[str, str]) -> dict[str, Any]:
            return {
                f"{name}.ddd.json": project(
                    "P", f"{name}-t.ddd.json", f"{name}-a.ddd.json", plugins=[str(PLUGIN)]
                ),
                f"{name}-t.ddd.json": {
                    "types": [
                        {
                            "type": "struct",
                            "name": "Pair_t",
                            "members": [
                                {
                                    "name": member,
                                    "member": "value",
                                    "datatype": datatypes[member],
                                    "conversion": {"kind": "identity"},
                                }
                                for member in order
                            ],
                        }
                    ]
                },
                f"{name}-a.ddd.json": component("A", stamped("P", 7, 1, typename="Pair_t")),
            }

        write_tree(tree, {**files("old", ("a", "b")), **files("new", ("b", "a"))})
        main(
            [
                "compare",
                str(tree / "old.ddd.json"),
                str(tree / "new.ddd.json"),
                "-W",
                "missing-id=ignore",
            ]
        )
        assert "layout/version-not-bumped" in capsys.readouterr().err

    def test_the_same_member_order_is_clean(self, tree: Path, capsys) -> None:
        datatypes = {"a": "uint8", "b": "uint16"}

        def files(name: str, order: tuple[str, str]) -> dict[str, Any]:
            return {
                f"{name}.ddd.json": project(
                    "P", f"{name}-t.ddd.json", f"{name}-a.ddd.json", plugins=[str(PLUGIN)]
                ),
                f"{name}-t.ddd.json": {
                    "types": [
                        {
                            "type": "struct",
                            "name": "Pair_t",
                            "members": [
                                {
                                    "name": member,
                                    "member": "value",
                                    "datatype": datatypes[member],
                                    "conversion": {"kind": "identity"},
                                }
                                for member in order
                            ],
                        }
                    ]
                },
                f"{name}-a.ddd.json": component("A", stamped("P", 7, 1, typename="Pair_t")),
            }

        write_tree(tree, {**files("old", ("a", "b")), **files("new", ("a", "b"))})
        main(
            [
                "compare",
                str(tree / "old.ddd.json"),
                str(tree / "new.ddd.json"),
                "-W",
                "missing-id=ignore",
            ]
        )
        assert "layout/" not in capsys.readouterr().err


class TestTheHeader:
    def test_one_entry_per_stamped_object_sorted_by_key(self, tree: Path) -> None:
        root = delivery(
            tree, "p", stamped("Y", 20, 2), stamped("X", 3, 1), declare("local", "Z"), max_key=100
        )
        out = tree / "out"
        assert (
            main(["generate", "layout", root, "-o", str(out), "-W", "missing-id=ignore"]) == EXIT_OK
        )
        header = (out / "ddd_layout.h").read_text(encoding="utf-8")
        assert "#define DDD_LAYOUT_MAX_KEY 100u" in header
        assert header.index("{ 3u, 1u, sizeof(X), &X }") < header.index(
            "{ 20u, 2u, sizeof(Y), &Y }"
        )
        assert "Z" not in header.split("DDD_LAYOUT_ENTRIES")[1]
