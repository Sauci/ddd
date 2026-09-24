# Brief shared by every pass of the 2026-09-24 complete review of DDD

You are one pass of a whole-project review of DDD (a data-dictionary tool: JSON descriptions ->
consistency checks, C code, A2L, a dictionary; a CLI, a CMake module, a language server, a VS Code
extension, plugins, and since 0.10.0 a local web GUI `ddd gui`). Release 0.11.0 has just been
merged; what this review finds will be fixed in 0.11.1. The maintainer asked for a **full** review.

## Where things are

- Review tree (read-only for you except your scratch folder): `C:/git/ac11/ddd/.claude/worktrees/complete-review`,
  branch `review/complete-review-2026-09-24`, at master `faee81e` (merge of PR #60, 0.11.0).
  Line numbers you cite are on this tree.
- Its venv: `.venv/Scripts/python.exe` (editable install of this tree; `ddd.exe` in the same folder).
- Scratch folder: `SCRATCH = C:/Users/lmbsog0/AppData/Local/Temp/claude/C--git-ac11-ddd/80311993-14bd-439a-bc58-d7aa49363ad3/scratchpad`.
  Put every probe project, script and transcript under `SCRATCH/pass-<N>/`. Never write in the
  repository. Never commit, never move HEAD, never touch other branches or worktrees.
- The previous whole review: `SCRATCH/review-2026-09-15.md` (5649 lines, 219 findings, same
  structure as yours). Its fixes landed in nine branches on 2026-09-16; the fix plan with the
  decisions taken and "Left open by the implementers" is `docs/superpowers/plans/2026-09-16-review-fixes.md`.
- Everything since then (web GUI milestones, record layouts / `point_counts`, dictionary format 9,
  0.11.0) has specs and plans in `docs/superpowers/specs/` and `docs/superpowers/plans/`. Plans have
  "Left open" sections: those are known and should be listed as known, not rediscovered as new.
- Earlier passes' reports of this review, if any: `SCRATCH/reports/pass-*.md`. Read the
  candidates blocks of the passes before yours so you do not repeat their findings; if you meet one
  again, cite it ("see pass 3 I2") rather than re-filing it.

## Environment (Windows 11, run from Git Bash)

```bash
cd /c/git/ac11/ddd/.claude/worktrees/complete-review
export PATH="$PWD/.venv/Scripts:/c/Users/lmbsog0/AppData/Local/Programs/CLion/bin/mingw/bin:/c/Program Files/nodejs:$PATH"
```

- Run pytest from Git Bash only (PowerShell makes `bash` resolve to WSL and the transcript tests fail).
- One test always fails here: `tests/test_lsp.py::TestSymlinkedWorkspace::...` (Windows symlink
  privilege). Not a finding.
- MinGW gcc is on the PATH above for compiling generated C. Docker cannot run here.
- Node 24 / npm are on the PATH above; `gui/node_modules` is installed. Playwright runs with
  `PLAYWRIGHT_CHANNEL=msedge` and `DDD_PYTHON=$PWD/.venv/Scripts/python.exe`.
- Sphinx plantuml: `JAVA=C:/CAD/Tools/MATLAB/R2022b_x64/sys/java/jre/win64/jre/bin/java.exe`,
  `PLANTUML_JAR=C:/Users/lmbsog0/.vscode/extensions/jebbs.plantuml-2.18.1/plantuml.jar`.
- Do not use `ptf` (another repository that vendors ddd) for anything.
- Do not spawn subagents. Do all of your pass yourself.

## How to work

- Read your scope **in full**, with line numbers. Then probe: write small throwaway projects and
  run the real tool on them. A finding you reproduced beats one you inferred. Keep transcripts.
- Report only real defects: wrong behaviour, a contradiction between documents and code, a
  document that promises what the tool does not do, a hole in a guard, a test that does not pin
  what it claims, a security hole, a maintainability problem that will cause a defect. Not style
  preferences, not "could add a comment".
- Every finding: a location (`path:line` on this tree), what is wrong, a concrete trigger
  (input -> observed output vs expected), and how you established it (reproduced / read off the
  line). Say which document or spec sentence is contradicted, if any.
- Grades: **Critical** - wrong output an integrator would ship (wrong C/A2L/dictionary, a check
  that silently passes a broken project, data loss in a file the GUI or an edit writes, a security
  hole in the local server). **Important** - wrong behaviour on a plausible project or use, a
  documented promise broken, a guard missing where a user will hit it. **Minor** - everything
  real but rarer or cosmetic in effect (a wrong sentence, an untested branch, an edge case).
- Check the 2026-09-15 findings in your area: for each, FIXED (cite the commit or line),
  STILL OPEN, or REGRESSED. Only list those that are not plainly fixed in a short table; a
  regressed or still-open one that matters is also a finding of yours.
- Do not fix anything.

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
### Assessment           (one paragraph)
```

Number findings `C1`, `I1`, `M1`... within your pass. Each finding is a bullet starting with a
bold one-line title, then the location, trigger, evidence.

End the file with a machine-readable block, one line per finding, exactly:

```candidates
<N>|C1|path:line|one-line title
<N>|I1|path:line|one-line title
...
```

Your final message back (not the file) is: the counts per grade, the three most serious findings
in one line each, and anything that blocked you. Keep it under 250 words.
