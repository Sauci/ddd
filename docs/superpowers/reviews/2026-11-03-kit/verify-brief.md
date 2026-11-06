# Brief shared by every verification of the 2026-11-03 complete review of DDD

You verify the findings of two or three passes of a whole-project review of DDD. Each pass was one
reader working alone, and its findings are candidates until someone who did not find them has
checked them. That is you. Your verdicts go into the review document beside each pass's report, and
the summary ranks what to fix on them. A verdict you did not earn costs more than one you leave open.

A pass's report argues for its findings the way this code argues for itself. Treat its prose, its
grades and its transcripts as claims to test. Expect some candidates to be wrong, overstated or
already guarded somewhere the pass did not look, but do not expect any particular proportion.

## Read first

- `review-brief.md` in this folder. Its environment, its rules and its grades bind you exactly as they
  bound the passes: no root, nothing written in the tree, no subagents, nothing read from
  `C:/git/ac11/ptf`, write early because the session may end, fresh timestamps on copies, long runs in
  the background. Fix nothing.
- The whole report of each pass you verify, `SCRATCH/reports/pass-<N>.md`. Its Issues section is what
  you verify, and its Scope covered says how it worked and what it did not run.
- The candidates blocks at the end of every other `SCRATCH/reports/pass-*.md`, so that you recognise a
  defect filed twice.

Your scratch folder is `SCRATCH/verify-<passes>/`, for instance `SCRATCH/verify-9-10/`. The passes'
folders `SCRATCH/pass-<N>/` hold their probes and transcripts. Read them, and copy what you need into
your own folder, but run nothing from theirs and write nothing into them.

## What to do with each candidate

1. Read the finding in full: its location, its trigger, its evidence, and what it says a document
   promises.
2. Check the location on this tree. If the line is off but the defect is there, correct the location
   and say so.
3. Reproduce it yourself. A pass's transcript tells you what to try. It is not evidence:
   - Run the trigger again and keep your own transcript. A pass's probe project may serve as input
     once you have read it.
   - For a finding about the tests (passes 21 to 23), apply the mutant or the probe test again in a
     copy of your own, and run the tests it names.
   - For a finding about text (a document against the code, a spec sentence, a test that does not
     assert what its name says), read both sides and quote the lines.
   - For a structural finding (a design, a split, a layering, a duplication), the claim to test is
     the consequence it states: a defect it causes, a change it blocks, a rule it lets drift. Show
     that consequence with a measurement of your own, or with the change tried in a copy. That the
     structure exists confirms nothing by itself.
4. Try to refute it before you confirm it. Look for the guard, the test, the caller or the spec
   sentence that would make it a non-issue. Look also for an input on which the claimed effect
   should appear and does not.
5. Give a verdict, a grade and one line of evidence.

Effort follows the grade. Reproduce every Critical and every Important, or say why it could not be
reproduced. Reproduce a Minor when that is cheap, a few minutes; otherwise read it off the line with
care. If you run out of room, stop at a candidate boundary and mark the rest UNVERIFIED. A short list
of honest gaps is worth more than a long list of guesses.

## Verdicts

- **CONFIRMED**: the effect reproduced on the tree as described. For a claim about text, both sides
  were read and quoted, and no reading of them saves it. A finding may be confirmed with corrections,
  such as a narrower trigger, another line or a smaller effect: say which.
- **PLAUSIBLE**: the code reads as the finding says, but the effect was not reproduced. Either it
  needs what this machine lacks (a real CANape, INCA or VS Code, a Linux tool that is not installed,
  root, a CI run, a wildcard network bind), or the run would cost more than it is worth. Say which,
  and what would settle it.
- **REFUTED**: the trigger does not produce the effect on the tree, or the finding misreads the code,
  the spec or the standard. Say what actually happens, with your transcript or the lines.
- **UNVERIFIED**: you did not reach it. Use this only for candidates you did not get to.

A candidate that is the same defect as one filed earlier, by its own pass or by another, still gets
its own verdict. Name the earlier one in the "duplicate of" column. If both are in your group, one
check may serve both; say so. If the later one adds a trigger or an effect, say what it adds.

## Grades

Re-grade each confirmed or plausible candidate by the definitions in `review-brief.md`, on the effect
as it stands after your check. A narrower trigger or a smaller effect may lower the grade; an effect
wider than the finder saw may raise it. For a PLAUSIBLE candidate, grade the effect it would have if
it is real, and say so. Give one line of reason for every change. "By analogy" or "for completeness"
is not a reason. For a Critical, name the wrong output, the lost file or the hole.

A `KNOWN` tag says that a plan left the item open. Check that the plan it names does leave it open.
If the plan does not mention it, drop the tag. If the plan says it was fixed, then either the finding
is a regression (say so) or it is wrong.

## Specific rules

- **Root.** Do not reproduce pass 19 M9's part as root, nor anything else that needs root. For M9, read
  `SCRATCH/pass-19/wsl/writer_root.txt` and the code, and give it PLAUSIBLE or CONFIRMED from the
  lines. Its part as an ordinary user may be reproduced, in a directory of your own.
- **The local server.** Start your own `ddd gui` and your own listeners, on loopback addresses only
  (any address in `127.0.0.0/8`, `::1`, or such an IPv4 address mapped as `::ffff:127.x.y.z`). Never
  bind a wildcard or a non-loopback address. Where a
  finding needs one, read it off the code and the pass's transcript, and say so.
- **The network.** Read-only `gh` queries about this project's own repository are allowed, such as
  `gh api` or `gh run list`. Download nothing: no `pip download`, no `npm pack` of a published version.
  Post nothing, and dispatch no workflow. Where a finding needs a published artefact, use the pass's
  transcript and say so.
- **Documents.** For a finding that says a document promises something, quote the sentence, then run
  what it promises.

## Groups

The verifications run one after another, in this order, each over two or three passes chosen so that
one setup serves the group:

| group | passes | subject |
| --- | --- | --- |
| V1 | 1, 2 | the concept; the split of the Python code |
| V2 | 3, 4 | the split of the UI and the backend; what the documentation misses |
| V3 | 5, 6 | SPEC.md on its own; the file formats |
| V4 | 7, 8 | checks and comparison; generated artefacts and addresses |
| V5 | 9, 10 | the tool interface and CMake; editor integration |
| V6 | 11, 12 | the toolbox and the ELF reader; the GUI server's security |
| V7 | 13, 14 | the GUI's edit engine; the GUI's API |
| V8 | 15, 16 | the page's logic; the screens |
| V9 | 17, 18, 19 | code review of the core and of the periphery |
| V10 | 20, 21 | the repository and remaining documents; the core's test suite |
| V11 | 22, 23 | the test suites of the periphery, the server and the page |

## Report

Write `SCRATCH/reports/verify-<N>.md` for each pass `<N>` you verify, one file per pass, because the
assembler appends it to that pass's report. Each file starts:

```
### Verification of pass <N>

By a reader who did not find these, on <date>, on the tree at master 2b4bae6c. Scratch:
`SCRATCH/verify-<passes>/`. <counts per verdict>. <the grade changes, in one line>.
```

Then comes a table with one row per candidate, in the order of the pass's candidates block:

```
| id | verdict | grade (was -> now) | duplicate of | evidence | note |
```

`evidence` is the path of your transcript under your scratch folder, or `read off <path:line>`.

After the table, write one short paragraph for each of these, in the same order: every REFUTED, every
PLAUSIBLE, every grade change, and every confirmation with corrections. Each says what you ran, what
you saw and why.

End each file with this block, one line per candidate, exactly:

```verdicts
<N>|<id>|<verdict>|<grade before>|<grade after>|<duplicate of, as P:ID, or ->|<one-line note>
```

Use `-` as the grade after for a REFUTED or UNVERIFIED candidate.

Your final message back, not the files, gives:
- per pass, the counts per verdict;
- one line each for every REFUTED Critical or Important, and for every change to or from Critical;
- anything that blocked you.

Keep it under 250 words.
