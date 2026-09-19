# The project's units in the GUI

A page of every unit a project states, where each is stated, and the vocabulary beside them.
From it a unit is renamed everywhere at once, two spellings of one unit are merged, the vocabulary
is described, added to and pruned, and a project without one adopts the units it already uses.
Editors gain the same rename and two quick fixes, from the same rules.

This is part 2 of the three `2026-09-18-gui-units-design.md` set out: after **units, the field**
(part 1, merged as #49), **units, the project**; then **the other fields** (part 3). It has its own
spec, plan and pull request, like part 1. The mockups the maintainer chose from are beside this
spec in `2026-09-19-gui-units-project/`.

## 1 What this adds

1. A **Units** tab on the project page, beside Graph and Table: a table of every unit the project
   states or its vocabulary lists - the unit, its description, how many variables, types and
   structure members state it, and its findings.
2. Selecting a unit opens its **panel** beside the table: whether the vocabulary lists it and in
   which file, its findings, and every place it is stated - the variable, type or structure member,
   its file, and its role.
3. **Rename a unit everywhere**: every declaration, structure member and scalar type stating it,
   and its vocabulary entry. Renaming onto a unit that already exists **merges** the two spellings.
   Only the spelling changes; values, limits and conversions stay as they are.
4. **The vocabulary**: a unit's description is edited in its panel; a unit outside the vocabulary
   is added to it; a unit nothing states any more is removed from it.
5. **Adopting a vocabulary**: a project with no units file writes one listing every unit in use,
   and includes it. Nothing is reported afterwards that was not reported before.
6. **In an editor**, Rename Symbol works on any unit, with the same reach and the same merge; an
   `unknown-unit` finding offers "Add RPM to the vocabulary" and, when the finding has a suggestion,
   "Rename RPM to rpm everywhere".
7. Every change is **previewed** - which files, and Show changes for the exact lines - and written
   to every file or none, through the edit endpoint milestone 1 built.

## 2 Decisions already taken

- **All four jobs in one part**: the page of units, the rename, the vocabulary edits and adoption.
  Without adoption a project with no units file - the demo is one - gets a list and a rename, and
  no vocabulary to hold them to.
- **A rename reaches everywhere a unit is stated**: data objects of every kind (measurements,
  parameters, axes, curves, maps), structure members, scalar types and the vocabulary, type files
  shared with other projects included. Afterwards no file of the project states the old spelling.
  These are the places `unknown-unit` already checks.
- **Merging is what a rename of a unit is for.** Two variables merged into one is a collision the
  language server refuses; two spellings of one unit merged into one is the fix. In the
  vocabulary, the old entry is renamed when the new spelling is not listed, and removed when it is;
  the entry that stays keeps its description.
- **Adoption takes every unit in use**, so that adopting changes nothing the analysis reports;
  spellings are merged by renaming afterwards.
- **Layout A**, a table of units and a panel beside it, over a grouped list acting inline (no room
  for Show changes) and a list beside one unit's whole page (a pattern no other page uses): the
  component page and the canvas already work this way, and it reuses part 1's widgets.
- **The rule lives with the language server's rename**, over a module of the GUI's own (the rename
  would reach editors only by a second route) and edits worked out by the page (the rules of where a
  unit is stated would be copied into TypeScript). Each change is planned once, as operations on
  JSON pointers; the language server renders a plan as text edits, and the page previews it and
  posts it to `POST /api/edit`. Part 1's `settle` is the precedent: one rule, both clients.
- **Editors get the rename and two quick fixes**; describing, removing and adopting stay the page's.
  An editor describes a unit by typing in the units file.
- **One write path.** The edit engine learns one thing: an edit may create a file, which adoption
  needs.

## 3 Out of scope

- Converting between units. `ms` to `s` is not a spelling: a rename leaves values, limits and
  conversions as they are, and the panel says so under its rename field.
- Other projects sharing a type file. The preview names every file a rename writes; the page cannot
  see projects it has not opened.
- Ordering the vocabulary, and moving units between units files.
- Undo.
- The other keys (part 3).

## 4 The server

### 4.1 Where units are stated

The navigation index records, for each spelling, every place a unit is stated and every vocabulary
entry listing it, beside what it already records for variables, types and constants. It is built
from the files that loaded, with the rest of the index:

- a **data object's** `unit` - a declaration of any kind, `component.interface[i].definition.unit`;
- a **structure member's** `unit`, and a **scalar type's** `unit`, in the types files;
- a **vocabulary entry**: a plain string `units[i]`, or the `unit` of an object `units[i]`.

The empty unit is no unit, as `unknown-unit` treats it, and is not recorded. Part 1's
`units_in_use` reads its counts from the same record, so the picker and the Units tab count alike.

### 4.2 Plans

A plan is the operations one change takes, per file, as `POST /api/edit` takes them - or a refusal
with a code and the file it concerns. The plans are made where the language server's rename is:

- **rename** `old` to `new`: every stated site's string set to `new`; in the vocabulary, each entry
  listing `old` renamed when no entry lists `new`, and removed when one does. A unit listed twice
  (`duplicate-unit`) has every entry treated so.
- **add** `unit` to the vocabulary: an entry appended to the first units file the project
  description's `includes` lists, in the form that file's entries take - a plain string when they
  all are, otherwise `{"unit": …, "description": ""}`.
- **describe** `unit`: the entry's `description` set, a plain-string entry becoming an object.
- **remove** `unit`: its entries taken out of the vocabulary, with exactly one comma each.
- **adopt**: a new `units.ddd.json` beside the project description listing every unit in use,
  alphabetically, as `{"unit": …, "description": ""}`, and its name appended to the description's
  `includes`, in one edit.

Refusals, before any file is touched:

- `unreadable` - a file of the project does not load. A rename or an adoption could not reach every
  place the unit is stated; adding, describing and removing refuse only when the units file itself
  does not load. The message names the file.
- `invalid` - a new name that is empty, has spaces around it or is the old one; removing a unit
  something still states; adopting with no unit in use (a units file lists at least one), or when
  `units.ddd.json` exists and is not a units file; adding a unit to a project with no units file.
- `not-found` - renaming, describing or removing a unit the project neither states nor lists.

### 4.3 The edit engine creates a file

A change whose `fingerprint` is `null` creates its file: the file must not exist, and the change
has exactly one operation, an `add` at the root pointer carrying the whole document. It is staged
and renamed into place like any write; if a later file of the same edit fails, the created file is
deleted with the others put back; if the file exists by the time the edit is made, the edit is
refused as `stale`. A created file takes the mode, and where the process may set them the owner and
group, of the project description beside it, so `ddd gui` in its container leaves the user a file
of their own.

The session accepts a change naming a file that is not yet one of the project's description files
only when it creates that file beside the open project's description, in an edit whose change to
that description leaves the file among its `includes`; otherwise the edit is refused as `invalid`
and nothing is written.

### 4.4 The endpoints

Declared in `src/ddd/gui/contract.py` with the page's types generated from them; `409` `no-project`
without an open project, as the others.

- `GET /api/units` keeps what part 1's picker reads and gains a row per unit for the table:
  `units: [{unit, description, files, variables, types, members, findings}]`, where `files` are the
  units files listing it (empty outside the vocabulary) and `findings` counts its `unknown-unit` and
  `duplicate-unit` findings; and `adoptable`: how many units adoption would list, `null` when the
  project has a units file.
- `GET /api/unit?name=` answers one unit's panel: `{revision, unit, description, entries, sites,
  findings}`. `entries` are its vocabulary entries (file and pointer); each site is `{path, pointer,
  kind, name, component, role}` with `kind` one of `variable`, `type`, `member`. A unit the project
  neither states nor lists is `404` `not-found`, and while a file does not load `409` `unreadable`
  naming it, as part 1's `/api/variable` answers.
- `GET /api/unit-plan?action=rename|add|describe|remove|adopt` with `unit`, and `to` for a rename,
  `description` for a description, answers a plan with the shape `/api/settle` has: `{revision,
  changes: [{file, fingerprint, operations, hunks}]}`, `fingerprint` `null` for a file adoption
  creates, whose hunk is the whole file. A refusal is `409` with its code, `404` for `not-found`,
  and `400` for a missing or unknown parameter.
- Apply posts the plan's `{file, fingerprint, operations}` to `POST /api/edit`, unchanged.

### 4.5 The language server

- **Rename.** `renameable_at` recognises a unit at any place 4.1 lists, as the kind `unit`. Prepare
  answers the range of the string's characters and the unit as the placeholder. The rename takes the
  rename plan and renders each operation as the text edit the edit engine computes for it, as the
  quick fixes do (`_protocol_edit`). A refusal is answered as the language server answers one
  today, and a buffer that no longer holds the unit where the index recorded it refuses the rename,
  naming the file, as for variables.
- **Quick fixes on `unknown-unit`** - which only a project with a vocabulary reports: "Add 'RPM'
  to the vocabulary", the add plan; and "Rename 'RPM' to 'rpm' everywhere", the rename plan, when
  the check's own `_did_you_mean` - the same cutoff, over the same vocabulary - finds a suggestion.

## 5 The screens

### 5.1 The Units tab

A third tab of the project page, at `/project?view=units`, with `&unit=` naming the unit whose
panel is open; opening and closing a panel replaces the address rather than pushing one, as part 1
does for a variable. One row per unit, its spelling exact - `rpm` and `RPM` are two rows:

| Column | Shows |
| --- | --- |
| Unit | the spelling |
| Description | the vocabulary's description; "not in the vocabulary" outside it; nothing without a units file |
| Stated by | "2 variables", "1 variable, 1 type", "unused" for a vocabulary entry nothing states |
| Findings | its `unknown-unit` and `duplicate-unit` chips |

Units with findings come first, then by how many variables, types and members state them, most
first, then by spelling; unused vocabulary entries come last. The title reads "9 units · 2 not in the vocabulary", or
"8 units · no units file".

### 5.2 A unit's panel

Top to bottom: the unit; "in the vocabulary, units.ddd.json" or "not in the vocabulary", and how
many places in how many files state it; its findings; **Where it is stated**, a table of the
variable, type or member, its file and its role (produces, reads, local, scalar type, structure
member); then what the unit's state offers:

- **In the vocabulary**: its **Description**, a text field; once changed, "Changes 1 file:
  units.ddd.json" and **Save**. **Remove from the vocabulary** appears only while nothing states it.
- **Not in the vocabulary**, with a units file: **Add to the vocabulary**, naming the file it goes
  into, with Show changes.
- **Always**: **Rename … to**, part 1's picker - the vocabulary's units first, then the other units
  in use, then the text as typed, the unit itself left out - over "Only the spelling changes; values,
  limits and conversions stay as they are." The consequence line says what the rename changes -
  "Changes 2 files: controller.ddd.json, types.ddd.json" - and what becomes of the vocabulary:
  "rpm is in the vocabulary already, so RPM merges into it", "renamed in units.ddd.json too", or,
  for a new spelling outside a vocabulary, part 1's "Not one of this project's units". Then **Show
  changes** and **Apply to N files**.

### 5.3 Adopting a vocabulary

Without a units file, a banner above the table: "This project has no units file, so no unit is
checked against a vocabulary. Adopting writes units.ddd.json with the 8 units in use and includes
it in the project: nothing is reported that is not reported today." with **Show changes**, which
opens the adoption's preview in the panel - the project description's new line and the new file -
and **Adopt 8 units**. A project that states no unit has nothing to adopt, and the banner says so.

### 5.4 What the reader sees when something goes wrong

- **A plan is refused**: the panel says why and names the file; there is nothing to apply.
- **A file changed on disk** between the preview and Apply: refused as `stale`; the panel says so
  and shows the new revision, and the reader chooses again, as in part 1.
- **The unit is gone** - renamed from outside, or an address naming a unit nothing states or lists
  - its panel closes, and a banner on the tab says so, as part 1's variable panel does. While a file
  does not load the panel stays, naming the file.
- **The server stopped**: milestone 1's banner; the panel keeps what it shows and offers no Apply.

## 6 Stories and screenshot tests

Every state of the panel has a story, photographed like part 1's in Playwright's Linux image: a unit
in the vocabulary, one outside it, one unused, the adoption banner and its preview, Show changes on
a merge, and a refused plan. The Units tab's table has one, with a row carrying findings.

## 7 Testing

- **Python**, under the 100 % line and branch gate, ruff and strict mypy:
  - the index's record of units: every kind of place 4.1 lists, both forms of vocabulary entry, the
    empty unit left out;
  - each plan: a rename, a merge removing the old entry, a unit listed twice; an addition in a file
    of plain strings and in one of objects; a description turning a plain string into an object; a
    removal, and its refusal while the unit is stated; an adoption, and its refusals;
  - the language server: prepare and rename from each kind of place, a merge, each refusal, a
    drifted buffer; each quick fix offered, and the rename's not offered without a suggestion;
  - the edit engine creating a file: written, refused as `stale` when it exists, deleted when a
    later file fails, taking the project description's mode and owner; the session refusing a new
    file that the same edit does not include;
  - the endpoints on copies of `examples/demo` and `examples/vocabulary`: a plan writes nothing,
    its edit posted to `POST /api/edit` changes exactly what it said, and every refusal, `400`,
    `404` and `409`.
- **The page's logic** under Vitest's 100 % gate: the table's order, the panel's sentences, what
  each state offers.
- **End to end**, in Chromium on Windows and Linux: adopting on a copy of the demo (the file
  created and included, no finding more); renaming `RPM` into `rpm` on a copy of
  `examples/vocabulary` with a spelling drifted from outside; describing, adding and removing; an
  Apply refused as stale; the Units tab in the journey that no page violates its
  Content-Security-Policy.
- **The gate** as part 1's, the real application in `docker compose up gui` included, with
  screenshots for the pull request.

## 8 Documentation and where it lands

- The changelog: the Units tab in the `ddd gui` preview entry, and the language server's unit
  rename and quick fixes in its own.
- The command page's `ddd gui` row; `docs/editor_integration.rst` for Rename Symbol on units and the
  two quick fixes; the developer page for the plans and the edit engine creating a file.
- On `feature/gui-units-project`, from master after #49.

## 9 Evidence

- `src/ddd/lsp/navigation.py`: `renameable_at`, `rename_sites`, `rename_problem`, `rename_edits` -
  the rename this extends; `Index`, which gains the units' record.
- `src/ddd/lsp/server.py`: `_prepare_rename` and `_answer_rename`, which refuse a drifted buffer.
- `src/ddd/lsp/edits.py`: `settle` and `_protocol_edit` - one rule for both clients, and a plan's
  edit rendered as text.
- `src/ddd/editing.py`: `apply_changes`, all or nothing; `removal` and `member_addition`, the text
  edits both clients share.
- `src/ddd/gui/session.py`: `_source`, which lets an edit name only the project's description files.
- `src/ddd/analysis.py`: `_check_units` - units are checked on declarations, structure members and
  scalar types, with `_did_you_mean` at a cutoff of 0.5.
- `src/ddd/models/units.py`: a units file lists at least one unit; an entry is a plain string or
  `{"unit", "description"}`. `src/ddd/models/types.py`: a structure member's and a scalar type's
  `unit`. `src/ddd/models/objects.py`: a data object's `unit`, which axes, curves and maps share.
- `docs/file_formats/units.rst`: the vocabulary, `unknown-unit` and `duplicate-unit`.
- `2026-09-19-gui-units-project/layouts.html`: the three layouts, A chosen (`layout-a.png`,
  `layout-b.png`, `layout-c.png`); `states.html`: layout A's other states (`vocabulary.png`,
  `adopt.png`, `merge.png`).
