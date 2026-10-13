# The GUI's journeys for every reader action

- **Part:** 19b of the GUI work, in milestone 8: the second half of end-to-end breadth (part 19).
  After it come the user guide (part 20), the independent review, the pilot, and removing *preview*.
- **Status:** design approved section by section; to be planned
- **Depends on:** part 19a (pull request #81, merged into master as `ff9954e`)

Part 19 is milestone 8's end-to-end breadth. The maintainer chose its widest reading: every action a
reader can take in the page has a journey, or a recorded reason it has none. 19a made the 94
journeys there are reliable on Ubuntu with Chromium, Windows with Chromium and Windows with Edge.
This part writes a journey for each action and state that has none, on that base.

## 1 The problem

- **The journeys are the screens' only test.** Vitest covers `src/api`, `src/lib` and `src/state`
  alone. No screen, no `*View.tsx` component and no `App.tsx` has a unit test: what no journey
  drives is not tested at all.
- **About 50 reader actions and states have no journey.** Part 19's survey of every screen against
  every journey (2026-10-07) found them, mostly on the thinnest screens:
  - the Shared files tab, where editing, renaming or removing an existing constant, section or
    raster has none;
  - the Compare tab, whose refused baselines were only ever checked by hand;
  - the start page, the canvas's Fit, search and hover, and the Types tab's keys;
  - on most tabs, an Apply refused as out of date, an entry gone, and the error banners.
- **A request can fail on its own on Windows.** CI saw `net::ERR_NO_BUFFER_SPACE` twice, both times
  on the Edge leg:
  - the sign-in's `POST /open` in hunt 37710529902, which 19a now sends once more (P19a-9);
  - the page's stylesheet in run 37760106344. The page was drawn unstyled, the declarations table
    drew only the rows near the viewport, and `skeleton.spec.ts:81` failed (P19a-23). Its trace,
    downloaded with the maintainer's leave, shows the stylesheet's request refused within a
    millisecond.

  Every other GET that fails that way today reads as the server stopped: `request()` throws
  `ServerUnreachable` on any rejected fetch.

## 2 What was read

- **The survey** of 2026-10-07, at master `290fd9a`: every screen, every `*View.tsx` component,
  `App.tsx`, `lib/route.ts`, the server's route table, and the 89 journeys of that day. Its rows
  are the starting inventory below (§4).
- **What 19a changed since:** the Files tab's option C and its three journeys, `localhost.spec.ts`
  and `mapped.spec.ts` (94 journeys now), the sign-in sent once more, and `useRoute`'s `arrived`.
- **The trace of run 37760106344's Edge failure:**
  - the network log: `GET /assets/index-*.css` failed `net::ERR_NO_BUFFER_SPACE`; every other
    request answered;
  - the last frame: the page in the browser's default style, the panel below the table, and the
    document scrolled to the unit picker;
  - the aria snapshot: the table drew ValueA, kept as the selected row, then the last five rows
    alone.
- **The API client** (`gui/src/api/client.ts`): `request()` sends once, and a rejected fetch that
  is not an abort becomes `ServerUnreachable`. React Query asks with `retry: false`
  (`gui/src/main.tsx`).
- **The page's stylesheets:** `/pressable.css`, linked in `gui/index.html`, and the stylesheet Vite
  builds into `/assets/`.

## 3 The answer

- **An inventory of every reader action and state,** committed in the plan: each row names its
  journey, or the ruling that says why none.
- **A journey for each row that has none,** written screen by screen, each shown to fail when the
  behaviour it names is broken.
- **The page sends its own loads once more** when the network fails them: its stylesheets, and any
  GET of the API that got no answer at all.
- **Bugs the journeys find** are fixed when the fix stays within one screen, component or library
  function, and recorded for the maintainer otherwise.

## 4 The inventory

- **What counts.** Every action a reader can take and every state a reader can meet:
  - every press, edit, key and hover;
  - every refusal the server gives: out of date, refused, gone, unreadable;
  - every error banner and loading state.

  Not counted: the two routes the page never calls (`/api/dictionary` and `/api/checks`), and redo,
  which the page does not have.
- **Where it lives.** One table in the plan: screen, action, and the journey that covers it, or the
  ruling saying why none. No new living document.
- **Done means** every row names a journey or a reason. A reason is one of two things:
  - a bug left for the maintainer;
  - an action no journey can reach, stated with what was tried.
- **The starting rows,** from the survey, to be checked against today's tree by the first task:
  - **The start page:** no project found; build records not used; the projects list failing; opening
    a project failing.
  - **The app around every page:** the signed-out view; the failure banner a broken answer raises.
  - **The canvas:** Fit; the module search and its Enter; hovering a module; the no-dictionary
    banner; the undeclared-variable banner reached from an arrow; the drawing and layout states.
  - **The components table:** its summary line while the findings update.
  - **Units:** the adopt refused.
  - **Types:** a type's limits; its other keys, picked or stated as nothing; its description; a type
    gone, or its file half-written.
  - **Shared files:**
    - "Declare an entry" on a project with none, and the blank form it opens;
    - the add form refused;
    - a constant's value and description saved, renamed, removed;
    - a section's access, alignment and description saved, renamed, removed;
    - a raster's event, cycle and description saved, renamed, removed;
    - a constant's and a raster's "Used by" rows followed;
    - an Apply refused as out of date;
    - an entry gone, or its file half-written;
    - the unreadable and untold banners.
  - **Files:** New file, Add or Remove refused as out of date; the findings a file would bring; the
    list failing.
  - **Findings:** a fix refused; a finding no longer reported; the page of findings failing.
  - **Compare:** a row selected opens its finding; that finding's route followed; the renamed
    objects; a baseline not found, not json, of the wrong shape, or outside the root; the busy
    state.
  - **A component:** a dimension removed; a finding's link to a variable of the same file opened in
    place; the file failing to load or to match its schema; a declaration refused as out of date.
  - **Values:** an Apply refused as out of date.
  - **The network (§6):** a stylesheet failed once; a GET failed once.
- **Carried from 19a:**
  - `files.spec.ts`'s `waitForResponse`, replaced by `route.fetch()`, an assertion that the entry is
    gone, then `route.fulfill()`;
  - `skeleton.spec.ts:81`, whose cause §6 removes.

## 5 How each kind of state is reached

- **Successful actions** are driven as a reader drives them: a press, typing, a key, a hover. A
  journey waits only on what the reader sees, or on `expect.poll`.
- **Refusals:**
  - **out of date:** the change on disk is made unseen with the existing helpers (`writeUnseen`,
    `driftMaxUnseen`), so the refusal holds until the journey looks;
  - **refused:** the input the server refuses, such as a name already taken, a value out of range,
    or a baseline that is not json;
  - **gone or unreadable:** a real change the watcher sees, such as an entry deleted or a file left
    half-written.
- **Edge projects** (no shared entry, no dictionary, no project at all, a build record not used): an
  example copied into the test's own directory and changed there, as the fixtures already copy one.
  A new example enters the repository only if no change to a copy can make the case.
- **Error banners:** Playwright makes that one request fail, and the server's code is not touched:
  - an HTTP error (`route.fulfill` with a `500`) where the server would answer one;
  - a network failure (`route.abort`) where it could not answer.

  Since §6 sends a GET once more, a network banner's journey fails its request twice.
- **Loading states:** the request is held by a route until the journey has seen the state, then let
  through, as `files.spec.ts` already holds one.
- **No journey is vacuous.** Each journey's key assertion is shown to fail under one named change to
  the page or the server. The change is made in a scratch copy, as in 19a, never in the checkout the
  two `ddd gui` containers serve. A journey that proves a fix is red before the fix.
- **The house rules hold:**
  - no retries in Playwright, and no skip;
  - no `waitForTimeout` and no `waitForResponse` beyond the two recorded exceptions (P19a-8, and
    `hostile.spec.ts:62`);
  - the journeys run after a build, never alongside the Docker screenshots.

## 6 The page sends its loads once more

- **The stylesheets.** When one of the page's own stylesheets failed to load, the page asks for it
  once more before it draws. One that fails twice leaves the page as it is today.
- **The API's GETs.** `request()` sends a GET once more when the fetch itself is rejected, with no
  HTTP answer. It never resends:
  - after any HTTP answer, a refusal included;
  - a `POST`, whose effect may have happened (the sign-in's own retry stays as 19a made it);
  - an abort, such as the long poll's own.

  A second rejection is `ServerUnreachable`, as one is today.
- **Where it lives.** The GET's rule is `request()`'s, under Vitest at 100 %. The stylesheets' rule
  is a function in `src/lib`, also under Vitest, called before the page renders.
- **The journeys:**
  - a stylesheet failed once (`route.abort` on its first request): the page is drawn styled;
  - a GET failed once: the page carries on, with no banner;
  - a GET failed twice: the page says the server cannot be reached, as it does today.

## 7 The work

One part, cut into tasks by screen. Each task:
- checks its screen's rows of the inventory against the code;
- writes the journeys, and any fixture or helper they need;
- fixes the contained bugs its journeys find, red first;
- records the others as rulings for the maintainer.

In order:
1. **The inventory and the groundwork:**
   - the survey redone against today's tree, and committed as the plan's table;
   - two helpers: one failing a request (an HTTP error or a network failure, once or always), one
     making an edge project out of a copied example;
   - `files.spec.ts`'s `waitForResponse` replaced.
2. **The page sends its loads once more** (§6).
3. **The start page and the app around every page.**
4. **The canvas.**
5. **Units and Types.**
6. **Shared files,** the largest group.
7. **Files and Findings.**
8. **Compare.**
9. **A component and its values.**
10. **The controller's:** the final hunt, the figures, the milestone gate and the close-out.

## 8 CI and checks

- **The legs.** CI keeps its three legs, and their timeouts. The journeys take 3 to 4 minutes a leg
  today. About 50 more add roughly 2 minutes to a pass, and about 10 to a hunt.
- **Windows.** Each task's Windows proof is a full run (`-f repeat=1`). Only the final hunt must be
  clean on all three legs.
- **The gates:** pytest at 100 % line and branch, ruff, format, mypy, the schemas, lint, typecheck,
  Vitest at 100 % on all four metrics, the build, Ladle, the screenshots in Docker, the docs under
  `-W`, and every journey.
- **Reviews.** Each task gets its own review, then a final whole-branch review on opus, one fix
  wave, and the pull request.
- **Screenshots.** Where a fix changes what the page shows, its Ladle reference changes and the pull
  request carries it.

## 9 Documentation

- **The CHANGELOG** gets an entry for the page sending its loads once more, and one for each
  contained bug fixed that a reader would notice.
- **The developer documentation** names the two new helpers beside the fixtures it already lists.
- **The plan's *Figures*:** the inventory's counts before and after; the final hunt on each leg; the
  journeys' time per leg before and after.

## 10 Risks

- **The journeys may find more bugs than the plan can fix.** The second answer below caps it: only a
  fix within one screen, component or library function is made here.
- **A state may have no honest way to be reached.** Its row then names what was tried, and stays a
  reason, never a journey that asserts nothing.
- **About 50 more journeys lengthen every run.** §8's estimate is checked against the first full
  run, and the timeouts are raised only if a pass comes near them.
- **Sending a GET once more could hide a server that is really gone.** It costs one more refused
  connect: the second rejection still shows the server unreachable.

## 11 Out of scope

- **Firefox, Safari and macOS.**
- **The user guide** (part 20).
- **A fix that needs a design decision.** It is recorded for the maintainer.
- **P19a-7's question,** how long a refusal held stale shows, unless the maintainer answers it.

## 12 Decisions taken

The maintainer's answers while this was designed:
- **Every action and every state counts,** error banners included, reached by failing one request in
  Playwright where no real condition can produce them.
- **Bugs:** a fix contained in one screen, component or library function is made in this part, red
  first; the rest are recorded for the maintainer.
- **One part, a task per screen,** with a committed inventory and one final hunt.
- **The page sends its own loads once more** on a network failure: its stylesheets, and a GET that
  got no answer.
- **The trace of run 37760106344's Edge failure** may be downloaded. It was, and §1 and §2 record
  what it shows.

Taken in the design:
- **The inventory lives in the plan,** not in a new document.
- **Each journey is shown to fail** under one named change, in a scratch copy.
- **Banners from a network failure** fail their request twice, since §6 recovers one failure.
