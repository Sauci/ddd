### Verification of pass 4

By a reader who did not find these, on 2026-11-06, on the tree at master 2b4bae6c. Scratch:
`SCRATCH/verify-3-4/`. 30 CONFIRMED. Grade changes: I8 Important -> Minor; I9 Important -> Minor.

| id | verdict | grade (was -> now) | duplicate of | evidence | note |
| --- | --- | --- | --- | --- | --- |
| I1 | CONFIRMED | Important -> Important | - | read off docs/command_line_interface.rst:294-567, docs/index.rst:9-25; verify-3-4/p4/html | confirmed as text: the gui row runs 274 lines, about 4,000 of the page's 8,000 words by my count, with no heading of its own (#ddd-gui lands on the generated argparse section); the sidebar's one GUI entry is GUI security; concept, getting_started, faq and index prose name the GUI 0 times; Tidy, Search modules, Adopt N units and Add to the vocabulary are drawn by the page and named in no document; KNOWN holds (the user guide, part 20: 2026-10-08-gui-journeys-every-action.md:1623, web-gui design 6.12) |
| I2 | CONFIRMED | Important -> Important | 1:I13 | verify-3-4/p4/i2.txt | reproduced: one component reading LegacySpeed, generated with a fresh copy of ddd templates-dir under -W missing-producer=ignore, defines volatile uint16_t LegacySpeed in the unresolved group; linked with the legacy.c defining it, gcc stops on multiple definition of LegacySpeed, and without legacy.c it links (control), the opposite of concept.rst:318-320; no page orders an adoption; in part 1:I13 (the model cannot say defined elsewhere), adding the missing guide and the link failure |
| I3 | CONFIRMED | Important -> Important | 1:I8 | read off docs/faq.rst:612-618, docs/file_formats/rasters.rst:126-133, docs/acronyms.rst:147-151, docs/file_formats/sections.rst:98-100, docs/concept.rst:234-238 | confirmed as text: A2ML and EPK occur on no page, MEMORY_SEGMENT only as planned, and the three notes stop at come from whatever configures the XCP stack; KNOWN corrected: 2026-09-16-review-fixes.md:87 says P10-M13 was documented as a reader obligation, and A2ML was never on any page (git log -S), so that closure did not happen, no regression; the documentation half of 1:I8 |
| I4 | CONFIRMED | Important -> Important | - | verify-3-4/p4/i4_powershell.txt, p4/i4_cmd.txt, p4/i4_bash.txt | reproduced: ddd id --assign components/*.ddd.json in PowerShell 5.1 and in cmd prints `components\*.ddd.json: not readable as json, skipped`, `wrote 0 ids`, exit 1, where Git Bash writes 2 ids; no page says its transcripts are a POSIX shell, and tests/test_transcripts.py:331-333 runs every one through bash |
| I5 | CONFIRMED | Important -> Important | 2:I5 | read off docs/developer_documentation.rst:899-1201 | confirmed as text: 3,747 words under one heading; contract.py, queries.py, routes.py and gui/api.py named 0 times, session.py once in a test-helper paragraph (:1008), the long poll once (:1008-1009), useKept, TanStack and the page's rules 0 times; extends 2:I5 (the layer table) to the GUI's server and page, adding where a new route or screen goes |
| I6 | CONFIRMED | Important -> Important | - | read off docs/developer_documentation.rst:392-404,416,535,665, README.md:995-1003; verify-3-4/p4/i6_symlink.txt | confirmed: both start at python -m pytest, pip install -e .[dev] appears only as a fact about ci (:535), no CONTRIBUTING or pull request template, CHANGELOG named 0 times on the developer page; the symlink test fails here, WinError 1314, while :416 says nothing in the suite skips and no page names the privilege or Git Bash for pytest |
| I7 | CONFIRMED | Important -> Important | - | verify-3-4/p4/i7.txt, p4/changelog_v0.11.0.md | reproduced from git: the paste, plot, Compare and mismatch button entries sit in HEAD's ## 0.11.0 (CHANGELOG.md:345,356,371,389) and in none of git show v0.11.0:CHANGELOG.md; v0.11.0 holds no ComparePage.tsx; PRs #61, #63, #64, #65 merged 2026-09-24 to 2026-09-27, after the tag (2026-09-24 06:45) |
| I8 | CONFIRMED | Important -> Minor | - | verify-3-4/p4/i8.txt | confirmed with a correction: empty-vocabulary (registered, info) occurs 0 times in CHANGELOG.md, 39f77bab relaxed five schemas, the Shared files (#67, #69, #71) and Files (#73) tabs have no entry; but the Unreleased from-elf bullet does name pyelftools as a new runtime dependency (CHANGELOG.md:26-27); lowered: nothing is released and the omissions cost an upgrader nothing (an info check, a schema that now loads what it refused, the preview's tabs) |
| I9 | CONFIRMED | Important -> Minor | - | read off SPEC.md:785,2132-2137, README.md:1053-1058, docs/superpowers/specs/2026-09-17-web-gui-design.md:500-505 | confirmed as text: SPEC names ddd gui twice and nothing on what it writes, refuses or undoes; lowered: the SPEC itself calls it a preview outside the interface (2136-2137), as the design decided (6.12), so no reader relies on an unspecified promise; what it costs is a contract for reviews, the maintainer's call |
| I10 | CONFIRMED | Important -> Important | - | read off README.md:36-38, tests/test_documentation.py:194,385,590; the volatile paragraphs at the eight places named | confirmed: README says it is the short version at 1,058 lines, and the suite asserts every check, command and common key is in it; the volatile account is told at all eight places named; the parted copies are real: M2, M3 and M11 below each confirmed |
| M1 | CONFIRMED | Minor -> Minor | - | verify-3-4/p4/m1_links.txt, p4/sphinx-build.txt | reproduced: sphinx-build -W passes with 0 warnings and builds no py-modindex.html; index.html links it; the one broken internal target of 30 pages |
| M2 | CONFIRMED | Minor -> Minor | - | read off docs/acronyms.rst:66-70,233-236, docs/faq.rst:553-565 against :515-528, docs/getting_started.rst:530-535, docs/file_formats/types.rst:333-336 | confirmed as text: DWARF row says DDD does not read it while ddd generate a2l --image reads it; the other four name --address-map alone, and faq.rst:564 keeps address zero silently beside the address-missing warning it shows at :517 |
| M3 | CONFIRMED | Minor -> Minor | - | read off docs/getting_started.rst:21-24,31-33, requirements.txt:1-7, README.md:52-53, docs/developer_documentation.rst:631 | confirmed as text: the tutorial says the only runtime dependencies are pydantic and jinja2 and the wheel carries everything apart from those two; requirements.txt and README add pyelftools; the developer page's dev-build recipe installs the two and --no-deps; no page gives an offline recipe |
| M4 | CONFIRMED | Minor -> Minor | - | read off docs/file_formats/component.rst:450-491 against docs/consistency_checks.rst:220 | confirmed as text: the page checks a component with -W missing-producer=ignore and three unknown-* overrides and never names --standalone (its one standalone at :438 is the word); consistency_checks.rst:220 calls naming the overrides by hand the mistake the flag exists to end |
| M5 | CONFIRMED | Minor -> Minor | - | verify-3-4/p4/m5.txt; read off src/ddd/gui/server.py:1051-1057, SPEC.md:2460-2463 | reproduced in process: a KeyboardInterrupt in GuiServer.serve_forever through cli.main ends ddd gui at exit 0, where the same interrupt in ddd check's analysis ends at 130 (control), against the page's exit code is the same everywhere and 130 for Ctrl-C; lsp's 0 or 1 is in the SPEC alone |
| M6 | CONFIRMED | Minor -> Minor | - | read off README.md:112-138,258-272 against docs/file_formats/index.rst:118-124, docs/plugins.rst:274-278, docs/editor_integration.rst, docs/build_integration.rst:492 | confirmed with a correction: the site's sample files on five format pages carry a $schema line and plugins.rst:276 says to point it at the schemas, and SCHEMA_DIRECTORY has its row; what is README-only is that the loader allows and ignores the key, the per-file relative path and the commit-or-build choice; editor_integration.rst has no $schema |
| M7 | CONFIRMED | Minor -> Minor | - | read off docs/build_integration.rst:8-9, docs/concept.rst:402-404, docs/command_line_interface.rst:714-717 | confirmed as text: two integrations are shipped, cmake and the docker image; concept.rst says DDD can be driven from make or a batch file and the sources page says its list can be pasted into a makefile, and no page assembles a make recipe |
| M8 | CONFIRMED | Minor -> Minor | - | read off docs/getting_started.rst:597-619, docs/build_integration.rst:143-166 | confirmed with a correction: the tutorial ends at generated files and Where to go next names concept, templates, the file formats and the command line, not the build, the editor or the GUI; but components/controller.c is named, in the build page's CMake snippet (:147), while no page shows hand-written C reading a curve, a member or an enum |
| M9 | CONFIRMED | Minor -> Minor | - | read off docs/templates.rst:472-477, examples/templates/ddd_globals.c.jinja2:2-5, docs/editor_integration.rst:259 | confirmed as text: no upgrade page; the pieces are scattered; templates.rst says nothing refers back to the copy taken, while the example template now renders the section attribute a copy taken before sections would not |
| M10 | CONFIRMED | Minor -> Minor | - | read off docs/editor_integration.rst:33-36,176-181, editors/vscode/README.md:10, README.md:151 | confirmed as text: Neovim, Helix and Emacs need only the command, with no filetype pattern or snippet; announced as log messages says not where; no page answers why no squiggle appears |
| M11 | CONFIRMED | Minor -> Minor | - | read off SPEC.md:2350-2362, README.md:212-224, editors/vscode/README.md:91-95 against docs/editor_integration.rst:91-104,154 and src/ddd/lsp/server.py:727-791 | confirmed as text: SPEC 7.2 and both READMEs rename an object, a type or a constant; the editor page and the server also rename a unit (_rename_unit), a section and a raster, and offer unknown-unit's two fixes |
| M12 | CONFIRMED | Minor -> Minor | - | read off SPEC.md:2215, src/ddd/ir.py:645; ddd dump of my probe project prints format 9 | confirmed: SPEC says today 8, DICTIONARY_FORMAT = 9 and a dump says 9; KNOWN holds, filed by the paused 2026-09-24 review (SCRATCH/pass-1-2026-09-24.md, its I1) and not fixed since |
| M13 | CONFIRMED | Minor -> Minor | - | read off README.md:42-46, CHANGELOG.md:7-11, docs/plugins.rst:120-121 | confirmed as text: the public interface is listed without the plugin api, while plugins.rst promises a field can be added without breaking a plugin written against the previous version |
| M14 | CONFIRMED | Minor -> Minor | - | read off the tree: no examples/README* and no gui/README* | confirmed: ten example directories and gui/ have no README |
| M15 | CONFIRMED | Minor -> Minor | - | read off docs/acronyms.rst:17-258, docs/concept.rst:241-302 | confirmed: the glossary has no LSP, A2ML or EPK row, and neither it nor concept.rst's Vocabulary section has a term the GUI's sentences use (plan, revision, stale, Apply) |
| M16 | CONFIRMED | Minor -> Minor | - | read off docs/conf.py:102-104, gui/scripts/schemas.mjs:4,13, docs/developer_documentation.rst:674-681,1015, docs/gui_security.rst:237 | confirmed as text: PLANTUML_JAR, JAVA and schemas.mjs's DDD are on no page; BROWSER only as a test fixture; the security page asks for a browser profile of its own and says not how |
| M17 | CONFIRMED | Minor -> Minor | - | read off docs/gui_security.rst, its headings at 9, 123, 156, 185, 195, 250, 256 | confirmed as text: the sections are a threat model, the bullet at 47-106 is 935 words by my count, and the reader's own steps (paste rather than click at 136-138, a profile of its own at 237, the reused-code line) are spread through it |
| M18 | CONFIRMED | Minor -> Minor | - | read off docs/consistency_checks.rst:519-521,839,854, docs/generated_artefacts.rst:610-612,866, docs/build_integration.rst:548-554, docs/file_formats/component.rst:323-324, docs/developer_documentation.rst:419 | confirmed as text: each quoted history and defence sentence is at the line cited |
| M19 | CONFIRMED | Minor -> Minor | - | verify-3-4/p4/html; read off docs/templates.rst headings, docs/generated_artefacts.rst | measured: templates.rst argues in four sections to :86 and starts Getting started at :449 of 507; generated_artefacts.rst 1,374 lines; data_contracts.html 2,441,477 bytes, 49 % of the built pages |
| M20 | CONFIRMED | Minor -> Minor | - | verify-3-4/p4/m20_status.txt; read off docs/developer_documentation.rst:1053-1056,1089-1092, src/ddd/toolbox/from_elf.py:4, src/ddd/gui/queries.py:7-8, pyproject.toml:100-106, gui/src/stories/fixtures.ts:1576 | confirmed: of 32 records 14 state no status and 12 say to be planned, not implemented or not yet planned of merged work; pages and code cite records the sdist excludes; KNOWN as a regression in kind: 2026-09-16-review-fixes.md:172 fixed the four lines 2026-09-15 named, and the staleness regrew in later records |

No candidate of pass 4 is refuted or left plausible. Two are lowered. Four more are confirmed with
corrections (I3, M6, M8 and M20), and two are partly duplicates of earlier findings (I2, I5).

I built the site myself with the system Python's Sphinx 8.2.3:
`sphinx-build -W --keep-going -b html -d verify-3-4/p4/doctrees docs verify-3-4/p4/html`, with `dot`
15.1.1 and plantuml through `JAVA` and `PLANTUML_JAR`. It passes with 0 warnings in 30 s, 30 pages
(`p4/sphinx-build.txt`). Every command a finding says a reader would run, I ran on copies of my own,
under the shells it names (`p4/i2.txt`, `p4/i4_*.txt`, `p4/m5.txt`). Each claim about text, I read on
both sides. The tree was not written; `find -newer` over it after the build and the pytest run shows
nothing outside the coordinator's `docs/superpowers/reviews/`.

**I8, confirmed with a correction, lowered from Important to Minor.** The facts hold (`p4/i8.txt`):
- `empty-vocabulary` is registered (info) and occurs nowhere in `CHANGELOG.md`.
- `39f77bab` (PR #72) relaxed the five vocabulary schemas.
- The Shared files tab (PRs #67, #69, #71) and the Files tab (#73) have no entry. "Files tab" and
  "Shared files" occur only in two later fixes (`CHANGELOG.md:34,52`).
- `## Unreleased` has 28 bullets and no `Migration:` line.

The correction: the Unreleased from-elf bullet does announce pyelftools, "which joins pydantic and
jinja2 as a runtime dependency" (`CHANGELOG.md:26-27`).

Why it is lowered: the section is unreleased, and what it omits costs an upgrader nothing.
- The new check is at info, which `--strict` does not promote (it reports warnings as errors).
- The schema change only lets a file load that used to be refused.
- The tabs belong to a preview.

So no user is misled into a wrong step, and the header's rule can still be met at release. It is
real and cheap to fix, and the missing registry-against-changelog test the pass names is the
durable fix.

**I9, confirmed as text, lowered from Important to Minor.** `SPEC.md` names `ddd gui` twice (785,
2136) and says nothing on what it writes, refuses or undoes, while `README.md:1055-1058` calls the
SPEC the contract the implementation is measured against. But the SPEC itself calls the GUI "a
preview whose options are not yet part of this interface" (2136-2137). That is exactly what the
design decided in `docs/superpowers/specs/2026-09-17-web-gui-design.md:505`. No reader is led to rely
on a behaviour the SPEC promises. What the silence costs is a contract to hold reviews against,
which is the maintainer's call, the pass's own open question 1. The user-facing half of the gap is
I1, which stays Important.

**I3, confirmed, with its KNOWN tag corrected.** The plan it cites
(`2026-09-16-review-fixes.md:84-88`) does not leave P10-M13 open. It says the item was "documented as
a reader obligation instead". The pages that exist do document an obligation, for the DAQ list,
the `PROTOCOL_LAYER` and the transport (`faq.rst:612-618`, `rasters.rst:126-133`,
`acronyms.rst:147-151`). They do not document one for the A2ML the item was about. A2ML and EPK occur
on no page, and `git log -S A2ML` over the pages finds no commit ever adding A2ML. So this is not a
regression: the closure the plan records never happened for A2ML. The finding is the documentation
half of pass 1 I8, and adds the missing recipe for the integrator.

**I2, confirmed, a duplicate in part of pass 1 I13.** I made one component reading `LegacySpeed`,
which a hand-written `legacy.c` still defines, and generated it with a fresh copy of
`ddd templates-dir` under `-W missing-producer=ignore` (`p4/i2.txt`). DDD writes
`volatile uint16_t LegacySpeed;` under `<unresolved>`. MinGW gcc 15.2 then stops on "multiple
definition of `LegacySpeed`". Without `legacy.c` the image links. This is the opposite of
`concept.rst:318-320`, which says such a project "would link only if some hand written translation
unit happened to define the symbol". Pass 1 I13's first bullet is the model's side of this: there is
no way to state an object defined elsewhere. What pass 4 adds is that no page orders an adoption,
and that the first step a reader would take fails at the link.

**I5, confirmed, extending pass 2 I5.** Of the GUI server's modules, `developer_documentation.rst:899-1201`
names only `session.py`, once, in a paragraph on a test helper (:1008). `contract.py`, `queries.py`,
`routes.py` and `gui/api.py` are named nowhere. The long poll is mentioned once, and the page's rules
not at all. Pass 2 I5 is the layer table's omission of the same code, so the two are one gap seen
from two sections.

**M6, confirmed with a correction.** The site is not silent about `$schema`:
- Five format pages show a `$schema` line in their sample file.
- `plugins.rst:276` says to point it at the published schemas.
- `SCHEMA_DIRECTORY` has its row on the build page (`build_integration.rst:492`).

What the README alone gives is the reason and the how: the loader allows and ignores the key, the
path is per file and relative, and the schemas are either committed or written by the build.

**M8, confirmed with a correction.** `examples/cmake/components/controller.c` is named, in the build
page's CMake snippet (`build_integration.rst:147`). The rest holds:
- No page shows hand-written C reading a curve, a structure member or an enum.
- "Where to go next" names neither the build integration, the editor nor the GUI.

**M20, confirmed, with its KNOWN tag read as a regression in kind.** The 2026-09-15 finding it cites
was fixed: `2026-09-16-review-fixes.md:172` corrected the four stale lines it named. Since then:
- Of the 32 records, 14 state no status.
- 12 say "to be planned", "not implemented" or "Not yet planned" of merged work
  (`p4/m20_status.txt`). Among them is `2026-10-02-addresses-from-image-design.md`, though
  `--image` ships.

So the defect regrew in the records written after the fix. Pages and code still cite records the
sdist excludes (`pyproject.toml:100-106`).

The other Minors are confirmed as read. Where I counted, my figures agree with the pass's within the
noise of word-counting:
- the gui row is 274 lines and about 4,000 of the CLI page's 8,000 words by my count;
- `data_contracts.html` is 2.44 MB, 49 % of the built pages;
- the 47-106 bullet of the security page is 935 words.

```verdicts
4|I1|CONFIRMED|Important|Important|-|confirmed as text: the gui row runs 274 lines, about 4,000 of the page's 8,000 words by my count, with no heading of its own (#ddd-gui lands on the generated argparse section); the sidebar's one GUI entry is GUI security; concept, getting_started, faq and index prose name the GUI 0 times; Tidy, Search modules, Adopt N units and Add to the vocabulary are drawn by the page and named in no document; KNOWN holds (the user guide, part 20: 2026-10-08-gui-journeys-every-action.md:1623, web-gui design 6.12)
4|I2|CONFIRMED|Important|Important|1:I13|reproduced: one component reading LegacySpeed, generated with a fresh copy of ddd templates-dir under -W missing-producer=ignore, defines volatile uint16_t LegacySpeed in the unresolved group; linked with the legacy.c defining it, gcc stops on multiple definition of LegacySpeed, and without legacy.c it links (control), the opposite of concept.rst:318-320; no page orders an adoption; in part 1:I13 (the model cannot say defined elsewhere), adding the missing guide and the link failure
4|I3|CONFIRMED|Important|Important|1:I8|confirmed as text: A2ML and EPK occur on no page, MEMORY_SEGMENT only as planned, and the three notes stop at come from whatever configures the XCP stack; KNOWN corrected: 2026-09-16-review-fixes.md:87 says P10-M13 was documented as a reader obligation, and A2ML was never on any page (git log -S), so that closure did not happen, no regression; the documentation half of 1:I8
4|I4|CONFIRMED|Important|Important|-|reproduced: ddd id --assign components/*.ddd.json in PowerShell 5.1 and in cmd prints `components\*.ddd.json: not readable as json, skipped`, `wrote 0 ids`, exit 1, where Git Bash writes 2 ids; no page says its transcripts are a POSIX shell, and tests/test_transcripts.py:331-333 runs every one through bash
4|I5|CONFIRMED|Important|Important|2:I5|confirmed as text: 3,747 words under one heading; contract.py, queries.py, routes.py and gui/api.py named 0 times, session.py once in a test-helper paragraph (:1008), the long poll once (:1008-1009), useKept, TanStack and the page's rules 0 times; extends 2:I5 (the layer table) to the GUI's server and page, adding where a new route or screen goes
4|I6|CONFIRMED|Important|Important|-|confirmed: both start at python -m pytest, pip install -e .[dev] appears only as a fact about ci (:535), no CONTRIBUTING or pull request template, CHANGELOG named 0 times on the developer page; the symlink test fails here, WinError 1314, while :416 says nothing in the suite skips and no page names the privilege or Git Bash for pytest
4|I7|CONFIRMED|Important|Important|-|reproduced from git: the paste, plot, Compare and mismatch button entries sit in HEAD's ## 0.11.0 (CHANGELOG.md:345,356,371,389) and in none of git show v0.11.0:CHANGELOG.md; v0.11.0 holds no ComparePage.tsx; PRs #61, #63, #64, #65 merged 2026-09-24 to 2026-09-27, after the tag (2026-09-24 06:45)
4|I8|CONFIRMED|Important|Minor|-|confirmed with a correction: empty-vocabulary (registered, info) occurs 0 times in CHANGELOG.md, 39f77bab relaxed five schemas, the Shared files (#67, #69, #71) and Files (#73) tabs have no entry; but the Unreleased from-elf bullet does name pyelftools as a new runtime dependency (CHANGELOG.md:26-27); lowered: nothing is released and the omissions cost an upgrader nothing (an info check, a schema that now loads what it refused, the preview's tabs)
4|I9|CONFIRMED|Important|Minor|-|confirmed as text: SPEC names ddd gui twice and nothing on what it writes, refuses or undoes; lowered: the SPEC itself calls it a preview outside the interface (2136-2137), as the design decided (6.12), so no reader relies on an unspecified promise; what it costs is a contract for reviews, the maintainer's call
4|I10|CONFIRMED|Important|Important|-|confirmed: README says it is the short version at 1,058 lines, and the suite asserts every check, command and common key is in it; the volatile account is told at all eight places named; the parted copies are real: M2, M3 and M11 below each confirmed
4|M1|CONFIRMED|Minor|Minor|-|reproduced: sphinx-build -W passes with 0 warnings and builds no py-modindex.html; index.html links it; the one broken internal target of 30 pages
4|M2|CONFIRMED|Minor|Minor|-|confirmed as text: DWARF row says DDD does not read it while ddd generate a2l --image reads it; the other four name --address-map alone, and faq.rst:564 keeps address zero silently beside the address-missing warning it shows at :517
4|M3|CONFIRMED|Minor|Minor|-|confirmed as text: the tutorial says the only runtime dependencies are pydantic and jinja2 and the wheel carries everything apart from those two; requirements.txt and README add pyelftools; the developer page's dev-build recipe installs the two and --no-deps; no page gives an offline recipe
4|M4|CONFIRMED|Minor|Minor|-|confirmed as text: the page checks a component with -W missing-producer=ignore and three unknown-* overrides and never names --standalone (its one standalone at :438 is the word); consistency_checks.rst:220 calls naming the overrides by hand the mistake the flag exists to end
4|M5|CONFIRMED|Minor|Minor|-|reproduced in process: a KeyboardInterrupt in GuiServer.serve_forever through cli.main ends ddd gui at exit 0, where the same interrupt in ddd check's analysis ends at 130 (control), against the page's exit code is the same everywhere and 130 for Ctrl-C; lsp's 0 or 1 is in the SPEC alone
4|M6|CONFIRMED|Minor|Minor|-|confirmed with a correction: the site's sample files on five format pages carry a $schema line and plugins.rst:276 says to point it at the schemas, and SCHEMA_DIRECTORY has its row; what is README-only is that the loader allows and ignores the key, the per-file relative path and the commit-or-build choice; editor_integration.rst has no $schema
4|M7|CONFIRMED|Minor|Minor|-|confirmed as text: two integrations are shipped, cmake and the docker image; concept.rst says DDD can be driven from make or a batch file and the sources page says its list can be pasted into a makefile, and no page assembles a make recipe
4|M8|CONFIRMED|Minor|Minor|-|confirmed with a correction: the tutorial ends at generated files and Where to go next names concept, templates, the file formats and the command line, not the build, the editor or the GUI; but components/controller.c is named, in the build page's CMake snippet (:147), while no page shows hand-written C reading a curve, a member or an enum
4|M9|CONFIRMED|Minor|Minor|-|confirmed as text: no upgrade page; the pieces are scattered; templates.rst says nothing refers back to the copy taken, while the example template now renders the section attribute a copy taken before sections would not
4|M10|CONFIRMED|Minor|Minor|-|confirmed as text: Neovim, Helix and Emacs need only the command, with no filetype pattern or snippet; announced as log messages says not where; no page answers why no squiggle appears
4|M11|CONFIRMED|Minor|Minor|-|confirmed as text: SPEC 7.2 and both READMEs rename an object, a type or a constant; the editor page and the server also rename a unit (_rename_unit), a section and a raster, and offer unknown-unit's two fixes
4|M12|CONFIRMED|Minor|Minor|-|confirmed: SPEC says today 8, DICTIONARY_FORMAT = 9 and a dump says 9; KNOWN holds, filed by the paused 2026-09-24 review (SCRATCH/pass-1-2026-09-24.md, its I1) and not fixed since
4|M13|CONFIRMED|Minor|Minor|-|confirmed as text: the public interface is listed without the plugin api, while plugins.rst promises a field can be added without breaking a plugin written against the previous version
4|M14|CONFIRMED|Minor|Minor|-|confirmed: ten example directories and gui/ have no README
4|M15|CONFIRMED|Minor|Minor|-|confirmed: the glossary has no LSP, A2ML or EPK row, and neither it nor concept.rst's Vocabulary section has a term the GUI's sentences use (plan, revision, stale, Apply)
4|M16|CONFIRMED|Minor|Minor|-|confirmed as text: PLANTUML_JAR, JAVA and schemas.mjs's DDD are on no page; BROWSER only as a test fixture; the security page asks for a browser profile of its own and says not how
4|M17|CONFIRMED|Minor|Minor|-|confirmed as text: the sections are a threat model, the bullet at 47-106 is 935 words by my count, and the reader's own steps (paste rather than click at 136-138, a profile of its own at 237, the reused-code line) are spread through it
4|M18|CONFIRMED|Minor|Minor|-|confirmed as text: each quoted history and defence sentence is at the line cited
4|M19|CONFIRMED|Minor|Minor|-|measured: templates.rst argues in four sections to :86 and starts Getting started at :449 of 507; generated_artefacts.rst 1,374 lines; data_contracts.html 2,441,477 bytes, 49 % of the built pages
4|M20|CONFIRMED|Minor|Minor|-|confirmed: of 32 records 14 state no status and 12 say to be planned, not implemented or not yet planned of merged work; pages and code cite records the sdist excludes; KNOWN as a regression in kind: 2026-09-16-review-fixes.md:172 fixed the four lines 2026-09-15 named, and the staleness regrew in later records
```
