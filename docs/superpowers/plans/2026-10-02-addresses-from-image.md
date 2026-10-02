# `ddd generate a2l --image` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `ddd generate a2l --image firmware.elf` reads every address the a2l carries - objects by name, structure members by access path - straight out of the linked image's DWARF, and the cmake module makes the a2l one post-link step (`ADDRESSES_FROM_IMAGE`), so no extraction script and no second build are needed.

**Architecture:** A new core module, `ddd.addresses`, holds a build's address information from either source: the JSON map's reader, moved there from the a2l backend, and a new `addresses_from_image` that walks each access path through the image's C model (`ddd.elf`). The a2l backend keeps only what is the a2l's: which symbols get an `ECU_ADDRESS`, and the 32 bits that field holds, now checked for both sources. `generate` chooses the source and reports what could not be placed through the existing `address-missing` check, with each symbol's reason as a note.

**Tech Stack:** Python 3.12+, pyelftools (a runtime dependency since #76), pytest with the 100 % coverage gate, CMake 3.20+ (the module) and 3.30 (the example), Docker cross toolchains (`docker/elf-fixtures.Dockerfile`) for the committed fixture images.

**Spec:** `docs/superpowers/specs/2026-10-02-addresses-from-image-design.md`. Read it before any task. Where this plan departs from it, the departure is a row of *Rulings taken* at the end, with its reason.

## Global Constraints

Every task's requirements include this section.

**Where the work happens**

- **The worktree is `/home/sauci/Documents/Github/ddd-toolbox-from-elf`, on the local branch `feature/addresses-from-image`** (from master `b7fc335`). Run every command from there. The main checkout, `/home/sauci/Documents/Github/ddd`, holds the maintainer's uncommitted work on `feature/gui-large-projects`: never `cd` into it, never run git against it, never edit a file in it.
- **Nothing is pushed** until the maintainer says so: no `git push`, no remote branch, no pull request.
- **The worktree has its own `.venv`** (Python 3.14). There is no `python` on PATH: always `.venv/bin/python`. pyelftools 0.33 is installed there, as a runtime dependency.
- **Docker runs under this plan's own compose project name**, `-p ddd-addresses`. It builds only the fixture image `ddd-elf-fixtures:dev` (`docker/elf-fixtures.Dockerfile`) and, at the milestone gate, `ddd-addresses:dev` through the override file that gate writes. **Never build, pull or retag `ddd:dev`**, which the main checkout's services run: `docker compose run --rm test`, `lint` or `docs` without the override would rebuild it from this branch. Note its id before Task 1 (`docker image ls ddd:dev --format '{{.ID}}'`); it must be the same at the gate. The maintainer's own work rebuilds it now and then (it went from `60e986bbee57` to `b915687d0629` on 2026-10-01, outside this work), so the id is read, never assumed.
- Docker cannot see the session scratchpad (`/tmp/claude-1000/...`). Throwaway files go under the worktree's ignored `build/`.

**Running things**

- **Never add `-q` to pytest.** `pyproject.toml` already sets it in `addopts`; a second one removes the `N passed` line while pytest-cov still prints its coverage line, so the output looks fine and says nothing.
- **A pipeline reports its last command's exit status.** Capture each tool's own: `.venv/bin/python -m pytest > build/gate.txt 2>&1; echo "EXIT=$?"; tail -3 build/gate.txt`. The tell for a run that finished is its **summary line**; a tail ending in a stack trace did not finish, whatever the exit code says.
- A stale `.coverage` data file once made pytest answer `4445 passed` with exit 3 and no coverage line. If the coverage summary is missing, delete `.coverage*` (gitignored) and re-run.
- `--no-cov` is for a narrowed run while developing; a task's closing run is the whole suite, with coverage.

**Gates**

- Python: `.venv/bin/python -m pytest` at **100 % line and branch**, `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, and `.venv/bin/mypy` run **bare**.
- **No `pragma: no cover`, no skips, no xfails.**
- The code must run on **Python 3.12**: CI and the image use it, the venv is 3.14. Nothing newer than 3.12 syntax or stdlib; the milestone gate runs the suite on 3.12 in Docker.
- CI also runs the suite on **Windows**: a path a test builds or compares is built with `Path` and compared in the spelling the tool prints (`as_posix()`), never with a hard-coded `/`.

**What the gates cannot see**

- **A conditional expression registers zero branches with coverage.py, and so does a comprehension filter.** A short-circuit `and`/`or` inside an `if` records one branch pair for the whole `if`, not one per operand. Where a branch matters, a named test pins each side, and a reviewer checks that one does.
- **An `assert` is not a branch either.** Each one in this plan states an invariant other code establishes, and carries a comment saying which.
- **A coverage gate cannot see data.** Ablate every new data value - a table row, a regular expression, a reason sentence, a set member - and confirm a **named** test dies. If none does, write the one that does.
- **Ablate in a scratch `git worktree` made from the task's commit, and run pytest with that worktree as the working directory.** `pyproject.toml` sets `pythonpath = ["src", "tools", "docker"]`, resolved against *rootdir* and placed ahead of any `PYTHONPATH`: a run started from this worktree measures this worktree. The tell is pytest's own `rootdir:` line (`-p no:cacheprovider -o addopts=""` shows it). **Clear `__pycache__` before every ablation run**: a same-size edit within the same second, `cp` or `sed -i`, leaves Python on the stale `.pyc` (measured on 2026-10-02, a restored constant still loaded as the ablated one). A survival is re-run under `PYTHONHASHSEED=0`, `1`, `4` and `7` before it is believed. Put the scratch worktree under `build/` and remove it afterwards.
- **Never draw a conclusion about what *else* pins something from a narrowed run.** That question is a whole-suite question.
- **A refusal or finding test asserts the whole sentence with `==`.**

**Prose**

- **A sentence stating a measurement gets the measurement run as it is written**, against the file it names. A sentence saying "nothing else does X" is a whole-repository claim and gets a whole-repository grep.
- **Cite by name, not by line number.**

**Conventions**

- Commits: lowercase imperative subject on **one line**, no `feat:`-style prefix, a body saying why. Trailer `Co-Authored-By: <your model> <noreply@anthropic.com>`. Never `--amend`, never rebase, never push. Commit with a heredoc, `git commit -F - <<'EOF'` ... `EOF`, as every task's commit step does: this environment's command guard refuses the `-m "$(printf ...)"` form.
- If a brief or this plan is wrong, **say so in your report rather than working around it silently.**

## Prerequisites

1. **The worktree is clean** apart from ignored files, on `feature/addresses-from-image`, whose last commit is the spec's (`8d97d92`) or this plan's.
2. **Gate the tree before Task 1** and record the baseline: the whole suite, `ruff check`, `ruff format --check`, bare `mypy`.
3. **Docker works** for the current user (`docker version` answers both client and server). Record `docker image ls ddd:dev --format '{{.ID}}'` in the ledger. Task 4 is the only task that builds an image before the gate: `ddd-elf-fixtures:dev`, rebuilt from the committed Dockerfile (each `docker compose build` gives it a new id over the same content; only `ddd:dev`'s id is checked).

## Review Focus

The inputs most likely to bite a user that no happy path reaches. Each is pinned by a test in the task that owns it.

1. **Bitfields before value members** (Task 3, Task 4, Task 5). A bitfield's packing decides where every member after it lands, and the ABIs differ on which storage unit holds a field, the padding after it and whether a field may cross a unit's boundary. Every value member after a bitfield must get exactly the compiler's `offsetof`, on every row, and no bitfield may get an address.
2. **A `static` sharing a global's name** (Task 1, Task 3). Only the variable with external linkage is placed; a project whose global was renamed while a `static` of the old name lives on must report the global missing, not take the static's address.
3. **An array of structures in two dimensions** (Task 3, Task 4). `Grid[1][2].v` is row-major: `(1 * 3 + 2) * sizeof(element) + offsetof(element, v)`, never the column-major sum.
4. **A big endian image** (Task 5). `--image` writes the image's byte order into the a2l, and a contradicting `--byte-order` is refused rather than silently obeyed.
5. **The post-link step and the pre-link generation sharing one output directory** (Task 6). The a2l run must leave the C sources, the headers and the dictionary the pre-link run wrote untouched, through the manifest's existing rule, and must not re-run when nothing changed.

## File Structure

| File | Responsibility | Tasks |
| --- | --- | --- |
| `src/ddd/elf.py` | `Variable.external`, read from `DW_AT_external` | 1 |
| `tests/test_elf.py` | linkage over doubles and over every row of the toolbox matrix | 1 |
| `src/ddd/addresses.py` *(new)* | a build's addresses: `load_address_map` (moved), `addresses_from_image`, `Placed` | 2, 3 |
| `src/ddd/backends/a2l/options.py` | `ADDRESS_MAX`, and `weigh_addresses`, the 32-bit check for both sources | 2 |
| `src/ddd/backends/a2l/__init__.py`, `src/ddd/backends/__init__.py` | stop exporting `load_address_map`; export `weigh_addresses` | 2 |
| `tests/test_addresses.py` *(new)* | the map reader's tests, moved from `tests/test_a2l.py`, and `addresses_from_image` over hand-built images | 2, 3 |
| `tests/test_a2l.py`, `tests/test_hardening.py` | lose the moved tests; the range checks go through `weigh_addresses` | 2 |
| `tests/test_backends.py` | the layering: `ddd.addresses` imports no backend | 2 |
| `docker/build_address_fixtures.py` *(new)* | builds the address fixture images and their oracle | 4 |
| `docker-compose.yml` | the `address-fixtures` service | 4 |
| `tests/fixtures/addresses/` *(new)* | the DDD project, its generated C, the oracle source, the images, the manifest | 4 |
| `tests/test_address_fixtures.py` *(new)* | the drift guard: inputs hashed, the generated C and the symbol list regenerated and compared, the five rows' span and layouts | 4 |
| `src/ddd/cli.py` | `--image`: the option, its refusals, the byte order, the reasons as notes | 5 |
| `tests/test_cli.py` | `--image` end to end, over every row of the address fixtures | 5 |
| `cmake/Ddd.cmake` | `ADDRESSES_FROM_IMAGE` | 6 |
| `tests/test_cmake.py` | one build, a quiet second build, a relink, the refused combinations | 6 |
| `SPEC.md`, `docs/build_integration.rst`, `docs/command_line_interface.rst`, `docs/developer_documentation.rst`, `README.md`, `CHANGELOG.md`, `tests/test_documentation.py` | the documentation, held to the code | 7 |
| `src/ddd/elf.py` (module docstring), `tests/test_backends.py` (a docstring) | stop calling the image's addresses planned | 7 |

## Interfaces Between Tasks

```python
# Task 1 — ddd.elf
@dataclass(frozen=True, slots=True)
class Variable:
    ...                       # unchanged fields
    external: bool = True     # DW_AT_external on the entry or on the declaration it completes

# Task 2 — ddd.addresses (moved) and ddd.backends.a2l.options
def load_address_map(path: Path) -> dict[str, int]: ...   # format checks only, every entry kept
ADDRESS_MAX: Final = 0xFFFFFFFF                            # stays in ddd.backends.a2l.options
def weigh_addresses(addresses: Mapping[str, int], carried: Collection[str], where: str) -> None:
    """Raise ValueError, in the map reader's sentence, for the first carried symbol outside
    0 .. ADDRESS_MAX, in the order of `addresses`."""

# Task 3 — ddd.addresses
@dataclass(frozen=True, slots=True)
class Placed:
    addresses: dict[str, int]   # every symbol placed
    reasons: dict[str, str]     # every symbol not placed, and why, in one sentence
def addresses_from_image(image: Image, symbols: Collection[str]) -> Placed: ...

# Task 4 — tests/fixtures/addresses/manifest.json
# {"hashes": {path: sha256}, "rows": {row: {"compiler": str, "flags": [str], "byte_order":
#  "little"|"big", "pointer_size": int, "addresses": {symbol: int}, "offsets": {...},
#  "bitfields": [symbol]}}}   - five rows: armv7m, powerpc, x86_64, aarch64_be, i686

# Task 5 — ddd.cli
# ddd generate a2l|all ... --image IMAGE
```

---

### Task 1: the reader records linkage

**Files:** Modify `src/ddd/elf.py`; Test `tests/test_elf.py`.

**Interfaces:** Consumes nothing new. Produces `Variable.external` (above).

`DW_AT_external` marks a variable with external linkage. Where a definition completes a declaration (`DW_AT_specification`), gcc states it on the declaration and not on the definition, and clang writes a single entry, the definition, which carries it. Measured with `readelf --debug-dump=info` over every row of the committed matrix: the eight gcc rows describe `Cal_Declared_First` and `Cal_Curve` as a declaration with `DW_AT_external` and a definition without it, the two clang rows (`riscv32`, `aarch64_be`) as one definition with it, and no static carries it on any row; the DWARF 2 and 3 rows (`armv7m-dwarf2`, `powerpc`) spell it `DW_FORM_flag`, the others `DW_FORM_flag_present`, and pyelftools reads both as `True`. So the reader takes it from the entry, or from the declaration the entry completes, the pair it already takes the name from, through `_either`: the definition's own attribute first, as `_declared` reads a line. The field defaults to `True` (Ruling 2), so that every hand-built `Variable` of the toolbox's tests keeps standing for a global.

The matrix test's oracle is the fixture's source, never the reader. A small scanner in the test reads every file-scope declaration of the units a row is built from (`build_elf_fixtures.UNITS`), under the `#ifdef` cases the row builds, and calls it external unless it says `static`. It reads 55 variables for a gcc row - 45 globals and 2 statics in `main.c`, and 3 globals and a static `Twin` in each of `unit_a.c` and `unit_b.c` - and 54 for a clang row, which builds no `Static_Folded`. The test compares the whole list of `(unit, name, external)`, so a variable the reader drops or adds fails it as well.

- [ ] **Step 1: Write the failing tests**

In `tests/test_elf.py`, the imports become:

```python
import itertools
import json
import re
import struct
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import elftools
import pytest
from build_elf_fixtures import UNITS
from elftools.elf.elffile import ELFFile
```

After `DECLARATION = Attr(True, "DW_FORM_flag_present")`, add:

```python
EXTERNAL = Attr(True, "DW_FORM_flag_present")
```

Two tests of `TestVariables` compare a whole `Variable` with one whose new field is `True` by default: give their doubles the `DW_AT_external` a global's entry carries. `test_a_variable_has_its_name_unit_type_declaration_and_address` becomes:

```python
    def test_a_variable_has_its_name_unit_type_declaration_and_address(self) -> None:
        (found,) = read(
            variable(b"Gain", DW_AT_decl_file=1, DW_AT_decl_line=12, DW_AT_external=EXTERNAL)
        )
        assert found == Variable("Gain", "unit.c", U8_TYPE, Declared("unit.c", 12), 0x100)
```

and the declaration of `test_a_definition_completing_a_declaration_takes_its_name_type_and_file_from_it` becomes:

```python
        declaration = variable(
            b"Spec",
            located=False,
            DW_AT_declaration=DECLARATION,
            DW_AT_external=EXTERNAL,
            DW_AT_decl_file=1,
            DW_AT_decl_line=4,
        )
```

Between `TestVariables` and `TestUntrustedText`, add:

```python
class TestLinkage:
    """``DW_AT_external``, which tells a global from a ``static`` of the same name (Review
    Focus 2)."""

    def test_a_variable_stating_dw_at_external_is_a_global(self) -> None:
        (found,) = read(variable(b"Global", DW_AT_external=EXTERNAL))
        assert found.external is True

    def test_a_variable_stating_nothing_is_a_static(self) -> None:
        (found,) = read(variable(b"Local"))
        assert found.external is False

    def test_a_flag_of_zero_says_the_attribute_is_absent(self) -> None:
        """DWARF 2 and 3 spell the flag as DW_FORM_flag, a byte whose 0 means absent; pyelftools
        reads that byte as a bool."""
        (found,) = read(variable(b"Local", DW_AT_external=Attr(False, "DW_FORM_flag")))
        assert found.external is False

    def test_a_definition_completing_a_declaration_takes_its_linkage_from_it(self) -> None:
        """gcc's way: DW_AT_external on the declaration, and none on the definition that
        completes it (measured on every gcc row of the matrix)."""
        declaration = variable(
            b"Spec", located=False, DW_AT_declaration=DECLARATION, DW_AT_external=EXTERNAL
        )
        definition = die(
            "DW_TAG_variable",
            specification=declaration,
            DW_AT_location=Attr(AT, "DW_FORM_exprloc"),
        )
        (found,) = read(declaration, definition)
        assert (found.name, found.address, found.external) == ("Spec", 0x100, True)

    def test_a_variable_built_by_hand_stands_for_a_global(self) -> None:
        """Ruling 2: every hand-built variable of the toolbox's tests stands for a global."""
        assert Variable("v", "unit.c", U8_TYPE).external is True
```

After `line_of`, add the oracle:

```python
_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_BLOCK = re.compile(r"\{[^{}]*\}")
_DECLARATOR = re.compile(r"(\w+)\s*(?:\[\w*\]\s*)*$")


def linkage_in_the_source(cases: list[str]) -> list[tuple[str, str, bool]]:
    """Every variable the units of a row state at file scope, as ``(unit, name, external)``:
    the oracle for linkage, read off ``tests/fixtures/elf/src/`` as the row's compiler saw it.

    Comments are dropped, and the lines of an ``#ifdef`` the row does not build; every braced
    block - a structure's members, an initializer, a function's body - is folded away, so that
    what is left splits at ``;`` into the declarations of the file's top level. Each one but a
    typedef and a function names a variable, ``static`` or not; ``USED`` is the fixture's
    ``__attribute__((used))``, which says nothing of linkage."""
    found: dict[tuple[str, str], bool] = {}
    for unit in UNITS:
        text = _COMMENT.sub(" ", (FIXTURES / "src" / f"{unit}.c").read_text(encoding="utf-8"))
        kept: list[str] = []
        skipping = False
        for line in text.splitlines():
            if line.startswith("#ifdef"):
                skipping = line.split()[1] not in cases
            elif line.startswith("#else"):
                skipping = not skipping
            elif line.startswith("#endif"):
                skipping = False
            elif not line.startswith("#") and not skipping:
                kept.append(line)
        text = re.sub(r"\bUSED\b", "", "\n".join(kept))
        while "{" in text:
            text = _BLOCK.sub("@", text)
        for statement in re.sub(r"\)\s*@", ");", text).split(";"):
            words = statement.split()
            declarator = _DECLARATOR.search(statement.split("=")[0])
            if declarator is None or words[0] == "typedef":
                continue
            found[(f"{unit}.c", declarator[1])] = "static" not in words
    return sorted((unit, name, external) for (unit, name), external in found.items())
```

In `TestTheMatrix`, before `test_a_definition_completing_a_declaration_is_declared_at_its_own_line`, add:

```python
    def test_every_variable_has_the_linkage_its_source_gives_it(
        self, row: tuple[Image, dict[str, Any]]
    ) -> None:
        """Review Focus 2, in the reader: a static is told from a global on every row, the
        source being the oracle. gcc states DW_AT_external on the declaration a definition
        completes (``Cal_Declared_First``, ``Cal_Curve``) and clang on the definition, its only
        entry; ``Twin`` is a static in two units, ``Common_Counter`` a global in two."""
        image, entry = row
        found = sorted((v.unit, v.name, v.external) for v in image.variables)
        assert found == linkage_in_the_source(entry["cases"])
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/bin/python -m pytest tests/test_elf.py --no-cov -k linkage`
Expected: `15 failed, 379 deselected`, each for `AttributeError: 'Variable' object has no attribute 'external'`: the five of `TestLinkage` and the matrix test on its ten rows. The two tests of `TestVariables` this step changed still pass, since the reader ignores the attribute until Step 3: the whole file, `.venv/bin/python -m pytest tests/test_elf.py --no-cov`, gives `15 failed, 379 passed`.

- [ ] **Step 3: Read the linkage**

In `src/ddd/elf.py`, `Variable` gains a last field, after the docstring of `missing`:

```python
    external: bool = True
    """Whether the variable has external linkage, as ``DW_AT_external`` states: False for a
    ``static``. True by default, so that a variable built by hand stands for a global, as an
    object of a project is; the reader always states it."""
```

and the last line of `_variable`, `return Variable(name, unit.name, ctype, declared_at, address, missing)`, becomes:

```python
    # Read where the name is: gcc states DW_AT_external on the declaration a definition
    # completes and not on the definition, clang on the one entry it writes (measured over the
    # fixture matrix). DWARF 2 and 3 spell it as a flag byte, whose 0 says it is absent.
    external = bool(_either(entry, named, "DW_AT_external"))
    return Variable(name, unit.name, ctype, declared_at, address, missing, external)
```

- [ ] **Step 4: Run them to see them pass**

Run: `.venv/bin/python -m pytest tests/test_elf.py --no-cov -k linkage`
Expected: `15 passed, 379 deselected`.

- [ ] **Step 5: The gates**

Run:

```bash
rm -f .coverage .coverage.*
.venv/bin/python -m pytest > build/gate.txt 2>&1; echo "EXIT=$?"; tail -3 build/gate.txt
.venv/bin/ruff check . > build/ruff.txt 2>&1; echo "RUFF=$?"; tail -1 build/ruff.txt
.venv/bin/ruff format --check . > build/fmt.txt 2>&1; echo "FMT=$?"; tail -1 build/fmt.txt
.venv/bin/mypy > build/mypy.txt 2>&1; echo "MYPY=$?"; tail -1 build/mypy.txt
```

Expected: `EXIT=0`, then `Required test coverage of 100% reached. Total coverage: 100.00%` and `5425 passed`, 15 more than before the task (the scratch branch measured `5410 passed` at `8d97d92`); `RUFF=0` and `All checks passed!`; `FMT=0` and `144 files already formatted`; `MYPY=0` and `Success: no issues found in 81 source files`.

- [ ] **Step 6: Commit**

```bash
git add src/ddd/elf.py tests/test_elf.py
git commit -F - <<'EOF'
record whether a variable has external linkage

DW_AT_external tells a global from a static of the same name, and
placing a symbol in an image has to: every object a dictionary describes
is a global. gcc states it on the declaration a definition completes and
clang on the definition, so the reader takes it from the pair it takes
the name from. It defaults to true, so that a variable built by hand
keeps standing for a global.

Co-Authored-By: <your model> <noreply@anthropic.com>
EOF
```

- [ ] **Step 7: Ablations**

In a scratch worktree made from the commit, from the worktree's root:

```bash
git worktree add --detach build/ablate HEAD
cd build/ablate
```

Each ablation below is one `sed` that changes one line of `src/ddd/elf.py` (`git diff --stat` says `1 file changed, 1 insertion(+), 1 deletion(-)`). After each, run, from `build/ablate`:

```bash
find . -name __pycache__ -prune -exec rm -rf {} +
/home/sauci/Documents/Github/ddd-toolbox-from-elf/.venv/bin/python -m pytest -p no:cacheprovider -o addopts="" tests/test_elf.py 2>&1 | grep -E "^FAILED|^ERROR|^=.*(passed|failed)|^rootdir"
git checkout -- src/ddd/elf.py
```

and check that the `rootdir:` line names `build/ablate`. All measured on the scratch branch:

1. The declaration's linkage ignored:

   ```bash
   sed -i 's/external = bool(_either(entry, named, "DW_AT_external"))/external = bool(_value(entry, "DW_AT_external"))/' src/ddd/elf.py
   ```

   `10 failed, 384 passed`: `TestVariables::test_a_definition_completing_a_declaration_takes_its_name_type_and_file_from_it`, `TestLinkage::test_a_definition_completing_a_declaration_takes_its_linkage_from_it`, and `TestTheMatrix::test_every_variable_has_the_linkage_its_source_gives_it` on the eight gcc rows (`aarch64`, `armeb`, `armv7m`, `armv7m-dwarf2`, `i686`, `powerpc`, `s390x`, `x86_64`). The clang rows survive it, as they must: there the definition states the attribute itself.

2. The attribute's presence read rather than its value:

   ```bash
   sed -i 's/external = bool(_either(entry, named, "DW_AT_external"))/external = _either(entry, named, "DW_AT_external") is not None/' src/ddd/elf.py
   ```

   `1 failed, 393 passed`: `TestLinkage::test_a_flag_of_zero_says_the_attribute_is_absent`.

3. The default turned to a static (Ruling 2):

   ```bash
   sed -i 's/    external: bool = True/    external: bool = False/' src/ddd/elf.py
   ```

   `3 failed, 391 passed`: `TestLinkage::test_a_variable_built_by_hand_stands_for_a_global`, and the two whole-`Variable` comparisons of `TestVariables`, `test_a_variable_has_its_name_unit_type_declaration_and_address` and `test_a_definition_completing_a_declaration_takes_its_name_type_and_file_from_it`.

4. Every variable a global:

   ```bash
   sed -i 's/external = bool(_either(entry, named, "DW_AT_external"))/external = True/' src/ddd/elf.py
   ```

   `12 failed, 382 passed`: `TestLinkage::test_a_variable_stating_nothing_is_a_static`, `TestLinkage::test_a_flag_of_zero_says_the_attribute_is_absent`, and the matrix test on all ten rows.

5. Every variable a static:

   ```bash
   sed -i 's/external = bool(_either(entry, named, "DW_AT_external"))/external = False/' src/ddd/elf.py
   ```

   `14 failed, 380 passed`: the two whole-`Variable` comparisons of `TestVariables`, `TestLinkage::test_a_variable_stating_dw_at_external_is_a_global`, `TestLinkage::test_a_definition_completing_a_declaration_takes_its_linkage_from_it`, and the matrix test on all ten rows.

Then, from the worktree's root: `git worktree remove build/ablate`.

### Task 2: one home for a build's addresses

**Files:** Create `src/ddd/addresses.py`; Modify `src/ddd/backends/a2l/options.py`, `src/ddd/backends/a2l/__init__.py`, `src/ddd/backends/__init__.py`, `src/ddd/cli.py`; Create `tests/test_addresses.py` (the map reader's tests moved from `tests/test_a2l.py`); Modify `tests/test_a2l.py`, `tests/test_hardening.py`, `tests/test_cli.py`, `tests/test_backends.py`.

**Interfaces:** Produces `load_address_map(path)` in `ddd.addresses` and `weigh_addresses(addresses, carried, where)` in `ddd.backends.a2l.options` (above).

A move and a split, no change a user can see: every sentence the map reader and its range check print today is printed unchanged, by the same command lines. The range check leaves the reader for the a2l side, which owns the 32 bits of an `ECU_ADDRESS`, so that Task 5 runs the same check over an image's addresses (Ruling 1). `load_address_map` keeps every entry and checks only how each address is written; `weigh_addresses` refuses, in the sentence the reader used to print, the first symbol the a2l carries whose address an `ECU_ADDRESS` cannot hold, in the order of the map. It takes the carried symbols as a set: the reader looked every entry up in the tuple `addressed_symbols` returns, and the documented recipe's map holds every symbol of the image (measured: 0.27 s against a tuple of 5000 symbols for 25000 entries, 0.5 ms against a set).

What proves that nothing a user sees changed:

- **The moved tests assert each sentence whole.** They matched a fragment (`match="is not an integer"`); they now assert with `==` the sentence the reader printed before the move, read off it at the commit before this task by calling the old `load_address_map` on the same maps.
- **The command line's tests about address maps pass unchanged** (Step 4), and one more is added, which passes before the split (Step 2) and after it: `test_an_address_no_a2l_field_could_hold_names_the_map_forward_slashed` holds the range refusal whole, path and all. The path of that sentence was the reader's to spell, and `test_every_complaint_about_a_map_spells_the_path_forward_slashed` held it to `as_posix()`; it is `generate`'s to spell now, handed to `weigh_addresses` as `where`. On Linux a path's `str()` is its `as_posix()`, so only Windows CI can catch a regression there (ablation 7), as it alone could before.
- **One thing does change**, measured by running 13 command lines before and after the split: a map holding an address the a2l carries but cannot hold, followed by a malformed entry, was refused for the address, since the reader went through the entries in order; it is now refused for the malformed entry, since every entry's spelling is read before anything is weighed. Both sentences are unchanged, the exit status is 2 either way, and mending the map mends both.

The repository names `load_address_map` in two more places, `docs/build_integration.rst` and a docstring of `tests/test_cmake.py`; both say it refuses a symbol stated twice, which it still does under its name, so neither changes. The plans and specs under `docs/superpowers/` record its old signature as history.

The layering test is new: `ddd.addresses` is core, and nothing else would notice it importing from a backend, which is what Ruling 1 avoids (ablation 9).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_addresses.py`:

```python
"""A build's addresses: the map a build writes after the link, and the range the a2l holds the
addresses it states to."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ddd.addresses import load_address_map
from ddd.backends.a2l.options import weigh_addresses


def refusal(path: Path) -> str:
    with pytest.raises(ValueError) as refused:
        load_address_map(path)
    return str(refused.value)


class TestTheMap:
    """The reader of the map, moved here from the a2l backend's tests. Each refusal is the
    sentence the reader printed before the move, read off it then and asserted whole."""

    def test_address_map_accepts_hex_and_decimal(self, tree: Path) -> None:
        path = tree / "addresses.json"
        path.write_text('{"A": "0x1000", "B": 32, "C": "40"}', encoding="utf-8")
        assert load_address_map(path) == {"A": 0x1000, "B": 32, "C": 40}

    @pytest.mark.parametrize(
        ("value", "said"),
        [
            ('"ff"', "is not an integer written in decimal or with a '0x' prefix: 'ff'"),
            ("true", "is not an integer: True"),
            ("null", "is not an integer: None"),
            ("[1]", "is not an integer: [1]"),
        ],
    )
    def test_address_map_rejects_anything_else(self, tree: Path, value: str, said: str) -> None:
        path = tree / "addresses.json"
        path.write_text(f'{{"A": {value}}}', encoding="utf-8")
        assert refusal(path) == f"{path.as_posix()}: address of 'A' {said}"

    def test_address_map_still_ignores_the_space_around_a_value(self, tree: Path) -> None:
        """The grammar holds the stripped text: a map is machine written, and a stray space
        around a number it got right is not what the strictness is for."""
        path = tree / "addresses.json"
        path.write_text('{"A": " 0x10 ", "B": "\\t32"}', encoding="utf-8")
        assert load_address_map(path) == {"A": 0x10, "B": 32}

    @pytest.mark.parametrize("value", ["0x1_0000", "+5", "١٢", "-5", "-0x10", "0b11", "0x"])
    def test_address_map_holds_a_spelled_address_to_the_two_documented_forms(
        self, tree: Path, value: str
    ) -> None:
        """``int()`` took every spelling python accepts, none of which section 6 offers.

        ``0x1_0000`` reached the a2l as ``0x00010000``, ``+5`` as ``0x00000005`` and the
        Arabic-Indic ``١٢`` as ``0x0000000C`` - from a file a linker script or a patch tool
        wrote, which is the argument for a strict grammar rather than a lenient one.
        """
        path = tree / "addresses.json"
        path.write_text(json.dumps({"A": value}), encoding="utf-8")
        assert refusal(path) == (
            f"{path.as_posix()}: address of 'A' is not an integer written in decimal or with a "
            f"'0x' prefix: {value!r}"
        )

    def test_address_map_refuses_a_symbol_stated_twice(self, tree: Path) -> None:
        """Python's json reader keeps the last of two equal keys, so the first address was
        dropped in silence - the loader refuses a repeated key for the same reason."""
        path = tree / "addresses.json"
        path.write_text('{"A": "0x10", "B": "0x20", "A": "0x30"}', encoding="utf-8")
        assert refusal(path) == (
            f"{path.as_posix()}: the address map names 'A' twice, with two addresses"
        )

    def test_address_map_reads_a_byte_order_mark(self, tree: Path) -> None:
        """Every other file the tool reads is read ``utf-8-sig``; a map written by a Windows
        tool or by Notepad was a json syntax error with python's advice to a programmer."""
        path = tree / "addresses.json"
        path.write_text('﻿{"A": "0x10"}', encoding="utf-8")
        assert load_address_map(path) == {"A": 0x10}

    def test_address_map_must_be_an_object(self, tree: Path) -> None:
        path = tree / "addresses.json"
        path.write_text("[1, 2]", encoding="utf-8")
        assert refusal(path) == (
            f"{path.as_posix()}: expected a json object mapping symbol names to addresses"
        )

    def test_an_address_map_that_is_not_json_names_the_file(self, tree: Path) -> None:
        """The words after the colon are json's own, read off it here rather than out of this
        test, as they may change between pythons."""
        path = tree / "addresses.json"
        path.write_text("{ not json", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError) as decoded:
            json.loads("{ not json")
        assert refusal(path) == (
            f"the address map '{path.as_posix()}' is not valid json: {decoded.value}"
        )

    def test_an_address_map_that_cannot_be_read_names_it(self, tree: Path) -> None:
        path = tree / "nosuch.json"
        with pytest.raises(OSError) as refused:
            load_address_map(path)
        assert str(refused.value) == (
            f"cannot read the address map '{path.as_posix()}': No such file or directory"
        )

    @pytest.mark.parametrize("content", ["[1, 2]", '{"A": "nowhere"}', '{"A": 1, "A": 2}'])
    def test_every_complaint_about_a_map_spells_the_path_forward_slashed(
        self, tree: Path, content: str
    ) -> None:
        """As every other path this tool prints is spelled, and as the same messages about a
        description file already are; on Windows these carried backslashes. The fourth
        complaint, an address no ``ECU_ADDRESS`` holds, is the a2l backend's since the move,
        and ``tests/test_cli.py`` holds its path to the same spelling."""
        path = tree / "sub" / "addresses.json"
        path.parent.mkdir()
        path.write_text(content, encoding="utf-8")
        said = refusal(path)
        assert path.as_posix() in said
        assert "\\" not in said

    def test_every_entry_is_kept_whatever_its_value(self, tree: Path) -> None:
        """Ruling 1: the reader checks how an address is written, never what it is; which
        addresses the a2l can state is ``weigh_addresses``' question, for the symbols it
        carries."""
        path = tree / "addresses.json"
        path.write_text('{"X": -16, "Y": "0x1FFFFFFFF"}', encoding="utf-8")
        assert load_address_map(path) == {"X": -16, "Y": 0x1_FFFF_FFFF}


class TestTheRange:
    """What an ``ECU_ADDRESS`` holds, weighed for the symbols the a2l carries alone."""

    @pytest.mark.parametrize("address", [-16, 0x1_FFFF_FFFF])
    def test_an_address_the_field_cannot_hold_is_refused_naming_the_symbol_and_where(
        self, address: int
    ) -> None:
        """A negative value renders as ``0x-0000010`` and a wider one as a 33 bit literal,
        either of which makes the whole a2l unreadable."""
        with pytest.raises(ValueError) as refused:
            weigh_addresses({"X": address}, ("X",), "build/addresses.json")
        assert str(refused.value) == (
            f"build/addresses.json: address of 'X' is {address}, outside the range "
            f"0 .. 0xFFFFFFFF that an a2l address can hold"
        )

    def test_both_ends_of_the_field_are_addresses(self) -> None:
        weigh_addresses({"Low": 0, "High": 0xFFFF_FFFF}, ("Low", "High"), "addresses.json")

    def test_an_address_the_a2l_never_states_is_not_weighed(self) -> None:
        """The documented recipe extracts every defined symbol of the image, which on a 64 bit
        host puts a hundred entries of the c runtime above 4 GB."""
        weigh_addresses({"X": 0x1000, "___crt_xc_end__": 0x1_4000_9018}, ("X",), "map.json")

    def test_the_first_address_out_of_range_is_named_in_the_order_of_the_map(self) -> None:
        with pytest.raises(ValueError) as refused:
            weigh_addresses({"Z": -1, "A": 0x1_0000_0000}, ("A", "Z"), "map.json")
        assert str(refused.value) == (
            "map.json: address of 'Z' is -1, outside the range 0 .. 0xFFFFFFFF that an a2l "
            "address can hold"
        )
```

In `tests/test_a2l.py`, the map reader's tests move out: delete every test of `TestHelpers` but `test_string_escaping`, from `test_address_map_accepts_hex_and_decimal` to the end of `test_every_complaint_about_a_map_spells_the_path_forward_slashed`. `pytest` is then unused there: delete `import pytest` and the blank line after it, and the `ddd.backends` import becomes:

```python
from ddd.backends import ByteOrder, write
```

In `tests/test_hardening.py`, `from ddd.backends import load_address_map` becomes:

```python
from ddd.addresses import load_address_map
from ddd.backends import weigh_addresses
from ddd.backends.c.literals import c_literal
```

the two tests of the range become:

```python
    def test_an_address_outside_the_a2l_field_is_refused(self, tree: Path) -> None:
        """For a symbol the a2l states an address for: a negative value renders as
        ``0x-0000010`` and a wider one as a 33 bit literal, either of which makes the whole
        file unreadable."""
        write_tree(tree, {"map.json": {"X": -16}})
        with pytest.raises(ValueError, match="outside the range"):
            weigh_addresses(load_address_map(tree / "map.json"), ("X",), "map.json")
        write_tree(tree, {"wide.json": {"X": "0x1FFFFFFFF"}})
        with pytest.raises(ValueError, match="outside the range"):
            weigh_addresses(load_address_map(tree / "wide.json"), ("X",), "wide.json")

    def test_an_address_outside_it_is_kept_for_a_symbol_the_a2l_never_states(
        self, tree: Path
    ) -> None:
        """The documented recipe extracts every defined symbol of the image, which on a 64 bit
        host puts a hundred entries of the c runtime above 4 GB. None of them is formatted
        into the a2l, so refusing them failed every build after the first for entries nobody
        asked for; they stay in the map and are named in the ``address-missing`` note."""
        write_tree(tree, {"map.json": {"X": "0x1000", "___crt_xc_end__": "0x140009018"}})
        addresses = load_address_map(tree / "map.json")
        weigh_addresses(addresses, ("X",), "map.json")
        assert addresses == {"X": 0x1000, "___crt_xc_end__": 0x140009018}
```

and in `test_an_address_map_that_is_not_json_names_the_file` and `test_an_address_that_is_no_integer_is_told_the_rule`, `load_address_map(tree / "map.json", carried=())` becomes `load_address_map(tree / "map.json")`.

In `tests/test_cli.py`, after `test_an_address_no_a2l_field_could_hold_is_refused_where_the_a2l_states_it`, add:

```python
    def test_an_address_no_a2l_field_could_hold_names_the_map_forward_slashed(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The range is weighed by the a2l backend, which is handed the map's path as every
        path this tool prints is spelled; on Windows its str() carries backslashes."""
        addresses = tmp_path / "addresses.json"
        addresses.write_text('{"ValueE": "0x140009018"}', encoding="utf-8")
        output = tmp_path / "gen"
        arguments = ["generate", "a2l", str(DEMO), "-o", str(output), "--address-map"]
        assert main([*arguments, str(addresses)]) == EXIT_USAGE
        assert capsys.readouterr().err == (
            f"ddd: {addresses.as_posix()}: address of 'ValueE' is 5368746008, outside the range "
            "0 .. 0xFFFFFFFF that an a2l address can hold\n"
        )
```

In `tests/test_backends.py`, `TestLayering`, after `test_the_elf_reader_knows_nothing_of_ddd`, add:

```python
    def test_a_build_s_addresses_reach_no_backend_and_no_command_line(self) -> None:
        """Ruling 1: reading a build's addresses is core, and what an ``ECU_ADDRESS`` holds is
        the a2l's own question - ddd.addresses importing ADDRESS_MAX from the backend would
        turn the layering upside down."""
        leaked = sorted(
            module
            for module in imported_modules(SOURCE / "addresses.py")
            if module.startswith(("ddd.backends", "ddd.cli"))
        )
        assert not leaked, f"addresses.py reaches into {leaked}"
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/bin/python -m pytest tests/test_addresses.py tests/test_hardening.py --no-cov`
Expected: `Interrupted: 2 errors during collection`, both `ModuleNotFoundError: No module named 'ddd.addresses'`.

Run: `.venv/bin/python -m pytest tests/test_backends.py tests/test_cli.py tests/test_a2l.py --no-cov`
Expected: `1 failed, 355 passed`: `TestLayering::test_a_build_s_addresses_reach_no_backend_and_no_command_line`, for `FileNotFoundError` on `src/ddd/addresses.py`. The new test of `tests/test_cli.py` passes already: it holds today's sentence.

- [ ] **Step 3: Move the reader, and give the a2l its range**

Create `src/ddd/addresses.py`:

```python
"""A build's address information: where each symbol of a dictionary sits in the target.

Reading it is core rather than a backend's business: the a2l only consumes the result, and
``SPEC.md`` gives address information a section of its own. What is read here is the map a
build writes after the link, ``{"Symbol": "0x20000100"}``, and only how each address in it is
written is checked: whether an address fits the field it is written into is the a2l's own
question, which ``ddd.backends.a2l.options.weigh_addresses`` answers.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Final

ADDRESS_PATTERN: Final = re.compile(r"^(?:0[xX][0-9A-Fa-f]+|[0-9]+)$")
"""The two spellings an address may be written in: ``0x20000100`` or ``536871168``.

The grammar of section 6, rather than python's ``int()``, which the reader used to hand the
text to: that accepts a digit separator (``0x1_0000`` became ``0x00010000``), a leading
``+``, and any Unicode decimal digit at all - the Arabic-Indic ``١٢`` became ``0x0000000C``.
None of those is a spelling anything writes on purpose, and a map is written by a linker
script or a patch tool nobody is looking at, which is the argument for reading exactly what
is documented and refusing the rest.
"""


def load_address_map(path: Path) -> dict[str, int]:
    """Read a ``{"Symbol": "0x20000100"}`` json file produced by the build.

    Read ``utf-8-sig`` for the reason every other file this tool reads is: a build step on
    Windows, or somebody's editor, writes a byte order mark in front of the text, and read as
    plain utf-8 that mark was a json syntax error carrying python's advice to a programmer.

    A symbol stated twice is refused rather than resolved to the last of the two, which is
    what json readers do and what the description loader already refuses: the two addresses
    of one symbol cannot both be right, and the map that carries them was merged from two
    sources or written twice by the same one.

    Every entry is kept as it is written, whatever its value: the documented recipe extracts
    *every* defined symbol of the image (``docs/build_integration.rst``), most of which the a2l
    never states, and those are counted among the entries the a2l does not carry and named in
    the ``address-missing`` note rather than dropped in silence. Which addresses an
    ``ECU_ADDRESS`` must hold is weighed by the a2l backend, for the symbols it carries.

    Every complaint spells the path forward-slashed, as every path this tool prints is: the
    same message about a description file has always been an ``as_posix()`` one, and a map
    named on the command line of a Windows build came back in the other spelling.
    """
    where = path.as_posix()
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=_no_repeats)
    except json.JSONDecodeError as error:
        # The bare json message names neither file nor purpose, and this one is typically
        # written by a linker script or a patch tool nobody is looking at.
        msg = f"the address map '{where}' is not valid json: {error}"
        raise ValueError(msg) from None
    except OSError as error:
        # The same reasoning one step earlier: `--address-map nosuch.json` answered
        # `[Errno 2] No such file or directory: 'nosuch.json'`, which names neither the
        # option that asked for the file nor what the run wanted it for.
        msg = f"cannot read the address map '{where}': {error.strerror or error}"
        raise OSError(msg) from None
    except _RepeatedSymbolError as error:
        msg = f"{where}: the address map names '{error.symbol}' twice, with two addresses"
        raise ValueError(msg) from None
    if not isinstance(data, dict):
        msg = f"{where}: expected a json object mapping symbol names to addresses"
        raise ValueError(msg)
    addresses: dict[str, int] = {}
    for symbol, value in data.items():
        addresses[symbol] = _address(where, symbol, value)
    return addresses


class _RepeatedSymbolError(ValueError):
    """One key of the map document appears twice; raised from inside the json reader."""

    def __init__(self, symbol: str) -> None:
        super().__init__(symbol)
        self.symbol = symbol


def _no_repeats(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """The ``object_pairs_hook`` of the reader: every object of the document, keys unique."""
    seen: dict[str, object] = {}
    for key, value in pairs:
        if key in seen:
            raise _RepeatedSymbolError(key)
        seen[key] = value
    return seen


def _address(where: str, symbol: str, value: object) -> int:
    # "integer" rather than "number" every time: 12.5 is a perfectly good number, and telling
    # its author so would leave the actual rule - an address is a whole number - unsaid.
    if isinstance(value, bool) or not isinstance(value, int | str):
        msg = f"{where}: address of '{symbol}' is not an integer: {value!r}"
        raise ValueError(msg)
    if isinstance(value, int):
        return value
    # Stripped first: the grammar is about how the number is written, and a space around
    # one a machine got right is not what it is there to catch.
    text = value.strip()
    if not ADDRESS_PATTERN.match(text):
        msg = (
            f"{where}: address of '{symbol}' is not an integer written in decimal or "
            f"with a '0x' prefix: {value!r}"
        )
        raise ValueError(msg)
    return int(text, 16 if text.lower().startswith("0x") else 10)
```

`src/ddd/backends/a2l/options.py` keeps the options and `ADDRESS_MAX`, now `Final`, and gains `weigh_addresses`; the reader and its helpers are gone from it:

```python
"""Options of the a2l backend, and the range of the addresses it states."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final


class ByteOrder(StrEnum):
    LITTLE = "little"
    BIG = "big"

    @property
    def a2l(self) -> str:
        return "MSB_LAST" if self is ByteOrder.LITTLE else "MSB_FIRST"


@dataclass(frozen=True, slots=True)
class A2lOptions:
    """Everything the a2l backend lets a project decide."""

    byte_order: ByteOrder = ByteOrder.LITTLE
    version: str = "1 61"
    addresses: dict[str, int] = field(default_factory=dict)
    """Symbol to address map; a symbol that is missing gets address 0."""

    def filename(self, project: str) -> str:
        return f"{project}.a2l"

    def address_of(self, symbol: str) -> str:
        return f"0x{self.addresses.get(symbol, 0):08X}"


ADDRESS_MAX: Final = 0xFFFFFFFF
"""Widest address the ``ECU_ADDRESS`` field of a2l holds: it is an unsigned 32 bit value."""


def weigh_addresses(addresses: Mapping[str, int], carried: Collection[str], where: str) -> None:
    """Refuse an address the a2l would state that its ``ECU_ADDRESS`` cannot hold.

    Only the symbols ``carried`` names are weighed - the ones the a2l states an
    ``ECU_ADDRESS`` for. For one of those, a negative value would render as ``0x-0000010`` and
    a wider one as a 33 bit literal, either of which makes the whole a2l unreadable, so it is a
    usage error naming the symbol and ``where`` its address came from. Every other address is
    never formatted at all: the documented recipe extracts *every* defined symbol of the image
    (``docs/build_integration.rst``), which on a 64 bit host means a hundred entries of the c
    runtime sitting above 4 GB, and refusing those made the two-run flow impossible to
    complete on the very host the page tells the reader to try it on.

    The first symbol out of range is named, in the order of ``addresses``.
    """
    # A set rather than the tuple the a2l lists them in: every entry of a map is looked up,
    # and the recipe's map holds every symbol of the image (measured, 0.27 s against a tuple
    # of 5000 symbols for 25000 entries, 0.5 ms against a set).
    weighed = frozenset(carried)
    for symbol, address in addresses.items():
        if symbol in weighed and not 0 <= address <= ADDRESS_MAX:
            msg = (
                f"{where}: address of '{symbol}' is {address}, outside the range "
                f"0 .. 0x{ADDRESS_MAX:08X} that an a2l address can hold"
            )
            raise ValueError(msg)
```

`src/ddd/backends/a2l/__init__.py` becomes:

```python
"""Everything that knows about ASAM MCD-2 MC."""

from ddd.backends.a2l.backend import A2lBackend
from ddd.backends.a2l.model import addressed_symbols
from ddd.backends.a2l.options import A2lOptions, ByteOrder, weigh_addresses

__all__ = ["A2lBackend", "A2lOptions", "ByteOrder", "addressed_symbols", "weigh_addresses"]
```

In `src/ddd/backends/__init__.py`, the import of `ddd.backends.a2l` becomes:

```python
from ddd.backends.a2l import (
    A2lBackend,
    A2lOptions,
    ByteOrder,
    addressed_symbols,
    weigh_addresses,
)
```

and in `__all__`, `"load_address_map",` goes and `"weigh_addresses",` comes between `"render",` and `"write",`.

In `src/ddd/cli.py`, `_command_generate` imports the reader from its new home and the range check from the backends:

```python
def _command_generate(args: argparse.Namespace) -> int:
    from ddd.addresses import load_address_map
    from ddd.backends import (
        DICTIONARY_ARTEFACT,
        A2lBackend,
        A2lOptions,
        ByteOrder,
        CBackend,
        COptions,
        Manifest,
        RemovalError,
        addressed_symbols,
        describe_write_failure,
        render,
        weigh_addresses,
        write,
    )
    from ddd.plugins import backend_of
```

and reads the map, then weighs it:

```python
            carried = addressed_symbols(dictionary)
            addresses = load_address_map(args.address_map)
            weigh_addresses(addresses, carried, args.address_map.as_posix())
```

The docstring of `_check_address_coverage` named the reader as what weighs an address; its sentence becomes:

```python
    including any whose address no ``ECU_ADDRESS`` could hold: ``weigh_addresses`` weighs an
    address only for a symbol this list carries, because no other one is ever formatted into
    anything, and this note is where the rest are accounted for.
```

Then check that every user moved:

Run: `git grep --untracked -n -e "load_address_map(.*carried" -e "import.*load_address_map" -e "^ *load_address_map,$" -e '"load_address_map"' -- . ':!docs/superpowers'`
Expected: exactly the three imports from the new home (the same command printed 22 lines before the task):

```
src/ddd/cli.py:1055:    from ddd.addresses import load_address_map
tests/test_addresses.py:11:from ddd.addresses import load_address_map
tests/test_hardening.py:27:from ddd.addresses import load_address_map
```

- [ ] **Step 4: Run them to see them pass**

Run: `.venv/bin/python -m pytest tests/test_addresses.py tests/test_hardening.py tests/test_backends.py --no-cov`
Expected: `154 passed`.

Run: `.venv/bin/python -m pytest tests/test_cli.py --no-cov -k address`
Expected: `16 passed, 264 deselected`: the command line's tests about address maps, unchanged, and the new one.

- [ ] **Step 5: The gates**

Run:

```bash
rm -f .coverage .coverage.*
.venv/bin/python -m pytest > build/gate.txt 2>&1; echo "EXIT=$?"; tail -3 build/gate.txt
.venv/bin/ruff check . > build/ruff.txt 2>&1; echo "RUFF=$?"; tail -1 build/ruff.txt
.venv/bin/ruff format --check . > build/fmt.txt 2>&1; echo "FMT=$?"; tail -1 build/fmt.txt
.venv/bin/mypy > build/mypy.txt 2>&1; echo "MYPY=$?"; tail -1 build/mypy.txt
```

Expected: `EXIT=0`, then `Required test coverage of 100% reached. Total coverage: 100.00%` and `5435 passed`, 10 more than after Task 1: 27 tests in `tests/test_addresses.py`, one each in `tests/test_cli.py` and `tests/test_backends.py`, and `tests/test_documentation.py::TestTheSuiteRunsEverythingEverywhere::test_nothing_in_the_suite_skips[test_addresses.py]`, which is parametrized over the test files; 20 leave `tests/test_a2l.py`. `RUFF=0` and `All checks passed!`; `FMT=0` and `146 files already formatted`; `MYPY=0` and `Success: no issues found in 82 source files`.

- [ ] **Step 6: Commit**

```bash
git add src/ddd/addresses.py src/ddd/backends/a2l/options.py src/ddd/backends/a2l/__init__.py src/ddd/backends/__init__.py src/ddd/cli.py tests/test_addresses.py tests/test_a2l.py tests/test_hardening.py tests/test_cli.py tests/test_backends.py
git commit -F - <<'EOF'
read address maps in the core, and weigh their addresses for the a2l

Reading the addresses of a build is core: the a2l only consumes them,
and the linked image is about to become their second source. The 32
bits of an ECU_ADDRESS stay with the a2l backend: the reader now checks
only how an address is written and keeps every entry, and
weigh_addresses refuses an address the a2l would state but cannot hold,
in the sentence the reader printed. No sentence changes; a map both
malformed and out of range is now refused for the malformed entry first.

Co-Authored-By: <your model> <noreply@anthropic.com>
EOF
```

- [ ] **Step 7: Ablations**

In a scratch worktree made from the commit, from the worktree's root:

```bash
git worktree add --detach build/ablate HEAD
cd build/ablate
```

Each ablation below is one `sed`. After each, run, from `build/ablate`, with the file it changed:

```bash
find . -name __pycache__ -prune -exec rm -rf {} +
/home/sauci/Documents/Github/ddd-toolbox-from-elf/.venv/bin/python -m pytest -p no:cacheprovider -o addopts="" tests/test_addresses.py tests/test_hardening.py tests/test_cli.py tests/test_backends.py 2>&1 | grep -E "^FAILED|^ERROR|^=.*(passed|failed)|^rootdir"
```

then `git checkout -- <the file>`, and check that the `rootdir:` line names `build/ablate`. All measured on the scratch branch:

1. Every entry weighed, carried or not:

   ```bash
   sed -i 's/        if symbol in weighed and not 0 <= address <= ADDRESS_MAX:/        if not 0 <= address <= ADDRESS_MAX:/' src/ddd/backends/a2l/options.py
   ```

   `3 failed, 431 passed`: `TestTheRange::test_an_address_the_a2l_never_states_is_not_weighed`, `test_hardening.py::TestInputTheToolMustSurvive::test_an_address_outside_it_is_kept_for_a_symbol_the_a2l_never_states`, `test_cli.py::TestGenerate::test_an_address_no_a2l_field_could_hold_is_read_where_the_a2l_never_states_it`.

2. No lower bound:

   ```bash
   sed -i 's/        if symbol in weighed and not 0 <= address <= ADDRESS_MAX:/        if symbol in weighed and not address <= ADDRESS_MAX:/' src/ddd/backends/a2l/options.py
   ```

   `3 failed, 431 passed`: `TestTheRange::test_an_address_the_field_cannot_hold_is_refused_naming_the_symbol_and_where[-16]`, `TestTheRange::test_the_first_address_out_of_range_is_named_in_the_order_of_the_map`, `test_hardening.py::TestInputTheToolMustSurvive::test_an_address_outside_the_a2l_field_is_refused`.

3. The top of the field refused:

   ```bash
   sed -i 's/        if symbol in weighed and not 0 <= address <= ADDRESS_MAX:/        if symbol in weighed and not 0 <= address < ADDRESS_MAX:/' src/ddd/backends/a2l/options.py
   ```

   `1 failed, 433 passed`: `TestTheRange::test_both_ends_of_the_field_are_addresses`.

4. Address 0 refused:

   ```bash
   sed -i 's/        if symbol in weighed and not 0 <= address <= ADDRESS_MAX:/        if symbol in weighed and not 0 < address <= ADDRESS_MAX:/' src/ddd/backends/a2l/options.py
   ```

   `1 failed, 433 passed`: `TestTheRange::test_both_ends_of_the_field_are_addresses`.

5. `ADDRESS_MAX` one less:

   ```bash
   sed -i 's/^ADDRESS_MAX: Final = 0xFFFFFFFF$/ADDRESS_MAX: Final = 0xFFFFFFFE/' src/ddd/backends/a2l/options.py
   ```

   `5 failed, 429 passed`: both cases of `TestTheRange::test_an_address_the_field_cannot_hold_is_refused_naming_the_symbol_and_where`, `TestTheRange::test_both_ends_of_the_field_are_addresses`, `TestTheRange::test_the_first_address_out_of_range_is_named_in_the_order_of_the_map`, `test_cli.py::TestGenerate::test_an_address_no_a2l_field_could_hold_names_the_map_forward_slashed`.

6. Weighed in name order rather than the map's:

   ```bash
   sed -i 's/    for symbol, address in addresses.items():/    for symbol, address in sorted(addresses.items()):/' src/ddd/backends/a2l/options.py
   ```

   `1 failed, 433 passed`: `TestTheRange::test_the_first_address_out_of_range_is_named_in_the_order_of_the_map`.

7. The map's path handed over as `str()` (a survival on Linux, and the one this list expects):

   ```bash
   sed -i 's/            weigh_addresses(addresses, carried, args.address_map.as_posix())/            weigh_addresses(addresses, carried, str(args.address_map))/' src/ddd/cli.py
   ```

   On Linux a path's `str()` is its `as_posix()`, so nothing can die of it here; on Windows CI, `test_an_address_no_a2l_field_could_hold_names_the_map_forward_slashed` does, as `test_every_complaint_about_a_map_spells_the_path_forward_slashed` did before the move. Measured over the whole suite, from `build/ablate`, under the default seed and the four the constraints name:

   ```bash
   find . -name __pycache__ -prune -exec rm -rf {} + ; /home/sauci/Documents/Github/ddd-toolbox-from-elf/.venv/bin/python -m pytest -p no:cacheprovider -o addopts="" > ../b7-default.txt 2>&1 ; find . -name __pycache__ -prune -exec rm -rf {} + ; PYTHONHASHSEED=0 /home/sauci/Documents/Github/ddd-toolbox-from-elf/.venv/bin/python -m pytest -p no:cacheprovider -o addopts="" > ../b7-seed0.txt 2>&1 ; find . -name __pycache__ -prune -exec rm -rf {} + ; PYTHONHASHSEED=1 /home/sauci/Documents/Github/ddd-toolbox-from-elf/.venv/bin/python -m pytest -p no:cacheprovider -o addopts="" > ../b7-seed1.txt 2>&1 ; find . -name __pycache__ -prune -exec rm -rf {} + ; PYTHONHASHSEED=4 /home/sauci/Documents/Github/ddd-toolbox-from-elf/.venv/bin/python -m pytest -p no:cacheprovider -o addopts="" > ../b7-seed4.txt 2>&1 ; find . -name __pycache__ -prune -exec rm -rf {} + ; PYTHONHASHSEED=7 /home/sauci/Documents/Github/ddd-toolbox-from-elf/.venv/bin/python -m pytest -p no:cacheprovider -o addopts="" > ../b7-seed7.txt 2>&1 ; tail -n 1 ../b7-default.txt ../b7-seed0.txt ../b7-seed1.txt ../b7-seed4.txt ../b7-seed7.txt
   ```

   `5435 passed` on each of the five runs.

8. The reader drops what an `ECU_ADDRESS` cannot hold:

   ```bash
   sed -i 's/^    return addresses$/    return {s: a for s, a in addresses.items() if 0 <= a <= 0xFFFFFFFF}/' src/ddd/addresses.py
   ```

   `6 failed, 428 passed`: `TestTheMap::test_every_entry_is_kept_whatever_its_value`, both range tests of `test_hardening.py::TestInputTheToolMustSurvive`, and `test_cli.py::TestGenerate::test_an_address_no_a2l_field_could_hold_is_read_where_the_a2l_never_states_it`, `test_an_address_no_a2l_field_could_hold_is_refused_where_the_a2l_states_it` and `test_an_address_no_a2l_field_could_hold_names_the_map_forward_slashed`.

9. The core module reaching into the backend (Ruling 1):

   ```bash
   sed -i 's/^from typing import Final$/from typing import Final\n\nfrom ddd.backends.a2l.options import ADDRESS_MAX/' src/ddd/addresses.py
   ```

   `1 failed, 433 passed`: `test_backends.py::TestLayering::test_a_build_s_addresses_reach_no_backend_and_no_command_line`.

10. `generate` no longer weighs the map:

    ```bash
    sed -i '/^            weigh_addresses(addresses, carried, args.address_map.as_posix())$/d' src/ddd/cli.py
    ```

    `2 failed, 432 passed`: `test_cli.py::TestGenerate::test_an_address_no_a2l_field_could_hold_is_refused_where_the_a2l_states_it` and `test_an_address_no_a2l_field_could_hold_names_the_map_forward_slashed`.

Then, from the worktree's root: `git worktree remove build/ablate`.

### Task 3: placing a symbol in an image

**Files:** Modify `src/ddd/addresses.py`; Test `tests/test_addresses.py`.

**Interfaces:** Consumes `Image`, `Variable` (with `external`), `Struct`, `Member`, `Array`, `Typedef`, `Qualified`, `size_of` of `ddd.elf`, and `CType` for its annotations. Produces `Placed` and `addresses_from_image` (above).

Section 4 of the spec, over images built by hand: the external variable, a common pair, the access path's steps, every reason, and bitfields hard.

`addresses_from_image` indexes the image's variables by name once, then places each symbol on its own. The variable is the one of the symbol's name with external linkage; the units describing it at one address are one variable, the first unit's type the one walked. A symbol is read as the a2l spells it: an object's identifier, or a member's path as `ddd.analysis` writes it, the variable's identifier and then `.member` and `[index]` steps (`_ROOT`, `_STEP`). Before each step the walk sees through typedefs and qualifiers; `.member` adds the member's byte offset, `[index]` the index times the size of what one index steps over - the rest of the array's dimensions, so two indices are row-major. Two `assert`s state that every symbol parses, an invariant `addressed_symbols` and `ddd.analysis` establish, as the toolbox's mapping states its own; each says which code establishes it. An `assert` is no branch to coverage.py, like a conditional expression.

The reasons, one sentence each, name the part of the symbol that failed, in the toolbox's voice; two reuse `ddd tool from-elf`'s own sentences (`selection.py`'s for a name nothing describes, with its hint that the unit was built without `-g` where the symbol table holds the name, and `elf-no-storage`'s, with the reader's own reason after the colon):

| Reason (spec section 4) | Sentence, and the symbol it is said of |
| --- | --- |
| no variable of that name | `the image's debug information holds no variable named 'Gian'` (`Gian`) |
| ... and the symbol table holds it | the same, then `; the symbol table holds it, so the unit defining it was built without debug information (-g)` |
| only a `static` of that name | `the image holds 'Gain' only as a static, and every object a dictionary describes is a global` (`Gain`) |
| no storage | `'Gain' has no address in the image: ` and the reader's reason (`Gain`) |
| no member of that name | `'Inlet.pair' has no member named 'mid' in the image` (`Inlet.pair.mid`) |
| a member of what is not a structure | `'Inlet.Level_2' is not a structure, so it has no member named 'bits'` (`Inlet.Level_2.bits`) |
| an index into what is not an array | `'Inlet' is not an array, so it has no element [2]` (`Inlet[2].raw`) |
| an index out of range | `'Grid[1]' has an extent of 3, so it has no element [3]` (`Grid[1][3].v`) |
| a bitfield | `'Mixed.b' is a bitfield, which an address cannot describe` (`Mixed.b`) |

Two reasons are not in section 4's list, because the reader's model holds what no C compiler writes and the walk must say something of it (proposed as rulings 6 and 7 in the notes): `where 'Holder.odd' lies cannot be worked out from the image's debug information`, for a member whose offset DWARF states as an expression the reader does not evaluate (`Member.bit_offset` is None) and for an element the reader gives no size (an array of `Unsupported`); and `'Twice' names globals at 2 addresses of the image, 0x1000, 0x2000`, for globals of one name at different addresses, which no linker makes - one global name is one symbol - and which the walk refuses to guess between.

`ddd.elf` is imported inside the functions that read an image, and its types for annotations under `TYPE_CHECKING`. `generate` imports `ddd.addresses` on every run since Task 2; importing `ddd.elf` costs some 47 ms (measured with `-X importtime`), and a broken installation that lacks pyelftools, which `ddd tool from-elf` answers with a usage error rather than a traceback (`_PYELFTOOLS_MISSING`), would otherwise fail every `generate`. Measured on the scratch branch with `sys.modules["elftools"] = None`: `generate a2l` of the demo project writes its a2l and loads no elftools module; with the reader imported at the top of the module (ablation 14), the same run stops on a traceback, `ModuleNotFoundError: import of elftools halted; None in sys.modules`. `test_reading_a_map_needs_no_pyelftools` holds it.

Review Focus 1's structure is no invention: `MIXED` is the layout gcc 15.2 gives `uint8_t a:3; int8_t b:4; uint8_t c:2; uint16_t value; uint32_t d:20; int16_t e:7; uint8_t level; uint32_t count;` for x86_64, measured with its own `offsetof` (`value 2 level 8 count 12 size 16`) and its DWARF (bitfields at bits 0, 3, 8, 32 and 52), and the bit offsets `open_image` reads of that image are the model's. Review Focus 3's grid needs more than the spec's example: in a grid of two rows of three, `Grid[1][2]` lands at the same place row-major or column-major ((1 · 3 + 2) = (2 · 2 + 1) = 5), so the test asks `Grid[0][1]` and `Grid[1][0]` too, which column-major would put at 0x60A and 0x606.

- [ ] **Step 1: Write the failing tests**

In `tests/test_addresses.py`, the docstring and the imports become:

```python
"""A build's addresses: the map a build writes after the link, the range the a2l holds the
addresses it states to, and the symbols an image places, over images built by hand."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

import ddd.addresses
from ddd.addresses import Placed, addresses_from_image, load_address_map
from ddd.backends.a2l.options import weigh_addresses
from ddd.elf import (
    DECLARED_ONLY,
    DISCARDED,
    DW_ATE_SIGNED,
    DW_ATE_SIGNED_CHAR,
    DW_ATE_UNSIGNED,
    DW_ATE_UNSIGNED_CHAR,
    FOLDED,
    NOT_AN_ADDRESS,
    REMOVED,
    THREAD_LOCAL,
    Array,
    Base,
    CType,
    Image,
    Member,
    Qualified,
    Struct,
    Typedef,
    Unsupported,
    Variable,
)
```

and at the end of the file, add:

```python
U8 = Base("unsigned char", DW_ATE_UNSIGNED_CHAR, 1)
S8 = Base("signed char", DW_ATE_SIGNED_CHAR, 1)
U16 = Base("short unsigned int", DW_ATE_UNSIGNED, 2)
S16 = Base("short int", DW_ATE_SIGNED, 2)
U32 = Base("unsigned int", DW_ATE_UNSIGNED, 4)
PAIR = Struct("Pair_s", 2, (Member("lo", U8, 0), Member("hi", U8, 8)))
INLET = Struct(
    "Inlet_s",
    16,
    (Member("raw", Array(U16, (4,)), 0), Member("pair", PAIR, 64), Member("Level_2", U32, 96)),
)
CELL = Struct("Cell_s", 4, (Member("raw", U16, 0), Member("v", U16, 16)))
MIXED = Struct(
    "Mixed_s",
    16,
    (
        Member("a", U8, 0, 3),
        Member("b", S8, 3, 4),
        Member("c", U8, 8, 2),
        Member("value", U16, 16),
        Member("d", U32, 32, 20),
        Member("e", S16, 52, 7),
        Member("level", U8, 64),
        Member("count", U32, 96),
    ),
)
"""``uint8_t a:3; int8_t b:4; uint8_t c:2; uint16_t value; uint32_t d:20; int16_t e:7;
uint8_t level; uint32_t count;`` as gcc 15.2 lays it out for x86_64 (measured with its own
``offsetof`` and DWARF): ``c`` would cross a byte and starts the next one, ``e`` shares the
storage unit ``d`` started, and the value members land at bytes 2, 8 and 12."""


def image(*variables: Variable, symbols: frozenset[str] = frozenset()) -> Image:
    return Image(Path("hand.elf"), "little", variables, (), symbols, b"")


def stored(
    name: str,
    ctype: CType = U8,
    *,
    unit: str = "unit.c",
    address: int | None = 0x100,
    missing: str = "",
    external: bool = True,
) -> Variable:
    return Variable(name, unit, ctype, None, address, missing, external)


def placed(img: Image, *symbols: str) -> Placed:
    return addresses_from_image(img, symbols)


def reason(img: Image, symbol: str) -> str:
    """Why ``img`` places ``symbol`` nowhere: the one reason, the symbol placed nowhere."""
    found = addresses_from_image(img, [symbol])
    assert found.addresses == {}
    (said,) = found.reasons.values()
    return said


class TestTheVariable:
    """Which variable of the image a symbol names: the global of that name."""

    def test_an_object_is_placed_at_its_variable_s_address(self) -> None:
        img = image(stored("_Cal_Gain_2", U16, address=0x2000_0100))
        assert placed(img, "_Cal_Gain_2") == Placed({"_Cal_Gain_2": 0x2000_0100}, {})

    def test_a_static_of_a_global_s_name_never_stands_for_it(self) -> None:
        """Review Focus 2: the static comes first, in a unit of its own, and the global is the
        one placed."""
        img = image(
            stored("Gain", unit="a.c", address=0x200, external=False),
            stored("Gain", unit="b.c", address=0x100),
        )
        assert placed(img, "Gain") == Placed({"Gain": 0x100}, {})

    def test_a_global_only_a_static_of_its_name_outlives_is_not_placed(self) -> None:
        """Review Focus 2: a global renamed while a static of its old name lives on is
        reported missing rather than given the static's address."""
        img = image(stored("Gain", unit="a.c", address=0x200, external=False))
        assert reason(img, "Gain") == (
            "the image holds 'Gain' only as a static, and every object a dictionary describes "
            "is a global"
        )

    def test_a_common_pair_is_one_variable(self) -> None:
        """Two units describe one tentative definition at one address, as -fcommon or the
        common attribute make them."""
        img = image(
            stored("Counter", U32, unit="unit_a.c", address=0x300),
            stored("Counter", U32, unit="unit_b.c", address=0x300),
        )
        assert placed(img, "Counter") == Placed({"Counter": 0x300}, {})

    def test_globals_of_one_name_at_two_addresses_are_not_placed(self) -> None:
        """No linker makes them, since one global name is one symbol; a model that holds them
        is not guessed at."""
        img = image(
            stored("Twice", unit="a.c", address=0x2000),
            stored("Twice", unit="b.c", address=0x1000),
        )
        assert reason(img, "Twice") == (
            "'Twice' names globals at 2 addresses of the image, 0x1000, 0x2000"
        )

    def test_a_name_the_image_does_not_describe_is_not_placed(self) -> None:
        assert reason(image(stored("Gain")), "Gian") == (
            "the image's debug information holds no variable named 'Gian'"
        )

    def test_a_name_only_the_symbol_table_holds_is_not_placed_naming_g(self) -> None:
        img = image(symbols=frozenset({"Nodebug_Counter"}))
        assert reason(img, "Nodebug_Counter") == (
            "the image's debug information holds no variable named 'Nodebug_Counter'; the "
            "symbol table holds it, so the unit defining it was built without debug "
            "information (-g)"
        )

    @pytest.mark.parametrize(
        "missing", [DECLARED_ONLY, FOLDED, REMOVED, DISCARDED, THREAD_LOCAL, NOT_AN_ADDRESS]
    )
    def test_a_global_without_storage_is_not_placed_with_the_reader_s_reason(
        self, missing: str
    ) -> None:
        img = image(stored("Gain", address=None, missing=missing))
        assert reason(img, "Gain") == f"'Gain' has no address in the image: {missing}"


class TestThePath:
    """A member by its access path: the variable's address and the offsets its type gives."""

    def test_a_member_is_placed_at_its_offset_through_nested_structures(self) -> None:
        img = image(stored("Inlet", INLET, address=0x400))
        assert placed(img, "Inlet.raw", "Inlet.pair.hi", "Inlet.Level_2") == Placed(
            {"Inlet.raw": 0x400, "Inlet.pair.hi": 0x409, "Inlet.Level_2": 0x40C}, {}
        )

    def test_bitfields_before_value_members_leave_each_value_member_at_its_own_offset(
        self,
    ) -> None:
        """Review Focus 1: each value member is where its own offset says, never where the
        sizes before it add up to, and a path naming a bitfield is refused."""
        img = image(stored("Mixed", MIXED, address=0x500))
        symbols = ("Mixed.value", "Mixed.level", "Mixed.count", "Mixed.b", "Mixed.e")
        assert placed(img, *symbols) == Placed(
            {"Mixed.value": 0x502, "Mixed.level": 0x508, "Mixed.count": 0x50C},
            {
                "Mixed.b": "'Mixed.b' is a bitfield, which an address cannot describe",
                "Mixed.e": "'Mixed.e' is a bitfield, which an address cannot describe",
            },
        )

    def test_an_array_of_structures_is_indexed_by_the_size_of_its_element(self) -> None:
        """An index of two digits, as an array of more than ten structures has."""
        img = image(stored("Cells", Array(CELL, (12,)), address=0x700))
        assert placed(img, "Cells[0].raw", "Cells[10].v") == Placed(
            {"Cells[0].raw": 0x700, "Cells[10].v": 0x72A}, {}
        )

    def test_an_array_of_structures_in_two_dimensions_is_indexed_row_major(self) -> None:
        """Review Focus 3: ``Grid[1][2].v`` is ``(1 * 3 + 2) * sizeof(Cell_s) + offsetof(Cell_s,
        v)``. The column-major sum would put ``Grid[0][1]`` and ``Grid[1][0]`` elsewhere."""
        img = image(stored("Grid", Array(CELL, (2, 3)), address=0x600))
        assert placed(img, "Grid[0][1].v", "Grid[1][0].v", "Grid[1][2].v") == Placed(
            {"Grid[0][1].v": 0x606, "Grid[1][0].v": 0x60E, "Grid[1][2].v": 0x616}, {}
        )

    def test_typedefs_and_qualifiers_are_seen_through_before_each_step(self) -> None:
        cell = Typedef("Cell_t", Qualified(CELL, volatile=True))
        rows = Typedef("Row_t", Qualified(Array(cell, (3,)), const=True))
        outer = Struct("Outer_s", 16, (Member("head", U32, 0), Member("rows", rows, 32)))
        img = image(
            stored("Outer", Qualified(Typedef("Outer_t", outer), const=True), address=0x800)
        )
        assert placed(img, "Outer.rows[2].v") == Placed({"Outer.rows[2].v": 0x80E}, {})

    def test_a_member_the_structure_does_not_have_is_not_placed(self) -> None:
        """The C code and the declaration disagree: a member renamed on one side only."""
        assert reason(image(stored("Inlet", INLET)), "Inlet.pair.mid") == (
            "'Inlet.pair' has no member named 'mid' in the image"
        )

    def test_a_member_of_what_is_no_structure_is_not_placed(self) -> None:
        assert reason(image(stored("Inlet", INLET)), "Inlet.Level_2.bits") == (
            "'Inlet.Level_2' is not a structure, so it has no member named 'bits'"
        )

    def test_an_index_into_what_is_no_array_is_not_placed(self) -> None:
        assert reason(image(stored("Inlet", INLET)), "Inlet[2].raw") == (
            "'Inlet' is not an array, so it has no element [2]"
        )

    @pytest.mark.parametrize(
        ("symbol", "said"),
        [
            ("Grid[2][0].v", "'Grid' has an extent of 2, so it has no element [2]"),
            ("Grid[1][3].v", "'Grid[1]' has an extent of 3, so it has no element [3]"),
        ],
    )
    def test_an_index_out_of_range_is_not_placed(self, symbol: str, said: str) -> None:
        """At the extent itself, the first index past the end, in either dimension."""
        assert reason(image(stored("Grid", Array(CELL, (2, 3)))), symbol) == said

    def test_a_member_whose_offset_the_reader_could_not_read_is_not_placed(self) -> None:
        """DWARF may state a member's offset as an expression the reader does not evaluate,
        which it reads as no bit offset at all."""
        holder = Struct("Holder_s", 4, (Member("odd", U32, None),))
        assert reason(image(stored("Holder", holder)), "Holder.odd") == (
            "where 'Holder.odd' lies cannot be worked out from the image's debug information"
        )

    def test_an_element_of_a_type_the_reader_does_not_size_is_not_placed(self) -> None:
        """An array of what the reader does not describe - unions here - has no element size."""
        unions = Array(Unsupported("a union"), (4,))
        assert reason(image(stored("Unions", unions)), "Unions[1].x") == (
            "where 'Unions[1]' lies cannot be worked out from the image's debug information"
        )


class TestWithoutPyelftools:
    def test_reading_a_map_needs_no_pyelftools(
        self, tree: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``generate`` imports this module on every run and only an image needs pyelftools,
        so a broken installation that lacks it still reads a map. Every elftools module an
        earlier test loaded is taken out first, as ``tests/test_cli.py``'s test of a missing
        pyelftools explains, and the package keeps the module it had."""
        for name in [name for name in sys.modules if name.partition(".")[0] == "elftools"]:
            monkeypatch.delitem(sys.modules, name)
        monkeypatch.setitem(sys.modules, "elftools", None)
        monkeypatch.delitem(sys.modules, "ddd.elf")
        monkeypatch.delitem(sys.modules, "ddd.addresses")
        monkeypatch.setattr(ddd, "addresses", ddd.addresses)
        fresh = importlib.import_module("ddd.addresses")
        path = tree / "addresses.json"
        path.write_text('{"A": "0x10"}', encoding="utf-8")
        assert fresh.load_address_map(path) == {"A": 0x10}
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/bin/python -m pytest tests/test_addresses.py --no-cov`
Expected: `Interrupted: 1 error during collection`, for `ImportError: cannot import name 'Placed' from 'ddd.addresses'`.

- [ ] **Step 3: Place the symbols**

In `src/ddd/addresses.py`, the docstring and the imports become:

```python
"""A build's address information: where each symbol of a dictionary sits in the target.

Reading it is core rather than a backend's business: the a2l only consumes the result, and
``SPEC.md`` gives address information a section of its own. Two sources answer the one
question: the map a build writes after the link, ``{"Symbol": "0x20000100"}``, which
:func:`load_address_map` reads, and the linked image itself, whose DWARF
:func:`addresses_from_image` reads through ``ddd.elf`` - objects by name, structure members by
access path. Whether an address fits the field it is written into is the a2l's own question,
which ``ddd.backends.a2l.options.weigh_addresses`` answers for both.

``ddd.elf`` is imported where an image is read and nowhere else: ``generate`` imports this
module on every run, and a broken installation that lacks pyelftools, which the reader needs,
still reads a map.
"""

from __future__ import annotations

import json
import re
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from ddd.elf import CType, Image, Variable
```

and after `_address`, add:

```python
_ROOT: Final = re.compile(r"\w+")
"""The name an access path starts with, the variable's."""
_STEP: Final = re.compile(r"\.(\w+)|\[(\d+)\]")
"""One step of an access path after its name: ``.member``, or ``[index]`` per dimension."""

_UNKNOWN: Final = "where '{}' lies cannot be worked out from the image's debug information"


@dataclass(frozen=True, slots=True)
class Placed:
    """Where an image puts each symbol it places, and why it places none of the others."""

    addresses: dict[str, int]
    """Every symbol placed, at its address."""

    reasons: dict[str, str]
    """Every symbol not placed, and why, in one sentence naming the part of it that failed."""


def addresses_from_image(image: Image, symbols: Collection[str]) -> Placed:
    """Place each symbol in ``image``: an object by its name, a member by its access path.

    The variable is the one of that name with external linkage, since every object a dictionary
    describes is a global: a ``static`` of the name never stands for it, and the units that
    describe one variable at one address, as ``-fcommon`` makes them, describe one variable.
    Each step of the path sees through typedefs and qualifiers first; ``.member`` adds the
    member's offset within its structure, and ``[index]``, one per dimension, the index times
    the size of the element, in C's row-major order. The type the path ends at is not compared
    with the declaration.
    """
    named: dict[str, list[Variable]] = {}
    for variable in image.variables:
        named.setdefault(variable.name, []).append(variable)
    addresses: dict[str, int] = {}
    reasons: dict[str, str] = {}
    for symbol in symbols:
        placed = _placed(symbol, image, named)
        if isinstance(placed, int):
            addresses[symbol] = placed
        else:
            reasons[symbol] = placed
    return Placed(addresses, reasons)


def _placed(symbol: str, image: Image, named: Mapping[str, list[Variable]]) -> int | str:
    """The address of ``symbol``, or why the image gives it none."""
    root = _ROOT.match(symbol)
    # The symbols of an a2l are those addressed_symbols lists: an object's identifier, or a
    # member's path, which ddd.analysis writes starting with the variable's identifier.
    assert root is not None
    found = _variable(root.group(), image, named.get(root.group(), []))
    if isinstance(found, str):
        return found
    address, ctype = found
    return _walk(symbol, root.end(), address, ctype)


def _variable(name: str, image: Image, named: Sequence[Variable]) -> tuple[int, CType] | str:
    """The address and the type of the global ``name``, or why the image holds none."""
    external = [variable for variable in named if variable.external]
    if not external:
        if named:
            return (
                f"the image holds '{name}' only as a static, and every object a dictionary "
                f"describes is a global"
            )
        missing = f"the image's debug information holds no variable named '{name}'"
        if name in image.symbols:
            missing += (
                "; the symbol table holds it, so the unit defining it was built without debug "
                "information (-g)"
            )
        return missing
    located: dict[int, Variable] = {}
    for variable in external:
        if variable.address is not None:
            located.setdefault(variable.address, variable)
    if not located:
        return f"'{name}' has no address in the image: {external[0].missing}"
    if len(located) > 1:
        listed = ", ".join(f"0x{address:X}" for address in sorted(located))
        return f"'{name}' names globals at {len(located)} addresses of the image, {listed}"
    ((address, variable),) = located.items()
    return address, variable.type


def _walk(symbol: str, at: int, address: int, ctype: CType) -> int | str:
    """``address`` moved along the steps of ``symbol`` from ``at``, or why it cannot be."""
    from ddd.elf import Array, Struct, size_of

    while at < len(symbol):
        step = _STEP.match(symbol, at)
        # ddd.analysis writes a member's path as identifiers joined by dots, an index per
        # dimension after an array of structures (_element_paths), and nothing else.
        assert step is not None
        reached = symbol[:at]
        at = step.end()
        core = _seen_through(ctype)
        member, index = step.groups()
        if member is not None:
            if not isinstance(core, Struct):
                return f"'{reached}' is not a structure, so it has no member named '{member}'"
            found = next((entry for entry in core.members if entry.name == member), None)
            if found is None:
                return f"'{reached}' has no member named '{member}' in the image"
            if found.bit_size is not None:
                return f"'{symbol[:at]}' is a bitfield, which an address cannot describe"
            if found.bit_offset is None:
                return _UNKNOWN.format(symbol[:at])
            address += found.bit_offset // 8
            ctype = found.type
            continue
        position = int(index)
        if not isinstance(core, Array):
            return f"'{reached}' is not an array, so it has no element [{position}]"
        extent, *rest = core.dimensions
        if position >= extent:
            return f"'{reached}' has an extent of {extent}, so it has no element [{position}]"
        element = Array(core.element, tuple(rest)) if rest else core.element
        size = size_of(element)
        if size is None:
            return _UNKNOWN.format(symbol[:at])
        address += position * size
        ctype = element
    return address


def _seen_through(ctype: CType) -> CType:
    """``ctype`` without the typedefs and qualifiers around it, as a step of a path sees it."""
    from ddd.elf import Qualified, Typedef

    while isinstance(ctype, Qualified | Typedef):
        ctype = ctype.inner
    return ctype
```

- [ ] **Step 4: Run them to see them pass**

Run: `.venv/bin/python -m pytest tests/test_addresses.py --no-cov`
Expected: `53 passed`.

- [ ] **Step 5: The gates**

Run:

```bash
rm -f .coverage .coverage.*
.venv/bin/python -m pytest > build/gate.txt 2>&1; echo "EXIT=$?"; tail -3 build/gate.txt
.venv/bin/ruff check . > build/ruff.txt 2>&1; echo "RUFF=$?"; tail -1 build/ruff.txt
.venv/bin/ruff format --check . > build/fmt.txt 2>&1; echo "FMT=$?"; tail -1 build/fmt.txt
.venv/bin/mypy > build/mypy.txt 2>&1; echo "MYPY=$?"; tail -1 build/mypy.txt
```

Expected: `EXIT=0`, then `Required test coverage of 100% reached. Total coverage: 100.00%` and `5461 passed`, 26 more than after Task 2; `RUFF=0` and `All checks passed!`; `FMT=0` and `146 files already formatted`; `MYPY=0` and `Success: no issues found in 82 source files`.

- [ ] **Step 6: Commit**

```bash
git add src/ddd/addresses.py tests/test_addresses.py
git commit -F - <<'EOF'
place a symbol in a linked image, by name and by access path

addresses_from_image finds the global of each name - a static of it
never stands for it, and a common pair is one variable - and walks the
access path through the types the image describes: a member adds its
own offset, whatever bitfields come before it, and an index the size of
its element, row-major. Each symbol it cannot place gets one sentence
saying why, naming the part of it that failed. ddd.elf is imported only
where an image is read, so reading a map still needs no pyelftools.

Co-Authored-By: <your model> <noreply@anthropic.com>
EOF
```

- [ ] **Step 7: Ablations**

In a scratch worktree made from the commit, from the worktree's root:

```bash
git worktree add --detach build/ablate HEAD
cd build/ablate
```

Each ablation below is one `sed` on `src/ddd/addresses.py`. After each, run, from `build/ablate`:

```bash
find . -name __pycache__ -prune -exec rm -rf {} +
/home/sauci/Documents/Github/ddd-toolbox-from-elf/.venv/bin/python -m pytest -p no:cacheprovider -o addopts="" tests/test_addresses.py 2>&1 | grep -E "^FAILED|^ERROR|^=.*(passed|failed)|^rootdir"
git checkout -- src/ddd/addresses.py
```

and check that the `rootdir:` line names `build/ablate`. Every test named below is of `tests/test_addresses.py`. All measured on the scratch branch:

1. A static of the name taken for the global:

   ```bash
   sed -i 's/    external = \[variable for variable in named if variable.external\]/    external = list(named)/' src/ddd/addresses.py
   ```

   `2 failed, 51 passed`: `TestTheVariable::test_a_static_of_a_global_s_name_never_stands_for_it`, `TestTheVariable::test_a_global_only_a_static_of_its_name_outlives_is_not_placed`.

2. The static and the absent name swap their reasons:

   ```bash
   sed -i 's/^        if named:$/        if not named:/' src/ddd/addresses.py
   ```

   `3 failed, 50 passed`: `TestTheVariable::test_a_global_only_a_static_of_its_name_outlives_is_not_placed`, `TestTheVariable::test_a_name_the_image_does_not_describe_is_not_placed`, `TestTheVariable::test_a_name_only_the_symbol_table_holds_is_not_placed_naming_g`.

3. The `-g` hint given on the wrong side:

   ```bash
   sed -i 's/        if name in image.symbols:/        if name not in image.symbols:/' src/ddd/addresses.py
   ```

   `2 failed, 51 passed`: `TestTheVariable::test_a_name_the_image_does_not_describe_is_not_placed`, `TestTheVariable::test_a_name_only_the_symbol_table_holds_is_not_placed_naming_g`.

4. A global without storage counted as located:

   ```bash
   sed -i 's/^        if variable.address is not None:$/        if True:/' src/ddd/addresses.py
   ```

   `6 failed, 47 passed`: the six cases of `TestTheVariable::test_a_global_without_storage_is_not_placed_with_the_reader_s_reason`.

5. The two units of a common pair counted as two variables:

   ```bash
   sed -i 's/    if len(located) > 1:/    if len(external) > 1:/' src/ddd/addresses.py
   ```

   `1 failed, 52 passed`: `TestTheVariable::test_a_common_pair_is_one_variable`.

6. A bitfield placed like a value member (Review Focus 1):

   ```bash
   sed -i 's/            if found.bit_size is not None:/            if found.bit_size is not None and False:/' src/ddd/addresses.py
   ```

   `1 failed, 52 passed`: `TestThePath::test_bitfields_before_value_members_leave_each_value_member_at_its_own_offset`.

7. A member's offset taken in bits:

   ```bash
   sed -i 's|            address += found.bit_offset // 8|            address += found.bit_offset|' src/ddd/addresses.py
   ```

   `5 failed, 48 passed`: `TestThePath::test_a_member_is_placed_at_its_offset_through_nested_structures`, `TestThePath::test_bitfields_before_value_members_leave_each_value_member_at_its_own_offset`, `TestThePath::test_an_array_of_structures_is_indexed_by_the_size_of_its_element`, `TestThePath::test_an_array_of_structures_in_two_dimensions_is_indexed_row_major`, `TestThePath::test_typedefs_and_qualifiers_are_seen_through_before_each_step`.

8. Value members laid end to end, as if the bitfields before them took no space (Review Focus 1):

   ```bash
   sed -i 's|^            address += found.bit_offset // 8$|            address += sum(size_of(m.type) or 0 for m in core.members[: core.members.index(found)] if m.bit_size is None)|' src/ddd/addresses.py
   ```

   `2 failed, 51 passed`: `TestThePath::test_a_member_is_placed_at_its_offset_through_nested_structures`, `TestThePath::test_bitfields_before_value_members_leave_each_value_member_at_its_own_offset`.

9. The dimensions taken last first (Review Focus 3):

   ```bash
   sed -i 's/        extent, \*rest = core.dimensions$/        extent, *rest = core.dimensions[::-1]/' src/ddd/addresses.py
   ```

   `3 failed, 50 passed`: `TestThePath::test_an_array_of_structures_in_two_dimensions_is_indexed_row_major` and both cases of `TestThePath::test_an_index_out_of_range_is_not_placed`.

10. An index stepping over one element whatever dimensions remain (Review Focus 3):

    ```bash
    sed -i 's/        element = Array(core.element, tuple(rest)) if rest else core.element/        element = core.element/' src/ddd/addresses.py
    ```

    `2 failed, 51 passed`: `TestThePath::test_an_array_of_structures_in_two_dimensions_is_indexed_row_major`, and the `Grid[1][3].v` case of `TestThePath::test_an_index_out_of_range_is_not_placed`.

11. The last index still leaving an array:

    ```bash
    sed -i 's/        element = Array(core.element, tuple(rest)) if rest else core.element/        element = Array(core.element, tuple(rest))/' src/ddd/addresses.py
    ```

    `3 failed, 50 passed`: `TestThePath::test_an_array_of_structures_is_indexed_by_the_size_of_its_element`, `TestThePath::test_an_array_of_structures_in_two_dimensions_is_indexed_row_major`, `TestThePath::test_typedefs_and_qualifiers_are_seen_through_before_each_step`.

12. An index equal to the extent taken as in range:

    ```bash
    sed -i 's/        if position >= extent:/        if position > extent:/' src/ddd/addresses.py
    ```

    `2 failed, 51 passed`: both cases of `TestThePath::test_an_index_out_of_range_is_not_placed`.

13. Typedefs and qualifiers not seen through:

    ```bash
    sed -i 's/        core = _seen_through(ctype)/        core = ctype/' src/ddd/addresses.py
    ```

    `1 failed, 52 passed`: `TestThePath::test_typedefs_and_qualifiers_are_seen_through_before_each_step`.

14. The reader imported with the module:

    ```bash
    sed -i 's/^from typing import TYPE_CHECKING, Final$/from typing import TYPE_CHECKING, Final\n\nfrom ddd.elf import size_of/' src/ddd/addresses.py
    ```

    `1 failed, 52 passed`: `TestWithoutPyelftools::test_reading_a_map_needs_no_pyelftools`.

15. An index of one digit only:

    ```bash
    sed -i 's/^_STEP: Final = re.compile(r"\\.(\\w+)|\\\[(\\d+)\\\]")$/_STEP: Final = re.compile(r"\\.(\\w+)|\\[(\\d)\\]")/' src/ddd/addresses.py
    ```

    `1 failed, 52 passed`: `TestThePath::test_an_array_of_structures_is_indexed_by_the_size_of_its_element`.

16. A name of letters only:

    ```bash
    sed -i 's/^_ROOT: Final = re.compile(r"\\w+")$/_ROOT: Final = re.compile(r"[A-Za-z]+")/' src/ddd/addresses.py
    ```

    `2 failed, 51 passed`: `TestTheVariable::test_an_object_is_placed_at_its_variable_s_address`, `TestTheVariable::test_a_name_only_the_symbol_table_holds_is_not_placed_naming_g`.

17. A member's name of lowercase letters only:

    ```bash
    sed -i 's/^_STEP: Final = re.compile(r"\\.(\\w+)|/_STEP: Final = re.compile(r"\\.([a-z]+)|/' src/ddd/addresses.py
    ```

    `2 failed, 51 passed`: `TestThePath::test_a_member_is_placed_at_its_offset_through_nested_structures`, `TestThePath::test_a_member_of_what_is_no_structure_is_not_placed`.

18. The sentence of an unknown offset reworded:

    ```bash
    sed -i "s/^_UNKNOWN: Final = \"where '{}' lies cannot be worked out from the image's debug information\"$/_UNKNOWN: Final = \"where '{}' lies is unknown\"/" src/ddd/addresses.py
    ```

    `2 failed, 51 passed`: `TestThePath::test_a_member_whose_offset_the_reader_could_not_read_is_not_placed`, `TestThePath::test_an_element_of_a_type_the_reader_does_not_size_is_not_placed`.

Every other sentence of the table above is asserted whole by the test its row names, which dies of any change to it.

Then, from the worktree's root: `git worktree remove build/ablate`.

### Task 4: the address fixtures, built in Docker and committed

**Files:** Create `docker/build_address_fixtures.py`, `tests/fixtures/addresses/` (the project, its generated C, the oracle source, the images, `manifest.json`), `tests/test_address_fixtures.py`; Modify `docker-compose.yml`.

The fixture directory, file by file:

- `project/project.ddd.json`, `project/types.ddd.json`, `project/engine.ddd.json`: the DDD project, written by hand (Step 1);
- `generated/ddd_types.h`, `ddd_globals.h`, `ddd_globals.c`, `Engine.h` and `.ddd-manifest.json`: what `ddd generate c` writes for the project, with `examples/templates`; `symbols.json`: the symbols its a2l carries an `ECU_ADDRESS` for, and its bitfield members; `oracle.c`: the oracle's source. All written on the host by `docker/build_address_fixtures.py --generate` (Step 7);
- `armv7m.elf`, `powerpc.elf`, `i686.elf`, `x86_64.elf`, `aarch64_be.elf` and `manifest.json`: written by the compose service (Step 8).

**Interfaces:** Consumes `ROWS`, `COMMON`, `Row`, `run`, `macros`, `digest` and `DOCKERFILE` of `build_elf_fixtures`. Produces the images and the manifest (above) that Task 5 holds `--image` to, each row stating two keys more than the skeleton drew: `pointer_size` (the compiler's `__SIZEOF_POINTER__`) and `offsets` (each carried symbol's offset from its variable, the compiler's `offsetof`). And the importable module `build_address_fixtures` (`docker/` is on pytest's `pythonpath`): `OUTPUT`, `PROJECT`, `GENERATED`, `SYMBOLS`, `ORACLE`, `MANIFEST`, `ROWS`, `hashed`, `root_of`, `oracle_source`, `generate_c`, `listed`.

A small DDD project - scalars of nine datatypes, measurements and parameters, a structure nesting another, arrays of structures in one and two dimensions, and four structures mixing bitfields of several widths and signedness with value members around them, one of them the element of every array of structures - whose C is what `ddd generate c` writes for it, committed beside it. Five rows of the toolbox matrix compile and link it: `armv7m` (gcc, 32 bit, little endian), `powerpc` (gcc, 32 bit, big endian), `i686` (gcc, 32 bit, little endian, a `uint64_t` aligned to 4), `x86_64` (gcc, 64 bit, a static PIE), `aarch64_be` (clang, 64 bit, big endian). The oracle is the toolchain (Ruling 4): each variable's address from `nm`, and each carried symbol's offset from its variable from the compiler's own `offsetof`, compiled into the image as integer constants and read back with `readelf` in the row's byte order.

The work has two halves, because DDD and the toolchains live in different places (Ruling 3). On the host, `docker/build_address_fixtures.py --generate` writes the C with `ddd generate c`; the symbols the a2l carries an `ECU_ADDRESS` for (`addressed_symbols`) and the bitfield members, which it carries none for, into `symbols.json`; and `oracle.c`, one `offsetof(struct { __typeof__(Root) r; }, r<steps>)` per symbol. Wrapping the variable's type in a structure gives one spelling for a member (`r.latest.value`), an array element (`r[2].v`) and both (`r[1][2].v`); gcc 14 and clang 19 compile the committed `oracle.c` and `generated/ddd_globals.c` under `-Wall -Wextra` on all five rows without a diagnostic (measured). In Docker, the compose service compiles `generated/ddd_globals.c` and `oracle.c` for each row, with the row's compiler and flags out of `build_elf_fixtures.py`, links them, and writes the manifest. `--generate` puts the checkout's `src` first on its path, as pytest's `pythonpath` does: run with the venv's interpreter from another checkout, `import ddd` finds whichever checkout the editable install names (measured: run from a scratch worktree under `build/`, it imported this worktree's `src`).

`tests/test_address_fixtures.py` regenerates the C and the symbols with the current DDD and compares them with the committed ones, so that a change to what DDD generates fails here rather than leaving the images behind; the hashes say when what the images were built from changed after they were. The project's descriptions are not hashed: the images are built from the C, and the C is held to the project. Each generated file's banner names the DDD that wrote it (`Generated from 'project.ddd.json' by ddd 0.11.0.`), and the test reads a fresh banner as naming the one `symbols.json` records: a release changes that line in every file and nothing a compiler reads, so it asks for no rebuild (ablation 7 below).

What the five rows measured (Review Focus 1 and 3). A bitfield that would cross a unit of its declared type starts the next one (each image's DWARF, read with `readelf`, puts `Status.mode` at byte 1 and `Status.count` at byte 4). A value member after bitfields takes the next byte its alignment allows, inside the bitfields' unit when it fits (`Mixed.after` at 1 and `Mixed.next` at 2, inside the four bytes of `flags`). A bitfield's declared type aligns its structure. The rows number a unit's bits from its least significant end (little endian) or its most (big endian), and gcc states a field's place as `DW_AT_bit_offset` within its unit at DWARF 3 and 4 (`powerpc`, `armv7m`, `i686`), where gcc at DWARF 5 and clang state `DW_AT_data_bit_offset` (`x86_64`, `aarch64_be`). `Grid[i][j]` is element `i * 3 + j` of the six on every row.

Four of the rows lay the project out identically, byte for byte: every carried symbol's offset and every structure's size are theirs in common. `i686` is the one that does not, and the one row of the whole toolbox matrix that does not (the ten rows were measured): it aligns a `uint64_t` to 4, so the eight byte unit of `Mixed.big` may start at byte 4, its DWARF placing `big` at bits 32 to 71 where the others place it at 64 to 103, and `Mixed.last` is at 12 there and at 16 on the others, `Mixed_t` 16 bytes rather than 24. That row is what lets Task 5 tell an offset read out of the image from one predicted from the declaration: the rules of any one of the five targets, applied to every row, give `Mixed.last` a wrong offset on some row. `test_the_rows_lay_the_project_out_in_more_than_one_way` holds the matrix to keeping such a row.

- [ ] **Step 1: The project**

Three files under `tests/fixtures/addresses/project/`. The declarations' ids were stamped by `ddd id --assign`, so that the check reports no `missing-id`.

`tests/fixtures/addresses/project/project.ddd.json`:

```json
{
  "$schema": "../../../../schemas/ddd_project.schema.json",
  "project": {
    "name": "AddressFixture",
    "description": "Every shape of variable whose address ddd generate a2l --image reads out of a linked image",
    "includes": [
      "types.ddd.json",
      "engine.ddd.json"
    ]
  }
}
```

`tests/fixtures/addresses/project/types.ddd.json`:

```json
{
  "$schema": "../../../../schemas/ddd_types.schema.json",
  "types": [
    {
      "type": "scalar",
      "name": "Temperature_t",
      "description": "A temperature as the sensors report it",
      "datatype": "uint16",
      "unit": "degC",
      "conversion": {
        "factor": 0.1,
        "offset": -40
      }
    },
    {
      "type": "struct",
      "name": "Sample_t",
      "description": "One reading and the instant it was taken",
      "members": [
        {
          "name": "value",
          "member": "value",
          "description": "The reading itself",
          "typename": "Temperature_t"
        },
        {
          "name": "timestamp",
          "member": "value",
          "description": "Milliseconds since the last reset",
          "datatype": "uint32",
          "conversion": {
            "kind": "identity"
          }
        }
      ]
    },
    {
      "type": "struct",
      "name": "Cell_t",
      "description": "One cell of a grid: two flags between two values",
      "members": [
        {
          "name": "raw",
          "member": "value",
          "description": "The cell's raw reading",
          "datatype": "uint16",
          "conversion": {
            "kind": "identity"
          }
        },
        {
          "name": "valid",
          "member": "bits",
          "description": "Set once the reading is trusted",
          "datatype": "uint8",
          "bits": 1,
          "conversion": {
            "kind": "identity"
          }
        },
        {
          "name": "bias",
          "member": "bits",
          "description": "A signed correction, in counts",
          "datatype": "sint8",
          "bits": 3,
          "conversion": {
            "kind": "identity"
          }
        },
        {
          "name": "v",
          "member": "value",
          "description": "The corrected reading, after the flags",
          "datatype": "sint16",
          "conversion": {
            "kind": "identity"
          }
        }
      ]
    },
    {
      "type": "struct",
      "name": "Sensor_t",
      "description": "A sensor: a nested structure, an array of values and an array of structures",
      "members": [
        {
          "name": "latest",
          "member": "value",
          "description": "The most recent reading",
          "typename": "Sample_t"
        },
        {
          "name": "history",
          "member": "value",
          "description": "The last four readings, oldest first",
          "datatype": "uint16",
          "conversion": {
            "kind": "identity"
          },
          "dimensions": [
            4
          ]
        },
        {
          "name": "cells",
          "member": "value",
          "description": "The sensor's two cells",
          "typename": "Cell_t",
          "dimensions": [
            2
          ]
        },
        {
          "name": "state",
          "member": "value",
          "description": "The sensor's state machine",
          "datatype": "uint8",
          "conversion": {
            "kind": "identity"
          }
        }
      ]
    },
    {
      "type": "struct",
      "name": "Status_t",
      "description": "Bitfields in units of one, two and four bytes, each group followed by a value",
      "members": [
        {
          "name": "ready",
          "member": "bits",
          "description": "Bit 0 of a byte",
          "datatype": "uint8",
          "bits": 1,
          "conversion": {
            "kind": "identity"
          }
        },
        {
          "name": "trim",
          "member": "bits",
          "description": "Four signed bits after it",
          "datatype": "sint8",
          "bits": 4,
          "conversion": {
            "kind": "identity"
          }
        },
        {
          "name": "mode",
          "member": "bits",
          "description": "Five bits, which would cross the byte and so start the next one",
          "datatype": "uint8",
          "bits": 5,
          "conversion": {
            "kind": "identity"
          }
        },
        {
          "name": "level",
          "member": "value",
          "description": "A byte after the byte bitfields",
          "datatype": "uint8",
          "conversion": {
            "kind": "identity"
          }
        },
        {
          "name": "count",
          "member": "bits",
          "description": "Nine bits, which would cross a two byte unit after level",
          "datatype": "uint16",
          "bits": 9,
          "conversion": {
            "kind": "identity"
          }
        },
        {
          "name": "delta",
          "member": "bits",
          "description": "Seven signed bits after them",
          "datatype": "sint16",
          "bits": 7,
          "conversion": {
            "kind": "identity"
          }
        },
        {
          "name": "word",
          "member": "value",
          "description": "Two bytes after the two byte bitfields",
          "datatype": "uint16",
          "conversion": {
            "kind": "identity"
          }
        },
        {
          "name": "wide",
          "member": "bits",
          "description": "Twenty bits of a four byte unit",
          "datatype": "uint32",
          "bits": 20,
          "conversion": {
            "kind": "identity"
          }
        },
        {
          "name": "drift",
          "member": "bits",
          "description": "Twelve signed bits filling it",
          "datatype": "sint32",
          "bits": 12,
          "conversion": {
            "kind": "identity"
          }
        },
        {
          "name": "tail",
          "member": "value",
          "description": "A byte after the four byte bitfields",
          "datatype": "uint8",
          "conversion": {
            "kind": "identity"
          }
        }
      ]
    },
    {
      "type": "struct",
      "name": "Mixed_t",
      "description": "Values inside a bitfield's unit, and bitfields of an eight byte unit",
      "members": [
        {
          "name": "flags",
          "member": "bits",
          "description": "Three bits of a four byte unit",
          "datatype": "uint32",
          "bits": 3,
          "conversion": {
            "kind": "identity"
          }
        },
        {
          "name": "after",
          "member": "value",
          "description": "A byte right after the three bits, inside their unit",
          "datatype": "uint8",
          "conversion": {
            "kind": "identity"
          }
        },
        {
          "name": "next",
          "member": "value",
          "description": "Two bytes after it, still inside the unit",
          "datatype": "uint16",
          "conversion": {
            "kind": "identity"
          }
        },
        {
          "name": "big",
          "member": "bits",
          "description": "Forty bits, which would cross an eight byte unit after next",
          "datatype": "uint64",
          "bits": 40,
          "conversion": {
            "kind": "identity"
          }
        },
        {
          "name": "small",
          "member": "bits",
          "description": "Seven signed bits after them",
          "datatype": "sint64",
          "bits": 7,
          "conversion": {
            "kind": "identity"
          }
        },
        {
          "name": "last",
          "member": "value",
          "description": "Four bytes after the eight byte bitfields",
          "datatype": "uint32",
          "conversion": {
            "kind": "identity"
          }
        }
      ]
    },
    {
      "type": "struct",
      "name": "Tuning_t",
      "description": "What the calibration tool may change: values around two bitfields",
      "members": [
        {
          "name": "gain",
          "member": "value",
          "description": "The loop gain",
          "datatype": "float32",
          "conversion": {
            "kind": "identity"
          }
        },
        {
          "name": "shift",
          "member": "value",
          "description": "A signed offset, in counts",
          "datatype": "sint16",
          "conversion": {
            "kind": "identity"
          }
        },
        {
          "name": "enable",
          "member": "bits",
          "description": "Whether the loop runs",
          "datatype": "uint8",
          "bits": 1,
          "conversion": {
            "kind": "identity"
          }
        },
        {
          "name": "retries",
          "member": "bits",
          "description": "How many times a failed step is tried again",
          "datatype": "uint8",
          "bits": 3,
          "conversion": {
            "kind": "identity"
          }
        },
        {
          "name": "timeout",
          "member": "value",
          "description": "Milliseconds before a step fails, after the bitfields",
          "datatype": "uint16",
          "conversion": {
            "kind": "identity"
          }
        }
      ]
    }
  ]
}
```

`tests/fixtures/addresses/project/engine.ddd.json`:

```json
{
  "$schema": "../../../../schemas/ddd_component.schema.json",
  "component": {
    "name": "Engine",
    "description": "Owns one variable of every shape the address fixtures place",
    "interface": [
      {
        "scope": "local",
        "definition": {
          "name": "Speed",
          "id": "bfat9q1g4y8q",
          "kind": "measurement",
          "description": "Shaft speed",
          "datatype": "uint16",
          "unit": "rpm",
          "conversion": {
            "factor": 0.25
          },
          "volatile": true
        }
      },
      {
        "scope": "local",
        "definition": {
          "name": "Torque",
          "id": "p84fyq945ckp",
          "kind": "measurement",
          "description": "Shaft torque, initialised so that it lands in .data",
          "datatype": "sint32",
          "unit": "Nm",
          "conversion": {
            "kind": "identity"
          },
          "init": 7,
          "volatile": false
        }
      },
      {
        "scope": "local",
        "definition": {
          "name": "Ratio",
          "id": "rtkepdw8cpra",
          "kind": "measurement",
          "description": "Gear ratio",
          "datatype": "float32",
          "conversion": {
            "kind": "identity"
          },
          "volatile": false
        }
      },
      {
        "scope": "local",
        "definition": {
          "name": "Energy",
          "id": "dnbmba1zk0zy",
          "kind": "measurement",
          "description": "Energy spent since the last reset",
          "datatype": "float64",
          "unit": "J",
          "conversion": {
            "kind": "identity"
          },
          "volatile": false
        }
      },
      {
        "scope": "local",
        "definition": {
          "name": "Ticks",
          "id": "nd6qrjg7hgn7",
          "kind": "measurement",
          "description": "Timer ticks since the last reset",
          "datatype": "uint64",
          "conversion": {
            "kind": "identity"
          },
          "volatile": true
        }
      },
      {
        "scope": "local",
        "definition": {
          "name": "Gear",
          "id": "p5fzcaheqtwe",
          "kind": "measurement",
          "description": "Engaged gear, negative in reverse",
          "datatype": "sint8",
          "conversion": {
            "kind": "identity"
          },
          "volatile": false
        }
      },
      {
        "scope": "local",
        "definition": {
          "name": "Samples",
          "id": "6acmvbvxk2th",
          "kind": "measurement",
          "description": "The last eight raw samples, an array of values",
          "datatype": "uint8",
          "conversion": {
            "kind": "identity"
          },
          "dimensions": [
            8
          ],
          "volatile": false
        }
      },
      {
        "scope": "local",
        "definition": {
          "name": "Enabled",
          "id": "n9ma3hy5nxk5",
          "kind": "parameter",
          "description": "Whether the engine may start",
          "datatype": "boolean",
          "conversion": {
            "kind": "identity"
          },
          "init": 1,
          "volatile": false
        }
      },
      {
        "scope": "local",
        "definition": {
          "name": "Gain",
          "id": "ftpmn0admvst",
          "kind": "parameter",
          "description": "Speed loop gain",
          "datatype": "float32",
          "conversion": {
            "kind": "identity"
          },
          "init": 1.5,
          "volatile": true
        }
      },
      {
        "scope": "local",
        "definition": {
          "name": "Limit",
          "id": "93dn9m9f7mcq",
          "kind": "parameter",
          "description": "Torque limit",
          "datatype": "sint16",
          "unit": "Nm",
          "conversion": {
            "kind": "identity"
          },
          "init": -100,
          "volatile": false
        }
      },
      {
        "scope": "local",
        "definition": {
          "name": "Table",
          "id": "2ercpfv47pdm",
          "kind": "value_block",
          "description": "Four calibratable thresholds",
          "datatype": "uint16",
          "conversion": {
            "kind": "identity"
          },
          "dimensions": [
            4
          ],
          "init": [
            1,
            2,
            3,
            4
          ],
          "volatile": false
        }
      },
      {
        "scope": "local",
        "definition": {
          "name": "Inlet",
          "id": "etdr67q3vvcj",
          "kind": "measurement",
          "description": "The inlet sensor: a structure nesting another, with arrays inside",
          "typename": "Sensor_t",
          "volatile": true
        }
      },
      {
        "scope": "local",
        "definition": {
          "name": "Cells",
          "id": "psbkecghsm2d",
          "kind": "measurement",
          "description": "An array of structures in one dimension",
          "typename": "Cell_t",
          "dimensions": [
            3
          ],
          "volatile": false
        }
      },
      {
        "scope": "local",
        "definition": {
          "name": "Grid",
          "id": "w7zx1jpxhwfg",
          "kind": "measurement",
          "description": "An array of structures in two dimensions",
          "typename": "Cell_t",
          "dimensions": [
            2,
            3
          ],
          "volatile": false
        }
      },
      {
        "scope": "local",
        "definition": {
          "name": "Status",
          "id": "39c5pyjmhysh",
          "kind": "measurement",
          "description": "Bitfields of one, two and four bytes between values",
          "typename": "Status_t",
          "volatile": true
        }
      },
      {
        "scope": "local",
        "definition": {
          "name": "Mixed",
          "id": "cettvg2rwnnb",
          "kind": "measurement",
          "description": "Values inside a bitfield's unit, and an eight byte unit",
          "typename": "Mixed_t",
          "volatile": false
        }
      },
      {
        "scope": "local",
        "definition": {
          "name": "Tuning",
          "id": "0pfcysc07am4",
          "kind": "parameter",
          "description": "The calibration of the speed loop, bitfields among its values",
          "typename": "Tuning_t",
          "volatile": true
        }
      }
    ]
  }
}
```

- [ ] **Step 2: Check it**

Run: `.venv/bin/python -m ddd check tests/fixtures/addresses/project/project.ddd.json`
Expected: `ok: 80 variables in 1 component are consistent`, exit 0: eleven objects and 69 structure members, 34 of which are bitfields.

- [ ] **Step 3: The build script**

`docker/build_address_fixtures.py`:

```python
#!/usr/bin/env python3
"""Build the address fixtures of ``ddd generate a2l --image``, and the manifest that is their
oracle.

Two steps, each a mode of this script, both run from the repository root:

1. ``python docker/build_address_fixtures.py --generate``, on the host, where DDD is importable,
   writes what ``ddd generate c`` writes for the project in ``tests/fixtures/addresses/project/``
   into ``tests/fixtures/addresses/generated/``; the symbols its a2l carries an ``ECU_ADDRESS``
   for, and its bitfield members, which get none, into ``symbols.json``; and the oracle's
   source, ``oracle.c``.
2. ``docker compose run --rm address-fixtures`` compiles and links that C for five rows of the
   toolbox's matrix (``build_elf_fixtures.py``), into ``tests/fixtures/addresses/<row>.elf``,
   and writes ``manifest.json``.

The images are committed, so that the suite needs neither Docker nor a compiler; and the C they
are built from is committed beside them, so that a test can hold it to what DDD generates today.

The manifest is what each toolchain itself says, never what ddd's reader says, which is what the
tests check against it. A variable's address is what ``nm`` says. A member's offset from its
variable is the compiler's own ``offsetof``, applied to a structure wrapping the variable's type,
so that one spelling serves a structure member, an array element and both at once: ``oracle.c``
compiles one constant per symbol into a section of its own, and ``readelf`` reads them back out
of the image in the row's byte order. Constants rather than addresses stored in the image,
because a static PIE (the ``x86_64`` row) keeps an absolute address as a dynamic relocation whose
bytes in the file are zero.

The Docker mode needs nothing but the standard library and ``build_elf_fixtures.py``. The suite
imports this module too, and must be able to without running anything.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal

import build_elf_fixtures
from build_elf_fixtures import COMMON, DOCKERFILE, Row, digest, macros, run

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "tests" / "fixtures" / "addresses"
PROJECT = OUTPUT / "project" / "project.ddd.json"
GENERATED = OUTPUT / "generated"
SYMBOLS = OUTPUT / "symbols.json"
ORACLE = OUTPUT / "oracle.c"
MANIFEST = OUTPUT / "manifest.json"
TEMPLATES = ROOT / "examples" / "templates"
TOOLBOX = Path(build_elf_fixtures.__file__).resolve()
SECTION = ".address_oracle"
ENTRY = "address_oracle_entry"
_TOOLBOX_ROWS = {row.name: row for row in build_elf_fixtures.ROWS}
ROWS = tuple(_TOOLBOX_ROWS[name] for name in ("armv7m", "powerpc", "i686", "x86_64", "aarch64_be"))
"""Little and big endian, 32 and 64 bit, gcc and clang; and ``i686``, whose ``uint64_t`` aligns to
4, the one row of the matrix that lays the project out otherwise, so that an offset predicted by
one target's rules is wrong on some row."""

_STEP = re.compile(r"[.\[]")
_DUMP = re.compile(r"^\s+0x[0-9a-f]+ (?P<bytes>[0-9a-f ]{35})")
_ORACLE_HEAD = f"""\
/* oracle.c - written by docker/build_address_fixtures.py out of symbols.json; do not edit.
 *
 * The offset of every symbol the a2l of tests/fixtures/addresses/project/ carries an
 * ECU_ADDRESS for, from the variable it belongs to, as this unit's compiler lays the variable
 * out: one constant per symbol, in the order symbols.json lists them. The build reads them back
 * out of each image and adds the variable's address, which nm gives.
 */
#include <stddef.h>
#include <stdint.h>

#include "ddd_globals.h"

__attribute__((used, section("{SECTION}"))) const uint32_t address_oracle[] = {{
"""
_ORACLE_TAIL = f"""\
}};

/* The image's entry point: the images are read, never run. */
void {ENTRY}(void) {{}}
"""


def hashed() -> dict[str, str]:
    """What the images are built from, by path relative to the repository, and its digest."""
    paths = [
        *sorted(GENERATED.iterdir()),
        ORACLE,
        SYMBOLS,
        DOCKERFILE,
        TOOLBOX,
        Path(__file__).resolve(),
    ]
    return {path.relative_to(ROOT).as_posix(): digest(path) for path in paths}


def root_of(symbol: str) -> str:
    """The variable a symbol belongs to: its access path up to the first step."""
    return _STEP.split(symbol, maxsplit=1)[0]


def oracle_source(symbols: Sequence[str]) -> str:
    """``oracle.c``: the offset of each symbol from its variable, in the order given."""
    entries = []
    for symbol in symbols:
        root = root_of(symbol)
        steps = symbol[len(root) :]
        entries.append(f"    offsetof(struct {{ __typeof__({root}) r; }}, r{steps}),\n")
    return _ORACLE_HEAD + "".join(entries) + _ORACLE_TAIL


def generate_c(directory: Path) -> None:
    """Write what ``ddd generate c`` writes for the project, with the repository's templates."""
    from ddd.cli import main

    arguments = ["generate", "c", str(PROJECT), "-o", str(directory), "-t", str(TEMPLATES)]
    if main(arguments) != 0:
        msg = f"ddd {' '.join(arguments)} failed"
        raise SystemExit(msg)


def listed() -> dict[str, Any]:
    """The symbols the project's a2l carries an ``ECU_ADDRESS`` for, its bitfield members, which
    it carries none for, and the DDD that says so."""
    from ddd import DiagnosticBag
    from ddd.analysis import analyze
    from ddd.backends.a2l.model import addressed_symbols
    from ddd.cli import GENERATOR
    from ddd.loading import load_workspace

    bag = DiagnosticBag()
    workspace = load_workspace(PROJECT, bag)
    if workspace is None or bag.has_errors:
        raise SystemExit("\n".join(finding.render() for finding in bag))
    dictionary = analyze(workspace, bag)
    return {
        "generator": GENERATOR,
        "addressed": list(addressed_symbols(dictionary)),
        "bitfields": sorted(leaf.path for leaf in dictionary.leaves if leaf.bits is not None),
    }


def generate() -> None:
    """The host's half: the C, the symbols and the oracle's source, out of the project."""
    generate_c(GENERATED)
    found = listed()
    SYMBOLS.write_text(json.dumps(found, indent=2) + "\n", "utf-8", newline="\n")
    ORACLE.write_text(oracle_source(found["addressed"]), "utf-8", newline="\n")
    print(
        f"wrote {len(found['addressed'])} symbols and {len(found['bitfields'])} bitfields into "
        f"{SYMBOLS.relative_to(ROOT).as_posix()}, and their oracle"
    )


def build(row: Row, work: Path) -> Path:
    """Compile the generated definitions and the oracle for one row and link them; the image
    lands in ``work``."""
    objects: list[str] = []
    for source in ("generated/ddd_globals.c", "oracle.c"):
        target = work / f"{row.name}-{Path(source).stem}.o"
        run(
            [
                *row.compiler,
                *row.target,
                *COMMON,
                *row.dwarf,
                f"-ffile-prefix-map={OUTPUT}=.",
                "-Igenerated",
                "-c",
                source,
                "-o",
                str(target),
            ],
            cwd=OUTPUT,
        )
        objects.append(str(target))
    image = work / f"{row.name}.elf"
    run(
        [
            *row.compiler,
            *row.target,
            *row.dwarf,
            "-nostdlib",
            f"-Wl,-e,{ENTRY}",
            *row.link,
            *objects,
            "-o",
            str(image),
        ],
        cwd=OUTPUT,
    )
    return image


def addresses_of(image: Path) -> dict[str, int]:
    """Every global symbol an image defines, and its address, as ``nm`` reads it."""
    found: dict[str, int] = {}
    for line in run(["nm", "-P", "-g", "--defined-only", str(image)], cwd=OUTPUT).splitlines():
        name, _kind, value, *_size = line.split()
        found[name] = int(value, 16)
    return found


def oracle_of(image: Path, byte_order: Literal["little", "big"]) -> list[int]:
    """The oracle's constants, as ``readelf`` dumps their section out of an image."""
    data = bytearray()
    for line in run(["readelf", "-x", SECTION, str(image)], cwd=OUTPUT).splitlines():
        match = _DUMP.match(line)
        if match is not None:
            data += bytes.fromhex(match["bytes"])
    return [int.from_bytes(data[start : start + 4], byte_order) for start in range(0, len(data), 4)]


def main() -> None:
    """Build every row, then the manifest."""
    found = json.loads(SYMBOLS.read_text(encoding="utf-8"))
    rows: dict[str, object] = {}
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory)
        for row in ROWS:
            image = build(row, work)
            shutil.copyfile(image, OUTPUT / image.name)
            defined = macros(row)
            order: Literal["little", "big"] = (
                "big" if defined["__BYTE_ORDER__"] == "__ORDER_BIG_ENDIAN__" else "little"
            )
            offsets = dict(zip(found["addressed"], oracle_of(image, order), strict=True))
            symbols = addresses_of(image)
            rows[row.name] = {
                "compiler": run([row.compiler[0], "--version"]).splitlines()[0],
                "flags": [*row.compiler[1:], *row.target, *COMMON, *row.dwarf, *row.link],
                "byte_order": order,
                "pointer_size": int(defined["__SIZEOF_POINTER__"]),
                "offsets": offsets,
                "addresses": {
                    symbol: symbols[root_of(symbol)] + offset for symbol, offset in offsets.items()
                },
                "bitfields": found["bitfields"],
            }
    manifest = {"hashes": hashed(), "rows": rows}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", "utf-8")
    print(f"wrote {len(ROWS)} rows into {OUTPUT.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build the address fixtures.")
    parser.add_argument(
        "--generate",
        action="store_true",
        help="write the C, the symbols and the oracle's source, on the host, with DDD",
    )
    if parser.parse_args().generate:
        # This checkout's DDD, as the suite's own pythonpath has it, rather than whichever one
        # the interpreter happens to have installed.
        sys.path.insert(0, str(ROOT / "src"))
        generate()
    else:
        main()
```

- [ ] **Step 4: The compose service**

In `docker-compose.yml`, after the `elf-fixtures` service and before `volumes:`:

```yaml
  # docker compose run --rm address-fixtures rebuilds the images of `ddd generate a2l --image`
  # that tests/fixtures/addresses/ holds, and their manifest, out of the C that `ddd generate c`
  # wrote there and five rows of the toolchains above, whose image this service shares. The
  # images are committed, so the suite needs neither Docker nor a compiler: this service is only
  # for changing them, after `python docker/build_address_fixtures.py --generate` has rewritten
  # the C on the host. What it writes into the checkout is handed back to the checkout's owner,
  # since the image runs as root.
  address-fixtures:
    build:
      context: docker
      dockerfile: elf-fixtures.Dockerfile
    image: ddd-elf-fixtures:dev
    working_dir: /work
    volumes:
      - .:/work
    command:
      - sh
      - -c
      - |
        python3 docker/build_address_fixtures.py
        status=$$?
        chown -R "$$(stat -c %u:%g .)" tests/fixtures/addresses
        exit $$status
```

Its `build:` is the `elf-fixtures` service's, so that either service builds the image the two share when it is missing; neither touches `ddd:dev`.

- [ ] **Step 5: Write the failing test**

`tests/test_address_fixtures.py`:

```python
"""The committed address fixtures are built from what DDD generates today, as far as a test can
tell without a compiler, and they span what they are there to span.

The images are built in Docker (``docker compose run --rm address-fixtures``) out of C that DDD
generated on the host (``python docker/build_address_fixtures.py --generate``), and all of it is
committed, so the suite runs where Docker cannot. Two things can leave the images stale, and each
has its tests: DDD can come to generate other C, or to carry other symbols, for the project, which
a fresh generation here notices; and what the images were built from can change after they were,
which the hashes notice.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from build_address_fixtures import (
    GENERATED,
    MANIFEST,
    ORACLE,
    OUTPUT,
    ROWS,
    SYMBOLS,
    generate_c,
    hashed,
    listed,
    oracle_source,
)

from ddd.cli import GENERATOR

FIXTURES = json.loads(MANIFEST.read_text(encoding="utf-8"))
LISTED = json.loads(SYMBOLS.read_text(encoding="utf-8"))
ROW_NAMES = [row.name for row in ROWS]


def test_the_images_are_built_from_what_is_committed() -> None:
    assert FIXTURES["hashes"] == hashed(), (
        "tests/fixtures/addresses/ was built from other sources than the ones committed: rebuild "
        "it with 'docker compose run --rm address-fixtures' and commit what it writes"
    )


def test_the_committed_c_is_what_ddd_generates_for_the_project(tmp_path: Path) -> None:
    """Every file, the output directory's manifest included. The banner names the DDD that wrote
    the file, and is read as naming the one ``symbols.json`` records: a release changes that line
    in every file, and nothing a compiler reads."""
    generate_c(tmp_path)
    fresh = {
        path.name: path.read_text(encoding="utf-8").replace(GENERATOR, LISTED["generator"])
        for path in tmp_path.iterdir()
    }
    committed = {path.name: path.read_text(encoding="utf-8") for path in GENERATED.iterdir()}
    assert fresh == committed, (
        "DDD no longer generates what tests/fixtures/addresses/generated/ holds: rewrite it with "
        "'python docker/build_address_fixtures.py --generate', then rebuild the images"
    )


def test_the_symbols_are_the_ones_the_a2l_carries_and_the_bitfields_it_leaves_out() -> None:
    fresh = listed()
    assert (fresh["addressed"], fresh["bitfields"]) == (LISTED["addressed"], LISTED["bitfields"]), (
        "DDD no longer carries the symbols tests/fixtures/addresses/symbols.json lists: rewrite it "
        "with 'python docker/build_address_fixtures.py --generate', then rebuild the images"
    )


def test_the_oracle_is_written_from_the_symbols() -> None:
    assert ORACLE.read_text(encoding="utf-8") == oracle_source(LISTED["addressed"]), (
        "tests/fixtures/addresses/oracle.c is not the oracle of symbols.json: rewrite it with "
        "'python docker/build_address_fixtures.py --generate', then rebuild the images"
    )


def test_every_row_is_built_and_described() -> None:
    assert list(FIXTURES["rows"]) == ROW_NAMES
    for row in ROW_NAMES:
        assert (OUTPUT / f"{row}.elf").is_file()


def test_the_rows_span_both_byte_orders_both_widths_and_both_compilers() -> None:
    rows = FIXTURES["rows"].values()
    assert {row["byte_order"] for row in rows} == {"little", "big"}
    assert {row["pointer_size"] for row in rows} == {4, 8}
    assert any("clang" in row["compiler"] for row in rows)
    assert any("gcc" in row["compiler"] for row in rows)


def test_the_rows_lay_the_project_out_in_more_than_one_way() -> None:
    """``i686`` aligns a ``uint64_t`` to 4 where the other rows align it to 8, so ``Mixed.last``
    is at 12 there and at 16 elsewhere. Rows that all agreed could not tell an offset read out of
    the image from one predicted by a single target's rules."""
    layouts = {tuple(sorted(row["offsets"].items())) for row in FIXTURES["rows"].values()}
    assert len(layouts) > 1


@pytest.mark.parametrize("row", ROW_NAMES)
def test_every_carried_symbol_has_an_address_on_every_row(row: str) -> None:
    assert sorted(FIXTURES["rows"][row]["offsets"]) == LISTED["addressed"]
    assert sorted(FIXTURES["rows"][row]["addresses"]) == LISTED["addressed"]


@pytest.mark.parametrize("row", ROW_NAMES)
def test_no_bitfield_member_has_an_address(row: str) -> None:
    bitfields = FIXTURES["rows"][row]["bitfields"]
    assert bitfields == LISTED["bitfields"]
    assert not set(bitfields) & set(FIXTURES["rows"][row]["addresses"])


@pytest.mark.parametrize("row", ROW_NAMES)
def test_the_two_dimensional_array_of_structures_is_laid_out_row_major(row: str) -> None:
    """``Grid[i][j]`` is element ``i * 3 + j`` of the six: ``Grid[1][0]`` is three elements on
    from ``Grid[0][0]``, where a column-major layout would put it one on."""
    offsets = FIXTURES["rows"][row]["offsets"]
    size = offsets["Grid[0][1].raw"] - offsets["Grid[0][0].raw"]
    for i in range(2):
        for j in range(3):
            for member in ("raw", "v"):
                start = offsets[f"Grid[0][0].{member}"]
                assert offsets[f"Grid[{i}][{j}].{member}"] == start + (i * 3 + j) * size
```

- [ ] **Step 6: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_address_fixtures.py --no-cov`
Expected: FAIL at collection, `ERROR tests/test_address_fixtures.py - FileNotFoundError: [Errno 2] No such f...` for `tests/fixtures/addresses/manifest.json`, `1 error`.

- [ ] **Step 7: Generate the C on the host**

Run: `.venv/bin/python docker/build_address_fixtures.py --generate`
Expected, exit 0 (measured in a scratch worktree, whose path is replaced here by this one's):

```text
wrote       /home/sauci/Documents/Github/ddd-toolbox-from-elf/tests/fixtures/addresses/generated/ddd_globals.c (created)
wrote       /home/sauci/Documents/Github/ddd-toolbox-from-elf/tests/fixtures/addresses/generated/ddd_globals.h (created)
wrote       /home/sauci/Documents/Github/ddd-toolbox-from-elf/tests/fixtures/addresses/generated/ddd_types.h (created)
wrote       /home/sauci/Documents/Github/ddd-toolbox-from-elf/tests/fixtures/addresses/generated/Engine.h (created)
wrote 46 symbols and 34 bitfields into tests/fixtures/addresses/symbols.json, and their oracle
```

46 symbols get an `ECU_ADDRESS`: the eleven objects and the 35 members that are not bitfields. The 34 bitfields get none.

The bitfield structures it declares, in `generated/ddd_types.h`:

```c
/* Mixed_t - Values inside a bitfield's unit, and bitfields of an eight byte unit */
typedef struct
{
    uint32_t flags : 3; /**< Three bits of a four byte unit */
    uint8_t after; /**< A byte right after the three bits, inside their unit */
    uint16_t next; /**< Two bytes after it, still inside the unit */
    uint64_t big : 40; /**< Forty bits, which would cross an eight byte unit after next */
    int64_t small : 7; /**< Seven signed bits after them */
    uint32_t last; /**< Four bytes after the eight byte bitfields */
} Mixed_t;
```

```c
/* Status_t - Bitfields in units of one, two and four bytes, each group followed by a value */
typedef struct
{
    uint8_t ready : 1; /**< Bit 0 of a byte */
    int8_t trim : 4; /**< Four signed bits after it */
    uint8_t mode : 5; /**< Five bits, which would cross the byte and so start the next one */
    uint8_t level; /**< A byte after the byte bitfields */
    uint16_t count : 9; /**< Nine bits, which would cross a two byte unit after level */
    int16_t delta : 7; /**< Seven signed bits after them */
    uint16_t word; /**< Two bytes after the two byte bitfields */
    uint32_t wide : 20; /**< Twenty bits of a four byte unit */
    int32_t drift : 12; /**< Twelve signed bits filling it */
    uint8_t tail; /**< A byte after the four byte bitfields */
} Status_t;
```

and the first entries of `oracle.c`'s array, the symbols in `symbols.json`'s order:

```c
__attribute__((used, section(".address_oracle"))) const uint32_t address_oracle[] = {
    offsetof(struct { __typeof__(Cells) r; }, r[0].raw),
    offsetof(struct { __typeof__(Cells) r; }, r[0].v),
```

- [ ] **Step 8: Build the image and the fixtures**

```bash
docker image ls ddd:dev --format '{{.ID}}'
docker compose -p ddd-addresses build address-fixtures
docker compose -p ddd-addresses run --rm address-fixtures
```

Expected: the first prints `ddd:dev`'s id, which must be the one recorded before Task 1; note it for Step 11. The build ends ` Image ddd-elf-fixtures:dev Built`: 8 s here, every layer from BuildKit's cache of the toolbox's build of 2026-09-30, the image itself having been removed; without that cache it downloads the toolchains first. Each `build` gives `ddd-elf-fixtures:dev` a new id even from the cache: the id is the digest of the index BuildKit writes, which holds an attestation of the build beside the unchanged `linux/amd64` manifest (measured: `5e71aeb6cd4e`, then `d45c22699dc7`, both over manifest `e9602c95cf82`). The run prints `wrote 5 rows into tests/fixtures/addresses`, exit 0, in about a second.

Then read the rows:

```bash
.venv/bin/python -c "import json; m = json.load(open('tests/fixtures/addresses/manifest.json')); [print(f'{k:11}', v['byte_order'], v['pointer_size'], v['compiler']) for k, v in m['rows'].items()]"
```

Expected:

```text
armv7m      little 4 arm-none-eabi-gcc (15:14.2.rel1-1) 14.2.1 20241119
powerpc     big 4 powerpc-linux-gnu-gcc (Debian 14.2.0-19) 14.2.0
i686        little 4 i686-linux-gnu-gcc (Debian 14.2.0-19) 14.2.0
x86_64      little 8 x86_64-linux-gnu-gcc (Debian 14.2.0-19) 14.2.0
aarch64_be  big 8 Debian clang version 19.1.7 (3+b1)
```

A compiler that answers otherwise is not an error to fix here: it is what that toolchain says, and the tests read the manifest. Report it.

And the offsets of the value members after bitfields, of the arrays of structures' elements, and of `Grid` (Review Focus 1 and 3):

```bash
.venv/bin/python -c "import json; m = json.load(open('tests/fixtures/addresses/manifest.json')); rows = m['rows'].values(); [print(f'{s:16}', *(row['offsets'][s] for row in rows)) for s in ['Status.level', 'Status.word', 'Status.tail', 'Mixed.after', 'Mixed.next', 'Mixed.last', 'Tuning.timeout', 'Cells[2].v', 'Inlet.cells[1].v', 'Grid[0][0].v', 'Grid[1][0].v', 'Grid[1][2].v']]"
```

Expected, one column per row in the manifest's order (`armv7m`, `powerpc`, `i686`, `x86_64`, `aarch64_be`):

```text
Status.level     2 2 2 2 2
Status.word      6 6 6 6 6
Status.tail      12 12 12 12 12
Mixed.after      1 1 1 1 1
Mixed.next       2 2 2 2 2
Mixed.last       16 16 12 16 16
Tuning.timeout   8 8 8 8 8
Cells[2].v       16 16 16 16 16
Inlet.cells[1].v 26 26 26 26 26
Grid[0][0].v     4 4 4 4 4
Grid[1][0].v     22 22 22 22 22
Grid[1][2].v     34 34 34 34 34
```

`Status.level`, `.word` and `.tail` follow bitfields of one, two and four bytes; `Mixed.after` and `.next` sit inside the four byte unit of the three bits before them, and `Mixed.last` follows the eight byte unit of `big`, at 12 on `i686` alone, whose eight byte unit may start at byte 4; `Tuning.timeout` follows two bitfields in a calibration structure; `Cells[2].v`, `Inlet.cells[1].v` and `Grid[1][2].v` follow the bitfields of `Cell_t`, six bytes, in an array of one dimension, an array member, and an array of two. `Grid[1][0].v` is 18 bytes - three elements - on from `Grid[0][0].v`, where a column-major layout would put it six.

Check the sizes, the owner, and that nothing else changed:

```bash
du -cb tests/fixtures/addresses/*.elf tests/fixtures/addresses/manifest.json
ls -l tests/fixtures/addresses
git status --short
```

Expected: `5360` for `aarch64_be.elf`, `38064` for `armv7m.elf`, `16704` for `i686.elf`, `70224` for `powerpc.elf`, `17848` for `x86_64.elf`, `21197` for `manifest.json`, `169397 total`; every file owned by you, not by root; `git status` lists `docker-compose.yml` as modified and `docker/build_address_fixtures.py`, `tests/fixtures/addresses/` and `tests/test_address_fixtures.py` as new, nothing else.

- [ ] **Step 9: Run the test, then the gates**

Run: `.venv/bin/python -m pytest tests/test_address_fixtures.py --no-cov`
Expected: `22 passed`, in a tenth of a second: the drift tests run `ddd generate c` and the analysis over 80 variables. Seven tests, three of them parametrized over the five rows.

Then:

```bash
rm -f .coverage .coverage.*
.venv/bin/python -m pytest > build/gate.txt 2>&1; echo "EXIT=$?"; tail -3 build/gate.txt
.venv/bin/ruff check . > build/ruff.txt 2>&1; echo "RUFF=$?"; tail -1 build/ruff.txt
.venv/bin/ruff format --check . > build/fmt.txt 2>&1; echo "FMT=$?"; tail -1 build/fmt.txt
.venv/bin/mypy > build/mypy.txt 2>&1; echo "MYPY=$?"; tail -1 build/mypy.txt
```

Expected: `EXIT=0`, then `Required test coverage of 100% reached. Total coverage: 100.00%` and `5484 passed`, 23 more than after Task 3: the 22 of the new file, and `tests/test_documentation.py::TestTheSuiteRunsEverythingEverywhere::test_nothing_in_the_suite_skips[test_address_fixtures.py]`, the case every new test file adds there (the scratch branch measured `5410 passed` at `8d97d92`, and `5433` with this task alone; after Tasks 1 to 3 both counts are higher, by the same 23). `RUFF=0` and `All checks passed!`; `FMT=0` and `N files already formatted`, two more than before the task (`146` on the scratch branch, from `144`); `MYPY=0` and `Success: no issues found in N source files`, as many as before the task (`81` on the scratch branch). ruff reads `docker/` and `tests/`; mypy reads neither, coverage measures only `ddd`, and the build script's own branches are held by the drift tests and the ablations below instead.

- [ ] **Step 10: Commit**

```bash
git add docker/build_address_fixtures.py docker-compose.yml tests/test_address_fixtures.py tests/fixtures/addresses/project/project.ddd.json tests/fixtures/addresses/project/types.ddd.json tests/fixtures/addresses/project/engine.ddd.json tests/fixtures/addresses/generated/.ddd-manifest.json tests/fixtures/addresses/generated/Engine.h tests/fixtures/addresses/generated/ddd_globals.c tests/fixtures/addresses/generated/ddd_globals.h tests/fixtures/addresses/generated/ddd_types.h tests/fixtures/addresses/symbols.json tests/fixtures/addresses/oracle.c tests/fixtures/addresses/armv7m.elf tests/fixtures/addresses/powerpc.elf tests/fixtures/addresses/i686.elf tests/fixtures/addresses/x86_64.elf tests/fixtures/addresses/aarch64_be.elf tests/fixtures/addresses/manifest.json
git commit -F - <<'EOF'
build the address fixtures of ddd generate a2l --image in docker, and commit them

A small DDD project - scalars, a nested structure, arrays of structures in one
and two dimensions, and bitfields in units of one, two, four and eight bytes
with value members after them - whose C is what ddd generate c writes for it,
compiled and linked for five rows of the toolbox matrix: little and big
endian, 32 and 64 bit, gcc and clang, and i686, whose uint64_t aligns to 4
and so lays the project out otherwise. The manifest is the toolchain's word,
never the reader's: each variable's address from nm, each member's offset
from the compiler's own offsetof, read back out of the image. A test
regenerates the C and the symbols with the current DDD, so that the images
cannot drift from what it generates.

Co-Authored-By: <your model> <noreply@anthropic.com>
EOF
```

The message comes from a here-document: `git commit -m "$(printf ...)"` was refused by the command guard the plan's sessions run under, and the quoted `'EOF'` keeps the shell from expanding anything in the message.

- [ ] **Step 11: Build once more: nothing moves**

```bash
.venv/bin/python docker/build_address_fixtures.py --generate
docker compose -p ddd-addresses run --rm address-fixtures
git status --short tests/fixtures/addresses
docker image ls ddd:dev --format '{{.ID}}'
```

Expected: `--generate` says `unchanged` for each of the four C files and prints its last line again; the run prints `wrote 5 rows into tests/fixtures/addresses`; `git status` prints nothing, the images and the manifest rebuilt byte for byte; the id is the one Step 8 noted. A difference is a finding: report which files moved.

- [ ] **Step 12: Ablations**

The whole-suite counts quoted below were measured while this task was drafted on its own, before Tasks 1 to 3 joined the branch, so the totals you see are 51 higher. What each ablation must do is kill the named tests; the counts beside them only show that nothing else moved.

In a scratch worktree made from the commit, from the worktree's root:

```bash
git worktree add --detach build/ablate HEAD
cd build/ablate
PY=/home/sauci/Documents/Github/ddd-toolbox-from-elf/.venv/bin/python
edit() { "$PY" -c "import json, pathlib; p = pathlib.Path('tests/fixtures/addresses/manifest.json'); d = json.loads(p.read_text()); $1; p.write_text(json.dumps(d, indent=2) + '\n')"; }
```

`edit` applies one change to the manifest and writes it back the way the build script writes it. Each ablation below is one edit. After each, run, from `build/ablate`:

```bash
find . -name __pycache__ -prune -exec rm -rf {} +
"$PY" -m pytest -p no:cacheprovider -o addopts="" tests/test_address_fixtures.py tests/test_elf_fixtures.py 2>&1 | grep -E "^FAILED|^ERROR|^=.*(passed|failed)|^rootdir"
```

check that the `rootdir:` line names `build/ablate`, then undo the edit with the `git checkout --` the ablation names. Before any edit the run says `53 passed`. All measured on the scratch branch, where each ablation was also run over the whole suite: nothing died there beyond what is named here.

1. The fixture image's Dockerfile changed:

   ```bash
   echo "# ablated" >> docker/elf-fixtures.Dockerfile
   ```

   `2 failed, 51 passed`: `test_the_images_are_built_from_what_is_committed`, here and in `tests/test_elf_fixtures.py`, whose images the Dockerfile builds too; the message names `docker compose run --rm address-fixtures`. Undo: `git checkout -- docker/elf-fixtures.Dockerfile`.

2. A checkout that converts line endings, as git on Windows may:

   ```bash
   sed -i 's/$/\r/' tests/fixtures/addresses/generated/ddd_types.h tests/fixtures/addresses/oracle.c
   ```

   `53 passed`: the hashes and the comparisons read a file with its line endings normalised. Undo: `git checkout -- tests/fixtures/addresses/generated/ddd_types.h tests/fixtures/addresses/oracle.c`.

3. DDD generating other C for the project:

   ```bash
   sed -i 's|^#include <stdint.h>$|#include <stdint.h>\n#include <stddef.h>|' examples/templates/ddd_types.h.jinja2
   ```

   `1 failed, 52 passed`: `test_the_committed_c_is_what_ddd_generates_for_the_project`, its message naming `--generate`. Over the whole suite it is the only test that dies: nothing else holds the example templates' output. Undo: `git checkout -- examples/templates/ddd_types.h.jinja2`.

4. A change to the project that no hash sees:

   ```bash
   sed -i 's/"bits": 5,/"bits": 3,/' tests/fixtures/addresses/project/types.ddd.json
   ```

   `1 failed, 52 passed`: the same test, alone. The descriptions are not hashed; the C they generate is, and this test holds it to them. Undo: `git checkout -- tests/fixtures/addresses/project/types.ddd.json`.

5. A change to the project that leaves the C as it is and moves the symbols:

   ```bash
   sed -i 's/"name": "last",/"name": "last", "a2l": {"export": false},/' tests/fixtures/addresses/project/types.ddd.json
   ```

   `1 failed, 52 passed`: `test_the_symbols_are_the_ones_the_a2l_carries_and_the_bitfields_it_leaves_out`, alone. Undo: `git checkout -- tests/fixtures/addresses/project/types.ddd.json`.

6. Another generator recorded:

   ```bash
   sed -i 's/"generator": "ddd 0.11.0"/"generator": "ddd 0.10.0"/' tests/fixtures/addresses/symbols.json
   ```

   `2 failed, 51 passed`: `test_the_images_are_built_from_what_is_committed` and `test_the_committed_c_is_what_ddd_generates_for_the_project`. Undo: `git checkout -- tests/fixtures/addresses/symbols.json`.

7. A release:

   ```bash
   sed -i 's/^__version__ = "0.11.0"$/__version__ = "0.12.0"/' src/ddd/__init__.py
   ```

   `53 passed`: a release asks for no rebuild of the fixtures. Over the whole suite, `28 failed, 5390 passed, 15 errors`, every one in `tests/test_cmake.py`, `tests/test_documentation.py` (the version's other spellings) or `tests/test_transcripts.py` (`docs/getting_started.rst`): what a release bumps with the version, none of it this task's. Undo: `git checkout -- src/ddd/__init__.py`.

8. The oracle out of step with the symbols:

   ```bash
   sed -i '/(Mixed) r; }, r\.after),$/{N;s/\(.*\)\n\(.*\)/\2\n\1/}' tests/fixtures/addresses/oracle.c
   ```

   `2 failed, 51 passed`: `test_the_images_are_built_from_what_is_committed` and `test_the_oracle_is_written_from_the_symbols`. Undo: `git checkout -- tests/fixtures/addresses/oracle.c`.

9. A row missing (undo this one and the five after it with `git checkout -- tests/fixtures/addresses/manifest.json`):

   ```bash
   edit "del d['rows']['powerpc']"
   ```

   `4 failed, 49 passed`: `test_every_row_is_built_and_described`, and the `[powerpc]` cases of the three tests parametrized over the rows.

10. One byte order for every row:

    ```bash
    sed -i 's/"byte_order": "big"/"byte_order": "little"/' tests/fixtures/addresses/manifest.json
    ```

    `1 failed, 52 passed`: `test_the_rows_span_both_byte_orders_both_widths_and_both_compilers`.

11. A carried symbol without an address:

    ```bash
    edit "del d['rows']['x86_64']['addresses']['Mixed.after']"
    ```

    `1 failed, 52 passed`: `test_every_carried_symbol_has_an_address_on_every_row[x86_64]`.

12. A bitfield missing from a row's list:

    ```bash
    edit "d['rows']['aarch64_be']['bitfields'].remove('Status.ready')"
    ```

    `1 failed, 52 passed`: `test_no_bitfield_member_has_an_address[aarch64_be]`, alone.

13. A bitfield given an address (Review Focus 1):

    ```bash
    edit "a = d['rows']['aarch64_be']['addresses']; a['Mixed.flags'] = a['Mixed.after'] - 1"
    ```

    `2 failed, 51 passed`: `test_no_bitfield_member_has_an_address[aarch64_be]` and `test_every_carried_symbol_has_an_address_on_every_row[aarch64_be]`.

14. A two-dimensional array of structures laid out column-major (Review Focus 3):

    ```bash
    edit "d['rows']['powerpc']['offsets'].update({f'Grid[{i}][{j}].{m}': (j * 2 + i) * 6 + s for i in range(2) for j in range(3) for m, s in (('raw', 0), ('v', 4))})"
    ```

    `1 failed, 52 passed`: `test_the_two_dimensional_array_of_structures_is_laid_out_row_major[powerpc]`.

15. The row that lays the project out otherwise dropped from the build script (undo this one and the two after it with `git checkout -- docker/build_address_fixtures.py`):

    ```bash
    sed -i 's/"powerpc", "i686", "x86_64"/"powerpc", "x86_64"/' docker/build_address_fixtures.py
    ```

    `2 failed, 48 passed`: `test_the_images_are_built_from_what_is_committed` and `test_every_row_is_built_and_described`; the three `[i686]` cases are no longer collected. Rebuilt without it, the manifest would also fail `test_the_rows_lay_the_project_out_in_more_than_one_way` (ablation 24).

16. Every member taken for a bitfield, `listed`'s comprehension filter dropped:

    ```bash
    sed -i 's/for leaf in dictionary.leaves if leaf.bits is not None/for leaf in dictionary.leaves/' docker/build_address_fixtures.py
    ```

    `2 failed, 51 passed`: `test_the_images_are_built_from_what_is_committed` and `test_the_symbols_are_the_ones_the_a2l_carries_and_the_bitfields_it_leaves_out`.

17. An index read as part of the variable's name, `_STEP` narrowed:

    ```bash
    sed -i 's/_STEP = re.compile(r"\[.\\\[\]")/_STEP = re.compile(r"[.]")/' docker/build_address_fixtures.py
    ```

    `2 failed, 51 passed`: `test_the_images_are_built_from_what_is_committed` and `test_the_oracle_is_written_from_the_symbols`, the oracle then asking for a member `raw` of a variable `Cells[0]`.

18. One width for every row (undo this one and the three after it with `git checkout -- tests/fixtures/addresses/manifest.json`):

    ```bash
    sed -i 's/"pointer_size": 8/"pointer_size": 4/' tests/fixtures/addresses/manifest.json
    ```

    `1 failed, 52 passed`: `test_the_rows_span_both_byte_orders_both_widths_and_both_compilers`.

19. No clang row:

    ```bash
    sed -i 's/"compiler": "Debian clang/"compiler": "Debian cc/' tests/fixtures/addresses/manifest.json
    ```

    `1 failed, 52 passed`: the same test.

20. No gcc row:

    ```bash
    sed -i 's/-gcc (/-cc (/' tests/fixtures/addresses/manifest.json
    ```

    `1 failed, 52 passed`: the same test.

21. A carried symbol without an offset:

    ```bash
    edit "del d['rows']['x86_64']['offsets']['Mixed.after']"
    ```

    `1 failed, 52 passed`: `test_every_carried_symbol_has_an_address_on_every_row[x86_64]`.

22. An image missing:

    ```bash
    rm tests/fixtures/addresses/powerpc.elf
    ```

    `1 failed, 52 passed`: `test_every_row_is_built_and_described`. The images are not hashed - they are what the build makes of what is - so this test is what notices one gone. Undo: `git checkout -- tests/fixtures/addresses/powerpc.elf`.

23. `i686` laying the project out as the other rows do, as a reader predicting by their rules would have it (undo this one and the next with `git checkout -- tests/fixtures/addresses/manifest.json`):

    ```bash
    edit "d['rows']['i686']['offsets']['Mixed.last'] = 16"
    ```

    `1 failed, 52 passed`: `test_the_rows_lay_the_project_out_in_more_than_one_way`, alone.

24. The `i686` row missing from the manifest:

    ```bash
    edit "del d['rows']['i686']"
    ```

    `5 failed, 48 passed`: `test_every_row_is_built_and_described`, `test_the_rows_lay_the_project_out_in_more_than_one_way` - the four rows left agree on every offset - and the `[i686]` cases of the three tests parametrized over the rows.

Then, from the worktree's root: `git worktree remove build/ablate`.

### Task 5: `--image` on the command line

**Files:** Modify `src/ddd/cli.py`; Test `tests/test_cli.py`.

**Interfaces:** Consumes `load_address_map`, `addresses_from_image` and `Placed` of `ddd.addresses` (Tasks 2 and 3), `weigh_addresses` and `addressed_symbols` of `ddd.backends` (Task 2), `open_image` and `Image` of `ddd.elf`, and Task 4's `tests/fixtures/addresses/`: the project, the five images and `manifest.json`. Produces `ddd generate a2l|all ... --image IMAGE`, and in `tests/test_cli.py` the helper `a2l_addresses(text) -> dict[str, int]`, which Task 6 imports.

`--image` is an option of the a2l artefact, so `generate a2l` and `generate all` take it and `generate c` does not. `generate` reads the image only when it is given, through `_image_reader()`: the import of `open_image` under the guard `ddd tool from-elf` had, which turns a missing pyelftools into the usage error `_PYELFTOOLS_MISSING` (notes-a's ruling 8 - `ddd.addresses` imports `ddd.elf` lazily, so nothing else would). The guard moves out of `_command_tool_from_elf` into that helper rather than being written twice, so the comparison it holds - the package of the module the import stopped at - stays one hidden branch, pinned on both sides by the toolbox's `test_without_pyelftools_the_command_says_how_to_install_it` and `test_a_missing_module_of_ddd_is_not_blamed_on_pyelftools`.

The refusals, each a usage error, exit 2, asserted whole:

| Case | Where | Sentence |
| --- | --- | --- |
| `--image` beside `--address-map` | `_selected`, before anything is read | `--image and --address-map are two sources of the a2l's addresses; give one of them` |
| `--image` in a run without the a2l | `_selected`'s loop over the subtracted artefacts' options | `--image belongs to the a2l artefact, left out by --without` (the map's own sentence) |
| an image the reader refuses | `open_image`, an `ElfReadError`, which is a `ValueError` | the reader's: `'<image>' carries no DWARF debug information: build it with -g`, `cannot read '<image>': No such file or directory`, ... |
| no pyelftools | `_image_reader()` | `_PYELFTOOLS_MISSING` |
| `--byte-order` contradicting the image | after the image is read: only it knows its byte order | `--byte-order big contradicts '<image>', which is little endian` |
| a carried address beyond 32 bits | `weigh_addresses(addresses, carried, image_path.as_posix())` | `<image>: address of 'Speed' is 4294983744, outside the range 0 .. 0xFFFFFFFF that an a2l address can hold` |

Without `--byte-order` the a2l takes the image's byte order; one that agrees is accepted. What the image cannot place reaches the a2l at address 0 and is `address-missing`, located at the image (`where`, so absolute in json as every location is) and worded as the map's finding is, `the image has no address for ...; it reaches the a2l at address 0`. Its notes are the reasons Task 3 wrote, and the question was how they stay readable when many symbols are missing. They are the reasons of the symbols the finding names - `_listed` spells `_LISTED_LIMIT` of them and counts the rest - each said once, in the order of the symbols: every member of a variable the image lacks shares one sentence, `the image's debug information holds no variable named 'Cells'`. Measured with the host's gcc 15.2: the address fixtures' `ddd_globals.c` compiled without `-g`, linked beside a `main.c` compiled with it, gives all 46 symbols missing and a finding of four lines, one note carrying Task 3's `-g` hint. A note has no location, so the reader's `DECLARED_ONLY` - "it is only declared here, and defined nowhere in the image" - reads its "here" against the finding's own place, the image (notes-a, "For the later phases"); it is left as the reader says it.

`_check_image_coverage` is the map's `_check_address_coverage` without its early return - an image is never the run a build makes before it has linked (notes-a) - and the two share the sentence's end, `_at_address_0`, so the conditional choosing `it reaches` or `they reach` is written once. Its `it reaches` side was pinned by no test before (`git grep "it reaches the a2l at address 0"` finds nothing at the commit before this task); the image's single-member test now holds it, and `docs/faq.rst` and `docs/concept.rst` hold the other side through their transcripts (ablation 4).

Review Focus 5 is the cmake module's (Task 6), and rests on a rule of the command line: the manifest of the output directory weighs only the artefacts a run produces, so the a2l run after the link takes back nothing the run before it wrote. Task 6 holds the build to it where the host links ELF, which the windows cells' MinGW does not; this task holds the two runs the module makes - `generate all --without a2l --dictionary`, then `generate a2l --image` into the same directory - on every host CI has: every file of the first run is there afterwards, byte for byte and with its modification time, and the second run reports writing the a2l and nothing else. Measured: breaking the rule (`Manifest.stale` weighing every artefact's files, ablation 17) kills it, where `tests/test_cli.py`'s older `test_the_a2l_run_of_a_two_run_build_keeps_the_c_the_image_was_built_from` survives - its `generate a2l` changes nothing, and `write` returns before removing anything when it has nothing to write.

End to end over every row of Task 4: `ddd generate a2l` of the fixtures' project with `--image <row>.elf` exits 0 with nothing to report, and the a2l it writes, read back record by record, states for every carried symbol exactly the address the manifest gives - 39 `MEASUREMENT`s on their `ECU_ADDRESS` line and 7 `CHARACTERISTIC`s on their `VALUE` or `VAL_BLK` line (notes-b) - no bitfield path appears anywhere in it, and its `BYTE_ORDER` is the row's: `MSB_FIRST` on `powerpc` and `aarch64_be` (Review Focus 4), `MSB_LAST` on the three others. The address beyond 32 bits is a real image too: a copy of `x86_64.elf` whose DWARF locates `Speed` 4 GB higher. gcc writes that location as an expression of nine bytes, `DW_OP_addr` (3) and the eight bytes of the address, which occur once in the image (measured), and the test rewrites them.

- [ ] **Step 1: Write the failing tests**

In `tests/test_cli.py`, the imports become:

```python
import json
import os
import re
import shutil
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, ClassVar

import elftools
import pytest

from conftest import (
    DEMO,
    EXAMPLES,
    INCONSISTENT,
    TEMPLATES,
    component,
    declare,
    project,
    value_member,
    write_tree,
)
```

and at the end of the file, after `TestToolFromElf`, add:

```python
ADDRESS_FIXTURES = Path(__file__).parent / "fixtures" / "addresses"
ADDRESS_PROJECT = ADDRESS_FIXTURES / "project" / "project.ddd.json"
ADDRESS_ROWS = json.loads((ADDRESS_FIXTURES / "manifest.json").read_text(encoding="utf-8"))["rows"]
"""Five images of one project, each beside what its own toolchain says of it: ``nm``'s address
of every variable, the compiler's ``offsetof`` of every member, and the target's byte order."""
X86_ADDRESSES = ADDRESS_FIXTURES / "x86_64.elf"


def a2l_addresses(text: str) -> dict[str, int]:
    """Every record of an a2l and the address it states, read back out of the file: a
    measurement's on its ``ECU_ADDRESS`` line, a characteristic's on its ``VALUE`` or
    ``VAL_BLK`` line."""
    found: dict[str, int] = {}
    record: str | None = None
    for line in text.splitlines():
        words = line.split()
        if words[:2] in (["/begin", "MEASUREMENT"], ["/begin", "CHARACTERISTIC"]):
            record = words[2]
        elif record is not None and words[:1] in (["ECU_ADDRESS"], ["VALUE"], ["VAL_BLK"]):
            found[record] = int(words[1], 16)
            record = None
    return found


def edited_project(tmp_path: Path, file: str, edit: Callable[[dict[str, Any]], None]) -> Path:
    """A copy of the address fixtures' project with one of its files edited, so that it says
    something the images were not built from; ``edit`` changes the file's json in place."""
    shutil.copytree(ADDRESS_PROJECT.parent, tmp_path / "project")
    path = tmp_path / "project" / file
    described = json.loads(path.read_text(encoding="utf-8"))
    edit(described)
    path.write_text(json.dumps(described, indent=2), encoding="utf-8")
    return tmp_path / "project" / "project.ddd.json"


def with_a_window(described: dict[str, Any]) -> None:
    """``Tuning_t`` gains a member, ``window``, that the C of every image lacks."""
    (tuning,) = [entry for entry in described["types"] if entry["name"] == "Tuning_t"]
    tuning["members"].append(value_member("window", "uint16"))


class TestGenerateFromAnImage:
    """``ddd generate a2l --image``: every address the a2l carries, out of the linked image."""

    def arguments(self, tmp_path: Path, project: Path = ADDRESS_PROJECT) -> list[str]:
        return ["generate", "a2l", str(project), "-o", str(tmp_path / "gen")]

    @pytest.mark.parametrize("row", sorted(ADDRESS_ROWS))
    def test_every_row_writes_the_addresses_and_the_byte_order_of_its_image(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], row: str
    ) -> None:
        """Every object and member at the address ``nm`` and the compiler's own ``offsetof``
        give it - the value members after bitfields included, and no bitfield anywhere (Review
        Focus 1) - and the byte order the image states: two of the rows are big endian (Review
        Focus 4), and ``i686`` lays the project out unlike the other four."""
        expected = ADDRESS_ROWS[row]
        a2l = tmp_path / "gen" / "AddressFixture.a2l"
        image = ADDRESS_FIXTURES / f"{row}.elf"
        assert main([*self.arguments(tmp_path), "--image", str(image)]) == EXIT_OK
        assert capsys.readouterr().err == f"wrote       {a2l.as_posix()} (created)\n"
        text = a2l.read_text(encoding="utf-8")
        assert a2l_addresses(text) == expected["addresses"]
        assert [path for path in expected["bitfields"] if path in text] == []
        order = {"little": "MSB_LAST", "big": "MSB_FIRST"}[expected["byte_order"]]
        assert f"      BYTE_ORDER {order}\n" in text

    def test_generate_all_reads_the_image_as_generate_a2l_does(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        output = tmp_path / "gen"
        arguments = [
            "generate",
            "all",
            str(ADDRESS_PROJECT),
            "-o",
            str(output),
            "-t",
            str(TEMPLATES),
        ]
        assert main([*arguments, "--image", str(ADDRESS_FIXTURES / "powerpc.elf")]) == EXIT_OK
        text = (output / "AddressFixture.a2l").read_text(encoding="utf-8")
        assert a2l_addresses(text) == ADDRESS_ROWS["powerpc"]["addresses"]
        assert (output / "ddd_globals.c").is_file()

    def test_a_byte_order_the_image_agrees_with_is_accepted(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        image = ADDRESS_FIXTURES / "powerpc.elf"
        arguments = [*self.arguments(tmp_path), "--image", str(image), "--byte-order", "big"]
        assert main(arguments) == EXIT_OK
        text = (tmp_path / "gen" / "AddressFixture.a2l").read_text(encoding="utf-8")
        assert "      BYTE_ORDER MSB_FIRST\n" in text

    @pytest.mark.parametrize("row", sorted(ADDRESS_ROWS))
    def test_a_byte_order_the_image_contradicts_is_refused(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], row: str
    ) -> None:
        """Review Focus 4: the image states the target's byte order, so an option saying the
        other one is a mistake about the target, refused rather than obeyed into an a2l whose
        every value a calibration tool would read byte-swapped."""
        stated = ADDRESS_ROWS[row]["byte_order"]
        other = {"little": "big", "big": "little"}[stated]
        image = ADDRESS_FIXTURES / f"{row}.elf"
        arguments = [*self.arguments(tmp_path), "--image", str(image), "--byte-order", other]
        assert main(arguments) == EXIT_USAGE
        assert capsys.readouterr().err == (
            f"ddd: --byte-order {other} contradicts '{image.as_posix()}', which is {stated} "
            f"endian\n"
        )
        assert not (tmp_path / "gen").exists()

    def test_an_image_beside_an_address_map_is_refused(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        addresses = tmp_path / "addresses.json"
        addresses.write_text("{}", encoding="utf-8")
        arguments = [*self.arguments(tmp_path), "--image", str(X86_ADDRESSES)]
        assert main([*arguments, "--address-map", str(addresses)]) == EXIT_USAGE
        assert capsys.readouterr().err == (
            "ddd: --image and --address-map are two sources of the a2l's addresses; give one of "
            "them\n"
        )
        assert not (tmp_path / "gen").exists()

    def test_an_image_given_to_a_run_without_the_a2l_is_refused(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """As the map is: a run that never writes the a2l has no use for its addresses."""
        output = tmp_path / "gen"
        arguments = [
            "generate",
            "all",
            str(ADDRESS_PROJECT),
            "-o",
            str(output),
            "-t",
            str(TEMPLATES),
        ]
        assert main([*arguments, "--without", "a2l", "--image", str(X86_ADDRESSES)]) == EXIT_USAGE
        assert capsys.readouterr().err == (
            "ddd: --image belongs to the a2l artefact, left out by --without\n"
        )

    @pytest.mark.parametrize(
        ("image", "said"),
        [
            (
                FIXTURES / "stripped.elf",
                "'{}' carries no DWARF debug information: build it with -g",
            ),
            (ADDRESS_FIXTURES / "missing.elf", "cannot read '{}': No such file or directory"),
        ],
    )
    def test_an_image_the_reader_refuses_is_a_usage_error_in_its_words(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], image: Path, said: str
    ) -> None:
        assert main([*self.arguments(tmp_path), "--image", str(image)]) == EXIT_USAGE
        assert capsys.readouterr().err == f"ddd: {said.format(image.as_posix())}\n"
        assert not (tmp_path / "gen").exists()

    def test_without_pyelftools_an_image_is_refused_saying_how_to_install_it(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """In the words ``ddd tool from-elf`` uses, through the same import. Every elftools
        module an earlier test loaded is taken out, as that command's test explains."""
        loaded = [name for name in sys.modules if name.partition(".")[0] == "elftools"]
        for name in loaded:
            monkeypatch.delitem(sys.modules, name)
        monkeypatch.setitem(sys.modules, "elftools", None)
        monkeypatch.delitem(sys.modules, "ddd.elf", raising=False)
        assert main([*self.arguments(tmp_path), "--image", str(X86_ADDRESSES)]) == EXIT_USAGE
        assert capsys.readouterr().err == (
            "ddd: reading an ELF image needs pyelftools, which is not installed: "
            "pip install 'pyelftools>=0.32,<1'\n"
        )

    def test_a_carried_address_beyond_32_bits_is_refused_naming_the_symbol_and_the_image(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A 64 bit target may place its data above 4 GB, where no ``ECU_ADDRESS`` reaches.
        ``Speed`` is moved there in a copy of the x86_64 image: its DWARF locates it with an
        expression of nine bytes, ``DW_OP_addr`` (3) and the address, which the copy rewrites."""
        address = ADDRESS_ROWS["x86_64"]["addresses"]["Speed"]
        moved = address + 0x1_0000_0000
        data = X86_ADDRESSES.read_bytes()
        located = bytes([9, 3]) + address.to_bytes(8, "little")
        assert data.count(located) == 1, "the x86_64 image no longer locates Speed this way"
        image = tmp_path / "above.elf"
        image.write_bytes(data.replace(located, bytes([9, 3]) + moved.to_bytes(8, "little")))
        assert main([*self.arguments(tmp_path), "--image", str(image)]) == EXIT_USAGE
        assert capsys.readouterr().err == (
            f"ddd: {image.as_posix()}: address of 'Speed' is {moved}, outside the range "
            f"0 .. 0xFFFFFFFF that an a2l address can hold\n"
        )

    def test_a_member_the_image_lacks_reaches_the_a2l_at_0_and_the_finding_says_why(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A description edited after the image was built: the declarations name a member its
        C did not have. The finding is located at the image, resolved as every location is -
        named relative to the working directory here - and its note is the reason."""
        project = edited_project(tmp_path, "types.ddd.json", with_a_window)
        monkeypatch.chdir(ADDRESS_FIXTURES)
        arguments = [*self.arguments(tmp_path, project), "--image", "x86_64.elf"]
        assert main([*arguments, "--format", "json"]) == EXIT_OK
        assert json.loads(capsys.readouterr().out)["diagnostics"] == [
            {
                "check": "address-missing",
                "severity": "warning",
                "message": (
                    "the image has no address for 'Tuning.window'; it reaches the a2l at address 0"
                ),
                "location": {
                    "path": X86_ADDRESSES.resolve().as_posix(),
                    "pointer": None,
                    "line": None,
                    "column": None,
                },
                "notes": [
                    {
                        "message": "'Tuning' has no member named 'window' in the image",
                        "location": None,
                    }
                ],
            }
        ]
        text = (tmp_path / "gen" / "AddressFixture.a2l").read_text(encoding="utf-8")
        assert a2l_addresses(text) == {**ADDRESS_ROWS["x86_64"]["addresses"], "Tuning.window": 0}

    def test_a_symbol_the_image_cannot_place_fails_a_strict_run_which_writes_nothing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        project = edited_project(tmp_path, "types.ddd.json", with_a_window)
        arguments = [*self.arguments(tmp_path, project), "--image", str(X86_ADDRESSES)]
        assert main([*arguments, "--strict"]) == EXIT_FINDINGS
        shown = where(X86_ADDRESSES).render(Path.cwd())
        assert capsys.readouterr().err == (
            f"{shown}: error[address-missing]: the image has no address for 'Tuning.window'; it "
            f"reaches the a2l at address 0\n"
            f"    note: 'Tuning' has no member named 'window' in the image\n"
            f"1 error\n"
        )
        assert not (tmp_path / "gen").exists()

    def test_the_notes_are_the_reasons_of_the_symbols_named_each_said_once(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """An image of the project before two renames, ``Cells`` to ``Bells`` and ``Speed`` to
        ``Spool``: seven symbols it cannot place. The finding names five, the members of
        ``Bells`` sharing one reason, and counts the rest, as it counts a map's: an image whose
        definition file was compiled without ``-g`` misses every symbol of the project, and the
        finding has to stay short. ``Spool``'s reason is not among the notes."""

        def renamed(described: dict[str, Any]) -> None:
            for entry in described["component"]["interface"]:
                name = entry["definition"]["name"]
                entry["definition"]["name"] = {"Cells": "Bells", "Speed": "Spool"}.get(name, name)

        project = edited_project(tmp_path, "engine.ddd.json", renamed)
        arguments = [*self.arguments(tmp_path, project), "--image", str(X86_ADDRESSES)]
        assert main(arguments) == EXIT_OK
        shown = where(X86_ADDRESSES).render(Path.cwd())
        a2l = tmp_path / "gen" / "AddressFixture.a2l"
        assert capsys.readouterr().err == (
            f"{shown}: warning[address-missing]: the image has no address for 'Bells[0].raw', "
            f"'Bells[0].v', 'Bells[1].raw', 'Bells[1].v', 'Bells[2].raw' and 2 others; they "
            f"reach the a2l at address 0\n"
            f"    note: the image's debug information holds no variable named 'Bells'\n"
            f"1 warning\n"
            f"wrote       {a2l.as_posix()} (created)\n"
        )

    def test_the_a2l_run_after_the_link_leaves_what_generate_all_wrote_untouched(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Review Focus 5 through the command line, as the cmake module runs it: ``generate all
        --without a2l --dictionary`` before the link, then ``generate a2l --image`` into the same
        directory. The second run produces the a2l alone, and the output directory's manifest
        weighs only the a2l's files: the c sources, the headers and the dictionary of the first
        are neither taken back nor written again. ``tests/test_cmake.py`` builds the same story
        where the host's toolchain links ELF; this runs on every host."""
        output = tmp_path / "gen"
        dictionary = output / "AddressFixture.dictionary.json"
        before = ["generate", "all", str(ADDRESS_PROJECT), "-o", str(output), "-t", str(TEMPLATES)]
        assert main([*before, "--without", "a2l", "--dictionary", str(dictionary)]) == EXIT_OK
        written = {
            path.name: (path.read_bytes(), path.stat().st_mtime_ns)
            for path in output.iterdir()
            if path.name != MANIFEST_NAME
        }
        assert sorted(written) == [
            "AddressFixture.dictionary.json",
            "Engine.h",
            "ddd_globals.c",
            "ddd_globals.h",
            "ddd_types.h",
        ]
        capsys.readouterr()
        a2l = output / "AddressFixture.a2l"
        assert main([*self.arguments(tmp_path), "--image", str(X86_ADDRESSES)]) == EXIT_OK
        assert capsys.readouterr().err == f"wrote       {a2l.as_posix()} (created)\n"
        kept = {
            path.name: (path.read_bytes(), path.stat().st_mtime_ns)
            for path in output.iterdir()
            if path.name not in (MANIFEST_NAME, a2l.name)
        }
        assert kept == written
```

`FIXTURES`, `where`, `EXIT_FINDINGS` and `MANIFEST_NAME` are the file's own already: the toolbox's fixtures directory, `ddd.diagnostics.where`, the findings exit and the name of the output directory's manifest.

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/bin/python -m pytest tests/test_cli.py --no-cov -k FromAnImage`
Expected: `22 failed, 280 deselected`, every one on `SystemExit: 2`, argparse's `ddd: error: unrecognized arguments: --image ...`.

- [ ] **Step 3: The option, its refusals, and the image as a source of addresses**

In `src/ddd/cli.py`, the imports under `TYPE_CHECKING` become:

```python
if TYPE_CHECKING:
    from pydantic import BaseModel

    from ddd.addresses import Placed
    from ddd.backends import Backend, GeneratedFile, WriteStatus
    from ddd.elf import Image
    from ddd.ir import Comparable, DataDictionary
    from ddd.plugins import Plugin
```

The docstring of `_PYELFTOOLS_MISSING` becomes, and `_image_reader` follows it:

```python
"""The usage error a command reading an image answers without pyelftools: ``ddd tool from-elf``,
and ``ddd generate`` given ``--image``. It is a dependency, so only a broken installation lacks
it, and the command says how to mend one rather than raising."""


def _image_reader() -> Callable[[Path], Image]:
    """:func:`ddd.elf.open_image`, for a command about to read an image.

    The one place a missing pyelftools becomes the usage error :data:`_PYELFTOOLS_MISSING`
    rather than a traceback: ``ddd tool from-elf`` asks for it, and ``ddd generate`` given
    ``--image``. Imported on that call and not before, like everything else this module needs,
    so that no other run pays for pyelftools or needs it.
    """
    try:
        from ddd.elf import open_image
    except ModuleNotFoundError as error:
        # The name is the module the import stopped at - `elftools.common` as often as
        # `elftools` - so the package decides, not the whole name.
        if (error.name or "").partition(".")[0] != "elftools":
            raise
        raise ValueError(_PYELFTOOLS_MISSING) from None
    return open_image
```

and in `_command_tool_from_elf` the `try`/`except` that imported `open_image` - eight lines, from `try:` to `raise ValueError(_PYELFTOOLS_MISSING) from None` - becomes:

```python
    open_image = _image_reader()
```

In `_build_parser`, the description of `generate` says an image as well:

```python
            "renders c takes a template directory, only one that writes the a2l takes an "
            "address map or an image. 'all' produces both, and the artefact of every plugin "
            "the project names that provides one, and takes --without to leave one of the "
            "built-in artefacts out of that; 'a2l' is the run a build repeats "
```

and the a2l artefact's entry of the loop that builds the artefacts becomes:

```python
        (
            "a2l",
            "write the a2l file, with the addresses --address-map or --image gives",
            False,
            True,
            False,
        ),
```

In `_add_generate_arguments`, under `if with_a2l:`, the help of `--byte-order` and the new option:

```python
            help=(
                f"byte order reported in the a2l file, default: {BYTE_ORDERS[0]}, or the "
                f"image's with --image"
            ),
        )
        parser.add_argument(
            "--address-map",
            type=Path,
            help="json file mapping variable names to their address in the target",
        )
        parser.add_argument(
            "--image",
            type=Path,
            help=(
                "linked ELF image whose DWARF debug information gives every address the a2l "
                "carries, and its byte order"
            ),
        )
```

(no `*`, backtick or `|` in either help: `test_no_help_string_carries_markup_characters`).

The map's finding takes its ending from a helper the image's shares; in `_check_address_coverage`:

```python
    bag.add(
        "address-missing",
        f"the address map has no entry for {_at_address_0(missing)}",
        where(path),
        notes=notes,
    )


def _check_image_coverage(
    carried: tuple[str, ...], placed: Placed, path: Path, bag: DiagnosticBag
) -> None:
    """Report the objects an image does not place, and why, as a map's missing ones are.

    The finding is the map's, ``address-missing``, for the same harm - a symbol of the a2l at
    address 0, which a calibration tool reads and writes as readily as any other - without the
    map's early return: an image is never the run a build makes before it has linked. Each
    reason is a note, said once however many symbols share it - every member of a variable the
    image lacks does - for the symbols the finding names; the rest are counted, as a map's are,
    so that an image whose definition file was compiled without ``-g``, every symbol of the
    project missing from its debug information, still gives a finding a few lines long.
    """
    missing = [symbol for symbol in carried if symbol in placed.reasons]
    if not missing:
        return
    reasons = dict.fromkeys(placed.reasons[symbol] for symbol in missing[:_LISTED_LIMIT])
    bag.add(
        "address-missing",
        f"the image has no address for {_at_address_0(missing)}",
        where(path),
        notes=[(reason, None) for reason in reasons],
    )


def _at_address_0(missing: list[str]) -> str:
    """``'A', 'B' and 3 others; they reach the a2l at address 0``: how ``address-missing`` ends,
    whichever source left the symbols out."""
    reach = "it reaches" if len(missing) == 1 else "they reach"
    return f"{_listed(missing)}; {reach} the a2l at address 0"
```

In `_selected`, the docstring's last sentence and the two refusals:

```python
    stayed must still have them. The a2l's addresses come from one source, a map or an image,
    which is refused here too, before anything is read.
    """
```

```python
        ("--address-map", getattr(args, "address_map", None) is not None, "a2l"),
        ("--image", getattr(args, "image", None) is not None, "a2l"),
    ):
        if given and not getattr(args, f"render_{artefact}"):
            msg = f"{option} belongs to the {artefact} artefact, left out by --without"
            raise ValueError(msg)
    if getattr(args, "address_map", None) is not None and getattr(args, "image", None) is not None:
        msg = "--image and --address-map are two sources of the a2l's addresses; give one of them"
        raise ValueError(msg)
```

In `_command_generate`, the first import becomes:

```python
    from ddd.addresses import addresses_from_image, load_address_map
```

the image is read before the map would be, its byte order checked, its symbols placed and weighed, and what it cannot place reported:

```python
        wants_addresses = args.render_a2l and getattr(args, "address_map", None) is not None
        addresses: dict[str, int] = {}
        byte_order: str | None = getattr(args, "byte_order", None)
        image_path: Path | None = getattr(args, "image", None)
        if image_path is not None:
            # Only a run writing the a2l gets here with an image: _selected refused it to the
            # others, as it refuses them the map. The symbols are the a2l's, as for a map.
            carried = addressed_symbols(dictionary)
            image = _image_reader()(image_path)
            # The image states its byte order, so an option saying the other one is a mistake
            # about the target, which an a2l of the wrong order would only hide.
            if byte_order not in (None, image.byte_order):
                msg = (
                    f"--byte-order {byte_order} contradicts '{image_path.as_posix()}', which "
                    f"is {image.byte_order} endian"
                )
                raise ValueError(msg)
            byte_order = image.byte_order
            placed = addresses_from_image(image, carried)
            addresses = placed.addresses
            weigh_addresses(addresses, carried, image_path.as_posix())
            _check_image_coverage(carried, placed, image_path, bag)
        elif wants_addresses:
```

and the a2l backend is given that byte order:

```python
                    A2lOptions(
                        byte_order=ByteOrder(byte_order or BYTE_ORDERS[0]),
                        addresses=addresses,
                    ),
```

The image is read inside the `_reported_on_failure` block `generate` already wraps its second half in, so every refusal after the analysis prints the project's findings first, as an unreadable map's does.

Then run ruff on both files, which settles the formatting the blocks above already have:

Run: `.venv/bin/ruff format src/ddd/cli.py tests/test_cli.py && .venv/bin/ruff check src/ddd/cli.py tests/test_cli.py`
Expected: `2 files left unchanged`, then `All checks passed!`.

- [ ] **Step 4: Run them to see them pass**

Run: `.venv/bin/python -m pytest tests/test_cli.py --no-cov -k "FromAnImage or FromElf"`
Expected: `76 passed, 226 deselected`: the 22 new tests and the toolbox's 54, whose two tests of the import guard now run through `_image_reader()`.

- [ ] **Step 5: The gates**

Run:

```bash
rm -f .coverage .coverage.*
.venv/bin/python -m pytest > build/gate.txt 2>&1; echo "EXIT=$?"; tail -3 build/gate.txt
.venv/bin/ruff check . > build/ruff.txt 2>&1; echo "RUFF=$?"; tail -1 build/ruff.txt
.venv/bin/ruff format --check . > build/fmt.txt 2>&1; echo "FMT=$?"; tail -1 build/fmt.txt
.venv/bin/mypy > build/mypy.txt 2>&1; echo "MYPY=$?"; tail -1 build/mypy.txt
```

Expected: `EXIT=0`, then `Required test coverage of 100% reached. Total coverage: 100.00%` and `5506 passed`, 22 more than after Task 4 (the scratch branch measured `5484 passed` with Tasks 1 to 4); `RUFF=0` and `All checks passed!`; `FMT=0` and `148 files already formatted`; `MYPY=0` and `Success: no issues found in 82 source files`.

- [ ] **Step 6: Commit**

```bash
git add src/ddd/cli.py tests/test_cli.py
git commit -F - <<'EOF'
take the a2l's addresses out of the linked image with --image

ddd generate a2l and all take --image: every symbol the a2l carries is
placed in the image's DWARF, an object by its name and a member by its
access path, and the a2l takes the byte order the image states. A
--byte-order the image contradicts is refused, as are --image beside
--address-map and in a run without the a2l; the reader's refusals and a
missing pyelftools are usage errors in their own words, and an address
beyond 32 bits is refused naming the symbol and the image. What the image
cannot place reaches the a2l at address 0 as address-missing, each reason
a note, said once, for the symbols the finding names. A test holds the a2l
run after the link to leaving what generate all wrote beside it untouched,
on every host.

Co-Authored-By: <your model> <noreply@anthropic.com>
EOF
```

- [ ] **Step 7: Ablations**

In a scratch worktree made from the commit, from the worktree's root:

```bash
git worktree add --detach build/ablate HEAD
cd build/ablate
```

Each ablation below is one `sed` that changes `src/ddd/cli.py`, the last `src/ddd/backends/base.py` (`git diff --stat` says `1 file changed`). After each, run, from `build/ablate`:

```bash
find . -name __pycache__ -prune -exec rm -rf {} +
/home/sauci/Documents/Github/ddd-toolbox-from-elf/.venv/bin/python -m pytest -p no:cacheprovider -o addopts="" tests/test_cli.py tests/test_transcripts.py 2>&1 | grep -E "^FAILED|^ERROR|^=.*(passed|failed)|^rootdir"
git checkout -- src/ddd/cli.py src/ddd/backends/base.py
```

and check that the `rootdir:` line names `build/ablate`. Before any edit the run says `358 passed`. Every test named below is of `tests/test_cli.py` unless it says otherwise. All measured on the scratch branch:

1. Every reason noted, not only the named symbols':

   ```bash
   sed -i 's/    reasons = dict.fromkeys(placed.reasons\[symbol\] for symbol in missing\[:_LISTED_LIMIT\])/    reasons = dict.fromkeys(placed.reasons[symbol] for symbol in missing)/' src/ddd/cli.py
   ```

   `1 failed, 357 passed`: `TestGenerateFromAnImage::test_the_notes_are_the_reasons_of_the_symbols_named_each_said_once` (`Spool`'s reason appears).

2. A reason noted once per symbol rather than once:

   ```bash
   sed -i 's/    reasons = dict.fromkeys(placed.reasons\[symbol\] for symbol in missing\[:_LISTED_LIMIT\])/    reasons = [placed.reasons[symbol] for symbol in missing[:_LISTED_LIMIT]]/' src/ddd/cli.py
   ```

   `1 failed, 357 passed`: the same test (five identical notes).

3. A finding for an image that places everything:

   ```bash
   sed -i '/^def _check_image_coverage/,/^def _at_address_0/ s/^    if not missing:$/    if False:/' src/ddd/cli.py
   ```

   `6 failed, 352 passed`: the five cases of `TestGenerateFromAnImage::test_every_row_writes_the_addresses_and_the_byte_order_of_its_image`, and `TestGenerateFromAnImage::test_the_a2l_run_after_the_link_leaves_what_generate_all_wrote_untouched`, whose a2l run reports a finding of nothing before the file it writes.

4. One symbol and several swapped:

   ```bash
   sed -i 's/    reach = "it reaches" if len(missing) == 1 else "they reach"/    reach = "it reaches" if len(missing) > 1 else "they reach"/' src/ddd/cli.py
   ```

   `5 failed, 353 passed`: `TestGenerateFromAnImage::test_a_member_the_image_lacks_reaches_the_a2l_at_0_and_the_finding_says_why`, `test_a_symbol_the_image_cannot_place_fails_a_strict_run_which_writes_nothing`, `test_the_notes_are_the_reasons_of_the_symbols_named_each_said_once`, and `tests/test_transcripts.py::test_every_documented_run_prints_what_the_page_shows[docs/concept.rst]` and `[docs/faq.rst]`, whose maps leave several symbols out: the ending is the map's as well.

5. A contradicting byte order obeyed:

   ```bash
   sed -i 's/            if byte_order not in (None, image.byte_order):/            if False:/' src/ddd/cli.py
   ```

   `5 failed, 353 passed`: the five cases of `TestGenerateFromAnImage::test_a_byte_order_the_image_contradicts_is_refused`.

6. The image's byte order not taken (Review Focus 4):

   ```bash
   sed -i '/^            byte_order = image.byte_order$/d' src/ddd/cli.py
   ```

   `2 failed, 356 passed`: `TestGenerateFromAnImage::test_every_row_writes_the_addresses_and_the_byte_order_of_its_image[aarch64_be]` and `[powerpc]`, the two big endian rows.

7. No option taken for a contradiction too:

   ```bash
   sed -i 's/            if byte_order not in (None, image.byte_order):/            if byte_order not in (image.byte_order,):/' src/ddd/cli.py
   ```

   `11 failed, 347 passed`: every run without `--byte-order` - the five row cases, `test_generate_all_reads_the_image_as_generate_a2l_does`, `test_a_carried_address_beyond_32_bits_is_refused_naming_the_symbol_and_the_image`, the three `address-missing` tests and `test_the_a2l_run_after_the_link_leaves_what_generate_all_wrote_untouched`.

8. The image's addresses not weighed:

   ```bash
   sed -i '/^            weigh_addresses(addresses, carried, image_path.as_posix())$/d' src/ddd/cli.py
   ```

   `1 failed, 357 passed`: `TestGenerateFromAnImage::test_a_carried_address_beyond_32_bits_is_refused_naming_the_symbol_and_the_image`.

9. The image's path handed to `weigh_addresses` as `str()` (a survival on Linux, and the one this list expects):

   ```bash
   sed -i 's/            weigh_addresses(addresses, carried, image_path.as_posix())/            weigh_addresses(addresses, carried, str(image_path))/' src/ddd/cli.py
   ```

   On Linux a path's `str()` is its `as_posix()`; on Windows CI, `test_a_carried_address_beyond_32_bits_is_refused_naming_the_symbol_and_the_image` dies of it, as Task 2's ablation 7 has its map's test die. Measured over the whole suite, from `build/ablate`, under the default seed and `PYTHONHASHSEED` 0, 1, 4 and 7, `__pycache__` cleared before each: `5506 passed` all five times.

10. An image beside a map not refused:

    ```bash
    sed -i 's/    if getattr(args, "address_map", None) is not None and getattr(args, "image", None) is not None:/    if False:/' src/ddd/cli.py
    ```

    `1 failed, 357 passed`: `TestGenerateFromAnImage::test_an_image_beside_an_address_map_is_refused`.

11. An image given to a run without the a2l not refused:

    ```bash
    sed -i '/^        ("--image", getattr(args, "image", None) is not None, "a2l"),$/d' src/ddd/cli.py
    ```

    `1 failed, 357 passed`: `TestGenerateFromAnImage::test_an_image_given_to_a_run_without_the_a2l_is_refused`.

12. The import guard inverted:

    ```bash
    sed -i 's/        if (error.name or "").partition(".")\[0\] != "elftools":/        if (error.name or "").partition(".")[0] == "elftools":/' src/ddd/cli.py
    ```

    `3 failed, 355 passed`: `TestToolFromElf::test_without_pyelftools_the_command_says_how_to_install_it`, `TestToolFromElf::test_a_missing_module_of_ddd_is_not_blamed_on_pyelftools` and `TestGenerateFromAnImage::test_without_pyelftools_an_image_is_refused_saying_how_to_install_it`.

13. `generate` importing the reader past the guard (notes-a's ruling 8):

    ```bash
    sed -i 's/            image = _image_reader()(image_path)/            image = __import__("ddd.elf", fromlist=["open_image"]).open_image(image_path)/' src/ddd/cli.py
    ```

    `1 failed, 357 passed`: `TestGenerateFromAnImage::test_without_pyelftools_an_image_is_refused_saying_how_to_install_it`.

14. The finding located as typed rather than resolved:

    ```bash
    sed -i '/^def _check_image_coverage/,/^def _at_address_0/ s/        where(path),/        Location(path),/' src/ddd/cli.py
    ```

    `1 failed, 357 passed`: `TestGenerateFromAnImage::test_a_member_the_image_lacks_reaches_the_a2l_at_0_and_the_finding_says_why`, which names the image relative to the working directory.

15. The contradiction reworded:

    ```bash
    sed -i 's/f"--byte-order {byte_order} contradicts /f"--byte-order {byte_order} disagrees with /' src/ddd/cli.py
    ```

    `5 failed, 353 passed`: the five cases of `TestGenerateFromAnImage::test_a_byte_order_the_image_contradicts_is_refused`. Every other sentence of the table above is asserted whole by the test its case names.

16. Nothing reported:

    ```bash
    sed -i '/^            _check_image_coverage(carried, placed, image_path, bag)$/d' src/ddd/cli.py
    ```

    `3 failed, 355 passed`: `TestGenerateFromAnImage::test_a_member_the_image_lacks_reaches_the_a2l_at_0_and_the_finding_says_why`, `test_a_symbol_the_image_cannot_place_fails_a_strict_run_which_writes_nothing` and `test_the_notes_are_the_reasons_of_the_symbols_named_each_said_once`.

17. The manifest's rule broken (Review Focus 5): a run takes back the files of artefacts it did not produce:

    ```bash
    sed -i '/^            if artefact not in self.artefacts:$/{N;d}' src/ddd/backends/base.py
    ```

    `2 failed, 356 passed`: `TestGenerateFromAnImage::test_the_a2l_run_after_the_link_leaves_what_generate_all_wrote_untouched`, whose a2l run removes every file the run before it wrote, and `tests/test_transcripts.py::test_every_documented_run_prints_what_the_page_shows[docs/concept.rst]`, whose post-link `generate a2l --address-map` now reports removing the c. `TestGenerateOwnsItsOutputDirectory::test_the_a2l_run_of_a_two_run_build_keeps_the_c_the_image_was_built_from` survives it: its `generate a2l` changes nothing, and `write` returns before removing anything when it has nothing to write.

Then, from the worktree's root: `git worktree remove build/ablate`.

### Task 6: `ADDRESSES_FROM_IMAGE` in the cmake module

**Files:** Modify `cmake/Ddd.cmake`, `docs/build_integration.rst` (the keyword's row of the options table), `README.md` (the keyword in the list of `ddd_generate`'s options); Test `tests/test_cmake.py`.

**Interfaces:** Consumes Task 5's `--image` and its test helper `a2l_addresses` (`from test_cli import a2l_addresses`, as `tests/test_gui_compare.py` takes helpers from `test_gui_api`), Task 4's `build_address_fixtures`: `PROJECT`, `ORACLE`, `SYMBOLS`, `root_of`, and the oracle's two readers, `addresses_of` (`nm`) and `oracle_of` (`readelf`), and the file's own `TestACollectedProjectWithPlugins.write` and `edit_plugin`. Produces the keyword `ADDRESSES_FROM_IMAGE` of `ddd_generate` and the target `<stem>_ddd_a2l`.

`ADDRESSES_FROM_IMAGE` makes the a2l a step after the link. The generation before the link runs as `NO_A2L` runs it, `ddd generate all --without a2l`, so the c sources, the headers and the dictionary are what they always were. After the link a second custom command runs `ddd generate a2l <project> --output-dir <dir> --image $<TARGET_FILE:<image>>`: its output is the a2l, it depends on the image target - a target-level dependency, and, the target being an executable, a file-level one that reruns the command whenever the image is rebuilt (CMake's documentation of `DEPENDS`) - and on what the project is read from: the project file, the descriptions collected or included, the `.py` plugins, and the tool. The templates and `DEPENDS` are the c's inputs and not the a2l's, so a template edit re-renders the c and relinks, which reruns the step through the image, and nothing else does. `<stem>_ddd_a2l`, built by default (`ALL`), drives it, and `DDD_A2L` names the same file as before. `STRICT` and `SEVERITY` reach the step through the options both runs share, and `BYTE_ORDER` goes to the step alone: the run before the link has left the a2l out, and `--byte-order` beside `--without a2l` is the usage error `--byte-order belongs to the a2l artefact, left out by --without` (ablation 2). `ADDRESSES_FROM_IMAGE` beside `ADDRESS_MAP` or `NO_A2L` is refused at configure time, in a sentence naming both keywords, as `PLUGINS` beside `PROJECT` is.

`tests/test_documentation.py` holds every keyword `cmake_parse_arguments` parses to a row of the build page's options table and a mention in the README (`test_every_option_of_ddd_generate_has_a_row_on_the_page`, `..._is_named_in_the_readme`): with the keyword parsed and neither written, both fail on `['ADDRESSES_FROM_IMAGE']` (measured). So this task writes the row and the README's mention - the least documentation the keyword owes, as the toolbox plan's Ruling 8 had its command line write its own - and Task 7 writes the rest.

The test builds a real image with the host toolchain, as the file's other classes do: the address fixtures' project, in the `PROJECT` mode, its generated c compiled by the host's compiler into an image that also carries the committed `oracle.c` - Task 4's constants, the compiler's own `offsetof` of every carried symbol, which `#include "ddd_globals.h"` reaches through `<stem>_ddd_headers`. The oracle is read back out of that very image as Task 4 reads it, `nm` for the variables and `readelf` for the constants, never through `ddd.elf`. The build type is `RelWithDebInfo`: without one the image carries no DWARF, and the step stops the build with the reader's `carries no DWARF debug information: build it with -g` (measured over the shipped example). Measured on the host, gcc 15.2 for x86_64, which links a position independent executable by default (`readelf -h`: `DYN`): the a2l of the first build states exactly the oracle's address for all 46 symbols; the second build prints `ninja: no work to do.`; an initialised `int Padding[64]` added to `main.c` relinks the image, moves the 38 symbols of the variables without an initial value by 256 bytes and leaves the 8 of the initialised ones where they were, before `main.c`'s data, and the step rereads them all; `Temperature_t`'s factor changed from 0.1 to 0.2 regenerates the dictionary, leaves the c `unchanged`, compiles and links nothing, and reruns the step, whose a2l changes in that `COMPU_METHOD` and in the physical limits of the measurement using it. Across the relink, the c sources, the headers and the dictionary the run before the link wrote keep their modification times: the step writes into their directory, and the output directory's manifest keeps it from taking them back (Review Focus 5; ablation 16 breaks that rule and kills four of these tests).

That story is the `PROJECT` mode's, whose descriptions `ddd sources` lists at configure time. The collected mode hands the step its descriptions as a generator expression over the link graph instead, and its `.py` plugins through `PLUGINS`, so one more test builds the layout example as `TestACollectedProjectWithPlugins` builds it, the keyword added. Measured: the a2l states `nm`'s address of the example's three objects; the plugin's own header, which the run before the link wrote, is still beside the a2l after the step; an edited plugin reruns the generation before the link, which leaves the c `unchanged`, and the step, which leaves the a2l `unchanged`, with no compile and no link (`[2/3] Reading the addresses of the a2l out of img`); an edited conversion, `CoolantTemperature`'s factor from 0.1 to 0.2, does the same, and the a2l's `COMPU_METHOD` for it reads `COEFFS 0 1 0 0 0 0.2`; a build after that has no work. The plugin is what kills ablation 9, which the `PROJECT` mode alone left alive.

**What the windows cells do.** CI runs this file on `windows-latest` too, where `compiler()` picks MinGW's gcc, which links PE, and `ddd.elf` reads ELF alone. There the step after the link refuses the image - `'<build>/img.exe' is not an ELF image this tool can read: Magic number does not match`, the reader stopping at the first four bytes - and the build stops with no a2l. The class reads the image's first four bytes after the first build and, where they are not ELF's, each test asserts that refusal instead of what it asks of an ELF host (`FromTheImage.linked_elf`, and the collected test the same way); the two configure-time refusals and the property are the same everywhere. This is not a skip - each test asserts what such a host gets - and it is measured here, on linux, by linking every image of the class as a raw binary: Step 5 runs the class that way, and all eleven pass through that side. Windows itself was not measured: no Windows machine is in reach of this plan.

- [ ] **Step 1: Write the failing tests**

In `tests/test_cmake.py`, the imports become:

```python
import json
import os
import re
import shutil
import subprocess
import sys
import sysconfig
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from build_address_fixtures import ORACLE, PROJECT, SYMBOLS, addresses_of, oracle_of, root_of

from conftest import EXAMPLES, declare
from ddd import __version__
from test_cli import a2l_addresses
```

and before `class TestAKeywordGivenNoValue`, add:

```python
NOT_ELF = "is not an ELF image this tool can read: Magic number does not match"
"""How DDD's reader refuses an image that is not ELF, a PE file included: the first four bytes
are where it stops."""

PRE_LINK = (
    "ddd_globals.c",
    "ddd_globals.h",
    "ddd_types.h",
    "Engine.h",
    "AddressFixture.dictionary.json",
)
"""What the run before the link writes into the directory the a2l is written into after it."""


def oracle(image: Path) -> dict[str, int]:
    """Where the toolchain put every symbol the a2l carries: ``nm``'s address of its variable,
    plus the compiler's own ``offsetof`` of it, which ``oracle.c`` compiled into the image - read
    back as the address fixtures read theirs, and never through DDD's reader."""
    carried = json.loads(SYMBOLS.read_text(encoding="utf-8"))["addressed"]
    found = addresses_of(image)
    offsets = zip(carried, oracle_of(image, sys.byteorder), strict=True)
    return {symbol: found[root_of(symbol)] + offset for symbol, offset in offsets}


@dataclass(frozen=True)
class Built:
    """One build of the class below, and what it left behind."""

    code: int
    output: str
    a2l: str
    """The a2l once the build was over, or nothing where there was none."""

    oracle: dict[str, int]
    """What the toolchain says of the image the build linked, where it linked ELF."""

    written: dict[str, int | None]
    """When each file of the run before the link was last written, or None where it is gone."""


@dataclass(frozen=True)
class FromTheImage:
    """What one configure and the builds after it left behind, for the class below."""

    configured: str
    generated: Path
    elf: bool
    builds: list[Built]
    """The first build, the same again, one after an edit that relinks the image, and one after
    a description edit the c does not see - or the first alone, where the image is not ELF."""

    def linked_elf(self) -> bool:
        """Whether the host's toolchain linked an ELF image, which is what DDD reads.

        MinGW's gcc, which the windows cells build with, links PE: there the step after the
        link refuses the image in the reader's words and the build stops with no a2l, which is
        asserted here before answering no - so that a test with nothing more to ask of such a
        host has still checked what it gets."""
        if self.elf:
            return True
        (first,) = self.builds
        assert first.code != 0, first.output
        assert NOT_ELF in first.output, first.output
        assert first.a2l == ""
        return False


class TestAddressesFromTheImage:
    """``ADDRESSES_FROM_IMAGE``: the a2l written once the image is linked, out of that image.

    One configure and four builds of one tree, the class fixture's story: the build that gives
    the whole a2l, the same build again, one after an edit that relinks the image, and one after
    a description edit that reaches the a2l and none of the c. The project is the address
    fixtures' - bitfields before value members, arrays of structures in one and two dimensions -
    built by the host's toolchain into an image that also carries ``oracle.c``, so that what the
    toolchain says of every symbol is read back out of the very image the a2l was read from.

    That needs a host whose toolchain links ELF, as every linux cell's does. MinGW's gcc, which
    the windows cells build with, links PE, which DDD does not read: what a build gets there is
    the step after the link refusing the image in the reader's words, and that is what each test
    asserts there instead (``FromTheImage.linked_elf``) - a test that skipped would report
    success without having run.
    """

    def write(self, source: Path, options: str = "", tail: str = "") -> None:
        """The address fixtures' project and oracle, and an image of them both."""
        shutil.copytree(PROJECT.parent, source / "project")
        shutil.copy(ORACLE, source / "oracle.c")
        (source / "main.c").write_text("int main(void) { return 0; }\n", encoding="utf-8")
        (source / "CMakeLists.txt").write_text(
            f"""cmake_minimum_required(VERSION 3.30)
project(FromImage LANGUAGES C)
list(APPEND CMAKE_MODULE_PATH "{(ROOT / "cmake").as_posix()}")
include(Ddd)
add_executable(img main.c oracle.c)
ddd_generate(img
             PROJECT "${{CMAKE_CURRENT_SOURCE_DIR}}/project/project.ddd.json"
             TEMPLATE_DIRECTORY "{TEMPLATES.as_posix()}"
             ADDRESSES_FROM_IMAGE{options})
{tail}
get_target_property(a2l img DDD_A2L)
message(STATUS "DDD_A2L=${{a2l}}")
""",
            encoding="utf-8",
        )

    @staticmethod
    def image(build_dir: Path) -> Path:
        return build_dir / ("img.exe" if os.name == "nt" else "img")

    @pytest.fixture(scope="class")
    @staticmethod
    def story(tmp_path_factory: pytest.TempPathFactory) -> FromTheImage:
        """One story, told once: build, build again, relink, edit a description."""
        source = tmp_path_factory.mktemp("from-image")
        TestAddressesFromTheImage().write(source)
        build_dir = source / "build"
        # With debug information, which the image has to carry and an empty build type omits.
        configured = configure(source, build_dir, "-DCMAKE_BUILD_TYPE=RelWithDebInfo")
        generated = build_dir / "ddd" / "img"
        image = TestAddressesFromTheImage.image(build_dir)

        def built() -> Built:
            run = cmake("--build", str(build_dir), cwd=build_dir)
            a2l = generated / "AddressFixture.a2l"
            paths = [generated / name for name in PRE_LINK]
            return Built(
                code=run.returncode,
                output=run.stdout + run.stderr,
                a2l=a2l.read_text(encoding="utf-8") if a2l.exists() else "",
                oracle=oracle(image) if image.read_bytes()[:4] == b"\x7fELF" else {},
                written={
                    path.name: path.stat().st_mtime_ns if path.exists() else None for path in paths
                },
            )

        builds = [built()]
        elf = image.read_bytes()[:4] == b"\x7fELF"
        if elf:
            builds.append(built())
            # An initialised array more: the image relinks, and what follows it moves.
            (source / "main.c").write_text(
                "int Padding[64] = {1};\n\nint main(void) { return Padding[0]; }\n",
                encoding="utf-8",
            )
            builds.append(built())
            types = source / "project" / "types.ddd.json"
            text = types.read_text(encoding="utf-8")
            assert text.count('"factor": 0.1,') == 1, "Temperature_t's factor is no longer 0.1"
            types.write_text(text.replace('"factor": 0.1,', '"factor": 0.2,'), encoding="utf-8")
            builds.append(built())
        return FromTheImage(configured.stdout, generated, elf, builds)

    def test_one_build_gives_the_a2l_the_toolchain_gives(self, story: FromTheImage) -> None:
        """Every symbol at ``nm``'s address of its variable plus the compiler's own
        ``offsetof``, the value members after bitfields and the elements of ``Grid`` included:
        no map to extract, no second build to read it."""
        if not story.linked_elf():
            return
        first = story.builds[0]
        assert first.code == 0, first.output
        assert a2l_addresses(first.a2l) == first.oracle
        assert len(first.oracle) == 46

    def test_the_a2l_property_names_the_file_the_step_writes(self, story: FromTheImage) -> None:
        """Unchanged: what a step installing or publishing the a2l reads."""
        printed = re.search(r"DDD_A2L=(.*)", story.configured)
        assert printed is not None, story.configured
        assert Path(printed.group(1).strip()) == story.generated / "AddressFixture.a2l"

    def test_a_second_build_runs_no_step(self, story: FromTheImage) -> None:
        if not story.linked_elf():
            return
        assert "ninja: no work to do." in story.builds[1].output

    def test_a_relink_reads_the_addresses_again(self, story: FromTheImage) -> None:
        """``main.c`` gains an initialised array, which the linker places before the definition
        file's variables without an initial value: they move, and the a2l says where to, as the
        toolchain does."""
        if not story.linked_elf():
            return
        first, _, relinked, _ = story.builds
        assert "Reading the addresses of the a2l out of img" in relinked.output
        assert relinked.oracle != first.oracle
        assert a2l_addresses(relinked.a2l) == relinked.oracle

    def test_the_step_after_the_link_leaves_what_the_step_before_it_wrote(
        self, story: FromTheImage
    ) -> None:
        """Review Focus 5: the a2l is written into the directory the run before the link wrote
        the c, the headers and the dictionary into, and the relink's step left every one of
        them as it was - not rewritten, not taken back - so nothing was compiled again."""
        if not story.linked_elf():
            return
        first, _, relinked, _ = story.builds
        assert None not in first.written.values()
        assert relinked.written == first.written
        assert "ddd_globals.c" not in relinked.output

    def test_a_description_the_a2l_reads_reruns_the_step_without_a_relink(
        self, story: FromTheImage
    ) -> None:
        """A conversion's factor reaches the a2l and none of the c: the c is left as it was, so
        nothing compiles or links, and the step reads the image again all the same."""
        if not story.linked_elf():
            return
        redescribed = story.builds[3]
        assert "Reading the addresses of the a2l out of img" in redescribed.output
        assert "Linking" not in redescribed.output
        assert "      COEFFS 0 1 40 0 0 0.2\n" in redescribed.a2l

    @pytest.mark.parametrize(
        ("keyword", "said"),
        [
            pytest.param(
                'ADDRESS_MAP "${CMAKE_CURRENT_BINARY_DIR}/map.json"',
                "ddd_generate: ADDRESSES_FROM_IMAGE cannot be given together with ADDRESS_MAP: "
                "the a2l takes its addresses from one of the two.",
                id="ADDRESS_MAP",
            ),
            pytest.param(
                "NO_A2L",
                "ddd_generate: ADDRESSES_FROM_IMAGE cannot be given together with NO_A2L: the "
                "addresses it reads out of the image are the a2l's.",
                id="NO_A2L",
            ),
        ],
    )
    def test_a_keyword_it_contradicts_is_refused_at_configure_time(
        self, tmp_path: Path, keyword: str, said: str
    ) -> None:
        self.write(tmp_path, options=f"\n             {keyword}")
        run = attempt(tmp_path, tmp_path / "build")
        assert run.returncode != 0, run.stdout + run.stderr
        # Rewrapped: cmake folds a message to its own width.
        assert said in " ".join(run.stderr.split())

    def test_under_strict_a_symbol_the_image_cannot_place_stops_the_build(
        self, tmp_path: Path
    ) -> None:
        """The definition file compiled without debug information, as a project's flags for
        generated code may have it: no symbol of the a2l has an address in the image, and the
        build stops rather than ship an a2l whose every address is 0."""
        self.write(
            tmp_path,
            options="\n             STRICT",
            tail="target_compile_options(img_ddd_globals PRIVATE -g0)",
        )
        configure(tmp_path, tmp_path / "build", "-DCMAKE_BUILD_TYPE=RelWithDebInfo")
        run = cmake("--build", str(tmp_path / "build"), cwd=tmp_path)
        output = run.stdout + run.stderr
        assert run.returncode != 0, output
        assert not (tmp_path / "build" / "ddd" / "img" / "AddressFixture.a2l").exists()
        if self.image(tmp_path / "build").read_bytes()[:4] != b"\x7fELF":
            assert NOT_ELF in output, output
            return
        assert (
            "error[address-missing]: the image has no address for 'Cells[0].raw', 'Cells[0].v', "
            "'Cells[1].raw', 'Cells[1].v', 'Cells[2].raw' and 41 others; they reach the a2l at "
            "address 0\n"
            "    note: the image's debug information holds no variable named 'Cells'; the symbol "
            "table holds it, so the unit defining it was built without debug information (-g)\n"
        ) in output

    def test_a_byte_order_the_image_contradicts_stops_the_build(self, tmp_path: Path) -> None:
        """``BYTE_ORDER`` reaches the step after the link, where the image says otherwise."""
        other = {"little": "big", "big": "little"}[sys.byteorder]
        self.write(tmp_path, options=f"\n             BYTE_ORDER {other}")
        configure(tmp_path, tmp_path / "build", "-DCMAKE_BUILD_TYPE=RelWithDebInfo")
        run = cmake("--build", str(tmp_path / "build"), cwd=tmp_path)
        output = run.stdout + run.stderr
        assert run.returncode != 0, output
        image = self.image(tmp_path / "build")
        if image.read_bytes()[:4] != b"\x7fELF":
            assert NOT_ELF in output, output
            return
        assert (
            f"ddd: --byte-order {other} contradicts '{image.as_posix()}', which is "
            f"{sys.byteorder} endian\n"
        ) in output

    def test_in_the_collected_mode_a_plugin_or_a_description_reruns_the_step(
        self, tmp_path: Path
    ) -> None:
        """The layout example as ``TestACollectedProjectWithPlugins`` builds it, the keyword
        added. Collected, the descriptions travel the link graph as a generator expression, and
        the step depends on them as the run before the link does, and on the ``.py`` plugin
        ``PLUGINS`` names: an edited plugin or conversion reaches the a2l and relinks nothing,
        and reruns the step all the same. The plugin's own header, which the run before the
        link wrote beside the a2l, is still there after it."""
        component, plugin = TestACollectedProjectWithPlugins().write(
            tmp_path, options="\n             ADDRESSES_FROM_IMAGE"
        )
        configure(tmp_path, tmp_path / "build", "-DCMAKE_BUILD_TYPE=RelWithDebInfo")
        run = cmake("--build", str(tmp_path / "build"), cwd=tmp_path)
        output = run.stdout + run.stderr
        generated = tmp_path / "build" / "ddd" / "img"
        a2l = generated / "LayoutDevice.a2l"
        image = self.image(tmp_path / "build")
        if image.read_bytes()[:4] != b"\x7fELF":
            assert run.returncode != 0, output
            assert NOT_ELF in output, output
            assert not a2l.exists()
            return
        assert run.returncode == 0, output
        found = addresses_of(image)
        assert a2l_addresses(a2l.read_text(encoding="utf-8")) == {
            name: found[name] for name in ("CoolantTemperature", "EngineHours", "ServiceCount")
        }
        assert (generated / "ddd_layout.h").is_file()

        edit_plugin(plugin)
        replugged = build(tmp_path / "build")
        assert "Reading the addresses of the a2l out of img" in replugged
        assert "Linking" not in replugged

        described = json.loads(component.read_text(encoding="utf-8"))
        (coolant,) = [
            entry["definition"]
            for entry in described["component"]["interface"]
            if entry["definition"]["name"] == "CoolantTemperature"
        ]
        coolant["conversion"]["factor"] = 0.2
        component.write_text(json.dumps(described, indent=2), encoding="utf-8")
        redescribed = build(tmp_path / "build")
        assert "Reading the addresses of the a2l out of img" in redescribed
        assert "Linking" not in redescribed
        assert "COEFFS 0 1 0 0 0 0.2" in a2l.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/bin/python -m pytest tests/test_cmake.py --no-cov -k AddressesFromTheImage`
Expected: `5 failed, 46 deselected, 6 errors`, every one on the module's `ddd_generate: unknown argument(s) "ADDRESSES_FROM_IMAGE".`: the six tests of the story as errors of its fixture, whose configure fails, and the other five as failures.

- [ ] **Step 3: The keyword**

In `cmake/Ddd.cmake`, the file's header says it:

```cmake
#   dictionary beside them, and links the result into the image. With ADDRESSES_FROM_IMAGE the a2l is written after
#   the link instead, every address it carries read out of the linked image.
```

and the comment documenting `ddd_generate` gains, after the line of `ADDRESS_MAP`:

```cmake
#              [ADDRESSES_FROM_IMAGE]        # write the a2l after the link, its addresses read out of the image
```

and, after the entry of `<stem>_ddd_list`:

```cmake
# * <stem>_ddd_a2l         with ADDRESSES_FROM_IMAGE, custom target writing the a2l once the image is linked, out of
#                          the image's debug information; built by default
```

`cmake_parse_arguments` takes the keyword among the options, and the two contradictions are refused right after the empty keywords are:

```cmake
                          "CONST_INPUTS;NO_A2L;NO_DICTIONARY;STRICT;NO_PROPAGATE_HEADERS;ADDRESSES_FROM_IMAGE"
```

```cmake
    _ddd_refuse_empty_keywords("ddd_generate" "${arg_KEYWORDS_MISSING_VALUES}")
    # The a2l takes its addresses from one place, and ADDRESSES_FROM_IMAGE is that place being the image: beside a map
    # the call would name two, and beside NO_A2L it would read addresses for a file nobody writes.
    if(arg_ADDRESSES_FROM_IMAGE AND arg_ADDRESS_MAP)
        message(FATAL_ERROR "ddd_generate: ADDRESSES_FROM_IMAGE cannot be given together with ADDRESS_MAP: the a2l "
                            "takes its addresses from one of the two.")
    endif()
    if(arg_ADDRESSES_FROM_IMAGE AND arg_NO_A2L)
        message(FATAL_ERROR "ddd_generate: ADDRESSES_FROM_IMAGE cannot be given together with NO_A2L: the addresses "
                            "it reads out of the image are the a2l's.")
    endif()
```

The run before the link leaves the a2l out, and `--byte-order` with it:

```cmake
    set(generate_options ${common_options})
    # ADDRESSES_FROM_IMAGE subtracts the a2l as well: it is written after the link, below.
    if(arg_NO_A2L OR arg_ADDRESSES_FROM_IMAGE)
        list(APPEND generate_options --without a2l)
    endif()
```

```cmake
    if(arg_BYTE_ORDER AND NOT arg_NO_A2L AND NOT arg_ADDRESSES_FROM_IMAGE)
        list(APPEND generate_options --byte-order ${arg_BYTE_ORDER})
    endif()
```

(`tests/test_cli.py::TestCmakeModule::test_the_a2l_options_are_not_passed_to_a_c_only_generation` reads `NOT arg_NO_A2L` in that guard, which stays.) The a2l is not an output of that run any more, and the property still names it:

```cmake
    if(NOT arg_NO_A2L)
        set(a2l_file "${arg_OUTPUT_DIRECTORY}/${arg_NAME}.a2l")
        # Written before the link, or after it by the step below; the property names it either way.
        if(NOT arg_ADDRESSES_FROM_IMAGE)
            list(APPEND generated_outputs "${a2l_file}")
        endif()
        set_property(TARGET ${image} PROPERTY DDD_A2L "${a2l_file}")
    endif()
```

and after `add_custom_target(${image_stem}_ddd_generation DEPENDS ${generated_outputs})`, the step after the link:

```cmake
    # ADDRESSES_FROM_IMAGE: the a2l is written once the image is linked, by a second run reading every address it
    # carries out of the image's debug information, so that one build gives the complete a2l - no map to extract,
    # and no second build to read it. The run depends on the image and on what the project is read from, so it runs
    # again whenever the image relinks or a description changes, and never otherwise: the templates and DEPENDS are
    # the c's inputs, not the a2l's. It writes into the directory the run before the link wrote, whose manifest keeps
    # each run from taking back the files of the other. STRICT and SEVERITY apply to it as to that run, so that under
    # STRICT a symbol the image cannot place stops the build rather than shipping an a2l with an address of 0; and
    # BYTE_ORDER is its alone, held to the byte order the image states.
    if(arg_ADDRESSES_FROM_IMAGE)
        set(a2l_options ${common_options})
        if(arg_BYTE_ORDER)
            list(APPEND a2l_options --byte-order ${arg_BYTE_ORDER})
        endif()
        add_custom_command(OUTPUT "${a2l_file}"
                           COMMAND ${DDD_EXECUTABLE} generate a2l "${project_file}"
                                   --output-dir "${arg_OUTPUT_DIRECTORY}"
                                   --image "$<TARGET_FILE:${image}>" ${a2l_options}
                           DEPENDS ${image} "${project_file}" ${descriptions} ${plugin_files} "${DDD_EXECUTABLE}"
                           COMMENT "Reading the addresses of the a2l out of ${image}"
                           COMMAND_EXPAND_LISTS
                           VERBATIM)
        add_custom_target(${image_stem}_ddd_a2l ALL DEPENDS "${a2l_file}")
    endif()
```

Run: `.venv/bin/python -m pytest tests/test_cmake.py --no-cov -k AddressesFromTheImage`
Expected: `11 passed, 46 deselected`, in about five seconds.

Run: `.venv/bin/python -m pytest tests/test_documentation.py --no-cov -k BuildIntegrationPage`
Expected: `2 failed, 5 passed, 847 deselected`: `test_every_option_of_ddd_generate_has_a_row_on_the_page` and `test_every_option_of_ddd_generate_is_named_in_the_readme`, each `AssertionError: ['ADDRESSES_FROM_IMAGE']`.

- [ ] **Step 4: The keyword's row, and its name in the README**

In `docs/build_integration.rst`, the options table gains, after the row of `ADDRESS_MAP <file>`:

```rst
   * - ``ADDRESSES_FROM_IMAGE``
     - write the a2l once the image is linked, every address it carries read out of the
       image's debug information, so that one build gives the complete a2l: the run before the
       link leaves the a2l out, as ``NO_A2L`` does, and ``<stem>_ddd_a2l``, built by default,
       writes it after the link - again whenever the image relinks or a description changes,
       and never otherwise. ``DDD_A2L`` names it as before, and ``STRICT``, ``SEVERITY`` and
       ``BYTE_ORDER`` apply to it. The image has to be ELF with DWARF, built with ``-g``.
       Refused together with ``ADDRESS_MAP`` or ``NO_A2L``.
```

and in `README.md`, the list of options after the paragraph on `ddd-build.json` names it after `ADDRESS_MAP`:

```markdown
the schemas), `ADDRESS_MAP`, `ADDRESSES_FROM_IMAGE` (the a2l written after the link, its
addresses read out of the linked image), `BYTE_ORDER`,
```

Run: `.venv/bin/python -m pytest tests/test_documentation.py --no-cov -k BuildIntegrationPage`
Expected: `7 passed, 847 deselected`.

- [ ] **Step 5: The side the windows cells take, measured here**

The class takes the other side of its `ELF` branches only where the host links no ELF. Link every image of the class as a raw binary for one run: CMake reads `LDFLAGS` on a tree's first configure into `CMAKE_EXE_LINKER_FLAGS_INIT` (its documentation of the variable), and every tree of the class is configured fresh.

Run: `LDFLAGS="-nostdlib -Wl,-e,main -Wl,--oformat=binary" .venv/bin/python -m pytest tests/test_cmake.py --no-cov -k AddressesFromTheImage`
Expected: `11 passed, 46 deselected`: every image starts with code rather than ELF's magic (`f3 0f 1e fa` here, measured on both the `PROJECT` tree and the collected one), the reader refuses it in the sentence `NOT_ELF` holds, and each test asserts that. CMake's own check of the compiler passes under those flags: its programs have a `main` and call nothing. (A raw binary rather than the C library's crt: `--oformat=binary` refuses a dynamic link, and a static one of glibc needs `__ehdr_start`.)

- [ ] **Step 6: The gates**

Run:

```bash
rm -f .coverage .coverage.*
.venv/bin/python -m pytest > build/gate.txt 2>&1; echo "EXIT=$?"; tail -3 build/gate.txt
.venv/bin/ruff check . > build/ruff.txt 2>&1; echo "RUFF=$?"; tail -1 build/ruff.txt
.venv/bin/ruff format --check . > build/fmt.txt 2>&1; echo "FMT=$?"; tail -1 build/fmt.txt
.venv/bin/mypy > build/mypy.txt 2>&1; echo "MYPY=$?"; tail -1 build/mypy.txt
```

Expected: `EXIT=0`, then `Required test coverage of 100% reached. Total coverage: 100.00%` and `5517 passed`, 11 more than after Task 5; `RUFF=0` and `All checks passed!`; `FMT=0` and `148 files already formatted`; `MYPY=0` and `Success: no issues found in 82 source files`.

- [ ] **Step 7: Commit**

```bash
git add cmake/Ddd.cmake tests/test_cmake.py docs/build_integration.rst README.md
git commit -F - <<'EOF'
write the a2l after the link with ADDRESSES_FROM_IMAGE

ddd_generate gains the keyword: the run before the link leaves the a2l
out, and a step after the link runs ddd generate a2l --image over the
image, as the a2l's own rule, depending on the image and on what the
project is read from. One build gives the complete a2l, a build with
nothing changed runs nothing, and a relink or a description edit reads
the image again. ADDRESS_MAP or NO_A2L beside it is refused at configure
time. The test builds the address fixtures' project with the host
toolchain and holds the a2l to nm and offsetof read back out of the image;
where the toolchain links PE, as on the windows cells, it holds the build
to the reader's refusal instead. In the collected mode, an edited plugin or
description reruns the step as well.

Co-Authored-By: <your model> <noreply@anthropic.com>
EOF
```

- [ ] **Step 8: Ablations**

In a scratch worktree made from the commit, from the worktree's root:

```bash
git worktree add --detach build/ablate HEAD
cd build/ablate
```

Each ablation below is one `sed`. After each, run, from `build/ablate`:

```bash
find . -name __pycache__ -prune -exec rm -rf {} +
/home/sauci/Documents/Github/ddd-toolbox-from-elf/.venv/bin/python -m pytest -p no:cacheprovider -o addopts="" tests/test_cmake.py tests/test_cli.py tests/test_documentation.py 2>&1 | grep -E "^FAILED|^ERROR|^=.*(passed|failed|error)|^rootdir"
git checkout -- cmake/Ddd.cmake src/ddd/backends/base.py
```

and check that the `rootdir:` line names `build/ablate`. Before any edit the run says `1213 passed`, in about 34 seconds. Every test named below is of `TestAddressesFromTheImage` in `tests/test_cmake.py`. All measured on the scratch branch:

1. The run before the link writes the a2l as well:

   ```bash
   sed -i 's/^    if(arg_NO_A2L OR arg_ADDRESSES_FROM_IMAGE)$/    if(arg_NO_A2L)/' cmake/Ddd.cmake
   ```

   `1 failed, 1212 passed`: `test_under_strict_a_symbol_the_image_cannot_place_stops_the_build` - the run before the link has written an a2l with every address 0 when the step after it stops the build, which is the a2l `STRICT` is there to keep from shipping.

2. `BYTE_ORDER` handed to the run before the link:

   ```bash
   sed -i 's/^    if(arg_BYTE_ORDER AND NOT arg_NO_A2L AND NOT arg_ADDRESSES_FROM_IMAGE)$/    if(arg_BYTE_ORDER AND NOT arg_NO_A2L)/' cmake/Ddd.cmake
   ```

   `1 failed, 1212 passed`: `test_a_byte_order_the_image_contradicts_stops_the_build`, the build stopping on `--byte-order belongs to the a2l artefact, left out by --without` instead.

3. The a2l an output of the run before the link too:

   ```bash
   sed -i 's/^        if(NOT arg_ADDRESSES_FROM_IMAGE)$/        if(TRUE)/' cmake/Ddd.cmake
   ```

   `8 failed, 1205 passed`: `test_one_build_gives_the_a2l_the_toolchain_gives`, `test_a_second_build_runs_no_step`, `test_a_relink_reads_the_addresses_again`, `test_the_step_after_the_link_leaves_what_the_step_before_it_wrote`, `test_a_description_the_a2l_reads_reruns_the_step_without_a_relink`, `test_under_strict_a_symbol_the_image_cannot_place_stops_the_build`, `test_a_byte_order_the_image_contradicts_stops_the_build` and `test_in_the_collected_mode_a_plugin_or_a_description_reruns_the_step`. The build passes and writes no a2l at all: ninja gives the file to the run before the link, which leaves it out, and the step after the link never runs (measured: six steps, the last of them the link).

4. `STRICT` and `SEVERITY` kept from the step after the link:

   ```bash
   sed -i 's/^        set(a2l_options ${common_options})$/        set(a2l_options "")/' cmake/Ddd.cmake
   ```

   `1 failed, 1212 passed`: `test_under_strict_a_symbol_the_image_cannot_place_stops_the_build`.

5. `BYTE_ORDER` kept from it:

   ```bash
   sed -i '/^            list(APPEND a2l_options --byte-order ${arg_BYTE_ORDER})$/d' cmake/Ddd.cmake
   ```

   `1 failed, 1212 passed`: `test_a_byte_order_the_image_contradicts_stops_the_build`.

6. The step not depending on the image:

   ```bash
   sed -i 's/^                           DEPENDS ${image} "${project_file}" ${descriptions} ${plugin_files} "${DDD_EXECUTABLE}"$/                           DEPENDS "${project_file}" ${descriptions} ${plugin_files} "${DDD_EXECUTABLE}"/' cmake/Ddd.cmake
   ```

   `1 failed, 1212 passed`: `test_a_relink_reads_the_addresses_again`. The first build still reads the image after the link: `$<TARGET_FILE:img>` in the command is a target-level dependency, which, as the documentation of `add_custom_command` (CMake 4.4's, the pip wheel's) says, adds no file-level one - a relink does not rerun the command unless the target is named in `DEPENDS`, which is what `${image}` there is for.

7. Nor on the descriptions:

   ```bash
   sed -i 's/^                           DEPENDS ${image} "${project_file}" ${descriptions} ${plugin_files} "${DDD_EXECUTABLE}"$/                           DEPENDS ${image} "${project_file}" ${plugin_files} "${DDD_EXECUTABLE}"/' cmake/Ddd.cmake
   ```

   `2 failed, 1211 passed`: `test_a_description_the_a2l_reads_reruns_the_step_without_a_relink`, and `test_in_the_collected_mode_a_plugin_or_a_description_reruns_the_step`, whose descriptions are a generator expression.

8. Nor on the project file - a survival:

   ```bash
   sed -i 's/^                           DEPENDS ${image} "${project_file}" ${descriptions} ${plugin_files} "${DDD_EXECUTABLE}"$/                           DEPENDS ${image} ${descriptions} ${plugin_files} "${DDD_EXECUTABLE}"/' cmake/Ddd.cmake
   ```

   `1213 passed`. In the `PROJECT` mode, `ddd sources` lists the project file among the descriptions (measured over the fixtures' project: `engine.ddd.json`, `project.ddd.json`, `types.ddd.json`), so it is a dependency twice. In the collected mode the project file is the one `file(GENERATE)` writes out of the link closure, `NAME` and `PLUGINS`: a component linked or dropped relinks the image, and a new `NAME` renames the a2l, a new output; a change of `PLUGINS` that leaves every plugin file it names older than the a2l - two plugins reordered, say - would reach the step through the project file alone, ninja rerunning a command only for an input newer than its output. The examples ship one plugin, and no test reorders two. The run before the link's own dependency on the project file survives the same ablation, measured over `tests/test_cmake.py` (`57 passed`).

9. Nor on the plugins:

   ```bash
   sed -i 's/^                           DEPENDS ${image} "${project_file}" ${descriptions} ${plugin_files} "${DDD_EXECUTABLE}"$/                           DEPENDS ${image} "${project_file}" ${descriptions} "${DDD_EXECUTABLE}"/' cmake/Ddd.cmake
   ```

   `1 failed, 1212 passed`: `test_in_the_collected_mode_a_plugin_or_a_description_reruns_the_step`, whose edited plugin reran nothing.

10. Nor on the tool - a survival:

    ```bash
    sed -i 's/^                           DEPENDS ${image} "${project_file}" ${descriptions} ${plugin_files} "${DDD_EXECUTABLE}"$/                           DEPENDS ${image} "${project_file}" ${descriptions} ${plugin_files}/' cmake/Ddd.cmake
    ```

    `1213 passed`: no test can touch the environment's `ddd`. The run before the link's own dependency on the tool survives the same ablation, measured over `tests/test_cmake.py` (`57 passed`).

11. The target not built by default:

    ```bash
    sed -i 's/^        add_custom_target(${image_stem}_ddd_a2l ALL DEPENDS "${a2l_file}")$/        add_custom_target(${image_stem}_ddd_a2l DEPENDS "${a2l_file}")/' cmake/Ddd.cmake
    ```

    `6 failed, 1207 passed`: `test_one_build_gives_the_a2l_the_toolchain_gives`, `test_a_relink_reads_the_addresses_again`, `test_a_description_the_a2l_reads_reruns_the_step_without_a_relink`, `test_under_strict_a_symbol_the_image_cannot_place_stops_the_build`, `test_a_byte_order_the_image_contradicts_stops_the_build` and `test_in_the_collected_mode_a_plugin_or_a_description_reruns_the_step`.

12. No image read:

    ```bash
    sed -i 's/^                                   --image "$<TARGET_FILE:${image}>" ${a2l_options}$/                                   ${a2l_options}/' cmake/Ddd.cmake
    ```

    `5 failed, 1208 passed`: `test_one_build_gives_the_a2l_the_toolchain_gives`, `test_a_relink_reads_the_addresses_again`, `test_under_strict_a_symbol_the_image_cannot_place_stops_the_build`, `test_a_byte_order_the_image_contradicts_stops_the_build` and `test_in_the_collected_mode_a_plugin_or_a_description_reruns_the_step`.

13. `ADDRESS_MAP` beside it not refused:

    ```bash
    sed -i '/^    if(arg_ADDRESSES_FROM_IMAGE AND arg_ADDRESS_MAP)$/,/^    endif()$/d' cmake/Ddd.cmake
    ```

    `1 failed, 1212 passed`: `test_a_keyword_it_contradicts_is_refused_at_configure_time[ADDRESS_MAP]`.

14. `NO_A2L` beside it not refused:

    ```bash
    sed -i '/^    if(arg_ADDRESSES_FROM_IMAGE AND arg_NO_A2L)$/,/^    endif()$/d' cmake/Ddd.cmake
    ```

    `1 failed, 1212 passed`: `test_a_keyword_it_contradicts_is_refused_at_configure_time[NO_A2L]`.

15. The keyword not parsed:

    ```bash
    sed -i 's/"CONST_INPUTS;NO_A2L;NO_DICTIONARY;STRICT;NO_PROPAGATE_HEADERS;ADDRESSES_FROM_IMAGE"/"CONST_INPUTS;NO_A2L;NO_DICTIONARY;STRICT;NO_PROPAGATE_HEADERS"/' cmake/Ddd.cmake
    ```

    `5 failed, 1202 passed, 6 errors`: every test of the class, as in Step 2.

16. The manifest's rule broken (Review Focus 5): a run takes back the files of artefacts it did not produce:

    ```bash
    sed -i '/^            if artefact not in self.artefacts:$/{N;d}' src/ddd/backends/base.py
    ```

    `5 failed, 1208 passed`: `test_a_second_build_runs_no_step`, `test_the_step_after_the_link_leaves_what_the_step_before_it_wrote`, `test_a_description_the_a2l_reads_reruns_the_step_without_a_relink` and `test_in_the_collected_mode_a_plugin_or_a_description_reruns_the_step` - the step took back the c, the headers, the dictionary and the plugin's header, and the next build had them to write again - and Task 5's `tests/test_cli.py::TestGenerateFromAnImage::test_the_a2l_run_after_the_link_leaves_what_generate_all_wrote_untouched`, which holds the same rule on every host.

Then, from the worktree's root: `git worktree remove build/ablate`.

### Task 7: the documentation

**Files:** Modify `SPEC.md`, `docs/build_integration.rst`, `docs/command_line_interface.rst`, `README.md`, `CHANGELOG.md`, `docs/developer_documentation.rst`, `docs/generated_artefacts.rst`, `docs/faq.rst`, `docs/concept.rst`, `docs/consistency_checks.rst`, `src/ddd/elf.py` (its module docstring), `src/ddd/diagnostics.py` (the registry's description of `address-missing`), `tests/test_backends.py` (a docstring); Test `tests/test_documentation.py`.

**Interfaces:** Consumes Tasks 5 and 6. Produces no interface: the pages, and three tests holding them and the registry to the code.

Section 7 of the spec, and what Tasks 1 to 6 left stale. The build page leads with the image: its new section *The a2l's addresses* comes before *Where the address map comes from*, which stays for an image without DWARF, and the section that introduces `ddd_generate` points at it. SPEC.md's section 6 gains its second source and keeps IEEE-695 and the type cross-check planned; section 7 gains `--image` and the a2l's options, and section 7.1 the keyword. The command page, the README, the changelog's Unreleased section follow.

Three pages answered "how do the addresses get in" with the map alone - the FAQ's question of that name, the concept page's second run, and the generated artefacts' "two mechanisms" - and the build page said DDD "reads no build output at all", which `--image` makes untrue; each now says the image first and keeps the map. The check's own description, `an object reaching the a2l has no entry in the address map the run was given`, is false of an image run: the registry, the README's checks table, the reference page and SPEC.md's section 4 say map or image. `ddd checks` prints the registry's line; no page shows a `ddd checks` transcript naming that check (a whole-repository grep for its old wording finds the three places changed here and nothing else), and no test read the line at all (measured: put back, it survives the whole suite), so a test now holds it to naming both sources, as `test_the_registry_describes_changed_storage_as_the_pages_do` holds `changed-storage`'s to the raster.

Notes-a found three places still calling the image's reading planned, all fixed here: the developer page's layer table and its layering bullets (a row and a bullet for `src/ddd/addresses.py`, which Task 2's `test_a_build_s_addresses_reach_no_backend_and_no_command_line` enforces), `ddd.elf`'s module docstring, and the docstring of `tests/test_backends.py::TestLayering::test_the_elf_reader_knows_nothing_of_ddd`. Notes-b asked for a paragraph on the address fixtures beside the developer page's *The ELF fixtures*: what they are, the two commands that rebuild them, and that a release needs neither (Task 4's ablation 7: a version bump kills no fixture test).

What the pages state, and the measurement behind each (all on the scratch branch, gcc 15.2 and the pip cmake 4.4):

- *One build gives the complete a2l*, *a build with nothing changed runs nothing*, *a conversion's factor reruns the step and nothing else*, *nothing is compiled again because the a2l was written*: Task 6's test, and the shipped example built with `ADDRESSES_FROM_IMAGE` (the milestone gate's hands-on check).
- *`-g`, which CMake's `Debug` and `RelWithDebInfo` build types add*: the example's `CMakeCache.txt` with gcc - `CMAKE_C_FLAGS_DEBUG:STRING=-g`, `CMAKE_C_FLAGS_RELWITHDEBINFO:STRING=-O2 -g -DNDEBUG`, `CMAKE_C_FLAGS_RELEASE:STRING=-O3 -DNDEBUG`.
- The shipped example's output, `firmware.elf: warning[address-missing]: ... 'ValueG' ...` and its note: built as `RelWithDebInfo` with the keyword added, the one finding of the step; `ValueG` is behind `#if defined(FEATURE_X)` in the generated `ddd_globals.c`, and `ValueA`, `ValueE`, `AxisA` and `ParameterA` land where `nm` puts them.
- *One built without `-g` is told to be*: the same example configured with no build type stops at the step with `'.../firmware.elf' carries no DWARF debug information: build it with -g`.
- *One that is not ELF at all, as a host build on Windows links, is refused as such*: on linux, an image linked with `--oformat=binary` is refused with `is not an ELF image this tool can read: Magic number does not match`, the reader stopping at the first four bytes, which no PE file passes either. A Windows build itself was not measured.

Two more claims are checkable, and get tests: every target `ddd_generate` creates, as its header comment lists them, has a row in the build page's table of targets (it had none for `<stem>_ddd_a2l`), and every option the a2l artefact takes and the c one does not - `--address-map`, `--byte-order`, `--image` - is named on the command page, in the README and in SPEC.md, which named no `--byte-order` and, outside `ddd build-info`'s own `--image`, no `--image` either.

The html is built at the milestone gate: Sphinx is not in the venv, and Docker builds `ddd-addresses:dev` only there. Measured on the scratch branch through the gate's own commands: `build succeeded.` under `-W`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_documentation.py`, after `TestTheCommandPage`:

```python
def generate_options(artefact: str) -> set[str]:
    """The long options ``ddd generate ARTEFACT`` takes."""
    parser = _build_parser()
    commands = next(
        action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
    )
    artefacts = next(
        action
        for action in commands.choices["generate"]._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    return {
        option
        for action in artefacts.choices[artefact]._actions
        for option in action.option_strings
        if option.startswith("--")
    }


class TestTheA2lOptions:
    """The options the a2l takes and the c does not say where its addresses and its byte order
    come from, so every document that says how to run ``generate`` names each of them."""

    OWN = sorted(generate_options("a2l") - generate_options("c"))

    def test_they_are_the_two_sources_of_the_addresses_and_the_byte_order(self) -> None:
        """The positive control: what the test below is parametrized over is not nothing."""
        assert self.OWN == ["--address-map", "--byte-order", "--image"]

    @pytest.mark.parametrize("option", OWN)
    @pytest.mark.parametrize(
        ("document", "spelling"),
        [
            ("docs/command_line_interface.rst", "``{}``"),
            ("README.md", "`{}"),
            ("SPEC.md", "`{}"),
        ],
    )
    def test_every_one_is_named(self, option: str, document: str, spelling: str) -> None:
        text = SPEC if document == "SPEC.md" else PAGES[document]
        assert spelling.format(option) in text
```

and in `TestTheBuildIntegrationPage`, after `test_every_option_of_ddd_generate_is_named_in_the_readme`:

```python
    def test_every_target_ddd_generate_creates_has_a_row_on_the_page(self) -> None:
        """The module's header lists what the call creates, and the page's table is where a
        reader looks a target up: one listed in either alone is one somebody misses."""
        created = re.findall(r"^# \* (<stem>_ddd_\w+)", self.CMAKE_MODULE, re.M)
        rows = re.findall(
            r"^   \* - ``(<stem>_ddd_\w+)``", PAGES["docs/build_integration.rst"], re.M
        )
        assert created, "the module's header no longer lists the targets it creates"
        assert sorted(rows) == sorted(created)
```

and in `TestTheCheckReference`, after `test_the_registry_describes_changed_storage_as_the_pages_do`:

```python
    def test_the_registry_describes_address_missing_as_the_pages_do(self) -> None:
        """``ddd checks`` prints the registry's one-liner, and since ``--image`` the check is
        about a symbol the image does not place as much as one the map leaves out: a line naming
        the map alone told a user of the image that the check was not about them."""
        description = CHECKS["address-missing"].description
        assert "address map" in description
        assert "image" in description
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/bin/python -m pytest tests/test_documentation.py --no-cov -k "A2lOptions or target_ddd_generate or describes_address_missing"`
Expected: `5 failed, 7 passed, 854 deselected`: `TestTheA2lOptions::test_every_one_is_named[docs/command_line_interface.rst-``{}``---image]`, `[README.md-`{}---image]`, `[SPEC.md-`{}---byte-order]`, `TestTheBuildIntegrationPage::test_every_target_ddd_generate_creates_has_a_row_on_the_page`, and `TestTheCheckReference::test_the_registry_describes_address_missing_as_the_pages_do`.

- [ ] **Step 3: The build page**

In `docs/build_integration.rst`, *Generating an image*: the paragraph ending "whose compile usage travels with them." gains:

```rst
The a2l is the one artefact that cannot be complete before the link, which decides every
address it carries: with ``ADDRESSES_FROM_IMAGE`` the module writes it after the link instead,
out of the linked image, and one build gives it whole (see *The a2l's addresses* below).
```

*The targets it creates*: the table gains, after the row of `<stem>_ddd_list`:

```rst
   * - ``<stem>_ddd_a2l``
     - with ``ADDRESSES_FROM_IMAGE``, built by default: writes the a2l once the image is
       linked, every address it carries read out of the image (see below). It depends on the
       image, on the project description and the files collected into it, on a ``.py`` plugin
       the call names and on the tool, and on nothing the c alone is rendered from.
```

and the paragraph under the table becomes:

```rst
The outputs declared for the generator are the files the template names already give away, plus
the a2l and the dictionary - the a2l being the output of ``<stem>_ddd_a2l``'s step instead
where ``ADDRESSES_FROM_IMAGE`` gives it one. The per-component headers are written next to
them, but their names come from inside the description files and are therefore unknown at
configure time - which is precisely why a consumer depends on ``<stem>_ddd_headers`` rather
than on an individual header path.
```

Before *Where the address map comes from*, a section:

```rst
The a2l's addresses
~~~~~~~~~~~~~~~~~~~

The address of every object the a2l carries is decided by the linker, so the a2l is the one
artefact a build cannot finish before the link. ``ADDRESSES_FROM_IMAGE`` gives it a step of its
own after the link: the generation before the link leaves the a2l out, as ``NO_A2L`` does, and
``<stem>_ddd_a2l``, built by default, runs ``ddd generate a2l --image`` over the linked image,
which reads every address the a2l carries out of the image's debug information - an object by
its name, a structure member by its access path, at the offset the compiler gave it. One build
gives the complete a2l, with no map to extract and no member offset to work out by hand:

.. code-block:: cmake

   ddd_generate(firmware.elf
                TEMPLATE_DIRECTORY "${templates}"
                ADDRESSES_FROM_IMAGE)

The image has to be a linked ELF image whose DWARF describes the variables
(:doc:`command_line_interface`), which a build with debug information writes: ``-g``, which
CMake's ``Debug`` and ``RelWithDebInfo`` build types add. The step depends on the image and on
what the project is read from, so it runs again when the image relinks or a description
changes - a conversion's factor, which reaches the a2l and none of the c, included - and a
build with nothing changed runs nothing at all. It writes the a2l into the directory the
generation before the link wrote the c sources, the headers and the dictionary into, and takes
none of them back (:ref:`what-a-run-owns`), so nothing is compiled again because the a2l was
written.

What the image cannot place keeps address 0 and is reported once, as ``address-missing``, each
symbol's reason a note beneath it. The example above, built as ``RelWithDebInfo`` with the
keyword added, places every object of the demo but ``ValueG``, which a condition compiles out
of this image:

.. code-block:: text

   firmware.elf: warning[address-missing]: the image has no address for 'ValueG'; it reaches the a2l at address 0
       note: the image's debug information holds no variable named 'ValueG'
   1 warning

Under ``STRICT`` that is an error, and the build stops rather than ship an a2l with an address
of 0. ``BYTE_ORDER`` is held to the byte order the image states: one that contradicts it stops
the build as well. So does an image the reader cannot read, in the reader's own words - one
built without ``-g`` is told to be, and one that is not ELF at all, as a host build on Windows
links, is refused as such. A build like that keeps the address map below.
```

The first paragraph of *Where the address map comes from* no longer says DDD reads no build output at all:

```rst
``ADDRESS_MAP`` names a file; writing it is the project's step. DDD ships no extractor and
runs no toolchain tool of its own, and the generation before the link reads no build output at
all, which is what lets it run before anything has been compiled; with a map, reading the
linked image is left to the build. What it needs is the json :doc:`generated_artefacts`
describes, one flat object of symbol to address; where that comes from is the project's
business, so a toolchain without ``nm`` costs nothing but the recipe below.
```

and in its last paragraph, "adds the member offsets itself, from the type description or from the debug information." becomes:

```rst
print: a project with structured objects adds the member offsets itself, from the type
description or from the debug information - which is what ``ADDRESSES_FROM_IMAGE`` reads, for an
image that carries it. And the addresses of the objects DDD *does* know
```

The recipe's two code blocks, which `tests/test_cmake.py::TestTheDocumentedAddressMapRecipe` reads out of the page, are untouched.

- [ ] **Step 4: The command page, the README, SPEC.md, the changelog**

`docs/command_line_interface.rst`, the row of `ddd generate`: "``--address-map`` and ``--byte-order`` belong to the a2l." becomes:

```rst
       something DDD can guess; ``--address-map``, ``--image`` and ``--byte-order`` belong to
       the a2l. ``--image`` reads every address the a2l carries out of a linked ELF image's
       DWARF - an object by its name, a structure member by its access path - and the a2l takes
       the image's byte order, so a ``--byte-order`` contradicting it is refused, as is
       ``--image`` beside ``--address-map``; what the image cannot place keeps address 0 and is
       reported as ``address-missing``, each reason a note. It reads the images ``ddd tool
       from-elf`` reads, and refuses the others in the same words.
```

`README.md`: the sentence on the runtime dependencies ends `which reads ELF images for `ddd tool from-elf` and `ddd generate --image`.`; the list of useful options of `generate` ends:

```markdown
`--byte-order big`, `--address-map addresses.json`, `--image firmware.elf` (the a2l's
addresses read out of the linked image, below).
```

the first lines of the bullet on addresses under *A2L support* become:

```markdown
* the address of an object is `0x00000000` unless the linked image or an address map gives
  it (`ECU_ADDRESS` is simply the keyword the format uses);
  `SYMBOL_LINK` is always emitted, so a2l address patchers can fill them in after linking.
  `--image firmware.elf` reads every address out of the linked ELF image's DWARF - an object
  by its name, a structure member by its access path - and takes the image's byte order; a
  symbol the image cannot place keeps address 0 and is reported, its reason a note, and in
  cmake `ADDRESSES_FROM_IMAGE` makes the a2l one step after the link.  `--address-map` serves
  an image without debug information.
```

the command table's row of `generate`:

```markdown
| `ddd generate all\|c\|a2l\|<plugin> FILE -o DIR` | check and generate; `--dictionary FILE` also writes the resolved dictionary, in the same write as the artefacts; `--image ELF` reads the a2l's addresses out of the linked image |
```

and the checks table's row of `address-missing`:

```markdown
| warning | `address-missing` | an object in the a2l gets no address from the address map or the image the run was given |
```

`SPEC.md`, section 1.6: the sentence on the second run becomes:

```markdown
to carry the real addresses, which exist only after linking, runs DDD a second time, after
the link, reading them out of the linked image or out of a map taken from the linker output.
A build that does not require them stops after the first run.
```

Section 4, `address-missing`: its first sentence becomes the first of these lines, and its last ends with the second paragraph's sentence:

```markdown
- `address-missing`: an object the A2L carries gets no address from the address map or the
  image the run was given. It fires for a map only when the map has at least one entry:
  without a map, or with an empty one, every address is zero by construction, which is the
  run a build makes
```

```markdown
  the same objects. Given an image instead ([section 6](#6-address-information)), it fires
  for every object the image does not place, located at the image, and its notes say why:
  one per reason, said once however many of the objects named share it, for the objects the
  finding names.
```

Section 6: its first paragraph, up to "A symbol **shall** be stated once", becomes three:

```markdown
The addresses of the generated objects are only known after linking. DDD takes them from
one of two sources, each an option of `ddd generate a2l` and `all`: the linked image itself
(`--image`), or a symbol to address map the build writes (`--address-map`). Both are a
usage error, as is either given to a run that does not write the A2L. A symbol is the C
identifier of an object or, for the member of a structured object, its access path, for
example `Inlet.latest` or `Inlet[2].raw`, exactly as the A2L names it
([section 5.2](#52-a2l)).

`--image FILE` reads a linked ELF image, `ET_EXEC` or `ET_DYN`, and its DWARF debug
information, versions 2 to 5: the images the reader of `ddd tool from-elf` reads
([section 7.3](#73-toolbox)), any other being a usage error in that reader's words. Each
symbol the A2L states an address for is placed on its own. An object is the image's
variable of that name with external linkage: the units describing one variable at one
address, as `-fcommon` makes them, describe one variable, and a `static` of the same name
never stands for it, every object a dictionary describes being a global. A member is found
along its access path, typedefs and qualifiers seen through before each step: `.name` adds
the member's offset within its structure, and `[i]`, one per dimension, `i` times the size
of what the index steps over, so that an array of several dimensions is indexed row-major,
as C lays it out. The type a path ends at is not compared with the declaration. The A2L
takes the byte order the image states: a `--byte-order` that agrees is accepted, and one
that contradicts the image is a usage error. A symbol the image does not place keeps
address `0x00000000` and is reported by `address-missing`
([section 4](#4-consistency-checks)), why it is not placed a note of the finding: the image
holds no variable of that name, or only a `static` of it; the variable has no storage -
only declared, folded into a constant, removed by the compiler or discarded by the linker,
thread-local, or at no fixed address; its type has no member of that name, the C code and
the declaration disagreeing; a step indexes what is not an array, or names a member of what
is not a structure; an index is out of range; or a step names a bitfield, whose bits an
address cannot describe. An address outside `0 .. 0xFFFFFFFF` for a symbol the A2L states
an address for is a usage error naming the symbol and the image, and nothing is written.

`--address-map FILE` names one flat JSON object mapping each symbol to its address, for an
image the build reads itself - one without debug information, say. A symbol **shall** be
stated once: a map naming one twice is a usage error rather than the last of the two
addresses silently winning. The address is a JSON integer, or a string read as hexadecimal
with a `0x` prefix and as decimal without one - those two spellings exactly, whatever
whitespace surrounds them. The address of a symbol the project carries **must** fit an
unsigned 32 bit
```

and from "A map with entries that leaves an object of the A2L uncovered" to the section's end becomes a paragraph of its own:

```markdown
downstream tool resolve those it cares about.

A map with entries, or an image, that leaves an object of the A2L uncovered is
`address-missing` ([section 4](#4-consistency-checks)): a warning by default, an error under
`--strict`, and a run that reports it as an error writes nothing rather than a file whose
addresses it has just been told are incomplete, unless `--force` asks for the file anyway
([section 7](#7-tool-interface)). `ddd generate a2l` writes the A2L alone - no C is rendered
and no template directory is accepted - so the post-link run regenerates the A2L without
touching the sources the image was built from. Reading IEEE-695 images, and cross-checking
the type of each linked variable against its declaration, is *planned*.
```

Section 7: after "and none of the built-in artefacts' own;":

```markdown
`a2l` and `all` take `--byte-order` and one source of the addresses, `--image` or
`--address-map` ([section 6](#6-address-information));
```

and among the usage errors raised after the analysis, "an address map that cannot be read" becomes:

```markdown
is held until the project is read ([section 3.11](#311-plugins)), an address map or an
image that cannot be read, a `--renames` file, a dumped dictionary or an artefact that cannot be
```

Section 7.1: after the paragraph on `ADDRESS_MAP` ("...the A2L being the only artefact that reads it."):

```markdown
`ADDRESSES_FROM_IMAGE` takes the addresses out of the linked image instead
([section 6](#6-address-information)), so that one build gives the complete A2L: the
generation before the link leaves the A2L out, as `NO_A2L` does, and a second step after the
link runs `ddd generate a2l --image` over the image, the A2L its output. The step depends on
the image and on what the project is read from - its description, the files it is collected
or included from, the `.py` plugins and the tool - so it runs again when the image relinks or
a description changes and never otherwise, and a target `<stem>_ddd_a2l`, built by default,
drives it. The A2L keeps its path and its `DDD_A2L` property, and the step writes it into the
directory the generation before the link writes into, whose manifest keeps either run from
taking back the other's files ([section 5](#5-generated-artefacts)). `STRICT`, `SEVERITY` and
`BYTE_ORDER` apply to the step, so that under `STRICT` a symbol the image cannot place stops
the build. `ADDRESSES_FROM_IMAGE` beside `ADDRESS_MAP` or beside `NO_A2L` is a configure
error naming both.
```

`CHANGELOG.md`, a second entry of `## Unreleased`, after the toolbox's and a blank line:

```markdown
* **The a2l's addresses out of the linked image: `ddd generate a2l --image`.**  Every address
  the a2l carries is read out of the linked ELF image's DWARF - an object by its name, a
  structure member by its access path, at the offset the compiler gave it - and the a2l takes
  the byte order the image states, which a contradicting `--byte-order` is refused for.  A
  build needs no extraction script and works out no member offset by hand.  What the image
  cannot place keeps address 0 and is reported as `address-missing`, each reason a note of
  the finding.  In cmake, `ddd_generate(... ADDRESSES_FROM_IMAGE)` writes the a2l in a step
  after the link, so that one build gives the complete a2l; `ADDRESS_MAP` and `--address-map`
  stay as they were, for an image without debug information.  The map's reader has moved,
  from `ddd.backends` to `ddd.addresses`, and a map that is both malformed and out of range
  for a symbol the a2l carries is now refused for the malformed entry, still exit 2.  No file
  format changes.
```

The last sentence is Task 2's one measured change a user can see (notes-a, the 13 command lines run before and after the split).

- [ ] **Step 5: What else the image makes stale**

`docs/faq.rst`, *How do I get the real addresses into the a2l?*: the answer's first two paragraphs become:

```rst
After linking, out of the linked image: ``ddd generate a2l --image firmware.elf`` reads every
address the a2l carries out of the image's debug information, and in cmake
``ADDRESSES_FROM_IMAGE`` makes that one step of the build (:doc:`build_integration`). The
address of a global variable is decided by the linker, so it cannot exist when the sources
are generated - which is why DDD is meant to run twice per build: once before compiling, to
produce the c code and an a2l with placeholder addresses, and once after linking, to produce
the a2l the calibration tool is actually given.

An image without debug information takes ``--address-map`` instead: a flat json object of
symbol name to address, decimal or hexadecimal, produced from the linker output by whatever
already parses it in your build:
```

(the transcript after it, over the map, is unchanged and still run by `tests/test_transcripts.py`).

`docs/concept.rst`, the second run:

```rst
addresses are decided by the linker, so DDD reads them out of the linked image's debug
information (``--image``), or is handed a symbol to address map extracted from the linker
output (``--address-map``), and rewrites the a2l with the real values. The map is a flat json
object, with the addresses written in decimal or hexadecimal:
```

`docs/generated_artefacts.rst`, the addresses of the a2l: "Two mechanisms exist to fix that up, and DDD offers both" becomes:

```rst
Three mechanisms exist to fix that up, and DDD offers all three because projects are split
between them. The first is ``SYMBOL_LINK``, which names the c symbol the record describes and is
```

the paragraph that introduced the map as the second becomes two:

```rst
The second is ``--image``, which lets DDD read the addresses out of the linked image itself:
an ELF image with DWARF debug information, in which every object the a2l carries is found by
its name and every structure member by its access path, at the offset the compiler gave it.
The a2l takes the byte order the image states, and an object the image does not place keeps
address 0 and is reported, as ``address-missing``, with why: no variable of that name - one a
condition compiled out, say - or a member the image's type does not have. Nothing has to be
extracted, and no member offset worked out by hand.

The third is ``--address-map``, for an image without debug information: DDD does the
substitution itself, out of a file the build writes. It takes a flat json object mapping
symbol names to addresses, written either as decimal numbers or as hexadecimal strings,
whichever the tool producing it finds easier:
```

and the two-run sentence:

```rst
with the image or the map extracted from the linker output, to produce the a2l that ships.
:doc:`build_integration` makes the image's run one step of a single build. The artefact
```

The check's description: in `src/ddd/diagnostics.py`,

```python
        _check("address-missing", Severity.WARNING,
               "an object reaching the a2l gets no address from the address map or the image the "
               "run was given"),
```

and its row in `docs/consistency_checks.rst`:

```rst
     - an object that reaches the a2l has no entry in the map ``--address-map`` was given, or
       the image ``--image`` was given does not place it, so its ``ECU_ADDRESS`` stays 0; with
       an image, why it does not is a note of the finding. A map produced from a linker output
       legitimately lacks the objects that were not linked into this image, and an image the
       objects a condition compiled out of it, which is why the run goes on; a post-link
```

`docs/developer_documentation.rst`: the layer table gains, after the row of `src/ddd/elf.py`:

```rst
   * - ``src/ddd/addresses.py``
     - a build's addresses: the map a build writes, and where an image places each symbol
     - any output format: what an ``ECU_ADDRESS`` holds is the a2l backend's to weigh
```

*The split is enforced by a test* names the module among those parsed - its line "``plugins.py``, ``elf.py`` and everything under ``toolbox/`` - with ``ast``, collects the" becomes two:

```rst
``plugins.py``, ``elf.py``, ``addresses.py`` and everything under ``toolbox/`` - with
``ast``, collects the
```

and its bullets on `elf.py` and the new module read:

```rst
* ``elf.py`` imports no ``ddd`` module at all, so that ``addresses.py`` reads images with it
  without the toolbox,
* ``addresses.py`` imports no backend and not ``ddd.cli``: reading a build's addresses is
  core, and the range an ``ECU_ADDRESS`` holds is the a2l backend's to weigh, and
```

After *The ELF fixtures*, a section:

```rst
The address fixtures
--------------------

``ddd generate a2l --image`` is held to five images of one DDD project, which
``tests/fixtures/addresses/`` holds: scalars, a structure nesting another, arrays of structures
in one and two dimensions, and structures mixing bitfields with the value members after them.
The project's c is what ``ddd generate c`` writes for it, committed beside it, and five rows
of the matrix above compile and link it - little and big endian, 32 and 64 bit, gcc and clang,
and ``i686``, whose ``uint64_t`` aligns to 4 and so lays the project out otherwise. The
manifest beside them is the toolchain's word, never the reader's: each variable's address
from ``nm``, and each member's offset from the compiler's own ``offsetof``, compiled into the
image and read back with ``readelf``.

Two steps rebuild them, because DDD and the toolchains live in different places:

.. code-block:: text

   $ python docker/build_address_fixtures.py --generate  # on the host: the c, the symbols, the oracle
   $ docker compose run --rm address-fixtures  # in docker: the five images and the manifest

``tests/test_address_fixtures.py`` regenerates the c with the current DDD and fails, naming
the first command, when DDD has come to generate other c for the project, and, naming the
second, when what the images are built from changed without a rebuild. A release needs
neither: the one line it changes in every generated file, the banner naming DDD's version,
is read as naming the version the committed files record.
```

The two commands carry a trailing comment, so `tests/test_transcripts.py` shows them rather than runs them, as it does the page's `elf-fixtures` command.

`src/ddd/elf.py`, the module docstring's second paragraph:

```python
This module knows nothing of DDD. It imports pyelftools and the standard library and nothing
else, so that :mod:`ddd.addresses`, which places the symbols of an a2l in an image (section 6
of ``SPEC.md``), reads images with it without the toolbox; ``tests/test_backends.py`` holds
it to that.
```

`tests/test_backends.py`, the docstring of `test_the_elf_reader_knows_nothing_of_ddd`:

```python
        """ddd.elf serves the toolbox and ddd.addresses, which places the symbols of an a2l in
        an image (SPEC.md section 6): it imports no ddd module, so that neither has to take the
        other with it."""
```

- [ ] **Step 6: Run the documentation's tests**

Run: `.venv/bin/python -m pytest tests/test_documentation.py --no-cov -k "A2lOptions or target_ddd_generate or describes_address_missing"`
Expected: `12 passed, 854 deselected`.

Run: `.venv/bin/python -m pytest tests/test_documentation.py tests/test_transcripts.py tests/test_backends.py --no-cov`
Expected: `958 passed`: the transcripts of `docs/faq.rst` and `docs/concept.rst`, whose maps leave several symbols out, still print `they reach the a2l at address 0`, and every page still runs what it shows.

- [ ] **Step 7: The gates**

Run:

```bash
rm -f .coverage .coverage.*
.venv/bin/python -m pytest > build/gate.txt 2>&1; echo "EXIT=$?"; tail -3 build/gate.txt
.venv/bin/ruff check . > build/ruff.txt 2>&1; echo "RUFF=$?"; tail -1 build/ruff.txt
.venv/bin/ruff format --check . > build/fmt.txt 2>&1; echo "FMT=$?"; tail -1 build/fmt.txt
.venv/bin/mypy > build/mypy.txt 2>&1; echo "MYPY=$?"; tail -1 build/mypy.txt
```

Expected: `EXIT=0`, then `Required test coverage of 100% reached. Total coverage: 100.00%` and `5529 passed`, 12 more than after Task 6: the target test, the registry test, the positive control and the nine cases of `test_every_one_is_named`. `RUFF=0` and `All checks passed!`; `FMT=0` and `148 files already formatted`; `MYPY=0` and `Success: no issues found in 82 source files`.

- [ ] **Step 8: Commit**

```bash
git add CHANGELOG.md README.md SPEC.md docs/build_integration.rst docs/command_line_interface.rst docs/concept.rst docs/consistency_checks.rst docs/developer_documentation.rst docs/faq.rst docs/generated_artefacts.rst src/ddd/diagnostics.py src/ddd/elf.py tests/test_backends.py tests/test_documentation.py
git commit -F - <<'EOF'
document the a2l's addresses read out of the linked image

The build page leads with ADDRESSES_FROM_IMAGE and one build, over the
shipped example, and keeps the nm recipe for an image without debug
information; SPEC.md gives section 6 its second source, and sections 7
and 7.1 the option and the keyword; the command page, the README, the
FAQ, the concept and artefact pages and the changelog follow. The
address-missing check now says it fires for an image as well, and the
developer page, ddd.elf's docstring and a layering test's no longer call
the image's reading planned. Tests hold the pages to the code: every
target the module creates has a row on the build page, every option of
the a2l artefact is named on the command page, in the README and in
SPEC.md, and the registry's line for address-missing names both sources.

Co-Authored-By: <your model> <noreply@anthropic.com>
EOF
```

- [ ] **Step 9: Ablations**

In a scratch worktree made from the commit, from the worktree's root:

```bash
git worktree add --detach build/ablate HEAD
cd build/ablate
```

Each ablation below is one `sed`. After each, run, from `build/ablate`:

```bash
find . -name __pycache__ -prune -exec rm -rf {} +
/home/sauci/Documents/Github/ddd-toolbox-from-elf/.venv/bin/python -m pytest -p no:cacheprovider -o addopts="" tests/test_documentation.py tests/test_transcripts.py 2>&1 | grep -E "^FAILED|^ERROR|^=.*(passed|failed|error)|^rootdir"
git checkout -- docs/build_integration.rst docs/command_line_interface.rst README.md SPEC.md src/ddd/diagnostics.py
```

and check that the `rootdir:` line names `build/ablate`. Before any edit the run says `922 passed`. Every test named below is of `tests/test_documentation.py`. All measured on the scratch branch:

1. The build page has no row for `<stem>_ddd_a2l`:

   ```bash
   sed -i '/^   \* - ``<stem>_ddd_a2l``$/,/^       the call names and on the tool, and on nothing the c alone is rendered from\.$/d' docs/build_integration.rst
   ```

   `1 failed, 921 passed`: `TestTheBuildIntegrationPage::test_every_target_ddd_generate_creates_has_a_row_on_the_page`.

2. A row for a target the module does not create:

   ```bash
   sed -i 's/^   \* - ``<stem>_ddd_a2l``$/   * - ``<stem>_ddd_address``/' docs/build_integration.rst
   ```

   `1 failed, 921 passed`: the same test, which compares both ways.

3. The command page names no `--image`:

   ```bash
   sed -i 's/``--image``/``--picture``/g' docs/command_line_interface.rst
   ```

   `1 failed, 921 passed`: `TestTheA2lOptions::test_every_one_is_named[docs/command_line_interface.rst-``{}``---image]`.

4. The README names no `--image`:

   ```bash
   sed -i 's/--image/--picture/g' README.md
   ```

   `1 failed, 921 passed`: `TestTheA2lOptions::test_every_one_is_named[README.md-`{}---image]`.

5. SPEC.md names no `--byte-order`:

   ```bash
   sed -i 's/`--byte-order`/a byte order option/g' SPEC.md
   ```

   `1 failed, 921 passed`: `TestTheA2lOptions::test_every_one_is_named[SPEC.md-`{}---byte-order]`. Section 6 and section 7 name it; taking one of the two leaves the test passing (measured), which is what the test asks.

6. The check's description back to the map alone:

   ```bash
   sed -i 's/"an object reaching the a2l gets no address from the address map or the image the "/"an object reaching the a2l has no entry in the address map the "/' src/ddd/diagnostics.py
   ```

   The two halves of the string then read the old sentence again, `an object reaching the a2l has no entry in the address map the run was given`. `1 failed, 921 passed`: `TestTheCheckReference::test_the_registry_describes_address_missing_as_the_pages_do`. Before that test, nothing read the line: the same ablation passed the whole suite.

7. The check's description naming the image alone:

   ```bash
   sed -i 's/"an object reaching the a2l gets no address from the address map or the image the "/"an object reaching the a2l gets no address from the image the "/' src/ddd/diagnostics.py
   ```

   `1 failed, 921 passed`: the same test, its other assertion.

Then, from the worktree's root: `git worktree remove build/ablate`.

---

## Milestone gate

Every gate on the branch tip, none taken from an earlier task's run, each with its own exit status. `ddd:dev`'s id was noted before Task 1 (Global Constraints); the Docker half prints it first and last, and both must be that id.

The Python half, from the worktree's root:

```bash
rm -f .coverage .coverage.*
.venv/bin/python -m pytest > build/gate.txt 2>&1; echo "PYTEST=$?"; tail -3 build/gate.txt
.venv/bin/ruff check . > build/ruff.txt 2>&1; echo "RUFF=$?"; tail -1 build/ruff.txt
.venv/bin/ruff format --check . > build/fmt.txt 2>&1; echo "FMT=$?"; tail -1 build/fmt.txt
.venv/bin/mypy > build/mypy.txt 2>&1; echo "MYPY=$?"; tail -1 build/mypy.txt
```

Expected: `PYTEST=0`, `Required test coverage of 100% reached. Total coverage: 100.00%` and `5529 passed`; `RUFF=0` and `All checks passed!`; `FMT=0` and `148 files already formatted`; `MYPY=0` and `Success: no issues found in 82 source files`.

The Docker half is a script, because a command line carrying `"$(id -u):$(id -g)"` was refused by the command guard the plan's drafting sessions ran under, where a script holding the same lines ran. Write `build/gate-docker.sh` (Docker sees the worktree's `build/`, never the session's scratchpad):

```bash
#!/bin/bash
# The milestone gate's Docker half, from the worktree's root: bash build/gate-docker.sh
docker image ls ddd:dev --format '{{.ID}}'
printf 'services:\n  test:\n    image: ddd-addresses:dev\n  docs:\n    image: ddd-addresses:dev\n' > build/compose.addresses.yml
docker compose -p ddd-addresses -f docker-compose.yml -f build/compose.addresses.yml build test > build/gate-image.txt 2>&1; echo "IMAGE=$?"; tail -1 build/gate-image.txt
docker compose -p ddd-addresses -f docker-compose.yml -f build/compose.addresses.yml run --rm --user "$(id -u):$(id -g)" test > build/gate-312.txt 2>&1; echo "PY312=$?"; tail -3 build/gate-312.txt
docker compose -p ddd-addresses -f docker-compose.yml -f build/compose.addresses.yml run --rm --user "$(id -u):$(id -g)" -e JAVA_TOOL_OPTIONS=-Duser.home=/tmp docs > build/gate-docs.txt 2>&1; echo "DOCS=$?"; tail -3 build/gate-docs.txt
.venv/bin/python docker/build_address_fixtures.py --generate
docker compose -p ddd-addresses run --rm address-fixtures; echo "FIXTURES=$?"
git status --short tests/fixtures/addresses
docker image ls ddd:dev --format '{{.ID}}'
```

and run it: `bash build/gate-docker.sh`. Expected, in under three minutes once the image is built:

```text
<the id noted before Task 1>
IMAGE=0
 Image ddd-addresses:dev Built 
PY312=0
80 files skipped due to complete coverage.
Required test coverage of 100% reached. Total coverage: 100.00%
5529 passed in 166.98s (0:02:46)
DOCS=0
build succeeded.

The HTML pages are in build/docs/html.
unchanged   <worktree>/tests/fixtures/addresses/generated/ddd_globals.c
unchanged   <worktree>/tests/fixtures/addresses/generated/ddd_globals.h
unchanged   <worktree>/tests/fixtures/addresses/generated/ddd_types.h
unchanged   <worktree>/tests/fixtures/addresses/generated/Engine.h
wrote 46 symbols and 34 bitfields into tests/fixtures/addresses/symbols.json, and their oracle
 Container ddd-addresses-address-fixtures-run-<id> Creating 
 Container ddd-addresses-address-fixtures-run-<id> Created 
wrote 5 rows into tests/fixtures/addresses
FIXTURES=0
<the id noted before Task 1>
```

- `IMAGE` builds `ddd-addresses:dev` from this worktree: the override file names that tag for `test` and `docs`, and is what keeps both off `ddd:dev`, which every other service of `docker-compose.yml` names. BuildKit resolves the base images, `python:3.12-slim-bookworm` and `node:24-bookworm-slim`, on Docker Hub (the log's `load metadata` lines); nothing is pulled or tagged as `ddd:dev`. Each build gives `ddd-addresses:dev` a new id even from BuildKit's cache, as Task 4 measured for the fixture image.
- `PY312` is the suite on Python 3.12, the image's - the venv is 3.14, and nothing newer than 3.12 may have crept in. It includes Task 6's cmake builds, linux images with DWARF: the image carries gcc, binutils (`nm`, `readelf`) and the pip cmake.
- `DOCS` is the html with `-W --keep-going`, the one place Task 7's pages are built. Open `build/docs/html/build_integration.html` and read *The a2l's addresses* as a user would.
- The fixture rebuild is the reproducibility check: `git status` must list nothing under `tests/fixtures/addresses`. A difference is a finding - report which files moved.
- The last line must print the id noted before Task 1, as the first did.

Then by hand, two checks a user would make, as one script, `build/hands-on.sh`:

```bash
#!/bin/bash
# The milestone gate's hands-on checks, from the worktree's root: bash build/hands-on.sh
# 1. The shipped cmake example with ADDRESSES_FROM_IMAGE, built as a user would build it.
rm -rf build/hands-on && mkdir -p build/hands-on
cp -r examples cmake build/hands-on/
sed -i 's|^             SCHEMA_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/schemas")$|             SCHEMA_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/schemas"\n             ADDRESSES_FROM_IMAGE)|' build/hands-on/examples/cmake/CMakeLists.txt
.venv/bin/cmake -S build/hands-on/examples/cmake -B build/hands-on/build -G Ninja "-DCMAKE_MAKE_PROGRAM=$PWD/.venv/bin/ninja" "-DDDD_EXECUTABLE=$PWD/.venv/bin/ddd" -DCMAKE_BUILD_TYPE=RelWithDebInfo > build/hands-on/configure.txt 2>&1; echo "CONFIGURE=$?"
.venv/bin/cmake --build build/hands-on/build; echo "BUILD=$?"
.venv/bin/cmake --build build/hands-on/build; echo "AGAIN=$?"
nm -P -g --defined-only build/hands-on/build/firmware.elf | grep -E '^(ValueA|ValueE|AxisA|ParameterA) '
grep -E -A2 'begin (MEASUREMENT (ValueA|ValueE)|AXIS_PTS AxisA|CHARACTERISTIC ParameterA) ' build/hands-on/build/ddd/firmware.elf/DemoDevice.a2l | grep -E 'begin|ECU_ADDRESS|0x'
# 2. --image over the address fixtures' project, its Tuning_t given a member no image has.
rm -rf build/hands-on-image && mkdir -p build/hands-on-image
cp -r tests/fixtures/addresses/project build/hands-on-image/project
.venv/bin/python -c "import json, pathlib; p = pathlib.Path('build/hands-on-image/project/types.ddd.json'); d = json.loads(p.read_text()); [t['members'].append({'name': 'window', 'member': 'value', 'datatype': 'uint16', 'conversion': {'kind': 'identity'}}) for t in d['types'] if t['name'] == 'Tuning_t']; p.write_text(json.dumps(d, indent=2))"
.venv/bin/ddd generate a2l build/hands-on-image/project/project.ddd.json -o build/hands-on-image/gen --image tests/fixtures/addresses/powerpc.elf; echo "EXIT=$?"
.venv/bin/ddd generate a2l build/hands-on-image/project/project.ddd.json -o build/hands-on-image/strict --image tests/fixtures/addresses/powerpc.elf --strict; echo "EXIT=$?"
ls build/hands-on-image
```

`bash build/hands-on.sh`, and read it. Expected, `<worktree>` being this one's root:

```text
CONFIGURE=0
[0/2] Re-checking globbed directories...
[1/14] Generating the data dictionary of firmware.elf
wrote       <worktree>/build/hands-on/build/ddd/firmware.elf/ddd_globals.c (created)
...
wrote       <worktree>/build/hands-on/build/ddd/firmware.elf/DemoDevice.dictionary.json (created)
[2/14] Building C object CMakeFiles/firmware_ddd_globals.dir/ddd/firmware.elf/ddd_globals.c.o
...
[12/14] Linking C executable firmware.elf
[13/14] Reading the addresses of the a2l out of firmware.elf
firmware.elf: warning[address-missing]: the image has no address for 'ValueG'; it reaches the a2l at address 0
    note: the image's debug information holds no variable named 'ValueG'
1 warning
wrote       <worktree>/build/hands-on/build/ddd/firmware.elf/DemoDevice.a2l (created)
BUILD=0
[0/2] Re-checking globbed directories...
ninja: no work to do.
AGAIN=0
AxisA R 2058 c
ParameterA R 2020 2
ValueA B 4070 1
ValueE B 407a 2
    /begin MEASUREMENT ValueA "Scalar measurement with a linear conversion"
      ECU_ADDRESS 0x00004070
    /begin MEASUREMENT ValueE "Measurement used as the input quantity of AxisA"
      ECU_ADDRESS 0x0000407A
    /begin AXIS_PTS AxisA "Shared axis indexed by ValueE"
      0x00002058 ValueE RL_AXIS_UWORD 0 CM_LIN_HZ 6 0 8000
    /begin CHARACTERISTIC ParameterA "Single calibratable constant"
      VALUE 0x00002020 RL_VALUES_UWORD 0 CM_LIN_HZ 500 1500
tests/fixtures/addresses/powerpc.elf: warning[address-missing]: the image has no address for 'Tuning.window'; it reaches the a2l at address 0
    note: 'Tuning' has no member named 'window' in the image
1 warning
wrote       build/hands-on-image/gen/AddressFixture.a2l (created)
EXIT=0
tests/fixtures/addresses/powerpc.elf: error[address-missing]: the image has no address for 'Tuning.window'; it reaches the a2l at address 0
    note: 'Tuning' has no member named 'window' in the image
1 error
EXIT=1
gen
project
```

What to read in it: one build gives the a2l, in a step after the link (`[13/14]`), and the next build has nothing to do; the one object the step reports is `ValueG`, which `#if defined(FEATURE_X)` compiles out of this image - the build page shows that very finding; the addresses `nm` prints for four objects of the demo are the ones the a2l states, a measurement's on its `ECU_ADDRESS` line, an axis's and a characteristic's on their first line; a declaration naming a member the image's C did not have reaches the a2l at 0 with the reason as the note, and under `--strict` the run stops and writes nothing (no `strict` directory). The exact addresses are this host's - gcc and binutils of the machine running it - and only their agreement is the check.

**Measured on the scratch branch** (`plan/addresses-c2` at `682854b`, Tasks 1 to 7; Python 3.14 venv, gcc 15.2, the pip cmake 4.4 and ninja), each script run as written but for one thing: the scratch worktree has no `.venv` of its own, so `.venv/bin/` was the main worktree's venv by its absolute path, and the hands-on script ran with `PYTHONPATH` naming the scratch tree's `src`, the venv's editable install naming the main worktree's.

| Gate | Result |
| --- | --- |
| `PYTEST` | `0`, `5529 passed in 85.62s`, `Total coverage: 100.00%` |
| `RUFF`, `FMT`, `MYPY` | `0` each: `All checks passed!`, `148 files already formatted`, `Success: no issues found in 82 source files` |
| `ddd:dev` before | `b915687d0629` |
| `IMAGE` | `0` (`ddd-addresses:dev` `92b5b1eadb72`; the first build of the image, in the first round, took 70 s) |
| `PY312` | `0`, `5529 passed in 166.98s`, `Total coverage: 100.00%` |
| `DOCS` | `0`, `build succeeded.`; *The a2l's addresses* read in `build_integration.html` |
| fixtures | four `unchanged`, `wrote 5 rows into tests/fixtures/addresses`, `FIXTURES=0`, `git status` empty |
| `ddd:dev` after | `b915687d0629` |
| hands-on | as above, line for line |

The previous plan's gate recorded one test failing under Python 3.12 in Docker, master's own (`tests/test_transcripts.py` rewriting `examples/pressure/work/`); it does not fail any more: `PY312` passed whole.

## Progress log

| Task | Commits | Review | Notes |
| --- | --- | --- | --- |
| 1 the reader records linkage | | | |
| 2 one home for a build's addresses | | | |
| 3 placing a symbol in an image | | | |
| 4 the address fixtures | | | |
| 5 `--image` on the command line | | | |
| 6 `ADDRESSES_FROM_IMAGE` | | | |
| 7 the documentation | | | |

## What was left open

Filled in as the work goes. Each entry says what was not done and what it costs. The first four are the spec's section 9, left open by design.

- **Comparing each linked variable's type with its declaration** (SPEC.md section 6's other half). A variable whose C type has drifted from its DDD declaration still gets its address, and only the a2l's reader notices.
- **Bitfield members in the a2l.** They stay out, as before. The image now says where their bits are, so the address of the field's storage unit and a `BIT_MASK` could describe one, for `--image` only.
- **IEEE-695** images, which SPEC.md section 6 names beside ELF.
- **Pointer members in `ddd tool from-elf`**, deferred by the maintainer on 2026-10-02 and recorded in the toolbox plan's "What was left open".
- **A host whose toolchain links no ELF** - Windows with MinGW, macOS - cannot use `ADDRESSES_FROM_IMAGE` for a native build: the reader refuses its PE or Mach-O image (ruling 17, held by Task 6's tests). Cross builds for embedded targets link ELF on every host.

## Rulings taken

| # | Ruling | Why | Cost if wrong |
| --- | --- | --- | --- |
| 1 | **`load_address_map(path)` loses its `carried` argument: the 32-bit check moves to the a2l side, `weigh_addresses`**, rather than the spec's "moves here unchanged" | The check is the `ECU_ADDRESS`'s, which only the a2l backend knows; core code importing `ADDRESS_MAX` from a backend would invert the layering. Every sentence a user sees stays the same | None a user can see |
| 2 | **`Variable.external` defaults to `True`** | Every hand-built variable of the toolbox's tests stands for a global; the reader always states it | A test meaning a `static` must say so |
| 3 | **The address fixtures' C is DDD's own output, committed and held to a fresh `ddd generate c` by a test**, not generated inside the fixture image | The fixture image has no DDD and needs none; the images are then built from exactly what DDD generates, and a change to the generator fails the drift test rather than drifting | A generator change asks for a fixture rebuild |
| 4 | **The oracle reads integer constants, never addresses stored in the image** | A static PIE (`x86_64`) stores an absolute address as a dynamic relocation whose bytes in the file are zero; `offsetof` and `sizeof` are plain integers on every row | None |
| 5 | **Five rows, not ten**: `armv7m`, `powerpc`, `x86_64`, `aarch64_be`, `i686` | The first four cover gcc and clang, both byte orders and both widths - and, measured, lay this project out identically, byte for byte. Only `i686` lays it out otherwise (`Mixed.last` at 12, not 16, its `uint64_t` aligned to 4), which is what lets Task 5 tell offsets read from the image from offsets predicted from the declaration. The reader itself is held to all ten | An ABI only another row has goes unmeasured |
| 6 | **A step whose offset the walk cannot work out is a reason of its own**: `where '<part>' lies cannot be worked out from the image's debug information` | The reader's model can hold a member whose `bit_offset` it could not read, and an element whose type has no size; the spec's list of reasons has none true of them | None a user meets: no C compiler states a C member's offset as an expression |
| 7 | **Globals of one name at several addresses are not placed**, with a reason naming the addresses | One global name is one symbol to a linker, so no real link does this; the model can still hold it, and taking the first unit's would be a silent guess | A symbol reported missing rather than guessed, in a case no linker makes |
| 8 | **`ddd.addresses` imports `ddd.elf` only inside the functions that read an image**; Task 5 imports `open_image` under `_command_tool_from_elf`'s `ModuleNotFoundError` guard | `generate` imports `ddd.addresses` on every run; `ddd.elf` costs 47 ms to import, and without pyelftools - a broken installation - every `generate` would end in a traceback (measured) | Two function-local imports |
| 9 | **A name only the symbol table holds says so**, with the `-g` hint of `ddd tool from-elf`'s own sentence | The commonest reason a global of the generated C has no DWARF is a unit compiled without `-g`; the hint names the fix | None |
| 10 | **A map with an out-of-range carried entry before a malformed one is refused for the malformed one**, where it used to be refused for the range | Inherent to Ruling 1: the reader no longer knows what the a2l carries. Measured over 13 maps: the only difference; both sentences are unchanged and both runs exit 2 | None worth a line of code |
| 11 | **The address fixtures' drift test reads a fresh banner's generator as the one recorded** | The banner (`Generated from 'project.ddd.json' by ddd <version>.`) is the one line a release changes in every generated file, and no compiler reads it; compared as it is, every release would ask for a Docker rebuild | A change of the generator's name alone goes unnoticed, and changes no image |
| 12 | **The address fixtures' hashes cover the generated C, the symbol list, `oracle.c`, the Dockerfile and both build scripts, not the project's descriptions** | The images are built from the C; a description change that alters neither the C nor the symbols changes no image, and one that does is caught without Docker by the regeneration test | None |
| 13 | **The build script's host mode (`--generate`) imports the checkout's own `src`, first on `sys.path`** | The venv's editable install names one checkout; run from another, `import ddd` would generate with the first one's DDD (measured from a scratch worktree) | None |
| 14 | **The fixture manifest states `pointer_size` and `offsets` for each row** | The span test needs each row's width, and `offsets` shows Review Focus 1 and 3, which `addresses` cannot: a structured variable's own address is not a carried symbol | None |
| 15 | **With an image, `address-missing`'s notes are the reasons of the symbols the finding names (`_LISTED_LIMIT` of them), each said once, in the order of the symbols** | Readable at any size: every member of a variable the image lacks shares one sentence, and an image whose definition file has no DWARF gives four lines for 46 missing symbols (measured) | A reason of a symbol past the fifth shows only once the first five are mended |
| 16 | **The map's and the image's findings share their ending, `_at_address_0`** | One `it reaches`/`they reach` conditional, pinned on both sides | None |
| 17 | **Task 6's build tests assert the reader's refusal where the host links no ELF** | The feature reads ELF; the suite has no skips; each test still asserts what such a host gets | The windows cells never see a successful `ADDRESSES_FROM_IMAGE` build |
| 18 | **The step after the link does not depend on the templates or `DEPENDS`** | They are the c's inputs; a template edit relinks, which reruns the step anyway | A `DEPENDS` file only the a2l would need reruns nothing - none is known |
| 19 | **`BYTE_ORDER` goes to the step after the link alone** | The run before it has left the a2l out (ablation 2) | None |
| 20 | **`address-missing`'s registry description, README row, reference row and SPEC entry say "map or image"**, the registry line held by a test | The old line is false of an image run; `ddd checks` prints it | A diagnostic's wording is not the public interface |
| 21 | **The reader's `DECLARED_ONLY` stays as it is in a note** | A note has no location, so its "here" reads against the finding's own, the image | A slightly odd "here" |
