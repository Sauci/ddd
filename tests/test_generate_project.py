"""``tools/generate_project.py``: a project of a chosen size, clean or findings-heavy, and the
same bytes every time it is asked for the same one."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest
from generate_project import SHAPES, generate, main

from ddd.lsp.diagnostics import run_project


def interfaces(directory: Path) -> list[list[dict[str, object]]]:
    return [
        json.loads(path.read_text(encoding="utf-8"))["component"]["interface"]
        for path in sorted((directory / "components").glob("*.ddd.json"))
    ]


@pytest.mark.parametrize("shape", SHAPES)
def test_a_project_generated_with_the_defaults_has_no_finding(tmp_path: Path, shape: str) -> None:
    """What makes it a project a real one could be: an id on every output, a unit its
    vocabulary lists, a reader for every output, and a reader stating what its producer states."""
    made = generate(tmp_path / "p", 1200, shape)
    assert [
        f"{found.check}: {found.message}" for found in run_project(made.project).bag.sorted
    ] == []


@pytest.mark.parametrize(
    ("shape", "components"), [("many", 100), ("large", 30), ("mixed", 15 + 50)]
)
def test_each_shape_shares_the_declarations_between_its_components(
    tmp_path: Path, shape: str, components: int
) -> None:
    made = generate(tmp_path / "p", 3000, shape)
    written = interfaces(tmp_path / "p")
    assert (made.components, made.declarations) == (components, 3000)
    assert (len(written), sum(len(interface) for interface in written)) == (components, 3000)


def test_the_many_shape_is_components_of_thirty(tmp_path: Path) -> None:
    generate(tmp_path / "p", 3000, "many")
    assert {len(interface) for interface in interfaces(tmp_path / "p")} == {30}


def test_a_total_that_even_sizes_cannot_make_is_rounded_down(tmp_path: Path) -> None:
    assert generate(tmp_path / "p", 1001, "large").declarations == 1000


def test_no_component_reads_its_own_output(tmp_path: Path) -> None:
    generate(tmp_path / "p", 1200, "mixed")
    for interface in interfaces(tmp_path / "p"):
        own = {entry["definition"]["name"] for entry in interface if entry["scope"] == "output"}
        read = {entry["definition"]["name"] for entry in interface if entry["scope"] == "input"}
        assert not own & read


def test_the_many_shape_lays_its_reader_a_layer_away(tmp_path: Path) -> None:
    """The canvas lays the "many" shape out in layers about thirty components across, rather
    than as one chain as deep as the project is long: of sixty components, the first one's
    output is read thirty components later, not by its very next neighbour."""
    generate(tmp_path / "p", 1800, "many")
    written = interfaces(tmp_path / "p")

    def reads_the_first_output(component: list[dict[str, object]]) -> bool:
        return any(
            entry["scope"] == "input" and entry["definition"]["name"] == "C00000_O0000"
            for entry in component
        )

    assert reads_the_first_output(written[30])
    assert not reads_the_first_output(written[1])


def test_the_findings_asked_for_are_the_findings_reported(tmp_path: Path) -> None:
    """1200 declarations in the "many" shape are 600 outputs and 600 inputs. Half the inputs
    written as outputs: 300 of them, each leaving its output unread and unread itself - 600 -
    and every one of the 900 outputs without an id."""
    made = generate(tmp_path / "p", 1200, "many", missing_ids=1.0, unread=0.5)
    reported = Counter(found.check for found in run_project(made.project).bag.sorted)
    assert (made.unnamed, made.unread) == (900, 600)
    assert reported == Counter({"missing-id": 900, "unused-output": 600})


def test_a_density_is_spread_over_the_whole_project(tmp_path: Path) -> None:
    """Not bunched at its start: every component of a tenth-density project has an output
    without an id, never one component with all of them."""
    generate(tmp_path / "p", 3000, "many", missing_ids=0.1)
    unnamed = [
        sum(
            1
            for entry in interface
            if entry["scope"] == "output" and "id" not in entry["definition"]
        )
        for interface in interfaces(tmp_path / "p")
    ]
    assert sum(unnamed) == 150
    assert max(unnamed) <= 2


def test_the_ids_are_scattered_not_sequential(tmp_path: Path) -> None:
    """Neighbouring declarations do not read alike: the first component's second and third
    outputs, numbered one apart, do not have ids one apart either, nor alike beyond the
    digits these two small numbers leave untouched."""
    generate(tmp_path / "p", 1200, "many")
    ids = {
        entry["definition"]["name"]: entry["definition"]["id"]
        for entry in interfaces(tmp_path / "p")[0]
        if entry["scope"] == "output"
    }
    assert ids["C00000_O0001"] == "vq8rdscaaaaa"
    assert ids["C00000_O0002"] == "c567g8eaaaaa"


def test_the_same_arguments_write_the_same_bytes(tmp_path: Path) -> None:
    def written(root: Path) -> dict[Path, bytes]:
        return {path.relative_to(root): path.read_bytes() for path in sorted(root.rglob("*.json"))}

    generate(tmp_path / "one", 1200, "mixed", missing_ids=0.3, unread=0.2)
    generate(tmp_path / "two", 1200, "mixed", missing_ids=0.3, unread=0.2)
    assert written(tmp_path / "one") == written(tmp_path / "two")


def test_every_file_is_written_with_the_same_line_ending_on_every_os(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``write_text``'s own default would translate every "\\n" to ``os.linesep`` on write,
    which is "\\r\\n" on Windows - a byte this generator would otherwise write differently
    there, contradicting its own docstring's "the same bytes ... on every machine". Checked on
    the call itself, which this platform's own ``os.linesep`` ("\\n") cannot: every file this
    machine writes would read back with none either way, so reading them back proves nothing
    here - the fix an ablation of ``newline="\\n"`` would leave unnoticed on this machine."""
    calls: list[tuple[str | None, ...]] = []
    original = Path.write_text

    def recording(self: Path, data: str, **kwargs: object) -> int:
        calls.append((kwargs.get("newline"),))
        return original(self, data, **kwargs)

    monkeypatch.setattr(Path, "write_text", recording)
    generate(tmp_path / "p", 1200, "many")
    assert len(calls) > 1
    assert all(call == ("\n",) for call in calls)


@pytest.mark.parametrize(
    ("arguments", "sentence"),
    [
        ((119, "many"), "a generated project has at least 120 declarations, not 119"),
        ((1200, "round"), "a shape is one of many, large or mixed, not 'round'"),
    ],
)
def test_what_cannot_be_generated_is_refused(
    tmp_path: Path, arguments: tuple[int, str], sentence: str
) -> None:
    with pytest.raises(ValueError) as refused:
        generate(tmp_path / "p", *arguments)
    assert str(refused.value) == sentence


def test_a_directory_that_exists_is_refused(tmp_path: Path) -> None:
    with pytest.raises(FileExistsError) as refused:
        generate(tmp_path, 1200, "many")
    assert str(refused.value) == f"{tmp_path} exists already; generate into a new directory"


def test_the_command_line_says_what_it_wrote(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(
        [str(tmp_path / "p"), "--declarations", "1200", "--shape", "large", "--unread", "0.5"]
    )
    assert code == 0
    assert capsys.readouterr().out == (
        f"{tmp_path / 'p' / 'project.ddd.json'}: 30 components, 1200 declarations, "
        "0 outputs without an id, 600 outputs nobody reads\n"
    )


@pytest.mark.parametrize(
    ("argument", "sentence"),
    [
        ("1.5", "a density is a fraction from 0 to 1, not 1.5"),
        ("-0.1", "a density is a fraction from 0 to 1, not -0.1"),
    ],
)
def test_a_density_outside_zero_to_one_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], argument: str, sentence: str
) -> None:
    with pytest.raises(SystemExit) as stopped:
        main([str(tmp_path / "p"), "--declarations", "1200", "--unread", argument])
    assert stopped.value.code == 2
    assert (
        capsys.readouterr().err.splitlines()[-1]
        == f"generate_project.py: error: argument --unread: {sentence}"
    )


def test_a_refusal_of_generate_is_a_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as stopped:
        main([str(tmp_path), "--declarations", "1200"])
    assert stopped.value.code == 2
    assert capsys.readouterr().err.splitlines()[-1] == (
        f"generate_project.py: error: {tmp_path} exists already; generate into a new directory"
    )
