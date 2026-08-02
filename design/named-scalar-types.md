# Named types in the types file

**Status**: proposal, nothing implemented.
**Prerequisite**: a component declaration cannot yet refer to a declared structure at all
(CHANGELOG, "Not yet available"). That reference is the shared foundation; this proposal
assumes it is designed once, here, for both structures and scalars.

## The problem

`_INTERFACE_FIELDS` in `src/ddd/analysis.py` is the list of things every component sharing an
object has to agree on:

```
kind, datatype, unit, shape, conversion, limits, references
```

Today agreement is reached by *repeating* all of it in every component that declares the
object, and having the analysis compare the copies and report `definition-mismatch`. Three
components consuming an engine speed each write out the datatype, the unit, the scaling and
the limits, and DDD's job is to notice when one of them is wrong.

That is checking what could be construction. If both components said "this is a `Speed_t`",
there would be nothing to disagree about.

The project has already grown one named type, in the wrong place. `EnumConversion` carries a
`name`, `_EnumRegistry` deduplicates by it, `DataDictionary.enums` publishes it, and
`_register_enum` exists solely to report that two same-named enums disagree - the very problem
a named type removes. An enum is a named type that had nowhere to live, so it moved into
`conversion`.

## Not in scope: opening the base datatype set

A project must not be able to declare its own base integer types.

`A2L_TYPE` and `C_TYPE` are total functions over the eleven `Datatype` members into sets fixed
by ASAM and by `<stdint.h>`. There is no three-byte entry in either and there will not be one.
An open set lets a description declare storage that is well formed, passes every structural
check, and then cannot be emitted - turning an impossibility-by-construction into a runtime
diagnostic, which is the wrong direction.

It would also cost the editor integration. `Datatype.schema_description` derives its hover text
from `_DATATYPE_INFO` precisely because the set is closed and known when the schema is
generated; project-defined datatypes cannot be enumerated in a published schema, so the
dropdown and the per-value documentation both disappear.

Width freedom is already served where it belongs: `bits`, constrained to fit its storage unit.

## The contract

### One key names a type, everywhere

The central decision. `datatype` accepts either a base datatype or the name of a type the
project declares:

```json
{ "kind": "measurement", "name": "EngSpd", "datatype": "Speed_t" }
{ "name": "latest", "member": "struct", "datatype": "Sample_t" }
```

This is the alternative to introducing a second key (`type`) alongside `datatype`, and it is
better for one reason: a `type` key would collide with itself. It would mean "the name of a
declared type" on a declaration and on a member, and "which shape this type entry has" at the
top of a type entry. One key, one meaning, is worth the trade.

It replaces `Member.type`, which exists today and is unreleased, so the rename is free.

**Cost, stated plainly**: the published schema can no longer say `datatype` is one of eleven
values. It becomes `anyOf: [Datatype, identifier-shaped string]`. VS Code still offers the
eleven as completions from the first branch, but it stops rejecting a typo in a base datatype
name at the moment it is typed - that becomes an `unknown-type` finding from `ddd check`
instead. This is the single biggest thing given up in this proposal and it should be weighed
before anything is written.

### The types file becomes a tagged union

`TypesFile.types` currently holds `StructType` only. It becomes a union discriminated on
`type`, the way `Member` is discriminated on `member` - stated, never inferred from which keys
are present, for the reason already recorded in `ddd.models.types`:

```json
{ "types": [
  { "type": "struct", "name": "Sample_t", "members": [ ... ] },

  { "type": "scalar", "name": "Speed_t",
    "datatype": "uint16",
    "unit": "rpm",
    "conversion": { "factor": 0.25 },
    "limits": { "min": 0, "max": 8000 },
    "description": "Crankshaft speed as every component agrees to see it" }
] }
```

A scalar type fixes exactly the four fields that make two declarations interchangeable:
`datatype`, `unit`, `conversion`, `limits`. It fixes nothing else. In particular it does **not**
fix `kind`, `dimensions`, `init`, `volatile` or `a2l`: those are properties of a variable, not
of a type, and two measurements of the same type may well differ in whether one is written by
an interrupt.

### Restating what the type fixes is refused

If a declaration names `Speed_t` and also states `unit`, that is an error, not an override.

This follows the rule the file already applies to members - "a key belonging to another shape is
refused rather than ignored" - and it keeps one answer to "where is this object's unit written
down". An override rule would mean the answer is "in one of two places, and you have to know
which wins".

Mechanically this is a `model_validator` on the definition, so it surfaces under the `schema`
check with a located pointer, exactly as the member shape rules do today. No new check
identifier.

## Reference resolution

A type reference is resolved in `_Analysis`, alongside `_check_types`, and **before**
`_collect_component` builds any declaration - a declaration whose type is unknown has no
datatype, so every later check on it would be reasoning about nothing.

Ordering within the analysis:

1. `_check_types` - as today: every nested name is declared, no cycles. Extended to walk scalar
   entries, which cannot nest and therefore cannot cycle.
2. **new** - resolve each declaration's `datatype` against the declared types. A name that is
   neither a base datatype nor a declared type is `unknown-type`, reusing the existing check;
   its registered description broadens from "a structure member nests a structure that no file
   declares" to cover a declaration too.
3. Everything downstream sees declarations whose datatype, unit, conversion and limits are
   already filled in, and needs no knowledge that a type was involved.

Using a struct type where a scalar is required, or the reverse, is the one genuinely new
failure. It is the same shape as `reference-kind` ("a reference points at an object of the wrong
kind") but about types rather than data objects. Two options, and I would take the first:

- reuse `unknown-type` with a message that says what was found instead. No new identifier, no
  README and SPEC churn, and `test_documentation` stays quiet.
- add `type-kind`. Cleaner to filter on, at the cost of a new public check name.

## Interaction with `_INTERFACE_FIELDS`

This is the part worth getting right, and the existing machinery already does most of it.

**Resolve first, then compare.** Expansion happens before `_compare` runs, so
`_INTERFACE_FIELDS` keeps working unchanged on `datatype`, `unit`, `conversion` and `limits`.
A component that names `Speed_t` and one that still writes `uint16` / `rpm` / `factor 0.25`
inline compare equal - which is what makes migrating a large project one component at a time
possible at all.

**Add the type name as an optional compared field.** `_ComparedField` already supports exactly
this: `_differing` skips an `optional=True` field when either side is `None`, which is how
`limits` behaves now.

```
_ComparedField("type", <the named type or None>, ..., optional=True)
```

The result is the behaviour you want in all three cases:

| component A | component B | outcome |
| --- | --- | --- |
| `Speed_t` | `Speed_t` | agree, nothing compared twice |
| `Speed_t` | inline, identical | field skipped; resolved fields agree; accepted |
| `Speed_t` | `Rpm_t`, identical content | **reported** |

The third row is a decision, not a consequence. I would report it: if two components name
different types for one object, the project has not decided what that object is, and the fact
that the two types happen to agree today is not something to rely on tomorrow. It reports under
`definition-mismatch`, whose registered description gains "named type" - no new check.

The pay-off is the message. Today a mismatch reads `datatype: uint8 != uint16`; with types it
reads `type: 'Torque_t' != 'Speed_t'`, which names the actual mistake instead of one of its
symptoms.

## What reaches the backends

Nothing changes for them, and that is deliberate.

`ResolvedObject` already carries `datatype`, `unit`, `conversion` and `limits` explicitly, and
`ir.py` already promises that "everything in here is resolved". Scalar types are expanded in the
analysis, so the c backend, the a2l backend, every project's templates and `compare` - which
operates on two `DataDictionary` values - are untouched.

One exception, if you want it: for generated c to *use* `Speed_t` as a typedef rather than
`uint16_t`, the dictionary has to carry which type an object came from. That means an optional
`type` field on `ResolvedObject`, which is a change to the shape of the document, which means
`DICTIONARY_FORMAT` goes to 2 - the models are `extra="forbid"`, so an older DDD reading a newer
dump fails, and the format stamp exists for exactly this. Worth doing, worth doing knowingly,
and worth leaving out of the first stage.

## Two gaps this surfaces

Both exist today and both get worse with more named things:

- **Type names are never screened against c.** `is_reserved_identifier` is applied to component
  names, variable names, enum names and enumerator names, but `_check_types` does not apply it
  to a structure name. A structure called `int` generates a header that does not compile. This
  should be fixed for structures regardless of this proposal, and covered for scalar types when
  they land.
- **Type names and variable names share no namespace check.** A scalar type and a variable may
  currently take the same name. In c a typedef and a variable can coexist, so this is legal, but
  it reads badly and `name-collision` is where the decision belongs.

The naming convention correctly stays out of this: `check_names` is applied only to data object
names, with the reason stated in the source ("a convention written for variables would reject
every one of them"). A convention for type names would be a separate feature and is not proposed
here.

## Staging

Each stage is releasable on its own.

1. **Declarations can refer to a declared structure.** The prerequisite that already has to
   happen. It establishes `datatype`-names-a-type, the resolution step and the `unknown-type`
   broadening, with no new type kind.
2. **`type: "scalar"`.** The union, the four fixed fields, the refusal to restate, the optional
   `_INTERFACE_FIELDS` entry.
3. **Enums move into the types file** as `type: "enum"`, with the inline form kept and defined
   as declaring a type of the same name. `_EnumRegistry` becomes a lookup rather than a
   reconciler.
4. **Optional**: carry the type name into the dictionary, bump `DICTIONARY_FORMAT`, let the c
   backend emit typedefs.

## Open questions

1. **`datatype` carrying both, or a separate `type` key?** The proposal takes the first and
   pays for it with a weaker json schema on `datatype`. This is the decision to make first
   because everything else is written in terms of it.
2. **Two different type names for one object - error or warning?** Proposed: error.
3. **May a scalar type fix `dimensions`?** Proposed: no - an array is a property of the
   variable. But `ValueBlock` and `Axis` make this arguable, and a `Table16_t` is a thing people
   ask for.
4. **Stage 3 at all?** Folding enums in is the tidiest outcome and the most disruptive change to
   a file format that is already released.
