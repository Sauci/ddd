"""The transcripts of the documentation are re-run, and have to print what they show.

A page that says "this is the actual output of the tool" makes a claim that rots the moment
a check is added or a message is reworded, and nobody re-reads every page after every
release. So every ``$ ddd ...`` command a page runs over the shipped examples is run here,
in a scratch copy of ``examples/``, and its output is compared line by line with the lines
the page shows beneath it.

Four conventions keep the transcripts honest without making them unreadable:

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

A page that builds its own project - the tutorial - writes it for the reader too: a json
block whose introducing paragraph names exactly one ``*.ddd.json`` path in double backticks
is that file. A page whose commands then name one of the files it wrote is building a
project of its own, and every command of its transcripts runs, through ``bash`` in the
page's own working directory, exactly as the reader types them - globs, redirections and
``cp`` included. The commands over the shipped examples run in-process on every page, and a
page quoting a shipped file under its own name, or naming files it never writes, has its
other commands read as illustrations.
"""

from __future__ import annotations

import contextlib
import io
import itertools
import json
import os
import re
import shlex
import shutil
import subprocess
import sysconfig
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
NAMED_FILE = re.compile(r"``([\w./-]+\.ddd\.json)``")
SCRIPTS = Path(sysconfig.get_path("scripts"))
"""Where ``ddd`` is installed for this interpreter, put first on the path of a shell run."""


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
    def illustrative(self) -> bool:
        """A trailing comment marks a run that depends on an edit the prose describes."""
        return " #" in self.command

    @property
    def over_the_examples(self) -> bool:
        """Whether the run needs nothing but the shipped examples, and so runs on every page."""
        return "examples/" in self.command or self.command.split()[:2] == ["ddd", "checks"]

    def mode(self, page_writes_files: bool) -> str | None:
        """How to run this transcript: in this process, through a shell, or not at all."""
        if self.illustrative:
            return None
        if self.over_the_examples and self.command.startswith("ddd "):
            return "process"
        return "shell" if page_writes_files else None


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
    """The runs of a page, each with the exit status the page pins, if it does.

    Every command is kept, ``ddd`` or not: a tutorial copies templates and lists them, and
    the shell has to see those in order. ``echo $?`` is not a run of its own but the status
    of the one before it.
    """
    found: list[Transcript] = []
    for number, command, shown in shell_segments(page):
        if command == "echo $?":
            if found and shown and shown[0].strip().isdigit():
                found[-1].status = int(shown[0])
            continue
        found.append(Transcript(page, number, command, shown))
    return found


def written_files(page: Path) -> dict[str, str]:
    """The description files a page writes for its reader, by the path the page names.

    A json block is a file when the paragraph introducing it names exactly one ``*.ddd.json``
    path in double backticks; a paragraph naming several names no single one.
    """
    lines = page.read_text(encoding="utf-8").splitlines()
    found: dict[str, str] = {}
    for number, text in enumerate(lines):
        if text.strip() != ".. code-block:: json":
            continue
        end = number
        while end > 0 and not lines[end - 1].strip():
            end -= 1
        start = end
        while start > 0 and lines[start - 1].strip():
            start -= 1
        names = NAMED_FILE.findall(" ".join(lines[start:end]))
        if len(names) != 1 or names[0].startswith("examples/"):
            continue  # several files named, or a shipped one quoted
        body: list[str] = []
        for line in lines[number + 1 :]:
            if line.strip() and not line.startswith("   "):
                break
            body.append(line[3:])
        content = "\n".join(body).strip() + "\n"
        json.loads(content)  # the page has to show valid json
        found[names[0]] = content
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
        if any(character in argument for character in "*?["):
            continue  # a glob names files that exist already, for the shell to expand
        target = cwd / argument
        if not target.exists() and not argument.startswith("examples/"):
            block = json_block_before(transcript.page, transcript.line)
            if block is not None:
                json.loads(block)  # the page has to show valid json
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(block, encoding="utf-8")


def normalized(text: str, cwd: Path) -> list[str]:
    """The printed lines as a page shows them, the scratch directory standing for the checkout.

    The tool prints paths in posix form on every platform, so both spellings of the directory
    are replaced: the native one and the posix one.
    """
    printed = [
        line.rstrip().replace(str(cwd), CHECKOUT).replace(cwd.as_posix(), CHECKOUT)
        for line in text.splitlines()
    ]
    while printed and not printed[-1]:
        printed.pop()
    return printed


def run(
    transcript: Transcript, cwd: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[list[str], int]:
    """Runs a ``ddd`` command in this process, output and findings merged as a terminal would.

    ``> file`` sends the payload where the page sends it - an archived dump, say - and the
    terminal then shows the findings alone, which is what the page shows too.
    """
    prepare(transcript, cwd)
    monkeypatch.chdir(cwd)
    command, _, target = transcript.command.partition(" > ")
    stream, payload = io.StringIO(), io.StringIO()
    with (
        contextlib.redirect_stdout(payload if target else stream),
        contextlib.redirect_stderr(stream),
    ):
        try:
            status = main(shlex.split(command)[1:])
        except SystemExit as usage_error:  # argparse refusing the command line
            status = int(usage_error.code or 0)
    if target:
        (cwd / target.strip()).write_text(payload.getvalue(), encoding="utf-8")
    return normalized(stream.getvalue(), cwd), status


def run_in_shell(transcript: Transcript, cwd: Path) -> tuple[list[str], int]:
    """Runs a command as the reader types it, through bash, in the page's own directory."""
    bash = shutil.which("bash")
    assert bash is not None, "the tutorial's transcripts are shell sessions; bash is needed"
    prepare(transcript, cwd)
    environment = {
        **os.environ,
        "PATH": f"{SCRIPTS}{os.pathsep}{os.environ.get('PATH', '')}",
        "PYTHONPATH": str(ROOT / "src"),
        "PYTHONUTF8": "1",
    }
    completed = subprocess.run(
        [bash, "-c", transcript.command],
        cwd=cwd,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    return normalized(completed.stdout, cwd), completed.returncode


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


FILES = {page: written_files(page) for page in PAGES}


def builds_its_own_project(page: Path) -> bool:
    """Whether a page's commands run over files it wrote, which is what opts it into a shell."""
    return any(name in t.command for name in FILES[page] for t in transcripts(page))


BUILDS = {page: builds_its_own_project(page) for page in PAGES}
RUNS = {page: [t for t in transcripts(page) if t.mode(BUILDS[page]) is not None] for page in PAGES}


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
    for name, content in FILES[page].items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text(content, encoding="utf-8")
    complaints: list[str] = []
    for transcript in RUNS[page]:
        if transcript.mode(BUILDS[page]) == "process":
            printed, status = run(transcript, tmp_path, monkeypatch)
        else:
            printed, status = run_in_shell(transcript, tmp_path)
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
