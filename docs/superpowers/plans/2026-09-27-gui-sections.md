# Sections in the GUI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sections join constants in the Shared files tab — listed, opened, edited, renamed, declared and removed — and the navigation index learns the two vocabularies it never walked, which the language server gains at the same time.

**Architecture:** Part 13 wrote `project_shared.py` and `shared_plans.py` concretely for constants, with a recorded ruling that this part would *refactor rather than extend*. So the first two tasks generalise those modules behind a per-kind `Vocabulary` descriptor with their own suites passing **untouched** as the proof that nothing moved, and only then does a second descriptor arrive. The index work comes next, because the reading and the plans both stand on it, and the page follows.

**Tech Stack:** Python 3.12+ (pydantic, no new dependency), React 19 + react-aria-components + TanStack Query (no new dependency), Vitest, Playwright (journeys and Ladle screenshots), Sphinx.

**Spec:** `docs/superpowers/specs/2026-09-27-gui-sections-design.md` — read it before Task 1. Section numbers below refer to it.

## Global Constraints

- **Python gate, every task:** `.venv/bin/python -m pytest && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy` — 100 % line **and** branch coverage, no `pragma: no cover`, no skipped tests. There is no `python` on PATH. Run `mypy` bare: it takes its targets from `pyproject.toml`.
- **Page gate, every page task:** `npm run lint && npm run typecheck && npm test && npm run build && npm run ladle:build` from `gui/`. Node is not on PATH: `export PATH="$HOME/.local/node-v24.21.0/bin:$PWD/.venv/bin:$PATH"`. Vitest is at 100 % over `src/api`, `src/lib` and `src/state`. **There are no component or screen tests in this repo and none may be added.**
- **No new dependency**, either side.
- **The interface never restates a rule the models own.** Each editable key names the model that judges it: a section's `alignment` by its own field's power-of-two rule, its `access` by `SectionAccess`, a name by `SECTION_NAME_PATTERN`.
- **A value travels as the json text its author wrote.** `alignment` is a text field, not a number input: the model wants `4`, not `4.0`, "which the published schema accepts and the loader refuses".
- **The refusal line (spec §2):** the interface **refuses** what it can see is wrong and the reader can trivially avoid; it **reports** what only the analysis can determine, or what the reader may legitimately be part-way through.
- **Every refusal names the file it concerns.**
- **A list the format requires to hold one entry may not be emptied.** `SectionsFile.sections` carries `Field(min_length=1)`, as `ConstantsFile.constants` does — part 13's Critical applies verbatim.
- **A conditional expression registers zero branches with coverage.py.** Where an arm needs a test, write statements or an early return.
- **Never `page.waitForResponse` in a journey.**
- **Commit trailer:** every commit ends with the implementer's own model in `Co-Authored-By`. Never `--amend`, never rebase.

## Review Focus

Five things the spec implies that no task's own tests would naturally reach. Each line's test is added to the task that owns the code, named there in that task's step style.

1. **`access` set through the api to a value outside the enum.** The panel's chooser offers two, but `GET /api/section-plan?action=set&key=access&raw="read-sideways"` is a request anyone can make, and writing it produces a file that does not load. Expected: refused, naming the file, the way a bad `alignment` is. *(Task 4)*
2. **A definition whose `section` key no longer holds a string.** The index recorded a use; the file has moved on since, and `raw_at` can answer anything. Expected: that use is left out, as a drifted declaration already is — not an exception reaching the route. *(Task 3)*
3. **A section whose name is also a valid C identifier, beside a variable of that spelling.** The spec says a section's name does not join `occupied`; nothing yet holds it to that. Expected: a project may declare a variable `calib` and a section `calib`, and neither rename refuses the other. *(Task 3)*
4. **The summary line with exactly one entry in a vocabulary.** Part 13's `_plural` shipped a wording no assertion could tell from the wrong one, because `"1 shape" in message` is also true of `"1 shapes"`. Expected: *"1 constant · 2 sections"*, pinned so a mutation that always pluralises fails. *(Task 6)*
5. **A section that is both named by a definition and the only entry its file declares.** Two refusals apply at once. Expected: one of them deterministically, so the sentence a reader sees does not depend on dictionary order. *(Task 2 — the guard is shared code and a constant can be both, so it is pinned where it lives)*

---
## Prerequisites

```bash
cd /home/sauci/Documents/Github/ddd
git branch --show-current          # feature/gui-sections
git log --oneline -1               # 6abb020 spec: sections in the GUI
.venv/bin/python -m pytest -q      # green, 100 %
.venv/bin/python -m ddd check examples/vocabulary/project.ddd.json
# ok: 4 variables in 1 component are consistent
```

Every Python command is `.venv/bin/python …`; there is no `python` on PATH. Node lives at
`~/.local/node-v24.21.0/bin` and is not on PATH by default:

```bash
export PATH="$HOME/.local/node-v24.21.0/bin:$PWD/.venv/bin:$PATH"
```

## Conventions

- **The fixture is `examples/vocabulary` and needs nothing added.** `sections.ddd.json` declares
  `.fast_ram` (read-write, aligned 4) and `.calib` (read-only, aligned 4), both described;
  `pump.ddd.json` places three definitions in them and carries a component-level `"raster": "10ms"`
  on line 6. The project checks clean, so a test wanting a finding makes one.
- **Unit tests build their own trees** with `conftest.write_tree`, and any test needing an index uses
  `conftest.built_of(tmp_path, **TREE)`, which returns `(Index, root)` and **writes `p.ddd.json`
  itself** — so a tree omits it.
- **A declaration's `scope` is `input`, `output` or `local`; its `kind` is `measurement`,
  `parameter`, `value_block`, `curve`, `map` or `axis`; and `conversion` and `volatile` are
  required.** A component that fails validation loads nothing, so a test built on invalid json
  asserts against an empty index. Read `src/ddd/models/` rather than guessing.
- **Docstrings carry the reason a thing is the way it is**, usually naming what went wrong without
  it. A docstring that restates its function's name is a defect here.
- **Screenshots run in Docker only:** `docker compose run --rm gui-screenshots`, with `UPDATE=1` to
  write new references. **Docs build in Docker:**
  `docker compose run --rm -e JAVA_TOOL_OPTIONS=-Duser.home=/tmp docs`.
- **Journeys need a build first**, and on this machine `PLAYWRIGHT_CHANNEL=chrome` and
  `DDD_PYTHON=<repo>/.venv/bin/python`.
- **When a test asserts a refusal, pin what distinguishes it from its neighbour.** Every review in
  part 13 found an assertion that survived the mutation it existed to catch, because a neighbouring
  refusal answered the same code with a similar message.

## File Structure

**Created**

| Path | Responsibility |
| --- | --- |
| `gui/src/screens/SectionPanel.tsx` | The section panel's screen: reads `/api/section`, asks for plans, applies them. |
| `gui/src/components/SectionPanelView.tsx` | The panel as a picture of its props. |
| `gui/src/components/SectionPanelView.stories.tsx` | Its stories, which become screenshot references. |
| `gui/e2e/sections.spec.ts` | One journey, end to end through a real server. |

**Modified**

| Path | Change |
| --- | --- |
| `src/ddd/project_shared.py` | the `Vocabulary` descriptor, the reading generalised, `CONSTANTS` and `SECTIONS`. |
| `src/ddd/shared_plans.py` | the four verbs generalised behind the same descriptor. |
| `src/ddd/lsp/navigation.py` | `index()` learns sections and rasters; `renameable_at` and `rename_sites` learn both kinds. |
| `src/ddd/finding_routes.py` | a `section` route. |
| `src/ddd/gui/contract.py` | `SectionReply` and its use model; `_ENDPOINTS`. |
| `src/ddd/gui/api.py` | `SECTION_PLANS`, `/api/section`, `/api/section-plan`, and the call sites moved to the generic readers. |
| `gui/src/api/types.ts`, `client.ts` | the new reply's re-export, `SectionPlanRequest`, `getSection`, `getSectionPlan`. |
| `gui/src/lib/shared.ts` | the summary line naming each vocabulary, and the row's `States` cell. |
| `gui/src/lib/findings.ts` | `sections` joins the kinds with a screen. |
| `gui/src/lib/route.ts` | `kind` widens from the literal `"constant"` to the tab's kinds. |
| `gui/src/lib/undo.ts` | `sectionLabel`. |
| `gui/src/components/SharedTableView.tsx` | `States` in place of `Value`, and the add form's chooser. |
| `gui/src/screens/SharedPage.tsx` | the second panel and the add form's per-kind fields. |
| `gui/src/app/App.tsx` | the section route wired as the constant's is. |
| `docs/command_line_interface.rst` | the `ddd gui` row gains sections. |

## Interfaces between the tasks

**Task 1 produces** — in `src/ddd/project_shared.py`:

```python
@dataclass(frozen=True, slots=True)
class Vocabulary:
    kind: str                                   # "constant", "section" — the word a row carries
    containers: tuple[str, ...]                 # ("constants", "component.constants") | ("sections",)
    name_key: str                               # "name" | "section"
    keys: tuple[str, ...]                       # every editable key, `description` among them
    strings: frozenset[str]                     # of those, the ones whose json value is a string
    required: frozenset[str]                    # keys the model gives no default, so may not be removed
    filename: str                               # the file `add` writes where the project has none
    entries: Callable[[Index], dict[str, Site]]        # built.constants | built.sections
    used: Callable[[Index], dict[str, list[Site]]]     # built.constant_uses | built.section_uses
    states: Callable[[Mapping[str, str]], str]         # display texts -> the row's States cell

CONSTANTS: Final = Vocabulary(...)   # kind "constant", containers ("constants", "component.constants")

def shared_rows(
    built: Index, findings: Iterable[tuple[Path, Diagnostic]], cache: dict[Path, Document]
) -> tuple[SharedRow, ...]: ...                 # every vocabulary the tab holds, by kind then name
def row_of(
    vocabulary: Vocabulary, built: Index, name: str,
    findings: Iterable[tuple[Path, Diagnostic]], cache: dict[Path, Document],
) -> SharedRow: ...
def text_of(vocabulary: Vocabulary, built: Index, name: str, key: str, cache) -> str: ...
def string_of(vocabulary: Vocabulary, built: Index, name: str, key: str, cache) -> str: ...
def shown(vocabulary: Vocabulary, built: Index, name: str, cache) -> dict[str, str]: ...
def uses_of(vocabulary: Vocabulary, built: Index, name: str, cache) -> tuple[Use, ...]: ...
def located_on(vocabulary: Vocabulary, built: Index, name: str, file: Path, found: Diagnostic) -> bool: ...
```

`description` is one of `keys` rather than a case beside them: a constant would otherwise have no
string-valued key, leaving the display branch an arm no test could reach until Task 4 and the 100 %
gate failing two tasks early. `states` picks what it wants from the display texts and ignores the
rest.

`SharedRow` gains a `states: str` field where it had `value: str`. `ConstantUse` is renamed `Use`,
its fields unchanged (`site`, `kind`, `name`, `component`). The six constants-named functions stay
as one-line bindings so `tests/test_project_shared.py` passes untouched; Task 5 moves the api to the
generic names and deletes the bindings.

**Task 2 produces** — in `src/ddd/shared_plans.py`, the same four verbs taking a descriptor first:

```python
def set_entry(vocabulary, built, name, key, raw, cache) -> SharedPlan: ...
def rename_entry(vocabulary, built, name, to, cache) -> SharedPlan: ...
def add_entry(vocabulary, built, project, name, raws, cache) -> SharedPlan: ...
def remove_entry(vocabulary, built, name, cache) -> SharedPlan: ...
def shared_project(vocabulary, project, unread, cache) -> SharedProject: ...
```

`add_entry` takes `raws: Mapping[str, str]` — one json text per required key — where `add_constant`
took a single `raw`, because a section is declared with an `access` and an `alignment` at once.
`SharedProject`'s `constants_files` becomes `files`, and `Vocabulary` gains `judge: Mapping[str,
TypeAdapter[Any]]` and `name_judge: TypeAdapter[str]`. The four constants-named verbs stay as
bindings for the same reason and for the same one task.

**Task 3 produces** — in `src/ddd/lsp/navigation.py`: `Index.sections`, `Index.section_uses`,
`Index.rasters`, `Index.raster_uses`, and `renameable_at`/`rename_sites` answering `("section",
name)` and `("raster", name)`.

**Task 4 produces** — `SECTIONS: Final = Vocabulary(...)` in `project_shared.py`, with
`name_judge` over `SECTION_NAME_PATTERN` and judges for `access` (`SectionAccess`) and `alignment`
(the model's own field).

**Task 5 produces** — `SECTION_PLANS` beside `CONSTANT_PLANS`, `GET /api/section?name=`,
`GET /api/section-plan?action=`, `contract.SectionReply`, and `route_of` answering
`Route("section", name)`.

**Task 6 produces** — `gui/src/lib/shared.ts`'s `tabTitle` naming each vocabulary,
`statesOf(entry)`, `isDeclared(reply, kind, name)` unchanged, `undo.ts`'s `sectionLabel`,
`client.ts`'s `getSection`/`getSectionPlan`/`SectionPlanRequest`, and `route.ts`'s widened `kind`.

**Tasks 7, 8 and 9 produce** screens, stories and a journey: no module another task imports.

---
## Task 1: the descriptor, and the reading generalised

**Files:**
- Modify: `src/ddd/project_shared.py`
- Modify: `tests/test_project_shared.py` (added to, never edited — see Step 5)

**Interfaces:**
- Consumes: `ddd.lsp.navigation.Index`/`Site`, `ddd.lsp.ranges.read`/`Document`, `ddd.diagnostics.Diagnostic`, `ddd.variables.declarations_of`.
- Produces: `Vocabulary`, `CONSTANTS`, `shared_rows`, `row_of`, `text_of`, `string_of`, `shown`, `uses_of`, `located_on`, and `Use` (renamed from `ConstantUse`), exactly as the **Interfaces** section spells them.

Read `src/ddd/project_shared.py` whole first. Every function in it becomes the same function with a
descriptor as its first parameter; the bodies change only where they reached for a constant-shaped
fact.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_project_shared.py`, at the end, a class exercising the generic surface:

```python
class TestTheDescriptor:
    def test_a_row_is_read_through_the_vocabulary_it_belongs_to(self, tmp_path: Path) -> None:
        # The same answer the constants-named reader gives, asked the generic way. Until sections
        # arrive this proves only that the descriptor threads through; Task 4 is what proves it
        # generalises, which is why the two arrive in that order.
        built, root = built_of(tmp_path, **TWO_HOMES)
        cache: dict[Path, Document] = {}
        assert row_of(CONSTANTS, built, "TREND_SAMPLES", (), cache) == constant_row(
            built, "TREND_SAMPLES", (), cache
        )

    def test_the_states_cell_of_a_constant_is_the_text_its_file_spells(
        self, tmp_path: Path
    ) -> None:
        # `2.0` is a fractional constant and `2` a whole one, so the cell carries the spelling.
        built, root = built_of(tmp_path, **TWO_HOMES)
        cache: dict[Path, Document] = {}
        assert row_of(CONSTANTS, built, "CELLS", (), cache).states == "2.0"

    def test_a_string_key_is_shown_without_its_quotes_and_a_literal_as_written(
        self, tmp_path: Path
    ) -> None:
        # Both arms of the display branch, which no single vocabulary would exercise if
        # `description` sat outside the editable keys.
        built, root = built_of(tmp_path, **TWO_HOMES)
        cache: dict[Path, Document] = {}
        assert shown(CONSTANTS, built, "TREND_SAMPLES", cache) == {
            "value": "16",
            "description": "slots of a trend buffer",
        }
```

Import `CONSTANTS`, `Vocabulary`, `row_of` and `shown` at the top of the file beside the existing
imports. **Do not touch any existing test in that file** — the whole of Step 5 rests on them being
untouched.

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_project_shared.py -q --no-cov -k TheDescriptor`
Expected: FAIL at collection — `ImportError: cannot import name 'Vocabulary' from 'ddd.project_shared'`.

- [ ] **Step 3: Add the descriptor**

At the top of `src/ddd/project_shared.py`, after the existing `CONSTANT` constant:

```python
@dataclass(frozen=True, slots=True)
class Vocabulary:
    """What one of the tab's vocabularies is, in the facts that differ between them.

    Three vocabularies share one table, one panel and one set of verbs, and they differ in a short,
    enumerable list: where their entries live, what their name key is called, which keys a reader may
    change and what judges each. Everything else - how a row is counted, how a use is found, how a
    rename reaches every naming site, how a file is created - is written once and takes one of
    these.

    Part 13 wrote all of it concretely for constants and recorded the ruling that this part would
    refactor rather than extend, so that the shape would be drawn from more than one real case. This
    record is that shape, drawn from three.
    """

    kind: str
    """The word a row carries in its own column: ``constant``, ``section``, ``raster``."""

    containers: tuple[str, ...]
    """The pointers its entries live at, first the vocabulary file's own. Only constants have a
    second: a component may declare them inline, where sections and rasters live in their own files
    alone."""

    name_key: str
    """What the entry calls its name: ``name`` for a constant, ``section``, ``raster``."""

    keys: tuple[str, ...]
    """Every key a reader may change, ``description`` among them, in the order the panel draws
    them."""

    strings: frozenset[str]
    """Of those keys, the ones whose json value is a string - so the panel shows them without their
    quotes and the row's cell reads as prose rather than as source."""

    entries: Callable[[Index], dict[str, Site]]
    """Where this vocabulary's own entries are recorded in the index."""

    used: Callable[[Index], dict[str, list[Site]]]
    """Where the places naming one are recorded."""

    states: Callable[[Mapping[str, str]], str]
    """The row's ``States`` cell, from the display texts of its keys. A constant states its value; a
    section its access and its alignment; a raster its event and its cycle. `Value` was the column's
    header while constants were alone in the tab and fits nothing else."""


CONSTANTS: Final = Vocabulary(
    kind=CONSTANT,
    containers=("constants", "component.constants"),
    name_key="name",
    keys=("value", "description"),
    strings=frozenset({"description"}),
    entries=lambda built: built.constants,
    used=lambda built: built.constant_uses,
    states=lambda shown: shown["value"],
)
```

Add `Callable` and `Mapping` to the `collections.abc` import.

- [ ] **Step 4: Generalise the readers**

Give each of `row_of` (from `constant_row`), `text_of` (from `constant_text`), `string_of` (from
`constant_string`), `uses_of` (from `constant_uses`) and `located_on` (from `located_on_constant`) a
`vocabulary: Vocabulary` first parameter, and replace every constants-shaped reach:

- `built.constants` becomes `vocabulary.entries(built)`;
- `built.constant_uses` becomes `vocabulary.used(built)`;
- `shared_rows` walks each vocabulary the tab holds — today `(CONSTANTS,)`, a module constant
  `HELD: Final = (CONSTANTS,)` so Task 4 adds one word — and sorts by kind then name.

Add `shown`, written as statements rather than a comprehension with a conditional, so both arms are
branches the gate can see:

```python
def shown(
    vocabulary: Vocabulary, built: Index, name: str, cache: dict[Path, Document]
) -> dict[str, str]:
    """Each editable key's display text: a string key without its quotes, any other as the json text
    its file spells.

    Written as a loop rather than a comprehension with a conditional expression, which coverage.py
    counts no branch in - the arm no vocabulary of the day exercised would pass the gate unseen.
    """
    display: dict[str, str] = {}
    for key in vocabulary.keys:
        if key in vocabulary.strings:
            display[key] = string_of(vocabulary, built, name, key, cache)
        else:
            display[key] = text_of(vocabulary, built, name, key, cache)
    return display
```

`SharedRow.value` becomes `SharedRow.states`, built by `vocabulary.states(shown(...))`.
`ConstantUse` becomes `Use`; its fields do not change.

Then, at the end of the module, the six bindings that keep the existing suite honest:

```python
# Bindings, for one task only. `tests/test_project_shared.py` passing untouched across the
# generalisation is the evidence that it moved no behaviour - the same evidence part 13's first task
# took from `tests/test_unit_plans.py`. Task 5 moves the api to the generic readers and deletes
# these; nothing else may call them.
def constant_row(built, name, findings, cache):  # noqa: ANN001, ANN201
    return row_of(CONSTANTS, built, name, findings, cache)
```

and the same one-liner shape for `constant_text`, `constant_string`, `constant_uses` and
`located_on_constant`. Give the block a single `# noqa` only where ruff's annotation rule objects,
and type them properly if it does not.

- [ ] **Step 5: Run the suite, and read what it proves**

Run: `.venv/bin/python -m pytest tests/test_project_shared.py -q --no-cov`
Expected: PASS, and `git diff --stat tests/test_project_shared.py` shows **only additions**. If any
existing test needed changing, the generalisation moved behaviour: find out what and say so in the
report rather than editing the test.

Run: `.venv/bin/python -m pytest -q && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy`
Expected: 100 % line and branch, all clean.

- [ ] **Step 6: Commit**

```bash
git add src/ddd/project_shared.py tests/test_project_shared.py
git commit -m "$(printf "read the tab's rows through the vocabulary they belong to\n\nOne record carries what differs between the three - where entries live, what\nthe name key is called, which keys may change, how a row states itself - and\nevery reader takes one. Part 13 wrote this concretely for constants and ruled\nthat this part would refactor rather than extend, so the shape is drawn from\nthree real cases rather than guessed from one.\n\ntests/test_project_shared.py gained tests and lost none, which is the evidence\nthat generalising moved no behaviour.\n\nCo-Authored-By: <your model> <noreply@anthropic.com>")"
```

---
## Task 2: the four verbs generalised

**Files:**
- Modify: `src/ddd/shared_plans.py`
- Modify: `src/ddd/project_shared.py` (the descriptor gains its plan-side fields)
- Modify: `tests/test_shared_plans.py` (added to, never edited)

**Interfaces:**
- Consumes: Task 1's `Vocabulary` and `CONSTANTS`; `ddd.editing.Operation`/`lay_out`/`DEFAULT_INDENT_UNIT`; `ddd.lsp.units.PlannedEdit`; `ddd.loading.included_files`/`resolve_path`.
- Produces: `set_entry`, `rename_entry`, `add_entry`, `remove_entry`, `shared_project` taking a descriptor; `SharedProject.files`; and `Vocabulary`'s `required`, `filename`, `judge`, `name_judge`.

Read `src/ddd/shared_plans.py` whole first, and `src/ddd/type_plans.py` beside it for the register.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_shared_plans.py`, without touching a line of what is there:

```python
class TestTheDescriptorsVerbs:
    def test_a_key_is_set_through_the_vocabulary_it_belongs_to(self, tmp_path: Path) -> None:
        built, root = built_of(tmp_path, **TWO_HOMES)
        cache: dict[Path, Document] = {}
        assert set_entry(CONSTANTS, built, "TREND_SAMPLES", "value", "2.0", cache) == set_constant(
            built, "TREND_SAMPLES", "value", "2.0", cache
        )

    def test_a_constant_both_named_and_alone_is_refused_for_being_named(
        self, tmp_path: Path
    ) -> None:
        # Both guards apply at once, and which sentence a reader meets must not depend on the order
        # a dict happened to yield. Named-by-something is checked first, because it names a place the
        # reader can go and undo; being alone in its file names only the file.
        built, root = built_of(tmp_path, **SOLE_AND_NAMED)
        cache: dict[Path, Document] = {}
        with pytest.raises(SharedRefusalError) as raised:
            remove_entry(CONSTANTS, built, "TREND_SAMPLES", cache)
        assert "is named by" in raised.value.message
        assert "is all" not in raised.value.message
```

`SOLE_AND_NAMED` is a new tree in that file: a constants file declaring exactly one constant, and a
component whose declaration is dimensioned by it. Copy the corrected shape of the trees already
there — a `scope` of `output`, a `kind` of `measurement`, and `conversion` and `volatile` present.

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_shared_plans.py -q --no-cov -k TheDescriptorsVerbs`
Expected: FAIL at collection — `ImportError: cannot import name 'set_entry'`.

- [ ] **Step 3: Give the descriptor its plan-side fields**

In `src/ddd/project_shared.py`, `Vocabulary` gains four:

```python
    required: frozenset[str]
    """Of ``keys``, the ones the model gives no default, so a reader may not take them away: a
    constant's ``value``, a section's ``access`` and ``alignment``. A file missing one does not
    load, which is the outcome the interface refuses rather than writes."""

    filename: str
    """The file ``add`` writes beside the project description where the project includes none, named
    for what it holds so that whoever opens the checkout can tell."""

    judge: Mapping[str, TypeAdapter[Any]]
    """Per key, the model that decides whether a json text may be written there. The interface never
    restates a rule: a constant's value is judged by ``ConstantValue``, a section's alignment by its
    own field's power-of-two rule."""

    name_judge: TypeAdapter[str]
    """What decides whether a name may be used. Not ``rename_problem``, whose C identifier rule fits
    a constant and neither of the others: a section's name is a linker string and a raster's an a2l
    short name, and neither joins the namespace ``occupied`` guards."""
```

`CONSTANTS` fills them: `required=frozenset({"value"})`, `filename="constants.ddd.json"`,
`judge={"value": TypeAdapter(ConstantValue), "description": TypeAdapter(str)}`, and `name_judge` the
adapter that enforces what `rename_problem` enforced for a constant — keep calling `rename_problem`
inside the constants judge so its behaviour is unchanged, and say so in a comment.

- [ ] **Step 4: Generalise the verbs**

Each of `set_constant`, `rename_constant`, `add_constant` and `remove_constant` becomes
`set_entry`/`rename_entry`/`add_entry`/`remove_entry` with `vocabulary` first, and:

- `SETTABLE` becomes `vocabulary.keys`; the "may not be left without" check reads
  `vocabulary.required`; `_value` and `_description` become one `_judged(vocabulary, key, raw, name,
  file)` reading `vocabulary.judge[key]`.
- `_entry` reads `vocabulary.entries(built)`; `remove_entry`'s use guard reads `vocabulary.used(built)`
  and its sole-entry guard reads the container from `vocabulary.containers`.
- `rename_entry` asks `vocabulary.name_judge`, then `rename_sites(built, vocabulary.kind, name)`.
- `add_entry` takes `raws: Mapping[str, str]`, judges each against `vocabulary.judge`, and builds the
  entry text from `vocabulary.name_key` and the keys given. `CONSTANTS_FILE` becomes
  `vocabulary.filename`; `SharedProject.constants_files` becomes `files`, and `shared_project` takes
  the descriptor so it recognises a file by the container the descriptor names.
- **`remove_entry` checks "named by something" before "is all its file declares"**, and a comment
  says why: the first names a place the reader can go to, the second names only a file.

Keep the four constants-named verbs as bindings, with the same comment Task 1's bindings carry.

- [ ] **Step 5: Run the suite, and read what it proves**

Run: `.venv/bin/python -m pytest tests/test_shared_plans.py -q --no-cov`
Expected: PASS, and `git diff --stat tests/test_shared_plans.py` shows **only additions**.

Run the whole Python gate. Expected: 100 %, all clean.

- [ ] **Step 6: Commit**

```bash
git add src/ddd/shared_plans.py src/ddd/project_shared.py tests/test_shared_plans.py
git commit -m "$(printf "plan a change through the vocabulary it belongs to\n\nThe four verbs take a descriptor, and every constants-shaped reach in them - the\nsettable keys, the required ones, the judge of a value, the file created, the\ncontainer a removal reads - comes off it. A name is judged by the vocabulary's\nown model rather than by rename_problem, whose c identifier rule fits a constant\nand neither of the others.\n\ntests/test_shared_plans.py gained tests and lost none.\n\nCo-Authored-By: <your model> <noreply@anthropic.com>")"
```

---

## Task 3: the index learns two vocabularies

**Files:**
- Modify: `src/ddd/lsp/navigation.py`
- Modify: `tests/test_lsp.py` (or the navigation suite that holds `index()`'s tests — find it first)

**Interfaces:**
- Consumes: `ddd.loading`'s `workspace.sections` and `workspace.rasters`, each entry carrying `location()`.
- Produces: `Index.sections`, `Index.section_uses`, `Index.rasters`, `Index.raster_uses`; `renameable_at` answering `("section", name)` and `("raster", name)`; `rename_sites` answering for both.

Read `index()` whole — in particular the constants loop it ends with, and the loop above it that
walks a structure member's dimensions, which is the shape the use walks follow.

- [ ] **Step 1: Write the failing tests**

```python
def test_a_section_is_indexed_with_every_definition_placing_data_in_it(tmp_path: Path) -> None:
    built, root = built_of(tmp_path, **PLACED)
    assert set(built.sections) == {".calib"}
    assert [site.pointer for site in built.section_uses[".calib"]] == [
        "component.interface[0].definition.section"
    ]

def test_a_raster_named_by_a_component_is_a_use_like_one_named_by_a_definition(
    tmp_path: Path,
) -> None:
    # `Component.raster` is the default for every variable the component produces - a use that is
    # not inside a definition at all, which no constant use ever was.
    built, root = built_of(tmp_path, **TIMED)
    assert [site.pointer for site in built.raster_uses["10ms"]] == [
        "component.raster",
        "component.interface[0].definition.raster",
    ]

def test_a_section_key_that_is_no_longer_a_string_is_no_use(tmp_path: Path) -> None:
    # The index is built from a file that loaded; a use is read from the file as it stands, which
    # may have moved on. Anything but a string names no section, and must be left out rather than
    # reach a caller as one.
    built, root = built_of(tmp_path, **PLACED_BY_A_NUMBER)
    assert built.section_uses == {}

def test_a_section_may_share_a_spelling_with_a_variable(tmp_path: Path) -> None:
    # A section's name is a linker string written into an attribute, not a c identifier, so it does
    # not join the namespace `occupied` guards and a project may spell both the same way.
    built, root = built_of(tmp_path, **CALIB_TWICE)
    assert rename_problem(built, "calib", "variable") is None
    assert "calib" in built.sections

def test_a_section_is_renameable_from_its_own_entry_and_from_a_use(tmp_path: Path) -> None:
    # Both ends, because a rename that reached the entry and not the uses would leave every
    # definition placing data in a section nothing declares.
    built, root = built_of(tmp_path, **PLACED)
    cache: dict[Path, Document] = {}
    assert renameable_at(read(root / "s.ddd.json", cache), "sections[0].section") == (
        "section",
        ".calib",
    )
    assert renameable_at(
        read(root / "a.ddd.json", cache), "component.interface[0].definition.section"
    ) == ("section", ".calib")
    assert [site.pointer for site in rename_sites(built, "section", ".calib")] == [
        "sections[0].section",
        "component.interface[0].definition.section",
    ]
```

`PLACED` declares `.calib` in a sections file and one definition placing data in it. `TIMED`
declares `10ms` in a rasters file, a component carrying `"raster": "10ms"` and a definition naming
it. `PLACED_BY_A_NUMBER` is `PLACED` with the definition's `section` rewritten to `4` after the
index is built — use the `edited` helper `tests/test_variable_keys.py` uses for the same trick.
`CALIB_TWICE` declares a variable named `calib` and a section named `calib`. Write the last test's
body out in full against `renameable_at`'s real signature, which takes a `Document` and a pointer.

- [ ] **Step 2: Run them to verify they fail**

Expected: `AttributeError: 'Index' object has no attribute 'sections'`.

- [ ] **Step 3: Index both vocabularies**

Four fields on `Index`, each with a docstring in the register of `constants`/`constant_uses`. In
`index()`, beside the constants loop:

```python
    for section in workspace.sections:
        built.sections[section.section] = Site(section.path, section.location().pointer)
    for raster in workspace.rasters:
        built.rasters[raster.raster] = Site(raster.path, raster.location().pointer)
```

**Neither joins `built.occupied`**, and a comment says why: a constant's name reaches generated code
as a c identifier, so a collision there is two objects sharing storage; a section's name is a linker
string and a raster's an a2l short name, and neither enters that namespace.

The use walks go where the definition loop already is: a definition's `section` and `raster` keys,
and a component's own `raster`. Each records the site only where the value read is a string, for the
reason the dimensions walk already gives.

Then `renameable_at` gains two arms, matching the entry's own name key and the places a use is
written, and `rename_sites` answers `[the entry, *uses]` for both kinds, as it does for a constant.

- [ ] **Step 4: Run the tests, then the whole gate**

Expected: PASS, 100 %, all clean. The language server's own suite must stay green untouched: teaching
`renameable_at` two kinds gives `ddd lsp` rename and go-to-definition on them, which is the point,
but it must not change what it answers for the four kinds it already knew.

- [ ] **Step 5: Commit**

```bash
git add src/ddd/lsp/navigation.py tests/
git commit -m "$(printf "index the two vocabularies nothing ever walked\n\nThe loader has collected sections and rasters all along, symmetrically with\nconstants; index() simply never read them, so every finding about one led\nnowhere and no client could rename one. A raster brings a use shape no constant\nhad: a component names one as its own default, outside any definition.\n\nNeither name joins occupied. A constant's reaches generated code as a c\nidentifier; a section's is a linker string and a raster's an a2l short name.\n\nCo-Authored-By: <your model> <noreply@anthropic.com>")"
```

---
## Task 4: the sections descriptor, and its own judges

**Files:**
- Modify: `src/ddd/project_shared.py` (the `SECTIONS` descriptor, and `HELD` gains it)
- Modify: `tests/test_project_shared.py`, `tests/test_shared_plans.py`

**Interfaces:**
- Consumes: Tasks 1-3's `Vocabulary`, the generic readers and verbs, and `Index.sections`/`section_uses`.
- Produces: `SECTIONS: Final = Vocabulary(...)`.

This is the task the whole generalisation was for: a second vocabulary should be a record and its
judges, and nothing else. **If it is not — if a generic function has to learn that sections exist —
say so in your report rather than adding a branch for it.** That is the signal the shape is wrong,
and it is worth more than a working task.

- [ ] **Step 1: Write the failing tests**

In `tests/test_project_shared.py`:

```python
class TestSections:
    def test_a_section_reads_its_access_and_its_alignment_into_one_cell(
        self, tmp_path: Path
    ) -> None:
        built, root = built_of(tmp_path, **PLACED)
        cache: dict[Path, Document] = {}
        row = row_of(SECTIONS, built, ".calib", (), cache)
        assert (row.kind, row.name, row.states) == ("section", ".calib", "read-only, align 4")

    def test_a_definition_placing_data_in_it_is_a_use_naming_its_variable(
        self, tmp_path: Path
    ) -> None:
        built, root = built_of(tmp_path, **PLACED)
        cache: dict[Path, Document] = {}
        used = uses_of(SECTIONS, built, ".calib", cache)
        assert [(use.kind, use.name, use.component) for use in used] == [
            ("variable", "Gain", "A")
        ]

    def test_both_vocabularies_share_the_table_sorted_by_kind_then_name(
        self, tmp_path: Path
    ) -> None:
        # The whole point of one tab: a reader looking for a name does not first choose which
        # vocabulary it is in.
        built, root = built_of(tmp_path, **PLACED_AND_SIZED)
        cache: dict[Path, Document] = {}
        assert [(row.kind, row.name) for row in shared_rows(built, (), cache)] == [
            ("constant", "TREND_SAMPLES"),
            ("section", ".calib"),
        ]
```

In `tests/test_shared_plans.py`:

```python
class TestSectionRefusals:
    @pytest.mark.parametrize(
        ("key", "raw"),
        [("access", '"read-sideways"'), ("alignment", "3"), ("alignment", "4.0")],
    )
    def test_a_value_the_model_would_refuse_is_refused_here(
        self, tmp_path: Path, key: str, raw: str
    ) -> None:
        # Measured on this checkout: `alignment: 3` answers `error[schema]: alignment 3 is not a
        # power of two`, and `4.0` is refused as not a whole number. Written, the file would not
        # load and every tab would empty because of one keystroke in this one. `access` reaches
        # here through the api whatever the panel's chooser offers.
        built, root = built_of(tmp_path, **PLACED)
        cache: dict[Path, Document] = {}
        with pytest.raises(SharedRefusalError) as raised:
            set_entry(SECTIONS, built, ".calib", key, raw, cache)
        assert raised.value.code == "invalid"
        assert "s.ddd.json" in raised.value.message

    def test_a_name_the_pattern_refuses_is_refused(self, tmp_path: Path) -> None:
        built, root = built_of(tmp_path, **PLACED)
        cache: dict[Path, Document] = {}
        with pytest.raises(SharedRefusalError) as raised:
            rename_entry(SECTIONS, built, ".calib", ".cal ib", cache)
        assert raised.value.code == "invalid"

    def test_a_section_may_be_renamed_to_a_name_no_c_identifier_allows(
        self, tmp_path: Path
    ) -> None:
        # The judge is the model's own pattern, not `rename_problem`: a leading dot is a normal
        # linker name and would fail a c identifier rule outright.
        built, root = built_of(tmp_path, **PLACED)
        cache: dict[Path, Document] = {}
        assert rename_entry(SECTIONS, built, ".calib", ".nvm", cache).edits
```

- [ ] **Step 2: Run them to verify they fail**

Expected: `ImportError: cannot import name 'SECTIONS'`.

- [ ] **Step 3: Write the descriptor**

```python
SECTION: Final = "section"

SECTIONS: Final = Vocabulary(
    kind=SECTION,
    containers=("sections",),
    name_key="section",
    keys=("access", "alignment", "description"),
    strings=frozenset({"access", "description"}),
    required=frozenset({"access", "alignment"}),
    filename="sections.ddd.json",
    entries=lambda built: built.sections,
    used=lambda built: built.section_uses,
    states=lambda shown: f"{shown['access']}, align {shown['alignment']}",
    judge={
        "access": TypeAdapter(SectionAccess),
        "alignment": _ALIGNMENT,
        "description": TypeAdapter(str),
    },
    name_judge=_SECTION_NAME,
)
```

`_ALIGNMENT` and `_SECTION_NAME` are `TypeAdapter`s over the model's **own** annotated types, pulled
from `ddd.models.sections` rather than rewritten — the field's power-of-two rule and
`SECTION_NAME_PATTERN`. Read that module and take the annotations it declares; if the power-of-two
rule lives in a validator rather than in the annotation, adapt `SectionDeclaration` itself for that
one key and say so in your report.

`HELD` becomes `(CONSTANTS, SECTIONS)`.

- [ ] **Step 4: Run the tests, then the whole gate**

Expected: PASS, 100 %, all clean. **Report whether any generic function needed a change**, and what,
because that is what the reviewer most needs to know.

- [ ] **Step 5: Commit**

```bash
git add src/ddd/project_shared.py tests/
git commit -m "$(printf "sections are a record and two judges\n\nA second vocabulary in the tab, and nothing generic learned that sections exist.\nIts alignment is judged by the model's own power-of-two field and its name by\nSECTION_NAME_PATTERN, because a leading dot is a normal linker name and a c\nidentifier rule would refuse it outright.\n\nCo-Authored-By: <your model> <noreply@anthropic.com>")"
```

---

## Task 5: the routes, the contract, and where a section's findings lead

**Files:**
- Modify: `src/ddd/finding_routes.py`, `src/ddd/gui/contract.py`, `src/ddd/gui/api.py`
- Modify: `tests/test_finding_routes.py`, `tests/test_gui_api.py`
- Modify: `gui/src/api/types.ts` (the re-export)

**Interfaces:**
- Consumes: Tasks 1-4's readers, verbs and `SECTIONS`.
- Produces: `SECTION_PLANS`, `GET /api/section`, `GET /api/section-plan`, `contract.SectionReply`, and `Route("section", name)`.

- [ ] **Step 1: Write the failing route tests**

```python
class TestASection:
    def test_unknown_section_leads_to_the_name_the_definition_places_data_in(
        self, tmp_path: Path
    ) -> None:
        # Measured: filed at `component.interface[0].definition.section`, whose value is the name -
        # the same shape the unit and constant branches read.
        root = built(tmp_path, **PLACED_NOWHERE)
        assert route_of(
            "unknown-section",
            root / "a.ddd.json",
            "component.interface[0].definition.section",
            "component",
            True,
            {},
        ) == Route("section", ".nvm")

    def test_duplicate_section_leads_to_the_section_its_entry_declares(
        self, tmp_path: Path
    ) -> None:
        root = built(tmp_path, **PLACED)
        assert route_of(
            "duplicate-section", root / "s.ddd.json", "sections[0].section", "sections", True, {}
        ) == Route("section", ".calib")
```

- [ ] **Step 2: Run them to verify they fail**

Expected: both answer `None`.

- [ ] **Step 3: Add the route**

`SECTION_CHECKS: Final = frozenset({"unknown-section"})` read like `CONSTANT_CHECKS` — the value at
the pointer is the name — and `WITHIN_SECTION` for a pointer inside a `sections[i]` entry, read like
`WITHIN_CONSTANT`. Both go **before** the `kind != COMPONENT_KIND` gate, since a sections file's kind
is `sections`. `Route.kind`'s docstring gains `section`, **and so does
`contract.FindingRoute.kind`'s `Literal`** — a kind missing from it makes `_finding` raise a pydantic
`ValidationError` for every finding carrying it, which is how part 13 nearly shipped a crash.

- [ ] **Step 4: The contract and the two routes**

`contract.SectionReply` beside `ConstantReply`, carrying `revision`, `name`, `file`, `pointer`, the
display texts of its keys, `uses` and `findings`; added to `_ENDPOINTS` and to
`gui/src/api/types.ts`'s re-export list. `SECTION_PLANS` beside `CONSTANT_PLANS`, with `add` taking
one query parameter per required key. The api's readers move to the generic names and **the bindings
Tasks 1 and 2 left are deleted** — that is what they were for.

Regenerate the page's types: `cd gui && npm run schemas`. That directory is gitignored
(`.gitignore:22`), so there is no diff to read: grep the file for `SectionReply` and let
`npm run typecheck` prove the page agrees.

- [ ] **Step 5: Write the api tests**

A `TestSection` class over `opened_example(tmp_path, "vocabulary", "project.ddd.json")`: the panel
names `.calib`'s file and pointer, its access and alignment, its three uses and its findings; `?name=`
missing is 400; a name no file declares is 404; each of the four actions previews; and every refusal
of spec §4.6 with its status — `not-found` as 404, `unreadable` and `invalid` as 409, a malformed
`raw` as 400.

- [ ] **Step 6: Both gates, then commit**

```bash
git add src/ddd gui/src/api/types.ts tests/
git commit -m "$(printf "serve the project's sections, and lead a finding to one\n\nTwo routes shaped like the constants pair, a section route tried before the\nkind gate since a sections file is not a component, and the bindings from tasks\n1 and 2 deleted now that the api calls the generic readers.\n\nCo-Authored-By: <your model> <noreply@anthropic.com>")"
```

---
## Task 6: the page's own decisions, under the coverage gate

**Files:**
- Modify: `gui/src/lib/shared.ts` and `shared.test.ts`, `gui/src/lib/route.ts` and `route.test.ts`, `gui/src/lib/findings.ts` and `findings.test.ts`, `gui/src/lib/undo.ts` and `undo.test.ts`, `gui/src/api/client.ts` and `client.test.ts`

**Interfaces:**
- Consumes: Task 5's `SectionReply` and `SECTION_PLANS`.
- Produces: `tabTitle` naming each vocabulary, `sectionLabel`, `getSection`, `getSectionPlan`, `SectionPlanRequest`, and `route.ts`'s widened `kind`. **No `statesOf` helper**: the server composes each row's cell through the descriptor's own `states`, so the page has nothing to decide.

Vitest is at 100 % over `src/api`, `src/lib` and `src/state`, and **no component or screen test may
be added**. Every branch written here needs a test.

- [ ] **Step 1: Write the failing tests**

```ts
describe("the tab's summary line", () => {
  test("names each vocabulary that has entries", () => {
    expect(tabTitle(entries(["constant", "constant", "section"]))).toBe("2 constants · 1 section");
  });

  test("says one of a kind in the singular", () => {
    // Part 13 shipped a plural no assertion could tell from the wrong one, because "1 shape" is a
    // substring of "1 shapes". `toBe` on the whole line is what catches a mutation that always
    // pluralises.
    expect(tabTitle(entries(["constant"]))).toBe("1 constant");
  });

  test("names only the kinds that have any", () => {
    expect(tabTitle(entries(["section", "section"]))).toBe("2 sections");
  });

  test("says a project with none declares none", () => {
    expect(tabTitle([])).toBe("This project declares nothing in its shared files.");
  });
});
```

`entries(kinds)` is a local helper building a `SharedEntry[]` from a list of kind words. Write the
route tests for `?view=shared&kind=section&name=.calib` round-tripping through `parseRoute` and
`hrefOf`, the `findings.ts` test that a sections file no longer says it has no page, the five
`sectionLabel` cases, and the `client.ts` calls with their exact urls — a section name carries a
leading dot and must be encoded.

- [ ] **Step 2: Run them to verify they fail**

Run, from `gui/`: `npx vitest run src/lib src/api`
Expected: FAIL on the summary line's new shape and on the missing exports.

- [ ] **Step 3: Implement**

`tabTitle` counts by kind and joins with ` · `, each part pluralised on its own count.
`route.ts`'s `kind` widens from the
literal `"constant"` to `"constant" | "section"`, which is what makes the tab's three route shapes
serve both. `findings.ts`'s `SHOWN` gains `sections`. `undo.ts` gains `sectionLabel` beside
`constantLabel`, using the same `fitted` helper. `client.ts` gains `getSection`, `getSectionPlan`
and a private `sectionQuery` in the shape of `constantQuery` beside it.

- [ ] **Step 4: Run the page gate, then commit**

```bash
git add gui/src/lib gui/src/api
git commit -m "$(printf "the tab's decisions with a second vocabulary in it\n\nA summary line that names each vocabulary it holds and counts each on its own,\nthe route kind widened, a sections file struck off the list of kinds with no\npage, and the client. The summary is pinned with toBe rather than a substring:\npart 13 shipped a plural no assertion could tell from the wrong one.\n\nCo-Authored-By: <your model> <noreply@anthropic.com>")"
```

---

## Task 7: the table, its new column, and section rows

**Files:**
- Modify: `gui/src/components/SharedTableView.tsx` and its stories, `gui/src/screens/SharedPage.tsx`

**Interfaces:**
- Consumes: Task 6's `tabTitle`.
- Produces: no module another task imports.

- [ ] **Step 1: Rename the column and draw both kinds**

`Value` becomes `States`, for the reason the header comment must carry: it fits a constant's `16`
and not a section's `read-only, align 4`, and this is the same call as the `Vocabulary` rename that
landed in PR #68 — cheap before a second vocabulary ships into the word, expensive after. The cell
reads `row.states`, which the server composes per kind, so the view learns nothing about sections.

- [ ] **Step 2: The did-not-load banner learns the second vocabulary**

`SharedPage` computes it as `unreadable(state, "constants")` — one kind, from when constants were
alone in the tab — so a **sections** file that failed to load would go unnamed while its rows went
missing, which is the whole failure PR #68 closed for the file whose kind could not be told. It must
name a failed file of either kind. Widen `lib/findings.ts`'s `unreadable` to take the kinds the tab
holds rather than one, and pin both in `findings.test.ts`: a constants file alone, a sections file
alone, and one of each at once. The `untold` half is unchanged.

- [ ] **Step 3: Write the stories**

Following the four already there: **both vocabularies in one table** (`.fast_ram` and `.calib`
beside `TREND_SAMPLES` and `PRESSURE_CELLS` — the story that is this tab's whole reason), **a section
carrying a finding**, and **one of each kind with nothing declared in the other**. Fixtures go in
`gui/src/stories/fixtures.ts` beside the constants ones.

- [ ] **Step 4: Photograph, and look**

```bash
UPDATE=1 docker compose run --rm gui-screenshots
git status --short gui/screenshots/references
```

Three existing Shared table references move for the column rename and the new ones are added;
nothing of parts 1-13 beyond those may move. **Open every changed and new PNG and say what you saw.**
A table that renders as an empty box passes every gate above.

- [ ] **Step 5: The page gate, then commit**

```bash
git add gui/src gui/screenshots/references
git commit -m "$(printf "one table, two vocabularies, and a column that fits both\n\nStates where the header said Value, which fitted a constant's 16 and not a\nsection's read-only, align 4. The cell is composed per kind on the server, so\nthe view learns nothing about sections.\n\nCo-Authored-By: <your model> <noreply@anthropic.com>")"
```

---

## Task 8: a section's panel, and the add form that knows two kinds

**Files:**
- Create: `gui/src/screens/SectionPanel.tsx`, `gui/src/components/SectionPanelView.tsx`, `gui/src/components/SectionPanelView.stories.tsx`
- Modify: `gui/src/screens/SharedPage.tsx`, `gui/src/components/SharedTableView.tsx`, `gui/src/app/App.tsx`

**Interfaces:**
- Consumes: Task 6's `getSection`, `getSectionPlan`, `sectionLabel`, `planEdit`, `isDeclared`; `screens/ConstantPanel.tsx`'s shape.
- Produces: nothing another task imports.

Read `gui/src/screens/ConstantPanel.tsx` and `components/ConstantPanelView.tsx` whole. The section's
pair are their siblings and must handle the same four states: a plan asked for again at every
revision, a refusal in a banner, a `stale` refusal that waits rather than clearing, and the entry
vanishing under the reader.

- [ ] **Step 1: The panel**

`access` is a chooser over `SectionAccess`'s own two values; `alignment` and `description` are text
fields — **`alignment` is text, not a number input**, because the model wants `4` and not `4.0`, and
a number input hands back one spelling for both. Its own hook is keyed `["section-plan", …]`, not a
widening of `ConstantPanel`'s, so invalidating one tab's plans does not throw away the other's.
Remove is **gated with a sentence saying why** where anything names the section or where it is the
only entry its file declares — the shape part 13's fix round settled, since the sibling's own gate
explains nothing.

- [ ] **Step 2: The add form learns two kinds**

The chooser picks a vocabulary; the fields follow from it — a name and a value for a constant, a
name, an access and an alignment for a section. Part 13's lone *Declare a constant* button becomes
one button opening the form with the chooser unset. `SharedPage` chooses between the two panels on
the route's `kind`, and `isDeclared` still decides panel-or-form.

- [ ] **Step 3: Stories, photographs, and a look**

A section with three uses; one nothing names, where *Remove* is offered; a refused rename; the add
form on sections. Then `UPDATE=1 docker compose run --rm gui-screenshots`, and **open each new PNG**.

- [ ] **Step 4: Drive it by hand**

Build the pages and run a real server over a copy of `examples/vocabulary`. The address printed
carries a token that must be **exchanged for a cookie** before the api answers — a token in the
query string on an api route gets 401. With curl: `curl -s -c jar "<printed address>"`, then
`curl -s -b jar …` with `-H "Origin: http://127.0.0.1:<port>"` on any POST.

By hand: change `.calib`'s alignment to 8 and see the preview name the file; try `3` and read the
refusal; rename `.calib` and check all three definitions followed; declare a section; remove one
nothing names; and try to remove `.fast_ram`, which two definitions name, and read what the panel
says instead of offering a button. Record what you ran and what you saw.

- [ ] **Step 5: The page gate, then commit**

```bash
git add gui/src gui/screenshots/references
git commit -m "$(printf "a section's panel, and an add form that knows two kinds\n\nIts access as a chooser over the model's own two values, its alignment as text\nbecause 4 and 4.0 are not the same whole number to the loader, the definitions\nplacing data in it, and a removal gated with a sentence rather than a button\nthat lies.\n\nCo-Authored-By: <your model> <noreply@anthropic.com>")"
```

---

## Task 9: the journey, the documentation, and the gate

**Files:**
- Create: `gui/e2e/sections.spec.ts`
- Modify: `docs/command_line_interface.rst`

- [ ] **Step 1: The journey**

Over a copy of `examples/vocabulary`: break a definition's `section` from outside the page so
`unknown-section` is filed, open the Findings tab, follow that finding, land on the add form with the
name already in it, give it an access and an alignment, apply, and watch the finding go and the table
gain the row. **No `page.waitForResponse`** — wait on what a reader would see. Run it three times,
and the whole suite once.

- [ ] **Step 2: The documentation**

The `ddd gui` row of `docs/command_line_interface.rst` gains sections beside constants: what the tab
lists, that a section is renamed everywhere it is named, that one can be declared — creating
`sections.ddd.json` where the project has none — and that removing one is refused while anything
names it or while it is all its file declares. Match the register of the rows around it: what it does
and what it refuses, the reason where a reader would otherwise ask, no marketing.

Run: `docker compose run --rm -e JAVA_TOOL_OPTIONS=-Duser.home=/tmp docs`

- [ ] **Step 3: Commit**

```bash
git add gui/e2e docs/command_line_interface.rst
git commit -m "$(printf "reach a section from the finding that complains about it\n\nOne journey drives the point: a finding nobody could act on becomes a section\ndeclared in two clicks.\n\nCo-Authored-By: <your model> <noreply@anthropic.com>")"
```

---

## Milestone gate

Every gate on the branch tip, none taken from an earlier task's run:

```bash
export PATH="$HOME/.local/node-v24.21.0/bin:$PWD/.venv/bin:$PATH"
python -m pytest -q && ruff check . && ruff format --check . && mypy
cd gui && npm run lint && npm run typecheck && npm test && npm run build && npm run ladle:build && cd ..
docker compose run --rm gui-screenshots && git status --short gui/screenshots/references
cd gui && PLAYWRIGHT_CHANNEL=chrome DDD_PYTHON="$PWD/../.venv/bin/python" npm run e2e && cd ..
docker compose run --rm -e JAVA_TOOL_OPTIONS=-Duser.home=/tmp docs
```

And by hand, on a copy of `examples/vocabulary`: an `unknown-section` followed to the form that
declares it, an alignment the model refuses read as a refusal, a rename every definition follows, a
project with no sections file getting one, and a removal refused while two definitions name it. A
screenshot of each, opened and looked at.

## Progress log

| Task | Started | Duration | Notes |
| --- | --- | --- | --- |
| | | | |

## What was left open

Filled in as the work goes. Each entry says what was not done and what it costs.

## Rulings taken

| # | Ruling | Why | Cost if wrong |
| --- | --- | --- | --- |
| 1 | The design covers three vocabularies; the part builds sections | Part 13 deferred the abstraction to the point where more than one real shape could be read; reading all three at once is what stops it being generalised twice | The spec describes more than the branch delivers, and rasters wait |
| 2 | One descriptor and one set of functions, not a module per vocabulary | The differences are a short enumerable list; three near-copies is three places for a rule to drift, which the consolidation branch just spent a commit undoing for `UNIT_CHECKS` | A fourth vocabulary that differed structurally would reopen the record |
| 3 | `description` is one of `keys`, not a case beside them | A constant would otherwise have no string-valued key, leaving the display branch an arm no test could reach until Task 4 and the gate failing two tasks early | One key in a list where it might have been a field |
| 4 | Neither name joins `occupied`, and `rename_problem` judges neither | A constant's name reaches generated code as a c identifier; a section's is a linker string and a raster's an a2l short name | A name one client accepts and another refuses |
| 5 | The refusal line is not "schema refused, checks reported" | That rule would have the interface help a reader create a `duplicate-section` it could plainly see coming; the line is what the interface can see and the reader can trivially avoid | An interface that refuses something the format permits, in two named cases |
| 6 | `remove` checks named-by-something before is-all-its-file-declares | Both can apply at once and the sentence must not depend on dictionary order; the first names a place the reader can go to | A reader meets the less useful of two true sentences |
| 7 | The column becomes `States` | `Value` fits a constant's `16` and not a section's `read-only, align 4`; same call as the `Vocabulary` rename, and cheaper now than after a second vocabulary ships into the word | Three screenshot references move |
| 8 | The index learns both vocabularies, though only sections get a tab | The two loops are one loop with a different key, and `ddd lsp` consumes a raster's entry the moment it exists | Index entries the tab does not read yet, which the editor does |
| 9 | Tasks 1 and 2 keep constants-named bindings for exactly one task | A suite passing untouched is the strongest evidence a refactor moved no behaviour, and it is the evidence part 13's first task took | Five one-line functions live two tasks longer than needed |
