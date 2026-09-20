# The project's units in the GUI (part 2) implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Units tab lists every unit a project states and where; from it a unit is renamed everywhere - two spellings merged into one - the vocabulary is described, added to and pruned, and a project without one adopts its units; editors get the same rename and two quick fixes.

**Architecture:** The navigation index records every place a unit is stated and every vocabulary entry. A new `ddd.lsp.units` plans each change - rename, add, describe, remove, adopt - as `ddd.editing` operations on JSON pointers, and both clients use the same plan: the language server renders it as text edits (Rename Symbol on a unit, two quick fixes on `unknown-unit`), and `ddd gui` previews it through three read-only endpoints and applies it through the existing `POST /api/edit`, which learns to create the file an adoption writes. The page gains a Units tab - a table and a panel beside it, part 1's pattern - with a Ladle story and screenshot for every state.

**Tech Stack:** Python 3.12+ with pydantic; React 19.3, TypeScript 7 strict, TanStack Query 5, `react-aria-components` 1.21.1, `@ladle/react` 5.1.1, Vitest, Playwright 1.63.0 and its image `mcr.microsoft.com/playwright:v1.63.0-noble`.

**Spec:** `docs/superpowers/specs/2026-09-19-gui-units-project-design.md` (part 2 of three; read it, and the mockups beside it in `docs/superpowers/specs/2026-09-19-gui-units-project/`, before starting any task). Part 1's spec and plan, `2026-09-18-gui-units-design.md` and `plans/2026-09-18-gui-units.md`, describe the panel, the picker, the design system and the screenshot tests this builds on.

## Global Constraints

- Python floor 3.12; **no new runtime dependency** of the Python package, and no new frontend dependency.
- Python gate: `python -m pytest` at 100 % line **and** branch coverage, `ruff check .`, `ruff format --check .`, `mypy`. No `pragma: no cover`, no `pytest.skip`/`skipif`/`xfail`/`importorskip`.
- Line length 100; ruff selects E, F, W, I, N, UP, B, SIM, RUF, ANN, PTH, C4; mypy strict with the pydantic plugin.
- **The Python gate runs in every task that touches Python, the documentation, `gui/scripts/licenses.mjs` or anything `tests/test_documentation.py` reads** - part 1's CI was red for three hours because a frontend task changed `licenses.mjs` and ran no Python.
- Every request and answer of the API is declared in `src/ddd/gui/contract.py`; the page's types are generated from it by `npm run schemas`. Never hand-write a type the generator produces.
- Values travel as raw JSON text; pointers are DDD's own spelling (`component.interface[0].definition.unit`, `units[2]`, `types[1].members[0].unit`).
- A unit's spelling is exact: `rpm` and `RPM` are two units. The empty unit is no unit and is never recorded, renamed or adopted.
- The language server's existing tests - renames of variables, types and constants, and every quick fix - pass unchanged.
- **A story imports nothing from `@ladle/react`.** A story is a plain exported function component.
- Vitest keeps its 100 % gate over `src/api`, `src/lib`, `src/state`. Widgets and screens are covered by stories, screenshot tests and end-to-end journeys.
- The Content-Security-Policy stays `default-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'none'`, and `gui/public/pressable.css` stays linked from `gui/index.html` under the id `react-aria-pressable-style`. No page may report a violation.
- **A React Aria `className` is a function keeping `defaultClassName`** when a class is added (`({ defaultClassName }) => \`${defaultClassName} has-error\``): a string replaces React Aria's own class, and `ui.css` selects on it.
- **Journeys that drive a picker type and press Enter as well as click an option**: part 1's final review found a typed unit that Enter never chose, which no clicking journey could see.
- **A new or changed story gets its screenshot reference made in Playwright's image** - `UPDATE=1 docker compose run --rm gui-screenshots`, then `docker compose run --rm gui-screenshots` - and every new or changed reference is opened and looked at. References are made nowhere else, and no comparison is loosened.
- `ddd gui` stays labelled **preview**.
- Two machines:
  - **Linux PC** (`/home/sauci/Documents/Github/ddd`): `export PATH="$HOME/.local/node-v24.21.0/bin:$PWD/.venv/bin:$PATH"; export DDD_PYTHON="$PWD/.venv/bin/python"` at the repository root. Journeys: `cd gui && PLAYWRIGHT_CHANNEL=chrome npm run e2e`. The documentation is built in the development image, since this PC has no Java or PlantUML: `docker compose run --rm --user "$(id -u):$(id -g)" -e JAVA_TOOL_OPTIONS=-Duser.home=/tmp ddd python -m sphinx -M html docs build/docs_out -W`. Docker cannot see the session's scratchpad; a throwaway copy that Docker must read goes under the ignored `build/`.
  - **Windows PC** (Git Bash): `export PATH="/c/git/ac11/ddd/.venv/Scripts:/c/Program Files/nodejs:/c/Users/lmbsog0/AppData/Local/Programs/CLion/bin/mingw/bin:$PATH" && cd /c/git/ac11/ddd`; journeys with `DDD_PYTHON=/c/git/ac11/ddd/.venv/Scripts/python.exe PLAYWRIGHT_CHANNEL=msedge npm run e2e`. No Docker: screenshot references are made on the Linux PC or read from CI.

## Prerequisites (before Task 1)

- The branch `feature/gui-units-project` starts from master after #49 (`aa88983`); the spec is its first commit, and draft pull request #51 carries it.
- The venv has `pip install -e ".[dev]"`, `gui/` has `npm ci`, and the gate is green on the branch before anything changes: the Python gate, `cd gui && npm run schemas && npm run lint && npm run typecheck && npm test && npm run build`.

## Conventions for every task

- Work on `feature/gui-units-project`. Tests first: write the failing test, watch it fail, implement, watch it pass.
- One commit per task (a fix round may add commits), its message a lowercase sentence saying what the change does, ending with a blank line and `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`. Push after each task.
- Before a task's commit, run the gate for what it touched: the Python gate for Python (and per the constraint above); `npm run lint && npm run typecheck && npm test && npm run build` for the page, `PLAYWRIGHT_CHANNEL=chrome npm run e2e` when a screen or journey changed, and the screenshot service when a story changed.
- After Task 5, `npm run schemas` regenerates `gui/src/generated/api.ts`; run it before any frontend task.
- Scratch files go to the session scratchpad, never into the repository.
- Record each task in the **Progress log** at the end: start time, duration, tokens, notes.

## File structure

| File | Responsibility |
| --- | --- |
| `src/ddd/lsp/navigation.py` | `UnitSite`; `Index.units` and `Index.vocabulary`, recorded by `index()`; `renameable_at` recognises a unit. |
| `src/ddd/loading.py` | `Workspace.unit_entries`, every vocabulary entry a unit listed twice included; `expand_include` made public, so the plans find the units files by the loader's own rule. |
| `src/ddd/variables.py` | `units_in_use(built)` counts from `Index.units` (Task 1); `planned` and `hunks` made public, `Planned.fingerprint` may be `None` (Task 5). |
| `src/ddd/analysis.py` | `close_units`, the did-you-mean `_check_units` reports and the rename quick fix offers - one function, one cutoff. |
| `src/ddd/lsp/units.py` (new) | `UnitProject`, `PlannedEdit`, `UnitPlan`, `UnitRefusalError`; the five plans; `unit_project`; `text_edits`, a plan as the protocol's text edits. |
| `src/ddd/lsp/server.py` | Prepare and rename on a unit; the refusals and the drift check for it. |
| `src/ddd/lsp/edits.py` | The two quick fixes on `unknown-unit`. |
| `src/ddd/editing.py` | `FileChange.fingerprint` may be `None` - the change creates its file - and `FileChange.like`; `apply_changes` creates, rolls back and copies access; `edited` made public. |
| `src/ddd/gui/session.py` | `LOAD_CHECKS` imported from `ddd.lsp.navigation` (Task 3); `edit` accepts a created file only beside the project description and only when the same edit includes it (Task 4). |
| `src/ddd/gui/server.py` | The query handed to the API keeps blank values, so a description can be cleared (Task 5). |
| `src/ddd/project_units.py` (new) | The project's units as the page shows them - the table's rows, one unit's places - and a plan's preview with its hunks. No GUI, no HTTP. |
| `src/ddd/gui/contract.py`, `src/ddd/gui/api.py` | `GET /api/units` gains the table; `GET /api/unit`; `GET /api/unit-plan`; `Change.fingerprint` nullable. |
| `tests/test_unit_index.py`, `tests/test_unit_plans.py` (new) | The index's record of units; the plans, case by case. |
| `tests/test_lsp.py`, `tests/test_units.py`, `tests/test_variables.py`, `tests/test_editing.py`, `tests/test_gui_session.py`, `tests/test_gui_api.py`, `tests/test_gui_server.py` | The rename and quick fixes; `close_units`; part 1's count; file creation; the session's rule; the endpoints, on copies of `examples/demo` and `examples/vocabulary`; blank parameters over real HTTP. |
| `gui/src/api/client.ts`, `gui/src/api/types.ts` | `getUnit`, `getUnitPlan`; the new types re-exported. |
| `gui/src/lib/projectUnits.ts` (new) | The table's order, the panel's sentences, what a unit's state offers, the rename picker's sections, a plan's edit. Pure. |
| `gui/src/lib/route.ts` | `view: "units"` and `unit`. |
| `gui/src/components/UnitsTableView.tsx`, `UnitPanelView.tsx`, `AdoptBannerView.tsx` (new, with `AdoptPanelView`) | The table, a unit's panel, the adoption banner and its preview as pictures of their props, each with stories. |
| `gui/src/components/Changes.tsx` (new), `UnitPicker.tsx`, `VariablePanelView.tsx` | Show changes, shared by both panels; the picker's `name` becomes `label`. |
| `gui/src/stories/fixtures.ts`, `gui/src/lib/units.test.ts`, `gui/src/styles/ui.css` | Part 1's `UnitsReply` literals gain the new fields (Task 5); the Units tab's mock answers and rules (Task 7). |
| `gui/src/screens/UnitsPage.tsx`, `gui/src/screens/UnitPanel.tsx` (new), `gui/src/app/App.tsx` | The tab's queries, plans and applies; the third tab. |
| `gui/e2e/project-units.spec.ts` (new), `gui/e2e/fixtures.ts`, `gui/e2e/demo.ts`, `gui/e2e/units.spec.ts` | The journeys; a fixture serving a copy of `examples/vocabulary`; the Units tab in the policy journey. |
| `gui/screenshots/references/*.png` | The new stories' references. |
| `CHANGELOG.md`, `docs/command_line_interface.rst`, `docs/editor_integration.rst`, `docs/developer_documentation.rst`, `docs/file_formats/units.rst` | What a user and a developer read. |

## Interfaces between the tasks

Every name here is exact; a task's implementer sees only their own task, and this is how they learn what their neighbours produce and consume.

**Task 1 produces** (`src/ddd/lsp/navigation.py`):

```python
@dataclass(frozen=True, slots=True)
class UnitSite:
    """One place a unit is stated: its string, and what states it."""

    site: Site
    """The unit's string itself: ``….definition.unit``, a scalar type's ``unit``, a member's."""

    kind: Literal["variable", "type", "member"]
    name: str
    """The variable's name, the type's, or ``Type.member`` for a structure member."""


# Index gains, beside its other records:
units: dict[str, list[UnitSite]]  # spelling -> every place it is stated, in index order
vocabulary: dict[str, list[Site]]  # spelling -> every vocabulary entry listing it, at `units[i]`
```

`Index.vocabulary` is read from a new `Workspace.unit_entries` (`src/ddd/loading.py`), which keeps every entry: `Workspace.units` keeps only the first of a unit listed twice. `units_in_use(built)` drops its unused `cache` parameter; its one caller, `api.py`'s `_units`, changes with it.

**Task 2 produces** (`src/ddd/lsp/units.py`):

```python
ADOPTED: Final = "units.ddd.json"

@dataclass(frozen=True, slots=True)
class UnitProject:
    project: Path  # the project description
    units_files: tuple[Path, ...]  # its units files, in the order its `project.includes` lists them
    unread: tuple[Path, ...]  # the project's files that did not load, sorted

@dataclass(frozen=True, slots=True)
class PlannedEdit:
    path: Path
    operations: tuple[Operation, ...]  # ddd.editing.Operation
    creates: bool = False  # the plan creates this file: operations is one `set` at pointer ""

@dataclass(frozen=True, slots=True)
class UnitPlan:
    edits: tuple[PlannedEdit, ...]  # one per file, sorted by path

class UnitRefusalError(Exception):  # ruff's N818 wants the suffix
    code: Literal["unreadable", "invalid", "not-found"]
    message: str

def unit_project(project: Path, unread: Sequence[Path], cache: dict[Path, Document]) -> UnitProject
def rename_unit(built: Index, project: UnitProject, old: str, new: str, cache: dict[Path, Document]) -> UnitPlan
def add_unit(built: Index, project: UnitProject, unit: str, cache: dict[Path, Document]) -> UnitPlan
def describe_unit(built: Index, project: UnitProject, unit: str, description: str, cache: dict[Path, Document]) -> UnitPlan
def remove_unit(built: Index, project: UnitProject, unit: str, cache: dict[Path, Document]) -> UnitPlan
def adopt_units(built: Index, project: UnitProject, cache: dict[Path, Document]) -> UnitPlan
```

Each plan raises `UnitRefusalError` for spec 4.2's refusals, before reading a file it would not write. `UnitProject.unread` holds the files that did not *load* - a units file whose only error is `duplicate-unit` loads, and a rename of a unit listed twice must go through.

**Task 3 produces** (`src/ddd/lsp/units.py`, `src/ddd/analysis.py`):

```python
def text_edits(plan: UnitPlan, cache: dict[Path, Document]) -> dict[str, list[dict[str, Any]]]
    # file URI -> the protocol's text edits, each operation rendered by the engine's own
    # replacement/removal/insertion/member_addition
def close_units(unit: str, vocabulary: Sequence[str]) -> tuple[str, ...]  # analysis.py
    # at most three, closest first, at the cutoff _check_units uses (0.5)
```

**Task 4 produces** (`src/ddd/editing.py`, `src/ddd/gui/contract.py`, `src/ddd/gui/session.py`):

```python
@dataclass(frozen=True, slots=True)
class FileChange:
    path: Path
    fingerprint: str | None  # None: the change creates the file, which must not exist
    operations: tuple[Operation, ...]
    like: Path | None = None  # for a created file, the file whose mode and owner it takes
```

`contract.Change.fingerprint: str | None`. `Session.edit` sets `like` to the project description for a created file.

**Task 5 produces** (`src/ddd/gui/contract.py`, `src/ddd/project_units.py`, `src/ddd/gui/api.py`):

```python
class ProjectUnit(_Frozen):  # one row of the Units tab
    unit: str
    description: str | None  # the vocabulary's, or None outside it or without one
    files: tuple[str, ...]  # the units files listing it, absolute posix; empty outside the vocabulary
    variables: int
    types: int
    members: int
    findings: int  # its unknown-unit and duplicate-unit findings

class UnitsReply(_Frozen):  # part 1's, extended
    revision: int
    vocabulary: tuple[VocabularyUnit, ...] | None
    used: tuple[UsedUnit, ...]
    units: tuple[ProjectUnit, ...]
    adoptable: int | None  # how many units adoption would list; None with a units file

class UnitEntry(_Frozen):
    file: str
    pointer: str

class UnitPlace(_Frozen):
    path: str
    pointer: str
    kind: Literal["variable", "type", "member"]
    name: str
    component: str | None  # a variable's component; None for a type or a member
    role: str | None  # "produces", "reads" or "local" for a variable; None otherwise

class UnitReply(_Frozen):  # GET /api/unit?name=
    revision: int
    unit: str
    description: str | None
    entries: tuple[UnitEntry, ...]
    sites: tuple[UnitPlace, ...]
    findings: tuple[Finding, ...]

class PlannedOperation(_Frozen):  # part 1's, widened
    op: Literal["set", "remove", "insert"]
    pointer: str
    raw: str | None

class PlannedChange(_Frozen):  # part 1's, fingerprint widened
    file: str
    fingerprint: str | None  # None: the file is created
    operations: tuple[PlannedOperation, ...]
    hunks: tuple[Hunk, ...]

class PlanReply(_Frozen):  # GET /api/unit-plan?action=…
    revision: int
    changes: tuple[PlannedChange, ...]
```

`GET /api/unit-plan` takes `action` (`rename`, `add`, `describe`, `remove`, `adopt`), `unit` (not for `adopt`), `to` (for `rename`) and `description` (for `describe`).

**Task 6 produces** (`gui/src/api/client.ts`, `gui/src/lib/projectUnits.ts`, `gui/src/lib/route.ts`):

```ts
export type UnitPlanRequest =
  | { action: "rename"; unit: string; to: string }
  | { action: "add" | "remove"; unit: string }
  | { action: "describe"; unit: string; description: string }
  | { action: "adopt" };
export function getUnit(name: string): Promise<UnitReply>;
export function getUnitPlan(plan: UnitPlanRequest): Promise<PlanReply>;

// lib/projectUnits.ts
export function unitRows(units: readonly ProjectUnit[]): ProjectUnit[];
export function statedBy(unit: ProjectUnit): string;
export function tabTitle(units: readonly ProjectUnit[], hasVocabulary: boolean): string;
export function unitMeta(unit: ProjectUnit, reply: UnitReply, hasVocabulary: boolean): string;
export function offers(unit: ProjectUnit, hasVocabulary: boolean): { describe: boolean; add: boolean; remove: boolean };
export function renameSections(unit: string, units: UnitsReply, narrow: string): UnitSection[];
export function renameConsequence(plan: PlanReply, from: ProjectUnit, to: string, units: UnitsReply): string;
export function adoptionSentence(adoptable: number): string;
export function planEdit(plan: PlanReply): Changes | null;

// lib/route.ts: Route's project page gains { page: "project"; view: "units"; unit?: string },
// at /project?view=units[&unit=…]
```

`UnitSection` and `enteredUnit` are part 1's (`gui/src/lib/units.ts`): the rename picker is part 1's `UnitPicker`, and Enter chooses what the text names.

**Task 7 produces** (`gui/src/components/`): `UnitsTableView`, `UnitPanelView`, `AdoptBannerView` - pictures of their props, named in the task.

**Task 8 produces** (`gui/src/screens/`, `gui/src/app/App.tsx`): `UnitsPage` and `UnitPanel`, and the third tab.

---

### Task 1: The index records units

**Files:**
- Modify: `src/ddd/loading.py` (`Workspace.unit_entries`; `_Loader.__init__`, `_Loader.load`, `_Loader._load_units`; new `_Loader._unit_entry`)
- Modify: `src/ddd/lsp/navigation.py` (imports; new `UnitSite`; `Index.units`, `Index.vocabulary`; `index`; new `_unit_stated`)
- Modify: `src/ddd/variables.py` (`units_in_use`)
- Modify: `src/ddd/gui/api.py` (`Api._units`, its `units_in_use` call)
- Create: `tests/test_unit_index.py`
- Modify: `tests/test_variables.py` (`TestUnits.test_the_units_in_use_are_counted_by_variable_most_used_first`)

**Interfaces:**
- Consumes: `ddd.loading.Workspace` (`components`, `types`), `LoadedComponent.declaration_location`, `LoadedType.location`, `.declared`, `.structure`, `.name`, `LoadedUnit.location()`, `.unit`; `ddd.models.ScalarType`; `ddd.diagnostics.Location`.
- Produces, for Tasks 2, 3 and 5:

```python
# src/ddd/lsp/navigation.py
@dataclass(frozen=True, slots=True)
class UnitSite:
    site: Site  # the unit's string itself
    kind: Literal["variable", "type", "member"]
    name: str  # the variable's name, the type's, or "Type.member"

# Index gains, after `mentions`:
units: dict[str, list[UnitSite]]  # spelling -> every place it is stated, in index order
vocabulary: dict[str, list[Site]]  # spelling -> every vocabulary entry listing it, at `units[i]`

# src/ddd/loading.py - Workspace gains, after `units`:
unit_entries: tuple[LoadedUnit, ...] = ()  # every entry of the units files, a unit listed twice twice

# src/ddd/variables.py
def units_in_use(built: Index) -> tuple[tuple[str, int], ...]
```

- [ ] **Step 1: The failing tests**

Create `tests/test_unit_index.py`:

```python
"""Where a project states each unit, and which entries of its vocabulary list it.

The navigation index's record of units is what renaming a unit reaches and what the Units tab of
``ddd gui`` counts, so each case here is a place a rename would otherwise leave holding the old
spelling, or a count the tab and the picker would otherwise disagree about.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from conftest import (
    component,
    declare,
    project,
    scalar_type,
    struct_type,
    types,
    value_member,
    write_tree,
)
from ddd.diagnostics import DiagnosticBag
from ddd.loading import load_workspace
from ddd.lsp.navigation import Index, Site, UnitSite, index
from ddd.variables import units_in_use

UNIT = "component.interface[0].definition.unit"


def built(tmp_path: Path, **files: Any) -> Index:
    """The index of a project including every file given, as the language server builds it."""
    write_tree(tmp_path, {"p.ddd.json": project("P", *files), **files})
    workspace = load_workspace(tmp_path / "p.ddd.json", DiagnosticBag())
    assert workspace is not None
    return index(workspace)


def at(tmp_path: Path, file: str, pointer: str) -> Site:
    """A site as the index records it, in the file the loader resolved."""
    return Site((tmp_path / file).resolve(), pointer)


class TestWhereAUnitIsStated:
    def test_every_declaration_stating_a_unit_is_recorded_as_its_variable(
        self, tmp_path: Path
    ) -> None:
        idx = built(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="rpm")),
            },
        )
        assert idx.units == {
            "rpm": [
                UnitSite(at(tmp_path, "a.ddd.json", UNIT), "variable", "Speed"),
                UnitSite(at(tmp_path, "b.ddd.json", UNIT), "variable", "Speed"),
            ]
        }

    @pytest.mark.parametrize(
        ("kind", "extra"),
        [
            ("measurement", {}),
            ("parameter", {}),
            ("value_block", {"dimensions": [4]}),
            ("axis", {"size": 4}),
            ("curve", {"axis": "Axis"}),
            ("map", {"x_axis": "Axis", "y_axis": "Axis"}),
        ],
    )
    def test_a_data_object_of_every_kind_states_its_unit(
        self, tmp_path: Path, kind: str, extra: dict[str, Any]
    ) -> None:
        idx = built(
            tmp_path,
            **{
                "a.ddd.json": component(
                    "A",
                    declare("output", "Table", kind=kind, unit="Nm", **extra),
                    declare("output", "Axis", kind="axis", size=4, unit="rpm"),
                )
            },
        )
        assert idx.units["Nm"] == [UnitSite(at(tmp_path, "a.ddd.json", UNIT), "variable", "Table")]

    def test_a_scalar_type_states_its_unit_under_its_own_name(self, tmp_path: Path) -> None:
        idx = built(tmp_path, **{"types.ddd.json": types(scalar_type("Speed_t", unit="rpm"))})
        assert idx.units == {
            "rpm": [UnitSite(at(tmp_path, "types.ddd.json", "types[0].unit"), "type", "Speed_t")]
        }

    def test_a_structure_member_states_its_unit_as_type_dot_member(self, tmp_path: Path) -> None:
        idx = built(
            tmp_path,
            **{
                "types.ddd.json": types(
                    struct_type("Sample_t", value_member("level"), value_member("rate", unit="Hz"))
                )
            },
        )
        assert idx.units == {
            "Hz": [
                UnitSite(
                    at(tmp_path, "types.ddd.json", "types[0].members[1].unit"),
                    "member",
                    "Sample_t.rate",
                )
            ]
        }

    def test_the_types_a_component_declares_inline_state_their_units_there(
        self, tmp_path: Path
    ) -> None:
        idx = built(
            tmp_path,
            **{
                "a.ddd.json": component(
                    "A",
                    declare("output", "Supply", typename="Volts_t"),
                    types=[
                        scalar_type("Volts_t", unit="V"),
                        struct_type("Frame_t", value_member("current", unit="A")),
                    ],
                )
            },
        )
        assert idx.units == {
            "A": [
                UnitSite(
                    at(tmp_path, "a.ddd.json", "component.types[1].members[0].unit"),
                    "member",
                    "Frame_t.current",
                )
            ],
            "V": [
                UnitSite(at(tmp_path, "a.ddd.json", "component.types[0].unit"), "type", "Volts_t")
            ],
        }

    def test_a_declaration_repeated_in_one_component_is_recorded_each_time(
        self, tmp_path: Path
    ) -> None:
        """``unknown-unit`` reads a repeat once; a rename has to rewrite both."""
        speed = declare("output", "Speed", unit="rpm")
        idx = built(tmp_path, **{"a.ddd.json": component("A", speed, speed)})
        assert [stated.site.pointer for stated in idx.units["rpm"]] == [
            UNIT,
            "component.interface[1].definition.unit",
        ]

    def test_the_empty_unit_is_no_unit_and_is_not_recorded(self, tmp_path: Path) -> None:
        idx = built(
            tmp_path,
            **{
                "types.ddd.json": types(
                    scalar_type("Ratio_t", unit=""),
                    struct_type("Pair_t", value_member("left", unit="")),
                ),
                "a.ddd.json": component(
                    "A", declare("output", "Plain", unit=""), declare("output", "Bare")
                ),
            },
        )
        assert idx.units == {}


class TestTheVocabulary:
    def test_both_forms_of_entry_are_recorded_at_the_entry(self, tmp_path: Path) -> None:
        idx = built(
            tmp_path,
            **{"units.ddd.json": {"units": ["rpm", {"unit": "Nm", "description": "torque"}]}},
        )
        assert idx.vocabulary == {
            "rpm": [at(tmp_path, "units.ddd.json", "units[0]")],
            "Nm": [at(tmp_path, "units.ddd.json", "units[1]")],
        }

    def test_a_unit_listed_twice_is_recorded_at_every_entry(self, tmp_path: Path) -> None:
        """The loader keeps the first of the two and reports the second as ``duplicate-unit``;
        a rename has to reach both, or the second still lists the spelling it renamed."""
        idx = built(
            tmp_path,
            **{
                "units.ddd.json": {"units": ["rpm", "Nm", {"unit": "rpm", "description": ""}]},
                "more.ddd.json": {"units": ["Nm"]},
            },
        )
        assert idx.vocabulary == {
            "rpm": [
                at(tmp_path, "units.ddd.json", "units[0]"),
                at(tmp_path, "units.ddd.json", "units[2]"),
            ],
            "Nm": [
                at(tmp_path, "units.ddd.json", "units[1]"),
                at(tmp_path, "more.ddd.json", "units[0]"),
            ],
        }

    def test_a_project_without_a_units_file_has_no_vocabulary(self, tmp_path: Path) -> None:
        idx = built(tmp_path, **{"a.ddd.json": component("A", declare("output", "S", unit="rpm"))})
        assert idx.vocabulary == {}

    def test_a_listed_unit_nothing_states_is_in_the_vocabulary_alone(self, tmp_path: Path) -> None:
        idx = built(tmp_path, **{"units.ddd.json": {"units": ["kPa"]}})
        assert (idx.units, list(idx.vocabulary)) == ({}, ["kPa"])


class TestTheUnitsInUse:
    def test_a_unit_only_types_and_members_state_is_used_by_no_variable(
        self, tmp_path: Path
    ) -> None:
        """The picker's count is of variables, as part 1 has it; a type's unit reaches no
        variable's count, not even that of a variable naming the type."""
        idx = built(
            tmp_path,
            **{
                "types.ddd.json": types(
                    scalar_type("Speed_t", unit="rpm"),
                    struct_type("Sample_t", value_member("rate", unit="Hz")),
                ),
                "a.ddd.json": component(
                    "A",
                    declare("output", "Speed", typename="Speed_t"),
                    declare("output", "Torque", unit="Nm"),
                ),
            },
        )
        assert units_in_use(idx) == (("Nm", 1),)

    def test_a_variable_two_components_declare_counts_once_under_each_spelling(
        self, tmp_path: Path
    ) -> None:
        idx = built(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="rpm")),
                "c.ddd.json": component("C", declare("output", "Idle", unit="RPM")),
            },
        )
        assert units_in_use(idx) == (("RPM", 1), ("rpm", 1))
```

In `tests/test_variables.py`, `TestUnits.test_the_units_in_use_are_counted_by_variable_most_used_first`, the last line becomes:

```python
        assert units_in_use(idx) == (("rpm", 2), ("Nm", 1))
```

Run: `python -m pytest tests/test_unit_index.py --no-cov`
Expected: FAIL at collection, `ImportError: cannot import name 'UnitSite' from 'ddd.lsp.navigation'`.

Run: `python -m pytest tests/test_variables.py --no-cov`
Expected: FAIL, `test_the_units_in_use_are_counted_by_variable_most_used_first` with `TypeError: units_in_use() missing 1 required positional argument: 'cache'`.

- [ ] **Step 2: Keep every entry of a units file**

In `src/ddd/loading.py`, `Workspace` gains a field right after `units` and its docstring:

```python
    unit_entries: tuple[LoadedUnit, ...] = ()
    """Every entry of the units files that loaded, in the order they were read.

    ``units`` keeps the first declaration of a spelling, which is all the check against the
    vocabulary needs; a unit listed twice is a ``duplicate-unit`` finding and is here twice.
    Renaming a unit needs both: an entry left out of the rename would still list the old
    spelling, in a file the rename said it had rewritten.
    """
```

In `_Loader.__init__`, right after `self._units_by_name: dict[str, LoadedUnit] = {}`:

```python
        self._unit_entries: list[LoadedUnit] = []
```

In `_Loader.load`, the project's `Workspace(...)` (the second one, after `self._validate_blocks(root)`), right after its `units=` argument:

```python
            unit_entries=tuple(self._unit_entries),
```

(The component's own `Workspace(...)` above it lists no units and keeps the default.) `_load_units` wraps each entry through a method that keeps it, and the method follows it:

```python
    def _load_units(self, path: Path, data: dict[str, Any]) -> None:
        """Read a unit vocabulary and register what it declares.

        A unit is registered under its spelling, so the second file to declare ``Nm`` is
        refused rather than merged: two files declaring one unit is either a copy that will
        drift or a disagreement about its description, and neither is worth keeping quiet.
        """
        self._load_vocabulary(
            path,
            data,
            file_model=UnitsFile,
            entries=lambda model: model.units,
            wrap=self._unit_entry,
            key=lambda loaded: loaded.unit,
            registry=self._units_by_name,
            noun="unit",
        )

    def _unit_entry(self, path: Path, index: int, declared: UnitDeclaration) -> LoadedUnit:
        """One entry of a units file, kept whether or not the registry takes it: the second
        declaration of a spelling is refused there, and is still an entry a rename rewrites."""
        entry = LoadedUnit(path, index, declared)
        self._unit_entries.append(entry)
        return entry
```

- [ ] **Step 3: Record the units in the index**

In `src/ddd/lsp/navigation.py`, the imports become:

```python
from typing import Any, Final, Literal

from ddd.build_info import BuildInfo
from ddd.diagnostics import DiagnosticBag, Location, Severity
```

Right after `Site`:

```python
@dataclass(frozen=True, slots=True)
class UnitSite:
    """One place a unit is stated: its string, and what states it."""

    site: Site
    """The unit's string itself: ``….definition.unit``, a scalar type's ``unit``, a member's."""

    kind: Literal["variable", "type", "member"]
    name: str
    """The variable's name, the type's, or ``Type.member`` for a structure member."""
```

`Index` gains two records after `mentions`:

```python
    units: dict[str, list[UnitSite]] = field(default_factory=dict)
    """Unit -> every place it is stated: a declaration's ``unit``, a scalar type's and a
    structure member's, which are the places ``unknown-unit`` checks - the declarations first,
    in the order the project lists its components, then the types by name.

    Keyed by the exact spelling, so ``rpm`` and ``RPM`` are two units, which is the drift a
    rename exists to merge. A declaration repeated in one component is here each time, though
    the check reads it once: a rename that left the repeat alone would leave the old spelling
    in the file. The empty unit is not here - a dimensionless value states no unit rather than a
    spelling of one.
    """

    vocabulary: dict[str, list[Site]] = field(default_factory=dict)
    """Unit -> every entry of the units files listing it, at ``units[i]``, whether the entry is
    the spelling on its own or an object naming it. Two entries are a unit listed twice."""
```

`index` becomes, and `_unit_stated` follows it:

```python
def index(workspace: Workspace) -> Index:
    """Read the positions out of an already loaded project."""
    built = Index()
    for loaded in workspace.components:
        for position, declaration in enumerate(loaded.component.interface):
            location = loaded.declaration_location(position, "definition")
            site = Site(location.path, location.pointer)
            name = declaration.definition.name
            built.declarations.setdefault(name, []).append(site)
            if declaration.scope.is_producer:
                built.producers.setdefault(name, []).append(site)
            built.mentions.setdefault(name, []).append(
                Site(location.path, f"{location.pointer}.name")
            )
            for key, target in declaration.definition.references.items():
                where = loaded.declaration_location(position, f"definition.{key}")
                built.mentions.setdefault(target, []).append(Site(where.path, where.pointer))
            for named_size, suffix in spelled_dimensions(declaration.definition):
                where = loaded.declaration_location(position, f"definition.{suffix}")
                built.constant_uses.setdefault(named_size, []).append(
                    Site(where.path, where.pointer)
                )
            named = declaration.definition.declared_type
            if named is not None:
                where = loaded.declaration_location(position, "definition.typename")
                built.type_uses.setdefault(named, []).append(Site(where.path, where.pointer))
            _occupy(built, declaration.definition.conversion)
            _unit_stated(
                built,
                declaration.definition.unit,
                loaded.declaration_location(position, "definition.unit"),
                "variable",
                name,
            )
    for entry in workspace.types:
        built.types[entry.name] = Site(entry.path, entry.location().pointer)
        built.occupied[entry.name] = f"the name of the type '{entry.name}'"
        declared = entry.declared
        if isinstance(declared, ScalarType):
            _occupy(built, declared.conversion)
            _unit_stated(built, declared.unit, entry.location("unit"), "type", entry.name)
        structure = entry.structure
        if structure is None:
            continue
        for position, member in enumerate(structure.members):
            _occupy(built, member.conversion)
            _unit_stated(
                built,
                member.unit,
                entry.location(f"members[{position}].unit"),
                "member",
                f"{entry.name}.{member.name}",
            )
            # A member naming a base datatype names no type; the two keys keep them apart.
            if member.typename is not None:
                where = entry.location(f"members[{position}].typename")
                built.type_uses.setdefault(member.typename, []).append(
                    Site(where.path, where.pointer)
                )
            for index, dimension in enumerate(member.dimensions):
                if isinstance(dimension, str):
                    where = entry.location(f"members[{position}].dimensions[{index}]")
                    built.constant_uses.setdefault(dimension, []).append(
                        Site(where.path, where.pointer)
                    )
    for constant in workspace.constants:
        built.constants[constant.name] = Site(constant.path, constant.location().pointer)
        built.occupied[constant.name] = f"the name of the declared constant '{constant.name}'"
    for listed in workspace.unit_entries:
        where = listed.location()
        built.vocabulary.setdefault(listed.unit, []).append(Site(where.path, where.pointer))
    return built


def _unit_stated(
    built: Index,
    unit: str,
    where: Location,
    kind: Literal["variable", "type", "member"],
    name: str,
) -> None:
    """Note one place a unit is stated, unless it states the empty unit, which is no unit:
    ``unknown-unit`` never checks it, so a rename or an adoption has nothing to do with it."""
    if unit:
        built.units.setdefault(unit, []).append(
            UnitSite(Site(where.path, where.pointer), kind, name)
        )
```

- [ ] **Step 4: Count the units in use from the index**

In `src/ddd/variables.py`, `units_in_use` becomes (the imports stay: `read`, `Document` and `Path` are still used by its neighbours):

```python
def units_in_use(built: Index) -> tuple[tuple[str, int], ...]:
    """Every unit a declaration states, with how many variables state it: most used first, then
    by spelling. A variable several components declare counts once; no unit is not a unit.

    Counted from the index's record of units, which the Units tab counts from too, so the picker
    and the tab cannot disagree about how many variables state a unit. A unit only types and
    structure members state is used by no variable, and is not one of these.
    """
    counted = {
        unit: len({stated.name for stated in sites if stated.kind == "variable"})
        for unit, sites in built.units.items()
    }
    return tuple(
        sorted(
            ((unit, count) for unit, count in counted.items() if count),
            key=lambda pair: (-pair[1], pair[0]),
        )
    )
```

In `src/ddd/gui/api.py`, `Api._units`, the line

```python
        used = () if revision.index is None else units_in_use(revision.index, cache)
```

becomes

```python
        used = () if revision.index is None else units_in_use(revision.index)
```

(`cache` stays: `vocabulary_of` still reads the units files through it.)

- [ ] **Step 5: Run the tests**

Run: `python -m pytest tests/test_unit_index.py tests/test_variables.py tests/test_gui_api.py tests/test_lsp.py tests/test_loading.py --no-cov`
Expected: PASS, every existing test unchanged.

- [ ] **Step 6: The Python gate, then commit**

Run: `python -m pytest`, `python -m ruff format --check .`, `python -m ruff check .`, `python -m mypy`.

```bash
git add src/ddd/loading.py src/ddd/lsp/navigation.py src/ddd/variables.py src/ddd/gui/api.py tests/test_unit_index.py tests/test_variables.py
git commit -m "record in the navigation index every place a unit is stated and every vocabulary entry listing it, a unit listed twice at both, and count the units in use from that record"
git push
```

---

### Task 2: The plans

**Files:**
- Modify: `src/ddd/loading.py` (new `expand_include`; `_Loader._expand` calls it; the `collections.abc` import)
- Create: `src/ddd/lsp/units.py`
- Create: `tests/test_unit_plans.py`

**Interfaces:**
- Consumes: Task 1's `Index.units`, `Index.vocabulary`, `UnitSite`; `ddd.lsp.navigation.Site`; `ddd.editing.Operation`, `lay_out`, `DEFAULT_INDENT_UNIT`; `ddd.lsp.ranges.Document`, `read`; `ddd.loading.resolve_path`.
- Produces, for Tasks 3, 4 and 5 (the skeleton's, with `UnitRefusalError` for `UnitRefusal`):

```python
# src/ddd/loading.py
def expand_include(
    source: Path, pattern: str, excluded: Collection[Path] = frozenset()
) -> list[Path]  # raises OSError, ValueError or NotImplementedError for a pattern pathlib refuses

# src/ddd/lsp/units.py
ADOPTED: Final = "units.ddd.json"

@dataclass(frozen=True, slots=True)
class UnitProject:
    project: Path  # the project description, resolved
    units_files: tuple[Path, ...]  # its units files, in the order its `project.includes` lists them
    unread: tuple[Path, ...]  # the project's files that did not load, resolved and sorted

@dataclass(frozen=True, slots=True)
class PlannedEdit:
    path: Path
    operations: tuple[Operation, ...]
    creates: bool = False

@dataclass(frozen=True, slots=True)
class UnitPlan:
    edits: tuple[PlannedEdit, ...]  # one per file, sorted by path

class UnitRefusalError(Exception):
    code: Literal["unreadable", "invalid", "not-found"]
    message: str

def unit_project(project: Path, unread: Sequence[Path], cache: dict[Path, Document]) -> UnitProject
def rename_unit(built: Index, project: UnitProject, old: str, new: str, cache: dict[Path, Document]) -> UnitPlan
def add_unit(built: Index, project: UnitProject, unit: str, cache: dict[Path, Document]) -> UnitPlan
def describe_unit(built: Index, project: UnitProject, unit: str, description: str, cache: dict[Path, Document]) -> UnitPlan
def remove_unit(built: Index, project: UnitProject, unit: str, cache: dict[Path, Document]) -> UnitPlan
def adopt_units(built: Index, project: UnitProject, cache: dict[Path, Document]) -> UnitPlan
```

- [ ] **Step 1: The failing tests**

Create `tests/test_unit_plans.py`:

```python
"""What each change of a unit takes, file by file, and what refuses it.

The plans are the one rule behind the language server's Rename Symbol on a unit and its two
quick fixes, and behind the Units tab of ``ddd gui``, so each case here is a sentence about what
either of them may write. A plan is checked by what it does rather than by how it spells it: its
operations are made by the edit engine on the files as they stand, and the json they leave is
what is asserted.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pytest

from conftest import (
    checks,
    component,
    declare,
    project,
    run_analysis,
    scalar_type,
    struct_type,
    types,
    value_member,
    write_tree,
)
from ddd.diagnostics import DiagnosticBag
from ddd.editing import edit_text
from ddd.loading import load_workspace
from ddd.lsp.navigation import Index, index
from ddd.lsp.ranges import Document
from ddd.lsp.units import (
    ADOPTED,
    UnitPlan,
    UnitProject,
    UnitRefusalError,
    add_unit,
    adopt_units,
    describe_unit,
    remove_unit,
    rename_unit,
    unit_project,
)


def opened(
    tmp_path: Path, files: dict[str, Any], unread: Sequence[str] = ()
) -> tuple[Index, UnitProject]:
    """A project including the files given, in that order: its index as the language server
    builds it, and the project its plans are made in, with the files named in ``unread`` taken
    for files that did not load."""
    write_tree(tmp_path, {"p.ddd.json": project("P", *files), **files})
    workspace = load_workspace(tmp_path / "p.ddd.json", DiagnosticBag())
    assert workspace is not None
    described = unit_project(tmp_path / "p.ddd.json", [tmp_path / name for name in unread], {})
    return index(workspace), described


def drifted(vocabulary: list[Any] | None = None) -> dict[str, Any]:
    """A project whose speed drifted into two spellings - ``RPM`` on a declaration, a scalar type
    and a structure member, ``rpm`` on another variable - with ``%`` stated by a structure member
    alone, and, given one, a vocabulary."""
    files: dict[str, Any] = {
        "a.ddd.json": component(
            "A",
            declare("output", "Speed", "uint16", unit="RPM", limits={"min": 0, "max": 8000}),
            declare("output", "Torque", unit="Nm"),
        ),
        "b.ddd.json": component(
            "B",
            declare("input", "Speed", "uint16", unit="RPM"),
            declare("output", "Idle", unit="rpm"),
        ),
        "types.ddd.json": types(
            scalar_type("Speed_t", unit="RPM"),
            struct_type(
                "Sample_t", value_member("rate", unit="RPM"), value_member("level", unit="%")
            ),
        ),
    }
    return files if vocabulary is None else {"units.ddd.json": {"units": vocabulary}, **files}


def written(plan: UnitPlan) -> dict[Path, str]:
    """Every file the plan writes, as the text it leaves: a created file as the text it carries,
    any other as the edit engine leaves it after making its operations in order."""
    found: dict[Path, str] = {}
    for edit in plan.edits:
        if edit.creates:
            (made,) = edit.operations
            assert (made.op, made.pointer) == ("set", "")
            assert made.raw is not None
            found[edit.path] = made.raw
        else:
            found[edit.path] = edit_text(edit.path.read_text(encoding="utf-8"), edit.operations)
    return found


def after(plan: UnitPlan) -> dict[str, Any]:
    """Every file the plan writes, by name, as the json it leaves."""
    return {path.name: json.loads(text) for path, text in written(plan).items()}


def refusal(plan: Callable[[], UnitPlan]) -> tuple[str, str]:
    """The code and the message a plan is refused with."""
    with pytest.raises(UnitRefusalError) as refused:
        plan()
    return refused.value.code, refused.value.message


class TestTheProject:
    def test_its_units_files_are_those_it_includes_in_the_order_it_lists_them(
        self, tmp_path: Path
    ) -> None:
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "late.ddd.json", "a.ddd.json", "early.ddd.json"),
                "late.ddd.json": {"units": ["rpm"]},
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "early.ddd.json": {"units": ["Nm"]},
            },
        )
        found = unit_project(tmp_path / "p.ddd.json", (), {})
        assert found.project == (tmp_path / "p.ddd.json").resolve()
        assert found.units_files == (
            (tmp_path / "late.ddd.json").resolve(),
            (tmp_path / "early.ddd.json").resolve(),
        )

    def test_a_pattern_is_expanded_as_the_loader_expands_it_and_a_file_counts_once(
        self, tmp_path: Path
    ) -> None:
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "units/b.ddd.json", "units/*.ddd.json"),
                "units/b.ddd.json": {"units": ["rpm"]},
                "units/a.ddd.json": {"units": ["Nm"]},
                "units/c.ddd.json": component("C", declare("output", "Speed", unit="rpm")),
                "units/broken.ddd.json": '{"units": [',
            },
        )
        assert unit_project(tmp_path / "p.ddd.json", (), {}).units_files == (
            (tmp_path / "units" / "b.ddd.json").resolve(),
            (tmp_path / "units" / "a.ddd.json").resolve(),
        )

    def test_an_entry_the_loader_cannot_expand_names_no_units_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def refuse(self: Path, pattern: str) -> object:
            raise NotImplementedError("Non-relative patterns are unsupported")

        write_tree(
            tmp_path,
            {
                "p.ddd.json": {
                    "project": {"name": "P", "includes": [7, "*.ddd.json", "u.ddd.json"]}
                },
                "u.ddd.json": {"units": ["rpm"]},
            },
        )
        monkeypatch.setattr(Path, "glob", refuse)
        assert unit_project(tmp_path / "p.ddd.json", (), {}).units_files == (
            (tmp_path / "u.ddd.json").resolve(),
        )

    def test_a_description_including_nothing_has_no_units_file(self, tmp_path: Path) -> None:
        write_tree(tmp_path, {"p.ddd.json": {"project": {"name": "P"}}})
        assert unit_project(tmp_path / "p.ddd.json", (), {}).units_files == ()

    def test_the_files_that_did_not_load_are_sorted_and_named_once(self, tmp_path: Path) -> None:
        write_tree(tmp_path, {"p.ddd.json": project("P")})
        b, a = tmp_path / "b.ddd.json", tmp_path / "a.ddd.json"
        assert unit_project(tmp_path / "p.ddd.json", [b, a, b], {}).unread == (
            a.resolve(),
            b.resolve(),
        )


class TestRename:
    def test_every_place_the_unit_is_stated_takes_the_new_spelling_and_nothing_else_changes(
        self, tmp_path: Path
    ) -> None:
        files = drifted()
        idx, where = opened(tmp_path, files)
        plan = rename_unit(idx, where, "RPM", "1/min", {})
        files["a.ddd.json"]["component"]["interface"][0]["definition"]["unit"] = "1/min"
        files["b.ddd.json"]["component"]["interface"][0]["definition"]["unit"] = "1/min"
        files["types.ddd.json"]["types"][0]["unit"] = "1/min"
        files["types.ddd.json"]["types"][1]["members"][0]["unit"] = "1/min"
        assert [edit.path.name for edit in plan.edits] == [
            "a.ddd.json",
            "b.ddd.json",
            "types.ddd.json",
        ]
        assert after(plan) == {
            name: files[name] for name in ("a.ddd.json", "b.ddd.json", "types.ddd.json")
        }

    def test_a_spelling_only_the_vocabulary_lists_is_renamed_there(self, tmp_path: Path) -> None:
        idx, where = opened(tmp_path, drifted(["rpm", "kPa"]))
        assert after(rename_unit(idx, where, "kPa", "hPa", {})) == {
            "units.ddd.json": {"units": ["rpm", "hPa"]}
        }

    def test_an_entry_is_renamed_in_the_form_it_takes_and_keeps_its_description(
        self, tmp_path: Path
    ) -> None:
        idx, where = opened(tmp_path, drifted(["rpm", {"unit": "Nm", "description": "torque"}]))
        plain = after(rename_unit(idx, where, "rpm", "1/min", {}))
        described = after(rename_unit(idx, where, "Nm", "N.m", {}))
        assert plain["units.ddd.json"] == {
            "units": ["1/min", {"unit": "Nm", "description": "torque"}]
        }
        assert described["units.ddd.json"] == {
            "units": ["rpm", {"unit": "N.m", "description": "torque"}]
        }

    def test_renaming_onto_a_listed_spelling_merges_and_takes_the_old_entry_out(
        self, tmp_path: Path
    ) -> None:
        vocabulary = [
            {"unit": "rpm", "description": "revolutions per minute"},
            {"unit": "RPM", "description": "the same, shouted"},
            "Nm",
        ]
        idx, where = opened(tmp_path, drifted(vocabulary))
        found = after(rename_unit(idx, where, "RPM", "rpm", {}))
        assert found["units.ddd.json"] == {
            "units": [{"unit": "rpm", "description": "revolutions per minute"}, "Nm"]
        }
        assert found["types.ddd.json"]["types"][1]["members"][0]["unit"] == "rpm"

    def test_a_unit_listed_twice_has_both_entries_renamed(self, tmp_path: Path) -> None:
        idx, where = opened(tmp_path, drifted(["RPM", "Nm", {"unit": "RPM", "description": ""}]))
        assert after(rename_unit(idx, where, "RPM", "1/min", {}))["units.ddd.json"] == {
            "units": ["1/min", "Nm", {"unit": "1/min", "description": ""}]
        }

    def test_a_spelling_outside_ascii_is_written_as_it_is_spelled(self, tmp_path: Path) -> None:
        idx, where = opened(
            tmp_path, {"t.ddd.json": component("T", declare("output", "T", unit="C"))}
        )
        (text,) = written(rename_unit(idx, where, "C", "°C", {})).values()
        assert '"unit": "°C"' in text

    def test_a_merge_takes_every_entry_of_a_unit_listed_twice_out_in_every_file(
        self, tmp_path: Path
    ) -> None:
        files = {"more.ddd.json": {"units": ["RPM", "kPa"]}, **drifted(["RPM", "rpm", "Nm", "RPM"])}
        idx, where = opened(tmp_path, files)
        found = after(rename_unit(idx, where, "RPM", "rpm", {}))
        assert found["units.ddd.json"] == {"units": ["rpm", "Nm"]}
        assert found["more.ddd.json"] == {"units": ["kPa"]}

    def test_a_merge_that_would_leave_a_units_file_listing_nothing_is_invalid(
        self, tmp_path: Path
    ) -> None:
        idx, where = opened(tmp_path, {"shouted.ddd.json": {"units": ["RPM"]}, **drifted(["rpm"])})
        code, message = refusal(lambda: rename_unit(idx, where, "RPM", "rpm", {}))
        assert code == "invalid"
        assert "shouted.ddd.json" in message

    @pytest.mark.parametrize("new", ["", " rpm", "rpm\t", "RPM"])
    def test_a_new_name_that_is_empty_has_spaces_around_it_or_is_the_old_one_is_invalid(
        self, tmp_path: Path, new: str
    ) -> None:
        idx, where = opened(tmp_path, drifted())
        assert refusal(lambda: rename_unit(idx, where, "RPM", new, {}))[0] == "invalid"

    def test_a_unit_the_project_neither_states_nor_lists_is_not_found(self, tmp_path: Path) -> None:
        idx, where = opened(tmp_path, drifted(["rpm"]))
        assert refusal(lambda: rename_unit(idx, where, "Hz", "1/s", {}))[0] == "not-found"

    def test_while_any_file_of_the_project_does_not_load_a_rename_is_unreadable(
        self, tmp_path: Path
    ) -> None:
        files = {**drifted(), "broken.ddd.json": '{"component": '}
        idx, where = opened(tmp_path, files, unread=["broken.ddd.json"])
        code, message = refusal(lambda: rename_unit(idx, where, "RPM", "rpm", {}))
        assert code == "unreadable"
        assert "broken.ddd.json" in message


class TestAdd:
    def test_a_unit_is_appended_as_a_spelling_where_every_entry_is_one(
        self, tmp_path: Path
    ) -> None:
        idx, where = opened(tmp_path, drifted(["rpm", "Nm"]))
        assert after(add_unit(idx, where, "RPM", {})) == {
            "units.ddd.json": {"units": ["rpm", "Nm", "RPM"]}
        }

    def test_a_unit_is_appended_as_an_object_where_an_entry_is_one(self, tmp_path: Path) -> None:
        idx, where = opened(tmp_path, drifted(["rpm", {"unit": "Nm", "description": "torque"}]))
        assert after(add_unit(idx, where, "RPM", {})) == {
            "units.ddd.json": {
                "units": [
                    "rpm",
                    {"unit": "Nm", "description": "torque"},
                    {"unit": "RPM", "description": ""},
                ]
            }
        }

    def test_a_unit_goes_into_the_first_units_file_the_includes_list(self, tmp_path: Path) -> None:
        files = {"first.ddd.json": {"units": ["kPa"]}, **drifted(["rpm"])}
        idx, where = opened(tmp_path, files)
        assert after(add_unit(idx, where, "Hz", {})) == {"first.ddd.json": {"units": ["kPa", "Hz"]}}

    @pytest.mark.parametrize("unit", ["", "RPM "])
    def test_a_spelling_no_unit_is_written_with_is_invalid(self, tmp_path: Path, unit: str) -> None:
        idx, where = opened(tmp_path, drifted(["rpm"]))
        assert refusal(lambda: add_unit(idx, where, unit, {}))[0] == "invalid"

    def test_a_project_without_a_units_file_has_nowhere_to_add_one(self, tmp_path: Path) -> None:
        idx, where = opened(tmp_path, drifted())
        assert refusal(lambda: add_unit(idx, where, "RPM", {})) == (
            "invalid",
            "p.ddd.json includes no units file to add 'RPM' to",
        )

    def test_a_unit_the_vocabulary_lists_already_is_invalid(self, tmp_path: Path) -> None:
        files = {"first.ddd.json": {"units": ["kPa"]}, **drifted(["rpm"])}
        idx, where = opened(tmp_path, files)
        code, message = refusal(lambda: add_unit(idx, where, "rpm", {}))
        assert code == "invalid"
        assert "units.ddd.json" in message

    def test_while_the_units_file_does_not_load_an_addition_is_unreadable(
        self, tmp_path: Path
    ) -> None:
        idx, where = opened(tmp_path, drifted(["rpm"]), unread=["units.ddd.json"])
        code, message = refusal(lambda: add_unit(idx, where, "RPM", {}))
        assert code == "unreadable"
        assert "units.ddd.json" in message


class TestDescribe:
    def test_an_entry_that_is_a_spelling_alone_becomes_an_object_holding_the_description(
        self, tmp_path: Path
    ) -> None:
        idx, where = opened(tmp_path, drifted(["rpm", {"unit": "Nm", "description": "torque"}]))
        assert after(describe_unit(idx, where, "rpm", "revolutions per minute", {})) == {
            "units.ddd.json": {
                "units": [
                    {"unit": "rpm", "description": "revolutions per minute"},
                    {"unit": "Nm", "description": "torque"},
                ]
            }
        }

    def test_an_object_has_its_description_set_or_added(self, tmp_path: Path) -> None:
        vocabulary = [{"unit": "rpm"}, {"unit": "Nm", "description": "torque"}]
        idx, where = opened(tmp_path, drifted(vocabulary))
        added = after(describe_unit(idx, where, "rpm", "speed", {}))
        replaced = after(describe_unit(idx, where, "Nm", "torque, newton metre", {}))
        assert added["units.ddd.json"]["units"][0] == {"unit": "rpm", "description": "speed"}
        assert replaced["units.ddd.json"]["units"][1] == {
            "unit": "Nm",
            "description": "torque, newton metre",
        }

    def test_a_unit_listed_twice_has_both_entries_described(self, tmp_path: Path) -> None:
        idx, where = opened(tmp_path, drifted(["rpm", {"unit": "rpm", "description": "old"}]))
        assert after(describe_unit(idx, where, "rpm", "speed", {})) == {
            "units.ddd.json": {
                "units": [
                    {"unit": "rpm", "description": "speed"},
                    {"unit": "rpm", "description": "speed"},
                ]
            }
        }

    def test_a_unit_the_project_neither_states_nor_lists_is_not_found(self, tmp_path: Path) -> None:
        idx, where = opened(tmp_path, drifted(["rpm"]))
        assert refusal(lambda: describe_unit(idx, where, "Hz", "frequency", {}))[0] == "not-found"

    def test_a_unit_stated_outside_the_vocabulary_has_no_description_to_set(
        self, tmp_path: Path
    ) -> None:
        idx, where = opened(tmp_path, drifted(["rpm"]))
        assert refusal(lambda: describe_unit(idx, where, "RPM", "shouted", {}))[0] == "invalid"

    def test_while_the_units_file_listing_it_does_not_load_a_description_is_unreadable(
        self, tmp_path: Path
    ) -> None:
        idx, where = opened(tmp_path, drifted(["rpm"]), unread=["units.ddd.json"])
        code, message = refusal(lambda: describe_unit(idx, where, "rpm", "speed", {}))
        assert code == "unreadable"
        assert "units.ddd.json" in message

    def test_a_unit_no_loaded_entry_lists_is_unreadable_while_a_units_file_does_not_load(
        self, tmp_path: Path
    ) -> None:
        """The file that did not load may be the one listing it: saying it is not in the
        vocabulary would be a guess."""
        idx, where = opened(tmp_path, drifted(["rpm"]), unread=["units.ddd.json"])
        assert refusal(lambda: describe_unit(idx, where, "RPM", "shouted", {}))[0] == "unreadable"


class TestRemove:
    def test_a_unit_nothing_states_is_taken_out_in_either_form(self, tmp_path: Path) -> None:
        vocabulary = ["rpm", "kPa", {"unit": "degC", "description": "temperature"}, "Nm"]
        idx, where = opened(tmp_path, drifted(vocabulary))
        assert after(remove_unit(idx, where, "kPa", {})) == {
            "units.ddd.json": {
                "units": ["rpm", {"unit": "degC", "description": "temperature"}, "Nm"]
            }
        }
        assert after(remove_unit(idx, where, "degC", {})) == {
            "units.ddd.json": {"units": ["rpm", "kPa", "Nm"]}
        }

    def test_a_unit_listed_twice_has_every_entry_taken_out(self, tmp_path: Path) -> None:
        idx, where = opened(tmp_path, drifted(["kPa", "rpm", {"unit": "kPa", "description": ""}]))
        assert after(remove_unit(idx, where, "kPa", {})) == {"units.ddd.json": {"units": ["rpm"]}}

    def test_a_unit_something_still_states_is_invalid(self, tmp_path: Path) -> None:
        idx, where = opened(tmp_path, drifted(["rpm", "Nm"]))
        assert refusal(lambda: remove_unit(idx, where, "rpm", {})) == (
            "invalid",
            "'rpm' is still stated in 1 place; only a unit nothing states is taken out of the "
            "vocabulary",
        )
        assert refusal(lambda: remove_unit(idx, where, "RPM", {}))[1].startswith(
            "'RPM' is still stated in 4 places"
        )

    def test_a_unit_no_entry_lists_is_not_found(self, tmp_path: Path) -> None:
        idx, where = opened(tmp_path, drifted(["rpm"]))
        assert refusal(lambda: remove_unit(idx, where, "Hz", {}))[0] == "not-found"

    def test_the_last_unit_a_units_file_lists_is_not_taken_out(self, tmp_path: Path) -> None:
        idx, where = opened(tmp_path, {"more.ddd.json": {"units": ["kPa"]}, **drifted(["rpm"])})
        assert refusal(lambda: remove_unit(idx, where, "kPa", {})) == (
            "invalid",
            "'kPa' is all more.ddd.json lists, and a units file lists at least one unit",
        )

    def test_while_the_units_file_listing_it_does_not_load_a_removal_is_unreadable(
        self, tmp_path: Path
    ) -> None:
        idx, where = opened(tmp_path, drifted(["rpm", "kPa"]), unread=["units.ddd.json"])
        code, message = refusal(lambda: remove_unit(idx, where, "kPa", {}))
        assert code == "unreadable"
        assert "units.ddd.json" in message


class TestAdopt:
    def test_every_unit_in_use_is_listed_alphabetically_and_the_file_included(
        self, tmp_path: Path
    ) -> None:
        idx, where = opened(tmp_path, drifted())
        plan = adopt_units(idx, where, {})
        listing = {
            "units": [
                {"unit": "%", "description": ""},
                {"unit": "Nm", "description": ""},
                {"unit": "RPM", "description": ""},
                {"unit": "rpm", "description": ""},
            ]
        }
        assert [(edit.path, edit.creates) for edit in plan.edits] == [
            ((tmp_path / "p.ddd.json").resolve(), False),
            ((tmp_path / ADOPTED).resolve(), True),
        ]
        assert plan.edits[1].operations[0].raw == (
            "{\n"
            '  "units": [\n'
            '    { "unit": "%", "description": "" },\n'
            '    { "unit": "Nm", "description": "" },\n'
            '    { "unit": "RPM", "description": "" },\n'
            '    { "unit": "rpm", "description": "" }\n'
            "  ]\n"
            "}\n"
        )
        assert after(plan) == {
            "p.ddd.json": project(
                "P", "a.ddd.json", "b.ddd.json", "types.ddd.json", "units.ddd.json"
            ),
            "units.ddd.json": listing,
        }

    def test_after_adopting_nothing_is_reported_that_was_not_reported_before(
        self, tmp_path: Path
    ) -> None:
        idx, where = opened(tmp_path, drifted())
        _, before = run_analysis(tmp_path, {}, root="p.ddd.json")
        for path, text in written(adopt_units(idx, where, {})).items():
            path.write_text(text, encoding="utf-8")
        _, adopted = run_analysis(tmp_path, {}, root="p.ddd.json")
        assert checks(adopted) == checks(before)

    def test_a_project_with_a_units_file_has_a_vocabulary_already(self, tmp_path: Path) -> None:
        idx, where = opened(tmp_path, drifted(["rpm"]))
        assert refusal(lambda: adopt_units(idx, where, {})) == (
            "invalid",
            "this project has a vocabulary already: units.ddd.json",
        )

    def test_a_units_file_a_sub_project_includes_is_a_vocabulary_already(
        self, tmp_path: Path
    ) -> None:
        files = {"sub.ddd.json": project("Sub", "rates.ddd.json"), **drifted()}
        write_tree(tmp_path, {"rates.ddd.json": {"units": ["Hz"]}})
        idx, where = opened(tmp_path, files)
        assert refusal(lambda: adopt_units(idx, where, {}))[1].endswith("rates.ddd.json")

    def test_a_project_stating_no_unit_has_nothing_to_adopt(self, tmp_path: Path) -> None:
        idx, where = opened(tmp_path, {"a.ddd.json": component("A", declare("output", "Flag"))})
        assert refusal(lambda: adopt_units(idx, where, {}))[0] == "invalid"

    @pytest.mark.parametrize("existing", [{"notes": "not a units file"}, {"units": ["rpm"]}])
    def test_a_file_where_the_vocabulary_would_go_is_never_written_over(
        self, tmp_path: Path, existing: dict[str, Any]
    ) -> None:
        files = drifted()
        write_tree(tmp_path, {ADOPTED: existing})
        idx, where = opened(tmp_path, files)
        code, message = refusal(lambda: adopt_units(idx, where, {}))
        assert code == "invalid"
        assert ADOPTED in message

    def test_while_any_file_of_the_project_does_not_load_adopting_is_unreadable(
        self, tmp_path: Path
    ) -> None:
        files = {**drifted(), "broken.ddd.json": '{"component": '}
        idx, where = opened(tmp_path, files, unread=["broken.ddd.json"])
        code, message = refusal(lambda: adopt_units(idx, where, {}))
        assert code == "unreadable"
        assert "broken.ddd.json" in message


@pytest.mark.parametrize(
    "plan",
    [
        lambda idx, where: add_unit(idx, where, "Hz", {}),
        lambda idx, where: describe_unit(idx, where, "rpm", "speed", {}),
        lambda idx, where: remove_unit(idx, where, "kPa", {}),
    ],
)
def test_a_component_that_does_not_load_stops_no_change_to_the_vocabulary(
    tmp_path: Path, plan: Callable[[Index, UnitProject], UnitPlan]
) -> None:
    """Only the units file matters to these: a component that did not load may state units, and
    no entry of the vocabulary changes with what it states."""
    files = {**drifted(["rpm", "kPa"]), "broken.ddd.json": '{"component": '}
    idx, where = opened(tmp_path, files, unread=["broken.ddd.json"])
    assert list(after(plan(idx, where))) == ["units.ddd.json"]


@pytest.mark.parametrize(
    "plan",
    [
        lambda idx, where, cache: rename_unit(idx, where, "RPM", "rpm", cache),
        lambda idx, where, cache: add_unit(idx, where, "Hz", cache),
        lambda idx, where, cache: describe_unit(idx, where, "rpm", "speed", cache),
        lambda idx, where, cache: remove_unit(idx, where, "kPa", cache),
        lambda idx, where, cache: adopt_units(idx, where, cache),
    ],
)
def test_a_refused_plan_has_read_no_file(
    tmp_path: Path, plan: Callable[[Index, UnitProject, dict[Path, Document]], UnitPlan]
) -> None:
    """Every refusal is made from the index and the project alone, before a file is read."""
    idx, where = opened(tmp_path, drifted(["rpm", "kPa"]), unread=["units.ddd.json"])
    cache: dict[Path, Document] = {}
    with pytest.raises(UnitRefusalError):
        plan(idx, where, cache)
    assert cache == {}
```

Run: `python -m pytest tests/test_unit_plans.py --no-cov`
Expected: FAIL at collection, `ModuleNotFoundError: No module named 'ddd.lsp.units'`.

- [ ] **Step 2: Expand an include by the loader's rule, in public**

In `src/ddd/loading.py`, the import becomes `from collections.abc import Callable, Collection`. `_Loader._expand` keeps its reporting and hands the expansion to a module function:

```python
    def _expand(
        self, source: Path, pattern: str, origin: Location, excluded: set[Path]
    ) -> list[Path]:
        """Resolve one include entry into a list of existing files, by :func:`expand_include`,
        reporting an entry that reaches none as ``include-empty``."""
        try:
            matches = expand_include(source, pattern, excluded)
        except (OSError, ValueError, NotImplementedError) as error:
            self._bag.add("include-empty", f"cannot expand pattern '{pattern}': {error}", origin)
            return []
        if not matches:
            self._bag.add("include-empty", f"pattern '{pattern}' matches no file", origin)
        return matches
```

and right before `_pattern_anchor`, the body it had, whole, with its docstring and comments:

```python
def expand_include(
    source: Path, pattern: str, excluded: Collection[Path] = frozenset()
) -> list[Path]:
    """The files one ``includes`` entry of the project description ``source`` names, resolved.

    An entry that names a file is that file, tried before it is read as a pattern. The two
    readings only ever collide over the three characters a pattern is made of, and a directory
    carrying one of them is not a thing a project chooses: the cmake module writes every
    include of a collected project as a literal absolute path, so a checkout under
    ``C:/work/proj [v2]`` - a copy Windows or a user names that way - turned every one of them
    into a character class that matched nothing, and the whole build failed on a project whose
    files were all there. Where a file of that name exists, it is what the entry meant; where
    none does, the entry is expanded as it always was, so ``a[12].ddd.json`` still reaches
    ``a1`` and ``a2``. A project that wants the class where a file of its own spelling exists
    renames one of the two.

    Public so that what else has to know which files a project includes - the unit plans
    finding the units file a new unit goes into - reads an entry by the loader's own rule, and
    cannot come to another answer than the run that checks the project. A pattern pathlib
    refuses to expand raises what pathlib raised: ``OSError``, ``ValueError`` or
    ``NotImplementedError``.
    """
    raw = Path(pattern)
    candidate = raw if raw.is_absolute() else source.parent / raw
    # `is_file()` rather than `exists()` for the second half: a directory of that name is no
    # more includable than a missing one, and reading it as a pattern is the better of the two
    # answers, a pattern being what it looks like. It answers False rather than raising for a
    # name the platform refuses outright, as every other reading here does.
    if not any(character in pattern for character in _GLOB_CHARACTERS) or candidate.is_file():
        return [resolve_path(candidate)]

    # The anchor decides where a pattern starts, not is_absolute(): on Windows both the rooted
    # '/shared/*.ddd.json' and the drive relative 'C:*.ddd.json' carry an anchor while
    # reporting is_absolute() as false, and handing either to Path.glob unchanged makes
    # pathlib refuse a non-relative pattern.
    anchor = raw.anchor
    base = _pattern_anchor(source.parent, raw)
    relative = raw.relative_to(anchor) if anchor else raw
    found = list(base.glob(relative.as_posix()))
    # Sorted by the POSIX spelling rather than by the Path, which compares as the platform
    # compares a path: case insensitively on Windows and by code point on Linux, so one project
    # loaded 'alpha' before 'Zeta' here and the other way round there, and the definition file
    # and the a2l of that project differed between two builds of the same sources. Names are
    # already ordered by code point, and so are these.
    return sorted(
        (
            resolved
            for match in found
            if match.is_file() and (resolved := resolve_path(match)) not in excluded
        ),
        key=Path.as_posix,
    )
```

Run: `python -m pytest tests/test_loading.py tests/test_hardening.py --no-cov`
Expected: PASS, every finding about an include as it was.

- [ ] **Step 3: Write `src/ddd/lsp/units.py`**

```python
"""Changing a unit everywhere a project states it, and the vocabulary that lists it.

A unit is free text wherever it is written, so one quantity drifts into two spellings - ``rpm``
in one component, ``RPM`` in the next - and a vocabulary is what holds a project to one. This
module plans each change to that: renaming a unit everywhere, which merges two spellings when the
new one is listed already; adding a unit to the vocabulary, describing it and taking it out; and
adopting a vocabulary where there is none. A plan is the operations of :mod:`ddd.editing` each
file takes, on json pointers, made once for both clients: the language server renders it as the
text edits of Rename Symbol and of its quick fixes, and ``ddd gui`` previews it and posts it to
its edit endpoint. Where a unit is stated is the navigation index's to say; nothing here decides
it again.

A plan refuses before it reads a file it would not write. A file that did not load may state the
unit, and a rename that cannot see it leaves the old spelling there, in a project the rename
said it had rewritten.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

from ddd.editing import DEFAULT_INDENT_UNIT, Operation, lay_out
from ddd.loading import expand_include, resolve_path
from ddd.lsp.navigation import Index, Site
from ddd.lsp.ranges import Document, read

ADOPTED: Final = "units.ddd.json"
"""The units file adopting a vocabulary writes, beside the project description."""


@dataclass(frozen=True, slots=True)
class UnitProject:
    """What a plan has to know of the project besides its index: where its vocabulary is kept,
    and which of its files did not load."""

    project: Path
    """The project description, resolved."""

    units_files: tuple[Path, ...]
    """Its units files, in the order its ``project.includes`` lists them: the first is where a
    unit added to the vocabulary goes."""

    unread: tuple[Path, ...]
    """The project's files that did not load, resolved and sorted."""


@dataclass(frozen=True, slots=True)
class PlannedEdit:
    """The operations one file takes, in the order they are made."""

    path: Path
    operations: tuple[Operation, ...]
    creates: bool = False
    """The plan creates this file: ``operations`` is one ``set`` at the root, carrying it whole."""


@dataclass(frozen=True, slots=True)
class UnitPlan:
    """Everything one change of a unit takes: one edit per file, sorted by path."""

    edits: tuple[PlannedEdit, ...]


class UnitRefusalError(Exception):
    """A change of a unit that cannot be planned, and the code both clients refuse it with."""

    code: Literal["unreadable", "invalid", "not-found"]
    """``unreadable``: a file the change has to see did not load. ``invalid``: the change cannot
    be made - a spelling no unit has, a unit something still states, a vocabulary the project
    has already. ``not-found``: the project neither states the unit nor lists it."""

    message: str
    """The sentence the refusal is shown with, naming the file it concerns."""

    def __init__(self, code: Literal["unreadable", "invalid", "not-found"], message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def unit_project(project: Path, unread: Sequence[Path], cache: dict[Path, Document]) -> UnitProject:
    """The project a unit's plans are made in: its description, its units files and the files of
    it that did not load.

    The units files are read out of the description's own ``includes``, each entry expanded by
    the loader's rule, so that the first of them is the first a run of ``ddd check`` reads. A
    units file is a document with ``units`` at its top, which is how the loader tells one; a file
    that does not parse is none, since what it is cannot be told.
    """
    path = resolve_path(project)
    listed = read(path, cache).value_at("project.includes")
    found: list[Path] = []
    for entry in listed if isinstance(listed, list) else ():
        for file in _included(path, entry):
            document = read(file, cache).data
            if file not in found and isinstance(document, dict) and "units" in document:
                found.append(file)
    return UnitProject(path, tuple(found), tuple(sorted({resolve_path(file) for file in unread})))


def rename_unit(
    built: Index, project: UnitProject, old: str, new: str, cache: dict[Path, Document]
) -> UnitPlan:
    """Every place ``old`` is stated spelled ``new``, and the vocabulary brought along.

    Only the spelling changes: a value, its limits and its conversion stay as they are, because
    ``ms`` to ``s`` is a conversion and not a spelling. In the vocabulary, each entry listing
    ``old`` is renamed, keeping its description, where no entry lists ``new``; where one does,
    the rename is a merge, and the entries listing ``old`` are taken out, leaving the entry of
    ``new`` with its own description. A unit listed twice has every entry treated so.
    """
    _spelling(new)
    if new == old:
        raise UnitRefusalError("invalid", f"'{old}' is spelled that way already")
    if project.unread:
        raise UnitRefusalError(
            "unreadable",
            f"{_names(project.unread)} did not load, so renaming '{old}' could not reach every "
            "place it is stated",
        )
    _known(built, old)
    raw = _raw(new)
    operations: dict[Path, list[Operation]] = {}
    for stated in built.units.get(old, ()):
        operations.setdefault(stated.site.path, []).append(
            Operation("set", stated.site.pointer, raw)
        )
    entries = built.vocabulary.get(old, [])
    if new in built.vocabulary:
        for file, removals in _taken_out(entries, old, cache).items():
            operations.setdefault(file, []).extend(removals)
    else:
        for entry in entries:
            spelled = entry.pointer
            if isinstance(read(entry.path, cache).value_at(entry.pointer), dict):
                spelled = f"{entry.pointer}.unit"
            operations.setdefault(entry.path, []).append(Operation("set", spelled, raw))
    return _plan(operations)


def add_unit(
    built: Index, project: UnitProject, unit: str, cache: dict[Path, Document]
) -> UnitPlan:
    """``unit`` appended to the first units file the project description includes, in the form
    that file's entries take: the spelling alone where every entry is one, and an object with an
    empty description where any entry is written as an object."""
    _spelling(unit)
    if not project.units_files:
        raise UnitRefusalError(
            "invalid", f"{project.project.name} includes no units file to add '{unit}' to"
        )
    file = project.units_files[0]
    if file in project.unread:
        raise UnitRefusalError(
            "unreadable", f"{file.name} did not load, so '{unit}' cannot be added to it"
        )
    if unit in built.vocabulary:
        raise UnitRefusalError(
            "invalid",
            f"'{unit}' is in the vocabulary already, in {_names(_paths(built.vocabulary[unit]))}",
        )
    listed = read(file, cache).value_at("units") or []
    plain = all(isinstance(entry, str) for entry in listed)
    written = _raw(unit if plain else {"unit": unit, "description": ""})
    return _plan({file: [Operation("insert", f"units[{len(listed)}]", written)]})


def describe_unit(
    built: Index, project: UnitProject, unit: str, description: str, cache: dict[Path, Document]
) -> UnitPlan:
    """The vocabulary's description of ``unit`` set to ``description``: an object entry's
    ``description``, added where it has none, and an entry that is the spelling alone turned into
    an object that holds one. A unit listed twice has every entry described."""
    _vocabulary_loaded(built, project, unit, "its description cannot be set there")
    _known(built, unit)
    entries = built.vocabulary.get(unit)
    if entries is None:
        raise UnitRefusalError(
            "invalid", f"'{unit}' is not in the vocabulary, so it has no description to set"
        )
    operations: dict[Path, list[Operation]] = {}
    for entry in entries:
        if isinstance(read(entry.path, cache).value_at(entry.pointer), dict):
            made = Operation("set", f"{entry.pointer}.description", _raw(description))
        else:
            whole = _raw({"unit": unit, "description": description})
            made = Operation("set", entry.pointer, whole)
        operations.setdefault(entry.path, []).append(made)
    return _plan(operations)


def remove_unit(
    built: Index, project: UnitProject, unit: str, cache: dict[Path, Document]
) -> UnitPlan:
    """Every entry listing ``unit`` taken out of the vocabulary, each with exactly one comma.

    Only a unit nothing states: taking out one that is stated would turn every place stating it
    into an ``unknown-unit`` finding.
    """
    _vocabulary_loaded(built, project, unit, "it cannot be taken out of it")
    stated = built.units.get(unit)
    if stated is not None:
        places = f"{len(stated)} place{'s' if len(stated) != 1 else ''}"
        raise UnitRefusalError(
            "invalid",
            f"'{unit}' is still stated in {places}; only a unit nothing states is taken out of "
            "the vocabulary",
        )
    entries = built.vocabulary.get(unit)
    if entries is None:
        raise UnitRefusalError("not-found", f"no file of this project states or lists '{unit}'")
    return _plan(_taken_out(entries, unit, cache))


def adopt_units(built: Index, project: UnitProject, cache: dict[Path, Document]) -> UnitPlan:
    """A vocabulary for a project without one: :data:`ADOPTED`, written beside the description
    and listing every unit in use alphabetically with an empty description, and its name
    appended to the description's ``includes``, in one edit.

    Every unit in use, drifted spellings included, so that adopting reports nothing that was not
    reported before; two spellings of one unit are merged by renaming one of them afterwards.
    The file is laid out by the edit engine the way a units file is written by hand, one entry
    to a line, so that the first edit anybody makes to it reads as a one-line change.
    """
    entries = [entry for listed in built.vocabulary.values() for entry in listed]
    held = sorted({*project.units_files, *_paths(entries)})
    if held:
        raise UnitRefusalError("invalid", f"this project has a vocabulary already: {_names(held)}")
    if project.unread:
        raise UnitRefusalError(
            "unreadable",
            f"{_names(project.unread)} did not load, so adopting could not list every unit in use",
        )
    if not built.units:
        raise UnitRefusalError(
            "invalid", "this project states no unit, and a units file lists at least one"
        )
    created = project.project.parent / ADOPTED
    if created.exists():
        raise UnitRefusalError(
            "invalid",
            f"adopting writes {ADOPTED} beside {project.project.name}, and a file of that name "
            "is there already",
        )
    document = {"units": [{"unit": unit, "description": ""} for unit in sorted(built.units)]}
    laid_out = lay_out(
        _raw(document), one_line=False, indent="", unit=DEFAULT_INDENT_UNIT, newline="\n"
    )
    whole = f"{laid_out}\n"
    includes = read(project.project, cache).value_at("project.includes") or []
    included = Operation("insert", f"project.includes[{len(includes)}]", _raw(ADOPTED))
    edits = (
        PlannedEdit(created, (Operation("set", "", whole),), creates=True),
        PlannedEdit(project.project, (included,)),
    )
    return UnitPlan(tuple(sorted(edits, key=lambda edit: edit.path)))


def _spelling(unit: str) -> None:
    """Refuse a spelling no unit is written with: the empty unit is no unit, and spaces around
    one are a slip of the keyboard rather than part of its spelling."""
    if not unit:
        raise UnitRefusalError("invalid", "the empty unit is no unit")
    if unit != unit.strip():
        raise UnitRefusalError("invalid", f"'{unit}' has spaces around it")


def _known(built: Index, unit: str) -> None:
    """Refuse a unit the project neither states nor lists: there is nothing of it to change."""
    if unit not in built.units and unit not in built.vocabulary:
        raise UnitRefusalError("not-found", f"no file of this project states or lists '{unit}'")


def _vocabulary_loaded(built: Index, project: UnitProject, unit: str, consequence: str) -> None:
    """Refuse to change the entries listing ``unit`` while a units file holding one did not load
    - or, for a unit no entry that loaded lists, while any units file did not, since that may be
    the one listing it. A component that did not load is no concern of the vocabulary's."""
    entries = built.vocabulary.get(unit)
    files = _paths(entries) if entries is not None else project.units_files
    unread = [file for file in files if file in project.unread]
    if unread:
        raise UnitRefusalError("unreadable", f"{_names(unread)} did not load, so {consequence}")


def _taken_out(
    entries: Sequence[Site], unit: str, cache: dict[Path, Document]
) -> dict[Path, list[Operation]]:
    """The removals taking every entry of ``unit`` out of the vocabulary, file by file.

    The entry furthest down a file goes first: the edit engine makes a file's operations one
    after another, and taking out ``units[1]`` makes ``units[3]`` the new ``units[2]``. Refused
    where the file would be left listing no unit at all, which a units file may not do - emptied,
    it would no longer load.
    """
    for file, taken in Counter(entry.path for entry in entries).items():
        listed = read(file, cache).value_at("units")
        if isinstance(listed, list) and taken >= len(listed):
            raise UnitRefusalError(
                "invalid",
                f"'{unit}' is all {file.name} lists, and a units file lists at least one unit",
            )
    operations: dict[Path, list[Operation]] = {}
    for entry in sorted(entries, key=lambda entry: (entry.path, -_position(entry))):
        operations.setdefault(entry.path, []).append(Operation("remove", entry.pointer))
    return operations


def _included(project: Path, entry: Any) -> list[Path]:
    """The files one ``includes`` entry names, or none for an entry the loader cannot expand -
    one that is not a string, or a pattern pathlib refuses - which it has reported already."""
    if not isinstance(entry, str):
        return []
    try:
        return expand_include(project, entry, {project})
    except (OSError, ValueError, NotImplementedError):
        return []


def _position(entry: Site) -> int:
    """Where a vocabulary entry sits in its file's ``units``, read off its pointer ``units[i]``."""
    return int(entry.pointer.removeprefix("units[").removesuffix("]"))


def _plan(operations: Mapping[Path, Sequence[Operation]]) -> UnitPlan:
    """One edit per file, sorted by path, each file's operations in the order they were planned."""
    return UnitPlan(
        tuple(PlannedEdit(path, tuple(made)) for path, made in sorted(operations.items()))
    )


def _raw(value: Any) -> str:
    """A value as the json text an operation carries, every character as written: a unit such as
    ``°C`` arrives in the file as ``°C``, where json's default would write ``\\u00b0C``."""
    return json.dumps(value, ensure_ascii=False)


def _paths(entries: Iterable[Site]) -> list[Path]:
    return sorted({entry.path for entry in entries})


def _names(files: Iterable[Path]) -> str:
    return ", ".join(file.name for file in files)
```

- [ ] **Step 4: Run the tests**

Run: `python -m pytest tests/test_unit_plans.py tests/test_unit_index.py tests/test_loading.py --no-cov`
Expected: PASS.

- [ ] **Step 5: The Python gate, then commit**

Run: `python -m pytest`, `python -m ruff format --check .`, `python -m ruff check .`, `python -m mypy`. `src/ddd/lsp/units.py` and `expand_include` must be at 100 % line and branch coverage; a branch left uncovered means a case of Step 1 is missing, not that the branch is dead.

```bash
git add src/ddd/loading.py src/ddd/lsp/units.py tests/test_unit_plans.py
git commit -m "plan renaming, merging, adding, describing, removing and adopting a unit as edit operations file by file, refused before a file the plan would not write is read"
git push
```

---

### Task 3: A unit renamed from an editor, and two quick fixes

**Files:**
- Modify: `src/ddd/analysis.py` (`_check_units`'s inner `check`; `_did_you_mean` rewritten on the new `_suggesting`, and `close_units` added before it; `import difflib` is there already)
- Modify: `src/ddd/lsp/navigation.py` (`_UNIT_KEY` and `LOAD_CHECKS` among the module's constants; `Loaded.unloaded`; `_loaded`; `_unreadable`; `renameable_at`)
- Modify: `src/ddd/gui/session.py` (`LOAD_CHECKS` imported from `ddd.lsp.navigation` instead of defined)
- Modify: `src/ddd/lsp/units.py` (its imports; `text_edits`, `unit_drift`, `_simultaneous`, `_engine_edit`, `_protocol_edit` at the end)
- Modify: `src/ddd/lsp/edits.py` (its imports; `UNKNOWN_UNIT`; `actions` split into `actions` and `_on_the_declaration`; `_vocabulary_actions`)
- Modify: `src/ddd/lsp/server.py` (its imports; `_answer_rename`; `_rename_unit`, `_gather`, `_drifted`; `_actions`)
- Test: `tests/test_lsp.py` (imports; `UNIT_PLACES`, `unit_places`, `rewritten_by` after `apply_edits`; class `TestRename`; new class `TestAUnitPlanAsTextEdits`; class `TestServer`; `UNLISTED` and new class `TestFixingAnUnknownUnit` after `TestOfferingAnIdentity`)
- Test: `tests/test_units.py` (class `TestTheCheck`)

**Interfaces:**
- Consumes: Task 1's `UnitSite` (`site`, `kind`, `name`), `Index.units` and `Index.vocabulary`, recorded by `index()`. Task 2's `UnitProject`, `unit_project(project, unread, cache)`, `UnitPlan` (`edits`), `PlannedEdit` (`path`, `operations`, `creates`), `UnitRefusalError` (`code`, `message` - the controller's name for the skeleton's `UnitRefusal`), `rename_unit(built, project, old, new, cache)` and `add_unit(built, project, unit, cache)`. `ddd.editing`'s `Operation`, `TextEdit`, `replacement`, `member_addition`, `removal`, `insertion`, `EditError`, `INVALID`, and `edit_text` in the tests; `ddd.lsp.navigation`'s `Loaded` and `workspaces`; `ddd.pointers.parent_pointer`.
- Produces, as the skeleton gives them:

```python
# src/ddd/lsp/units.py
def text_edits(plan: UnitPlan, cache: dict[Path, Document]) -> dict[str, list[dict[str, Any]]]
# src/ddd/analysis.py
def close_units(unit: str, vocabulary: Sequence[str]) -> tuple[str, ...]
    # compared lowercased at 0.5: every close spelling, at most three, closest first then by
    # spelling, never the unit itself
```

  and beside them, for no other task: `unit_drift(built: Index, unit: str, cache: dict[Path, Document]) -> tuple[Path, ...]` in `ddd.lsp.units`; `LOAD_CHECKS` and `Loaded.unloaded: tuple[Path, ...] = ()` in `ddd.lsp.navigation`; `UNKNOWN_UNIT: Final = frozenset({"unknown-unit"})` in `ddd.lsp.edits`; `actions(built, path, document, pointer, cache, reported=(), project: UnitProject | None = None)`.

- [ ] **Step 1: The failing tests**

In `tests/test_units.py`, import `close_units` before `from ddd.diagnostics import DiagnosticBag`:

```python
from ddd.analysis import close_units
```

and in class `TestTheCheck`, after `test_the_nearest_spelling_is_suggested`, add:

```python
    def test_every_close_spelling_is_suggested_closest_first(self, tree: Path) -> None:
        """As :func:`ddd.analysis.close_units` finds them - closest first, a tie by spelling -
        which is also what the editor offers to rename the unit to."""
        _, bag = run_analysis(tree, self.files("rpms", "Nm", "rpm", "rpm2", "rps"))
        (finding,) = bag
        assert finding.message == (
            "'rpms' is not a unit this project declares - did you mean 'rpm' or 'rps' or 'rpm2'?"
        )

    def test_a_spelling_in_another_case_is_suggested(self, tree: Path) -> None:
        """The likeliest near miss of all, which the spellings as written would score at
        nothing: 'RPM' and 'rpm' share no character."""
        _, bag = run_analysis(tree, self.files("RPM", "rpm", "Nm"))
        (finding,) = bag
        assert finding.message == "'RPM' is not a unit this project declares - did you mean 'rpm'?"

    def test_every_spelling_of_a_close_unit_is_suggested_but_its_own(self) -> None:
        """Case counts in the vocabulary - 'mV' and 'MV' are two units - so both are named, by
        spelling; and a unit is never its own suggestion."""
        assert close_units("mv", ("V", "mV", "MV")) == ("MV", "mV", "V")
        assert close_units("mV", ("V", "mV", "MV")) == ("MV", "V")

    def test_no_more_than_three_spellings_are_suggested(self) -> None:
        assert close_units("rpms", ("Nm", "rpm", "rpm2", "rpms2", "rps")) == ("rpms2", "rpm", "rps")

    def test_a_spelling_half_the_same_is_close_enough(self) -> None:
        """The cutoff is 0.5, and a spelling that close is suggested: difflib scores twice what
        two spellings share over their length together, so 'ms' scores 0.5 against 'us' and 0.4
        against 'rpm'."""
        assert close_units("ms", ("us", "rpm")) == ("us",)
```

In `tests/test_lsp.py`, add `struct_type` and `value_member` to the names imported from `conftest`, keeping them sorted (`..., session, struct_type, types, value_member, write_tree`); add the first import below after `from ddd.diagnostics import ...`, and the second after `from ddd.lsp.server import Server, uri_to_path`:

```python
from ddd.editing import INVALID, EditError, Operation, edit_text
```

```python
from ddd.lsp.units import (
    PlannedEdit,
    UnitPlan,
    UnitRefusalError,
    rename_unit,
    text_edits,
    unit_drift,
    unit_project,
)
```

After `apply_edits`, before `class TestRename`, add the project every kind of place is tested on:

```python
UNIT_PLACES = [
    ("a.ddd.json", "component.interface[0].definition.unit"),
    ("b.ddd.json", "component.interface[0].definition.unit"),
    ("a.ddd.json", "component.types[0].unit"),
    ("a.ddd.json", "component.types[1].members[0].unit"),
    ("types.ddd.json", "types[0].unit"),
    ("types.ddd.json", "types[1].members[0].unit"),
    ("units.ddd.json", "units[0].unit"),
]
"""Every kind of place :func:`unit_places` spells ``rpm``: a declaration on either side, a scalar
type and a structure member in a component's own list and in a types file, and its vocabulary
entry, an object."""


def unit_places(base: Path) -> Path:
    """A project stating ``rpm`` in every kind of place a unit is stated, and listing it in its
    vocabulary as an object - and ``Nm`` as a spelling on its own, stated by one member."""
    write_tree(
        base,
        {
            "p.ddd.json": project(
                "P", "units.ddd.json", "types.ddd.json", "a.ddd.json", "b.ddd.json"
            ),
            "units.ddd.json": {"units": [{"unit": "rpm", "description": "speed"}, "Nm"]},
            "types.ddd.json": types(
                scalar_type("Speed_t", unit="rpm"),
                struct_type(
                    "Pair_t",
                    value_member("speed", unit="rpm"),
                    value_member("torque", unit="Nm"),
                ),
            ),
            "a.ddd.json": component(
                "A",
                declare("output", "Speed", unit="rpm"),
                types=[
                    scalar_type("Idle_t", unit="rpm"),
                    struct_type("Spin_t", value_member("idle", unit="rpm")),
                ],
            ),
            "b.ddd.json": component("B", declare("input", "Speed", unit="rpm")),
        },
    )
    return base / "p.ddd.json"


def rewritten_by(changes: dict[str, list[dict[str, Any]]]) -> dict[str, str]:
    """Every file an edit changes, by name, as a client leaves it."""
    return {
        uri_to_path(uri).name: apply_edits(uri_to_path(uri), edits)
        for uri, edits in changes.items()
    }
```

At the end of class `TestRename`, after `test_a_name_longer_than_the_contract_allows_is_refused`, add:

```python
    @pytest.mark.parametrize(("source", "pointer"), UNIT_PLACES)
    def test_a_unit_is_a_rename_subject_wherever_it_is_spelled(
        self, tmp_path: Path, source: str, pointer: str
    ) -> None:
        unit_places(tmp_path)
        assert navigation.renameable_at(read(tmp_path / source, {}), pointer) == ("unit", "rpm")

    def test_a_vocabulary_entry_that_is_the_spelling_alone_is_a_rename_subject(
        self, tmp_path: Path
    ) -> None:
        unit_places(tmp_path)
        document = read(tmp_path / "units.ddd.json", {})
        assert navigation.renameable_at(document, "units[1]") == ("unit", "Nm")

    @pytest.mark.parametrize("pointer", ["units[0]", "units[0].description"])
    def test_an_entry_written_as_an_object_is_renamed_from_its_unit_alone(
        self, tmp_path: Path, pointer: str
    ) -> None:
        """The editor opens its box over the range this names, and neither the object nor its
        description is a spelling to type over."""
        unit_places(tmp_path)
        assert navigation.renameable_at(read(tmp_path / "units.ddd.json", {}), pointer) is None

    def test_neither_the_empty_unit_nor_a_plugins_own_unit_is_a_rename_subject(
        self, tmp_path: Path
    ) -> None:
        """A dimensionless value states no unit, so there is no spelling to rename; and an
        extensions block may spell any key, ``unit`` among them."""
        write_tree(
            tmp_path,
            {
                "a.ddd.json": component(
                    "A", declare("local", "Ratio", unit="", extensions={"tag": {"unit": "rpm"}})
                )
            },
        )
        document = read(tmp_path / "a.ddd.json", {})
        definition = "component.interface[0].definition"
        assert navigation.renameable_at(document, f"{definition}.unit") is None
        assert navigation.renameable_at(document, f"{definition}.extensions.tag.unit") is None

    def test_a_file_that_loaded_with_an_error_is_unreadable_but_not_unloaded(
        self, tmp_path: Path
    ) -> None:
        """A units file listing a unit twice loads, with a duplicate-unit error: it stays in the
        index, where a plan can reach both entries. A component its schema refuses does not."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "units.ddd.json", "a.ddd.json"),
                "units.ddd.json": {"units": ["rpm", "RPM", "RPM"]},
                "a.ddd.json": component("A", declare("output", "Speed", "uint99", unit="rpm")),
            },
        )
        (loaded,) = navigation.workspaces([], tmp_path / "units.ddd.json", tmp_path)
        assert [path.name for path in loaded.unreadable] == ["a.ddd.json", "units.ddd.json"]
        assert [path.name for path in loaded.unloaded] == ["a.ddd.json"]
```

After class `TestRename`, before `class TestPropagating`, add:

```python
class TestAUnitPlanAsTextEdits:
    """A unit's plan as an editor applies it, and the buffers that keep it from being made."""

    def vocabulary(self, tmp_path: Path) -> Path:
        write_tree(tmp_path, {"units.ddd.json": {"units": ["rpm", {"unit": "Nm"}, "degC", "kPa"]}})
        return tmp_path / "units.ddd.json"

    @pytest.mark.parametrize(
        "operations",
        [
            pytest.param((Operation("set", "units[0]", '"1/min"'),), id="replaced"),
            pytest.param((Operation("set", "units[1].unit", '"N.m"'),), id="replaced-in-an-object"),
            pytest.param(
                (Operation("set", "units[1].description", '"torque"'),), id="member-added"
            ),
            pytest.param((Operation("insert", "units[4]", '"bar"'),), id="inserted"),
            pytest.param((Operation("remove", "units[1]"),), id="removed"),
            pytest.param(
                (Operation("remove", "units[3]"), Operation("remove", "units[2]")),
                id="neighbours-removed-last-first",
            ),
            pytest.param(
                (Operation("remove", "units[2]"), Operation("remove", "units[2]")),
                id="neighbours-removed-in-turn",
            ),
            pytest.param(
                (
                    Operation("set", "units[0]", '"1/min"'),
                    Operation("remove", "units[3]"),
                    Operation("remove", "units[2]"),
                ),
                id="replaced-and-removed",
            ),
        ],
    )
    def test_a_client_applying_the_edits_writes_what_the_engine_writes(
        self, tmp_path: Path, operations: tuple[Operation, ...]
    ) -> None:
        """The engine makes a file's operations in turn, each on the text the last one left; a
        client applies a file's edits at once, to the text as it stands. The file has to come
        out the same, or the editor and ddd gui would write two different things."""
        path = self.vocabulary(tmp_path)
        plan = UnitPlan((PlannedEdit(path, operations),))
        (edits,) = text_edits(plan, {}).values()
        assert apply_edits(path, edits) == edit_text(path.read_text(encoding="utf-8"), operations)

    def test_neighbouring_entries_taken_out_are_one_edit(self, tmp_path: Path) -> None:
        """Each removal takes one comma, and against the text as it stands the two would both
        claim the one between them: two overlapping edits, which a client refuses whole."""
        path = self.vocabulary(tmp_path)
        removed = (Operation("remove", "units[3]"), Operation("remove", "units[2]"))
        (edits,) = text_edits(UnitPlan((PlannedEdit(path, removed),)), {}).values()
        assert len(edits) == 1
        assert json.loads(apply_edits(path, edits))["units"] == ["rpm", {"unit": "Nm"}]

    def test_the_edit_is_made_in_the_buffer_on_screen(self, tmp_path: Path) -> None:
        """The client applies it to what it shows, which one blank line puts a line lower."""
        path = self.vocabulary(tmp_path)
        disk = path.read_text(encoding="utf-8")
        plan = UnitPlan((PlannedEdit(path, (Operation("set", "units[0]", '"1/min"'),)),))
        (edits,) = text_edits(plan, {path: Document("\n" + disk)}).values()
        on_disk = Document(disk).value_range_of("units[0]")
        assert on_disk is not None
        assert edits[0]["range"]["start"]["line"] == on_disk["start"]["line"] + 1

    def test_a_file_the_plan_creates_is_no_text_edit(self, tmp_path: Path) -> None:
        """Only an adoption creates a file, and only ddd gui adopts: an edit of a file that is
        not there would be one no client can apply."""
        created = PlannedEdit(
            tmp_path / "units.ddd.json",
            (Operation("set", "", '{"units": ["rpm"]}'),),
            creates=True,
        )
        with pytest.raises(EditError) as refused:
            text_edits(UnitPlan((created,)), {})
        assert refused.value.code == INVALID

    def built(self, tmp_path: Path) -> Any:
        workspace = load_workspace(unit_places(tmp_path), DiagnosticBag())
        assert workspace is not None
        return navigation.index(workspace)

    def test_a_unit_where_the_index_found_it_has_not_drifted(self, tmp_path: Path) -> None:
        """Its entry an object or the spelling alone, wherever it is stated."""
        built = self.built(tmp_path)
        assert unit_drift(built, "rpm", {}) == ()
        assert unit_drift(built, "Nm", {}) == ()

    def test_a_buffer_that_moved_a_stated_unit_has_drifted(self, tmp_path: Path) -> None:
        built = self.built(tmp_path)
        b = tmp_path / "b.ddd.json"
        moved = json.dumps(
            component(
                "B", declare("input", "Other", unit="Nm"), declare("input", "Speed", unit="rpm")
            ),
            indent=2,
        )
        assert unit_drift(built, "rpm", {b: Document(moved)}) == (b,)

    def test_a_buffer_that_moved_a_vocabulary_entry_has_drifted(self, tmp_path: Path) -> None:
        built = self.built(tmp_path)
        units = tmp_path / "units.ddd.json"
        moved = Document(json.dumps({"units": ["Nm", {"unit": "rpm", "description": "speed"}]}))
        assert unit_drift(built, "rpm", {units: moved}) == (units,)
        assert unit_drift(built, "Nm", {units: moved}) == (units,)
```

In class `TestServer`, after `test_a_file_in_two_projects_is_edited_once`, add (`navigation_request` and `rename_request` are this class's helpers):

```python
    @pytest.mark.parametrize(("source", "pointer"), [*UNIT_PLACES, ("units.ddd.json", "units[1]")])
    def test_preparing_a_rename_of_a_unit_puts_the_box_over_its_spelling(
        self, tmp_path: Path, source: str, pointer: str
    ) -> None:
        unit_places(tmp_path)
        path = tmp_path / source
        document = Document(path.read_text(encoding="utf-8"))
        position = document.range_of(pointer)["start"]
        writer = io.BytesIO()
        Server(
            session(self.navigation_request("textDocument/prepareRename", path, position)),
            writer,
            root=tmp_path,
        ).run()
        (answer,) = answered(writer)
        assert answer["result"] == {
            "range": document.text_range_of(pointer),
            "placeholder": document.value_at(pointer),
        }

    def renamed_unit(self, tmp_path: Path, source: str, pointer: str, name: str) -> Any:
        """The server's answer to a rename asked at ``pointer`` in ``source``."""
        writer = io.BytesIO()
        Server(
            session(self.rename_request(tmp_path / source, pointer, name)),
            writer,
            root=tmp_path,
        ).run()
        (answer,) = answered(writer)
        return answer

    @pytest.mark.parametrize(("source", "pointer"), UNIT_PLACES)
    def test_a_unit_is_renamed_everywhere_from_wherever_it_is_spelled(
        self, tmp_path: Path, source: str, pointer: str
    ) -> None:
        """The same four files whichever place the rename starts from, and afterwards no file
        states the old spelling; the vocabulary's entry keeps its description."""
        unit_places(tmp_path)
        answer = self.renamed_unit(tmp_path, source, pointer, "1/min")
        rewritten = rewritten_by(answer["result"]["changes"])
        assert set(rewritten) == {"units.ddd.json", "types.ddd.json", "a.ddd.json", "b.ddd.json"}
        assert not any('"rpm"' in text for text in rewritten.values())
        assert sum(text.count('"1/min"') for text in rewritten.values()) == len(UNIT_PLACES)
        assert json.loads(rewritten["units.ddd.json"])["units"] == [
            {"unit": "1/min", "description": "speed"},
            "Nm",
        ]

    def test_a_unit_listed_as_a_spelling_alone_is_renamed_from_its_entry(
        self, tmp_path: Path
    ) -> None:
        unit_places(tmp_path)
        answer = self.renamed_unit(tmp_path, "units.ddd.json", "units[1]", "N.m")
        rewritten = rewritten_by(answer["result"]["changes"])
        assert set(rewritten) == {"units.ddd.json", "types.ddd.json"}
        assert json.loads(rewritten["units.ddd.json"])["units"][1] == "N.m"
        pair = json.loads(rewritten["types.ddd.json"])["types"][1]
        assert pair["members"][1]["unit"] == "N.m"

    def test_renaming_onto_a_listed_unit_merges_the_two_spellings(self, tmp_path: Path) -> None:
        """Two spellings of one unit are what a rename of a unit is for: the old one's entry
        is taken out, and the entry that stays keeps its description."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "units.ddd.json", "a.ddd.json", "b.ddd.json"),
                "units.ddd.json": {
                    "units": [{"unit": "rpm", "description": "speed"}, "1/min", "Nm"]
                },
                "a.ddd.json": component(
                    "A",
                    declare("output", "Speed", unit="1/min"),
                    declare("output", "Idle", unit="rpm"),
                ),
                "b.ddd.json": component("B", declare("input", "Speed", unit="1/min")),
            },
        )
        answer = self.renamed_unit(
            tmp_path, "b.ddd.json", "component.interface[0].definition.unit", "rpm"
        )
        rewritten = rewritten_by(answer["result"]["changes"])
        assert set(rewritten) == {"units.ddd.json", "a.ddd.json", "b.ddd.json"}
        assert json.loads(rewritten["units.ddd.json"])["units"] == [
            {"unit": "rpm", "description": "speed"},
            "Nm",
        ]
        assert "1/min" not in rewritten["a.ddd.json"] + rewritten["b.ddd.json"]

    def test_a_unit_listed_twice_is_merged_at_both_of_its_entries(self, tmp_path: Path) -> None:
        """The units file loaded, though with a duplicate-unit error, so the rename reaches
        both entries - and the two neighbours taken out come to the client as one edit."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "units.ddd.json", "a.ddd.json"),
                "units.ddd.json": {"units": ["rpm", "RPM", "RPM"]},
                "a.ddd.json": component("A", declare("output", "Speed", unit="RPM")),
            },
        )
        answer = self.renamed_unit(
            tmp_path, "a.ddd.json", "component.interface[0].definition.unit", "rpm"
        )
        changes = answer["result"]["changes"]
        rewritten = rewritten_by(changes)
        assert json.loads(rewritten["units.ddd.json"])["units"] == ["rpm"]
        speed = json.loads(rewritten["a.ddd.json"])["component"]["interface"][0]
        assert speed["definition"]["unit"] == "rpm"
        assert len(changes[(tmp_path / "units.ddd.json").as_uri()]) == 1

    def refusal_of(self, document: Path, old: str, new: str) -> UnitRefusalError:
        """The plan's own refusal of this rename, which is what the server has to answer."""
        (loaded,) = navigation.workspaces([], document, document.parent)
        built = navigation.index(loaded.workspace)
        project = unit_project(loaded.path, loaded.unloaded, {})
        with pytest.raises(UnitRefusalError) as refused:
            rename_unit(built, project, old, new, {})
        return refused.value

    @pytest.mark.parametrize("name", ["", " 1/min", "rpm"])
    def test_a_unit_rename_the_plan_refuses_is_answered_with_its_reason(
        self, tmp_path: Path, name: str
    ) -> None:
        """No spelling at all, one with spaces around it, and the spelling it has already."""
        unit_places(tmp_path)
        a = tmp_path / "a.ddd.json"
        answer = self.renamed_unit(
            tmp_path, "a.ddd.json", "component.interface[0].definition.unit", name
        )
        refusal = self.refusal_of(a, "rpm", name)
        assert refusal.code == "invalid"
        assert answer["error"] == {"code": REQUEST_FAILED, "message": refusal.message}

    def test_a_unit_rename_is_refused_while_a_file_of_the_project_did_not_load(
        self, tmp_path: Path
    ) -> None:
        """The file that did not load may state the unit too, and nothing could reach it."""
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "units.ddd.json", "a.ddd.json", "b.ddd.json"),
                "units.ddd.json": {"units": ["rpm"]},
                "a.ddd.json": component("A", declare("output", "Speed", "uint99", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="rpm")),
            },
        )
        answer = self.renamed_unit(
            tmp_path, "b.ddd.json", "component.interface[0].definition.unit", "1/min"
        )
        refusal = self.refusal_of(tmp_path / "b.ddd.json", "rpm", "1/min")
        assert refusal.code == "unreadable"
        assert "a.ddd.json" in refusal.message
        assert answer["error"] == {"code": REQUEST_FAILED, "message": refusal.message}

    def unit_rename_in_a_buffer(
        self, tmp_path: Path, opened: Path, text: str, asked: Path, name: str
    ) -> dict[str, Any]:
        """The answer to a rename of the unit of ``asked``'s first declaration, while ``opened``
        holds ``text`` unsaved."""
        shown = text if asked == opened else asked.read_text(encoding="utf-8")
        at = Document(shown).range_of("component.interface[0].definition.unit")["start"]
        stream = framed(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"rootUri": tmp_path.as_uri()},
            },
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didOpen",
                "params": {
                    "textDocument": {
                        "uri": opened.as_uri(),
                        "languageId": "json",
                        "version": 1,
                        "text": text,
                    }
                },
            },
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "textDocument/rename",
                "params": {
                    "textDocument": {"uri": asked.as_uri()},
                    "position": at,
                    "newName": name,
                },
            },
            {"jsonrpc": "2.0", "id": 3, "method": "shutdown"},
            {"jsonrpc": "2.0", "method": "exit"},
        )
        writer = io.BytesIO()
        assert Server(stream, writer, root=tmp_path).run() == 0
        return next(message for message in sent(writer) if message.get("id") == 2)

    def test_renaming_a_unit_the_project_neither_states_nor_lists_is_refused(
        self, tmp_path: Path
    ) -> None:
        """Typed into a buffer and not saved: the project the index read has no such unit."""
        unit_places(tmp_path)
        a = tmp_path / "a.ddd.json"
        typed = a.read_text(encoding="utf-8").replace('"unit": "rpm"', '"unit": "rpmx"', 1)
        answer = self.unit_rename_in_a_buffer(tmp_path, a, typed, a, "1/min")
        refusal = self.refusal_of(a, "rpmx", "1/min")
        assert refusal.code == "not-found"
        assert answer["error"] == {"code": REQUEST_FAILED, "message": refusal.message}

    def test_a_unit_rename_is_refused_while_a_buffer_has_moved_the_unit(
        self, tmp_path: Path
    ) -> None:
        """The plan's pointers are the disk's: made in B's buffer, where a declaration was put
        in front, the rename would respell 'Other' and leave 'Speed' as it was."""
        unit_places(tmp_path)
        moved = json.dumps(
            component(
                "B", declare("input", "Other", unit="Nm"), declare("input", "Speed", unit="rpm")
            ),
            indent=2,
        )
        answer = self.unit_rename_in_a_buffer(
            tmp_path, tmp_path / "b.ddd.json", moved, tmp_path / "a.ddd.json", "1/min"
        )
        assert answer["error"]["code"] == REQUEST_FAILED
        assert answer["error"]["message"].startswith("b.ddd.json has unsaved changes")
        assert "result" not in answer

    def test_a_code_action_on_an_unknown_unit_offers_the_vocabulary_fixes(
        self, tmp_path: Path
    ) -> None:
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "units.ddd.json", "a.ddd.json"),
                "units.ddd.json": {"units": ["rpm", "Nm"]},
                "a.ddd.json": component("A", declare("output", "Speed", unit="RPM")),
            },
        )
        a = tmp_path / "a.ddd.json"
        span = Document(a.read_text(encoding="utf-8")).range_of(
            "component.interface[0].definition.unit"
        )
        writer = io.BytesIO()
        Server(
            session(
                {
                    "jsonrpc": "2.0",
                    "id": 13,
                    "method": "textDocument/codeAction",
                    "params": {
                        "textDocument": {"uri": a.as_uri()},
                        "range": span,
                        "context": {"diagnostics": UNLISTED},
                    },
                }
            ),
            writer,
            root=tmp_path,
        ).run()
        (answer,) = answered(writer)
        added, renamed = answer["result"]
        assert added["title"] == "Add 'RPM' to the vocabulary"
        assert list(added["edit"]["changes"]) == [(tmp_path / "units.ddd.json").as_uri()]
        assert renamed["title"] == "Rename 'RPM' to 'rpm' everywhere"
        assert list(renamed["edit"]["changes"]) == [a.as_uri()]
```

After class `TestOfferingAnIdentity`, before `class TestFrameLengths`, add:

```python
UNLISTED = [
    {"code": "unknown-unit", "source": "ddd", "message": "is not a unit this project declares"}
]


class TestFixingAnUnknownUnit:
    """The code actions behind ``unknown-unit``: put the unit into the vocabulary, or respell it
    everywhere as a unit the vocabulary lists - the plans ``ddd gui`` makes, as text edits."""

    AT_THE_UNIT = "component.interface[0].definition.unit"

    def stating(self, tmp_path: Path, unit: str, *vocabulary: Any) -> Path:
        """A producer declaring two variables in ``unit`` and a reader of one, and a vocabulary
        of ``vocabulary`` when it lists anything."""
        files: dict[str, Any] = {
            "a.ddd.json": component(
                "A", declare("output", "Speed", unit=unit), declare("output", "Idle", unit=unit)
            ),
            "b.ddd.json": component("B", declare("input", "Speed", unit=unit)),
        }
        if vocabulary:
            files["units.ddd.json"] = {"units": list(vocabulary)}
        write_tree(tmp_path, {"p.ddd.json": project("P", *files), **files})
        return tmp_path / "p.ddd.json"

    def offered(
        self,
        root: Path,
        source: str = "a.ddd.json",
        pointer: str = AT_THE_UNIT,
        cache: dict[Path, Document] | None = None,
        reported: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        from ddd.lsp.edits import actions

        cache = {} if cache is None else cache
        reported = UNLISTED if reported is None else reported
        workspace = load_workspace(root, DiagnosticBag())
        assert workspace is not None
        built = navigation.index(workspace)
        path = root.parent / source
        project = unit_project(root, (), cache)
        return actions(built, path, read(path, cache), pointer, cache, reported, project)

    def titles(self, offered: list[dict[str, Any]]) -> list[str]:
        return [action["title"] for action in offered]

    def test_an_unknown_unit_is_offered_the_vocabulary_and_each_close_spelling(
        self, tmp_path: Path
    ) -> None:
        """One rename per spelling the finding suggests, in the order it names them: closest
        first, a tie by spelling."""
        offered = self.offered(self.stating(tmp_path, "rpms", "rpm", "rps", "rpm2", "Nm"))
        assert self.titles(offered) == [
            "Add 'rpms' to the vocabulary",
            "Rename 'rpms' to 'rpm' everywhere",
            "Rename 'rpms' to 'rps' everywhere",
            "Rename 'rpms' to 'rpm2' everywhere",
        ]
        assert all(action["diagnostics"] == UNLISTED for action in offered)

    @pytest.mark.parametrize(
        ("vocabulary", "added"),
        [
            (("rpm", "Nm"), "rpms"),
            (("rpm", {"unit": "Nm", "description": "torque"}), {"unit": "rpms", "description": ""}),
        ],
    )
    def test_adding_appends_the_unit_in_the_form_the_vocabulary_is_written_in(
        self, tmp_path: Path, vocabulary: tuple[Any, ...], added: Any
    ) -> None:
        root = self.stating(tmp_path, "rpms", *vocabulary)
        (adding,) = [a for a in self.offered(root) if a["title"].startswith("Add")]
        rewritten = rewritten_by(adding["edit"]["changes"])
        assert json.loads(rewritten["units.ddd.json"])["units"] == [*vocabulary, added]

    def test_renaming_respells_the_unit_everywhere_it_is_stated(self, tmp_path: Path) -> None:
        root = self.stating(tmp_path, "rpms", "rpm", "Nm")
        (renaming,) = [a for a in self.offered(root) if a["title"].startswith("Rename")]
        rewritten = rewritten_by(renaming["edit"]["changes"])
        assert set(rewritten) == {"a.ddd.json", "b.ddd.json"}
        assert rewritten["a.ddd.json"].count('"unit": "rpm"') == 2
        assert rewritten["b.ddd.json"].count('"unit": "rpm"') == 1

    def test_a_unit_a_type_states_is_offered_the_same(self, tmp_path: Path) -> None:
        """A unit is written on a scalar type as often as on a declaration."""
        files: dict[str, Any] = {
            "units.ddd.json": {"units": ["rpm", "Nm"]},
            "types.ddd.json": types(scalar_type("Speed_t", unit="rpms")),
        }
        write_tree(tmp_path, {"p.ddd.json": project("P", *files), **files})
        offered = self.offered(tmp_path / "p.ddd.json", "types.ddd.json", "types[0].unit")
        assert self.titles(offered) == [
            "Add 'rpms' to the vocabulary",
            "Rename 'rpms' to 'rpm' everywhere",
        ]

    def test_a_unit_in_another_case_is_offered_the_spelling_the_vocabulary_lists(
        self, tmp_path: Path
    ) -> None:
        """The design's own example: 'RPM' against a vocabulary listing 'rpm'."""
        root = self.stating(tmp_path, "RPM", "rpm", "Nm")
        offered = self.offered(root)
        assert self.titles(offered) == [
            "Add 'RPM' to the vocabulary",
            "Rename 'RPM' to 'rpm' everywhere",
        ]
        rewritten = rewritten_by(offered[1]["edit"]["changes"])
        assert "RPM" not in rewritten["a.ddd.json"] + rewritten["b.ddd.json"]

    def test_a_unit_nothing_in_the_vocabulary_is_close_to_is_offered_no_rename(
        self, tmp_path: Path
    ) -> None:
        """The finding suggests nothing, and neither does the lightbulb."""
        offered = self.offered(self.stating(tmp_path, "bar", "rpm", "Nm"))
        assert self.titles(offered) == ["Add 'bar' to the vocabulary"]

    def test_nothing_is_offered_unless_the_finding_was_reported(self, tmp_path: Path) -> None:
        """Which keeps the offer inside the project's own severity policy, as the identity's."""
        root = self.stating(tmp_path, "rpms", "rpm", "Nm")
        assert self.offered(root, reported=[]) == []

    def test_nothing_is_offered_without_the_project_to_plan_in(self, tmp_path: Path) -> None:
        from ddd.lsp.edits import actions

        root = self.stating(tmp_path, "rpms", "rpm", "Nm")
        workspace = load_workspace(root, DiagnosticBag())
        assert workspace is not None
        path = tmp_path / "a.ddd.json"
        cache: dict[Path, Document] = {}
        offered = actions(
            navigation.index(workspace),
            path,
            read(path, cache),
            self.AT_THE_UNIT,
            cache,
            UNLISTED,
        )
        assert offered == []

    def test_a_unit_the_vocabulary_lists_by_now_is_offered_nothing(self, tmp_path: Path) -> None:
        """The finding came from an older save; the vocabulary lists the unit now."""
        assert self.offered(self.stating(tmp_path, "rpm", "rpm", "Nm")) == []

    def test_a_plan_the_project_refuses_is_not_offered(self, tmp_path: Path) -> None:
        """No units file to add the unit to, and no vocabulary to be close to: a finding from
        before the units file was taken out of the project."""
        assert self.offered(self.stating(tmp_path, "rpms")) == []

    def test_a_rename_the_plan_refuses_is_not_offered(self, tmp_path: Path) -> None:
        """The buffer spells a unit the project on disk does not state, so there is nothing
        of it to rename yet - while adding it is a plan like any other."""
        root = self.stating(tmp_path, "rpms", "rpm", "rps", "rpm2", "Nm")
        a = tmp_path / "a.ddd.json"
        typed = json.dumps(
            component(
                "A", declare("output", "Speed", unit="rpms"), declare("output", "Idle", unit="rpmx")
            ),
            indent=2,
        )
        offered = self.offered(
            root, pointer="component.interface[1].definition.unit", cache={a: Document(typed)}
        )
        assert self.titles(offered) == ["Add 'rpmx' to the vocabulary"]

    def test_a_units_file_caught_halfway_through_an_edit_is_offered_no_addition(
        self, tmp_path: Path
    ) -> None:
        """Its buffer is no json the engine can place an entry in, and no edit is better than
        one that lands somewhere else."""
        root = self.stating(tmp_path, "rpms", "rpm", "Nm")
        units = tmp_path / "units.ddd.json"
        offered = self.offered(root, cache={units: Document('{"units": ["rpm", "Nm"')})
        assert self.titles(offered) == ["Rename 'rpms' to 'rpm' everywhere"]

    def test_no_rename_is_offered_while_a_buffer_has_moved_the_unit(self, tmp_path: Path) -> None:
        root = self.stating(tmp_path, "rpms", "rpm", "Nm")
        b = tmp_path / "b.ddd.json"
        moved = json.dumps(
            component(
                "B", declare("input", "Other", unit="Nm"), declare("input", "Speed", unit="rpms")
            ),
            indent=2,
        )
        offered = self.offered(root, cache={b: Document(moved)})
        assert self.titles(offered) == ["Add 'rpms' to the vocabulary"]
```

Run: `python -m pytest tests/test_units.py tests/test_lsp.py --no-cov`
Expected: FAIL - neither module collects: `ImportError: cannot import name 'close_units' from 'ddd.analysis'` and `ImportError: cannot import name 'text_edits' from 'ddd.lsp.units'`.

- [ ] **Step 2: `close_units`, one rule for suggesting a unit**

In `src/ddd/analysis.py`, replace `_did_you_mean` with these three functions; `_or_list` stays after them:

```python
def close_units(unit: str, vocabulary: Sequence[str]) -> tuple[str, ...]:
    """The spellings of ``vocabulary`` closest to ``unit``, whatever their case: at most three,
    closest first, then by spelling.

    One rule for the two places a unit is suggested: the did-you-mean of ``unknown-unit``, and
    the language server's "Rename 'RPM' to 'rpm' everywhere", which offers exactly the spellings
    the finding names. The spellings are compared lowercased, because a unit written in the
    wrong case is the likeliest near miss of all - and scored as written, ``RPM`` and ``rpm``
    share no character. Case still counts in the vocabulary, so every spelling of a close unit
    is answered: ``mV`` and ``MV`` alike. A unit is a short spelling and matches loosely, at
    0.5; ``unit`` itself is never answered.
    """
    wanted = unit.lower()
    scores = {
        spelling: difflib.SequenceMatcher(None, spelling.lower(), wanted).ratio()
        for spelling in vocabulary
        if spelling != unit
    }
    close = sorted(
        (spelling for spelling, score in scores.items() if score >= 0.5),
        key=lambda spelling: (-scores[spelling], spelling),
    )
    return tuple(close[:3])


def _did_you_mean(name: str, candidates: Sequence[str], *, cutoff: float) -> str:
    """The suggestion suffix for ``name``, from the candidates at least ``cutoff`` close to it.

    The cutoff stays with the caller: a unit or section is a short spelling and matches
    loosely at 0.5, a type name is longer and wants the stricter 0.6.
    """
    return _suggesting(tuple(difflib.get_close_matches(name, candidates, n=3, cutoff=cutoff)))


def _suggesting(matches: tuple[str, ...]) -> str:
    """`` - did you mean 'Nm'?``: the suggestion suffix, empty when nothing is close enough."""
    return f" - did you mean {_or_list(matches)}?" if matches else ""
```

In `_check_units`, the inner `check` builds its suffix from `close_units`. The words are the same; what changes is who is named - a spelling differing only in case, and two that tie in the order of their spelling:

```python
        def check(unit: str, where: Location) -> None:
            if unit and unit not in vocabulary:
                nearest = _suggesting(close_units(unit, sorted(vocabulary)))
                self._bag.add(
                    "unknown-unit",
                    f"'{unit}' is not a unit this project declares{nearest}",
                    where,
                )
```

- [ ] **Step 3: A unit is a rename subject**

In `src/ddd/lsp/navigation.py`, after `_CONSTANT_NAME`, add:

```python
_UNIT_KEY: Final = re.compile(
    rf"^(?:(?:component\.interface\[\d+\]\.definition|(?:component\.)?types\[\d+\]|{_MEMBER}"
    rf"|units\[\d+\])\.unit|units\[\d+\])$"
)
"""Where a unit is spelled: a declaration's ``unit``; a scalar type's or a structure member's, in
a types file or in a component's own list; and an entry of a units file - the spelling on its
own, or the ``unit`` of an object. The places ``unknown-unit`` checks, and the vocabulary it
checks them against."""
```

and replace `renameable_at` with:

```python
def renameable_at(document: Document, pointer: str) -> tuple[str, str] | None:
    """What a rename may start from at this position: its kind and its name, or nothing.

    A variable, from its name or from a reference naming it; a declared type, from the
    ``name`` of its entry or from any ``typename`` spelling it; a declared constant, from the
    ``name`` of its entry or from any dimension or axis ``size`` spelling it; a unit, from any
    place it is stated or from its entry in a units file. Narrow on purpose, like
    :func:`variable_at`: the editor opens its box over the range this names.

    A unit is renamed by :func:`ddd.lsp.units.rename_unit` rather than by :func:`rename_edits`:
    its rename rewrites the vocabulary too, and merges two spellings where a name would collide.
    """
    value = document.value_at(pointer)
    if not isinstance(value, str):
        return None
    variable = variable_at(document, pointer)
    if variable is not None:
        return ("variable", variable)
    if _TYPENAME_KEY.match(pointer) or _TYPE_NAME.match(pointer):
        return ("type", value)
    if _DIMENSION_KEY.match(pointer) or _CONSTANT_NAME.match(pointer):
        return ("constant", value)
    # The empty unit is no unit - a dimensionless value states none - so there is nothing
    # spelled there to rename.
    if value and _UNIT_KEY.match(pointer):
        return ("unit", value)
    return None
```

`_prepare_rename` needs no change: it answers `text_range_of(pointer)` and `subject[1]` for whatever `renameable_at` names, which for a unit is the characters between the quotes, and the unit.

- [ ] **Step 4: A file that did not load, told from one that loaded with an error**

In `src/ddd/lsp/navigation.py`, after `_BASE_DATATYPES` and its docstring, add the constant `ddd gui` has kept until now:

```python
LOAD_CHECKS: Final = frozenset({"file-not-found", "json-syntax", "file-kind", "schema"})
"""The checks whose error on a file means that file did not load.

One notion for both clients: ``ddd gui`` shows such a file as not loaded, and a plan of
:mod:`ddd.lsp.units` made in the language server refuses to reach round one.
"""
```

In `Loaded`, after `unreadable` and its docstring, add:

```python
    unloaded: tuple[Path, ...] = ()
    """The files of ``unreadable`` that did not load at all, sorted: an error of one of
    :data:`LOAD_CHECKS`, as ``ddd gui`` counts a file that did not load.

    Narrower on purpose, for the plans of :mod:`ddd.lsp.units`. A file that loaded with an error
    is in the index all the same: a units file listing a unit twice is reported as
    ``duplicate-unit``, and a rename of that unit has to reach both of its entries, which a
    refusal would not let it do.
    """
```

`_loaded` fills it in - its last line becomes:

```python
    return Loaded(path, workspace, bag, _unreadable(bag), _unreadable(bag, LOAD_CHECKS))
```

and `_unreadable` becomes:

```python
def _unreadable(bag: DiagnosticBag, checks: frozenset[str] | None = None) -> tuple[Path, ...]:
    """Every file the read reported an error on - an error of one of ``checks``, when they are
    given - sorted and each named once."""
    found = {
        finding.location.path
        for finding in bag.sorted
        if finding.severity is Severity.ERROR
        and finding.location is not None
        and (checks is None or finding.check in checks)
    }
    return tuple(sorted(found))
```

In `src/ddd/gui/session.py`, delete `LOAD_CHECKS` and its docstring (lines 37-38), and import it where it now lives:

```python
from ddd.lsp.navigation import LOAD_CHECKS, Index
```

- [ ] **Step 5: A plan as text edits, and the buffers that drifted from it**

In `src/ddd/lsp/units.py`, add `INVALID`, `EditError`, `TextEdit`, `insertion`, `member_addition`, `removal` and `replacement` to the names the module imports from `ddd.editing`, beside `Operation` and whatever else Task 2 imports there, in ruff's order - with Task 2's fragment as it stands:

```python
from ddd.editing import (
    INVALID,
    EditError,
    Operation,
    TextEdit,
    insertion,
    member_addition,
    removal,
    replacement,
)
```

and after `from ddd.lsp.ranges import Document, read`, add:

```python
from ddd.pointers import parent_pointer
```

(`Any`, `Sequence`, `Path`, `Index`, `Document` and `read` are imported by Task 2 already.) From Step 6 on `ddd.lsp.edits` imports this module, so this module must never import `ddd.lsp.edits`; that is why `_protocol_edit` below is its own. At the end of the module, add:

```python
def text_edits(plan: UnitPlan, cache: dict[Path, Document]) -> dict[str, list[dict[str, Any]]]:
    """A plan as a language client applies it: the protocol's text edits, by file uri.

    Each operation is made by the edit engine's own :func:`~ddd.editing.replacement`,
    :func:`~ddd.editing.member_addition`, :func:`~ddd.editing.removal` or
    :func:`~ddd.editing.insertion`, on the text the operations before it left - the way
    ``POST /api/edit`` makes them, so an editor and ``ddd gui`` write the same bytes. A client
    applies a file's edits all at once, to the text as it stands, and refuses two that overlap,
    so the edits are restated against that text, and edits that meet become one: two
    neighbouring vocabulary entries taken out would otherwise both claim the comma between them.

    Each file is read through ``cache``, which holds the buffers an editor has open, because
    the edit is applied to what is on screen. A plan that creates a file - an adoption, which
    only ``ddd gui`` plans - is refused rather than rendered: a text edit changes a file that
    is there.
    """
    changes: dict[str, list[dict[str, Any]]] = {}
    for planned in plan.edits:
        if planned.creates:
            raise EditError(
                INVALID, f"{planned.path.name} is created by this plan, which no text edit can do"
            )
        document = read(planned.path, cache)
        changes[planned.path.as_uri()] = [
            _protocol_edit(document, edit) for edit in _simultaneous(document, planned.operations)
        ]
    return changes


def unit_drift(built: Index, unit: str, cache: dict[Path, Document]) -> tuple[Path, ...]:
    """The files whose text no longer holds ``unit`` where the index found it, sorted.

    The index is read off the disk, and a buffer an editor has open may have moved or respelled
    what it recorded since. A plan's pointers are the index's, so made in that buffer they would
    respell whatever sits there now: the language server refuses the rename instead, naming
    these files, and offers none as a quick fix.
    """
    stated = [
        found.site.path
        for found in built.units.get(unit, ())
        if read(found.site.path, cache).value_at(found.site.pointer) != unit
    ]
    listed = [
        entry.path
        for entry in built.vocabulary.get(unit, ())
        if read(entry.path, cache).value_at(entry.pointer) != unit
        and read(entry.path, cache).value_at(f"{entry.pointer}.unit") != unit
    ]
    return tuple(sorted({*stated, *listed}))


def _simultaneous(document: Document, operations: Sequence[Operation]) -> list[TextEdit]:
    """The operations' edits of ``document`` as its text stands, in order and none overlapping.

    Made one after another, as the engine makes them, with every character of the result
    remembered by where it came from: an offset of the text as it stands, or none for a
    character an edit wrote. Whatever lies between two characters kept from that text is one
    edit of it, however many operations it took.
    """
    current = document
    origins: list[int | None] = list(range(len(document.text)))
    for operation in operations:
        edit = _engine_edit(current, operation)
        origins[edit.start : edit.end] = [None] * len(edit.text)
        text = current.text
        current = Document(f"{text[: edit.start]}{edit.text}{text[edit.end :]}")
    edits: list[TextEdit] = []
    kept = 0
    written: list[str] = []
    # A last character kept past the end, so that an edit running to the end of the text is
    # closed like any other.
    ends = ("", len(document.text))
    for character, origin in [*zip(current.text, origins, strict=True), ends]:
        if origin is None:
            written.append(character)
            continue
        if origin != kept or written:
            edits.append(TextEdit(kept, origin, "".join(written)))
            written = []
        kept = origin + 1
    return edits


def _engine_edit(document: Document, operation: Operation) -> TextEdit:
    """The edit the engine makes for one operation, as :func:`ddd.editing.edit_text` makes it:
    an entry taken out with one comma, an element inserted into an array, a value replaced, or
    a member added to an object that has none of that name. A plan makes no ``move``."""
    if operation.op == "remove":
        return removal(document, operation.pointer)
    # Every other operation of a plan writes a value, carried as json text.
    assert operation.raw is not None
    if operation.op == "insert":
        return insertion(document, operation.pointer, operation.raw)
    if document.raw_at(operation.pointer) is not None:
        return replacement(document, operation.pointer, operation.raw)
    parent = parent_pointer(operation.pointer)
    key = operation.pointer[len(parent) + 1 :] if parent else operation.pointer
    return member_addition(document, parent, key, operation.raw)


def _protocol_edit(document: Document, edit: TextEdit) -> dict[str, Any]:
    """An edit the engine computed as offsets, as the protocol carries it - the rendering
    :mod:`ddd.lsp.edits` gives its quick fixes."""
    return {
        "range": {"start": document.position(edit.start), "end": document.position(edit.end)},
        "newText": edit.text,
    }
```

Why `_simultaneous` exists: `edit_text` makes a file's operations in turn, each pointer naming its place in the text the operation before it left, while a client applies a file's edits at once, to the text they were computed on, and refuses two that overlap. `removal` takes the comma after an entry, or the one before it for the last, so two neighbouring entries taken out - a merge of a unit listed twice - both claim the comma between them when each is computed against one text. The cases `neighbours-removed-last-first` and `neighbours-removed-in-turn` are that, in both orders a plan may give them; `test_neighbouring_entries_taken_out_are_one_edit` and `test_a_unit_listed_twice_is_merged_at_both_of_its_entries` check it comes out as one edit.

- [ ] **Step 6: The two quick fixes**

In `src/ddd/lsp/edits.py`, the imports become:

```python
from __future__ import annotations

import contextlib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any, Final, Literal

from ddd.analysis import close_units
from ddd.editing import EditError, TextEdit, member_addition, removal
from ddd.identity import insertions
from ddd.lsp.navigation import Index, Site, renameable_at
from ddd.lsp.ranges import Document, read
from ddd.lsp.units import (
    UnitProject,
    UnitRefusalError,
    add_unit,
    rename_unit,
    text_edits,
    unit_drift,
)
from ddd.models import definition_keys
from ddd.models.objects import MEANING_KEYS
```

After `UNIDENTIFIED` and its docstring, add:

```python
UNKNOWN_UNIT: Final = frozenset({"unknown-unit"})
"""The finding the vocabulary actions settle, so a client can put its lightbulb on the squiggle.

Its own set for the reason :data:`UNIDENTIFIED` has one: these actions change the vocabulary, or
every place a unit is stated, rather than one declaration to agree with another.
"""
```

Replace the head of `actions` - its signature and its docstring - with the block below. It ends with the head of `_on_the_declaration`, and the old body of `actions`, from `within = _WITHIN_DEFINITION.match(pointer)` to `return offered`, stays exactly as it is as that function's body:

```python
def actions(
    built: Index,
    path: Path,
    document: Document,
    pointer: str,
    cache: dict[Path, Document],
    reported: Sequence[dict[str, Any]] = (),
    project: UnitProject | None = None,
) -> list[dict[str, Any]]:
    """What an editor may offer at this position.

    On a key that can be propagated, that key. Anywhere else inside the declaration - on the
    ``"definition"`` line, on a nested ``limits.min``, on a selection covering the lot - every
    key that differs from the other declarations, one action each.

    The wide answer is the one that matters in practice. The finding is drawn over the whole
    declaration, so that is where the pointer lands when somebody asks for a fix; requiring
    them to have first found the offending key is asking them to do the diagnosis the fix is
    for.

    Nothing at all when there is nothing to change: a fix that does nothing teaches a reader
    to stop reading the lightbulb.

    The reconcile actions are offered whether or not the client sent a finding with its
    request; the identity one is not. It is offered only where ``missing-id`` was actually
    reported, which is what keeps it inside the project's own severity policy: a project that
    has silenced the check with ``-W missing-id=ignore`` has said it is not adopting ids yet,
    and an editor that goes on offering them anyway is arguing with a decision already made.

    The vocabulary actions are offered only where ``unknown-unit`` was reported, for the same
    reason, and on whatever states the unit - a scalar type or a structure member as much as a
    declaration. They are planned in the project ``project`` names; without one, none is.
    """
    # After the declaration's own actions, so that neither inherits the other's findings, and
    # a fix the reader asked for about the declaration keeps the preferred slot.
    return [
        *_on_the_declaration(built, path, document, pointer, cache, reported),
        *_vocabulary_actions(built, document, pointer, cache, reported, project),
    ]


def _on_the_declaration(
    built: Index,
    path: Path,
    document: Document,
    pointer: str,
    cache: dict[Path, Document],
    reported: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    """The actions on the declaration around the cursor: its keys brought into agreement with
    the other declarations of its object, and an identity where ``missing-id`` was reported."""
```

After `_on_the_declaration`, before `interface_keys`, add:

```python
def _vocabulary_actions(
    built: Index,
    document: Document,
    pointer: str,
    cache: dict[Path, Document],
    reported: Sequence[dict[str, Any]],
    project: UnitProject | None,
) -> list[dict[str, Any]]:
    """Put the unit under the cursor into the vocabulary, or respell it everywhere as a unit the
    vocabulary lists.

    Both are the plans of :mod:`ddd.lsp.units`, the ones ``ddd gui`` makes, so an editor and the
    page write the same edit. The spellings offered are the finding's own suggestions -
    :func:`ddd.analysis.close_units` over the same vocabulary - so the lightbulb never proposes
    a unit the message did not name, and a unit nothing is close to is offered no rename at
    all. A plan that is refused is not offered.
    """
    unknown = [entry for entry in reported if entry.get("code") in UNKNOWN_UNIT]
    subject = renameable_at(document, pointer)
    if project is None or not unknown or subject is None or subject[0] != "unit":
        return []
    unit = subject[1]
    if unit in built.vocabulary:
        # The finding is older than the vocabulary, which lists the unit now.
        return []
    plans = [(f"Add '{unit}' to the vocabulary", partial(add_unit, built, project, unit, cache))]
    # A rename's pointers are the disk's, and made in a buffer that has moved one of them it
    # would respell whatever sits there now: none is offered until that buffer is saved.
    if not unit_drift(built, unit, cache):
        plans.extend(
            (
                f"Rename '{unit}' to '{close}' everywhere",
                partial(rename_unit, built, project, unit, close, cache),
            )
            for close in close_units(unit, sorted(built.vocabulary))
        )
    offered: list[dict[str, Any]] = []
    for title, plan in plans:
        # Refused, or not an edit the engine can make in the buffer as it stands - a units file
        # caught halfway through an edit: either way there is nothing to offer.
        with contextlib.suppress(UnitRefusalError, EditError):
            changes = text_edits(plan(), cache)
            offered.append(
                {
                    "title": title,
                    "kind": QUICK_FIX,
                    "edit": {"changes": changes},
                    "diagnostics": unknown,
                }
            )
    return offered
```

- [ ] **Step 7: The server renames a unit, and gives the code actions their project**

In `src/ddd/lsp/server.py`, the `ddd.lsp.edits` import becomes `from ddd.lsp.edits import QUICK_FIX, UNKNOWN_UNIT, actions`, and after `from ddd.lsp.ranges import Document, read` add:

```python
from ddd.lsp.units import UnitRefusalError, rename_unit, text_edits, unit_drift, unit_project
```

Replace `_answer_rename` with these four methods. The variable rename keeps its order and its words: its dedupe loop and its drift message move into `_gather` and `_drifted` unchanged, and its comment on the dedupe becomes `_gather`'s docstring.

```python
    def _answer_rename(self, request_id: Any, message: dict[str, Any]) -> None:
        """Rewrite a name everywhere the project writes it, or say why it cannot be.

        A refusal is an error rather than an empty edit: an editor shows the message, where an
        empty edit looks like a rename that quietly did nothing. A drifted buffer is refused
        along with the rest of the rename rather than skipped on its own: writing every other
        file and leaving that one alone is the half-renamed project the refusal exists to
        prevent, and it would happen silently, because the client asked for one rename, not a
        rename of everything except what it could not reach.

        A unit is renamed by :meth:`_rename_unit` instead: its rename is a plan that rewrites
        the vocabulary as well, and merges two spellings where a variable's would collide.
        """
        path = self._document(message)
        cache = self._cache(path)
        document = read(path, cache)
        pointer = document.pointer_at(self._at(message))
        params = _field(message.get("params"), dict, "params")
        wanted = _field(params.get("newName"), str, "params.newName")
        subject = renameable_at(document, pointer)
        if subject is not None and subject[0] == "unit":
            self._rename_unit(request_id, path, subject[1], wanted, cache)
            return
        changes: dict[str, list[dict[str, Any]]] = {}
        seen: set[tuple[str, int, int]] = set()
        drifted: set[Path] = set()
        for loaded in self._projects_of(path):
            unreadable = self._unreadable(loaded)
            if unreadable is not None:
                write_message(self.writer, error(request_id, REQUEST_FAILED, unreadable))
                return
            built = index(loaded.workspace)
            refused = rename_problem(built, wanted, subject[0] if subject else "variable")
            if refused is not None:
                write_message(self.writer, error(request_id, REQUEST_FAILED, refused))
                return
            edited = rename_edits(built, document, pointer, wanted, cache)
            drifted.update(edited.drifted)
            self._gather(changes, seen, edited.changes)
        if drifted:
            refusal = self._drifted(drifted, "moved a declaration")
            write_message(self.writer, error(request_id, REQUEST_FAILED, refusal))
            return
        # The edits rewrite the very files every answer above was read out of, so anything
        # kept from before them now describes the past.
        self._forget()
        write_message(self.writer, response(request_id, self._workspace_edit(changes)))

    def _rename_unit(
        self, request_id: Any, path: Path, old: str, new: str, cache: dict[Path, Document]
    ) -> None:
        """Respell a unit everywhere each project holding the document states or lists it, or
        say why it cannot be.

        The plan is :func:`ddd.lsp.units.rename_unit`'s, the one ``ddd gui`` previews and
        applies, so an editor and the page cannot disagree about what a rename reaches or when
        it merges two spellings; its refusal is answered as a variable's is. The plan refuses
        while a file of the project did not load, and only then: one that loaded with an error
        is in the index, and a unit its units file lists twice is renamed at both entries. A
        buffer that no longer holds the unit where the index found it refuses the rename before
        the plan is made: the plan's pointers are the disk's, and made in that buffer they would
        respell whatever sits there now.
        """
        changes: dict[str, list[dict[str, Any]]] = {}
        seen: set[tuple[str, int, int]] = set()
        drifted: set[Path] = set()
        for loaded in self._projects_of(path):
            built = index(loaded.workspace)
            moved = unit_drift(built, old, cache)
            if moved:
                drifted.update(moved)
                continue
            project = unit_project(loaded.path, loaded.unloaded, cache)
            try:
                plan = rename_unit(built, project, old, new, cache)
            except UnitRefusalError as refused:
                write_message(self.writer, error(request_id, REQUEST_FAILED, refused.message))
                return
            self._gather(changes, seen, text_edits(plan, cache))
        if drifted:
            refusal = self._drifted(drifted, "moved or respelled a unit")
            write_message(self.writer, error(request_id, REQUEST_FAILED, refusal))
            return
        self._forget()
        write_message(self.writer, response(request_id, self._workspace_edit(changes)))

    @staticmethod
    def _gather(
        changes: dict[str, list[dict[str, Any]]],
        seen: set[tuple[str, int, int]],
        found: dict[str, list[dict[str, Any]]],
    ) -> None:
        """Add one project's edits to a rename's, each place once.

        A component linked into two images is in two projects, and both of them mention the
        same characters. Sending that edit twice is not a duplicate an editor tolerates: it is
        two overlapping rewrites of one range.
        """
        for uri, edits in found.items():
            for edit in edits:
                start = edit["range"]["start"]
                where = (uri, start["line"], start["character"])
                if where not in seen:
                    seen.add(where)
                    changes.setdefault(uri, []).append(edit)

    @staticmethod
    def _drifted(drifted: set[Path], changed: str) -> str:
        """Why a rename is refused while a buffer no longer holds what the index found in it,
        naming every such file."""
        names = ", ".join(sorted(path.name for path in drifted))
        verb = "has" if len(drifted) == 1 else "have"
        return (
            f"{names} {verb} unsaved changes that {changed} this rename would touch; save it "
            "and rename again"
        )
```

In `_actions`, the lines from `reported = context.get("diagnostics", [])` to the end of the loop over the projects become:

```python
        reported = context.get("diagnostics", [])
        # A unit is fixed from the project's units files, and telling which files those are
        # reads every file the description includes. A client asks for actions at every move
        # of the caret, so they are looked for only when it sent a finding about a unit.
        about_units = any(entry.get("code") in UNKNOWN_UNIT for entry in reported)
        offered: list[dict[str, Any]] = []
        for loaded in self._projects_of(path):
            unreadable = self._unreadable(loaded)
            if unreadable is not None:
                raise MessageError(REQUEST_FAILED, unreadable)
            project = unit_project(loaded.path, loaded.unloaded, cache) if about_units else None
            offered.extend(
                actions(index(loaded.workspace), path, document, pointer, cache, reported, project)
            )
```

- [ ] **Step 8: Run the tests**

Run: `python -m pytest tests/test_units.py tests/test_lsp.py tests/test_gui_session.py --no-cov`
Expected: PASS, every existing rename, quick fix and session test unchanged.

- [ ] **Step 9: The Python gate, then commit**

Run: `python -m pytest`, `python -m ruff format --check .`, `python -m ruff check .`, `python -m mypy`. The modules this task touches stay at 100 % line and branch coverage: a branch left uncovered means a case of Step 1 is missing, not that the branch is dead.

```bash
git add src/ddd/analysis.py src/ddd/lsp/navigation.py src/ddd/gui/session.py src/ddd/lsp/units.py src/ddd/lsp/edits.py src/ddd/lsp/server.py tests/test_lsp.py tests/test_units.py
git commit -m "rename a unit everywhere from an editor, merging two spellings into one, and offer to add an unknown unit to the vocabulary or to respell it as a close one"
git push
```

---

### Task 4: The edit engine creates a file

**Files:**
- Modify: `src/ddd/editing.py` (`FileChange`; `apply_changes`; `_edited`, which becomes the public `edited`; new `_created`; `_stage_and_replace`; `_put_back`)
- Modify: `src/ddd/gui/contract.py` (`Change.fingerprint`)
- Modify: `src/ddd/gui/api.py` (`_file_change`'s docstring)
- Modify: `src/ddd/gui/session.py` (imports; `Session.edit`; new `_confined` and `_included`)
- Test: `tests/test_editing.py` (the two `failing` fakes of `TestWritingFiles`; new `created`, `UNITS_FILE`, class `TestCreatingAFile`)
- Test: `tests/test_gui_session.py` (imports; new `adoption`, class `TestCreatingAFile`)
- Test: `tests/test_gui_api.py` (class `TestEdit`, three tests)

**Interfaces:**
- Consumes: `ddd.editing.edit_text`, `_read`, `_keep_access`, `fingerprint`, `INVALID`, `STALE`, `UNWRITABLE`; `ddd.loading.resolve_path`; `ddd.lsp.ranges.Document`; the session's `_source` and `Revision.project`, and its imports as Task 3 leaves them (`LOAD_CHECKS` from `ddd.lsp.navigation`).
- Produces, for Task 5 and the page:

```python
# src/ddd/editing.py
@dataclass(frozen=True, slots=True)
class FileChange:
    path: Path
    fingerprint: str | None  # None: the change creates the file, which must not exist
    operations: tuple[Operation, ...]
    like: Path | None = None  # for a created file, the file whose mode and owner it takes

def edited(pending: FileChange) -> tuple[bytes | None, bytes]  # was _edited; None for a created file

# src/ddd/gui/contract.py
class Change(_Request):
    fingerprint: str | None  # required; null creates the file
```

`Session.edit` passes `like=` the project description for a created file, and refuses as `EditError(INVALID, …)` a created file that is not beside the project description, or that the same edit's change of the description does not leave among its `includes`.

- [ ] **Step 1: The failing tests**

In `tests/test_editing.py`, class `TestWritingFiles`, the fakes of `test_a_failed_write_puts_back_the_files_already_written` and `test_a_file_that_cannot_be_put_back_is_named` take the third parameter `_stage_and_replace` gains, and hand it on:

```python
        def failing(path, data, like):
            if path == b:
                raise OSError("disk full")
            real(path, data, like)
```

```python
        def failing(path, data, like):
            calls.append(path)
            if path == b or calls.count(a) > 1:
                raise OSError("disk full")
            real(path, data, like)
```

At the end of the file:

```python
def created(path: Path, raw: str, like: Path | None = None) -> FileChange:
    return FileChange(path, None, (Operation("set", "", raw),), like)


UNITS_FILE = '{\n  "units": [\n    { "unit": "rpm", "description": "" }\n  ]\n}\n'


class TestCreatingAFile:
    """A change without a fingerprint creates its file: the one a vocabulary's adoption writes."""

    def test_a_created_file_holds_its_one_set_exactly_as_given(self, tmp_path):
        path = tmp_path / "units.ddd.json"
        written = apply_changes([created(path, UNITS_FILE)])
        assert path.read_bytes() == UNITS_FILE.encode("utf-8")
        assert written == {path: fingerprint(UNITS_FILE.encode("utf-8"))}
        assert not list(tmp_path.glob(f"*{STAGING_SUFFIX}"))

    @pytest.mark.parametrize(
        "operations",
        [
            (),
            (Operation("set", "", "{}"), Operation("set", "units", "[]")),
            (Operation("insert", "", "{}"),),
            (Operation("set", "units", '["rpm"]'),),
            (Operation("set", ""),),
        ],
    )
    def test_a_file_is_created_only_whole_by_one_set_at_its_top(self, tmp_path, operations):
        path = tmp_path / "units.ddd.json"
        with pytest.raises(EditError) as refused:
            apply_changes([FileChange(path, None, operations)])
        assert refused.value.code == INVALID
        assert str(refused.value).startswith(str(path))
        assert not path.exists()

    @pytest.mark.parametrize("raw", ["{", '{"units": NaN}', '{"units": [], "units": []}'])
    def test_a_file_is_never_created_holding_what_the_loader_does_not_read(self, tmp_path, raw):
        path = tmp_path / "units.ddd.json"
        with pytest.raises(EditError) as refused:
            apply_changes([created(path, raw)])
        assert refused.value.code == INVALID
        assert not path.exists()

    def test_a_file_that_exists_by_the_time_of_the_edit_is_stale(self, tmp_path):
        path = tmp_path / "units.ddd.json"
        path.write_bytes(b'{"units": ["Nm"]}')
        with pytest.raises(EditError) as refused:
            apply_changes([created(path, UNITS_FILE)])
        assert refused.value.code == STALE
        assert path.read_bytes() == b'{"units": ["Nm"]}'

    def test_a_created_file_is_taken_away_when_a_later_file_fails(self, tmp_path, monkeypatch):
        units = tmp_path / "units.ddd.json"
        project = tmp_path / "p.ddd.json"
        project.write_bytes(b'{"project": {"includes": []}}')
        real = editing._stage_and_replace

        def failing(path, data, like):
            if path == project:
                raise OSError("disk full")
            real(path, data, like)

        monkeypatch.setattr(editing, "_stage_and_replace", failing)
        with pytest.raises(EditError) as refused:
            apply_changes(
                [
                    created(units, UNITS_FILE),
                    change(project, Operation("insert", "project.includes[0]", '"units.ddd.json"')),
                ]
            )
        assert refused.value.code == UNWRITABLE
        assert "put back" in str(refused.value)
        assert not units.exists()
        assert project.read_bytes() == b'{"project": {"includes": []}}'

    def test_a_created_file_takes_the_mode_of_the_file_it_is_like(self, tmp_path):
        like = tmp_path / "p.ddd.json"
        like.write_bytes(b"{}")
        like.chmod(0o640)
        mode = stat.S_IMODE(like.stat().st_mode)
        path = tmp_path / "units.ddd.json"
        apply_changes([created(path, UNITS_FILE, like)])
        assert stat.S_IMODE(path.stat().st_mode) == mode

    def test_a_created_file_is_given_to_the_owner_of_the_file_it_is_like(
        self, tmp_path, monkeypatch
    ):
        """What ``ddd gui`` run as root in its container needs: the units file an adoption
        writes into a checkout mounted from the host belongs to whoever owns the project."""
        given = []
        monkeypatch.setattr(
            editing.os, "chown", lambda _, uid, gid: given.append((uid, gid)), raising=False
        )
        like = tmp_path / "p.ddd.json"
        like.write_bytes(b"{}")
        owner = like.stat()
        apply_changes([created(tmp_path / "units.ddd.json", UNITS_FILE, like)])
        assert given == [(owner.st_uid, owner.st_gid)]

    def test_a_file_created_like_no_file_keeps_the_access_a_new_file_gets(
        self, tmp_path, monkeypatch
    ):
        given = []
        monkeypatch.setattr(editing.os, "chown", lambda *args: given.append(args), raising=False)
        path = tmp_path / "units.ddd.json"
        apply_changes([created(path, UNITS_FILE)])
        assert path.read_bytes() == UNITS_FILE.encode("utf-8")
        assert given == []

    def test_a_file_that_exists_keeps_its_own_mode_whatever_it_is_said_to_be_like(self, tmp_path):
        path = tmp_path / "a.ddd.json"
        path.write_bytes(b'{"a": 1}')
        path.chmod(0o600)
        mode = stat.S_IMODE(path.stat().st_mode)
        like = tmp_path / "p.ddd.json"
        like.write_bytes(b"{}")
        like.chmod(0o644)
        pending = FileChange(
            path, fingerprint(b'{"a": 1}'), (Operation("set", "a", "2"),), like=like
        )
        apply_changes([pending])
        assert stat.S_IMODE(path.stat().st_mode) == mode
```

In `tests/test_gui_session.py`, the imports gain `json`, `stat` and `INVALID`:

```python
import json
import re
import stat
import threading
```

```python
from ddd.editing import (
    INVALID,
    STALE,
    UNREADABLE,
    EditError,
    FileChange,
    Operation,
    fingerprint,
)
```

and, right before `test_the_demo_opens_clean`:

```python
def adoption(project_file: Path, name: str = "units.ddd.json") -> list[FileChange]:
    """What adopting a vocabulary posts: a units file created beside the project, and its name
    appended to the project's includes."""
    includes = json.loads(project_file.read_text(encoding="utf-8"))["project"]["includes"]
    return [
        FileChange(project_file.parent / name, None, (Operation("set", "", '{"units": ["rpm"]}'),)),
        FileChange(
            project_file,
            fingerprint(project_file.read_bytes()),
            (Operation("insert", f"project.includes[{len(includes)}]", json.dumps(name)),),
        ),
    ]


class TestCreatingAFile:
    """An edit creates a file only beside the project description, and only by including it."""

    def test_a_file_the_same_edit_includes_beside_the_project_is_created_and_read(
        self, shared: Path
    ) -> None:
        session = Session(shared.parent)
        session.open(shared)
        units = (shared.parent / "units.ddd.json").resolve()
        revision, written = session.edit(adoption(shared))
        assert units.read_bytes() == b'{"units": ["rpm"]}'
        assert set(written) == {units, shared.resolve()}
        described = {f.path.name: (f.kind, f.loaded) for f in revision.files}
        assert described["units.ddd.json"] == ("units", True)

    def test_a_created_file_takes_the_mode_of_the_project_description(self, shared: Path) -> None:
        shared.chmod(0o640)
        mode = stat.S_IMODE(shared.stat().st_mode)
        session = Session(shared.parent)
        session.open(shared)
        session.edit(adoption(shared))
        assert stat.S_IMODE((shared.parent / "units.ddd.json").stat().st_mode) == mode

    def test_a_file_the_edit_does_not_include_is_not_created(self, shared: Path) -> None:
        session = Session(shared.parent)
        session.open(shared)
        created, _ = adoption(shared)
        with pytest.raises(EditError) as refused:
            session.edit([created])
        assert refused.value.code == INVALID
        assert not (shared.parent / "units.ddd.json").exists()

    def test_a_change_of_the_description_that_leaves_the_file_out_is_not_enough(
        self, shared: Path
    ) -> None:
        session = Session(shared.parent)
        session.open(shared)
        created, _ = adoption(shared)
        renamed = FileChange(
            shared, fingerprint(shared.read_bytes()), (Operation("set", "project.name", '"Q"'),)
        )
        before = shared.read_bytes()
        with pytest.raises(EditError) as refused:
            session.edit([created, renamed])
        assert refused.value.code == INVALID
        assert not (shared.parent / "units.ddd.json").exists()
        assert shared.read_bytes() == before

    def test_a_file_is_created_only_beside_the_project_description(self, shared: Path) -> None:
        session = Session(shared.parent)
        session.open(shared)
        with pytest.raises(EditError) as refused:
            session.edit(adoption(shared, "vocabulary/units.ddd.json"))
        assert refused.value.code == INVALID
        assert not (shared.parent / "vocabulary").exists()

    def test_a_description_changed_on_disk_since_is_stale(self, shared: Path) -> None:
        session = Session(shared.parent)
        session.open(shared)
        edit = adoption(shared)
        shared.write_text(shared.read_text(encoding="utf-8") + " ", encoding="utf-8")
        with pytest.raises(EditError) as refused:
            session.edit(edit)
        assert refused.value.code == STALE
        assert not (shared.parent / "units.ddd.json").exists()
```

In `tests/test_gui_api.py`, class `TestEdit`, right before `test_a_move_carries_its_target_index`:

```python
    def test_a_change_without_a_fingerprint_creates_the_file_the_edit_includes(
        self, api: Api, root: Path
    ) -> None:
        described = root / "p.ddd.json"
        created = {"op": "set", "pointer": "", "raw": '{"units": ["rpm"]}'}
        included = {"op": "insert", "pointer": "project.includes[2]", "raw": '"units.ddd.json"'}
        edit = {
            "changes": [
                {
                    "file": (root / "units.ddd.json").as_posix(),
                    "fingerprint": None,
                    "operations": [created],
                },
                {
                    "file": described.as_posix(),
                    "fingerprint": fingerprint(described.read_bytes()),
                    "operations": [included],
                },
            ]
        }
        reply = post(api, "/api/edit", edit)
        assert reply.status == 200
        assert (root / "units.ddd.json").read_bytes() == b'{"units": ["rpm"]}'
        assert {f["path"] for f in reply.body["files"]} == {
            posix(root, "units.ddd.json"),
            posix(root, "p.ddd.json"),
        }
        files = {Path(f["path"]).name: f for f in get(api, "/api/state").body["files"]}
        assert (files["units.ddd.json"]["kind"], files["units.ddd.json"]["loaded"]) == (
            "units",
            True,
        )

    def test_a_file_the_edit_does_not_include_is_not_created(self, api: Api, root: Path) -> None:
        edit = {
            "changes": [
                {
                    "file": (root / "units.ddd.json").as_posix(),
                    "fingerprint": None,
                    "operations": [{"op": "set", "pointer": "", "raw": '{"units": ["rpm"]}'}],
                }
            ]
        }
        reply = post(api, "/api/edit", edit)
        assert (reply.status, reply.body["error"]) == (409, "invalid")
        assert not (root / "units.ddd.json").exists()

    def test_a_change_that_leaves_its_fingerprint_out_is_a_bad_request(
        self, api: Api, root: Path
    ) -> None:
        """Left out is not ``null``: a page that forgot the fingerprint is not taken to be
        creating the file."""
        edit = unit_edit(api, root, "Hz")
        del edit["changes"][0]["fingerprint"]
        reply = post(api, "/api/edit", edit)
        assert (reply.status, reply.body["error"]) == (400, "bad-request")
```

- [ ] **Step 2: Run them and watch them fail**

Run: `python -m pytest tests/test_editing.py tests/test_gui_session.py tests/test_gui_api.py --no-cov`
Expected: FAIL. The two `TestWritingFiles` fakes with `TypeError: … failing() missing 1 required positional argument: 'like'`; `tests/test_editing.py::TestCreatingAFile` with `AssertionError: assert 'stale' == 'invalid'` (the engine reads the file that is not there), `TypeError: FileChange.__init__() takes 4 positional arguments but 5 were given` and `… got an unexpected keyword argument 'like'`; `tests/test_gui_session.py::TestCreatingAFile` with `NotInProjectError: …/units.ddd.json is not a description file of the open project`; the first two new `TestEdit` tests with `400 bad-request`, `changes[0].fingerprint: Input should be a valid string`. `test_a_change_that_leaves_its_fingerprint_out_is_a_bad_request` passes already: it pins that `null` and a fingerprint left out stay two things.

- [ ] **Step 3: The engine creates a file**

In `src/ddd/editing.py`, `FileChange` becomes:

```python
@dataclass(frozen=True, slots=True)
class FileChange:
    """The operations for one file, and the fingerprint of the bytes they were computed for."""

    path: Path
    fingerprint: str | None
    """``None`` for a change that creates its file, which must not exist yet: one ``set`` of the
    whole document, at the pointer ``""``."""

    operations: tuple[Operation, ...]
    like: Path | None = None
    """The file a created file takes its mode from, and its owner and group where this process
    may give it them; a file that exists keeps its own, whatever this says."""
```

`apply_changes` and `_edited` are replaced by these three, in this order:

```python
def apply_changes(changes: Sequence[FileChange]) -> dict[Path, str]:
    """Make every change or none of them, and hand back each file's new fingerprint.

    Every file is checked against its fingerprint and edited in memory before anything is
    written, so a refusal leaves every file as it was. Each write is staged beside its file and
    renamed onto it; when one fails, the files already written are written back from the bytes
    read before the edit, a file the edit created is taken away again, and the refusal names
    any that could not be.
    """
    staged: list[tuple[FileChange, bytes | None, bytes]] = []
    for pending in changes:
        if any(done.path == pending.path for done, _, _ in staged):
            raise EditError(INVALID, f"{pending.path} is named twice in one edit")
        original, new = edited(pending)
        staged.append((pending, original, new))
    written: list[tuple[Path, bytes | None]] = []
    for pending, original, new in staged:
        # A file that exists keeps its own access; one the edit creates takes the access of the
        # file it is like, or the access any new file gets when it is like none.
        like = pending.path if original is not None else pending.like
        try:
            _stage_and_replace(pending.path, new, like)
        except OSError as error:
            lost = [done for done, before in written if not _put_back(done, before)]
            outcome = (
                "these could not be put back: " + ", ".join(str(done) for done in lost)
                if lost
                else "the files already written were put back"
            )
            raise EditError(
                UNWRITABLE, f"{pending.path} could not be written ({error}); {outcome}"
            ) from None
        written.append((pending.path, original))
    return {pending.path: fingerprint(new) for pending, _, new in staged}


def edited(pending: FileChange) -> tuple[bytes | None, bytes]:
    """A file's bytes as they are, and as the change leaves them, made in memory and refused as
    :func:`apply_changes` refuses them; ``None`` for the bytes of a file the change creates.

    Public for a caller that has to know what an edit would write before it is made: ``ddd gui``
    lets an edit create a file only when its change of the project description includes that
    file, and asks this - rather than a reading of its own - what the description would say.
    """
    if pending.fingerprint is None:
        return None, _created(pending)
    try:
        original = pending.path.read_bytes()
    except OSError:
        raise EditError(STALE, f"{pending.path} can no longer be read") from None
    if fingerprint(original) != pending.fingerprint:
        raise EditError(STALE, f"{pending.path} changed on disk since it was read")
    mark = codecs.BOM_UTF8 if original.startswith(codecs.BOM_UTF8) else b""
    try:
        text = original[len(mark) :].decode("utf-8")
    except UnicodeDecodeError:
        raise EditError(UNREADABLE, f"{pending.path} is not utf-8") from None
    try:
        changed = edit_text(text, pending.operations)
    except EditError as refusal:
        raise EditError(refusal.code, f"{pending.path}: {refusal}") from None
    return original, mark + changed.encode("utf-8")


def _created(pending: FileChange) -> bytes:
    """The bytes of a file a change creates: its one ``set`` of the whole document, as given.

    As given, because there is no file yet whose layout an edit could follow - whoever plans the
    change lays the document out - and still read by the loader's rule first, so that no file
    ``ddd check`` would refuse to read is ever written. A file already there is somebody's, and
    the change was computed without it: refused as stale, whatever it holds.
    """
    only = pending.operations[0] if len(pending.operations) == 1 else None
    if only is None or (only.op, only.pointer) != ("set", "") or only.raw is None:
        raise EditError(
            INVALID, f"{pending.path} is created whole, by one set at the top of the file"
        )
    _read(only.raw, INVALID, f"{pending.path} would be created holding what DDD does not read")
    if pending.path.exists():
        raise EditError(STALE, f"{pending.path} exists already")
    return only.raw.encode("utf-8")
```

`_stage_and_replace` takes the file whose access the write keeps; `_keep_access` stays as it is:

```python
def _stage_and_replace(path: Path, data: bytes, like: Path | None) -> None:
    """Write ``data`` to ``path`` through a file staged beside it, which takes the access of
    ``like``, the file itself when it exists, before it is renamed into place."""
    staging = path.with_name(path.name + STAGING_SUFFIX)
    try:
        staging.write_bytes(data)
        if like is not None:
            _keep_access(like, staging)
        staging.replace(path)
    except OSError:
        with contextlib.suppress(OSError):
            staging.unlink()
        raise
```

and `_put_back` takes a created file away:

```python
def _put_back(path: Path, data: bytes | None) -> bool:
    """Leave a file as it was before the edit - its bytes written back, or the file taken away
    when the edit created it - and say whether that could be done."""
    try:
        if data is None:
            path.unlink()
        else:
            _stage_and_replace(path, data, path)
    except OSError:
        return False
    return True
```

- [ ] **Step 4: The contract lets a change say it creates its file**

In `src/ddd/gui/contract.py`, `Change.fingerprint` becomes (no default: a change that leaves the fingerprint out is still refused):

```python
    fingerprint: str | None
    """The fingerprint the file was read at; refused as ``stale`` if it has since changed.
    ``None`` creates the file, which must not exist yet, from one ``set`` of its whole document
    at the pointer ``""``."""
```

In `src/ddd/gui/api.py`, `_file_change` already hands `change.fingerprint` on as it is; its docstring says so:

```python
def _file_change(change: contract.Change) -> FileChange:
    """A validated change, as the session's edit engine takes it: a ``null`` fingerprint stays
    ``None``, the change that creates its file."""
    operations = tuple(Operation(o.op, o.pointer, o.raw, o.to) for o in change.operations)
    return FileChange(Path(change.file), change.fingerprint, operations)
```

- [ ] **Step 5: The session allows the one file an edit may create**

In `src/ddd/gui/session.py`, on top of Task 3 (which deleted the session's own `LOAD_CHECKS` and imports it from `ddd.lsp.navigation`), the imports from `ddd.editing` down become:

```python
from ddd.editing import INVALID, EditError, FileChange, apply_changes, edited, fingerprint
from ddd.ir import DataDictionary
from ddd.loading import parse_json_text, resolve_path
from ddd.lsp.diagnostics import Run, group_findings, run_build, run_project
from ddd.lsp.discovery import BUILD_DIRECTORY_PATTERNS, discover
from ddd.lsp.navigation import LOAD_CHECKS, Index
from ddd.lsp.ranges import Document
```

`Session.edit` becomes:

```python
    def edit(self, changes: Sequence[FileChange]) -> tuple[Revision, dict[Path, str]]:
        """Make an edit of description files of the open project, then analyse it again.

        A change without a fingerprint creates its file, and only the kind of file adopting a
        vocabulary writes: one beside the project description, in an edit whose change of that
        description includes it. Any other is refused before a file is touched.
        """
        with self._lock:
            revision = self._required()
            confined = [_confined(revision, pending, changes) for pending in changes]
            written = apply_changes(confined)
            # After the edit's own write, so the next poll does not take it for somebody else's,
            # and before the analysis, so a save landing while that runs is not taken for seen.
            stamps = _signature(self._signature)
            return self._publish(self._analysed(revision.project), stamps), written
```

and right after `_source`:

```python
def _confined(revision: Revision, pending: FileChange, changes: Sequence[FileChange]) -> FileChange:
    """One change of an edit, its file resolved and allowed: a description file of the open
    project, or a file the edit may create, which takes the access of the project description."""
    if pending.fingerprint is not None:
        return FileChange(_source(revision, pending.path), pending.fingerprint, pending.operations)
    target = pending.path.resolve()
    project = revision.project
    described = next(
        (c for c in changes if c.fingerprint is not None and c.path.resolve() == project), None
    )
    if (
        target.parent != project.parent
        or described is None
        or target not in _included(project, described)
    ):
        raise EditError(
            INVALID,
            f"{pending.path} can be created only beside {project.name}, "
            "by an edit that adds it to the includes there",
        )
    return FileChange(target, None, pending.operations, like=project)


def _included(project: Path, change: FileChange) -> frozenset[Path]:
    """The files the project description's ``includes`` name once ``change`` is made to it, each
    entry resolved as the loader resolves one naming a file.

    Made in memory by the edit engine itself, so a description that changed on disk since the
    change was computed is refused as stale here, as the engine would refuse it. A pattern is
    not expanded: the file it would have to match does not exist yet.
    """
    _, new = edited(FileChange(project, change.fingerprint, change.operations))
    entries = Document(new.decode("utf-8-sig")).value_at("project.includes")
    return frozenset(
        resolve_path(project.parent / entry)
        for entry in (entries if isinstance(entries, list) else [])
        if isinstance(entry, str)
    )
```

- [ ] **Step 6: Run the tests**

Run: `python -m pytest tests/test_editing.py tests/test_gui_session.py tests/test_gui_api.py tests/test_gui_contract.py --no-cov`
Expected: PASS.

- [ ] **Step 7: The Python gate, the page's types, then commit**

Run: `python -m pytest`, `python -m ruff format --check .`, `python -m ruff check .`, `python -m mypy`. `src/ddd/editing.py` and `src/ddd/gui/session.py` stay at 100 % line and branch coverage.

Then the page, which writes a `Change` in `editOf`: `cd gui && npm run schemas && npm run typecheck`. `grep -c "fingerprint: string | null" src/generated/api.ts` prints 1 (`Change`'s), and part 1's page type-checks unchanged.

```bash
git add src/ddd/editing.py src/ddd/gui/contract.py src/ddd/gui/api.py src/ddd/gui/session.py tests/test_editing.py tests/test_gui_session.py tests/test_gui_api.py
git commit -m "let an edit create the file it includes beside the project description, staged like any write, taken away again when a later file fails, and given the description's mode and owner"
git push
```

---

### Task 5: The endpoints

**Files:**
- Create: `src/ddd/project_units.py`
- Modify: `src/ddd/gui/contract.py` (`__all__`; new `ProjectUnit`; `UnitsReply`; new section `GET /api/unit` with `UnitEntry`, `UnitPlace`, `UnitReply`; `PlannedOperation`; `PlannedChange`; new section `GET /api/unit-plan` with `PlanReply`; `_ENDPOINTS`)
- Modify: `src/ddd/variables.py` (`Planned`; `_planned` and `_hunks` become the public `planned` and `hunks`; `preview`'s call)
- Modify: `src/ddd/gui/api.py` (imports; `UNIT_PLANS`; `Api._file`'s check; `Api._units`; new `Api._unit`, `Api._unit_plan`; `Api._settle`'s `raw` and its answer; `_ROUTES`; new `_unit_plan_of`, `_planned_changes`)
- Modify: `src/ddd/gui/server.py` (`_Handler._route`: the query handed to the api keeps blank values)
- Modify: `gui/src/lib/units.test.ts` (`FREE`, `VOCABULARY`), `gui/src/stories/fixtures.ts` (`FREE_UNITS`, `VOCABULARY`)
- Test: `tests/test_gui_api.py`, `tests/test_gui_server.py` (new class `TestBlankParameters`)

**Interfaces:**
- Consumes: Task 1's `UnitSite`, `Index.units`, `Index.vocabulary`, `units_in_use(built)`; Task 2's `UnitProject`, `PlannedEdit` (`path`, `operations`, `creates`), `UnitPlan`, `UnitRefusalError` (`code`, `message`), `unit_project`, `rename_unit`, `add_unit`, `describe_unit`, `remove_unit`, `adopt_units`; the revision's `SourceFile.loaded`, whose `False` is Task 3's `LOAD_CHECKS` notion of a file that did not load, passed as `unread`; Task 4's `FileChange.fingerprint: str | None` and the session's created file; part 1's `declarations_of`, `vocabulary_of`, `Planned`, `Hunk`, `_undeclared`, `_finding`, `REFUSALS`.
- Produces, for Tasks 6 to 8 (the skeleton's contract, field for field, and the page types `npm run schemas` generates from it):

```python
class ProjectUnit(_Frozen):
    unit: str
    description: str | None
    files: tuple[str, ...]
    variables: int
    types: int
    members: int
    findings: int

class UnitsReply(_Frozen):
    revision: int
    vocabulary: tuple[VocabularyUnit, ...] | None
    used: tuple[UsedUnit, ...]
    units: tuple[ProjectUnit, ...]  # by spelling
    adoptable: int | None

class UnitEntry(_Frozen):
    file: str
    pointer: str

class UnitPlace(_Frozen):
    path: str
    pointer: str
    kind: Literal["variable", "type", "member"]
    name: str
    component: str | None
    role: str | None

class UnitReply(_Frozen):  # GET /api/unit?name=
    revision: int
    unit: str
    description: str | None
    entries: tuple[UnitEntry, ...]
    sites: tuple[UnitPlace, ...]
    findings: tuple[Finding, ...]

class PlannedOperation(_Frozen):
    op: Literal["set", "remove", "insert"]
    pointer: str
    raw: str | None

class PlannedChange(_Frozen):
    file: str
    fingerprint: str | None  # None: the file is created
    operations: tuple[PlannedOperation, ...]
    hunks: tuple[Hunk, ...]

class PlanReply(_Frozen):  # GET /api/unit-plan?action=…
    revision: int
    changes: tuple[PlannedChange, ...]
```

`GET /api/unit-plan` takes `action` (`rename`, `add`, `describe`, `remove`, `adopt`), `unit` (not for `adopt`), `to` (for `rename`) and `description` (for `describe`). The server hands the api blank values: `description=` asks for the empty description, and `to=` for an empty spelling, which the plan refuses `invalid`. A missing parameter, an empty `unit` or an unknown `action` is `400 bad-request`; a `UnitRefusalError` is `409` with its code, or `404` for `not-found`; an engine refusal of the preview is `409` for one of `REFUSALS`, else `500`.

- [ ] **Step 1: The failing tests**

In `tests/test_gui_api.py`, the `conftest` import becomes:

```python
from conftest import (
    EXAMPLES,
    component,
    declare,
    project,
    scalar_type,
    struct_type,
    types,
    value_member,
    write_tree,
)
```

Right after `HALF_SAVED`:

```python
# One unit stated three ways: by a variable, by a scalar type and by a structure member.
STATED_THREE_WAYS = {
    "p.ddd.json": project("P", "types.ddd.json", "a.ddd.json"),
    "types.ddd.json": types(
        scalar_type("Speed_t", unit="rpm"),
        struct_type("Sample_t", value_member("speed", unit="rpm")),
    ),
    "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
}

# A vocabulary listing one unit twice, which the loader reports as `duplicate-unit`.
LISTED_TWICE = {
    "p.ddd.json": project("P", "units.ddd.json", "a.ddd.json"),
    "units.ddd.json": {"units": ["rpm", "rpm"]},
    "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
}
```

Right after `posix`:

```python
def picked(body: dict[str, Any]) -> dict[str, Any]:
    """What part 1's picker reads of ``GET /api/units``: the Units tab's rows and adoption left
    out, which the tests of the tab assert on their own."""
    return {key: body[key] for key in ("revision", "vocabulary", "used")}
```

In `TestUnits.test_without_a_vocabulary_the_units_in_use_are_answered`, `TestTheDemo.test_without_a_vocabulary_the_units_in_use_are_answered_most_used_first` and `TestTheVocabulary.test_the_vocabulary_is_answered_described_beside_the_units_in_use`, the line

```python
        assert get(api, "/api/units").body == {
```

becomes

```python
        assert picked(get(api, "/api/units").body) == {
```

with the expected body under it as it stands.

Right after `with_unit`:

```python
def findings_of(state: dict[str, Any]) -> set[tuple[str, str, str, str]]:
    """What a state reports, each finding by its file, check, place and sentence."""
    return {(f["file"], f["check"], f["pointer"], f["message"]) for f in state["findings"]}
```

In `TestTheDemo`, after its last test:

```python
    def test_the_units_tab_lists_every_unit_in_use_and_how_many_adopting_would_list(
        self, demo: tuple[Api, Path]
    ) -> None:
        api, _ = demo
        body = get(api, "/api/units").body
        assert body["adoptable"] == 5
        assert [
            (u["unit"], u["variables"], u["types"], u["members"], u["findings"])
            for u in body["units"]
        ] == [
            ("%", 5, 0, 0, 0),
            ("Hz", 3, 0, 0, 0),
            ("V", 2, 0, 0, 0),
            ("degC", 2, 0, 0, 0),
            ("ms", 1, 0, 0, 0),
        ]
        assert all((u["description"], u["files"]) == (None, []) for u in body["units"])

    def test_adopting_writes_the_units_file_includes_it_and_reports_nothing_more(
        self, demo: tuple[Api, Path]
    ) -> None:
        api, root = demo
        before = contents(root)
        reported = findings_of(get(api, "/api/state").body)
        preview = get(api, "/api/unit-plan", action="adopt").body
        assert contents(root) == before
        described, created = preview["changes"]
        assert (described["file"], created["file"]) == (
            posix(root, "demo.ddd.json"),
            posix(root, "units.ddd.json"),
        )
        assert described["fingerprint"] == fingerprint(before["demo.ddd.json"])
        assert created["fingerprint"] is None
        assert applied(api, preview).status == 200
        text = (root / "units.ddd.json").read_text(encoding="utf-8")
        assert created["hunks"] == [{"line": 1, "before": [], "after": text.splitlines()}]
        listed = json.loads(text)["units"]
        assert sorted(entry["unit"] for entry in listed) == ["%", "Hz", "V", "degC", "ms"]
        assert all(entry["description"] == "" for entry in listed)
        last = b'"subsystems/logging/logging.ddd.json"'
        assert contents(root) == {
            **before,
            "demo.ddd.json": before["demo.ddd.json"].replace(
                last, last + b',\n      "units.ddd.json"'
            ),
            "units.ddd.json": text.encode("utf-8"),
        }
        assert findings_of(get(api, "/api/state").body) <= reported
        units = get(api, "/api/units").body
        assert units["adoptable"] is None
        assert {u["unit"]: u["files"] for u in units["units"]}["Hz"] == [
            posix(root, "units.ddd.json")
        ]
```

In `TestTheVocabulary`, after its last test:

```python
    def test_the_units_tab_lists_the_vocabulary_beside_what_states_each_unit(
        self, vocabulary: tuple[Api, Path]
    ) -> None:
        api, root = vocabulary
        body = get(api, "/api/units").body
        listing = [posix(root, "units.ddd.json")]
        assert body["adoptable"] is None
        assert body["units"] == [
            {
                "unit": "Nm",
                "description": "torque, newton metre",
                "files": listing,
                "variables": 0,
                "types": 1,
                "members": 0,
                "findings": 0,
            },
            {
                "unit": "degC",
                "description": "temperature",
                "files": listing,
                "variables": 0,
                "types": 0,
                "members": 0,
                "findings": 0,
            },
            {
                "unit": "kPa",
                "description": "pressure",
                "files": listing,
                "variables": 2,
                "types": 0,
                "members": 0,
                "findings": 0,
            },
            {
                "unit": "rpm",
                "description": "rotational speed, revolutions per minute",
                "files": listing,
                "variables": 1,
                "types": 0,
                "members": 0,
                "findings": 0,
            },
        ]

    def test_a_unit_a_type_states_is_answered_with_its_entry_and_the_type(
        self, vocabulary: tuple[Api, Path]
    ) -> None:
        api, root = vocabulary
        assert get(api, "/api/unit", name="Nm").body == {
            "revision": 1,
            "unit": "Nm",
            "description": "torque, newton metre",
            "entries": [{"file": posix(root, "units.ddd.json"), "pointer": "units[1]"}],
            "sites": [
                {
                    "path": posix(root, self.PUMP),
                    "pointer": "component.types[0].unit",
                    "kind": "type",
                    "name": "Torque_t",
                    "component": None,
                    "role": None,
                }
            ],
            "findings": [],
        }

    def test_a_spelling_drifted_from_outside_merges_into_the_vocabularys_own(
        self, vocabulary: tuple[Api, Path]
    ) -> None:
        api, root = vocabulary
        original = contents(root)
        (root / self.PUMP).write_bytes(with_unit(original[self.PUMP], "PumpSpeed", "RPM"))
        assert api.session.poll() is True
        drifted = {u["unit"]: u for u in get(api, "/api/units").body["units"]}["RPM"]
        assert (drifted["description"], drifted["files"], drifted["findings"]) == (None, [], 1)
        before = contents(root)
        preview = get(api, "/api/unit-plan", action="rename", unit="RPM", to="rpm").body
        assert contents(root) == before
        assert [(c["file"], c["operations"]) for c in preview["changes"]] == [
            (
                posix(root, self.PUMP),
                [
                    {
                        "op": "set",
                        "pointer": "component.interface[0].definition.unit",
                        "raw": '"rpm"',
                    }
                ],
            )
        ]
        assert applied(api, preview).status == 200
        assert contents(root) == original
        units = {u["unit"]: u for u in get(api, "/api/units").body["units"]}
        assert "RPM" not in units
        assert (units["rpm"]["variables"], units["rpm"]["findings"]) == (1, 0)

    def test_a_description_is_written_into_its_entry_and_nowhere_else(
        self, vocabulary: tuple[Api, Path]
    ) -> None:
        api, root = vocabulary
        before = contents(root)
        preview = get(
            api, "/api/unit-plan", action="describe", unit="kPa", description="pressure, kilopascal"
        ).body
        assert contents(root) == before
        assert applied(api, preview).status == 200
        assert contents(root) == {
            **before,
            "units.ddd.json": before["units.ddd.json"].replace(
                b'"pressure"', b'"pressure, kilopascal"'
            ),
        }
        assert get(api, "/api/unit", name="kPa").body["description"] == "pressure, kilopascal"

    def test_a_unit_outside_the_vocabulary_is_added_in_the_form_its_entries_take(
        self, vocabulary: tuple[Api, Path]
    ) -> None:
        api, root = vocabulary
        original = contents(root)
        (root / self.PUMP).write_bytes(with_unit(original[self.PUMP], "ManifoldPressure", "bar"))
        assert api.session.poll() is True
        before = contents(root)
        preview = get(api, "/api/unit-plan", action="add", unit="bar").body
        assert contents(root) == before
        assert applied(api, preview).status == 200
        last = b'{ "unit": "kPa", "description": "pressure" }'
        assert contents(root) == {
            **before,
            "units.ddd.json": before["units.ddd.json"].replace(
                last, last + b',\n    { "unit": "bar", "description": "" }'
            ),
        }
        assert "unknown-unit" not in {f["check"] for f in get(api, "/api/state").body["findings"]}

    def test_a_unit_nothing_states_is_removed_from_the_vocabulary(
        self, vocabulary: tuple[Api, Path]
    ) -> None:
        api, root = vocabulary
        before = contents(root)
        preview = get(api, "/api/unit-plan", action="remove", unit="degC").body
        assert contents(root) == before
        assert applied(api, preview).status == 200
        assert contents(root) == {
            **before,
            "units.ddd.json": before["units.ddd.json"].replace(
                b'    { "unit": "degC", "description": "temperature" },\n', b""
            ),
        }
        assert get(api, "/api/unit", name="degC").status == 404

    def test_a_unit_something_still_states_is_not_removed(
        self, vocabulary: tuple[Api, Path]
    ) -> None:
        api, root = vocabulary
        before = contents(root)
        reply = get(api, "/api/unit-plan", action="remove", unit="rpm")
        assert (reply.status, reply.body["error"]) == (409, "invalid")
        assert contents(root) == before
```

At the end of the file:

```python
class TestUnitsTab:
    """The rows ``GET /api/units`` adds for the Units tab, and what adopting would list."""

    def test_each_unit_in_use_is_a_row_and_adopting_would_list_it(self, api: Api) -> None:
        body = get(api, "/api/units").body
        assert body["units"] == [
            {
                "unit": "rpm",
                "description": None,
                "files": [],
                "variables": 1,
                "types": 0,
                "members": 0,
                "findings": 0,
            }
        ]
        assert body["adoptable"] == 1

    def test_a_unit_is_counted_by_the_variables_types_and_members_stating_it(
        self, tmp_path: Path
    ) -> None:
        (row,) = get(opened(tmp_path, STATED_THREE_WAYS), "/api/units").body["units"]
        assert (row["unit"], row["variables"], row["types"], row["members"]) == ("rpm", 1, 1, 1)

    def test_a_unit_listed_twice_counts_its_findings_on_both_entries_and_its_file_once(
        self, tmp_path: Path
    ) -> None:
        body = get(opened(tmp_path, LISTED_TWICE), "/api/units").body
        assert body["adoptable"] is None
        (row,) = body["units"]
        assert (row["files"], row["findings"]) == ([posix(tmp_path, "units.ddd.json")], 2)

    def test_a_project_the_analysis_could_not_read_has_no_rows_and_nothing_to_adopt(
        self, tmp_path: Path
    ) -> None:
        body = get(unloaded(tmp_path), "/api/units").body
        assert (body["units"], body["adoptable"]) == ([], 0)


class TestUnit:
    def test_every_place_stating_a_unit_is_answered_with_its_variable(
        self, api: Api, root: Path
    ) -> None:
        reply = get(api, "/api/unit", name="rpm")
        assert reply.status == 200
        assert reply.body == {
            "revision": 1,
            "unit": "rpm",
            "description": None,
            "entries": [],
            "sites": [
                {
                    "path": posix(root, name),
                    "pointer": UNIT,
                    "kind": "variable",
                    "name": "Speed",
                    "component": component_name,
                    "role": role,
                }
                for name, component_name, role in (
                    ("a.ddd.json", "A", "produces"),
                    ("b.ddd.json", "B", "reads"),
                )
            ],
            "findings": [],
        }

    def test_a_type_and_a_structure_member_are_places_of_their_unit(self, tmp_path: Path) -> None:
        sites = get(opened(tmp_path, STATED_THREE_WAYS), "/api/unit", name="rpm").body["sites"]
        assert sorted(
            (s["kind"], s["name"], s["pointer"], s["component"], s["role"]) for s in sites
        ) == [
            ("member", "Sample_t.speed", "types[1].members[0].unit", None, None),
            ("type", "Speed_t", "types[0].unit", None, None),
            ("variable", "Speed", UNIT, "A", "produces"),
        ]

    def test_a_variable_its_file_no_longer_declares_there_is_left_out(
        self, api: Api, root: Path
    ) -> None:
        write_tree(root, {"b.ddd.json": component("B", declare("input", "Torque", unit="rpm"))})
        sites = get(api, "/api/unit", name="rpm").body["sites"]
        assert [(s["component"], s["name"]) for s in sites] == [("A", "Speed")]

    def test_a_unit_listed_twice_has_its_findings_on_both_entries(self, tmp_path: Path) -> None:
        body = get(opened(tmp_path, LISTED_TWICE), "/api/unit", name="rpm").body
        units = posix(tmp_path, "units.ddd.json")
        assert body["entries"] == [
            {"file": units, "pointer": "units[0]"},
            {"file": units, "pointer": "units[1]"},
        ]
        assert sorted((f["file"], f["check"], f["pointer"]) for f in body["findings"]) == [
            (units, "duplicate-unit", "units[0]"),
            (units, "duplicate-unit", "units[1]"),
        ]

    def test_a_unit_is_asked_for_by_name(self, api: Api) -> None:
        reply = get(api, "/api/unit")
        assert (reply.status, reply.body["error"]) == (400, "bad-request")

    def test_a_unit_nothing_states_or_lists_is_not_found(self, api: Api) -> None:
        reply = get(api, "/api/unit", name="RPM")
        assert (reply.status, reply.body["error"]) == (404, "not-found")

    def test_a_unit_only_a_file_that_did_not_load_states_is_not_said_to_be_gone(
        self, tmp_path: Path
    ) -> None:
        reply = get(opened(tmp_path, HALF_SAVED), "/api/unit", name="Nm")
        assert (reply.status, reply.body["error"]) == (409, "unreadable")
        assert "b.ddd.json did not load" in reply.body["message"]

    def test_a_project_the_analysis_could_not_read_cannot_say_what_it_states(
        self, tmp_path: Path
    ) -> None:
        reply = get(unloaded(tmp_path), "/api/unit", name="rpm")
        assert (reply.status, reply.body["error"]) == (409, "unreadable")

    def test_a_unit_needs_an_open_project(self, root: Path) -> None:
        reply = get(Api(Session(root)), "/api/unit", name="rpm")
        assert (reply.status, reply.body["error"]) == (409, "no-project")


class TestUnitPlan:
    def test_a_rename_is_previewed_as_the_edit_and_the_lines_it_changes(
        self, api: Api, root: Path
    ) -> None:
        before = contents(root)
        reply = get(api, "/api/unit-plan", action="rename", unit="rpm", to="Hz")
        assert reply.status == 200
        assert contents(root) == before
        assert reply.body["revision"] == 1
        assert [change["file"] for change in reply.body["changes"]] == [
            posix(root, "a.ddd.json"),
            posix(root, "b.ddd.json"),
        ]
        for change in reply.body["changes"]:
            name = Path(change["file"]).name
            lines = before[name].decode("utf-8").splitlines()
            line = next(n for n, text in enumerate(lines, 1) if '"unit": "rpm"' in text)
            assert change["fingerprint"] == fingerprint(before[name])
            assert change["operations"] == [{"op": "set", "pointer": UNIT, "raw": '"Hz"'}]
            assert change["hunks"] == [
                {
                    "line": line,
                    "before": [lines[line - 1]],
                    "after": [lines[line - 1].replace('"rpm"', '"Hz"')],
                }
            ]

    def test_posting_a_rename_changes_the_unit_everywhere_it_is_stated(
        self, api: Api, root: Path
    ) -> None:
        before = contents(root)
        preview = get(api, "/api/unit-plan", action="rename", unit="rpm", to="Hz").body
        assert applied(api, preview).status == 200
        assert contents(root) == {
            **before,
            **{
                name: before[name].replace(b'"unit": "rpm"', b'"unit": "Hz"')
                for name in ("a.ddd.json", "b.ddd.json")
            },
        }
        assert get(api, "/api/unit", name="rpm").status == 404

    @pytest.mark.parametrize(
        "query",
        [
            {},
            {"action": "merge", "unit": "rpm"},
            {"action": "rename", "unit": "rpm"},
            {"action": "rename", "to": "Hz"},
            {"action": "describe", "unit": "rpm"},
            {"action": "remove", "unit": ""},
        ],
    )
    def test_a_missing_or_unknown_parameter_is_a_bad_request(
        self, api: Api, query: dict[str, str]
    ) -> None:
        reply = get(api, "/api/unit-plan", **query)
        assert (reply.status, reply.body["error"]) == (400, "bad-request")

    @pytest.mark.parametrize(
        "query",
        [
            {"action": "rename", "unit": "rpm", "to": "rpm"},
            {"action": "rename", "unit": "rpm", "to": ""},
            {"action": "add", "unit": "rpm"},
        ],
    )
    def test_a_plan_its_rules_refuse_is_invalid_and_writes_nothing(
        self, api: Api, root: Path, query: dict[str, str]
    ) -> None:
        before = contents(root)
        reply = get(api, "/api/unit-plan", **query)
        assert (reply.status, reply.body["error"]) == (409, "invalid")
        assert contents(root) == before

    def test_a_unit_the_project_neither_states_nor_lists_is_not_found(self, api: Api) -> None:
        reply = get(api, "/api/unit-plan", action="rename", unit="Nm", to="rpm")
        assert (reply.status, reply.body["error"]) == (404, "not-found")

    def test_a_rename_while_a_file_does_not_load_is_unreadable_and_names_it(
        self, tmp_path: Path
    ) -> None:
        reply = get(
            opened(tmp_path, HALF_SAVED), "/api/unit-plan", action="rename", unit="rpm", to="Hz"
        )
        assert (reply.status, reply.body["error"]) == (409, "unreadable")
        assert "b.ddd.json" in reply.body["message"]

    def test_a_project_the_analysis_could_not_read_plans_nothing(self, tmp_path: Path) -> None:
        reply = get(unloaded(tmp_path), "/api/unit-plan", action="adopt")
        assert (reply.status, reply.body["error"]) == (409, "unreadable")
        assert reply.body["message"].startswith("p.ddd.json did not load")

    def test_a_preview_the_engine_refuses_is_a_refusal_the_page_can_act_on(
        self, api: Api, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def refuse(*_: object) -> None:
            raise EditError(UNVERIFIED, "does not read back")

        monkeypatch.setattr("ddd.gui.api.previewed", refuse)
        reply = get(api, "/api/unit-plan", action="rename", unit="rpm", to="Hz")
        assert (reply.status, reply.body["error"]) == (409, "unverified")

    def test_planning_needs_an_open_project(self, root: Path) -> None:
        reply = get(Api(Session(root)), "/api/unit-plan", action="adopt")
        assert (reply.status, reply.body["error"]) == (409, "no-project")
```

In `tests/test_gui_server.py`, right before `class TestAProjectWithAFileThatDoesNotParse`:

```python
class TestBlankParameters:
    """A parameter given with no value reaches the api as the empty text: clearing a unit's
    description sends ``description=``. Every other handler answers it as a missing one."""

    @pytest.fixture
    def described(self, tmp_path: Path, pages: Path) -> Iterator[tuple[GuiServer, Path]]:
        """ddd gui serving a project whose vocabulary describes its one unit."""
        root = tmp_path / "described"
        write_tree(
            root,
            {
                "p.ddd.json": project("P", "units.ddd.json", "a.ddd.json"),
                "units.ddd.json": {"units": [{"unit": "rpm", "description": "rotational speed"}]},
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
            },
        )
        session = Session(root)
        session.open(root / "p.ddd.json")
        for server in serving(Api(session, root / "p.ddd.json", wait_seconds=0.05), pages):
            yield server, root.resolve()

    def test_an_empty_description_clears_the_units_description(self, described) -> None:
        server, root = described
        plan = answered(server, "GET", "/api/unit-plan?action=describe&unit=rpm&description=")
        (change,) = plan["changes"]
        assert change["operations"] == [
            {"op": "set", "pointer": "units[0].description", "raw": '""'}
        ]
        edit = {"changes": [{key: change[key] for key in ("file", "fingerprint", "operations")}]}
        answered(server, "POST", "/api/edit", edit)
        units = json.loads((root / "units.ddd.json").read_text(encoding="utf-8"))["units"]
        assert units == [{"unit": "rpm", "description": ""}]

    @pytest.mark.parametrize(
        "path",
        [
            "/api/variable?name=",
            "/api/unit?name=",
            "/api/file?path=",
            "/api/settle?name=&key=unit",
            "/api/unit-plan?action=",
            "/api/unit-plan?action=rename&unit=&to=rpm",
        ],
    )
    def test_any_other_blank_parameter_is_refused_as_a_missing_one(self, server, path) -> None:
        assert answered(server, "GET", path, status=400)["error"] == "bad-request"

    def test_a_blank_raw_takes_the_key_out_as_a_missing_one_does(self, server) -> None:
        changes = answered(server, "GET", "/api/settle?name=Speed&key=unit&raw=")["changes"]
        assert [change["operations"] for change in changes] == [
            [{"op": "remove", "pointer": "component.interface[0].definition.unit", "raw": None}]
        ]
```

- [ ] **Step 2: Run them and watch them fail**

Run: `python -m pytest tests/test_gui_api.py tests/test_gui_server.py --no-cov`
Expected: FAIL. The panel and the plans answer `404 not-found`, `/api/unit is not part of the api` (and `/api/unit-plan`), so the tests expecting `200`, `400` or `409` fail on the status and the rest with `KeyError: 'sites'` or `'changes'`; the table's tests fail with `KeyError: 'units'` and `KeyError: 'adoptable'`. The three `picked` assertions pass. In `TestBlankParameters`, whatever reaches `/api/unit` or `/api/unit-plan` fails the same way; the blank parameters of part 1's endpoints (`/api/variable?name=`, `/api/file?path=`, `/api/settle?name=&key=unit`) and the blank `raw` pass already - they pin today's answers, which Step 6 keeps.

- [ ] **Step 3: The contract**

In `src/ddd/gui/contract.py`, `__all__` gains five names, in the order ruff's RUF022 keeps:

```python
    "Operation",
    "PlanReply",
    "PlannedChange",
    "PlannedOperation",
    "ProjectUnit",
    "RefusedBuild",
    "SessionInfo",
    "SettleReply",
    "SourceFile",
    "State",
    "UnitEntry",
    "UnitPlace",
    "UnitReply",
    "UnitsReply",
    "UsedUnit",
```

In the `GET /api/units` section, `UnitsReply` is replaced by these two, and a section for `GET /api/unit` follows them:

```python
class ProjectUnit(_Frozen):
    """One row of the Units tab: a spelling the project states or its vocabulary lists."""

    unit: str
    """The spelling, exactly: ``rpm`` and ``RPM`` are two units."""

    description: str | None
    """What the vocabulary says it means, or ``None`` outside the vocabulary, without one, or
    for an entry that is a spelling alone."""

    files: tuple[str, ...]
    """Absolute, posix-separated paths of the units files listing it; empty outside the
    vocabulary."""

    variables: int
    """How many variables state it."""

    types: int
    """How many scalar types state it."""

    members: int
    """How many structure members state it."""

    findings: int
    """How many ``unknown-unit`` and ``duplicate-unit`` findings are filed on the places stating
    it and the entries listing it."""


class UnitsReply(_Frozen):
    """What ``GET /api/units`` answers: the project's declared vocabulary, its units in use, and
    the Units tab's rows."""

    revision: int
    """The revision this answer was read from."""

    vocabulary: tuple[VocabularyUnit, ...] | None
    """The units the project's units files declare, or ``None`` when it has none, which keeps
    its units free."""

    used: tuple[UsedUnit, ...]
    """Every unit in use, most used first."""

    units: tuple[ProjectUnit, ...]
    """Every unit the project states or its vocabulary lists, by spelling."""

    adoptable: int | None
    """How many units adopting a vocabulary would list - every unit in use - or ``None`` when
    the project has a units file."""


# --- GET /api/unit --------------------------------------------------------------------------


class UnitEntry(_Frozen):
    """One entry of the vocabulary listing a unit."""

    file: str
    """Absolute, posix-separated path of the units file."""

    pointer: str
    """Dotted path of the entry inside that file, ``units[i]``."""


class UnitPlace(_Frozen):
    """One place a unit is stated: a variable's declaration, a scalar type or a structure member."""

    path: str
    """Absolute, posix-separated path of the file stating it."""

    pointer: str
    """Dotted path of the unit's own string inside that file."""

    kind: Literal["variable", "type", "member"]
    """What states it."""

    name: str
    """The variable's name, the type's, or ``Type.member`` for a structure member."""

    component: str | None
    """The component declaring the variable; ``None`` for a type or a member."""

    role: str | None
    """What that component does with the variable - ``produces``, ``reads`` or ``local`` - by the
    declaration's scope; ``None`` for a type or a member."""


class UnitReply(_Frozen):
    """What ``GET /api/unit`` answers: one unit's panel."""

    revision: int
    """The revision this answer was read from."""

    unit: str
    """The unit named in the request."""

    description: str | None
    """What the vocabulary says it means, or ``None`` outside the vocabulary, without one, or for
    an entry that is a spelling alone."""

    entries: tuple[UnitEntry, ...]
    """Every vocabulary entry listing it; more than one is a ``duplicate-unit``."""

    sites: tuple[UnitPlace, ...]
    """Every place stating it, in the order the navigation index recorded them."""

    findings: tuple[Finding, ...]
    """Every ``unknown-unit`` and ``duplicate-unit`` finding filed on one of its places or
    entries."""
```

In the `GET /api/settle` section, `PlannedOperation` and `PlannedChange` become:

```python
class PlannedOperation(_Frozen):
    """One change at one pointer, as a preview comes to it."""

    op: Literal["set", "remove", "insert"]
    """Which operation this is: a settlement sets and removes, and a unit's plan inserts too."""

    pointer: str
    """Dotted path to the value this operation acts on."""

    raw: str | None
    """The json text ``set`` writes, or ``None`` for ``remove``."""
```

```python
class PlannedChange(_Frozen):
    """The edit of one file a preview comes to, and the lines it changes."""

    file: str
    """Absolute, posix-separated path of the file this change is made to."""

    fingerprint: str | None
    """What the file was read at, which ``POST /api/edit`` checks; ``None`` for a file the
    change creates."""

    operations: tuple[PlannedOperation, ...]
    """The operations to apply to the file, in order."""

    hunks: tuple[Hunk, ...]
    """The lines the operations change; the page drops these and posts the rest to
    ``POST /api/edit``."""
```

and right after `SettleReply`:

```python
# --- GET /api/unit-plan ---------------------------------------------------------------------


class PlanReply(_Frozen):
    """What ``GET /api/unit-plan`` answers: the preview of one change of the project's units."""

    revision: int
    """The revision this preview was computed from."""

    changes: tuple[PlannedChange, ...]
    """One per file, sorted by path; a file the change creates has no fingerprint, and one hunk
    at line 1 that is the whole of it."""
```

`_ENDPOINTS` ends:

```python
    (UnitsReply, "serialization"),
    (SettleReply, "serialization"),
    (UnitReply, "serialization"),
    (PlanReply, "serialization"),
)
```

- [ ] **Step 4: A preview of a file that is created**

In `src/ddd/variables.py`, `Planned` becomes:

```python
@dataclass(frozen=True, slots=True)
class Planned:
    """The edit of one file a preview comes to, and the lines it changes."""

    path: Path
    fingerprint: str | None
    """What the analysis read the file at, which the edit is checked against; ``None`` for a
    file the change creates."""

    operations: tuple[Operation, ...]
    hunks: tuple[Hunk, ...]
```

`_planned` and `_hunks`, at the end of the module, are taken out, and right after `preview` come the same two, public for `ddd.project_units`, with docstrings:

```python
def planned(
    path: Path, operations: tuple[Operation, ...], fingerprints: Mapping[Path, str]
) -> Planned:
    """The edit of one file the analysis read, and the lines it changes, made in memory.

    The file carries the fingerprint the analysis read it at, from ``fingerprints`` (keyed by
    resolved path): a file the analysis did not read, or that can no longer be read as utf-8,
    is refused as unreadable rather than previewed from bytes nobody analysed.
    """
    stamp = fingerprints.get(path.resolve())
    if stamp is None:
        raise EditError(UNREADABLE, f"{path} is not a file the last analysis read")
    try:
        text = path.read_bytes().removeprefix(codecs.BOM_UTF8).decode("utf-8")
    except (OSError, UnicodeDecodeError):
        raise EditError(UNREADABLE, f"{path} can no longer be read as utf-8") from None
    return Planned(path, stamp, operations, hunks(text, edit_text(text, operations)))


def hunks(before: str, after: str) -> tuple[Hunk, ...]:
    """The lines a change replaces in a text, each run of them numbered as the text stood."""
    old, new = before.splitlines(), after.splitlines()
    matcher = difflib.SequenceMatcher(a=old, b=new, autojunk=False)
    return tuple(
        Hunk(first + 1, tuple(old[first:last]), tuple(new[start:end]))
        for tag, first, last, start, end in matcher.get_opcodes()
        if tag != "equal"
    )
```

`preview`'s last statement calls the public name:

```python
    return tuple(
        planned(path, tuple(made), fingerprints) for path, made in sorted(operations.items())
    )
```

- [ ] **Step 5: Write `src/ddd/project_units.py`**

```python
"""A project's units as the Units tab of ``ddd gui`` shows them, and what changing one takes.

Transport-neutral, like :mod:`ddd.variables`: nothing here knows about http or the session. Where
a unit is stated and which vocabulary entries list it is the navigation index's own record
(:attr:`ddd.lsp.navigation.Index.units` and :attr:`~ddd.lsp.navigation.Index.vocabulary`), and
every change is planned by :mod:`ddd.lsp.units`, beside the language server's rename, so that the
page and an editor cannot disagree about what renaming a unit reaches. What this adds is what a
page needs around the two: the table's rows, one unit's places with the component and the role
of each variable stating it, the findings that are the unit's own, and the edit a plan comes to
with the lines it changes, computed without writing anything.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from ddd.diagnostics import Diagnostic
from ddd.lsp.navigation import Index, Site, UnitSite
from ddd.lsp.ranges import Document, read
from ddd.lsp.units import UnitPlan
from ddd.variables import Planned, declarations_of, hunks, planned

UNIT_CHECKS: Final = frozenset({"unknown-unit", "duplicate-unit"})
"""The findings that are a unit's own: stated outside the vocabulary, or listed in it twice."""


@dataclass(frozen=True, slots=True)
class UnitRow:
    """One unit as the Units tab lists it."""

    unit: str
    description: str | None
    """What the vocabulary says it means, or ``None`` outside it or for a spelling alone."""

    files: tuple[Path, ...]
    """The units files listing it, each once, in the index's order; empty outside the
    vocabulary."""

    variables: int
    types: int
    members: int
    findings: int
    """How many of its own findings - ``unknown-unit`` and ``duplicate-unit`` - are filed."""


@dataclass(frozen=True, slots=True)
class Place:
    """One place a unit is stated, as its panel lists it."""

    stated: UnitSite
    component: str | None
    """The component declaring the variable; ``None`` for a type or a member."""

    role: str | None
    """``produces``, ``reads`` or ``local`` for a variable; ``None`` for a type or a member."""


def unit_rows(
    built: Index, findings: Iterable[tuple[Path, Diagnostic]], cache: dict[Path, Document]
) -> tuple[UnitRow, ...]:
    """Every unit the project states or its vocabulary lists, by spelling, with how many
    variables, types and structure members state it and how many of its own findings are filed.

    Counted from the index's record as it stands, the way the picker counts the units in use:
    a variable several components declare counts once, and so does a type or a member.
    """
    own = [(file, finding) for file, finding in findings if finding.check in UNIT_CHECKS]
    return tuple(
        UnitRow(
            unit=unit,
            description=description_of(built, unit, cache),
            files=tuple(dict.fromkeys(entry.path for entry in built.vocabulary.get(unit, ()))),
            variables=_stating(built, unit, "variable"),
            types=_stating(built, unit, "type"),
            members=_stating(built, unit, "member"),
            findings=sum(1 for file, finding in own if located_on_unit(built, unit, file, finding)),
        )
        for unit in sorted(built.units.keys() | built.vocabulary.keys())
    )


def description_of(built: Index, unit: str, cache: dict[Path, Document]) -> str | None:
    """What the vocabulary says ``unit`` means: the description of the first entry listing it,
    read from its file; ``None`` outside the vocabulary and for an entry that is a spelling
    alone."""
    first = next(iter(built.vocabulary.get(unit, ())), None)
    if first is None:
        return None
    described = read(first.path, cache).value_at(f"{first.pointer}.description")
    return described if isinstance(described, str) else None


def places_of(built: Index, unit: str, cache: dict[Path, Document]) -> tuple[Place, ...]:
    """Every place the index recorded stating ``unit``, in the order it recorded them.

    A variable comes with its component and its role as :func:`ddd.variables.declarations_of`
    reads them, and a variable its file no longer declares where the index recorded it is left
    out, as that function leaves it out: the file changed since the analysis, and the next
    revision lists it where it went.
    """
    found: list[Place] = []
    for stated in built.units.get(unit, ()):
        if stated.kind != "variable":
            found.append(Place(stated, None, None))
            continue
        definition = Site(stated.site.path, stated.site.pointer.removesuffix(".unit"))
        declared = next(
            (d for d in declarations_of(built, stated.name, cache) if d.site == definition), None
        )
        if declared is not None:
            found.append(Place(stated, declared.component, declared.role))
    return tuple(found)


def located_on_unit(built: Index, unit: str, file: Path, finding: Diagnostic) -> bool:
    """Whether a finding shown on ``file`` is one of ``unit``'s own: an ``unknown-unit`` or a
    ``duplicate-unit`` filed on a place stating it or on an entry listing it."""
    location = finding.location
    if location is None or finding.check not in UNIT_CHECKS:
        return False
    shown = file.resolve()
    return any(
        site.pointer == location.pointer and site.path.resolve() == shown
        for site in (
            *(stated.site for stated in built.units.get(unit, ())),
            *built.vocabulary.get(unit, ()),
        )
    )


def adoptable(built: Index | None, has_vocabulary: bool) -> int | None:
    """How many units adopting a vocabulary would list - every unit in use - or ``None`` when
    the project has a units file already, and so nothing to adopt."""
    if has_vocabulary:
        return None
    return 0 if built is None else len(built.units)


def previewed(plan: UnitPlan, fingerprints: Mapping[Path, str]) -> tuple[Planned, ...]:
    """The edit a plan comes to, file by file in the plan's order, and the lines it changes in
    each - made by the edit engine in memory and never written.

    A file the plan changes carries the fingerprint the analysis read it at, from
    ``fingerprints`` (keyed by resolved path), exactly as :func:`ddd.variables.preview` has it.
    A file the plan creates has none - ``POST /api/edit`` creates a file for a change without
    one - and its one hunk is the whole file, at line 1.
    """
    return tuple(
        Planned(edit.path, None, edit.operations, hunks("", edit.operations[0].raw or ""))
        if edit.creates
        else planned(edit.path, edit.operations, fingerprints)
        for edit in plan.edits
    )


def _stating(built: Index, unit: str, kind: str) -> int:
    """How many variables, types or members - by name, each once - state ``unit``."""
    return len({stated.name for stated in built.units.get(unit, ()) if stated.kind == kind})
```

- [ ] **Step 6: The handlers**

In `src/ddd/gui/api.py`, the imports from `ddd.lsp.edits` down become:

```python
from ddd.lsp.edits import PROPAGATED_KEYS, settle
from ddd.lsp.navigation import Index
from ddd.lsp.ranges import Document, read
from ddd.lsp.units import (
    UnitPlan,
    UnitProject,
    UnitRefusalError,
    add_unit,
    adopt_units,
    describe_unit,
    remove_unit,
    rename_unit,
    unit_project,
)
from ddd.project_units import (
    adoptable,
    description_of,
    located_on_unit,
    places_of,
    previewed,
    unit_rows,
)
from ddd.variables import (
    Declared,
    Planned,
    declarations_of,
    located_on,
    preview,
    refusal,
    units_in_use,
    vocabulary_of,
)
```

Right after `REFUSALS`:

```python
UNIT_PLANS: Final[Mapping[str, tuple[str, ...]]] = {
    "rename": ("unit", "to"),
    "add": ("unit",),
    "describe": ("unit", "description"),
    "remove": ("unit",),
    "adopt": (),
}
"""The changes ``GET /api/unit-plan`` previews, each with the parameters it takes besides
``action``."""
```

`Api._units` is replaced by these three. `_unit_plan` passes `unit_project` the files the revision shows as not loaded (`SourceFile.loaded is False`), which is what the language server passes as Task 3's `Loaded.unloaded`: a units file listing a unit twice still loads, so a rename of that unit reaches both entries.

```python
    def _units(self, query: Query, body: bytes | None) -> Reply:
        revision = self._opened()
        cache: dict[Path, Document] = {}
        vocabulary = vocabulary_of(
            [read(file.path, cache) for file in revision.files if file.kind == "units"]
        )
        built = revision.index
        used = () if built is None else units_in_use(built)
        rows = (
            ()
            if built is None
            else unit_rows(built, [(f.file, f.diagnostic) for f in revision.findings], cache)
        )
        return Reply(
            200,
            contract.UnitsReply(
                revision=revision.number,
                vocabulary=None
                if vocabulary is None
                else [{"unit": unit, "description": text} for unit, text in vocabulary],
                used=[{"unit": unit, "variables": count} for unit, count in used],
                units=[
                    {
                        "unit": row.unit,
                        "description": row.description,
                        "files": [path.resolve().as_posix() for path in row.files],
                        "variables": row.variables,
                        "types": row.types,
                        "members": row.members,
                        "findings": row.findings,
                    }
                    for row in rows
                ],
                adoptable=adoptable(built, vocabulary is not None),
            ).model_dump(mode="json"),
        )

    def _unit(self, query: Query, body: bytes | None) -> Reply:
        revision = self._opened()
        unit = _single(query.get("name"))
        if not unit:
            return _error(400, "bad-request", "unit takes ?name=")
        built = revision.index
        if built is None or (unit not in built.units and unit not in built.vocabulary):
            return _undeclared(revision, unit)
        cache: dict[Path, Document] = {}
        return Reply(
            200,
            contract.UnitReply(
                revision=revision.number,
                unit=unit,
                description=description_of(built, unit, cache),
                entries=[
                    {"file": entry.path.resolve().as_posix(), "pointer": entry.pointer}
                    for entry in built.vocabulary.get(unit, ())
                ],
                sites=[
                    {
                        "path": place.stated.site.path.resolve().as_posix(),
                        "pointer": place.stated.site.pointer,
                        "kind": place.stated.kind,
                        "name": place.stated.name,
                        "component": place.component,
                        "role": place.role,
                    }
                    for place in places_of(built, unit, cache)
                ],
                findings=[
                    _finding(filed)
                    for filed in revision.findings
                    if located_on_unit(built, unit, filed.file, filed.diagnostic)
                ],
            ).model_dump(mode="json"),
        )

    def _unit_plan(self, query: Query, body: bytes | None) -> Reply:
        revision = self._opened()
        action = _single(query.get("action")) or ""
        takes = UNIT_PLANS.get(action)
        if takes is None:
            return _error(
                400, "bad-request", f"unit-plan takes ?action= one of {', '.join(UNIT_PLANS)}"
            )
        given = {part: value for part in takes if (value := _single(query.get(part))) is not None}
        if len(given) < len(takes) or given.get("unit") == "":
            wanted = " and ".join(f"?{part}=" for part in takes)
            return _error(400, "bad-request", f"{action} takes {wanted}")
        built = revision.index
        if built is None:
            unread = [file.path.name for file in revision.files if not file.loaded]
            return _error(
                409,
                UNREADABLE,
                f"{', '.join(unread) or revision.project.name} did not load, "
                "so no unit of the project can be changed",
            )
        cache: dict[Path, Document] = {}
        project = unit_project(
            revision.project, [file.path for file in revision.files if not file.loaded], cache
        )
        try:
            plan = _unit_plan_of(action, built, project, given, cache)
        except UnitRefusalError as refused:
            status = 404 if refused.code == "not-found" else 409
            return _error(status, refused.code, refused.message)
        stamps = {file.path.resolve(): file.fingerprint for file in revision.files}
        try:
            planned = previewed(plan, stamps)
        except EditError as refused:
            return _error(409 if refused.code in REFUSALS else 500, refused.code, str(refused))
        return Reply(
            200,
            contract.PlanReply(
                revision=revision.number, changes=_planned_changes(planned)
            ).model_dump(mode="json"),
        )
```

`Api._file` refuses a blank `path` as it refuses a missing one - the `400` it answered while the server dropped blank values; only its check changes:

```python
        path = _single(query.get("path"))
        if not path:
            return _error(400, "bad-request", "file takes ?path=")
```

`Api._settle`'s first statement after `revision = self._opened()`, `name, key, raw = (...)`, becomes:

```python
        name, key = (_single(query.get(part)) for part in ("name", "key"))
        # A blank ``raw`` is none, as a missing one: the key goes from every declaration.
        raw = _single(query.get("raw")) or None
```

and it answers through the same helper, its `return` becoming:

```python
        return Reply(
            200,
            contract.SettleReply(
                revision=revision.number, changes=_planned_changes(planned)
            ).model_dump(mode="json"),
        )
```

`_ROUTES` ends:

```python
    "/api/settle": ("GET", Api._settle),
    "/api/unit": ("GET", Api._unit),
    "/api/unit-plan": ("GET", Api._unit_plan),
}
```

and right after `_undeclared`:

```python
def _unit_plan_of(
    action: str,
    built: Index,
    project: UnitProject,
    given: Mapping[str, str],
    cache: dict[Path, Document],
) -> UnitPlan:
    """The plan ``action`` names, over the parameters :data:`UNIT_PLANS` says it takes."""
    if action == "rename":
        return rename_unit(built, project, given["unit"], given["to"], cache)
    if action == "add":
        return add_unit(built, project, given["unit"], cache)
    if action == "describe":
        return describe_unit(built, project, given["unit"], given["description"], cache)
    if action == "remove":
        return remove_unit(built, project, given["unit"], cache)
    return adopt_units(built, project, cache)


def _planned_changes(planned: Sequence[Planned]) -> list[dict[str, Any]]:
    """A preview's files as the page reads them: the edit of each - posted to ``POST /api/edit``
    as it stands - beside the lines it changes."""
    return [
        {
            "file": entry.path.resolve().as_posix(),
            "fingerprint": entry.fingerprint,
            "operations": [
                {"op": o.op, "pointer": o.pointer, "raw": o.raw} for o in entry.operations
            ],
            "hunks": [{"line": h.line, "before": h.before, "after": h.after} for h in entry.hunks],
        }
        for entry in planned
    ]
```

In `src/ddd/gui/server.py`, `_Handler._route`'s last two lines become:

```python
        # Blank values kept: clearing a unit's description asks for `description=`, which means
        # the empty text, where a parameter left out means nothing was given. Every handler that
        # reads a parameter answers a blank one as it answers a missing one, as it did when
        # blank values were dropped here.
        query = parse_qs(url.query, keep_blank_values=True)
        reply = self._gui.api.handle(method, url.path, query, body)
        self._send_json(reply.status, reply.body)
```

- [ ] **Step 7: Run the tests**

Run: `python -m pytest tests/test_gui_api.py tests/test_gui_server.py tests/test_gui_contract.py tests/test_variables.py --no-cov`
Expected: PASS. `test_every_model_declared_here_has_a_defs_entry` passes because `UnitReply` and `PlanReply` are in `_ENDPOINTS` and reach the three other new models.

- [ ] **Step 8: The page's types, and part 1's replies that lack the new fields**

Run: `cd gui && npm run schemas && npm run typecheck`
Expected: FAIL, four times `TS2739: Type '{ … }' is missing the following properties from type 'UnitsReply': units, adoptable`, at `src/lib/units.test.ts` (`FREE`, `VOCABULARY`) and `src/stories/fixtures.ts` (`FREE_UNITS`, `VOCABULARY`).

In `gui/src/lib/units.test.ts`, `FREE` and `VOCABULARY` become, with a helper before them:

```ts
/** A row of the Units tab, which nothing here reads: a unit stated by variables alone. */
function row(
  unit: string,
  variables: number,
  description: string | null = null,
  files: string[] = [],
): UnitsReply["units"][number] {
  return { unit, description, files, variables, types: 0, members: 0, findings: 0 };
}

const FREE: UnitsReply = {
  revision: 1,
  vocabulary: null,
  used: [
    { unit: "Hz", variables: 4 },
    { unit: "%", variables: 3 },
    { unit: "rpm", variables: 1 },
  ],
  units: [row("%", 3), row("Hz", 4), row("rpm", 1)],
  adoptable: 3,
};
const UNITS_FILE = "C:/w/units.ddd.json";
const VOCABULARY: UnitsReply = {
  revision: 1,
  vocabulary: [
    { unit: "rpm", description: "rotational speed" },
    { unit: "Nm", description: null },
  ],
  used: [{ unit: "rpm", variables: 1 }],
  units: [row("Nm", 0, null, [UNITS_FILE]), row("rpm", 1, "rotational speed", [UNITS_FILE])],
  adoptable: null,
};
```

In `gui/src/stories/fixtures.ts`, `FREE_UNITS` and `VOCABULARY` become, with the same helper before them:

```ts
/** A row of the Units tab, which the variable panel does not read: a unit variables state. */
function row(
  unit: string,
  variables: number,
  description: string | null = null,
  files: string[] = [],
): UnitsReply["units"][number] {
  return { unit, description, files, variables, types: 0, members: 0, findings: 0 };
}

/** A project with no units vocabulary: the picker's "Other units in this project" list. */
export const FREE_UNITS: UnitsReply = {
  revision: 7,
  vocabulary: null,
  used: [
    { unit: "Hz", variables: 4 },
    { unit: "%", variables: 3 },
    { unit: "V", variables: 3 },
    { unit: "degC", variables: 1 },
    { unit: "rpm", variables: 1 },
  ],
  units: [row("%", 3), row("Hz", 4), row("V", 3), row("degC", 1), row("rpm", 1)],
  adoptable: 5,
};

const UNITS_FILE = "C:/work/demo/units.ddd.json";

/** A project's declared vocabulary, described, with how many variables use each. */
export const VOCABULARY: UnitsReply = {
  revision: 7,
  vocabulary: [
    { unit: "rpm", description: "rotational speed, revolutions per minute" },
    { unit: "Nm", description: "torque, newton metre" },
    { unit: "degC", description: "temperature" },
    { unit: "kPa", description: "pressure" },
  ],
  used: [{ unit: "rpm", variables: 1 }],
  units: [
    row("Nm", 0, "torque, newton metre", [UNITS_FILE]),
    row("degC", 0, "temperature", [UNITS_FILE]),
    row("kPa", 0, "pressure", [UNITS_FILE]),
    row("rpm", 1, "rotational speed, revolutions per minute", [UNITS_FILE]),
  ],
  adoptable: null,
};
```

Run: `npm run typecheck`
Expected: PASS. `grep -c "fingerprint: string | null" src/generated/api.ts` prints 2 (`Change`'s and `PlannedChange`'s).

- [ ] **Step 9: Run the gates, then commit**

The Python gate: `python -m pytest`, `python -m ruff format --check .`, `python -m ruff check .`, `python -m mypy`. `src/ddd/project_units.py`, `src/ddd/gui/api.py` and `src/ddd/variables.py` are at 100 % line and branch coverage; a branch left uncovered means a case of Step 1 is missing, not that the branch is dead.

The page: `cd gui && npm run lint && npm run typecheck && npm test && npm run build`. No story changes its picture - neither view reads the new fields - so no screenshot reference is made.

```bash
git add src/ddd/project_units.py src/ddd/gui/contract.py src/ddd/gui/api.py src/ddd/gui/server.py src/ddd/variables.py tests/test_gui_api.py tests/test_gui_server.py gui/src/lib/units.test.ts gui/src/stories/fixtures.ts
git commit -m "answer the units tab's rows, one unit's places, entries and findings, and the preview of renaming, adding, describing, removing and adopting a unit, a created file carrying no fingerprint and a blank description clearing one"
git push
```

---

### Task 6: The page's calls and logic

**Files:**
- Modify: `gui/src/api/client.ts` (`UnitPlanRequest`, `getUnit`, `getUnitPlan`, `planQuery`), `gui/src/api/types.ts` (five names re-exported)
- Create: `gui/src/lib/projectUnits.ts`
- Modify: `gui/src/lib/route.ts` (`ProjectView`, `Route`, `parseRoute`, `hrefOf`)
- Test: `gui/src/lib/projectUnits.test.ts` (new), `gui/src/lib/route.test.ts`, `gui/src/api/client.test.ts`

**Interfaces:**
- Consumes: Task 5's generated `ProjectUnit`, `UnitsReply` with `units` and `adoptable`, `UnitEntry`, `UnitPlace`, `UnitReply`, `PlanReply`, `PlannedOperation` with `op: "insert"`, and `PlannedChange` and `Change` with `fingerprint: string | null`, and part 1's four `UnitsReply` literals as Task 5 left them; part 1's `UnitSection`, `consequence`, `baseName`, `editOf` and `outsideVocabulary` (`gui/src/lib/units.ts`).
- Produces, for Tasks 7 and 8:

```ts
// api/client.ts
export type UnitPlanRequest =
  | { action: "rename"; unit: string; to: string }
  | { action: "add" | "remove"; unit: string }
  | { action: "describe"; unit: string; description: string }
  | { action: "adopt" };
getUnit(name: string, fetchImpl?: Fetch): Promise<UnitReply>
getUnitPlan(plan: UnitPlanRequest, fetchImpl?: Fetch): Promise<PlanReply>

// lib/projectUnits.ts: the skeleton's nine, and three the widgets draw with
unitRows(units: readonly ProjectUnit[]): ProjectUnit[]
statedBy(unit: ProjectUnit): string
descriptionOf(unit: ProjectUnit, hasVocabulary: boolean): string
findingCheck(unit: ProjectUnit): "unknown-unit" | "duplicate-unit" | null
tabTitle(units: readonly ProjectUnit[], hasVocabulary: boolean): string
unitMeta(unit: ProjectUnit, reply: UnitReply, hasVocabulary: boolean): string
placeRole(place: UnitPlace): string
offers(unit: ProjectUnit, hasVocabulary: boolean): { describe: boolean; add: boolean; remove: boolean }
renameSections(unit: string, units: UnitsReply, narrow: string): UnitSection[]
renameConsequence(plan: PlanReply, from: ProjectUnit, to: string, units: UnitsReply): string
adoptionSentence(adoptable: number): string
planEdit(plan: PlanReply): Changes | null

// lib/route.ts
type ProjectView = "graph" | "table" | "units";
type Route =
  | { page: "start" }
  | { page: "project"; view: Exclude<ProjectView, "units">; variable?: string }
  | { page: "project"; view: "units"; unit?: string }  // /project?view=units[&unit=…]
  | { page: "component"; file: string; variable?: string };
```

- [ ] **Step 1: The types Task 5 generates**

Run: `cd gui && npm run schemas && npm run typecheck`
Expected: PASS. `gui/src/generated/api.ts` declares `ProjectUnit`, `UnitEntry`, `UnitPlace`, `UnitReply` and `PlanReply`, `fingerprint: string | null` on `PlannedChange` and `Change`, and `"insert"` among `PlannedOperation`'s `op`; part 1's four `UnitsReply` literals carry `units` and `adoptable`. If either is not so, Task 5 is not in: stop.

- [ ] **Step 2: The failing tests**

Create `gui/src/lib/projectUnits.test.ts`:

```ts
import { expect, describe as group, test } from "vitest";
import type {
  PlannedChange,
  PlanReply,
  ProjectUnit,
  UnitPlace,
  UnitReply,
  UnitsReply,
} from "../api/types";
import {
  adoptionSentence,
  descriptionOf,
  findingCheck,
  offers,
  placeRole,
  planEdit,
  renameConsequence,
  renameSections,
  statedBy,
  tabTitle,
  unitMeta,
  unitRows,
} from "./projectUnits";

const UNITS_FILE = "C:/w/units.ddd.json";
const MORE_UNITS = "C:/w/more_units.ddd.json";
const CONTROLLER = "C:/w/components/controller.ddd.json";
const PUMP = "C:/w/components/pump.ddd.json";
const TYPES = "C:/w/types.ddd.json";

/** A row of the Units tab: outside the vocabulary and stated by nothing, unless told otherwise. */
function row(unit: string, extra: Partial<ProjectUnit> = {}): ProjectUnit {
  return {
    unit,
    description: null,
    files: [],
    variables: 0,
    types: 0,
    members: 0,
    findings: 0,
    ...extra,
  };
}

// The vocabulary example with one declaration drifted to RPM from outside, and a type file
// stating RPM too: the mockups' project, cut down.
const RPM = row("RPM", { variables: 1, types: 1, findings: 2 });
const RPM_LISTED = row("rpm", {
  description: "rotational speed",
  files: [UNITS_FILE],
  variables: 2,
});
const KPA = row("kPa", { description: "pressure", files: [UNITS_FILE], variables: 2 });
const NM = row("Nm", { description: null, files: [UNITS_FILE], types: 1 });
const DEGC = row("degC", { description: "temperature", files: [UNITS_FILE] });
const MS = row("ms", { variables: 1, findings: 1 });
const ROWS = [DEGC, KPA, MS, NM, RPM, RPM_LISTED];
const VOCABULARY: UnitsReply = {
  revision: 3,
  vocabulary: [
    { unit: "rpm", description: "rotational speed" },
    { unit: "Nm", description: null },
    { unit: "degC", description: "temperature" },
    { unit: "kPa", description: "pressure" },
  ],
  used: [
    { unit: "kPa", variables: 2 },
    { unit: "rpm", variables: 2 },
    { unit: "RPM", variables: 1 },
    { unit: "ms", variables: 1 },
  ],
  units: ROWS,
  adoptable: null,
};
// The same project without its units file: every unit is free, and adoption would list them.
const FREE: UnitsReply = {
  revision: 3,
  vocabulary: null,
  used: VOCABULARY.used,
  units: [
    row("Hz", { variables: 3 }),
    row("%", { variables: 4 }),
    row("RPM", { variables: 1, types: 1 }),
    row("rpm", { variables: 2 }),
    row("V", { variables: 2 }),
  ],
  adoptable: 5,
};

function place(kind: UnitPlace["kind"], path: string, extra: Partial<UnitPlace> = {}): UnitPlace {
  return {
    path,
    pointer: "component.interface[0].definition.unit",
    kind,
    name: "EngineSpeed",
    component: kind === "variable" ? "Controller" : null,
    role: kind === "variable" ? "reads" : null,
    ...extra,
  };
}

function reply(unit: string, sites: UnitPlace[]): UnitReply {
  return { revision: 3, unit, description: null, entries: [], sites, findings: [] };
}

// RPM renamed onto rpm: Controller's declaration and the scalar type stating it.
const IN_CONTROLLER: PlannedChange = {
  file: CONTROLLER,
  fingerprint: "c0",
  operations: [{ op: "set", pointer: "component.interface[0].definition.unit", raw: '"rpm"' }],
  hunks: [{ line: 14, before: ['  "unit": "RPM",'], after: ['  "unit": "rpm",'] }],
};
const IN_TYPES: PlannedChange = {
  file: TYPES,
  fingerprint: "t0",
  operations: [{ op: "set", pointer: "types[0].unit", raw: '"rpm"' }],
  hunks: [{ line: 6, before: ['  "unit": "RPM",'], after: ['  "unit": "rpm",'] }],
};
const MERGE: PlanReply = { revision: 3, changes: [IN_CONTROLLER, IN_TYPES] };
const ONE_FILE: PlanReply = { revision: 3, changes: [IN_CONTROLLER] };
// rpm renamed onto RPM, which no entry lists: its own entry is renamed with it.
const RENAMED_ENTRY: PlanReply = {
  revision: 3,
  changes: [
    { ...IN_CONTROLLER, file: PUMP },
    {
      file: UNITS_FILE,
      fingerprint: "u0",
      operations: [{ op: "set", pointer: "units[0].unit", raw: '"RPM"' }],
      hunks: [{ line: 3, before: ['  { "unit": "rpm",'], after: ['  { "unit": "RPM",'] }],
    },
  ],
};

group("the table", () => {
  test("units with findings come first, then the most stated, then by spelling, unused last", () => {
    expect(unitRows(ROWS).map((unit) => unit.unit)).toEqual([
      "RPM",
      "ms",
      "kPa",
      "rpm",
      "Nm",
      "degC",
    ]);
  });

  test("spellings compare code unit by code unit, capitals first, whatever the locale", () => {
    const tied = [
      row("rpm", { variables: 1 }),
      row("°C", { variables: 1 }),
      row("RPM", { variables: 1 }),
    ];
    expect(unitRows(tied).map((unit) => unit.unit)).toEqual(["RPM", "rpm", "°C"]);
  });

  test("an unused vocabulary entry with a finding of its own still comes with the findings", () => {
    const twice = row("bar", { files: [UNITS_FILE, MORE_UNITS], findings: 2 });
    expect(unitRows([KPA, twice]).map((unit) => unit.unit)).toEqual(["bar", "kPa"]);
  });

  test("the table leaves the answer as it came", () => {
    const rows = [...ROWS];
    unitRows(rows);
    expect(rows).toEqual(ROWS);
  });

  test.each([
    [RPM_LISTED, "2 variables"],
    [RPM, "1 variable, 1 type"],
    [NM, "1 type"],
    [row("m/s", { variables: 1, types: 2, members: 3 }), "1 variable, 2 types, 3 members"],
    [row("N", { members: 1 }), "1 member"],
    [DEGC, "unused"],
  ])("%o is stated by %s", (unit, sentence) => {
    expect(statedBy(unit)).toBe(sentence);
  });

  test("the description is the vocabulary's, and says so of a unit outside it", () => {
    expect(descriptionOf(RPM_LISTED, true)).toBe("rotational speed");
    expect(descriptionOf(NM, true)).toBe("");
    expect(descriptionOf(RPM, true)).toBe("not in the vocabulary");
  });

  test("without a units file no unit is described, and none is said to be outside", () => {
    expect(descriptionOf(RPM, false)).toBe("");
  });

  test("a unit's findings are unknown outside the vocabulary, and listed twice inside it", () => {
    expect(findingCheck(RPM)).toBe("unknown-unit");
    expect(findingCheck(row("kPa", { files: [UNITS_FILE, MORE_UNITS], findings: 2 }))).toBe(
      "duplicate-unit",
    );
    expect(findingCheck(RPM_LISTED)).toBeNull();
  });

  test("the title counts the units, and those the vocabulary leaves out", () => {
    expect(tabTitle(ROWS, true)).toBe("6 units · 2 not in the vocabulary");
    expect(tabTitle([RPM_LISTED], true)).toBe("1 unit · all in the vocabulary");
    expect(tabTitle(FREE.units, false)).toBe("5 units · no units file");
    expect(tabTitle([], false)).toBe("0 units · no units file");
  });
});

group("a unit's panel", () => {
  test("the line under the unit says where it is listed and how widely it is stated", () => {
    const sites = [place("variable", CONTROLLER), place("type", TYPES, { name: "Speed_t" })];
    expect(unitMeta(RPM, reply("RPM", sites), true)).toBe(
      "not in the vocabulary · stated in 2 places, 2 files",
    );
    const two = [place("variable", PUMP), place("variable", PUMP, { name: "PumpSpeed" })];
    expect(unitMeta(RPM_LISTED, reply("rpm", two), true)).toBe(
      "in the vocabulary, units.ddd.json · stated in 2 places, 1 file",
    );
    expect(unitMeta(DEGC, reply("degC", []), true)).toBe(
      "in the vocabulary, units.ddd.json · stated nowhere",
    );
    const twice = row("kPa", { files: [UNITS_FILE, MORE_UNITS] });
    expect(unitMeta(twice, reply("kPa", [place("variable", PUMP)]), true)).toBe(
      "in the vocabulary, units.ddd.json, more_units.ddd.json · stated in 1 place, 1 file",
    );
  });

  test("without a units file the line says only where the unit is stated", () => {
    const sites = [place("variable", CONTROLLER), place("type", TYPES, { name: "Speed_t" })];
    expect(unitMeta(RPM, reply("RPM", sites), false)).toBe("stated in 2 places, 2 files");
  });

  test("a place is a variable's role, a scalar type or a structure member", () => {
    expect(placeRole(place("variable", PUMP, { role: "local" }))).toBe("local");
    expect(placeRole(place("type", TYPES))).toBe("scalar type");
    expect(placeRole(place("member", TYPES, { name: "Motor_t.speed" }))).toBe("structure member");
    expect(placeRole(place("variable", PUMP, { role: null }))).toBe("variable");
  });

  test("a unit the vocabulary lists is described, and removed once nothing states it", () => {
    expect(offers(RPM_LISTED, true)).toEqual({ describe: true, add: false, remove: false });
    expect(offers(DEGC, true)).toEqual({ describe: true, add: false, remove: true });
  });

  test("a unit outside the vocabulary is added to it, when the project has one", () => {
    expect(offers(RPM, true)).toEqual({ describe: false, add: true, remove: false });
    expect(offers(RPM, false)).toEqual({ describe: false, add: false, remove: false });
  });
});

group("the rename picker", () => {
  test("the vocabulary's units first, then the other units in use, the unit left out", () => {
    const sections = renameSections("RPM", VOCABULARY, "");
    expect(sections.map((section) => [section.id, section.title])).toEqual([
      ["vocabulary", "This project's units"],
      ["used", "Other units in this project"],
    ]);
    expect(sections[0]?.choices.map((c) => [c.id, c.unit, c.label, c.detail])).toEqual([
      ["vocabulary:rpm", "rpm", "rpm", "rotational speed · 2 variables"],
      ["vocabulary:Nm", "Nm", "Nm", "1 type"],
      ["vocabulary:degC", "degC", "degC", "temperature · unused"],
      ["vocabulary:kPa", "kPa", "kPa", "pressure · 2 variables"],
    ]);
    expect(sections[1]?.choices.map((c) => [c.id, c.detail])).toEqual([["used:ms", "1 variable"]]);
  });

  test("without a vocabulary every other unit in use is listed, the most stated first", () => {
    const sections = renameSections("RPM", FREE, "");
    expect(sections.map((section) => section.id)).toEqual(["used"]);
    expect(sections[0]?.choices.map((c) => [c.label, c.detail])).toEqual([
      ["%", "4 variables"],
      ["Hz", "3 variables"],
      ["V", "2 variables"],
      ["rpm", "2 variables"],
    ]);
  });

  test("an adopted vocabulary's empty descriptions leave only what states each unit", () => {
    const adopted: UnitsReply = {
      ...VOCABULARY,
      units: [row("rpm", { description: "", files: [UNITS_FILE], variables: 1 })],
    };
    expect(renameSections("RPM", adopted, "")[0]?.choices[0]?.detail).toBe("1 variable");
  });

  test("typing narrows every section, regardless of case", () => {
    const sections = renameSections("RPM", VOCABULARY, "M");
    expect(sections.map((section) => section.choices.map((c) => c.label))).toEqual([
      ["rpm", "Nm"],
      ["ms"],
      ["M"],
    ]);
  });

  test("what was typed is offered as typed unless it is listed exactly, or is the unit itself", () => {
    expect(renameSections("RPM", VOCABULARY, "rpm/min").at(-1)).toEqual({
      id: "typed",
      title: "As typed",
      choices: [
        {
          id: "typed:rpm/min",
          unit: "rpm/min",
          label: "rpm/min",
          detail: "not one of this project's units",
        },
      ],
    });
    expect(renameSections("RPM", FREE, "rpm/min").at(-1)?.choices[0]?.detail).toBe("");
    expect(renameSections("RPM", VOCABULARY, "rpm").some((s) => s.id === "typed")).toBe(false);
    expect(renameSections("RPM", VOCABULARY, "RPM").some((s) => s.id === "typed")).toBe(false);
  });
});

group("what a plan says and sends", () => {
  test("renaming onto a spelling the vocabulary lists merges the two", () => {
    expect(renameConsequence(MERGE, RPM, "rpm", VOCABULARY)).toBe(
      "Changes 2 files: controller.ddd.json, types.ddd.json. " +
        "rpm is in the vocabulary already, so RPM merges into it.",
    );
  });

  test("renaming a listed unit onto a new spelling renames its entry too", () => {
    expect(renameConsequence(RENAMED_ENTRY, RPM_LISTED, "RPM", VOCABULARY)).toBe(
      "Changes 2 files: pump.ddd.json, units.ddd.json. rpm is renamed in units.ddd.json too.",
    );
  });

  test("renaming onto a spelling no vocabulary lists says so, as part 1's picker does", () => {
    expect(renameConsequence(ONE_FILE, MS, "s", VOCABULARY)).toBe(
      "Changes 1 file: controller.ddd.json. Not one of this project's units.",
    );
  });

  test("without a units file a rename says only what it changes", () => {
    expect(renameConsequence(MERGE, RPM, "rpm", FREE)).toBe(
      "Changes 2 files: controller.ddd.json, types.ddd.json",
    );
  });

  test("the banner says what adopting writes, and that nothing more will be reported", () => {
    expect(adoptionSentence(8)).toBe(
      "This project has no units file, so no unit is checked against a vocabulary. " +
        "Adopting writes units.ddd.json with the 8 units in use and includes it in the " +
        "project: nothing is reported that is not reported today.",
    );
    expect(adoptionSentence(1)).toContain("with the 1 unit in use");
  });

  test("a project stating no unit has nothing to adopt, and the banner says so", () => {
    expect(adoptionSentence(0)).toBe(
      "This project has no units file, so no unit is checked against a vocabulary. " +
        "It states no unit, so there is nothing to adopt.",
    );
  });

  test("a plan comes to the edit POST /api/edit takes, a created file's null fingerprint kept", () => {
    const adoption: PlanReply = {
      revision: 3,
      changes: [
        {
          file: "C:/w/demo.ddd.json",
          fingerprint: "d0",
          operations: [{ op: "insert", pointer: "project.includes[2]", raw: '"units.ddd.json"' }],
          hunks: [{ line: 7, before: [], after: ['      "units.ddd.json"'] }],
        },
        {
          file: UNITS_FILE,
          fingerprint: null,
          operations: [
            { op: "set", pointer: "", raw: '{"units": [{"unit": "%", "description": ""}]}' },
          ],
          hunks: [{ line: 1, before: [], after: ["{", '  "units": ['] }],
        },
      ],
    };
    expect(planEdit(adoption)).toEqual({
      changes: [
        {
          file: "C:/w/demo.ddd.json",
          fingerprint: "d0",
          operations: [{ op: "insert", pointer: "project.includes[2]", raw: '"units.ddd.json"' }],
        },
        {
          file: UNITS_FILE,
          fingerprint: null,
          operations: [
            { op: "set", pointer: "", raw: '{"units": [{"unit": "%", "description": ""}]}' },
          ],
        },
      ],
    });
  });

  test("a plan with nothing to change comes to no edit", () => {
    expect(planEdit({ revision: 3, changes: [] })).toBeNull();
  });
});
```

Append to `gui/src/lib/route.test.ts`:

```ts
test.each([
  ["/project", "?view=units", { page: "project", view: "units" }],
  ["/project", "?view=units&unit=RPM", { page: "project", view: "units", unit: "RPM" }],
  ["/project", "?view=units&unit=%25", { page: "project", view: "units", unit: "%" }],
  ["/project", "?view=units&unit=", { page: "project", view: "units" }],
  ["/project", "?view=units&variable=ValueA", { page: "project", view: "units" }],
  ["/project", "?unit=RPM", { page: "project", view: "graph" }],
] as const)("%s%s carries the unit %o", (pathname, search, route) => {
  expect(parseRoute(pathname, search)).toEqual(route);
});

test.each([
  [{ page: "project", view: "units" }, "/project?view=units"],
  [{ page: "project", view: "units", unit: "RPM" }, "/project?view=units&unit=RPM"],
  [{ page: "project", view: "units", unit: "°C" }, "/project?view=units&unit=%C2%B0C"],
  [{ page: "project", view: "units", unit: "m/s" }, "/project?view=units&unit=m%2Fs"],
] as const)("%o is at %s", (route, href) => {
  expect(hrefOf(route)).toBe(href);
});
```

In `gui/src/api/client.test.ts`, import `getUnit` and `getUnitPlan` beside `getUnits`, and in "each call asks the path and method the api expects" call, after the second `getSettle` and before `postEdit`:

```ts
    await getUnit("°C", fetchImpl);
    await getUnitPlan({ action: "rename", unit: "RPM", to: "rpm" }, fetchImpl);
    await getUnitPlan({ action: "add", unit: "m/s" }, fetchImpl);
    await getUnitPlan({ action: "remove", unit: "kPa" }, fetchImpl);
    await getUnitPlan(
      { action: "describe", unit: "rpm", description: "rotational speed, 1/min" },
      fetchImpl,
    );
    await getUnitPlan({ action: "adopt" }, fetchImpl);
```

and expect, after `"/api/settle?name=ValueA&key=unit"` and before `"/api/edit"`:

```ts
      ["/api/unit?name=%C2%B0C", { credentials: "same-origin" }],
      ["/api/unit-plan?action=rename&unit=RPM&to=rpm", { credentials: "same-origin" }],
      ["/api/unit-plan?action=add&unit=m%2Fs", { credentials: "same-origin" }],
      ["/api/unit-plan?action=remove&unit=kPa", { credentials: "same-origin" }],
      [
        "/api/unit-plan?action=describe&unit=rpm&description=rotational%20speed%2C%201%2Fmin",
        { credentials: "same-origin" },
      ],
      ["/api/unit-plan?action=adopt", { credentials: "same-origin" }],
```

Run: `npm test`
Expected: FAIL: `Error: Cannot find module './projectUnits'`; in the client's test `TypeError: getUnit is not a function`; and nine of the ten new route tests, a units address read as the graph (`expected { page: 'project', view: 'graph' } to deeply equal { page: 'project', view: 'units' }`) and a units route written as `/project`.

- [ ] **Step 3: The calls**

In `gui/src/api/client.ts`, the type import gains `PlanReply` and `UnitReply`:

```ts
import type {
  Changes,
  EditReply,
  FileContent,
  Found,
  GraphReply,
  PlanReply,
  SessionInfo,
  SettleReply,
  State,
  UnitReply,
  UnitsReply,
  VariableReply,
} from "./types";
```

and after `settleQuery`:

```ts
/** One change to the project's units, as `GET /api/unit-plan` takes it: what each action needs,
 * and nothing it does not. */
export type UnitPlanRequest =
  | { action: "rename"; unit: string; to: string }
  | { action: "add" | "remove"; unit: string }
  | { action: "describe"; unit: string; description: string }
  | { action: "adopt" };

export const getUnit = (name: string, fetchImpl: Fetch = fetch) =>
  request<UnitReply>(`/api/unit?name=${encodeURIComponent(name)}`, {}, fetchImpl);

export const getUnitPlan = (plan: UnitPlanRequest, fetchImpl: Fetch = fetch) =>
  request<PlanReply>(`/api/unit-plan?${planQuery(plan)}`, {}, fetchImpl);

/** A plan's query: the action, then the unit and whichever of `to` and `description` it takes. */
function planQuery(plan: UnitPlanRequest): string {
  const parts: [string, string][] = [["action", plan.action]];
  if (plan.action !== "adopt") parts.push(["unit", plan.unit]);
  if (plan.action === "rename") parts.push(["to", plan.to]);
  if (plan.action === "describe") parts.push(["description", plan.description]);
  return parts.map(([key, value]) => `${key}=${encodeURIComponent(value)}`).join("&");
}
```

`gui/src/api/types.ts` re-exports the five new names, in the order Biome keeps:

```ts
// The JSON the server answers with (src/ddd/gui/api.py), shape for shape - re-exported from
// gui/src/generated/api.ts, generated from src/ddd/gui/contract.py by scripts/schemas.mjs, so
// that a model added to the contract without a page type here fails the build instead of the
// two silently drifting apart.
export type {
  Change,
  Changes,
  EditReply,
  FileContent,
  Finding,
  Found,
  FoundProject,
  GraphDisagreement,
  GraphFlow,
  GraphModule,
  GraphReply,
  Hunk,
  Note,
  Operation,
  PlannedChange,
  PlannedOperation,
  PlanReply,
  ProjectUnit,
  SessionInfo,
  SettleReply,
  Severity,
  SourceFile,
  State,
  UnitEntry,
  UnitPlace,
  UnitReply,
  UnitsReply,
  UsedUnit,
  VariableDeclaration,
  VariableReply,
  VocabularyUnit,
} from "../generated/api";
```

- [ ] **Step 4: The route**

`gui/src/lib/route.ts` whole:

```ts
/** Which of the project screen's three tabs is open. */
export type ProjectView = "graph" | "table" | "units";

export type Route =
  | { page: "start" }
  | { page: "project"; view: Exclude<ProjectView, "units">; variable?: string }
  | { page: "project"; view: "units"; unit?: string }
  | { page: "component"; file: string; variable?: string };

/** The page an address shows; anything unknown is the start page. */
export function parseRoute(pathname: string, search: string): Route {
  const query = new URLSearchParams(search);
  const variable = query.get("variable") || undefined;
  // The graph is what a bare /project opens on, so an address written before the tabs existed -
  // a bookmark, the masthead, a link in a message - still lands on the project screen. The graph
  // has a variable's panel beside it and the units tab a unit's; the table's rows open their
  // component instead.
  if (pathname === "/project") {
    const view = query.get("view");
    if (view === "table") return { page: "project", view: "table" };
    if (view === "units") {
      const unit = query.get("unit") || undefined;
      return unit === undefined
        ? { page: "project", view: "units" }
        : { page: "project", view: "units", unit };
    }
    return variable === undefined
      ? { page: "project", view: "graph" }
      : { page: "project", view: "graph", variable };
  }
  const file = query.get("file");
  if (pathname === "/component" && file) {
    return variable === undefined
      ? { page: "component", file }
      : { page: "component", file, variable };
  }
  return { page: "start" };
}

/** The address of a page. */
export function hrefOf(route: Route): string {
  const variable =
    "variable" in route && route.variable !== undefined
      ? `variable=${encodeURIComponent(route.variable)}`
      : "";
  switch (route.page) {
    case "start":
      return "/";
    case "project":
      if (route.view === "table") return "/project?view=table";
      if (route.view === "units") {
        return route.unit === undefined
          ? "/project?view=units"
          : `/project?view=units&unit=${encodeURIComponent(route.unit)}`;
      }
      return variable === "" ? "/project" : `/project?${variable}`;
    case "component": {
      const file = `/component?file=${encodeURIComponent(route.file)}`;
      return variable === "" ? file : `${file}&${variable}`;
    }
  }
}
```

- [ ] **Step 5: The page's logic**

Create `gui/src/lib/projectUnits.ts`:

```ts
import type {
  Changes,
  PlanReply,
  ProjectUnit,
  UnitPlace,
  UnitReply,
  UnitsReply,
} from "../api/types";
import { baseName, consequence, editOf, outsideVocabulary, type UnitSection } from "./units";

/** The file adoption writes beside the project description (`ddd.lsp.units.ADOPTED`). */
const ADOPTED = "units.ddd.json";

const OUTSIDE = "not in the vocabulary";

/** The Units tab's rows in the order spec 5.1 gives: units with findings first, then the most
 * stated, then by spelling - code unit by code unit, as Python sorts them, so `RPM` comes before
 * `rpm` on every machine whatever its locale. A vocabulary entry nothing states is stated by
 * nothing, and so comes last among its kind. */
export function unitRows(units: readonly ProjectUnit[]): ProjectUnit[] {
  return [...units].sort(
    (a, b) =>
      Number(b.findings > 0) - Number(a.findings > 0) ||
      stated(b) - stated(a) ||
      spelling(a.unit, b.unit),
  );
}

/** The table's Stated by column: "2 variables", "1 variable, 1 type", or "unused" for a
 * vocabulary entry nothing states. */
export function statedBy(unit: ProjectUnit): string {
  const parts = [
    counted(unit.variables, "variable"),
    counted(unit.types, "type"),
    counted(unit.members, "member"),
  ].filter((part) => part !== null);
  return parts.length === 0 ? "unused" : parts.join(", ");
}

/** The table's Description column: the vocabulary's description, "not in the vocabulary"
 * outside it, and nothing at all for a project with no units file, where every unit is free. */
export function descriptionOf(unit: ProjectUnit, hasVocabulary: boolean): string {
  if (!hasVocabulary) return "";
  return unit.files.length === 0 ? OUTSIDE : (unit.description ?? "");
}

/**
 * The check a unit's findings are filed by, for its chip in the table; `null` without any.
 *
 * The row carries a count, not the findings: which check they are is read from where the unit
 * stands, since a unit outside the vocabulary can only be unknown and one inside it can only be
 * listed twice.
 */
export function findingCheck(unit: ProjectUnit): "unknown-unit" | "duplicate-unit" | null {
  if (unit.findings === 0) return null;
  return unit.files.length === 0 ? "unknown-unit" : "duplicate-unit";
}

/** The line above the table: "9 units · 2 not in the vocabulary", or "8 units · no units file". */
export function tabTitle(units: readonly ProjectUnit[], hasVocabulary: boolean): string {
  const all = plural(units.length, "unit");
  if (!hasVocabulary) return `${all} · no units file`;
  const outside = units.filter((unit) => unit.files.length === 0).length;
  return `${all} · ${outside === 0 ? "all in the vocabulary" : `${outside} ${OUTSIDE}`}`;
}

/** The panel's line under the unit: where the vocabulary lists it, and how many places in how
 * many files state it - "in the vocabulary, units.ddd.json · stated in 2 places, 2 files". A
 * project with no units file has no vocabulary to speak of, and the line says only the places. */
export function unitMeta(unit: ProjectUnit, reply: UnitReply, hasVocabulary: boolean): string {
  const files = new Set(reply.sites.map((site) => site.path)).size;
  const places =
    reply.sites.length === 0
      ? "stated nowhere"
      : `stated in ${plural(reply.sites.length, "place")}, ${plural(files, "file")}`;
  if (!hasVocabulary) return places;
  const listed =
    unit.files.length === 0 ? OUTSIDE : `in the vocabulary, ${unit.files.map(baseName).join(", ")}`;
  return `${listed} · ${places}`;
}

/** What a place stating the unit is, for the panel's What column: a variable's role, or the
 * kind of type. */
export function placeRole(place: UnitPlace): string {
  if (place.kind === "type") return "scalar type";
  if (place.kind === "member") return "structure member";
  return place.role ?? "variable";
}

/** What the unit's state offers beside the rename, which it always offers (spec 5.2): a
 * description for a unit the vocabulary lists, its removal once nothing states it, and its
 * addition for a unit outside a vocabulary the project has. */
export function offers(
  unit: ProjectUnit,
  hasVocabulary: boolean,
): { describe: boolean; add: boolean; remove: boolean } {
  const listed = unit.files.length > 0;
  return { describe: listed, add: hasVocabulary && !listed, remove: listed && stated(unit) === 0 };
}

/**
 * The rename picker's sections: the vocabulary's units first, in the order its files list them,
 * then the other units in use, the most stated first, then the text as typed - the unit itself
 * left out of all three, since renaming it onto itself changes nothing. Narrowed as part 1's
 * picker narrows, by what is typed, regardless of case.
 */
export function renameSections(unit: string, units: UnitsReply, narrow: string): UnitSection[] {
  const others = units.units.filter((row) => row.unit !== unit);
  const order = (units.vocabulary ?? []).map((entry) => entry.unit);
  const listed: UnitSection[] = [
    {
      id: "vocabulary",
      title: "This project's units",
      choices: others
        .filter((row) => row.files.length > 0)
        .sort((a, b) => order.indexOf(a.unit) - order.indexOf(b.unit))
        .map((row) => choice("vocabulary", row.unit, detailOf(row))),
    },
    {
      id: "used",
      title: "Other units in this project",
      choices: others
        .filter((row) => row.files.length === 0)
        .sort((a, b) => stated(b) - stated(a) || spelling(a.unit, b.unit))
        .map((row) => choice("used", row.unit, statedBy(row))),
    },
  ];
  const wanted = narrow.toLowerCase();
  const sections = listed
    .map((section) => ({
      ...section,
      choices: section.choices.filter((entry) => entry.label.toLowerCase().includes(wanted)),
    }))
    .filter((section) => section.choices.length > 0);
  const exact = sections.some((section) => section.choices.some((entry) => entry.unit === narrow));
  if (narrow !== "" && narrow !== unit && !exact) {
    const note = outsideVocabulary(units, narrow) ? "not one of this project's units" : "";
    sections.push({ id: "typed", title: "As typed", choices: [choice("typed", narrow, note)] });
  }
  return sections;
}

/**
 * What a rename changes, and what becomes of the vocabulary (spec 5.2): the files it writes,
 * then - where the project has a vocabulary - that the new spelling is listed already and the
 * two merge, that the unit's own entry is renamed too, or that the new spelling is not one of
 * the project's units.
 */
export function renameConsequence(
  plan: PlanReply,
  from: ProjectUnit,
  to: string,
  units: UnitsReply,
): string {
  const changes = consequence(plan.changes);
  if (units.vocabulary === null) return changes;
  const vocabulary = units.vocabulary.some((entry) => entry.unit === to)
    ? `${to} is in the vocabulary already, so ${from.unit} merges into it`
    : from.files.length > 0
      ? `${from.unit} is renamed in ${from.files.map(baseName).join(", ")} too`
      : "Not one of this project's units";
  return `${changes}. ${vocabulary}.`;
}

/** The adoption banner's sentence (spec 5.3), for a project with no units file. */
export function adoptionSentence(adoptable: number): string {
  const opening = "This project has no units file, so no unit is checked against a vocabulary.";
  if (adoptable === 0) return `${opening} It states no unit, so there is nothing to adopt.`;
  return (
    `${opening} Adopting writes ${ADOPTED} with the ${plural(adoptable, "unit")} in use and ` +
    "includes it in the project: nothing is reported that is not reported today."
  );
}

/** The edit a plan comes to, exactly as `POST /api/edit` takes it - the `null` fingerprint of a
 * file it creates included - or `null` when there is nothing to change. A plan has the shape of
 * part 1's preview, and comes to its edit the same way. */
export function planEdit(plan: PlanReply): Changes | null {
  return editOf(plan);
}

/** How many variables, types and structure members state a unit. */
function stated(unit: ProjectUnit): number {
  return unit.variables + unit.types + unit.members;
}

/** Two spellings compared code unit by code unit, without a branch for the equal pair a table
 * of one row per spelling never holds. */
function spelling(a: string, b: string): number {
  return Number(a > b) - Number(a < b);
}

/** "1 variable", "2 variables". */
function plural(count: number, noun: string): string {
  return `${count} ${noun}${count === 1 ? "" : "s"}`;
}

/** A count of what states a unit, or `null` for none, which the sentence leaves out. */
function counted(count: number, noun: string): string | null {
  return count === 0 ? null : plural(count, noun);
}

/** A vocabulary unit's detail in the picker: its description, then what states it. */
function detailOf(row: ProjectUnit): string {
  return [row.description, statedBy(row)]
    .filter((part) => part !== null && part !== "")
    .join(" · ");
}

function choice(section: UnitSection["id"], unit: string, detail: string) {
  return { id: `${section}:${unit}`, unit, label: unit, detail };
}
```

`planEdit` is part 1's `editOf`: a `PlanReply` has a `SettleReply`'s shape, and `editOf` already keeps whatever `fingerprint` a change carries, `null` included. `spelling` has no branch, so that the gate need not reach an equal pair `unitRows` never meets.

- [ ] **Step 6: Run the gate, then commit**

Run: `npm run lint && npm run typecheck && npm test && npm run build`
Expected: PASS; Vitest runs 150 tests at 100 % over `src/api`, `src/lib` and `src/state`. No story changes, so the screenshot service need not run; and nothing here is Python, documentation or read by `tests/test_documentation.py`, so neither need the Python gate - nor in Tasks 7 and 8.

From the repository root:

```bash
git add gui/src/api gui/src/lib/projectUnits.ts gui/src/lib/projectUnits.test.ts gui/src/lib/route.ts gui/src/lib/route.test.ts
git commit -m "ask for a unit and its plans, and decide the units tab's order, its sentences and what each unit offers"
git push
```

---

### Task 7: The Units tab's pictures, and their stories

**Files:**
- Create: `gui/src/components/Changes.tsx`
- Modify: `gui/src/components/VariablePanelView.tsx` (its imports; the picker's `label`; its private `Changes` removed), `gui/src/components/UnitPicker.tsx` (`name` becomes `label`), `gui/src/components/UnitPicker.stories.tsx`
- Create: `gui/src/components/UnitsTableView.tsx`, `UnitsTableView.stories.tsx`, `UnitPanelView.tsx`, `UnitPanelView.stories.tsx`, `AdoptBannerView.tsx`, `AdoptBannerView.stories.tsx`
- Modify: `gui/src/stories/fixtures.ts` (the Units tab's answers), `gui/src/styles/ui.css` (the Units tab's rules)
- Create: the eight references of Step 8, under `gui/screenshots/references/`

**Interfaces:**
- Consumes: Task 6's `client.ts` types and `projectUnits.ts`; part 1's `UnitPicker`, `Panel`, `Table`, `Button`, `Chip`, `Banner`, `keyedFindings`, `distinctFindings`, `consequence`, `baseName`, `hunkLines`.
- Produces, for Task 8:

```ts
// components/Changes.tsx
Changes({ changes }: { changes: readonly PlannedChange[] })
// components/UnitPicker.tsx: Props' `name: string` becomes
label: string // "Unit of ValueA", "Rename RPM to"
// components/UnitsTableView.tsx
interface UnitsTableViewProps {
  units: UnitsReply;
  selected: string | undefined;
  onSelect: (unit: string | undefined) => void;
}
// components/UnitPanelView.tsx
type UnitAction = "describe" | "add" | "remove" | "rename";
interface Offer { plan: PlanReply | null; refusal: string | null; pending: boolean }
interface UnitPanelViewProps {
  unit: ProjectUnit;
  reply: UnitReply;
  units: UnitsReply;
  description: string;
  onDescription: (text: string) => void;
  typed: string;
  narrow: string;
  onTyped: (text: string) => void;
  onChosen: (unit: string) => void;
  onPickerClosed: () => void;
  to: string | null;
  describing: Offer | null;
  adding: Offer | null;
  removing: Offer | null;
  renaming: Offer | null;
  shown: UnitAction | null;
  onShown: (action: UnitAction | null) => void;
  onApply: (action: UnitAction) => void;
  busy: boolean;
  onClose: () => void;
}
// components/AdoptBannerView.tsx
interface AdoptBannerViewProps {
  adoptable: number;
  plan: PlanReply | null;
  refusal: string | null;
  onShowChanges: () => void;
  onAdopt: () => void;
  busy: boolean;
}
interface AdoptPanelViewProps {
  adoptable: number;
  plan: PlanReply;
  onAdopt: () => void;
  busy: boolean;
  onClose: () => void;
}
```

- [ ] **Step 1: The stories' answers**

In `gui/src/stories/fixtures.ts`, as Task 5 left it, the type import and the paths grow:

```ts
import type {
  Finding,
  PlanReply,
  ProjectUnit,
  SettleReply,
  UnitReply,
  UnitsReply,
  VariableReply,
} from "../api/types";

// Paths as the spec's own examples spell them (docs/superpowers/specs/2026-09-18-gui-units-
// design.md, 4.3): absolute and posix, on a Windows checkout.
const SENSOR_HUB = "C:/work/demo/components/sensor_hub.ddd.json";
const CONTROLLER = "C:/work/demo/components/controller.ddd.json";
const USER_INTERFACE = "C:/work/demo/components/user_interface.ddd.json";
const PUMP = "C:/work/demo/components/pump.ddd.json";
const TYPES = "C:/work/demo/types.ddd.json";
const DEMO = "C:/work/demo/demo.ddd.json";
```

and after `NOTHING`, the mockups' project (`docs/superpowers/specs/2026-09-19-gui-units-project/`) - its rows, made with Task 5's `row` and `UNITS_FILE`, three units' panels and five plans:

```ts
// The Units tab of part 2's mockups (docs/superpowers/specs/2026-09-19-gui-units-project/), whose
// DemoDevice states nine units, two of them outside its vocabulary.

/** RPM, outside the vocabulary: Controller reads EngineSpeed in it and the type Speed_t states
 * it, each with an `unknown-unit` finding. */
export const UNKNOWN_RPM: ProjectUnit = { ...row("RPM", 1), types: 1, findings: 2 };

/** rpm, which the vocabulary lists and describes, stated by two variables. */
export const LISTED_RPM = row("rpm", 2, "rotational speed, revolutions per minute", [UNITS_FILE]);

/** kPa, which the vocabulary lists and nothing states. */
export const UNUSED_KPA = row("kPa", 0, "pressure", [UNITS_FILE]);

/** The mockups' project: its vocabulary, and the nine units it states or lists. */
export const PROJECT_UNITS: UnitsReply = {
  revision: 7,
  vocabulary: [
    { unit: "%", description: "percentage" },
    { unit: "Hz", description: "frequency" },
    { unit: "rpm", description: "rotational speed, revolutions per minute" },
    { unit: "V", description: "voltage" },
    { unit: "degC", description: "temperature" },
    { unit: "ms", description: "time" },
    { unit: "kPa", description: "pressure" },
  ],
  used: [
    { unit: "%", variables: 4 },
    { unit: "Hz", variables: 3 },
    { unit: "V", variables: 2 },
    { unit: "degC", variables: 2 },
    { unit: "rpm", variables: 2 },
    { unit: "RPM", variables: 1 },
    { unit: "ms", variables: 1 },
    { unit: "°C", variables: 1 },
  ],
  units: [
    UNKNOWN_RPM,
    { ...row("°C", 1), findings: 1 },
    row("%", 4, "percentage", [UNITS_FILE]),
    row("Hz", 3, "frequency", [UNITS_FILE]),
    LISTED_RPM,
    row("V", 2, "voltage", [UNITS_FILE]),
    row("degC", 2, "temperature", [UNITS_FILE]),
    row("ms", 1, "time", [UNITS_FILE]),
    UNUSED_KPA,
  ],
  adoptable: null,
};

/** The same project before it had a units file: its eight units in use, none of them checked. */
export const UNADOPTED_UNITS: UnitsReply = {
  revision: 7,
  vocabulary: null,
  used: PROJECT_UNITS.used,
  units: PROJECT_UNITS.units
    .filter((unit) => unit !== UNUSED_KPA)
    .map((unit) => ({ ...unit, description: null, files: [], findings: 0 })),
  adoptable: 8,
};

const UNKNOWN: Finding = {
  file: CONTROLLER,
  check: "unknown-unit",
  severity: "error",
  message: "'RPM' is not a unit this project declares - did you mean 'rpm'?",
  pointer: "component.interface[3].definition.unit",
  notes: [],
};

/** RPM's panel: where it is stated, and its finding, filed at each place. */
export const UNKNOWN_RPM_PANEL: UnitReply = {
  revision: 7,
  unit: "RPM",
  description: null,
  entries: [],
  sites: [
    {
      path: CONTROLLER,
      pointer: "component.interface[3].definition.unit",
      kind: "variable",
      name: "EngineSpeed",
      component: "Controller",
      role: "reads",
    },
    {
      path: TYPES,
      pointer: "types[0].unit",
      kind: "type",
      name: "Speed_t",
      component: null,
      role: null,
    },
  ],
  findings: [UNKNOWN, { ...UNKNOWN, file: TYPES, pointer: "types[0].unit" }],
};

/** rpm's panel: its vocabulary entry, and the two variables stating it. */
export const LISTED_RPM_PANEL: UnitReply = {
  revision: 7,
  unit: "rpm",
  description: "rotational speed, revolutions per minute",
  entries: [{ file: UNITS_FILE, pointer: "units[2]" }],
  sites: [
    {
      path: SENSOR_HUB,
      pointer: "component.interface[4].definition.unit",
      kind: "variable",
      name: "EngineSpeed",
      component: "SensorHub",
      role: "produces",
    },
    {
      path: PUMP,
      pointer: "component.interface[0].definition.unit",
      kind: "variable",
      name: "PumpSpeed",
      component: "Pump",
      role: "local",
    },
  ],
  findings: [],
};

/** kPa's panel: its vocabulary entry, and nothing stating it. */
export const UNUSED_KPA_PANEL: UnitReply = {
  revision: 7,
  unit: "kPa",
  description: "pressure",
  entries: [{ file: UNITS_FILE, pointer: "units[6]" }],
  sites: [],
  findings: [],
};

/** RPM renamed onto rpm, which the vocabulary lists: the two spellings merge (merge.png). */
export const MERGE: PlanReply = {
  revision: 7,
  changes: [
    {
      file: CONTROLLER,
      fingerprint: "5e443ce41f14ce2c5cf6062cad6f583092f065e4901791ae8b63f8667f4bf78d",
      operations: [{ op: "set", pointer: "component.interface[3].definition.unit", raw: '"rpm"' }],
      hunks: [
        { line: 14, before: ['          "unit": "RPM",'], after: ['          "unit": "rpm",'] },
      ],
    },
    {
      file: TYPES,
      fingerprint: "cee6509cdb23a7a9d4daa23fa12f36312dc95ce558a20d8c74c93129bf8ac904",
      operations: [{ op: "set", pointer: "types[0].unit", raw: '"rpm"' }],
      hunks: [{ line: 6, before: ['      "unit": "RPM",'], after: ['      "unit": "rpm",'] }],
    },
  ],
};

/** rpm described anew: its entry in units.ddd.json. */
export const DESCRIPTION: PlanReply = {
  revision: 7,
  changes: [
    {
      file: UNITS_FILE,
      fingerprint: "f4dfde5af01af4f851acf7769078368fe5c90e74482b08df28b52451d7529d04",
      operations: [{ op: "set", pointer: "units[2].description", raw: '"revolutions per minute"' }],
      hunks: [
        {
          line: 6,
          before: [
            '    { "unit": "rpm", "description": "rotational speed, revolutions per minute" },',
          ],
          after: ['    { "unit": "rpm", "description": "revolutions per minute" },'],
        },
      ],
    },
  ],
};

/** RPM added to units.ddd.json, in the form its entries take. */
export const ADDITION: PlanReply = {
  revision: 7,
  changes: [
    {
      file: UNITS_FILE,
      fingerprint: "f4dfde5af01af4f851acf7769078368fe5c90e74482b08df28b52451d7529d04",
      operations: [
        { op: "insert", pointer: "units[7]", raw: '{"unit": "RPM", "description": ""}' },
      ],
      hunks: [
        {
          line: 10,
          before: ['    { "unit": "kPa", "description": "pressure" }'],
          after: [
            '    { "unit": "kPa", "description": "pressure" },',
            '    {"unit": "RPM", "description": ""}',
          ],
        },
      ],
    },
  ],
};

/** kPa taken out of units.ddd.json, with the comma before it. */
export const REMOVAL: PlanReply = {
  revision: 7,
  changes: [
    {
      file: UNITS_FILE,
      fingerprint: "f4dfde5af01af4f851acf7769078368fe5c90e74482b08df28b52451d7529d04",
      operations: [{ op: "remove", pointer: "units[6]", raw: null }],
      hunks: [
        {
          line: 9,
          before: [
            '    { "unit": "ms", "description": "time" },',
            '    { "unit": "kPa", "description": "pressure" }',
          ],
          after: ['    { "unit": "ms", "description": "time" }'],
        },
      ],
    },
  ],
};

/** The units file adoption writes for the project's eight units, line by line. */
const ADOPTED = [
  "{",
  '  "units": [',
  '    {"unit": "%", "description": ""},',
  '    {"unit": "Hz", "description": ""},',
  '    {"unit": "RPM", "description": ""},',
  '    {"unit": "V", "description": ""},',
  '    {"unit": "degC", "description": ""},',
  '    {"unit": "ms", "description": ""},',
  '    {"unit": "rpm", "description": ""},',
  '    {"unit": "°C", "description": ""}',
  "  ]",
  "}",
];

/** Adoption: the project description includes units.ddd.json, which is new (adopt.png). */
export const ADOPTION: PlanReply = {
  revision: 7,
  changes: [
    {
      file: DEMO,
      fingerprint: "c333b9667097f729ecfdadeb89b200663a6783290e4e2e65004cd74b4570a5c0",
      operations: [{ op: "insert", pointer: "project.includes[2]", raw: '"units.ddd.json"' }],
      hunks: [
        {
          line: 7,
          before: ['      "subsystems/logging/logging.ddd.json"'],
          after: ['      "subsystems/logging/logging.ddd.json",', '      "units.ddd.json"'],
        },
      ],
    },
    {
      file: UNITS_FILE,
      fingerprint: null,
      operations: [{ op: "set", pointer: "", raw: ADOPTED.join("\n") }],
      hunks: [{ line: 1, before: [], after: ADOPTED }],
    },
  ],
};
```

- [ ] **Step 2: The failing stories**

One story per state of spec 6. `gui/src/components/UnitsTableView.stories.tsx`:

```tsx
import { useState } from "react";
import { PROJECT_UNITS } from "../stories/fixtures";
import { UnitsTableView } from "./UnitsTableView";

export default { title: "Components / UnitsTableView" };

/** The mockups' nine units with RPM selected: the rows with findings first and marked, then the
 * most stated, and kPa, which nothing states, last. */
export const WithFindings = () => {
  const [selected, setSelected] = useState<string | undefined>("RPM");
  return <UnitsTableView units={PROJECT_UNITS} selected={selected} onSelect={setSelected} />;
};
```

`gui/src/components/UnitPanelView.stories.tsx` - a unit in the vocabulary (its description being edited, so that Save shows), one outside it, one unused, Show changes on a merge, and a refused plan:

```tsx
import { useState } from "react";
import type { PlanReply, ProjectUnit, UnitReply } from "../api/types";
import {
  ADDITION,
  DESCRIPTION,
  LISTED_RPM,
  LISTED_RPM_PANEL,
  MERGE,
  PROJECT_UNITS,
  REMOVAL,
  UNKNOWN_RPM,
  UNKNOWN_RPM_PANEL,
  UNUSED_KPA,
  UNUSED_KPA_PANEL,
} from "../stories/fixtures";
import { type Offer, type UnitAction, UnitPanelView } from "./UnitPanelView";

export default { title: "Components / UnitPanelView" };

interface Props {
  unit: ProjectUnit;
  reply: UnitReply;
  /** The description as the reader has typed it, and the plan that saves it. */
  draft?: { description: string; plan: PlanReply };
  /** The plan of the vocabulary's change the unit's state offers: its addition or its removal. */
  vocabulary?: PlanReply;
  /** The spelling chosen to rename the unit to, and where its rename stands. */
  rename?: { to: string; offer: Offer };
  shown?: UnitAction;
}

/** The panel over one scenario's fixtures, with its own draft, spelling and Show changes, kept
 * as UnitPanel.tsx keeps them: the picker's field reads what is typed, else the spelling chosen,
 * else the unit's own, and its sections are narrowed only by what is typed. */
function View({ unit, reply, draft, vocabulary, rename, shown: initiallyShown }: Props) {
  const [description, setDescription] = useState(draft?.description);
  const [typed, setTyped] = useState<string | undefined>(undefined);
  const [to, setTo] = useState<string | null>(rename?.to ?? null);
  const [shown, setShown] = useState<UnitAction | null>(initiallyShown ?? null);
  const planned =
    vocabulary === undefined ? null : { plan: vocabulary, refusal: null, pending: false };
  return (
    <UnitPanelView
      unit={unit}
      reply={reply}
      units={PROJECT_UNITS}
      description={description ?? unit.description ?? ""}
      onDescription={setDescription}
      typed={typed ?? to ?? unit.unit}
      narrow={typed ?? ""}
      onTyped={setTyped}
      onChosen={(chosen) => {
        setTo(chosen === unit.unit ? null : chosen);
        setTyped(undefined);
      }}
      onPickerClosed={() => setTyped(undefined)}
      to={to}
      describing={
        draft !== undefined && description === draft.description
          ? { plan: draft.plan, refusal: null, pending: false }
          : null
      }
      adding={unit.files.length === 0 ? planned : null}
      removing={unit.files.length === 0 ? null : planned}
      renaming={rename !== undefined && to === rename.to ? rename.offer : null}
      shown={shown}
      onShown={setShown}
      onApply={() => undefined}
      busy={false}
      onClose={() => undefined}
    />
  );
}

export const InTheVocabulary = () => (
  <View
    unit={LISTED_RPM}
    reply={LISTED_RPM_PANEL}
    draft={{ description: "revolutions per minute", plan: DESCRIPTION }}
  />
);

export const OutsideTheVocabulary = () => (
  <View
    unit={UNKNOWN_RPM}
    reply={UNKNOWN_RPM_PANEL}
    vocabulary={ADDITION}
    rename={{ to: "rpm", offer: { plan: MERGE, refusal: null, pending: false } }}
  />
);

export const Unused = () => (
  <View unit={UNUSED_KPA} reply={UNUSED_KPA_PANEL} vocabulary={REMOVAL} />
);

export const MergeChangesShown = () => (
  <View
    unit={UNKNOWN_RPM}
    reply={UNKNOWN_RPM_PANEL}
    vocabulary={ADDITION}
    rename={{ to: "rpm", offer: { plan: MERGE, refusal: null, pending: false } }}
    shown="rename"
  />
);

export const Refused = () => (
  <View
    unit={UNKNOWN_RPM}
    reply={UNKNOWN_RPM_PANEL}
    vocabulary={ADDITION}
    rename={{
      to: "rpm",
      offer: {
        plan: null,
        refusal:
          "types.ddd.json did not load, so renaming 'RPM' could not reach every place it is stated",
        pending: false,
      },
    }}
  />
);
```

`gui/src/components/AdoptBannerView.stories.tsx` - the banner, and its preview shown:

```tsx
import { useState } from "react";
import { ADOPTION, UNADOPTED_UNITS } from "../stories/fixtures";
import { AdoptBannerView, AdoptPanelView } from "./AdoptBannerView";
import { UnitsTableView } from "./UnitsTableView";

export default { title: "Components / AdoptBannerView" };

/** The Units tab of a project with no units file, laid out as UnitsPage.tsx lays it out: the
 * banner, then the table, with the adoption's preview beside it once Show changes opened it. */
function Tab({ previewing = false }: { previewing?: boolean }) {
  const [shown, setShown] = useState(previewing);
  return (
    <>
      <AdoptBannerView
        adoptable={UNADOPTED_UNITS.adoptable ?? 0}
        plan={ADOPTION}
        refusal={null}
        onShowChanges={() => setShown(true)}
        onAdopt={() => undefined}
        busy={false}
      />
      <div className={shown ? "with-panel" : undefined}>
        <div>
          <UnitsTableView
            units={UNADOPTED_UNITS}
            selected={undefined}
            onSelect={() => setShown(false)}
          />
        </div>
        {shown && (
          <AdoptPanelView
            adoptable={UNADOPTED_UNITS.adoptable ?? 0}
            plan={ADOPTION}
            onAdopt={() => undefined}
            busy={false}
            onClose={() => setShown(false)}
          />
        )}
      </div>
    </>
  );
}

export const NoUnitsFile = () => <Tab />;

export const PreviewShown = () => <Tab previewing />;
```

Run: `npm run typecheck`
Expected: FAIL: `error TS2307: Cannot find module './UnitsTableView'`, and the same of `./UnitPanelView` and `./AdoptBannerView`.

- [ ] **Step 3: Show changes, shared, and the picker's label**

Create `gui/src/components/Changes.tsx`, `VariablePanelView`'s private `Changes` moved out and taught one thing, the header of a file the change creates:

```tsx
import type { PlannedChange } from "../api/types";
import { baseName, hunkLines } from "../lib/units";

/**
 * The lines each file will get, as Show changes prints them: a variable's panel, a unit's and
 * the adoption's preview alike. A file the change creates has no line of its own yet, and is
 * named as new.
 */
export function Changes({ changes }: { changes: readonly PlannedChange[] }) {
  return (
    <div className="changes">
      {changes.flatMap((change) =>
        change.hunks.map((hunk) => (
          <pre key={`${change.file} ${hunk.line}`} className="hunk">
            <span className="where">
              {baseName(change.file)}, {change.fingerprint === null ? "new" : `line ${hunk.line}`}
            </span>
            {hunkLines(hunk).map((line) => (
              <span key={line.key} className={line.sign === "-" ? "removed" : "added"}>
                {line.sign} {line.text}
              </span>
            ))}
          </pre>
        )),
      )}
    </div>
  );
}
```

In `gui/src/components/VariablePanelView.tsx`, the imports become

```tsx
import type { SettleReply, UnitsReply, VariableReply } from "../api/types";
import { distinctFindings, keyedFindings } from "../lib/findings";
import { consequence, describe, pickerSections, unitOfDeclaration, willChange } from "../lib/units";
import { Button } from "../ui/Button";
import { Chip } from "../ui/Chip";
import { Panel } from "../ui/Panel";
import { Changes } from "./Changes";
import { UnitPicker } from "./UnitPicker";
```

the picker is given its label in place of its name,

```tsx
      <UnitPicker
        label={`Unit of ${variable.name}`}
```

and the private `Changes` at the end of the file, with its comment, is deleted. What the panel draws is unchanged: the header's text is the same, split differently between text nodes.

`gui/src/components/UnitPicker.tsx` whole - `name` becomes `label`:

```tsx
import { enteredUnit, type UnitSection } from "../lib/units";
import { ComboBox } from "../ui/ComboBox";

interface Props {
  /** What the field is for: "Unit of ValueA", "Rename RPM to". */
  label: string;
  sections: readonly UnitSection[];
  typed: string;
  onTyped: (text: string) => void;
  onPick: (unit: string | null) => void;
  /** The list closed or the field was left: whatever was typed is dropped. */
  onClose: () => void;
  note: string | undefined;
  isDisabled: boolean;
  /** A new value on every request to focus the field; `null` asks for no focus. */
  autoFocus: number | null;
  /** "focus" opens the list as the field takes the focus, for a story to photograph it open. */
  menuTrigger?: "input" | "focus" | undefined;
}

/** A unit to choose - a variable's, or the spelling a unit is renamed to: the sections of
 * lib/units.ts or lib/projectUnits.ts in React Aria's combobox. */
export function UnitPicker({
  label,
  sections,
  typed,
  onTyped,
  onPick,
  onClose,
  note,
  isDisabled,
  autoFocus,
  menuTrigger,
}: Props) {
  return (
    <ComboBox
      label={label}
      inputValue={typed}
      onInputChange={onTyped}
      sections={sections}
      onPick={(id) => {
        const chosen = sections
          .flatMap((section) => section.choices)
          .find((entry) => entry.id === id);
        if (chosen !== undefined) onPick(chosen.unit);
      }}
      onEnter={(text) => {
        const unit = enteredUnit(sections, text);
        if (unit !== undefined) onPick(unit);
      }}
      onClose={onClose}
      note={note}
      isDisabled={isDisabled}
      autoFocus={autoFocus}
      menuTrigger={menuTrigger}
    />
  );
}
```

In `gui/src/components/UnitPicker.stories.tsx`, `name="ValueA"` becomes `label="Unit of ValueA"`.

- [ ] **Step 4: The table**

Create `gui/src/components/UnitsTableView.tsx`:

```tsx
import type { UnitsReply } from "../api/types";
import { descriptionOf, findingCheck, statedBy, unitRows } from "../lib/projectUnits";
import { Chip } from "../ui/Chip";
import { Cell, Column, Row, Table, TableBody, TableHeader } from "../ui/Table";

export interface UnitsTableViewProps {
  units: UnitsReply;
  /** The unit whose panel is open, or `undefined`. */
  selected: string | undefined;
  /** A row selected, or the selected one let go. */
  onSelect: (unit: string | undefined) => void;
}

/** The Units tab's table (spec 5.1), drawn from what the api answered: a picture of its props. */
export function UnitsTableView({ units, selected, onSelect }: UnitsTableViewProps) {
  const rows = unitRows(units.units);
  const hasVocabulary = units.vocabulary !== null;
  return (
    <Table
      aria-label="Units"
      selectionMode="single"
      selectedKeys={new Set(selected === undefined ? [] : [selected])}
      onSelectionChange={(keys) => {
        const key = keys === "all" ? undefined : [...keys][0];
        onSelect(rows.find((row) => row.unit === key)?.unit);
      }}
    >
      <TableHeader>
        <Column isRowHeader>Unit</Column>
        <Column>Description</Column>
        <Column className={also("stated")}>Stated by</Column>
        <Column>Findings</Column>
      </TableHeader>
      <TableBody items={rows}>
        {(row) => {
          const check = findingCheck(row);
          const unused = row.variables + row.types + row.members === 0;
          return (
            <Row id={row.unit} className={also(check === null ? "" : "has-error")}>
              <Cell className={also("unit")}>{row.unit}</Cell>
              <Cell className={also(row.files.length === 0 ? "quiet" : "")}>
                {descriptionOf(row, hasVocabulary)}
              </Cell>
              <Cell className={also(unused ? "stated quiet" : "stated")}>{statedBy(row)}</Cell>
              {/* Both checks are errors unless a build lowers them, which the row's count does not
                  say: the panel shows each finding at its own severity. */}
              <Cell>{check !== null && <Chip tone="error">{check}</Chip>}</Cell>
            </Row>
          );
        }}
      </TableBody>
    </Table>
  );
}

/** React Aria's own class with this table's beside it, since ui.css selects on both: a string
 * would replace React Aria's. */
function also(name: string) {
  return ({ defaultClassName }: { defaultClassName: string | undefined }) =>
    `${defaultClassName ?? ""} ${name}`.trim();
}
```

- [ ] **Step 5: A unit's panel**

Create `gui/src/components/UnitPanelView.tsx`. Top to bottom, as spec 5.2 orders it: the unit and its line, its findings, Where it is stated, then what its state offers - the Description, its removal, its addition - then the rename, always. Each change is a `section` named for the journeys, which have one Show changes per section to press:

```tsx
import type { PlanReply, ProjectUnit, UnitReply, UnitsReply } from "../api/types";
import { distinctFindings, keyedFindings } from "../lib/findings";
import {
  offers,
  placeRole,
  renameConsequence,
  renameSections,
  unitMeta,
} from "../lib/projectUnits";
import { baseName, consequence } from "../lib/units";
import { Button } from "../ui/Button";
import { Chip } from "../ui/Chip";
import { Panel } from "../ui/Panel";
import { Changes } from "./Changes";
import { UnitPicker } from "./UnitPicker";

/** A change a unit's panel applies. */
export type UnitAction = "describe" | "add" | "remove" | "rename";

/** Where one change stands: its plan once it has come, and why it cannot be applied. */
export interface Offer {
  /** The plan; `null` while it is being asked for, or when it was refused. */
  plan: PlanReply | null;
  /** Why the plan was refused, or why applying it was; `null` when neither was. */
  refusal: string | null;
  /** The plan shown is an earlier one's, kept on screen while this one is asked for: a
   * description's, which changes with every key typed. It cannot be applied. */
  pending: boolean;
}

export interface UnitPanelViewProps {
  unit: ProjectUnit;
  reply: UnitReply;
  units: UnitsReply;
  /** What the Description field reads: what is being typed, else the vocabulary's description. */
  description: string;
  onDescription: (text: string) => void;
  /** What the rename picker's field reads: what is being typed, else the spelling chosen, else
   * the unit's own. */
  typed: string;
  /** What narrows the picker's sections: "" unless the reader is typing, as in part 1's panel -
   * opening the picker lists everything, not just what contains the spelling it shows. */
  narrow: string;
  onTyped: (text: string) => void;
  /** A spelling chosen from the picker, or typed and confirmed with Enter. */
  onChosen: (unit: string) => void;
  /** The picker's list closed or its field was left: what was typed there is dropped. */
  onPickerClosed: () => void;
  /** The spelling chosen to rename the unit to, or `null` while none is. */
  to: string | null;
  /** Each change asked for, or `null` while it is not: the description left as it is, no
   * spelling chosen, or a change the unit's state does not offer. */
  describing: Offer | null;
  adding: Offer | null;
  removing: Offer | null;
  renaming: Offer | null;
  /** The change whose lines Show changes has opened, or `null`. */
  shown: UnitAction | null;
  onShown: (action: UnitAction | null) => void;
  onApply: (action: UnitAction) => void;
  /** Applying, or the server stopped: nothing can be changed or applied. */
  busy: boolean;
  onClose: () => void;
}

/** One unit's panel (spec 5.2), drawn from what the api answered: a picture of its props. */
export function UnitPanelView(props: UnitPanelViewProps) {
  const { unit, reply, units, to } = props;
  const hasVocabulary = units.vocabulary !== null;
  const offered = offers(unit, hasVocabulary);
  const outcome = (
    action: UnitAction,
    offer: Offer | null,
    sentence: (plan: PlanReply) => string,
    label: (plan: PlanReply) => string,
  ) => (
    <Outcome
      offer={offer}
      sentence={sentence}
      label={label}
      // The rename is the one change every panel offers, and its button the panel's own.
      variant={action === "rename" ? "primary" : "secondary"}
      shown={props.shown === action}
      onShown={(shown) => props.onShown(shown ? action : null)}
      onApply={() => props.onApply(action)}
      busy={props.busy}
    />
  );
  const files = (plan: PlanReply) => consequence(plan.changes);
  return (
    <Panel title={unit.unit} meta={unitMeta(unit, reply, hasVocabulary)} onClose={props.onClose}>
      {reply.findings.length > 0 && (
        <ul className="panel-findings">
          {keyedFindings(distinctFindings(reply.findings)).map(([finding, key]) => (
            <li key={key}>
              <Chip tone={finding.severity === "error" ? "error" : "warning"}>{finding.check}</Chip>{" "}
              <span className="quiet">{finding.message}</span>
            </li>
          ))}
        </ul>
      )}
      <h3 className="panel-heading">Where it is stated</h3>
      {reply.sites.length === 0 ? (
        <p className="quiet">Nothing in the project states {unit.unit}.</p>
      ) : (
        <table className="panel-declarations">
          <thead>
            <tr>
              <th scope="col">Where</th>
              <th scope="col">File</th>
              <th scope="col">What</th>
            </tr>
          </thead>
          <tbody>
            {reply.sites.map((site) => (
              <tr key={`${site.path} ${site.pointer}`}>
                <td>{site.name}</td>
                <td className="quiet">{baseName(site.path)}</td>
                <td>{placeRole(site)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {offered.describe && (
        <section className="panel-offer" aria-label="Description">
          <label className="panel-field">
            Description
            <input
              type="text"
              value={props.description}
              disabled={props.busy}
              onChange={(event) => props.onDescription(event.target.value)}
            />
          </label>
          {outcome("describe", props.describing, files, () => "Save")}
        </section>
      )}
      {offered.remove && (
        <section className="panel-offer" aria-label="Remove from the vocabulary">
          {outcome("remove", props.removing, files, () => "Remove from the vocabulary")}
        </section>
      )}
      {offered.add && (
        <section className="panel-offer" aria-label="Add to the vocabulary">
          {outcome("add", props.adding, files, () => "Add to the vocabulary")}
        </section>
      )}
      <section className="panel-offer" aria-label="Rename">
        <UnitPicker
          label={`Rename ${unit.unit} to`}
          sections={renameSections(unit.unit, units, props.narrow)}
          typed={props.typed}
          onTyped={props.onTyped}
          onPick={(chosen) => {
            // Only Enter on the no-unit label answers `null` (part 1's rule), and a unit cannot be
            // renamed into none: the rename lists no such entry, and ignores it.
            if (chosen !== null) props.onChosen(chosen);
          }}
          onClose={props.onPickerClosed}
          note={undefined}
          isDisabled={props.busy}
          autoFocus={null}
        />
        <p className="rename-note">
          Only the spelling changes; values, limits and conversions stay as they are.
        </p>
        {to !== null &&
          outcome(
            "rename",
            props.renaming,
            (plan) => renameConsequence(plan, unit, to, units),
            (plan) => `Apply to ${plan.changes.length} file${plan.changes.length === 1 ? "" : "s"}`,
          )}
      </section>
    </Panel>
  );
}

/**
 * One change's part of the panel: why it cannot be applied, if it cannot; then, once its plan has
 * come, what it changes, the lines it changes once Show changes opens them, and the button that
 * applies it. A change refused on Apply - a file changed on disk - says so above the plan asked
 * for again, which the reader then applies or not.
 */
function Outcome({
  offer,
  sentence,
  label,
  variant,
  shown,
  onShown,
  onApply,
  busy,
}: {
  offer: Offer | null;
  sentence: (plan: PlanReply) => string;
  label: (plan: PlanReply) => string;
  variant: "primary" | "secondary";
  shown: boolean;
  onShown: (shown: boolean) => void;
  onApply: () => void;
  busy: boolean;
}) {
  if (offer === null) return null;
  const { plan, refusal } = offer;
  return (
    <>
      {refusal !== null && (
        <p className="panel-refusal" role="status">
          {refusal}
        </p>
      )}
      {plan !== null && <p className="consequence">{sentence(plan)}</p>}
      {plan !== null && plan.changes.length > 0 && (
        <>
          {shown && <Changes changes={plan.changes} />}
          <div className="panel-actions">
            <Button variant="link" onPress={() => onShown(!shown)}>
              {shown ? "Hide changes" : "Show changes"}
            </Button>
            <Button variant={variant} isDisabled={busy || offer.pending} onPress={onApply}>
              {label(plan)}
            </Button>
          </div>
        </>
      )}
    </>
  );
}
```

- [ ] **Step 6: The adoption banner and its preview**

Create `gui/src/components/AdoptBannerView.tsx`:

```tsx
import type { PlanReply } from "../api/types";
import { adoptionSentence } from "../lib/projectUnits";
import { consequence } from "../lib/units";
import { Banner } from "../ui/Banner";
import { Button } from "../ui/Button";
import { Panel } from "../ui/Panel";
import { Changes } from "./Changes";

export interface AdoptBannerViewProps {
  /** How many units adoption would list: 0 for a project that states none. */
  adoptable: number;
  /** The adoption's plan once it has come; `null` while it is asked for, or when it was refused. */
  plan: PlanReply | null;
  /** Why the plan was refused, or why applying it was; `null` when neither was. */
  refusal: string | null;
  /** Opens the adoption's preview in the panel beside the table. */
  onShowChanges: () => void;
  onAdopt: () => void;
  /** Adopting, or the server stopped: nothing can be adopted. */
  busy: boolean;
}

/** The banner above the table of a project with no units file (spec 5.3): a picture of its
 * props. */
export function AdoptBannerView({
  adoptable,
  plan,
  refusal,
  onShowChanges,
  onAdopt,
  busy,
}: AdoptBannerViewProps) {
  return (
    <Banner tone="warning">
      <div className="adopt-banner">
        <p>{adoptionSentence(adoptable)}</p>
        {plan !== null && plan.changes.length > 0 && (
          <div className="adopt-actions">
            <Button variant="link" onPress={onShowChanges}>
              Show changes
            </Button>
            <Button variant="primary" isDisabled={busy} onPress={onAdopt}>
              {adoptLabel(adoptable)}
            </Button>
          </div>
        )}
      </div>
      {refusal !== null && <p className="adopt-refusal">{refusal}</p>}
    </Banner>
  );
}

export interface AdoptPanelViewProps {
  adoptable: number;
  plan: PlanReply;
  onAdopt: () => void;
  busy: boolean;
  /** Closes the preview: its Close and its Hide changes alike. */
  onClose: () => void;
}

/** The adoption's preview in the panel beside the table (spec 5.3): the project description's
 * new line and the new file, then Adopt. A picture of its props. */
export function AdoptPanelView({ adoptable, plan, onAdopt, busy, onClose }: AdoptPanelViewProps) {
  return (
    <Panel title="Adopt a vocabulary" meta={consequence(plan.changes)} onClose={onClose}>
      <Changes changes={plan.changes} />
      <div className="panel-actions">
        <Button variant="link" onPress={onClose}>
          Hide changes
        </Button>
        <Button variant="primary" isDisabled={busy} onPress={onAdopt}>
          {adoptLabel(adoptable)}
        </Button>
      </div>
    </Panel>
  );
}

function adoptLabel(adoptable: number): string {
  return `Adopt ${adoptable} unit${adoptable === 1 ? "" : "s"}`;
}
```

- [ ] **Step 7: The styles**

In `gui/src/styles/ui.css`, before `/* The project screen's tabs, moved out of app.css unchanged. */`, tokens only:

```css
/* The Units tab (docs/superpowers/specs/2026-09-19-gui-units-project-design.md, 5): the table's
   spelling in bold and its count to the right; a unit's panel - its sub-heading, each change it
   offers set apart, the Description field and the line under the rename; and the adoption
   banner, its sentence beside its two buttons and a refusal under both. */
.react-aria-Cell.unit {
  font-weight: 600;
}
.react-aria-Column.stated,
.react-aria-Cell.stated {
  text-align: right;
  white-space: nowrap;
}
.panel-heading {
  margin: var(--space-3) 0 var(--space-1);
  font-size: var(--text-small);
  font-weight: 600;
}
.panel-offer {
  margin-top: var(--space-3);
}
.panel-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  color: var(--ink-quiet);
  font-size: var(--text-small);
}
.panel-field input {
  padding: var(--cell);
  background: var(--surface);
  border: 1px solid var(--rule);
  border-radius: var(--radius);
  color: var(--ink);
  font: inherit;
  font-size: var(--text-body);
}
.panel-field input:disabled {
  background: var(--ground);
}
.rename-note {
  margin: var(--space-1) 0 0;
  color: var(--ink-quiet);
  font-size: var(--text-small);
}
.adopt-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}
.adopt-banner p {
  margin: 0;
}
.adopt-actions {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  gap: var(--space-3);
  white-space: nowrap;
}
.adopt-refusal {
  margin: var(--space-2) 0 0;
}
```

Run: `npm run lint && npm run typecheck && npm test && npm run build && npm run ladle:build`
Expected: PASS; `gui/ladle-build/meta.json` lists the eight new stories beside part 1's nineteen.

- [ ] **Step 8: The references, in Playwright's image, on the Linux PC**

```bash
cd ..
UPDATE=1 docker compose run --rm gui-screenshots
docker compose run --rm gui-screenshots
git status --short gui/screenshots/references
```

Expected: the first run writes eight references; the second compares all 27 stories and passes; `git status` lists exactly these eight as new, and none of part 1's nineteen as modified - `VariablePanelView` and the picker look as they did. If one of those is modified, stop: a picture of part 1 changed.

- `components--unitstableview--with-findings.png`
- `components--unitpanelview--in-the-vocabulary.png`
- `components--unitpanelview--outside-the-vocabulary.png`
- `components--unitpanelview--unused.png`
- `components--unitpanelview--merge-changes-shown.png`
- `components--unitpanelview--refused.png`
- `components--adoptbannerview--no-units-file.png`
- `components--adoptbannerview--preview-shown.png`

Open every one and look at it. The table: RPM and °C first, each with a red inset and an `unknown-unit` chip, RPM's row selected, "not in the vocabulary" in quiet ink, the counts right-aligned, kPa last and "unused". In the vocabulary: rpm, its two places, "revolutions per minute" in the Description, "Changes 1 file: units.ddd.json", Show changes and Save, then "Rename rpm to" reading rpm over the note. Outside it: RPM's finding once, EngineSpeed reads and Speed_t scalar type, Add to the vocabulary with its consequence, then the merge's sentence and Apply to 2 files. Unused: "Nothing in the project states kPa.", its Description and Remove from the vocabulary. The merge: the same, with the two hunks of `RPM` becoming `rpm` under the rename. Refused: the refusal in warning ink where the rename's consequence was, and no Apply. The banner: its sentence beside Show changes and Adopt 8 units, above eight rows with an empty Description; the preview: the same with "Adopt a vocabulary" beside the table, demo.ddd.json's line 7 and "units.ddd.json, new" with twelve added lines. None may show a spinner or an empty page.

- [ ] **Step 9: Commit**

From the repository root:

```bash
git add gui/src/components gui/src/stories/fixtures.ts gui/src/styles/ui.css gui/screenshots/references
git commit -m "draw the units tab's table, a unit's panel and the adoption banner as pictures of their props, with a story for each state"
git push
```

---

### Task 8: The Units tab

**Files:**
- Create: `gui/src/screens/UnitPanel.tsx`, `gui/src/screens/UnitsPage.tsx`
- Modify: `gui/src/app/App.tsx` (the third tab)
- Test: `gui/e2e/project-units.spec.ts` (new); `gui/e2e/fixtures.ts` (`vocabularyGui`), `gui/e2e/demo.ts` (`PUMP`, `UNITS`, `driftIn`), `gui/e2e/units.spec.ts` (the policy journey visits the Units tab)

**Interfaces:**
- Consumes: Tasks 6 and 7.
- Produces:

```ts
// screens/UnitsPage.tsx
UnitsPage({ state, unit, stopped, onUnit }: {
  state: State | null;
  unit: string | undefined;
  stopped: boolean;
  onUnit: (unit: string | undefined) => void;
})
// screens/UnitPanel.tsx
UnitPanel({ name, revision, stopped, onClose, onGone, onMoved }: {
  name: string;
  revision: number | undefined;
  stopped: boolean;
  onClose: () => void;
  onGone: () => void; // nothing states or lists the unit any longer
  onMoved: (unit: string | undefined) => void; // renamed, or removed, from this panel
})
usePlan(request: UnitPlanRequest | null, revision: number | undefined, keep?: boolean)
refusalOf(error: Error): string
// e2e/fixtures.ts: `vocabularyGui: Gui`, ddd gui over a copy of examples/vocabulary
// e2e/demo.ts: PUMP, UNITS, driftIn(directory: string, file: string, variable: string, unit: string): Buffer
```

- [ ] **Step 1: The journeys, and watch them fail**

`gui/e2e/fixtures.ts` serves a copy of either example; `gui` and `bareGui` stay the demo's:

```ts
import { type ChildProcess, spawn } from "node:child_process";
import { cpSync } from "node:fs";
import { join } from "node:path";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";
import { test as base, type TestInfo } from "@playwright/test";

const EXAMPLES = fileURLToPath(new URL("../../examples/", import.meta.url));

/** An example the journeys serve a copy of: its directory under examples/, and its project. */
interface Example {
  directory: string;
  project: string;
}

const DEMO: Example = { directory: "demo", project: "demo.ddd.json" };
/** The example with a units file, which part 2's journeys rename and describe units in. */
const VOCABULARY: Example = { directory: "vocabulary", project: "project.ddd.json" };

export interface Gui {
  /** The address ddd gui printed, token included. */
  address: string;
  /** The copy of the example the server edits, under this test's own output directory. */
  directory: string;
  /** Stops the server; stopping twice is harmless. */
  stop: () => Promise<void>;
}

/** `ddd gui` over a fresh copy of an example, with its project named or not. */
async function started(
  example: Example,
  named: boolean,
  use: (gui: Gui) => Promise<void>,
  testInfo: TestInfo,
): Promise<void> {
  // Under test-results/, which Playwright empties at the start of every run: a failed journey
  // then keeps its copy beside its trace, and nothing here has to remove it.
  const directory = testInfo.outputPath(example.directory);
  cpSync(join(EXAMPLES, example.directory), directory, { recursive: true });
  const project = named ? [join(directory, example.project)] : [];
  // python -m ddd rather than the ddd launcher: on Windows the launcher starts python as a child
  // of its own, which killing the launcher leaves running, holding the port and the copy.
  const child = spawn(
    process.env.DDD_PYTHON ?? "python",
    ["-m", "ddd", "gui", ...project, "--no-browser"],
    {
      cwd: directory,
      stdio: ["ignore", "pipe", "inherit"],
    },
  );
  let stopped = false;
  const stop = async () => {
    if (!stopped) {
      stopped = true;
      await terminated(child);
    }
  };
  try {
    await use({ address: await served(child), directory, stop });
  } finally {
    await stop();
  }
}

function served(child: ChildProcess): Promise<string> {
  return new Promise((resolve, reject) => {
    if (child.stdout === null) {
      reject(new Error("ddd gui has no stdout"));
      return;
    }
    createInterface({ input: child.stdout }).on("line", (line) => {
      const found = /serving (\S+)/.exec(line);
      if (found?.[1] !== undefined) resolve(found[1]);
    });
    child.once("exit", (code) => reject(new Error(`ddd gui exited with ${code} before serving`)));
  });
}

function terminated(child: ChildProcess): Promise<void> {
  return new Promise((resolve) => {
    if (child.exitCode !== null || child.signalCode !== null) {
      resolve();
      return;
    }
    child.once("exit", () => resolve());
    child.kill();
  });
}

export const test = base.extend<{ gui: Gui; bareGui: Gui; vocabularyGui: Gui }>({
  // biome-ignore lint/correctness/noEmptyPattern: Playwright reads a fixture's dependencies from this pattern
  gui: async ({}, use, testInfo) => started(DEMO, true, use, testInfo),
  // biome-ignore lint/correctness/noEmptyPattern: Playwright reads a fixture's dependencies from this pattern
  bareGui: async ({}, use, testInfo) => started(DEMO, false, use, testInfo),
  // biome-ignore lint/correctness/noEmptyPattern: Playwright reads a fixture's dependencies from this pattern
  vocabularyGui: async ({}, use, testInfo) => started(VOCABULARY, true, use, testInfo),
});

export { expect } from "@playwright/test";
```

In `gui/e2e/demo.ts`, after `SENSOR_HUB`:

```ts
/** The files of examples/vocabulary the journeys change, in its copy: the component stating its
 * units, and the units file listing them. */
export const PUMP = "pump.ddd.json";
export const UNITS = "units.ddd.json";
```

and `drift` becomes the demo's case of `driftIn`:

```ts
/** Controller's reading of a variable drifted to another unit, saved from outside - ValueA's to
 * `rpm` unless said otherwise; answers the file as it was before. */
export function drift(directory: string, variable = "ValueA", unit = "rpm"): Buffer {
  return driftIn(directory, CONTROLLER, variable, unit);
}

/** A variable's unit in one file of a copy drifted to another spelling, saved from outside;
 * answers the file as it was before. */
export function driftIn(directory: string, file: string, variable: string, unit: string): Buffer {
  const path = join(directory, file);
  const before = readFileSync(path);
  writeFileSync(path, withUnitOf(before, variable, unit));
  return before;
}
```

Create `gui/e2e/project-units.spec.ts`. The rename journey takes one spelling from the list with a click and the other by typing it and pressing Enter; the names are the examples' own (Facts checked):

```ts
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { driftIn, PUMP, UNITS } from "./demo";
import { expect, test } from "./fixtures";

/** The entries of a units file as it stands on disk: objects, in both examples' units files. */
function entriesOf(file: string): { unit: string; description: string }[] {
  return (
    JSON.parse(readFileSync(file, "utf8")) as { units: { unit: string; description: string }[] }
  ).units;
}

/** The demo's units in use, as adoption lists them: sorted, code unit by code unit. */
const DEMO_UNITS = ["%", "Hz", "V", "degC", "ms"];

test("adopting writes the units in use into a units file the project includes, and reports nothing more", async ({
  page,
  gui,
}) => {
  const adopted = join(gui.directory, UNITS);
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Table" }).click();
  const summary = page.locator(".summary");
  await expect(summary).toBeVisible();
  const reported = await summary.innerText();

  await page.getByRole("link", { name: "Units" }).click();
  await expect(page).toHaveURL(/\?view=units$/);
  await expect(page.getByText("5 units · no units file")).toBeVisible();
  // Without a units file, a unit's panel says where it is stated, and nothing of a vocabulary.
  await page.getByRole("row", { name: "ms", exact: true }).click();
  const ms = page.getByRole("complementary", { name: "ms" });
  await expect(ms.getByText("stated in 1 place, 1 file", { exact: true })).toBeVisible();
  const banner = page.getByRole("status").filter({ hasText: "This project has no units file" });
  await expect(banner).toContainText("with the 5 units in use");
  await banner.getByRole("button", { name: "Show changes" }).click();
  const preview = page.getByRole("complementary", { name: "Adopt a vocabulary" });
  await expect(preview.getByText("Changes 2 files: demo.ddd.json, units.ddd.json")).toBeVisible();
  await expect(preview.getByText("units.ddd.json, new")).toBeVisible();
  await preview.getByRole("button", { name: "Adopt 5 units" }).click();

  // The file created, listing every unit in use, and included in the project.
  await expect.poll(() => existsSync(adopted)).toBe(true);
  expect(entriesOf(adopted)).toEqual(DEMO_UNITS.map((unit) => ({ unit, description: "" })));
  const project = JSON.parse(readFileSync(join(gui.directory, "demo.ddd.json"), "utf8"));
  expect(project.project.includes).toContain(UNITS);
  await expect(page.getByText("5 units · all in the vocabulary")).toBeVisible();
  await expect(banner).toHaveCount(0);
  await expect(preview).toHaveCount(0);

  // Every unit is in the vocabulary now, with a description to write.
  for (const unit of DEMO_UNITS) {
    await page.getByRole("row", { name: unit, exact: true }).click();
    const panel = page.getByRole("complementary", { name: unit });
    await expect(panel.getByText("in the vocabulary, units.ddd.json")).toBeVisible();
    await expect(panel.getByRole("textbox", { name: "Description" })).toHaveValue("");
  }

  // And nothing is reported that was not reported before.
  await page.getByRole("link", { name: "Table" }).click();
  await expect(summary).toHaveText(reported);
});

test("a unit renamed from its panel is renamed everywhere, merging into the vocabulary's spelling", async ({
  page,
  vocabularyGui,
}) => {
  const pump = join(vocabularyGui.directory, PUMP);
  const units = join(vocabularyGui.directory, UNITS);
  // PumpSpeed's unit drifted to a spelling the vocabulary does not list, saved from outside.
  const before = driftIn(vocabularyGui.directory, PUMP, "PumpSpeed", "RPM");
  const vocabulary = readFileSync(units);
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Units" }).click();
  await expect(page.getByText("5 units · 1 not in the vocabulary")).toBeVisible();
  // Its finding puts it first.
  await expect(page.getByRole("rowheader").first()).toHaveText("RPM");
  await page.getByRole("row", { name: "RPM", exact: true }).click();

  const panel = page.getByRole("complementary", { name: "RPM" });
  await expect(panel.getByText("not in the vocabulary · stated in 1 place, 1 file")).toBeVisible();
  await expect(panel.getByText("unknown-unit", { exact: true })).toBeVisible();
  const renaming = panel.getByRole("region", { name: "Rename" });
  const picker = renaming.getByRole("combobox", { name: "Rename RPM to" });

  // Taken from the list: another unit of the vocabulary, which RPM would merge into.
  await renaming.getByRole("button", { name: "Show the choices for Rename RPM to" }).click();
  await page.getByRole("option", { name: "kPa", exact: true }).click();
  await expect(picker).toHaveValue("kPa");
  await expect(
    renaming.getByText(
      "Changes 1 file: pump.ddd.json. kPa is in the vocabulary already, so RPM merges into it.",
    ),
  ).toBeVisible();

  // Typed and confirmed with Enter: the spelling the finding suggests.
  await picker.fill("rpm");
  await picker.press("Enter");
  await expect(picker).toHaveValue("rpm");
  await expect(
    renaming.getByText(
      "Changes 1 file: pump.ddd.json. rpm is in the vocabulary already, so RPM merges into it.",
    ),
  ).toBeVisible();
  await renaming.getByRole("button", { name: "Show changes" }).click();
  await expect(renaming.locator(".hunk .removed")).toHaveText(['- "unit": "RPM",']);
  await expect(renaming.locator(".hunk .added")).toHaveText(['+ "unit": "rpm",']);
  await renaming.getByRole("button", { name: "Apply to 1 file" }).click();

  // The file is as it was before the drift, and the vocabulary untouched: rpm was listed.
  await expect.poll(() => readFileSync(pump).equals(before)).toBe(true);
  expect(readFileSync(units).equals(vocabulary)).toBe(true);
  // The panel follows the unit to its one spelling; the other is gone from the tab, unannounced.
  const merged = page.getByRole("complementary", { name: "rpm" });
  await expect(
    merged.getByText("in the vocabulary, units.ddd.json · stated in 1 place, 1 file"),
  ).toBeVisible();
  await expect(page).toHaveURL(/\?view=units&unit=rpm$/);
  await expect(page.getByRole("row", { name: "RPM", exact: true })).toHaveCount(0);
  await expect(page.getByText("4 units · all in the vocabulary")).toBeVisible();
  await expect(page.getByText("no longer stated or listed")).toHaveCount(0);
});

test("the vocabulary is described, added to and pruned from the units' panels", async ({
  page,
  vocabularyGui,
}) => {
  const units = join(vocabularyGui.directory, UNITS);
  // ManifoldPressure's unit drifted to a spelling the vocabulary does not list; PressureTrend
  // still states kPa.
  driftIn(vocabularyGui.directory, PUMP, "ManifoldPressure", "mbar");
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Units" }).click();
  await expect(page.getByText("5 units · 1 not in the vocabulary")).toBeVisible();

  // Described: its entry's description, written on Save.
  await page.getByRole("row", { name: "rpm", exact: true }).click();
  const rpm = page.getByRole("complementary", { name: "rpm" });
  const describing = rpm.getByRole("region", { name: "Description" });
  const description = describing.getByRole("textbox", { name: "Description" });
  await expect(description).toHaveValue("rotational speed, revolutions per minute");
  await description.fill("revolutions per minute");
  await expect(describing.getByText("Changes 1 file: units.ddd.json")).toBeVisible();
  await describing.getByRole("button", { name: "Save" }).click();
  await expect
    .poll(() => entriesOf(units)[0])
    .toEqual({ unit: "rpm", description: "revolutions per minute" });
  await expect(describing.getByText("Changes 1 file")).toHaveCount(0);
  await expect(description).toHaveValue("revolutions per minute");

  // Added: the unit outside the vocabulary, in the form the file's entries take.
  await page.getByRole("row", { name: "mbar", exact: true }).click();
  const mbar = page.getByRole("complementary", { name: "mbar" });
  await expect(mbar.getByText("not in the vocabulary · stated in 1 place, 1 file")).toBeVisible();
  const adding = mbar.getByRole("region", { name: "Add to the vocabulary" });
  await expect(adding.getByText("Changes 1 file: units.ddd.json")).toBeVisible();
  await adding.getByRole("button", { name: "Show changes" }).click();
  await expect(adding.locator(".hunk .added").last()).toContainText('"mbar"');
  await adding.getByRole("button", { name: "Add to the vocabulary" }).click();
  await expect.poll(() => entriesOf(units)).toContainEqual({ unit: "mbar", description: "" });
  await expect(
    mbar.getByText("in the vocabulary, units.ddd.json · stated in 1 place, 1 file"),
  ).toBeVisible();
  await expect(mbar.getByRole("textbox", { name: "Description" })).toHaveValue("");

  // Removed: a unit nothing states, and its panel with it, without a word of its going.
  await page.getByRole("row", { name: "degC", exact: true }).click();
  const degC = page.getByRole("complementary", { name: "degC" });
  await expect(degC.getByText("in the vocabulary, units.ddd.json · stated nowhere")).toBeVisible();
  const removing = degC.getByRole("region", { name: "Remove from the vocabulary" });
  await removing.getByRole("button", { name: "Remove from the vocabulary" }).click();
  await expect
    .poll(() => entriesOf(units).map((entry) => entry.unit))
    .toEqual(["rpm", "Nm", "kPa", "mbar"]);
  await expect(degC).toHaveCount(0);
  await expect(page.getByRole("row", { name: "degC", exact: true })).toHaveCount(0);
  await expect(page).toHaveURL(/\?view=units$/);
  await expect(page.getByText("no longer stated or listed")).toHaveCount(0);
});

test("an apply made from a panel that is out of date is refused, and the panel shows the files as they are", async ({
  page,
  vocabularyGui,
}) => {
  const units = join(vocabularyGui.directory, UNITS);
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Units" }).click();
  await page.getByRole("row", { name: "degC", exact: true }).click();
  const panel = page.getByRole("complementary", { name: "degC" });
  const removing = panel.getByRole("region", { name: "Remove from the vocabulary" });
  await expect(removing.getByText("Changes 1 file: units.ddd.json")).toBeVisible();

  // Described from outside between the preview and Apply.
  await page.route("**/api/edit", async (route) => {
    writeFileSync(
      units,
      readFileSync(units, "utf8").replace('"temperature"', '"temperature, degrees Celsius"'),
    );
    await route.continue();
  });
  await removing.getByRole("button", { name: "Remove from the vocabulary" }).click();
  await expect(removing.getByRole("status").filter({ hasText: "changed on disk" })).toBeVisible();
  await expect(panel.getByRole("textbox", { name: "Description" })).toHaveValue(
    "temperature, degrees Celsius",
  );
  expect(entriesOf(units).map((entry) => entry.unit)).toContain("degC");

  // Chosen again, on the files as they are now, it is applied.
  await page.unroute("**/api/edit");
  await removing.getByRole("button", { name: "Remove from the vocabulary" }).click();
  await expect
    .poll(() => entriesOf(units).map((entry) => entry.unit))
    .toEqual(["rpm", "Nm", "kPa"]);
});

test("a unit nothing states any longer closes its panel and the tab says so, but not while a file does not load", async ({
  page,
  vocabularyGui,
}) => {
  const pump = join(vocabularyGui.directory, PUMP);
  const before = driftIn(vocabularyGui.directory, PUMP, "PumpSpeed", "RPM");
  const drifted = readFileSync(pump);
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Units" }).click();
  await page.getByRole("row", { name: "RPM", exact: true }).click();
  const panel = page.getByRole("complementary", { name: "RPM" });
  const picker = panel.getByRole("combobox", { name: "Rename RPM to" });
  await expect(picker).toBeVisible();
  await expect(page).toHaveURL(/\?view=units&unit=RPM$/);
  const bookmark = page.url();

  // Saved half-edited, as an editor saves a file being typed into: nothing that loads states RPM,
  // but the file that does not load may, and the panel stays, naming it.
  writeFileSync(pump, drifted.subarray(0, Math.floor(drifted.length / 2)));
  await expect(panel.getByRole("alert")).toContainText("pump.ddd.json");
  await expect(page).toHaveURL(/\?view=units&unit=RPM$/);
  writeFileSync(pump, drifted);
  await expect(picker).toBeVisible();

  // Renamed back from outside: nothing states RPM any longer, and its panel closes, saying so.
  writeFileSync(pump, before);
  const gone = page
    .getByRole("status")
    .filter({ hasText: "RPM is no longer stated or listed in the open project." });
  await expect(gone).toBeVisible();
  await expect(panel).toHaveCount(0);
  await expect(page).toHaveURL(/\?view=units$/);

  // Another unit selected, the banner has said what it had to.
  await page.getByRole("row", { name: "rpm", exact: true }).click();
  await expect(page.getByRole("complementary", { name: "rpm" })).toBeVisible();
  await expect(gone).toHaveCount(0);

  // An address naming it from before - a bookmark - is answered the same way.
  await page.goto(bookmark);
  await expect(gone).toBeVisible();
  await expect(page.getByRole("complementary", { name: "RPM" })).toHaveCount(0);
  await expect(page).toHaveURL(/\?view=units$/);
});
```

In `gui/e2e/units.spec.ts`, "no page reports a violation of its content security policy" visits the Units tab after reopening DemoDevice, before the Table tab:

```ts
  // The Units tab: a unit's panel with a rename's changes shown, then - the demo having no units
  // file - the adoption's preview in its place.
  await page.getByRole("link", { name: "Units" }).click();
  await page.getByRole("row", { name: "rpm", exact: true }).click();
  const unit = page.getByRole("complementary", { name: "rpm" });
  const rename = unit.getByRole("combobox", { name: "Rename rpm to" });
  await rename.fill("%");
  await rename.press("Enter");
  await unit.getByRole("button", { name: "Show changes" }).click();
  await expect(unit.locator(".hunk")).toBeVisible();
  await page
    .getByRole("status")
    .filter({ hasText: "no units file" })
    .getByRole("button", { name: "Show changes" })
    .click();
  const adoption = page.getByRole("complementary", { name: "Adopt a vocabulary" });
  await expect(adoption.getByText("units.ddd.json, new")).toBeVisible();
```

Run: `npm run build && PLAYWRIGHT_CHANNEL=chrome npm run e2e`
Expected: FAIL: the five journeys of `project-units.spec.ts` and the policy journey time out on `getByRole("link", { name: "Units" })`; the other 24 pass.

- [ ] **Step 2: A unit's panel**

Create `gui/src/screens/UnitPanel.tsx`, after `VariablePanel.tsx`: every query keyed by the revision, `not-found` closing the panel from an effect and `unreadable` keeping it, a stale refusal said in place, and Apply posting `planEdit(plan)` to `POST /api/edit`:

```tsx
import { skipToken, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import {
  ApiError,
  getUnit,
  getUnitPlan,
  getUnits,
  postEdit,
  type UnitPlanRequest,
} from "../api/client";
import { type Offer, type UnitAction, UnitPanelView } from "../components/UnitPanelView";
import { offers, planEdit } from "../lib/projectUnits";
import { Banner } from "../ui/Banner";
import { Panel } from "../ui/Panel";

interface Props {
  name: string;
  revision: number | undefined;
  stopped: boolean;
  onClose: () => void;
  /** Nothing in the open project states or lists the unit: the tab closes the panel, saying why. */
  onGone: () => void;
  /** Renamed or removed from this panel: the tab opens the new spelling's panel, or none. */
  onMoved: (unit: string | undefined) => void;
}

/** What the tab says when an edit it posted was refused: stale, as part 1's panel says it, or the
 * server's own reason. */
export function refusalOf(error: Error): string {
  return error instanceof ApiError && error.code === "stale"
    ? "A file changed on disk, so nothing was written. The page now shows the files as they are."
    : `The change was refused: ${error.message}`;
}

/**
 * One plan, asked for again at every revision - an Apply spends the fingerprints it carries - and
 * not asked for at all while `request` is `null`.
 *
 * `keep` leaves the last plan on screen while the next is asked for, marked as a placeholder, for
 * a description: its plan changes with every key typed, and only in the text it writes, so the
 * line saying which file it changes would otherwise blink at every key.
 */
export function usePlan(
  request: UnitPlanRequest | null,
  revision: number | undefined,
  keep = false,
) {
  return useQuery({
    queryKey: ["unit-plan", request, revision],
    queryFn: request === null ? skipToken : () => getUnitPlan(request),
    placeholderData: (previous) => (keep ? previous : undefined),
  });
}

/** One unit's panel: where it is stated, its vocabulary entry, and a spelling to rename it to. */
export function UnitPanel({ name, revision, stopped, onClose, onGone, onMoved }: Props) {
  const queries = useQueryClient();
  const reply = useQuery({
    queryKey: ["unit", name, revision],
    queryFn: () => getUnit(name),
    placeholderData: (previous) => previous,
  });
  const units = useQuery({
    queryKey: ["units", revision],
    queryFn: () => getUnits(),
    placeholderData: (previous) => previous,
  });
  // Set once this panel renamed or removed its unit: the unit is then gone because the reader
  // asked, and the panel moves on without the tab saying that it disappeared.
  const moving = useRef(false);
  // Spec 5.4: a unit renamed or removed from outside - or named by an address nothing states or
  // lists, such as an old bookmark - is gone, and its panel closes, the tab saying why. While a
  // file does not load the server cannot say that, and answers `unreadable` instead: the panel
  // then stays, naming the file, and shows the unit again once the file loads.
  const gone = reply.error instanceof ApiError && reply.error.code === "not-found";
  useEffect(() => {
    if (gone && !moving.current) onGone();
  }, [gone, onGone]);

  // What the reader types into the Description field, `undefined` until they do: the field then
  // reads the vocabulary's description.
  const [description, setDescription] = useState<string | undefined>(undefined);
  // The spelling chosen to rename the unit to, `null` until one is; and what is being typed into
  // the picker, `undefined` whenever its list is closed - the field then reads the spelling
  // chosen, else the unit's own, as part 1's picker reads the unit settled on.
  const [to, setTo] = useState<string | null>(null);
  const [typed, setTyped] = useState<string | undefined>(undefined);
  const [shown, setShown] = useState<UnitAction | null>(null);
  const [failed, setFailed] = useState<{ action: UnitAction; message: string } | null>(null);

  const row = units.data?.units.find((entry) => entry.unit === name);
  const offered =
    row === undefined || units.data === undefined
      ? null
      : offers(row, units.data.vocabulary !== null);
  const draft =
    description !== undefined && description !== (row?.description ?? "") ? description : null;
  const plans = {
    describe: usePlan(
      offered?.describe && draft !== null
        ? { action: "describe", unit: name, description: draft }
        : null,
      revision,
      true,
    ),
    add: usePlan(offered?.add ? { action: "add", unit: name } : null, revision),
    remove: usePlan(offered?.remove ? { action: "remove", unit: name } : null, revision),
    rename: usePlan(to === null ? null : { action: "rename", unit: name, to }, revision),
  };
  const apply = useMutation({
    mutationFn: (action: UnitAction) => {
      const plan = plans[action].data;
      const edit = plan === undefined ? null : planEdit(plan);
      if (edit === null) throw new Error("there is nothing to change");
      return postEdit(edit);
    },
    onMutate: () => setFailed(null),
    // Renamed, the unit is the new spelling now, and the tab opens its panel; removed, it is gone
    // as the reader asked. Neither is the unit disappearing that spec 5.4 has the tab announce.
    onSuccess: (_reply, action) => {
      setShown(null);
      if (action === "rename" && to !== null) {
        moving.current = true;
        onMoved(to);
      } else if (action === "remove") {
        moving.current = true;
        onMoved(undefined);
      }
    },
    onError: (error, action) => setFailed({ action, message: refusalOf(error) }),
    // An Apply changes the unit's places, the tab's rows and every plan, whose fingerprints the
    // edit spent: they are asked for again, and nothing can be applied until they answer. The
    // description saved is let go only then, so that the field goes from what was typed straight
    // to the vocabulary's new description, and never back through the old one.
    onSettled: async (_reply, error, action) => {
      await Promise.all([
        queries.invalidateQueries({ queryKey: ["unit"] }),
        queries.invalidateQueries({ queryKey: ["units"] }),
        queries.invalidateQueries({ queryKey: ["unit-plan"] }),
      ]);
      if (error === null && action === "describe") setDescription(undefined);
    },
  });
  /** Where a change stands: its plan, and why it was refused - on Apply, else when asked for. */
  const offer = (action: UnitAction): Offer => ({
    plan: plans[action].data ?? null,
    refusal: failed?.action === action ? failed.message : (plans[action].error?.message ?? null),
    pending: plans[action].isPlaceholderData,
  });

  if (gone) return null;
  if (reply.isError) {
    return (
      <Panel title={name} onClose={onClose}>
        <Banner tone="error">{reply.error.message}</Banner>
      </Panel>
    );
  }
  if (reply.data === undefined || units.data === undefined || row === undefined) {
    return (
      <Panel title={name} onClose={onClose}>
        <p className="quiet">Reading {name}…</p>
      </Panel>
    );
  }
  return (
    <UnitPanelView
      unit={row}
      reply={reply.data}
      units={units.data}
      description={description ?? row.description ?? ""}
      onDescription={(text) => {
        setDescription(text);
        setFailed(null);
      }}
      typed={typed ?? to ?? name}
      // Never the spelling chosen: opening the picker on it must still list everything.
      narrow={typed ?? ""}
      onTyped={setTyped}
      onChosen={(chosen) => {
        // The unit's own spelling renames nothing: choosing it goes back to no rename at all.
        setTo(chosen === name ? null : chosen);
        setTyped(undefined);
        setFailed(null);
      }}
      onPickerClosed={() => setTyped(undefined)}
      to={to}
      // Nothing is said of a description left as it is: the plan kept for the last key typed
      // (usePlan) would otherwise still show once the text is the vocabulary's again.
      describing={draft === null ? null : offer("describe")}
      adding={offer("add")}
      removing={offer("remove")}
      renaming={offer("rename")}
      shown={shown}
      onShown={setShown}
      onApply={(action) => apply.mutate(action)}
      busy={stopped || apply.isPending}
      onClose={onClose}
    />
  );
}
```

- [ ] **Step 3: The tab**

Create `gui/src/screens/UnitsPage.tsx`:

```tsx
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { getUnits, postEdit } from "../api/client";
import type { State } from "../api/types";
import { AdoptBannerView, AdoptPanelView } from "../components/AdoptBannerView";
import { UnitsTableView } from "../components/UnitsTableView";
import { planEdit, tabTitle } from "../lib/projectUnits";
import { Banner } from "../ui/Banner";
import { refusalOf, UnitPanel, usePlan } from "./UnitPanel";

interface Props {
  state: State | null;
  /** The unit whose panel is open, as the address names it. */
  unit: string | undefined;
  stopped: boolean;
  onUnit: (unit: string | undefined) => void;
}

/** The open project's Units tab (spec 5.1): every unit it states or lists, the panel of the one
 * selected, and adoption for a project with no units file (spec 5.3). */
export function UnitsPage({ state, unit, stopped, onUnit }: Props) {
  const queries = useQueryClient();
  const revision = state?.revision;
  const units = useQuery({
    queryKey: ["units", revision],
    queryFn: () => getUnits(),
    // The table stays while the next revision's units are read: swapped for a loading line on
    // every edit, it lost the reader's place and made the tab flash.
    placeholderData: (previous) => previous,
  });
  // The unit whose panel closed because nothing states or lists it any longer (spec 5.4), named
  // above the table until another unit is selected or the reader leaves the tab.
  const [gone, setGone] = useState<string | null>(null);
  // Whether the adoption's preview is open, in the panel's place beside the table.
  const [previewing, setPreviewing] = useState(false);
  const [refused, setRefused] = useState<string | null>(null);
  const adoptable = units.data?.adoptable ?? null;
  // Asked for as soon as the banner offers it, so that Adopt applies exactly what Show changes
  // shows; a project stating no unit has nothing to adopt, and nothing is asked.
  const adoption = usePlan(
    adoptable !== null && adoptable > 0 ? { action: "adopt" } : null,
    revision,
  );
  const adopt = useMutation({
    mutationFn: () => {
      const edit = adoption.data === undefined ? null : planEdit(adoption.data);
      if (edit === null) throw new Error("there is nothing to adopt");
      return postEdit(edit);
    },
    onMutate: () => setRefused(null),
    onSuccess: () => setPreviewing(false),
    onError: (error) => setRefused(refusalOf(error)),
    // Adopting changes every row and every plan: they are asked for again, and nothing can be
    // adopted a second time while they are.
    onSettled: () =>
      Promise.all([
        queries.invalidateQueries({ queryKey: ["units"] }),
        queries.invalidateQueries({ queryKey: ["unit"] }),
        queries.invalidateQueries({ queryKey: ["unit-plan"] }),
      ]),
  });

  if (units.data === undefined) {
    if (units.isError) return <Banner tone="error">{units.error.message}</Banner>;
    return <p className="quiet">Reading the project's units…</p>;
  }
  const select = (next: string | undefined) => {
    setGone(null);
    setPreviewing(false);
    onUnit(next);
  };
  const preview = unit === undefined && previewing ? (adoption.data ?? null) : null;
  return (
    <>
      <p className="summary">{tabTitle(units.data.units, units.data.vocabulary !== null)}</p>
      {/* A server that stopped answering leaves the table as it was, and says so above it. */}
      {units.isError && <Banner tone="error">{units.error.message}</Banner>}
      {gone !== null && (
        <Banner tone="warning">{gone} is no longer stated or listed in the open project.</Banner>
      )}
      {adoptable !== null && (
        <AdoptBannerView
          adoptable={adoptable}
          plan={adoption.data ?? null}
          refusal={refused ?? adoption.error?.message ?? null}
          onShowChanges={() => {
            select(undefined);
            setPreviewing(true);
          }}
          onAdopt={() => adopt.mutate()}
          busy={stopped || adopt.isPending}
        />
      )}
      <div className={unit !== undefined || preview !== null ? "with-panel" : undefined}>
        <div>
          <UnitsTableView units={units.data} selected={unit} onSelect={select} />
        </div>
        {unit !== undefined ? (
          <UnitPanel
            key={unit}
            name={unit}
            revision={revision}
            stopped={stopped}
            onClose={() => onUnit(undefined)}
            onGone={() => {
              setGone(unit);
              onUnit(undefined);
            }}
            onMoved={select}
          />
        ) : (
          preview !== null && (
            <AdoptPanelView
              adoptable={adoptable ?? 0}
              plan={preview}
              onAdopt={() => adopt.mutate()}
              busy={stopped || adopt.isPending}
              onClose={() => setPreviewing(false)}
            />
          )
        )}
      </div>
    </>
  );
}
```

- [ ] **Step 4: The third tab**

In `gui/src/app/App.tsx`, import `UnitsPage` from `"../screens/UnitsPage"` after `StartPage`; before `App`:

```tsx
/** The project screen's tabs, in the order they are shown. */
const PROJECT_VIEWS = [
  ["graph", "Graph"],
  ["table", "Table"],
  ["units", "Units"],
] as const;
```

after `openVariable`:

```tsx
  // Selecting a unit replaces the address, as selecting a variable does.
  const openUnit = useCallback(
    (unit: string | undefined) =>
      navigate(
        unit === undefined
          ? { page: "project", view: "units" }
          : { page: "project", view: "units", unit },
        { replace: true },
      ),
    [navigate],
  );
```

and the project page's tabs and views:

```tsx
        <LinkTabs
          label="Project views"
          tabs={PROJECT_VIEWS.map(([view, label]) => ({
            href: hrefOf({ page: "project", view }),
            label,
            current: route.view === view,
            onFollow: () => navigate({ page: "project", view }),
          }))}
        />
        {route.view === "graph" ? (
          <GraphPage
            project={opened.path}
            state={state}
            variable={route.variable}
            stopped={stopped}
            onComponent={openComponent}
            onVariable={openVariable}
          />
        ) : route.view === "units" ? (
          <UnitsPage state={state} unit={route.unit} stopped={stopped} onUnit={openUnit} />
        ) : (
          <ProjectPage state={state} onComponent={openComponent} />
        )}
```

The units view is reached by its own `route.view === "units"`, never as what is left once `"table"` is ruled out: the graph-or-table member's `view` is a union, which `!== "table"` does not narrow away, and `route.unit` would not type-check.

- [ ] **Step 5: Run the gate, then commit**

Run: `npm run lint && npm run typecheck && npm test && npm run build && npm run ladle:build && PLAYWRIGHT_CHANNEL=chrome npm run e2e`
Expected: PASS; 30 journeys, 13 in `skeleton.spec.ts`, 12 in `units.spec.ts` and 5 in `project-units.spec.ts`. On the Windows PC: `DDD_PYTHON=/c/git/ac11/ddd/.venv/Scripts/python.exe PLAYWRIGHT_CHANNEL=msedge npm run e2e`. No story changed, so the screenshot service need not run.

From the repository root:

```bash
git add gui/src/screens/UnitPanel.tsx gui/src/screens/UnitsPage.tsx gui/src/app/App.tsx gui/e2e
git commit -m "add the units tab: every unit the project states, renamed, described, added, removed and adopted from its panel"
git push
```

---

### Task 9: The documentation

**Files:**
- Modify: `CHANGELOG.md`, `docs/command_line_interface.rst`, `docs/editor_integration.rst`, `docs/developer_documentation.rst`, `docs/file_formats/units.rst`

**Interfaces:**
- Consumes: what Tasks 1 to 8 built, read from their code: the Units tab (Task 8), the plans (`ddd.lsp.units`, Task 2), the language server's rename and quick fixes (Task 3), the edit engine creating a file (Task 4).
- Produces: nothing a later task reads.

- [ ] **Step 1: What a user reads**

- `CHANGELOG.md`, Unreleased:
  - In the `ddd gui` preview entry, one paragraph for the Units tab. Cover every unit the project states or its vocabulary lists, with where each is stated. Cover renaming a unit everywhere, including a merge into a unit that exists. Cover describing, adding and removing vocabulary units, and adopting a vocabulary for a project without one, which reports nothing it did not report before. Say that every change is previewed and written to every file or none.
  - In the language server's entry: Rename Symbol on a unit, with the same reach and merge, refused while a project file does not load; and on `unknown-unit`, "Add … to the vocabulary" and "Rename … to … everywhere" for each close unit.
  - In the checks' entry: `unknown-unit` suggests a spelling that differs only in case, as `RPM` suggests `rpm` (Task 3's `close_units`).
- `docs/command_line_interface.rst`, the `ddd gui [PROJECT]` row: the project page gains a Units tab listing the project's units and maintaining its vocabulary.
- `docs/editor_integration.rst`:
  - Where it lists what Rename Symbol renames, add units: from any place a unit is stated, or from its vocabulary entry. A rename onto a unit that exists merges the two.
  - Where it lists the quick fixes, add the two on `unknown-unit`.
  
  Read the page first, and say only what Task 3's code does.
- `docs/file_formats/units.rst`, where it quotes `unknown-unit`'s suggestion: a spelling in another case is suggested too.

- [ ] **Step 2: What a developer reads**

`docs/developer_documentation.rst`, "The browser interface":
- The plans. `ddd.lsp.units` plans each change to the project's units once, as operations on JSON pointers. The language server renders a plan as text edits, and `ddd gui` previews it and posts it to `POST /api/edit`; that is why the two can never disagree.
- The one thing the edit engine learnt. A change whose fingerprint is `null` creates its file. It is accepted beside the project description only when the same edit includes it. The file takes the owner and mode of the project description.

- [ ] **Step 3: The documentation build and the Python gate, then commit**

Run the documentation build in the development image (Global Constraints), then `python -m pytest tests/test_documentation.py --no-cov`, then the whole Python gate.

```bash
git add CHANGELOG.md docs/command_line_interface.rst docs/editor_integration.rst docs/developer_documentation.rst docs/file_formats/units.rst
git commit -m "say what the units tab, the unit rename and the vocabulary's quick fixes do, and how both clients share one plan"
git push
```

---

### Task 10: Milestone gate

Done by the controlling session, not by an implementer.

- [ ] **Step 1: The whole gate, from a clean build**

```bash
rm -rf src/ddd/gui/static gui/src/generated gui/test-results gui/ladle-build build/docs_out
python -m pytest && python -m ruff format --check . && python -m ruff check . && python -m mypy
docker compose run --rm --user "$(id -u):$(id -g)" -e JAVA_TOOL_OPTIONS=-Duser.home=/tmp ddd python -m sphinx -M html docs build/docs_out -W
cd gui && npm ci && npm run schemas && npm run lint && npm run typecheck && npm test && npm run build && npm run ladle:build && PLAYWRIGHT_CHANNEL=chrome npm run e2e
cd .. && docker compose run --rm gui-screenshots
git status --short
```

Expected: every step green; `git status` shows nothing but the untracked `.claude/`.

- [ ] **Step 2: The Units tab in the real application**

`docker compose up gui` on the Linux PC serves `examples/demo`, which has no units file.
1. Adopt a vocabulary from the Units tab. Check `demo.ddd.json` includes `units.ddd.json`, the new file belongs to your user with the project file's mode, and no finding appears.
2. Rename one of its units into another, as a merge, and describe one.
3. Take screenshots of the tab, a unit's panel, Show changes on the merge and the adoption preview, for the pull request.
4. Leave `examples/demo` as it was: `git checkout -- examples/demo && rm -f examples/demo/units.ddd.json`, then `git status --short`.

Then serve a copy of `examples/vocabulary` under `build/` with `ddd gui` from the venv. Drift one declaration's unit to `RPM` from outside, and merge it back into `rpm` from its panel, typing `rpm` and pressing Enter.

- [ ] **Step 3: Hand over**

Report:
- the gate's result and the screenshots;
- what part 2 does and does not do;
- every ruling taken while executing;
- what it leaves for part 3.

Update the pull request's description, and ask before marking it ready for review.

---

## Progress log

| Task | Started | Duration | Tokens | Notes |
| --- | --- | --- | --- | --- |
| 1 | 09:35 | 10 min | ~257k | The index records every place a unit is stated and every vocabulary entry, and `units_in_use` counts from it. Review clean, no findings. |
| 2 | 09:45 | 29 min | ~459k | The five plans. Its review found the new module sorting `Path` objects, which order differently on Windows and Linux, where the loader's own include expansion sorts by posix spelling; one fix round settled it everywhere in the file. |
| 3 | 10:14 | 25 min | ~498k | Rename Symbol on a unit, and the two quick fixes on `unknown-unit`. Review clean. Its one question - whether the quick fixes should pass the gate the rename now passes - was ruled below. |
| 4 | 10:39 | 24 min | ~387k | The edit engine creates a file. Review clean: the confinement was checked against `..`, symlinks and respelled paths, and the window between the must-not-exist check and the rename was ruled below. |
| 5 | 11:03 | 28 min | ~545k | The three endpoints, blank query values kept, part 1's contract widened. Review clean, no findings. |
| 6 | 11:31 | 15 min | ~314k | The page's calls, its pure logic and the Units tab's route. Review clean; the generated types matched the plan's own expectations exactly. |
| 7 | 11:46 | 20 min | ~373k | The tab's widgets, and a story with its reference for every state. Part 1's journeys ran too, since the picker's prop was renamed; none of its references changed. Review clean. |
| 8 | 12:06 | 37 min | ~484k | The tab's screens and five journeys - the first run they ever had. The stale journey raced the server's once-a-second poll and now waits for its re-analysis, as milestone 1's own stale journey does. Review clean. |
| 9 | 12:43 | 35 min | ~595k | The documentation. Its review found a refusal paragraph that read as covering the unit rename, which is refused only while a file does not load, and a "part 1" label no published page defines; one fix round. |
| Final review | 14:00 | 20 min | ~334k | The whole branch: ready to merge, nothing Critical or Important. Every deferred minor was triaged "can wait", and nine rulings were confirmed against the code. It ran on sonnet: the account's weekly Opus limit was exhausted (ruling below). |
| 10 | 14:25 | 55 min | controller | The gate from a clean build: Python 3593 at 100 %, ruff, mypy, the documentation from nothing, Vitest 150, the build, Ladle, 30 journeys in Chrome, 27 stories in Playwright's image. Its first run failed on three demo tests: the final reviewer had driven the checkout's own `examples/demo` rather than a copy, and left `degC` renamed to `Hz` there; restored, and the gate then passed. Then `docker compose up gui`: the demo adopted a vocabulary, a unit was described, a spelling drifted in from outside was merged back by typing and pressing Enter, the created file came out owned by the user with the project description's mode, and no page reported a policy violation. The screenshots are beside this plan in `2026-09-19-gui-units-project/`. |

## Left open by the implementers

The minor findings of the task reviews, which the final whole-branch review triaged as able to wait, and the one it found itself. The maintainer decides which, if any, must be fixed before merging.

- Task 2: `remove_unit` repeats `_known`'s not-found message inline rather than calling it.
- Task 4: `_confined` recomputes `_included` once per created file (one today); no test of `_put_back` failing to unlink a created file during a rollback.
- Task 6: `renameSections` repeats part 1's `pickerSections`' narrowing and typed-section logic, over different choice shapes.
- Task 7: `UnitPanelView` repeats `VariablePanelView`'s findings list; a tie in the table's order falls to code-unit spelling (`V`, `degC` before `rpm`), where the mockup shows another order.
- Task 8: a unit's panel keeps one refusal message for all its actions, so trying Remove clears a Save refusal shown beside it; and a plan refetched right after a stale refusal can carry the old fingerprint until the server's once-a-second poll re-analyses, so an immediate retry is refused again. The second is shared with part 1's variable panel, and is out as a follow-up.
- Task 9: the command page's `ddd gui` row says "tab" twice in close succession.
- Found by the final review: `variables.preview` sorts `Path` objects, the ordering hazard this branch fixed next door in `lsp/units.py`; it is part 1's code, and goes out as a follow-up.
- Found while writing the plan, in part 1's code: `pickerSections` gives a unit the vocabulary lists twice two entries with one id.

## Rulings made while writing and executing the plan

Rulings 1 to 33 were taken while writing the plan, on 2026-09-19.

1. **A created file is one `set` at the root pointer.** The engine has no `add` operation. The spec's section 4.3 said `add`, and was corrected in the plan's first commit. Cost if wrong: none.
2. **Adoption refuses whenever `units.ddd.json` exists**, not only when it exists and is not a units file, as the spec says. A units file the project does not include is a question for the reader, not something adoption should quietly include. Cost if wrong: the reader includes that file by hand.
3. **The rename quick fix is offered once for each close unit**, up to the three `close_units` finds. The finding already names them all, and choosing among them is the reader's job. Cost if wrong: two actions more in an editor's list.
4. **`close_units` lives in `analysis.py`**, and `_check_units` builds its suggestion from it. That way the quick fix and the finding cannot come to disagree about which units are close. Cost if wrong: none.
5. **"The first units file the includes list" is read from the project description's own `project.includes`, in order.** The workspace sorts what it loads, so that order is lost there. Cost if wrong: a new unit lands in a different units file of a project that has several.
6. **The task bodies were drafted by four subagents from the skeleton's interfaces, then reviewed and assembled by the controlling session.** Each drafter checked its code against the source, and every deviation from the interfaces is ruled on below. Cost if wrong: an interface mismatch between two tasks, which the first task that consumes it finds.
7. **`UnitRefusal` is `UnitRefusalError`**: ruff's N818 refuses an exception class without the suffix, and every exception of ddd ends in `Error`. Cost if wrong: none.
8. **`Index.vocabulary` is read from a new `Workspace.unit_entries`**, every entry of every units file: the loader's registry keeps only the first of a unit listed twice, and a rename would reach one entry of two. Cost if wrong: none.
9. **`units_in_use(built)` loses its `cache` parameter**, unused once it counts from `Index.units`; its one caller and part 1's test change with it. Cost if wrong: none.
10. **`ddd.loading.expand_include` is made public**, so `unit_project` expands an include by the loader's own rule, not a copy of it. Cost if wrong: none.
11. **Adoption is refused while any vocabulary exists** - one of the description's own units files, or an entry in `Index.vocabulary`, such as a sub-project's units file - since adopting beside it would list every unit twice. Cost if wrong: none.
12. **Every raw a plan writes is `json.dumps(…, ensure_ascii=False)`**: the engine keeps a literal as spelled, and the default wrote `°C` as `"\u00b0C"`. Cost if wrong: none.
13. **A removal or a merge that would empty a units file is refused as `invalid`**: a units file lists at least one unit, and the engine would write one that no longer loads. Cost if wrong: the reader removes the file by hand.
14. **Add refuses an empty unit, one with spaces around it, and one listed already; describe refuses a unit stated but not listed; for describe and remove, the units file they edit is the one holding the entry**, or every units file when no loaded entry lists the unit, which answers `unreadable` rather than `not-found`. Cost if wrong: none.
15. **Each plan checks its refusals in a fixed order**, the first that applies winning, as Task 2 lists them. Cost if wrong: a less helpful refusal when two apply.
16. **An included file that does not parse is no units file** to `unit_project`, since its kind cannot be told. Cost if wrong: an addition lands in the next units file.
17. **The adopted file writes one entry per line**, `{ "unit": "rpm", "description": "" }`, laid out by the engine's `lay_out`, as the chosen mockup and `examples/vocabulary` write it. Cost if wrong: a layout.
18. **"Did not load" is one notion for both clients**: `LOAD_CHECKS` moves to `ddd.lsp.navigation`, where `Loaded.unloaded` is built from it and passed as `UnitProject.unread` by the language server; the page reads `SourceFile.loaded`. A unit listed twice is merged at both entries in an editor as on the page; a file that loaded with another error no longer stops a unit plan. The variable rename and the other code actions still refuse on `unreadable`. Cost if wrong: a unit rename past a file with another error.
19. **`close_units` ignores case**, so `unknown-unit` on `RPM` suggests `rpm` and the quick fix offers that rename - the design's own example, which the check's case-sensitive match never found. Every message quoted in a test or a page keeps its words. Cost if wrong: a suggestion more where only case differs.
20. **The language server's side**: `actions` takes `project: UnitProject | None = None`; the drift check is `unit_drift` in `ddd.lsp.units`, run before planning; the `UnitProject` is built only when the client sent an `unknown-unit` finding; the quick fixes drop an `EditError`; `text_edits` merges edits that meet and raises for a created file; `ddd.lsp.units` never imports `ddd.lsp.edits`. Cost if wrong: none.
21. **`ddd.editing.edited`, `ddd.variables.planned` and `hunks` are made public** rather than imported by private names; a project description changed on disk since the preview is refused `stale`; an `includes` entry names a new file only literally. Cost if wrong: none.
22. **Task 5 gives part 1's four `UnitsReply` literals the new fields**, and part 1's three exact-body `/api/units` tests compare `revision`, `vocabulary` and `used`. Cost if wrong: none.
23. **`ProjectUnit.findings` counts every filed copy**, a `duplicate-unit` twice; the page says each finding once. Cost if wrong: a count one higher than the chips.
24. **`/api/unit-plan`'s parameters**: an empty `unit` is a `400`; an empty `to` reaches the plan and comes back `invalid`; a parameter an action does not take is ignored. `/api/unit` reuses part 1's `_undeclared`; with no index, `/api/unit-plan` answers `409 unreadable`. Cost if wrong: none.
25. **The server keeps blank query values**, so `description=` clears a description; `/api/file` and `/api/settle` read a blank value as a missing one and answer as before, pinned over real HTTP. Cost if wrong: none.
26. **The page's names beyond the interfaces**: `projectUnits.ts` also exports `descriptionOf`, `findingCheck` and `placeRole`; `Changes` moves into `components/Changes.tsx`; `AdoptPanelView` shows spec 5.3's preview; `UnitPicker`'s `name` becomes `label`; `UnitPanel.tsx` exports `usePlan` and `refusalOf`; `getUnit` and `getUnitPlan` take the client's trailing `fetchImpl`. Cost if wrong: none.
27. **Every change a panel offers has its consequence line, Show changes and its button** (spec 1.7), though spec 5.2 names Show changes for adding and renaming only; the rename's Apply is the primary button. Cost if wrong: a link more.
28. **The tab's summary line sits under the tabs**, as the Table tab's does, not beside the project's heading as in the mockups, and reads "4 units · all in the vocabulary" when nothing is outside it. Cost if wrong: a line's place.
29. **The table's chip is inferred from the count**, `unknown-unit` outside the vocabulary and `duplicate-unit` inside it; units with findings come first even when nothing states them. Cost if wrong: a chip whose tone a build lowered.
30. **After its own rename the panel follows the unit to its new spelling; after its own removal it closes**, neither with spec 5.4's banner, which is for a unit gone from outside. Cost if wrong: none.
31. **A description's plan is asked for at each change of the field**, the last kept on screen with Save disabled until the next arrives; the field is a labelled `<input>`, not a new `ui/` widget. Cost if wrong: requests while typing.
32. **A fifth journey covers spec 5.4**: a unit gone from outside, a bookmark naming it, and the panel staying while a file does not load. Cost if wrong: none.
33. **The drafters verified their code on scratch copies**: Tasks 1 to 5 pass the Python gate together at 100 %, and Tasks 6 to 8 pass lint, typecheck, Vitest at 100 %, build and Ladle with Task 5's types in place. The journeys are type-checked only until Tasks 1 to 5 exist to serve them. Cost if wrong: a journey's first run finds what reading could not.

Rulings 34 to 44 were taken executing the plan, on 2026-09-19 and 2026-09-20, in the controlling session's ledger:

34. **Work in place** on `feature/gui-units-project` in the main checkout, no linked worktree: the venv's editable install points at this checkout's `src/`, as for part 1. Cost if wrong: a second session in this checkout collides with this one.
35. **Implementers and task reviews on sonnet**, the final whole-branch review on the most capable model available. Cost if wrong: tokens.
36. **Task 7 ran part 1's journeys as well as its own gate**, since it renamed a prop of `UnitPicker`, which those journeys drive. Cost if wrong: a few minutes.
37. **Task 8's journeys were its failing tests**: never run while the plan was written, run against Tasks 1 to 7 and made to pass. Cost if wrong: none.
38. **Task 6 began with `npm run schemas` and a typecheck**, and a difference between the generated types and the plan's own expectation would have been fixed in the page code, not the contract. There was none. Cost if wrong: a contract field shaped for the page's convenience.
39. **An implementer keeps the co-author trailer its own harness gives it**, which names the model that wrote the commit; no pushed commit is rewritten. Cost if wrong: none.
40. **Every collection of paths in `lsp/units.py` is sorted by its posix spelling** (Task 2's review): `Path` orders case-insensitively on Windows and by code point on Linux, and the loader's own include expansion already sorted this way. Cost if wrong: none.
41. **The unit quick fixes keep the gate every code action has** - withheld while any file had an error from the read - although the explicit rename passes a narrower one (Task 3). Cost if wrong: no unit quick fix in an editor while a units file lists a unit twice; the rename and the page still work.
42. **The created file's must-not-exist check stands where the edit is computed** (Task 4), as an ordinary edit's fingerprint check does, rather than being made atomic at the rename with a hard link, which not every filesystem or bind mount offers. Cost if wrong: a `units.ddd.json` written by another program in that window is overwritten.
43. **The final whole-branch review ran on sonnet**: the account's weekly Opus limit was exhausted for two days, and every task's own review was already clean behind it. Cost if wrong: a less searching final review than part 1's.
44. **No fix wave followed the final review**, which left nothing Critical or Important; its one Minor is part 1's code and goes out as a follow-up rather than a controller fix that would skip review. Cost if wrong: part 1 keeps an ordering difference between Windows and Linux that it has shipped with since it merged.
