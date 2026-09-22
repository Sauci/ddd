# Types in the GUI

`ddd gui` can settle what a variable's declarations disagree about, maintain the project's
vocabulary, route every finding to the place it names and put any change back. It cannot open a
types file. A project that declares `Temperature_t` - a datatype, a unit, a conversion and limits
that every declaration naming it takes - has no page for it, so two things are dead ends today: a
finding filed on a types file says "types.ddd.json is a types file, which has no page yet"
(`gui/src/lib/findings.ts`), and a declaration naming a type shows its `unit`, `conversion` and
`limits` greyed as *fixed by the type* with no way to reach the type that fixes them.

This adds the tab those two point at. It is part 6 of the GUI's growth by field, after units (#49),
the project's units (#51), the other keys (#52), the findings (#53) and undo (#55), and it is the
first of the original design's milestone 6 - the shared project files.

## 1 What this adds

1. **A Types tab**, beside Graph, Table, Units and Findings: every type the project declares, in
   one table - scalars, externals and structures together, because a reader looking for `Sample_t`
   does not know which kind it is.
2. **A panel per type**: what it fixes, where it is used, its description, its findings, and - for
   a structure - its members.
3. **Every finding on a types file leads there.** `route_of` answers a `type` route for a pointer
   inside a type, so `duplicate-type`, `unknown-type`, `type-kind`, `type-cycle`, `unknown-unit`,
   `init-invalid` and `limits-out-of-range` stop being dead ends.
4. **A declaration's greyed row becomes a way in**: the *fixed by the type* text in a variable's
   panel links to the type that fixes it.
5. **What a scalar type fixes is editable** - `datatype`, `unit`, `conversion`, `limits` - beside
   any type's `description` and an external's `header`, previewed and applied as every other change
   the interface makes, and undone by part 5's stack.
6. **A type is renamed everywhere it is named**: its own `name`, every declaration's
   `definition.typename` and every structure member's `typename`, in one all-or-nothing edit.

## 2 Decisions already taken

- **The tab mirrors the Units tab.** Part 2 built a project-wide shared file as a table with a
  panel beside it, and a types file is the same kind of thing: one file the whole project reads
  from. A reader who has used the Units tab knows this one.
- **A rename onto a name that exists is refused, never merged.** Part 2 merges two spellings of a
  unit, because two names for one unit is a spelling problem. Two types under one name is
  `duplicate-type`, an error, and their shapes may differ - merging would silently retype every
  variable naming one of them.
- **`datatype` and `conversion` offer no "state nothing".** `ScalarType` requires both
  (`src/ddd/models/types.py`), unlike a declaration, where part 3's chooser offers to leave a key
  out. The arm is absent for those two and present for `unit` and `limits`.
- **A structure's members are shown, not edited.** A member is as rich as a declaration - its own
  datatype, unit, conversion, bits, dimensions or a type of its own - and editing one needs its own
  panel and its own chooser. Reading them is what makes the tab useful now.
- **One chooser, not two.** Part 3's `KeyChooser` takes a whole `VariableReply` and looks its offer
  up inside it. A type has no declarations, so reusing it means taking the offer and a label
  instead - a small decoupling, in the path of this work. The alternative is a second chooser that
  drifts from the first.
- **The rename is the editor's rename.** `ddd.lsp.navigation` already renames a type: its
  `renameable_at` answers `("type", name)` from a type's own `name` or from any `typename`, its
  `rename_sites` gives every string to rewrite, and its `rename_problem` says why a name may not be
  used. The tab asks those two the same questions the editor asks, so the two clients cannot
  disagree about what a rename reaches or which names it refuses.
- **Nothing is added or removed.** This part changes types that exist. Declaring a new one belongs
  with adding a declaration, which is the part after this.

## 3 Out of scope

- Adding a type, removing one, or creating a types file where the project has none.
- Editing a structure's members, or adding, removing or reordering them.
- The other shared files milestone 6 names: sections, constants and rasters.
- Anything about how the generated C spells a type. A rename changes the description files; what
  the backends emit follows from them, as it always has.
- Changing what any check reports, or its severity.

## 4 The server

### 4.1 What is already indexed

Nothing new is indexed. `ddd.lsp.navigation.Index` already carries what the tab needs:

| Field | What it holds |
| --- | --- |
| `types` | every type's name -> where it is declared |
| `type_uses` | every type's name -> each place naming it: a declaration's `definition.typename` and a structure member's |
| `occupied` | every C identifier already spent - a type's own name, an enum's, an enumerator's - and the phrase saying what spends it |

`type_uses` covers both homes of a `typename` because the index fills it from a declaration's
`declared_type` and from each structure member's, which is exactly the pair a rename has to reach.
`occupied` carries every type's name beside the enums', so "is this name free?" is one lookup
rather than three. Note that `Index.types` is filled for every type although its own docstring says
"Structure name": the field is written before the walk that only structures enter.

### 4.2 What the tab reads

`src/ddd/project_types.py`, transport-neutral like `ddd.project_units`: a `TypeRow` per type - name,
kind, description, how many places name it, how many of its own findings - and `uses_of(name)`,
giving each use with the component and the variable, or the structure and the member. A type's own
findings are those filed inside it: `duplicate-type`, `unknown-type`, `type-kind`, `type-cycle`,
`unknown-unit`, `init-invalid` and `limits-out-of-range`.

### 4.3 What changing one takes

`src/ddd/type_plans.py`, the way `ddd.project_units` plans a unit's change:

- `set_key(name, key, raw)` - a scalar's `datatype`, `unit`, `conversion` or `limits`, any type's
  `description`, an external's `header`. One file, one pointer.
- `rename_type(name, to)` - the type's own `name` and every `typename` reaching it, across every
  file, in one edit.

Neither invents what the editor already knows. `rename_type` asks
`ddd.lsp.navigation.rename_problem(index, to, "type")` whether the name may be used, and
`rename_sites(index, "type", name)` which strings to rewrite - the type's own `name` pointer and
every use `type_uses` holds. What it does not borrow is the editor's `rename_edits`, which answers
text edits with ranges; the tab plans `ddd.editing` operations on json pointers instead, exactly as
part 4's identity fix did rather than borrowing the language server's quick fix. `rename_edits`'s
own `drifted` has no counterpart here either: it exists because an editor's buffer may have moved
a declaration out from under the index, and the tab reads the disk the index described, with the
edit engine's fingerprints refusing a file that changed since.

### 4.4 The endpoints

| Request | Answers |
| --- | --- |
| `GET /api/types` | every row, sorted by name |
| `GET /api/type?name=` | one type, its uses and its findings |
| `GET /api/type-plan?action=set&name=&key=&raw=` | `PlanReply` |
| `GET /api/type-plan?action=rename&name=&to=` | `PlanReply` |

`PlanReply` is part 2's own `{revision, changes}`, so the page turns a plan into an edit with the
`planEdit` it already has, and applies it through `POST /api/edit` with a label part 5's undo
reads. `FindingRoute.kind` gains `"type"`.

### 4.5 What is refused, and what is merely reported

A rename is refused for whatever `rename_problem` refuses it for, in that function's own words,
which is more than a tab would have thought to check: a name that is not a usable c identifier or
is too long, one spelling a base datatype, one c or a generated header reserves, one this project
already declares as a variable, and one `occupied` records - another type's name, an enum's, an
enumerator's - reported as "'X' is the name of the type 'X', which shares c's namespace with the
variables". Beside it: a `set` of a key the type does not have, a `datatype` on a structure or a
`header` on a scalar, and the refusals every edit already has, `stale` first among them.

Not refused: a value that is legal json for its key but wrong for the project. A unit outside the
vocabulary is written and then reported as `unknown-unit`; limits the datatype cannot hold are
written and reported as `limits-out-of-range`. The edit engine verifies that a file still reads
back as the document intended, not that the project is consistent - and part 3 already behaves this
way when a reader types a unit the vocabulary does not list.

## 5 The screens

### 5.1 The Types tab

| Column | Shows |
| --- | --- |
| Type | the type's name |
| Kind | scalar, external or structure |
| Description | what the type says it is |
| Used by | how many declarations and members name it |
| Findings | its own findings |

Sorted by name, all three kinds in one table. The meta line counts what is there - "9 types · 5
scalars, 3 structures, 1 external". A project declaring none says so.

### 5.2 A type's panel

- **What it fixes**, as rows a reader selects: `datatype`, `unit`, `conversion` and `limits` for a
  scalar; `header` for an external; none for a structure. Selecting one opens part 3's chooser -
  the eleven datatypes, the unit picker with the project's vocabulary behind it, the two range
  fields - then part 1's consequence line, Show changes and Apply.
- **Where it is used**: every declaration naming it, with its component and its role, and every
  structure member nesting it. Part 2's "Where it is stated", from `type_uses`.
- **Description**, and **Rename *Temperature_t* to**, as a unit's panel carries them.
- **Its members**, for a structure: name, value or bits, the type or datatype, unit, bits and
  dimensions - read only, each member naming a type linking to it.
- **Its findings**, each leading where it leads.

### 5.3 The way in from a variable's panel

Part 3 greys `unit`, `conversion` and `limits` on a declaration naming a type and says *fixed by
the type*. That text becomes a link to the type, following part 4's pairing of a real href with an
in-place handler, so it opens the Types tab without reloading the page.

### 5.4 What the reader sees when something goes wrong

- **The type is gone** by the time its panel is opened - renamed or deleted on disk: the panel
  closes and the tab says why, as part 2's unit panel does.
- **A file changed on disk**: refused as stale, with part 4's wait for a later revision, so the
  retry goes through.
- **The new name is taken**: refused, naming what holds it - another type, an enum, an enumerator.
- **A types file did not load**: the tab says so and lists what it can. One unreadable file does
  not blank the others.
- **The server stopped**: milestone 1's banner, and no Apply.

## 6 Stories and screenshot tests

One story per state, photographed in Playwright's Linux image as parts 1 to 5 are: the tab with all
three kinds; a scalar's panel; the same with a key chosen and its changes shown; a structure's
panel with its members; an external's; a rename refused because the name is taken; and a project
that declares no types. **Part 3's five reference images must come out unchanged**, which is what
proves the chooser's decoupling changed nothing a reader sees.

## 7 Testing

- **Python**, under the 100 % line and branch gate, ruff and strict mypy:
  - the rows and the uses over `examples/structures`, the one example carrying all three kinds, and
    over a project whose types file did not load;
  - `set_key` for every key of every kind, including the refusals for a key the kind does not have;
  - `rename_type` across a declaration and a nested member at once, the whole edit checked byte for
    byte, and refused for each shape `rename_problem` refuses - a taken name, a base datatype's, a
    reserved one, a variable's and a spelling that is no identifier - with its sentence carried
    through to the page unchanged;
  - the route for a finding filed inside a type, and for one filed on a types file that did not
    load;
  - every refusal, and every `400`, `404` and `409`.
- **The page's logic** under Vitest's 100 % gate: the rows and their counts, what each panel shows
  per kind, and the edit a plan comes to.
- **End to end**, in Chromium on Windows and Linux: open a type from a finding; open one from a
  variable's greyed row; change a scalar's unit and read the file back; rename a type and find both
  the type and the declaration naming it rewritten; meet a rename refused because the name is
  taken; and the Content-Security-Policy journey visiting the new tab.
- **The gate** as parts 1 to 5 ran it, the real application included, with screenshots for the pull
  request.

## 8 Documentation and where it lands

- The changelog and the command page say that the types a project declares are a tab of their own,
  that what a scalar type fixes is editable there, and that renaming one rewrites every declaration
  naming it. The developer page describes `project_types`, `type_plans` and the three endpoints.
  `docs/editor_integration.rst` needs nothing: the language server is untouched.
- On `feature/gui-types`, from master once #55 lands. The branch is cut from the undo branch's tip
  so that its own pull request carries only this work.

## 9 Evidence

- `src/ddd/lsp/navigation.py`: `Index.types`, filled for every type although its docstring says
  "Structure name"; `Index.type_uses`, filled from a declaration's `declared_type` and from each
  structure member's `typename`; and `Index.occupied`, which already holds every type's own name
  beside the enums' and is what a rename checks against.
- `src/ddd/models/types.py`: `ScalarType`, whose `datatype` and `conversion` are required and whose
  `unit` and `limits` are not; `ExternalType`, with its `header`; `StructType` and `Member`.
- `examples/structures/types.ddd.json`: all three kinds, a member nesting another structure, a
  member carrying bits and an enum, and a member with dimensions.
- `src/ddd/lsp/navigation.py` again: `renameable_at`, which already answers `("type", name)`;
  `rename_sites`, which adds the type's own `name` to its uses; and `rename_problem`, whose five
  refusals this tab reuses rather than re-deriving. `rename_edits` beside them answers text edits
  with ranges, which is why the tab plans its own operations.
- `src/ddd/project_units.py` and `src/ddd/lsp/units.py`: the pair this mirrors - what a tab reads,
  and what changing one takes.
- `src/ddd/gui/contract.py`: `FindingRoute`, which gains a kind, and `PlanReply`, which is reused
  as it stands.
- `gui/src/components/KeyChooser.tsx`: takes a whole `VariableReply` today, which is what section 2
  decouples.
- `gui/src/lib/findings.ts`: `noRouteReason`, whose "which has no page yet" this deletes for a
  types file.
