# Brief shared by every pass of the 2026-11-03 complete review of DDD

You are one pass of a whole-project review of DDD: a data-dictionary tool for the global variables
of component based embedded software. JSON descriptions -> consistency checks, C code, A2L, a
dictionary; a CLI, a CMake module, a language server, a VS Code extension, plugins, a toolbox, and a
local web GUI (`ddd gui`). The maintainer asked for a **complete, honest review** of the master
branch: is the concept sound, is the code split cleanly (UI / backend / ...), does the documentation
miss anything, and does it all work. "We made quite some changes since last review, so take your
time."

## Where things are

- Review tree (read-only for you except your scratch folder):
  `C:/git/ac11/ddd/.claude/worktrees/complete-review`, branch `review/complete-review-2026-11-03`,
  whose code is master `2b4bae6c` (merge of PR #83). Line numbers you cite are on this tree. Only
  `docs/superpowers/reviews/` differs from master, and it is not under review.
- Its venv: `.venv/Scripts/python.exe` (editable install of this tree; `ddd.exe` in the same folder).
  The GUI's pages are already built into `src/ddd/gui/static/` (git-ignored) and `gui/node_modules`
  is installed.
- Scratch folder: `SCRATCH = C:/Users/lmbsog0/AppData/Local/Temp/claude/C--git-ac11-ddd/8681cf0d-d41d-4120-88ca-b1b2c3615be8/scratchpad`.
  Put every probe project, script and transcript under `SCRATCH/pass-<N>/`. Never write in the
  repository, not even a build output (redirect `--basetemp`, `-o`, `outDir`, coverage files and
  the like to your scratch folder; a stray file in the tree is a defect of yours). Never commit,
  never move HEAD, never touch other branches or worktrees.
- **Never run anything as root or administrator, WSL included (no `wsl -u root`, no `sudo`), and never
  name a system path as a target.** A probe writes only into a directory it made itself, under your
  scratch folder or a temp folder of its own, and removes nothing it did not make. Pass 19 ran a probe
  as root in WSL and it replaced that instance's real `/dev/null`. If a finding needs root to
  reproduce, read it off the line and say so.
- What the last whole review found: `SCRATCH/review-2026-09-15.md` (5649 lines, 219 findings; its
  fixes landed on 2026-09-16 and their plan, with the decisions taken and "Left open by the
  implementers", is `docs/superpowers/plans/2026-09-16-review-fixes.md`). A later review was started
  on 2026-09-24 and stopped after its pass on SPEC.md: `SCRATCH/pass-1-2026-09-24.md`.
- Everything since has specs and plans in `docs/superpowers/specs/` and `docs/superpowers/plans/`.
  Plans have "Left open" or "What was left open" sections. Read them for your area: an item there is
  **known**. Do not rediscover it as if it were new, but do not bury it either: if it is still open
  and it matters, list it as a finding tagged `KNOWN` with the plan that left it, graded as you would
  grade it yourself.
- Earlier passes' reports of this review, if any: `SCRATCH/reports/pass-*.md`. Read the candidates
  blocks of the passes before yours so you do not repeat their findings; if you meet one again, cite
  it ("see pass 3 I2") rather than re-filing it, and add what your angle adds.

## Environment (Windows 11, run from Git Bash)

```bash
cd /c/git/ac11/ddd/.claude/worktrees/complete-review
export PATH="$PWD/.venv/Scripts:/c/Users/lmbsog0/AppData/Local/Programs/CLion/bin/mingw/bin:/c/Program Files/nodejs:$PATH"
```

- Run pytest from Git Bash only (under PowerShell `bash` resolves to WSL and the transcript tests
  fail). A subset: `python -m pytest --no-cov -p no:cacheprovider --basetemp="$SCRATCH/pass-<N>/tmp" tests/test_x.py`.
- One test always fails here: `tests/test_lsp.py::TestSymlinkedWorkspace::...` (Windows symlink
  privilege). Not a finding.
- MinGW gcc 15.2 is on the PATH above for compiling generated C. Docker cannot run here.
- Node 24 / npm are on the PATH above. Playwright runs with `PLAYWRIGHT_CHANNEL=msedge` and
  `DDD_PYTHON=$PWD/.venv/Scripts/python.exe`.
- Sphinx plantuml: `JAVA=C:/CAD/Tools/MATLAB/R2022b_x64/sys/java/jre/win64/jre/bin/java.exe`,
  `PLANTUML_JAR=C:/Users/lmbsog0/.vscode/extensions/jebbs.plantuml-2.18.1/plantuml.jar`.
- The ASAP2 standards are git-ignored PDFs in the main checkout:
  `C:/git/ac11/ddd/docs/superpowers/ASAP2-1.51.pdf` and `ASAP2-1.6.1.pdf`.
- **Do not read or cite `C:/git/ac11/ptf`** (another repository that vendors ddd); the maintainer
  has ruled it out as a source for this work.
- **Do not spawn subagents.** Do all of your pass yourself. Only one agent runs at a time on this
  project, because of an account rate limit.
- A long command: keep it under 10 minutes or run it in the background and read its output later.

## How to work

- Read your scope **in full**, with line numbers. Large files in chunks, but all of them. If you run
  out of room before finishing, say exactly what you did not read; a partial pass that says so is
  worth more than a complete-looking one that does not.
- Then probe: write small throwaway projects and run the real tool on them. A finding you reproduced
  beats one you inferred. Keep transcripts in your scratch folder.
- **This code argues for itself.** Its docstrings, comments, specs and plans are long and persuasive,
  and it has 100 % coverage and a very large test suite. None of that is evidence of soundness. Treat
  every "cannot drift", "cannot disagree", "by construction", "the same rule", "never" as a claim to
  test, not as a fact to repeat. Coverage says a line ran, not that it is right.
- Be honest in both directions. Say plainly what is wrong, including the uncomfortable and the
  structural. Say plainly what is good, with evidence. Do not inflate a grade to look thorough, and
  do not soften one to be polite. If something looks fine, say so and move on: an empty section is an
  acceptable result, a padded one is not.
- Report only real defects: wrong behaviour, a contradiction between documents and code, a document
  that promises what the tool does not do, a hole in a guard, a test that does not pin what it
  claims, a security hole, a design or structure that will cause a defect or block a likely change.
  Not style preferences, not "could add a comment".
- Every finding: a location (`path:line` on this tree), what is wrong, a concrete trigger (input ->
  observed output vs expected), and how you established it (`reproduced`, with the transcript's path,
  or `read off the line`). Name the document or spec sentence it contradicts, if any.
- Grades:
  - **Critical**: wrong output an integrator would ship (wrong C, A2L or dictionary; a check that
    silently passes a broken project), loss or corruption of a file the GUI or an edit writes, a
    security hole in the local server, or a design flaw that produces one of those by construction.
  - **Important**: wrong behaviour on a plausible project or use, a documented promise broken, a
    guard missing where a user will hit it, a structure that is already causing defects or
    duplication or that stands in the way of an obvious next change, a gap in the documentation that
    leaves a real user stuck.
  - **Minor**: everything real but rarer or cosmetic in effect.
- Check the 2026-09-15 findings in your area: for each, FIXED (cite the line), STILL OPEN or
  REGRESSED. In your report list only those that are not plainly fixed, in a short table; a regressed
  or still-open one that matters is also a finding of yours.
- Do not fix anything. Where a fix is not obvious, say in one or two lines what you would do.

## Report

Write `SCRATCH/reports/pass-<N>.md` with exactly these sections:

```
## Pass <N>: <subject>

### Scope covered        (what you read, with line ranges; what you ran; what you did not cover)
### Strengths            (short; what holds, with evidence)
### Issues
#### Critical
#### Important
#### Minor
### Status of the 2026-09-15 findings in this area
### Open questions       (decisions only the maintainer can take; say what each answer changes)
### Test gaps
### Assessment           (one paragraph, your plain verdict)
```

Number findings `C1`, `I1`, `M1`... within your pass. Each finding is a bullet starting with a bold
one-line title, then the location, the trigger, the evidence, and for a structural finding its
consequence and the change you would make with a rough size (S: hours, M: days, L: weeks).

End the file with a machine-readable block, one line per finding, exactly:

```candidates
<N>|C1|path:line|one-line title
<N>|I1|path:line|one-line title
...
```

Your final message back (not the file) is: the counts per grade, the three most serious findings in
one line each, and anything that blocked you. Keep it under 250 words.
