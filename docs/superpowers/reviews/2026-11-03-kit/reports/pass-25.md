## Pass 25: the documents sweep

`SCRATCH` is `C:/Users/lmbsog0/AppData/Local/Temp/claude/C--git-ac11-ddd/8681cf0d-d41d-4120-88ca-b1b2c3615be8/scratchpad`.
Every script and transcript named below lies under `SCRATCH/pass-25/`. Line numbers are on the review tree (code at
master `2b4bae6c`). Everything ran in `t0/`, a copy made with `git -C <tree> archive HEAD | tar -x -m`, the review
venv's python with `PYTHONPATH=t0/src`; `ddd_file.txt` prints `ddd.__file__` as the copy's. No server or listener was
started; no process of mine is left; the tree's `git status`, plain and `--ignored`, is as before (`status-*.txt`).

**The answer, plainly.** Against the tool's own lists, the reference documentation is complete and, where two
documents state one fact, they agree almost everywhere: of 505 surfaces, 448 are documented where a user looks, and
the 57 others are the GUI (34 of its 66 rows), four environment variables, three exit-code cases, the plugin
`CheckInfo` flags and a handful of copies. The sweep found one new contradiction (M1, Minor) and no new Critical or
Important: the documents' real problem is still what pass 4 named - no guide to `ddd gui` (pass 4 I1, KNOWN) and the
same fact told in several places (pass 4 I10) - and the sweep found four more copies of earlier findings that the
earlier passes did not list (Assessment).

### Scope covered

**Read first.** `review-brief.md`; `passes.md`, its introduction and Part E; `pass-4.md`, `pass-20.md`, `verify-4.md`,
`verify-20.md` in full; `SCRATCH/pass-24/digest.txt` (the Scope covered and candidates of passes 1 to 23 and the
verdicts of V1 to V11), all 1,724 lines; `pass-24.md` in full.

**The tool's own words** (`inv/`): `ddd --help` and the `--help` of all 22 commands and subcommands, a plugin's
artefact included (`inv/help/*.txt`, all exit 0); the parser walked in process (`cli_walk.py` ->
`cli_options.tsv`: 98 argument rows, 31 option strings); `ddd checks` and `--format json` (72 checks);
the committed schemas walked (`schema_keys.py` -> 341 property rows, 153 distinct keys per kind); `cmake/Ddd.cmake`'s
`cmake_parse_arguments`, targets and properties; the server's `initialize` capabilities (`lsp/server.py:885-900`) and the
extension's `contributes`; the plugin api's dataclasses (`Plugin`, the three contexts, `CheckInfo`, `GeneratedFile`,
`Backend`, `DiagnosticBag.add`); every environment read in `src`, `docs/conf.py`, `cmake`, `gui/scripts`, `gui/e2e`,
`editors/vscode/src`; the exit codes of `cli.py`, `gui/server.py`, `lsp/server.py`; the GUI's tabs, routes and screens
(`app/App.tsx`, `lib/route.ts`, `screens/*`, `components/*View.tsx`, labels by `gui_actions.py`) and the titles of all
journeys (`inv/e2e_titles.txt`), read off the source rather than driven.

**The inventory** is `SCRATCH/pass-25/inventory.tsv` (surface, where documented, verdict, note), built by
`build_inventory.py` with the GUI rows written by hand (`inv/gui_rows.tsv`) and the rows judged by reading in
`inv/overrides.tsv`. Counts (`inv/inventory_groups.txt`):

| category | rows | documented | not plainly documented |
| --- | --- | --- | --- |
| commands | 20 | 20 | - |
| options and positionals | 90 | 89 | 1 stated wrongly (M1) |
| checks | 72 | 72 | - |
| description and dictionary keys | 153 | 152 | 1 in the generated reference only (`cycle_ns`, pass 4) |
| CMake keywords, functions, targets, properties | 38 | 32 | 6 internal, rightly not |
| language server and extension | 15 | 10 | 2 editor page only (4 M11), 1 overstated (10 M8), 1 editor page only (the restart command), 1 nowhere (10 M7) |
| plugin api | 27 | 24 | 3 `CheckInfo` flags only as `ddd checks` json keys (9 M12) |
| outputs | 10 | 10 | - |
| environment | 7 | 3 | 2 nowhere, 1 contributor page only (4 M16), 1 internal |
| exit codes | 7 | 4 | 1 nowhere, 1 SPEC only (4 M5), 1 contradicted (9 M1, 19 I3) |
| `ddd gui` screens, actions, states | 66 | 32 | 13 nowhere, 9 changelog only, 4 design records only, 7 partly, 1 contradicted by the page (16 I5) |
| **total** | **505** | **448** | **57** (7 of them internal) |

**What no pass read closely.** From the Scope covered sections every user document was read whole by at least one pass
(README by 1, 4, 20; SPEC by 1, 5; CHANGELOG by 20; every page of `docs/` by 4 and an area pass) but two:
`assets/logo/README.md` (63 lines) and `docs/_templates/versions.html` (31; pass 20 read its head). I read both and
checked the logo page's facts (the README's icon is `ddd-icon-128.png` over its raw url, `editors/vscode/icon.png` is
that file byte for byte, `custom.css` paints `#123540`): nothing to report. Read as documentation for the first time,
rather than as code: the 104 key descriptions of the seven description schemas (`inv/schema_descriptions.txt`), which
every editor shows as hover text and `data_contracts.rst` renders, and the top-level and object descriptions of the
dictionary schema (`inv/dictionary_descriptions.txt`, its 106 rows by name, about half read).

**The seams, mechanically** (each script beside its output in `inv/`):
- `doc_cmdlines.py`, `doc_values.py`: every `ddd ...` command line in 33 user documents, inline literals and code
  blocks, README, SPEC, CHANGELOG and the extension's README included - 803 lines - held to the parser's options, the
  registry's checks and severities and the choices of `--format`, `--scope`, `--without`, `--byte-order` and `schema`.
- `quoted_messages.py`: every sentence the documents quote from the tool, inline or as a finding line, looked up in the
  tool's strings (python via `ast`, the page's sources whole).
- `checks_xref.py`, `checks_text.py`: each check's severity and flags in the registry, the reference page, README and
  SPEC, and its description in all four side by side (`checks_text.md`); first release of every check missing from the
  changelog (`git log -S`).
- `keys_xref.py`: each key of each schema on the format pages, the other pages, README, SPEC.
- By hand: limits and counts the documents state (include depth, nesting, caps, ids, name lengths, undo, timeouts, body
  size) against the source's constants; the json shapes of `artefacts`, `sources`, `checks`, `list`, `compare`; the
  exit codes of `sources`, `artefacts`, `list`, `checks --plugin`, `schema --plugin`, `build-info`, `id`; the
  `ddd gui` row of the command line page (`command_line_interface.rst:294-567`) claim by claim against the screens and
  `gui/session.py`, `gui/compare.py`; plugins page against `plugins.py`; the extension's README against
  `package.json`, `extension.ts`, the editor page and SPEC 7.2; the public interface between `v0.11.0` and HEAD
  (`git diff` of the c model, ir, models, schemas, cmake).
- Probes: `probe/elf/transcript.txt` (M1); `probe/o0/` (the documents' `-O0` claim, compiled with MinGW gcc 15.2);
  `probe/sm/` (a documented `storage-mismatch` message); `probe/exits/` (exit codes, json shapes, plugin listings);
  `probe/cmp/` (compare json and `--renames`).

**Not covered.** The page was not driven: its screens are read off `gui/src` and `gui/e2e`, as the brief allows. No
documentation build (the brief does not need one; passes 4 and 20 built it under `-W`). The 90 quoted sentences the
lookup could not match verbatim were not checked one by one: 24 were, and each was a message composed from parts, a
pydantic or compiler message, or a transcript `tests/test_transcripts.py` runs. SPEC was not read whole again (passes 1
and 5); the dictionary schema's nested descriptions were read in part.

### Strengths

- **Every documented command line is one the tool accepts.** 803 `ddd ...` lines in 33 documents name no option their
  command lacks; every `-W` names a registered check and severity; the 9 lines flagged are the pages' own refusal
  demonstrations (`-W schema=ignore`, `-W unused-output=nope`) and alternation notation (`inv/doc_cmdlines_bad.txt`,
  `inv/doc_values_bad.txt`). `test_transcripts.py` holds the `$` transcripts of the pages and README; this holds the rest
  too, including SPEC, the changelog and the extension's README.
- **The tool's sentences are quoted exactly.** 136 quoted in prose - 33 of them the GUI row's refusal texts, which no
  test runs - are in the tool word for word (`inv/quoted_found.tsv`).
- **One severity per check everywhere.** 72 of 72 checks carry the registry's severity on the reference page, README and
  SPEC, the eight fixed ones counted alike; the four descriptions per check agree but for the two pass 7 M15 already
  named (`changed-interface`'s layout clause, `missing-plugin`'s "this run has not loaded"). Every check missing from the
  changelog predates its first section (`v0.5.0`) but `empty-vocabulary` (pass 4 I8).
- **The strong claims tried hold.** "at `-O0` the body is `mov eax, 3`" (`generated_artefacts.rst:452`, five other
  copies): MinGW gcc 15.2 writes exactly that, `mov eax, 30` for the array and `mov eax, 3` for the start-up copy
  (`probe/o0/gain-O0.s`). README.md:947-949's "the file keeps its owner and permissions although every service runs as
  root" holds even for a file the GUI creates, which takes the project description's (`gui/session.py:891`,
  `editing.py:949-963`). The documented json shapes of `artefacts`, `sources`, `checks` and `list`, the exit codes of
  nine commands, the build record's keys and the plugin listings are what the tool prints (`probe/exits/`).
- **The schema hover texts are documentation, and good.** The 104 descriptions say what a key means, what it may hold,
  where the loader is stricter than the published schema ("`4`, not `4.0`"), and why; but for the one claim below they
  agree with the pages and SPEC.

### Issues

#### Critical

None.

#### Important

None new. The largest documentation gap remains pass 4 I1 (KNOWN), which the inventory widens by rows, not by grade.

#### Minor

- **M1. `ddd tool from-elf --format json` writes its findings to stderr, beside the declarations on stdout, where README
  and the command page say `ddd dump` is the only command that does so.** `README.md:804` ("`ddd dump` is the one command
  whose stdout is *itself* the payload, so there the diagnostics go to stderr"), `docs/command_line_interface.rst:27-28,57`
  ("In json the diagnostics become part of the document the command prints ... The one exception is `ddd dump`"); SPEC
  names dump alone (`SPEC.md:2173-2175`) and 7.3 says only that the declarations go to stdout (`:2484-2485`); the tool's
  own help says the truth (`src/ddd/cli.py:606-613`, "which go to stderr on this command"), and `docs/toolbox.rst` never
  names `--format`.
  *Trigger:* `ddd tool from-elf x86_64.elf Type_Bool Type_F32 --format json > out.json 2> err.json`, on the committed
  fixture. *Observed:* `out.json` is a list of two interface entries, `err.json` is `{diagnostics, summary}` with the
  `elf-not-inferred` info, exit 0; a glob matching nothing leaves stdout empty and the error document on stderr
  (`probe/elf/transcript.txt`, `out*.json`, `err*.json`). *Expected, by the pages:* one document on stdout holding the
  declarations next to `diagnostics`, as `list`, `sources` and `artefacts` print. A script written from the command page
  parses stdout for `diagnostics` and gets a list, or nothing. *Why Minor:* `from-elf` runs once on the way into DDD,
  rarely in a job, and its own help is right. *Change:* name the two commands whose stdout is the payload in both places
  (two sentences, S); or derive the sentence in a test from the parser, whose `--format` help already says which.

### Status of the 2026-09-15 findings in this area

None beyond what passes 4 and 20 tabulated for that review's pass 7; nothing in this sweep changes one of their
statuses.

### Open questions

1. **Should `ddd tool from-elf --format json` print one document, as `list` does, or stay as `dump` is (M1)?** One
   document makes the command page's rule true and is a change of an output, so a changelog line; staying as it is costs
   two sentences on two pages and one on the toolbox page.
2. **Is `editors/vscode/README.md` meant to be complete, or a pointer to the editor page?** It is the page VS Code shows
   for the extension and the only one inside the `.vsix`; today it is neither (Assessment). Complete means keeping a third
   copy in step with SPEC 7.2 and the editor page; a pointer means four lines and the settings table.

### Test gaps

- Nothing holds "the one exception" (`README.md:804`, `command_line_interface.rst:57`) to the parser, whose `--format`
  help says per command where the findings go: M1 passes the whole suite.
- `tests/test_transcripts.py` reads the `$` transcripts of `docs/*.rst` and README alone (`:63-66`). The command lines in
  prose, and every one in SPEC, the changelog and the extension's README, are held by nothing; `doc_cmdlines.py` and
  `doc_values.py` (about 120 lines) hold all 803 today.
- The 136 tool sentences quoted in prose, the GUI row's 33 refusal texts among them, are held by nothing: a reworded
  refusal leaves the page quoting the old one. `quoted_messages.py` is the shape such a test would take, with a list of the
  composed messages it may skip.
- No test reads the extension README's settings table or feature list against `package.json` and the server's
  capabilities (`tests/test_documentation.py:850-883,1033-1065` hold its install route and trust paragraph only).

### Assessment

The documentation is a complete reference to a tool that holds still while it is described: every command, option,
check, key, CMake keyword and target, plugin field and output has a row where a user looks, the pages quote the tool
word for word, and the documented command lines all run as written. Where it fails is where the tool moved fastest. The
GUI has 34 of its 66 surfaces documented nowhere, in the changelog alone, in design records alone, in part, or
contradicted by the page, which is pass 4 I1 seen row by row: this inventory adds eleven small rows to pass 4's nineteen (the start page's search depth and
the directories it skips, the layout worker's failure, the unit chooser, the Files tab's waiting Remove, the undo cap of
fifty, undo emptied by opening a project, the keyboard, the screen-reader notes, a values grid read only or reading
zero, the "Connecting" state, that opening or comparing runs plugins), and none changes I1's grade. And the facts told in
several places keep parting, pass 4 I10's mechanism, which this sweep met four more times in candidates already filed:
**1 I7 is wider:** the published schemas' hover text says `volatile` "on a typical toolchain, moves a calibration object
out of read-only memory" (`src/ddd/models/objects.py:607-608`, `schemas/ddd_component.schema.json:231` and five more
definitions), so every editor carries the claim gcc 13 to 15 contradict. **1 M2 is wider:** `README.md:29` says "The front
end never mentions c or a2l" as `concept.rst:530` does. **4 M11 is wider:** `editors/vscode/README.md`, the extension's own
page, also omits the `missing-id` quick fix (SPEC 7.2 and `editor_integration.rst:148` have it) and its one command,
"DDD: Restart Language Server" (`editor_integration.rst:251`, "for picking up a newly installed tool"). **12 M1 is wider:**
its 500 on `?baseline=%00` breaks `CHANGELOG.md:202-210` ("a path with a NUL character ... is refused with a plain `400`,
`404` or `409` ... No malformed input ... is answered with a `500` any more") as well as the security page it names.
Further Minor, unnumbered: `README.md:810` gives the exit codes as 0, 1 and 2, where the command page and SPEC add 130.
What I would do: write the GUI guide (pass 4 I1), and turn this pass's three scripts into tests, since the reference half
of the documentation is already kept true by tests and these are the halves no test reads.

```candidates
25|M1|README.md:804|ddd tool from-elf --format json writes its findings to stderr beside the declarations on stdout, where README and the command page say dump is the one command that does so
```
