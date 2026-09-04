# Object identity across deliveries

- **Date:** 2026-09-03
- **Status:** implemented and merged to master; sections 8, 9 and 10 amended in flight
- **Touches:** the models, the data dictionary, the comparison, the cli, the language server's ranges

## 1 What this adds

DDD keys an object on its name. `DataDictionary.comparable` in `src/ddd/ir.py` builds
`{name: entry}`, and `compare` in `src/ddd/compare.py` walks the baseline's names looking each
one up in the candidate. A rename is therefore not a thing DDD can see: it reads as
`removed-object`, an error whenever a component read the object, next to `added-object`, an
info, with nothing relating the two. The interface comparison never runs across the pair, so a
rename that also widened a datatype or rescaled a conversion is not reported at all - the two
findings that replace it say only that one name left and another arrived.

This design gives every data object an identity that survives its name:

- an optional `id` on the producing declaration, opaque and immutable;
- pairing in `compare` on that id, falling back to the name, so a rename becomes one
  `renamed-object` finding that the ordinary interface comparison still runs across;
- `reused-name`, which catches the dangerous direction - a spelling freed by a rename, or by a
  deletion, being claimed by a different object, so that a calibration dataset keyed by that
  spelling silently binds to storage nobody intended;
- an old-to-new name map falling out of a comparison, for migrating datasets, recordings and
  test scripts.

The id is a *join key between two deliveries*, not a link inside one. Within a project the
producer and its consumers go on binding by name, and `ddd check` is untouched. This is what
keeps the change small: only `compare` reads the id, and only the producing declaration writes
one.

The project being in git is what makes the record trustworthy rather than a second thing to
maintain. The id is committed by the same change that does the rename, so *when*, *who* and
*why* are already answered by `git blame` and the commit it points at. The file format
therefore carries no date, no release tag and no author: that data would be a hand-maintained
copy of what the repository already knows, and copies drift. It also means DDD never reads git,
and the runtime dependencies stay pydantic and jinja2.

## 2 Out of scope

- **Names other than a data object's.** Components, types, enumerators, units, constants,
  sections, rasters and the project keep name-as-identity. Renaming a component is a
  build-visible break, but not one a calibration dataset or a recording feels, which is the
  failure this design is for.
- **Members of a declared type.** A leaf reaches the dictionary under its access path,
  `Inlet.latest.value`, assembled from an instance and a type. The path is part of its
  identity here (section 3.3), so renaming a *member* remains an invisible rename. This is a
  known gap, not an oversight; section 14 says what closing it would cost.
- **The id as an in-project link.** A consumer keeps naming the object it reads. Making the id
  the resolution key would rewrite the loader, the index, the language server's navigation and
  every error message that names an object, and would buy nothing: the c and a2l backends
  still emit names.
- **Inferring a rename from properties.** No heuristic pairs a removal with an addition on
  matching kind, datatype and unit. The one concession is a note, section 5.5, which asserts
  nothing.
- **Reading git.** No command shells out. Section 9 is a documented recipe.

## 3 The `id` key

### 3.1 What an id is made of

Twelve characters of Crockford-style lowercase base32 - `abcdefghjkmnpqrstvwxyz0123456789`,
excluding `i`, `l`, `o` and `u` - drawn from `secrets.choice`. About sixty bits: a collision
across a project is not a thing that happens, and `duplicate-id` catches it if it does.

```json
{
  "name": "FilterGain",
  "scope": "output",
  "kind": "parameter",
  "id": "k7m2q9xr4t8w",
  "datatype": "float32",
  "conversion": { "kind": "identity" },
  "volatile": false
}
```

The shape is enforced by a pydantic pattern on the field rather than by a check, so a
hand-typed id is refused as a `schema` finding and the published json schema makes an editor
flag it before the tool is run at all.

Freezing the object's *first name* as its id was considered and rejected. It would migrate an
existing project with a mechanical copy and read well in a log, but an id that looks like a
name invites somebody mid-rename to bring it along - and that edit destroys the identity with
nothing able to detect it, returning the comparison to exactly the state this design exists to
leave. An opaque token does not invite the edit.

### 3.2 Where it may be written

On the declaration whose `scope` is `output`, and on an instance of a declared type, which is
an object in the dictionary like any other. A declaration whose scope is `input` stating an
`id` is refused by `consumer-identity`, on the reasoning `consumer-storage` already applies to
`section` and `init` in section 3.3.1.2 of `SPEC.md`: a component that only reads an object has
no claim over what that object *is*, and the finding belongs where it is written rather than
where it is overruled.

An id is immutable by convention, not by mechanism - no single version of a project can
observe that one changed. Section 5.5 is the net under that.

### 3.3 Structured objects

`DataDictionary.comparable` spans `objects` and `leaves`, and a leaf has no declaration of its
own to carry an id: `Inlet.latest.value` is assembled from an instance and the members of its
type. A leaf's identity is therefore the pair *(its instance's id, its member access path)*,
and it pairs across two deliveries when both halves match. Renaming the instance is tracked;
renaming a member of the type is not, and lands as a removal and an addition, with the note of
section 5.5 if nothing else about it changed.

## 4 Adoption

### 4.1 Format 6

`DICTIONARY_FORMAT` in `src/ddd/ir.py` goes from 5 to 6. `ResolvedObject` and
`ResolvedInstance` gain `id: str | None = None`, documented as empty in a dictionary from
format 5 or older, in the wording those models already use for `dimensions` and `references`.

A baseline older than format 6 has no ids at all, which is not the same as having none: its
objects pair by name and no rename is ever inferred from it. This mirrors `_VALUE_SHAPE_FIELD`
and `_DEFERRED_INTERFACE_FIELDS` in `src/ddd/compare.py`, where a baseline that recorded no
dimension spellings makes the comparison defer to values rather than conclude a difference from
a silence.

### 4.2 `missing-id`

An object without an id is reported by `missing-id` at **info**. The key is optional, so
nothing existing breaks and no project is forced to migrate; a project that has finished
migrating turns it into a gate with `-W missing-id=error`, and one that never adopts ids is
disturbed by nothing but section 5.5's note.

`missing-id` is not `needs_every_component`: it reads one declaration and is right about it
whatever else exists.

### 4.3 `ddd id --assign`

`ddd id --assign FILE...` stamps an id into every producing declaration and instance that
lacks one, writing the files in place, and prints how many it wrote. A declaration that already
has one is left alone, which makes the command idempotent - a second run must change nothing,
or the command re-identifies the project on every invocation.

This is the first command that edits a hand-authored `*.ddd.json`, and it is defensible because
the project is in git: the tool proposes, the diff is reviewed, `git checkout` undoes it. It
writes only the new key and preserves the rest of the file's formatting; a file it cannot parse
is reported and skipped rather than rewritten.

## 5 Comparison

### 5.1 Pairing

`compare` builds an id index over each side and pairs in two passes:

1. entries carrying the same id are paired, whatever their names;
2. every entry still unpaired is matched by name, as today.

Both regimes therefore coexist without a special case, which is what lets a project migrate
one component at a time. What is left after the two passes is a genuine removal on the baseline
side and a genuine addition on the candidate side.

A swap - `A` renamed to `B` and `B` to `A` in one change - falls out of this correctly and with
no handling of its own. It is in the test matrix because it is the case no name-based heuristic
can ever get right.

### 5.2 `renamed-object`

Same id, different name. Reported at **warning**, and the ordinary comparison of section 4.1 of
`SPEC.md` - interface, storage, limits, owner, condition, a2l - still runs across the pair, so
a rename that also changed the object reports both.

Warning rather than error because nothing *inside* the project is broken: every consumer names
the object it reads, so a rename that left one behind already failed `ddd check` in the same
change. What breaks is outside DDD's sight - calibration datasets, recorded measurements, test
scripts and requirement documents keyed by the old spelling - and a warning is what says "this
delivery needs a migration step" without claiming the software is wrong.

### 5.3 `reused-name`

A name present on both sides that now names a different object, proved either of two ways.
Both sides state an id for it and the ids differ - two declared objects, unrelated. Or pairing
(section 5.1) has already matched the baseline's object under that name to a *different* name
elsewhere in the candidate, by id - which proves that whatever still answers to this name in
the candidate is not it, whether or not that entry has stated an id of its own. Reported at
**error**, above the removal and addition it accompanies, because it is the failure that
compiles, links, runs and reads the wrong storage: a dataset or a recording keyed by that
spelling binds to the new object as readily as it did to the old one, and nothing about the
delivery looks broken.

The second proof matters most in exactly the regime section 5.1 exists for: a project adopting
ids one component at a time. The claimant of a freed name is under no less suspicion before it
has been stamped with an id than after - the reasoning above is about wrong storage, and wrong
storage does not care which side of the migration wrote the claim. `reused-name` is also the
highest-severity finding this feature produces, which makes silence here, for no better reason
than "the claimant hasn't been stamped yet", the worst place for the feature to have a blind
spot.

When the baseline's object survives elsewhere in the candidate under a new name, the finding
carries a note saying so - the spelling was freed by a rename and claimed in the same delivery,
which is the worst version of it. A project that reuses names deliberately relaxes the check
with `-W reused-name=warning`.

### 5.4 References compared by id

`_INTERFACE_FIELDS` compares `references`, and those are referents *by name*: `{"axis":
"InletAxis"}` for a curve, `{"input": "..."}` for an axis. Left alone, renaming one axis would
report `changed-interface` on every curve and map that refers to it - a crowd of findings about
objects that did not change, burying the one that did.

So a reference is resolved to its referent's id before being compared, falling back to the name
when either side's referent has no id. And where a reference still differs only because compare
has already reported that referent as renamed, the derived finding is suppressed: the same
principle `compare` applies to narrowed limits today, that a consequence must not bury its
cause.

### 5.5 The note under an unpaired identical pair

Nothing in a single version can tell that an id was edited by hand or mangled by a merge; the
object simply becomes two unrelated objects again. The net is a note rather than a finding.

When a removal and an addition are both left unpaired and *every compared field is identical* -
`differing()` over the interface and storage tables returning empty - the removal carries a
note: `'FiltGain' was removed and 'FilterGain' added with an identical interface; if that was a
rename, the id did not travel with it`. It asserts nothing and invents no pairing, in the shape
`_check_address_coverage` in `src/ddd/cli.py` already uses for the map entries it cannot claim,
where reading the two halves together is what identifies a rename.

This is also the only part of the feature that does anything for a project which never adopts
ids at all.

## 6 Checks

| check | severity | reported when | overridable | needs every component |
| --- | --- | --- | --- | --- |
| `duplicate-id` | error | two objects in one project carry the same id | yes | no |
| `consumer-identity` | error | a declaration whose scope is `input` states an `id` | yes | no |
| `missing-id` | info | a producing declaration or instance has no `id` | yes | no |
| `renamed-object` | warning | baseline and candidate share an id under different names | yes | n/a |
| `reused-name` | error | baseline and candidate share a name that now names a different object | yes | n/a |

`duplicate-id` is not `needs_every_component`, and for the reason every other duplicate check
is not: the flag marks a check that reaches the *wrong* answer when a file is missing, which is
a check concluding something from an absence. A duplicate concludes from a presence - seeing
one half of a pair makes the run incomplete, not wrong - so it sits with `duplicate-type`,
`duplicate-unit` and `duplicate-raster`, and the count of checks needing every component stays
at nine.

## 7 The migration map

`ddd compare BASELINE CANDIDATE --renames PATH` writes the pairs a dataset migration tool
wants, rather than making it parse findings:

```json
[{ "id": "k7m2q9xr4t8w", "from": "FiltGain", "to": "FilterGain" }]
```

Sorted by the new name, so two runs of the same comparison produce the same file and a diff of
two such files means something. Written whether or not the comparison found errors - a delivery
that cannot be accepted still needs its renames listed, so that whoever fixes it knows what
moved. An empty comparison writes `[]` rather than no file, so a build step can tell "no
renames" from "compare never ran".

## 8 The a2l - withdrawn

This section specified an `ANNOTATION` carrying an object's previous name into the generated
a2l, reached by `ddd generate a2l --baseline`. It was gated on a question: does the calibration
tool in use resolve a dataset label through an `ANNOTATION`? It said that if the tool ignores
annotations, the section is wasted work and should be deleted rather than built.

The question has been answered and the section is withdrawn. The tools in use are Vector CANape
and ETAS INCA. `ANNOTATION` is a documentation container in ASAP2 - a label, an origin and free
text - and nothing in the standard gives it a linking or aliasing meaning. A tool may well show
the text in an object's properties; neither tool resolves a dataset label through it, because
dataset matching goes by name and memory layout and no standard mechanism says otherwise. The
annotation would therefore have produced a remark for a human to read, not the automatic
migration it was meant to enable.

What the section was reaching for is built and lives elsewhere: `ddd compare --renames` writes
the old-to-new pairs a migration script or a tool's own mapping import consumes
([section 7](#7-the-migration-map)). That is the functional path; the annotation was only ever
going to be the decorative one.

Nothing here was implemented, so there is nothing to remove from the code. The a2l backend is
untouched by this design.

## 9 History in git

An earlier draft of this section claimed that an immutable id makes one object's history exact
across a rename, with `git log -S`. That was verified false, twice and independently, in
freshly built scratch repositories. `-S` is the pickaxe: it shows a commit only when the
*number of occurrences* of a string changes. A rename edits `name` in place and never touches
the `id` line, so the count does not move, and a plain `git mv` is invisible to it too, under
git's default rename detection.

What holds is narrower, and held from the start: nothing rewrites the id, so it is still
there, under whatever name and in whatever file, after a rename or a move. That is what the
rest of this section rests on, not `-S`:

```bash
git grep k7m2q9xr4t8w -- '*.ddd.json'
git log -S k7m2q9xr4t8w --oneline -- '*.ddd.json'
```

The first finds where the object lives now, whatever it is called. The second finds the
commit that first wrote the id, and a commit where the declaration was added to or removed
from a file - not a rename, and not a plain `git mv`. What a rename actually was is not a git
incantation but `renames.json`, written by `ddd compare --renames`, and the `renamed-object`
finding it comes with.

This is documentation, in the faq. No command wraps it: a `ddd history` would pull git into a
tool whose dependencies are pydantic and jinja2, to save typing two lines git already gives
you.

## 10 The dictionary

`ddd dump` writes the id where an object carries one and `null` where it does not, exactly like
`section`, `raster`, `condition` and the other optional fields of the same models. An earlier
draft of this section asked for a dictionary from an unmigrated project to stay byte-identical
to what format 5 wrote, apart from the format stamp, to protect existing consumers of a dumped
dictionary - there are none, so nothing needs protecting, and the key instead follows the
convention its two closest precedents, `dimensions` and `raster`, already set: neither was held
to a byte-identical bar when it arrived. `ddd list` gains no column: the id is machinery, and a
person reading a list of objects is looking for names.

The published `ddd schema dictionary` and the per-kind schemas grow the key, and
`schemas/*.schema.json` are regenerated and committed.

## 11 Testing

- `tests/test_compare.py` - the pairing matrix as a table: id to id renamed, id to id
  unchanged, id to nameless, nameless to nameless, the swap, name reuse with and without the
  baseline object surviving, a format 5 baseline against a format 6 candidate, and the note of
  section 5.5.
- `tests/test_compare.py` - the reference cascade: renaming an axis reports one finding, not
  one per curve and map that refers to it.
- `tests/test_comparison_tables.py` - a recorded decision that `id` is in **neither**
  comparison table, and why. This matters more than it looks. `TestComparisonTables` exists so
  that a difference between the two tables is a decision rather than an oversight, and without
  the entry somebody later adds `id` to `_INTERFACE_FIELDS` as an obvious omission - turning
  the single commit that stamps ids into a `changed-interface` error on every object in the
  project.
- `tests/test_models.py` - the id pattern refuses a hand-typed value; `consumer-identity` on an
  input declaration; `duplicate-id` across two components.
- `tests/test_cli.py` - `ddd id --assign` writes ids, is idempotent on a second run, leaves an
  unparseable file alone, and reports what it wrote; `--renames` writes sorted pairs and writes
  `[]` for a comparison with no renames.
- `tests/test_documentation.py` passes without amendment only if every new check is named in
  both `README.md` and `SPEC.md` and the new command is documented, which section 12 is.

## 12 Documentation

- `SPEC.md` section 3.3 gains the `id` key and section 3.3.1.2 the `consumer-identity` rule;
  section 4 gains `duplicate-id`, `consumer-identity` and `missing-id`; section 4.1 gains
  `renamed-object` and `reused-name` and the note; section 5.2 gains the annotation if section
  8 is ever built.
- `README.md` gains the three check rows in the checks table, the two rows in the comparison
  table, and `ddd id` in the command table.
- `docs/comparing_deliveries.rst` gains the migration story end to end: stamp ids, archive the
  dump, compare, read `--renames`, migrate the datasets.
- `docs/faq.rst` gains "how do I find out what happened to this variable" with the `git log -S`
  recipe of section 9.
- `CHANGELOG.md` records the format 6 bump and what a migration costs, as the project's `0.x`
  convention requires.

## 13 Increments

1. **The record** - the `id` key, format 6, `duplicate-id`, `consumer-identity`, `missing-id`,
   `ddd id --assign`, schemas, documentation. Useful alone: it makes an accidental name reuse
   catchable within one version.
2. **Comparison** - pairing, `renamed-object`, `reused-name`, references by id, the note. The
   payload.
3. **The migration map and the git recipe** - `--renames` and the documentation of section 9.
4. ~~**The a2l**~~ - withdrawn; see [section 8](#8-the-a2l---withdrawn).

The implementation plan covered 1 to 3, which is the whole of what shipped.

## 14 Deferred

- **Member renames.** Closing section 2's gap means an id on a type's member, which makes a
  leaf's identity *(instance id, member id)* and lets a member be renamed like anything else.
  Deferred because it doubles the surface of the feature to serve a rename that a project can
  avoid, and because a type is shared: an id on a member is an identity for every instance of
  the type at once, which is a different question from the one this design answers.
- **`ddd id --verify`.** A mode that fails when any object lacks an id, for a project that
  wants the gate without turning `missing-id` into an error across every run. Wait for someone
  to want it.
- **Renames across a merge of two projects.** Two projects assembled into one image may each
  carry an object with the same id if one was copied from the other. `duplicate-id` reports it,
  which is right, but says nothing about which is the original. Wait for the case to occur.
- ~~**A language server code action for `missing-id`.**~~ Deferred here when this design
  shipped, and built afterwards: the server offers the fix on a declaration with no id, writing
  what `ddd id --assign` writes and reading where it goes from the same place, so the two cannot
  drift. It is offered only where `missing-id` is reported, which keeps it inside the project's
  own severity policy. See `docs/editor_integration.rst`.