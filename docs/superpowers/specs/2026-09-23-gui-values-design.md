# A curve's numbers

`ddd gui` can now write a component's interface: settle what its declarations disagree about
(#52), maintain the vocabulary (#51), stamp a missing id (#53), change what a type fixes and
rename a type everywhere (#56), add a declaration and take one away (#57), and undo any of it
(#55). It shows nothing of what a calibration object actually holds. `init` is in no panel, no
key row and no chooser, and is not in `ddd.variable_keys.KEY_ORDER`.

So `examples/demo` has a curve whose six numbers the interface cannot show, a map whose
twenty-four it cannot show, and - since part 7 - a form that will happily declare a new curve
the reader then has no way to fill in.

This adds the grid. It is part 8 of the GUI's growth by field, and milestone 5 of the original
design, less the two halves named in section 3.

## 1 What this adds

1. **A grid of an object's values**, against its breakpoints where it has them: a curve over its
   axis, a map over two, an axis over its own indices, and any declaration with `dimensions` over
   indices alone.
2. **Raw or physical**, by a toggle: the counts the file holds, or what they mean through each
   object's own conversion.
3. **A cell is editable**, previewed and applied through the one endpoint that writes, and undone
   by part 5's stack.

## 2 Decisions already taken

- **The grid reads the resolved dictionary, not the files.** `ddd.analysis.Variable` already
  carries, per object, the fully numeric `shape` (from the axes, for a curve or a map), the
  effective `definition` taken from the producing component, the resolved physical `limits`, the
  `conversion` with its defaults filled in, the `references` naming the axes, and the `owner`.
  `revision.dictionary` already computes it and `GET /api/dictionary` already serves it.
  Re-deriving any of that in a new module would give the project two answers to "what shape is
  this object", and the second would be wrong first for a dimension spelled as a constant's name -
  which the models allow and `_numeric_shape` resolves.
- **The writes go to the producer's file.** `init` is a producer key
  (`ddd.analysis.PRODUCER_KEYS`), so an object's numbers live in exactly one declaration, and
  `Index.producers` says where. Writing into a file the reader is not looking at is already
  ordinary here - part 3's settle writes into every declaring file, part 6's rename into every
  file naming the type - and the preview names it, as they do.
- **A cell is one operation at a json pointer.** `set` at
  `component.interface[3].definition.init[2]` for a curve, `…init[1][3]` for a map, so the preview
  is one changed line. Rewriting the whole array to change one cell would print 256 numbers for a
  16 × 16 map.
- **A map's rows are its y axis and its columns its x.** Measured, not assumed: `MapA` has
  `x_axis: AxisA` (size 6) and `y_axis: AxisB` (size 4), and its resolved `shape` is `[4, 6]`.
- **Physical entry rounds, and the grid shows what was stored.** `ConversionRule.to_raw` answers a
  float; an integer datatype stores an integer. `models/conversion.py`'s own docstring states the
  asymmetry this rests on: "every raw value has exactly one physical image under a linear
  conversion, while most physical values are the image of no raw count at all." So `12.004` typed
  into `CurveA` (linear ×0.01, `uint16`) stores raw `1200` and reads back `12.0`, and **`12.0` is
  what the grid then shows**. A page that echoed the typed value would be lying about the file.
- **The grid has an address.** Opening one puts it in the browser's address bar, so it survives a
  reload, a link reaches it, and an `init-invalid` finding can lead to the object whose value is
  wrong rather than stopping at its panel - which is what part 4 promised every finding would do.
  `route_of` answers `Route("variable", name)` for a pointer inside a declaration today
  (`finding_routes.py:88`); a pointer inside its `init` answers the values route instead.
- **The grid takes the whole page.** A drill-down from the component's table, not a section of the
  variable's panel: a real map is 16 × 16, and the panel is `minmax(0, 1fr)` beside the table -
  about half the width. One thing at a time, which is part 7's lesson about a panel slot applied
  to a screen.

## 3 Out of scope

- **Paste from Excel**, and **plots**. The other two halves of milestone 5. Each is its own part:
  paste is a parser and a shape match with its own refusals, and a plot is either a new frontend
  dependency - which the GUI has refused since part 1 - or hand-rolled SVG.
- **Marking the cells a finding names.** The analysis folds `init-invalid` into one finding per
  kind of mistake, naming the offending values in its message and filing one `Location` for the
  whole `init` (`analysis.py:2614`). Marking the guilty cells needs a per-element answer, and the
  two ways to get one from here are parsing that sentence or re-deriving the check in the page.
  Part 7's one Critical came from the second move - a rule derived from what the examples happened
  to hold rather than from the code that enforces it, which wrote files the tool's own checks then
  rejected at ERROR. The grid shows the finding and leaves the marking to a part that can ask the
  analysis for it properly.
- **A string init.** `SoftwareLabel` is `"V1.2.3"` and `StateName` is `"OFF"`. Those are text, not
  a grid, and the grid does not claim them.
- **Editing an axis's `size`, or a `dimensions`.** Changing the shape is part 7's form and part 3's
  chooser; this part changes what is in the shape.
- **Any change to `ddd check`, the language server or the generators.** This writes the same `init`
  a person writes by hand.

## 4 The server

### 4.1 What is already there

Everything the grid reads. One object's record in the resolved dictionary, verbatim from
`examples/demo`:

```
CurveA: kind=curve  datatype=uint16  unit=ms  conversion={linear, factor 0.01, offset 0.0}
        limits={min 0.0, max 655.35}   shape=[6]   dimensions=[6]
        init=[1200, 900, 800, 750, 700, 650]
        references={axis: AxisA}   owner=Controller   local=true
```

The breakpoints are the referenced axis's own record in the same dictionary: `AxisA` is
`shape=[6]`, `unit=Hz`, `conversion={linear, factor 0.25}`,
`init=[0, 3200, 6400, 12800, 19200, 32000]`.

### 4.2 What the grid reads

`GET /api/values?name=` answers one object's grid:

- what it is - `kind`, `datatype`, `unit`, the conversion and the resolved limits;
- its `shape`, fully numeric;
- its values as the file holds them, and what they are: an **array**, a **scalar** standing for
  every element, or **absent**;
- one entry per axis it references - which axis, in which position (`axis`, `x_axis`, `y_axis`),
  with that axis's own unit, conversion and breakpoints;
- the producing declaration's file, so the page can say where an edit lands, and whether there is
  one at all;
- the findings filed on its `init`.

### 4.3 What changing a cell takes

`GET /api/value-plan?name=&at=&raw=` answers the existing `PlanReply`, previewed and applied
through `POST /api/edit` exactly as the units, the types and the declarations are.

- `at` is the element, as a json pointer suffix: `[2]` for a curve, `[1][3]` for a map.
- `raw` is the count to store, always raw. The page does the physical arithmetic with the
  conversion the answer above gave it, so one rule converts and the server stores what it is told.

**When the array is not there yet**, the plan is one `set` of the whole `init`: filled from the
scalar it had, or with zeros where it had none. The preview shows that, so an object gaining an
explicit value is something the reader sees rather than discovers.

### 4.4 The module

`src/ddd/object_values.py`, shaped like `ddd.type_plans`: what a grid shows, and what changing one
cell takes. It reads the dictionary for the values and the index for where to write them - the
same pairing `ddd.project_types` and `ddd.type_plans` use.

### 4.5 What is refused

- `invalid`, in the words the init check itself uses, and for the reasons it uses them: a
  fractional value under an integer datatype; a value outside `datatype.raw_min … raw_max`; a
  value that `datatype.rounds_to_zero`; a value that is not `0`, `1` or a bool under `boolean`.
  These come from `Datatype`'s own public properties, which is where `analysis._check_init`
  (`analysis.py:2536`) gets them - not from a second copy of the rule.
- `invalid` also for an `at` that is not an element of the shape, an object whose init is a
  string, and an object with no shape at all.
- **A value outside the object's limits is not refused.** Measured: `limits-out-of-range`
  (`analysis.py:2640`) weighs the *limits* against the *storage*, and nothing weighs an init
  against the limits - so refusing here would make the grid stricter than `ddd check`, and a file
  a person wrote by hand would have cells the interface could not edit. The grid says the value is
  outside the declared range and stores it.
- `not-found`: the project declares no object of that name.
- `unreadable`: a file the change has to see did not load, or the project has no dictionary.
- A name nothing produces answers its grid read-only rather than refusing: there is no declaration
  to write into, and the page says so.
- `stale` and `unwritable` arrive from the edit engine, as they do today.

## 5 The screen

### 5.1 The way in

The component's table gains a **Shape** column between Type and Unit: `6` for `CurveA`, `4 × 6`
for `MapA`, `8` for `BlockA`, blank for a scalar object. It is a **button** where the grid can
draw the object - `Show the values of CurveA`, the way the Unit cell is already a button - and
plain text where it cannot, which is an object whose init is a string: `SoftwareLabel` is shaped
`16` and holds `"V1.2.3"`, so its shape is shown and not offered. A grid that refused the moment
it opened would be a button that lies.

### 5.2 The grid

It takes the page. The table, the findings list and the variable's panel give way to it, with the
object's name as the heading, a way back to the component, and the undo strip where it always is.

A curve, in physical:

```
AxisA (Hz)      0     800    1600    3200    4800    8000
CurveA (ms)    12       9       8     7.5       7     6.5
```

A map, rows against the y axis and columns against the x:

```
             AxisA (Hz) →
AxisB (%)        0     800    1600    3200    4800    8000
   0            10      12      14      15      16      15
  30             9      11      13      14      15      14
  70             6       8      10      11      12      11
 100             3       5       7       8       9       8
```

An axis alone is its breakpoints over indices. A value block or a dimensioned measurement is the
same grid over indices, with no breakpoint header.

Above it, one line of what the object is - `curve · uint16 · ms · linear ×0.01 · 0 … 655.35`
- and the raw/physical toggle. The header converts by the **axis's** rule and the values by the
**object's**: they are different objects with different units, which is why `CurveA` in ms sits
over `AxisA` in Hz.

A **scalar** init draws as that value repeated, with a note that it is stated once; an **absent**
one draws as zeros, greyed, with a note that nothing is stated.

### 5.3 Changing one

A cell is a text field. Type, press Enter, and the grid shows what every other write path in this
interface shows: the sentence - `Sets element 3 of CurveA to 7.5 ms` - then `Show changes` and
`Apply to 1 file`, naming the producer's file. No cell writes on its own.

A reader's page shows the same grid and edits the same file: `ValueB` on `Controller` is an
`input`, its numbers live in `SensorHub`, and the preview names `sensor_hub.ddd.json`.

### 5.4 What the reader sees when something goes wrong

Refusals render where the other panels render theirs - the `panel-refusal` paragraph with
`role="status"`. A stale one is held by `shownRefusal` until the analysis moves past the revision
it was refused at.

The shape can change under an open grid - someone edits the axis's `size`, or a constant a
dimension names. The grid is keyed on the revision and redraws at the new shape; a cell edit
already in flight is refused as stale by the fingerprint it carries.

The object can go: remove the producing declaration and there is nothing to draw. The grid says so
and offers the way back, the same path `onUndeclared` already takes in a variable's panel.

## 6 Stories and screenshot tests

Ladle stories for `ValuesGridView`: a curve with its breakpoints, a map with both headers, an axis
alone, a value block over indices, a scalar init noted as stated once, an absent one greyed, a
cell mid-change with its preview, and a refused cell. A story imports nothing from
`@ladle/react`. Screenshots are written and taken in `mcr.microsoft.com/playwright:v1.63.0-noble`,
through `docker compose run --rm gui-screenshots`.

## 7 Testing

- **Python**, at the 100 % line-and-branch gate, no `pragma: no cover` and no skips:
  `tests/test_object_values.py` for the grid, the readings, the cell plan at a pointer, the
  materialising of a scalar or absent init, and every refusal of 4.5; the two endpoints added to
  `TestEveryEndpointOnTheDemo`; and the contract test that fails the build for a model no endpoint
  reaches.
- **The page**: `gui/src/lib/objectValues.ts` holds what is testable without a browser - laying a
  flat init against a shape into rows, reading a raw count as physical and back, the sentence a
  cell's change makes, and what each kind of header is - under Vitest at 100 % over `src/lib`. No
  Vitest for a component or a screen.
- **Journeys**, `gui/e2e/values.spec.ts`: read `CurveA`'s grid and check the physical row is
  `12, 9, 8, 7.5, 7, 6.5` against `AxisA`'s `0 … 8000 Hz`; toggle to raw and see `1200, 900, …`
  over `0, 3200, …`; change a cell and find it in the file; change one of `MapA`'s and find it at
  `init[1][3]`; type a physical value no raw count represents and watch the grid show what was
  stored; be refused for a value out of range; and undo. The content-security-policy journey gains
  the grid, as every part has added its screen to that walk.
- `examples/demo` carries every case already - a curve, a map, two axes, a value block, a scalar
  init in `CurveB`, an absent one in `ValueB`'s readers and a string one in `SoftwareLabel` - so no
  new example is needed.

## 8 Documentation and where it lands

- New: `src/ddd/object_values.py`, `gui/src/lib/objectValues.ts`,
  `gui/src/components/ValuesGridView.tsx`, `gui/src/screens/ValuesPage.tsx` and their stories.
- Extended: `src/ddd/gui/contract.py`, `src/ddd/gui/api.py`, `src/ddd/finding_routes.py`;
  `gui/src/api/types.ts` (its export list sorted case-insensitively), `gui/src/lib/route.ts`,
  `gui/src/app/App.tsx` and `gui/src/screens/ComponentPage.tsx`.
- Unchanged: `ddd check`, the language server, the generators, `ddd.analysis`.
- The GUI's page in `docs/` gains the grid, and `ddd gui` stays labelled preview.
- The branch is `feature/gui-values`, off `master` at the merge of #57.

## 9 Evidence

Every figure below was read from the code or computed with it, not recalled.

- `src/ddd/analysis.py:391`: `Variable`, carrying `shape` ("the resolved array shape, fully
  numeric; for a curve or map it comes from the axes"), `definition` ("the effective definition,
  taken from the producing component"), `dimensions` and `limits`.
- `revision.dictionary.model_dump()`, run against `examples/demo`: `CurveA` answers
  `shape=[6]`, `init=[1200, 900, 800, 750, 700, 650]`, `references={axis: AxisA}`,
  `owner=Controller`, `conversion={kind: linear, factor: 0.01, offset: 0.0}`,
  `limits={0.0, 655.35}`. `MapA` answers `shape=[4, 6]` against `x_axis=AxisA` (6) and
  `y_axis=AxisB` (4).
- The physical readings in section 5.2, computed with `ConversionRule.to_physical` and
  `round_physical` rather than by hand: `AxisA` is `0, 800, 1600, 3200, 4800, 8000` Hz, `AxisB` is
  `0, 30, 70, 100` %, `CurveA` is `12, 9, 8, 7.5, 7, 6.5` ms, and `MapA`'s first row is
  `10, 12, 14, 15, 16, 15`.
- `src/ddd/analysis.py:2536` `_check_init` and `:2640` `_check_limits_fit`: what an init value is
  actually refused for - the datatype's range, a fraction under an integer type, a float rounding
  to zero, a non-bool under `boolean` - and what is *not* weighed against it, the object's limits.
- `src/ddd/models/common.py:303` `Datatype.info`, carrying `raw_min`, `raw_max`, `is_float` and
  `is_signed`: `uint16` is `0 … 65535`, `sint8` is `-128 … 127`. `conversion_range` answers the
  *physical* bound instead - `(0.0, 655.35)` for `CurveA` - which is why the refusal uses the
  datatype's own range and not that.
- `src/ddd/models/conversion.py:32`: the `ConversionRule` protocol - `to_physical`, `to_raw`,
  `describe` - with `:128` `LinearConversion.to_raw` returning `(physical - offset) / factor`, a
  float; `:353` `round_physical`; `:398` `physical_range`; `:425` `raw_reading`, whose docstring
  states the asymmetry section 2 rests on.
- `src/ddd/models/objects.py:61` `InitValue`, "a scalar, or a (nested) sequence of scalars matching
  the shape of the object"; `:557` `declared_shape`, `None` for a curve or a map "whose shape
  follows from the axes they refer to".
- `src/ddd/analysis.py:3397` `_check_init_shape`, which is why a shape is resolved rather than
  read: "only one of the two shapes is written in the file".
- `src/ddd/analysis.py:2614` `init-invalid`, folded into one finding per kind of mistake with one
  `Location` - the reason section 3 leaves cell marking out.
- `examples/demo`, measured: `AxisA` size 6 ×0.25 Hz, `AxisB` size 4 ×0.5 %, `CurveA` over `AxisA`
  ×0.01 ms, `MapA` 4 × 6, `BlockA` `[0, 12, 28, 52, 84, 124, 180, 255]`, `CurveB` `init: 200`,
  `SoftwareLabel` `"V1.2.3"`, and `AxisA` in `user_interface` with `init: null` - the reader's copy
  of a producer key.
- `gui/src/styles/ui.css:131`: `.with-panel` is `minmax(0, 1.1fr) minmax(0, 1fr)`, which is why the
  grid does not go in the panel.
- `src/ddd/finding_routes.py:88`: `Route("variable", name)` for a pointer inside a declaration -
  what a pointer inside an `init` stops answering.
