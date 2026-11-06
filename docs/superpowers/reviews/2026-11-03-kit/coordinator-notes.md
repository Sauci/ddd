## The coordinator's own reading

Read and measured directly by the coordinator before any pass ran, and deliberately not handed to the
passes of part A, so that their readings stay independent. Each item is compared with what the passes
found once they have reported.

### R1. `--const-inputs` changes what the compiler may assume (reproduced)

`docs/concept.rst:193-200` and `README.md:711-715` say the mismatch between a consumer's
`extern const` and the definition's non-const is "a constraint violation in strict c ... even though
the usual embedded toolchains accept it and generate exactly the code one expects". Two things are
wrong with that:

- It is not a constraint violation. Two declarations of one object in different translation units
  with incompatible types is undefined behaviour under C11 6.2.7p2, which requires no diagnostic.
- The code is not what one expects. gcc 15.2 at `-O2` treats an `extern const int` that is not
  volatile as unchanged across a call to another translation unit:

  ```c
  extern const int ValueF;
  void step(void);
  int twice(void) { int before = ValueF; step(); return before + ValueF; }
  int wait_for_ten(void) { while (ValueF < 10) { step(); } return ValueF; }
  ```

  `twice` loads `ValueF` once and doubles it (`leal (%rbx,%rbx), %eax`); `wait_for_ten` loads it once,
  and if it is below ten spins in `.L5: call step; jmp .L5` forever. The same source with plain
  `extern int` re-reads it after every call. So a consumer built with `--const-inputs` that reads a
  non-volatile input on both sides of a call sees a stale value, and a loop waiting on one never ends.
  A measurement is exactly an object another component writes, and `volatile` is `false` on most of
  them, as the document itself says it may be. Probe: `SCRATCH/constprobe/`.

### R2. Measured shape of `src/ddd` (39,696 lines, 89 files)

`SCRATCH/layers.py` computes the import graph, top-level and lazy, `SCRATCH/layers.txt` its output.

- `ddd.lsp` is no longer the language server alone: `lsp.ranges` has 21 importers and `lsp.navigation`
  18, most of them outside `lsp/`. `ddd.editing`, `ddd.identity` and fourteen root modules import it,
  and `lsp.edits`, `lsp.units` and `lsp.navigation` import them back, so the package boundary is a cycle
  in both directions. `identity.py` says it itself: `ranges` "happens to live under the language
  server". `lsp/__init__.py` still opens "The language server".
- Fourteen modules at the package root are imported by the GUI alone or by each other, and describe
  themselves in the GUI's words ("as the Units tab of `ddd gui` shows them", "the unit panel"), while
  calling themselves transport-neutral: `declaration_plans`, `file_plans`, `shared_plans`, `type_plans`,
  `project_shared`, `project_types`, `project_units`, `variables`, `variable_keys`, `object_values`,
  `finding_routes`, `finding_fixes`, `findings_by_file`, `graph`. Nothing in the tree says they are a layer.
- `tests/test_backends.py`'s guards name the front end and the backends. Neither `gui/` nor `lsp/` nor the
  fourteen modules is guarded, so "the layering cannot rot silently" holds for less than half the code.
- `docs/developer_documentation.rst:19-58` (Layers) does not have a row for `src/ddd/gui/` or for any of
  the fourteen; line 75 says "six smaller modules sit beside them"; line 92 calls `lsp/` "a second front
  end". `README.md:1033-1041` (Layout) stops at the backends as well.
- `gui.api.Api` is one class of 1,366 lines. `cli._build_parser` is one function of 426.

### R3. Measured shape of `gui/src` (production code 16,000 lines, generated 6,560)

`SCRATCH/tslayers.py`. The direction is mostly sound: `components` and `ui` import no `state`, no query
library and only the types of `api`; `lib` is pure and sits under a 100 % gate; `screens` hold the hooks.
A cycle `api/client` <-> `state` exists (`api/client.ts:1` imports `state/edits`, `state/revisions.ts:1`
imports `api/client`). No identifier pattern, numeric range or datatype table turned up in `lib/`,
`screens/` or the views by a first grep, which is good, and is for pass 3 to confirm or refute by reading.

### R4. The documents

- `docs/index.rst` has `gui_security` and no page on using the GUI: there is no guide to a part of the
  product that is, measured in lines, as large as all of the rest. `docs/developer_documentation.rst`'s
  section The browser interface is mostly the mechanics of test fixtures and benchmarks; no page says how
  the GUI is put together.
- `SPEC.md`, which calls itself the authoritative contract, mentions `ddd gui` twice (lines 785, 2136) and
  specifies nothing of it.
- `SPEC.md:2215` says the dictionary's `format` is "today `8`"; `src/ddd/ir.py:645` says 9. Reported on
  2026-09-24 and still there.
- Production code cites planning artefacts in 103 places ("Task 2 is the only caller", "part 5's stack",
  "Appendix A of docs/superpowers/plans/...", `graph.py`, `gui/compare.py`, `gui/queries.py`,
  `declaration_plans.py`, ...).

### What the passes made of R1 to R4

The passes found each of the coordinator's readings again, independently, and took each further. The
one reading that was wrong was the coordinator's, and a pass corrected it.

- **R1 is 1:C1**, which V1 confirmed on gcc 15.2. The stale read happens from `-Og` up, with no
  warning under the CI's `-Werror` set. The pass added that the documents call it a constraint
  violation, where C11 makes it undefined behaviour.
- **R2 is 2:I1, 2:I2, 2:I4 and 2:I5**, with 2:M9 for the planning artefacts cited from the code. Pass 2
  measured it further: the edit layer's 9,040 lines, the 12-module cycle behind two deferred imports,
  and 33 of 33 realistic violations passing the guards. It then drew the target structure. Pass 24
  measured the graph again: 87 modules, 363 edges, and no cycle among top-level imports.
- **R3's positive half held.** The `api` and `state` cycle is 3:M2. **Its negative half did not.** A
  first grep found no domain rule in the page, but pass 3 found several by reading: 3:C1 (64-bit
  integers held as doubles), 3:I1 and 3:I3.
- **R4 is 4:I1 and 4:I5** for the missing GUI documentation, and **4:I9** for SPEC's silence on
  `ddd gui`, which V2 lowered to Minor. The dictionary format number is **4:M12** and **5:I1**, which
  V3 lowered to Minor as a duplicate. The planning artefacts cited from the code are **2:M9** for the
  Python and **3:M10** for the page.

### An accident during the review

Pass 19 ran one probe as root in the WSL instance `Ubuntu-24.04`, to show what the writer does to a
device (its M9), and the probe also replaced that instance's real `/dev/null` with a regular file. Nobody
had asked for root. The pass restored the device at once with `mknod`; a later sweep of `/tmp` as root
was refused and not retried. The coordinator checked on 2026-11-04, after the instance had restarted:
`/dev/null`, `/dev/zero` and `/dev/full` are character devices of mode 666 (1,3, 1,5 and 1,7), and
`/dev/null` takes a write from the ordinary user and reads empty. Neither the repository nor Windows was
touched. From pass 20 on, the brief forbids root and system paths as targets.
