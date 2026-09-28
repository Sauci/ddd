# Sections in the GUI

`ddd gui` has a Shared files tab, and it holds one of the three vocabularies it was built for. A
project that declares `.calib` - read-only flash a calibration tool writes through an emulation
overlay, four byte aligned - has no page for it, so `duplicate-section` and `unknown-section` are
dead ends and a definition reading `"section": ".fast_ram"` is a name with nowhere to go.

This adds sections to that tab. It is part 14, and the third slice of milestone 6 after types and
constants.

**This design covers all three vocabularies; this part builds sections.** Rasters get their own part
against the same shape. Part 13 wrote `project_shared.py` and `shared_plans.py` concretely for
constants with a recorded ruling that the sections part would *refactor rather than extend* -
deferring the abstraction to the point where more than one real shape could be read. That point is
now, and reading all three at once is what stops the shape being generalised twice.

## 1 What this adds

1. **Section rows in the tab readers already know**, their `Vocabulary` column reading `sections`.
   Nothing new to navigate: that was the whole point of part 13's one-tab decision.
2. **A panel per section**: its `access`, its `alignment`, its description, where it is declared,
   every definition that places data in it, and its findings.
3. **Both section checks stop being dead ends.** `duplicate-section` leads to the section;
   `unknown-section` leads there too, carrying the name even when nothing declares it, so the add
   form opens pre-filled.
4. **`access`, `alignment` and `description` are editable**, previewed and undone like every other
   change.
5. **A section is renamed everywhere it is named** - its own entry and every definition's `section` -
   in one all-or-nothing edit.
6. **One can be declared**, creating `sections.ddd.json` beside the project description and adding it
   to `includes` where the project has none.
7. **One can be removed**, refused while any definition names it, and refused while it is the only
   entry its file declares.
8. **The index learns both vocabularies at once**, which the language server gains at the same
   time. The two loops are one loop with a different key, and `ddd lsp` consumes a raster's entry
   the moment it exists - go-to-definition and rename - so indexing rasters here is not dead code
   waiting for a tab. Only the *tab* gains sections alone.

## 2 Decisions already taken

- **One descriptor, one set of functions.** A frozen record carries only what differs between the
  three vocabularies; the reading and the plans are written once and take it. The differences are
  small and enumerable, and every one of them is read from the models rather than restated:

  | | constants | sections | rasters |
  | --- | --- | --- | --- |
  | container | `constants`, and `component.constants` | `sections` | `rasters` |
  | name key | `name` | `section` | `raster` |
  | editable keys | `value` | `access`, `alignment` | `event`, `cycle` |
  | what a row states | `16` | `read-only, align 4` | `event 3, 10ms` |
  | created file | `constants.ddd.json` | `sections.ddd.json` | `rasters.ddd.json` |
  | a second home | a component's own list | none | none |

  Cost if wrong: a fourth vocabulary that differed structurally would reopen the record. Milestone 6
  names exactly these three.
- **Only constants have an inline home.** A component may declare its own constants; sections and
  rasters live in their own files alone. The descriptor carries whether a second home exists rather
  than every function assuming one.
- **Each editable key names the model that judges it.** A constant's `value` is judged by
  `ConstantValue`, a section's `alignment` by the power-of-two rule its own field carries, a raster's
  `cycle` by the XCP period grammar. The interface never restates a rule; it asks the owner. Cost if
  wrong: a rule stated twice drifts, which is what the interface exists not to do.
- **Neither a section's name nor a raster's joins `occupied`, and `rename_problem` judges neither.**
  A constant's name reaches generated code as a C identifier, which is why `occupied` guards it and
  why part 13 could borrow `rename_problem` wholesale. A section's name is a linker string written
  into an attribute; a raster's is an a2l short name. Each rename asks its own model's name type
  instead - `SECTION_NAME_PATTERN`, `RasterName`. Cost if wrong: a name one client accepts and
  another refuses, which is the outcome borrowing the editor's judge was for.
- **The refusal line, stated once rather than case by case.** The interface **refuses** what it can
  see is wrong and the reader can trivially avoid; it **reports** what only the analysis can
  determine, or what the reader may legitimately be part-way through. A category rule - "a schema
  error is refused, a check is reported" - was considered and rejected: it would have had the
  interface help a reader create a `duplicate-section` it could plainly see coming. §4.6 applies this
  to every measured case.
- **The removal guard applies verbatim.** `sections` and `rasters` carry the same `min_length=1` that
  made part 13's Critical: a list the format requires to hold one entry may not be emptied, or the
  file stops loading.
- **`alignment` is a text field, not a number input**, for the reason part 13 gave for a constant's
  value: the model requires a whole number written without a decimal point - *"4, not 4.0, which the
  published schema accepts and the loader refuses"* - and a number input hands back one spelling for
  both.
- **The tab mirrors itself.** A second vocabulary in the same table with the same panel beside it; a
  reader who has used the tab for constants knows this one.

## 3 Out of scope

- **Rasters.** They get their own part against this shape, and this design carries their column of
  the descriptor so that part is a fill-in rather than a second generalisation.
- **The project's `includes`, and new files in general.** The one `sections.ddd.json` that `add`
  creates is the exception, because `add` needs it.
- **The three untied-key tables part 13 recorded** - `ConstantPanel`'s `plans`, and both of
  `UnitPanel`'s and `TypePanel`'s.
- Changing what any check reports, or its severity.
- Anything about how the generated C or a2l places data. A rename changes the description files;
  what the backends emit follows from them, as it always has.

## 4 The server

### 4.1 What the index must learn

`ddd.lsp.navigation`'s `index()` records nothing of either vocabulary. The loader already collects
them symmetrically with constants - `workspace.sections` and `workspace.rasters`, each an entry with
its own `location()` - and nothing ever walked them. It gains four dictionaries:

| | |
| --- | --- |
| `Index.sections` | name -> the `Site` of its entry |
| `Index.section_uses` | name -> every `Site` where a definition places data in it |
| `Index.rasters` | name -> the `Site` of its entry |
| `Index.raster_uses` | name -> every `Site` naming it |

One use shape is new. A section is named only at a definition's `section`. A raster is named at a
definition's `raster` **and at a component's own** (`Component.raster`, its default for every
variable the component produces) - a use that is not inside a definition at all, which no constant
use ever was. `examples/vocabulary/pump.ddd.json` carries one on its line 6.

`renameable_at` and `rename_sites` learn both kinds at the same time, so `ddd lsp` gains
go-to-definition and rename on them. That is part 13's argument working for us: one answer, asked by
two clients, which cannot disagree.

### 4.2 The descriptor

A frozen record in `ddd.project_shared`, one per vocabulary, carrying the table of §2 - the container
pointer or pointers, the name key, the editable keys with the model that judges each, and the file
`add` creates. Every function below takes one. Nothing else in the modules branches on which
vocabulary it is holding.

### 4.3 What the tab reads

The reading is already written and is generalised rather than added to: `shared_rows`,
`constant_row`, the raw-text reader, the string reader, the uses reader and `located_on_constant`
become the same functions taking a descriptor. Their behaviour is unchanged for constants, which
`tests/test_project_shared.py` holds them to - a suite that passes untouched is the proof that
generalising moved no behaviour, exactly as `tests/test_unit_plans.py` was for part 13's first task.

### 4.4 What changing one takes

The four verbs generalise the same way. `rename` gains the per-kind name judge; `add` gains the
per-kind created file and form; `set` gains the per-kind editable keys and their judges; `remove` is
unchanged except that its two refusals - named by something, and the only entry its file declares -
now read the descriptor for the container.

### 4.5 The endpoints

`GET /api/shared` already answers every kind the tab holds and needs no change but its rows. The
panel and the plan routes are per-kind today - `/api/constant`, `/api/constant-plan` - and gain
siblings `/api/section` and `/api/section-plan`, in the shape `/api/type` and `/api/unit-plan`
already set. `ddd.finding_routes.route_of` gains a `section` route, answered for a pointer inside a
`sections[i]` entry and for a pointer a definition's `section` key matches.

### 4.6 What is refused, and what is reported

Measured against this checkout, not assumed:

| The reader asks for | `ddd check` on the result | The interface |
| --- | --- | --- |
| a section name outside `^[A-Za-z0-9_.$]+$` | `error[schema]`, the file does not load | refuses |
| an `alignment` that is not a power of two | `error[schema]: alignment 3 is not a power of two` | refuses |
| a `cycle` that is no XCP period (`1234ms`) | `error[schema]` naming the grammar | refuses |
| a name this vocabulary already declares | `error[duplicate-section]`, the file loads | **refuses** |
| an `event` another raster claims | `error[duplicate-event]`, the file loads | **refuses** |
| a section nothing places data in | nothing | allows |

The two bold rows are where the category rule would have gone wrong. Both are checks rather than
schema errors, so the format permits them - but the interface can see the name or the number is
taken and the reader can pick another, so offering to write one is offering to create a finding the
interface watched them walk into. That is not the same as `dimension-value`, which stays reported
because nothing in the project says what an array's length should be.

Rows naming `cycle` and `event` are the rasters part's to implement; they are here because the
descriptor is designed against all three, and a refusal designed for two of them is a refusal
redesigned later.

A rename onto a name the vocabulary already declares is refused for the same reason the Types tab
refuses one and the Units tab does not: two units under one spelling is a spelling problem worth
merging, while two sections under one name have different `access` and `alignment`, and merging them
would silently move data.

## 5 The screens

### 5.1 The table

Section rows join the existing table, `Vocabulary` reading `sections`. Two things generalise:

- **The third column is headed `States`, not `Value`.** `Value` fits a constant's `16` and not a
  section's `read-only, align 4`, and the descriptor carries how each kind renders its own row - a
  constant the json text of its value, a section its access and alignment, a raster its event and
  its cycle. This is the same call as the `Vocabulary` rename the consolidation branch made, for the
  same reason: cheap before a second vocabulary ships into the word, expensive after. It moves the
  tab's existing references, which is stated rather than discovered.
- **The summary line** names each vocabulary that has entries - *"2 constants · 2 sections"* - where
  it says *"2 constants"* today, and its empty state says the project declares none of them.
- **The add form gains a vocabulary chooser**, because declaring a section asks for a name, an
  `access` and an `alignment` where a constant asks for a name and a value. The descriptor drives
  which fields it shows, so the third vocabulary adds no form code. Part 13's lone *Declare a
  constant* button becomes one button opening the form with the chooser unset.

### 5.2 A section's panel

Beside the table, mirroring the constant's: its name as the heading and the panel's `aria-label`,
where it is declared, `access` as a chooser over the enum's own values, `alignment` and
`description` as text fields, every definition placing data in it as a link to that variable, its
findings, a *Rename* control, and a *Remove* one - gated, with a sentence saying why, where anything
names it or where it is the only entry its file declares.

### 5.3 What the reader sees when something goes wrong

A refusal is drawn as every refusal in the interface is, carrying the server's own sentence. A
sections file that did not load leaves its sections out of the table and says so above it, and a
file that did not load without saying what kind it is says so too - both of which the consolidation
branch merged as PR #68 already does for every tab.

## 6 Stories and screenshot tests

`examples/vocabulary` is the fixture and needs nothing added: `.fast_ram` (read-write, aligned 4) and
`.calib` (read-only, aligned 4), named by three definitions of `pump.ddd.json`, beside the two
constants already there - so one story shows the mixed table that is this tab's whole reason. Stories
for that table, a section's panel with two uses, a panel whose section nothing names (where *Remove*
is offered), the add form with its chooser on sections, and a refused rename. Screenshots follow the
repo's gate: references added, none of parts 1-13's moved.

## 7 Testing

- `tests/test_project_shared.py` and `tests/test_shared_plans.py` pass **untouched** across the
  generalisation, then gain sections' own cases. The untouched run is the proof.
- `tests/test_lsp.py` and the navigation suite for the four new dictionaries, including the
  component-level raster use.
- `tests/test_gui_api.py` for the two new routes and every refusal of §4.6.
- `tests/test_finding_routes.py` for the `section` route from both pointer shapes.
- Vitest at 100 % over `gui/src/lib`, including the generalised summary line; no component or screen
  tests, as the repo's page gate has never had them.
- One journey: break a definition's `section` so `unknown-section` is filed, follow it to the form,
  declare the section, and watch the finding go. No `page.waitForResponse`.
- The Python gate at 100 % line and branch, no `pragma: no cover`, no skips.

## 8 Documentation

The `ddd gui` row of `docs/command_line_interface.rst` gains sections beside constants: what the tab
lists, that a section is renamed everywhere it is named, that one can be declared - creating the file
where the project has none - and that removing one is refused while anything names it or while it is
all its file declares. Built under sphinx `-W`.

## 9 Evidence

Measured on `master` at `8df6d67` before this spec was written:

- `index()` records nothing of either vocabulary - no `sections`, no `section_uses` - and
  `renameable_at` answers for variables, types, constants and units only.
- The loader already collects both: `workspace.sections` and `workspace.rasters`, built from
  `_sections_by_name` and `_rasters_by_name` beside `_constants_by_name`.
- `Component.raster` is a component-level default (`models/component.py:102`), and
  `examples/vocabulary/pump.ddd.json:6` carries one.
- `unknown-section` is filed at `component.interface[0].definition.section`, whose value is the name
  - the same shape the unit and constant branches read.
- `alignment: 3` answers `error[schema]: Value error, alignment 3 is not a power of two`;
  `cycle: "1234ms"` answers a schema error naming the grammar; `".cal ib"` answers
  `String should match pattern '^[A-Za-z0-9_.$]+$'`.
- Two sections of one name answer `error[duplicate-section]` and two rasters on one event answer
  `error[duplicate-event]`, both with the project loading.
- `SectionsFile.sections` and `RastersFile.rasters` are both `Field(min_length=1)`, as
  `ConstantsFile.constants` is.
- `examples/vocabulary` checks clean, and carries both vocabularies already.
