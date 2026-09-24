## Baseline

On master at `faee81e`, Windows 11, Python 3.13, the worktree's own venv, from Git Bash:

- `python -m pytest`: all passed but one, coverage 100.00 % of lines and branches (10543
  statements, 2848 branches), in 5 min 23 s. The failure is the known
  `tests/test_lsp.py::TestSymlinkedWorkspace::test_a_document_opened_through_a_symlink_is_covered_by_its_build`
  (Windows symlink privilege); it passes in CI.
- `ruff check .`, `ruff format --check .` (122 files), `mypy` (strict, 68 source files): clean.
- `gui/`: `npm run schemas`, `lint` (biome, 133 files, one info), `typecheck`, `test` (Vitest, 19
  files, 358 tests, 100 % statements/branches/functions/lines), `build`: clean. Without
  `npm run schemas` first, `typecheck` fails on three implicit `any` in `src/stories/fixtures.ts`
  (the generated types are absent); CI runs `schemas` first, so this is only a local trap.
