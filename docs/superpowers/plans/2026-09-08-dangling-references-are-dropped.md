# A dangling reference drops the referring object - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A curve, map or axis whose reference names no object, or an object of the wrong kind, is dropped from the dictionary the way an object referring to a dropped declaration already is, so that relaxing `unknown-reference` or `reference-kind` can no longer put a curve into the C as a scalar or a dangling name into the A2L; when the finding is silenced, `incomplete-project` says what went.

**Architecture:** The reference validation moves from `_lookup` (called while shapes are resolved, after the set of resolved objects is fixed) into `_absent` (branch `fix/dropped-declarations-are-marked`), where absence is computed: a reference to a name that is not in `_effective` and not absent is `unknown-reference`, one to the wrong kind is `reference-kind`, and either drops the referrer with the same "explained" bookkeeping as a dropped declaration. `_resolve_shape` then only meets valid references and asserts so; the A2L backend's guard against a missing axis becomes unreachable and is removed.

**Tech Stack:** Python 3.12, pytest.

**Spec:** `docs/superpowers/reviews/2026-09-08-complete-review.md` (branch `review/complete-review-2026-09-08`): pass 3 Important 1, pass 4 Important 1 and answer (l). `SPEC.md` section 4, entry `unknown-reference`, `reference-kind` (1141-1144), and the `dropped as unresolvable` rule of 3.9 (884-886).

## Global Constraints

- Branch: `fix/dangling-references-are-dropped`, created **from `fix/dropped-declarations-are-marked`** (it needs `_absent`, `_dropped`, `_via` and `_report_absences`), never from `master`. Push after every task. Do not open a pull request; the final report says the pull request's base has to be `fix/dropped-declarations-are-marked` until that one merges.
- Run this checkout only; full `python -m pytest` with 100% coverage, ruff check, ruff format check and mypy (scratchpad venv `C:/Users/lmbsog0/AppData/Local/Temp/claude/C--git-ac11-ddd/ab815568-8224-42f5-b802-44dd98973875/scratchpad/venv`) before the last commit. The 12 environmental failures of the review baseline are known.
- Tests that pin the old behaviour (`tests/test_edge_cases.py::test_a_map_whose_axes_are_unknown_has_no_shape`, `::TestBackendEdges::test_a_curve_whose_axis_is_missing_is_left_out`, and whatever `tests/test_a2l.py:300-315` and `tests/test_calibration.py:227-282` assert about a kept referrer) are rewritten to the new rule, each rewrite named in the commit body.
- Commit messages: a lowercase sentence, no prefix, trailer `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

---

## File Structure

- Modify: `src/ddd/analysis.py` - `_absent` (reference validation), `_resolve_shape`, `_lookup` (removed or reduced to a lookup that cannot fail), `_report_absences` messages for a dangling reference.
- Modify: `src/ddd/backends/a2l/model.py:359-367` - remove the guard in `_characteristic`.
- Modify: `tests/test_analysis.py`, `tests/test_edge_cases.py`, `tests/test_a2l.py`, `tests/test_calibration.py`, `tests/test_generation.py` (or wherever the C output is asserted).
- Modify: `SPEC.md` section 4, `docs/consistency_checks.rst`, `README.md` row if its wording implies the object stays, `CHANGELOG.md`.

---

### Task 1: An unresolvable reference drops the referrer

**Files:**
- Modify: `src/ddd/analysis.py`
- Test: `tests/test_analysis.py`, `tests/test_edge_cases.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_analysis.py`, a new class:

```python
class TestDanglingReferences:
    """A reference nobody resolves takes the referring object down with it.

    A curve without its axis has no shape - it was generated as a scalar - and an axis
    naming an absent measurement would leave a dangling name in the a2l, which a calibration
    tool refuses whole. Both were kept, with an empty shape, whenever the finding was relaxed.
    """

    def test_a_curve_over_an_unknown_axis_is_dropped(self, tree: Path) -> None:
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "Gain", "uint16", kind="curve", axis="NoAxis")),
            },
            severities=["unknown-reference=warning"],
        )
        assert dictionary is not None
        assert checks(bag) == ["unknown-reference"]
        assert dictionary.objects == ()
        assert [d.name for c in dictionary.components for d in c.declarations] == []

    def test_an_axis_over_an_unknown_input_is_dropped(self, tree: Path) -> None:
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "Ax", "uint16", kind="axis", size=4, input="NoInput")),
            },
            severities=["unknown-reference=warning"],
        )
        assert dictionary is not None
        assert checks(bag) == ["unknown-reference"]
        assert dictionary.objects == ()

    def test_a_reference_of_the_wrong_kind_is_dropped(self, tree: Path) -> None:
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    declare("local", "NotAnAxis", "uint16"),
                    declare("local", "Gain", "uint16", kind="curve", axis="NotAnAxis"),
                ),
            },
            severities=["reference-kind=warning"],
        )
        assert dictionary is not None
        assert checks(bag) == ["reference-kind"]
        assert [entry.name for entry in dictionary.objects] == ["NotAnAxis"]

    def test_silencing_the_finding_says_what_went(self, tree: Path) -> None:
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "Gain", "uint16", kind="curve", axis="NoAxis")),
            },
            severities=["unknown-reference=ignore"],
        )
        assert dictionary is not None and dictionary.objects == ()
        assert checks(bag) == ["incomplete-project"]
        rendered = messages(bag)
        assert "'Gain' is not in the data dictionary" in rendered
        assert "unknown-reference" in rendered
        assert "a.ddd.json#component.interface[0].definition.axis" in rendered

    def test_a_map_over_one_known_and_one_unknown_axis_is_dropped(self, tree: Path) -> None:
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    declare("local", "Nx", "uint16", kind="axis", size=4),
                    declare("local", "M", "uint8", kind="map", x_axis="Nx", y_axis="Ny"),
                ),
            },
            severities=["unknown-reference=warning"],
        )
        assert dictionary is not None
        assert checks(bag) == ["unknown-reference"]
        assert [entry.name for entry in dictionary.objects] == ["Nx"]

    def test_a_curve_over_a_dropped_referrer_goes_with_it(self, tree: Path) -> None:
        """Transitive, like a dropped declaration: an axis whose input is unknown goes, and
        the curve over that axis goes with it, silently while the root is reported."""
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    declare("local", "Ax", "uint16", kind="axis", size=4, input="NoInput"),
                    declare("local", "Gain", "uint16", kind="curve", axis="Ax"),
                ),
            },
            severities=["unknown-reference=warning"],
        )
        assert dictionary is not None and dictionary.objects == ()
        assert checks(bag) == ["unknown-reference"]
```

Rewrite in `tests/test_edge_cases.py`:
- `test_a_map_whose_axes_are_unknown_has_no_shape` -> `test_a_map_whose_axes_are_unknown_is_dropped`: same fixture, assert `checks(bag) == ["unknown-reference", "unknown-reference"]` and `"M" not in dictionary.by_name` (read `DataDictionary.by_name` in `src/ddd/ir.py` to see whether it is a dict or a method).
- `TestBackendEdges::test_a_curve_whose_axis_is_missing_is_left_out`: keep the name and the assertion `model.characteristics == ()`, and change the docstring to "Dropped at analysis: a CURVE without its AXIS_DESCR would be an invalid file rather than a smaller one, so the object never reaches the backend." (the test now exercises that the backend receives no curve at all).

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_analysis.py -k TestDanglingReferences tests/test_edge_cases.py -k "unknown or missing" --no-cov -q`
Expected: the new tests fail with the objects present.

- [ ] **Step 3: Implement**

In `src/ddd/analysis.py`:

1. In `_absent`, between filling `_effective` and the transitive loop, validate every reference of every name that has an effective definition:

```python
        # A reference nobody resolves drops the referrer, for the reason a dropped referent
        # does: a curve without its axis has no shape, and an axis naming an absent
        # measurement would leave a dangling name in the a2l. Decided here, over the whole
        # census, so that the drop propagates like any other.
        for name, refs in ordered:
            if name in absent or name not in self._effective:
                continue
            definition = self._effective[name]
            reference = owners[name] or refs[0]
            for key, target in definition.references.items():
                if target in absent:
                    continue  # the transitive loop below takes it, silently or not
                found = self._effective.get(target)
                if found is None:
                    reported = self._bag.add(
                        "unknown-reference",
                        f"{definition.kind.value} '{name}' refers to '{target}' as its "
                        f"{key}, but no component declares '{target}'",
                        reference.location(f"definition.{key}"),
                    ) is not None
                elif found.kind is not _EXPECTED_KIND[key]:
                    reported = self._bag.add(
                        "reference-kind",
                        f"the {key} of {definition.kind.value} '{name}' must be of kind "
                        f"'{_EXPECTED_KIND[key].value}', but '{target}' is of kind "
                        f"'{found.kind.value}'",
                        reference.location(f"definition.{key}"),
                    ) is not None
                else:
                    continue
                absent[name] = reported
                self._via[name] = (key, target)
                if not reported:
                    self._dangling[name] = "unknown-reference" if found is None else "reference-kind"
                break
```

with, at module level, `_EXPECTED_KIND: Final = {"axis": ObjectKind.AXIS, "x_axis": ObjectKind.AXIS, "y_axis": ObjectKind.AXIS, "input": ObjectKind.MEASUREMENT}` (the keys `references` uses; confirm with `grep -n "def references" -A 12 src/ddd/models/objects.py`), and `self._dangling: dict[str, str] = {}` in `__init__` ("For a name absent because its own reference was refused and the refusal silenced, the check that was silenced").

Careful: a name with two references (a map) is checked reference by reference and dropped at the first bad one; the second bad reference of the same map is still reported (loop on without `break` for reporting, but set `absent` once). Adjust so that every bad reference is reported (both `unknown-reference` of `test_a_map_whose_axes_are_unknown_is_dropped`) while `absent[name]` is `True` if any of them was reported.

2. `_report_absences`: a name in `self._dangling` (its own reference was the root) gets the message `f"'{name}' is not in the data dictionary: its {key} '{target}' does not resolve, and the {check} that says why is not reported"` at `definition.{key}`; the existing dependent message ("did not resolve, and the finding that says why is not reported") stays for names dropped through another absent name.

3. `_resolve_shape`: replace the `_lookup` calls with direct reads of `self._effective[...]`, asserting the kind, and delete `_lookup`:

```python
        if isinstance(definition, Curve):
            axis = self._effective[definition.axis]
            assert isinstance(axis, Axis)  # validated in _absent
            return ((self._dimension_value(axis.size),), (axis.size,))
```

and the same for the two axes of a map; drop the `((), ())` fallbacks and the `input` lookup of an axis (its target was validated in `_absent`; nothing is needed from it here).

4. Remove from `src/ddd/backends/a2l/model.py:359-367` the guard `if any(name not in self._by_name for name in axes): return None` and its comment (unreachable now); `_characteristic` returns `CharacteristicView` unconditionally. Check `_axis_descr` and `_axis_pts`: `axis.references.get("input") or NO_INPUT_QUANTITY` stays (an axis without an input is legitimate).

- [ ] **Step 4: Run the tests, then everything**

Run: `python -m pytest tests/test_analysis.py tests/test_edge_cases.py tests/test_calibration.py tests/test_a2l.py tests/test_generation.py tests/test_backends.py --no-cov -q`, then the full `python -m pytest`.
Expected: all pass; coverage 100% (the removed guard and the removed `_lookup` branches no longer need covering; if `_kind_detail` in `src/ddd/backends/c/literals.py` shows an uncovered default branch, it was already covered by another test or is now dead - remove a dead default rather than adding a test for it).

- [ ] **Step 5: Commit and push**

```bash
git add src/ddd/analysis.py src/ddd/backends/a2l/model.py tests/test_analysis.py tests/test_edge_cases.py tests/test_a2l.py tests/test_calibration.py
git commit -m "drop a curve, map or axis whose reference does not resolve" -m "Relaxing unknown-reference generated the curve as a scalar and put a dangling input quantity into the a2l; the referrer is now dropped the way an object referring to a dropped declaration is, and incomplete-project says so when the finding is silenced." -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push -u origin fix/dangling-references-are-dropped
```

---

### Task 2: The specification, the checks page and the changelog

**Files:** `SPEC.md` section 4 (`unknown-reference`, `reference-kind`, 1141-1144), `docs/consistency_checks.rst` (rows 478-483), `README.md:508-509` if needed, `CHANGELOG.md`.

- [ ] **Step 1: SPEC.md.** Replace the entry with: "`unknown-reference`, `reference-kind`: a curve, map or axis refers to an object that does not exist or has the wrong kind. The referring object is dropped as unresolvable whatever severity the finding is given, because a curve without its axis has no shape and an axis naming an absent measurement would leave a dangling name in the A2L; `incomplete-project` says so when the finding is silenced. A reference to an object that was declared but dropped as unresolvable is not reported a second time: the finding at the declaration is the one to act on, and the referring object is dropped with it."

- [ ] **Step 2: docs/consistency_checks.rst and README.md.** Add the drop sentence to the two rows and to any prose paragraph about references (`grep -n "unknown-reference" docs/consistency_checks.rst`); the README rows (508-509) are accurate as they stand.

- [ ] **Step 3: CHANGELOG.md.** Under `## Unreleased`:

```
* **A dangling reference drops the referring object.**  With `unknown-reference` or
  `reference-kind` relaxed, a curve whose axis nobody declares was kept with an empty shape:
  the c backend declared it as a scalar and the a2l backend wrote an `AXIS_PTS` whose input
  quantity names a measurement that does not exist, a file a calibration tool refuses whole.
  The referring object is now dropped the way an object referring to a dropped declaration
  already was, transitively, and `incomplete-project` reports the absence when the finding is
  silenced.  **Migration:** a project relaxing either check gets a smaller artefact instead of
  an invalid one; nothing changes for a project where the checks are errors.
```

- [ ] **Step 4: Verification and commit**

Run `python -m pytest tests/test_documentation.py tests/test_transcripts.py --no-cov -q`, then the full `python -m pytest`, ruff check, ruff format check, mypy.

```bash
git add SPEC.md docs/consistency_checks.rst CHANGELOG.md
git commit -m "say that a dangling reference drops the referring object" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push
```
