# Dropped declarations are marked, not erased - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A declaration the analysis cannot resolve stays in the ownership census, so that `missing-producer` and `unused-output` stop accusing the other component, an object whose producer was dropped is left out whole, and `incomplete-project` is reported for every declaration the dictionary omits whose cause was silenced - a poisoned type, a dropped referent, a dropped producer.

**Architecture:** `_Analysis` in `src/ddd/analysis.py` gains a full census (`_census`, every non-duplicate declaration in load order) beside the census of resolved ones (`_refs`), and a record of which dropped declarations had their cause reported (`_dropped: dict[key, explained]`). Ownership is decided over the full census; an object whose owner was dropped, or none of whose declarations resolved, is absent; absence propagates over references as today; and every declaration left out for a silenced cause gets one `incomplete-project`. Poisoned types carry the cause that poisoned them so the same rule reaches a variable of such a type.

**Tech Stack:** Python 3.12, pydantic v2 models (read only here), pytest with the `run_analysis`/`checks`/`messages` helpers of `tests/conftest.py`.

**Spec:** `docs/superpowers/reviews/2026-09-08-complete-review.md` (branch `review/complete-review-2026-09-08`): pass 3 Critical 1, pass 7 Important 1, pass 7 Minor 5, pass 7 design note 1. `SPEC.md` section 4, entries `incomplete-project`, `missing-producer`, `unused-output`; section 2.1.

## Global Constraints

- Branch: `fix/dropped-declarations-are-marked`, off `master`. Push after every task. Do not open a pull request.
- Run this checkout only: `python -m pytest tests/test_analysis.py --no-cov -q` while developing; the full `python -m pytest` (100% branch coverage enforced) before the last commit; `<venv>/Scripts/python.exe -m ruff check .`, `-m ruff format --check .`, `-m mypy` clean (venv: `C:/Users/lmbsog0/AppData/Local/Temp/claude/C--git-ac11-ddd/ab815568-8224-42f5-b802-44dd98973875/scratchpad/venv`). The 12 environmental failures of the review baseline are known.
- Existing tests that pin the *old* behaviour (a `missing-producer` after a dropped producer, the message `'X' is not in the data dictionary`) are updated to the new one; every such update is named in the commit body. Tests pinning `checks(bag)` in insertion order may need reordering when `incomplete-project` moves from `_refuse` time to the end of the run - keep the pinned set, reorder as observed, do not weaken to `set()` unless the order is genuinely arbitrary.
- The `_Analysis.run` phase order matters (`_check_types` fills `_poisoned_types` before `_collect_component`; ownership before shapes); keep it, and say in a comment where a phase depends on an earlier one.
- Commit messages: a lowercase sentence, no prefix, trailer `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Docstrings say why; British spelling; ` - ` not em dashes.

---

## File Structure

- Modify: `src/ddd/analysis.py` - `DeclarationRef.key`, `_Cause`, `_poisoned_types` becomes `dict[str, _Cause]`, `_census`, `_dropped`, `_refuse`, `_drop_for_type`, `_collect_component`, `_select_producer` (unchanged body, wider input), `_check_unused` callers, `run`, `_unresolved` -> `_absent`, `_report_absences`.
- Modify: `tests/test_analysis.py` (new class `TestDroppedDeclarations`), `tests/test_constants.py` (messages), `tests/test_structures.py` / `tests/test_types.py` where expectations change.
- Modify: `SPEC.md` section 4 (`incomplete-project`, and the ownership sentence), `docs/consistency_checks.rst` (the three rows), `CHANGELOG.md`.

---

### Task 1: A dropped declaration still counts for ownership

**Files:**
- Modify: `src/ddd/analysis.py` (`DeclarationRef`, `_Analysis.__init__`, `_refuse`, `_collect_component`, `run`, `_build_variable`, `_build_instance`)
- Test: `tests/test_analysis.py`

**Interfaces:**
- Produces: `DeclarationRef.key -> tuple[str, int]` (component name, index). `_Analysis._census: dict[str, list[DeclarationRef]]` (every non-duplicate declaration, load order, dropped ones included). `_Analysis._dropped: dict[tuple[str, int], bool]` (dropped declaration -> a finding explaining the drop was reported). `_Analysis._refuse(check, message, location, ref, notes=()) -> None` (was `name: str`; now takes the ref).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_analysis.py` (imports `checks`, `component`, `declare`, `messages`, `project`, `run_analysis` from `conftest`; check the file's existing imports):

```python
class TestDroppedDeclarations:
    """A declaration that cannot resolve is still a declaration.

    Dropping one used to erase it from every census, so the ownership checks reasoned about
    a project in which it had never been written: a producer of an unknown type made every
    consumer a `missing-producer`, pointing at a file another team owns and telling them to
    add a producer that exists.
    """

    def test_a_dropped_producer_is_not_a_missing_producer(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "x", typename="Nope_t")),
                "b.ddd.json": component("B", declare("input", "x")),
            },
        )
        assert checks(bag) == ["unknown-type"], messages(bag)

    def test_a_dropped_consumer_is_not_an_unused_output(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "x", dimensions=[2])),
                "b.ddd.json": component("B", declare("input", "x", dimensions=["NOPE"])),
            },
        )
        assert checks(bag) == ["unknown-constant"], messages(bag)

    def test_an_object_whose_producer_was_dropped_is_left_out_whole(self, tree: Path) -> None:
        """The producer's declaration is the one that says what the object is; without it
        the consumers' copies describe nothing that has storage."""
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "x", typename="Nope_t")),
                "b.ddd.json": component("B", declare("input", "x")),
            },
            severities=["unknown-type=warning"],
        )
        assert dictionary is not None
        assert dictionary.objects == ()
        assert [d.name for c in dictionary.components for d in c.declarations] == []

    def test_two_dropped_producers_are_still_two_producers(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "x", typename="Nope_t")),
                "b.ddd.json": component("B", declare("output", "x", typename="Nope_t")),
            },
        )
        assert sorted(checks(bag)) == ["multiple-producers", "unknown-type", "unknown-type"]

    def test_a_second_declaration_of_a_dropped_name_is_a_duplicate(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A", declare("local", "X", typename="Nope_t"), declare("local", "X", "uint16")
                ),
            },
        )
        assert checks(bag) == ["unknown-type", "duplicate-declaration"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_analysis.py -k TestDroppedDeclarations --no-cov -q`
Expected: the first fails with `missing-producer` in the list, the second with `unused-output`, the third with `x` in `objects`, the fourth without `multiple-producers`, the fifth without `duplicate-declaration`.

- [ ] **Step 3: Implement**

In `src/ddd/analysis.py`:

1. `DeclarationRef`: add

```python
    @property
    def key(self) -> tuple[str, int]:
        """What identifies the declaration across the run: its component and its index."""
        return (self.component_name, self.index)
```

2. `_Analysis.__init__`: replace `self._dropped: set[str] = set()` and its docstring with

```python
        self._census: dict[str, list[DeclarationRef]] = defaultdict(list)
        """Every declaration that is not a duplicate, in load order, whether or not it resolved.

        What ownership is decided over. A declaration the analysis could not resolve is still
        a declaration: a consumer of an object whose producer names an unknown type is not
        reading something nobody produces, and an output whose only reader was dropped is
        not unread. Erasing dropped declarations from the census made both findings fire,
        each pointing at the file the mistake was not in."""
        self._dropped: dict[tuple[str, int], bool] = {}
        """The declarations that were dropped as unresolvable, and whether a finding said why.

        ``True`` when the cause was reported at whatever severity, ``False`` when it was
        silenced; the latter is what :meth:`_report_absences` turns into
        ``incomplete-project``, because an absence nothing mentions is the one way this tool
        is wrong without anybody being told."""
```

3. `_refuse`: change the parameter `name: str` to `ref: DeclarationRef`, and the body to

```python
        reported = self._bag.add(check, message, location, notes) is not None
        self._dropped[ref.key] = self._dropped.get(ref.key, False) or reported
        if reported:
            return
        self._bag.add(
            "incomplete-project",
            f"the declaration of '{ref.name}' by component '{ref.component_name}' is not in "
            f"the data dictionary: the {check} that says why is not reported, so nothing "
            f"reading the dictionary - the listing, the dump, every backend - carries it either",
            location,
        )
```

Update the four callers (`_shape_resolves` passes `ref` instead of `ref.name`; `_resolve_type` passes `ref` in its two `_refuse` calls; `_structure_fits` passes `ref`). In `_limits_stay_finite`, after the `schema` add (always reported, the check is fixed), record `self._dropped[ref.key] = True`.

4. `_collect_component`: replace the loop body with

```python
        seen: dict[str, DeclarationRef] = {}
        for index, declaration in enumerate(component.interface):
            original = DeclarationRef(loaded, index, declaration)
            previous = seen.get(original.name)
            if previous is not None:
                # Decided on the name alone, before resolution: a second copy of a name whose
                # first copy could not resolve is still a second copy.
                self._bag.add(
                    "duplicate-declaration",
                    f"component '{component.name}' declares '{original.name}' twice "
                    f"(as {previous.scope.value} and as {original.scope.value})",
                    original.location(),
                    notes=[("first declared here", previous.location())],
                )
                continue
            seen[original.name] = original
            self._census[original.name].append(original)
            ref = self._resolve_type(original)
            if ref is None:
                # Its datatype names nothing this project declares, or a type that was
                # refused, and the finding sits there. The declaration is dropped - every
                # later check would be reasoning about a value with no storage - but what
                # needs neither storage nor shape still runs: the name it takes, and the
                # claims a consumer may not make.
                assert original.key in self._dropped
                self._check_declared_name(original)
                continue
            if not self._shape_resolves(ref):
                # A dimension names a constant nobody declares, which is now reported. The
                # declaration is dropped the way one naming an unknown type is - an array
                # of no known length is storage nothing downstream can reason about - but
                # every check that does not need the resolved shape still runs: an init
                # outside the datatype is wrong whatever the shape turns out to be, and
                # silencing unknown-constant must not silence that.
                self._check_declaration(ref)
                continue
            self._refs[ref.name].append(ref)
            self._check_declaration(ref)
```

(`_resolve_type` returns `None` on five paths; after this task every one of them records the key in `_dropped`: the two `_refuse` calls, `_structure_fits`'s `_refuse`, `_limits_stay_finite`'s record, and the poisoned-type returns, which Task 2 handles - for now, in the two `if named in self._poisoned_types:` branches, add `self._dropped[ref.key] = True` with a `# Task 2 refines this` comment, so the assert holds.)

5. `run`: replace the block from `ordered = sorted(self._refs.items())` down to `shapes = {...}` with

```python
        ordered = sorted(self._refs.items())
        self._check_enumerator_collisions(ordered)
        self._check_type_name_collisions(ordered)
        self._check_constant_collisions(ordered)
        self._check_identity_collisions(ordered)

        # Ownership is decided over every declaration, dropped ones included, because the
        # producer owns the definition and a dropped producer is still the one that claimed
        # it. It has to be settled before anything that reads a definition - in particular
        # before curves and maps look up their axes.
        owners = {name: self._select_producer(name, refs) for name, refs in sorted(self._census.items())}
        absent = self._absent(ordered, owners)
        resolved = [(name, refs) for name, refs in ordered if name not in absent]
        shapes = {
            name: self._resolve_shape(self._effective[name], owners[name] or refs[0])
            for name, refs in resolved
        }
```

and replace `_unresolved` with

```python
    def _absent(
        self, ordered: list[tuple[str, list[DeclarationRef]]], owners: dict[str, DeclarationRef | None]
    ) -> dict[str, bool]:
        """The names that resolve to no object, each with whether a finding says why.

        Three ways in: every declaration of the name was dropped; the declaration that owns
        it was, in which case the consumers' copies describe storage nothing defines; or,
        transitively, it refers to an absent name - a curve over a dropped axis cannot
        resolve its shape, and an axis whose ``input`` is a dropped measurement would leave a
        dangling name in the a2l. The finding for the root sits at the root cause, and a
        referring object is dropped without one of its own - ``unknown-reference`` would
        claim that nobody declares the target, which is false. What every entry carries is
        whether that root finding was reported: an absence whose cause was silenced is what
        :meth:`_report_absences` says out loud.

        Fills ``_effective`` on the way, for exactly the names that have a definition to
        offer: the owner's, else the first surviving declaration's.
        """
        absent: dict[str, bool] = {}
        for name, drops in self._dropped_by_name().items():
            if name not in self._refs:
                absent[name] = any(drops.values())
        for name, refs in ordered:
            owner = owners[name]
            if owner is not None and owner.key in self._dropped:
                absent[name] = self._dropped[owner.key]
                continue
            self._effective[name] = (owner or refs[0]).definition
        settled = False
        while not settled:
            settled = True
            for name, definition in self._effective.items():
                if name in absent:
                    continue
                for target in definition.references.values():
                    if target in absent:
                        absent[name] = absent[target]
                        settled = False
                        break
        return absent

    def _dropped_by_name(self) -> dict[str, dict[tuple[str, int], bool]]:
        """The dropped declarations grouped by the name they declare."""
        grouped: dict[str, dict[tuple[str, int], bool]] = defaultdict(dict)
        for name, refs in self._census.items():
            for ref in refs:
                if ref.key in self._dropped:
                    grouped[name][ref.key] = self._dropped[ref.key]
        return grouped
```

Remove the line `self._effective = {name: (owners[name] or refs[0]).definition for name, refs in ordered}` from `run` (`_absent` fills `_effective` now). Everything after `shapes` in `run` stays; `owners[name]` for a resolved name is never a dropped ref (such names are absent), and `kept` stays as it is.

6. `_build_variable` and `_build_instance`: replace `[ref for ref in refs if ref.scope is Scope.INPUT]` in the `_check_unused` calls with `[ref for ref in self._census[name] if ref.scope is Scope.INPUT]` (in `_build_instance` the local variable `consumers` feeds only `_check_unused`; check with `sed -n '1871,1936p' src/ddd/analysis.py`).

- [ ] **Step 4: Run the tests**

Run: `python -m pytest tests/test_analysis.py tests/test_constants.py tests/test_structures.py tests/test_types.py tests/test_edge_cases.py --no-cov -q`
Expected: the five new tests pass. Existing tests asserting the message `'X' is not in the data dictionary` (`tests/test_constants.py:306`) fail: update them to `"the declaration of 'X' by component 'A' is not in the data dictionary"`. Any test whose `checks(bag)` now carries an extra `missing-producer`-free list or a different order: update to what the new rule says, and read each failing test's docstring first to be sure the change is the intended one.

- [ ] **Step 5: Commit and push**

```bash
git add src/ddd/analysis.py tests/test_analysis.py tests/test_constants.py
git commit -m "keep a dropped declaration in the ownership census" -m "A consumer of an object whose producer names an unknown type was a missing-producer, and an output whose only reader was dropped was unused; both findings pointed at the file the mistake was not in. Ownership is now decided over every declaration, an object whose owner was dropped is left out whole, and a second copy of a dropped name is a duplicate." -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push -u origin fix/dropped-declarations-are-marked
```

---

### Task 2: A poisoned type carries the cause that poisoned it

**Files:**
- Modify: `src/ddd/analysis.py` (`_Cause`, `_poisoned_types`, `_check_types`, `_refuse_infinite_type_limits`, `_check_member_dimensions`, `_members_resolve` -> `_poison_of`, `_resolve_type`)
- Test: `tests/test_analysis.py`

**Interfaces:**
- Produces: `_Cause(check: str, reported: bool, location: Location)` (frozen dataclass); `_Analysis._poisoned_types: dict[str, _Cause]`; `_Analysis._drop_for_type(ref: DeclarationRef, named: str) -> None`.

- [ ] **Step 1: Write the failing tests**

Add to `class TestDroppedDeclarations` (fixtures `struct_type`, `value_member`, `constants`, `constant` exist in `tests/test_constants.py` and `tests/test_structures.py`; import them from wherever they are defined, or write the json by hand as below):

```python
    @pytest.mark.parametrize(
        ("types", "cause"),
        [
            (
                [{"type": "struct", "name": "Loop_t", "members": [{"name": "self", "member": "value", "typename": "Loop_t"}]}],
                "type-cycle",
            ),
            (
                [{"type": "struct", "name": "Loop_t", "members": [{"name": "m", "member": "value", "typename": "Nope_t"}]}],
                "unknown-type",
            ),
            (
                [{"type": "struct", "name": "Loop_t", "members": [{"name": "m", "member": "value", "datatype": "uint8", "conversion": {"kind": "identity"}, "dimensions": ["NOPE"]}]}],
                "unknown-constant",
            ),
        ],
    )
    def test_silencing_what_poisoned_a_type_is_said_at_the_variable(self, tree: Path, types: list, cause: str) -> None:
        """The cause sits at the type; a variable of the type is dropped. With the cause
        silenced nothing said the variable had gone."""
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json", "a.ddd.json"),
                "types.ddd.json": {"types": types},
                "a.ddd.json": component("A", declare("local", "V", typename="Loop_t")),
            },
            severities=[f"{cause}=ignore"],
        )
        assert dictionary is not None and dictionary.instances == ()
        assert checks(bag) == ["incomplete-project"], messages(bag)
        rendered = messages(bag)
        assert "the declaration of 'V' by component 'A' is not in the data dictionary" in rendered
        assert f"the {cause}" in rendered
        assert "a.ddd.json#component.interface[0].definition.typename" in rendered

    def test_a_reported_poisoning_needs_no_second_finding(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json", "a.ddd.json"),
                "types.ddd.json": {"types": [{"type": "struct", "name": "Loop_t", "members": [{"name": "self", "member": "value", "typename": "Loop_t"}]}]},
                "a.ddd.json": component("A", declare("local", "V", typename="Loop_t")),
            },
        )
        assert checks(bag) == ["type-cycle"]

    def test_a_structure_nesting_a_poisoned_one_inherits_its_cause(self, tree: Path) -> None:
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json", "a.ddd.json"),
                "types.ddd.json": {"types": [
                    {"type": "struct", "name": "Inner_t", "members": [{"name": "m", "member": "value", "typename": "Nope_t"}]},
                    {"type": "struct", "name": "Outer_t", "members": [{"name": "i", "member": "value", "typename": "Inner_t"}]},
                ]},
                "a.ddd.json": component("A", declare("local", "V", typename="Outer_t")),
            },
            severities=["unknown-type=ignore"],
        )
        assert dictionary is not None and dictionary.instances == ()
        assert checks(bag) == ["incomplete-project"]
        assert "the unknown-type" in messages(bag)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_analysis.py -k "poisoned or poisoning" --no-cov -q`
Expected: the three parametrised cases and the nesting case fail (`checks(bag) == []`); the reported case passes already.

- [ ] **Step 3: Implement**

1. Add beside `_EnumRegistry`:

```python
@dataclass(frozen=True, slots=True)
class _Cause:
    """Why a type is unusable: the check that says so, whether it was reported, and where."""

    check: str
    reported: bool
    location: Location
```

2. `_Analysis.__init__`: `self._poisoned_types: dict[str, _Cause] = {}`, docstring: keep the text and add "Each carries the cause that poisoned it, so that a variable of the type can say, when the cause was silenced, what nobody reported."

3. `_check_types`: in the first loop, the member `unknown-type` add becomes

```python
                if target is None:
                    location = entry.location(f"members[{index}]")
                    reported = self._bag.add("unknown-type", f"...same message...", location) is not None
                    self._poisoned_types.setdefault(entry.name, _Cause("unknown-type", reported, location))
```

In the cycle loop: compute `reported` once per cycle (`reported = self._bag.add("type-cycle", ..., location) is not None`) and record for every type whose walk reaches the cycle `self._poisoned_types.setdefault(entry.name, _Cause("type-cycle", reported, declared[cycle[0]].location()))`. The loop currently poisons before deciding whether to report; restructure so that the cause (with the location of the structure the cycle closes on) is known: keep a `causes: dict[frozenset[str], _Cause]` keyed like `reported` is today, create the cause when the cycle is first met (adding the finding), and reuse it for every later type reaching the same cycle.

In `_refuse_infinite_type_limits`: `self._poisoned_types.setdefault(entry.name, _Cause("schema", True, <the location just reported at>))` (the check is fixed, so it is always reported).

In `_check_member_dimensions`: `reported = self._bag.add("unknown-constant", ..., location) is not None` then `self._poisoned_types.setdefault(entry.name, _Cause("unknown-constant", reported, location))`.

Replace `_members_resolve` and the `unresolvable` block at the end of `_check_types` with

```python
        # Propagated the way the cycles are: a sound structure nesting a broken one has the
        # same unresolvable leaves, and a variable of either is dropped at resolution, saying
        # what poisoned the inner one.
        for entry in self._workspace.types:
            cause = self._poison_of(entry.name, set())
            if cause is not None:
                self._poisoned_types.setdefault(entry.name, cause)

    def _poison_of(self, name: str, seen: set[str]) -> _Cause | None:
        """What makes a variable of that type unresolvable, if anything does.

        The type's own cause when it has one; else the first cause found walking its nested
        structures, however deep. A cycle is not this walk's business - it is reported and
        recorded as ``type-cycle`` before this runs - so a name already seen is not followed
        again. A nested name nobody declares was recorded on the type naming it.
        """
        if name in seen:
            return None
        seen.add(name)
        cause = self._poisoned_types.get(name)
        if cause is not None:
            return cause
        entry = self._types.get(name)
        if entry is None:
            return None
        for _, _, nested in _nested_types(entry):
            found = self._poison_of(nested, seen)
            if found is not None:
                return found
        return None
```

4. `_resolve_type`: replace the two `if named in self._poisoned_types:` blocks (the temporary `self._dropped[ref.key] = True` from Task 1 included) with `self._drop_for_type(ref, named); return None`, and add

```python
    def _drop_for_type(self, ref: DeclarationRef, named: str) -> None:
        """Drop a declaration of a poisoned type, and say so when nothing else did.

        The cycle, the unknown member type or the refused conversion is reported at the type,
        and a second finding here would only repeat it with a worse location. Unless the
        first was silenced: then the variable would simply be gone, from the listing, the
        dump and every backend, and the one place that can say so is this declaration.
        """
        cause = self._poisoned_types[named]
        self._dropped[ref.key] = cause.reported
        if cause.reported:
            return
        self._bag.add(
            "incomplete-project",
            f"the declaration of '{ref.name}' by component '{ref.component_name}' is not in "
            f"the data dictionary: it names the type '{named}', and the {cause.check} that "
            f"says why the type is unusable is not reported, so nothing reading the "
            f"dictionary - the listing, the dump, every backend - carries it either",
            ref.location("definition.typename"),
            notes=[("the type is unusable from here", cause.location)],
        )
```

- [ ] **Step 4: Run the tests**

Run: `python -m pytest tests/test_analysis.py tests/test_structures.py tests/test_types.py tests/test_constants.py tests/test_external.py --no-cov -q`
Expected: all pass; `test_a_declaration_of_a_poisoned_type_keeps_its_name_checks` (`tests/test_constants.py`, severities `unknown-constant=ignore`) now reports `incomplete-project` beside `consumer-storage`: update its expected list, and its docstring gains one sentence saying the silenced cause is now said at the variable.

- [ ] **Step 5: Commit and push**

```bash
git add src/ddd/analysis.py tests/test_analysis.py tests/test_constants.py
git commit -m "say at the variable what silenced finding poisoned its type" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push
```

---

### Task 3: Every declaration the dictionary omits for a silenced cause is reported

**Files:**
- Modify: `src/ddd/analysis.py` (`run`, new `_report_absences`)
- Test: `tests/test_analysis.py`

**Interfaces:**
- Produces: `_Analysis._report_absences(absent: dict[str, bool], owners: dict[str, DeclarationRef | None]) -> None`.

- [ ] **Step 1: Write the failing tests**

Add to `class TestDroppedDeclarations`:

```python
    def test_a_curve_over_a_silently_dropped_axis_is_said_to_be_missing(self, tree: Path) -> None:
        """The axis got its own incomplete-project; the curve over it vanished without one."""
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    declare("local", "Ax", "uint16", kind="axis", size="MISSING"),
                    declare("local", "Gain", "uint16", kind="curve", axis="Ax"),
                ),
            },
            severities=["unknown-constant=ignore"],
        )
        assert dictionary is not None and dictionary.objects == ()
        assert checks(bag) == ["incomplete-project", "incomplete-project"]
        rendered = messages(bag)
        assert "'Gain' is not in the data dictionary: its axis 'Ax' did not resolve" in rendered
        assert "a.ddd.json#component.interface[1].definition.axis" in rendered

    def test_a_reported_cause_drops_the_referring_object_silently(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    declare("local", "Ax", "uint16", kind="axis", size="MISSING"),
                    declare("local", "Gain", "uint16", kind="curve", axis="Ax"),
                ),
            },
        )
        assert checks(bag) == ["unknown-constant"]

    def test_a_consumer_of_a_silently_dropped_producer_is_said_to_be_missing(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "x", typename="Nope_t")),
                "b.ddd.json": component("B", declare("input", "x")),
            },
            severities=["unknown-type=ignore"],
        )
        assert checks(bag) == ["incomplete-project", "incomplete-project"]
        rendered = messages(bag)
        assert "the declaration of 'x' by component 'A' is not in the data dictionary" in rendered
        assert "'x' is declared by component 'B' but is not in the data dictionary" in rendered
        assert "b.ddd.json#component.interface[0].definition" in rendered

    def test_an_axis_over_a_silently_dropped_input_measurement_is_said_to_be_missing(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    declare("local", "M", "uint16", typename="Nope_t"),
                    declare("local", "Ax", "uint16", kind="axis", size=4, input="M"),
                ),
            },
            severities=["unknown-type=ignore"],
        )
        assert checks(bag) == ["incomplete-project", "incomplete-project"]
        assert "'Ax' is not in the data dictionary: its input 'M' did not resolve" in messages(bag)
```

(`declare(..., typename=...)` drops `datatype`; passing `"uint16"` positionally is harmless because the helper ignores `datatype` when `typename` is given - check `tests/conftest.py:40-50`.)

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_analysis.py -k "silently_dropped or drops_the_referring" --no-cov -q`
Expected: three fail with one `incomplete-project` instead of two; the reported-cause case passes.

- [ ] **Step 3: Implement**

In `run`, after `absent = self._absent(ordered, owners)`, add `self._report_absences(absent, owners)`. Then, in `_absent`, record beside each transitive absence the reference that caused it - change the dict value to a small record, or keep a parallel `self._via: dict[str, tuple[str, str]]` (name -> (key, target)) filled in the fixpoint loop when `absent[name] = absent[target]` is set. Add:

```python
    def _report_absences(
        self, absent: dict[str, bool], owners: dict[str, DeclarationRef | None]
    ) -> None:
        """One ``incomplete-project`` per declaration the dictionary omits for a silenced cause.

        The root of each absence already said so where it was dropped, if anything said so at
        all. What nothing said yet is the rest: a curve over an axis that went, the consumers
        of an object whose producer went. Each surviving declaration of such a name is named,
        at the reference that pulled the object down where there is one, at the declaration
        otherwise, so that no declaration leaves the dictionary in silence.
        """
        for name in sorted(absent):
            if absent[name]:
                continue
            refs = self._refs.get(name, [])
            first = owners[name] if owners[name] in refs else (refs[0] if refs else None)
            via = self._via.get(name)
            for ref in refs:
                if ref is first and via is not None:
                    key, target = via
                    self._bag.add(
                        "incomplete-project",
                        f"'{name}' is not in the data dictionary: its {key} '{target}' did "
                        f"not resolve, and the finding that says why is not reported",
                        ref.location(f"definition.{key}"),
                    )
                else:
                    self._bag.add(
                        "incomplete-project",
                        f"'{name}' is declared by component '{ref.component_name}' but is not "
                        f"in the data dictionary: it did not resolve, and the finding that "
                        f"says why is not reported",
                        ref.location("definition"),
                    )
```

`self._via` is initialised in `__init__` (`self._via: dict[str, tuple[str, str]] = {}`, docstring: "For a name absent because of what it refers to, the reference key and its target."). In `_absent`'s fixpoint loop, set `self._via[name] = (key, target)` when iterating `definition.references.items()`.

- [ ] **Step 4: Run the tests, then the whole suite**

Run: `python -m pytest tests/test_analysis.py --no-cov -q`, then `python -m pytest` (coverage 100% must hold: every new branch needs a test; the parametrised cases above cover the three poisonings, the two `_report_absences` messages are covered by the curve and the consumer tests).
Expected: only the 12 known environmental failures.

- [ ] **Step 5: Commit and push**

```bash
git add src/ddd/analysis.py tests/test_analysis.py
git commit -m "report every declaration the dictionary omits for a silenced cause" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push
```

---

### Task 4: The specification, the checks page and the changelog

**Files:**
- Modify: `SPEC.md` (section 4: `incomplete-project` entry at lines 1197-1206; section 2.1 or the ownership paragraph of section 4)
- Modify: `docs/consistency_checks.rst` (the `incomplete-project`, `missing-producer`, `unused-output` rows and any prose on dropping)
- Modify: `CHANGELOG.md`

- [ ] **Step 1: SPEC.md.** In the `incomplete-project` entry, after "This check fires only when the cause is silenced; a reported cause already says the declaration could not resolve." add: "It is reported for every declaration the dictionary omits on that account: the dropped declaration itself, a variable of a type whose cycle, unknown member type or unknown member constant was silenced, the consumers of an object whose producing declaration was dropped, and an object referring to one that went - a curve over such an axis, an axis indexed by such a measurement - at the reference that pulled it down." In section 4's general rules, after the paragraph naming the checks that need every component, add a paragraph: "A declaration dropped as unresolvable still counts for the ownership checks: a consumer of an object whose producing declaration was dropped is not `missing-producer`, an output whose only reader was dropped is not `unused-output`, and two dropped producers are still `multiple-producers`. An object whose producing declaration was dropped is left out of the dictionary whole, every declaration of it with it, because the consumers' copies describe storage nothing defines; a second declaration of a dropped name is `duplicate-declaration` as it would be of any other."

- [ ] **Step 2: docs/consistency_checks.rst.** Find the three rows (`grep -n "incomplete-project\|missing-producer\|unused-output" docs/consistency_checks.rst`) and the prose around "dropped"; add one sentence each to the same effect as Step 1, in the page's voice.

- [ ] **Step 3: CHANGELOG.md.** Under `## Unreleased`:

```
* **A dropped declaration is still a declaration.**  A producer naming an unknown type made
  every consumer a `missing-producer`, and a consumer dimensioned by an unknown constant made
  its producer an `unused-output`, each finding pointing at the file the mistake was not in.
  Ownership is now decided over every declaration, dropped ones included; an object whose
  producing declaration was dropped is left out of the dictionary whole, with every
  declaration of it; a second declaration of a dropped name is a `duplicate-declaration`.
  `incomplete-project`, which fires when the finding explaining a drop is silenced, now
  reaches every declaration the dictionary omits on that account: a variable of a poisoned
  type, the consumers of a dropped producer, a curve over a dropped axis - it used to name
  only the dropped declaration itself, so most of what a silenced check removed went
  unmentioned.  Its message names the component whose declaration is missing.
```

- [ ] **Step 4: Verification and commit**

Run `python -m pytest tests/test_documentation.py tests/test_transcripts.py --no-cov -q`, then the full `python -m pytest`, then ruff and mypy.

```bash
git add SPEC.md docs/consistency_checks.rst CHANGELOG.md
git commit -m "say that a dropped declaration still counts, and what incomplete-project now reaches" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push
```
