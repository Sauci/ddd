# Findings you can act on

`ddd gui` tells a reader what is wrong with their project and leaves them to work out where to go.
A component's page lists the findings filed on its file, the variable panel lists the ones filed on
its declarations, and the project's Table tab counts them per file. All of it is text. A reader who
reads "'ValueA' is declared differently by component 'Controller' (conversion: linear(factor=0.25)
!= linear(factor=0.5))" has to know, by themselves, that the answer is the variable's panel and its
conversion row.

This gives every finding a destination, lists them all in one place, and offers the one fix the GUI
has nowhere to put. It is part 4 of the GUI's growth by field, after units (#49), the project's
units (#51) and the other keys (#52).

## 1 What this adds

1. **A Findings tab**, beside Graph, Table and Units: every finding in the project, worst first,
   grouped by the file it is filed on, each one a row a reader can press.
2. **Every finding leads somewhere.** Pressing it opens what it names - the variable's panel on its
   component's page, that unit's panel on the Units tab, or the component's page - and a finding
   whose file did not load says so rather than leading nowhere.
3. **The lists that already exist become links**: the component page's and the variable panel's.
4. **One fix, offered where it has no home**: `missing-id`, "Give 'ValueA' an id", previewed and
   applied like every other edit the GUI makes.
5. **One rule for what a value is.** `ddd.lsp.edits.settle` compares the json text of a key, where
   the GUI compares what a value means; making `settle` use the same rule serves both clients and
   deletes the layer part 3 added to work around it.
6. Two rough edges with it: a retry straight after a stale refusal, and a sort that orders
   differently on Windows and Linux.

## 2 Decisions already taken

- **A finding takes a reader to its fix rather than growing one of its own.** Parts 1 to 3 already
  settle a key from the variable's panel and a unit from the Units tab; a second way to do either,
  under the finding, would be a second set of rules to keep in step. What is missing is the route.
- **Every finding is a route, not only the three with fixes.** Of the roughly fifty checks the tool
  reports, three carry a fix. The other forty-seven still name a place, and taking a reader there is
  the whole of what a page can do for them.
- **The server says where a finding leads.** Which check means what, and which declaration a pointer
  names, are the loader's knowledge; they stay in Python under the 100 % gate, and the page draws
  the link it is given.
- **A variable's route names no key.** Part 3's panel already opens on the first row that disagrees,
  so a `definition-mismatch` on `ValueA` opens its panel with the disagreeing row selected without
  the route having to say which.
- **Fixes are offered in one place**, the Findings tab's panel. A finding listed elsewhere is a
  link.
- **No filter on the tab.** The rows are worst first and grouped by file, which is the order a
  reader works through them, and the Table tab already carries the per-file counts.

## 3 Out of scope

- A raw-text view of a file that does not parse. A `json-syntax` or `schema` finding names a file
  the GUI cannot open, and says so; fixing it stays an editor's job for now.
- New fixes for checks that have none.
- Undo, still.
- Changing what any check reports, or its severity.

## 4 The server

### 4.1 Where a finding leads

Every `Finding` in `GET /api/state` gains a `route`, worked out from the finding's own file and
pointer through the documents the revision has already read:

| Route | When | What the page opens |
| --- | --- | --- |
| `{"kind": "variable", "name": "ValueA"}` | the pointer lies inside a declaration of a component file | that component's page, with the variable's panel open |
| `{"kind": "unit", "unit": "degC"}` | the finding is `unknown-unit`, filed where the unit is stated | the Units tab, on that unit |
| `{"kind": "component", "file": "…"}` | the file is a component and the pointer names no declaration in it | that component's page |
| `null` | there is nothing to open | nothing; the row says why |

Three things leave a finding without a route, and the row says which: its file did not load, so the
pointer describes a document nobody parsed; its file is not a component and the GUI has no page for
one - a types, units, constants, sections or rasters file, which milestone 6 is about; or the
finding is about the project rather than a place in a file. A `unit` route is the exception that
crosses those lines: part 2's unit panel lists every place a unit is stated, a scalar type's and a
structure member's included, so an `unknown-unit` filed on a types file still leads somewhere.

### 4.2 The fix a finding carries

`GET /api/fix?file=&pointer=&check=` answers the fixes that finding carries, each with the preview
`GET /api/settle` and `GET /api/unit-plan` already answer - the operations, the fingerprints and the
lines each file would change. A list rather than one fix, so that the second one needs no new
endpoint.

Today the list holds one: `missing-id`, for a producing declaration without an identity. It is
planned as `ddd.editing` operations on json pointers rather than borrowed from the language server's
own quick fix, which writes text edits with ranges; `ddd.identity` already owns what both need -
`new_id` and the rule that only a producing declaration is stamped.

**An id is generated once.** `ddd.identity.insertions` says it plainly: asking twice proposes two
different ids, so a caller applies the answer it was given. The page therefore posts the preview's
own edit, exactly as the panels do, and a preview refetched because the revision moved on carries a
new id - which is nothing to a reader, since neither was written.

### 4.3 One rule for what a value is

`ddd.lsp.edits.settle` compares the json text of a key, so a declaration that already means the
chosen value but spells it differently counts as a change. Part 3 found what that costs a reader -
an Apply that never goes away - and worked around it in the GUI with `ddd.variables.narrowed`.

`settle` now compares with `ddd.value_identity.same_value`, and `narrowed` goes. Both clients gain
it: the language server stops offering to rewrite a line to a value it already means, which is the
point of the change, and the tests that pinned the old behaviour change with it.

Two rough edges are fixed beside it, both found while part 3 ran:

- A retry straight after a stale refusal can be refused again, because the plan it refetched still
  carries the fingerprints of the analysis that was current when the file changed. The page waits
  instead: the refusal is held, and the Apply under it withheld, until a revision later than the
  one it was refused at arrives (`gui/src/lib/refusals.ts`). The watcher answers within a second,
  so the retry goes through, and no endpoint is made to re-read the files the next analysis is
  about to read anyway. Its one weakness, plainly: only a later revision takes the sentence down,
  so a watcher that has stopped publishing leaves it standing.
- `ddd.variables.preview` sorts `Path` objects, which order differently on Windows and Linux; it
  sorts by the posix spelling, as `ddd.lsp.units` already does.

## 5 The screens

### 5.1 The Findings tab

The Units tab's shape, which the reader already knows: a table, and a panel beside it.

| Column | Shows |
| --- | --- |
| Check | the check's identifier, as a chip tinted by its severity |
| Message | what the finding says |
| File | the file it is filed on |

Worst first - errors, then warnings, then information - and within a severity grouped by file, in
the order the analysis filed them. The meta line counts what is there: "14 findings · 3 errors, 11
warnings". A project with nothing to report says so.

### 5.2 Pressing a finding

Selecting a row opens its panel: the check, the message in full, its notes - the other side of a
disagreement, with the file it points at - and

- **a button that goes where it leads**, named for the thing rather than the screen: "Open ValueA",
  "Open degC", "Open SensorHub";
- **the fix**, where the finding carries one: its title, part 1's consequence line, Show changes,
  and Apply to N files;
- **why there is nowhere to go**, where there is not: "sensor_hub.ddd.json did not load".

A finding listed on a component's page or in a variable's panel is a link that goes the same place,
except where that place is the one the reader is already looking at: a finding in `ValueA`'s panel
that leads to `ValueA` is text, as it is today. It offers no fix there either: one place offers
fixes, and it is the tab.

### 5.3 What the reader sees when something goes wrong

- **The finding is gone** by the time it is pressed - the analysis moved on, or somebody else fixed
  it: the panel closes and the tab says why, as part 2's unit panel does.
- **A file changed on disk**: refused as stale, and the retry now goes through.
- **The fix is refused** by the edit engine: its own sentence, under the title.
- **The file did not load**: no link, and the row says so.
- **The server stopped**: milestone 1's banner, and no Apply.

## 6 Stories and screenshot tests

One story per state, photographed in Playwright's Linux image as parts 1 to 3 are: the tab with
findings of each severity; a finding that leads to a variable, to a unit and to a component; one
that leads nowhere; the `missing-id` fix with its changes shown; a refusal; and a project with
nothing to report.

## 7 Testing

- **Python**, under the 100 % line and branch gate, ruff and strict mypy:
  - a route for every shape of finding over copies of `examples/demo` and `examples/vocabulary`: a
    declaration's, a unit's, a file's, and the ones that lead nowhere, including a file that did not
    load;
  - `GET /api/fix` for `missing-id`: the preview writes nothing, its edit applied stamps exactly the
    declaration it named, and a second ask proposes a different id;
  - every refusal, and every `400`, `404` and `409`;
  - **the language server's own tests**, which change: a quick fix that used to offer to rewrite a
    value differing only in spelling is no longer offered, and that is the change rather than a
    regression to work around. `ddd.variables.narrowed` and its tests go.
- **The page's logic** under Vitest's 100 % gate: the tab's order, its counts, and the link each
  route makes.
- **End to end**, in Chromium on Windows and Linux: press a `definition-mismatch` and land on the
  variable's panel with the row selected; press an `unknown-unit` and land on its unit; fix a
  missing id and read the file back; meet a finding whose file did not load; and the
  Content-Security-Policy journey visiting the new tab.
- **The gate** as parts 1 to 3 ran it, the real application included, with screenshots for the pull
  request.

## 8 Documentation and where it lands

- The changelog and the command page say that the findings are a tab of their own and lead to what
  they name. The developer page describes the route and the fix endpoint. `docs/editor_integration.rst`
  gains a line: a reconcile quick fix is no longer offered for a value that already means the same.
- On `feature/gui-findings`, from master after #52.

## 9 Evidence

- `ddd checks`: roughly fifty checks; `missing-id`, `unknown-unit` and `definition-mismatch` are the
  three that carry a fix.
- `src/ddd/lsp/edits.py`: `actions`, and the reconcile and identity actions it gathers - each built
  as a text edit with a range, which is why the GUI plans its own operations; `settle`, whose
  comparison section 4.3 changes.
- `src/ddd/identity.py`: `new_id`, `insertions` and `_unstamped` - a fresh id per call, and only a
  producing declaration stamped.
- `src/ddd/analysis.py`: `definition-mismatch` filed at `other.location("definition")`, so a
  finding's pointer names the declaration rather than the key it is about.
- `src/ddd/value_identity.py` and `ddd.variables.narrowed`: part 3's rule, and the layer that goes.
- `src/ddd/gui/contract.py`: `Finding` and `State.findings`, which every screen already reads.
- `gui/src/screens/UnitsPage.tsx` and `UnitPanel.tsx`: the table-and-panel the Findings tab follows.
- `gui/src/lib/route.ts`: the page's addresses, which gain the tab and its selected finding.
