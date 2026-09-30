# `ddd tool from-elf` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A toolbox on the command line, `ddd tool`, whose first tool, `ddd tool from-elf IMAGE SYMBOL...`, prints the DDD declarations of the C variables a linked ELF image's DWARF describes - checked by DDD itself before anything is printed.

**Architecture:** A reader, `ddd.elf`, turns ELF and DWARF into a small C-type model and knows nothing of DDD; it works on two narrow protocols so that test doubles reach every branch no compiler produces. A translator, the package `ddd.toolbox`, selects the variables, maps the model to DDD's spelling, decodes initial values from the image's bytes, and hands the result to DDD's own loader and analysis under `--standalone`'s policy, relaying what they find. `cli.py` adds the `tool` group. Fixture images for ten targets - little and big endian, 32 and 64 bit, gcc and clang, DWARF 2 to 5 - are built in Docker and committed, so the suite needs neither Docker nor a compiler.

**Tech Stack:** Python 3.12+ (the worktree's venv is 3.14, CI and the image run 3.12), pyelftools 0.33 as an optional extra, pydantic v2 through DDD's own models, pytest at 100 % line and branch, Debian trixie cross toolchains in Docker (gcc 14.2, clang 19), GNU readelf as the fixtures' oracle, Sphinx docs under `-W`.

**Spec:** `docs/superpowers/specs/2026-09-30-toolbox-from-elf-design.md`. Read it before any task. Where this plan departs from it, the departure is a row of *Rulings taken* at the end, with its reason.

**How this plan was written.** Every line of `src/` code below ran before it was written here: the reader and the translator were drafted in a scratch package, run over probe images gcc 15 built at DWARF 2, 4 and 5 (compressed, and as a static PIE), then over the whole fixture matrix built in the pinned Debian image, and passed `ruff check`, `ruff format --check` and `mypy --strict` as they stand. The fixture sources, the Dockerfile and the build script below are the ones that built all ten rows on the first run. What was *not* run is the tests: they are written here from the behaviour measured, and the TDD steps are where they first meet the code. A test that fails for a reason this plan did not predict is a finding to report, not a test to bend.

## Global Constraints

Every task's requirements include this section.

**Where the work happens**

- **The worktree is `/home/sauci/Documents/Github/ddd-toolbox-from-elf`, on the local branch `feature/toolbox-from-elf`.** Run every command from there. The main checkout, `/home/sauci/Documents/Github/ddd`, holds the maintainer's uncommitted work on `feature/gui-large-projects`: never `cd` into it, never run git against it, never edit a file in it.
- **Nothing is pushed.** No `git push`, no remote branch, no pull request, no `gh` command that writes. The branch stays local until the maintainer decides otherwise.
- **The worktree has its own `.venv`** (Python 3.14). There is no `python` on PATH: always `.venv/bin/python`. The main checkout's `.venv` is never touched.
- **Docker runs under this branch's own compose project name**, `-p ddd-toolbox`, and builds only the fixture image `ddd-elf-fixtures:dev` and, at the milestone gate, `ddd-toolbox:dev` through the override file that gate writes. **Never build, pull or retag `ddd:dev`**, which the main checkout's services run: `docker compose run --rm test`, `lint` or `docs` without the override would rebuild it from this branch.
- Docker cannot see the session scratchpad (`/tmp/claude-1000/...`). Throwaway files go under the worktree's ignored `build/`.

**Running things**

- **Never add `-q` to pytest.** `pyproject.toml` already sets it in `addopts`; a second one removes the `N passed` line while pytest-cov still prints its coverage line, so the output looks fine and says nothing.
- **A pipeline reports its last command's exit status.** Capture each tool's own: `.venv/bin/python -m pytest > build/gate.txt 2>&1; echo "EXIT=$?"; tail -3 build/gate.txt`. The tell for a run that finished is its **summary line**; a tail ending in a stack trace did not finish, whatever the exit code says.
- A stale `.coverage` data file once made pytest answer `4445 passed` with exit 3 and no coverage line. If the coverage summary is missing, delete `.coverage*` (gitignored) and re-run.
- `--no-cov` is for a narrowed run while developing; a task's closing run is the whole suite, with coverage.

**Gates**

- Python: `.venv/bin/python -m pytest` at **100 % line and branch**, `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, and `.venv/bin/mypy` run **bare**.
- **No `pragma: no cover`, no skips, no xfails.** Nothing skips when pyelftools is missing: it is a dev requirement from Task 3 on, and a test that skips reports success without having run.
- The code must run on **Python 3.12**: CI and the image use it, the venv is 3.14. Nothing newer than 3.12 syntax or stdlib; the milestone gate runs the suite on 3.12 in Docker.

**What the gates cannot see**

- **A conditional expression registers zero branches with coverage.py, and so does a comprehension filter.** A short-circuit `and`/`or` inside an `if` records one branch pair for the whole `if`, not one per operand. Where a branch matters, a named test pins each side - the tests below do, and a reviewer checks that they do.
- **An `assert` is not a branch either.** The two in `ddd.toolbox.mapping` and the one in `ddd.toolbox.from_elf` state invariants other code establishes; each has a comment saying which.
- **A coverage gate cannot see data.** Ablate every new data value - a table row, a regular expression, a set of section names, a sentence - and confirm a **named** test dies. If none does, write the one that does.
- **Ablate in a scratch `git worktree` and run pytest with that worktree as the working directory.** `pyproject.toml` sets `pythonpath = ["src", "tools", "docker"]`, resolved against *rootdir* and placed ahead of any `PYTHONPATH`: a run started from this worktree measures this worktree, every rot in the scratch one "survives", and the reading is that nothing pins anything. The tell is pytest's own `rootdir:` line. Confirm an ablation kills something before trusting that another kills nothing. A survival is re-run under `PYTHONHASHSEED=0`, `1`, `4` and `7` before it is believed. Put the scratch worktree under `build/`.
- **Never draw a conclusion about what *else* pins something from a narrowed run** - no `-k`, no path argument. That question is a whole-suite question; copy the summary line in rather than paraphrasing it.
- **A refusal test asserts the whole sentence with `==`.** A code and a substring leave the explanatory clause pinned by nothing. Where a sentence below quotes pyelftools' own words, read it off the running code, never out of this plan.

**Prose**

- **A sentence stating a measurement gets the measurement run as it is written**, against the file it names, with the exit status copied from that run. A sentence saying "nothing else does X" is a whole-repository claim and gets a whole-repository grep.
- **Cite by name, not by line number.** Line numbers go stale the moment an earlier task edits the file.
- **Before ruling on a trade-off, confirm both sides of it can actually happen.**

**Conventions**

- Commits: lowercase imperative subject on **one line**, no `feat:`-style prefix, a body saying why. Trailer `Co-Authored-By: <your model> <noreply@anthropic.com>`. Never `--amend`, never rebase, never push.
- Subagents do not write report files; they return findings as text.
- If a brief or this plan is wrong, **say so in your report rather than working around it silently.** The fixture matrix is the likeliest place: a toolchain can answer differently from the trial build this plan records.

## Prerequisites

1. **The worktree exists and is clean** apart from ignored files: `git -C /home/sauci/Documents/Github/ddd-toolbox-from-elf status --short` prints nothing, and `git log --oneline -3` shows the spec's two commits on `06d8737`.
2. **Gate the tree before Task 1**: the baseline measured when the worktree was made is `4714 passed` at 100 %, `RUFF=0`, `FMT=0`, `MYPY=0`. Each task is compared against the gates at the commit before it.
3. **Docker works** for the current user: `docker version` answers both client and server. Task 1 is the only task that needs it before the milestone gate.
4. The venv has pyelftools 0.33 already, installed while the spec was written; Task 3 is where it becomes a declared dependency. Check with `.venv/bin/python -c "import elftools; print(elftools.__version__)"`.

## Review Focus

The inputs most likely to bite a user that no task's happy path reaches. Each is pinned by a test in the task that owns it.

1. **A big endian image whose DWARF states bitfields the old way** (Task 3). DWARF 2 and 3 count `DW_AT_bit_offset` from the storage unit's most significant bit, so the conversion differs by byte order. The `powerpc` (DWARF 3) and `armeb` rows must read `Gapped_s`'s members at bits 0, 5 and 7 exactly as the little endian rows do - the trial build did.
2. **An enum with no underlying type** (Task 2, Task 3). Strict DWARF 2 states neither `DW_AT_type` nor `DW_AT_encoding` on an enum, and its sign then rests on a negative enumerator alone. `armv7m-dwarf2`'s `Enum_Signed` must read signed.
3. **A `static` two units define, reached by a glob** (Task 4). `'Tw*'` must report `elf-symbol-ambiguous` for `Twin`, not print the first unit's silently.
4. **A DDD analysis error hidden behind a load error** (Task 7). A `schema` error stops DDD before its analysis; the variable carrying an `init-invalid` is only refused on the second pass. Refusing on the first pass alone would print it.
5. **Thread-local storage overlapping ordinary sections** (Task 3). `.tbss` shares addresses with the section after it; a variable there must not be read as belonging to `.tbss`, and `Image.sections` must leave the thread-local sections out.

## File Structure

| File | Responsibility | Tasks |
| --- | --- | --- |
| `tests/fixtures/elf/src/main.c`, `unit_a.c`, `unit_b.c`, `nodebug.c`, `shared.h` *(new)* | the fixture's C source, a variable per case | 1 |
| `docker/elf-fixtures.Dockerfile` *(new)* | the pinned cross toolchains | 1 |
| `docker/build_elf_fixtures.py` *(new)* | builds every row, the negative inputs, the example copy and the manifest | 1 |
| `docker-compose.yml` | the `elf-fixtures` service | 1 |
| `tests/fixtures/elf/*.elf`, `main.o`, `manifest.json`, `examples/firmware/firmware.elf` *(new, generated)* | the committed images and their oracle | 1 |
| `tests/test_elf_fixtures.py` *(new)* | the drift guard, and the matrix's own shape | 1 |
| `src/ddd/elf.py` *(new)* | the C model, the protocols, the readers over them (Task 2); pyelftools, `open_image` (Task 3) | 2, 3 |
| `tests/test_elf.py` *(new)* | the reader: doubles (Task 2), the matrix and the refusals (Task 3) | 2, 3 |
| `requirements-elf.txt` *(new)*, `pyproject.toml` | the `elf` extra, `dev` including it, the sdist | 3 |
| `tests/test_backends.py` | the layering: `ddd.elf` imports no `ddd` module, the toolbox no backend | 3, 4 |
| `src/ddd/toolbox/__init__.py`, `findings.py`, `selection.py` *(new)* | the package, its findings table, which variables the arguments name | 4 |
| `src/ddd/toolbox/mapping.py` *(new)* | the C model to DDD's spelling | 5 |
| `src/ddd/toolbox/values.py` *(new)* | initial values out of bytes | 6 |
| `src/ddd/toolbox/checked.py`, `from_elf.py` *(new)* | DDD's check, and `describe` | 7 |
| `tests/test_toolbox_from_elf.py` *(new)* | the translator, on hand-built models | 4, 5, 6, 7 |
| `src/ddd/cli.py` | the `tool` group, the handler, one writer for `-o` | 8 |
| `tests/test_cli.py` | the command end to end, over every row | 8 |
| `SPEC.md`, `README.md`, `docs/toolbox.rst` *(new)*, `docs/index.rst`, `docs/command_line_interface.rst`, `docs/developer_documentation.rst`, `CHANGELOG.md`, `tests/test_documentation.py` | the documentation, held to the code | 9 |

## Interfaces Between Tasks

```python
# Task 2 — ddd.elf (the model and the readers over protocols; no pyelftools yet)
DW_ATE_BOOLEAN, DW_ATE_COMPLEX_FLOAT, DW_ATE_FLOAT, DW_ATE_SIGNED, DW_ATE_SIGNED_CHAR,
DW_ATE_UNSIGNED, DW_ATE_UNSIGNED_CHAR: Final[int]
DECLARED_ONLY, FOLDED, REMOVED, THREAD_LOCAL, NOT_AN_ADDRESS: Final[str]  # why no address
class ElfReadError(ValueError): ...
@dataclass(frozen=True, slots=True) class Declared: path: str; line: int
@dataclass(frozen=True, slots=True) class Base: name: str; encoding: int; size: int
@dataclass(frozen=True, slots=True) class Enum: tag: str | None; size: int; signed: bool
    enumerators: tuple[tuple[str, int], ...]; declared_at: Declared | None = None
@dataclass(frozen=True, slots=True) class Member: name: str | None; type: CType
    bit_offset: int | None; bit_size: int | None = None; alignment: int | None = None
    declared_at: Declared | None = None
@dataclass(frozen=True, slots=True) class Struct: tag: str | None; size: int
    members: tuple[Member, ...]; alignment: int | None = None; declared_at: Declared | None = None
@dataclass(frozen=True, slots=True) class Array: element: CType; dimensions: tuple[int, ...]
@dataclass(frozen=True, slots=True) class Qualified: inner: CType; const: bool = False; volatile: bool = False
@dataclass(frozen=True, slots=True) class Typedef: name: str; inner: CType
@dataclass(frozen=True, slots=True) class Unsupported: what: str
type CType = Base | Enum | Struct | Array | Qualified | Typedef | Unsupported
@dataclass(frozen=True, slots=True) class Variable: name: str; unit: str; type: CType
    declared_at: Declared | None = None; address: int | None = None; missing: str = ""
@dataclass(frozen=True, slots=True) class Section: name: str; address: int; size: int; offset: int | None
@dataclass(frozen=True, slots=True) class Image: path: Path; byte_order: Literal["little", "big"]
    variables: tuple[Variable, ...]; sections: tuple[Section, ...]; symbols: frozenset[str]
    contents: bytes
    def section_of(self, address: int) -> Section | None: ...
    def read(self, address: int, size: int) -> bytes | None: ...
class Entry(Protocol): tag, offset, attributes, iter_children(), get_DIE_from_attribute(name)
class Unit(Protocol): name, top, operations(expression), indexed_address(index), file(index)
@dataclass(frozen=True, slots=True) class FileTable: version: int
    files: tuple[tuple[str, int], ...]; directories: tuple[str, ...]; compilation_directory: str
def file_path(table: FileTable | None, index: int) -> str | None: ...
def size_of(ctype: CType) -> int | None: ...
def read_variables(
    units: Iterable[Unit], *, big_endian: bool, thread_local: frozenset[str] = frozenset()
) -> tuple[Variable, ...]: ...

# Task 3 — ddd.elf (pyelftools)
def open_image(path: Path) -> Image: ...  # raises ElfReadError
def file_table(program: Any, compilation_directory: str) -> FileTable | None: ...

# Task 4 — ddd.toolbox.findings / ddd.toolbox.selection
FINDINGS: Final[dict[str, Severity]]
def place(image: Image, declared: Declared | None) -> Location: ...
def report(bag, check, message, location, notes=()) -> None: ...
@dataclass(frozen=True, slots=True) class Wanted: text: str; unit: str | None; pattern: str; glob: bool
def wanted(text: str) -> Wanted: ...  # raises ValueError
def select(image: Image, arguments: Sequence[Wanted], bag: DiagnosticBag) -> list[Variable]: ...

# Task 5 — ddd.toolbox.mapping
@dataclass(frozen=True, slots=True) class Shape: core; dimensions; const; volatile; name
def shape_of(ctype: CType) -> Shape: ...
def datatype_of(core: Base | Enum) -> str | None: ...
def described(core: Base | Enum) -> str: ...
@dataclass(frozen=True, slots=True) class Typed: kind: str; datatype: str | None
    typename: str | None; dimensions: tuple[int, ...]; conversion: dict[str, Any] | None
    volatile: bool; reaches: frozenset[str]; element_size: int
@dataclass(frozen=True, slots=True) class Refusal: path: str; what: str; declared_at: Declared | None = None
class Mapper:
    def __init__(self, image: Image, bag: DiagnosticBag) -> None: ...
    def typed(self, variable: Variable) -> Typed | None: ...
    def conflicts(self) -> dict[str, list[Declared | None]]: ...
    def types(self, names: Collection[str]) -> list[dict[str, Any]]: ...

# Task 6 — ddd.toolbox.values
class UnstatableValueError(ValueError): ...
def initial_value(raw: bytes, datatype: str, dimensions: tuple[int, ...], byte_order: str) -> Any: ...
def shortest_float32(value: float) -> float: ...

# Task 7 — ddd.toolbox.checked / ddd.toolbox.from_elf
POLICY: Final[tuple[str, ...]]
@dataclass(frozen=True, slots=True) class Candidate: variable: Variable
    definition: dict[str, Any]; reaches: frozenset[str]
def component_file(name, types, interface) -> dict[str, Any]: ...
def checked(candidates, types, *, image, scope, component, bag) -> list[Candidate]: ...
DEFAULT_SECTIONS, PRODUCER_SCOPES: Final[frozenset[str]]
CHECKED_COMPONENT, NOT_INFERRED, VALUE_BLOCKS: Final[str]
@dataclass(frozen=True, slots=True) class Description: interface: tuple[dict, ...]; types: tuple[dict, ...]
def describe(image, arguments, *, scope: str, component: str | None, bag) -> Description: ...
def document_text(description: Description, component: str | None) -> str: ...

# Task 8 — ddd.cli
def _command_tool_from_elf(args: argparse.Namespace) -> int: ...
def _write_output(path: Path, text: Callable[[], str], bag, output_format: str, *sources: Path) -> None: ...
```

---

### Task 1: the fixture matrix, built in Docker and committed

**Files:**
- Create: `tests/fixtures/elf/src/main.c`, `unit_a.c`, `unit_b.c`, `nodebug.c`, `shared.h`
- Create: `docker/elf-fixtures.Dockerfile`, `docker/build_elf_fixtures.py`
- Modify: `docker-compose.yml` (the `elf-fixtures` service)
- Create, by running the service: `tests/fixtures/elf/{x86_64,i686,armv7m,armv7m-dwarf2,armeb,aarch64,powerpc,s390x,riscv32,aarch64_be}.elf`, `stripped.elf`, `main.o`, `manifest.json`, and `examples/firmware/firmware.elf`
- Test: `tests/test_elf_fixtures.py`

**Interfaces:**
- Consumes: nothing.
- Produces: the committed images; `manifest.json` shaped `{"hashes": {path: sha256}, "rows": {row: {"compiler", "flags", "cases", "traits", "variables"}}}`; the importable module `build_elf_fixtures` (`docker/` is on pytest's `pythonpath`) with `ROWS`, `OUTPUT`, `EXAMPLE`, `EXAMPLE_ROW`, `STRIPPED_ROW`, `digest`, `hashed`.

Why first: every reader test after Task 2 reads these images, and the manifest is their oracle - what each target's own toolchain says, never what ddd's reader says. Why flat paths, `docker/build_elf_fixtures.py` rather than the spec's `docker/elf-fixtures/build_fixtures.py`: a hyphenated directory is no package, and only a module directly in `docker/` is importable by the drift guard, which must use the build script's own `hashed` rather than a second copy of it (ruling 1).

- [ ] **Step 1: The fixture source**

`tests/fixtures/elf/src/shared.h`:

```c
/* Shared by unit_a.c and unit_b.c. DWARF gives each unit its own copy of this structure, and
   `ddd tool from-elf` states it once. */
#ifndef SHARED_H
#define SHARED_H

#include <stdint.h>

typedef struct {
    uint8_t x;
    uint8_t y;
} Shared_t;

#endif
```

`tests/fixtures/elf/src/main.c`:

```c
/* The fixture of `ddd tool from-elf`: a variable per case of section 4 of
   docs/superpowers/specs/2026-09-30-toolbox-from-elf-design.md, each named for its case.

   No initial value repeats a byte, so that a byte order mistake cannot pass for a right
   answer. FIXTURE_TLS and FIXTURE_FOLDED are the optional cases: a row defines them where its
   toolchain builds them, and tests/fixtures/elf/manifest.json records which it did. */
#include <stdbool.h>
#include <stdint.h>

#include "shared.h"

#define USED __attribute__((used))

/* 4.1 kind */
uint16_t Meas_U16 = 0x1234;
volatile uint32_t Meas_Volatile = 0x12345678;
int16_t Meas_Array[3] = {-2, 0x1234, 7};
uint8_t Meas_Matrix[2][3] = {{1, 2, 3}, {4, 5, 6}};
uint8_t Meas_Fill[4] = {9, 9, 9, 9};
uint32_t Meas_Bss;
const uint16_t Cal_Gain = 300;
const volatile uint8_t Cal_Tunable = 0x5A;
const int32_t Cal_Table[4] = {-2, 0x12345678, 0, 1};
extern const uint16_t Cal_Declared_First;
const uint16_t Cal_Declared_First = 0x1234;

/* 4.2 datatypes */
bool Type_Bool = true;
char Type_Char = 'A';
long Type_Long = -2;
uint64_t Type_U64 = 0x0102030405060708u;
int64_t Type_S64 = -0x0102030405060708;
float Type_F32 = 1.5f;
float Type_F32_Tenth = 0.1f;
double Type_F64 = 0.1;
long double Type_Long_Double = 1.0L;
_Complex float Type_Complex;
uint8_t *Type_Pointer;
union {
    uint8_t a;
    uint16_t b;
} Type_Union;

/* 4.3 enums */
typedef enum { STATE_OFF = 0, STATE_ON = 1, STATE_FAULT = 200 } State_t;
State_t Enum_State = STATE_ON;
enum Signed_e { SIGNED_NEG = -2, SIGNED_POS = 3 };
enum Signed_e Enum_Signed = SIGNED_NEG;
enum { ANON_A = 1, ANON_B = 2 } Enum_Anonymous = ANON_B;
const State_t Enum_Table[2] = {STATE_FAULT, STATE_OFF};

/* 4.4 structures */
typedef enum { MODE_IDLE = 0, MODE_RUN = 1, MODE_STOP = 2 } Mode_t;
typedef struct Inlet_s {
    uint16_t raw[4];
    State_t state;
    struct {
        uint8_t lo;
        uint8_t hi;
    } pair;
    uint8_t flags : 3;
    Mode_t mode : 2;
    bool ready : 1;
} Inlet_t;
Inlet_t Struct_Inlet;
Inlet_t Struct_Inlets[2];
const Inlet_t Struct_Config = {.raw = {1, 2, 3, 4}};
const Inlet_t Struct_Configs[2];
struct {
    uint8_t a;
    uint8_t b;
} Struct_Anonymous;
struct Holder_s {
    uint8_t *ptr;
    uint8_t n;
} Struct_With_Pointer;
struct Qualified_s {
    volatile uint8_t v;
    const uint8_t c;
} Struct_Qualified;

/* 4.5 layout */
struct Gapped_s {
    uint8_t a : 2;
    uint8_t : 3;
    uint8_t b : 2;
    uint16_t c : 9;
};
struct Gapped_s Layout_Gapped;
struct Padded_s {
    uint8_t a : 7;
    uint8_t b : 2;
};
struct Padded_s Layout_Padded;
struct Aligned_s {
    _Alignas(8) uint8_t x;
};
struct Aligned_s Layout_Aligned;

/* 4.7 sections */
__attribute__((section(".calib"))) const uint16_t Section_Calib = 0x1234;

/* storage */
static uint16_t Static_Used USED = 0x0102;
#ifdef FIXTURE_TLS
_Thread_local uint32_t Tls_Counter;
#endif
#ifdef FIXTURE_FOLDED
static const uint32_t Static_Folded = 7;
#endif

/* The probes: tests/fixtures/elf/manifest.json holds their sizes, as the row's readelf reads
   them. */
enum Probe_e { PROBE_ONE = 1 };
enum Probe_e Probe_Enum;
struct {
    char c;
    uint64_t v;
} Probe_Align;

uint32_t fixture_entry(void) {
#ifdef FIXTURE_FOLDED
    return Static_Folded + Meas_Bss;
#else
    return Meas_Bss;
#endif
}
```

Two cases the spec lists are not here, on purpose. A custom section without contents: gcc gives `@nobits` to a section only when its name starts `.bss.`, and the default linker scripts fold `.bss.*` into `.bss`, so no portable spelling yields one; Task 7 covers it with a hand-built image. An `_Atomic` variable: whether DWARF keeps the qualifier depends on the DWARF version and strictness, so no row-independent expectation exists; Task 2 covers it with a double (ruling 2).

`tests/fixtures/elf/src/unit_a.c`:

```c
/* One of the two units that define a static of one name, share a structure through a header,
   and define two different structures under one tag; unit_b.c is the other. */
#include <stdint.h>

#include "shared.h"

#define USED __attribute__((used))

static uint16_t Twin USED = 0x1111;
Shared_t Shared_A;
struct Clash_s {
    uint8_t a;
} Clash_A;
```

`tests/fixtures/elf/src/unit_b.c`:

```c
/* The other of the two units unit_a.c describes. */
#include <stdint.h>

#include "shared.h"

#define USED __attribute__((used))

static uint16_t Twin USED = 0x2222;
Shared_t Shared_B;
struct Clash_s {
    uint16_t a;
    uint16_t b;
} Clash_B;
```

`tests/fixtures/elf/src/nodebug.c`:

```c
/* Compiled without -g: its variable is in the symbol table and in no DWARF. */
#include <stdint.h>

uint32_t Nodebug_Counter = 1;
```

- [ ] **Step 2: The image**

`docker/elf-fixtures.Dockerfile`:

```dockerfile
# The cross toolchains that build the ELF fixtures of `ddd tool from-elf`, which
# tests/fixtures/elf/ holds and the suite reads without Docker or a compiler: see
# build_elf_fixtures.py beside this file, and `docker compose run --rm elf-fixtures`.
#
# Pinned by digest rather than by tag. The fixtures are committed, and the manifest beside them
# records which compiler built each: a rebuild on a tag that has moved would change them for a
# reason nobody asked for. Every row's compiler is a Debian package, cross gcc for five targets
# and clang with lld for two more; binutils is here for its readelf, which reads every target's
# headers, symbols and DWARF and is the manifest's oracle.
FROM debian:trixie-slim@sha256:a99cfc517144bc59b1978475ec53b46ecabec7e43635402ee5b77cc54cd1b20a

RUN apt-get update \
    && apt-get install --no-install-recommends --yes \
        binutils \
        clang \
        gcc-aarch64-linux-gnu \
        gcc-arm-none-eabi \
        gcc-i686-linux-gnu \
        gcc-powerpc-linux-gnu \
        gcc-s390x-linux-gnu \
        gcc-x86-64-linux-gnu \
        lld \
        python3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /work
```

- [ ] **Step 3: The build script**

`docker/build_elf_fixtures.py`:

```python
#!/usr/bin/env python3
"""Build the ELF fixtures of ``ddd tool from-elf``, and the manifest the tests read them with.

Usage, from the repository root: ``docker compose run --rm elf-fixtures``

Each row of :data:`ROWS` compiles ``tests/fixtures/elf/src/`` with one toolchain and links it
into ``tests/fixtures/elf/<row>.elf``, beside a stripped copy of one row, a relocatable object,
and a copy of the ``armv7m`` row at ``examples/firmware/firmware.elf`` for the documentation's
re-run transcripts. The images are committed, so that the suite needs neither Docker nor a
compiler.

The manifest records what each toolchain itself says about its target - never what ddd's
reader says, which is what the tests check against it - and a hash of everything the images
were built from, so that a test can tell when they are stale. GNU readelf is the one tool used
for every row: it reads the headers, the symbols and the DWARF of any target's ELF, where nm
and objdump are built for one.

It runs inside the image of ``docker/elf-fixtures.Dockerfile`` and needs nothing but the
standard library there. The suite imports it too, for :func:`hashed`, and must be able to
without running anything.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests" / "fixtures" / "elf" / "src"
OUTPUT = ROOT / "tests" / "fixtures" / "elf"
DOCKERFILE = ROOT / "docker" / "elf-fixtures.Dockerfile"
EXAMPLE = ROOT / "examples" / "firmware" / "firmware.elf"
EXAMPLE_ROW = "armv7m"
STRIPPED_ROW = "x86_64"
UNITS = ("main", "unit_a", "unit_b")
UNDEBUGGED = "nodebug"
ENTRY = "fixture_entry"
COMMON = ("-O2", "-std=gnu11", "-ffreestanding", "-fno-common")
TLS = "FIXTURE_TLS"
FOLDED = "FIXTURE_FOLDED"


@dataclass(frozen=True)
class Row:
    """One image: its compiler, the flags naming its target, its DWARF, and how it links."""

    name: str
    compiler: tuple[str, ...]
    target: tuple[str, ...]
    dwarf: tuple[str, ...]
    link: tuple[str, ...]
    cases: tuple[str, ...] = (TLS, FOLDED)
    """The optional cases of ``main.c`` this row builds. ``FOLDED`` is gcc's alone: clang may
    drop the entry of a folded static rather than give it a ``DW_AT_const_value``."""


GNU_LINK = ("-static", "-no-pie")
CORTEX_M4 = ("-mcpu=cortex-m4", "-mthumb")
ROWS = (
    Row("x86_64", ("x86_64-linux-gnu-gcc",), ("-fPIE",), ("-gdwarf-5",), ("-static-pie",)),
    Row("i686", ("i686-linux-gnu-gcc",), (), ("-gdwarf-4",), GNU_LINK),
    Row("armv7m", ("arm-none-eabi-gcc",), CORTEX_M4, ("-gdwarf-4",), ()),
    Row("armv7m-dwarf2", ("arm-none-eabi-gcc",), CORTEX_M4, ("-gdwarf-2", "-gstrict-dwarf"), ()),
    Row(
        "armeb",
        ("arm-none-eabi-gcc",),
        ("-mcpu=cortex-r5", "-marm", "-mbig-endian"),
        ("-gdwarf-4",),
        (),
    ),
    Row("aarch64", ("aarch64-linux-gnu-gcc",), (), ("-gdwarf-5",), GNU_LINK),
    Row("powerpc", ("powerpc-linux-gnu-gcc",), (), ("-gdwarf-3",), GNU_LINK),
    Row("s390x", ("s390x-linux-gnu-gcc",), (), ("-gdwarf-5", "-gz=zlib"), GNU_LINK),
    Row(
        "riscv32",
        ("clang", "--target=riscv32-unknown-elf", "-march=rv32imac", "-mabi=ilp32"),
        (),
        ("-gdwarf-5",),
        ("-fuse-ld=lld",),
        cases=(TLS,),
    ),
    Row(
        "aarch64_be",
        ("clang", "--target=aarch64_be-none-elf"),
        (),
        ("-gdwarf-4",),
        ("-fuse-ld=lld",),
        cases=(TLS,),
    ),
)

_SYMBOL = re.compile(
    r"^\s*\d+:\s+[0-9a-f]+\s+(?P<size>0x[0-9a-f]+|\d+)\s+(?P<type>\w+)\s+\w+\s+\w+\s+"
    r"(?P<index>\S+)\s+(?P<name>\S+)$"
)
_SECTION = re.compile(r"^\s*\[\s*(?P<index>\d+)\]\s+(?P<name>\S+)\s+(?P<type>\S+)\s")


def digest(path: Path) -> str:
    """The SHA-256 of a text file with its line endings normalised, so that a checkout that
    converts them - git on Windows does, by default - is not read as a change."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def hashed() -> dict[str, str]:
    """What the images are built from, by path relative to the repository, and its digest."""
    paths = [*sorted(SOURCE.iterdir()), DOCKERFILE, Path(__file__).resolve()]
    return {path.relative_to(ROOT).as_posix(): digest(path) for path in paths}


def run(command: list[str], cwd: Path = SOURCE) -> str:
    """Run a command, failing loudly with its output when it fails."""
    done = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    if done.returncode != 0:
        msg = f"{' '.join(command)} failed:\n{done.stdout}{done.stderr}"
        raise SystemExit(msg)
    return done.stdout


def build(row: Row, work: Path) -> Path:
    """Compile and link one row; the image lands in ``work``."""
    defines = [f"-D{case}" for case in row.cases]
    prefix = f"-ffile-prefix-map={SOURCE}=."
    objects: list[str] = []
    for unit in UNITS:
        target = work / f"{row.name}-{unit}.o"
        run(
            [
                *row.compiler,
                *row.target,
                *COMMON,
                *row.dwarf,
                *defines,
                prefix,
                "-c",
                f"{unit}.c",
                "-o",
                str(target),
            ]
        )
        objects.append(str(target))
    target = work / f"{row.name}-{UNDEBUGGED}.o"
    run([*row.compiler, *row.target, *COMMON, "-c", f"{UNDEBUGGED}.c", "-o", str(target)])
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
        ]
    )
    return image


def macros(row: Row) -> dict[str, str]:
    """The macros the row's compiler predefines, by name."""
    text = run([*row.compiler, *row.target, "-dM", "-E", "-x", "c", "/dev/null"])
    found: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.split(maxsplit=2)
        if len(parts) >= 2 and parts[0] == "#define":
            found[parts[1]] = parts[2] if len(parts) == 3 else ""
    return found


def sections(image: Path) -> dict[str, tuple[str, str]]:
    """Every section of an image, by index: its name and its type."""
    found: dict[str, tuple[str, str]] = {}
    for line in run(["readelf", "-S", "-W", str(image)]).splitlines():
        match = _SECTION.match(line)
        if match is not None:
            found[match["index"]] = (match["name"], match["type"])
    return found


def variables(image: Path) -> list[dict[str, object]]:
    """Every object and thread-local symbol of an image: its section, whether that has
    contents, its size. A thread-local variable's symbol is of type TLS rather than OBJECT, and
    the tests read its section to hold the reader to leaving that section out."""
    table = sections(image)
    found: list[dict[str, object]] = []
    for line in run(["readelf", "-s", "-W", str(image)]).splitlines():
        match = _SYMBOL.match(line)
        if match is None or match["type"] not in ("OBJECT", "TLS") or match["index"] not in table:
            continue
        name, kind = table[match["index"]]
        found.append(
            {
                "name": match["name"],
                "section": name,
                "contents": kind != "NOBITS",
                "size": int(match["size"], 0),
            }
        )
    return sorted(found, key=lambda entry: (str(entry["name"]), str(entry["section"])))


def traits(row: Row, image: Path, found: list[dict[str, object]]) -> dict[str, object]:
    """What the row's toolchain says about its target, the answers the tests hold ddd to."""
    defined = macros(row)
    sizes = {str(entry["name"]): int(str(entry["size"])) for entry in found}
    order = defined["__BYTE_ORDER__"]
    dump = run(["readelf", "--debug-dump=info", str(image)])
    return {
        "byte_order": "big" if order == "__ORDER_BIG_ENDIAN__" else "little",
        "char_unsigned": "__CHAR_UNSIGNED__" in defined,
        "sizeof_long": int(defined["__SIZEOF_LONG__"]),
        "sizeof_long_double": int(defined["__SIZEOF_LONG_DOUBLE__"]),
        "pointer_size": int(defined["__SIZEOF_POINTER__"]),
        "sizeof_enum": sizes["Probe_Enum"],
        "uint64_alignment": sizes["Probe_Align"] - 8,
        "alignment_attribute": "DW_AT_alignment" in dump,
    }


def main() -> None:
    """Build every row, the two negative inputs and the example copy, then the manifest."""
    OUTPUT.mkdir(parents=True, exist_ok=True)
    rows: dict[str, object] = {}
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory)
        for row in ROWS:
            image = build(row, work)
            shutil.copyfile(image, OUTPUT / image.name)
            found = variables(image)
            rows[row.name] = {
                "compiler": run([row.compiler[0], "--version"]).splitlines()[0],
                "flags": [*row.compiler[1:], *row.target, *COMMON, *row.dwarf, *row.link],
                "cases": list(row.cases),
                "traits": traits(row, image, found),
                "variables": found,
            }
        run(
            [
                "x86_64-linux-gnu-strip",
                "--strip-debug",
                "-o",
                str(OUTPUT / "stripped.elf"),
                str(OUTPUT / f"{STRIPPED_ROW}.elf"),
            ]
        )
        run(
            [
                "x86_64-linux-gnu-gcc",
                *COMMON,
                "-gdwarf-5",
                f"-ffile-prefix-map={SOURCE}=.",
                "-c",
                "main.c",
                "-o",
                str(OUTPUT / "main.o"),
            ]
        )
    EXAMPLE.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(OUTPUT / f"{EXAMPLE_ROW}.elf", EXAMPLE)
    manifest = {"hashes": hashed(), "rows": rows}
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", "utf-8")
    print(f"wrote {len(ROWS)} rows into {OUTPUT.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: The compose service**

In `docker-compose.yml`, after the `gui-screenshots` service and before `volumes:`:

```yaml
  # docker compose run --rm elf-fixtures rebuilds the ELF images of `ddd tool from-elf` that
  # tests/fixtures/elf/ holds, with their manifest and the copy examples/firmware/ holds, out of
  # tests/fixtures/elf/src/ and the pinned cross toolchains of docker/elf-fixtures.Dockerfile. The
  # images are committed, so the suite needs neither Docker nor a compiler: this service is only
  # for changing them. Its image is its own rather than ddd:dev, and what it writes into the
  # checkout is handed back to whoever owns tests/fixtures/elf, since the image runs as root.
  elf-fixtures:
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
        python3 docker/build_elf_fixtures.py
        status=$$?
        chown -R "$$(stat -c %u:%g tests/fixtures/elf)" tests/fixtures/elf examples/firmware
        exit $$status
```

- [ ] **Step 5: Write the failing test**

`tests/test_elf_fixtures.py`:

```python
"""The committed ELF fixtures are the ones their committed sources build, as far as a test can
tell without a compiler, and they span what they are there to span.

The images are built in Docker (``docker compose run --rm elf-fixtures``) and committed, so
the suite runs where Docker cannot. What the suite cannot do is rebuild them; what it can do is
notice that what they were built from has changed since, which is what the hashes are for.
"""

from __future__ import annotations

import json

import pytest

from build_elf_fixtures import EXAMPLE, EXAMPLE_ROW, OUTPUT, ROWS, STRIPPED_ROW, hashed

MANIFEST = json.loads((OUTPUT / "manifest.json").read_text(encoding="utf-8"))
TRAITS = {
    "byte_order",
    "char_unsigned",
    "sizeof_long",
    "sizeof_long_double",
    "pointer_size",
    "sizeof_enum",
    "uint64_alignment",
    "alignment_attribute",
}


def test_the_images_are_built_from_what_is_committed() -> None:
    assert MANIFEST["hashes"] == hashed(), (
        "tests/fixtures/elf/ was built from other sources than the ones committed: rebuild it "
        "with 'docker compose run --rm elf-fixtures' and commit what it writes"
    )


def test_every_row_is_built_and_described() -> None:
    assert sorted(MANIFEST["rows"]) == sorted(row.name for row in ROWS)
    for row in ROWS:
        assert (OUTPUT / f"{row.name}.elf").is_file()


@pytest.mark.parametrize("row", sorted(MANIFEST["rows"]))
def test_every_row_states_the_traits_the_tests_read(row: str) -> None:
    assert set(MANIFEST["rows"][row]["traits"]) == TRAITS


def test_the_matrix_spans_both_byte_orders_both_widths_and_both_compilers() -> None:
    rows = MANIFEST["rows"].values()
    assert {row["traits"]["byte_order"] for row in rows} == {"little", "big"}
    assert {row["traits"]["pointer_size"] for row in rows} == {4, 8}
    assert any("clang" in row["compiler"] for row in rows)
    assert any("gcc" in row["compiler"] for row in rows)


def test_the_example_image_is_the_row_it_copies() -> None:
    assert EXAMPLE.read_bytes() == (OUTPUT / f"{EXAMPLE_ROW}.elf").read_bytes()


def test_the_two_negative_inputs_are_there() -> None:
    assert (OUTPUT / "stripped.elf").is_file()
    assert (OUTPUT / "main.o").is_file()
    assert STRIPPED_ROW in MANIFEST["rows"]
```

- [ ] **Step 6: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_elf_fixtures.py --no-cov`
Expected: FAIL at collection - `FileNotFoundError` for `tests/fixtures/elf/manifest.json`.

- [ ] **Step 7: Build the fixtures**

Run, from the worktree root:

```bash
docker compose -p ddd-toolbox run --rm elf-fixtures
```

Expected: `wrote 10 rows into tests/fixtures/elf`, exit 0. The first run builds `ddd-elf-fixtures:dev`, which downloads the toolchains; later runs reuse it. Then check the result against the trial build this plan was written from - every trait below was measured there:

```bash
.venv/bin/python -c "import json; m = json.load(open('tests/fixtures/elf/manifest.json')); [print(f'{k:14}', v['traits'], v['cases']) for k, v in m['rows'].items()]"
```

| row | byte order | `char` unsigned | `long` | `long double` | pointer | enum | `uint64` alignment | `DW_AT_alignment` | cases |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `x86_64` | little | no | 8 | 16 | 8 | 4 | 8 | yes | TLS, FOLDED |
| `i686` | little | no | 4 | 12 | 4 | 4 | 4 | yes | TLS, FOLDED |
| `armv7m` | little | yes | 4 | 8 | 4 | 1 | 8 | yes | TLS, FOLDED |
| `armv7m-dwarf2` | little | yes | 4 | 8 | 4 | 1 | 8 | **no** | TLS, FOLDED |
| `armeb` | big | yes | 4 | 8 | 4 | 1 | 8 | yes | TLS, FOLDED |
| `aarch64` | little | yes | 8 | 16 | 8 | 4 | 8 | yes | TLS, FOLDED |
| `powerpc` | big | yes | 4 | 16 | 4 | 4 | 8 | yes | TLS, FOLDED |
| `s390x` | big | yes | 8 | 16 | 8 | 4 | 8 | yes | TLS, FOLDED |
| `riscv32` | little | yes | 4 | 16 | 4 | 4 | 8 | yes | TLS |
| `aarch64_be` | big | yes | 8 | 16 | 8 | 4 | 8 | yes | TLS |

A row that answers differently is not an error to fix in the table: it is what that toolchain says, and every later test reads the manifest rather than this table. Report the difference.

Check the sizes, and that nothing else changed:

```bash
du -ch tests/fixtures/elf/*.elf tests/fixtures/elf/main.o tests/fixtures/elf/manifest.json examples/firmware/firmware.elf | tail -1
git status --short
```

The trial build measured about 490 KB in total, the manifest being about 70 KB of it. `git status` must list the new files and `docker-compose.yml` only; every new file must be owned by you (`ls -l tests/fixtures/elf`), not by root.

- [ ] **Step 8: Run the test to verify it passes, then the whole suite**

Run: `.venv/bin/python -m pytest tests/test_elf_fixtures.py --no-cov` - Expected: PASS, 15 tests.
Run: `.venv/bin/python -m pytest > build/gate.txt 2>&1; echo "EXIT=$?"; tail -3 build/gate.txt` - Expected: `EXIT=0`, the baseline's count plus 15, at 100 %.
Run: `.venv/bin/ruff check .; echo "RUFF=$?"` and `.venv/bin/ruff format --check .; echo "FMT=$?"` - both 0: the build script is linted like every python file of the repository.

- [ ] **Step 9: Ablate the guard**

In a scratch worktree under `build/`, with pytest run from inside it: append a comment line to `tests/fixtures/elf/src/nodebug.c`. `test_the_images_are_built_from_what_is_committed` must fail, with the message naming the compose command. Then replace a `\n` of `main.c` with `\r\n`: the test must still pass - the line-ending normalisation is what lets a Windows checkout pass.

- [ ] **Step 10: Commit**

```bash
git add tests/fixtures/elf docker/elf-fixtures.Dockerfile docker/build_elf_fixtures.py docker-compose.yml examples/firmware/firmware.elf tests/test_elf_fixtures.py
git commit -m "$(printf 'build the fixture matrix of ddd tool from-elf in docker, and commit it\n\nTen images - little and big endian, 32 and 64 bit, gcc and clang, DWARF 2 to\n5, compressed and not, ET_EXEC and ET_DYN - out of one C source that holds a\nvariable per case of the design, and a manifest of what each toolchain says\nabout its target. The suite reads the committed files, so it needs neither\nDocker nor a compiler; a hash guard says when they have gone stale.\n\nCo-Authored-By: <your model> <noreply@anthropic.com>')"
```

---

### Task 2: the reader's model, and its readers over two protocols

**Files:**
- Create: `src/ddd/elf.py` (everything but pyelftools, which is Task 3's)
- Test: `tests/test_elf.py`

**Interfaces:**
- Consumes: nothing - this module imports the standard library only in this task, and nothing of `ddd` ever.
- Produces: everything listed under *Task 2* in *Interfaces Between Tasks*.

The model is plain frozen data, so the translator's tests can build it by hand, and the readers work on two protocols, so this task's tests reach every branch through doubles: an `Attr` for pyelftools' `AttributeValue`, a `Die` for its `DIE`, a `FakeUnit` whose expressions are already `(operation, arguments)` pairs. Task 3 then proves pyelftools and the ten real images fit the same protocols.

- [ ] **Step 1: Write the failing tests**

`tests/test_elf.py`:

```python
"""The reader of ``ddd tool from-elf``: DWARF entries to the C model (with doubles here), and
linked images to it (over the fixture matrix, from Task 3 on)."""

from __future__ import annotations

import itertools
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from ddd.elf import (
    DECLARED_ONLY,
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
    Declared,
    Enum,
    FileTable,
    Image,
    Member,
    Qualified,
    Section,
    Struct,
    Typedef,
    Unsupported,
    Variable,
    file_path,
    read_variables,
    size_of,
)

_OFFSETS = itertools.count(1)


@dataclass(frozen=True)
class Attr:
    """A double of pyelftools' ``AttributeValue``: the reader reads its value and its form."""

    value: Any
    form: str = "DW_FORM_data1"


@dataclass(eq=False)
class Die:
    """A double of pyelftools' ``DIE``, as :class:`ddd.elf.Entry` asks for one."""

    tag: str | int | None
    attributes: dict[str, Attr] = field(default_factory=dict)
    children: list[Die] = field(default_factory=list)
    references: dict[str, Die] = field(default_factory=dict)
    offset: int = field(default_factory=lambda: next(_OFFSETS))

    def iter_children(self) -> Iterator[Die]:
        return iter(self.children)

    def get_DIE_from_attribute(self, name: str) -> Die:  # noqa: N802 - pyelftools' name
        return self.references[name]


@dataclass
class FakeUnit:
    """A double of a compilation unit: its expressions are already ``(operation, arguments)``
    pairs, and its ``.debug_addr`` and file table are plain mappings."""

    top: Die
    name: str = "unit.c"
    files: dict[int, str] = field(default_factory=lambda: {1: "unit.c"})
    addresses: dict[int, int] = field(default_factory=dict)

    def operations(self, expression: Any) -> list[tuple[str, list[Any]]]:
        return list(expression)

    def indexed_address(self, index: int) -> int:
        return self.addresses[index]

    def file(self, index: int) -> str | None:
        return self.files.get(index)


def die(
    tag: str | int,
    *children: Die,
    of: Die | None = None,
    specification: Die | None = None,
    **attributes: Any,
) -> Die:
    """A DWARF entry: ``of`` is its ``DW_AT_type``, ``specification`` its declaration."""
    made = Die(
        tag,
        {name: value if isinstance(value, Attr) else Attr(value) for name, value in attributes.items()},
        list(children),
    )
    for name, target in (("DW_AT_type", of), ("DW_AT_specification", specification)):
        if target is not None:
            made.attributes[name] = Attr(target.offset, "DW_FORM_ref4")
            made.references[name] = target
    return made


U8 = die(
    "DW_TAG_base_type",
    DW_AT_name=b"unsigned char",
    DW_AT_encoding=DW_ATE_UNSIGNED_CHAR,
    DW_AT_byte_size=1,
)
U8_TYPE = Base("unsigned char", DW_ATE_UNSIGNED_CHAR, 1)
AT = [("DW_OP_addr", [0x100])]
DECLARATION = Attr(True, "DW_FORM_flag_present")


def variable(
    name: bytes | str = b"v", *, of: Die | None = None, located: bool = True, **attributes: Any
) -> Die:
    attributes["DW_AT_name"] = name
    if located:
        attributes.setdefault("DW_AT_location", Attr(AT, "DW_FORM_exprloc"))
    return die("DW_TAG_variable", of=U8 if of is None else of, **attributes)


def read(*entries: Die, big_endian: bool = False, **unit: Any) -> tuple[Variable, ...]:
    return read_variables(
        [FakeUnit(die("DW_TAG_compile_unit", *entries), **unit)], big_endian=big_endian
    )


def type_of(entry: Die, *, big_endian: bool = False) -> CType:
    (found,) = read(variable(of=entry), big_endian=big_endian)
    return found.type


def subrange(**attributes: Any) -> Die:
    return die("DW_TAG_subrange_type", **attributes)


def enumerator(name: bytes, value: int, form: str = "DW_FORM_data1") -> Die:
    return die("DW_TAG_enumerator", DW_AT_name=name, DW_AT_const_value=Attr(value, form))


def member(name: bytes | None, of: Die, **attributes: Any) -> Die:
    if name is not None:
        attributes["DW_AT_name"] = name
    return die("DW_TAG_member", of=of, **attributes)


class TestTypes:
    def test_a_base_type_is_its_name_encoding_and_size(self) -> None:
        entry = die(
            "DW_TAG_base_type",
            DW_AT_name=b"unsigned int",
            DW_AT_encoding=DW_ATE_UNSIGNED,
            DW_AT_byte_size=4,
        )
        assert type_of(entry) == Base("unsigned int", DW_ATE_UNSIGNED, 4)

    def test_a_typedef_keeps_its_name_over_what_it_stands_for(self) -> None:
        assert type_of(die("DW_TAG_typedef", of=U8, DW_AT_name=b"uint8_t")) == Typedef(
            "uint8_t", U8_TYPE
        )

    def test_const_and_volatile_are_one_qualifier_each(self) -> None:
        entry = die("DW_TAG_const_type", of=die("DW_TAG_volatile_type", of=U8))
        assert type_of(entry) == Qualified(Qualified(U8_TYPE, volatile=True), const=True)

    def test_restrict_is_passed_through(self) -> None:
        assert type_of(die("DW_TAG_restrict_type", of=U8)) == U8_TYPE

    def test_a_qualifier_of_nothing_qualifies_void(self) -> None:
        assert type_of(die("DW_TAG_const_type")) == Qualified(Unsupported("void"), const=True)

    @pytest.mark.parametrize(
        ("tag", "what"),
        [
            ("DW_TAG_pointer_type", "a pointer"),
            ("DW_TAG_union_type", "a union"),
            ("DW_TAG_class_type", "a class"),
            ("DW_TAG_reference_type", "a reference"),
            ("DW_TAG_rvalue_reference_type", "a reference"),
            ("DW_TAG_subroutine_type", "a function"),
            ("DW_TAG_ptr_to_member_type", "a pointer to member"),
            ("DW_TAG_atomic_type", "an _Atomic type"),
            ("DW_TAG_unspecified_type", "an unspecified type"),
        ],
    )
    def test_a_type_ddd_has_no_word_for_is_unsupported_by_name(self, tag: str, what: str) -> None:
        assert type_of(die(tag, of=U8)) == Unsupported(what)

    def test_a_tag_nobody_named_is_unsupported_by_its_number(self) -> None:
        assert type_of(die(0x4109)) == Unsupported("a type DWARF tags 16649")

    def test_an_array_states_its_extents_in_c_order(self) -> None:
        entry = die(
            "DW_TAG_array_type", subrange(DW_AT_upper_bound=1), subrange(DW_AT_count=3), of=U8
        )
        assert type_of(entry) == Array(U8_TYPE, (2, 3))

    def test_a_lower_bound_counts(self) -> None:
        entry = die(
            "DW_TAG_array_type", subrange(DW_AT_lower_bound=1, DW_AT_upper_bound=4), of=U8
        )
        assert type_of(entry) == Array(U8_TYPE, (4,))

    def test_a_child_that_is_no_subrange_is_passed_over(self) -> None:
        entry = die(
            "DW_TAG_array_type", die("DW_TAG_enumeration_type"), subrange(DW_AT_count=2), of=U8
        )
        assert type_of(entry) == Array(U8_TYPE, (2,))

    @pytest.mark.parametrize(
        "bounds",
        [
            {},
            {"DW_AT_upper_bound": Attr([0x91, 0x00], "DW_FORM_exprloc")},
            {"DW_AT_lower_bound": Attr([0x91, 0x00], "DW_FORM_exprloc"), "DW_AT_upper_bound": 3},
            {"DW_AT_count": 0},
        ],
        ids=["flexible", "variable length", "variable lower bound", "zero length"],
    )
    def test_an_array_without_a_fixed_positive_size_is_unsupported(
        self, bounds: dict[str, Any]
    ) -> None:
        assert type_of(die("DW_TAG_array_type", subrange(**bounds), of=U8)) == Unsupported(
            "an array without a fixed size of at least one element"
        )

    def test_an_array_without_any_subrange_is_unsupported(self) -> None:
        assert type_of(die("DW_TAG_array_type", of=U8)) == Unsupported(
            "an array without a fixed size of at least one element"
        )

    def test_an_enum_takes_its_sign_from_its_underlying_type(self) -> None:
        signed_char = die(
            "DW_TAG_base_type",
            DW_AT_name=b"signed char",
            DW_AT_encoding=DW_ATE_SIGNED_CHAR,
            DW_AT_byte_size=1,
        )
        entry = die(
            "DW_TAG_enumeration_type",
            enumerator(b"LOW", 0xFE),
            of=die("DW_TAG_typedef", of=signed_char, DW_AT_name=b"int8_t"),
            DW_AT_name=b"Level_e",
            DW_AT_byte_size=1,
        )
        assert type_of(entry) == Enum("Level_e", 1, True, (("LOW", -2),))

    def test_an_underlying_type_that_is_no_base_type_leaves_the_encoding_to_decide(
        self,
    ) -> None:
        entry = die(
            "DW_TAG_enumeration_type",
            enumerator(b"A", 200),
            of=die("DW_TAG_pointer_type"),
            DW_AT_encoding=DW_ATE_UNSIGNED,
            DW_AT_byte_size=1,
        )
        assert type_of(entry) == Enum(None, 1, False, (("A", 200),))

    def test_without_an_underlying_type_the_encoding_decides(self) -> None:
        entry = die(
            "DW_TAG_enumeration_type",
            enumerator(b"A", 0xFF),
            DW_AT_encoding=DW_ATE_SIGNED,
            DW_AT_byte_size=1,
        )
        assert type_of(entry) == Enum(None, 1, True, (("A", -1),))

    def test_with_neither_a_negative_enumerator_makes_an_enum_signed(self) -> None:
        """What strict DWARF 2 leaves to go on: the armv7m-dwarf2 row's Enum_Signed."""
        entry = die(
            "DW_TAG_enumeration_type",
            enumerator(b"NEG", -2, "DW_FORM_sdata"),
            enumerator(b"POS", 3),
            DW_AT_byte_size=4,
        )
        assert type_of(entry) == Enum(None, 4, True, (("NEG", -2), ("POS", 3)))

    def test_with_neither_and_no_negative_enumerator_an_enum_is_unsigned(self) -> None:
        entry = die(
            "DW_TAG_enumeration_type",
            enumerator(b"BIG", 0xFF),
            enumerator(b"NONE", 0, "DW_FORM_sdata"),
            DW_AT_byte_size=1,
        )
        assert type_of(entry) == Enum(None, 1, False, (("BIG", 255), ("NONE", 0)))

    def test_an_enumerator_in_a_form_of_its_own_sign_is_read_as_it_is(self) -> None:
        entry = die(
            "DW_TAG_enumeration_type",
            enumerator(b"WIDE", 255, "DW_FORM_udata"),
            DW_AT_encoding=DW_ATE_SIGNED,
            DW_AT_byte_size=2,
        )
        assert type_of(entry) == Enum(None, 2, True, (("WIDE", 255),))

    def test_an_enum_declared_but_never_defined_is_unsupported(self) -> None:
        entry = die("DW_TAG_enumeration_type", DW_AT_declaration=DECLARATION)
        assert type_of(entry) == Unsupported("an enum declared but never defined")

    def test_an_enum_knows_where_it_is_declared(self) -> None:
        entry = die(
            "DW_TAG_enumeration_type",
            enumerator(b"A", 1),
            DW_AT_byte_size=4,
            DW_AT_decl_file=1,
            DW_AT_decl_line=7,
        )
        assert type_of(entry) == Enum(None, 4, False, (("A", 1),), Declared("unit.c", 7))

    def test_a_structure_lists_its_members_where_they_start(self) -> None:
        entry = die(
            "DW_TAG_structure_type",
            member(b"a", U8, DW_AT_data_member_location=0),
            member(b"b", U8, DW_AT_data_member_location=1),
            DW_AT_name=b"Pair_s",
            DW_AT_byte_size=2,
        )
        assert type_of(entry) == Struct(
            "Pair_s", 2, (Member("a", U8_TYPE, 0), Member("b", U8_TYPE, 8))
        )

    def test_a_member_offset_given_as_an_expression_is_read(self) -> None:
        """DW_OP_plus_uconst 300, its operand two bytes of ULEB128, as DWARF 2 spells it."""
        entry = die(
            "DW_TAG_structure_type",
            member(b"far", U8, DW_AT_data_member_location=Attr([0x23, 0xAC, 0x02], "DW_FORM_block1")),
            DW_AT_byte_size=301,
        )
        assert type_of(entry) == Struct(None, 301, (Member("far", U8_TYPE, 2400),))

    def test_a_member_offset_given_as_another_expression_is_unknown(self) -> None:
        entry = die(
            "DW_TAG_structure_type",
            member(b"odd", U8, DW_AT_data_member_location=Attr([0x10, 0x01], "DW_FORM_block1")),
            DW_AT_byte_size=1,
        )
        assert type_of(entry) == Struct(None, 1, (Member("odd", U8_TYPE, None),))

    def test_an_operand_cut_short_is_read_as_far_as_it_goes(self) -> None:
        """0x81 announces a second byte that never comes: the loop runs out of data rather
        than reaching a last byte, which is the one arc of it the other tests do not take."""
        entry = die(
            "DW_TAG_structure_type",
            member(b"cut", U8, DW_AT_data_member_location=Attr([0x23, 0x81], "DW_FORM_block1")),
            DW_AT_byte_size=2,
        )
        assert type_of(entry) == Struct(None, 2, (Member("cut", U8_TYPE, 8),))

    def test_a_member_without_an_offset_starts_the_structure(self) -> None:
        entry = die("DW_TAG_structure_type", member(b"only", U8), DW_AT_byte_size=1)
        assert type_of(entry) == Struct(None, 1, (Member("only", U8_TYPE, 0),))

    def test_dwarf_4_and_later_may_state_a_bitfield_s_offset_outright(self) -> None:
        entry = die(
            "DW_TAG_structure_type",
            member(b"b", U8, DW_AT_bit_size=2, DW_AT_data_bit_offset=5),
            DW_AT_byte_size=1,
        )
        assert type_of(entry) == Struct(None, 1, (Member("b", U8_TYPE, 5, 2),))

    @pytest.mark.parametrize(("big_endian", "bit_offset"), [(False, 1), (True, 5)])
    def test_older_dwarf_counts_a_bitfield_from_its_unit_s_most_significant_bit(
        self, big_endian: bool, bit_offset: int
    ) -> None:
        """``b`` of ``uint8_t a:2; uint8_t :3; uint8_t b:2`` starts at bit 5 on every target.
        gcc states it as DW_AT_bit_offset 1 in a one byte unit on a little endian one
        (measured, gcc 15 at DWARF 2), counting from the unit's most significant bit, which is
        its last; and as 5 on a big endian one, where that bit is the unit's first."""
        entry = die(
            "DW_TAG_structure_type",
            member(
                b"b",
                U8,
                DW_AT_bit_size=2,
                DW_AT_bit_offset=bit_offset,
                DW_AT_byte_size=1,
                DW_AT_data_member_location=0,
            ),
            DW_AT_byte_size=1,
        )
        assert type_of(entry, big_endian=big_endian) == Struct(
            None, 1, (Member("b", U8_TYPE, 5, 2),)
        )

    def test_a_bitfield_without_a_unit_size_takes_its_type_s(self) -> None:
        u16 = die(
            "DW_TAG_base_type",
            DW_AT_name=b"short unsigned int",
            DW_AT_encoding=DW_ATE_UNSIGNED,
            DW_AT_byte_size=2,
        )
        entry = die(
            "DW_TAG_structure_type",
            member(b"c", u16, DW_AT_bit_size=9, DW_AT_bit_offset=0, DW_AT_data_member_location=0),
            DW_AT_byte_size=2,
        )
        assert type_of(entry) == Struct(
            None, 2, (Member("c", Base("short unsigned int", DW_ATE_UNSIGNED, 2), 7, 9),)
        )

    def test_a_bit_offset_without_a_width_leaves_the_byte_offset(self) -> None:
        entry = die(
            "DW_TAG_structure_type",
            member(b"x", U8, DW_AT_bit_offset=3, DW_AT_data_member_location=2),
            DW_AT_byte_size=3,
        )
        assert type_of(entry) == Struct(None, 3, (Member("x", U8_TYPE, 16),))

    def test_a_member_without_a_name_is_kept_anonymous(self) -> None:
        entry = die(
            "DW_TAG_structure_type", member(None, U8, DW_AT_data_member_location=0), DW_AT_byte_size=1
        )
        assert type_of(entry) == Struct(None, 1, (Member(None, U8_TYPE, 0),))

    def test_alignment_is_kept_where_dwarf_states_it(self) -> None:
        entry = die(
            "DW_TAG_structure_type",
            member(b"x", U8, DW_AT_data_member_location=0, DW_AT_alignment=8),
            DW_AT_byte_size=8,
            DW_AT_alignment=8,
        )
        assert type_of(entry) == Struct(
            None, 8, (Member("x", U8_TYPE, 0, alignment=8),), alignment=8
        )

    def test_a_child_that_is_no_member_is_passed_over(self) -> None:
        entry = die(
            "DW_TAG_structure_type",
            die("DW_TAG_subprogram"),
            member(b"x", U8, DW_AT_data_member_location=0),
            DW_AT_byte_size=1,
        )
        assert type_of(entry) == Struct(None, 1, (Member("x", U8_TYPE, 0),))

    def test_a_structure_declared_but_never_defined_is_unsupported(self) -> None:
        entry = die("DW_TAG_structure_type", DW_AT_declaration=DECLARATION)
        assert type_of(entry) == Unsupported("a structure declared but never defined")

    def test_a_structure_and_its_members_know_where_they_are_declared(self) -> None:
        entry = die(
            "DW_TAG_structure_type",
            member(b"x", U8, DW_AT_data_member_location=0, DW_AT_decl_file=1, DW_AT_decl_line=4),
            DW_AT_byte_size=1,
            DW_AT_decl_file=1,
            DW_AT_decl_line=3,
        )
        assert type_of(entry) == Struct(
            None,
            1,
            (Member("x", U8_TYPE, 0, declared_at=Declared("unit.c", 4)),),
            declared_at=Declared("unit.c", 3),
        )

    def test_a_type_reached_twice_is_built_once(self) -> None:
        shared = die(
            "DW_TAG_structure_type", member(b"x", U8, DW_AT_data_member_location=0), DW_AT_byte_size=1
        )
        first, second = read(variable(b"a", of=shared), variable(b"b", of=shared))
        assert first.type is second.type


class TestVariables:
    def test_a_variable_has_its_name_unit_type_declaration_and_address(self) -> None:
        (found,) = read(variable(b"Gain", DW_AT_decl_file=1, DW_AT_decl_line=12))
        assert found == Variable("Gain", "unit.c", U8_TYPE, Declared("unit.c", 12), 0x100)

    def test_an_indexed_address_is_resolved_through_the_unit(self) -> None:
        location = Attr([("DW_OP_addrx", [3])], "DW_FORM_exprloc")
        (found,) = read(variable(DW_AT_location=location), addresses={3: 0x2000})
        assert found.address == 0x2000

    @pytest.mark.parametrize("operation", ["DW_OP_form_tls_address", "DW_OP_GNU_push_tls_address"])
    def test_a_thread_local_variable_has_no_address(self, operation: str) -> None:
        location = Attr([("DW_OP_const8u", [0]), (operation, [])], "DW_FORM_exprloc")
        (found,) = read(variable(DW_AT_location=location))
        assert (found.address, found.missing) == (None, THREAD_LOCAL)

    @pytest.mark.parametrize(
        "location",
        [
            Attr(0x40, "DW_FORM_sec_offset"),
            Attr([("DW_OP_fbreg", [-8])], "DW_FORM_exprloc"),
            Attr([], "DW_FORM_exprloc"),
        ],
        ids=["location list", "frame relative", "empty"],
    )
    def test_a_location_that_is_not_one_address_is_no_address(self, location: Attr) -> None:
        (found,) = read(variable(DW_AT_location=location))
        assert (found.address, found.missing) == (None, NOT_AN_ADDRESS)

    def test_a_variable_the_compiler_folded_has_no_address(self) -> None:
        (found,) = read(variable(located=False, DW_AT_const_value=7))
        assert (found.address, found.missing) == (None, FOLDED)

    def test_a_variable_without_location_or_value_was_removed(self) -> None:
        (found,) = read(variable(located=False))
        assert (found.address, found.missing) == (None, REMOVED)

    def test_a_variable_without_a_location_the_symbol_table_calls_thread_local_is(self) -> None:
        """What aarch64's DWARF leaves for a thread-local variable: no location at all."""
        units = [FakeUnit(die("DW_TAG_compile_unit", variable(b"Counter", located=False)))]
        (found,) = read_variables(units, big_endian=False, thread_local=frozenset({"Counter"}))
        assert (found.address, found.missing) == (None, THREAD_LOCAL)

    def test_a_declaration_is_dropped_where_something_defines_its_name(self) -> None:
        declared = variable(b"Elsewhere", located=False, DW_AT_declaration=DECLARATION)
        (found,) = read(declared, variable(b"Elsewhere"))
        assert found.address == 0x100

    def test_a_declaration_is_kept_where_nothing_defines_its_name(self) -> None:
        (found,) = read(variable(b"Nowhere", located=False, DW_AT_declaration=DECLARATION))
        assert (found.address, found.missing) == (None, DECLARED_ONLY)

    def test_a_name_declared_by_two_units_is_kept_once(self) -> None:
        units = [
            FakeUnit(
                die(
                    "DW_TAG_compile_unit",
                    variable(b"Nowhere", located=False, DW_AT_declaration=DECLARATION),
                )
            )
            for _ in range(2)
        ]
        assert len(read_variables(units, big_endian=False)) == 1

    def test_a_definition_completing_a_declaration_takes_its_name_type_and_file_from_it(
        self,
    ) -> None:
        declaration = variable(
            b"Spec",
            located=False,
            DW_AT_declaration=DECLARATION,
            DW_AT_decl_file=1,
            DW_AT_decl_line=4,
        )
        definition = die(
            "DW_TAG_variable",
            specification=declaration,
            DW_AT_decl_line=5,
            DW_AT_location=Attr(AT, "DW_FORM_exprloc"),
        )
        (found,) = read(declaration, definition)
        assert found == Variable("Spec", "unit.c", U8_TYPE, Declared("unit.c", 5), 0x100)

    def test_an_entry_without_a_name_is_passed_over(self) -> None:
        assert read(die("DW_TAG_variable", of=U8, DW_AT_location=Attr(AT, "DW_FORM_exprloc"))) == ()

    def test_only_the_top_of_a_unit_is_read(self) -> None:
        assert read(die("DW_TAG_subprogram", variable(b"Local"), DW_AT_name=b"f")) == ()

    def test_a_variable_without_a_type_is_void(self) -> None:
        (found,) = read(
            die("DW_TAG_variable", DW_AT_name=b"v", DW_AT_location=Attr(AT, "DW_FORM_exprloc"))
        )
        assert found.type == Unsupported("void")

    def test_a_declaration_the_file_table_does_not_hold_is_none(self) -> None:
        (found,) = read(variable(DW_AT_decl_file=9, DW_AT_decl_line=3))
        assert found.declared_at is None

    def test_a_declaration_without_a_line_is_none(self) -> None:
        (found,) = read(variable(DW_AT_decl_file=1))
        assert found.declared_at is None

    def test_a_name_may_arrive_as_text(self) -> None:
        (found,) = read(variable("Text"))
        assert found.name == "Text"


class TestFileTable:
    def test_no_table_names_no_file(self) -> None:
        assert file_path(None, 1) is None

    def test_dwarf_5_counts_from_zero_with_directory_zero_the_compilation_directory(self) -> None:
        table = FileTable(5, (("main.c", 0), ("shared.h", 1)), ("/work/src", "include"), "/x")
        assert (file_path(table, 0), file_path(table, 1)) == ("/work/src/main.c", "include/shared.h")

    def test_older_dwarf_counts_from_one_and_takes_directory_zero_from_the_unit(self) -> None:
        table = FileTable(4, (("main.c", 0), ("shared.h", 1)), ("include",), ".")
        assert (file_path(table, 0), file_path(table, 1), file_path(table, 2)) == (
            None,
            "main.c",
            "include/shared.h",
        )

    def test_an_index_past_the_table_names_no_file(self) -> None:
        assert file_path(FileTable(5, (("main.c", 0),), (".",), "."), 1) is None

    def test_a_directory_index_past_the_table_is_left_out(self) -> None:
        assert file_path(FileTable(5, (("main.c", 7),), (".",), "."), 0) == "main.c"

    @pytest.mark.parametrize("name", ["/abs/main.c", "C:/proj/main.c", "C:\\proj\\main.c"])
    def test_an_absolute_name_ignores_its_directory(self, name: str) -> None:
        table = FileTable(5, ((name, 0),), ("/elsewhere",), ".")
        assert file_path(table, 0) == name.replace("\\", "/")

    def test_backslashes_become_slashes(self) -> None:
        table = FileTable(5, (("src\\main.c", 0),), ("C:\\proj",), ".")
        assert file_path(table, 0) == "C:/proj/src/main.c"


class TestSizes:
    def test_a_size_follows_qualifiers_typedefs_and_arrays(self) -> None:
        assert size_of(Qualified(Typedef("t", Array(U8_TYPE, (2, 3))), const=True)) == 6

    def test_an_enum_and_a_structure_have_their_own(self) -> None:
        assert (size_of(Enum(None, 1, False, ())), size_of(Struct(None, 12, ()))) == (1, 12)

    def test_what_the_model_does_not_describe_has_none(self) -> None:
        assert size_of(Unsupported("a pointer")) is None
        assert size_of(Array(Unsupported("a pointer"), (2,))) is None


IMAGE = Image(
    Path("hand.elf"),
    "little",
    (),
    (Section(".data", 0x100, 4, 0x10), Section(".bss", 0x200, 4, None)),
    frozenset(),
    bytes(range(32)),
)


class TestImage:
    def test_a_read_takes_bytes_out_of_the_section_s_contents(self) -> None:
        assert IMAGE.read(0x101, 2) == bytes([0x11, 0x12])

    def test_a_section_without_contents_holds_no_bytes(self) -> None:
        assert IMAGE.read(0x200, 4) is None

    def test_a_read_past_the_end_of_a_section_is_none(self) -> None:
        assert IMAGE.read(0x102, 4) is None

    def test_an_address_outside_every_section_is_none(self) -> None:
        assert IMAGE.read(0x300, 1) is None
        assert IMAGE.section_of(0x300) is None

    def test_the_section_holding_an_address_is_the_one_that_spans_it(self) -> None:
        found = IMAGE.section_of(0x103)
        assert found is not None
        assert found.name == ".data"
        assert IMAGE.section_of(0x104) is None
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_elf.py --no-cov`
Expected: FAIL at collection - `ModuleNotFoundError: No module named 'ddd.elf'`.

- [ ] **Step 3: Implement**

`src/ddd/elf.py`:

```python
"""The C variables of a linked ELF image, read from its DWARF debug information.

This module knows nothing of DDD. It imports pyelftools and the standard library and nothing
else, so that reading an address map straight out of an image - planned in section 6 of
``SPEC.md`` - can use it without the toolbox; ``tests/test_backends.py`` holds it to that.

What it offers is a small model of C types - :class:`Base`, :class:`Enum`, :class:`Struct`,
:class:`Array`, :class:`Qualified`, :class:`Typedef` and :class:`Unsupported` - and the
variables of static storage an image holds, each with its type, its address and where its
source declared it. Every variation of DWARF stops here: versions 2 to 5, gcc's spellings and
clang's, compressed sections. A type this module cannot describe becomes an
:class:`Unsupported` node where it occurs rather than an exception, so a caller can name the
place and go on with everything else.

The readers work on two narrow protocols, :class:`Entry` and :class:`Unit`. pyelftools' DIEs
satisfy the first and :class:`_PyelftoolsUnit` the second, and so do a test's doubles: the
branches no C compiler produces are reached that way.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Final, Literal, Protocol

DW_ATE_BOOLEAN: Final = 0x02
DW_ATE_COMPLEX_FLOAT: Final = 0x03
DW_ATE_FLOAT: Final = 0x04
DW_ATE_SIGNED: Final = 0x05
DW_ATE_SIGNED_CHAR: Final = 0x06
DW_ATE_UNSIGNED: Final = 0x07
DW_ATE_UNSIGNED_CHAR: Final = 0x08

SIGNED_ENCODINGS: Final = frozenset({DW_ATE_SIGNED, DW_ATE_SIGNED_CHAR})

DECLARED_ONLY: Final = "it is only declared here, and defined nowhere in the image"
FOLDED: Final = "the compiler replaced it by its value, and gave it no storage"
REMOVED: Final = "the compiler removed its storage"
THREAD_LOCAL: Final = "it is thread-local, with an address of its own in every thread"
NOT_AN_ADDRESS: Final = "its location is not a fixed address"

_DW_OP_PLUS_UCONST: Final = 0x23
_TLS_OPERATIONS: Final = frozenset({"DW_OP_form_tls_address", "DW_OP_GNU_push_tls_address"})
_DATA_WIDTHS: Final = {
    "DW_FORM_data1": 8,
    "DW_FORM_data2": 16,
    "DW_FORM_data4": 32,
    "DW_FORM_data8": 64,
}
"""The forms whose constant carries no sign of its own, by width in bits: an enumerator of a
signed enum written in one of them is sign-extended from that width."""

_UNSUPPORTED: Final = {
    "DW_TAG_pointer_type": "a pointer",
    "DW_TAG_union_type": "a union",
    "DW_TAG_class_type": "a class",
    "DW_TAG_reference_type": "a reference",
    "DW_TAG_rvalue_reference_type": "a reference",
    "DW_TAG_subroutine_type": "a function",
    "DW_TAG_ptr_to_member_type": "a pointer to member",
    "DW_TAG_atomic_type": "an _Atomic type",
    "DW_TAG_unspecified_type": "an unspecified type",
}


class ElfReadError(ValueError):
    """An image this module cannot read at all; the message names the file and says why."""


@dataclass(frozen=True, slots=True)
class Declared:
    """Where a source declared something: the file as DWARF names it, and the line."""

    path: str
    line: int


@dataclass(frozen=True, slots=True)
class Base:
    """A base type: DWARF's spelling of it, its ``DW_ATE_*`` encoding and its size in bytes."""

    name: str
    encoding: int
    size: int


@dataclass(frozen=True, slots=True)
class Enum:
    """An enumeration: its tag, if it has one, its size, its sign and its enumerators in order."""

    tag: str | None
    size: int
    signed: bool
    enumerators: tuple[tuple[str, int], ...]
    declared_at: Declared | None = None


@dataclass(frozen=True, slots=True)
class Member:
    """One member of a structure, where it starts in bits, and its width if it is a bitfield."""

    name: str | None
    type: CType
    bit_offset: int | None
    """From the start of the structure; None where DWARF gives an offset this module cannot
    read, which only the layout warnings of a caller need."""

    bit_size: int | None = None
    alignment: int | None = None
    declared_at: Declared | None = None


@dataclass(frozen=True, slots=True)
class Struct:
    """A structure: its tag, if it has one, its size, its members in declaration order."""

    tag: str | None
    size: int
    members: tuple[Member, ...]
    alignment: int | None = None
    declared_at: Declared | None = None


@dataclass(frozen=True, slots=True)
class Array:
    """An array of ``element``, one extent per dimension in C order."""

    element: CType
    dimensions: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class Qualified:
    """``const`` or ``volatile`` on ``inner``; DWARF states each as an entry of its own."""

    inner: CType
    const: bool = False
    volatile: bool = False


@dataclass(frozen=True, slots=True)
class Typedef:
    """A typedef: its name, and the type it stands for."""

    name: str
    inner: CType


@dataclass(frozen=True, slots=True)
class Unsupported:
    """A type this module does not describe, ``what`` saying which, as "a pointer" does."""

    what: str


type CType = Base | Enum | Struct | Array | Qualified | Typedef | Unsupported


@dataclass(frozen=True, slots=True)
class Variable:
    """A variable of static storage a unit's DWARF describes at its top level."""

    name: str
    unit: str
    type: CType
    declared_at: Declared | None = None
    address: int | None = None
    missing: str = ""
    """Why ``address`` is None, as one of the constants of this module says it."""


@dataclass(frozen=True, slots=True)
class Section:
    """An allocated section: where it lies in memory, and where its bytes start in the file."""

    name: str
    address: int
    size: int
    offset: int | None
    """None for a section without contents (``SHT_NOBITS``), whose bytes the startup code
    provides rather than the image."""


@dataclass(frozen=True, slots=True)
class Image:
    """What a linked ELF image says about its C variables; :func:`open_image` fills it."""

    path: Path
    byte_order: Literal["little", "big"]
    variables: tuple[Variable, ...]
    sections: tuple[Section, ...]
    """The allocated sections, the thread-local ones left out: their addresses are offsets
    into a thread's block, and they overlap the sections that follow them in memory."""

    symbols: frozenset[str]
    """The names of the object symbols of the symbol table."""

    contents: bytes

    def section_of(self, address: int) -> Section | None:
        """The section holding ``address``, or None where none does."""
        for section in self.sections:
            if section.address <= address < section.address + section.size:
                return section
        return None

    def read(self, address: int, size: int) -> bytes | None:
        """The ``size`` bytes at ``address``, or None where the image does not hold them."""
        section = self.section_of(address)
        if section is None or section.offset is None:
            return None
        if address + size > section.address + section.size:
            return None
        start = section.offset + address - section.address
        return self.contents[start : start + size]


class Entry(Protocol):
    """What the readers ask of a DWARF entry. pyelftools' ``DIE`` is one."""

    @property
    def tag(self) -> str | int | None: ...

    @property
    def offset(self) -> int: ...

    @property
    def attributes(self) -> Mapping[str, Any]: ...

    def iter_children(self) -> Iterator[Entry]: ...

    def get_DIE_from_attribute(self, name: str) -> Entry: ...  # noqa: N802 - pyelftools' name


class Unit(Protocol):
    """What the variable reader asks of a compilation unit."""

    @property
    def name(self) -> str: ...

    @property
    def top(self) -> Entry: ...

    def operations(self, expression: Sequence[int]) -> list[tuple[str, list[Any]]]:
        """A location expression, as ``(operation name, arguments)`` pairs."""
        ...

    def indexed_address(self, index: int) -> int:
        """The address ``.debug_addr`` holds at ``index`` for this unit."""
        ...

    def file(self, index: int) -> str | None:
        """The path ``DW_AT_decl_file`` ``index`` names, or None where the table has none."""
        ...


@dataclass(frozen=True, slots=True)
class FileTable:
    """A unit's file table, as plain data: the entries, the directories and the unit's own
    directory, whose meaning depends on the DWARF version."""

    version: int
    files: tuple[tuple[str, int], ...]
    """Each file's name and the index of its directory."""

    directories: tuple[str, ...]
    compilation_directory: str


def file_path(table: FileTable | None, index: int) -> str | None:
    """The path a ``DW_AT_decl_file`` names, forward-slashed; None where the table has none.

    DWARF 5 counts files from 0, and its directory 0 is the compilation directory itself.
    Versions 2 to 4 count files from 1, with 0 meaning no file, and a directory index of 0
    meaning the unit's ``DW_AT_comp_dir``.
    """
    if table is None:
        return None
    if table.version >= 5:
        position = index
        directories = table.directories
    else:
        position = index - 1
        directories = (table.compilation_directory, *table.directories)
    if not 0 <= position < len(table.files):
        return None
    name, directory_index = table.files[position]
    name = name.replace("\\", "/")
    if name.startswith("/") or PureWindowsPath(name).is_absolute():
        return name
    directory = ""
    if 0 <= directory_index < len(directories):
        directory = directories[directory_index].replace("\\", "/")
    return str(PurePosixPath(directory, name))


def size_of(ctype: CType) -> int | None:
    """The size of ``ctype`` in bytes, or None for a type this module does not describe."""
    if isinstance(ctype, Base | Enum | Struct):
        return ctype.size
    if isinstance(ctype, Qualified | Typedef):
        return size_of(ctype.inner)
    if isinstance(ctype, Array):
        element = size_of(ctype.element)
        if element is None:
            return None
        count = 1
        for extent in ctype.dimensions:
            count *= extent
        return element * count
    return None


def read_variables(
    units: Iterable[Unit], *, big_endian: bool, thread_local: frozenset[str] = frozenset()
) -> tuple[Variable, ...]:
    """The variables at the top of every unit, each with its type, address and declaration.

    A name that is only ever declared is kept, as a variable without storage, so that a
    caller asking for it can say why it is not there; a name that some unit defines drops
    every declaration of it. ``thread_local`` names the thread-local symbols of the image: a
    target whose DWARF cannot state a thread-local address gives such a variable no location
    at all, and only the symbol table still says what it is.
    """
    types = _Types(big_endian=big_endian)
    defined: list[Variable] = []
    declared: dict[str, Variable] = {}
    for unit in units:
        for entry in unit.top.iter_children():
            if entry.tag != "DW_TAG_variable":
                continue
            variable = _variable(entry, unit, types, thread_local)
            if variable is None:
                continue
            if variable.missing == DECLARED_ONLY:
                declared.setdefault(variable.name, variable)
                continue
            defined.append(variable)
    names = {variable.name for variable in defined}
    defined.extend(variable for name, variable in declared.items() if name not in names)
    return tuple(defined)


def _variable(
    entry: Entry, unit: Unit, types: _Types, thread_local: frozenset[str]
) -> Variable | None:
    named = entry
    if "DW_AT_specification" in entry.attributes:
        named = entry.get_DIE_from_attribute("DW_AT_specification")
    name = _text(named.attributes.get("DW_AT_name"))
    if name is None:
        return None
    ctype = types.inner(named, unit)
    declared_at = _declared(entry, named, unit)
    attributes = entry.attributes
    address: int | None = None
    missing = ""
    if "DW_AT_location" in attributes:
        address, missing = _address(attributes["DW_AT_location"].value, unit)
    elif "DW_AT_const_value" in attributes:
        missing = FOLDED
    elif "DW_AT_declaration" in attributes:
        missing = DECLARED_ONLY
    elif name in thread_local:
        # aarch64's gcc 14 and clang 19 state no location at all for a thread-local variable
        # (the trial build); its symbol, of type STT_TLS, still says what it is.
        missing = THREAD_LOCAL
    else:
        missing = REMOVED
    return Variable(name, unit.name, ctype, declared_at, address, missing)


def _address(value: Any, unit: Unit) -> tuple[int | None, str]:
    if not isinstance(value, list):
        return None, NOT_AN_ADDRESS
    operations = unit.operations(value)
    names = [name for name, _ in operations]
    if names and names[-1] in _TLS_OPERATIONS:
        return None, THREAD_LOCAL
    if names == ["DW_OP_addr"]:
        return int(operations[0][1][0]), ""
    if names == ["DW_OP_addrx"]:
        return unit.indexed_address(int(operations[0][1][0])), ""
    return None, NOT_AN_ADDRESS


def _declared(entry: Entry, named: Entry, unit: Unit) -> Declared | None:
    """Where a variable is declared: the definition's own line and file where it states them,
    else those of the declaration it completes."""
    line = _either(entry, named, "DW_AT_decl_line")
    index = _either(entry, named, "DW_AT_decl_file")
    if not isinstance(line, int) or not isinstance(index, int):
        return None
    path = unit.file(index)
    if path is None:
        return None
    return Declared(path, line)


class _Types:
    """C types out of DWARF entries, each entry built once."""

    def __init__(self, *, big_endian: bool) -> None:
        self._big_endian = big_endian
        self._built: dict[int, CType] = {}

    def of(self, entry: Entry, unit: Unit) -> CType:
        built = self._built.get(entry.offset)
        if built is None:
            built = self._build(entry, unit)
            self._built[entry.offset] = built
        return built

    def inner(self, entry: Entry, unit: Unit) -> CType:
        """The type ``entry``'s ``DW_AT_type`` names; C's ``void`` where it names none."""
        if "DW_AT_type" not in entry.attributes:
            return Unsupported("void")
        return self.of(entry.get_DIE_from_attribute("DW_AT_type"), unit)

    def _build(self, entry: Entry, unit: Unit) -> CType:
        tag = entry.tag
        if tag == "DW_TAG_base_type":
            return Base(
                _text(entry.attributes.get("DW_AT_name")) or "",
                int(_value(entry, "DW_AT_encoding")),
                int(_value(entry, "DW_AT_byte_size")),
            )
        if tag == "DW_TAG_typedef":
            return Typedef(_text(entry.attributes.get("DW_AT_name")) or "", self.inner(entry, unit))
        if tag == "DW_TAG_const_type":
            return Qualified(self.inner(entry, unit), const=True)
        if tag == "DW_TAG_volatile_type":
            return Qualified(self.inner(entry, unit), volatile=True)
        if tag == "DW_TAG_restrict_type":
            # restrict qualifies a pointer only, and a pointer is refused whatever qualifies it.
            return self.inner(entry, unit)
        if tag == "DW_TAG_array_type":
            return self._array(entry, unit)
        if tag == "DW_TAG_enumeration_type":
            return self._enum(entry, unit)
        if tag == "DW_TAG_structure_type":
            return self._struct(entry, unit)
        return Unsupported(_UNSUPPORTED.get(str(tag), f"a type DWARF tags {tag}"))

    def _array(self, entry: Entry, unit: Unit) -> CType:
        dimensions: list[int] = []
        for child in entry.iter_children():
            if child.tag != "DW_TAG_subrange_type":
                continue
            extent = _extent(child)
            if extent is None or extent < 1:
                return Unsupported("an array without a fixed size of at least one element")
            dimensions.append(extent)
        if not dimensions:
            return Unsupported("an array without a fixed size of at least one element")
        return Array(self.inner(entry, unit), tuple(dimensions))

    def _enum(self, entry: Entry, unit: Unit) -> CType:
        if "DW_AT_declaration" in entry.attributes:
            return Unsupported("an enum declared but never defined")
        children = [child for child in entry.iter_children() if child.tag == "DW_TAG_enumerator"]
        signed = self._signed(entry, children, unit)
        return Enum(
            tag=_text(entry.attributes.get("DW_AT_name")),
            size=int(_value(entry, "DW_AT_byte_size")),
            signed=signed,
            enumerators=tuple(_enumerator(child, signed=signed) for child in children),
            declared_at=_declared(entry, entry, unit),
        )

    def _signed(self, entry: Entry, children: Sequence[Entry], unit: Unit) -> bool:
        """An enum's sign: its underlying type's, else its encoding's, else whether an
        enumerator is negative - which an old producer states and nothing else."""
        if "DW_AT_type" in entry.attributes:
            underlying = _core(self.inner(entry, unit))
            if isinstance(underlying, Base):
                return underlying.encoding in SIGNED_ENCODINGS
        encoding = _value(entry, "DW_AT_encoding")
        if isinstance(encoding, int):
            return encoding in SIGNED_ENCODINGS
        for child in children:
            attribute = child.attributes["DW_AT_const_value"]
            if attribute.form == "DW_FORM_sdata" and attribute.value < 0:
                return True
        return False

    def _struct(self, entry: Entry, unit: Unit) -> CType:
        if "DW_AT_declaration" in entry.attributes:
            return Unsupported("a structure declared but never defined")
        members = tuple(
            self._member(child, unit)
            for child in entry.iter_children()
            if child.tag == "DW_TAG_member"
        )
        return Struct(
            tag=_text(entry.attributes.get("DW_AT_name")),
            size=int(_value(entry, "DW_AT_byte_size")),
            members=members,
            alignment=_value(entry, "DW_AT_alignment"),
            declared_at=_declared(entry, entry, unit),
        )

    def _member(self, entry: Entry, unit: Unit) -> Member:
        ctype = self.inner(entry, unit)
        bit_size = _value(entry, "DW_AT_bit_size")
        return Member(
            name=_text(entry.attributes.get("DW_AT_name")),
            type=ctype,
            bit_offset=self._bit_offset(entry, ctype, bit_size),
            bit_size=bit_size,
            alignment=_value(entry, "DW_AT_alignment"),
            declared_at=_declared(entry, entry, unit),
        )

    def _bit_offset(self, entry: Entry, ctype: CType, bit_size: int | None) -> int | None:
        """Where a member starts, in bits from the start of its structure.

        DWARF 4 and later may state it outright. Before that, a bitfield states the byte its
        storage unit starts at, the unit's size, and its offset inside the unit counted from
        the unit's most significant bit - so from its first byte on a big endian target and
        from its last on a little endian one.
        """
        data_bit_offset = _value(entry, "DW_AT_data_bit_offset")
        if isinstance(data_bit_offset, int):
            return data_bit_offset
        location = _member_location(entry)
        if location is None:
            return None
        old = _value(entry, "DW_AT_bit_offset")
        if not isinstance(old, int) or bit_size is None:
            return location * 8
        storage = _value(entry, "DW_AT_byte_size")
        if not isinstance(storage, int):
            storage = size_of(ctype) or 0
        if self._big_endian:
            return location * 8 + old
        return location * 8 + storage * 8 - old - bit_size


def _member_location(entry: Entry) -> int | None:
    attribute = entry.attributes.get("DW_AT_data_member_location")
    if attribute is None:
        return 0
    value = attribute.value
    if isinstance(value, int):
        return value
    if isinstance(value, list) and len(value) >= 2 and value[0] == _DW_OP_PLUS_UCONST:
        return _uleb128(value[1:])
    return None


def _uleb128(data: Sequence[int]) -> int:
    result = 0
    for shift, byte in enumerate(data):
        result |= (byte & 0x7F) << (7 * shift)
        if not byte & 0x80:
            break
    return result


def _extent(entry: Entry) -> int | None:
    count = _value(entry, "DW_AT_count")
    if isinstance(count, int):
        return count
    upper = _value(entry, "DW_AT_upper_bound")
    lower = _value(entry, "DW_AT_lower_bound")
    if lower is None:
        lower = 0
    if not isinstance(upper, int) or not isinstance(lower, int):
        return None
    return upper - lower + 1


def _enumerator(entry: Entry, *, signed: bool) -> tuple[str, int]:
    attribute = entry.attributes["DW_AT_const_value"]
    value = int(attribute.value)
    width = _DATA_WIDTHS.get(attribute.form)
    if signed and width is not None and value >= 1 << (width - 1):
        value -= 1 << width
    return _text(entry.attributes.get("DW_AT_name")) or "", value


def _core(ctype: CType) -> CType:
    while isinstance(ctype, Qualified | Typedef):
        ctype = ctype.inner
    return ctype


def _either(first: Entry, second: Entry, name: str) -> Any:
    if name in first.attributes:
        return first.attributes[name].value
    return _value(second, name)


def _value(entry: Entry, name: str) -> Any:
    attribute = entry.attributes.get(name)
    if attribute is None:
        return None
    return attribute.value


def _text(attribute: Any) -> str | None:
    if attribute is None:
        return None
    return _decoded(attribute.value)


def _decoded(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)
```

Every loop that can leave early has a test for each way out, because branch coverage counts the arc of a loop running out separately from the arc of a `break` or a `return` inside it: `_uleb128` is left by `break` after the multi-byte test's second byte and runs out in `test_an_operand_cut_short_is_read_as_far_as_it_goes`; `_array` returns early for a bad extent and runs out for a good array; `_signed` returns early on a negative enumerator and runs out without one; `Image.section_of` returns a section and runs out outside every one. `_decoded`'s `str` branch is what a double's name spells; pyelftools always gives `bytes`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_elf.py --no-cov`
Expected: PASS. Then the whole suite with coverage: `ddd/elf.py` at 100 % line and branch from these tests alone - in this task it holds no pyelftools code.

- [ ] **Step 5: The gates, and ablations**

`ruff check .`, `ruff format --check .` (let `ruff format` settle the test file's long lines first, then re-read what it changed), bare `mypy` - each 0. Then, in a scratch worktree: drop `"DW_TAG_atomic_type"` from `_UNSUPPORTED` (its parametrized case must die by name); make `_bit_offset`'s little endian arm return `location * 8 + old` (the `big_endian=False` case must die); change `_DATA_WIDTHS["DW_FORM_data1"]` to 16 (`test_an_enum_takes_its_sign_from_its_underlying_type` must die).

- [ ] **Step 6: Commit**

```bash
git add src/ddd/elf.py tests/test_elf.py
git commit -m "$(printf 'read c variables and their types out of dwarf entries, over two protocols\n\nThe model is plain frozen data and the readers ask a DIE and a unit for no\nmore than two small protocols, so every variation of DWARF - versions 2 to 5,\nbitfields stated either way, a definition completing a declaration - is\nreached here with doubles, before pyelftools comes in.\n\nCo-Authored-By: <your model> <noreply@anthropic.com>')"
```

---

### Task 3: pyelftools, `open_image`, and the reader over the whole matrix

**Files:**
- Create: `requirements-elf.txt`
- Modify: `pyproject.toml` (the `elf` extra, `dev` including it, the sdist's include list)
- Modify: `src/ddd/elf.py` (pyelftools: `open_image`, the unit adapter, the file table's reader)
- Modify: `tests/test_backends.py` (`TestLayering`: `ddd.elf` imports nothing of `ddd`)
- Test: `tests/test_elf.py`

**Interfaces:**
- Consumes: Task 1's images and manifest; Task 2's model and readers.
- Produces: `open_image(path: Path) -> Image`, raising `ElfReadError`; `file_table(program, compilation_directory) -> FileTable | None`.

The floor of the dependency is measured, not guessed: the reader draft this plan was written from read all ten trial rows identically under pyelftools 0.33 and 0.32, and 0.31, 0.30, 0.29, 0.28 and 0.27 refuse `has_dwarf_info(strict=True)`, which is what tells a stripped image from one with DWARF (`.eh_frame` alone counts as debug information otherwise). Step 6 re-measures it against the real tests.

- [ ] **Step 1: The dependency**

`requirements-elf.txt`:

```text
# What `ddd tool from-elf` reads ELF images and their DWARF with, installed by the `elf` extra
# (pip install 'ddd-tool[elf]') and by `dev`, so that every environment that runs the suite has
# it. Not a runtime dependency: the command imports it inside its handler, and says how to
# install it where it is missing. 0.32 is the first release whose has_dwarf_info takes strict,
# measured against the fixture matrix on 2026-09-30.
pyelftools>=0.32,<1
```

In `pyproject.toml`, `[tool.hatch.metadata.hooks.requirements_txt.optional-dependencies]` becomes:

```toml
[tool.hatch.metadata.hooks.requirements_txt.optional-dependencies]
dev = ["requirements-dev.txt", "requirements-elf.txt"]
docs = ["requirements-docs.txt"]
elf = ["requirements-elf.txt"]
```

and the sdist's `include` gains `"/requirements-elf.txt",` after `"/requirements-docs.txt",`. Then reinstall the worktree's package so its metadata knows the extra: `.venv/bin/python -m pip install --quiet -e '.[dev]'`.

- [ ] **Step 2: Write the failing tests**

In `tests/test_backends.py`, `TestLayering` gains:

```python
    def test_the_elf_reader_knows_nothing_of_ddd(self) -> None:
        """ddd.elf serves the toolbox today and, as SPEC.md section 6 plans, the reading of an
        address map straight out of an image tomorrow: it imports no ddd module, so that
        neither has to take the other with it."""
        assert imported_modules(SOURCE / "elf.py") == set()
```

In `tests/test_elf.py`, add `import json` to the standard library imports, `from elftools.elf.elffile import ELFFile` to the third-party ones, `ElfReadError`, `file_table` and `open_image` to the `ddd.elf` import, and append:

```python
FIXTURES = Path(__file__).parent / "fixtures" / "elf"
MANIFEST = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
MAIN = (FIXTURES / "src" / "main.c").read_text(encoding="utf-8").splitlines()


def line_of(text: str) -> int:
    """The line of main.c holding ``text``: the oracle for where a variable is declared."""
    (found,) = [number for number, line in enumerate(MAIN, start=1) if text in line]
    return found


def by_name(image: Image, name: str) -> Variable:
    (found,) = [variable for variable in image.variables if variable.name == name]
    return found


def core(ctype: CType) -> CType:
    while isinstance(ctype, Qualified | Typedef | Array):
        ctype = ctype.element if isinstance(ctype, Array) else ctype.inner
    return ctype


@pytest.fixture(scope="module", params=sorted(MANIFEST["rows"]))
def row(request: pytest.FixtureRequest) -> tuple[Image, dict[str, Any]]:
    """One row of the matrix, opened once for every test that reads it."""
    return open_image(FIXTURES / f"{request.param}.elf"), MANIFEST["rows"][request.param]


class TestTheMatrix:
    """Every row read against what its own toolchain said about it (the manifest)."""

    def test_the_byte_order_is_the_toolchain_s(self, row: tuple[Image, dict[str, Any]]) -> None:
        image, entry = row
        assert image.byte_order == entry["traits"]["byte_order"]

    def test_every_variable_is_in_the_section_the_symbol_table_puts_it_in(
        self, row: tuple[Image, dict[str, Any]]
    ) -> None:
        image, entry = row
        found: dict[str, set[tuple[str, bool]]] = {}
        for variable in image.variables:
            if variable.address is None:
                continue
            section = image.section_of(variable.address)
            assert section is not None, variable.name
            found.setdefault(variable.name, set()).add((section.name, section.offset is not None))
        expected: dict[str, set[tuple[str, bool]]] = {}
        for record in entry["variables"]:
            if record["name"] in found:
                expected.setdefault(record["name"], set()).add(
                    (record["section"], record["contents"])
                )
        assert found == expected

    def test_every_sized_variable_is_the_size_the_symbol_table_gives_it(
        self, row: tuple[Image, dict[str, Any]]
    ) -> None:
        image, entry = row
        sizes = {record["name"]: record["size"] for record in entry["variables"]}
        stored = [variable for variable in image.variables if variable.address is not None]
        unsized = {variable.name for variable in stored if size_of(variable.type) is None}
        assert unsized == {"Type_Pointer", "Type_Union"}
        for variable in stored:
            if variable.name not in unsized:
                assert size_of(variable.type) == sizes[variable.name], variable.name

    @pytest.mark.parametrize(
        ("name", "value"),
        [
            ("Meas_U16", 0x1234),
            ("Meas_Volatile", 0x12345678),
            ("Cal_Gain", 300),
            ("Type_U64", 0x0102030405060708),
            ("Static_Used", 0x0102),
        ],
    )
    def test_an_initial_value_reads_back_in_the_image_s_byte_order(
        self, row: tuple[Image, dict[str, Any]], name: str, value: int
    ) -> None:
        image, _ = row
        variable = by_name(image, name)
        assert variable.address is not None
        size = size_of(variable.type)
        assert size is not None
        raw = image.read(variable.address, size)
        assert raw is not None
        assert int.from_bytes(raw, image.byte_order) == value

    def test_char_long_and_long_double_are_what_the_target_makes_them(
        self, row: tuple[Image, dict[str, Any]]
    ) -> None:
        image, entry = row
        traits = entry["traits"]
        char = core(by_name(image, "Type_Char").type)
        assert isinstance(char, Base)
        unsigned = traits["char_unsigned"]
        assert char.encoding == (DW_ATE_UNSIGNED_CHAR if unsigned else DW_ATE_SIGNED_CHAR)
        assert size_of(by_name(image, "Type_Long").type) == traits["sizeof_long"]
        assert size_of(by_name(image, "Type_Long_Double").type) == traits["sizeof_long_double"]

    def test_an_enum_is_as_wide_as_the_target_makes_it_and_signed_where_its_values_are(
        self, row: tuple[Image, dict[str, Any]]
    ) -> None:
        """Review Focus 2: on strict DWARF 2 an enum states no underlying type and no
        encoding, and only its negative enumerator says it is signed."""
        image, entry = row
        state = core(by_name(image, "Enum_State").type)
        signed = core(by_name(image, "Enum_Signed").type)
        assert isinstance(state, Enum)
        assert isinstance(signed, Enum)
        width = entry["traits"]["sizeof_enum"]
        assert (state.size, state.signed) == (width, False)
        assert (signed.size, signed.signed) == (width, True)
        assert signed.enumerators == (("SIGNED_NEG", -2), ("SIGNED_POS", 3))

    def test_bitfields_start_at_the_same_bits_whatever_the_byte_order_or_the_dwarf(
        self, row: tuple[Image, dict[str, Any]]
    ) -> None:
        """Review Focus 1: DWARF 2 and 3 count DW_AT_bit_offset from the storage unit's most
        significant bit, so the conversion differs by byte order; the offsets must not."""
        image, _ = row
        gapped = core(by_name(image, "Layout_Gapped").type)
        padded = core(by_name(image, "Layout_Padded").type)
        assert isinstance(gapped, Struct)
        assert isinstance(padded, Struct)
        assert [(m.name, m.bit_offset, m.bit_size) for m in gapped.members] == [
            ("a", 0, 2),
            ("b", 5, 2),
            ("c", 7, 9),
        ]
        assert [(m.name, m.bit_offset, m.bit_size) for m in padded.members] == [
            ("a", 0, 7),
            ("b", 8, 2),
        ]

    def test_an_explicit_alignment_is_read_where_the_dwarf_states_it(
        self, row: tuple[Image, dict[str, Any]]
    ) -> None:
        """gcc on the Linux targets states it on the structure and on the member, gcc for
        arm-none-eabi and clang on the member alone (the trial build): the member is held to
        the trait, the structure may carry it or not."""
        image, entry = row
        aligned = core(by_name(image, "Layout_Aligned").type)
        assert isinstance(aligned, Struct)
        expected = 8 if entry["traits"]["alignment_attribute"] else None
        assert aligned.members[0].alignment == expected
        assert aligned.alignment in (expected, None)

    def test_thread_local_storage_has_no_address_and_its_sections_are_left_out(
        self, row: tuple[Image, dict[str, Any]]
    ) -> None:
        """Review Focus 5: .tbss shares its addresses with the section after it."""
        image, entry = row
        assert "FIXTURE_TLS" in entry["cases"], "every row builds the thread-local case"
        assert by_name(image, "Tls_Counter").missing == THREAD_LOCAL
        placed = {r["section"] for r in entry["variables"] if r["name"] == "Tls_Counter"}
        assert placed
        assert not placed & {section.name for section in image.sections}

    def test_a_folded_static_has_no_address_where_the_row_builds_one(
        self, row: tuple[Image, dict[str, Any]]
    ) -> None:
        image, entry = row
        names = {variable.name for variable in image.variables}
        assert ("Static_Folded" in names) == ("FIXTURE_FOLDED" in entry["cases"])
        if "Static_Folded" in names:
            assert by_name(image, "Static_Folded").missing == FOLDED

    def test_a_variable_of_a_unit_without_dwarf_is_in_the_symbol_table_only(
        self, row: tuple[Image, dict[str, Any]]
    ) -> None:
        image, _ = row
        assert "Nodebug_Counter" in image.symbols
        assert "Nodebug_Counter" not in {variable.name for variable in image.variables}

    def test_a_definition_completing_a_declaration_is_declared_at_its_own_line(
        self, row: tuple[Image, dict[str, Any]]
    ) -> None:
        image, _ = row
        assert by_name(image, "Cal_Declared_First").declared_at == Declared(
            "main.c", line_of("const uint16_t Cal_Declared_First = 0x1234;")
        )

    def test_a_static_two_units_define_is_two_variables(
        self, row: tuple[Image, dict[str, Any]]
    ) -> None:
        image, _ = row
        twins = sorted(variable.unit for variable in image.variables if variable.name == "Twin")
        assert twins == ["unit_a.c", "unit_b.c"]


class TestRefusals:
    """What open_image refuses, each in a sentence naming the file. Where the end of the
    sentence is pyelftools' own words about a damaged file, the test pins ours and leaves
    theirs to them."""

    def test_a_file_that_cannot_be_read_is_refused(self, tmp_path: Path) -> None:
        path = tmp_path / "missing.elf"
        with pytest.raises(ElfReadError) as refused:
            open_image(path)
        assert str(refused.value) == (
            f"cannot read '{path.as_posix()}': No such file or directory"
        )

    def test_a_file_that_is_not_elf_is_refused(self, tmp_path: Path) -> None:
        path = tmp_path / "notes.txt"
        path.write_bytes(b"not an image")
        with pytest.raises(ElfReadError) as refused:
            open_image(path)
        assert str(refused.value) == (
            f"'{path.as_posix()}' is not an ELF image this tool can read: "
            f"Magic number does not match"
        )

    def test_a_truncated_image_is_refused(self, tmp_path: Path) -> None:
        data = (FIXTURES / "x86_64.elf").read_bytes()
        path = tmp_path / "truncated.elf"
        path.write_bytes(data[: len(data) // 2])
        with pytest.raises(ElfReadError) as refused:
            open_image(path)
        assert str(refused.value).startswith(
            f"'{path.as_posix()}' is not an ELF image this tool can read: "
        )

    def test_debug_information_of_a_version_pyelftools_does_not_read_is_refused(
        self, tmp_path: Path
    ) -> None:
        data = bytearray((FIXTURES / "x86_64.elf").read_bytes())
        with (FIXTURES / "x86_64.elf").open("rb") as stream:
            offset = ELFFile(stream).get_section_by_name(".debug_info")["sh_offset"]
        # A unit's header: a four byte length, then its two byte version.
        data[offset + 4 : offset + 6] = (9).to_bytes(2, "little")
        path = tmp_path / "future.elf"
        path.write_bytes(bytes(data))
        with pytest.raises(ElfReadError) as refused:
            open_image(path)
        assert str(refused.value) == (
            f"'{path.as_posix()}' is not an ELF image this tool can read: "
            f"Expected supported DWARF version. Got '9'"
        )

    def test_an_image_without_dwarf_is_refused_naming_g(self) -> None:
        path = FIXTURES / "stripped.elf"
        with pytest.raises(ElfReadError) as refused:
            open_image(path)
        assert str(refused.value) == (
            f"'{path.as_posix()}' carries no DWARF debug information: build it with -g"
        )

    def test_a_relocatable_object_is_refused(self) -> None:
        path = FIXTURES / "main.o"
        with pytest.raises(ElfReadError) as refused:
            open_image(path)
        assert str(refused.value) == (
            f"'{path.as_posix()}' is a relocatable object, not a linked image: its addresses "
            f"and its initial values are not final until it is linked"
        )

    def test_an_elf_file_of_another_kind_is_refused(self, tmp_path: Path) -> None:
        data = bytearray((FIXTURES / "x86_64.elf").read_bytes())
        data[16:18] = (4).to_bytes(2, "little")  # e_type ET_CORE; the row is little endian
        path = tmp_path / "core.elf"
        path.write_bytes(bytes(data))
        with pytest.raises(ElfReadError) as refused:
            open_image(path)
        assert str(refused.value) == (
            f"'{path.as_posix()}' is an ELF file of type ET_CORE, not a linked image"
        )

    def test_a_unit_without_a_line_program_has_no_file_table(self) -> None:
        assert file_table(None, ".") is None
```

- [ ] **Step 3: Run them to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_elf.py tests/test_backends.py --no-cov`
Expected: FAIL at collection of `tests/test_elf.py` - `ImportError: cannot import name 'file_table' from 'ddd.elf'` (`ElfReadError` exists since Task 2). The layering test passes already, `ddd.elf` importing nothing of `ddd` from its first line; it is there to keep it so.

- [ ] **Step 4: Implement**

In `src/ddd/elf.py`, the imports become:

```python
from __future__ import annotations

import io
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Final, Literal, Protocol

from elftools.common.exceptions import DWARFError, ELFError
from elftools.dwarf.dwarf_expr import DWARFExprParser
from elftools.elf.constants import SH_FLAGS
from elftools.elf.elffile import ELFFile
from elftools.elf.sections import SymbolTableSection
```

and after `read_variables`, add:

```python
def open_image(path: Path) -> Image:
    """Read a linked ELF image and its DWARF; :class:`ElfReadError` says why one cannot be."""
    shown = path.as_posix()
    try:
        contents = path.read_bytes()
    except OSError as error:
        msg = f"cannot read '{shown}': {error.strerror}"
        raise ElfReadError(msg) from None
    try:
        return _image(path, contents)
    except (ELFError, DWARFError) as error:
        msg = f"'{shown}' is not an ELF image this tool can read: {error}"
        raise ElfReadError(msg) from None


def _image(path: Path, contents: bytes) -> Image:
    shown = path.as_posix()
    elf = ELFFile(io.BytesIO(contents))
    kind = elf.header["e_type"]
    if kind == "ET_REL":
        msg = (
            f"'{shown}' is a relocatable object, not a linked image: its addresses and its "
            f"initial values are not final until it is linked"
        )
        raise ElfReadError(msg)
    if kind not in ("ET_EXEC", "ET_DYN"):
        msg = f"'{shown}' is an ELF file of type {kind}, not a linked image"
        raise ElfReadError(msg)
    if not elf.has_dwarf_info(strict=True):
        msg = f"'{shown}' carries no DWARF debug information: build it with -g"
        raise ElfReadError(msg)
    dwarf = elf.get_dwarf_info(relocate_dwarf_sections=False, follow_links=False)
    units = [_PyelftoolsUnit(cu, dwarf) for cu in dwarf.iter_CUs()]
    variables = read_variables(
        units, big_endian=not elf.little_endian, thread_local=_symbols(elf, "STT_TLS")
    )
    return Image(
        path=path,
        byte_order="little" if elf.little_endian else "big",
        variables=variables,
        sections=_sections(elf),
        symbols=_symbols(elf, "STT_OBJECT"),
        contents=contents,
    )


def _sections(elf: ELFFile) -> tuple[Section, ...]:
    sections: list[Section] = []
    for section in elf.iter_sections():
        flags = section["sh_flags"]
        if not flags & SH_FLAGS.SHF_ALLOC or flags & SH_FLAGS.SHF_TLS:
            continue
        offset = None if section["sh_type"] == "SHT_NOBITS" else section["sh_offset"]
        sections.append(Section(section.name, section["sh_addr"], section["sh_size"], offset))
    return tuple(sections)


def _symbols(elf: ELFFile, kind: str) -> frozenset[str]:
    """The names of the symbols of type ``kind`` (``STT_OBJECT``, ``STT_TLS``) in any table."""
    names: set[str] = set()
    for section in elf.iter_sections():
        if isinstance(section, SymbolTableSection):
            names.update(
                symbol.name
                for symbol in section.iter_symbols()
                if symbol["st_info"]["type"] == kind
            )
    return frozenset(names)


class _PyelftoolsUnit:
    """A pyelftools compilation unit, as :class:`Unit` asks for one."""

    def __init__(self, cu: Any, dwarf: Any) -> None:
        self._cu = cu
        self._dwarf = dwarf
        self._parser = DWARFExprParser(cu.structs)
        self.top: Entry = cu.get_top_DIE()
        self.name = _text(self.top.attributes.get("DW_AT_name")) or ""
        self._files = file_table(
            dwarf.line_program_for_CU(cu), _text(self.top.attributes.get("DW_AT_comp_dir")) or ""
        )

    def operations(self, expression: Sequence[int]) -> list[tuple[str, list[Any]]]:
        return [(op.op_name, list(op.args)) for op in self._parser.parse_expr(expression)]

    def indexed_address(self, index: int) -> int:
        return int(self._dwarf.get_addr(self._cu, index))

    def file(self, index: int) -> str | None:
        return file_path(self._files, index)


def file_table(program: Any, compilation_directory: str) -> FileTable | None:
    """A pyelftools line program's file table as plain data; None for a unit without one."""
    if program is None:
        return None
    return FileTable(
        version=int(program["version"]),
        files=tuple(
            (_decoded(entry.name), int(entry.dir_index)) for entry in program["file_entry"]
        ),
        directories=tuple(_decoded(directory) for directory in program["include_directory"]),
        compilation_directory=compilation_directory,
    )
```

Where each branch of this code is reached, since no double does it: `_symbols`' symbol table by every row (`Nodebug_Counter` for `STT_OBJECT`, `Tls_Counter` for `STT_TLS`, which the `aarch64` and `aarch64_be` rows need - their DWARF gives a thread-local variable no location at all, measured in the trial build, and `read_variables` takes the symbol table's word for it); `_sections`' thread-local skip by every row's `.tbss`; its `SHT_NOBITS` offset by every `.bss`; `indexed_address` by the `riscv32` row, whose clang DWARF 5 locates variables through `DW_OP_addrx`; `file_table`'s version 5 and older tables by the rows of each; `ET_DYN` by the `x86_64` row, a static PIE. If coverage says one of these is missed, the matrix is not what this plan measured: report it.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_elf.py tests/test_backends.py --no-cov` - Expected: PASS.
Then the whole suite with coverage - `ddd/elf.py` at 100 % line and branch - and `ruff check .`, `ruff format --check .`, bare `mypy`, each 0. pyelftools 0.33 ships `py.typed`; the draft passed `mypy --strict` without an override, so none is added. If bare `mypy` disagrees, add an override for `ddd.elf` alone and say why in its comment.

- [ ] **Step 6: Re-measure the floor**

In a throwaway venv under `build/`, install the worktree with the floor and run the reader's tests:

```bash
python3.14 -m venv build/floor
build/floor/bin/python -m pip install --quiet -e '.[dev]' 'pyelftools==0.32'
build/floor/bin/python -m pytest tests/test_elf.py --no-cov; echo "FLOOR=$?"
build/floor/bin/python -m pip install --quiet 'pyelftools==0.31'
build/floor/bin/python -m pytest tests/test_elf.py --no-cov -x; echo "BELOW=$?"
```

Expected: `FLOOR=0`, and `BELOW=1` with a `TypeError` naming `strict`. Then `rm -rf build/floor`. If 0.32 fails a test, raise the floor to the oldest release that passes and say so in the report and in `requirements-elf.txt`'s comment.

- [ ] **Step 7: Ablations**

In a scratch worktree: drop `or flags & SH_FLAGS.SHF_TLS` from `_sections` (the thread-local test must die on the rows whose `.tbss` overlaps the section after it); make `_image` treat `ET_DYN` as refused (every `x86_64` test must die); reverse the `SHT_NOBITS` test in `_sections` (the section test must die).

- [ ] **Step 8: Commit**

```bash
git add requirements-elf.txt pyproject.toml src/ddd/elf.py tests/test_elf.py tests/test_backends.py
git commit -m "$(printf 'open linked elf images with pyelftools, an optional extra\n\nThe reader of the previous commit now reads real images: every row of the\nmatrix is held to what its own toolchain said about it - sections, sizes,\nbyte order, char, long, enums, bitfields, alignment, thread-local storage.\npyelftools is the elf extra and part of dev, never a runtime dependency; 0.32\nis its floor, measured.\n\nCo-Authored-By: <your model> <noreply@anthropic.com>')"
```

---

### Task 4: the toolbox's findings, and which variables the arguments name

**Files:**
- Create: `src/ddd/toolbox/__init__.py`, `src/ddd/toolbox/findings.py`, `src/ddd/toolbox/selection.py`
- Modify: `tests/test_backends.py` (`TestLayering`: the toolbox reaches no backend and no command line)
- Test: `tests/test_toolbox_from_elf.py`

**Interfaces:**
- Consumes: `Image`, `Variable`, `Declared` of Task 2; `DiagnosticBag`, `Location`, `Severity`, `where` of `ddd.diagnostics`.
- Produces: `FINDINGS`, `place`, `report`; `Wanted`, `wanted`, `select`.

The findings are not checks of the catalogue: `bag.add(..., severity=...)` states each one's severity, which is what keeps a `-W` off them, and `FINDINGS` is the one table of them - Task 9's documentation test reads it.

- [ ] **Step 1: Write the failing tests**

`tests/test_toolbox_from_elf.py`:

```python
"""The translator of ``ddd tool from-elf``, on hand-built images: which variables the
arguments name, how their types are spelled, their initial values, and DDD's own verdict on
the result. The reader has its own tests (``tests/test_elf.py``); here nothing is read from a
file, so every case is exactly the one its test names."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pytest

from ddd.diagnostics import CHECKS, DiagnosticBag, Location, Severity, where
from ddd.elf import (
    DW_ATE_UNSIGNED_CHAR,
    Base,
    CType,
    Declared,
    Image,
    Section,
    Variable,
)
from ddd.toolbox.findings import FINDINGS, place, report
from ddd.toolbox.selection import Wanted, select, wanted

U8 = Base("unsigned char", DW_ATE_UNSIGNED_CHAR, 1)
DATA = Section(".data", 0x100, 0x100, 0)


def image(
    *variables: Variable,
    sections: tuple[Section, ...] = (DATA,),
    contents: bytes = bytes(0x100),
    symbols: frozenset[str] = frozenset(),
    byte_order: Literal["little", "big"] = "little",
) -> Image:
    return Image(Path("hand.elf"), byte_order, variables, sections, symbols, contents)


def stored(
    name: str,
    ctype: CType = U8,
    *,
    unit: str = "unit.c",
    address: int | None = 0x100,
    line: int | None = None,
    missing: str = "",
) -> Variable:
    declared = Declared(unit, line) if line is not None else None
    return Variable(name, unit, ctype, declared, address, missing)


def found(bag: DiagnosticBag) -> list[tuple[str, Severity, str]]:
    return [(d.check, d.severity, d.message) for d in bag.sorted]


def chosen(img: Image, *arguments: str, bag: DiagnosticBag | None = None) -> list[str]:
    # Not `bag or DiagnosticBag()`: a bag has a length, so an empty one is false, and the
    # findings would go into a bag nobody reads.
    if bag is None:
        bag = DiagnosticBag()
    return [v.name for v in select(img, [wanted(a) for a in arguments], bag)]


class TestFindings:
    def test_no_finding_of_the_tool_is_a_check_of_the_catalogue(self) -> None:
        assert not set(FINDINGS) & set(CHECKS)

    @pytest.mark.parametrize(("check", "severity"), sorted(FINDINGS.items()))
    def test_a_finding_goes_in_with_the_severity_the_table_gives_it(
        self, check: str, severity: Severity
    ) -> None:
        bag = DiagnosticBag()
        report(bag, check, "a sentence", Location(Path("main.c"), line=3))
        assert found(bag) == [(check, severity, "a sentence")]

    def test_a_finding_about_a_declaration_is_shown_at_it(self) -> None:
        assert place(image(), Declared("main.c", 3)) == Location(Path("main.c"), line=3)

    def test_a_finding_about_what_dwarf_places_nowhere_is_shown_at_the_image(self) -> None:
        assert place(image(), None) == where(Path("hand.elf"))


class TestWanted:
    def test_a_name_is_matched_exactly(self) -> None:
        assert wanted("Cal_Gain") == Wanted("Cal_Gain", None, "Cal_Gain", False)

    def test_a_unit_narrows_a_glob(self) -> None:
        assert wanted("cal.c:Cal_*") == Wanted("cal.c:Cal_*", "cal.c", "Cal_*", True)

    def test_a_unit_keeps_its_drive_letter(self) -> None:
        assert wanted("C:/src/cal.c:Gain") == Wanted("C:/src/cal.c:Gain", "C:/src/cal.c", "Gain", False)

    @pytest.mark.parametrize("pattern", ["Cal_?", "Tab[12]", "*"])
    def test_every_glob_character_makes_a_glob(self, pattern: str) -> None:
        assert wanted(pattern).glob

    def test_a_unit_without_a_name_is_refused(self) -> None:
        with pytest.raises(ValueError) as refused:
            wanted("cal.c:")
        assert str(refused.value) == (
            "'cal.c:' names no variable: give a name or a pattern after the unit"
        )

    def test_a_colon_without_a_unit_is_refused(self) -> None:
        with pytest.raises(ValueError) as refused:
            wanted(":Gain")
        assert str(refused.value) == "':Gain' names no unit before its colon"


class TestSelect:
    def test_arguments_keep_their_order_a_glob_its_names_and_each_variable_comes_once(
        self,
    ) -> None:
        img = image(stored("Zeta"), stored("Alpha"), stored("Beta"))
        assert chosen(img, "Zeta", "*a", "Beta") == ["Zeta", "Alpha", "Beta"]

    def test_a_name_nothing_defines_is_missing(self) -> None:
        bag = DiagnosticBag()
        assert chosen(image(stored("Other")), "Gain", bag=bag) == []
        assert found(bag) == [
            (
                "elf-symbol-missing",
                Severity.ERROR,
                "the image's debug information holds no variable named 'Gain'",
            )
        ]
        assert bag.sorted[0].location == where(Path("hand.elf"))

    def test_a_name_only_the_symbol_table_holds_says_how_that_happens(self) -> None:
        bag = DiagnosticBag()
        chosen(image(symbols=frozenset({"Gain"})), "Gain", bag=bag)
        assert found(bag)[0][2] == (
            "the image's debug information holds no variable named 'Gain'; the symbol table "
            "holds it, so the unit defining it was built without debug information (-g)"
        )

    def test_a_glob_matching_nothing_is_missing_too(self) -> None:
        bag = DiagnosticBag()
        chosen(image(stored("Other")), "cal.c:Cal_*", bag=bag)
        assert found(bag) == [
            (
                "elf-symbol-missing",
                Severity.ERROR,
                "no variable of the image's debug information matches 'Cal_*' in unit 'cal.c'",
            )
        ]

    def test_a_unit_is_matched_whole_or_by_its_last_components(self) -> None:
        img = image(
            stored("Gain", unit="src/app/cal.c"),
            stored("Gain", unit="src/app/xcal.c"),
            stored("Rate", unit="src\\app\\cal.c"),
            stored("Mode", unit="cal.c"),
        )
        picked = select(img, [wanted("cal.c:*")], DiagnosticBag())
        assert [(v.name, v.unit) for v in picked] == [
            ("Gain", "src/app/cal.c"),
            ("Mode", "cal.c"),
            ("Rate", "src\\app\\cal.c"),
        ]

    def test_a_name_two_units_define_is_ambiguous_once_however_often_it_is_asked_for(
        self,
    ) -> None:
        bag = DiagnosticBag()
        img = image(
            stored("Twin", unit="unit_a.c", line=9),
            stored("Twin", unit="unit_b.c", line=8),
            stored("Tweed"),
        )
        assert chosen(img, "Tw*", "Twin", bag=bag) == ["Tweed"]
        (diagnostic,) = bag.sorted
        assert (diagnostic.check, diagnostic.message) == (
            "elf-symbol-ambiguous",
            "'Twin' names a variable in 2 units, 'unit_a.c', 'unit_b.c': prefix it with one, "
            "as 'unit_a.c:Twin'",
        )
        assert diagnostic.location == Location(Path("unit_a.c"), line=9)
        assert diagnostic.notes == (
            ("defined in 'unit_a.c'", Location(Path("unit_a.c"), line=9)),
            ("defined in 'unit_b.c'", Location(Path("unit_b.c"), line=8)),
        )

    def test_its_unit_resolves_an_ambiguous_name(self) -> None:
        img = image(stored("Twin", unit="unit_a.c"), stored("Twin", unit="unit_b.c"))
        assert chosen(img, "unit_b.c:Twin") == ["Twin"]

    def test_a_variable_without_storage_is_reported_once_with_its_reason(self) -> None:
        bag = DiagnosticBag()
        img = image(stored("Tls", address=None, missing="it is thread-local", line=4))
        assert chosen(img, "Tls", "T*", bag=bag) == []
        assert found(bag) == [
            ("elf-no-storage", Severity.ERROR, "'Tls' has no address in the image: it is thread-local")
        ]
        assert bag.sorted[0].location == Location(Path("unit.c"), line=4)
```

In `tests/test_backends.py`, `TestLayering` gains:

```python
    def test_the_toolbox_reaches_no_backend_and_no_command_line(self) -> None:
        """A tool turns one thing into another; where its output goes is cli.py's alone, and
        what DDD generates is none of its business."""
        for path in SOURCE.joinpath("toolbox").rglob("*.py"):
            leaked = sorted(
                module
                for module in imported_modules(path)
                if module.startswith(("ddd.backends", "ddd.cli"))
            )
            assert not leaked, f"{path.name} reaches into {leaked}"
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_toolbox_from_elf.py --no-cov`
Expected: FAIL at collection - `ModuleNotFoundError: No module named 'ddd.toolbox'`.

- [ ] **Step 3: Implement**

`src/ddd/toolbox/__init__.py`:

```python
"""The toolbox: tools run once, on the way into DDD or out of it, rather than in every build.

``ddd tool`` is their namespace on the command line (section 7.3 of ``SPEC.md``), and each
tool is a module here. :mod:`ddd.toolbox.from_elf` is the first: it describes the C variables
of a linked ELF image as DDD declarations.
"""
```

`src/ddd/toolbox/findings.py`:

```python
"""The findings ``ddd tool from-elf`` reports of its own, and where it shows them.

They are not checks of the project catalogue: ``ddd checks`` does not list them and ``-W``
does not take them, because they judge an image rather than a description. Each goes into the
run's bag with its severity stated, which is what keeps a severity policy off it, and the
documentation lists every one of them (``tests/test_documentation.py`` holds it to this
table).
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Final

from ddd.diagnostics import DiagnosticBag, Location, Severity, where
from ddd.elf import Declared, Image

FINDINGS: Final[dict[str, Severity]] = {
    "elf-symbol-missing": Severity.ERROR,
    "elf-symbol-ambiguous": Severity.ERROR,
    "elf-no-storage": Severity.ERROR,
    "elf-type-unsupported": Severity.ERROR,
    "elf-type-conflict": Severity.ERROR,
    "elf-init-unsupported": Severity.ERROR,
    "elf-init-dropped": Severity.WARNING,
    "elf-bitfield-gap": Severity.WARNING,
    "elf-alignment": Severity.WARNING,
    "elf-qualifier-dropped": Severity.WARNING,
    "elf-section": Severity.WARNING,
    "elf-name-synthesized": Severity.WARNING,
    "elf-types-omitted": Severity.WARNING,
    "elf-boolean-bitfield": Severity.INFO,
    "elf-not-inferred": Severity.INFO,
}


def place(image: Image, declared: Declared | None) -> Location:
    """Where a finding about something the image describes is shown: at its declaration in
    the C source, or at the image itself where DWARF names none.

    The declaration's path is the one the image recorded, so it is relative wherever the build
    mapped its prefix to a relative one; DDD cannot resolve it against a directory it does not
    know, and a finding that claimed an absolute path would name a file that is not there.
    """
    if declared is None:
        return where(image.path)
    return Location(Path(declared.path), line=declared.line)


def report(
    bag: DiagnosticBag,
    check: str,
    message: str,
    location: Location,
    notes: Iterable[tuple[str, Location | None]] = (),
) -> None:
    """Add one of this module's findings, with the severity :data:`FINDINGS` gives it."""
    bag.add(check, message, location, notes, severity=FINDINGS[check])
```

`src/ddd/toolbox/selection.py`:

```python
"""Which variables of an image the command line asks for (section 3.1 of the design)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from fnmatch import fnmatchcase
from typing import Final

from ddd.diagnostics import DiagnosticBag, where
from ddd.elf import Image, Variable
from ddd.toolbox.findings import place, report

_GLOB: Final = frozenset("*?[")


@dataclass(frozen=True, slots=True)
class Wanted:
    """One ``SYMBOL`` argument: a name or a glob, and the unit it is narrowed to, if any."""

    text: str
    unit: str | None
    pattern: str
    glob: bool


def wanted(text: str) -> Wanted:
    """Read one ``[UNIT:]PATTERN`` argument; a malformed one is a usage error.

    The argument is split at its last colon, which neither a C identifier nor a glob holds, so
    a unit spelled with a drive letter keeps it.
    """
    unit, colon, pattern = text.rpartition(":")
    if not pattern:
        msg = f"'{text}' names no variable: give a name or a pattern after the unit"
        raise ValueError(msg)
    if colon and not unit:
        msg = f"'{text}' names no unit before its colon"
        raise ValueError(msg)
    return Wanted(text, unit or None, pattern, not _GLOB.isdisjoint(pattern))


def select(image: Image, arguments: Sequence[Wanted], bag: DiagnosticBag) -> list[Variable]:
    """The variables the arguments name, in their order, each once; a glob's in name order.

    An argument naming nothing, a name several units define and a variable without storage
    are findings rather than usage errors, so that one run reports every one of them.
    """
    chosen: list[Variable] = []
    taken: set[tuple[str, str]] = set()
    judged: set[str] = set()
    for argument in arguments:
        matched = [
            variable
            for variable in image.variables
            if _in_unit(variable, argument.unit) and _matches(variable, argument)
        ]
        if not matched:
            report(bag, "elf-symbol-missing", _missing(argument, image), where(image.path))
            continue
        for name in sorted({variable.name for variable in matched}):
            group = sorted(
                (variable for variable in matched if variable.name == name),
                key=lambda variable: variable.unit,
            )
            if len(group) > 1:
                if name not in judged:
                    judged.add(name)
                    _report_ambiguous(name, group, image, bag)
                continue
            (variable,) = group
            if variable.address is None:
                if name not in judged:
                    judged.add(name)
                    report(
                        bag,
                        "elf-no-storage",
                        f"'{name}' has no address in the image: {variable.missing}",
                        place(image, variable.declared_at),
                    )
                continue
            key = (variable.name, variable.unit)
            if key not in taken:
                taken.add(key)
                chosen.append(variable)
    return chosen


def _in_unit(variable: Variable, unit: str | None) -> bool:
    if unit is None:
        return True
    spelled = variable.unit.replace("\\", "/")
    return spelled == unit or spelled.endswith(f"/{unit}")


def _matches(variable: Variable, argument: Wanted) -> bool:
    if argument.glob:
        return fnmatchcase(variable.name, argument.pattern)
    return variable.name == argument.pattern


def _missing(argument: Wanted, image: Image) -> str:
    within = ""
    if argument.unit is not None:
        within = f" in unit '{argument.unit}'"
    if argument.glob:
        return f"no variable of the image's debug information matches '{argument.pattern}'{within}"
    message = f"the image's debug information holds no variable named '{argument.pattern}'{within}"
    if argument.pattern in image.symbols:
        message += (
            "; the symbol table holds it, so the unit defining it was built without debug "
            "information (-g)"
        )
    return message


def _report_ambiguous(
    name: str, group: Sequence[Variable], image: Image, bag: DiagnosticBag
) -> None:
    units = ", ".join(f"'{variable.unit}'" for variable in group)
    report(
        bag,
        "elf-symbol-ambiguous",
        f"'{name}' names a variable in {len(group)} units, {units}: prefix it with one, "
        f"as '{group[0].unit}:{name}'",
        place(image, group[0].declared_at),
        [
            (f"defined in '{variable.unit}'", place(image, variable.declared_at))
            for variable in group
        ],
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_toolbox_from_elf.py tests/test_backends.py --no-cov` - Expected: PASS. Then the whole suite with coverage (`ddd/toolbox/findings.py` and `selection.py` at 100 %), `ruff check .`, `ruff format --check .` (format the test file first), bare `mypy` - each 0.

- [ ] **Step 5: Ablations**

In a scratch worktree: drop `"["` from `_GLOB` (the `Tab[12]` case dies); make `_in_unit` test `endswith(unit)` without the slash (the `xcal.c` row of the unit test dies); make `select` report ambiguity every time rather than once (the ambiguity test's single diagnostic dies).

- [ ] **Step 6: Commit**

```bash
git add src/ddd/toolbox tests/test_toolbox_from_elf.py tests/test_backends.py
git commit -m "$(printf 'select the variables ddd tool from-elf is asked for, and say which it cannot\n\nA name, a glob, or either narrowed to one unit, in the order they were given;\nwhat names nothing, what several units define and what has no storage are\nfindings of their own, outside the check catalogue, so that one run reports\nall of them.\n\nCo-Authored-By: <your model> <noreply@anthropic.com>')"
```

---

### Task 5: the C model in DDD's spelling

**Files:**
- Create: `src/ddd/toolbox/mapping.py`
- Test: `tests/test_toolbox_from_elf.py`

**Interfaces:**
- Consumes: Task 2's model and `size_of`; Task 4's `place` and `report`.
- Produces: `Shape`, `shape_of`, `datatype_of`, `described`, `Typed`, `Refusal`, `Mapper` (`typed`, `conflicts`, `types`).

Section 4.1 to 4.5 of the spec, on hand-built models. What DDD decides about the result is not restated here: Task 7 hands it to DDD's own loader and analysis. Two `assert`s in this module state invariants rather than branches (*What the gates cannot see*): a bitfield's type and every member's type are describable by the time `_layout` runs, because `_describe_struct` refuses the structure first otherwise.

- [ ] **Step 1: Write the failing tests**

In `tests/test_toolbox_from_elf.py`, add to the imports:

```python
from typing import Any

from ddd.elf import (
    DW_ATE_BOOLEAN,
    DW_ATE_COMPLEX_FLOAT,
    DW_ATE_FLOAT,
    DW_ATE_SIGNED,
    DW_ATE_SIGNED_CHAR,
    DW_ATE_UNSIGNED,
    Array,
    Enum,
    Member,
    Qualified,
    Struct,
    Typedef,
    Unsupported,
)
from ddd.toolbox.mapping import Mapper, Shape, Typed, datatype_of, described, shape_of
```

and append:

```python
U16 = Base("short unsigned int", DW_ATE_UNSIGNED, 2)
S32 = Base("int", DW_ATE_SIGNED, 4)
F32 = Base("float", DW_ATE_FLOAT, 4)
BOOL = Base("_Bool", DW_ATE_BOOLEAN, 1)
LONG_DOUBLE = Base("long double", DW_ATE_FLOAT, 16)
IDENTITY = {"kind": "identity"}
STATE = Enum("State_e", 4, False, (("OFF", 0), ("ON", 1)), Declared("main.c", 2))
PAIR = Struct(
    "Pair_s",
    2,
    (Member("a", U8, 0), Member("b", U8, 8)),
    declared_at=Declared("main.c", 10),
)
PAIR_ENTRY = {
    "type": "struct",
    "name": "Pair_s",
    "members": [
        {"name": "a", "member": "value", "datatype": "uint8", "conversion": IDENTITY},
        {"name": "b", "member": "value", "datatype": "uint8", "conversion": IDENTITY},
    ],
}


def mapped(
    ctype: CType, name: str = "v", *, bag: DiagnosticBag | None = None, mapper: Mapper | None = None
) -> Typed | None:
    if bag is None:
        bag = DiagnosticBag()
    if mapper is None:
        mapper = Mapper(image(), bag)
    return mapper.typed(stored(name, ctype, line=5))


def structure(tag: str | None, *members: Member, size: int = 4, **extra: Any) -> Struct:
    return Struct(tag, size, members, **extra)


class TestShapes:
    def test_qualifiers_and_dimensions_are_collected_on_the_way_to_the_core(self) -> None:
        ctype = Qualified(Typedef("Row_t", Array(Qualified(U8, const=True), (2, 3))), volatile=True)
        assert shape_of(ctype) == Shape(U8, (2, 3), const=True, volatile=True, name=None)

    def test_the_name_is_the_typedef_closest_to_the_core(self) -> None:
        assert shape_of(Typedef("Alias_t", Typedef("Pair_t", PAIR))).name == "Pair_t"

    @pytest.mark.parametrize(
        ("core", "datatype"),
        [
            (BOOL, "boolean"),
            (Base("_Bool", DW_ATE_BOOLEAN, 2), None),
            (Base("signed char", DW_ATE_SIGNED_CHAR, 1), "sint8"),
            (Base("long long unsigned int", DW_ATE_UNSIGNED, 8), "uint64"),
            (F32, "float32"),
            (Base("double", DW_ATE_FLOAT, 8), "float64"),
            (LONG_DOUBLE, None),
            (Base("complex float", DW_ATE_COMPLEX_FLOAT, 8), None),
            (Base("char8_t", 0x10, 1), None),
            (Enum(None, 2, True, ()), "sint16"),
            (Enum(None, 3, False, ()), None),
        ],
    )
    def test_a_datatype_holds_a_base_type_or_an_enum_of_its_encoding_and_size(
        self, core: Base | Enum, datatype: str | None
    ) -> None:
        assert datatype_of(core) == datatype

    @pytest.mark.parametrize(
        ("core", "words"),
        [
            (LONG_DOUBLE, "'long double', a floating point number of 16 bytes"),
            (Base("char8_t", 0x10, 1), "'char8_t', a value of DWARF encoding 0x10 of 1 byte"),
            (Enum(None, 3, False, ()), "an enum of 3 bytes"),
        ],
    )
    def test_what_no_datatype_holds_is_said_in_words(self, core: Base | Enum, words: str) -> None:
        assert described(core) == words


class TestScalars:
    def test_a_variable_is_a_measurement_of_its_datatype_under_the_identity(self) -> None:
        assert mapped(U8) == Typed("measurement", "uint8", None, (), IDENTITY, False, frozenset(), 1)

    @pytest.mark.parametrize(
        ("ctype", "kind", "dimensions", "volatile"),
        [
            (Qualified(U16, const=True), "parameter", (), False),
            (Array(Qualified(U16, const=True), (4,)), "value_block", (4,), False),
            (Array(U16, (2, 3)), "measurement", (2, 3), False),
            (Qualified(U16, volatile=True), "measurement", (), True),
            (Qualified(Qualified(U16, volatile=True), const=True), "parameter", (), True),
        ],
    )
    def test_const_decides_the_kind_and_the_shape_the_calibration_kind(
        self, ctype: CType, kind: str, dimensions: tuple[int, ...], volatile: bool
    ) -> None:
        result = mapped(ctype)
        assert result is not None
        assert (result.kind, result.dimensions, result.volatile, result.element_size) == (
            kind,
            dimensions,
            volatile,
            2,
        )

    def test_an_enum_is_its_datatype_under_an_enum_conversion_named_by_its_typedef(self) -> None:
        result = mapped(Typedef("State_t", STATE))
        assert result is not None
        assert (result.datatype, result.conversion, result.reaches) == (
            "uint32",
            {"kind": "enum", "name": "State_t", "enumerators": {"OFF": 0, "ON": 1}},
            frozenset({"State_t"}),
        )

    def test_an_enum_without_a_typedef_is_named_by_its_tag(self) -> None:
        result = mapped(STATE)
        assert result is not None
        assert result.conversion == {"kind": "enum", "name": "State_e", "enumerators": {"OFF": 0, "ON": 1}}

    def test_an_anonymous_enum_is_named_after_the_variable_and_says_so(self) -> None:
        bag = DiagnosticBag()
        result = mapped(Enum(None, 1, False, (("A", 1),), Declared("main.c", 3)), "Mode", bag=bag)
        assert result is not None
        assert result.conversion == {"kind": "enum", "name": "Mode_t", "enumerators": {"A": 1}}
        assert found(bag) == [
            (
                "elf-name-synthesized",
                Severity.WARNING,
                "an anonymous enum is named 'Mode_t', after the first thing that reaches it; "
                "rename it if the source has a better name",
            )
        ]
        assert bag.sorted[0].location == Location(Path("main.c"), line=3)

    @pytest.mark.parametrize(
        ("ctype", "message"),
        [
            (Unsupported("a pointer"), "'v' is a pointer, which DDD cannot state"),
            (
                LONG_DOUBLE,
                "'v' is 'long double', a floating point number of 16 bytes, which DDD cannot state",
            ),
            (Enum(None, 3, False, (("A", 1),)), "'v' is an enum of 3 bytes, which DDD cannot state"),
            (
                Array(Qualified(PAIR, const=True), (2,)),
                "'v' is a const array of structures, which DDD cannot state: a parameter has no "
                "dimensions, and a value block holds no structure",
            ),
        ],
    )
    def test_what_ddd_cannot_state_is_refused_at_the_variable(self, ctype: CType, message: str) -> None:
        bag = DiagnosticBag()
        assert mapped(ctype, bag=bag) is None
        assert found(bag) == [("elf-type-unsupported", Severity.ERROR, message)]
        assert bag.sorted[0].location == Location(Path("unit.c"), line=5)


class TestStructures:
    def test_a_structure_is_a_typename_and_one_entry_of_types(self) -> None:
        mapper = Mapper(image(), DiagnosticBag())
        assert mapped(PAIR, mapper=mapper) == Typed(
            "measurement", None, "Pair_s", (), None, False, frozenset({"Pair_s"}), 2
        )
        assert mapper.types({"Pair_s"}) == [PAIR_ENTRY]

    @pytest.mark.parametrize(
        ("ctype", "kind", "dimensions"),
        [(Qualified(PAIR, const=True), "parameter", ()), (Array(PAIR, (3,)), "measurement", (3,))],
    )
    def test_a_structured_object_is_a_measurement_or_a_parameter(
        self, ctype: CType, kind: str, dimensions: tuple[int, ...]
    ) -> None:
        result = mapped(ctype)
        assert result is not None
        assert (result.kind, result.typename, result.dimensions) == (kind, "Pair_s", dimensions)

    def test_a_structure_is_named_by_the_typedef_closest_to_it(self) -> None:
        result = mapped(Typedef("Alias_t", Typedef("Pair_t", PAIR)))
        assert result is not None
        assert result.typename == "Pair_t"

    def test_an_anonymous_structure_is_named_once_after_the_first_variable_reaching_it(self) -> None:
        bag = DiagnosticBag()
        mapper = Mapper(image(), bag)
        anonymous = structure(None, Member("x", U8, 0), size=1, declared_at=Declared("main.c", 7))
        first = mapped(anonymous, "First", mapper=mapper)
        second = mapped(anonymous, "Second", mapper=mapper)
        assert first is not None
        assert second is not None
        assert (first.typename, second.typename) == ("First_t", "First_t")
        assert found(bag) == [
            (
                "elf-name-synthesized",
                Severity.WARNING,
                "an anonymous structure is named 'First_t', after the first thing that reaches "
                "it; rename it if the source has a better name",
            )
        ]

    def test_members_are_values_arrays_nested_structures_enums_and_bitfields(self) -> None:
        bag = DiagnosticBag()
        mapper = Mapper(image(), bag)
        inner = structure(None, Member("lo", U8, 0), Member("hi", U8, 8), size=2)
        outer = structure(
            "Outer_s",
            Member("raw", Array(U16, (4,)), 0),
            Member("pair", inner, 64),
            Member("pairs", Array(inner, (2,)), 80),
            Member("state", Typedef("State_t", STATE), 128),
            Member("flags", U8, 160, 3),
            Member("mode", Typedef("State_t", STATE), 163, 2),
            Member("ready", BOOL, 165, 1, declared_at=Declared("main.c", 30)),
            size=24,
        )
        result = mapped(outer, mapper=mapper)
        assert result is not None
        assert result.reaches == frozenset({"Outer_s", "Outer_s_pair_t", "State_t"})
        state = {"kind": "enum", "name": "State_t", "enumerators": {"OFF": 0, "ON": 1}}
        assert mapper.types(result.reaches) == [
            {
                "type": "struct",
                "name": "Outer_s_pair_t",
                "members": [
                    {"name": "lo", "member": "value", "datatype": "uint8", "conversion": IDENTITY},
                    {"name": "hi", "member": "value", "datatype": "uint8", "conversion": IDENTITY},
                ],
            },
            {
                "type": "struct",
                "name": "Outer_s",
                "members": [
                    {
                        "name": "raw",
                        "member": "value",
                        "datatype": "uint16",
                        "conversion": IDENTITY,
                        "dimensions": [4],
                    },
                    {"name": "pair", "member": "value", "typename": "Outer_s_pair_t"},
                    {
                        "name": "pairs",
                        "member": "value",
                        "typename": "Outer_s_pair_t",
                        "dimensions": [2],
                    },
                    {"name": "state", "member": "value", "datatype": "uint32", "conversion": state},
                    {
                        "name": "flags",
                        "member": "bits",
                        "datatype": "uint8",
                        "conversion": IDENTITY,
                        "bits": 3,
                    },
                    {
                        "name": "mode",
                        "member": "bits",
                        "datatype": "uint32",
                        "conversion": state,
                        "bits": 2,
                    },
                    {
                        "name": "ready",
                        "member": "bits",
                        "datatype": "uint8",
                        "conversion": IDENTITY,
                        "bits": 1,
                    },
                ],
            },
        ]
        assert [(check, severity) for check, severity, _ in found(bag)] == [
            ("elf-name-synthesized", Severity.WARNING),
            ("elf-boolean-bitfield", Severity.INFO),
        ]
        assert found(bag)[1][2] == (
            "'Outer_s.ready' is a _Bool bitfield, described as a uint8 one of the same width: DDD "
            "refuses a boolean bitfield"
        )

    @pytest.mark.parametrize(
        ("member", "path", "what"),
        [
            (Member("ptr", Unsupported("a pointer"), 0), "Holder_s.ptr", "a pointer"),
            (Member(None, U8, 0), "Holder_s.<anonymous>", "an anonymous member"),
            (
                Member("far", LONG_DOUBLE, 0),
                "Holder_s.far",
                "'long double', a floating point number of 16 bytes",
            ),
            (Member("packed", PAIR, 0, 3), "Holder_s.packed", "a bitfield of a structure"),
            (Member("wide", Enum(None, 3, False, ()), 0, 2), "Holder_s.wide", "an enum of 3 bytes"),
        ],
    )
    def test_a_member_ddd_cannot_state_refuses_every_variable_reaching_it(
        self, member: Member, path: str, what: str
    ) -> None:
        bag = DiagnosticBag()
        mapper = Mapper(image(), bag)
        declared = Member(
            member.name, member.type, member.bit_offset, member.bit_size,
            declared_at=Declared("main.c", 21),
        )
        holder = structure("Holder_s", declared)
        assert mapped(holder, mapper=mapper) is None
        assert mapped(Array(holder, (2,)), "w", mapper=mapper) is None
        errors = [d for d in bag.sorted if d.check == "elf-type-unsupported"]
        assert [d.message for d in errors] == [
            f"'{name}' cannot be described: '{path}' is {what}, which DDD cannot state"
            for name in ("v", "w")
        ]
        assert errors[0].notes == (
            (f"'{path}' is declared here", Location(Path("main.c"), line=21)),
        )

    def test_a_refusal_deep_inside_a_nested_structure_names_the_member_it_occurs_at(self) -> None:
        bag = DiagnosticBag()
        inner = structure("Inner_s", Member("ptr", Unsupported("a pointer"), 0))
        assert mapped(structure("Outer_s", Member("inner", inner, 0)), bag=bag) is None
        assert found(bag) == [
            (
                "elf-type-unsupported",
                Severity.ERROR,
                "'v' cannot be described: 'Inner_s.ptr' is a pointer, which DDD cannot state",
            )
        ]

    def test_a_synthesised_name_that_is_taken_is_named_once_and_conflicts(self) -> None:
        """A variable ``S_m`` of one anonymous structure and a member ``m`` of ``S`` of
        another both synthesise ``S_m_t``: the name is announced once, and the two ways it is
        defined are a conflict, which refuses both (Task 7)."""
        bag = DiagnosticBag()
        mapper = Mapper(image(), bag)
        mapped(structure(None, Member("x", U8, 0), size=1), "S_m", mapper=mapper)
        mapped(structure("S", Member("m", structure(None, Member("y", U16, 0), size=2), 0)), mapper=mapper)
        assert [check for check, _, _ in found(bag)] == ["elf-name-synthesized"]
        assert set(mapper.conflicts()) == {"S_m_t"}

    def test_a_qualified_member_says_ddd_qualifies_whole_objects(self) -> None:
        bag = DiagnosticBag()
        holder = structure(
            "Q_s",
            Member("v", Qualified(U8, volatile=True), 0),
            Member("c", Qualified(U8, const=True), 8),
            Member("cv", Qualified(Qualified(U8, volatile=True), const=True), 16),
        )
        mapped(holder, bag=bag)
        assert [message for _, _, message in found(bag)] == [
            "'Q_s.v' is volatile in C, which DDD cannot state of a member: DDD qualifies whole "
            "objects",
            "'Q_s.c' is const in C, which DDD cannot state of a member: DDD qualifies whole "
            "objects",
            "'Q_s.cv' is const volatile in C, which DDD cannot state of a member: DDD qualifies "
            "whole objects",
        ]

    def test_one_structure_reached_by_two_variables_is_one_entry_described_once(self) -> None:
        bag = DiagnosticBag()
        mapper = Mapper(image(), bag)
        holder = structure("Q_s", Member("v", Qualified(U8, volatile=True), 0))
        mapped(holder, "a", mapper=mapper)
        mapped(holder, "b", mapper=mapper)
        assert len(mapper.types({"Q_s"})) == 1
        assert len(found(bag)) == 1

    def test_one_name_described_two_ways_is_a_conflict_naming_both_declarations(self) -> None:
        mapper = Mapper(image(), DiagnosticBag())
        first = structure("Clash_s", Member("a", U8, 0), size=1, declared_at=Declared("unit_a.c", 11))
        second = structure(
            "Clash_s",
            Member("a", U16, 0),
            Member("b", U16, 16),
            declared_at=Declared("unit_b.c", 10),
        )
        mapped(first, "A", mapper=mapper)
        mapped(second, "B", mapper=mapper)
        mapped(first, "C", mapper=mapper)
        assert mapper.conflicts() == {
            "Clash_s": [Declared("unit_a.c", 11), Declared("unit_b.c", 10)]
        }

    def test_two_enums_under_one_name_with_different_enumerators_conflict(self) -> None:
        mapper = Mapper(image(), DiagnosticBag())
        mapped(Enum("Mode_e", 4, False, (("A", 1),)), "a", mapper=mapper)
        mapped(Enum("Mode_e", 4, False, (("A", 2),)), "b", mapper=mapper)
        assert set(mapper.conflicts()) == {"Mode_e"}

    def test_types_lists_only_the_structures_it_is_asked_for(self) -> None:
        mapper = Mapper(image(), DiagnosticBag())
        mapped(PAIR, mapper=mapper)
        mapped(Typedef("State_t", STATE), mapper=mapper)
        assert mapper.types({"State_t"}) == []
        assert mapper.types({"Pair_s", "State_t"}) == [PAIR_ENTRY]


class TestLayout:
    def layout(self, *members: Member, **extra: Any) -> list[str]:
        bag = DiagnosticBag()
        mapped(structure("L_s", *members, **extra), bag=bag)
        return [message for _, _, message in found(bag)]

    def test_an_alignment_the_source_states_is_said_not_to_be_carried(self) -> None:
        messages = self.layout(Member("x", U8, 0, alignment=8), alignment=8, size=8)
        assert messages == [
            "'L_s' is aligned to 8 bytes in C, which DDD cannot state: the structure DDD "
            "generates is aligned as its members are",
            "'L_s.x' is aligned to 8 bytes in C, which DDD cannot state",
        ]

    def test_bits_a_bitfield_would_have_fit_into_are_a_gap(self) -> None:
        messages = self.layout(Member("a", U8, 0, 2), Member("b", U8, 5, 2), Member("c", U16, 7, 9))
        assert messages == [
            "'L_s.b' starts at bit 5 although it fits at bit 2: an unnamed or zero width "
            "bitfield leaves such a gap, which DDD cannot state, so the structure DDD generates "
            "starts it at bit 2"
        ]

    def test_bits_the_rule_itself_skips_are_no_gap(self) -> None:
        assert self.layout(Member("a", U8, 0, 7), Member("b", U8, 8, 2)) == []

    def test_a_gap_before_the_first_bitfield_counts_from_the_start(self) -> None:
        messages = self.layout(Member("a", U8, 3, 2))
        assert messages == [
            "'L_s.a' starts at bit 3 although it fits at bit 0: an unnamed or zero width "
            "bitfield leaves such a gap, which DDD cannot state, so the structure DDD generates "
            "starts it at bit 0"
        ]

    def test_a_gap_after_a_value_member_counts_from_its_end(self) -> None:
        messages = self.layout(Member("x", U8, 0), Member("y", U8, 12, 2))
        assert len(messages) == 1
        assert messages[0].startswith("'L_s.y' starts at bit 12 although it fits at bit 8")

    def test_a_member_whose_offset_is_unknown_leaves_the_next_unjudged(self) -> None:
        assert self.layout(Member("a", U8, None, 2), Member("b", U8, 5, 2)) == []
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_toolbox_from_elf.py --no-cov`
Expected: FAIL at collection - `ModuleNotFoundError: No module named 'ddd.toolbox.mapping'`.

- [ ] **Step 3: Implement**

`src/ddd/toolbox/mapping.py`:

```python
"""From the C model of :mod:`ddd.elf` to DDD's spelling of it (section 4 of the design).

Kinds, datatypes, conversions, dimensions and the ``struct`` entries of ``types``: what an
image states exactly, it states. What DDD itself decides about the result - its caps, an
enumerator wider than an ``int``, the spelling of a name - is not restated here: the result is
handed to DDD's own loader and analysis (:mod:`ddd.toolbox.checked`), which says so itself.
"""

from __future__ import annotations

import json
from collections.abc import Collection
from dataclasses import dataclass
from typing import Any, Final

from ddd.diagnostics import DiagnosticBag, Location
from ddd.elf import (
    DW_ATE_BOOLEAN,
    DW_ATE_COMPLEX_FLOAT,
    DW_ATE_FLOAT,
    DW_ATE_SIGNED,
    DW_ATE_SIGNED_CHAR,
    DW_ATE_UNSIGNED,
    DW_ATE_UNSIGNED_CHAR,
    Array,
    Base,
    CType,
    Declared,
    Enum,
    Image,
    Member,
    Qualified,
    Struct,
    Typedef,
    Unsupported,
    Variable,
    size_of,
)
from ddd.toolbox.findings import place, report

_FAMILIES: Final = {
    DW_ATE_BOOLEAN: "boolean",
    DW_ATE_FLOAT: "float",
    DW_ATE_SIGNED: "signed",
    DW_ATE_SIGNED_CHAR: "signed",
    DW_ATE_UNSIGNED: "unsigned",
    DW_ATE_UNSIGNED_CHAR: "unsigned",
}
_DATATYPES: Final = {
    ("boolean", 1): "boolean",
    ("unsigned", 1): "uint8",
    ("unsigned", 2): "uint16",
    ("unsigned", 4): "uint32",
    ("unsigned", 8): "uint64",
    ("signed", 1): "sint8",
    ("signed", 2): "sint16",
    ("signed", 4): "sint32",
    ("signed", 8): "sint64",
    ("float", 4): "float32",
    ("float", 8): "float64",
}
_ENCODED_AS: Final = {
    DW_ATE_BOOLEAN: "a boolean",
    DW_ATE_COMPLEX_FLOAT: "a complex number",
    DW_ATE_FLOAT: "a floating point number",
    DW_ATE_SIGNED: "a signed integer",
    DW_ATE_SIGNED_CHAR: "a signed character",
    DW_ATE_UNSIGNED: "an unsigned integer",
    DW_ATE_UNSIGNED_CHAR: "an unsigned character",
}


@dataclass(frozen=True, slots=True)
class Shape:
    """A C type seen as DDD sees one: its core, the dimensions around it, its qualifiers, and
    the typedef closest to the core that names it."""

    core: Base | Enum | Struct | Unsupported
    dimensions: tuple[int, ...] = ()
    const: bool = False
    volatile: bool = False
    name: str | None = None


def shape_of(ctype: CType) -> Shape:
    """Walk ``ctype`` down to its core, collecting what DDD states about the way.

    A qualifier counts wherever it sits: on the variable's type, under a typedef, or on an
    array's element, where producers put it for an array. The name is the typedef closest to
    the core, so that a second alias still names one structure; a typedef naming an array
    names the array, and is dropped when the walk passes into its element.
    """
    dimensions: list[int] = []
    const = False
    volatile = False
    name: str | None = None
    node = ctype
    while True:
        if isinstance(node, Qualified):
            const = const or node.const
            volatile = volatile or node.volatile
            node = node.inner
        elif isinstance(node, Typedef):
            name = node.name
            node = node.inner
        elif isinstance(node, Array):
            dimensions.extend(node.dimensions)
            name = None
            node = node.element
        else:
            return Shape(node, tuple(dimensions), const, volatile, name)


def datatype_of(core: Base | Enum) -> str | None:
    """The DDD datatype of a base type or an enum, or None where no datatype holds it."""
    if isinstance(core, Enum):
        sign = "signed" if core.signed else "unsigned"
        return _DATATYPES.get((sign, core.size))
    family = _FAMILIES.get(core.encoding)
    if family is None:
        return None
    return _DATATYPES.get((family, core.size))


def described(core: Base | Enum) -> str:
    """A base type or an enum in words, as a refusal says what it is."""
    if isinstance(core, Enum):
        return f"an enum of {_bytes(core.size)}"
    what = _ENCODED_AS.get(core.encoding, f"a value of DWARF encoding {core.encoding:#x}")
    return f"'{core.name}', {what} of {_bytes(core.size)}"


def _bytes(size: int) -> str:
    if size == 1:
        return "1 byte"
    return f"{size} bytes"


@dataclass(frozen=True, slots=True)
class Typed:
    """What DDD states of one variable's type, before its storage is read."""

    kind: str
    datatype: str | None
    """None for a structured object, which names its ``typename`` instead."""

    typename: str | None
    dimensions: tuple[int, ...]
    conversion: dict[str, Any] | None
    volatile: bool
    reaches: frozenset[str]
    """The structures and enums the variable names, directly or through members."""

    element_size: int
    """The bytes of one element, for reading the initial value."""


@dataclass(frozen=True, slots=True)
class Refusal:
    """Why a type cannot be described: the path to the part DDD cannot state, and what it is."""

    path: str
    what: str
    declared_at: Declared | None = None


type _Described = tuple[str, frozenset[str]] | Refusal


class Mapper:
    """Maps variables one after the other, keeping one ``types`` entry per structure name.

    Structures and enums are registered by name as they are described, every distinct
    description of one name kept, so that :meth:`conflicts` can name each name the image
    defines more than one way once every variable has been mapped.
    """

    def __init__(self, image: Image, bag: DiagnosticBag) -> None:
        self._image = image
        self._bag = bag
        self._named: dict[str, list[tuple[dict[str, Any], Declared | None]]] = {}
        self._structures: list[str] = []
        self._synthesized: dict[Struct | Enum, str] = {}
        self._described: dict[tuple[Struct, str], _Described] = {}
        self._reported: set[tuple[str, str]] = set()

    def typed(self, variable: Variable) -> Typed | None:
        """What DDD states of ``variable``'s type; None, reported, where it cannot be stated."""
        shape = shape_of(variable.type)
        location = place(self._image, variable.declared_at)
        core = shape.core
        if isinstance(core, Unsupported):
            self._refuse(variable, Refusal(variable.name, core.what), location)
            return None
        if isinstance(core, Struct):
            return self._structured(variable, shape, core, location)
        scalar = self._scalar(core, variable.name, shape.name, f"{variable.name}_t", None)
        if isinstance(scalar, Refusal):
            self._refuse(variable, scalar, location)
            return None
        datatype, conversion, reaches = scalar
        return Typed(
            kind=_kind(shape),
            datatype=datatype,
            typename=None,
            dimensions=shape.dimensions,
            conversion=conversion,
            volatile=shape.volatile,
            reaches=reaches,
            element_size=core.size,
        )

    def conflicts(self) -> dict[str, list[Declared | None]]:
        """Every name the image defines more than one way, with where each way is declared."""
        return {
            name: [declared_at for _, declared_at in known]
            for name, known in self._named.items()
            if len(known) > 1
        }

    def types(self, names: Collection[str]) -> list[dict[str, Any]]:
        """The ``struct`` entries among ``names``, each after the structures it names."""
        return [self._named[name][0][0] for name in self._structures if name in names]

    def _structured(
        self, variable: Variable, shape: Shape, core: Struct, location: Location
    ) -> Typed | None:
        if shape.const and shape.dimensions:
            report(
                self._bag,
                "elf-type-unsupported",
                f"'{variable.name}' is a const array of structures, which DDD cannot state: a "
                f"parameter has no dimensions, and a value block holds no structure",
                location,
            )
            return None
        described_ = self._struct(core, shape.name, f"{variable.name}_t")
        if isinstance(described_, Refusal):
            self._refuse(variable, described_, location)
            return None
        name, reaches = described_
        return Typed(
            kind="parameter" if shape.const else "measurement",
            datatype=None,
            typename=name,
            dimensions=shape.dimensions,
            conversion=None,
            volatile=shape.volatile,
            reaches=reaches,
            element_size=core.size,
        )

    def _refuse(self, variable: Variable, refusal: Refusal, location: Location) -> None:
        if refusal.path == variable.name:
            message = f"'{variable.name}' is {refusal.what}, which DDD cannot state"
        else:
            message = (
                f"'{variable.name}' cannot be described: '{refusal.path}' is {refusal.what}, "
                f"which DDD cannot state"
            )
        notes: list[tuple[str, Location | None]] = []
        if refusal.declared_at is not None:
            notes.append(
                (f"'{refusal.path}' is declared here", place(self._image, refusal.declared_at))
            )
        report(self._bag, "elf-type-unsupported", message, location, notes)

    def _scalar(
        self,
        core: Base | Enum,
        path: str,
        alias: str | None,
        synthesized: str,
        declared_at: Declared | None,
    ) -> tuple[str, dict[str, Any], frozenset[str]] | Refusal:
        datatype = datatype_of(core)
        if datatype is None:
            return Refusal(path, described(core), declared_at)
        if isinstance(core, Base):
            return datatype, {"kind": "identity"}, frozenset()
        name = alias or core.tag or self._synthesize(core, synthesized)
        conversion = {"kind": "enum", "name": name, "enumerators": dict(core.enumerators)}
        self._register(name, conversion, core.declared_at)
        return datatype, conversion, frozenset({name})

    def _struct(self, struct: Struct, alias: str | None, synthesized: str) -> _Described:
        name = alias or struct.tag or self._synthesize(struct, synthesized)
        key = (struct, name)
        known = self._described.get(key)
        if known is None:
            known = self._describe_struct(struct, name)
            self._described[key] = known
        return known

    def _describe_struct(self, struct: Struct, name: str) -> _Described:
        members: list[dict[str, Any]] = []
        reaches: set[str] = {name}
        for member in struct.members:
            entry = self._member(name, member)
            if isinstance(entry, Refusal):
                return entry
            described_member, reached = entry
            members.append(described_member)
            reaches.update(reached)
        self._register(
            name, {"type": "struct", "name": name, "members": members}, struct.declared_at
        )
        if name not in self._structures:
            self._structures.append(name)
        self._layout(name, struct)
        return name, frozenset(reaches)

    def _member(
        self, structure: str, member: Member
    ) -> tuple[dict[str, Any], frozenset[str]] | Refusal:
        if member.name is None:
            return Refusal(f"{structure}.<anonymous>", "an anonymous member", member.declared_at)
        path = f"{structure}.{member.name}"
        shape = shape_of(member.type)
        if shape.const or shape.volatile:
            self._qualifier_dropped(path, shape, member.declared_at)
        core = shape.core
        synthesized = f"{structure}_{member.name}_t"
        if isinstance(core, Unsupported):
            return Refusal(path, core.what, member.declared_at)
        if member.bit_size is not None:
            return self._bits(path, member, core, shape.name, synthesized)
        entry: dict[str, Any] = {"name": member.name, "member": "value"}
        if isinstance(core, Struct):
            nested = self._struct(core, shape.name, synthesized)
            if isinstance(nested, Refusal):
                return nested
            entry["typename"], reaches = nested
            if shape.dimensions:
                entry["dimensions"] = list(shape.dimensions)
            return entry, reaches
        scalar = self._scalar(core, path, shape.name, synthesized, member.declared_at)
        if isinstance(scalar, Refusal):
            return scalar
        entry["datatype"], entry["conversion"], reaches = scalar
        if shape.dimensions:
            entry["dimensions"] = list(shape.dimensions)
        return entry, reaches

    def _bits(
        self,
        path: str,
        member: Member,
        core: Base | Enum | Struct,
        alias: str | None,
        synthesized: str,
    ) -> tuple[dict[str, Any], frozenset[str]] | Refusal:
        if isinstance(core, Struct):
            return Refusal(path, "a bitfield of a structure", member.declared_at)
        entry: dict[str, Any] = {"name": member.name, "member": "bits"}
        if isinstance(core, Base) and core.encoding == DW_ATE_BOOLEAN:
            self._once(
                "elf-boolean-bitfield",
                path,
                f"'{path}' is a _Bool bitfield, described as a uint8 one of the same width: "
                f"DDD refuses a boolean bitfield",
                member.declared_at,
            )
            entry["datatype"] = "uint8"
            entry["conversion"] = {"kind": "identity"}
            entry["bits"] = member.bit_size
            return entry, frozenset()
        scalar = self._scalar(core, path, alias, synthesized, member.declared_at)
        if isinstance(scalar, Refusal):
            return scalar
        entry["datatype"], entry["conversion"], reaches = scalar
        entry["bits"] = member.bit_size
        return entry, reaches

    def _qualifier_dropped(self, path: str, shape: Shape, declared_at: Declared | None) -> None:
        stated = [word for word, on in (("const", shape.const), ("volatile", shape.volatile)) if on]
        self._once(
            "elf-qualifier-dropped",
            path,
            f"'{path}' is {' '.join(stated)} in C, which DDD cannot state of a member: DDD "
            f"qualifies whole objects",
            declared_at,
        )

    def _layout(self, name: str, struct: Struct) -> None:
        if struct.alignment is not None:
            self._once(
                "elf-alignment",
                name,
                f"'{name}' is aligned to {struct.alignment} bytes in C, which DDD cannot state: "
                f"the structure DDD generates is aligned as its members are",
                struct.declared_at,
            )
        end: int | None = 0
        for member in struct.members:
            label = f"{name}.{member.name}"
            if member.alignment is not None:
                self._once(
                    "elf-alignment",
                    label,
                    f"'{label}' is aligned to {member.alignment} bytes in C, which DDD cannot "
                    f"state",
                    member.declared_at,
                )
            gap = _gap(end, member)
            if gap:
                self._once(
                    "elf-bitfield-gap",
                    label,
                    f"'{label}' starts at bit {member.bit_offset} although it fits at bit {end}: "
                    f"an unnamed or zero width bitfield leaves such a gap, which DDD cannot "
                    f"state, so the structure DDD generates starts it at bit {end}",
                    member.declared_at,
                )
            end = _end(member)

    def _synthesize(self, key: Struct | Enum, name: str) -> str:
        known = self._synthesized.get(key)
        if known is not None:
            return known
        self._synthesized[key] = name
        what = "structure" if isinstance(key, Struct) else "enum"
        self._once(
            "elf-name-synthesized",
            name,
            f"an anonymous {what} is named '{name}', after the first thing that reaches it; "
            f"rename it if the source has a better name",
            key.declared_at,
        )
        return name

    def _register(
        self, name: str, description: dict[str, Any], declared_at: Declared | None
    ) -> None:
        known = self._named.setdefault(name, [])
        text = json.dumps(description)
        if all(json.dumps(other) != text for other, _ in known):
            known.append((description, declared_at))

    def _once(self, check: str, key: str, message: str, declared_at: Declared | None) -> None:
        if (check, key) in self._reported:
            return
        self._reported.add((check, key))
        report(self._bag, check, message, place(self._image, declared_at))


def _kind(shape: Shape) -> str:
    if not shape.const:
        return "measurement"
    if shape.dimensions:
        return "value_block"
    return "parameter"


def _gap(end: int | None, member: Member) -> int:
    """The bits before a bitfield that it would have fit into, or 0.

    That is the trace an unnamed or zero width bitfield leaves. "Would have fit" is the rule
    the System V ABIs and the AAPCS share: a bitfield starts at the next free bit unless it
    would then cross a boundary of its declared type's size. A gap that rule explains is
    padding the structure DDD generates reproduces, and is none of this function's business.
    """
    start = member.bit_offset
    if end is None or start is None or member.bit_size is None or start <= end:
        return 0
    size = size_of(member.type)
    # A bitfield's type is an integer or an enum here: any other was refused before the
    # layout of its structure was looked at.
    assert size is not None
    width = 8 * size
    if end // width != (end + member.bit_size - 1) // width:
        return 0
    return start - end


def _end(member: Member) -> int | None:
    if member.bit_offset is None:
        return None
    if member.bit_size is not None:
        return member.bit_offset + member.bit_size
    size = size_of(member.type)
    # Every member's type is described by the time the layout is looked at.
    assert size is not None
    return member.bit_offset + 8 * size
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_toolbox_from_elf.py --no-cov` - Expected: PASS. Then the whole suite with coverage (`ddd/toolbox/mapping.py` at 100 % line and branch), `ruff check .`, `ruff format --check .` (format the test file first), bare `mypy` - each 0.

- [ ] **Step 5: Ablations**

In a scratch worktree: drop the `("unsigned", 8)` row of `_DATATYPES` (the `uint64` case dies); make `shape_of` keep `name` across an array (`test_the_name_is_the_typedef_closest_to_the_core` survives - it has no array - so confirm `test_qualifiers_and_dimensions_are_collected_on_the_way_to_the_core` dies instead, its `Row_t` then naming the core); drop `name = None` from `shape_of`'s array arm and see which dies; replace `_gap`'s fit test with `return start - end` (`test_bits_the_rule_itself_skips_are_no_gap` dies); make `_register` compare with `==` rather than as json (`test_two_enums_under_one_name_with_different_enumerators_conflict` survives - order is not what differs there - so add the case of the same enumerators in another order to that test if the ablation survives, and state it in the report).

- [ ] **Step 6: Commit**

```bash
git add src/ddd/toolbox/mapping.py tests/test_toolbox_from_elf.py
git commit -m "$(printf 'spell the c model the way ddd states it: kinds, datatypes, enums, structures\n\nconst decides between a measurement and calibration data, and the shape\nbetween the calibration kinds; enums sit inline, structures become one types\nentry each, members and bitfields in order. What ddd cannot state is refused\nat the path it occurs, and the layout traces ddd cannot carry are warned about.\n\nCo-Authored-By: <your model> <noreply@anthropic.com>')"
```

---

### Task 6: initial values out of an image's bytes

**Files:**
- Create: `src/ddd/toolbox/values.py`
- Test: `tests/test_toolbox_from_elf.py`

**Interfaces:**
- Consumes: nothing of the toolbox.
- Produces: `UnstatableValueError`, `initial_value(raw, datatype, dimensions, byte_order)`, `shortest_float32(value)`.

Section 4.6 of the spec. Bytes rather than values decide whether an array is one fill value, so that `-0.0` and `0.0` stay apart. The largest float32 exercises the overflow arm of `_reads_back` - rounded to four digits it is `3.403e38`, which no float32 holds - and `0x03AD66B5` the nine-digit fallback: nine digits read every float32 back, and a scan of every exponent found this one among the few that need all nine.

- [ ] **Step 1: Write the failing tests**

In `tests/test_toolbox_from_elf.py`, add to the imports:

```python
import json
import math
import struct

from ddd.toolbox.values import UnstatableValueError, initial_value, shortest_float32
```

and append:

```python
class TestValues:
    @pytest.mark.parametrize(
        ("raw", "datatype", "byte_order", "value"),
        [
            (bytes([0x34, 0x12]), "uint16", "little", 0x1234),
            (bytes([0x12, 0x34]), "uint16", "big", 0x1234),
            (bytes([0xFE, 0xFF]), "sint16", "little", -2),
            (bytes([1, 2, 3, 4, 5, 6, 7, 8]), "uint64", "big", 0x0102030405060708),
            (bytes([0xFF]), "sint8", "little", -1),
            (bytes([1]), "boolean", "little", True),
            (bytes([0]), "boolean", "little", False),
            (struct.pack(">d", 0.1), "float64", "big", 0.1),
            (struct.pack("<f", 1.5), "float32", "little", 1.5),
            (struct.pack("<f", 0.1), "float32", "little", 0.1),
        ],
    )
    def test_a_scalar_is_read_in_the_image_s_byte_order(
        self, raw: bytes, datatype: str, byte_order: str, value: Any
    ) -> None:
        result = initial_value(raw, datatype, (), byte_order)
        assert result == value
        assert type(result) is type(value)

    def test_an_array_is_nested_lists_in_c_order(self) -> None:
        assert initial_value(bytes([1, 2, 3, 4, 5, 6]), "uint8", (2, 3), "little") == [
            [1, 2, 3],
            [4, 5, 6],
        ]

    def test_three_dimensions_nest_three_deep(self) -> None:
        assert initial_value(bytes(range(8)), "uint8", (2, 2, 2), "little") == [
            [[0, 1], [2, 3]],
            [[4, 5], [6, 7]],
        ]

    def test_an_array_of_one_value_is_that_value(self) -> None:
        assert initial_value(bytes([9, 9, 9, 9]), "uint8", (4,), "little") == 9

    def test_bytes_not_values_decide_whether_an_array_is_one_value(self) -> None:
        value = initial_value(struct.pack("<ff", -0.0, 0.0), "float32", (2,), "little")
        assert [math.copysign(1.0, item) for item in value] == [-1.0, 1.0]

    @pytest.mark.parametrize(
        ("raw", "datatype", "reason"),
        [
            (bytes([2]), "boolean", "a boolean byte of 2, which is neither 0 nor 1"),
            (struct.pack("<f", math.nan), "float32", "NaN"),
            (struct.pack("<d", -math.inf), "float64", "an infinity"),
        ],
    )
    def test_a_value_ddd_has_no_spelling_for_is_refused(
        self, raw: bytes, datatype: str, reason: str
    ) -> None:
        with pytest.raises(UnstatableValueError) as refused:
            initial_value(raw, datatype, (), "little")
        assert str(refused.value) == reason

    def test_one_element_ddd_has_no_spelling_for_refuses_the_array(self) -> None:
        with pytest.raises(UnstatableValueError):
            initial_value(bytes([1, 3]), "boolean", (2,), "little")

    def test_a_float32_is_spelled_with_the_fewest_digits_that_read_it_back(self) -> None:
        tenth = struct.unpack("<f", struct.pack("<f", 0.1))[0]
        assert shortest_float32(tenth) == 0.1

    def test_the_largest_float32_is_not_spelled_past_what_a_float32_holds(self) -> None:
        largest = struct.unpack("<f", (0x7F7FFFFF).to_bytes(4, "little"))[0]
        assert shortest_float32(largest) == 3.4028235e38

    def test_a_float32_needing_nine_digits_gets_nine(self) -> None:
        value = struct.unpack("<f", (0x03AD66B5).to_bytes(4, "little"))[0]
        assert shortest_float32(value) == 1.01916065e-36
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_toolbox_from_elf.py --no-cov`
Expected: FAIL at collection - `ModuleNotFoundError: No module named 'ddd.toolbox.values'`.

- [ ] **Step 3: Implement**

`src/ddd/toolbox/values.py`:

```python
"""Initial values out of an image's bytes, spelled as DDD states them (section 4.6)."""

from __future__ import annotations

import math
import struct
from typing import Any, Final

_FORMATS: Final = {
    "boolean": "B",
    "uint8": "B",
    "sint8": "b",
    "uint16": "H",
    "sint16": "h",
    "uint32": "I",
    "sint32": "i",
    "uint64": "Q",
    "sint64": "q",
    "float32": "f",
    "float64": "d",
}
_FLOAT32_DIGITS: Final = 9
"""Significant digits that read every float32 back to its own bits."""


class UnstatableValueError(ValueError):
    """An initial value DDD has no spelling for; the message says what the value is."""


def initial_value(raw: bytes, datatype: str, dimensions: tuple[int, ...], byte_order: str) -> Any:
    """``raw`` read as ``datatype`` in ``byte_order``: a scalar, or nested lists in C order.

    An array whose elements are all the same bytes is that one value, the fill DDD gives a
    scalar stated on an array-shaped object. Bytes rather than values are compared, so that
    ``-0.0`` and ``0.0`` stay apart.
    """
    code = ("<" if byte_order == "little" else ">") + _FORMATS[datatype]
    size = struct.calcsize(code)
    chunks = [raw[start : start + size] for start in range(0, len(raw), size)]
    if all(chunk == chunks[0] for chunk in chunks):
        return _decoded(chunks[0], code, datatype)
    return _nested([_decoded(chunk, code, datatype) for chunk in chunks], dimensions)


def shortest_float32(value: float) -> float:
    """The shortest decimal that reads back to the float32 ``value``: 0.1 for ``0.1f``, rather
    than the 0.10000000149011612 the same bits spell as a double."""
    for digits in range(1, _FLOAT32_DIGITS):
        candidate = float(f"{value:.{digits}g}")
        if _reads_back(candidate, value):
            return candidate
    return float(f"{value:.{_FLOAT32_DIGITS}g}")


def _reads_back(candidate: float, value: float) -> bool:
    try:
        (again,) = struct.unpack("<f", struct.pack("<f", candidate))
    except OverflowError:
        # Rounded up past the largest float32, as 3.403e38 is for its largest value.
        return False
    return bool(again == value)


def _decoded(chunk: bytes, code: str, datatype: str) -> Any:
    (value,) = struct.unpack(code, chunk)
    if datatype == "boolean":
        if value not in (0, 1):
            msg = f"a boolean byte of {value}, which is neither 0 nor 1"
            raise UnstatableValueError(msg)
        return value == 1
    if datatype in ("float32", "float64"):
        if math.isnan(value):
            msg = "NaN"
            raise UnstatableValueError(msg)
        if math.isinf(value):
            msg = "an infinity"
            raise UnstatableValueError(msg)
        if datatype == "float32":
            return shortest_float32(value)
    return value


def _nested(values: list[Any], dimensions: tuple[int, ...]) -> list[Any]:
    if len(dimensions) <= 1:
        return values
    step = len(values) // dimensions[0]
    return [
        _nested(values[index * step : (index + 1) * step], dimensions[1:])
        for index in range(dimensions[0])
    ]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_toolbox_from_elf.py --no-cov` - Expected: PASS. Then the whole suite with coverage (`ddd/toolbox/values.py` at 100 % line and branch), `ruff check .`, `ruff format --check .`, bare `mypy` - each 0.

- [ ] **Step 5: Ablations**

In a scratch worktree: compare decoded values instead of chunks in `initial_value` (the `-0.0` test dies); drop the `except OverflowError` (the largest-float32 test dies with an `OverflowError`); make `_FORMATS["sint8"]` `"B"` (the `-1` case dies).

- [ ] **Step 6: Commit**

```bash
git add src/ddd/toolbox/values.py tests/test_toolbox_from_elf.py
git commit -m "$(printf 'decode initial values the way ddd states them\n\nIn the image s byte order, nested in c order, an array of one value as that\nvalue, a float32 in the fewest digits that read it back; NaN, an infinity and\na boolean byte other than 0 and 1 have no spelling and say so.\n\nCo-Authored-By: <your model> <noreply@anthropic.com>')"
```

---

### Task 7: DDD's own check, and `describe`

**Files:**
- Create: `src/ddd/toolbox/checked.py`, `src/ddd/toolbox/from_elf.py`
- Test: `tests/test_toolbox_from_elf.py`

**Interfaces:**
- Consumes: Tasks 4, 5 and 6; `load_workspace` of `ddd.loading`, `analyze` of `ddd.analysis`, `STANDALONE_POLICY` and `SeverityPolicy` of `ddd.diagnostics`.
- Produces: `POLICY`, `Candidate`, `component_file`, `checked`; `DEFAULT_SECTIONS`, `PRODUCER_SCOPES`, `CHECKED_COMPONENT`, `NOT_INFERRED`, `VALUE_BLOCKS`, `Description`, `describe`, `document_text`.

`checked` writes the component into a temporary directory as `from_elf.ddd.json` - the loader wants that suffix - and runs DDD's loader and analysis on it under `--standalone`'s policy with `missing-id` ignored. It must iterate: a load error such as `schema` stops DDD before its analysis (measured while this plan was written), so an analysis error is only found once the load errors are gone (Review Focus 4). The errors of every pass are relayed; the warnings and infos of the last pass only, so nothing is said twice.

`from_elf` holds the one `assert` of the translator outside `mapping`: `_storage` runs for a selected variable, and selection keeps only variables with an address.

- [ ] **Step 1: Write the failing tests**

In `tests/test_toolbox_from_elf.py`, add to the imports:

```python
from ddd.diagnostics import STANDALONE_POLICY
from ddd.toolbox.checked import POLICY
from ddd.toolbox.from_elf import (
    DEFAULT_SECTIONS,
    NOT_INFERRED,
    VALUE_BLOCKS,
    Description,
    describe,
    document_text,
)
```

and append:

```python
def run(
    img: Image, *arguments: str, scope: str = "output", component: str | None = None
) -> tuple[Description, DiagnosticBag]:
    bag = DiagnosticBag()
    return describe(img, list(arguments), scope=scope, component=component, bag=bag), bag


def filled(*pairs: tuple[int, bytes], size: int = 0x100) -> bytes:
    data = bytearray(size)
    for offset, raw in pairs:
        data[offset : offset + len(raw)] = raw
    return bytes(data)


def names(description: Description) -> list[str]:
    return [entry["definition"]["name"] for entry in description.interface]


class TestDescribe:
    def test_a_variable_becomes_one_entry_and_the_run_says_what_it_leaves_out(self) -> None:
        img = image(stored("Gain", U16, line=3), contents=filled((0, bytes([0x2C, 0x01]))))
        description, bag = run(img, "Gain")
        assert description == Description(
            (
                {
                    "scope": "output",
                    "definition": {
                        "name": "Gain",
                        "kind": "measurement",
                        "datatype": "uint16",
                        "conversion": IDENTITY,
                        "init": 300,
                        "volatile": False,
                    },
                },
            ),
            (),
        )
        assert found(bag) == [("elf-not-inferred", Severity.INFO, NOT_INFERRED)]

    def test_a_definition_states_its_keys_in_the_examples_order(self) -> None:
        calib = Section(".calib", 0x100, 0x100, 0)
        img = image(
            stored("Table", Array(Qualified(U8, const=True), (2,))),
            sections=(calib,),
            contents=filled((0, bytes([1, 2]))),
        )
        description, _ = run(img, "Table")
        assert list(description.interface[0]["definition"]) == [
            "name",
            "kind",
            "datatype",
            "dimensions",
            "conversion",
            "init",
            "section",
            "volatile",
        ]

    def test_a_consumer_states_no_storage_and_reads_none(self) -> None:
        img = image(
            stored("Level", F32),
            sections=(Section(".calib", 0x100, 4, 0),),
            contents=filled((0, struct.pack("<f", math.nan))),
        )
        description, bag = run(img, "Level", scope="input")
        assert description.interface[0] == {
            "scope": "input",
            "definition": {
                "name": "Level",
                "kind": "measurement",
                "datatype": "float32",
                "conversion": IDENTITY,
                "volatile": False,
            },
        }
        assert [check for check, _, _ in found(bag)] == ["elf-not-inferred"]

    def test_a_local_states_its_storage_as_an_output_does(self) -> None:
        img = image(stored("Gain", U16), contents=filled((0, bytes([0x2C, 0x01]))))
        description, _ = run(img, "Gain", scope="local")
        assert description.interface[0]["scope"] == "local"
        assert description.interface[0]["definition"]["init"] == 300

    def test_a_default_section_without_contents_states_neither_init_nor_section(self) -> None:
        bss = Section(".bss", 0x200, 4, None)
        description, _ = run(image(stored("Counter", U16, address=0x200), sections=(DATA, bss)), "Counter")
        assert {"init", "section"}.isdisjoint(description.interface[0]["definition"])

    def test_a_custom_section_without_contents_is_stated_without_an_init(self) -> None:
        """The case no portable C spelling builds (Task 1): a .noinit the startup code leaves
        alone."""
        noinit = Section(".noinit", 0x200, 4, None)
        img = image(stored("Retained", U16, address=0x200), sections=(DATA, noinit))
        description, bag = run(img, "Retained")
        definition = description.interface[0]["definition"]
        assert ("init" in definition, definition["section"]) == (False, ".noinit")
        assert [check for check, _, _ in found(bag)] == ["elf-section", "elf-not-inferred"]

    @pytest.mark.parametrize("section", sorted(DEFAULT_SECTIONS))
    def test_a_toolchain_default_section_is_not_stated(self, section: str) -> None:
        img = image(stored("Gain", U16), sections=(Section(section, 0x100, 4, 0),))
        description, _ = run(img, "Gain")
        assert "section" not in description.interface[0]["definition"]

    def test_a_section_the_output_states_is_warned_about_once(self) -> None:
        calib = Section(".calib", 0x100, 8, 0)
        img = image(
            stored("A", U16, line=3), stored("B", U16, address=0x102, line=4), sections=(calib,)
        )
        _, bag = run(img, "A", "B")
        sections = [d for d in bag.sorted if d.check == "elf-section"]
        assert [(d.message, d.location) for d in sections] == [
            (
                "'A' is placed in '.calib', the name of the image's output section: DDD's "
                "section is the one the source places it in, which the linker script may have "
                "renamed, and the project has to declare it in a sections file, or 'ddd check' "
                "reports unknown-section",
                Location(Path("unit.c"), line=3),
            )
        ]

    def test_an_address_no_section_holds_is_refused(self) -> None:
        description, bag = run(image(stored("Lost", U16, address=0x900)), "Lost")
        assert description.interface == ()
        assert found(bag) == [
            (
                "elf-no-storage",
                Severity.ERROR,
                "'Lost' has an address, 0x900, that no section of the image holds",
            )
        ]

    def test_a_variable_running_past_its_section_is_refused(self) -> None:
        img = image(stored("Wide", Base("unsigned int", DW_ATE_UNSIGNED, 4), address=0x1FE))
        _, bag = run(img, "Wide")
        assert found(bag) == [
            (
                "elf-init-unsupported",
                Severity.ERROR,
                "'Wide' runs past the end of section '.data', so its initial value cannot be read",
            )
        ]

    def test_a_value_ddd_cannot_state_is_refused(self) -> None:
        img = image(stored("Level", F32), contents=filled((0, struct.pack("<f", math.nan))))
        _, bag = run(img, "Level")
        assert found(bag) == [
            (
                "elf-init-unsupported",
                Severity.ERROR,
                "'Level' starts as NaN, which DDD cannot state as an initial value",
            )
        ]

    def test_a_structured_object_s_values_are_dropped_and_said_to_be(self) -> None:
        img = image(
            stored("Config", Qualified(PAIR, const=True), line=7),
            contents=filled((0, bytes([1, 2]))),
        )
        description, bag = run(img, "Config", component="Pump")
        assert description.interface[0]["definition"] == {
            "name": "Config",
            "kind": "parameter",
            "typename": "Pair_s",
            "volatile": False,
        }
        assert description.types == (PAIR_ENTRY,)
        assert found(bag)[0] == (
            "elf-init-dropped",
            Severity.WARNING,
            "'Config' starts with values the image holds, which DDD does not carry: a structured "
            "object is zero-initialised, and its values reach it from the running software or "
            "from the calibration tool",
        )

    def test_a_structured_object_of_zeros_loses_nothing(self) -> None:
        _, bag = run(image(stored("Config", PAIR)), "Config", component="Pump")
        assert [check for check, _, _ in found(bag)] == ["elf-not-inferred"]

    def test_the_list_output_says_where_the_types_went(self) -> None:
        _, bag = run(image(stored("Config", PAIR)), "Config")
        assert (
            "elf-types-omitted",
            Severity.WARNING,
            "the list output has no place for the types its structured objects name: "
            "'--component NAME' prints a component file that holds them",
        ) in found(bag)

    def test_a_value_block_adds_why_it_is_one_to_what_the_run_leaves_out(self) -> None:
        _, bag = run(image(stored("Table", Array(Qualified(U8, const=True), (2,)))), "Table")
        assert found(bag) == [("elf-not-inferred", Severity.INFO, NOT_INFERRED + VALUE_BLOCKS)]

    def test_every_variable_reaching_a_name_defined_two_ways_is_refused(self) -> None:
        first = structure("Clash_s", Member("a", U8, 0), size=1, declared_at=Declared("unit_a.c", 11))
        second = structure(
            "Clash_s", Member("a", U16, 0), size=2, declared_at=Declared("unit_b.c", 10)
        )
        img = image(
            stored("A", first, unit="unit_a.c", line=13),
            stored("B", second, unit="unit_b.c", line=13),
            stored("Gain", U8),
        )
        description, bag = run(img, "A", "B", "Gain")
        assert names(description) == ["Gain"]
        conflicts = [d for d in bag.sorted if d.check == "elf-type-conflict"]
        assert [d.message for d in conflicts] == [
            f"'{name}' reaches 'Clash_s', which the image defines 2 different ways, so no one "
            f"description of it is right"
            for name in ("A", "B")
        ]
        assert conflicts[0].notes == (
            ("'Clash_s' is defined one way here", Location(Path("unit_a.c"), line=11)),
            ("'Clash_s' is defined one way here", Location(Path("unit_b.c"), line=10)),
        )

    def test_a_variable_the_mapping_refuses_is_left_out_and_the_rest_described(self) -> None:
        img = image(stored("Pointer", Unsupported("a pointer")), stored("Gain", U16))
        description, bag = run(img, "Pointer", "Gain")
        assert names(description) == ["Gain"]
        assert [check for check, _, _ in found(bag)] == ["elf-type-unsupported", "elf-not-inferred"]

    def test_a_malformed_argument_is_refused_before_anything_is_read(self) -> None:
        with pytest.raises(ValueError):
            run(image(), "unit.c:")


class TestDocumentText:
    def test_the_list_output_is_the_entries(self) -> None:
        description = Description(({"scope": "output", "definition": {"name": "A"}},), (PAIR_ENTRY,))
        assert document_text(description, None) == (
            '[\n  {\n    "scope": "output",\n    "definition": {\n'
            '      "name": "A"\n    }\n  }\n]\n'
        )

    def test_the_component_output_holds_the_types_where_there_are_some(self) -> None:
        with_types = Description(
            ({"scope": "output", "definition": {"name": "A"}},), (PAIR_ENTRY,)
        )
        without = Description(with_types.interface, ())
        document = json.loads(document_text(with_types, "Pump"))
        assert document == {
            "component": {
                "name": "Pump",
                "types": [PAIR_ENTRY],
                "interface": list(with_types.interface),
            }
        }
        assert list(document["component"]) == ["name", "types", "interface"]
        assert json.loads(document_text(without, "Pump")) == {
            "component": {"name": "Pump", "interface": list(without.interface)}
        }


class TestTheCheckByDdd:
    def test_the_policy_is_standalone_s_and_leaves_missing_id_out(self) -> None:
        assert (*STANDALONE_POLICY, "missing-id=ignore") == POLICY

    def test_a_load_error_then_an_analysis_error_each_refuse_their_variable(self) -> None:
        """Review Focus 4: the schema error stops DDD before its analysis, so the enumerator
        wider than an int is only found on the second pass."""
        wide = Enum("Wide_e", 8, False, (("SMALL", 1), ("HUGE", 1 << 40)))
        long_name = "L" * 130
        img = image(
            stored("Good", U8, line=1),
            stored(long_name, U8, address=0x101, line=2),
            stored("Wide", wide, address=0x108, line=3),
        )
        description, bag = run(img, "Good", "L*", "Wide")
        assert names(description) == ["Good"]
        errors = [d for d in bag.sorted if d.severity is Severity.ERROR]
        assert [(d.check, d.location, d.notes[-1]) for d in errors] == [
            ("schema", Location(Path("unit.c"), line=2), (f"'{long_name}' is left out", None)),
            ("init-invalid", Location(Path("unit.c"), line=3), ("'Wide' is left out", None)),
        ]

    def test_a_finding_on_a_type_refuses_every_variable_reaching_it(self) -> None:
        wide = Enum("Wide_e", 8, False, (("HUGE", 1 << 40),))
        holder = structure("Holder_s", Member("level", wide, 0), size=8)
        img = image(
            stored("A", holder, line=4),
            stored("B", holder, address=0x108, line=5),
            stored("Good", U8, address=0x110),
        )
        description, bag = run(img, "A", "B", "Good", component="Pump")
        assert names(description) == ["Good"]
        assert description.types == ()
        (error,) = [d for d in bag.sorted if d.severity is Severity.ERROR]
        assert (error.check, error.location) == ("init-invalid", Location(Path("unit.c"), line=4))
        assert error.notes[-2:] == (("'A' is left out", None), ("'B' is left out", None))

    def test_ddd_s_warnings_of_the_last_pass_are_relayed_at_the_declaration(self) -> None:
        twice = Enum("Twice_e", 1, False, (("ONE", 1), ("UNO", 1)))
        _, bag = run(image(stored("Mode", twice, line=6)), "Mode")
        (duplicate,) = [d for d in bag.sorted if d.check == "enum-duplicate-value"]
        assert (duplicate.severity, duplicate.location) == (
            Severity.WARNING,
            Location(Path("unit.c"), line=6),
        )

    def test_a_note_of_ddd_s_is_moved_to_the_declaration_it_points_at(self) -> None:
        img = image(stored("gain", U8, line=1), stored("Gain", U8, address=0x101, line=2))
        _, bag = run(img, "gain", "Gain")
        (similar,) = [d for d in bag.sorted if d.check == "name-similar"]
        assert (similar.severity, similar.location) == (
            Severity.WARNING,
            Location(Path("unit.c"), line=1),
        )
        assert similar.notes == (("other variable", Location(Path("unit.c"), line=2)),)

    def test_a_finding_about_no_variable_is_relayed_at_the_image_and_ends_the_passes(
        self,
    ) -> None:
        description, bag = run(image(stored("Gain", U8)), "Gain", component="1bad")
        (error,) = [d for d in bag.sorted if d.severity is Severity.ERROR]
        assert (error.check, error.location) == ("schema", where(Path("hand.elf")))
        assert names(description) == ["Gain"]

    def test_a_run_ddd_refuses_everything_of_has_nothing_left_to_check(self) -> None:
        wide = Enum("Wide_e", 8, False, (("HUGE", 1 << 40),))
        description, bag = run(image(stored("Wide", wide)), "Wide")
        assert description.interface == ()
        assert [d.check for d in bag.sorted] == ["init-invalid"]
```

`test_a_note_of_ddd_s_is_moved_to_the_declaration_it_points_at` pins where DDD's own `name-similar` puts its finding and its note - at the first variable, the note at the second, measured when this plan was written; if DDD's placement moves, read the new answer off the running code and say so in the report.

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_toolbox_from_elf.py --no-cov`
Expected: FAIL at collection - `ModuleNotFoundError: No module named 'ddd.toolbox.checked'`.

- [ ] **Step 3: Implement**

`src/ddd/toolbox/checked.py`:

```python
"""DDD's own verdict on what ``ddd tool from-elf`` built (section 5.2 of the design).

The translator states what an image states and nothing of DDD's rules; this module hands the
result to DDD's loader and analysis, under the policy ``ddd check --standalone`` applies, and
relays what they find. A variable one of their errors concerns is left out and the check runs
again, because a load error stops DDD before its analysis: the analysis's own errors only show
once the load errors are gone.
"""

from __future__ import annotations

import json
import re
import tempfile
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from ddd.analysis import analyze
from ddd.diagnostics import (
    STANDALONE_POLICY,
    Diagnostic,
    DiagnosticBag,
    Location,
    Severity,
    SeverityPolicy,
    where,
)
from ddd.elf import Image, Variable
from ddd.loading import load_workspace
from ddd.toolbox.findings import place

POLICY: Final = (*STANDALONE_POLICY, "missing-id=ignore")
"""``ddd check --standalone``'s policy, and ``missing-id`` left out: the tool writes no ``id``
on purpose, says so once in ``elf-not-inferred``, and every producing entry would earn one."""

CHECKED_FILE: Final = "from_elf.ddd.json"
_INTERFACE: Final = re.compile(r"component\.interface\[(\d+)\]")
_TYPES: Final = re.compile(r"component\.types\[(\d+)\]")


@dataclass(frozen=True, slots=True)
class Candidate:
    """One variable's definition, before DDD has had its say."""

    variable: Variable
    definition: dict[str, Any]
    reaches: frozenset[str]


def component_file(
    name: str, types: Sequence[dict[str, Any]], interface: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    """A component description holding ``types``, when there are any, and ``interface``."""
    body: dict[str, Any] = {"name": name}
    if types:
        body["types"] = list(types)
    body["interface"] = list(interface)
    return {"component": body}


def checked(
    candidates: Sequence[Candidate],
    types: Callable[[Collection[str]], list[dict[str, Any]]],
    *,
    image: Image,
    scope: str,
    component: str,
    bag: DiagnosticBag,
) -> list[Candidate]:
    """The candidates DDD accepts, every finding it has about them relayed into ``bag``.

    The errors of every pass are relayed, and the warnings and infos of the last pass only,
    so that nothing is reported twice. A finding that concerns no variable is a fault of the
    tool: it is relayed as it is, located at the image, and the passes stop.
    """
    alive = list(candidates)
    last: list[Diagnostic] = []
    names: list[str] = []
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / CHECKED_FILE
        while alive:
            entries = types(set().union(*(candidate.reaches for candidate in alive)))
            names = [entry["name"] for entry in entries]
            interface = [{"scope": scope, "definition": c.definition} for c in alive]
            path.write_text(json.dumps(component_file(component, entries, interface)), "utf-8")
            found = DiagnosticBag(SeverityPolicy.from_strings(POLICY, standalone=True))
            workspace = load_workspace(path, found)
            if workspace is not None and not found.has_errors:
                analyze(workspace, found)
            errors = [d for d in found.sorted if d.severity is Severity.ERROR]
            last = [d for d in found.sorted if d.severity is not Severity.ERROR]
            if not errors:
                break
            refused: set[int] = set()
            for diagnostic in errors:
                concerned = _concerned(diagnostic.location, alive, names)
                _relay(diagnostic, concerned, alive, names, image, bag)
                refused.update(concerned)
            if not refused:
                break
            alive = [candidate for index, candidate in enumerate(alive) if index not in refused]
            last = []
    for diagnostic in last:
        _relay(diagnostic, _concerned(diagnostic.location, alive, names), alive, names, image, bag)
    return alive


def _concerned(
    location: Location | None, alive: Sequence[Candidate], names: Sequence[str]
) -> list[int]:
    """The indices of the candidates a finding is about; none for a finding outside them."""
    pointer = location.pointer if location is not None else ""
    match = _INTERFACE.match(pointer)
    if match is not None:
        return [int(match.group(1))]
    match = _TYPES.match(pointer)
    if match is not None:
        name = names[int(match.group(1))]
        return [index for index, candidate in enumerate(alive) if name in candidate.reaches]
    return []


def _relay(
    diagnostic: Diagnostic,
    concerned: Sequence[int],
    alive: Sequence[Candidate],
    names: Sequence[str],
    image: Image,
    bag: DiagnosticBag,
) -> None:
    """Add one of DDD's findings to ``bag``, at the C declaration of what it concerns."""
    if concerned:
        location = place(image, alive[concerned[0]].variable.declared_at)
    else:
        location = where(image.path)
    notes: list[tuple[str, Location | None]] = []
    for text, note_location in diagnostic.notes:
        about = _concerned(note_location, alive, names)
        notes.append((text, place(image, alive[about[0]].variable.declared_at) if about else None))
    if diagnostic.severity is Severity.ERROR:
        notes.extend((f"'{alive[index].variable.name}' is left out", None) for index in concerned)
    bag.add(diagnostic.check, diagnostic.message, location, notes, severity=diagnostic.severity)
```

`src/ddd/toolbox/from_elf.py`:

```python
"""``ddd tool from-elf``: the DDD declarations of the C variables a linked ELF image describes.

Section 7.3 of ``SPEC.md`` states the rules, and the design they came from is
``docs/superpowers/specs/2026-09-30-toolbox-from-elf-design.md``. :func:`describe` selects the
variables (:mod:`~ddd.toolbox.selection`), maps their types (:mod:`~ddd.toolbox.mapping`),
reads their initial values (:mod:`~ddd.toolbox.values`) and has DDD check the result
(:mod:`~ddd.toolbox.checked`).
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final

from ddd.diagnostics import DiagnosticBag, Location, where
from ddd.elf import Image, Variable
from ddd.toolbox.checked import Candidate, checked, component_file
from ddd.toolbox.findings import place, report
from ddd.toolbox.mapping import Mapper, Typed
from ddd.toolbox.selection import select, wanted
from ddd.toolbox.values import UnstatableValueError, initial_value

DEFAULT_SECTIONS: Final = frozenset(
    {
        ".data",
        ".bss",
        ".rodata",
        ".sdata",
        ".sbss",
        ".sdata2",
        ".sbss2",
        ".srodata",
        ".data1",
        ".rodata1",
    }
)
"""The sections a toolchain places a variable in by default: a variable in one states no
``section``, and is placed by the defaults as it was."""

PRODUCER_SCOPES: Final = frozenset({"output", "local"})
CHECKED_COMPONENT: Final = "FromElf"
"""The name the list output's entries are checked under; it never reaches the output."""

NOT_INFERRED: Final = (
    "an image states no unit, description, limits, scaling or id, so the output states none: "
    "every conversion but an enum's is the identity, the limits are the ones DDD derives, and "
    "'ddd id --assign' writes the ids"
)
VALUE_BLOCKS: Final = (
    "; and a const array is a value block, since nothing in an image tells a curve, a map or "
    "an axis from any other array"
)


@dataclass(frozen=True, slots=True)
class Description:
    """What ``from-elf`` prints: the interface entries, and the types they name."""

    interface: tuple[dict[str, Any], ...]
    types: tuple[dict[str, Any], ...]


def describe(
    image: Image,
    arguments: Sequence[str],
    *,
    scope: str,
    component: str | None,
    bag: DiagnosticBag,
) -> Description:
    """The declarations of the variables ``arguments`` name, every finding reported into
    ``bag``; a malformed argument raises ``ValueError`` before anything is read."""
    wanted_ = [wanted(text) for text in arguments]
    chosen = select(image, wanted_, bag)
    mapper = Mapper(image, bag)
    producer = scope in PRODUCER_SCOPES
    candidates: list[Candidate] = []
    for variable in chosen:
        typed = mapper.typed(variable)
        if typed is None:
            continue
        definition = _definition(image, variable, typed, producer=producer, bag=bag)
        if definition is not None:
            candidates.append(Candidate(variable, definition, typed.reaches))
    candidates = _without_conflicts(candidates, mapper, image, bag)
    kept = checked(
        candidates,
        mapper.types,
        image=image,
        scope=scope,
        component=component or CHECKED_COMPONENT,
        bag=bag,
    )
    _report_sections(kept, image, bag)
    _report_run(kept, image, bag, component=component)
    interface = tuple({"scope": scope, "definition": c.definition} for c in kept)
    reached: set[str] = set().union(*(candidate.reaches for candidate in kept))
    return Description(interface, tuple(mapper.types(reached)))


def document_text(description: Description, component: str | None) -> str:
    """The json ``from-elf`` prints: the list of entries, or the component file ``component``
    names."""
    if component is None:
        document: Any = list(description.interface)
    else:
        document = component_file(component, description.types, description.interface)
    return json.dumps(document, indent=2) + "\n"


def _definition(
    image: Image, variable: Variable, typed: Typed, *, producer: bool, bag: DiagnosticBag
) -> dict[str, Any] | None:
    definition: dict[str, Any] = {"name": variable.name, "kind": typed.kind}
    if typed.typename is not None:
        definition["typename"] = typed.typename
    else:
        definition["datatype"] = typed.datatype
    if typed.dimensions:
        definition["dimensions"] = list(typed.dimensions)
    if typed.conversion is not None:
        definition["conversion"] = typed.conversion
    if producer and not _storage(image, variable, typed, definition, bag):
        return None
    definition["volatile"] = typed.volatile
    return definition


def _storage(
    image: Image, variable: Variable, typed: Typed, definition: dict[str, Any], bag: DiagnosticBag
) -> bool:
    """Add the storage keys a producer states; False, reported, where they cannot be read."""
    assert variable.address is not None  # selection keeps a variable with an address only
    location = place(image, variable.declared_at)
    section = image.section_of(variable.address)
    if section is None:
        report(
            bag,
            "elf-no-storage",
            f"'{variable.name}' has an address, {variable.address:#x}, that no section of the "
            f"image holds",
            location,
        )
        return False
    if section.offset is not None:
        raw = image.read(variable.address, typed.element_size * math.prod(typed.dimensions))
        if raw is None:
            report(
                bag,
                "elf-init-unsupported",
                f"'{variable.name}' runs past the end of section '{section.name}', so its "
                f"initial value cannot be read",
                location,
            )
            return False
        if typed.datatype is not None:
            try:
                definition["init"] = initial_value(
                    raw, typed.datatype, typed.dimensions, image.byte_order
                )
            except UnstatableValueError as error:
                report(
                    bag,
                    "elf-init-unsupported",
                    f"'{variable.name}' starts as {error}, which DDD cannot state as an "
                    f"initial value",
                    location,
                )
                return False
        elif any(raw):
            report(
                bag,
                "elf-init-dropped",
                f"'{variable.name}' starts with values the image holds, which DDD does not "
                f"carry: a structured object is zero-initialised, and its values reach it from "
                f"the running software or from the calibration tool",
                location,
            )
    if section.name not in DEFAULT_SECTIONS:
        definition["section"] = section.name
    return True


def _without_conflicts(
    candidates: list[Candidate], mapper: Mapper, image: Image, bag: DiagnosticBag
) -> list[Candidate]:
    conflicts = mapper.conflicts()
    kept: list[Candidate] = []
    for candidate in candidates:
        clashing = sorted(candidate.reaches & conflicts.keys())
        if not clashing:
            kept.append(candidate)
            continue
        name = clashing[0]
        notes: list[tuple[str, Location | None]] = [
            (f"'{name}' is defined one way here", place(image, declared_at))
            for declared_at in conflicts[name]
        ]
        report(
            bag,
            "elf-type-conflict",
            f"'{candidate.variable.name}' reaches '{name}', which the image defines "
            f"{len(conflicts[name])} different ways, so no one description of it is right",
            place(image, candidate.variable.declared_at),
            notes,
        )
    return kept


def _report_sections(kept: Sequence[Candidate], image: Image, bag: DiagnosticBag) -> None:
    seen: set[str] = set()
    for candidate in kept:
        name = candidate.definition.get("section")
        if name is None or name in seen:
            continue
        seen.add(name)
        report(
            bag,
            "elf-section",
            f"'{candidate.variable.name}' is placed in '{name}', the name of the image's output "
            f"section: DDD's section is the one the source places it in, which the linker "
            f"script may have renamed, and the project has to declare it in a sections file, "
            f"or 'ddd check' reports unknown-section",
            place(image, candidate.variable.declared_at),
        )


def _report_run(
    kept: Sequence[Candidate], image: Image, bag: DiagnosticBag, *, component: str | None
) -> None:
    if not kept:
        return
    message = NOT_INFERRED
    if any(candidate.definition["kind"] == "value_block" for candidate in kept):
        message += VALUE_BLOCKS
    report(bag, "elf-not-inferred", message, where(image.path))
    if component is None and any("typename" in candidate.definition for candidate in kept):
        report(
            bag,
            "elf-types-omitted",
            "the list output has no place for the types its structured objects name: "
            "'--component NAME' prints a component file that holds them",
            where(image.path),
        )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_toolbox_from_elf.py --no-cov` - Expected: PASS. Then the whole suite with coverage (`ddd/toolbox/` at 100 % line and branch), `ruff check .`, `ruff format --check .`, bare `mypy` - each 0.

- [ ] **Step 5: Ablations**

In a scratch worktree: make `checked` stop after its first pass (`test_a_load_error_then_an_analysis_error_each_refuse_their_variable` dies - Review Focus 4); drop `"missing-id=ignore"` from `POLICY` (the policy test dies, and `test_a_variable_becomes_one_entry_and_the_run_says_what_it_leaves_out` with it, a `missing-id` info joining its findings); drop `".sdata"` from `DEFAULT_SECTIONS` (its parametrized case dies); relay the last pass's findings before a refusal pass too (the warning test sees `enum-duplicate-value` twice, or not - report which).

- [ ] **Step 6: Commit**

```bash
git add src/ddd/toolbox/checked.py src/ddd/toolbox/from_elf.py tests/test_toolbox_from_elf.py
git commit -m "$(printf 'describe the variables of an image, and have ddd itself check the result\n\nThe definitions are handed to the loader and the analysis under the standalone\npolicy; what they refuse is relayed at its c declaration and left out, and the\ncheck runs again, since a load error hides the analysis errors behind it. The\ntool restates none of ddd s rules.\n\nCo-Authored-By: <your model> <noreply@anthropic.com>')"
```

---

### Task 8: `ddd tool from-elf` on the command line

**Files:**
- Modify: `src/ddd/cli.py` (the `tool` group and its `from-elf` parser; `_command_tool_from_elf`; `_write_output`, which `_write_dictionary` now writes through)
- Modify: `tests/test_documentation.py` (the parser's known commands), `README.md`, `SPEC.md`, `docs/command_line_interface.rst` - the least each documentation test asks for a new command, so that this commit leaves no gate red (ruling 23 of the previous plan; Task 9 writes the rest)
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `open_image` and `ElfReadError` (a `ValueError`, so `main` turns it into exit `2`); `describe`, `document_text`; `resolve_path`; `C_IDENTIFIER_PATTERN`, `IDENTIFIER_MAX_LENGTH`.
- Produces: `ddd tool from-elf IMAGE SYMBOL... [--component NAME] [--scope {output,local,input}] [-o FILE] [--force] [--format {text,json}]`.

`cli.py` imports the toolbox and the reader inside the handler, as every heavy import of the module is, so that `ddd --help` and every other command answer without pyelftools - and a missing pyelftools is a usage error naming the extra rather than a traceback. A `ModuleNotFoundError` for anything else is re-raised: a broken install is not the extra's fault.

- [ ] **Step 1: Write the failing tests**

In `tests/test_cli.py`, add `import sys` to the standard library imports, `_build_parser` to the `ddd.cli` import, `where` to the `ddd.diagnostics` import, and append:

```python
FIXTURES = Path(__file__).parent / "fixtures" / "elf"
FIXTURE_ROWS = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))["rows"]
X86 = FIXTURES / "x86_64.elf"


def fixture_line(unit: str, text: str) -> int:
    """The line of a fixture unit holding ``text``: the oracle for where DWARF says a variable
    is declared."""
    lines = (FIXTURES / "src" / unit).read_text(encoding="utf-8").splitlines()
    (found,) = [number for number, line in enumerate(lines, start=1) if text in line]
    return found


def from_elf(capsys: pytest.CaptureFixture[str], *arguments: str) -> tuple[int, str, str]:
    code = main(["tool", "from-elf", *arguments])
    out, err = capsys.readouterr()
    return code, out, err


def expected_definitions(traits: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """What a row must print for the variables of main.c every row describes: the values the
    source states, and what the row's own toolchain said its target makes of the rest."""
    identity = {"kind": "identity"}
    unsigned_enum = {1: "uint8", 4: "uint32"}[traits["sizeof_enum"]]
    signed_enum = {1: "sint8", 4: "sint32"}[traits["sizeof_enum"]]
    state = {
        "kind": "enum",
        "name": "State_t",
        "enumerators": {"STATE_OFF": 0, "STATE_ON": 1, "STATE_FAULT": 200},
    }

    def value(
        name: str,
        kind: str,
        datatype: str,
        init: Any = None,
        *,
        dimensions: list[int] | None = None,
        conversion: dict[str, Any] = identity,
        volatile: bool = False,
    ) -> dict[str, Any]:
        definition: dict[str, Any] = {"name": name, "kind": kind, "datatype": datatype}
        if dimensions is not None:
            definition["dimensions"] = dimensions
        definition["conversion"] = conversion
        if init is not None:
            definition["init"] = init
        definition["volatile"] = volatile
        return definition

    rows = [
        value("Meas_U16", "measurement", "uint16", 0x1234),
        value("Meas_Volatile", "measurement", "uint32", 0x12345678, volatile=True),
        value("Meas_Array", "measurement", "sint16", [-2, 0x1234, 7], dimensions=[3]),
        value("Meas_Matrix", "measurement", "uint8", [[1, 2, 3], [4, 5, 6]], dimensions=[2, 3]),
        value("Meas_Fill", "measurement", "uint8", 9, dimensions=[4]),
        value("Meas_Bss", "measurement", "uint32"),
        value("Cal_Gain", "parameter", "uint16", 300),
        value("Cal_Tunable", "parameter", "uint8", 0x5A, volatile=True),
        value("Cal_Table", "value_block", "sint32", [-2, 0x12345678, 0, 1], dimensions=[4]),
        value("Cal_Declared_First", "parameter", "uint16", 0x1234),
        value("Type_Bool", "measurement", "boolean", True),
        value("Type_Char", "measurement", "uint8" if traits["char_unsigned"] else "sint8", 65),
        value("Type_Long", "measurement", {4: "sint32", 8: "sint64"}[traits["sizeof_long"]], -2),
        value("Type_U64", "measurement", "uint64", 0x0102030405060708),
        value("Type_S64", "measurement", "sint64", -0x0102030405060708),
        value("Type_F32", "measurement", "float32", 1.5),
        value("Type_F32_Tenth", "measurement", "float32", 0.1),
        value("Type_F64", "measurement", "float64", 0.1),
        value("Enum_State", "measurement", unsigned_enum, 1, conversion=state),
        value(
            "Enum_Signed",
            "measurement",
            signed_enum,
            -2,
            conversion={
                "kind": "enum",
                "name": "Signed_e",
                "enumerators": {"SIGNED_NEG": -2, "SIGNED_POS": 3},
            },
        ),
        value(
            "Enum_Anonymous",
            "measurement",
            unsigned_enum,
            2,
            conversion={
                "kind": "enum",
                "name": "Enum_Anonymous_t",
                "enumerators": {"ANON_A": 1, "ANON_B": 2},
            },
        ),
        value("Enum_Table", "value_block", unsigned_enum, [200, 0], dimensions=[2], conversion=state),
        value("Static_Used", "measurement", "uint16", 0x0102),
    ]
    definitions = {definition["name"]: definition for definition in rows}
    definitions["Section_Calib"] = {
        "name": "Section_Calib",
        "kind": "parameter",
        "datatype": "uint16",
        "conversion": identity,
        "init": 0x1234,
        "section": ".calib",
        "volatile": False,
    }
    for name, dimensions in (("Struct_Inlet", None), ("Struct_Inlets", [2])):
        structured: dict[str, Any] = {"name": name, "kind": "measurement", "typename": "Inlet_t"}
        if dimensions is not None:
            structured["dimensions"] = dimensions
        structured["volatile"] = False
        definitions[name] = structured
    definitions["Struct_Config"] = {
        "name": "Struct_Config",
        "kind": "parameter",
        "typename": "Inlet_t",
        "volatile": False,
    }
    return definitions


class TestToolFromElf:
    """``ddd tool from-elf`` end to end, over the committed fixture matrix."""

    @pytest.mark.parametrize("row", sorted(FIXTURE_ROWS))
    def test_every_row_prints_what_its_toolchain_says_its_variables_are(
        self, capsys: pytest.CaptureFixture[str], row: str
    ) -> None:
        expected = expected_definitions(FIXTURE_ROWS[row]["traits"])
        code, out, err = from_elf(
            capsys, str(FIXTURES / f"{row}.elf"), *expected, "--component", "Fixture"
        )
        assert code == EXIT_OK, err
        interface = json.loads(out)["component"]["interface"]
        assert {entry["definition"]["name"]: entry["definition"] for entry in interface} == expected
        assert {entry["scope"] for entry in interface} == {"output"}

    @pytest.mark.parametrize("row", sorted(FIXTURE_ROWS))
    def test_long_double_is_a_float64_only_where_the_target_makes_it_eight_bytes(
        self, capsys: pytest.CaptureFixture[str], row: str
    ) -> None:
        size = FIXTURE_ROWS[row]["traits"]["sizeof_long_double"]
        code, out, err = from_elf(capsys, str(FIXTURES / f"{row}.elf"), "Type_Long_Double", "--force")
        if size == 8:
            assert code == EXIT_OK, err
            (entry,) = json.loads(out)
            assert (entry["definition"]["datatype"], entry["definition"]["init"]) == ("float64", 1.0)
        else:
            assert code == EXIT_FINDINGS
            assert f"'long double', a floating point number of {size} bytes" in err

    def test_the_component_output_carries_its_types_and_passes_ddd_check_standalone(
        self, capsys: pytest.CaptureFixture[str], tmp_path: Path
    ) -> None:
        code, out, err = from_elf(
            capsys,
            str(X86),
            "Struct_Inlet",
            "Struct_Anonymous",
            "Struct_Qualified",
            "Layout_*",
            "Shared_*",
            "--component",
            "Fixture",
        )
        assert code == EXIT_OK, err
        document = json.loads(out)["component"]
        assert [entry["name"] for entry in document["types"]] == [
            "Inlet_t_pair_t",
            "Inlet_t",
            "Struct_Anonymous_t",
            "Qualified_s",
            "Aligned_s",
            "Gapped_s",
            "Padded_s",
            "Shared_t",
        ]
        written = tmp_path / "fixture.ddd.json"
        written.write_text(out, encoding="utf-8")
        assert main(["check", "--standalone", str(written)]) == EXIT_OK

    def test_every_finding_about_a_variable_is_shown_at_its_line_of_the_source(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code, _, err = from_elf(
            capsys,
            str(X86),
            "Type_Pointer",
            "Struct_With_Pointer",
            "Tls_Counter",
            "Static_Folded",
            "Nodebug_Counter",
            "Twin",
            "Struct_Config",
            "Layout_Gapped",
            "Section_Calib",
        )
        assert code == EXIT_FINDINGS
        lines = err.splitlines()
        main_c = "main.c"
        expected = [
            f"{main_c}:{fixture_line(main_c, 'uint8_t *Type_Pointer;')}: error[elf-type-unsupported]: "
            f"'Type_Pointer' is a pointer, which DDD cannot state",
            f"{main_c}:{fixture_line(main_c, '} Struct_With_Pointer;')}: error[elf-type-unsupported]: "
            f"'Struct_With_Pointer' cannot be described: 'Holder_s.ptr' is a pointer, which DDD "
            f"cannot state",
            f"    note: {main_c}:{fixture_line(main_c, 'uint8_t *ptr;')}: 'Holder_s.ptr' is declared here",
            f"{main_c}:{fixture_line(main_c, '_Thread_local uint32_t Tls_Counter;')}: "
            f"error[elf-no-storage]: 'Tls_Counter' has no address in the image: it is "
            f"thread-local, with an address of its own in every thread",
            f"{main_c}:{fixture_line(main_c, 'static const uint32_t Static_Folded = 7;')}: "
            f"error[elf-no-storage]: 'Static_Folded' has no address in the image: the compiler "
            f"replaced it by its value, and gave it no storage",
            f"{where(X86).render(Path.cwd())}: error[elf-symbol-missing]: the image's debug "
            f"information holds no variable named 'Nodebug_Counter'; the symbol table holds it, "
            f"so the unit defining it was built without debug information (-g)",
            f"unit_a.c:{fixture_line('unit_a.c', 'static uint16_t Twin')}: "
            f"error[elf-symbol-ambiguous]: 'Twin' names a variable in 2 units, 'unit_a.c', "
            f"'unit_b.c': prefix it with one, as 'unit_a.c:Twin'",
            f"{main_c}:{fixture_line(main_c, 'const Inlet_t Struct_Config =')}: "
            f"warning[elf-init-dropped]: 'Struct_Config' starts with values the image holds, "
            f"which DDD does not carry: a structured object is zero-initialised, and its values "
            f"reach it from the running software or from the calibration tool",
            # Gapped_s.b is the line after its unnamed field; Padded_s has a `b : 2` of its own.
            f"{main_c}:{fixture_line(main_c, 'uint8_t : 3;') + 1}: warning[elf-bitfield-gap]: "
            f"'Gapped_s.b' starts at bit 5 although it fits at bit 2: an unnamed or zero width "
            f"bitfield leaves such a gap, which DDD cannot state, so the structure DDD generates "
            f"starts it at bit 2",
            f"{main_c}:{fixture_line(main_c, 'const uint16_t Section_Calib')}: "
            f"warning[elf-section]: 'Section_Calib' is placed in '.calib', the name of the "
            f"image's output section: DDD's section is the one the source places it in, which "
            f"the linker script may have renamed, and the project has to declare it in a "
            f"sections file, or 'ddd check' reports unknown-section",
        ]
        for line in expected:
            assert line in lines, line

    def test_an_error_writes_nothing_and_exits_1(self, capsys: pytest.CaptureFixture[str]) -> None:
        code, out, _ = from_elf(capsys, str(X86), "Cal_Gain", "Type_Pointer")
        assert (code, out) == (EXIT_FINDINGS, "")

    def test_force_writes_what_was_described_and_still_exits_1(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code, out, _ = from_elf(capsys, str(X86), "Cal_Gain", "Type_Pointer", "--force")
        assert code == EXIT_FINDINGS
        assert [entry["definition"]["name"] for entry in json.loads(out)] == ["Cal_Gain"]

    def test_a_consumer_s_entries_state_no_storage(self, capsys: pytest.CaptureFixture[str]) -> None:
        code, out, _ = from_elf(capsys, str(X86), "Section_Calib", "--scope", "input")
        assert code == EXIT_OK
        (entry,) = json.loads(out)
        assert entry["scope"] == "input"
        assert {"init", "section"}.isdisjoint(entry["definition"])

    def test_the_findings_go_to_stderr_as_json_and_the_declarations_stay_on_stdout(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code, out, err = from_elf(capsys, str(X86), "Cal_Gain", "--format", "json")
        assert code == EXIT_OK
        assert json.loads(out)[0]["definition"]["name"] == "Cal_Gain"
        assert [d["check"] for d in json.loads(err)["diagnostics"]] == ["elf-not-inferred"]

    def test_output_writes_the_file_and_leaves_it_alone_when_nothing_changes(
        self, capsys: pytest.CaptureFixture[str], tmp_path: Path
    ) -> None:
        target = tmp_path / "gain.json"
        code, out, err = from_elf(capsys, str(X86), "Cal_Gain", "-o", str(target))
        assert (code, out) == (EXIT_OK, "")
        assert json.loads(target.read_text(encoding="utf-8"))[0]["definition"]["name"] == "Cal_Gain"
        assert err.splitlines()[-1] == f"wrote       {target.as_posix()} (created)"
        code, _, err = from_elf(capsys, str(X86), "Cal_Gain", "-o", str(target), "--format", "json")
        assert code == EXIT_OK
        assert json.loads(err)["generated"] == [{"path": target.as_posix(), "status": "unchanged"}]

    def test_an_output_naming_the_image_is_refused_and_the_image_kept(
        self, capsys: pytest.CaptureFixture[str], tmp_path: Path
    ) -> None:
        image = tmp_path / "copy.elf"
        image.write_bytes(X86.read_bytes())
        code, _, err = from_elf(capsys, str(image), "Cal_Gain", "-o", str(image))
        assert code == EXIT_USAGE
        assert err.splitlines()[-1] == (
            f"ddd: -o would write over '{image.as_posix()}', which this run reads; give it a "
            f"file of its own"
        )
        assert image.read_bytes() == X86.read_bytes()

    def test_an_image_that_cannot_be_used_is_a_usage_error(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        stripped = FIXTURES / "stripped.elf"
        code, out, err = from_elf(capsys, str(stripped), "Cal_Gain")
        assert (code, out) == (EXIT_USAGE, "")
        assert err == (
            f"ddd: '{stripped.as_posix()}' carries no DWARF debug information: build it with -g\n"
        )

    @pytest.mark.parametrize("name", ["1bad", "N" * 129])
    def test_a_component_name_that_is_no_c_identifier_is_a_usage_error(
        self, capsys: pytest.CaptureFixture[str], name: str
    ) -> None:
        code, _, err = from_elf(capsys, str(X86), "Cal_Gain", "--component", name)
        assert (code, err) == (
            EXIT_USAGE,
            f"ddd: --component takes a C identifier of at most 128 characters, not '{name}'\n",
        )

    def test_a_malformed_symbol_is_a_usage_error(self, capsys: pytest.CaptureFixture[str]) -> None:
        code, _, err = from_elf(capsys, str(X86), "main.c:")
        assert (code, err) == (
            EXIT_USAGE,
            "ddd: 'main.c:' names no variable: give a name or a pattern after the unit\n",
        )

    def test_without_pyelftools_the_command_names_the_extra(
        self, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An import answers from sys.modules before it looks at a parent package, so every
        elftools module an earlier test loaded is taken out too - otherwise ddd.elf imports
        again, and its classes are no longer the ones the toolbox tests instances against."""
        loaded = [name for name in sys.modules if name.partition(".")[0] == "elftools"]
        for name in loaded:
            monkeypatch.delitem(sys.modules, name)
        monkeypatch.setitem(sys.modules, "elftools", None)
        monkeypatch.delitem(sys.modules, "ddd.elf", raising=False)
        code, _, err = from_elf(capsys, str(X86), "Cal_Gain")
        assert (code, err) == (
            EXIT_USAGE,
            "ddd: reading an ELF image needs pyelftools, which the 'elf' extra installs: "
            "pip install 'ddd-tool[elf]'\n",
        )

    def test_a_broken_install_is_not_blamed_on_the_extra(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setitem(sys.modules, "ddd.elf", None)
        with pytest.raises(ModuleNotFoundError):
            main(["tool", "from-elf", str(X86), "Cal_Gain"])

    def test_the_toolbox_without_a_tool_is_a_usage_error(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as exited:
            main(["tool"])
        assert exited.value.code == EXIT_USAGE
        assert "TOOL" in capsys.readouterr().err

    def test_the_scopes_offered_are_ddd_s_scopes(self) -> None:
        from ddd.models.component import Scope

        def subcommands(parser: Any) -> dict[str, Any]:
            (action,) = [a for a in parser._actions if a.__class__.__name__ == "_SubParsersAction"]
            return dict(action.choices)

        tool = subcommands(subcommands(_build_parser())["tool"])["from-elf"]
        (scope,) = [action for action in tool._actions if action.dest == "scope"]
        assert set(scope.choices) == {member.value for member in Scope}
```

Where each expected line comes from: `Type_Pointer`'s declaration is the line of its declarator, which gcc states as `DW_AT_decl_line`; `Struct_With_Pointer`'s is the line its declarator closes on (`} Struct_With_Pointer;`); a member's is its own line. The trial build measured each on every row; this test reads them on `x86_64`.

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_cli.py -k ToolFromElf --no-cov`
Expected: FAIL - `SystemExit: 2`, argparse answering `invalid choice: 'tool'`.

- [ ] **Step 3: Implement**

In `src/ddd/cli.py`:

(a) The `collections.abc` import gains `Callable`:

```python
from collections.abc import Callable, Iterator, Sequence
```

(b) After `_FORMAT_HELP`'s docstring:

```python
_ELF_EXTRA_MISSING = (
    "reading an ELF image needs pyelftools, which the 'elf' extra installs: "
    "pip install 'ddd-tool[elf]'"
)
"""The usage error ``ddd tool from-elf`` answers without pyelftools, which is an extra rather
than a dependency: every other command runs without it."""
```

(c) In `_build_parser`, before `return parser`:

```python
    tool = subparsers.add_parser(
        "tool",
        help="run a tool of the toolbox, used once on the way into DDD or out of it",
        description=(
            "The toolbox holds what is run once rather than in every build: a tool that turns "
            "something a project already has into DDD descriptions, or DDD descriptions into "
            "something else. Each tool is a command of its own under this one."
        ),
    )
    tools = tool.add_subparsers(dest="tool", required=True, metavar="TOOL")
    from_elf = tools.add_parser(
        "from-elf",
        help="print the DDD declarations of C variables a linked ELF image describes",
        description=(
            "Reads a linked ELF image and its DWARF debug information, and prints as json the "
            "declaration of every C variable named or matched: its kind, datatype, shape, "
            "enumerators, structure members, initial value and section, as the image states "
            "them. What an image does not state - a unit, a description, limits, a scaling, "
            "whether an array is a curve - is left out, and said once. DDD itself checks every "
            "entry, as 'ddd check --standalone' checks a component, before it is printed. "
            "Needs pyelftools, which the 'elf' extra installs."
        ),
    )
    from_elf.add_argument(
        "image", type=Path, help="the linked ELF image, built with debug information (-g)"
    )
    from_elf.add_argument(
        "symbols",
        nargs="+",
        metavar="SYMBOL",
        help=(
            "a C variable, by name or by a pattern in shell glob syntax, prefixed with UNIT: "
            "to take it from one compilation unit, for a static several units define"
        ),
    )
    from_elf.add_argument(
        "--component",
        metavar="NAME",
        help=(
            "print a component file of this name, holding the types its structures need, "
            "rather than a list of interface entries"
        ),
    )
    from_elf.add_argument(
        "--scope",
        choices=["output", "local", "input"],
        default="output",
        help=(
            "the scope of every entry; input leaves out the initial value and the section, "
            "which a consumer does not state"
        ),
    )
    from_elf.add_argument(
        "-o",
        "--output",
        type=Path,
        help=(
            "write the declarations to this file instead of stdout, leaving the file untouched "
            "when its content would not change"
        ),
    )
    from_elf.add_argument(
        "--force",
        action="store_true",
        help=(
            "write the declarations that were described even where others were not; the exit "
            "code still reports the errors"
        ),
    )
    from_elf.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help=(
            "format of the diagnostics, which go to stderr on this command; the declarations "
            "are json either way"
        ),
    )
    from_elf.set_defaults(handler=_command_tool_from_elf)
```

(d) After `_command_dump`:

```python
def _command_tool_from_elf(args: argparse.Namespace) -> int:
    """``ddd tool from-elf``: the DDD declarations of the C variables a linked ELF image holds.

    stdout carries the declarations and nothing else, as ``dump``'s carries the dictionary, and
    the findings go to stderr in either format. Nothing is written while an error stands unless
    ``--force`` asks for what was described; the exit code reports the errors either way, so
    that a script reads the verdict from the code rather than from the presence of the output.
    """
    try:
        from ddd.elf import open_image
    except ModuleNotFoundError as error:
        # The name is the module the import stopped at - `elftools.common` as often as
        # `elftools` - so the package decides, not the whole name.
        if (error.name or "").partition(".")[0] != "elftools":
            raise
        raise ValueError(_ELF_EXTRA_MISSING) from None
    from ddd.loading import resolve_path
    from ddd.models.common import C_IDENTIFIER_PATTERN, IDENTIFIER_MAX_LENGTH
    from ddd.toolbox.from_elf import describe, document_text

    component = args.component
    if component is not None and (
        not re.fullmatch(C_IDENTIFIER_PATTERN, component) or len(component) > IDENTIFIER_MAX_LENGTH
    ):
        msg = (
            f"--component takes a C identifier of at most {IDENTIFIER_MAX_LENGTH} characters, "
            f"not '{component}'"
        )
        raise ValueError(msg)
    image = open_image(args.image)
    bag = DiagnosticBag()
    description = describe(image, args.symbols, scope=args.scope, component=component, bag=bag)
    if bag.has_errors and not args.force:
        _report(bag, args.format, stream=sys.stderr)
        return EXIT_FINDINGS
    text = document_text(description, component)
    if args.output is None:
        print(text, end="")
        sys.stdout.flush()
        _report(bag, args.format, stream=sys.stderr)
    else:
        _write_output(args.output, lambda: text, bag, args.format, resolve_path(args.image))
    return EXIT_FINDINGS if bag.has_errors else EXIT_OK
```

(e) `_write_dictionary` keeps its signature and docstring, its body becoming one call, and its writing moves into a function of its own:

```python
    _write_output(
        path,
        lambda: _dictionary_text(resolved.dictionary),
        bag,
        output_format,
        *resolved.sources,
    )


def _write_output(
    path: Path,
    text: Callable[[], str],
    bag: DiagnosticBag,
    output_format: str,
    *sources: Path,
) -> None:
    """One text into ``path``, reported the way ``generate`` reports a file: what ``dump -o``
    and ``tool from-elf -o`` write through.

    ``text`` is made inside the reported block, as the dictionary always was, so that a failure
    to make it is reported after the findings of the run exactly as a failure to write it is.
    A path naming a directory, or a file the run read - ``sources`` - is refused.
    """
    from ddd.backends import GeneratedFile, describe_write_failure, write

    with _reported_on_failure(bag, output_format, sys.stderr):
        _refuse_a_directory(path, "-o")
        _refuse_a_source(path, "-o", *sources)
        content = text()
        try:
            (result,) = write([GeneratedFile(path, content)])
        except OSError as error:
            raise OSError(describe_write_failure(error, path.as_posix())) from None
    shown = path.as_posix()
    if output_format == "json":
        payload = _diagnostics_payload(bag)
        payload["generated"] = [{"path": shown, "status": result.status.value}]
        print(json.dumps(payload, indent=2), file=sys.stderr)
        return
    _report(bag, output_format)
    print(_written(result.status, shown), file=sys.stderr)
```

The existing `dump -o` tests are what prove (e) a refactor: none of them may change.

- [ ] **Step 4: The documentation every new command owes**

`tests/test_documentation.py`: `test_the_parser_offers_the_commands_this_suite_knows_about`'s set gains `"tool"`.

`README.md`, the command table, after the `ddd templates-dir` row:

```markdown
| `ddd tool from-elf IMAGE SYMBOL...` | print the declarations of C variables a linked ELF image's DWARF describes, checked by DDD itself; `--component NAME` prints a component file with the types its structures need; needs the `elf` extra |
```

and, in the paragraph on `--format json`, `` `artefacts` and `checks`. The rest `` becomes `` `artefacts`, `checks` and `tool`. The rest ``.

`docs/command_line_interface.rst`: "eight commands understand" becomes "nine commands understand", and ``` ``artefacts`` and ``checks``. That leaves ``` becomes ``` ``artefacts``, ``checks`` and ``tool``. That leaves ```; and the command table gains, after the ``` ``ddd templates-dir`` ``` row:

```rst
   * - ``ddd tool from-elf IMAGE SYMBOL...``
     - print, as json, the declarations of the C variables a linked ELF image's DWARF
       describes - by name, by glob, or narrowed to a unit as ``UNIT:NAME`` - checked by DDD
       itself before they are printed. Needs the ``elf`` extra.
```

Task 9 adds the link to its guide once the page exists. Every gate is green at this commit.

`SPEC.md`, section 7's list of commands: `` live (`ddd cmake-dir`, `ddd templates-dir`; a piece not installed is a usage error); and `` becomes:

```markdown
live (`ddd cmake-dir`, `ddd templates-dir`; a piece not installed is a usage error);
describing the C variables of a linked ELF image as declarations (`ddd tool from-elf`, the
first tool of a toolbox); and
```

keeping the line breaks of the paragraph around it.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_cli.py tests/test_documentation.py --no-cov` - Expected: PASS. Then the whole suite with coverage (`cli.py` at 100 % line and branch), `ruff check .`, `ruff format --check .`, bare `mypy` - each 0.

- [ ] **Step 6: Ablations**

In a scratch worktree: drop the package test on `error.name` (`test_a_broken_install_is_not_blamed_on_the_extra` dies); compare the whole name with `"elftools"` instead of its package (`test_without_pyelftools_the_command_names_the_extra` dies - measured while this plan was written: an import stopped by `sys.modules["elftools"] = None` names `elftools.common`); drop `or len(component) > IDENTIFIER_MAX_LENGTH` (the `N` * 129 case dies - the model would refuse it only at the check, as `schema`, exit 1); drop `resolve_path(args.image)` from `_write_output`'s call (the image-keeping test dies, the image overwritten).

- [ ] **Step 7: Commit**

```bash
git add src/ddd/cli.py tests/test_cli.py tests/test_documentation.py README.md SPEC.md docs/command_line_interface.rst
git commit -m "$(printf 'add ddd tool from-elf to the command line, the first tool of a toolbox\n\nThe declarations go to stdout and nothing else, the findings to stderr; an error\nwrites nothing unless --force, and the exit code says so either way. Without\npyelftools the command is a usage error naming the extra, and every other\ncommand is untouched by its absence. dump -o and from-elf -o write through one\nfunction.\n\nCo-Authored-By: <your model> <noreply@anthropic.com>')"
```

---

### Task 9: the documentation

**Files:**
- Create: `docs/toolbox.rst`
- Modify: `docs/index.rst`, `docs/command_line_interface.rst`, `docs/developer_documentation.rst`, `SPEC.md`, `README.md`, `CHANGELOG.md`
- Test: `tests/test_documentation.py`

**Interfaces:**
- Consumes: `FINDINGS` (the one table of the tool's findings), `examples/firmware/firmware.elf` (Task 1).
- Produces: the user guide, section 7.3 of the specification, and the developer page's account of the fixtures.

The transcripts below were produced by running the commands exactly as `tests/test_transcripts.py` runs them - in-process, stdout and stderr merged, in a copy of `examples/` - over the trial build's `firmware.elf`. Task 1 builds the same image from the same source, so they should hold as they stand; `test_transcripts.py` is the judge. If a line differs, read the new one off the running command and say why in the report.

- [ ] **Step 1: Write the failing test**

In `tests/test_documentation.py`, add `from ddd.toolbox.findings import FINDINGS` to the imports, and append:

```python
class TestToolbox:
    """The findings of ddd tool from-elf, held to the one table of them: each is named in the
    user guide and in the specification, as every check of the catalogue is."""

    GUIDE = PAGES["docs/toolbox.rst"]

    @pytest.mark.parametrize("finding", sorted(FINDINGS))
    def test_every_finding_of_the_tool_is_named_in_the_guide(self, finding: str) -> None:
        assert f"``{finding}``" in self.GUIDE

    @pytest.mark.parametrize("finding", sorted(FINDINGS))
    def test_every_finding_of_the_tool_is_named_in_the_spec(self, finding: str) -> None:
        assert f"`{finding}`" in SPEC
```

Run: `.venv/bin/python -m pytest tests/test_documentation.py --no-cov -k Toolbox`
Expected: FAIL at collection - `KeyError: 'docs/toolbox.rst'`.

- [ ] **Step 2: The user guide**

`docs/toolbox.rst`:

````rst
The toolbox
===========

Some work is done once rather than in every build: bringing what a project already has into
DDD, or taking DDD's descriptions somewhere else. That is what the toolbox is for. Its tools
are commands under ``ddd tool``, and ``ddd tool from-elf`` is the first.

From an ELF image
-----------------

A project that adopts DDD rarely starts from nothing: its variables already exist, in C,
compiled into an image. ``ddd tool from-elf`` reads a linked ELF image and its DWARF debug
information, and prints the DDD declaration of every C variable it is asked for - as far as
the image states it, and checked by DDD itself before it is printed, the way
``ddd check --standalone`` checks a component. It needs pyelftools, which the ``elf`` extra
installs, and an image built with debug information (``-g``):

.. code-block:: text

   pip install 'ddd-tool[elf]'

A variable is named as it is in C, or matched with a glob such as ``'Cal_*'``, and a
``static`` that several compilation units define is taken from one of them by naming its unit
first, ``cal.c:Gain``. What the tool prints is the ``interface`` of a component, ready to paste
into one; ``examples/firmware/firmware.elf`` is an image of the tests' fixture, built for a
Cortex-M4:

.. code-block:: text

   $ ddd tool from-elf firmware/firmware.elf Cal_Gain Enum_State
   [
     {
       "scope": "output",
       "definition": {
         "name": "Cal_Gain",
         "kind": "parameter",
         "datatype": "uint16",
         "conversion": {
           "kind": "identity"
         },
         "init": 300,
         "volatile": false
       }
     },
     {
       "scope": "output",
       "definition": {
         "name": "Enum_State",
         "kind": "measurement",
         "datatype": "uint8",
         "conversion": {
           "kind": "enum",
           "name": "State_t",
           "enumerators": {
             "STATE_OFF": 0,
             "STATE_ON": 1,
             "STATE_FAULT": 200
           }
         },
         "init": 1,
         "volatile": false
       }
     }
   ]
   firmware/firmware.elf: info[elf-not-inferred]: an image states no unit, description, limits, scaling or id, so the output states none: every conversion but an enum's is the identity, the limits are the ones DDD derives, and 'ddd id --assign' writes the ids
   1 info
   $ echo $?
   0

``Enum_State`` is a ``uint8`` because this target makes an enum as small as its values: the
datatype is the one the image states, never the one its C spelling suggests elsewhere.
``--scope input`` prints the same entries as a consumer states them, without the initial value
and the section; ``-o FILE`` writes them into a file instead of standard output.

What an image states, and what it does not
------------------------------------------

.. list-table::
   :header-rows: 1
   :widths: 28 72

   * - key
     - where it comes from
   * - ``kind``
     - the variable's ``const``: a ``measurement`` without it; with it a ``parameter``, or a
       ``value_block`` for an array. Nothing in an image tells a curve, a map or an axis from
       any other array, so none is inferred.
   * - ``datatype``
     - the encoding and size DWARF states: ``long``, plain ``char`` and an enum follow the
       target that built the image.
   * - ``conversion``
     - the identity, or an ``enum`` conversion carrying the enumerators in declaration order,
       named after the typedef closest to the enum, else its tag.
   * - ``dimensions``
     - the array's extents, in C order.
   * - ``init``
     - the image's own bytes, in its byte order; an array of one value as that value, a
       ``float32`` in the fewest digits that read it back. None for a variable in a section
       without contents, which starts at zero.
   * - ``section``
     - stated only where the variable's section is not one of the toolchain's defaults. It is
       the image's output section, which is the name the source used when the linker script
       kept it, and the project has to declare it in a sections file.
   * - ``volatile``
     - the qualifier.
   * - ``typename`` and ``types``
     - a structure, its members, bitfields and nested structures, one ``types`` entry per
       structure.
   * - ``unit``, ``description``, ``limits``, ``id``, ``raster``, the ``a2l`` block
     - nothing in an image states them. They are left out, and the run says so once:
       ``elf-not-inferred``.

Structures
----------

A variable of a structure names it as its ``typename``, and ``--component NAME`` prints a whole
component file, with a ``types`` entry for every structure the variables reach:

.. code-block:: text

   $ ddd tool from-elf firmware/firmware.elf Struct_Inlet --component Inlet
   {
     "component": {
       "name": "Inlet",
       "types": [
   ...
       "interface": [
         {
           "scope": "output",
           "definition": {
             "name": "Struct_Inlet",
             "kind": "measurement",
             "typename": "Inlet_t",
             "volatile": false
           }
         }
       ]
     }
   }
   main.c:57: warning[elf-name-synthesized]: an anonymous structure is named 'Inlet_t_pair_t', after the first thing that reaches it; rename it if the source has a better name
   firmware/firmware.elf: info[elf-not-inferred]: an image states no unit, description, limits, scaling or id, so the output states none: every conversion but an enum's is the identity, the limits are the ones DDD derives, and 'ddd id --assign' writes the ids
   main.c:63: info[elf-boolean-bitfield]: 'Inlet_t.ready' is a _Bool bitfield, described as a uint8 one of the same width: DDD refuses a boolean bitfield
   1 warning, 2 infos

The list output has nowhere to put a ``types`` entry, and says so (``elf-types-omitted``). A
structure's entry belongs once in a project: where two components need it, move it into a
shared types file rather than pasting it into both.

A structure is named by the typedef closest to it, else by its tag, and an anonymous one after
the first thing that reaches it (``elf-name-synthesized``). Two structures of one name that
differ - one per compilation unit, each unit's own - are ``elf-type-conflict``, and no
variable reaching either is printed. A ``_Bool`` bitfield is described as a ``uint8`` one
(``elf-boolean-bitfield``), since DDD refuses a boolean bitfield, and ``const`` or ``volatile``
on a member is dropped (``elf-qualifier-dropped``): DDD qualifies whole objects. A structured
object states no initial value, as DDD requires; values the image holds for one are dropped
and said to be (``elf-init-dropped``).

The layout of a structure
~~~~~~~~~~~~~~~~~~~~~~~~~

DDD states member order, datatypes and widths, never offsets, and the compiler lays out the
structure it generates. Nothing in the a2l depends on that, but the structure DDD generates can
lay out differently from the source's where the source asked for a layout its members do not
imply - and DWARF records none of those requests directly. The tool warns about the two traces
it can read: bits skipped where the next bitfield would have fit, which an unnamed or zero
width bitfield leaves (``elf-bitfield-gap``), and an alignment the source states
(``elf-alignment``). Packing - ``#pragma pack``, ``packed`` - is not detected: whether an
offset is packed or merely the target's own alignment depends on the ABI.

What the tool cannot describe
-----------------------------

A variable that cannot be described is not printed, and a run with one exits ``1`` and writes
nothing, unless ``--force`` asks for what could be described:

.. code-block:: text

   $ ddd tool from-elf firmware/firmware.elf Type_Pointer Tls_Counter Cal_Gain
   main.c:106: error[elf-no-storage]: 'Tls_Counter' has no address in the image: it is thread-local, with an address of its own in every thread
   main.c:38: error[elf-type-unsupported]: 'Type_Pointer' is a pointer, which DDD cannot state
   firmware/firmware.elf: info[elf-not-inferred]: an image states no unit, description, limits, scaling or id, so the output states none: every conversion but an enum's is the identity, the limits are the ones DDD derives, and 'ddd id --assign' writes the ids
   2 errors, 1 info
   $ echo $?
   1

A finding about a variable is shown at its declaration in the C source, as the image recorded
the path. An image that cannot be used at all - not ELF, without DWARF, a relocatable object
rather than a linked image - is a usage error, exit ``2``.

The findings
~~~~~~~~~~~~

They are the tool's own rather than checks of the catalogue: ``ddd checks`` does not list them
and ``-W`` does not take them. DDD's own findings on the declarations are reported beside them
under DDD's identifiers.

.. list-table::
   :header-rows: 1
   :widths: 30 12 58

   * - finding
     - severity
     - when
   * - ``elf-symbol-missing``
     - error
     - a name or a pattern matches no variable of the image's debug information; where the
       symbol table holds the name, the unit defining it was built without ``-g``
   * - ``elf-symbol-ambiguous``
     - error
     - several compilation units define the name; ``UNIT:NAME`` takes one
   * - ``elf-no-storage``
     - error
     - the variable has no address: only declared, folded into a constant, or thread-local
   * - ``elf-type-unsupported``
     - error
     - a type DDD cannot state - a pointer, a union, a ``long double`` wider than eight bytes,
       a ``const`` array of structures - named at the member where it occurs
   * - ``elf-type-conflict``
     - error
     - one name stands for two different structures or enums
   * - ``elf-init-unsupported``
     - error
     - an initial value DDD has no spelling for, such as NaN
   * - ``elf-init-dropped``
     - warning
     - a structured object whose values the image holds
   * - ``elf-bitfield-gap``
     - warning
     - bits skipped where the next bitfield would have fit
   * - ``elf-alignment``
     - warning
     - an alignment the source states
   * - ``elf-qualifier-dropped``
     - warning
     - ``const`` or ``volatile`` on a structure member
   * - ``elf-section``
     - warning
     - a section the output states, once per name
   * - ``elf-name-synthesized``
     - warning
     - an anonymous structure or enum given a name
   * - ``elf-types-omitted``
     - warning
     - the list output holds a structured object, whose type only ``--component`` prints
   * - ``elf-boolean-bitfield``
     - info
     - a ``_Bool`` bitfield described as a ``uint8`` one
   * - ``elf-not-inferred``
     - info
     - once per run: what an image never states
````

- [ ] **Step 3: The rest of the documentation**

`docs/index.rst`: the *Using DDD* toctree gains `toolbox` after `command_line_interface`.

`docs/command_line_interface.rst`: the `ddd tool from-elf` row of Task 8 gains the link - `` checked by DDD itself before they are printed. Needs the ``elf`` extra. `` becomes `` checked by DDD itself before they are printed; :doc:`toolbox` is the guide. Needs the ``elf`` extra. ``

`docs/developer_documentation.rst`, the *Layers* table gains, after the `src/ddd/lsp/` row:

```rst
   * - ``src/ddd/elf.py``
     - ELF images, DWARF 2 to 5, C types, the variables of static storage
     - DDD: it imports no ``ddd`` module
   * - ``src/ddd/toolbox/``
     - turning what a project already has into DDD descriptions, once
     - where its output goes, any output format
```

In *The split is enforced by a test*, the layered modules named become `` ``loading.py``, ``analysis.py``, ``ir.py``, ``diagnostics.py``, everything under ``backends/``, ``plugins.py``, ``elf.py`` and everything under ``toolbox/`` ``; the bullet on `plugins.py` ends in a comma instead of a full stop, and two bullets follow it:

```rst
* ``elf.py`` imports no ``ddd`` module at all, so that reading an address map straight out of
  an image can use it without the toolbox, and
* nothing under ``toolbox/`` imports a backend or ``ddd.cli``.
```

After *The coverage gate*, a section:

```rst
The ELF fixtures
----------------

``ddd tool from-elf`` is tested against ten images of one C source - little and big endian, 32
and 64 bit, gcc and clang, DWARF 2 to 5, compressed debug sections and not, a static PIE - which
``tests/fixtures/elf/`` holds beside a manifest of what each image's own toolchain says about its
target: byte order, the signedness of ``char``, the sizes of ``long``, ``long double`` and an
enum, the alignment of a ``uint64_t``, and the section and size of every symbol. The reader's
tests hold it to the manifest, never to itself. ``examples/firmware/firmware.elf`` is a copy of
the Cortex-M4 image, for the transcripts of :doc:`toolbox`.

The images are committed, so the suite needs neither Docker nor a compiler. They are built in
Docker, out of ``tests/fixtures/elf/src/``, by ``docker/build_elf_fixtures.py`` in the image of
``docker/elf-fixtures.Dockerfile``, a Debian image pinned by digest:

.. code-block:: text

   $ docker compose run --rm elf-fixtures  # rebuilds every image and the manifest

The manifest holds a hash of every file the images are built from, and
``tests/test_elf_fixtures.py`` fails, naming that command, when one of them changed without a
rebuild. Commit what the rebuild writes.
```

`SPEC.md`:

- The table of contents gains `    - [7.3 Toolbox](#73-toolbox)` after the 7.2 line.
- Section 6's `` against the declarations is *planned*. `` gains, after that sentence: `` The reader ``ddd tool from-elf`` uses ([section 7.3](#73-toolbox)) reads ELF images and their DWARF already, and imports nothing of DDD, so that reading the address map can use it. `` - with single backticks, it being markdown.
- Section 7's list: `` (`ddd tool from-elf`, the first tool of a toolbox) `` becomes `` (`ddd tool from-elf`, the first tool of a toolbox, [section 7.3](#73-toolbox)) ``, keeping the paragraph's line breaks.
- At the end of the file, after section 7.2:

```markdown
### 7.3 Toolbox

`ddd tool` holds the tools run once rather than in every build, on the way into DDD or out of
it. Its one tool is `from-elf`.

`ddd tool from-elf IMAGE SYMBOL...` reads a linked ELF image, `ET_EXEC` or `ET_DYN`, and its
DWARF debug information, versions 2 to 5, and prints the declarations of the C variables named
or matched, as json on standard output: a list of interface entries, or with `--component NAME`
a component file whose `types` holds the structures the variables name. A `SYMBOL` is
`[UNIT:]PATTERN`: a C identifier matched exactly, or a glob matched case sensitively, narrowed
to the compilation unit whose name is `UNIT` or ends in `/UNIT`. A candidate is a variable at
the top of a unit with a static address; the `static` locals of a function are not candidates.

What the image states, the declaration states:

- `kind`: a `measurement` without `const`; with it a `parameter`, or a `value_block` for an
  array. A `const` array of structures is refused, since a `parameter` has no `dimensions` and
  a `value_block` holds no structure ([section 3.7](#37-type-description)). A curve, a map or
  an axis is never inferred.
- `datatype`: from the DWARF encoding and size - `boolean` of one byte, `uint8` to `uint64`,
  `sint8` to `sint64`, `float32` and `float64`. Any other pairing, a pointer, a union, an
  `_Atomic` type or a function is refused.
- `conversion`: the identity, or an `enum` conversion carrying the enumerators in declaration
  order, named by the typedef closest to the enum, else by its tag, else by a name made from
  what first reaches it.
- a structure: its `typename`, and one `struct` entry of `types`, members in declaration
  order, a bitfield a `bits` member. `const` or `volatile` on a member cannot be stated, and a
  `_Bool` bitfield is described as a `uint8` one.
- `init`: from the image's bytes in its byte order - an array whose elements are all equal as
  that one value, a `float32` as the shortest decimal that reads back to it - and none for a
  variable in a section without contents, which starts at zero. A structured object states
  none ([section 3.7](#37-type-description)).
- `section`: where the variable's section is not one of the toolchain's defaults, `.data`,
  `.bss`, `.rodata`, `.sdata`, `.sbss`, `.sdata2`, `.sbss2`, `.srodata`, `.data1` and
  `.rodata1`. It is the image's output section, which the project **must** declare
  ([section 3.5](#35-memory-placement)).
- `volatile`: from the qualifier.

`--scope` is `output`, the default, `local` or `input`; an `input` entry states neither `init`
nor `section` (`consumer-storage`, [section 3.3.1.2](#3312-storage)). Nothing else is stated:
no `unit`, `description`, `limits`, `id`, `raster` or `a2l` block.

Before anything is printed, DDD's own loader and analysis check the declarations, under the
policy of `ddd check --standalone` with `missing-id` ignored. A variable one of their errors
concerns is left out, and the check is repeated until none remains, since a load error stops
DDD before its analysis. Their findings are reported with the tool's own, under their own
identifiers.

The tool's own findings are not checks of [section 4](#4-consistency-checks) and take no `-W`:
`elf-symbol-missing`, `elf-symbol-ambiguous`, `elf-no-storage`, `elf-type-unsupported`,
`elf-type-conflict` and `elf-init-unsupported` are errors; `elf-init-dropped`,
`elf-bitfield-gap`, `elf-alignment`, `elf-qualifier-dropped`, `elf-section`,
`elf-name-synthesized` and `elf-types-omitted` warnings; `elf-boolean-bitfield` and
`elf-not-inferred` infos. A finding about a variable is located at its declaration in the C
source, as the image recorded the path.

The layout of a structure is not checked: DDD states no offsets
([section 3.7](#37-type-description)), and DWARF records neither packing nor an unnamed
bitfield. The gap such a bitfield leaves where the next one would have fit is
`elf-bitfield-gap`, and an alignment the source states is `elf-alignment`.

The exit code is `0` when every argument was described, and `1` when one was not; nothing is
written then unless `--force`, which writes what was described. An image that cannot be read,
is not ELF, carries no DWARF or is not linked, an `-o` naming the image, and a missing
pyelftools - which the `elf` extra installs - are usage errors, `2`.
```

`README.md`: after `Requires Python 3.12 or newer; the only runtime dependencies are pydantic and jinja2.`, a sentence: `` `ddd tool from-elf` reads ELF images with pyelftools, which the `elf` extra installs: `pip install 'ddd-tool[elf]'`. ``

`CHANGELOG.md`, above `## 0.11.0`:

```markdown
## Unreleased

* **A toolbox, and its first tool: `ddd tool from-elf`.**  It reads a linked ELF image and its
  DWARF debug information and prints the DDD declarations of the C variables named or matched
  on the command line - kind, datatype, shape, enumerators, structure members, initial value
  and section, as the image states them - as a list of interface entries or, with `--component
  NAME`, a component file holding the types its structures need.  DDD itself checks every
  entry before it is printed, as `ddd check --standalone` checks a component; what an image
  does not state, a unit or a scaling, is left out and said once.  It needs pyelftools, which
  the new `elf` extra installs (`pip install 'ddd-tool[elf]'`); the runtime dependencies are
  unchanged, and every other command runs without it.  No file format changes.
```

- [ ] **Step 4: Run the documentation's tests**

Run: `.venv/bin/python -m pytest tests/test_documentation.py tests/test_transcripts.py --no-cov` - Expected: PASS. The transcripts of `docs/toolbox.rst` run in-process over the scratch copy of `examples/`; `docs/developer_documentation.rst`'s docker line carries a trailing comment, which shows it rather than runs it. Then the whole suite, `ruff check .`, `ruff format --check .`, bare `mypy`.

- [ ] **Step 5: Build the documentation**

The docs build runs in Docker, under this branch's own image - never `ddd:dev`:

```bash
printf 'services:\n  test:\n    image: ddd-toolbox:dev\n  docs:\n    image: ddd-toolbox:dev\n' > build/compose.toolbox.yml
docker compose -p ddd-toolbox -f docker-compose.yml -f build/compose.toolbox.yml run --rm --user "$(id -u):$(id -g)" -e JAVA_TOOL_OPTIONS=-Duser.home=/tmp docs; echo "DOCS=$?"
```

Expected: `DOCS=0`, the build running with `-W`. Open `build/docs/html/toolbox.html` and read it.

- [ ] **Step 6: Ablation**

In a scratch worktree: drop the `elf-alignment` row from the guide's table and its name from section 7.3 (both parametrized cases of `elf-alignment` die).

- [ ] **Step 7: Commit**

```bash
git add docs/toolbox.rst docs/index.rst docs/command_line_interface.rst docs/developer_documentation.rst SPEC.md README.md CHANGELOG.md tests/test_documentation.py
git commit -m "$(printf 'document ddd tool from-elf: its guide, section 7.3, and its fixtures\n\nThe guide s transcripts run over examples/firmware/firmware.elf in the suite,\nand every finding of the tool is held to being named in the guide and in the\nspecification, as every check of the catalogue is.\n\nCo-Authored-By: <your model> <noreply@anthropic.com>')"
```

## Milestone gate

Every gate on the branch tip, none taken from an earlier task's run, each with its own exit status. Before Task 1, note `ddd:dev`'s image id - `docker image ls ddd:dev --format '{{.ID}}'` - so that the last line below can prove this branch never touched it.

```bash
cd /home/sauci/Documents/Github/ddd-toolbox-from-elf
.venv/bin/python -m pytest > build/gate.txt 2>&1; echo "PYTEST=$?"; tail -3 build/gate.txt
.venv/bin/ruff check .; echo "RUFF=$?"
.venv/bin/ruff format --check .; echo "FMT=$?"
.venv/bin/mypy; echo "MYPY=$?"
printf 'services:\n  test:\n    image: ddd-toolbox:dev\n  docs:\n    image: ddd-toolbox:dev\n' > build/compose.toolbox.yml
docker compose -p ddd-toolbox -f docker-compose.yml -f build/compose.toolbox.yml build test
docker compose -p ddd-toolbox -f docker-compose.yml -f build/compose.toolbox.yml run --rm --user "$(id -u):$(id -g)" test > build/gate-312.txt 2>&1; echo "PY312=$?"; tail -3 build/gate-312.txt
docker compose -p ddd-toolbox -f docker-compose.yml -f build/compose.toolbox.yml run --rm --user "$(id -u):$(id -g)" -e JAVA_TOOL_OPTIONS=-Duser.home=/tmp docs; echo "DOCS=$?"
docker compose -p ddd-toolbox run --rm elf-fixtures; echo "FIXTURES=$?"
git status --short tests/fixtures/elf examples/firmware
docker image ls ddd:dev --format '{{.ID}}'
```

- `PY312` is the suite on Python 3.12, the image's - the venv is 3.14, and nothing newer than 3.12 may have crept in. The image is built from this worktree under its own tag; the override file is what keeps it off `ddd:dev`.
- The fixture rebuild is the reproducibility check: `git status` must list nothing under `tests/fixtures/elf` or `examples/firmware`. A difference is a finding - report which files moved and whether the manifest's traits did.
- The last line must print the id noted before Task 1.

And by hand, over `examples/firmware/firmware.elf` and the `powerpc` row: print a glob of calibration variables as a list and as a component; paste the component into a scratch project under `build/` with a sections file declaring `.calib`, and run `ddd check` on it (not `--standalone`); read every finding. Then print `Struct_With_Pointer` and `Twin`, and read the refusals as a user would.

## Progress log

| Task | Commits | Review | Notes |
| --- | --- | --- | --- |
| 1 the fixture matrix | | | |
| 2 the reader over protocols | | | |
| 3 pyelftools and the matrix | | | |
| 4 findings and selection | | | |
| 5 the mapping | | | |
| 6 initial values | | | |
| 7 DDD's check, `describe` | | | |
| 8 the command line | | | |
| 9 the documentation | | | |

## What was left open

Filled in as the work goes. Each entry says what was not done and what it costs.

- **Packing is not detected** (spec section 4.5). A packed structure is described member for member, and DDD's generated structure is not packed. The user guide says so; comparing offsets against a layout the image's own toolchain computes is its own piece of work (spec section 11).
- **No custom section without contents and no `_Atomic` variable in the fixtures** (ruling 2): both reached through hand-built models and doubles only.
- **A glob over a large image is checked by DDD in one component**, every pass writing and loading it again. Nothing was measured on a large image; a run describing thousands of variables with many refusals would repeat the analysis once per pass.

## Rulings taken

| # | Ruling | Why | Cost if wrong |
| --- | --- | --- | --- |
| 1 | **The build script is `docker/build_elf_fixtures.py` and the Dockerfile `docker/elf-fixtures.Dockerfile`** - a departure from the spec's `docker/elf-fixtures/` directory | `pyproject.toml` puts `docker/` on pytest's path; a hyphenated subdirectory is no package, and the drift guard must import the script's own `hashed` rather than restate it | None: the compose service names the Dockerfile |
| 2 | **No fixture case for a custom section without contents, nor for `_Atomic`** | gcc marks a section `@nobits` only when its name starts `.bss.`, which the default linker scripts fold into `.bss`; whether DWARF keeps `_Atomic` depends on the version and strictness. Both are covered by hand-built models (Task 7) and doubles (Task 2) | A toolchain answering differently for either goes unmeasured |
| 3 | **`Image` is a frozen dataclass whose variables, sections and symbols are attributes**, not the methods the spec's sketch shows | It is data `open_image` fills once; tests build one by hand | None |
| 4 | **The translator is five modules** - `findings`, `selection`, `mapping`, `values`, `checked` - beside `from_elf`, not one | One responsibility each; `from_elf` only orchestrates | None |
| 5 | **A variable without a location whose name is an `STT_TLS` symbol is thread-local** - not in the spec | aarch64's gcc 14 and clang 19 state no location at all for a thread-local variable (the trial build); without the symbol table the reason would read "removed", which is false | A local static and a thread-local global of one name would both read as thread-local; none is known |
| 6 | **The manifest records `TLS` symbols as well as `OBJECT` ones** | The thread-local test reads the section of `Tls_Counter` from it; `readelf` types that symbol `TLS` | None |
| 7 | **pyelftools `>=0.32,<1`** | Measured: 0.32 reads the trial matrix as 0.33 does; 0.31 and older lack `has_dwarf_info(strict=...)` | Re-measured in Task 3 |
| 8 | **Task 8 writes the least documentation a new command owes** - the README's row, the command page's row and its `--format json` count, the spec's list, the test's command set | The documentation tests fail on an undocumented command, and no commit may leave a gate red | Task 9 writes the rest; nothing is documented twice |
| 9 | **The x86_64 row is a static PIE** | It gives `ET_DYN` a real image, the spec accepting both kinds | None |
| 10 | **Spec corrections made while planning** (commit `aa2984b` and the plan's own commit): `note` is `info`; the check adds `missing-id=ignore`; the typedef closest to a type names it; a section without contents states no `init` rather than `init: null`; strict DWARF 2 and a unit without `-g` join the matrix | Each measured or read off DDD's code while this plan was written | Recorded in the spec's evidence section |
