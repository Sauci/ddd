"""A dictionary this version dumps reads back, a leaf's composed display identifier included.

A display identifier stated on a structure member stands for that member's own segment of the
path of every leaf below it, so ``V[1].j.b`` with ``j`` displayed ``J`` is published as
``V[1].J.b``. The leaf's ``a2l`` block carried that path in the field of the block a project
writes, one plain identifier, and built it without validation: the dump wrote what its own reader
refused, and a project stating such an identifier could not archive a baseline. The leaf's block
has a model of its own, whose display identifier is a path, and the dictionary is format 10. The
block a project writes keeps its one plain identifier.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from conftest import checks, component, declare, project, run_analysis, struct_type, types
from ddd.cli import EXIT_OK, main
from ddd.diagnostics import DiagnosticBag
from ddd.ir import DICTIONARY_FORMAT, DataDictionary
from ddd.loading import load_dictionary
from ddd.models import A2lObjectOptions, LeafA2lOptions

FINDING = re.compile(r"\b(?:error|warning|info)\[")

MEMBERS_STATING_A_BLOCK: dict[str, Any] = {
    "project.ddd.json": project("P", "types.ddd.json", "a.ddd.json"),
    "a.ddd.json": component("A", declare("local", "V", typename="Out_t", id="abcdefghjkmn")),
    "types.ddd.json": types(
        struct_type(
            "In_t",
            {"name": "b", "member": "value", "datatype": "uint8", "conversion": {}},
            {"name": "c", "member": "value", "datatype": "uint8", "conversion": {}},
        ),
        struct_type(
            "Out_t",
            {"name": "v", "member": "value", "datatype": "uint8", "conversion": {}},
            {
                "name": "j",
                "member": "value",
                "typename": "In_t",
                "a2l": {"format": "%6.2", "display_identifier": "J"},
            },
            {"name": "k", "member": "value", "typename": "In_t", "a2l": {"export": False}},
        ),
    ),
}
"""A structure whose member ``j``, over two leaves, gives them its format and display
identifier, while its member ``k``, over two, leaves them out of the a2l: the project of the
release note's entry."""


def dumped(tree: Path, files: dict[str, Any]) -> tuple[DataDictionary, Path]:
    dictionary, bag = run_analysis(tree, files)
    assert dictionary is not None, [finding.render() for finding in bag]
    target = tree / "baseline.json"
    target.write_text(dictionary.model_dump_json(indent=2), encoding="utf-8")
    return dictionary, target


def read_back(path: Path) -> DataDictionary:
    bag = DiagnosticBag()
    loaded = load_dictionary(path, bag)
    assert loaded is not None, [finding.render() for finding in bag]
    assert checks(bag) == []
    return loaded


class TestADumpReadsBack:
    def test_a_baseline_this_version_dumps_checks_and_compares_clean(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The run as a delivery makes it: ``ddd dump`` archives the baseline, and the project,
        unchanged, is checked and compared against it."""
        for name, content in MEMBERS_STATING_A_BLOCK.items():
            (tree / name).write_text(json.dumps(content), encoding="utf-8")
        baseline, root = tree / "baseline.json", tree / "project.ddd.json"
        assert main(["dump", str(root), "-o", str(baseline)]) == EXIT_OK
        leaves = json.loads(baseline.read_text(encoding="utf-8"))["leaves"]
        shown = {leaf["path"]: leaf["a2l"]["display_identifier"] for leaf in leaves}
        assert (shown["V.j.b"], shown["V.j.c"]) == ("V.J.b", "V.J.c")
        capsys.readouterr()

        for command in (
            ["check", "--baseline", str(baseline), "--strict", str(root)],
            ["compare", str(baseline), str(root)],
        ):
            status = main(command)
            printed = capsys.readouterr()
            assert status == EXIT_OK, printed.err
            assert not FINDING.search(printed.out + printed.err), printed.err

    def test_the_indices_of_arrays_of_structures_read_back(self, tree: Path) -> None:
        """Every part of the path keeps its index: an array of the variable's type, and an
        array of the member's, each displayed."""
        files = {
            "project.ddd.json": project("P", "types.ddd.json", "a.ddd.json"),
            "a.ddd.json": component("A", declare("local", "V", typename="Out_t", dimensions=[2])),
            "types.ddd.json": types(
                struct_type(
                    "In_t", {"name": "b", "member": "value", "datatype": "uint8", "conversion": {}}
                ),
                struct_type(
                    "Mid_t",
                    {
                        "name": "n",
                        "member": "value",
                        "typename": "In_t",
                        "a2l": {"display_identifier": "Inner"},
                    },
                ),
                struct_type(
                    "Out_t",
                    {
                        "name": "j",
                        "member": "value",
                        "typename": "Mid_t",
                        "dimensions": [2],
                        "a2l": {"display_identifier": "J"},
                    },
                ),
            ),
        }
        dictionary, target = dumped(tree, files)
        loaded = read_back(target)
        assert loaded == dictionary
        shown = {leaf.path: leaf.a2l.display_identifier for leaf in loaded.leaves}
        assert shown == {
            "V[0].j[0].n.b": "V[0].J[0].Inner.b",
            "V[0].j[1].n.b": "V[0].J[1].Inner.b",
            "V[1].j[0].n.b": "V[1].J[0].Inner.b",
            "V[1].j[1].n.b": "V[1].J[1].Inner.b",
        }

    def test_a_dictionary_of_format_9_with_a_leaf_reads_back_as_before(self, tree: Path) -> None:
        """Format 10 widens what a leaf's display identifier may hold and adds no field, so a
        format 9 dictionary, whose leaves hold at most one plain identifier, is read as it was."""
        files = {
            "project.ddd.json": project("P", "types.ddd.json", "a.ddd.json"),
            "a.ddd.json": component("A", declare("local", "V", typename="S_t")),
            "types.ddd.json": types(
                struct_type(
                    "S_t",
                    {
                        "name": "raw",
                        "member": "value",
                        "datatype": "uint8",
                        "conversion": {},
                        "a2l": {"display_identifier": "Raw"},
                    },
                )
            ),
        }
        dictionary, target = dumped(tree, files)
        document = json.loads(target.read_text(encoding="utf-8"))
        assert DICTIONARY_FORMAT == document["format"] == 10
        document["format"] = 9
        target.write_text(json.dumps(document), encoding="utf-8")
        loaded = read_back(target)
        assert loaded.format == 9
        assert loaded.leaves == dictionary.leaves
        assert loaded.leaves[0].a2l.display_identifier == "Raw"


class TestTheTwoBlocks:
    @pytest.mark.parametrize(
        "path", ["V.J.b", "V[1].J.b", "V.J[0].Inner.x", "Inlet.cells[1].J.v", "A[0][1].B", "Raw"]
    )
    def test_a_leaf_block_takes_a_path_of_identifiers(self, path: str) -> None:
        assert LeafA2lOptions(display_identifier=path).display_identifier == path

    @pytest.mark.parametrize(
        "spelled", ["V..b", "V.J.", ".J", "1V.b", "V[x].b", "V[].b", "V.J b", "V-J", ""]
    )
    def test_a_leaf_block_refuses_what_no_path_is(self, spelled: str) -> None:
        with pytest.raises(ValidationError):
            LeafA2lOptions(display_identifier=spelled)

    def test_a_leaf_block_is_held_to_no_length(self) -> None:
        """A variable kept out of the a2l is not held by its checks, and its leaves are composed
        all the same, so a dictionary can carry a path past ``MAX_IDENT`` 1024, or a part past
        ``MAX_PARTIAL_IDENT`` 128, that nothing reported; it has to read back."""
        part = "m" * 126 + "[10]"
        path = "V.D." + ".".join([part] * 9) + ".v"
        assert len(path) > 1024 and len(part) > 128
        assert LeafA2lOptions(display_identifier=path).display_identifier == path

    def test_the_block_a_project_writes_keeps_one_plain_identifier(self, tree: Path) -> None:
        """A member's or a definition's display identifier is one identifier, as it was."""
        with pytest.raises(ValidationError):
            A2lObjectOptions(display_identifier="V.J.b")
        files = {
            "project.ddd.json": project("P", "a.ddd.json"),
            "a.ddd.json": component(
                "A", declare("local", "X", a2l={"display_identifier": "X.Shown"})
            ),
        }
        _, bag = run_analysis(tree, files)
        assert checks(bag) == ["schema"]

    def test_the_leaf_block_is_built_with_validation(self) -> None:
        """What the analysis writes on a leaf is held to the leaf's model as it is made, so that
        the dump never carries what its reader refuses."""
        from ddd.analysis import _A2lScope, _Analysis
        from ddd.ir import ResolvedInstance
        from ddd.models import IdentityConversion, Member

        member = Member.model_validate(
            {"name": "b", "member": "value", "datatype": "uint8", "conversion": {}}
        )
        instance = ResolvedInstance(name="V", type="S_t", kind="measurement")
        with pytest.raises(ValidationError):
            _Analysis._leaf_a2l(instance, member, IdentityConversion(), _A2lScope(shown="V..J"))
        block = _Analysis._leaf_a2l(instance, member, IdentityConversion(), _A2lScope(shown="V.J"))
        assert type(block) is LeafA2lOptions
        assert block.display_identifier == "V.J.b"
