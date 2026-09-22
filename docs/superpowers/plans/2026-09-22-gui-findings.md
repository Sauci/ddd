# Findings you can act on (part 4) implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every finding `ddd gui` reports leads to what it names - the variable's panel, a unit's, a component's page - a Findings tab lists them all worst first, and the one fix the GUI has nowhere to put is offered there.

**Architecture:** A new `ddd.finding_routes` turns a finding's own file and pointer into where it leads, and `GET /api/state` answers that beside each finding; a new `ddd.finding_fixes` plans the one fix a finding carries as `ddd.editing` operations, which `GET /api/fix` previews and `POST /api/edit` applies. The page gains a Findings tab in the Units tab's shape - a table and a panel - and the lists that already exist become links. Beside it, one rule for what a value is: `ddd.lsp.edits.settle` compares what a value means rather than its json text, which serves both clients and deletes the layer part 3 added to work around it.

**Tech Stack:** Python 3.12+ with pydantic; React 19.3, TypeScript 7 strict, TanStack Query 5, `react-aria-components` 1.21.1, `@ladle/react` 5.1.1, Vitest, Playwright 1.63.0 and its image `mcr.microsoft.com/playwright:v1.63.0-noble`.

**Spec:** `docs/superpowers/specs/2026-09-22-gui-findings-design.md` (part 4; read it before starting any task). Parts 1 to 3 - `2026-09-18-gui-units-design.md`, `2026-09-19-gui-units-project-design.md`, `2026-09-20-gui-other-keys-design.md` and their plans - describe the panel, the Units tab, the preview-and-apply path and the screenshot tests this builds on.

## Global Constraints

- Python floor 3.12; **no new runtime dependency** of the Python package, and no new frontend dependency.
- Python gate: `python -m pytest` at 100 % line **and** branch coverage, `ruff check .`, `ruff format --check .`, `mypy`. No `pragma: no cover`, no `pytest.skip`/`skipif`/`xfail`/`importorskip`.
- Line length 100; ruff selects E, F, W, I, N, UP, B, SIM, RUF, ANN, PTH, C4; mypy strict with the pydantic plugin.
- **The Python gate runs in every task that touches Python, the documentation, `gui/scripts/licenses.mjs` or anything `tests/test_documentation.py` reads.**
- Every request and answer of the API is declared in `src/ddd/gui/contract.py`; the page's types are generated from it by `npm run schemas` into the git-ignored `gui/src/generated/`, and only `gui/src/api/types.ts` is committed. Never hand-write a type the generator produces.
- Values travel as **raw JSON text**; pointers are DDD's own spelling (`component.interface[0].definition.unit`, `types[1].members[0].unit`).
- **No check changes.** What the analysis reports, and at what severity, is untouched by this branch: `tests/test_analysis.py` passes unchanged.
- **The language server's behaviour changes once, deliberately** (Task 1) and nowhere else: a reconcile action is no longer offered for a value that already means the same. Every other action it offers, and every rename, stays as it is.
- Vitest keeps its 100 % gate over `src/api`, `src/lib`, `src/state`. Components and screens are covered by stories, screenshot tests and end-to-end journeys - **do not write a Vitest test for a component or a screen**.
- **A story imports nothing from `@ladle/react`.** A story is a plain exported function component holding its own state.
- The Content-Security-Policy stays `default-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'none'`, and `gui/public/pressable.css` stays linked from `gui/index.html` under the id `react-aria-pressable-style`. No page may report a violation.
- **A React Aria `className` is a function keeping `defaultClassName`** when a class is added; `gui/src/components/UnitsTableView.tsx` is the working example.
- **A new or changed story gets its screenshot reference made in Playwright's image** - `UPDATE=1 docker compose run --rm gui-screenshots`, then `docker compose run --rm gui-screenshots` - and every new or changed reference is opened and looked at. References are made nowhere else, and no comparison is loosened.
- **The journeys drive the compiled pages**: `npm run build` before `npm run e2e`, always.
- `ddd gui` stays labelled **preview**.
- Two machines:
  - **Linux PC** (`/home/sauci/Documents/Github/ddd`): `export PATH="$HOME/.local/node-v24.21.0/bin:$PWD/.venv/bin:$PATH"; export DDD_PYTHON="$PWD/.venv/bin/python"` at the repository root. Journeys: `cd gui && npm run build && PLAYWRIGHT_CHANNEL=chrome npm run e2e`. The documentation builds in the development image: `docker compose run --rm --user "$(id -u):$(id -g)" -e JAVA_TOOL_OPTIONS=-Duser.home=/tmp ddd python -m sphinx -M html docs build/docs_out -W`. Docker cannot see the session's scratchpad; a throwaway copy Docker must read goes under the ignored `build/`.
  - **Windows PC** (Git Bash): `export PATH="/c/git/ac11/ddd/.venv/Scripts:/c/Program Files/nodejs:/c/Users/lmbsog0/AppData/Local/Programs/CLion/bin/mingw/bin:$PATH" && cd /c/git/ac11/ddd`; journeys with `DDD_PYTHON=/c/git/ac11/ddd/.venv/Scripts/python.exe PLAYWRIGHT_CHANNEL=msedge npm run e2e`. No Docker: screenshot references are made on the Linux PC or read from CI.

## Prerequisites (before Task 1)

- The branch `feature/gui-findings` starts from master after #52 (`764340e`); the spec is its first commit (`55b2af2`). The pull request is opened when the branch is finished.
- The venv has `pip install -e ".[dev]"`, `gui/` has `npm ci`, and the gate is green on the branch before anything changes: the Python gate, and `cd gui && npm run schemas && npm run lint && npm run typecheck && npm test && npm run build`.

## Conventions for every task

- Work on `feature/gui-findings`. Tests first: write the failing test, watch it fail, implement, watch it pass.
- One commit per task (a fix round may add commits), its message a lowercase sentence saying what the change does, ending with a blank line and a `Co-Authored-By:` line naming the model that wrote it. Push after each task.
- Before a task's commit, run the gate for what it touched: the Python gate for Python (and per the constraint above); `npm run lint && npm run typecheck && npm test && npm run build` for the page, `npm run build && PLAYWRIGHT_CHANNEL=chrome npm run e2e` when a screen or journey changed, and the screenshot service when a story changed.
- After Task 3 and after Task 4, `npm run schemas` regenerates `gui/src/generated/api.ts`; run it before any frontend task.
- Scratch files go to the session scratchpad, never into the repository.

## File structure

| File | Responsibility |
| --- | --- |
| `src/ddd/lsp/edits.py` | `settle` and `_assign` compare what a value means, so neither client offers to rewrite a line to a value it already means (Task 1). |
| `src/ddd/variables.py` | `narrowed` and `_differs` go, part 3's workaround being the rule now; `preview` sorts paths by their posix spelling (Task 1). |
| `src/ddd/finding_routes.py` (new) | Where a finding leads: a variable, a unit, a component, or nothing. Pure - no GUI, no HTTP (Task 2). |
| `src/ddd/finding_fixes.py` (new) | The fixes a finding carries, as `ddd.editing` operations: an identity for a producing declaration without one (Task 4). |
| `src/ddd/gui/contract.py`, `src/ddd/gui/api.py` | `Finding.route` on `GET /api/state` (Task 3); `GET /api/fix` (Task 4). |
| `tests/test_finding_routes.py`, `tests/test_finding_fixes.py` (new) | The routes and the fixes, case by case (Tasks 2 and 4). |
| `tests/test_settle.py`, `tests/test_lsp.py`, `tests/test_variables.py`, `tests/test_gui_api.py` | The one rule's effect on both clients (Task 1); the endpoints (Tasks 3 and 4). |
| `gui/src/api/types.ts`, `gui/src/api/client.ts` | The generated route and fix types re-exported; `getFix` (Tasks 3 and 4). |
| `gui/src/lib/findings.ts` | The tab's order, its counts, and what each route says and leads to. Pure (Task 5). |
| `gui/src/lib/route.ts` | `view: "findings"` (Task 7). |
| `gui/src/components/FindingsTableView.tsx`, `FindingPanelView.tsx` (new) | The table and the panel as pictures of their props, with stories (Task 6). |
| `gui/src/screens/FindingsPage.tsx` (new) | The tab: the selected finding, its fix and the apply (Task 7). |
| `gui/src/app/App.tsx`, `gui/src/screens/ComponentPage.tsx`, `gui/src/components/VariablePanelView.tsx` | The fourth tab, and the lists that become links (Task 7). |
| `gui/src/screens/VariablePanel.tsx`, `gui/src/screens/UnitPanel.tsx` | A stale refusal waits for the next revision before offering Apply again (Task 8). |
| `gui/src/stories/fixtures.ts`, `gui/src/styles/ui.css` | What the stories draw, and the tab's own rules (Task 6). |
| `gui/e2e/findings.spec.ts` (new), `gui/e2e/demo.ts`, `gui/e2e/units.spec.ts` | The journeys, and the policy journey visiting the new tab (Task 9). |
| `CHANGELOG.md`, `docs/command_line_interface.rst`, `docs/developer_documentation.rst`, `docs/editor_integration.rst` | What a user and a developer read (Task 10). |

## Interfaces between the tasks

Every name here is exact; a task's implementer sees only their own task, and this is how they learn what their neighbours produce and consume.

**Task 2 produces** (`src/ddd/finding_routes.py`):

```python
@dataclass(frozen=True, slots=True)
class Route:
    """Where a finding leads."""

    kind: str          # "variable" | "unit" | "component"
    name: str | None   # the variable's name, the unit's spelling; None for a component

def route_of(
    check: str,
    path: Path,
    pointer: str,
    kind: str,          # the file's own kind: "component", "types", "units", "project", …
    loaded: bool,
    cache: dict[Path, Document],
) -> Route | None: ...
```

**Task 3 produces** (`src/ddd/gui/contract.py`, and so `gui/src/generated/api.ts`):

```python
class FindingRoute(_Frozen):
    kind: Literal["variable", "unit", "component"]
    name: str | None

class Finding(_Frozen):
    file: str
    check: str
    severity: Severity
    message: str
    pointer: str
    notes: tuple[Note, ...]
    route: FindingRoute | None      # new
```

**Task 4 produces** (`src/ddd/finding_fixes.py`, the contract, and `gui/src/api/client.ts`):

```python
@dataclass(frozen=True, slots=True)
class Fix:
    """One fix a finding carries: one file, and the operations to write in it."""

    title: str
    path: Path
    operations: tuple[Operation, ...]   # ddd.editing's own

def fixes_for(
    check: str, path: Path, pointer: str, cache: dict[Path, Document]
) -> tuple[Fix, ...]: ...
```

```python
class FixOffered(_Frozen):
    title: str
    changes: tuple[PlannedChange, ...]

class FixReply(_Frozen):
    revision: int
    fixes: tuple[FixOffered, ...]
```

```ts
export const getFix = (file: string, pointer: string, check: string, fetchImpl?: Fetch) =>
  Promise<FixReply>;
```

**Task 5 produces** (`gui/src/lib/findings.ts`, beside the existing `keyedFindings` and `distinctFindings`):

```ts
export interface FindingRow { finding: Finding; key: string; file: string }
export function findingRows(state: State): FindingRow[];
export function findingCounts(findings: readonly Finding[]): string;
export function routeOf(finding: Finding): Route | null;          // the page's own Route
export function routeHref(finding: Finding): string | null;       // that Route as an address
export function routeLabel(finding: Finding, state: State): string | null;
export function noRouteReason(finding: Finding, state: State): string;
export function fixEdit(reply: FixReply, title: string): Changes | null;
```

**Task 6 produces** (`gui/src/components/`):

```ts
export interface FindingsTableViewProps {
  rows: readonly FindingRow[];
  selected: string | undefined;          // a row's key
  onSelect: (key: string | undefined) => void;
}

export interface FindingPanelViewProps {
  finding: Finding;
  label: string | null;                  // "Open ValueA", or null when it leads nowhere
  href: string | null;                   // the address that link carries, beside onOpen
  reason: string;                        // why it leads nowhere, when it does
  onOpen: () => void;
  fixes: FixReply | null;
  chosen: string | undefined;            // the title of the fix being previewed
  onChoose: (title: string | undefined) => void;
  changesShown: boolean;
  onChangesShown: (shown: boolean) => void;
  onApply: () => void;
  refusal: string | null;
  busy: boolean;
  onClose: () => void;
}
```

**Task 7 consumes** all of the above and adds `view: "findings"` to `gui/src/lib/route.ts`; `VariablePanel`'s and `UnitPanel`'s props do not change.

---

### Task 1: One rule for what a value is

`ddd.lsp.edits.settle` compares the json text of a key. An edit writes a value in the *target file's* layout, so a declaration that already means the chosen value but spells it differently counts as a change - which is why part 3 wrapped the GUI's own preview in `ddd.variables.narrowed`. Put the rule where both clients get it, and the wrapper goes.

**Files:**
- Modify: `src/ddd/lsp/edits.py` (`settle`'s comparison, `_assign`'s "already says", one import)
- Modify: `src/ddd/variables.py` (`narrowed` and `_differs` deleted; `preview` sorts by posix spelling)
- Modify: `src/ddd/gui/api.py` (the `narrowed` call and its import go)
- Test: `tests/test_settle.py`, `tests/test_lsp.py`, `tests/test_variables.py`, `tests/test_gui_api.py`

**Interfaces:**
- Consumes: `ddd.value_identity.same_value(key, raw)` - part 3's rule; a conversion through the models, an enum by its name, limits as the numbers they resolve to, everything else the canonical json text, and anything the models refuse falling back to its text.
- Produces: `settle` and `_assign` compare by meaning. `ddd.variables.narrowed` no longer exists; `GET /api/settle` behaves exactly as it does today, by the rule underneath rather than a layer above.

- [ ] **Step 1: Write the failing tests**

In `tests/test_settle.py`, beside the existing ones:

```python
def test_a_declaration_spelling_the_value_differently_is_nothing_to_change(
    tmp_path: Path,
) -> None:
    # An edit writes a value in the target file's own layout, so the producer's four-line
    # conversion and a reader's one-line spelling of the same conversion are one value: a
    # settlement that asked for the change anyway would ask for it again after every apply.
    built = built_index(
        tmp_path,
        **{
            "a.ddd.json": component(
                "A", declare("output", "Speed", conversion={"kind": "linear", "factor": 2})
            ),
            "b.ddd.json": component(
                "B", declare("input", "Speed", conversion={"factor": 2, "offset": 0})
            ),
        },
    )
    raw = read(tmp_path / "a.ddd.json", {}).raw_at(f"{DEFINITION}.conversion")
    assert raw is not None
    assert settle(built, "Speed", "conversion", raw, {}).changes == ()


def test_a_declaration_meaning_something_else_still_changes(tmp_path: Path) -> None:
    built = built_index(
        tmp_path,
        **{
            "a.ddd.json": component(
                "A", declare("output", "Speed", conversion={"kind": "linear", "factor": 2})
            ),
            "b.ddd.json": component(
                "B", declare("input", "Speed", conversion={"kind": "linear", "factor": 4})
            ),
        },
    )
    raw = read(tmp_path / "a.ddd.json", {}).raw_at(f"{DEFINITION}.conversion")
    assert raw is not None
    changed = settle(built, "Speed", "conversion", raw, {}).changes
    assert [change.site.path.name for change in changed] == ["b.ddd.json"]
```

Use the file's own helper for the index rather than inventing one - `tests/test_settle.py` already builds one at the top of the file; if its name differs from `built_index`, use the file's.

In `tests/test_lsp.py`, the same rule seen through the editor, beside the existing action tests:

```python
def test_no_action_offers_to_rewrite_a_value_that_already_means_the_same(
    tmp_path: Path,
) -> None:
    # `ddd gui` has compared meaning since part 3; the editor now does too, so a lightbulb
    # that rewrote a line to the value it already had is gone.
    root = write_tree(
        tmp_path,
        {
            "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
            "a.ddd.json": component(
                "A", declare("output", "Speed", conversion={"kind": "linear", "factor": 2})
            ),
            "b.ddd.json": component(
                "B", declare("input", "Speed", conversion={"factor": 2, "offset": 0})
            ),
        },
    )
    built = index(load_workspace(root / "p.ddd.json", DiagnosticBag()))
    cache: dict[Path, Document] = {}
    document = read(root / "b.ddd.json", cache)
    offered = actions(built, root / "b.ddd.json", document, f"{DEFINITION}.conversion", cache)
    assert [entry["title"] for entry in offered] == []
```

Match the file's own idioms for building a workspace and reading an index - `tests/test_lsp.py` has them; do not add a second way.

- [ ] **Step 2: Run them to watch them fail**

Run: `python -m pytest tests/test_settle.py tests/test_lsp.py -k "means_the_same or spelling_the_value" -v`
Expected: FAIL - the settlement carries a change, and the editor offers a title.

- [ ] **Step 3: Compare by meaning**

In `src/ddd/lsp/edits.py`, import the rule beside the others:

```python
from ddd.value_identity import same_value
```

Replace `settle`'s comparison:

```python
        stated = document.raw_at(f"{site.pointer}.{key}")
        if _already(key, stated, raw) or (key in DEFERRED_KEYS and stated is None):
            continue
```

and add, beside `_fixed_by`:

```python
def _already(key: str, stated: str | None, raw: str | None) -> bool:
    """Whether the declaration already says what the settlement would write.

    By what the value means rather than by its json text. The text is the file's own layout,
    and an edit writes a value in the *target* file's layout: comparing text would call a
    declaration changed for spelling a conversion over four lines where the value came from a
    file that writes it on one, and would go on asking for that change after every apply.
    Removing a key compares as it always did - ``None`` against ``None`` is nothing to remove,
    and a stated key has something to take out whatever it says.
    """
    if stated is None or raw is None:
        return stated == raw
    return same_value(key, stated) == same_value(key, raw)
```

In `_assign`, the same rule where it decides a declaration already says it:

```python
    existing = document.raw_at(f"{definition}.{key}")
    if existing is not None:
        if same_value(key, existing) == same_value(key, raw):
            return None
        return {"range": document.value_range_of(f"{definition}.{key}"), "newText": raw}
```

- [ ] **Step 4: Delete the layer above it**

In `src/ddd/variables.py`, delete `narrowed` and `_differs`, and the sentence about narrowing in the module docstring. In `src/ddd/gui/api.py`, delete the `narrowed` import and its call in `_settle`, leaving the cache that feeds `settle` and `declarations_of` as it is. In `tests/test_variables.py`, delete `TestNarrowed`.

`tests/test_gui_api.py`'s two convergence tests - a conversion and a range settled, applied, and previewed again with nothing left to change - stay exactly as they are. They passed through the layer; they must now pass through the rule. If either fails, the rule is wrong, not the test.

- [ ] **Step 5: Sort paths by their posix spelling**

In `src/ddd/variables.py`, `preview` sorts the files it planned:

```python
        planned(path, tuple(made), fingerprints)
        for path, made in sorted(operations.items(), key=lambda entry: entry[0].as_posix())
```

A `Path` sorts by its parts, which order differently on Windows and Linux; `ddd.lsp.units` already sorts this way, and a preview that listed two files in one order on one machine and another elsewhere would photograph differently in the two.

- [ ] **Step 6: Run the tests that pinned the old behaviour**

Run: `python -m pytest tests/test_settle.py tests/test_lsp.py tests/test_variables.py tests/test_gui_api.py -v`
Expected: the new tests pass. **Some existing tests will fail, and that is this task.** Read each one: a test asserting that an action is offered, or that a settlement changes a declaration, where the two values differ only in spelling, now asserts the old behaviour - change it to assert the new, keeping its name honest. A test that fails for any other reason is a bug in the change, not a test to edit.

- [ ] **Step 7: Run the Python gate**

Run: `python -m pytest && ruff check . && ruff format --check . && mypy`
Expected: green at 100 % line and branch. Deleting `narrowed` removes branches; if coverage now reports an uncovered line elsewhere, it is a line only its tests reached - cover it or delete it, and say which in the report.

- [ ] **Step 8: Commit**

```bash
git add src/ddd/lsp/edits.py src/ddd/variables.py src/ddd/gui/api.py tests/
git commit -m "compare what a value means in both clients, not only its text

Co-Authored-By: Claude <noreply@anthropic.com>"
```

(Name the model you are in the trailer.)

---

### Task 2: Where a finding leads

A finding names a file and a place in it. This says what the page can open for it, and answers nothing where the page has nothing to open.

**Files:**
- Create: `src/ddd/finding_routes.py`
- Modify: `src/ddd/lsp/edits.py` (`_WITHIN_DEFINITION` made public)
- Test: `tests/test_finding_routes.py` (new)

**Interfaces:**
- Consumes: `ddd.lsp.ranges.Document` and `read`; `WITHIN_DEFINITION` from `ddd.lsp.edits`.
- Produces: `Route(kind, name)` and `route_of(check, path, pointer, kind, loaded, cache)`, exactly as the Interfaces section at the top spells them.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_finding_routes.py`:

```python
"""Where each finding of ``ddd gui`` leads."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from conftest import component, declare, project, scalar_type, types, write_tree
from ddd.finding_routes import Route, route_of

DEFINITION = "component.interface[0].definition"


def tree(tmp_path: Path, **files: Any) -> Path:
    write_tree(tmp_path, {"p.ddd.json": project("P", *files), **files})
    return tmp_path


class TestRoutes:
    def test_a_finding_inside_a_declaration_leads_to_its_variable(self, tmp_path: Path) -> None:
        root = tree(
            tmp_path, **{"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))}
        )
        route = route_of(
            "definition-mismatch", root / "a.ddd.json", DEFINITION, "component", True, {}
        )
        assert route == Route(kind="variable", name="Speed")

    def test_a_finding_deep_inside_a_declaration_leads_to_the_same_variable(
        self, tmp_path: Path
    ) -> None:
        # `limits-out-of-range` is filed on the range itself, not on the definition.
        root = tree(
            tmp_path,
            **{
                "a.ddd.json": component(
                    "A", declare("output", "Speed", limits={"min": 0, "max": 100})
                )
            },
        )
        route = route_of(
            "limits-out-of-range",
            root / "a.ddd.json",
            f"{DEFINITION}.limits.max",
            "component",
            True,
            {},
        )
        assert route == Route(kind="variable", name="Speed")

    def test_an_unknown_unit_leads_to_the_unit_it_names(self, tmp_path: Path) -> None:
        root = tree(
            tmp_path, **{"a.ddd.json": component("A", declare("output", "Speed", unit="degC"))}
        )
        route = route_of(
            "unknown-unit", root / "a.ddd.json", f"{DEFINITION}.unit", "component", True, {}
        )
        assert route == Route(kind="unit", name="degC")

    def test_an_unknown_unit_on_a_type_leads_to_the_unit_as_well(self, tmp_path: Path) -> None:
        # The unit panel of part 2 lists every place a unit is stated, a scalar type's included,
        # so this leads somewhere although no page opens a types file.
        root = tree(tmp_path, **{"t.ddd.json": types(scalar_type("Speed_t", unit="degC"))})
        route = route_of("unknown-unit", root / "t.ddd.json", "types[0].unit", "types", True, {})
        assert route == Route(kind="unit", name="degC")

    def test_a_finding_on_a_component_file_naming_no_declaration_leads_to_the_component(
        self, tmp_path: Path
    ) -> None:
        root = tree(
            tmp_path, **{"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))}
        )
        route = route_of("duplicate-component", root / "a.ddd.json", "component.name", "component", True, {})
        assert route == Route(kind="component", name=None)

    def test_a_finding_on_a_file_that_did_not_load_leads_nowhere(self, tmp_path: Path) -> None:
        root = tree(
            tmp_path, **{"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))}
        )
        assert route_of("json-syntax", root / "a.ddd.json", "", "component", False, {}) is None

    def test_a_finding_on_a_file_the_gui_has_no_page_for_leads_nowhere(
        self, tmp_path: Path
    ) -> None:
        # A types, units, constants, sections or rasters file has no screen of its own yet.
        root = tree(tmp_path, **{"t.ddd.json": types(scalar_type("Speed_t", unit="rpm"))})
        assert route_of("duplicate-type", root / "t.ddd.json", "types[0].name", "types", True, {}) is None

    def test_a_finding_naming_no_place_leads_nowhere(self, tmp_path: Path) -> None:
        root = tree(
            tmp_path, **{"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))}
        )
        assert route_of("missing-producer", root / "a.ddd.json", "", "component", True, {}) is None

    def test_a_declaration_the_file_no_longer_holds_leads_nowhere(self, tmp_path: Path) -> None:
        # The analysis read the file; the pointer describes where the declaration was then.
        root = tree(
            tmp_path, **{"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))}
        )
        route = route_of(
            "definition-mismatch",
            root / "a.ddd.json",
            "component.interface[7].definition",
            "component",
            True,
            {},
        )
        assert route is None

    def test_a_file_that_broke_since_the_analysis_leads_nowhere_rather_than_failing(
        self, tmp_path: Path
    ) -> None:
        # Every finding of the project is routed on every state request, so a file saved
        # half-edited between the analysis and the request must answer nothing rather than
        # raise: `ddd.lsp.ranges.read` gives an empty document for a file it cannot read, and
        # an empty document answers every question with nothing.
        root = tree(
            tmp_path, **{"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))}
        )
        (root / "a.ddd.json").write_text('{"component": {"name": "A", "inter', encoding="utf-8")
        assert (
            route_of("definition-mismatch", root / "a.ddd.json", DEFINITION, "component", True, {})
            is None
        )

    def test_a_file_gone_since_the_analysis_leads_nowhere(self, tmp_path: Path) -> None:
        root = tree(
            tmp_path, **{"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))}
        )
        (root / "a.ddd.json").unlink()
        assert (
            route_of("unknown-unit", root / "a.ddd.json", f"{DEFINITION}.unit", "component", True, {})
            is None
        )

    def test_an_unknown_unit_whose_pointer_holds_no_string_leads_nowhere(
        self, tmp_path: Path
    ) -> None:
        root = tree(
            tmp_path, **{"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))}
        )
        route = route_of(
            "unknown-unit", root / "a.ddd.json", f"{DEFINITION}.datatype.nothing", "component", True, {}
        )
        assert route is None
```

- [ ] **Step 2: Run them to watch them fail**

Run: `python -m pytest tests/test_finding_routes.py -v`
Expected: FAIL - `ModuleNotFoundError: No module named 'ddd.finding_routes'`.

- [ ] **Step 3: Make the definition pattern public**

In `src/ddd/lsp/edits.py`, rename `_WITHIN_DEFINITION` to `WITHIN_DEFINITION` (its docstring unchanged) and update its uses in that file. One pattern for one thing: a second copy in the new module would drift the day a declaration's pointer changes shape.

- [ ] **Step 4: Write the module**

Create `src/ddd/finding_routes.py`:

```python
"""Where a finding leads.

``ddd gui`` lists what the analysis reported and, until now, left the reader to work out where
to go: a sentence about a variable's declarations says nothing about which screen settles them.
This answers what the page can open for one finding - the variable whose declaration it is
about, the unit it names, or the component it is filed on - and answers nothing where the page
has nothing to open, so that a row can say why instead of leading somewhere useless.

Pure: no GUI and no HTTP. :mod:`ddd.gui.api` turns a route into the shape ``GET /api/state``
answers, and nothing else reads them.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from ddd.lsp.edits import WITHIN_DEFINITION
from ddd.lsp.ranges import Document, read

UNIT_CHECKS: Final = frozenset({"unknown-unit"})
"""The checks filed where a unit is stated, whose finding leads to that unit's own panel."""

COMPONENT_KIND: Final = "component"
"""The one file kind the page has a screen for; the rest are milestone 6's."""


@dataclass(frozen=True, slots=True)
class Route:
    """Where a finding leads."""

    kind: str
    """``variable``, ``unit`` or ``component``."""

    name: str | None
    """The variable's name or the unit's spelling; ``None`` for a component, which the finding's
    own file already names."""


def route_of(
    check: str,
    path: Path,
    pointer: str,
    kind: str,
    loaded: bool,
    cache: dict[Path, Document],
) -> Route | None:
    """What the page can open for a finding filed on ``path`` at ``pointer``.

    ``kind`` and ``loaded`` are the file's own, as the analysis recorded them. Nothing is
    answered for a file that did not load - the pointer describes a document nobody parsed -
    and nothing for a finding that names no place at all, which is how a check about the
    project rather than a line in a file reports itself.
    """
    if not loaded:
        return None
    if check in UNIT_CHECKS:
        # A unit is stated in a component, in a scalar type and in a structure member, and part
        # 2's panel lists all three: the one route that does not care which file it was on.
        stated = read(path, cache).value_at(pointer)
        return Route("unit", stated) if isinstance(stated, str) and stated else None
    if kind != COMPONENT_KIND:
        return None
    within = WITHIN_DEFINITION.match(pointer)
    if within is None:
        # Somewhere else in a component: its own page is what there is to open.
        return Route("component", None) if pointer else None
    name = read(path, cache).value_at(f"{within.group()}.name")
    # The pointer is where the analysis found the declaration; the file may have moved on since.
    return Route("variable", name) if isinstance(name, str) else None
```

- [ ] **Step 5: Run the tests to watch them pass**

Run: `python -m pytest tests/test_finding_routes.py -v`
Expected: PASS.

- [ ] **Step 6: Run the Python gate**

Run: `python -m pytest && ruff check . && ruff format --check . && mypy`
Expected: green at 100 % line and branch.

- [ ] **Step 7: Commit**

```bash
git add src/ddd/finding_routes.py src/ddd/lsp/edits.py tests/test_finding_routes.py
git commit -m "work out where each finding leads

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: The state answers where each finding leads

`GET /api/state` carries every finding of the project; each gains the route Task 2 works out. `GET /api/variable` and `GET /api/unit` carry findings too, and answer the same shape - one finding, one answer, wherever it is read.

**Files:**
- Modify: `src/ddd/gui/contract.py` (`FindingRoute`, and `route` on `Finding`)
- Modify: `src/ddd/gui/api.py` (`_finding` takes what a route needs; its three call sites)
- Modify: `gui/src/api/types.ts` (the generated name re-exported)
- Test: `tests/test_gui_api.py`

**Interfaces:**
- Consumes: `Route` and `route_of` (Task 2); `Revision.files`, whose `SourceFile` carries `path`, `kind` and `loaded`.
- Produces: `Finding.route`, the shape the Interfaces section at the top spells, on every endpoint that answers findings.

- [ ] **Step 1: Write the failing tests**

In `tests/test_gui_api.py`, in `class TestState`:

```python
    def test_every_finding_says_where_it_leads(self, api: Api, root: Path) -> None:
        # The root fixture's two components declare Speed, and `a.ddd.json` states no id.
        routes = {
            (finding["check"], finding["route"] is None): finding["route"]
            for finding in get(api, "/api/state").body["findings"]
        }
        assert routes[("missing-id", False)] == {"kind": "variable", "name": "Speed"}

    def test_a_finding_on_a_file_that_did_not_load_leads_nowhere(self, tmp_path: Path) -> None:
        state = get(opened(tmp_path, HALF_SAVED), "/api/state").body
        half = next(
            finding
            for finding in state["findings"]
            if finding["file"].endswith("b.ddd.json")
        )
        assert half["route"] is None

    def test_an_unknown_unit_leads_to_its_unit(self, tmp_path: Path) -> None:
        api = opened_example(tmp_path, "vocabulary", "project.ddd.json")
        drifted = tmp_path / "vocabulary" / "pump.ddd.json"
        drifted.write_text(
            drifted.read_text(encoding="utf-8").replace('"unit": "kPa"', '"unit": "KPA"', 1),
            encoding="utf-8",
            newline="",
        )
        api.session.refresh()
        unknown = next(
            finding
            for finding in get(api, "/api/state").body["findings"]
            if finding["check"] == "unknown-unit"
        )
        assert unknown["route"] == {"kind": "unit", "name": "KPA"}
```

If the session has no method that re-analyses on demand, open the example *after* writing the
drift instead of refreshing, and say so in the report - the point of the test is the route, not
how the revision arrived.

And in `class TestVariable`, that a panel's findings carry it too:

```python
    def test_a_panel_finding_carries_its_route(self, api: Api) -> None:
        findings = get(api, "/api/variable", name="Speed").body["findings"]
        assert all(finding["route"] == {"kind": "variable", "name": "Speed"} for finding in findings)
```

- [ ] **Step 2: Run them to watch them fail**

Run: `python -m pytest tests/test_gui_api.py -k "leads or route" -v`
Expected: FAIL - `KeyError: 'route'`.

- [ ] **Step 3: Declare the route**

In `src/ddd/gui/contract.py`, before `Finding`:

```python
class FindingRoute(_Frozen):
    """What the page can open for a finding."""

    kind: Literal["variable", "unit", "component"]
    """Which screen: a variable's panel, a unit's panel, or the component's own page."""

    name: str | None
    """The variable's name or the unit's spelling; ``None`` for a component, which the
    finding's own ``file`` already names."""
```

and on `Finding`, after `notes`:

```python
    route: FindingRoute | None
    """Where pressing this finding leads, or ``None`` when the page has nothing to open: its
    file did not load, its file is not a component and has no screen yet, or it names no place
    at all."""
```

- [ ] **Step 4: Answer it**

In `src/ddd/gui/api.py`, import `route_of` from `ddd.finding_routes`, and give `_finding` what a route needs:

```python
def _finding(filed: Filed, source: SourceFile | None, cache: dict[Path, Document]) -> dict[str, Any]:
    """One finding as the page reads it, with where it leads.

    ``source`` is the analysis's own record of the file the finding is filed on, or ``None``
    for a finding filed on a file the analysis did not list - which leads nowhere, having no
    kind to route by.
    """
```

Its body keeps what it builds today and adds:

```python
        route=None
        if source is None
        else _route(
            route_of(
                finding.check,
                filed.file,
                "" if finding.location is None else finding.location.pointer,
                source.kind,
                source.loaded,
                cache,
            )
        ),
```

with

```python
def _route(route: Route | None) -> dict[str, Any] | None:
    return None if route is None else {"kind": route.kind, "name": route.name}
```

Each of the three call sites builds the lookup and the cache once, beside the answer it is
part of:

```python
        sources = {file.path.resolve(): file for file in revision.files}
        cache: dict[Path, Document] = {}
        ...
                findings=[
                    _finding(filed, sources.get(filed.file.resolve()), cache)
                    for filed in revision.findings
                ],
```

`GET /api/variable` and `GET /api/unit` already hold a cache of their own; pass that one rather
than making a second.

- [ ] **Step 5: Run the tests to watch them pass**

Run: `python -m pytest tests/test_gui_api.py tests/test_gui_contract.py -v`
Expected: PASS. The direct `_finding` test at the top of the file takes the new arguments -
pass `None` for the source, which is exactly the case it is about.

- [ ] **Step 6: Run the Python gate**

Run: `python -m pytest && ruff check . && ruff format --check . && mypy`
Expected: green at 100 %.

- [ ] **Step 7: Regenerate the page's types and re-export them**

```bash
cd gui && npm run schemas
```

Add `FindingRoute` to the sorted `export type { … }` list of `gui/src/api/types.ts`, then:

```bash
cd gui && npm run lint && npm run typecheck && npm test && npm run build
```

Expected: green. `Finding.route` is not optional, so any `Finding` literal in
`gui/src/stories/fixtures.ts` needs `route: null` for now - Task 6 gives each story the route it
is about.

- [ ] **Step 8: Commit**

```bash
git add src/ddd/gui tests/test_gui_api.py gui/src/api/types.ts gui/src/stories/fixtures.ts
git commit -m "answer where each finding leads

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: The fix a finding carries

One check has a fix the GUI has nowhere to put: `missing-id`, for a producing declaration without an identity. The language server writes it as a text edit; the GUI needs the same answer as operations on json pointers, so that `POST /api/edit` applies it like every other edit.

**Files:**
- Create: `src/ddd/finding_fixes.py`
- Modify: `src/ddd/identity.py` (`_unstamped` made public)
- Modify: `src/ddd/gui/contract.py`, `src/ddd/gui/api.py` (`GET /api/fix`), `src/ddd/gui/server.py` if the route table lives there
- Modify: `gui/src/api/client.ts`, `gui/src/api/types.ts`
- Test: `tests/test_finding_fixes.py` (new), `tests/test_gui_api.py`

**Interfaces:**
- Consumes: `ddd.identity.new_id` and the unstamped walk; `WITHIN_DEFINITION` (Task 2); `ddd.editing.Operation`; `ddd.variables.planned(path, operations, fingerprints)` and `_planned_changes` in the api, which part 2 and part 3 both use.
- Produces: `Fix`, `fixes_for`, `FixOffered`, `FixReply` and `getFix`, as the Interfaces section at the top spells them.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_finding_fixes.py`:

```python
"""The fixes a finding of ``ddd gui`` carries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from conftest import component, declare, project, write_tree
from ddd.finding_fixes import fixes_for

DEFINITION = "component.interface[0].definition"


def tree(tmp_path: Path, **files: Any) -> Path:
    write_tree(tmp_path, {"p.ddd.json": project("P", *files), **files})
    return tmp_path


class TestAnIdentity:
    def test_a_producing_declaration_without_one_is_offered_an_id(self, tmp_path: Path) -> None:
        root = tree(
            tmp_path, **{"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))}
        )
        offered = fixes_for("missing-id", root / "a.ddd.json", DEFINITION, {})
        assert [fix.title for fix in offered] == ["Give 'Speed' an id"]
        (operation,) = offered[0].operations
        assert (operation.op, operation.pointer) == ("set", f"{DEFINITION}.id")
        assert len(json.loads(operation.raw or '""')) == 12

    def test_two_asks_propose_two_ids(self, tmp_path: Path) -> None:
        # `ddd.identity` generates a fresh id per call, which is why a caller applies the
        # answer it was given rather than asking again.
        root = tree(
            tmp_path, **{"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))}
        )
        first = fixes_for("missing-id", root / "a.ddd.json", DEFINITION, {})[0]
        second = fixes_for("missing-id", root / "a.ddd.json", DEFINITION, {})[0]
        assert first.operations[0].raw != second.operations[0].raw

    def test_a_declaration_that_has_an_id_is_offered_nothing(self, tmp_path: Path) -> None:
        root = tree(
            tmp_path,
            **{"a.ddd.json": component("A", declare("output", "Speed", unit="rpm", id="abc123def456"))},
        )
        assert fixes_for("missing-id", root / "a.ddd.json", DEFINITION, {}) == ()

    def test_a_declaration_that_reads_the_variable_is_offered_nothing(
        self, tmp_path: Path
    ) -> None:
        # An identity belongs to whoever produces the object; a reader states none.
        root = tree(
            tmp_path, **{"a.ddd.json": component("A", declare("input", "Speed", unit="rpm"))}
        )
        assert fixes_for("missing-id", root / "a.ddd.json", DEFINITION, {}) == ()

    def test_an_id_stated_as_null_is_replaced_rather_than_added(self, tmp_path: Path) -> None:
        # What `ddd dump` writes for an unstamped object, and what `missing-id` reports too.
        root = tree(
            tmp_path,
            **{"a.ddd.json": component("A", declare("output", "Speed", unit="rpm", id=None))},
        )
        (fix,) = fixes_for("missing-id", root / "a.ddd.json", DEFINITION, {})
        assert fix.operations[0].pointer == f"{DEFINITION}.id"

    def test_another_check_carries_no_fix(self, tmp_path: Path) -> None:
        root = tree(
            tmp_path, **{"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))}
        )
        assert fixes_for("definition-mismatch", root / "a.ddd.json", DEFINITION, {}) == ()

    def test_a_pointer_naming_no_declaration_carries_no_fix(self, tmp_path: Path) -> None:
        root = tree(
            tmp_path, **{"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))}
        )
        assert fixes_for("missing-id", root / "a.ddd.json", "component.name", {}) == ()

    def test_a_declaration_whose_name_is_not_a_name_carries_no_fix(self, tmp_path: Path) -> None:
        # The file moved on since the analysis: the fix's own title would have nothing to say.
        root = tree(
            tmp_path, **{"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))}
        )
        path = root / "a.ddd.json"
        path.write_text(
            path.read_text(encoding="utf-8").replace('"name": "Speed"', '"name": 3', 1),
            encoding="utf-8",
            newline="",
        )
        assert fixes_for("missing-id", path, DEFINITION, {}) == ()
```

- [ ] **Step 2: Run them to watch them fail**

Run: `python -m pytest tests/test_finding_fixes.py -v`
Expected: FAIL - `ModuleNotFoundError: No module named 'ddd.finding_fixes'`.

- [ ] **Step 3: Make the unstamped walk public**

In `src/ddd/identity.py`, rename `_unstamped` to `unstamped` (docstring unchanged) and update its uses in that file. One rule for which declarations get an id: `ddd id`, the language server's quick fix and the GUI's all read it from here, and a second walk in the new module would be the same reasoning written twice.

- [ ] **Step 4: Write the module**

Create `src/ddd/finding_fixes.py`:

```python
"""The fixes a finding of ``ddd gui`` carries.

Most checks have none: they name what is wrong, and the panel that owns the key is where a
reader settles it. One has a fix with nowhere else to go - ``missing-id``, an identity for a
producing declaration that states none - and this plans it as operations on json pointers, the
form ``POST /api/edit`` applies.

The language server offers the same fix as a text edit with a range, computed by
:mod:`ddd.identity` from the same walk this reads: which declarations want an id is decided in
one place, and only how the edit is spelled differs between the two clients.

A list of fixes rather than one, so that the second check to grow a fix needs no new shape.
One file per fix, because that is what a fix is: a change reaching several files is a plan, and
:mod:`ddd.lsp.units` already shows what those look like.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from ddd.editing import Operation
from ddd.identity import new_id, unstamped
from ddd.lsp.edits import WITHIN_DEFINITION
from ddd.lsp.ranges import Document, read

MISSING_ID: Final = "missing-id"
"""The one check whose fix the page has nowhere else to offer."""


@dataclass(frozen=True, slots=True)
class Fix:
    """One fix a finding carries."""

    title: str
    """What the button says, naming the thing it changes."""

    path: Path
    """The file it writes in."""

    operations: tuple[Operation, ...]
    """What it writes there, for the edit engine."""


def fixes_for(
    check: str, path: Path, pointer: str, cache: dict[Path, Document]
) -> tuple[Fix, ...]:
    """The fixes the finding filed at ``pointer`` of ``path`` carries, in the order to offer
    them.

    Empty for every check but one, and empty for that one wherever the declaration it names has
    moved on since the analysis: a file is read here as it stands now, and a fix planned against
    something that is no longer there would be refused by the engine anyway - with a sentence
    about fingerprints rather than about the declaration.
    """
    if check != MISSING_ID:
        return ()
    document = read(path, cache)
    within = WITHIN_DEFINITION.match(pointer)
    if within is None:
        return ()
    definition = within.group()
    if definition not in {found for found, _ in unstamped(document)}:
        return ()
    name = document.value_at(f"{definition}.name")
    if not isinstance(name, str):
        return ()
    # A fresh id per call: the page applies the preview it was given, never one asked for twice.
    return (
        Fix(
            title=f"Give '{name}' an id",
            path=path,
            operations=(Operation("set", f"{definition}.id", json.dumps(new_id())),),
        ),
    )
```

- [ ] **Step 5: Run the tests to watch them pass**

Run: `python -m pytest tests/test_finding_fixes.py -v`
Expected: PASS.

- [ ] **Step 6: Write the endpoint's failing tests**

In `tests/test_gui_api.py`, a class of its own beside `TestSettle`:

```python
class TestFix:
    def test_a_missing_id_is_previewed_and_applied(self, api: Api, root: Path) -> None:
        before = contents(root)
        reply = get(
            api,
            "/api/fix",
            file=posix(root, "a.ddd.json"),
            pointer="component.interface[0].definition",
            check="missing-id",
        )
        assert reply.status == 200
        assert [fix["title"] for fix in reply.body["fixes"]] == ["Give 'Speed' an id"]
        assert contents(root) == before, "a preview writes nothing"

        (change,) = reply.body["fixes"][0]["changes"]
        assert change["hunks"], "the reader is shown the line it would add"
        edit = {"changes": [{f: change[f] for f in ("file", "fingerprint", "operations")}]}
        assert post(api, "/api/edit", edit).status == 200
        stamped = json.loads((root / "a.ddd.json").read_text(encoding="utf-8"))
        assert len(stamped["component"]["interface"][0]["definition"]["id"]) == 12

    def test_a_finding_with_no_fix_answers_none(self, api: Api, root: Path) -> None:
        reply = get(
            api,
            "/api/fix",
            file=posix(root, "a.ddd.json"),
            pointer="component.interface[0].definition",
            check="definition-mismatch",
        )
        assert (reply.status, reply.body["fixes"]) == (200, [])

    @pytest.mark.parametrize(
        "query",
        [{}, {"file": "a.ddd.json"}, {"file": "a.ddd.json", "pointer": "x"}],
    )
    def test_a_malformed_request_is_bad(self, api: Api, query: dict[str, str]) -> None:
        assert get(api, "/api/fix", **query).status == 400

    def test_a_file_of_no_project_is_not_found(self, api: Api, tmp_path: Path) -> None:
        reply = get(
            api,
            "/api/fix",
            file=(tmp_path / "elsewhere.ddd.json").resolve().as_posix(),
            pointer="component.interface[0].definition",
            check="missing-id",
        )
        assert (reply.status, reply.body["error"]) == (404, "not-found")

    def test_fixing_needs_an_open_project(self, root: Path) -> None:
        reply = get(
            Api(Session(root)),
            "/api/fix",
            file=posix(root, "a.ddd.json"),
            pointer="component.interface[0].definition",
            check="missing-id",
        )
        assert (reply.status, reply.body["error"]) == (409, "no-project")
```

- [ ] **Step 7: Declare and answer it**

In `src/ddd/gui/contract.py`, under a heading of its own:

```python
class FixOffered(_Frozen):
    """One fix a finding carries, previewed."""

    title: str
    """What the button says."""

    changes: tuple[PlannedChange, ...]
    """One per file, as ``POST /api/edit`` takes them, beside the lines each would change."""


class FixReply(_Frozen):
    """What ``GET /api/fix`` answers: every fix one finding carries."""

    revision: int
    """The revision the previews were computed from."""

    fixes: tuple[FixOffered, ...]
    """Empty for a finding that carries none, which is most of them."""
```

In `src/ddd/gui/api.py`, the endpoint beside `_settle`:

```python
    def _fix(self, query: Query, body: bytes | None) -> Reply:
        revision = self._opened()
        file, check = (_single(query.get(part)) for part in ("file", "check"))
        pointer = _single(query.get("pointer"))
        if not file or not check or pointer is None:
            return _error(400, "bad-request", "fix takes ?file=, ?pointer= and ?check=")
        wanted = Path(file).resolve()
        source = next((f for f in revision.files if f.path.resolve() == wanted), None)
        if source is None:
            return _error(404, "not-found", f"{file} is not a file of the open project")
        cache: dict[Path, Document] = {}
        stamps = {f.path.resolve(): f.fingerprint for f in revision.files}
        offered = []
        for fix in fixes_for(check, source.path, pointer, cache):
            try:
                made = planned(fix.path, fix.operations, stamps)
            except EditError as refused:
                return _error(409 if refused.code in REFUSALS else 500, refused.code, str(refused))
            offered.append({"title": fix.title, "changes": _planned_changes([made])})
        return Reply(
            200,
            contract.FixReply(revision=revision.number, fixes=offered).model_dump(mode="json"),
        )
```

and its row in the route table: `"/api/fix": ("GET", Api._fix)`.

Check `planned`'s own signature before you write this: part 2 made it public in
`src/ddd/variables.py`, and it answers one `Planned` for one file. If it raises nothing, drop
the `try` and say so in the report rather than keeping a branch no test can reach.

- [ ] **Step 8: Run the tests and the gate**

Run: `python -m pytest tests/test_gui_api.py tests/test_finding_fixes.py -v`
Expected: PASS.

Run: `python -m pytest && ruff check . && ruff format --check . && mypy`
Expected: green at 100 %.

- [ ] **Step 9: The page's call**

```bash
cd gui && npm run schemas
```

Add `FixOffered` and `FixReply` to `gui/src/api/types.ts`, and the call to
`gui/src/api/client.ts`, beside `getSettle`:

```ts
export const getFix = (
  file: string,
  pointer: string,
  check: string,
  fetchImpl: Fetch = fetch,
) =>
  request<FixReply>(
    `/api/fix?file=${encodeURIComponent(file)}&pointer=${encodeURIComponent(pointer)}` +
      `&check=${encodeURIComponent(check)}`,
    {},
    fetchImpl,
  );
```

Cover it in `gui/src/api/client.test.ts` the way `getSettle` is covered - the query it builds,
and that it answers what the server sent.

Run: `cd gui && npm run lint && npm run typecheck && npm test && npm run build`
Expected: green, `src/api` still at 100 %.

- [ ] **Step 10: Commit**

```bash
git add src/ddd tests gui/src/api
git commit -m "offer the one fix a finding carries

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: The page's logic

The tab's order and counts, what each route says and where it leads, why a finding leads nowhere, and the edit a chosen fix comes to. Pure functions over the answers, under Vitest's 100 % gate.

**Files:**
- Modify: `gui/src/lib/findings.ts`, `gui/src/lib/findings.test.ts`

**Interfaces:**
- Consumes: `Finding`, `State`, `FixReply`, `Changes` from `../api/types`; `hrefOf` from `./route`; `baseName` from `./units`; the existing `keyedFindings` in this file.
- Produces: `FindingRow`, `findingRows`, `findingCounts`, `routeOf`, `routeHref`, `routeLabel`, `noRouteReason`, `fixEdit`, as the Interfaces section at the top spells them.

- [ ] **Step 1: Write the failing tests**

Append to `gui/src/lib/findings.test.ts` (it already tests `keyedFindings` and `distinctFindings`; keep those):

```ts
const SENSOR_HUB = "C:/work/demo/components/sensor_hub.ddd.json";
const TYPES = "C:/work/demo/types.ddd.json";

function finding(fields: Partial<Finding> = {}): Finding {
  return {
    file: SENSOR_HUB,
    check: "definition-mismatch",
    severity: "error",
    message: "'ValueA' is declared differently by component 'Controller'",
    pointer: "component.interface[2].definition",
    notes: [],
    route: { kind: "variable", name: "ValueA" },
    ...fields,
  };
}

function state(findings: Finding[]): State {
  return {
    revision: 7,
    project: "C:/work/demo/demo.ddd.json",
    files: [
      { path: SENSOR_HUB, kind: "component", name: "SensorHub", loaded: true, fingerprint: "a", findings: { error: 1, warning: 0, info: 0 } },
      { path: TYPES, kind: "types", name: null, loaded: true, fingerprint: "b", findings: { error: 1, warning: 0, info: 0 } },
    ],
    findings,
  };
}

describe("the rows of the findings tab", () => {
  test("errors come before warnings, and warnings before information", () => {
    const rows = findingRows(
      state([
        finding({ severity: "info", check: "missing-id" }),
        finding({ severity: "error" }),
        finding({ severity: "warning", check: "storage-mismatch" }),
      ]),
    );
    expect(rows.map((row) => row.finding.severity)).toEqual(["error", "warning", "info"]);
  });

  test("within a severity the analysis's own order is kept, which groups them by file", () => {
    const rows = findingRows(
      state([
        finding({ file: TYPES, check: "duplicate-type", route: null }),
        finding({ file: SENSOR_HUB }),
      ]),
    );
    expect(rows.map((row) => row.file)).toEqual(["types.ddd.json", "sensor_hub.ddd.json"]);
  });

  test("each row has a key that tells two findings of one wording apart", () => {
    const rows = findingRows(state([finding(), finding()]));
    expect(new Set(rows.map((row) => row.key)).size).toBe(2);
  });
});

describe("what the tab says about how many there are", () => {
  test.each([
    [[], "Nothing to report"],
    [[finding()], "1 finding · 1 error"],
    [
      [finding(), finding({ severity: "warning" }), finding({ severity: "info" })],
      "3 findings · 1 error, 1 warning, 1 note",
    ],
  ])("%#", (findings, says) => {
    expect(findingCounts(findings)).toBe(says);
  });
});

describe("where a finding leads", () => {
  test("a variable, by name", () => {
    const one = finding();
    expect(routeLabel(one, state([one]))).toBe("Open ValueA");
    expect(routeHref(one)).toBe(
      `/component?file=${encodeURIComponent(SENSOR_HUB)}&variable=ValueA`,
    );
  });

  test("a unit, by its spelling", () => {
    const one = finding({ check: "unknown-unit", route: { kind: "unit", name: "degC" } });
    expect(routeLabel(one, state([one]))).toBe("Open degC");
    expect(routeHref(one)).toBe("/project?view=units&unit=degC");
  });

  test("a component, by the name its file gives it", () => {
    const one = finding({ route: { kind: "component", name: null } });
    expect(routeLabel(one, state([one]))).toBe("Open SensorHub");
    expect(routeHref(one)).toBe(`/component?file=${encodeURIComponent(SENSOR_HUB)}`);
  });

  test("nowhere, when the answer says so", () => {
    const one = finding({ route: null });
    expect(routeLabel(one, state([one]))).toBeNull();
    expect(routeHref(one)).toBeNull();
    expect(routeOf(one)).toBeNull();
  });

  test("the route itself is what a screen navigates to", () => {
    // The address and the route are one answer in two forms: a link carries the address, and
    // the screen hands the route to the app's own navigate.
    expect(routeOf(finding())).toEqual({
      page: "component",
      file: SENSOR_HUB,
      variable: "ValueA",
    });
  });
});

describe("why a finding leads nowhere", () => {
  test("its file did not load", () => {
    const one = finding({ route: null });
    const half = state([one]);
    half.files = [{ ...half.files[0], loaded: false }];
    expect(noRouteReason(one, half)).toBe("sensor_hub.ddd.json did not load");
  });

  test("the page has no screen for that kind of file", () => {
    const one = finding({ file: TYPES, check: "duplicate-type", route: null });
    expect(noRouteReason(one, state([one]))).toBe("types.ddd.json is a types file, which has no page yet");
  });

  test("it names no place in a file", () => {
    const one = finding({ pointer: "", route: null, check: "missing-producer" });
    expect(noRouteReason(one, state([one]))).toBe("it is about the project rather than a place in a file");
  });

  test("its file is not one the analysis listed", () => {
    const one = finding({ file: "C:/elsewhere.ddd.json", route: null });
    expect(noRouteReason(one, state([one]))).toBe("elsewhere.ddd.json is not a file of this project");
  });
});

describe("the edit a chosen fix comes to", () => {
  const reply: FixReply = {
    revision: 7,
    fixes: [
      {
        title: "Give 'ValueA' an id",
        changes: [
          {
            file: SENSOR_HUB,
            fingerprint: "a",
            operations: [
              { op: "set", pointer: "component.interface[2].definition.id", raw: '"rbdtf7g2eey1"' },
            ],
            hunks: [],
          },
        ],
      },
    ],
  };

  test("the one it names", () => {
    expect(fixEdit(reply, "Give 'ValueA' an id")?.changes).toHaveLength(1);
  });

  test("nothing for a title the answer does not carry, or a fix that changes nothing", () => {
    expect(fixEdit(reply, "Give 'ValueB' an id")).toBeNull();
    expect(fixEdit({ revision: 7, fixes: [{ title: "t", changes: [] }] }, "t")).toBeNull();
  });
});
```

- [ ] **Step 2: Run them to watch them fail**

Run: `cd gui && npm test -- findings`
Expected: FAIL - the new names are not exported.

- [ ] **Step 3: Write them**

Append to `gui/src/lib/findings.ts`:

```ts
/** One row of the Findings tab: a finding, a key stable in the list, and the file's own name. */
export interface FindingRow {
  finding: Finding;
  key: string;
  file: string;
}

/** Worst first, and within a severity in the order the analysis filed them - which groups them
 * by file, since that is the order `GET /api/state` answers in. A stable sort is what keeps the
 * second half of that sentence true. */
export function findingRows(state: State): FindingRow[] {
  const rank = { error: 0, warning: 1, info: 2 };
  return keyedFindings(state.findings)
    .map(([finding, key]) => ({ finding, key, file: baseName(finding.file) }))
    .sort((one, other) => rank[one.finding.severity] - rank[other.finding.severity]);
}

/** The tab's line above the table. */
export function findingCounts(findings: readonly Finding[]): string {
  if (findings.length === 0) return "Nothing to report";
  const counted = [
    ["error", "errors"],
    ["warning", "warnings"],
    ["note", "notes"],
  ] as const;
  const of = (severity: Finding["severity"]) =>
    findings.filter((finding) => finding.severity === severity).length;
  const parts = [of("error"), of("warning"), of("info")]
    .map((count, at) => [count, counted[at][count === 1 ? 0 : 1]] as const)
    .filter(([count]) => count > 0)
    .map(([count, word]) => `${count} ${word}`);
  const total = `${findings.length} finding${findings.length === 1 ? "" : "s"}`;
  return `${total} · ${parts.join(", ")}`;
}

/** What the button that follows a finding says, or `null` when it leads nowhere. */
export function routeLabel(finding: Finding, state: State): string | null {
  const route = finding.route;
  if (route === null) return null;
  if (route.kind === "component") {
    const listed = state.files.find((file) => file.path === finding.file);
    return `Open ${listed?.name ?? baseName(finding.file)}`;
  }
  return `Open ${route.name}`;
}

/** The page's own route a finding leads to, or `null` when it leads nowhere.
 *
 * One answer in two forms: a screen navigates with the route, and a link carries the address
 * `routeHref` writes from it, the way `LinkTabs` already pairs an `href` with its `onFollow`. */
export function routeOf(finding: Finding): Route | null {
  const route = finding.route;
  if (route === null) return null;
  if (route.kind === "unit" && route.name !== null) {
    return { page: "project", view: "units", unit: route.name };
  }
  if (route.kind === "variable" && route.name !== null) {
    return { page: "component", file: finding.file, variable: route.name };
  }
  return { page: "component", file: finding.file };
}

/** The address that route is written as, or `null` when the finding leads nowhere. */
export function routeHref(finding: Finding): string | null {
  const route = routeOf(finding);
  return route === null ? null : hrefOf(route);
}

/** Why a finding leads nowhere, in the words the panel says it. */
export function noRouteReason(finding: Finding, state: State): string {
  const name = baseName(finding.file);
  const listed = state.files.find((file) => file.path === finding.file);
  if (listed === undefined) return `${name} is not a file of this project`;
  if (!listed.loaded) return `${name} did not load`;
  if (listed.kind !== "component") return `${name} is a ${listed.kind} file, which has no page yet`;
  return "it is about the project rather than a place in a file";
}

/** The edit the fix of that title comes to, exactly as `POST /api/edit` takes it. */
export function fixEdit(reply: FixReply, title: string): Changes | null {
  const chosen = reply.fixes.find((fix) => fix.title === title);
  if (chosen === undefined) return null;
  const [first, ...rest] = chosen.changes.map(({ file, fingerprint, operations }) => ({
    file,
    fingerprint,
    operations,
  }));
  return first === undefined ? null : { changes: [first, ...rest] };
}
```

`Changes`'s `operations` is a non-empty tuple in the generated types; if the compiler refuses
the spread above, narrow it the way `editOf` in `gui/src/lib/units.ts` does - that file solved
the same problem and its answer is the one to copy.

- [ ] **Step 4: Run them to watch them pass, then the page's gate**

Run: `cd gui && npm test -- findings`
Expected: PASS.

Run: `cd gui && npm run lint && npm run typecheck && npm test && npm run build`
Expected: green, `src/lib/findings.ts` at 100 % statements, branches, functions and lines.

- [ ] **Step 5: Commit**

```bash
git add gui/src/lib/findings.ts gui/src/lib/findings.test.ts
git commit -m "order the findings, say where each leads and what its fix writes

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6: The tab's pictures, and their stories

The table and the panel, each a picture of its props, with a story and a screenshot reference per state. The tab itself is Task 7: nothing here is wired to a query, so the page stays green throughout.

**Files:**
- Create: `gui/src/components/FindingsTableView.tsx`, `FindingsTableView.stories.tsx`, `FindingPanelView.tsx`, `FindingPanelView.stories.tsx`
- Modify: `gui/src/stories/fixtures.ts`, `gui/src/styles/ui.css`
- Create: `gui/screenshots/references/*.png` for the new stories

**Interfaces:**
- Consumes: `findingRows`, `findingCounts`, `routeLabel`, `noRouteReason` (Task 5); `Changes` from `./Changes`; `Button`, `Chip`, `Panel`, `Table` from `gui/src/ui/`.
- Produces: `FindingsTableView` and `FindingPanelView` with the props the Interfaces section at the top spells.

- [ ] **Step 1: The table**

Create `gui/src/components/FindingsTableView.tsx`, following `gui/src/components/UnitsTableView.tsx` - read it first, and keep its `also()` helper for the class names:

```tsx
import type { FindingRow } from "../lib/findings";
import { Chip } from "../ui/Chip";
import { Cell, Column, Row, Table, TableBody, TableHeader } from "../ui/Table";

export interface FindingsTableViewProps {
  rows: readonly FindingRow[];
  /** The key of the row whose panel is open, or `undefined`. */
  selected: string | undefined;
  onSelect: (key: string | undefined) => void;
}

/** The Findings tab's table (spec 5.1): every finding of the project, worst first. A picture of
 * its props. */
export function FindingsTableView({ rows, selected, onSelect }: FindingsTableViewProps) {
  return (
    <Table
      aria-label="Findings"
      selectionMode="single"
      selectedKeys={new Set(selected === undefined ? [] : [selected])}
      onSelectionChange={(keys) => {
        const key = keys === "all" ? undefined : [...keys][0];
        onSelect(rows.find((row) => row.key === key)?.key);
      }}
    >
      <TableHeader>
        <Column isRowHeader>Check</Column>
        <Column>Message</Column>
        <Column>File</Column>
      </TableHeader>
      <TableBody items={rows}>
        {(row) => (
          <Row id={row.key} className={also(row.finding.severity === "error" ? "has-error" : "")}>
            <Cell>
              <Chip tone={toneOf(row.finding.severity)}>{row.finding.check}</Chip>
            </Cell>
            <Cell>{row.finding.message}</Cell>
            <Cell className={also("quiet")}>{row.file}</Cell>
          </Row>
        )}
      </TableBody>
    </Table>
  );
}

/** The chip's tone for a severity; `info` is the quiet one the design system calls neutral. */
function toneOf(severity: FindingRow["finding"]["severity"]) {
  return severity === "error" ? "error" : severity === "warning" ? "warning" : "neutral";
}

/** React Aria's own class with this table's beside it, since ui.css selects on both. */
function also(name: string) {
  return ({ defaultClassName }: { defaultClassName: string | undefined }) =>
    `${defaultClassName ?? ""} ${name}`.trim();
}
```

`Chip`'s tones are whatever `gui/src/ui/Chip.tsx` declares - read it, and if it has no neutral
tone, use the quietest it has and say which in your report rather than adding one.

- [ ] **Step 2: The panel**

Create `gui/src/components/FindingPanelView.tsx`. It draws, in this order: the check as a chip
with the severity beside it, the message, each note with the file it points at, then either the
**Open** button or the sentence saying why there is none, then each fix the finding carries -
its title as a button; the chosen one shows part 1's consequence line, **Show changes** and
**Apply to N files** - and last a refusal, when there is one.

```tsx
import type { Finding, FixReply } from "../api/types";
import { consequence } from "../lib/units";
import { Button } from "../ui/Button";
import { Chip } from "../ui/Chip";
import { Panel } from "../ui/Panel";
import { Changes } from "./Changes";

export interface FindingPanelViewProps {
  finding: Finding;
  /** What the button that follows it says, or `null` when it leads nowhere. */
  label: string | null;
  /** The address it carries, so the link is a real one; `null` with `label`. */
  href: string | null;
  /** Why it leads nowhere, said when `label` is `null`. */
  reason: string;
  /** Following it, without a reload - `LinkTabs`' own pairing of an href with a handler. */
  onOpen: () => void;
  fixes: FixReply | null;
  /** The title of the fix being previewed, or `undefined` while none is. */
  chosen: string | undefined;
  onChoose: (title: string | undefined) => void;
  changesShown: boolean;
  onChangesShown: (shown: boolean) => void;
  onApply: () => void;
  refusal: string | null;
  busy: boolean;
  onClose: () => void;
}
```

Its body follows `gui/src/components/UnitPanelView.tsx`, which draws the same shapes for a
unit's plans: read that file and keep its idioms - the `Panel` with a title and a meta line, the
findings list's markup, the actions row, and the refusal as a `role="status"` paragraph.

- [ ] **Step 3: The styles**

In `gui/src/styles/ui.css`, beside the Units tab's rules: the findings table's message column
takes the width left over and wraps rather than truncating, the file column is quiet and does
not wrap, and a note in the panel indents under its message. Use the existing tokens; add no
colours of your own.

- [ ] **Step 4: The fixtures**

In `gui/src/stories/fixtures.ts`, give the `Finding` literals the `route` Task 3 made required -
each the route it is about - and add what the new stories draw:

- `PROJECT_FINDINGS`: a `State` with one finding of each severity, one leading to a variable,
  one to a unit, one to a component, and one leading nowhere because its file did not load;
- `ID_FIX`: a `FixReply` carrying "Give 'ValueA' an id" with one change and one hunk;
- `NO_FINDINGS`: a `State` with none.

Every literal is of the generated type, so a field that drifts from the contract fails the type
check here.

- [ ] **Step 5: The stories**

`FindingsTableView.stories.tsx`: `WorstFirst` (`PROJECT_FINDINGS`, nothing selected),
`Selected` (its first row selected), `NothingToReport` (`NO_FINDINGS`).

`FindingPanelView.stories.tsx`: `LeadsToAVariable`, `LeadsToAUnit`, `LeadsNowhere` (with its
reason), `WithAFix` (`ID_FIX`, nothing chosen), `FixChosen` (chosen, changes shown), `Refused`
(a refusal sentence, no Apply). Each is a plain exported function component holding its own
state - nothing imported from `@ladle/react`.

- [ ] **Step 6: Run the page's gate**

Run: `cd gui && npm run lint && npm run typecheck && npm test && npm run build && npm run ladle:build`
Expected: green.

- [ ] **Step 7: Make the screenshot references, and look at them**

```bash
UPDATE=1 docker compose run --rm gui-screenshots
docker compose run --rm gui-screenshots
```

Open every new reference and look at it: a message that overflows its column, a table whose
chips wrapped, a panel whose Apply sits below the fold, or a story that photographed a spinner
is a story or a style to fix, not a reference to keep. Say in your report what each shows.

- [ ] **Step 8: Commit**

```bash
git add gui/src/components gui/src/stories/fixtures.ts gui/src/styles/ui.css gui/screenshots/references
git commit -m "draw the findings table and the panel a finding opens

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 7: The tab, and the lists that become links

The fourth tab, wired: the rows, the finding selected, its fix previewed and applied. And the two lists that already exist start leading somewhere.

**Files:**
- Create: `gui/src/screens/FindingsPage.tsx`
- Modify: `gui/src/lib/route.ts`, `gui/src/lib/route.test.ts`, `gui/src/app/App.tsx`, `gui/src/screens/ComponentPage.tsx`, `gui/src/components/VariablePanelView.tsx`

**Interfaces:**
- Consumes: `FindingsTableView`, `FindingPanelView` (Task 6); `findingRows`, `findingCounts`, `routeOf`, `routeHref`, `routeLabel`, `noRouteReason`, `fixEdit` (Task 5); `getFix` (Task 4); `postEdit`, `ApiError`.
- Produces: `view: "findings"` in the address, and `FindingsPage`. No other screen's props change.

- [ ] **Step 1: The address**

In `gui/src/lib/route.ts`, the project's views gain one, and the union says what each carries:

```ts
export type ProjectView = "graph" | "table" | "units" | "findings";

export type Route =
  | { page: "start" }
  | { page: "project"; view: "graph"; variable?: string }
  | { page: "project"; view: "table" }
  | { page: "project"; view: "units"; unit?: string }
  | { page: "project"; view: "findings" }
  | { page: "component"; file: string; variable?: string };
```

`parseRoute` answers `{ page: "project", view: "findings" }` for `/project?view=findings`, and
`hrefOf` writes it. **The finding selected is not in the address**: a finding is not a name, it
is an observation that may be gone at the next revision, and the reader presses it to leave for
somewhere that does have an address. Cover the new view in `gui/src/lib/route.test.ts` as the
others are covered - parsed and written, both ways.

- [ ] **Step 2: The screen**

Create `gui/src/screens/FindingsPage.tsx`, following `gui/src/screens/UnitsPage.tsx` - read it
first; this is the same shape with a simpler panel:

```tsx
interface Props {
  state: State | null;
  stopped: boolean;
  /** Following a finding: the route it leads to, which the app navigates to. `routeOf` says
   * what that route is, and `routeHref` writes the address the link carries. */
  onOpen: (route: Route) => void;
}
```

It holds `selected` (a row's key), `chosen` (a fix's title), `changesShown` and `refused` in
state; asks `getFix(finding.file, finding.pointer, finding.check)` for the selected finding,
keyed by `["fix", file, pointer, check, revision]`; applies with `postEdit(fixEdit(...))`; and
invalidates `["state"]`, `["fix"]` and the panels' queries on settle, as `UnitsPage` does for
its own. A finding that is gone from the next revision's rows closes its panel, and the tab says
so above the table - `UnitsPage`'s `gone` state is the pattern.

- [ ] **Step 3: The tab**

In `gui/src/app/App.tsx`, add `["findings", "Findings"]` to `PROJECT_VIEWS` after `units`, and
the branch that renders `FindingsPage` with `onOpen={navigate}` - the screen answers a `Route`,
which is what `navigate` takes, so no address is parsed back into one.

- [ ] **Step 4: The lists become links**

In `gui/src/screens/ComponentPage.tsx`, each finding in "Findings in this component" becomes a
link when `routeHref` answers one **and** the route is not this very component's page - a link
to where the reader already is teaches nothing. In `gui/src/components/VariablePanelView.tsx`,
the same, except that the place already being looked at is the variable: a finding whose route
names it stays text.

Use `Button variant="link"` with the address as its `href` if the design system's Button takes
one; otherwise a plain anchor styled by `ui.css`, as the masthead's links are. No new widget.

- [ ] **Step 5: Run the page's gate and the journeys**

Run: `cd gui && npm run lint && npm run typecheck && npm test && npm run build && npm run ladle:build`
Run: `cd gui && PLAYWRIGHT_CHANNEL=chrome npm run e2e`
Expected: green, and every journey of parts 1 to 3 still passing - the fourth tab must not move
what they press.

- [ ] **Step 6: Remake the screenshots the tab bar appears in**

```bash
UPDATE=1 docker compose run --rm gui-screenshots
docker compose run --rm gui-screenshots
```

Any story drawing the project screen's tab bar changes. Look at each changed reference: four
tabs must still fit without wrapping at the reference's width.

- [ ] **Step 7: Commit**

```bash
git add gui/src
git commit -m "list the project's findings in a tab of their own, each leading somewhere

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 8: A stale refusal waits for the next revision

Part 1's panel says "A file changed on disk, so nothing was written. The panel now shows the files as they are." It does not: the analysis that noticed the change has not run yet, so a reader who chooses again straight away applies the same stale fingerprints and is refused a second time. Make the sentence true.

**Files:**
- Create: `gui/src/lib/refusals.ts`, `gui/src/lib/refusals.test.ts`
- Modify: `gui/src/screens/VariablePanel.tsx`, `gui/src/screens/UnitPanel.tsx`, `gui/src/screens/FindingsPage.tsx`

**Interfaces:**
- Produces: `shownRefusal(stored, revision)`, which every panel that refuses reads.

- [ ] **Step 1: Write the failing tests**

Create `gui/src/lib/refusals.test.ts`:

```ts
import { expect, test } from "vitest";
import { shownRefusal } from "./refusals";

test("a refusal shows until the revision it was refused at has passed", () => {
  const stored = { text: "A file changed on disk", revision: 7 };
  expect(shownRefusal(stored, 7)).toBe("A file changed on disk");
  expect(shownRefusal(stored, 8)).toBeNull();
});

test("nothing refused shows nothing, whatever the revision", () => {
  expect(shownRefusal(null, 7)).toBeNull();
});

test("a refusal from before the page knew a revision shows until one arrives", () => {
  expect(shownRefusal({ text: "refused", revision: undefined }, undefined)).toBe("refused");
  expect(shownRefusal({ text: "refused", revision: undefined }, 7)).toBeNull();
});
```

- [ ] **Step 2: Run them to watch them fail**

Run: `cd gui && npm test -- refusals`
Expected: FAIL - the module does not exist.

- [ ] **Step 3: Write it**

Create `gui/src/lib/refusals.ts`:

```ts
/** What a panel refused, and the revision it was refused at. */
export interface Refused {
  text: string;
  revision: number | undefined;
}

/**
 * The refusal a panel shows: the one stored, until the analysis has moved past the revision it
 * was refused at.
 *
 * A stale refusal is the reason this exists. The server refuses an edit whose file changed on
 * disk, and the panel says the files are shown as they are - but the analysis that noticed the
 * change has not finished yet, so everything on screen, the fingerprints included, is still the
 * revision that was refused. Choosing again straight away sends those same fingerprints and is
 * refused a second time. Holding the sentence until the next revision arrives makes it true:
 * the watcher answers within a second, and what comes back is a panel that can be applied.
 */
export function shownRefusal(stored: Refused | null, revision: number | undefined): string | null {
  if (stored === null) return null;
  return stored.revision === revision ? stored.text : null;
}
```

- [ ] **Step 4: Read it in the panels**

In `gui/src/screens/VariablePanel.tsx` and `gui/src/screens/UnitPanel.tsx`, the refusal state
becomes `Refused | null`: set it with `{ text, revision }` where it is set today, read it
through `shownRefusal(refused, revision)` where it is passed to the view, and **stop clearing it
when the reader chooses again** - it clears itself when the revision moves on. Every other
refusal these panels show is set and cleared exactly as it is today; only the stale one gains
the wait, and it gains it by having a revision attached.

`gui/src/screens/FindingsPage.tsx` (Task 7) stores and reads its refusal the same way.

- [ ] **Step 5: A journey proves it**

In `gui/e2e/keys.spec.ts`, beside the journeys of part 3:

```ts
test("a change refused as stale can be applied again once the analysis has caught up", async ({
  page,
  gui,
}) => {
  const panel = await openPanel(page, gui.address, "ValueA");
  await panel.getByRole("row", { name: /^limits/ }).click();
  // The file changes under the page: the preview it is holding is against the old bytes.
  driftMax(gui.directory, CONTROLLER, "ValueA", 60);
  await panel.getByLabel("Max").fill("50");
  await panel.getByRole("button", { name: /^Apply to/ }).click();
  await expect(panel.getByText("A file changed on disk")).toBeVisible();

  // The watcher catches up within a second; the sentence goes and Apply works.
  await expect(panel.getByText("A file changed on disk")).toBeHidden({ timeout: 15000 });
  await panel.getByLabel("Max").fill("50");
  await panel.getByRole("button", { name: /^Apply to/ }).click();
  await expect(panel.getByText("Nothing to change")).toBeVisible({ timeout: 15000 });
});
```

`driftMax` is part 3's `driftFactor` for a range - if `gui/e2e/demo.ts` has no such helper, add
one beside it in the same shape, replacing a variable's `"max"` in one file.

- [ ] **Step 6: Run the page's gate and the journeys**

Run: `cd gui && npm run lint && npm run typecheck && npm test && npm run build && PLAYWRIGHT_CHANNEL=chrome npm run e2e`
Expected: green; `src/lib` still at 100 %.

- [ ] **Step 7: Commit**

```bash
git add gui/src gui/e2e
git commit -m "hold a stale refusal until the analysis has caught up

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 9: The journeys

What a reader does with the tab, end to end, in a real browser against a real server over copies of the examples.

**Files:**
- Create: `gui/e2e/findings.spec.ts`
- Modify: `gui/e2e/demo.ts` (a helper the journeys share), `gui/e2e/units.spec.ts` (the policy journey visits the tab)

- [ ] **Step 1: Write the journeys**

Create `gui/e2e/findings.spec.ts`. Five, each opening the tab from the project screen:

1. **A disagreement leads to its variable.** Drift Controller's `ValueA` unit from outside, open
   the Findings tab, select the `definition-mismatch` row, press **Open ValueA**, and check the
   page is Controller's with `ValueA`'s panel open and its `unit` row selected (part 3's panel
   opens on the row that disagrees).
2. **An unknown unit leads to its unit.** Over `examples/vocabulary`, drift a unit's spelling,
   select the `unknown-unit` row, press **Open**, and check the Units tab is showing that unit's
   panel.
3. **A missing id is fixed.** Over the demo, select a `missing-id` row, press "Give 'X' an id",
   press **Show changes** and check the added line, press **Apply to 1 file**, and read the file
   back: a twelve character id where there was none, and the row gone from the tab.
4. **A finding that leads nowhere says why.** Save a component file half-edited from outside, and
   check its row offers no **Open** and says the file did not load.
5. **The tab says when there is nothing to report**, over a project whose findings are all
   silenced or fixed - `examples/vocabulary` once its drift is undone, or the demo with its
   `missing-id` findings stamped; whichever is true of the copy the fixture serves.

Each journey asserts what a reader sees *and* what the files say afterwards, as parts 1 to 3 do.
A journey that drives a chooser types and presses Enter as well as clicking.

- [ ] **Step 2: The policy journey visits the tab**

In `gui/e2e/units.spec.ts`, the journey that collects Content-Security-Policy violations opens
the Findings tab and selects a row, so the new table and panel are on the page while the console
is watched. Nothing may be reported.

- [ ] **Step 3: Run them on both machines' browsers**

Run (Linux): `cd gui && npm run build && PLAYWRIGHT_CHANNEL=chrome npm run e2e`
Run (Windows): `cd gui && npm run build && DDD_PYTHON=/c/git/ac11/ddd/.venv/Scripts/python.exe PLAYWRIGHT_CHANNEL=msedge npm run e2e`
Expected: every journey passes, parts 1 to 3's included.

- [ ] **Step 4: Commit**

```bash
git add gui/e2e
git commit -m "press a finding and land where it leads, end to end

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 10: The documentation

**Files:**
- Modify: `CHANGELOG.md`, `docs/command_line_interface.rst`, `docs/developer_documentation.rst`, `docs/editor_integration.rst`

- [ ] **Step 1: The changelog**

Under `## Unreleased`, a fourth paragraph on the browser interface, in the voice of the three
beside it: the findings are a tab of their own now - every finding of the project, worst first,
each leading to what it names: the variable's panel, the unit's, or the component's page, and
saying plainly when there is nowhere to go, as for a file that did not load or a types file the
interface has no page for yet.  A producing declaration without an identity is given one from
there, previewed like every other change.  Two spaces after a full stop, as the file writes it.

Beside it, a line of its own about the language server, because it is a behaviour change a user
can see: a reconcile quick fix is no longer offered for a value that already means what it would
be set to - a conversion written over four lines and the same conversion written on one are one
value, as the checks have always counted them.

- [ ] **Step 2: The command page**

In `docs/command_line_interface.rst`, the `ddd gui` row gains the tab in its list of what is one
tab away, keeping the row one clause longer rather than three.

- [ ] **Step 3: The developer page**

After the paragraph on the variable panel's keys, say where a finding leads and what carries it:
`ddd.finding_routes` answers the route from the finding's own file and pointer, `GET /api/state`
carries it on every finding, and `ddd.finding_fixes` plans the one fix a finding has nowhere
else to offer - an identity from the same walk `ddd id` and the language server's own quick fix
read, written as operations rather than as a text edit. Say too that `ddd.lsp.edits.settle` now
compares what a value means, which is why `ddd gui` no longer narrows a settlement of its own.

- [ ] **Step 4: The editor page**

In `docs/editor_integration.rst`, where the reconcile quick fixes are described, say that one is
not offered for a value that already means what it would be set to.

- [ ] **Step 5: Build the documentation and run the Python gate**

```bash
docker compose run --rm --user "$(id -u):$(id -g)" -e JAVA_TOOL_OPTIONS=-Duser.home=/tmp ddd python -m sphinx -M html docs build/docs_out -W
python -m pytest && ruff check . && ruff format --check . && mypy
```

Expected: `build succeeded.` with no warnings, and the Python gate green.

- [ ] **Step 6: Commit**

```bash
git add CHANGELOG.md docs
git commit -m "say what the findings tab does and what the editor stopped offering

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 11: Milestone gate

The whole thing, from a clean build, on the Linux PC. **This task changes no code**: a failure is a task to reopen, not a line to patch here.

- [ ] **Step 1: The Python gate**

```bash
export PATH="$HOME/.local/node-v24.21.0/bin:$PWD/.venv/bin:$PATH"
python -m pytest && ruff check . && ruff format --check . && mypy
```

- [ ] **Step 2: The documentation from nothing**

```bash
rm -rf build/docs_out
docker compose run --rm --user "$(id -u):$(id -g)" -e JAVA_TOOL_OPTIONS=-Duser.home=/tmp ddd python -m sphinx -M html docs build/docs_out -W
```

- [ ] **Step 3: The page, from a clean install**

```bash
cd gui && npm ci && npm run schemas && npm run lint && npm run typecheck && npm test && npm run build && npm run ladle:build
```

- [ ] **Step 4: The journeys and the screenshots**

```bash
cd gui && PLAYWRIGHT_CHANNEL=chrome npm run e2e
cd .. && docker compose run --rm gui-screenshots
```

- [ ] **Step 5: The real application**

`docker compose up gui` over the checkout's own `examples/demo`, driven with Playwright's Chrome
from the host, photographing into `docs/superpowers/plans/2026-09-22-gui-findings/`:

- the Findings tab, worst first, with its counts;
- a finding's panel, its **Open** button and its notes;
- the `missing-id` fix with its changes shown;
- a finding that leads nowhere, saying why.

Look at each with the Read tool before keeping it. Then stop the containers and restore the
examples (`git checkout -- examples/`). No page may report a policy violation.

- [ ] **Step 6: The tree is clean**

```bash
git status --short
```

Expected: nothing but the screenshots the step above added.

- [ ] **Step 7: Commit the screenshots**

```bash
git add docs/superpowers/plans/2026-09-22-gui-findings
git commit -m "keep the findings tab's screenshots beside the plan

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Progress log

Executed on 2026-09-22 by subagent-driven development: an implementer per task, a reviewer after
each, and a scoped re-review after every fix round. Duration and tokens are the implementer's; the
review's follow in brackets. Six of the eleven tasks needed a fix round, and five of those six were
found by a reviewer checking a claim against the code rather than by a failing test.

| Task | Implementer | Duration | Tokens | Notes |
| --- | --- | --- | --- | --- |
| 1 One rule for what a value is | sonnet | 15 min [6 min] | 239 k [172 k] | Clean. No existing test pinned the old text comparison, which the reviewer verified by reading the suite rather than trusting the report. |
| 2 Where a finding leads | sonnet | 5 + 9 min fix [8 + 3 min] | 103 k + 181 k [151 k + 97 k] | One fix round: the route matched only a pointer under a `definition`, so `missing-producer`, `local-conflict` and `condition-mismatch` - all filed on the declaration itself - led to the component's page instead of the variable's panel. |
| 3 The state answers where each finding leads | sonnet | 13 min [6 min] | 178 k [136 k] | Clean. All three endpoints that answer findings carry the route, each building its lookup and its cache once. |
| 4 The fix a finding carries | sonnet | 13 + 5 min fix [8 + 3 min] | 202 k + 237 k [146 k + 95 k] | One fix round: the endpoint would have answered 500 where every sibling answers 409 `unreadable`, for a file rewritten between the two reads of one request. |
| 5 The page's logic | sonnet | 14 min [7 min] | 203 k [142 k] | Clean. The severity map's fourth entry was verified unreachable by construction rather than assumed. |
| 6 The tab's pictures, and their stories | sonnet | 28 + 5 min fix [7 + 2 min] | 337 k + 382 k [156 k + 106 k] | One fix round: all four new fixtures showed real checks at severities they never report, and the stories are these components' only documentation. Two CSS defects were found by looking at the photographs. |
| 7 The tab, and the lists that become links | sonnet | 24 + 14 min fix [5 + 4 min] | 325 k + 459 k [101 k + 125 k] | One fix round, reviewed on opus: a link tore the whole app down to move one page sideways, the new anchors had no focus ring, and a successful fix greeted the reader with a warning. |
| 8 A stale refusal waits for the next revision | sonnet | 12 + 12 min fix [5 + 4 min] | 172 k + 276 k [122 k + 110 k] | One fix round: the wait had been put on every refusal, so a type-fixed one hid Apply until any file changed and carried forward to the next selection. |
| 9 The journeys | sonnet | 28 min [9 min] | 294 k [161 k] | Clean. The reviewer said for each of the five which assertion fails if the feature reverts, and re-ran `ddd check` to confirm both examples report nothing unmodified. |
| 10 The documentation | sonnet | 20 min [6 min] | 232 k [133 k] | Clean. Every claim on the developer page was traced to the module it names. |
| 11 Milestone gate | sonnet | 14 min | 196 k | Every step green from a clean build; four photographs of the real application, each looked at. |

## Left open by the implementers

- **One pattern, written twice.** `ddd.lsp.navigation` already held a private `_WITHIN_DECLARATION`
  with the same regex and a near-identical read-the-name helper; the public one this branch added
  to `ddd.lsp.edits` duplicates it. The ruling that put it there was made without knowing the first
  existed. One public pattern, imported by both, is the honest shape.
- `docs/editor_integration.rst` puts the same-value carve-out after a three-item list, which invites
  a reader to think a removal is gated by it too; only taking and spreading compare values. The
  changelog's parallel sentence names the two correctly.
- Two tests reach a branch by an input the server cannot send: `routeLabel`'s fallback is driven
  with a component route whose file the state does not list, and `_finding(filed, None, {})` proves
  only that the `None` source does not crash, never that the route it answers is `None`.
- `UnitPanel.offer()` short-circuits to `null` once a stale refusal's wait lapses, instead of
  falling through to the plan's own error. Pre-existing; this branch only moved the wait into it.

## Rulings made while writing the plan

1. **The selected finding is not in the address.** A unit has a name and a variable has a name; a finding is an observation that may be gone at the next revision, and pressing one leads somewhere that does have an address. Cost if wrong: a reader cannot link somebody to a finding, only to the tab.
2. **One fix, one file.** `Fix` carries a path and its operations rather than a list of files: that is what a fix is today, and a change reaching several files is a plan, which `ddd.lsp.units` already shows the shape of. Cost if wrong: the second fix that spans files reshapes `Fix` before it is written.
3. **`_WITHIN_DEFINITION` and `_unstamped` are made public** rather than copied. Which pointers name a declaration, and which declarations want an id, are each one rule; a second copy drifts the day the first changes. Cost if wrong: two more names in modules that were private, both documented.
4. **A stale refusal is held by the page, not fixed in the server.** The server's refusal is right - the file did change - and the page's own sentence is what was untrue. Holding it until the next revision makes it true without the endpoint re-reading files the analysis is about to read anyway. Cost if wrong: the reader waits up to a second, which is the watcher's own period.
5. **The findings tab has no filter.** The rows are worst first and grouped by file, which is the order a reader works through them, and the Table tab already carries the per-file counts. Cost if wrong: a project with hundreds of findings scrolls.

### Taken while executing it

6. **Task 6's panel body was described rather than written out**, its props given as code and its markup pointed at `UnitPanelView.tsx`. Why: the component is a picture of its props, its gate is the screenshot and the stories, and copying a 230-line neighbour into a plan rots the day that neighbour changes. Cost if wrong: a panel whose order or markup drifts from the Units tab's, which one fix round settles.
7. **A route matches a pointer anywhere under `component.interface[N]`**, not only under its `definition`, while `WITHIN_DEFINITION` keeps its narrower meaning for the editor's actions and the identity fix. Why: `missing-producer`, `local-conflict` and `condition-mismatch` are all filed on the declaration itself and are all findings about a variable. Cost if wrong: a finding on a declaration's `scope` or `condition` opens the variable's panel, where that key is not shown.
8. **`GET /api/fix` keeps the engine's refusal**, against the implementer's argument that nothing can raise. Why: `fixes_for` and `planned` each read the file inside the one request, so an external write between them is reachable, and answering 500 where every sibling answers 409 is the page losing a sentence it knows how to say. Cost if wrong: one branch and one test for a race nobody sees.
9. **A fixture must be an answer the server could give.** Four stories showed real checks at severities those checks never report; they were set to their real defaults and the references remade. Why: these stories are the components' only documentation, and nothing about them needed the fabrication. Cost if wrong: the photographs' row order changed, which is what remaking them is for.
10. **The panel's chip says the severity, not the check its title already carries.** Why: the chip's tone was the severity and its text was the check, so the panel said one word twice and never said which severity it was. Cost if wrong: a reader reads the severity instead of inferring it from a colour.
11. **Five findings in Task 7 were fixed in one round**, three of them defects a reader meets: a link that reloaded the whole application although the callback for an in-place move was in scope, anchors with no keyboard focus ring, and a successful fix greeted by the warning meant for a finding somebody else fixed. Cost if wrong: a larger fix diff to re-review.
12. **Only the stale refusal waits.** The wait had been attached to every refusal, which hid Apply until any file changed - indefinitely in a project nobody is editing - and carried a refusal forward onto the next selection. Cost if wrong: two pieces of state per panel where there was one.
13. **`UnitsPage`'s adoption refusal was fixed too**, although Task 8 named three screens. Why: the point of the task is that the sentence is true wherever the page says it. Cost if wrong: a fourth screen changed in a task that named three.
