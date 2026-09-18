# Module graph implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The project screen of `ddd gui` opens on a canvas of the project's modules, with an arrow per producer-consumer pair coloured by the worst disagreement between them, and a click opening the module.

**Architecture:** A transport-neutral `src/ddd/graph.py` turns one analysed revision into modules and flows; `GET /api/graph` serialises it through the pydantic contract; the page draws it with React Flow laid out by dagre, keeping the reader's own arrangement in the browser.

**Tech Stack:** Python 3.12+ with pydantic; React 19, TypeScript 7 strict, TanStack Query 5, `@xyflow/react` and `@dagrejs/dagre`, Vitest and Playwright.

**Spec:** `docs/superpowers/specs/2026-09-18-module-graph-design.md` (milestone 2 of `docs/superpowers/specs/2026-09-17-web-gui-design.md`)

## Global Constraints

- Python floor 3.12; **no new runtime dependency** of the Python package.
- Python gate: `python -m pytest` at 100 % line **and** branch coverage, `ruff check .`, `ruff format --check .`, `mypy`. No `pragma: no cover`, no `pytest.skip`/`skipif`/`xfail`/`importorskip`.
- Line length 100; ruff selects E, F, W, I, N, UP, B, SIM, RUF, ANN, PTH, C4; mypy strict with the pydantic plugin.
- The only expected failure anywhere is `tests/test_lsp.py::TestSymlinkedWorkspace::test_a_document_opened_through_a_symlink_is_covered_by_its_build`.
- Every request and answer of the API is declared in `src/ddd/gui/contract.py`; the page's types are generated from it by `npm run schemas`. Never hand-write a type that the generator produces.
- Frontend dependencies are pinned exactly, at whatever version Task 3 installs (`npm install --save-exact`), and the versions are recorded in its report. Bundled licences stay within MIT, ISC, Apache-2.0, BSD-2-Clause, BSD-3-Clause; `npm run build` refuses anything else.
- Vitest keeps its 100 % gate over `src/api`, `src/lib` and `src/state`; screens are covered by Playwright, not Vitest.
- Severity order is error, then warning, then info. A flow's severity is the worst of its disagreements; `info` never colours an arrow.
- `ddd gui` stays labelled **preview**.
- Local toolchain (Git Bash, never PowerShell):
  `export PATH="/c/git/ac11/ddd/.venv/Scripts:/c/Program Files/nodejs:/c/Users/lmbsog0/AppData/Local/Programs/CLion/bin/mingw/bin:$PATH" && cd /c/git/ac11/ddd`
  Playwright locally: `DDD_PYTHON=/c/git/ac11/ddd/.venv/Scripts/python.exe PLAYWRIGHT_CHANNEL=msedge npm run e2e`.
  The documentation build needs `JAVA="/c/CAD/Tools/MATLAB/R2022b_x64/sys/java/jre/win64/jre/bin/java.exe"` and `PLANTUML_JAR="/c/Users/lmbsog0/.vscode/extensions/jebbs.plantuml-2.18.1/plantuml.jar"`.

## File structure

| File | Responsibility |
| --- | --- |
| `src/ddd/graph.py` | One analysed revision to modules, flows and disagreements. No GUI, no HTTP, no I/O. |
| `tests/test_graph.py` | Its rules, case by case. |
| `src/ddd/gui/contract.py` | Gains the graph's models beside the other answers. |
| `src/ddd/gui/api.py` | Gains `GET /api/graph`, which serialises what `graph.py` returns. |
| `gui/src/api/client.ts` | Gains `getGraph`. |
| `gui/src/lib/layout.ts` | Modules and flows to nodes and edges with positions, through dagre. Pure. |
| `gui/src/state/positions.ts` | The reader's own arrangement, per project, in browser storage. |
| `gui/src/components/ModuleNode.tsx` | One module on the canvas: name, badge, ports. |
| `gui/src/components/FlowEdge.tsx` | One arrow: colour, count, hover. |
| `gui/src/screens/GraphPage.tsx` | The canvas, its controls and its selection. |
| `gui/src/screens/ProjectPage.tsx` | Gains the `Graph` / `Table` tabs around today's table. |
| `gui/src/lib/route.ts` | The project route carries which tab is open. |
| `gui/e2e/skeleton.spec.ts` | Gains the canvas journeys. |

---

### Task 1: The graph of a revision

**Files:**
- Create: `src/ddd/graph.py`
- Test: `tests/test_graph.py`

**Interfaces:**
- Consumes: `ddd.ir.DataDictionary` (its `components: tuple[ResolvedComponent, ...]` and `objects`, each object carrying `name`, `owner: str | None`, `consumers: tuple[str, ...]`, `local: bool`); `ddd.diagnostics.Diagnostic` (`check`, `severity`, `message`, `location`, `notes: tuple[tuple[str, Location | None], ...]`) and `ddd.diagnostics.Severity`.
- Produces, for Task 2:

```python
@dataclass(frozen=True, slots=True)
class Module:
    """One component of the project, as the canvas shows it."""

    path: PurePosixPath
    name: str
    loaded: bool
    errors: int
    warnings: int
    infos: int


@dataclass(frozen=True, slots=True)
class Disagreement:
    """One finding that says two modules describe the same object differently."""

    object: str | None
    check: str
    severity: Severity
    message: str


@dataclass(frozen=True, slots=True)
class Flow:
    """Everything one module produces for another."""

    source: PurePosixPath
    target: PurePosixPath
    objects: tuple[str, ...]
    disagreements: tuple[Disagreement, ...]

    @property
    def severity(self) -> Severity | None:
        """The worst disagreement on this flow, or nothing when the two agree."""


@dataclass(frozen=True, slots=True)
class Graph:
    """The modules of one revision and what flows between them."""

    modules: tuple[Module, ...]
    flows: tuple[Flow, ...]


def graph_of(
    dictionary: DataDictionary | None,
    modules: Iterable[Module],
    findings: Iterable[tuple[PurePosixPath, Diagnostic]],
) -> Graph:
    """The graph of one revision: its modules, and a flow per producing-consuming pair."""
```

The caller (Task 2) builds the `Module` list from the revision's files and pairs each finding with the file it is filed on, so that this module never touches `ddd.gui`.

- [ ] **Step 1: Write the failing tests**

`tests/test_graph.py`, with a small builder so each case reads as its own sentence. Use `ddd.ir`'s models directly; build a dictionary with `DataDictionary(format=..., components=(...), objects=(...))` following what `tests/test_dump.py` already does (read it first for the exact constructor arguments a valid dictionary needs).

The cases, each its own test:

1. **A flow per pair.** Two modules, `a.ddd.json` owning `Speed` with `b.ddd.json` in its consumers: one flow from a to b, `objects == ("Speed",)`, `disagreements == ()`, `severity is None`.
2. **Several objects on one flow.** The same pair owning `Speed` and `Torque`: one flow, `objects == ("Speed", "Torque")` (sorted).
3. **A local object makes no flow.** An object with `local=True` and no consumers: no flow.
4. **An unread object makes no flow.** `consumers == ()`: no flow.
5. **An object with no owner makes no flow.** `owner is None` with a consumer: no flow, and the module is still a node.
6. **A disagreement colours its flow.** A finding on `b.ddd.json` at `component.interface[0].definition`, severity error, with a note whose location is `a.ddd.json`: the flow from a to b carries one disagreement whose `object` is the name `declarations[0]` of component b gives, and `severity is Severity.ERROR`.
7. **The worst severity wins.** Two disagreements on one flow, a warning and an error: `severity is Severity.ERROR`; both are carried.
8. **A finding with no note is not a disagreement.** Same finding without notes: the flow has none, `severity is None`.
9. **A finding whose note points at a file that is not a module** (a shared types file): no disagreement.
10. **A finding whose declaration index does not resolve** (`component.interface[9]` where the component declares two): the disagreement is carried with `object is None`, so the arrow still colours.
11. **Both directions between one pair.** a owns `Speed` for b, b owns `Torque` for a: two flows, and a disagreement about `Torque` attaches to the flow from b to a only.
12. **A module that did not load** is a node with `loaded=False` and takes part in no flow.
13. **No dictionary at all** (`None`): the modules are returned and `flows == ()`.
14. **Deterministic order.** Modules sorted by path, flows sorted by (source, target); assert the exact tuples on a three-module project.

Run: `python -m pytest tests/test_graph.py --no-cov`
Expected: FAIL, `ModuleNotFoundError: No module named 'ddd.graph'`.

- [ ] **Step 2: Write `src/ddd/graph.py`**

The rules, in the order they are applied:

1. Modules come from the caller, sorted by path. A dictionary of component name to module path is built from the modules that loaded; a component the dictionary names but no module has is ignored.
2. For every object of the dictionary with an `owner` that maps to a module, every consumer that maps to a module makes a pair; the object's name joins that pair's set. A consumer equal to the owner is skipped.
3. Every finding whose file is a module and which carries at least one note locating another module makes a disagreement on the pairs joining the two, when a flow exists between them. The object is read from the dictionary: the finding's pointer ends in `component.interface[<index>]...`, and `declarations[index].name` of the component the file holds names the object; anything that does not resolve gives `object=None`.
4. A disagreement attaches to the flow whose objects contain its object; when the object is `None`, it attaches to every flow between the two modules.
5. `Flow.severity` is the worst of `disagreements`, by `Severity`'s own order, or `None` when there are none.

Use `ddd.pointers.segments` to read the index out of the pointer rather than a regular expression of your own. Sort every tuple that reaches the answer: modules by path, flows by `(source, target)`, objects alphabetically, disagreements by `(object or "", check, message)`.

- [ ] **Step 3: Run the tests**

Run: `python -m pytest tests/test_graph.py --no-cov`
Expected: PASS, every case.

- [ ] **Step 4: The whole Python gate**

Run: `python -m pytest`, then `python -m ruff format --check .`, `python -m ruff check .`, `python -m mypy`.
Expected: green, 100 % coverage, only the known symlink failure.

- [ ] **Step 5: Commit**

```bash
git add src/ddd/graph.py tests/test_graph.py
git commit -m "read one revision as modules and the flows between them, with the disagreements that colour them"
git push
```
---

### Task 2: The endpoint

**Files:**
- Modify: `src/ddd/gui/contract.py`, `src/ddd/gui/api.py`
- Test: `tests/test_gui_api.py`, `tests/test_gui_server.py`

**Interfaces:**
- Consumes: Task 1's `graph_of`, `Module`, `Flow`, `Disagreement`, `Graph`; the session's `Revision` (`number`, `files: tuple[SourceFile, ...]`, `findings: tuple[Filed, ...]`, `dictionary`), `SourceFile` (`path`, `kind`, `name`, `loaded`, `errors`, `warnings`, `infos`) and `Filed` (`file: Path`, `diagnostic: Diagnostic`).
- Produces, for Task 3: `GET /api/graph` answering

```json
{
  "revision": 7,
  "modules": [
    {"path": "components/controller.ddd.json", "name": "Controller", "loaded": true,
     "findings": {"error": 1, "warning": 0, "info": 0}}
  ],
  "flows": [
    {"from": "components/sensor_hub.ddd.json", "to": "components/controller.ddd.json",
     "objects": ["ValueA"], "severity": "error",
     "disagreements": [{"object": "ValueA", "check": "definition-mismatch",
                        "severity": "error", "message": "..."}]}
  ]
}
```

`severity` is `null` when a flow carries no disagreement. Without an open project the endpoint
answers 409 with the code `no-project`, as `/api/state` does.

- [ ] **Step 1: Write the failing tests**

In `tests/test_gui_api.py`, beside the other endpoint classes, a `TestGraph` class using the same
fixtures the file already has:

1. On `examples/demo`: the answer lists the four component modules by path, each with its name and
   its finding counts, and the flows between them; assert the exact module paths and names, and
   that every flow's `severity` is `null` on the untouched demo.
2. After an edit that gives `ValueA` a unit its producer does not have (the file fixture the edit
   tests already use, or a copy written in the test): the flow between the two modules carries a
   `definition-mismatch` disagreement and `severity == "error"`.
3. With no project open: 409, code `no-project`.
4. A project whose component file does not parse: that module is in `modules` with
   `"loaded": false`, its name the file's stem, and it is in no flow.

In `tests/test_gui_server.py`, add `/api/graph` to the test that calls every endpoint over real
HTTP on a copy of the demo, asserting 200 and the keys `revision`, `modules`, `flows`.

Run: `python -m pytest tests/test_gui_api.py -k Graph --no-cov`
Expected: FAIL, 404 `not-found` - the route does not exist.

- [ ] **Step 2: Declare the answer in the contract**

In `src/ddd/gui/contract.py`, in the file's own style: `GraphModule` (path, name, loaded,
findings), `GraphDisagreement` (object, check, severity, message), `GraphFlow` (from, to, objects,
severity, disagreements) and `GraphReply` (revision, modules, flows). `from` is a Python keyword:
declare the field as `source` with `alias="from"` and serialise by alias, or `model_config =
ConfigDict(populate_by_name=True)` - whichever the file already does for such a case; the JSON key
is `from`, and `to` is plain.

Reuse the severity type the contract already uses for findings, and the counts model `/api/state`
uses for a file's findings rather than declaring a second one.

- [ ] **Step 3: Route it**

In `api.py`, `_graph` beside `_dictionary`: take `self.session.revision`, raise `NoProjectError`
when it is `None`, build the `Module` list from the revision's files whose `kind == "component"`
(the name is `file.name` when it loaded, otherwise the file's stem without `.ddd.json`), pair every
finding with the file it is filed on, call `graph_of`, and serialise with
`GraphReply(...).model_dump(mode="json", by_alias=True)`. Add `"/api/graph": ("GET", Api._graph)`
to the routes table.

- [ ] **Step 4: Run the tests, then the whole Python gate**

Run: `python -m pytest tests/test_gui_api.py -k Graph --no-cov`, then `python -m pytest`,
`python -m ruff format --check .`, `python -m ruff check .`, `python -m mypy`.
Expected: PASS, 100 %, only the known symlink failure.

- [ ] **Step 5: Commit**

```bash
git add src/ddd/gui/contract.py src/ddd/gui/api.py tests/test_gui_api.py tests/test_gui_server.py
git commit -m "answer the modules of a project and the flows between them, coloured by what the two ends disagree about"
git push
```

---

### Task 3: What the page needs before it can draw

**Files:**
- Modify: `gui/package.json`, `gui/package-lock.json`, `gui/src/api/client.ts`
- Create: `gui/src/lib/layout.ts`, `gui/src/lib/layout.test.ts`, `gui/src/state/positions.ts`, `gui/src/state/positions.test.ts`

**Interfaces:**
- Consumes: Task 2's endpoint, and the generated types (`npm run schemas` writes them; the graph's types come with the contract, so no type is hand-written). If the generator spells a name differently from the pydantic model, re-export it under `GraphReply`, `GraphModule`, `GraphFlow` and `GraphDisagreement` in `gui/src/api/types.ts`, the way milestone 1's types module already re-exports what the screens import.
- Produces, for Tasks 4 and 5:

```ts
export const getGraph = (fetchImpl: Fetch = fetch) => request<GraphReply>("/api/graph", {}, fetchImpl);

/** A module placed on the canvas. */
export interface Placed { path: string; x: number; y: number; }

/**
 * Where every module goes: dagre lays the flows out left to right, and a position the reader
 * saved wins over the one dagre computed.
 */
export function laidOut(
  modules: readonly GraphModule[],
  flows: readonly GraphFlow[],
  saved: Readonly<Record<string, { x: number; y: number }>>,
): Placed[];

/** The arrangement the reader made for one project, as their browser remembers it. */
export function savedPositions(project: string): Record<string, { x: number; y: number }>;
export function rememberPosition(project: string, path: string, x: number, y: number): void;
export function forgetPositions(project: string): void;
```

- [ ] **Step 1: Add the two packages**

From `gui/`: `npm install --save-exact @xyflow/react @dagrejs/dagre`, then `npm run build` to see
the licence check accept them. Record the two versions it installed in your report; both must be
MIT. If either resolves to a licence outside the allow-list, stop and report BLOCKED with what it
found.

- [ ] **Step 2: Write the failing tests for the layout**

`gui/src/lib/layout.test.ts`, with Vitest, over hand-written modules and flows:

1. Three modules in a chain (a produces for b, b for c): the x of a is less than b's, and b's less
   than c's - a left-to-right layering, not a hard-coded pixel.
2. Two modules with no flow between them: both are placed, and their positions differ.
3. A module the reader moved: its saved position is returned unchanged, while the others keep
   dagre's.
4. A saved position for a module that no longer exists is ignored, not returned.
5. The same input twice gives the same output (determinism).

`gui/src/state/positions.test.ts`:

1. What was remembered comes back for that project, and not for another project's key.
2. Forgetting clears that project and leaves another's alone.
3. Reading returns `{}` when storage is empty, when it holds text that is not JSON, and when the
   accessor throws (stub `localStorage` with a getter that throws) - the canvas must open either
   way.
4. Writing when storage throws does not throw.

Run: `npx vitest run src/lib/layout.test.ts src/state/positions.test.ts`
Expected: FAIL, the modules do not exist.

- [ ] **Step 3: Write the two modules**

`layout.ts` builds a `dagre.graphlib.Graph` with `rankdir: "LR"`, a node per module sized 180 by
48, an edge per flow, runs `dagre.layout`, and returns dagre's centres as top-left positions
(subtract half the size, as React Flow's dagre example does). A saved position replaces the
computed one; a saved entry for an unknown module is dropped.

`positions.ts` keeps one JSON object per project under the key `ddd-gui:positions:<project>`, and
wraps every read and write in `try`/`catch`, returning `{}` and doing nothing respectively when
storage refuses. Storage is a convenience: never let it fail a render.

- [ ] **Step 4: Add `getGraph` to the client**

Beside the other calls in `gui/src/api/client.ts`, in the same shape, with the generated
`GraphReply` type. Add a case to `client.test.ts` like the neighbouring ones, so the 100 % gate
still holds.

- [ ] **Step 5: Run the frontend gate**

Run, from `gui/`: `npm run schemas`, `npm run format`, `npm run lint`, `npm run typecheck`,
`npm test`, `npm run build`.
Expected: all clean, Vitest at 100 % over api, lib and state.

- [ ] **Step 6: Commit**

```bash
git add gui/package.json gui/package-lock.json gui/src
git commit -m "lay the modules out with dagre, remember where the reader dragged them, and fetch the graph"
git push
```

---

### Task 4: The canvas

**Files:**
- Create: `gui/src/components/ModuleNode.tsx`, `gui/src/components/FlowEdge.tsx`, `gui/src/screens/GraphPage.tsx`
- Modify: `gui/src/lib/route.ts`, `gui/src/app/App.tsx`, `gui/src/screens/ProjectPage.tsx`, `gui/src/styles/app.css`, `gui/src/styles/tokens.css`

**Interfaces:**
- Consumes: Task 3's `getGraph`, `laidOut`, `savedPositions`; milestone 1's `useProjectState` (for the revision) and `Banner`.
- Produces, for Task 6's journeys - keep these accessible names exactly:
  - the canvas is a region named `Modules`;
  - each module is a button whose accessible name is the component's name alone (`Controller`);
  - a module that did not load is a button named `<stem> (not loaded)`;
  - a module's badge carries `aria-label` `<n> errors` or `<n> warnings` (singular below two);
  - each arrow's label is a `<span>` with `aria-label` `<source name> to <target name>: <n> variables, <state>`, where the state is `error`, `warning` or `agreed`, and `<n> variables` is singular below two;
  - the tabs are links named `Graph` and `Table`; the address of the table is `/project?view=table`.

- [ ] **Step 1: Carry the tab in the route**

`gui/src/lib/route.ts`: the project route becomes `{ page: "project"; view: "graph" | "table" }`.
`parseRoute` reads `?view=table` on `/project` and defaults to `graph`; `hrefOf` writes
`/project?view=table` for the table and `/project` for the graph. Update `route.test.ts` with both
directions, and every place that builds a project route (`App.tsx`, the masthead, `StartPage`'s
`onOpened`) to pass the view.

- [ ] **Step 2: Write the node and the arrow**

`ModuleNode.tsx`: a React Flow custom node - a rounded box with the component's name as a
`<button type="button">`, a `Handle` of type `target` on the left and `source` on the right, and,
when the module holds errors or warnings, a badge carrying the count and the `aria-label` above.
A module that did not load is drawn muted with `not loaded` in place of its badge. Clicking the
button navigates to the component page.

`FlowEdge.tsx`: a React Flow custom edge drawn with `getBezierPath`, its stroke taken from the
severity (`var(--error)`, `var(--warning)`, `var(--rule)`), width 2 for a coloured arrow and 1.5
otherwise, and a label rendered in an `EdgeLabelRenderer` with the `aria-label` above.

The shape of the two, so that the names Task 6 selects on are not left to chance:

```tsx
export interface ModuleData extends Record<string, unknown> {
  name: string;
  loaded: boolean;
  errors: number;
  warnings: number;
  onOpen: (path: string) => void;
  faded: boolean;
}

export function ModuleNode({ id, data }: NodeProps<Node<ModuleData>>) {
  const badge = data.errors > 0 ? data.errors : data.warnings;
  const tone = data.errors > 0 ? "error" : "warning";
  return (
    <div className={`module ${data.loaded ? "" : "unloaded"}`} data-faded={data.faded}>
      <Handle type="target" position={Position.Left} />
      <button type="button" className="name" onClick={() => data.onOpen(id)}>
        {data.loaded ? data.name : `${data.name} (not loaded)`}
      </button>
      {data.loaded && badge > 0 && (
        <span className={`badge ${tone}`} aria-label={`${badge} ${tone}${badge > 1 ? "s" : ""}`}>
          {badge}
        </span>
      )}
      <Handle type="source" position={Position.Right} />
    </div>
  );
}
```

```tsx
export interface FlowData extends Record<string, unknown> {
  source: string;
  target: string;
  objects: readonly string[];
  severity: "error" | "warning" | "info" | null;
  disagreements: readonly GraphDisagreement[];
  faded: boolean;
}

// The state a reader hears: the arrow is in error, in warning, or its two ends agree.
const state = (severity: FlowData["severity"]) =>
  severity === "error" || severity === "warning" ? severity : "agreed";
```

The label's text is the number of objects; its `aria-label` is
`` `${data.source} to ${data.target}: ${n} ${n > 1 ? "variables" : "variable"}, ${state(data.severity)}` ``,
where `source` and `target` are the two modules' **names**, not their paths.

- [ ] **Step 3: Write the canvas**

`GraphPage.tsx`: fetches the graph with TanStack Query keyed by `["graph", revision]` - the same
pattern the component page uses for a file - places the modules with `laidOut(...)` over
`savedPositions(project)`, and renders `<ReactFlow>` with the custom node and edge types,
`fitView`, a `<Background>` and `<Controls>`, inside a region labelled `Modules`. While the first
answer is loading it shows `Drawing the project…`; an error shows milestone 1's error banner. When
the revision has no dictionary, a warning banner says the project has no dictionary and the
modules are drawn without arrows.

Import React Flow's stylesheet (`@xyflow/react/dist/style.css`) once, in `main.tsx`, beside the
other stylesheets.

- [ ] **Step 4: Put the tabs around it**

`App.tsx` renders `GraphPage` for `view: "graph"` and today's `ProjectPage` for `view: "table"`,
with a tab strip above them: two links, `Graph` and `Table`, the open one marked
`aria-current="page"`. The heading stays the project's name, above the tabs, so both tabs keep it.

- [ ] **Step 5: Look at it once**

Build the pages (`npm run build`), start `python -m ddd gui examples/demo/demo.ddd.json
--no-browser` from the repository root, and drive it with a throwaway Playwright script in the
scratchpad (`channel: "msedge"`, headless) that opens the printed address, waits for the region
`Modules`, and saves a screenshot. Expected: four modules, the arrows between them, no colour on
the untouched demo. Then change `ValueA`'s unit through the component page and screenshot again:
the arrow between SensorHub and Controller is red. Restore `examples/demo` afterwards
(`git checkout examples/demo`) and stop the server. Put both screenshots in the scratchpad and
name them in your report.

- [ ] **Step 6: The frontend gate**

Run, from `gui/`: `npm run format`, `npm run lint`, `npm run typecheck`, `npm test`,
`npm run build`. Expected: clean. The journeys of milestone 1 will fail until Task 6 updates them
for the tabs - do not run `npm run e2e` in this task, and say so in your report.

- [ ] **Step 7: Commit**

```bash
git add gui/src
git commit -m "open a project on a canvas of its modules, with an arrow per pair coloured by what its ends disagree about"
git push
```

---

### Task 5: Moving around the canvas

**Files:**
- Modify: `gui/src/screens/GraphPage.tsx`, `gui/src/components/ModuleNode.tsx`, `gui/src/components/FlowEdge.tsx`, `gui/src/styles/app.css`
- Create: `gui/src/lib/neighbours.ts`, `gui/src/lib/neighbours.test.ts`

**Interfaces:**
- Consumes: Task 3's `rememberPosition` and `forgetPositions`, Task 4's canvas.
- Produces, for Task 6's journeys: a textbox named `Search modules`; buttons named `Tidy` and
  `Fit`; a module faded by a search or a hover carries `data-faded="true"`; an arrow's tooltip is
  an element with `role="tooltip"` naming each object and, for a disagreement, its check.

- [ ] **Step 1: Write the failing test for the neighbour rule**

`gui/src/lib/neighbours.test.ts` over hand-written flows:

```ts
/** The modules to keep bright when one is hovered: itself, and whatever it produces for or reads from. */
export function neighboursOf(path: string, flows: readonly GraphFlow[]): Set<string>;
```

1. A module with no flows: the set holds only itself.
2. A producer: itself and its consumers.
3. A consumer: itself and its producers.
4. A module in the middle of a chain: both sides, and not the module two steps away.

Run: `npx vitest run src/lib/neighbours.test.ts` - Expected: FAIL.

- [ ] **Step 2: Implement it, and wire the interactions**

- Hovering a module fades every node and edge outside `neighboursOf`; leaving restores.
- The search box fades every module whose name does not contain the text, ignoring case, and every
  edge whose two ends are not both bright; Enter centres the first match with React Flow's
  `fitView({ nodes: [...] })`.
- Dragging a module calls `rememberPosition` on drag stop.
- `Tidy` calls `forgetPositions` and re-runs the layout; `Fit` calls `fitView`.
- Hovering an arrow opens a tooltip listing its objects, and for each disagreement the check and
  its message, in a `role="tooltip"` element.

- [ ] **Step 3: The frontend gate, and a second look**

Run the same npm commands as Task 4 Step 6, and re-run your look script with a drag, a search and
`Tidy`, keeping one screenshot of a hovered module with its neighbours bright. Expected: clean, and
the arrangement survives a revision (change a unit from the component page and come back).

- [ ] **Step 4: Commit**

```bash
git add gui/src
git commit -m "fade what is not a neighbour, find a module by name, and keep the arrangement the reader made"
git push
```
---

### Task 6: The journeys and the documentation

**Files:**
- Modify: `gui/e2e/skeleton.spec.ts`, `CHANGELOG.md`, `docs/command_line_interface.rst`, `docs/developer_documentation.rst`
- Test: the journeys themselves

**Interfaces:**
- Consumes: every accessible name Tasks 4 and 5 produce.
- Produces: `npm run e2e` green again, with the canvas covered.

- [ ] **Step 1: Bring milestone 1's journeys back to green**

The project screen now opens on the canvas, so the journeys that reach a component by clicking its
name still work - a module node is a button named exactly the component's name - but the one that
asserts the per-component error and warning counts must first open the `Table` tab. Change that
journey, and nothing else about the seven: their expectations are milestone 1's promises.

Run: `DDD_PYTHON=/c/git/ac11/ddd/.venv/Scripts/python.exe PLAYWRIGHT_CHANNEL=msedge npm run e2e`
Expected: 7 passed.

- [ ] **Step 2: Write the canvas journeys**

In the same file, after the others, each starting from `gui.address` as the others do:

1. **The demo opens on a canvas of its four modules.** The region `Modules` is visible, and each
   of Controller, SensorHub, UserInterface and EventLogger is a button on it. Every arrow's label
   ends in `agreed`.
2. **A disagreement colours its arrow.** Open Controller, change `ValueA`'s unit to `rpm`, go back
   to the project: the label `SensorHub to Controller: 1 variable, error` is visible. Put the unit
   back and it reads `agreed` again.
3. **An arrow says what is wrong.** With the mismatch standing, hover the arrow's label and expect
   a `role="tooltip"` containing `ValueA` and `definition-mismatch`.
4. **A module opens.** Clicking the Controller node lands on its component page, with the heading
   `Controller`; the browser's back button returns to the canvas.
5. **The table is one tab away.** Clicking `Table` shows the component table of milestone 1 and the
   address ends in `?view=table`; a reload keeps it.
6. **The arrangement is kept.** Drag a module, save the file from outside so a new revision
   arrives, and the module is still where it was dragged; `Tidy` puts it back where dagre wants it.

Run the suite twice, as milestone 1's convention asks: `npm run e2e` twice, 13 passed each time,
no stray output.

- [ ] **Step 3: The documentation**

- `CHANGELOG.md`, in the `## Unreleased` section's `ddd gui` entry: the project now opens on a
  canvas of its modules, with an arrow per producing-consuming pair coloured by the worst
  disagreement between its ends, and the component table one tab away.
- `docs/command_line_interface.rst`, the `ddd gui` paragraph: say the same in one sentence, in that
  page's voice.
- `docs/developer_documentation.rst`, "The browser interface": name the two packages the canvas
  brings, `@xyflow/react` for the canvas and `@dagrejs/dagre` for the layout, and that both are MIT
  like every other bundled package.

Run: `python -m pytest tests/test_documentation.py --no-cov`, then the sphinx build with the
`JAVA` and `PLANTUML_JAR` of the global constraints.
Expected: pass, `build succeeded`.

- [ ] **Step 4: Commit**

```bash
git add gui/e2e CHANGELOG.md docs
git commit -m "drive the canvas end to end, and say in the documentation what the project screen now shows"
git push
```

---

### Task 7: Milestone gate

Done by the controlling session, not by an implementer.

- [ ] **Step 1: The whole gate, from a clean build**

```bash
rm -rf src/ddd/gui/static gui/src/generated gui/test-results
python -m pytest && python -m ruff format --check . && python -m ruff check . && python -m mypy
python -m sphinx -M html docs "$SCRATCH/docs_out" -W
cd gui && npm ci && npm run schemas && npm run lint && npm run typecheck && npm test && npm run build
DDD_PYTHON=/c/git/ac11/ddd/.venv/Scripts/python.exe PLAYWRIGHT_CHANNEL=msedge npm run e2e
```

- [ ] **Step 2: Measure what the spec promises at size**

Generate a project of 200 components with a few flows each into the scratchpad (a short script, not
committed), open it with `ddd gui`, and record how long the endpoint takes and how long the canvas
takes to draw. Spec section 5.7 asks for under a second; record what it is, and if it is worse, say
so rather than quietly leaving it.

- [ ] **Step 3: Screenshots for the maintainer**

With `ddd gui examples/demo/demo.ddd.json --no-browser` running, capture the canvas as it opens,
the canvas with a mismatch colouring one arrow, and a module hovered with its neighbours bright.
Leave `examples/demo` unchanged.

- [ ] **Step 4: Hand over**

The gate's result, the screenshots, what the milestone does and does not do, every ruling taken
while executing this plan, and what is left for the milestones after it. Ask before opening a pull
request; do not dispatch CI.

---

## Progress log

Started is local time on 18 September 2026; the milestone ran overnight while the maintainer slept. Duration runs from dispatching the task to dispatching the next, reviews and fix rounds included; several reviews ran beside the next task, so the durations overlap by design. Tokens are those the task's agents reported, implementer and reviews together; the controlling session is not counted.

| Task | Started | Duration | Tokens | Notes |
| --- | --- | --- | --- | --- |
| 1 | 01:17 | 52 min | 639,678 | The graph of a revision. Its review found a Critical the tests could not: a variable one component declares `local` can still be read by another - the analysis reports `local-conflict` and keeps the reference - so such a pair drew an ordinary arrow. Fix round 1 also stopped a `KeyError` when a module's name has no component in the dictionary. |
| 2 | 02:09 | 28 min | 432,760 | `GET /api/graph`. The paths are the absolute ones `/api/state` already speaks, which the spec now says; a relative path could not be compared with a finding's note, which is where colouring would have stopped. |
| 3 | 02:37 | 29 min | 428,806 | The dagre layout, the remembered arrangement and the client call. `@xyflow/react` 12.11.6 and `@dagrejs/dagre` 3.1.1, both MIT. It also fixed the licence script, which crashed on an unmet optional peer dependency. |
| 4 | 03:06 | 44 min | 386,272 | The canvas: modules, arrows, colours, the tabs, a click opening a module. Its review (opus) found the "no dictionary" banner asserting what the page could not know - the same shape as a project whose components simply share nothing. |
| 5 | 03:50 | 58 min | 556,877 | Task 4's findings and then hover fading, search, dragging that is remembered, `Tidy`, `Fit` and the arrow tooltip. The banner now follows a `dictionary` flag the endpoint answers. Two accessible names moved deliberately, and Task 6 was dispatched with them. |
| 6 | 04:48 | 28 min | 278,087 | Six canvas journeys, and milestone 1's seven brought back to green (two needed the `Table` tab). The documentation: the changelog, the command page and the developer page. Reviewed by the controller reading the diff rather than by a review seat, at 05:35. |
| 7 | 05:16 | 35 min | - | The gate from a clean build, the 200-module measurement, the screenshots and this log. |

## Left open by the implementers

Nothing below blocks the branch; each says where it belongs.

**Before this milestone is called done**
- Spec 5.7 is not met at size. Measured on a generated project of 200 components and 600 flows:
  `ddd check` 656 ms, the session's analysis 190 ms, `graph_of` 18 ms, `GET /api/graph` 35-40 ms
  over HTTP even with a long poll open - but the canvas takes about 6.5 s to appear in headless
  Edge. The cost is the page drawing 200 nodes and 600 arrows, each arrow's label portalled on its
  own, not the server. Fewer DOM nodes per arrow, or virtualising what is off screen, is the fix.
- At 200 modules the canvas also opens unframed: the screenshot taken when the first node became
  visible shows mostly empty grid with a few arrows crossing it, so the initial `fitView` either had
  not settled or does not frame a graph that size. Whoever takes the rendering also takes this.
- A failed first read of a *new* revision still replaces the canvas with a banner: TanStack drops
  its placeholder once a new key settles to error. "The server stopped" is covered, because the
  revision does not advance then. What to draw while a new revision's first read is failing is a
  deliberate choice nobody has made yet.

**Milestone 3 (the visual design), which restyles this canvas**
- `stateOf`'s three colours, the badge and the node box live in `gui/src/styles/app.css` beside
  milestone 1's; the canvas deliberately invents no visual style of its own.
- A module that did not load shows `not loaded` but not the loader's message on hover, which spec
  5.6 asks for: `/api/graph` does not carry it. Clicking the module reaches it on the component
  page.
- A file that does not parse at all never becomes a module: the session cannot tell what kind of
  file it is, so it has kind `unknown` and the canvas's `component` filter drops it. A file that
  parses and fails its schema does appear, marked not loaded. Either the session learns a broken
  file's kind from the project's includes, or spec 4.2 is narrowed to files that parse.

**Whenever the file is next touched**
- `tests/test_graph.py`: two loaded modules sharing one name collapse in `paths_by_component`; a
  diagnostic carrying several notes fans out into one disagreement per note (no check emits more
  than one today). Both are commented where they live.
- `gui/src/lib/layout.ts`: no test pins the centre-to-top-left conversion, so dropping the
  half-size subtraction would still pass every layout test.
- `gui/src/state/positions.ts`: `isRecord` accepts an array from storage, and `rememberPosition`
  serialises inside the same `try` as the write, so a programming error would be swallowed with a
  storage failure.
- `gui/src/screens/GraphPage.tsx`: one tooltip slot is shared by the keyboard-focused arrow and the
  mouse-hovered one.
- No Python test pins "two resolved modules that share nothing answer `dictionary: true`"; the
  screenshot shows it.

**On the branch below this one** (`feature/gui-api-contract`, not yet a pull request): its review
left two Important findings unfixed overnight - three response helpers that hand-build a dict a
model then re-validates, and `DictionaryReply` publishing the file format's whole type tree inside
the API schema (23 of 45 definitions). They were parked at 02:00 to keep the canvas on the critical
path, and the graph's own additions sit beside them.

## Rulings made while executing the plan

The maintainer approved the spec by delegation and slept; every decision below was the controlling session's, and each says what it costs if it was wrong.

1. the maintainer delegated the spec's approval ("Can you approve the spec and continue") and went to sleep, so the brainstorming skill's review gate is met by the controller's own self-review, recorded in the spec's commit — cost if wrong: a spec they would have changed, found in the morning.
2. work in place in the main checkout on feature/module-graph, no linked worktree, as milestone 1 did — cost if wrong: a second session in this checkout would collide.
3. the graph stacks on feature/gui-api-contract rather than on master, because its endpoint is declared in the pydantic contract that branch introduces — cost if wrong: two branches to merge in order.
4. model per task rather than the cheapest everywhere, as the maintainer asked: sonnet for Tasks 1, 2, 3 and 6 (transcription and tests from a detailed brief), opus for Tasks 4 and 5 (React Flow and the interaction, described in prose rather than given as code), reviews on sonnet with opus for Task 4's — cost if wrong: more of the weekly limit than sonnet throughout.
5. agents one at a time in the background, pushing each task, no pull request and no CI dispatch overnight — cost if wrong: nothing but the wait.
6. no whole-branch review at the end tonight; the per-task reviews stand, and the maintainer reads the branch in the morning — cost if wrong: a cross-task defect found later than milestone 1's were.
7. an implementer may run beside a read-only reviewer when their files do not overlap (Task 1 writes src/ddd/graph.py and tests/test_graph.py; the API review reads api.py, contract.py and the frontend's api files), never two implementers — the maintainer is asleep and wall-clock is the scarce thing tonight — cost if wrong: a reviewer reading a file mid-change, which a re-read settles.
8. both are fixed in one round on that branch before the graph's Task 2 touches the same files, and the branch is then merged into feature/module-graph so the graph builds on the fixed contract — the alternative, fixing them later, means two branches editing api.py and contract.py in the same regions — cost if wrong: one merge commit in the graph branch.
9. the fix round waits for Task 1 to finish rather than running beside it: the two branches cannot be checked out at once in this working tree, and the venv's editable install points at this checkout, so a linked worktree would test the wrong tree — cost if wrong: about half an hour of wall clock tonight.
10. the contract branch's two Important findings are parked until the morning rather than fixed tonight. It is 02:00, the maintainer wakes at about 07:00 and asked to see the canvas working; fixing them costs a branch switch, a fix round and a re-review, about forty minutes of the critical path, and the graph's Task 2 can add its models beside the helpers as they stand, leaving a small mechanical conflict to resolve when the branches merge. Cost if wrong: the contract branch carries two known findings overnight, and Task 2's additions have to be re-touched when they are fixed.
11. from here the priority is a visible canvas by morning - Tasks 2, 3 and 4 - and Tasks 5 and 6 only if the clock allows; a task review may run beside the next task's implementer when their files do not overlap. Cost if wrong: interaction and journeys land in the morning instead of overnight.
12. accept absolute paths and correct the spec instead of the code (commit d570a8d) — the page treats the path as an opaque identity it hands back to /api/file, and matching what /api/state says is what keeps the two answers joinable; a relative path would also have to be resolved before it could be compared with a note's location, which is where colouring would silently stop — cost if wrong: the JSON shows a machine's directory layout, which the page never displays.
13. fold the Important and the four cheap Minors into Task 5's dispatch instead of a separate fix round and re-review — it is 03:45, Task 5 rewrites the same two files, and its review then covers both — cost if wrong: a defect in the fixes is caught one review later than the loop would.
14. spec 5.6's "the loader's message when a module that did not load is hovered" is parked for a later milestone — the message is not in /api/graph, the node already says "not loaded", and clicking it opens the component page where milestone 1 shows the loader's reason — cost if wrong: one hover short of the spec until then.
15. the spec's example answer gains the dictionary field (commit ad3615a) rather than leaving the record behind the code — cost if wrong: none.
16. park that race rather than open a fix round at 05:00 — the reviewer approved the task, no data is lost (positions are already in storage), and it needs a deliberate choice about what to render while a new revision's first read is failing; it goes to the plan's "Left open" for the milestone after — cost if wrong: a reader who hits a transient failure on the poll that carries a new revision loses pan, zoom and search, and reloads.
17. no review seat for Task 6 at 05:35; the controller read the diff instead. skeleton.spec.ts gains 131 lines and deletes none, so no milestone 1 expectation was loosened; the two forced changes are a Table-tab click each, commented; the new journeys assert the arrows' spoken sentences (`... 2 variables, error` then `agreed`), the tooltip's check, the module opening, the tab's address and the arrangement surviving a revision. Cost if wrong: a defect in the journeys themselves reaches the maintainer unreviewed, with the suite passing twice as the only guard.
18. spec 5.7's "under a second" is not met at 200 modules and the milestone ships without meeting it. The measurement says where the time goes (the page, not the endpoint), the canvas is usable at the sizes the maintainer will try it on first, and the fix - fewer DOM nodes per arrow, or virtualising what is off screen - is a rendering decision that belongs with the milestone that styles the canvas. Recorded in the plan's "Left open" with the numbers. Cost if wrong: a project of that size opens in about six seconds until then.
