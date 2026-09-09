# Specification catch-up - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring `SPEC.md` back in line with what the 0.8.0 tool and the unreleased master do, and state the public contracts it calls public but never describes: the listings, the `--renames` file, the A2L file name and record order, the CMake targets, the plugin name grammar, and the dictionary.

**Architecture:** Prose only. Every edit below states behaviour the tool has today (verified by passes 1 to 5 of the review); nothing here changes code, and two behaviours that other branches change (dropped declarations, dangling references) are deliberately left out so that each behavioural branch carries its own spec sentence. Where the spec's silence hides a decision the maintainer has not made (a reference into another component's `local` object; `typename` compared as spelled or as resolved), this plan documents what ships and the pull request description flags the sentence.

**Tech Stack:** Markdown (GitHub flavoured; `tests/test_documentation.py::TestSpecCrossReferences` checks that the table of contents is the outline and every `[section N](#anchor)` resolves).

**Spec:** `docs/superpowers/reviews/2026-09-08-complete-review.md` (branch `review/complete-review-2026-09-08`), passes 1 to 5; the exact items are copied below so this plan stands alone.

## Global Constraints

- Branch: `docs/spec-catch-up`, off `master`. Push after every task. Do not open a pull request.
- Line numbers below are those of `SPEC.md` on master at `441c600`; locate each edit by the quoted words, not by the number, because earlier edits move later lines. Read the whole paragraph around each edit before changing it, and keep the document's voice: rationale beside the rule, present tense for what the tool does, the requirement words of section 1.1 only where 1.1 means them, British spelling, ` - ` with spaces rather than an em dash, check identifiers in backticks.
- After every task run `python -m pytest tests/test_documentation.py tests/test_transcripts.py --no-cov -q` from the repository root (with this checkout: `PYTHONPATH` is set by `pyproject.toml`'s `pythonpath`). A new heading needs its line in the table of contents at the top of the file, at the right indentation, with the anchor rule the test applies (lower case, spaces to hyphens, punctuation dropped).
- Before the last commit: the full `python -m pytest` (the 12 environmental failures of the review baseline are known), and the ruff format check (`<venv>/Scripts/python.exe -m ruff format --check .`; the venv is at `C:/Users/lmbsog0/AppData/Local/Temp/claude/C--git-ac11-ddd/ab815568-8224-42f5-b802-44dd98973875/scratchpad/venv`).
- Do not touch: the `unknown-reference` / `reference-kind` entry and the `incomplete-project` entry of section 4, the `missing-producer` and `unused-output` entries (other branches own them); anything about JSON booleans as an integer `init`; anything deciding whether a reference into another component's `local` object is a use.
- Commit messages: a lowercase sentence, no prefix, trailer `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

---

### Task 1: Section 2 and the intro of section 3

**Files:** Modify `SPEC.md` (the concept table at lines 139-161, the section 3 intro at 176-205, 3.1 at 206-251).

- [ ] **Step 1: Concept table.** Add two rows after the `**data object**` row:

```
| **instance** | a declaration naming a structure type ([section 3.7](#37-type-description)): one C object whose members are data objects in their own right, each reached by its access path |
| **leaf** | one value-holding member of an instance, as the dictionary and the A2L see it; a member naming an external type is opaque and is no leaf |
```

- [ ] **Step 2: "storage" means the 3.3.1.2 group.** The word is used for three things. Keep it for the key group of 3.3.1.2 and for the check names, and reword the datatype sense: at line 459 ("the storage (`datatype` or `typename`)") write "the datatype, stated as `datatype` or as `typename`"; at 529 ("A definition states its storage exactly once") write "A definition states its datatype exactly once, as `datatype` or as `typename`"; at 753, the same substitution; at 769 ("opaque storage") write "opaque bytes". Check each with `grep -n "storage" SPEC.md` and change only the datatype sense.

- [ ] **Step 3: Section 3 intro.** After "only the first two can be the root of a run." (line 188) add: "Handed any other kind as the root, the tool reports `file-kind` with a hint naming the `includes` entry that should carry the file, and exits 1 ([section 7](#7-tool-interface))." After the sentence on `$schema` ("a top level `$schema` key **shall** be accepted and ignored...") add: "as a string or `null`; any other value is `schema`." After the sentence "A file that is not valid UTF-8, or whose nesting exceeds the depth the parser accepts, is refused the same way (`json-syntax`)." add: "So is a file spelling `NaN` or `Infinity`, which JSON does not define; a number too large for the parser's floating point, such as `1e400`, reads as infinity and is refused as `schema` where it is written. A file whose top level is not an object is `file-kind`."

- [ ] **Step 4: 3.1.** At line 231 ("Include cycles are an error") write "Include cycles are an error (`include-cycle`)". Where 3.1 describes literal includes and `file-not-found` (247-250), add: "A file that is not named `*.ddd.json` is `file-extension`, reported after the file is read; loading continues."

- [ ] **Step 5: Test and commit**

Run: `python -m pytest tests/test_documentation.py --no-cov -q`

```bash
git add SPEC.md
git commit -m "define instance and leaf, and keep storage for the key group" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push -u origin docs/spec-catch-up
```

---

### Task 2: Sections 3.3 to 3.10

**Files:** Modify `SPEC.md` 3.3 (294-553), 3.4 (554-597), 3.5 (598-665), 3.7 (702-802), 3.8 (803-836), 3.9 (837-892), 3.10 (893-942).

- [ ] **Step 1: 3.3, the key table and the kinds.** Line 317, the `a2l` row's default: replace "export" with "`{}`, exported unless a declaration states `export` ([section 3.3.1.3](#3313-presentation))". Line 391, `dimensions` of a measurement: replace "non-empty" so the sentence reads "a list of sizes, `[]` or absent for a scalar". Lines 362-364 (`boolean` init): add "written as `true`/`false` or as `1`/`0`". After the sentence at 371-372 ("`boolean` does not count as an integer datatype"), nothing changes.

- [ ] **Step 2: 3.3.1.1 Interface.** After the limits rule (466-468, "`limits` are the one interface key a declaration **may** leave out"), add two sentences: "An omitted `unit` is the empty unit and compares as such: a consumer stating none against a producer stating `rpm` is `definition-mismatch`. A `typename` compares as what it fixes - the datatype, unit, conversion and limits of the scalar type - so a declaration naming `Speed_t` and one spelling `uint16` with the same unit, conversion and limits agree; a structured object compares by its type name." Then in 3.3.1.2 (477) write "The storage keys are `init` and `section`; the group also holds `id`, `raster` and `extensions`, the keys a consumer **must not** state."

- [ ] **Step 3: 3.3.1.3 Presentation.** After "left out only when every stated answer is `false`" (505-507) add: "with one exception the A2L needs: an axis an exported curve or map refers to, and the measurement an exported axis is indexed by, are carried whatever they state ([section 5.2](#52-a2l)). `export` **may** also be stated as `null`, which counts as unstated."

- [ ] **Step 4: 3.4 Conversions.** After the mapping form of enumerators (566-568) add: "The textual order of the enumerators counts in both forms: two declarations listing the same pairs in a different order disagree (`enum-conflict`)." After 570-573 (the `typedef enum`): add "The variable itself is declared with its base datatype, never with the enum type; the `typedef enum` exists for the enumerators ([section 5.1](#51-c-code))."

- [ ] **Step 5: 3.5 Memory placement.** After the structure rule at 645-650, add: "The need of a base datatype is its size in bytes, `boolean` counting one; an array needs what its element needs; a structure the strictest of its members, nested structures included. A structure reaching an external type, or one that nests itself, has no known need and earns no `section-alignment`."

- [ ] **Step 6: 3.7 Type description.** In the scalar and struct entries (744-758) add "`description` is optional" where the external entry already says it (762), and the same for a member. After the `header` forms (two forms are stated) add: "a spelling containing whitespace, a quote inside the name, or an unclosed angle bracket is `schema`." At 787-788 (`init` on a structured declaration is `type-kind`) leave as is; section 4's entry is extended in Task 3.

- [ ] **Step 7: 3.8 and 3.9.** 3.8: add "An empty spelling is `schema`." 3.9: after the sentence naming where a constant may be spelled (877-881), add "A structure member's `dimensions` **may** name a constant as well, reported at the member (`unknown-constant`) when the name is not declared."

- [ ] **Step 8: 3.10 Rasters.** Add, where `consumer-raster` and `raster-kind` are introduced: "An `input` declaration of a calibration object stating a `raster` earns both `consumer-raster` and `raster-kind`, because both rules are broken."

- [ ] **Step 9: Test and commit**

```bash
python -m pytest tests/test_documentation.py --no-cov -q
git add SPEC.md
git commit -m "state the file format rules the tool applies and the spec left unsaid" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push
```

---

### Task 3: Section 3.11 and section 4

**Files:** Modify `SPEC.md` 3.11 (943-1022) and 4 (1023-1214).

- [ ] **Step 1: 3.11.** In the `"plugins"` bullet, after "claims a name another plugin already has is `plugin-invalid`.", insert: "A plugin's `name` matches `[a-z][a-z0-9_]*` and is none of `c`, `a2l` and `all`, which name the built-in artefacts of `ddd generate`; each check identifier it registers is `<name>/<check>` with `<check>` matching `[a-z][a-z0-9]*(-[a-z0-9]+)*`. Malformed means: no `PLUGIN`, a `PLUGIN` that is not a `Plugin`, a name outside the grammar or reserved, a check identifier outside its grammar, or a check registered twice. A module is imported once per process; an edit takes effect in the next run, and in the editor after the server is restarted." In the `"extensions"` bullet, after "as any unknown key is." add: "A project block keyed by a name no loaded plugin has is `unknown-extension`, as on a definition." (If branch `fix/lsp-windows-uris-and-buffers` has already merged its sentence "Naming a plugin runs its module..." into this bullet, keep it.)

- [ ] **Step 2: Section 4, the general rules (1039-1060).** After the note rule ("with a note pointing at the producer's declaration or the first loaded one"), add: "for `limits`, at the first declaration that states them ([section 3.3.1.1](#3311-interface))". After the ordering rule of findings (1580-1582 is in section 7; here nothing), nothing.

- [ ] **Step 3: Section 4, the entries.** Apply, entry by entry:
  - `type-kind` (1113-1115): append "or a structured declaration carries a key a structure cannot take, such as `init` ([section 3.7](#37-type-description))".
  - `reserved-identifier` (1145-1150): append "It applies to the names that reach the generated C: projects, components, data objects, declared types, structure members, enums, enumerators and constants; not to `display_identifier`, which reaches only the A2L."
  - `a2l-unrepresentable` (1184-1185): replace "an object the A2L exports" with "an object the A2L carries, the closure over references included ([section 5.2](#52-a2l))".
  - `address-missing` (1188-1191): replace the sentence "It fires only when a map is supplied: without one every address is zero by construction, which is the run a build makes before it has linked anything." with "It fires only when a map with at least one entry is supplied: without a map, or with an empty one, every address is zero by construction, which is the run a build makes before it has linked anything ([section 7.1](#71-build-system-integration)). It is one finding per run, naming up to five of the uncovered objects and counting the rest, with a note listing the entries of the map that name nothing the A2L carries, because those are usually the old spellings of the same objects."
  - `plugin-invalid` (1090-1091): append "and, in the language server only, a hook that raises while a file is checked ([section 3.11](#311-plugins))".
  - `enum-conflict` (1128-1130): append "in the textual order of the file, for the list form and the mapping form alike".

- [ ] **Step 4: 4.1 Comparing two deliveries.** Edits:
  - After "The baseline is analysed in its own right, and only its error findings are carried into the report, each prefixed with `in the baseline:`" (1222-1228) add: "and without `--strict`, its warnings being its own. A candidate given as a description is analysed too, and all of its findings are reported at their own severities. The verdict is that the candidate can replace the baseline exactly when no finding of the run is reported as an error - the candidate's own, the baseline's carried ones and the comparison's alike - and the exit code follows the verdict ([section 7](#7-tool-interface)). When a side cannot be read, or the baseline carries an error and the candidate is a description, no verdict is printed and the exit code is 1."
  - `--renames` (1230-1236): replace the sentence describing the file's content with: "`--renames <file>` writes a JSON list of objects `{"id", "from", "to"}`, sorted by `to`, `[]` when nothing was renamed; a member of a structured object is listed once per member, its `id` being the instance's `id` followed by `.` and the member path. The file is written whether or not the comparison found errors, and not at all when a side could not be read. Both `--renames` and `--plugin` belong to `ddd compare`; `ddd check --baseline` runs the candidate's own plugins and writes no rename list."
  - `renamed-object` (1308-1310): replace "Renaming the instance therefore keeps every member paired and is one `renamed-object`" with "Renaming the instance therefore keeps every member paired, each reported as a `renamed-object` under its path, which is what a migration tool needs".
  - The lost-identity note (1296-1298): replace "every compared field" with "interface, storage and references".
  - `reused-name` (1253): replace "is reported above the removal and addition it accompanies" with "is reported above the removal it accompanies; findings at one location keep the order they were reported in".
  - `missing-plugin` (1288-1294): append "Each side given as a description runs the plugins it names for its own analysis; the comparison hooks are the candidate's (or `--plugin`'s for a dumped candidate), and `missing-plugin` is reported for a plugin either side records that the comparison did not run."
  - The format rule (1264-1268): append "A dictionary of an older format is read with the defaults of that format: a format-3 baseline states no `dimensions`, so shapes compare by value alone; one before format 6 records no `plugins`, so `missing-plugin` cannot fire for it. Adopting a scalar type is not a change of interface, because the dictionary records the datatype a type resolves to ([section 3.3.1.1](#3311-interface))."

- [ ] **Step 5: Test and commit**

```bash
python -m pytest tests/test_documentation.py --no-cov -q
git add SPEC.md
git commit -m "state the plugin grammar, the verdict, the renames file and the rules section 4 applies" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push
```

---

### Task 4: Sections 5 and 6, and a new section 5.3

**Files:** Modify `SPEC.md` 5.1 (1323-1419), 5.2 (1420-1504), 6 (1505-1521); add `### 5.3 Data dictionary` after 5.2 and its line in the table of contents (`    - [5.3 Data dictionary](#53-data-dictionary)` under 5.2).

- [ ] **Step 1: 5.1 C code.** After the sentence on the sort order of the generated objects, add: "A component's own header keeps the author's declaration order. An object no component owns - a declaration whose producer's `missing-producer` was relaxed - is grouped under `<unresolved>` in the definition file." Where external headers are said to be included "in a fixed order" (1370), write "in the sorted order of their spellings, so the angle-bracket forms come first". Where enums are described, add "a variable under an enum conversion is declared with its base datatype; the `typedef enum` is for the enumerators".

- [ ] **Step 2: 5.2 A2L.** Edits:
  - First paragraph: add "The file is written as `<project name>.a2l` into the output directory (`-o`), beside the C sources; a component generated on its own names the file after the component."
  - Records order: after the sentence on records sorted by object name (1443), add: "Inside the `MODULE` the record kinds come in a fixed order: `MOD_COMMON`, `MOD_PAR`, the `RECORD_LAYOUT`s, the `COMPU_VTAB`s, the `COMPU_METHOD`s, the `MEASUREMENT`s, the `AXIS_PTS`s, the `CHARACTERISTIC`s and the `GROUP`s; within a kind the plain objects by name, then the leaves of structured objects by access path."
  - `COMPU_METHOD` (1429-1430): replace "shared between objects with the same conversion and unit" with "shared between objects with the same conversion, unit and default display format (an integer and a float object scaled alike get one method each, because the method states the format)"; after the naming rule (1459-1462) add: "The `_2`, `_3` suffix is added when the generated name collides - two linear conversions in one unit, or one conversion used by an integer and by a float object - and the unsuffixed name goes to the method of the object first in name order."
  - Display format (1468-1471): replace the rule with "The display format defaults to `%8.0` for an integer or `boolean` datatype under an identity or under a linear conversion whose `factor` and `offset` are whole numbers, and to `%8.3` otherwise. The default is stated on the `COMPU_METHOD`, so an object with no method (`NO_COMPU_METHOD`: an identity without a unit) carries no format unless its own `format` states one, which is written on the record."
  - Export closure (1476-1479): replace "a pulled in axis pulls the measurement indexing it" with "an axis in the file, exported in its own right or pulled in, pulls the measurement indexing it".
  - `GROUP` (1436-1438): replace the sentence with "one `GROUP` per component that contributes at least one exported object, referencing every declaration of the component, in any scope, in declaration order, then the leaves of the structured objects it declares".
  - `AXIS_PTS`: where the layouts are described (`RECORD_LAYOUT`, 1450 area), add "the axis layout is `INDEX_INCR DIRECT` and the value layouts `ROW_DIR DIRECT`; an `AXIS_PTS` states `MaxDiff 0`".

- [ ] **Step 3: New section 5.3 Data dictionary.** Insert after the end of 5.2 (before `## 6 Address information`):

```
### 5.3 Data dictionary

`ddd dump` publishes the resolved project as one JSON document, the contract between the
checking front end and every backend, DDD's own and a project's. Its `format` is `7`; a
reader **shall** refuse a higher number and **may** read a lower one with the defaults of
that format ([section 4.1](#41-comparing-two-deliveries)). Its schema is published by
`ddd schema dictionary`. The top level carries `format`, `name`, `description`, `source`
(the file name of the root description), `components`, `objects`, `enums`, `constants`,
`rasters`, `types`, `instances`, `leaves`, `plugins` and `extensions`.

A component records `name`, `description`, `source` and its `declarations`, each a `name`, a
`scope` and a `condition`; only declarations whose object resolved are listed. An object
records what its producing declaration states, resolved: `name`, `id`, `extensions`, `kind`,
`datatype`, `description`, `unit`, `conversion` with its `kind` spelled out, `limits`
(`min`, `max`, the stated ones or the ones the datatype and conversion imply), `shape` (the
numbers) and `dimensions` (the spelling, constant names kept), `init`, `section`, `raster`
(the declaration's own, else its component's default), `volatile`, `condition` (the
producer's), `references`, `owner`, `consumers`, `local` and `a2l` with `export` resolved
to a boolean. An instance records `name`, `id`, `extensions`, `type`, `kind`, `description`,
`shape`, `dimensions`, `volatile`, `section`, `raster`, `condition`, `owner`, `consumers`,
`local` and `a2l`; a leaf records `path`, `instance`, `instance_id`, `kind`, `datatype`,
`description`, `unit`, `conversion`, `limits`, `shape`, `dimensions`, `bits`, `volatile`,
`section`, `raster`, `condition`, `owner`, `consumers`, `local` and `a2l`, the instance's
and the member's `export` folded into one. `types` lists the structures in dependency
order with their members; `enums` the enum conversions, one per name, the best documented
variant; `constants` and `rasters` the declared entries. Nothing in the document depends on
the machine that wrote it.
```

- [ ] **Step 4: Section 6 Address information.** Replace "a JSON number" (1511-1512) with "a JSON integer"; after "**must** fit" add "in 32 bits; a map that is not a JSON object of integers, or an address outside `0 .. 0xFFFFFFFF`, is a usage error and nothing is written. A map with entries that leaves an object of the A2L uncovered is `address-missing` ([section 4](#4-consistency-checks)): a warning by default, an error under `--strict` that writes nothing."

- [ ] **Step 5: Test and commit**

```bash
python -m pytest tests/test_documentation.py --no-cov -q
git add SPEC.md
git commit -m "describe the dictionary, the a2l file and record order, and the compu method key" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push
```

---

### Task 5: Sections 7, 7.1 and 7.2

**Files:** Modify `SPEC.md` 7 (1522-1601), 7.1 (1602-1668), 7.2 (1669-1729).

- [ ] **Step 1: Section 7, `--standalone` and the listings.** Replace the clause at 1570-1573 ("a component alone is checked with every check, the whole project ones included, because holding them back is the editor's leniency (section 7.2), not the command line's") with: "a component alone is checked with every check unless `--standalone` is given, which holds back the ten checks that need every component ([section 4](#4-consistency-checks)), the same set the editor holds back ([section 7.2](#72-editor-integration)); an explicit `-W` on the same run still wins. Given a project root, `--standalone` holds the same checks back project-wide, which is rarely wanted." Then, at the commands: `ddd list` "rows sorted by variable name"; `ddd sources` "sorted absolute POSIX paths, the modules of the plugins the project names among them"; `ddd artefacts` "`c`, `a2l`, then the plugins with a backend in the order the project names them; a plugin without a backend is named in a note; given neither a project nor `--plugin` it lists the two built-in artefacts"; `ddd checks` "in the order of the registry, then each `--plugin`'s checks in their declared order". Exit codes (1586-1590): add "`ddd sources` and `ddd artefacts` exit 0 whatever the findings, because what a project is built out of does not depend on whether it is consistent; they exit 1 only when the root cannot be read." `ok:` line (1582-1583): write "a `ddd check` with no finding at all closes with an `ok:` line". `ddd dump`: add "with `--format json` the findings document goes to stderr, so stdout carries the dictionary alone in both formats". `ddd generate <name>` for a plugin (1530-1533): add "takes the output directory, `--dry-run`, `--force` and the severity and format options, and none of the built-in artefacts' own". `ddd id --assign`: add "fills an explicit `\"id\": null` in place, leaves a file that is not a component alone, and reports a file it cannot parse while stamping the others, exiting 1". Add a sentence on the pre-commit hook: "The package publishes a pre-commit hook, `ddd-id`, that runs `ddd id --assign` on the staged description files."

- [ ] **Step 2: 7.1.** Edits:
  - `ddd_add_component` (1604-1606): "registers descriptions, component and vocabulary files alike" and add "it needs CMake 3.30; a registered file not named `*.ddd.json` is a configure error. For each registered component file it defines an on-demand target `<target>.ddd` that runs `ddd check <file> --standalone` under the default severity policy; vocabulary files get none."
  - The libraries (1610-1613): name them: "an interface library `<image>_ddd_headers`, carrying the output directory as an include directory and, in the collected mode, the interface include directories, compile definitions and compile options of every registered component; and an object library `<image>_ddd_globals` compiling the definition files, which links the first and is linked into the image".
  - After `NAME` (1616): "sanitised by replacing every character outside `[A-Za-z0-9_]` with `_` and prefixing a leading digit with `N`".
  - Include order (1623-1625): "the order CMake evaluates the transitive `DDD_JSON` property in - a depth-first walk of `target_link_libraries` in declaration order - first occurrence kept".
  - The map (1629-1637): after "seeded empty at configure time" add "and an empty map raises no `address-missing` ([section 4](#4-consistency-checks)), so the first build passes under `STRICT`; with `NO_A2L` the map is neither seeded nor a dependency". Add "`OUTPUT_DIRECTORY` (`-o`)" beside `TEMPLATE_DIRECTORY (required, --template-dir)` (1638).
  - Add, near `SCHEMA_DIRECTORY`: "beside `PROJECT` it closes the schemas over the plugins that one file names, not over a sub-project's".
  - Add: "`ddd_generate` publishes the A2L path as the target property `DDD_A2L`; multi-config generators are refused at configure time; the tool is found by `find_program` into the cache variable `DDD_EXECUTABLE`, and the executable itself is a dependency of the generation."

- [ ] **Step 3: 7.2.** After "takes the build directories as repeatable `-b` arguments" (1723-1725) add "relative to the server's working directory". Where the containing project search is described ("the nearest directory that include it") add "the candidates being the `*.ddd.json` files of that directory in sorted order, the opened file excluded, and the walk stopping at the workspace folder". Replace "a corrupted frame header, after which no message boundary can be trusted, ends the session with a message rather than a failure trace" with "a frame header whose `Content-Length` is not a number, after which no message boundary can be trusted, ends the session with a message rather than a failure trace; a header block without a length is read as the end of the conversation". In the last paragraph (the extension "shall do no more than launch the server"), add "and offer to restart it" after "point it at the build directories" (keep the trust sentence if branch `fix/lsp-windows-uris-and-buffers` has landed it).

- [ ] **Step 4: CHANGELOG.** Under `## Unreleased`, add a bullet:

```
* **The specification catches up with the tool.**  `SPEC.md` now states what 0.8.0 and this
  release do: `ddd check --standalone` and the per-component `<target>.ddd` target, the empty
  address map that raises no `address-missing`, the `COMPU_METHOD` sharing key and the display
  format rule, the closure over an exported axis's input, the A2L file name and record order,
  the `<image>_ddd_headers` and `<image>_ddd_globals` targets and `DDD_A2L`, the plugin name
  grammar and its reserved names, the shape of the `--renames` file, the verdict of a
  comparison, the orders of the listings, and a section describing the data dictionary.  It
  defines "instance" and "leaf" and uses "storage" for one thing.  No behaviour changed.
```

- [ ] **Step 5: Full verification and final commit**

Run `python -m pytest` (expect only the 12 known environmental failures) and `<venv>/Scripts/python.exe -m ruff format --check .`.

```bash
git add SPEC.md CHANGELOG.md
git commit -m "state the command line, the cmake module and the server as they are" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push
```

Then write, in the final report, the list of sentences that encode a behaviour the maintainer may want to revisit: a `typename` compared as resolved (3.3.1.1 and 4.1); `--standalone` accepted on a project root (7); `ddd sources` reporting nothing in text mode is *not* stated (a later change makes it report); the header block without a length ending the conversation silently (7.2).
