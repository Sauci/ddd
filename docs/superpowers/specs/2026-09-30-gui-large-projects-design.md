# Large projects in the GUI

- **Part:** 17 of the GUI work, and the first of milestone 8
- **Status:** design approved section by section; to be planned
- **Depends on:** part 16 (the Files tab, pull request #73) - master is merged into this branch once it
  lands, rather than this branch stacking on it

Milestone 8 of `2026-09-17-web-gui-design.md` §5 is *"Hardening (large projects, security review,
end-to-end breadth), the user guide, an independent review, the pilot, removing preview"*. Milestones
1 to 7 are done. This part is the first of milestone 8: it makes the browser interface usable on
projects of tens of thousands of declarations and more, and leaves behind the means to show it stays so.

## 1 Milestone 8, in parts

| Part | What | Why in this order |
| --- | --- | --- |
| 17 | **Large projects** (this spec) | Evidence first; it may change screens, so it comes before the guide |
| 18 | **Security review**: the server's whole surface - token, host and origin checks, the content security policy, served directories, edits, plugins, the file endpoints - with fixes | May change server behaviour the later parts then lock |
| 19 | **End-to-end breadth**: every screen and action mapped to the journeys that drive it, the gaps filled, and a run on Windows with Edge | Locks behaviour before it is documented |
| 20 | **The user guide**: every screen, with its screenshots, in the documentation | Needs the final screens |
| 21 | **Removing *preview***: the command's line, `GET /api/session`'s `preview`, the README and the CHANGELOG | Last, after the pilot |
| - | **The independent review and the pilot** | Organised by the maintainer with Simulink developers; what they find is fixed between parts |

## 2 What was measured

Real projects grow past 35,000 declarations, by an amount nobody can fix in advance, and they mix
many small components with few large ones. The estimate behind the GUI measured a re-check of 49 ms,
569 ms and 4,002 ms for 720, 7,080 and 35,200 declarations (`2026-09-17-web-gui-design.md` §9), but
the GUI had never been measured on a project of that size.

It was measured for this design, on the Linux development PC, one run of each, with the server driven
in process (`ddd.gui.api.Api` over a `ddd.gui.session.Session`) and the page in the built-in browser
against a running `ddd gui`. The projects were generated: `N / 30` components of 30 outputs each
("many"), or 30 components of `N / 30` outputs ("large"), every component but the first also reading
five outputs of the one before it. Their declarations carry no id and most outputs have no reader, so
each project carries about two findings per declaration - a `missing-id` note and an `unused-output`
warning. A real project with ids and readers has far fewer; one half-way through a migration can still
have thousands, which is why the findings-heavy case is kept.

| | 9,000 declarations | 36,000 | 72,000 |
| --- | --- | --- | --- |
| Opening: one analysis | 354 ms | 1,511 ms | 3,153 ms |
| `GET /api/state`, built | 443 ms | 1,796 ms | 3,571 ms |
| its body: every finding | 5.4 MB | 21.7 MB | 43.5 MB |
| `POST /api/edit` of one unit: waits for an analysis | 366 ms | 1,560 ms | 3,183 ms |
| findings | 16,505 | 66,005 | 132,005 |

The "large" shape at 36,000 declarations measured within 11 % of the "many" one: 1,348 ms to
analyse, 1,688 ms to build the state, 22.9 MB. Every cost grows linearly - about 40 to 44
microseconds a declaration to analyse, and about 27 microseconds and 330 bytes a finding for the state.

At 36,000 declarations, in the "many" shape:

- **The page.** The graph had drawn its 1,200 components when first looked at, 3.4 s after the page
  was opened; the state reply alone took 2.1 s to arrive, 27 MB as transferred. The graph was fetched
  twice. **Opening the Findings tab froze the page for more than two minutes**, drawing a row for
  every one of 66,005 findings: no table of the page is virtualised.
- **Per request.** A variable's panel (`GET /api/variable`) took 1,845 ms for a 0.39 MB answer: it
  scans every finding of the revision to keep the variable's own. `GET /api/units` took 768 ms and
  `GET /api/types` 626 ms for replies under 5 kB. `GET /api/files` took 24 ms.
- **An edit that creates a file analyses twice.** `Session._publish` stamps a file with no stamp from
  before as unknown, so that a save racing the analysis is caught; a file the edit itself created is
  such a file, and the next poll analyses the whole project again (part 16's measurement saw two
  revisions after every New file and Add).

`GET /api/dictionary` answered 19.8 MB in 261 ms, and no screen asks for it.

## 3 What this part delivers, and its budgets

The analysis itself is not changed: `ddd check` and the GUI keep one engine, and an analysis of
100,000 declarations will take about 4.4 s at today's rate. What changes is that **the page never
waits for it**. An edit shows at once; its findings follow when the analysis lands, and the page says
they are updating until then.

The budgets, at every size up to 100,000 declarations, in both shapes, clean and findings-heavy:

| Measure | Budget |
| --- | --- |
| The page answering after a project is opened: its shell, the project's name, an analysing state | under 1 s |
| The first analysed screen | within one analysis plus 1 s |
| Any tab or panel drawing, once analysed | under 1 s |
| Typing or scrolling stalling | never over 100 ms |
| An Apply's own change showing | under 500 ms |
| The findings current after an edit | within one analysis plus 1 s, the page saying "updating" until then |

## 4 Measuring

- **A committed generator** under `tools/`, deterministic, building a project of `N` declarations in
  the "many", "large" or mixed shape. Its declarations take ids, units and readers, so that a project
  can be clean as a real one is; an option adds the findings §2's projects carried - declarations
  without an id, outputs nobody reads - at a density it is given.
- **A committed benchmark**, in two halves. The server half times opening, one analysis, each
  endpoint's answer and its size, and an edit's round trip, in process. The page half is a Playwright
  script against a running `ddd gui`: the page answering after opening, the first analysed screen,
  each tab's first drawing, typing in a panel, scrolling a long table, an Apply until its own change
  shows, and an Apply until the findings are current.
- **Sizes** 10,000, 35,000 and 100,000 declarations, each shape, clean and findings-heavy. The
  benchmark runs by hand - it is slow and the machine's own - not in CI. The part's plan and its pull
  request record its figures before and after, the machine and the method with them.

## 5 The server

- **An edit answers once its files are written.** `Session.edit` and `Session.undo` confine, check
  fingerprints, write and record the undo step as today, and answer with the fingerprints they wrote;
  they no longer analyse. One background analyser does, taking requests from edits, undos and the file
  poll alike and merging them: edits landing while an analysis runs lead to one more analysis of the
  disk as it then stands, never to a queue. Each revision records the last edit it includes, and
  `POST /api/edit` answers the edit's own number, so the page knows when its change has been analysed.
- **The state reply stops carrying findings.** `GET /api/state` answers the revision, the project, the
  files with their counts, the undo entry, the counts by severity and an `analysing` flag; its long
  poll wakes on a change of `analysing` as well as on a new revision.
- **`GET /api/findings`** answers one revision's findings a page at a time - `offset` and `limit` -
  filtered by severity, file or check, sorted as the Findings tab sorts them, with how many there are
  in all. A component's page asks for its own file's.
- **A revision's answers are built once.** What is derived from a revision - the state's body, each
  page of findings with its routes, the graph, the tabs' rows - is cached for that revision. What a
  per-name request needs is indexed once per revision: the findings by file and by the name they are
  about, which a variable's panel reads rather than scanning every finding.
- **No second analysis after a file is created.** A file an edit created is stamped from the edit's
  own write; a file the edit did not write keeps the unknown stamp, so a save racing the analysis is
  still caught.
- **A plan while an analysis is pending** is computed against the newest published revision, and
  never waits behind the analysis. The edit engine still refuses a write to a file changed since its
  plan read it. A plan the Files tab judges answers `stale` until the analysis lands, in the words it
  answers today.

## 6 The page

- **Long tables are virtualised** with React Aria's own `Virtualizer` and `TableLayout`: the Findings
  table, the component table, the project's file list, the vocabulary and Files tables, and a
  variable's keys. The document holds the rows in view and a margin. Which rows those are, and which
  page of findings to ask for, is decided in `gui/src/lib` under the Vitest gate; the `.tsx` draws.
- **The Findings tab pages through `GET /api/findings`** as it scrolls: the visible range and a
  margin, filtered on the server, its totals from the state. A component's page asks for its file's
  findings alone.
- **"Updating"** is shown on the findings counts and each panel's list of findings while the state
  says `analysing`, or while the page's own last edit is newer than the revision it holds. The fields
  and values an edit wrote show that edit at once.
- **The graph** is fetched once, draws only the nodes in view at large sizes, and has its layout
  measured by the benchmark; it moves off the main thread only if it misses the budget.
- **Typing never waits.** A panel's plan request is debounced, the delay decided in `lib` under test;
  a reply for text the reader has since typed past is dropped.

## 7 What can go wrong

- **An analysis failing in the background** - a plugin raising, or anything unforeseen - never kills
  the analyser and never leaves `analysing` set. The revision it makes carries the failure as a
  revision does today.
- **An edit or an undo during an analysis** is written at once; the analyser runs once more after, and
  the page learns from its own edit's number when its change is in.
- **A second window** learns of an edit made in the first from the state's long poll, `analysing`
  included.
- **Opening a project** answers within 1 s with the analysing state, and draws its first analysed
  screen when the first analysis lands.
- **The server stopping** during an analysis shows the stopped banner, as it does today.

## 8 Testing

- **Python**, at 100 % line and branch: the analyser deterministically, with no sleeping - analyses
  counted, so that merged edits and the one analysis after a created file are pinned; a failure during
  an analysis; `GET /api/findings`' pages, filters and order; each cache and index answering what the
  uncached computation answers.
- **The page**, at 100 % over `src/api`, `src/lib` and `src/state`: the range arithmetic, the debounce
  and the "updating" decision. New screenshot references for the updating state and a long virtualised
  table.
- **Journeys**: an edit showing at once and its findings arriving after, and the Findings tab scrolled
  on a findings-heavy generated project.
- **The benchmark**, before and after, its figures in the plan and the pull request.

## 9 Out of scope

- **Analysing only what changed.** The analysis stays the engine `ddd check` runs; if the benchmark
  shows the lag unbearable at sizes real projects reach, analysing incrementally is its own part.
- **Server-sent events** instead of the long poll (`2026-09-17-web-gui-design.md` §8). Paging removes
  the large replies the poll carried; the benchmark decides whether the poll itself shows.
- **`GET /api/dictionary`'s size.** No screen asks for it.
- **The benchmark in CI.** It is slow and the machine's own.

## 10 Decisions taken

The maintainer's answers while this was designed:

- Milestone 8 in the parts of §1, large projects first.
- The GUI must stay usable on projects past 35,000 declarations, by an amount not known in advance:
  measure to a ceiling and prefer what grows slowly.
- Large projects mix many small components with few large ones: the generator makes both.
- The page stays fast and the findings may lag; the analysis engine is not changed in this part.
- Approach: findings lagging by design, over keeping edits waiting and over pushing changes by
  server-sent events.
- The opening budget as §3 states it: the page answering within 1 s and the first analysed screen
  within one analysis plus 1 s - first proposed as a first screen within 3 s at every size, which no
  page drawing analysed content can meet at 100,000 declarations while the analysis is unchanged.
