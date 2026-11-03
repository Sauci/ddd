## Baseline

On master at `2b4bae6c`, Windows 11, Python 3.13, the review tree's own venv, from Git Bash:

- `python -m pytest`: 7,042 tests collected, three failures, coverage 100.00 % of lines and branches
  (14,908 statements, 4,184 branches). The failures are all of this machine, none of them fails in CI:
  - `tests/test_lsp.py::TestSymlinkedWorkspace::test_a_document_opened_through_a_symlink_is_covered_by_its_build`
    needs the Windows symlink privilege, which this shell does not hold. Known since 2026-09.
  - `tests/test_gui_api.py::TestEdit::test_the_longest_name_a_file_can_be_created_under_is_written` and
    `tests/test_gui_api.py::TestCreatingAFile::test_the_longest_name_a_file_can_be_created_under_is_planned_and_written`
    answer `500 unwritable`, because this machine runs with `LongPathsEnabled = 0`, stock Windows, and the
    temporary directory plus a name of 244 bytes passes 260 characters. New since the last review, and
    a small finding in its own right: the limit the GUI states counts the name, not the path, and the
    suite is not green on a stock Windows machine.
- `ruff check .`, `ruff format --check .` (170 files), `mypy` (strict, 91 source files): clean.
- `gui/`: `npm run schemas`, `lint` (biome, 224 files, one info), `typecheck`, `test` (Vitest, 38 files,
  959 tests, 100 % statements/branches/functions/lines over `src/api`, `src/lib`, `src/state`), `build`: clean.
- `npm run e2e` with the installed Edge (`PLAYWRIGHT_CHANNEL=msedge`), against a real `ddd gui`: 294 journeys
  passed in 13 minutes; `mapped.spec.ts` stays out of the run without `DDD_MAPPED_DRIVE`, as documented.
