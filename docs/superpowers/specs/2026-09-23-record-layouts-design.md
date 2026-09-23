# Point counts stored ahead of a table

A project migrating an ECU data dictionary of some 15,000 objects to DDD found one gap between
DDD's a2l and a usable one (`ddd-feature-request-record-layouts.md`, against 0.10.0). Its
firmware stores the number of axis points *inside* every curve, map and axis, ahead of the data,
in the object's own type:

```
8093841c  10000000 10000000 00000000 ...     a 16 x 16 map of uint32
          nx = 16  ny = 16   then the 256 values
```

A map stores x then y (an 8 by 11 map begins `0800 0b00`), a curve stores its one count, and an
axis stores its own. The interpolation routines read the counts to learn the shape of the table,
so an object without them does not end early: its first value is read as a count. The legacy
a2l describes it with `NO_AXIS_PTS_X` / `NO_AXIS_PTS_Y` ahead of `FNC_VALUES` / `AXIS_PTS_X`.
In that project the convention covers 1,548 objects: 600 maps, 437 curves and 511 axes.

DDD cannot say any of this. `_RecordLayoutBuilder` (`src/ddd/backends/a2l/model.py:538`) writes
two layouts, both with the data at position 1 and keyed by datatype alone, so the a2l gives the
right `ECU_ADDRESS` and a layout that contradicts it: a calibration tool shows the counts as the
first values and everything after them shifted. A plugin cannot amend the a2l
(`Plugin.__post_init__` refuses a plugin named after a built-in artefact), and the project
worked around the c side in its own templates.

This adds a description of that storage, honoured by both backends.

## 1 Decisions already taken

- **A storage fact, not an a2l option.** The setting changes the object's size and where its
  data starts, so the c backend lays the counts out and the a2l describes them. Out of the box,
  DDD's c and a2l cannot disagree about where the data starts.
- **Stated per project, overridden per component.** The convention belongs to the interpolation
  library, which is usually project wide; a component taken from another library states its
  own. The override follows the producer, as a component's `raster` does. There is no per-object
  override and no sub-project level: nothing asks for either.
- **In c, a flat array.** Counts first, then the values in the `[y][x]` order the nested form
  had. That is what the project's templates and the legacy image both do, and no padding
  question arises.
- **The counts use the object's own datatype, floats included.** A `float32` table stores
  `8.0f`. Every example in the request is an integer, and the request says "the object's own
  type"; nothing in the format refuses a float count.
- **No `STATIC_RECORD_LAYOUT`.** See section 5.

## 2 The description

A new key, `point_counts`, takes `"none"` or `"leading"`. An enumeration rather than a boolean
so that it reads as what it describes, and so that another placement ASAP2 allows can be added
without renaming anything.

- **`project.point_counts`** is the default for every curve, map and axis of the project. It is
  `"none"` when no project file states it. At most one project file may state it: a second
  file stating a *different* value is a `schema` finding at the second file, the rule plugin
  settings follow (`loading.py`, `_register_settings`). A second file stating the same value
  is accepted, since the two agree.
- **`component.point_counts`** overrides the default for the curves, maps and axes this
  component *defines* (the producing declaration). It applies to nothing the component reads,
  and to no other kind of object: a component that states it and defines no table is not an
  error, since the key may well be written ahead of the tables.

```json
{ "project": { "name": "ecu", "includes": ["**/*.ddd.json"], "point_counts": "leading" } }
```

Both keys are optional, so every existing description stays valid and means what it meant.
The published schemas are regenerated.

## 3 What is resolved

Every `ResolvedObject` carries a resolved `point_counts`: `"leading"` or `"none"` for a curve, a
map or an axis, and `"none"` for every other kind. It is the component's value when the
producing component states one, and the project's otherwise.

It is a new field of the dump, so `DICTIONARY_FORMAT` becomes **9** (format 8 shipped in 0.10.0).
A format 8 dictionary reads back with `"none"` everywhere, which is what it meant. The format's
docstring gains the sentence saying so.

What the counts are, in storage order:

| kind  | counts                         |
|-------|--------------------------------|
| axis  | its own size                   |
| curve | the size of its axis           |
| map   | x axis size, then y axis size  |

They are not part of `init`. DDD derives them from the axes, so an author never writes them and
an `init` keeps the shape it has today.

### Findings

- **`point-counts-unrepresentable`** (error, at the producing declaration): the object's datatype
  cannot hold one of its counts. That is a `boolean` table, or an integer type whose range does
  not reach the count (a `uint8` axis of 300 points, a `sint8` map with 200 rows). Without it the
  c initialiser overflows without a word. A float type always holds a count.
- **`point-counts-mismatch`** (warning, at the curve or map): a curve or a map resolves to one
  convention and one of its axes to the other. ASAP2 can describe the mix, one record layout per
  object, but an interpolation routine is unlikely to read it, so the author is told and the
  output is written as resolved.

Both are added to `docs/consistency_checks.rst` with the rest.

### `ddd compare`

`point_counts` joins the interface fields of an object (`_INTERFACE_FIELDS`, `compare.py:276`),
so a table whose convention changes between two deliveries is reported as `changed-interface`,
an error. Every reader compiles against a different declaration and reads its data at a
different offset, which is the rule that file already applies to the width of a bitfield: "the
c the consumers compile against is a different structure either way".

## 4 The c backend

All of it is in the c model (`src/ddd/backends/c/model.py`, `literals.py`). The shipped templates
(`examples/templates/`) render `definition` and `declaration()`, which already compose from
`array_suffix` and `initializer`, so they need no change, and neither does a project template
that uses the same fields.

**`array_suffix` gives the storage.** For an object resolved to `"leading"`:

```c
const uint16_t M[2 + (11) * (8)] = { 8, 11, ... };   /* map: y then x, as its [y][x] */
const uint16_t C[1 + (8)] = { 8, ... };              /* curve */
const sint16_t MX[1 + (8)] = { 8, ... };             /* axis */
```

A dimension spelled with a constant stays spelled: `[2 + (NY) * (NX)]`. For every `"none"` object
the suffix is exactly what it is today.

**`initializer` is always written** for a counted object, as one flat brace list, counts first:

- with an `init`: `{ 8, 11, 1, 2, 3, ... }`, the values in the row order the nested braces used;
- with `init` null: `{ 8, 11 }`, the rest zero. The counts cannot be left to the startup code.

A count whose axis size is spelled with a constant is written by name (`{ NX, NY, ... }`), so the
initialiser follows the constant if it is changed.

**Two new `ObjectView` fields**, present on every object:

- `dimensions`: the table's shape as written, e.g. `(11, 8)` or `("NY", "NX")`, `()` for a
  scalar. This is the request's first smaller item: a template no longer parses `array_suffix`
  back apart to learn the shape.
- `point_counts`: the counts in storage order as written, e.g. `(8, 11)` or `("NX", "NY")`, and
  `()` when the object carries none. A template tests it to tell the two forms apart.

Unchanged: structure members (a member cannot be a table), the doc comment, sections, `volatile`,
and the extern declarations of the component headers, which go through `declaration()` and pick
up the new suffix by themselves.

## 5 The a2l backend

An object resolved to `"leading"` references a layout of its own kind. `"none"` objects keep
`RL_VALUES_<T>` and `RL_AXIS_<T>` unchanged.

```
/begin RECORD_LAYOUT RL_MAP_COUNTED_ULONG
  NO_AXIS_PTS_X 1 ULONG
  NO_AXIS_PTS_Y 2 ULONG
  FNC_VALUES 3 ULONG ROW_DIR DIRECT
/end RECORD_LAYOUT

/begin RECORD_LAYOUT RL_CURVE_COUNTED_UWORD
  NO_AXIS_PTS_X 1 UWORD
  FNC_VALUES 2 UWORD ROW_DIR DIRECT
/end RECORD_LAYOUT

/begin RECORD_LAYOUT RL_AXIS_COUNTED_SWORD
  NO_AXIS_PTS_X 1 SWORD
  AXIS_PTS_X 2 SWORD INDEX_INCR DIRECT
/end RECORD_LAYOUT
```

A counted curve cannot share the values layout, as it does today, because it has one count
where a counted map has two. `RecordLayoutView.entry` becomes `entries`, a tuple of lines, and
`project.a2l.jinja` loops over it. That template is the backend's own and not a project
extension point, so no project depends on the old field. `ECU_ADDRESS`, `MAX_AXIS_POINTS`,
`AXIS_DESCR` and `COM_AXIS` are unchanged: the address is the start of the object, which is
where the counts now are.

What ASAP2 1.6.1 settles (section 3.5.91 `NO_AXIS_PTS_X`, section 3.5.103 `RECORD_LAYOUT`):

- The form is `NO_AXIS_PTS_X <position> <datatype>`, and the counts' datatype is independent of
  the values'. The spec's own `3D_structure_table_int` is `NO_AXIS_PTS_X 1 UWORD`,
  `NO_AXIS_PTS_Y 2 UWORD`, `FNC_VALUES 3 SWORD`, the requested shape exactly.
- Positions ascend with no gaps, and without `STATIC_RECORD_LAYOUT` "the number of axis points
  (NO_AXIS_PTS_?) has to be located in the ECU memory before the axis points (AXIS_PTS_?) and
  the function values (FNC_VALUES)". Leading counts are the form the text requires.
- **`STATIC_RECORD_LAYOUT` is not written.** Without it, a tool that lets an engineer remove
  points compacts the data behind the new count, which is what a routine computing
  `y * nx + x` from the stored count expects, and what the legacy a2l does.

What the text does not address: a `COM_AXIS` curve or map carrying its own `NO_AXIS_PTS_X`
beside the count of the `AXIS_PTS` it refers to. The legacy a2l writes it, the image stores it,
and the only other truthful description of those bytes would be `RESERVED`. It is written.

## 6 The address map recipe

The request's second smaller item. The recipe on `docs/build_integration.rst` runs
`nm --defined-only`, and its pattern `[BbDdGgRrSs]` takes file-local statics too: two
translation units each defining a static `cntr_50ms_decimate_5` made `load_address_map` refuse
the map, correctly, as one symbol with two addresses. Every object a dictionary describes is a
global, so the recipe gains `--extern-only` and a sentence saying why. If a CMake test runs the
recipe, it runs the new one.

## 7 Documentation

- `docs/data_dictionary.rst`: the setting, where it may be stated and how it resolves, with the
  requester's layout (the dump bytes and the a2l) as its example.
- `docs/templates.rst`: `dimensions`, `point_counts`, and what `array_suffix` and
  `initializer` hold for a counted object.
- `docs/generated_artefacts.rst`: the three counted record layouts.
- `docs/consistency_checks.rst`: the two findings.
- `SPEC.md`: the key in the project and component sections, and the resolved field of the
  dictionary.
- `CHANGELOG.md`: the feature, format 9, and the recipe change.

## 8 Testing

Test first, as every change here is.

- **Loading:** the key on a project and on a component; a second project file stating a
  different value (`schema`), the same value (accepted); an unknown value refused by the schema.
- **Resolution:** project default only; component override in both directions; a table read
  by a component that states otherwise keeps its producer's value; format 8 read-back.
- **Findings:** `boolean` table, integer overflow at the boundary (255 fits a `uint8`, 256 does
  not), a float that always fits, a map whose y axis disagrees.
- **c:** the suffix and initialiser of a counted axis, curve and map; constant-spelled sizes and
  counts; `init: null`; `dimensions` and `point_counts` on counted and uncounted objects; an
  unchanged output for a project that never states the key.
- **CMake:** compiles a project with a counted map and checks with `sizeof` and a read of the
  first elements that the counts sit where the a2l says.
- **a2l:** the three layouts, their names shared between objects of one kind and type, and a
  mixed project.
- **compare:** a changed convention reports `changed-storage`.
- Coverage stays at 100 %.

## 9 Out of scope

- A per-object override, a sub-project level, counts behind the data, or a count datatype
  different from the object's. Each is a small extension of the enumeration or the resolution
  once a project needs it.
- `ddd gui`. It is being developed on another branch at the same time; it will not offer the new
  key until a later change teaches it to. This branch touches the published schemas and the
  project and component models, where a conflict with that work is possible at merge time, and
  keeps those edits small for that reason.
