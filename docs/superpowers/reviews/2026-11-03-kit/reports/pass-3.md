## Pass 3: the split between the UI and the backend, and inside the front end

`SCRATCH` is `C:/Users/lmbsog0/AppData/Local/Temp/claude/C--git-ac11-ddd/8681cf0d-d41d-4120-88ca-b1b2c3615be8/scratchpad`.
Every script and transcript named below lies under `SCRATCH/pass-3/`. Line numbers are on the review tree.

**The answer, plainly.** The line between the page and the server is mostly in the right place, and better kept than the size of
the page suggests: the server composes every plan and every diff, the page matches no refusal text, the shapes on the wire are
generated, and the views are pictures of their props. It leaks in three places, and each leak has already produced wrong behaviour on
a real `ddd gui`: **numbers** (the page parses and converts them as doubles, and the wire is `float`, so a 64 bit value is shown and
written wrong without a word), **one missing read model** (the component's table reads the raw file in a `.tsx`, and is wrong about a
type's unit and about which declarations have a grid), and **one missing judge** (`settle` and `type-plan` take any value, by design,
so the page is the only guard of what a file can hold, and its guard has a hole). Inside the page the direction of the imports is
sound, and the `*View` half of the split holds. The `screens` half does not: the rule "no decision in a `.tsx`" is restated in eight
plans and not kept, and three panels are one panel copied.

### Scope covered

**Read in full, with line numbers:** `gui/src/api/*` (client, types, token, signIn), `gui/src/app/*`, `gui/src/state/*`, `gui/src/main.tsx`,
every file of `gui/src/lib/` but the tails of `layout.ts` (80-293) and `layoutAnswers.ts` (60-137); every file of `gui/src/screens/`;
of `gui/src/components/`: `VariablePanelView`, `VariableKeysTable`, `KeyChooser`, `FileActionsView`, `FilesTableView`, `ValuesGridView`,
`ValuesPlotView`, `DeclarePanelView`, `DimensionsField`, `ConstantPanelView`, `TypePanelView`, `SharedAddView`, `SharedTableView`,
`FindingPanelView`, `CompareView`; `ui/Table.tsx`; `gui/scripts/*`, `gui/package.json`, `vite.config.ts`, `tsconfig.json`, `biome.json`;
`src/ddd/gui/contract.py`, `queries.py`, `routes.py`, and as the twins of the page's rules `object_values.py`, `variable_keys.py`,
`finding_routes.py`, `models/conversion.py`, `models/objects.py`, `models/component.py`, `models/common.py` 120-224, `lsp/units.py` 80-160 and
221-460, `value_identity.py` 40-80, `gui/api.py` 215-325, 1219-1247, 1395-1461, 2386-2420. `tests/test_gui_contract.py`. The "Left open" of every GUI plan.

**Read in part:** `UnitPanelView`, `SectionPanelView`, `RasterPanelView` (first half, the rest by search); `UnitsTableView`, `TypesTableView`,
`FindingsTableView`, `CompareTableView`, `UndoStripView`, `AdoptBannerView`, `Changes`, `UnitPicker`, `FlowEdge`, `ModuleNode`, the rest of `ui/` (searched
for domain words, none found). **Not covered:** `styles/`, `stories/`, `.ladle/`, the journeys beyond searching them, `gui/session.py` and `server.py` (passes 2 and 12).

**Ran:** the import graph (`tsgraph.py` -> `graph.txt`); sizes, prose, decisions and likeness of the panels (`measure_fe.py` -> `measure_fe.txt`); the contract's surface
(`probe_contract.txt`); a dozen mutations through `tsc` and vitest on a scratch copy (`mutate.py` -> `mutate.txt`; baseline tsc 0 errors, vitest 959 of 959);
the page's own `lib` functions, run unbuilt under node, against a real `ddd gui` over HTTP (`probe_numbers`, `probe_tables`, `probe_u64`, `probe_declare`, `probe_rules`, `probe_rest`,
`probe_guard`, `probe_limits`, `probe_misc`, `probe_removal`, `probe_offered`, each `.py` and `.txt`), and the real page in Edge over a real `ddd gui` (`browser/*.mjs` ->
`browser_u64.txt`, `browser_limits.txt`, `browser_paste.txt`). I did not run pytest or the journeys. One side effect: the mutation run went through a junction to `gui/node_modules` and rewrote vitest's
cache there (`.vite/vitest/.../results.json`, git-ignored); the junction is gone and `git status` is clean at `35aca14a`.

### Strengths

- **The direction of the imports is sound, measured.** 116 production files. No cycle of value imports between files, and one of types (`lib/layout.ts`, `lib/layoutAnswers.ts`). `lib` imports nothing from `app`, `screens`,
  `components` or `ui`; `components` nothing from `screens`, `app` or `state`, and from `api` only types (22 of 22). Two cycles between folders, none between files of them, both cheap (M2).
- **The views are pictures of their props.** Across 29 files of `components/`: no `useState`, no `useQuery`, no `useMutation`; one `useEffect` (a scroll, in `FindingsTableView`) and two `useRef` (that box; a focus, in `FileActionsView`). All 37 queries and 15 mutations are in `screens/` and `app/`.
- **Shapes on the wire are one definition.** 133 generated names, from the models the server validates and answers with, regenerated in CI before the type check and never committed. Renaming one field gives 58 type errors. Queries go through `queryOf<Q>`,
  so a parameter the server does not take fails the type check.
- **No refusal text is matched by the page.** No `message.includes`, no prefix test: the page looks at codes only and draws the server's sentences as they come. `CompareReply.baseline_findings` is told apart structurally.
- **A plan is the server's.** The page never computes an operation or a hunk: it asks, draws the hunks, posts the operations back. It sends text for a constant's value, a section's and a raster's keys and a unit, and the server judges it in its own
  words (`probe_rules.txt` 2, 3): `5.0` stays `5.0`, and the largest uint64 as a constant's value comes through exact. This is the right pattern, and C1 is what the page gets where it does not follow it.
- **What can be asked is mostly answered, not restated:** `kinds`, `scopes`, `creatable`, `adoptable`, `carried`, `choices`. The add form's composed definition was judged right by the server on 24 of 24 combinations (`probe_declare.txt`), both storages and neither refused in the server's words.
- **The hand tables agree today.** 12 of 12 (`probe_tables.txt`); `offers` against the plans 12 of 12 answers; "may this go" 7 of 7; `ADDRESS_LIMIT` is exact to the byte (65521 answered, 65522 is 414); `segments` 13 of 13 spellings.
- **Dependencies:** six in production, each used, each where it should be (`react-aria-components` in `ui/` alone, `dagre` in the worker's chunk alone, measured in the bundle). A licence gate. Nothing to remove.
- **The server decides little that is the page's.** `Route.kind` and `EDITORS` speak of screens and fields (pass 2 I8), and from this side that costs only their words: the page maps them one to one.

### Issues

#### Critical

- **C1. The grid holds a 64 bit integer as a double: a value past 2^53 is shown wrong, and a typed or pasted one lands in the file as another number, without a word.**
  `gui/src/lib/objectValues.ts:104` (`Number(text)`), `:32`, `gui/src/api/client.ts:366`, `src/ddd/gui/contract.py:1447`, `:1411`, `:1437` (`float` on the wire), `gui/src/components/ValuesGridView.tsx:211`.
  Trigger, in the real page (`browser_u64.txt`, `probe_u64.txt`), a `uint64` block whose file holds `[9007199254740993, 18446744073709551615]`:
  the wire answers `[[9007199254740992.0, 1.8446744073709552e+19]]`, and the grid shows `9007199254740992` and `18446744073709552000`, a number the datatype cannot hold, under a meta line reading `0 … 18446744073709552000`.
  Typing the 64 bit mask `0x8000000000000001` (`Number` takes hex) offers `Sets element 1 of u64_block to 9223372036854776000`; Apply writes `9223372036854776000`, which is `0x80000000000000C0`: bit 0 gone, bits 6 and 7 set, no finding, since it fits. Typing `9007199254740993` writes `...992`.
  Pasting `9007199254740993, 9007199254740995` plans `9007199254740992, 9007199254740996`. Typing the file's own `18446744073709551615` is refused with `18446744073709552000 does not fit into uint64`, a number nobody typed. Expected: what was typed, or a refusal.
  It contradicts `models/common.py:206` ("the range of a 64 bit datatype does not survive a float") and `models/conversion.py:357`. No test holds a value past 2^53 through the page or the wire, and no spec mentions it (`grep`: none). Narrow, and silent where it bites: it reaches the C of every component reading the value.
  *Change:* text across the line (the boundary below, move 1): cells answered as exact text, what was typed sent as text, parsed, converted and rounded by the server. M. A stop-gap in hours: refuse any whole number whose text does not survive `Number`, and say the grid cannot show it.

#### Important

- **I1. `settle` and `type-plan` take any value, so the page is the only guard of what a file can hold, and its guard passes what the loader refuses.** `src/ddd/gui/api.py:1219`, `gui/src/lib/variableKeys.ts:468` (`limitsRaw`), `:491`.
  Trigger (`browser_u64.txt`): open the `limits` row of a `uint64` measurement stating `max 18446744073709551615`, typing nothing. The Max field reads `18446744073709552000`, the row `will change`, Apply is offered. Pressed, it writes that number and `a.ddd.json` stops loading: `schema`, "does not fit 64 bits". Undo puts it back.
  Asked without the page (`probe_guard.txt`): `datatype "uint7"`, `unit 5`, a conversion with factor 0, `size 0`, `dimensions "N"` are each planned and applied by `settle`, and the files stop loading; a type's `limits` with max below min likewise. The vocabularies' plans refuse all of it (`project_shared.Vocabulary`'s judges, 3 of 3), and so does `value-plan` (2 of 2).
  `KNOWN` as a design: spec `2026-09-20-gui-other-keys-design.md` 4.2 ("the page sends only a value one of section 4.1's editors can produce"). It contradicts `variableKeys.ts:464-466` ("a pair the models refuse ... never becomes a value to settle on"). Adds to pass 2 I3: a second client has no guard at all here.
  *Change:* one judge, the models asked of the definition as the plan would leave it, in `settle` and `type-plan`, as the vocabularies have; what is wrong only in context stays written and reported, as the spec rules. The page's Min and Max travel as text. S to M.

- **I2. A variable stating no limits cannot be given any: Min and Max end in "Nothing to change".** `src/ddd/lsp/edits.py:549` (`key in DEFERRED_KEYS and stated is None`), `gui/src/components/KeyChooser.tsx:81`.
  Trigger (`browser_limits.txt`): a measurement with no `limits`, its row selected, Min `0`, Max `100`: the section reads `Nothing to change`, no Apply, the file untouched; the same on a variable of two declarations (`probe_limits.txt`). The rule that a declaration may defer to whoever states limits is applied when nobody does.
  It contradicts spec 5.2 ("a min and a max ... before it offers to apply") and `gui/src/lib/declarations.ts:36` (`limits` "left for the key chooser to add afterwards"): a declaration made in the GUI can never have limits. No journey has this case; every one starts from stated limits. A type's limits work.
  *Change:* where no declaration states the key, the settlement writes it, at least on the producer. S; which declarations is a decision (question 3).

- **I3. The component's table is a second reader of the file format, in a `.tsx`, and it is wrong twice.** `gui/src/screens/ComponentPage.tsx:150`, `:46`, `:166-169`, the claim at `:157-161`.
  The one screen with no read model: it reads `GET /api/file` by string pointers. Trigger (`browser_u64.txt`, `probe_offered.txt`): a `value_block` or `measurement` naming a *scalar* type with dimensions has no button in its Shape cell, on the comment's ground that such a declaration is structured and the dictionary holds no such object; `GET /api/values` answers it (`typed_block` 200, `[4]`, by its address it edits and writes correctly, `probe_misc.txt`).
  A `curve` naming a structure has the button, and the grid answers 404. And the Unit column reads `none` for every declaration naming a type (`typed_block`, `typed_meas`, `cur_typed`: `Speed_t` fixes `rpm`), with the panel beside it saying `rpm, from Speed_t`.
  `docs/file_formats/types.rst:193` describes naming a scalar type as how components agree about a value, so this is an ordinary project. The comment reasons from `examples/`, where every `typename` is a measurement or a parameter. *Consequence:* each of these rules exists twice, the second copy unreachable by vitest.
  *Change:* `GET /api/component?file=` answering rows - scope, name, kind, type, effective unit, shape text, whether a grid opens, asked of the code that draws the grid. The page loses `SHAPED_BY_KIND`, `shapeOf`, `offered`, `valueAt`, `lib/values.ts`, `lib/formats.ts`. M.

- **I4. "A file-format change the page has not caught up with fails the build" is false.** `gui/scripts/schemas.mjs:1-3`, spec `2026-09-17-web-gui-design.md:401-403`, `gui/src/lib/formats.ts:4`, `src/ddd/gui/contract.py:415`.
  Trigger (`mutate.txt`): renaming `kind`, then `interface`, throughout `generated/component.ts`: tsc exit 0, vitest 959 of 959. `ComponentPage` reads `data` (`Any`) through strings; the type guards one `?.component?.name`, behind a cast. Of the eight generated file-format modules, one type of `component.ts` and one of `sections.ts` are imported; `constants`, `dictionary`, `project`, `rasters`, `types`, `units` by nothing (`graph.txt`).
  *Change:* with I3 gone there is nothing left to guard; `SectionAccess` can come from the contract, and `schemas.mjs` loses its first half. S after I3. Until then, correct the two sentences.

- **I5. The shapes are one definition; the routes, the replies, the refusal codes and the kinds are not.** `src/ddd/gui/routes.py:41` (a `Route` names no reply), `gui/src/api/client.ts:154` (`body as T`, 35 sites), `gui/src/lib/findings.ts:256`, `gui/src/api/client.ts:183`, `src/ddd/gui/contract.py:1415`, `:1434`, `gui/src/lib/refusals.ts:30`.
  Trigger, measured (`mutate.txt`, table below): `FindingRoute.kind` gaining a word passes tsc and vitest, and `routeOf` opens the component's page for it - the very failure `finding_routes.py:210-224` spends a docstring guarding on the Python side, which stops at the contract. A new parameter of `FindingsQuery` is dropped by `findingsQuery`'s hand list, silently. A conversion kind added to the models reaches `physicalOf` and `rawOf`, which compute with it, as `{[k: string]: unknown}`, and reads as the identity.
  A wrong path passes tsc, and fails vitest only because `client.test.ts` keeps its own list; nothing compares that list with `ROUTES`. The error body and its codes (`stale`, `unreadable`, `not-found`) are in no schema: 21 string comparisons, pinned by journeys.
  *Change, in order:* `switch` with `never` in `routeOf`, `findingsQuery` through `queryOf`, the codes as a `Literal` in the contract (S together); a `reply` on `Route`, a generated route table, one generic `ask(route, query)` replacing 35 hand pairings (M); `Conversion` typed, or gone from the page with C1's move.

- **I6. Three panels are one panel, copied; two more are nearly.** `gui/src/screens/{Constant,Section,Raster}Panel.tsx`, `gui/src/components/{Constant,Section,Raster}PanelView.tsx`, also `UnitPanel`, `TypePanel`. `KNOWN` in part (`2026-10-08-gui-journeys-every-action.md`, P19b-24; `2026-09-28-gui-rasters.md`).
  Measured (`measure_fe.txt`, code lines with each vocabulary's noun normalised): screens 0.84-0.86 alike, `UnitPanel` 0.70, views 0.80-0.81. `Outcome` four times; `use*Plan` five; `refusalOf` three times, two of them identical (`UnitPanel.tsx:35`, `TypePanel.tsx:40`), eight screens importing it from `UnitPanel`; the test for a stale refusal in 13 places of ten files, `isStale` used by one; `Apply to {n} file` six times; `routeOfUse` three times.
  *Consequence, already happened:* the panels differ on what a refusal leaves standing (P19b-24, "the unit panel keeps its Apply, the type panel withdraws it"), `TypePanelView` decides a route in a `.tsx`, and a fourth vocabulary falls through to a constant's panel in four unguarded chains (`SharedPage.tsx:152-168`).
  *Change:* one `useOffers(requests, ask, label, invalidate)` and one `Outcome`, `refusalOf` beside `isStale` in `lib/refusals.ts`; a panel keeps its fields. By my estimate about 600 of the five panels' 2,200 lines of code go, and there is one rule for a refusal. M. A generic vocabulary panel on `Vocabulary`'s descriptor is a further decision (question 4).

- **I7. The rule "no decision may live in a `.tsx`" is not kept, and what breaks it is reachable only by a browser journey.** Stated in eight plans (`2026-09-28-gui-rasters.md:43` ...) and at `gui/src/app/useDebounced.ts:24`. `KNOWN` (`2026-09-20-gui-other-keys.md`, "A screen's own state is guarded by the journeys alone"; `2026-10-08-gui-journeys-every-action.md`).
  Measured: `screens/` 3,608 lines of code, about 600 conditionals (a rough count), 119 `useState`, no unit test; vitest's gate reaches `api`, `lib`, `state`. Decisions that are no wiring: `ComponentPage.tsx:44-65,166-169`, `DeclarePanel.tsx:41-60` (`requestOf`), `TypePanel.tsx:197-204` (`active`), `VariablePanel.tsx:162-194` (`selected`, `range`, `target`), `UnitPanel.tsx:35`, `DeclarePanelView.tsx:43-56` (`scopeOf`), `ConstantPanelView.tsx:76,262-287`, `TypePanelView.tsx:68-69,279-291`.
  Mutation: `SHAPED_BY_KIND` losing `map`, `refusalOf` inverted: tsc 0, vitest 959 of 959 (`mutate.txt`). Only a journey can catch them, and a journey has the example's cases, which is how I3 lived.
  *Change:* move what is listed into `lib`, S each. Then either enforce the rule (a lint on what a screen may contain) or restate it as "no domain decision", which is what is worth keeping (question 5).

- **I8. A plan is a GET, so the request line bounds what can be pasted.** `gui/src/api/client.ts:381`, `:394`, `src/ddd/gui/api.py:1687`. `KNOWN` by design (`2026-09-24-gui-paste-design.md:166`).
  Trigger (`browser_paste.txt`): a 128 by 128 table of whole counts: `'table_128' has too many values to plan in one request: its counts need 96467 characters of address, and ddd gui reads at most 65521`. The limit is http.server's, the page carries it as a constant, and past about 8,000 to 10,000 whole counts, or 2,500 with long decimals, a reader has no way in the GUI to set a table but cell by cell. Nothing in the domain asks for it.
  *Change:* `POST /api/values-plan` with the counts in the body, gated as any POST is. S; the constant goes.

#### Minor

- **M1. The first vertical became the library.** `gui/src/lib/units.ts:186` (`baseName`), `:161` (`consequence`), `:177`, `:208`; `gui/src/lib/projectUnits.ts:218`; `gui/src/screens/UnitPanel.tsx:35`; `gui/src/components/UnitPanelView.tsx:23`. `lib/units.ts` has the highest fan-in of `lib` (25), for helpers about plans and paths: 12 importers each of `baseName`, `consequence`, `shownChanges`. `planEdit` is `shared.planEdit` -> `projectUnits.planEdit` -> `units.editOf`, and `findings.fixEdit` writes `editOf` again; `nonEmpty` and `owner` twice. `VariablePanelView` types its removal from a unit's panel. Read off the graph. *Change:* `lib/plans.ts`, `baseName` to `lib/paths.ts`, the wrappers gone. S.
- **M2. Two cycles between folders, one edge the wrong way, and nothing guards the direction.** `gui/src/api/client.ts:1` (into `state/edits`) with `gui/src/state/revisions.ts:1`; 28 imports from `screens` into `app`, which imports every screen; `gui/src/ui/Table.tsx:12` takes `ROW_HEIGHT` from `lib/findingsWindow`. `state/` is an in-memory store, `localStorage` for the canvas and the long poll: three things. `graph.txt`. No test or lint looks at imports in `gui/src`. *Change:* `revisions.ts` to `api/`; `app/` split into the root and `hooks/`; `postEdit` not noting into a store (a caller does, or a listener); `ROW_HEIGHT` in a leaf; a thirty line vitest walking imports. S.
- **M3. The Files tab's hold re-derives what the plan did, from its operations.** `gui/src/lib/filesHold.ts:49` (the pointer's regex), `:53`, `:103` (a path join), `:82`. Trigger (`probe_rest.txt`): `extra\x3.ddd.json` and `EXTRA/X1.DDD.JSON` on Windows: the held row's key is not the server's, and it reads "not read by the last analysis" until the list answers. The plan notes links, not these. *Change:* `FilesPlanReply` carries the row it adds and the key it removes; `INSERTED`, `ABSOLUTE`, `joined` go. S.
- **M4. Small divergences in the page's arithmetic.** `gui/src/lib/objectValues.ts:41` against `models/conversion.py:353` ("as `round_physical` takes it off"): exact ties differ, 2,321 of 60,000 random values (`probe_numbers.txt`), `1234567890.125` reads `...13` and `...12`; display only. `:37`: `Math.round` makes `2.5` 3 and `-2.5` -2, and `0.6` typed into a boolean in Physical stores `1` where Raw refuses it (`probe_misc.txt`). `1,5` is refused typed (`:104`) and read as 1.5 pasted (`:165`). All go with C1's move, but for the paste's own reading of a comma, which is the page's.
- **M5. A label cut through a surrogate pair refuses the edit.** `gui/src/lib/undo.ts:143`. Trigger (`probe_rest.txt`): a rename of a unit spelled with emoji past the limit: `POST /api/edit` answers 400, `lone leading surrogate`. It contradicts "no edit is ever refused for the length of a name". Rare. *Change:* cut by code point. S.
- **M6. Small tables and sentences held twice, agreeing today, pinned by nothing across the line.** `lib/shared.ts:201`, `:237`, `lib/projectUnits.ts:12`, `lib/undo.ts:16`, `lib/findings.ts:324`; `lib/objectValues.ts:94`, `:139`, `:292`, `screens/ValuesPage.tsx:283`, `components/ValuesGridView.tsx:173` with `object_values.py:312,314,317,325,348,421`. And twice on the page itself, "kept here too": `KIND_WORDS` (`lib/projectTypes.ts:5`, `components/TypePanelView.tsx:52`), the scope words (`lib/declarations.ts:7`, `components/DeclarePanelView.tsx:43`). Drift is loud or only wording. *Change:* `ValuesReply` says why a grid is read-only, in a field; the file name adopted, in `UnitsReply`; the rest stay. S.
- **M7. Words and code about the contract that nothing holds.** `gui/src/api/types.ts:1-4` says a model without a page type "fails the build": 43 generated names are not re-exported and nothing fails, and 18 of the 90 hand-listed are imported by nothing (`probe_contract.txt`). *Change:* `export type * from "../generated/api"`. `gui/src/screens/FindingsPage.tsx:205` invalidates a key no query has. After an undo one predicate says what is asked again (`lib/undo.ts:209`), after an Apply each screen lists its own: one policy would do. `GET /api/checks` and `GET /api/dictionary` have no client in the page. S.
- **M8. A raster cannot be made acyclic from its panel.** `gui/src/lib/shared.ts:243`. Emptying Cycle sends `""`, refused (`browser_paste.txt`); the plan route takes the key away with `raw` left out, and no field asks that. `KNOWN` (`2026-09-28-gui-rasters.md`, "How a reader clears an optional string wants a design answer"). *Change:* an empty field on an optional key sends no `raw`. S.
- **M9. The panel and the checker disagree about limits past 2^53.** `src/ddd/value_identity.py:63` (`float(bound)`). `ddd check` reports `definition-mismatch` on `...992` against `...993` (`same_value/`), while `same_value` makes them one value (`probe_rest.txt`), so the panel shows no disagreement and settling says nothing to change: read off `variable_keys.py:235`. Against `value_identity.py:41-43` ("a caller has to group values the way the checker does"). *Change:* compare the exact numbers. S.
- **M10. 145 citations of planning artefacts in 51 files of the page, 184 of spec sections, and 40 % of `lib` is prose.** Beside pass 2 M9. Essays on column widths "measured in Chrome (fix round 3)" in 8 views, `useDebounced.ts` 52 lines of prose on 19 of code. Several no longer hold: `lib/shared.ts:9` and `SectionPanel.tsx:115` say no gate executes a `.tsx`, where CI's journeys do. *Change:* what a reader needs stays, with the history in the plans. S.

### Status of the 2026-09-15 findings in this area

None. That review predates `gui/` (the web GUI's design is of 2026-09-17): `SCRATCH/review-2026-09-15.md` has no finding on the page or on `ddd gui`.

### Open questions

1. **Must a 64 bit integer be exact in the GUI?** Yes, as I would answer and as the models say: C1's move, M. No: a refusal past 2^53, in hours, and the grid says it cannot show such a value.
2. **Does `settle` get a judge, against spec 4.2?** Yes: I1's change, and a batch tool inherits the guard. No: the page stays the only guard, a hole like C1's is a corrupt file each time, and a second client should be told.
3. **When nobody states `limits`, whom does a settlement write to?** The producer alone keeps "a consumer defers"; every declaration matches what the panel says of every other key. I2 wants one of them.
4. **One panel per vocabulary, or one panel?** The plans keep each table's facts concrete on purpose. One panel driven by `Vocabulary` makes a fourth vocabulary a data change and costs that concreteness; `useOffers` (I6) is worth doing either way.
5. **Is "no decision in a `.tsx`" still the rule?** As stated it asks for what no React screen can give. "No domain decision, and nothing a test should reach" is keepable, and a lint can hold part of it.
6. **Is a table past about 10,000 counts one the GUI should take?** If not, I8 is a sentence in the guide and nothing else.

### Test gaps

- No value past 2^53 anywhere: not in `test_object_values.py`, `test_gui_api.py`, `objectValues.test.ts`, `values.spec.ts`. The contract's `float` fields have no test of exactness.
- No differential between the page's rule and Python's, for any row of the table below. Each side pins its own literal: `segments`, `rounded`, `LIMIT`, `SECTION_STRINGS`, the codes. A pytest reading a table the server publishes, or a vitest run against a captured reply, would hold them.
- No journey on a `value_block` naming a scalar type, on a type's unit in the component's table, or on limits added to a variable with none (I2, I3). The journeys use the examples' shapes.
- A new `FindingRoute.kind`, a new `editor`, a new `FindingsQuery` parameter, a conversion kind: nothing fails (I5).
- `client.test.ts`'s list of paths is compared with nothing on the server, and `ROUTES`' reply with nothing at all.
- Nothing guards the direction of imports in `gui/src`.

### Assessment

The maintainer's question, for this boundary: **yes, for the most part, with three leaks worth closing before 1.0.** The server owns plans, diffs and the vocabularies' judgement, the wire's shapes are generated and no refusal text is matched: that is the hard part, and it is right. Where the page goes through a number instead of passing text, or reads a file instead of asking, or is trusted because the server does not check, it is wrong on a plausible project (C1, I1, I2, I3), and 959 unit tests at 100 % see none of it, because each side tests its own copy. None of the moves is large, and most remove page code. Inside the page the layering is sound and the views are clean; the screens carry too much, three of them are one, and the helpers that everything uses still live where the first feature put them. I would close C1 first, then I1 and I2, and treat I3 as the move that also ends the file-format generation.

#### The measured graph

Folder to folder, production files, value imports / type-only imports (`graph.txt`). Files and lines, code and prose: `app` 9, 704 (30 % prose); `screens` 19, 5,042 (27 %); `components` 29, 4,451 (23 %); `ui` 8, 351 (29 %); `lib` 33, 5,106 (40 %); `state` 3, 177 (30 %); `api` 4, 706 (23 %); `generated` 9, 6,560.

```
from\to       app   screens components   ui      lib     state    api    generated
main          2/0     .         .         .       .        .      1/0       .
app           4/0   12/0       1/0       4/0    10/3      2/0     3/3       .
screens      28/0   17/0      21/1      39/0    70/9      3/0    18/12      .
components     .      .       23/1      68/0    47/7       .      0/22      .
ui             .      .         .        1/0     1/0       .       .        .
lib            .      .         .         .     20/5       .      2/25     0/2
state          .      .         .         .       .        .      1/1       .
api            .      .         .         .       .       1/0     3/2      0/1
```

Going the wrong way: `screens` -> `app` (the hooks), `api` -> `state` (`client.ts`, `ownEdits`), `ui` -> `lib` (`ROW_HEIGHT`); and worth a look, `lib` -> `api/client` by value, twice, for `ApiError`. `api` <-> `state` is a cycle of folders, not of files. Highest fan-in: `api/types` 61, `api/client` 28, `lib/units` 25, `ui/Button`, `ui/Banner` 22, `lib/route` 18, `lib/findings` 17. `screens/UnitPanel` has 8, for `refusalOf`.

**What the folders mean.** `ui`: what it says, widgets over React Aria. `components`: the views, plus a few widgets of the domain; what it says. `screens`: queries, state and, against the rule, decisions. `lib`: pure and framework-free but for `canvas.ts` (`@xyflow/react`) and `layout.ts` (`dagre`); the name hides three kinds of thing (wording, the page's state machines, copies of domain rules, the last of which should shrink). `api`: what it says, but for noting edits into a store. `app`: the root and the hooks, two things. `state`: three things. **Files of several hundred lines:** `variableKeys.ts` (494) is four jobs (the table's rows, wording a value, the chooser's sections, a range's fields), and four modules import `shortValue` from it, three of them for that alone; `shared.ts` (409) is three families copied per vocabulary, 40 % prose; `ComponentPage.tsx` (429) is a format reader and a table; `SharedPage.tsx` (396) a page and a form. `canvas.ts`, `files.ts`, `findings.ts`, `client.ts`, `FileActionsView.tsx`, `GraphPage.tsx` are long and cohesive: leave them.

**Justified by the job:** the long poll and revision keys; dagre in a worker (measured by them at 475 to 1,164 ms for 3,333 components); virtual tables and the findings window (25,000 findings); `useKept` and the holds as display, given an edit is answered before its analysis (a 500 ms budget at 100,000 declarations). **Simpler with no loss:** I6; `api/types.ts`; `client.ts`'s 40 functions, once a table is generated; the page's half of the holds that re-derives a plan (M3); invalidation lists (M7).

#### Every domain rule the page holds

"Diverged" means I made them disagree on a real `ddd gui`. "Judged" means the server has the last word, so drift costs a refusal rather than a wrong file.

| rule | page | python | state |
| --- | --- | --- | --- |
| what a typed number is | `objectValues.ts:104` | `gui/api.py:2386` | **diverged**, C1 |
| physical to raw, and rounding | `objectValues.ts:32` | `conversion.py:129`, no rounding anywhere | **diverged**, C1, M4; the rounding exists on the page alone |
| raw to physical | `objectValues.ts:23,41` | `conversion.py:126,353` | **diverged** at ties, M4; any new kind reads as identity, I5 |
| a range | `variableKeys.ts:446-494` | `objects.py:167`, `common.py:201` | **diverged**, I1; not judged |
| which declarations have a grid | `ComponentPage.tsx:46,166` | `object_values.py:116` | **diverged**, I3 |
| the unit a declaration has | `ComponentPage.tsx:150` | the type's `fixed` | **diverged**, I3 |
| the file format | `ComponentPage.tsx:129-151` | `models/component.py`, `objects.py` | can drift unseen, I4 |
| which limits can be added | field drawn, `KeyChooser.tsx:81` | `edits.py:549` | **diverged**, I2 |
| where an appended entry goes, its key | `filesHold.ts:49,53,103` | `lsp/units.py:104`, `resolve_path` | **diverged**, transient, M3 |
| the storage a kind asks; identity beside a datatype | `declarations.ts:41,75` | `objects.py:384,400,415` | agrees, 24 of 24; judged |
| a dimension | `declarations.ts:82` | `objects.py:87` | agrees on 11 spellings; judged |
| a size typed | `variableKeys.ts:422` | `objects.py:87` | agrees; not judged, I1 |
| a section's, a raster's json strings | `shared.ts:201,237` | `project_shared.py:775,970` | agrees; judged; unpinned, M6 |
| what `add` requires | `shared.ts:269-321` | `project_shared.py:703,780,975` | agrees, 3 of 3; judged |
| a section's access | `shared.ts:59` | `models/sections.py`, by the generated type | one definition |
| may this go | `ConstantPanel.tsx:142`, `SectionPanel.tsx:132`, `shared.ts:344` | `shared_plans.py` | agrees, 7 of 7; judged |
| what a unit offers | `projectUnits.ts:93` | `lsp/units.py:261,288,312` | agrees, 12 of 12; judged |
| which check a unit's findings are | `projectUnits.ts:54` | `finding_routes.py:26` | agrees by reasoning; not run on a project of several images |
| a component needs a name | `files.ts:185` | `file_plans.py` | agrees, 6 of 6; judged |
| what a cell write does to `stated` | `valuesHold.ts:45` | `object_values.py:331` | agrees; display only |
| why a grid is read-only; two more sentences; `table`; `elementLabel` | `objectValues.ts:94,139,292`, `ValuesPage.tsx:283`, `ValuesGridView.tsx:173` | `object_values.py:312-325,348,421` | agrees; wording, M6 |
| the pointer grammar | `pointer.ts`, `findingsByRow.ts:49`, `findings.ts:344`, `ConstantPanelView.tsx:76`, `variableKeys.ts:223`, `objectValues.ts:286`, `filesHold.ts:49` | `lsp/ranges.py` and pass 2 M8's regexes | `segments` agrees, 13 of 13; nine sites; unowned |
| which file kinds have a screen; why a finding leads nowhere | `findings.ts:324,337` | `finding_routes.py:232` | agrees on the probes; wording |
| route kind to screen | `findings.ts:223` | `finding_routes.py:205`, `contract.py:274` | not exhaustive, I5 |
| the vocabularies | `route.ts:19`, `shared.ts:19,49` | `project_shared.py:993` | agrees; KNOWN four chains |
| kinds of type; scopes | `projectTypes.ts:5,28`, `declarations.ts:7` | `models/types.py`, `component.py:16` | agrees; each twice on the page, M6 |
| a conversion's kind left out | `variableKeys.ts:252` | `conversion.py:274` | agrees on 8 of 9, the ninth a block the models refuse |
| refusal codes | `refusals.ts:30,67`, 13 sites | `editing.py:60`, `gui/api.py` | agrees; journeys pin, I5 |
| a label's length; the adopted file | `undo.ts:16`, `projectUnits.ts:12` | `contract.py:1662`, `lsp/units.py:43` | agrees; M5, M6 |
| the request line | `client.ts:381` | http.server | agrees to the byte; I8 |
| which reads follow the analysis | `undo.ts:190` | each route of `gui/api.py` | unpinned, cannot be measured from outside |
| units in play | `units.ts:224` | `variable_keys.py:217` | agrees; the reply already says it |

Rules the page holds alone, rightly: what a paste means (rows, tabs, a decimal comma), debouncing, selection, labels, the sentences of a consequence. Wrongly alone: rounding a physical value to a count.

#### What is generated, and what is mirrored

| crossing | how it is defined | what a change does (`mutate.txt`) |
| --- | --- | --- |
| a reply's or a query's shape | generated, 133 names | a field renamed: **tsc fails, 58 errors** |
| a query's parameters | `queryOf<Q>`, but `findingsQuery` lists its own | a new one: passes, dropped |
| path and method | literals in `client.ts` | wrong path: tsc passes, vitest fails on the page's own list; a server rename fails only journeys |
| which reply a route gives | `request<T>`, `body as T`, 35 sites; no reply on `Route` | unchecked |
| error body, codes | by hand | page's spelling changed: vitest fails on its own literal; a server rename fails only journeys |
| `FindingRoute.kind`, `editor` | generated `Literal`, used non-exhaustively | a new word: **passes everything** |
| `Conversion` | `dict[str, Any]` by decision, computed with on the page | a new kind: **passes everything** |
| `FileContent.data` | `Any`, read by string pointers | a key renamed: **passes everything** |
| `SharedEntry.kind`, `ProjectType.kind`, `SourceFile.kind` | `str` by decision | falls through a chain |
| `stated`, `fixed` | `dict[str, str]` of json text | parsed where read |
| names the screens import | hand list of 90 in `api/types.ts` | nothing, M7 |
| refusal sentences | shown, never matched | nothing to drift |

#### The boundary I would draw

**The page holds what a person sees and does: words, layout, selection, focus, drafts, debouncing, what is drawn while an analysis catches up. The server holds what a project is and what a value means: reading a value, converting it, rounding it, whether a file could hold it, what a declaration resolves to. Text crosses the line; numbers do not, but for drawing.** The page should never compute a value that ends up in a file, and never read a description file.

| # | move | what crosses | removes | size |
| --- | --- | --- | --- | --- |
| 0 | Guards first: exhaustive `routeOf`, `findingsQuery` through `queryOf`, codes as a `Literal`, `export type *`, an import walk as a ratchet | nothing | half of I5, M2's silence, M7 | S |
| 1 | Cells as exact text: `ValuesReply` answers `rows` and readings as text, axes likewise; `value-plan` and `values-plan` take what was typed and `physical` or `raw`; the server parses, converts, rounds, judges, and says what it stored | `typedNumber`, `rawOf`, `physicalOf`, `rounded` to the server; the plot parses text to draw | C1, M4 | M |
| 2 | One judge in `settle` and `type-plan`; Min and Max as text; the limits of a variable that has none | `limitsRaw` to a template; the rule to the models | I1, I2, M9 | S to M |
| 3 | `POST /api/values-plan` | `ADDRESS_LIMIT` goes | I8 | S, with 1 |
| 4 | `GET /api/component` | `SHAPED_BY_KIND`, `offered`, `shapeOf`, the raw reads to the server; then the file-format half of `schemas.mjs` goes | I3, I4 | M |
| 5 | Plans carry what the page now derives: `FilesPlanReply`'s row and key; `ValuesReply`'s read-only sentence; the adopted file's name | `INSERTED`, `joined`, `readOnlyNote`, `ADOPTED` | M3, M6 | S |
| 6 | Inside the page: `lib/plans.ts`; `refusalOf` in `lib`; one `useOffers`, one `Outcome`; the decisions of I7 into `lib`; `revisions.ts` to `api/`, `hooks/` out of `app/` | none | I6, I7, M1, M2 | M |
| 7 | A generated route table: `reply` on `Route`, one `ask(route, query)` | the 35 pairings become one | the rest of I5 | M |
| 8 | One vocabulary panel, if question 4 says so | the panels' key lists to `Vocabulary` | about 400 more lines | M |

About two weeks in all; 0 to 3 are three or four days and stand on their own, and 1 and 2 are the ones that change what a user can lose. **Across the line the other way:** nothing that needs doing now. `Route.kind` and `EDITORS` could name what a finding or a key is about rather than a screen and a field, as pass 2's move 7 will do anyway.

**What I would leave exactly as it is:** the plan, preview and apply round trip, with operations posted back as data; refusals as the server's sentences; `contract.py` and `queries.py` as the wire (pass 2 agrees); the views as pictures of their props, with stories and screenshots on them; `ui/` over React Aria; `useDebounced`, `planShown`, `useKept`, `panelShows`, the findings window, the layout worker: each answers a measured problem, and each is the page's; the paste parser; six production dependencies.

```candidates
3|C1|gui/src/lib/objectValues.ts:104|The grid holds 64 bit integers as doubles: past 2^53 it shows wrong and writes another number without a word (a typed mask loses bit 0)
3|I1|src/ddd/gui/api.py:1219|settle and type-plan take any value, so the page is the only guard, and opening a uint64's limits row offers a write the loader refuses (KNOWN as design)
3|I2|src/ddd/lsp/edits.py:549|A variable stating no limits cannot be given any: Min and Max end in Nothing to change, against spec 5.2 and declarations.ts:36
3|I3|gui/src/screens/ComponentPage.tsx:150|The component's table reads the raw file in a tsx: a type's unit reads none, a block naming a scalar type has no grid button, a curve of a structure has one
3|I4|gui/scripts/schemas.mjs:1|A file-format change fails the build is false: renaming kind or interface in the generated types passes tsc and vitest; six of eight modules unused
3|I5|src/ddd/gui/routes.py:41|Shapes are one definition; routes, replies, refusal codes and kinds are not: a new route kind, query parameter or conversion kind passes every gate
3|I6|gui/src/screens/SectionPanel.tsx:60|Three panels are one panel copied (0.84 to 0.86 alike), Outcome four times, the stale block 13 times; they already differ on a refusal (KNOWN in part)
3|I7|gui/src/app/useDebounced.ts:24|No decision in a tsx is restated in eight plans and not kept: about 600 conditionals in screens with no unit test; mutations pass tsc and vitest (KNOWN)
3|I8|gui/src/api/client.ts:381|A plan is a GET, so the request line bounds a paste: a 128 by 128 table is refused, the page carrying http.server's constant (KNOWN)
3|M1|gui/src/lib/units.ts:186|The first vertical became the library: baseName and consequence in lib/units, planEdit three ways, refusalOf imported from UnitPanel by eight screens
3|M2|gui/src/api/client.ts:1|Folder cycles api and state, screens and app; ui imports lib; state is three things; nothing guards the direction of imports in gui/src
3|M3|gui/src/lib/filesHold.ts:49|The Files tab's hold re-derives a plan's entry by regex and path join; differs from the server on a backslash or another case, until the list answers
3|M4|gui/src/lib/objectValues.ts:41|rounded differs from round_physical at ties; Math.round is asymmetric at half; 0.6 in a boolean stores 1; a decimal comma refused typed and read pasted
3|M5|gui/src/lib/undo.ts:143|fitted cuts a label through a surrogate pair and the edit is refused 400, against no edit is ever refused for the length of a name
3|M6|gui/src/lib/shared.ts:201|Small tables and sentences held twice across the line, and KIND_WORDS and the scope words twice on the page; agree today, unpinned
3|M7|gui/src/api/types.ts:1|The header's fails the build is false, 18 of 90 re-exports unused; a dead invalidation; two policies for what is asked again; two routes with no client
3|M8|gui/src/lib/shared.ts:243|A raster cannot be made acyclic from its panel (KNOWN)
3|M9|src/ddd/value_identity.py:63|same_value reads limits through float: ddd check reports a mismatch past 2^53 and the panel shows one value with nothing to settle
3|M10|gui/src/lib/shared.ts:9|145 citations of planning artefacts in 51 files, 40 % of lib is prose, width essays in 8 views, some no longer true
```
