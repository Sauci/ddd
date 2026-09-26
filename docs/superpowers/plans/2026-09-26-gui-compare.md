# Comparing a delivery in the browser — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Compare tab in `ddd gui` answering the question `ddd check` does not — can this
delivery replace the one already out there — against a baseline the reader names by a path.

**Architecture:** One new module holds how a side of a comparison is read, moved out of `cli.py`
so the command and the page share one policy rather than two readings of it. One stateless route
runs the comparison against the open project and answers a verdict, findings and rename rows. One
new screen draws it, reusing the findings components part 4 built and part 11 extended.

**Tech Stack:** Python 3.13 (`ddd.compare`, `ddd.cli`, `ddd.gui.api`), React with Ladle stories
and Playwright journeys. No new dependency on either side.

**Spec:** [`docs/superpowers/specs/2026-09-26-gui-compare-design.md`](../specs/2026-09-26-gui-
compare-design.md)

## Global Constraints

Copied from the spec. Every task's requirements include these.

- **The candidate is always the open project.** There is no two-arbitrary-deliveries mode.
- **A baseline is a path resolved under the session root.** A path that escapes it is refused
  with its reason, not silently clamped. This is the first time the page reads a file that is not
  a file of the open project, and the restriction is what keeps it from being a file browser.
- **A baseline may be a dumped dictionary or a project description**, as the command accepts.
- **The baseline-reading policy is shared, not reimplemented**: its own bag, never `--strict`
  however strict this run is, and only its errors carried over, prefixed.
- **The severity policy is the session's own.** No new control.
- **The route is stateless.** The page holds the baseline path and asks again when the revision
  changes. The server keeps a cache of resolved baselines and nothing else.
- **The rename map is shown as a table.** Saving it as a file is out of scope.
- **Nothing changes what the language server reports.** `ddd.lsp.diagnostics`' runners are the
  editor's; this part does not touch them.
- **Python gate at 100 % of lines and branches**, no `pragma: no cover`, no skips. **A
  conditional expression registers no branch at all with `coverage.py`** — five defects reached
  part 9's review through that hole and one reached part 11's. Where an arm needs a test, write a
  statement or early returns; ruff's `SIM108` pushes the other way and early returns satisfy both.
- **No Vitest test for a component or a screen**, as since part 1.
- **No new dependency**, page or server. The rule has held since part 1.
- Commit messages end with `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`. Never
  `--amend`, never rebase.

## Prerequisites (before Task 1)

- Branch `feature/gui-compare`, off master at `df6bc3f`, with the spec as its first two commits
  `f8440bd` and `a00f2b8`. Part 11 is merged; this builds on it.
- Environment, **from the repository root, before changing directory**:
  `export PATH="$HOME/.local/node-v24.21.0/bin:$PWD/.venv/bin:$PATH"`.
- Green before anything is touched: `python -m pytest && ruff check . && ruff format --check . &&
  mypy`.
  `mypy` takes its targets from `pyproject.toml`; a bare `mypy .` adds noise that is not yours.
- **Today's numbers, measured not guessed: 4039 Python tests, 405 Vitest, 95 screenshot
  references, 75 journeys.**
- The journeys need `PLAYWRIGHT_CHANNEL=chrome` on this machine — a bare `npm run e2e` fails all
  75 with `Executable doesn't exist at ~/.cache/ms-playwright/…`, which is the missing variable
  and not a broken install — and `npm run build` must precede them, because they drive the
  compiled pages in `src/ddd/gui/static`.
- Sphinx needs `-e JAVA_TOOL_OPTIONS=-Duser.home=/tmp` or a stray `docs/?/.java` appears.

## Conventions for every task

- **Probe before you write.** Every claim below was checked against the code, and the plans of
  parts 8 through 11 were still wrong nine, eleven, four and six times. **Four times a plan's own
  example would have shipped a test that asserts nothing.** If the code disagrees with a step,
  the code is right: say so in your report and do what is correct.
- **Never `page.waitForResponse`** in a journey. It broke part 6's CI and two known flaky spots
  in the suite trace to timing — `skeleton.spec.ts:134`'s arrow count and a `waitForResponse`
  near line 220.
- Commit at the end of each task. Do not dispatch subagents; review arrives from the controller.

## File structure

| File | Responsible for |
| --- | --- |
| `src/ddd/deliveries.py` | **New.** How a side of a comparison is read: `Resolved`, `where`, `holds_a_description`, `read_dictionary`, `read_baseline`. Moved out of `cli.py` whole, so the policy in their docstrings keeps one home. |
| `src/ddd/cli.py` | **Modified.** Imports them instead of defining them. Nothing else changes. |
| `src/ddd/gui/compare.py` | **New.** The comparison the route answers: resolve a baseline under the root, cache it by path and fingerprint, run `compare`, turn the bag into findings, decide the verdict. |
| `src/ddd/gui/contract.py` | **Modified.** `CompareReply`, and whatever it nests. |
| `src/ddd/gui/api.py` | **Modified.** `_compare` and its `_ROUTES` entry. |
| `gui/src/api/client.ts` | **Modified.** `getCompare`. |
| `gui/src/screens/ComparePage.tsx` | **New.** The tab: the path field, the verdict, the findings, the renames. |
| `gui/src/components/CompareView.tsx` | **New.** The picture of it, holding no state. |
| `gui/src/components/CompareView.stories.tsx` | **New.** Four stories. |
| `gui/e2e/compare.spec.ts` | **New.** One journey. |
| `CHANGELOG.md`, `docs/command_line_interface.rst` | **Modified.** What a reader is told. |

## Interfaces between the tasks

Task 1 produces these; Tasks 2 and 3 consume them. Names and types are exact.

```python
# src/ddd/deliveries.py  — every one of these is moved, not written

@dataclass(frozen=True, slots=True)
class Resolved:
    """A dictionary and what a plugin's hook needs beside it."""
    dictionary: DataDictionary
    plugins: tuple[Plugin, ...]
    locate: Callable[[str], Location | None]
    from_description: bool
    sources: tuple[Path, ...]

def where(path: Path) -> Location: ...
def holds_a_description(document: dict[str, Any] | None) -> bool: ...
def read_dictionary(path: Path, bag: DiagnosticBag) -> Resolved | None: ...
def read_baseline(path: Path, bag: DiagnosticBag, standalone: bool = False) -> Resolved | None: ...
```

```python
# src/ddd/gui/compare.py

@dataclass(frozen=True, slots=True)
class Compared:
    """One comparison of the open project against a baseline."""
    verdict: bool
    """Whether the candidate can stand in for the baseline, by the rule the command's exit
    code uses: no finding of severity error survived the policy."""
    findings: tuple[Filed, ...]
    renames: tuple[dict[str, str], ...]

class BaselineRefused(Exception):
    """A baseline the page may not read, or could not read. Its message is what the reader
    is shown, so it names the path and says which of the four reasons it is."""

# Resolved baselines, keyed by resolved path AND the fingerprint the file had when it was read,
# so a re-dumped baseline is re-read rather than served stale. A plain dict: throwing it away
# costs speed and nothing else.
BaselineCache = dict[tuple[Path, str], Resolved]

def compared(revision: Revision, baseline: Path, root: Path, cache: BaselineCache) -> Compared:
    """Raises BaselineRefused for a path outside `root`, unreadable, not json, or json that
    is neither a dictionary nor a description."""
```

The route turns `Compared.findings` into the page's `Finding`s with `api._finding`, which is the
same function `/api/state` uses, so a comparison finding routes exactly as a consistency finding
does.

---

### Task 1: One home for reading a side of a comparison

**Files:**
- Create: `src/ddd/deliveries.py`
- Modify: `src/ddd/cli.py` — `_where` (648), `Resolved` (1639), `_read_dictionary` (1699),
  `_read_baseline` (1766), `_holds_a_description` (1805)
- Must not change: `tests/test_cli.py`, `tests/test_compare.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `Resolved`, `where`, `holds_a_description`, `read_dictionary`, `read_baseline`, as
  spelled in *Interfaces between the tasks*.

**What this task is.** A pure move. Five things come out of `cli.py` into a module of their own,
unchanged but for losing a leading underscore, and `cli.py` imports them. Nothing gains a
behaviour and nothing loses one.

**Why it is worth its own task.** `read_baseline` carries policy that took real thought — its own
bag, never `--strict`, only errors carried over prefixed, `-W` deliberately not reaching it — and
the GUI needs exactly that policy. Reimplementing it would be two readings of one rule, which is
what part 11 spent itself removing. Read its docstring before you move it; it explains a bug that
used to exist.

**The proof.** `tests/test_cli.py` is 3816 lines and mentions these functions only twice; almost
everything exercises them through the command. So **it must come out unedited**, and so must
`tests/test_compare.py`. If either needs a change, the move was not a move.

- [ ] **Step 1: Read all five, in full**

Run: `sed -n '648,665p;1639,1655p;1699,1727p;1766,1803p;1805,1812p' src/ddd/cli.py`

- [ ] **Step 2: Create the module with its own docstring**

```python
"""Reading a side of a comparison: a delivery as it was handed over.

``ddd compare`` and ``ddd check --baseline`` take a baseline and a candidate, each of which is
either a dictionary somebody archived or a project description that has to be analysed to become
one. ``ddd gui`` compares the open project against a baseline the reader names, and needs the
same reading of what a baseline is - so it lives here rather than in the command, where the page
would have had to copy it.

What makes the copy dangerous is not the reading but the policy around it: a baseline is analysed
in a bag of its own, without ``--strict`` however strict the run asking is, and only its errors
are carried over. :func:`read_baseline` says why at length. A second implementation would have
drifted from that the first time either side changed.
"""
```

- [ ] **Step 3: Move the five, verbatim but for their names**

`_where` → `where`, `_holds_a_description` → `holds_a_description`, `_read_dictionary` →
`read_dictionary`, `_read_baseline` → `read_baseline`; `Resolved` keeps its name. **Keep every
docstring word for word** — they are the reason this module exists. Carry the imports each needs:
`Resolved` wants `DataDictionary`, `Plugin`, `Location`, `Callable`, `Path`; `read_baseline` wants
`STANDALONE_POLICY`, `DiagnosticBag`, `SeverityPolicy`, `Severity`. Keep the lazy
`from ddd.analysis import analyze` and `from ddd.loading import …` **inside** `read_dictionary`'s
body, and the lazy `from ddd.loading import resolve_path` inside `where`'s — they are deliberate,
and hoisting them may well make a cycle. If it does not, leave them anyway: that is not this
task's question.

- [ ] **Step 4: Import them in `cli.py` and edit the call sites**

```python
from ddd.deliveries import Resolved, holds_a_description, read_baseline, read_dictionary, where
```

`_where(` becomes `where(` at its seven sites, `_read_dictionary(` at its three,
`_holds_a_description(` at its two, `_read_baseline(` at its one. **Do not alias on import** —
`import where as _where` would keep the diff smaller and hide that the function moved, which is
the opposite of what this task is for.

- [ ] **Step 5: Run the whole Python gate**

Run: `python -m pytest && ruff check . && ruff format --check . && mypy`
Expected: **4039 passed**, 100 % line and branch.

- [ ] **Step 6: Prove it was a move**

Run: `git diff --stat df6bc3f..HEAD -- tests/test_cli.py tests/test_compare.py`
Expected: **no output.** A change there means behaviour moved with the code, and that is a defect
rather than a test needing an update.

Then check the module is reachable the way the GUI will reach it:

Run: `python -c "from ddd.deliveries import read_baseline;
print(read_baseline.__doc__.splitlines()[0])"`
Expected: the first line of the docstring you moved.

- [ ] **Step 7: Commit**

```bash
git add src/ddd/deliveries.py src/ddd/cli.py
git commit -m "give reading a delivery a home the page can reach"
```

### Task 2: The comparison the route answers

**Files:**
- Create: `src/ddd/gui/compare.py`
- Modify: `src/ddd/gui/contract.py`, `src/ddd/gui/api.py`
- Test: `tests/test_gui_compare.py` (new), `tests/test_gui_api.py`

**Interfaces:**
- Consumes: `read_baseline`, `Resolved` from Task 1.
- Produces: `Compared`, `compared(revision, baseline, root, cache)`, `BaselineRefused`, and `GET
  /api/compare?baseline=`.

**What this task is.** The whole server side. Resolve a path under the root, read the baseline
through Task 1's shared policy, compare it against `revision.dictionary`, turn the bag into
findings the page already knows how to draw, and say whether the candidate can stand in.

- [ ] **Step 1: Write the failing test for the path rule**

The first thing to pin is the restriction, because it is the part that is about safety rather
than about comparing. In `tests/test_gui_compare.py`:

```python
def test_a_baseline_outside_the_root_is_refused(tmp_path: Path) -> None:
    # The page has never read a file that is not a file of the open project. A path that
    # climbs out of the session's root is refused with its reason, not clamped to something
    # inside it - a silent clamp would compare against a delivery nobody named.
    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "elsewhere.json"
    outside.write_text("{}")
    with pytest.raises(BaselineRefused) as refused:
        compared(_a_revision(root), outside, root, {})
    # The reason travels, not merely the refusal: a reader who is told "no" and not "why"
    # cannot act on it, and the path they typed is the thing they have to correct.
    assert outside.as_posix() in str(refused.value)
    assert "outside" in str(refused.value)
```

`_a_revision(root)` is the helper you will need in every test here — a `Revision` over a small
project on disk. Look at how `tests/test_gui_api.py` builds one and reuse that rather than
inventing a second way; if it builds one only through the `Session`, use the `Session`.

- [ ] **Step 2: Run it and watch it fail**

Run: `python -m pytest tests/test_gui_compare.py -q`
Expected: FAIL — `ddd.gui.compare` does not exist.

- [ ] **Step 3: Write the module**

The shape, with the pieces this repository already has named:

```python
@dataclass(frozen=True, slots=True)
class Compared:
    verdict: bool
    findings: tuple[Filed, ...]
    renames: tuple[dict[str, str], ...]
```

- **The path.** Resolve it and require `session.root` to be one of its parents. `Path.resolve()`
  then `is_relative_to` is the reading to use; check what `find_projects` does with its own root
  and follow it rather than inventing a second rule.
- **The baseline.** `read_baseline(path, bag)` from Task 1, into a bag of its own.
- **The cache.** Keyed by resolved path **and the file's fingerprint**, so a baseline edited on
  disk is re-read. `ddd.gui.session` already has a `fingerprint` helper — use it. A cache that
  keys on the path alone would serve a stale delivery after a re-dump, which is the one thing a
  comparison must not do.
- **The comparison.** `compare(baseline.dictionary, revision.dictionary, bag, location=…)` from
  `ddd.compare`, which hands back the pairing; `renames(paired)` reads the map out of it rather
  than comparing a second time.
- **The findings.** `group_findings(bag, fallback, grouped)` from `ddd.lsp.diagnostics`, the same
  function the session uses, then a `Filed` per entry. **Check what it does with a comparison
  finding's notes**: `_mirrors` files a copy at each note's location, and a comparison's notes may
  point into the *baseline*, which is not a file of the open project. Decide what that should do
  and say what you decided — a row on a file the page cannot open is a real possibility here and
  nobody has looked at it.
- **The verdict.** No finding of severity error survived the policy. Take the severity from the
  session's own policy, not a new one.

- [ ] **Step 4: Run the test**

Run: `python -m pytest tests/test_gui_compare.py -q`
Expected: PASS.

- [ ] **Step 5: Add the contract and the route**

`CompareReply` in `src/ddd/gui/contract.py`, beside the other replies and documented the way they
are — a docstring per field, saying what the page does with it. It carries `revision`, `verdict`,
`findings` and `renames`.

`_compare` in `src/ddd/gui/api.py` and its `_ROUTES` entry. Follow `_fix` (`728`) for the shape: a
`?baseline=` that is missing answers `400 bad-request` with a sentence naming the parameter, and a
`BaselineRefused` answers `400` with its message. Build the findings with `_finding`, the same
function
`/api/state` uses — **not** a second construction, or a comparison finding will route differently
from a consistency finding and nobody will know why.

- [ ] **Step 6: Test the route**

In `tests/test_gui_api.py`, beside the `/api/fix` tests: a project compared against a dump of
itself answering `verdict: true` with no findings; the same project with a datatype drifted
answering `verdict: false` with a `changed-interface` finding that carries a route; a missing
`?baseline=` answering `400`; and **all four refusals** the spec names, each answering `400` with
a message that says which it is — outside the root, unreadable, not json, and json that is
neither a dictionary nor a description. The fourth is the one nobody thinks of: a valid json file
that is simply something else.

- [ ] **Step 7: The whole Python gate**

Run: `python -m pytest && ruff check . && ruff format --check . && mypy`
Expected: PASS at 100 % line and branch.

Run: `git diff --stat df6bc3f..HEAD -- tests/test_cli.py tests/test_compare.py`
Expected: still no output. This task does not touch the command.

- [ ] **Step 8: Commit**

```bash
git add src/ddd/gui/compare.py src/ddd/gui/contract.py src/ddd/gui/api.py tests/test_gui_compare.py tests/test_gui_api.py
git commit -m "answer whether the open project can stand in for a delivery"
```

### Task 3: The tab

**Files:**
- Create: `gui/src/screens/ComparePage.tsx`, `gui/src/components/CompareView.tsx`
- Modify: `gui/src/app/App.tsx` (`PROJECT_VIEWS`, 21-27), `gui/src/api/client.ts`,
  `gui/src/styles/ui.css`
- Test: whatever lands in `gui/src/lib` or `gui/src/api` only

**Interfaces:**
- Consumes: `GET /api/compare?baseline=` from Task 2.
- Produces: a `compare` project view, and `CompareView`'s props for Task 4's stories.

**What this task is.** A sixth tab. `PROJECT_VIEWS` is a const tuple of `[view, label]` pairs —
`graph`, `table`, `units`, `types`, `findings` — and this adds `["compare", "Compare"]`. Follow
how `findings` is wired end to end and do the same; **read it before writing, and if the route
type needs the new view added somewhere this plan has not named, that is the code being right.**

- [ ] **Step 1: Read the Findings tab end to end**

Run: `sed -n '21,27p;95,110p' gui/src/app/App.tsx` and then read
`gui/src/screens/FindingsPage.tsx`
whole. It is the closest neighbour: a screen that asks the server, holds a selection, and hands a
component its props.

- [ ] **Step 2: Add the view and the client call**

`["compare", "Compare"]` in `PROJECT_VIEWS`, after `findings`. In `gui/src/api/client.ts`, beside
`getFix`:

```ts
export const getCompare = (baseline: string, fetchImpl: Fetch = fetch) =>
  request<CompareReply>(`/api/compare?baseline=${encodeURIComponent(baseline)}`, {}, fetchImpl);
```

**Check `request`'s real signature** before copying this — `getFix` at `client.ts:122` is the
model, and it is what the client tests assert against.

- [ ] **Step 3: Write `CompareView`, which holds no state**

Props: the baseline the field shows, a handler for changing it, a handler for asking, the reply or
`null`, a refusal or `null`, and `busy`. It draws, in this order:

1. **The field**, with a sentence saying what it accepts: a dumped dictionary or a project
   description, at a path under the project's own root.
2. **The verdict**, leading, once there is a reply. A list of differences without an answer makes
   the reader do the arithmetic the command already does for them.
3. **The findings**, through `FindingsTableView` and `FindingPanelView` **unchanged**. If either
   needs a prop it does not have, stop and report it rather than widening them — they are part 4's
   and part 11's, and four other screens draw them.
4. **The renames**, as a table of `id`, `from` and `to`, under a heading that says what it is for:
   migrating datasets and recordings that name objects DDD cannot see.
5. **A refusal**, said plainly, where one came back.

- [ ] **Step 4: Write `ComparePage`, which holds the state**

The baseline path, the reply, the refusal. **It re-asks when the revision changes** — read how
`FindingsPage` gets `state?.revision` and do the same, so fixing a `changed-interface` turns the
verdict while the reader watches. That liveness is the whole reason this is a tab and not a
report.

- [ ] **Step 5: The page gate**

Run: `cd gui && npm run lint && npm run typecheck && npm test && npm run build && npm run
ladle:build`
Expected: clean, Vitest still **405** at 100 % on all four metrics — this task adds no test there,
and if coverage drops you have put logic in `src/lib` without testing it.

- [ ] **Step 6: Drive it by hand once**

Start `ddd gui` over a **copy** of `examples/demo`, dump that copy's own dictionary with
`ddd dump <project> -o <copy>/baseline.json`, and compare against it. It must pass. Then break a
datatype and watch the verdict turn. **Take a screenshot and look at it.**

- [ ] **Step 7: Commit**

```bash
git add gui/src/screens/ComparePage.tsx gui/src/components/CompareView.tsx gui/src/app/App.tsx gui/src/api/client.ts gui/src/styles/ui.css
git commit -m "put the replacement question where a reader can ask it"
```

### Task 4: What it looks like

**Files:**
- Create: `gui/src/components/CompareView.stories.tsx`
- Modify: `gui/src/stories/fixtures.ts`
- Reference: `gui/screenshots/references/` (regenerate)

**What this task is.** Four stories, and their screenshot references. **95 today; this makes 99.**

- [ ] **Step 1: Read how stories are written here**

Read `gui/src/components/FindingPanelView.stories.tsx`. It has a local `View` wrapper that
supplies the props a story does not care about and holds the choice in `useState`; findings come
from `gui/src/stories/fixtures.ts` rather than being written per story; and a fix's `changes`
carry real `PlannedChange`s with `hunks`, never `[]`. Part 11's plan got all three wrong and its
implementer had to be corrected. Do not repeat that.

- [ ] **Step 2: The four stories**

- **Empty** — the field and its sentence, nothing else. What a reader sees on opening the tab.
- **A delivery that can replace** — the verdict, no findings, and the renames empty.
- **A delivery that cannot** — the verdict, two or three findings of different comparison checks,
  and a renames table with rows. Use real check names from the thirteen: `changed-interface`,
  `removed-object`, `renamed-object`.
- **A refused baseline** — the reason said plainly, no verdict.

**Every fixture must be true of the real demo.** Part 11 shipped a reference naming a file that
declares no such variable, and it had to be rebuilt. Check the names and paths you use against
`examples/demo` before writing them.

- [ ] **Step 3: Build and regenerate**

Run: `cd gui && npm run lint && npm run typecheck && npm run build && npm run ladle:build`
Then: `UPDATE=1 docker compose run --rm gui-screenshots`
Expected: **99**, and `git status --porcelain gui/screenshots` shows **four additions and no
modifications**. A modification means a story you did not mean to touch moved.

- [ ] **Step 4: Open all four PNGs and look at them**

Not a formality. Part 10 shipped three defects that only a picture caught — a tick clipped to
`320(`, a row label on its own marker, then that label struck through by its own line — and the
DOM was correct every time. Say what you saw, not what the DOM contained.

- [ ] **Step 5: Commit**

```bash
git add gui/src/components/CompareView.stories.tsx gui/src/stories/fixtures.ts gui/screenshots/references
git commit -m "show a delivery that can replace one, and one that cannot"
```

### Task 5: The journey

**Files:**
- Create: `gui/e2e/compare.spec.ts`
- Modify: `gui/e2e/demo.ts` if it needs a helper

**What this task is.** One journey. **75 today; this makes 76.**

- [ ] **Step 1: Read the suite's real shape first**

The fixture is `test("…", async ({ page, gui }) => …)` with `gui.directory` and `gui.address`;
there is no `demo`/`open`/`read` trio. `driftIn(directory, file, variable, unit)` plants a fault
in the copy. Findings are reached as `getByRole("row", …)` into a `complementary` panel. Read
`gui/e2e/findings.spec.ts` and `gui/e2e/fixtures.ts` and use the real names.

- [ ] **Step 2: Write it**

Compare a copy of the demo against a dump of **itself**, which must pass; then drift a datatype
and assert the verdict turns and a `changed-interface` finding appears.

Producing the dump is the new part: the journey needs a `ddd dump` of the copy, written inside
`gui.directory` so the path is under the root. **Check how `fixtures.ts` starts `ddd gui`** and
produce the dump the same way — the binary is already reachable there.

**Assert the verdict's text, not merely that findings changed.** A journey that only counts rows
would pass against a server that never ran a comparison.

**Never `page.waitForResponse`.**

- [ ] **Step 3: Build, then run three times**

Run: `cd gui && npm run build && PLAYWRIGHT_CHANNEL=chrome npm run e2e`
Expected: **76**, three times. Report which of the two documented flaky spots fired, if either.

- [ ] **Step 4: Commit**

```bash
git add gui/e2e/compare.spec.ts gui/e2e/demo.ts
git commit -m "prove a reader can ask whether this delivery replaces the last"
```

### Task 6: What a user reads

**Files:** `CHANGELOG.md`, `docs/command_line_interface.rst`

- [ ] **Step 1: Find the anchors by content, not by line**

The changelog's unreleased block, after part 11's paragraph. The `ddd gui` row of the
command-line page, whose sentence already lists the tabs — "a Units tab … and a Findings tab of
every finding, worst first, one tab away". The new tab joins that list.

- [ ] **Step 2: Measure before writing**

**The ceiling is the longest sentence in the section you are editing, not in the file.** For part
11 those were **102 words** in the changelog's unreleased block and **73** in the `ddd gui` cell,
while the whole-file figures were 170 and 126 — which would have been a false ceiling. Re-measure;
part 11 changed both sections.

- [ ] **Step 3: Say what is true**

Each clause checked against the code you shipped: that a Compare tab answers whether the open
project can stand in for a delivery the reader names; that a baseline is a dumped dictionary or a
project description at a path under the project's own root; that the verdict is the command's own;
that the findings are the thirteen comparison checks and lead to what they name; and that the
rename map is shown and not written. **If a sentence is not true of Task 2's code, the code is
right.**

- [ ] **Step 4: Build the docs and read the rendered page**

Run: `docker compose run --rm -e JAVA_TOOL_OPTIONS=-Duser.home=/tmp docs`
Expected: `build succeeded`, and `git status` free of a stray `docs/?`.

- [ ] **Step 5: Commit**

```bash
git add CHANGELOG.md docs/command_line_interface.rst
git commit -m "say the browser can now ask the replacement question"
```

### Task 7: The milestone gate

**Files:** none. This runs everything and fills in the progress log.

- [ ] **Step 1: Python** — `python -m pytest && ruff check . && ruff format --check . && mypy`,
      100 % line and branch.
- [ ] **Step 2: The move, proved** — `git diff --stat df6bc3f..HEAD -- tests/test_cli.py
      tests/test_compare.py` prints nothing.
- [ ] **Step 3: The page** — `cd gui && npm run lint && npm run typecheck && npm test && npm run
      build && npm run ladle:build`, Vitest at 100 % on all four metrics.
- [ ] **Step 4: Screenshots** — `docker compose run --rm gui-screenshots` in verify mode: **99**,
      with nothing from parts 1 to 11 changed.
- [ ] **Step 5: Journeys, three times** — `PLAYWRIGHT_CHANNEL=chrome npm run e2e`, **76** each.
- [ ] **Step 6: Documentation** — sphinx clean under `-W`, no stray `docs/?`.
- [ ] **Step 7: Drive it by hand, and look at it.** Over a **copy** of `examples/demo`: dump the
      copy's own dictionary and compare against it — it must pass. Drift a datatype and watch the
      verdict turn. Name a path **outside** the root and read the refusal. Name a file that is
      neither a dictionary nor a description and read that one. Compare against
      `examples/inconsistent`'s project description, which is a baseline that does not resolve,
      and check the "in the baseline:" prefix reaches the page. **Take screenshots and look at
      them.**
- [ ] **Step 8: Fill in the progress log**, one row per task, the way the earlier plans write
      theirs: what the fix rounds found, in a sentence or two. **Do not touch `Left open` or
      `Rulings` — those are the controller's.** Commit.

## Progress log

| Task | Commit | Notes |
| --- | --- | --- |
| 1 | `e97fb42`, `14a7159` | Moved `Resolved`, `where`, `holds_a_description`, `read_dictionary` and `read_baseline` out of `cli.py` into `deliveries.py` verbatim but for their names; `tests/test_cli.py` and `tests/test_compare.py` held, the move's own proof. One review round: dropped a one-line `_read_dictionary` re-export in `cli.py` kept only to protect `test_cli.py`'s own private import, pointing that import at `ddd.deliveries` directly instead; and moved `where()` a second time, out of `deliveries.py` into `diagnostics.py` beside the `Location` it builds, since six of its seven call sites are not about reading a delivery at all. |
| 2 | `25895ef`, `735a42c`, `59b4793` | `compare.py`'s `Compared`/`compared()`/`BaselineRefused`, the `CompareReply` contract and `GET /api/compare`, reusing `api._finding` so a comparison finding routes the way a consistency finding does. One correction to the spec along the way: comparison findings do not route to what they name, every one lands on the candidate's project file with an empty pointer — caught by declining to assert what the plan's own example claimed and measuring a drifted pair instead. One review round: a baseline's own forwarded finding was being routed as though it were the open project's, and a comparison check's severity took whichever build's policy sorted first rather than the strictest of several; both closed together. |
| 3 | `f7d86ce`, `5c23fc2`, `45dd835` | The Compare tab end to end — `ComparePage`/`CompareView`, the sixth `PROJECT_VIEWS` entry, `getCompare`, a `route.ts` arm — re-asking live on `state?.revision` the way `FindingsPage` does. One self-caught fix: the field asked with the untrimmed value, so a stray leading or trailing space passed `CompareView`'s own disabled check and was sent to the server verbatim. One review round: `CompareReply.findings` merged the comparison's own findings and the baseline's forwarded ones into one tuple told apart only by an `"in the baseline: "` message prefix, so a baseline row sharing a candidate file's display name was indistinguishable — split into two structural fields, `findings` and `baseline_findings`, client and server, with the File column now reading "the baseline's X" for the baseline's own rows. |
| 4 | `590cbb2` | Four `CompareView` stories and their screenshots — empty, a delivery the demo can replace, one it cannot (three comparison checks plus a baseline finding reading "the baseline's sensor_hub.ddd.json"), and a baseline refused for sitting outside the root — fixtures checked name for name against `examples/demo`, 95 references becoming 99. Clean: no fix round. |
| 5 | `dc61fe8` | One journey: a copy of the demo compared against a dump of itself passes, then against itself with `ValueA`'s datatype widened on its producing declaration (`sensor_hub.ddd.json`) turns the verdict and reports one `changed-interface` finding, asserted on the verdict's own text and the finding's own message, not merely a row appearing. `demo.ts` gained `dump()` and `driftDatatypeIn()`. 76/76 three times; one of the two documented flaky spots fired once, the expected occurrence for this task and not a new one. No fix round. |
| 6 | `b5e34b6` | Documented the Compare tab: a sixth-tab paragraph in the changelog's unreleased block, and the `ddd gui` row of the CLI reference naming the tab in its opening list plus an addendum on the baseline's confinement and four refusal reasons, the verdict's narrower scope (it excludes the open project's own consistency errors), the comparison's and baseline's findings leading nowhere, and the rename table being drawn, not written. Clean: no fix round, sphinx build succeeded under `-W`. |
| 7 | | The gate, clean: 4065 Python and 411 Vitest tests, each at 100% line and branch; task 1's move still proven by one changed import line in `tests/test_cli.py` and nothing in `tests/test_compare.py`; 99 screenshots unmoved; 76 journeys three times with no flake at all, the documented `skeleton.spec.ts` one that fired once during Task 5 not recurring; sphinx clean under `-W`, no stray `docs/?`. Driven by hand over a copy of the demo: a fresh self-dump compared as replaceable; widening `ValueA`'s datatype on its producing declaration in `sensor_hub.ddd.json` turned the verdict red live, no click, with one `changed-interface` finding naming both datatypes and the reading consumer; a path outside the root, a file that was not json, and a valid json file of the wrong shape were each refused with a message naming which of the four reasons applied; and comparing against `examples/inconsistent`'s own project description surfaced 35 findings, its own errors each prefixed "in the baseline: " with the File column separately marking them "the baseline's `<file>`", never colliding with the candidate's own rows. |

## Left open

Filled in as the plan runs: anything found and deliberately not fixed here, with what it costs.

## Rulings

Filled in as the plan runs: every decision taken against the plan's text, why, and what it costs
if wrong.
