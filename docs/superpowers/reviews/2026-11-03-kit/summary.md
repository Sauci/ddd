## Summary

Twenty-five passes read the project, each by one reader working alone: 23 by area (parts A to D of
`2026-11-03-kit/passes.md`) and two sweeps for what fell between them (part E). A second reader who
had not found them then checked every one of their 456 findings, in twelve verification groups, by
reproducing it on the tree wherever it could be run. Of the 456, 445 were confirmed, 9 are left
plausible and 2 were refuted, and 11 changed grade: 9 down, 2 up. What stands is **12 Critical,
131 Important and 311 Minor findings**.

This summary answers the maintainer's four questions in order, says what to fix first, and lists the
decisions only the maintainer can take. A finding is named by its pass and its id: `13:C1` is pass 13's
first Critical. The reports follow, each with its verification beside it.

### The short answers

- **Is the concept sound?** Yes, at its core. Declaring interfaces as data, resolving one owner per
  variable, generating one dictionary and rendering everything from it is a good idea, well executed,
  and rigorous on what it checks. It overclaims at its edges, where it meets the compiler, the linker,
  the build, and the consumers it does not rebuild. Pass 1's four Criticals sit there, each with a
  small fix, and none needs the concept changed.
- **Is the code split cleanly?** The core, the file formats and the backends are: measured, there is
  no cycle among top-level imports, and a third backend would need nothing changed. The edit layer
  that the editor and the GUI grew, about 9,000 lines, has no home of its own, and the page computes a
  few things the server should, one of them Critical. Both have mostly mechanical fixes, which the
  100 % coverage makes safe to make.
- **Does the documentation miss something?** As a reference, almost nothing: 448 of 505 surfaces are
  documented where a user looks, every documented command line runs, and the tool is quoted word for
  word. As a guide, a good deal. There is no guide to `ddd gui`, no path for adopting DDD in a project
  that already has code, and nothing between the generated a2l and a connected tool. And facts told in
  up to eight places have started to contradict each other.
- **Does it work?** The generator does. Pass 8 got no wrong address, size, value, conversion or
  qualifier out of the C and a2l writers across everything it tried, and the command line did not crash
  in 57,914 runs. What fails is around it:
  - a Ninja build that ships objects compiled against the old header (9:C1);
  - an edit engine that can rewrite the wrong entry, overwrite a save or delete a description
    (13:C1, 13:C2, 13:I1);
  - a page that writes values the user did not type (3:C1, 15:C1);
  - an ELF reader that gets signed enums wrong (11:C1);
  - a delivery comparison that passes a moved layout (1:C3, 7:C1).

  The suites hold 100 % coverage, and none of the twelve Criticals fails a test. Each Critical needs a
  situation the suites never set up: a second writer, a build after an edit, a consumer compiled from
  the generated C, or a value at the edge of its type.

### 1. Is the concept sound?

Pass 1, with passes 7, 8 and 9 for the comparison, the artefacts and the build.

| principle | verdict |
| --- | --- |
| Every component declares its data interface explicitly | Holds with a caveat: descriptions are compared with descriptions only, and several ordinary interfaces cannot be stated (1:I2, 1:I13). |
| Exactly one component owns each variable | Holds, but a component that declares `input` and writes anyway is invisible by default: "nobody can write a foreign variable" is false by default (1:I1). |
| Access rules are enforced by what is generated | Does not hold as stated. The one enforcing option, `--const-inputs`, is undefined behaviour that gcc miscompiles from `-Og` up, with no warning under the CI's `-Werror` set (1:C1). |
| DDD owns the data, the project owns the presentation | Holds for the C. Not for the a2l, which has no extension point (1:I8). |
| Everything passes through the dictionary | Holds. |

**`check` and `compare`.** Both ask the right question.
- `check` is sound on descriptions. Pass 7 found the 72 checks agree with the documents, and 385 of
  387 mutated projects that pass `check` compile.
- `compare` is not sound on layout. It reasons about leaves, so a moved layout passes as `info` or as
  nothing (1:C3, 7:C1). It also ignores vocabularies, and grades a measurement's limits backwards
  (1:I3, 1:I4).

**Images and the build.** The image and project split and reproducibility hold. But the
`ADDRESS_MAP` flow ships the previous link's addresses with no finding, even under `STRICT` (1:C2).

**The editor and the GUI.** Both follow from the files being the artefact, except that the GUI treats
a file the build generated as one the user wrote (1:C4).

**Open decisions.** The concept leaves two decisions open: whether a consumer restates, shares or pins
a producer's definition (pass 1, question 3), and the comparison's cost model (pass 7, question 1).
The most valuable next feature is holding the linked image to the description (1:I12). That turns
"cannot disagree" from a claim about the generator into a fact about the build.

### 2. Is the code split cleanly?

Passes 2 and 3, measured again by pass 24.

**The Python package.**
- **What is split cleanly.** The core is split cleanly, and the transport sits at the edge. `models`,
  `ir`, `backends` and `plugins` are the strongest part of the design, and nothing below the GUI
  imports the GUI. Pass 24 measured 87 modules and 363 import edges. It found no cycle among top-level
  imports, and the layer table is true of the modules it names.
- **What is not.** The edit layer that the editor and the GUI grew is not split. About 9,000 lines
  have no home: part sits in `ddd.lsp`, part at the package root in modules named after tabs, and part
  in `gui/api.py` and `gui/session.py` (2:I1, 2:I3, 2:I8).
  - Importing `ddd.lsp.ranges` loads the language server, and two deferred imports hide a 12-module
    cycle (2:I2).
  - The layer table leaves out 39 % of the code (2:I5).
  - The import guards hold eight rules, and all 33 realistic violations tried pass them (2:I4).
- **What it has cost.** Rules held twice have already diverged: `ddd id --assign` is a second edit
  engine (2:I6), and "load, gate, analyse" exists six times (2:I7).
- **The fix.** Pass 2 drew the target: a `ddd/editing/` package beneath both clients, reached by
  behaviour-preserving moves. The first five moves take a day or two and stand on their own: a layer
  test as a ratchet, an empty `lsp/__init__.py`, and a few modules moved to the leaves. The whole is
  two to three weeks, mostly mechanical.

**The UI and the backend.** These are split cleanly, for the most part (pass 3).
- **What holds.** The server owns plans, diffs and the vocabularies' judgement, the wire's shapes are
  generated, and no refusal text is matched.
- **The leaks.** They are where the page computes a number instead of passing text, reads a file
  instead of asking, or is trusted because the server does not check:
  - 64-bit integers are held as doubles and written changed without a word (3:C1);
  - `settle` and `type-plan` accept any value (3:I1);
  - the component table reads the raw file in a `.tsx` (3:I3).
- **The fix.** The boundary pass 3 proposes is that text crosses the line and numbers do not, and the
  page never computes a value that ends up in a file. Its first four moves take three or four days.
- **Inside the page.** The views are clean. The screens carry the decisions (3:I7), and that is where
  pass 15 found the page's Critical (15:C1).

**Rules written twice.** Pass 24 counted every rule the code holds in more than one place.
- **Where they agree.** Where two sides share one definition, they agree: one dictionary writer, one
  name grammar, one record discovery, positions in UTF-16 both ways, and a page that echoes the
  server's plans.
- **Where they disagree.** Disagreements come where a rule was written twice, and each is already
  filed. Two examples:
  - the raster rename: the GUI's copy escapes a quote, while the language server's writes it raw
    (10:I9);
  - stage-and-rename, which exists three times with different protections (2:I6, 13:C2, 19:M1).
- **The other side of one definition.** A defect in a rule held once reaches every caller. The GUI's
  constant rename asks the language server's `rename_sites`, so it inherits 10:I10.

### 3. Does the documentation miss something?

Pass 4, with pass 20 for the remaining documents and pass 25's inventory.

**The reference.** It is complete, and tests keep it true. Pass 25 listed 505 surfaces: commands,
options, checks, keys, outputs, CMake keywords, editor features, plugin hooks, GUI actions,
environment variables and exit codes. Of these, 448 are documented where a user looks.
- All 803 documented command lines are ones the tool accepts.
- All 136 sentences quoted from the tool appear in it word for word.
- Every check has one severity everywhere.

**What is missing.** It is the "how", and the newest part of the tool. Pass 4 ranked the gaps by how
many readers they stop:

1. A guide to `ddd gui` (4:I1). Its one account is a 3,960-word table cell, and 34 of its 66 surfaces
   are documented nowhere, or only in the changelog or design records, or only in part, or are
   contradicted by the page.
2. How a project that already has code adopts DDD (4:I2).
3. How to get from the generated a2l to a connected tool (4:I3).
4. Windows in the tutorial: `ddd id --assign components/*.ddd.json` fails there (4:I4).
5. How the GUI is put together, for a contributor (4:I5), and a contributor's set-up and definition
   of done (4:I6).
6. Honest release notes: the 0.11.0 section lists four features the tag does not have (4:I7).
7. One home per fact (4:I10). The same facts are written in up to eight places, the "short" README is
   9,762 words, and the copies have started to part. Pass 25 met four more such copies.

**SPEC.md.** It calls itself the authoritative contract, yet gives `ddd gui` and the edit engine two
clauses (4:I9) and states the wrong dictionary format (5:I1, 4:M12).

**Claims stronger than the code.** Several sentences claim more than the code does:
- that `const volatile` moves an object out of `.rodata` is false on gcc 13 to 15 and clang 19, and
  the schemas' hover text repeats it (1:I7);
- that dump and generate `--force` give output under any error, that nothing lands inside a printed
  document, and that nothing DDD writes is a file it read (5:I3, 5:I4, 5:I5).

### 4. Does it work?

**What holds, as measured.**
- **The file formats** (pass 6): five sources describe about two hundred keys and agree, over a
  thousand probes.
- **The generated C and a2l** (pass 8): every address, size, value, conversion and qualifier agrees
  with gcc and the linker. This held across every datatype, shape and kind, 26 image variants, a
  32-bit ABI, big-endian images and 456 random projects.
- **The checks and the core's code** (passes 7, 17 and 18): about 76,000 hostile documents raised no
  traceback, and `analysis.py` gave no wrong answer of its own.
- **The command line as a contract** (pass 9): 57,914 runs gave no crash and no wrong exit code on a
  project's fault.
- **The text engine** (pass 13): 122,179 random edits and 7,612 plans read back exactly, and undo is
  byte-exact.
- **The local server's security** (pass 12): a hostile page on another port got nothing, and 11,300
  malformed requests produced two `500`s.
- **The packaging** (pass 20): `pip install` of the wheel gives a working tool, pages included, with
  no Node.js needed.

**What fails**, ordered by the harm it does.
- **Stale output under a green build.**
  - Under Ninja, the first build after a description change recompiles the definitions but not the
    components that read the changed header. It exits 0, a consumer reads a truncated value, and only
    a second build corrects it (9:C1). Pass 9 calls it the failure the whole tool exists to prevent.
  - Four more changes end in `no work to do` over stale artefacts: a plugin that stops importing, a
    wildcard include, an edit to what a sub-project includes, and a plugin model that raises (9:I1,
    9:I2, 9:I3, 19:I2).
  - The `ADDRESS_MAP` flow writes the previous link's addresses into the a2l, with no finding even
    under `STRICT` (1:C2).
- **Files rewritten or lost by the GUI.**
  - A save during an analysis makes a plan rewrite the wrong declaration, value or entry (13:C1: in
    64 of 90 trials).
  - Two writers at once can delete the description (13:C2).
  - A save during an edit is overwritten, answered as written, and undo cannot bring it back (13:I1,
    raised to Critical).
  - Over a project the build collected, the GUI writes into the build tree, and the next configure
    drops what it wrote (1:C4).
- **Values the user did not write.**
  - The page holds 64-bit integers as doubles (3:C1).
  - A value picked for one key is carried to the next, so `"unit": "uint32"` loads with no finding and
    reaches the a2l (15:C1).
  - A number typed into a map cell loses digits to the table's type-to-find (16:C1, lowered to
    Important, because the file gets what the cell shows).
  - The ELF reader sign-extends a positive enumerator of a signed enum: `200` reads `-56`, clean under
    `--strict`, and it reaches the header and the a2l (11:C1).
- **Generated C the compiler may break.** The C that `--const-inputs` generates is undefined
  behaviour, and gcc reads a stale input from `-Og` up (1:C1).
- **A delivery verdict that passes a moved layout** (1:C3, 7:C1). An appended member, a grown nested
  structure, or a renamed and swapped nested type gives `info` or no finding, and a consumer built
  against the baseline reads 0.
- **The editor integration's model of the project.**
  - It assumes one project at a time, and the nearest description answers for the whole (10:I1,
    10:I2).
  - A rename's result depends on where F2 was pressed and on what is unsaved (10:I3, 10:I4).
  - 143 of 1,688 quick fixes write a file the loader refuses (10:I7).
- **The released version.** 0.11.0, the version users install, still has the security holes master's
  changelog says are fixed (the token sent as a cookie to every local port, among them), and there is
  no advisory (20:I4).

**The tests.** There are 7,042 Python tests, 959 Vitest tests and 294 journeys, at 100 % coverage, and
none of the Criticals fails any of them.
- **The core suite.** The tests that own the code notice about 72 % of the mutations that run
  (pass 21). The writers' outputs are matched by fragment, so a `float64` written as `UBYTE`, or an
  a2l whose `/begin` and `/end` do not match, still passes (21:I1, 21:I2, 21:I3).
- **The periphery suite.** It is better by every measure, killing 84 % of mutants (pass 22). But it
  tests one refusal at a time and never builds the second actor that every hand-found defect needs: a
  second writer, a save in the window, a second image, a buffer unlike the disk (22:I1).
- **The journeys.** They never type key by key, nor leave text in a field (23:I1).
- **What would catch them.** For each of those defects, the review left a probe that fails today and
  could become a regression test: 5 to 30 lines each, in pass 22's `test_p22_probes.py` and pass 23's
  `p23-probes.spec.ts`.

### What to fix first

In order of harm, with the sizes the passes gave:

1. **The edit engine** (13:C1, 13:C2, 13:I1). The causes are a fingerprint read after the analysis, one
   fixed stage name, and a check made once before all the writing. Each is hours to fix. Fix them
   before anyone edits a real project with the GUI and a text editor side by side.
2. **The build** (9:C1, then 9:I1 to 9:I3, 19:I2 and 1:C2). For 9:C1, `BYPRODUCTS` is already
   prototyped. Days, with one story test that edits, builds, and asserts that a second build has
   nothing to do.
3. **Silent wrong values.**
   - 11:C1, the first of pass 11's fixes.
   - 3:C1: either cells as exact text (pass 3's move 1) or a refusal past 2^53 (pass 3, question 1).
   - 15:C1.
   - 1:C1: pass 1's question 2 offers `--const-inputs` as a lint only.
4. **The comparison's layouts** (1:C3, 7:C1), once it is decided which consumer `compare` protects
   (pass 1, question 1, taken up by pass 7).
5. **`ddd gui` over a collected project** (1:C4).
6. **The release.**
   - Decide on the 0.11.0 advisory (20:I4).
   - Correct the changelog (4:I7, 4:I8) and SPEC's format number (5:I1).
   - Then release. Pass 20's advice: stop adding, fix what can lose a file or ship a wrong a2l,
     correct the changelog, and release.
7. **The tests that would have caught them.** Take the passes' probes into the suites (22:I1, 23:I1),
   and read the writers' outputs as records (21:I1 to 21:I3).
8. **The GUI guide** (4:I1), then the first moves of the split (pass 2's moves 0 to 4, pass 3's moves
   0 to 3).

### Decisions only the maintainer can take

Each report's Open questions section lists the decisions in its area. These are the ones that change
what to fix first, or that the review could not take:

- **The concept**:
  - which consumer `ddd compare` protects, one that is rebuilt or one that is not (pass 1, question
    1; pass 7, question 1). The answer decides what 1:C3 and 7:C1 become.
  - whether `--const-inputs` stays (pass 1, question 2);
  - what a consumer's restatement is, the interface or a copy (pass 1, question 3).
- **The split**:
  - whether a second interface, or a batch tool making edits, is a goal (pass 2, question 1). If it
    is, all of pass 2's moves are worth making; if not, stop after moves 0 to 4 and 10.
  - whether a 64-bit integer must be exact in the GUI (pass 3, question 1);
  - one panel per vocabulary, or one panel (pass 3, question 4);
  - whether `ddd gui` belongs in SPEC (pass 4, question 1);
  - whether `docs/superpowers` stays on master with an index, or moves to an orphan branch (pass 4,
    question 2).
- **The GUI's verdicts**: the Compare tab says "can replace" where `ddd compare` exits 1, and SPEC 4.1
  and the reference page disagree on which is right (14:I1).
- **The a2l**: loading one generated a2l in CANape and in INCA (pass 1, question 7; pass 4,
  question 6). It is an hour's work, and it settles 1:I8 to 1:I10 and the `MATRIX_DIM` order of 8:I3,
  which the review refuted on ASAP2 1.6.1's text alone.
- **Security**:
  - whether a dual-stack listener on `[::]` receives `localhost:<port>/open?token=` (12:I1). It is
    plausible, and at the edge of Critical if real. Testing it needs a wildcard bind, which the review
    may not make.
  - whether `ddd gui` must be safe on a tree not yet trusted, and whether the token must buy code
    execution (pass 12, questions 1 and 2);
  - the Docker image has no `USER`, so the writer runs as root there (19:M9).
- **The release and the repository**:
  - an advisory for 0.11.0 (20:I4);
  - turning on Dependabot's version updates, which GitHub does not run on a fork until enabled: a
    settings click (20:I1);
  - whether the releases are pre-releases or stable (20:M8);
  - pinning actions by sha and protecting the publishing environments (20:M13, 20:M14), which the
    2026-09-16 plan left to the maintainer.
- **The build**: which policy `<target>.ddd` should apply (24:I1). SPEC specifies the default
  policy, but the build page never says so, and under a project-wide relaxation the target can never
  pass. One component can sit in several images with different settings.
- **The page**: whether React Aria may close a chooser's list behind the reader (24:M2).
- **Two documents**: whether `ddd tool from-elf --format json` should print one document (25:M1), and
  whether the extension's README should be complete or a pointer (pass 25, question 2).
- **Left unsettled here**: 20:M1, which needs a `ddd check` under pydantic 2.9.2 and 2.10.0, and 20:M9,
  which needs `npm audit --omit=dev` in `editors/vscode` and so sends the dependency tree to the
  registry. The review could do neither.

### Grades at the edge

- **15:C1 kept Critical, 16:C1 lowered to Important.** Both are page defects that write what the user
  did not intend. 16:C1 writes what the cell and the sentence show, and Undo restores it. 15:C1 fills a
  key the user never touched, and `uint32` as a unit passes every check into the a2l.
- **13:I1 raised to Critical.** A save is overwritten and answered as written, and undo cannot bring
  it back.
- **19:I2 kept Important.** That is the grade V5 gave 9:I1, but the finding is wider than filed: from
  a working build, a plugin edited so that its validator raises leaves Ninja at `no work to do`, and
  every later edit is ignored until a manual reconfigure.
- **22:M6 raised to Important.** It is a gap in the tests, not a defect: nothing pins the default a2l
  byte order, so a one-token slip would give every CMake build without `BYTE_ORDER` a big-endian a2l
  under a green suite.
- **12:I1 left plausible.** It is at the edge of Critical if real.
- **Nine grades lowered**, each with its reason in its verification: 3:I8, 4:I8, 4:I9, 5:I1, 5:I6,
  16:C1, 19:I3, 20:I3 and 24:I1.
- **Pass 21's survivor counts for the C templates are overstated**, because its run left out
  `test_cmake`, which kills 8 of the 11 sampled (21:M2).

### How far to trust this review

- **The verdicts.** A second reader reproduced every finding, or read it off where it could not be
  run, and each verdict says which. Two findings were refuted. 8:I3, `MATRIX_DIM`'s order, fell on the
  standard's text. 22:M1 fell because the test it said would block 13:C2's fix pins only a suffix's
  spelling. Nine are left plausible: 10:I6, 10:I11, 10:M7, 12:I1, 12:M9, 12:M10, 20:M1, 20:M9 and
  23:M2.
- **Not run.**
  - Linux end to end: WSL has no pydantic, so Linux claims were checked with the real modules copied
    out of the tree. Nor macOS.
  - Anything as root: forbidden after pass 19's accident, which the coordinator's notes record.
  - Downloads and registry queries.
  - A real calibration tool, so no a2l was ever shown to load in one.
  - A real network loss: 15:I2 used the browser's offline event instead.
  - A person's smooth scroll, for 24:M2.
  - CMake below 4.3.
  - The screenshot job: Playwright's own Chromium is not installed here.
- **Samples.** Long lists were sampled, for example 21:I7's 65 survivors (16 re-run) and 23:I2's 134
  mutants (22 re-run). Each verification says what it did not re-run.
- **The evidence.** Transcripts, probes and mutant logs are in the review's scratch folder, named
  relative to it in each report. A copy without the bulky worker trees is at
  `C:\git\ac11\ddd\.claude\review-2026-11-03-scratch` on the review machine, untracked.
