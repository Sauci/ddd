# Plugin boundary - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A plugin can no longer break the tool by accident: a module using a dataclass under `from __future__ import annotations` imports; a backend cannot alias or escape the output directory; a hook calling `sys.exit` is a plugin error, not a clean run; a factory returning the wrong thing and a template raising a non-jinja exception are usage errors; and a generation that fails part-way leaves the previous artefacts untouched.

**Architecture:** Five contained changes in `src/ddd/plugins.py` and `src/ddd/backends/base.py`: register the module before executing it; normalise every returned path and refuse one outside the output directory; catch `SystemExit` in `_call`; validate the factory's result and `generate`'s return; stage every file to a temporary name and rename them all at the end.

**Tech Stack:** Python 3.12, importlib, jinja2, pytest.

**Spec:** `docs/superpowers/reviews/2026-09-08-complete-review.md` (branch `review/complete-review-2026-09-08`), pass 8 Important 1, 2, 3, 5, 6 and Minor 7. `SPEC.md` 3.11.

## Global Constraints

- Branch: `fix/plugin-boundary`, off `master` once the previous branches have merged. Push after every task. Do not open a pull request.
- Run this checkout only; the full `python -m pytest` with 100% branch coverage, ruff check, ruff format check and mypy strict from the scratchpad venv (`.../scratchpad/venv/Scripts/python.exe`) before the last commit; only the environmental failures known on this machine are allowed.
- The exit codes stay: usage errors are 2, findings 1. No new exit code.
- Every behaviour change gets a `CHANGELOG.md` bullet under `## Unreleased`; `docs/plugins.rst` and `SPEC.md` 3.11 say what a plugin may rely on.
- Commit messages: a lowercase sentence, no prefix, trailer `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Docstrings say why; British spelling; ` - ` not em dashes.

---

### Task 1: A plugin module is registered before it runs

**Files:** `src/ddd/plugins.py` (`_load_from_path`), tests in `tests/test_plugins.py`.

- [ ] Test first: a plugin file beginning `from __future__ import annotations` with a `@dataclass class Cfg: n: int = 1` and `PLUGIN = Plugin(name="dc")` loads (`ddd check` on a project naming it reports no `plugin-invalid`); a plugin whose module body raises is still `plugin-invalid` and `sys.modules` does not keep it (a second load retries and reports again).
- [ ] Implement the importlib recipe: `sys.modules[name] = module` before `exec_module`, `sys.modules.pop(name, None)` in the `except`. Commit: `register a plugin module before running it, as importlib does`.

### Task 2: A backend's paths are normalised and stay inside the output directory

**Files:** `src/ddd/backends/base.py` (`render`), `src/ddd/plugins.py` (`_GuardedBackend.generate`), tests in `tests/test_backends.py` and `tests/test_plugins.py`.

- [ ] Tests first: a plugin backend returning `output_dir / "sub" / ".." / "ddd_globals.h"` is refused as the path the c backend claims ("two artefacts claim ..."), exit 2, nothing written; one returning `Path("ddd_globals.c")` (relative) is resolved against the output directory and refused the same way; one returning `output_dir.parent / "escape.h"` is a usage error naming the plugin and the path ("writes outside the output directory"), exit 2, nothing written; a backend returning `output_dir / "sub" / "x.h"` still works.
- [ ] Implement: in `render`, for every `GeneratedFile`, `path = (output_dir / file.path).resolve()` when relative, else `file.path.resolve()`; refuse if `output_dir.resolve()` is not among its parents; compare claims on the resolved path; write the resolved path. Commit: `keep a backend's files inside the output directory, and compare their paths as paths`.

### Task 3: `sys.exit` in a hook is the plugin's error

**Files:** `src/ddd/plugins.py` (`_call`), `src/ddd/lsp/diagnostics.py` (the `PluginError` catch already there), tests in `tests/test_plugins.py` and `tests/test_lsp.py`.

- [ ] Tests first: a `check` hook calling `sys.exit(0)` makes `ddd check` print the run's findings and `ddd: plugin 'x' failed in its check hook: SystemExit(0)` (or the exit's message), exit 2; the language server reports `plugin-invalid` at the project file and keeps running; `KeyboardInterrupt` in a hook still interrupts (a unit test calling `_call` directly).
- [ ] Implement: `except (Exception, SystemExit) as error:` in `_call`, with the message naming the exit code when the error carries one. Commit: `treat a hook that exits the interpreter as a hook that raised`.

### Task 4: A factory's result and a template's exception are usage errors

**Files:** `src/ddd/plugins.py` (`backend_of`, `_GuardedBackend.generate`), `src/ddd/backends/base.py` (`render_template`), tests in `tests/test_plugins.py` and `tests/test_backends.py`.

- [ ] Tests first: a `backend` hook returning `None` is `ddd: plugin 'x' returned no backend from its backend hook` (exit 2); a `generate` returning a string is `ddd: plugin 'x' returned something other than a list of generated files from its generate hook`; a template containing `{{ 1 / 0 }}` is `ddd: cannot render template 'ddd_globals.c.jinja2', line N: division by zero` (exit 2), and one with `{{ model.groups | length + 'x' }}` likewise names the template; none of the four is a traceback.
- [ ] Implement: `backend_of` checks the result has a `str` `name` and a callable `generate` (the runtime-checkable `Backend` protocol if one exists, else the two attributes), else `PluginError`; `_GuardedBackend.generate` checks the returned value is a list whose items are `GeneratedFile`; `render_template` catches `Exception` beside `TemplateError` and routes it through `describe_template_error` (the line from the traceback, the exception's own text as the reason). Commit: `turn what a factory returns and what a template raises into usage errors`.

### Task 5: Generation writes all or nothing

**Files:** `src/ddd/backends/base.py` (`write`), `src/ddd/cli.py` (the write-failure message, if it changes), tests in `tests/test_generation.py` and `tests/test_cli.py`.

- [ ] Tests first: with `out/ddd_globals.h` a directory, `ddd generate c` writes nothing (no `ddd_globals.c` appears, no `*.tmp` remains) and names `ddd_globals.h` in its message, exit 2; an unchanged rerender still reports `unchanged` and leaves the mtime alone; `--dry-run` still creates nothing.
- [ ] Implement: `write` first decides each file's status (unchanged / created / updated) without writing; for the files to write, it writes `path.with_name(path.name + ".tmp")` for all, then renames each over its target (`os.replace`); on any `OSError` it removes the temporary files it created and re-raises with the failing path in `filename`. Windows: `os.replace` over an existing file works; a target that is a directory raises, which is the test. Commit: `write every generated file or none`.

### Task 6: The plugins page, the spec and the changelog

- [ ] `docs/plugins.rst`: a plugin is one module (a sibling import is not supported: the file is loaded by location, and the way to share code is a package the environment can import); a hook must return rather than exit; a backend's files stay inside the output directory and their names must not collide with a built-in artefact's; edits to a plugin take effect in the next process (already there; keep).
- [ ] `SPEC.md` 3.11: "A backend's files lie inside the output directory; one that names a path outside it, or a path another artefact writes, is a usage error before anything is written."
- [ ] `CHANGELOG.md`: one bullet per behaviour change. Full verification. Commit: `say what a plugin may rely on at its boundary`.
