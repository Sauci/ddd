"""The transcripts of the documentation are re-run, and have to print what they show.

A page that says "this is the actual output of the tool" makes a claim that rots the moment
a check is added or a message is reworded, and nobody re-reads every page after every
release. So every ``$ ddd ...`` command a page runs over the shipped examples is run here,
in a scratch copy of ``examples/``, and its output is compared line by line with the lines
the page shows beneath it.

Three conventions keep the transcripts honest without making them unreadable:

* a line that is only ``...`` stands for any run of lines the page left out;
* ``$ echo $?`` followed by a number pins the exit status of the command before it;
* a command carrying a trailing ``# comment`` depends on an edit the prose describes, and
  is shown rather than run;
* ``/home/you/ddd`` stands for the reader's checkout wherever a command prints an absolute
  path.

A transcript that shows a file being ``created`` runs against an emptied output directory,
so a page may show a first run wherever its story needs one; ``updated`` and ``unchanged``
runs see whatever the page's earlier commands left behind. A json file a command names
that the examples do not ship - an address map, say - is written from the json block the
page shows last before the command, which is where a reader would have copied it from.
"""

from __future__ import annotations

import contextlib
import io
import itertools
import json
import re
import shlex
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from ddd.cli import main

ROOT = Path(__file__).resolve().parents[1]
PAGES = [
    *sorted(page for page in (ROOT / "docs").rglob("*.rst") if "superpowers" not in page.parts),
    ROOT / "README.md",
]

SHELL = re.compile(r"^(?P<indent>\s*)\$ (?P<command>.*)$")
ELISION = "..."
CHECKOUT = "/home/you/ddd"


@dataclass
class Transcript:
    """One documented run: where it is, what was typed, and what the page shows for it."""

    page: Path
    line: int
    command: str
    shown: list[str] = field(default_factory=list)
    status: int | None = None

    @property
    def where(self) -> str:
        return f"{self.page.relative_to(ROOT)}:{self.line}"

    @property
    def reproducible(self) -> bool:
        """Whether the run needs nothing but the shipped examples.

        A command over a project the page builds in prose (a tutorial's files, a delivery
        archive) cannot be re-run from here; one with a trailing comment is illustrative.
        """
        if " #" in self.command:
            return False
        return "examples/" in self.command or self.command.split()[:2] == ["ddd", "checks"]


def shell_segments(page: Path) -> list[tuple[int, str, list[str]]]:
    """Every ``$`` line of a page with the lines shown after it, up to the end of its block.

    A block ends at the first line indented less than the command (reStructuredText) or at
    a closing fence (markdown); a blank line inside a block belongs to it.
    """
    segments: list[tuple[int, str, list[str]]] = []
    lines = page.read_text(encoding="utf-8").splitlines()
    current: list[str] | None = None
    indent = 0
    for number, text in enumerate(lines, start=1):
        stripped = text.strip()
        if current is not None:
            own_indent = len(text) - len(text.lstrip())
            if stripped.startswith("```") or (stripped and own_indent < indent):
                current = None
            elif not SHELL.match(text):
                current.append(text[indent:].rstrip())
                continue
        found = SHELL.match(text)
        if found:
            indent = len(found.group("indent"))
            current = []
            segments.append((number, found.group("command").strip(), current))
    for _, _, shown in segments:
        while shown and not shown[-1]:
            shown.pop()
    return segments


def transcripts(page: Path) -> list[Transcript]:
    """The ``ddd`` runs of a page, each with the exit status the page pins, if it does."""
    found: list[Transcript] = []
    for number, command, shown in shell_segments(page):
        if command.startswith("ddd "):
            found.append(Transcript(page, number, command, shown))
        elif command == "echo $?" and found and shown and shown[0].strip().isdigit():
            found[-1].status = int(shown[0])
    return found


def json_block_before(page: Path, line: int) -> str | None:
    """The last json code block a page shows before a line, dedented."""
    lines = page.read_text(encoding="utf-8").splitlines()[: line - 1]
    starts = [
        number
        for number, text in enumerate(lines)
        if text.strip() in (".. code-block:: json", "```json")
    ]
    if not starts:
        return None
    start = starts[-1]
    body: list[str] = []
    for text in lines[start + 1 :]:
        if text.strip().startswith("```"):
            break
        if body and text.strip() and (len(text) - len(text.lstrip())) == 0:
            break
        body.append(text)
    while body and not body[0].strip():
        body.pop(0)
    indent = min(len(text) - len(text.lstrip()) for text in body if text.strip())
    return "\n".join(text[indent:] for text in body).strip() + "\n"


def prepare(transcript: Transcript, cwd: Path) -> None:
    """Puts the working directory in the state the page's reader would have it in."""
    arguments = shlex.split(transcript.command)[1:]
    for flag in ("-o", "--output-dir"):
        if flag in arguments and any("(created)" in line for line in transcript.shown):
            shutil.rmtree(cwd / arguments[arguments.index(flag) + 1], ignore_errors=True)
    for previous, argument in zip(["", *arguments[:-1]], arguments, strict=True):
        if previous in ("-o", "--output-dir") or not argument.endswith(".json"):
            continue
        target = cwd / argument
        if not target.exists() and not argument.startswith("examples/"):
            block = json_block_before(transcript.page, transcript.line)
            if block is not None:
                json.loads(block)  # the page has to show valid json
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(block, encoding="utf-8")


def run(
    transcript: Transcript, cwd: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[list[str], int]:
    """Runs the command as the page shows it, output and findings merged as a terminal would."""
    prepare(transcript, cwd)
    monkeypatch.chdir(cwd)
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        try:
            status = main(shlex.split(transcript.command)[1:])
        except SystemExit as usage_error:  # argparse refusing the command line
            status = int(usage_error.code or 0)
    # The tool prints paths in posix form on every platform, so both spellings of the
    # scratch directory stand for the reader's checkout: the native one and the posix one.
    printed = [
        line.rstrip().replace(str(cwd), CHECKOUT).replace(cwd.as_posix(), CHECKOUT)
        for line in stream.getvalue().splitlines()
    ]
    while printed and not printed[-1]:
        printed.pop()
    return printed, status


def matches(shown: list[str], printed: list[str]) -> bool:
    """Whether the printed lines are the shown ones, ``...`` standing for any run of lines."""
    groups = [
        list(group)
        for is_gap, group in itertools.groupby(shown, key=lambda line: line.strip() == ELISION)
        if not is_gap
    ]
    if not groups:
        return bool(shown) or not printed
    position = 0
    for index, group in enumerate(groups):
        if index == 0 and shown[0].strip() != ELISION:
            if printed[: len(group)] != group:
                return False
            position = len(group)
            continue
        window = len(group)
        found = next(
            (
                start
                for start in range(position, len(printed) - window + 1)
                if printed[start : start + window] == group
            ),
            None,
        )
        if found is None:
            return False
        position = found + window
    return shown[-1].strip() == ELISION or position == len(printed)


RUNS = {page: [t for t in transcripts(page) if t.reproducible] for page in PAGES}


@pytest.mark.parametrize(
    "page",
    [page for page, runs in RUNS.items() if runs],
    ids=lambda page: str(page.relative_to(ROOT)),
)
def test_every_documented_run_prints_what_the_page_shows(
    page: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One scratch copy of the examples per page; the page's runs happen in its order."""
    shutil.copytree(ROOT / "examples", tmp_path / "examples")
    complaints: list[str] = []
    for transcript in RUNS[page]:
        printed, status = run(transcript, tmp_path, monkeypatch)
        if not matches(transcript.shown, printed):
            shown = "\n".join(transcript.shown)
            complaints.append(
                f"{transcript.where}: $ {transcript.command}\n"
                f"--- the page shows ---\n{shown}\n"
                f"--- the tool prints ---\n" + "\n".join(printed)
            )
        if transcript.status is not None and status != transcript.status:
            complaints.append(
                f"{transcript.where}: $ {transcript.command}\n"
                f"the page pins exit status {transcript.status}, the tool exits {status}"
            )
    assert not complaints, "\n\n".join(complaints)


class TestTheMatcher:
    """The elision rule is the one thing here that could pass a stale page by accident."""

    def test_an_exact_transcript_matches_only_itself(self) -> None:
        assert matches(["a", "b"], ["a", "b"])
        assert not matches(["a", "b"], ["a", "b", "c"])
        assert not matches(["a", "b"], ["a"])

    def test_an_elision_stands_for_any_run_of_lines(self) -> None:
        assert matches(["a", "...", "d"], ["a", "b", "c", "d"])
        assert matches(["a", "...", "d"], ["a", "d"])
        assert not matches(["a", "...", "d"], ["a", "b", "c"])

    def test_an_elision_at_either_end_leaves_that_end_open(self) -> None:
        assert matches(["...", "d"], ["a", "d"])
        assert matches(["a", "..."], ["a", "b"])
        assert not matches(["...", "d"], ["a", "d", "e"])

    def test_the_shown_lines_have_to_appear_in_order(self) -> None:
        assert not matches(["b", "...", "a"], ["a", "b"])
