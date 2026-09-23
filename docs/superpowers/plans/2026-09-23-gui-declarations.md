# Adding and removing declarations (part 7) implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A component's interface gains the three verbs it has never had: read a variable the project already declares, carrying the producer's own keys; declare a new object of any of the six kinds; and remove a declaration.

**Architecture:** Nothing new is indexed and nothing new is formatted. `ddd.lsp.navigation.Index` already records every declared name, its producers and every C identifier already spent; `definition_keys` answers a kind's required keys from the kind alone; and the edit engine's `insert` and `remove` already write a declaration into `component.interface` in the layout the file uses. One new module plans the three verbs as edit-engine operations, exactly as `ddd.type_plans` plans a type's. The page reuses part 3's key chooser to draw a new declaration's form, and adds one panel beside the component's table and one offer inside a variable's panel.

**Tech Stack:** Python 3.12+ with pydantic; React 19.3, TypeScript 7 strict, TanStack Query 5, `react-aria-components` 1.21.1, `@ladle/react` 5.1.1, Vitest, Playwright 1.63.0 and its image `mcr.microsoft.com/playwright:v1.63.0-noble`.

**Spec:** `docs/superpowers/specs/2026-09-23-gui-declarations-design.md` (part 7; read it before starting any task). Parts 1 to 6 - the design documents beside it and their plans - describe the panel, the Units tab, the other keys, the findings, undo and the types, all of which this builds on.

## Global Constraints

- Python floor 3.12; **no new runtime dependency** of the Python package, and no new frontend dependency.
- Python gate: `python -m pytest` at 100 % line **and** branch coverage, `ruff check .`, `ruff format --check .`, `mypy`. No `pragma: no cover`, no `pytest.skip`/`skipif`/`xfail`/`importorskip`. **A branch no test can reach is a defect, not a safety net.**
- Line length 100; ruff selects E, F, W, I, N, UP, B, SIM, RUF, ANN, PTH, C4; mypy strict with the pydantic plugin. Tests are exempt from ANN only. `__all__` stays sorted (RUF022).
- **The Python gate runs in every task that touches Python, the documentation, `gui/scripts/licenses.mjs` or anything `tests/test_documentation.py` reads.**
- Every request and answer of the API is declared in `src/ddd/gui/contract.py`; the page's types are generated from it by `npm run schemas` into the git-ignored `gui/src/generated/`, and only `gui/src/api/types.ts` is committed, its export list sorted case-insensitively. **A model no endpoint reaches fails `tests/test_gui_contract.py::test_every_model_declared_here_has_a_defs_entry`.**
- **The language server, the analysis and the generators are untouched.** `src/ddd/lsp/` may be *read* freely; `tests/test_lsp.py`, `tests/test_analysis.py` and `tests/test_generation.py` pass unchanged. What the checks report does not change - this writes the same files a person writes by hand.
- An edit is written all-or-nothing, previewed before it is applied, and undone by part 5's stack: every `POST /api/edit` this adds carries a label.
- Vitest keeps its 100 % gate over `src/api`, `src/lib`, `src/state`. Components and screens are covered by stories, screenshot tests and journeys - **no Vitest test for a component or a screen**.
- **A story imports nothing from `@ladle/react`.** A story is a plain exported function component holding its own state.
- The Content-Security-Policy stays as it is, and no page may report a violation.
- **A React Aria `className` is a function keeping `defaultClassName`** when a class is added; `gui/src/components/UnitsTableView.tsx` is the working example.
- **A new or changed story gets its screenshot reference made in Playwright's image** - `UPDATE=1 docker compose run --rm gui-screenshots`, then `docker compose run --rm gui-screenshots` - and every new or changed reference is opened and looked at. **No existing reference may change**: this part adds panels, it does not restyle one.
- **The journeys drive the compiled pages**: `npm run build` before `npm run e2e`, always.
- `ddd gui` stays labelled **preview**.
- Two machines:
  - **Linux PC** (`/home/sauci/Documents/Github/ddd`): `export PATH="$HOME/.local/node-v24.21.0/bin:$PWD/.venv/bin:$PATH"` at the repository root. Journeys: `cd gui && npm run build && PLAYWRIGHT_CHANNEL=chrome npm run e2e` - **Google Chrome is installed here, so no browser download is needed**. The documentation builds in the development image: `docker compose run --rm --user "$(id -u):$(id -g)" -e JAVA_TOOL_OPTIONS=-Duser.home=/tmp ddd python -m sphinx -M html docs build/docs_out -W`.
  - **Windows PC** (Git Bash): `export PATH="/c/git/ac11/ddd/.venv/Scripts:/c/Program Files/nodejs:$PATH" && cd /c/git/ac11/ddd`; journeys with `DDD_PYTHON=/c/git/ac11/ddd/.venv/Scripts/python.exe PLAYWRIGHT_CHANNEL=msedge npm run e2e`. No Docker: screenshot references are made on the Linux PC or read from CI.

## Prerequisites (before Task 1)

- The branch `feature/gui-declarations` starts from master after #56 (`6a0208b`); the spec is its first commit (`27a48d6`).
- The venv has `pip install -e ".[dev]"`, `gui/` has `npm ci`, and the gate is green on the branch before anything changes.
- `examples/demo` is the example this part leans on. **Measured, not assumed** - read these facts once before Task 1 rather than rediscovering them:
  - It declares 23 names: `AxisA`, `AxisB`, `BlockA`, `CurveA`, `CurveB`, `Diagnosis`, `FlagA`, `MapA`, `ParameterA`, `SoftwareLabel`, `StateA`, `StateName`, `ValueA` … `ValueK`.
  - All six kinds appear: `measurement`, `parameter`, `value_block`, `curve`, `map`, `axis`.
  - `Controller` (`examples/demo/components/controller.ddd.json`) declares 14 of them and could read the other 9: `BlockA`, `CurveB`, `Diagnosis`, `FlagA`, `ValueC`, `ValueD`, `ValueI`, `ValueJ`, `ValueK`.
  - **It declares no constants at all**, so a `size` or a `dimension` is typed as a whole number rather than chosen - which is what the journeys do.
  - `Pressure` is a free name: `rename_problem` answers `None` for it. `ValueA` answers `'ValueA' is already declared by this project`, and `STATE_OFF` answers `'STATE_OFF' is an enumerator of enum 'StateA_t', which shares c's namespace with the variables`.

## Conventions for every task

- Work on `feature/gui-declarations`. Tests first: write the failing test, watch it fail, implement, watch it pass.
- One commit per task (a fix round may add commits), its message a **short** lowercase sentence saying what the change does - the repository's habit is 40 to 70 characters - ending with a blank line and a `Co-Authored-By:` line naming the model that wrote it.
- Before a task's commit, run the gate for what it touched.
- After Task 3, `npm run schemas` regenerates `gui/src/generated/api.ts`; run it before every frontend task.
- Stage the files you changed by name. There is an untracked `.claude/` directory in the tree that must never be swept into a commit.
- Scratch files go to the session scratchpad, never into the repository.

## File structure

| File | Responsibility |
| --- | --- |
| `src/ddd/declaration_plans.py` (new) | Everything part 7 adds to the Python side: what a component may add (Task 1) and what each of the three verbs takes (Task 2). One module, because the reading half is fifteen lines about the same subject. |
| `src/ddd/gui/contract.py`, `src/ddd/gui/api.py` | The models and the two endpoints (Task 3). |
| `tests/test_declaration_plans.py` (new), `tests/test_gui_api.py`, `tests/test_gui_server.py` | The rules, the plans and the endpoints (Tasks 1 to 3). |
| `gui/src/api/types.ts`, `gui/src/api/client.ts` | The new types re-exported; `getDeclarable` and `getDeclarationPlan` (Task 4). |
| `gui/src/lib/declarations.ts` (new) | The form's logic: which keys a kind asks for, which scopes a name may take, the json a form makes, and the sentence that tells reading from declaring. Pure (Task 4). |
| `gui/src/components/DimensionsField.tsx` (new) | A value block's `dimensions`: the `size` chooser repeated, with stories (Task 5). |
| `gui/src/components/DeclarePanelView.tsx` (new) | The add panel as a picture of its props, with stories (Task 6). |
| `gui/src/components/VariablePanelView.tsx` | The removal offer, with stories (Task 7). |
| `gui/src/screens/DeclarePanel.tsx` (new), `gui/src/screens/ComponentPage.tsx` | The panel's queries, its mutation and its refusals, and the control that opens it (Task 8). |
| `gui/src/screens/VariablePanel.tsx` | Removal's mutation, its refusal and the clearing between the two write paths (Task 9). |
| `gui/src/stories/fixtures.ts`, `gui/src/styles/ui.css` | What the stories draw, and the panel's own rules (Tasks 5 to 7). |
| `gui/e2e/declarations.spec.ts` (new), `gui/e2e/units.spec.ts` | The journeys, and the policy journey (Task 10). |
| `CHANGELOG.md`, `docs/command_line_interface.rst`, `docs/developer_documentation.rst` | What a user and a developer read (Task 11). |

## Interfaces between the tasks

Every name here is exact; a task's implementer sees only their own task, and this is how they learn what their neighbours produce and consume.

**Task 1 produces** (`src/ddd/declaration_plans.py`):

```python
KINDS: Final = ("measurement", "parameter", "value_block", "curve", "map", "axis")
"""The six kinds a declaration may be, in the order the form offers them."""

SCOPES: Final = ("output", "input", "local")
"""``ddd.models.component.Scope``'s three values, in the order the form offers them."""

CARRIED_BY_A_READER: Final = frozenset({"id", "init"})
"""What a reader does NOT copy from the producer it reads.

Measured against examples/demo, examples/structures and examples/vocabulary: across every
variable declared by more than one component, a reader's definition is the producer's without
these two and with nothing of its own. ``id`` is the producer's identity - ``ddd.identity``
stamps only a producing declaration - and ``init`` is the owner's initial value.
"""


@dataclass(frozen=True, slots=True)
class Declarable:
    """One variable this component could read, as the name field offers it."""

    name: str
    kind: str               # "measurement" … "axis", or "" when no declaration states one
    producer: str | None    # the component producing it; None when nothing does


def declarable(built: Index, file: Path, cache: dict[Path, Document]) -> tuple[Declarable, ...]:
    """Every name the project declares that ``file`` does not, sorted by name."""


def scopes_for(built: Index, name: str) -> tuple[str, ...]:
    """Which of :data:`SCOPES` this name may be declared with, in that order.

    ``input`` always. ``output`` only when nothing produces the name yet, so the menu cannot
    make a ``multiple-producers``; ``local`` only when nothing declares it at all, because
    ``local-conflict`` is exactly a local beside another declaration. A name the project has
    never seen gets all three.
    """


def form_for(built: Index, kind: str) -> tuple[KeyOffer, ...]:
    """What a new declaration of that kind asks for: one offer per key of ``KEY_ORDER`` the
    kind accepts, each with no value in play, ``required`` set from ``definition_keys``.

    An unknown kind answers empty - ``definition_keys`` answers two empty sets for one, and the
    endpoint refuses before reaching here, so this never raises.
    """
```

**Task 2 produces** (the same module):

```python
@dataclass(frozen=True, slots=True)
class DeclarationPlan:
    """Everything one change of an interface takes: one edit per file, sorted by path."""

    edits: tuple[PlannedEdit, ...]


class DeclarationRefusalError(Exception):
    """A change of an interface that cannot be planned, and the code both clients refuse with."""

    code: Literal["invalid", "not-found"]
    message: str

    def __init__(self, code: Literal["invalid", "not-found"], message: str) -> None: ...


def read_object(
    built: Index, file: Path, name: str, scope: str, cache: dict[Path, Document]
) -> DeclarationPlan:
    """What reading an object the project already has takes: one ``insert`` appending a
    declaration that carries the producer's own definition, less ``CARRIED_BY_A_READER``."""


def declare_object(
    built: Index, file: Path, scope: str, definition: Mapping[str, object],
    cache: dict[Path, Document]
) -> DeclarationPlan:
    """What declaring a new object takes: one ``insert`` appending the definition given, with a
    fresh ``id`` when ``scope`` is ``output``."""


def remove_declaration(
    built: Index, file: Path, name: str, cache: dict[Path, Document]
) -> DeclarationPlan:
    """What removing a declaration takes: one ``remove`` at its index in the interface."""
```

**Task 3 produces** (`src/ddd/gui/contract.py`, reached from `_ENDPOINTS`):

```python
class DeclarableName(_Frozen):
    name: str
    kind: str
    producer: str | None
    scopes: tuple[str, ...]


class KindForm(_Frozen):
    kind: str
    keys: tuple[VariableKeyOffer, ...]


class DeclarableReply(_Frozen):
    revision: int
    file: str
    names: tuple[DeclarableName, ...]
    kinds: tuple[KindForm, ...]
    scopes: tuple[str, ...]      # what a name the project has never seen may be declared with
```

`GET /api/declarable?file=` answers `DeclarableReply`; `GET /api/declaration-plan?action=read|declare|remove&file=…` answers the existing `PlanReply`. **No new plan model**: `PlanReply` is reused as part 6 reused it.

**Task 4 produces** (`gui/src/lib/declarations.ts`):

```ts
export type Mode = "unchosen" | "read" | "declare";

/** Which of the three the name field has landed on, and what it landed on. */
export function modeOf(typed: string, names: DeclarableName[]): Mode;

/** The variable the typed name names, or null when it names none. */
export function chosenName(typed: string, names: DeclarableName[]): DeclarableName | null;

/** Which scopes the typed name may be declared with, in DeclarableReply order. */
export function scopesOf(typed: string, reply: DeclarableReply): string[];

/** The keys a kind asks for, required first, in KEY_ORDER within each group. */
export function keysOf(kind: string, reply: DeclarableReply): VariableKeyOffer[];

/** The definition the form has made, as json text - null while a required key is unstated. */
export function definitionOf(
  name: string, kind: string, values: Record<string, string>, reply: DeclarableReply,
): string | null;

/** The sentence above the preview, which is what tells reading from declaring. */
export function declareSentence(
  typed: string, kind: string, scope: string, reply: DeclarableReply,
): string;

/** The json a row of dimension fields makes: `["4","CELLS"]` -> `[4, "CELLS"]`. */
export function dimensionsRaw(rows: string[]): string | null;
```

**Task 7 adds** to `gui/src/lib/declarations.ts`:

```ts
/** What removing one declaration leaves behind, written from what the panel already holds. */
export function removalSentence(
  variable: { name: string; declarations: { component: string; role: string }[] },
  from: string,
): string;
```

**Task 5 produces** `gui/src/components/DimensionsField.tsx`:

```ts
export interface DimensionsFieldProps {
  /** One entry per dimension, each a whole number or a constant's name. */
  rows: string[];
  /** The project's constants, offered beside whatever is typed. */
  constants: string[];
  owner: string;
  busy: boolean;
  onRows: (rows: string[]) => void;
}
export function DimensionsField(props: DimensionsFieldProps): JSX.Element;
```

**Task 6 produces** `gui/src/components/DeclarePanelView.tsx`, **Task 7** the removal offer inside `VariablePanelView`, **Task 8** `gui/src/screens/DeclarePanel.tsx`, and **Task 9** removal's wiring. Their props are written out in full in their own tasks.

---

### Task 1: What a component may add

**Files:**
- Create: `src/ddd/declaration_plans.py`
- Test: `tests/test_declaration_plans.py` (new)

**Interfaces:**
- Consumes: `ddd.lsp.navigation.Index` (`declarations: dict[str, list[Site]]`, `producers: dict[str, list[Site]]`, `kinds: dict[str, str]`), `ddd.lsp.ranges.read(path, cache) -> Document`, `ddd.models.objects.definition_keys(kind) -> (accepted, required)`, `ddd.variable_keys.KEY_ORDER`, `KeyOffer`, `offer_for(built, key, raw, *, required)`.
- Produces: `KINDS`, `SCOPES`, `CARRIED_BY_A_READER`, `INTERFACE`, `Declarable`, `declarable`, `scopes_for`, `form_for`, and the private `_component_of`. **`_statable` belongs to Task 2**, beside its only caller: the coverage gate is per-task, and a helper nothing in this task calls cannot be covered here.

- [ ] **Step 1: Write the failing tests**

```python
"""What a component may add to its interface, and what each change of one takes."""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import component, declare, project, write_tree
from ddd.declaration_plans import KINDS, SCOPES, Declarable, declarable, form_for, scopes_for
from ddd.diagnostics import DiagnosticBag
from ddd.loading import load_workspace
from ddd.lsp.navigation import Index, index
from ddd.lsp.ranges import Document

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
CONTROLLER = EXAMPLES / "demo" / "components" / "controller.ddd.json"


@pytest.fixture
def demo() -> Index:
    return index(load_workspace(EXAMPLES / "demo" / "demo.ddd.json", DiagnosticBag()))


@pytest.fixture
def cache() -> dict[Path, Document]:
    return {}


class TestWhatMayBeRead:
    def test_every_name_the_project_has_that_this_file_has_not(self, demo, cache) -> None:
        # Measured against examples/demo as it stands: Controller declares 14 of the project's
        # 23 names, so these 9 are what it could read, each with the component producing it.
        assert declarable(demo, CONTROLLER, cache) == (
            Declarable("BlockA", "value_block", "UserInterface"),
            Declarable("CurveB", "curve", "UserInterface"),
            Declarable("Diagnosis", "measurement", "SensorHub"),
            Declarable("FlagA", "measurement", "SensorHub"),
            Declarable("ValueC", "measurement", "SensorHub"),
            Declarable("ValueD", "measurement", "SensorHub"),
            Declarable("ValueI", "measurement", "UserInterface"),
            Declarable("ValueJ", "measurement", "EventLogger"),
            Declarable("ValueK", "measurement", "EventLogger"),
        )

    def test_a_name_nothing_produces_names_no_producer(self, tmp_path, cache) -> None:
        # Its own project, because every name of examples/demo is produced by something.
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("input", "Orphan")),
                "b.ddd.json": component("B"),
            },
        )
        built = index(load_workspace(tmp_path / "p.ddd.json", DiagnosticBag()))
        assert declarable(built, tmp_path / "b.ddd.json", cache) == (
            Declarable("Orphan", "measurement", None),
        )


class TestWhichScopesANameMayTake:
    def test_a_name_with_a_producer_may_only_be_read(self, demo) -> None:
        assert scopes_for(demo, "ValueC") == ("input",)

    def test_a_name_without_one_may_be_produced_or_read(self, tmp_path) -> None:
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("input", "Orphan")),
            },
        )
        built = index(load_workspace(tmp_path / "p.ddd.json", DiagnosticBag()))
        assert scopes_for(built, "Orphan") == ("output", "input")

    def test_a_name_the_project_has_never_seen_may_take_all_three(self, demo) -> None:
        assert scopes_for(demo, "Pressure") == SCOPES


class TestWhatAKindAsksFor:
    def test_every_kind_asks_for_what_the_models_require(self, demo) -> None:
        # Read from definition_keys rather than listed here, so a key added to a model shows up
        # as a failure of this test rather than as a form that cannot make a loadable file.
        required = {
            kind: {offer.key for offer in form_for(demo, kind) if offer.carried[0].required}
            for kind in KINDS
        }
        assert required == {
            "measurement": {"volatile"},
            "parameter": {"volatile"},
            "value_block": {"volatile", "dimensions"},
            "curve": {"volatile", "axis"},
            "map": {"volatile", "x_axis", "y_axis"},
            "axis": {"volatile", "size"},
        }

    def test_a_kind_offers_the_editors_the_chooser_already_draws(self, demo) -> None:
        editors = {offer.key: offer.editor for offer in form_for(demo, "axis")}
        assert editors["size"] == "size"
        assert editors["unit"] == "unit"
        assert editors["input"] == "name"

    def test_a_kind_nothing_declares_asks_for_nothing(self, demo) -> None:
        # definition_keys answers two empty sets for a kind it does not know, and the endpoint
        # refuses before reaching here - so this is the branch a broken caller would take.
        assert form_for(demo, "nonsense") == ()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/test_declaration_plans.py -q --no-cov`
Expected: FAIL, `ModuleNotFoundError: No module named 'ddd.declaration_plans'`.

- [ ] **Step 3: Write the module**

```python
"""What a component may add to its interface, and what each change of one takes.

Transport-neutral, like :mod:`ddd.type_plans` beside it. Nothing here writes a file: a verb
answers a plan of edit-engine operations, and ``POST /api/edit`` is what writes it, so one
engine makes every change ``ddd gui`` makes and part 5's stack puts any of them back.

Nothing here formats json either. ``ddd.editing.insertion`` lays a value out in the layout of
the place it goes - a key per line, a container of literals on one line - which is exactly how
the description files spell a declaration.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from ddd.editing import Operation
from ddd.identity import new_id
from ddd.lsp.navigation import Index, rename_problem
from ddd.lsp.ranges import Document, read
from ddd.lsp.units import PlannedEdit
from ddd.models.objects import definition_keys
from ddd.variable_keys import KEY_ORDER, KeyOffer, offer_for

KINDS: Final = ("measurement", "parameter", "value_block", "curve", "map", "axis")
"""The six kinds a declaration may be, in the order the form offers them."""

SCOPES: Final = ("output", "input", "local")
"""``ddd.models.component.Scope``'s three values, in the order the form offers them."""

CARRIED_BY_A_READER: Final = frozenset({"id", "init"})
"""What a reader does not copy from the producer it reads.

Measured across examples/demo, examples/structures and examples/vocabulary: for every variable
more than one component declares, a reader's definition is the producer's without these two,
and with nothing of its own. ``id`` is the producer's identity - :mod:`ddd.identity` stamps
only a producing declaration - and ``init`` is the owner's initial value.
"""

INTERFACE: Final = "component.interface"
"""Where a component's declarations live, which is the array a verb inserts into."""


@dataclass(frozen=True, slots=True)
class Declarable:
    """One variable this component could read, as the name field offers it."""

    name: str
    kind: str
    """``measurement`` … ``axis``, or ``""`` when no declaration of it states one."""

    producer: str | None
    """The component producing it; ``None`` when nothing does."""


def declarable(built: Index, file: Path, cache: dict[Path, Document]) -> tuple[Declarable, ...]:
    """Every name the project declares that ``file`` does not, sorted by name."""
    here = file.resolve()
    return tuple(
        Declarable(
            name=name,
            kind=built.kinds.get(name, ""),
            producer=(
                _component_of(produced[0].path, cache)
                if (produced := built.producers.get(name) or [])
                else None
            ),
        )
        for name, sites in sorted(built.declarations.items())
        if all(site.path != here for site in sites)
    )


def scopes_for(built: Index, name: str) -> tuple[str, ...]:
    """Which of :data:`SCOPES` this name may be declared with, in that order.

    ``input`` always. ``output`` only while nothing produces the name, so the menu cannot make
    a ``multiple-producers`` - and when something is missing a producer, this is the repair.
    ``local`` only for a name nothing declares at all, because ``local-conflict`` is exactly a
    local beside another declaration.
    """
    if name not in built.declarations:
        return SCOPES
    return ("input",) if built.producers.get(name) else ("output", "input")


def form_for(built: Index, kind: str) -> tuple[KeyOffer, ...]:
    """What a new declaration of that kind asks for: one offer per key of ``KEY_ORDER`` the
    kind accepts, each with no value in play and ``required`` as the models have it.

    A kind nothing declares answers empty rather than raising: ``definition_keys`` answers two
    empty sets for one, and the endpoint refuses before reaching here.
    """
    accepted, required = definition_keys(kind)
    return tuple(
        offer_for(built, key, None, required=key in required)
        for key in KEY_ORDER
        if key in accepted
    )


def _component_of(path: Path, cache: dict[Path, Document]) -> str:
    return str(read(path, cache).value_at("component.name") or "")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_declaration_plans.py -q --no-cov`
Expected: PASS, 8 tests.

- [ ] **Step 5: Run the gate**

Run: `python -m pytest -q && ruff check . && ruff format --check . && mypy`
Expected: 100 % coverage, all checks pass, no issues. Task 2 fills the module's other half, so every function written here has a test here.

- [ ] **Step 6: Commit**

```bash
git add src/ddd/declaration_plans.py tests/test_declaration_plans.py
git commit -m "say what a component may add to its interface

Co-Authored-By: <model that wrote it> <noreply@anthropic.com>"
```

### Task 2: The three verbs

**Files:**
- Modify: `src/ddd/declaration_plans.py` (append to what Task 1 wrote)
- Test: `tests/test_declaration_plans.py` (append)

**Interfaces:**
- Consumes: Task 1's `KINDS`, `SCOPES`, `CARRIED_BY_A_READER`, `INTERFACE`, `scopes_for`, `_component_of`; `ddd.editing.Operation`, `ddd.identity.new_id`, `ddd.lsp.navigation.rename_problem`, `ddd.lsp.units.PlannedEdit`.
- Produces: `DeclarationPlan`, `DeclarationRefusalError`, `read_object`, `declare_object`, `remove_declaration`, and the private `_statable`, `_interface` and `_appended`. Task 3 calls the three verbs and turns the refusal into a 404 or a 409.

- [ ] **Step 1: Write the failing tests**

```python
class TestReadingWhatTheProjectHas:
    def test_a_reader_carries_the_producer_s_definition_without_its_id_and_init(
        self, demo, cache, tmp_path
    ) -> None:
        # The rule this whole verb rests on, measured rather than assumed: across every
        # variable more than one component of examples/demo declares, a reader's definition is
        # the producer's less `id` and `init`, with nothing of its own.
        plan = read_object(demo, CONTROLLER, "ValueC", "input", cache)
        (edit,) = plan.edits
        (operation,) = edit.operations
        assert edit.path == CONTROLLER
        assert operation.op == "insert"
        assert operation.pointer == "component.interface[14]"
        written = json.loads(operation.raw or "")
        assert written["scope"] == "input"
        producer = json.loads(
            (EXAMPLES / "demo" / "components" / "sensor_hub.ddd.json").read_text(encoding="utf-8")
        )["component"]["interface"]
        stated = next(
            entry["definition"]
            for entry in producer
            if entry["definition"]["name"] == "ValueC"
        )
        assert written["definition"] == {
            key: value for key, value in stated.items() if key not in {"id", "init"}
        }

    def test_the_edit_writes_a_declaration_the_file_can_be_read_back_from(
        self, demo, cache
    ) -> None:
        # The layout is the edit engine's, not this module's: `insertion` lays a value out the
        # way the place it goes is laid out. Asserted by applying it and parsing the result.
        plan = read_object(demo, CONTROLLER, "ValueC", "input", cache)
        after = edit_text(CONTROLLER.read_text(encoding="utf-8"), plan.edits[0].operations)
        interface = json.loads(after)["component"]["interface"]
        assert len(interface) == 15
        assert interface[-1]["definition"]["name"] == "ValueC"
        assert '"name": "ValueC",\n' in after  # a key per line, as the file spells one

    def test_a_name_the_project_does_not_declare_is_not_found(self, demo, cache) -> None:
        with pytest.raises(DeclarationRefusalError) as refused:
            read_object(demo, CONTROLLER, "Nope", "input", cache)
        assert (refused.value.code, refused.value.message) == (
            "not-found",
            "the project declares no 'Nope'",
        )

    def test_a_name_this_component_already_declares_is_refused(self, demo, cache) -> None:
        with pytest.raises(DeclarationRefusalError) as refused:
            read_object(demo, CONTROLLER, "ValueA", "input", cache)
        assert refused.value.code == "invalid"
        assert refused.value.message == "this component already declares 'ValueA'"

    def test_a_scope_the_name_may_not_take_is_refused(self, demo, cache) -> None:
        # ValueC has a producer, so offering `output` here would make a multiple-producers.
        with pytest.raises(DeclarationRefusalError) as refused:
            read_object(demo, CONTROLLER, "ValueC", "output", cache)
        assert refused.value.message == "'ValueC' may not be declared 'output' here"

    def test_a_name_with_no_producer_is_read_from_the_declaration_there_is(
        self, tmp_path, cache
    ) -> None:
        # Nothing produces Orphan, so there is no producer's definition to carry - the one
        # declaration that does exist is what a second component reads it as.
        write_tree(
            tmp_path,
            {
                "p.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("input", "Orphan", unit="rpm")),
                "b.ddd.json": component("B"),
            },
        )
        built = index(load_workspace(tmp_path / "p.ddd.json", DiagnosticBag()))
        plan = read_object(built, tmp_path / "b.ddd.json", "Orphan", "input", cache)
        written = json.loads(plan.edits[0].operations[0].raw or "")
        assert written["definition"]["unit"] == "rpm"


class TestDeclaringSomethingNew:
    def test_a_producer_is_stamped_with_a_fresh_id_after_its_name(self, demo, cache) -> None:
        plan = declare_object(
            demo,
            CONTROLLER,
            "output",
            {"name": "Pressure", "kind": "measurement", "datatype": "uint16", "volatile": False},
            cache,
        )
        written = json.loads(plan.edits[0].operations[0].raw or "")
        assert list(written["definition"])[:2] == ["name", "id"]
        assert len(written["definition"]["id"]) == OBJECT_ID_LENGTH

    def test_a_reader_and_a_local_are_not_stamped(self, demo, cache) -> None:
        for scope in ("input", "local"):
            plan = declare_object(
                demo,
                CONTROLLER,
                scope,
                {"name": "Pressure", "kind": "measurement", "volatile": False},
                cache,
            )
            written = json.loads(plan.edits[0].operations[0].raw or "")
            assert "id" not in written["definition"]

    def test_a_name_the_project_refuses_is_refused_in_the_editor_s_own_words(
        self, demo, cache
    ) -> None:
        for name, why in (
            ("ValueA", "'ValueA' is already declared by this project"),
            ("int", "'int' is reserved by c or by a header DDD generates"),
            ("no spaces", "'no spaces' is not a usable c identifier"),
            (
                "STATE_OFF",
                "'STATE_OFF' is an enumerator of enum 'StateA_t', which shares c's namespace "
                "with the variables",
            ),
        ):
            with pytest.raises(DeclarationRefusalError) as refused:
                declare_object(
                    demo,
                    CONTROLLER,
                    "output",
                    {"name": name, "kind": "measurement", "volatile": False},
                    cache,
                )
            assert (refused.value.code, refused.value.message) == ("invalid", why)

    def test_a_kind_that_is_not_one_of_the_six_is_refused(self, demo, cache) -> None:
        with pytest.raises(DeclarationRefusalError) as refused:
            declare_object(
                demo, CONTROLLER, "output", {"name": "Pressure", "kind": "signal"}, cache
            )
        assert refused.value.message == (
            "'signal' is not a kind: measurement, parameter, value_block, curve, map, axis"
        )

    def test_a_definition_without_a_name_or_a_kind_is_refused(self, demo, cache) -> None:
        for definition in ({"kind": "measurement"}, {"name": "Pressure"}, {"name": 4}):
            with pytest.raises(DeclarationRefusalError) as refused:
                declare_object(demo, CONTROLLER, "output", definition, cache)
            assert refused.value.message == "a definition states a 'name' and a 'kind'"

    def test_a_scope_that_is_not_one_of_the_three_is_refused(self, demo, cache) -> None:
        with pytest.raises(DeclarationRefusalError) as refused:
            declare_object(
                demo,
                CONTROLLER,
                "sideways",
                {"name": "Pressure", "kind": "measurement", "volatile": False},
                cache,
            )
        assert refused.value.message == "'sideways' is not a scope: output, input, local"

    def test_a_required_key_left_out_is_refused_before_a_file_is_written(
        self, demo, cache
    ) -> None:
        with pytest.raises(DeclarationRefusalError) as refused:
            declare_object(
                demo,
                CONTROLLER,
                "output",
                {"name": "Pressure", "kind": "value_block", "volatile": False},
                cache,
            )
        assert refused.value.message == "a value_block must state 'dimensions'"

    def test_a_key_the_kind_has_not_is_refused(self, demo, cache) -> None:
        with pytest.raises(DeclarationRefusalError) as refused:
            declare_object(
                demo,
                CONTROLLER,
                "output",
                {"name": "Pressure", "kind": "parameter", "volatile": False, "size": 4},
                cache,
            )
        assert refused.value.message == "a parameter has no 'size' to state"

    def test_an_id_sent_by_the_page_is_refused_rather_than_written(self, demo, cache) -> None:
        # The server mints it, so a client that states one is either confused or forging an
        # identity another object already carries.
        with pytest.raises(DeclarationRefusalError) as refused:
            declare_object(
                demo,
                CONTROLLER,
                "output",
                {"name": "Pressure", "kind": "measurement", "volatile": False, "id": "aaaaaaaaaaaa"},
                cache,
            )
        assert refused.value.message == "an id is this server's to mint, not the page's"

    def test_what_is_written_parses_and_loads(self, demo, cache, tmp_path) -> None:
        # The end of the verb's promise: a file the loader reads back without a complaint.
        plan = declare_object(
            demo,
            CONTROLLER,
            "output",
            {
                "name": "Pressure",
                "kind": "axis",
                "description": "Declared from the interface",
                "datatype": "uint16",
                "size": 8,
                "volatile": False,
            },
            cache,
        )
        after = edit_text(CONTROLLER.read_text(encoding="utf-8"), plan.edits[0].operations)
        written = tmp_path / "demo"
        shutil.copytree(EXAMPLES / "demo", written)
        (written / "components" / "controller.ddd.json").write_text(after, encoding="utf-8")
        bag = DiagnosticBag()
        load_workspace(written / "demo.ddd.json", bag)
        # A pristine examples/demo loads with nothing reported, so anything here is this
        # declaration's doing. `DiagnosticBag.sorted()` is how a bag is read.
        assert [finding.check for finding in bag.sorted()] == []


class TestRemovingADeclaration:
    def test_the_declaration_goes_and_the_rest_stay(self, demo, cache) -> None:
        plan = remove_declaration(demo, CONTROLLER, "ValueA", cache)
        (edit,) = plan.edits
        assert edit.operations == (Operation("remove", "component.interface[0]"),)
        after = edit_text(CONTROLLER.read_text(encoding="utf-8"), edit.operations)
        names = [
            entry["definition"]["name"] for entry in json.loads(after)["component"]["interface"]
        ]
        assert len(names) == 13
        assert "ValueA" not in names

    def test_a_name_this_file_does_not_declare_is_not_found(self, demo, cache) -> None:
        with pytest.raises(DeclarationRefusalError) as refused:
            remove_declaration(demo, CONTROLLER, "ValueI", cache)
        assert (refused.value.code, refused.value.message) == (
            "not-found",
            "controller.ddd.json declares no 'ValueI'",
        )

    def test_a_file_with_no_interface_is_not_found(self, tmp_path, cache) -> None:
        # A project file rather than a component: it has no `component.interface` to change,
        # and the endpoint's own guard is a component check, so this is what reaching here
        # with the wrong file answers.
        write_tree(tmp_path, {"p.ddd.json": project("P")})
        built = index(load_workspace(tmp_path / "p.ddd.json", DiagnosticBag()))
        with pytest.raises(DeclarationRefusalError) as refused:
            remove_declaration(built, tmp_path / "p.ddd.json", "ValueA", cache)
        assert refused.value.code == "not-found"
        assert refused.value.message == "p.ddd.json declares no interface"
```

Add to the test file's imports:

```python
import json
import shutil

from ddd.declaration_plans import (
    DeclarationRefusalError,
    declare_object,
    read_object,
    remove_declaration,
)
from ddd.editing import Operation, edit_text
from ddd.identity import OBJECT_ID_LENGTH
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/test_declaration_plans.py -q --no-cov`
Expected: FAIL, `ImportError: cannot import name 'read_object' from 'ddd.declaration_plans'`.

- [ ] **Step 3: Write the three verbs**

Append to `src/ddd/declaration_plans.py`:

```python
@dataclass(frozen=True, slots=True)
class DeclarationPlan:
    """Everything one change of an interface takes: one edit per file, sorted by path.

    One file, always, as it happens - a declaration is written into the component that makes
    it, and nothing else moves - but the shape is :class:`~ddd.type_plans.TypePlan`'s so that
    :func:`ddd.project_units.previewed` previews all three tabs' plans.
    """

    edits: tuple[PlannedEdit, ...]


class DeclarationRefusalError(Exception):
    """A change of an interface that cannot be planned, and the code both clients refuse with."""

    code: Literal["invalid", "not-found"]
    """``invalid``: the change cannot be made - a name that may not be used, a key the kind has
    not, a required key left out, a scope this name may not take. ``not-found``: the file
    declares no interface, or no declaration of that name."""

    message: str
    """The sentence the refusal is shown with."""

    def __init__(self, code: Literal["invalid", "not-found"], message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def read_object(
    built: Index, file: Path, name: str, scope: str, cache: dict[Path, Document]
) -> DeclarationPlan:
    """What reading an object the project already has takes.

    One ``insert`` appending a declaration that carries the producer's own definition, less
    :data:`CARRIED_BY_A_READER` - which is what makes the new reader agree with its producer by
    construction rather than by a later check. A name nothing produces is read from the one
    declaration there is: there is no owner's definition to copy, and the alternative is
    refusing the very repair the reader came for.
    """
    here, entries = _interface(file, cache)
    sites = built.declarations.get(name)
    if not sites:
        raise DeclarationRefusalError("not-found", f"the project declares no '{name}'")
    if any(site.path == here for site in sites):
        raise DeclarationRefusalError("invalid", f"this component already declares '{name}'")
    if scope not in scopes_for(built, name):
        raise DeclarationRefusalError("invalid", f"'{name}' may not be declared '{scope}' here")
    owner = (built.producers.get(name) or sites)[0]
    stated = read(owner.path, cache).value_at(owner.pointer)
    if not isinstance(stated, dict):
        raise DeclarationRefusalError("not-found", f"the project declares no '{name}'")
    definition = {key: value for key, value in stated.items() if key not in CARRIED_BY_A_READER}
    return _appended(here, entries, scope, definition)


def declare_object(
    built: Index,
    file: Path,
    scope: str,
    definition: Mapping[str, object],
    cache: dict[Path, Document],
) -> DeclarationPlan:
    """What declaring a new object takes: one ``insert`` appending the definition given.

    Refused before a file is touched for a name the project may not use, in
    :func:`~ddd.lsp.navigation.rename_problem`'s own sentence - a new declaration lands in the
    namespace a rename guards, so it gets the same answers rather than a second set derived
    here. A producing declaration is stamped with a fresh id, after its ``name``, where every
    stamped declaration of the examples carries one.
    """
    here, entries = _interface(file, cache)
    name, kind = definition.get("name"), definition.get("kind")
    if not isinstance(name, str) or not isinstance(kind, str):
        raise DeclarationRefusalError("invalid", "a definition states a 'name' and a 'kind'")
    if kind not in KINDS:
        raise DeclarationRefusalError("invalid", f"'{kind}' is not a kind: {', '.join(KINDS)}")
    if scope not in SCOPES:
        raise DeclarationRefusalError("invalid", f"'{scope}' is not a scope: {', '.join(SCOPES)}")
    problem = rename_problem(built, name)
    if problem is not None:
        raise DeclarationRefusalError("invalid", problem)
    if "id" in definition:
        raise DeclarationRefusalError("invalid", "an id is this server's to mint, not the page's")
    if extra := sorted(set(definition) - _statable(kind)):
        raise DeclarationRefusalError("invalid", f"a {kind} has no '{extra[0]}' to state")
    _, required = definition_keys(kind)
    if missing := sorted(required - set(definition)):
        raise DeclarationRefusalError("invalid", f"a {kind} must state '{missing[0]}'")
    stated = dict(definition)
    if scope == "output":
        stated = {"name": stated.pop("name"), "id": new_id(), **stated}
    return _appended(here, entries, scope, stated)


def remove_declaration(
    built: Index, file: Path, name: str, cache: dict[Path, Document]
) -> DeclarationPlan:
    """What removing a declaration takes: one ``remove`` at its index in the interface.

    ``built`` is unread - the index says which components declare a name, and this needs the
    index *of this file*, which its own text is. It is taken all the same so that the three
    verbs are called the same way, and so that a later rule about the project can be added here
    without changing every caller.
    """
    here, entries = _interface(file, cache)
    document = read(here, cache)
    for position in range(len(entries)):
        if document.value_at(f"{INTERFACE}[{position}].definition.name") == name:
            operation = Operation("remove", f"{INTERFACE}[{position}]")
            return DeclarationPlan((PlannedEdit(here, (operation,)),))
    raise DeclarationRefusalError("not-found", f"{here.name} declares no '{name}'")


def _statable(kind: str) -> frozenset[str]:
    """What a definition sent here may state: what the form can offer, and nothing else.

    ``definition_keys`` accepts more - ``id``, ``init``, ``a2l``, ``extensions``, ``raster``
    and ``section`` among them. The form offers none of those: ``id`` is this module's to mint,
    and the rest belong to whoever writes the file by hand.
    """
    accepted, _ = definition_keys(kind)
    return frozenset({"name", "kind", "description"}) | (accepted & frozenset(KEY_ORDER))


def _interface(file: Path, cache: dict[Path, Document]) -> tuple[Path, list[object]]:
    """The file resolved, and the declarations it holds."""
    here = file.resolve()
    entries = read(here, cache).value_at(INTERFACE)
    if not isinstance(entries, list):
        raise DeclarationRefusalError("not-found", f"{here.name} declares no interface")
    return here, entries


def _appended(
    here: Path, entries: list[object], scope: str, definition: Mapping[str, object]
) -> DeclarationPlan:
    """The plan that appends one declaration: an ``insert`` at the end of the interface."""
    raw = json.dumps({"scope": scope, "definition": definition})
    operation = Operation("insert", f"{INTERFACE}[{len(entries)}]", raw)
    return DeclarationPlan((PlannedEdit(here, (operation,)),))
```

`remove_declaration`'s unused `built` needs ruff's blessing: name it `_built` if ARG002 fires, and say why in the docstring as written above.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_declaration_plans.py -q --no-cov`
Expected: PASS, 27 tests - Task 1's 8 and this task's 19.

- [ ] **Step 5: Run the gate**

Run: `python -m pytest -q && ruff check . && ruff format --check . && mypy`
Expected: 100 % line and branch coverage over `src/ddd/declaration_plans.py`, all checks pass.

- [ ] **Step 6: Commit**

```bash
git add src/ddd/declaration_plans.py tests/test_declaration_plans.py
git commit -m "plan reading, declaring and removing a declaration

Co-Authored-By: <model that wrote it> <noreply@anthropic.com>"
```

### Task 3: The contract and the two endpoints

**Files:**
- Modify: `src/ddd/gui/contract.py` (models, and `_ENDPOINTS` near line 1064), `src/ddd/gui/api.py` (two handlers, and `_ROUTES` near line 755)
- Test: `tests/test_gui_api.py`, `tests/test_gui_server.py`

**Interfaces:**
- Consumes: Task 1's `declarable`, `scopes_for`, `form_for`, `KINDS`, `SCOPES`; Task 2's three verbs and `DeclarationRefusalError`. From the api's own file: `_single`, `_error`, `_opened`, `Reply`, `Query`, `previewed`, `UNREADABLE`, `REFUSALS`, and `ddd.gui.session._source`'s `NotInProjectError`.
- Produces: `DeclarableName`, `KindForm`, `DeclarableReply`; `GET /api/declarable` and `GET /api/declaration-plan`. Task 4 generates the page's types from them.

- [ ] **Step 1: Write the failing tests**

In `tests/test_gui_api.py`, using the file's own harness - `copied(tmp_path, "demo", "demo.ddd.json")` for a writable copy, `get(api, path, **query)` for a request, `applied(api, preview, label)` to post one, and `contents(root)` to prove nothing was written:

```python
class TestWhatAComponentMayAdd:
    @pytest.fixture
    def demo(self, tmp_path: Path) -> tuple[Api, Path]:
        return copied(tmp_path, "demo", "demo.ddd.json")

    def controller(self, root: Path) -> str:
        return (root / "components" / "controller.ddd.json").as_posix()

    def test_the_names_it_may_read_come_with_their_producer_and_scopes(self, demo) -> None:
        api, root = demo
        body = get(api, "/api/declarable", file=self.controller(root)).body
        names = {entry["name"]: entry for entry in body["names"]}
        # Measured against examples/demo: Controller declares 14 of the project's 23 names.
        assert sorted(names) == [
            "BlockA", "CurveB", "Diagnosis", "FlagA",
            "ValueC", "ValueD", "ValueI", "ValueJ", "ValueK",
        ]
        assert (names["ValueC"]["producer"], names["ValueC"]["kind"]) == ("SensorHub", "measurement")
        # Every one of them is produced by something, so reading is all any of them may be.
        assert names["ValueC"]["scopes"] == ["input"]

    def test_the_kinds_carry_the_form_each_one_asks_for(self, demo) -> None:
        api, root = demo
        body = get(api, "/api/declarable", file=self.controller(root)).body
        forms = {entry["kind"]: entry for entry in body["kinds"]}
        assert list(forms) == ["measurement", "parameter", "value_block", "curve", "map", "axis"]
        required = {
            key["key"] for key in forms["value_block"]["keys"] if key["carried"][0]["required"]
        }
        assert required == {"volatile", "dimensions"}
        editors = {key["key"]: key["editor"] for key in forms["axis"]["keys"]}
        assert (editors["size"], editors["unit"], editors["input"]) == ("size", "unit", "name")

    def test_a_name_the_project_has_never_seen_may_take_any_scope(self, demo) -> None:
        api, root = demo
        body = get(api, "/api/declarable", file=self.controller(root)).body
        assert body["scopes"] == ["output", "input", "local"]

    def test_without_a_file_it_says_so(self, demo) -> None:
        api, _ = demo
        reply = get(api, "/api/declarable")
        assert (reply.status, reply.body["error"]) == (400, "bad-request")
        assert reply.body["message"] == "declarable takes ?file="

    def test_a_file_outside_the_project_is_not_found(self, demo, tmp_path) -> None:
        api, _ = demo
        reply = get(api, "/api/declarable", file=(tmp_path / "x.ddd.json").as_posix())
        assert (reply.status, reply.body["error"]) == (404, "not-found")

    def test_a_file_of_the_project_that_is_not_a_component_is_refused(self, demo) -> None:
        api, root = demo
        reply = get(api, "/api/declarable", file=(root / "demo.ddd.json").as_posix())
        assert (reply.status, reply.body["error"]) == (409, "invalid")
        assert reply.body["message"] == "demo.ddd.json is not a component of the open project"

    def test_a_project_that_did_not_load_offers_nothing_to_add_to(self, tmp_path) -> None:
        # Measured: `unloaded` leaves one file in the revision, p.ddd.json, kind "project" and
        # loaded False - so it passes the project check and fails the component one.
        api = unloaded(tmp_path)
        reply = get(api, "/api/declarable", file=(tmp_path / "p.ddd.json").as_posix())
        assert (reply.status, reply.body["error"]) == (409, "invalid")
        assert reply.body["message"] == "p.ddd.json is not a component of the open project"


class TestPlanningAChangeOfAnInterface:
    @pytest.fixture
    def demo(self, tmp_path: Path) -> tuple[Api, Path]:
        return copied(tmp_path, "demo", "demo.ddd.json")

    def controller(self, root: Path) -> str:
        return (root / "components" / "controller.ddd.json").as_posix()

    def test_reading_a_variable_is_previewed_then_written(self, demo) -> None:
        api, root = demo
        before = contents(root)
        preview = get(
            api,
            "/api/declaration-plan",
            action="read",
            file=self.controller(root),
            name="ValueC",
            scope="input",
        ).body
        assert contents(root) == before  # a plan writes nothing
        assert [Path(change["file"]).name for change in preview["changes"]] == [
            "controller.ddd.json"
        ]
        assert applied(api, preview, "reading ValueC").status == 200
        written = (root / "components" / "controller.ddd.json").read_text(encoding="utf-8")
        assert '"name": "ValueC"' in written

    def test_declaring_a_new_object_takes_the_definition_as_json(self, demo) -> None:
        api, root = demo
        definition = json.dumps(
            {"name": "Pressure", "kind": "measurement", "datatype": "uint16", "volatile": False}
        )
        preview = get(
            api,
            "/api/declaration-plan",
            action="declare",
            file=self.controller(root),
            scope="output",
            definition=definition,
        ).body
        assert len(preview["changes"]) == 1
        assert applied(api, preview, "declaring Pressure").status == 200
        written = (root / "components" / "controller.ddd.json").read_text(encoding="utf-8")
        assert '"name": "Pressure"' in written and '"id"' in written

    def test_removing_a_declaration_previews_its_going(self, demo) -> None:
        api, root = demo
        preview = get(
            api,
            "/api/declaration-plan",
            action="remove",
            file=self.controller(root),
            name="ValueA",
        ).body
        removed = [
            line["text"]
            for change in preview["changes"]
            for hunk in change["hunks"]
            for line in hunk["lines"]
            if line["kind"] == "removed"
        ]
        assert any('"name": "ValueA"' in text for text in removed)
        assert applied(api, preview, "removing ValueA").status == 200
        written = (root / "components" / "controller.ddd.json").read_text(encoding="utf-8")
        assert '"name": "ValueA"' not in written

    def test_an_action_that_is_not_one_of_the_three_says_which_are(self, demo) -> None:
        api, _ = demo
        reply = get(api, "/api/declaration-plan", action="invent")
        assert (reply.status, reply.body["error"]) == (400, "bad-request")
        assert reply.body["message"] == (
            "declaration-plan takes ?action= one of read, declare, remove"
        )

    def test_an_action_missing_a_parameter_says_which_it_takes(self, demo) -> None:
        api, root = demo
        reply = get(api, "/api/declaration-plan", action="read", file=self.controller(root))
        assert reply.status == 400
        assert reply.body["message"] == "read takes ?file= and ?name= and ?scope="

    @pytest.mark.parametrize("definition", ["{not json", "[1, 2]"])
    def test_a_definition_that_is_not_a_json_object_is_refused(self, demo, definition) -> None:
        api, root = demo
        reply = get(
            api,
            "/api/declaration-plan",
            action="declare",
            file=self.controller(root),
            scope="output",
            definition=definition,
        )
        assert (reply.status, reply.body["error"]) == (409, "invalid")
        assert reply.body["message"] == "the definition is not json"

    def test_a_refusal_carries_the_module_s_own_code_and_sentence(self, demo) -> None:
        api, root = demo
        reply = get(
            api,
            "/api/declaration-plan",
            action="read",
            file=self.controller(root),
            name="ValueA",
            scope="input",
        )
        assert (reply.status, reply.body["error"]) == (409, "invalid")
        assert reply.body["message"] == "this component already declares 'ValueA'"

    def test_a_name_the_project_has_not_is_not_found(self, demo) -> None:
        api, root = demo
        reply = get(
            api,
            "/api/declaration-plan",
            action="read",
            file=self.controller(root),
            name="Nope",
            scope="input",
        )
        assert (reply.status, reply.body["error"]) == (404, "not-found")

    def test_a_file_outside_the_project_is_not_found(self, demo, tmp_path) -> None:
        api, _ = demo
        reply = get(
            api,
            "/api/declaration-plan",
            action="remove",
            file=(tmp_path / "x.ddd.json").as_posix(),
            name="ValueA",
        )
        assert (reply.status, reply.body["error"]) == (404, "not-found")

    def test_a_project_that_did_not_load_has_nothing_to_plan_against(self, tmp_path) -> None:
        # The answer /api/type-plan already gives: measured, `unloaded`'s revision has
        # `index is None` and one file, p.ddd.json, which `_source` accepts - so the guard that
        # answers here is the missing index, not the missing file.
        api = unloaded(tmp_path)
        reply = get(
            api,
            "/api/declaration-plan",
            action="remove",
            file=(tmp_path / "p.ddd.json").as_posix(),
            name="ValueA",
        )
        assert (reply.status, reply.body["error"]) == (409, "unreadable")
```

In `tests/test_gui_server.py`, inside `TestEveryEndpointOnTheDemo`, so both go through real HTTP:

```python
    def test_the_declarable_names_and_a_plan_of_one(self, demo) -> None:
        server, root = demo
        controller = (root / "components" / "controller.ddd.json").as_posix()
        answer = answered(server, "GET", f"/api/declarable?file={quote(controller)}")
        assert [entry["name"] for entry in answer["names"]][:2] == ["BlockA", "CurveB"]
        assert [form["kind"] for form in answer["kinds"]][0] == "measurement"
        planned = answered(
            server,
            "GET",
            f"/api/declaration-plan?action=read&file={quote(controller)}&name=ValueC&scope=input",
        )
        assert len(planned["changes"]) == 1
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/test_gui_api.py -k "MayAdd or PlanningAChange" tests/test_gui_server.py -k declarable -q --no-cov`
Expected: FAIL - the routes answer 404 with `"error": "not-found"`.

- [ ] **Step 3: Write the models**

In `src/ddd/gui/contract.py`, after the `GET /api/type-plan` section:

```python
# --- GET /api/declarable ---------------------------------------------------------------------


class DeclarableName(_Frozen):
    """One variable a component could read, as its name field offers it."""

    name: str
    kind: str
    """``measurement`` … ``axis``, or empty when no declaration of it states one."""

    producer: str | None
    """The component producing it; ``null`` when nothing does."""

    scopes: tuple[str, ...]
    """Which scopes this name may be declared with here, in the form's own order: reading
    always, producing only while nothing produces it, and never a local beside another
    declaration."""


class KindForm(_Frozen):
    """What one kind of object asks for when it is declared new."""

    kind: str
    keys: tuple[VariableKeyOffer, ...]
    """One offer per key the kind accepts, with no value in play: the same shape a variable's
    panel draws, so one chooser draws both."""


class DeclarableReply(_Frozen):
    """What ``GET /api/declarable`` answers: what this component may add to its interface."""

    revision: int
    file: str
    """Absolute, posix-separated path of the component asked about."""

    names: tuple[DeclarableName, ...]
    kinds: tuple[KindForm, ...]
    scopes: tuple[str, ...]
    """What a name the project has never seen may be declared with."""
```

and add `(DeclarableReply, "serialization"),` to `_ENDPOINTS` after `(TypeReply, "serialization"),`.

- [ ] **Step 4: Write the two handlers**

In `src/ddd/gui/api.py`:

```python
    def _declarable(self, query: Query, body: bytes | None) -> Reply:
        path = _single(query.get("file"))
        if not path:
            return _error(400, "bad-request", "declarable takes ?file=")
        revision = self._opened()
        try:
            file = _source(revision, Path(path))
        except NotInProjectError as outside:
            return _error(404, "not-found", str(outside))
        if not any(entry.path == file and entry.kind == "component" for entry in revision.files):
            return _error(
                409, "invalid", f"{file.name} is not a component of the open project"
            )
        built = revision.index
        if built is None:
            return _error(409, UNREADABLE, _NOTHING_LOADED)
        cache: dict[Path, Document] = {}
        return Reply(
            200,
            contract.DeclarableReply(
                revision=revision.number,
                file=file.as_posix(),
                names=tuple(
                    contract.DeclarableName(
                        name=entry.name,
                        kind=entry.kind,
                        producer=entry.producer,
                        scopes=scopes_for(built, entry.name),
                    )
                    for entry in declarable(built, file, cache)
                ),
                kinds=tuple(
                    # `asdict`, exactly as `_variable` already converts its offers: the
                    # dataclasses of `ddd.variable_keys` are the contract's models field for
                    # field, and the contract validates what comes out, so a name that drifts
                    # apart fails here rather than reaching the page.
                    contract.KindForm(
                        kind=kind, keys=[asdict(offer) for offer in form_for(built, kind)]
                    )
                    for kind in KINDS
                ),
                scopes=SCOPES,
            ).model_dump(mode="json"),
        )

    def _declaration_plan(self, query: Query, body: bytes | None) -> Reply:
        action = _single(query.get("action")) or ""
        takes = DECLARATION_PLANS.get(action)
        if takes is None:
            return _error(
                400,
                "bad-request",
                f"declaration-plan takes ?action= one of {', '.join(DECLARATION_PLANS)}",
            )
        given = {part: value for part in takes if (value := _single(query.get(part))) is not None}
        if len(given) < len(takes):
            wanted = " and ".join(f"?{part}=" for part in takes)
            return _error(400, "bad-request", f"{action} takes {wanted}")
        revision = self._opened()
        try:
            file = _source(revision, Path(given["file"]))
        except NotInProjectError as outside:
            return _error(404, "not-found", str(outside))
        built = revision.index
        if built is None:
            return _error(409, UNREADABLE, _NOTHING_LOADED)
        cache: dict[Path, Document] = {}
        try:
            plan = _declaration_plan_of(action, built, file, given, cache)
        except DeclarationRefusalError as refused:
            status = 404 if refused.code == "not-found" else 409
            return _error(status, refused.code, refused.message)
        stamps = {entry.path.resolve(): entry.fingerprint for entry in revision.files}
        try:
            planned = previewed(plan.edits, stamps)
        except EditError as refused:
            return _error(409 if refused.code in REFUSALS else 500, refused.code, str(refused))
        return Reply(
            200,
            contract.PlanReply(revision=revision.number, changes=planned).model_dump(mode="json"),
        )
```

and, beside the module's other helpers:

```python
DECLARATION_PLANS: Final[Mapping[str, tuple[str, ...]]] = {
    "read": ("file", "name", "scope"),
    "declare": ("file", "scope", "definition"),
    "remove": ("file", "name"),
}
"""Which query parameters each action of ``GET /api/declaration-plan`` takes."""

_NOTHING_LOADED: Final = (
    "the open project did not load, so no interface of it can be changed"
)


def _declaration_plan_of(
    action: str,
    built: Index,
    file: Path,
    given: Mapping[str, str],
    cache: dict[Path, Document],
) -> DeclarationPlan:
    if action == "read":
        return read_object(built, file, given["name"], given["scope"], cache)
    if action == "remove":
        return remove_declaration(built, file, given["name"], cache)
    try:
        definition = json.loads(given["definition"])
    except json.JSONDecodeError as malformed:
        raise DeclarationRefusalError("invalid", "the definition is not json") from malformed
    if not isinstance(definition, dict):
        raise DeclarationRefusalError("invalid", "the definition is not json")
    return declare_object(built, file, given["scope"], definition, cache)
```

Register both in `_ROUTES`:

```python
    "/api/declarable": {"GET": Api._declarable},
    "/api/declaration-plan": {"GET": Api._declaration_plan},
```

There is no converter to write: `_variable` already passes `keys=[asdict(offer) for offer in offers(built, declared)]` (`src/ddd/gui/api.py:408`), because the dataclasses of `ddd.variable_keys` are the contract's models field for field. `asdict` is already imported there. Add to the imports of `api.py`: `from ddd.declaration_plans import KINDS, SCOPES, DeclarationPlan, DeclarationRefusalError, declarable, declare_object, form_for, read_object, remove_declaration, scopes_for` and, from `ddd.gui.session`, `NotInProjectError` and `_source` if they are not already there (`_variable` and `_file` use them).

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/test_gui_api.py tests/test_gui_server.py tests/test_gui_contract.py -q --no-cov`
Expected: PASS. `test_every_model_declared_here_has_a_defs_entry` passes because `DeclarableReply` is in `_ENDPOINTS`; `DeclarableName`, `KindForm` and `VariableKeyOffer` are reached through it.

- [ ] **Step 6: Run the gate and regenerate the page's types**

```bash
python -m pytest -q && ruff check . && ruff format --check . && mypy
cd gui && npm run schemas && git diff --stat src/api/types.ts
```

Expected: 100 % coverage and no issues; `npm run schemas` leaves `gui/src/generated/api.ts` (git-ignored) holding `DeclarableReply`. `gui/src/api/types.ts` is **not** touched here - Task 4 re-exports the new names.

- [ ] **Step 7: Commit**

```bash
git add src/ddd/gui/contract.py src/ddd/gui/api.py tests/test_gui_api.py tests/test_gui_server.py
git commit -m "answer what a component may add, and plan a change of it

Co-Authored-By: <model that wrote it> <noreply@anthropic.com>"
```

### Task 4: The page reads what may be added

**Files:**
- Modify: `gui/src/api/types.ts`, `gui/src/api/client.ts`
- Create: `gui/src/lib/declarations.ts`, `gui/src/lib/declarations.test.ts`

**Interfaces:**
- Consumes: Task 3's `DeclarableReply`, `DeclarableName`, `KindForm`, and the existing `PlanReply` and `VariableKeyOffer`.
- Produces: `getDeclarable`, `DeclarationPlanRequest`, `getDeclarationPlan`, and the pure functions of `gui/src/lib/declarations.ts` that Tasks 6 and 8 draw with.

- [ ] **Step 1: Regenerate and re-export the types**

```bash
cd gui && npm run schemas
```

Add `DeclarableName`, `DeclarableReply` and `KindForm` to the `export type { … }` list of `gui/src/api/types.ts`, **sorted case-insensitively** with the rest: they land between `Change` and `EditReply` as `DeclarableName`, `DeclarableReply`, then later `KindForm` after `Hunk`.

- [ ] **Step 2: Write the client's two functions**

In `gui/src/api/client.ts`, beside `getTypePlan`:

```ts
export const getDeclarable = (file: string, fetchImpl: Fetch = fetch) =>
  request<DeclarableReply>(`/api/declarable?file=${encodeURIComponent(file)}`, {}, fetchImpl);

/** One change to a component's interface, as `GET /api/declaration-plan` takes it. */
export type DeclarationPlanRequest =
  | { action: "read"; file: string; name: string; scope: string }
  | { action: "declare"; file: string; scope: string; definition: string }
  | { action: "remove"; file: string; name: string };

export const getDeclarationPlan = (plan: DeclarationPlanRequest, fetchImpl: Fetch = fetch) =>
  request<PlanReply>(`/api/declaration-plan?${declarationQuery(plan)}`, {}, fetchImpl);

/** A plan's query: the action and the file, then whichever of `name`, `scope` and `definition`
 * the action takes - the same three sets the server's DECLARATION_PLANS names. */
function declarationQuery(plan: DeclarationPlanRequest): string {
  const parts: [string, string][] = [
    ["action", plan.action],
    ["file", plan.file],
  ];
  if (plan.action === "read") parts.push(["name", plan.name], ["scope", plan.scope]);
  else if (plan.action === "remove") parts.push(["name", plan.name]);
  else parts.push(["scope", plan.scope], ["definition", plan.definition]);
  return parts.map(([key, value]) => `${key}=${encodeURIComponent(value)}`).join("&");
}
```

Add the two calls to `gui/src/api/client.test.ts`'s existing "every request is spelled the way the server reads it" table, which asserts the exact paths:

```ts
      ["/api/declarable?file=%2Ftmp%2Fc.ddd.json", { credentials: "same-origin" }],
      [
        "/api/declaration-plan?action=read&file=%2Ftmp%2Fc.ddd.json&name=ValueC&scope=input",
        { credentials: "same-origin" },
      ],
      [
        "/api/declaration-plan?action=remove&file=%2Ftmp%2Fc.ddd.json&name=ValueA",
        { credentials: "same-origin" },
      ],
      [
        "/api/declaration-plan?action=declare&file=%2Ftmp%2Fc.ddd.json&scope=output&definition=%7B%22name%22%3A%22P%22%7D",
        { credentials: "same-origin" },
      ],
```

- [ ] **Step 3: Write the failing tests for the form's logic**

`gui/src/lib/declarations.test.ts`:

```ts
import { describe, expect, test } from "vitest";
import type { DeclarableReply } from "../api/types";
import {
  chosenName,
  declareSentence,
  definitionOf,
  dimensionsRaw,
  keysOf,
  modeOf,
  scopesOf,
} from "./declarations";

function offer(key: string, required: boolean, editor = "none") {
  return {
    key,
    carried: [{ allowed: true, required }],
    values: [],
    disagrees: false,
    editor,
    choices: [],
  };
}

const REPLY: DeclarableReply = {
  revision: 3,
  file: "/p/components/controller.ddd.json",
  names: [
    { name: "ValueC", kind: "measurement", producer: "SensorHub", scopes: ["input"] },
    { name: "Orphan", kind: "measurement", producer: null, scopes: ["output", "input"] },
  ],
  kinds: [
    { kind: "measurement", keys: [offer("unit", false, "unit"), offer("volatile", true, "volatile")] },
    {
      kind: "value_block",
      keys: [offer("dimensions", true), offer("volatile", true, "volatile")],
    },
  ],
  scopes: ["output", "input", "local"],
} as DeclarableReply;

describe("which of the two verbs the name field has landed on", () => {
  test("nothing typed has landed on neither", () => {
    expect(modeOf("", REPLY.names)).toBe("unchosen");
  });

  test("a name the project declares is read", () => {
    expect(modeOf("ValueC", REPLY.names)).toBe("read");
    expect(chosenName("ValueC", REPLY.names)?.producer).toBe("SensorHub");
  });

  test("a name it does not is declared", () => {
    expect(modeOf("Pressure", REPLY.names)).toBe("declare");
    expect(chosenName("Pressure", REPLY.names)).toBeNull();
  });
});

describe("which scopes a name may take", () => {
  test("a listed name's are the server's answer for it", () => {
    expect(scopesOf("ValueC", REPLY)).toEqual(["input"]);
    expect(scopesOf("Orphan", REPLY)).toEqual(["output", "input"]);
  });

  test("a new name may take all three", () => {
    expect(scopesOf("Pressure", REPLY)).toEqual(["output", "input", "local"]);
  });
});

describe("what a kind asks for", () => {
  test("required keys come first, in the server's order within each group", () => {
    expect(keysOf("measurement", REPLY).map((key) => key.key)).toEqual(["volatile", "unit"]);
  });

  test("a kind the reply does not carry asks for nothing", () => {
    expect(keysOf("nonsense", REPLY)).toEqual([]);
  });
});

describe("the definition the form has made", () => {
  test("it is json with the name and the kind in it", () => {
    const raw = definitionOf("Pressure", "measurement", { volatile: "false" }, REPLY);
    expect(JSON.parse(raw ?? "")).toEqual({
      name: "Pressure",
      kind: "measurement",
      volatile: false,
    });
  });

  test("a stated optional key joins it", () => {
    const raw = definitionOf("Pressure", "measurement", { volatile: "false", unit: '"%"' }, REPLY);
    expect(JSON.parse(raw ?? "")).toEqual({
      name: "Pressure",
      kind: "measurement",
      volatile: false,
      unit: "%",
    });
  });

  test("a required key left unstated makes no definition at all", () => {
    expect(definitionOf("Pressure", "measurement", {}, REPLY)).toBeNull();
  });

  test("a value that is not json makes none either", () => {
    expect(definitionOf("Pressure", "measurement", { volatile: "maybe" }, REPLY)).toBeNull();
  });

  test("a name or a kind left empty makes none", () => {
    expect(definitionOf("", "measurement", { volatile: "false" }, REPLY)).toBeNull();
    expect(definitionOf("Pressure", "", { volatile: "false" }, REPLY)).toBeNull();
  });
});

describe("the dimensions a row of fields makes", () => {
  test("a whole number is a number and anything else is a constant's name", () => {
    expect(dimensionsRaw(["4", "CELLS"])).toBe('[4,"CELLS"]');
  });

  test("no rows at all state nothing", () => {
    expect(dimensionsRaw([])).toBeNull();
  });

  test("a blank row states nothing, because a value block is never a scalar", () => {
    expect(dimensionsRaw(["4", ""])).toBeNull();
  });
});

describe("the sentence that tells reading from declaring", () => {
  test("a listed name names its producer", () => {
    expect(declareSentence("ValueC", "", "input", REPLY)).toBe(
      "Reads ValueC as SensorHub declares it.",
    );
  });

  test("a listed name nothing produces says so", () => {
    expect(declareSentence("Orphan", "", "input", REPLY)).toBe(
      "Reads Orphan as this project declares it.",
    );
  });

  test("a new name names the kind and the scope", () => {
    expect(declareSentence("Pressure", "measurement", "output", REPLY)).toBe(
      "Declares Pressure, a measurement this component produces.",
    );
  });

  test("nothing typed asks for a name", () => {
    expect(declareSentence("", "", "input", REPLY)).toBe("Choose a variable, or type a new name.");
  });
});
```

- [ ] **Step 4: Run them to verify they fail**

Run: `cd gui && npx vitest run src/lib/declarations.test.ts`
Expected: FAIL, `Failed to resolve import "./declarations"`.

- [ ] **Step 5: Write the module**

`gui/src/lib/declarations.ts`:

```ts
import type { DeclarableName, DeclarableReply, VariableKeyOffer } from "../api/types";

/** Which of the two verbs the name field has landed on. */
export type Mode = "unchosen" | "read" | "declare";

/** How the page words each scope, as ROLES words it on every other screen. */
const ROLE: Record<string, string> = {
  output: "produces",
  input: "reads",
  local: "keeps to itself",
};

export function chosenName(typed: string, names: DeclarableName[]): DeclarableName | null {
  return names.find((entry) => entry.name === typed) ?? null;
}

export function modeOf(typed: string, names: DeclarableName[]): Mode {
  if (typed === "") return "unchosen";
  return chosenName(typed, names) === null ? "declare" : "read";
}

export function scopesOf(typed: string, reply: DeclarableReply): string[] {
  return [...(chosenName(typed, reply.names)?.scopes ?? reply.scopes)];
}

/** The keys a kind asks for: the ones it must state first, each group in the server's order.
 * Required first because a form a reader fills top to bottom should ask for what it cannot do
 * without before what it can. */
export function keysOf(kind: string, reply: DeclarableReply): VariableKeyOffer[] {
  const keys = reply.kinds.find((entry) => entry.kind === kind)?.keys ?? [];
  const required = keys.filter((key) => key.carried[0]?.required === true);
  return [...required, ...keys.filter((key) => key.carried[0]?.required !== true)];
}

/** The definition the form has made, as json text - `null` while it could not be written:
 * no name, no kind, a required key unstated, or a value that is not json. */
export function definitionOf(
  name: string,
  kind: string,
  values: Record<string, string>,
  reply: DeclarableReply,
): string | null {
  if (name === "" || kind === "") return null;
  const definition: Record<string, unknown> = { name, kind };
  for (const key of keysOf(kind, reply)) {
    const raw = values[key.key];
    if (raw === undefined || raw === "") {
      if (key.carried[0]?.required === true) return null;
      continue;
    }
    try {
      definition[key.key] = JSON.parse(raw);
    } catch {
      return null;
    }
  }
  return JSON.stringify(definition);
}

/** The json a row of dimension fields makes: a whole number stays a number, anything else is
 * the name of a constant. `null` while any row is blank - a value block is never a scalar, so
 * a half-filled row states nothing rather than a shape nobody asked for. */
export function dimensionsRaw(rows: string[]): string | null {
  if (rows.length === 0 || rows.some((row) => row.trim() === "")) return null;
  return JSON.stringify(
    rows.map((row) => (/^[1-9][0-9]*$/.test(row.trim()) ? Number(row.trim()) : row.trim())),
  );
}

/** The sentence above the preview, which is what tells reading from declaring apart before
 * anything is written. */
export function declareSentence(
  typed: string,
  kind: string,
  scope: string,
  reply: DeclarableReply,
): string {
  const mode = modeOf(typed, reply.names);
  if (mode === "unchosen") return "Choose a variable, or type a new name.";
  if (mode === "read") {
    const producer = chosenName(typed, reply.names)?.producer;
    const whose = producer === null || producer === undefined ? "this project" : producer;
    return `Reads ${typed} as ${whose} declares it.`;
  }
  const role = ROLE[scope] ?? scope;
  return `Declares ${typed}, a ${kind} this component ${role}.`;
}
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd gui && npm test`
Expected: PASS, and 100 % over `src/lib` - every branch above has a test, including `keysOf`'s unknown kind, `definitionOf`'s four `null`s and `declareSentence`'s producerless name.

- [ ] **Step 7: Commit**

```bash
cd gui && npm run lint && npm run typecheck && npm test
git add gui/src/api/types.ts gui/src/api/client.ts gui/src/api/client.test.ts gui/src/lib/declarations.ts gui/src/lib/declarations.test.ts
git commit -m "read what a component may add, and word which verb it is

Co-Authored-By: <model that wrote it> <noreply@anthropic.com>"
```

### Task 5: A value block's dimensions

**Files:**
- Create: `gui/src/components/DimensionsField.tsx`, `gui/src/components/DimensionsField.stories.tsx`
- Modify: `gui/src/styles/ui.css`

**Interfaces:**
- Consumes: the existing `ComboBox` of `gui/src/ui/ComboBox.tsx` and `Button` of `gui/src/ui/Button.tsx`. It takes `rows: string[]` and emits `rows`; turning those into json is Task 8's, through `dimensionsRaw`.
- Produces: `DimensionsField` and `DimensionsFieldProps`, which Task 6's panel draws for a `dimensions` key.

**Why this is its own component.** `EDITORS` spells `dimensions` as `none` (`src/ddd/variable_keys.py:54`), so the key chooser offers no field for it - deliberately, because settling a shape across declarations that already state one is the hazardous act. A value block *requires* `dimensions`, so a form that cannot state it cannot declare one of the six kinds. Stating a required key once, on a declaration that does not exist yet, settles nothing, so this is the `size` field repeated: a `Dimension` is a whole number of at least 1 or the name of a constant the project declares (`src/ddd/models/objects.py:685`), which is exactly what a `size` is.

- [ ] **Step 1: Write the component**

```tsx
import { Button } from "../ui/Button";
import { ComboBox } from "../ui/ComboBox";

export interface DimensionsFieldProps {
  /** One entry per dimension, each a whole number or a constant's name. */
  rows: string[];
  /** The project's constants, offered beside whatever is typed. */
  constants: string[];
  /** The name the labels speak of, so a screen reader hears which object this shapes. */
  owner: string;
  busy: boolean;
  onRows: (rows: string[]) => void;
}

/** A value block's shape: one `size` field per dimension, in c declaration order. A picture of
 * its props - it holds nothing of its own. */
export function DimensionsField({ rows, constants, owner, busy, onRows }: DimensionsFieldProps) {
  const shown = rows.length === 0 ? [""] : rows;
  return (
    <div className="dimensions-field" role="group" aria-label={`Dimensions of ${owner}`}>
      {shown.map((row, index) => (
        // The index is the identity here: a dimension has no name, and two of the same size
        // are two different dimensions of one shape.
        // biome-ignore lint/suspicious/noArrayIndexKey: a dimension is its position
        <div className="dimension-row" key={index}>
          <ComboBox
            label={`Dimension ${index + 1} of ${owner}`}
            inputValue={row}
            onInputChange={(value) => onRows(shown.map((old, at) => (at === index ? value : old)))}
            sections={[
              {
                id: "constants",
                title: "This project's constants",
                choices: constants.map(choiceOf),
              },
            ]}
            onPick={(id) => onRows(shown.map((old, at) => (at === index ? id : old)))}
            onEnter={(text) => onRows(shown.map((old, at) => (at === index ? text : old)))}
            onClose={() => undefined}
            isDisabled={busy}
          />
          <Button
            variant="link"
            aria-label={`Remove dimension ${index + 1} of ${owner}`}
            isDisabled={busy || shown.length === 1}
            onPress={() => onRows(shown.filter((_, at) => at !== index))}
          >
            Remove
          </Button>
        </div>
      ))}
      <Button variant="link" isDisabled={busy} onPress={() => onRows([...shown, ""])}>
        Add a dimension
      </Button>
    </div>
  );
}

function choiceOf(constant: string) {
  return { id: constant, label: constant, detail: "" };
}
```

The prop names above are `gui/src/ui/ComboBox.tsx`'s own, checked against it: `label`, `inputValue`, `onInputChange`, `sections`, `onPick`, `onEnter`, `onClose`, `isDisabled`, and optionally `note`, `autoFocus` and `menuTrigger`. A `ComboSection` is `{ id, title, choices }` and a `ComboChoice` is `{ id, label, detail }` - `detail` is the grey text beside a choice, empty here because a constant's name is the whole of what there is to say.

- [ ] **Step 2: Write the stories**

`gui/src/components/DimensionsField.stories.tsx` - a plain exported function component per story, holding its own state, importing nothing from `@ladle/react`:

```tsx
import { useState } from "react";
import { DimensionsField } from "./DimensionsField";

export function OneDimensionNotYetStated() {
  const [rows, setRows] = useState<string[]>([]);
  return (
    <DimensionsField rows={rows} constants={[]} owner="BlockB" busy={false} onRows={setRows} />
  );
}

export function TwoDimensionsStated() {
  const [rows, setRows] = useState(["4", "8"]);
  return (
    <DimensionsField rows={rows} constants={[]} owner="BlockB" busy={false} onRows={setRows} />
  );
}

export function AConstantAmongThem() {
  const [rows, setRows] = useState(["PRESSURE_CELLS", "4"]);
  return (
    <DimensionsField
      rows={rows}
      constants={["PRESSURE_CELLS", "SENSOR_COUNT"]}
      owner="BlockB"
      busy={false}
      onRows={setRows}
    />
  );
}
```

- [ ] **Step 3: Add the rules**

In `gui/src/styles/ui.css`, beside the other panel rules:

```css
.dimensions-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.dimension-row {
  display: flex;
  align-items: end;
  gap: var(--space-2);
}
```

`--space-2` and `--space-3` are the tokens `.panel-actions` already uses (`gui/src/styles/ui.css:185`), so no new token is needed.

- [ ] **Step 4: Take the screenshots**

```bash
cd gui && npm run lint && npm run typecheck && npm run ladle:build
cd .. && UPDATE=1 docker compose run --rm gui-screenshots && docker compose run --rm gui-screenshots
```

Expected: three new references under `gui/screenshots/`, named for the three stories, and **no existing reference changed** (`git status` shows only additions). Open all three and look at them: the field is one row per dimension with a Remove beside it and an "Add a dimension" under them; the third shows the constants offered.

- [ ] **Step 5: Commit**

```bash
git add gui/src/components/DimensionsField.tsx gui/src/components/DimensionsField.stories.tsx gui/src/styles/ui.css gui/screenshots
git commit -m "state a value block's shape, one dimension at a time

Co-Authored-By: <model that wrote it> <noreply@anthropic.com>"
```

### Task 6: The add panel as a picture of its props

**Files:**
- Create: `gui/src/components/DeclarePanelView.tsx`, `gui/src/components/DeclarePanelView.stories.tsx`
- Modify: `gui/src/stories/fixtures.ts`, `gui/src/styles/ui.css`

**Interfaces:**
- Consumes: Task 4's `declarations.ts`; Task 5's `DimensionsField`; the existing `Panel`, `Button`, `ComboBox`, `Changes`, `KeyChooser`, and `shownChanges`/`consequence` from `gui/src/lib/units.ts`.
- Produces:

```ts
export interface DeclarePanelViewProps {
  reply: DeclarableReply;
  /** What the name field holds: a listed name, a new one, or nothing yet. */
  typed: string;
  kind: string;
  scope: string;
  /** The json text of each key the form has stated, by key. */
  values: Record<string, string>;
  /** A value block's rows, kept apart because `dimensions` has no chooser. */
  dimensions: string[];
  plan: PlanReply | null;
  refusal: string | null;
  changesShown: boolean;
  busy: boolean;
  onTyped: (typed: string) => void;
  onKind: (kind: string) => void;
  onScope: (scope: string) => void;
  onValue: (key: string, raw: string) => void;
  onDimensions: (rows: string[]) => void;
  onChangesShown: (shown: boolean) => void;
  onApply: () => void;
  onClose: () => void;
}
export function DeclarePanelView(props: DeclarePanelViewProps): JSX.Element;
```

- [ ] **Step 1: Write the view**

It holds no state and asks for nothing: every value comes from its props and every change goes out through a callback, the way `UnitPanelView` and `TypePanelView` are written. Its body, in order:

1. `<Panel title="Add a declaration" onClose={props.onClose}>`.
2. **The name field**: one `ComboBox` labelled `Name`, offering `reply.names` in a section headed `This project's variables`, taking whatever is typed. Each choice's secondary text is `${entry.kind} from ${entry.producer ?? "no producer"}`.
3. **The scope field**: a `ComboBox` labelled `Scope`, its choices `scopesOf(props.typed, props.reply)` worded as the page words them - `produces`, `reads`, `keeps to itself`.
4. **When `modeOf(props.typed, props.reply.names) === "declare"`**: a `ComboBox` labelled `Kind` over `reply.kinds.map((entry) => entry.kind)`, and then, for each key of `keysOf(props.kind, props.reply)`, either `<DimensionsField>` when `key.key === "dimensions"` or a `<KeyChooser>` for every other key, each with `owner={props.typed}` and `offer={key}`.
5. `<p className="consequence">{declareSentence(props.typed, props.kind, props.scope, props.reply)}</p>`.
6. The refusal, `plan`, `Show changes` and `Apply`, written exactly as `UnitPanelView`'s `panel-offer` writes them:

```tsx
      {props.refusal !== null && (
        <p className="panel-refusal" role="status">
          {props.refusal}
        </p>
      )}
      {props.refusal === null && props.plan !== null && props.plan.changes.length > 0 && (
        <>
          {props.changesShown && <Changes changes={shownChanges(props.plan.changes)} />}
          <div className="panel-actions">
            <Button variant="link" onPress={() => props.onChangesShown(!props.changesShown)}>
              {props.changesShown ? "Hide changes" : "Show changes"}
            </Button>
            <Button variant="primary" isDisabled={props.busy} onPress={props.onApply}>
              Apply to {props.plan.changes.length} file
              {props.plan.changes.length === 1 ? "" : "s"}
            </Button>
          </div>
        </>
      )}
```

- [ ] **Step 2: Add the fixture**

In `gui/src/stories/fixtures.ts`, a `DECLARABLE: DeclarableReply` built from what `examples/demo`'s Controller really answers - the nine names of the prerequisites, each with its producer, and the six kinds with their keys. Copy the keys from a real `GET /api/declarable` answer rather than writing them by hand:

```bash
cd gui && npm run build && cd ..
python -m ddd gui examples/demo/demo.ddd.json --no-browser &
# then, with the token the command printed:
curl -s --cookie "ddd-gui-<port>=<token>" \
  "http://127.0.0.1:<port>/api/declarable?file=$PWD/examples/demo/components/controller.ddd.json" \
  | python -m json.tool > /tmp/declarable.json
```

- [ ] **Step 3: Write the stories**

Six, each a plain function component holding its own state: `NothingChosenYet`, `AVariableChosenToRead`, `ANewMeasurement`, `ANewCurve` (whose `axis` key is the `editor: "name"` chooser, offering the project's axes), `ANewValueBlock` (which draws Task 5's field), and `ANameTheProjectRefuses` (its `refusal` set to `'ValueA' is already declared by this project`).

- [ ] **Step 4: Take the screenshots**

```bash
cd gui && npm run lint && npm run typecheck && npm run ladle:build
cd .. && UPDATE=1 docker compose run --rm gui-screenshots && docker compose run --rm gui-screenshots
```

Expected: six new references, no existing one changed. **Open all six and look at them.** The two to check hardest are `ANewCurve`, whose `axis` field must offer `AxisA` and `AxisB` rather than free text, and `ANewValueBlock`, whose dimensions row must sit among the other keys rather than beside them.

- [ ] **Step 5: Commit**

```bash
git add gui/src/components/DeclarePanelView.tsx gui/src/components/DeclarePanelView.stories.tsx gui/src/stories/fixtures.ts gui/src/styles/ui.css gui/screenshots
git commit -m "draw the panel that adds a declaration

Co-Authored-By: <model that wrote it> <noreply@anthropic.com>"
```

### Task 7: The removal offer

**Files:**
- Modify: `gui/src/components/VariablePanelView.tsx`, `gui/src/components/VariablePanelView.stories.tsx`, `gui/src/styles/ui.css`

**Interfaces:**
- Consumes: the existing `Offer` interface, exported from `gui/src/components/UnitPanelView.tsx:21` (`{ plan, refusal, pending }`) - import it from there rather than declaring a second one; `Changes`; `shownChanges` from `gui/src/lib/units.ts:176`.
- Produces: two new props on `VariablePanelViewProps`:

```ts
  /** What removing this declaration from this component would take; `null` on a screen that
   * offers no removal - the graph's panel, where no one component is in view. */
  removal: Offer | null;
  /** Which component the removal would take it from, for the sentence and the label. */
  removeFrom: string | null;
  removalShown: boolean;
  onRemovalShown: (shown: boolean) => void;
  onRemove: () => void;
```

- [ ] **Step 1: Add the offer to the view**

At the end of the panel, after the key chooser's own actions and before `</Panel>`:

```tsx
      {props.removal !== null && props.removeFrom !== null && (
        <section className="panel-offer" aria-label="Remove the declaration">
          <p className="consequence">{removalSentence(variable, props.removeFrom)}</p>
          {props.removal.refusal !== null && (
            <p className="panel-refusal" role="status">
              {props.removal.refusal}
            </p>
          )}
          {props.removal.refusal === null &&
            props.removal.plan !== null &&
            props.removal.plan.changes.length > 0 && (
              <>
                {props.removalShown && (
                  <Changes changes={shownChanges(props.removal.plan.changes)} />
                )}
                <div className="panel-actions">
                  <Button variant="link" onPress={() => props.onRemovalShown(!props.removalShown)}>
                    {props.removalShown ? "Hide changes" : "Show changes"}
                  </Button>
                  <Button
                    variant="secondary"
                    isDisabled={props.busy || props.removal.pending}
                    onPress={props.onRemove}
                  >
                    Remove from {props.removeFrom}
                  </Button>
                </div>
              </>
            )}
        </section>
      )}
```

- [ ] **Step 2: Write the sentence**

In `gui/src/lib/declarations.ts` (Task 4's module), with its own Vitest tests:

```ts
/** What removing one declaration leaves behind, from what the panel already holds: the other
 * components declaring the variable, and what they do with it. */
export function removalSentence(
  variable: { name: string; declarations: { component: string; role: string }[] },
  from: string,
): string {
  const others = variable.declarations.filter((entry) => entry.component !== from);
  const readers = others.filter((entry) => entry.role === "reads").map((entry) => entry.component);
  if (others.length === 0) {
    return `Removes ${variable.name}, which no other component declares.`;
  }
  if (readers.length === 0) {
    return `Removes ${variable.name} from ${from}; ${listed(others.map((e) => e.component))} still declare it.`;
  }
  return `Removes ${variable.name} from ${from}; ${listed(readers)} still read it.`;
}

/** "A", "A and B", "A, B and C" - the way every sentence of this interface lists names. */
function listed(names: string[]): string {
  if (names.length <= 1) return names.join("");
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
}
```

Its tests, in `gui/src/lib/declarations.test.ts`:

```ts
describe("what removing a declaration leaves behind", () => {
  const declaredBy = (...entries: [string, string][]) => ({
    name: "ValueA",
    declarations: entries.map(([component, role]) => ({ component, role })),
  });

  test("the only declaration leaves nothing", () => {
    expect(removalSentence(declaredBy(["Controller", "reads"]), "Controller")).toBe(
      "Removes ValueA, which no other component declares.",
    );
  });

  test("the readers left behind are named", () => {
    const variable = declaredBy(
      ["SensorHub", "produces"],
      ["Controller", "reads"],
      ["UserInterface", "reads"],
    );
    expect(removalSentence(variable, "SensorHub")).toBe(
      "Removes ValueA from SensorHub; Controller and UserInterface still read it.",
    );
  });

  test("with no reader left, the components that remain are named instead", () => {
    const variable = declaredBy(["SensorHub", "produces"], ["Controller", "reads"]);
    expect(removalSentence(variable, "Controller")).toBe(
      "Removes ValueA from Controller; SensorHub still declares it.",
    );
  });

  test("one name is listed without an and", () => {
    const variable = declaredBy(["SensorHub", "produces"], ["Controller", "reads"]);
    expect(removalSentence(variable, "SensorHub")).toBe(
      "Removes ValueA from SensorHub; Controller still reads it.",
    );
  });
});
```

- [ ] **Step 3: Add the stories and take the screenshots**

Two more stories on `VariablePanelView`: `WithARemovalAndReadersLeft` and `WithARemovalAndNothingLeft`. Then:

```bash
cd gui && npm run lint && npm run typecheck && npm test && npm run ladle:build
cd .. && UPDATE=1 docker compose run --rm gui-screenshots && docker compose run --rm gui-screenshots
```

Expected: two new references. **Part 3's five existing `variablepanelview` references must come out unchanged** - the offer is drawn only when `removal` is not `null`, and those stories pass `null`. If any of them moves, the offer is rendering where it should not; fix that rather than updating the reference.

- [ ] **Step 4: Commit**

```bash
git add gui/src/components/VariablePanelView.tsx gui/src/components/VariablePanelView.stories.tsx gui/src/lib/declarations.ts gui/src/lib/declarations.test.ts gui/src/styles/ui.css gui/screenshots
git commit -m "offer to remove a declaration, and say what it leaves

Co-Authored-By: <model that wrote it> <noreply@anthropic.com>"
```

### Task 8: The add panel's screen, and the way in

**Files:**
- Create: `gui/src/screens/DeclarePanel.tsx`
- Modify: `gui/src/screens/ComponentPage.tsx`

**Interfaces:**
- Consumes: Task 4's `getDeclarable`, `getDeclarationPlan`, `DeclarationPlanRequest`, `definitionOf`, `dimensionsRaw`, `modeOf`; Task 6's `DeclarePanelView`; the existing `postEdit`, `planEdit` and `refusalOf` of `gui/src/screens/UnitPanel.tsx`'s shape.
- Produces: `DeclarePanel`, opened by the component page's own state.

- [ ] **Step 1: Write the screen**

`gui/src/screens/DeclarePanel.tsx` holds the queries, the mutation and the refusals; `DeclarePanelView` holds none of them.

```tsx
interface Props {
  /** The component being added to: its absolute, posix-separated path. */
  file: string;
  revision: number | undefined;
  stopped: boolean;
  onClose: () => void;
  /** Applied: the component page selects the new declaration's variable. */
  onDeclared: (name: string) => void;
}
```

- `useQuery({ queryKey: ["declarable", file, revision], queryFn: () => getDeclarable(file) })`, with `placeholderData: (previous) => previous` so the form does not blink on every revision.
- The form's own state - `typed`, `kind`, `scope`, `values`, `dimensions`, `changesShown` - is `useState` here, because a half-filled form is this panel's and nothing else's.
- **`scope` follows the name.** When `typed` changes, a `scope` the new name may not take is not kept: set it to the first of `scopesOf(typed, reply)`. This is what stops the panel offering an `output` for a name that already has a producer after the reader has typed over a new name.
- The plan is a query keyed by everything it is made of, so it is re-asked when any of them changes and when the revision does:

```tsx
  const request: DeclarationPlanRequest | null = requestOf(file, typed, kind, scope, values, dimensions, declarable.data);
  const plan = useQuery({
    queryKey: ["declaration-plan", request, revision],
    queryFn: request === null ? skipToken : () => getDeclarationPlan(request),
  });
```

where `requestOf` answers `{ action: "read", file, name: typed, scope }` when `modeOf` says `read`, `{ action: "declare", file, scope, definition }` when `definitionOf` (with `dimensions` folded in through `dimensionsRaw`) answers a definition, and `null` otherwise - which is what leaves the panel showing no preview and no Apply while a required key is unstated.

- The mutation posts `planEdit(plan.data, label)` where the label is the sentence an undo will offer: `reading ValueC into Controller` or `declaring Pressure in Controller`. On success it invalidates `["file"]`, `["declarable"]` and `["declaration-plan"]`, calls `onDeclared(typed)` and closes.
- A refusal is shown as the other panels show one: `refusalOf(error)` for a stale, the `ApiError`'s own message otherwise, cleared on the next change of the form. **`refusalOf` is exported twice already** - `gui/src/screens/UnitPanel.tsx:31` and `gui/src/screens/TypePanel.tsx:36`, the same four lines. Import one of them rather than writing a third; if a reviewer asks, moving the one function to `gui/src/lib/refusals.ts` beside `shownRefusal` is the tidier answer and is in scope for this task.

- [ ] **Step 2: Open it from the component page**

In `gui/src/screens/ComponentPage.tsx`:

```tsx
  const [adding, setAdding] = useState(false);
```

A control in the heading beside `UndoStrip`:

```tsx
          <Button variant="secondary" isDisabled={stopped} onPress={() => setAdding(true)}>
            Add a declaration
          </Button>
```

and, in the panel slot, the new panel when `adding` and no variable is selected:

```tsx
    <section className={variable === undefined && !adding ? undefined : "with-panel"}>
```

```tsx
      {adding && (
        <DeclarePanel
          file={file}
          revision={state?.revision}
          stopped={stopped}
          onClose={() => setAdding(false)}
          onDeclared={(name) => {
            setAdding(false);
            setUndeclared(null);
            onVariable(name);
          }}
        />
      )}
```

**One panel at a time.** Selecting a variable while the form is open closes the form: add `setAdding(false)` to the table's `onSelectionChange` and to `followVariable`, beside the `setFocusPicker(null)` and `setUndeclared(null)` they already do. Opening the form while a variable is selected clears the selection: `onVariable(undefined)` in the control's `onPress`. This is part 6's task 9 lesson - two write paths, each able to be dirty, and a panel with one slot.

- [ ] **Step 3: Check it by hand before the journeys**

```bash
cd gui && npm run build && cd ..
python -m ddd gui examples/demo/demo.ddd.json --no-browser
```

Open the address, go to Table, open Controller, press **Add a declaration**, and check by eye: choosing `ValueC` shows `Reads ValueC as SensorHub declares it.` and a preview of one file; typing `Pressure` grows the form; typing `ValueA` is refused in the project's own words. Apply one and see the row appear in the table. **Do not skip this**: Task 10's journeys are written against what this step shows.

- [ ] **Step 4: Commit**

```bash
cd gui && npm run lint && npm run typecheck && npm test && npm run build
git add gui/src/screens/DeclarePanel.tsx gui/src/screens/ComponentPage.tsx
git commit -m "add a declaration from the component's own page

Co-Authored-By: <model that wrote it> <noreply@anthropic.com>"
```

### Task 9: Removal wired into the variable's panel

**Files:**
- Modify: `gui/src/screens/VariablePanel.tsx`

**Interfaces:**
- Consumes: Task 4's `getDeclarationPlan`; Task 7's new `VariablePanelView` props; the panel's existing `apply` mutation, `failed`/`staleFailed` state and `shownRefusal`.
- Produces: nothing later tasks read.

**This task owns the `file` prop, both halves.** Measured: `VariablePanel`'s `Props` (`gui/src/screens/VariablePanel.tsx:19`) has no `file` today - it is `name`, `revision`, `stopped`, `focusPicker`, `onClose`, `onUndeclared`, `onOpenType`. Add `file: string | undefined` to it **and** pass `file={file}` from `gui/src/screens/ComponentPage.tsx`, which Task 8 has already changed by the time this runs. It is `undefined` on the project screen's own panel, where no one component is in view and no removal is offered - which is what Task 7's `removal: Offer | null` is for.

- [ ] **Step 1: Ask for the removal's plan**

Only when the panel is on a component's page, which is what the new `file` prop says:

```tsx
  const removal = useQuery({
    queryKey: ["declaration-plan", "remove", file, name, revision],
    queryFn:
      file === undefined
        ? skipToken
        : () => getDeclarationPlan({ action: "remove", file, name }),
  });
```

- [ ] **Step 2: Add its mutation, and make the two paths clear each other**

The panel now has two write paths: settling a key and removing the declaration. Part 6's task 9 found three of them dirty at once in a type's panel, with one preview and one Apply between them. Here:

- Removing clears the key chooser's refusal and its selection.
- Settling a key clears the removal's refusal and hides its changes.
- A success in either invalidates `["variable"]`, `["file"]`, `["declarable"]` and `["declaration-plan"]`.

The removal's label, which is what an undo offers: `removing ${name} from ${component}`.

- [ ] **Step 3: Close the panel when the last declaration goes**

Nothing new to write: removing the only declaration of a variable leaves no file declaring it, `GET /api/variable` answers no declarations, and the panel's existing `onUndeclared` fires - the path the component page already names above its table. **Assert it in Task 10's journey** rather than adding a second mechanism here.

- [ ] **Step 4: Commit**

```bash
cd gui && npm run lint && npm run typecheck && npm test && npm run build
git add gui/src/screens/VariablePanel.tsx
git commit -m "remove a declaration from the variable's own panel

Co-Authored-By: <model that wrote it> <noreply@anthropic.com>"
```

### Task 10: The journeys

**Files:**
- Create: `gui/e2e/declarations.spec.ts`
- Modify: `gui/e2e/units.spec.ts` (the content-security-policy journey)

**Interfaces:**
- Consumes: `gui/e2e/fixtures.ts`'s `gui` fixture (a copy of `examples/demo`), and `gui/e2e/demo.ts`'s `CONTROLLER`.
- Produces: nothing later tasks read.

- [ ] **Step 1: Write the six journeys**

Against a copy of `examples/demo`, driving the compiled pages through the real `ddd gui`:

1. **`a variable another component produces is read, keys and all`** - open Controller, Add a declaration, choose `ValueC`, check the sentence reads `Reads ValueC as SensorHub declares it.`, Show changes, Apply, then assert the written file: `readFileSync(join(gui.directory, CONTROLLER), "utf8")` holds a `ValueC` declaration whose `unit` is `degC` and which carries **no `id` and no `init`** - the rule the whole verb rests on, asserted where it is finally visible.
2. **`a new measurement is declared and stamped`** - type `Pressure`, kind `measurement`, scope `produces`, a `datatype` and a `volatile`, Apply, then assert the file holds `"name": "Pressure"` followed by an `"id"` of twelve characters.
3. **`a value block is declared with the shape it is given`** - type `BlockB`, kind `value_block`, add two dimensions `4` and `8`, Apply, and assert `"dimensions": [4, 8]` reaches the file. This is the journey that exercises Task 5's field.
4. **`a curve is declared against an axis the project has`** - type `CurveC`, kind `curve`, and open the `axis` chooser: it offers `AxisA` and `AxisB`, the demo's two axes, because `EDITORS` spells `axis` as `name` and `_choices` fills it from the project's objects of that kind. Choose `AxisA`, Apply, and assert `"axis": "AxisA"` reaches the file. This is the journey that exercises the object-reference chooser, which is the one part of the form nothing else covers.
5. **`a name the project already has is refused in its own words`** - type `ValueA` and assert the panel says `'ValueA' is already declared by this project` and that **nothing is written**: the file's bytes before and after are equal.
6. **`a declaration is removed and put back`** - open `ValueB` on Controller's page and remove it. Measured: Controller declares `ValueB` as an `input`, SensorHub produces it and UserInterface also reads it, so the sentence reads `Removes ValueB from Controller; SensorHub and UserInterface still declare it.` Assert the row is gone from the table and the name is gone from the file, then press Undo and assert the file is byte-for-byte what it was.

Journey 6's byte comparison is the point of it: `const before = readFileSync(file); … await expect.poll(() => readFileSync(file).equals(before)).toBe(true);` - the shape `undo.spec.ts` already uses.

- [ ] **Step 2: Extend the policy journey**

In `gui/e2e/units.spec.ts`'s `no page reports a violation of its content security policy`, after the Types section and before the Table tab, add the new panel to the walk:

```ts
  // The add panel (part 7), on the component page. Opened and filled far enough to draw its
  // preview - the panel's own chooser, its consequence and its hunks are the three things a
  // policy would otherwise catch - then closed, so the walk below starts where it did.
  await page.getByRole("link", { name: "Table" }).click();
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Add a declaration" }).click();
  const adding = page.getByRole("complementary", { name: "Add a declaration" });
  await adding.getByRole("combobox", { name: "Name" }).fill("ValueC");
  await adding.getByRole("combobox", { name: "Name" }).press("Enter");
  await adding.getByRole("button", { name: "Show changes" }).click();
  await expect(adding.locator(".hunk")).toHaveCount(1);
  await adding.getByRole("button", { name: "Close" }).click();
```

**The journey already navigates to Table and Controller further down; leave those lines where they are** rather than deleting them - the walk returns to the component page for the undo strip, and arriving twice costs a second and proves the page survives it.

- [ ] **Step 3: Run them**

```bash
cd gui && npm run build && PLAYWRIGHT_CHANNEL=chrome npx playwright test e2e/declarations.spec.ts
cd gui && PLAYWRIGHT_CHANNEL=chrome npx playwright test
```

Expected: six new journeys pass, and the whole suite passes - 57 of them.

**Run the whole suite three times before believing it.** A journey that waits on a network response rather than on something the page shows is a race that passes until it does not; #56's `project-units.spec.ts` lost exactly that race when the server changed. **Wait for what the page shows**: a sentence, a row, a count of hunks - never `page.waitForResponse`.

- [ ] **Step 4: Commit**

```bash
git add gui/e2e/declarations.spec.ts gui/e2e/units.spec.ts
git commit -m "drive adding and removing a declaration in a browser

Co-Authored-By: <model that wrote it> <noreply@anthropic.com>"
```

### Task 11: What a user and a developer read

**Files:**
- Modify: `CHANGELOG.md`, `docs/command_line_interface.rst`, `docs/developer_documentation.rst`

- [ ] **Step 1: The changelog**

Under the unreleased heading, in the voice the entries beside it use - what a reader can now do, not what was built:

```markdown
- `ddd gui` can add a declaration to a component and take one away. A variable the project
  already declares is read with the producer's own keys, so the new reader agrees with it by
  construction; a new object is declared with its kind's required keys and, when it produces,
  a fresh id. Both are previewed before they are written and undone by one press.
```

- [ ] **Step 2: The command line page**

`docs/command_line_interface.rst`'s `ddd gui` section gains the verb to its list of what the interface can do, and keeps the word **preview**.

- [ ] **Step 3: The developer page**

`docs/developer_documentation.rst` gains `ddd.declaration_plans` beside `ddd.type_plans` and `ddd.project_units`, with one sentence: what a component may add, and what each of the three verbs takes.

- [ ] **Step 4: Build the documentation and run the gate**

```bash
docker compose run --rm --user "$(id -u):$(id -g)" -e JAVA_TOOL_OPTIONS=-Duser.home=/tmp ddd \
  python -m sphinx -M html docs build/docs_out -W
python -m pytest -q && ruff check . && ruff format --check . && mypy
```

Expected: sphinx clean under `-W`, and `tests/test_documentation.py` passes - it reads these pages.

- [ ] **Step 5: Commit**

```bash
git add CHANGELOG.md docs/command_line_interface.rst docs/developer_documentation.rst
git commit -m "say what the interface can add and take away

Co-Authored-By: <model that wrote it> <noreply@anthropic.com>"
```

### Task 12: The milestone gate

**Files:** none. This task runs everything and writes the progress log below.

- [ ] **Step 1: The whole Python gate**

```bash
export PATH="$HOME/.local/node-v24.21.0/bin:$PWD/.venv/bin:$PATH"
python -m pytest -q && ruff check . && ruff format --check . && mypy
```

Expected: 100 % line and branch coverage, all checks pass, no `pragma: no cover` and no skip anywhere in the diff.

- [ ] **Step 2: The whole page gate**

```bash
cd gui && npm run lint && npm run typecheck && npm test && npm run build && npm run ladle:build
```

Expected: Vitest 100 % over `src/api`, `src/lib`, `src/state`; the build and the ladle build clean.

- [ ] **Step 3: The screenshots**

```bash
docker compose run --rm gui-screenshots
```

Expected: every reference matches, the eleven new ones included (three from Task 5, six from Task 6, two from Task 7), and **no reference from parts 1 to 6 has changed**.

- [ ] **Step 4: The journeys, three times**

```bash
cd gui && npm run build && for i in 1 2 3; do PLAYWRIGHT_CHANNEL=chrome npx playwright test || break; done
```

Expected: 57 passed, three times over.

- [ ] **Step 5: The documentation**

```bash
docker compose run --rm --user "$(id -u):$(id -g)" -e JAVA_TOOL_OPTIONS=-Duser.home=/tmp ddd \
  python -m sphinx -M html docs build/docs_out -W
```

- [ ] **Step 6: Drive it once by hand**

Start `ddd gui` over a copy of `examples/demo` and do all three verbs in the browser: read a variable, declare a new one, remove one, undo each. **Look at the files afterwards.** The gate is green code; this is the part that says the feature is real.

- [ ] **Step 7: Fill in the progress log below, then hand over**

Use `superpowers:finishing-a-development-branch`.

## Progress log

| Task | Commit | Notes |
| --- | --- | --- |
| 1 | | |
| 2 | | |
| 3 | | |
| 4 | | |
| 5 | | |
| 6 | | |
| 7 | | |
| 8 | | |
| 9 | | |
| 10 | | |
| 11 | | |
| 12 | | |

## Left open

Filled in as the plan runs: anything found and deliberately not fixed here, with what it costs.

## Rulings

Filled in as the plan runs: every decision taken against the plan's text, why, and what it costs if wrong.
