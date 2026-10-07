# The GUI's Journeys on Every Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The 89 journeys pass reliably on Ubuntu with Chromium, Windows with Chromium and Windows with Edge. Four items earlier parts left for this point close with them:
- a refused `POST`'s body is drained;
- `[::1]` is held on the port;
- the Files tab asks a removal's plan on arrival only for a row the reader chose;
- a mapped drive is tried in CI.

**Architecture:**
- **CI first.** The gui job runs three legs, and every job has a timeout. The manual trigger's `repeat` input turns a run into a hunt, which repeats the journeys and runs nothing else.
- **Measure, then fix.** A baseline hunt on the journeys as master has them names the flakes. Each is fixed at its cause, from its trace, and a final hunt shows none left.
- **The server.** `_send` drains a refused `POST`'s declared body, or closes with a lingering close. `GuiServer` binds `[::1]` beside its IPv4 socket, and never listens there.
- **The page.** The route says whether it is the one the page was loaded with. The Remove panel asks its plan at once only when it is not.

**Tech Stack:**
- **CI:** GitHub Actions (`.github/workflows/ci.yml`). Playwright 1.63's `channel: "msedge"` drives the Windows runner's own Edge 153. PowerShell's `New-SmbShare` and `net use` map the drive.
- **Server:** Python 3.12 to 3.14, `socket`, `http.server`, and pytest at 100 % line and branch.
- **Page:** React 19 + TypeScript, Vitest at 100 % over `src/api`, `src/lib` and `src/state`, Ladle with Docker screenshot references, and Playwright journeys.

**Spec:** `docs/superpowers/specs/2026-10-07-gui-journeys-every-platform-design.md`. Read it before any task. Where this plan departs from it, the departure is a ruling in *Rulings taken* at the end, with its reason.

## Global Constraints

Every task's requirements include this section.

**Running things**

- **Interpreters.** There is no `python` on PATH: always use `.venv/bin/python`. Node is not on PATH either; it is at `~/.local/node-v24.21.0/bin`.
- **Never add `-q` to pytest.** `pyproject.toml` already sets it in `addopts`. A second one removes the `N passed` line while pytest-cov still prints its coverage line, so the output looks fine and says nothing.
- **A pipeline reports its last command's exit status.** Capture each tool's own: `.venv/bin/python -m pytest > gate.txt 2>&1; echo "EXIT=$?"; tail -3 gate.txt`. A run that finished ends with its **summary line**; a tail ending in a stack trace did not finish, whatever the exit code says.
- **A stale `.coverage` file.** Once it made pytest answer `4445 passed` with exit 3 and **no coverage line**. If the coverage summary is missing, delete `.coverage*` (gitignored) and run again.
- **Journeys:**
  1. Run `cd gui && npm run build` first, because the journeys drive the **compiled** pages in `src/ddd/gui/static`.
  2. Then run `PLAYWRIGHT_CHANNEL=chrome DDD_PYTHON="$PWD/../.venv/bin/python" npx playwright test --output=<a path outside the repository>`. Writing `--output` inside `gui/` fails with `EACCES`.
- **Never run the journeys while the Docker screenshot run is running.** Both drive Playwright over the same `gui/` checkout, and the journeys then fail with "Playwright Test did not expect test() to be called here". Run one after the other.
- **Screenshots and docs** run from the repository root, in Docker, which cannot see the session scratchpad:
  - `UPDATE=1 docker compose run --rm gui-screenshots` rewrites the references; without `UPDATE=1` it compares.
  - `docker compose run --rm -e JAVA_TOOL_OPTIONS=-Duser.home=/tmp docs` builds the docs.
- **Page schemas:** run `cd gui && DDD=../.venv/bin/ddd DDD_PYTHON=../.venv/bin/python npm run schemas`. `gui/src/generated/` is gitignored, so grep the generated file and let `npm run typecheck` prove the page agrees.
- **Stopping a server you started.** List its PID by process name, then kill it in a **separate** command:
  1. `ps -eo pid,comm,args | awk '$2 ~ /^python/ && /<pattern>/'`
  2. `kill <pid>`

  Never `pkill -f` and never `pgrep -f`: the shell running the command holds the pattern in its own command line, so `pkill -f` kills that shell, and a `pgrep -f` wait loop never ends. Leave nothing of yours running.
- **Never route around a refusal.** If the permission check refuses a command, stop and say so in your report. Never reach the same effect another way.
- **Delete only what you created,** each by its exact path, and never with a glob outside the session scratchpad.
- **Two `ddd gui` Docker containers on ports 8124 and 8125 belong to other work.** Leave them alone.

**Windows, through CI alone**

- **No Windows machine is at hand.** A change whose proof is a Windows leg is pushed to this branch and run there. Each attempt costs about ten minutes, so batch what can be batched.
- **Only the controller pushes, and only this branch.** The maintainer gave leave for `feature/gui-journeys-every-platform`, for 19a's CI runs and hunts. Never master, never `--force`. An implementer commits locally and reports; the controller pushes, starts the run, and hands the result back.
- **Starting a run:**
  - a full run of every job: `gh workflow run ci.yml --ref feature/gui-journeys-every-platform -f repeat=1`;
  - a hunt: `-f repeat=5`.

  Wait on it once, in the background, with `gh run watch <run> --interval 30`. Never poll it in a loop.
- **Reading a run:**
  - its jobs: `gh run view <run> --json jobs`;
  - a job's log: `gh api repos/Sauci/ddd/actions/jobs/<job>/logs`.
- **The failed runs' Playwright reports** may be downloaded without asking: the maintainer's leave, for 19a's runs alone. Use `gh run download <run> -n playwright-report-<os>-<browser> -D <scratchpad>/<run>`. Read each failed test's `error-context.md`, the page's accessibility snapshot at the failure, and the network entries in its `trace.zip`. Nothing else is downloaded without asking.

**Gates**

- **Python:** `.venv/bin/python -m pytest` at **100 % line and branch**, `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, and `.venv/bin/mypy` run **bare** (it checks `src/ddd` and `tools`, strictly).
- **Page:** `npm run lint && npm run typecheck && npm test && npm run build && npm run ladle:build`, with Vitest at 100 % on statements, branches, functions **and** lines over `src/api`, `src/lib` and `src/state`.
- No `pragma: no cover`, no skips, no xfails.
- **No commit leaves a gate red.**
- **CI runs more than the development PC does:**
  - **Python versions and runners.** Python 3.12, 3.13 and 3.14, on ubuntu **and** windows runners. On 3.12 and 3.13, coverage traces with `sys.settrace`, which spends stack on every traced call.
  - **Windows file locks.** Windows refuses to rename over, or delete, a file that another handle holds open (`ddd.editing.REPLACE_TRIES`).
  - **Windows sockets.**
    - A socket bound without `SO_EXCLUSIVEADDRUSE` can be shared by another one that sets `SO_REUSEADDR`.
    - A connection to a port nobody listens on is refused only after Windows has retried for about two seconds.
    - A socket closed with unread data resets the connection, and a reset can throw away an answer the other side has not read yet.
  - **Windows reads `a:b` as a drive,** and **Python 3.12's pathlib** raises `RuntimeError` on a loop of links. Anything a request names is resolved through `loading.resolve_path`.

**What the gates cannot see**

- **Some code registers no branch with coverage.py.** A conditional expression registers zero branches, and so does a comprehension filter. A short-circuit `and`/`or` inside an `if` records one branch pair for the whole `if`, not one per operand. Write statements where a branch matters.
- **A coverage gate cannot see data.** Ablate every new data value (a limit, a sentence, a header, a default, a line of `ci.yml`) and confirm that a **named** test dies. If none does, write the one that does.
- **Ablate Python in a scratch `git worktree`, with pytest run from inside that worktree.**
  - `pyproject.toml` sets `pythonpath = ["src", "tools", "docker"]`, resolved against *rootdir* and placed ahead of any `PYTHONPATH` you export. A run started from the main repository measures the main repository. The tell is pytest's own `rootdir:` line.
  - **Confirm one ablation kills something before trusting that another kills nothing.**
  - Before a survival is believed, run it again under `PYTHONHASHSEED=0`, `1`, `4` and `7`.
  - A `cp` into the worktree, or a `sed -i` in the same second, can leave a stale `.pyc`: set `PYTHONDONTWRITEBYTECODE=1`.
- **Ablate the page in place,** because a fresh worktree has no `node_modules`.
  - Run `git status --porcelain <file>` **immediately before every restore**: `git checkout -- <file>` reverts to HEAD and silently eats any fix made in that file since.
  - After each restore, grep for something you expect still to be there.
- **Never conclude what *else* pins something from a narrowed run** (no `-k`, no path argument). That is a whole-suite question; copy the summary line in rather than paraphrasing it.
- **No decision may live in a `.tsx` file.** Every judgement lives in `gui/src/lib` or `gui/src/state`, under the Vitest gate; a `src/app` hook is glue only.
- **A refusal test asserts the whole sentence with `==`.** Read every expected sentence off the running code, never out of this plan.
- **A test never sleeps to coordinate.** It uses `threading.Event`s, real sockets and timeouts. Every wait passes a timeout, so that a hold that lasts too long fails the test instead of hanging the suite.
- **A journey waits on what the reader sees.**
  - Never `page.waitForTimeout`.
  - Never `page.waitForResponse` to coordinate (`docs/superpowers/plans/2026-09-26-gui-compare.md`).
  - Never a count read with `.all()` before what it counts is drawn.
  - Use `toHaveCount`, `toBeVisible`, `toHaveAccessibleName`, or `expect.poll` on what the page shows.
- **A journey leaves no visible window between a write and its stamp** (`driftMaxUnseen` in `gui/e2e/demo.ts`).
- **The suite forbids skips** (`test_nothing_in_the_suite_skips`). A branch only one platform takes is covered by a module flag monkeypatched both ways, as `queries._CASELESS` and `queries._OPENS_DEVICES` are.
- **CI configuration is data.** A change to `ci.yml` is pinned by a test in `tests/test_documentation.py` that reads the workflow's text, the way the development build's tests already do (`job`, `step`, `uncommented`).

**Prose**

- **A sentence stating a measurement gets the measurement run as it is written,** against the file it names, with the exit status copied from *that* run. A sentence saying "nothing else does X" is a whole-repository claim, and gets a whole-repository grep.
- **The security page states what was measured or read from the code, never what was guessed** (part 18b's two reviews of it).
- **A probe is quoted with the machine, the commit, the project and the run it came from.**
- **Cite by name, not by line number.** Line numbers in this plan were measured at `e935295`, and go stale the moment an earlier task edits the file.
- **Before ruling on a trade-off, confirm that both sides of it can actually happen.**

**Conventions**

- **Commits:** a lowercase imperative subject on **one line**, with no `feat:`-style prefix, and a body saying why. The trailer names the model that wrote the commit: `Co-Authored-By: <the model you are> <noreply@anthropic.com>`. A dispatch never tells you which model to name (part 18b's P18b-15). Never `--amend`, never rebase, never push.
- **Every UI pull request carries a screenshot of what it added,** the maintainer's standing rule. Open each new or changed reference and say what it shows, quoting from the image. "Updated N references" is not a report.
- **Reports go where your dispatch says,** to the report file it names.
- **If a brief or this plan is wrong, say so in your report** rather than working around it silently.
- **Bidi characters.** A unicode escape typed through the tools can land as the character itself: a right-to-left override did, twice, in part 18. Write such a character as words ("U+202E"), or build it in code with `chr()`. Before any push, the controller scans the commit messages and the changed files for U+202A to U+202E and U+2066 to U+2069.

## Prerequisites

1. **The branch.** The work is on `feature/gui-journeys-every-platform`, made from master `290fd9a` (part 18b, PR #80). Its first commit is the spec, `e935295`. Work in the main checkout `/home/sauci/Documents/Github/ddd`: Docker cannot see the session scratchpad.
2. **The baseline gate.** Run the milestone gate (below) once at this plan's commit, before Task 1, so that every later red is this part's own.
3. **Read the spec,** whose §1 and §2 say what was found and where.

## Review Focus

The five failure modes the spec implies but no task would test on its own, most likely first. Each has its test in the task that owns the code.

1. **A hunt is not a pass.** A dispatch with `repeat` above 1 must skip every job but the three gui legs, and publish nothing. A pull request's run, and a dispatch with `repeat` 1, must run every job as today. *(Task 1: the `if:` of every job, and the development build's conditions untouched.)*
2. **A refused `POST` whose sender stops sending.** The drain reads a declared body before answering. A sender that declares 100 bytes and sends 10 must not hold its thread past the idle timeout, and must not be answered. *(Task 4.)*
3. **`[::1]` refused on Windows takes about two seconds,** after Windows has retried. A browser opening `localhost:<port>` must still land within the journey's usual timeouts on the Windows legs, through its fallback to `127.0.0.1`. *(Task 5's journey, on all three legs.)*
4. **A row the page was loaded with, then pressed again in the table.** The panel waiting for its press must ask the plan once when pressed. A reader who presses the same row in the table instead gets the plan at once, never a second button. *(Task 6: a Vitest case and a journey step.)*
5. **The mapped drive's neighbours.** A network path under the drive's served directory is answered. One beside it (`//localhost/ddd-mapped-other/…`) is refused, with the whole sentence. *(Task 2's journey.)*

## File Structure

| File | Task | What |
| --- | --- | --- |
| `.github/workflows/ci.yml` | 1, 2 | three gui legs, timeouts, the `repeat` input; the mapped drive's step |
| `tests/test_documentation.py` | 1, 2 | the legs, the timeouts, the hunt and the mapped step, read off the workflow |
| `gui/playwright.config.ts` | 2 | `mapped.spec.ts` chosen by `DDD_MAPPED_DRIVE` |
| `gui/e2e/fixtures.ts` | 2 | `mappedGui` |
| `gui/e2e/mapped.spec.ts` | 2 | the journey on the mapped drive |
| `gui/e2e/*.spec.ts`, `gui/e2e/demo.ts` | 3 | the flakes, each at its cause |
| `src/ddd/gui/server.py` | 4, 5, 7 | the drain and the lingering close; `[::1]` held; the docstring |
| `tests/test_gui_server.py` | 4, 5 | both, through real sockets |
| `gui/e2e/localhost.spec.ts` | 5 | `localhost` reaches `ddd gui`, and a stranger cannot hold `[::1]` |
| `gui/src/app/useRoute.ts`, `gui/src/app/App.tsx` | 6 | whether the route is the one the page was loaded with, handed to the Files tab |
| `gui/src/lib/files.ts`, `files.test.ts` | 6 | `removalAsked` |
| `gui/src/screens/FilesPage.tsx` | 6 | glue: the plan's query waits on `removalAsked` |
| `gui/src/components/FileActionsView.tsx`, `.stories.tsx` | 6 | the Remove panel waiting for its press, and its story |
| `gui/screenshots/references/` | 6 | the story's reference |
| `gui/e2e/files.spec.ts` | 6 | the arrival journey |
| `docs/gui_security.rst`, `CHANGELOG.md` | 7 | what is defended now |
| this plan | 8 | figures, progress, what was left open, rulings |

## Interfaces Between Tasks

- **Task 1 gives every later run its shape.**
  - The `repeat` input of `ci.yml`.
  - The gui job's names, `gui (<os>, <browser>)`.
  - Its failure artifacts, `playwright-report-<os>-<browser>`.
  - The step names `Install Playwright's Chromium` and `Run the journeys`.
- **Task 2:** the environment variable `DDD_MAPPED_DRIVE`, a drive such as `M:`, and the fixture `mappedGui: Gui`.
- **Task 4 to Task 5:** `_Handler._declared() -> int | None`, a declared length the server reads, at most `MAX_BODY`. Also `_Handler._linger: bool` and `_linger(connection: socket.socket) -> None`.
- **Task 5:**
  - `class IPv6Held(OSError)`;
  - `GuiServer.held: socket.socket | None`;
  - `_held_beside(host: str, port: int) -> socket.socket | None`;
  - the module flag `_EXCLUSIVE: bool`;
  - `PORT_TRIES: Final = 5`.
- **Task 6:**
  - `useRoute(): [Route, navigate, arrived: boolean]`;
  - `removalAsked(arrived: boolean, pressed: boolean): boolean` in `gui/src/lib/files.ts`;
  - `RemoveFileViewProps.waiting?: () => void`, the press that asks the plan, present while it waits.
- **Task 7** reads what Tasks 4 to 6 built, for the prose.

---

### Task 1: CI, with three legs, timeouts and the hunt

**Model:** sonnet. It is YAML and text tests, fully specified here.

**Files:**
- Modify: `.github/workflows/ci.yml`
- Test: `tests/test_documentation.py`

**Interfaces:**
- Consumes: the helpers `job`, `step`, `uncommented` and `CI_WORKFLOW` in `tests/test_documentation.py`.
- Produces: the `repeat` input; the gui legs `gui (ubuntu-latest, chromium)`, `gui (windows-latest, chromium)` and `gui (windows-latest, msedge)`; the steps `Install Playwright's Chromium` and `Run the journeys`; artifacts `playwright-report-<os>-<browser>`.

- [ ] **Step 1: Write the failing tests.** Add this class to `tests/test_documentation.py`, after the development build's tests (the class holding `test_it_waits_for_every_other_job_of_the_run`):

```python
class TestTheCiRun:
    """What part 19a asked of ci.yml (spec §4): the journeys on three legs, a timeout on every
    job, and a manual run that repeats the journeys and runs nothing else."""

    @staticmethod
    def names() -> list[str]:
        return re.findall(r"^  ([a-z][\w-]*):\n", CI_WORKFLOW.split("\njobs:\n", 1)[1], re.M)

    def test_every_job_has_a_timeout(self) -> None:
        """GitHub's own default is 360 minutes: a gui job once hung 24 of them installing a
        browser, and would have held the run, and any re-run of its failed jobs, for the rest."""
        untimed = [name for name in self.names() if "\n    timeout-minutes: " not in job(CI_WORKFLOW, name)]
        assert untimed == [], f"these jobs of ci.yml can run for 360 minutes: {untimed}"

    def test_the_journeys_run_on_three_legs(self) -> None:
        legs = re.findall(
            r"- os: (\S+)\n\s+browser: (\S+)", uncommented(job(CI_WORKFLOW, "gui"))
        )
        assert sorted(legs) == [
            ("ubuntu-latest", "chromium"),
            ("windows-latest", "chromium"),
            ("windows-latest", "msedge"),
        ]

    def test_edge_is_the_runner_s_own_and_the_install_is_bounded(self) -> None:
        install = step(job(CI_WORKFLOW, "gui"), "Install Playwright's Chromium")
        assert "if: matrix.browser == 'chromium'" in install
        assert "timeout-minutes: 5" in install
        journeys = step(job(CI_WORKFLOW, "gui"), "Run the journeys")
        assert "PLAYWRIGHT_CHANNEL: ${{ matrix.browser == 'msedge' && 'msedge' || '' }}" in journeys

    def test_the_manual_run_asks_how_many_times(self) -> None:
        dispatch = CI_WORKFLOW.split("\n  workflow_dispatch:", 1)[1].split("\npermissions:", 1)[0]
        assert "repeat:" in dispatch
        assert "type: number" in dispatch
        assert "default: 1" in dispatch

    def test_a_hunt_repeats_every_journey(self) -> None:
        journeys = step(job(CI_WORKFLOW, "gui"), "Run the journeys")
        assert "npm run e2e -- --repeat-each=${{ inputs.repeat || 1 }}" in journeys

    def test_a_hunt_runs_the_journeys_alone(self) -> None:
        """Every job but the gui legs is skipped by a hunt; the development build already
        publishes nothing on a manual run (``test_only_this_repository_publishes_one``)."""
        alone = {"gui", "dev-build", "dev-publish"}
        unskipped = [
            name
            for name in self.names()
            if name not in alone
            and "\n    if: ${{ !(inputs.repeat > 1) }}\n" not in job(CI_WORKFLOW, name)
        ]
        assert unskipped == [], f"these jobs would run during a hunt: {unskipped}"
```

Read `step`'s own definition first: it finds a step by its `name:`. If it matches differently (by `- name: <name>` with a prefix), adapt the two step names and this test together, and say so in your report.

- [ ] **Step 2: Run them to see them fail.**
  - Run: `.venv/bin/python -m pytest tests/test_documentation.py -k TestTheCiRun --no-cov -p no:cacheprovider`
  - Expected: 6 failed. Five fail because the workflow lacks what they read. `test_every_job_has_a_timeout` lists all eight jobs.

- [ ] **Step 3: The manual trigger's input.** In `ci.yml`, replace `  workflow_dispatch:` under `on:` with:

```yaml
  # A manual run of any branch. With repeat above 1 it is a hunt: the journeys run that many
  # times on all three legs, and every other job is skipped (part 19a).
  workflow_dispatch:
    inputs:
      repeat:
        description: "How many times each journey runs; above 1, only the journeys run"
        type: number
        default: 1
```

- [ ] **Step 4: Skip and time every other job.** Directly under each of `test:`, `lint:`, `container:`, `extension:` and `gui-screenshots:`, before its first existing key, add these lines, with the timeout shown:

```yaml
    # Skipped by a hunt, which is the journeys' alone.
    if: ${{ !(inputs.repeat > 1) }}
    timeout-minutes: 25
```

The timeouts are 25 for `test`, 10 for `lint`, 20 for `container`, 15 for `extension` and 20 for `gui-screenshots`. `dev-build` gets `timeout-minutes: 25` and `dev-publish` gets `timeout-minutes: 10`, beside their existing keys. Their conditions stay as they are.

- [ ] **Step 5: The three legs.** Replace the gui job's `strategy:` block and `runs-on:` line with the block below. Keep the job's comment, and add one sentence to it: "Three legs: Playwright's own Chromium on both systems, and the windows runner's own Edge, which a reader on windows most likely has (part 19a)."

```yaml
    name: gui (${{ matrix.os }}, ${{ matrix.browser }})
    strategy:
      fail-fast: false
      matrix:
        include:
          - os: ubuntu-latest
            browser: chromium
          - os: windows-latest
            browser: chromium
          - os: windows-latest
            browser: msedge
    runs-on: ${{ matrix.os }}
    # A hunt runs every journey five times or more: an ordinary run's half hour is too short
    # for it.
    timeout-minutes: ${{ inputs.repeat > 1 && 150 || 30 }}
```

- [ ] **Step 6: The two steps, and the artifact's name.** Replace `- run: npx playwright install --with-deps chromium` and `- run: npm run e2e` with:

```yaml
      # Edge is the windows runner's own, and needs no download. A stalled download fails in
      # minutes rather than holding the job: it once hung for 24.
      - name: Install Playwright's Chromium
        if: matrix.browser == 'chromium'
        timeout-minutes: 5
        run: npx playwright install --with-deps chromium
      - name: Run the journeys
        run: npm run e2e -- --repeat-each=${{ inputs.repeat || 1 }}
        env:
          PLAYWRIGHT_CHANNEL: ${{ matrix.browser == 'msedge' && 'msedge' || '' }}
```

In the `if: failure()` upload at the job's end, change `name: playwright-report-${{ matrix.os }}` to `name: playwright-report-${{ matrix.os }}-${{ matrix.browser }}`. The `if: runner.os == 'Linux'` steps stay, and now run on the one Ubuntu leg.

- [ ] **Step 7: Run the tests to see them pass.**
  - Run: `.venv/bin/python -m pytest tests/test_documentation.py --no-cov -p no:cacheprovider`
  - Expected: every test passes, `test_it_waits_for_every_other_job_of_the_run` among them. The job keys are unchanged.

- [ ] **Step 8: Ablate the data.** Restore after each one, checking `git status --porcelain .github/workflows/ci.yml` before the restore:
  - delete one job's `timeout-minutes` line;
  - change `msedge` in the matrix to `chromium`;
  - delete the `if:` from `lint`;
  - change `--repeat-each=${{ inputs.repeat || 1 }}` to `--repeat-each=1`.

  Each must kill a named test of `TestTheCiRun`.

- [ ] **Step 9: The whole gate.** Run pytest at 100 %, ruff, format and mypy, each exit status captured. Nothing of the page changed.

- [ ] **Step 10: Commit.** Use a lowercase imperative subject, such as "run the journeys in edge too, put a timeout on every job, and let a manual run repeat them", and a body saying why: the Windows flakes, the 24-minute hang, and the hunt.

### The controller: the first push, and the baseline hunt

Not a subagent's task.

- [ ] **Scan before pushing.** Scan the branch's commit messages and changed files for bidi characters (Global Constraints).
- [ ] **Push** `feature/gui-journeys-every-platform`: `git push -u origin feature/gui-journeys-every-platform`. A refused push stops here, and is reported.
- [ ] **Start the baseline hunt:** `gh workflow run ci.yml --ref feature/gui-journeys-every-platform -f repeat=5`. Find its run id with `gh run list --workflow ci.yml --branch feature/gui-journeys-every-platform --limit 1`, and wait on it once, in the background.
- [ ] **Check the hunt ran as Task 1 says:**
  - the three gui legs ran;
  - every other job was skipped;
  - `dev-build` and `dev-publish` did not run.

  If the YAML did not parse, the run fails at once and says where. Task 1 is then reopened with that line.
- [ ] **Record every failure** in *Figures*, under *The baseline hunt*: per leg, its runs and its failures by journey. For each failure, download its leg's report and note the error, the page's snapshot from `error-context.md`, and the cause the trace suggests.
- [ ] **Rule Task 3's shape:** one task per cause the baseline shows, or one task holding several small ones. Record the ruling.

### Task 2: the mapped drive

**Model:** opus. A Windows-only experiment, iterated through CI.

**Files:**
- Modify: `.github/workflows/ci.yml`, `gui/playwright.config.ts`, `gui/e2e/fixtures.ts`
- Create: `gui/e2e/mapped.spec.ts`
- Test: `tests/test_documentation.py`

**Interfaces:**
- Consumes: Task 1's gui legs.
- Produces: `DDD_MAPPED_DRIVE`; the `mappedGui` fixture.

- [ ] **Step 1: The test of the step.** Add to `TestTheCiRun`:

```python
    def test_the_windows_chromium_leg_maps_a_drive_for_its_journey(self) -> None:
        mapped = step(job(CI_WORKFLOW, "gui"), "Map a drive for the mapped-drive journey")
        assert "if: runner.os == 'Windows' && matrix.browser == 'chromium'" in mapped
        assert "New-SmbShare" in mapped and "net use M:" in mapped
        assert "DDD_MAPPED_DRIVE=M:" in mapped
```

Run it, and expect it to fail: the workflow has no such step.

- [ ] **Step 2: The step.** Insert it in the gui job, after `npm run build` and before `Install Playwright's Chromium`:

```yaml
      # P18-12: a project on a mapped drive, which Windows names by its network path. The runner
      # shares a directory with itself and maps it as M:, and the windows chromium leg runs
      # mapped.spec.ts there; one leg is enough, the server's paths being what is tested.
      - name: Map a drive for the mapped-drive journey
        if: runner.os == 'Windows' && matrix.browser == 'chromium'
        shell: pwsh
        run: |
          $shared = Join-Path $env:RUNNER_TEMP "ddd-mapped"
          New-Item -ItemType Directory -Path $shared | Out-Null
          New-SmbShare -Name ddd-mapped -Path $shared -FullAccess "$env:USERDOMAIN\$env:USERNAME" | Out-Null
          net use M: \\localhost\ddd-mapped /persistent:no
          "DDD_MAPPED_DRIVE=M:" | Out-File -FilePath $env:GITHUB_ENV -Append -Encoding utf8
```

Run the test from step 1, and see it pass.

- [ ] **Step 3: Choose the journey by configuration.** In `gui/playwright.config.ts`, after `testDir: "e2e",`, add:

```ts
  // mapped.spec.ts needs a drive mapped to a network share, which CI's windows chromium leg
  // makes (ci.yml) and names in DDD_MAPPED_DRIVE: everywhere else it is left out, not skipped.
  testIgnore: process.env.DDD_MAPPED_DRIVE ? [] : ["**/mapped.spec.ts"],
```

- [ ] **Step 4: The fixture.** In `gui/e2e/fixtures.ts`:
  - add `mappedGui: Gui;` to the `base.extend` type;
  - add this fixture after `generatedGui`:

```ts
  // biome-ignore lint/correctness/noEmptyPattern: Playwright reads a fixture's dependencies from this pattern
  mappedGui: async ({}, use, testInfo) => {
    const drive = process.env.DDD_MAPPED_DRIVE;
    if (drive === undefined) {
      throw new Error("mappedGui serves a mapped drive, which DDD_MAPPED_DRIVE must name");
    }
    // A directory of the test's own on the drive, as `started` makes one under test-results.
    const directory = join(`${drive}\\`, `ddd-${testInfo.testId}`, DEMO.directory);
    cpSync(join(EXAMPLES, DEMO.directory), directory, { recursive: true });
    await serving(directory, [join(directory, DEMO.project)], use);
  },
```

- [ ] **Step 5: The journey.** Create `gui/e2e/mapped.spec.ts`:

```ts
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { CONTROLLER, chooseUnit, openPanel } from "./demo";
import { expect, test } from "./fixtures";

/** ValueA's own definition in `file` of the copy on the drive, read back as written. */
function valueA(directory: string, file: string): { unit?: string } {
  const data = JSON.parse(readFileSync(join(directory, file), "utf8"));
  return data.component.interface.find(
    (declaration: { definition: { name: string } }) => declaration.definition.name === "ValueA",
  ).definition;
}

test("a project on a mapped drive is served by its network path, and edited through it", async ({
  page,
  mappedGui,
}) => {
  const token = new URL(mappedGui.address).searchParams.get("token");
  const headers = { authorization: `Bearer ${token}` };

  // Windows names a mapped drive's directory by the network path it maps (P18-12): every file
  // the server answers is named so, and the page sends those names back.
  const state = (await (await fetch(new URL("/api/state", mappedGui.address), { headers })).json()) as {
    files: { path: string }[];
  };
  expect(state.files.length).toBeGreaterThan(0);
  for (const file of state.files) {
    expect(file.path.toLowerCase()).toMatch(/^\/\/localhost\/ddd-mapped\//);
  }

  // An edit through the page, written through the share.
  const panel = await openPanel(page, mappedGui.address, "ValueA");
  await chooseUnit(page, "rpm");
  await panel.getByRole("button", { name: /^Apply to/ }).click();
  await expect.poll(() => valueA(mappedGui.directory, CONTROLLER).unit).toBe("rpm");

  // A network path beside the directory served is refused, in the server's own words.
  const beside = new URL("/api/file", mappedGui.address);
  beside.searchParams.set("path", "//localhost/ddd-mapped-other/a.ddd.json");
  const refused = await fetch(beside, { headers });
  expect(refused.status).toBe(400);
  expect(await refused.json()).toEqual({
    error: "bad-request",
    message: "file takes ?path= as a file's path",
  });
});
```

`openPanel` and `chooseUnit` are `gui/e2e/demo.ts`'s own. Read both before relying on them, and read how `units.spec.ts` applies a unit after `chooseUnit`. If the panel's button is named otherwise there, use its name. Read the refusal's error code and sentence off the running server (`FileQuery` in `src/ddd/gui/queries.py`), never out of this plan.

- [ ] **Step 6: Locally, nothing runs it.**
  - Run: `cd gui && npm run build && PLAYWRIGHT_CHANNEL=chrome DDD_PYTHON="$PWD/../.venv/bin/python" npx playwright test --list | grep -c mapped`. Expected: `0`.
  - Then run the whole suite, with `--output` outside the repository. Expected: 89 passed.
- [ ] **Step 7: The gates:** pytest, ruff, format, mypy, lint, typecheck and build, each exit status captured.
- [ ] **Step 8: Commit,** then report to the controller. The controller pushes, starts a full run (`-f repeat=1`) and hands back the Windows chromium leg's log.
- [ ] **Step 9: Read the run.**
  - **The step mapped `M:` and the journey passed:** report its lines from the log.
  - **The journey failed:** read its report (Global Constraints), fix the cause, and go back to step 8.
  - **The step itself failed** (no SMB server, or a policy): report the error. The controller rules the step out of `ci.yml`, together with its test from step 1. `mapped.spec.ts`, its fixture and the configuration stay: the maintainer's check by hand then becomes "map a drive, set `DDD_MAPPED_DRIVE`, run `npx playwright test e2e/mapped.spec.ts`". That sentence goes into *What was left open*.

### Task 3: the flakes, each at its cause

**Model:** opus. Diagnosis from traces.

**Files:** as the baseline shows; known so far:
- `gui/e2e/skeleton.spec.ts`: "the demo opens on a canvas of its four modules", and "a dragged module stays where it was put after a revision, and Tidy puts it back";
- `gui/e2e/keys.spec.ts`: "a change refused as stale can be applied again once the analysis has caught up";
- `gui/e2e/values.spec.ts`: "a curve is drawn from the numbers it holds", and "a physical value no raw count represents shows what was stored".

**Interfaces:**
- Consumes: the baseline's table in *Figures*, and its reports in the scratchpad.
- Produces: journeys with no timing assumption, one commit per cause.

- [ ] **Step 1: Read the baseline.** For each failure in *Figures*, read the leg's downloaded report:
  - the failed test's `error-context.md`: what the page showed;
  - the `trace.zip`'s network entries: what was asked, and when.

  Name the cause in one sentence. A journey that failed on no leg of the baseline is left as it is, and *Figures* says it was not reproduced in its runs.
- [ ] **Step 2: The arrow count**, if the baseline shows it or the code still reads `.all()` before the arrows are drawn. In "the demo opens on a canvas of its four modules", replace the lines from `const arrows = await canvas.getByRole("group").all();` to the loop's end with the block below. `DEMO_ARROWS` is the demo's arrow count, read once off the served page and pinned literally, as `values.spec.ts` pins its points:

```ts
  // Drawn once the nodes are measured, after the module buttons: counted only once all of them
  // are there, which `toHaveCount` waits for and `.all()` did not.
  const arrows = canvas.getByRole("group");
  await expect(arrows).toHaveCount(DEMO_ARROWS);
  for (const arrow of await arrows.all()) {
    await expect(arrow).toHaveAccessibleName(/agreed$/);
  }
```

  Declare `const DEMO_ARROWS = <the count>;` above the test, with a comment saying where it was read.
- [ ] **Step 3: The dragged module's wait.** In "a dragged module stays where it was put after a revision, and Tidy puts it back", replace the outside save and its `waitForResponse` with a drift whose effect the reader sees. The drift colours SensorHub's arrow into Controller:

```ts
  // Saved from outside the page, so that a new revision arrives while the canvas is open - and
  // waited for by what it changes on the canvas, the arrow it colours, rather than by a
  // response the page may or may not have asked for yet.
  drift(gui.directory);
  await expect(page.getByLabel("SensorHub to Controller: 2 variables, error")).toBeVisible();
  await expect
    .poll(() => controller.evaluate((node) => (node as HTMLElement).style.transform))
    .toBe(dragged);
```

  Import `drift` from `./demo`, and drop the imports nothing uses any more (`SENSOR_HUB`, `writeFileSync`, `readFileSync`, if so). `drift`'s own comment says which file it writes. Check that the arrow is the one it colours, as "a disagreement colours its arrow" shows.
- [ ] **Step 4: Each other cause** the baseline names: the change that removes it, a wait on what the reader sees in place of a wait on time or on a response. The journey's comment says what raced and what it now waits for.
- [ ] **Step 5: Prove each fix locally:** `npx playwright test e2e/<file>.spec.ts --repeat-each=20 --output=<scratch>`, with no failure. Copy the summary line.
- [ ] **Step 6: Commit,** one commit per cause, each body naming the run and the leg whose trace showed it.
- [ ] **Step 7: The Windows proof.** The controller pushes and starts a hunt (`-f repeat=5`). A failure left goes back to step 1, with its new trace. Five rounds without its cause found is a ruling: it is recorded in *Figures* with its rate and evidence, and stays visible in the pull request (spec §5).

### Task 4: a refused `POST` drains its body

**Model:** opus. Sockets, and a Windows-only red.

**Files:**
- Modify: `src/ddd/gui/server.py`
- Test: `tests/test_gui_server.py`

**Interfaces:**
- Consumes: `_Handler._send`, `_Handler._body`, `MAX_BODY`, `IDLE_SECONDS` and `_body_read`, as they are.
- Produces: `_Handler._declared() -> int | None`, `_Handler._linger: bool`, `_linger(connection: socket.socket) -> None`, `LINGER_SECONDS: Final = 2.0`.

- [ ] **Step 1: The tests of what changes.** In `TestABodyLeftUnread`:
  - Replace `test_a_post_refused_before_its_body_is_read_is_answered_once_and_closed` with the test below, parametrized as it was.
  - Change `test_a_misdirected_post_is_answered_once_and_closed` the same way: drained, answered once, kept open.
  - Rewrite the class's docstring to say the body is now read before such a refusal, so that nothing of it is ever read as a request, and nothing is left unread to reset the connection (P18-31).

```python
    def test_a_post_refused_before_its_body_is_read_drains_it_and_keeps_its_connection(
        self, server, target, headers, status
    ) -> None:
        """The body, a request smuggled inside it among them, is read as body and thrown away:
        answered once, the connection kept, and the next request on it answered as itself."""
        signed = f"Authorization: Bearer {server.token}\r\n"
        own = f"Origin: http://127.0.0.1:{server.port}\r\n"
        headers = headers.replace("SIGNED ", signed).replace("OWN ", own)
        refused = (
            f"POST {target} HTTP/1.1\r\nHost: 127.0.0.1:{server.port}\r\n{headers}"
            f"Content-Length: {len(self.SMUGGLED)}\r\n\r\n"
        ).encode("ascii") + self.SMUGGLED
        following = (
            f"GET /api/session HTTP/1.1\r\nHost: 127.0.0.1:{server.port}\r\n"
            f"Authorization: Bearer {server.token}\r\n\r\n"
        ).encode("ascii")
        answered = every_answer(server, refused + following)
        assert answered.count(b"HTTP/1.1 ") == 2
        assert answered.startswith(f"HTTP/1.1 {status} ".encode("ascii"))
        assert b"\r\nConnection: close\r\n" not in answered
        assert b"HTTP/1.1 200 " in answered.partition(b"\r\n\r\n")[2]
```

- [ ] **Step 2: The lingering close's test,** beside `test_a_post_whose_length_is_refused_is_answered_once_and_closed`, which stays as it is:

```python
    def test_a_post_too_long_to_read_is_answered_whole_while_its_body_still_arrives(
        self, server
    ) -> None:
        """Refused before a byte of it is read, its body still arriving: the answer is written,
        the writing side shut, and what arrives drained before the close, so that the close is
        no reset that throws the answer away before it is read (P18-31) - which windows did."""
        head = posted(server, str(MAX_BODY + 1)).replace(b"Connection: close\r\n", b"")
        with socket.create_connection(("127.0.0.1", server.port), timeout=10) as connection:
            connection.sendall(head)

            def send_the_body() -> None:
                # Still sending when the answer comes, as a browser posting a large body is: the
                # server stops reading, and whatever it does with what arrives decides whether
                # this side gets its answer or a reset.
                with contextlib.suppress(OSError):
                    connection.sendall(b"x" * (4 * MAX_BODY))

            sending = threading.Thread(target=send_the_body, daemon=True)
            sending.start()
            answered = b""
            while not answered.endswith(b"}"):
                chunk = connection.recv(65536)
                if not chunk:
                    break
                answered += chunk
        assert answered.startswith(b"HTTP/1.1 413 ")
        assert answered.endswith(
            json.dumps({"error": "too-large", "message": f"a request body is at most {MAX_BODY} bytes"}).encode()
        )
```

  `tests/test_gui_server.py` imports `threading` already, but not `contextlib`: add it. Read the 413's sentence off the running code.
- [ ] **Step 3: Review Focus 2's test,** in the same class:

```python
    def test_a_refused_post_whose_body_never_comes_is_closed_after_the_idle_time(
        self, server
    ) -> None:
        """Declared 100 bytes, sent 10: the drain waits for the rest no longer than any
        connection waits, then closes it unanswered - no answer was written - and gives its
        slot back."""
        sent = (
            f"POST /api/edit HTTP/1.1\r\nHost: 127.0.0.1:{server.port}\r\n"
            "Content-Length: 100\r\n\r\n"
        ).encode("ascii") + b"x" * 10
        with socket.create_connection(("127.0.0.1", server.port), timeout=10) as connection:
            connection.sendall(sent)
            assert connection.recv(65536) == b""
        assert wait_for(lambda: server.slots._value == MAX_CONNECTIONS, seconds=5)
```

  Use the slot counting the module's other tests use: the cap's tests read the semaphore through a helper. Use theirs, and their own `wait_for`-style helper, if they have one. `briefly_idle` keeps the wait to half a second.
- [ ] **Step 4: Run them to see them fail.**
  - Run: `.venv/bin/python -m pytest tests/test_gui_server.py -k TestABodyLeftUnread --no-cov -p no:cacheprovider`
  - Expected:
    - the drain tests fail: the answer says `Connection: close`, and the following request is never answered;
    - the never-comes test fails: the refusal *is* answered today;
    - the lingering test may pass on Linux, which delivers what it holds before a reset. Its red is Windows': see step 8.
- [ ] **Step 5: The drain.** In `src/ddd/gui/server.py`:
  - next to `MAX_BODY`, add:

```python
LINGER_SECONDS: Final = 2.0
"""How long a connection closed with a body still arriving is drained before its close (P18-31):
long enough for a browser to finish sending what it declared, short enough that a sender who
never stops holds its thread no longer."""
```

  - in `_Handler`, beside `_body_read`, add:

```python
    _linger = False
    """Whether this connection is closed with a request's body unread - too long to read, or of
    no length to read by. Its answer is written, its writing side shut, and what still arrives
    drained before the close (:meth:`finish`), so that the close is no reset."""

    def _declared(self) -> int | None:
        """The request's ``Content-Length``, if it is one this server reads: a length, of at most
        :data:`MAX_BODY`. ``None`` for none, or for one past it."""
        length = self.headers.get("Content-Length", "0")
        if not (length.isascii() and length.isdecimal()):
            return None
        significant = length.lstrip("0") or "0"
        if len(significant) > len(str(MAX_BODY)) or int(significant) > MAX_BODY:
            return None
        return int(significant)
```

  - in `_send`, replace the `if self.command == "POST" and not self._body_read:` block with:

```python
        if self.command == "POST" and not self._body_read:
            # Refused before its body was read. A body this server would have read is read now
            # and thrown away: nothing of it is then read as the next request, and nothing is
            # left unread to make closing the connection a reset (P18-31). One it would not -
            # too long, or of no length - is left, the connection closed after this answer, and
            # what still arrives drained first (finish).
            declared = self._declared()
            if declared is None:
                own["Connection"] = "close"
                self._linger = True
            else:
                self.rfile.read(declared)
                self._body_read = True
```

  - after `_send`, add:

```python
    def finish(self) -> None:
        super().finish()
        if self._linger:
            _linger(self.request)
```

  - at module level, after `_refuse`, add:

```python
def _linger(connection: socket.socket) -> None:
    """Shut the writing side of a connection closed with a body still arriving, and drain what
    arrives - for at most :data:`LINGER_SECONDS` and :data:`MAX_BODY` bytes - before the close,
    so that the close is no reset that could throw the answer away before the client reads it
    (P18-31). Run on the connection's own thread, never the one that accepts (`_refuse`)."""
    with contextlib.suppress(OSError):
        connection.shutdown(socket.SHUT_WR)
        deadline = time.monotonic() + LINGER_SECONDS
        drained = 0
        while drained <= MAX_BODY:
            left = deadline - time.monotonic()
            if left <= 0:
                return
            connection.settimeout(left)
            chunk = connection.recv(65536)
            if not chunk:
                return
            drained += len(chunk)
```

  `_body` can read its length through `_declared` where the two agree. Keep its two refusals, 400 for no length and 413 for one past `MAX_BODY`, with their sentences unchanged.
- [ ] **Step 6: Run the tests to see them pass,** then cover every branch of `_linger`: an end of file, a timeout, and the byte cap. Monkeypatch `LINGER_SECONDS` and `MAX_BODY` small where a test needs it.
- [ ] **Step 7: Ablate.**
  - Take out the drain's `self.rfile.read(declared)`: the drain test dies.
  - Take out the `finish` override.
  - Make `LINGER_SECONDS` 0: on Linux nothing may die. Say so in the report; Windows is where it dies.
  - Change the byte cap to `< 0`.

  Ablate in a scratch worktree (Global Constraints).
- [ ] **Step 8: The Windows red, then green.**
  1. Commit the lingering test alone first, in its own commit, with step 5's code not yet in it. Report to the controller, who pushes and starts a full run. The Windows test legs show whether it fails there.
  2. Then commit the fix. The controller runs again, and the Windows legs pass.
  3. Report both runs' lines. If the Windows legs pass even without the fix, say so: *Figures* records that the reset was not reproduced, and the test stays as the pin of the drain.

  If the step 8 split is impractical, commit in the order red test, then fix, so that the history shows both.
- [ ] **Step 9: The whole Python gate,** each exit status captured.

### Task 5: `[::1]` held

**Model:** opus. Socket options that differ by system.

**Files:**
- Modify: `src/ddd/gui/server.py`
- Create: `gui/e2e/localhost.spec.ts`
- Test: `tests/test_gui_server.py`

**Interfaces:**
- Consumes: `GuiServer.__init__`, `server_bind`, `server_close`, `run`, `_refused`, `is_loopback`.
- Produces: `IPv6Held(OSError)`, `GuiServer.held`, `_held_beside`, `_EXCLUSIVE`, `PORT_TRIES`.

- [ ] **Step 1: The failing tests.** Add `class TestIPv6Held` to `tests/test_gui_server.py`. Each test uses real sockets except where it says otherwise:
  - `test_ipv6_is_held_beside_the_port`:
    - with a `GuiServer` started on port 0, binding `("::1", server.port)` from the test raises `OSError`, with and without `SO_REUSEADDR` set on the test's socket;
    - a connection to `("::1", server.port)` raises `ConnectionRefusedError`.
  - `test_the_hold_ends_with_the_server`: after `server_close()`, `("::1", port)` binds.
  - `test_a_fixed_port_held_on_ipv6_is_refused_naming_it`:
    1. the test binds a free port on `127.0.0.1` and closes it;
    2. it binds `("::1", that port)` and keeps it;
    3. it calls `run(None, (), that_port, open_browser=False, static=<the compiled pages>)` with `capsys`.

    It asserts `EXIT_USAGE` and the whole stderr line, read off the running code. Expected shape: `ddd: cannot serve 127.0.0.1 on port <p>: another program holds [::1]:<p>, where a browser opening localhost:<p> would reach it`.
  - `test_port_zero_tries_again_when_ipv6_is_held`: monkeypatch `module._held_beside` to raise `IPv6Held` on its first call and delegate after. `run` serves on a second port, with nothing printed about the first.
  - `test_port_zero_gives_up_after_its_tries`: `_held_beside` always raises. `run` answers `EXIT_USAGE` with the sentence after `PORT_TRIES` attempts, counted by the patch.
  - `test_no_ipv6_loopback_holds_nothing_and_says_nothing`, two cases monkeypatched:
    - creating an `AF_INET6` socket raises `OSError(errno.EAFNOSUPPORT, ...)`;
    - binding `::1` raises `OSError(errno.EADDRNOTAVAIL, ...)`.

    `_held_beside` answers `None` for each, and the server starts.
  - `test_beyond_loopback_holds_nothing`: `_held_beside("0.0.0.0", port)` is `None`, and `_held_beside("192.0.2.1", port)` is `None`.
  - `test_windows_binds_both_sockets_exclusively` and its counterpart: monkeypatch `module._EXCLUSIVE` both ways, and record `setsockopt` calls with a socket stand-in. True gives `_SO_EXCLUSIVEADDRUSE` on both the IPv4 and the `[::1]` socket; False gives it on neither. The `[::1]` socket never gets `SO_REUSEADDR` either way. Linux refuses the option's value, so the stand-in records it instead of setting it.
- [ ] **Step 2: Run them to see them fail.**
  - Run: `.venv/bin/python -m pytest tests/test_gui_server.py -k TestIPv6Held --no-cov -p no:cacheprovider`
  - Expected: every test fails. `IPv6Held` and `_held_beside` do not exist, and `[::1]` binds freely beside a running server.
- [ ] **Step 3: The hold.** In `src/ddd/gui/server.py`, add `import errno` to the imports if it is not there, and near `MAX_CONNECTIONS`:

```python
_EXCLUSIVE: Final = sys.platform == "win32"
"""Whether a socket is bound with ``SO_EXCLUSIVEADDRUSE``: on Windows, where one bound without it
can be shared by another that sets ``SO_REUSEADDR``. A flag, so that the suite takes both
branches on every platform (``test_nothing_in_the_suite_skips``)."""

PORT_TRIES: Final = 5
"""How many ports ``--port 0`` is tried on before ``[::1]`` held on each of them is a refusal."""

_SO_EXCLUSIVEADDRUSE: Final[int] = getattr(socket, "SO_EXCLUSIVEADDRUSE", -5)
"""Windows' own option, which typeshed declares on win32 alone, so read rather than named for mypy
on every platform; -5 is its value there, ``~SO_REUSEADDR``. Used only where :data:`_EXCLUSIVE`."""

_IPV6_HELD: Final = "another program holds [::1]:{port}, where a browser opening localhost:{port} would reach it"


class IPv6Held(OSError):
    """``[::1]`` held by another program on the port ``ddd gui`` was to serve on."""


def _held_beside(host: str, port: int) -> socket.socket | None:
    """``[::1]`` bound on ``port`` beside a loopback ``host``, and never listened on (spec §6.2):
    no other program can then take ``localhost`` there, and a browser trying ``[::1]`` first is
    refused, and falls back to ``127.0.0.1``. ``None`` where nothing need or can be held - a
    host beyond loopback, or a computer with no IPv6 loopback. Raises :class:`IPv6Held` where
    another program holds it."""
    if not is_loopback(host):
        return None
    try:
        held = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    except OSError:
        return None
    try:
        held.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        if _EXCLUSIVE:
            held.setsockopt(socket.SOL_SOCKET, _SO_EXCLUSIVEADDRUSE, 1)
        held.bind(("::1", port))
    except OSError as error:
        held.close()
        if error.errno == errno.EADDRNOTAVAIL:
            return None
        raise IPv6Held(error.errno, _IPV6_HELD.format(port=port)) from error
    return held
```

  In `GuiServer`:
  - add the class attribute `held: socket.socket | None = None`, with a docstring;
  - at the end of `__init__`'s binding, right after `super().__init__((host, port), _Handler)`:

```python
        try:
            self.held = _held_beside(host, self.port)
        except IPv6Held:
            self.server_close()
            raise
```

  - add:

```python
    def server_bind(self) -> None:
        if _EXCLUSIVE:
            self.socket.setsockopt(socket.SOL_SOCKET, _SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

    def server_close(self) -> None:
        super().server_close()
        if self.held is not None:
            self.held.close()
```

  In `run`, replace `server = GuiServer(Api(session, project), pages, port, address)` and its `except OSError` with a loop:

```python
        for attempt in range(1, PORT_TRIES + 1):
            try:
                server = GuiServer(Api(session, project), pages, port, address)
                break
            except IPv6Held as error:
                # --port 0 picked a port whose [::1] another program holds: another pick is
                # another port. A port given is that port, or nothing.
                if port != 0 or attempt == PORT_TRIES:
                    return _refused(address, port, error)
            except OSError as error:
                return _refused(address, port, error)
```

  mypy may need `server` declared before the loop. Write it so mypy, and coverage of every branch, pass.
- [ ] **Step 4: Run the tests to see them pass,** then the whole server module.
- [ ] **Step 5: The journey.** Create `gui/e2e/localhost.spec.ts`:

```ts
import { createServer } from "node:net";
import { expect, test } from "./fixtures";

/** Whether a stranger can listen on `host` at `port`: the error it is refused with, or null. */
function listenRefusal(port: number, host: string): Promise<string | null> {
  return new Promise((resolve) => {
    const stranger = createServer();
    stranger.once("error", (error: NodeJS.ErrnoException) => resolve(error.code ?? "unknown"));
    stranger.listen(port, host, () => stranger.close(() => resolve(null)));
  });
}

test("localhost reaches ddd gui, and nothing else can listen on [::1] at its port", async ({
  page,
  gui,
}) => {
  const address = new URL(gui.address);
  const port = Number(address.port);
  // Held by ddd gui, never listened on (part 19a): the bind is refused - EADDRINUSE, or
  // EACCES where windows binds the port exclusively.
  expect(["EADDRINUSE", "EACCES"]).toContain(await listenRefusal(port, "::1"));

  // The browser tries [::1] first, is refused, and falls back to 127.0.0.1, where ddd gui
  // answers - on windows only after its own retries, which is what this journey's legs time.
  const token = address.searchParams.get("token");
  await page.goto(`http://localhost:${port}/open?token=${token}`);
  await expect(page.getByRole("button", { name: "Controller", exact: true })).toBeVisible();
});
```

  Run it locally (build first). On Linux, a `[::1]` that is free before the change must make the first assertion fail: check that red against the code before step 3, by stashing nothing. Run it from a commit made before step 3, or with `_held_beside` patched to answer `None` in a scratch copy, and say which.
- [ ] **Step 6: Ablate** in a scratch worktree:
  - the `[::1]` bind;
  - the `IPV6_V6ONLY` option;
  - the exclusive option, with its flag true;
  - the retry.

  Each must kill a named test.
- [ ] **Step 7: The gates:** the whole Python gate, and the journeys after a build.
- [ ] **Step 8: Commit, and the Windows proof.** The controller pushes and starts a full run. On the Windows legs the server tests must pass, and `localhost.spec.ts` must pass on all three legs. A failure there is read from its report, and fixed at its cause.

### Task 6: option C, the Files row the page was loaded with

**Model:** opus. Page glue, a lib decision, a story, a journey.

**Files:**
- Modify: `gui/src/app/useRoute.ts`, `gui/src/app/App.tsx`, `gui/src/screens/FilesPage.tsx`, `gui/src/components/FileActionsView.tsx`, `gui/src/components/FileActionsView.stories.tsx`, `gui/src/lib/files.ts`
- Test: `gui/src/lib/files.test.ts`, `gui/e2e/files.spec.ts`
- Create: the story's screenshot reference under `gui/screenshots/references/`

**Interfaces:**
- Consumes: `useRoute`, `FilesPage`'s `path` and `onPath`, `RemoveFile`, `useFilesPlan`, `RemoveFileView`.
- Produces: `useRoute(): [Route, navigate, arrived: boolean]`; `removalAsked(arrived, pressed)`; `RemoveFileViewProps.waiting?: () => void`.

- [ ] **Step 1: The failing Vitest case.** In `gui/src/lib/files.test.ts`:

```ts
describe("removalAsked", () => {
  it("asks at once for a row the reader reached within the page", () => {
    expect(removalAsked(false, false)).toBe(true);
  });
  it("waits for the press on the row the page was loaded with", () => {
    expect(removalAsked(true, false)).toBe(false);
  });
  it("asks once the reader presses for it", () => {
    expect(removalAsked(true, true)).toBe(true);
  });
});
```

  Run `npm test -- src/lib/files.test.ts`, and expect it to fail: `removalAsked` is not exported.
- [ ] **Step 2: The decision.** In `gui/src/lib/files.ts`, after `fileRemoval`:

```ts
/** Whether the Remove panel asks its plan now (P18b-10, spec §7). Its plan re-analyses the
 * project, running its plugins, so the row the page was loaded with - one a link from elsewhere
 * can name, or a bookmark, a typed address or a reload - waits for the reader's press; a row the
 * reader reached within the page, by the table, a link of its own, or back and forward, asks at
 * once. */
export function removalAsked(arrived: boolean, pressed: boolean): boolean {
  return !arrived || pressed;
}
```

  Run the case, and see it pass.
- [ ] **Step 3: The route.** In `gui/src/app/useRoute.ts`:

```ts
export function useRoute(): [
  Route,
  (route: Route, options?: { replace?: boolean }) => void,
  boolean,
] {
  const [route, setRoute] = useState(() =>
    parseRoute(window.location.pathname, window.location.search),
  );
  // Whether the route is still the one the page was loaded with - which a link from elsewhere,
  // a bookmark, a typed address or a reload chose - rather than one the reader reached within
  // the page. Any navigation, back and forward included, is the reader's.
  const [arrived, setArrived] = useState(true);
  useEffect(() => {
    const followHistory = () => {
      setArrived(false);
      setRoute(parseRoute(window.location.pathname, window.location.search));
    };
    window.addEventListener("popstate", followHistory);
    return () => window.removeEventListener("popstate", followHistory);
  }, []);
  const navigate = useCallback((next: Route, options?: { replace?: boolean }) => {
    if (options?.replace) {
      window.history.replaceState(null, "", hrefOf(next));
    } else {
      window.history.pushState(null, "", hrefOf(next));
    }
    setArrived(false);
    setRoute(next);
  }, []);
  return [route, navigate, arrived];
}
```

  Update its doc comment to say the third value. In `App.tsx`, take `arrived` from `useRoute()`, and pass it to `FilesPage` as `arrived={arrived}`.
- [ ] **Step 4: The panel waits.** In `FilesPage.tsx`:
  - `Props` gains `arrived: boolean`, documented;
  - `FilesPage` passes it to `RemoveFile`;
  - in `RemoveFile`:

```ts
  const [pressed, setPressed] = useState(false);
  const asked = removalAsked(arrived, pressed);
  const plan = useFilesPlan(asked ? removal.request : null, revision);
```

  and it passes `waiting={asked ? undefined : () => setPressed(true)}` to `RemoveFileView`. Update `RemoveFile`'s doc comment: its plan is asked as soon as the row is selected within the page, and on the reader's press for the row the page was loaded with.

  In `FileActionsView.tsx`:
  - `RemoveFileViewProps` gains `waiting?: () => void`, documented as "the press that asks the plan, present while it waits";
  - `RemoveFileView` renders, while `waiting` is set, this in place of `<Preview …/>`:

```tsx
        {props.waiting !== undefined ? (
          <>
            <p className="quiet">
              Opened from an address: what removing it would change is planned when you ask.
            </p>
            <Button variant="secondary" onPress={props.waiting}>
              Plan its removal
            </Button>
          </>
        ) : (
          <Preview … />
        )}
```

  `Button` is the house component the panels use, so read its import from a sibling view. The words are this plan's; if the house style of a panel's quiet line differs, keep the meaning and say what changed.
- [ ] **Step 5: The story and its reference.** In `FileActionsView.stories.tsx`, add a story of `RemoveFileView` waiting, beside the existing Remove story, with the same fixture and `waiting={() => {}}`. Name it so that its id reads `remove-waiting`.
  - Build Ladle, then run `UPDATE=1 docker compose run --rm gui-screenshots` from the repository root.
  - Exactly one reference is added. Run compare mode once more, and none may move.
  - Open the new PNG and say what it shows, quoting its words.
- [ ] **Step 6: The journey.** In `gui/e2e/files.spec.ts`, add the test below. Read the panel's accessible name, the allowed row's key spelling, and the plan's visible offer from the file's own first test, which removes `units.ddd.json`, and use them as it does:

```ts
test("the row the page was opened on waits for the reader before its removal is planned", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await expect(page.getByRole("button", { name: "Controller", exact: true })).toBeVisible();
  const planned: string[] = [];
  page.on("request", (request) => {
    if (new URL(request.url()).pathname === "/api/files-plan") planned.push(request.url());
  });

  // Loaded at the row's own address, as a link from elsewhere would load it: nothing that runs
  // a plugin is asked until the reader asks (P18b-10).
  const key = `${gui.directory.replaceAll("\\", "/")}/units.ddd.json`;
  const origin = new URL(gui.address).origin;
  await page.goto(`${origin}/project?view=files&path=${encodeURIComponent(key)}`);
  const ask = page.getByRole("button", { name: "Plan its removal" });
  await expect(ask).toBeVisible();
  expect(planned).toEqual([]);

  await ask.click();
  await expect(page.getByRole("button", { name: "Show changes" })).toBeVisible();
  expect(planned).toHaveLength(1);

  // A row the reader selects in the table is planned at once, as before.
  await page.getByRole("row", { name: /constants\.ddd\.json/ }).click();
  await expect.poll(() => planned.length).toBe(2);
  await expect(page.getByRole("button", { name: "Plan its removal" })).toHaveCount(0);
});
```

  Review Focus 4 is the last two assertions. Also run the case of pressing the arrived row itself in the table: press `units.ddd.json`'s own row instead of the button. One plan is asked, and no button stays.
- [ ] **Step 7: The gates:**
  - lint, typecheck, and Vitest at 100 % on all four;
  - build and Ladle;
  - the screenshots in compare mode;
  - the journeys, all of them, after the build.
- [ ] **Step 8: Ablate the page in place,** with the Global Constraints' care:
  - `removalAsked` returning `true` always: the journey and the case die;
  - `setArrived(false)` taken out of `navigate`;
  - `setArrived(false)` taken out of `popstate`.

  Name what dies for each.
- [ ] **Step 9: Commit.**

### Task 7: what the security page and the CHANGELOG say

**Model:** sonnet, reviewed on opus.

**Files:**
- Modify: `docs/gui_security.rst`, `CHANGELOG.md`, and the module docstring of `src/ddd/gui/server.py`.

- [ ] **Step 1: The security page.**
  - **The `localhost` bullet,** "The printed address, opened as something other than itself", under *What it does not defend against*. It goes, and its fact moves under *What it defends against*:
    - `ddd gui` holds `[::1]` on its port when it listens on loopback, so no other program can listen on `localhost` there;
    - a browser trying `[::1]` is refused, and falls back to `127.0.0.1`;
    - on Windows, both sockets are bound exclusively;
    - a fixed `--port` whose `[::1]` is taken is refused.
  - **The paragraphs on navigations from elsewhere,** in *The browsers it protects*. They now say what a page reached so still does: it signs itself in from its storage and opens at the address it was sent to. But the Files tab's Remove panel no longer asks its plan on arrival; it waits for the reader's press (option C). State only what Task 6 built.
  - **A refused `POST`.** Wherever the page speaks of a refused `POST` or a connection closed, make it true of the drain and the lingering close.
  - **Check every sentence** against the code, and against Tasks 4 to 6's tests. The route table's label and table stay untouched.
- [ ] **Step 2: The CHANGELOG.** Add three entries in the file's own style, under the unreleased section: the drain, the `[::1]` hold, and option C. Each is a bold lead, then two spaces after it and between sentences, with no line over 95 columns.
- [ ] **Step 3: The docstring.** Make `server.py`'s module docstring true of the hold and the drain.
- [ ] **Step 4: The gates:**
  - `tests/test_gui_docs.py` and `tests/test_documentation.py`, run with `--no-cov -p no:cacheprovider`;
  - the docs in Docker, under `-W`;
  - the whole pytest.
- [ ] **Step 5: Commit.**

### Task 8: the final hunt, the figures, the gate and the close-out

**The controller's own.**

- [ ] **Step 1: Push,** after the bidi scan. Start the final hunt (`-f repeat=5`), and record its table in *Figures*. It must pass with no failure on all three legs. A failure goes back to Task 3's procedure.
- [ ] **Step 2: The probes,** before (master `290fd9a`) and after (the branch's head):
  - a stranger listening on `[::1]` at `ddd gui`'s port, while `localhost:<port>/open?token=<token>` is opened in Chrome;
  - a Files row opened by its address: the `/api/files-plan` requests counted until the press.

  Record each in *Figures*, with the machine, the commit and the run.
- [ ] **Step 3: The milestone gate** at the head, each exit status captured.
- [ ] **Step 4: Close the plan out:**
  - an *As built* note under the header;
  - *Figures*;
  - the progress log;
  - *What was left open*;
  - *Rulings taken*.

## Milestone gate

Every command, each exit status captured on its own line:

```bash
rm -f .coverage .coverage.*
.venv/bin/python -m pytest > gate/pytest.txt 2>&1; echo "PYTEST=$?"
.venv/bin/ruff check . ; echo "RUFF=$?"
.venv/bin/ruff format --check . ; echo "FMT=$?"
.venv/bin/mypy ; echo "MYPY=$?"
cd gui
DDD=../.venv/bin/ddd DDD_PYTHON=../.venv/bin/python npm run schemas; echo "SCHEMAS=$?"
npm run lint; echo "LINT=$?"
npm run typecheck; echo "TSC=$?"
npm test; echo "VITEST=$?"
npm run build; echo "BUILD=$?"
npm run ladle:build; echo "LADLE=$?"
cd ..
docker compose run --rm gui-screenshots; echo "SHOTS=$?"
git status --short gui/screenshots/references      # must be empty
docker compose run --rm -e JAVA_TOOL_OPTIONS=-Duser.home=/tmp docs; echo "DOCS=$?"
cd gui && PLAYWRIGHT_CHANNEL=chrome DDD_PYTHON="$PWD/../.venv/bin/python" \
  npx playwright test --output=<scratch>/e2e; echo "E2E=$?"
```

Then:
- **The final hunt,** `gh workflow run ci.yml --ref feature/gui-journeys-every-platform -f repeat=5`, clean on all three legs.
- **The pull request's own CI,** every check green.

Before any push, scan the branch's commit messages and changed files for bidi characters.

## Figures

### The baseline hunt

Filled in after Task 1: the run, its commit, and each leg's runs and failures by journey.

| leg | runs | failures | by journey (error, cause) |
| --- | --- | --- | --- |

### The final hunt

Filled in by Task 8.

| leg | runs | failures |
| --- | --- | --- |

### Probes, before and after

Filled in by Tasks 4, 5 and 8.

| asked | before | after |
| --- | --- | --- |
| a refused `POST` past `MAX_BODY`, its body still arriving, on the Windows legs: the answer read whole? | | |
| a stranger listening on `[::1]` at `ddd gui`'s port, `localhost:<port>/open?token=` opened in Chrome | | |
| a Files row opened by its address: `/api/files-plan` asked before any press | | |
| the mapped drive on the Windows chromium leg | | |

## Progress log

| Task | Commits | Review | Notes |
| --- | --- | --- | --- |

## What was left open

Filled in as the work goes. Known before execution:
- **Every reader action without a journey,** about 49 of them: 19b's.
- **Firefox, Safari and macOS.**
- **The mapped drive on Python 3.13 and 3.14** (spec §8).
- **Part 18b's leftovers that are not this part's:**
  - a server that used the same port before, which is documented;
  - `Clear-Site-Data`;
  - a fresh origin each run;
  - Subresource Integrity.

## Rulings taken

Taken while planning; execution adds its own below them.

1. **CI first, then the baseline hunt, before any fix.** The baseline then measures the journeys as master has them, on the three legs the fixes will be judged on — cost if wrong: one hunt's time.
2. **The hunt is `ci.yml`'s own `repeat` input, not a workflow of its own.** `workflow_dispatch` runs a workflow only if its file is on the default branch, and `ci.yml` already is — cost if wrong: none.
3. **The Edge leg is a cell of the gui job's matrix, not a job of its own.** `dev-build` must list every job it waits for (`test_it_waits_for_every_other_job_of_the_run`), and a cell needs no entry there. Nothing requires the old check names: the repository's ruleset forbids only deletion and force-pushes — cost if wrong: none.
4. **`mapped.spec.ts` stays even if the runner refuses SMB.** The maintainer's check by hand then becomes one command — cost if wrong: a journey CI never runs.
5. **The drain lives in `_send`,** the one place every answer goes through. `_body`'s own refusals (400 and 413) take the lingering close through the same branch — cost if wrong: none.
6. **The lingering close runs in `_Handler.finish`,** on the connection's own thread. It never runs in `GuiServer.shutdown_request`, which the accepting thread also calls for the cap's 503 (`_refuse`): a linger there would hold every waiting connection — cost if wrong: none.
7. **`[::1]` is held in `GuiServer`,** beside the bind it already makes. `run` retries `--port 0` on `IPv6Held` alone, and only up to `PORT_TRIES` — cost if wrong: a start refused after five unlucky picks.
8. **"Arrived" is `useRoute`'s:** false after any `navigate` or `popstate`. The Files tab reads it, and no other tab needs it (spec §7) — cost if wrong: one click after a reload, on the Files tab alone.
9. **The flakes are fixed one commit per cause,** each naming the run and the leg whose trace showed it — cost if wrong: a longer history.
10. **Only the controller pushes,** and only this branch. An implementer's Windows proof is a run the controller starts and hands back — cost if wrong: a slower loop.

### Taken during execution
