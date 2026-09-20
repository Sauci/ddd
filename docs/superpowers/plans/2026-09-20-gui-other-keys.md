# The other keys in the GUI (part 3) implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The variable panel shows every key a variable's declarations share - a row per key, a column per declaration - says which of them disagree, and settles any one of them on every declaration at once, where today it settles only the unit.

**Architecture:** The navigation index records each object's kind, and a new `ddd.variable_keys` works out, per key, what each declaration's kind may and must hold, which values are in play and who states them, which editor the key takes and what that editor may offer - the loader's own knowledge, in Python, under the 100 % gate. `GET /api/variable` answers those beside the declarations it already answers; `GET /api/settle` and `POST /api/edit` are unchanged, and so is the language server. The page turns the answer into a table of rows and a chooser per key, reusing part 1's picker for the unit and part 2's `Changes`, with a Ladle story and a screenshot for every state.

**Tech Stack:** Python 3.12+ with pydantic; React 19.3, TypeScript 7 strict, TanStack Query 5, `react-aria-components` 1.21.1, `@ladle/react` 5.1.1, Vitest, Playwright 1.63.0 and its image `mcr.microsoft.com/playwright:v1.63.0-noble`.

**Spec:** `docs/superpowers/specs/2026-09-20-gui-other-keys-design.md` (part 3 of three; read it, and the mockups beside it in `docs/superpowers/specs/2026-09-20-gui-other-keys/`, before starting any task). Part 1's spec and plan, `2026-09-18-gui-units-design.md` and `plans/2026-09-18-gui-units.md`, describe the panel, the picker, the design system and the screenshot tests this rebuilds on; part 2's, `2026-09-19-gui-units-project-design.md` and `plans/2026-09-19-gui-units-project.md`, the Units tab and `Changes`.

## Global Constraints

- Python floor 3.12; **no new runtime dependency** of the Python package, and no new frontend dependency.
- Python gate: `python -m pytest` at 100 % line **and** branch coverage, `ruff check .`, `ruff format --check .`, `mypy`. No `pragma: no cover`, no `pytest.skip`/`skipif`/`xfail`/`importorskip`.
- Line length 100; ruff selects E, F, W, I, N, UP, B, SIM, RUF, ANN, PTH, C4; mypy strict with the pydantic plugin.
- **The Python gate runs in every task that touches Python, the documentation, `gui/scripts/licenses.mjs` or anything `tests/test_documentation.py` reads.**
- Every request and answer of the API is declared in `src/ddd/gui/contract.py`; the page's types are generated from it by `npm run schemas`. Never hand-write a type the generator produces.
- Values travel as **raw JSON text**, never as parsed values: `'"rpm"'`, `'{"min": 0, "max": 100}'`, `'true'`, `'4'`. Pointers are DDD's own spelling (`component.interface[0].definition.unit`).
- **The twelve keys are `PROPAGATED_KEYS`** (`src/ddd/lsp/edits.py`): `datatype`, `typename`, `unit`, `conversion`, `limits`, `dimensions`, `size`, `volatile`, `axis`, `x_axis`, `y_axis`, `input`. `kind` is shown and never settled. `id` and `description` are not in the panel at all.
- **`GET /api/settle`, `POST /api/edit`, `ddd.lsp.edits.settle` and the language server are untouched.** Their existing tests pass unchanged; a task that finds itself editing `settle` has misread the plan.
- Vitest keeps its 100 % gate over `src/api`, `src/lib`, `src/state`. Widgets and screens are covered by stories, screenshot tests and end-to-end journeys.
- **A story imports nothing from `@ladle/react`.** A story is a plain exported function component.
- The Content-Security-Policy stays `default-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'none'`, and `gui/public/pressable.css` stays linked from `gui/index.html` under the id `react-aria-pressable-style`. No page may report a violation.
- **A React Aria `className` is a function keeping `defaultClassName`** when a class is added (`({ defaultClassName }) => \`${defaultClassName} has-error\``): a string replaces React Aria's own class, and `ui.css` selects on it.
- **Journeys that drive a picker type and press Enter as well as click an option**: part 1's final review found a typed unit that Enter never chose, which no clicking journey could see.
- **A new or changed story gets its screenshot reference made in Playwright's image** - `UPDATE=1 docker compose run --rm gui-screenshots`, then `docker compose run --rm gui-screenshots` - and every new or changed reference is opened and looked at. References are made nowhere else, and no comparison is loosened.
- `ddd gui` stays labelled **preview**.
- Two machines:
  - **Linux PC** (`/home/sauci/Documents/Github/ddd`): `export PATH="$HOME/.local/node-v24.21.0/bin:$PWD/.venv/bin:$PATH"; export DDD_PYTHON="$PWD/.venv/bin/python"` at the repository root. Journeys: `cd gui && PLAYWRIGHT_CHANNEL=chrome npm run e2e`. The documentation is built in the development image, since this PC has no Java or PlantUML: `docker compose run --rm --user "$(id -u):$(id -g)" -e JAVA_TOOL_OPTIONS=-Duser.home=/tmp ddd python -m sphinx -M html docs build/docs_out -W`. Docker cannot see the session's scratchpad; a throwaway copy that Docker must read goes under the ignored `build/`.
  - **Windows PC** (Git Bash): `export PATH="/c/git/ac11/ddd/.venv/Scripts:/c/Program Files/nodejs:/c/Users/lmbsog0/AppData/Local/Programs/CLion/bin/mingw/bin:$PATH" && cd /c/git/ac11/ddd`; journeys with `DDD_PYTHON=/c/git/ac11/ddd/.venv/Scripts/python.exe PLAYWRIGHT_CHANNEL=msedge npm run e2e`. No Docker: screenshot references are made on the Linux PC or read from CI.

## Prerequisites (before Task 1)

- The branch `feature/gui-other-keys` starts from master after #51 (`9ef0bf3`); the spec and its mockups are its first commit (`bcac139`). The pull request is opened when the branch is finished.
- The venv has `pip install -e ".[dev]"`, `gui/` has `npm ci`, and the gate is green on the branch before anything changes: the Python gate, and `cd gui && npm run schemas && npm run lint && npm run typecheck && npm test && npm run build`.

## Conventions for every task

- Work on `feature/gui-other-keys`. Tests first: write the failing test, watch it fail, implement, watch it pass.
- One commit per task (a fix round may add commits), its message a lowercase sentence saying what the change does, ending with a blank line and `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`. Push after each task.
- Before a task's commit, run the gate for what it touched: the Python gate for Python (and per the constraint above); `npm run lint && npm run typecheck && npm test && npm run build` for the page, `PLAYWRIGHT_CHANNEL=chrome npm run e2e` when a screen or journey changed, and the screenshot service when a story changed.
- After Task 3, `npm run schemas` regenerates `gui/src/generated/api.ts`; run it before any frontend task.
- Scratch files go to the session scratchpad, never into the repository.
- Record each task in the **Progress log** at the end: start time, duration, tokens, notes.

## File structure

| File | Responsibility |
| --- | --- |
| `src/ddd/lsp/navigation.py` | `Index.kinds`: name -> the kind its first declaration states, so a chooser can list the project's axes and measurements without re-reading every file (Task 1). |
| `src/ddd/variable_keys.py` (new) | What each key offers: what a declaration's kind may and must hold, the values in play with who states them, which editor the key takes and what it may offer. Pure - no GUI, no HTTP (Task 2). |
| `src/ddd/gui/contract.py`, `src/ddd/gui/api.py` | `GET /api/variable` answers `keys`, one entry per key of `PROPAGATED_KEYS` (Task 3). |
| `tests/test_variable_keys.py` (new) | The index's kinds, and every offer, kind by kind (Tasks 1-2). |
| `tests/test_gui_api.py`, `tests/test_gui_contract.py` | The endpoint's answer over copies of `examples/demo` and hand-written trees (Task 3). |
| `gui/src/api/types.ts` | The generated key types re-exported (Task 4). |
| `gui/src/lib/variableKeys.ts` (new) | The table's rows and their order, what a cell reads, which chooser a key takes and what it lists, and the json text a choice travels as. Pure (Task 4). |
| `gui/src/lib/units.ts` | `textOf`, `consequence`, `baseName`, `editOf`, `hunkLines`, `pickerSections` and `rawOf` stay as they are and are reused (Task 4); `describe`, `unitOfDeclaration`, `willChange` and `startingUnit`, which only part 1's panel used, go when the panel stops using them (Task 6). |
| `gui/src/components/VariableKeysTable.tsx` (new) | The key x declaration table, a row selected, as a picture of its props (Task 5). |
| `gui/src/components/KeyChooser.tsx` (new) | One key's chooser: the values in play, state nothing, and the editor the key takes (Task 5). |
| `gui/src/components/VariablePanelView.tsx` | Composes the head, the findings, the table, the chooser, the consequence line, Show changes and Apply (Task 6). |
| `gui/src/stories/fixtures.ts` | The answers the stories draw: `keys: []` when the field appears (Task 3), then what each story is about (Task 5). |
| `gui/src/screens/VariablePanel.tsx` | The queries, the selected key, the value chosen for it and the apply (Task 6). |
| `gui/src/screens/ComponentPage.tsx`, `gui/src/screens/GraphPage.tsx` | Unchanged props; `focusPicker` now means "open the panel on the unit's row and focus its chooser" (Task 6). |
| `gui/src/styles/ui.css` | The table's and the chooser's own rules (Task 5). |
| `gui/e2e/keys.spec.ts` (new), `gui/e2e/demo.ts`, `gui/e2e/skeleton.spec.ts` | The journeys, and the policy journey visiting the new table (Task 7). |
| `gui/screenshots/references/*.png` | The two new components' stories (Task 5), and every panel story remade (Task 6). |
| `CHANGELOG.md`, `docs/command_line_interface.rst`, `docs/developer_documentation.rst` | What a user and a developer read (Task 8). |

## Interfaces between the tasks

Every name here is exact; a task's implementer sees only their own task, and this is how they learn what their neighbours produce and consume.

**Task 1 produces** (`src/ddd/lsp/navigation.py`):

```python
kinds: dict[str, str] = field(default_factory=dict)
"""Name -> the kind its first declaration states."""
```

**Task 2 produces** (`src/ddd/variable_keys.py`):

```python
KEY_ORDER: Final[tuple[str, ...]]          # the twelve keys, in the models' own spelling order
DATATYPES: Final[tuple[str, ...]]          # the eleven datatype names
EDITORS: Final[dict[str, str]]             # key -> "unit"|"datatype"|"typename"|"volatile"
                                           #        |"limits"|"size"|"name"|"none"

@dataclass(frozen=True, slots=True)
class Carried:
    allowed: bool
    required: bool

@dataclass(frozen=True, slots=True)
class InPlay:
    raw: str
    components: tuple[str, ...]
    producer: bool

@dataclass(frozen=True, slots=True)
class KeyOffer:
    key: str
    carried: tuple[Carried, ...]           # aligned with the declarations passed in
    values: tuple[InPlay, ...]
    disagrees: bool
    editor: str
    choices: tuple[str, ...]

def offers(built: Index, declared: Sequence[Declared]) -> tuple[KeyOffer, ...]: ...
```

**Task 3 produces** (`src/ddd/gui/contract.py`, and so `gui/src/generated/api.ts`):

```python
class VariableKeyCarried(_Frozen):
    allowed: bool
    required: bool

class VariableKeyValue(_Frozen):
    raw: str
    components: tuple[str, ...]
    producer: bool

class VariableKeyOffer(_Frozen):
    key: str
    carried: tuple[VariableKeyCarried, ...]
    values: tuple[VariableKeyValue, ...]
    disagrees: bool
    editor: Literal["unit", "datatype", "typename", "volatile", "limits", "size", "name", "none"]
    choices: tuple[str, ...]

class VariableReply(_Frozen):
    revision: int
    name: str
    declarations: tuple[VariableDeclaration, ...]
    keys: tuple[VariableKeyOffer, ...]     # new, one per key of PROPAGATED_KEYS, in KEY_ORDER
    findings: tuple[Finding, ...]
```

**Task 4 produces** (`gui/src/lib/variableKeys.ts`):

```ts
export interface KeyCell { text: string; quiet: boolean; from: string | null; changing: boolean }
export interface KeyRow { key: string; cells: KeyCell[]; disagrees: boolean; settleable: boolean }
export interface ValueChoice { id: string; raw: string | null; label: string; detail: string }
export interface ValueSection {
  id: "declared" | "project" | "nothing" | "typed";
  title: string;
  choices: ValueChoice[];
}

export function keyRows(variable: VariableReply, preview: SettleReply | null): KeyRow[];
export function describeVariable(variable: VariableReply): string;
export function shortValue(key: string, raw: string): string;
export function offerOf(variable: VariableReply, key: string): VariableKeyOffer | undefined;
export function startingRaw(variable: VariableReply, key: string): string | null;
export function labelOfRaw(variable: VariableReply, key: string, raw: string | null): string;
export function chooserSections(
  variable: VariableReply,
  key: string,
  typed: string,
): ValueSection[];
export function enteredValue(
  sections: readonly ValueSection[],
  key: string,
  text: string,
): string | null | undefined;
export function limitsOf(raw: string | null): { min: string; max: string };
export function limitsRaw(min: string, max: string): string | null;
export function willChangeKey(
  preview: SettleReply,
  declaration: VariableDeclaration,
  key: string,
): boolean;
```

**Task 5 produces** (`gui/src/components/`):

```ts
export interface VariableKeysTableProps {
  variable: VariableReply;
  preview: SettleReply | null;
  selected: string | undefined;
  onSelect: (key: string | undefined) => void;
}

export interface KeyChooserProps {
  variable: VariableReply;
  keyName: string;                // which key is being settled
  units: UnitsReply;
  chosen: string | null;          // the json text chosen, `null` for "state nothing"
  typed: string;                  // what the field reads
  narrow: string;                 // what filters the list: "" unless the reader is typing
  onTyped: (text: string) => void;
  onChosen: (raw: string | null) => void;
  onPickerClosed: () => void;
  range: { min: string; max: string };        // the two fields, while the key is `limits`
  onRange: (range: { min: string; max: string }) => void;
  note: string | undefined;
  busy: boolean;
  focus: number | null;
  pickerTrigger?: "input" | "focus" | undefined;
}
```

**Task 6 consumes** all of the above; the props of `VariablePanel` (`name`, `revision`, `stopped`, `focusPicker`, `onClose`, `onUndeclared`) do not change, so `ComponentPage.tsx` and `GraphPage.tsx` keep their call sites.

---

### Task 1: The index records each object's kind

A chooser for `axis`, `x_axis`, `y_axis` or `input` lists the project's axes and its measurements. The index already walks every declaration of every component; recording the kind as it goes is what lets the answer name them without reading the whole project again per request.

**Files:**
- Modify: `src/ddd/lsp/navigation.py` (the `Index` dataclass, and the declaration loop of `index()`)
- Test: `tests/test_variable_keys.py` (new)

**Interfaces:**
- Consumes: `Index`, `index(workspace)`, `Site` - all as they stand.
- Produces: `Index.kinds: dict[str, str]`, name -> the kind its first declaration states (`"measurement"`, `"axis"`, `"curve"`, `"map"`, `"value_block"`, `"parameter"`).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_variable_keys.py`:

```python
"""What every key of a variable offers the panel of ``ddd gui``, and the kinds the index records."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from conftest import component, declare, project, write_tree
from ddd.diagnostics import DiagnosticBag
from ddd.loading import load_workspace
from ddd.lsp.navigation import Index, index

def built(tmp_path: Path, **files: Any) -> Index:
    """The index of a project of these files, named by a project description of the same name."""
    write_tree(tmp_path, {"p.ddd.json": project("P", *files), **files})
    workspace = load_workspace(tmp_path / "p.ddd.json", DiagnosticBag())
    assert workspace is not None
    return index(workspace)

def one_of_each(tmp_path: Path) -> Index:
    """A component declaring one object of every kind, the axis-shaped ones referring to `Points`."""
    return built(
        tmp_path,
        **{
            "a.ddd.json": component(
                "A",
                declare("output", "Speed", unit="rpm"),
                declare("output", "Points", kind="axis", size=4),
                declare("output", "Torque", kind="curve", axis="Points"),
                declare("output", "Grid", kind="map", x_axis="Points", y_axis="Points"),
                declare("output", "Block", kind="value_block", dimensions=[3, 4]),
                declare("output", "Gain", kind="parameter"),
            )
        },
    )

class TestKinds:
    def test_every_object_is_recorded_with_the_kind_it_states(self, tmp_path: Path) -> None:
        assert one_of_each(tmp_path).kinds == {
            "Speed": "measurement",
            "Points": "axis",
            "Torque": "curve",
            "Grid": "map",
            "Block": "value_block",
            "Gain": "parameter",
        }

    def test_a_name_two_components_declare_keeps_the_kind_of_the_first(self, tmp_path: Path) -> None:
        # Declarations that disagree about their kind are two objects under one name, which
        # `definition-mismatch` reports and no chooser settles: the index records one kind, and
        # the first component the project lists is the one it reads it from.
        idx = built(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", kind="parameter")),
            },
        )
        assert idx.kinds == {"Speed": "measurement"}
```

- [ ] **Step 2: Run them to watch them fail**

Run: `python -m pytest tests/test_variable_keys.py -v`
Expected: FAIL - `AttributeError: 'Index' object has no attribute 'kinds'`.

- [ ] **Step 3: Record the kind**

In `src/ddd/lsp/navigation.py`, add the field to `Index` after `constant_uses` and before `occupied`:

```python
    kinds: dict[str, str] = field(default_factory=dict)
    """Name -> the kind its first declaration states, in the order the project lists its
    components.

    What a chooser naming an object reads: the ``axis`` of a curve is one of the project's
    axes, the ``input`` of an axis one of its measurements. One kind per name rather than one
    per declaration, because declarations disagreeing about their kind are two objects under
    one name - which ``definition-mismatch`` reports and no chooser can settle, ``kind`` being
    the one shared key an edit may not carry from one declaration to another (see
    :data:`ddd.lsp.edits.PROPAGATED_KEYS`).
    """
```

In `index()`, inside the declaration loop, beside `built.declarations.setdefault(...)`:

```python
            built.kinds.setdefault(name, declaration.definition.kind.value)
```

- [ ] **Step 4: Run the tests to watch them pass**

Run: `python -m pytest tests/test_variable_keys.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Run the Python gate**

Run: `python -m pytest && ruff check . && ruff format --check . && mypy`
Expected: all green, coverage still 100 %.

- [ ] **Step 6: Commit**

```bash
git add src/ddd/lsp/navigation.py tests/test_variable_keys.py
git commit -m "record each object's kind in the navigation index

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: What a key offers

The panel settles one key of a variable on every declaration at once. What it may offer for a key - which declarations may hold it and which must, what is already in play and who states it, which editor it takes and what that editor lists - is the loader's own knowledge, and this is where it lives. Pure: no GUI, no HTTP, no pydantic.

**Files:**
- Create: `src/ddd/variable_keys.py`
- Test: `tests/test_variable_keys.py` (extend Task 1's file)

**Interfaces:**
- Consumes: `Index` and `Index.kinds` (Task 1); `ddd.variables.Declared` with its `stated`, `fixed`, `component` and `role`; `ddd.lsp.edits.PROPAGATED_KEYS`; `ddd.models.definition_keys`; `ddd.models.common.Datatype`.
- Produces: `KEY_ORDER`, `DATATYPES`, `EDITORS`, `Carried`, `InPlay`, `KeyOffer`, `offers(built, declared)` - exactly as the Interfaces section at the top spells them.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_variable_keys.py` (and add the imports its new names need at the top:
`from ddd.variable_keys import Carried, DATATYPES, EDITORS, InPlay, KEY_ORDER, offers` and
`from ddd.variables import declarations_of`, plus `from ddd.lsp.edits import PROPAGATED_KEYS`
and `from conftest import scalar_type, types` for the typed fixtures):

```python
def offered(idx: Index, name: str, key: str) -> Any:
    """The one offer for ``key`` among those made for ``name``'s declarations."""
    return next(offer for offer in offers(idx, declarations_of(idx, name, {})) if offer.key == key)

class TestTheKeysOffered:
    def test_every_propagated_key_is_offered_once_in_the_models_own_order(
        self, tmp_path: Path
    ) -> None:
        made = offers(one_of_each(tmp_path), declarations_of(one_of_each(tmp_path), "Speed", {}))
        assert [offer.key for offer in made] == list(KEY_ORDER)
        assert set(KEY_ORDER) == PROPAGATED_KEYS
        assert set(EDITORS) == PROPAGATED_KEYS

    def test_the_eleven_datatypes_are_what_a_datatype_may_be(self, tmp_path: Path) -> None:
        assert offered(one_of_each(tmp_path), "Speed", "datatype").choices == (
            "boolean",
            "uint8",
            "sint8",
            "uint16",
            "sint16",
            "uint32",
            "sint32",
            "uint64",
            "sint64",
            "float32",
            "float64",
        )
        assert DATATYPES == offered(one_of_each(tmp_path), "Speed", "datatype").choices

class TestWhatAKindCarries:
    def test_a_measurement_may_hold_dimensions_and_must_hold_its_volatile(
        self, tmp_path: Path
    ) -> None:
        idx = one_of_each(tmp_path)
        assert offered(idx, "Speed", "dimensions").carried == (Carried(allowed=True, required=False),)
        assert offered(idx, "Speed", "volatile").carried == (Carried(allowed=True, required=True),)
        assert offered(idx, "Speed", "size").carried == (Carried(allowed=False, required=False),)

    def test_a_value_block_must_hold_the_dimensions_a_measurement_may_leave_out(
        self, tmp_path: Path
    ) -> None:
        idx = one_of_each(tmp_path)
        assert offered(idx, "Block", "dimensions").carried == (Carried(allowed=True, required=True),)

    def test_an_axis_holds_a_size_it_must_state_and_an_input_it_need_not(
        self, tmp_path: Path
    ) -> None:
        idx = one_of_each(tmp_path)
        assert offered(idx, "Points", "size").carried == (Carried(allowed=True, required=True),)
        assert offered(idx, "Points", "input").carried == (Carried(allowed=True, required=False),)

    def test_a_curve_holds_its_axis_and_a_map_both_of_its_own(self, tmp_path: Path) -> None:
        idx = one_of_each(tmp_path)
        assert offered(idx, "Torque", "axis").carried == (Carried(allowed=True, required=True),)
        assert offered(idx, "Grid", "x_axis").carried == (Carried(allowed=True, required=True),)
        assert offered(idx, "Grid", "y_axis").carried == (Carried(allowed=True, required=True),)
        assert offered(idx, "Grid", "axis").carried == (Carried(allowed=False, required=False),)

    def test_a_parameter_holds_none_of_the_shaped_keys(self, tmp_path: Path) -> None:
        idx = one_of_each(tmp_path)
        for key in ("dimensions", "size", "input", "axis", "x_axis", "y_axis"):
            assert offered(idx, "Gain", key).carried == (Carried(allowed=False, required=False),)

    def test_the_storage_a_declaration_uses_is_one_it_may_not_be_left_without(
        self, tmp_path: Path
    ) -> None:
        # `definition_keys` derives what a kind requires from the models' fields, where every
        # one of these three is optional: a definition states either a datatype with its
        # conversion or the name of a type that fixes both. Offering to strip the one the
        # declaration actually uses would write a file the loader refuses.
        idx = built(
            tmp_path,
            **{
                "types.ddd.json": types(scalar_type("Speed_t", unit="rpm")),
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", typename="Speed_t")),
            },
        )
        assert offered(idx, "Speed", "datatype").carried == (
            Carried(allowed=True, required=True),
            Carried(allowed=True, required=False),
        )
        assert offered(idx, "Speed", "conversion").carried == (
            Carried(allowed=True, required=True),
            Carried(allowed=True, required=False),
        )
        assert offered(idx, "Speed", "typename").carried == (
            Carried(allowed=True, required=False),
            Carried(allowed=True, required=True),
        )

    def test_a_declaration_whose_file_lost_its_kind_carries_nothing(self, tmp_path: Path) -> None:
        # The index was built from a file that loaded; what a declaration states is read again
        # from the file as it stands now, which may have moved on. A kind this reader does not
        # know means "offer nothing" rather than an error of its own.
        idx = built(tmp_path, **{"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))})
        edited(tmp_path / "a.ddd.json", lambda definition: definition.pop("kind"))
        assert offered(idx, "Speed", "unit").carried == (Carried(allowed=False, required=False),)

    def test_a_kind_written_as_a_number_carries_nothing_either(self, tmp_path: Path) -> None:
        idx = built(tmp_path, **{"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))})
        edited(tmp_path / "a.ddd.json", lambda definition: definition.__setitem__("kind", 3))
        assert offered(idx, "Speed", "unit").carried == (Carried(allowed=False, required=False),)

class TestWhatIsInPlay:
    def test_each_value_is_listed_once_with_the_components_stating_it(self, tmp_path: Path) -> None:
        idx = built(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="%")),
                "c.ddd.json": component("C", declare("input", "Speed", unit="%")),
            },
        )
        assert offered(idx, "Speed", "unit").values == (
            InPlay(raw='"rpm"', components=("A",), producer=True),
            InPlay(raw='"%"', components=("B", "C"), producer=False),
        )

    def test_the_producers_value_comes_first_however_the_project_lists_it(
        self, tmp_path: Path
    ) -> None:
        idx = built(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("input", "Speed", unit="%")),
                "b.ddd.json": component("B", declare("output", "Speed", unit="rpm")),
            },
        )
        assert offered(idx, "Speed", "unit").values == (
            InPlay(raw='"rpm"', components=("B",), producer=True),
            InPlay(raw='"%"', components=("A",), producer=False),
        )

    def test_a_value_a_named_type_fixes_is_in_play_like_any_other(self, tmp_path: Path) -> None:
        idx = built(
            tmp_path,
            **{
                "types.ddd.json": types(scalar_type("Speed_t", unit="rpm")),
                "a.ddd.json": component("A", declare("output", "Speed", typename="Speed_t")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="%")),
            },
        )
        assert offered(idx, "Speed", "unit").values == (
            InPlay(raw='"rpm"', components=("A",), producer=True),
            InPlay(raw='"%"', components=("B",), producer=False),
        )

    def test_one_value_written_two_ways_is_one_value_in_play(self, tmp_path: Path) -> None:
        # A conversion is an object, and an object's keys may be written in any order: the two
        # declarations below mean the same linear conversion, which `definition-mismatch` does
        # not report and the panel does not offer to settle. The spelling carried is the
        # producer's, so that applying it leaves the producer's own file alone.
        idx = built(
            tmp_path,
            **{
                "a.ddd.json": component(
                    "A",
                    declare(
                        "output",
                        "Speed",
                        conversion={"kind": "linear", "factor": 2, "offset": 0},
                    ),
                ),
                "b.ddd.json": component(
                    "B",
                    declare(
                        "input",
                        "Speed",
                        conversion={"offset": 0, "factor": 2, "kind": "linear"},
                    ),
                ),
            },
        )
        values = offered(idx, "Speed", "conversion").values
        assert [(value.components, value.producer) for value in values] == [(("A", "B"), True)]
        assert json.loads(values[0].raw) == {"kind": "linear", "factor": 2, "offset": 0}
        assert list(json.loads(values[0].raw)) == ["kind", "factor", "offset"]

    def test_a_key_nobody_states_has_nothing_in_play(self, tmp_path: Path) -> None:
        idx = built(tmp_path, **{"a.ddd.json": component("A", declare("output", "Speed"))})
        assert offered(idx, "Speed", "unit").values == ()

class TestWhatDisagrees:
    def test_two_values_in_play_disagree(self, tmp_path: Path) -> None:
        idx = built(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="%")),
            },
        )
        assert offered(idx, "Speed", "unit").disagrees is True

    def test_one_value_beside_a_declaration_stating_none_disagrees(self, tmp_path: Path) -> None:
        idx = built(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed")),
            },
        )
        assert offered(idx, "Speed", "unit").disagrees is True

    def test_limits_left_out_defer_rather_than_disagree(self, tmp_path: Path) -> None:
        idx = built(
            tmp_path,
            **{
                "a.ddd.json": component(
                    "A", declare("output", "Speed", limits={"min": 0, "max": 100})
                ),
                "b.ddd.json": component("B", declare("input", "Speed")),
            },
        )
        assert offered(idx, "Speed", "limits").disagrees is False

    def test_two_ranges_disagree_like_any_other_two_values(self, tmp_path: Path) -> None:
        idx = built(
            tmp_path,
            **{
                "a.ddd.json": component(
                    "A", declare("output", "Speed", limits={"min": 0, "max": 100})
                ),
                "b.ddd.json": component(
                    "B", declare("input", "Speed", limits={"min": 0, "max": 50})
                ),
            },
        )
        assert offered(idx, "Speed", "limits").disagrees is True

    def test_a_key_nobody_states_does_not_disagree(self, tmp_path: Path) -> None:
        idx = built(tmp_path, **{"a.ddd.json": component("A", declare("output", "Speed"))})
        assert offered(idx, "Speed", "unit").disagrees is False

    def test_a_declaration_whose_kind_cannot_hold_the_key_is_not_asked(
        self, tmp_path: Path
    ) -> None:
        # Two kinds under one name are two objects, which `definition-mismatch` reports; the
        # `dimensions` of the measurement is not made a disagreement by the parameter beside it,
        # which has no dimensions to state.
        idx = built(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("output", "Speed", dimensions=[4])),
                "b.ddd.json": component("B", declare("input", "Speed", kind="parameter")),
            },
        )
        assert offered(idx, "Speed", "dimensions").disagrees is False

class TestWhatAnEditorOffers:
    def test_a_name_is_chosen_from_the_objects_of_the_kind_the_key_takes(
        self, tmp_path: Path
    ) -> None:
        idx = one_of_each(tmp_path)
        for key in ("axis", "x_axis", "y_axis"):
            assert offered(idx, "Torque", key).editor == "name"
            assert offered(idx, "Torque", key).choices == ("Points",)
        assert offered(idx, "Points", "input").choices == ("Speed",)

    def test_a_typename_is_chosen_from_the_types_the_project_declares(self, tmp_path: Path) -> None:
        idx = built(
            tmp_path,
            **{
                "types.ddd.json": types(scalar_type("Speed_t", unit="rpm"), scalar_type("Raw_t")),
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
            },
        )
        offer = offered(idx, "Speed", "typename")
        assert (offer.editor, offer.choices) == ("typename", ("Raw_t", "Speed_t"))

    def test_a_size_is_chosen_from_the_constants_the_project_declares(self, tmp_path: Path) -> None:
        idx = built(
            tmp_path,
            **{
                "constants.ddd.json": {"constants": [{"name": "CELLS", "value": 4}]},
                "a.ddd.json": component("A", declare("output", "Points", kind="axis", size=4)),
            },
        )
        offer = offered(idx, "Points", "size")
        assert (offer.editor, offer.choices) == ("size", ("CELLS",))

    def test_the_keys_the_page_writes_itself_list_nothing(self, tmp_path: Path) -> None:
        idx = one_of_each(tmp_path)
        assert [(offered(idx, "Speed", key).editor, offered(idx, "Speed", key).choices)
                for key in ("unit", "volatile", "limits", "conversion", "dimensions")] == [
            ("unit", ()),
            ("volatile", ()),
            ("limits", ()),
            ("none", ()),
            ("none", ()),
        ]
```

And the small helper the two "file moved on" tests use, beside `built`:

```python
def edited(path: Path, change: Any) -> None:
    """Change the first declaration's definition in place, as a save from an editor would."""
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data["component"]["interface"][0]["definition"])
    path.write_text(json.dumps(data, indent=2), encoding="utf-8", newline="")
```

- [ ] **Step 2: Run them to watch them fail**

Run: `python -m pytest tests/test_variable_keys.py -v`
Expected: FAIL - `ModuleNotFoundError: No module named 'ddd.variable_keys'`.

- [ ] **Step 3: Write the module**

Create `src/ddd/variable_keys.py`:

```python
"""What each key of a variable offers the panel of ``ddd gui``.

The panel settles one key of a variable at a time, on every declaration of it at once. What it
may offer for a key is the loader's own knowledge - which kinds carry which key, which of them
have to state it, what is already in play, and what a name may be - so it is worked out here,
once, and the page draws what it is given. No GUI and no HTTP: :mod:`ddd.gui.api` turns these
into the shape ``GET /api/variable`` answers, and nothing else reads them.

The values are raw json text throughout, as everywhere else in this interface: what the file
says, spelled the way it says it, which is what :func:`ddd.lsp.edits.settle` compares and what
an edit writes back.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from ddd.lsp.edits import DEFERRED_KEYS, PROPAGATED_KEYS
from ddd.lsp.navigation import Index
from ddd.models import definition_keys
from ddd.models.common import Datatype
from ddd.models.objects import ObjectKind
from ddd.variables import Declared

KEY_ORDER: Final = (
    "datatype",
    "typename",
    "unit",
    "conversion",
    "limits",
    "dimensions",
    "size",
    "volatile",
    "axis",
    "x_axis",
    "y_axis",
    "input",
)
"""Every key of :data:`ddd.lsp.edits.PROPAGATED_KEYS`, in the order a definition spells them:
what it is made of, what it means, what shape it has, and what it refers to.

An order rather than the frozenset itself, because an answer has to list them somehow and a
page cannot sort what it does not understand. The page groups the rows it draws - what the
declarations disagree about first - and keeps this order inside each group.
"""

DATATYPES: Final = tuple(datatype.value for datatype in Datatype)
"""The eleven names a ``datatype`` may be, from the models rather than a copy of them."""

EDITORS: Final = {
    "datatype": "datatype",
    "typename": "typename",
    "unit": "unit",
    "conversion": "none",
    "limits": "limits",
    "dimensions": "none",
    "size": "size",
    "volatile": "volatile",
    "axis": "name",
    "x_axis": "name",
    "y_axis": "name",
    "input": "name",
}
"""Which field the page offers beside the values already in play, per key.

``none`` is not "nothing may be chosen": a value in play is always offered, and for a
``conversion`` or a ``dimensions`` that is all - four kinds of conversion, an enumeration's
enumerators and a list of dimensions are a second loader's worth of form, and an editor writes
them better than a panel would. The rest are one field wide: a name, a number, a truth value,
a range, or part 1's unit picker.
"""

@dataclass(frozen=True, slots=True)
class Carried:
    """What one declaration's kind does with a key."""

    allowed: bool
    """Its kind has this key at all: ``dimensions`` on a measurement, never on a parameter."""

    required: bool
    """It cannot be left without it - so the panel offers no "state nothing"."""

@dataclass(frozen=True, slots=True)
class InPlay:
    """One value a key has among the declarations, and who has it."""

    raw: str
    """The json text, as the file spells it."""

    components: tuple[str, ...]
    """The components stating it, in the order the project lists them."""

    producer: bool
    """The producer is one of them."""

@dataclass(frozen=True, slots=True)
class KeyOffer:
    """What one key offers for one variable."""

    key: str
    carried: tuple[Carried, ...]
    """One per declaration, in the order they were passed in."""

    values: tuple[InPlay, ...]
    """Every distinct value in play, the producer's first."""

    disagrees: bool
    """The declarations do not all say the same thing about the key."""

    editor: str
    """One of :data:`EDITORS`."""

    choices: tuple[str, ...]
    """What that editor names, sorted: datatypes, types, constants or objects."""

def offers(built: Index, declared: Sequence[Declared]) -> tuple[KeyOffer, ...]:
    """What every key offers for these declarations of one variable, in :data:`KEY_ORDER`."""
    return tuple(_offer(built, declared, key) for key in KEY_ORDER)

def _offer(built: Index, declared: Sequence[Declared], key: str) -> KeyOffer:
    carried = tuple(_carried(entry, key) for entry in declared)
    values = _in_play(declared, key)
    return KeyOffer(
        key=key,
        carried=carried,
        values=values,
        disagrees=_disagrees(declared, carried, values, key),
        editor=EDITORS[key],
        choices=_choices(built, key),
    )

def _disagrees(
    declared: Sequence[Declared],
    carried: Sequence[Carried],
    values: Sequence[InPlay],
    key: str,
) -> bool:
    """Whether the declarations say different things about the key.

    Two values in play are a disagreement, and so is one value beside a declaration that may
    hold the key and states none: silence is a value, which is what ``definition-mismatch``
    reports. Except for a deferred key - a declaration stating no ``limits`` leaves them to
    whoever states them, and the check compares limits only where both sides state them. A
    declaration whose kind cannot hold the key at all is not part of the question, and a key
    nobody states is not a disagreement but an interface nobody has written down yet.
    """
    if len(values) > 1:
        return True
    if not values or key in DEFERRED_KEYS:
        return False
    stating = sum(1 for entry in declared if key in entry.stated or key in entry.fixed)
    return stating < sum(1 for may in carried if may.allowed)

def _carried(entry: Declared, key: str) -> Carried:
    accepted, required = definition_keys(_kind_of(entry))
    return Carried(allowed=key in accepted, required=key in required or key in _storage_of(entry))

def _kind_of(entry: Declared) -> str:
    """The kind the declaration states, or ``""`` when its file states none.

    The index was built from files that loaded; what a declaration states is read again from
    the file as it stands, which may have moved on since. A kind the models do not know means
    "offer nothing", which is what :func:`ddd.models.definition_keys` answers for it.
    """
    raw = entry.stated.get("kind")
    # Raw text of a parsed document: json, always, so there is nothing here to fail on.
    value = None if raw is None else json.loads(raw)
    return value if isinstance(value, str) else ""

def _storage_of(entry: Declared) -> frozenset[str]:
    """The storage keys this declaration cannot be left without.

    :func:`ddd.models.definition_keys` derives what a kind requires from the models' own
    fields, where ``datatype``, ``typename`` and ``conversion`` are each optional: a definition
    states either a datatype with the conversion that goes with it, or the name of a type that
    fixes both, and the models check the pair after the fact. Offering to strip the one a
    declaration actually uses would write a file the loader refuses, so the panel does not
    offer it.
    """
    if "typename" in entry.stated:
        return frozenset({"typename"})
    if "datatype" in entry.stated:
        return frozenset({"datatype", "conversion"})
    return frozenset()

def _in_play(declared: Sequence[Declared], key: str) -> tuple[InPlay, ...]:
    """Every distinct value the key has, the producer's first, then in the project's own order.

    A declaration naming a type has the value that type fixes, counted with the rest: the
    chooser lists what the variable means today, not what each file happens to spell.

    One value, however it is written. The json text carries the layout of the file it came from
    and the order that file wrote an object's keys in, so a conversion of the same meaning can
    read two ways; the checker compares the values rather than the text, and so does this. The
    spelling carried is the producer's where the producer has the value, so that applying what
    the producer already states leaves its file alone.
    """
    stating: dict[str, list[str]] = {}
    spelling: dict[str, str] = {}
    produced: set[str] = set()
    for entry in declared:
        raw = entry.stated.get(key, entry.fixed.get(key))
        if raw is None:
            continue
        # Raw text of a parsed document: json, always, so there is nothing here to fail on.
        same = json.dumps(json.loads(raw), sort_keys=True)
        stating.setdefault(same, []).append(entry.component)
        if same not in spelling or entry.role == "produces":
            spelling[same] = raw
        if entry.role == "produces":
            produced.add(same)
    # Stable, so the producer's value leads and the others keep the order the project lists them.
    ordered = sorted(stating, key=lambda same: same not in produced)
    return tuple(
        InPlay(raw=spelling[same], components=tuple(stating[same]), producer=same in produced)
        for same in ordered
    )

def _choices(built: Index, key: str) -> tuple[str, ...]:
    """What the key's editor names, for the editors that name something."""
    if key == "datatype":
        return DATATYPES
    if key == "typename":
        return tuple(sorted(built.types))
    if key == "size":
        return tuple(sorted(built.constants))
    if key in ("axis", "x_axis", "y_axis"):
        return _objects(built, ObjectKind.AXIS)
    if key == "input":
        return _objects(built, ObjectKind.MEASUREMENT)
    return ()

def _objects(built: Index, kind: ObjectKind) -> tuple[str, ...]:
    """Every object of that kind the project declares, by name.

    A measurement that is an instance of a declared structure is listed with the rest, although
    an ``input`` may not name one: what a name may refer to beyond its kind is the loader's
    answer, and it gives it on the next analysis, exactly as it does for a file edited by hand.
    """
    return tuple(sorted(name for name, stated in built.kinds.items() if stated == kind.value))
```

- [ ] **Step 4: Run the tests to watch them pass**

Run: `python -m pytest tests/test_variable_keys.py -v`
Expected: PASS.

- [ ] **Step 5: Run the Python gate**

Run: `python -m pytest && ruff check . && ruff format --check . && mypy`
Expected: all green, coverage 100 % line and branch. A line of `variable_keys.py` no test reaches is a test missing, not a `pragma`.

- [ ] **Step 6: Commit**

```bash
git add src/ddd/variable_keys.py tests/test_variable_keys.py
git commit -m "work out what each key of a variable offers

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: The endpoint answers what every key offers

`GET /api/variable` already answers, per declaration, the json text of `kind` and of every shared key it states, the type it names and what that type fixes. It gains the offers of Task 2 beside them. `GET /api/settle` and `POST /api/edit` are not touched.

**Files:**
- Modify: `src/ddd/gui/contract.py` (three models, and one field on `VariableReply`)
- Modify: `src/ddd/gui/api.py` (`_variable`; `_declared` folded into it)
- Modify: `gui/src/api/types.ts` (the three generated names re-exported)
- Test: `tests/test_gui_api.py` (class `TestVariable`)

**Interfaces:**
- Consumes: `offers`, `KEY_ORDER` (Task 2); `Revision.index`; `declarations_of`.
- Produces: `VariableKeyCarried`, `VariableKeyValue`, `VariableKeyOffer` and `VariableReply.keys` - the shape the Interfaces section at the top spells, and so the generated `gui/src/generated/api.ts`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_gui_api.py`, add to `class TestVariable` (and import what they name:
`from ddd.variable_keys import KEY_ORDER`):

```python
    def test_every_shared_key_is_answered_with_what_it_offers(self, api: Api) -> None:
        offered = {offer["key"]: offer for offer in get(api, "/api/variable", name="Speed").body["keys"]}
        assert list(offered) == list(KEY_ORDER)
        # Both declarations of the root fixture are measurements stating rpm.
        assert offered["unit"]["values"] == [
            {"raw": '"rpm"', "components": ["A", "B"], "producer": True}
        ]
        assert offered["volatile"]["carried"] == [
            {"allowed": True, "required": True},
            {"allowed": True, "required": True},
        ]
        assert offered["size"]["carried"] == [
            {"allowed": False, "required": False},
            {"allowed": False, "required": False},
        ]

    def test_the_keys_that_disagree_say_so(self, api: Api, root: Path) -> None:
        assert post(api, "/api/edit", unit_edit(api, root, "%")).status == 200
        offered = {
            offer["key"]: offer for offer in get(api, "/api/variable", name="Speed").body["keys"]
        }
        assert offered["unit"]["disagrees"] is True
        assert offered["datatype"]["disagrees"] is False
        assert offered["limits"]["disagrees"] is False

    def test_a_key_says_which_field_chooses_it_and_what_that_field_lists(self, api: Api) -> None:
        offered = {offer["key"]: offer for offer in get(api, "/api/variable", name="Speed").body["keys"]}
        assert (offered["datatype"]["editor"], offered["datatype"]["choices"][:2]) == (
            "datatype",
            ["boolean", "uint8"],
        )
        assert (offered["conversion"]["editor"], offered["conversion"]["choices"]) == ("none", [])
        assert (offered["unit"]["editor"], offered["limits"]["editor"]) == ("unit", "limits")

    def test_a_value_a_type_fixes_is_in_play_and_its_storage_is_not_removable(
        self, tmp_path: Path
    ) -> None:
        offered = {
            offer["key"]: offer
            for offer in get(opened(tmp_path, TYPED), "/api/variable", name="Speed").body["keys"]
        }
        # `a.ddd.json` names Speed_t, which fixes rpm; `b.ddd.json` states % itself.
        assert offered["unit"]["values"] == [
            {"raw": '"rpm"', "components": ["A"], "producer": True},
            {"raw": '"%"', "components": ["B"], "producer": False},
        ]
        assert offered["typename"]["carried"] == [
            {"allowed": True, "required": True},
            {"allowed": True, "required": False},
        ]
        assert offered["typename"]["choices"] == ["Speed_t"]

    def test_a_key_naming_an_object_lists_the_projects_objects_of_that_kind(
        self, tmp_path: Path
    ) -> None:
        api = opened_example(tmp_path, "demo", "demo.ddd.json")
        offered = {
            offer["key"]: offer for offer in get(api, "/api/variable", name="MapA").body["keys"]
        }
        # The demo's map is declared once, local to Controller, over the two axes it declares.
        assert offered["x_axis"]["values"] == [
            {"raw": '"AxisA"', "components": ["Controller"], "producer": False}
        ]
        assert offered["x_axis"]["choices"] == ["AxisA", "AxisB"]
        assert offered["y_axis"]["choices"] == ["AxisA", "AxisB"]
        # A map has no `axis` of its own, and the axes are not measurements.
        assert offered["axis"]["carried"] == [{"allowed": False, "required": False}]
        assert "ValueA" in offered["input"]["choices"]
        assert "AxisA" not in offered["input"]["choices"]

    def test_one_value_two_files_spell_differently_is_one_value_in_play(
        self, tmp_path: Path
    ) -> None:
        api = opened_example(tmp_path, "demo", "demo.ddd.json")
        offered = {
            offer["key"]: offer for offer in get(api, "/api/variable", name="ValueA").body["keys"]
        }
        # SensorHub writes ValueA's conversion over four lines and Controller writes it on one:
        # one conversion, in the producer's spelling, and a row the panel does not mark.
        assert [
            (value["components"], value["producer"]) for value in offered["conversion"]["values"]
        ] == [(["Controller", "SensorHub"], True)]
        assert json.loads(offered["conversion"]["values"][0]["raw"])["kind"] == "linear"
        assert "\n" in offered["conversion"]["values"][0]["raw"]
```

And, in `class TestSettle` - `/api/settle` itself does not change, but no test settles anything
but a unit today, and spec 7 asks for a key of each shape over a copy of the examples:

```python
    @pytest.mark.parametrize(
        ("name", "key", "raw", "written"),
        [
            ("ValueA", "unit", '"Hz"', "Hz"),
            ("ValueA", "limits", '{"min": 0, "max": 50}', {"min": 0, "max": 50}),
            (
                "ValueA",
                "conversion",
                '{"kind": "linear", "factor": 0.25}',
                {"kind": "linear", "factor": 0.25},
            ),
            ("ValueA", "volatile", "true", True),
            ("CurveA", "axis", '"AxisB"', "AxisB"),
        ],
    )
    def test_a_key_of_any_shape_previews_without_writing_and_applies_what_it_said(
        self, tmp_path: Path, name: str, key: str, raw: str, written: Any
    ) -> None:
        api = opened_example(tmp_path, "demo", "demo.ddd.json")
        root = tmp_path / "demo"
        before = contents(root)
        preview = get(api, "/api/settle", name=name, key=key, raw=raw)
        assert preview.status == 200
        assert contents(root) == before, "a preview writes nothing"
        edit = {
            "changes": [
                {field: change[field] for field in ("file", "fingerprint", "operations")}
                for change in preview.body["changes"]
            ]
        }
        assert post(api, "/api/edit", edit).status == 200
        for declaration in get(api, "/api/variable", name=name).body["declarations"]:
            assert json.loads(declaration["stated"][key]) == written

    def test_a_key_a_declarations_kind_cannot_hold_is_refused_whole(self, tmp_path: Path) -> None:
        # Two kinds under one name: the measurement may hold dimensions and the parameter may
        # not, so the change reaches some declarations and not others - which `ddd gui` refuses
        # rather than applying by halves (see `ddd.lsp.edits.settle`).
        api = opened(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed", dimensions=[4])),
                "b.ddd.json": component("B", declare("input", "Speed", kind="parameter")),
            },
        )
        before = contents(tmp_path)
        reply = get(api, "/api/settle", name="Speed", key="dimensions", raw="[8]")
        assert (reply.status, reply.body["error"]) == (409, "invalid")
        assert "b.ddd.json" in reply.body["message"]
        assert contents(tmp_path) == before
```

If `tests/test_gui_api.py` has no `opened_example` helper yet, add it beside `opened`:

```python
def opened_example(tmp_path: Path, example: str, description: str) -> Api:
    """`ddd gui` over a copy of one of the shipped examples, so the test may edit it."""
    shutil.copytree(EXAMPLES / example, tmp_path / example)
    session = Session(tmp_path / example)
    session.open(tmp_path / example / description)
    return Api(session, tmp_path / example / description, wait_seconds=0.05)
```

- [ ] **Step 2: Run them to watch them fail**

Run: `python -m pytest tests/test_gui_api.py -k Variable -v`
Expected: FAIL - `KeyError: 'keys'`.

- [ ] **Step 3: Declare the three models**

In `src/ddd/gui/contract.py`, under the `GET /api/variable` heading and before `VariableReply`:

```python
class VariableKeyCarried(_Frozen):
    """What one declaration's kind does with a key."""

    allowed: bool
    """Its kind has the key at all: ``dimensions`` on a measurement, never on a parameter."""

    required: bool
    """It cannot be left without it, so the panel offers no "state nothing" for the key."""

class VariableKeyValue(_Frozen):
    """One value a key has among the declarations, and who has it."""

    raw: str
    """The json text, as the file that carries it spells it.

    One entry per value rather than per spelling: two files writing one conversion with its keys
    in a different order state the same conversion, and this is the producer's spelling of it.
    """

    components: tuple[str, ...]
    """The components stating it, in the order the project lists them."""

    producer: bool
    """The producer is one of them; the panel marks that entry."""

class VariableKeyOffer(_Frozen):
    """What one key of a variable offers: a row of the panel, and the chooser the row opens."""

    key: str
    """One of the twelve keys every declaration of an object has to agree on."""

    carried: tuple[VariableKeyCarried, ...]
    """One per declaration, aligned with ``VariableReply.declarations``."""

    values: tuple[VariableKeyValue, ...]
    """Every distinct value in play, the producer's first."""

    editor: Literal["unit", "datatype", "typename", "volatile", "limits", "size", "name", "none"]
    """Which field the page offers beside the values in play.

    ``none`` is not "nothing may be chosen": a value in play is always offered, and for a
    ``conversion`` or a ``dimensions`` that is all - an editor composes those better than a
    panel would.
    """

    choices: tuple[str, ...]
    """What that field names, sorted: the datatypes, the project's types, its declared constants
    or its objects of the kind the key takes. Empty for a field that names nothing."""
```

and add the field to `VariableReply`, after `declarations`:

```python
    keys: tuple[VariableKeyOffer, ...]
    """What every shared key offers for these declarations, in the order a definition spells
    them (``ddd.variable_keys.KEY_ORDER``). The page groups the rows it draws; the order here
    is what it keeps inside each group."""
```

- [ ] **Step 4: Answer them**

In `src/ddd/gui/api.py`: add `from dataclasses import asdict` beside the existing `dataclass` import, and `from ddd.variable_keys import offers`. Replace the body of `_variable` down to `declared`:

```python
    def _variable(self, query: Query, body: bytes | None) -> Reply:
        revision = self._opened()
        name = _single(query.get("name"))
        if not name:
            return _error(400, "bad-request", "variable takes ?name=")
        built = revision.index
        declared = () if built is None else declarations_of(built, name, {})
        if built is None or not declared:
            return _undeclared(revision, name)
```

and add the field to the `contract.VariableReply(...)` it answers with, after `declarations=[...]`:

```python
                # The dataclasses of `ddd.variable_keys` are the contract's models field for
                # field; the contract validates what comes out, so a name that drifts apart
                # fails here rather than reaching the page.
                keys=[asdict(offer) for offer in offers(built, declared)],
```

Delete `_declared`, which had this one caller.

- [ ] **Step 5: Run the tests to watch them pass**

Run: `python -m pytest tests/test_gui_api.py tests/test_gui_contract.py -v`
Expected: PASS. `tests/test_gui_contract.py::TestApiSchema::test_every_model_declared_here_has_a_defs_entry` covers the three new models reaching the generated schema.

- [ ] **Step 6: Run the Python gate**

Run: `python -m pytest && ruff check . && ruff format --check . && mypy`
Expected: all green at 100 %.

- [ ] **Step 7: Regenerate the page's types and re-export them**

```bash
cd gui && npm run schemas
```

Add `VariableKeyCarried`, `VariableKeyOffer` and `VariableKeyValue` to the sorted `export type { ... }` list of `gui/src/api/types.ts`.

`VariableReply` now has a field the stories' fixtures do not: give each `VariableReply` literal in `gui/src/stories/fixtures.ts` an empty `keys: [],` for now - Task 5 fills them with what each story is about. Then:

```bash
cd gui && npm run lint && npm run typecheck && npm test && npm run build
```

Expected: all green. (`gui/src/generated/` is git-ignored; only `types.ts` is committed.)

- [ ] **Step 8: Commit**

```bash
git add src/ddd/gui/contract.py src/ddd/gui/api.py tests/test_gui_api.py gui/src/api/types.ts
git commit -m "answer what every key of a variable offers

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: The page's logic

Everything the panel decides, as pure functions over the answer: which rows the table has and in which order, what each cell reads, what a key's chooser lists, and the json text a choice travels as. Under Vitest's 100 % gate, with no React in sight.

**Files:**
- Create: `gui/src/lib/variableKeys.ts`, `gui/src/lib/variableKeys.test.ts`
- Modify: `gui/src/lib/units.ts` (nothing removed yet; `textOf`, `consequence`, `baseName`, `editOf`, `pickerSections`, `rawOf` and `outsideVocabulary` are imported as they are)

**Interfaces:**
- Consumes: `VariableReply`, `VariableKeyOffer`, `VariableDeclaration`, `SettleReply` from `../api/types` (Task 3); `textOf` from `./units`.
- Produces: the exported names below, which Tasks 5 and 6 draw.

- [ ] **Step 1: Write the failing tests**

Create `gui/src/lib/variableKeys.test.ts`. The fixtures it builds are plain object literals of the
answer's shape - a `VariableReply` with `keys` - so the file starts with two small builders:

```ts
import { describe, expect, test } from "vitest";
import type { SettleReply, VariableKeyOffer, VariableReply } from "../api/types";
import {
  chooserSections,
  describeVariable,
  enteredValue,
  keyRows,
  labelOfRaw,
  limitsOf,
  limitsRaw,
  offerOf,
  shortValue,
  startingRaw,
  willChangeKey,
} from "./variableKeys";

const SENSOR_HUB = "C:/work/demo/components/sensor_hub.ddd.json";
const CONTROLLER = "C:/work/demo/components/controller.ddd.json";

/** One key's offer, with everything it does not say left at its emptiest. */
function offer(key: string, fields: Partial<VariableKeyOffer> = {}): VariableKeyOffer {
  return {
    key,
    carried: [
      { allowed: true, required: false },
      { allowed: true, required: false },
    ],
    values: [],
    disagrees: false,
    editor: "none",
    choices: [],
    ...fields,
  };
}

/** ValueA produced by SensorHub and read by Controller, with the offers a test cares about. */
function variable(keys: VariableKeyOffer[], stated: Record<string, string>[] = []): VariableReply {
  return {
    revision: 7,
    name: "ValueA",
    declarations: [
      {
        path: SENSOR_HUB,
        pointer: "component.interface[2].definition",
        component: "SensorHub",
        role: "produces",
        stated: { kind: '"measurement"', ...stated[0] },
        type: null,
        fixed: {},
      },
      {
        path: CONTROLLER,
        pointer: "component.interface[0].definition",
        component: "Controller",
        role: "reads",
        stated: { kind: '"measurement"', ...stated[1] },
        type: null,
        fixed: {},
      },
    ],
    keys,
    findings: [],
  };
}

describe("the rows of the table", () => {
  test("kind comes first and opens nothing", () => {
    const rows = keyRows(variable([offer("unit")]), null);
    expect(rows[0]).toMatchObject({ key: "kind", disagrees: false, settleable: false });
    expect(rows[0].cells.map((cell) => cell.text)).toEqual(["measurement", "measurement"]);
  });

  test("declarations of two kinds are a row that says so", () => {
    const of = variable([offer("unit")], [{}, { kind: '"parameter"' }]);
    expect(keyRows(of, null)[0].disagrees).toBe(true);
  });

  test("what disagrees comes first, then what is stated, then the rest", () => {
    const rows = keyRows(
      variable([
        offer("datatype", { values: [value('"uint8"', ["SensorHub", "Controller"], true)] }),
        offer("unit", { disagrees: true, values: [value('"%"', ["SensorHub"], true)] }),
        offer("limits"),
        offer("volatile", { values: [value("false", ["SensorHub", "Controller"], true)] }),
      ]),
      null,
    );
    expect(rows.map((row) => row.key)).toEqual([
      "kind",
      "unit",
      "datatype",
      "volatile",
      "limits",
    ]);
  });

  test("a key no declaration's kind holds is not a row at all", () => {
    const rows = keyRows(
      variable([
        offer("size", {
          carried: [
            { allowed: false, required: false },
            { allowed: false, required: false },
          ],
        }),
      ]),
      null,
    );
    expect(rows.map((row) => row.key)).toEqual(["kind"]);
  });

  test("a cell whose kind cannot hold the key says so rather than sitting empty", () => {
    const rows = keyRows(
      variable([
        offer("dimensions", {
          carried: [
            { allowed: true, required: false },
            { allowed: false, required: false },
          ],
          values: [value("[4]", ["SensorHub"], true)],
        }),
      ]),
      null,
    );
    expect(rows[1].cells[1]).toMatchObject({ text: "not on a parameter", quiet: true });
  });

  test("a cell of a declaration stating nothing reads none", () => {
    const rows = keyRows(variable([offer("unit", { values: [value('"%"', ["SensorHub"], true)] })]), null);
    expect(rows[1].cells.map((cell) => [cell.text, cell.quiet])).toEqual([
      ["%", false],
      ["none", true],
    ]);
  });

  test("a value a type fixes names the type", () => {
    const of = variable([offer("unit", { values: [value('"rpm"', ["SensorHub"], true)] })]);
    of.declarations[0] = { ...of.declarations[0], type: "Speed_t", fixed: { unit: '"rpm"' } };
    expect(keyRows(of, null)[1].cells[0]).toMatchObject({ text: "rpm", from: "Speed_t" });
  });

  test("the declarations a preview writes into are marked on that key's row alone", () => {
    const preview: SettleReply = {
      revision: 7,
      changes: [
        {
          file: CONTROLLER,
          fingerprint: "abc",
          operations: [
            { op: "set", pointer: "component.interface[0].definition.unit", value: '"%"' },
          ],
          hunks: [],
        },
      ],
    };
    const rows = keyRows(variable([offer("unit"), offer("datatype")]), preview);
    expect(rows.find((row) => row.key === "unit")?.cells.map((cell) => cell.changing)).toEqual([
      false,
      true,
    ]);
    expect(rows.find((row) => row.key === "datatype")?.cells.map((cell) => cell.changing)).toEqual([
      false,
      false,
    ]);
  });
});

describe("a value as a reader reads it", () => {
  test.each([
    ["unit", '"%"', "%"],
    ["volatile", "true", "true"],
    ["size", "4", "4"],
    ["size", '"CELLS"', "CELLS"],
    ["dimensions", "[3, 4]", "3 × 4"],
    ["limits", '{ "min": 0, "max": 100 }', "0 … 100"],
    ["conversion", '{ "kind": "identity" }', "identity"],
    ["conversion", "{}", "identity"],
    ["conversion", '{ "factor": 0.5 }', "linear ×0.5"],
    ["conversion", '{ "kind": "linear", "factor": 0.5, "offset": 2 }', "linear ×0.5 +2"],
    ["conversion", '{ "kind": "linear", "factor": 1, "offset": -2 }', "linear ×1 -2"],
    ["conversion", '{ "name": "Gear_e", "enumerators": [] }', "enum Gear_e"],
    ["conversion", '{ "enumerators": [{ "name": "OFF", "value": 0 }] }', "enum, 1 enumerator"],
    ["conversion", '{ "kind": "string" }', "string"],
    ["unit", "{", "{"],
  ])("%s %s reads %s", (key, raw, reads) => {
    expect(shortValue(key, raw)).toBe(reads);
  });
});

describe("the panel's line under the name", () => {
  test("it says what the variable is, who owns it and what disagrees", () => {
    const of = variable(
      [offer("unit", { disagrees: true }), offer("datatype", { disagrees: true })],
      [{ datatype: '"uint8"' }, {}],
    );
    expect(describeVariable(of)).toBe(
      "measurement · uint8 · produced by SensorHub · 2 declarations · 2 keys disagree",
    );
  });

  test("one disagreement is one key, and none is said plainly", () => {
    const one = variable([offer("unit", { disagrees: true })], [{ datatype: '"uint8"' }]);
    expect(describeVariable(one)).toContain("1 key disagrees");
    const agreed = variable([offer("unit")], [{ datatype: '"uint8"' }]);
    expect(describeVariable(agreed)).toContain("2 declarations · all agreed");
  });
});

describe("what a key's chooser lists", () => {
  test("the values in play come first, the producer's marked", () => {
    const sections = chooserSections(
      variable([
        offer("unit", {
          editor: "unit",
          values: [value('"%"', ["SensorHub"], true), value('"rpm"', ["Controller"], false)],
        }),
      ]),
      "unit",
      "",
    );
    expect(sections[0].title).toBe("Declared for ValueA");
    expect(sections[0].choices.map((choice) => [choice.label, choice.detail])).toEqual([
      ["%", "SensorHub · the producer"],
      ["rpm", "Controller"],
    ]);
  });

  test("state nothing is offered unless a declaration requires the key", () => {
    const optional = chooserSections(variable([offer("unit", { editor: "unit" })]), "unit", "");
    expect(optional.some((section) => section.id === "nothing")).toBe(true);
    const required = chooserSections(
      variable([
        offer("volatile", {
          editor: "volatile",
          carried: [
            { allowed: true, required: true },
            { allowed: true, required: true },
          ],
        }),
      ]),
      "volatile",
      "",
    );
    expect(required.some((section) => section.id === "nothing")).toBe(false);
  });

  test("an editor that names things lists what the project has, what is in play left out", () => {
    const sections = chooserSections(
      variable([
        offer("axis", {
          editor: "name",
          choices: ["AxisA", "AxisB"],
          values: [value('"AxisA"', ["SensorHub"], true)],
        }),
      ]),
      "axis",
      "",
    );
    expect(sections.map((section) => [section.title, section.choices.map((c) => c.label)])).toEqual(
      [
        ["Declared for ValueA", ["AxisA"]],
        ["This project's axes", ["AxisB"]],
        ["State nothing", ["state nothing"]],
      ],
    );
  });

  test("each naming editor says what it is naming", () => {
    const titles = (key: string, editor: VariableKeyOffer["editor"], choices: string[]) =>
      chooserSections(variable([offer(key, { editor, choices })]), key, "").map((s) => s.title);
    expect(titles("input", "name", ["ValueE"])[1]).toBe("This project's measurements");
    expect(titles("typename", "typename", ["Speed_t"])[1]).toBe("This project's types");
    expect(titles("datatype", "datatype", ["uint8"])[1]).toBe("Datatypes");
    expect(titles("size", "size", ["CELLS"])[1]).toBe("This project's constants");
    expect(titles("volatile", "volatile", [])[1]).toBe("True or false");
  });

  test("a conversion offers what is in play and nothing else", () => {
    const sections = chooserSections(
      variable([offer("conversion", { values: [value("{}", ["SensorHub"], true)] })]),
      "conversion",
      "",
    );
    expect(sections.map((section) => section.id)).toEqual(["declared", "nothing"]);
  });

  test("what is typed narrows the list, and a size may be typed outright", () => {
    const narrowed = chooserSections(
      variable([offer("size", { editor: "size", choices: ["CELLS", "ROWS"] })]),
      "size",
      "RO",
    );
    expect(narrowed.flatMap((section) => section.choices.map((c) => c.label))).toEqual(["ROWS"]);
    const typed = chooserSections(
      variable([offer("size", { editor: "size", choices: ["CELLS"] })]),
      "size",
      "12",
    );
    expect(typed[typed.length - 1]).toMatchObject({ id: "typed" });
    expect(typed[typed.length - 1].choices[0].raw).toBe("12");
  });

  test("a name that is no name of this project is not offered as typed", () => {
    const sections = chooserSections(
      variable([offer("axis", { editor: "name", choices: ["AxisA"] })]),
      "axis",
      "Wheel",
    );
    expect(sections.some((section) => section.id === "typed")).toBe(false);
  });
});

describe("what a field's text chooses", () => {
  test("an entry spelling the text exactly", () => {
    const of = variable([offer("datatype", { editor: "datatype", choices: ["uint8", "uint16"] })]);
    expect(enteredValue(chooserSections(of, "datatype", "uint16"), "datatype", "uint16")).toBe(
      '"uint16"',
    );
  });

  test("state nothing, by the label the list gives it", () => {
    const of = variable([offer("unit", { editor: "unit" })]);
    expect(enteredValue(chooserSections(of, "unit", ""), "unit", "state nothing")).toBeNull();
  });

  test("a whole number for a size, and nothing at all for a field left empty", () => {
    const of = variable([offer("size", { editor: "size", choices: [] })]);
    expect(enteredValue(chooserSections(of, "size", "12"), "size", "12")).toBe("12");
    expect(enteredValue(chooserSections(of, "size", " "), "size", " ")).toBeUndefined();
  });

  test("a name this project does not declare chooses nothing", () => {
    const of = variable([offer("axis", { editor: "name", choices: ["AxisA"] })]);
    expect(enteredValue(chooserSections(of, "axis", "Wheel"), "axis", "Wheel")).toBeUndefined();
  });
});

describe("the value a chooser starts on", () => {
  test("the producer's, which is the first in play", () => {
    const of = variable([
      offer("unit", { values: [value('"%"', ["SensorHub"], true), value('"rpm"', ["Controller"], false)] }),
    ]);
    expect(startingRaw(of, "unit")).toBe('"%"');
    expect(labelOfRaw(of, "unit", startingRaw(of, "unit"))).toBe("%");
  });

  test("nothing in play starts on nothing, which the field says in words", () => {
    const of = variable([offer("unit")]);
    expect(startingRaw(of, "unit")).toBeNull();
    expect(labelOfRaw(of, "unit", null)).toBe("state nothing");
  });

  test("a key the answer does not carry offers nothing", () => {
    expect(offerOf(variable([offer("unit")]), "nonsense")).toBeUndefined();
    expect(startingRaw(variable([offer("unit")]), "nonsense")).toBeNull();
  });
});

describe("a range typed into two fields", () => {
  test("it travels as one object, and an empty field is no range at all", () => {
    expect(limitsRaw("0", "100")).toBe('{ "min": 0, "max": 100 }');
    expect(limitsRaw("-2.5", "2.5")).toBe('{ "min": -2.5, "max": 2.5 }');
    expect(limitsRaw("", "100")).toBeNull();
    expect(limitsRaw("low", "100")).toBeNull();
  });

  test("the fields read what is stated, and nothing where nothing is", () => {
    expect(limitsOf('{ "min": 0, "max": 100 }')).toEqual({ min: "0", max: "100" });
    expect(limitsOf(null)).toEqual({ min: "", max: "" });
    expect(limitsOf("{")).toEqual({ min: "", max: "" });
  });
});
```

The `value` helper the fixtures use goes beside `offer`:

```ts
function value(raw: string, components: string[], producer: boolean) {
  return { raw, components, producer };
}
```

- [ ] **Step 2: Run them to watch them fail**

Run: `cd gui && npm test -- variableKeys`
Expected: FAIL - `Failed to resolve import "./variableKeys"`.

- [ ] **Step 3: Write the module**

Create `gui/src/lib/variableKeys.ts`:

```ts
import type {
  SettleReply,
  VariableDeclaration,
  VariableKeyOffer,
  VariableReply,
} from "../api/types";
import { textOf } from "./units";

/** What one declaration's cell of a row reads. */
export interface KeyCell {
  /** The value as a reader reads it, `none` where nothing is stated, or why there is no cell. */
  text: string;
  /** Drawn quiet: nothing is stated here, or this kind has no such key. */
  quiet: boolean;
  /** The declared type the value comes from, which the cell names after it. */
  from: string | null;
  /** The preview writes this key into this declaration. */
  changing: boolean;
}

/** One row of the panel's table: a key, and what each declaration says about it. */
export interface KeyRow {
  key: string;
  cells: KeyCell[];
  disagrees: boolean;
  /** Selecting it opens a chooser. `kind` never does. */
  settleable: boolean;
}

/** One value a chooser offers: the json text it settles on, or `null` for "state nothing". */
export interface ValueChoice {
  /** Unique across the whole list: its section, then the value. */
  id: string;
  raw: string | null;
  label: string;
  detail: string;
}

export interface ValueSection {
  id: "declared" | "project" | "nothing" | "typed";
  title: string;
  choices: ValueChoice[];
}

const NOTHING = "state nothing";

/** What each naming editor is naming, for the title of its section and for nothing else. */
const NAMED: Record<string, string> = {
  datatype: "Datatypes",
  typename: "This project's types",
  size: "This project's constants",
  volatile: "True or false",
  axis: "This project's axes",
  x_axis: "This project's axes",
  y_axis: "This project's axes",
  input: "This project's measurements",
};

/** The rows of the panel's table: `kind`, then what disagrees, then what is stated, then the
 * keys this variable's kinds allow and nobody states.
 *
 * A key no declaration's kind holds at all is not a row: an axis has no `x_axis`, and a reader
 * looking at one learns nothing from a line of "not on an axis".
 */
export function keyRows(variable: VariableReply, preview: SettleReply | null): KeyRow[] {
  const kinds = variable.declarations.map((declaration) => declaration.stated.kind);
  const kind: KeyRow = {
    key: "kind",
    cells: variable.declarations.map((declaration) => ({
      text: textOf(declaration.stated.kind) ?? "none",
      quiet: textOf(declaration.stated.kind) === null,
      from: null,
      changing: false,
    })),
    disagrees: new Set(kinds).size > 1,
    settleable: false,
  };
  const rows = variable.keys
    .filter((offer) => offer.carried.some((carried) => carried.allowed))
    .map((offer) => rowOf(variable, offer, preview));
  // Stable, so the answer's own order - the order a definition spells its keys - survives
  // inside each of the three groups.
  return [kind, ...rows.sort((one, other) => group(one) - group(other))];
}

/** Which of the three groups a row belongs to. */
function group(row: KeyRow): number {
  if (row.disagrees) return 0;
  return row.cells.some((cell) => !cell.quiet) ? 1 : 2;
}

function rowOf(
  variable: VariableReply,
  offer: VariableKeyOffer,
  preview: SettleReply | null,
): KeyRow {
  return {
    key: offer.key,
    cells: variable.declarations.map((declaration, at) =>
      cellOf(declaration, offer, at, preview),
    ),
    disagrees: offer.disagrees,
    settleable: true,
  };
}

function cellOf(
  declaration: VariableDeclaration,
  offer: VariableKeyOffer,
  at: number,
  preview: SettleReply | null,
): KeyCell {
  const changing = preview !== null && willChangeKey(preview, declaration, offer.key);
  if (!offer.carried[at].allowed) {
    return {
      text: `not on a ${textOf(declaration.stated.kind) ?? "declaration"}`,
      quiet: true,
      from: null,
      changing,
    };
  }
  const stated = declaration.stated[offer.key];
  const fixed = declaration.fixed[offer.key];
  const raw = stated ?? fixed;
  if (raw === undefined) return { text: "none", quiet: true, from: null, changing };
  return {
    text: shortValue(offer.key, raw),
    quiet: false,
    from: stated === undefined ? declaration.type : null,
    changing,
  };
}

/** Whether a preview writes this key into this declaration. */
export function willChangeKey(
  preview: SettleReply,
  declaration: VariableDeclaration,
  key: string,
): boolean {
  return preview.changes.some(
    (change) =>
      change.file === declaration.path &&
      change.operations.some(
        (operation) => operation.pointer === `${declaration.pointer}.${key}`,
      ),
  );
}

/** A value as a reader reads it: short, and in the words the description files use.
 *
 * The json text is what the file says, layout and all; a table of twelve rows has no room for
 * four lines of conversion, and a reader comparing two declarations wants to see at a glance
 * which of them is the odd one.
 */
export function shortValue(key: string, raw: string): string {
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    // Not json at all: the file says it, so the table does too.
    return raw;
  }
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) return value.map((entry) => String(entry)).join(" × ");
  if (value === null || typeof value !== "object") return raw;
  const fields = value as Record<string, unknown>;
  if (key === "limits") return `${format(fields.min)} … ${format(fields.max)}`;
  if (key === "conversion") return conversion(fields);
  return raw.replace(/\s+/g, " ");
}

/** A conversion in one phrase; the kind may be left out where the keys make it plain. */
function conversion(fields: Record<string, unknown>): string {
  const kind =
    fields.kind ??
    (fields.factor !== undefined || fields.offset !== undefined
      ? "linear"
      : fields.enumerators !== undefined || fields.name !== undefined
        ? "enum"
        : "identity");
  if (kind === "linear") {
    const factor = `×${format(fields.factor ?? 1)}`;
    const offset = fields.offset === undefined || fields.offset === 0 ? "" : ` ${signed(fields.offset)}`;
    return `linear ${factor}${offset}`;
  }
  if (kind === "enum") {
    if (typeof fields.name === "string") return `enum ${fields.name}`;
    const listed = Array.isArray(fields.enumerators) ? fields.enumerators.length : 0;
    return `enum, ${listed} enumerator${listed === 1 ? "" : "s"}`;
  }
  return String(kind);
}

function signed(value: unknown): string {
  return typeof value === "number" && value > 0 ? `+${value}` : format(value);
}

function format(value: unknown): string {
  return value === undefined ? "?" : String(value);
}

/** The panel's line under the variable's name. */
export function describeVariable(variable: VariableReply): string {
  const first = owner(variable.declarations);
  if (first === undefined) return "";
  const kind = textOf(first.stated.kind) ?? "declaration";
  const datatype = first.type ?? textOf(first.stated.datatype) ?? "no datatype";
  const who =
    first.role === "produces"
      ? `produced by ${first.component}`
      : first.role === "local"
        ? `local to ${first.component}`
        : "no producer";
  const declarations = `${variable.declarations.length} declaration${
    variable.declarations.length === 1 ? "" : "s"
  }`;
  const disagreeing = variable.keys.filter((offer) => offer.disagrees).length;
  const state =
    disagreeing === 0 ? "all agreed" : `${disagreeing} key${disagreeing === 1 ? "" : "s"} disagree${disagreeing === 1 ? "s" : ""}`;
  return `${kind} · ${datatype} · ${who} · ${declarations} · ${state}`;
}

/** Who the variable belongs to: its producer, else the first declaration listed. */
function owner(declarations: readonly VariableDeclaration[]): VariableDeclaration | undefined {
  return declarations.find((entry) => entry.role === "produces") ?? declarations[0];
}

/** What the answer says about one key, or `undefined` for a key it does not carry. */
export function offerOf(variable: VariableReply, key: string): VariableKeyOffer | undefined {
  return variable.keys.find((offer) => offer.key === key);
}

/** The json text the chooser starts on: the producer's value, which the answer lists first. */
export function startingRaw(variable: VariableReply, key: string): string | null {
  return offerOf(variable, key)?.values[0]?.raw ?? null;
}

/** What the field reads for a value while nothing is being typed. */
export function labelOfRaw(variable: VariableReply, key: string, raw: string | null): string {
  return raw === null ? NOTHING : shortValue(key, raw);
}

/** Every section a key's chooser lists, narrowed to what was typed (spec 5.2). */
export function chooserSections(
  variable: VariableReply,
  key: string,
  typed: string,
): ValueSection[] {
  const offer = offerOf(variable, key);
  if (offer === undefined) return [];
  const inPlay = offer.values.map((value) =>
    choice("declared", key, value.raw, who(value.components, value.producer)),
  );
  const listed: ValueSection[] = [
    { id: "declared", title: `Declared for ${variable.name}`, choices: inPlay },
    {
      id: "project",
      title: NAMED[offer.editor === "name" ? key : offer.editor] ?? "",
      choices: projectChoices(offer, key).filter(
        (entry) => !inPlay.some((had) => had.raw === entry.raw),
      ),
    },
  ];
  if (!offer.carried.some((carried) => carried.required)) {
    listed.push({
      id: "nothing",
      title: "State nothing",
      choices: [{ id: "nothing:", raw: null, label: NOTHING, detail: "" }],
    });
  }
  const wanted = typed.toLowerCase();
  const sections = listed
    .map((section) => ({
      ...section,
      choices: section.choices.filter((entry) => entry.label.toLowerCase().includes(wanted)),
    }))
    .filter((section) => section.choices.length > 0);
  const exact = sections.some((section) =>
    section.choices.some((entry) => entry.label === typed),
  );
  const asTyped = typedRaw(key, typed);
  if (!exact && asTyped !== null) {
    sections.push({
      id: "typed",
      title: "As typed",
      choices: [{ id: `typed:${typed}`, raw: asTyped, label: typed, detail: "" }],
    });
  }
  return sections;
}

/** What the project itself offers for the key, beside what is already in play. */
function projectChoices(offer: VariableKeyOffer, key: string): ValueChoice[] {
  if (offer.editor === "volatile") {
    return ["true", "false"].map((raw) => choice("project", key, raw, ""));
  }
  return offer.choices.map((name) => choice("project", key, JSON.stringify(name), ""));
}

function choice(
  section: ValueSection["id"],
  key: string,
  raw: string,
  detail: string,
): ValueChoice {
  return { id: `${section}:${raw}`, raw, label: shortValue(key, raw), detail };
}

function who(components: readonly string[], producer: boolean): string {
  const listed = components.join(", ");
  return producer ? `${listed} · the producer` : listed;
}

/** The json text a text typed into the field travels as, or `null` when the key takes none.
 *
 * A size may be any whole number, so one typed is taken as it stands. Everything else names
 * something the project declares, and a name it does not declare is not offered: the list is
 * the answer to "what may this be", and a typed one would be a reference to nothing.
 */
function typedRaw(key: string, typed: string): string | null {
  return key === "size" && /^[1-9][0-9]*$/.test(typed) ? typed : null;
}

/**
 * What Enter chooses from the text in the field: the value of an entry whose label spells it
 * exactly, else what the text itself may be taken as, else nothing at all (`undefined`), which
 * leaves the chooser as it was.
 */
export function enteredValue(
  sections: readonly ValueSection[],
  key: string,
  text: string,
): string | null | undefined {
  if (text.trim() === "") return undefined;
  for (const section of sections) {
    for (const entry of section.choices) {
      if (entry.label === text) return entry.raw;
    }
  }
  return typedRaw(key, text) ?? undefined;
}

/** The two fields of a range, read from what is stated. */
export function limitsOf(raw: string | null): { min: string; max: string } {
  if (raw === null) return { min: "", max: "" };
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    return { min: "", max: "" };
  }
  const fields = (value ?? {}) as Record<string, unknown>;
  return { min: numberText(fields.min), max: numberText(fields.max) };
}

function numberText(value: unknown): string {
  return typeof value === "number" ? String(value) : "";
}

/** The json text a range typed into the two fields travels as; `null` while it is not one. */
export function limitsRaw(min: string, max: string): string | null {
  const low = Number(min);
  const high = Number(max);
  if (min.trim() === "" || max.trim() === "" || Number.isNaN(low) || Number.isNaN(high)) {
    return null;
  }
  return `{ "min": ${low}, "max": ${high} }`;
}
```

- [ ] **Step 4: Run the tests to watch them pass**

Run: `cd gui && npm test -- variableKeys`
Expected: PASS.

- [ ] **Step 5: Run the page's gate**

Run: `cd gui && npm run lint && npm run typecheck && npm test && npm run build`
Expected: green, `src/lib/variableKeys.ts` at 100 % statements, branches, functions and lines. A branch no test reaches is a test missing.

- [ ] **Step 6: Commit**

```bash
git add gui/src/lib/variableKeys.ts gui/src/lib/variableKeys.test.ts
git commit -m "work out the panel's rows, cells and choosers from the answer

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: The two new pictures, and their stories

The table of keys and the chooser a row opens, each a picture of its props, each with its own stories and screenshot references. Part 1's panel is not touched yet: it still draws its one unit column, and the page stays green.

**Files:**
- Create: `gui/src/components/VariableKeysTable.tsx`, `VariableKeysTable.stories.tsx`, `KeyChooser.tsx`, `KeyChooser.stories.tsx`
- Modify: `gui/src/stories/fixtures.ts` (the fixtures the new stories draw), `gui/src/styles/ui.css`
- Create: `gui/screenshots/references/*.png` for the new stories

**Interfaces:**
- Consumes: `keyRows`, `chooserSections`, `enteredValue`, `offerOf` (Task 4); `pickerSections` and `rawOf` from `lib/units.ts`; `ComboBox`, `Table`, `UnitPicker` from the existing kit.
- Produces: `VariableKeysTable` and `KeyChooser` with the props the Interfaces section at the top spells - which Task 6 composes into the panel.

- [ ] **Step 1: The table**

Create `gui/src/components/VariableKeysTable.tsx`:

```tsx
import type { SettleReply, VariableReply } from "../api/types";
import { keyRows } from "../lib/variableKeys";
import { Cell, Column, Row, Table, TableBody, TableHeader } from "../ui/Table";

export interface VariableKeysTableProps {
  variable: VariableReply;
  preview: SettleReply | null;
  /** The key whose chooser is open, or `undefined`. */
  selected: string | undefined;
  /** A row selected, or the selected one let go. `kind` is never selected. */
  onSelect: (key: string | undefined) => void;
}

/** The panel's table (spec 5.1): a row per key, a column per declaration, drawn from what the
 * api answered. A picture of its props. */
export function VariableKeysTable({
  variable,
  preview,
  selected,
  onSelect,
}: VariableKeysTableProps) {
  const rows = keyRows(variable, preview);
  const columns = [
    { id: "key", name: "Key", at: -1 },
    ...variable.declarations.map((declaration, at) => ({
      id: `${declaration.path} ${declaration.pointer}`,
      name: declaration.component,
      at,
    })),
  ];
  return (
    <Table
      aria-label={`Keys of ${variable.name}`}
      selectionMode="single"
      selectedKeys={new Set(selected === undefined ? [] : [selected])}
      onSelectionChange={(keys) => {
        const key = keys === "all" ? undefined : [...keys][0];
        const row = rows.find((entry) => entry.key === key);
        // `kind` decides which other keys a declaration may carry at all, so it is shown and
        // never settled (spec 2): selecting it opens nothing and lets the open one go.
        onSelect(row?.settleable === true ? row.key : undefined);
      }}
    >
      <TableHeader columns={columns}>
        {(column) => <Column isRowHeader={column.id === "key"}>{column.name}</Column>}
      </TableHeader>
      <TableBody items={rows}>
        {(row) => (
          <Row id={row.key} columns={columns} className={also(row.disagrees ? "has-error" : "")}>
            {(column) => {
              if (column.at < 0) return <Cell className={also("key")}>{row.key}</Cell>;
              const cell = row.cells[column.at];
              return (
                <Cell className={also(cell.quiet ? "quiet" : "")}>
                  {cell.text}
                  {cell.from !== null && <span className="quiet">, from {cell.from}</span>}
                  {cell.changing && <span className="tag">will change</span>}
                </Cell>
              );
            }}
          </Row>
        )}
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

- [ ] **Step 2: The chooser**

Create `gui/src/components/KeyChooser.tsx`:

```tsx
import type { UnitsReply, VariableReply } from "../api/types";
import { pickerSections, rawOf } from "../lib/units";
import { chooserSections, enteredValue, offerOf } from "../lib/variableKeys";
import { ComboBox } from "../ui/ComboBox";
import { UnitPicker } from "./UnitPicker";

export interface KeyChooserProps {
  variable: VariableReply;
  /** Which key is being settled. */
  keyName: string;
  units: UnitsReply;
  /** The json text settled on, or `null` for "state nothing". */
  chosen: string | null;
  /** What the field reads: what is being typed, else the value settled on. */
  typed: string;
  /** What narrows the list: "" unless the reader is typing (part 1's rule, spec 5.3). */
  narrow: string;
  onTyped: (text: string) => void;
  onChosen: (raw: string | null) => void;
  /** The list closed or the field was left: what was typed there is dropped. */
  onPickerClosed: () => void;
  /** The two fields of a range, while the key is `limits`. */
  range: { min: string; max: string };
  onRange: (range: { min: string; max: string }) => void;
  note: string | undefined;
  busy: boolean;
  /** A new value on every request to focus the field; `null` asks for no focus. */
  focus: number | null;
  /** "focus" opens the list as the field takes the focus, for a story to photograph it open. */
  pickerTrigger?: "input" | "focus" | undefined;
}

/** One key's chooser (spec 5.2): the values in play, state nothing, and the field the key takes.
 * A picture of its props. */
export function KeyChooser(props: KeyChooserProps) {
  const { variable, keyName, units } = props;
  const offer = offerOf(variable, keyName);
  if (offer === undefined) return null;
  if (offer.editor === "unit") {
    return (
      <UnitPicker
        label={`Unit of ${variable.name}`}
        sections={pickerSections(variable.name, variable.declarations, units, props.narrow)}
        typed={props.typed}
        onTyped={props.onTyped}
        onPick={(unit) => props.onChosen(rawOf(unit))}
        onClose={props.onPickerClosed}
        note={props.note}
        isDisabled={props.busy}
        autoFocus={props.focus}
        menuTrigger={props.pickerTrigger}
      />
    );
  }
  const sections = chooserSections(variable, keyName, props.narrow);
  return (
    <div className="key-chooser">
      <ComboBox
        label={`${label(keyName)} of ${variable.name}`}
        inputValue={props.typed}
        onInputChange={props.onTyped}
        sections={sections}
        onPick={(id) => {
          const chosen = sections.flatMap((section) => section.choices).find((e) => e.id === id);
          if (chosen !== undefined) props.onChosen(chosen.raw);
        }}
        onEnter={(text) => {
          const raw = enteredValue(sections, keyName, text);
          if (raw !== undefined) props.onChosen(raw);
        }}
        onClose={props.onPickerClosed}
        note={props.note}
        isDisabled={props.busy}
        autoFocus={props.focus}
        menuTrigger={props.pickerTrigger}
      />
      {offer.editor === "limits" && (
        <div className="key-range">
          <label>
            Min
            <input
              type="text"
              inputMode="decimal"
              value={props.range.min}
              disabled={props.busy}
              onChange={(event) => props.onRange({ ...props.range, min: event.target.value })}
            />
          </label>
          <label>
            Max
            <input
              type="text"
              inputMode="decimal"
              value={props.range.max}
              disabled={props.busy}
              onChange={(event) => props.onRange({ ...props.range, max: event.target.value })}
            />
          </label>
        </div>
      )}
    </div>
  );
}

/** The key as the field's label spells it: `x_axis` reads "X axis". */
function label(key: string): string {
  const words = key.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}
```

Note what the chooser does **not** do: it never decides what a choice means, and it holds no state of its own. `labelOfRaw` and `limitsOf` are the screen's (Task 6), which seeds `typed` and `range` with them; the chooser only draws what it is handed. Nothing else is imported - `npm run lint` fails on an import with no use.

- [ ] **Step 3: The styles**

In `gui/src/styles/ui.css`, beside the existing `.panel-declarations` rules (which go with part 1's table): the key column reads as a name (`.react-aria-Cell.key { font-family: var(--font-mono); }`), a row that disagrees keeps the `has-error` tint the units table already uses, `.key-chooser` stacks its field and its range, and `.key-range` puts the two fields side by side with a short width. Keep the existing tokens; add no colours of your own.

- [ ] **Step 4: The fixtures the new stories draw**

In `gui/src/stories/fixtures.ts`, fill the empty `keys: []` Task 3 left on `DISAGREEING`, `AGREEING` and `FIXED_BY_TYPE` with the offers they are about - a `unit` that disagrees beside a `datatype`, `conversion`, `limits` and `volatile` that agree; the same settled; and, for `FIXED_BY_TYPE`, a `unit` whose one value is the type's - and add three fixtures of its own:

- `SHAPED`: an axis two components declare, with `size`, `input` and a `limits` that disagrees, so a story can photograph a naming chooser and a range;
- `MIXED_KINDS`: a name one component declares as a measurement with `dimensions` and another as a parameter, for the "not on a parameter" cell;
- `PREVIEW_CONVERSION`: a `SettleReply` whose one operation sets `component.interface[0].definition.conversion`, so the changing mark and Show changes have something to draw.

Every literal is of the generated type - `VariableReply`, `VariableKeyOffer`, `SettleReply` - so a field that drifts from the contract fails the type check here.

- [ ] **Step 5: The stories**

`VariableKeysTable.stories.tsx`: `WithDisagreement` (`DISAGREEING`, the `unit` row selected), `NothingSelected` (nothing selected, no preview), `MixedKinds` (`MIXED_KINDS`, the `dimensions` row selected). Each holds its own selection in `useState` and imports nothing from `@ladle/react`.

`KeyChooser.stories.tsx`: `Names` (`SHAPED`, key `input`, list open), `Datatypes` (`DISAGREEING`, key `datatype`, list open), `TrueOrFalse` (key `volatile`, list open), `Range` (`SHAPED`, key `limits`, both fields filled), `InPlayOnly` (key `conversion`, which offers what is in play and nothing else).

- [ ] **Step 6: Run the page's gate**

Run: `cd gui && npm run lint && npm run typecheck && npm test && npm run build && npm run ladle-build`
Expected: green. Part 1's panel and its stories are untouched and still pass.

- [ ] **Step 7: Make the screenshot references, and look at them**

```bash
UPDATE=1 docker compose run --rm gui-screenshots
docker compose run --rm gui-screenshots
```

Open every new reference under `gui/screenshots/references/` and look at it: a chooser that photographed its spinner, a table whose columns collapsed or a range whose fields sit on two lines is a story to fix, not a reference to keep.

- [ ] **Step 8: Commit**

```bash
git add gui/src/components gui/src/stories/fixtures.ts gui/src/styles/ui.css gui/screenshots/references
git commit -m "draw a variable's table of keys and the chooser a key opens

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 6: The panel rebuilt around them

The view composes the table and the chooser; the screen holds which key is open, what is chosen for it, and the apply. They change together: the view's props are what the screen hands it, and neither compiles without the other.

**Files:**
- Modify: `gui/src/components/VariablePanelView.tsx`, `VariablePanelView.stories.tsx`, `gui/src/screens/VariablePanel.tsx`, `gui/src/lib/units.ts`, `gui/src/lib/units.test.ts`, `gui/src/stories/fixtures.ts`
- Modify: `gui/screenshots/references/components--variablepanelview--*.png` (every panel story's reference, remade)

**Interfaces:**
- Consumes: `VariableKeysTable`, `KeyChooser` and `KeyChooserProps` (Task 5); `describeVariable`, `startingRaw`, `labelOfRaw`, `limitsOf`, `limitsRaw` (Task 4); `consequence`, `outsideVocabulary`, `textOf`, `editOf` from `lib/units.ts`; `getVariable`, `getUnits`, `getSettle(name, key, raw)`, `postEdit`, `ApiError`.
- Produces: no change to `VariablePanel`'s own props, so `ComponentPage.tsx` and `GraphPage.tsx` are not touched. `focusPicker` now means "open the unit's row and focus its chooser".

- [ ] **Step 1: The view**

Rewrite `gui/src/components/VariablePanelView.tsx` to compose them:

```tsx
import type { SettleReply, UnitsReply, VariableReply } from "../api/types";
import { distinctFindings, keyedFindings } from "../lib/findings";
import { consequence } from "../lib/units";
import { describeVariable } from "../lib/variableKeys";
import { Button } from "../ui/Button";
import { Chip } from "../ui/Chip";
import { Panel } from "../ui/Panel";
import { Changes } from "./Changes";
import { KeyChooser, type KeyChooserProps } from "./KeyChooser";
import { VariableKeysTable } from "./VariableKeysTable";

export interface VariablePanelViewProps
  extends Omit<KeyChooserProps, "keyName" | "variable" | "units"> {
  variable: VariableReply;
  units: UnitsReply;
  /** The key whose chooser is open, or `undefined` - the panel then shows the table alone. */
  selected: string | undefined;
  onSelect: (key: string | undefined) => void;
  preview: SettleReply | null;
  /** Why the chosen value cannot be applied, or why applying it was refused. */
  refusal: string | null;
  changesShown: boolean;
  onChangesShown: (shown: boolean) => void;
  onApply: () => void;
  onClose: () => void;
}

/** One variable's panel, drawn from what the api answered: a picture of its props. */
export function VariablePanelView(props: VariablePanelViewProps) {
  const { variable, units, preview, refusal, selected } = props;
  const changes = preview?.changes ?? [];
  return (
    <Panel title={variable.name} meta={describeVariable(variable)} onClose={props.onClose}>
      <VariableKeysTable
        variable={variable}
        preview={preview}
        selected={selected}
        onSelect={props.onSelect}
      />
      {variable.findings.length > 0 && (
        <ul className="panel-findings">
          {keyedFindings(distinctFindings(variable.findings)).map(([finding, key]) => (
            <li key={key}>
              <Chip tone={finding.severity === "error" ? "error" : "warning"}>{finding.check}</Chip>{" "}
              <span className="quiet">{finding.message}</span>
            </li>
          ))}
        </ul>
      )}
      {selected === undefined ? (
        <p className="quiet">Select a key to settle it on every declaration.</p>
      ) : (
        <KeyChooser
          variable={variable}
          keyName={selected}
          units={units}
          chosen={props.chosen}
          typed={props.typed}
          narrow={props.narrow}
          onTyped={props.onTyped}
          onChosen={props.onChosen}
          onPickerClosed={props.onPickerClosed}
          range={props.range}
          onRange={props.onRange}
          note={props.note}
          busy={props.busy}
          focus={props.focus}
          pickerTrigger={props.pickerTrigger}
        />
      )}
      {refusal !== null ? (
        <p className="panel-refusal" role="status">
          {refusal}
        </p>
      ) : (
        selected !== undefined && preview !== null && <p className="consequence">{consequence(changes)}</p>
      )}
      {refusal === null && changes.length > 0 && (
        <>
          {props.changesShown && <Changes changes={changes} />}
          <div className="panel-actions">
            <Button variant="link" onPress={() => props.onChangesShown(!props.changesShown)}>
              {props.changesShown ? "Hide changes" : "Show changes"}
            </Button>
            <Button variant="primary" isDisabled={props.busy} onPress={props.onApply}>
              Apply to {changes.length} file{changes.length === 1 ? "" : "s"}
            </Button>
          </div>
        </>
      )}
    </Panel>
  );
}
```

- [ ] **Step 2: The screen**

`gui/src/screens/VariablePanel.tsx` keeps its shape and gains the selected key:

```tsx
  const [selected, setSelected] = useState<string | undefined>(undefined);
  // `undefined` until the reader chooses: the chooser then settles on the producer's value, the
  // direction the tool's own rule reads in, and says what that would change.
  const [chosen, setChosen] = useState<string | null | undefined>(undefined);
  const [typed, setTyped] = useState<string | undefined>(undefined);
  const [range, setRange] = useState<{ min: string; max: string }>({ min: "", max: "" });
  const [changesShown, setChangesShown] = useState(false);
  const [refused, setRefused] = useState<string | null>(null);
  const target =
    selected === undefined || variable.data === undefined
      ? null
      : chosen === undefined
        ? startingRaw(variable.data, selected)
        : chosen;
  const preview = useQuery({
    queryKey: ["settle", name, selected, target, revision],
    queryFn: () => getSettle(name, selected as string, target),
    enabled: variable.data !== undefined && selected !== undefined,
  });
```

Selecting a row starts that key afresh - what was chosen for the last one means nothing for this
one:

```tsx
  const select = (key: string | undefined) => {
    setSelected(key);
    setChosen(undefined);
    setTyped(undefined);
    setChangesShown(false);
    setRefused(null);
    setRange(
      key === undefined || variable.data === undefined
        ? { min: "", max: "" }
        : limitsOf(startingRaw(variable.data, key)),
    );
  };
```

The unit cell of the component table hands the reader over to the unit's chooser, which is what
`focusPicker` has always asked for; it now says which row to open as well:

```tsx
  useEffect(() => {
    if (focusPicker !== null) select("unit");
    // `select` is rebuilt every render and reads only state setters and the latest data.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusPicker]);
```

A range typed into the two fields is the value chosen as soon as it is a range:

```tsx
  const onRange = (next: { min: string; max: string }) => {
    setRange(next);
    const raw = limitsRaw(next.min, next.max);
    // A half-typed range is not a choice: the preview keeps showing the last whole one.
    if (raw !== null) {
      setChosen(raw);
      setRefused(null);
    }
  };
```

The view is handed what it draws:

```tsx
    <VariablePanelView
      variable={variable.data}
      units={units.data}
      selected={selected}
      onSelect={select}
      chosen={target}
      typed={typed ?? (selected === undefined ? "" : labelOfRaw(variable.data, selected, target))}
      // Never the target: opening the list on the producer's value must still list everything,
      // not just the entries that happen to contain it (spec 5.3, and part 1's own journey).
      narrow={typed ?? ""}
      onTyped={setTyped}
      onChosen={(raw) => {
        setChosen(raw);
        setTyped(undefined);
        setRefused(null);
        if (selected === "limits") setRange(limitsOf(raw));
      }}
      onPickerClosed={() => setTyped(undefined)}
      range={range}
      onRange={onRange}
      note={
        selected === "unit" && outsideVocabulary(units.data, textOf(target ?? undefined))
          ? "Not one of this project's units"
          : undefined
      }
      preview={preview.data ?? null}
      refusal={refused ?? (preview.error === null ? null : preview.error.message)}
      changesShown={changesShown}
      onChangesShown={setChangesShown}
      onApply={() => apply.mutate()}
      busy={stopped || apply.isPending}
      focus={focusPicker}
      onClose={onClose}
    />
```

Everything else stays as part 1 wrote it: the `undeclared` effect and its early `return null`, the
error panel, the "Reading …" panel, and the `apply` mutation with its `stale` sentence and its
three invalidations (`variable`, `units`, `settle`). The mutation's `onSuccess` keeps the key
selected and drops what was typed, so the panel says there is nothing left to change.

- [ ] **Step 3: Retire what part 1's panel alone used**

`unitOfDeclaration`, `willChange` and `startingUnit` in `gui/src/lib/units.ts` now have no caller - `git grep -n "unitOfDeclaration\|willChange\|startingUnit" gui/src` says so once the stories of Step 6 are written. Delete each one that has none, with its tests in `gui/src/lib/units.test.ts`; keep `describe`, `pickerSections`, `unitLabel`, `enteredUnit`, `outsideVocabulary`, `rawOf`, `textOf`, `consequence`, `baseName`, `hunkLines` and `editOf`, which the unit chooser, part 2's Units tab and `Changes` still use. Dead code under a 100 % gate is a test that proves nothing.

- [ ] **Step 4: The panel's stories**

Rewrite `gui/src/components/VariablePanelView.stories.tsx` around the new props, keeping part 1's seven scenarios and adding the five the other keys bring. Its `View` holds the reader's own state exactly as `VariablePanel.tsx` does in Step 2 - `selected`, `chosen`, `typed`, `range`, `changesShown` - and draws on the fixtures Task 5 added (`SHAPED`, `MIXED_KINDS`, `PREVIEW_CONVERSION`) beside part 1's.

```tsx
export const Disagreeing = () => <View variable={DISAGREEING} units={FREE_UNITS} preview={ONE_FILE} selected="unit" />;
export const NothingSelected = () => <View variable={DISAGREEING} units={FREE_UNITS} preview={null} />;
export const ChangesShown = () => <View variable={DISAGREEING} units={FREE_UNITS} preview={ONE_FILE} selected="unit" changesShown />;
export const PickerOpen = () => <View variable={DISAGREEING} units={FREE_UNITS} preview={ONE_FILE} selected="unit" pickerOpen />;
export const TypedOutsideVocabulary = () => <View variable={DISAGREEING} units={VOCABULARY} preview={null} selected="unit" chosen='"RPM"' />;
export const FixedByType = () => (
  <View
    variable={FIXED_BY_TYPE}
    units={FREE_UNITS}
    preview={null}
    selected="unit"
    refusal="the declaration of 'ValueA' in sensor_hub.ddd.json names the type 'Speed_t', which fixes its unit"
  />
);
export const Agreeing = () => <View variable={AGREEING} units={FREE_UNITS} preview={NOTHING} selected="unit" />;
export const RefusedAsStale = () => (
  <View
    variable={DISAGREEING}
    units={FREE_UNITS}
    preview={null}
    selected="unit"
    refusal="A file changed on disk, so nothing was written. The panel now shows the files as they are."
  />
);
export const ConversionChosen = () => (
  <View variable={DISAGREEING} units={FREE_UNITS} preview={PREVIEW_CONVERSION} selected="conversion" pickerOpen />
);
export const RangeTyped = () => <View variable={SHAPED} units={FREE_UNITS} preview={ONE_FILE} selected="limits" />;
export const NameChosen = () => <View variable={SHAPED} units={FREE_UNITS} preview={null} selected="input" pickerOpen />;
export const NotOnThisKind = () => <View variable={MIXED_KINDS} units={FREE_UNITS} preview={null} selected="dimensions" />;
```

Every story is a plain exported function component - no import from `@ladle/react`. The two components' own stories were written in Task 5 and do not change here.

- [ ] **Step 5: Run the page's gate**

Run: `cd gui && npm run lint && npm run typecheck && npm test && npm run build && npm run ladle-build`
Expected: green, Vitest still at 100 % over `src/api`, `src/lib`, `src/state`.

- [ ] **Step 6: Remake the panel's screenshot references, and look at them**

```bash
UPDATE=1 docker compose run --rm gui-screenshots
docker compose run --rm gui-screenshots
```

Every `components--variablepanelview--*` reference changes, since the panel is a different
picture now. Open each one: a table of twelve rows that runs off the panel, a chooser sitting
under the fold or a row whose "will change" tag wrapped is a story or a style to fix.

- [ ] **Step 7: Drive it by hand once**

```bash
export PATH="$HOME/.local/node-v24.21.0/bin:$PWD/.venv/bin:$PATH"
cd gui && npm run build && cd ..
python -m ddd gui examples/demo/demo.ddd.json --no-browser
```

Open the address it prints, go to Controller, press the unit cell of `ValueA`, and check with
your own eyes: the unit's row is selected and its field has the focus; selecting `conversion`
lists SensorHub's conversion; selecting `limits` fills the two fields; selecting `kind` opens
nothing. Then stop the server and put the example back if anything was applied
(`git checkout -- examples/demo`).

- [ ] **Step 8: Commit**

```bash
git add gui/src/components gui/src/screens/VariablePanel.tsx gui/src/lib/units.ts gui/src/lib/units.test.ts gui/src/stories/fixtures.ts gui/screenshots/references
git commit -m "settle any key of a variable from its panel

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 7: The journeys

What a reader does, end to end, in a real browser against a real server over a copy of the examples.

**Files:**
- Create: `gui/e2e/keys.spec.ts`
- Modify: `gui/e2e/demo.ts` (helpers the new journeys share), `gui/e2e/skeleton.spec.ts` (the policy journey visits the new table)

**Interfaces:**
- Consumes: the `gui` fixture of `gui/e2e/fixtures.ts` (a copy of an example, `ddd gui` over it, the address it printed) and the helpers of `gui/e2e/demo.ts`.

- [ ] **Step 1: Two helpers the journeys share**

In `gui/e2e/demo.ts`, beside `drift` and `chooseUnit`:

```ts
/** Opens a variable's panel from its component's table, the way a reader reaches it: the unit
 * cell, which opens the panel on the unit's row with its field focused. */
export async function openPanel(
  page: Page,
  address: string,
  variable: string,
  component = "Controller",
): Promise<Locator> {
  await page.goto(address);
  await page.getByRole("button", { name: component, exact: true }).click();
  await page.getByRole("button", { name: `Set the unit of ${variable}` }).click();
  return page.getByRole("complementary", { name: variable });
}

/** One variable's linear factor in one file of a copy drifted, saved from outside; answers the
 * file as it was before. */
export function driftFactor(
  directory: string,
  file: string,
  variable: string,
  factor: number,
): Buffer {
  const path = join(directory, file);
  const before = readFileSync(path);
  const text = before
    .toString("utf8")
    .replace(new RegExp(`("name": "${variable}"[\\s\\S]*?"factor": )[0-9.]+`), `$1${factor}`);
  writeFileSync(path, text, "utf8");
  return before;
}
```

`Locator` comes from `@playwright/test`, beside the `Page` the file already imports.

- [ ] **Step 2: Write the journeys**

Create `gui/e2e/keys.spec.ts`:

```ts
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { CONTROLLER, PUMP, SENSOR_HUB, driftFactor, openPanel } from "./demo";
import { expect, test } from "./fixtures";

/** ValueA's definition in one file of the copy, read back from disk. */
function valueA(directory: string, file: string): Record<string, never> {
  const data = JSON.parse(readFileSync(join(directory, file), "utf8"));
  const entry = data.component.interface.find(
    (declaration: { definition: { name: string } }) => declaration.definition.name === "ValueA",
  );
  return entry.definition;
}

test("a conversion drifted from outside is carried back from the producer", async ({
  page,
  gui,
}) => {
  // The demo's two declarations of ValueA state one conversion; drifting Controller's factor
  // makes the row disagree, and the row a reader settles is the producer's own value.
  driftFactor(gui.directory, CONTROLLER, "ValueA", 0.25);
  const panel = await openPanel(page, gui.address, "ValueA");
  await panel.getByRole("row", { name: /^conversion/ }).click();
  const field = panel.getByRole("combobox", { name: "Conversion of ValueA" });
  await expect(field).toHaveValue("linear ×0.5");
  await expect(panel.getByText("Changes 1 file: controller.ddd.json")).toBeVisible();
  await panel.getByRole("button", { name: "Show changes" }).click();
  await expect(panel.locator(".hunk .added")).toContainText("0.5");

  await panel.getByRole("button", { name: "Apply to 1 file" }).click();
  await expect(panel.getByText("Nothing to change")).toBeVisible();
  expect(valueA(gui.directory, CONTROLLER).conversion).toEqual({ kind: "linear", factor: 0.5 });
});

test("a range typed into the two fields reaches every declaration", async ({ page, gui }) => {
  const panel = await openPanel(page, gui.address, "ValueA");
  await panel.getByRole("row", { name: /^limits/ }).click();
  await expect(panel.getByLabel("Max")).toHaveValue("100");
  await panel.getByLabel("Max").fill("50");
  await expect(
    panel.getByText("Changes 2 files: controller.ddd.json, sensor_hub.ddd.json"),
  ).toBeVisible();

  await panel.getByRole("button", { name: "Apply to 2 files" }).click();
  await expect(panel.getByText("Nothing to change")).toBeVisible();
  expect(valueA(gui.directory, SENSOR_HUB).limits).toEqual({ min: 0, max: 50 });
  expect(valueA(gui.directory, CONTROLLER).limits).toEqual({ min: 0, max: 50 });
});

test("a truth value is typed, confirmed with Enter, and cannot be left unstated", async ({
  page,
  gui,
}) => {
  const panel = await openPanel(page, gui.address, "ValueA");
  await panel.getByRole("row", { name: /^volatile/ }).click();
  const field = panel.getByRole("combobox", { name: "Volatile of ValueA" });
  await expect(field).toHaveValue("false");
  // Every kind states its volatile, so the list has no way of taking it away.
  await field.press("ArrowDown");
  await expect(panel.getByRole("option", { name: "state nothing" })).toHaveCount(0);

  await field.fill("true");
  await field.press("Enter");
  await panel.getByRole("button", { name: "Apply to 2 files" }).click();
  await expect(panel.getByText("Nothing to change")).toBeVisible();
  expect(valueA(gui.directory, SENSOR_HUB).volatile).toBe(true);
  expect(valueA(gui.directory, CONTROLLER).volatile).toBe(true);
});

test("a key a declared type fixes is refused, and nothing is written", async ({
  page,
  vocabularyGui,
}) => {
  // The pump's TorqueLimit names Torque_t, which fixes its unit at Nm.
  const before = readFileSync(join(vocabularyGui.directory, PUMP));
  const panel = await openPanel(page, vocabularyGui.address, "TorqueLimit", "Pump");
  const field = panel.getByRole("combobox", { name: "Unit of TorqueLimit" });
  await field.fill("rpm");
  await field.press("Enter");
  await expect(panel.getByText("which fixes its unit")).toBeVisible();
  await expect(panel.getByRole("button", { name: /^Apply to/ })).toHaveCount(0);
  expect(readFileSync(join(vocabularyGui.directory, PUMP)).equals(before)).toBe(true);
});

test("a key that may be left unstated goes from every declaration", async ({ page, gui }) => {
  const panel = await openPanel(page, gui.address, "ValueA");
  // The unit's own chooser is part 1's picker, whose entry for no unit reads "no unit".
  const field = panel.getByRole("combobox", { name: "Unit of ValueA" });
  await field.fill("no unit");
  await field.press("Enter");
  await panel.getByRole("button", { name: "Apply to 2 files" }).click();
  await expect(panel.getByRole("row", { name: /^unit/ })).toContainText("none");
  expect(valueA(gui.directory, SENSOR_HUB).unit).toBeUndefined();
  expect(valueA(gui.directory, CONTROLLER).unit).toBeUndefined();
});
```

Part 1's two journeys in `gui/e2e/units.spec.ts` must keep working unchanged: the unit cell still opens the panel on the unit's row with the field focused, and the picker still takes a unit typed and confirmed with Enter. Run them and do not rewrite them.

- [ ] **Step 3: The policy journey visits the new table**

In `gui/e2e/skeleton.spec.ts`, the journey that collects Content-Security-Policy violations opens
the variable panel: have it select a row of the keys table and open its chooser, so the new
controls are on the page while the console is watched. Nothing may be reported.

- [ ] **Step 4: Run them on both machines' browsers**

Run (Linux): `cd gui && PLAYWRIGHT_CHANNEL=chrome npm run e2e`
Run (Windows): `cd gui && DDD_PYTHON=/c/git/ac11/ddd/.venv/Scripts/python.exe PLAYWRIGHT_CHANNEL=msedge npm run e2e`
Expected: every journey passes, part 1's and part 2's included.

- [ ] **Step 5: Commit**

```bash
git add gui/e2e
git commit -m "drive every kind of key from the panel, end to end

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 8: The documentation

What a user and a developer read about the panel. The language server's actions did not change, so `docs/editor_integration.rst` is not touched.

**Files:**
- Modify: `CHANGELOG.md`, `docs/command_line_interface.rst`, `docs/developer_documentation.rst`

- [ ] **Step 1: The changelog**

In `CHANGELOG.md`, under `## Unreleased`, add a third paragraph to the browser-interface entry,
beside the one part 2 added:

```markdown
  A variable's panel now carries every key its declarations share rather than the unit alone:
  a row per key - what the variable is made of, what it means, what shape it has and which
  declarations it points at - a column per declaration, and the rows they disagree about
  first.  Selecting a row offers the values already in play, each naming the components
  stating it and marking the producer's, and the field the key takes: one of the eleven
  datatypes, a type, an axis or a measurement the project declares, true or false, a minimum
  and a maximum, or the unit picker with the project's vocabulary behind it.  A conversion and
  a list of dimensions are carried from the declaration that states them rather than composed
  here, and `kind` is shown and never settled, since it decides which other keys a declaration
  may carry at all.  What is chosen is applied to every declaration at once, with the lines
  each file will change shown on request, exactly as a unit already was.
```

Two spaces after a full stop, as the rest of the file writes it.

- [ ] **Step 2: The command page**

In `docs/command_line_interface.rst`, the `ddd gui` row ends "a variable's unit is set from a
panel for the whole variable, not one declaration." Replace that clause with:

```text
       a variable's panel shows every key its declarations share, says which of them they
       disagree about, and settles one on every declaration at once
```

keeping the sentence it sits in and the row's indentation.

- [ ] **Step 3: The developer page**

In `docs/developer_documentation.rst`, after the paragraph beginning "A change to the project's
units", add:

```text
What a key of a variable offers the panel is worked out in ``ddd.variable_keys``: per key, and
per declaration, whether that declaration's kind has the key at all and whether it must state
it - ``ddd.models.definition_keys``, plus the storage keys a declaration cannot be left without
- beside the values in play, one entry per value however its file spells it, the components
stating it and whether one of them produces the variable. It says which field chooses the key
and what that field names: the eleven datatypes, the project's types, its declared constants,
or its axes and measurements, which the navigation index records as it reads each declaration's
kind. ``GET /api/variable`` answers those beside the declarations themselves;
``GET /api/settle`` settles any of the twelve keys of ``ddd.lsp.edits.PROPAGATED_KEYS`` and is
the same endpoint the unit has always used.
```

- [ ] **Step 4: Build the documentation**

Run (Linux PC):

```bash
docker compose run --rm --user "$(id -u):$(id -g)" -e JAVA_TOOL_OPTIONS=-Duser.home=/tmp ddd python -m sphinx -M html docs build/docs_out -W
```

Expected: `build succeeded.` with no warnings.

- [ ] **Step 5: Run the Python gate**

Run: `python -m pytest && ruff check . && ruff format --check . && mypy`
Expected: green - `tests/test_documentation.py` reads these pages.

- [ ] **Step 6: Commit**

```bash
git add CHANGELOG.md docs/command_line_interface.rst docs/developer_documentation.rst
git commit -m "say what the variable panel settles now

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 9: Milestone gate

The whole thing, from a clean build, on the Linux PC. Nothing here changes code: a failure is a task to reopen, not a line to patch here.

- [ ] **Step 1: The Python gate**

```bash
export PATH="$HOME/.local/node-v24.21.0/bin:$PWD/.venv/bin:$PATH"
python -m pytest && ruff check . && ruff format --check . && mypy
```

Expected: every test passing at 100 % line and branch coverage; ruff and mypy clean.

- [ ] **Step 2: The documentation from nothing**

```bash
rm -rf build/docs_out
docker compose run --rm --user "$(id -u):$(id -g)" -e JAVA_TOOL_OPTIONS=-Duser.home=/tmp ddd python -m sphinx -M html docs build/docs_out -W
```

Expected: `build succeeded.`, no warnings.

- [ ] **Step 3: The page, from a clean install**

```bash
cd gui && npm ci && npm run schemas && npm run lint && npm run typecheck && npm test && npm run build && npm run ladle-build
```

Expected: green, Vitest at 100 % over `src/api`, `src/lib`, `src/state`.

- [ ] **Step 4: The journeys and the screenshots**

```bash
cd gui && PLAYWRIGHT_CHANNEL=chrome npm run e2e
cd .. && docker compose run --rm gui-screenshots
```

Expected: every journey passes, every story matches its reference.

- [ ] **Step 5: The real application**

Serve the demo in the development image and drive it in a browser, as parts 1 and 2 did, photographing what the pull request shows:

```bash
docker compose up gui
```

- the panel of `ValueA` with its table of keys, the disagreeing row first;
- a conversion carried from the producer, with Show changes open;
- a range typed into the two fields;
- a key a declared type fixes, refused.

Put the four screenshots beside the plan in `docs/superpowers/plans/2026-09-20-gui-other-keys/`, and put `examples/demo` back as it was afterwards (`git checkout -- examples/demo`) - a demo left edited fails the next gate's tests.

- [ ] **Step 6: The tree is clean**

```bash
git status --short
```

Expected: nothing but the screenshots the step above added.

- [ ] **Step 7: Commit the screenshots and the log**

```bash
git add docs/superpowers/plans/2026-09-20-gui-other-keys
git commit -m "log part 3's tasks and keep the panel's screenshots beside the plan

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Progress log

| Task | Started | Duration | Tokens | Notes |
| --- | --- | --- | --- | --- |
| | | | | |

## Left open by the implementers

_Filled in as the plan runs: anything found and not fixed, with why._

- The whitespace of a value is the file's own. Two declarations stating one value in different layouts are one value in play and one agreeing row, but `ddd.lsp.edits.settle` compares the json text: settling that value on both rewrites the one whose layout differs, which Show changes shows as a change of the line. The edit engine lays every value out in the file's own style, so the content is the same afterwards.
- Moving a variable onto a declared type - choosing a `typename` for a declaration that states a `datatype` - writes a file the loader refuses until its storage keys go, which the panel cannot do in the same edit. Spec 4.2 rules that such a value is written and reported on the next analysis; a reader doing this fixes the rest in an editor.

## Rulings made while writing and executing the plan

Each ruling: what was decided, why, and what it costs if it is wrong.

1. **The index records each object's kind** (`Index.kinds`), rather than the answer reading every component's file per request to find the project's axes and measurements. Why: the index already walks every declaration, and the panel's choosers need the names on every open. Cost if wrong: one dictionary per project in memory, and a kind recorded from the first declaration where two disagree - which is a disagreement no chooser settles anyway.
2. **The storage keys a declaration uses are required at that declaration** - `datatype` and `conversion` where it states a datatype, `typename` where it names a type - although `definition_keys` calls all three optional. Why: they are optional to the models because a definition states one set or the other, and offering to strip the set in use writes a file the loader refuses. Cost if wrong: a reader who wants a declaration without either has to edit the file by hand, which is the only way to get there anyway.
3. **One value, however it is spelled.** `_in_play` groups by the value rather than by the json text, and carries the producer's spelling. Why: the checker compares values, so a row the checker does not report must not read as a disagreement here. Cost if wrong: settling a value on a declaration that spells it differently rewrites that line - see "Left open".
4. **The server says what disagrees** (`KeyOffer.disagrees`), rather than the page working it out from the values. Why: silence is a value for every key but the deferred ones, and `DEFERRED_KEYS` is the language server's own list - a copy of it in TypeScript would drift the day a key joins it. Cost if wrong: one more field in the answer.
5. **A key no declaration's kind holds is not a row at all**, where a key some hold and others do not is a row with "not on a parameter" in those cells. Why: an axis has no `x_axis`, and a row of nothing but refusals teaches a reader nothing; a mixed row is exactly what a reader needs to see. Cost if wrong: a reader who wanted to know that an axis has no `x_axis` does not learn it here.
6. **A name is chosen from the list and never typed**, where a `size` may be typed as a whole number. Why: the choices are the answer to "what may this be", and a typed name is a reference to something the project does not declare - which the loader reports and nothing in the panel could fix. Cost if wrong: a reader naming an object declared in a file that did not load has to edit by hand until it loads.
7. **`limits` is two fields beside the list, and the list stays.** Why: a range is the one value a reader is likely to want that no declaration has yet, and the values in play are how the producer's range is taken in one press. Cost if wrong: a slightly busier chooser for one key of twelve.
8. **The unit keeps part 1's picker.** Why: it carries part 2's vocabulary, its "not one of this project's units" note and its own journeys; a second unit chooser would be a second set of rules. Cost if wrong: one key's chooser looks a little different from the other eleven, which is what its vocabulary earns it.
