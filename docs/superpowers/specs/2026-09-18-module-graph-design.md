# The module graph

The project screen of `ddd gui`: the components of a project as a canvas, the variables flowing
between them as arrows, and a disagreement between a producer and a consumer as the colour of the
arrow that carries it.

This is milestone 2 of the web GUI designed in `2026-09-17-web-gui-design.md`, whose milestone 1
(the walking skeleton) is pull request #45. It takes the place milestone 2 held there: the visual
design moves behind it and restyles two screens instead of one, so that the canvas can be seen
working - and shown to the developers whose usability sessions the design milestone needs - before
anyone chooses a look. The milestones after it keep their order and shift by one.

## 1 What this adds

1. `GET /api/graph` answers, for one revision, the project's modules and the flows between them,
   each flow carrying the variables that travel it and the worst disagreement between its two
   modules.
2. The project screen opens on a canvas of those modules, laid out left to right from producers to
   consumers, drawn with React Flow.
3. An arrow is red when the two modules it joins disagree with an error, orange with a warning, and
   plain otherwise. It is labelled with the number of variables that flow along it, and hovering it
   lists them with what is wrong.
4. A module shows its name and, when it has findings of its own, a badge counting them. A
   description file that does not parse is shown as a module marked `not loaded`, which the
   component table of milestone 1 cannot do.
5. Hovering a module fades everything that is not one of its direct neighbours. Clicking it opens
   the component page of milestone 1, unchanged.
6. A search box finds a module by name. A `Tidy` button lays the canvas out again.
7. The component table of milestone 1 stays, one tab away.

## 2 Decisions already taken

- **Modules only.** The canvas holds components. Variables are the arrows' labels, never nodes of
  their own.
- **No grouping boxes.** One flat canvas for the 60 to 200 modules a real project holds, with
  search and neighbour highlighting instead of subsystem boxes.
- **One arrow per pair of modules**, counting its variables, not one arrow per variable.
- **The server computes the graph**, in `src/ddd/graph.py`, beside the analysis rather than inside
  the GUI. Which findings mean "these two disagree" is DDD's knowledge, and it stays in Python
  under the 100 % gate; the endpoint serialises what that module returns, and a command or an
  editor feature can call the same function later. The page draws what it is given.
- **React Flow** (`@xyflow/react`, MIT) draws the canvas and **dagre** (`@dagrejs/dagre`, MIT) lays
  it out. Both licences are on the list the build enforces; `elkjs`, the other layout engine, is
  EPL-2.0 and would be refused.
- **The arrangement is the reader's, and local.** Modules can be dragged, and their positions are
  remembered in that browser for that project.

## 2.1 One backend, two front doors

The GUI and the language server answer the same questions about a project, and they answer them
with the same code. Only `ddd/lsp/server.py` and `ddd/lsp/protocol.py` are about the protocol; the
rest of `ddd/lsp/` is what an editor needs to know, and it is a library like any other. Milestone 1
already reads `lsp.diagnostics` for its runs and its per-file grouping, and `lsp.discovery` for the
build records; the edit engine holds the layout helpers the server's quick fixes use, so there is
one implementation of the layout rules.

This milestone keeps that rule, and the ones after it are bound by it:

- the graph's flows come from the resolved dictionary, not from a second traversal of the files;
- milestone 4's component editor takes what a variable resolves to from `lsp.hover`, and the places
  one name is declared from `lsp.navigation`, rather than deriving either again;
- milestone 7's one-click fixes are `lsp.edits`, the same quick fix the editor offers, applied
  through the edit engine.

What cannot be shared is the lifecycle. An editor owns buffers that were never saved and pushes
every keystroke; the GUI reads the files on disk and polls them. Both drive the same analysis, and
neither knows about the other - one day `ddd lsp` could serve the pages too, so that an editor and
a browser share one analysis of one project, which is worth revisiting when the GUI leaves preview.

## 3 Out of scope

Variables as nodes; boxes grouping modules by folder or by include; a layout shared through git;
exporting the canvas as an image; filtering by raster or section; editing anything on the canvas.
The component page, the start page and the edit engine are milestone 1's and do not change.

## 4 The data

### 4.1 Where it comes from

The resolved dictionary of the revision already says, for every object, the component that owns it
(`owner`) and the components that read it (`consumers`); the session already lists the project's
files with their name, kind and finding counts. The graph is those two joined, so it costs no
analysis of its own - it is read from the revision the session has already published.

### 4.2 A module

One component of the project, identified by its description file's path as `GET /api/state`
spells it: the absolute path in posix form, which the page hands back to `/api/file` unchanged and
never shows. The findings a module carries locate themselves by that same path, which is why the
graph speaks it rather than a prettier relative one. It carries the component's
name, its finding counts by severity, and whether its file was loaded. A file that does not parse
has no component name; the module is named by the file's stem and marked not loaded.

### 4.3 A flow

One pair of modules with at least one object owned by the first and read by the second. It carries
the names of those objects, sorted, and the disagreements between the two modules. Objects a
component owns and reads alone (`local`) make no flow, and an object nobody reads makes none
either. A consumer whose object has no owner makes no flow: the analysis already reports it on the
consumer as `missing-producer`, and the module's badge shows it.

### 4.4 A disagreement

A finding located on one module's declaration of an object, carrying a note that points at another
module's declaration of the same object. That is how the analysis records that two components
declare one object differently, whatever the check is called, so a check added later colours
arrows without the graph being taught about it.

A flow's severity is the worst of its disagreements, error before warning before info: `error`
paints the arrow red, `warning` orange, and anything else leaves it plain. Every disagreement is carried with its check, its severity, its
message and the object it is about, so that hovering the arrow says what is wrong rather than only
that something is.

### 4.5 The endpoint

`GET /api/graph`, answering `200` with

```json
{
  "revision": 7,
  "modules": [
    {
      "path": "C:/work/demo/components/controller.ddd.json",
      "name": "Controller",
      "loaded": true,
      "findings": {"error": 1, "warning": 0, "info": 0}
    }
  ],
  "flows": [
    {
      "from": "C:/work/demo/components/sensor_hub.ddd.json",
      "to": "C:/work/demo/components/controller.ddd.json",
      "objects": ["ValueA", "ValueB"],
      "severity": "error",
      "disagreements": [
        {
          "object": "ValueA",
          "check": "definition-mismatch",
          "severity": "error",
          "message": "'ValueA' is declared differently by component 'Controller' than by 'SensorHub' (unit: 'rpm' != '%')"
        }
      ]
    }
  ]
}
```

`severity` is `null` when a flow has no disagreement, and `disagreements` is then empty. Without an
open project the endpoint answers `409` with the code `no-project`, as the other endpoints do. When
the analysis produced no dictionary - a plugin raised, which spec 6.10 of milestone 1 already
describes - `modules` is still the revision's components and `flows` is empty; the page says the
project has no dictionary.

The request and the answer are declared in `src/ddd/gui/contract.py` like every other endpoint, and
the page's types are generated from it.

## 5 The screen

### 5.1 The canvas

Modules are laid out left to right, producers before consumers, by dagre, over the modules sorted
by path so that one project always lays out the same way. The layout runs on every revision; a
module the reader has moved keeps its own position, and one they have not follows the layout. A
module that disappears takes its remembered position with it.

Positions are remembered in the browser, keyed by the open project's path, and `Tidy` forgets them
and lays the canvas out again. Browser storage is a convenience: the canvas opens correctly when it
is empty, unreadable or refused.

### 5.2 A module

A rounded node with the component's name and, when the module holds errors or warnings, a badge
counting them: red when any is an error, otherwise orange. Findings of severity `info` leave the
node plain, as they leave milestone 1's table. A module whose file did not load shows `not loaded` in
place of its badge and is drawn muted. Each node is a button whose accessible name is the module's
name, so the journeys of milestone 1's kind can find it and a reader can reach it by keyboard.

### 5.3 An arrow

A curved link from the producer's output side to the consumer's input side, labelled with the
number of objects that flow. Red, orange or plain, as section 4.4 says. Hovering it shows the
objects it carries and, for each disagreement, the check and its message.

### 5.4 Moving around

- Hovering a module fades every module and arrow that is not the module or one of its direct
  neighbours.
- Clicking a module opens its component page. The address carries the project and the file, as
  milestone 1's routes already do, so the back button returns to the canvas.
- The search box fades every module whose name does not contain what was typed, matching without
  regard to case, and every arrow that does not join two modules still shown; Enter centres the
  first match.
- `Tidy` re-runs the layout.
- The canvas pans and zooms, and a `Fit` control brings the whole project back into view.

### 5.5 The table tab

The component table of milestone 1, unchanged, on a `Table` tab beside `Graph`. The address says
which tab is open, so a reload and the back button keep it.

### 5.6 What the reader sees when something goes wrong

- **A module does not load.** It is a node marked `not loaded`, with the loader's message when it
  is hovered, and no arrows.
- **The project has no dictionary.** A banner says so, the modules are shown, and there are no
  arrows.
- **The server stopped.** The canvas keeps what it has and milestone 1's banner appears, as on
  every other screen.

### 5.7 How big it may be

The canvas is drawn for projects of 60 to 200 modules. Laying out and drawing 200 modules and 600
flows must stay under a second on a developer's machine, measured once and recorded; the endpoint
itself reads a revision the session already has, so it adds no analysis.

## 6 Testing

- **The endpoint**, in Python, under the 100 % line and branch gate: a project whose modules all
  agree; a disagreement colouring one flow; two objects flowing between the same pair, one of them
  in disagreement, and the flow taking the worst severity; a local object making no flow; an object
  with no owner making none; a module whose file does not parse; a project with no dictionary; and
  no open project.
- **The page's logic** - the layout adapter and the remembered positions - under the frontend's
  100 % gate, screens excluded as in milestone 1.
- **The screen**, end to end in Chromium on Windows and Linux, over a copy of `examples/demo`:
  the four modules and the arrows between them; changing `ValueA`'s unit turns the
  SensorHub-Controller arrow red and putting it back makes it plain; hovering an arrow names the
  object and the check; clicking a module opens its component page; the `Table` tab still lists the
  components; a dragged module stays where it was put after a revision, and `Tidy` puts it back.

## 7 Packaging and documentation

`@xyflow/react` and `@dagrejs/dagre` are pinned exactly like every other frontend dependency, and
their licences are checked by the build as all bundled licences are. The changelog's preview entry
for `ddd gui` gains the canvas; the command page's paragraph says the project opens on a graph of
its modules; the developer page needs no change beyond what the dependency list says for itself.

## 8 Evidence

- `ddd.ir.ResolvedObject.owner` and `.consumers` carry the producer and the readers of every
  object; `ResolvedComponent.name` and the session's `SourceFile` give the modules their names and
  paths.
- The analysis records a disagreement as a finding on one declaration with a note pointing at the
  other: `_compare` and `_compare_limits` in `src/ddd/analysis.py`, mirrored onto both files by
  `group_findings` in `src/ddd/lsp/diagnostics.py`.
- `@dagrejs/dagre` is MIT (github.com/dagrejs/dagre); `elkjs` is EPL-2.0 (github.com/kieler/elkjs),
  which the build's allow-list refuses.
