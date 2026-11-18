"""Tests for the generated c code."""

from __future__ import annotations

import errno
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from conftest import DEMO, EXAMPLES, component, declare, project, render_files, run_analysis
from ddd.backends import (
    MANIFEST_NAME,
    A2lBackend,
    A2lOptions,
    GeneratedFile,
    Manifest,
    RemovalError,
    WriteResult,
    WriteStatus,
    render,
    write,
)
from ddd.backends.c.literals import component_guard
from ddd.models.reserved import is_reserved_identifier


def generate(tree: Path, files: dict[str, Any], **options: Any) -> dict[str, str]:
    dictionary, bag = run_analysis(tree, files)
    assert dictionary is not None, [d.render() for d in bag]
    assert not bag.has_errors, [d.render() for d in bag]
    rendered = render_files(dictionary, tree / "gen", **options)
    return {file.path.name: file.content for file in rendered}


def simple(*declarations: dict[str, Any], name: str = "A") -> dict[str, Any]:
    return {
        "project.ddd.json": project("P", "a.ddd.json"),
        "a.ddd.json": component(name, *declarations, description="the component"),
    }


class TestGlobalDefinitionFile:
    def test_scalar_definition(self, tree: Path) -> None:
        files = generate(tree, simple(declare("local", "Speed", "uint16", init=7)))
        assert "uint16_t Speed = 7U;" in files["ddd_globals.c"]
        assert 'include "ddd_globals.h"' in files["ddd_globals.c"]

    def test_without_init_no_initialiser_is_emitted(self, tree: Path) -> None:
        files = generate(tree, simple(declare("local", "Speed", "uint16")))
        assert "uint16_t Speed;" in files["ddd_globals.c"]

    def test_volatile(self, tree: Path) -> None:
        files = generate(tree, simple(declare("local", "Speed", "uint16", volatile=True)))
        assert "volatile uint16_t Speed;" in files["ddd_globals.c"]

    def test_signed_negative_and_float_literals(self, tree: Path) -> None:
        files = generate(
            tree,
            simple(
                declare("local", "A", "sint16", init=-400),
                declare("local", "B", "float32", init=1.5),
                declare("local", "C", "float64", init=2),
                declare("local", "D", "boolean", init=True),
                declare("local", "E", "uint64", init=5),
                declare("local", "F", "sint64", init=-5),
            ),
        )
        source = files["ddd_globals.c"]
        assert "int16_t A = -400;" in source
        assert "float B = 1.5F;" in source
        assert "double C = 2.0;" in source
        # 1 rather than true: the word would need <stdbool.h> before C23, and a project on
        # AUTOSAR's Platform_Types has TRUE instead; the numeral needs no header anywhere.
        assert "bool D = 1;" in source
        assert "uint64_t E = 5ULL;" in source
        assert "int64_t F = -5LL;" in source

    def test_one_dimensional_array(self, tree: Path) -> None:
        declaration = declare("local", "A", "uint8", dimensions=[3], init=[1, 2, 3])
        files = generate(tree, simple(declaration))
        assert "uint8_t A[3] = { 1U, 2U, 3U };" in files["ddd_globals.c"]

    def test_long_array_is_wrapped(self, tree: Path) -> None:
        files = generate(tree, simple(declare("local", "A", "uint8", dimensions=[10], init=1)))
        source = files["ddd_globals.c"]
        assert "uint8_t A[10] = {\n    1U, 1U, 1U, 1U, 1U, 1U, 1U, 1U,\n    1U, 1U\n};" in source

    def test_two_dimensional_array(self, tree: Path) -> None:
        files = generate(
            tree, simple(declare("local", "A", "sint8", dimensions=[2, 2], init=[[1, 2], [3, 4]]))
        )
        assert "int8_t A[2][2] = {\n    { 1, 2 },\n    { 3, 4 }\n};" in files["ddd_globals.c"]

    def test_condition_wraps_the_definition(self, tree: Path) -> None:
        files = generate(
            tree, simple(declare("local", "A", condition="defined(FEATURE_X) && VERSION > 2"))
        )
        source = files["ddd_globals.c"]
        assert "#if defined(FEATURE_X) && VERSION > 2\n" in source
        assert "#endif /* defined(FEATURE_X) && VERSION > 2 */" in source
        assert source.index("#if ") < source.index("uint8_t A;") < source.index("#endif /*")

    def test_description_and_unit_become_a_comment(self, tree: Path) -> None:
        files = generate(tree, simple(declare("local", "A", description="Flow rate", unit="l/min")))
        assert "/** Flow rate [l/min] */" in files["ddd_globals.c"]

    def test_comment_end_marker_is_escaped(self, tree: Path) -> None:
        files = generate(tree, simple(declare("local", "A", description="a */ b")))
        assert "/** a * / b */" in files["ddd_globals.c"]

    def test_comment_start_marker_is_escaped(self, tree: Path) -> None:
        """``/*`` inside a comment is an error under the flag set the repository compiles with.

        ``-Wcomment`` is in ``-Wall`` and reports ``"/*" within comment``; with ``-Werror``
        beside it, one description ending up in every header and in the definition file takes
        the whole build down. The end marker was already defused for the other half of the
        same reason.
        """
        files = generate(tree, simple(declare("local", "A", description="opens /* inside")))
        assert "/** opens / * inside */" in files["ddd_globals.c"]
        assert "/*" not in files["ddd_globals.c"].split("/** opens", 1)[1].split("*/", 1)[0]

    def test_overlapping_markers_leave_neither_behind(self, tree: Path) -> None:
        """``/*/`` is both markers over one ``*``; defusing either one alone re-forms the other."""
        files = generate(tree, simple(declare("local", "A", description="a /*/ b")))
        assert "/** a / * / b */" in files["ddd_globals.c"]

    def test_a_unit_is_defused_like_a_description(self, tree: Path) -> None:
        files = generate(tree, simple(declare("local", "A", description="Rate", unit="/*")))
        assert "/** Rate [/ *] */" in files["ddd_globals.c"]

    def test_variables_are_grouped_by_owning_component(self, tree: Path) -> None:
        files = generate(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "X")),
                "b.ddd.json": component("B", declare("input", "X"), declare("local", "Y")),
            },
        )
        source = files["ddd_globals.c"]
        assert source.index("uint8_t X;") < source.index("uint8_t Y;")
        assert source.count("uint8_t X;") == 1


class TestTypesHeader:
    def test_enum_typedef(self, tree: Path) -> None:
        files = generate(
            tree,
            simple(
                declare(
                    "local",
                    "Mode",
                    conversion={
                        "kind": "enum",
                        "name": "Mode_t",
                        "enumerators": [
                            {"name": "OFF", "value": 0, "description": "switched off"},
                            {"name": "ON", "value": 1},
                        ],
                    },
                )
            ),
        )
        header = files["ddd_types.h"]
        assert "typedef enum\n{\n    OFF = 0, /**< switched off */\n    ON = 1\n} Mode_t;" in header

    def test_stdbool_is_included_only_when_needed_and_stdint_always(self, tree: Path) -> None:
        """``model.needs_stdint`` still answers whether a datatype of the project asks for
        the header; the example template includes it either way. Every other generated header
        includes the type header and nothing else, so a type header holding nothing leaves
        those headers holding nothing too, and ``-Wpedantic`` refuses an empty translation
        unit - which is what a project whose objects are all floating point used to get."""
        assert "#include <stdint.h>" in generate(tree, simple(declare("local", "A")))["ddd_types.h"]
        only_bool = generate(tree, simple(declare("local", "A", "boolean")))["ddd_types.h"]
        assert "#include <stdint.h>" in only_bool
        assert "#include <stdbool.h>" in only_bool
        only_floats = generate(tree, simple(declare("local", "A", "float32")))["ddd_types.h"]
        assert "#include <stdint.h>" in only_floats
        assert "#include <stdbool.h>" not in only_floats

    def test_include_guard(self, tree: Path) -> None:
        """The template writes its own guard; the model only normalises the spelling."""
        files = generate(tree, simple(declare("local", "A")))
        assert "#ifndef DDD_TYPES_H" in files["ddd_types.h"]
        assert "#endif /* DDD_TYPES_H */" in files["ddd_types.h"]


class TestComponentHeaders:
    def test_only_the_own_interface_is_visible(self, tree: Path) -> None:
        files = generate(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component(
                    "A", declare("output", "Shared"), declare("local", "Hidden")
                ),
                "b.ddd.json": component("B", declare("input", "Shared")),
            },
        )
        assert "Shared" in files["B.h"]
        assert "Hidden" not in files["B.h"]
        assert "Hidden" in files["A.h"]

    def test_sections(self, tree: Path) -> None:
        files = generate(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Out"), declare("local", "Own")),
                "b.ddd.json": component("B", declare("input", "Out")),
            },
        )
        header = files["A.h"]
        assert "extern uint8_t Out;" in header
        assert "extern uint8_t Own;" in header
        assert "/* outputs - written by A" in header
        assert "/* locals - owned exclusively by A */" in header
        assert "/* inputs" not in header

    def test_input_mentions_the_producer(self, tree: Path) -> None:
        files = generate(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("Producer", declare("output", "X")),
                "b.ddd.json": component("Consumer", declare("input", "X")),
            },
        )
        assert "extern uint8_t X;  /* produced by Producer */" in files["Consumer.h"]

    def test_an_input_is_declared_as_its_producer_defines_it(self, tree: Path) -> None:
        files = generate(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "X")),
                "b.ddd.json": component("B", declare("input", "X")),
            },
        )
        assert "extern uint8_t X;" in files["B.h"]
        assert "extern uint8_t X;" in files["A.h"]
        assert "const" not in files["B.h"]
        assert "const" not in files["ddd_globals.c"]

    def test_empty_component_gets_a_header(self, tree: Path) -> None:
        dictionary, _ = run_analysis(
            tree,
            {"project.ddd.json": project("P", "a.ddd.json"), "a.ddd.json": component("A")},
        )
        assert dictionary is not None
        files = {file.path.name: file.content for file in render_files(dictionary, tree / "gen")}
        assert "This component declares no global variable." in files["A.h"]

    def test_header_uses_the_own_condition(self, tree: Path) -> None:
        files = generate(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "X", condition="defined(F)")),
                "b.ddd.json": component("B", declare("input", "X", condition="defined(F)")),
            },
        )
        assert "#if defined(F)" in files["B.h"]


class TestWriting:
    def test_create_update_and_unchanged(self, tree: Path) -> None:
        dictionary, _ = run_analysis(tree, simple(declare("local", "A")))
        assert dictionary is not None
        first = write(render_files(dictionary, tree / "gen"))
        assert {result.status for result in first} == {WriteStatus.CREATED}
        assert (tree / "gen" / "ddd_globals.c").is_file()

        # An unchanged file is not rewritten, so its mtime survives a rerun untouched - what
        # lets a build system that watches mtimes tell the ninja module depends on skip work a
        # rerun did not actually change; see test_cmake.py. Stamped to a sentinel well in the
        # past, rather than read straight after the first write, because two writes close
        # enough together can land on the same clock tick and match by coincidence even when
        # the second one did rewrite the file - a rewrite would replace the sentinel with a
        # fresh time, which is what makes this a real check rather than a flaky one.
        generated = tree / "gen" / "ddd_globals.c"
        stamp = generated.stat().st_mtime_ns - 10**10
        os.utime(generated, ns=(stamp, stamp))
        second = write(render_files(dictionary, tree / "gen"))
        assert {result.status for result in second} == {WriteStatus.UNCHANGED}
        assert generated.stat().st_mtime_ns == stamp

        (tree / "gen" / "ddd_globals.c").write_text("stale", encoding="utf-8")
        third = write(render_files(dictionary, tree / "gen"))
        assert any(
            result.status is WriteStatus.UPDATED and result.path.name == "ddd_globals.c"
            for result in third
        )

    def test_dry_run_writes_nothing(self, tree: Path) -> None:
        dictionary, _ = run_analysis(tree, simple(declare("local", "A")))
        assert dictionary is not None
        results = write(render_files(dictionary, tree / "gen"), dry_run=True)
        assert {result.status for result in results} == {WriteStatus.CREATED}
        assert not (tree / "gen").exists()

    def test_a_file_of_the_reader_s_own_beside_a_target_is_left_alone(self, tree: Path) -> None:
        """``.tmp`` is a suffix people give real files; the staging suffix is one nobody else
        picks. A run stages over its own leftovers and deletes them on the way out, so a
        neighbour it staged onto would be silently destroyed - which is why it stages onto a
        name no artefact and no hand-written file carries."""
        dictionary, _ = run_analysis(tree, simple(declare("local", "A")))
        assert dictionary is not None
        out = tree / "gen"
        out.mkdir()
        neighbour = out / "ddd_globals.c.tmp"
        neighbour.write_text("mine\n", encoding="utf-8")
        write(render_files(dictionary, out))
        assert neighbour.read_text(encoding="utf-8") == "mine\n"

    def test_a_failed_replace_undoes_an_earlier_creation_in_the_same_call(self, tree: Path) -> None:
        """Two files; the second's target is a directory, so its replace raises. The first
        one's replace had already gone through by then - undoing it too is what makes the
        failure all-or-nothing, rather than leaving the caller with one of the two files it
        asked for and no sign that the run, as a whole, did not succeed."""
        out = tree / "gen"
        out.mkdir()
        first = GeneratedFile(out / "first.h", "first\n")
        blocked = out / "second.h"
        blocked.mkdir()
        second = GeneratedFile(blocked, "second\n")

        with pytest.raises(OSError) as excinfo:
            write([first, second])
        # The path a reader recognises is the target they asked for, not the sibling
        # temporary file the failure actually happened on.
        assert excinfo.value.filename == str(blocked)
        assert not first.path.exists()
        assert not any(out.glob("*.ddd-staging"))

    def test_a_failed_replace_leaves_an_earlier_update_in_its_new_state(self, tree: Path) -> None:
        """Unlike a fresh file, an updated one cannot be undone: its old bytes are already
        gone once its own replace has gone through, so the new content is what a later
        failure leaves behind - the one window write() documents as accepted rather than
        solved."""
        out = tree / "gen"
        out.mkdir()
        (out / "first.h").write_text("old\n", encoding="utf-8")
        first = GeneratedFile(out / "first.h", "new\n")
        blocked = out / "second.h"
        blocked.mkdir()
        second = GeneratedFile(blocked, "second\n")

        with pytest.raises(OSError):
            write([first, second])
        assert (out / "first.h").read_text(encoding="utf-8") == "new\n"
        assert not any(out.glob("*.ddd-staging"))

    def test_a_failed_write_removes_its_own_partial_temporary(
        self, tree: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A temporary is recorded for cleanup before it is written, not after: a write that
        fails once the file already exists on disk - a full disk partway through, an I/O
        error - used to leave that staging file behind, unrecorded and so never unlinked."""
        out = tree / "gen"
        out.mkdir()
        first = GeneratedFile(out / "first.h", "first\n")
        second = GeneratedFile(out / "second.h", "second\n")
        real_write_bytes = Path.write_bytes

        def flaky(path: Path, data: bytes) -> int:
            if path.name == "second.h.ddd-staging":
                real_write_bytes(path, data)
                raise OSError(errno.ENOSPC, "No space left on device")
            return real_write_bytes(path, data)

        monkeypatch.setattr(Path, "write_bytes", flaky)

        with pytest.raises(OSError) as excinfo:
            write([first, second])
        assert excinfo.value.filename == str(second.path)
        assert not first.path.exists()
        assert not second.path.exists()
        assert not any(out.glob("*.ddd-staging"))

    def test_a_failed_replace_names_only_the_real_target(
        self, tree: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failed ``Path.replace`` sets ``filename`` to the staging file it renamed from and
        ``filename2`` to the target it could not replace - forced here, rather than provoked,
        because which ``OSError`` a blocked rename actually raises reads differently by
        platform. ``write()`` overwrites ``filename`` with the target, so a reader sees the
        path they typed, and drops ``filename2`` rather than leave it naming that same target
        a second time; pinning ``str(error)`` is what would show a regression to either half
        as a diff, rather than only to a ``.filename`` assertion a stray ``.filename2``
        would not affect."""
        out = tree / "gen"
        out.mkdir()
        first = GeneratedFile(out / "first.h", "first\n")
        second = GeneratedFile(out / "second.h", "second\n")
        real_replace = Path.replace

        def refuse(path: Path, target: Path) -> Path:
            if target.name == "second.h":
                error = OSError(errno.EACCES, "Access is denied", str(path))
                error.filename2 = str(target)
                raise error
            return real_replace(path, target)

        monkeypatch.setattr(Path, "replace", refuse)

        with pytest.raises(OSError) as excinfo:
            write([first, second])
        assert str(excinfo.value) == f"[Errno 13] Access is denied: {str(second.path)!r}"

    def test_files_use_unix_line_endings(self, tree: Path) -> None:
        dictionary, _ = run_analysis(tree, simple(declare("local", "A")))
        assert dictionary is not None
        write(render_files(dictionary, tree / "gen"))
        assert b"\r\n" not in (tree / "gen" / "ddd_globals.c").read_bytes()

    def test_a2l_can_be_switched_off(self, tree: Path) -> None:
        files = generate(tree, simple(declare("local", "A")), emit_a2l=False)
        assert not any(name.endswith(".a2l") for name in files)

    def test_a_component_may_not_overwrite_a_shared_file(self, tree: Path) -> None:
        """A component named after a shared file is refused, and the message says who by."""
        with pytest.raises(ValueError, match=r"c backend would write 'ddd_types\.h' twice"):
            generate(tree, simple(declare("local", "A"), name="ddd_types"))


def pair(tree: Path, *components: str) -> dict[str, Any]:
    """A project including one component file per name, each declaring one local of its own."""
    return {
        "project.ddd.json": project("P", *(f"{name.lower()}.ddd.json" for name in components)),
        **{
            f"{name.lower()}.ddd.json": component(name, declare("local", f"{name}Value"))
            for name in components
        },
    }


class TestTheManifest:
    """``generate`` owns its output directory: it records what it wrote and removes the rest.

    The defect this closes: a component dropped from a project kept its generated header, on
    every component's include path, so a translation unit went on compiling against the
    interface of a component the image no longer contains.
    """

    def rendered(self, tree: Path, *components: str, **options: Any) -> list[GeneratedFile]:
        dictionary, bag = run_analysis(tree, pair(tree, *components))
        assert dictionary is not None, [entry.render() for entry in bag]
        return render_files(dictionary, tree / "gen", **options)

    def owning(self, tree: Path, *artefacts: str) -> Manifest:
        return Manifest(tree / "gen", artefacts or ("c", "a2l"))

    def entries(self, tree: Path) -> dict[str, str]:
        text = (tree / "gen" / MANIFEST_NAME).read_text(encoding="utf-8")
        return dict(json.loads(text)["files"])

    def test_a_header_of_a_component_that_is_gone_is_removed(self, tree: Path) -> None:
        """The review's trigger, under the writer: B leaves the project and B.h leaves with it."""
        write(self.rendered(tree, "A", "B"), manifest=self.owning(tree))
        assert (tree / "gen" / "B.h").is_file()
        assert "B.h" in self.entries(tree)

        results = write(self.rendered(tree, "A"), manifest=self.owning(tree))
        assert not (tree / "gen" / "B.h").exists()
        assert (tree / "gen" / "A.h").is_file()
        assert "B.h" not in self.entries(tree)
        assert WriteResult(tree / "gen" / "B.h", WriteStatus.REMOVED) in results

    def test_a_file_the_manifest_does_not_name_is_never_removed(self, tree: Path) -> None:
        """Only what this tool wrote: a file of the project's own beside the artefacts - a
        checked-in header, a note, an object file of an earlier build - is not ours to delete."""
        write(self.rendered(tree, "A", "B"), manifest=self.owning(tree))
        foreign = tree / "gen" / "handwritten.h"
        foreign.write_text("mine\n", encoding="utf-8")
        write(self.rendered(tree, "A"), manifest=self.owning(tree))
        assert foreign.read_text(encoding="utf-8") == "mine\n"
        assert "handwritten.h" not in self.entries(tree)

    def test_an_artefact_this_run_does_not_produce_keeps_its_files(self, tree: Path) -> None:
        """``ddd generate a2l -o <the same directory>`` regenerates the a2l after the link
        "without touching the sources the image was built from" (section 6), so a run removes
        the stale files of the artefacts it produced and of no others."""
        write(self.rendered(tree, "A", "B"), manifest=self.owning(tree))
        dictionary, _ = run_analysis(tree, pair(tree, "A"))
        assert dictionary is not None
        only_a2l = render(dictionary, [A2lBackend(A2lOptions())], tree / "gen")
        write(only_a2l, manifest=self.owning(tree, "a2l"))
        assert (tree / "gen" / "B.h").is_file(), "the c artefact was not produced by that run"
        assert self.entries(tree)["B.h"] == "c"

    def test_a_dry_run_removes_nothing_and_records_nothing(self, tree: Path) -> None:
        write(self.rendered(tree, "A", "B"), manifest=self.owning(tree))
        before = (tree / "gen" / MANIFEST_NAME).read_bytes()
        results = write(self.rendered(tree, "A"), manifest=self.owning(tree), dry_run=True)
        assert (tree / "gen" / "B.h").is_file()
        assert (tree / "gen" / MANIFEST_NAME).read_bytes() == before
        assert WriteResult(tree / "gen" / "B.h", WriteStatus.REMOVED) in results

    def test_a_run_that_changes_nothing_writes_nothing(self, tree: Path) -> None:
        """The mtime promise reaches the record as well: a rerun that removes nothing and
        rewrites no artefact leaves the manifest untouched too."""
        write(self.rendered(tree, "A", "B"), manifest=self.owning(tree))
        record = tree / "gen" / MANIFEST_NAME
        stamp = record.stat().st_mtime_ns - 10**10
        os.utime(record, ns=(stamp, stamp))
        results = write(self.rendered(tree, "A", "B"), manifest=self.owning(tree))
        assert {result.status for result in results} == {WriteStatus.UNCHANGED}
        assert record.stat().st_mtime_ns == stamp

    def test_a_write_that_fails_removes_nothing_and_keeps_the_record(self, tree: Path) -> None:
        """The record is renamed last of all, so a run that could not write its artefacts
        leaves the previous one describing what is still on disk."""
        write(self.rendered(tree, "A", "B"), manifest=self.owning(tree))
        before = (tree / "gen" / MANIFEST_NAME).read_bytes()
        blocked = tree / "gen" / "ddd_globals.c"
        blocked.unlink()
        blocked.mkdir()
        with pytest.raises(OSError):
            write(self.rendered(tree, "A"), manifest=self.owning(tree))
        assert (tree / "gen" / "B.h").is_file()
        assert (tree / "gen" / MANIFEST_NAME).read_bytes() == before

    def test_a_removal_that_fails_is_named_and_keeps_the_record(
        self, tree: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A stale file that cannot be deleted - held open, or read only - fails the run and
        stays in the record, so the next run tries again rather than losing track of it."""
        write(self.rendered(tree, "A", "B"), manifest=self.owning(tree))
        before = (tree / "gen" / MANIFEST_NAME).read_bytes()
        real_unlink = Path.unlink

        def refuse(path: Path, **keywords: Any) -> None:
            if path.name == "B.h":
                raise OSError(errno.EACCES, "Access is denied", str(path))
            real_unlink(path, **keywords)

        monkeypatch.setattr(Path, "unlink", refuse)
        with pytest.raises(RemovalError) as excinfo:
            write(self.rendered(tree, "A"), manifest=self.owning(tree))
        assert excinfo.value.filename == str(tree / "gen" / "B.h")
        assert (tree / "gen" / MANIFEST_NAME).read_bytes() == before
        assert not any((tree / "gen").glob("*.ddd-staging"))

    @pytest.mark.parametrize(
        "broken",
        [
            pytest.param("[]", id="not an object"),
            pytest.param('{"format": 99, "files": {}}', id="a format this version has not got"),
            pytest.param('{"format": 1}', id="no files at all"),
            pytest.param('{"format": 1, "files": {"B.h": 7}}', id="a file recorded under no name"),
            pytest.param("{ not json", id="not json"),
        ],
    )
    def test_a_record_this_version_cannot_read_removes_nothing(
        self, tree: Path, broken: str
    ) -> None:
        """A manifest a newer DDD wrote, or a hand edit broke, is one this run declines rather
        than misreads - and it is rewritten, so the next run owns the directory again. It is
        read to decide what to *delete*, which is the argument for reading it strictly."""
        write(self.rendered(tree, "A", "B"), manifest=self.owning(tree))
        (tree / "gen" / MANIFEST_NAME).write_text(broken, encoding="utf-8")
        write(self.rendered(tree, "A"), manifest=self.owning(tree))
        assert (tree / "gen" / "B.h").is_file()
        assert set(self.entries(tree)) >= {"A.h", "ddd_globals.c"}

    def test_a_recorded_path_outside_the_directory_is_never_removed(self, tree: Path) -> None:
        """The record names files under the directory the run owns; anything else in it - a
        hand edit, an absolute path - names something this run has no claim on."""
        write(self.rendered(tree, "A"), manifest=self.owning(tree))
        outside = tree / "outside.h"
        outside.write_text("mine\n", encoding="utf-8")
        record = tree / "gen" / MANIFEST_NAME
        written = json.loads(record.read_text(encoding="utf-8"))
        written["files"]["../outside.h"] = "c"
        record.write_text(json.dumps(written), encoding="utf-8")
        write(self.rendered(tree, "A"), manifest=self.owning(tree))
        assert outside.read_text(encoding="utf-8") == "mine\n"

    def test_the_record_is_not_reported_as_a_generated_file(self, tree: Path) -> None:
        """It is bookkeeping rather than an artefact: what a run reports is what it generated."""
        results = write(self.rendered(tree, "A"), manifest=self.owning(tree))
        assert (tree / "gen" / MANIFEST_NAME).is_file()
        assert MANIFEST_NAME not in {result.path.name for result in results}


class TestStringInitialisers:
    """A string init is a c string literal; c fills the rest of the array with zero."""

    def string(
        self, init: object, *, datatype: str = "uint8", kind: str = "value_block", size: int = 16
    ) -> dict[str, Any]:
        return simple(
            declare(
                "local",
                "Label",
                datatype,
                kind=kind,
                conversion={"kind": "string"},
                dimensions=[size],
                init=init,
            )
        )

    def test_a_string_init_is_a_string_literal(self, tree: Path) -> None:
        files = generate(tree, self.string("V1.2.3"))
        assert 'const uint8_t Label[16] = "V1.2.3";' in files["ddd_globals.c"]

    def test_the_literal_escapes_what_c_reads_specially(self, tree: Path) -> None:
        """A quote, a backslash, and ``?`` - two of which before ``=`` form a trigraph."""
        files = generate(tree, self.string('a "b" \\ ??=', size=32))
        assert r'const uint8_t Label[32] = "a \"b\" \\ \?\?=";' in files["ddd_globals.c"]

    def test_the_empty_string_is_an_explicit_initialiser(self, tree: Path) -> None:
        files = generate(tree, self.string("", kind="measurement"))
        assert 'uint8_t Label[16] = "";' in files["ddd_globals.c"]

    def test_a_list_init_on_a_string_object_renders_as_bytes(self, tree: Path) -> None:
        files = generate(tree, self.string([86, 49, 0, 0], size=4))
        assert "const uint8_t Label[4] = { 86U, 49U, 0U, 0U };" in files["ddd_globals.c"]

    def test_a_signed_byte_string_takes_the_same_literal(self, tree: Path) -> None:
        files = generate(tree, self.string("abc", datatype="sint8", size=8))
        assert 'const int8_t Label[8] = "abc";' in files["ddd_globals.c"]


class TestRetainingADefinitionAGarbageCollectingLinkWouldDrop:
    """``DDD_RETAIN``, which the example ``ddd_globals.c`` template puts before every definition:
    empty unless the project defines it, and then what keeps the object under ``--gc-sections``."""

    RETAIN = "__attribute__((used, retain))"

    @staticmethod
    def generated(directory: Path) -> Path:
        from ddd.cli import main

        arguments = ["generate", "c", str(DEMO), "-o", str(directory), "-t"]
        assert main([*arguments, str(EXAMPLES / "templates")]) == 0
        return directory / "ddd_globals.c"

    @staticmethod
    def compiler() -> str:
        gcc = shutil.which("gcc")
        assert gcc, "no gcc on the path: the objects a link keeps are counted from its output"
        return gcc

    def run(self, *command: str | Path) -> str:
        done = subprocess.run(
            [str(part) for part in command], capture_output=True, text=True, check=False
        )
        assert done.returncode == 0, done.stderr
        return done.stdout

    def kept(self, tmp_path: Path, *flags: str) -> tuple[set[str], set[str], bytes, str]:
        """Link the generated definitions with ``-fdata-sections`` and ``--gc-sections`` against
        a ``main`` that references none of them: the objects the unit defines, the ones the image
        keeps, the image's first bytes, and its path."""
        source = self.generated(tmp_path / "gen")
        main_c = tmp_path / "main.c"
        main_c.write_text("int main(void) { return 0; }\n", encoding="utf-8")
        include = f"-I{DEMO.parent / 'include'}"
        gcc = self.compiler()
        self.run(gcc, "-g", "-O2", "-fdata-sections", include, f"-I{source.parent}", *flags,
                 "-c", source, "-o", tmp_path / "globals.o")  # fmt: skip
        self.run(gcc, "-g", "-O2", "-c", main_c, "-o", tmp_path / "main.o")
        image = tmp_path / "image.exe"
        self.run(gcc, "-Wl,--gc-sections", tmp_path / "main.o", tmp_path / "globals.o", "-o", image)

        def objects(path: Path) -> set[str]:
            symbols = (line.split() for line in self.run("nm", path).splitlines())
            return {s[2].removeprefix("_") for s in symbols if len(s) == 3 and s[1] in "BbDdRrGgSs"}

        defined = objects(tmp_path / "globals.o")
        return defined, defined & objects(image), image.read_bytes()[:4], str(image)

    def test_the_macro_keeps_every_definition_on_elf_and_no_more_than_the_empty_one_on_pe(
        self, tmp_path: Path
    ) -> None:
        """Measured on ELF with gcc 15.2.0 and binutils 2.46: the empty macro and ``used`` alone
        keep nothing, and ``used, retain`` keeps every object. On PE gcc ignores ``retain``, so the
        macro keeps what the empty one does, whatever the linker leaves of that: no count is held
        there, since it is the linker's."""
        defined, empty, magic, _ = self.kept(tmp_path / "empty")
        _, used, _, _ = self.kept(tmp_path / "used", "-DDDD_RETAIN=__attribute__((used))")
        _, retained, _, _ = self.kept(tmp_path / "retain", f"-DDDD_RETAIN={self.RETAIN}")
        version = self.run(self.compiler(), "--version").splitlines()[0]
        met = f"{version}: the empty macro kept {sorted(empty)}, used {sorted(used)}"
        assert len(defined) >= 20, met
        if magic == b"\x7fELF":
            assert empty == used == set(), met
            assert retained == defined, f"{met}, used and retain {sorted(retained)}"
        else:
            assert magic[:2] == b"MZ", met
            assert used == retained == empty, f"{met}, used and retain {sorted(retained)}"

    def test_the_a2l_of_an_image_without_them_says_the_addresses_are_missing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """On an ELF image the a2l run warns ``address-missing``; the reader reads no other
        format, so what a PE leg holds is that the image it linked is a PE one."""
        from ddd.cli import main

        _, _, magic, image = self.kept(tmp_path / "empty")
        if magic != b"\x7fELF":
            assert magic[:2] == b"MZ", "the linked image is neither an ELF nor a PE one"
            return
        arguments = ["generate", "a2l", str(DEMO), "--image", image, "-o", str(tmp_path / "a2l")]
        main(arguments)
        assert "warning[address-missing]" in capsys.readouterr().err

    def test_the_macro_defaults_to_nothing_and_the_c_compiles_as_it_did(
        self, tmp_path: Path
    ) -> None:
        """Compiled to assembly, the unit with ``DDD_RETAIN`` before each definition is the unit
        without it, byte for byte."""
        source = self.generated(tmp_path / "with")
        text = source.read_text(encoding="utf-8")
        assert text.count("DDD_RETAIN ") >= 20
        without = tmp_path / "without"
        without.mkdir()
        (without / "ddd_globals.c").write_text(
            text.replace("DDD_RETAIN ", ""), encoding="utf-8", newline="\n"
        )
        for directory in (source.parent, without):
            self.run(
                self.compiler(), "-S", "-O2", "-g0", "-fdata-sections", f"-I{source.parent}",
                f"-I{DEMO.parent / 'include'}", directory / "ddd_globals.c",
                "-o", directory / "out.s",
            )  # fmt: skip
        assert (source.parent / "out.s").read_bytes() == (without / "out.s").read_bytes()


CI_C_FLAGS = [
    "-std=c11",
    "-Wall",
    "-Wextra",
    "-Wpedantic",
    "-Werror",
    "-Wconversion",
    "-Wshadow",
    "-Wcast-qual",
    "-Wstrict-prototypes",
]
"""The warning set ``docker/compile.sh`` verifies the generated c with."""


def compiled(directory: Path, source: str) -> subprocess.CompletedProcess[str]:
    """Compile ``source`` as a translation unit beside the generated files, under the CI flags."""
    gcc = shutil.which("gcc")
    assert gcc, "no gcc on the path: the generated c is proved by compiling it"
    unit = directory / "unit.c"
    unit.write_text(source, encoding="utf-8")
    return subprocess.run(
        [gcc, *CI_C_FLAGS, f"-I{directory}", "-c", str(unit), "-o", os.devnull],
        capture_output=True,
        text=True,
        check=False,
    )


class TestOneGuardForOneComponent:
    """Two components must not open one include guard: a file including both headers finds the
    second one preprocessed away, and ``compile.sh`` compiles each header alone."""

    @staticmethod
    def two(tree: Path, first: str, second: str) -> dict[str, str]:
        return generate(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component(first, declare("output", "FromFirst")),
                "b.ddd.json": component(second, declare("output", "FromSecond")),
            },
        )

    @staticmethod
    def guard_of(header: str) -> str:
        return header.split("#ifndef ", 1)[1].split("\n", 1)[0]

    def test_a_trailing_underscore_has_a_prefix_of_its_own(self, tree: Path) -> None:
        files = self.two(tree, "Valve", "Valve_")
        assert self.guard_of(files["Valve.h"]) == "DDD_COMPONENT_VALVE_H"
        assert self.guard_of(files["Valve_.h"]) == "DDD_COMPONENTS_TRAILING_VALVE_H"

    def test_a_leading_underscore_has_a_prefix_of_its_own(self, tree: Path) -> None:
        files = self.two(tree, "valve", "_valve")
        assert self.guard_of(files["valve.h"]) == "DDD_COMPONENT_VALVE_H"
        assert self.guard_of(files["_valve.h"]) == "DDD_COMPONENTS_LEADING_VALVE_H"

    def test_both_edges_have_a_prefix_of_their_own(self, tree: Path) -> None:
        files = self.two(tree, "_valve_", "valve")
        assert self.guard_of(files["_valve_.h"]) == "DDD_COMPONENTS_BOTH_VALVE_H"

    def test_no_two_of_these_names_share_a_guard(self, tree: Path) -> None:
        names = ["v", "_v", "v_", "_v_", "v_w", "_v_w", "v_w_", "_v_w_", "leading_v", "both_v"]
        guards = [component_guard(name) for name in names]
        assert len(set(guards)) == len(names)

    def test_a_file_including_both_headers_compiles_under_the_ci_flags(self, tree: Path) -> None:
        files = self.two(tree, "Valve", "Valve_")
        directory = tree / "gen"
        directory.mkdir()
        for name, content in files.items():
            (directory / name).write_text(content, encoding="utf-8")
        done = compiled(
            directory,
            '#include "Valve.h"\n#include "Valve_.h"\n'
            "unsigned char read_both(void) { return (unsigned char)(FromFirst + FromSecond); }\n",
        )
        assert done.returncode == 0, done.stderr

    def test_a_name_with_no_edge_underscore_keeps_the_guard_it_had(self, tree: Path) -> None:
        files = self.two(tree, "ValveHub", "Valve_Hub")
        assert self.guard_of(files["ValveHub.h"]) == "DDD_COMPONENT_VALVEHUB_H"
        assert self.guard_of(files["Valve_Hub.h"]) == "DDD_COMPONENT_VALVE_HUB_H"

    def test_no_guard_is_a_reserved_identifier(self, tree: Path) -> None:
        """The screen the analysis applies to a component's own name: a double underscore
        anywhere, or an underscore and a capital at the start."""
        for name in ("valve", "_valve", "valve_", "_v_", "v_w", "_v_w_"):
            files = self.two(tree / name, name, "Other")
            guard = self.guard_of(files[f"{name}.h"])
            assert not is_reserved_identifier(guard), guard
            assert re.fullmatch(r"[A-Z][A-Z0-9_]*", guard), guard

    def test_the_shared_headers_keep_theirs(self, tree: Path) -> None:
        files = self.two(tree, "Valve", "Valve_")
        assert self.guard_of(files["ddd_types.h"]) == "DDD_TYPES_H"
        assert self.guard_of(files["ddd_globals.h"]) == "DDD_GLOBALS_H"


class TestADescriptionEndingInATrigraph:
    """``??/`` is a backslash to a compiler that reads trigraphs, and at the end of a line it
    splices the next one: ``-Wtrigraphs``, which the CI flags turn into an error, stops it.
    The component's description ends a line in the component header and in the file of
    definitions."""

    @pytest.mark.parametrize("ending", ["=", "(", "/", ")", "'", "<", "!", ">", "-"])
    def test_a_component_description_ending_in_any_trigraph_compiles_under_the_ci_flags(
        self, tree: Path, ending: str
    ) -> None:
        description = f"Reads??{ending}"
        files = generate(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("C", declare("output", "Value"), description=description),
            },
        )
        directory = tree / "gen"
        directory.mkdir()
        for name, content in files.items():
            (directory / name).write_text(content, encoding="utf-8")
        for unit in (
            '#include "C.h"\n',
            '#include "ddd_globals.h"\n',
            '#include "ddd_globals.c"\n',
        ):
            done = compiled(directory, unit)
            assert done.returncode == 0, done.stderr
        assert f"Reads? ?{ending}\n" in files["C.h"]
        assert all(
            description not in content
            for name, content in files.items()
            if name.endswith((".c", ".h"))
        )
