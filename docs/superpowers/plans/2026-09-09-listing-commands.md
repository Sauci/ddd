# Listing commands and the enum double report - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `ddd sources` reports its findings in text mode as it does in json; `ddd checks` says which checks need every component and which belong to a comparison; an enum reordering is one `enum-conflict`, not a `definition-mismatch` with an empty message beside it.

**Architecture:** Three small changes in `src/ddd/cli.py` and `src/ddd/analysis.py`, each with its test, plus the spec and page sentences that follow.

**Tech Stack:** Python 3.12, pytest.

**Spec:** `docs/superpowers/reviews/2026-09-08-complete-review.md` (branch `review/complete-review-2026-09-08`): pass 5 Important 2 and 4, pass 3 Important 2 and 8. `SPEC.md` section 7 (`ddd sources`, `ddd checks`), section 4 (`enum-conflict`, `definition-mismatch`).

## Global Constraints

- Branch: `fix/listing-commands`, off `master` once the previous branches have merged. Push after every task. Do not open a pull request.
- Run this checkout only; the full `python -m pytest` with 100% branch coverage, ruff check, ruff format check and mypy strict from the scratchpad venv before the last commit; only the environmental failures known on this machine are allowed. `tests/test_transcripts.py` pins the documented outputs of `ddd sources` and `ddd checks`: run it, and update the pages where the output changes deliberately.
- Every behaviour change gets a `CHANGELOG.md` bullet; the `ddd checks` json fields are public interface and go into `SPEC.md` section 7.
- Commit messages: a lowercase sentence, no prefix, trailer `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

---

### Task 1: `ddd sources` reports its findings in text mode

- [ ] Test first (`tests/test_cli.py`): a project whose second include does not exist: `ddd sources` prints the paths on stdout, `error[file-not-found]` on stderr, exit 0; `--format json` unchanged.
- [ ] Implement: `_command_sources` text mode calls `_report(bag, "text")` after the listing (the exit code stays 0 unless the root cannot be read). `SPEC.md` section 7: `ddd sources` "reports its findings and exits 0 whatever they are; 1 only when the root cannot be read". `docs/command_line_interface.rst` says the same. Commit: `let ddd sources say what it found beside what it listed`.

### Task 2: `ddd checks` says which checks need every component

- [ ] Test first: `ddd checks --format json` entries carry `needs_every_component` and `comparison` booleans; the text form marks a whole-project check `(project)` and a comparison check `(comparison)` beside `(fixed)`; the set marked `(project)` equals `STANDALONE_POLICY`'s.
- [ ] Implement in `_command_checks` (`CheckInfo` already carries `needs_every_component`; add `comparison` to `CheckInfo` if absent, set for the 4.1 checks in the registry). `SPEC.md` section 7 (`ddd checks`) names the two fields and markers; `docs/command_line_interface.rst` and `docs/consistency_checks.rst` ("the registry itself is machine readable") too; `docs/build_integration.rst:56-58`'s claim becomes true. Update the transcript pages that show `ddd checks` output. Commit: `let ddd checks print which checks need the whole project`.

### Task 3: An enum reordering is one finding

- [ ] Test first (`tests/test_analysis.py`): two declarations of one object with the same enumerators in a different order: `checks(bag) == ["enum-conflict"]`; two with different enumerator values: `["enum-conflict"]` as well (today both also carry a `definition-mismatch` whose message prints identical text on both sides); a declaration under an enum against one under a linear conversion: `definition-mismatch` alone.
- [ ] Implement: `_conversion_value` returns `("enum", conversion.name)` for an `EnumConversion` (the enumerators are `enum-conflict`'s business); check `tests/test_analysis.py:330-339` and `tests/test_compare.py` for expectations that change. `SPEC.md` section 4 `definition-mismatch`: "conversion, compared by kind and parameters, an enum by its name (`enum-conflict` compares the enumerators)". Commit: `compare an enum conversion by its name, and leave the enumerators to enum-conflict`.

### Task 4: Changelog and verification

- [ ] Three bullets; full verification. Commit: `record the listing and enum changes`.
