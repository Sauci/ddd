## Pass 17: code review of the core, part A

`SCRATCH` is `C:/Users/lmbsog0/AppData/Local/Temp/claude/C--git-ac11-ddd/8681cf0d-d41d-4120-88ca-b1b2c3615be8/scratchpad`.
Every script and transcript named below lies under `SCRATCH/pass-17/`. Line numbers are on the review tree.

### Scope covered

- **Read in full, with line numbers:** `src/ddd/models/__init__.py` 1-164, `common.py` 1-419, `component.py` 1-167, `constants.py` 1-115, `conversion.py` 1-444, `objects.py` 1-993, `project.py` 1-78, `rasters.py` 1-151, `reserved.py` 1-77, `schema.py` 1-250, `sections.py` 1-95, `types.py` 1-561, `units.py` 1-95; `src/ddd/loading.py` 1-1608; `src/ddd/diagnostics.py` 1-590; `src/ddd/names.py` 1-58; `src/ddd/pointers.py` 1-29; `src/ddd/file_names.py` 1-111.
- **Read for how the scope is used:** `src/ddd/analysis.py` 205-235, 960-1030, 2620-2700, 3325-3400, 3675-3692; `src/ddd/plugins.py` 105-130, 180-337; `src/ddd/deliveries.py` 120-175; `src/ddd/cli.py` 100-170, 1190-1300, 1950-2000; `src/ddd/backends/base.py` 340-372; `src/ddd/elf.py` 55-80; `src/ddd/variable_keys.py` 176-262; `src/ddd/declaration_plans.py` 108-128, 230-296; `SPEC.md` 186-290; the previous review's pass 8; `docs/superpowers/plans/2026-09-16-review-fixes.md` "Left open"; the open items of all 31 plans, by keyword; pass 6 in full and the candidates of passes 1 to 16.
- **Ran:**
  - `fuzz_core.py`, random schema-valid projects with odd combinations (unknown types, constants of every value, wrong reference kinds, enums past `int`, every conversion on every datatype) under random `-W`, through `check`, `dump`, `list`, `generate a2l`, `generate c --force`, `compare`, `check --standalone`: 5,400 projects, about 43,000 runs in process (`fuzz_core_2.txt`, `fuzz_core_3.txt`).
  - `pointer_fuzz.py`, 30,000 mutated descriptions from `examples/`, each finding's pointer walked through the document (`pointer_fuzz.txt`).
  - `fuzz_dump.py`, 3,000 mutated dumps through `compare` (`fuzz_dump.txt`).
  - `order_dep.py`, every example project with its includes expanded and permuted, dumps and a2l compared (`order_dep.txt`).
  - `time_load.py`, `time_load2.py`, the loader and the analysis on the four generated shapes at 100,000 declarations (`profile_large.txt`, `profile_chain.txt`); `bigarrays.py`, arrays at the documented cap (`bigarrays.txt`); `meaningful.py`, `mapping_key.py`, broken large files (`meaningful.txt`, `mapping_key.txt`).
  - `suspects1.py` to `suspects4.py`, `lsp_digits.py`, `lsp_deep2.py`, `status0915.py`, `last_checks.py`, `small_facts.py`, `devices.py`; `plug/p17plugin.py`, a pytest plugin recording every hash of a data object and every ordering of a `Location` over `test_loading`, `test_compare`, `test_models`, `test_edge_cases`, `test_hardening`, `test_analysis`, `test_cli`, `test_plugins`, `test_gui_session` (all green). `mypy --strict` and `ruff` over the scope: clean.
- **Not covered:** python 3.12 and 3.14, which this machine does not have (M5 rests on python's documentation for 3.12); a real out-of-memory run; another operating system. Whether a CI log parser acts on a forged line (M4) was not tried. No mutation testing: pass 21.
- **Met again and cited rather than re-filed, with what the inside adds:**
  - pass 6 M1, M2, M3, M4, M7, M10: confirmed at the lines the pass names; nothing to add.
  - pass 6 M5: its surrogate half has a cause and a further effect, my M3.
  - pass 8 M8 (`float64` under a factor above 1): every position answers with the `not finite` finding, producer, consumer, consumers alone, member, scalar type, `float32`, `uint64` at `1e308` and an offset overflowing the sum. `Limits(min=inf)` at `objects.py:711` and `types.py:228` would be a pydantic error out of the analysis, and no path reaches it (`suspects2.txt`). The guard holds.
  - pass 8 M1, pass 7 M8, pass 5 M16, M17, pass 7 M10: read at the lines; nothing to add.
  - pass 10 I13, pass 14 M7: my M2 is one more trigger of each.
  - pass 8 I2: my M9 is its other half.
- **Met on the way, for pass 19, not filed:** one `generate` in about 10,000 here failed with `cannot write '.../.ddd-manifest.json': Access is denied`, a file written a few milliseconds earlier and re-replaced with no retry (`backends/base.py:370`; `fuzz_core_3.txt`, `cases/fuzz_kept/000/argv.txt`). `plugins.py:113`, `:124` use `.match` on a pattern ending in `$`, so a plugin named `"layout\n"` passes (`small_facts.txt`). The text report prints each finding to unbuffered stderr: at 125,000 findings `ddd check` took 54 s against 16 s with `--format json`, measured while a fuzz was running, and the rendering itself 4.4 s.

### Strengths

- **No traceback from any input the schema admits.** About 43,000 CLI runs over 5,400 odd projects under random relaxations: zero tracebacks, and the one exit 2 is the manifest above. 3,000 mutated dumps: zero. Every `assert` in the scope (`objects.py:374`, `:655`, `:709`, `types.py:220-221`, `:300`, `rasters.py:113`) held. This is the result I most expected to break.
- **The pointer machinery is right.** Of 39,483 findings on 30,000 mutated descriptions, 27,916 resolve exactly and 8,517 end one key short at a key that is missing. Of the remaining 3,050, 3,048 are keys I injected with `.` or `[n]` in them and 2 are `units[i].unit`, both M7. Zero exceptions in the reporting path. `_place` (`loading.py:1509-1546`) fixed the two Important findings it was written for (`status0915.txt`).
- **On a valid project the loader is linear and small.** 100,000 declarations: 3.3 s in 3,333 files, 2.3 s in 30 files, 2.6 s mixed, against 6 to 8 s of analysis. 50,000 files: 27 s (31 s under the profiler, 11.5 s of it Windows' `realpath`, about 230 µs a file), and nothing grows with the square. `_locations` is the largest step of the loader's own code, about a fifth of the load at 30 files, and harmless. Arrays are about 2 µs per element to the 10,000,000 cap.
- **Meaning does not depend on include order.** Permuted includes of all example projects: the dump's meaning is identical every time, and the a2l differs only in the order of its lines (`order_dep.txt`).
- **The hash machinery hides no cliff.** Nothing but an explicit test hashes a model or a workspace (`plug/p17plugin.py.out`).
- **Patterns are matched carefully.** Every use of a `$` pattern against unvalidated text is `fullmatch` (`rasters.py:48`, `cli.py:168`, `:1385`, `lsp/navigation.py:780`, `:826`, `:849`), `plugins.py:113` above apart, and pydantic's engine reads `$` as the end of the text.
- **The last review's findings here are fixed,** down to the small ones: 16 of 21 plainly, 5 with the remainders below.

### Issues

#### Critical

None.

#### Important

None. The earlier passes found the formats sound from the outside; from the inside I find the same.

#### Minor

- **M1. A file whose definitions all fail one of the models' own rules takes quadratic time in the filter that tidies the findings.** `src/ddd/loading.py:1383`. `explained_by_a_deeper_finding` walks every place for every error whose input holds something (`:1388`), and an `after` validator's error has the whole object as its input. Trigger: one component of N definitions stating `"datatype": "uint8"` and no `conversion`, so N `schema` findings: whole `ddd check` 1.7 s at 4,000, 6.0 s at 8,000, 22.5 s at 16,000 (`meaningful.txt`). In process at 16,000: validation 0.13 s, `_place` 0.04 s, `_meaningful` 17.95 s; the same count of missing `volatile`, whose type returns early at `:1386`, 0.016 s (`last_checks.txt`). At the square, about twelve minutes at 100,000 in one file. It needs a generated component broken whole at once, which is what a release tightening a rule does, and how `conversion` became required (`622561a0`). The language server and `ddd gui` pay it on each analysis until the file is fixed. Reproduced. Build the set of every proper prefix of every place once, and ask it; S.

- **M2. An unknown key holding a long bracketed number ends `ddd check` in python's advice, with no finding, and ends `ddd lsp`.** `src/ddd/diagnostics.py:310` `int(p)`, `src/ddd/pointers.py:21` `int(index)`: both read `\d+` unbounded, and `int()` refuses past 4300 digits. Trigger: `{"component": {"name": "A", "interface": [], "x[1...1]": 1}}` at 4301 digits -> `ddd: Exceeds the limit (4300 digits) for integer string conversion ... use sys.set_int_max_str_digits()`, exit 2, and nothing on stdout under `--format json`; at 4300 digits an ordinary located `schema` finding, exit 1 (`last_checks.txt`, `suspects1.txt`). `textDocument/didOpen` on the file: `ddd lsp` exits 2 (`lsp_digits.txt`). `src/ddd/graph.py:170` reads the same pointer (read off). Against `loading.py:1264` "Every failure has to come back as a located finding"; `rasters.py:36-38` calls this very sentence "python's advice to a programmer". The edit engine guards itself (`editing.py:91` `_LONG_INDEX`), so the rule exists once, in a client. Reproduced. `\d{1,18}` in both patterns, a longer run being text; S.

- **M3. `_write_utf8` throws away stderr's `backslashreplace`, so a finding quoting a lone surrogate ends `ddd check` with exit 2 and no findings (adds to pass 6 M5).** `src/ddd/cli.py:118`. `reconfigure(encoding="utf-8")` resets `errors` to `strict`: stderr `backslashreplace` before, `strict` after; stdout `surrogateescape` before, `strict` after (`reconfigure.txt`). Python's own default would have printed `\ud800`. Pass 6 M5 has `ddd check` clean on such a file; that holds only until a finding quotes the text. Triggers: `"unit": "\ud800"` in a project with a units file (`unknown-unit`); a duplicated key spelled `"\ud800"`; an include naming one, the most ordinary finding there is -> `ddd: 'utf-8' codec can't encode character '\ud800' ...`, exit 2, where `--format json` gives the finding and exit 1 (`suspects3.txt` q2, q8; `suspects4.txt`). `tests/test_gui_queries.py:489` pins this escape for the GUI's sentence. Reproduced. `errors="backslashreplace"` on stderr; pass 6 M5's refusal at the parser ends it as well (open question 3); S.

- **M4. Free text reaches the text report raw, so one finding can print as two and escape codes reach the terminal.** `src/ddd/diagnostics.py:335`, `:405`; `src/ddd/loading.py:181`, `:1331`. `(got: ...)` goes through `repr`; the pointer, a quoted unit and a quoted include do not. Against `docs/consistency_checks.rst:69` "Every finding is one line, in a shape an editor or a log parser can pick apart" and `docs/command_line_interface.rst:15`. Triggers: an unknown key `"a\nb: error[fake]: forged"` -> a line ending `#component.a`, and a second reading `b: error[fake]: forged: error[schema]: ...`; a unit holding `\n` and `\u001b[31m`, and an include holding the same (`suspects3.txt` q3, q4, q9; `suspects4.txt`). The ELF reader takes care of exactly this (`src/ddd/elf.py:61`, pinned by `tests/test_cli.py:4216`, whose subject is `.c\x1b[2K`), so the decision exists for one source of text. Cosmetic under the stated trust, a description being able to run a plugin anyway; a log parser would read the forged line. Reproduced. Escape control characters once, at render, leaving the json as it is; S.

- **M5. An include ending in `**` means two things, by python version.** `src/ddd/loading.py:1432`; `SPEC.md:273` "`**` matches directories recursively"; `docs/file_formats/project.rst:100`; `pyproject.toml:14` `>=3.12`; `.github/workflows/ci.yml:46` runs 3.12, 3.13, 3.14. Trigger: `"includes": ["components/**"]` -> on 3.13.17 both files under it, exit 0, against the spec's sentence (`starstar.txt`). On 3.12 `Path.glob` yields directories alone, by python's own note ("Changed in version 3.13: Globbing with a pattern that ends with "**" returns both files and directories. In previous versions, only directories were returned"), so `match.is_file()` at `:1442` leaves nothing and the same project is `include-empty`, an error. `components/**.ddd.json` reads as `*.ddd.json` on 3.13; 3.12's pathlib, as I remember it, refuses a partial `**` (not run). No test uses such a pattern. 3.13 half reproduced; 3.12 half from the documentation, since this machine has no 3.12. See open question 1; S.

- **M6. An interface nothing calls, a field nothing reads, and an ordering that would raise.** `src/ddd/models/conversion.py:39`, `:98`, `:128`, `:239`, `:267` `to_raw`; `:32` `ConversionRule`; `:295` `IDENTITY`; `src/ddd/loading.py:195`, `:218` `parents`, threaded through `:769`, `:995`, `:1016`, `:1188`; `src/ddd/diagnostics.py:313` `order=True`. No caller in `src/ddd` for any of them; tests alone read them (`tests/test_models.py:155`, `:427`, `tests/test_edge_cases.py:193-196`, `tests/test_loading.py:59`) (`dead.txt`), and that is how a 100 % gate keeps them. The module's opening sentence, `conversion.py:3-4`, says each variant answers the same three questions; nobody asks the second. `Location`'s generated ordering is never used over nine test modules (`plug/p17plugin.py.out`) and raises where it would be: `sorted([Location(p, "x", 3, 1), Location(p, "x")])` -> `TypeError`, `None` against `int` (`small_facts.txt`): a `json-syntax` location carries a line and every other location none. Reproduced. Remove them, or state them as plugin api (open question 2); S.

- **M7. Two kinds of finding still point at a place the file does not have (remainder of P8-M14).** `src/ddd/loading.py:1531`, `src/ddd/models/units.py:53`, `src/ddd/models/common.py:64-69`; `docs/file_formats/index.rst:77-78`. (a) `"units": [""]` -> `units[0].unit`: the shorthand is rewritten to `{"unit": ""}` before validation, as an enumerator mapping is, and `_mapping_key` handles that one alone; the file holds a string there (`pointer_fuzz.txt`). (b) A refused block key: `"extensions": {"c[1]": {}, "a.b": {}}` -> `...extensions.c[1]`, `...extensions.a.b`, which `pointers.segments` reads as an index and as two keys, where `common.py:64-69` says the pattern keeps such a key out of the pointer (`status0915.txt`, m14). Any unknown key so spelled does the same. Editors fall back to the parent, so the cost is a wider underline. Reproduced. Stop the walk at a scalar where the model read an object, and correct the sentence; S.

- **M8. Small untrue sentences.** Each reproduced or read off.
  - `src/ddd/loading.py:62-64`: a tree too deep is "most often a project that includes a sibling which includes it back under a second spelling of one path". Identity is the resolved path, so that is `include-cycle` at once (`spelling.txt`); only a real chain reaches the cap.
  - `src/ddd/models/objects.py:69-73`: the integer arm is listed first "so that an out of range whole number is reported against that bound". `within_64_bits` (`:62`) answers before any arm: `Value error, does not fit 64 bits` (`initbound.txt`).
  - `src/ddd/loading.py:613-615`: "every other problem is reported through `bag`". A plugin's model raising leaves as `PluginError` through `:1163`, by design at `plugins.py:325-327` (read off).

- **M9. The names no file can be created under are not asked of the files DDD generates (adds to pass 8 I2).** `src/ddd/file_names.py:1-7`, `:32-36`; `SPEC.md` 3.2 "it becomes the name of a generated header". A component or a project named `NUL`, `CON`, `AUX`, `COM1` or `LPT1` passes `ddd check --strict`, and `ddd generate all` reports `wrote out/NUL.h`, `wrote out/CON.a2l` (`devices.txt`). On this Windows 11 those are plain files, so the module's "opening it opens the device" is untrue here, and "on any system" with it. On a Windows that still reads them as the module says, the header is lost with exit 0 and `#include "NUL.h"` reads nothing; not reproducible here. Its docstring's reason, "a project is checked out on more than one system", is as good for a header as for a description. Rare. First half reproduced, second read off. Ask `device_named` of a component's and a project's name beside `name-collision`, and soften the sentence; S.

- **M10. `ddd sources` lists in the order the platform compares paths (KNOWN, `plans/2026-09-16-review-fixes.md`, "Left open").** `src/ddd/loading.py:498`; `SPEC.md:2124`. On Windows `_under, alpha, Beta, p, Zeta`, where the same files load `Beta, Zeta, under, alpha` (`last_checks.txt`). Nothing generated depends on it. Still open; one line, `key=Path.as_posix`.

### Status of the 2026-09-15 findings in this area

Checked against the tree, by run or at the line. Plainly fixed: P8-I2, P8-I3 (`loading.py:1509-1546`), P8-M2 (`reserved.py:39`), P8-M3 (`common.py:153`), P8-M4 (`loading.py:1502`), P8-M5, P8-M6, P8-M7, P8-M8 (`deliveries.py:134`, `:150`), P8-M9 (`--version` 0.146 s against 0.048 s for python alone), P8-M10 (`rasters.py:41`), P8-M11 (`loading.py:1549`), P8-M12 (`conversion.py:146-164`), P8-M13, P8-M15 (`loading.py:1466`), P8-M16 (`common.py:131`). All in `status0915.txt`, `last_checks.txt`.

| id | finding | status | where |
| --- | --- | --- | --- |
| P8-I1 | a file 500 levels deep ends `ddd id --assign` and the server | FIXED as a crash. The server stays up, its finding at 0:0 from about 500 levels (`lsp_deep2.txt`). `ddd id --assign` at 520 says `not readable as json, skipped`, exit 1, of a file `ddd check` reads clean (`status0915.txt`): untrue, and rare | `identity.py`, pass 18 |
| P8-M1 | a condition ending in a backslash | FIXED (`component.py:82`); its trigraph is pass 6 M6 | |
| P8-M14 | an extension key with `.` or `[n]` | PARTLY: refused now, and the refusal itself still carries that pointer | M7 |
| P8-M17 | `MemoryError` on a read | FIXED for the read (`loading.py:1300`); the parse at `:119-128` has no such clause. Read off, not provoked, and a file that is not json fails at its first byte | |
| P8-M18 | `assign` rewrites in place | FIXED; the staging that replaced it has its own findings | pass 13 C2, I5 |
| P7 design note 3 | strict by default | STILL OPEN, KNOWN, decision 10 | pass 6 M10 |

### Open questions

1. **What does a trailing `**` mean (M5)?** "Directories", as SPEC says: `x/**` then reaches no file on any python, and 3.13's reading must be filtered out. "Everything under", as 3.13 does: normalise `x/**` to `x/**/*` on every python and change the sentence, at the price of sweeping non-DDD files into `file-extension`. Either way one branch in `expand_include` and a test on the matrix.
2. **Is the conversion interface public (M6)?** Whether a plugin may call `to_raw` or lean on `ConversionRule` is pass 4 M13's open point. If yes, document it. If no, five methods, a Protocol and a constant go, with the tests that read them.
3. **Is a lone surrogate refused at the parser (pass 6 M5's proposal)?** If yes, M3's stream handler is a belt and the check gains a finding, with a migration for nobody. If no, the handler is the fix, and `ddd list`, `dump` and `generate` still need their own answer.

### Test gaps

- Nothing holds `_meaningful` to linear (M1): a bound on 20,000 errors would have caught it.
- `tests/test_hardening.py:1316-1324` and `tests/test_pointers.py:20` pin ordinary indices and superscripts; no run of digits past python's limit (M2).
- Nothing tests `_write_utf8`, or a lone surrogate in a finding through `ddd check`; `tests/test_gui_queries.py:489` is the GUI's sentence (M3).
- Control characters in the text report are pinned for the ELF reader alone, `tests/test_cli.py:4216` (M4). The sentence "one line per finding" has no test.
- No test uses an include ending in `**` or holding a partial one, on a matrix of three pythons that differ on both (M5).
- `tests/test_models.py:155`, `:427`, `tests/test_edge_cases.py:193-196`, `tests/test_loading.py:59` pin code nothing runs (M6).
- Across the suite, `units[0].unit` appears as a pointer only for a file spelling that key (`tests/test_lsp.py:2178`); the shorthand's location is not pinned (M7).
- No test asks what happens to a component named after a device (M9).

### Assessment

This is careful code, and from the inside I find what pass 6 found from the outside: the models, the loader and the diagnostics are sound. I went looking for a branch that does the wrong thing, an unguarded impossible input and a cliff, with three fuzzers and about 76,000 hostile documents and runs, and the result is no traceback from a description and no wrong pointer beyond two small classes. The loader is linear and cheap on valid input, the assertions hold, the numeric guards reach every position, and the last review's three Important findings here are fixed. What is left is real and small: one quadratic filter on a file broken whole, one unbounded `int()`, one stream handler reset by accident, control characters in a report promised to be one line per finding, and a wildcard that means two things on two supported pythons. The code's prose is the weakest part: it states absolutes ("every", "never", "on any system") that are nearly true, and M6 shows a 100 % gate keeping alive what nothing calls. I would fix M1 to M5 in an afternoon and leave the structure of these modules as it is.

```candidates
17|M1|src/ddd/loading.py:1383|A file whose definitions all fail a model's rule is quadratic in the findings filter: 22.5 s at 16,000, 18 s of it in _meaningful, about twelve minutes at 100,000
17|M2|src/ddd/diagnostics.py:310|An unknown key holding a bracketed run past 4300 digits: ddd check exit 2 with python's advice and no finding, ddd lsp exits on didOpen; pointers.py:21 the same
17|M3|src/ddd/cli.py:118|_write_utf8 resets stderr's backslashreplace to strict: a finding quoting a lone surrogate ends ddd check with exit 2 and no findings (adds to pass 6 M5)
17|M4|src/ddd/diagnostics.py:405|Free text reaches the text report raw: a newline in a key or unit forges a finding line, escape codes reach the terminal, against one line per finding; the ELF reader escapes them
17|M5|src/ddd/loading.py:1432|An include ending in ** reads every file on 3.13 and nothing on 3.12, include-empty, against SPEC's matches directories; no test on a matrix of three pythons
17|M6|src/ddd/models/conversion.py:39|Nothing calls to_raw, ConversionRule, IDENTITY or parents, tests alone keep them; Location order=True is unused and raises on a None line
17|M7|src/ddd/loading.py:1531|Findings pointing at what the file lacks: units[0].unit on a bare string, extensions.c[1] on a refused key, against common.py:64 (remainder of P8-M14)
17|M8|src/ddd/loading.py:62|Small untrue sentences: a second spelling reaching the depth cap, the arm order of init, every other problem reported through bag
17|M9|src/ddd/file_names.py:32|A component or project named NUL, CON, AUX passes --strict and writes NUL.h; plain files on Windows 11 against the docstring, lost on a Windows reading them as devices (adds to pass 8 I2)
17|M10|src/ddd/loading.py:498|ddd sources lists in the platform's path order, case insensitive on Windows, where components load by code point (KNOWN, 2026-09-16 left open)
```
