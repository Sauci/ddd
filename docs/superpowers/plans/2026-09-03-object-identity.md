# Object identity across deliveries — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give a data object an opaque, immutable `id` that survives a rename, so `ddd compare` reports one `renamed-object` instead of an unrelated removal and addition, and a name freed by a rename cannot be silently claimed by a different object.

**Architecture:** The `id` is a *join key between two deliveries*, never a link inside one. Only the producing declaration writes one, only `compare` reads one; the loader, the resolution, the c backend and the a2l backend are untouched. A leaf of a structured object has no declaration of its own, so its identity is the pair *(its instance's id, its access path below the instance)*.

**Tech Stack:** Python 3.12, pydantic 2, pytest. No new runtime dependency — `secrets` and `re` are stdlib.

**Spec:** `docs/superpowers/specs/2026-09-03-object-identity-design.md`

## Global Constraints

- **Increments 1–3 only.** Section 8 of the spec (the a2l annotation and `generate a2l --baseline`) is specified and deliberately unplanned. Do not implement it; it is gated on confirming that the calibration tool in use resolves a dataset label through an `ANNOTATION`.
- **Runtime dependencies stay `pydantic>=2.7,<3` and `jinja2>=3.1,<4`.** Nothing shells out to git.
- **Line length 100.** `ruff` lint selects `E,F,W,I,N,UP,B,SIM,RUF,ANN,PTH,C4`, ignores `ANN401`, and drops `ANN` for `tests/*`. `docs/superpowers` is excluded from ruff, so this plan's code blocks are never reformatted.
- **mypy runs `strict = true` over `src/ddd`.** Every new function is fully annotated.
- **`tests/test_documentation.py` fails if a registered check is not named in *both* `README.md` and `SPEC.md`**, and if a command is not documented in the README. Every task that registers a check therefore edits both documents in the same commit — this is not optional polish.
- **Check identifiers, command names and json file formats are the tool's public interface.** New identifiers are `duplicate-id`, `consumer-identity`, `missing-id`, `renamed-object`, `reused-name`; new command `ddd id`; new key `id`.
- **Full gate before every commit:** `pytest -q`, `ruff check .`, `ruff format --check .`, `mypy`.

---

## File Structure

| File | Responsibility | Tasks |
| --- | --- | --- |
| `src/ddd/models/common.py` | the `ObjectId` constrained type and its alphabet | 1 |
| `src/ddd/models/objects.py` | the `id` key on `DataObject` | 1 |
| `src/ddd/analysis.py` | `consumer-identity`, `missing-id`, `duplicate-id`; carrying the id into the resolved forms | 2, 3, 4, 5 |
| `src/ddd/diagnostics.py` | registration of the five new checks | 2, 3, 4, 7, 8 |
| `src/ddd/ir.py` | `id` on `ResolvedObject`/`ResolvedInstance`, `instance_id` on `ResolvedLeaf`, `DICTIONARY_FORMAT = 6` | 5 |
| `src/ddd/identity.py` | **new** — generating an id, and stamping one into a description file's text | 6 |
| `src/ddd/cli.py` | the `ddd id` command and `compare --renames` | 6, 11 |
| `src/ddd/compare.py` | identity, pairing, `renamed-object`, `reused-name`, references by id, the note | 7, 8, 9, 10 |
| `schemas/*.schema.json` | the published contract, regenerated | 1 |
| `README.md`, `SPEC.md` | the checks, the key, the command | 1–11 |
| `docs/comparing_deliveries.rst`, `docs/faq.rst`, `CHANGELOG.md` | the narrative | 12 |

---

## Task 1: The `id` key

**Files:**
- Modify: `src/ddd/models/common.py` (beside `Identifier`, around line 45)
- Modify: `src/ddd/models/objects.py` (`DataObject`, after `name`, around line 243)
- Modify: `schemas/*.schema.json` (regenerated, not hand-edited)
- Modify: `SPEC.md` section 3.3, `README.md` file-formats section
- Test: `tests/test_models.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `ddd.models.common.ObjectId` (a `str` type alias constrained to the pattern), `OBJECT_ID_ALPHABET: str`, `OBJECT_ID_LENGTH: int`, `OBJECT_ID_PATTERN: str`; `DataObject.id: ObjectId | None`.

- [ ] **Step 1: Write the failing test**

In `tests/test_models.py`:

```python
def test_an_id_of_the_right_shape_is_accepted(tree):
    dictionary, bag = run_analysis(
        tree,
        {
            "project.ddd.json": project("P", "a.ddd.json"),
            "a.ddd.json": component("A", declare("local", "X", id="k7m2q9xr4t8w")),
        },
    )
    assert dictionary is not None, messages(bag)


@pytest.mark.parametrize(
    "value",
    ["k7m2q9xr4t8", "k7m2q9xr4t8ww", "K7M2Q9XR4T8W", "k7m2q9xr4t8i", "k7m2-q9xr4t8", ""],
)
def test_an_id_of_the_wrong_shape_is_refused(tree, value):
    """Too short, too long, upper case, an excluded letter, punctuation, empty."""
    _, bag = run_analysis(
        tree,
        {
            "project.ddd.json": project("P", "a.ddd.json"),
            "a.ddd.json": component("A", declare("local", "X", id=value)),
        },
    )
    assert "schema" in checks(bag), messages(bag)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_models.py -k "id_of_the" -v`
Expected: FAIL — the accepted case fails with a `schema` finding for the unknown key `id` (`extra="forbid"`), the refused cases fail for the same reason rather than for the shape.

- [ ] **Step 3: Add the constrained type**

In `src/ddd/models/common.py`, after the `Identifier` definition:

```python
OBJECT_ID_ALPHABET: Final = "abcdefghjkmnpqrstvwxyz0123456789"
"""The characters an object id is drawn from: lowercase base32 without ``i``, ``l``, ``o``
or ``u``.

Those four are excluded so that an id read off a screen, a printout or a review comment can
be typed back without ambiguity. Lowercase alone rather than both cases, because an id that
differs from another only in case is one somebody will eventually mistype into a duplicate.
"""

OBJECT_ID_LENGTH: Final = 12
"""Twelve characters, about sixty bits: a collision inside one project does not happen, and
``duplicate-id`` catches it if it does."""

OBJECT_ID_PATTERN: Final = rf"^[{OBJECT_ID_ALPHABET}]{{{OBJECT_ID_LENGTH}}}$"

ObjectId = Annotated[str, StringConstraints(pattern=OBJECT_ID_PATTERN)]
"""The identity of a data object, which survives every rename of it.

Constrained rather than free text so that a hand-typed value is refused by the schema, where
an editor reports it as it is typed, rather than by a check that only a run of the tool
reaches. ``ddd id --assign`` is what writes one.
"""
```

- [ ] **Step 4: Add the key to `DataObject`**

In `src/ddd/models/objects.py`, import `ObjectId` from `ddd.models.common` and add the field immediately after `name`:

```python
    id: ObjectId | None = None
    """Identity of this object, which survives its name.

    Written by the component that produces the object and by nothing else: a consumer stating
    one is refused as ``consumer-identity``, on the reasoning that makes ``section`` and
    ``init`` producer keys. It links this object to itself in an earlier delivery, so that
    ``ddd compare`` reports a rename as a rename rather than as a removal and an unrelated
    addition, and so that a name freed by a rename cannot be quietly claimed by something
    else.

    Nothing inside a project reads it: the producer and its consumers go on binding by name,
    and the generated c and a2l never mention it. Optional, so that a project adopts it one
    component at a time; ``missing-id`` says where it has not.
    """
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/test_models.py -k "id_of_the" -v`
Expected: PASS

- [ ] **Step 6: Regenerate the published schemas**

Run: `PYTHONPATH=src python -m ddd schema all -o schemas`
Then `git diff schemas/` and confirm the only change is the added `id` property on the definition of each kind.

- [ ] **Step 7: Document the key**

In `SPEC.md` section 3.3, in the table of definition keys, add a row for `id`: *"identity of the object, twelve lowercase base32 characters, stated by the producer only; survives a rename and is compared by nothing"*. In `README.md`, in the data object json example of the file-formats section, do **not** add it to the example — add one sentence after the example: *"A producing declaration may also carry an `id`, the identity that survives a rename; see `ddd id`."*

- [ ] **Step 8: Run the full gate and commit**

```bash
pytest -q && ruff check . && ruff format --check . && mypy
git add src/ddd/models/common.py src/ddd/models/objects.py schemas SPEC.md README.md tests/test_models.py
git commit -m "give a data object an id that survives its name"
```

---

## Task 2: `consumer-identity`

**Files:**
- Modify: `src/ddd/diagnostics.py` (the check registry, beside `consumer-storage` around line 127)
- Modify: `src/ddd/analysis.py` (`_check_declared_name`, around line 1423)
- Modify: `SPEC.md` sections 3.3.1.2 and 4, `README.md` checks table
- Test: `tests/test_models.py`

**Interfaces:**
- Consumes: `DataObject.id` from Task 1.
- Produces: the check identifier `consumer-identity`.

- [ ] **Step 1: Write the failing test**

In `tests/test_models.py`:

```python
def test_a_consumer_may_not_state_an_identity(tree):
    _, bag = run_analysis(
        tree,
        {
            "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
            "a.ddd.json": component("A", declare("output", "X", id="k7m2q9xr4t8w")),
            "b.ddd.json": component("B", declare("input", "X", id="p3rt5vwx9z2q")),
        },
    )
    assert "consumer-identity" in checks(bag), messages(bag)
    assert "'B', which reads it" in messages(bag)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_models.py::test_a_consumer_may_not_state_an_identity -v`
Expected: FAIL — `KeyError: 'consumer-identity'` from the diagnostic bag, because the check is not registered.

- [ ] **Step 3: Register the check**

In `src/ddd/diagnostics.py`, immediately after the `consumer-raster` entry:

```python
        _check("consumer-identity", Severity.ERROR,
               "a declaration that reads a variable states its identity"),
```

- [ ] **Step 4: Emit it**

In `src/ddd/analysis.py`, in `_check_declared_name`, after the `consumer-raster` branch:

```python
        if not ref.scope.is_producer and definition.id is not None:
            self._bag.add(
                "consumer-identity",
                f"'{definition.name}': the identity is decided by the component that "
                f"produces the variable, not by '{ref.component_name}', which reads it",
                ref.location("definition.id"),
            )
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `pytest tests/test_models.py::test_a_consumer_may_not_state_an_identity -v`
Expected: PASS

- [ ] **Step 6: Document the check**

In `SPEC.md` section 3.3.1.2, extend the producer-keys paragraph: an `id` on a declaration whose scope is `input` is `consumer-identity`. In `SPEC.md` section 4 and in the `README.md` checks table, add the row: `consumer-identity` — *"a declaration whose scope is `input` states an `id`"*, severity error.

- [ ] **Step 7: Run the full gate and commit**

```bash
pytest -q && ruff check . && ruff format --check . && mypy
git add src/ddd/diagnostics.py src/ddd/analysis.py SPEC.md README.md tests/test_models.py
git commit -m "refuse an identity stated by a component that only reads the variable"
```

---

## Task 3: `missing-id`

**Files:**
- Modify: `src/ddd/diagnostics.py`
- Modify: `src/ddd/analysis.py` (`_check_declared_name`)
- Modify: `SPEC.md` section 4, `README.md` checks table
- Test: `tests/test_models.py`

**Interfaces:**
- Consumes: `DataObject.id`.
- Produces: the check identifier `missing-id`.

- [ ] **Step 1: Write the failing test**

```python
def test_a_producing_declaration_without_an_identity_is_reported(tree):
    _, bag = run_analysis(
        tree,
        {
            "project.ddd.json": project("P", "a.ddd.json"),
            "a.ddd.json": component("A", declare("local", "X")),
        },
    )
    assert "missing-id" in checks(bag), messages(bag)


def test_a_reading_declaration_without_an_identity_is_not_reported(tree):
    """The key is the producer's to state, so its absence is only the producer's silence."""
    _, bag = run_analysis(
        tree,
        {
            "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
            "a.ddd.json": component("A", declare("output", "X", id="k7m2q9xr4t8w")),
            "b.ddd.json": component("B", declare("input", "X")),
        },
    )
    assert "missing-id" not in checks(bag), messages(bag)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_models.py -k missing_id -v`
Expected: the first FAILs with `KeyError: 'missing-id'`; the second passes vacuously and must keep passing.

- [ ] **Step 3: Register the check**

```python
        _check("missing-id", Severity.INFO,
               "a declaration that produces a variable states no identity for it"),
```

- [ ] **Step 4: Emit it**

In `_check_declared_name`, after the `consumer-identity` branch:

```python
        if ref.scope.is_producer and definition.id is None:
            # Info, and optional, because the key is an adoption: a project that has migrated
            # turns this into its gate with -W missing-id=error, and one that has not is not
            # stopped by a run that reports something it has not started doing.
            self._bag.add(
                "missing-id",
                f"'{definition.name}' has no 'id', so a later delivery that renames it "
                f"reports a removal and an unrelated addition; 'ddd id --assign' writes one",
                ref.location("definition.name"),
            )
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/test_models.py -k missing_id -v`
Expected: PASS

- [ ] **Step 6: Fix the fallout in the existing suite**

Every fixture project now reports `missing-id`. Run `pytest -q` and repair only assertions that compare a *complete* list of checks; assertions of the form `assert "x" in checks(bag)` are unaffected. Do **not** add ids to `tests/conftest.py`'s `declare` helper — the info finding on the ordinary fixture is the honest state of a project that has not migrated.

- [ ] **Step 7: Document the check**

`SPEC.md` section 4 under Information, and the `README.md` checks table: `missing-id` — *"a producing declaration or instance states no `id`"*, severity info.

- [ ] **Step 8: Run the full gate and commit**

```bash
pytest -q && ruff check . && ruff format --check . && mypy
git add -A
git commit -m "report a producing declaration that states no identity"
```

---

## Task 4: `duplicate-id`

**Files:**
- Modify: `src/ddd/diagnostics.py`
- Modify: `src/ddd/analysis.py` (a new `_check_identity_collisions`, called from `run` beside `_check_constant_collisions` around line 479)
- Modify: `SPEC.md` section 4, `README.md` checks table
- Test: `tests/test_models.py`

**Interfaces:**
- Consumes: `DataObject.id`, the `ordered: list[tuple[str, list[DeclarationRef]]]` shape already built in `_Analysis.run`.
- Produces: the check identifier `duplicate-id`; the method `_Analysis._check_identity_collisions(self, ordered: Sequence[tuple[str, list[DeclarationRef]]]) -> None`.

- [ ] **Step 1: Write the failing test**

```python
def test_two_objects_may_not_share_an_identity(tree):
    """The likeliest real mistake: a declaration copied to make a new object."""
    _, bag = run_analysis(
        tree,
        {
            "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
            "a.ddd.json": component("A", declare("local", "X", id="k7m2q9xr4t8w")),
            "b.ddd.json": component("B", declare("local", "Y", id="k7m2q9xr4t8w")),
        },
    )
    assert "duplicate-id" in checks(bag), messages(bag)
    assert "'Y'" in messages(bag) and "'X'" in messages(bag)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_models.py::test_two_objects_may_not_share_an_identity -v`
Expected: FAIL — `KeyError: 'duplicate-id'`.

- [ ] **Step 3: Register the check**

```python
        _check("duplicate-id", Severity.ERROR,
               "two data objects of one project carry the same id"),
```

Do **not** pass `needs_every_component=True`. That flag marks a check reaching the *wrong* answer when a file is missing — one concluding something from an absence. A duplicate concludes from a presence: seeing one half of a pair makes the run incomplete, not wrong. It therefore sits with `duplicate-type`, `duplicate-unit` and `duplicate-raster`, and the count of checks needing every component stays at **nine**, so the prose counting them in `README.md` and `SPEC.md` is untouched.

- [ ] **Step 4: Emit it**

In `src/ddd/analysis.py`, add the method and call it from `run` on the line after `self._check_constant_collisions(ordered)`:

```python
    def _check_identity_collisions(
        self, ordered: Sequence[tuple[str, list[DeclarationRef]]]
    ) -> None:
        """Two objects claiming one identity, which is a copied declaration nine times in ten.

        Reported on the second one in name order rather than on both, so the finding names a
        place to edit; the first is named in the message. The one that keeps the id is the
        one the comparison of a later delivery would pair, and choosing that by file order
        would make the report depend on the order of the includes.
        """
        seen: dict[str, str] = {}
        for name, refs in ordered:
            for ref in refs:
                identity = ref.definition.id
                if identity is None or not ref.scope.is_producer:
                    continue
                first = seen.setdefault(identity, name)
                if first != name:
                    self._bag.add(
                        "duplicate-id",
                        f"'{name}' carries the id '{identity}', which '{first}' already "
                        f"carries; an id is one object's alone, and two objects sharing one "
                        f"make a later comparison pair the wrong pair",
                        ref.location("definition.id"),
                    )
```

`Sequence` is already imported in `analysis.py`; confirm before adding an import.

- [ ] **Step 5: Run the test to verify it passes**

Run: `pytest tests/test_models.py::test_two_objects_may_not_share_an_identity -v`
Expected: PASS

- [ ] **Step 6: Document the check**

`SPEC.md` section 4 under Errors, and the `README.md` checks table: `duplicate-id` — *"two data objects of one project carry the same id"*, severity error.

- [ ] **Step 7: Run the full gate and commit**

```bash
pytest -q && ruff check . && ruff format --check . && mypy
git add -A
git commit -m "refuse two objects claiming one identity"
```

---

## Task 5: Format 6 — the id in the dictionary

**Files:**
- Modify: `src/ddd/ir.py` (`ResolvedObject` around line 110, `ResolvedLeaf` around line 375, `ResolvedInstance` around line 297, `DICTIONARY_FORMAT` at line 507)
- Modify: `src/ddd/analysis.py` (`_Variable.resolve` around line 281, the `ResolvedInstance(...)` construction around line 1794, `_flatten` around line 1830)
- Test: `tests/test_structures.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: `DataObject.id`.
- Produces: `ResolvedObject.id: str | None`, `ResolvedInstance.id: str | None`, `ResolvedLeaf.instance_id: str | None`, `DICTIONARY_FORMAT == 6`. Task 7 reads exactly these three.

- [ ] **Step 1: Write the failing test**

In `tests/test_cli.py`:

```python
def test_the_dictionary_carries_the_identity_and_states_format_six(tree, capsys):
    write_tree(
        tree,
        {
            "project.ddd.json": project("P", "a.ddd.json"),
            "a.ddd.json": component("A", declare("local", "X", id="k7m2q9xr4t8w")),
        },
    )
    assert main(["dump", str(tree / "project.ddd.json")]) == EXIT_OK
    dumped = json.loads(capsys.readouterr().out)
    assert dumped["format"] == 6
    assert dumped["objects"][0]["id"] == "k7m2q9xr4t8w"
```

In `tests/test_structures.py`, built from that file's own `struct`, `val` and `types` helpers (lines 27–50) and the declaration shape it already uses at line 228:

```python
def test_a_leaf_carries_the_identity_of_its_instance(tree):
    """A leaf has no declaration to carry an id, so it borrows its instance's."""
    dictionary, bag = run_analysis(
        tree,
        {
            "project.ddd.json": project("P", "t.ddd.json", "a.ddd.json"),
            "t.ddd.json": types(struct("S_t", val("value"), val("raw"))),
            "a.ddd.json": component(
                "A", declare("local", "Inlet", typename="S_t", id="k7m2q9xr4t8w")
            ),
        },
    )
    assert dictionary is not None, messages(bag)
    assert {leaf.path for leaf in dictionary.leaves} == {"Inlet.value", "Inlet.raw"}
    assert {leaf.instance_id for leaf in dictionary.leaves} == {"k7m2q9xr4t8w"}
```

`load` in that module returns `(workspace, bag)` and does not analyse, so this test uses
`run_analysis` from `conftest`; add it, `project`, `component`, `declare` and `messages` to
that module's import line if they are not already there.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_cli.py -k identity_and_states_format_six tests/test_structures.py -k leaf_carries -v`
Expected: FAIL — `format == 5`, and `AttributeError: 'ResolvedLeaf' object has no attribute 'instance_id'`.

- [ ] **Step 3: Add the fields and bump the format**

In `src/ddd/ir.py`, on `ResolvedObject` after `name`, and identically on `ResolvedInstance` after `name`:

```python
    id: str | None = None
    """Identity the producer gave this object, which survives a rename of it.

    Empty in a dictionary from format 5 or older, which recorded none: an object that pairs
    on nothing pairs on its name, exactly as it did then.
    """
```

On `ResolvedLeaf`, after `instance`:

```python
    instance_id: str | None = None
    """Identity of the variable this leaf belongs to; a member has none of its own.

    A leaf is identified by this together with the part of :attr:`path` below the instance,
    so renaming the instance is tracked and renaming a *member of the type* is not - the
    path is half of the identity. Empty in a dictionary from format 5 or older.
    """
```

And at line 507:

```python
DICTIONARY_FORMAT = 6
```

- [ ] **Step 4: Carry it through the resolution**

In `src/ddd/analysis.py`, in `_Variable.resolve`, add to the `ResolvedObject(...)` call, immediately after `name=self.name,`:

```python
            id=definition.id,
```

In the `ResolvedInstance(...)` construction, immediately after `name=name,`:

```python
            id=definition.id,
```

In `_flatten`, in the `out.append(ResolvedLeaf(...))` call, add:

```python
                        instance_id=instance.id,
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/test_cli.py -k identity_and_states_format_six tests/test_structures.py -k leaf_carries -v`
Expected: PASS

- [ ] **Step 6: Run the full suite and repair the format assertions**

Run: `pytest -q`. Any test asserting `format == 5` is asserting the old contract; update it to 6. A test asserting a *whole dumped dictionary* against a literal gains `"id": null` only where the fixture states one — confirm each diff rather than blanket-updating.

- [ ] **Step 7: Run the full gate and commit**

```bash
pytest -q && ruff check . && ruff format --check . && mypy
git add -A
git commit -m "carry the identity into the dictionary, at format 6"
```

---

## Task 6: `ddd id --assign`

**Files:**
- Create: `src/ddd/identity.py`
- Modify: `src/ddd/cli.py` (a subparser beside `dump`, around line 165; a `_command_id` handler)
- Modify: `README.md` command table, `SPEC.md` command list
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `ddd.models.common.OBJECT_ID_ALPHABET`, `OBJECT_ID_LENGTH`; `ddd.lsp.ranges.Document` (its public `text` and `data` attributes) and `ddd.lsp.ranges.read`.
- Produces: `ddd.lsp.ranges.Document.value_span_of(pointer: str) -> tuple[int, int] | None`; `ddd.identity.new_id() -> str`; `ddd.identity.assign(path: Path) -> int`, returning how many ids it wrote, or `-1` for a file it could not read as json.

- [ ] **Step 1: Write the failing test**

In `tests/test_cli.py`:

```python
def test_assigning_ids_writes_one_per_producing_declaration(tree, capsys):
    write_tree(
        tree,
        {
            "project.ddd.json": project("P", "a.ddd.json"),
            "a.ddd.json": component(
                "A", declare("local", "X"), declare("output", "Y"), declare("input", "Z")
            ),
        },
    )
    assert main(["id", "--assign", str(tree / "a.ddd.json")]) == EXIT_OK
    written = json.loads((tree / "a.ddd.json").read_text(encoding="utf-8"))
    interface = written["component"]["interface"]
    assert re.fullmatch(r"[a-z0-9]{12}", interface[0]["definition"]["id"])
    assert re.fullmatch(r"[a-z0-9]{12}", interface[1]["definition"]["id"])
    assert "id" not in interface[2]["definition"], "a consumer owns no identity"


def test_assigning_ids_twice_changes_nothing(tree):
    write_tree(
        tree,
        {
            "project.ddd.json": project("P", "a.ddd.json"),
            "a.ddd.json": component("A", declare("local", "X")),
        },
    )
    assert main(["id", "--assign", str(tree / "a.ddd.json")]) == EXIT_OK
    once = (tree / "a.ddd.json").read_text(encoding="utf-8")
    assert main(["id", "--assign", str(tree / "a.ddd.json")]) == EXIT_OK
    assert (tree / "a.ddd.json").read_text(encoding="utf-8") == once


def test_assigning_ids_leaves_the_rest_of_the_file_alone(tree):
    """One inserted line per declaration, and nothing else touched."""
    original = '{\n  "component": {\n    "name": "A",\n    "interface": [\n      {\n        "scope": "local",\n        "definition": {\n          "name": "X",\n          "datatype": "uint8",\n          "conversion": {"kind": "identity"},\n          "kind": "measurement",\n          "volatile": false\n        }\n      }\n    ]\n  }\n}\n'
    write_tree(tree, {"a.ddd.json": original})
    assert main(["id", "--assign", str(tree / "a.ddd.json")]) == EXIT_OK
    after = (tree / "a.ddd.json").read_text(encoding="utf-8")
    added = [line for line in after.splitlines() if line not in original.splitlines()]
    assert len(added) == 1
    assert added[0].startswith('          "id": "')


def test_assigning_ids_skips_a_file_it_cannot_parse(tree, capsys):
    write_tree(tree, {"a.ddd.json": "{ not json"})
    assert main(["id", "--assign", str(tree / "a.ddd.json")]) == EXIT_FINDINGS
    assert (tree / "a.ddd.json").read_text(encoding="utf-8") == "{ not json"


def test_assigning_ids_keeps_a_byte_order_mark(tree):
    """``ranges.read`` reads with utf-8-sig, so the mark is invisible by the time we edit.

    Written back as plain utf-8 it would be silently dropped - a change to a file this
    command promises to leave alone but for one line, and one that several Windows editors
    and PowerShell redirection put there in the first place.
    """
    path = tree / "a.ddd.json"
    write_tree(tree, {"a.ddd.json": component("A", declare("local", "X"))})
    path.write_bytes(codecs.BOM_UTF8 + path.read_bytes())
    assert main(["id", "--assign", str(path)]) == EXIT_OK
    assert path.read_bytes().startswith(codecs.BOM_UTF8)


def test_assigning_ids_keeps_the_line_endings(tree):
    """``read`` decodes with universal newlines, so a crlf file arrives here as lf.

    Written back with the default translation it would come out lf on Linux and crlf on
    Windows, whatever it went in as - a diff on every line of the file, which is exactly what
    makes editing a hand-authored source unreviewable.
    """
    path = tree / "a.ddd.json"
    write_tree(tree, {"a.ddd.json": component("A", declare("local", "X"))})
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    assert main(["id", "--assign", str(path)]) == EXIT_OK
    assert b"\r\n" in path.read_bytes()
    assert path.read_bytes().replace(b"\r\n", b"").count(b"\n") == 0
```

Add `import re` and `import codecs` to the test module if they are not already imported.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_cli.py -k assigning_ids -v`
Expected: FAIL — `argparse` exits with code 2, "invalid choice: 'id'".

- [ ] **Step 3a: Expose the offsets `Document` already holds**

`Document` records every value's span as character offsets in `self._values`, but publishes
them only as protocol line-and-character ranges through `value_range_of`. A tool editing the
text itself wants the offsets it would slice with, and converting a range back into an offset
would recompute what the document already knows. Add beside `value_range_of` in
`src/ddd/lsp/ranges.py`:

```python
    def value_span_of(self, pointer: str) -> tuple[int, int] | None:
        """Where a value's characters sit in the text, as offsets into it.

        :meth:`value_range_of` answers the same question in the line and character terms the
        protocol counts in, which is what an editor wants. A command rewriting the file wants
        the offsets it slices with, and converting one back into the other would recompute
        what the scan already recorded.
        """
        return self._values.get(pointer)
```

For a string value the span covers the quotes too — `raw_at` slices with it and is documented
as returning the source "exactly as the author wrote it" — so its end is the offset one
character past the closing quote, which is exactly where the new key goes.

- [ ] **Step 3b: Write the identity module**

Create `src/ddd/identity.py`:

```python
"""Making an identity, and writing one into a description file without reformatting it.

The insertion is textual rather than a json round trip on purpose. Rewriting the whole
document to add one key would produce a diff in which every line moved, and a diff nobody can
read is exactly what makes a tool that edits hand-authored sources dangerous. What justifies
this command is that the project is in git - the tool proposes, the diff is reviewed, a
checkout undoes it - and that justification only holds while the diff is one line per object.

The text positions come from :mod:`ddd.lsp.ranges`, which is a json-pointer-to-text utility
that happens to live under the language server; the command reuses it rather than growing a
second scanner that would drift from it.
"""

from __future__ import annotations

import json
import secrets
from pathlib import Path

from ddd.lsp.ranges import Document, read
from ddd.models.common import OBJECT_ID_ALPHABET, OBJECT_ID_LENGTH

_PRODUCING = ("output", "local")

UNREADABLE = -1
"""What :func:`assign` returns for a file it could not read as json, which is not zero.

``ranges.read`` answers an unreadable or half-written file with an empty document rather than
an exception, so "nothing to do" and "could not read it" arrive here looking identical. The
command exits non-zero on the second and says nothing about the first.
"""


def new_id() -> str:
    """A fresh identity: twelve characters of the unambiguous lowercase base32 alphabet."""
    return "".join(secrets.choice(OBJECT_ID_ALPHABET) for _ in range(OBJECT_ID_LENGTH))


def _pointers_needing_an_id(document: Document) -> list[str]:
    """The ``...definition.name`` pointer of every producing declaration that has no id.

    A component file is the only kind that declares data objects, so a file of any other kind
    yields nothing and is left untouched rather than reported: ``ddd id`` is pointed at a
    directory of description files as readily as at one component.
    """
    parsed = document.data
    if not isinstance(parsed, dict):
        return []
    component = parsed.get("component")
    if not isinstance(component, dict):
        return []
    interface = component.get("interface")
    if not isinstance(interface, list):
        return []
    wanted = []
    for index, entry in enumerate(interface):
        if not isinstance(entry, dict) or entry.get("scope") not in _PRODUCING:
            continue
        definition = entry.get("definition")
        if not isinstance(definition, dict) or "id" in definition or "name" not in definition:
            continue
        wanted.append(f"component.interface[{index}].definition.name")
    return wanted


def _indent_of_line_at(text: str, offset: int) -> str:
    """The leading whitespace of the line ``offset`` sits on, so the new key lines up.

    Whatever the file is indented with: a project writing tabs gets a tab, and one writing
    four spaces gets four. The command has no opinion about how a description is formatted.
    """
    start = text.rfind("\n", 0, offset) + 1
    return text[start : len(text) - len(text[start:].lstrip())]


def assign(path: Path) -> int:
    """Write an id into every producing declaration of ``path`` that lacks one.

    Returns how many were written, or :data:`UNREADABLE` for a file that is not json. A file
    that reads but declares no data objects is left exactly as it was and reports zero: the
    loader is what has something to say about a description, and this command must not
    rewrite one it could not read.
    """
    document = read(path, {})
    if document.data is None:
        return UNREADABLE
    pointers = _pointers_needing_an_id(document)
    if not pointers:
        return 0
    text = document.text
    # Back to front, so an insertion never moves the offset of the one before it.
    for pointer in reversed(pointers):
        span = document.value_span_of(pointer)
        if span is None:
            continue
        at = span[1]
        indent = _indent_of_line_at(text, at)
        text = f'{text[:at]},\n{indent}"id": "{new_id()}"{text[at:]}'
    # What the file was encoded and ended with, which ``read`` has already normalised away:
    # it decodes with utf-8-sig and with universal newlines, so by the time the text is here
    # a byte order mark is gone and every line ends in "\n". Writing the defaults back would
    # drop the mark and rewrite every line ending - turning a one line diff into a whole file
    # one, which is the only thing making a command that edits hand-authored sources safe.
    raw = path.read_bytes()
    encoding = "utf-8-sig" if raw.startswith(codecs.BOM_UTF8) else "utf-8"
    path.write_text(text, encoding=encoding, newline="\r\n" if b"\r\n" in raw else "\n")
    return len(pointers)
```

Add `import codecs` to the module. Drop `import json` if nothing else in the module uses it.

- [ ] **Step 4: Add the command**

In `src/ddd/cli.py`, beside the `dump` subparser:

```python
    identity = subparsers.add_parser(
        "id",
        help="write an identity into every producing declaration that has none",
        description=(
            "Stamps an 'id' into each declaration of scope 'output' or 'local' that does "
            "not carry one, editing the files in place. An identity is what lets a later "
            "'ddd compare' report a rename as a rename. A declaration that already has one "
            "is left alone, so a second run changes nothing."
        ),
    )
    identity.add_argument("files", type=Path, nargs="+", help="the description files to stamp")
    identity.add_argument(
        "--assign",
        action="store_true",
        required=True,
        help="write the ids; required, so that no run edits a file by accident",
    )
    identity.set_defaults(handler=_command_id)
```

And the handler, beside `_command_dump`:

```python
def _command_id(args: argparse.Namespace) -> int:
    """Stamp identities into description files, reporting what was written."""
    written = 0
    skipped: list[Path] = []
    for path in args.files:
        count = assign(path)
        if count == UNREADABLE:
            skipped.append(path)
        else:
            written += count
    for path in skipped:
        print(f"{path}: not readable as json, skipped", file=sys.stderr)
    print(f"wrote {written} id{'' if written == 1 else 's'}", file=sys.stderr)
    return EXIT_FINDINGS if skipped else EXIT_OK
```

Add `from ddd.identity import UNREADABLE, assign` to the cli imports.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/test_cli.py -k assigning_ids -v`
Expected: PASS — all four.

- [ ] **Step 6: Document the command**

`README.md` command table: `ddd id --assign FILE...` — *"write an identity into every producing declaration that has none"*. `SPEC.md` command list: the same entry, in the order the parser offers it. `tests/test_documentation.py` enforces both.

- [ ] **Step 7: Run the full gate and commit**

```bash
pytest -q && ruff check . && ruff format --check . && mypy
git add -A
git commit -m "add ddd id, which stamps an identity into a description file"
```

---

## Task 7: Pairing on identity, and `renamed-object`

**Files:**
- Modify: `src/ddd/compare.py` (`compare` at line 151)
- Modify: `src/ddd/diagnostics.py`
- Modify: `SPEC.md` section 4.1, `README.md` comparison table
- Test: `tests/test_compare.py`, `tests/test_comparison_tables.py`

**Interfaces:**
- Consumes: `ResolvedObject.id`, `ResolvedLeaf.instance_id`, `DataDictionary.comparable` from Task 5.
- Produces: `ddd.compare.identity(entry: Comparable) -> tuple[str, str] | None`; `ddd.compare._pair(was: Mapping[str, Comparable], now: Mapping[str, Comparable]) -> tuple[list[tuple[Comparable, Comparable]], list[Comparable], list[Comparable]]` returning *(paired, removed, added)*, each sorted by name. Tasks 8, 10 and 11 consume both.

- [ ] **Step 1: Write the failing test**

In `tests/test_compare.py`:

```python
def test_a_renamed_object_is_one_finding_not_two(tree):
    before = one_component(tree, "before", declare("local", "FiltGain", id="k7m2q9xr4t8w"))
    after = one_component(tree, "after", declare("local", "FilterGain", id="k7m2q9xr4t8w"))
    bag = verdict(before, after)
    assert checks(bag) == ["renamed-object"], messages(bag)
    assert "'FiltGain'" in messages(bag) and "'FilterGain'" in messages(bag)


def test_a_rename_that_also_changed_the_interface_reports_both(tree):
    before = one_component(
        tree, "before", declare("local", "FiltGain", "uint8", id="k7m2q9xr4t8w")
    )
    after = one_component(
        tree, "after", declare("local", "FilterGain", "uint16", id="k7m2q9xr4t8w")
    )
    bag = verdict(before, after)
    assert set(checks(bag)) == {"renamed-object", "changed-interface"}, messages(bag)


def test_a_swap_is_two_renames_and_no_interface_change(tree):
    """The case no name-matching heuristic can get right."""
    before = one_component(
        tree,
        "before",
        declare("local", "A", id="k7m2q9xr4t8w"),
        declare("local", "B", id="p3rt5vwx9z2q"),
    )
    after = one_component(
        tree,
        "after",
        declare("local", "B", id="k7m2q9xr4t8w"),
        declare("local", "A", id="p3rt5vwx9z2q"),
    )
    bag = verdict(before, after)
    assert checks(bag) == ["renamed-object", "renamed-object"], messages(bag)


def test_objects_without_an_identity_still_pair_by_name(tree):
    before = one_component(tree, "before", declare("local", "X"))
    after = one_component(tree, "after", declare("local", "X"))
    assert checks(verdict(before, after)) == [], messages(verdict(before, after))


def test_a_baseline_without_identities_infers_no_rename(tree):
    """A format 5 baseline recorded none, so a rename against it is still two findings."""
    before = one_component(tree, "before", declare("local", "FiltGain"))
    after = one_component(tree, "after", declare("local", "FilterGain", id="k7m2q9xr4t8w"))
    bag = verdict(before, after)
    assert "renamed-object" not in checks(bag), messages(bag)
    assert "removed-unused-object" in checks(bag)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_compare.py -k "renamed or swap or pair_by_name or infers_no_rename" -v`
Expected: FAIL — `KeyError: 'renamed-object'`; the two "still works" tests pass and must keep passing.

- [ ] **Step 3: Register the check**

```python
        _check("renamed-object", Severity.WARNING,
               "an object of the baseline is offered under a different name"),
```

Warning, not error: every consumer names the object it reads, so a rename that left one behind already failed `ddd check`. What breaks is outside DDD's sight — datasets, recordings, scripts.

- [ ] **Step 4: Write the identity and the pairing**

In `src/ddd/compare.py`, add above `compare`:

```python
def identity(entry: Comparable) -> tuple[str, str] | None:
    """What two deliveries join this object on, or nothing when it carries no id.

    A plain object is its id. A leaf is its instance's id together with the part of its path
    below the instance, because a member has no declaration of its own to carry one: renaming
    the instance keeps the pair, and renaming a member of the *type* changes the second half
    and is therefore not tracked - which section 2 of the design records as a known gap.
    """
    if isinstance(entry, ResolvedLeaf):
        if entry.instance_id is None:
            return None
        return (entry.instance_id, entry.path[len(entry.instance) :])
    return None if entry.id is None else (entry.id, "")


def _pair(
    was: Mapping[str, Comparable], now: Mapping[str, Comparable]
) -> tuple[list[tuple[Comparable, Comparable]], list[Comparable], list[Comparable]]:
    """Pair on identity first, then on name, and say what is left on each side.

    Two passes rather than one so that both regimes coexist while a project migrates: an
    object that carries an id pairs on it whatever it is called, and one that does not pairs
    on its name exactly as it did before ids existed.
    """
    was_by_id = {key: entry for entry in was.values() if (key := identity(entry)) is not None}
    now_by_id = {key: entry for entry in now.values() if (key := identity(entry)) is not None}

    paired: list[tuple[Comparable, Comparable]] = []
    old_done: set[str] = set()
    new_done: set[str] = set()
    for key in sorted(was_by_id.keys() & now_by_id.keys()):
        old, new = was_by_id[key], now_by_id[key]
        paired.append((old, new))
        old_done.add(old.name)
        new_done.add(new.name)

    for name in sorted(was):
        if name in old_done or name in new_done or name not in now:
            continue
        paired.append((was[name], now[name]))
        old_done.add(name)
        new_done.add(name)

    paired.sort(key=lambda pair: pair[0].name)
    removed = [was[name] for name in sorted(was) if name not in old_done]
    added = [now[name] for name in sorted(now) if name not in new_done]
    return paired, removed, added
```

Import `Mapping` from `collections.abc` and `ResolvedLeaf` from `ddd.ir` at the top of the module.

- [ ] **Step 5: Rewrite the body of `compare` around it**

Replace the two loops in `compare` (from `was = baseline.comparable` to the end of the additions loop) with:

```python
    was = baseline.comparable
    now = candidate.comparable
    paired, removed, added = _pair(was, now)

    for old, new in paired:
        if old.name != new.name:
            readers = f", read by {', '.join(old.consumers)}" if old.consumers else ""
            bag.add(
                "renamed-object",
                f"'{old.name}' is now called '{new.name}'{readers}; every dataset, recording "
                f"and script keyed by the old spelling needs migrating",
                location,
            )
        _compare_object(old, new, bag, location)

    for old in removed:
        _report_removal(old, bag, location)

    for new in added:
        bag.add(
            "added-object",
            f"'{new.name}' is new in {candidate.name} "
            f"({new.kind.value}, produced by {new.owner or 'nobody'})",
            location,
        )
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `pytest tests/test_compare.py -v`
Expected: PASS, including every test that existed before — the name-pairing path is unchanged for a project with no ids.

- [ ] **Step 7: Record the table decision**

In `tests/test_comparison_tables.py`, inside `TestComparisonTables`:

```python
    def test_the_identity_is_in_neither_table(self):
        """The id is what the pairing is *done on*, so it is never a thing compared.

        Putting it in either table would make the one commit that stamps ids report a changed
        interface on every object in the project - and in the in-project table it would make
        a consumer's silence about an id a disagreement, when a consumer may not state one at
        all.
        """
        assert "id" not in table_names(analysis._INTERFACE_FIELDS, analysis._STORAGE_FIELDS)
        assert "id" not in table_names(compare._INTERFACE_FIELDS, compare._STORAGE_FIELDS)
```

- [ ] **Step 8: Document the check**

`SPEC.md` section 4.1 and the `README.md` comparison table: `renamed-object`, warning — *"an object of the baseline is offered under a different name; its id is what says so"*.

- [ ] **Step 9: Run the full gate and commit**

```bash
pytest -q && ruff check . && ruff format --check . && mypy
git add -A
git commit -m "pair a comparison on identity, and report a rename as one finding"
```

---

## Task 8: `reused-name`

**Files:**
- Modify: `src/ddd/compare.py`
- Modify: `src/ddd/diagnostics.py`
- Modify: `SPEC.md` section 4.1, `README.md` comparison table
- Test: `tests/test_compare.py`

**Interfaces:**
- Consumes: `identity`, `_pair` from Task 7.
- Produces: the check identifier `reused-name`.

- [ ] **Step 1: Write the failing test**

```python
def test_a_name_freed_by_a_rename_and_claimed_again_is_an_error(tree):
    before = one_component(tree, "before", declare("local", "FiltGain", id="k7m2q9xr4t8w"))
    after = one_component(
        tree,
        "after",
        declare("local", "FilterGain", id="k7m2q9xr4t8w"),
        declare("local", "FiltGain", id="p3rt5vwx9z2q"),
    )
    bag = verdict(before, after)
    assert "reused-name" in checks(bag), messages(bag)
    assert "is now called 'FilterGain'" in messages(bag), "the note says where it went"


def test_a_name_reused_after_a_deletion_is_an_error(tree):
    before = one_component(tree, "before", declare("local", "X", id="k7m2q9xr4t8w"))
    after = one_component(tree, "after", declare("local", "X", id="p3rt5vwx9z2q"))
    assert "reused-name" in checks(verdict(before, after)), messages(verdict(before, after))


def test_a_name_kept_by_the_same_object_is_not_a_reuse(tree):
    before = one_component(tree, "before", declare("local", "X", id="k7m2q9xr4t8w"))
    after = one_component(tree, "after", declare("local", "X", id="k7m2q9xr4t8w"))
    assert checks(verdict(before, after)) == [], messages(verdict(before, after))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_compare.py -k reuse -v`
Expected: FAIL — `KeyError: 'reused-name'`.

- [ ] **Step 3: Register the check**

```python
        _check("reused-name", Severity.ERROR,
               "a name of the baseline now belongs to a different object"),
```

- [ ] **Step 4: Emit it**

In `compare`, after the `paired` loop and before the removals:

```python
    for name in sorted(was.keys() & now.keys()):
        before, after = identity(was[name]), identity(now[name])
        if before is None or after is None or before == after:
            continue
        # The failure that compiles, links, runs and reads the wrong storage: a dataset or a
        # recording keyed by this spelling binds to the new object as readily as to the old.
        moved = next((new.name for old, new in paired if old.name == name), None)
        notes = [(f"'{name}' is now called '{moved}'", None)] if moved else []
        bag.add(
            "reused-name",
            f"'{name}' now names a different object; a calibration dataset or a recording "
            f"keyed by that spelling will bind to it",
            location,
            notes=notes,
        )
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/test_compare.py -k reuse -v`
Expected: PASS

- [ ] **Step 6: Document the check**

`SPEC.md` section 4.1 and the `README.md` comparison table: `reused-name`, error — *"a name of the baseline now belongs to an object with a different id"*, with the sentence that it is relaxed by `-W reused-name=warning` where a project reuses names deliberately.

- [ ] **Step 7: Run the full gate and commit**

```bash
pytest -q && ruff check . && ruff format --check . && mypy
git add -A
git commit -m "report a name that now belongs to a different object"
```

---

## Task 9: References compared by identity

**Files:**
- Modify: `src/ddd/compare.py` (`_INTERFACE_FIELDS` around line 82, `_compare_object` around line 210)
- Modify: `tests/test_comparison_tables.py`
- Test: `tests/test_compare.py`

**Interfaces:**
- Consumes: `identity`, `_pair`.
- Produces: `ddd.compare._compare_references(old: Comparable, new: Comparable, was: Mapping[str, Comparable], now: Mapping[str, Comparable], renamed: frozenset[str]) -> str | None`, returning the phrase for a `changed-interface` message or `None`. `_compare_object` gains the parameters `was`, `now`, `renamed`.

- [ ] **Step 1: Write the failing test**

```python
def _curve_over(axis: str, axis_id: str, curve_id: str) -> list[dict[str, Any]]:
    return [
        declare("local", axis, kind="axis", size=8, id=axis_id),
        declare("local", "Curve", kind="curve", axis=axis, id=curve_id),
    ]


def test_renaming_an_axis_does_not_report_its_curve(tree):
    before = one_component(tree, "before", *_curve_over("A", "k7m2q9xr4t8w", "p3rt5vwx9z2q"))
    after = one_component(tree, "after", *_curve_over("B", "k7m2q9xr4t8w", "p3rt5vwx9z2q"))
    bag = verdict(before, after)
    assert checks(bag) == ["renamed-object"], messages(bag)


def test_pointing_a_curve_at_a_different_axis_is_still_an_interface_change(tree):
    before = one_component(tree, "before", *_curve_over("A", "k7m2q9xr4t8w", "p3rt5vwx9z2q"))
    after = one_component(
        tree,
        "after",
        declare("local", "A", kind="axis", size=8, id="k7m2q9xr4t8w"),
        declare("local", "Other", kind="axis", size=8, id="w9x8y7z6q5r4"),
        declare("local", "Curve", kind="curve", axis="Other", id="p3rt5vwx9z2q"),
    )
    assert "changed-interface" in checks(verdict(before, after)), messages(verdict(before, after))
```

Check the exact keys an axis and a curve take against `src/ddd/models/objects.py:489` and `:509` before running — an axis takes `size`, a curve takes `axis`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_compare.py -k curve -v`
Expected: the first FAILs with `["renamed-object", "changed-interface"]` — the curve is reported because its `references` still compare by name. The second passes and must keep passing.

- [ ] **Step 3: Take `references` out of the table**

Remove the `ComparedField("references", ...)` entry from `_INTERFACE_FIELDS` in `src/ddd/compare.py`, and replace its comment with:

```python
# ``references`` is compared by hand below rather than from this table, for the reason
# ``limits`` is: the answer is not a property of the entry alone. A referent is named, and two
# deliveries name it differently the moment it is renamed - so the comparison resolves each
# name to the referent's identity first, which no lambda over one entry can do.
```

- [ ] **Step 4: Compare them by identity**

Add to `src/ddd/compare.py`:

```python
def _referent(name: str, side: Mapping[str, Comparable]) -> tuple[str, str] | str:
    """What a referent is compared as: its identity where it has one, else its name."""
    entry = side.get(name)
    key = identity(entry) if entry is not None else None
    return key if key is not None else name


def _compare_references(
    old: Comparable,
    new: Comparable,
    was: Mapping[str, Comparable],
    now: Mapping[str, Comparable],
) -> str | None:
    """How the referents differ, or nothing when they are the same objects.

    Compared as identities so that renaming one axis reports the axis and not every curve and
    map over it: a reference that follows a rename is the same reference.
    """
    if old.references.keys() != new.references.keys():
        return _describe_reference_change(old, new)
    for field, before in old.references.items():
        if _referent(before, was) != _referent(new.references[field], now):
            return _describe_reference_change(old, new)
    return None


def _describe_reference_change(old: Comparable, new: Comparable) -> str:
    return f"references: {_describe_references(new)} != {_describe_references(old)}"
```

In `_compare_object`, thread the two sides through and fold the result into the existing `interface` decision so that the narrowed-limits suppression keeps working:

```python
    interface = differing(_interface_fields(old, new), old, new)
    references = _compare_references(old, new, was, now)
    if interface or references:
        readers = f", read by {', '.join(old.consumers)}" if old.consumers else ""
        spelled = spell_out(interface, old, new) if interface else ""
        both = ", ".join(part for part in (spelled, references or "") if part)
        bag.add(
            "changed-interface",
            f"'{old.name}' is not the same object any more ({both}){readers}",
            location,
        )
```

and change the limits guard from `if narrowed and not interface:` to `if narrowed and not interface and references is None:`.

Update the call in `compare` to `_compare_object(old, new, bag, location, was, now)` and the signature to match; keep `bag` and `location` in their current positions so the existing call sites read the same.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/test_compare.py -v`
Expected: PASS, both new tests and every existing one.

- [ ] **Step 6: Record the table decision**

In `tests/test_comparison_tables.py`, add to `TestComparisonTables`:

```python
    def test_references_are_compared_by_hand_between_deliveries(self):
        """Between two deliveries a referent is compared as an identity, not as a name.

        Inside a project the two declarations of one object are two spellings of one moment,
        so the analysis compares the names as written. Between deliveries a rename moves the
        name while the referent stays the same object - and resolving a name to an identity
        needs both sides, which a table of lambdas over one entry cannot reach.
        """
        assert "references" in table_names(analysis._INTERFACE_FIELDS, analysis._STORAGE_FIELDS)
        assert "references" not in table_names(compare._INTERFACE_FIELDS, compare._STORAGE_FIELDS)
```

The in-project half of that assertion holds today — `analysis._INTERFACE_FIELDS` carries `ComparedField("references", ...)` at `src/ddd/analysis.py:125`, and this task does not touch it.

- [ ] **Step 7: Run the full gate and commit**

```bash
pytest -q && ruff check . && ruff format --check . && mypy
git add -A
git commit -m "compare a referent by its identity, so one rename is one finding"
```

---

## Task 10: The note under an unpaired identical pair

**Files:**
- Modify: `src/ddd/compare.py` (`_report_removal` around line 195)
- Test: `tests/test_compare.py`

**Interfaces:**
- Consumes: `_pair`, `differing`, `_interface_fields`, `_STORAGE_FIELDS`.
- Produces: `_report_removal(old, bag, location, added)` — the fourth parameter is the list of unpaired additions.

- [ ] **Step 1: Write the failing test**

```python
def test_an_identical_removal_and_addition_suggest_a_lost_identity(tree):
    """Nothing in one version can see a hand-edited id; this is the only net under it."""
    before = one_component(tree, "before", declare("local", "FiltGain"))
    after = one_component(tree, "after", declare("local", "FilterGain"))
    bag = verdict(before, after)
    assert "removed-unused-object" in checks(bag), messages(bag)
    assert "the id did not travel with it" in messages(bag)


def test_no_such_note_when_the_two_differ(tree):
    before = one_component(tree, "before", declare("local", "FiltGain", "uint8"))
    after = one_component(tree, "after", declare("local", "FilterGain", "uint16"))
    assert "did not travel" not in messages(verdict(before, after))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_compare.py -k travel -v`
Expected: the first FAILs on the missing note text; the second passes and must keep passing.

- [ ] **Step 3: Write the note**

In `src/ddd/compare.py`:

```python
def _lost_identity_note(
    old: Comparable, added: Sequence[Comparable]
) -> list[tuple[str, Location | None]]:
    """A note naming an addition identical to this removal, if there is exactly one.

    It asserts nothing and pairs nothing - the two really may be different objects. What it
    catches is the case no check can: an id edited by hand or mangled by a merge, after which
    the object is two unrelated objects again and every finding about it is technically true
    and completely unhelpful. Exactly one candidate, because naming several would be a guess
    dressed as a list.
    """
    same = [
        new
        for new in added
        if not differing(_interface_fields(old, new), old, new)
        and not differing(_STORAGE_FIELDS, old, new)
    ]
    if len(same) != 1:
        return []
    return [
        (
            f"'{same[0].name}' was added with an identical interface; if that was a rename, "
            f"the id did not travel with it",
            None,
        )
    ]
```

Then give `_report_removal` the extra parameter and pass the note into both of its `bag.add` calls:

```python
def _report_removal(
    old: Comparable, bag: DiagnosticBag, location: Location | None, added: Sequence[Comparable]
) -> None:
    notes = _lost_identity_note(old, added)
    if old.consumers:
        bag.add(
            "removed-object",
            f"'{old.name}' is gone, but was read by {', '.join(old.consumers)}",
            location,
            notes=notes,
        )
    else:
        bag.add(
            "removed-unused-object",
            f"'{old.name}' is gone; no component read it, but a calibration dataset or an "
            f"external tool still might",
            location,
            notes=notes,
        )
```

and in `compare`, call it as `_report_removal(old, bag, location, added)`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_compare.py -k travel -v`
Expected: PASS

- [ ] **Step 5: Run the full gate and commit**

```bash
pytest -q && ruff check . && ruff format --check . && mypy
git add -A
git commit -m "note an addition identical to a removal, where an identity went missing"
```

---

## Task 11: `compare --renames`

**Files:**
- Modify: `src/ddd/cli.py` (the `compare` subparser at line 131, `_command_compare` around line 1030)
- Modify: `src/ddd/compare.py`
- Modify: `README.md` command table
- Test: `tests/test_compare.py`

**Interfaces:**
- Consumes: `_pair` from Task 7.
- Produces: `ddd.compare.renames(baseline: DataDictionary, candidate: DataDictionary) -> list[dict[str, str]]`, each entry `{"id": ..., "from": ..., "to": ...}`, sorted by `"to"`.

- [ ] **Step 1: Write the failing test**

```python
def test_the_renames_file_lists_the_pairs_a_dataset_needs(tree, tmp_path):
    write_tree(
        tree,
        {
            "before.ddd.json": project("P", "before-a.ddd.json"),
            "before-a.ddd.json": component("A", declare("local", "FiltGain", id="k7m2q9xr4t8w")),
            "after.ddd.json": project("P", "after-a.ddd.json"),
            "after-a.ddd.json": component("A", declare("local", "FilterGain", id="k7m2q9xr4t8w")),
        },
    )
    out = tmp_path / "renames.json"
    main(
        [
            "compare",
            str(tree / "before.ddd.json"),
            str(tree / "after.ddd.json"),
            "--renames",
            str(out),
        ]
    )
    assert json.loads(out.read_text(encoding="utf-8")) == [
        {"id": "k7m2q9xr4t8w", "from": "FiltGain", "to": "FilterGain"}
    ]


def test_a_comparison_with_no_renames_writes_an_empty_list(tree, tmp_path):
    """So a build step can tell 'no renames' from 'compare never ran'."""
    write_tree(
        tree,
        {
            "before.ddd.json": project("P", "before-a.ddd.json"),
            "before-a.ddd.json": component("A", declare("local", "X", id="k7m2q9xr4t8w")),
            "after.ddd.json": project("P", "after-a.ddd.json"),
            "after-a.ddd.json": component("A", declare("local", "X", id="k7m2q9xr4t8w")),
        },
    )
    out = tmp_path / "renames.json"
    main(
        [
            "compare",
            str(tree / "before.ddd.json"),
            str(tree / "after.ddd.json"),
            "--renames",
            str(out),
        ]
    )
    assert json.loads(out.read_text(encoding="utf-8")) == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_compare.py -k renames_file -v`
Expected: FAIL — argparse exits 2, "unrecognized arguments: --renames".

- [ ] **Step 3: Write the map**

In `src/ddd/compare.py`:

```python
def renames(baseline: DataDictionary, candidate: DataDictionary) -> list[dict[str, str]]:
    """The old-to-new name pairs of this comparison, for migrating what DDD cannot see.

    Sorted by the new name, so two runs of one comparison produce the same file and a diff of
    two such files means something.
    """
    paired, _, _ = _pair(baseline.comparable, candidate.comparable)
    moved = [
        {"id": key[0], "from": old.name, "to": new.name}
        for old, new in paired
        if old.name != new.name and (key := identity(old)) is not None
    ]
    return sorted(moved, key=lambda entry: entry["to"])
```

- [ ] **Step 4: Add the flag**

In `src/ddd/cli.py`, on the `compare` subparser:

```python
    compare_parser.add_argument(
        "--renames",
        type=Path,
        help="also write the old-to-new name pairs here, for migrating datasets and recordings",
    )
```

And in `_command_compare`, after `compare(...)` has run and before the verdict is printed:

```python
    if args.renames is not None:
        # Written whether or not the comparison found errors: a delivery that cannot be
        # accepted still needs its renames listed, so that whoever fixes it knows what moved.
        args.renames.write_text(
            json.dumps(renames(baseline, candidate), indent=2) + "\n", encoding="utf-8"
        )
```

Add `renames` to the `from ddd.compare import ...` line in the cli, and confirm `json` is imported there.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/test_compare.py -k renames_file -v`
Expected: PASS

- [ ] **Step 6: Document the flag**

`README.md`, in the comparing-two-deliveries section, add the flag to the example block and one sentence saying what the file is for. The command table entry for `ddd compare` stays as it is.

- [ ] **Step 7: Run the full gate and commit**

```bash
pytest -q && ruff check . && ruff format --check . && mypy
git add -A
git commit -m "write the rename pairs a dataset migration needs"
```

---

## Task 12: The narrative documentation

**Files:**
- Modify: `docs/comparing_deliveries.rst`
- Modify: `docs/faq.rst`
- Modify: `CHANGELOG.md`
- Test: `tests/test_documentation.py` (run, not edited)

**Interfaces:**
- Consumes: everything above.
- Produces: nothing further tasks read.

- [ ] **Step 1: Write the migration story**

In `docs/comparing_deliveries.rst`, a new section after the existing baseline workflow, following that file's heading style:

```rst
Renames
-------

A rename is invisible to a comparison keyed on names: the old spelling is a removal and the
new one an unrelated addition, and the interface comparison never runs across the pair. An
``id`` on the producing declaration is what relates them.

.. code-block:: bash

   ddd id --assign components/*.ddd.json    # once, per project
   ddd dump project.ddd.json > baseline.json                    # at release time
   ddd compare baseline.json project.ddd.json --renames renames.json

``renames.json`` holds one entry per renamed object - its id, the old name and the new one -
which is what a dataset, a recorded measurement or a test script is migrated with. The
comparison itself reports ``renamed-object`` for each, and ``reused-name`` where a spelling
freed by a rename has been claimed by a different object, which is the failure that binds an
old dataset to new storage without anything looking broken.
```

- [ ] **Step 2: Write the history recipe**

In `docs/faq.rst`, a new entry in that file's existing question style:

```rst
What happened to this variable?
-------------------------------

An id, once written, is never rewritten, so it is still there, under whatever name and in
whatever file, after a rename or a move:

.. code-block:: bash

   git grep k7m2q9xr4t8w -- '*.ddd.json'

``git log -S`` finds the commit that first wrote the id, and a commit where the declaration
was added to or removed from a file:

.. code-block:: bash

   git log -S k7m2q9xr4t8w --oneline -- '*.ddd.json'

Not a rename: renaming an object edits its ``name``, never its ``id`` line, so the count
``-S`` looks for does not change and the rename commit is invisible to it. What an object used
to be called is what ``ddd compare --renames`` already wrote down in ``renames.json`` when the
rename happened - the record to keep, rather than one to reconstruct from git. DDD has no
command wrapping any of this, and needs none: it reads no git.
```

- [ ] **Step 3: Write the changelog entry**

In `CHANGELOG.md`, under the unreleased heading, matching that file's existing wording for a format change — it must say what a migration costs:

```markdown
### Added

- `id` on a producing declaration: the identity of a data object, which survives a rename.
  `ddd compare` pairs on it, so a rename is one `renamed-object` finding with the interface
  comparison still running across it, rather than a removal and an unrelated addition. A name
  freed by a rename and claimed by a different object is `reused-name`, an error.
- `ddd id --assign FILE...` writes an id into every producing declaration that has none,
  editing the files in place; a second run changes nothing.
- `ddd compare --renames PATH` writes the old-to-new name pairs, for migrating calibration
  datasets, recordings and test scripts.

### Changed

- The dictionary format is 6. A dictionary from format 5 reads back unchanged and its objects
  pair by name, so no rename is inferred against an older baseline. **Migration:** run
  `ddd id --assign` over the description files once and commit the result; until then every
  producing declaration reports `missing-id` at info, which a migrated project turns into its
  gate with `-W missing-id=error`.
```

- [ ] **Step 4: Verify the documentation gate**

Run: `pytest tests/test_documentation.py -v`
Expected: PASS — every registered check named in both README.md and SPEC.md, every command documented, no dead file links.

- [ ] **Step 5: Run the full gate and commit**

```bash
pytest -q && ruff check . && ruff format --check . && mypy
git add -A
git commit -m "document renames, the identity, and what migrating to format 6 costs"
```

---

## Self-review notes

**Spec coverage.** §3.1 → Task 1. §3.2 → Tasks 1, 2. §3.3 → Task 5 (`instance_id`) and Task 7 (`identity`). §4.1 → Task 5. §4.2 → Task 3. §4.3 → Task 6. §5.1 → Task 7. §5.2 → Task 7. §5.3 → Task 8. §5.4 → Task 9. §5.5 → Task 10. §6 → Tasks 2, 3, 4, 7, 8. §7 → Task 11. §8 → **deliberately unplanned**, per Global Constraints. §9 → Task 12. §10 → Tasks 1 and 5. §11 → distributed across every task. §12 → Tasks 1–12. §13 → the task ordering itself. §14 → nothing to build.

**Both open questions from the first draft are resolved**, so no task guesses. `ranges.Document` publishes the parsed document as `.data` and the text as `.text`, and holds every value's offsets in `_values` — which Task 6 Step 3a publishes as `value_span_of` rather than converting a protocol range back into an offset. `analysis._INTERFACE_FIELDS` does carry `ComparedField("references", ...)`, at `src/ddd/analysis.py:125`.

**One bug the first draft would have shipped**, caught while resolving those and now covered by two tests in Task 6: `ranges.read` decodes with `utf-8-sig` *and* universal newlines, so by the time `assign` has the text a byte order mark is gone and every line ends in `\n`. Writing the defaults back would strip the mark and rewrite every line ending of a crlf file — a whole-file diff from a command whose entire safety argument is that its diff is one line per object.

**One judgement call worth a reviewer's attention:** `src/ddd/identity.py` imports from `ddd.lsp.ranges`, so the cli now depends on the language server package for a json-pointer-to-text utility that is not really about the protocol. The alternative — a second scanner in `identity.py` — would drift from the one the editor uses, which is worse. If a reviewer disagrees, the fix is to lift `ranges.py` out of `lsp/` rather than to duplicate it.

**Names used consistently across tasks:** `identity()`, `_pair()`, `renames()`, `_compare_references()`, `_lost_identity_note()`, `new_id()`, `assign()`, `ResolvedObject.id`, `ResolvedInstance.id`, `ResolvedLeaf.instance_id`, `DICTIONARY_FORMAT == 6`.
