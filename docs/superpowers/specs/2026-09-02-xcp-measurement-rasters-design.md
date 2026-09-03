# XCP measurement rasters

- **Date:** 2026-09-02
- **Status:** design approved, not implemented
- **Touches:** the loader, the models, the analysis, the data dictionary, the a2l backend

## 1 What this adds

DDD describes what a variable is and where it lives, but not when it is updated. A
calibration tool measuring over XCP has to be told which DAQ event a signal belongs to, and
the files DDD writes today tell it nothing: `SPEC.md` section 5.2 lists `IF_DATA` for XCP
with measurement rasters among the planned work, and both the faq and the acronym list say
in the present tense that no generated file contains such a section.

This design closes that gap with three pieces:

- a project wide vocabulary of **rasters**, each a named DAQ event with a period;
- a `raster` key on a variable definition and a **default** on the producing component, so
  that the common case - a component whose measurements are all updated by its one main
  task - is stated once rather than on every variable;
- a `DAQ_EVENT` in the generated a2l for every exported measurement that resolves to a
  raster.

The default is the point of the feature. A component typically produces hundreds of
measurements and updates nearly all of them in one task, so a per variable key alone would
bury the handful of exceptions in several hundred identical lines. The default is still
*authored*, by the component that owns the answer: DDD invents no raster for a variable whose
project said nothing, and a measurement that resolves to no raster reaches the a2l exactly as
it does today, without an `IF_DATA` section.

## 2 Out of scope

Everything here is deliberate, and section 11 says which parts are expected to return.

- **The transport.** `PROTOCOL_LAYER`, `XCP_ON_CAN`, `XCP_ON_ETH` and their kin describe how
  a tool reaches the ecu. DDD describes the data, and the acronym list promises as much.
- **The module level `/begin DAQ` block**, and with it the `EVENT` definitions. Writing that
  block means describing the ecu's DAQ implementation - configuration type, odt entry
  granularity and size, overload indication - none of which follows from the data. A project
  that needs a standalone a2l merges the block its XCP stack already generates. See section
  11.
- **`FIXED_EVENT_LIST`.** The emitted event is a `DEFAULT_EVENT_LIST`: the raster is the event
  the tool preselects, and the engineer may move the signal elsewhere. A raster that turns out
  wrong is then corrected in the tool rather than by regenerating the a2l.
- **`STIM` and any direction other than `DAQ`.** DDD describes measurement.
- **Rasters on calibration objects.** No DAQ list carries a `CHARACTERISTIC`.
- **More than one raster per variable.** The a2l shape is a list, and the model can grow into
  it later without breaking a file that names one.

## 3 The rasters file

`rasters` becomes the seventh file kind, added to `FILE_KINDS` in `src/ddd/loading.py` and to
the hint map beside it, so a rasters file passed where a component is expected gets the same
"list it in the `includes` of your project" message every other kind gets. Its schema is
published as `schemas/ddd_rasters.schema.json` by one entry in the kind map of
`src/ddd/cli.py`.

```json
{
  "$schema": "../schemas/ddd_rasters.schema.json",
  "rasters": [
    { "raster": "1ms",   "event": 0, "cycle": "1ms",   "description": "fast control task" },
    { "raster": "10ms",  "event": 1, "cycle": "10ms",  "description": "control task" },
    { "raster": "100ms", "event": 2, "cycle": "100ms", "description": "diagnostic task" },
    { "raster": "crank", "event": 3, "description": "crank synchronous, not cyclic" }
  ]
}
```

The file is project wide and never appears inside a component, for the reason the `Component`
model already gives for `units` and `sections`: an event channel number is a property of the
ecu's DAQ configuration, not of any one component. A component that declared its own would be
asserting a number it does not decide, and DDD would be reduced to reporting disagreements
about a fact none of them should have stated.

`src/ddd/models/rasters.py` mirrors `src/ddd/models/sections.py`:

```python
class RasterDeclaration(BaseModel):
    """One DAQ event the ecu offers, named so that a definition can refer to it."""

    raster: Annotated[str, StringConstraints(min_length=1, max_length=8, pattern=r"^\S+$")]
    event: int = Field(ge=0, le=0xFFFF)
    cycle: str | None = None
    description: str = ""


class RastersFile(FileRoot):
    rasters: Annotated[tuple[RasterDeclaration, ...], Field(min_length=1)]
```

### 3.1 `raster`

The name every reference uses, and the short name of the XCP event. The a2l gives that short
name a field eight characters wide, so a longer name is refused at load time with a message
naming the limit rather than truncated: a silently shortened name would collide with another
shortened name sooner or later, and the collision would surface in a calibration tool rather
than in DDD. `1ms`, `10ms` and `crank` fit; `Task_10ms` does not.

The human readable name is `description`, which is what the eventual `EVENT` line writes as
the long name and what the documentation shows.

The limit of eight is baked into a validator here, so its provenance matters. **Half of it is
now settled and half is not.** The protocol layer specification says an event channel name is
length-prefixed by a byte and carries no terminator, so the *protocol* imposes nothing like a
limit of eight - the original wording of this section, which credited the cap to XCP itself,
was wrong. What remains unconfirmed is the width of `EVENT_CHANNEL_SHORT_NAME` in the a2l
description of an `EVENT`, believed to be `char[9]`, which is the field a raster name is
actually written to. That still has to be read from the ASAM document alongside the grammar of
section 6.

The limit is kept at eight while that is open, because the two directions are not symmetric: a
cap that is later relaxed accepts every file it accepted before, while one that is later
tightened refuses files that were valid. Nothing DDD writes carries an event name yet, so the
constraint costs a project only the names it may choose.

### 3.2 `event`

The XCP event channel number, a json integer in `0 .. 0xFFFF`, distinct across the project.
It is the only field of a declaration that reaches the a2l in this version.

Written as a plain integer rather than as a hexadecimal string, unlike the address map: an
event number is a small ordinal chosen by whoever configured the XCP stack, not an address,
and the two notations in one project would be one notation too many.

### 3.3 `cycle`

The period of the event, written as an integer and a unit suffix, one of `ns`, `us`, `ms`,
`s`, with no space and no fractional part: `100us`, `10ms`, `1s`. Write `1500us` rather than
`1.5ms`.

**Optional.** A declaration without a `cycle` is a non cyclic event - crank synchronous, on
change, on demand - which is a real kind of raster and not an omission. This is the one place
where "not stated" carries meaning rather than falling back to something, and it is
unambiguous because the alternative reading, an unknown period, would describe an event
nobody could configure.

A stated cycle must be exactly representable as an XCP event period, that is as
`count * 10^k` nanoseconds for some `k` in `0 .. 9` - the decades from 1 ns to 1 s - with
`count` in `1 .. 255`. `500ms` is `5 * 100ms` and passes; `1234ms` is representable by no such
pair and is refused at load time by a model validator, the way `SectionDeclaration` refuses an
alignment that is not a power of two.

That rule is enforced now although this version emits no period, so that a rasters file which
loads today still loads once the module level block of section 11 arrives. The table mapping a
decade to the XCP time unit code is not needed until then, and is deliberately not written
here: it must be taken from the ASAM document at that point rather than from memory.

## 4 Referring to a raster

### 4.1 On a definition

`raster: str | None` joins `DataObject` beside `section`, at the top level of the definition
rather than inside the `a2l` block. That block is documented as holding what no other backend
interprets and what changes neither the c nor the meaning of the object. "This variable is
updated by the 10 ms task" is an engineering claim about the data that happens to have one
consumer today; `section` sits at the top level on the same reasoning, although only the c
backend reads it.

### 4.2 On a component

`raster: str | None` joins `Component` beside `description`. It is the default for every
measurement that component **produces**.

```json
{
  "component": {
    "name": "Controller",
    "raster": "10ms",
    "interface": [
      { "scope": "output", "definition": { "name": "EngineSpeed", "kind": "measurement" } },
      { "scope": "output", "definition": { "name": "FuelRate", "raster": "1ms",
                                           "kind": "measurement" } }
    ]
  }
}
```

`EngineSpeed` resolves to `10ms` from the component, `FuelRate` to `1ms` from its own key. The
two definitions are abbreviated: each also carries the `datatype`, `volatile` and `conversion`
every definition states.

### 4.3 Resolution

Two authored levels, and no more:

1. the raster named by the **producing** declaration, else
2. the raster named by the **producing component**, else
3. nothing, and the measurement reaches the a2l without an `IF_DATA` section.

A third, project wide level was rejected: one image mixes components running at different
rates, so a project default would be wrong for most of them, and "why is this signal in the
10 ms event" would have three places to look. Two levels keep the answer to that question in
the file that owns the variable.

Consequences that fall out of "producing", and that the implementation has to get right:

- A **consumer** may not state a raster at all; doing so is `consumer-raster`, the sibling of
  the `consumer-storage` finding a consumer gets for stating `init` or `section`.
- A **consumer's component default never applies** to a variable it merely reads, and this is
  not a finding. A component that produces some variables and consumes others is the normal
  case, and its default is a statement about its own production.
- A component default that covers **calibration objects** does not apply to them and is not a
  finding either, for the same reason: the default is a blanket statement about the
  component's measurements. Only an *explicit* raster on a calibration object is
  `raster-kind`.
- A **structured** variable carries one raster for the whole object, and every leaf inherits
  it, exactly as `section` is inherited. A member states no raster of its own.
- A **local** variable is produced by its component, so the default applies to it.

## 5 The dictionary

`ResolvedObject.raster` and `ResolvedLeaf.raster`, both `str | None`, carry the resolved name:
the outcome of section 4.3, not what any one file wrote.

`DataDictionary.rasters` carries the declarations whole, as `constants` are carried whole and
for the same reason: a generator DDD does not ship can then write the event list itself rather
than repeat the resolution, and a raster named by an archived dictionary stays readable after
the description files have moved on.

The dictionary carries a `ResolvedRaster` rather than the authored `RasterDeclaration`,
because it carries one field the author does not write:

```python
class ResolvedRaster(_Frozen):
    raster: str
    event: int
    cycle: str | None = None      # as authored: "10ms"
    cycle_ns: int | None = None   # the same period in nanoseconds: 10_000_000
    description: str = ""
```

Both spellings are kept for the reason `shape` and `dimensions` are both kept on an object:
the authored form is what a reader recognises, and the resolved number is what a consumer
computes with.

`DICTIONARY_FORMAT` goes from 4 to 5. Every new field is documented as absent from a
dictionary of format 4 or older, so an archived baseline still reads back.

## 6 The a2l

`MeasurementView` gains `event: int | None`, resolved in `src/ddd/backends/a2l/model.py` by
looking the object's raster name up in the dictionary's raster list. The template writes the
block after `DISPLAY_IDENTIFIER`:

```text
/begin MEASUREMENT EngineSpeed "engine speed"
  UWORD CM_EngineSpeed 0 0 0 8000
  ECU_ADDRESS 0x20000100
  SYMBOL_LINK "EngineSpeed" 0
  /begin IF_DATA XCP
    /begin DAQ_EVENT VARIABLE
      /begin DEFAULT_EVENT_LIST
        EVENT 1
      /end DEFAULT_EVENT_LIST
    /end DAQ_EVENT
  /end IF_DATA
/end MEASUREMENT
```

Measurements only, exported objects only, and only where a raster resolved. A bitfield leaf
reaches no a2l at all and therefore no `IF_DATA` either.

The event number is written in decimal, as the rasters file writes it.

**Implementation note.** The exact grammar of `DAQ_EVENT` above - the `VARIABLE` taggedunion
and the `DEFAULT_EVENT_LIST` block inside it - has to be checked against the XCP a2ml
description before release, and the generated file opened by at least one calibration tool. It
is written here as the shape the design intends, not as a quotation.

## 7 Checks

Five new identifiers in `src/ddd/diagnostics.py`, all errors:

| id | what it catches |
|---|---|
| `duplicate-raster` | a raster is declared more than once, in one file or across files |
| `duplicate-event` | two rasters claim the same event channel number |
| `unknown-raster` | a definition or a component names a raster no file declares |
| `consumer-raster` | an input declaration states a raster only the producer decides |
| `raster-kind` | a raster is stated on a calibration object, which no daq list carries |

`unknown-raster` carries `needs_every_component=True`, like `unknown-section`: the file
declaring the raster may be anywhere in the project, so the finding is only sound once the
whole project is loaded. It reports a nearest match through `_did_you_mean`, as
`_check_sections` does, and it applies to a component default as well as to a definition, a
component naming a raster nobody declares being the same mistake wherever it is written.

`consumer-raster` is a new identifier rather than a third message under `consumer-storage`,
whose published description says *storage*. A raster is not storage, and broadening that
description to cover it would make the identifier lie to anyone filtering on it in ci.

`_check_rasters` mirrors `_check_sections` in `src/ddd/analysis.py`, and the consumer rule is
reported where the claim is written, beside the existing `init` and `section` cases, on the
same reasoning: the producer may be in a file this author has never opened.

## 8 Comparison

`raster` joins `_STORAGE_FIELDS` in `src/ddd/compare.py`, whose comment - changing these
alters behaviour or the generated files, but no consumer becomes wrong - describes a changed
raster exactly. A variable moving from the 100 ms to the 1 ms event changes the a2l a
calibration engineer works with and belongs in the report of a delivery comparison; it
invalidates nobody's code.

## 9 Testing

`tests/test_rasters.py`, alongside `tests/test_sections.py`:

- each of the five checks, once finding and once clean;
- resolution across the three levels of section 4.3, including a measurement that resolves to
  nothing and reaches the a2l unchanged;
- a consumer's component default not applying to a variable it reads, and producing no
  finding;
- a component default covering a calibration object, producing no finding, while an explicit
  raster on one produces `raster-kind`;
- a structured variable, whose every leaf inherits the raster;
- the eight character refusal, and a `cycle` that is representable by no count and decade;
- a raster with no `cycle`, which is valid;
- a format 4 dictionary reading back with no rasters.

`tests/test_a2l.py` for the emitted block: present, absent, and correct for a leaf of a
structure. `tests/test_loading.py` for the new file kind and its hint. `tests/test_cli.py` for
`ddd schema rasters`.

## 10 Documentation

The five checks are public interface, and `tests/test_documentation.py` fails until each is
named in both `README.md` and `SPEC.md`. Beyond that:

- `docs/file_formats/rasters.rst`, and its entry in `docs/file_formats/index.rst`;
- the check table in `docs/consistency_checks.rst`;
- `SPEC.md` section 5.2, whose planned list loses measurement rasters and keeps the rest;
- `docs/faq.rst` and `docs/acronyms.rst`, which currently promise in the present tense that no
  generated file carries an `IF_DATA` section for XCP. That promise becomes a narrower and
  more useful one: DDD writes the event a measurement belongs to, and not the protocol or the
  transport that reaches it.
- `CHANGELOG.md`, including the dictionary format bump.

Six more pages describe the world before rasters, and this list missed every one of them.
They were found by the whole-branch review rather than by the plan, and are recorded here so
that the next feature adding a file kind starts from the full set:

- `docs/data_dictionary.rst`, which embeds a copy of the dictionary schema and walks its top
  level key by key;
- `docs/comparing_deliveries.rst`, which counts the properties `changed-storage` covers, in
  its table and again in the prose below it;
- `docs/generated_artefacts.rst`, the chapter describing what a generated a2l contains,
  record by record;
- `docs/editor_integration.rst`, which enumerates the checks the language server holds back
  when it checks a file belonging to no project;
- `docs/data_contracts.rst` and `docs/file_formats/project.rst`, which list what `ddd schema`
  publishes and what an `includes` may name. The same lists appear in `SPEC.md` sections 3
  and 3.1, and were missed there too.

The shape of the miss is worth naming: a new file kind is not one page but an entry in every
enumeration of the kinds, and every count derived from one. `tests/test_documentation.py` now
holds both documents that count the checks needing the whole project - and the list each of
them gives - to the registry, which is the part of this a test can carry.

## 11 Deferred

- **The module level `DAQ` block.** A `daq` key beside `rasters` in the same file, carrying the
  fields the block's opening line requires, and an `EVENT` per declaration. Stated, DDD writes
  the block and the generated a2l stands alone; omitted, the behaviour is this version's. This
  is where `cycle` acquires its consumer and where the XCP time unit table is needed.
- **`FIXED_EVENT_LIST`,** for a signal the ecu can only sample in its own task, most likely as
  a key on the reference rather than on the declaration.
- **Several rasters per variable,** which the a2l already shapes as a list.
