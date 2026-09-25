# Fixing a disagreement from its finding — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `definition-mismatch` finding in `ddd gui` gains one button per key that disagrees,
taking the producing component's value across every declaration of the variable.

**Architecture:** The editor has offered this fix for some time; the page has not. Rather than
write it twice, the five action builders of `ddd.lsp.edits` stop returning protocol dictionaries
and return a **decision** — a title and the `Settled` tuple the rest of the tool already speaks.
The editor spells that as `TextEdit`s, the page as `Operation`s through the preview it already
has. The extraction lands first, on its own, and is proved by the editor's own test file coming
out of it unchanged.

**Tech Stack:** Python 3.13 (`ddd.lsp.edits`, `ddd.finding_fixes`, `ddd.gui.api`), and Ladle
stories for the page. No TypeScript beyond a stories file. No new dependency, either side.

**Spec:** [`docs/superpowers/specs/2026-09-25-gui-mismatch-fix-design.md`](../specs/2026-09-25-gui-mismatch-fix-design.md)

## Global Constraints

Copied from the spec. Every task's requirements include these.

- **The page offers the first of the editor's ordered pair only.** The editor offers up to two
  actions per key; `ordered = [given, taken] if produces else [taken, given]` at
  `lsp/edits.py:283`. The page takes `ordered[0]`.
- **Direction is never the reader's problem.** A consumer's finding offers the producing
  component's value; the producer's own finding sends its value outward.
- **The reach is the whole variable.** `settle` makes every declaration agree, so one press
  clears the finding on every file that carried it.
- **`limits` is never offered**, being in `DEFERRED_KEYS`: a declaration that omits them agrees
  with whoever states them.
- **`kind` is never offered**, being absent from `PROPAGATED_KEYS`. A mismatch differing only in
  `kind` gets no button at all.
- **Nothing is offered when there is no single producer**, nor when the settlement cannot
  complete. No button that always refuses.
- **No page change beyond a stories file.** `FindingPanelView` already draws every fix a finding
  carries, with a preview and an `Apply to N files`.
- **`tests/test_lsp.py` must not change in Task 1 or Task 2.** It is the proof the editor's
  answers did not move. `git diff 63a493f..HEAD -- tests/test_lsp.py` must print nothing at the
  end of each.
- **Python gate at 100 % of lines and branches**, no `pragma: no cover`, no skips. **A
  conditional expression registers no branch at all with coverage.py** — five defects reached
  part 9's review through that hole. Where an arm needs a test, write a statement or early
  returns; ruff's `SIM108` pushes the other way and early returns satisfy both.
- **No new dependency**, page or server. The rule has held since part 1.
- Commit messages end with `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`. Never
  `--amend`, never rebase.

## Prerequisites (before Task 1)

- Branch `feature/gui-mismatch-fix`, off master at `63a493f`, with the spec as its first commit
  `1540fa8`. Part 10 (plots) is merged; nothing here depends on it.
- Environment, **from the repository root, before changing directory**:
  `export PATH="$HOME/.local/node-v24.21.0/bin:$PWD/.venv/bin:$PATH"`.
- The Python gate, green before anything is touched:
  `python -m pytest && ruff check . && ruff format --check . && mypy`.
  `mypy` takes its targets from `pyproject.toml`; a bare `mypy .` adds noise that is not yours.
- The journeys need a browser Playwright has not downloaded on either machine. Run them as
  `PLAYWRIGHT_CHANNEL=chrome npm run e2e` (Linux) or `PLAYWRIGHT_CHANNEL=msedge` (Windows). A
  bare `npm run e2e` fails all 74 with `Executable doesn't exist at ~/.cache/ms-playwright/...`,
  which is the missing variable and not a broken install.

## Conventions for every task

- **Probe before you write.** Every claim this plan makes about existing code was checked against
  it, and earlier plans in this series were still wrong nine, eleven and four times. If the code
  disagrees with a step below, the code is right: say so in your report and do what is correct.
- **Never `page.waitForResponse`** in a journey. It broke part 6's CI and an existing task tracks
  the two that remain.
- Run the journeys after `npm run build`: they drive the **compiled** pages in
  `src/ddd/gui/static`, not Vite's dev server.
- Commit at the end of each task, with a message that says what changed and why.
- Do not dispatch subagents. Review arrives from the controller, after your report.

## File structure

| File | Responsible for |
| --- | --- |
| `src/ddd/lsp/edits.py` | **Modified.** `Reconciliation`; `settled_at` lifted out of `settle`; the five builders return decisions; one spelling layer turns a decision into a protocol action. Keeps every text concern: verbatim values, member indentation, the one comma a removal takes. |
| `src/ddd/finding_fixes.py` | **Modified.** `definition-mismatch` joins `missing-id`. `Fix` grows from one file to several. `fixes_for` gains the `Index`. |
| `src/ddd/gui/api.py` | **Modified.** `_fix` passes `revision.index` and previews a fix over several files. |
| `tests/test_lsp.py` | **Must not change** in Tasks 1 and 2. The proof the editor's answers held. |
| `tests/test_finding_fixes.py` | **Modified.** `TestAMismatch`; the existing `== ()` assertion inverts. |
| `tests/test_gui_api.py` | **Modified.** `/api/fix` over a mismatch. |
| `gui/src/components/FindingPanelView.stories.tsx` | **Modified.** Two stories: a mismatch offering two keys, one offering none. |
| `gui/e2e/findings.spec.ts` | **Modified.** One journey over a copy of the demo, on `ValueE`. |
| `CHANGELOG.md`, `docs/command_line_interface.rst` | **Modified.** What a reader is told. |

## Interfaces between the tasks

Task 1 produces these; Tasks 2 and 3 consume them. Names and types are exact.

```python
# src/ddd/lsp/edits.py

@dataclass(frozen=True, slots=True)
class Reconciliation:
    """One way to settle one key of one variable: decided, and not yet spelled."""

    title: str
    """What the button or the lightbulb says."""

    key: str
    """The definition key it settles, so a spelling knows which member to write."""

    settlement: Settlement
    """`changes` are the declarations that take the value; `unsettled` those that cannot, which
    the editor leaves out of its action and the page refuses over."""


def settled_at(
    built: Index, site: Site, name: str, key: str, raw: str | None, cache: dict[Path, Document]
) -> Settled | Unsettled | None:
    """What one declaration does about `raw` for `key`: take it, refuse it, or nothing at all.

    `None` where there is nothing to do - it already means that value, or it is deferring a key
    it may defer. The body of `settle`'s own loop, lifted so that an action changing one
    declaration asks that declaration the same question a whole settlement asks of each.
    """


def settle(
    built: Index, name: str, key: str, raw: str | None, cache: dict[Path, Document]
) -> Settlement:
    """Unchanged in behaviour: now a loop over `settled_at`."""
```

```python
# src/ddd/finding_fixes.py

@dataclass(frozen=True, slots=True)
class FileEdit:
    """What one fix writes in one file."""

    path: Path
    operations: tuple[Operation, ...]


@dataclass(frozen=True, slots=True)
class Fix:
    """One fix a finding carries."""

    title: str
    changes: tuple[FileEdit, ...]
    """One per file, in the order the settlement names them. `missing-id` has exactly one."""


def fixes_for(
    check: str, path: Path, pointer: str, cache: dict[Path, Document], built: Index
) -> tuple[Fix, ...]:
    """The fixes the finding filed at `pointer` of `path` carries, in the order to offer them."""
```

`Fix.path` and `Fix.operations` are gone. `api.py:741` and every test that reads them changes
with the shape.

---

### Task 1: The decision, and the three actions that change one declaration

**Files:**
- Modify: `src/ddd/lsp/edits.py` — `settle` (403-441), `_adopt` (507-556), `_from_producer`
  (558-586), `_remove_here` (589-640)
- Must not change: `tests/test_lsp.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `Reconciliation`, `settled_at`, and `_protocol_action`, as spelled in *Interfaces
  between the tasks*.

**What this task is.** Three of the five builders change exactly one declaration — the one the
cursor is in. Each decides for itself whether that declaration may take the value, by calling
`_assign` or `_erase` and treating `None` as "no action". Those refusals are decisions, and
`settle` already makes the same ones for every declaration it reaches. This task lifts `settle`'s
loop body into `settled_at`, points the three builders at it, and gives them a decision to return
instead of a protocol dictionary.

**The proof.** `tests/test_lsp.py` must not be edited. 332 tests, 25 places asserting the action
titles, at 100 % branch coverage. If the editor's answers moved, one of them would have to move
too. The last step checks it mechanically.

- [ ] **Step 1: Read the four functions you are about to change, in full.**

Run: `sed -n '403,441p;507,640p' src/ddd/lsp/edits.py`

They are dense and every clause is load-bearing. Two in particular:

- `_adopt` and `_remove_here` **withhold entirely** when any other declaration is unreachable,
  because their titles make a claim about all of them — "*A declaration drifted out of reach is
  not the same as one that agrees*". That stays in the builder, which reads the others itself.
- `_assign` refuses three things and `_erase` refuses two. Four of those five are `settled_at`'s
  to make from now on. The fifth — `_erase`'s only child — stays in the spelling, for the reason
  in Step 6.

- [ ] **Step 2: Write the failing test for `settled_at`**

Add to `tests/test_lsp.py`… **no.** That file must not change. Put it in a new file,
`tests/test_lsp_decisions.py`:

```python
"""The decision a settlement makes about one declaration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from conftest import component, declare, project, write_tree
from ddd.diagnostics import DiagnosticBag
from ddd.loading import load_workspace
from ddd.lsp.edits import settled_at
from ddd.lsp.navigation import Index, Site, index
from ddd.lsp.ranges import Document


def built_of(tmp_path: Path, **files: Any) -> tuple[Index, Path]:
    write_tree(tmp_path, {"p.ddd.json": project("P", *files), **files})
    workspace = load_workspace(tmp_path / "p.ddd.json", DiagnosticBag())
    assert workspace is not None
    return index(workspace), tmp_path


class TestOneDeclaration:
    def test_a_declaration_that_can_take_the_value_takes_it(self, tmp_path: Path) -> None:
        built, root = built_of(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="Hz")),
            },
        )
        site = Site(root / "b.ddd.json", "component.interface[0].definition")
        cache: dict[Path, Document] = {}
        decided = settled_at(built, site, "Speed", "unit", '"rpm"', cache)
        assert decided is not None
        assert (decided.site, decided.raw) == (site, '"rpm"')

    def test_a_declaration_that_already_means_it_does_nothing(self, tmp_path: Path) -> None:
        built, root = built_of(
            tmp_path,
            **{"a.ddd.json": component("A", declare("output", "Speed", unit="rpm"))},
        )
        site = Site(root / "a.ddd.json", "component.interface[0].definition")
        assert settled_at(built, site, "Speed", "unit", '"rpm"', {}) is None
```

- [ ] **Step 3: Run it and watch it fail**

Run: `python -m pytest tests/test_lsp_decisions.py -q`
Expected: FAIL with `ImportError: cannot import name 'settled_at' from 'ddd.lsp.edits'`.

- [ ] **Step 4: Lift `settle`'s loop body into `settled_at`**

The lift is exact — every line below is `settle`'s, in its order, with `continue` becoming
`return None` and each `append` becoming a `return`:

```python
def settled_at(
    built: Index, site: Site, name: str, key: str, raw: str | None, cache: dict[Path, Document]
) -> Settled | Unsettled | None:
    """What one declaration does about ``raw`` for ``key``: take it, refuse it, or nothing.

    ``None`` where there is nothing to do - the declaration already means that value, or it is
    leaving a deferred key to whoever states it. The body of :func:`settle`'s own loop, lifted
    so that an action changing one declaration asks it the same question a whole settlement
    asks of each: the two must not drift into two readings of "can this declaration take it".
    """
    document = _at_site(site, name, cache)
    if document is None:
        return Unsettled(site, "unreachable")
    typename = document.value_at(f"{site.pointer}.typename")
    if key in MEANING_KEYS and isinstance(typename, str):
        if _fixed_by(built, typename, key, cache) != raw:
            return Unsettled(site, "type", typename)
        return None
    stated = document.raw_at(f"{site.pointer}.{key}")
    if _already(key, stated, raw) or (key in DEFERRED_KEYS and stated is None):
        return None
    accepted, required = _keys_of(document, site.pointer)
    if (raw is None and key in required) or (raw is not None and key not in accepted):
        return Unsettled(site, "kind")
    return Settled(site, raw)


def settle(
    built: Index, name: str, key: str, raw: str | None, cache: dict[Path, Document]
) -> Settlement:
    """Which declarations of ``name`` change for every one of them to state ``raw`` as ``key``,
    and which of them cannot.

    One rule for two callers. The language server's "Apply this unit to N other declarations"
    leaves out what cannot change and offers the rest; ``ddd gui`` refuses the whole change
    instead, because its reader chose a value for the variable and a change that reaches only
    some of its declarations is not the one they chose. Deciding here, once, is what keeps the
    editor and the page from disagreeing about what a change touches.
    """
    changes: list[Settled] = []
    unsettled: list[Unsettled] = []
    for site in built.declarations.get(name, ()):
        decided = settled_at(built, site, name, key, raw, cache)
        if isinstance(decided, Settled):
            changes.append(decided)
        elif decided is not None:
            unsettled.append(decided)
    return Settlement(tuple(changes), tuple(unsettled))
```

The two paragraphs of `settle`'s docstring that described a declaration already stating the
value, and one naming a declared type, move to `settled_at` — that is where those decisions now
are. Do not leave them in both.

- [ ] **Step 5: Run the whole Python suite**

Run: `python -m pytest -q`
Expected: PASS, and coverage still 100 %. `settle`'s callers are unchanged, so nothing else
should move. If anything fails here, the lift was not exact — compare line by line rather than
guessing.

- [ ] **Step 6: Add `Reconciliation` and the spelling layer**

```python
@dataclass(frozen=True, slots=True)
class Reconciliation:
    """One way to settle one key of one variable: decided, and not yet spelled.

    What the two clients share. The decision is which declarations come to state what, which is
    a question about the project; how that arrives in a file is a question about text, and the
    two have no business being one function. :mod:`ddd.finding_fixes` spells this as operations
    on json pointers, this module as edits with ranges.
    """

    title: str
    key: str
    settlement: Settlement


def _protocol_action(reconciliation: Reconciliation, cache: dict[Path, Document]) -> dict[str, Any]:
    """A decision as the protocol carries it: a titled quick fix over one or more files.

    ``_assign`` and ``_erase`` answer ``None`` for a change the decision already ruled out, so
    nothing here is expected to skip; the guard is the only-child refusal of :func:`_erase`,
    which stays a question about a file's own style rather than about the data.
    """
    changes: dict[str, list[dict[str, Any]]] = {}
    for change in reconciliation.settlement.changes:
        document = read(change.site.path, cache)
        edit = (
            _erase(document, change.site.pointer, reconciliation.key)
            if change.raw is None
            else _assign(document, change.site.pointer, reconciliation.key, change.raw)
        )
        if edit is not None:
            changes.setdefault(change.site.path.as_uri(), []).append(edit)
    return {"title": reconciliation.title, "kind": QUICK_FIX, "edit": {"changes": changes}}
```

**Why `_erase`'s only-child guard stays here and does not move to `settled_at`.** The spec says
three refusals move; it is two, and this is the third. `_erase` refuses to empty an object
because "what to leave between the braces is a judgement about the file's style rather than about
the data", and its own docstring adds that it "cannot arise for these keys anyway - every
definition has a ``name`` beside them". Moving an unreachable refusal into `settled_at` would put
a branch in the decision layer that no test can cover and the 100 % gate would then be unable to
hold. Left here, it is inside an `or` chain whose other arms are reachable. Say this in your
report; it is a correction to the spec, not an oversight of it.

- [ ] **Step 7: Point the three single-declaration builders at the decision**

`_from_producer` in full. Note that the four conditions the old body spelled out — `raw is None`,
`raw == mine`, a deferred key not stated here, and everything `_assign` refused — are now three
lines: `raw is None`, and `settled_at` answering anything but `Settled`.

```python
def _from_producer(
    built: Index, here: Site, document: Document, name: str, key: str, cache: dict[Path, Document]
) -> Reconciliation | None:
    """Take the value the producing component states, into the declaration asked at.

    The direction that reads naturally from a consumer. A component that reads a variable is
    describing what it expects to find, and the component that writes it is the one that
    decides - so "use what the producer says" is a fix, where "make the producer say what I
    say" is a consumer redefining data it does not own.
    """
    producers = [site for site in built.producers.get(name, ()) if site != here]
    if len(producers) != 1:
        # No producer, or several - which is its own finding, and not one to guess through.
        return None
    producer = producers[0]
    target = _at_site(producer, name, cache)
    raw = None if target is None else target.raw_at(f"{producer.pointer}.{key}")
    if raw is None:
        return None
    decided = settled_at(built, here, name, key, raw, cache)
    if not isinstance(decided, Settled):
        return None
    owner = producer.path.stem.removesuffix(".ddd")
    return Reconciliation(f"Use the {key} declared in {owner}", key, Settlement((decided,), ()))
```

`_adopt` keeps its whole gathering half — the unanimity by meaning, and the withholding when any
other declaration is unreachable — and changes only its last four lines:

```python
    decided = settled_at(built, here, name, key, next(iter(stated.values())), cache)
    if not isinstance(decided, Settled):
        return None
    return Reconciliation(
        f"Take the {key} the other declarations of '{name}' state", key,
        Settlement((decided,), ()),
    )
```

`_remove_here` keeps its gathering half too, and loses its own `key in _keys_of(...)[1]` guard,
which `settled_at` makes as `Unsettled(site, "kind")` when `raw is None` and the key is required:

```python
    decided = settled_at(built, here, name, key, None, cache)
    if not isinstance(decided, Settled):
        return None
    producers = [site for site in built.producers.get(name, ()) if site != here]
    where = (
        f"which {producers[0].path.stem.removesuffix('.ddd')} does not declare"
        if len(producers) == 1
        else f"which no other declaration of '{name}' has"
    )
    return Reconciliation(f"Remove this {key}, {where}", key, Settlement((decided,), ()))
```

- [ ] **Step 8: Spell the three at the call site**

In `_on_the_declaration`, the three now answer `Reconciliation | None` while `_propagate` and
`_remove_elsewhere` still answer protocol dictionaries. Spell only what has changed, and leave
Task 2's two alone:

```python
        taken = (
            _from_producer(built, here, document, name, candidate, cache)
            or _remove_here(built, here, document, name, candidate, cache)
            or _adopt(built, here, document, name, candidate, cache)
        )
        given = _propagate(built, here, document, name, candidate, cache) or _remove_elsewhere(
            built, here, document, name, candidate, cache
        )
        spelled = None if taken is None else _protocol_action(taken, cache)
        ordered = [given, spelled] if produces else [spelled, given]
```

- [ ] **Step 9: Run the whole Python suite and the gate**

Run: `python -m pytest -q && ruff check . && ruff format --check . && mypy`
Expected: PASS, 100 % line and branch.

- [ ] **Step 10: Prove the editor's answers did not move**

Run: `git diff --stat 63a493f..HEAD -- tests/test_lsp.py`
Expected: **no output.** One edited line there means the refactor changed what the editor says,
and the change is wrong until you can say why it is right.

Then capture what the examples offer, as a supplement. Write
`<scratch>/capture-actions.py`:

```python
"""Every action `ddd.lsp.edits.actions` offers over the example projects, as stable json."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from ddd.diagnostics import DiagnosticBag
from ddd.loading import load_workspace
from ddd.lsp.edits import actions
from ddd.lsp.navigation import index
from ddd.lsp.ranges import Document, read

out: dict[str, object] = {}
for root in sorted(Path("examples").glob("*/*.ddd.json")):
    workspace = load_workspace(root, DiagnosticBag())
    if workspace is None:
        continue
    built = index(workspace)
    for loaded in workspace.components:
        for position, _ in enumerate(loaded.component.interface):
            where = loaded.declaration_location(position, "definition")
            cache: dict[Path, Document] = {}
            offered = actions(built, where.path, read(where.path, cache), where.pointer, cache)
            if offered:
                out[f"{root.as_posix()}|{where.path.as_posix()}|{where.pointer}"] = offered
json.dump(out, sys.stdout, indent=1, sort_keys=True, default=str)
```

Run it on `63a493f` and on your head, and `diff` the two. **Expect no difference, and expect the
capture to be small**: it finds 3 declaration sites and 6 actions, every one of them
`_propagate`'s, because `SharedValue` has two producers and every declaration of it states its
keys. It covers none of the three functions this task changed. It is a supplement to the
untouched test file, not a substitute for it — do not report it as though it proved anything
about `_from_producer`.

- [ ] **Step 11: Commit**

```bash
git add src/ddd/lsp/edits.py tests/test_lsp_decisions.py
git commit -m "decide what a declaration does about a value in one place"
```

### Task 2: The two actions that change the other declarations

**Files:**
- Modify: `src/ddd/lsp/edits.py` — `_propagate` (699-729), `_remove_elsewhere` (642-677),
  `_on_the_declaration` (283-287)
- Modify: `tests/test_lsp_decisions.py`
- Must not change: `tests/test_lsp.py`

**Interfaces:**
- Consumes: `Reconciliation`, `settled_at`, `_protocol_action` from Task 1.
- Produces: all five builders answering `Reconciliation | None`, and
  `reconciliations(built, path, document, pointer, cache) -> list[Reconciliation]` — the public
  seam Task 3 consumes, ordered producer-first, at most two per key.

**What this task is.** The other two builders already reach several files, and `_propagate`
already delegates its decision to `settle` — its own comment says every check `_assign` makes was
already made, and asserts the edit is never `None`. So `_propagate` is nearly a rename.
`_remove_elsewhere` decides per site and must keep one difference from `settle`: it **skips** an
unreachable declaration where `settled_at` reports it `Unsettled`. Both behaviours are correct
for the editor, which offers what it can; the page refuses over `unsettled`, which is why the
decision carries both.

- [ ] **Step 1: Write the failing test for a decision over several files**

Add to `tests/test_lsp_decisions.py`:

```python
class TestTheOtherDeclarations:
    def test_a_value_sent_out_names_every_declaration_that_takes_it(
        self, tmp_path: Path
    ) -> None:
        built, root = built_of(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="Hz")),
                "c.ddd.json": component("C", declare("input", "Speed", unit="Hz")),
            },
        )
        here = Site(root / "a.ddd.json", "component.interface[0].definition")
        document = read(here.path, {})
        decision = _propagate(built, here, document, "Speed", "unit", {})
        assert decision is not None
        assert decision.title == "Apply this unit to 2 other declarations of 'Speed'"
        assert {change.site.path.name for change in decision.settlement.changes} == {
            "b.ddd.json",
            "c.ddd.json",
        }
        assert all(change.raw == '"rpm"' for change in decision.settlement.changes)
```

Import `_propagate` and `read` at the top of the file with the rest.

- [ ] **Step 2: Run it and watch it fail**

Run: `python -m pytest tests/test_lsp_decisions.py::TestTheOtherDeclarations -q`
Expected: FAIL — `_propagate` still answers a dictionary, so `decision.title` raises
`AttributeError`.

- [ ] **Step 3: Rewrite `_propagate` as a decision**

The count in the title comes from the settlement now, where it used to come from the edits
`_assign` produced. Those are the same number: the old body asserted every edit was non-`None`
precisely because `settle` had already decided each one.

```python
def _propagate(
    built: Index, here: Site, document: Document, name: str, key: str, cache: dict[Path, Document]
) -> Reconciliation | None:
    """One action, or nothing when every other declaration already says the same.

    Which declarations it reaches is :func:`settle`'s to say, as it is for ``ddd gui``. One that
    cannot take the value is left out of the action rather than refusing it: the others can
    still be reconciled from here, and an editor offers what it can.
    """
    raw = document.raw_at(f"{here.pointer}.{key}")
    if raw is None:
        return None
    settlement = settle(built, name, key, raw, cache)
    elsewhere = len(settlement.changes)
    if elsewhere == 0:
        return None
    return Reconciliation(
        f"Apply this {key} to {elsewhere} other declaration"
        f"{'s' if elsewhere != 1 else ''} of '{name}'",
        key,
        settlement,
    )
```

`settle` never returns `here` among its changes when `here` already states `raw`: `_already`
answers true for it. Do not add a filter for that — adding one would be a branch no input can
take, and the gate would then be unable to cover it.

- [ ] **Step 4: Rewrite `_remove_elsewhere` as a decision**

Its loop keeps skipping what it cannot change, which `settled_at` now reports rather than the
loop working out:

```python
def _remove_elsewhere(
    built: Index, here: Site, document: Document, name: str, key: str, cache: dict[Path, Document]
) -> Reconciliation | None:
    """Take the key out of the other declarations, when this one does not state it.

    The mirror of spreading a value, and the direction that was missing: a declaration with no
    ``unit`` could take one from the others but never say "none of you should have one
    either". Both are ways of agreeing, and which one is meant is the author's to choose.

    What cannot lose the key is left out rather than refusing the action, as it is for
    :func:`_propagate`: an editor offers what it can.
    """
    if key in DEFERRED_KEYS or document.raw_at(f"{here.pointer}.{key}") is not None:
        return None
    changes = tuple(
        decided
        for site in built.declarations.get(name, ())
        if site != here
        and isinstance(decided := settled_at(built, site, name, key, None, cache), Settled)
    )
    elsewhere = len(changes)
    if elsewhere == 0:
        return None
    return Reconciliation(
        f"Remove the {key} from {elsewhere} other declaration"
        f"{'s' if elsewhere != 1 else ''} of '{name}'",
        key,
        Settlement(changes, ()),
    )
```

**Two things to check rather than assume**, and to say which way they went in your report:

1. The old loop called `_erase` and dropped a site when it answered `None` — for an absent key,
   for a required key, and for an only child. `settled_at` covers the first two. The third it
   does not, so a site whose definition holds nothing but this key would now be listed. Every
   definition states a `name` beside its keys, so no input reaches it; confirm that by reading
   `definition_keys`, and do not add a guard for a case you cannot write a test for.
2. The old loop `continue`d past an unreachable declaration silently. The comprehension above
   does the same, because `settled_at` answers `Unsettled` and the `isinstance` drops it.

- [ ] **Step 5: Lift the ordering into a public `reconciliations`, and spell it**

With all five answering one shape, the half of `_on_the_declaration` that decides becomes a
function the page can call. Delete the `spelled` line Task 1 added.

```python
def reconciliations(
    built: Index, path: Path, document: Document, pointer: str, cache: dict[Path, Document]
) -> list[Reconciliation]:
    """Every way to settle the declaration at ``pointer``, in the order to offer them.

    On a key that can be propagated, that key; anywhere else inside the declaration, every key
    that differs from the other declarations. Two ways at most per key - somebody else's answer
    brought here, and this one's answer sent out - ordered by which side owns the variable.

    Public because ``ddd gui`` offers the first of each key's pair from a finding, and must
    order them the way the editor does or the two clients disagree about which fix is the
    natural one.
    """
    within = WITHIN_DEFINITION.match(pointer)
    if within is None:
        return []
    definition = within.group()
    name = document.value_at(f"{definition}.name")
    if not isinstance(name, str):
        return []
    key = pointer.rsplit(".", 1)[-1]
    if pointer == f"{definition}.{key}" and key in PROPAGATED_KEYS:
        wanted = [key]
    else:
        wanted = interface_keys(document.value_at(definition)) + _missing(
            built, path, document, name, definition, cache
        )
    here = Site(path, definition)
    produces = here in built.producers.get(name, ())
    offered: list[Reconciliation] = []
    for candidate in wanted:
        # Two ways to settle a key, and at most one of each. Taking is somebody else's answer
        # brought here - the producer's for preference, the one the rest agree on otherwise,
        # or their silence. Giving is this declaration's answer sent out, value or silence.
        taken = (
            _from_producer(built, here, document, name, candidate, cache)
            or _remove_here(built, here, document, name, candidate, cache)
            or _adopt(built, here, document, name, candidate, cache)
        )
        given = _propagate(built, here, document, name, candidate, cache) or _remove_elsewhere(
            built, here, document, name, candidate, cache
        )
        # A consumer is offered the producer's value first; the producer is offered its own,
        # outward. Which side owns the variable is not a matter of taste here - it is the rule
        # the whole tool is built on, and the fix that reads naturally is the one that follows
        # it rather than the one that quietly redefines somebody else's data.
        ordered = [given, taken] if produces else [taken, given]
        offered.extend(action for action in ordered if action is not None)
    return offered
```

`_on_the_declaration` keeps everything about the protocol — the `diagnostics` it attaches, the
`isPreferred` slot, and the identity action appended after:

```python
    offered = [
        _protocol_action(action, cache)
        for action in reconciliations(built, path, document, pointer, cache)
    ]
    settles = [entry for entry in reported if entry.get("code") in RECONCILED]
```

Everything from `settles` down is unchanged. The `within`/`name` guards at the top of
`_on_the_declaration` are now `reconciliations`' — but `_give_an_identity` below still needs
`definition`, so keep the guards in both. Two readings of "is this a declaration" is the one
duplication this split costs; say so in your report rather than deleting a guard that is load
bearing.

- [ ] **Step 6: Run the whole Python suite and the gate**

Run: `python -m pytest -q && ruff check . && ruff format --check . && mypy`
Expected: PASS at 100 % line and branch.

- [ ] **Step 7: Prove the editor's answers did not move, again**

Run: `git diff --stat 63a493f..HEAD -- tests/test_lsp.py`
Expected: no output.

Run the capture script from Task 1 Step 10 against `63a493f` and against your head, and `diff`.
Expected: identical. This time it means something for `_propagate`, whose six actions are the
whole of what it finds.

- [ ] **Step 8: Commit**

```bash
git add src/ddd/lsp/edits.py tests/test_lsp_decisions.py
git commit -m "let an action say which declarations change, not how their files read"
```

### Task 3: The fix the page offers

**Files:**
- Modify: `src/ddd/finding_fixes.py`
- Modify: `src/ddd/gui/api.py` — `_fix` (728-750)
- Modify: `tests/test_finding_fixes.py`, `tests/test_gui_api.py`

**Interfaces:**
- Consumes: `Reconciliation`, `reconciliations` from Task 2.
- Produces: `FileEdit`, the new `Fix`, and `fixes_for(check, path, pointer, cache, built)` as
  spelled in *Interfaces between the tasks*.

**What this task is.** `definition-mismatch` joins `missing-id`. For each key the declaration
disagrees on, the page takes **the first of that key's ordered pair** and spells it as operations.
A fix whose settlement cannot complete is dropped rather than offered — no button that refuses.

- [ ] **Step 1: Write the failing tests**

In `tests/test_finding_fixes.py`, below `TestAnIdentity`. `built_of` is the helper Task 1 wrote
in `tests/test_lsp_decisions.py`; copy it rather than importing across test modules, which this
repository does not do:

```python
class TestAMismatch:
    def test_a_consumer_is_offered_the_producer_s_value(self, tmp_path: Path) -> None:
        built, root = built_of(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="Hz")),
            },
        )
        offered = fixes_for("definition-mismatch", root / "b.ddd.json", DEFINITION, {}, built)
        assert [fix.title for fix in offered] == ["Use the unit declared in a"]
        (edit,) = offered[0].changes
        assert edit.path == root / "b.ddd.json"
        assert [(o.op, o.pointer, o.raw) for o in edit.operations] == [
            ("set", f"{DEFINITION}.unit", '"rpm"')
        ]

    def test_the_producer_is_offered_its_own_value_outward(self, tmp_path: Path) -> None:
        built, root = built_of(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="Hz")),
                "c.ddd.json": component("C", declare("input", "Speed", unit="Hz")),
            },
        )
        offered = fixes_for("definition-mismatch", root / "a.ddd.json", DEFINITION, {}, built)
        assert [fix.title for fix in offered] == [
            "Apply this unit to 2 other declarations of 'Speed'"
        ]
        assert {edit.path.name for edit in offered[0].changes} == {"b.ddd.json", "c.ddd.json"}

    def test_two_keys_disagreeing_are_two_fixes(self, tmp_path: Path) -> None:
        built, root = built_of(
            tmp_path,
            **{
                "a.ddd.json": component(
                    "A", declare("output", "Speed", unit="rpm", datatype="uint16")
                ),
                "b.ddd.json": component(
                    "B", declare("input", "Speed", unit="Hz", datatype="uint8")
                ),
            },
        )
        offered = fixes_for("definition-mismatch", root / "b.ddd.json", DEFINITION, {}, built)
        assert [fix.title for fix in offered] == [
            "Use the datatype declared in a",
            "Use the unit declared in a",
        ]
```

And the three silences the spec binds, each of which is a rule a reader would otherwise have to
discover:

```python
    def test_a_variable_with_two_producers_is_offered_nothing(self, tmp_path: Path) -> None:
        # The case `examples/inconsistent` is: `SharedValue` written by two components. There is
        # no producer whose value is *the* producer's, and picking one would be guessing.
        built, root = built_of(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("output", "Speed", unit="rpm")),
                "c.ddd.json": component("C", declare("input", "Speed", unit="Hz")),
            },
        )
        assert fixes_for("definition-mismatch", root / "c.ddd.json", DEFINITION, {}, built) == ()

    def test_a_declaration_that_cannot_take_the_value_stops_the_fix_being_offered(
        self, tmp_path: Path
    ) -> None:
        # A third declaration naming a type that fixes the key cannot take any other value, so
        # the settlement cannot complete and the page offers no button rather than one that
        # refuses. The reason is still a click away, in the variable's own panel.
        built, root = built_of(
            tmp_path,
            **{
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="Hz")),
                "c.ddd.json": component("C", declare("input", "Speed", typename="Speed_t")),
                "t.ddd.json": types(scalar_type("Speed_t", unit="kPa")),
            },
        )
        # Asserted first, so this cannot pass by the fixture quietly having no mismatch at all:
        # `c` really is the declaration that cannot move, and `b` really is the one that would.
        settlement = settle(built, "Speed", "unit", '"rpm"', {})
        assert [change.site.path.name for change in settlement.changes] == ["b.ddd.json"]
        assert [(u.site.path.name, u.reason, u.type_name) for u in settlement.unsettled] == [
            ("c.ddd.json", "type", "Speed_t")
        ]
        assert fixes_for("definition-mismatch", root / "b.ddd.json", DEFINITION, {}, built) == ()
```

That fixture was run before this plan was written and answers exactly those two lines; import
`scalar_type`, `types` and `settle` alongside the rest. Asserting the settlement before asserting
the empty tuple is the point of it — an empty tuple is what a fixture with no mismatch at all
would also produce, and part 9 shipped a test that asserted nothing for want of that check.

There is no test for `kind` here because there is nothing to test in this module: `kind` is
absent from `PROPAGATED_KEYS`, so `interface_keys` never names it and no builder is ever asked.
Task 7's hand-driving is where that is confirmed against the running application.

The order of the two titles in `test_two_keys_disagreeing_are_two_fixes` was **measured, not
reasoned**: `actions()` over exactly that fixture answers

```
Use the datatype declared in a
Apply this datatype to 1 other declaration of 'Speed'
Use the unit declared in a
Apply this unit to 1 other declaration of 'Speed'
```

`interface_keys` reads the keys in the order the file writes them, and `declare` puts `datatype`
in before the `**definition` that carries `unit`. Taking the first of each key's pair leaves the
two `Use the …` titles, in that order.

And the existing assertion inverts — `tests/test_finding_fixes.py:72` reads:

```python
        assert fixes_for("definition-mismatch", root / "a.ddd.json", DEFINITION, {}) == ()
```

Its tree is a lone component, so there is nobody to disagree with. Give it the fifth argument and
keep the assertion: a variable one component declares has no mismatch and no fix. Rename it to
say that — `test_a_lone_declaration_has_nothing_to_reconcile`.

- [ ] **Step 2: Run them and watch them fail**

Run: `python -m pytest tests/test_finding_fixes.py -q`
Expected: FAIL — `fixes_for() takes 4 positional arguments but 5 were given`.

- [ ] **Step 3: Grow `Fix` to several files**

```python
@dataclass(frozen=True, slots=True)
class FileEdit:
    """What one fix writes in one file."""

    path: Path
    operations: tuple[Operation, ...]


@dataclass(frozen=True, slots=True)
class Fix:
    """One fix a finding carries."""

    title: str
    """What the button says, naming the thing it changes."""

    changes: tuple[FileEdit, ...]
    """One per file, in the order the settlement names them. An identity has exactly one; a
    reconciliation has as many as the variable has declarations that must move."""
```

The module docstring says "One file per fix, because that is what a fix is: a change reaching
several files is a plan". That is no longer true and was a statement about what had been built
rather than about what a fix is — the editor's own reconcile actions have reached several files
since they existed. Replace that paragraph with what is now the case: a fix carries whatever
files its decision names, and the page previews each before anything is written.

- [ ] **Step 4: Add the mismatch**

```python
MISMATCH: Final = "definition-mismatch"
"""Two components describing one variable differently - the finding this tool exists to file,
and until now the one it could only describe."""


def fixes_for(
    check: str, path: Path, pointer: str, cache: dict[Path, Document], built: Index
) -> tuple[Fix, ...]:
    """The fixes the finding filed at ``pointer`` of ``path`` carries, in the order to offer
    them.

    Empty for every check but two, and empty for those wherever the declaration they name has
    moved on since the analysis: a file is read here as it stands now, and a fix planned against
    something that is no longer there would be refused by the engine anyway - with a sentence
    about fingerprints rather than about the declaration.
    """
    if check == MISSING_ID:
        return _an_identity(path, pointer, cache)
    if check == MISMATCH:
        return _reconciled(built, path, pointer, cache)
    return ()


def _reconciled(
    built: Index, path: Path, pointer: str, cache: dict[Path, Document]
) -> tuple[Fix, ...]:
    """One fix per key the declaration disagrees on: the first of that key's ordered pair.

    The editor offers up to two ways to settle a key and lets the reader pick; the page offers
    the one that follows the ownership rule - a consumer takes the producer's value, the
    producer sends its own out - because a button whose direction the reader has to work out is
    not the one press this exists to be. The other way is a click away, in the variable's own
    panel, which settles any value the reader chooses.

    A settlement that cannot reach every declaration is dropped rather than offered. The page
    refuses a partial settlement, so the button would do nothing but explain itself, and a fix
    that does nothing teaches a reader to stop reading the fixes.
    """
    document = read(path, cache)
    seen: set[str] = set()
    fixes: list[Fix] = []
    for decision in reconciliations(built, path, document, pointer, cache):
        if decision.key in seen:
            continue
        seen.add(decision.key)
        if decision.settlement.unsettled:
            continue
        fixes.append(Fix(decision.title, _written(decision)))
    return tuple(fixes)


def _written(decision: Reconciliation) -> tuple[FileEdit, ...]:
    """A decision as operations, file by file, the way ``ddd.variables.preview`` spells one."""
    operations: dict[Path, list[Operation]] = {}
    for change in decision.settlement.changes:
        pointer = f"{change.site.pointer}.{decision.key}"
        made = (
            Operation("remove", pointer)
            if change.raw is None
            else Operation("set", pointer, change.raw)
        )
        operations.setdefault(change.site.path, []).append(made)
    return tuple(FileEdit(path, tuple(made)) for path, made in operations.items())
```

`_written` is `ddd.variables.preview`'s first half, which builds the same dictionary before
handing it to the edit engine. **Check whether that half can be shared** rather than written
twice — `preview` takes a `Settlement` and a key and returns `Planned`, so the split would be a
new function there returning the dictionary. If sharing it costs more than the eight lines above,
say so in your report and leave the two; if it does not, share it.

Move `missing-id`'s body into `_an_identity(path, pointer, cache)` unchanged but for returning
`(Fix(title, (FileEdit(path, (operation,)),)),)`.

- [ ] **Step 5: Run the tests**

Run: `python -m pytest tests/test_finding_fixes.py -q`
Expected: PASS.

- [ ] **Step 6: Wire the api**

`src/ddd/gui/api.py`, `_fix`. The index may be absent — `_settle` above guards it as
`if built is None or name not in built.declarations`, and `_values` has the same shape. A
revision with no index has no declarations to reconcile, so answer no fixes rather than an error:

Import `Index` from `ddd.lsp.navigation`. **Do not write `built or Index()`**: an `or` inside an
expression is a branch `coverage.py` does not count, so the arm that handles a revision with no
index would be untested and the 100 % gate would not notice. Write it as a statement, and cover
both arms — `_settle` above guards the same field, so a test for the absent case already has a
shape to follow.

```python
        cache: dict[Path, Document] = {}
        stamps = {f.path.resolve(): f.fingerprint for f in revision.files}
        built = revision.index
        if built is None:
            # No index, no declarations - a revision whose project did not load has nothing to
            # reconcile, and answering no fixes is truer than answering an error.
            built = Index()
        offered = []
        for fix in fixes_for(check, source.path, pointer, cache, built):
            try:
                made = [planned(edit.path, edit.operations, stamps) for edit in fix.changes]
            except EditError as refused:
                return _error(409 if refused.code in REFUSALS else 500, refused.code, str(refused))
            offered.append({"title": fix.title, "changes": _planned_changes(made)})
```

`_planned_changes` already takes a list — the single-element `[made]` it was given is what made
the old call read as though a fix were one file. Confirm its signature before relying on this.

Add to `tests/test_gui_api.py`, beside the existing `/api/fix` tests. Read the `missing-id` one
first — it builds a project on disk, opens it through the api, and asserts the reply — and write
this one the same way, asserting three things the unit tests above cannot:

- the reply's `fixes` has exactly one entry, with title `Use the unit declared in a`;
- its `changes` has one element, whose `path` is the consumer's file and whose `hunks` are
  non-empty — the preview really reached the edit engine;
- `revision` is the revision the fix was computed from, as the `missing-id` test asserts.

And one for the absent index, which the `if built is None` arm above needs: a revision whose
project did not load answers `200` with no fixes, not an error. Find how the existing tests
produce such a revision — `_values` and `_settle` both guard the same field, so a fixture exists.

- [ ] **Step 7: Run the whole Python gate**

Run: `python -m pytest -q && ruff check . && ruff format --check . && mypy`
Expected: PASS at 100 % line and branch.

Run: `git diff --stat 63a493f..HEAD -- tests/test_lsp.py`
Expected: still no output. This task does not touch the editor, and that is worth proving twice.

- [ ] **Step 8: Commit**

```bash
git add src/ddd/finding_fixes.py src/ddd/gui/api.py tests/test_finding_fixes.py tests/test_gui_api.py
git commit -m "let a disagreement be settled from the finding that reports it"
```

### Task 4: What it looks like

**Files:**
- Modify: `gui/src/components/FindingPanelView.stories.tsx`
- Reference: `gui/screenshots/references/` (regenerate)

**Interfaces:**
- Consumes: nothing. The component already draws every fix a finding carries.
- Produces: two screenshot references.

- [ ] **Step 1: Read the stories file and the props it feeds**

Run: `sed -n '1,80p' gui/src/components/FindingPanelView.stories.tsx`

The component takes `fixes: FixReply | null`, `chosen: string | undefined`, `changesShown` and
`refusal`. A story sets those directly — there is no server in a story.

- [ ] **Step 2: Add a story for a mismatch offering two keys**

```tsx
export const AMismatchWithTwoFixes = () => (
  <FindingPanelView
    finding={{
      file: "/p/user_interface.ddd.json",
      check: "definition-mismatch",
      severity: "error",
      message:
        "'ValueE' is declared differently by component 'UserInterface' than by 'Controller' " +
        "(unit: 'kHz' != 'Hz')",
      pointer: "component.interface[0].definition",
      notes: [
        {
          message: "reference declaration",
          file: "/p/controller.ddd.json",
          pointer: "component.interface[4].definition",
        },
      ],
      route: { kind: "variable", name: "ValueE" },
    }}
    label="Open ValueE"
    href="#/variable/ValueE"
    reason=""
    onOpen={() => {}}
    fixes={{
      revision: 1,
      fixes: [
        { title: "Use the unit declared in controller", changes: [] },
        { title: "Use the datatype declared in controller", changes: [] },
      ],
    }}
    chosen={undefined}
    onChoose={() => {}}
    changesShown={false}
    onChangesShown={() => {}}
    onApply={() => {}}
    refusal={null}
    busy={false}
    onClose={() => {}}
  />
);
```

**Check every field against `gui/src/api/types.ts` before writing it.** `Finding`, `Note` and
`FixOffered` are generated from the Python contract, so a field this plan spelled wrongly is a
typecheck failure, not a runtime one. `changes: []` renders the buttons without a preview, which
is what this story is for; the story below shows one chosen.

- [ ] **Step 3: Add a story for a mismatch that offers nothing**

The same finding with `fixes={{ revision: 1, fixes: [] }}`, named `AMismatchWithNoFix`, so the
reference records what a reader sees when the variable has two producers or only its `kind`
disagrees: the message, the note, and the link — no buttons.

- [ ] **Step 4: Build and check the stories render**

Run: `cd gui && npm run lint && npm run typecheck && npm run build && npm run ladle:build`
Expected: clean.

- [ ] **Step 5: Regenerate the screenshots and look at them**

Run: `UPDATE=1 docker compose run --rm gui-screenshots`
Expected: **two new references, and none of the existing 93 changed.** Confirm with
`git status --porcelain gui/screenshots`: two additions, no modifications. A modification means a
story you did not mean to touch moved, and it is not this part's to move.

**Open both PNGs and look at them.** Three of part 10's defects were found this way and by
nothing else: a tick clipped to `320(`, a label sitting on its own marker, and then that same
label struck through by its own line. The DOM was correct every time.

- [ ] **Step 6: Commit**

```bash
git add gui/src/components/FindingPanelView.stories.tsx gui/screenshots/references
git commit -m "show what a finding that can be fixed looks like, and one that cannot"
```

### Task 5: The journey

**Files:**
- Modify: `gui/e2e/findings.spec.ts`, `gui/e2e/demo.ts`

**Interfaces:**
- Consumes: the whole feature, through the running application.
- Produces: journey count 75.

**The fixture.** `ValueE` is written by `Controller` and read by `UserInterface` and
`EventLogger`, `uint16` in `Hz` — the only demo variable with one producer and two consumers, so
it can show a fix reaching one file and a fix reaching two. `demo.ts` already exports
`CONTROLLER`, `SENSOR_HUB` and `USER_INTERFACE`, and already has `withUnitOf(bytes, variable,
unit)`, which replaces one variable's unit and nothing else.

- [ ] **Step 1: Export the logging component's path**

`gui/e2e/demo.ts`, beside the other three:

```ts
export const EVENT_LOGGER = join("subsystems", "logging", "event_logger.ddd.json");
```

Confirm the path against `examples/demo/` before writing it.

- [ ] **Step 2: Write the journey**

In `gui/e2e/findings.spec.ts`, following the shape of the journeys already there — they plant a
fault by rewriting a file in the copy, then open the page:

```ts
test("a disagreement is settled from the finding that reports it", async ({ page }, info) => {
  // `ValueE` is written by Controller and read by UserInterface and EventLogger, all three in
  // Hz. Changing one reader's unit is a definition-mismatch filed on that reader, with the
  // producer as its reference - which is the shape the fix follows.
  const project = await demo(info);
  await rewrite(project, USER_INTERFACE, (bytes) => withUnitOf(bytes, "ValueE", "kHz"));
  await open(page, project);
  await page.getByRole("link", { name: "Findings" }).click();
  await page.getByRole("button", { name: /definition-mismatch/ }).first().click();
  await page.getByRole("button", { name: "Use the unit declared in controller" }).click();
  await expect(page.getByRole("button", { name: "Apply to 1 file" })).toBeVisible();
  await page.getByRole("button", { name: "Apply to 1 file" }).click();
  await expect(page.getByText("definition-mismatch")).toHaveCount(0);
  expect(await read(project, USER_INTERFACE)).toContain('"unit": "Hz"');
});
```

`demo`, `rewrite`, `open` and `read` are this suite's own helpers under names it already uses —
**read `findings.spec.ts` and `fixtures.ts` and use the real ones.** The names above are
placeholders for whatever those files call them, and a journey written against invented helpers
will not compile.

**Never `page.waitForResponse`.** It broke part 6's CI.

- [ ] **Step 3: Add the two-file case to the same journey**

After the first apply, plant the same wrong unit in `EVENT_LOGGER` as well and assert the button
reads **`Apply to 2 files`** — one settlement reaching both readers. This is what proves the
count comes from the settlement rather than from the finding, which names one file.

- [ ] **Step 4: Build, then run the journeys**

Run: `cd gui && npm run build && PLAYWRIGHT_CHANNEL=chrome npm run e2e`
Expected: **75 passed.** The journeys drive the compiled pages, so the build is not optional.

Run it **three times**. Two flaky spots on the graph canvas are known and documented —
`skeleton.spec.ts:134`'s arrow count and the `waitForResponse` at line 220 — and a new journey
that is itself racy must not be mistaken for one of them.

- [ ] **Step 5: Commit**

```bash
git add gui/e2e/findings.spec.ts gui/e2e/demo.ts
git commit -m "prove a reader can settle a disagreement without leaving the findings"
```

### Task 6: What a user reads

**Files:**
- Modify: `CHANGELOG.md`, `docs/command_line_interface.rst`

**Interfaces:**
- Consumes: the finished behaviour.
- Produces: nothing code depends on.

- [ ] **Step 1: Find the anchors by content, not by line number**

The changelog's unreleased section, after the plots paragraph part 10 added. The command-line
page's `ddd gui` section, where findings are already described as leading somewhere. **Line
numbers in a plan go stale** — part 10's were wrong by nine lines before its branch began. Search
for the sentence, not the line.

- [ ] **Step 2: Write the changelog sentence**

Say what is true and check each clause against the code:

- a `definition-mismatch` finding now carries a button per key that disagrees;
- the button takes the producing component's value, because the component that writes a variable
  is the one that decides;
- it settles **every** declaration of the variable, not only the one the finding is filed on;
- nothing is offered where there is no single producer, where only `kind` disagrees, or where
  some declaration cannot take the value.

**Keep each sentence inside what the file's own longest already is.** Part 10 shipped two
sentences of 129 and 96 words into documents whose longest were 102 and 73, and both had to be
split at a semicolon they already carried. Count before you commit.

- [ ] **Step 3: Write the command-line page's paragraph**

The same facts in that page's voice, in the `ddd gui` section beside what it already says about
findings. Then **read it rendered**, not only in source.

- [ ] **Step 4: Build the docs**

Run: `docker compose run --rm -e JAVA_TOOL_OPTIONS=-Duser.home=/tmp docs`
Expected: `build succeeded`, no warnings. The `JAVA_TOOL_OPTIONS` is not optional — without it a
stray `docs/?/.java` directory appears in the tree.

- [ ] **Step 5: Commit**

```bash
git add CHANGELOG.md docs/command_line_interface.rst
git commit -m "say that a disagreement can now be settled where it is reported"
```

### Task 7: The milestone gate

**Files:** none. This task runs everything and fills in the progress log.

- [ ] **Step 1: The Python gate** — `python -m pytest && ruff check . && ruff format --check . && mypy`, 100 % line and branch.
- [ ] **Step 2: The editor's answers, proved unmoved** — `git diff --stat 63a493f..HEAD -- tests/test_lsp.py` prints nothing. This is the whole proof of Tasks 1 and 2; run it last as well as first.
- [ ] **Step 3: The page gate** — `cd gui && npm run lint && npm run typecheck && npm test && npm run build && npm run ladle:build`, Vitest at 100 % on all four metrics.
- [ ] **Step 4: The screenshots** — `docker compose run --rm gui-screenshots` in verify mode: **95**, the 93 of part 10 plus this part's two, and not one of the 93 changed.
- [ ] **Step 5: The journeys, three times** — 75 each time, with `PLAYWRIGHT_CHANNEL=chrome`.
- [ ] **Step 6: The documentation** — sphinx clean under `-W`, no stray `docs/?`.
- [ ] **Step 7: Drive it by hand, and look at it.** Start `ddd gui` over a **copy** of `examples/demo`. Break `ValueE`'s unit in `user_interface.ddd.json`, open Findings, and press the button. Check the file on disk afterwards and check undo puts it back. Then open `examples/inconsistent` and confirm its `SharedValue` mismatch offers **no** fix at all — two producers, which is the case the spec measured. **Take screenshots and look at them.**
- [ ] **Step 8: Fill in the progress log, then hand over** with `superpowers:finishing-a-development-branch`.

## Progress log

| Task | Commit | Notes |
| --- | --- | --- |
| 1 | | |
| 2 | | |
| 3 | | |
| 4 | | |
| 5 | | |
| 6 | | |
| 7 | | |

## Left open

Filled in as the plan runs: anything found and deliberately not fixed here, with what it costs.

## Rulings

Filled in as the plan runs: every decision taken against the plan's text, why, and what it costs
if wrong.
