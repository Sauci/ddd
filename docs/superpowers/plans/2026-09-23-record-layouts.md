# Point Counts Ahead Of A Table Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a project state that its curves, maps and axes store their point counts ahead of their data, and have the c backend lay the counts out and the a2l backend describe them with `NO_AXIS_PTS_X` / `NO_AXIS_PTS_Y`.

**Architecture:** A `point_counts` key (`"none"` / `"leading"`) on the project and on a component is loaded into the `Workspace`, resolved per object in `ddd.analysis` (producer's component, else project) and carried on `ResolvedObject` (dictionary format 9). The c model turns a counted object into a flat array with the counts first; the a2l model gives it a record layout of its own kind. Two new findings guard the datatype and the agreement between a table and its axes, and `ddd compare` treats a changed convention as a changed interface.

**Tech Stack:** Python 3.13, pydantic 2, jinja2, pytest, CMake + MinGW gcc for the compile proof.

**Spec:** `docs/superpowers/specs/2026-09-23-record-layouts-design.md`

## Global Constraints

- Work only in the worktree `C:\git\ac11\ddd\.claude\worktrees\record-layouts`, branch `feature/record-layouts`. Never touch the main checkout: another session is editing it.
- Run every test from **Git Bash** with the worktree's own venv first on PATH:
  `export PATH="/c/git/ac11/ddd/.claude/worktrees/record-layouts/.venv/Scripts:/c/Users/lmbsog0/AppData/Local/Programs/CLion/bin/mingw/bin:$PATH"`
  then `python -m pytest ...`. Never use the main checkout's `.venv`: it is an editable install of the other checkout.
- One failure is expected on this machine and is not yours: `tests/test_lsp.py::TestSymlinkedWorkspace::test_a_document_opened_through_a_symlink_is_covered_by_its_build`.
- Coverage is enforced at **100 %** (lines and branches) by the full run.
- The enumeration values are exactly `"none"` and `"leading"`. The key is exactly `point_counts`, on `project` and on `component`.
- Finding identifiers are exactly `point-counts-unrepresentable` (error) and `point-counts-mismatch` (warning).
- Record layout names are exactly `RL_MAP_COUNTED_<T>`, `RL_CURVE_COUNTED_<T>`, `RL_AXIS_COUNTED_<T>`, where `<T>` is the `A2L_TYPE` spelling.
- `DICTIONARY_FORMAT` becomes `9`.
- A project that never states the key must generate byte-identical c and a2l to today.
- Commit messages are lower case, imperative, and say what changed and why (see `git log`). End each with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Push after every task (`git push`), since the maintainer reviews on GitHub.
- Match the surrounding code: docstrings explain *why*, tests are grouped in classes and named as sentences.

## File Map

- `src/ddd/models/objects.py`: `PointCounts`, `COUNTED_KINDS`, `stored_counts()`.
- `src/ddd/models/__init__.py`: export them.
- `src/ddd/models/project.py`, `src/ddd/models/component.py`: the key.
- `src/ddd/loading.py`: `Workspace.point_counts` and the one-value rule.
- `src/ddd/ir.py`: `ResolvedObject.point_counts`, `DICTIONARY_FORMAT = 9`.
- `src/ddd/analysis.py`: resolution and the two findings.
- `src/ddd/diagnostics.py`: the two catalogue entries.
- `src/ddd/backends/c/literals.py`, `src/ddd/backends/c/model.py`: the storage suffix, initialiser and new fields.
- `src/ddd/backends/a2l/model.py`, `src/ddd/backends/a2l/templates/project.a2l.jinja`: the counted layouts.
- `src/ddd/compare.py`: the interface field.
- `schemas/*.schema.json`: regenerated.
- `tests/test_point_counts.py` (new): every test of this feature, apart from the ones already living in `tests/test_cmake.py`, `tests/test_constants.py` and `tests/test_documentation.py`.
- `docs/data_dictionary.rst`, `docs/templates.rst`, `docs/generated_artefacts.rst`, `docs/consistency_checks.rst`, `docs/build_integration.rst`, `SPEC.md`, `CHANGELOG.md`.

---

### Task 1: The key on a project and on a component

**Files:**
- Modify: `src/ddd/models/objects.py` (after `class ObjectKind`, around line 128)
- Modify: `src/ddd/models/__init__.py`
- Modify: `src/ddd/models/project.py` (after `plugins`)
- Modify: `src/ddd/models/component.py` (after `raster`, line 110)
- Modify: `src/ddd/loading.py` (`Workspace` at line 366, `_load_project` at ~line 943, both `Workspace(...)` constructions at ~lines 636 and 658)
- Regenerate: `schemas/ddd_project.schema.json`, `schemas/ddd_component.schema.json`
- Create: `tests/test_point_counts.py`

**Interfaces:**
- Produces: `ddd.models.PointCounts` (`StrEnum`: `NONE = "none"`, `LEADING = "leading"`); `ddd.models.COUNTED_KINDS: frozenset[ObjectKind]`; `ddd.models.stored_counts(kind: ObjectKind, shape: tuple[T, ...]) -> tuple[T, ...]`; `Project.point_counts: PointCounts | None`; `Component.point_counts: PointCounts | None`; `Workspace.point_counts: PointCounts` (default `PointCounts.NONE`).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_point_counts.py`:

```python
"""Tests for point counts stored ahead of a curve, a map or an axis.

Some firmware stores the number of axis points inside every interpolation object, ahead of
its data, in the object's own type: the routines read the counts to learn the table's shape.
A project states that once, a component may state otherwise for what it defines, and both
backends then agree on where the data starts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from conftest import checks, component, declare, messages, project, run_analysis, write_tree
from ddd.diagnostics import DiagnosticBag
from ddd.loading import load_workspace
from ddd.models import ComponentFile, ObjectKind, PointCounts, ProjectFile, stored_counts


def axis(name: str = "AX", size: int | str = 4, datatype: str = "uint16", **extra: Any) -> dict[str, Any]:
    return declare("local", name, datatype, kind="axis", size=size, **extra)


def curve(name: str = "C", over: str = "AX", datatype: str = "uint16", **extra: Any) -> dict[str, Any]:
    return declare("local", name, datatype, kind="curve", axis=over, **extra)


def table(
    name: str = "M", x: str = "AX", y: str = "AY", datatype: str = "uint16", **extra: Any
) -> dict[str, Any]:
    return declare("local", name, datatype, kind="map", x_axis=x, y_axis=y, **extra)


class TestTheDescription:
    def test_a_project_states_the_key(self) -> None:
        model = ProjectFile.model_validate(project("P", point_counts="leading"))
        assert model.project.point_counts is PointCounts.LEADING

    def test_a_component_states_the_key(self) -> None:
        model = ComponentFile.model_validate(component("A", point_counts="none"))
        assert model.component.point_counts is PointCounts.NONE

    def test_the_key_is_optional_on_both(self) -> None:
        assert ProjectFile.model_validate(project("P")).project.point_counts is None
        assert ComponentFile.model_validate(component("A")).component.point_counts is None

    def test_an_unknown_value_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            ProjectFile.model_validate(project("P", point_counts="trailing"))


class TestTheProjectDefault:
    def test_an_unstated_default_is_none(self, tree: Path) -> None:
        write_tree(tree, {"project.ddd.json": project("P", "a.ddd.json"), "a.ddd.json": component("A")})
        workspace = load_workspace(tree / "project.ddd.json", DiagnosticBag())
        assert workspace is not None
        assert workspace.point_counts is PointCounts.NONE

    def test_a_sub_project_may_state_the_default(self, tree: Path) -> None:
        write_tree(
            tree,
            {
                "project.ddd.json": project("P", "sub.ddd.json"),
                "sub.ddd.json": project("S", "a.ddd.json", point_counts="leading"),
                "a.ddd.json": component("A"),
            },
        )
        workspace = load_workspace(tree / "project.ddd.json", DiagnosticBag())
        assert workspace is not None
        assert workspace.point_counts is PointCounts.LEADING

    def test_a_second_file_stating_another_value_is_refused(self, tree: Path) -> None:
        write_tree(
            tree,
            {
                "project.ddd.json": project("P", "sub.ddd.json", point_counts="leading"),
                "sub.ddd.json": project("S", "a.ddd.json", point_counts="none"),
                "a.ddd.json": component("A"),
            },
        )
        bag = DiagnosticBag()
        load_workspace(tree / "project.ddd.json", bag)
        assert checks(bag) == ["schema"]
        assert "point_counts is already stated as 'leading'" in messages(bag)

    def test_a_second_file_stating_the_same_value_is_accepted(self, tree: Path) -> None:
        write_tree(
            tree,
            {
                "project.ddd.json": project("P", "sub.ddd.json", point_counts="leading"),
                "sub.ddd.json": project("S", "a.ddd.json", point_counts="leading"),
                "a.ddd.json": component("A"),
            },
        )
        bag = DiagnosticBag()
        workspace = load_workspace(tree / "project.ddd.json", bag)
        assert workspace is not None, messages(bag)
        assert checks(bag) == []
        assert workspace.point_counts is PointCounts.LEADING


class TestTheStoredCounts:
    @pytest.mark.parametrize(
        ("kind", "shape", "counts"),
        [
            (ObjectKind.AXIS, (8,), (8,)),
            (ObjectKind.CURVE, (8,), (8,)),
            (ObjectKind.MAP, (11, 8), (8, 11)),
            (ObjectKind.MAP, ("NY", "NX"), ("NX", "NY")),
            (ObjectKind.VALUE_BLOCK, (4,), ()),
            (ObjectKind.PARAMETER, (), ()),
        ],
    )
    def test_x_comes_first(self, kind: ObjectKind, shape: tuple[Any, ...], counts: tuple[Any, ...]) -> None:
        """A map is declared ``[y][x]`` and stores x then y: an 8 by 11 map begins ``8, 11``."""
        assert stored_counts(kind, shape) == counts
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `python -m pytest tests/test_point_counts.py -q -p no:cacheprovider --no-cov`
Expected: collection error, `ImportError: cannot import name 'PointCounts'`.

- [ ] **Step 3: Add the enumeration and the helper**

In `src/ddd/models/objects.py`, directly after `class ObjectKind` (ends around line 127):

```python
class PointCounts(StrEnum):
    """Where an interpolation object stores its number of axis points, if anywhere."""

    NONE = "none"
    """Nowhere: the object is its data and nothing else. What every project had before."""

    LEADING = "leading"
    """Ahead of the data, in the object's own datatype: x first, then y for a map.

    What firmware whose interpolation routines learn a table's shape from the table itself
    stores, and what ASAP2 describes with ``NO_AXIS_PTS_X`` and ``NO_AXIS_PTS_Y`` ahead of
    ``FNC_VALUES`` or ``AXIS_PTS_X``. An enumeration rather than a flag so that another
    placement the format allows can join it without renaming the key.
    """


COUNTED_KINDS: Final = frozenset({ObjectKind.AXIS, ObjectKind.CURVE, ObjectKind.MAP})
"""The kinds a point count describes: the ones with axis points."""


def stored_counts[T](kind: ObjectKind, shape: tuple[T, ...]) -> tuple[T, ...]:
    """The counts a counted object stores, in storage order, taken from its own shape.

    Generic over the element so the same rule answers the numbers and the spellings: a map
    is declared ``[y][x]`` and stores x first, so its counts are its shape reversed; an axis
    and a curve have one dimension, which reversing leaves alone. Empty for every other kind.
    """
    return tuple(reversed(shape)) if kind in COUNTED_KINDS else ()
```

Check `Final` is already imported in that module (`grep -n "^from typing" src/ddd/models/objects.py`); add it to the import if it is not. Then export all three from `src/ddd/models/__init__.py`, beside `ObjectKind`, in both the import and `__all__` if the module keeps one.

- [ ] **Step 4: Add the key to the two models**

In `src/ddd/models/project.py`, import `PointCounts` from `ddd.models.objects` and add after `plugins`:

```python
    point_counts: PointCounts | None = None
    """Where the project's curves, maps and axes store their point counts: ``"leading"``
    ahead of the data, or ``"none"``. Unstated, it is ``"none"``.

    The default a component's own ``point_counts`` overrides. It belongs to the firmware's
    interpolation library, which is why it is stated here and not on each object; one project
    file of a tree states it, and a second one stating another value is refused.
    """
```

In `src/ddd/models/component.py`, after `raster`:

```python
    point_counts: PointCounts | None = None
    """Where the curves, maps and axes this component defines store their point counts,
    overriding the project's default.

    It follows the producer, as ``raster`` does: the component that defines a table is the one
    whose routines interpolate over it. It reaches nothing this component reads, and nothing
    that is not a curve, a map or an axis.
    """
```

- [ ] **Step 5: Load it into the workspace**

In `src/ddd/loading.py`:

1. Import `PointCounts` from `ddd.models`.
2. Add to `Workspace`, after `project_extensions`:

```python
    point_counts: PointCounts = PointCounts.NONE
    """The project's default for where tables store their point counts, as the one project
    file stating it wrote it; ``none`` when no file does, and for a component read alone."""
```

3. In the loader's `__init__` beside `self._project_blocks`, add `self._point_counts: tuple[PointCounts, Location] | None = None`.
4. In `_load_project`, right after the `for name, block in model.project.extensions.items():` loop (~line 947):

```python
        if model.project.point_counts is not None:
            self._register_point_counts(
                model.project.point_counts, Location(path, "project.point_counts")
            )
```

5. Beside `_register_settings`:

```python
    def _register_point_counts(self, value: PointCounts, location: Location) -> None:
        """One default per tree. A second file restating it agrees and is accepted; one stating
        another value is refused like a second plugin settings block, since two files cannot
        both decide how the image is laid out."""
        previous = self._point_counts
        if previous is None:
            self._point_counts = (value, location)
        elif previous[0] is not value:
            self._bag.add(
                "schema",
                f"point_counts is already stated as '{previous[0].value}'",
                location,
                notes=[("first stated here", previous[1])],
            )
```

6. In the project `Workspace(...)` construction (~line 658), add
   `point_counts=self._point_counts[0] if self._point_counts else PointCounts.NONE,`.
   Leave the standalone-component construction on the default.

- [ ] **Step 6: Regenerate the schemas**

Run: `ddd schema all -o schemas`
Expected: `schemas/ddd_project.schema.json` and `schemas/ddd_component.schema.json` change, nothing else.

- [ ] **Step 7: Run the tests to see them pass**

Run: `python -m pytest tests/test_point_counts.py tests/test_documentation.py tests/test_loading.py tests/test_models.py -q -p no:cacheprovider --no-cov`
Expected: PASS.

- [ ] **Step 8: Commit and push**

```bash
git add src/ddd/models src/ddd/loading.py schemas tests/test_point_counts.py
git commit -m "let a project and a component state where tables keep their point counts"
git push
```

---

### Task 2: Resolve the convention onto every object (dictionary format 9)

**Files:**
- Modify: `src/ddd/ir.py` (`ResolvedObject` after `raster` line ~209, `DICTIONARY_FORMAT` line 622)
- Modify: `src/ddd/analysis.py` (`_resolved_raster` line 370, `Variable` line 391, `_build_variable` line 3314)
- Modify: `tests/test_constants.py:958`, `docs/data_dictionary.rst:37`
- Regenerate: `schemas/ddd_dictionary.schema.json`
- Test: `tests/test_point_counts.py`

**Interfaces:**
- Consumes: `PointCounts`, `COUNTED_KINDS`, `Workspace.point_counts` (Task 1).
- Produces: `ResolvedObject.point_counts: PointCounts` (default `PointCounts.NONE`); `ddd.analysis._resolved_point_counts(producer, definition, default) -> PointCounts`; `Variable.point_counts: PointCounts`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_point_counts.py` (add `from ddd.ir import DataDictionary, ResolvedObject` and `from ddd.loading import load_dictionary`):

```python
def files(*declarations: dict[str, Any], default: str | None = None, **extra: Any) -> dict[str, Any]:
    stated = {"point_counts": default} if default is not None else {}
    return {
        "project.ddd.json": project("P", "a.ddd.json", **stated),
        "a.ddd.json": component("A", *declarations, **extra),
    }


def resolved(dictionary: DataDictionary, name: str) -> ResolvedObject:
    return next(entry for entry in dictionary.objects if entry.name == name)


TABLES = (axis("AX", 8), axis("AY", 11), curve("C"), table("M"))


class TestTheResolution:
    def test_the_project_default_reaches_every_table(self, tree: Path) -> None:
        dictionary, bag = run_analysis(tree, files(*TABLES, default="leading"))
        assert dictionary is not None, messages(bag)
        for name in ("AX", "AY", "C", "M"):
            assert resolved(dictionary, name).point_counts is PointCounts.LEADING

    def test_nothing_stated_is_none(self, tree: Path) -> None:
        dictionary, bag = run_analysis(tree, files(*TABLES))
        assert dictionary is not None, messages(bag)
        assert resolved(dictionary, "M").point_counts is PointCounts.NONE

    @pytest.mark.parametrize(("default", "override"), [("leading", "none"), ("none", "leading")])
    def test_a_component_overrides_the_default(self, tree: Path, default: str, override: str) -> None:
        dictionary, bag = run_analysis(tree, files(*TABLES, default=default, point_counts=override))
        assert dictionary is not None, messages(bag)
        assert resolved(dictionary, "M").point_counts is PointCounts(override)

    def test_it_reaches_no_other_kind(self, tree: Path) -> None:
        dictionary, bag = run_analysis(
            tree,
            files(declare("local", "X"), declare("local", "K", kind="parameter", init=1), default="leading"),
        )
        assert dictionary is not None, messages(bag)
        assert resolved(dictionary, "X").point_counts is PointCounts.NONE
        assert resolved(dictionary, "K").point_counts is PointCounts.NONE

    def test_a_readers_setting_does_not_reach_what_it_reads(self, tree: Path) -> None:
        """It follows the producer. The reader is included first so that an implementation
        reading the first declaration instead of the producing one would get it wrong."""
        tree_files = {
            "project.ddd.json": project("P", "b.ddd.json", "a.ddd.json"),
            "b.ddd.json": component(
                "B", declare("input", "AX", "uint16", kind="axis", size=8), point_counts="leading"
            ),
            "a.ddd.json": component("A", declare("output", "AX", "uint16", kind="axis", size=8)),
        }
        dictionary, bag = run_analysis(tree, tree_files)
        assert dictionary is not None, messages(bag)
        assert resolved(dictionary, "AX").point_counts is PointCounts.NONE

    def test_a_format_8_dictionary_reads_back_as_none(self, tree: Path) -> None:
        dictionary, bag = run_analysis(tree, files(*TABLES, default="leading"))
        assert dictionary is not None, messages(bag)
        dumped = dictionary.model_dump(mode="json")
        dumped["format"] = 8
        for entry in dumped["objects"]:
            del entry["point_counts"]
        target = tree / "old.json"
        target.write_text(json.dumps(dumped), encoding="utf-8")
        again = load_dictionary(target, DiagnosticBag())
        assert again is not None
        assert {entry.point_counts for entry in again.objects} == {PointCounts.NONE}
```

Add `import json` at the top of the file.

In `tests/test_constants.py:958`, change `== 8` to `== 9`.

- [ ] **Step 2: Run the tests to see them fail**

Run: `python -m pytest tests/test_point_counts.py -q -p no:cacheprovider --no-cov`
Expected: FAIL, `AttributeError: 'ResolvedObject' object has no attribute 'point_counts'`.

- [ ] **Step 3: Add the field and bump the format**

In `src/ddd/ir.py`, after `raster` on `ResolvedObject` (~line 209):

```python
    point_counts: PointCounts = PointCounts.NONE
    """Whether this curve, map or axis stores its point counts ahead of its data: its
    producing component's ``point_counts``, else the project's. ``none`` for every other kind,
    and in a dictionary from format 8 or older, which never stored any."""
```

Set `DICTIONARY_FORMAT = 9` and append to its docstring:

```
Format 9 added ``point_counts`` to every object. A format 8 dictionary carries none, and reads
back with ``none`` everywhere, which is the layout it described.
```

If the dump loader refuses a format it does not know, confirm 8 is still accepted (`grep -n "DICTIONARY_FORMAT" src/ddd/ir.py src/ddd/loading.py`).

- [ ] **Step 4: Resolve it in the analysis**

In `src/ddd/analysis.py`, beside `_resolved_raster`:

```python
def _resolved_point_counts(
    producer: DeclarationRef | None, definition: DataObject, default: PointCounts
) -> PointCounts:
    """Where a table keeps its point counts: its producing component's say, else the project's.

    Only a curve, a map or an axis has counts to keep. The reader's component is not consulted,
    for the reason it is not for a raster: the convention follows the code that defines the
    table, and every reader of it is handed the same bytes.
    """
    if definition.kind not in COUNTED_KINDS:
        return PointCounts.NONE
    stated = producer.owner.component.point_counts if producer is not None else None
    return stated if stated is not None else default
```

Add a field `point_counts: PointCounts` to the `Variable` dataclass (after `extensions`), pass `point_counts=self.point_counts` in `Variable.resolve()`, and in `_build_variable`'s `Variable(...)` call pass
`point_counts=_resolved_point_counts(producer, definition, self._workspace.point_counts),`.
Import `COUNTED_KINDS` and `PointCounts` from `ddd.models`.

- [ ] **Step 5: Update the format in the documentation and the dictionary schema**

In `docs/data_dictionary.rst` line 37 change `"format": 8,` to `"format": 9,`. Run `ddd schema all -o schemas`; expected: only `schemas/ddd_dictionary.schema.json` changes.

- [ ] **Step 6: Run the tests to see them pass**

Run: `python -m pytest tests/test_point_counts.py tests/test_constants.py tests/test_documentation.py tests/test_analysis.py tests/test_cli.py -q -p no:cacheprovider --no-cov`
Expected: PASS.

- [ ] **Step 7: Commit and push**

```bash
git add src/ddd/ir.py src/ddd/analysis.py schemas docs/data_dictionary.rst tests/test_point_counts.py tests/test_constants.py
git commit -m "resolve each table's point counts from its producer, and stamp dictionary format 9"
git push
```

---

### Task 3: The two findings

**Files:**
- Modify: `src/ddd/diagnostics.py` (beside `a2l-unrepresentable`, line ~204)
- Modify: `src/ddd/analysis.py` (`run`, after the `variables` list is built, ~line 845)
- Modify: `docs/consistency_checks.rst` (the table holding `a2l-unrepresentable`, line ~645)
- Test: `tests/test_point_counts.py`

**Interfaces:**
- Consumes: `Variable.point_counts`, `stored_counts` (Tasks 1-2).
- Produces: checks `point-counts-unrepresentable` (ERROR) and `point-counts-mismatch` (WARNING); `_Analyzer._check_point_counts(variables: list[Variable]) -> None`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_point_counts.py`:

```python
class TestTheFindings:
    def test_a_boolean_table_cannot_hold_a_count(self, tree: Path) -> None:
        dictionary, bag = run_analysis(tree, files(axis("AX", 2, "boolean"), default="leading"))
        assert dictionary is None
        assert checks(bag) == ["point-counts-unrepresentable"]
        assert "'AX' stores its point count 2 as boolean" in messages(bag)

    def test_the_widest_count_a_type_holds_is_accepted(self, tree: Path) -> None:
        dictionary, bag = run_analysis(tree, files(axis("AX", 255, "uint8"), default="leading"))
        assert dictionary is not None, messages(bag)
        assert checks(bag) == []

    def test_one_more_is_refused(self, tree: Path) -> None:
        dictionary, bag = run_analysis(tree, files(axis("AX", 256, "uint8"), default="leading"))
        assert dictionary is None
        assert checks(bag) == ["point-counts-unrepresentable"]

    def test_a_map_is_checked_on_both_counts(self, tree: Path) -> None:
        """The y count is the one that overflows here, which a check of x alone would miss."""
        dictionary, bag = run_analysis(
            tree,
            files(axis("AX", 8, "sint8"), axis("AY", 200, "sint16"), table("M", datatype="sint8"), default="leading"),
        )
        assert dictionary is None
        assert checks(bag) == ["point-counts-unrepresentable"]
        assert "'M' stores its point count 200 as sint8" in messages(bag)

    def test_a_float_always_holds_a_count(self, tree: Path) -> None:
        dictionary, bag = run_analysis(tree, files(axis("AX", 300, "float32"), default="leading"))
        assert dictionary is not None, messages(bag)
        assert checks(bag) == []

    def test_an_uncounted_boolean_table_is_not_a_finding(self, tree: Path) -> None:
        dictionary, bag = run_analysis(tree, files(axis("AX", 2, "boolean")))
        assert dictionary is not None, messages(bag)
        assert checks(bag) == []

    def test_a_table_and_its_axis_disagreeing_is_a_warning(self, tree: Path) -> None:
        """A defines the curve and reads the axis B defines; B states the other convention."""
        tree_files = {
            "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json", point_counts="leading"),
            "a.ddd.json": component(
                "A", declare("input", "AX", "uint16", kind="axis", size=8), curve("C")
            ),
            "b.ddd.json": component(
                "B", declare("output", "AX", "uint16", kind="axis", size=8), point_counts="none"
            ),
        }
        dictionary, bag = run_analysis(tree, tree_files)
        assert dictionary is not None, messages(bag)
        assert checks(bag) == ["point-counts-mismatch"]
        assert "'C' stores its point counts 'leading', but its axis 'AX' stores them 'none'" in messages(bag)

    def test_agreement_is_not_a_finding(self, tree: Path) -> None:
        dictionary, bag = run_analysis(tree, files(*TABLES, default="leading"))
        assert dictionary is not None, messages(bag)
        assert checks(bag) == []
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `python -m pytest tests/test_point_counts.py::TestTheFindings -q -p no:cacheprovider --no-cov`
Expected: FAIL. The unrepresentable cases resolve with no finding; the catalogue does not know the checks.

- [ ] **Step 3: Add the catalogue entries**

In `src/ddd/diagnostics.py`, after the `init-invalid` entry (errors are grouped before warnings):

```python
        _check("point-counts-unrepresentable", Severity.ERROR,
               "a table stores its point counts in a datatype that cannot hold them"),
```

and after `a2l-unrepresentable`:

```python
        _check("point-counts-mismatch", Severity.WARNING,
               "a curve or map and one of its axes store their point counts differently"),
```

- [ ] **Step 4: Implement the checks**

In `src/ddd/analysis.py`, add to the analyzer class:

```python
    def _check_point_counts(self, variables: list[Variable]) -> None:
        """A counted table's type holds its counts, and a table agrees with its axes.

        The first is an error because the c initialiser would otherwise overflow in silence:
        a ``boolean`` has no room for a count, and a ``uint8`` axis of 300 points writes 44.
        A float holds any count a shape can have. The second is a warning: ASAP2 describes a
        mix, one record layout per object, but an interpolation routine reads one convention.
        """
        by_name = {variable.name: variable for variable in variables}
        for variable in variables:
            reference = variable.producer or variable.declarations[0]
            if variable.point_counts is PointCounts.LEADING:
                datatype = variable.definition.datatype
                for count in stored_counts(variable.definition.kind, variable.shape):
                    if datatype is Datatype.BOOLEAN or (
                        datatype.is_integer and count > datatype.raw_max
                    ):
                        self._bag.add(
                            "point-counts-unrepresentable",
                            f"'{variable.name}' stores its point count {count} as "
                            f"{datatype.value}, which cannot hold it",
                            reference.location("definition"),
                        )
                        break
            for key, axis_name in variable.definition.references.items():
                if key == "input":
                    continue
                axis = by_name.get(axis_name)
                if axis is not None and axis.point_counts is not variable.point_counts:
                    self._bag.add(
                        "point-counts-mismatch",
                        f"'{variable.name}' stores its point counts "
                        f"'{variable.point_counts.value}', but its axis '{axis_name}' stores "
                        f"them '{axis.point_counts.value}'",
                        reference.location("definition"),
                    )
```

An axis's only reference is `input`, a measurement, which the `continue` skips. Call `self._check_point_counts(variables)` in `run` right after the `variables = [...]` list is built (just before `instances = [...]`). Confirm the list's name there, and `Datatype` / `stored_counts` imports.

- [ ] **Step 5: Document the checks**

In `docs/consistency_checks.rst`, add rows to the same list-table that holds `a2l-unrepresentable` (and, if errors live in a separate table, the error one there), following the neighbouring rows' columns exactly:

- `point-counts-unrepresentable`, error: "a table stores its point counts in a datatype that cannot hold them: a ``boolean`` table, or an integer one whose range stops short of a count. Only a counted table is checked; a float holds any count."
- `point-counts-mismatch`, warning: "a curve or a map stores its point counts one way and one of its axes the other. The a2l describes each as resolved; the interpolation routine is unlikely to read both."

Run `python -m pytest tests/test_documentation.py -q -p no:cacheprovider --no-cov`: the suite checks every catalogue entry is documented, so it tells you if the table's form is wrong.

- [ ] **Step 6: Run the tests to see them pass**

Run: `python -m pytest tests/test_point_counts.py tests/test_documentation.py tests/test_analysis.py -q -p no:cacheprovider --no-cov`
Expected: PASS.

- [ ] **Step 7: Commit and push**

```bash
git add src/ddd/diagnostics.py src/ddd/analysis.py docs/consistency_checks.rst tests/test_point_counts.py
git commit -m "refuse a count its table's datatype cannot hold, and warn when a table and its axis disagree"
git push
```

---

### Task 4: The c backend lays the counts out

**Files:**
- Modify: `src/ddd/backends/c/literals.py` (`initializer_of`, line 104)
- Modify: `src/ddd/backends/c/model.py` (`ObjectView` line 33, `_view` line 557)
- Modify: `docs/templates.rst`
- Test: `tests/test_point_counts.py`

**Interfaces:**
- Consumes: `ResolvedObject.point_counts`, `stored_counts` (Tasks 1-2).
- Produces: `ObjectView.dimensions: tuple[int | str, ...]`, `ObjectView.point_counts: tuple[int | str, ...]`; `literals.storage_suffix(entry: ResolvedObject | ResolvedInstance) -> str`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_point_counts.py` (add `render_files` to the conftest import, plus `from ddd.backends.c.model import build_code_model` and `from ddd.backends.c.options import COptions`):

```python
def generated(tree: Path, tree_files: dict[str, Any]) -> dict[str, str]:
    dictionary, bag = run_analysis(tree, tree_files)
    assert dictionary is not None, messages(bag)
    return {file.path.name: file.content for file in render_files(dictionary, tree / "gen")}


class TestTheC:
    def test_a_counted_map_is_a_flat_array_with_its_counts_first(self, tree: Path) -> None:
        source = generated(
            tree, files(axis("AX", 2), axis("AY", 3), table("M", init=[[1, 2], [3, 4], [5, 6]]), default="leading")
        )["ddd_globals.c"]
        assert "const uint16_t M[2 + (3) * (2)] = { 2U, 3U, 1U, 2U, 3U, 4U, 5U, 6U };" in source

    def test_a_counted_axis_and_curve_carry_one_count(self, tree: Path) -> None:
        source = generated(tree, files(axis("AX", 2, init=[10, 20]), curve("C"), default="leading"))[
            "ddd_globals.c"
        ]
        assert "const uint16_t AX[1 + (2)] = { 2U, 10U, 20U };" in source
        assert "const uint16_t C[1 + (2)] = { 2U };" in source

    def test_a_count_spelled_by_a_constant_is_written_by_name(self, tree: Path) -> None:
        tree_files = files(axis("AX", "NX"), axis("AY", "NY"), table("M"), default="leading")
        tree_files["project.ddd.json"]["project"]["includes"].append("k.ddd.json")
        tree_files["k.ddd.json"] = {"constants": [{"name": "NX", "value": 8}, {"name": "NY", "value": 11}]}
        source = generated(tree, tree_files)["ddd_globals.c"]
        assert "const uint16_t M[2 + (NY) * (NX)] = { NX, NY };" in source

    def test_the_component_header_declares_the_storage(self, tree: Path) -> None:
        header = generated(tree, files(axis("AX", 2), default="leading"))["A.h"]
        assert "uint16_t AX[1 + (2)]" in header

    def test_an_uncounted_project_is_unchanged(self, tree: Path) -> None:
        """A project that never states the key generates what it generated before."""
        stated = generated(tree / "a", files(axis("AX", 2), axis("AY", 3), table("M"), default="none"))
        unstated = generated(tree / "b", files(axis("AX", 2), axis("AY", 3), table("M")))
        assert stated == unstated
        assert "const uint16_t M[3][2];" in unstated["ddd_globals.c"]

    def test_the_view_offers_the_dimensions_and_the_counts(self, tree: Path) -> None:
        dictionary, bag = run_analysis(tree, files(axis("AX", 2), axis("AY", 3), table("M"), default="leading"))
        assert dictionary is not None, messages(bag)
        views = {
            view.name: view
            for group in build_code_model(dictionary, COptions(), "test").groups
            for view in group.variables
        }
        assert views["M"].dimensions == (3, 2)
        assert views["M"].point_counts == (2, 3)
        assert views["AX"].point_counts == (2,)

    def test_an_uncounted_view_has_its_dimensions_and_no_counts(self, tree: Path) -> None:
        dictionary, bag = run_analysis(tree, files(declare("local", "V", kind="value_block", dimensions=[4])))
        assert dictionary is not None, messages(bag)
        views = {
            view.name: view
            for group in build_code_model(dictionary, COptions(), "test").groups
            for view in group.variables
        }
        assert views["V"].dimensions == (4,)
        assert views["V"].point_counts == ()
```

Run the first test once before implementing, and read the real output for the exact literal spelling and the exact file names (`ddd_globals.c`, `A.h`). Then fix the expectations to match the code's *existing* conventions, not the other way round. What the tests pin is the suffix, the order and the presence of the counts.

- [ ] **Step 2: Run the tests to see them fail**

Run: `python -m pytest tests/test_point_counts.py::TestTheC -q -p no:cacheprovider --no-cov`
Expected: FAIL: the map is still `M[3][2]`, and the view has no `dimensions`.

- [ ] **Step 3: Implement the suffix and the initialiser**

In `src/ddd/backends/c/literals.py`, import `PointCounts` and `stored_counts` from `ddd.models` (and `ResolvedInstance` from `ddd.ir` if not imported), then:

```python
def _counted(entry: ResolvedObject | ResolvedInstance) -> bool:
    """Whether the object stores its point counts ahead of its data.

    A structured variable never does: it is no table, and it carries no such field."""
    return isinstance(entry, ResolvedObject) and entry.point_counts is PointCounts.LEADING


def storage_suffix(entry: ResolvedObject | ResolvedInstance) -> str:
    """The array suffix the object is declared with: its shape, or the flat storage of a table
    that keeps its counts in front of its values.

    Flat because the counts and the values are one run of one type in memory - which is what
    the routine reading them is handed - and a ``[y][x]`` array has no room in front of it.
    Each dimension is parenthesised because it may be a constant's name, and a constant is a
    macro whose expansion nobody here controls.
    """
    spelled = entry.spelled_shape
    if not _counted(entry):
        return format_shape(spelled)
    product = " * ".join(f"({dimension})" for dimension in spelled)
    return f"[{len(spelled)} + {product}]"


def _flattened(value: InitValue) -> list[InitValue]:
    """The elements of a nested init in storage order, the last index running fastest."""
    if isinstance(value, tuple):
        return [element for part in value for element in _flattened(part)]
    return [value]
```

Replace `initializer_of`:

```python
def initializer_of(entry: ResolvedObject) -> str | None:
    """The initialiser of an object, or ``None`` for implicit zero initialisation.

    A table keeping its counts in front always has one, since the counts cannot be left to the
    startup code: the counts, each by the constant's name when its axis is sized by one, then
    the values in the row order the nested form would have used - or nothing more, when no
    ``init`` was given, which leaves the rest zero exactly as an absent initialiser would.
    """
    if _counted(entry):
        counts = [
            count if isinstance(count, str) else c_literal(count, entry.datatype)
            for count in stored_counts(entry.kind, entry.spelled_shape)
        ]
        values = (
            [] if entry.init is None else _flattened(broadcast(entry.init, entry.shape))
        )
        flat = tuple([*counts, *(c_literal(value, entry.datatype) for value in values)])
        return _flat_braces(flat)
    if entry.init is None:
        return None
    return c_initializer(broadcast(entry.init, entry.shape), entry.datatype)
```

`c_initializer` already lays a flat list out (one line up to eight values, then wrapped), but it renders its elements itself. Factor that layout out of `c_initializer` into `_flat_braces(parts: tuple[str, ...], indent: int = 0) -> str`, holding the `len(parts) <= _MAX_VALUES_PER_LINE` branch and the wrapped branch, and call it from both, so the two render one flat list one way. Keep `c_initializer`'s behaviour byte for byte: the existing c tests are the proof.

- [ ] **Step 4: Add the view fields**

In `src/ddd/backends/c/model.py`, add to `ObjectView` after `array_suffix`:

```python
    dimensions: tuple[int | str, ...] = ()
    """The object's shape as the description spells it, in declaration order: ``(11, 8)`` or
    ``("NY", "NX")`` for a map, ``()`` for a scalar. What ``array_suffix`` was rendered from,
    so a template computing anything from the shape does not parse the suffix back apart."""

    point_counts: tuple[int | str, ...] = ()
    """The counts a table stores ahead of its values, in storage order - x, then y - spelled
    like ``dimensions``; ``()`` for every object that stores none. When it is not empty,
    ``array_suffix`` and ``initializer`` already describe the flat storage."""
```

In `_view`, replace `array_suffix=format_shape(entry.spelled_shape),` with:

```python
        array_suffix=storage_suffix(entry),
        dimensions=tuple(entry.spelled_shape),
        point_counts=(
            stored_counts(entry.kind, entry.spelled_shape)
            if isinstance(entry, ResolvedObject) and entry.point_counts is PointCounts.LEADING
            else ()
        ),
```

Keep the comment above it, reworded: "The spelled shape, so an array dimensioned by a constant is declared by its name; a table keeping its counts in front is declared flat." Import `storage_suffix`, `stored_counts` and `PointCounts`. Drop `format_shape` from the imports if it is no longer used.

- [ ] **Step 5: Document the fields**

In `docs/templates.rst`, find where the `ObjectView` fields are listed (`grep -n "array_suffix" docs/templates.rst`) and add `dimensions` and `point_counts` in the same form. Next to `array_suffix` and `initializer`, add one sentence each saying what they hold for an object whose `point_counts` is `leading`: the flat suffix, and the counts-first list that is always written. If a documentation test lists the view's fields, it will fail until this is done.

- [ ] **Step 6: Run the tests to see them pass**

Run: `python -m pytest tests/test_point_counts.py tests/test_backends.py tests/test_generation.py tests/test_calibration.py tests/test_documentation.py -q -p no:cacheprovider --no-cov`
Expected: PASS.

- [ ] **Step 7: Commit and push**

```bash
git add src/ddd/backends/c docs/templates.rst tests/test_point_counts.py
git commit -m "declare a counted table flat with its counts first, and offer its dimensions to templates"
git push
```

---

### Task 5: Prove the c compiles and puts the counts where the a2l says

**Files:**
- Modify: `tests/test_cmake.py` (`class TestEveryGeneratedHeaderCompilesAlone`, line 582)

**Interfaces:**
- Consumes: the generated c from Task 4; the class's own `generated`, `compile_alone`, `project` helpers.

- [ ] **Step 1: Write the test**

Add to `TestEveryGeneratedHeaderCompilesAlone`:

```python
    def test_a_table_keeping_its_counts_compiles_with_them_in_front(self, tmp_path: Path) -> None:
        """The flat declaration, its initialiser and the extern in the component header agree
        with one another under the full warning set - ``-Wconversion`` included, which is what
        a count spelled as a constant's name meets - and a static assertion pins the size and
        the first elements to what the a2l's NO_AXIS_PTS_X / NO_AXIS_PTS_Y say."""
        (tmp_path / "k.ddd.json").write_text(
            json.dumps({"constants": [{"name": "NX", "value": 8}]}), encoding="utf-8"
        )
        (tmp_path / "t.ddd.json").write_text(
            json.dumps(
                {
                    "component": {
                        "name": "T",
                        "interface": [
                            declare("output", "AX", "uint16", kind="axis", size="NX"),
                            declare("output", "AY", "uint16", kind="axis", size=11),
                            declare("output", "M", "uint32", kind="map", x_axis="AX", y_axis="AY"),
                        ],
                    }
                }
            ),
            encoding="utf-8",
        )
        description = tmp_path / "project.ddd.json"
        description.write_text(
            json.dumps(
                {"project": {"name": "P", "includes": ["k.ddd.json", "t.ddd.json"], "point_counts": "leading"}}
            ),
            encoding="utf-8",
        )
        output = self.generated(tmp_path, description)
        (output / "check_counts.c").write_text(
            '#include "T.h"\n'
            "_Static_assert(sizeof M == (2 + 8 * 11) * sizeof(uint32_t), \"counts ahead of M\");\n"
            "_Static_assert(sizeof AX == (1 + 8) * sizeof(uint16_t), \"count ahead of AX\");\n",
            encoding="utf-8",
        )
        self.compile_alone(tmp_path, output)
```

`compile_alone` compiles every `*.c` in the output directory, so `check_counts.c` goes along. `_Static_assert` needs a complete type, which the extern in `T.h` gives, since it carries the full suffix. Check the component header's real file name first (`ls` of a generated output, or the `{component}.h.jinja2` template name). A value check of the counts belongs to Task 4's string tests; this test proves they compile and size right.

- [ ] **Step 2: Run it**

Run: `python -m pytest tests/test_cmake.py -k counts -q -p no:cacheprovider --no-cov`
Expected: PASS. A failure here is a real defect in Task 4, typically a `-Wconversion` complaint about a count or a missing include for the constant. Fix the c model rather than the flags.

- [ ] **Step 3: Commit and push**

```bash
git add tests/test_cmake.py
git commit -m "compile a table that keeps its counts in front, and pin its size"
git push
```

---

### Task 6: The a2l describes the counts

**Files:**
- Modify: `src/ddd/backends/a2l/model.py` (`RecordLayoutView` line 78, `_characteristic` line 414, `_axis_pts` line 463, `_RecordLayoutBuilder` line 538, module docstring)
- Modify: `src/ddd/backends/a2l/templates/project.a2l.jinja` (lines 30-35)
- Modify: `docs/generated_artefacts.rst`
- Test: `tests/test_point_counts.py`

**Interfaces:**
- Consumes: `ResolvedObject.point_counts` (Task 2).
- Produces: `RecordLayoutView.entries: tuple[str, ...]` (replaces `entry`); `_RecordLayoutBuilder.counted(kind: ObjectKind, datatype: Datatype) -> str`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_point_counts.py`:

```python
def a2l(tree: Path, tree_files: dict[str, Any]) -> str:
    return generated(tree, tree_files)["P.a2l"]


def layout(text: str, name: str) -> list[str]:
    """The lines of one record layout, stripped."""
    start = text.index(f"/begin RECORD_LAYOUT {name}\n")
    end = text.index("/end RECORD_LAYOUT", start)
    return [line.strip() for line in text[start:end].splitlines()[1:] if line.strip()]


class TestTheA2l:
    def test_a_counted_map_has_both_counts_ahead_of_its_values(self, tree: Path) -> None:
        text = a2l(tree, files(axis("AX", 8, "uint32"), axis("AY", 11, "uint32"), table("M", datatype="uint32"), default="leading"))
        assert layout(text, "RL_MAP_COUNTED_ULONG") == [
            "NO_AXIS_PTS_X 1 ULONG",
            "NO_AXIS_PTS_Y 2 ULONG",
            "FNC_VALUES 3 ULONG ROW_DIR DIRECT",
        ]
        assert "MAP 0x00000000 RL_MAP_COUNTED_ULONG" in text

    def test_a_counted_curve_has_one_count(self, tree: Path) -> None:
        text = a2l(tree, files(axis("AX", 8), curve("C"), default="leading"))
        assert layout(text, "RL_CURVE_COUNTED_UWORD") == ["NO_AXIS_PTS_X 1 UWORD", "FNC_VALUES 2 UWORD ROW_DIR DIRECT"]

    def test_a_counted_axis_has_its_count_ahead_of_its_points(self, tree: Path) -> None:
        text = a2l(tree, files(axis("AX", 8, "sint16"), default="leading"))
        assert layout(text, "RL_AXIS_COUNTED_SWORD") == [
            "NO_AXIS_PTS_X 1 SWORD",
            "AXIS_PTS_X 2 SWORD INDEX_INCR DIRECT",
        ]

    def test_objects_of_one_kind_and_type_share_a_layout(self, tree: Path) -> None:
        text = a2l(tree, files(axis("AX", 8), axis("AY", 11), default="leading"))
        assert text.count("/begin RECORD_LAYOUT RL_AXIS_COUNTED_UWORD") == 1

    def test_a_mixed_project_keeps_the_plain_layouts_for_the_rest(self, tree: Path) -> None:
        tree_files = {
            "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json", point_counts="leading"),
            "a.ddd.json": component("A", axis("AX", 8)),
            "b.ddd.json": component("B", axis("BX", 8), point_counts="none"),
        }
        text = a2l(tree, tree_files)
        assert "RL_AXIS_COUNTED_UWORD" in text
        assert layout(text, "RL_AXIS_UWORD") == ["AXIS_PTS_X 1 UWORD INDEX_INCR DIRECT"]

    def test_no_static_record_layout_is_written(self, tree: Path) -> None:
        """A tool removing points compacts the data behind the new count, which is what a
        routine computing ``y * nx + x`` from the stored count expects."""
        text = a2l(tree, files(axis("AX", 8), default="leading"))
        assert "STATIC_RECORD_LAYOUT" not in text
```

Check the a2l file name the backend writes (`A2lOptions.filename`, `f"{project}.a2l"`: project `P` gives `P.a2l`) and the exact `MAP <address> <layout>` spacing against the template before running.

- [ ] **Step 2: Run the tests to see them fail**

Run: `python -m pytest tests/test_point_counts.py::TestTheA2l -q -p no:cacheprovider --no-cov`
Expected: FAIL, `ValueError: substring not found` for `RL_MAP_COUNTED_ULONG`.

- [ ] **Step 3: Implement the layouts**

In `src/ddd/backends/a2l/model.py`:

`RecordLayoutView`:

```python
@dataclass(frozen=True, slots=True)
class RecordLayoutView:
    name: str
    entries: tuple[str, ...]
    """The layout's lines in position order, e.g. ``("FNC_VALUES 1 UBYTE ROW_DIR DIRECT",)``."""
```

`_RecordLayoutBuilder`:

```python
class _RecordLayoutBuilder:
    """Creates one RECORD_LAYOUT per datatype and storage category."""

    def __init__(self) -> None:
        self._layouts: dict[str, RecordLayoutView] = {}

    def values(self, datatype: Datatype) -> str:
        a2l_type = A2L_TYPE[datatype]
        return self._add(f"RL_VALUES_{a2l_type}", (f"FNC_VALUES 1 {a2l_type} ROW_DIR DIRECT",))

    def axis(self, datatype: Datatype) -> str:
        a2l_type = A2L_TYPE[datatype]
        return self._add(f"RL_AXIS_{a2l_type}", (f"AXIS_PTS_X 1 {a2l_type} INDEX_INCR DIRECT",))

    def counted(self, kind: ObjectKind, datatype: Datatype) -> str:
        """The layout of a table that keeps its point counts ahead of its data.

        One count per axis - x, then y for a map - each in the object's own type, then the data
        at the next position: ASAP2 1.6.1 numbers positions in ascending order without gaps and
        wants the counts in memory before the points and the values. No
        ``STATIC_RECORD_LAYOUT``: a tool removing points then compacts the data behind the new
        count, which is what a routine indexing by the stored count reads. A curve cannot share
        the values layout, because it has one count where a map has two.
        """
        a2l_type = A2L_TYPE[datatype]
        keywords = ("NO_AXIS_PTS_X", "NO_AXIS_PTS_Y")[: 2 if kind is ObjectKind.MAP else 1]
        counts = tuple(
            f"{keyword} {position} {a2l_type}" for position, keyword in enumerate(keywords, 1)
        )
        data = (
            f"AXIS_PTS_X {len(counts) + 1} {a2l_type} INDEX_INCR DIRECT"
            if kind is ObjectKind.AXIS
            else f"FNC_VALUES {len(counts) + 1} {a2l_type} ROW_DIR DIRECT"
        )
        return self._add(f"RL_{kind.name}_COUNTED_{a2l_type}", (*counts, data))

    def _add(self, name: str, entries: tuple[str, ...]) -> str:
        self._layouts.setdefault(name, RecordLayoutView(name, entries))
        return name

    def layouts(self) -> tuple[RecordLayoutView, ...]:
        return tuple(sorted(self._layouts.values(), key=lambda layout: layout.name))
```

In `_characteristic`, replace `deposit=self._layouts.values(entry.datatype),` with:

```python
            deposit=(
                self._layouts.counted(entry.kind, entry.datatype)
                if entry.point_counts is PointCounts.LEADING
                else self._layouts.values(entry.datatype)
            ),
```

In `_axis_pts`, replace `deposit=self._layouts.axis(entry.datatype),` the same way, with `counted(entry.kind, ...)` / `axis(...)`. `_leaf_characteristic` is unchanged: a member is never a table. Import `PointCounts`. Add one bullet to the module docstring: "a curve, map or axis whose ``point_counts`` is ``leading`` gets a record layout with ``NO_AXIS_PTS_X`` (and ``_Y``) ahead of its data".

In `project.a2l.jinja`, replace line 33 `      {{ layout.entry }}` with:

```
{% for entry in layout.entries %}
      {{ entry }}
{% endfor %}
```

The environment trims blocks and strips leading whitespace (`backends/base.py:435`), so this renders one line per entry. The existing a2l tests show whether it does.

- [ ] **Step 4: Document the layouts**

In `docs/generated_artefacts.rst`, where the record layouts are described (`grep -n "RECORD_LAYOUT\|RL_VALUES" docs/generated_artefacts.rst`), add the three counted layouts with the map example from the spec (section 5), and one sentence each on why no `STATIC_RECORD_LAYOUT` is written and why a `COM_AXIS` table still carries its own count ("the image stores it, and the only other truthful description of those bytes is `RESERVED`").

- [ ] **Step 5: Run the tests to see them pass**

Run: `python -m pytest tests/test_point_counts.py tests/test_a2l.py tests/test_generation.py tests/test_documentation.py -q -p no:cacheprovider --no-cov`
Expected: PASS, with every existing a2l test unchanged.

- [ ] **Step 6: Commit and push**

```bash
git add src/ddd/backends/a2l docs/generated_artefacts.rst tests/test_point_counts.py
git commit -m "describe a table's leading point counts with NO_AXIS_PTS in its own record layout"
git push
```

---

### Task 7: `ddd compare` reports a changed convention as a changed interface

**Files:**
- Modify: `src/ddd/compare.py` (`_INTERFACE_FIELDS`, line 276)
- Test: `tests/test_point_counts.py`

**Interfaces:**
- Consumes: `ResolvedObject.point_counts`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_point_counts.py` (add `from ddd.compare import compare` and `from ddd.diagnostics import SeverityPolicy`):

```python
class TestCompare:
    def test_a_changed_convention_is_a_changed_interface(self, tree: Path) -> None:
        old, bag = run_analysis(tree / "old", files(axis("AX", 8)))
        assert old is not None, messages(bag)
        new, bag = run_analysis(tree / "new", files(axis("AX", 8), default="leading"))
        assert new is not None, messages(bag)
        verdict = DiagnosticBag(SeverityPolicy.from_strings(()))
        compare(old, new, verdict)
        assert checks(verdict) == ["changed-interface"]
        assert "point_counts" in messages(verdict)

    def test_an_unchanged_convention_is_not_a_finding(self, tree: Path) -> None:
        old, _ = run_analysis(tree / "old", files(axis("AX", 8), default="leading"))
        new, _ = run_analysis(tree / "new", files(axis("AX", 8), default="leading"))
        assert old is not None and new is not None
        verdict = DiagnosticBag(SeverityPolicy.from_strings(()))
        compare(old, new, verdict)
        assert checks(verdict) == []
```

- [ ] **Step 2: Run it to see it fail**

Run: `python -m pytest tests/test_point_counts.py::TestCompare -q -p no:cacheprovider --no-cov`
Expected: FAIL, `assert [] == ['changed-interface']`.

- [ ] **Step 3: Implement**

In `src/ddd/compare.py`, add a helper above `_INTERFACE_FIELDS`:

```python
def _point_counts(entry: Comparable) -> str:
    """The convention of a plain object; a structure member is never a table, so ``none``."""
    return entry.point_counts.value if isinstance(entry, ResolvedObject) else PointCounts.NONE.value
```

and append to `_INTERFACE_FIELDS`, after `shape`:

```python
    # Where a table keeps its point counts is layout, for the reason a bitfield's width is:
    # the size every reader declares changes, and the data moves behind the counts, so every
    # reader and every interpolation over it reads the wrong element whether or not it compiles.
    ComparedField("point_counts", _point_counts, _point_counts),
```

Import `PointCounts` from `ddd.models` and `ResolvedObject` from `ddd.ir` if either is missing. Check how `ComparedField`'s second callable is used (`lambda o: ...` rendering the value for the message) and match it. `_DEFERRED_INTERFACE_FIELDS` and the leaf tables are derived from this tuple and pick the field up by themselves.

- [ ] **Step 4: Run the tests to see them pass**

Run: `python -m pytest tests/test_point_counts.py tests/test_compare.py tests/test_comparison_tables.py -q -p no:cacheprovider --no-cov`
Expected: PASS. If a test in `test_comparison_tables.py` pins the list of interface fields, extend it with `point_counts`.

- [ ] **Step 5: Commit and push**

```bash
git add src/ddd/compare.py tests/test_point_counts.py tests/test_comparison_tables.py
git commit -m "report a table changing where it keeps its point counts as a changed interface"
git push
```

---

### Task 8: The address-map recipe reads only global symbols

**Files:**
- Modify: `docs/build_integration.rst` (the `cmake/AddressMap.cmake` block, line ~585)
- Test: `tests/test_cmake.py::TestTheDocumentedAddressMapRecipe` (runs the block as written)

- [ ] **Step 1: Change the recipe**

In the documented block, change

```cmake
   execute_process(COMMAND "${NM}" --defined-only --format=posix "${IMAGE}"
```

to

```cmake
   execute_process(COMMAND "${NM}" --defined-only --extern-only --format=posix "${IMAGE}"
```

and in the prose after the block ("Two things such a script has to get right."), add a sentence before it: "``--extern-only`` keeps the file-local statics out: every object a dictionary describes is a global, and two translation units each defining a ``static`` of one name would otherwise hand the map one symbol at two addresses, which ``load_address_map`` refuses."

- [ ] **Step 2: Run the recipe test**

Run: `python -m pytest tests/test_cmake.py::TestTheDocumentedAddressMapRecipe -q -p no:cacheprovider --no-cov`
Expected: PASS. The test also asserts `any(name.startswith("_") for name in extracted)`, meaning the c runtime's symbols are among those extracted. With `--extern-only` the runtime's global symbols stay. If that assertion now fails, the runtime's entries on this toolchain were all local. Then change the assertion to the documented intent (a project global such as `ValueA` is extracted, and a file-local static is not), without weakening what it proves about the >4 GB entries.

- [ ] **Step 3: Add a regression test for the case the request hit**

In `TestTheDocumentedAddressMapRecipe`, add a test that writes two extra `.c` files into the example project's sources, each defining `static int cntr_50ms_decimate_5 = 1;` plus a function using it, and adds them to the `firmware.elf` target. Build twice as `test_three_builds_settle_with_the_addresses_in_the_a2l` does, and assert that the second build succeeds and that `addresses.json` has no `cntr_50ms_decimate_5`. Reuse `self.write(tmp_path)` and append to the `CMakeLists.txt` it wrote, e.g. `target_sources(firmware.elf PRIVATE statics_a.c statics_b.c)`.

- [ ] **Step 4: Run it and commit**

Run: `python -m pytest tests/test_cmake.py::TestTheDocumentedAddressMapRecipe -q -p no:cacheprovider --no-cov`
Expected: PASS.

```bash
git add docs/build_integration.rst tests/test_cmake.py
git commit -m "keep file-local statics out of the documented address map"
git push
```

---

### Task 9: Documentation, changelog, and the full run

**Files:**
- Modify: `docs/data_dictionary.rst`, `SPEC.md`, `CHANGELOG.md`

- [ ] **Step 1: The data dictionary page**

In `docs/data_dictionary.rst`, add a section "Point counts ahead of a table" next to the one describing rasters or the component defaults (`grep -n "raster" docs/data_dictionary.rst`), saying:
- what the key does, the two values, where it may be stated (project, once; component, for what it defines), and that it follows the producer;
- the example from the spec: the dump bytes `10000000 10000000 ...` of a 16 x 16 `uint32` map, the c declaration `const uint32_t M[2 + (16) * (16)] = { 16U, 16U, ... };`, and the `RL_MAP_COUNTED_ULONG` layout;
- the two findings by name, linking to `consistency_checks`;
- that the resolved object carries `point_counts` from format 9 on.

Where the page lists the fields of a resolved object, add `point_counts`.

- [ ] **Step 2: SPEC.md**

Add `point_counts` (optional, `"none"` | `"leading"`) to the project keys list (near line 243, `"includes"`) and to the component keys, and add it to the resolved-object fields of the data dictionary section, with one sentence of meaning each, in the style of the neighbouring entries. Add the two checks to the consistency-check table of section 4, with their severities.

- [ ] **Step 3: CHANGELOG.md**

At the **end** of the `## Unreleased` list, not the top, add one entry. The GUI branch edits the top of that list, and appending keeps the merge clean:

```markdown
* **Tables that keep their point counts in front.**  A project states `"point_counts":
  "leading"` - once, in a project file, and a component may state otherwise for the curves,
  maps and axes it defines - when its firmware stores each table's number of axis points ahead
  of its data, in the table's own type.  The c declares such a table flat, counts first
  (`M[2 + (11) * (8)] = { 8, 11, ... }`), and the a2l describes it with `NO_AXIS_PTS_X` and
  `NO_AXIS_PTS_Y` ahead of `FNC_VALUES` or `AXIS_PTS_X` in a record layout of its own.  Two
  checks come with it: `point-counts-unrepresentable` refuses a table whose type cannot hold
  its counts, and `point-counts-mismatch` warns when a table and its axis disagree; `ddd
  compare` reports a changed convention as `changed-interface`.  The c templates are offered
  each object's `dimensions` and `point_counts`.  The dumped dictionary is format 9, adding
  `point_counts` to every object; a format 8 dictionary reads back unchanged.  The address map
  recipe of the build integration page now runs `nm --extern-only`, so two file-local statics
  sharing a name no longer make the map refuse to load.
```

`tests/test_documentation.py::...test_it_states_the_format_of_the_dictionary_it_ships` matches phrases like "dictionary is format N" in the Unreleased section: make sure any such phrase says 9. The one above says "is format 9", which it reads.

- [ ] **Step 4: Full run**

Run: `python -m pytest -q -p no:cacheprovider`
Expected: every test passes except the known symlink test, and coverage is `100.00%`. Cover any uncovered line or branch the report names with a test in `tests/test_point_counts.py`, never with a `pragma: no cover`.

Then run the linters the repository uses (`grep -n "ruff\|mypy" pyproject.toml requirements-dev.txt`), e.g. `ruff check src tests`, `ruff format --check src tests` and `mypy src`, and fix what they report.

- [ ] **Step 5: Commit and push**

```bash
git add docs/data_dictionary.rst SPEC.md CHANGELOG.md tests/test_point_counts.py
git commit -m "document where a table keeps its point counts"
git push
```
