# Pasting a table into the values grid

- **Part:** 9 of the GUI work, the second third of milestone 5
- **Status:** design approved; to be planned
- **Builds on:** [`2026-09-23-gui-values-design.md`](2026-09-23-gui-values-design.md), shipped as
  part 8

## 1 Why

Part 8 gave a curve, a map, an axis and any shaped declaration a grid of their own, and one cell
at a time to change. That is the right unit for correcting a value and the wrong one for entering
a calibration: `MapA` is twenty-four cells, so filling it today is twenty-four previews,
twenty-four applies and twenty-four entries in the undo stack, each one a chance to stop halfway
and leave the object half written.

The numbers exist already, in a spreadsheet, on the engineer's other screen. This part lets them
arrive in one act: one paste, one preview, one change to the file, one undo.

Part 8's own section 3 named this as its successor - "paste is a parser and a shape match with its
own refusals" - and that is what it is. Nothing about the grid, the endpoints, the edit engine or
the undo stack changes; a paste is a second way to reach `init`, and it refuses on the same
boundary a typed cell does.

## 2 What a paste is

**A paste replaces every value of one object.** It is never partial, so there is no anchor and no
focused cell: pressing Ctrl-V anywhere in the grid means the same thing, and a reader who wants to
change one number types it as before.

One edit, one preview, one entry in the undo stack. The whole `init` is written, which is the
shape `set_cell` already writes when a producer states one value for every element or none at all.

## 3 The shape it takes

The block is read as rows of tab-separated cells, which is what a spreadsheet puts on the
clipboard. It must be one of exactly two shapes, measured against the object the grid is showing.
These are the demo's, read from `grid_of` rather than counted by hand:

| Object | `shape` | Values only | With a header |
| --- | --- | --- | --- |
| `CurveA` | `[6]` | 1 row × 6 | 2 rows × 7 |
| `MapA` | `[4, 6]` | 4 rows × 6 | 5 rows × 7 |
| `BlockA` | `[8]` | 1 row × 8 | 2 rows × 9 |

A one-dimensional object is one row, as the grid draws it.

**The header form is exactly one row and one column larger**, and its first row and first column
are **discarded without being read**. That is what makes a block copied straight off the drawn
grid work - the blank corner, `AxisA (Hz)`'s readings across the top, the `CurveA (ms)` label down
the side. Nothing in the discarded cells is compared against the object's own axes: a block built
against a different axis is not caught here, and the preview is what catches it, by showing the
line the file will change before anything is written.

Two refusals are worth naming because they are what a reader will actually hit.

- **Two rows of six** - the breakpoints above the values, labels not selected - matches neither
  form. The refusal names both: *expected 1 row of 6, or 2 rows of 7 with a header; got 2 rows
  of 6.*
- **A column of six** for a curve is refused. The grid draws a curve as a row; accepting the
  transpose would double every rule here for a case the header form already complicates.

A block whose rows are not all the same length is refused as not being a table at all.

## 4 The numbers in it

### 4.1 Raw or physical

Every cell is read **in the mode the grid is showing**, exactly as a typed cell is. In physical,
each value goes through the object's conversion and is rounded to a count the datatype can hold,
so pasting `12.004` into `CurveA` stores `1200` and the grid then reads `12` - part 8's honesty
about what was stored, applied to a whole table at once. In raw, the values are counts and nothing
converts them.

### 4.2 What counts as a number

A cell's text is trimmed, and must then be **wholly** a number - the grammar `typedNumber` already
applies to a typed cell, so a numeric prefix is not a number and neither is an empty cell.

**A comma is decided for the block as a whole, before any cell is read.** If no cell contains a
point and no cell contains more than one comma, a comma is the decimal separator throughout;
otherwise a comma is a refusal. So:

- a block of `1,5` and `2,5`, which is what a French or German spreadsheet writes, is read as
  `1.5` and `2.5`;
- a block mixing `1.5` and `2,5` is refused as not knowing which it means;
- `1.234,56` is refused: its point turns the comma rule off, and what is left is not a number;
- `1 234,5` is refused rather than guessed at - whitespace inside a cell is not stripped.

A typed cell keeps the stricter grammar, and the difference is explainable: a typed cell is one
value a person is entering now, and a block carries its own evidence about which convention wrote
it.

### 4.3 What is refused

**The boundary part 8 established holds unchanged.** A paste refuses exactly what
`analysis._check_init` refuses - a fractional value under an integer datatype, one outside
`raw_min … raw_max`, one that `rounds_to_zero`, a non-bool under `boolean` - and **not** the
object's declared limits, which are shown beside its kind and datatype and never enforced.

One thing differs from a single cell: a block can be wrong in several places at once, so the
refusal names **every** offending element rather than the first, up to five and then how many
more. A reader fixing a pasted column wants the list, not one round trip per bad number.

A grid that is read-only - nothing produces the object, or more than one declaration does - has
nothing to paste into, and says so as it already does.

## 5 Where the work happens

**The split is the one part 8 already uses.** A typed cell is parsed and converted on the page -
`typedNumber` refuses `'1,5' is not a number` in the grid's own voice - and the raw count it
produces is sent to the server, which refuses what the datatype cannot hold. A paste follows that
exactly, so there is **one** implementation of the raw↔physical arithmetic rather than two that
must agree. Part 8's whole-branch review checked that arithmetic against `round_physical` and
found it identical; a second copy server-side would put that back at risk for nothing.

### 5.1 The page

`gui/src/lib/objectValues.ts` gains the parser: clipboard text and the reply in, either the rows
of raw counts or a sentence out. It owns everything decidable from the text and the shape - the
two accepted forms, the discarded header, the comma rule, "that is not a number" - and it is pure,
under Vitest's 100 % gate for lines *and* branches.

`ValuesGridView` takes a `paste` event anywhere in the grid, and gains one line under it saying
what shape it wants: `Paste 4 rows of 6 values from a spreadsheet to replace them all.` The line
is both the only way the feature is discoverable and the hint that stops the commonest refusal
before it happens, which is why it is worth its markup. No clipboard is read by the page on its
own: `navigator.clipboard.readText()` prompts for a permission in Chrome and is refused outright
in some contexts, and this interface has avoided anything that can fail for reasons the reader
cannot see.

### 5.2 The server

`src/ddd/object_values.py` gains `set_values(dictionary, built, name, rows, cache)` beside
`set_cell`, taking the counts already folded into rows. It checks every value with the same
`_acceptable` a single cell goes through and plans **one** `set` of the whole `init`.

Measured, because it is easy to say otherwise: that one `set` moves **one** line for a curve,
whose `init` is a single line of six, and **one line per row** for a map, whose `init` is written
a row to a line. One operation and one undo entry either way; not one line either way.

`GET /api/values-plan?name=&raw=` answers the existing `PlanReply`, with the counts as one
comma-separated list in **row-major order** - `MapA`'s twenty-four as one list of twenty-four, not
four lists of six. The server folds them by the shape it already knows, and refuses a list whose
length is not that shape's, which is the one thing it can check that the page can also get wrong.
It is a GET with its arguments in the query, like `/api/unit-plan`, `/api/type-plan`,
`/api/declaration-plan` and `/api/value-plan`, which is every other plan endpoint this server has.
The number of counts is bounded by the object's own shape, because the page refuses a block that
does not match before it builds a request.

Nothing is needed in the edit engine, the preview, `POST /api/edit`, or the undo stack.

## 6 Stories and screenshots

One story for the grid with its paste line, and its screenshot. The line is the only visible
change, so no existing reference moves.

## 7 Testing

- **The parser carries most of the weight**, so it takes most of the tests: Vitest at 100 % of
  lines and branches over both accepted forms for a one- and a two-dimensional object, the header
  form discarding its first row and column, the two-rows-of-six that matches neither, the
  transposed column, the ragged block, and all three arms of the comma rule.
- **Python** at the 100 % line-and-branch gate, no `pragma: no cover` and no skips:
  `set_values` in `tests/test_object_values.py` and the endpoint in `tests/test_gui_api.py`. The
  refusal that names several offenders at once is the one new thing worth pinning hard.
  **A conditional expression registers no branch with coverage.py** - four defects reached part 8's
  review through that blind spot, so a conditional whose arms need a test is written as a
  statement.
- **Five journeys** against a copy of `examples/demo`: a curve pasted and written; a map pasted
  with its header row and column and written; a block of the wrong shape refused with both shapes
  named and the file byte-identical; a value the datatype cannot hold refused with every offender
  named and nothing written; and a paste put back by Undo to the exact original bytes.
- **No Vitest test for a component or a screen**, as since part 1.

## 8 Out of scope

- **Plots.** The last third of milestone 5, still needing either a frontend dependency this GUI
  has refused since part 1 or hand-rolled SVG.
- **Copy out of the grid.** The natural twin of this, and cheap, but a separate act with its own
  questions - which mode it writes, whether it carries the header - and it waits for its own part.
- **Marking the cells a finding names.** Unchanged from part 8: the analysis files one finding for
  the whole `init`, so marking the guilty cells needs a per-element answer nothing can give yet.
- **Checking a pasted header against the object's own axes.** Deliberate, and the cost is stated
  in section 3: a block built against another axis is caught by the preview, not by the parser.
