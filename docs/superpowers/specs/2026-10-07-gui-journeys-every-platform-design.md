# The GUI's journeys on every platform

- **Part:** 19a of the GUI work, in milestone 8. It is the first half of end-to-end breadth (part 19).
  After it come 19b's journeys for every reader action, then the user guide (part 20), the independent
  review, the pilot, and removing *preview*.
- **Status:** design approved section by section; to be planned
- **Depends on:** part 18b (pull request #80, merged into master as `290fd9a`)

Part 19 is milestone 8's end-to-end breadth. The maintainer chose its widest reading: every action a
reader can take in the page has a journey, or a recorded reason it has none. It is cut in two:
- **19a, this part,** makes the 89 journeys there are reliable on the three platforms CI will run
  them on. It also closes four items earlier parts left for this point.
- **19b** then writes a journey for each action that has none, on that base.

## 1 The problem

- **The journeys are the screens' only test.** Vitest covers `src/api`, `src/lib` and `src/state`
  alone (`gui/vite.config.ts`). No screen, no `*View.tsx` component and no `App.tsx` has a unit test.
- **Nothing runs them in Edge.** CI runs them on Ubuntu and on Windows, both with Playwright's own
  Chromium. A pilot user on Windows most likely has Edge.
- **They are not reliable on Windows.** `gui (windows-latest)` has failed on journeys no branch had
  touched:
  - `keys.spec.ts`'s stale change: on master on 2026-09-28 (run 36444205637), and on part 17's branch
    on 2026-10-05 (run 37313217328);
  - `values.spec.ts:76`, the plot: in that same run on 2026-10-05;
  - `values.spec.ts:217`: once on part 18b's pull request on 2026-10-07 (run 37665957824), where the
    CurveA grid never appeared within the 60 s. It passed on the re-run, and in 10 runs of 10 on
    the Linux development PC pinned to one core.

  Earlier plans also record two flaky spots in `skeleton.spec.ts`: the canvas's arrow count, and a
  `page.waitForResponse` that `2026-09-26-gui-compare.md` says never to use in a journey.
- **CI has no timeouts.** On 2026-10-07 the Ubuntu gui job hung in
  `npx playwright install --with-deps chromium` for over 24 minutes, until the run was cancelled. The
  same step took 20 s on master's run before. Left alone, it could have held the run for up to
  GitHub's default of 360 minutes, and with it any re-run of the run's failed jobs.
- **Four items were left for this point:**
  - **P18-31.** A `POST` refused before its body is read is answered `Connection: close`, and the
    connection is closed with the body unread. On Windows that close is a reset, which can destroy
    the answer before the browser reads it.
  - **P18-12.** A project on a mapped drive. The rule behind it is tested on every leg: a network path
    is answered only under a directory `ddd gui` serves. But it has never met a real mapped drive,
    and was to be checked by hand on Windows.
  - **Part 18b's I-2.** `ddd gui` listens on IPv4 alone. A program listening on `[::1]` at the same
    port receives `http://localhost:<port>/…`, a pasted address's token included. Part 18b's final
    review measured this in Chrome 153, three times out of three.
  - **P18b-10.** A navigation that passes the gate opens the signed-in page at an address of its
    choosing. Opened on a Files row, the Remove panel asks its plan at once, and the plan
    re-analyses the project with its plugins.

## 2 What was read

- **A survey of every screen against every journey,** on 2026-10-07. It found:
  - about 49 reader actions with no journey, which are 19b's;
  - the timing-sensitive spots above;
  - the helper every click into a virtualised table goes through, `scrolledIntoView`
    (`gui/e2e/demo.ts:142-166`).
- **CI** (`.github/workflows/ci.yml`):
  - **Triggers:** a push to master, a pull request, and `workflow_dispatch`.
  - **The gui job:** a matrix of `ubuntu-latest` and `windows-latest`, with Python 3.12 and Node 24.
    It installs Playwright's Chromium, then runs `npm run e2e`.
  - **No job sets `timeout-minutes`.**
  - **The browser:** `gui/playwright.config.ts` passes `PLAYWRIGHT_CHANNEL` through as Playwright's
    `channel`.
- **The Windows runner image** `windows-2025-vs2026`, version 20260925.250, lists Microsoft Edge
  153.0.4234.48 and its driver among its software. The list says nothing of SMB.
- **The server** (`src/ddd/gui/server.py`):
  - `_send` closes a `POST`'s connection when its body was not read (`_body_read`).
  - `_body` refuses a length over `MAX_BODY` with `413` before reading anything.
  - `run` resolves `--host` with `AF_INET` alone, and `GuiServer` binds one socket.
- **The Files tab** (`gui/src/screens/FilesPage.tsx`):
  - `RemoveFile` asks `useFilesPlan` as soon as the panel mounts.
  - The selection is the route's `path`, set by `onPath` when a row is pressed.

## 3 The answer

- **CI runs the journeys on three legs:** Ubuntu with Chromium, Windows with Chromium, and Windows
  with Edge. Every job gets a timeout. An on-demand hunt repeats the journeys.
- **The flakes are measured, then fixed.** A hunt runs before anything is fixed. Each failure it finds
  is fixed at its cause, and a final hunt shows none left. Nothing is retried.
- **The server drains a refused `POST`'s body, and holds `[::1]` on its port.**
- **The Files tab's Remove panel asks its plan on arrival only for a row the reader chose within the
  page** (option C).
- **A runner maps a drive to itself,** and a journey runs `ddd gui` from it.

## 4 CI

- **Three journey legs.** The gui job's matrix becomes:
  - Ubuntu with Chromium;
  - Windows with Chromium;
  - Windows with Edge.

  The Edge leg sets `PLAYWRIGHT_CHANNEL=msedge` and installs no browser: Edge is the runner's own.
  Each job's name carries its browser, as in `gui (windows-latest, msedge)`, and so does the name of
  the report it uploads on failure. The wheel's build and its check stay on Ubuntu alone.
- **Timeouts.** Every job sets `timeout-minutes`, sized from recent runs with a generous margin. As a
  rough guide:
  - about 20 for the test legs;
  - about 30 for the gui legs;
  - less for lint and the extension.

  The Playwright install step gets a limit of its own, about 5 minutes, so that a stalled download
  fails in minutes.
- **The hunt.** The manual trigger gains an input, `repeat`, whose default is 1.
  - **Above 1,** the three gui legs run the journeys with `--repeat-each=<repeat>`, and every other
    job is skipped, the jobs that publish a development build to TestPyPI among them.
  - **It is started with** `gh workflow run ci.yml --ref <branch> -f repeat=5`, which needs the branch
    pushed before any pull request exists. The maintainer is asked before that push.
- **A pass and a hunt.** The ordinary single pass stays as it is. A hunt of 5 repeats is 445 runs of
  the 89 journeys on each leg.

## 5 The flakes

- **The baseline.** Once §4 is on the branch, one hunt runs the journeys exactly as they are on
  master. Each failure is recorded with its journey, its leg, how often, its error and its trace.
  The plan's *Figures* keeps the table.
- **The traces.** The maintainer allowed downloading the failed hunts' Playwright traces without
  asking each time. They are the report artifacts of this repository's own CI runs, about 1 MB each,
  saved to the session's scratchpad.
- **The known spots:**
  - `keys.spec.ts`'s stale change. Its helper `driftMaxUnseen` already retries a rename Windows
    refuses.
  - `skeleton.spec.ts`'s arrow count.
  - `skeleton.spec.ts`'s `page.waitForResponse`.
  - `values.spec.ts:76`, the plot.
  - `values.spec.ts:217`, the grid that never appeared.
- **Fixed at the cause.** Each of these, and whatever else the baseline finds, is fixed at its cause,
  from what its trace shows:
  - a wait on time, or on a response, becomes a wait on what the reader sees;
  - a click races nothing that is still scrolling.

  Each fix names its cause. No journey is retried, and Playwright's `retries` stays 0.
- **A flake that resists.** One that cannot be traced to its cause within the plan is recorded with its
  rate and its evidence, as a ruling. It stays visible in the pull request.
- **The final hunt** runs on the finished branch: 5 repeats on all three legs, with no failure.

## 6 The server

### 6.1 A refused `POST` drains its body

Every `POST` the server refuses before reading its body is concerned:
- a `Host` it does not answer (`421`);
- a target it cannot read (`400`);
- the gate's refusal (`403`);
- a page's path (`405`);
- the API without the token (`401`);
- a `POST` from elsewhere (`403`).

Each is handled by its declared length:
- **Up to `MAX_BODY`:** the server reads and discards that many bytes first, then answers. The
  connection stays open, and nothing unread is left on it. A slow sender is bounded by the idle
  timeout the connection already has.
- **Past `MAX_BODY`, or not a length:** the answer says `Connection: close`. The server then shuts its
  writing side and discards whatever still arrives, for at most 2 seconds and `MAX_BODY` bytes,
  whichever comes first, before it closes. This lingering close lets the answer reach the browser
  before any reset.

### 6.2 `[::1]` is held

When `ddd gui` listens on loopback, as it does by default, it also binds `[::1]` on the same port. It
never listens there.
- **What that buys.** No other program can listen on `localhost` at that port. A browser that tries
  `[::1]` first is refused at once, and falls back to `127.0.0.1`, where `ddd gui` answers.
- **No program can share it.**
  - On Windows, both sockets are bound with `SO_EXCLUSIVEADDRUSE`, so no program can share either
    port through `SO_REUSEADDR`.
  - The `[::1]` socket never sets `SO_REUSEADDR` itself. Linux lets two sockets share a port nobody
    listens on only when both set it.
  - The `[::1]` socket is `IPV6_V6ONLY`, so it never touches IPv4.
- **`--port 0`:** a port free on both addresses is chosen.
- **A fixed `--port` whose `[::1]` is taken:** `ddd gui` refuses to start, naming `[::1]`, as it refuses
  a taken `--port` today.
- **No IPv6 loopback:** there is nothing to hold, and nothing is said.
- **`--host` beyond loopback,** as in a container: nothing is held. The browser is on the host, and the
  container's own `[::1]` is out of its reach.

## 7 The page: option C

The Files tab's Remove panel asks its plan the moment its row is selected. That plan re-analyses the
project with its plugins. Option C asks it at once only when the selection came from within the page:
- **The row the page was loaded with** waits for a press: one from a link from elsewhere, a bookmark,
  a typed address, or a reload. The panel shows the row and a button that asks the plan, and nothing
  is asked until it is pressed.
- **Every other row asks at once,** as today. That is a row the reader selects, one reached through
  the page's own links (a finding's "Open …"), or one reached by back or forward within the page.
- **Where it lives.** The route keeps whether it is still the one the page was loaded with. The
  decision is a function in `src/lib`, under Vitest, so that the `.tsx` stays glue. The plan's query
  waits on that decision.
- **Nothing else needs the same.** Part 18b's final review found no other route that runs plugins or
  writes on arrival. Compare needs a typed baseline and a press, and the start page asks for the
  list of projects alone.
- **The button's words** are settled in the plan, along the lines of "Plan its removal".

## 8 The mapped drive

- **An early experiment.** Right after §4, one task finds out whether a Windows runner can map a drive
  to itself. A PowerShell step:
  1. creates a directory;
  2. shares it with `New-SmbShare`;
  3. maps it with `net use M: \\localhost\ddd-mapped`.

  If the runner refuses (no SMB server, or a policy), the plan records that as a ruling and drops the
  step. P18-12 then stays the maintainer's, by hand, in *What was left open*.
- **What runs on the drive.** A journey file, `gui/e2e/mapped.spec.ts`, starts `ddd gui` over a copy of
  `examples/demo` on `M:`. It then:
  - opens the project, which the server names by its network path, `//localhost/ddd-mapped/…`;
  - reads a component;
  - makes an edit of a unit, written through the share;
  - adds a file under the drive.

  A network path outside the directory served is still refused.
- **Chosen by configuration, not skipped.** `playwright.config.ts` leaves `mapped.spec.ts` out unless
  `DDD_MAPPED_DRIVE` names a drive. Only the Windows Chromium leg sets it, after mapping. One leg is
  enough: what is tested is the server's handling of paths, not the browser.
- **What is not covered.** The gui job runs Python 3.12 alone. The mapped case is not exercised on 3.13
  or 3.14, whose path resolution makes the same call. That is recorded as left open.

## 9 Testing

The house gates all hold: pytest at 100 % line and branch, ruff, format, mypy, the schemas, lint,
typecheck, Vitest at 100 % on all four metrics, the build, Ladle, the screenshots in Docker, the docs
under `-W`, and the journeys. Besides them:
- **The drain** (§6.1), tested on all six Python legs:
  - a refused `POST` with a body leaves its connection usable for a second request;
  - a refused `POST` past `MAX_BODY` has its answer read whole, with no reset.

  The Windows legs are where the old behaviour fails.
- **`[::1]`** (§6.2), tested on both systems:
  - while `ddd gui` runs, a second bind of `[::1]` on its port fails, and a connection there is
    refused;
  - a fixed port whose `[::1]` is taken is refused, with the whole sentence;
  - `--port 0` is retried;
  - no IPv6 loopback, and `--host` beyond loopback, each have a test of their own.

  A journey opens `localhost:<port>` in the browser and reaches `ddd gui`. A stranger cannot listen on
  `[::1]` at that port.
- **Option C** (§7). The decision has a Vitest case, and the new panel state has a Ladle story and a
  screenshot reference. A journey:
  1. opens `/project?view=files&path=<key>` as an address;
  2. checks that no `/api/files-plan` request goes out until the press;
  3. presses, and sees the plan;
  4. selects another row, whose plan is asked at once.

  The existing Files journeys select by pressing, and stay as they are.
- **The mapped drive** (§8): `mapped.spec.ts`, on the Windows Chromium leg.
- **The hunts** (§5): the baseline and the final hunt, on all three legs.

## 10 Documentation

- **The security page.**
  - The `localhost` bullet says `ddd gui` holds `[::1]`, and leaves *What it does not defend against*.
  - The paragraph on navigations from elsewhere describes option C. Such a navigation still opens the
    page at an address it chooses, but nothing that runs plugins is asked on arrival.
  - Whatever the page says of a refused `POST` stays true of the drain.
- **The CHANGELOG** gets one entry each for the drain, the `[::1]` hold and option C. CI changes are
  not the reader's, and stay out of it.
- **The plan's *Figures*,** before and after:
  - the hunt on each leg: its runs, and its failures by journey;
  - the refused-`POST` probe on Windows: how many resets;
  - a stranger on `[::1]:<port>`: it gets the token before, and cannot bind there after;
  - arriving at a Files row by its address: the plan is asked before, and nothing is asked after.

## 11 Risks

- **The baseline may find more flakes than the five known.** Fixing them is open-ended, so rulings cap
  it (§5).
- **SMB may be off on the runners.** §8 then falls back to the check by hand.
- **Windows-only behaviour is iterated through CI alone.** The reset, the socket options and the
  mapped drive each cost a push and about 10 minutes per attempt, because no Windows machine is at
  hand.
- **Edge on the runner is one version, 153,** where a pilot's may be older or newer. It is the same
  engine as Chrome 153, which the journeys already run in locally.

## 12 Out of scope

- **The journeys for the actions that have none,** about 49 of them: 19b's.
- **Firefox, Safari and macOS.**
- **The mapped drive on Python 3.13 and 3.14** (§8).

## 13 Decisions taken

The maintainer's answers while this was designed:
- **Part 19 covers every reader action,** cut into 19a, this part, and 19b.
- **P18b-10 is closed with option C,** in 19a, before 19b writes journeys for the Files tab.
- **CI's job timeouts, and holding `[::1]`, are taken into 19a.**
- **Windows runs the journeys in both Edge and Chromium.**
- **Measure, then fix.** A hunt runs before and after, with no retries.
- **The failed hunts' traces may be downloaded** without asking each time.

Taken in the design:
- **The hunt is the manual trigger's `repeat` input.** A hunt skips every job but the three gui legs.
- **`[::1]` is bound without being listened on.** On Windows, both sockets take `SO_EXCLUSIVEADDRUSE`. A
  fixed `--port` whose `[::1]` is taken is refused, and `--port 0` is retried.
- **The drain reads a declared body up to `MAX_BODY` before answering.** Past it, the server closes
  with a lingering close.
- **Option C's "arrival" is the route the page was loaded with.** Back and forward within the page,
  and the page's own links, count as the reader's.
- **`mapped.spec.ts` is chosen by configuration,** on the Windows Chromium leg.
