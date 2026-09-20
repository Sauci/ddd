# The other keys in the GUI

The variable panel settles one key today, the unit. This carries it to the other eleven keys the
language server's reconcile actions already settle: what a variable is made of, what it means, what
shape it has, and which declarations it points at. The panel shows every key of a variable side by
side, says which of them its declarations disagree about, and settles any one of them on every
declaration at once.

This is part 3 of the three `2026-09-18-gui-units-design.md` set out: after **units, the field**
(part 1, merged as #49) and **units, the project** (part 2, merged as #51), **the other fields**. It
is the last of them; the milestones the web GUI's own design left after it are planned again once
it lands. The mockups the maintainer chose from are beside this spec in `2026-09-20-gui-other-keys/`.

## 1 What this adds

1. **A table of keys in the panel**, where part 1 put a single unit column: a row per key, a column
   per declaration, the producer first, and the cells that differ marked. The rows whose
   declarations disagree come first, then the keys someone states, then the keys this kind allows
   and nobody states.
2. **Every key the reconcile actions settle**: `datatype`, `typename`, `unit`, `conversion`,
   `limits`, `dimensions`, `size`, `volatile`, `axis`, `x_axis`, `y_axis` and `input`.
3. **Choosing a value**, in the place part 1's picker sits: the values already in play, each naming
   who states it and marking the producer's; **state nothing**, where the key may be left out; and,
   where the shape is simple, a field to type a new one.
4. **Composing is not offered** for `conversion` and `dimensions`. They are carried from one
   declaration to the others, which is what the reconcile actions themselves do.
5. **The server says what each key offers.** One answer carries, per key, the values in play,
   whether each declaration's kind may carry it and whether it must, and which editor it takes,
   beside the stated and type-fixed text it already carries. The page draws what it is given.
6. **Everything else stays as it is**: the consequence line, Show changes, Apply to N files, and the
   all-or-nothing write through `POST /api/edit`.

## 2 Decisions already taken

- **All eleven keys in one part**, rather than the meaning keys first: the panel is where a
  disagreement is settled, whatever it is about, and the server settles them all already.
- **Choose, and type where the shape is simple.** The values in play are always offered, since they
  are what the reconcile actions carry. A new value may be typed for `unit` (part 1's picker over
  part 2's vocabulary), `datatype` (its eleven names), `typename` (the project's declared types),
  `volatile` (true or false), `limits` (a min and a max), `size` (a whole number or a declared
  constant), `axis`, `x_axis` and `y_axis` (the project's axes) and `input` (its measurements). A
  `conversion` has four kinds and, for an enumeration, a list of enumerators; a `dimensions` is a
  list. Building either in the page would be a second loader, and an editor does it better.
- **A row per key**, over one key at a time behind a chooser and over a list of only what disagrees:
  a reader opening a variable wants to see where its declarations differ, and the rest is context
  they can read in the same glance. It scales to eleven keys; with many readers the columns narrow.
- **The server decides, as in parts 1 and 2.** Which kinds may carry which key, which keys a type
  fixes, and what a name may be are the loader's knowledge; they stay in Python under the 100 %
  gate, and the page draws what it is given.
- **`kind` is shown and never settled.** A declaration's kind decides which keys it may carry at
  all, so changing it from here would change the shape of everything else in the same breath.
- **The language server is untouched.** It already offers "Use the X declared in Y", "Take the X the
  other declarations state", "Apply this X to N other declarations" and the two removals for every
  one of these keys.

## 3 Out of scope

- Composing a `conversion` or a `dimensions` list.
- Changing a declaration's `kind`.
- `id` and `description`, which the reconcile actions do not settle: an id belongs to one
  declaration, and a description is prose each may word its own way.
- Undo, and the units vocabulary, which part 2 finished.

## 4 The server

### 4.1 What a key offers

`GET /api/variable` already answers, per declaration, the raw JSON text of `kind` and of every key
of `PROPAGATED_KEYS` that declaration states, the name of the type it names, and the text that type
fixes. The table's cells and their `rpm, from Speed_t` come from those, unchanged. The answer gains
one block per key for what the page cannot derive from them:

- **`carries`**, one per declaration: whether that declaration's kind may hold the key at all, and
  whether it must hold it. `dimensions` belongs to a measurement and a value block, `size` and
  `input` to an axis, `axis` to a curve, `x_axis` and `y_axis` to a map; a parameter holds none of
  them. A value block must state its `dimensions` where a measurement may leave them out, an axis
  its `size`, a curve its `axis`, a map both of its axes, and every kind its `volatile`. This is
  `definition_keys`, which derives both halves from the models themselves.
- **`values`**: the distinct raw values in play, each with the declarations stating it, the
  producer's marked - the chooser's own list, and what the reconcile actions carry. The server
  builds it, so that the list and the settlement it produces cannot disagree about which
  declarations a value reaches, and so that a declaration whose value comes from a type it names is
  counted once with the rest.
- **`editor`**: `unit`, `datatype`, `typename`, `volatile`, `limits`, `size`, `name` or `none`, as
  section 2 lists; `conversion` and `dimensions` take `none`.
- **`choices`**, for the editors that name things: the eleven datatypes - `boolean`, `uint8`,
  `sint8`, `uint16`, `sint16`, `uint32`, `sint32`, `uint64`, `sint64`, `float32`, `float64` - the
  project's declared types, its axes, its measurements and its declared constants, read from the
  navigation index parts 1 and 2 already use.

**State nothing** is offered when no declaration requires the key, and only then: settling is
all-or-nothing in the GUI, so a removal one declaration would refuse is not offered to begin with.

A `limits` a declaration leaves out is agreement, not a disagreement, as the analysis treats it: the
key is deferred, and a variable whose readers state none is not marked.

### 4.2 The endpoints

- `GET /api/variable` answers the blocks above beside what it answers today.
- `GET /api/settle?name=&key=&raw=` is unchanged. It settles any key of `PROPAGATED_KEYS`, refuses
  `fixed-by-type` when a type fixes the key at a declaration, `invalid` when a declaration's kind
  cannot carry it, and `unreadable` when a file no longer reads; leaving `raw` out removes the key
  from every declaration that states it.
- Apply posts the preview's `edit` to `POST /api/edit`, unchanged.
- The page sends only a value one of section 4.1's editors can produce, or a value already in play.
  A value that is well shaped but wrong in its context - an enumeration conversion on a float, a
  `datatype` beside a `typename` - is written, and the next analysis reports it on the file, exactly
  as it does for an edit made by hand.

## 5 The screens

### 5.1 The panel's table of keys

The panel keeps its head - the variable's name, its kind, its datatype or type, its producer - and
its findings, and replaces part 1's single unit column with one table:

| Column | Shows |
| --- | --- |
| Key | the key's name, `kind` first, then the rows in the order below |
| One per declaration | the value as a reader reads it: `"%"`, `{0, 100}`, `linear ×0.5`, `true` |

- The rows whose declarations disagree come first, then the keys someone states, then the keys this
  kind allows and nobody states, quietly.
- A cell whose declaration's kind cannot carry the key says so rather than sitting empty.
- A value a type fixes reads `rpm, from Speed_t`, as part 1's panel already writes it.
- `kind` is the first row, marked when it differs, and opens nothing.
- The meta line says how many declarations there are and how many keys disagree.

### 5.2 Choosing a key's value

Selecting a row opens that key below the table, where part 1's picker sits:

- **The values in play**, each naming the declarations that state it, the producer's marked.
- **State nothing**, when no declaration requires the key.
- **A field**, for the editors of section 4.1: the eleven datatype names; the project's types, axes,
  measurements or constants; true or false; a min and a max, both numbers and the max at least the
  min, which the field says before it offers to apply; or part 1's unit picker, which keeps part
  2's vocabulary and its "not one of this project's units" note.
- Then part 1's consequence line - which files the choice changes, and which declarations it marks
  "will change" - **Show changes**, and **Apply to N files**.

### 5.3 What the reader sees when something goes wrong

- **A type fixes the key**: the chooser says which type, and offers nothing.
- **A kind cannot carry the key**: the cell says so, and a choice that would reach that declaration
  is refused before anything is written, naming it.
- **A key that must be stated** offers no "state nothing".
- **A file no longer reads**: refused, naming the file.
- **A file changed on disk**: refused as stale; the panel shows the new revision and the reader
  chooses again.
- **The variable is gone**: the panel closes and the page says why, as part 2 made it.
- **The server stopped**: milestone 1's banner, and no Apply.

## 6 Stories and screenshot tests

One story per state, photographed in Playwright's Linux image as parts 1 and 2 are: the table with a
disagreement; each editor open - names, datatype, true or false, a min and a max, the unit picker,
and a key that is chosen only; a key a type fixes; and a cell a kind cannot carry.

## 7 Testing

- **Python**, under the 100 % line and branch gate, ruff and strict mypy:
  - the per-key answer for a measurement, a value block, an axis, a curve and a map, including the
    cells a kind cannot carry and the keys it must state;
  - `carries` against `definition_keys` for every kind, `values` with their declarations and the
    producer marked, a value a named type fixes counted with the rest, and each editor's `choices`
    read from the index;
  - the endpoints over copies of `examples/demo` and `examples/vocabulary`: a preview writes
    nothing, and its edit applied changes exactly what it said, for a key of each shape - a string,
    a number pair, an object carried whole, a boolean and a name;
  - every refusal, and every `400`, `404` and `409`.
- **The page's logic** under Vitest's 100 % gate: the row order, how each value is written short,
  which editor a key takes, and what each chooser lists.
- **End to end**, in Chromium on Windows and Linux: settling `conversion` from the producer; typing
  `limits` and applying; turning `volatile` off; a key a type fixes, refused; removing an optional
  key; and the Content-Security-Policy journey visiting the new table.
- **The gate** as parts 1 and 2 ran it, the real application included, with screenshots for the pull
  request.

## 8 Documentation and where it lands

- The changelog and the command page say what the panel settles now. The developer page describes
  the per-key answer. `docs/editor_integration.rst` needs nothing: the language server's actions are
  unchanged.
- `2026-09-17-web-gui-design.md` section 5 is planned again once this lands, as the paragraph part 1
  added there says.
- On `feature/gui-other-keys`, from master after #51.

## 9 Evidence

- `src/ddd/lsp/edits.py`: `PROPAGATED_KEYS`, the twelve keys; `DEFERRED_KEYS`, which holds `limits`;
  `settle` and its three refusals; `actions`, the five reconcile actions this reuses unchanged.
- `src/ddd/models/objects.py`: `MEANING_KEYS` and `refuse_restating`, which a declaration naming a
  type may not restate; `definition_keys`, which says what a kind may carry; `Limits`, whose `max`
  is at least its `min`; the kind classes `Measurement`, `ValueBlock`, `Axis`, `Curve` and `Map`.
- `src/ddd/models/common.py`: `Datatype`, the eleven names.
- `src/ddd/models/conversion.py`: the four conversion kinds, `identity`, `linear`, `enum` and
  `string`.
- `src/ddd/variables.py`: `FIXED_BY_A_TYPE` and `declarations_of`, which already answer `stated` and
  `fixed` for every key; `SETTLE_CODES` and `refusal`, which name the three refusals; `preview`,
  which turns a settlement into the edit and its hunks.
- `src/ddd/gui/contract.py`: `VariableDeclaration`, whose `stated`, `type` and `fixed` already carry
  every key's text - what section 4.1 builds on rather than repeats.
- `src/ddd/gui/api.py`: `_variable` and `_settle`, already key-generic.
- `gui/src/components/VariablePanelView.tsx` and `gui/src/lib/units.ts`: where the page assumes a
  unit today - one column, one picker.
- `2026-09-20-gui-other-keys/layouts.html`: the three panels the maintainer chose from, A chosen
  (`panel-a.png`, `panel-b.png`, `panel-c.png`).
