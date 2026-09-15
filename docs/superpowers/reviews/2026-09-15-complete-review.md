# Complete review of DDD, 2026-09-15

A whole-tool review before the official release, run as a sequence of independent passes,
each by one reviewer reading the material fresh, followed by a verification of every finding
by a second reviewer and a sweep for what the passes missed. It follows the review of
2026-09-08 (branch `review/complete-review-2026-09-08`), whose findings were fixed in two
tiers between 2026-09-08 and 2026-09-10; each pass here records the status of that review's
findings in its area, so that what is still open is listed once, here.

The passes, in order:

1. `SPEC.md` on its own: contradictions, gaps, ambiguities, requirement words, undefined
   terms, and the sentences the features since 0.9.0 added.
2. File formats: `SPEC.md` section 3.1 to 3.10 against the published schemas, the pydantic
   models, the loader and the file format documentation.
3. Consistency checks and comparison: `SPEC.md` section 4 against `analysis.py`,
   `compare.py`, `identity.py`, `diagnostics.py` and their documentation.
4. Generated artefacts, address information and the dictionary: `SPEC.md` sections 5 and 6
   against `ir.py`, the backends, `build_info.py`, the shipped templates and their
   documentation; the generated c compiled under the CI flag set.
5. Tool interface: `SPEC.md` sections 3.11, 7 and 7.1 against `cli.py`, `plugins.py`,
   `Ddd.cmake`, the pre-commit hook and their documentation.
6. Editor integration: `SPEC.md` section 7.2 against the language server, the extension and
   their documentation, with the server's code reviewed line by line.
7. The remaining documentation and the repository: getting started, concept, FAQ, data
   contracts, developer documentation, README, CHANGELOG, examples, docker, CI, packaging
   and release readiness.
8. Code review of the core, part A: `models/`, `loading.py`, `diagnostics.py`, `identity.py`.
9. Code review of the core, part B: `analysis.py`, `ir.py`, `compare.py`.
10. Code review of the periphery: `cli.py`, `plugins.py`, the backends, `build_info.py`, the
    cmake module.
11. The test suite: what it pins, what it leaves open, and how it would fail.

After the passes, every Critical, Important and Minor finding was handed to a verifier that
had not written it, with the verdict CONFIRMED (trigger and outcome reproduced or read off
the line), PLAUSIBLE (the mechanism is real, the trigger uncertain) or REFUTED (the code does
not say that, or a guard elsewhere catches it); refuted candidates are listed at the end of
each pass so that the next review does not raise them again. Two sweeps then read the code
and the documents again with the verified list in hand, looking only for what was missed.

Line numbers refer to master at `6e9e99f` unless a pass says otherwise.

**Status: in progress.** Passes are appended as they complete and pushed; the summary is
written last.

## Baseline

On master at `6e9e99f`, Windows 11, Python 3.13, the project's own venv:

- `python -m pytest`: 2284 passed, 1 failed, coverage 100.00 % of lines and branches, in
  2 min 22 s. The failure is
  `tests/test_lsp.py::TestSymlinkedWorkspace::test_a_document_opened_through_a_symlink_is_covered_by_its_build`,
  which needs a Windows privilege the shell does not hold; the same test passes in CI.
- `ruff check .`, `ruff format --check .` (81 files), `mypy` (strict, 46 source files):
  clean.
- `sphinx-build -W --keep-going -b html docs`: clean, with graphviz and plantuml available.

## Summary

To be written when every pass, the verification and the sweeps are done.
