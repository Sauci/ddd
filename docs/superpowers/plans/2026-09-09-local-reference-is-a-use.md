# A reference into another component's local object is a use - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A curve, map or axis produced by one component that refers to an object another component declared `local` is reported as `local-conflict`, because section 2.1 says another component must not use a local object, and binding a curve to a private axis is a use.

**Architecture:** One check beside the reference validation in `_Analysis._absent`: once `_refuse_reference` has found the target present and of the right kind, the target's owner is compared with the referrer's producing component; a `local` owner in another component is `local-conflict` at the reference key, with a note at the local declaration. Nothing is dropped: as for two declarations, the finding is the ownership violation and the object still resolves.

**Tech Stack:** Python 3.12, pytest (`run_analysis`, `checks`, `messages` from `tests/conftest.py`).

**Spec:** The review's open question 1 (pass 1) and pass 3 Important 10 in `docs/superpowers/reviews/2026-09-08-complete-review.md` on branch `review/complete-review-2026-09-08`; `SPEC.md` section 2.1 (the `local` row) and section 4 (`local-conflict`).

## Global Constraints

- Branch: `fix/local-reference-is-a-use`, off `master` once the tier-1 stack has merged. Push after every task. Do not open a pull request.
- Run this checkout only (`python -m pytest tests/test_analysis.py -k <name> --no-cov`; the full `python -m pytest` with 100% coverage, ruff check, ruff format check and mypy strict from the scratchpad venv `C:/Users/lmbsog0/AppData/Local/Temp/claude/C--git-ac11-ddd/ab815568-8224-42f5-b802-44dd98973875/scratchpad/venv` before the last commit; only the environmental failures known on this machine are allowed).
- Commit messages: a lowercase sentence, no prefix, trailer `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Docstrings say why; British spelling; ` - ` not em dashes.

---

### Task 1: The check

**Files:**
- Modify: `src/ddd/analysis.py` (`_absent`'s reference loop; a new method `_check_local_reference`)
- Test: `tests/test_analysis.py` (new class `TestLocalReferences`)

**Interfaces:**
- Produces: `_Analysis._check_local_reference(definition: DataObject, key: str, target: str, reference: DeclarationRef, owners: dict[str, DeclarationRef | None]) -> None`.

- [ ] **Step 1: Write the failing tests**

```python
class TestLocalReferences:
    """A local object may not be used by another component, and a reference is a use.

    A curve of B bound to an axis A declared local compiles, links and reaches the a2l bound
    to A's private axis; nothing said so, because only declarations were compared.
    """

    def test_a_curve_over_another_components_local_axis_is_a_conflict(self, tree: Path) -> None:
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("local", "Ax", "uint16", kind="axis", size=4)),
                "b.ddd.json": component("B", declare("output", "Gain", "uint16", kind="curve", axis="Ax")),
            },
            severities=["local-conflict=warning"],
        )
        assert dictionary is not None
        assert checks(bag) == ["local-conflict", "unused-output"]
        rendered = messages(bag)
        assert "'Ax' is local to component 'A' but is also used as the axis of 'Gain' by component 'B'" in rendered
        assert "b.ddd.json#component.interface[0].definition.axis" in rendered
        assert "declared local here" in rendered
        assert [entry.name for entry in dictionary.objects] == ["Ax", "Gain"]

    def test_a_curve_over_its_own_components_local_axis_is_fine(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    declare("local", "Ax", "uint16", kind="axis", size=4),
                    declare("local", "Gain", "uint16", kind="curve", axis="Ax"),
                ),
            },
        )
        assert checks(bag) == []

    def test_an_axis_over_another_components_local_measurement_is_a_conflict(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("local", "M", "uint16")),
                "b.ddd.json": component("B", declare("local", "Ax", "uint16", kind="axis", size=4, input="M")),
            },
        )
        assert checks(bag) == ["local-conflict"]
        assert "'M' is local to component 'A' but is also used as the input of 'Ax' by component 'B'" in messages(bag)

    def test_a_reference_to_another_components_output_is_still_fine(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Ax", "uint16", kind="axis", size=4)),
                "b.ddd.json": component("B", declare("local", "Gain", "uint16", kind="curve", axis="Ax")),
            },
        )
        assert checks(bag) == ["unused-output"]

    def test_declaring_and_referring_are_two_uses(self, tree: Path) -> None:
        # B declares A's local object as its input and binds a curve to it: the declaration
        # is one use and the reference another, each reported where it is written, as
        # unknown-reference reports every reference rather than the first.
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("local", "Ax", "uint16", kind="axis", size=4)),
                "b.ddd.json": component(
                    "B",
                    declare("input", "Ax", "uint16", kind="axis", size=4),
                    declare("local", "Gain", "uint16", kind="curve", axis="Ax"),
                ),
            },
        )
        assert checks(bag) == ["local-conflict", "local-conflict"]
        rendered = messages(bag)
        assert "b.ddd.json#component.interface[0]" in rendered
        assert "b.ddd.json#component.interface[1].definition.axis" in rendered
```

(`unused-output` fires for an `output` nobody reads; keep it in the expectations. The message is deliberately parallel to the existing `local-conflict` message in `_select_producer` - "'X' is local to component 'A' but is also declared as input by component 'B'" - and carries the same note. The check also runs when the target's owner was dropped: a reference to a dropped local object is still a use. Check the sort order the bag applies before pinning the order of `checks(bag)`; if findings are ordered by location, the two `local-conflict` findings of the last test come in file order.)

- [ ] **Step 2: Run to see them fail** (`python -m pytest tests/test_analysis.py -k TestLocalReferences --no-cov`): the two conflict tests fail with no `local-conflict`.

- [ ] **Step 3: Implement.** In `_absent`'s reference loop, after `refused = self._refuse_reference(...)`, when `refused is None` call `self._check_local_reference(definition, key, target, reference, owners)`:

```python
    def _check_local_reference(
        self,
        definition: DataObject,
        key: str,
        target: str,
        reference: DeclarationRef,
        owners: dict[str, DeclarationRef | None],
    ) -> None:
        """A reference into another component's local object is a use, and is refused as one.

        Section 2.1 promises that a local object is used by nobody else; comparing
        declarations alone kept that promise only for declarations. A curve of one component
        bound to an axis another declared local compiles, links and reaches the a2l bound to
        that private axis, which is exactly the coupling the scope forbids. Reported where the
        reference is written, with a note at the local declaration, and nothing is dropped:
        as between two declarations, the finding is the ownership violation, not a missing
        object.
        """
        owner = owners.get(target)
        if owner is None or owner.scope is not Scope.LOCAL:
            return
        if owner.component_name == reference.component_name:
            return
        self._bag.add(
            "local-conflict",
            f"'{target}' is local to component '{owner.component_name}' but is also used as "
            f"the {key} of '{definition.name}' by component '{reference.component_name}'",
            reference.location(f"definition.{key}"),
            notes=[("declared local here", owner.location())],
        )
```

`reference` is `owners[name] or refs[0]`, so a referrer without a producer is judged by its first declaring component; say so in a comment.

- [ ] **Step 4: Run the tests, then the full suite, ruff, mypy.** Update any existing test whose `checks(bag)` now carries a `local-conflict` (search the suite for a cross-component reference to a `local` object; `examples/` are checked by the transcripts test: run `tests/test_transcripts.py` and `tests/test_documentation.py` too).

- [ ] **Step 5: Commit and push:** `refuse a reference into another component's local object as the use it is`.

---

### Task 2: The specification, the checks page, the README row and the changelog

- [ ] `SPEC.md` 2.1, the `local` row: "another component **must not** use it, by a declaration or by a reference (`local-conflict`)". Section 4, the `local-conflict` entry: "a component local object is declared by another component as well, or is referred to - as an axis, an `x_axis`, a `y_axis` or an `input` - by an object another component produces; the finding sits at the reference, with a note at the local declaration, and the object is not dropped." Also remove the review's open question if the spec carries any "left open" wording about it (it does not; skip).
- [ ] `docs/consistency_checks.rst`, the `local-conflict` row and the prose paragraph around line 789 ("**local-conflict.** ``Scratch`` is ``local`` to ``ComponentA``..."): add one sentence on references.
- [ ] `README.md:487`: already "a component local variable is used by another component"; leave.
- [ ] `CHANGELOG.md`, under `## Unreleased`: "**A reference into another component's local object is a use.** A curve, map or axis produced by one component that named an axis or a measurement another component declared `local` was accepted, and the generated a2l bound it to that private object. It is now `local-conflict`, at the reference, with a note at the local declaration; the object is not dropped."
- [ ] Verification: `tests/test_documentation.py`, `tests/test_transcripts.py`, the full suite, ruff format check. Commit: `say that a reference is a use of a local object`.
