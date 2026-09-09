# Core robustness - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** No input a user could write, however absurd, makes `ddd` exit with a Python traceback: huge integers, deep JSON, deep include trees, deep structure nesting and arrays of structures beyond any sensible size all become located findings, and a scalar type is checked where it is declared rather than once per declaration naming it.

**Architecture:** Bounds in the contracts (pydantic `Field(ge=..., le=...)`) where a value has a range DDD could never store; `RecursionError` caught at the three JSON readers that lacked it; an include-depth cap and a structure-nesting cap reported as findings before the recursive walks run, and a leaf-count cap before an array of structures is flattened; the pointer sort keyed on the regex's own groups; scalar-type checks moved to `_check_types`.

**Tech Stack:** Python 3.12, pydantic v2, pytest.

**Spec:** `docs/superpowers/reviews/2026-09-08-complete-review.md` (branch `review/complete-review-2026-09-08`), pass 7 Important 2, 3, 4, 5, 7, 8 and Minor 5. `SPEC.md` sections 3.1 (includes), 3.3 (numbers), 3.7 (types), 4.

## Global Constraints

- Branch: `fix/core-robustness`, off `master` once the tier-1 stack and `fix/local-reference-is-a-use` have merged. Push after every task. Do not open a pull request.
- Run this checkout only; the full `python -m pytest` with 100% branch coverage, ruff check, ruff format check and mypy strict from the scratchpad venv (`.../scratchpad/venv/Scripts/python.exe`) before the last commit; only the environmental failures known on this machine are allowed.
- A new check identifier is public interface: it needs the registry entry (`src/ddd/diagnostics.py`), the `SPEC.md` section 4 entry, a `docs/consistency_checks.rst` row, a `README.md` table row and a changelog line; `tests/test_documentation.py` enforces the first three.
- Limits chosen here are contract decisions the maintainer may revisit; each is stated once in `SPEC.md` and named in the final report: include depth 64; structure nesting 64; 100 000 leaves per array of structures; 10 000 000 elements per plain array; integers within 64 bits.
- Every behaviour change gets a `CHANGELOG.md` bullet under `## Unreleased`.
- Commit messages: a lowercase sentence, no prefix, trailer `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Docstrings say why; British spelling; ` - ` not em dashes.

---

### Task 1: Integers beyond the float range are findings, not `OverflowError`

**Files:** `src/ddd/models/common.py` (`Number`), `src/ddd/models/conversion.py` (`Enumerator.value`), `src/ddd/models/constants.py` (`ConstantDeclaration.value`), `src/ddd/models/objects.py` (`Dimension`'s integer arm), `schemas/*.json` (regenerated), tests in `tests/test_models.py`.

- [ ] Tests first: a `limits` `max` of 400 digits on a definition and on a structure member, an enumerator value of `10**400` on a definition, a member and a scalar type, a constant of `10**400`, a dimension of `10**400`: each is a `schema` finding at the key, never a traceback (`run_analysis` returns a bag with `schema` and `dictionary is None`). Keep the existing behaviour for `2**64` and `-(2**63)` (accepted where the datatype allows; `init-invalid`/`limits-out-of-range` where it does not).
- [ ] Implement: `Number = Annotated[int, Field(ge=-(2**63), le=2**64 - 1)] | Real` (no `strict=True` on the int arm: strictness is a separate, deferred change with its own migration note); `Enumerator.value: Annotated[int, Field(strict=True, ge=-(2**63), le=2**64 - 1)]`; `ConstantDeclaration.value` and the integer arm of `Dimension` gain `le=2**64 - 1`; then `grep -n "int" src/ddd/models/*.py` for every other integer-valued field a description can state (an `init` value, a bit width, a `size`, an address, a `format` version, ...) and bound each the same way, listing them in the report - the spec sentence below claims every integer. The message pydantic writes for `le` names the bound; if it is unreadable ("Input should be less than or equal to 18446744073709551615"), add a `field_validator` whose message says "does not fit 64 bits". Regenerate the published schemas: `PYTHONPATH=src python -m ddd schema all -o schemas` (the test `tests/test_documentation.py` compares them).
- [ ] `SPEC.md` 3.3 (the paragraph on `init` and limits) gains: "Every integer a description states - an initial value, a limit, an enumerator's value, a constant, a dimension - fits 64 bits; a larger one is `schema` where it is written, because no datatype could hold it." Commit: `refuse an integer no datatype could hold where it is written`.

### Task 2: Deep JSON is a finding at every reader

**Files:** `src/ddd/loading.py` (`_dictionary_format_is_supported`, `load_dictionary`), `src/ddd/cli.py` (`_holds_a_description`), `src/ddd/lsp/ranges.py` (`Document.__init__`), `src/ddd/identity.py` (the JSON read of `assign`), tests in `tests/test_hardening.py` and `tests/test_lsp.py`.

- [ ] Tests first: a 100 000-deep JSON document given as a `ddd compare` baseline and candidate (both sides) is `json-syntax` "nested too deeply to read", exit 1, no traceback; the same document under `ddd id --assign` is reported "not readable as json, skipped", exit 1; `Document(text)` on it has `data is None` and answers nothing; a non-UTF-8 file as a compare candidate is `json-syntax` at the file, not a usage error.
- [ ] Implement, with the smallest change at each reader rather than a shared helper (`_read_json` already carries the full handling): `_dictionary_format_is_supported` catches `RecursionError` beside `ValueError` and, since such a document cannot be validated either, reports `json-syntax` "nested too deeply to read" at the path and returns False (check first whether `DataDictionary.model_validate_json` raises `RecursionError` or a `ValidationError` on the deep document, and handle whichever it is in `load_dictionary`); `_holds_a_description` catches `(OSError, ValueError, RecursionError, UnicodeDecodeError)`; `Document.__init__` catches `RecursionError` beside `ValueError`; `identity.assign`'s reader catches `RecursionError` where it catches `json.JSONDecodeError`. Commit: `read every json document through one reader that cannot raise a traceback`.

### Task 3: Include depth and structure nesting are capped with findings

**Files:** `src/ddd/loading.py` (`_load_include`), `src/ddd/analysis.py` (`_check_types`), `src/ddd/diagnostics.py` (new `include-depth`), `SPEC.md` 3.1, 3.7 and section 4, `docs/consistency_checks.rst`, `README.md`, tests in `tests/test_loading.py` and `tests/test_structures.py`.

- [ ] Tests first: 65 nested project includes is `include-depth` at the include entry that crosses the cap, the run continues without that subtree, no traceback at 500 levels; a chain of 65 nested structures is `schema` at the 65th type ("nests 65 levels deep; DDD reads at most 64"), every type of the chain is poisoned, a variable of the outermost is dropped with the usual `incomplete-project` when silenced (not applicable: `schema` is fixed), and 500 levels raise nothing.
- [ ] Implement: `_load_include` refuses when `len(stack) >= 64` (`include-depth`, fixed severity error, `needs_every_component=False`); in `_check_types`, before the cycle walk, compute each structure's nesting depth with an explicit stack (a cycle counts as infinite and is left to `type-cycle`), poison a type whose depth exceeds 64 with `_Cause("schema", True, entry.location())` after reporting `schema` at it, and make `_nesting_cycle`, `_poison_of`, `_type_alignment`, `_reaches_external`, `_nested_types` walks not descend into a poisoned type (check each: some already stop at poisoned names). Registry entry: `_check("include-depth", Severity.ERROR, "a project includes sub-projects more than 64 levels deep", overridable=False)`. Spec 3.1: "Includes nest at most 64 levels; a deeper tree is `include-depth` at the entry that crosses the limit." Spec 3.7: "A structure nests at most 64 levels; a deeper one is `schema` at the type that crosses the limit." Section 4 gains the `include-depth` entry among the fixed checks. Docs and README rows. Commit: `cap the include tree and the structure nesting where python would give up`.

### Task 4: Arrays are capped before they are flattened or broadcast

**Files:** `src/ddd/analysis.py` (`_build_instance` before `_flatten`; `_resolve_shape` or `_check_declaration` for plain arrays), `SPEC.md` 3.3 and 3.7, tests in `tests/test_structures.py` and `tests/test_analysis.py`.

- [ ] Tests first: a structure of 2 members with `dimensions: [100000, 1000]` is `schema` at `definition.dimensions` ("would contribute 200000000 leaves; DDD carries at most 100000") and the instance is dropped; a plain `uint8` array `[1000000000]` with a scalar `init` is `schema` at `definition.dimensions` ("has 1000000000 elements; DDD carries at most 10000000"); `[64][64]` of a 20-member structure (81 920 leaves) is accepted; `ddd generate c` on the capped project writes nothing and exits 1 rather than hanging.
- [ ] Implement: in `_absent`'s seeds or in `_collect_component` after the shape resolves (the earliest point where the numeric shape and the type are known), compute `math.prod(shape)` for a plain object against `_MAX_ELEMENTS = 10_000_000` and `math.prod(shape) * leaves_of(structure)` for an instance against `_MAX_LEAVES = 100_000` (count leaves iteratively over the structure with nested arrays multiplied in), and refuse through `_refuse("schema", ...)` so the drop is recorded like any other. Spec 3.3: "An array holds at most 10 000 000 elements"; 3.7: "an array of structures contributes at most 100 000 leaves"; both "because the dictionary, the A2L and the generated code carry every element". Commit: `refuse an array or an array of structures larger than anything the outputs could carry`.

### Task 5: The pointer sort survives any key

**Files:** `src/ddd/diagnostics.py` (`_pointer_order`), tests in `tests/test_hardening.py`.

- [ ] Test first: a component file whose top-level key is `"²"` yields one `schema` finding printed by `ddd check` (exit 1), not a usage error; `_pointer_order("a[10].b")` still sorts after `a[2].b`.
- [ ] Implement: `parts = re.split(r"\[(\d+)\]", pointer)`; `tuple((False, int(p)) if i % 2 else (True, p) for i, p in enumerate(parts) if p)`. Commit: `sort a pointer by the indices the regex captured, not by what looks like a digit`.

### Task 6: A scalar type is checked where it is declared

**Files:** `src/ddd/analysis.py` (`_check_types`, `_check_declaration`, `_check_limits`, `_register_enum`), tests in `tests/test_types.py`.

- [ ] Tests first: a scalar type `Pct_t` (`uint8`, limits `[0, 300]`) named by two components yields one `limits-out-of-range` at `types.ddd.json#types[0].limits` and none at the declarations; a scalar type with an enum whose enumerator is a reserved identifier yields `reserved-identifier` at the type's `conversion`; a scalar type nobody names is still checked; a declaration naming a scalar type still gets its own `init-invalid` when its `init` is out of the type's range (the init is the declaration's).
- [ ] Implement: in `_check_types`, for a `ScalarType` entry run the limits check (`_check_limits` with the entry's location) and register its enum (`_register_enum` at `entry.location("conversion")`), using the member helpers' pattern (`_check_member_limits`, `_register_member_enums`); in `_check_declaration`, skip `_check_limits` and the enum registration when `ref.resolved is not None` (the definition was filled from a type); keep `_check_init`. Commit: `check a scalar type once, where it is declared`.

### Task 7: Changelog and the final verification

- [ ] `CHANGELOG.md`: one bullet per task above, in the file's style, the limits named. Full verification. Commit: `record the robustness changes and the limits they introduce`.
