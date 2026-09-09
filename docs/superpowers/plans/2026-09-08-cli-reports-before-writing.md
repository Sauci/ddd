# The command line reports its findings before any step that can fail - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A run whose analysis succeeded never loses its findings because a later step failed: a plugin hook raising, a `--renames` file that cannot be written, an address map that cannot be read, a template that fails, an output directory that cannot be written. The findings are printed, then the usage error, and the exit code is 2.

**Architecture:** One context manager in `src/ddd/cli.py`, `_reported_on_failure(bag, output_format)`, wraps every fallible step that runs after the bag holds the analysis: on `OSError` or `ValueError` it reports the bag in the requested format, then re-raises for `main` to print the usage error. The plugin hook case lives inside `analyze()` (called by `_analyze` and `_read_dictionary`), so the wrapper goes around those calls too. Two messages are sharpened on the way: the `--renames` failure names the option, and a write failure names the file rather than the directory.

**Tech Stack:** Python 3.12, argparse, pytest (`main([...])` with `capsys`, as `tests/test_cli.py` does).

**Spec:** `docs/superpowers/reviews/2026-09-08-complete-review.md` (branch `review/complete-review-2026-09-08`): pass 8 Important 4, pass 3 Important 5, pass 8 Important 6 (the message half), pass 8 design note "Report before you write". `SPEC.md` section 7 (exit codes, 1586-1590) and 3.11 (a hook that raises is a usage error).

## Global Constraints

- Branch: `fix/cli-reports-before-writing`, off `master`. Push after every task. Do not open a pull request.
- Run this checkout only (`python -m pytest tests/test_cli.py --no-cov -q` while developing; the full `python -m pytest` with 100% coverage, ruff check, ruff format check and mypy from the scratchpad venv `C:/Users/lmbsog0/AppData/Local/Temp/claude/C--git-ac11-ddd/ab815568-8224-42f5-b802-44dd98973875/scratchpad/venv` before the last commit). The 12 environmental failures of the review baseline are known.
- The output *order* of a successful run does not change: the transcripts in the documentation are re-run by `tests/test_transcripts.py` and pin it. Only the failure path gains output.
- The exit code of a failed step stays 2 (`EXIT_USAGE`), as `SPEC.md` 1.1 and 7 say; the findings exit 1 is reserved for findings.
- Commit messages: a lowercase sentence, no prefix, trailer `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Docstrings say why; British spelling; ` - ` not em dashes.

---

## File Structure

- Modify: `src/ddd/cli.py` - `_reported_on_failure`, `_analyze`, `_read_dictionary`, `_command_compare` (the `--renames` write), `_command_generate` (the address map, the backends, `render`, `write`).
- Modify: `tests/test_cli.py` (new class `TestFindingsSurviveAFailedStep`), `tests/test_plugins.py` (the raising-hook test asserts the findings are printed).
- Modify: `SPEC.md` section 7 (one sentence), `docs/command_line_interface.rst` (exit code table, one sentence), `CHANGELOG.md`.

---

### Task 1: The findings are printed before a usage error that follows the analysis

**Files:**
- Modify: `src/ddd/cli.py`
- Test: `tests/test_cli.py`, `tests/test_plugins.py`

**Interfaces:**
- Produces: `_reported_on_failure(bag: DiagnosticBag, output_format: str) -> contextlib.AbstractContextManager[None]`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cli.py` (it imports `main`, `EXIT_USAGE`, `component`, `declare`, `project`, `write_tree`, `TEMPLATES`, `DEMO`):

```python
class TestFindingsSurviveAFailedStep:
    """A step that fails after the analysis must not take the findings down with it.

    The one run that fails is the one whose findings the reader needs; and the failing step
    - a file that cannot be written, a template that cannot render - is usually unrelated to
    what the findings say.
    """

    def files(self) -> dict[str, Any]:
        # An info finding (`missing-id`) on an otherwise clean project: what has to survive.
        return {
            "project.ddd.json": project("P", "a.ddd.json"),
            "a.ddd.json": component("A", declare("local", "X")),
        }

    def test_a_renames_file_that_cannot_be_written(self, tree: Path, capsys: pytest.CaptureFixture[str]) -> None:
        write_tree(tree, self.files())
        (tree / "blocked").mkdir()
        code = main(["compare", str(tree / "project.ddd.json"), str(tree / "project.ddd.json"), "--renames", str(tree / "blocked")])
        captured = capsys.readouterr()
        assert code == EXIT_USAGE
        assert "info[missing-id]" in captured.err
        assert "cannot write the --renames file" in captured.err
        assert captured.err.index("missing-id") < captured.err.index("--renames file")

    def test_a_template_that_fails_to_render(self, tree: Path, capsys: pytest.CaptureFixture[str]) -> None:
        write_tree(tree, self.files())
        templates = tree / "templates"
        templates.mkdir()
        (templates / "ddd_globals.c.jinja2").write_text("{{ model.no_such_attribute.deeper }}", encoding="utf-8")
        code = main(["generate", "c", str(tree / "project.ddd.json"), "-t", str(templates), "-o", str(tree / "out")])
        captured = capsys.readouterr()
        assert code == EXIT_USAGE
        assert "info[missing-id]" in captured.err
        assert "ddd_globals.c.jinja2" in captured.err

    def test_an_address_map_that_cannot_be_read(self, tree: Path, capsys: pytest.CaptureFixture[str]) -> None:
        write_tree(tree, self.files())
        (tree / "map.json").write_text("{ not json", encoding="utf-8")
        code = main(["generate", "a2l", str(tree / "project.ddd.json"), "-o", str(tree / "out"), "--address-map", str(tree / "map.json")])
        captured = capsys.readouterr()
        assert code == EXIT_USAGE
        assert "info[missing-id]" in captured.err
        assert "not valid json" in captured.err

    def test_an_output_file_that_cannot_be_written_is_named(self, tree: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """The directory is fine; one target inside it is a directory itself. Naming the
        directory sent the reader to check its permissions."""
        write_tree(tree, self.files())
        out = tree / "out"
        (out / "ddd_globals.h").mkdir(parents=True)
        code = main(["generate", "c", str(tree / "project.ddd.json"), "-t", str(TEMPLATES), "-o", str(out)])
        captured = capsys.readouterr()
        assert code == EXIT_USAGE
        assert "info[missing-id]" in captured.err
        assert "cannot write '" in captured.err and "ddd_globals.h'" in captured.err

    def test_json_output_carries_the_findings_too(self, tree: Path, capsys: pytest.CaptureFixture[str]) -> None:
        write_tree(tree, self.files())
        (tree / "blocked").mkdir()
        code = main(["compare", str(tree / "project.ddd.json"), str(tree / "project.ddd.json"), "--renames", str(tree / "blocked"), "--format", "json"])
        captured = capsys.readouterr()
        assert code == EXIT_USAGE
        payload = json.loads(captured.out)
        assert [entry["check"] for entry in payload["diagnostics"]] == ["missing-id"]
        assert "cannot write the --renames file" in captured.err
```

(`Any` is imported in `tests/test_cli.py`; `json` too. If `test_an_address_map_that_cannot_be_read` finds `load_address_map` raising before `_analyze` runs, read `_command_generate`: the map is loaded *after* the analysis, so the finding exists at that point.)

In `tests/test_plugins.py`, find the test of a `check` hook that raises on the command line (`grep -n "failed in its check hook" tests/test_plugins.py`) and extend its assertions: the run's own findings (the fixture's `missing-id`, or whatever finding that project has - read the fixture) appear on stderr before the `ddd: plugin '...' failed in its check hook` line, and the exit code is still `EXIT_USAGE`. If the fixture project has no finding of its own, add a `missing-id` by using an unstamped `local` declaration.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_cli.py -k TestFindingsSurviveAFailedStep --no-cov -q`
Expected: the four stderr tests fail on `"info[missing-id]" in captured.err` (or on the message); the naming test fails on `cannot write '`.

- [ ] **Step 3: Implement**

In `src/ddd/cli.py`:

1. Add (near `_report`):

```python
@contextlib.contextmanager
def _reported_on_failure(bag: DiagnosticBag, output_format: str) -> Iterator[None]:
    """Print the findings gathered so far if what follows turns into a usage error.

    Every command analyses first and produces something second - a rename list, an address
    map read, the artefacts - and ``main`` turns a failure of the second half into one line
    and exit 2. Without this the findings of the first half were gone with it, and the run
    that failed is exactly the run whose findings the reader needs.
    """
    try:
        yield
    except (OSError, ValueError):
        _report(bag, output_format)
        raise
```

with `import contextlib` and `from collections.abc import Iterator` added to the imports.

2. `_analyze`: wrap the analysis:

```python
    bag.policy.verify(bag.registered)
    with _reported_on_failure(bag, args.format):
        # A plugin hook that raises is a usage error naming the plugin (section 3.11); the
        # findings collected before the hook ran are the project's, and are printed first.
        dictionary = analyze(workspace, bag)
```

`_read_dictionary` and `_read_baseline` have no `args` and are called once the shared bag may already hold the candidate's findings (`ddd check --baseline` analyses the candidate first). Leave their signatures alone and wrap the *calls* instead: in `_command_check`, `baseline = _read_baseline(args.baseline, bag)` goes inside `with _reported_on_failure(bag, args.format):`; in `_command_compare`, the two reads (`_read_baseline`, `_read_dictionary`) go inside one such block, so a candidate whose hook raises still prints the baseline's carried errors, and a baseline whose hook raises prints whatever the bag holds.

3. `_command_compare`: wrap the `--renames` write and name the option:

```python
    if args.renames is not None:
        # Written whether or not the comparison found errors: a delivery that cannot be
        # accepted still needs its renames listed, so that whoever fixes it knows what moved.
        with _reported_on_failure(bag, args.format):
            try:
                args.renames.write_text(
                    json.dumps(renames(paired), indent=2) + "\n", encoding="utf-8", newline=""
                )
            except OSError as error:
                msg = f"cannot write the --renames file '{args.renames.as_posix()}': {error.strerror or error}"
                raise OSError(msg) from None
```

4. `_command_generate`: wrap `load_address_map` and `_check_address_coverage` (the map read), the plugin `backend_of` calls, `render` and `write`, in `with _reported_on_failure(bag, args.format):` blocks (one block from the map load to the end of `write` is simplest; the `bag.has_errors and not args.force` gate inside it already reports and returns, which is fine because the context manager only acts on an exception). Change the `write` failure message to name the file:

```python
    except OSError as error:
        # The target is the one thing a caller gets wrong regularly - a path that is a
        # directory, or one nothing may be written to. Naming the file beats the bare errno
        # text, and beats naming the directory, which is usually fine.
        target = Path(error.filename).as_posix() if error.filename else args.output_dir.as_posix()
        msg = f"cannot write '{target}': {error.strerror or error}"
        raise OSError(msg) from None
```

Then the JSON case: when `args.format == "json"` and the failure happens, `_reported_on_failure` prints the diagnostics document to stdout (via `_report(bag, "json")` - check `_report` prints the payload to stdout in json mode), and `main` prints the error line to stderr. That is what the last test asserts.

- [ ] **Step 4: Run the tests**

Run: `python -m pytest tests/test_cli.py tests/test_plugins.py tests/test_transcripts.py --no-cov -q`
Expected: all pass. A test that asserted the old `cannot write into '<dir>'` wording (`tests/test_cli.py`, `test_an_output_directory_that_is_a_file`) is updated to the new message, which names the path that failed.

- [ ] **Step 5: Commit and push**

```bash
git add src/ddd/cli.py tests/test_cli.py tests/test_plugins.py
git commit -m "print the findings before a step after the analysis turns into a usage error" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push -u origin fix/cli-reports-before-writing
```

---

### Task 2: The specification, the command line page and the changelog

**Files:**
- Modify: `SPEC.md` section 7 (the exit code paragraph, 1586-1590), `docs/command_line_interface.rst` (the exit code table), `CHANGELOG.md`.

- [ ] **Step 1: SPEC.md.** After the sentence defining exit code 2 (a usage error), add: "A usage error raised by a step that follows the analysis - a plugin hook that raises, a `--renames` file, an address map or an artefact that cannot be written - is printed after the findings of the analysis, which are reported in the requested format first; the exit code is still 2."

- [ ] **Step 2: docs/command_line_interface.rst.** In the exit code table's row for 2 (find it with `grep -n "usage error" docs/command_line_interface.rst`), add the same sentence in the page's voice; `docs/consistency_checks.rst` lines 828-832 say exit 2 means "Nothing was checked": reword to "the command line, a plugin or an output could not be used; the findings gathered before the failure are still printed".

- [ ] **Step 3: CHANGELOG.md.** Under `## Unreleased`:

```
* **A failed step after the analysis no longer discards the findings.**  A plugin hook that
  raised, a `--renames` file, an address map or an output that could not be written turned
  the whole run into one usage error line, and the findings of the analysis - the ones the
  reader of a failed run needs - were gone with it.  They are now printed first, in the
  requested format, and the usage error follows; the exit code is still 2.  The `--renames`
  failure names the option, and a write failure names the file rather than its directory.
```

- [ ] **Step 4: Verification and commit**

Run `python -m pytest tests/test_documentation.py tests/test_transcripts.py --no-cov -q`, then the full `python -m pytest`, ruff check, ruff format check, mypy.

```bash
git add SPEC.md docs/command_line_interface.rst docs/consistency_checks.rst CHANGELOG.md
git commit -m "say that the findings are printed before a later usage error" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push
```
