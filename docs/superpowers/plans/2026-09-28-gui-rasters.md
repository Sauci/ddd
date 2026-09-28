# Rasters in the GUI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A project's measurement rasters are listed, opened, edited, renamed, declared and removed in the Shared files tab, and every finding about one leads to it.

**Architecture:** The tab's machinery is already generic over a per-vocabulary descriptor; part 14 proved it by adding sections without changing one generic function. This part adds the third descriptor and the one field it needs that the first two did not — a raster has two project-unique keys, its name and its `event`, so `name_judge` becomes a map from key to a project-aware judge.

**Tech Stack:** Python 3.14, pydantic v2, pytest at 100 % line and branch; React 19 + TypeScript, Vitest at 100 % over `src/api`, `src/lib`, `src/state`; Playwright journeys; Ladle stories with Docker screenshot references; Sphinx docs under `-W`.

**Spec:** `docs/superpowers/specs/2026-09-28-gui-rasters-design.md`, which inherits `docs/superpowers/specs/2026-09-27-gui-sections-design.md` by reference. **Read both.**

## Prerequisites

- Branch `feature/gui-rasters`, off master at `a6700d1`, spec committed as `82bda96`.
- **PR #70 (`fix/consolidation-before-rasters`) must land first.** Task 1's fifth invariant extends the fourth, which is in that PR. When it merges, `git merge master` into this branch before starting Task 1 — do not stack the branches, and do not re-implement the fourth invariant.

## Global Constraints

Every task's requirements implicitly include this section.

**Running things**

- There is no `python` on PATH. Always `.venv/bin/python`.
- **Never add `-q` to pytest.** `pyproject.toml:118` already sets it, and a second one raises quiet to level two and removes the `N passed` summary line entirely. `pytest-cov` prints `Required test coverage of 100% reached` whether or not tests failed, so that line is not evidence.
- **A pipeline reports its last command's exit status.** `pytest … | tail` exits with `tail`'s. Capture the tool's own status: `.venv/bin/python -m pytest > gate.txt 2>&1; echo "EXIT=$?"; tail -3 gate.txt`. The tell for a run that finished is a **summary line** — `N passed in …s`. A tail that ends in a stack trace or a bare `}` did not finish, whatever the exit code says.
- Node is not on PATH; it is at `~/.local/node-v24.21.0/bin`.
- Journeys: `cd gui && npm run build` first — they drive the **compiled** pages in `src/ddd/gui/static`, not Vite — then `PLAYWRIGHT_CHANNEL=chrome DDD_PYTHON="$PWD/../.venv/bin/python" npx playwright test --output=<a path outside the repository>`. The channel is required; there are no downloaded browsers. Writing `--output` inside `gui/` fails with `EACCES`.
- Screenshots: `UPDATE=1 docker compose run --rm gui-screenshots` from the repository root. Docs: `docker compose run --rm -e JAVA_TOOL_OPTIONS=-Duser.home=/tmp docs`.

**Gates**

- Python: `.venv/bin/python -m pytest` at **100 % line and branch**, `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, and `.venv/bin/mypy` run **bare** — it takes its targets from `pyproject.toml`, and passing paths gives a different and wrong answer.
- Page: `npm run lint && npm run typecheck && npm test && npm run build && npm run ladle:build`. Vitest at 100 % on statements, branches, functions **and** lines over `src/api`, `src/lib`, `src/state`.
- No `pragma: no cover`, no skips, no xfails.

**What the gates cannot see**

- **A conditional expression registers zero branches with coverage.py, and so does a comprehension filter.** An unexercised arm of either passes a 100 % branch gate silently. Write statements or early returns where a branch matters.
- **A coverage gate cannot see data.** Part 14 shipped four `SECTIONS` field values pinned by no test, because every line reading them is covered through `CONSTANTS`. **Ablate every new descriptor value and confirm a named test dies.** If none does, write the one that does.
- **A survival under ablation can be luck.** Python randomises string hashing per process, so a `frozenset` of strings iterates differently run to run — one part 14 reviewer's "the sort is unpinned" was a coin toss. Re-run a survival under `PYTHONHASHSEED=0`, `1`, `4` and `7` before believing it. A death proves the point; a survival does not.
- **Ablate only in a `git worktree add` scratch checkout, and run pytest with that worktree as the working directory.** `pyproject.toml:122` sets `pythonpath = ["src", "tools", "docker"]`, which pytest resolves against **rootdir** and puts ahead of any `PYTHONPATH` you export — so a run started from the main repository measures the main repository however `PYTHONPATH` is set, every rot "survives", and the conclusion is that nothing pins anything. Measured on this branch, twice, by the controller. The tell is pytest's own `rootdir:` line, and the guard is to **confirm the ablation kills something before trusting that it kills nothing**. Set `PYTHONHASHSEED` too. Remove the worktree afterwards and confirm a clean tree.
- **No decision may live in a `.tsx` file.** Almost nothing in this repository executes one under any gate; lint, typecheck, build and the screenshot diff are all the scrutiny most of them get. The exception, which the final review measured rather than assumed: `gui/e2e/rasters.spec.ts` drives the *compiled* panel and asserts the Used by row reads "everything it produces", so `rasterUseWhat` is exercised through `RasterPanelView` — one narrow happy path, but not nothing. It presses nothing, so no refusal, no Save and no Remove is reached that way. Part 14 shipped four defects in `.tsx` that every gate passed. Judgements live in `gui/src/lib` behind the Vitest gate.
- **Write the prose as carefully as the code.** Five stale or false cross-references in part 14 all arrived the same way: text copied from the constants version without re-reading it against what is now true. Cite a mechanism in the code rather than a section number, and grep a quoted phrase rather than trusting it.

**Conventions**

- Commits: lowercase imperative subject, no `feat:`-style prefix. Trailer `Co-Authored-By: <your model> <noreply@anthropic.com>`. Never `--amend`, never rebase.
- `gui/src/generated/` is gitignored (`.gitignore:22`): there is no diff to read there. Grep the generated file and let `npm run typecheck` prove the page agrees.
- If a brief or this plan is wrong, **say so in your report rather than working around it silently.** Every task of part 14 surfaced at least one real defect that way, and seven of them corrected an instruction that was wrong.

## Review Focus

Five things the spec implies that no task's own tests would otherwise exercise. Each has its test added to the task that owns the code.

1. **A raster keeping its own event.** A panel asks for a plan on every keystroke, so re-typing the `1` a raster already claims must not be refused as taken. Task 4.
2. **A raster with no cycle.** `cycle` is `str | None`, so the row's cell must read `event 3` rather than `event 3, None` or a `KeyError`. Task 4.
3. **A component's own raster in the uses list.** `component.raster` is a use inside no definition; a panel listing only definitions would silently omit the component that names it as a default. Task 3.
4. **An event outside the model's range.** `event` is `ge=0, le=EVENT_MAX`; `-1` and `EVENT_MAX + 1` must be refused with the model's own words, not written. Task 4.
5. **A descriptor whose `taken` names a key it does not have.** The fifth invariant exists for a third descriptor written by hand; nothing else would catch `taken={"evnt": …}`. Task 1.

## File structure

| File | Responsibility | Tasks |
| --- | --- | --- |
| `src/ddd/project_shared.py` | `Vocabulary`, its invariants, the generic readers, `CONSTANTS`/`SECTIONS`/`RASTERS` | 1, 3, 4 |
| `src/ddd/shared_plans.py` | the four verbs, which consult `taken` | 1, 4 |
| `src/ddd/lsp/navigation.py` | `rename_problem`'s per-kind arms | 2 |
| `src/ddd/finding_routes.py` | where a raster's findings lead | 5 |
| `src/ddd/gui/contract.py`, `api.py` | `RasterReply`, `/api/raster`, `/api/raster-plan` | 5 |
| `gui/src/lib/shared.ts`, `findings.ts`, `route.ts`, `undo.ts`, `api/client.ts` | every page decision, under the Vitest gate | 6 |
| `gui/src/components/SharedTableView.tsx` | raster rows | 7 |
| `gui/src/components/RasterPanelView.tsx`, `SharedAddView.tsx`, `screens/RasterPanel.tsx`, `SharedPage.tsx` | the panel and the chooser's third entry | 8 |
| `gui/e2e/rasters.spec.ts`, `docs/command_line_interface.rst`, `docs/editor_integration.rst` | the journey and the manual | 9 |

## The fixture

`examples/vocabulary` needs nothing added and supports every story:

- `rasters.ddd.json` declares `1ms` (event 0), `10ms` (event 1), `100ms` (event 2), each with a cycle and a description.
- `pump.ddd.json` has `"raster": "10ms"` on the **component** — the use inside no definition — and a definition naming `"1ms"`.
- **`100ms` is named by nobody**, so it is the one a removal is offered for.
- The three events are distinct, so a `duplicate-event` refusal is driven by setting one raster's event to another's.

Every count in this plan was measured on the checkout. If one disagrees with what you find, report it: two briefs in part 14 miscounted this same fixture.

---

## Task 1: one map where there was one judge

**Files:**
- Modify: `src/ddd/project_shared.py` (the field, the fifth invariant, both descriptors)
- Modify: `src/ddd/shared_plans.py:218`, `:259` (the two call sites)
- Modify: `tests/test_project_shared.py` (added to, never edited)

**Interfaces:**
- Consumes: `Vocabulary` as it stands, with `name_judge: Callable[[Index, str], str | None]`.
- Produces: `taken: Mapping[str, Callable[[Index, str | None, str, dict[Path, Document]], str | None]]`, replacing `name_judge`; the fifth `__post_init__` invariant.

**The proof this task turns on:** `tests/test_shared_plans.py` passes **untouched**, and `tests/test_project_shared.py` gains tests and loses none. That is the evidence the signature change moved no behaviour, and it is the evidence part 14's first two tasks took. If you find yourself needing to edit an existing line in either, stop and report it.

**Why the judges may ignore their new argument.** The entry argument exists for `event`, which Task 4 adds. A name judge keeps ignoring it: part 14 settled that renaming `.calib` to `.calib` is refused as already declared — "it would reach the same guard and say nothing about a reader's real mistake" — so preserving that is preserving a decision, not an oversight.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_project_shared.py`, without touching a line of what is there:

```python
class TestTakenReplacesTheNameJudge:
    def test_a_name_is_judged_through_the_map_it_now_lives_in(self, tmp_path: Path) -> None:
        built, _ = built_of(tmp_path, **TWO_HOMES)
        cache: dict[Path, Document] = {}
        judge = CONSTANTS.taken[CONSTANTS.name_key]
        assert judge(built, None, "TREND_SAMPLES", cache) is not None
        assert judge(built, None, "FRESH", cache) is None

    def test_a_taken_key_that_is_neither_the_name_nor_settable_is_refused(self) -> None:
        """The fifth invariant. A third descriptor is written by hand, and a `taken` naming a key
        the vocabulary does not have would judge nothing while reading as though it did."""
        with pytest.raises(ValueError, match="taken"):
            dataclasses.replace(SECTIONS, taken={"nowhere": _section_name_judge})
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_project_shared.py --no-cov -k TakenReplaces`
Expected: FAIL at collection — `AttributeError: 'Vocabulary' object has no attribute 'taken'`.

- [ ] **Step 3: Replace the field**

In `src/ddd/project_shared.py`, `name_judge` becomes:

```python
    taken: Mapping[str, Callable[[Index, str | None, str, dict[Path, Document]], str | None]]
    """Per key whose value is the project's alone, what refuses a value another entry claims.

    The index, the entry whose key is being set — ``None`` where there is no entry yet, as an
    ``add`` has none — the wanted value, and the document cache; the sentence refusing it, or
    ``None``.

    A map rather than the single ``name_judge`` it replaces, because a raster has **two** such
    keys: its name and its ``event``. :func:`~ddd.shared_plans._judged` takes no :class:`Index`,
    so a key's own judge can ask whether a value is legal and never whether it is taken.

    The entry is given because an event needs it: a panel asks for a plan on every keystroke, so a
    reader re-typing the event their raster already claims must not be told it is taken by
    themselves. A name judge ignores it, which preserves what part 14 settled — a rename of a name
    to itself is refused, and says nothing about a reader's real mistake either way.

    The cache is given because :attr:`Index.rasters` maps a name to a :class:`Site` and **not** to
    its event: asking which raster claims one means reading each entry's own text, as
    :func:`text_of` does and takes a cache for. A name judge ignores this too — a name is in the
    index — so both name judges carry two arguments they do not read. That is the price of one map
    over two fields, and it is paid once.
    """
```

- [ ] **Step 4: Add the fifth invariant**

In `__post_init__`, beside the four that are there:

```python
        stray = sorted(key for key in self.taken if key != self.name_key and key not in self.keys)
        if stray:
            msg = f"{self.kind}: {stray} in taken but neither the name key nor settable"
            raise ValueError(msg)
```

Correct the method's docstring count — it says "Four checks" today.

- [ ] **Step 5: Give both descriptors their map**

`CONSTANTS`: `taken={"name": _constant_name_judge}`. `SECTIONS`: `taken={"section": _section_name_judge}`. Both judges gain the ignored middle parameter, named `_entry` so its being unused reads as deliberate:

```python
def _constant_name_judge(
    built: Index, _entry: str | None, to: str, _cache: dict[Path, Document]
) -> str | None:
```

- [ ] **Step 6: Move the two call sites**

`shared_plans.py:218`, in `rename_entry` — the entry being renamed is `name`:

```python
    problem = vocabulary.taken[vocabulary.name_key](built, name, to, cache)
```

`shared_plans.py:259`, in `add_entry` — there is no entry yet:

```python
    problem = vocabulary.taken[vocabulary.name_key](built, None, name, cache)
```

- [ ] **Step 7: Run the suite, and read what it proves**

Run: `.venv/bin/python -m pytest > gate.txt 2>&1; echo "EXIT=$?"; tail -3 gate.txt`
Expected: PASS at 100 %. Then `git diff --stat <base> -- tests/test_shared_plans.py` — **no output at all**, and `tests/test_project_shared.py` showing insertions and zero deletions.

Then the whole Python gate, each command with its own exit status.

- [ ] **Step 8: Ablate, and confirm what dies**

In a scratch worktree, drop the fifth invariant and confirm `test_a_taken_key_that_is_neither_the_name_nor_settable_is_refused` dies. Then rot `CONSTANTS.taken`'s key from `"name"` to `"nayme"` and confirm something dies — if nothing does, the map's key is unpinned and needs the test that pins it.

- [ ] **Step 9: Commit**

```bash
git add src/ddd/project_shared.py src/ddd/shared_plans.py tests/test_project_shared.py
git commit -m "$(printf "judge every key the project speaks for, not only the name\n\nA raster has two keys the project owns, its name and its event, and a judge\nthat cannot see the index can only ask whether a value is legal. name_judge\nbecomes a map from key to such a judge, and a judge takes the entry as well as\nthe value so an event is not refused against itself.\n\ntests/test_shared_plans.py is untouched.\n\nCo-Authored-By: <your model> <noreply@anthropic.com>")"
```

---

## Task 2: rename_problem learns a third kind

**Files:**
- Modify: `src/ddd/lsp/navigation.py` (`rename_problem`'s dispatch, a `_raster_problem` beside `_section_problem`)
- Modify: `tests/test_lsp.py`

**Interfaces:**
- Consumes: `_section_problem`'s shape; `RasterName` from `ddd.models.rasters`; `Index.rasters`.
- Produces: `rename_problem(built, name, "raster")` answering a raster's own rules.

Measured today: `rename_problem(Index(), "10ms", "raster")` answers **`"'10ms' is not a usable c identifier"`**, which is false about an a2l short name. `rename_problem`'s own docstring discloses this and says the rasters part adds the arm beside the section's.

- [ ] **Step 1: Write the failing tests**

```python
    def test_a_raster_is_judged_as_the_a2l_short_name_it_is(self, tmp_path: Path) -> None:
        """`10ms` starts with a digit, which no c identifier may. The rule that refuses it is a
        constant's, and a raster does not share that namespace."""
        from ddd.lsp.navigation import rename_problem

        built, _ = built_of(tmp_path, **TIMED)
        assert rename_problem(built, "10ms", "raster") is None

    def test_a_raster_may_not_take_a_name_the_project_declares(self, tmp_path: Path) -> None:
        from ddd.lsp.navigation import rename_problem

        built, _ = built_of(tmp_path, **TWO_RASTERS)
        problem = rename_problem(built, "20ms", "raster")
        assert problem is not None
        assert "20ms" in problem
```

`TWO_RASTERS` is a new tree in that file: a rasters file declaring `10ms` on event 1 and `20ms` on event 2, and a component naming `10ms`. `TIMED` is already there.

- [ ] **Step 2: Run them to verify they fail**

Expected: the first FAILs with `'10ms' is not a usable c identifier`; the second passes for the wrong reason — the c identifier rule refuses `20ms` too. **Both must be run**, and the second's reason checked, or it will keep passing after a wrong fix.

- [ ] **Step 3: Give rename_problem a raster arm**

Beside the section's early return:

```python
    if kind == "raster":
        return _raster_problem(built, name)
```

And, beside `_section_problem`:

```python
def _raster_problem(built: Index, name: str) -> str | None:
    """Why the project may not have a raster called ``name``, or nothing if it may.

    Judged by :data:`~ddd.models.rasters.RASTER_NAME_PATTERN` rather than by the c identifier rule
    the other kinds answer to: a raster's name is the short name of its XCP event, which `10ms`
    spells and no c identifier may. It joins no namespace ``occupied`` guards, for the reason
    `_section_problem` gives about a section's.

    A name the vocabulary already declares is refused although the file would still load, exactly
    as a section's is: ``duplicate-raster`` is a check, not a schema error, so two rasters may share
    a name — and each carries its own event and cycle, so merging two would silently sample one
    signal on another's channel.
    """
```

```python
    if not re.fullmatch(RASTER_NAME_PATTERN, name) or len(name) > RASTER_NAME_LENGTH:
        return f"'{name}' is not a usable raster name"
    if name in built.rasters:
        return f"'{name}' is already a raster this project declares"
    return None
```

Statements, not a conditional expression. **The model is the authority on the length, and unlike a
section's a raster's name has one**: `RasterName` is `StringConstraints(min_length=1,
max_length=RASTER_NAME_LENGTH, pattern=RASTER_NAME_PATTERN)` in `ddd.models.common`. Do not reach for
`IDENTIFIER_MAX_LENGTH`, which bounds a c identifier and is a different number for a different reason.

- [ ] **Step 4: Run the tests, then the whole gate**

Expected: PASS, 100 %, all clean. **The four pre-existing kinds must answer identically.** Prove it rather than assert it: a harness over several names × every kind, run against this tree and against a `git worktree` of the base commit, with the answers diffed. Part 14's Task 4 did exactly this over 22 names × 8 kinds × 2 projects and found 308 identical pairs.

- [ ] **Step 5: Commit**

```bash
git add src/ddd/lsp/navigation.py tests/test_lsp.py
git commit -m "$(printf "judge a raster's name by the rule its model states\n\nrename_problem answered \"'10ms' is not a usable c identifier\" for a name that\nis an a2l short name and never reaches c. Its own docstring said this part\nwould add the arm; here it is, beside the section's and for the same reason.\n\nCo-Authored-By: <your model> <noreply@anthropic.com>")"
```

---

## Task 3: the use shape no definition holds

**Files:**
- Modify: `src/ddd/project_shared.py` (`Use.kind`, a `_raster_uses` reader)
- Modify: `tests/test_project_shared.py`

**Interfaces:**
- Consumes: `Index.raster_uses`, populated by part 14; `_RASTER_KEY` in `navigation.py`, which matches `component.raster` **and** a definition's own.
- Produces: `Use.kind` widened; `_raster_uses`, to be bound as `RASTERS.uses` in Task 4.

`Use.kind` is `Literal["variable", "member"]` — a constant is named by a declaration's dimension or a structure member's. A section needed no change, because a section is named by a definition and so its use is that variable's. **A component naming a raster is neither.**

- [ ] **Step 1: Write the failing tests**

```python
    def test_a_component_naming_a_raster_is_a_use_of_its_own_kind(self, tmp_path: Path) -> None:
        """`Component.raster` is the default for everything the component produces - a use inside
        no definition at all, which neither of the other two vocabularies has."""
        built, root = built_of(tmp_path, **TIMED)
        cache: dict[Path, Document] = {}
        used = _raster_uses(built, "10ms", cache)
        assert [(use.kind, use.name, use.component) for use in used] == [
            ("component", "A", "A"),
            ("variable", "X", "A"),
        ]
```

Read `_section_uses` first and follow its shape; the order is the order the index recorded, which part 14 pinned as the component's own first.

- [ ] **Step 2: Run it to verify it fails**

Expected: FAIL — `_raster_uses` is not defined.

- [ ] **Step 3: Widen the literal and write the reader**

```python
    kind: Literal["variable", "member", "component"]
    """Whose use this is: a variable's declaration, a structure member's, or a **component's own**
    - the last being a raster named at `component.raster` as the default for everything that
    component produces, which sits inside no definition. A constant is never named that way and a
    section is named only by a definition, so this third word arrives with rasters."""
```

- [ ] **Step 4: Run the tests, then the whole gate**

Expected: PASS, 100 %. `Use.kind` is read by `contract.py`'s wire model too — if `mypy` or a test objects, that is Task 5's `RasterUse`, and the objection belongs in your report rather than in a widening of the contract here.

- [ ] **Step 5: Commit**

```bash
git add src/ddd/project_shared.py tests/test_project_shared.py
git commit -m "$(printf "read a use that sits inside no definition\n\nA component names a raster as its default for everything it produces. That is\nneither a variable's use nor a structure member's, so Use.kind gains its third\nword - the first time the type has had to move since part 13 wrote it.\n\nCo-Authored-By: <your model> <noreply@anthropic.com>")"
```

---

## Task 4: the rasters descriptor, and the judge that reads the project

**Files:**
- Modify: `src/ddd/project_shared.py` (`RASTERS`, `HELD`, the event judge)
- Modify: `tests/test_project_shared.py`, `tests/test_shared_plans.py`

**Interfaces:**
- Consumes: Tasks 1–3's `taken`, `Use.kind`, `_raster_uses`; `Index.rasters`/`raster_uses`.
- Produces: `RASTERS: Final = Vocabulary(...)`; `HELD = (CONSTANTS, SECTIONS, RASTERS)`.

**This is the task the descriptor was built for.** A third vocabulary should be a record and its judges. **If a generic function has to learn that rasters exist, say so in your report rather than adding a branch for it** — that is the signal the shape is wrong, and part 14's Task 1 surfaced exactly such a thing by refusing to bend one.

- [ ] **Step 1: Write the failing tests**

In `tests/test_project_shared.py`:

```python
class TestRasters:
    def test_a_raster_states_its_event_and_its_cycle(self, tmp_path: Path) -> None:
        built, _ = built_of(tmp_path, **TIMED)
        cache: dict[Path, Document] = {}
        row = row_of(RASTERS, built, "10ms", (), cache)
        assert (row.kind, row.name, row.states) == ("raster", "10ms", "event 1, 10ms")

    def test_a_raster_with_no_cycle_states_its_event_alone(self, tmp_path: Path) -> None:
        """`cycle` is `str | None`, where a section's two keys are both required. This is the
        first row cell composed from a key that may not be there."""
        built, _ = built_of(tmp_path, **UNTIMED)
        cache: dict[Path, Document] = {}
        assert row_of(RASTERS, built, "20ms", (), cache).states == "event 2"

    def test_all_three_vocabularies_share_the_table(self, tmp_path: Path) -> None:
        built, _ = built_of(tmp_path, **ONE_OF_EACH)
        cache: dict[Path, Document] = {}
        assert [(row.kind, row.name) for row in shared_rows(built, (), cache)] == [
            ("constant", "TREND_SAMPLES"),
            ("raster", "10ms"),
            ("section", ".calib"),
        ]
```

`UNTIMED` declares `20ms` on event 2 with no `cycle` key at all. `ONE_OF_EACH` declares one of each vocabulary; the order above is `sorted(key=(kind, name))`, which is what `shared_rows` does — check it rather than assuming the alphabet.

In `tests/test_shared_plans.py`:

```python
class TestRasterRefusals:
    @pytest.mark.parametrize(("key", "raw"), [("event", "-1"), ("event", "1e3"), ("cycle", "4")])
    def test_a_value_the_model_would_refuse_is_refused_here(
        self, tmp_path: Path, key: str, raw: str
    ) -> None:
        built, _ = built_of(tmp_path, **TIMED)
        cache: dict[Path, Document] = {}
        with pytest.raises(SharedRefusalError) as raised:
            set_entry(RASTERS, built, "10ms", key, raw, cache)
        assert raised.value.code == "invalid"
        assert "r.ddd.json" in raised.value.message

    def test_an_event_another_raster_claims_is_refused(self, tmp_path: Path) -> None:
        """Spec §4: `duplicate-event` is a check, not a schema error, so the file would load and
        the project would be wrong in a way only the analysis names. The reader can pick another
        channel, so the interface refuses."""
        built, _ = built_of(tmp_path, **TWO_RASTERS)
        cache: dict[Path, Document] = {}
        with pytest.raises(SharedRefusalError) as raised:
            set_entry(RASTERS, built, "10ms", "event", "2", cache)
        assert "20ms" in raised.value.message

    def test_a_raster_keeping_the_event_it_already_claims_is_not_refused(
        self, tmp_path: Path
    ) -> None:
        """A panel asks for a plan on every keystroke. Without the entry, a reader re-typing the
        `1` their own raster claims would be told it is taken - by themselves."""
        built, _ = built_of(tmp_path, **TWO_RASTERS)
        cache: dict[Path, Document] = {}
        assert set_entry(RASTERS, built, "10ms", "event", "1", cache).edits
```

- [ ] **Step 2: Run them to verify they fail**

Expected: `ImportError: cannot import name 'RASTERS'`.

- [ ] **Step 3: Write the event judge**

```python
def _event_taken(built: Index, entry: str | None, wanted: str) -> str | None:
    """Why this event may not be claimed, or nothing if it may.

    ``entry`` is the raster whose event is being set, and is exempt from itself: the panel asks for
    a plan on every keystroke, so a reader who has typed nothing new must not be refused.

    Read from the index rather than from a file's text, for the reason
    :func:`ddd.shared_plans.remove_entry` gives about what is in use: reading text to answer a
    question about meaning is the mistake part 11 filed against ``variable_keys._storage_of``.
    """
```

```python
def _event_taken(
    built: Index, entry: str | None, wanted: str, cache: dict[Path, Document]
) -> str | None:
    try:
        event = json.loads(wanted)
    except ValueError:
        return None
    for other in built.rasters:
        if other == entry:
            continue
        claimed = text_of(RASTERS, built, other, "event", cache)
        if claimed and json.loads(claimed) == event:
            return f"event {event} is already claimed by raster '{other}'"
    return None
```

Three things about that body:

- **The wanted value arrives as json text**, not an `int`: `set_entry` judges `raw`. Text the model
  would refuse leaves through the `except` as *not taken*, so `judge["event"]` produces the refusal
  instead. Two refusals for one keystroke is one too many, and the model's is the one that says what
  a legal event looks like. That is ruling 6.
- **`entry` is skipped**, which is the whole reason a judge takes it.
- **It names `RASTERS` before `RASTERS` exists.** Module globals resolve at call time, so this is
  fine — but `taken={"event": _event_taken}` resolves the *function* at construction time, so
  `_event_taken` must be defined above the descriptor. Part 14 hit exactly this with `_constant_uses`
  and moved `CONSTANTS` down; follow that arrangement rather than rediscovering it.

- [ ] **Step 4: Write the descriptor**

```python
RASTER: Final = "raster"

RASTERS: Final = Vocabulary(
    kind=RASTER,
    containers=("rasters",),
    name_key="raster",
    keys=("event", "cycle", "description"),
    strings=frozenset({"cycle", "description"}),
    entries=lambda built: built.rasters,
    used=lambda built: built.raster_uses,
    states=_raster_states,
    uses=_raster_uses,
    required=frozenset({"event"}),
    filename="rasters.ddd.json",
    judge={
        "event": Judgement(_EVENT, "a whole number the target offers as a channel"),
        "cycle": Judgement(_CYCLE, "a json string, or nothing"),
        "description": Judgement(_DESCRIPTION, "a json string"),
    },
    taken={"raster": _raster_name_judge, "event": _event_taken},
)

HELD: Final = (CONSTANTS, SECTIONS, RASTERS)
```

`_raster_states` is a named function, not a lambda, because it has a branch:

```python
def _raster_states(texts: Mapping[str, str]) -> str:
    """``event 3, 10ms``, or ``event 3`` where the raster states no cycle.

    The first row cell composed from an optional key. Written as statements: a conditional
    expression registers no branch with coverage.py, and the arm for a raster with no cycle would
    then be one no gate could tell had run.
    """
    cycle = texts.get("cycle", "")
    if not cycle:
        return f"event {texts['event']}"
    return f"event {texts['event']}, {cycle}"
```

`_raster_name_judge` is the third of its family, beside `_constant_name_judge` and
`_section_name_judge`, and asks the arm Task 2 added:

```python
def _raster_name_judge(
    built: Index, _entry: str | None, to: str, _cache: dict[Path, Document]
) -> str | None:
    """:data:`RASTERS`'s name judge: ``rename_problem``'s own raster arm, asked exactly as the
    other two ask for theirs, so that the tab and the editor's F2 refuse a name in the same words."""
    return rename_problem(built, to, RASTER)
```

`_EVENT` and `_CYCLE` are `TypeAdapter`s over the model's **own** annotated types, pulled from `ddd.models.rasters` rather than rewritten. If a rule lives in a validator rather than an annotation — as a section's power-of-two rule did — adapt `RasterDeclaration` itself for that key, the way `_ALIGNMENT` does, and say so in your report.

- [ ] **Step 5: Run the tests, then the whole gate**

Expected: PASS, 100 %, all clean. **Report whether any generic function needed a change**, and name it if so.

- [ ] **Step 6: Ablate every value of the descriptor**

In a scratch worktree, rot each of `containers`, `name_key`, `keys`, `strings`, `required`, `filename`, and each key of `judge` and `taken`, and confirm a **named** test dies for each. Part 14 shipped four such values pinned by nothing, because every line reading them is covered through another vocabulary. Re-run any survival under `PYTHONHASHSEED=0`, `1`, `4`, `7` before believing it.

- [ ] **Step 7: Commit**

```bash
git add src/ddd/project_shared.py tests/
git commit -m "$(printf "rasters are a record, two judges and one branch\n\nThe third vocabulary in the tab. Its event is judged twice - once by the model\nfor what a channel may be, once by the project for whether another raster has\nit - and its row cell is the first composed from a key that may not be there.\n\nCo-Authored-By: <your model> <noreply@anthropic.com>")"
```

---

## Task 5: the routes, the contract, and where a raster's findings lead

**Files:**
- Modify: `src/ddd/finding_routes.py`, `src/ddd/gui/contract.py`, `src/ddd/gui/api.py`
- Modify: `tests/test_finding_routes.py`, `tests/test_gui_api.py`
- Modify: `gui/src/api/types.ts` (the re-export)

**Interfaces:**
- Consumes: Task 4's `RASTERS`.
- Produces: `RASTER_PLANS`, `GET /api/raster`, `GET /api/raster-plan`, `contract.RasterReply`, `contract.RasterUse`, `Route("raster", name)`.

- [ ] **Step 1: Write the failing route tests**

```python
class TestARaster:
    def test_unknown_raster_leads_to_the_name_the_definition_asks_for(
        self, tmp_path: Path
    ) -> None:
        root = built(tmp_path, **TIMED_NOWHERE)
        assert route_of(
            "unknown-raster",
            root / "a.ddd.json",
            "component.interface[0].definition.raster",
            "component",
            True,
            {},
        ) == Route("raster", "50ms")

    def test_a_component_s_own_raster_leads_there_too(self, tmp_path: Path) -> None:
        """The use inside no definition still names a raster, and a finding filed at it must reach
        the raster rather than falling through to the component's page."""
        root = built(tmp_path, **TIMED_NOWHERE)
        assert route_of(
            "unknown-raster", root / "a.ddd.json", "component.raster", "component", True, {}
        ) == Route("raster", "10ms")
```

`TIMED_NOWHERE` is `TIMED` with the definition's `raster` changed to a name no file declares — `50ms` — which is the state `unknown-raster` reports.

- [ ] **Step 2: Run them to verify they fail**

Expected: both answer `None`.

- [ ] **Step 3: Add the route**

`RASTER_CHECKS` and a `WITHIN_RASTER` for a pointer inside a `rasters[i]` entry, read like their section equivalents, **before** the `kind != COMPONENT_KIND` gate since a rasters file's kind is `rasters`.

**A raster's pointer shapes are two, not one**: `component.interface[i].definition.raster` and `component.raster`. `navigation._RASTER_KEY` already spells both — read it rather than writing a third copy of the pattern.

`Route.kind`'s docstring gains `raster`, **and so does `contract.FindingRoute.kind`'s `Literal`** — a kind missing from it makes `_finding` raise a pydantic `ValidationError` for every finding carrying it, which is how part 13 nearly shipped a crash.

**Stop at the `Literal`.** The page's `routeOf` needs its arm too, and that is Task 6's, which owns that file and runs under the Vitest gate.

- [ ] **Step 4: The contract and the two routes**

`contract.RasterReply` beside `SectionReply`, carrying `revision`, `name`, `file`, `pointer`, the display texts of its keys, `uses` and `findings`; `contract.RasterUse` whose `kind` is `Literal["variable", "component"]` — a raster is never named by a structure member. Added to `_ENDPOINTS` and to `gui/src/api/types.ts`'s re-export list. `RASTER_PLANS` beside `SECTION_PLANS`, with `add` taking one query parameter per required key — which for a raster is **`event` alone**.

Regenerate the page's types: `cd gui && npm run schemas`. That directory is gitignored, so grep the generated file for `RasterReply` and let `npm run typecheck` prove the page agrees.

- [ ] **Step 5: Write the api tests**

A `TestRaster` class over `opened_example(tmp_path, "vocabulary", "project.ddd.json")`: the panel names `10ms`'s file and pointer, its event and cycle, **its two uses — the component's own and the definition's** — and its findings; `?name=` missing is 400; a name no file declares is 404; each of the four actions previews; and every refusal with its status — `not-found` as 404, `unreadable` and `invalid` as 409, a malformed `raw` as 400.

**Assert enough of each refusal's sentence that a rewording fails it.** Measured in part 14: every refusal test in `tests/test_shared_plans.py` asserts only a substring, so a silently reworded refusal breaks nothing.

- [ ] **Step 6: Both gates, then commit**

```bash
git add src/ddd gui/src/api/types.ts tests/
git commit -m "$(printf "serve the project's rasters, and lead a finding to one\n\nTwo routes shaped like the sections pair, and a raster route tried before the\nkind gate since a rasters file is not a component. A raster is named at two\npointer shapes, one of them outside any definition.\n\nCo-Authored-By: <your model> <noreply@anthropic.com>")"
```

---

## Task 6: the page's own decisions, under the coverage gate

**Files:**
- Modify: `gui/src/lib/shared.ts` and `shared.test.ts`, `route.ts` and `route.test.ts`, `findings.ts` and `findings.test.ts`, `undo.ts` and `undo.test.ts`, `api/client.ts` and `client.test.ts`

**Interfaces:**
- Consumes: Task 5's `RasterReply`, `RasterUse`, the two endpoints.
- Produces: `getRaster`, `getRasterPlan`, `RasterPlanRequest`, `rasterLabel`, `rasterSet`; `SHARED_KINDS` and `SHARED_VOCABULARIES` gaining a third word; `route.ts`'s widened `kind`.

**Everything the page decides lives here.** `gui/src/lib` runs under a 100 % Vitest gate on statements, branches, functions and lines; the `.tsx` of Tasks 7 and 8 runs under nothing but lint, typecheck, build and the screenshot diff — bar the one happy path `gui/e2e/rasters.spec.ts` drives through the compiled panel, which presses no control.

- [ ] **Step 1: Widen what the tab holds**

`SHARED_KINDS` gains `"rasters"` and `SHARED_VOCABULARIES` gains `"raster"`. **Pin them by a relation, not a restatement** — a test asserting the literal repeats the source. `findings.test.ts` already builds a state with a failed file per kind and asserts `unreadable(state, SHARED_KINDS)` names each; add the raster case there, so dropping a kind fails a behavioural test. Confirm by mutation.

`findings.ts`'s `SHOWN` gains `"rasters"`, and **`routeOf` gains `raster` in the arm it already shares**:

```ts
  if (
    (route.kind === "constant" || route.kind === "section" || route.kind === "raster") &&
    route.name !== null
  ) {
```

The coverage provider is v8 and counts each side of a `||`, so all three need their own test.

- [ ] **Step 2: `tabTitle` needs nothing**

Measured in part 14: it counts through a `Map` with no hardcoded vocabulary list, and its test already asserts `["constant","raster","raster","section"]` → `"1 constant · 2 rasters · 1 section"`. **Check that this still holds and say so** rather than changing it — if it needs a change, the genericity it was given has been lost and that is worth reporting.

- [ ] **Step 3: The client and the labels**

`getRaster`, `getRasterPlan` and `RasterPlanRequest` beside the section trio; `rasterSet(name, key, text)` generic in the key **exactly as `sectionSet` is**, so the literal survives into the return type and a wrong key is a compile error rather than a test failure. `undo.ts` gains `rasterLabel`.

- [ ] **Step 4: Run the page gate**

Run: `cd gui && npm run lint && npm run typecheck && npm test`
Expected: Vitest at 100 % on all four metrics.

- [ ] **Step 5: Ablate**

Rot each new value in a scratch worktree and confirm a named test dies: `SHARED_KINDS`' third word, `SHARED_VOCABULARIES`', `routeOf`'s new arm, each of `rasterSet`'s keys, and the query parameter names in `RASTER_PLANS`' client.

- [ ] **Step 6: Commit**

```bash
git add gui/src/lib gui/src/api
git commit -m "$(printf "the tab's decisions with a third vocabulary in it\n\nEvery judgement the page makes about a raster, in the files a gate executes.\nrouteOf gains a word rather than an arm, which is what one tab for three\nvocabularies was for.\n\nCo-Authored-By: <your model> <noreply@anthropic.com>")"
```

---

## Task 7: raster rows in the table

**Files:**
- Modify: `gui/src/components/SharedTableView.tsx` and its stories, `gui/src/stories/fixtures.ts`

**Interfaces:**
- Consumes: Task 6's `tabTitle`, `rowKey`, `selectionAt`, `vocabularyOf`.
- Produces: no module another task imports.

**No decision may live in this diff.** The server composes each cell per kind through the descriptor's own `states`, and the row's vocabulary word comes from `vocabularyOf` in `lib`. If you find yourself writing a condition about rasters, that is the signal it belongs under the gate: report it rather than writing it.

- [ ] **Step 1: Check what already works**

The table takes rows and draws them; `vocabularyOf` already answers `"rasters"` for a raster, pinned by a test in part 14's consolidation. Establish by reading — and say in your report — how much of this task is already done. Part 14's Task 7 found its first step half-complete because an earlier task had reached into the file.

- [ ] **Step 2: Write the stories**

Following the six already there: **all three vocabularies in one table** — the story this part exists for — **a raster carrying a finding**, and **a raster with no cycle beside one with**, which is the only place a reader sees the two cell shapes together. Fixtures go in `gui/src/stories/fixtures.ts` beside the section ones, with values true to `examples/vocabulary`: `1ms`/0, `10ms`/1, `100ms`/2, and `10ms` used twice — once by the component, once by a definition.

**Choose values that make the claim visible.** Part 14 shipped a six-key fixture whose alphabetical keys made the two orderings it existed to distinguish agree at every position.

- [ ] **Step 3: Photograph, and look**

```bash
UPDATE=1 docker compose run --rm gui-screenshots
git status --short gui/screenshots/references
```

**Open every changed and new PNG and say what you saw** — the rows, the headers, whether all three vocabularies appear, whether the finding count sits on the row it belongs to, whether the cycle-less raster's cell reads `event 2` and its neighbour's `event 1, 10ms`. A table that renders as an empty box passes every gate above. "Updated N references" is not a report.

Nothing outside `components--sharedtableview--*` and your new stories may move. If anything else does, stop and report it: a reference moving for a change that should not touch it has been the tell for a real defect twice in this project.

- [ ] **Step 4: The page gate, then commit**

```bash
git add gui/src gui/screenshots/references
git commit -m "$(printf "one table, three vocabularies\n\nThe tab the Vocabulary column was renamed for in PR #68 now holds all three\nwords it was renamed to fit. The cell is composed per kind on the server, so\nthe view learns nothing about rasters.\n\nCo-Authored-By: <your model> <noreply@anthropic.com>")"
```

---

## Task 8: a raster's panel, and the chooser's third entry

**Files:**
- Create: `gui/src/components/RasterPanelView.tsx` and its stories, `gui/src/screens/RasterPanel.tsx`
- Modify: `gui/src/components/SharedAddView.tsx`, `gui/src/screens/SharedPage.tsx`, `gui/src/app/App.tsx`, `gui/src/stories/fixtures.ts`

**Interfaces:**
- Consumes: Task 6's `getRaster`, `getRasterPlan`, `rasterLabel`, `rasterSet`, `isDeclared`, `planEdit`; `screens/SectionPanel.tsx`'s shape.
- Produces: nothing another task imports.

- [ ] **Step 1: The panel**

A section's panel with different fields: `event` a number, `cycle` text, `description` text, each judged by the api rather than the panel. Its uses list every definition naming it **and every component naming it as a default** — the second is why `RasterUse.kind` has two words, and a panel listing only definitions would silently omit a component.

`Offer` is declared in each panel view. **Three copies exist and yours is the fourth** — which is the count the review that raised it asked to revisit at. Either extract it, or record in your report why not. Two panels carry written arguments against sharing it; read them before deciding, and if you extract it, rewrite those arguments rather than leaving them contradicting the code.

- [ ] **Step 2: The chooser's third entry**

`SharedAddView`'s chooser is built from `SHARED_VOCABULARIES`, which Task 6 widened, and its fields follow from the chosen kind. A raster's add takes **`event` alone** beyond the name, since `cycle` and `description` both default. `SharedPage` chooses between three panels on the route's `kind`.

- [ ] **Step 3: The stories, and the screenshots**

A raster with two uses; one nothing names, where *Remove* is offered — that is `100ms` in the real example; a refused rename; an event another raster claims, refused; and the add form with the chooser on rasters. **Open every reference and say what is in each**, including what each refusal sentence reads.

Expect `components--sharedaddview--nothing-chosen-yet.png` to move: the chooser gains an entry.

- [ ] **Step 4: Both gates, then commit**

```bash
git add gui/src gui/screenshots/references
git commit -m "$(printf "a raster's panel, and a chooser that offers all three\n\nThe last vocabulary of the tab. Its uses list the components that name it as a\ndefault beside the definitions that name it outright, which is the shape\nneither constants nor sections have.\n\nCo-Authored-By: <your model> <noreply@anthropic.com>")"
```

---

## Task 9: the journey, the documentation, and the gate

**Files:**
- Create: `gui/e2e/rasters.spec.ts`
- Modify: `docs/command_line_interface.rst`, `docs/editor_integration.rst`

- [ ] **Step 1: The journey**

Over a copy of `examples/vocabulary`: break the component's own `raster` from outside the page so `unknown-raster` is filed, open the Findings tab, follow that finding, land on the add form with the name already in it, give it an event, apply, and watch the finding go and the table gain the row. **No `page.waitForResponse`** — wait on what a reader would see. Run it three times, and the whole suite once.

Driving the **component's** raster rather than a definition's is deliberate: it is the use shape this part added, and a journey over a definition's would pass without ever exercising it.

- [ ] **Step 2: The documentation**

The `ddd gui` row of `docs/command_line_interface.rst` gains rasters beside constants and sections: what the tab lists, that a raster is renamed everywhere it is named **including a component's default**, that one can be declared — creating `rasters.ddd.json` where the project has none — that removing one is refused while anything names it or while it is all its file declares, and that an event another raster claims is refused with the reason. A capability with its refusals unstated is half a row.

`docs/editor_integration.rst`'s Rename paragraph gains a raster beside the section, including that none of the c identifier refusals it lists applies to either.

Run: `docker compose run --rm -e JAVA_TOOL_OPTIONS=-Duser.home=/tmp docs`

- [ ] **Step 3: Commit**

```bash
git add gui/e2e docs/
git commit -m "$(printf "reach a raster from the finding that complains about it\n\nOne journey drives the point, through the use shape this part added: a\ncomponent's own default naming a raster nothing declares.\n\nCo-Authored-By: <your model> <noreply@anthropic.com>")"
```

## Milestone gate

Every gate on the branch tip, none taken from an earlier task's run, **each command with its own exit status**:

```bash
cd /home/sauci/Documents/Github/ddd
.venv/bin/python -m pytest > gate.txt 2>&1; echo "PYTEST=$?"; tail -3 gate.txt
.venv/bin/ruff check .; echo "RUFF=$?"
.venv/bin/ruff format --check .; echo "FMT=$?"
.venv/bin/mypy; echo "MYPY=$?"
cd gui && npm run lint; echo "LINT=$?"
npm run typecheck; echo "TSC=$?"
npm test; echo "VITEST=$?"
npm run build; echo "BUILD=$?"
npm run ladle:build; echo "LADLE=$?"
cd .. && docker compose run --rm gui-screenshots; echo "SHOTS=$?"
git status --short gui/screenshots/references
docker compose run --rm -e JAVA_TOOL_OPTIONS=-Duser.home=/tmp docs; echo "DOCS=$?"
cd gui && PLAYWRIGHT_CHANNEL=chrome DDD_PYTHON="$PWD/../.venv/bin/python" \
  npx playwright test --output=/tmp/pw-final; echo "E2E=$?"
```

And by hand, on a copy of `examples/vocabulary`: an `unknown-raster` followed to the form that declares it, an event another raster claims read as a refusal, a rename every definition **and the component** follows, a project with no rasters file getting one, and a removal refused while a component names it. A screenshot of each, opened and looked at.

## Progress log

| Task | Commits | Review | Notes |
| --- | --- | --- | --- |
| 1 name_judge becomes `taken` | `2477fba`, `f5f8024` | clean after 1 fix round | The descriptor's sixth invariant: a `taken` lacking the name key raises at construction rather than `KeyError` at the first rename. |
| 2 `rename_problem`'s raster arm | in `a8c0177..` | clean | `'10ms' is not a usable c identifier` was the wrong answer; a raster's name is an a2l short name. |
| 3 `Use.kind` widens, `_raster_uses` | in `a8c0177..` | clean | A component's own `raster` is a use sitting inside no definition. |
| 4 the `RASTERS` descriptor | `a186951`, `06859f5` | clean after 1 fix round | **No generic function learned that rasters exist.** `set_entry` and `add_entry` gained a `_untaken` consult that reads `vocabulary.taken` and names no vocabulary. |
| 5 routes, contract, api | `8d6ce98`, `24fedde` | clean after 1 fix round | Fixed a defect already live on its parent: a `consumer-raster` finding was counted on a raster's row while routing to the variable. |
| 6 the page's lib | `cc4659c`, `89c6889` | clean after 1 fix round | Adding `rasters` to `SHOWN` orphaned the branch the rasters fixture had been the only thing reaching; `kind: "project"` is the one real kind left outside it. |
| 7 raster rows in the table | `bfaaea4` | clean, no fix round | `SharedTableView.tsx` needed **no functional change** - already generic through `vocabularyOf(row.kind)` and `row.states`. |
| 8 the panel and the chooser | `43149d8`, `828b430` | clean after 1 fix round | Five judgements moved out of `.tsx` into `lib` test-first. Three debts earlier tasks had deferred were paid here. |
| 9 journey, docs, gate | `5c29b2c`, `d8b8104` | - | The journey drives the **component's** raster, the use shape this part added. |

**Milestone gate, run at the tip:** `PYTEST=0` 4443 passed at 100 % line and branch; `RUFF=0 FMT=0
MYPY=0`; `LINT=0 TSC=0 VITEST=0` 503 passed at 100 % on all four metrics; `BUILD=0 LADLE=0`;
`SHOTS=0` 130 passed in **compare** mode with no drift; `DOCS=0`; `E2E=0` 79 passed.

**By hand, on a copy of `examples/vocabulary`:** an `unknown-raster` on a component's own default
followed to an add form with the name already in it, applied, the finding gone and the surviving one
gaining *"did you mean '10ms'?"*; `event 0 is already claimed by raster '1ms'` on a keystroke, and
the same field retyped with its **own** event refused nothing; a rename rewriting every naming site
in one plan - the reference and the declaration, whose event, cycle and description were untouched;
a project with no rasters file getting one, `includes` and all; and a Remove refused by the shape
still naming the raster.

**The copy it was driven on had been edited during the session**, so the two counts this paragraph
first quoted - *"all three naming sites"* and `2 shapes name 10ms, so it cannot be removed.` -
were that copy's and not a clean one's, and neither the wording nor the number reproduces. Measured
afresh on an unmodified `examples/vocabulary`: `10ms` has exactly one use, Pump's own default, and
`1ms` one, PumpSpeed's definition; `remove` answers `'10ms' is named by 1 shape, the first in
pump.ddd.json; nothing may name it before it goes`, and a rename of either rewrites **two** sites,
its own entry and the one shape naming it. `fixtures.ts` already says this of the same fixture -
its second use of `10ms` is marked invented, and for a reason it states.

## What was left open

Each entry says what was not done and what it costs.

- **Go to definition has no arm for a section or a raster.** `definition()` answers the declaration
  the cursor is already inside for a definition's `section` key; it was never taught either
  vocabulary, and this part does not teach it. Closing it is one small piece of work covering both.
- **A raster cannot be made acyclic from the panel.** Clearing the Cycle field sends `""`, which the
  period rule refuses, and typing `null` sends `'"null"'`, refused the same way. `cycle` is
  `str | None` where `None` is a real kind of raster - crank synchronous, on change, on demand - and
  `RasterReply.cycle` renders it as `""`, so the panel **displays a state it cannot write**. It is
  the only field on that panel that does not round-trip. Declaring an acyclic raster works, since the
  key simply defaults; only clearing one later does not. How a reader clears an optional string wants
  a design answer rather than a fix.
- **`SharedPage.tsx`'s panel chain is not exhaustive over `SharedKind`**, and neither are three
  sibling chains in that file. A fourth vocabulary stops the build at exactly one place -
  `SHARED_VOCABULARIES`'s object literal - and once that is widened `tsc` is silent, so a fourth
  word would silently open a *constant's* panel under its own route. Pre-existing; written down
  where a reader will meet it, not fixed.
- **`Offer` is declared a fourth time** rather than extracted. Measured rather than asserted:
  `Offer` is never named at a call site, so four structural copies cannot disagree silently, unlike
  the values this branch was burned by. The honest cost of sharing it is a trip to another file.
- **No Ladle story renders a raster named only by a component default.** It is pinned at the unit
  level and photographed by hand during the milestone gate, but the screenshot suite has no picture
  of the use shape this part added.

## Rulings taken

| # | Ruling | Why | Cost if wrong |
| --- | --- | --- | --- |
| 1 | The spec inherits part 14's rather than restating it | Part 14 designed all three vocabularies deliberately, so restating would create two documents that can disagree | A reader of this part must open two documents |
| 2 | `name_judge` becomes a per-key map rather than gaining a sibling field | "This name is taken" and "this event is taken" are one rule; two fields expressing one idea is the duplication the descriptor exists to avoid | A vocabulary with no project-unique key carries an empty map |
| 3 | A judge takes the entry as well as the value | A panel asks for a plan on every keystroke, so a reader re-typing their own event must not be refused against themselves | Every name judge carries an argument it ignores |
| 4 | A name judge keeps ignoring the entry | Part 14 settled that renaming a name to itself is refused and says nothing about a reader's real mistake; preserving that preserves a decision | A self-rename stays refused, as it is today |
| 5 | `Use.kind` widens rather than `Use` being restructured | A component's own raster is a third kind of use, not a different shape of one | A fourth use shape would reopen it |
| 6 | An event the model would refuse is left to `judge`, not answered by `taken` | Two refusals for one keystroke is one too many, and the model's says what a legal event looks like | A reader typing nonsense is told it is not taken rather than not legal |
