# Constants in the GUI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Shared files tab that lists the project's constants, opens a panel on one, and lets a reader change its value, describe it, rename it everywhere it is named, add one — creating `constants.ddd.json` where the project has none — and remove one nothing names, so that `duplicate-constant`, `dimension-value` and `unknown-constant` stop being dead ends.

**Architecture:** Two new transport-neutral Python modules beside `project_types.py` and `type_plans.py` — `project_shared.py` reads, `shared_plans.py` plans — behind three api routes shaped like `/api/types`, `/api/type` and `/api/type-plan`. The rename is the editor's own: `ddd.lsp.navigation.rename_sites` and `rename_problem` already answer for a constant, so the tab asks rather than reimplements. On the page a `SharedPage` holds a table with a panel beside it, mirroring `UnitsPage`, and `lib/shared.ts` carries every decision the 100 % Vitest gate has to see.

**Tech Stack:** Python 3.12+ (pydantic, no new dependency), React 19 + react-aria-components + TanStack Query (no new dependency), Vitest, Playwright (journeys and Ladle screenshots), Sphinx.

**Spec:** `docs/superpowers/specs/2026-09-27-gui-constants-design.md` — read it before Task 1. Section numbers in the tasks below refer to it.

## Global Constraints

- **Python gate, every task:** `python -m pytest && ruff check . && ruff format --check . && mypy` — 100 % line **and** branch coverage, no `pragma: no cover`, no skipped tests. Run `mypy` bare: it takes its targets from `pyproject.toml` (`files = ["src/ddd", "tools"]`), and `mypy .` adds noise from files it is not meant to check.
- **Page gate, every page task:** `npm run lint && npm run typecheck && npm test && npm run build && npm run ladle:build` from `gui/`. Vitest is at 100 % statements, branches, functions and lines over `src/api`, `src/lib` and `src/state`. **There are no Vitest tests for components or screens** — the repo has never had them, and adding one is not this part's business.
- **No new dependency**, either side. The rule has held since part 1.
- **A value travels as the json text its author wrote.** `ConstantValue` is strict on both arms and `_refuse_whole_number` keeps them apart, so `2` is a whole constant and `2.0` a fractional one. Nothing is parsed into the models and re-serialised; an operation carries the raw text.
- **Every refusal names the file it concerns**, as `UnitRefusalError`'s docstring requires of the units plans.
- **The tab is labelled `Shared files`**, its route key is `shared`, and its table's columns are `Name`, `Kind`, `Value`, `Used by`, `Findings` — in that order (spec §5.1).
- **A row's finding count includes the findings on its uses** (spec §2). `dimension-value` is filed at the shape, not at the entry.
- **Never `page.waitForResponse` in a journey.** It is what broke part 6's CI; `e2e/skeleton.spec.ts:220` is one of two spots documented as flaky because of it.
- **Commit trailer:** every commit ends with `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`. Never `git commit --amend`, never rebase — the branch's history is read by the reviews.

---

## Prerequisites

Run once, before Task 1, and confirm each:

```bash
cd /home/sauci/Documents/Github/ddd
git branch --show-current          # feature/gui-constants
git log --oneline -1               # d1587a3 spec: constants in the browser
.venv/bin/python -m pytest -q      # green, 100 %
.venv/bin/python -m ddd check examples/vocabulary/project.ddd.json
# ok: 4 variables in 1 component are consistent
```

Every Python command in this plan is `.venv/bin/python …`; there is no `python` on this machine's PATH. Node is at `~/.local/node-v24.21.0/bin` and is **not** on PATH by default:

```bash
export PATH="$HOME/.local/node-v24.21.0/bin:$PWD/.venv/bin:$PATH"
```

## Conventions

- **The fixture is `examples/vocabulary`.** `constants.ddd.json` declares `TREND_SAMPLES` with value `16`; `pump.ddd.json` declares `PRESSURE_CELLS` with value `8` inline at `component.constants[0]`, and names both as dimensions. The project checks clean, so a test that wants a finding makes one.
- **Unit tests build their own trees** with `conftest.write_tree`, as `tests/test_project_types.py` does. `tests/conftest.py` exports `component`, `declare`, `project`, `types`, `write_tree` and more; read its exports before inventing a helper.
- **Docstrings carry the reason, not the restatement.** Every module, class and non-obvious function in this repo says *why* it is the way it is, usually naming what went wrong without it. Match that; a docstring that only renames the function is a review finding here.
- **Comments name the failure they prevent.** `# Two statements rather than one conditional expression: coverage.py counts no branch in an expression` is the house style.
- **A conditional expression registers zero branches with coverage.py.** Where an arm needs a test, write statements or an early return, or the 100 % gate passes over an arm nothing exercised.
- **Screenshots run in Docker only:** `docker compose run --rm gui-screenshots`, and `UPDATE=1 docker compose run --rm gui-screenshots` to write new references. Windows and Linux draw text differently, so a reference made anywhere else fails everywhere else.
- **Docs build in Docker:** `docker compose run --rm -e JAVA_TOOL_OPTIONS=-Duser.home=/tmp docs`. Without that variable Java takes `?` as its home and leaves a `docs/?/.java` directory in the checkout.
- **Journeys need a build first:** `npm run build` writes the pages the server serves from `src/ddd/gui/static`, and `npm run e2e` drives those, not the dev server. On this machine they need `PLAYWRIGHT_CHANNEL=chrome` and `DDD_PYTHON=<repo>/.venv/bin/python`.

## File Structure

**Created**

| Path | Responsibility |
| --- | --- |
| `src/ddd/project_shared.py` | What the Shared files tab reads: one row per entry, and one constant's panel. Transport-neutral — nothing in it knows about http or the session. |
| `src/ddd/shared_plans.py` | What changing a constant takes: `set_constant`, `rename_constant`, `add_constant`, `remove_constant`, each planned and never written. |
| `tests/test_project_shared.py` | The reading. |
| `tests/test_shared_plans.py` | The four verbs and every refusal. |
| `gui/src/lib/shared.ts` | The tab's own decisions: its summary line, whether a name is declared, the undo label for each action. |
| `gui/src/lib/shared.test.ts` | Vitest over that, at 100 %. |
| `gui/src/components/SharedTableView.tsx` | The table. A picture of its props and nothing else. |
| `gui/src/components/SharedTableView.stories.tsx` | Its stories, which become screenshot references. |
| `gui/src/components/ConstantPanelView.tsx` | The panel. |
| `gui/src/components/ConstantPanelView.stories.tsx` | Its stories. |
| `gui/src/screens/SharedPage.tsx` | The tab's screen: reads `/api/shared`, holds the selection, draws the table and the panel. |
| `gui/src/screens/ConstantPanel.tsx` | The panel's screen: reads `/api/constant`, asks for plans, applies them. |
| `gui/e2e/constants.spec.ts` | One journey, end to end through a real server. |

**Modified**

| Path | Change |
| --- | --- |
| `src/ddd/loading.py` | `included_files(source, entry)` made public beside `expand_include`. |
| `src/ddd/lsp/units.py` | its private `_included` becomes a call to that, so one rule has one implementation. |
| `src/ddd/finding_routes.py` | a `constant` route. |
| `src/ddd/gui/contract.py` | `SharedEntry`, `SharedReply`, `ConstantUse`, `ConstantReply`, and the two replies added to `_ENDPOINTS`. |
| `src/ddd/gui/api.py` | `CONSTANT_PLANS`, the three route methods, three `_ROUTES` entries. |
| `gui/src/generated/api.ts` | regenerated by `npm run schemas`; never edited by hand, and **gitignored** (`.gitignore:22`) - ci regenerates it before it typechecks, so it is never committed. |
| `gui/src/api/client.ts` | `getShared`, `getConstant`, `getConstantPlan`. |
| `gui/src/lib/route.ts` | three `shared` shapes. |
| `gui/src/lib/findings.ts` | a constants file is no longer a dead end. |
| `gui/src/lib/undo.ts` | `constantLabel`. |
| `gui/src/app/App.tsx` | the tab, and the screen it shows. |
| `gui/src/components/DimensionsField.tsx` | a dimension that names a constant becomes a way in. |
| `docs/command_line_interface.rst` | the `ddd gui` row gains the tab. |

## Interfaces between the tasks

Copied here so a task's implementer, who sees only their own task, knows the exact names and types their neighbours use.

**Task 1 produces**

```python
# src/ddd/loading.py
def included_files(source: Path, entry: Any) -> list[Path]: ...
```

```python
# src/ddd/shared_plans.py
CONSTANTS_FILE: Final = "constants.ddd.json"

@dataclass(frozen=True, slots=True)
class SharedProject:
    project: Path                       # the project description, resolved
    constants_files: tuple[Path, ...]   # in `project.includes` order; the first takes a new entry
    unread: tuple[Path, ...]            # the project's files that did not load, resolved, sorted

def shared_project(
    project: Path, unread: Sequence[Path], cache: dict[Path, Document]
) -> SharedProject: ...

class SharedRefusalError(Exception):
    code: Literal["unreadable", "invalid", "not-found"]
    message: str
    def __init__(self, code: Literal["unreadable", "invalid", "not-found"], message: str) -> None: ...

@dataclass(frozen=True, slots=True)
class SharedPlan:
    edits: tuple[PlannedEdit, ...]      # PlannedEdit is ddd.lsp.units.PlannedEdit
```

**Task 2 produces**

```python
# src/ddd/project_shared.py
@dataclass(frozen=True, slots=True)
class SharedRow:
    kind: str       # "constant"
    name: str
    value: str      # the json text its file spells: "16", "2.0"
    uses: int
    findings: int

@dataclass(frozen=True, slots=True)
class ConstantUse:
    site: Site                            # ddd.lsp.navigation.Site
    kind: Literal["variable", "member"]
    name: str                             # "Pressure", or "Sample_t.speed" for a member
    component: str | None                 # the component declaring it; None for a member

def shared_rows(
    built: Index, findings: Iterable[tuple[Path, Diagnostic]], cache: dict[Path, Document]
) -> tuple[SharedRow, ...]: ...
def constant_row(
    built: Index, name: str, findings: Iterable[tuple[Path, Diagnostic]], cache: dict[Path, Document]
) -> SharedRow: ...
def constant_text(built: Index, name: str, key: str, cache: dict[Path, Document]) -> str: ...
def constant_string(built: Index, name: str, key: str, cache: dict[Path, Document]) -> str: ...
def constant_uses(
    built: Index, name: str, cache: dict[Path, Document]
) -> tuple[ConstantUse, ...]: ...
def located_on_constant(built: Index, name: str, file: Path, found: Diagnostic) -> bool: ...
```

**Tasks 3 and 4 produce**

```python
# src/ddd/shared_plans.py
SETTABLE: Final = frozenset({"value", "description"})

def set_constant(
    built: Index, name: str, key: str, raw: str | None, cache: dict[Path, Document]
) -> SharedPlan: ...
def remove_constant(built: Index, name: str, cache: dict[Path, Document]) -> SharedPlan: ...
def rename_constant(
    built: Index, name: str, to: str, cache: dict[Path, Document]
) -> SharedPlan: ...
def add_constant(
    built: Index, project: SharedProject, name: str, raw: str, cache: dict[Path, Document]
) -> SharedPlan: ...
```

**Task 5 produces**

```python
# src/ddd/gui/api.py
CONSTANT_PLANS: Final[Mapping[str, tuple[str, ...]]] = {
    "set": ("name", "key"),      # `raw` too, which may be absent: leaving the key out
    "rename": ("name", "to"),
    "add": ("name", "raw"),
    "remove": ("name",),
}
```

Routes: `GET /api/shared` → `contract.SharedReply`; `GET /api/constant?name=` → `contract.ConstantReply`; `GET /api/constant-plan?action=` → `contract.PlanReply`, the model `/api/unit-plan` and `/api/type-plan` already answer with. `ddd.finding_routes.route_of` answers `Route("constant", name)`.

```python
# src/ddd/gui/contract.py
class SharedEntry(_Frozen):
    kind: str
    name: str
    value: str
    uses: int
    findings: int

class SharedReply(_Frozen):
    revision: int
    entries: tuple[SharedEntry, ...]

class ConstantUse(_Frozen):
    path: str                              # absolute, posix-separated
    pointer: str
    kind: Literal["variable", "member"]
    name: str
    component: str | None

class ConstantReply(_Frozen):
    revision: int
    name: str
    file: str                              # absolute, posix-separated; the entry's file
    pointer: str                           # `constants[i]` or `component.constants[i]`
    value: str                             # the json text the entry spells
    description: str                       # the string, for prose
    uses: tuple[ConstantUse, ...]
    findings: tuple[Finding, ...]
```

**Task 6 produces**

```ts
// gui/src/lib/route.ts — added to the Route union
| { page: "project"; view: "shared" }
| { page: "project"; view: "shared"; kind: string; name: string }
| { page: "project"; view: "shared"; kind: string; declare: string }
```

```ts
// gui/src/lib/shared.ts
export function tabTitle(entries: readonly SharedEntry[]): string;
export function isDeclared(reply: SharedReply, kind: string, name: string): boolean;
export function planEdit(plan: PlanReply, label: string): Changes | null;
// gui/src/lib/undo.ts
export function constantLabel(plan: ConstantPlanRequest): string;
// gui/src/api/client.ts
export const getShared: (fetchImpl?: Fetch) => Promise<SharedReply>;
export const getConstant: (name: string, fetchImpl?: Fetch) => Promise<ConstantReply>;
export const getConstantPlan: (query: ConstantPlanRequest, fetchImpl?: Fetch) => Promise<PlanReply>;
```

`ConstantPlanRequest` is the discriminated union `lib/undo.ts` takes, declared in `gui/src/api/client.ts` beside `UnitPlanRequest` (`client.ts:138`) and `TypePlanRequest` (`client.ts:166`) - **not** in `api/types.ts`, which holds nothing hand-written, only the generated re-exports:

```ts
export type ConstantPlanRequest =
  | { action: "set"; name: string; key: "value" | "description"; raw?: string }
  | { action: "rename"; name: string; to: string }
  | { action: "add"; name: string; raw: string }
  | { action: "remove"; name: string };
```

**Tasks 7, 8 and 9 produce** screens and stories only: no module another task imports.

---
## Task 1: one rule for which files a project includes, and the project a constant's plans are made in

**Files:**
- Modify: `src/ddd/loading.py` (add `included_files` immediately after `expand_include`, which ends near line 1400)
- Modify: `src/ddd/lsp/units.py:329-337` (delete its private `_included`; call the public one)
- Create: `src/ddd/shared_plans.py`
- Create: `tests/test_shared_plans.py`

**Interfaces:**
- Consumes: `ddd.loading.expand_include`, `ddd.loading.resolve_path`, `ddd.lsp.ranges.read`, `ddd.lsp.units.PlannedEdit`.
- Produces: `loading.included_files`, and `shared_plans`'s `CONSTANTS_FILE`, `SETTABLE`, `SharedProject`, `shared_project`, `SharedRefusalError`, `SharedPlan`, `_raw`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_shared_plans.py`:

```python
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

    def test_a_pattern_the_platform_refuses_names_nothing(self, tmp_path: Path) -> None:
        """Which exception a NUL byte earns is the platform's business - linux refuses it in
        `resolve()`, windows carries it to the read - and the run has reported it already."""
        assert included_files(tmp_path / "p.ddd.json", "a\0.ddd.json") == []

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
        write_tree(tmp_path, {"p.ddd.json": project("P", "c.ddd.json", "*.ddd.json"), "c.ddd.json": CONSTANTS})
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
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_shared_plans.py -q --no-cov`
Expected: FAIL at collection — `ImportError: cannot import name 'included_files' from 'ddd.loading'` (and, once that exists, `ModuleNotFoundError: No module named 'ddd.shared_plans'`).

- [ ] **Step 3: Make the include rule public**

In `src/ddd/loading.py`, immediately after `expand_include`:

```python
def included_files(source: Path, entry: Any) -> list[Path]:
    """The files one ``includes`` entry names, or none for an entry the loader cannot expand -
    one that is not a string, or a pattern pathlib refuses - which the run has reported already.

    Beside :func:`expand_include` and public for the same reason it is: two clients that ask
    which files a project includes - the unit plans, and the constants a shared files tab adds
    to - must not come to a different answer than the run that checks the project, and each
    swallowing the three exceptions its own way is how they would drift apart.
    """
    if not isinstance(entry, str):
        return []
    try:
        return expand_include(source, entry, {source})
    except (OSError, ValueError, NotImplementedError):
        return []
```

In `src/ddd/lsp/units.py`: delete `_included` (lines 329-337), change line 39 to
`from ddd.loading import included_files, resolve_path`, and call `included_files(path, entry)` in
`unit_project`. `expand_include` is then unused there — `ruff check` will say so if it is left.

- [ ] **Step 4: Write `shared_plans.py`'s foundations**

```python
"""What changing one of a project's constants takes, planned and never written.

Transport-neutral, like :mod:`ddd.project_shared` beside it: nothing here knows about http or the
session. A rename is the editor's rename - :func:`ddd.lsp.navigation.rename_sites` says which
strings it has to rewrite, :func:`~ddd.lsp.navigation.rename_problem` says why a name may not be
used - for the reason :mod:`ddd.type_plans` borrows them both: two clients that renamed a constant
differently would disagree about what a project means, and the one reaching fewer files would
leave it broken across several at once.

Every value travels as the json text its author wrote. :data:`ddd.models.constants.ConstantValue`
is strict on both arms and refuses a whole number in the fractional one, so ``2`` and ``2.0`` are
two different constants; a plan that parsed a value and wrote it back would retype one nobody
asked it to.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

from ddd.loading import included_files, resolve_path
from ddd.lsp.ranges import Document, read
from ddd.lsp.units import PlannedEdit

CONSTANTS_FILE: Final = "constants.ddd.json"
"""The constants file ``add_constant`` writes for a project that has none, beside its description.

Named as :data:`ddd.lsp.units.ADOPTED` names the units file adoption writes, and for the same
reason: whoever opens the checkout afterwards should be able to tell what the file is from its
name.
"""

SETTABLE: Final = frozenset({"value", "description"})
"""What the interface may set on a constant's entry. ``name`` is not one of them: changing a name
is a rename, which has to rewrite every shape naming it in the same edit."""


@dataclass(frozen=True, slots=True)
class SharedProject:
    """What a plan has to know of the project besides its index: where its constants are kept,
    and which of its files did not load."""

    project: Path
    """The project description, resolved."""

    constants_files: tuple[Path, ...]
    """Its constants files, in the order its ``project.includes`` lists them, each listed once:
    the first is where a new constant goes, so that it lands in the file a run of ``ddd check``
    reads first."""

    unread: tuple[Path, ...]
    """The project's files that did not load, resolved and sorted."""


@dataclass(frozen=True, slots=True)
class SharedPlan:
    """Everything one change of a constant takes: one edit per file, sorted by path."""

    edits: tuple[PlannedEdit, ...]


class SharedRefusalError(Exception):
    """A change of a constant that cannot be planned, and the code both clients refuse it with."""

    code: Literal["unreadable", "invalid", "not-found"]
    """``unreadable``: a file the change has to see did not load. ``invalid``: the change cannot
    be made - a key a constant has not, a name that may not be used, a constant a shape still
    names. ``not-found``: no file of the project declares a constant of that name."""

    message: str
    """The sentence the refusal is shown with, naming the file it concerns."""

    def __init__(self, code: Literal["unreadable", "invalid", "not-found"], message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def shared_project(
    project: Path, unread: Sequence[Path], cache: dict[Path, Document]
) -> SharedProject:
    """The project a constant's plans are made in: its description, its constants files and the
    files of it that did not load.

    The constants files come out of the description's own ``includes``, each entry expanded by the
    loader's rule, so that the first of them is the first a run of ``ddd check`` reads. A
    constants file is a document with ``constants`` at its top, which is how the loader tells one;
    a file that does not parse is none, since what it is cannot be told - and a new entry must not
    be appended to a file nobody could read.
    """
    path = resolve_path(project)
    listed = read(path, cache).value_at("project.includes")
    found: list[Path] = []
    for entry in listed if isinstance(listed, list) else ():
        for file in included_files(path, entry):
            document = read(file, cache).data
            if file not in found and isinstance(document, dict) and "constants" in document:
                found.append(file)
    return SharedProject(
        path,
        tuple(found),
        tuple(sorted({resolve_path(file) for file in unread}, key=Path.as_posix)),
    )


def _raw(value: Any) -> str:
    """A value as the json text an operation carries, every character as written: a description
    holding a degree sign arrives in the file as one, where json's default would write an
    escape."""
    return json.dumps(value, ensure_ascii=False)
```

`_raw` has no caller until Task 3. If the coverage gate reports it unexercised at the end of this
task, move its definition into Task 3 rather than writing a test that only calls it: a test whose
whole purpose is to reach a line is the shape the repo's reviews reject.

- [ ] **Step 5: Run the tests, then the whole gate**

Run: `.venv/bin/python -m pytest tests/test_shared_plans.py -q --no-cov`
Expected: PASS.

Run: `.venv/bin/python -m pytest -q && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy`
Expected: 100 % line and branch; ruff and mypy clean. The existing `tests/test_unit_plans.py` must
stay green untouched — that is the proof that moving `_included` moved no behaviour.

- [ ] **Step 6: Commit**

```bash
git add src/ddd/loading.py src/ddd/lsp/units.py src/ddd/shared_plans.py tests/test_shared_plans.py
git commit -m "$(printf "one rule for which files a project includes\n\nThe unit plans and the constants plans both have to ask which files a project\nincludes, and both have to get the same answer the run gets. The wrapper moves\nout of lsp/units.py to sit beside expand_include, whose docstring already says\nit is public for exactly this.\n\ntests/test_unit_plans.py is untouched, which is the proof that moving it moved\nno behaviour.\n\nCo-Authored-By: Claude Opus 5 <noreply@anthropic.com>")"
```

---
## Task 2: what the Shared files tab reads

**Files:**
- Create: `src/ddd/project_shared.py`
- Create: `tests/test_project_shared.py`

**Interfaces:**
- Consumes: `ddd.lsp.navigation.Index` (its `constants` and `constant_uses`), `Site`, `ddd.lsp.ranges.read` with `Document.raw_at` and `Document.value_at`, `ddd.diagnostics.Diagnostic`, `ddd.variables.declarations_of`.
- Produces: `SharedRow`, `ConstantUse`, `CONSTANT`, `shared_rows`, `constant_row`, `constant_text`, `constant_string`, `constant_uses`, `located_on_constant`.

Read `src/ddd/project_types.py` first, whole. This module is its sibling and follows it in shape,
naming and docstring register; a reviewer will compare them.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_project_shared.py`. Build the index the way `tests/test_project_types.py` builds
its own — read that file and use the same helper rather than inventing a second one.

```python
"""A project's constants as the Shared files tab shows them."""

from __future__ import annotations

from pathlib import Path

from ddd.diagnostics import Diagnostic, Location, Severity
from ddd.lsp.navigation import _DIMENSION_KEY
from ddd.lsp.ranges import Document
from ddd.project_shared import (
    _DECLARATION_SHAPE,
    _MEMBER_SHAPE,
    constant_row,
    constant_string,
    constant_text,
    constant_uses,
    located_on_constant,
    shared_rows,
)

TWO_HOMES = {
    "p.ddd.json": {"project": {"name": "P", "includes": ["c.ddd.json", "a.ddd.json"]}},
    "c.ddd.json": {
        "constants": [
            {"name": "TREND_SAMPLES", "value": 16, "description": "slots of a trend buffer"}
        ]
    },
    "a.ddd.json": {
        "component": {
            "name": "A",
            "constants": [{"name": "CELLS", "value": 2.0}],
            "interface": [
                {
                    "scope": "public",
                    "definition": {
                        "kind": "value",
                        "name": "Trend",
                        "datatype": "uint16",
                        "unit": "rpm",
                        "dimensions": ["TREND_SAMPLES"],
                    },
                }
            ],
        }
    },
}


class TestTheRows:
    def test_every_constant_of_both_homes_is_a_row(self, tmp_path: Path) -> None:
        """A reader looking for CELLS does not know whether a constants file or a component's own
        list declares it, so one table holds both."""
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        rows = shared_rows(built, (), cache)
        assert [(row.kind, row.name, row.value) for row in rows] == [
            ("constant", "CELLS", "2.0"),
            ("constant", "TREND_SAMPLES", "16"),
        ]

    def test_a_fractional_value_keeps_the_spelling_its_author_wrote(self, tmp_path: Path) -> None:
        """`2.0` is a fractional constant and `2` a whole one - `ConstantValue` refuses a whole
        number in its fractional arm - so a row showing `2` would name a different constant, and
        an edit built from that row would retype it."""
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        assert constant_row(built, "CELLS", (), cache).value == "2.0"

    def test_a_row_counts_the_shapes_that_name_it(self, tmp_path: Path) -> None:
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        assert {row.name: row.uses for row in shared_rows(built, (), cache)} == {
            "CELLS": 0,
            "TREND_SAMPLES": 1,
        }

    def test_a_row_counts_a_finding_filed_at_a_shape_that_names_it(self, tmp_path: Path) -> None:
        """`dimension-value` is filed at the shape, never at the entry, and is about nothing but
        the constant's value: a table counting only the entry's own findings would show nothing
        for the one finding a reader of this tab came to act on."""
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        at_the_shape = Diagnostic(
            check="dimension-value",
            severity=Severity.ERROR,
            message="whose value is no array length",
            location=Location(
                tmp_path / "a.ddd.json", "component.interface[0].definition.dimensions[0]"
            ),
        )
        rows = {
            row.name: row.findings
            for row in shared_rows(built, [(tmp_path / "a.ddd.json", at_the_shape)], cache)
        }
        assert rows == {"CELLS": 0, "TREND_SAMPLES": 1}

    def test_a_row_counts_a_finding_filed_inside_its_own_entry(self, tmp_path: Path) -> None:
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        at_the_entry = Diagnostic(
            check="duplicate-constant",
            severity=Severity.ERROR,
            message="declared more than once",
            location=Location(tmp_path / "c.ddd.json", "constants[0].name"),
        )
        rows = {
            row.name: row.findings
            for row in shared_rows(built, [(tmp_path / "c.ddd.json", at_the_entry)], cache)
        }
        assert rows["TREND_SAMPLES"] == 1

    def test_findings_are_read_once_however_many_rows_there_are(self, tmp_path: Path) -> None:
        """The api hands this a generator. Walked once per row, every row after the first would
        count nothing."""
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        at_the_entry = Diagnostic(
            check="duplicate-constant",
            severity=Severity.ERROR,
            message="declared more than once",
            location=Location(tmp_path / "c.ddd.json", "constants[0].name"),
        )
        given = iter([(tmp_path / "c.ddd.json", at_the_entry)])
        rows = {row.name: row.findings for row in shared_rows(built, given, cache)}
        assert rows["TREND_SAMPLES"] == 1

    def test_a_finding_with_no_place_belongs_to_no_constant(self, tmp_path: Path) -> None:
        built = _index(tmp_path, TWO_HOMES)
        about_the_project = Diagnostic(
            check="no-components", severity=Severity.ERROR, message="none", location=None
        )
        assert not located_on_constant(
            built, "TREND_SAMPLES", tmp_path / "p.ddd.json", about_the_project
        )

    def test_a_finding_in_another_file_belongs_to_no_constant(self, tmp_path: Path) -> None:
        """The pointer can match while the file does not: two components number their
        declarations from zero."""
        built = _index(tmp_path, TWO_HOMES)
        elsewhere = Diagnostic(
            check="dimension-value",
            severity=Severity.ERROR,
            message="whose value is no array length",
            location=Location(
                tmp_path / "c.ddd.json", "component.interface[0].definition.dimensions[0]"
            ),
        )
        assert not located_on_constant(built, "TREND_SAMPLES", tmp_path / "c.ddd.json", elsewhere)

    def test_a_finding_on_a_name_nothing_declares_still_belongs_to_it(
        self, tmp_path: Path
    ) -> None:
        """`unknown-constant` is filed at a shape naming a constant that does not exist. The
        question is still whether the finding is about that name, and the answer is still yes -
        it is what sends the reader to the pre-filled add form."""
        files = {
            **TWO_HOMES,
            "a.ddd.json": {
                "component": {
                    "name": "A",
                    "interface": [
                        {
                            "scope": "public",
                            "definition": {
                                "kind": "value",
                                "name": "Trend",
                                "datatype": "uint16",
                                "unit": "rpm",
                                "dimensions": ["MISSING_CELLS"],
                            },
                        }
                    ],
                }
            },
        }
        built = _index(tmp_path, files)
        undeclared = Diagnostic(
            check="unknown-constant",
            severity=Severity.ERROR,
            message="which is not a constant any file of this project declares",
            location=Location(
                tmp_path / "a.ddd.json", "component.interface[0].definition.dimensions[0]"
            ),
        )
        assert located_on_constant(built, "MISSING_CELLS", tmp_path / "a.ddd.json", undeclared)


class TestOneConstantsPanel:
    def test_its_value_and_description_are_read_from_its_entry(self, tmp_path: Path) -> None:
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        assert constant_text(built, "TREND_SAMPLES", "value", cache) == "16"
        assert (
            constant_string(built, "TREND_SAMPLES", "description", cache)
            == "slots of a trend buffer"
        )

    def test_a_key_the_entry_has_not_reads_empty(self, tmp_path: Path) -> None:
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        assert constant_string(built, "CELLS", "description", cache) == ""

    def test_a_key_holding_something_other_than_a_string_reads_empty_as_a_string(
        self, tmp_path: Path
    ) -> None:
        """A file that changed since the analysis can have anything at that key; the panel draws
        prose there, and a number would arrive as one."""
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        assert constant_string(built, "TREND_SAMPLES", "value", cache) == ""

    def test_a_name_the_index_does_not_hold_reads_empty(self, tmp_path: Path) -> None:
        """The api looks a name up before it asks, so this arm is only reachable from a test -
        which is where `ddd.project_types` covers its own."""
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        assert constant_text(built, "NOTHING", "value", cache) == ""
        assert constant_string(built, "NOTHING", "description", cache) == ""
        assert constant_uses(built, "NOTHING", cache) == ()

    def test_a_use_names_the_variable_and_the_component_it_is_in(self, tmp_path: Path) -> None:
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        used = constant_uses(built, "TREND_SAMPLES", cache)
        assert [(use.kind, use.name, use.component) for use in used] == [("variable", "Trend", "A")]
        assert used[0].site.pointer == "component.interface[0].definition.dimensions[0]"

    def test_an_axis_size_is_a_use_like_a_dimension(self, tmp_path: Path) -> None:
        """A curve's axis states its length as `size`, which is the second of the three places a
        shape is written; nothing shipped in `examples/` declares one, so this tree writes it."""
        built = _index(tmp_path, _WITH_AN_AXIS)
        cache: dict[Path, Document] = {}
        used = constant_uses(built, "TREND_SAMPLES", cache)
        assert [(use.kind, use.name) for use in used] == [("variable", "TrendAxis")]
        assert used[0].site.pointer.endswith(".size")

    def test_a_structure_members_dimension_is_a_use_naming_its_structure(
        self, tmp_path: Path
    ) -> None:
        """The third place. A member carries no component: its structure may be declared in a
        types file no component owns, so the structure's name is what locates it."""
        built = _index(tmp_path, _WITH_A_STRUCTURE)
        cache: dict[Path, Document] = {}
        used = constant_uses(built, "TREND_SAMPLES", cache)
        assert [(use.kind, use.name, use.component) for use in used] == [
            ("member", "Sample_t.history", None)
        ]

    def test_a_use_whose_declaration_has_moved_is_left_out(self, tmp_path: Path) -> None:
        """The index recorded where the analysis read it; the file has changed since. The next
        revision lists it where it went, and a panel naming a declaration that is not there is
        worse than one row short."""
        built = _index(tmp_path, TWO_HOMES)
        (tmp_path / "a.ddd.json").write_text(
            '{"component": {"name": "A", "interface": []}}', encoding="utf-8"
        )
        cache: dict[Path, Document] = {}
        assert constant_uses(built, "TREND_SAMPLES", cache) == ()


def test_the_two_shape_patterns_match_what_the_index_calls_a_shape() -> None:
    """One authority, two readings of it: `_DIMENSION_KEY` decides where a constant may be named,
    and a pointer this module fails to recognise is a use the panel silently drops."""
    pointers = [
        "component.interface[0].definition.dimensions[0]",
        "component.interface[3].definition.size",
        "types[0].members[1].dimensions[0]",
        "component.types[2].members[0].dimensions[4]",
        "component.interface[0].definition.unit",
        "constants[0].value",
        "component.interface[0].definition.dimensions[0].extra",
    ]
    for pointer in pointers:
        mine = _DECLARATION_SHAPE.match(pointer) or _MEMBER_SHAPE.match(pointer)
        assert bool(mine) == bool(_DIMENSION_KEY.match(pointer)), pointer
```

`_WITH_AN_AXIS` and `_WITH_A_STRUCTURE` are two more trees in the same shape as `TWO_HOMES`: one
declaring a curve whose axis `size` is `"TREND_SAMPLES"`, one declaring a structure `Sample_t` with
a member `history` whose `dimensions` is `["TREND_SAMPLES"]`. Copy the exact json for both out of
hand: `examples/vocabulary/pump.ddd.json` declares neither, whatever an earlier draft of this plan
said, so there is nothing to copy. A declaration's `scope` is one of `input`, `output`, `local`, its
`kind` one of `measurement`, `parameter`, `value_block`, `curve`, `map`, `axis`, and `conversion` and
`volatile` are required - read `src/ddd/models/` for the rest rather than guessing.

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_project_shared.py -q --no-cov`
Expected: FAIL at collection — `ModuleNotFoundError: No module named 'ddd.project_shared'`.

- [ ] **Step 3: Write `project_shared.py`**

```python
"""A project's constants as the Shared files tab shows them.

Transport-neutral, like :mod:`ddd.project_types` and :mod:`ddd.project_units`: nothing here knows
about http or the session. Where a constant is declared and which shapes name it is the navigation
index's own record (:attr:`ddd.lsp.navigation.Index.constants` and
:attr:`~ddd.lsp.navigation.Index.constant_uses`), and what an entry *says* is read from the
document at that entry, the way a type's keys are.

Nothing is parsed into the models: a value travels as the json text it is written as, so ``2.0``
reaches the page - and comes back to an edit - as the three characters its author typed. The format
treats ``2`` and ``2.0`` as different constants, so a panel that read the value and wrote it back
would retype one nobody asked it to.

Every function answers empty for a name the index does not hold. The api looks a name up before it
asks, so that arm is only reachable from a test - which is where it is covered.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from ddd.diagnostics import Diagnostic
from ddd.lsp.navigation import Index, Site
from ddd.lsp.ranges import Document, read
from ddd.variables import declarations_of

CONSTANT: Final = "constant"
"""The ``kind`` a constant's row carries. The tab holds three kinds once sections and rasters land;
the column is what tells a reader how to read the rest of the row."""

_DECLARATION_SHAPE: Final = re.compile(
    r"^(component\.interface\[\d+\]\.definition)\.(?:dimensions\[\d+\]|size)$"
)
"""A declaration's own shape - an entry of its ``dimensions``, or the ``size`` of its axis - and
the definition it belongs to, whose ``name`` names the variable."""

_MEMBER_SHAPE: Final = re.compile(
    r"^((?:component\.)?types\[\d+\])\.(members\[\d+\])\.dimensions\[\d+\]$"
)
"""A structure member's dimension, and the two halves of its address: the structure and the member.

The ``component.`` prefix is optional because a component may declare its own types inline,
alongside its interface, at ``component.types[i]`` rather than a types file's ``types[i]`` -
exactly as :data:`ddd.project_types._MEMBER_TYPENAME` allows, and for the same reason:
:mod:`ddd.loading` registers both homes under one name.
"""


@dataclass(frozen=True, slots=True)
class SharedRow:
    """One row of the Shared files tab."""

    kind: str
    """``constant``. Sections and rasters bring their own words here."""

    name: str

    value: str
    """What the entry states, as the json text its file spells: ``16``, ``2.0``."""

    uses: int
    """How many shapes name it."""

    findings: int
    """How many findings are filed inside its entry or at a shape naming it."""


@dataclass(frozen=True, slots=True)
class ConstantUse:
    """One shape that names a constant."""

    site: Site

    kind: Literal["variable", "member"]

    name: str
    """The variable's name, or ``Sample_t.history`` for a structure member."""

    component: str | None
    """The component declaring the variable; ``None`` for a member, whose structure may be
    declared in a types file no component owns, and which ``name`` locates instead."""


def located_on_constant(built: Index, name: str, file: Path, found: Diagnostic) -> bool:
    """Whether this finding belongs to that constant: filed inside its entry, or at a shape naming
    it.

    Wider than :func:`ddd.project_types.located_in_type`, which asks only about a type's own entry,
    and deliberately. ``dimension-value`` is filed at the shape, never at the entry, and is about
    nothing but the constant's value; a table counting only the entry's own findings would show
    nothing for the one finding a reader of this tab has come to act on.

    Answered for a name no file declares too, which is what ``unknown-constant`` is: the question
    is whether the finding concerns that name, and the shape naming it is where it is filed.
    """
    location = found.location
    if location is None:
        return False
    resolved = file.resolve()
    entry = built.constants.get(name)
    places = [] if entry is None else [entry]
    places.extend(built.constant_uses.get(name, ()))
    return any(
        place.path.resolve() == resolved
        and (
            location.pointer == place.pointer
            or location.pointer.startswith((f"{place.pointer}.", f"{place.pointer}["))
        )
        for place in places
    )


def shared_rows(
    built: Index, findings: Iterable[tuple[Path, Diagnostic]], cache: dict[Path, Document]
) -> tuple[SharedRow, ...]:
    """Every entry the tab lists, by name: the project's constants today, from both homes.

    ``findings`` is read into a list once rather than walked per row: the api hands this a
    generator, and a second walk of a spent one would count nothing for every row but the first.
    """
    filed = list(findings)
    return tuple(constant_row(built, name, filed, cache) for name in sorted(built.constants))


def constant_row(
    built: Index,
    name: str,
    findings: Iterable[tuple[Path, Diagnostic]],
    cache: dict[Path, Document],
) -> SharedRow:
    """One constant's own row: what :func:`shared_rows` would answer for ``name`` alone, without
    building every other row alongside it - what ``GET /api/constant`` needs one of."""
    filed = list(findings)
    return SharedRow(
        kind=CONSTANT,
        name=name,
        value=constant_text(built, name, "value", cache),
        uses=len(built.constant_uses.get(name, ())),
        findings=sum(1 for file, found in filed if located_on_constant(built, name, file, found)),
    )


def constant_text(built: Index, name: str, key: str, cache: dict[Path, Document]) -> str:
    """The json text ``key`` is written as in that constant's entry, or empty where the entry has
    it not: ``16``, ``2.0``, ``"slots of a trend buffer"``.

    The text and not the value, so that an edit built from what the page was shown writes back what
    was written.
    """
    entry = built.constants.get(name)
    if entry is None:
        return ""
    return read(entry.path, cache).raw_at(f"{entry.pointer}.{key}") or ""


def constant_string(built: Index, name: str, key: str, cache: dict[Path, Document]) -> str:
    """The string ``key`` holds in that constant's entry, or empty where it holds none.

    Beside :func:`constant_text` rather than folded into it: a description is shown as prose and a
    value as the text it is written as, and reading a description through ``raw_at`` would put its
    quotes on the screen.
    """
    entry = built.constants.get(name)
    if entry is None:
        return ""
    value = read(entry.path, cache).value_at(f"{entry.pointer}.{key}")
    return value if isinstance(value, str) else ""


def constant_uses(built: Index, name: str, cache: dict[Path, Document]) -> tuple[ConstantUse, ...]:
    """Every shape the index recorded naming ``name``, in the order it recorded them.

    A declaration comes with the component declaring it, as :func:`ddd.variables.declarations_of`
    reads it, and one its file no longer declares where the index recorded it is left out, as that
    function leaves it out: the file changed since the analysis, and the next revision lists it
    where it went.
    """
    found: list[ConstantUse] = []
    for site in built.constant_uses.get(name, ()):
        document = read(site.path, cache)
        member = _MEMBER_SHAPE.match(site.pointer)
        if member is not None:
            structure = document.value_at(f"{member.group(1)}.name")
            named = document.value_at(f"{member.group(1)}.{member.group(2)}.name")
            if isinstance(structure, str) and isinstance(named, str):
                found.append(ConstantUse(site, "member", f"{structure}.{named}", None))
            continue
        shape = _DECLARATION_SHAPE.match(site.pointer)
        if shape is None:
            continue
        definition = shape.group(1)
        variable = document.value_at(f"{definition}.name")
        if not isinstance(variable, str):
            continue
        declared = next(
            (
                entry
                for entry in declarations_of(built, variable, cache)
                if entry.site == Site(site.path, definition)
            ),
            None,
        )
        if declared is not None:
            found.append(ConstantUse(site, "variable", variable, declared.component))
    return tuple(found)
```

`declarations_of` returns entries whose `component` and `site` this relies on; check its dataclass
before writing the last block and use its real field names.

- [ ] **Step 4: Run the tests, then the whole gate**

Run: `.venv/bin/python -m pytest tests/test_project_shared.py -q --no-cov`
Expected: PASS.

Run: `.venv/bin/python -m pytest -q && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy`
Expected: 100 % line and branch; ruff and mypy clean. Every arm of `constant_uses` needs a test —
the member that no longer parses, the declaration whose `name` is gone, the pointer neither pattern
matches — and a conditional expression would hide one, so keep them as the statements above.

- [ ] **Step 5: Commit**

```bash
git add src/ddd/project_shared.py tests/test_project_shared.py
git commit -m "$(printf "read a project's constants as a tab shows them\n\nOne row per entry with both homes in one list, a value carried as the text its\nauthor wrote, and a row's finding count reaching the shapes that name it -\nbecause dimension-value is filed there and is about nothing but the constant's\nvalue.\n\nCo-Authored-By: Claude Opus 5 <noreply@anthropic.com>")"
```

---
## Task 3: setting a constant's value or description, and removing one

**Files:**
- Modify: `src/ddd/shared_plans.py` (add to what Task 1 created)
- Modify: `tests/test_shared_plans.py`

**Interfaces:**
- Consumes: Task 1's `SharedProject`, `SharedPlan`, `SharedRefusalError`, `SETTABLE`, `_raw`; `ddd.editing.Operation`; `ddd.lsp.units.PlannedEdit`; `ddd.lsp.navigation.Index`/`Site`; `ddd.models.constants.ConstantValue`.
- Produces: `set_constant`, `remove_constant`, and the private `_entry`, `_plan`, `_value`, `_plural` the next task also uses.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_shared_plans.py`:

```python
class TestSettingAKey:
    def test_a_value_is_set_as_the_text_it_was_given(self, tmp_path: Path) -> None:
        """`2.0` stays fractional: the operation carries the three characters, not a parsed 2."""
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        plan = set_constant(built, "TREND_SAMPLES", "value", "2.0", cache)
        assert [(edit.path.name, edit.operations) for edit in plan.edits] == [
            ("c.ddd.json", (Operation("set", "constants[0].value", "2.0"),))
        ]

    def test_a_description_is_set_on_the_entry(self, tmp_path: Path) -> None:
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        plan = set_constant(built, "TREND_SAMPLES", "description", '"a trend"', cache)
        assert plan.edits[0].operations == (
            Operation("set", "constants[0].description", '"a trend"'),
        )

    def test_a_description_may_be_taken_away(self, tmp_path: Path) -> None:
        """The model defaults it to empty, so a file without one loads - and part 3's chooser
        already offers to leave a key out wherever the format allows it."""
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        plan = set_constant(built, "TREND_SAMPLES", "description", None, cache)
        assert plan.edits[0].operations == (Operation("remove", "constants[0].description"),)

    def test_a_value_may_not_be_taken_away(self, tmp_path: Path) -> None:
        """`ConstantDeclaration` requires it, so the file would stop loading and the tab would
        have emptied itself in one press."""
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        with pytest.raises(SharedRefusalError) as raised:
            set_constant(built, "TREND_SAMPLES", "value", None, cache)
        assert raised.value.code == "invalid"
        assert "c.ddd.json" in raised.value.message

    def test_a_key_a_constant_has_not_is_refused(self, tmp_path: Path) -> None:
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        with pytest.raises(SharedRefusalError) as raised:
            set_constant(built, "TREND_SAMPLES", "unit", "\"rpm\"", cache)
        assert raised.value.code == "invalid"
        assert "description" in raised.value.message and "value" in raised.value.message

    def test_a_name_no_file_declares_is_not_found(self, tmp_path: Path) -> None:
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        with pytest.raises(SharedRefusalError) as raised:
            set_constant(built, "NOTHING", "value", "1", cache)
        assert raised.value.code == "not-found"

    @pytest.mark.parametrize("raw", ['"eight"', "true", "null", "[1]", "1e400"])
    def test_a_value_the_format_would_refuse_is_refused_here(self, tmp_path: Path, raw: str) -> None:
        """Written, the file would stop loading and the whole project with it - every tab empty
        because of one keystroke in this one. `ConstantValue` itself is the judge, so the
        interface and the loader cannot disagree about what a constant may hold."""
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        with pytest.raises(SharedRefusalError) as raised:
            set_constant(built, "TREND_SAMPLES", "value", raw, cache)
        assert raised.value.code == "invalid"

    def test_a_value_no_shape_could_use_is_allowed(self, tmp_path: Path) -> None:
        """`2.5` is a legal constant. A shape naming it is what makes it wrong, and
        `dimension-value` is the check that says so - on the next revision, in the panel, with a
        route back to this value. The interface does not invent a rule the format has not."""
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        assert set_constant(built, "TREND_SAMPLES", "value", "2.5", cache).edits


class TestRemoving:
    def test_an_entry_nothing_names_is_taken_out(self, tmp_path: Path) -> None:
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        plan = remove_constant(built, "CELLS", cache)
        assert [(edit.path.name, edit.operations) for edit in plan.edits] == [
            ("a.ddd.json", (Operation("remove", "component.constants[0]"),))
        ]

    def test_a_constant_a_shape_names_is_refused_with_where_it_is_named(
        self, tmp_path: Path
    ) -> None:
        """Removed, every shape naming it would be left naming nothing - `unknown-constant` on
        each, in files the reader was not looking at. Asked of the index, never of a file's text:
        that is the mistake part 11 filed against `variable_keys._storage_of`."""
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        with pytest.raises(SharedRefusalError) as raised:
            remove_constant(built, "TREND_SAMPLES", cache)
        assert raised.value.code == "invalid"
        assert "a.ddd.json" in raised.value.message
        assert "1 shape" in raised.value.message

    def test_a_name_no_file_declares_is_not_found(self, tmp_path: Path) -> None:
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        with pytest.raises(SharedRefusalError) as raised:
            remove_constant(built, "NOTHING", cache)
        assert raised.value.code == "not-found"
```

Add a test that the shape count reads `2 shapes` for a constant two shapes name, so both arms of
the plural are exercised — a conditional expression would register no branch for the one nothing
took.

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_shared_plans.py -q --no-cov`
Expected: FAIL — `ImportError: cannot import name 'set_constant' from 'ddd.shared_plans'`.

- [ ] **Step 3: Implement the two verbs**

Add to `src/ddd/shared_plans.py`, and add `from collections.abc import Mapping, Sequence`,
`from ddd.editing import Operation`, `from ddd.lsp.navigation import Index, Site`,
`from ddd.models.constants import ConstantValue` and `from pydantic import TypeAdapter` to its
imports:

```python
_VALUE: Final = TypeAdapter(ConstantValue)
"""The format's own judge of what a constant may hold, so that the interface and the loader cannot
come to different answers. Strict on both arms, which is what keeps ``2`` a whole constant and
``2.0`` a fractional one."""


def set_constant(
    built: Index, name: str, key: str, raw: str | None, cache: dict[Path, Document]
) -> SharedPlan:
    """``key`` of that constant's entry set to the json text ``raw``, or taken away where ``raw``
    is ``None``.

    ``raw`` is trusted to be json: the api parses it with :func:`ddd.editing.parse_raw` and answers
    ``bad-request`` for text that is not, the way ``GET /api/settle`` already does - a malformed
    request is not a refusal about the project.

    A ``value`` may not be taken away, and one the format would refuse is refused here: written,
    the file would stop loading and every tab would empty because of one keystroke in this one.
    """
    entry = _entry(built, name)
    if key not in SETTABLE:
        raise SharedRefusalError(
            "invalid",
            f"a constant has no '{key}': it states {' and '.join(sorted(SETTABLE))}",
        )
    if key == "value":
        if raw is None:
            raise SharedRefusalError(
                "invalid",
                f"a constant states a value, so '{name}' cannot be left without one in "
                f"{entry.path.name}",
            )
        _value(raw, name, entry.path)
        return _plan({entry.path: [Operation("set", f"{entry.pointer}.{key}", raw)]})
    if raw is None:
        return _plan({entry.path: [Operation("remove", f"{entry.pointer}.{key}")]})
    return _plan({entry.path: [Operation("set", f"{entry.pointer}.{key}", raw)]})


def remove_constant(built: Index, name: str, cache: dict[Path, Document]) -> SharedPlan:
    """That constant's entry taken out of the list holding it.

    Refused while any shape names it. Removed, each of those shapes would name nothing, which is
    an ``unknown-constant`` apiece in files the reader was not looking at - a worse answer than
    saying no. What is in use is asked of the index, never of a file's text: reading text to answer
    a question about meaning is the mistake part 11 filed against ``variable_keys._storage_of``.
    """
    entry = _entry(built, name)
    used = built.constant_uses.get(name, ())
    if used:
        raise SharedRefusalError(
            "invalid",
            f"'{name}' is named by {_plural(len(used), 'shape')}, the first in "
            f"{used[0].path.name}; nothing may name it before it goes",
        )
    return _plan({entry.path: [Operation("remove", entry.pointer)]})


def _entry(built: Index, name: str) -> Site:
    """Where that constant is declared, or a refusal saying nothing declares it."""
    entry = built.constants.get(name)
    if entry is None:
        raise SharedRefusalError(
            "not-found", f"no file of this project declares a constant called '{name}'"
        )
    return entry


def _value(raw: str, name: str, file: Path) -> None:
    """Refuse a value the format would not take, naming the file it would have been written to."""
    try:
        _VALUE.validate_python(json.loads(raw))
    except (ValueError, TypeError) as refused:
        raise SharedRefusalError(
            "invalid",
            f"{raw} is not a value a constant may state, so '{name}' cannot take it in "
            f"{file.name}: a whole number a 64 bit target holds, of either sign, or a finite "
            f"fractional one",
        ) from refused


def _plan(operations: Mapping[Path, Sequence[Operation]]) -> SharedPlan:
    """One edit per file, sorted by path, as :class:`SharedPlan` promises and the interface applies
    them."""
    return SharedPlan(
        tuple(
            PlannedEdit(path, tuple(operations[path]))
            for path in sorted(operations, key=Path.as_posix)
        )
    )


def _plural(count: int, noun: str) -> str:
    """"1 shape", "2 shapes"."""
    return f"{count} {noun}{'' if count == 1 else 's'}"
```

`_plural` returns a conditional expression inside an f-string, which coverage.py counts no branch
in — so both counts must appear in a test, or one wording ships unexercised. The tests above ask
for exactly that.

- [ ] **Step 4: Run the tests, then the whole gate**

Run: `.venv/bin/python -m pytest tests/test_shared_plans.py -q --no-cov`
Expected: PASS.

Run: `.venv/bin/python -m pytest -q && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy`
Expected: 100 %, all clean.

- [ ] **Step 5: Commit**

```bash
git add src/ddd/shared_plans.py tests/test_shared_plans.py
git commit -m "$(printf "plan a constant's value, its description and its removal\n\nA value is carried as the text it was given and judged by ConstantValue itself,\nso the interface cannot write a file the loader then refuses. A constant a shape\nstill names is not removed: the index says what names it, never the text of a\nfile.\n\nCo-Authored-By: Claude Opus 5 <noreply@anthropic.com>")"
```

---
## Task 4: renaming a constant, and declaring one

**Files:**
- Modify: `src/ddd/shared_plans.py`
- Modify: `tests/test_shared_plans.py`

**Interfaces:**
- Consumes: Task 3's `_entry`, `_plan`, `_value`, `_raw`; `ddd.lsp.navigation.rename_problem`, `rename_sites`; `ddd.editing.lay_out`, `DEFAULT_INDENT_UNIT`, `Operation`; Task 1's `CONSTANTS_FILE`, `SharedProject`.
- Produces: `rename_constant`, `add_constant`.

Read `src/ddd/type_plans.py::rename_type` and `src/ddd/lsp/units.py::adopt_units` before writing.
The first is the rename this one copies; the second is the only other plan in the repo that creates
a file, and the shape of its two-edit plan is the shape this one must take.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_shared_plans.py`:

```python
class TestRenaming:
    def test_the_entry_and_every_shape_naming_it_are_rewritten_in_one_edit(
        self, tmp_path: Path
    ) -> None:
        """All or nothing: a rename that reached the entry but not the shapes would leave the
        project with `unknown-constant` on every one of them."""
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        plan = rename_constant(built, "TREND_SAMPLES", "TREND_SLOTS", cache)
        assert {edit.path.name: edit.operations for edit in plan.edits} == {
            "a.ddd.json": (
                Operation(
                    "set",
                    "component.interface[0].definition.dimensions[0]",
                    '"TREND_SLOTS"',
                ),
            ),
            "c.ddd.json": (Operation("set", "constants[0].name", '"TREND_SLOTS"'),),
        }

    def test_the_edits_come_sorted_by_path(self, tmp_path: Path) -> None:
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        plan = rename_constant(built, "TREND_SAMPLES", "TREND_SLOTS", cache)
        assert [edit.path.name for edit in plan.edits] == ["a.ddd.json", "c.ddd.json"]

    @pytest.mark.parametrize(
        ("to", "because"),
        [
            ("2CELLS", "not a usable c identifier"),
            ("CELLS", "already"),
            ("int", "reserved"),
        ],
    )
    def test_a_name_the_editor_refuses_is_refused_here_in_its_words(
        self, tmp_path: Path, to: str, because: str
    ) -> None:
        """`rename_problem` is the editor's own judge, and the tab asks it rather than deciding
        for itself: two clients that refused different names would disagree about what a project
        may be called. Adjust the expected fragments to whatever that function actually says -
        read it, do not guess."""
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        with pytest.raises(SharedRefusalError) as raised:
            rename_constant(built, "TREND_SAMPLES", to, cache)
        assert raised.value.code == "invalid"
        assert because in raised.value.message

    def test_a_name_no_file_declares_is_not_found(self, tmp_path: Path) -> None:
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        with pytest.raises(SharedRefusalError) as raised:
            rename_constant(built, "NOTHING", "SOMETHING", cache)
        assert raised.value.code == "not-found"


class TestDeclaringOne:
    def test_it_is_appended_to_the_first_constants_file_the_project_includes(
        self, tmp_path: Path
    ) -> None:
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        found = shared_project(tmp_path / "p.ddd.json", (), cache)
        plan = add_constant(built, found, "PRESSURE_CELLS", "8", cache)
        assert [edit.path.name for edit in plan.edits] == ["c.ddd.json"]
        assert plan.edits[0].operations[0].op == "insert"
        assert plan.edits[0].operations[0].pointer == "constants[1]"
        assert '"value": 8' in (plan.edits[0].operations[0].raw or "")
        assert plan.edits[0].creates is False

    def test_the_value_is_embedded_as_the_text_it_was_given(self, tmp_path: Path) -> None:
        """`2.0` declares a fractional constant and `2` a whole one. Parsed and reprinted, a
        reader asking for one would get the other."""
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        found = shared_project(tmp_path / "p.ddd.json", (), cache)
        plan = add_constant(built, found, "GAIN", "2.0", cache)
        assert '"value": 2.0' in (plan.edits[0].operations[0].raw or "")

    def test_a_project_with_no_constants_file_gets_one_beside_its_description(
        self, tmp_path: Path
    ) -> None:
        """Both edits in one plan, so a project can never list a file that was not written.
        `Session._confined` allows exactly this shape of creation and no other."""
        files = {
            "p.ddd.json": project("P", "a.ddd.json"),
            "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
        }
        built = _index(tmp_path, files)
        cache: dict[Path, Document] = {}
        found = shared_project(tmp_path / "p.ddd.json", (), cache)
        plan = add_constant(built, found, "CELLS", "8", cache)
        assert [(edit.path.name, edit.creates) for edit in plan.edits] == [
            ("constants.ddd.json", True),
            ("p.ddd.json", False),
        ]
        whole = plan.edits[0].operations[0].raw or ""
        assert whole.startswith("{\n") and whole.endswith("}\n")
        assert '"name": "CELLS"' in whole
        assert plan.edits[1].operations == (
            Operation("insert", "project.includes[1]", '"constants.ddd.json"'),
        )

    def test_a_file_of_that_name_already_there_is_refused_rather_than_overwritten(
        self, tmp_path: Path
    ) -> None:
        files = {
            "p.ddd.json": project("P", "a.ddd.json"),
            "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
            "constants.ddd.json": "not a description",
        }
        built = _index(tmp_path, files)
        cache: dict[Path, Document] = {}
        found = shared_project(tmp_path / "p.ddd.json", (), cache)
        with pytest.raises(SharedRefusalError) as raised:
            add_constant(built, found, "CELLS", "8", cache)
        assert raised.value.code == "invalid"
        assert "constants.ddd.json" in raised.value.message

    def test_a_constants_file_that_did_not_load_is_not_appended_to(self, tmp_path: Path) -> None:
        """It parses, so it is a constants file; it did not load, so what it already declares is
        unknown - and an entry appended to it could collide with one of them."""
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        found = shared_project(
            tmp_path / "p.ddd.json", [tmp_path / "c.ddd.json"], cache
        )
        with pytest.raises(SharedRefusalError) as raised:
            add_constant(built, found, "CELLS_2", "8", cache)
        assert raised.value.code == "unreadable"
        assert "c.ddd.json" in raised.value.message

    def test_a_name_the_project_already_declares_is_refused(self, tmp_path: Path) -> None:
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        found = shared_project(tmp_path / "p.ddd.json", (), cache)
        with pytest.raises(SharedRefusalError) as raised:
            add_constant(built, found, "TREND_SAMPLES", "8", cache)
        assert raised.value.code == "invalid"

    def test_a_value_the_format_would_refuse_is_refused(self, tmp_path: Path) -> None:
        built = _index(tmp_path, TWO_HOMES)
        cache: dict[Path, Document] = {}
        found = shared_project(tmp_path / "p.ddd.json", (), cache)
        with pytest.raises(SharedRefusalError) as raised:
            add_constant(built, found, "CELLS_2", '"eight"', cache)
        assert raised.value.code == "invalid"
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_shared_plans.py -q --no-cov`
Expected: FAIL — `ImportError: cannot import name 'rename_constant' from 'ddd.shared_plans'`.

- [ ] **Step 3: Implement the two verbs**

Add `from ddd.editing import DEFAULT_INDENT_UNIT, Operation, lay_out` and
`from ddd.lsp.navigation import Index, Site, rename_problem, rename_sites` to the imports, then:

```python
def rename_constant(built: Index, name: str, to: str, cache: dict[Path, Document]) -> SharedPlan:
    """What renaming a constant takes: its own ``name`` and every shape spelling it.

    The editor's rename, asked for rather than reimplemented.
    :func:`ddd.lsp.navigation.rename_sites` knows the three places a shape is written and
    :func:`~ddd.lsp.navigation.rename_problem` knows why a name may not be used - with
    ``Index.occupied`` already holding *the name of the declared constant* - so the tab and the
    editor cannot disagree about what a rename reaches or which names it refuses.

    Refused before a file is touched: a rename writes into every file naming the constant, and a
    name that turned out to be unusable would leave the project broken across all of them at once.
    """
    _entry(built, name)
    problem = rename_problem(built, to, "constant")
    if problem is not None:
        raise SharedRefusalError("invalid", problem)
    by_file: dict[Path, list[Operation]] = {}
    for site in rename_sites(built, "constant", name):
        by_file.setdefault(site.path, []).append(Operation("set", site.pointer, _raw(to)))
    return _plan(by_file)


def add_constant(
    built: Index, project: SharedProject, name: str, raw: str, cache: dict[Path, Document]
) -> SharedPlan:
    """``name`` declared with the value ``raw``: appended to the first constants file the project
    includes, or written into a new one beside the project description where it includes none.

    One verb, where the units vocabulary has two. ``adopt`` harvests the units already in use into
    a new file; the constants in use are exactly the ones ``unknown-constant`` complains about, and
    a value cannot be harvested - nothing in the project says what the length of an array is. So
    this creates the file when there is none, and there is nothing to adopt.

    ``raw`` is embedded as the text it was given rather than parsed and reprinted: ``2.0`` declares
    a fractional constant and ``2`` a whole one, and a reader asking for one would otherwise get
    the other.
    """
    problem = rename_problem(built, name, "constant")
    if problem is not None:
        raise SharedRefusalError("invalid", problem)
    if not project.constants_files:
        return _created(project, name, raw, cache)
    file = project.constants_files[0]
    if file in project.unread:
        raise SharedRefusalError(
            "unreadable",
            f"{file.name} did not load, so what it declares is unknown and '{name}' cannot be "
            "added to it",
        )
    _value(raw, name, file)
    listed = read(file, cache).value_at("constants")
    position = len(listed) if isinstance(listed, list) else 0
    return _plan({file: [Operation("insert", f"constants[{position}]", _entry_text(name, raw))]})


def _created(
    project: SharedProject, name: str, raw: str, cache: dict[Path, Document]
) -> SharedPlan:
    """The constants file a project without one gets, and the ``includes`` entry naming it.

    Follows :func:`ddd.lsp.units.adopt_units`, the only other plan in the repo that creates a file:
    laid out with :func:`ddd.editing.lay_out` so the new file reads like one a person wrote, and
    carried in the same plan as the ``includes`` entry so that a project can never list a file that
    was not written - which is also the only shape of creation
    :func:`ddd.gui.session._confined` allows.
    """
    created = project.project.parent / CONSTANTS_FILE
    if created.exists():
        raise SharedRefusalError(
            "invalid",
            f"declaring '{name}' writes {CONSTANTS_FILE} beside {project.project.name}, and a "
            "file of that name is there already",
        )
    _value(raw, name, created)
    laid_out = lay_out(
        f'{{"constants": [{_entry_text(name, raw)}]}}',
        one_line=False,
        indent="",
        unit=DEFAULT_INDENT_UNIT,
        newline="\n",
    )
    includes = read(project.project, cache).value_at("project.includes")
    position = len(includes) if isinstance(includes, list) else 0
    edits = (
        PlannedEdit(created, (Operation("set", "", f"{laid_out}\n"),), creates=True),
        PlannedEdit(project.project, (Operation("insert", f"project.includes[{position}]", _raw(CONSTANTS_FILE)),)),
    )
    return SharedPlan(tuple(sorted(edits, key=lambda edit: edit.path.as_posix())))


def _entry_text(name: str, raw: str) -> str:
    """One constant entry as json text, with ``raw`` embedded exactly as it was given.

    Built as text rather than dumped from a dict because a dict would carry the value through
    python's number types: ``1e3`` would come back ``1000.0`` and ``2.00`` as ``2.0``. The
    generated outputs normalise a number that way on purpose, but a description file should say
    what its author wrote. ``raw`` has passed :func:`_value`, so what is built here is json.
    """
    return f'{{"name": {_raw(name)}, "value": {raw}, "description": ""}}'
```

- [ ] **Step 4: Run the tests, then the whole gate**

Run: `.venv/bin/python -m pytest tests/test_shared_plans.py -q --no-cov`
Expected: PASS.

Run: `.venv/bin/python -m pytest -q && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy`
Expected: 100 %, all clean. Both arms of each `isinstance(... , list)` need a test — a project whose
`includes` is not a list, and a constants file whose `constants` is not one — so write them rather
than folding either into a conditional expression.

- [ ] **Step 5: Drive it by hand once**

A plan that is never applied proves nothing about the engine taking it. On a copy of
`examples/vocabulary`:

```bash
cp -r examples/vocabulary /tmp/vocab && cd /tmp/vocab
```

Then, from a python shell with the repo's venv, build the index, call `add_constant` for a new
constant and apply the plan through `ddd.editing`'s engine exactly as `ddd.gui.session.edit` does;
confirm `ddd check project.ddd.json` still answers `ok`, and that a project without a constants
file gets one that `ddd check` reads. Record what you ran in the report.

- [ ] **Step 6: Commit**

```bash
git add src/ddd/shared_plans.py tests/test_shared_plans.py
git commit -m "$(printf "plan a constant's rename, and declaring one\n\nThe rename is the editor's rename: rename_sites knows the three places a shape\nis written and rename_problem knows which names are refused, so the tab and the\neditor cannot disagree. Declaring one appends to the first constants file the\nproject includes, or writes constants.ddd.json beside the description and\nincludes it in the same plan - the one shape of creation the session allows.\n\nCo-Authored-By: Claude Opus 5 <noreply@anthropic.com>")"
```

---
## Task 5: the three routes, the contract, and where a constant's findings lead

**Files:**
- Modify: `src/ddd/finding_routes.py`
- Modify: `src/ddd/gui/contract.py` (the four models, and `_ENDPOINTS` near line 1241)
- Modify: `src/ddd/gui/api.py`
- Modify: `gui/src/generated/api.ts` (regenerated, never hand-edited)
- Modify: `tests/test_finding_routes.py`, `tests/test_gui_api.py`

**Interfaces:**
- Consumes: Task 2's `shared_rows`, `constant_row`, `constant_text`, `constant_string`, `constant_uses`, `located_on_constant`; Task 1's `shared_project`, `SharedRefusalError`; Tasks 3 and 4's four verbs; the api's own `_single`, `_error`, `_opened`, `_finding`, `_planned_changes`, `UNREADABLE`, `_NOTHING_LOADED`, `REFUSALS`; `ddd.project_units.previewed`; `ddd.editing.parse_raw`.
- Produces: `CONSTANT_PLANS` and the three routes, exactly as the **Interfaces between the tasks** section spells them.

- [ ] **Step 1: Write the failing route tests**

In `tests/test_finding_routes.py`, add a class covering all four pointer shapes. The important one
is the ordering:

```python
SHAPES = {
    "a.ddd.json": {
        "component": {
            "name": "A",
            "constants": [{"name": "CELLS", "value": 8}],
            "interface": [
                {
                    "scope": "public",
                    "definition": {
                        "kind": "value",
                        "name": "Trend",
                        "datatype": "uint16",
                        "unit": "rpm",
                        "dimensions": ["MISSING_CELLS"],
                    },
                },
                {
                    "scope": "public",
                    "definition": {
                        "kind": "axis",
                        "name": "TrendAxis",
                        "datatype": "uint16",
                        "unit": "rpm",
                        "size": "MISSING_CELLS",
                    },
                },
            ],
            "types": [
                {
                    "type": "struct",
                    "name": "Sample_t",
                    "members": [
                        {"name": "history", "datatype": "uint16", "dimensions": ["MISSING_CELLS"]}
                    ],
                }
            ],
        }
    },
    "c.ddd.json": {"constants": [{"name": "TREND_SAMPLES", "value": 16}]},
}


class TestAConstant:
    def test_unknown_constant_leads_to_the_name_the_shape_spells(self, tmp_path: Path) -> None:
        """The name does not exist - that is what the finding says - and the route still carries
        it: the page opens the add form with it filled in, which is the whole point of the tab
        for this check."""
        path = write_tree(tmp_path, SHAPES) / "a.ddd.json"
        assert route_of(
            "unknown-constant",
            path,
            "component.interface[0].definition.dimensions[0]",
            "component",
            True,
            {},
        ) == Route("constant", "MISSING_CELLS")

    def test_dimension_value_leads_to_the_constant_whose_value_is_wrong(
        self, tmp_path: Path
    ) -> None:
        """The one check of the three whose target is directly editable: the value is what has to
        change, and the panel is where it changes."""
        path = write_tree(tmp_path, SHAPES) / "a.ddd.json"
        assert route_of(
            "dimension-value",
            path,
            "component.interface[0].definition.dimensions[0]",
            "component",
            True,
            {},
        ) == Route("constant", "MISSING_CELLS")

    def test_an_axis_size_leads_there_too(self, tmp_path: Path) -> None:
        """The second of the three places a shape is written: an axis states its length as
        `size`, not as a `dimensions` entry."""
        path = write_tree(tmp_path, SHAPES) / "a.ddd.json"
        assert route_of(
            "unknown-constant",
            path,
            "component.interface[1].definition.size",
            "component",
            True,
            {},
        ) == Route("constant", "MISSING_CELLS")

    def test_a_constant_check_inside_a_type_beats_the_type_route(self, tmp_path: Path) -> None:
        """A structure member's dimension is inside `types[i]`, which `WITHIN_TYPE` matches. Tried
        after it, an `unknown-constant` on a member would open the type instead of the constant -
        the same ordering `UNIT_CHECKS` already needs and already has."""
        path = write_tree(tmp_path, SHAPES) / "a.ddd.json"
        assert route_of(
            "unknown-constant",
            path,
            "component.types[0].members[0].dimensions[0]",
            "component",
            True,
            {},
        ) == Route("constant", "MISSING_CELLS")

    def test_duplicate_constant_leads_to_the_constant_its_entry_declares(
        self, tmp_path: Path
    ) -> None:
        path = write_tree(tmp_path, SHAPES) / "c.ddd.json"
        assert route_of(
            "duplicate-constant", path, "constants[0].name", "constants", True, {}
        ) == Route("constant", "TREND_SAMPLES")

    def test_a_constant_declared_inline_by_a_component_leads_there_as_well(
        self, tmp_path: Path
    ) -> None:
        """`ddd.loading` registers `component.constants[i]` and a constants file's `constants[i]`
        under one name, so the tab lists both and a finding on either leads to the same panel."""
        path = write_tree(tmp_path, SHAPES) / "a.ddd.json"
        assert route_of(
            "duplicate-constant", path, "component.constants[0].name", "component", True, {}
        ) == Route("constant", "CELLS")

    def test_a_shape_holding_no_string_leads_nowhere(self, tmp_path: Path) -> None:
        """A dimension written as a number names no constant, and a file that changed since the
        analysis can have anything there."""
        assert (
            route_of(
                "unknown-constant",
                path,
                "component.interface[0].definition.dimensions[0]",
                "component",
                True,
                {},
            )
            is None
        )

    def test_a_sections_file_still_leads_nowhere(self, tmp_path: Path) -> None:
        """Sections and rasters are the parts after this one; their findings keep saying so."""
        assert route_of("duplicate-section", path, "sections[0].section", "sections", True, {}) is None
```

Copy the existing tests in that file for the exact `route_of` call shape and fixture style before
writing these; the six positional arguments above are from its current signature.

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_finding_routes.py -q --no-cov`
Expected: FAIL — each new test gets `None` or `Route("type", …)` where it wants `Route("constant", …)`.

- [ ] **Step 3: Add the constant route**

In `src/ddd/finding_routes.py`:

```python
CONSTANT_CHECKS: Final = frozenset({"unknown-constant", "dimension-value"})
"""The checks filed where a shape names a constant, whose finding leads to that constant.

``unknown-constant`` names one no file declares, and the route carries the name anyway: the page
opens its add form with it filled in. ``dimension-value`` names one whose value is no array length,
and the value is the thing to change.
"""

WITHIN_CONSTANT: Final = re.compile(r"^(?:component\.)?constants\[\d+\]")
"""The entry a pointer inside a constant lies in - whether the constant was declared in a constants
file (``constants[i]``) or inline by a component (``component.constants[i]``), which
:mod:`ddd.loading` registers the same way."""
```

`Route.kind`'s docstring gains ``constant``; `COMPONENT_KIND`'s says that sections and rasters are
what is left of milestone 6, not "the rest".

In `route_of`, immediately after the `UNIT_CHECKS` branch and **before** `WITHIN_TYPE`:

```python
    if check in CONSTANT_CHECKS:
        # Before WITHIN_TYPE below, exactly as UNIT_CHECKS is and for the same reason: a structure
        # member's dimension is inside `types[i]`, so tried after it an unknown-constant on a
        # member would open the type rather than the constant the finding is about.
        named = read(path, cache).value_at(pointer)
        return Route("constant", named) if isinstance(named, str) and named else None
    within_constant = WITHIN_CONSTANT.match(pointer)
    if within_constant is not None:
        # Before the kind check below, as WITHIN_TYPE is: a constants file's kind is `constants`,
        # and a component may declare a constant inline at `component.constants[i]`.
        name = read(path, cache).value_at(f"{within_constant.group()}.name")
        return Route("constant", name) if isinstance(name, str) else None
```

- [ ] **Step 4: Add the contract models**

In `src/ddd/gui/contract.py`, in a section commented
`# --- GET /api/shared, GET /api/constant ---` placed after the types section, add `SharedEntry`,
`SharedReply`, `ConstantUse` and `ConstantReply` exactly as the **Interfaces between the tasks**
section spells them, each field carrying a docstring in this file's register — every path field
saying *absolute, posix-separated*, as the neighbouring models do. Then add to `_ENDPOINTS`:

```python
    (SharedReply, "serialization"),
    (ConstantReply, "serialization"),
```

`PlanReply` is already there and is what `/api/constant-plan` answers with.

`gui/src/api/types.ts` re-exports the generated types by name, so the four new ones go into that
list too — its own comment says the point is that a model added to the contract without a page type
fails the build rather than the two drifting apart, and Task 6 imports them from there.

- [ ] **Step 5: Write the failing api tests**

In `tests/test_gui_api.py`, a `TestShared` class and a `TestConstant` class over
`opened_example(tmp_path, "vocabulary", "project.ddd.json")`, covering: the table lists
`PRESSURE_CELLS` and `TREND_SAMPLES` with their values as text; a panel names the entry's file and
pointer, its uses with their variables and components, and its findings; `?name=` missing is 400;
a name no file declares is 404; `/api/constant-plan` previews each of the four actions; and every
refusal of spec §4.5 with its status — `not-found` as 404, everything else as 409, a malformed
`raw` as 400. Model the class on `TestUnits` and `TestTheTypesTab`, which already do this for the
two tabs that exist.

- [ ] **Step 6: Add the three routes**

In `src/ddd/gui/api.py`, `CONSTANT_PLANS` beside `TYPE_PLANS`, then the three methods modelled on
`_types`, `_type` and `_unit_plan`. `_constant_plan` turns the plan into a preview with
`previewed(plan.edits, stamps)` — the same function `_unit_plan` uses, and the one that already
knows how to preview a file the plan creates:

```python
        try:
            made = previewed(plan.edits, stamps)
        except EditError as refused:
            return _error(409 if refused.code in REFUSALS else 500, refused.code, str(refused))
```

`_planned_changes` is what turns those into the reply's `changes`. **Read its current signature in
the file rather than copying one from this plan**: PR #66 gives it a `revision` first parameter, and
whether that has reached this branch depends on when #66 merged.

`raw` is validated with `ddd.editing.parse_raw` before any plan is asked for, and a malformed one is
`400 bad-request` — a request that is not json is not a refusal about the project, which is how
`_settle` already treats it.

Then three `_ROUTES` entries:

```python
    "/api/shared": {"GET": Api._shared},
    "/api/constant": {"GET": Api._constant},
    "/api/constant-plan": {"GET": Api._constant_plan},
```

- [ ] **Step 7: Regenerate the page's types**

```bash
export PATH="$HOME/.local/node-v24.21.0/bin:$PWD/.venv/bin:$PATH"
cd gui && npm run schemas && git diff --stat src/generated/
```

Expected: `src/generated/api.ts` gains `SharedReply`, `SharedEntry`, `ConstantReply` and
`ConstantUse`. That directory is **gitignored** (`.gitignore:22`), so there is no diff to read and
nothing to commit - grep the file for the four interface names and let `npm run typecheck` prove the
page agrees with them. `npm run schemas` runs `ddd schema all` **and**
`ddd.gui.contract.api_schema`, so the package must be installed (`pip install -e .`); it is, in the
venv. Never edit that file by hand.

`contract.FindingRoute.kind` is a `Literal`, and a route kind missing from it makes `_finding` raise
a pydantic `ValidationError` for every finding that carries it. Add `constant` there as well as to
`Route.kind`'s docstring.

- [ ] **Step 8: Run both gates**

Run: `.venv/bin/python -m pytest -q && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy`
Expected: 100 %, all clean.

Run, from `gui/`: `npm run lint && npm run typecheck && npm test`
Expected: green. Nothing on the page reads the new types yet, so the only change here is the
generated file.

- [ ] **Step 9: Commit**

```bash
git add src/ddd/finding_routes.py src/ddd/gui/contract.py src/ddd/gui/api.py gui/src/api/types.ts tests/
git commit -m "$(printf "serve the project's constants, and lead a finding to one\n\nThree routes shaped like the types tab's, and a constant route tried ahead of\nthe type route - a structure member's dimension lies inside types[i], so the\nother order would open the type rather than the constant the finding is about.\n\nunknown-constant carries a name no file declares: the page opens its add form\nwith it filled in, which is what this part exists for.\n\nCo-Authored-By: Claude Opus 5 <noreply@anthropic.com>")"
```

---
## Task 6: the page's own decisions, under the coverage gate

**Files:**
- Create: `gui/src/lib/shared.ts`, `gui/src/lib/shared.test.ts`
- Modify: `gui/src/lib/route.ts` and `gui/src/lib/route.test.ts`
- Modify: `gui/src/lib/findings.ts:161` and `gui/src/lib/findings.test.ts`
- Modify: `gui/src/lib/undo.ts` and `gui/src/lib/undo.test.ts`
- Modify: `gui/src/api/types.ts`, `gui/src/api/client.ts`, `gui/src/api/client.test.ts`

**Interfaces:**
- Consumes: Task 5's `SharedReply`, `SharedEntry`, `ConstantReply`, `ConstantUse`, `PlanReply` from `src/generated/api.ts`; `lib/projectUnits.planEdit`; `lib/undo.fitted`.
- Produces: `ConstantPlanRequest`, `getShared`, `getConstant`, `getConstantPlan`, `tabTitle`, `isDeclared`, `planEdit`, `constantLabel`, and the three `shared` route shapes.

Everything in `src/lib`, `src/api` and `src/state` is at 100 % statements, branches, functions and
lines. Every branch written in this task needs a test; there are no component tests to hide behind.

- [ ] **Step 1: Write the failing tests**

`gui/src/lib/shared.test.ts`:

```ts
import { describe, expect, test } from "vitest";
import type { SharedReply } from "../api/types";
import { isDeclared, tabTitle } from "./shared";

const reply = (names: string[]): SharedReply => ({
  revision: 1,
  entries: names.map((name) => ({
    kind: "constant",
    name,
    value: "16",
    uses: 0,
    findings: 0,
  })),
});

describe("the tab's summary line", () => {
  test("names how many constants the project declares", () => {
    expect(tabTitle(reply(["A", "B"]).entries)).toBe("2 constants");
  });

  test("says one constant in the singular", () => {
    expect(tabTitle(reply(["A"]).entries)).toBe("1 constant");
  });

  test("says a project with none declares none, rather than showing a zero", () => {
    expect(tabTitle([])).toBe("This project declares no constants.");
  });
});

describe("whether a name is declared", () => {
  test("a name the table holds is declared", () => {
    expect(isDeclared(reply(["TREND_SAMPLES"]), "constant", "TREND_SAMPLES")).toBe(true);
  });

  test("a name it does not hold is not - which is what opens the add form", () => {
    expect(isDeclared(reply(["TREND_SAMPLES"]), "constant", "CELLS")).toBe(false);
  });

  test("a name of another kind is not, however it is spelled", () => {
    expect(isDeclared(reply(["TREND_SAMPLES"]), "section", "TREND_SAMPLES")).toBe(false);
  });
});
```

For `route.test.ts`, three parses and three addresses:

```ts
test("the shared files tab with nothing selected", () => {
  expect(parseRoute("/project", "?view=shared")).toEqual({ page: "project", view: "shared" });
  expect(hrefOf({ page: "project", view: "shared" })).toBe("/project?view=shared");
});

test("the shared files tab with a constant selected", () => {
  const route = { page: "project", view: "shared", kind: "constant", name: "TREND_SAMPLES" } as const;
  expect(parseRoute("/project", "?view=shared&kind=constant&name=TREND_SAMPLES")).toEqual(route);
  expect(hrefOf(route)).toBe("/project?view=shared&kind=constant&name=TREND_SAMPLES");
});

test("the shared files tab with a name offered for declaration", () => {
  const route = { page: "project", view: "shared", kind: "constant", declare: "CELLS" } as const;
  expect(parseRoute("/project", "?view=shared&kind=constant&declare=CELLS")).toEqual(route);
  expect(hrefOf(route)).toBe("/project?view=shared&kind=constant&declare=CELLS");
});

test("a selection with no kind is the bare tab", () => {
  expect(parseRoute("/project", "?view=shared&name=TREND_SAMPLES")).toEqual({
    page: "project",
    view: "shared",
  });
});
```

For `findings.test.ts`, the dead end that goes and the ones that stay:

```ts
test("a finding on a constants file no longer says it has no page", () => {
  expect(noRouteReason(finding("c.ddd.json", ""), stateWith("c.ddd.json", "constants"))).toBe(
    "it is about the project rather than a place in a file",
  );
});

test("a finding on a sections file still says so, sections being the part after this", () => {
  expect(noRouteReason(finding("s.ddd.json", "sections[0]"), stateWith("s.ddd.json", "sections"))).toBe(
    "s.ddd.json is a sections file, which has no page yet",
  );
});
```

Read the existing helpers in `findings.test.ts` and use them; `finding` and `stateWith` above stand
for whatever that file already calls them.

For `undo.test.ts`, one per action:

```ts
test.each([
  [{ action: "set", name: "TREND_SAMPLES", key: "value", raw: "16" }, "the value of TREND_SAMPLES"],
  [{ action: "set", name: "TREND_SAMPLES", key: "description" }, "the description of TREND_SAMPLES"],
  [{ action: "rename", name: "TREND_SAMPLES", to: "TREND_SLOTS" }, "the rename of 'TREND_SAMPLES' to 'TREND_SLOTS'"],
  [{ action: "add", name: "CELLS", raw: "8" }, "'CELLS' declared as a constant"],
  [{ action: "remove", name: "CELLS" }, "'CELLS' removed from the constants"],
] as const)("%o is undone as %s", (plan, label) => {
  expect(constantLabel(plan)).toBe(label);
});
```

For `client.test.ts`, one per route, asserting the exact url — including that a name with a space
and a `#` is encoded, which is the bug `client.test.ts:164` already pins for `/api/file`.

- [ ] **Step 2: Run them to verify they fail**

Run, from `gui/`: `npm test -- --run`
Expected: FAIL — `Cannot find module './shared'`, plus the route, findings, undo and client
assertions.

- [ ] **Step 3: Write `lib/shared.ts`**

```ts
import type { Changes, PlanReply, SharedEntry, SharedReply } from "../api/types";
import { planEdit as editOfPlan } from "./projectUnits";

/** The line above the table: what this tab holds, or that the project has nothing of the kind.
 *
 * A project with no constants is told so in words rather than shown a table with a zero in it:
 * the tab is where a constant is declared, and an empty table with a count above it reads as a
 * screen that failed to load. */
export function tabTitle(entries: readonly SharedEntry[]): string {
  if (entries.length === 0) return "This project declares no constants.";
  return `${entries.length} constant${entries.length === 1 ? "" : "s"}`;
}

/** Whether the table holds that entry.
 *
 * What decides between the panel and the add form. A route carries the name a finding named, and
 * `unknown-constant` names one no file declares - so the page asks the table it already has rather
 * than a second request that would answer 404 on purpose. It also settles the race where the
 * constant was declared between the analysis and the click. */
export function isDeclared(reply: SharedReply, kind: string, name: string): boolean {
  return reply.entries.some((entry) => entry.kind === kind && entry.name === name);
}

/** A preview's changes as `POST /api/edit` takes them, under the label an undo of it offers.
 *
 * The units tab's own converter, not a second one: a plan is a plan whichever route previewed it,
 * and two of these would drift. */
export function planEdit(plan: PlanReply, label: string): Changes | null {
  return editOfPlan(plan, label);
}
```

- [ ] **Step 4: Add the routes, the labels, the client and the dead end**

`lib/route.ts`: the three shapes in the union, the parse arm and the `hrefOf` arm. The parse arm
reads `kind`, `name` and `declare`, and answers the bare tab where `kind` is absent or where
neither `name` nor `declare` is there — a half-written address is the tab, never a crash.

`lib/undo.ts`: `constantLabel`, beside `unitLabel` and `typeLabel`, using the same `fitted` helper.

`api/types.ts`: `ConstantPlanRequest`, beside `UnitPlanRequest` and `TypePlanRequest`.

`api/client.ts`:

```ts
export const getShared = (fetchImpl: Fetch = fetch) =>
  request<SharedReply>("/api/shared", {}, fetchImpl);

export const getConstant = (name: string, fetchImpl: Fetch = fetch) =>
  request<ConstantReply>(`/api/constant?name=${encodeURIComponent(name)}`, {}, fetchImpl);

export const getConstantPlan = (query: ConstantPlanRequest, fetchImpl: Fetch = fetch) =>
  request<PlanReply>(`/api/constant-plan?${searchOf(query)}`, {}, fetchImpl);
```

`searchOf` stands for however `getUnitPlan` already builds its query string — read it and use the
same one rather than writing a second.

`lib/findings.ts:161`: the kinds with a screen are no longer only `component`. Write it as a set the
line reads from, so that the sections and rasters parts add a word each rather than rewrite the
condition:

```ts
/** The file kinds the page has a screen for. Sections and rasters are the parts after this one,
 * and their findings keep saying so rather than leading somewhere blank. */
const SHOWN = new Set(["component", "constants"]);
```

- [ ] **Step 5: Run the page gate**

Run, from `gui/`: `npm run lint && npm run typecheck && npm test`
Expected: green, and Vitest at 100 % over `src/api`, `src/lib`, `src/state`. A branch with no test
fails the gate here, which is the point.

- [ ] **Step 6: Commit**

```bash
git add gui/src/lib gui/src/api
git commit -m "$(printf "the shared files tab's own decisions, under the coverage gate\n\nIts summary line, whether a name is declared - which is what chooses between\nthe panel and the add form, and settles the race where it was declared since -\nthe three addresses of the tab, the undo labels, and the client. A constants\nfile is no longer a dead end; sections and rasters still say they are.\n\nCo-Authored-By: Claude Opus 5 <noreply@anthropic.com>")"
```

---

## Task 7: the table, and the tab it lives in

**Files:**
- Create: `gui/src/components/SharedTableView.tsx`, `gui/src/components/SharedTableView.stories.tsx`
- Create: `gui/src/screens/SharedPage.tsx`
- Modify: `gui/src/app/App.tsx:22-29` (the tab strip and the screen it shows)

**Interfaces:**
- Consumes: Task 6's `getShared`, `tabTitle`, and the `shared` route shapes.
- Produces: no module another task imports. Task 8 adds the panel beside this table.

Read `gui/src/components/UnitsTableView.tsx`, `gui/src/components/TypesTableView.tsx` and
`gui/src/screens/UnitsPage.tsx` before writing. This table is their sibling: a
`react-aria-components` `Table` with `selectionMode="single"`, a `Column isRowHeader` first, and the
selection handler shape `TypesTableView` already uses.

- [ ] **Step 1: Write the component**

`SharedTableView` takes `{ reply: SharedReply; selected: string | undefined; onSelect: (name: string | undefined) => void }` and draws:

| Column | Cell |
| --- | --- |
| `Name` (`isRowHeader`) | `entry.name` |
| `Kind` | `entry.kind` |
| `Value` | `entry.value`, the json text the file spells |
| `Used by` | `entry.uses`, empty where it is 0 — as `TypesTableView` draws its own counts |
| `Findings` | `entry.findings`, empty where it is 0 |

No `Description` column: a constant's description is a full sentence — the shipped example's is
*sample slots of a pressure trend buffer, a device wide size no single component owns* — and it
would dominate every row, while the value is what a reader scans a list of constants for (spec
§5.1). The description is in the panel.

Above the table, `tabTitle(reply.entries)`, and for a project that declares none, that line and a
single *Declare a constant* button.

And, per spec §5.4, a warning line above the table naming any constants file that did not load: its
constants are in no index, so they are in no row either, and a table that silently omitted them
would read as a project that declares nothing. The state the page already holds says which files
did not load (`State.files`, its `loaded` flag) — filter it by `kind === "constants"` rather than
asking the server a second question. One of the stories in Step 2 draws this line.

- [ ] **Step 2: Write the stories**

`SharedTableView.stories.tsx`, following `TypesTableView.stories.tsx` exactly in shape:

- **two homes** — `TREND_SAMPLES` (`16`, used by 1) and `PRESSURE_CELLS` (`8`, used by 2), one from
  a constants file and one declared inline, which is what the tab is for.
- **a row with a finding** — `TREND_SAMPLES` with `findings: 1`, the `dimension-value` case.
- **nothing declared** — the empty line and the button.
- **a constants file that did not load** — the warning line above a table missing its constants,
  which is the state spec §5.4 names.

Each story becomes a screenshot reference automatically: `screenshots/stories.spec.ts` walks Ladle's
`meta.json`, so no spec changes.

- [ ] **Step 3: Write the screen and add the tab**

`SharedPage.tsx` reads `/api/shared` with `useQuery`, keyed `["shared", revision]`, with
`placeholderData: (previous) => previous` so the table stays up while the next revision is read —
the reason `UnitsPage` does the same is that swapping it for a loading line lost the reader's place
on every edit. It holds the selection from the route and draws the table; Task 8 puts the panel
beside it in the `with-panel` div `UnitsPage` uses.

In `app/App.tsx`, `["shared", "Shared files"]` between `["types", "Types"]` and
`["findings", "Findings"]`, and the `view === "shared"` arm rendering `SharedPage`.

- [ ] **Step 4: Run the page gate and photograph the stories**

Run, from `gui/`: `npm run lint && npm run typecheck && npm test && npm run build && npm run ladle:build`
Expected: green. Vitest is unchanged — there are no component tests.

Run, from the repo root: `UPDATE=1 docker compose run --rm gui-screenshots`
Then `git status --short gui/screenshots/references` — expected: only the new stories' PNGs added,
nothing from parts 1-12 modified. **Open the new images and look at them.** A table that renders as
an empty box passes every gate above.

- [ ] **Step 5: Commit**

```bash
git add gui/src/components gui/src/screens gui/src/app gui/screenshots/references
git commit -m "$(printf "a Shared files tab, listing the project's constants\n\nOne table for the three vocabularies with no page - constants now, sections and\nrasters later - with a Kind column, and a Value column where the types tab has\nDescription: a constant's description is a sentence that would fill the row, and\nits value is what a reader scans the list for.\n\nCo-Authored-By: Claude Opus 5 <noreply@anthropic.com>")"
```

---
## Task 8: a constant's panel, and the four changes it makes

**Files:**
- Create: `gui/src/components/ConstantPanelView.tsx`, `gui/src/components/ConstantPanelView.stories.tsx`
- Create: `gui/src/screens/ConstantPanel.tsx`
- Modify: `gui/src/screens/SharedPage.tsx` (the panel beside the table, and the add form)

**Interfaces:**
- Consumes: Task 6's `getConstant`, `getConstantPlan`, `planEdit`, `constantLabel`, `isDeclared`; `screens/UnitPanel.tsx`'s exported `refusalOf`; `lib/refusals.shownRefusal`; `components/Changes.tsx`.
- Produces: nothing another task imports.

Read `gui/src/screens/UnitPanel.tsx` and `gui/src/screens/TypePanel.tsx` whole first. This panel is
their sibling and must handle the same four states they do: a plan asked for at every revision, a
refusal drawn in a banner, a `stale` refusal that waits for a later revision rather than clearing,
and the entry disappearing under the reader.

`usePlan` in `UnitPanel.tsx` is typed to `UnitPlanRequest` and keyed `["unit-plan", …]`. Write a
`useConstantPlan` in `ConstantPanel.tsx` in the same shape, keyed `["constant-plan", …]`, rather
than widening theirs: the key has to differ so that invalidating one tab's plans does not throw away
the other's, and a generic taking both would be a wider change than this part needs.

- [ ] **Step 1: Write the component**

`ConstantPanelView` takes the `ConstantReply`, the plan for whatever change is being previewed, a
refusal string or null, a busy flag, and the callbacks. It draws:

- the constant's **name** as the panel's heading, and the panel's `aria-label` — so the journey and
  the screenshot stories can address it the way they address a unit's panel;
- **where it is declared**: the entry's file name, linking to that file's own page where it is a
  component, as `TypePanelView` does for a type declared inline;
- **Value**, an editable text field holding the json text, with the reason it is text and not a
  number input stated in a comment: `2` and `2.0` are two different constants, and a number input
  would hand back `2` for both;
- **Description**, an editable text field;
- **Used by**: one row per `ConstantUse`, the variable or `Sample_t.history`, its component where it
  has one, linking to that variable's own page;
- **Findings**: the same list `UnitPanelView` draws, through `distinctFindings`/`keyedFindings`;
- **Rename** and **Remove** controls;
- the `Changes` view for whatever is previewed, and one banner for a refusal.

- [ ] **Step 2: Write the stories**

`ConstantPanelView.stories.tsx`:

- **a constant two shapes name** — `TREND_SAMPLES`, value `16`, a description, two uses, no findings.
- **a value no shape can use** — the same constant with value `2.5` and a `dimension-value` finding,
  which is the state this tab exists to let a reader fix.
- **a constant nothing names** — no uses, so *Remove* is offered rather than refused.
- **a refused rename** — the banner carrying the editor's own sentence.
- **declaring one** — the add form with `PRESSURE_CELLS` filled in, as `unknown-constant` leaves it.

- [ ] **Step 3: Write the screen**

`ConstantPanel.tsx` reads `/api/constant?name=`, asks for the previewed plan of whichever change is
open, and applies it with `postEdit(planEdit(plan, constantLabel(request)))`. It invalidates
`["shared"]`, `["constant"]` and `["constant-plan"]` on settle, and `["state"]` is invalidated by
`postEdit`'s own path as every other edit does — check how `UnitPanel` does it and do the same.

`SharedPage` gains: the panel beside the table when the route names a declared entry, and the add
form when the route names one that is not declared or when the reader presses *Declare a constant*.
`isDeclared` is what chooses, from the table the page already has.

- [ ] **Step 4: Drive it by hand**

Build the pages and run the real server over a copy of `examples/vocabulary`:

```bash
export PATH="$HOME/.local/node-v24.21.0/bin:$PWD/.venv/bin:$PATH"
cd gui && npm run build && cd ..
cp -r examples/vocabulary /tmp/vocab-gui && cd /tmp/vocab-gui
ddd gui project.ddd.json --no-browser
```

Open the address it prints in the browser pane (`.claude/launch.json` has a config; read the
`driving-ddd-gui-in-browser-pane` notes if the token exchange trips you up — the api needs the
cookie, not the token in the query). Then, by hand: change `TREND_SAMPLES` to `2.5` and watch a
`dimension-value` finding appear with a route back; change it to `12` and watch it go; rename it and
check every dimension followed; declare a constant; remove one; and take a screenshot of the panel.
**Look at the screenshot.** Record what you did in the report.

- [ ] **Step 5: Run the page gate and photograph the stories**

Run, from `gui/`: `npm run lint && npm run typecheck && npm test && npm run build && npm run ladle:build`
Then, from the root: `UPDATE=1 docker compose run --rm gui-screenshots`, and check
`git status --short gui/screenshots/references` shows only additions. Open the new images.

- [ ] **Step 6: Commit**

```bash
git add gui/src gui/screenshots/references
git commit -m "$(printf "a constant's panel, and the four changes it makes\n\nIts value as the text its file spells - a number input would hand back 2 for a\nconstant its author wrote 2.0, and those are two different constants - its\ndescription, the shapes that name it, its findings, a rename that follows every\none of them, and declaring or removing one.\n\nCo-Authored-By: Claude Opus 5 <noreply@anthropic.com>")"
```

---

## Task 9: the way in from a declaration, the journey, and the documentation

**Files:**
- Modify: `gui/src/components/DimensionsField.tsx`
- Create: `gui/e2e/constants.spec.ts`
- Modify: `docs/command_line_interface.rst` (the `ddd gui` row, near line 288)

**Interfaces:**
- Consumes: Tasks 6-8's routes and screens.
- Produces: nothing.

- [ ] **Step 1: Make a dimension a way in**

**Not `DimensionsField`** — that is the add-a-declaration form's `ComboBox` editor, not a display, and
an earlier draft of this plan named it wrongly. `dimensions` is one of a variable's own keys
(`src/ddd/variable_keys.py:35`), so it is already a row of `gui/src/components/VariableKeysTable.tsx`.

That file is also where part 6 put its own way in: it takes `onOpenType: (name: string) => void`
(`:14`) and calls it from a type's value at `:92`, wired from `gui/src/app/App.tsx:156` and `:216`.
Mirror it with an `onOpenConstant`, wired the same way, called from the `dimensions` row.

An entry that is a literal number stays text; an entry that is a name becomes a link to the Shared
files tab carrying `kind=constant` and that name. The tab decides what to show, so one link serves a
constant that is declared and one that is not — `isDeclared` answers that on the other side, and this
end needs to know nothing about which constants exist. Where the row renders its entries joined into
one string, they have to be split so each name is its own link.

- [ ] **Step 2: Write the journey**

`gui/e2e/constants.spec.ts`, over a copy of `examples/vocabulary`. One journey, the whole point of
the part:

1. Break a shape so `unknown-constant` is filed: rewrite `pump.ddd.json`'s
   `["TREND_SAMPLES"]` to `["TREND_SLOTS"]` from outside the page, the way
   `e2e/demo.ts`'s helpers write a file.
2. Open the Findings tab and follow that finding.
3. Land on the Shared files tab with the add form holding `TREND_SLOTS`.
4. Give it a value and apply.
5. The finding is gone, and the table holds `TREND_SLOTS`.

**No `page.waitForResponse`.** Wait on what the reader would see — `expect(...).toBeVisible()` and
`expect.poll` on the table's own rows — which is what the rest of `e2e/` does and what part 6's CI
failure taught. Use `openPanel`-style helpers from `e2e/demo.ts` where they fit rather than writing
new selectors.

Run: `export PATH="$HOME/.local/node-v24.21.0/bin:$PATH" && cd gui && npm run build && PLAYWRIGHT_CHANNEL=chrome DDD_PYTHON="$PWD/../.venv/bin/python" npx playwright test e2e/constants.spec.ts`
Expected: PASS. Then run it twice more: a journey that passes once and fails once is a journey that
fails in CI on a different machine.

- [ ] **Step 3: Document the tab**

In the `ddd gui` row of `docs/command_line_interface.rst`, after the Compare tab's paragraph and
before the `-b DIR` sentence, add what the tab holds: every constant the project declares, from a
constants file or a component's own list, with its value and what names it; that its value and
description are changed there and a rename follows every shape naming it; that one can be declared —
writing ``constants.ddd.json`` beside the project description and adding it to the ``includes``
where the project has none; that removing one anything names is refused; and that a finding naming a
constant leads there, a name nothing declares landing on the form that declares it.

Keep the register of the surrounding rows: what it does and what it refuses, no marketing, and the
reason where a reader would otherwise ask.

Run: `docker compose run --rm -e JAVA_TOOL_OPTIONS=-Duser.home=/tmp docs`
Expected: `build succeeded`, no warnings — the build runs `-W`.

- [ ] **Step 4: Commit**

```bash
git add gui/src/components/DimensionsField.tsx gui/e2e/constants.spec.ts docs/command_line_interface.rst
git commit -m "$(printf "reach a constant from the shape that names it, and say so in the docs\n\nA dimension that names a constant becomes a link, as part 6's 'fixed by the\ntype' did, and the tab decides whether that name has a panel or a form. One\njourney drives the whole point of the part: a finding nobody could act on\nbecomes a constant declared in two clicks.\n\nCo-Authored-By: Claude Opus 5 <noreply@anthropic.com>")"
```

---

## Milestone gate

Run every gate on the branch tip, and do not treat a green run from an earlier task as evidence for
the tip:

```bash
export PATH="$HOME/.local/node-v24.21.0/bin:$PWD/.venv/bin:$PATH"

# Python
python -m pytest -q && ruff check . && ruff format --check . && mypy

# The page
cd gui && npm run lint && npm run typecheck && npm test && npm run build && npm run ladle:build && cd ..

# The stories, unchanged except for this part's own
docker compose run --rm gui-screenshots
git status --short gui/screenshots/references          # nothing modified, only this part's added

# The journeys, three consecutive clean runs
cd gui && PLAYWRIGHT_CHANNEL=chrome DDD_PYTHON="$PWD/../.venv/bin/python" npm run e2e && cd ..

# The documentation
docker compose run --rm -e JAVA_TOOL_OPTIONS=-Duser.home=/tmp docs
```

And by hand, once, on a copy of `examples/vocabulary`: an `unknown-constant` followed to the form
that declares it, a `dimension-value` followed to the value that causes it, a rename that every
dimension follows, a project with no constants file getting one, and a removal refused while a shape
names it. A screenshot of each, opened and looked at.

## Progress log

| Task | Started | Duration | Tokens | Notes |
| --- | --- | --- | --- | --- |
| | | | | |

## Left open

Filled in as the work goes. Each entry says what was not done and what it costs.

## Rulings taken

| # | Ruling | Why | Cost if wrong |
| --- | --- | --- | --- |
| 1 | One tab for constants, sections and rasters, not three | The three are near-identical in shape - one name, one or two scalar properties, one description - so three tables, three panels and three modules would be triplication; and the tab needs no navigation added when the other two land | The table carries three property shapes from the start |
| 2 | The tab is labelled `Shared files`, not `Vocabulary` | The codebase calls all three of these files vocabularies, but the Units tab's shipped copy already uses that word for units, so the label would collide with text a reader has seen | A reader may expect Units and Types under it; the heading names the kinds it holds |
| 3 | `unknown-constant` gets a route, not a one-click fix | Nothing in the project says what an array's length is, so a fix would write `1` and hope; part 11's fixes exist because a mismatch has one correct value the project already states | A reader still types the number, which they would have had to anyway |
| 4 | One route kind, and the page decides between panel and form | The route carries a name that may not be declared; asking the table the page already has also settles the race where it was declared since the analysis | A stale table shows the wrong one of the two for one revision |
| 5 | One `add`, not units' `add` plus `adopt` | The constants in use are the ones `unknown-constant` names, and their values cannot be harvested | A project with many undeclared constants is declared one at a time |
| 6 | A row's finding count reaches its uses, unlike the Types tab's | `dimension-value` is filed at the shape and is about nothing but the constant's value | Two vocabulary tables count differently until the Types tab is brought along |
| 7 | A value is judged by `ConstantValue` itself before it is written | A value the format refuses stops the project loading, emptying every tab because of one keystroke in this one | A reader is refused a value the loader would in fact have taken, if the model and the plan ever disagree |
| 8 | `_included` moves into `loading.py` as `included_files` | Two clients asking which files a project includes must get the run's own answer, and each swallowing the three exceptions its own way is how they drift | A one-line revert |
| 9 | `Value` in the table where the Types tab has `Description` | A constant's description is a full sentence that would fill the row; its value is what a reader scans the list for | A reader opens the panel to read a description |
| 10 | One server module for the three kinds, written concretely for constants | An abstraction shaped by a single example is worse than two cases and then a shape | The sections part refactors rather than extends |
