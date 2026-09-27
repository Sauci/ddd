# Constants in the GUI

`ddd gui` can settle what a variable's declarations disagree about, maintain the project's units,
open a types file, route every finding to the place it names, plot an object's values, fix a
disagreement in one click and ask whether the project can replace a baseline delivery. It cannot
open a constants file. A project that declares `TREND_SAMPLES` — one number, named by every shape
that walks that buffer — has no page for it, so three checks are dead ends today
(`gui/src/lib/findings.ts:161` says `constants.ddd.json is a constants file, which has no page
yet`), and a dimension reading `["TREND_SAMPLES"]` in a variable's panel is a name with nowhere to
go.

This adds the tab those point at. It is part 13, after the units (#49), the project's units (#51),
the other keys (#52), the findings (#53), undo (#55), types (#56), declarations (#57), values
(#58), paste (#61), plots (#63), the mismatch fix (#64) and comparing deliveries (#65). It is the
second slice of the original design's milestone 6 — the shared project files — after types.

## 1 What this adds

1. **A Shared files tab**, between Types and Findings, for the three vocabularies with no page:
   constants now, sections and rasters later. One table, a `Kind` column, one panel per kind.
2. **A panel per constant**: its value, its description, where it is declared, every shape that
   names it, and its findings.
3. **All three constant checks stop being dead ends.** `duplicate-constant` leads to the constant;
   `dimension-value` leads to it too, and that one is directly actionable, since the value is the
   thing to change; `unknown-constant` leads to the tab with the missing name offered for
   declaration.
4. **A constant's `value` and `description` are editable**, previewed and applied as every other
   change the interface makes, and undone by part 5's stack.
5. **A constant is renamed everywhere it is named**: its own entry, every declaration's
   `dimensions[i]` and `size`, and every structure member's `dimensions[i]`, in one all-or-nothing
   edit.
6. **A constant can be added**, creating `constants.ddd.json` beside the project description and
   adding it to `includes` where the project has none.
7. **A constant can be removed**, refused while any shape names it.
8. **A dimension that names a constant links to it**, the way part 6 turned *fixed by the type*
   into a way in.

## 2 Decisions already taken

- **One tab for the three remaining vocabularies, not three tabs.** A constant is `name` + `value`
  + `description`; a section is `section` + `access` + `alignment` + `description`; a raster is
  `raster` + `event` + `cycle` + `description`. One name, one or two scalar properties, one
  description — alike enough that three tables, three panels and three server modules would be
  triplication, and alike enough that one table with a `Kind` column holds all three. Sections and
  rasters add rows and a panel each; they add no navigation. Cost if wrong: the table carries three
  property shapes from the start.
- **The tab is called Shared files, not Vocabulary.** The codebase calls all three of these files
  vocabularies — `models/constants.py` opens *"Contract for the constant vocabulary file"* — but
  the Units tab's shipped copy already uses that word for units (`this project has a vocabulary
  already`), so the label would collide with text a reader has seen. Cost if wrong: a reader may
  expect Units and Types under it; the tab's heading names the kinds it holds.
- **`unknown-constant` gets a route, not a one-click fix.** A shape naming `PRESSURE_CELLS` says
  the array's length is that constant, and nothing in the project says what that length is. A fix
  would have to write `1` and hope. Part 11's fixes exist because a `definition-mismatch` has one
  correct value the project already states; this has none. The finding leads to the tab with the
  name pre-filled, and the reader supplies the number.
- **One route kind, and the page decides.** The route carries `constant` and a name. The page opens
  the panel where the name is declared and the pre-filled add form where it is not — which is also
  what happens when somebody declared it between the analysis and the click.
- **One `add`, not units' `add` plus `adopt`.** `lsp.units.adopt_units` harvests the units already
  in use into a new file; the constants in use are exactly the ones `unknown-constant` complains
  about, and their values cannot be harvested. So `add` creates the file where there is none, and
  there is no second verb.
- **A new constant goes in the first constants file `includes` names**, exactly as `add_unit` picks
  its file.
- **The rename is the editor's rename.** `ddd.lsp.navigation` already renames a constant:
  `renameable_at` answers `("constant", name)` from a constant's own `name` and from any of the
  three places a shape is written, `rename_sites` returns the declaration and every use, and
  `rename_problem` says why a name may not be used — with `built.occupied` already holding *the
  name of the declared constant*. The tab asks those same questions the editor asks, so the two
  clients cannot disagree about what a rename reaches or which names it refuses.
- **What is in use is asked of the index, never of a file's text.** `Index.constant_uses` is the
  project's own record of every shape naming a constant. Part 11 filed a bug against
  `variable_keys._storage_of` for reading raw text to answer a question about meaning — it marks an
  in-use `datatype` removable. The index makes that mistake hard to repeat here.
- **A value travels as the json text its author wrote.** `ConstantValue` is strict on both arms and
  `_refuse_whole_number` keeps them apart, so the spelling decides the type: `2` is a whole
  constant and `2.0` a fractional one. The panel reads and writes the raw text, as
  `project_types.py` already does for `limits` and `conversion`. Nothing is parsed into the models
  and re-serialised.
- **A constant declared inline in a component is listed and edited like one in a constants file.**
  The loader registers `component.constants[i]` and `constants[i]` under one name, and the Types
  tab already handles both homes for types. `add` always writes to a constants file.
- **One server module for the three kinds**, written concretely for constants, its per-kind facts
  named constants at the top rather than a descriptor abstraction built from a single example.
  Sections and rasters add their facts to the same file. Cost if wrong: the sections part refactors
  rather than extends.
- **A row's finding count includes the findings on its uses.** `project_types.type_rows` counts
  only what is filed inside the entry itself (`_within_entry`), so `unknown-type`, filed at a
  `typename`, does not reach the Types table's count. Here that would hide the one finding a reader
  of this tab most needs: `dimension-value` is filed at the shape, not at the entry, and it is
  entirely about the constant's value. So this table counts both. Cost if wrong: two vocabulary
  tables count differently until the Types tab is brought along, which this part does not do.
- **The tab mirrors the Units and Types tabs**: a table with a panel beside it. A reader who has
  used either knows this one.

## 3 Out of scope

- **Sections and rasters** — their rows, their panels, their routes. This part builds the tab they
  will live in; until they land, a finding on a sections or rasters file keeps saying it has no
  page yet.
- **The project's `includes` editor, and new files in general.** The one `constants.ddd.json` that
  `add` creates is the exception, because `add` needs it.
- **The two bugs part 11 filed**: `variable_keys._storage_of` reading raw text, and `_remove_here`
  asking what a file spells rather than what it means. Separate work; this part only declines to
  repeat the mistake.
- **A one-click fix for `unknown-constant`, `unknown-section` or `unknown-raster`.** See §2.
- **The same finding-count gap on the Types tab.** `unknown-type` is filed at a `typename` and so
  is missing from that table's count, for the reason given in §2. Worth fixing; not here.
- Changing what any check reports, or its severity.
- Anything about how the generated C or a2l spells a constant. A rename changes the description
  files; what the backends emit follows from them, as it always has.

## 4 The server

### 4.1 What is already indexed

`ddd.lsp.navigation` records, for every constant the project declares:

| | |
| --- | --- |
| `Index.constants` | name → the `Site` of its entry, in a constants file or in `component.constants` |
| `Index.constant_uses` | name → every `Site` where a shape names it |
| `Index.occupied` | name → `the name of the declared constant 'X'`, which a rename is refused against |

`_DIMENSION_KEY` fixes the three places a shape is written: a declaration's `dimensions[i]`, a
declaration's `size` — the axis case — and a structure member's `dimensions[i]`. `/api/declarable`
already publishes `built.constants` to the page, for the dimensions field of the add-a-declaration
form. Nothing new is indexed by this part.

### 4.2 What the tab reads

`src/ddd/project_shared.py`, transport-neutral like `project_units.py` and `project_types.py`:
nothing in it knows about http or the session.

- **`shared_rows(built, findings, cache)`** → one row per entry: `kind` (`constant`), `name`, its
  `value` as the text its file spells (`16`), how many shapes name it, and how many findings are
  filed on its entry **or on any shape that names it**. Sorted by kind then name. `findings` is the sequence
  `[(filed.file, filed.diagnostic), ...]` that `project_types.type_rows` already takes, so the api
  builds it once for both tabs.
- **`constant_row(built, name, cache)`** → the panel: `value` and `description` as raw text, the
  file and pointer of its entry, every use with its file, its pointer, the variable or member it
  belongs to and the component it is in, and the findings on both the entry and the uses.

A name the index does not hold answers empty, as `project_types.py` does: the api looks the name up
before it asks, so that arm is only reachable from a test.

### 4.3 What changing one takes

`src/ddd/shared_plans.py`, one function per verb, each returning a plan of `PlannedEdit`s and
raising `SharedRefusalError(code, message)`. `shared_project(project, cache)` builds the record the
verbs need — the project description's path, the constants files its `includes` names in that
order, and which of them did not load — the way `lsp.units.unit_project` builds `UnitProject`.

| Verb | What it writes |
| --- | --- |
| `set_key(built, name, key, raw, cache)` | `value` or `description` of the entry, the raw text as given |
| `rename(built, name, to, cache)` | the entry's `name` and every site `rename_sites` returns, in one edit |
| `add(built, project, name, raw, cache)` | an entry appended to the first constants file the project includes — or `constants.ddd.json` written beside the project description and added to its `includes` where there is none. `raw` is the value's json text, so `2` and `2.0` stay two different constants |
| `remove(built, name, cache)` | the entry, and nothing else |

`add`'s creating arm follows `lsp.units.adopt_units` exactly: the file is laid out with `lay_out`,
the `includes` entry is inserted at the end, and both edits travel in one plan so a project can
never list a file that was not written. `Session._confined` already permits a file created beside
the project description by an edit that includes it there.

### 4.4 The endpoints

| Route | Answers |
| --- | --- |
| `GET /api/shared` | every row of the tab, for every kind it holds |
| `GET /api/constant?name=X` | one constant's panel |
| `GET /api/constant-plan?action=` | `set` (`name`, `key`, optional `raw` — its absence is what removing a `description` means), `rename` (`name`, `to`), `add` (`name`, `raw` — the value's json text), `remove` (`name`) — previewed, never applied |

Mirroring `/api/types` + `/api/type` + `/api/type-plan` and `/api/unit-plan`. A plan is applied by
`POST /api/edit` with the changes it returned, as every other preview in the interface is.

`ddd.finding_routes.route_of` gains a `constant` route, answered for a pointer inside a
`constants[i]` or `component.constants[i]` entry and for a pointer `_DIMENSION_KEY` matches. The
name comes from the document at that pointer for a use, and from the entry's `name` for an entry.

### 4.5 What is refused, and what is merely reported

Refused, before a file is touched:

- a rename to a name `rename_problem` rejects — not a usable c identifier, reserved, already
  declared, or occupied by another constant;
- an `add` of a name the project already declares anywhere, refused in `rename_problem`'s own
  sentence — which names what holds the name rather than which file holds it, because the tab asks
  that function rather than deciding for itself, and wrapping its answer to append a path would mean
  this module post-processing another's message;
- an `add` while the constants file it would write to did not load, or while creating one would
  overwrite a file of that name already beside the project description;
- a `remove` of a constant any shape names, with the count and the first of them named;
- any verb naming a constant no file of the project declares.

Reported, not refused: a value that is no array length. Setting `TREND_SAMPLES` to `2.5` while a
dimension names it is a legal edit of a legal file, and `dimension-value` is the check that says
so — on the next revision, in the panel, with a route back to the value. The interface does not
invent a rule the format does not have.

## 5 The screens

### 5.1 The Shared files tab

A table: `Name`, `Kind`, `Value`, `Used by`, `Findings`. Every constant the project declares,
sorted by name, those in a component's own list among those in a constants file — a reader looking
for `PRESSURE_CELLS` does not know which file holds it. A project with no constants shows one line
saying so and the button that adds the first one.

`Value` where the Types tab has `Description`, and not both: a constant's description is a full
sentence — the example's is *sample slots of a pressure trend buffer, a device wide size no single
component owns* — which would dominate every row, while its value is short and is what a reader
scans a list of constants for. A type's row has nothing shorter than its description to show, which
is why that tab shows one. The description is in the panel. Sections and rasters read the same
column as what they state: `read-only, align 8`, `event 3`.

### 5.2 A constant's panel

Beside the table: its name, its value and description as editable fields, the file and line its
entry is at, every shape that names it as a link to that variable or member, its findings, a
*Rename* control and a *Remove* one. Every change is previewed in the same `Changes` view every
other edit uses, and applied by the same button.

### 5.3 The way in from a declaration

A variable's panel lists `dimensions` among its keys, in `VariableKeysTable` - the same table where
part 6 turned a type's name into a way in, through an `onOpenType` callback. An entry that names a
declared constant becomes a link to it; an entry that is a literal number stays text; an entry that
names nothing the project declares becomes a link too, to the pre-filled add form - that name is
exactly what `unknown-constant` is about, and the reader is one click from declaring it.

### 5.4 What the reader sees when something goes wrong

A refusal is drawn as the banner every refusal in the interface is drawn as, carrying the server's
own sentence. A constants file that did not load leaves its constants out of the tab and says so
above the table, because a table that silently omitted them would read as a project that declares
nothing.

## 6 Stories and screenshot tests

`examples/vocabulary` is the fixture: `TREND_SAMPLES` (16) in `constants.ddd.json`,
`PRESSURE_CELLS` (8) declared inline in `pump.ddd.json`, both named by dimensions, and the project
checks clean. Stories for the table (both homes in one table), the empty table, a panel with two
uses, a panel with a `dimension-value` finding on it, and a refused rename. Screenshots follow the
repo's existing gate: new references added, none of parts 1–12's moved.

## 7 Testing

- `tests/test_project_shared.py` and `tests/test_shared_plans.py`, new, over the reading and the
  four verbs, at 100 % line and branch with no `pragma: no cover` and no skips.
- `tests/test_gui_api.py` for the three routes, including every refusal in §4.5.
- `tests/test_finding_routes.py` for the `constant` route from all four pointer shapes.
- Vitest over `gui/src/lib/shared.ts` and the three new `route.ts` shapes at 100 %; no component
  tests, as the repo's page gate has never had them.
- One journey: break a dimension in a copy of `examples/vocabulary` so `unknown-constant` is filed,
  follow the finding to the tab, declare the constant with a value, and watch the finding go. No
  `page.waitForResponse` — it is what broke part 6's CI.

## 8 Documentation and where it lands

The `ddd gui` row of `docs/command_line_interface.rst` gains the tab: what it lists, that a
constant is renamed everywhere it is named, that one can be added — creating the file where the
project has none — and that removing one in use is refused. Built under sphinx `-W`.

## 9 Evidence

Measured on `master` at `8d9be79` before this spec was written:

- `renameable_at` answers `("constant", value)` from `_DIMENSION_KEY` or `_CONSTANT_NAME`
  (`navigation.py:638`), and `rename_sites` returns `[the entry, *constant_uses]`
  (`navigation.py:603`). The rename does not have to be written, only asked for.
- `built.occupied[name]` is set for every declared constant (`navigation.py:264`), so a colliding
  rename is already refused by `rename_problem`.
- `add_unit` refuses when the project includes no units file (`lsp/units.py:169`); `adopt_units`
  is the only code that creates one (`lsp/units.py:259`). The creating arm of `add` has a working
  precedent, and `Session._confined` already permits it.
- `fixes_for` answers for exactly two checks, `missing-id` and `definition-mismatch`
  (`finding_fixes.py:70`). The `unknown-*` family has no fix today, and this part adds none.
- `unknown-constant` and `dimension-value` are filed at the shape that names the constant
  (`analysis.py:1695`, `analysis.py:2069`), which is a pointer `_DIMENSION_KEY` matches.
- `/api/declarable` already returns `constants=tuple(sorted(built.constants))`.
- `examples/vocabulary` checks clean: *ok: 4 variables in 1 component are consistent*.
- The tab strip holds six views today (`gui/src/app/App.tsx:22`); this part makes seven, and
  sections and rasters will make no more.
