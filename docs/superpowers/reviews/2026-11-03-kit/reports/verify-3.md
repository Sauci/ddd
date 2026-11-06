### Verification of pass 3

By a reader who did not find these, on 2026-11-06, on the tree at master 2b4bae6c. Scratch:
`SCRATCH/verify-3-4/`. 19 CONFIRMED. Grade changes: I8 Important -> Minor.

| id | verdict | grade (was -> now) | duplicate of | evidence | note |
| --- | --- | --- | --- | --- | --- |
| C1 | CONFIRMED | Critical -> Critical | - | verify-3-4/p3/c1_http.txt, p3/c1_browser.txt | reproduced in Edge and over HTTP: init [9007199254740993, 18446744073709551615, 7] is answered [9007199254740992.0, 1.8446744073709552e+19, 7.0] and shown 9007199254740992 and 18446744073709552000; typed 0x8000000000000001 writes 9223372036854776000 = 0x80000000000000c0; typed ...993 writes ...992; a pasted row plans ...992, ...996, ...996; typed 2^64-1 refused as 18446744073709552000; correction: the preview sentence names the stored number, nothing says it differs from what was typed |
| I1 | CONFIRMED | Important -> Important | - | verify-3-4/p3/i1_i2_http.txt, p3/limits_browser.txt, p3/vocab_judge.txt | reproduced: settle writes datatype uint7, unit 5, factor 0, size 0, dimensions "N", limits 10..1 and type-plan factor 0, uint7, limits 10..1, each applied and each file then fails schema, while value-plan refuses 70000 and 1.5 in uint16 and constant-plan refuses 3 of 3; in Edge the limits row of a uint64 stating 2^64-1 opens on Max 18446744073709552000, will change, Apply writes it and a.ddd.json fails schema (does not fit 64 bits); KNOWN holds as a design (spec 2026-09-20 4.2:105-108); related to 2:I3, not the same defect |
| I2 | CONFIRMED | Important -> Important | - | verify-3-4/p3/limits_browser.txt, p3/i1_i2_http.txt | reproduced in Edge: Min 0 and Max 100 typed on nolim (two declarations, none stating limits) and on plain (one declaration) read Nothing to change, no Apply, file unchanged; GET /api/settle answers 200 with no changes; lsp/edits.py:549 skips any declaration stating none; spec 5.2's field and declarations.ts:36 promise it; no plan leaves it open, no journey covers it |
| I3 | CONFIRMED | Important -> Important | - | verify-3-4/p3/i3_browser.txt | reproduced in Edge: a value_block naming the scalar type Speed_t with dimensions [4] has no Shape button while GET /api/values answers 200, shape [4], unit rpm, file set; its Unit cell and a measurement naming Speed_t read none where GET /api/variable says rpm; a curve naming a structure has the button and the grid answers 404 (that declaration is itself a type-kind error) |
| I4 | CONFIRMED | Important -> Important | - | verify-3-4/p3/mutate.txt | my copy: every kind (10 properties) or interface renamed in generated/component.ts passes tsc 0 and vitest 959/959, a renamed component (the one read through the type, ComponentPage.tsx:209) fails tsc; only generated/component (formats.ts) and generated/sections (shared.ts) of the eight file-format modules are imported |
| I5 | CONFIRMED | Important -> Important | - | verify-3-4/p3/mutate.txt | my copy: FindingRoute.kind gaining widget, and FindingsQuery gaining a parameter, each pass tsc 0 and vitest 959/959; routeOf's last line sends any other kind to the component page (findings.ts:256); findingsQuery lists its five by hand (client.ts:184-193); /api/graph misspelt passes tsc and fails 1 vitest of client.test.ts's own list; 21 code comparisons by string, no error schema in the contract; conversion kinds today are four and agree |
| I6 | CONFIRMED | Important -> Important | - | verify-3-4/p3/likeness.txt, p3/fourth_vocabulary.txt | my own measure: screens Constant/Section/Raster 0.84 to 0.86 alike, UnitPanel 0.69 to 0.71, views 0.80 to 0.81; Outcome defined in four views, each saying it mirrors another; refusalOf identical in UnitPanel and TypePanel, imported from UnitPanel by eight screens; the stale test 13 times in ten screens, isStale used by one; a fourth vocabulary in my copy: tsc stops at SHARED_VOCABULARIES only, then 0; the recorded refusal divergence holds (P19b-24, P19c-6); KNOWN in part holds |
| I7 | CONFIRMED | Important -> Important | - | verify-3-4/p3/mutate.txt, p3/screens_measure.txt | eight plans carry the rule as a Global Constraint; screens/ 3,622 code lines, 119 useState, 596 conditionals by my count, no unit test, vitest's coverage list api, lib, state; SHAPED_BY_KIND losing map and refusalOf inverted each pass tsc 0 and vitest 959/959 in my copy; KNOWN holds (2026-09-20-gui-other-keys.md:2980 Left open; 2026-10-08 plan:1643) |
| I8 | CONFIRMED | Important -> Minor | - | verify-3-4/p3/paste_browser.txt, p3/paste_float_browser.txt, p3/paste_float_lengths.txt, p3/paste_float_random.txt | reproduced in Edge with a narrower trigger: 100x100 five digit counts (80028 characters) and 128x128 are refused, the server answers 414 when asked straight, but 80x80 whole counts and 40x40 and 56x56 float32 maps at factor 0.1 plan, and by the page's own arithmetic a 64x64 one needs 50203 characters and random 1 to 3 decimal 64x64 maps at factors 0.1, 0.01, 0.5 at most 54916, refusal starting near 70x70; lowered: a rare table size, refused in a sentence naming it, cell by cell still open; KNOWN by design holds (2026-09-24-gui-paste-design.md:165-172) |
| M1 | CONFIRMED | Minor -> Minor | - | verify-3-4/p3/tsimports.txt; read off gui/src/lib/shared.ts:4,407, lib/projectUnits.ts:218, lib/units.ts:53,208-218, lib/findings.ts:352-366, lib/variableKeys.ts:310, components/VariablePanelView.tsx:12 | measured: lib/units.ts has the highest fan-in of lib (25), baseName, consequence and shownChanges 12 importers each; planEdit goes shared -> projectUnits -> units.editOf and findings.fixEdit is editOf's body again; nonEmpty and owner twice; VariablePanelView imports type Offer from UnitPanelView |
| M2 | CONFIRMED | Minor -> Minor | - | verify-3-4/p3/tsimports.txt, p3/mutate.txt | measured with my own graph: folder cycles api<->state (client.ts imports ownEdits from state/edits, revisions.ts imports client) and app<->screens (28 imports into app), ui/Table.tsx takes ROW_HEIGHT from lib/findingsWindow, no file cycle; a lib -> screens re-export in my copy passes tsc, vitest 959/959 and biome |
| M3 | CONFIRMED | Minor -> Minor | - | verify-3-4/p3/m3.txt | reproduced on Windows: Add of extra\x3.ddd.json and of EXTRA/X1.DDD.JSON, the page's filesHoldOf holds keys .../extra\x3.ddd.json and .../EXTRA/X1.DDD.JSON where GET /api/files lists .../extra/x3.ddd.json and .../extra/x1.ddd.json; extra/x1.ddd.json agrees (control); transient, until the list answers |
| M4 | CONFIRMED | Minor -> Minor | - | verify-3-4/p3/m4.txt, p3/misc_http.txt | reproduced: rounded(1234567890.125) reads 1234567890.13, round_physical 1234567890.12 (15 of 20,000 random 13 digit values differ, a smaller share than the pass's sample); rawOf 2.5 -> 3, -2.5 -> -2; 0.6 in a boolean in Physical -> 1, which value-plan writes as [true, 1], where raw 0.6 is refused (not a valid bool); 1,5 typed is not a number, pasted reads 1.5 |
| M5 | CONFIRMED | Minor -> Minor | - | verify-3-4/p3/m5_label.txt, p3/m5.txt | reproduced: unitLabel of a rename of a unit spelled a plus 60 emoji is cut at 119 code units through a pair (a lone \ud83d before the ellipsis); a valid settle edit posted with it answers 400 Invalid JSON: lone leading surrogate, the same edit with the label cut by code point 200 |
| M6 | CONFIRMED | Minor -> Minor | - | read off gui/src/lib/objectValues.ts:94-97 against src/ddd/object_values.py:317,325; lib/projectTypes.ts:5-9 against components/TypePanelView.tsx:52-56; lib/declarations.ts:7-11 against components/DeclarePanelView.tsx:43-47 | confirmed as text: the read-only sentences are object_values.py's two refusals word for word, KIND_WORDS and the scope words are each written twice on the page with a comment saying so; all agree today and nothing pins them across the line |
| M7 | CONFIRMED | Minor -> Minor | - | verify-3-4/p3/m7_types.txt; read off gui/src/api/types.ts:1-4, screens/FindingsPage.tsx:205 | confirmed with a smaller count: 133 generated names, 90 re-exported, 43 not, and nothing fails; 12 re-exports imported by no file by my count, not 18; FindingsPage invalidates [state], a key no useQuery has (the state comes by the long poll); GET /api/dictionary and GET /api/checks are in ROUTES with no client in the page |
| M8 | CONFIRMED | Minor -> Minor | - | verify-3-4/p3/paste_browser.txt | reproduced in Edge: the 10ms raster's Cycle emptied is refused ("" is not a cycle ... which no value set here can do), no Apply; KNOWN holds (2026-09-28-gui-rasters.md:858-870, What was left open) |
| M9 | CONFIRMED | Minor -> Minor | - | verify-3-4/p3/m9.txt | reproduced: producer max 9007199254740993, reader max 9007199254740992: ddd check error[definition-mismatch], exit 1; same_value maps both to [0.0, 9007199254740992.0]; GET /api/variable's limits row disagrees false with one value for A and B; settling on the producer's range plans no change |
| M10 | CONFIRMED | Minor -> Minor | - | verify-3-4/p3/m10.txt; read off gui/src/lib/shared.ts:9-11, screens/SectionPanel.tsx:115, .github/workflows/ci.yml:230-231 | measured with my own patterns: 149 planning citations in 50 production files, 195 spec citations, lib 40 % comment lines; shared.ts:9 and SectionPanel.tsx:115 say no gate executes a .tsx where ci.yml's journeys run the compiled pages |

No candidate of pass 3 is refuted or left plausible. One grade changes, and five confirmations
carry corrections.

Every run was mine. The project was a probe of my own, copied fresh for each run (`verify-3-4/p3/proj`,
`proj_i3`). The server was my own `ddd gui` on 127.0.0.1. The page ran in headless Edge, through
Playwright imported from my own copy of `gui/` (`verify-3-4/w/gui`), which has its own `node_modules`;
the baseline there is tsc 0 errors and vitest 959 of 959. Every mutation was made in that copy and
restored, and each restore was compared byte for byte with the tree (`p3/mutate.txt`). The tree was
not written.

**I8, confirmed with a narrower trigger, lowered from Important to Minor.** The refusal is real
(`p3/paste_browser.txt`):
- A 100 by 100 table of five-digit counts is refused, needing 80,028 characters of address; 128 by
  128 needs 96,462.
- Asked of the server straight, it answers 414.

But the bound comes much later than the pass, the client's comment (`client.ts:388-393`) and the
paste design (`2026-09-24-gui-paste-design.md:170`, "A 64×64 `float32` map is over that line") put
it:
- An 80 by 80 table of whole counts plans.
- 40 by 40 and 56 by 56 `float32` maps at factor 0.1, pasted as two-decimal physical values, plan in
  the real page (`p3/paste_float_browser.txt`).
- By the page's own `rawOf`, a 64 by 64 one needs 50,203 characters, and refusal starts near 70 by
  70 (`p3/paste_float_lengths.txt`). Random 64 by 64 maps of one- to three-decimal values at factors
  0.1, 0.01 and 0.5 need at most 54,916 (`p3/paste_float_random.txt`). Pass 3's own transcript planned
  a 64 by 64 too.

What remains is tables of roughly 5,000 to 10,000 counts and more. They are refused before anything
is sent, in a sentence naming the object, and can still be set cell by cell. That is a rare table
size and a stated limit, so Minor. The structural point, a server constant carried by the page,
stands as written. One detail the paste design itself gets wrong is its 64 by 64 example.

**C1, confirmed with one correction, still Critical.** The trigger reproduces end to end in the real
page (`p3/c1_browser.txt`) and over HTTP (`p3/c1_http.txt`). A `uint64` block whose file holds
`[9007199254740993, 18446744073709551615, 7]` comes over the wire as
`[[9007199254740992.0, 1.8446744073709552e+19, 7.0]]` (`contract.py:1447`, `rows: tuple[tuple[float, ...], ...]`),
and the grid shows `9007199254740992` and `18446744073709552000`. Typing `0x8000000000000001` offers
"Sets element 1 of big to 9223372036854776000", and Apply writes `9223372036854776000`, which is
`0x80000000000000c0`. Typing `9007199254740993` writes `...992`. A pasted row `...993, ...995, ...997`
plans `...992, ...996, ...996`. Typing the file's own `2^64-1` is refused as "18446744073709552000 does not
fit into uint64". The cause is on both sides: the page's `Number` (`objectValues.ts:105`), and
`client.ts:366`, which sends `String(raw)`, while the server's `_number` (`gui/api.py:2386-2406`) keeps
whole numbers exact through `json.loads`. So the server writes exactly the wrong number the page sent.
I looked for a guard (`isSafeInteger`, `MAX_SAFE_INTEGER`, `BigInt` in `gui/src`) and found none, and no
GUI test holds a value past 2^53. The correction: "without a word" is a little strong. The preview
sentence and its hunk show the number about to be stored, so a careful reader can see that
`...992` is not what they typed. Nothing marks the difference, though, and a decimal shown for a hex mask
cannot be checked by eye. It stays Critical because the GUI writes a value nobody typed into a
description file, from which the C and the a2l are generated, with no refusal.

**I3, confirmed with a narrower third trigger.** In Edge (`p3/i3_browser.txt`):
- `sblock`, a `value_block` naming the scalar type `Speed_t` with `dimensions [4]`, has no Shape
  button, although `GET /api/values` answers it (200, shape `[4]`, unit `rpm`, a file to write). A
  value-plan on it writes `[9, 2, 3, 4]` correctly (`p3/misc_http.txt`).
- The Unit cell of `sblock` and of the measurement `smeas` reads `none`, where `GET /api/variable`
  answers `rpm`.

The third trigger, a curve naming a structure that has the button and gets a grid answering 404, is
real. That declaration, though, is itself a `type-kind` error of the analysis, so it arises only in a
project that already fails `ddd check`. The first two are on an ordinary project, as
`docs/file_formats/types.rst:193-200` describes one.

**M4, confirmed with a smaller share.** `rounded(1234567890.125)` reads `1234567890.13` on the page and
`round_physical` gives `1234567890.12` (`p3/m4.txt`). Of 20,000 random values of 13 significant digits,
15 read differently, far fewer than the pass's 2,321 of 60,000. The share depends on how many exact ties
the sample holds, and the divergence is display only. The writing half is real:
- `rawOf` rounds 2.5 to 3 and -2.5 to -2.
- 0.6 typed into a boolean block in Physical becomes 1, which the server writes as `[true, 1]`. The
  same 0.6 asked in raw is refused, "0.6 is not a valid bool" (`p3/misc_http.txt`).

**M7, confirmed with a smaller count.** Of 133 generated names, 90 are re-exported and 43 are not, and
nothing fails (`p3/m7_types.txt`). That makes `types.ts:1-4`'s "fails the build" untrue. I count 12
re-exports that no file imports, not 18. The other three parts hold:
- `FindingsPage.tsx:205` invalidates `["state"]`, which no `useQuery` uses.
- `GET /api/dictionary` and `GET /api/checks` are in `ROUTES` with no client.
- An undo uses one predicate, and each screen keeps its own invalidation list.

**M10, confirmed with slightly different counts.** My patterns find 149 planning citations in 50
production files and 195 spec citations, against the pass's 145 in 51 and 184. 40 % of `lib`'s
non-blank lines are comments (`p3/m10.txt`). Two of the cited sentences are untrue:
- `lib/shared.ts:9-11` says ".tsx is executed by no gate in this repo".
- `SectionPanel.tsx:115` says "nothing in this repo executes a .tsx file under a gate".

`ci.yml:229-231` runs the journeys over the compiled pages, so both overstate it.

Two points about whether the KNOWN tags hold. I1's KNOWN is a design decision rather than a left-open
item: spec `2026-09-20-gui-other-keys-design.md:105-108` makes the page the guard on purpose. I6's
"KNOWN in part" holds:
- `2026-09-28-gui-rasters.md:872-876` leaves the non-exhaustive vocabulary chains open.
- `2026-10-08-gui-journeys-every-action.md:1640-1643` leaves the panels' different refusals and the
  inline stale test open.

A fourth vocabulary tried in my copy (`p3/fourth_vocabulary.txt`) stops `tsc` only at
`SHARED_VOCABULARIES`, as recorded. After that, only vitest's own pin of that literal list notices it,
not the four chains in `SharedPage`, `SharedAdd` and `SharedAddView`.

```verdicts
3|C1|CONFIRMED|Critical|Critical|-|reproduced in Edge and over HTTP: init [9007199254740993, 18446744073709551615, 7] is answered [9007199254740992.0, 1.8446744073709552e+19, 7.0] and shown 9007199254740992 and 18446744073709552000; typed 0x8000000000000001 writes 9223372036854776000 = 0x80000000000000c0; typed ...993 writes ...992; a pasted row plans ...992, ...996, ...996; typed 2^64-1 refused as 18446744073709552000; correction: the preview sentence names the stored number, nothing says it differs from what was typed
3|I1|CONFIRMED|Important|Important|-|reproduced: settle writes datatype uint7, unit 5, factor 0, size 0, dimensions "N", limits 10..1 and type-plan factor 0, uint7, limits 10..1, each applied and each file then fails schema, while value-plan refuses 70000 and 1.5 in uint16 and constant-plan refuses 3 of 3; in Edge the limits row of a uint64 stating 2^64-1 opens on Max 18446744073709552000, will change, Apply writes it and a.ddd.json fails schema (does not fit 64 bits); KNOWN holds as a design (spec 2026-09-20 4.2:105-108); related to 2:I3, not the same defect
3|I2|CONFIRMED|Important|Important|-|reproduced in Edge: Min 0 and Max 100 typed on nolim (two declarations, none stating limits) and on plain (one declaration) read Nothing to change, no Apply, file unchanged; GET /api/settle answers 200 with no changes; lsp/edits.py:549 skips any declaration stating none; spec 5.2's field and declarations.ts:36 promise it; no plan leaves it open, no journey covers it
3|I3|CONFIRMED|Important|Important|-|reproduced in Edge: a value_block naming the scalar type Speed_t with dimensions [4] has no Shape button while GET /api/values answers 200, shape [4], unit rpm, file set; its Unit cell and a measurement naming Speed_t read none where GET /api/variable says rpm; a curve naming a structure has the button and the grid answers 404 (that declaration is itself a type-kind error)
3|I4|CONFIRMED|Important|Important|-|my copy: every kind (10 properties) or interface renamed in generated/component.ts passes tsc 0 and vitest 959/959, a renamed component (the one read through the type, ComponentPage.tsx:209) fails tsc; only generated/component (formats.ts) and generated/sections (shared.ts) of the eight file-format modules are imported
3|I5|CONFIRMED|Important|Important|-|my copy: FindingRoute.kind gaining widget, and FindingsQuery gaining a parameter, each pass tsc 0 and vitest 959/959; routeOf's last line sends any other kind to the component page (findings.ts:256); findingsQuery lists its five by hand (client.ts:184-193); /api/graph misspelt passes tsc and fails 1 vitest of client.test.ts's own list; 21 code comparisons by string, no error schema in the contract; conversion kinds today are four and agree
3|I6|CONFIRMED|Important|Important|-|my own measure: screens Constant/Section/Raster 0.84 to 0.86 alike, UnitPanel 0.69 to 0.71, views 0.80 to 0.81; Outcome defined in four views, each saying it mirrors another; refusalOf identical in UnitPanel and TypePanel, imported from UnitPanel by eight screens; the stale test 13 times in ten screens, isStale used by one; a fourth vocabulary in my copy: tsc stops at SHARED_VOCABULARIES only, then 0; the recorded refusal divergence holds (P19b-24, P19c-6); KNOWN in part holds
3|I7|CONFIRMED|Important|Important|-|eight plans carry the rule as a Global Constraint; screens/ 3,622 code lines, 119 useState, 596 conditionals by my count, no unit test, vitest's coverage list api, lib, state; SHAPED_BY_KIND losing map and refusalOf inverted each pass tsc 0 and vitest 959/959 in my copy; KNOWN holds (2026-09-20-gui-other-keys.md:2980 Left open; 2026-10-08 plan:1643)
3|I8|CONFIRMED|Important|Minor|-|reproduced in Edge with a narrower trigger: 100x100 five digit counts (80028 characters) and 128x128 are refused, the server answers 414 when asked straight, but 80x80 whole counts and 40x40 and 56x56 float32 maps at factor 0.1 plan, and by the page's own arithmetic a 64x64 one needs 50203 characters and random 1 to 3 decimal 64x64 maps at factors 0.1, 0.01, 0.5 at most 54916, refusal starting near 70x70; lowered: a rare table size, refused in a sentence naming it, cell by cell still open; KNOWN by design holds (2026-09-24-gui-paste-design.md:165-172)
3|M1|CONFIRMED|Minor|Minor|-|measured: lib/units.ts has the highest fan-in of lib (25), baseName, consequence and shownChanges 12 importers each; planEdit goes shared -> projectUnits -> units.editOf and findings.fixEdit is editOf's body again; nonEmpty and owner twice; VariablePanelView imports type Offer from UnitPanelView
3|M2|CONFIRMED|Minor|Minor|-|measured with my own graph: folder cycles api<->state (client.ts imports ownEdits from state/edits, revisions.ts imports client) and app<->screens (28 imports into app), ui/Table.tsx takes ROW_HEIGHT from lib/findingsWindow, no file cycle; a lib -> screens re-export in my copy passes tsc, vitest 959/959 and biome
3|M3|CONFIRMED|Minor|Minor|-|reproduced on Windows: Add of extra\x3.ddd.json and of EXTRA/X1.DDD.JSON, the page's filesHoldOf holds keys .../extra\x3.ddd.json and .../EXTRA/X1.DDD.JSON where GET /api/files lists .../extra/x3.ddd.json and .../extra/x1.ddd.json; extra/x1.ddd.json agrees (control); transient, until the list answers
3|M4|CONFIRMED|Minor|Minor|-|reproduced: rounded(1234567890.125) reads 1234567890.13, round_physical 1234567890.12 (15 of 20,000 random 13 digit values differ, a smaller share than the pass's sample); rawOf 2.5 -> 3, -2.5 -> -2; 0.6 in a boolean in Physical -> 1, which value-plan writes as [true, 1], where raw 0.6 is refused (not a valid bool); 1,5 typed is not a number, pasted reads 1.5
3|M5|CONFIRMED|Minor|Minor|-|reproduced: unitLabel of a rename of a unit spelled a plus 60 emoji is cut at 119 code units through a pair (a lone \ud83d before the ellipsis); a valid settle edit posted with it answers 400 Invalid JSON: lone leading surrogate, the same edit with the label cut by code point 200
3|M6|CONFIRMED|Minor|Minor|-|confirmed as text: the read-only sentences are object_values.py's two refusals word for word, KIND_WORDS and the scope words are each written twice on the page with a comment saying so; all agree today and nothing pins them across the line
3|M7|CONFIRMED|Minor|Minor|-|confirmed with a smaller count: 133 generated names, 90 re-exported, 43 not, and nothing fails; 12 re-exports imported by no file by my count, not 18; FindingsPage invalidates [state], a key no useQuery has (the state comes by the long poll); GET /api/dictionary and GET /api/checks are in ROUTES with no client in the page
3|M8|CONFIRMED|Minor|Minor|-|reproduced in Edge: the 10ms raster's Cycle emptied is refused ("" is not a cycle ... which no value set here can do), no Apply; KNOWN holds (2026-09-28-gui-rasters.md:858-870, What was left open)
3|M9|CONFIRMED|Minor|Minor|-|reproduced: producer max 9007199254740993, reader max 9007199254740992: ddd check error[definition-mismatch], exit 1; same_value maps both to [0.0, 9007199254740992.0]; GET /api/variable's limits row disagrees false with one value for A and B; settling on the producer's range plans no change
3|M10|CONFIRMED|Minor|Minor|-|measured with my own patterns: 149 planning citations in 50 production files, 195 spec citations, lib 40 % comment lines; shared.ts:9 and SectionPanel.tsx:115 say no gate executes a .tsx where ci.yml's journeys run the compiled pages
```
