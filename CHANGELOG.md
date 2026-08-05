# Changelog

Notable changes per release, newest first.  Versions follow
[semantic versioning](https://semver.org): while the major version is `0`, a minor bump may
change the file formats, and this file says how.

The check identifiers, the command names and the json file formats are the tool's public
interface; anything else - the layout of the generated c, the wording of a diagnostic - is
not, and the templates a project provides are its own.

## Unreleased

### A `datatype` states its `conversion`, and the two spellings of a no-op stay two

**Breaking.**  `conversion` used to default to the identity.  It is required now wherever
storage is named by `datatype` - on a definition, on a structure member, on a scalar type -
for the reason `volatile` and `kind` are required: raw equalling physical is an engineering
claim, and a forgotten scaling on a fixed point value displays raw counts without anything
looking broken.  A definition that says nothing no longer loads:

```text
a.ddd.json#component.interface[0].definition: error[schema]: Value error, a 'datatype' comes with a 'conversion': the identity ({"kind": "identity"}) is an answer to state, not a default to fall into
```

A declaration naming a `typename` still states none - the type fixes it.  Also written down
while we are at it: `linear` with `factor` 1 and `offset` 0 is *not* the identity;
conversions compare as written, and the a2l carries what was written (`RAT_FUNC` against
`IDENTICAL`).

### Base and declared storage are two keys: `datatype` and `typename`

**Breaking.**  `datatype` used to accept the name of a declared type as well as the eleven
base datatypes, and the ambiguity was paid for with a lookalike rule.  It is one of the
eleven again, and a declared type is named by the new key `typename` - exactly one of the
two on every definition and on every structure member:

```json
{ "kind": "measurement", "name": "Inlet", "typename": "Sensor_t", "volatile": true }
```

The published schema says `datatype` is eleven values again, so an editor completes exactly
them and a mistyped base datatype is refused as it is typed.  A `typename` spelling a base
datatype in any case (`UINT16`) is refused; any other name is just a name - `Int16_t` is
unambiguous now, the key already saying it is declared - so the storage-stem lookalike rule
retires.  A file naming a type under `datatype` no longer loads:

```text
a.ddd.json#component.interface[0].definition.datatype: error[schema]: Input should be 'boolean', 'uint8', 'sint8', 'uint16', 'sint16', 'uint32', 'sint32', 'uint64', 'sint64', 'float32' or 'float64' (got: 'Sensor_t')
```

The `unknown-type` finding moves with the key, to `definition.typename`.  The data
dictionary is untouched: it records resolved storage, and its `format` stays 2.

### The component's list of declarations is the `interface`, and it is required

**Breaking.**  The key ``declarations`` read as the C declarations it is not, so it is named
for what it is - the component's explicitly declared data interface:

```json
{ "component": { "name": "Controller", "interface": [ ... ] } }
```

It is also required now, with no default, for the reason `volatile` and `kind` are: a
component with nothing to declare says so with an explicit `[]`, rather than with a key that
might merely have been forgotten. A component file spelling `declarations`, or omitting the
key, no longer loads:

```text
a.ddd.json#component.declarations: error[schema]: Extra inputs are not permitted
a.ddd.json#component.interface: error[schema]: Field required
```

Finding pointers follow the key (`component.interface[2].definition`). The data dictionary
is untouched: its `components` section keeps its own `declarations` key, and its `format`
stays 2.

### A repeated key inside one json object is refused

**Breaking.**  json allows `{"init": 0, "init": 255}` and parsers resolve it silently, the
last spelling winning - so the value the author reads first is not the value the tool uses.
A description file spelling any key twice in one object no longer loads:

```text
a.ddd.json: error[json-syntax]: key 'init' appears twice in one object; json would silently
keep the last spelling, so decide which one stays
```

### `volatile` is a key of every kind, and every definition states it

**Breaking.**  `volatile` used to belong to the measurement alone, where it was optional and
saying nothing meant `false`.  It is a key of every kind now - measurement, parameter, value
block, curve, map, axis - and it is required on every definition, with no default:

```json
{ "kind": "parameter", "name": "Gain", "datatype": "uint16", "init": 3, "volatile": true }
```

A definition that leaves it out does not load:

```text
sensing.ddd.json#component.declarations[0].definition.volatile: error[schema]: Field required
```

The generated c composes the two qualifiers independently, where `const` used to swallow the
`volatile` a definition asked for:

```c
volatile uint16_t Speed;            /* measurement, volatile true  */
uint16_t Speed;                     /* measurement, volatile false */
const volatile uint16_t Gain = 3U;  /* calibration, volatile true  */
const uint16_t Gain = 3U;           /* calibration, volatile false */
```

The matching `extern` declarations carry the same pair, and `--const-inputs` still adds no
second `const`.

A calibration object needs the qualifier because `const` alone lets the compiler use the initial
value in place of a read wherever it can see that value, and gcc 12.2.0 does.  Read in the
translation unit that defines it, `const uint16_t Gain = 3;` under
`apply(x) { return x * Gain; }` compiles at `-O2` to `lea eax, [rdi+rdi*2]` - the 3 has become a
shift and an add, and no load of `Gain` is left in the function.  With `const volatile` the same
function is `movzx eax, WORD PTR Gain[rip]` followed by `imul eax, edi`.  Nor is this the
optimiser, so lowering the level is no escape: at `-O0` the body is `mov eax, 3`, because the c
front end substitutes the initialiser while it parses, and an array element read at a constant
index folds there too.  Across translation units without `-flto` - which is DDD's own layout,
the definitions in `ddd_globals.c` and the reads in the components - the load does survive, but
`const` still lets the compiler serve two source-level reads from one of them and move it across
an opaque call: two reads either side of a call are one `movzwl` with plain `const` and two with
`const volatile`.  With `-flto` it folds outright.  A program that writes 7 through the object's
address prints, at `-O0`, `-O2` and `-Os` alike, `memory now holds Gain=7` and then
`apply(1) = 3`: the new value is in memory and the software is not reading it.  Reading the
object once into a ram copy at startup is no way out either - `RamGain = Gain;` is
`mov eax, 3`.

What `true` costs is read-only memory.  gcc counts a volatile access as a side effect and takes
the object out of the read-only category, so `.rodata` becomes a plain `.data`: measured on
DDD's own generated demo with the flag set this project documents, `size -A ddd_globals.o` goes
from `.rodata 84` and `.data 2` to `.data 86`, and an explicitly attributed section behaves the
same way - `.calib` is emitted `A` for const and `WA` for const volatile.  On a flash target with
an ordinary linker script that means a ram address with a load region in flash and a copy at
startup, so the tool programs a page the code never reads and the next reset overwrites what the
tool wrote.  A project that calibrates online settles the placement in its linker script - DDD's
own memory placement is section 3.6 of `SPEC.md` and still planned - and DDD states no
preference between the two and reports nothing about the choice, because only the project knows
which cost it is paying.

Hand-written code that consumes the object may need its helpers re-typed: passing a
`const volatile` array to one that takes a plain `const` array is
`error: passing argument 1 of 'sum' discards 'volatile' qualifier`, reported under
`-Werror=discarded-qualifiers`, and casting the qualifier away is closed by `-Wcast-qual`, which
this project's documented flag set includes.  The qualifier also buys freshness by giving up
coherence: the compiler has to re-read at every mention, so a parameter set read at several
points of one control step can straddle a calibration write, and a loop over a `const volatile`
gain does not vectorise at `-O3`.

**Migrating**: add the key to every declaration of every kind.  `ddd check` names each one that
still lacks it, and no severity softens it - the finding is `schema`, and `-W schema=warning` is
refused with `the severity of check 'schema' cannot be changed`.  A project that does not
calibrate a running ecu states `false` throughout and keeps its data in flash exactly as before;
one whose calibration tool writes through an object's address states `true` and places those
objects itself.

### `name-collision` also sees the enum type names

A variable may not share its name with an enum, as it already may not share one with an
enumerator.  The types header spells the enum out as `typedef enum { ... } Mode;`, and c keeps
a typedef name at file scope in the same namespace as the variables, so `uint8_t Mode;` beside
it is a redeclaration.  It was caught for the enumerators and not for the name they are
declared under, which left it to the compiler and to a message about a generated file.

### Structured datatypes

A `types` description file declares the types a project names, and a declaration names one with
the key it already had:

```json
{ "types": [
  { "type": "scalar", "name": "Temperature_t", "datatype": "uint16", "unit": "degC",
    "conversion": { "factor": 0.1, "offset": -40 }, "limits": { "min": -40, "max": 150 } },

  { "type": "struct", "name": "Sample_t", "members": [
    { "name": "value",     "member": "value", "datatype": "Temperature_t" },
    { "name": "timestamp", "member": "value", "datatype": "uint32", "unit": "ms" },
    { "name": "ready",     "member": "bits",  "datatype": "uint16", "bits": 1 } ] }
] }
```

```json
{ "scope": "output", "definition": {
    "name": "Inlet", "kind": "measurement", "datatype": "Sample_t", "volatile": true } }
```

**One key names a type, everywhere.**  `datatype` accepts one of the eleven base datatypes or the
name of a type the project declares, on a structure member and on a component declaration alike.
There is no second key beside it: a `type` key would have to mean "the name of a declared type" in
those two places and "which shape this entry has" at the top of a types entry, and one key with
one meaning is worth what it costs.

**A scalar type is agreement by naming rather than by copying.**  Three components consuming an
engine speed used to write out the datatype, the unit, the scaling and the limits, leaving DDD to
notice when one of them was wrong.  If all three say `Speed_t`, there is nothing left to disagree
about.  A type fixes exactly `datatype`, `unit`, `conversion` and `limits`; `kind`, `dimensions`,
`init`, `volatile` and `a2l` stay on the variable, because two measurements of one type may well
differ in whether an interrupt writes one of them.  Naming a type and then restating what it
fixes is an error rather than an override, so "where is this unit written down" keeps one answer.

**A member says what its bytes mean as well as where they are.**  It carries `unit`, `conversion`,
`limits` and `a2l` of its own, or names a scalar type that fixes them - never both.  It carries
no `init` and no `volatile`, because those belong to a variable rather than to a type: two
variables of one structure may start at different values, and a qualifier applies to a whole c
object.  For the same reason a member states no `kind`; the declaration decides, so a structure
mixing measured and calibrated members is not something the format can express rather than
something DDD has to report.

**The limits of a bitfield come from its width.**  A two bit `mode` offered to a calibration tool
as `0 .. 65535` lets somebody enter a value the field cannot hold, and the software then reads
back something else.

#### What it generates

The structures reach `ddd_types.h`, each after every structure it nests, because c needs the
nested one complete first - a template may loop over `model.structures` and write them out as
they come:

```c
typedef struct
{
    uint16_t value;           /**< The reading itself */
    uint32_t timestamp;       /**< Milliseconds since the last reset */
    uint16_t ready : 1;       /**< Set once the sensor has produced a first reading */
} Sample_t;
```

A scalar type is not a c typedef: `Temperature_t` says what a number *means*, and the storage it
means it in is a `uint16_t`.  Carrying the name into the generated c would be a second feature -
it needs the dictionary to record which type each object came from - and it is not this one.

```c
volatile Sample_t Inlet;
extern volatile Sample_t Inlet;
```

In the a2l a structure is **flattened into one object per member**, named by the c expression that
reads it, so the a2l, the generated c and a map file all spell one thing one way:

```text
/begin MEASUREMENT Inlet.value "The reading itself"
  UWORD CM_LIN_DEGC 0 0 -40 150
  ECU_ADDRESS 0x00000000
  SYMBOL_LINK "Inlet.value" 0
/end MEASUREMENT
```

The offset in `SYMBOL_LINK` is `0` and means it: the offset of a symbol from itself.  DDD predicts
no member offset and no bit position - c leaves both to the compiler - and `--address-map` is
keyed on these paths, so a build reports them the way it already reports the address of any other
symbol.  An array of structures contributes its elements, `Inlet.cell[0].raw` and the rest, since
no single record describes two of them at once; an array of values stays one record with a
`MATRIX_DIM`.

**A bitfield member reaches no a2l.**  `&s.ready` does not compile, so no build can report where
that member is, and a `SYMBOL_LINK` carries a byte offset with nowhere to put a bit position:
leaving the mask out would claim the whole word and writing zero would claim nothing.  Both are
wrong answers dressed as output, so the member waits for a build that can say.  Everything else
about it - the c declaration, the width, the limits - is generated as usual.

#### The rest of it

`ddd schema types` publishes the contract, `examples/structures` is a working project, and the
language server jumps from a `datatype` to the type it names and lists the declarations that use
one.  Six checks: `duplicate-type`, `unknown-type`, `type-kind` and `type-cycle`, plus
`name-collision` and `reserved-identifier` reaching type names.

The rest of the tool sees a structured variable as the objects it is made of: `ddd list` and the
`ddd check` summary count its members, and `ddd compare` compares them, so a delivery that drops
or retypes one is reported the way any other removal is.  What it does not yet report is a member
*reordered* within a structure, which moves every address after it.

`unknown-type` is the price of one key naming both, and it is worth stating.  A mistyped base
datatype is a well formed *name*, so the schema can no longer reject `uint166` as you type -
except that a name reading as a storage stem with the digits wrong is refused outright, which
catches `uint166`, `int16`, `float3` and `sint_16`.  What that cannot catch, a transposition like
`unit16`, is answered by the check: *did you mean 'uint16'?*

**The dictionary format is now 2.**  It carries `types`, `instances` and `leaves` beside the
objects, so a dump written by this version cannot be read by an older DDD - which is what the
format stamp exists to say plainly rather than have it misread.

**Migrating**: a `types` file entry needs `"type": "struct"`; a member that nested a structure
writes `"datatype": "Other_t"` instead of `"member": "struct", "type": "Other_t"`; and a member's
`"kind"` is deleted.  Nothing else in a description changes.  A project that copied
`examples/templates` should take the new `ddd_types.h.jinja2`, which renders the structures -
without it a structured variable is declared against a type its header never defines.

### Storage, interface and presentation are told apart

Three properties that used to be settled the same way - "the producer wins, with a warning" -
turn out to be three different kinds of thing, and are now handled as such.

**`volatile` is interface.**  It reaches every consumer's own header as a type qualifier,
`extern volatile uint16_t Speed[4]`, which is what tells that component's code not to cache the
value and not to expect two reads to agree - and, on a calibration object, what keeps the
compiler from using the initial value instead of reading the variable at all.  A component
declaring the opposite has misunderstood what it is compiled against, so a disagreement is now a
`definition-mismatch` error rather than a warning it loses.

**Every declaration has to say the same thing**, and every declaration has to say it: the key is
required on every definition of every kind, and there is no value it takes by staying silent.
That is unlike `limits`, which a declaration may omit because DDD derives them from the datatype
and the conversion - there is nothing to derive here.  A component whose description does not
say a variable is volatile is a component whose author was never told, which is the thing an
interface description exists to prevent.

**Migrating**: every component that reads a volatile variable has to declare it volatile too.
`ddd check` names each one.

**`export` is nobody's alone.**  Which signals a calibration engineer needs to see is not a
property of whoever happens to write the variable, so **any** component may now ask for an
object to reach the a2l, and asking wins over declining:

```json
{ "scope": "output", "definition": { "name": "X", "kind": "measurement",
                                     "datatype": "uint8", "volatile": false,
                                     "a2l": { "export": false } } }
{ "scope": "input",  "definition": { "name": "X", "kind": "measurement",
                                     "datatype": "uint8", "volatile": false,
                                     "a2l": { "export": true } } }
```

`X` is exported.  The rule is order independent, so two consumers can never conflict and there
is no finding to invent for them.  A producer that says `false` while nobody asks still keeps
the object out, exactly as before.

The key therefore has three states, and "unstated" is one of them rather than a spelling of
`true`.  Everything downstream asks for the resolved answer: a dictionary with no `a2l` block
at all exports its objects, and `ddd compare` reads a baseline that omitted the key and a
candidate that spells out `export: true` as the same a2l entry rather than as a `changed-a2l`
nobody can act on.  That is what keeps an older or third party dictionary readable without
rewriting it.

**What is left of the `a2l` block is presentation** - a `format` string, a
`display_identifier` - where two values genuinely cannot both be used.  That stays a
`storage-mismatch` warning with the producer winning.

### `init` belongs to the producer

**Breaking.** A declaration whose `scope` is `input` may no longer state `init`.  What a
variable starts out as is decided by the component that produces it, so a component that only
reads it was never expressing an opinion that could lose - it was claiming storage it does not
own.  The new `consumer-storage` check reports it, where the claim is written:

```text
controller.ddd.json#component.declarations[0].definition.init: error[consumer-storage]: 'ValueA': the initial value is decided by the component that produces the variable, not by 'Controller', which reads it
```

**Migrating**: delete `init` from every `input` declaration; nothing else changes, since the
producer's value was already the one being generated.  The check is relaxable, so a large
project can lower it with `-W consumer-storage=warning` while the keys come out.

This also fixes the reason those keys were there.  A consumer that left `init` out used to be
reported as specifying "none" against the producer's value, so restating it was the only way to
keep a run quiet - silence was read as a claim.  `init` has left the `storage-mismatch`
comparison entirely; what that check still compares is the `a2l` block, and only the part of it
that is presentation.

The other two keys the trap applied to are out of it as well, by the two ways there are of
getting out.  `volatile` is required on every definition now, so there is no silence left to
read as a claim, and what it states is compared as interface rather than as storage.  `export`
kept the right to say nothing and gained a third state for it, so a declaration that omits the
key is stored as having omitted it rather than as having asked for the default.

### `ddd lsp`: the checks, in the editor

A language server, speaking the Language Server Protocol on stdin and stdout.  It reports the
consistency checks while a description file is being written - which a json schema cannot do,
being per file and static: whether an `axis` names a declared axis, whether exactly one
component produces a name, whether two components agree on a unit, whether a name follows the
convention.

Hovering anywhere in a declaration - on the name, the datatype, the scope - shows the resolved
object rather than the authored text: the shape a curve
took from its axis, the limits derived from its datatype and conversion, its producer and its
consumers, what an enum's values are called, and the initial values as a sparkline.  A map is
drawn a row at a time against one shared scale; values that are all the same are stated instead
of drawn.  These are the *initial* values - DDD describes an interface, not calibration data.

It navigates as well.  Go to definition on an `input` - or on an `axis`, `x_axis`, `y_axis` or
`input` reference - lands on the declaration that writes it, in whichever component that turns
out to be; find references lists every declaration of it.  The same works from a `type` to the
structure it nests and back, and from an `includes` entry or a project's `naming` to the files
they name, wildcards included.

A quick fix reconciles a `definition-mismatch`.  With the cursor on a `unit`, a
`conversion`, a `datatype` or any other key the declarations of one object have to agree on,
the editor offers every way of reconciling it: take the producing component's value, spread
this one to the others, or - when nobody else states the key - remove it.  A consumer is shown
the producer's answer first and the producer its own, because which side owns the variable is
the rule the rest of the tool is built on.

`kind` is the one key the declarations have to agree on that is never offered, because its
value decides which *other* keys a definition may carry: writing one declaration's `kind` into
another would leave keys the new kind forbids and drop keys it requires, and the file would
stop loading rather than stop disagreeing.

The value is copied as source text rather than re-serialised, so a project's formatting
survives a fix; a declaration that never mentioned the key gets it inserted beside its
neighbours, and removing one takes exactly the comma that joined it.

`F2` renames a variable everywhere the project writes it - every declaration, and every
`axis`, `x_axis`, `y_axis` or `input` naming it, across as many files as that takes.  A name c
reserves, one that is not a usable identifier, one the project already declares, or one an enum
or an enumerator already occupies is refused with the reason before anything is written, since
a rename touches several files at once and an unusable name would otherwise surface a build
later.  Only the characters between the quotes are
replaced, so a project's formatting survives, and free text is left alone.

It reports on open and on save, and publishes for every file of a project rather than only the
one on screen, because half of a disagreement is always in the other component.  Both sides of
a conflict are marked: `ddd check` reports it once with a note at the other declaration, which
suits a list read whole, but in an editor a file with no finding on it looks correct - and of
two components declaring the same output, neither is the innocent one.  Which project
a file belongs to is read from the `ddd-build.json` below, so the editor applies the severities
the build applies.  Editors that launch a server themselves need nothing further, and `-b DIR`
points at an out-of-tree build.

A file no build claims is checked on its own, but only for what one file can decide.  Read
alone, a component has inputs nobody writes, outputs nobody reads and axes declared in files
nobody handed over, so `missing-producer`, `unused-output` and `unknown-reference` are left out.
A check that needs the whole project now says so where it is registered, rather than in a list
somewhere else that can be - and was - forgotten.

No new dependency: the protocol framing is a hundred lines and DDD still installs with
pydantic and jinja2 alone.

A VS Code extension comes with it, in `editors/vscode`, because VS Code cannot start a language
server without one.  It is a launcher and deliberately nothing more - two settings, one restart
command - so an editor that starts servers itself needs none of it.

It is **not published to the marketplace**.  Every release attaches a `ddd-<version>.vsix` to
its GitHub release, installable with `code --install-extension ddd-<version>.vsix` or through
"Install from VSIX…" in the Extensions view.  There is no automatic update for an extension
that did not come from the marketplace, so reinstall it when you upgrade the python package.

### `ddd build-info`, so a build can tell an editor what it does

A new command, and a `ddd-build.json` that `ddd_generate()` now writes into its output
directory at configure time.  It records the two things no description file can state: which
project description this image is generated from, and the severity policy it is generated
under.

Without `PROJECT`, the project description is collected out of the c link graph and written
into the build tree, so nothing in the source tree names it - which means a tool reading only
`*.ddd.json` cannot work out which components belong together.  Nothing in the build reads the
new file; it exists so that an editor can report what the build reports, the same bargain
`SCHEMA_DIRECTORY` already makes for the json schemas.

A `SEVERITY` naming a check that does not exist is now refused while the project is being
configured, rather than when the build later runs the check.

### The published schemas carry their documentation

`ddd schema` writes the same contract as before - nothing it publishes accepts or rejects a
file it did not accept or reject previously - and a lot more of what an editor can show while a
description file is being written:

* every key of every format now has a description, including the 27 in the dictionary and
  naming schemas that used to hover blank;
* every value of a closed set has one too.  `uint16` says how much storage it costs and which
  values fit in it, `"kind": "curve"` says what a curve is as against a value block.  The text
  is both spelled out in the description of the key and repeated in `enumDescriptions`, the
  array VS Code reads to document each entry of the completion dropdown;
* each file states its dialect, `https://json-schema.org/draft/2020-12/schema`, so a validator
  no longer has to guess which version of json schema it is reading, and is titled for the
  format it describes rather than for the python class behind it;
* descriptions are rendered as the markdown an editor shows, so a reference written for the api
  documentation no longer arrives as the literal characters `` :class:`Foo` `` or points a
  reader at a python module they do not have.

The rules that span several keys - which keys a `bits` member takes, that a segment has tokens
or a pattern and not both - are stated in the descriptions rather than as constraints, so a
validating editor still accepts a few files that `ddd check` rejects.

## 0.2.0

Breaking changes to the description file format and to `ddd generate`.  Migrating an existing
project means editing its `*.ddd.json` files and its build integration; `ddd check` reports
every file that still needs it, so the migration is finished when the check is clean.

### The c templates now belong to the project

DDD no longer decides what the generated c looks like.  What used to be built in is shipped
as an example instead, and `ddd generate` requires the directory to render:

```bash
ddd templates-dir                      # prints a working set to copy
ddd generate project.ddd.json -o gen -t templates
```

Every `*.jinja2` in that directory renders to a file named like it without the extension, a
name starting with `_` is a helper that renders nothing, and a name containing `{component}`
renders once per component.  The templates therefore name the generated files, which is why
**`--prefix` is gone** - rename a template to rename its output.  In CMake, `PREFIX` is
replaced by a required `TEMPLATE_DIRECTORY`.

The a2l generator is unchanged and stays internal: ASAP2 is defined by ASAM, not by a project.

### `kind` is required on every definition

A definition no longer defaults to `measurement`; it states its kind, including a measurement:

```json
{ "kind": "measurement", "name": "ValueE", "datatype": "uint16" }
```

The default made a bare definition match two variants at once in the published json schema,
which an editor validating a file reported as an ambiguity.

### Datatypes are named without reference to c

| was | now |
| --- | --- |
| `bool` | `boolean` |
| `int8`, `int16`, `int32`, `int64` | `sint8`, `sint16`, `sint32`, `sint64` |

The unsigned and floating point names are unchanged.  The generated c and a2l are unaffected:
a `sint16` is still `int16_t` in c and `SWORD` in the a2l.

### Editor support

* a top level `$schema` key is accepted and ignored, so a description file can be bound to
  its schema; every other unknown key is still rejected as a typo,
* `ddd schema all -o DIR` writes every schema at once, for a project to commit,
* `ddd_generate(... SCHEMA_DIRECTORY <dir>)` writes them at configure time instead, so they
  cannot describe a version that is no longer installed,
* every field of every contract carries its documentation, so hovering a key explains it.

### Added

* `ddd sources FILE` lists every description file a project is built out of, which is what a
  build system needs to know when to run DDD again,
* `ddd templates-dir` prints the example templates,
* `-v` as a short form of `--version`,
* `name-collision`, `a2l-unrepresentable` and `project-mismatch` checks,
* archived dictionaries carry a `format` version, so a dump from a newer DDD is refused
  rather than misread,
* the documentation is published at <https://sauci.github.io/ddd/>, rebuilt from the sources
  on every change rather than written out by hand.

### Fixed

* **`MATRIX_DIM` was transposed.**  ASAP2 lists the fastest running index first, so a c array
  `[2][3]` is `MATRIX_DIM 3 2 1`; it was emitted in c order, and a calibration tool addressed
  the wrong element of every multi-dimensional object.
* **Names that would not compile passed the checks.**  Enum names, enumerator names and the
  identifiers `<stdint.h>` declares are now screened; enumerators of different enums, and an
  enumerator sharing a name with a variable, are reported as `name-collision`.
* `INT64_MIN` was emitted as a literal no c compiler accepts.
* A shell completion could execute code from somebody else's convention file.
* A legal name was rejected when a repeatable segment was followed by an optional one.
* `ddd sources` omitted a file it had read but rejected, so a build never noticed the fix.
* Descriptions and preprocessor conditions could break out of the comment they were written
  into; NaN, infinity, non-utf-8 files and several malformed inputs now produce a located
  finding instead of a traceback.
* `ddd check --baseline` reported the baseline's own findings as findings of the run.
* `ddd dump` writes only the dictionary to stdout, so `> baseline.json` archives it in both
  output formats.

## 0.1.0

First release.
