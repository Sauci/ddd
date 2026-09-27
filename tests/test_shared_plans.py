"""What changing one of a project's constants takes, planned and never written."""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import component, declare, project, write_tree
from ddd.loading import included_files
from ddd.lsp.ranges import Document
from ddd.shared_plans import CONSTANTS_FILE, SharedRefusalError, shared_project

CONSTANTS = {"constants": [{"name": "TREND_SAMPLES", "value": 16, "description": "slots"}]}


class TestWhichFilesAnEntryNames:
    def test_an_entry_that_is_not_a_string_names_nothing(self, tmp_path: Path) -> None:
        assert included_files(tmp_path / "p.ddd.json", 3) == []

    def test_a_pattern_the_loader_cannot_expand_names_nothing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Forced rather than found: a NUL byte in a literal entry never reaches this function's
        own `except` at all, since :func:`~ddd.loading.resolve_path` swallows exactly that
        exception one frame further in and hands back an unresolved path instead - so the one
        arm this test can still reach is the pattern branch's, forced the way
        `test_unit_plans.py`'s own `test_an_entry_the_loader_cannot_expand_names_no_units_file`
        forces the same thing for the same reason."""

        def refuse(self: Path, pattern: str) -> object:
            raise NotImplementedError("Non-relative patterns are unsupported")

        monkeypatch.setattr(Path, "glob", refuse)
        assert included_files(tmp_path / "p.ddd.json", "*.ddd.json") == []

    def test_an_entry_names_the_file_beside_the_project(self, tmp_path: Path) -> None:
        write_tree(tmp_path, {"p.ddd.json": project("P", "c.ddd.json"), "c.ddd.json": CONSTANTS})
        assert included_files(tmp_path / "p.ddd.json", "c.ddd.json") == [
            (tmp_path / "c.ddd.json").resolve()
        ]


class TestTheProjectAPlanIsMadeIn:
    def test_the_constants_files_come_in_the_order_includes_lists_them(
        self, tmp_path: Path
    ) -> None:
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "second.ddd.json", "first.ddd.json", "a.ddd.json"),
                "second.ddd.json": CONSTANTS,
                "first.ddd.json": {"constants": [{"name": "CELLS", "value": 8}]},
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
            },
        )
        cache: dict[Path, Document] = {}
        found = shared_project(tmp_path / "p.ddd.json", (), cache)
        assert [file.name for file in found.constants_files] == [
            "second.ddd.json",
            "first.ddd.json",
        ]
        assert found.project == (tmp_path / "p.ddd.json").resolve()

    def test_a_file_that_does_not_parse_is_no_constants_file(self, tmp_path: Path) -> None:
        """What a file is cannot be told from one nobody could read, so it is not counted - and a
        new constant must not be appended to it."""
        write_tree(tmp_path, {"p.ddd.json": project("P", "c.ddd.json"), "c.ddd.json": "{"})
        cache: dict[Path, Document] = {}
        assert shared_project(tmp_path / "p.ddd.json", (), cache).constants_files == ()

    def test_a_project_naming_no_constants_file_has_none(self, tmp_path: Path) -> None:
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
            },
        )
        cache: dict[Path, Document] = {}
        assert shared_project(tmp_path / "p.ddd.json", (), cache).constants_files == ()

    def test_one_file_named_twice_is_listed_once(self, tmp_path: Path) -> None:
        """A pattern and a literal entry can name the same file; the first is where a new constant
        goes, and a list holding it twice would say there are two places."""
        write_tree(
            tmp_path,
            {"p.ddd.json": project("P", "c.ddd.json", "*.ddd.json"), "c.ddd.json": CONSTANTS},
        )
        cache: dict[Path, Document] = {}
        assert len(shared_project(tmp_path / "p.ddd.json", (), cache).constants_files) == 1

    def test_the_files_that_did_not_load_are_resolved_and_sorted(self, tmp_path: Path) -> None:
        write_tree(tmp_path, {"p.ddd.json": project("P")})
        cache: dict[Path, Document] = {}
        unread = [tmp_path / "z.ddd.json", tmp_path / "a.ddd.json", tmp_path / "z.ddd.json"]
        found = shared_project(tmp_path / "p.ddd.json", unread, cache)
        assert [file.name for file in found.unread] == ["a.ddd.json", "z.ddd.json"]

    def test_an_includes_that_is_not_a_list_names_nothing(self, tmp_path: Path) -> None:
        """A project whose `includes` is a number is refused by the loader; read here it has to
        answer no files rather than iterate a number."""
        write_tree(tmp_path, {"p.ddd.json": {"project": {"name": "P", "includes": 3}}})
        cache: dict[Path, Document] = {}
        assert shared_project(tmp_path / "p.ddd.json", (), cache).constants_files == ()


def test_the_file_a_project_without_one_gets_is_named_for_what_it_holds() -> None:
    assert CONSTANTS_FILE == "constants.ddd.json"


def test_a_refusal_carries_its_code_and_its_sentence() -> None:
    with pytest.raises(SharedRefusalError) as raised:
        raise SharedRefusalError("invalid", "'X' is already declared")
    assert (raised.value.code, raised.value.message) == ("invalid", "'X' is already declared")
