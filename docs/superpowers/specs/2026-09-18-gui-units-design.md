# Units in the GUI

The unit of a variable in `ddd gui`: set on the variable rather than on one of its declarations,
from a panel that lists every declaration of it, with a disagreement between a producer and its
readers settled by choosing the unit the variable should have. Building it also sets the design
system every later screen is built with: the visual style, a widget library, a workbench for the
widgets and screenshot tests of them.

This is part 1 of three that take the GUI one field deep before widening it, and it replaces the
order of the milestones after the module graph in `2026-09-17-web-gui-design.md` section 5.
Instead of a design milestone followed by horizontal ones - project home, component editor,
tables, shared files, fixes - the GUI grows by field:

1. **Units, the field** - this spec.
2. **Units, the project** - a page of every unit in use and where, renaming a unit everywhere,
   and the units vocabulary.
3. **The other fields** - part 1's panel carried to the other eleven keys the language server's
   reconcile actions already settle.

Each part gets its own spec, plan and pull request. The rest of the old table - the curve, map and
axis tables, the shared project files, the comparison of deliveries, the hardening and the pilot -
keeps its place after part 3 and is planned again when it is reached. The usability sessions the
design milestone held are replaced by the maintainer's own review of clickable mockups, kept
beside this spec in `2026-09-18-gui-units/`.

## 1 What this adds

1. Selecting a declaration on the component page opens a **panel for its variable** beside the
   table: the variable's kind, its datatype or type, its producer, every declaration of it - the
   component, whether it produces, reads or keeps the variable local, and the unit it states - and
   the variable's findings.
2. The panel has **one unit control**, "Unit of ValueA": a picker listing first the units the
   variable's declarations state, each with the components stating it, then either the project's
   units vocabulary with each unit's description or, without one, the other units the project
   uses, each with how many variables use it. Any unit can be typed. In a project with a
   vocabulary, a unit outside it is flagged under the picker before it is applied.
3. Choosing a unit marks the declarations it would change and says how many files that is.
   **Show changes** lists the exact lines of each file before and after. **Apply** writes every
   file or none, through the edit endpoint milestone 1 built.
4. A red or orange **arrow on the canvas** opens the same panel, beside the canvas, for the
   variables it carries.
5. A unit a declaration takes from its **declared type** is shown with the type it comes from and
   cannot be changed from the panel: the type fixes it, and a declaration naming the type may not
   state a unit of its own.
6. **The design system**: the tokens of the chosen style, React Aria Components wrapped once under
   the page's own CSS, a Ladle story for every widget and every state of the panel, and screenshot
   tests of those stories. The start page, the canvas, the component table and the component page
   are restyled with it.

## 2 Decisions already taken

- **The unit belongs to the variable.** A variable has one unit, and its producer owns it: setting
  one reader's unit on its own is exactly how a disagreement is made. The panel therefore sets the
  unit of every declaration at once, and milestone 1's inline unit editor in the table is retired -
  a unit cell opens the panel instead. Milestone 1's spec section 6.1 item 4, "a declaration's unit
  can be changed in the table", is superseded by this. An editor such as VS Code still edits a
  single declaration.
- **Resolver B, a panel for the variable**, over a popover at the finding (cramped with many
  readers, and only reachable from a finding) and a guided dialog (three steps for one value, and it
  covers the page). The dialog's review of the exact lines stays, as a link rather than a step.
- **Style 3, the current look refined**, over a compact grid-lined style and a roomier one: medium
  density, the colours milestone 1 chose, and the least restyling of the screens that exist.
- **React Aria Components** (Adobe, Apache-2.0) for the widgets, over Headless UI (no table and no
  tooltip) and hand-written widgets (an accessible combobox and popover is where hand-written
  interfaces break, and part 3 multiplies them). Radix was not a candidate: it has no combobox.
- **Ladle** (MIT) as the workbench, over Storybook: it builds with Vite like the pages, starts in
  about a second, and its stories are in the format Storybook reads, should it ever be outgrown.
  Widgets are developed there on mock data with hot reloading, which covers design section 8's
  deferred development server without relaxing the server's origin check.
- **Screenshot tests in one place**: Playwright compares each story with a reference image, and the
  references come from Playwright's Linux Docker image alone, since Windows and Linux render fonts
  differently. CI and a Linux machine with Docker run them; a Windows machine runs every other test
  and skips these.
- **The server decides what a change touches.** Which declarations one unit reaches, and which of
  them refuse it, is DDD's knowledge, and it stays in Python under the 100 % gate, in the code the
  language server's quick fixes already use. The page draws what it is given.
- **One write path.** The server previews a change as the request `POST /api/edit` already takes,
  and the page posts that request unchanged, so the all-or-nothing write, the stale refusal and the
  verification are the ones milestone 1 tested.

## 3 Out of scope

- The units page, renaming a unit and editing the vocabulary (part 2).
- Every key but `unit` (part 3). The panel lists the variable's other findings but offers no fix
  for them yet.
- Units stated on scalar types and structure members, and the types themselves (the shared files).
- Undo, and a dark theme.
- The canvas's edge routing. Two of the demo's seven arrows are drawn along the row of other
  arrows and behind modules, their labels on top of other labels, because the canvas draws plain
  curves between handles rather than the routes dagre computes. That is fixed on its own, not
  restyled away here.

## 4 The server

### 4.1 Setting a key on every declaration

`ddd.lsp.edits.settle(built, name, key, raw)` answers the edit that makes every declaration of the
variable `name` state `raw` as its `key`, or refuses. It is the rule behind the language server's
"Apply this unit to N other declarations", made public under a name that says what it does, and
that action calls it; the language server's existing tests are the guard that its answers do not
change.

- `key` is one of `PROPAGATED_KEYS`. Part 1's page asks for `unit` alone.
- `raw` is the JSON text of the value, or `None` for no value: the key is then removed from every
  declaration that states it.
- The declarations are `Index.declarations[name]`. One that already states `raw` is left alone; one
  that states something else gets a `set` operation at `<pointer>.<key>`, and one that states
  nothing gets the member added, as `set` already does. A key in `DEFERRED_KEYS` that a declaration
  leaves out stays left out, as the quick fixes treat it.
- It refuses, naming the declaration, when a declaration names a declared type that fixes the key
  to another value (`fixed-by-type`); when a declaration's file no longer reads as JSON
  (`unreadable`); and when a declaration's kind cannot carry the key (`invalid`).

### 4.2 The revision keeps the index

`lsp.diagnostics.Run` also keeps the navigation index built from the workspace its analysis
loaded, `None` when the workspace did not load, and the session's `Revision` keeps the index of the
run it takes its dictionary from. The endpoints below read a revision the session has already
published, so none of them analyses anything.

### 4.3 The endpoints

Declared in `src/ddd/gui/contract.py` like every other endpoint, with the page's types generated
from them. Without an open project each answers `409` `no-project`, as the others do.

`GET /api/variable?name=ValueA` answers every declaration of one variable:

```json
{
  "revision": 7,
  "name": "ValueA",
  "declarations": [
    {
      "path": "C:/work/demo/components/sensor_hub.ddd.json",
      "pointer": "component.interface[2].definition",
      "component": "SensorHub",
      "role": "produces",
      "stated": {"kind": "\"measurement\"", "datatype": "\"uint8\"", "unit": "\"%\""},
      "type": null,
      "fixed": {}
    },
    {
      "path": "C:/work/demo/components/controller.ddd.json",
      "pointer": "component.interface[0].definition",
      "component": "Controller",
      "role": "reads",
      "stated": {"kind": "\"measurement\"", "datatype": "\"uint8\"", "unit": "\"rpm\""},
      "type": null,
      "fixed": {}
    }
  ],
  "findings": []
}
```

- `role` is `produces`, `reads` or `local`.
- `stated` holds the JSON text of `kind` and of every key of `PROPAGATED_KEYS` the declaration
  states, spelled as the file spells it. Part 3 reads its other keys from the same answer.
- `type` names the declared type a declaration names, and `fixed` holds the JSON text of each key
  that type fixes - `datatype`, `unit`, `conversion` and `limits`.
- `findings` are those located on any of the declarations, as `GET /api/state` spells them.
- A name no declaration has answers `404` `not-found`.

`GET /api/units` answers what the picker offers:

```json
{
  "revision": 7,
  "vocabulary": [{"unit": "rpm", "description": "rotational speed, revolutions per minute"}],
  "used": [{"unit": "%", "variables": 5}, {"unit": "Hz", "variables": 4}]
}
```

`vocabulary` is `null` when the project declares none. `used` lists every unit a declaration
states, each with the number of variables stating it, most used first. No unit is not listed; the
picker offers it itself.

`GET /api/settle?name=ValueA&key=unit&raw=%22%25%22` previews a change and writes nothing:

```json
{
  "revision": 7,
  "edit": {
    "changes": [
      {
        "file": "C:/work/demo/components/controller.ddd.json",
        "fingerprint": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
        "operations": [
          {"op": "set", "pointer": "component.interface[0].definition.unit", "raw": "\"%\""}
        ]
      }
    ]
  },
  "files": [
    {
      "path": "C:/work/demo/components/controller.ddd.json",
      "hunks": [{"line": 14, "before": ["          \"unit\": \"rpm\","], "after": ["          \"unit\": \"%\","]}]
    }
  ]
}
```

- `edit` is exactly the body `POST /api/edit` takes, each file with the fingerprint the revision
  read it at, so a file saved since is refused as `stale` when the page applies it.
- `files` gives each file's changed lines before and after, numbered as the file stands, for
  **Show changes**. It is computed by applying the operations in memory with the edit engine,
  never by writing.
- Without `raw`, the preview removes the key: no unit.
- A declaration that already agrees contributes nothing; when every one agrees, `changes` and
  `files` are empty.
- `settle`'s refusals answer `409` with their code and a message naming the declaration. A `key`
  settle may not write, or a `raw` that is not one JSON value, answers `400` `bad-request`, and a
  name no declaration has `404` `not-found`.

## 5 The screens

### 5.1 The design system

The tokens of style 3 replace milestone 1's in `gui/src/styles/tokens.css`, and nothing else in the
page holds a colour or a size:

| Token | Value |
| --- | --- |
| type | "Segoe UI", system-ui; 13.5 px body, 20 px titles; "Cascadia Mono", Consolas for code |
| ink, quiet ink | `#1d2a2f`, `#5b6b71` |
| ground, surface, rule | `#f7f9f9`, `#ffffff`, `#d9e2e5` |
| accent, its focus ring, selection | `#0e6b7c`, `rgba(14, 107, 124, .16)`, `#e3f1f3` |
| error on its ground | `#b3261e` on `#fdecea` |
| warning ("will change") on its ground | `#7a4f00` on `#fff4dc` |
| radius: controls, chips, frames | 6 px, 10 px, 10 px |
| spacing: cells, panels, gaps | 6 px 10 px, 12 px 14 px, 14 px and 8 px |
| popover shadow | `0 8px 24px rgba(20, 30, 35, .14)` |

React Aria Components is pinned exactly, like every dependency of the page, and its licence and
those of its own dependencies are checked by the build like every bundled licence. It is wrapped
once in `gui/src/ui/` - Button, ComboBox, Table, Popover, Tooltip, Tabs, Chip, Banner and Panel -
styled with the page's CSS, and the screens import widgets from `ui/` alone. The canvas's module
and arrow colours come from the same tokens.

### 5.2 The component page

The declarations table is the React Aria Table: a row is selected by a click or from the keyboard,
and the address carries the selected variable (`...&variable=ValueA`), so a reload and the back
button keep the panel open, as milestone 1's routes keep the page. A unit cell is a button that
selects its row and moves the focus to the picker.

The panel shows, top to bottom, the variable's name; its kind, its datatype or type and its
producer, or that it has none or is local; a table of its declarations with the component, the role
and the unit, a unit its type fixes reading "rpm, from Speed_t"; the variable's findings; the unit
picker; what the chosen unit would change - "Changes 1 file: controller.ddd.json", or "Nothing to
change"; **Show changes**; and **Apply to N files**. Choosing a unit fetches its preview and marks
each declaration it would change "will change". Apply posts the preview's `edit`, and the panel
then follows the revision the edit answered with.

### 5.3 The unit picker

A React Aria ComboBox that accepts any typed value, listing:

1. **Declared for ValueA**: each distinct unit the variable's declarations state, with the
   components stating it, "no unit" among them when a declaration states none.
2. With a vocabulary, **This project's units**: each with its description and, when in use, how
   many variables use it. Without one, **Other units in this project**: `used`, with its counts.
3. **No unit.**
4. **As typed**, when what was typed is not exactly one of the entries above: the typed text, taken
   as it is.

Typing narrows every section to the units containing what was typed, regardless of case, but a
unit is only ever taken as spelled: `mV` and `MV` are different units, so typing `RPM` offers
`rpm` from the lists and `RPM` as typed. In a project with a vocabulary, a unit outside it reads
"Not one of this project's units" under the picker; it can still be applied, and the analysis then
reports `unknown-unit` with its own suggestion, as for a file edited by hand.

What the picker lists, in which order, and what the consequence line says are logic modules under
Vitest's 100 % gate; the panel and the picker themselves are screens.

### 5.4 The canvas

A red or orange arrow is a button. Choosing it opens the panel beside the canvas: for an arrow
carrying one variable in disagreement, that variable; for several, the list of them, each opening
its own panel. The address carries it as it does on the component page.

### 5.5 What the reader sees when something goes wrong

- **The preview is refused** - a type fixes the unit, or a file does not read. The panel says why
  and names the file; there is nothing to apply.
- **The file changed on disk** between the preview and Apply. The edit is refused as `stale`, and
  milestone 1's banner says so; the panel shows the new revision's declarations and the reader
  chooses again.
- **The variable is no longer declared**, renamed or removed on disk. The panel says so and closes
  back to the table.
- **The server stopped.** Milestone 1's banner appears, and the panel keeps what it shows but offers
  no Apply.

## 6 The workbench and the screenshot tests

- `npm run ladle` serves every story with hot reloading; `npm run ladle:build` builds them into
  static files. Stories live beside what they show, as `*.stories.tsx`, on mock data typed from the
  generated API types. Biome and the type check cover them like any other source.
- Every widget of `ui/` has a story, and the panel has one per state: the units agree; they
  disagree; a unit a type fixes; a project with a vocabulary, and a unit typed outside it; the
  picker open; Show changes open; an Apply refused as stale.
- A Playwright project, `screenshots`, visits every story of the static build and compares it with
  its reference image, committed under `gui/`. The references are made and checked in Playwright's
  Linux Docker image, pinned to the version the page's Playwright is: in CI, in the `gui` job on
  Ubuntu, and on a developer's Linux machine through a `gui-screenshots` compose service, which
  also refreshes the references on request. Files the service writes into the checkout belong to
  the user who ran it, not to root.

## 7 Testing

- **Python**, under the 100 % line and branch gate, ruff and strict mypy:
  - `settle` over a variable whose declarations all differ, some already agreeing, a local variable,
    no producer, a type fixing the unit to another value and to the same one, no unit as the target,
    a file that no longer reads, a kind that cannot carry the key, and an invalid `raw`;
  - the language server's quick-fix tests, unchanged, across `_propagate`'s move onto `settle`;
  - the three endpoints on `examples/demo` and on `examples/vocabulary`: a preview writes nothing,
    the files' bytes compared before and after, and its `edit`, posted to `POST /api/edit`, changes
    exactly the units' values;
  - every refusal and every `400`, `404` and `409` above.
- **The page's logic** under Vitest's 100 % gate; **every story** in the screenshot tests.
- **End to end**, in Chromium on Windows and Linux over a copy of `examples/demo`:
  - a disagreement written into a file from outside, resolved from the component page: the file
    differs from the original by exactly the unit's value, the finding is withdrawn and the canvas's
    arrow is plain again;
  - the same disagreement resolved from its arrow on the canvas;
  - the picker's sections, and Show changes naming the line;
  - an Apply refused as stale after a save from outside;
  - milestone 1's journeys, adjusted where the inline editor is retired;
  - no page reports a violation of its Content-Security-Policy.

## 8 Documentation and where it lands

- The command page and the changelog's preview entry for `ddd gui` describe the panel and the
  picker. The developer page describes the workbench, the screenshot tests and the compose service
  that refreshes them.
- `2026-09-17-web-gui-design.md` section 5 points to this spec for what follows the module graph,
  as the module graph's spec did for its own place.
- The spec and its plan are on `feature/gui-units`, started from `feature/gui-in-docker` (#48), and
  the branch moves onto master once #45 to #48 have merged. Part 1 restyles every screen and
  touches `api.py` and `contract.py`, so it is built after they merge rather than stacked a fifth
  time.

## 9 Evidence

- `src/ddd/lsp/edits.py`: `actions`, `_propagate`, `_from_producer`, `PROPAGATED_KEYS`,
  `DEFERRED_KEYS` - the reconcile rules this reuses.
- `src/ddd/lsp/navigation.py`: `Index.declarations` and `Index.producers` - every declaration of a
  name, and its producer.
- `src/ddd/models/objects.py` line 230: a declaration naming a declared type may not restate what
  the type fixes; `docs/file_formats/types.rst` lists the four keys a scalar type fixes.
- `docs/file_formats/units.rst`: the vocabulary, `unknown-unit` and its suggestions.
- `src/ddd/gui/server.py` line 63: the Content-Security-Policy, `default-src 'self'`, which refuses
  styles injected at run time; React Aria positions its popovers through style properties set from
  script, which it allows.
- `2026-09-18-gui-units/resolver-mockups.html` and `style-mockups.html`: the mockups the maintainer
  chose from, with the demo's ValueA given a second reader to show a choice that reaches more than
  one file. `chosen-design.html` is the chosen resolver in the chosen style, and the six images
  beside it are its states: `panel`, `picker`, `changes`, `vocabulary`, `canvas` and `applied`.
- Licences: React Aria Components Apache-2.0, Ladle MIT, Playwright Apache-2.0.
