# Large Projects in the GUI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `ddd gui` stays usable on projects of 100,000 declarations and more: an edit shows at once, its findings follow when the analysis lands with the page saying they are updating, no table draws more rows than are in view, and a committed generator and benchmark show the figures before and after.

**Architecture:** One background analyser in `ddd.gui.session.Session` takes every request - an edit, an undo, the file poll, opening a project - and merges those landing while it runs into one more analysis; edits answer once written, and the state reply says `analysing` and which edit its revision includes. The state stops carrying findings: `GET /api/findings` answers them a page at a time from an index built once per revision, which also serves every per-name panel and tab. The page follows the state by a version, knows its own edits, draws a window of the Findings table chosen in `gui/src/lib`, virtualises the other long tables with React Aria's own `Virtualizer`, lays the graph out in a Web Worker once per shape, and debounces plan requests.

**Tech Stack:** Python 3.14, pydantic v2, `threading`, pytest at 100 % line and branch; React 19 + TypeScript, react-aria-components 1.21.1 (`Virtualizer`, `TableLayout`), @xyflow/react 12.11.6, @dagrejs/dagre 3.1.1 in a Web Worker, TanStack Query 5, Vitest at 100 % over `src/api`, `src/lib`, `src/state`; Playwright journeys and a Playwright benchmark; Ladle stories with Docker screenshot references; Sphinx docs under `-W`.

**Spec:** `docs/superpowers/specs/2026-09-30-gui-large-projects-design.md`. Read it before any task. Where this plan departs from it, the departure is a ruling in *Rulings taken* at the end, with its reason and the measurement behind it.

## Global Constraints

Every task's requirements include this section.

**Running things**

- There is no `python` on PATH. Always `.venv/bin/python`. Node is not on PATH; it is at `~/.local/node-v24.21.0/bin`.
- **Never add `-q` to pytest.** `pyproject.toml` already sets it in `addopts`; a second removes the `N passed` line while pytest-cov still prints its coverage line, so the output looks fine and says nothing.
- **A pipeline reports its last command's exit status.** Capture each tool's own: `.venv/bin/python -m pytest > gate.txt 2>&1; echo "EXIT=$?"; tail -3 gate.txt`. The tell for a run that finished is its **summary line**. A tail ending in a stack trace did not finish, whatever the exit code says.
- A stale `.coverage` data file once made pytest answer `4445 passed` with exit 3 and **no coverage line**. If the coverage summary is missing, delete `.coverage*` (gitignored) and re-run.
- Journeys: `cd gui && npm run build` first - they drive the **compiled** pages in `src/ddd/gui/static` - then `PLAYWRIGHT_CHANNEL=chrome DDD_PYTHON="$PWD/../.venv/bin/python" npx playwright test --output=<a path outside the repository>`. Writing `--output` inside `gui/` fails with `EACCES`.
- **Never run the journeys while the Docker screenshot run is running**: both drive Playwright over the same `gui/` checkout, and the journeys then fail with "Playwright Test did not expect test() to be called here". One after the other.
- Screenshots: `UPDATE=1 docker compose run --rm gui-screenshots` from the repository root rewrites references; without `UPDATE=1` it compares. Docs: `docker compose run --rm -e JAVA_TOOL_OPTIONS=-Duser.home=/tmp docs`. Docker cannot see the session scratchpad.
- Page schemas: `cd gui && DDD=../.venv/bin/ddd DDD_PYTHON=../.venv/bin/python npm run schemas`. `gui/src/generated/` is gitignored - grep the generated file and let `npm run typecheck` prove the page agrees.
- **Generated projects and benchmark output go in a directory outside the repository** (`BENCH` below; the controller names it in each dispatch). Never commit one.
- **A benchmark runs alone on the machine**: not beside the suite, the journeys, Docker or another benchmark, whose load it would measure. Close the built-in browser pane's other tabs first.

**Gates**

- Python: `.venv/bin/python -m pytest` at **100 % line and branch**, `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, and `.venv/bin/mypy` run **bare** (it checks `src/ddd` and `tools`, strict).
- Page: `npm run lint && npm run typecheck && npm test && npm run build && npm run ladle:build`, Vitest at 100 % on statements, branches, functions **and** lines over `src/api`, `src/lib`, `src/state`.
- No `pragma: no cover`, no skips, no xfails.
- **No commit leaves a gate red.** A change of the contract lands with the page that reads it, in one commit.

**What the gates cannot see**

- **A conditional expression registers zero branches with coverage.py, and so does a comprehension filter.** A short-circuit `and`/`or` inside an `if` records one branch pair for the whole `if`, not one per operand. Write statements where a branch matters.
- **A coverage gate cannot see data.** Ablate every new data value - a threshold, a page size, a sentence, a default - and confirm a **named** test dies. If none does, write the one that does.
- **Ablate python in a scratch `git worktree` and run pytest with that worktree as the working directory.** `pyproject.toml` sets `pythonpath = ["src", "tools", "docker"]`, resolved against *rootdir* and placed ahead of any `PYTHONPATH` you export: a run started from the main repository measures the main repository, every rot "survives", and the reading is that nothing pins anything. The tell is pytest's own `rootdir:` line. **Confirm an ablation kills something before trusting that another kills nothing.** A survival is re-run under `PYTHONHASHSEED=0`, `1`, `4` and `7` before it is believed.
- **Ablate the page in place** - a fresh worktree has no `node_modules`. Run `git status --porcelain <file>` **immediately before every restore**, not once at the start: `git checkout -- <file>` reverts to HEAD and silently eats any fix made in that file since. After each restore, grep for something you expect still to be there.
- **Never draw a conclusion about what *else* pins something from a narrowed run** - no `-k`, no path argument. That question is a whole-suite question; copy the summary line in rather than paraphrasing it.
- **No decision may live in a `.tsx` file.** Lint, typecheck, build and the screenshot diff are nearly all the scrutiny one gets; the journeys do drive the compiled pages, so it is narrow rather than none. Every judgement lives in `gui/src/lib` or `gui/src/state` under the Vitest gate; a `src/app` hook is glue only.
- **A refusal test asserts the whole sentence with `==`.** A code and a substring leave the explanatory clause pinned by nothing. Read every expected sentence off the running code, never out of this plan.
- **A test of the analyser never sleeps** (spec §8). It coordinates with `threading.Event`s and counts analyses; every wait it makes passes a timeout, so a lock held too long fails the test instead of hanging the suite.

**Prose**

- **A sentence stating a measurement gets the measurement run as it is written**, against the file it names, with the exit status copied from *that* run. A sentence saying "nothing else does X" is a whole-repository claim and gets a whole-repository grep.
- **A figure is quoted with the machine, the project - size, shape, density - and the run it came from.** A figure from a profiled run says so: cProfile roughly doubles a Python call's time.
- **Cite by name, not by line number.** Line numbers in this plan were measured on `feature/gui-files` at `588f284` and go stale the moment an earlier task edits the file.
- **Before ruling on a trade-off, confirm both sides of it can actually happen.**

**Conventions**

- Commits: lowercase imperative subject on **one line**, no `feat:`-style prefix, a body saying why. Trailer `Co-Authored-By: <your model> <noreply@anthropic.com>`. Never `--amend`, never rebase.
- **Every UI pull request carries a screenshot of what it added** - the maintainer's standing rule. Open each new or changed reference and say, quoting from the image, what it shows. "Updated N references" is not a report.
- Subagents do not write report files; they return findings as text.
- If a brief or this plan is wrong, **say so in your report rather than working around it silently.**

## Prerequisites

1. **PR #73 (`feature/gui-files`) has merged.** This part virtualises the Files table and indexes what `GET /api/files` counts. Do not start before it lands.
2. **Bring the branch up to date and move it into the main checkout.** `feature/gui-large-projects` was created in a scratch worktree, from `d4053aa`, so the spec could be written while #73 was open. Execution needs the main checkout, because the screenshot and docs gates run in Docker and Docker cannot see the scratchpad:

   ```bash
   cd /home/sauci/Documents/Github/ddd
   git worktree remove /tmp/claude-1000/-home-sauci-Documents-Github-ddd/260ccbb9-1e8c-4023-817a-2dbecb093f04/scratchpad/gui-large-projects
   git checkout master && git pull --ff-only origin master
   git checkout feature/gui-large-projects
   git merge master        # brings #73 in; never rebase
   git log --oneline -4    # the merge, this plan and the spec
   ```
3. **Gate the merged tree before Task 1** - the milestone gate's commands, each exit status captured. Every gate green there is the baseline each task is compared against.

## Review Focus

The inputs most likely to bite a person using a large project that no task's happy path reaches. Each is pinned by a test in the task that owns it.

1. **The analyser and the session lock** (Task 5). One lock guards the writes, the undo stack, the counters, the request and the stamps; the analysis runs outside it. An edit landing while an analysis runs is written at once and analysed by exactly one analysis after it, however many land; a project opened while another's analysis runs throws that analysis away.
2. **Edit numbers across the async boundary** (Tasks 5, 6). An undo takes a number as an edit does; a revision includes every write numbered up to its `edits`; the page compares its own last number with it. A second window's edit is not the first window's.
3. **A plan made while an edit waits for its analysis** (Task 6). A plan touching a file an unanalysed write changed is refused `analysing` rather than computed from an index of other bytes; a plan touching nothing written since is computed against the published revision (spec §5). The Files tab's judge answers `stale` in its own words while it waits.
4. **Stamps** (Task 5). A save landing while an analysis runs is still caught; a file an edit created is stamped from its own write; opening stamps the files the root's includes name - so neither costs a second analysis, and a sub-project's files still do.
5. **A failure in the background** (Task 5). An exception out of an analysis never kills the analyser and never leaves `analysing` set; it is printed, and the next poll tries again.
6. **A second window** (Task 6). It learns of another window's edit from the long poll - `analysing`, the undo entry - and its plan for the file that edit wrote is refused, never applied over it.
7. **The Findings window and the keyboard** (Task 7). Arrow keys past the rows drawn move the window with the focus; a selected finding the next revision no longer reports closes its panel as it did.
8. **Virtualised tables in screenshots** (Task 9). A long table scrolls inside a box of fixed maximum height, so the photographed page is the same at every size; a short table's box is no taller than its rows.
9. **Journeys while the findings lag** (Task 12). A journey waits on what a reader sees - "Updating the findings" gone, a count changed - never on a response.
10. **The graph's layout** (Task 10). Laid out once per set of modules and arrows, in a worker; a layout that fails says so instead of leaving the canvas empty.

## Measured while planning

The pre-flight measured what the tasks below are shaped by. Linux development PC, one run each, `feature/gui-files` at `588f284`, the 36,000-declaration "many" project the spec's §2 probe generated (1,200 components, 66,005 findings). The endpoint rows were **profiled** with `cProfile` (roughly twice the unprofiled time); the throwaway scripts lived in the session scratchpad.

| What | Measured | Where the time went |
| --- | --- | --- |
| `GET /api/state` | 4,435 ms profiled | `route_of` per finding 2,047 ms, of which parsing the 1,200 files 1,519 ms; `Path.resolve()` once per finding 1,096 ms |
| `GET /api/variable?name=C4V0` | 3,858 ms profiled | `located_on` over all 66,005 findings 3,767 ms, of which `Path.resolve()` 2,915 ms |
| `GET /api/units` | 1,492 ms profiled | `ddd.lsp.units.unit_project` parsing every included file 1,449 ms, to find the units files |
| `GET /api/types` | 1,361 ms profiled | `type_rows` resolving each finding's file, 977 ms |
| `GET /api/shared` | 2 ms | the project declares no shared entry; `shared_rows` is O(entries x findings) |
| `GET /api/graph` | 146 ms profiled | - |

React Aria's `Table` of three columns, with and without its own `Virtualizer` and `TableLayout` (rows of 32 px, a box 600 px high), in a production build in the built-in browser, timed from `root.render` inside `flushSync` to `flushSync` returning - the synchronous work of the first draw, React Aria's second pass over its collection included:

| Rows | Virtualised | Not virtualised |
| --- | --- | --- |
| 300 | - | 95 ms |
| 3,333 | 58 ms | 666 ms |
| 30,000 | 286 ms | - |
| 132,000 | 1,531 ms | - |

`@dagrejs/dagre` 3.1.1 laying out graphs in node 24 (`dagre.layout`, nodes 180 x 48, `rankdir: "LR"`):

| Components | a chain | layers of thirty, each component reading one of the layer before | a tree, four children each | no arrows |
| --- | --- | --- | --- | --- |
| 1,200 | 225 ms | 173 ms | 266 ms | 51 ms |
| 1,800 | `RangeError: Maximum call stack size exceeded` | 232 ms | 427 ms | 78 ms |
| 3,333 | `RangeError` | 475 ms | 1,164 ms | 163 ms |

And one cause, found by reading, of the graph fetched twice that the spec's §2 saw: `GraphPage` asks for `["graph", project, state?.revision]` before the first state arrives - once with `undefined`, then again with the revision. Opening's second analysis (review focus 4) is another: its revision asks for the graph again.

## File Structure

| File | Responsibility | Tasks |
| --- | --- | --- |
| `tools/generate_project.py` *(new)* | a project of `N` declarations, "many", "large" or "mixed", clean or findings-heavy | 1 |
| `tests/test_generate_project.py` *(new)* | its tests | 1 |
| `tools/bench_gui.py` *(new)* | the server half of the benchmark | 2, 5, 6, 7 |
| `tests/test_bench_gui.py` *(new)* | its smoke test | 2, 6, 7 |
| `gui/bench/page.bench.ts`, `gui/playwright.bench.config.ts` *(new)* | the page half | 3, 7 |
| `gui/package.json`, `gui/tsconfig.json` | the `bench` script; `bench/` typechecked | 3 |
| `src/ddd/findings_by_file.py` *(new)* | findings grouped by their file, each file resolved once | 4 |
| `src/ddd/project_types.py`, `src/ddd/project_shared.py`, `src/ddd/project_units.py` | rows and per-name findings over `FindingsByFile` | 4 |
| `src/ddd/lsp/units.py` | `unit_project` parses only a file that can be a units file | 4 |
| `src/ddd/gui/derived.py` *(new)* | what the api derives from one revision, once | 4, 7 |
| `src/ddd/gui/session.py` | the background analyser; versions, snapshots, unanalysed writes | 5, 6 |
| `src/ddd/gui/api.py` | the index and caches; `settled` then none; `analysing`; `GET /api/findings` | 4, 5, 6, 7 |
| `src/ddd/gui/server.py` | starting the analyser; opening without waiting | 5, 6 |
| `src/ddd/gui/contract.py` | `State`, `EditReply`, `UndoReply`; `FindingsReply`, `ListedFinding` | 6, 7 |
| `gui/src/state/revisions.ts` | following the state by its version | 6 |
| `gui/src/state/edits.ts` *(new)* | the page's own last edit | 6 |
| `gui/src/lib/updating.ts` *(new)* | `analysed`, `updatingOf` | 6, 8 |
| `gui/src/api/client.ts`, `gui/src/api/types.ts` | `getState(after)`; `postEdit`/`postUndo` noting the page's own edits; `getFindings` | 6, 7 |
| `gui/src/app/useProjectState.ts`, `gui/src/app/App.tsx` | the analysing shell; `updating` | 6, 8 |
| `gui/src/lib/findingsWindow.ts` *(new)* | which rows the Findings table draws and which pages it asks for | 7 |
| `gui/src/lib/findings.ts` | `findingCounts` from the state's counts; `stillReported` | 7, 8 |
| `gui/src/components/FindingsTableView.tsx`, `gui/src/screens/FindingsPage.tsx`, `ProjectPage.tsx`, `ComponentPage.tsx` | the window; the counts; a file's findings | 7, 8, 9 |
| the seven panel views with a list of findings | "Updating" above it | 8 |
| `gui/src/ui/Table.tsx`, `gui/src/styles/ui.css`, the table views | long tables virtualised | 9 |
| `gui/src/lib/layout.ts`, `gui/src/app/layoutWorker.ts` *(new)*, `gui/src/app/useLayout.ts` *(new)*, `gui/src/screens/GraphPage.tsx` | the graph laid out off the main thread, once per shape | 10 |
| `gui/src/lib/typing.ts` *(new)*, `gui/src/app/useDebounced.ts` *(new)*, the screens asking for plans | plan requests debounced | 11 |
| `gui/e2e/fixtures.ts`, `gui/e2e/large.spec.ts` *(new)*, `docs/command_line_interface.rst`, `docs/developer_documentation.rst`, `CHANGELOG.md` | the journeys, the documentation | 12 |

## Interfaces Between Tasks

```python
# Task 1 - tools/generate_project.py
SHAPES: Final = ("many", "large", "mixed")
@dataclass(frozen=True, slots=True)
class Generated:
    project: Path; components: int; declarations: int; unnamed: int; unread: int
def generate(directory: Path, declarations: int, shape: str, *,
             missing_ids: float = 0.0, unread: float = 0.0) -> Generated: ...
def main(argv: Sequence[str] | None = None) -> int: ...

# Task 2 - tools/bench_gui.py
@dataclass(frozen=True, slots=True)
class Measure:
    name: str; milliseconds: float; size: int | None   # bytes of the answer, where there is one
NAMES: Final[tuple[str, ...]]                          # every measure's name, in order
def measure(project: Path) -> list[Measure]: ...
def main(argv: Sequence[str] | None = None) -> int: ...

# Task 4 - ddd.findings_by_file / ddd.gui.derived
Pair = tuple[Path, Diagnostic]
class FindingsByFile:
    def __init__(self, pairs: Iterable[Pair]) -> None: ...
    def __iter__(self) -> Iterator[Pair]: ...
    def on(self, path: Path) -> tuple[Pair, ...]: ...
    def on_any(self, paths: Iterable[Path]) -> list[Pair]: ...
    def positions(self, path: Path) -> tuple[int, ...]: ...   # Task 7
def type_rows(built: Index, findings: FindingsByFile, cache: dict[Path, Document]) -> tuple[TypeRow, ...]: ...
def shared_rows(built: Index, findings: FindingsByFile, cache: dict[Path, Document]) -> tuple[SharedRow, ...]: ...
def unit_rows(built: Index, findings: FindingsByFile, cache: dict[Path, Document]) -> tuple[UnitRow, ...]: ...
@dataclass(frozen=True, slots=True)
class Derived:
    number: int; files: Mapping[Path, SourceFile]; sources: tuple[SourceFile | None, ...]
    findings: FindingsByFile; at_entry: Mapping[int, int]
    # Task 7: ranked: tuple[int, ...]; repeats: tuple[int, ...]; counts: tuple[int, int, int]
def derived(revision: Revision) -> Derived: ...
def Api._memoised(self, revision: Revision, key: tuple[object, ...], make: Callable[[], Reply]) -> Reply: ...

# Task 5 - ddd.gui.session.Session
def open(self, project: Path) -> None: ...               # asks for the analysis
def edit(self, changes: Sequence[FileChange], label: str) -> tuple[int, tuple[Written, ...]]: ...
def undo(self, at: int) -> int: ...                      # the undo's own number
def poll(self) -> bool: ...
def start(self) -> None: ...                             # the analyser thread, then the poller
def settled(self, timeout: float | None) -> Revision | None: ...
@property
def project(self) -> Path | None: ...
@property
def edits(self) -> int: ...                              # every edit and undo written, counted
# Revision gains: edits: int = 0

# Task 6 - ddd.gui.session / ddd.gui.contract
@dataclass(frozen=True, slots=True)
class Snapshot:
    version: int; project: Path | None; revision: Revision | None; analysing: bool; undoable: Undoable | None
def snapshot(self) -> Snapshot: ...
def wait(self, after: int, timeout: float) -> Snapshot: ...      # after: a version, no longer a revision
def current(self) -> Revision: ...                               # NoProjectError / NotAnalysedError
def unanalysed(self, revision: Revision) -> frozenset[Path]: ...
class NotAnalysedError(RuntimeError): ...
ANALYSING: Final = "analysing"                                    # ddd.gui.api
# State: + version: int, analysing: bool, edits: int (revision 0 before the first analysis)
# EditReply: edit: int, files          UndoReply: edit: int

# Task 7 - ddd.gui.contract
class ListedFinding(Finding): key: str
class FindingsReply(_Frozen): revision: int; total: int; offset: int; findings: tuple[ListedFinding, ...]
# State: - findings, + counts: FindingCounts
```

```ts
// Task 6 - gui/src/state/edits.ts, gui/src/lib/updating.ts, gui/src/state/revisions.ts
export class OwnEdits { wrote(edit: number): void; newest(): number; subscribe(listener: () => void): () => void }
export const ownEdits: OwnEdits;
export function analysed(state: Pick<State, "revision">): boolean;
export function updatingOf(state: Pick<State, "analysing" | "edits">, ownEdit: number): boolean;
export async function followStates(follow: Follow): Promise<void>;   // was followRevisions
// Task 6 - gui/src/app/useProjectState.ts
export function useProjectState(open: boolean): {
  state: State | null;    // the newest analysed state, null before the first analysis
  latest: State | null;   // the newest state, revision 0 included
  updating: boolean; stopped: boolean; failure: string | null };
// Task 7 - gui/src/api/client.ts, gui/src/lib/findingsWindow.ts
export interface FindingsQuery { offset?: number; limit?: number; severity?: string; file?: string; check?: string }
export const getFindings: (query: FindingsQuery, fetchImpl?: Fetch) => Promise<FindingsReply>;
export const ROW_HEIGHT: number; export const PAGE_SIZE: number; export const MARGIN: number;
export interface Span { first: number; last: number }                 // rows [first, last)
export function spanOf(scrollTop: number, height: number, total: number): Span;
export function pagesOf(span: Span): number[];
export interface WindowRow { index: number; key: string; finding: ListedFinding | null; file: string }
export function windowRows(span: Span, pages: ReadonlyMap<number, FindingsReply>): WindowRow[];
export function findingCounts(counts: FindingCounts, updating: boolean): string;  // was over a list; updating from Task 8
export function stillReported(key: string, reply: FindingsReply): boolean;
// Task 8 - gui/src/lib/findings.ts, gui/src/app/updating.ts
export function tableLine(counts: FindingCounts, updating: boolean): string;
export const UpdatingContext: React.Context<boolean>; export function useUpdating(): boolean;
// Task 10 - gui/src/lib/layout.ts
export function shapeOf(modules: readonly GraphModule[], flows: readonly GraphFlow[]): string;
export const VISIBLE_ONLY_ABOVE: number;
export function visibleOnly(count: number): boolean;
// Task 11 - gui/src/lib/typing.ts
export const PLAN_DELAY_MS: number;
export function planDelay(asked: boolean): number;
export function sameRequest(asked: unknown, typed: unknown): boolean;
```

---

### Task 1: the generator

**Model:** standard (`sonnet`) - the code is below; the care is in making a generated project truly clean.

**Files:**
- Create: `tools/generate_project.py`
- Test: `tests/test_generate_project.py`

**Interfaces:**
- Consumes: `ddd.models.common.OBJECT_ID_ALPHABET` (32 characters) and `OBJECT_ID_LENGTH` (12); `ddd.lsp.diagnostics.run_project` in the tests.
- Produces: `SHAPES`, `Generated`, `generate(directory, declarations, shape, *, missing_ids=0.0, unread=0.0)`, `main(argv)`. Tasks 2, 3 and 12 run it as `.venv/bin/python tools/generate_project.py DIRECTORY --declarations N --shape SHAPE [--missing-ids F] [--unread F]`.

A **declaration** here is one entry of a component's interface, output or input alike - what a reader counts down a component's table. The spec §2 counted outputs only and put five readers beside them; every figure this part publishes is re-measured on this generator's projects, never compared with §2's.

The layout of a generated project:

```
DIRECTORY/project.ddd.json       {"project": {"name": "Generated", "includes": ["units.ddd.json", "components/*.ddd.json"]}}
DIRECTORY/units.ddd.json         the eight UNITS, each described
DIRECTORY/components/c00000.ddd.json, c00001.ddd.json, ...   component C00000, C00001, ...
```

Each component's interface is its outputs `C00012_O0000`, `C00012_O0001`, ... then its inputs, each input the producer's own definition without its id. The `i`-th input of the project, counted across components in order, reads the `(i + shift)`-th output, `shift` being far enough that no component reads its own: in the "many" shape, `LAYER` components on, so the canvas has thirty-odd columns of layers instead of one chain as deep as the project is long (*Measured while planning*: dagre 3.1.1 overflows its stack on a chain of 1,800 components). `--unread F` writes that fraction of the inputs as outputs of their own instead (`C00012_X0003`): the output it would have read and the one it becomes are both read by nobody - two `unused-output` warnings, and the count of declarations unchanged. `--missing-ids F` leaves that fraction of the outputs without an id - a `missing-id` note each. A density is spread evenly by `_chosen`: the `n`-th item is chosen where `floor((n + 1) * d) > floor(n * d)`, which chooses exactly `floor(count * d)` of `count` items.

- [ ] **Step 1: Write the failing tests** - `tests/test_generate_project.py`:

```python
"""``tools/generate_project.py``: a project of a chosen size, clean or findings-heavy, and the
same bytes every time it is asked for the same one."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from ddd.lsp.diagnostics import run_project
from generate_project import SHAPES, generate, main


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
    assert [f"{found.check}: {found.message}" for found in run_project(made.project).bag.sorted] == []


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
        sum(1 for entry in interface if entry["scope"] == "output" and "id" not in entry["definition"])
        for interface in interfaces(tmp_path / "p")
    ]
    assert sum(unnamed) == 150
    assert max(unnamed) <= 2


def test_the_same_arguments_write_the_same_bytes(tmp_path: Path) -> None:
    def written(root: Path) -> dict[Path, bytes]:
        return {path.relative_to(root): path.read_bytes() for path in sorted(root.rglob("*.json"))}

    generate(tmp_path / "one", 1200, "mixed", missing_ids=0.3, unread=0.2)
    generate(tmp_path / "two", 1200, "mixed", missing_ids=0.3, unread=0.2)
    assert written(tmp_path / "one") == written(tmp_path / "two")


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
    code = main([str(tmp_path / "p"), "--declarations", "1200", "--shape", "large", "--unread", "0.5"])
    assert code == 0
    assert capsys.readouterr().out == (
        f"{tmp_path / 'p' / 'project.ddd.json'}: 30 components, 1200 declarations, "
        "0 outputs without an id, 600 outputs nobody reads\n"
    )


@pytest.mark.parametrize(
    ("argument", "sentence"),
    [("1.5", "a density is a fraction from 0 to 1, not 1.5"), ("-0.1", "a density is a fraction from 0 to 1, not -0.1")],
)
def test_a_density_outside_zero_to_one_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], argument: str, sentence: str
) -> None:
    with pytest.raises(SystemExit) as stopped:
        main([str(tmp_path / "p"), "--declarations", "1200", "--unread", argument])
    assert stopped.value.code == 2
    assert capsys.readouterr().err.splitlines()[-1] == f"generate_project.py: error: argument --unread: {sentence}"


def test_a_refusal_of_generate_is_a_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as stopped:
        main([str(tmp_path), "--declarations", "1200"])
    assert stopped.value.code == 2
    assert capsys.readouterr().err.splitlines()[-1] == (
        f"generate_project.py: error: {tmp_path} exists already; generate into a new directory"
    )
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/bin/python -m pytest tests/test_generate_project.py --no-cov`
Expected: collection fails with `ModuleNotFoundError: No module named 'generate_project'`.

- [ ] **Step 3: Write `tools/generate_project.py`**

```python
"""Generate a project of a chosen size and shape, to measure ``ddd gui`` on.

The benchmark of the browser interface (``tools/bench_gui.py``, ``gui/bench/``) runs on projects of
10,000, 35,000 and 100,000 declarations, and real projects mix many small components with a few
large ones (``docs/superpowers/specs/2026-09-30-gui-large-projects-design.md`` §4). Nothing in
``examples/`` comes near those sizes, so this writes them - the same bytes for the same arguments,
on every machine.

Every declaration is written as a finished project writes one: an id on every output, a unit its
vocabulary lists, a reader for every output, each reader stating what its producer states. A
project generated with the defaults therefore has no finding at all, as a real one can;
``--missing-ids`` and ``--unread`` give it the findings of a project half-way through a migration,
at the density asked for.

Not part of the ``ddd`` package: a tool of the repository's own, as ``dev_version.py`` is, run by
hand, by the benchmark and by the journeys, and checked by ``tests/test_generate_project.py``.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from ddd.models.common import OBJECT_ID_ALPHABET, OBJECT_ID_LENGTH

SHAPES: Final = ("many", "large", "mixed")
"""Many small components; a few large ones sharing every declaration; or half of each."""

SMALL: Final = 30
"""The declarations of a component of the "many" shape - the size the spec's §2 measured."""

LARGE: Final = 30
"""How many components the "large" shape shares its declarations between; the "mixed" shape has
half as many large ones, beside its small ones."""

LAYER: Final = 30
"""How many components on a reader's output sits, in the "many" shape: the canvas then lays the
project out in layers about this many components across, rather than as one chain as deep as the
project is long, which ``@dagrejs/dagre`` 3.1.1 runs out of stack on past about 1,500
components."""

FEWEST: Final = 120
"""The smallest project generated: fewer declarations leave the "many" shape a component or two,
between which no reader can sit ``LAYER`` components away."""

UNITS: Final = ("rpm", "Nm", "kPa", "degC", "V", "A", "ms", "Hz")
"""The vocabulary every generated project lists, and the units its outputs state in turn."""

MULTIPLIER: Final = 2_654_435_761
"""Scatters the ids: odd, so multiplying by it is a bijection on the 2**60 ids of
``OBJECT_ID_LENGTH`` characters of the 32-letter ``OBJECT_ID_ALPHABET``, and neighbouring
declarations do not read alike."""


@dataclass(frozen=True, slots=True)
class Generated:
    """What :func:`generate` wrote."""

    project: Path
    components: int
    declarations: int
    unnamed: int
    """Outputs written without an id: a ``missing-id`` each."""

    unread: int
    """Outputs nobody reads: an ``unused-output`` each."""


def generate(
    directory: Path,
    declarations: int,
    shape: str,
    *,
    missing_ids: float = 0.0,
    unread: float = 0.0,
) -> Generated:
    """Write a project of ``declarations`` declarations, rounded down to even components, into
    ``directory``, which must not exist yet."""
    if shape not in SHAPES:
        raise ValueError(f"a shape is one of many, large or mixed, not {shape!r}")
    if declarations < FEWEST:
        raise ValueError(
            f"a generated project has at least {FEWEST} declarations, not {declarations}"
        )
    if directory.exists():
        raise FileExistsError(f"{directory} exists already; generate into a new directory")
    halves = [size // 2 for size in _sizes(declarations, shape)]
    owners = [component for component, half in enumerate(halves) for _ in range(half)]
    starts = [sum(halves[:component]) for component in range(len(halves))]
    total = len(owners)
    widest = max(halves)
    shift = min(max(widest, LAYER * (SMALL // 2)), total - widest)
    interfaces: list[list[dict[str, Any]]] = [[] for _ in halves]
    names: list[str] = []
    unnamed = 0
    for number, owner in enumerate(owners):
        name = f"C{owner:05d}_O{number - starts[owner]:04d}"
        names.append(name)
        entry = _output(name, number, named=not _chosen(number, missing_ids))
        unnamed += "id" not in entry["definition"]
        interfaces[owner].append(entry)
    read = [False] * total
    converted = 0
    for slot, owner in enumerate(owners):
        if _chosen(slot, unread):
            number = total + slot
            name = f"C{owner:05d}_X{slot - starts[owner]:04d}"
            entry = _output(name, number, named=not _chosen(number, missing_ids))
            unnamed += "id" not in entry["definition"]
            interfaces[owner].append(entry)
            converted += 1
            continue
        source = (slot + shift) % total
        read[source] = True
        interfaces[owner].append({"scope": "input", "definition": _definition(names[source], source)})
    _write(directory, interfaces)
    return Generated(
        project=directory / "project.ddd.json",
        components=len(halves),
        declarations=2 * total,
        unnamed=unnamed,
        unread=read.count(False) + converted,
    )


def _sizes(declarations: int, shape: str) -> list[int]:
    """Each component's declarations, in component order."""
    if shape == "many":
        return _even(declarations, declarations // SMALL)
    if shape == "large":
        return _even(declarations, LARGE)
    half = declarations // 2
    return _even(half, LARGE // 2) + _even(declarations - half, (declarations - half) // SMALL)


def _even(total: int, parts: int) -> list[int]:
    """``total`` over ``parts`` components as evenly as even sizes allow - an even size being as
    many outputs as inputs - the first components taking two more where some are left over."""
    base = total // parts // 2 * 2
    sizes = [base] * parts
    for index in range((total - base * parts) // 2):
        sizes[index] += 2
    return sizes


def _chosen(number: int, density: float) -> bool:
    """Whether the ``number``-th item is among a ``density`` of them, spread evenly: of ``count``
    items, exactly ``floor(count * density)`` are chosen, never bunched at the start."""
    return math.floor((number + 1) * density) > math.floor(number * density)


def _definition(name: str, number: int) -> dict[str, Any]:
    """What a producer states of its output, and what its reader states back."""
    return {
        "name": name,
        "kind": "measurement",
        "description": f"generated measurement {number}",
        "datatype": "uint16",
        "unit": UNITS[number % len(UNITS)],
        "conversion": {"kind": "identity"},
        "volatile": False,
    }


def _output(name: str, number: int, *, named: bool) -> dict[str, Any]:
    definition = _definition(name, number)
    if named:
        definition = {"name": name, "id": _id(number), **definition}
    return {"scope": "output", "definition": definition}


def _id(number: int) -> str:
    """The ``number``-th id: distinct for distinct numbers, spelled in ``OBJECT_ID_ALPHABET``."""
    size = len(OBJECT_ID_ALPHABET)
    value = (number * MULTIPLIER) % size**OBJECT_ID_LENGTH
    digits = []
    for _ in range(OBJECT_ID_LENGTH):
        value, digit = divmod(value, size)
        digits.append(OBJECT_ID_ALPHABET[digit])
    return "".join(digits)


def _write(directory: Path, interfaces: Sequence[Sequence[dict[str, Any]]]) -> None:
    components = directory / "components"
    components.mkdir(parents=True)
    _dump(
        directory / "project.ddd.json",
        {"project": {"name": "Generated", "includes": ["units.ddd.json", "components/*.ddd.json"]}},
    )
    _dump(
        directory / "units.ddd.json",
        {"units": [{"unit": unit, "description": f"generated unit {unit}"} for unit in UNITS]},
    )
    for index, interface in enumerate(interfaces):
        _dump(
            components / f"c{index:05d}.ddd.json",
            {"component": {"name": f"C{index:05d}", "interface": list(interface)}},
        )


def _dump(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _density(text: str) -> float:
    value = float(text)
    if not 0.0 <= value <= 1.0:
        raise argparse.ArgumentTypeError(f"a density is a fraction from 0 to 1, not {text}")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="generate_project.py",
        description="Write a project of N declarations to measure ddd gui on.",
    )
    parser.add_argument("directory", type=Path, help="where to write it; must not exist yet")
    parser.add_argument("--declarations", type=int, required=True, metavar="N")
    parser.add_argument("--shape", choices=SHAPES, default="many")
    parser.add_argument("--missing-ids", type=_density, default=0.0, metavar="FRACTION")
    parser.add_argument("--unread", type=_density, default=0.0, metavar="FRACTION")
    arguments = parser.parse_args(argv)
    try:
        made = generate(
            arguments.directory,
            arguments.declarations,
            arguments.shape,
            missing_ids=arguments.missing_ids,
            unread=arguments.unread,
        )
    except (ValueError, FileExistsError) as error:
        parser.error(str(error))
    print(
        f"{made.project}: {made.components} components, {made.declarations} declarations, "
        f"{made.unnamed} outputs without an id, {made.unread} outputs nobody reads"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Two things the code above guesses and the clean test decides - fix the code, never the test: which keys a declaration needs to load without a finding (the §2 probe needed `volatile` and `conversion`; `kind`, `description` and `datatype` are copied from `examples/demo`), and whether `unnamed += "id" not in ...` passes `ruff` (it adds a `bool` to an `int`; write `if ... : unnamed += 1` where the linter or mypy objects). A `missing-id` or a `definition-mismatch` in the clean test means a definition the generator writes differs from what the loader wants: read the finding's message, never loosen the test.

- [ ] **Step 4: Run the tests to see them pass**

Run: `.venv/bin/python -m pytest tests/test_generate_project.py --no-cov`
Expected: all pass. Then time a large one by hand and say the figure in your report: `time .venv/bin/python tools/generate_project.py "$BENCH/probe-100k" --declarations 100000 --shape many` - it should take seconds, not minutes.

- [ ] **Step 5: Ablate the data** - in a scratch worktree, running pytest from inside it (*Global Constraints*): `SMALL` 30 to 20; `LARGE` 30 to 20; `LAYER` 30 to 1 (the no-self-read test must still pass, and say what does pin `LAYER` - if nothing does, the canvas's depth is unpinned: add a test that the "many" shape's first component is read by component `LAYER`, not by component 1); `_chosen`'s `>` to `>=`; `MULTIPLIER` to 2 (ids collide: which test dies?); `FEWEST` 120 to 60. Each must kill a named test.

- [ ] **Step 6: Both gates** - the whole Python gate (`pytest`, `ruff check`, `ruff format --check`, bare `mypy`, which checks `tools/`) with each exit status. The page is untouched.

- [ ] **Step 7: Commit**

```bash
git add tools/generate_project.py tests/test_generate_project.py
git commit -m "generate projects of a chosen size and shape, clean or findings-heavy" \
  -m "Part 17 measures ddd gui at 10,000 to 100,000 declarations, and nothing in examples/ comes near. The generator writes such a project the same bytes every time: every output with an id, a unit and a reader, so a default project is clean, and --missing-ids and --unread add the findings of a migration half done." \
  -m "Co-Authored-By: <your model> <noreply@anthropic.com>"
```

---

### Task 2: the server half of the benchmark, and its figures before

**Model:** standard (`sonnet`).

**Files:**
- Create: `tools/bench_gui.py`, `tests/test_bench_gui.py`
- Modify: this plan's *Figures* section (the server table, before)

**Interfaces:**
- Consumes: Task 1's `generate`; `ddd.gui.session.Session`, `ddd.gui.api.Api` (`handle(method, path, query, body) -> Reply`), `ddd.variables.declarations_of(built, name, cache)` for the edit's target.
- Produces: `Measure`, `measure(project)`, `main(argv)`. Tasks 5, 6 and 7 change the api it drives and **update it in the same commit, keeping every measure's name and meaning**.

The measures, in this order, each timed with `time.perf_counter` from the call to its answer **serialised as the server sends it** (`json.dumps(reply.body, allow_nan=False)` inside the timed region - the server does that before the first byte leaves), the size being those bytes:

| Name | What |
| --- | --- |
| `open` | `Session.open` until the project's first revision is published |
| `state`, `graph`, `units`, `types`, `shared`, `files` | `GET /api/<name>` |
| `variable` | `GET /api/variable?name=` the middle one of `sorted(revision.index.declarations)` |
| `unit` | `GET /api/unit?name=` the first of `sorted(revision.index.units)` |
| `remove judged` | `GET /api/files-plan?action=remove&path=` the key of the root's last entry, as `GET /api/files` answers it |
| `analysis` | one component file's modification time moved forward by `os.utime`, then `Session.poll()` until it has analysed |
| `edit answered` | `POST /api/edit` of the unit of the middle variable's first declaration to the next unit of `UNITS`, until it answers |
| `edit analysed` | from the same edit's start until a revision including it is published |

After `edit analysed`, `POST /api/undo` puts the unit back, so a second run measures the same project. Before Task 5 an edit answers only after its analysis, so the two edit figures are one; say so in the figures, don't hide it.

- [ ] **Step 1: The failing test** - `tests/test_bench_gui.py`:

```python
"""``tools/bench_gui.py``: every measure of the server half, on a small generated project."""

from __future__ import annotations

from pathlib import Path

import pytest

from bench_gui import NAMES, main, measure
from generate_project import generate


def test_every_measure_is_taken_in_order_with_its_size(tmp_path: Path) -> None:
    made = generate(tmp_path / "p", 600, "many", missing_ids=0.5, unread=0.5)
    taken = measure(made.project)
    assert [each.name for each in taken] == list(NAMES)
    assert all(each.milliseconds >= 0 for each in taken)
    sized = {each.name for each in taken if each.size is not None}
    assert sized == {"state", "graph", "units", "types", "shared", "files", "variable", "unit", "remove judged", "edit answered"}


def test_the_project_is_left_as_it_was_generated(tmp_path: Path) -> None:
    made = generate(tmp_path / "p", 600, "many")
    before = {path: path.read_bytes() for path in sorted((tmp_path / "p").rglob("*.json"))}
    measure(made.project)
    assert {path: path.read_bytes() for path in sorted((tmp_path / "p").rglob("*.json"))} == before


def test_the_command_line_prints_one_row_per_measure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    made = generate(tmp_path / "p", 600, "large")
    assert main([str(made.project)]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[:2] == ["| project | measure | ms | bytes |", "| --- | --- | --- | --- |"]
    assert [line.split(" | ")[1] for line in lines[2:]] == list(NAMES)
```

Mind the second test: the undo writes the unit back through the edit engine, which writes the bytes the edit found - the file comes back byte for byte only if the engine restores rather than re-lays out. If it fails, read `ddd.editing.restore`'s docstring before changing anything.

- [ ] **Step 2: Run it to see it fail** - `ModuleNotFoundError: No module named 'bench_gui'`.

- [ ] **Step 3: Write `tools/bench_gui.py`** - a module docstring saying what it measures, how and where it may not run (not in CI: the figures are the machine's own), `NAMES` as the tuple of the table above, `Measure`, `measure(project)` over one `Session` and one `Api(session, project, wait_seconds=0.0)`, and `main(argv)` taking one or more project paths and printing the table the test reads, one row per measure, `bytes` blank where there is no size, `ms` to the whole millisecond. A `--json PATH` option writes the same rows as a list of objects, for the figures to be assembled from. Everything the measures need to choose - the variable, the unit, the entry to remove - is chosen from the revision, sorted, so the same project measures the same things on every run.

- [ ] **Step 4: Run it to see it pass**, then the whole Python gate.

- [ ] **Step 5: Generate the benchmark's projects** - 18 of them, into `$BENCH`, each size, shape and density:

```bash
for size in 10000 35000 100000; do for shape in many large mixed; do
  .venv/bin/python tools/generate_project.py "$BENCH/$size-$shape-clean" --declarations $size --shape $shape
  .venv/bin/python tools/generate_project.py "$BENCH/$size-$shape-heavy" --declarations $size --shape $shape --missing-ids 1 --unread 0.5
done; done
```

"Findings-heavy" is **every output without an id and half the inputs written as unread outputs** everywhere this plan says it. Copy the line each command printed into your report.

- [ ] **Step 6: The figures before** - alone on the machine (*Global Constraints*): `.venv/bin/python tools/bench_gui.py --json "$BENCH/server-before.json" $BENCH/*/project.ddd.json > "$BENCH/server-before.md"; echo "EXIT=$?"`. Put them in *Figures* under **Server, before**, one row per project and one column per measure, with the machine, the commit and the date. Say which measures you would call over the spec's budgets and which the spec does not budget.

- [ ] **Step 7: Commit** - the tool, its test and the plan's figures, one commit.

---

### Task 3: the page half of the benchmark, and its figures before

**Model:** standard (`sonnet`).

**Files:**
- Create: `gui/bench/page.bench.ts`, `gui/playwright.bench.config.ts`
- Modify: `gui/package.json` (a `bench` script), `gui/tsconfig.json` (`include` gains `bench` and `playwright.bench.config.ts`), this plan's *Figures* (the page table, before)

**Interfaces:**
- Consumes: Task 1's projects in `$BENCH`; `ddd gui` started the way `gui/e2e/fixtures.ts` starts it (`DDD_PYTHON -m ddd gui --no-browser`, reading the address it prints).
- Produces: `npm run bench`, with `DDD_BENCH_PROJECT` naming a project description and `DDD_BENCH_OUT` naming a file the rows are appended to. Task 7 changes the Findings table it scrolls and keeps the measure's name.

`ddd gui` is started **without naming the project**, in the project's directory, so the measure starts where a reader's does: the start page, the project's button pressed. The measures, each capped at `CAP_MS = 120_000` - a measure that has not finished is written `> 120000`, never waited for longer - and each in a `test()` of its own over a fresh page, so a tab that froze in one does not freeze the next:

| Name | From | Until |
| --- | --- | --- |
| `answering` | the project's button on the start page pressed | the heading naming the project is visible |
| `first screen` | the same press | the canvas shows its first module |
| `Table`, `Units`, `Types`, `Shared files`, `Files`, `Findings` | the tab followed | the tab's table shows its first row, or its own sentence for having none - read each tab to know which |
| `typing` | twelve characters typed into the unit field of a variable's panel, 50 ms apart | the longest long task while typing, in ms (`0` if none) |
| `scrolling` | forty wheel steps of 600 px over the Findings table, 50 ms apart | the longest long task while scrolling |
| `apply shows` | Apply pressed on that variable's new unit | the component table's unit cell shows it |
| `findings current` | the same press | a `GET /api/state` answer whose `revision` is newer than the one before the press - a benchmark may wait on a response; a journey may not |

Long tasks are read with a `PerformanceObserver` for `longtask`, installed by `page.addInitScript` and read back with `page.evaluate`: a long task is reported only from 50 ms, so `0` means no stall of 50 ms or more. After `findings current`, press Undo, so the project is as generated for the next run.

- [ ] **Step 1: Write the config** - `gui/playwright.bench.config.ts`, `testDir: "bench"`, `testMatch: "*.bench.ts"`, one worker, `timeout: 300_000` per test, `reporter: "list"`, `use` with `browserName: "chromium"`, the channel from `PLAYWRIGHT_CHANNEL` exactly as `playwright.config.ts` has it, and a fixed `viewport` of 1280 x 800 so every run draws the same number of rows. A comment saying it is run by hand and why not in CI.
- [ ] **Step 2: Write `gui/bench/page.bench.ts`** - `test.describe.configure({ mode: "serial" })`; a `beforeAll` that throws `DDD_BENCH_PROJECT names no project description` when the variable is unset or names no file, starts `ddd gui` in `dirname(project)` and reads its address; an `afterAll` that stops it; one `test` per row above, each appending `| <project> | <measure> | <ms> |` to `DDD_BENCH_OUT` when set and printing it. The variable is picked the way a reader would pick one: the first component the Table tab lists, and that component's first row. The server half picks the middle of the sorted declarations instead; say so in a comment - the two measure different things (a panel drawn, a request answered) and need not name the same variable.
- [ ] **Step 3: Run it once on the smallest project** - `cd gui && DDD_BENCH_PROJECT="$BENCH/10000-many-clean/project.ddd.json" DDD_BENCH_OUT="$BENCH/page-trial.md" DDD_PYTHON="$PWD/../.venv/bin/python" PLAYWRIGHT_CHANNEL=chrome npm run bench; echo "EXIT=$?"`, and read every row: a measure of `0` ms or one that caps on a small project is the script's fault, not the page's.
- [ ] **Step 4: The page gate** - `npm run lint && npm run typecheck` over the new files (biome lints `bench/`; `tsconfig.json`'s `include` makes typecheck see them), then the rest of the page gate unchanged.
- [ ] **Step 5: The figures before** - alone on the machine, on eight projects: `10000`, `35000` and `100000` in the "many" shape, clean and heavy, and `35000-large-heavy` and `35000-mixed-heavy`. The other ten are measured after (Task 13); before, eight are enough to show what is slow, and each costs minutes of capped measures. Put them in *Figures* under **Page, before**.
- [ ] **Step 6: Commit.**

---

### Task 4: a revision's findings indexed once, and what is derived from it kept

**Model:** most capable (`opus`) - many endpoints, each of whose answers must not move by one finding.

**Files:**
- Create: `src/ddd/findings_by_file.py`, `src/ddd/gui/derived.py`, `tests/test_findings_by_file.py`
- Modify: `src/ddd/project_types.py` (`type_rows`, `row_of`), `src/ddd/project_shared.py` (`shared_rows`, `row_of`), `src/ddd/project_units.py` (`unit_rows`), `src/ddd/lsp/units.py` (`unit_project`), `src/ddd/file_plans.py` (its `Pair` imported, not spelled again), `src/ddd/gui/session.py` (`Session.edits`), `src/ddd/gui/api.py`
- Test: `tests/test_project_types.py`, `tests/test_project_shared.py`, `tests/test_unit_plans.py`, `tests/test_gui_api.py`

**Interfaces:**
- Consumes: `Revision.findings`, `Revision.files`, `Revision.number`; the predicates `ddd.variables.located_on`, `ddd.project_units.located_on_unit`, `ddd.project_types.located_in_type`, `ddd.project_shared.located_on`, unchanged.
- Produces: `FindingsByFile`, `Pair`; `derived(revision) -> Derived`; `Api._derive(revision)` and `Api._memoised(revision, key, make)`; `Session.edits`. Task 7 adds the Findings tab's order to `Derived`.

**Why.** *Measured while planning*: every per-name question - a variable's, a unit's, a type's, a shared entry's findings - is asked of every finding of the revision, each asking resolving two paths; `GET /api/variable` spent 2.9 s of 3.9 s (profiled) in `Path.resolve()` on a project of 66,005 findings. A finding can belong to a name only where it is shown on a file one of the name's places is in, so grouping the findings by resolved file once, and asking each predicate only of the files it can answer yes for, gives the same answer at a fraction of the cost. `GET /api/units` spent 1.4 s parsing every included file to find the units files among them. `shared_rows` asks every entry of every finding: O(entries x findings), 2 ms on the probe only because it declares no entry.

**The rule every change here keeps:** an answer is the same list, in the same order, as before. The order is the revision's - file by file in path order - so `FindingsByFile` remembers where each finding came and gives any subset back in that order.

- [ ] **Step 1: `FindingsByFile`, test first** - `tests/test_findings_by_file.py`:

```python
"""``ddd.findings_by_file``: findings grouped by resolved file, given back in the order given."""

from __future__ import annotations

from pathlib import Path

from ddd.diagnostics import Diagnostic, Location, Severity
from ddd.findings_by_file import FindingsByFile


def found(path: Path, pointer: str) -> Diagnostic:
    return Diagnostic("unused-output", Severity.WARNING, "not read", Location(path, pointer))


def test_a_file_is_asked_about_however_it_is_spelled(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    a = tmp_path / "a.ddd.json"
    pairs = [(a, found(a, "x")), (tmp_path / "sub" / ".." / "a.ddd.json", found(a, "y"))]
    grouped = FindingsByFile(pairs)
    assert grouped.on(tmp_path / "sub" / ".." / "a.ddd.json") == tuple(pairs)
    assert grouped.on(tmp_path / "b.ddd.json") == ()


def test_several_files_come_back_in_the_order_given_not_the_order_named(tmp_path: Path) -> None:
    a, b = tmp_path / "a.ddd.json", tmp_path / "b.ddd.json"
    pairs = [(a, found(a, "1")), (b, found(b, "2")), (a, found(a, "3"))]
    grouped = FindingsByFile(pairs)
    assert grouped.on_any([b, a, b]) == pairs
    assert list(grouped) == pairs


def test_each_file_is_resolved_once(tmp_path: Path, monkeypatch) -> None:
    a = tmp_path / "a.ddd.json"
    resolved: list[Path] = []
    real = Path.resolve
    monkeypatch.setattr(Path, "resolve", lambda self, strict=False: resolved.append(self) or real(self, strict))
    FindingsByFile([(a, found(a, str(n))) for n in range(5)])
    assert resolved == [a]
```

Check `Diagnostic`'s constructor against `ddd.diagnostics` before copying `found` - build it the way the nearest existing test does.

- [ ] **Step 2: Write `src/ddd/findings_by_file.py`** so they pass:

```python
"""Findings grouped by the file they are shown on, each file resolved once.

Every per-name question the browser interface asks - which findings are a variable's, a unit's,
a type's, a shared entry's - comes down to a finding shown on a file one of the name's places is
in. Asked finding by finding, each question resolved both paths: over a project of 66,005
findings ``GET /api/variable`` spent 2.9 s of its 3.9 s (profiled) in
:meth:`pathlib.Path.resolve`, the same 1,200 files resolved for every finding. Grouped here once,
a question reads only the findings of the files it is about, and gets them in the order they were
given - the revision's own - so that an answer asked this way is the answer asked of them all.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path

from ddd.diagnostics import Diagnostic

type Pair = tuple[Path, Diagnostic]
"""A finding and the file it is shown on."""


class FindingsByFile:
    """The findings of one analysis, each with the file it is shown on, grouped by that file
    resolved: each distinct file resolved once, however many findings it carries."""

    def __init__(self, pairs: Iterable[Pair]) -> None:
        self._pairs = tuple(pairs)
        resolved: dict[Path, Path] = {}
        grouped: dict[Path, list[int]] = {}
        for index, (file, _) in enumerate(self._pairs):
            key = resolved.get(file)
            if key is None:
                key = file.resolve()
                resolved[file] = key
            grouped.setdefault(key, []).append(index)
        self._grouped = {key: tuple(indexes) for key, indexes in grouped.items()}

    def __iter__(self) -> Iterator[Pair]:
        """Every finding, in the order given."""
        return iter(self._pairs)

    def on(self, path: Path) -> tuple[Pair, ...]:
        """The findings shown on ``path``, however it is spelled, in the order given."""
        return tuple(self._pairs[index] for index in self._grouped.get(path.resolve(), ()))

    def on_any(self, paths: Iterable[Path]) -> list[Pair]:
        """The findings shown on any of ``paths``, each once, in the order given - never in the
        order the paths are named, which would reorder a panel's list by its declarations."""
        indexes: set[int] = set()
        for path in paths:
            indexes.update(self._grouped.get(path.resolve(), ()))
        return [self._pairs[index] for index in sorted(indexes)]
```

`ddd.file_plans`' own `type Pair = tuple[Path, Diagnostic]` becomes `from ddd.findings_by_file import Pair` - one spelling of the alias - re-exported where `ddd.gui.api` imports it from `ddd.file_plans` today.

- [ ] **Step 3: The rows take `FindingsByFile`** - failing tests first, in `tests/test_project_types.py` and `tests/test_project_shared.py`: every existing call of `type_rows`, `row_of` and `shared_rows` wraps its list in `FindingsByFile(...)`, and one new test per module pins the order-and-subset rule - a finding filed at a type's entry on a file that also carries another type's finding counts on its own row only. Then the code:
  - `type_rows(built, findings: FindingsByFile, cache)`: its own `by_path` loop goes; each row counts `sum(1 for _, found in findings.on(site.path) if _within_entry(found, site))`. Its docstring's sentence about resolving once per finding becomes one about `FindingsByFile` doing it once per file.
  - `project_types.row_of(built, name, findings: FindingsByFile, cache)`: `located_in_type` asked only of `findings.on(site.path)`.
  - `shared_rows(built, findings: FindingsByFile, cache)` and `project_shared.row_of(vocabulary, built, name, findings: FindingsByFile, cache)`: `located_on` asked only of `findings.on_any(place.path for place in places)`, `places` being exactly what `located_on` itself compares against - the entry's site where declared, and every `vocabulary.used(built).get(name, ())`. Extract that list into one private function both read, so the candidates and the predicate cannot come to name different places. `shared_rows`' sentence about reading a generator into a list once goes; `FindingsByFile` is not spent by being read.
  - `unit_rows(built, findings: FindingsByFile, cache)`: the same iteration over `findings`; only its annotation and docstring change.
- [ ] **Step 4: `unit_project` parses only what can be a units file** - failing tests first in `tests/test_unit_plans.py`: (a) a units file whose key is written `"units"` is still found - the escape is why the check below looks for `\u`; (b) on a project of a component and a units file, the component is not in `cache` afterwards (it was never parsed); (c) the order of units files is still the includes' order. Then, in `ddd.lsp.units.unit_project`, skip a file for which `_may_list_units(file, cache)` is false:

```python
def _may_list_units(file: Path, cache: dict[Path, Document]) -> bool:
    """Whether ``file`` can be a units file at all, asked before parsing it: a document with
    ``units`` at its top spells that key in its text, as ``"units"`` or with an escape somewhere
    in it. A file already parsed is left to the parse. ``GET /api/units`` spent 1.4 s of its
    1.5 s (profiled) parsing every file of a 1,200-component project to find its one units file;
    reading them for two strings is what is left of that."""
    if file in cache:
        return True
    try:
        text = file.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return False
    return '"units"' in text or "\\u" in text
```

A file that cannot be read answers `False`, as `read` makes it an empty document that is no units file either - say so in a test.

- [ ] **Step 5: `Derived`** - `src/ddd/gui/derived.py`:

```python
"""What the api derives from one revision, derived once for it rather than once per request.

A revision is immutable, so anything computed from it alone holds for as long as it is the newest:
each file's description by resolved path, each finding's own file's, the findings grouped by file,
and how many findings each root entry carries. ``GET /api/state`` resolved every finding's file
to find its description; ``GET /api/files`` counted every finding once per entry.
"""

@dataclass(frozen=True, slots=True)
class Derived:
    number: int
    """The revision's, which is what says whether this is still the newest."""

    files: Mapping[Path, SourceFile]
    """Each file the revision read, by resolved path."""

    sources: tuple[SourceFile | None, ...]
    """Each finding's file as the revision describes it, in the revision's order: ``None`` for a
    file the revision did not list."""

    findings: FindingsByFile
    at_entry: Mapping[int, int]
    """How many findings are filed at ``project.includes[i]`` of the project description, by
    ``i``, compared as ``_at_entry`` compared them: the description's own path, the entry's
    pointer."""


def derived(revision: Revision) -> Derived: ...
```

`sources` is built by resolving each distinct finding file once (a dictionary from the path as filed to its description). `at_entry` counts, in one pass, each finding whose `location` equals `Location(revision.project, f"project.includes[{i}]")` for some `i` - read the index off the pointer with a regular expression anchored at both ends, and pin that `project.includes[2].x` is not the entry's.

- [ ] **Step 6: The api reads `Derived`, and keeps what it makes** - in `Api`:
  - `self._derived: Derived | None = None` and `self._memo: dict[tuple[object, ...], Reply] = {}`; `_derive(revision)` returns the kept one where its `number` is the revision's, else derives and keeps a new one **and empties `_memo`**; `_memoised(revision, key, make)` returns `_memo[(key, revision.number, self.session.edits)]`, making it once - `key` a tuple naming the answer, `("graph",)` or `("units",)`. Two requests of one revision that both find nothing kept both make it - harmless, and cheaper than a lock around a computation of hundreds of milliseconds; say so in its docstring.
  - `Session.edits`: a property answering `self._edits`, under the lock, documented as how many edits this session has written. It is in the key because an answer reading the files as they stand - a vocabulary's descriptions - changes with an edit before the analysis does, from Task 6 on.
  - `GET /api/graph`, `/api/units`, `/api/types`, `/api/shared`, `/api/files` answer through `_memoised`.
  - `_state`, `_variable`, `_unit`, `_type`, `_entry_findings`, `_values` and `_files` read `Derived`: `_state` takes each finding's description from `sources` by index; the per-name endpoints ask their predicate only of `derived.findings.on(...)`/`on_any(...)` over the name's places - a variable's declarations' files; a unit's stated sites' and vocabulary entries' files; a type's own file; a shared entry's places as Step 3 extracted them; a grid's own file - and look a candidate's description up in `files`. `_at_entry` goes: `_files` reads `at_entry.get(index, 0)`.
- [ ] **Step 7: Each answer equals the uncached computation** - in `tests/test_gui_api.py`, a class that opens copies of `examples/demo`, `examples/vocabulary` and `examples/structures` and, for **every** name each project declares, compares the endpoint's `findings` with an oracle written in the test the way the code was before this task: every finding of the revision, filtered by the same predicate, in order. Every variable of `index.declarations`, every unit of `index.units` and `index.vocabulary`, every type, every constant, section and raster, and the rows of `/api/units`, `/api/types` and `/api/shared` against `unit_rows`/`type_rows`/`shared_rows` given every finding. A project where a finding sits on a name's place *through another spelling of its path* - a symlinked directory, as `tests/test_gui_api.py` already builds for other reasons - is one of them. And for the memo: the same revision answers `/api/graph` with the very same `Reply` (`is`), a new revision - an edit made and analysed - with a new one showing the change.
- [ ] **Step 8: Measure** - the server benchmark on `$BENCH/35000-many-heavy` and `$BENCH/100000-many-heavy`, alone on the machine; the figures into your report beside Task 2's for the same projects. Nothing here changes `open`, `analysis` or the edit.
- [ ] **Step 9: Ablate** - in a scratch worktree: `on_any`'s `sorted(indexes)` to `indexes` in insertion order (the order test and the panel oracles must die); `_may_list_units`' `"\\u"` removed (the escaped-key test); `at_entry`'s anchoring removed; `_derive` never re-deriving (`is not None` alone - the new-revision memo test).
- [ ] **Step 10: Both gates, then commit.**

---

### Task 5: the background analyser, its answers still waited for

**Model:** most capable (`opus`) - concurrency.

**Files:**
- Modify: `src/ddd/gui/session.py`, `src/ddd/gui/api.py` (`_open`, `_edit`, `_apply_undo` wait with `settled`), `src/ddd/gui/server.py` (`run` starts the analyser)
- Test: `tests/conftest.py` (`Gated`, `begun`), `tests/test_gui_session.py`, `tests/test_gui_server.py`

**Interfaces:**
- Consumes: `Session._analysed(project)`, `_confined`, `apply_changes`, `restore`, `stamped`, `UNKNOWN`; `ddd.loading.included_files`.
- Produces: `Session.open -> None`, `edit -> (at, written)`, `undo -> int`, `poll -> bool`, `start()`, `settled(timeout)`, `project`, and `Revision.edits`. **The api's answers do not change in this task**: `_open`, `_edit` and `_apply_undo` call `settled(None)` and answer the revision as before, and `run` waits for the first analysis before it serves. Task 6 removes those waits.

**Why a task of its own.** The analyser is the one piece of this part that can deadlock, lose an edit or publish the wrong project, and none of that shows in a page. Landing it behind the answers the page already gets lets a reviewer judge the concurrency alone, and every existing test of the api and of the journeys still passes over it unchanged - which is itself the first proof it is right.

**The design** (spec §5, §7):

- **One lock, one condition on it.** `_lock` guards the open project, the newest revision, the undo stack, `_edits`, the request (`_asked`, `_running`) and the stamps (`_signature`, `_fresh`), and every write happens under it. An analysis runs **outside** it, so an edit is written while one runs. `_changed` is a `threading.Condition` on the same lock, notified whenever any of those changes.
- **Every request asks the same way.** Opening, an edit, an undo and a poll noticing a change set `_asked` to the open project (`_request`). A request landing while an analysis runs finds `_asked` already set or sets it again: one analysis follows the running one, of the disk as it then stands - never a queue.
- **Two ways to run.** After `start()`, the analyser thread takes each request (`_analyse_until_stopped`), and the call that asked answers at once. Without it - every test not about the analyser, and any session nobody started - the call makes the analysis itself before answering (`_analyse_here`), as every call did before this task, and a failure is raised to it.
- **Stamps before the read.** An analysis begins by stamping every file of the last revision, and every file written or named since (`_fresh`), before it reads one; those become the revision's stamps when it is published. While it runs, the stamps it took stand in for the old ones, so the poll does not take its own edit's write for a change the running analysis missed. **A file an edit created is in `_fresh`, stamped from its own write, and costs no second analysis** (spec §5). **Opening a project puts the description and the files its own includes name in `_fresh`** - the loader's rule, `included_files` - so opening a flat project analyses once; a sub-project's files still have no stamp and cost the analysis more they always did (ruling 5).
- **Numbers.** Revisions keep one count across projects (`_numbered`), so a number never names two answers. An undo takes a number of its own from `_edits`, as an edit does; a revision records in `edits` the last one on disk when its analysis began.
- **Another project.** Opening one while an analysis runs asks for the new project's; the running one's revision is thrown away when it finishes.
- **A failure.** An exception out of an analysis on the thread is printed - `ddd gui: analysing the project failed: <error>` - and the files it stamped are stamped unknown, so the next poll asks again: never a dead thread, never `analysing` left set (spec §7).

- [ ] **Step 1: The failing tests** - `Gated` and `begun` in `tests/conftest.py`, since Task 6's api tests use them too, and the classes in `tests/test_gui_session.py`:

```python
class Gated(Session):
    """A session whose analyses are counted, announce that they have begun, and wait at a gate
    the test opens: what lets a test land an edit while an analysis runs without sleeping."""

    def __init__(self, root: Path) -> None:
        # Polling an hour apart: the poller start() starts never polls while a test runs.
        super().__init__(root, poll_interval=3600)
        self.begun = threading.Semaphore(0)
        self.gate = threading.Event()
        self.analyses = 0

    def _analysed(self, project: Path) -> Revision:
        self.analyses += 1
        self.begun.release()
        assert self.gate.wait(timeout=10), "the test never opened the gate"
        return super()._analysed(project)


def begun(session: Gated) -> None:
    """Wait until one more analysis has begun."""
    assert session.begun.acquire(timeout=10), "no analysis began"


class TestTheAnalyser:
    def test_an_edit_answers_before_its_analysis_and_the_next_revision_includes_it(
        self, shared: Path
    ) -> None:
        session = Gated(shared.parent)
        session.gate.set()
        session.start()
        try:
            session.open(shared)
            begun(session)
            assert session.settled(timeout=10) is not None
            session.gate.clear()
            at, _ = session.edit([unit_of_b(shared, "Hz")], "the unit of Speed")
            begun(session)
            revision = session.revision
            assert revision is not None and revision.edits < at and mismatches(session) == 0
            session.gate.set()
            settled = session.settled(timeout=10)
            assert settled is not None and settled.edits == at and mismatches(session) == 2
        finally:
            session.gate.set()
            session.stop()

    def test_edits_landing_while_an_analysis_runs_make_one_analysis_more_not_one_each(
        self, shared: Path
    ) -> None:
        session = Gated(shared.parent)
        session.gate.set()
        session.start()
        try:
            session.open(shared)
            begun(session)
            session.settled(timeout=10)
            session.gate.clear()
            session.edit([unit_of_b(shared, "Hz")], "one")
            begun(session)
            last = 0
            for unit in ("kPa", "Nm", "rpm"):
                last, _ = session.edit([unit_of_b(shared, unit)], unit)
            session.gate.set()
            settled = session.settled(timeout=10)
            assert settled is not None and settled.edits == last
            assert session.analyses == 3  # opening, the first edit, and the three after it
        finally:
            session.gate.set()
            session.stop()

    def test_a_project_opened_while_another_is_analysed_throws_that_analysis_away(
        self, shared: Path
    ) -> None:
        write_tree(shared.parent, {"q.ddd.json": project("Q", "a.ddd.json")})
        other = shared.parent / "q.ddd.json"
        session = Gated(shared.parent)
        session.start()
        try:
            session.open(shared)
            begun(session)
            session.open(other)
            session.gate.set()
            settled = session.settled(timeout=10)
            assert settled is not None and settled.project == other.resolve()
            assert (settled.number, session.analyses) == (1, 2)
        finally:
            session.gate.set()
            session.stop()

    def test_an_analysis_failing_on_the_thread_is_printed_and_asked_for_again(
        self, shared: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        class Failing(Gated):
            def _analysed(self, project: Path) -> Revision:
                revision = super()._analysed(project)
                if self.analyses == 2:
                    raise RuntimeError("boom")
                return revision

        session = Failing(shared.parent)
        session.gate.set()
        session.start()
        try:
            session.open(shared)
            first = session.settled(timeout=10)
            at, _ = session.edit([unit_of_b(shared, "Hz")], "the unit of Speed")
            assert session.settled(timeout=10) is first
            assert capsys.readouterr().err.splitlines()[-1] == (
                "ddd gui: analysing the project failed: boom"
            )
            assert session.poll() is True
            settled = session.settled(timeout=10)
            assert settled is not None and settled.edits == at and mismatches(session) == 2
        finally:
            session.stop()

    def test_stopping_ends_the_analyser_and_the_poller(self, shared: Path) -> None:
        session = Gated(shared.parent)
        session.gate.set()
        session.start()
        session.open(shared)
        session.settled(timeout=10)
        session.stop()
        assert session._analyser is not None and not session._analyser.is_alive()
        assert session._poller is not None and not session._poller.is_alive()

    def test_settled_answers_after_its_timeout_while_an_analysis_waits(self, shared: Path) -> None:
        session = Gated(shared.parent)
        session.start()
        try:
            session.open(shared)
            begun(session)
            assert session.settled(timeout=0.01) is None
        finally:
            session.gate.set()
            session.stop()


class TestStamps:
    def test_opening_a_project_analyses_it_once(self, shared: Path) -> None:
        session = Session(shared.parent)
        session.open(shared)
        assert session.poll() is False
        assert session.revision is not None and session.revision.number == 1

    def test_a_sub_projects_files_still_cost_opening_one_analysis_more(self, tmp_path: Path) -> None:
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "sub/s.ddd.json"),
                "sub/s.ddd.json": project("S", "c.ddd.json"),
                "sub/c.ddd.json": component("C", declare("output", "Speed", unit="rpm")),
            },
        )
        session = Session(tmp_path)
        session.open(tmp_path / "p.ddd.json")
        assert session.poll() is True
        assert session.poll() is False

    def test_a_file_an_edit_created_costs_no_second_analysis(self, shared: Path) -> None:
        session = Session(shared.parent)
        session.open(shared)
        session.edit(adoption(shared), "the vocabulary")
        assert session.poll() is False

    def test_an_undo_takes_a_number_of_its_own_and_the_revision_includes_it(
        self, shared: Path
    ) -> None:
        session = Session(shared.parent)
        session.open(shared)
        at, _ = session.edit([unit_of_b(shared, "Hz")], "the unit of Speed")
        undone = session.undo(at)
        assert undone == at + 1
        assert session.revision is not None and session.revision.edits == undone
```

Check each against the helpers it uses before trusting it: `project(name, *includes)` and `component`/`declare` from `tests/conftest.py`, and a sub-project's includes read relative to its own directory, as `examples/demo`'s `subsystems/logging` is. `test_after_the_one_analysis_more_opening_costs_an_unchanged_project_is_left_alone` pinned the cost this task removes: it becomes `test_opening_a_project_analyses_it_once`, its docstring saying why. Every other existing session test keeps passing as written - they run with no analyser started - except where `edit` and `undo` now answer numbers: adjust those call sites, never what they assert.

- [ ] **Step 2: Run them to see them fail** - `.venv/bin/python -m pytest tests/test_gui_session.py --no-cov`: `start`, `settled` and `Revision.edits` do not exist, `edit` answers a revision.

- [ ] **Step 3: The session.** `Revision` gains, after `served`:

```python
    edits: int = 0
    """The last edit or undo on disk when this revision's analysis began: every one numbered up
    to it was written before the analysis read a file. ``0`` where the session has written
    none."""
```

and `Session` becomes (`_analysed`, `read_file`, `undoable` and the module's functions unchanged but for `_analysed` numbering its revision `0` - `_published` numbers it; `_publish` goes):

```python
@dataclass(frozen=True, slots=True)
class _Begun:
    """An analysis begun: the project it reads, the stamps its revision is published with -
    taken before it read a file - and the last edit already on disk."""

    project: Path
    stamps: dict[Path, tuple[int, int] | None]
    edits: int


class Session:
    """One open project at a time, analysed into numbered revisions by one analysis at a time.

    Everything that asks for an analysis - opening a project, an edit, an undo, the poll noticing
    that a file changed - asks it the same way, and one asked for while another runs is merged
    with any other: one analysis follows, of the disk as it then stands, never a queue. Once
    :meth:`start` has started the analyser, it runs them on a thread of its own and whatever
    asked answers at once; where nothing started it - every test not about it, and a session
    nobody started - whatever asked makes the analysis itself before it answers.

    One lock guards the project, its newest revision, the undo stack, the counters, the request
    and the stamps, and every write is made holding it. An analysis runs without it, which is
    what lets an edit be written while one runs.
    """

    def __init__(
        self, root: Path, build_directories: Sequence[Path] = (), *, poll_interval: float = 1.0
    ) -> None:
        self.root = root.resolve()
        self.build_directories = tuple(build_directories)
        self.poll_interval = poll_interval
        self._lock = threading.Lock()
        self._changed = threading.Condition(self._lock)
        self._project: Path | None = None
        self._revision: Revision | None = None
        self._numbered = 0
        self._stack: list[Undoable] = []
        self._edits = 0
        self._signature: dict[Path, tuple[int, int] | None] = {}
        self._fresh: set[Path] = set()
        self._asked: Path | None = None
        self._running = False
        self._stopping = threading.Event()
        self._poller: threading.Thread | None = None
        self._analyser: threading.Thread | None = None

    @property
    def project(self) -> Path | None:
        """The project open, analysed yet or not; ``None`` while none is."""
        return self._project

    @property
    def revision(self) -> Revision | None:
        """The open project's newest revision, or ``None`` while it has none yet."""
        return self._revision

    @property
    def edits(self) -> int:
        """How many edits and undos this session has written: the number the last one took."""
        with self._lock:
            return self._edits

    def open(self, project: Path) -> None:
        """Open a project description, replacing the project open before it, and ask for its
        first analysis."""
        path = project.resolve()
        if not _is_project(path):
            raise ValueError(f"{project} is not a project description")
        with self._lock:
            self._project = path
            self._revision = None
            self._stack = []
            self._signature = {}
            self._fresh = _named_by(path)
            self._request()
        self._analyse_here()

    def settled(self, timeout: float | None) -> Revision | None:
        """The newest revision once no analysis is asked for or running, or once ``timeout``
        seconds have passed; ``None`` waits as long as that takes."""
        with self._changed:
            self._changed.wait_for(lambda: self._asked is None and not self._running, timeout)
            return self._revision

    def wait(self, after: int, timeout: float) -> Revision | None:
        """The newest revision as soon as it is newer than ``after``, or after ``timeout``."""
        with self._changed:
            self._changed.wait_for(
                lambda: self._revision is not None and self._revision.number > after, timeout
            )
            return self._revision

    def poll(self) -> bool:
        """Ask for an analysis if a file of the open project changed on disk since its stamps
        were taken; say whether one did."""
        with self._lock:
            if self._project is None or stamped(self._signature) == self._signature:
                return False
            self._request()
        self._analyse_here()
        return True

    def start(self) -> None:
        """Analyse on a thread of its own from now on, and poll on another, until :meth:`stop`."""
        if self._analyser is None:
            self._analyser = threading.Thread(
                target=self._analyse_until_stopped, name="ddd-gui-analyse", daemon=True
            )
            self._analyser.start()
        self.start_polling()

    def start_polling(self) -> None:
        """Poll every ``poll_interval`` seconds on a thread of its own, until :meth:`stop`."""
        if self._poller is None:
            self._poller = threading.Thread(
                target=self._poll_until_stopped, name="ddd-gui-poll", daemon=True
            )
            self._poller.start()

    def stop(self) -> None:
        """End the analyser and the poller, each once its current round is done."""
        self._stopping.set()
        with self._changed:
            self._changed.notify_all()
        for thread in (self._poller, self._analyser):
            if thread is not None:
                thread.join()

    def edit(
        self, changes: Sequence[FileChange], label: str
    ) -> tuple[int, tuple[Written, ...]]:
        """Make an edit of description files of the open project, ask for its analysis, and
        answer the number it took and what it wrote.

        (the rest of today's docstring, on creating a file and on ``label``, kept)
        """
        with self._lock:
            revision = self._required()
            confined = [_confined(revision, pending, changes) for pending in changes]
            written = apply_changes(confined)
            self._edits += 1
            self._stack.append(Undoable(self._edits, label, written))
            del self._stack[:-MAX_UNDO]
            self._fresh |= {file.path for file in written}
            self._request()
            at = self._edits
        self._analyse_here()
        return at, written

    def undo(self, at: int) -> int:
        """Put the edit numbered ``at`` back, pop it, ask for an analysis, and answer the number
        the undo took.

        (the rest of today's docstring, on the top of the stack and a refusal, kept)
        """
        with self._lock:
            self._required()
            top = self._stack[-1] if self._stack else None
            if top is None or top.at != at:
                raise EditError(STALE, f"edit {at} is not the one to undo any more")
            restore(top.files)
            self._stack.pop()
            self._edits += 1
            self._fresh |= {file.path for file in top.files}
            self._request()
            number = self._edits
        self._analyse_here()
        return number

    def _request(self) -> None:
        """Ask for an analysis of the open project. Holding the lock, with a project open."""
        self._asked = self._project
        self._changed.notify_all()

    def _analyse_here(self) -> None:
        """Make the analyses asked for on this thread, where no analyser was started."""
        if self._analyser is not None:
            return
        begun = self._next(wait=False)
        while begun is not None:
            self._run(begun, raising=True)
            begun = self._next(wait=False)

    def _analyse_until_stopped(self) -> None:
        while not self._stopping.is_set():
            begun = self._next(wait=True)
            if begun is not None:
                self._run(begun, raising=False)

    def _next(self, *, wait: bool) -> _Begun | None:
        """The analysis to make next, begun - its stamps taken before it reads a file - or
        ``None`` where there is none to make; after waiting for one, where asked to, until the
        session stops."""
        with self._changed:
            if wait:
                self._changed.wait_for(
                    lambda: self._stopping.is_set()
                    or (self._asked is not None and not self._running)
                )
            project = self._asked
            if project is None or self._running or self._stopping.is_set():
                return None
            self._asked = None
            self._running = True
            stamps = stamped(set(self._signature) | self._fresh)
            self._fresh = set()
            self._signature = dict(stamps)
            return _Begun(project, stamps, self._edits)

    def _run(self, begun: _Begun, *, raising: bool) -> None:
        try:
            revision = self._analysed(begun.project)
        except Exception as error:
            with self._changed:
                self._failed(begun)
            if raising:
                raise
            # A thread that dies here leaves a page that never updates again, and nothing says
            # why: the one line is that reason, and the next poll asks again.
            print(f"ddd gui: analysing the project failed: {error}", file=sys.stderr)
            return
        with self._changed:
            self._published(begun, revision)

    def _published(self, begun: _Begun, revision: Revision) -> None:
        """Make what an analysis made the newest revision, its files stamped as they were before
        it read them - a file with no stamp from before :data:`UNKNOWN` - unless the project it
        read is no longer the one open. Holding the lock.

        (keep the two paragraphs of today's ``_publish`` docstring on why before and never after)
        """
        self._running = False
        if begun.project == self._project:
            self._numbered += 1
            self._revision = replace(revision, number=self._numbered, edits=begun.edits)
            self._signature = {
                file.path: begun.stamps.get(file.path, UNKNOWN) for file in revision.files
            }
        self._changed.notify_all()

    def _failed(self, begun: _Begun) -> None:
        """What an analysis that raised leaves: nothing published, and - where its project is
        still the one open - every file it stamped stamped unknown, so the next poll asks again.
        Holding the lock."""
        self._running = False
        if begun.project == self._project:
            self._signature = dict.fromkeys(begun.stamps, UNKNOWN)
        self._changed.notify_all()
```

and, beside `_is_project`:

```python
def _named_by(project: Path) -> set[Path]:
    """The project description and every file its own ``includes`` name now, by the loader's own
    rule: what the first analysis of a project is about to read, stamped before it reads them so
    that opening a project analyses it once. A sub-project's ``includes`` are not read; its
    files have no stamp from before, and cost the one analysis more opening always cost."""
    named = {project}
    data = _read_json(project)
    block = data.get("project") if isinstance(data, dict) else None
    listed = block.get("includes") if isinstance(block, dict) else None
    for entry in listed if isinstance(listed, list) else []:
        named.update(included_files(project, entry))
    return named
```

`_poll_until_stopped` is unchanged. The module docstring's first paragraph now says a revision is made by one analysis at a time on a thread of its own, and that an edit is written at once and analysed after (while the api waits for it until Task 6 - say so, and have Task 6 take the clause out).

Check before trusting the code: that `_confined`'s paths and `revision.files`' paths compare equal for a created file (both resolved), since `_fresh`'s stamp is looked up by the path the analysis files it under - the created-file test is what proves it.

- [ ] **Step 4: The api waits, for now** - `_open` calls `self.session.open(wanted)` then `self.session.settled(None)`; `_edit` takes `at, written` from `edit`, calls `settled(None)` and answers `EditReply(revision=self._opened().number, ...)` as before; `_apply_undo` likewise. A comment at each says the wait goes in Task 6. `run` in `server.py` calls `session.start()` before opening and `session.settled(None)` after, so the first address it prints still serves an analysed project; `session.stop()` in its `finally` ends both threads. `tests/test_gui_server.py`'s calls of `run` must still pass as written.
- [ ] **Step 5: Run the session tests, then the whole Python gate.** Every api test passes unchanged - that is this task's claim; any that does not is a behaviour change to explain in your report, never to patch over.
- [ ] **Step 6: The journeys** - `npm run build` then the journeys, alone: all pass, since the page gets the answers it always got.
- [ ] **Step 7: Ablate** - in a scratch worktree: `_next` stamping after the analysis instead of before (move the `stamped` call into `_published`: the save-while-analysing tests must die); `_fresh |= ...` removed from `edit` (the created-file test); `_named_by` answering `{project}` alone (the opened-once test); the `begun.project == self._project` guard in `_published` removed (the other-project test); the thread's `except` narrowed to `ValueError` (the failure test).
- [ ] **Step 8: Commit.**

---

### Task 6: edits answer once written, and the page follows the analyser

**Model:** most capable (`opus`) - the contract changes under the page, and the page must follow it in the same commit.

**Files:**
- Modify: `src/ddd/gui/session.py` (`Snapshot`, `snapshot`, `wait` by version, `current`, `NotAnalysedError`, `unanalysed`), `src/ddd/gui/api.py`, `src/ddd/gui/contract.py` (`State`, `EditReply`, `UndoReply`), `src/ddd/gui/server.py`, `tools/bench_gui.py`
- Modify (page): `gui/src/api/client.ts`, `gui/src/state/revisions.ts`, `gui/src/app/useProjectState.ts`, `gui/src/app/App.tsx`, `gui/src/stories/fixtures.ts`
- Create (page): `gui/src/state/edits.ts`, `gui/src/lib/updating.ts`, and their tests
- Test: `tests/test_gui_session.py`, `tests/test_gui_api.py`, `tests/test_gui_server.py`, `tests/test_gui_contract.py`, `tests/test_bench_gui.py`, `gui/src/api/client.test.ts`, `gui/src/state/revisions.test.ts`

**Interfaces:**
- Consumes: Task 5's session; `Gated` and `begun` from `tests/conftest.py`.
- Produces: `Snapshot`, `Session.snapshot()`, `Session.wait(after, timeout) -> Snapshot` (**`after` is a version now**), `Session.current()`, `NotAnalysedError`, `Session.unanalysed(revision)`, `ANALYSING`; `State.version`, `State.analysing`, `State.edits` (and `State.revision == 0` before the first analysis); `EditReply.edit`, `UndoReply.edit`; on the page `OwnEdits`/`ownEdits`, `analysed`, `updatingOf`, `followStates`, and `useProjectState`'s `{ state, latest, updating, stopped, failure }`. Task 7 drops `State.findings`; Task 8 draws `updating`.

**What changes for a reader:** Apply answers as soon as the files are written, and the change shows where it was made; the findings follow the analysis. Opening a project answers at once, with its name and "Analysing the project…" until the first analysis lands. **A plan changing a file an unanalysed edit wrote is refused**, in the panel's own refusal line: `an edit that wrote b.ddd.json has not been analysed yet, so this change can be planned once it has` - it would otherwise carry the fingerprint the analysis read the file at and be refused as stale on Apply, and its pointers would come from an index of bytes no longer on disk (ruling 3). A plan changing only files nobody wrote since is computed against the newest revision at once, as the spec's §5 says.

- [ ] **Step 1: The session's version, snapshot and unanalysed writes** - failing tests first in `tests/test_gui_session.py`, then:

```python
class NotAnalysedError(RuntimeError):
    """Asked about the open project before any analysis of it has finished."""


@dataclass(frozen=True, slots=True)
class Snapshot:
    """What the session says at one moment, every part of it read at once: what
    ``GET /api/state`` answers."""

    version: int
    """Counts up at every change of anything else here - an analysis asked for, one published
    or failed, an edit or an undo written: what a long poll waits past."""

    project: Path | None
    revision: Revision | None
    analysing: bool
    """Whether an analysis is asked for or running: the findings may be about to change."""

    undoable: Undoable | None
```

`Session` gains `self._version = 0`, bumped in `_request`, `_published` and `_failed` just before their `notify_all`; `self._written: list[tuple[int, frozenset[Path]]] = []`, appended in `edit` (`(at, frozenset(file.path for file in written))`) and `undo` (the undone files), emptied by `open`, and pruned in `_published` to the entries numbered after the published revision's `edits`; and:

```python
    def snapshot(self) -> Snapshot:
        with self._lock:
            return self._snapshot()

    def wait(self, after: int, timeout: float) -> Snapshot:
        """What the session says as soon as its version is past ``after``, or after
        ``timeout``."""
        with self._changed:
            self._changed.wait_for(lambda: self._version > after, timeout)
            return self._snapshot()

    def current(self) -> Revision:
        """The open project's newest revision, refusing where there is none: no project open, or
        no analysis of it finished yet."""
        with self._lock:
            return self._required()

    def unanalysed(self, revision: Revision) -> frozenset[Path]:
        """Every file an edit or an undo wrote after ``revision``'s analysis began: numbered past
        its ``edits``. A revision older than the newest may miss some the newest already
        includes; the engine's own fingerprint check still refuses a plan made against it."""
        with self._lock:
            waiting: set[Path] = set()
            for number, paths in self._written:
                if number > revision.edits:
                    waiting |= paths
            return frozenset(waiting)

    def _snapshot(self) -> Snapshot:
        return Snapshot(
            self._version,
            self._project,
            self._revision,
            self._asked is not None or self._running,
            self._stack[-1] if self._stack else None,
        )

    def _required(self) -> Revision:
        if self._project is None:
            raise NoProjectError("no project is open")
        if self._revision is None:
            raise NotAnalysedError("the open project has not been analysed yet")
        return self._revision
```

`_snapshot`'s conditional expressions register no branch; the test that reads a snapshot with an empty stack and one with an entry is what pins both - write it.

- [ ] **Step 2: The contract** - failing tests in `tests/test_gui_contract.py` first (the fields and their docstrings are what `npm run schemas` turns into the page's types). `State` gains, after `revision`:

```python
    version: int
    """Counts up at every change of what this reply says - an analysis asked for, published or
    failed, an edit or an undo written: what a later ``?after=`` waits past."""
```

and, after `undoable`:

```python
    analysing: bool
    """Whether an analysis is asked for or running: the findings may be about to change."""

    edits: int
    """The last edit or undo this revision's analysis includes - every one numbered up to it was
    on disk when the analysis read the files - ``0`` where there is none."""
```

`revision`'s docstring says `0` before the open project's first analysis, when `files` and `findings` are empty. `EditReply.revision` becomes `edit: int` ("the number the session gave this edit: a revision whose `edits` has reached it includes it") and `UndoReply.revision` becomes `edit: int` likewise.

- [ ] **Step 3: The api** - failing tests in `tests/test_gui_api.py` first, then:
  - `ANALYSING: Final = "analysing"`, documented as the refusal of a request the analysis has not caught up with; `REFUSALS` gains it; `handle` answers `NotAnalysedError` 409 `analysing` with its sentence.
  - `_state` answers `self.session.snapshot()`, or `self.session.wait(after, self.wait_seconds)` where `?after=` is given, and refuses `no project is open` where the snapshot has none. The body - revision `0`, no files and no findings before the first analysis - is kept per version: `self._state_kept: tuple[int, Reply] | None`, rebuilt only when the version moved.
  - `_edit` answers `EditReply(edit=at, files=...)` without waiting; `_apply_undo` answers `UndoReply(edit=number)`; `_open` answers `_session_body()` without waiting. Task 5's three `settled(None)` calls go.
  - `_session_body` names `self.session.project` - its name read off the description with `_name_in(_read_json(project), "project")` - so a project being analysed is named at once; `builds` stay the revision's, empty before it.
  - `_opened` is `self.session.current()`; `_dictionary` and `_graph` read the revision through it, so asking before the first analysis answers `analysing`, never `no project is open`.
  - Every plan endpoint - `_unit_plan`, `_type_plan`, `_shared_plan` (three vocabularies), `_files_plan`, `_settle`, `_fix`, `_declaration_plan`, `_value_plan`, `_values_plan` - calls, first inside the `try` that already catches `EditError` around its preview:

```python
    def _refuse_unanalysed(self, revision: Revision, paths: Iterable[Path]) -> None:
        """Refuse a plan changing a file an edit wrote since ``revision``'s analysis began.

        Computed all the same, it would carry the fingerprint the analysis read that file at, and
        the edit engine would refuse its Apply as stale; and where it points into the file comes
        from an index of bytes no longer on disk. A plan changing only files nobody wrote since is
        made against ``revision`` at once, never waiting for the analysis (spec §5)."""
        waiting = self.session.unanalysed(revision)
        named: list[str] = []
        for path in paths:
            resolved = path.resolve()
            if resolved in waiting and resolved.name not in named:
                named.append(resolved.name)
        if named:
            raise EditError(
                ANALYSING,
                f"an edit that wrote {', '.join(named)} has not been analysed yet, "
                "so this change can be planned once it has",
            )
```

  with the paths of the plan's own edits (`plan.edits`, a settlement's declarations, each fix's changes - read each endpoint to find them).
  - `_memoised`' key keeps `self.session.edits`: from now on an edit changes what a vocabulary's rows read before the analysis moves the revision, and a test says so - a unit's description changed by an edit shows in `GET /api/units` before its analysis lands.
- [ ] **Step 4: The tests of Step 3** - each with a `Gated` session, started, its gate closed at the moment that matters:
  - `GET /api/state` before the first analysis: revision `0`, `analysing` true, no files, the project named; and every endpoint needing a revision answers 409 `analysing`, `the open project has not been analysed yet`.
  - `POST /api/edit` answers `{"edit": 1, "files": [...]}` while its analysis waits at the gate; `GET /api/state` then says `analysing`, `edits` below 1, the undo entry already the edit's; with the gate opened, `edits` is 1.
  - **A second window**: `GET /api/state?after=<version>` waiting in a thread answers as soon as the edit is written - with `analysing` true - not when its analysis lands.
  - **Every plan endpoint** refuses a plan of a file the waiting edit wrote with the whole sentence, and answers a plan of a file it did not write (spec §5). One test per endpoint, parametrised where the fixture allows.
  - `GET /api/session` names the project before its first analysis.
  - **The Files tab's judge while an edit waits** (spec §5): a removal asked while an edit of a *component* waits for its analysis is refused `stale` in the words it answers today, naming the component - `_refuse_unanalysed` does not reach it, the plan changing the description alone - and one asked while an edit of the *description* waits is refused `analysing`.
- [ ] **Step 5: The server** - `run` starts the session (`session.start()`) and then opens the project without waiting: `ddd gui PROJECT` prints its address before the first analysis. Every path out of `run` stops what it started - a refused project, a port that cannot be bound, an interrupt. `_sign_in` sends a page to `/project` where `session.project` is set, analysed yet or not.
- [ ] **Step 6: The benchmark** - `measure` starts the session's analyser: `open` is `open` then `settled(None)`, `analysis` the poll then `settled(None)`, `edit answered` the reply, `edit analysed` until `settled(None)`; `stop()` at the end. The names and their meanings do not change; `tests/test_bench_gui.py` passes as written.
- [ ] **Step 7: The page's own edits** - `gui/src/state/edits.ts`:

```ts
/**
 * The newest edit or undo this page wrote, by the number the server answered it with
 * (`EditReply.edit`, `UndoReply.edit`): what says whether the revision on screen has caught up
 * with the page's own change, in the moment before the state says it is being analysed.
 * One per page, beside the client that notes into it; a test makes its own.
 */
export class OwnEdits {
  #newest = 0;
  readonly #listeners = new Set<() => void>();

  /** Notes an edit written; listeners hear of it only when it is newer than every one before. */
  readonly wrote = (edit: number): void => {
    if (edit <= this.#newest) return;
    this.#newest = edit;
    for (const listener of this.#listeners) listener();
  };

  readonly newest = (): number => this.#newest;

  /** For `useSyncExternalStore`: answers the function that stops the listening. */
  readonly subscribe = (listener: () => void): (() => void) => {
    this.#listeners.add(listener);
    return () => {
      this.#listeners.delete(listener);
    };
  };
}

export const ownEdits = new OwnEdits();
```

`postEdit` and `postUndo` in `client.ts` take a last parameter `edits: OwnEdits = ownEdits` and note `reply.edit` once the answer arrives; a refused edit notes nothing. `getState`'s doc says `after` is a version.

- [ ] **Step 8: The two decisions** - `gui/src/lib/updating.ts`:

```ts
import type { State } from "../api/types";

/** Whether a state holds an analysed revision: `0` is the open project's before its first. */
export function analysed(state: Pick<State, "revision">): boolean {
  return state.revision > 0;
}

/** Whether the findings on screen may be about to change (spec §6): an analysis is asked for or
 * running, or the page's own last edit is newer than the revision it holds - which covers the
 * moment between an edit's answer and the state saying it is being analysed. */
export function updatingOf(state: Pick<State, "analysing" | "edits">, ownEdit: number): boolean {
  return state.analysing || ownEdit > state.edits;
}
```

- [ ] **Step 9: Following by version** - `followRevisions` becomes `followStates`, `after` the version of the state it holds, a state handed on when `after === null || state.version > after`; its docstring says a state can be new with the same revision - an analysis beginning, an edit written. Its tests move with it, and one pins that a state whose version grew and whose revision did not is handed on.
- [ ] **Step 10: The page** - `useProjectState` keeps `latest` (every state followed, revision `0` included), reads the page's own last edit with `useSyncExternalStore(ownEdits.subscribe, ownEdits.newest)`, and answers `state` (`latest` where `analysed(latest)`, else `null`), `latest`, `updating` (`latest !== null && updatingOf(latest, ownEdit)`), `stopped` and `failure`. In `App.tsx`, while a project is open and `state` is `null`, the project and component routes draw the heading - the name `GET /api/session` gave - and, in place of the tab's screen, `<p className="quiet">Analysing the project…</p>`: no screen asks the server anything before the first analysis, which also ends the graph being fetched once with no revision (*Measured while planning*). `updating` is only passed on here; Task 8 draws it. `gui/src/stories/fixtures.ts`' states gain `version`, `analysing: false` and `edits`.
- [ ] **Step 10b: The change shows where it was made** (spec §6: "the fields and values an edit wrote show that edit at once"). Until now a screen could rely on the revision moving after its Apply to read again what it shows; from this task the revision moves an analysis later. Read every `onSettled` of every screen that posts an edit or an undo - `UnitsPage`, `UnitPanel`, `TypePanel`, `ConstantPanel`, `SectionPanel`, `RasterPanel`, `SharedPage`, `DeclarePanel`, `VariablePanel` (both), `ValuesPage`, `FilesPage`, `FindingsPage`, `UndoStrip` - and make sure each asks again for every query that draws what its edit wrote: the component page's `["file", ...]`, the panel's own reply, the tab's rows. List in your report each one you had to add; the page benchmark's `apply shows` and Task 12's first journey are what measure it.
- [ ] **Step 11: Schemas, both gates** - `npm run schemas`, then the whole Python gate and the whole page gate. Vitest covers `edits.ts`, `updating.ts`, `revisions.ts` and the client's two notes at 100 %.
- [ ] **Step 12: The journeys** - build, then run them all, alone. An Apply now answers before its findings change; a journey that read a finding straight after an Apply waits for it on screen as before (`expect` retries), and one that applied twice to one file now meets the `analysing` refusal until its analysis lands - which a journey waiting on what it sees rides out. **A journey that fails is read, not re-run until it passes**: say in your report which ones needed a change and why.
- [ ] **Step 13: Ablate** - in a scratch worktree: the version bump in `_published` removed (the second-window test must die); `_refuse_unanalysed`'s condition inverted; `_written`'s pruning removed. On the page, in place: `updatingOf`'s second clause removed; `followStates` comparing revisions again.
- [ ] **Step 14: Screenshots** - `docker compose run --rm gui-screenshots` in compare mode: no reference may move, fixtures aside. If one does, stop and report.
- [ ] **Step 15: Commit** - one commit: the contract, the server and the page that reads it.

---

### Task 7: findings a page at a time

**Model:** most capable (`opus`) - a new endpoint, the state's biggest field removed, and the one table React Aria's own virtualiser cannot hold.

**Files:**
- Modify: `src/ddd/gui/contract.py` (`ListedFinding`, `FindingsReply`; `State.findings` out, `State.counts` in), `src/ddd/gui/derived.py` (the Findings tab's order, counts), `src/ddd/findings_by_file.py` (`positions`), `src/ddd/gui/api.py` (`GET /api/findings`; `_state`), `tools/bench_gui.py`, `gui/bench/page.bench.ts`
- Modify (page): `gui/src/api/client.ts`, `gui/src/api/types.ts`, `gui/src/lib/findings.ts`, `gui/src/components/FindingsTableView.tsx` and its stories, `gui/src/screens/FindingsPage.tsx`, `gui/src/screens/ProjectPage.tsx`, `gui/src/screens/ComponentPage.tsx`, `gui/src/styles/ui.css`, `gui/src/stories/fixtures.ts`
- Create (page): `gui/src/lib/findingsWindow.ts`, `gui/src/lib/findingsWindow.test.ts`
- Test: `tests/test_gui_api.py`, `tests/test_gui_contract.py`, `tests/test_findings_by_file.py`, `tests/test_bench_gui.py`, `gui/src/lib/findings.test.ts`, `gui/src/api/client.test.ts`

**Interfaces:**
- Consumes: Task 4's `Derived`, `FindingsByFile`, `_memoised`; Task 6's `State`.
- Produces: `GET /api/findings`; `ListedFinding`, `FindingsReply`; `State.counts`; `getFindings`, `FindingsQuery`; `ROW_HEIGHT`, `PAGE_SIZE`, `MARGIN`, `Span`, `spanOf`, `pagesOf`, `WindowRow`, `windowRows`; `findingCounts(counts, updating)` - `updating` passed `false` until Task 8 - and `stillReported`. Task 9 takes `ROW_HEIGHT` for every virtualised table.

**`GET /api/findings`** (spec §5): `?offset=` (a whole number from 0; `0` when absent), `?limit=` (a whole number from 1; every finding from `offset` on when absent - what a component's page asks for its file), and any of `?severity=` (`error`, `warning` or `info`), `?file=` (a file's path, however spelled), `?check=`. The findings are in the Findings tab's order - worst first, and within a severity in the revision's own order, the stable sort `findingRows` makes on the page today - and each carries a `key`: its file, severity, check, place and words, and which repeat of those it is, counted over the whole revision in that order, so a finding keeps its key on every page, under every filter, and into the next revision where it stays. Refusals, each a whole sentence a test asserts: `findings takes ?offset= as a whole number from 0`, `findings takes ?limit= as a whole number from 1`, `findings takes ?severity= as error, warning or info`.

**The Findings table is a window, not React Aria's virtualiser** (ruling 1): *Measured while planning*, its `Virtualizer` takes 1,531 ms to draw 132,000 rows - ten to twelve microseconds a row, every one in its collection - and a findings-heavy project of 100,000 declarations has 125,000 findings. The table draws the rows in view and `MARGIN` on each side, between two spacers standing for the rows above and below, all at `ROW_HEIGHT` - so which rows are in view, and which pages of findings to ask for, is arithmetic `gui/src/lib` does under test. React Aria's `Table` draws the window, with its selection and its keyboard.

- [ ] **Step 1: The contract** - failing tests first. `ListedFinding(Finding)` adds `key: str` with the docstring above; `FindingsReply` has `revision`, `total` ("how many findings the filters leave, in all"), `offset` and `findings: tuple[ListedFinding, ...]`; `_ENDPOINTS` and `__all__` gain `FindingsReply`, and `gui/src/api/types.ts` re-exports `FindingsReply` and `ListedFinding`. `State.findings` goes; `State.counts: FindingCounts` comes - "how many findings of each severity the revision has, in all" - `0`s before the first analysis.
- [ ] **Step 2: The order, once per revision** - `Derived` gains `ranked: tuple[int, ...]` (the findings' positions sorted by `diagnostic.severity.rank`, stably), `repeats: tuple[int, ...]` (each position's repeat number among findings of equal file, severity, check, place and words, counted along `ranked`) and `counts: tuple[int, int, int]`; `FindingsByFile` gains `positions(path) -> tuple[int, ...]`, where in the given order the findings shown on `path` stand. Tests in `tests/test_findings_by_file.py` and on `derived` over a revision with two findings of equal content on one file.
- [ ] **Step 3: The endpoint** - failing tests in `tests/test_gui_api.py` first, over a copy of `examples/demo` with findings of every severity:
  - the pages of every size from 1 to 7, laid end to end, are the whole list, in the order the page's `findingRows` made from the old `State.findings` - write that oracle in the test from the revision: a stable sort by severity rank;
  - every key is unique in a revision, and the same finding has the same key on every page, under every filter, and in the next revision after an unrelated edit;
  - `?file=` spelled through a symlinked directory, `?severity=`, `?check=`, and two together, each against a filter of the whole list; `total` is the filtered count;
  - `?limit=` absent answers every finding from `offset`; `?offset=` past the end answers none, with the right `total`;
  - each refusal, by its whole sentence;
  - the same page twice is the same `Reply` (`is`), and a new revision a new one.

  Then `_findings` answers through `_memoised(revision, ("findings", offset, limit, severity, file, check), make)`, building each listed finding with `_finding` - its route included - and its key; `_memo` keeps at most `MEMO` answers, the oldest dropped first:

```python
MEMO: Final = 256
"""How many answers the api keeps for the newest revision: every tab's rows, the graph, and the
pages of findings a reader scrolls back to. A bound, the oldest dropped first: without one, every
page of a findings-heavy project a reader scrolled through would be kept until its next
analysis."""
```

  `_state` builds `counts` from `Derived.counts`, and no longer carries a finding.
- [ ] **Step 4: The api tests that read `State.findings`** - 69 places in `tests/test_gui_api.py` read `state["findings"]`. They read `GET /api/findings` instead, through one helper beside `get`:

```python
def every_finding(api: Api) -> list[dict[str, Any]]:
    """Every finding of the newest revision, in the Findings tab's order, each without its
    ``key`` - what ``State.findings`` answered before findings came a page at a time."""
    return [
        {name: value for name, value in listed.items() if name != "key"}
        for listed in get(api, "/api/findings").body["findings"]
    ]
```

  **Mind the order**: `State.findings` was the revision's order and this is the tab's. A test that compared positions compares sets, or sorts both sides - never loosen what it asserts about content. Say in your report how many tests changed and that none lost an assertion.
- [ ] **Step 5: The benchmark** - `tools/bench_gui.py` gains two measures after `files`: `findings page` (`GET /api/findings?offset=0&limit=100`) and `findings of a file` (`GET /api/findings?file=` the first component's file, no limit). `NAMES` and the smoke test gain them. `gui/bench/page.bench.ts`' `scrolling` wheels over the Findings table's own scroll box, which is where the table now scrolls; its name and meaning stay.
- [ ] **Step 6: The window's arithmetic** - `gui/src/lib/findingsWindow.ts`, test first:

```ts
import type { FindingsReply, ListedFinding } from "../api/types";
import { baseName } from "./units";

/** Every row of the Findings table is this tall, in pixels - `ui.css` draws it so - which is what
 * turns a scroll position into a row. Every virtualised table takes its rows' height from here. */
export const ROW_HEIGHT = 33;

/** How many findings one request asks for. */
export const PAGE_SIZE = 100;

/** How many rows beyond the ones in view are drawn on each side: what the keyboard moves into
 * before the window follows it. */
export const MARGIN = 20;

/** The rows drawn: from `first`, up to but not including `last`. */
export interface Span {
  first: number;
  last: number;
}

/** The rows in view at a scroll position and height, and `MARGIN` on each side, within `total`. */
export function spanOf(scrollTop: number, height: number, total: number): Span {
  const top = Math.floor(Math.max(0, scrollTop) / ROW_HEIGHT);
  const shown = Math.ceil(Math.max(0, height) / ROW_HEIGHT);
  return { first: Math.min(total, Math.max(0, top - MARGIN)), last: Math.min(total, top + shown + MARGIN) };
}

/** The pages of `PAGE_SIZE` findings a span covers, in order. */
export function pagesOf(span: Span): number[] {
  const pages: number[] = [];
  for (let page = Math.floor(span.first / PAGE_SIZE); page * PAGE_SIZE < span.last; page += 1) {
    pages.push(page);
  }
  return pages;
}

/** A row the window draws: its place, its key, and its finding - `null` until its page arrives,
 * when it is drawn as a placeholder nobody can select. */
export interface WindowRow {
  index: number;
  key: string;
  finding: ListedFinding | null;
  file: string;
}

/** The rows of a span, from the pages that have arrived. */
export function windowRows(span: Span, pages: ReadonlyMap<number, FindingsReply>): WindowRow[] {
  const rows: WindowRow[] = [];
  for (let index = span.first; index < span.last; index += 1) {
    const finding = pages.get(Math.floor(index / PAGE_SIZE))?.findings[index % PAGE_SIZE] ?? null;
    rows.push({
      index,
      key: finding?.key ?? `pending-${index}`,
      finding,
      file: finding === null ? "" : baseName(finding.file),
    });
  }
  return rows;
}
```

  Its tests: a span at the top (no negative `first`), in the middle, at the bottom (no `last` past `total`), of a table shorter than its box, and of no findings; `pagesOf` across a page boundary and of an empty span; `windowRows` with a page arrived and one not.
- [ ] **Step 7: `findings.ts`** - `findingCounts(counts: FindingCounts, updating: boolean)` makes the tab's line from the state's counts - the words it makes today from the list, `updating` ignored until Task 8 says what it adds - and `stillReported(key, reply)` says whether a reply carries that key. `findingRows` stays: the Compare tab still makes its rows from its own reply's list.
- [ ] **Step 8: The client** - `getFindings(query: FindingsQuery)`, each parameter encoded and left out where absent; its tests.
- [ ] **Step 9: The table and its screen** - `FindingsTableView` draws, and decides nothing: a scroll box (`.findings-window`, its height fixed in `ui.css`) calling `onScroll(scrollTop, clientHeight)`, a spacer `span.first * ROW_HEIGHT` tall, React Aria's `Table` of the window's rows - a placeholder row for each `finding: null`, listed in `disabledKeys` - and a spacer for the rows below. The columns have fixed widths and every cell one line, ellipsis where it overflows (the message in full is in the panel); the header row stays at the top of the box (`position: sticky`). `FindingsPage` keeps the box's scroll position and height in state (starting at the top, one box high), asks each of `pagesOf(spanOf(...))` with `useQueries` under `["findings", revision, page]`, and draws `windowRows`. A selected finding is kept with its key; on each new revision the page asks `getFindings({ file, check })` of it and closes its panel with "This finding is no longer reported." where `stillReported` says no - the behaviour `gone` has today. The summary line is `findingCounts(state.counts, false)`.
- [ ] **Step 10: The other two readers of `State.findings`** - `ProjectPage`'s line counts from `state.counts`; `ComponentPage` asks `getFindings({ file })` under `["findings", revision, "file", file]` - every finding of its own file, no limit - for its rows' chips and its list.
- [ ] **Step 11: Stories and screenshots** - the `FindingsTableView` stories take the window's props, with fixtures true to `examples/demo` or saying they are constructed; one new story, **a long table**: 2,000 findings, the window at its top, a placeholder row among the arrived ones. `UPDATE=1 docker compose run --rm gui-screenshots`, then **open every Findings reference, new and moved, and say what each shows** - the one-line rows and fixed columns move them all; nothing else may move.
- [ ] **Step 12: Both gates, the journeys** - schemas, the Python gate, the page gate; build, then the journeys alone. `findings.spec.ts` reads the tab through what a reader sees and should pass unchanged; say so, or why not.
- [ ] **Step 13: Ablate** - in a scratch worktree: the sort's key from `rank` to the check's name; `repeats` counted over the revision's order instead of the ranked one (a key test must die); `MEMO` to 0. On the page, in place: `MARGIN` to 0 and `spanOf`'s `Math.max(0, ...)` removed.
- [ ] **Step 14: Measure** - the server benchmark on `$BENCH/35000-many-heavy` and `$BENCH/100000-many-heavy`: `state`'s size and time, and the two new findings measures, in your report.
- [ ] **Step 15: Commit** - one commit: the endpoint, the contract and the page that reads them.

---

### Task 8: "Updating" shown

**Model:** standard (`sonnet`) - many files, each a small change, and screenshots to read.

**Files:**
- Create: `gui/src/ui/UpdatingNote.tsx` and its story, `gui/src/app/updating.ts` (a React context, glue only)
- Modify: `gui/src/lib/findings.ts` (`findingCounts`' `updating`; `tableLine`), `gui/src/app/App.tsx`, `gui/src/screens/FindingsPage.tsx`, `ProjectPage.tsx`, `ComponentPage.tsx`, `VariablePanel.tsx`, `UnitPanel.tsx`, `TypePanel.tsx`, `ConstantPanel.tsx`, `SectionPanel.tsx`, `RasterPanel.tsx`, `ValuesPage.tsx`; the views they draw with - `VariablePanelView`, `UnitPanelView`, `TypePanelView`, `ConstantPanelView`, `SectionPanelView`, `RasterPanelView`, `ValuesGridView` - and a story each for the two named below
- Test: `gui/src/lib/findings.test.ts`

**Interfaces:**
- Consumes: Task 6's `updating` from `useProjectState`; Task 7's `findingCounts(counts, updating)`.
- Produces: `UpdatingContext` (`gui/src/app/updating.ts`), `useUpdating()`, the `UpdatingNote` widget, an optional `updating?: boolean` on each of the seven views.

Spec §6: "Updating" is shown on the findings counts and each panel's list of findings while the state says `analysing`, or while the page's own last edit is newer than its revision. Read here as: **the project's heading** (every tab, every screen), **the two summary lines** - the Findings tab's and the Table tab's - and **each panel's list of findings**, including a component page's. A table's per-row counts are not marked; the heading beside them says the findings are updating (ruling 15).

- [ ] **Step 1: The words, in lib, test first** - `findingCounts(counts, updating)` ends in ` · updating` when `updating`; `tableLine(counts, updating)` makes the Table tab's `N errors, M warnings` - today spelled in `ProjectPage.tsx`, a decision in a `.tsx` file - with the same ending. Tests pin both whole lines, updating and not, one and many.
- [ ] **Step 2: The widget** - `UpdatingNote` draws `Updating the findings…` quietly, as a `role="status"` region so a screen reader hears it arrive; a story.
- [ ] **Step 3: The context** - `gui/src/app/updating.ts` exports `UpdatingContext = createContext(false)` and `useUpdating()`; `App.tsx` provides `updating` around the page, and draws `UpdatingNote` in the project's heading and the component page's while it is true. Screens read `useUpdating()`; views take `updating` as a prop, so their stories stay pictures of their props.
- [ ] **Step 4: The panels** - each of the seven views draws `UpdatingNote` where its list of findings is, whenever `updating` - also when the list is empty, since an edit may be about to bring the panel's first finding - and the list below it as before. Each screen passes `useUpdating()` on. `ComponentPage`'s "Findings in this component" does the same.
- [ ] **Step 5: Stories, screenshots** - one new story for `VariablePanelView` and one for `UnitPanelView`, each with its findings updating; `UPDATE=1 docker compose run --rm gui-screenshots`, **open each new reference and quote what it shows**; nothing that exists may move.
- [ ] **Step 6: Both gates, then the journeys, alone.** Then by hand, on `$BENCH/35000-many-heavy`: Apply a unit in a variable's panel and watch the heading and the panel say "Updating the findings…" until the analysis lands; a screenshot of it, opened and read.
- [ ] **Step 7: Ablate** - in place: `findingCounts` dropping its ending; one view ignoring its `updating` (the new story's reference must change - which is the only thing that pins a view).
- [ ] **Step 8: Commit.**

---

### Task 9: long tables virtualised

**Model:** standard (`sonnet`).

**Files:**
- Modify: `gui/src/ui/Table.tsx` (re-exports `Virtualizer` and `TableLayout`), `gui/src/styles/ui.css`, `gui/src/components/UnitsTableView.tsx`, `TypesTableView.tsx`, `SharedTableView.tsx`, `FilesTableView.tsx`, `VariableKeysTable.tsx`, `gui/src/screens/ComponentPage.tsx` (its declarations), `gui/src/screens/ProjectPage.tsx` (its components, from a plain `<table>` to React Aria's), their stories and `gui/src/stories/fixtures.ts`

**Interfaces:**
- Consumes: Task 7's `ROW_HEIGHT`.
- Produces: nothing another task imports.

Spec §6: the component table, the project's file list, the vocabulary and Files tables and a variable's keys are virtualised **with React Aria's own `Virtualizer` and `TableLayout`**. *Measured while planning*: 58 ms to draw 3,333 rows virtualised against 666 ms not - and 3,333 is the "many" shape's component count at 100,000 declarations, and about the "large" shape's declarations of one component (3,332 or 3,334, the sizes being even). A variable's keys grow in columns - one per declaration - and `TableLayout` lays out columns as well as rows.

Each table becomes:

```tsx
<Virtualizer layout={TableLayout} layoutOptions={{ rowHeight: ROW_HEIGHT, headingHeight: ROW_HEIGHT }}>
  <Table aria-label="..." className="long" /* its selection props as today */>
    <TableHeader>
      <Column isRowHeader width={...}>...</Column>
      ...
    </TableHeader>
    ...
  </Table>
</Virtualizer>
```

- [ ] **Step 1: The style** - in `ui.css`, a `.react-aria-Table.long` is its own scroll box - `display: block; max-height: 60vh; overflow: auto` - so a short table is no taller than its rows and a long one scrolls inside a box of fixed height (review focus 8); its cells are one line, ellipsis where they overflow, at `ROW_HEIGHT` - the same rows the Findings table draws (ruling 7). A comment saying why both.
- [ ] **Step 2: Each table** - wrapped as above, each column given the `width` that draws it as the table drew itself before (a `Column` without one takes an equal share - what React Aria's `TableLayout` does), selection and keyboard as today. `ProjectPage`'s components become a React Aria table of the same columns, the component's name still the button that opens its page. Nothing a table shows or decides changes.
- [ ] **Step 3: Stories** - one new story, **a long table**: `FilesTableView` with a pattern matching 3,000 files, as the "many" shape's `components/*.ddd.json` does at 100,000 declarations. `UPDATE=1 docker compose run --rm gui-screenshots`: **every reference of these seven tables moves** - one-line rows, set widths - so open each and say what changed in it; any other that moves, stop and report.
- [ ] **Step 4: Both gates; the journeys, alone.** A journey that found a row by its text may now find it out of view - and React Aria does not draw a row out of view, so no locator reaches it until the box is scrolled to it: scroll the box the way a reader would (`mouse.wheel` over it, or the keyboard from a row in view), never enlarge the box for a test. The examples the journeys copy are short enough that their tables fit the box; say which journeys needed this, if any.
- [ ] **Step 5: By hand** - on `$BENCH/100000-many-heavy`: the Table tab's 3,333 components scroll without a stall; the Files tab's pattern opens on its 3,333 files; a component of `$BENCH/100000-large-clean` opens on its 3,334 declarations, and the keyboard walks its rows past the box's edge. A screenshot of each, opened and read.
- [ ] **Step 6: Commit.**

---

### Task 10: the graph, laid out once per shape and off the main thread

**Model:** standard (`sonnet`).

**Files:**
- Modify: `gui/src/lib/layout.ts` (`shapeOf`, `visibleOnly`), `gui/src/lib/layout.test.ts`, `gui/src/lib/canvas.ts` (placing a layout's positions and the reader's saved ones), `gui/src/screens/GraphPage.tsx`
- Create: `gui/src/app/layoutWorker.ts`, `gui/src/app/useLayout.ts`

**Interfaces:**
- Consumes: `laidOut(modules, flows, saved)`, `savedPositions(project)`.
- Produces: `shapeOf(modules, flows)`, `VISIBLE_ONLY_ABOVE`, `visibleOnly(count)`.

Ruling 2: *Measured while planning*, dagre lays out 1,200 components in 173 to 266 ms and 3,333 in 475 to 1,164 ms, every one over the 100 ms a stall may last - and the canvas laid out again on every revision. So the layout moves into a Web Worker, and is made again only when the set of modules or of arrows changes: a revision after an edit of a unit changes neither. The page's content security policy (`default-src 'self'`) lets a worker the build emits as a file of its own run; a worker made from a `blob:` it would refuse.

- [ ] **Step 1: The decisions, test first** - `shapeOf(modules, flows)`: one string from the sorted module paths and the sorted arrows (`from`, `to`), the same for the same graph in any order, different when a module or an arrow comes or goes, the same when only findings counts change. `VISIBLE_ONLY_ABOVE = 200` and `visibleOnly(count)`: React Flow draws only the nodes in view (`onlyRenderVisibleElements`) above that many modules - below, drawing them all costs nothing a reader sees, and panning never meets a node drawn late.
- [ ] **Step 2: The worker** - `gui/src/app/layoutWorker.ts` answers each message `{ modules, flows }` with `{ placed }` from `laidOut(modules, flows, {})`, or `{ error }` with the error's message: dagre overflows its stack on chains of 1,800 components (*Measured while planning*), and a layout that fails says so rather than leaving the canvas empty. `gui/src/app/useLayout.ts` makes one worker for the page's life (`new Worker(new URL("./layoutWorker.ts", import.meta.url), { type: "module" })`), posts when `shapeOf` changes, drops an answer for a shape it has since moved past, and answers `{ placed, error }`; the reader's saved positions are laid over `placed` on the main thread, as `laidOut` lays them now.
- [ ] **Step 3: The canvas** - `GraphPage` draws "Laying the project out…" until the first layout arrives, then keeps the last one while the next is made; a layout's error is a `Banner` naming it; `onlyRenderVisibleElements={visibleOnly(graph.modules.length)}`. It asks for the graph once per revision - Task 6 already stopped the ask before the first state.
- [ ] **Step 4: Both gates; build; the journeys, alone** - `skeleton.spec.ts` drives the canvas.
- [ ] **Step 5: By hand** - on `$BENCH/100000-many-clean`: the first screen, a pan across the canvas, and an edit's revision arriving without the canvas moving. The page benchmark's `first screen` on it, in your report.
- [ ] **Step 6: Commit.**

---

### Task 11: typing never waits

**Model:** standard (`sonnet`).

**Files:**
- Create: `gui/src/lib/typing.ts`, `gui/src/lib/typing.test.ts`, `gui/src/app/useDebounced.ts`
- Modify: every screen asking for a plan as the reader types - `DeclarePanel.tsx`, `ConstantPanel.tsx`, `SectionPanel.tsx`, `RasterPanel.tsx`, `UnitPanel.tsx`, `TypePanel.tsx`, `VariablePanel.tsx`, `ValuesPage.tsx` (both plans), `FilesPage.tsx`

**Interfaces:**
- Produces: `PLAN_DELAY_MS`, `planDelay(asked)`, `sameRequest(asked, typed)`, `useDebounced(value)`.

Spec §6: a panel's plan request is debounced, the delay decided in `lib` under test; a reply for text the reader has since typed past is dropped. Today every keystroke asks for a plan - and part 16's Add on the Files tab re-runs the whole analysis for each (its ruling 25).

- [ ] **Step 1: The decisions, test first** - `gui/src/lib/typing.ts`:

```ts
/** How long a panel waits after the reader's last keystroke before asking for the plan it
 * previews: long enough that typing a name asks once, short enough that the preview follows. */
export const PLAN_DELAY_MS = 250;

/** How long to wait before asking for a plan: at once for a panel's first - opening it previews
 * straight away - and `PLAN_DELAY_MS` for every later one. */
export function planDelay(asked: boolean): number {
  return asked ? PLAN_DELAY_MS : 0;
}

/** Whether a plan asked for is the one the reader's fields now say: only then is its preview
 * shown and applied, never one for text the reader has since typed past. */
export function sameRequest(asked: unknown, typed: unknown): boolean {
  return JSON.stringify(asked) === JSON.stringify(typed);
}
```

- [ ] **Step 2: The hook** - `gui/src/app/useDebounced.ts`: `useDebounced<T>(value: T): T` answers the value last asked for, moving to `value` after `planDelay(...)`; a newer value cancels the wait; unmounting cancels it. Glue only.
- [ ] **Step 3: Each screen** - asks for its plan with `useDebounced(request)` in the query key, and shows and applies the answer only where `sameRequest(asked, request)` - otherwise the preview is pending, as it is while any plan loads, and Apply is not offered. Read each screen for the one or two places it builds its request; a plan the reader has typed past is never applied - review this per screen.
- [ ] **Step 4: Both gates; build; the journeys, alone** - they type and wait for what they see, and should pass unchanged; a journey that asserted a preview within the same tick as its typing is waiting on the page, not on the reader, and is read before it is changed.
- [ ] **Step 5: By hand** - on `$BENCH/35000-many-clean`: type a path into the Files tab's Add and watch one plan asked for, not one per character (the built-in browser's network log); the page benchmark's `typing` on it, in your report.
- [ ] **Step 6: Ablate** - in place: `planDelay` answering `PLAN_DELAY_MS` always (the first-plan test); `sameRequest` answering `true`.
- [ ] **Step 7: Commit.**

---

### Task 12: the journeys and the documentation

**Model:** standard (`sonnet`).

**Files:**
- Modify: `gui/e2e/fixtures.ts` (a `generatedGui` fixture), `docs/command_line_interface.rst` (the `ddd gui` row), `docs/developer_documentation.rst` (the generator and the benchmark), `CHANGELOG.md` (0.11.0's browser interface entry)
- Create: `gui/e2e/large.spec.ts`

**Interfaces:**
- Consumes: Task 1's generator, run as `DDD_PYTHON tools/generate_project.py`; everything the page now shows.

- [ ] **Step 1: The fixture** - `generatedGui` writes, into the test's own output directory, a project of **20,000 declarations in the "many" shape, every output without an id and half the inputs unread** - large enough that an analysis lasts long enough for a reader to see "Updating the findings…", and findings enough that the Findings table is a window - by running `tools/generate_project.py` through `DDD_PYTHON` with `spawnSync` (as `demo.ts`' `dump` runs `ddd dump`), failing with its exit status and stderr where it fails; then starts `ddd gui` over the project exactly as `started` does for an example. Refactor `started` to take a directory already prepared, rather than copying `started` a second time.
- [ ] **Step 2: The journeys** - `gui/e2e/large.spec.ts`, over `generatedGui`, each waiting on what a reader sees and **never on a response** (review focus 9):
  - **An edit shows at once, and its findings follow**: the Table tab, component `C00000`, `Set the unit of C00000_O0000`, `Nm` chosen and applied; the unit cell reads `Nm`, and `Updating the findings…` is shown; then it is gone, and the Findings tab's line names errors - the producer and its reader now disagree - where before the edit it named none.
  - **The Findings table scrolled to its end**: the tab's line names every finding; the table's box scrolled to its bottom shows rows of the last component's file, `c00665.ddd.json`.
  - **The keyboard walks past the rows drawn**: a row selected, then `ArrowDown` sixty times - past `MARGIN` and the rows in view; the focused row is in view and the table's first finding is no longer drawn.
  Run the file three times, then the whole suite once, alone.
- [ ] **Step 3: The documentation** - the `ddd gui` row of `docs/command_line_interface.rst` gains a paragraph, in the words the code uses: an edit is written at once and shows where it was made; the findings follow when the project has been analysed again, the heading saying `Updating the findings…` until then, and each panel's findings saying so too; a change of a file an edit wrote is refused until that edit is analysed - `an edit that wrote pump.ddd.json has not been analysed yet, so this change can be planned once it has`; opening a project answers at once with its name and `Analysing the project…`, and asked of anything before its first analysis the server answers `the open project has not been analysed yet`; the Findings tab asks for its findings a page at a time as it scrolls, and the long tables draw only the rows in view. **Every sentence measured or read off the code as it stands** - run the refusal and copy it. `docs/developer_documentation.rst`, beside the page's commands: the generator (its shapes, what "findings-heavy" is), the two halves of the benchmark and how each is run, that both run by hand and never in CI, and where their figures are kept - this plan and the pull request.
- [ ] **Step 4: The changelog** - 0.11.0's browser interface entry gains a sentence: large projects stay responsive - an edit shows at once and its findings follow, the Findings tab reads its findings a page at a time, and long tables draw only what is in view - with no figure a reader could not reproduce from the documentation.
- [ ] **Step 5: The docs gate** - `docker compose run --rm -e JAVA_TOOL_OPTIONS=-Duser.home=/tmp docs; echo "DOCS=$?"`, and the Python gate (`tests/test_documentation.py` reads the docs).
- [ ] **Step 6: Commit.**

---

### Task 13: the figures after, and the milestone gate

**Model:** the controller runs this task itself - it is measurement, and the plan's own record.

- [ ] **Step 1: Regenerate** the eighteen projects of Task 2 Step 5 into a fresh `$BENCH` - the generator is deterministic, so they are the projects measured before, and a copy an earlier task edited is not.
- [ ] **Step 2: The server half after**, alone on the machine, on all eighteen; into *Figures* under **Server, after**.
- [ ] **Step 3: The page half after**, alone on the machine, on **all eighteen** (ruling 12); into *Figures* under **Page, after**.
- [ ] **Step 4: Against the budgets** - under *Figures*, one line per budget of the spec's §3 table, saying for every size, shape and density whether it is met, with the figure; a budget missed is a row of *What was left open*, never a sentence softened.
- [ ] **Step 5: By hand at 100,000 declarations** - `ddd gui` on `$BENCH/100000-mixed-heavy` in the built-in browser: opening, the first screen, each tab, a panel typed into, the Findings table scrolled to its end, an Apply and its findings arriving, the Undo; a screenshot of each, opened and read.
- [ ] **Step 6: The milestone gate** below, every command on the branch tip.
- [ ] **Step 7: Close out this plan** - the progress log, *What was left open*, *Rulings taken*, and an **As built** note under the header saying where execution departed from the task texts.

## Milestone gate

Every gate on the branch tip, none taken from an earlier task's run, each with its own exit status:

```bash
cd /home/sauci/Documents/Github/ddd
.venv/bin/python -m pytest > gate.txt 2>&1; echo "PYTEST=$?"; tail -3 gate.txt
.venv/bin/ruff check .; echo "RUFF=$?"
.venv/bin/ruff format --check .; echo "FMT=$?"
.venv/bin/mypy; echo "MYPY=$?"
cd gui && DDD=../.venv/bin/ddd DDD_PYTHON=../.venv/bin/python npm run schemas; echo "SCHEMAS=$?"
npm run lint; echo "LINT=$?"
npm run typecheck; echo "TSC=$?"
npm test; echo "VITEST=$?"
npm run build; echo "BUILD=$?"
npm run ladle:build; echo "LADLE=$?"
cd .. && docker compose run --rm gui-screenshots; echo "SHOTS=$?"
git status --short gui/screenshots/references
docker compose run --rm -e JAVA_TOOL_OPTIONS=-Duser.home=/tmp docs; echo "DOCS=$?"
cd gui && PLAYWRIGHT_CHANNEL=chrome DDD_PYTHON="$PWD/../.venv/bin/python" \
  npx playwright test --output=<a path outside the repository>; echo "E2E=$?"
```

The screenshot run is in **compare** mode: the committed references are checked against the committed stories, not rewritten to match them. The journeys run after the screenshots have finished, never beside them.

## Figures

Filled in by Tasks 2, 3 and 13, each table saying the machine, the commit and the date it was measured on. Every project is `tools/generate_project.py`'s, named `<declarations>-<shape>-<clean|heavy>`; heavy is `--missing-ids 1 --unread 0.5`. Milliseconds, one run each; a page measure that had not finished after 120 s reads `> 120000`.

### Server, before

*(Task 2, Step 6.)*

### Page, before

*(Task 3, Step 5 - eight projects.)*

### Server, after

*(Task 13, Step 2.)*

### Page, after

*(Task 13, Step 3 - all eighteen.)*

### Against the budgets

*(Task 13, Step 4.)*

## Progress log

| Task | Commits | Review | Notes |
| --- | --- | --- | --- |
| 1 the generator | | | |
| 2 the server benchmark, before | | | |
| 3 the page benchmark, before | | | |
| 4 the index and the kept answers | | | |
| 5 the analyser, waited for | | | |
| 6 edits answer once written | | | |
| 7 findings a page at a time | | | |
| 8 "Updating" shown | | | |
| 9 long tables virtualised | | | |
| 10 the graph | | | |
| 11 typing never waits | | | |
| 12 journeys and documentation | | | |
| 13 figures after, the gate | | | |

## What was left open

Filled in as the work goes. Each entry says what was not done and what it costs. Known before execution:

- **A project with sub-projects is analysed twice on opening.** Opening stamps the files the root's own includes name (ruling 5); a sub-project's files have no stamp from before, and the poll after the first analysis makes a second. The page says the findings are updating while it runs.
- **A judged add or removal on the Files tab costs one analysis** of the project with its includes changed - `remove judged` in the figures. The analysis is not changed by this part (spec §3); a reader waits that long for the preview.
- **An analysis that raises is retried at every poll**, the terminal printing why each time; before the project's first revision, the page says `Analysing the project…` until one succeeds.
- **The analysis and the requests share one interpreter.** A request answered while an analysis runs waits for its share of it; the server figures are taken with none running, but for `edit analysed`.
- **A plan made against a revision older than the newest** may not be refused `analysing` for a file the newest already read; the engine's own fingerprint check still refuses its Apply as stale.
- **A tab's rows kept between an outside save and its analysis** show what was read before the save until the revision moves, when the page asks again.
- **The Findings window counts its rows to a screen reader as the rows drawn**, not the table's: React Aria numbers the rows of its collection, which is the window.
- **The Findings tab has no filter of its own.** `GET /api/findings` filters by severity, file and check (spec §5); only a component's page asks it to, by file.
- **A chain of components deeper than dagre's stack** - about 1,500 - cannot be laid out; the canvas says so (Task 10) rather than drawing it.

## Rulings taken

Taken while planning; execution adds its own below them.

| # | Ruling | Why | Cost if wrong |
| --- | --- | --- | --- |
| 1 | **The Findings table is a window React Aria's `Table` draws, its rows chosen in `gui/src/lib`** - a departure from spec §6's "React Aria's own `Virtualizer`" for this one table | Its `Virtualizer` puts every row in its collection, ten to twelve microseconds a row: measured 1,531 ms for 132,000 rows and 286 ms for 30,000; a findings-heavy project of 100,000 declarations has 125,000 findings (ruling 11) | The window's own code to keep: its arithmetic under the Vitest gate, its keyboard behaviour under a journey, and a screen reader counting the window's rows (*What was left open*) |
| 2 | **The graph is laid out in a Web Worker, once per set of modules and arrows** - spec §6 moved it off the main thread "only if it misses the budget" | Measured before any benchmark: 173 to 266 ms at 1,200 components, 475 to 1,164 ms at 3,333 - every one over 100 ms - and laid out again on every revision | A worker file of its own, and a layout that answers later than the graph |
| 3 | **A plan changing a file an unanalysed edit wrote is refused `analysing`** - spec §5 says a plan during a pending analysis "is computed against the newest published revision" | Computed, it carries the fingerprint the analysis read that file at, so its Apply is refused stale; and its pointers come from an index of other bytes. Every other plan is computed at once, as §5 says | A reader changing one file twice waits one analysis before the second previews - seconds at 100,000 declarations |
| 4 | **The generator's readers sit `LAYER` components away**, not on the component before - departing from the spec §2 probe's chain | dagre 3.1.1 overflows its stack on a chain of 1,800 components, measured; no real project is one chain | Figures not comparable with §2's; every figure of this part is re-measured on the generator |
| 5 | **Opening stamps the files the root's includes name before the first analysis** - extending spec §5's rule for a created file | The same double analysis: every file unstamped, so the poll after opening analysed the whole project again | A sub-project's files still cost it (*What was left open*) |
| 6 | **`GET /api/findings` answers every finding from `offset` where no `limit` is given** | A component's page draws a chip on each row from its file's findings, all of them | A page asking the whole list of a heavy project gets it; only the component page asks without a limit, and only for one file |
| 7 | **Every virtualised table draws one line per row at `ROW_HEIGHT`** | The window's arithmetic needs rows of one height; one height keeps every photographed table the same at every size; each row's panel shows its text in full | Long descriptions and messages end in an ellipsis in the tables |
| 8 | **A finding's key is the server's**, from its file, severity, check, place and words and which repeat it is, counted over the whole revision | A page of findings cannot count repeats it does not hold; the page's `keyedFindings` left the file out | None found |
| 9 | **The Findings tab gains no filter control** | Spec §6 names none; the endpoint's filters serve the component page | A reader of a heavy project scrolls rather than narrows |
| 10 | **The analyser lands behind the waits it will remove** (Task 5), before the waits go (Task 6) | The one piece that can deadlock or lose an edit is reviewed alone, over api answers and journeys that do not change | About fifteen lines written in Task 5 and removed in Task 6 |
| 11 | **"Findings-heavy" is every output without an id and half the inputs written as unread outputs** | Spec §2's projects carried about two findings a declaration; this carries about 1.25 - a migration half done - with arrows still on the canvas | A heavier project's figures are not measured |
| 12 | **The page's figures before are taken on eight projects, after on all eighteen** | Before, every measure of the Findings tab caps at 120 s on the heavy ones, and eight projects show what is slow | Ten before-figures a reader cannot compare with |
| 13 | **A declaration is one entry of an interface, output or input** | What a reader counts down a component's table; spec §2 counted outputs and five readers each | None: every figure published here is this part's own |
| 14 | **No commit leaves a gate red; a change of the contract lands with the page that reads it** | A red gate between tasks is a gate nobody runs | Larger commits for Tasks 6 and 7 |
| 15 | **"Updating" is shown on the heading, the two summary lines and each panel's findings** - spec §6's "the findings counts" read as the lines that count them | A table's per-row counts sit under the heading that already says so | A reader looking only at a row's count does not see it is about to change |
| 16 | **A revision's findings are indexed by file; a name's are the findings on its places' files, asked of the name's own predicate** - spec §5 indexes them "by file and by the name they are about" | An index by name would restate each of the four predicates - a variable's, a unit's, a type's, a shared entry's - as a second rule that could drift from the first; the candidates on a name's files are few, and the predicate answers for them as it answered for all | A unit stated on every file of a project - `rpm` in a generated one - still asks its predicate of every finding carrying a unit check |
