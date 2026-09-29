# The project's files in the GUI

Part 16 of the browser interface, and the last of milestone 6: *"Shared project files: types and
structures, units, sections, constants, rasters, the project's includes, new files."* Parts 12 to 15
gave every vocabulary a tab. This part gives the list they all hang off — the project's `includes` —
a tab of its own, and lets a reader create a file, add one, and remove one.

It depends on the change on `feature/empty-vocabulary-files`, which lands first: a vocabulary file may
declare nothing and is reported `empty-vocabulary` at INFO; an empty units file still opts the project
into unit checking; and adoption fills an empty units file. Without it, this part could create only
components, and would route the other five kinds elsewhere.

## 1 What exists, and this part consumes

- **The page already receives every file.** `contract.State.files` carries one `SourceFile` per file
  the analysis read: its path, its kind, its name, whether it loaded, its fingerprint and its finding
  counts. Most of what the tab shows is on the wire today.
- **The loader already knows which entry pulled each file in.** `_Loader` loads every included file
  with an `origin` of `Location(project, "project.includes[i]")`. It does not record that where the
  session can read it. That record is the one piece of data this part adds.
- **An `includes` entry is a pattern or a path, decided by the disk.** Its model's own docstring:
  *"An entry that names an existing file is that file whatever characters it holds … only an entry
  naming no file is expanded as a pattern."* Shell wildcards, `**` included. So a file can be part of
  the project through an entry that does not name it.
- **Creation is already confined.** `session._confined` lets an edit create a file only beside the
  project description, and only when the same edit adds it to `includes`. `shared_plans._created` and
  `lsp.units.adopt_units` are the two plans that create files today, and both have that shape.
- **What the page may reach is already confined.** `session._served` refuses any path outside the
  directories the session serves, for every route that takes a path and every edit. Its docstring
  names this part's risk in advance: *"an edit may add anything to the project's own `includes`, so a
  reader of the page can make a file anywhere part of the project and then ask for it."*
- **Nothing can delete a file.** The edit engine has no forward delete; its one `unlink` is
  `editing._put_back`, undo taking back a file an edit created.
- **Two findings are the same finding** by `lsp.diagnostics._identity`: check, severity, location and
  message.

## 2 What the Files tab shows

A tab, **Files**, beside the others. One row per entry of the project's `includes`, in the order the
project lists them.

- **An entry naming a file** shows the file: its kind, whether it loaded, its finding count.
- **A pattern** shows the pattern as written, and beneath it every file it matched, each with its own
  kind, state and count. This is what lets the tab say why a file cannot be removed on its own.
- **An entry naming nothing** — a missing file, a pattern matching no file — shows as such, carrying
  the `include-empty` finding the loader already files there.
- **A sub-project** is a row of kind `project`. Its own `includes` are neither expanded nor editable
  here; managing them is opening it as a project.

**Two findings lead here, and lead nowhere today.** `include-empty`, filed at `project.includes[i]`
for a pattern or path matching no file, and `empty-vocabulary`, filed at a vocabulary file's own list:
`finding_routes.route_of` answers `None` for both, measured. Each is about an entry or a whole file
rather than anything a panel shows, and this tab is the one screen that shows both. `route_of` gains
a `file` route naming the entry or the file, and `contract.FindingRoute.kind`'s `Literal` gains the
word with it — which part 15's `test_every_kind_a_route_answers_is_one_the_contract_publishes`
exists to catch if it does not.

One endpoint, `GET /api/files`, answers the entries in order with what each resolved to. It joins
the loader's per-entry record (§1) to `State.files` on the resolved path rather than repeating what
`SourceFile` already carries.

## 3 The three actions

### New file

The reader picks a kind — component, types, units, constants, sections, rasters — and names the file.
One edit creates it beside the project description and adds it to `includes`: the shape `_confined`
allows, and the only one.

- A vocabulary file is created declaring nothing, which the dependency makes legal.
- A component takes a name as well, and starts with an empty `interface`. It is reported
  `empty-component` at INFO, which is that check's purpose.
- **A project's first units file adopts the units the project already states**, in the same edit. An
  empty units file opts the project in, so creating one bare would turn every stated unit into an
  `unknown-unit` at once; the tab must never make a clean project fail in one click. A second units
  file is created empty — the project is already opted in, so it changes nothing.
- The file is always `<name>.ddd.json`: every one of the eighteen `includes` entries across the
  nine project files committed to this repository ends that way.

### Add an existing file

A path relative to the project description. Always literal: the tab never writes a pattern. Its
preview lists any error the file would bring (§4), but **informs rather than refuses**, because adding
a half-finished file is often exactly what a reader means.

### Remove

Drops the entry from `includes`. The file stays on disk. A pattern entry is removed whole. **Judged by
the analysis** (§4): refused where the project without the entry has errors it does not have now.

Add and remove are deliberately asymmetric. Removal is where the costly mistake lives — dropping a
file believed unused and orphaning everything that named it — and it matches the vocabulary tabs,
which refuse removing an entry anything names. And the two halves of milestone 6 compose: a reader
empties a vocabulary file in its own tab, then removes it here.

## 4 How the analysis judges

**The loader gains one override: the root project's `includes`, for one analysis.** Every file is
still read from disk; only the root's list differs; sub-projects keep their own. This is the only
change this part makes to `loading.py`.

A **removal preview** analyses the project with that entry gone and compares its errors with the
current revision's, which the session already holds. Findings match by `_identity` (§1). Only errors
count, after the project's severity policy — the line `ddd check` draws between passing and failing.

**Removing an entry shifts every later index** of the root's `includes`, so a finding at
`project.includes[4]` reappears at `[3]` and would read as new. A finding on the root's own `includes`
is matched by the entry it names, not by its position.

The refusal names what would break: the first error it would leave, and how many there are — *"removing constants.ddd.json
would leave 3 errors, the first in pump.ddd.json: 'TREND_SAMPLES' is not a constant any file
declares."* An **add preview** uses the same override with the entry appended. **New file** needs no
analysis: an empty file breaks nothing, and the one kind that could — units — adopts in the same edit.

**Cost, measured.** One load-and-analyse run, in process, median of seven: 1.7 ms on `examples/demo`
(six files, four components, 22 objects) and 0.5 ms on `examples/vocabulary`. A preview runs once per
click, never per keystroke. The cost grows with the project; no project larger than the examples was
measured, and the plan should measure one before assuming a larger one stays this cheap.

## 5 What is refused, and what is reported

**New file** is refused where a file of that name already exists, where the name is not a usable file
name ending `.ddd.json`, or where a component's name is not a c identifier or is already taken.

**Add** is refused where the path:
- lies outside what the session serves — **decided by `_served` itself**, so adding and reading can
  never disagree about what is reachable;
- names no file (that is New file);
- is already part of the project — named by an entry, or matched by a pattern, which the refusal names;
- is the project description itself;
- holds nothing the loader recognises as a kind.

**Remove** is refused where the analysis finds new errors (§4), and where the file came in through a
pattern rather than an entry of its own — the refusal names the pattern, which can be removed whole.

**What can reach the loader from a request: nothing arbitrary.** The override is never read from a
request. The server computes it — the current `includes` less one existing entry, or plus one path
that has passed every refusal above. And because the tab never writes a pattern, it cannot write one
that reaches outside the root with `../**`.

## 6 Out of scope

- **Creating a file in a subdirectory.** `_confined` allows beside the project description only.
  Relaxing it is a security change, not one to make inside a feature.
- **Creating a sub-project**, and editing a sub-project's own `includes`.
- **Writing a pattern.** The tab adds literal paths only.
- **Reordering `includes`.** Order does mean something: it decides which of two files declaring one
  name is the second, and so carries the `duplicate-*` finding, and which file of a vocabulary
  `add_entry` appends to. Reordering is a real capability with consequences a reader should see
  previewed, which is its own piece of work rather than a line in this one.
- **Deleting a file from disk.** Nothing in the edit engine can, and removal from the project is what
  a reader of this page needs.
- **Go to definition** for a section or a raster, which parts 14 and 15 left open.

## 7 Testing

Parts 13 to 15's gates exactly: Python at 100 % line and branch with `ruff` and bare `mypy` clean;
Vitest at 100 % over `src/api`, `src/lib` and `src/state`; the screenshot references; the journeys;
the docs under `-W`.

- **The judge** is tested at each case: a removal that orphans uses (refused, naming them), one that
  does not (allowed), a file pulled in by a pattern (refused, naming the pattern), a pattern removed
  whole, and the shifted index of §4.
- **Both findings** of §2 route to their row: `include-empty` to its entry, `empty-vocabulary` to its file.
- **The override** is tested for reaching the root only: a sub-project's `includes` unchanged by it.
- **No decision lives in a `.tsx` file.** The journeys do drive the compiled page, so that scrutiny is
  not zero, but it is narrow; every judgement the tab makes lives in `gui/src/lib`.
- **Ablate what a coverage gate cannot see**, in a scratch worktree with pytest run from inside it.
  A survival is re-run under several `PYTHONHASHSEED`s before it is believed.
- **A journey** creates a component, adds an existing file, is refused removing a file whose
  declarations are used, and removes one whose are not.

## 8 Documentation

The `ddd gui` row of `docs/command_line_interface.rst` gains the Files tab: what it lists, the three
actions, and every refusal in §5 — a capability with its refusals unstated is half a row.

## 9 Decisions, and what each costs if wrong

| Decision | Why | Cost if wrong |
| --- | --- | --- |
| The analysis judges removal | It asks the same authority `ddd check` answers, with no per-kind rule to restate or forget | One narrow loader override; if it proves wrong, per-kind rules replace it behind the same refusal |
| Add informs, remove refuses | Removal is where the costly, silent mistake lives | A reader adds a broken file and sees its errors after applying; undo is one click |
| A first units file adopts | An empty one would fail a clean project in one click | A reader who wanted an empty units file removes the adopted units, now legal |
| Beside the project description only | `_confined` already draws that line; widening it is a security change | A reader who wants a subdirectory creates the file by hand, then adds it |
| Sub-projects listed, not managed | Their `includes` belong to opening them | Nesting stays a text-editor job until a part takes it on |
