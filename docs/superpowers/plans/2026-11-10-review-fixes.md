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

- [ ] **Task 1 (`9:C1`, Critical; decision 9.1):** the per-component headers are declared as
      `BYPRODUCTS`, with their names read at configure. `ddd_add_component` reads `component.name`,
      and `PROJECT` asks the tool. A renamed component needs a reconfigure, and the page says so.
      A story test, run under Ninja and, after task 7, under Make (Review focus 5):
      - change a variable's datatype in both descriptions and build once: the reader is recompiled,
        and the image reads the new value;
      - a second build has nothing to do;
      - an edit that leaves `Logger.h` alone recompiles `sensor.c` and not `logger.c`.
- [ ] **Task 2 (`1:C2`, `1:I6`, Critical):** the `ADDRESS_MAP` flow gets the architecture
      `ADDRESSES_FROM_IMAGE` already has.
      - The generation before the link leaves the a2l out.
      - `<stem>_ddd_a2l` depends on the image and the map, and runs `generate a2l --address-map`.
      - An a2l written with no address source says so in a comment.

      Tests, under `STRICT`:
      - an array grown and built once gives an a2l holding this link's addresses;
      - an object added still builds;
      - a clean checkout's first build is said for what it is.
- [ ] **Task 3 (`9:I1`, `19:I2`, `19:M8`; decision 9.4):** `ddd sources` lists every `.py` the
      project names, loaded or not, and every file of a package plugin.
      - `load_workspace` moves inside `_analyze`'s guarded block.
      - `sources` and `artefacts` report `plugin-invalid` beside their listing instead of exiting 2.
      - The module prints `ddd sources`' stderr as `message(WARNING)`, and its fallback keeps the
        project file a configure dependency.

      Tests: task 1's story for a plugin that stops importing, and for one whose model raises: the
      next build re-runs. `check --format json` still prints its document when a plugin model raises.
- [ ] **Task 4 (`9:I2`):** each wildcard include is globbed with `CONFIGURE_DEPENDS`. The source list
      is written into the build tree only when it differs, as a dependency of the generation. Test:
      task 1's story for a file a pattern starts, then stops, matching.
- [ ] **Task 5 (`9:I3`; decision 9.2):** `ddd_add_component` refuses a file whose top-level key is
      `project`, naming `PROJECT`. Test: the configure error and its sentence.
- [ ] **Task 6 (`9:I4`, `9:I5`):**
      - The empty-keyword guard walks `ARGV<n>`, so `ADDRESS_MAP "${UNSET}"` and
        `PROJECT "${UNSET}"` are refused at configure.
      - `execute_process` reads `ddd sources` with `ENCODING UTF-8`.

      Tests: the two configure errors, and (Review focus 2) a `PROJECT` build under a non-ASCII
      directory name on the windows legs.
- [ ] **Task 7 (`9:M4`, `9:M5`, `9:M6`, `9:M7`; decision 9.3):**
      - The release handshake is keyed on the tool's version as well as its path.
      - The dead fallback goes: the project file has to exist and parse at configure, and the page
        says so.
      - Makefile generators get a stamp output, and `tests/test_cmake.py` gets a Makefile cell.
      - The module's six edges are handled: a bracket in a path, a deleted output directory, a C++
        project, a helper in a subdirectory, a removed template's output, and a vocabulary generated
        later.
- [ ] **Task 8 (`24:I1`; decision 24.1):** `<target>.ddd` applies the default policy. The build page
      says so: the "cannot drift apart" sentence goes, and a supplier is told that their check is not
      the build's.
- [ ] **Task 9 (`9:M14`):** the small untrue or missing sentences of the command page and the build
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

- [ ] **Task 1 (`3:C1`, Critical; decision M3):**
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
- [ ] **Task 2 (`15:C1`, Critical):** `chosen`, `typed` and `edited` are held as `{key, value}`, and
      ignored while `key !== selected`. Test: the probe `p15-C1`.
- [ ] **Task 3 (`16:C1`, lowered to Important):** a cell's `onKeyDown` keeps one-character keys from
      the table's type-to-find. Test: the probe `p16-C1`, typing 20, 5.1 and a 16x16 map's cell key
      by key.
- [ ] **Task 4 (`15:I1`, `24:M2`; decisions 15.3 and 24.2):** while a chooser's text is not the
      settled value's label, Apply is withheld. A scroll that closes the list keeps what was typed.
      Tests: the probes `p15-I1` and `p15-I1b`, and a journey with a wheel notch between `km` and
      `/h`.
- [ ] **Task 5 (`16:I1`, `16:I2`, `16:I3`; decision 16.2):**
      - A value cell is sized to its text.
      - The offer stays in view while a cell is open.
      - Several typed cells are planned as one table plan.

      Tests: the probe `p16-I2`, and a journey typing three cells and applying once.
- [ ] **Task 6 (`16:I4`; decision M8):** a scalar's `init` is edited as a one-cell grid, and the
      variable's panel gets a description field. The panel says that renaming and scope are edited in
      the editor. Tests: demo `ParameterA` shows 3200 and its description, and each is written by a
      plan, in pytest and in a journey.
- [ ] **Task 7 (`3:M4`, `3:M5`, `15:M4`, `15:M5`, `15:M6`, `15:M7`, `15:M9`, `15:M10`, `15:M13`):**
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
- [ ] **Task 8 (`15:M8`):** the plot becomes linear in the cells. Test: Vitest counting the plot's
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
  - Private vulnerability reporting, which is still off.
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
  with the plans it measures against their budgets.
- **`ddd id --assign` syncs the files it stamps one after another** (task 6, `2:I6`): it hands
  `apply_changes` one file at a time, so nothing batches the syncs, as an edit's are batched.
  Measured on the Linux development PC's NVMe disk (ext4) over the generated project of 35,000
  declarations with every output lacking an id - 1,166 component files - a first run took 0.70 s
  before this branch and 10.7 s after it, the median of three runs each; a second run, which
  stamps nothing, about 0.6 s both. No branch owns `identity.py`.
- **The variable's key chooser still offers another component's locals** (task 9, `13:I6`): for an
  `axis` or an `input` it lists a name another component declares `local`, which `declarable`
  leaves out, and choosing it writes a `local-conflict`, the harm `13:I6` was graded for. Branch
  10 lists `variable_keys.py`, where the chooser's offer is made.
- **A description given with `PROJECT` whose record sits beside it reads as generated** (task 4,
  `1:C4`; R2): `ddd_generate()` writes `ddd-build.json` into `OUTPUT_DIRECTORY` with or without
  `PROJECT`, and where that is the description's own directory the record names a hand-written
  project from beside it: every change of its files is refused as `generated`, in a sentence
  saying the build writes it. Nothing is written wrongly, and the CLI and developer pages state the
  limit. Branch 2, which owns `cmake/Ddd.cmake`, can say precisely which description the build
  writes, by a key it adds to the description it collects or to the record: an addition to the
  format, which its changelog would then state.
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
  chooses it, and the contract.
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
  `object_values.py` and `gui/api.py`.
- **A settled value whose declaration moved is refused `unreadable`** (task 3): where the other
  plans say `stale`, as the changelog states; the page draws the two alike. No branch owns
  `variables.py`.
- **Fingerprints across several build records** (task 3): a file several runs read takes the
  fingerprint of the first run that read it, not the index's run, so a file saved and put back
  between two runs can carry the fingerprint of bytes other than the index's; several records
  only, and rare. Branch 7 and branch 10 list `gui/session.py`.
- **A generated project left unrecognised** (task 4): a record that does not parse is read as no
  record, and `ddd build-info --output` writes one unstaged, so a write that dies can leave it
  half written; and a build configured at another path, a container's mount, names a project the
  path opened does not match. Either can leave a generated description editable. An empty
  `CMAKE_HOME_DIRECTORY` reads as the working directory besides: the description's own directory
  is refused all the same, and only how much of the build tree around it is refused changes.
  Branch 7 and branch 10 list `gui/session.py`, branch 12 `cli.py`.
- **An existing description added to a generated project** (task 4): is refused without the
  `ddd_add_component()` line a new file is offered with. Branch 10 lists `gui/*.py`.
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
  `lsp/units.py`.
- **A file saved half way after the analysis** (task 7): a file typed into after the analysis and
  then saved half way is unseen by a plan, which checks the fingerprints of the files it writes
  alone. Branch 10 lists `gui/*.py`.
- **An input stays answered while a file does not load** (task 7, R15): a local of the same name in
  the unread file is a `local-conflict` once it loads. Branch 10 lists `declaration_plans.py`.
- **A hidden local's name typed into the add panel** (task 9): is told the project declares it
  already, not whose local it is. Branch 10 lists `declaration_plans.py`.
- **The would-not-load sentence** (task 8): it reads "with that dimensions", and a removal's names
  a value it does not write; the panel keys each sentence by its words, so two alike, from two
  files of one name, share a key. No branch owns `variables.py`; branch 11 lists `components/*`.
- **The editor's preferred fix** (task 8): for a consumer's mismatch the editor now prefers "Apply
  this datatype to 1 other declaration", the first fix left once the others are withheld. Branch 9
  lists `lsp/*.py`.
- **What the panel's check does not ask** (task 8): a shape mixing a constant with numbers the
  analysis refuses whatever the constant is planned without its sentence, and a type's key is read
  at the index's pointer with no name checked (`_fixed_by`); `type_plans.set_key` is branch 10,
  task 1's. Branch 13 lists `models/*`, branch 10 `lsp/edits.py`.
- **A pattern character typed through a link** (task 11): a relative entry naming a file with a
  pattern character, typed through a link the kernel cannot follow `..` after, is checked as the
  file but read by `expand_include` as a pattern matching nothing. Branch 13 lists `loading.py`.
- **The documents' corners** (tasks 4 and 8): no page says that the build tree is the output
  directory where the cache cannot be read, and the three passages on what the panel's check does
  not ask list different sets. Branch 15 owns `docs/*.rst`.
- **A misdirected undo, and a print that fails** (task 12): a second window's undo of an entry no
  longer on top is refused `stale` and asks for a whole analysis; and the line printed for an
  analysis that failed on a refusing request raises where stderr cannot be written, replacing the
  `409` with a `500`, which the analyser's own thread suppresses. Branch 7 and branch 10 list
  `gui/session.py`.
- **One case the threat model sets aside** stays as `docs/gui_security.rst` draws that model. No
  branch owns it.

## Rulings taken

Every departure from a task's text, with its reason, numbered `R1`, `R2`, and so on.

**Branch 1:**
- **R1.** Task 1 gives `editing.py` its stage of its own and leaves `identity.py`'s writer to task
  6, which routes `ddd id --assign` through `apply_changes`: `13:C2`'s `ddd id` half closes there,
  rather than being written in task 1 and rewritten three tasks later.
- **R2.** Task 4 recognises a generated project by the build record naming it, and could have
  marked it from `cmake/Ddd.cmake` where the record did not suffice; it sufficed for the projects
  the task names, so the module is unchanged. It does not suffice for a description given with
  `PROJECT` whose record sits beside it, which is taken for generated (*Left open*, branch 2).
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

## Progress log

| Branch | Pull request | Merged | Notes |
| --- | --- | --- | --- |
| 1, `fix/edit-engine` | #84 | not merged | Its four Criticals and the edit engine's Importants; the re-review's residuals carried into branch 2's D0 |

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
