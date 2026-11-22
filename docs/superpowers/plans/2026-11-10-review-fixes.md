# Fixing the complete review of 2026-11-03

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:subagent-driven-development to
> implement this plan branch by branch, one agent at a time. Steps use checkbox (`- [ ]`) syntax
> for tracking.

**Goal:** close the findings that stand after the 2026-11-03 complete review was verified: 12
Critical, 131 Important and 311 Minor. The twelve Criticals go first, so that 0.12.0 can be released
after the first wave. Findings that a decision below defers, or leaves to the maintainer, are listed
under *Not in any branch*.

**Architecture:** sixteen stacked branches in three waves, merged in the order below. They stack
because nearly all of them add to `CHANGELOG.md`, and most edit `SPEC.md` or a page under `docs/`.
Each branch retargets to master as the previous one merges. That is the convention the earlier
reviews' fixes used: the 2026-09-15 review's were PRs #34 to #42.
- **Wave 1, branches 1 to 8:** what can lose a file, ship a wrong value or address, leave a build
  stale or pass a delivery that breaks its readers. Then the server's hardening and the release
  notes. Once wave 1 has merged, releasing 0.12.0 is the maintainer's call. Pass 20's advice was:
  "stop adding, fix what can lose a file or ship a wrong a2l, correct the changelog, and release".
- **Wave 2, branches 9 to 13:** the rest of the code, area by area.
- **Wave 3, branches 14 to 16:** the structure, the documents and the tests. They come last, so that
  they describe and pin the code as fixed.

**Tech stack:**
- **Core:** Python 3.12 to 3.14, pydantic v2, jinja2, pytest with a 100 % line-and-branch gate, ruff,
  mypy strict.
- **Docs:** sphinx with `-W`.
- **Build:** CMake from 3.20, or 3.30 for the collected mode, with Ninja and, after branch 2,
  Makefile generators.
- **Page:** React 19 and TypeScript, Vitest at 100 % over `src/api`, `src/lib` and `src/state`, and
  Playwright journeys.
- **Editor:** the VS Code extension in TypeScript.
- **Images:** DWARF through pyelftools.

**Spec:** the review itself, on the local branch `review/complete-review-2026-11-03` at `6a35b64c`.
- **The branch is not on GitHub** (decision M4). It is on the Linux PC, and the Windows PC holds its
  own copy.
- **Reading it:**
  - the whole review: `git show
    review/complete-review-2026-11-03:docs/superpowers/reviews/2026-11-03-complete-review.md`;
  - one pass, for example pass 13: `git show
    review/complete-review-2026-11-03:docs/superpowers/reviews/2026-11-03-kit/reports/pass-13.md`;
  - its verification: the same path with `verify-13.md`.
- **Naming:** a finding is named by its pass and its id, as the review names it: `13:C1` is pass 13's
  first Critical.
- **What specifies a task:** the finding's section gives the trigger, the evidence, the anchored lines
  and the proposed change. The finding's row in its verification's `verdicts` block, and the paragraph
  under that block, can correct it. Read both: together they are the specification of the task that
  names the finding.
- **Line numbers** are at master `2b4bae6c`, the tree the review read. Master has not moved since.
- **Evidence:** the review's scratch transcripts and scripts are on the Windows PC only, untracked, in
  `C:\git\ac11\ddd\.claude\review-2026-11-03-scratch`. Two probe files are in the kit's `probes/`:
  `test_p22_probes.py` and `p23-probes.spec.ts`.

## Global constraints

Every task's requirements include this section.

**Running things**

- **The machine.** The work runs on the Linux development PC, in the main checkout
  `/home/sauci/Documents/Github/ddd`. Docker cannot see the session scratchpad.
- **Interpreters.** There is no `python` on PATH: use `.venv/bin/python`. Node is at
  `~/.local/node-v24.21.0/bin`, also off PATH.
- **Never add `-q` to pytest.** `pyproject.toml:118` already sets it in `addopts`. A second one
  removes the `N passed` line while pytest-cov still prints its coverage line, so the output looks
  fine and proves nothing.
- **A pipeline reports its last command's exit status.** Capture each tool's own:
  `.venv/bin/python -m pytest > gate.txt 2>&1; echo "EXIT=$?"; tail -n 3 gate.txt`. A finished run
  ends with its summary line. If the coverage summary is missing, delete `.coverage*` and run again.
- **Journeys** drive the compiled pages in `src/ddd/gui/static`, so build first:
  `cd gui && npm run build`, then
  `PLAYWRIGHT_CHANNEL=chrome DDD_PYTHON="$PWD/../.venv/bin/python" npx playwright test --output=<a path outside the repository>`.
  Never run them while a Docker screenshot run is going.
- **Docker** builds four things. Run each from the repository root:
  - the screenshots: `UPDATE=1 docker compose run --rm gui-screenshots`, which compares instead when
    `UPDATE` is not set;
  - the docs: `docker compose run --rm -e JAVA_TOOL_OPTIONS=-Duser.home=/tmp docs`;
  - the ELF fixtures: `docker compose run --rm elf-fixtures`;
  - the address fixtures: `docker compose run --rm address-fixtures`.
- **Page schemas:** `cd gui && DDD=../.venv/bin/ddd DDD_PYTHON=../.venv/bin/python npm run schemas`.
- **Stopping a server you started:** list its PID by process name
  (`ps -eo pid,comm,args | awk '$2 ~ /^python/ && /<pattern>/'`), then `kill <pid>` as a separate
  command. Never `pkill -f` or `pgrep -f`: the pattern matches the shell running them.
- **Other containers on this PC belong to other work** (a model proxy, a notebook server). Leave
  them alone.
- **Never route around a refusal.** Stop and say so in your report.
- **Delete only what you created,** by its exact path.

**Windows**

- **Windows proof comes from CI** unless the maintainer runs it on the Windows PC.
  - Only the controller pushes, and only the branch in work. Never master, never `--force`.
  - A full run is `gh workflow run ci.yml --ref <branch> -f repeat=1`. Wait on it once, in the
    background, and read it with `gh run view <run> --json jobs`.
- **What the Windows legs exercise:**
  - Windows refuses to rename over, or delete, a file that another handle holds. `REPLACE_TRIES` in
    `src/ddd/editing.py` retries the rename.
  - Windows has a read-only flag where Linux has a mode.
  - The console code page is not UTF-8.
  - `.gitattributes` checks files out with LF on every leg.
- **A stock Windows without long paths is a supported development machine** (decision 22.2).

**Gates**

- **Python:** `.venv/bin/python -m pytest` at 100 % line and branch, `.venv/bin/ruff check .`,
  `.venv/bin/ruff format --check .`, and `.venv/bin/mypy` run bare.
- **Page:** `npm run lint && npm run typecheck && npm test && npm run build && npm run ladle:build`.
  Then the journeys, when a task touched the page or its server.
- **Docs:** the Docker docs build with `-W`, whenever a page changed.
- **No escapes:** no `pragma: no cover`, no skips, no xfails (`test_nothing_in_the_suite_skips`).
  No commit leaves a gate red.
- **CI runs more than this PC does:** Python 3.12, 3.13 and 3.14 on ubuntu and windows, and the
  journeys on three legs.

**What the gates cannot see**

- **Tests first.** Each task first writes the test that fails on the defect, and sees it fail for the
  finding's reason. Then the fix, then the run.
  - Where the review left a probe, port it into the suite and start from it (decision 22.1). The probe
    named in a task is the one to port.
  - A task whose finding needs a second actor builds that actor in its test: a second writer, a save
    inside the window, a second image, a buffer unlike the disk, or a closed stream.
- **Ablation:**
  - Ablate Python in a scratch `git worktree`, run pytest from inside it with
    `PYTHONDONTWRITEBYTECODE=1`, and restore by exact edit.
  - Ablate the page in a scratch copy, never in place.
  - Confirm that one ablation kills something before trusting that another kills nothing.
  - Believe a survival only after `PYTHONHASHSEED` 0, 1, 4 and 7.
  - Never conclude what else pins something from a narrowed run.
- **A coverage gate cannot see data.** Ablate every new sentence, header or default, and confirm that
  a named test dies.
- **No domain decision in a `.tsx` file** (decision 3.5). Nothing a test should reach lives in a
  screen: judgements go in `gui/src/lib`, `gui/src/state` or `gui/src/api`, under the Vitest gate.
- **Journeys:**
  - Wait on what the reader sees, and keep `retries` at 0.
  - Drive a field that handles keys (grid cells, choosers, type-to-find) key by key, with
    `pressSequentially` (decision 23.2). `.fill()` stays for plain inputs.
- **A sentence stating a measurement gets that measurement run, as written,** against the file it
  names.

**Interfaces and documents**

- **The changelog.** A behaviour change gets a `## Unreleased` entry saying what changed and what the
  migration costs, when it touches the public interface the changelog preamble defines:
  - check identifiers, command names and options, and the json formats;
  - the signatures of `ddd_generate()` and `ddd_add_component()`, and the names a template renders
    from;
  - and, from this plan on, the plugin api (decision 4.4).
- **A rule that changes reaches all of its homes:**
  - `SPEC.md`;
  - the model docstring, which is published in `schemas/`: regenerate it with `ddd schema <kind>`,
    since `tests/test_documentation.py` compares them byte for byte;
  - the file-format or reference page, and the changelog.

  After branch 15 the README is no longer one of those homes (decision M6).
- **Cite by name, not by line number.** The review's lines go stale as the earlier branches land.

**Conventions**

- **Commits:** a lowercase imperative subject on one line, with no `feat:`-style prefix, and a body
  saying why. The trailer names the model that wrote the commit. Never `--amend`, never rebase.
  Implementers never push.
- **One commit per task,** pushed by the controller as each lands. The maintainer reviews on GitHub.
- **No pull request is opened without asking.** Each branch's PR lists the findings it closes and the
  decisions it applies.
- **Every UI pull request embeds screenshots of what it changed,** the maintainer's standing rule.
  Use the reference PNGs at the head SHA, each opened, looked at and described in a sentence.
- **One agent at a time,** the maintainer's standing rule (part 19c's ruling 8). That covers
  implementers, reviewers and pre-flights alike.
- **The review stays off GitHub** (decision M4):
  - never push `review/complete-review-2026-11-03`;
  - never quote a report into a commit, a pull request or this plan;
  - branch 7's commits and pull request say what changed, by finding id, and not how to reach what was
    there.
- **Bidi characters.** Before any push, the controller scans the commit messages and the changed
  files for U+202A to U+202E and U+2066 to U+2069.
- **If a brief or this plan is wrong, say so in the report** rather than working around it.

## Decisions

### Asked of the maintainer, answered on 2026-11-10

- **M1. Readers may be precompiled** (pass 1 question 1, pass 7 question 1). A delivered component's
  readers can be binaries compiled against the previous headers.
  - So a moved layout cannot replace: 1:C3 and 7:C1 stay Critical.
  - Turning `volatile` on is an error for an object somebody reads.
  - So is renaming it.
  - 7:I2 stands.
- **M2. `--const-inputs` is removed** (pass 1 question 2), with a migration line: 1:C1.
- **M3. The GUI refuses a whole number past 2^53** (pass 3 question 1). A typed or pasted value that a
  double cannot hold is refused, and the grid says it cannot show one. Pass 3's move 1 (cells as exact
  text) is not made.
- **M4. The review was taken off GitHub** (pass 20 question 3). Done on 2026-11-10: the remote branch
  was deleted after a local branch was made at the same commit. The three older review branches stay,
  since their findings are fixed.
- **M5. No second client is planned** (pass 2 question 1). So only pass 2's moves 0 to 4 and 10 are
  made. 2:I1, 2:I3, 2:I8 and 2:M11 are deferred, and so is the load-gate-analyse half of 2:I7.
- **M6. The README becomes short, one home per fact** (pass 4 question 3): 4:I10.
- **M7. `ddd gui` is treated like `make`, and refuses edits to a plugins list** (pass 12 questions 1
  and 2).
  - The security page says that `ddd gui` runs what the project names.
  - `POST /api/edit` refuses any change to a `plugins` list, so the token no longer chooses the code
    that runs.
- **M8. The GUI edits a scalar's value and a variable's description** (pass 16 question 1). Renaming
  and scope stay in the editor, and the panel says so: 16:I4.

### Taken here

Each answers a review question, with the reason in a few words. Each is a line or two to reverse,
and the changelog says what was chosen.

- **Pass 1:**
  - **1.3:** a consumer's restatement is a format change, so it needs a design of its own before 1.0.
    Not in this plan.
  - **1.4:** the same holds for which of 1:I13's objects DDD expresses. 4:I2's adoption page states
    today's limits instead.
  - **1.5:** the a2l gets a fragment hook, not a model of `MEMORY_SEGMENT`, `EPK` and the XCP block,
    as the reviewer advised (1:I8).
  - **1.6:** floating point counts stay as they are until a calibration tool has read one. That is
    the maintainer's hour with CANape or INCA.
- **Pass 2:**
  - **2.2:** nothing outside the repository imports `ddd.lsp`, `ddd.editing` or `ddd.gui` (ptf was
    ruled out). So moves 1 to 3 leave no shim, and the changelog names the modules that moved.
  - **2.4:** `ddd.gui.api.Api` stays internal, as it is documented.
  - **2.5:** an id goes after `name`, where `ddd id` writes it (2:M7).
- **Pass 3:**
  - **3.2:** `settle` and `type-plan` get a judge (3:I1).
  - **3.3:** a settlement with no stated `limits` writes on the producer alone, which keeps "a consumer
    defers" (3:I2).
  - **3.4:** one panel per vocabulary stays. `useOffers` is made anyway (3:I6).
  - **3.5:** the rule becomes "no domain decision in a `.tsx`, and nothing a test should reach"
    (3:I7).
  - **3.6:** a table past about 10,000 counts is not one the GUI takes. 3:I8 becomes a sentence in the
    refusal and in the guide.
- **Pass 4:**
  - **4.1:** SPEC gets a short section 7.4 on what a project may rely on from `ddd gui`. Its screens
    stay out (4:I9).
  - **4.2:** the design records stay on master and gain an index page, off the site. Moving them to an
    orphan branch would be the maintainer's call.
  - **4.4:** the plugin api is public, since the docs teach it and an example ships with it. It joins
    the changelog preamble (4:M13).
  - **4.5:** the GUI guide is written now, in branch 15, after the GUI branches have landed (4:I1).
- **Pass 5:**
  - **5.1:** `dump` and `generate --force` keep stopping at a loading error, and only the sentences
    change (5:I3).
  - **5.2:** a broken baseline no longer withholds a description candidate's findings or its renames.
    That aligns `compare` with `check --baseline` and makes 4.1 true as written (5:M4).
  - **5.3:** an instance is not a row of `ddd list`, and the concept row narrows (5:M3).
  - **5.4:** a sub-project may not state `point_counts`, and 3.1 says so (5:M1).
  - **5.5:** `init` compares as storage, `null` equal to explicit zeros. That follows the 2026-09-16
    plan's decision 1 (5:M10).
  - **5.6:** `compare` gets no `--standalone`, and 4.1 names `check --baseline --standalone` (5:M15).
- **Pass 6:**
  - **6.1:** the strict-mode residue stays deferred, as decision 10 of 2026-09-16 left it, and the
    published sentences say so (6:M10).
  - **6.2:** a member's `a2l` block on a nested structure is honoured (6:I1).
  - **6.3:** a string past the a2l's limits is a warning (6:I2).
- **Pass 7:**
  - **7.2:** `compare` is told when a side is a component file, and grades a removal by scope (7:I3).
    The mark a `dump --standalone` would need is a format change, so it is deferred.
  - **7.3:** relaxing a duplicate stays, with a note naming what was dropped and a winner chosen by
    code-point path order (7:M5).
  - **7.4:** a description baseline takes the project's `-W` relaxations, never its promotions
    (7:M12).
- **Pass 8:**
  - **8.3:** a derived limit rounds outward. The change lies within the tolerance `is_above` already
    grants, so archived baselines keep comparing clean (8:M1).
  - **8.4:** `RAT_FUNC` stays, and the artefacts page says it is a choice (8:M12).
- **Pass 9:**
  - **9.1:** the per-component headers are declared as `BYPRODUCTS` (9:C1).
  - **9.2:** `ddd_add_component` refuses a project file and names `PROJECT` (9:I3).
  - **9.3:** Makefile generators are supported, with a stamp output and a test cell (9:M6).
  - **9.4:** `ddd sources` lists what the project names, whether or not it loaded (9:I1).
  - **9.5:** stdout is LF on every system (9:M13).
- **Pass 10:**
  - **10.1:** the language server gets a net: each request is wrapped, answers `-32603` and writes the
    trace to stderr (10:I13).
  - **10.2:** a rename reaches every project that holds a touched file (10:I3).
  - **10.3:** the outermost description that includes a document answers for it, and a build record
    still wins (10:I2).
  - **10.4:** a rename is refused while an open document of the project differs from the disk
    (10:I4).
  - **10.5:** a multi-file edit carries `needsConfirmation` (10:I11).
  - **10.6:** the server registers the file watcher (10:M8).
- **Pass 11:**
  - **11.1:** the reader is for gcc and clang, and the pages say so. An odd type refuses the variables
    that reach it, not the whole image (11:M4).
  - **11.2:** a layout DDD cannot state is the warning `elf-layout` (11:I2, 11:I3).
  - **11.3:** a hostile image is in scope, as `elf.py` says (11:I6).
  - **11.4:** gcc LTO stays refused, and the build page says so (11:I7).
  - **11.5:** `SPEC.md` names the linkers it is tested with (11:I1).
- **Pass 12:**
  - **12.3:** the one-click browser stays. After M7 the token no longer chooses code, and the terminal
    line says what to do (12:I3).
  - **12.4:** 12:I1 takes the fix pass 12 measured.
  - **12.5:** there is no fresh origin per run (12:M9).
- **Pass 13:**
  - **13.1:** a read-only file is refused on every system (13:I4).
  - **13.2:** there is no lock file. The stage name of its own and the check before each rename make
    a second writer lose cleanly with `stale` (13:C2, 13:I1).
  - **13.3:** a rename or removal is refused while a file does not load (13:I2).
  - **13.4:** all-or-nothing does not survive a kill. The staged file is synced, and the contract says
    what a refusal guarantees (13:M1).
  - **13.5:** a button whose result would not load is withheld, and a panel's value is written and
    reported (13:I3).
- **Pass 14:**
  - **14.1:** the Compare tab's verdict includes the project's own errors (14:I1).
  - **14.2:** a changed plugin is reported, and the server asks for a restart (14:I4).
  - **14.3:** the headline counts statements, as `ddd check` does (14:M1).
  - **14.4:** a type on one side and the same thing spelled on the other is no disagreement (14:I3).
  - **14.5:** the budgets bind a plan on the Linux PC (14:I6).
- **Pass 15:**
  - **15.1:** a paste that drops a header row and column says so.
  - **15.2:** a single value pasted into a focused cell sets that cell.
  - **15.3:** text left in a chooser withholds Apply (15:I1).
  - **15.4:** the long poll asks again, after a delay (15:M1).
- **Pass 16:**
  - **16.2:** several typed cells make one plan (16:I3).
  - **16.3:** the target is keyboard use and a readable canvas. Every accessibility finding is fixed,
    each being small, and no WCAG level is claimed.
  - **16.4:** the 1,100 px measure stays, but not for the Graph or the values grid (16:M8).
- **Pass 17:**
  - **17.1:** a trailing `**` means directories, as SPEC says, on every Python (17:M5).
  - **17.2:** the conversion interface is not public, and its unused methods go (17:M6).
  - **17.3:** a lone surrogate is refused at the parser (6:M5, 17:M3).
- **Pass 18:**
  - **18.1:** a member's shape is capped like a declaration's (18:M1, 5:M16).
  - **18.2:** a reference is not a use, and the message says "declared as input by nobody".
  - **18.3:** a reader's `a2l.format` under a silent producer gets an `info`.
  - **18.4:** a member's change is reported per path, in numeric order (18:M7).
- **Pass 19:**
  - **19.1:** a closed pipe keeps the verdict, and a closed stderr is never 0 (19:I3).
  - **19.2:** the dictionary carries a block as the file spells it (`by_alias=True`) (19:I1).
  - **19.3:** a target that is not a regular file is written through (19:M9).
  - **19.4:** two `generate` runs into one directory at once are not supported, and SPEC 5 says so
    (19:M11).
  - **19.5:** `DDD_TRACEBACK` shows a plugin's traceback (19:M4).
- **Pass 20:**
  - **20.1:** wave 1 comes before the release. The advisory for 0.11.0 is the maintainer's to publish,
    and branch 8 drafts its text.
  - **20.6:** macOS is not claimed: the classifier lists Windows and Linux.
- **Pass 21:**
  - **21.1:** the example templates are held to the tool's standard, so the suite compiles what they
    render (21:M2).
  - **21.2:** a valid a2l is an invariant the suite tests (21:I2, 21:I3).
  - **21.3:** each check's default severity is part of the contract the suite pins (21:I4).
  - **21.4:** the two performance tests get a bound, and CI gets no durations job (21:M7).
- **Pass 22:**
  - **22.1:** a second actor is a rule. Every fix of passes 10, 13 and 19 lands with its probe (22:I1).
  - **22.2:** a stock Windows is supported, and the two longest-name tests change (22:M8).
  - **22.3:** `slow` marks `test_cmake` and `test_gui_server`, and the developer page gives the short
    loop (22:M9).
- **Pass 23:**
  - **23.1:** the decisions move into `lib/`, under the gate that already holds it (3:I7, 23:I2).
  - **23.3:** a stock Windows with Defender is a supported place for the journeys, so the fixtures get
    room in their bounds (23:M2).
- **Pass 24:**
  - **24.1:** `<target>.ddd` applies the default policy, and the build page says so (24:I1).
  - **24.2:** React Aria may close a chooser's list on a scroll, and the page keeps what was typed
    (24:M2).
- **Pass 25:**
  - **25.1:** `ddd tool from-elf --format json` stays as `dump` is, and the pages say so (25:M1).
  - **25.2:** the extension's README becomes a pointer, plus its settings table.

## Review focus

The failure modes most likely to bite a person that the findings' own tests would not reach. Each
has its test in the task named after it.

1. **A second writer during any GUI write, not only the three the review timed.** The second writer
   can be an editor's save, a second `ddd gui` or `ddd id --assign`, and it can land during a create,
   an undo or a multi-file rename. Each save landing before the write's last look at its file must
   be refused `stale` or kept beside the write, and never answered as written over. One landing
   between that look and the rename is still lost, since no lock of the file system closes that
   moment (*Left open*, branch 1). *(Branch 1, task 2: an undo and a create, each raced by a
   save.)*
2. **Windows.** A held handle, the read-only flag, the console's code page, a path past 260
   characters. *(Branch 1, task 5; branch 2, task 6; branch 16, task 6: on the windows legs.)*
3. **A project with one file that does not load.** Every plan, panel and count must say so, rather
   than act on the files that did load. *(Branch 1, task 7: a parametrised test over every plan
   route; branch 11, task 7: the banner.)*
4. **Values at the edge of their type:**
   - 2^53 and past it, the ends of 64 bits, `FLT_MAX`;
   - an enumerator at its enum's full width, `-0.0`, a limit rounded at the twelfth digit.

   *(Branch 3, task 1; branch 4, task 1; branch 5, task 8; branch 6, task 4: each with a table of
   edge values.)*
5. **The build after an edit.** A description changed, a plugin broken, a file matched or unmatched,
   under Ninja and under Make. Each must rebuild what it changed, and a second build must have
   nothing to do. *(Branch 2, task 1's story test, run for the triggers of tasks 3 and 4, on both
   generators.)*

---

## Wave 1: what loses a file, a value or a build

### Branch 1: `fix/edit-engine` (off `master`)

The writes of the GUI and of `ddd id`, and the plans that act on a project in a state they cannot
see. This branch carries three Criticals and pass 1's GUI one, 1:C4.

**Files:**
- `src/ddd/`: `editing.py`, `identity.py`, `file_names.py`, `loading.py` (what the analysis read),
  `variables.py`, `type_plans.py`, `shared_plans.py`, `declaration_plans.py`, `object_values.py`,
  `file_plans.py` and `finding_fixes.py`;
- `src/ddd/lsp/`: `edits.py` and `units.py`;
- `src/ddd/gui/`: `session.py`, `api.py` and `contract.py`;
- the matching `tests/test_*.py`, with `test_editing_at_once.py`;
- `docs/command_line_interface.rst` (the gui row), `SPEC.md` 7 and `CHANGELOG.md`.

- [x] **Task 1 (`13:C2`, Critical):** every writer stages under a name of its own beside the file
      (`tempfile.mkstemp` in the target's directory), in `editing.py` and in `identity.py`.
      `CREATED_NAME_MAX` and the test pinning the suffix follow. 22:M1 was refuted: that test pins a
      spelling and nothing more. Test: the probe
      `test_p13_c2_what_an_edit_answers_is_true_of_the_file_when_another_writer_stages`.
- [x] **Task 2 (`13:I1`, raised to Critical):** after staging, and immediately before each rename,
      compare the file's bytes with `original` again. A difference refuses `stale` and puts back what
      was already renamed. Tests:
      - the probe `test_p13_i1_a_save_landing_during_an_edit_is_refused_not_overwritten`;
      - for Review focus 1, an undo and a create, each raced by a save through the same seam.
- [x] **Task 3 (`13:C1`, Critical):** a revision fingerprints the bytes its analysis read.
      - The loader records a hash of the bytes it parsed for each file, and `_described` takes those
        rather than reading the file again.
      - The plans that point by index ask the in-place question the read routes ask: `rename_unit`,
        `describe_unit`, `remove_unit`, `rename_type`, `set_entry`, `rename_entry`, `remove_entry`,
        `set_cell`, `set_values` and `read_object`.

      Tests: the probes `test_p13_c1_a_revision_fingerprints_the_bytes_its_analysis_read` and
      `test_p13_c1_an_edit_planned_from_that_revision_is_refused_as_stale`, with
      `saving_while_analysing` in `tests/test_gui_session.py` making the trigger.
- [x] **Task 4 (`1:C4`, Critical):** `ddd gui` recognises a project the build generated, from the
      build record that names it or from a mark `cmake/Ddd.cmake` writes into it.
      - Every plan that would touch such a project's files is refused, with a sentence saying that
        membership is `ddd_add_component`'s.
      - A new description is offered only beside an existing source file, with the CMake line to add.

      Test: the review's `b/ddd/fw/Fw.ddd.json` project, where both the create and the include are
      refused with that sentence.
- [x] **Task 5 (`13:I4`, `13:M1`; decisions 13.1 and 13.4):**
      - A target this process may not write is refused before staging, on every system.
      - A stage is made writable before it is unlinked.
      - The staged bytes are `os.fsync`ed before the rename.
      - `contract.py`'s "made all at once, or not at all", and the page's sentence, say what a refusal
        guarantees, and that a killed server can leave part of an edit.

      Test (Review focus 2): a 0444 file on Linux is refused, its bytes and mode untouched and no stage
      left. On the windows legs, a read-only file is refused, and the next edit succeeds once the file
      is writable.
- [x] **Task 6 (`2:I6`, `13:I5`, `2:M7`; decision 2.5):** `identity.assign` builds `FileChange`s and
      calls `apply_changes`, keeping its insertion after `name`.
      - It then keeps a file's mode, writes through a symbolic link, and refuses what the loader
        refuses: a duplicated key, a `NaN`.
      - The GUI's id fix inserts after `name` too.

      Tests: `ddd id --assign` keeps a 0600 file at 0600; stamps a link's target and keeps the link;
      writes nothing to a file with a duplicated key, and says so.
- [x] **Task 7 (`13:I2`, `16:I10`, `14:M4`; decision 13.3):** while a file of the project does not
      load, every plan that renames or removes is refused, naming the file, as `rename_unit` already
      is: `_type_plan`, `_shared_plan`, `_settle`, and a declaration's removal.
      - A plan's refusal says that a file did not load, not "no such entry".
      - Branch 11 task 7 draws the page's side.

      Test (Review focus 3): one parametrised test over every plan route with `b.ddd.json` half
      saved. Each route answers 409 and names `b`.
- [x] **Task 8 (`13:I3`, `10:I7`; decision 13.5):** the text a plan computes is validated with the
      model of that file's kind before it is answered.
      - A quick fix or a button whose result would not load is withheld, in the GUI and in the editor
        alike (`finding_fixes.py` imports `lsp.edits.reconciliations`).
      - A panel's value whose result would not load is planned with a sentence saying so.

      Test: the three file-breaking fixes the verification reproduced are withheld. The panel's case
      is planned with its sentence.
- [x] **Task 9 (`13:I6`):** `declarable` leaves out a name that only locals hold. Test: W's local
      `Loc` is not offered to R.
- [x] **Task 10 (`13:M8`, `18:M3`):** adding a member to a one-line file, and `ddd id --assign` over a
      large file, become linear. Test: one that fails on quadratic growth without timing the machine,
      for example by counting the characters scanned at 1,000 and 4,000 declarations.
- [x] **Task 11 (`13:M2`, `13:M3`, `13:M4`, `13:M6`, `13:M7`, `13:M9`):**
      - `at` without brackets is refused.
      - Reading a conditional object carries its condition.
      - A short `init`'s cell past its end is set, the repair `object_values.py` promises.
      - A CRLF file keeps CRLF where no line break follows, and a bare CR reads as a line break.
      - A created file takes the project's newline and indent.
      - The Files tab writes includes with `/`, relative to the project.
      - A key holding the pointer grammar is refused, not answered 500.
- [x] **Task 12 (`13:M5`):** a stale refusal asks for an analysis, so a change of the same size and
      time is not stale for good.

### Branch 2: `fix/build-integration` (off branch 1)

Every way a build reports `no work to do` over stale artefacts, and the module's guards.

**Files:**
- `cmake/Ddd.cmake` and `examples/cmake/`;
- in `src/ddd/`: `loading.py` (`Workspace.sources`), `cli.py` (`sources`, `artefacts`, `_analyze`)
  and `plugins.py` (a package plugin's files);
- `tests/test_cmake.py`, `test_cli.py` and `test_plugins.py`;
- `docs/build_integration.rst` and `generated_artefacts.rst`, `SPEC.md` 7.1, and `CHANGELOG.md`.

- [x] **Task 1 (`9:C1`, Critical; decision 9.1):** the per-component headers are declared as
      `BYPRODUCTS`, with their names read at configure. `ddd_add_component` reads `component.name`,
      and `PROJECT` asks the tool. A renamed component needs a reconfigure, and the page says so.
      A story test, run under Ninja and, after task 7, under Make (Review focus 5):
      - change a variable's datatype in both descriptions and build once: the reader is recompiled,
        and the image reads the new value;
      - a second build has nothing to do;
      - an edit that leaves `Logger.h` alone recompiles `sensor.c` and not `logger.c`.
- [x] **Task 2 (`1:C2`, `1:I6`, Critical):** the `ADDRESS_MAP` flow gets the architecture
      `ADDRESSES_FROM_IMAGE` already has.
      - The generation before the link leaves the a2l out.
      - `<stem>_ddd_a2l` depends on the image and the map, and runs `generate a2l --address-map`.
      - An a2l written with no address source says so in a comment.

      Tests, under `STRICT`:
      - an array grown and built once gives an a2l holding this link's addresses;
      - an object added still builds;
      - a clean checkout's first build is said for what it is.
- [x] **Task 3 (`9:I1`, `19:I2`, `19:M8`; decision 9.4):** `ddd sources` lists every `.py` the
      project names, loaded or not, and every file of a package plugin.
      - `load_workspace` moves inside `_analyze`'s guarded block.
      - `sources` and `artefacts` report `plugin-invalid` beside their listing instead of exiting 2.
      - The module prints `ddd sources`' stderr as `message(WARNING)`, and its fallback keeps the
        project file a configure dependency.

      Tests: task 1's story for a plugin that stops importing, and for one whose model raises: the
      next build re-runs. `check --format json` still prints its document when a plugin model raises.
- [x] **Task 4 (`9:I2`):** each wildcard include is globbed with `CONFIGURE_DEPENDS`. The source list
      is written into the build tree only when it differs, as a dependency of the generation. Test:
      task 1's story for a file a pattern starts, then stops, matching.
- [x] **Task 5 (`9:I3`; decision 9.2):** `ddd_add_component` refuses a file whose top-level key is
      `project`, naming `PROJECT`. Test: the configure error and its sentence.
- [x] **Task 6 (`9:I4`, `9:I5`):**
      - The empty-keyword guard walks `ARGV<n>`, so `ADDRESS_MAP "${UNSET}"` and
        `PROJECT "${UNSET}"` are refused at configure.
      - `execute_process` reads `ddd sources` with `ENCODING UTF-8`.

      Tests: the two configure errors, and (Review focus 2) a `PROJECT` build under a non-ASCII
      directory name on the windows legs.
- [x] **Task 7 (`9:M4`, `9:M5`, `9:M6`, `9:M7`; decision 9.3):**
      - The release handshake is keyed on the tool's version as well as its path.
      - The dead fallback goes: the project file has to exist and parse at configure, and the page
        says so.
      - Makefile generators get a stamp output, and `tests/test_cmake.py` gets a Makefile cell.
      - The module's six edges are handled: a bracket in a path, a deleted output directory, a C++
        project, a helper in a subdirectory, a removed template's output, and a vocabulary generated
        later.
- [x] **Task 8 (`24:I1`; decision 24.1):** `<target>.ddd` applies the default policy. The build page
      says so: the "cannot drift apart" sentence goes, and a supplier is told that their check is not
      the build's.
- [x] **Task 9 (`9:M14`):** the small untrue or missing sentences of the command page and the build
      page.

### Branch 3: `fix/gui-values` (off branch 2)

What the page writes when a person types, picks or pastes a value.

**Files:**
- in `gui/src/`: `lib/objectValues.ts`, `valuePlot.ts`, `units.ts` and `undo.ts`; `ui/ComboBox.tsx`;
  `components/ValuesGridView.tsx`; `screens/VariablePanel.tsx` and `ValuesPage.tsx`; and
  `styles/ui.css`;
- in `src/ddd/`: `gui/contract.py`, `gui/api.py`, `object_values.py` and `variable_keys.py`;
- `tests/test_gui_api.py` and `test_object_values.py`;
- the Vitest files beside the libraries, `gui/e2e/values.spec.ts` and the probes from
  `p23-probes.spec.ts`;
- `gui/screenshots/references/`, and `CHANGELOG.md`.

- [x] **Task 1 (`3:C1`, Critical; decision M3):**
      - A whole number whose text a double cannot hold is refused where it is typed or pasted, in one
        sentence. That covers anything past 2^53, and a hexadecimal or binary spelling that would lose
        a bit.
      - The values route marks a block that holds such a value, and the grid says it cannot show it
        instead of drawing a rounded number.
      - The server refuses a plan's integral value at or past 2^53 for a 64-bit datatype.

      Tests (Review focus 4):
      - a Vitest table over 2^53 - 1, 2^53 + 1, `0x8000000000000001` and `18446744073709551615`;
      - pytest of the route's mark and of the server's refusal;
      - a journey on a `uint64` block holding `[9007199254740993, 18446744073709551615]`.
- [x] **Task 2 (`15:C1`, Critical):** `chosen`, `typed` and `edited` are held as `{key, value}`, and
      ignored while `key !== selected`. Test: the probe `p15-C1`.
- [x] **Task 3 (`16:C1`, lowered to Important):** a cell's `onKeyDown` keeps one-character keys from
      the table's type-to-find. Test: the probe `p16-C1`, typing 20, 5.1 and a 16x16 map's cell key
      by key.
- [x] **Task 4 (`15:I1`, `24:M2`; decisions 15.3 and 24.2):** while a chooser's text is not the
      settled value's label, Apply is withheld. A scroll that closes the list keeps what was typed.
      Tests: the probes `p15-I1` and `p15-I1b`, and a journey with a wheel notch between `km` and
      `/h`.
- [x] **Task 5 (`16:I1`, `16:I2`, `16:I3`; decision 16.2):**
      - A value cell is sized to its text.
      - The offer stays in view while a cell is open.
      - Several typed cells are planned as one table plan.

      Tests: the probe `p16-I2`, and a journey typing three cells and applying once.
- [x] **Task 6 (`16:I4`; decision M8):** a scalar's `init` is edited as a one-cell grid, and the
      variable's panel gets a description field. The panel says that renaming and scope are edited in
      the editor. Tests: demo `ParameterA` shows 3200 and its description, and each is written by a
      plan, in pytest and in a journey.
- [x] **Task 7 (`3:M4`, `3:M5`, `15:M4`, `15:M5`, `15:M6`, `15:M7`, `15:M9`, `15:M10`, `15:M13`):**
      - **Reading numbers:**
        - one number grammar for every field, with no hexadecimal, binary, octal or `Infinity`;
        - one rule for a decimal comma, typed or pasted, including a comma locale's block holding a
          three-decimal value;
        - a boolean takes 0 and 1 alone.
      - **Writing numbers:**
        - rounding as `round_physical` rounds at ties;
        - a physical value typed into a float object planned as the shortest float that round-trips;
        - Physical past twelve significant digits read as typed.
      - **The grid:**
        - columns from the shape, with a missing cell drawn empty;
        - a cell retyped to its own value offers nothing;
        - a stray space in a unit refused, as the Units tab refuses it;
        - a label cut on a code point, never through a surrogate pair.

      Test: a Vitest table for each.
- [x] **Task 8 (`15:M8`):** the plot becomes linear in the cells. Test: Vitest counting the plot's
      work over a 4,096-cell grid.

### Branch 4: `fix/elf-and-addresses` (off branch 3)

Everything read from a linked image, and where an address comes from.

**Files:**
- in `src/ddd/`: `elf.py`, `addresses.py`, `toolbox/*.py`, `backends/a2l/model.py` (what is placed)
  and `analysis.py` (a conditional object's placement);
- `tests/test_elf.py`, `test_elf_fixtures.py`, `test_toolbox_from_elf.py`, `test_addresses.py` and
  `test_address_fixtures.py`;
- `tests/fixtures/elf/` (rebuilt) and `docker/build_elf_fixtures.py`;
- `docs/toolbox.rst`, `build_integration.rst`, `generated_artefacts.rst`, `faq.rst` and
  `acronyms.rst`, `SPEC.md` 6, and `CHANGELOG.md`.

- [ ] **Task 1 (`11:C1`, Critical):** an enumerator is reinterpreted as signed only at its enum's
      full width; anywhere else a `dataN` is zero-extended. `SIGNED_BIG = 200` and
      `SIGNED_WIDE = 40000` join `Signed_e` in the fixture source, which is rebuilt with
      `docker compose run --rm elf-fixtures`. Test (Review focus 4): over every DWARF version the
      fixtures carry, `from-elf` and `--image` read 200 and 40000, while -128 and -32768 stay
      negative.
- [ ] **Task 2 (`11:I1`; decision 11.5):** an external variable with no object symbol of its name at
      its address is not placed. `addresses.py` takes `image.section_of`. SPEC names the linkers it is
      tested with. Test: a gold `--gc-sections` image gives no address for its discarded unit.
- [ ] **Task 3 (`11:I2`, `11:I3`; decision 11.2):** `elf-layout` warns where a member's offset or
      `Struct.size` departs from the natural layout under `e_machine`'s alignment cap. Offsets join
      the conflict comparison. Test: a packed structure, `pack(2)`, a packed member, an unnamed
      bitfield and a zero-width one.
- [ ] **Task 4 (`11:I4`):** `DW_AT_alignment` on a variable is read and reported, and so is
      `DW_AT_GNU_vector`.
- [ ] **Task 5 (`11:I5`):** `from-elf` refuses an image whose executable sections have no contents.
      `--image` keeps reading such an image, since its addresses are right.
- [ ] **Task 6 (`11:I6`, `11:M5`; decision 11.3):** children are walked with a forward-only cursor,
      and a sibling that does not advance is refused. The line table is read only when a finding needs
      a path. Test: a 710-byte image whose sibling points at itself is a usage error at once, and the
      785-byte one is refused.
- [ ] **Task 7 (`11:I7`, `11:M10`, `11:M11`, `4:M2`; decision 11.4):** the build page says that an
      LTO image cannot use `--image`. Also: the toolbox's small untrue sentences, and the five pages
      `--image` did not reach.
- [ ] **Task 8 (`11:M1`, `11:M2`, `11:M3`, `11:M4`, `11:M6`, `11:M7`, `11:M8`, `11:M9`, `1:M7`;
      decision 11.1):**
      - **Values:** a `float32` of `FLT_MAX` accepted.
      - **Damage:** a damaged debug string refused; debug sections past the file's end refused; a
        crafted attribute caught inside `open_image`'s net; an odd type refusing only the variables
        it reaches.
      - **Disagreements:** units disagreeing about a variable reported, and likewise `-fcommon`, weak
        symbols, and sections at one address.
      - **C++:** refused, or described honestly. The finding names the base member, the static member
        and the namespace variable.
      - **The output:** `from-elf`'s component name, and its identity claim (1:M7).
- [ ] **Task 9 (`1:I5`, `8:M6`):** an object whose `condition` the image, or a non-empty map, does not
      place is left out of the a2l and reported at `info`. An unconditional curve over a conditional
      axis is a finding. Test: the demo without `FEATURE_X`, under `--strict`.
- [ ] **Task 10 (`8:M5`, `8:M7`, `8:M15`):**
      - `--image` on an `ET_DYN` file is refused, since its addresses are load-relative.
      - A UTF-16 map names its file.
      - A deep map and a huge number are findings.
      - `-gsplit-dwarf` and `-g1` are told what they are.
- [ ] **Task 11 (`1:I12`, KNOWN):** the `--image` run compares each placed variable's size,
      encoding, qualifiers and shape with its description, as a new warning, `elf-mismatch`. Test: a
      template dropping `const volatile`, and a `uint32` declared as `UWORD`.

### Branch 5: `fix/generated-artefacts` (off branch 4)

What the C and a2l writers produce, and the option that made the C undefined.

**Files:**
- in `src/ddd/`: `backends/c/*`, `backends/a2l/*`, `cli.py`, `models/conversion.py` and
  `analysis.py`;
- `cmake/Ddd.cmake`, `docker/compile.sh`, `docker-compose.yml` and `examples/templates/*`;
- `tests/test_generation.py`, `test_a2l.py`, `test_calibration.py`, `test_cmake.py`,
  `test_documentation.py` and `conftest.py`;
- `docs/generated_artefacts.rst`, `templates.rst`, `concept.rst`, `getting_started.rst`,
  `build_integration.rst` and `file_formats/component.rst`;
- `README.md`, `SPEC.md` 5.1 and 5.2, and `CHANGELOG.md`.

- [ ] **Task 1 (`1:C1`, Critical; decision M2):** `--const-inputs`, and the module's
      `CONST_INPUTS`, are removed. Each is refused with one sentence naming the release that removed
      it and why.
      - The `compile-const` service goes, with its branch of `docker/compile.sh`.
      - So does every sentence teaching the option, in the files listed above, with a migration line.

      Test: `ddd generate c --const-inputs` exits 2 with the sentence, and
      `ddd_generate(... CONST_INPUTS)` fails configure with it.
- [ ] **Task 2 (`1:I8`; decision 1.5):** `--a2l-module-fragment` and `A2L_MODULE_FRAGMENT` paste a
      project's file verbatim inside `MODULE`. The artefacts page names A2ML, EPK and `MEMORY_SEGMENT`
      as what such a fragment carries. Test: the fragment appears once, inside the module, in an a2l
      written before the link and in one written after it.
- [ ] **Task 3 (`1:I9`):** with `--image`, a member's `SYMBOL_LINK` names the linker symbol and the
      member's offset. Before the link, the page says the record names a path no map can answer.
      Test: `Diagnosis.faults` gives `SYMBOL_LINK "Diagnosis" <offset>`.
- [ ] **Task 4 (`1:I10`, `6:I2`, `1:M12`; decision 6.3):**
      - A name reaching the a2l that matches a keyword in ASAP2 1.6.1's index is refused. The
        implementer chooses between a check of its own and an a2l half of `reserved-identifier`, and
        the changelog names the choice.
      - A string past `MAX_STRING` 255 is a warning, and so is an identifier past `MAX_IDENT` 1024.
      - So is an array of structures whose element names pass `MAX_PARTIAL_IDENT`.

      Tests: `MAP`, `VALUE`, `ROOT` and `MODULE`; a 300-character unit; a 128-character name with
      its index.
- [ ] **Task 5 (`1:I7`, `1:I11`):**
      - Where `const volatile` places an object is measured again on the fixture images, and pinned
        by a test on them. The page says what depends on the compiler's version.
      - `--gc-sections` is said in 5.1 and on the templates page, and the example templates gain a
        retain macro a project sets.
- [ ] **Task 6 (`1:I2`):**
      - `ObjectView` offers `unit`, `conversion` and `limits`.
      - The example templates write scale macros, so a rescale reaches the reader's header.
      - The concept page says what is detected and what is not.
      - Each reconcile preview says that the readers' code is not touched.
- [ ] **Task 7 (`6:I1`; decision 6.2):** a member's `a2l` block on a member that names a structure is
      honoured. `export: false` keeps the subtree out of every instance, and `format` and
      `display_identifier` reach the records.
- [ ] **Task 8 (`8:M1`, `8:M2`, `8:M3`, `8:M4`, `18:M4`, `1:M6`; decision 8.3):**
      - Derived limits round outward, and a `float32`'s never pass `FLT_MAX`.
      - A size past 65,535 for `MATRIX_DIM`, `NUMBER` or `MaxAxisPoints` is refused, as `event` is.
      - Records and `GROUP` list elements in one order, and the comment and 5.1's `cell[10]` sentence
        say it.
      - `MOD_COMMON`'s alignments come from the image when there is one.
      - A byte order defaulted, with no `--byte-order` and no image, is reported at `info`.

      Test (Review focus 4): a `uint64` under factor 1, a `uint32` under 2^-10, and `float32` limits.
- [ ] **Task 9 (`8:M9`, `8:M10`, `8:M11`, `8:M12`, `8:M13`, `8:M14`, `8:M17`; decision 8.4):**
      - **Templates and their page:** `.const` true only where const was added; `.value` and
        `.literal` documented as they differ.
      - **The C:** distinct guards for `Sensor` and `Sensor_`; a description ending in `??/` defused.
      - **The a2l:** `RAT_FUNC` called a choice; the unsuffixed compu method's name given to the object
        that reaches the file first.
      - **The artefacts page:** its small sentences.
- [ ] **Task 10 (`18:M6`, `19:M14`):** a member past `MATRIX_DIM` is reported once per member, at
      the types file. The a2l's method names become linear in the conversions that share a unit.

### Branch 6: `fix/comparison-verdicts` (off branch 5)

Whether a delivery can replace another, for readers that may be precompiled (decision M1).

**Files:**
- in `src/ddd/`: `compare.py`, `deliveries.py`, `ir.py`, `cli.py` and `gui/compare.py`;
- `tests/test_compare.py`, `test_comparison_tables.py` and `test_gui_compare.py`;
- `SPEC.md` 4.1 and 5.3, `docs/comparing_deliveries.rst` and `CHANGELOG.md`.

- [ ] **Task 1 (`1:C3`, `7:C1`, `7:M2`, Critical; decision M1):** each instance gets one layout
      signature, taken from the dictionary's `types`: its ordered members, nested types expanded,
      external members by name and shape, and dimensions by value.
      - The signature is compared as interface: any difference is `changed-interface`.
      - The one exception is an append to a scalar top-level instance, which stays `added-object`.

      Tests:
      - 7:C1's four rows, and 1:C3's insertion and external member: each `changed-interface`, and
        "cannot replace" under `--strict`;
      - a reordering stays an error;
      - a nested type renamed with the same layout gives no finding.
- [ ] **Task 2 (decision M1):** turning `volatile` from false to true is an error on an object
      somebody reads, and so is `renamed-object`. Test: each against a reader, and each keeping its
      grade on an object nobody reads.
- [ ] **Task 3 (`7:I2`):** narrowing an object somebody reads by a condition, none to one or one to
      another, is an error under an identifier of its own. A condition going away stays a warning.
- [ ] **Task 4 (`7:I1`, `7:M9`):** `_uniform` collapses an `init` only when every leaf holds one
      value, and the difference is walked over the broadcast shape. `-0.0` and `1e-400` are told as
      what they store. Test (Review focus 4): a transposed square map, the 3x3, and the 2x2x2 pair.
- [ ] **Task 5 (`7:I3` in part; decision 7.2):** `compare` is told when a side is a component file.
      There, an output gone is `removed-object`, with a sentence that does not claim to know the
      readers, and an input gone is at most `info`.
- [ ] **Task 6 (`1:I3`):** on a measurement with readers, widening its limits is a warning and
      narrowing them at most `info`. Calibration data keeps today's grades.
- [ ] **Task 7 (`1:I4` in part):** constants and rasters are compared as entries: a changed constant
      is `changed-interface`, a changed event `changed-storage`. External types are compared by
      header. Sections wait for the dictionary to carry them.
- [ ] **Task 8 (`5:I6`, `7:M1`):** removing, renaming or reusing a consumed instance that has no leaf
      is reported. A structured variable's kind is one finding.
- [ ] **Task 9 (`14:I1`, `2:I7` in part; decision 14.1):** one `compare_deliveries` in
      `deliveries.py`, which `ddd compare`, `check --baseline` and the Compare tab all call. The tab's
      verdict then counts the candidate's own errors, and its panel says how many. Test: a candidate
      with its own `definition-mismatch` exits 1 from both commands, and `GET /api/compare` answers
      `verdict: false`.
- [ ] **Task 10 (`1:M9`, `1:M10`, `5:M4`, `5:M10`, `5:M15`, `7:M7`, `7:M12`, `14:M6`, `18:M7`;
      decisions 5.2, 5.5, 5.6, 7.4 and 18.4):**
      - **Messages:** a constant's changed value is no longer told as "shape [N] != [N]".
      - **The baseline:**
        - an object with readers and no producer is an error;
        - a broken baseline withholds nothing of the candidate's;
        - a description baseline takes the project's relaxations alone;
        - the Compare tab stamps a baseline before reading it.
      - **What compares:**
        - `null` against explicit zeros is no change;
        - 4.1 names `check --baseline --standalone`;
        - a json holding only a `name` is no delivery;
        - a member's change is reported per path, in numeric order.

### Branch 7: `fix/gui-server-hardening` (off branch 6)

Pass 12's findings. This branch's commits and pull request name each finding by its id and say what
changed, and nothing more (decision M4).

**Files:**
- in `src/ddd/gui/`: `server.py`, `session.py`, `api.py` and `compare.py`;
- `tests/test_gui_server.py`, `test_gui_hostile.py` and `test_gui_api.py`;
- `docs/gui_security.rst` and `CHANGELOG.md`.

- [ ] **Task 1 (`12:I2`; decision M7):** `POST /api/edit` refuses an edit that changes a `plugins`
      list, the document of a created file included. The security page says that `ddd gui` runs what
      the project names, as `make` does, and what the token amounts to. The `--host` warning says the
      same.
- [ ] **Task 2 (`12:I4`):** the change pass 12 gives, with its test in `tests/test_gui_hostile.py`.
- [ ] **Task 3 (`12:I1`, plausible; decision 12.4):** the fix pass 12 measured, with its test.
      Trying the finding's own trigger is the maintainer's (*Not in any branch*).
- [ ] **Task 4 (`12:I3`; decision 12.3):** the line the terminal prints says what to do. The page
      weighs the residual again, once task 1 has landed.
- [ ] **Task 5 (`12:M1`, `12:M2`, `12:M3`, `12:M4`, `12:M5`, `12:M7`, `12:M11`, `9:M8`):** as pass 12
      and pass 9 give them, each with its test in `tests/test_gui_hostile.py` or
      `tests/test_gui_server.py`.

### Branch 8: `fix/release-machinery` (off branch 7)

What a release would publish wrong, and the notes it would carry.

**Files:**
- `CHANGELOG.md`, `SPEC.md` 7 and `SECURITY.md`;
- `.github/workflows/ci.yml`, `docs.yml` and `publish.yml`;
- `gui/scripts/licenses.mjs`, `pyproject.toml` and `tools/`;
- `README.md` (its release lines), `docs/developer_documentation.rst` and
  `tests/test_documentation.py`.

- [ ] **Task 1 (`4:I7`, `4:I8`, `5:I1`, `4:M12`):**
      - The four entries filed under 0.11.0 move under Unreleased.
      - `empty-vocabulary`, the Shared files tab and the Files tab get entries.
      - Unreleased gains its Migration line.
      - SPEC 7 says dictionary format 9.

      Test: a guard that every format number SPEC states is the tool's.
- [ ] **Task 2 (`20:I2`):** the licence walk visits every entry's dependencies. Test: every non-dev
      package of the lock file is listed.
- [ ] **Task 3 (`20:I3`, `20:M5`):** the site crowns a release only once Publish has succeeded, and a
      later push does not cancel a release's documentation run.
- [ ] **Task 4 (`20:M4`, `20:M6`, `20:M13` in part, `20:M16`):**
      - **Publish** runs the gates CI runs, on its own commit, and installs what it uploads.
      - **The sdist** carries `SECURITY.md`, `.dockerignore` and `.gitattributes`.
      - **Versions:** build, twine, hatchling, vsce and sphinx are pinned. Pinning actions by sha
        stays the maintainer's. A wheel built from master carries a dev version.
- [ ] **Task 5 (`20:M2`, `20:M3`, `20:M7`, `20:M11`, `20:M12`, `20:M15`):**
      - **The README:** "runs without being installed".
      - **The build:** `npm run build` under a path that holds a uuid.
      - **PyPI:** a release's page links its own version.
      - **The developer page:** its jobs, minutes and licences.
      - **The steps of a release,** written as steps.
      - **The small untrue sentences.**
- [ ] **Task 6 (`20:I4`; decision 20.1):** this branch's PR body drafts the advisory for 0.11.0,
      saying what that release lacks and what to do. `SECURITY.md` says where advisories appear.
      Publishing the advisory is the maintainer's.

**After wave 1:** releasing 0.12.0 is the maintainer's decision. So are the advisory and the
release's flags (*Not in any branch*).

---

## Wave 2: the rest of the code

### Branch 9: `fix/editor` (off branch 8)

The language server and the VS Code extension. 10:I7 is already in branch 1, task 8.

**Files:**
- `src/ddd/lsp/*.py`;
- `editors/vscode/src/extension.ts`, `package.json` and its tests;
- `tests/test_lsp.py` and `test_lsp_decisions.py`;
- `SPEC.md` 7.2, `docs/editor_integration.rst` and `CHANGELOG.md`.

- [ ] **Task 1 (`10:I1`):** withdraw only the files this run reported on, and refresh no deleted
      path. Test: the probe
      `test_p10_i1_opening_a_file_of_another_project_keeps_this_ones_findings`.
- [ ] **Task 2 (`10:I2`; decision 10.3):** walk to the root, and answer from the outermost
      description that includes the document. SPEC's sentence changes with it. Test: the probe
      `test_p10_i2_the_demos_sub_project_component_shows_what_ddd_check_shows`.
- [ ] **Task 3 (`10:I3`; decision 10.2):** once the edits are computed, take every project that holds
      a touched file, until none is new, and rename across them. Test: the probe
      `test_p10_i3_a_rename_from_a_reader_reaches_the_other_images_reader_or_is_refused`.
- [ ] **Task 4 (`10:I4`; decision 10.4):** a rename is refused while any open document of the project
      differs from the disk. Test: the probe
      `test_p10_i4_a_rename_with_an_unsaved_mention_open_is_refused_or_covers_it`.
- [ ] **Task 5 (`10:I5`):** with no project known, any rename but a local's is refused, saying that no
      project is known.
- [ ] **Task 6 (`10:I6`, plausible; `10:I13`; decision 10.1):** each request is wrapped: it answers
      `-32603`, writes the trace to stderr, and the session goes on. While a file does not load,
      `codeAction` answers `[]` and says so once with `window/logMessage`. The three triggers that end
      a session are fixed too: a hover on `init []`, a `float64` at 1e308, and a relative record.
- [ ] **Task 7 (`10:I8`, `10:I9`, `10:I10`, `14:M13`):**
      - A producer's key is read through its type, and no removal is offered while a type is unsettled.
      - A raster's new name is written as json, escaped.
      - A constant's rename rewrites a condition that spells the constant as a word, and the GUI's
        used-by count reads conditions too.
- [ ] **Task 8 (`10:I11`, plausible; decision 10.5):** a fix or rename that edits several files sends
      `changeAnnotations` with `needsConfirmation`.
- [ ] **Task 9 (`10:I12`):** one analysis per distinct project in a refresh, with queued `didOpen` and
      `didSave` coalesced and the resolved dictionary kept until `_forget`. Test: one that counts the
      analyses for a save with ten tabs open.
- [ ] **Task 10 (`10:M1` to `10:M12`; decision 10.6):**
      - **Requests and edits:**
        - malformed params are refused (`10:M1`);
        - a quick fix under a moved buffer is refused whole (`10:M2`);
        - a fix in two images is offered once (`10:M3`).
      - **Answers:**
        - the hover answers from the document's own project (`10:M4`);
        - a file reached through a junction is published under one spelling, so its findings
          refresh (`10:M5`);
        - ranges come from the buffer (`10:M6`).
      - **The extension:**
        - activation is narrower than `onLanguage:json` (`10:M7`, plausible);
        - the server registers the watcher (`10:M8`);
        - workspace folders added later are followed, with a relative `-b` for each (`10:M10`).
      - **Refusals and cost:**
        - an external type that a header defines is not renamed (`10:M9`);
        - a unit plan renders in linear time (`10:M11`).
      - **Text:** the small untrue sentences (`10:M12`).

### Branch 10: `fix/gui-plans-and-answers` (off branch 9)

What the GUI's server answers, and what it lets a plan carry.

**Files:**
- in `src/ddd/`: `gui/*.py`, `graph.py`, `variable_keys.py`, `value_identity.py`, `lsp/edits.py`
  (the settlement), `shared_plans.py`, `declaration_plans.py`, `object_values.py` and `plugins.py`;
- `tools/bench_gui.py`;
- `tests/test_gui_*.py`, `test_graph.py`, `test_variable_keys.py`, `test_settle.py` and
  `test_bench_gui.py`;
- `gui/src/api/client.ts` and the libraries that send limits;
- `docs/command_line_interface.rst` and `CHANGELOG.md`.

- [ ] **Task 1 (`3:I1`, `3:I2`, `3:M9`; decisions 3.2 and 3.3):** pass 3's move 2.
      - `type-plan`'s `set_key` asks the models about the definition as the plan would leave it,
        through `ddd.models.definition_problem`, which `settle` asks already since branch 1, task 8
        (`lsp/edits.loading_problem`), so that one rule serves both.
      - Min and Max travel as text.
      - Where no declaration states `limits`, the settlement writes them on the producer.
      - `same_value` reads limits exactly.
- [ ] **Task 2 (`14:I2`):** `GET /api/graph` walks the instances as well as the objects. Test:
      `examples/structures` draws `Inlet`'s arrow.
- [ ] **Task 3 (`14:I3`; decision 14.4):** `typename` disagrees only where two declarations name
      different types. Test: a table of pairs holding the panel's word against `ddd check`.
- [ ] **Task 4 (`14:I4`, `14:I5`; decision 14.2):**
      - A plugin whose stamp moved is reported as changed, and the server asks for a restart.
      - The poll stamps the directory each pattern expands in, every path `plugins` spells, and every
        build record.
- [ ] **Task 5 (`14:I6`, `14:M12`, `14:M14`, `2:I9`; decision 14.5):**
      - A plan's hunks come from the spans its operations replace, not from a diff of the file.
      - `declarable` no longer reads every producer's file.
      - `open` stops parsing every description before it answers, or the bench measures it as it
        is. The finding offers both ways.
      - `project_of` is asked only for `add`.

      Test: `tools/bench_gui.py` gains a plan in the largest file and an applied rename, each with its
      budget.
- [ ] **Task 6 (`2:I10`, `2:M2`):** pass 2's move 4: one `Plan`, one `PlanRefusal` and one
      `_answered`. The four private names `api.py` takes from `session.py` become public.
- [ ] **Task 7 (`15:I4`, `3:I8`; decision 3.6):** `/api/edit`'s body limit fits what its own plans
      make. A plan past the request line's limit says why.
- [ ] **Task 8 (`16:I8`):** a finding with no route carries its line and column, and the panel draws
      `file:line:column`, or the pointer.
- [ ] **Task 9 (`14:M1`, `14:M2`, `14:M3`, `14:M5`, `14:M7`, `14:M8`, `14:M9`, `14:M11`, `14:M15`;
      decision 14.3):**
      - **Counts and names:** the headline counts statements; a disagreement names the right variable.
      - **Reads:**
        - `/api/values` answers a structured variable, a dropped object and a curve of a structure;
        - `/api/type` tolerates a save;
        - a missing include reads as missing.
      - **What the page is told:**
        - an analysis that raised is shown;
        - a finding leads to a panel that lists it;
        - a refused build record is told on every page.
      - **The contract:** its untrue sentences.

### Branch 11: `fix/gui-screens` (off branch 10)

What the page shows, and how a person moves through it.

**Files:**
- in `gui/src/`: `screens/*`, `components/*`, `ui/*`, `styles/*`, `app/*` and `main.tsx`;
- the libraries those read: `findings`, `kept`, `declarations`, `canvas`, `compare`, `layoutAnswers`,
  `findingsWindow` and `revisions`;
- `gui/e2e/*.spec.ts` and the probes, `gui/screenshots/references/`, and `CHANGELOG.md`.

- [ ] **Task 1 (`15:I2`):** `networkMode: "always"` for queries and for mutations. Test: the probe
      `p15-I2`.
- [ ] **Task 2 (`15:I3`):** the page takes its name from the state, and asks for `["session"]` again
      when `state.project` differs from what it opened.
- [ ] **Task 3 (`15:I5`):** one error boundary, inside the masthead. Test: the probe `p15-I5`.
- [ ] **Task 4 (`16:I5`):** the Declare button always sits above the Shared files table. Test: the
      probe `p16-I5`.
- [ ] **Task 5 (`16:I6`, `16:M7`):** the declare form names what it still needs, and its sentence
      says whether the declaration reads or produces.
- [ ] **Task 6 (`16:I7`, `16:I14`, `16:M1`, `16:M10`, `16:M17`):**
      - The name list is narrowed and windowed.
      - A long table gets a filter, and the masthead a go-to-variable.
      - Compare's table is windowed.
      - The Graph's search says what it found.
      - A wide rename's file list is collapsed.
- [ ] **Task 7 (`16:I9`, `16:M13`):**
      - One banner names what did not load.
      - The panel's sentence says "no file that loaded", beside branch 1, task 7's refusal.
      - An empty project gets a next step.
      - A description that does not parse is listed.
- [ ] **Task 8 (`16:I11`, `16:I12`, `16:I13`, `16:M9`, `16:M14`, `16:M19`; decision 16.3):**
      - **Contrast:** arrows at least `--ink-quiet`, and a visible focus ring, forced colours included.
      - **Focus:** to the heading on a change of page, to the row on Close, to the panel after Apply.
      - **Announcing:** a title per page, and a status line saying what was written.
      - **Layout:** narrow widths handled.
      - **Without colour:** severity not by colour alone.
      - **Motion:** reduced motion honoured.

      Test: the probe `p16-I13`.
- [ ] **Task 9 (`16:M2` to `16:M6`, `16:M8`, `16:M11`, `16:M12`, `16:M15`, `16:M16`, `16:M18`,
      `16:M20`, `16:M21`, `16:M22`; decision 16.4):**
      - **Compare:** it keeps and names its baseline, and refuses in the tool's words.
      - **Panels:**
        - typed text is kept, or the reader is warned before it is dropped;
        - a broken range says so;
        - a key row opens by mouse too.
      - **The Graph:**
        - the Graph and the values grid use the full width;
        - an arrow's tooltip stays readable;
        - a stopped layout worker can be reloaded.
      - **Moving around:**
        - Back keeps the place;
        - a Files row leads to its component;
        - text in a table can be selected.
      - **Names and words:**
        - files are told apart by path where two share a name;
        - a long name keeps Close in view;
        - the small words.
- [ ] **Task 10 (`15:M1`, `15:M2`, `15:M3`, `15:M11`, `15:M12`, `15:M14`, `15:M15`; decision 15.4):**
      - The long poll asks again after a delay.
      - A stale refusal is stamped with the revision it was asked against.
      - `refusalShown` is used in every panel.
      - Reopening the open project keeps the undo stack.
      - A finding whose pointer moved keeps its panel.
      - The stale sentences, and part 19c's recorded items listed in 15:M15.
- [ ] **Task 11 (`3:M8`, `16:M23`):** a raster can be made acyclic from its panel, a refused undo no
      longer blocks the stack, and the Findings window's keys work.
- [ ] **Task 12 (decisions 15.1 and 15.2):** a paste that drops a header row and column says so, and a
      single value pasted into a focused cell sets that cell.

### Branch 12: `fix/cli-and-plugins` (off branch 11)

The command line's boundary with plugins, streams and the files it writes.

**Files:**
- in `src/ddd/`: `cli.py`, `plugins.py`, `backends/base.py`, `diagnostics.py` and `lsp/server.py`
  (`--no-plugins`);
- `gui/src/screens/StartPage.tsx` and `components/CompareView.tsx` (a sentence each);
- `tests/test_cli.py`, `test_plugins.py`, `test_backends.py` and `test_example_plugin.py`;
- `docs/command_line_interface.rst` and `plugins.rst`, `SPEC.md` 7, `README.md` and `CHANGELOG.md`.

- [ ] **Task 1 (`19:I1`; decision 19.2):** a block is dumped with `by_alias=True, round_trip=True`. A
      hook is handed the instance validated from the stated block. The plugin page states that a model
      reads back its own dump.
- [ ] **Task 2 (`5:I4`, `9:M2`):**
      - A plugin's `print` at import, or in a model validator, goes to stderr, as a hook's already does.
      - The page names what is redirected (`print`, `sys.stdout`) and what is the plugin's to keep off
        stdout (a child process, `os.write`, `sys.__stdout__`).
      - The redirect's process-wide reach, which part 19c recorded, is said beside it.
- [ ] **Task 3 (`5:I5`, `8:M16`):** `--dictionary`, an artefact and `build-info -o` each refuse a
      target that is a file the run read: an image, a map, a template or a description.
- [ ] **Task 4 (`5:I3`; decision 5.1):** the sentences about `dump` and `generate --force` say that a
      loading-stage error yields no dictionary.
- [ ] **Task 5 (`1:I15`, `12:M6`):** `--no-plugins` on `check`, `list`, `dump`, `sources`, `compare`
      and `lsp`, each reporting that a named plugin did not run. The README, `check --help`, the start
      page and the Compare form say that a project's plugins run.
- [ ] **Task 6 (`19:I3`, `9:M1`; decision 19.1):** a closed pipe keeps the verdict, and a closed
      stderr is never 0. Test: the probe `test_p19_i3_a_closed_pipe_keeps_the_verdict_of_a_failing_check`.
- [ ] **Task 7 (`19:M2`, `19:M3`, `19:M4`, `19:M5`, `19:M7`, `19:M16`; decision 19.5):**
      - A plugin's name is held to the grammar with `fullmatch`.
      - A hook's bad finding, a `BaseException` and a raising `__getattr__` are reported as findings.
      - `DDD_TRACEBACK` prints a traceback.
      - A check hook that returns its findings, is a generator or is async is refused with words.
      - Two threads meeting a path plugin first share one import.
      - The small untrue sentences.
- [ ] **Task 8 (`19:M1`, `19:M6`, `19:M9`, `19:M10`, `19:M11`, `19:M15`, `1:M5`, `24:M1`; decisions
      19.3 and 19.4):** in `backends/base.py`'s writer:
      - **Renames:** a refused rename is retried, as `editing.py` retries; a case-only rename on a
        case-insensitive disk keeps its file.
      - **Paths:** they are fixed before any hook runs, so an `os.chdir` cannot move them; a target that
        is not a regular file is written through; an output directory another process creates meanwhile
        is the run's own.
      - **Cleanup:** an interrupted write takes its stage files back; the manifest removes only files
        this tool wrote.
      - **What SPEC 5 says:** that two `generate` runs at once are not supported.
- [ ] **Task 9 (`9:M3`, `9:M9`, `9:M10`, `9:M11`, `9:M12`, `9:M13`, `19:M12`, `19:M13`, `17:M3`,
      `17:M4`, `4:I4`; decisions 9.5 and 17.3):**
      - **Output:**
        - `list --format json` keeps what loaded, when a load fails;
        - stdout is LF everywhere;
        - stderr keeps `backslashreplace`;
        - free text is escaped in the text report;
        - `main`'s last word cannot raise.
      - **Options:**
        - `--renames` alone creates its directory;
        - `check --baseline` blames the root, not the command line;
        - `generate -o ""` is refused as `dump -o ""` is.
      - **Plugins:**
        - a backend's name is held to its plugin's;
        - `CheckInfo`'s flags are documented, and `needs_every_component` is held back by
          `--standalone`.
      - **`ddd id`:** it expands a pattern the shell left unexpanded, and the pages say their
        transcripts are bash.

### Branch 13: `fix/loader-and-checks` (off branch 12)

The loader's words, the checks' reach, and the analysis's cost.

**Files:**
- in `src/ddd/`: `loading.py`, `diagnostics.py`, `analysis.py`, `ir.py`, `models/*`, `pointers.py`
  and `file_names.py`, with `schemas/*.json` regenerated;
- `tests/test_loading.py`, `test_models.py`, `test_analysis.py`, `test_hardening.py`,
  `test_edge_cases.py`, `test_structures.py`, `test_types.py` and `test_constants.py`;
- `docs/file_formats/*.rst`, `consistency_checks.rst` and `data_contracts.rst`, `SPEC.md` 3, and
  `CHANGELOG.md`.

- [ ] **Task 1 (`18:I1`):** `name-collision` between constants and members runs on a member index
      built once. The project generator gains its types and constants options. Test: the bench at
      4,000 constants against 40,000 members.
- [ ] **Task 2 (`8:I1`):** `input-mismatch`, a warning, when an axis and its input measurement differ
      in unit, and a note when their conversions differ.
- [ ] **Task 3 (`8:I2`, `17:M9`):**
      - `name-collision` covers the C library's header names, compared without regard to case, and
        the external headers in use.
      - A component or project named after a Windows device (`NUL`, `CON`, `AUX` and the rest) is
        refused.
- [ ] **Task 4 (`1:M3`, `7:M10`, `6:M11`):** `reserved-identifier` follows C11 7.1.3. Library names
      such as `time` and `log` are refused, `Speed__raw` is allowed, and `_speed` at file scope is
      refused. An external type may be named `size_t` or `wchar_t`.
- [ ] **Task 5 (`1:M4`, `1:M8`, `5:M8`, `5:M16`, `18:M1`, `5:M17`, `6:M6`, `7:M13`, `7:M14`, `8:M8`,
      `18:M5`; decision 18.1):** the checks' rules, set right. All but one are things `--strict`
      lets through today.
      - **Values:**
        - an `init` outside its limits, and an axis that does not rise;
        - `true` on a number and `1.0` on a boolean, both refused, with a migration line;
        - a limit past an integer datatype's range, which the limits-out-of-range tolerance no
          longer covers;
        - the exception: a `float64` under a factor above 1 with stated limits is accepted, where
          today it is refused for a reason that does not hold.
      - **Places and names:** a measurement and a parameter in one read-write section; an enum and an
        enumerator of one name.
      - **Shapes:** a member's shape capped like a declaration's; an axis indexed by an array or a
        string measurement.
      - **Conditions:** one ending in `??/`, and one a preprocessor refuses.
- [ ] **Task 6 (`6:M1`, `6:M2`, `6:M3`, `6:M4`, `6:M7`, `17:M2`, `17:M7`, `17:M8`):** the loader's
      words.
      - A curve with no axis names the key.
      - No Python or pydantic words reach the reader.
      - `1e400`, two BOMs, a 5,000-digit number and a deep `init` each get a sentence of the tool's.
      - A duplicate key gets its line.
      - The include depth no longer depends on the order of the entries.
      - A bracketed run past 4,300 digits is a finding.
      - A finding points at what the file has.
      - The small untrue sentences.
- [ ] **Task 7 (`6:M5`; decision 17.3):** a lone surrogate is refused at the parser, and `1e400` in a
      block, a deep block and an offset past 64 bits are findings. A clean check then hands the
      writers only what they can carry.
- [ ] **Task 8 (`6:M8`, `6:M9`, `6:M10`, `6:M12`, `6:M13`; decision 6.1):** the published
      descriptions, the schema sentences, the strict-mode residue said as it is, the BOM and
      PowerShell sentence, and the drifted sentences.
- [ ] **Task 9 (`7:M3`, `7:M4`, `7:M5`, `7:M6`, `7:M8`, `7:M11`, `7:M15`; decision 7.3):**
      - **Under `--standalone`:** `point-counts-mismatch` does not fire falsely, and a project root
        keeps `incomplete-project`.
      - **Duplicates:** relaxing one leaves a note naming what was dropped, and a stable winner.
      - **Plugins' checks:** a plugin's fixed check refuses `-W`, and a default that is not a
        `Severity` is refused cleanly.
      - **Narrowing:** the narrowed-limits tolerance no longer hides narrowing done on purpose.
      - **Sentences:** SPEC's `local-conflict` sentence says "produces", and the small untrue
        sentences.
- [ ] **Task 10 (`17:M1`, `18:M2`):** `_meaningful` becomes linear, and every "did you mean" is
      memoised by spelling.
- [ ] **Task 11 (`17:M5`, `17:M10`; decision 17.1):** a trailing `**` reaches directories alone, on
      every Python, with a test on all three. `ddd sources` lists by code point.
- [ ] **Task 12 (`17:M6`; decision 17.2):** `to_raw`, `ConversionRule`, `IDENTITY` and `parents` go,
      with the tests that keep them. `Location` loses `order=True`.
- [ ] **Task 13 (`18:M8`; decisions 18.2 and 18.3):** the small untrue sentences of `ir.py` and of the
      analysis; "declared as input by nobody"; and an `info` for a reader's `a2l.format` under a
      silent producer.

---

## Wave 3: the structure, the documents and the tests

### Branch 14: `refactor/layers` (off branch 13)

Pass 2's moves 0 to 3 and 10, and pass 3's moves 0 and 4 to 6 (decision M5). Pass 2's move 4 is
branch 10's task 6, and the `identity.assign` half of its move 3 is branch 1's task 6. Every move
keeps the code's behaviour: the full suite passes unchanged after each.

**Files:**
- across `src/ddd/` and `gui/src/`;
- `tests/test_layers.py` (new) and `tests/conftest.py`;
- `docs/developer_documentation.rst`, `README.md`'s layer table, `src/ddd/__init__.py` and
  `docs/concept.rst`.

- [ ] **Task 1 (`2:I4`):** move 0. `tests/test_layers.py` walks every module's imports against the
      table, with a ratchet of today's violations that only shrinks. `conftest.py` stops importing the
      editors at module level.
- [ ] **Task 2 (`2:I2`):** move 1. `lsp/__init__.py` becomes empty, and `editing.py` and
      `identity.py` import at the top.
- [ ] **Task 3 (`2:M1`):** move 2.
      - `lsp/ranges.py` and `resolve_path` move to the leaves.
      - The `EXIT_*` codes move to `names.py`.
      - `load_dictionary` moves to `deliveries.py`.
- [ ] **Task 4 (`2:M3`, `2:M4`, `2:M5`, `2:M6`, `2:M8`, `5:M14`, `14:M10`):** move 3.
      - One `file_kind()` in `loading`, comparing extensions without regard to case everywhere: the
        module, the pre-commit hook and the GUI.
      - One `init_problem()`.
      - Member names in `occupied`.
      - `ensure_ascii=False`.
      - One module owning the pointer grammar.
- [ ] **Task 5 (`3:I5` in part, `3:M2`, `3:M7`):** pass 3's move 0.
      - An exhaustive `routeOf`, and `findingsQuery` through `queryOf`.
      - The refusal codes as a `Literal`, and `export type *`.
      - An import walk over `gui/src` as a ratchet.
- [ ] **Task 6 (`3:I3`, `3:I4`):** pass 3's move 4. `GET /api/component` answers the component
      table's rows, and the page loses its raw reads. `schemas.mjs` loses its file-format half.
- [ ] **Task 7 (`3:M3`, `3:M6`):** pass 3's move 5. The plans carry what the page now derives.
- [ ] **Task 8 (`3:I6`, `3:I7`, `3:M1`, `23:I2`; decisions 3.4, 3.5 and 23.1):** pass 3's move 6.
      - One `useOffers`, one `Outcome`, and `refusalOf` in `lib/refusals.ts`.
      - 3:I7's decisions move into `lib`, under the Vitest gate.
      - The rule is restated as decision 3.5 words it.
- [ ] **Task 9 (`2:I5`, `4:I5`):** move 10.
      - The layer table on the developer page, the README's table, and `ddd/__init__.py`.
      - An account of how the GUI is put together: its contract, queries, routes and screens, and
        where a new endpoint or screen goes.
- [ ] **Task 10 (`2:M9`, `2:M10`, `3:M10`):** citations a reader cannot resolve, and docstrings the
      code has outgrown, on both sides of the line.

### Branch 15: `docs/review-corrections` (off branch 14)

Every page the earlier branches did not already correct, and the guides the review found missing.

**Files:** `README.md`, `SPEC.md`, `docs/*.rst`, `docs/file_formats/*.rst`,
`editors/vscode/README.md`, `CHANGELOG.md` and `tests/test_documentation.py`.

- [ ] **Task 1 (`4:I10`; decision M6):** a README of about 150 lines: what DDD is, installing, a quick
      start, and where everything is. The name tests move to the reference pages, and every other
      copy of a fact becomes a link to its one home.
- [ ] **Task 2 (`4:I1`; decision 4.5):** a guide to `ddd gui`, written from the GUI as branches 1, 3,
      7, 10 and 11 left it. Screenshots are added by the Docker run.
- [ ] **Task 3 (`4:I2`; decision 1.4):** adopting DDD in a project that already has code, stating
      today's limits.
- [ ] **Task 4 (`4:I3`):** from the generated a2l to a connected tool: A2ML, EPK, and branch 5's
      fragment hook.
- [ ] **Task 5 (`4:I6`, `4:M16`):** a contributor's set-up and definition of done, and the
      environment variables that are documented only in code today.
- [ ] **Task 6 (`4:I9`; decision 4.1):** SPEC 7.4, on what a project may rely on from `ddd gui`.
- [ ] **Task 7 (`5:I2`, `5:M1`, `5:M2`, `5:M3`, `5:M5`, `5:M6`, `5:M7`, `5:M9`, `5:M11`, `5:M12`,
      `5:M13`, `5:M18`, `5:M19`, `5:M20`; decisions 5.3 and 5.4):** SPEC on its own, as pass 5 read
      it.
- [ ] **Task 8 (`4:M1`, `4:M3`, `4:M4`, `4:M5`, `4:M6`, `4:M7`, `4:M8`, `4:M9`, `4:M10`, `4:M11`,
      `4:M13`, `4:M14`, `4:M15`, `4:M17`, `4:M18`, `4:M19`, `4:M20`; decisions 4.2 and 4.4):** the
      site, as pass 4 read it, with the design records' index page.
- [ ] **Task 9 (`1:I1` in part, `1:M1`, `1:M2`, `1:M11`):**
      - The README and the concept page say who can write a foreign variable.
      - The concept page covers the editor stack, and what the front end knows of C and the a2l.
      - It says what one definition rests on.
- [ ] **Task 10 (`20:M10`, `25:M1`; decisions 25.1 and 25.2):** the a2l keyword table, the
      `from-elf --format json` sentences, and the extension's README as a pointer.
- [ ] **Task 11:** the changelog entry for the whole review, naming every migration the sixteen
      branches introduce. A `tests/test_documentation.py` guard checks that every migration line
      names a release.

### Branch 16: `test/review-gaps` (off branch 15)

The tests the review showed missing, beyond those each fix landed with.

**Files:** `tests/*`, `gui/e2e/*`, `gui/playwright.config.ts`, `pyproject.toml` (the `slow` marker),
and `docs/developer_documentation.rst`.

- [ ] **Task 1 (`21:I1`, `21:I2`, `21:I3`; decision 21.2):** every datatype is pinned through both
      writers' tables. An a2l reader runs over every a2l the suite generates: names unique, references
      defined, `/begin` matched by `/end`.
- [ ] **Task 2 (`21:I4`; decision 21.3):** every check's default severity is pinned against the
      documentation's table.
- [ ] **Task 3 (`21:I5`, `21:I6`, `21:I7`):**
      - The seven tests that pass with their rule deleted are made to fail on it.
      - Fixtures that are not square, not in name order, and wider than `uint8`.
      - Boundaries for 21:I7's survivors, re-run against the code as fixed.
- [ ] **Task 4 (`21:M1` to `21:M9`; decisions 21.1 and 21.4):** the reserved-word table pinned, and
      the example templates' output compiled.
      - **What is asserted:** older formats' defaults; where descriptions go; absence; message texts.
      - **Performance:** the two performance tests get a bound.
      - **Housekeeping:** the core tests import their helpers from `conftest`, and `pytest --co` exits
        clean.
- [ ] **Task 5 (`22:I1`, `23:I1`; decisions 22.1 and 23.2):** every probe of both probe files is in
      the suites, ported by the branch that fixed it. The developer page states the two rules: a
      second actor, and key-by-key typing.
- [ ] **Task 6 (`22:I2`, `22:I3`, `22:M2` to `22:M9`; decisions 22.2 and 22.3):**
      - **The server:** the token and `Host` parametrised over their wrong forms; the idle timeout
        tested without replacing it.
      - **The page's state:** a second edit before the state is read.
      - **Expectations:** none taken from the code under test.
      - **Coverage gaps:** guard survivors, positive paths, and the command line's guards, the default
        a2l byte order among them.
      - **What only a separate process shows.**
      - **Windows:** the longest-name tests on a stock Windows.
      - **The loop:** a `slow` marker, and the developer page's short loop.
- [ ] **Task 7 (`23:M1` to `23:M6`; decision 23.3):** the journeys' page and their machinery.
      - The developer page says that the journeys serve the compiled pages.
      - The fixtures get room for a stock Windows, and the config an `actionTimeout`.
      - The section and raster stale refusals get journeys.
      - The drift helpers check their edit landed, and screenshots pin a screen's states.

---

## Not in any branch

**Left to the maintainer.** Each is a setting, an outward act, a tool or a download that only the
maintainer has:

- **Settings on GitHub:**
  - `20:I1`: Dependabot's version updates, a settings click, since GitHub does not run them on a fork
    until they are enabled.
  - `20:M14`: `pypi`'s protection.
  - The other half of `20:M13`: pinning actions by sha.
- **The releases:**
  - `20:M8`: what a release is: Pre-release or stable, the classifier, and whether `preview` stays the
    GUI's word.
  - 0.12.0 itself, and the 0.11.0 advisory that branch 8, task 6 drafts.
- **Checks that need an install or a download:**
  - `20:M1`, plausible: the pydantic floor, which needs a `ddd check` under pydantic 2.9.2 and 2.10.0.
  - `20:M9` and `12:M10`, plausible: `npm audit`, which sends the dependency tree to the registry.
- **Trials only the maintainer can run:**
  - `12:I1`'s own trigger, plausible, which the review could not run. Branch 7, task 3 makes the
    measured fix regardless.
  - An hour with CANape and INCA, loading one generated a2l in each. It settles the tool side of 1:I8
    to 1:I10, `MATRIX_DIM`'s order (8:I3, refuted on the standard's text alone), why `RAT_FUNC` is
    written, `MaxAxisPoints`, and floating point counts (decisions 1.6 and 8.4).
- **Deferred by the maintainer:** `11:I8`, pointer members, deferred on 2026-10-02. The typedef'd half
  is one task once picked up.
- **Choices left open:**
  - The Docker image's `USER`, raised beside 19:M9: a non-root user changes the volume permissions
    users rely on.
  - Moving the design records to an orphan branch (decision 4.2's alternative).
  - The three older review branches still on GitHub.

**Deferred by a decision:**
- **The design-sized features:**
  - `1:I13` (decision 1.4).
  - `1:I14`: one component's flags reaching every component is the price SPEC and the README state. A
    types header per component needs a design.
  - The enforcement half of `1:I1`: per-component include directories, the same design.
- **The split** (decision M5): `2:I1`, `2:I3`, `2:I8` and `2:M11`; the load-gate-analyse half of
  `2:I7`; and pass 3's moves 1, 3, 7 and 8, with them the generated-route-table half of `3:I5`
  (decisions M3, 3.6 and 3.4).
- **Format changes:** the sections half of `1:I4`, since the dictionary does not carry sections, and
  the `dump --standalone` mark of `7:I3`.
- **Kept as documented:** `12:M8`. `12:M9`, plausible, stays too (decision 12.5).

**Refuted by the verification**, so not fixed: `8:I3` and `22:M1`.

## Left open by the implementers

Recorded as each branch lands, so that nothing is lost between a task and the release notes.

**Branch 1:**
- **Long file names** (task 1, `13:C2`): a stage is 21 bytes longer than its file's name, where it
  was 12, so an existing file named 235 to 255 bytes can no longer be edited, where it was 244 to
  255, and on a Windows without long paths, which decision 22.2 supports, a file whose full path is
  239 characters or more, where it was 248. A file created from the page is refused past 234 bytes,
  naming the limit. Branch 13 lists `file_names.py`, which builds the stage's name.
- **The 255-byte stage on a real disk** (task 1): the test of the longest name a file can be
  created under stages a name of 255 bytes in the test's own temporary directory, a full path that
  a Windows without long paths refuses. Branch 16, task 6, the longest-name tests on a stock
  Windows, takes it with them.
- **A unit rename's plan parses each file twice** (task 3, `13:C1`): the in-place guard and the
  plan each parse every file, so the plan of a unit stated in 1,167 files takes 1.55 s where it
  took 1.14 s, widening a budget the plans already miss (spec §3). Branch 10, task 5 owns it,
  with the plans it measures against their budgets. *(Done by branch 10, task 5: a plan's edit is
  made from the document the plan read, so each file a rename writes is scanned once as it stands
  and once as its edit leaves it. Over the 1,167 files of a generated project of 35,000
  declarations the rename's plan took 1,273 ms in two runs of `tools/bench_gui.py`, where it took
  1,608 and 1,631 ms, still past its second, as branch 10's entry on the budgets says.)*
- **`ddd id --assign` syncs the files it stamps one after another** (task 6, `2:I6`): it hands
  `apply_changes` one file at a time, so nothing batches the syncs, as an edit's are batched.
  Measured on the Linux development PC's NVMe disk (ext4) over the generated project of 35,000
  declarations with every output lacking an id - 1,166 component files - a first run took 0.70 s
  before this branch and 10.7 s after it, the median of three runs each; a second run, which
  stamps nothing, about 0.6 s both. No branch owns `identity.py`.
- **The variable's key chooser still offers another component's locals** (task 9, `13:I6`): for an
  `axis` or an `input` it lists a name another component declares `local`, which `declarable`
  leaves out, and choosing it writes a `local-conflict`, the harm `13:I6` was graded for. Branch
  10 lists `variable_keys.py`, where the chooser's offer is made. *(Done by branch 10, task 3:
  `variable_keys._objects` leaves out a name a component declares `local` unless every file the
  offer is for is the one that keeps it, reading the owner off `Index.scopes` as `_kept_by` does;
  a variable's panel offers by the files its declarations are in, and `form_for` by the file the
  new declaration is written into. A type's panel, which is no component's declaration, still
  lists them all.)*
- **A description given with `PROJECT` whose record sits beside it reads as generated** (task 4,
  `1:C4`; R2): `ddd_generate()` writes `ddd-build.json` into `OUTPUT_DIRECTORY` with or without
  `PROJECT`, and where that is the description's own directory the record names a hand-written
  project from beside it: every change of its files is refused as `generated`, in a sentence
  saying the build writes it. Nothing is written wrongly, and the CLI and developer pages state the
  limit. Branch 2, which owns `cmake/Ddd.cmake`, can say precisely which description the build
  writes, by a key it adds to the description it collects or to the record: an addition to the
  format, which its changelog would then state. *(Done by branch 2, task 10, R29: the record of a
  description given as `PROJECT` carries `origin`, `given`, and is stamped `format` 2; the record
  of a collected one is the format 1 record every DDD reads, with no key. `ddd gui` edits a
  project whose record says `given`, and refuses every other, a record without the key included,
  as every record before the key. A DDD from 0.11.0 on declines a record of format 2 as written
  by a newer DDD and says so, an older one skips it in silence, so the cost falls on `PROJECT`
  builds' records alone. The CLI and developer pages state the limit no more, and the branch's
  changelog entry states the key and the format.)*
- **A removal refused as stale waits for the panel to close, or a key to settle** (R22): the
  variable panel's removal offer withdraws Remove while any refusal stands (P19b-24), so its
  sentence, kept now until the reader's next choice, goes when they settle a key or close the
  panel, and only then is Remove offered again. Drawing Remove under the sentence, as the other
  offers draw their Apply, is the question P19b-24 recorded for the maintainer. Branch 11 lists
  `screens/*` and `components/*`.
- **A refused undo is tried again only by closing the strip** (R22): the Undo strip draws a
  refusal in place of its preview and Put back, so an undo refused is asked again only once the
  reader has closed and opened the strip, where a revision landing let a stale refusal go before
  this branch. The refusal is of the entry pressed for, and another coming to the top while the
  strip is open is offered whole (branch 2, D0). Branch 11 lists `screens/*`.
- **A create racing another writer's create** (task 2, `13:I1`; R23): a file an edit creates is
  renamed into place, replacing one another writer created between the edit's last look and the
  rename, and a save landing in that instant is written over too, as the documents now say.
  Closing the create case takes a write that refuses an existing name - the stage linked to the
  new name, then unlinked, and on Windows a rename that refuses one - with a fallback where a file
  system offers neither. No branch owns `editing.py`.
- **A read-only file is answered `500`** (task 5, `13:I4`): `unwritable`, refused before anything
  is staged, takes the status of a write that failed, where a refusal the reader can mend is a
  `409` elsewhere; another status is a change of the contract. Branch 10 lists `gui/api.py`, which
  chooses it, and the contract. *(Done by branch 10, task 6: `unwritable` is a refusal, which the
  one mapping answers `409` from an edit, an undo and the undo's preview alike, and the page shows
  the server's sentence; a code the mapping does not know is still a `500`.)*
- **An undo left half written forward keeps its entry** (task 2, `16:M23`): after an `unwritable`
  undo that put a file back but could not write the others forward again, the entry stays on the
  stack, so a later undo of it is refused `stale` and the edits beneath it are out of reach until
  the server restarts. Branch 11, task 11 owns it.
- **What a refused write says** (tasks 2 and 5): a refused one-file edit, and a stage or a sync
  refused in a batch, say the files already written were put back, or written forward again,
  where none was touched; a file that cannot be read at the last look is told it changed on disk,
  its error dropped; and a file deleted just before the write, or during an undo's batch, is
  answered `unwritable` where `stale` is true. No branch owns `editing.py`.
- **A folder a stage cannot be made in, and a umask without the owner's write bit** (task 5): the
  first is not refused before staging starts but at its own stage, which is made before any file
  is renamed, so nothing is written or put back, though the refusal says otherwise (above); under
  the second every edit and undo is refused, the stage being opened again to write before it is
  synced. No branch owns `editing.py`.
- **A plan an unanalysed edit moved reads as `stale`** (task 3): where an edit of the page's own
  moved the place a plan points at, the plan is refused `stale` before that edit's analysis lands,
  ahead of the `analysing` refusal the CLI page documents for the case. Branch 10 lists
  `object_values.py` and `gui/api.py`. *(Done by branch 10, task 6: a plan refused `stale` is
  answered `analysing` instead where an edit of the page's own, not yet analysed, wrote a file the
  plan read, whichever file its place is in; a place moved by a save from elsewhere is `stale`
  still. The Files tab's judge still answers `stale` for such an edit, as branch 10's entry
  says.)*
- **A settled value whose declaration moved is refused `unreadable`** (task 3): where the other
  plans say `stale`, as the changelog states; the page draws the two alike. No branch owns
  `variables.py`.
- **Fingerprints across several build records** (task 3): a file several runs read takes the
  fingerprint of the first run that read it, not the index's run, so a file saved and put back
  between two runs can carry the fingerprint of bytes other than the index's; several records
  only, and rare. Branch 10 lists `gui/session.py` (R110). *(Done by branch 10, task 4: the run the
  index comes from is chosen once, and its read is what the files' fingerprints are taken from, a
  file it did not read taking the first run's read as before.)*
- **A generated project left unrecognised** (task 4): a record that does not parse is read as no
  record, and `ddd build-info --output` writes one unstaged, so a write that dies can leave it
  half written; and a build configured at another path, a container's mount, names a project the
  path opened does not match. Either can leave a generated description editable. An empty
  `CMAKE_HOME_DIRECTORY` reads as the working directory besides: the description's own directory
  is refused all the same, and only how much of the build tree around it is refused changes.
  Branch 10 lists `gui/session.py` (R110), branch 12 `cli.py`. *(Done by branch 10, task 4, in
  part: a record beside a description that does not read as one, a write of it cut short among
  them, is no longer read as no record, and the description is refused as generated, naming the
  record, until it reads, the record watched so that its repair is noticed; and an empty
  `CMAKE_HOME_DIRECTORY` names no source tree. `ddd build-info --output`'s unstaged write stays
  branch 12's, and a build configured at another path the maintainer's, nothing the session reads
  telling the two paths are one.)*
- **An existing description added to a generated project** (task 4): is refused without the
  `ddd_add_component()` line a new file is offered with. Branch 10 lists `gui/*.py`. *(Done by
  branch 10, task 4: Add a file offers that line too, to add to the `CMakeLists.txt` beside the
  description, passing over one under the build tree, which goes with the tree; an edit posted
  with an entry written by hand is still told the build's membership alone.)*
- **The editor's own id fix** (tasks 6 and 10): the language server places an id with
  `identity.insertions`, always breaking the line, so for a one-line object or a file of bare
  carriage returns it writes other bytes than the page's fix and `ddd id`, and on a one-line file
  it reads the file through once per declaration. Branch 9 lists `lsp/*.py`, which could build the
  offer from the engine's own edit.
- **What `ddd id` reports** (task 6): every refusal reads "cannot be written, skipped", a `stale`
  one included; a file the loader refuses is reported without the loader's reason; and a read-only
  file with nothing to stamp is left alone with exit 0, where the CLI page says a read-only file is
  reported. Branch 12 lists `cli.py`, which words the report; no branch owns `identity.py`.
- **What a refusal names while a file does not load** (task 7): one saying that nothing loaded
  names no file, two unread files of one name in different directories are named alike, and a
  dangling include is told of the project description. Branch 10 lists `gui/api.py`, branch 9
  `lsp/units.py`. *(Done by branch 10, tasks 6 and 9: the did-not-load sentence is written once
  and names each file that did not load, two of one name by as much of their paths as tells them
  apart, in the server's refusals and in the Types and Shared files tabs' own line; and a missing
  include is listed as the file that did not load, its finding staying filed at the entry. An
  entry whose pattern names several files leaves its error with the description, as branch 10's
  entry says.)*
- **A file saved half way after the analysis** (task 7): a file typed into after the analysis and
  then saved half way is unseen by a plan, which checks the fingerprints of the files it writes
  alone. Branch 10 lists `gui/*.py`.
- **An input stays answered while a file does not load** (task 7, R15): a local of the same name in
  the unread file is a `local-conflict` once it loads. Branch 10 lists `declaration_plans.py`.
- **A hidden local's name typed into the add panel** (task 9): is told the project declares it
  already, not whose local it is. Branch 10 lists `declaration_plans.py`. *(Done by branch 10,
  task 6: `declare_object` refuses the name in the sentence a read of it is refused in, naming
  the component that keeps it.)*
- **The would-not-load sentence** (task 8): it reads "with that dimensions", and a removal's names
  a value it does not write; the panel keys each sentence by its words, so two alike, from two
  files of one name, share a key. No branch owns `variables.py`; branch 11 lists `components/*`.
- **The editor's preferred fix** (task 8): for a consumer's mismatch the editor now prefers "Apply
  this datatype to 1 other declaration", the first fix left once the others are withheld. Branch 9
  lists `lsp/*.py`.
- **What the panel's check does not ask** (task 8): a shape mixing a constant with numbers the
  analysis refuses whatever the constant is planned without its sentence, and a type's key is read
  at the index's pointer with no name checked (`_fixed_by`); `type_plans.set_key` is branch 10,
  task 1's. Branch 13 lists `models/*`, branch 10 `lsp/edits.py`. *(Done by branch 10, task 1, in
  part: `type_plans.set_key` asks the models of the type entry as the plan leaves it
  (`type_problem`), refusing a value it would not load with. `_fixed_by` checks the name since
  branch 9's task 7 (R173), and the shape mixing a constant with numbers stays branch 13's.)*
- **A pattern character typed through a link** (task 11): a relative entry naming a file with a
  pattern character, typed through a link the kernel cannot follow `..` after, is checked as the
  file but read by `expand_include` as a pattern matching nothing. Branch 13 lists `loading.py`.
- **The documents' corners** (tasks 4 and 8): no page says that the build tree is the output
  directory where the cache cannot be read, and the three passages on what the panel's check does
  not ask list different sets. Branch 15 owns `docs/*.rst`.
- **A misdirected undo, and a print that fails** (task 12): a second window's undo of an entry no
  longer on top is refused `stale` and asks for a whole analysis; and the line printed for an
  analysis that failed on a refusing request raises where stderr cannot be written, replacing the
  `409` with a `500`, which the analyser's own thread suppresses. Branch 10 lists
  `gui/session.py` (R110). *(Done by branch 10, task 9: an undo of an entry no longer on top is
  refused `stale` without asking for an analysis, the stack having moved and not the disk; and the
  line is printed through the one function that loses a line it cannot write, so the refusal stays
  the answer. The poller's own failure print is still bare, as branch 10's entry says.)*
- **One case the threat model sets aside** stays as `docs/gui_security.rst` draws that model. No
  branch owns it.

**Branch 2:**
- **A plugin's file reaches a component compiling it a build late under Ninja** (task 1, `9:C1`;
  R40): the module declares no file of a plugin, whose names are the plugin's own and known once
  it has run, so ninja looks at such a file before the generation rewrites it, and a change of it
  reaches a component compiling it a build late, however the component is ordered after the
  generation; under make the build after it is right. The build page and SPEC 7.1 give that cost,
  and the remedy a project has: a component whose object depends on the dictionary
  (`OBJECT_DEPENDS` on the path of `DDD_DICTIONARY`) is compiled again in the very build a
  description change runs, though not in the one an edit of the plugin's own code runs that
  changes only what it writes, and not its model; and `ninja -t clean` and `make clean` leave such
  files. Declaring them is one task in two halves: a
  plugin naming its files before it writes them, which is the plugin api, `plugins.py` and
  `backends/base.py`, both on branch 12's list, and the module asking for those names at
  configure and declaring them, in `cmake/Ddd.cmake`, which branch 5 lists. Branch 5 comes first,
  and its half would consume branch 12's, so the task is branch 12's, its files then taking the
  module.
- **The CMake floors are run nowhere** (tasks 1 and 4): CI and the Linux development PC have the
  CMake pip installs, 4.4.3, so neither the module's floor of 3.20 nor the collected mode's of
  3.30 is run. On CMake 3.20 to 3.22 a component file of a `PROJECT` build that starts with a
  byte order mark may name no component, if the json reader of those releases refuses the mark,
  which no run has shown either way: its header would then go undeclared, a change of it reaching
  its readers a build late under Ninja, and a root starting with one would be refused as not
  json, as 0.11.0 refused it. No branch's task runs a floor. Branch 5 listed `cmake/Ddd.cmake` and
  took none of it, and no later branch lists it, so it is the maintainer's.
- **A component's file turned into a project after the configure** (task 5, `9:I3`):
  `ddd_add_component()` refuses a project file when the build is configured, and a registered
  file is no dependency of the configure, so a component's file rewritten as a project is
  refused only at the next configure. Until then the generation collects it as any registered
  file, and an edit of what it includes builds to `no work to do`. Branch 5 listed
  `cmake/Ddd.cmake` and took none of it, and no later branch lists it, so it is the maintainer's.
- **A generated file deleted by hand under make** (task 7, `9:M6`): it is not written again until
  the step runs for another reason - an edit, a clean - or its stamp is deleted, and every build
  reading it stops on it until then, as the build page and SPEC 7.1 have it; ninja makes a
  declared file that is missing. Branch 5 listed `cmake/Ddd.cmake` and took none of it, and no later
  branch lists it, so it is the maintainer's.
- **The a2l options' flag for an address source** (task 2): `A2lOptions.has_address_source` is
  false unless given, whatever addresses the options carry, so an a2l written through options
  that carry addresses and leave the flag out says it has no address source; the one place in the
  tool building the options sets the flag. Branch 5 listed `backends/a2l/*` and took none of it, and
  no later branch lists it, so it is the maintainer's.
- **`STRICT` passes an empty map read after the link** (task 2): a map with no entries raises no
  `address-missing`, so an a2l whose every address is 0 passes `STRICT`, saying so in its comment.
  Whether `STRICT` should fail it is a change of a check, the maintainer's to decide, in the pull
  request.
- **A refusal's sentence on the variable panel** (D0): a row the panel picks by itself can still
  hide the sentence when a revision lands, as it could before branch 1. Branch 1's re-review left
  it, its keying being older than that branch, when D0 took the other residuals. Branch 11 lists
  `screens/*`.

**Branch 3:**
- **A field focused without a click** (task 3, `16:C1`): a field a screen reader or voice control
  focuses, while the grid already holds a focused cell of its own, lands on that cell instead -
  the table is one stop for Tab and keeps the cell last focused, as it did before the task. The
  journeys click a cell before they type into it, so none goes that way; the readers who meet it
  are the ones decision 16.3 is for. Branch 11 lists `components/*`, its task 8 being that
  decision's.
- **`1e400` and `1e-400` in the json-text fields** (task 7, R51): a constant's Value, a size, a
  dimension, a section's alignment and a raster's event send `1e400` as typed, and the server
  refuses it in DDD's own words; `1e-400` typed into a constant's Value is written in those
  characters, which the loader reads as 0.0, so a dimension that constant names is refused by
  `ddd check` as one of 0.0. Branch 13, task 7 makes `1e400` in a block a finding and lists
  `loading.py`; branch 10 lists `shared_plans.py`, which writes the value.
- **A press lost while a revision lands** (the Files tab, R58): when a revision reaches the page,
  the tab asks each of its plans again for it and draws no Apply until the plan comes, so a press
  made in that moment is lost, with no request and no sentence. The tab's journeys of a stale
  refusal press again only once a row's kind, read off the revision the page holds, says that
  revision has come. Branch 11 lists `screens/*`.
- **FLT_MAX read out of an image** (R55): `ddd tool from-elf` writes a `float32`'s `init` in the
  fewest digits that read it back, so FLT_MAX is written 3.4028235e+38, a double past FLT_MAX's
  own, which `ddd check` refuses as `init-invalid` - the spelling the page planned until this
  branch's final wave. Branch 4 lists `toolbox/*.py`.
- **The refusal of an Apply chosen in two more screens** (decision 3.5): the Units and Types
  tabs' `refusalOf` choose a refused Apply's sentence inline, as the four sites that now call
  `refusalSentence` did, and the Files tab borrows the Units tab's. Branch 11 lists `screens/*`.

**Branch 4:**
- **The bound of a line table's header** (task 6a, `11:I6`; R67): the four Important findings of
  6a's review stand. The bound on the counts a line table's header states is measured against
  the length that header gives, not against its section, and takes every entry to be at least
  one byte long; it is the one guard before the parser allocates, and since 6a it is reached
  lazily, from any declaration a run asks for. Its tests hold the comparison on two numbers
  alone, the tests of the forward cursor's refusals would hang rather than fail were a refusal
  to go, and the bound's wiring into the reader is not tested. The changelog says the bound is
  open. The maintainer's, after the two safety stops.
- **8b** (task 8, `11:M2`, `11:M3`, `11:M4`; R66, R67): in task 8's own words, a damaged debug
  string refused; debug sections past the file's end refused; a crafted attribute caught inside
  `open_image`'s net; an odd type refusing only the variables it reaches, which is the catch per
  variable. Until it lands, a type built on demand that fails stops the run, exit 2, at the
  first variable it reaches, and the findings already gathered go unprinted, so decision 11.1's
  odd type is not met; the seam R66 names is where the catch goes. `elf.py`'s module docstring,
  which promises an `Unsupported` node and no exception for a type the module cannot describe,
  holds for a well-formed type and not for a damaged one. The maintainer's.
- **6b** (task 6; R67): tests end to end over damaged image files. What pins the refusals of the
  forward cursor is stand-ins at its own interface, the test task 6 names, of two small damaged
  images, is not in the suite, and what the changelog's headline says, that a damaged image is
  refused where it hung, rests on them alone. The maintainer's; branch 16 lists `tests/*`.
- **A leading underscore on C symbols** (task 2, `11:I1`): an external is placed only where the
  symbol table holds an object of the name its debug information gives, so a toolchain that
  prefixes C symbols with an underscore would have no external placed, where the branch's base
  placed it by its address. `from-elf` meets such a toolchain the same way: it refuses every
  external that the symbol table does not hold under the name the debug information gives, as
  `elf-no-storage`, where the branch's base described each one. None of the toolchains SPEC names
  as tested does so, and none here could show it. No branch owns `addresses.py`.
- **An image with debug information and no symbol table** (task 2; R72): neither `--image` nor
  `from-elf` takes an external variable from it, each saying of every one that the symbol table
  holds no object of its name there, as a linker leaves a variable of a unit it discarded; rare,
  since a strip removes the debug information as well. No branch owns `addresses.py`.
- **A debug-only companion under `--scope input`** (task 5; R65): `from-elf` refuses one whatever
  the scope, though an input entry states neither the initial value nor the section a companion
  lacks; SPEC 7.3 leaves a separate debug file out of what the tool reads. No branch owns
  `toolbox/*.py`.
- **A measurement only a left-out axis pulled in** (task 9; R69): where a map lacks an
  unconditional object the build holds, `address-missing` also names, as reaching the a2l at
  address 0, an `export: false` measurement that only an axis the run left out pulled in, and
  `--strict` stops a build over a record that is not in the file; the list of what reaches the
  a2l would be taken under the run's left-out symbols. Branch 5 lists `backends/a2l/*` and
  `cli.py`. Branch 5's D1 closed it.
- **A declaration alone in a split image** (the final wave): `from-elf` tells a split image that
  a name the symbol table holds, and no unit describes, is in its `.dwo` files, but a name a
  unit only declares, in an image some of whose units are split, is still said to be defined in
  assembly or in a unit built without `-g`, where the placement of `--image` names the `.dwo`
  files in both. No branch owns `toolbox/*.py`.
- **SPEC section 6's planned cross-check** (task 11; R71): the section ends by calling planned
  the comparison of each linked variable's type with its declaration, which `elf-mismatch` now
  makes. Branch 15 lists `SPEC.md`.

**Branch 5:**
- **`EPK` beside named constants** (task 2, `1:I8`; R77): a project that declares named constants
  gets the `MOD_PAR` DDD writes for them, and a fragment holding a `MOD_PAR` of its own is refused,
  so such a project cannot carry `EPK`, `ADDR_EPK` or a `MEMORY_SEGMENT` through the fragment.
  Carrying them needs a hook of its own beside the fragment, or the constants merged into a
  `MOD_PAR` the fragment brings. No branch after this one lists `backends/a2l/*`, so this is for
  the maintainer.
- **What a settle preview says** (task 6, `1:I2`; R81): the preview of a settle, which the page
  draws in its own words, says nothing of the readers' code, where the quick fix's title, which
  the server writes, does; and the stories still show the fix by its old title, with the
  references drawn from them. Branch 11 lists `screens/*` and `components/*`.
- **The editor's quick-fix titles** (task 6; R81): the language server's quick fixes for a
  `definition-mismatch` carry no sentence on the readers' code; branch 9 lists
  `src/ddd/lsp/*.py`.
- **Whether the keyword list is the standard's** (task 4, `1:I10`; R79): the list is written from
  the grammar without the standard's text. The final wave left two candidates it could not settle
  from memory, `DEFAULT_VALUE_NUMERIC` and `NOT_IN_ECU`, and took `INPUT_QUANTITY` out as the name
  of a parameter; the words the grammar fixes as a parameter's value, `NO_COMPU_METHOD` and
  `NO_INPUT_QUANTITY`, which DDD writes, are not on the list either. ASAP2 1.7's `OVERWRITE` block is recalled, from memory, to hold
  `INPUT_QUANTITY` and `CONVERSION` as keywords; that matters to the list once DDD writes version
  1.7, as SPEC 5.2 plans. Checking it takes the standard, so it is the maintainer's; the list lives in `models/*`, which branch 13 lists.
- **What the a2l checks cannot see** (tasks 4 and 8): `a2l-keyword` and `a2l-unrepresentable` are
  judged from the descriptions before a run reads its image or its map, so an object the run
  drops because its build holds none of it still draws them, and `-W` relaxes them for that run,
  as SPEC 4, the check reference and the changelog say. A filter aware of the run would touch
  `analysis.py`, which branch 13 lists, and `cli.py`, which branch 12 lists.
- **The reading of C11 7.1.3** (task 6): SPEC 4, the check reference, the README and the FAQ say
  that C reserves any name holding a double underscore, which C++ does; C reserves a name that
  begins with two underscores, or with one and a capital. `reserved-identifier`'s refusal of a
  double underscore anywhere stands as a rule of the project's own; its stated reason does not.
  Branch 15 lists `SPEC.md` and `docs/*.rst`, and branch 13 lists `consistency_checks.rst` too.
- **A string's escapes against `MAX_STRING`** (task 4): `a2l_string` doubles a backslash and a
  quote, so a description of 255 characters of quotes is a literal of 510, while the check counts
  the text as written. The maintainer decides which length the standard counts; no branch after
  this one lists `backends/a2l/*`.
- **The `SYMBOL_LINK` of a member, written from a map** (task 3, `1:I9`; R78): with an address map,
  as before the link, a member's record names its path at offset 0, which a patcher resolving
  symbols through the map cannot answer. Stating the offset would take the image's layout, which a
  map does not give: for the maintainer, should a patcher that reads debug information be tried.

**Branch 6:**
- **The count the Compare panel does not draw** (task 9; R96): the tab's verdict counts the open
  project's own errors and its reply says how many, `own_errors`, but the page draws neither the
  count nor a reason, so a project whose every error is its own is told it cannot replace the
  baseline above a comparison that has nothing to report. Branch 11 lists `components/*` and the
  `compare` library; whether 0.12.0 waits for it is the maintainer's.
- **What the tests do not run yet** (tasks 1, 3, 4, 6 and 9): three `$ ddd` blocks of the
  comparing page, the 1.3.0 comparison and the two runs of v1.3, the first of which prints an
  absolute path a test has to put in place; a single variable whose structure ends in a nested
  structure that grew; a nested array's size respelled, compared against a dump; a `-0.0` initial
  value in a dumped baseline; the message of a condition replaced on an object nobody reads; and,
  in `tests/test_compare_deliveries.py`, a `tmp_path` and a `capsys` nothing uses and a module
  imported in the body of a test. Branch 16 lists `tests/*`.
- **The cost of reading a float** (task 4; R93): the loader reads every float literal through a
  Python hook, `_read_float`, which takes the mantissa to tell a non-zero literal that reads as 0
  from a zero. The gap is the hook against the C reader alone, and the mantissa is part of it
  only. Over 500,000 floats (`json.loads` of one document, the best of five; first the re-review's
  run, then D0's): the C reader alone 0.069 s and 0.069 s, a `parse_float=float` of no more than
  the C reader's own 0.068 s, `_read_float` 0.119 s and 0.120 s, and a hook that takes the mantissa
  when a value reads as 0, and at no other time, at 0.096 s and 0.096 s. Taking the mantissa only at 0 would
  recover about half the gap, 0.024 s of 0.051 s, and leave the rest to the Python call every
  literal still makes. Branch 13 lists `loading.py` and starts from half.
- **A member that states `export: false`** (D0): the sentences D0 corrected on what the a2l
  checks hold put a condition on skipping such a member, which is always skipped, nothing naming
  a member from outside. Branch 13 lists `consistency_checks.rst`, branch 15 the other pages.
- **The comparison's words left to the documents** (tasks 3, 4 and 10): SPEC 4.1's list of
  warnings, and the comparing page's, open on a line saying no consumer becomes wrong, which
  `widened-limits` under it says the opposite of; a sentence of SPEC and of the page beginning
  "Both spellings" lost what it refers to when the `-0.0` sentence came between them; lines past
  100 columns and uneven rewraps; and `missing-producer`, which SPEC 4.1 lists among the
  comparison's errors, is in neither comparison table, and its registry line does not say a
  comparison files it. Branch 15 lists the pages, and branch 12 `diagnostics.py`.
- **An example plugin's account of `changed-interface`** (task 1): `examples/plugins/ddd_layout.py`
  describes what the check compares as a part of it. No branch lists the example plugins, so it is
  the maintainer's.

**Branch 7:**
- **Whether repairing a description's schema may let the plugins it names run** (task 1, `12:I2`;
  R124): an edit cannot change which plugins the project's descriptions name, and a description
  that does not load runs none of those it names, whichever way an edit leaves it. Whether an edit
  that lets one load may so turn its plugins on is the maintainer's call under decision M7; were
  the guard to read every changed document the loader's way instead, it would be branch 10's,
  which lists `gui/*.py`.
- **Whether the token should run what other projects and baselines name** (task 1, `12:I2`;
  R124): the token may open a project the start page offers, or compare against a baseline under
  the directory `ddd gui` was started in, and either runs the plugins its descriptions name, as
  the security page says. A design question beyond decision M7's edit, so the maintainer's.
- **The plugins guard's corners** (task 1; R113): an undo writes back only what an edit left, and
  `restore` refuses a file changed since, but it asks no plugins refusal of its own; the walk has
  no depth cap, where the loader stops at 64, and a `MemoryError` or a `RecursionError` in it is
  answered `500`, failing closed, where `_read_json`'s comment and a test's docstring overstate
  what holds, saying that the walk for plugins raises on nothing the next analysis would not; and
  a reorder of `includes`, allowed, reorders the plugins the included descriptions name, as
  `_plugins_named`'s docstring says. Branch 10 lists `gui/*.py` and `tests/test_gui_*.py`, so the
  claim is its to correct. *(Done by branch 10, task 6: the read's comment, the walk's docstring
  and the test's say what holds - each file read as the loader reads it, or not at all, and the
  walk following the includes further than the loader's 64 levels, failing closed beyond what the
  analysis reads; the walk itself is unchanged.)*
- **Three readings of `includes`** (task 1): `_plugins_named` and `_includes_of` are nearly one
  function written twice, and `_named_by` reads `includes` a third way. Branch 14, which moves
  code across `src/ddd/`, or branch 10, which lists `gui/*.py`. *(Done by branch 10, task 6:
  `_listed` is the one reading of a description's lists those three made, the plugins guard, the
  poll's watch and `named_by` asking it. `_included`, which reads an edit's output, reads
  `includes` another way, and the watch copies the loader's reading of one entry, as branch 10's
  entries say.)*
- **The create rule inside the plugins refusal** (task 1; R103, R111): what kind a created file
  is, and that it is named `*.ddd.json`, are judged inside `_refuse_plugins`, whose call from the
  Files plan keeps its `plugins` refusal alone. No plan names another, so nothing turns on it, but
  the rule belongs beside `_creatable` or `_confined`. Branch 10 lists `gui/*.py`. *(Done by
  branch 10, task 6: `_refuse_created_kind` judges it beside `_creatable` and `_confined`, each
  change still judged whole, in the order an edit lists them.)*
- **The Files tab's `plugins` refusal on the screenshots** (task 1; R112): the tab can now show a
  plan's `plugins` refusal, which no reference screenshot shows. Branch 11 lists
  `gui/screenshots/references/`, or the pull request says so in a sentence.
- **The directories a record is read under** (task 2, `12:I4`; R114): the builds that feed an open
  project read a record under the start directory alone, and the record of how it is generated
  under the project's own directory too, so a project whose build records name it by a network
  path is fed by the builds those records describe only where that path lies under the start
  directory, though a request may name a path in the open project's own directory;
  `_readable_project`'s docstring says so. Passing the project's own directory to the feed too is
  branch 10's, which lists `gui/*.py`. *(Done by branch 10, task 4: the feed reads records under
  every directory the revision serves, the open project's own among them; the start page's
  listing keeps the start directory alone.)*
- **A description's suffix and its case** (task 2): the record filter and the walk for
  descriptions compare `.ddd.json` case-sensitively, where the create rule and the loader's
  extension check do not, and `DESCRIPTION_SUFFIX` repeats `loading.DDD_SUFFIX`. Branch 14's
  task 4 compares extensions without regard to case everywhere, the GUI included.
- **The signed-out view after a launch code presented again** (task 4, `12:I3`; R125): the page,
  signed out, tells the reader to open the address `ddd gui` printed, this run's, where the
  terminal's line then says to start `ddd gui` again and open the address it prints then.
  Branch 11 lists `components/*`.
- **The all-clear where the launched browser held the token already** (task 4, `12:I3`; R125):
  the page's sign-in leaves a token it already holds in place when the code it was launched with
  is refused, so that no page can sign the reader out of every tab, as `signInFrom`'s docstring
  says. So where the browser `ddd gui` opened held this run's token already, it lands signed in
  whichever program spent the code, and the terminal's line tells its reader that nothing more is
  needed, though that program may hold the token as well. No branch lists
  `gui/src/api/signIn.ts`, and branch 14's moves keep the code's behaviour, so it is the
  maintainer's.
- **What `--host 0.0.0.0` costs a container on several networks** (task 5, `9:M8`; R106): a
  container's user who named one of its interfaces gives `0.0.0.0`, which listens on every network
  the container is attached to, wider than the interface chosen, as the changelog says. The plan
  takes pass 9's change, so whether `--host` should take a container's own interface is the
  maintainer's.
- **The messages beside `--host`** (task 5, `9:M8`; R106): what `ddd gui` says of its `-b` and of
  a project it is given sits beside `--host` in `cli.py`. Branch 12 lists `cli.py`.
- **The standard library's refusals close with bytes unread** (task 5, `12:M7`): its own refusals
  of a request `ddd gui` cannot read close without reading what follows, so on Windows a reset can
  lose one before the browser reads it, where the refusals `ddd gui` writes itself read the rest
  first. Branch 10 lists `gui/*.py`. *(Done by branch 10, task 7: they read the rest before the
  close as those do, `501` and `505` among them.)*
- **A test's server takes up to half a second to stop** (task 3; R126): the serving loop reads its
  stop only when `select` returns, as `socketserver`'s loop did, so every server-backed test waits
  up to the poll interval as it ends; a wake-up the selector watches would end it at once.
  Branch 16, whose task 6 makes the short loop, owns it.
- **The walk's Windows stand-in** (task 5, `12:M1`): its `strict` branch is never taken. Branch 16
  lists `tests/*`.
- **A member's kind hold** (D0): it rests on the member's instance being paired, which every case
  built here meets, a leaf's identity being its instance's id and its path below. No later branch
  lists `compare.py`, so it is the maintainer's, or branch 16's for a probe.
- **Lines past 100 columns** (D0): D0's rewordings run lines of SPEC's section 4.1, of the
  comparing page and of the check reference past 100 columns, beside branch 6's entry on the
  comparison's words. Branch 15 lists the pages.
- **Two notes the page's gates print** (task 3; R119): Vite's warning on a chunk's size and a
  deprecation biome reports, both from before the branch, and no task names them. The
  maintainer's.

**Branch 8:**
- **The terminal's line on a launch code presented again** (D0, `12:I3`): it ends saying that
  this run's address, opened since, does not take the token back, and no longer says whose
  token; the security page names the winner as the one a restart takes it from. Branch 10,
  which lists `gui/*.py`, may reword it.
- **The security page's sign for a launch with no project** (D0, `12:I3`): its bullet on that
  line says the browser is signed out instead of landing on the project, inexact for a launch
  with no project, which lands on the start page, though the sign it describes still holds.
  Branch 15 lists `docs/*.rst`.
- **"Their builds" and "its own directory"** (D0, `12:I4`; R114): both read ambiguously in
  `_readable_project`'s docstring and in branch 7's entry above on the directories a record is
  read under. Branch 10 lists `gui/*.py`, for the docstring; the entry's wording is branch 9's
  D0's. *(Done by branch 10, task 4, for the docstring, which names the builds those records
  describe and the open project's own directory; branch 9's D0 reworded the entry, R154.)*
- **The opening's items held to their entries** (task 1, `4:I8`; R132, R139, R150): the opening of
  Unreleased names about eighty migrations a second time, each beside its entry, and nothing
  holds an item to the entry it names, though later branches will rewrite entries. A test that
  every item names exactly one entry's lead, whole or by a prefix, is branch 15's, whose task 11
  plans an entry naming every migration the sixteen branches make; how long the opening stays is
  for whoever curates 0.12.0's notes.
- **The release tools' refusals** (tasks 2 and 4; R134, R148): the refusals of
  `tools/installed_wheel.py` - a wheel without one `METADATA` or a version, a `ddd` that cannot
  run or hangs, a `ddd gui` that does not answer at the address it printed or prints another line
  where its address should be - and two of `tools/dev_version.py`'s are what a maintainer reads
  on a release day, and no test reaches them, the coverage gate measuring `src/ddd` alone. The
  refusal of `gui/scripts/licenses.mjs` where the installed packages and the lock file disagree
  was shown once, by hand. Branch 16 lists `tests/*`, for the Python half; no later branch lists
  `gui/scripts/`, so the script's is the maintainer's.
- **`installed_wheel.main()` blaming the wheel** (task 4): it reports any `OSError` or
  `ValueError` of its checks as the wheel's fault, though only a fault of the environment
  reaches it: the step is a failure whichever is blamed, and its message names what went
  wrong. No later branch lists `tools/`, so it is the maintainer's.
- **The licence walk's two refusals** (task 2): the one for a package missing from the lock file
  can print a package twice, and the one for a lock file the installed packages disagree with
  could say to run `npm ci`, as the changelog does. The maintainer's, `gui/scripts/` being in no
  later branch's list.
- **ci's two `pip install build`** (task 4, `20:M13`): the `gui` job and `dev-build` install
  `build` at whatever version is newest, where Publish installs it from
  `requirements-release.txt`; harmless while the backend, which decides the wheel, is pinned. No
  later branch lists `.github/workflows/`, so it is the maintainer's.
- **What Dependabot reaches** (task 4, `20:M13`; R130): its first weekly runs show whether it
  moves `requirements-release.txt` and the `[build-system]` table, and vsce, written into an
  `npx` command, is moved by hand, as the developer page says. The maintainer's.
- **A candidate's version in the extension's manifest** (task 4; R143, R151): `0.12.0rc1`,
  which a test would have `editors/vscode/package.json` state as `__version__` does, is not a
  semver version, and packaging most likely refuses it, failing the `extension` job in ci's
  runs and in Publish's; the page calls that untried. A rule for spelling the manifest's
  version under a candidate is the maintainer's to make once a candidate is planned: branch 9
  lists the manifest, but such a rule reaches all ten files that spell the version, and their
  tests.
- **Four suggestions on Publish** (task 4; R148): letting a re-run of `publish-pypi` skip the
  files already on pypi.org, as `dev-publish` does, which would let *Re-run failed jobs*
  complete an upload that stopped partway; checking the tag before calling ci, which would
  refuse a wrong tag at once rather than after the gates; a time limit on each of Publish's
  jobs, as ci's jobs have; and a way to ship a release's `.vsix` when its tagged commit fails
  to package one. Each is the maintainer's call.
- **What only a release shows** (tasks 3 and 4; R135, R152): GitHub starting Publish with the
  call - the permissions it checks as the run starts, the name and the group ci is given there,
  and `build` waiting on `ci` with the development builds skipped; *Re-run failed jobs* inside the
  called workflow; the build's new steps on a runner; Documentation's run on Publish's
  completion, its payload, its firing on a re-run's completion, the group of its own a
  release's run is put in, and a release's deploy running beside master's; the dispatch
  naming a tag, its pypi.org check with it; and a release candidate through the `extension`
  job. The documentation under sphinx 9.1.1 is first built by this branch's pull request, and
  Dependabot's first proposals come with its weekly runs. The dry run among the steps of a
  release shows the first and the third before a tag exists. The maintainer's, at 0.12.0.

**Branch 9:**
- **The panel's check of a type's key** (task 7, `10:I8`; R199): `variables._fixed` takes the key a
  type states from wherever the index points, not checking that the entry there still names the
  type. Branch 14 moves `variables.py` and keeps what it does, and no branch takes it for
  behaviour, so it is the maintainer's.
- **A condition's use on the Shared files tab** (task 7, `14:M13`; R201): the panel calls a
  condition's use of a constant a shape, the comment of `gui/src/lib/shared.ts` still counts
  shapes alone, and a declaration whose dimension spells the constant, and whose condition spells
  it too, appears twice in the Used by table; the count, the uses `GET /api/constant` answers and
  the refusal to remove are right. Branch 11 lists `gui/src/components/*`, where the panel and the
  table live; the comment is branch 14's task 10's, branch 11 not listing `shared`.
- **What the editor reads of a condition beyond a rename** (task 7, `10:I10`): the conditions a
  constant's rename rewrites are missing from the references found from that constant; a rename
  onto a name the build defines as a macro, which a condition spells, is not refused, as before the
  branch; and the word a rename rewrites is matched inside a condition's string literal or header
  name too. No branch after this one changes what `lsp/navigation.py` does, so they are the
  maintainer's.
- **A fix taking another image's answer, and a unit added** (task 10, `10:M3`; R208): a fix taking
  another declaration's answer in is offered by the images that offer it alone, so it may unsettle
  the declaration in an image that offers no such fix; and adding a unit to the vocabulary is not
  checked beyond the document's own projects. They are branch 10's, whose Files list takes the
  settlement in `lsp/edits.py`, or else the maintainer's.
- **The hover's summary across images** (task 10, `10:M4`; R211): where several projects hold the
  document, the shape and the limits are the first project's, so a hover in two images whose types
  disagree shows the first's. No later branch lists `lsp/hover.py`, so it is the maintainer's.
- **Two images' writers in one hover** (the final wave; R227): a reader linked into two images,
  whose input a producer of each image writes, hovers with both producers named as its writers in
  one sentence, which reads like two components writing one variable of one image. Naming each
  writer's image, where two images' writers differ, would tell them apart; behaviour beyond the
  plan, so the maintainer's.
- **Components of one name in two images** (task 10, `10:M4`): the hover knows a component by its
  name alone, so where two images each hold a component of one name it names that name once, where
  find references lists both files. The maintainer's.
- **A finding over the item its place holds** (task 10, `10:M6`): a finding names its key by its
  place in the file, so with a declaration typed above another in one list, unsaved, it is drawn
  over the item at that place until the save, as the pages say. Matching a buffer's declarations
  to the file's by their names would draw it over its own. The maintainer's.
- **A one-line description in quadratic time** (task 10, `10:M11`; R219): `Document.position`
  encodes a line's prefix for each position on it, so every range on a long line costs that line's
  length: a unit's rename over a component of 8,000 statings written on one line took 1.90 s,
  where the pretty-printed file took 0.30 s, as task 10's fourth part measured it on the Linux
  development PC. A position counted on from the last one, offsets ascending, or each line's
  UTF-16 offsets kept by the document, would answer it. The maintainer's, unless a later branch
  changes what `ranges.py` does first; branch 14's task 3 only moves it.
- **The keys of a mismatch in its data** (the final wave; R227): which fix settles which
  `definition-mismatch` is read out of the sentence the analysis writes, which a test now holds to
  the analysis's own words; the server, which writes both, could carry the keys in the finding's
  `data`, which a client sends back with a code action's request. The maintainer's.
- **The orchestration in `server.py`** (tasks 3 and 10; R227): the module holds the session, the
  withdrawal of what is on screen, the folders, and a rename's and the fixes' reach over projects
  with the order of their refusals, near 2,000 lines. Moving that orchestration into a module a
  test reaches directly, `units.engine_edit` to a home of its own, and `word_spans` with the
  helpers mapping json text into `ranges.py` are branch 14's, which moves code across `src/ddd/`;
  so is one closure passed to both of a code action's questions, which share one read of the
  descriptions safely by the order of the two calls alone. Its task 10 takes the docstrings the
  code has outgrown, `_withheld`'s and `_holding`'s among them, which name a file that did not load
  where one that loaded with an error withholds the fixes too.
- **The language server's tests** (`10:M12`; R224): `tests/test_lsp.py` runs past 14,000 lines and
  could be split by class into modules; and nothing checks that the tests use nothing newer than
  python 3.12, the oldest CI runs, mypy checking `src/ddd` and `tools` alone - a parameter python
  3.13 added broke the 3.12 legs. A notification whose uri has a host part no file system takes is
  tested as a `didOpen` alone, no test asserts that find references still lists the reader of an
  image a plugin stops, `edit_answers` relies on a rename's answer carrying id 11 without saying so,
  and task 2's probe runs `ddd check` after the server where, run first, it would say the tree is
  clean before the server answers. Branch 16 lists `tests/*`.
- **The extension manifest's version for a candidate** (R189): the maintainer's, as branch 8's
  entry says; branch 9 changed the manifest's activation and its settings, not its version.
- **A VS Code session end to end** (task 10, `10:M7`, `10:M8`, `10:M10`; R188): CI's `extension`
  job compiles the extension and runs `config.ts`'s tests, and nothing runs VS Code: its
  activation by a description, its registration of the watcher, the folder changes it sends and
  the preview `needsConfirmation` opens were seen by no test. The maintainer's.
- **An interrupt on a Windows console** (task 9; R204): a server started there by hand takes Ctrl-C
  only once another message arrives; an editor ends the run with `exit`. The maintainer's, through
  the pull request.
- **A rename and a broken plugin** (task 5; R196, R226): a rename of anything but a local cannot go
  on while any recorded image's description fails to read, the refusal naming the one a plugin
  stops. The maintainer's, through the pull request.
- **Two folders' project files in a refusal** (task 3): in a workspace of several folders, two
  folders each holding a `project.ddd.json` at their root name it alike in a refusal; naming the
  folder as well would tell them apart. The maintainer's.
- **What a rename reads of the open documents** (task 4): at every rename, `differs_from_disk`
  parses each open document of the projects reached, and reads and parses its file, a cost bounded
  by the documents open. The maintainer's.
- **What the log of withheld fixes keeps** (task 6): a project the log was told of is kept until it
  reads whole, though its description is deleted or no longer parses - at most a repeat line held
  back, and one cheap read per check - and `navigation._named_at` reads the description again for
  each error of an include entry. The maintainer's.
- **A rename's label in the preview** (task 8): the annotation of an edit reaching several files is
  labelled "Rename" alone, where it could name what is renamed. The maintainer's.
- **A refused watch registration** (task 10, `10:M8`): a client's refusal of the watcher's
  registration is dropped without a line in the log; no client is known to refuse it. The
  maintainer's.
- **A new file closed unsaved** (task 1): a document closed without ever being saved, so on no
  disk, has its findings withdrawn at the next check rather than as it closes. The maintainer's.
- **A record whose project is gone** (the final wave): a build record still naming a project
  description that was moved or deleted is announced and not analysed, so a file only its build
  reported on keeps its findings until a check reaches it, or a record changes and everything on
  screen is checked again (R225). The maintainer's.
- **Lines past the wrap** (tasks 2 and 10): a line of `editors/vscode/README.md` runs past the wrap,
  pins of the page tests split phrases mid-way, and the editor page has two lines a hundred
  characters long, beside branch 7's entry on lines past 100 columns. Branch 15 lists the pages.
- **The progress log's rows** (D0): branch 8's row names its ids by the headings of its tasks and
  may miss some, and says it is not merged, which #94 since was; that row and branch 9's are branch
  10's D0's (R228). Corrected by branch 10's D0, which filled
  both: row 8 is marked merged into master (`96900155`) and row 9 is added (#95, `c011143b`).
- **A component two projects include, taken out of one** (the re-review of the final wave): a
  component that two projects include is taken out of one of them, which a save or a change behind
  the editor does, is not open, and no build record runs the other project: its findings are
  withdrawn until the other project is next checked. Before branch 9 it kept the first project's
  findings, stale. Running the other project's place again would settle it, at the cost of a second
  pass of the check. The maintainer's to weigh, and PR #95's body names it.

**Branch 10:**
- **The type judge's sentence, and the spread of limits across images** (task 1, `3:I1`,
  `3:I2`; R267): a type plan is refused where the entry would carry a problem it did not carry,
  told apart by the problem's sentence, so a change bringing another problem worded exactly as the
  entry's own is planned; and the editor's spread of limits across images writes a project's
  producers, or answers `unproduced` there, in an arm no test reaches and which may be out of
  reach, a spread writing to no declaration but one that states limits already. The
  maintainer's.
- **A `**` at a project's root** (task 4, `14:I5`; R239, R313): it watches the checkout's `.git`,
  its `node_modules` and its build trees, as the session's module docstring and the gui row of the
  command reference say, so that committing, installing packages or building there asks for an
  analysis, and each round of the poll stamps every directory under that root. No plan or edit is
  refused for it. Leaving such directories out would part the watch from the loader's walk, which
  goes into them. The maintainer's; branch 15 lists the page.
- **What the poll does not notice** (tasks 4a and 4b, `14:I4`, `14:I5`; R260, R270, R273,
  R274): a record a build writes where the search for records had found nothing, elsewhere than
  beside the description, and a plugin named as a module and installed since, are noticed only
  once something else changes; a module a plugin imports is not watched, and a plugin named as a
  module is not compared, so editing either takes a restart nothing tells of; and the Compare tab
  reports no plugin of a baseline's that changed since `ddd gui` imported it. Tracking what a
  plugin imports is a design decision 14.2's change does not ask for. The maintainer's.
- **The watch's own reading of an entry** (task 4): `_expanded_in` reads an `includes` entry as a
  file first and then as a pattern walked from its own anchor, as `ddd.loading` does, in code of
  its own; sharing it takes a public reading in `ddd.loading`, and the two differ on python 3.12
  over a name too long for the file system, the loader asking `Path.is_file` where the watch asks
  `os.path.isfile`. Both are pinned by the watch's tests. Branch 13 lists `loading.py`, and
  branch 14 moves code across `src/ddd/`.
- **The line offered for a description added to a generated project** (task 4): `_registered`
  names the `CMakeLists.txt` beside the description whether one is there or not. The maintainer's.
- **A plugin path holding a NUL in a description that validates** (the final wave): the loader
  resolves it and raises, so `ddd check` ends with exit 2 and the analysis of `ddd gui` fails,
  where the watch passes such a path over and a description that does not validate reports its
  own error. Branch 12 lists `plugins.py`.
- **The plugin's digest and the bytes run** (task 4, `14:I4`): `plugin-changed` compares a digest
  of the bytes the loader read just before it imports the file, and the import reads the file
  again, or runs the bytecode cached beside it wherever the time and size it recorded still match.
  A save between the two reads is told as a change until the restart, failing safe; an edit of the
  same size within one tick of the file's time runs code the digest does not describe. Running the
  bytes digested, `exec(compile(source, path, "exec"))`, would close both at the cost of the
  bytecode cache of path plugins. And since the loader reads the source itself, a `.py` plugin
  that cannot be read but whose bytecode cache is valid is `plugin-invalid` in every command, as
  the changelog says. Branch 12 lists `plugins.py`.
- **The budgets a rename of every component misses** (task 5, `14:I6`; R279): on the
  Linux development PC, the projects held in memory, the plan of the rename of the unit stated in
  the most files took 1,211 to 1,311 ms at 35,000 declarations and 3,459 to 4,073 ms at 100,000,
  against the second a panel has, and its Apply 2,242 to 2,388 ms and 6,635 to 7,261 ms, against
  the half second an Apply's own change has; and an edit asked halfway through an analysis, held
  to that half second too, took longer in four of seven runs at 100,000, 540 to 940 ms, and in one
  at 35,000, 547 ms. The plan's time is the position scanner, `lsp/ranges.py`, reading once each
  file the rename looks in; the Apply's is `edited` asked twice of each change, by the plugins
  refusal and by `apply_changes`, each reading the file and reading back what it leaves, so four
  scans of every file changed. One `edited` per change would about halve the Apply, the first way
  out, which would still take over half a second at either size: meeting either budget takes a
  plan and an Apply that do not scan every file they touch. What a change reaching every
  component costs is a question of design beyond `14:I6`'s. The maintainer's.
- **The bench's arm for a variable that moved** (task 5): `_in_the_largest_file`, finding the
  variable no longer where the analysis found it, raises the message of the other case, that it
  states no unit of its own. No later branch lists `tools/`, so it is the maintainer's.
- **Two readings of an unparsed file** (task 6, `2:I9`; R243, R286): `vocabulary_project`, the one
  function `project_of` and `unit_project` became, keeps the two families' readings of a file
  that does not parse apart, by `skims`. While a project's only units file is half written, its
  top-level key not yet there, it reads as no units file at all, and Add unit is refused
  `invalid`, saying the project has none to add to; a shared file stopped at the same point is
  reported as a file that did not parse. One meaning would change what one family's `add` creates
  or refuses. The maintainer's; no later branch changes what `lsp/units.py` does.
- **What is left of `2:I10`** (task 6): two copies each of `_plan`, `_raw` and `_protocol_edit`,
  and more than one shape for the edit of a single file, none of them in pass 2's move 4; and the
  units' and the shared `_names`, one function written twice since task 6. Branch 14 moves code
  across `src/ddd/`.
- **The Files tab's judge and the page's own waiting edit** (task 6; R296): a removal or an
  addition the tab judges against a file an edit of the page's own wrote, before that edit's
  analysis lands, is refused `stale`, saying the file changed since the analysis, where the other
  plans answer `analysing`: spec §5 words the tab's judgement so, and a reader asks again by hand
  where `analysing` would have waited. The maintainer's.
- **Two refusals naming less than they could** (task 6): `_refuse_unanalysed` names once two files
  of one name that one waiting edit wrote, where `told_apart` over their resolved paths would tell
  them apart; and `/api/compare` answers that the project did not resolve without naming the file
  that did not load, as `_unresolved` names it. The maintainer's.
- **An edit past its limit read as `ddd gui` not answering** (task 7, `15:I4`; R298): what
  follows a refused body is drained up to 1,048,576 bytes or two seconds, so on Windows a reset
  can lose the answer to an Apply past `EDIT_BODY`'s 8 MiB, and to an Apply past 1 MiB refused
  `401` or `403` for its token or its origin before its body is read, and the page then reads the
  server as not answering. The most a generated project's rename posts, 4,725,352 bytes, is a
  little over half the limit. The way out is for `request` to refuse, unsent, a body larger than
  `EDIT_BODY`, as it refuses an address past the request line's limit. The maintainer's: no later
  branch lists `gui/src/api/client.ts` for behaviour.
- **Decision 3.6's figure** (task 7, `3:I8`; R300): its sentence says a table past about 10,000
  counts is not one `ddd gui` takes, where the address already refuses one past about 8,000 counts
  of five digits each, as the gui row says, and a float map of long decimals sooner. The
  decision's wording is the maintainer's to change.
- **Where the Compare panel draws a finding's place** (task 8, `16:I8`): below its related line,
  where it can read as that related place's own. Branch 11 lists `components/*`.
- **The page drawing `failed` and `refused`** (task 9, `14:M7`, `14:M11`; R256): the state says
  why the last analysis failed and which build records this DDD cannot use, and the page draws
  neither, so until branch 11 a failed analysis reads as analysing still. Branch 11's task 7, one
  banner naming what did not load.
- **An entry whose pattern names several files, and the description read after the analysis**
  (task 9, `14:M9`): the error of such an entry stays with the description, so `ddd gui` lists
  the description as the file that did not load, where the language server counts neither as
  unloaded, as `SourceFile.loaded` and the gui row say; and `named_at` reads the description again
  after the analysis, so a save reordering `includes` in between may name another file as the one
  that did not load until the next revision, as the language server's `_unread` may. Taking the
  entry from what the run itself read would close the second. The maintainer's: no later branch
  changes what `lsp/navigation.py` does.
- **The poller's own failure print** (task 9; R110): the line the poller prints when a poll fails
  is printed bare, where every other print of the session goes through `_printed`; in the server,
  where an analyser runs and stamping raises nothing, no poll fails, so the thread it would end is
  not reached. The maintainer's.
- **The Types tab's row count** (task 9, `14:M8`): counting a row's findings by its panel's rule
  takes about three times as long at 1,000 types with 1,000 findings in one file, a third of a
  second, memoised per revision and within the tab's second; asking `_within_entry` before
  resolving either path would halve it. The maintainer's.
- **Docstrings and a default the code has outgrown** (tasks 1 to 9): `fieldBound`'s docstring and
  the reference page still speak of the double the page no longer sends; `type_plans`' module
  docstring says a refused value takes every type of its file with it, which a refused derived
  range does not; `_choices`' docstring runs on; `_listed`'s calls it the session's one reading
  of `includes`, beside `_included`; `_refusal`'s account of `name=None` leaves out its newer
  callers; `Route.name` names fewer kinds than `FindingRoute.name`; `TypeReply.findings` has no
  docstring; `SourceFile.loaded` opens loosely for a missing include; `PlanReply` says each plan
  route and leaves out `files-plan`; the developer page's account of `settle` and `settled_at`
  names neither the producer rule nor `unproduced`; `graph_of`'s check that an object has an
  owner is dead, mypy needing `owner` narrowed before it goes; and `_described`'s `unloaded`
  defaults to loaded. Branch 14 takes the code and, in its task 10, the docstrings the code has
  outgrown; branch 15 the pages.
- **Two modules grown** (tasks 4 to 9): `gui/session.py` runs to about 2,000 lines and
  `gui/api.py` to about 2,900. Branch 14 moves code across `src/ddd/`.
- **Tests branch 10 leaves** (tasks 1 to 9): no test settles a variable with one reader and no
  producer, nor asks `/api/type-plan` for a refused derived range or an external's header;
  `an_instance` hard-codes the type `Inlet_t`; the table of pairs' external-type row filters
  `type-kind` whatever the key, its typename rows' word `datatype` explained in a comment alone;
  `writeUnseen`'s precondition, that no served pattern watches the directory above the file's, is
  neither stated nor pinned; `SAYING_PLUGIN` is written twice; the guard of private names reached
  across modules misses chained attributes and `getattr`; no test makes a plan whose place moved
  once the waiting edit's analysis lands, as its docstring says; one test asks `_finding` three
  times for one tuple, and one computes a column from the end of its fixture; a test pins the
  private `_unloaded`; `FirstFails` is written twice, `Failing` three times and `Unwritable`
  twice; and the pin of `PlanReply` skips `files-plan` unsaid. Branch 16 lists `tests/*` and
  `gui/e2e/*`.
- **The changelog's long entries** (the last D; R312): the entry on limits written on the producer
  says "Nothing to migrate", where a client of the api that sets limits on a variable nobody
  produces meets a refusal; and the entries on what the poll notices, on `plugin-changed` and on a
  finding leading to its panel run long, as branch 9's do. The api is internal. For whoever curates
  0.12.0's notes, branch 15's task 11 among them.
- **Lines past the wrap** (D0 and the last D; R312): D0's rewording runs a line of the editor page
  to 115 columns, beside branch 9's entry on lines past the wrap, and two lines of the changelog
  that earlier branches wrote run to 112 and 126 columns. Branch 15 lists the pages and
  `CHANGELOG.md`.
- **The page gates' notices** (tasks 1 to 9): Biome's deprecation notice, Vite's warning on a
  chunk's size, Vitest's hint on its cache and a line on stderr in the journeys, each from before
  the branch, beside branch 7's entry on the two notes. The maintainer's.
- **What branch 10 left of the entries naming it** (B10-12, B10-30; R240, R258): branch 1's file
  saved half way after the analysis, whose check at every plan would cost a stat per file at
  every keystroke, and its input answered while a file does not load, R15's trade, are the
  maintainer's; so are its entries on `editing.py` and `variables.py`, which branch 10 changed for
  a plan's spans and hunks alone: a create racing another's, what a refused write says, a folder
  a stage cannot be made in, a settled value refused `unreadable` - where the other plans answer
  `stale`, and since task 6 `analysing` for the page's own waiting edit - and the would-not-load
  sentence, whose keys on the panel stay branch 11's. Branch 3's `1e-400` is refused at the query
  since branch 6, `1e400` in a block staying branch 13's task 7's; branch 7's repaired schema
  letting plugins run stays the maintainer's call under decision M7; branch 8's terminal line on a
  launch code presented again is left as it is, no finding asking it; and branch 9's fix taking
  another image's answer, and a unit added, are the maintainer's, branch 10's change to the
  settlement not reaching them.

## Rulings taken

Every departure from a task's text, with its reason, numbered `R1`, `R2`, and so on.

**Branch 1:**
- **R1.** Task 1 gives `editing.py` its stage of its own and leaves `identity.py`'s writer to task
  6, which routes `ddd id --assign` through `apply_changes`: `13:C2`'s `ddd id` half closes there,
  rather than being written in task 1 and rewritten three tasks later.
- **R2.** Task 4 recognises a generated project by the build record naming it, and could have
  marked it from `cmake/Ddd.cmake` where the record did not suffice; it sufficed for the projects
  the task names, so the module is unchanged. It does not suffice for a description given with
  `PROJECT` whose record sits beside it, which was taken for generated until branch 2's task 10
  (*Left open*, branch 1).
- **R3.** A stage is created by an exclusive open of `<name>.<8 hexadecimal digits>.ddd-staging`,
  not by `tempfile.mkstemp`, whose `0600` would carry into a file the engine creates, which takes
  the access any new file gets; the name is as much its own either way.
- **R4.** A branch's changelog entries for its fixes are written once, at the branch's end, not with
  each task: the plan asks a task for an entry only where it changes the public interface, while
  the Unreleased section names every fix of what `ddd gui` shipped in 0.11.0. A migration line
  stays with the task that makes it.
- **R5.** A fix for a dependency's drift joins branch 1 as task D1, after task 2: the depth test
  accepts both wordings pydantic-core gives its refusal, both cores lying in the range the
  requirements allow, so that no commit leaves a gate red.
- **R6.** Task 2 guards a refused edit's rollback and an undo's roll-forward too, though its text
  names the edit's renames only: a file saved since is left as saved, and named, where an
  unguarded put-back would lose the very save the task keeps.
- **R7.** Task 3 gives `type_plans.set_key` the in-place guard as well, and corrects `kind_of`'s
  docstring, which called it safe: every plan that points by the index asks the in-place question.
- **R8.** The `ddd_add_component()` line task 4 offers keeps `<target>` as a placeholder: nothing
  DDD reads names a component's target, and filling it in needs a change of `cmake/Ddd.cmake`.
- **R9.** Task 4 refuses every file under the CMake build tree - the nearest directory at or above
  the record holding a `CMakeCache.txt` - and not the output directory's alone: an edit anywhere in
  that tree is lost when the build writes it again.
- **R10.** A build whose cache's source tree lies at or under the cache's directory leaves that
  source tree editable, an in-source build's and one configured inside its build tree alike, where
  refusing the tree would refuse every component.
- **R11.** Task 5 keeps the sync, but batches it: every file is staged, the stages are synced
  together on at most `SYNC_WORKERS` threads, then each file is looked at again and renamed, and an
  undo is written the same way. One sync after another made an edit and an undo of many files many
  times slower under the session's lock, and NTFS, journaling no file data, needs the sync; only
  the put-back of a refused write still syncs one file at a time.
- **R12.** Decision 13.4's "the page's sentence" is read as the contract's `Changes` and the
  reference pages: no sentence the page shows claims an edit is made all at once.
- **R13.** Task 10 runs right after task 6, before tasks 7 to 9: task 6 made `ddd id --assign`,
  which a pre-commit hook runs, many times slower on a file of many declarations, and task 10
  depends on none of tasks 7 to 9.
- **R14.** Task 7 also refuses a unit's removal while a file does not load, though its text lists
  only the others: decision 13.3 is about a rename or a removal.
- **R15.** Task 7's "each route answers 409 and names `b`" is read narrowly: renames, removals,
  settles and the unit and value routes refuse, while setting a key, adding an entry, adding or
  describing a unit, and the Files tab stay answered, since decision 13.3 is about renames and
  removals.
- **R16.** Task 7 also refuses as `unreadable`, naming the file, a declaration that produces a
  name - an object declared, a variable read as an output or a local - while a file does not load:
  that file may produce the name already, and loaded, it would give the name two producers.
- **R17.** Task 8 draws `SettleReply.unloadable` on the page in branch 1, with its story, reference
  screenshot and journey, rather than leaving it to branch 11: decision 13.5's "written and
  reported" means the person is told, and wave 1 ships before branch 11.
- **R18.** Task 8 widens the check rather than narrowing the documents: "would not load" is the
  page's own notion, so after the models the check asks the definition's own analysis rules, and a
  named string type's rule where it knows the type, and the documents say what is asked and what is
  not.
- **R19.** On the variable's panel, a value that would name a declaration's storage twice or leave a
  datatype without its conversion, or that the declaration's kind does not take or cannot go
  without, stays refused `409`: decision 13.5's sentence covers the values the panel used to write
  in silence, and a refusal writes nothing.
- **R20.** Task 9's "a name only locals hold" covers any name a component declares `local`: the
  analysis files `local-conflict` for every other declaration of such a name.
- **R21.** Task 11's rounds settle four edges of the code they rewrite: Add refuses a path on
  another drive, which its page now lists; on Windows a path rooted without a drive counts as
  rooted; an entry typed through a link is written with the link's name; and a file created beside
  a description that does not parse gets the defaults, its newline among them.
- **R22.** A refusal because a file changed on disk keeps its sentence until the reader chooses
  again in that panel, as the panel's other refusals do, rather than until the next revision: task
  12 brings that revision a few milliseconds from the refusal, sooner or later than it, so its
  coming says nothing of whether the sentence was read, and the rule needs nothing new in the
  contract.
- **R23.** The final wave takes the documents' clause on the last look only. Closing the create
  case, by linking the stage to the new name and then unlinking it, and on Windows by a rename that
  refuses an existing name, is left open: it is a write of its own, with fallbacks for the file
  systems lacking either, rather than a change of wording.
- **R24.** What the whole-branch review set aside stays so; `unwritable`'s 500 is under *Left open*.
- **R25.** These records keep what a person meets or a later branch needs, the ledger how tasks ran.

**Branch 2:**
- **R26.** The five residuals branch 1's final re-review left join branch 2 as its first task, D0,
  ahead of the plan's: branch 1 took no second fix wave, its pull request being open. D0 ties each
  refusal the page holds to the entry or offer it came from, has five journeys wait on what only
  a refusal's analysis draws, and corrects the plan's records of branch 1; a sixth residual,
  whose cause is older than branch 1, is left (*Left open*, branch 2).
- **R27.** Branch 2 runs D0 first, then the plan's tasks 1 to 9 in order, task 1's story being the
  harness tasks 3, 4 and 7 tell their triggers in, then a task 10 the plan does not list (R29), the
  last to change the module, then its changelog, as R4 has it.
- **R28.** Task 7's "the dead fallback goes" removes only what the verification of `9:M5` found
  dead, the tolerance of a `PROJECT` not yet written or not json, which is now refused at
  configure, as is one naming no project. The fallback task 3 keeps live stays: a root that
  parses and fails its schema is warned of, and the generation and the configure depend on that
  file alone, since such a root still reaches it.
- **R29.** Branch 2 takes the mark branch 1 left it as task 10: the build record says where its
  description came from, `origin: "given"` for one handed to the module as `PROJECT`, and
  `ddd gui` edits only a project whose record says so, which completes `1:C4`'s fix where the
  module is this branch's. The key was to be additive, but the record forbids a key it does not
  know, so a record with it is stamped `format` 2, which 0.11.0 declines saying so and an older
  DDD skips in silence; it is written for a given description alone, so that cost falls on
  `PROJECT` builds, a collected record keeping the format 1 every DDD reads. Writing it only
  where the record lies beside its description would have spared the other `PROJECT` builds as
  well, at the price of a key that comes and goes with the layout: the maintainer's to weigh.
- **R30.** The Makefile cell of task 7 is on every leg of CI - GNU make's generator on Linux, and
  MinGW's on Windows, with the `mingw32-make` beside the runner's `gcc` - picked by the platform
  and never skipped, as nothing in the suite is; the developer page names the `make` it needs.
  The final wave keeps the build stories under make, and of the five shapes of a wildcard the
  plain one, and tells under Ninja alone a case the configure decides alone and the other four
  shapes, which differ from the plain one only in how the module spells the pattern it watches.
- **R31.** Task 1 names a collected image's components by walking its link graph at configure,
  since `BYPRODUCTS` cannot take the generator expression that collects them, and waits for the
  end of the directory calling `ddd_generate()`, so that an image linked after the call is read
  whole; a link behind `$<CONFIG:...>` alone is read for `CMAKE_BUILD_TYPE`, and any other
  expression counts whatever it comes to. A component that walk cannot see - reached through a
  link made, or a library defined, after that directory is done, or registered after it - would
  go undeclared, so the configure stops at it once the top directory is done, naming it; it
  stops too at a component named like a file the templates render, which no build can declare
  twice; and a description the build writes is watched, so the first build to find it
  configures again. No task names these configure errors, and the changelog gives the late one
  its migration.
- **R32.** Task 2's "a clean checkout's first build is said for what it is" is read both ways, a
  test holding each: with the map, the first build's a2l carries the addresses of the image that
  build linked, and an a2l written with no address source says so in a comment.
- **R33.** Task 3 gives `ddd sources` `-W` and `--strict`, which no task names, and the module
  passes it the call's `SEVERITY` and `STRICT`: the configure prints what the tool reports as a
  warning, and a check the build relaxed would otherwise be warned of at every configure, with no
  way to silence it. Since the final wave a `SEVERITY` the tool refuses, naming no check, stops
  the configure in the tool's words, where it was warned of as a project the tool could not
  resolve.
- **R34.** Task 6's commit message repeated words of the review, found once committed and before
  any push, and was reworded with `git commit --amend`, the tree unchanged, against "never
  `--amend`": a quotation must not reach GitHub, and nothing pushed was rewritten.
- **R35.** Task 7's "keyed on the tool's version as well as its path" is met by asking
  `ddd --version` at every configure, once, the answer kept for that run alone: a key on the
  version cannot be had without asking for it, one on the file's size and time misses a wrapper
  script and an editable install, and the question takes some 0.04 s.
- **R36.** Task 7 refuses every empty value among a value keyword's values, naming the keyword,
  where task 6's text names a value given alone: an empty value in quotes is a variable unset or
  mistyped, and one dropped in silence leaves a `SEVERITY` policy weaker than the call says.
- **R37.** Task 7 gives each shared file a stamped step may be read by the path of (the a2l, the
  dictionary and the files the template names give away) a rule of its own under make, depending
  on the step's target, beyond the stamp its text names; the `{component}` headers and a plugin's
  files get none, and stay byproducts: make knows a file only as a rule's output, so a step
  depending on the dictionary's or the a2l's path had nothing to make it with in a fresh tree, and
  after an edit read what the build before had left. Task 10 has `make clean` take those files,
  which the rules had put out of its reach.
- **R38.** Task 7 raises the test job's limit from 25 minutes to 40, the windows legs taking 12.5 to
  15 minutes with the Makefile cell (8 to 14 before it; CI run 43561237620, after the final
  wave's M6): the limit guards against a hang rather than timing the suite. The final wave gives
  some of that time back (R30).
- **R39.** Task 9 changes two behaviours beside its sentences, both its finding's own: `ddd
  check`'s count line agrees in number, and `--dictionary` naming the file a run keeps its
  manifest under is refused for that, where the refusal spoke of the path's length. It rewords
  the advice of the late-link refusal and the reason of the `PROJECT` one as well, the module's
  sentences being what a build prints.
- **R40.** The final wave leaves a plugin's files undeclared, so Review focus 5 goes unmet under
  Ninja for a component compiling one: declaring them takes a plugin naming its files before it
  writes them, which no task of this branch can give. The pages say what such a build reaches
  instead, and what a project can do (*Left open*, branch 2).
- **R41.** What the whole-branch review set aside stays so, a warning for a component renamed in
  the collected mode among it: the pages say the cost of such a rename instead.

**Branch 3:**
- **R42.** Branch 3 runs a D0 first, the residuals branch 2's re-review left and its row of the
  progress log, then the plan's tasks 1 to 8 in order, then its changelog as D2 (R4), task 6's
  entry moved among branch 3's, then the whole-branch review and one final wave, as branch 2 did
  (R27).
- **R43.** Task 1 refuses a whole number past what a double holds in every spelling the grammar
  read when it landed, its table keeping `0x8000000000000001`; task 7 then makes one grammar with
  no hexadecimal, binary, octal or `Infinity`, and that row stays refused by the grammar's own
  sentence. A spelling that would lose a bit is refused as no decimal notation, where the task's
  text has it refused for the bit; `3:C1` and `15:M13` both hold once both have landed.
- **R44.** Task 1 reaches the limits as well as the values, though its text names a plan's values:
  a range's two fields refuse a bound past 2^53, a stated bound past it shows in its file's own
  digits rather than filled in rounded, the meta line says a limit it cannot show, and `settle`
  and `type-plan` refuse a 64-bit limit at or past 2^53 - the same rounding, reached through the
  panel. The values route marks a 64-bit block holding 2^53 itself, where that refusal starts.
  What task 1's re-review left of the physical reading - the check on the raw count, a float
  written as a float, the limits read as the cells read, the server's limits refusal weighing what
  the page sends - task 7 made, its grammar rewriting those lines anyway.
- **R45.** One of task 1's fix commits left a line past ruff's length, which the next commit
  wrapped: that commit alone fails `ruff check`, against "No commit leaves a gate red". Rewriting
  five unpushed commits to mend one line was more risk than the bisect it costs.
- **R46.** Task 3 keeps from the grid exactly the keys its type-to-find takes, one character with
  neither Ctrl nor Meta, judged in `lib`, and settles the grid's first focus too, which its text
  does not name: a field taking the focus tells the table its own cell is the focused one only
  where the table holds none, so the keys after a fresh grid's first focus stay in the field and
  an arrow moves on from its cell, while a click, Tab and Shift+Tab keep React Aria's handling. The
  journeys' thirteen `.fill()`s of grid cells are typed key by key (decision 23.2), and the loop
  that retyped around the jump is gone.
- **R47.** Task 4 covers every chooser with an Apply one press away - the variable panel's, the
  Units tab's rename and the type panel's - and the declare form's Add, though the branch's Files
  list names neither `UnitPanel.tsx` nor `TypePanel.tsx`, nor that form: decision 15.3 is general,
  and each is the same defect. Only Escape and the focus leaving end the text typed; every other
  close keeps it - the arrow's, an Enter that takes nothing and a list the text empties, as well as
  the scroll the task names - and a sentence under the field says how to take the text, each of
  its three wordings true for the chooser it is drawn under.
- **R48.** Task 5 plans several typed cells cell by cell, not as one table: `set_cells` makes one
  edit of a `set` at each typed element's own pointer, so cells nobody typed keep their spelling
  and the file its layout; where the file states one value for every cell, states none or writes
  too short an array, the whole `init` is written, as `set_cell` writes it for one cell. It has a
  route of its own, `GET /api/cells-plan`, beside `value-plan` for one cell and `values-plan` for a
  paste: decision 16.2 asks for one plan, and the whole table written weighed and respelled cells
  nobody typed and outgrew a request for a large block, at the cost of one more route, query model
  and schema. A cell keeps the reading it was typed in when the toggle turns. Left out, and said in
  the pull request: the arrows, Home and End moving the caret, and typed cells dropped without a
  word on leaving the page, so `16:I3` is closed in part.
- **R49.** A task may land as several commits, one per finding or part and one per fix round, each
  pushed for CI as it lands and never amended, rebased or forced, so "One commit per task" does not
  hold after a task's first push; the pull request says so, and the maintainer may squash at
  merge.
- **R50.** Task 6 reaches a scalar's value from its row's Shape column, which reads `scalar`, as a
  grid of one cell with the toggle and no picture, rather than from the panel, and offers the same
  grid for a declaration naming a scalar type, one rule for scalars and value blocks; a scalar
  stating no `init` gains one, and a text `init` and several producers stay refused. The
  description is the declaration's own, two components describing one variable in their own
  words: a field on the panel opened from a component, not from the project screen, written as
  typed, a lone surrogate refused, the empty text taking the key away.
- **R51.** Task 7 reads every number by one grammar, a section's alignment and a raster's event
  among the fields as much as a size, a dimension and a constant's Value; a comma that could be
  either is asked about in the grid with a choice of one press, which no task names; and the five
  json-text fields send `1e400` as typed, the server refusing it in DDD's words, since they have no
  datatype to weigh it by (*Left open*, branch 3).
- **R52.** Every cell the file does not state is drawn hollow, an absent `init`'s included, which
  supersedes the values spec's 5.2, where an absent one drew as greyed zeros; and the picture
  follows the cells, so a grid stating nothing draws none, as a scalar draws none, where a plot of
  zeros lay under hollow cells. The pull request states it as a change of spec 5.2.
- **R53.** Where an axis states fewer breakpoints than the shape has columns, the picture places
  the values at their indices, its ticks reading the indices and, since the final wave, no axis
  named under them, where breakpoints were read at places that were indices.
- **R54.** `type-plan` refuses a unit with spaces around it as `settle` does, the judgement being
  the server's; a plan whose edit would change no byte is no change on four routes, `value-plan`,
  `cells-plan`, `values-plan` and `description-plan`, beyond the cell typed back the task names;
  and `type-plan` stays out of that rule, P19b-13 being the maintainer's.
- **R55.** A value is written as its datatype holds it: a float's as a float - `3.0` for the `3`
  the page sends, `0.0` for the zeros an array is filled out with, `-50.0` for a float's limit -
  since a float written as a whole number past 2^53 is a literal the grid marks as one it cannot
  show, an integer no C type holds; and, since the final wave, a boolean's as `true` or `false`,
  where a `false` set to 1 and back was written `1` and then `0`. A physical value typed into a
  float is planned as the shortest float that comes back, but FLT_MAX as its own double,
  3.4028234663852886e+38: its shortest spelling is a double past it, which the server and
  `ddd check` refuse a `float32`. The cost is a diff respelling a pasted table or an untouched
  bound, which the changelog states.
- **R56.** Task 8 makes a keystroke in a grid draw only the field typed into (`GridStore`), as well
  as the picture linear in its cells, the readings cache task 7's review left joining it, and
  measures a keystroke to its second frame with a bench case of its own, beside the Vitest count
  its text names.
- **R57.** D2 was committed with D0's message, read from a file left from before, which the tool
  writing the new one would not overwrite unread; that one commit, local and unpushed, had its
  message amended to its own, the tree unchanged, against "never `--amend`": the history must say
  what a commit does. Each message has since been written to a new file.
- **R58.** The final wave has the Files tab's three journeys of a stale refusal - Remove, New file
  and Add - wait for a row's kind before their second press, the outside change also renaming the
  rasters entry to a copy of that file: the plan's lines and the finding counted at an entry they
  waited on are answered from the server's newest analysis, and with the analysis' revision held
  back from the page each was met before it came, so a press could fall in the update that
  revision brings; a row's kind is read off the revision the page holds.
- **R59.** The final wave keeps a cell clear of the held offer by a scroll margin of the offer's
  height on each cell of the grid, which the table's scroll into view honours: Ctrl+End scrolled
  the last cell into view after its field had taken the focus, and left it under the offer.
  Padding the window's scroll instead scrolled the window away from the cell typed into at every
  Tab to the offer's own buttons, and a scroll listener while a field holds the focus would push
  back a scroll the reader makes.
- **R60.** What the whole-branch review set aside stays so, the debounce flag task 2 left read in
  the component and the pick dropped while the panel says only that it is updating among it, which
  the pull request states.

**Branch 4:**
- **R61.** Branch 4 runs a D0 first, the residuals branch 3's re-review left and its row of the
  progress log, then task 1, then a D1, a journey that loaded a second address before the page
  held its session and so failed once on a slow leg of branch 3's pull request, then tasks 2 to
  11 in order, then its changelog as D2 (R4), then the whole-branch review and one final wave, as
  branches 2 and 3 did (R27, R42). D1 waited for task 1's review, one agent at a time, branch 3
  having had its one final wave.
- **R62.** Task 1's two commits, local and unpushed, became one with `git reset --soft`, its
  message written anew in the project's own words and the tree unchanged, against "never
  `--amend`": the first message repeated words of the review. D0's first commit, which had taken
  in a directory the docs container left under `docs/`, was undone the same way and made again
  with its own files alone. Nothing pushed was rewritten (R34, R57).
- **R63.** Task 2 checks a `static` as well, though its text names an external variable: against
  the image's local object symbols wherever the image keeps any, and by its address alone where a
  link made with `-Wl,-x` kept none, since gold leaves a discarded unit's statics at offsets too.
  A static that a link kept and whose local symbol a tool removed afterwards is refused where it
  was read.
- **R64.** Task 3 takes the alignment cap from `e_machine` and `e_flags`, where its text names
  `e_machine`: ARM's cap holds only under an EABI, which `e_flags` names, since the legacy ABIs
  (`-mabi=apcs-gnu`, `atpcs`) lay structures out otherwise, and an RV32E image is not checked,
  compilers differing on its cap and no fixture measuring GCC's; either gets the info
  `elf-layout-unchecked`, which no task names. The pages say that a layout a build flag gives
  every structure, `-fpack-struct` or `-malign-double`, is warned though the generated C built
  the same way repeats it.
- **R65.** Task 5 refuses a file that has allocated sections of the program, code and data
  alike, and holds the contents of none of them, as a debug-only companion does, where its text
  names executable sections: an image whose code alone lies outside the file, in a `NOLOAD`
  region, keeps its data and its initial values, and is read.
- **R66.** Task 6 takes as its own the half of `11:M4`'s change that `11:M5` names, a variable's
  type built only when that variable is asked for, and leaves to task 8 the other half, the
  catch per variable, on top: the two findings name one change, and the walk task 6 rewrites is
  where it lives (B4-1). Since R67 that half is 8b's.
- **R67.** Task 6 was split after a safety stop on its damaged-input work. 6a made the
  forward-only walk and its refusal of a sibling that does not advance, the bound of a line
  table header's counts before anything is allocated, and the types built on demand, tested
  over in-memory stand-ins at the cursor's and the bound's own interfaces and over the committed
  fixtures, no damaged image file being built by anyone. 6b, tests end to end over damaged image
  files, is the maintainer's to decide: how, whether and by whom. 6a's fix round was stopped in
  turn before it changed anything, so its four Important findings stay open, and the execution
  stopped to ask the maintainer, task 8 being next on the same ground. On the maintainer's word
  to go on (2026-11-16), task 8 was split as told: 8a, `11:M1` and `11:M6` to `11:M9` with
  `1:M7`, what a well-formed image says; 8b, `11:M2` to `11:M4` with the catch per variable,
  which stays the maintainer's with 6a's four findings and 6b (*Left open*, branch 4).
- **R68.** Task 8a takes both of the ways `1:M7` offered: no conversion is written for an entry
  or a member that is not an enum, and `--identity-conversions` writes the identity on the
  author's word, an image saying nothing of raw against physical. It tells a C++ static member
  by the declaration mark gcc writes on it rather than by a missing location, which a first
  member also lacks where gcc leaves its offset out, and at DWARF 5, where gcc writes the static
  apart, the structure is described by its storage. A unit prefix chooses the unit and nothing
  more: the sizes of a variable are judged over every unit that holds its name at that address,
  which the finding left unsaid.
- **R69.** Task 9 leaves an object out only where the build holds nothing of it - no variable and
  no symbol of its name in the image, a declaration alone included, or no entry of a map with
  entries for it or for any member - where its text says an object the source does not place,
  and decides a structured object as one. Every other reason stays `address-missing`, a linker's
  discard among them where the image records it, by a tombstone address or by an address no
  symbol of the name holds; GNU ld drops the debug information of a unit it discards whole, so a
  conditional variable of such a unit reads as absent and is left out, which nothing in the image
  tells apart from a feature compiled out. The final wave corrected the ruling, which had kept
  every discard `address-missing`. A curve or a map that goes with a left-out axis is named by a
  check of its own, `reference-left-out`, at `warning`, the build holding what the a2l lacks, so
  that a `--strict` build stops for it whatever is done to `condition-mismatch`; since the final
  wave one finding per axis names the axis and its condition. The reference across conditions
  keeps the id it shares with the declarations, `condition-mismatch`, so `-W
  condition-mismatch=ignore` silences both comparisons.
- **R70.** Task 10 reads an `ET_DYN` image under `--image` and says so, as the new info
  `image-load-relative`, where its text has it refused: `8:M5`'s change is a note on the run and
  a sentence in SPEC section 6, the offsets are right for a project that adds its load base, and
  a refusal would turn away every default Debian or Ubuntu gcc build, the shipped example's among
  them (B4-2).
- **R71.** Task 11 holds a consumer's declaration of a variable too, though its text names the
  variable placed: where a unit's debug information declares it without the `volatile` its kind
  carries, or with one the kind does not, `elf-mismatch` names that unit, and an added `const` is
  allowed while `--const-inputs` gives an input one. The definition alone cannot show a header
  that drops `volatile`; clang records no declaration of an extern a unit only reads, so its
  images say nothing of one.
- **R72.** What the whole-branch review set aside stays so, an image with debug information and
  no symbol table placing nothing among it, which the pull request states (*Left open*, branch
  4).

**Branch 5:**
- **R73.** Branch 5 runs a D0 first, the residuals branch 4's re-review left and its row of the
  progress log, then a D1, the item of branch 4's *Left open* the branch owns (a measurement only
  a left-out axis pulled in), then tasks 1 to 10 in order, then its changelog as D2 (R4), then the
  whole-branch review and one final wave, as branches 2 to 4 did (R27, R42, R61). D0 drops the
  compose service from the build page's sentence on the example build's output rather than build
  the shared image again, which the documentation and every compose service use.
- **R74.** Task 1 also has `elf-mismatch` name a consumer's declaration that adds `const`, which
  reverses R71's allowance of an added `const` while `--const-inputs` gave an input one: decision
  M2 removes the option because such a pair of declarations is undefined (C11 6.2.7p2 and
  6.7.3p10), and a check letting it through would bless by hand what the release stops
  generating. Task 1 rewords every sentence citing the option as the reason, in files that are
  branch 4's, and the `constinputs` fixture becomes the red case; a hand-written header adding
  `const` meets a new warning, which stops a `STRICT` build.
- **R75.** Task 1 removes the template api's `.const` and `declaration(const=...)` with the option
  they served, a template still using either refused in a sentence naming the removal, so
  `8:M9`, which task 9 names, is closed by task 1; the address fixtures' builder writes the
  `constinputs` declaration by hand. Every use of either piece that changed what a template wrote
  wrote task 1's undefined pair, so a removal that says so serves better than a `.const` kept
  false.
- **R76.** The refusals of task 1 name 0.12.0, the release `## Unreleased` becomes: the task asks
  for the release that removed the option, and a release before 1.0 that removes one is a minor.
- **R77.** Task 2 pastes the fragment unchanged at the head of `MODULE`, before `MOD_COMMON`, so an
  `A2ML` it holds comes before every `IF_DATA`, and refuses a fragment holding a `MOD_PAR` in a
  project that declares named constants, for which DDD writes one of its own, ASAP2 allowing one:
  the task names one hook, and DDD neither merges nor parses what it pastes (*Left open*, branch 5).
- **R78.** Task 3 leaves a member's `SYMBOL_LINK` naming its path at offset 0 where the a2l is
  written from an address map, as before the link, and the pages say no map can answer it: a map
  gives a symbol's address and nothing of a member's offset, which only the image's layout states
  (*Left open*, branch 5).
- **R79.** Task 4's list of ASAP2 keywords is a module of the project's own, written from the
  format's keywords and the values its grammar fixes, since the standard's text is not in the
  repository and nothing may be downloaded; it holds every word DDD's template and writer spell
  outside `IF_DATA`, whose words are the XCP metalanguage's, and every name a project gives that
  reaches the a2l is held to it, each part of a path too, never a fragment's text, as table 5
  counts an identifier's limits per part. The final wave adds `RIP_ADDR_W` and
  `DEF_CHARACTERISTIC` and takes out `INPUT_QUANTITY`, the name of a parameter of `AXIS_PTS` and
  `AXIS_DESCR` (*Left open*, branch 5).
- **R80.** Task 5 completed only once CI's Windows legs passed its `--gc-sections` test, whose PE
  half was not run here: the first run's legs found MinGW's gcc keeping two objects of a link with
  the macro empty, so the test holds of PE only that the macro keeps no more than the empty one,
  and CI 44026810354's Windows legs passed it.
- **R81.** Task 6's "each reconcile preview" is read as the previews whose words the server
  writes: the quick fix's title says the readers' code is not touched. The settle preview the page
  draws in its own words goes to branch 11, which lists `screens/*`, and the editor's quick-fix
  titles to branch 9, whose Files list names `src/ddd/lsp/*.py`: branch 5 lists neither, and a
  sentence in the page would make it a pull request of the interface, with journeys and
  references (*Left open*, branch 5).
- **R82.** Task 7's display identifier on a member naming a structure stands for that member's own
  segment of each record's path below it, `V[1].j.b` with `j` displayed `J` being `V[1].J.b`, so
  records stay as distinct as their paths and several members' identifiers compose; a leaf's own
  is written as stated, which the elements of an array of structures share, as the pages say. Its
  first form, the path below the member alone, told two elements of one variable apart by
  nothing. `export: false` there drops the subtree, and `format` reaches every leaf below, the
  innermost member's winning.
- **R83.** Task 8 treats a size past 65,535 for `MATRIX_DIM`, `NUMBER` or `MaxAxisPoints` as an
  object past `MATRIX_DIM`'s dimensions is treated, where its text has it refused as `event` is:
  the record is written with its number whole and `a2l-unrepresentable` warns, which stops a
  `--strict` or `STRICT` build. An event always reaches the a2l, while an array of 70,000 need not;
  the commit's subject says "refuse", which the pull request does not repeat.
- **R84.** Decision 8.3 has a derived limit round outward, and task 8's do not all: an end within
  four units in the last place of its twelve digit decimal is written as that decimal, which may
  lie up to those four units inward of the product, since `is_above`'s tolerance treats the two
  as equal and the pinned `7.65` has to read as written; any other end is the number itself.
  `TAIL_ULPS` names the tail. A tool comparing without a tolerance finds the top raw count a few
  units outside such a limit.
- **R85.** The final wave builds each enum's views once, as the review of the whole branch asked,
  and shares the tuple of the enum's entry in `model.enums` with every object it converts, so an
  object whose own copy of the enum documents less states the copy the types header declares,
  where it stated its own; the conversions page already says that the better documented spelling
  is the one reaching the generated code.
- **R86.** A dump this version writes reads back. Task 7 composes a structure member's display
  identifier into the path of every leaf below it, `V[1].J.b`, and the leaf carried it in the
  block a project writes, whose display identifier is one plain identifier, built by a copy that
  validated nothing, so `ddd compare` and `ddd check --baseline` refused the archived dictionary
  of any project that states one. The final wave's round gives a leaf's `a2l` block a model of
  its own, `LeafA2lOptions`, whose display identifier is a path of identifiers, each with its
  indices, and held to no length, since a variable kept out of the a2l is composed with no
  finding, past `MAX_IDENT` included; the analysis builds it with validation. The block a project
  writes keeps one plain identifier. Widening what a field accepts changes the document's shape,
  so the dictionary is format 10, which 0.11.0 refuses as the dictionary of a newer DDD, and a
  format 9 one reads back unchanged.

**Branch 6:**
- **R87.** Branch 6 runs a D0 first, the residuals branch 5's re-review left and its row of the
  progress log, then tasks 1 to 10 in order, then its changelog as D1 (R4), then the whole-branch
  review and one final wave, as branches 2 to 5 did (R27, R42, R61, R73).
- **R88.** D0 reads a leaf's composed display identifier that differs from the baseline's only by
  its instance's name at its head, `V.J.b` against `W.J.b`, as no `changed-a2l`: the rename is
  the leaf's own finding, and a consequence is not told beside its cause. 0.11.0 composed no
  identifier, so the changelog has no entry for it.
- **R89.** Task 1 says a layout that moved once, at each variable whose layout it is, inside that
  variable's one `changed-interface`, and never at the structure: whether an edit of a structure
  moves anything is the variable's question, a member added at the end moving every element after
  the first of an array and nothing of a single variable. The reorder the structure used to report
  is gone, so a structure three variables hold is three findings and one no variable holds is
  none, as the changelog says. A layout that moved and a path added or removed are two facts, each
  said once, and a member renamed in place is also its variable's `changed-interface`, the layout
  holding names so that a swap is seen.
- **R90.** Task 1's "dimensions by value" is read as each dimension's value with its spelling
  kept, a nested array's as every other: the generated code carries the spelling, so a nested
  array respelled at an equal size is `changed-interface`, as a member holding values already was,
  and `7:M2` is settled one way. Against a baseline that records no spellings, the values alone
  compare.
- **R91.** An id has one severity, so the grades tasks 2, 3 and 6 make by whether somebody reads
  the object are ids of their own: a read object's rename is the new error `renamed-read-object`,
  where task 2's text makes `renamed-object` an error; a read object narrowed by a condition is the
  new error `narrowed-condition`; a read measurement's limits widened are the new warning
  `widened-limits`, and narrowed the new information `narrowed-read-limits`. `volatile` turned on
  under a reader makes a precompiled reader's access undefined (C11 6.7.3p6), and joins
  `changed-interface`. The existing ids keep their grades for an object nobody reads, so that a
  `-W` naming one still names one grade; a range that moved both ways is a widening.
- **R92.** A change of the dictionary's shape on branches 6 to 16 stays format 10 and adds its
  sentence to format 10's paragraph: no release has written 10, and the number marks what a
  release reads. Branch 6 changes no field: it reads `types`, `constants` and `rasters` as they
  were.
- **R93.** Task 4 closes `7:M9` whole. The comparison tells `-0.0` from `0.0` by the bytes they
  store, and the loader, which branch 13 lists, refuses a non-zero literal a double reads as 0,
  `1e-400`, as `json-syntax`, naming it, where it refuses NaN, so that `ddd check` holds it to the
  rule that calls it `init-invalid`.
- **R94.** Task 7 gives a constant gone an id of its own, the error `removed-constant`, since a
  reader using its macro no longer builds, and one that arrived the information `added-constant`,
  beside the changed value its text names; a constant has no `id`, so one renamed is the two.
  Constants are compared only when both dictionaries are format 4 or newer, the first to record
  them, and a raster's cycle by the period it resolves to.
- **R95.** Task 8 reports a structured variable with no leaf as an object is, and another `id`
  under its name gives the three findings an object's reuse gives, `reused-name`,
  `removed-object` and `added-object`, where its text names the reuse alone.
- **R96.** Task 9's "its panel says how many" is met by the server. The tab's verdict counts the
  open project's own errors, and the reply carries their count as `own_errors` in
  `gui/contract.py`, outside the Files list, where the reply is typed; the page's three fixtures
  of the reply under `gui/src` gain it, every field of the reply being required, and the page's
  whole gate ran. The page's sentence drawing the count is branch 11's, which lists
  `components/*`: branch 6 lists no page file, and a sentence of the page makes a pull request of
  the interface, with its screenshots. Until then a project whose every error is its own is told
  it cannot replace the baseline above a comparison that has nothing to report, which the pull
  request says, so whether a release waits for branch 11 is the maintainer's (*Left open*,
  branch 6).
- **R97.** Decision 5.6 is read as `ddd compare` reading a component file given as the baseline
  under the floor of `ddd check --standalone`, and one given as the candidate as a project's file,
  so two versions of a component with inputs are compared with `ddd check --baseline
  --standalone`, the command that takes the option. The floor task 5 left `ddd compare` without
  went to task 9, where the three callers share one reading of a component file.
- **R98.** Task 10's object that lost its producer is `missing-producer`, an error, where the
  baseline's object had a producer and the candidate's, still read, has none, said in place of
  that pair's `changed-owner`; an object with no producer on both sides is no change, a dump
  carrying no mark of being a component's (decision 7.2). Where the floor of `--standalone` alone
  silences the check, the comparison says it, as an error the floor does not reach, and a
  project's own `-W missing-producer=ignore` still silences it: `SeverityPolicy` gains `floored`
  to tell the two apart, which no plugin page names, so the changelog does not either.
- **R99.** Task 10's stamp is taken before the read and compared with the stamps after it by
  equality, as the session's poll compares, with no window and no slack. A flat description named
  as a baseline is stamped by the files it names before its first read, so it is kept from that
  read, and a dump's first read parses it once more to learn what it names; a write that keeps a
  file's time and size exactly is not told, as the session does not tell it.
- **R100.** Branch 6 brings each rule it changes to every home of the rule - the registry in
  `diagnostics.py`, the README's table, the check reference, the command line page, the FAQ and
  the file-format pages among them - though its Files list names the comparing page, the
  changelog and two sections of SPEC: a rule that changes reaches all of its homes.
- **R101.** The final wave takes what a component read alone produces as read by every grade that
  waits on a reader. That amends task 5's resolution, under which only an output's removal was
  graded by what one file can know, and the reading of tasks 2, 3 and 6, under which an object
  was read where the baseline records a consumer: a component file records no reader of its
  outputs, so a grade waiting for one could never be given. Renamed, such an output is
  `renamed-read-object`, given a condition `narrowed-condition`, turned `volatile`
  `changed-interface`, and a measurement's limits widened are `widened-limits` and narrowed
  `narrowed-read-limits`, each message saying the readers are not known; a local object and an
  input keep their grades. The price is a supplier's gate that stops on a change to an output
  nobody in the whole project reads.

**Branch 7:**
- **R102.** Branch 7 runs a D0 first, the residuals branch 6's re-review left and its row of the
  progress log, then tasks 1 to 5 in order, then its changelog as D1 (R4), then the whole-branch
  review and one final wave, the order of branches 2 to 6 (R27, R42, R61, R73, R87).
- **R103.** Task 1 holds a file an edit creates to a description's kind as well, the kind
  `session.edit`'s docstring names, beside the project description and included by the edit's own
  change of it, and refuses any other before a file is touched (ruling B7-1): decision M7's
  promise is kept only if it covers every file an edit writes, a created one among them. The cost
  falls on an edit creating a file of another kind, which none of the page's flows writes.
- **R104.** Task 3 listens on `[::1]` on every system, beside the IPv4 socket and on its port, and
  answers there as on `127.0.0.1`, through the one gate, and signed out until the printed address
  is opened there (ruling B7-2). Part 19a's hold goes (P19a-14), since a listening `[::]` would
  answer for `ddd gui` on each IPv6 interface, and the journey of `localhost` has its comments
  brought to the change, though outside the Files list, by R100's rule that a changed rule reaches
  every home. 12:I1's own trigger stays the maintainer's (*Not in any branch*).
- **R105.** No test of branch 7 listens beyond loopback, `127.0.0.1` or `[::1]`, names a network
  path except to loopback, or opens a Windows device unbounded (ruling B7-3, as R117 reads it),
  so that a regressing fix fails instead of hanging or reaching the network. Every host beyond
  loopback, and 12:I1's own trigger, are the maintainer's (*Not in any branch*). The cost: a test
  may prove a refusal by what it is given rather than by reaching what it refuses.
- **R106.** 9:M8 takes pass 9's change (ruling B7-4), so that a `--host` other than `127.0.0.1`,
  `0.0.0.0` or a name resolving to either is refused before anything binds, saying what to give
  instead. A container's user who named one of its own interfaces gives `0.0.0.0` instead, which
  in a container attached to several networks listens on all of them; the final wave puts that
  cost in the changelog, and weighing it is the maintainer's (*Left open*, branch 7). What
  `ddd gui` says of its `-b` and of a project it is given, beside `--host` in `cli.py`, is branch
  12's.
- **R107.** 12:M2 says what the directories `ddd gui` serves guard - `GET /api/file`'s reads, and
  the files an edit writes and a plan previews, each named by its path - rather than making them
  a bound on what an analysis reads (ruling B7-5): decision M7 settled pass 12's open question by
  refusing an edit of a `plugins` list. A reader learns the guard's limit instead of gaining a
  boundary.
- **R108.** 12:M3's long poll waits a second at a time and gives its connection back once its
  client has gone, rather than the page's sentence on it being corrected (ruling B7-6): the
  sentence states the design. It costs the long poll more code than a sentence would.
- **R109.** Branch 7's commit messages and its pull request, under decision M4, name the findings
  by their ids and say what changed; with the changelog's entries, the pages, and the names and
  docstrings of the tests, they tell what `ddd gui` now does, and what a person meets of it, and
  never how a weakness was reached, the input that reached it or what was measured of it (ruling
  B7-7). No finding's id appears in the changelog or on the page. The changelog says less of why.
- **R110.** The three entries of branch 1 under *Left open* that named `gui/session.py` for branch
  7 as well as branch 10 are branch 10's alone (ruling B7-8): branch 7 is pass 12's alone under
  decision M4, while branch 10's list, `gui/*.py`, holds an edit's plan and the session's undo.
  They wait three branches more.
- **R111.** Task 1 reads ruling B7-1 as a rule on the name too (ruling B7-9): a file an edit
  creates is named `*.ddd.json`, `loading.DDD_SUFFIX`, as each create flow of the page names one,
  besides being of a description's kind, since `kind_of` tells a file not named as a plugin by its
  content alone, and some systems run a file because of its name. A description given another
  name, which none of the page's flows writes, is refused.
- **R112.** `GET /api/files-plan` asks the edit's own plugins refusal where it asks `generated`,
  so the Files tab refuses, `409 plugins`, a plan whose Apply would be refused, before the reader
  presses: a plan offering what its Apply refuses would mislead. The page's words for that
  refusal, and the screenshots that would show it, are branch 11's (*Left open*, branch 7).
- **R113.** A reorder of `includes` stays allowed, bringing in and dropping nothing, though it
  reorders the plugins the included descriptions name, where a reorder of one `plugins` list is
  refused; the final wave says so on `_plugins_named`. The walk over what an includes change
  brings in or drops reads under the session's lock, as its docstring says, so such a change
  alone holds other requests while it reads.
- **R114.** Task 2 reads a build record's `project` by one rule in each of its readers - the start
  page's listing, the builds that feed an open project, and the record of how a project is
  generated - since DDD itself writes no record naming anything but a `*.ddd.json` project, while
  a record the rule refuses names no project a request could open. One opened by a path the rule
  refuses, from the command line, opens, but its records' severities do not apply to it, as the
  changelog says; the directories each reader allows are under *Left open* (branch 7).
- **R115.** Task 2's commit message, unpushed, said how its finding was reached, so the controller
  reworded that message alone, its tree the same (`6393102c`), against "never `--amend`":
  decision M4 binds branch 7's messages, and nothing pushed was rewritten (R34, R57, R62).
- **R116.** The `[::1]` listener sets `SO_REUSEADDR` wherever the IPv4 listener does, which is
  every system but Windows, where both keep `SO_EXCLUSIVEADDRUSE` (ruling B7-10): without it a
  fixed `--port` could not be listened on again for a while after a connection the server
  closed, and the refusal would blame another program. What it costs, in the moment between the
  listener's bind and its listen, is benign.
- **R117.** Ruling B7-3 forbids a listener beyond loopback, and not a program that binds the IPv6
  wildcard with `IPV6_V6ONLY` set and never listens (ruling B7-11): the suite's programs on `[::]`
  come back beside the listener, each asserting what each system does, and where no run had shown
  it, the refusal, for CI's Windows legs to settle. A bind that never listens serves nothing, and
  they are part 19a's tests that no other program holds the wildcard at the port.
- **R118.** Task 3's test of a program already on the IPv6 wildcard asserts what each system does,
  as CI's Windows legs showed it; the ruling that decided so also had the page's sentence on a
  fixed port say on which system the refusal holds, and carried both into task 3's round beside
  its review's findings, one agent at a time. The round, through those findings, had the
  sentence name instead what refuses the start on every system, a program listening on `[::1]`
  at that port.
- **R119.** D1 replaces part 19a's changelog entry on the hold with branch 7's entry on `[::1]`, so
  that a reader meets one entry on it, without its sentence on a fixed port held there. Two notes
  the page's gates print, a warning of Vite's on a chunk's size and a deprecation biome reports,
  come from before the branch and stay (*Left open*, branch 7).
- **R120.** Task 5's commit for 12:M5 named, in its subject and body, the input that reached its
  weakness, so before the push the controller rebuilt it and the three unpushed commits after it
  with `git commit-tree`, each on its own tree, as `be7ee189`, `479af8a4`, `41cc5b02` and
  `b17c1e8e` (ruling B7-12): the final tree is the same, so the gates stand, and the test name and
  the two test docstrings naming that input were reworded in task 5's round. Against "never
  rebase": nothing pushed was rewritten, and the originals stay in the local reflog.
- **R121.** Task 5's round has the test that hung on python 3.12, of a request the standard
  library refuses, close its client's sending side once the request line is sent, where a further
  blank line could have been sent instead: bytes the server has not read when it closes can make
  the close a reset, the reason `ddd gui` reads a refused `POST`'s body to its end.
- **R122.** A source comment or a code docstring may say what the code does with an input it
  refuses: ruling B7-7 holds the messages, the pull request, the changelog and the pages to it,
  with the names and docstrings of the tests, and the code may say more than they do.
- **R123.** D1's commit, unpushed, broke ruling B7-7 in its first entry, so before the push it and
  its round's fix were joined by `git commit-tree` into one commit on `02a94de1`, `bbbdf781`, whose
  tree is the fix's, and the first wording never reached the history (ruling B7-13), as R120
  reasons.
- **R124.** The final wave narrows what the branch says rather than the guard: the token names no
  new code, an edit cannot change which plugins the project's descriptions name, and what the
  token can run is what descriptions already name - the open project's, and those of a project the
  start page offers or a baseline under the directory `ddd gui` was started in - in every home of
  the rule. Reading every changed document the loader's way, and whether the token should run
  what those other projects name, stay under *Left open* (branch 7).
- **R125.** The final wave has the terminal's line for a launch code presented again say that
  nothing more is needed only where the browser `ddd gui` opened landed on the project, and
  otherwise to start `ddd gui` again and open the address it prints then, since this run's
  address does not take the token back. What the signed-out view says is branch 11's (*Left
  open*, branch 7).
- **R126.** The final wave leaves four of the whole-branch review's points to later branches, each
  under *Left open* (branch 7): one set of directories for a record's readers, and the create
  rule's place, to branch 10; a description's suffix compared without regard to case, to branch
  14's task 4; and a test's server that takes up to half a second to stop, to branch 16.

**Branch 8:**
- **R127.** Branch 8 runs a D0 first, then tasks 1 to 6 in order, then its changelog as D1 (R4),
  then the whole-branch review and one final wave, the order of branches 2 to 7 (R27, R42, R61,
  R73, R87, R102). D0 carries what branch 7's re-review left and the progress log's rows for #91
  to #93, held to ruling B7-7 and scanned against pass 12 as branch 7's own commits were, those
  items being branch 7's (ruling B8-11).
- **R128.** Task 2 takes `20:M3` from task 5 (ruling B8-1): the entries the licence walk skipped
  and the paths npm's redaction breaks are both its reading of npm's output, so the walk is
  rewritten once, its directories taken from the lock file's keys. Task 5 keeps its other five
  findings.
- **R129.** Task 4 reads "a wheel built from master carries a dev version" as every wheel ci
  builds being stamped with a development version, as `dev-build` stamps its own (ruling B8-2).
  Master's source keeps the last release's version between releases, as the developer page's
  walk of the version has it, so a wheel built from it locally carries that version, and the
  page says so.
- **R130.** Task 4's pins reach the files that pin each tool, beyond its Files list:
  `requirements-docs.txt` for sphinx, and `editors/vscode/package.json`, whose scripts run vsce
  (ruling B8-3). Pinning the actions by sha stays the maintainer's (*Not in any branch*).
- **R131.** Task 1 was to have SPEC 7 say dictionary format 9, as the task asks, with a test
  holding every format number SPEC states to the tool's, so that no statement could drift
  (ruling B8-4, which R138 corrects). Its cost: one fact stated in two sections of SPEC, where
  `5:I1` asked for one.
- **R132.** "Unreleased gains its Migration line" is read as an opening of the section, as
  0.11.0's section opens, saying what the entries' migrations come to read together, each named
  by its entry; branches 1 to 7's entries keep their migration sentences where they stand
  (ruling B8-5, as R139 amends it). The cost: Unreleased's entries do not end in 0.11.0's
  **Migration:** form.
- **R133.** Task 4 keeps in `publish.yml` what task 3's crowning waits on (ruling B8-6): the
  workflow's name, its `release: published` trigger and its run's success, which a test holds.
- **R134.** Task 2's test of the walk runs where the pages' gates run, beside the script under
  `gui/`, since the licences file is built and not tracked, and reads the lock file's non-dev
  packages against the walk's list (ruling B8-7). It came as a check inside
  `gui/scripts/licenses.mjs`, run by every build of the pages: each of ci's legs shows it
  passing, and no committed test shows its refusal (*Left open*, branch 8).
- **R135.** No task runs a release (ruling B8-8): no tag is pushed, no release published, and no
  workflow dispatched against PyPI or `gh-pages`. The workflows' changes are shown by reading
  them, by the tests, which evaluate their expressions and run their steps' scripts, and by ci's
  own runs of `ci.yml`, so a release is the first to exercise the rest (R152).
- **R136.** Task 5 corrects each sentence where it lives, beyond its Files list too, by R100's
  rule: `docs/getting_started.rst`, `requirements.txt` and `src/ddd/addresses.py` among them
  (ruling B8-9). The FAQ sentence `20:M12` shares with `4:M4` waits for branch 15's task 8.
- **R137.** Task 6 drafts the advisory for 0.11.0 to a file, for the controller's pull request
  body: what 0.11.0 lacks, by what master's changelog says publicly, branch 7's entries among
  them, and what to do (ruling B8-10). It says nothing of pass 12's findings beyond what branch
  7's entries say (decision M4, ruling B7-7), and publishing it is the maintainer's (decision
  20.1). The cost: the advisory says less than a reader might want. R146 corrects the versions it
  names.
- **R138.** SPEC 7 already states the tool's dictionary format, `10`, as section 5.3 does, since
  branch 5 made it 10 (R92); the plan's "9" was the tool's when the plan was written. So task 1
  writes the guard alone: every format number SPEC states, the dictionary's and each other
  format it names, is held to the tool's own constant, so that none can drift again (ruling
  B8-4, corrected).
- **R139.** The opening may be a list, one item per migration an entry names, each said as its
  entry says it and naming the entry by its lead, so that a reader who stops there misses no
  work (ruling B8-5, amended in task 1's round). The cost is an opening longer than 0.10.0's
  (R150).
- **R140.** Task 3 takes the plan's reading of `20:I3`, that the site crowns a release only once
  Publish has succeeded, over the lighter one pass 20 offers, which compares the tag with the
  version in Documentation's own build or has the page say how to remove a directory: the
  plan's text binds, and the lighter change leaves crowned a release whose tests failed. The
  cost: Documentation's release path moves to Publish's completion, an event no run here can
  exercise.
- **R141.** A release's documentation waits for every job of Publish's run to pass, the
  `.vsix`'s among them, the `.vsix` being part of what the release makes; task 3's round adds a
  route by hand for a release no re-run of its Publish can finish, Documentation dispatched from
  master naming the release's tag, and the page and the workflow's comments name the re-run that
  works and why *Re-run all jobs* cannot. As first ruled, the route went through whatever
  the release path checks, with Publish's comparison of the tag to the version included, and its
  cost was that a release's documentation could now be deployed in two ways, both under the same
  checks; R149 corrects that: the route lacked the check that defines the release path, that
  Publish uploaded the version, and the final wave limits it to a release pypi.org holds.
- **R142.** A pin's version is, in order, what ci itself installed in its latest green run that
  installed the tool, read off that run's log; the version in pip's cache on the Linux PC; or the
  newest release the index's json names (ruling B8-12). Nothing is installed or committed from a
  download, and task 4's report names each pin's source: `build` 1.6.1 and `twine` 7.0.0 from
  Publish's run for v0.11.0, `hatchling` 1.33.0 and `hatch-requirements-txt` 0.4.1 from ci's
  latest green run, vsce 4.1.1 from the npm registry, and sphinx 9.1.1 as the documentation's
  workflow installed it. The cost: a pin may be older or newer than what a release last used,
  until Dependabot moves it.
- **R143.** A development build after a release candidate is numbered as the next candidate's
  development build, `0.12.0rc2.dev<run>` after `0.12.0rc1`, which sorts after the candidate
  and before both the next candidate and the release, in `tools/dev_version.py` and
  `dev-publish`'s version pattern (ruling B8-13): with the `gui` job's wheel stamped (R129), the
  stamp's old refusal of a candidate would have reached every run, and B8-13's stated aim was
  that a candidate on master fails no job; R151 restates that aim, as removing the stamp's
  refusal, which leaves a candidate's manifest version to a rule still to be made.
- **R144.** Publish's call of `ci.yml` keeps `id-token: write`: GitHub checks a called workflow's
  nested permissions as the run starts, whatever a job's `if:`, and `dev-publish`, the one job
  asking for it, cannot run in Publish's run, `dev-build` being skipped there. The cost: one line
  allows more than any job of the call uses.
- **R145.** Three of task 4's review's points on the developer page go to task 5, which rewrites
  the page's release machinery as steps: its claim that a candidate on master fails no job, where
  packaging the extension needs a semver version; `dependabot.yml`'s comment on the backend,
  against the page and `pyproject.toml`; and its claim that the `gui` job's wheel is numbered as
  `dev-build`'s, true of a push and not of every pull request.
- **R146.** The advisory names 0.11.0 alone as affected, the first release with `ddd gui`, where
  task 6's notes said 0.11.0 and earlier: no `src/ddd/gui` exists at v0.10.0 (R137).
- **R147.** The final wave takes the whole-branch review's Important, the route by hand held to
  a release pypi.org holds (R149), and five of its Minors in the files the wave rewrites: what
  writes a published release's directory again, the tests reading `ci.yml`'s name, Publish's dry
  run among the steps of a release (R152), and the release gate's item and the `docs` extra in
  the changelog; with them the stale line under *Not in any branch*, and these records. The
  cost: a larger wave.
- **R148.** The final wave leaves the rest of the review's points under *Left open* (branch 8):
  the release tools' refusals that no test runs to branch 16 and the maintainer, the opening's
  items unheld to their entries to branch 15, whose task 11 overlaps them, and four suggestions
  on Publish to the maintainer.
- **R149.** The route by hand lacked the release path's defining check, that Publish uploaded the
  version, and was offered where nothing had reached pypi.org, a gate failing in the tagged
  commit included (correcting R141). The final wave limits it to a release pypi.org holds: the
  dispatch reads pypi.org's json for the tag's version before anything is built and refuses one
  it holds no file of, or one it gives no answer for, and the workflow, the page and the
  changelog say what the route checks and cannot. A release pypi.org never received is deleted
  with its tag and created again.
- **R150.** The opening runs about 340 lines, and gives each migration a second home that no test
  ties to its entry (R139): whoever curates 0.12.0's notes decides its length, and branch 15's
  planning is told it exists (*Left open*, branch 8). The cost: an item and its entry may drift
  apart until branch 15.
- **R151.** B8-13 removes the stamp's refusal of a candidate (R143); a candidate on master still
  needs a rule for spelling the extension's manifest version, which packaging needs as semver,
  and making it is the maintainer's once a candidate is planned (*Left open*, branch 8).
- **R152.** The final wave cuts B8-8's cost (R135) with an optional step among the steps of a
  release: Publish dispatched from master to TestPyPI before the tag exists, which runs most of
  the release path and spends the version on TestPyPI alone. The pull request recommends it
  before 0.12.0's tag.

**Branch 9:**
- **R153.** Branch 9 runs a D0 first, then tasks 1 to 10 in order, 7 and 10 in parts (R174), then
  its changelog as D1 (R4), then the whole-branch review and one final wave, the order of branches
  2 to 8 (R127; ruling B9-1). Every order its tasks need between them is their numbering's
  already.
- **R154.** D0 carries what branch 8 left it (ruling B9-2): `docs.yml`'s comment on a tag a
  dispatch names, beyond the Files list; R141 and R143 marked as corrected by R149 and R151, as
  R131 is by R138; the wording of branch 7's entry on the directories a record is read under,
  which branch 8's entry handed to it; and the progress log's rows for #93 and #94.
- **R155.** Each task brings the rule it changes to every home, `README.md` and
  `editors/vscode/README.md` among them, beyond the Files list, by R100's rule as R136 applied it
  (ruling B9-3): until branch 15 the README is one of a rule's homes, and left as it was it would
  have contradicted SPEC from this branch's merge on. Both READMEs change in an editor branch,
  and branch 15 rewrites them anyway.
- **R156.** The probes of tasks 3 and 4 are ported without their early return on an error answer
  (ruling B9-4): task 3's asserts an edit reaching the second image's reader, task 4's a refusal
  naming the unsaved document. Each probe took either of two answers, decisions 10.2 and 10.4
  chose one, and once task 6 answers a defect with an error, the early return would pass a crash.
- **R157.** A task's probe, in the briefs of tasks 1 to 4, is the last function of the excerpt the
  brief carries, ported with the helpers it calls and with the suite's own `published` (ruling
  B9-5): each excerpt ran from the probe module's fixture through every probe above the one named.
- **R158.** Task 1 withdraws a file that was deleted, once, with an empty list, and checks nothing
  from its path (ruling B9-6): once a check withdraws only what its run reported on, no run
  reports on a deleted file again, and a run started from its path is what published a finding
  about a file that does not exist.
- **R159.** Task 1's test checks one document per message, and task 9's review ablates task 1's
  rule again (ruling B9-7): once task 9 checks together two opens that arrive together, the probe
  reports on both projects in one check, and passes without the rule.
- **R160.** Task 2 rewords the pages' sentence on a project file (ruling B9-8): it is searched for
  above like any file, and checked as the project it is where no description above includes it,
  as the code always did and as decision 10.3 has the outermost description answer.
- **R161.** Task 3's closure serves every kind of rename - a variable's, a type's, a constant's, a
  section's, a raster's, and a unit's through its own plan - and every project it reaches is asked
  each refusal a rename asks before anything is answered (ruling B9-9). A quick fix reaching
  across images goes to task 10's first part, which makes one fix of several images' offers; until
  it, a fix pressed at a reader still reached its own image alone.
- **R162.** Task 3's closure reads no description twice in one rename (ruling B9-10): it keeps the
  projects it has read by their descriptions, asks their sources which of the touched files they
  hold, and reads only a build or a candidate it has not read yet, where the search asked file by
  file read every image once per touched file, the cost `10:I12` is about.
- **R163.** Task 4's open document of the project is any open document that is a source of a
  project the rename reaches through task 3's closure, a unit's rename included (ruling B9-11): an
  unsaved mention in an image the document is not in is the half-rename `10:I4` is about. A rename
  may then be refused for a tab of another image.
- **R164.** Task 4 tells a buffer that differs from its file by what the two parse to, the file read
  from the disk apart from any buffer, a buffer that does not parse differing (ruling B9-12):
  compared as text, a CRLF file read through universal newlines would differ from every buffer an
  editor sends for it, and every rename on Windows would be refused. A buffer changed only in
  whitespace refuses no rename, which is harmless, positions being read from the buffer.
- **R165.** Task 4 also refuses a rename that would rewrite nothing, a variable's and a unit's
  alike, saying that nothing on disk spells the name (ruling B9-13): `10:I4`'s change asks it,
  though the task's text leaves it out, and an empty edit is applied without a word.
- **R166.** Task 5's case of no project known is a component read on its own: one that no build
  record claims, that no description at or above it includes, and that declares no project itself
  (ruling B9-14). A project file read alone is a project known, and renames as before; a component
  whose description above could not be read is refused, naming that description and why; a local's
  rename goes on, and every other kind is refused, a unit's too. R196 reads its refusal for a
  description that could not be read as reaching every kind, and R226 takes a local out of it.
- **R167.** Task 6's net wraps every message, the notifications included (ruling B9-15): a request
  the server fails on is answered with the internal error, `-32603`, a code beside the protocol's
  others, and a notification with nothing; each writes its trace to stderr, and the session reads
  on; only `Exception` is caught, so an interrupt still ends the run. The relative record ended the
  session on a `didOpen`, which a net round the requests alone would have left outside it.
- **R168.** Task 6 skips a build record naming its project by a relative path where the server takes
  the records, announcing why as for any record this version cannot use; a uri is built from a
  resolved path, and only where the client gave none; and `discovery.py` and `BuildInfo`, which
  `ddd gui` reads too, stay as they are (ruling B9-16). A hand-made relative record is ignored,
  the log saying why.
- **R169.** The log says why the quick fixes are withheld once per reason while it stands (ruling
  B9-17): at the first request a project's unread file empties, and again only once a check has
  read the project whole and a later one finds it broken. Said once a session it would hide a
  second break, and once a request it is the flood the error notifications were.
- **R170.** Task 6 keeps `window/logMessage` alone, as the task says, and SPEC and the editor page
  say where the reason is: in the unread file's own finding, and in the log (ruling B9-18). A
  reader asking for a fix in another file meets an empty lightbulb, and the reason in the
  Problems list.
- **R171.** Decision 10.1's `-32603` stands, and the editor page says that a client shows a request
  the server fails on as a failed request, with the trace in the server's log (ruling B9-19): VS
  Code shows a notification per failed request, so a defect in the hover shows one per hover while
  it stands, and the session and the findings outlive it.
- **R172.** Task 7 indexes a condition's use of a constant apart from the constant's shapes, in a
  field of its own (ruling B9-20), and takes beyond the Files list `src/ddd/project_shared.py`,
  `src/ddd/shared_plans.py`, the command line page's sentence on a constant's uses, and their
  tests: the Shared files tab counts and lists a condition among a constant's uses, renames its
  word with the constant, and refuses to remove a constant a condition still spells. Modules of
  the page's server and their tests change in an editor branch; no file under `gui/src` does.
- **R173.** Task 7's first part takes three *Left open* entries in the code it rewrites (ruling
  B9-21): the preferred mark goes to the fix the ownership rule orders first, and to none where
  that one is withheld; `_fixed_by` reads a type's key only where the entry still names the type;
  and the editor's reconcile titles end with the page's sentence on the readers' code, which a
  test holds equal to the page's. Where the owner's way is withheld the lightbulb applies nothing
  by itself.
- **R174.** Task 7 runs as 7a (`10:I8`) and 7b (`10:I9`, `10:I10`, `14:M13`), and task 10 as 10a to
  10e, by its five groups, each part with its own brief, commits and review (ruling B9-22), as
  branch 4 split two of its tasks. The cost: seven more dispatches, and one commit per task read
  as one per part.
- **R175.** Task 8 marks an edit `needsConfirmation` only for a client that announced both
  `documentChanges` and `changeAnnotationSupport`, one annotation named by every text edit of an
  edit reaching two files or more, a rename's or a fix's (ruling B9-23): an annotated edit exists
  only inside `documentChanges`, and an annotation is outside what another client negotiated. A
  client that previews without announcing it is not asked.
- **R176.** SPEC 7.2 and the editor page say that the preview decision 10.5 opens lets the reader
  leave a file out, which applies the edit in part, by the reader's choice (ruling B9-24).
- **R177.** Task 9 reads the stream on a thread of its own into a queue, and handles one message at
  a time on the server's thread (ruling B9-25): an open, a save and a watch event mark their
  documents and drop what was read, and the documents marked are checked together once every
  message already queued is handled, before the next request is answered, never waiting for one
  that has not arrived. Broken framing still ends the run with 1. Its test pins one analysis per
  project for a save and its watch event queued together, and one per check when they come
  apart. The cost: a thread in the server, and a publication a batch later than its message.
- **R178.** The hover's dictionary is kept per description until what was read is dropped, resolved
  as the hover resolves it rather than taken from a check (ruling B9-26): a check resolves nothing
  for a project whose read reported an error, where a hover resolves what loaded.
- **R179.** Task 10's tests of a request of another shape assert the invalid-parameters error,
  `-32602`, naming the field, and nothing on stderr (ruling B9-27): after task 6 any exception is
  answered and the session goes on, so a test of the session's survival alone passes without the
  checks.
- **R180.** A quick fix that `10:M2` refuses whole under a moved buffer is not offered, and SPEC 7.2
  says not offered where it said refused (ruling B9-28): an error answer to a code action is the
  notification task 6 took away. The cost: a shorter lightbulb, with no
  sentence, until the buffer is saved.
- **R181.** Task 10's second part reads `10:M4` as its four cases: the readers named across every
  project holding the document, both writers named where two write, and a line naming a reader's
  file, or a writer's, that did not load (ruling B9-29).
- **R182.** A build record's watch event goes to the search for records - what was found is dropped,
  and the open documents, or what is on screen while none is open, are checked again under the
  records - and never to a check as a document, the branch for nothing open taking descriptions
  alone (ruling B9-30): checked as one, a record was read as a component and given a finding of its
  own. R225 checks what is on screen at a record's change whatever is open.
- **R183.** Task 10 registers the watcher once the client says it is initialized, and only where it
  announced the dynamic registration of watched files, for `**/*.ddd.json` and `**/ddd-build.json`,
  the extension dropping its own file events in the same commit; a message carrying an `id` and no
  `method` is a client's answer, and is answered nothing; and the description of
  `ddd.buildDirectories` says a change takes a restart (ruling B9-31). A client without dynamic
  registration gets no watch events, as it got none from the server before.
- **R184.** Task 10 narrows when the extension starts the server, not when it is activated (ruling
  B9-32): it starts it once a `*.ddd.json` is open or a workspace folder holds one, deciding so in
  `config.ts`, which imports no `vscode` and is tested by node, a file beyond the Files list's
  names. Activated only by a workspace holding a description, the extension would start nothing
  for a description opened outside a folder or created after the window opened.
- **R185.** Task 10 reads a relative `-b` against each workspace folder, in the server, the
  extension's arguments unchanged, and its migration is the changelog entry written with it (ruling
  B9-33): it was read against the working directory, and an option's meaning is the interface the
  changelog's preamble names. An editor starting `ddd lsp -b build` from a directory that is none of
  its folders finds another build tree.
- **R186.** Task 10 refuses an external type's rename by one check over the index, which the server
  and `type_plans.rename_type` both ask, `type_plans.py` and its test joining the Files list (ruling
  B9-34): the page's Types tab renamed an external type through the same sites, and the two clients
  are not to disagree about what a rename refuses. One module of the page's server and its test
  change in an editor branch. R220 corrects what the index was taken to hold.
- **R187.** Task 10 renders a unit's rename in linear time, a batch of independent sets made against
  the text as it was read, the entries a merge takes out still made in turn (ruling B9-35):
  `editing.py` joins the list, its helpers for edits made at once being shared. A document built
  after each operation was the quadratic part.
- **R188.** A change of the extension is proved by CI's `extension` job on the pushed commit, as the
  Windows legs prove theirs; here a node test that imports no `vscode` may be compiled in scratch
  with the page's TypeScript (ruling B9-36): `editors/vscode` has no installed packages on this PC,
  and installing them is a registry download. A compile error in `extension.ts` is first seen on
  CI.
- **R189.** Of the *Left open* entries naming branch 9's files (ruling B9-37), the editor's own id
  fix joins task 10's last part beside `10:M12`'s line endings, both an editor fix writing other
  bytes than the engine; the naming of unread files joins task 6, in the server's sentence and in
  `units._names` where two files share a name, the page's halves staying branch 10's; the three
  entries of R173 join 7a; the wording of branch 7's record entry is D0's (R154); and a candidate's
  version in the extension's manifest stays the maintainer's.
- **R190.** At the maintainer's word to continue, branch 9 runs from task 3 to its pull request, and
  the controller pauses once the pull request is open, as the maintainer first asked.
- **R191.** cc003bc5's message stays as committed, and the pull request says what it got wrong:
  commits are never amended.
- **R192.** A description the closure meets and cannot read refuses the rename too, rather than
  being skipped: task 5's refusal covers every description a rename's search or its closure meets
  and cannot read, naming the image where a record names one. Until task 5, a rename half-applied to
  an image whose description a plugin stops, as before task 3.
- **R193.** Only a refusal from a project the document is not in names that project's image; a
  refusal from the document's own projects keeps its words, which earlier tests pin, and the pages
  say both. A refusal from one of two images the document is in names neither.
- **R194.** Task 4 asks for the open documents that differ once the closure's loop is done, before
  the answer (R163).
- **R195.** A rename's round trip on Windows is proved by CI's Windows legs on the pushed commit.
- **R196.** A rename is refused where a description it needs could not be read, whatever is renamed:
  a build record holds no list of the files its image reads, so a rename cannot tell whether an
  image whose description a plugin stops holds a file it rewrites without reading that description;
  the refusal names the description and why, and the pull request tells the maintainer that a rename
  cannot go on while any recorded image's description fails to read. R226 revises it for a local.
- **R197.** Task 6's round carries R189's item for task 6, which its dispatch left out: two unread
  files of one name told apart, in the server's sentence and in `units._names`, and the refusal
  for an include that names no file naming the file it names, not the project description.
- **R198.** Task 7's first part mends in its own round a fix reading a types entry that a types
  buffer has moved, rather than leaving it to task 10: `10:M2` is about a buffer that moved a
  declaration an edit touches, not a types file a decision only reads, so no later task held it.
- **R199.** `variables._fixed` taking a type's key from wherever the index points, with no check of
  the name there, goes to *Left open*: no branch owns `variables.py`.
- **R200.** The journeys of `/api/fix` and of the settle route, whose answers task 7's first part
  changes, are proved by CI's journeys on the pushed commit.
- **R201.** The Shared files tab's word for a condition's use goes to *Left open*, for branch 11:
  R172 keeps every file under `gui/src` out of the editor branch, and a change of the page brings
  its gates, journeys and screenshots. The count and the refusal are right meanwhile.
- **R202.** Task 7's second part is read by CI's journeys and other legs on the pushed commit: no
  journey or example spells a declared constant in a condition.
- **R203.** Where a pin of task 8's page sentences was not red first, its ablation killing it stands
  for the red.
- **R204.** On a Windows console, Ctrl-C reaches a server started by hand only once another message
  arrives: the pull request names it for the maintainer, and CI runs the subprocess test on
  Windows. An editor ends the run with `exit`.
- **R205.** Task 9's tests of the standard input on python 3.12 and 3.13, and on Windows, are proved
  by CI's six legs.
- **R206.** A save and its watch event are one analysis when the event is queued behind the save,
  and two when it comes later; both stand (R177), and a run against a real client's timing is the
  maintainer's.
- **R207.** The handshake refuses a client capability of another shape than the protocol's, naming
  it, rather than reading it as not announced: every field the server reads is checked alike, and
  VS Code sends well-formed capabilities. A client sending another shape for an optional
  capability cannot start the server until it is read as not announced, a few lines; the changelog
  and the pull request say so, since it reverses task 8's tolerance.
- **R208.** A fix taking another declaration's answer in is offered by the images that offer it
  alone, and adding a unit to the vocabulary is not checked beyond the document's projects: both
  were so before the branch, and neither is one of `10:M3`'s cases, so they go to *Left open*.
- **R209.** The quick fix that respells an unknown unit is withheld wherever Rename Symbol refuses
  that rename, an unsaved document a rename reaches among the reasons: it is `10:M2`'s not
  offering at its widest, on the safe side, and the changelog says so; R227 names the step it asks
  as a migration.
- **R210.** f1433c26's message, untrue of a producer opened through a link and corrected by
  8dfe9ffd's docstring, stays as committed, and the pull request names it beside R191's.
- **R211.** The hover's summary facts, the shape and the limits, stay the first project's where
  several hold the document: the line naming the files that did not load is for `10:M4`'s cases
  (R181), and the facts are none of them, so they go to *Left open*.
- **R212.** A unit's rename renders in linear time, and `codeAction/resolve` is not built: `10:M11`
  names it as one way, and linear rendering answers the cost with no capability for a client to
  announce. A code action still renders its plans as it is answered, each in linear time.
- **R213.** `type_plans.rename_type` refuses an external type, and the page shows that refusal as it
  shows any other; no code under `gui/` changes in branch 9, the page's own controls being branch
  11's. Until then the page offers a rename of an external type that it then refuses.
- **R214.** Where a project holding the document does not resolve, a plugin stopping it, the hover
  says so in one line naming that project as a rename's refusals name an image, wherever it names
  readers and writers, and the pages say so: a project left out makes every name the hover gives
  partial, and answering nothing would drop what the other projects say.
- **R215.** A part split into several commits runs the whole gate at its last commit, each earlier
  one its focused suites, ruff and mypy: CI runs on the head. An earlier commit may hold a red gate,
  met only by a bisect (R218, R222).
- **R216.** Two corners of task 10's third part go to *Left open* at first: a file also under a
  nested folder that stays kept what the outer folder's project alone had said of it, once that
  folder was removed, and a record's change while documents are open checked those alone. R217
  settles the first, and R225 the second.
- **R217.** A change of the workspace folders checks again every file whose findings are on screen,
  as well as the open documents, and a test removes a folder with nothing open, in task 10's last
  part: a file whose findings only the removed folder's checks gave is checked again, so the
  pages' answer as if the folder had never been named holds. One more check of every file on
  screen at a folder change, which is rare.
- **R218.** 6850c998 and acd2f6c3 leave `tests/test_editing_at_once.py` red, and b4a5339a mends it:
  the five commits of task 10's fourth part stay as they are, and the pull request names the two
  and the one mending them, so the maintainer can squash them at the merge; rewriting history
  needs the rebase the plan forbids its workers.
- **R219.** On a description written on one line, a plan's rendering and every range the server
  sends still take time quadratic in the line's length, and go to *Left open*: the quadratic part
  `10:M11` names, a document built per operation, is gone, and what is left is what
  `Document.position` costs on a long line, which every range on such a line pays, a fix of
  `Document` for every caller.
- **R220.** R186's premise is `Index.externals`, an external type's name and its header: the index
  recorded no type's kind, and the external's is the one kind the check needs.
- **R221.** As R45 kept one of branch 1's commits that failed a gate, branch 9's middle commits that
  leave one red stay as they are: the pull request names 6850c998 and acd2f6c3 as leaving failures
  in `tests/test_editing_at_once.py`, b4a5339a as mending it and 6850c998's message as superseded,
  and task 10's last part runs that suite whenever it changes `editing.py`. A bisect stopping at
  either needs a skip, and the maintainer can squash them at the merge.
- **R222.** 6b31f399 to cb5b6e95 each fall one branch short of the coverage gate, which 93be303c's
  test covers: they stay as they are, and the pull request names them beside R221's two.
- **R223.** A `definition-mismatch` naming two keys is carried by neither key's fix, both fixes
  still offered at the declaration: each action carries the findings it settles, and one claiming a
  finding it leaves in place is worse than one silent about it; applying one fix leaves a finding
  naming the other key, which that key's fix carries. A declaration differing in two keys settles in
  two steps.
- **R224.** The branch's head failing two of CI's python versions, 3.12 and 3.13, in test code, goes
  to the final wave rather than to a round of task 10's last part, the whole-branch review reading
  the checkout: the tests read a file's bytes, and `Document` is built with its text alone, a closed
  file's line ending set by `read` after it, so that it is called as the tests' copy of the old walk
  is. CI on the pushed head proves both.
- **R225.** The final wave withdraws a file whose findings no run reports on any more, superseding
  R182's checks of what is open and R216's second corner: a check withdraws a file that a run from
  the same place reported on the last time and that no run reports on now, and a watched
  description whose findings are on screen is checked whatever is open, as is every file on screen
  at a record's change. The cost: an analysis per project with findings on screen that a pull
  touches, and what each run reported on, kept by where it ran from.
- **R226.** A local's rename is not refused for a description that could not be read, revising R196
  as it reaches a local: a local is spelled in its own file alone, whichever image holds that file,
  so no description, read or not, changes what its rename reaches. A local may be renamed while a
  plugin is broken in an image holding its file, which changes nothing that image's description
  says.
- **R227.** The final wave also takes six of the whole-branch review's Minors, each a few lines of
  the branch's own code, tests or sentences: a document closed unsaved is checked again where its
  buffer drew its findings; two changelog entries name their migrations, each with its item in the
  opening; a test settles the fixes against the analysis's own wording; `server.py`'s docstring says
  what the module holds; the pages say that a reached project's unread file may have loaded with an
  error; and `ddd lsp`'s help, the README and the FAQ say where `-b` is read and the usual names
  searched. Naming two images' writers apart in a hover, and the keys of a mismatch carried in the
  finding's data, go to the maintainer, and moving the orchestration out of `server.py` to branch 14
  (*Left open*, branch 9).
- **R228.** The final wave writes branch 9's rulings from R153 and its *Left open* entries; the
  progress log's rows are branch 10's D0's.

**Branch 10:**
- **R229.** Branch 10 runs a D0, then tasks 1 to 9 in order, 4, 6 and 9 in parts (R238, R247,
  R257), then its changelog as the last D (R4), then the whole-branch review and one final wave,
  the order of branches 2 to 9 (R153; ruling B10-1). Every order its tasks need between them is
  their numbering's already.
- **R230.** D0 also rewords SPEC 7.2's sentence on a description the client reports changed, and
  the pins `tests/test_documentation.py` holds of it and of the editor page's (ruling B10-2):
  SPEC 7.2 is the rule's fourth home, beside the three D0's brief named (R155).
- **R231.** Each task brings the rule it changes to every home, and takes the test file of each
  module it changes, beyond the Files list, by R100's rule as R155 applied it (ruling B10-3): the
  list names `declaration_plans.py`, `object_values.py`, `plugins.py` and `shared_plans.py` but
  not their tests, and until branch 15 the README is one of a rule's homes. Task 1 takes
  `type_plans.py` and the models' home of its judge, task 4 its check's homes, task 5
  `variables.py`, `editing.py` and `project_units.py`, task 6 R246's modules, task 7 the security
  page, and tasks 8 and 9 the page's files their findings reach. Branch 15 rewrites the pages
  anyway.
- **R232.** A task that changes `gui/*.py` runs the journeys after building the page, one that
  changes a contract model regenerates the page's schemas first, never committing them, and one
  that changes `gui/src` runs the page's gates (ruling B10-4). A new field of `State` or of
  `Finding` is required, as the contract's tests pin every field, so every literal of either in
  the page's tests and stories carries it; where a component or a story changes, the screenshots
  compare, and every reference that moves is embedded in the pull request with its sentence.
  Windows is proved by CI's three journey legs alone.
- **R233.** Task 1's judge of a type plan asks the models about the type entry as the plan leaves
  it - validated as a type, a scalar's derived range held finite as the analysis holds it -
  through `type_problem`, beside `definition_problem` in the models, which `type_plans.set_key`
  asks (ruling B10-5): `definition_problem` validates a data object's definition, which a type
  entry is not, so asked of a type it refuses every plan, and the task's one rule for both
  clients holds of the models answering. A module branch 13 lists gains a function.
- **R234.** The judge refuses a type plan the models refuse, `invalid`, in their words, as the
  vocabularies' plans refuse, and decision 13.5's planned-with-a-sentence stays the variable
  panel's alone (ruling B10-6): `PlanReply` has no `unloadable`, the Types tab has no place to draw
  one, and a types file the loader refuses takes every type it declares with it. Task 1 asks
  nothing new of `settle`, whose half of `3:I1` branch 1's task 8 closed.
- **R235.** "Min and Max travel as text" is read as `limitsRaw` writing each bound in the digits
  typed, a float's keeping its point, its signature and every check before it unchanged, under
  decision M3 (ruling B10-7): the page still refuses a bound it cannot hold exactly, and the
  server's `limits_refusal` stays. Moving the template to the server would change both panels'
  screens, branch 11's.
- **R236.** "The producer" is every declaration of a producing scope, an output or a local's own,
  so where two produce, both take the limits; where no declaration states limits and none
  produces, the plan is refused, saying none produces the variable (ruling B10-8). The rule is
  decided in `settle` over every declaration, `settled_at`'s answer for one declaration kept for
  the editor's actions, and the gui row says it: decision 3.3 is silent on none and two, and an
  empty answer is the silence `3:I2` is about. A variable that is only read cannot be given
  limits from the panel.
- **R237.** Task 3's table holds, for each pair of pass 14's categories, the panel's word against
  whether `ddd check` files `definition-mismatch` on that key, and the panel reads silence as the
  models' default for a key they default, `unit` as `""` (ruling B10-9). Three pairs stay apart by
  design, each held as what it says: `kind`, which no row shows; two types of one meaning, which
  the `typename` row tells apart; and an external type beside a scalar, which the check files as
  `type-kind`. The task's rule alone left two of the finding's pairs apart.
- **R238.** Task 4 runs as 4a, `14:I5` with the session's *Left open* entries, and 4b, `14:I4`,
  each with its own brief, commits and review (R174; ruling B10-10). A plugin whose bytes moved
  since they were imported is reported by a check of its own, `plugin-changed`, which `ddd gui`
  files on the plugin's file, saying the server has to be restarted, with every home a check has:
  the registry, the check reference, the README's and SPEC's tables, SPEC's and the plugin page's
  sentences on editing a plugin, their pins and the changelog. `plugin-invalid` says the module
  exposes no well-formed `PLUGIN`, and reusing it would change a check's meaning.
- **R239.** Task 4a stamps, beside the files the analysis read, the directory each `includes`
  pattern expands in, every directory a `**` walks among them, every path a `plugins` list
  spells, loaded or not, and every build record the search finds, the refused among them; the
  stamps join the analysis's own signature and never `named_by`, which a comparison's baseline is
  stamped by (ruling B10-11). Creating or removing an entry moves its directory's time, and a
  refused record mended is a change the page must notice. The cost: a stat per directory and
  record at every poll, every directory under a project's root where a `**` starts there
  (*Left open*, branch 10).
- **R240.** Task 5 takes `variables.py`, `editing.py` and `project_units.previewed`, with their
  tests, beyond the Files list, a plan's lines coming from the spans the engine's own edits
  replace, at once and in turn (ruling B10-12): the lines `14:I6` names are `variables.py`'s, and
  only the engine knows what an operation replaced. Spans touching one line make one hunk, so the
  journeys' counts hold; the undo's preview, two texts and no operation, keeps difflib.
  `tests/test_editing_at_once.py` runs whenever `editing.py` changes (R221).
- **R241.** Task 5 makes `POST /api/open` answer the open project, or one the last listing found,
  before it walks the start directory, walking for any other path, and the bench times the open
  through `POST /api/open`: both, where the finding offers either (ruling B10-13). Timed as it
  was, the open would have recorded a budget missed and mended nothing. A project created since
  the last listing costs one walk, as every open did. R261 holds the open answered so to the
  walk's own checks.
- **R242.** Task 5's red tests count work, not time: a plan's hunks enter no difflib, the lines
  they compare stay near each span however long the file, `declarable` reads no producer's file,
  and a `set` reads no included file for its project (ruling B10-14). The bench's two new
  measures, a plan in the largest file and an applied rename, each with its budget, are run on
  the Linux development PC at 35,000 and 100,000 declarations and written on the reference and
  developer pages, and branch 1's unit rename that parsed each file twice is measured with them
  and given one parse. No gate times the machine.
- **R243.** `2:I9`'s other half, `project_of` and `unit_project` made one function, goes to task
  6's first part, pass 2's move 4, once task 5 asks `project_of` for `add` alone (ruling B10-15):
  task 5's text kept `2:I9`'s cost and left the rule written twice, the two disagreeing on what a
  file that does not parse means. R286 keeps both readings.
- **R244.** Task 5's applied rename records the bytes its body is, and task 7 sets the limit of
  `POST /api/edit` from the largest of them, with room for longer paths, testing it through the
  socket (ruling B10-16): the bench applies through `Api.handle`, which no body limit reaches, so
  in process an applied rename passes however the server would refuse it. R297 sets the limit.
- **R245.** Task 6 makes public every private name reached across modules, the five `gui/api.py`
  took from `gui/session.py` and the one `gui/compare.py` took since branch 6, `_named_by` (ruling
  B10-17): `2:M2` is about every such name, six at the branch's start.
- **R246.** Task 6's one `Plan` and one plan refusal replace the plans of one field and the
  refusals the finding names, in a module below `lsp` and `gui` that each plan module imports
  without a cycle, `ddd.plans`; `lsp/units.py`, `type_plans.py`, `file_plans.py`, `lsp/server.py`,
  `lsp/edits.py` beyond the settlement and `project_units.py` join the list with their tests
  (ruling B10-18): pass 2's move 4 names those classes, half of them in modules the list left
  out. The editor's modules change in a branch of the page's server, their behaviour kept.
- **R247.** Task 6 runs as 6a - one `Plan`, one refusal and one `_answered`, the names public,
  R243's one function and the *Left open* entries that keep behaviour, the suite passing
  unchanged - and 6b, the *Left open* entries that change what a refusal answers, made once in
  `_answered`, each part with its own brief, commits and review (ruling B10-19): a refactor
  reviewed with behaviour changes inside it can be read as neither.
- **R248.** Task 7 raises the body limit of `POST /api/edit` alone, as that route's own, read
  only once a request has shown the token and the page's origin, and keeps `MAX_BODY` for every
  other body, `POST /open`'s among them, and for the drain (ruling B10-20): raised, `MAX_BODY`
  would have every route read the larger size before refusing a body. The cost: two limits where
  there was one.
- **R249.** Task 7 brings the limit to the security page's sentence on what a body may promise,
  beyond the list, and decision 3.6's sentence into the refusal and onto the gui row of the
  command reference (ruling B10-21): the guide the decision names is branch 15's, written from
  the GUI as branch 10 leaves it.
- **R250.** "A plan past the request line's limit says why" covers every plan the page asks by
  `GET`: `request` refuses an address past the limit before it sends it, naming the route;
  values-plan's sentence says, as decision 3.6 has it, that a table past about 10,000 counts is
  not one `ddd gui` takes, and how else to set it; and the standard library's refusals drain what
  is left before the close, as `ddd gui`'s own do (ruling B10-22). One plan alone was guarded
  before, any other past the line meeting the standard library's page. The cost: one comparison
  per request.
- **R251.** Task 7's brief carries the verification of `3:I8` whole, where it had been cut short
  (ruling B10-23): a finding and its verification read together are a task's specification, and
  the comment it corrects is in the task's own file.
- **R252.** `contract.Finding` gains `line` and `column`, required and null where the loader gave
  none, on every finding, and the panel draws `file:line:column`, or the pointer, where a finding
  leads nowhere; task 8 takes the page's half beyond the list - the place said in
  `lib/findings.ts` beside `noRouteReason`, its line in `FindingPanelView`, the stories' fixtures
  and every `Finding` of the page's tests, the references it moves and a journey of a half-saved
  file (ruling B10-24): what the panel draws is the page's. Branch 10's pull request becomes one
  of the page's, its screenshots embedded, and branch 11 edits a component branch 10 changed.
- **R253.** Task 9's first part counts statements in a field of its own, `State.statements`, and
  keeps `counts` as the rows the Findings window sizes itself by, the lines above the tables
  reading the statements, and the journeys and the `State` literals changing with them (ruling
  B10-25): `counts` changed in place would size the window below its rows, the last ones never
  drawn. Two counts in the state, and page files branch 11 lists change here.
- **R254.** `/api/values` answering a structured variable, a dropped object and a curve of a
  structure is read as `14:M3`'s change: the refusal says why there is no grid, naming the
  finding that dropped the object, and never that the project declares no such name (ruling
  B10-26). A grid of a structure's members is a design the finding does not ask for, and the
  Shape column's button for one is `3:I3`'s, branch 14's task 6, so the button still offers a
  grid that answers with a sentence.
- **R255.** Task 9's second part takes `project_types.py`, and its third `finding_routes.py` and
  `project_shared.py`, each with its test, beyond the list (ruling B10-27): the findings' own
  lines are there.
- **R256.** Task 9's third part lands `14:M7` and `14:M11` as fields of `State`, why the last
  analysis failed and which build records this DDD cannot use, with their reasons, as the start
  page lists them, and a refused record gets a line in the terminal, as `ddd lsp` logs one; the
  page's drawing of both is branch 11's task 7, one banner naming what did not load (ruling
  B10-28): a line drawn here would be drawn again there. Until branch 11 the page is told and
  shows neither (*Left open*, branch 10).
- **R257.** Task 9 runs as four parts, each with its own brief, commits and review (R174; ruling
  B10-29): 9a the counts and names, 9b the reads, 9c what the page is told, with two of R110's
  corners, and 9d the contract's sentences, after tasks 2, 6 and 8 changed some of them.
- **R258.** Each *Left open* entry naming branch 10 or a file of its list goes into the task
  rewriting its function, or nowhere, with its reason (ruling B10-30): R110's three entries to
  tasks 4a and 9c, and the chooser's locals to task 3, read off `Index.scopes` since
  `declaration_plans` imports `variable_keys`; the entries marked done say where the others
  went, and *Left open*, branch 10, what went nowhere.
- **R259.** `plugin-changed` is an error by default, which `ddd gui` alone files, on the plugin's
  file; `ddd check` imports afresh and never files it, and no plan or edit is refused while it
  stands: every finding after the change is the old code's, and a warning would leave the
  headline's error count over an analysis of code no longer on disk. An error where a warning
  might do, until the restart the finding asks for.
- **R260.** A module a plugin imports is not watched, as `14:I4`'s trigger has it: the pages say
  that editing one takes a restart, and *Left open* records it as the maintainer's, tracking a
  plugin's imports being a design decision 14.2's smaller change does not ask for.
- **R261.** An open answered without the walk passes every check the walk's answer passes, branch
  7's confinement under the start directory among them, and a description deleted or replaced
  since the listing is walked for or refused, never answered from the listing: a listing read
  once is a snapshot, and the opens are what branch 7 hardened. The bench times the open of the
  project named on the command line, which needs no walk; a listed project's open, which may
  walk, is untimed, as the developer page says.
- **R262.** The screenshots are compared by CI's `gui-screenshots` job on the pushed commit, never
  by a local run, whose `npm ci` downloads from the registry (R188's reason); a reference that
  moves on purpose is taken from that job's artifact, made in the pinned Playwright image, looked
  at, and committed by the task that moved it. The cost: a reference committed a CI run after
  its change, a red run between (R302).
- **R263.** Where a pin D0 changed with its words was not seen red against the old ones, an
  ablation killing it stands for the red, as R203 has it for page pins.
- **R264.** Branch 9's *Left open* entry on the progress log's rows stays, saying that branch 10's
  D0 filled both: the section is read as what is open.
- **R265.** A structure member's derived range stays the analysis's to refuse: a type plan sets a
  key of a type's entry and never a member's, so no plan makes a member's range infinite, and a
  member naming a changed scalar type is held by that type's own check.
- **R266.** At the maintainer's word of 2026-11-21, no pause at a pull request: once branch 10's
  is open, branch 11 follows at once, stacked on it, and so on, the leave unchanged.
- **R267.** Task 1's judge plans a change that leaves the type entry's own problem as it was, the
  same sentence from `type_problem` before and after, refuses one that brings a problem the entry
  did not carry, naming its key, and plans one that mends it: the judge guards what a change
  writes, the analysis files what the entry carries, and a reader who has only selected a row is
  not to be refused. A type the analysis refuses stays editable in its other keys, its finding on
  screen.
- **R268.** Task 4a's changes to three journeys and to a paragraph of the developer page stand
  beyond the Files list (R231): the journeys test the server whose watch `14:I5` widened, and a
  write that stopped being unseen is the change's own consequence.
- **R269.** Two of `14:I5`'s four cases already held at task 4a's base, by branch 2's fix, and
  their tests stay as regression tests: red first holds of the behaviour the task changes.
- **R270.** What the poll still does not see after task 4a - a record a build writes where the
  search for records had found nothing, and a plugin named as a module and installed since - goes
  to *Left open*, as the module docstring says.
- **R271.** The Windows legs of tasks 4a, 4b and 5, and task 5's screenshots, are proved by CI on
  the pushed commit, each leg run once: a systematic failure of a cross-directory rename or of a
  directory's time on Windows shows in one run. CI has no journey leg on macOS.
- **R272.** `plugin-changed` stays relaxable: the fixed checks are fixed because something went
  unread or cannot be interpreted, which a plugin read and run is not, and a reader who relaxes
  it does so by a `-W` of their own.
- **R273.** A plugin named as a module is not compared, as a module a plugin imports is not: the
  import system resolves it, from its package's other files and its bytecode, so its digest
  would not be of the bytes that ran. The pages say so, and *Left open* records it.
- **R274.** The Compare tab counts `plugin-changed` among the open project's own errors, so its
  verdict is a refusal while a plugin stands changed, the comparison's rules being the old
  plugin's then; SPEC 4.1's sentence says that exception and the restart that ends it. A
  baseline's own changed plugins go to *Left open*.
- **R275.** The gui row of the command reference says that a plugin edited while the server runs
  is reported as `plugin-changed` and takes a restart, and that a plugin's imports and a plugin
  named as a module are not compared: a home task 4b's notes missed, mended before its review.
- **R276.** SPEC 3.11 names the two plugin checks of a fixed severity where it said both, a third
  standing beside them now: a home of the rule (R231), pinned.
- **R277.** The gui row's sentence on the Compare tab's verdict says the exception R274 states
  too, a third home of SPEC 4.1's rule (R231).
- **R278.** No journey, story or Vitest test draws a finding of `plugin-changed`'s shape, a
  plugin's check on the plugin's file leading nowhere: the controller looked at one in the
  running app before task 4b was complete, and it drew as such a finding draws.
- **R279.** The rename's plan and its Apply missing their budgets are recorded as measured,
  written as missed on the developer page and given a *Left open* entry with their profile and
  the first way out: `14:I6`'s own case, a plan in the largest file, meets its second at both
  sizes, and what a rename reaching every component costs is a question of design beyond the
  finding's change. Decision 14.5 read as mending every plan here would be the same work, done
  when a task takes it.
- **R280.** The bench's projects were held in memory, so that no write of an Apply waited for a
  disk; the pages say so, and a disk would only lengthen a miss recorded already.
- **R281.** A plan is held to the second a panel has, being what a panel draws before it offers
  Apply, and `BUDGETS` holds every measure spec §3 gives a figure, so that the bench says met or
  missed of each: what decision 14.5's binding asks of it. The cost: a budget column on three
  older measures.
- **R282.** The reference page's sentence giving an edit and a plan asked while an analysis runs
  as answered within a tenth of a second is task 5's to restate, `14:I6` naming it beside the
  sentence the task restated, and is restated from the bench's runs.
- **R283.** One span over lines whose middle line is unchanged is one hunk, R240's rule, and
  80265bb7's message stands, the final gate running the suite without the line it removed; no
  commit is amended.
- **R284.** The bench is not run again after task 5's first round, the code it times being
  unchanged since its runs but for lines the suite holds equal, and its open never reaching
  `walk_finds`.
- **R285.** `walk_finds` finding a description through a junction, which the walk passes over and
  which only Windows has, goes to a second round of task 5 once 6a has reported, one agent at a
  time: it now asks `is_junction()` beside `is_symlink()`, and the walk leaves a junction out on
  python 3.12 as on 3.13. f3cdad90 to 8677d9d6 stay red on the Windows legs, for the pull request
  to name (R314).
- **R286.** `vocabulary_project` keeps the two families' readings of a file that does not parse,
  by `skims`, its docstring saying both and why: one meaning would change what one family's `add`
  creates or refuses, which task 6's first part, keeping behaviour, may not. *Left open* records
  what it leaves.
- **R287.** Fifty-six test calls change shape for the one reader task 6's first part makes, their
  assertions kept, as an AST comparison shows: two call shapes cannot become one function
  otherwise.
- **R288.** The refusal class is `PlanRefusalError`, as ruff's N818 asks; `source_path` and
  `served_path` say what they return; the guard on private names reached across modules sits
  with the package's other guards; and a page comment naming a renamed function follows it.
- **R289.** 56d3d038 was pushed with task 6a's ten commits under it, unreviewed, so that CI read
  task 5's Windows fix while 6a's review ran: no pull request was open on the branch, and what
  that review found landed as new commits on top.
- **R290.** The plan routes that can answer a change of no lines - a unit's, a type's, and a
  constant's, a section's and a raster's - are pinned to keep a file their edit leaves
  unchanged, behaviour kept, an ablation of `changing` failing each; whether they should answer
  that nothing changes stays out, the type key's case being P19b-13's, the maintainer's.
- **R291.** Every `unwritable` is answered `409`, a disk's refusal to write among them, and a code
  the one mapping does not know is still a `500`, pinned with a code of its own.
- **R292.** A plan is answered `analysing` in place of its own refusal only where it is refused
  `stale`, the waiting edits asked of every file the plan read: asked before a plan that would be
  made, it would change successful answers no entry asks about, so such a plan is made against a
  file still being analysed, as before.
- **R293.** The Files tab's refusal of a first units file names the files that did not load
  apart too, beyond 6b's notes: the same defect, in one more refusal.
- **R294.** The page's own line on what did not load, in the Types and Shared files tabs, tells
  two files of one name apart, in 6b's round: R189 keeps the page's halves of naming unread files
  in branch 10, and the notes had named the server's sentences alone.
- **R295.** A tab tells a file that did not load apart from every file that did not load, as the
  server does, so a folder is shown only where another unread file shares the name, and one file
  has one name on the page and in a refusal.
- **R296.** The Files tab's judge answering `stale` for a file the page's own waiting edit wrote is
  not 6b's: its entry is about a plan whose place an edit moved, and the judge's words are spec
  §5's. It goes to *Left open*.
- **R297.** `POST /api/edit` takes 8 MiB, corrected before task 7's review from the 4 MiB sized on
  task 5's largest body: every shape the project's own generator makes at 100,000 declarations
  fits, the chain shape's 4,725,352 bytes the most at any density, with room for paths of 443
  bytes, and a chain project's rename refused by its own tool is the defect `15:I4` names. The
  body is read only after the token and the origin are checked (R248). The cost: an
  authenticated body of 8 MiB read into memory.
- **R298.** The drain behind a refusal stays at `MAX_BODY`, as R248 has it, so an edit past its
  limit can read as `ddd gui` not answering: *Left open* says so, with `request` refusing such a
  body before it is sent as the way out. No measured plan comes near the limit.
- **R299.** Task 7's drain takes the standard library's `501` and `505` too, the same close
  without a drain, and `15:I4` stands in two commits, a correcting one where amending is not
  allowed.
- **R300.** Decision 3.6's "past about 10,000 counts" stays its words, the maintainer's, "about"
  hedging them and the gui row giving the five-digit figure; the pull request names it.
- **R301.** The changelog's account of a finding's line and column is the last D's (R4), and the
  place is named as the panel's heading names its file, one name per panel, so two files of one
  name that the heading names alike are named alike there too.
- **R302.** Task 8's references are brought from CI's run at 9a's head with 9a's own, and
  committed by 9a's implementer, in a commit of their own naming `16:I8`: one CI run instead of
  two, and no second agent beside 9a's. 2d149ae9 to de0260e0 are red on the screenshots job,
  6c073aea closing the range, for the pull request to name (R314).
- **R303.** The gui row's sentence on what the line above each table counts stands beyond the
  notes, a home of `14:M1`'s rule (R231).
- **R304.** Each file's own counts still count a disagreement on every file it concerns, R253
  keeping `counts` as the rows the window sizes itself by, and `graph_of`'s `index` is
  keyword-only with a default, three tests catching a call that leaves it out.
- **R305.** `14:M9` is read as a missing include named as the file that did not load, as R197 has
  a refusal name the file an include names and not the project description; the notes had
  restated the *Left open* entry's defect.
- **R306.** Task 9b corrects a docstring of `finding_routes.py`, 9c's file, that its change made
  untrue, and makes `lsp/navigation.named_at` public, a private name it reaches across modules
  (R245); SPEC states nothing of it, and `SourceFile.loaded`'s sentence is 9d's.
- **R307.** A type declared twice and a grid of two producing declarations are `14:M8`'s too,
  each a finding whose panel would not list it, and task 9c takes both before its review: the
  Types tab lists the repetition and counts it at both places, and a grid of two producers lists
  the findings at each one's init, its route kept since the router cannot tell one producer from
  two.
- **R308.** Task 9c changes `findings_by_file.py` and its test beyond the list: a repetition is
  tied to its name only by its note, and a pinned test forbids walking every finding. The cost:
  about 4 ms a revision at 100,000 declarations.
- **R309.** Task 9c's round mends a comment of `gui/src/screens/UndoStrip.tsx`, branch 11's file,
  untrue since a misdirected undo stopped asking for an analysis: one line touched a branch early.
- **R310.** `Grid.pointer` is kept, its docstring reworded, a test still asserting it: removing a
  field a test asserts is a behaviour change 9c's round was not asked for.
- **R311.** That every finding leads to a panel that lists it is left unsaid in the contract,
  untrue of the Files tab, whose row only counts findings; the docstrings of `Route.name` and
  `TypeReply.findings` go to *Left open*.
- **R312.** Branch 10's changelog entries follow the code where the last D's brief was loose: a
  plan refused naming its route, the state carrying `failed` and `refused`, which the page does
  not draw yet, and `/api/values` answering `409` for a declared name with no grid, made an item
  for a client. The two lines past 100 columns that earlier branches wrote are left, and
  *Left open* names them.
- **R313.** The final wave takes the whole-branch review's six Minors, each a few lines in a file
  the branch touched: the watch passes over a plugin path the system will not resolve, so that a
  description failing its schema beside one reports that error; `_appeared_since` and
  `keyedFindings` give the reasons they now have; the developer and reference pages record the
  edit asked while an analysis runs as missing its half second; the changelog says the command
  line's project opens wherever it lies; and the session's docstring and the gui row say what a
  `**` at a project's root watches. A NUL in a plugin path of a description that validates goes
  to branch 12, and a root `**`'s cost to the maintainer (*Left open*, branch 10).
- **R314.** As R45 kept one of branch 1's commits that failed a gate, branch 10's middle commits
  that leave one red stay as they are, and the pull request names each: 7a30cf58 on the
  documentation's pins; 213a1e16 to c8b266bf, two journeys racing until cf047cd9; f3cdad90 to
  8677d9d6 on the Windows legs (R285); 257379ac, f53fe9a4, ebcbbf2c, 003c0f56 and 0c3c84a0 on
  `ruff check`; b61d25fa on coverage; and 2d149ae9 to de0260e0 on the screenshots (R302). Every
  Python gate was run at each middle commit of task 6's first part, and of task 9's third up to
  its review; every other middle commit is known green on ruff, its format, mypy and the
  documentation's pins, and on nothing more. A bisect stopping at one needs a skip, and the
  maintainer can squash them at the merge.
- **R315.** The final wave writes branch 10's rulings from R229, its *Left open* entries, and a
  mark on each entry of an earlier branch it closed, as those were marked before; the progress
  log's row for branch 10 is branch 11's D0's, which knows the pull request's number.

## Progress log

| Branch | Pull request | Merged | Notes |
| --- | --- | --- | --- |
| 1, `fix/edit-engine` | #84 | 2026-11-15, into master (`ac0fb9b0`) | Its four Criticals and the edit engine's Importants; the re-review's residuals carried into branch 2's D0 |
| 2, `fix/build-integration` | #85 | 2026-11-15, into its stacked base; reached master through #87 (`7d1ff765`) the same day | `9:C1` and `1:C2`, every stale build of the review, and the module's guards; the re-review's residuals carried into branch 3's D0 |
| 3, `fix/gui-values` | #86 | 2026-11-15, into its stacked base; reached master through #87 (`7d1ff765`) the same day | `3:C1` and `15:C1`, what the page writes when a person types, picks or pastes a value; the re-review's residuals carried into branch 4's D0 |
| 4, `fix/elf-and-addresses` | #88 | 2026-11-17, into master (`287f9d0b`) | Its Critical (`11:C1`) and what the branch covers: what is read from a linked image, and where an address comes from; the re-review's residuals carried into branch 5's D0; task 6a's four Importants, 8b and 6b stay with the maintainer after two safety stops |
| 5, `fix/generated-artefacts` | #89 | 2026-11-17, into its stacked base (`1883c717`); reached master through #91 (`f695ddef`) on 2026-11-18 | Its Critical (`1:C1`) and what the branch covers: what the C and a2l writers produce, and the option that made the C undefined; the re-review's residuals carried into branch 6's D0; branch 2's four *Left open* entries that named its Files list are now the maintainer's, it having taken none of them |
| 6, `fix/comparison-verdicts` | #90 | 2026-11-18, into its stacked base (`8a469220`); reached master through #92 (`921df5dc`) the same day | Its two Criticals (`1:C3`, `7:C1`) and what the branch covers: whether a delivery can replace another, for readers that may be precompiled (decision M1); the re-review's residuals carried into branch 7's D0 |
| 7, `fix/gui-server-hardening` | #93 | 2026-11-18, into master (`2fbd374b`) | Pass 12's findings and `9:M8`, on what `ddd gui`'s server lets an edit change, where it listens, what it prints and how it answers, named by id alone (decision M4); the re-review's residuals carried into branch 8's D0 |
| 8, `fix/release-machinery` | #94 | 2026-11-19, into master (`96900155`) | Pass 20's findings and what branch 8 covers: what a release publishes wrong and the notes it carries (`4:I7`, `4:I8`, `5:I1`, `4:M12`, `20:I2`, `20:I3`, `20:M5`, `20:M4`, `20:M6`, `20:M13` in part, `20:M16`, `20:M2`, `20:M3`, `20:M7`, `20:M11`, `20:M12`, `20:M15`, `20:I4`), named by id alone (decision M4); the re-review's two residuals carried into branch 9's D0 |
| 9, `fix/editor` | #95 | 2026-11-21, into master (`c011143b`) | Pass 10's findings and what branch 9 covers: the language server, `ddd lsp` and the VS Code extension (`10:I1`, `10:I2`, `10:I3`, `10:I4`, `10:I5`, `10:I6`, `10:I13`, `10:I8`, `10:I9`, `10:I10`, `10:I11`, `10:I12`, `10:M1` to `10:M12`, `14:M13`), named by id alone (decision M4); the re-review's residuals carried into branch 10's D0 |

## Self-review

**Coverage.** A script checked this plan against the 456 verdict rows of the review's twelve
verification groups. Every standing finding is named in one of three places: one branch's task,
*Not in any branch*, or both where a task closes it in part.
- **Closed by a task: 439,** each owned by exactly one of 149 tasks. Six of them are closed in part:
  `1:I1`, `1:I4`, `2:I7`, `3:I5`, `7:I3` and `20:M13`. Their other halves are under *Not in any
  branch*.
- **Not in any branch: 15.** Seven are left to the maintainer and eight are deferred by a decision.
- **Refuted: 2.**
- **None is missing, and none is owned by two tasks.** `12:I1` is named twice on purpose: branch 7,
  task 3 makes its measured fix, and its own trigger is the maintainer's to try.

Three tasks carry a decision and no finding id, since the decision came from an open question rather
than a finding: branch 6, task 2; branch 11, task 12; and branch 15, task 11.

**Order.** No task consumes what a later branch produces:
- branch 1, task 8's validation of quick fixes comes before the editor's branch, which relies on it;
- branch 2 changes `cmake/Ddd.cmake` before branch 5 removes `CONST_INPUTS` from it;
- branch 6, task 9's `compare_deliveries` is the one the GUI's Compare tab calls from then on;
- the structural moves of branch 14 come after every fix that edits the modules they move;
- the README is shortened in branch 15, after every branch that adds to it.

**Placeholders.** Each task names its finding ids. The review's section for each, with its
verification, gives the trigger to turn into a test and the change in a sentence. Where the review
left a probe, the task names it.
