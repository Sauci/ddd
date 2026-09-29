# Rasters in the GUI

`ddd gui`'s Shared files tab holds two of the three vocabularies it was built for. A project that
declares `10ms` — a DAQ event the target offers, claimed by event channel 3, sampled every ten
milliseconds — has no page for it, so `unknown-raster`, `duplicate-raster` and `duplicate-event` are
dead ends and a definition reading `"raster": "10ms"` is a name with nowhere to go.

This adds rasters to that tab. It is part 15, and the last vocabulary of milestone 6; the project's
`includes` and new files remain after it.

**This design inherits part 14's.** `docs/superpowers/specs/2026-09-27-gui-sections-design.md`
deliberately covered all three vocabularies, so its table of containers, name keys, editable keys,
row cells and created files stands unchanged and is not restated here. Its refuse/report line, its
removal guard and its account of what the index must learn stand too. What follows is only what that
design could not know, because it was written before sections were built.

---

## 1 What part 14 settled, and this part consumes

From `2026-09-27-gui-sections-design.md` §2, unchanged:

| | rasters |
| --- | --- |
| container | `rasters` |
| name key | `raster` |
| editable keys | `event`, `cycle` |
| what a row states | `event 3, 10ms` |
| created file | `rasters.ddd.json` |
| a second home | none |

**One key of that table is optional, which is new.** `RasterDeclaration.cycle` is `str | None = None`,
where a section's `access` and `alignment` are both mandatory and a constant's `value` is. So
`RASTERS.required` is `{"event"}` alone, and the row's cell is the first composed from a key that may
not be there: `event 3, 10ms` when a raster states its cycle and `event 3` when it does not. A
section's cell interpolates two keys unconditionally because it can. This is a difference the
descriptor already carries — `required` exists for exactly this — but the cell's own composition has
to answer it rather than assume both.

And from its §4.1, already delivered by part 14: `Index.rasters` and `Index.raster_uses` are
populated, `renameable_at` answers `("raster", name)`, and `rename_sites` answers for a raster from
its entry and from every use. **One use shape is a raster's alone**: a definition names one at
`definition.raster`, and a component names one at `component.raster` as its default for everything it
produces — a use inside no definition at all. That is indexed already.

## 2 Three corrections to the inherited design

**`rename_problem` judges a raster's name.** Part 14's §2 says *"Neither a section's name nor a
raster's joins `occupied`, and `rename_problem` judges neither."* Its first half stands. Its second
half was reversed while part 14 ran: `rename_problem` is the one entry point both the tab and the
editor's `F2` already reach, and `ddd.lsp.navigation` cannot import `ddd.project_shared` — that module
needs `Index` — so writing each vocabulary's name rule anywhere else writes it twice. A raster gets
its own arm beside the section's, judged by `RasterName` and refusing a name the project already
declares. Until it does, `rename_problem` answers *"'10ms' is not a usable c identifier"*, which is
false about an a2l short name and is disclosed in that function's own docstring today.

**`Use.kind` widens.** `ddd.project_shared.Use.kind` is `Literal["variable", "member"]`, which is
constants-shaped: a constant is named by a declaration's dimension or a structure member's. A section
needed no change, because a section is named by a definition and so its use is that variable's. A
component naming a raster is neither, so the literal gains a third word. This is the first time the
type has had to move, and it moves because of a use shape the other two vocabularies do not have.

**Go to definition stays absent.** Part 14's plan claimed teaching `renameable_at` two kinds would
give `ddd lsp` "rename and go to definition on them". Only rename shipped: `definition()` is a
separate function no task owned, and measured on the tip it answers the declaration the cursor is
already inside for a definition's `section` key. Rasters inherits that gap rather than closing it, and
`docs/editor_integration.rst` keeps saying only what is true. Closing it is its own small piece of
work, for either vocabulary at once.

## 3 The descriptor grows one field

A raster has **two** project-unique keys: its name, and its `event`. The descriptor can express one.
`_judged(vocabulary, key, raw, name, file)` takes no `Index`, so a key's judge can ask whether a value
is legal and never whether it is taken; only `name_judge` gets the index, because — as its own
docstring says — "the answer depends on what the project already holds".

Part 14's §2 warned that *a fourth vocabulary that differed structurally would reopen the record*. The
third reopens it, for a reason worth naming: `event` is the first key that is neither free text nor a
name, but is the project's alone.

**`name_judge` becomes `taken`, a map from key to a project-aware judge.**

| | `taken` |
| --- | --- |
| `CONSTANTS` | `{"name": …}` |
| `SECTIONS` | `{"section": …}` |
| `RASTERS` | `{"raster": …, "event": …}` |

- `rename_entry` asks `taken[name_key]`, which is what `name_judge` did.
- `set_entry` asks `taken.get(key)` when the key has one, before it writes.
- `Vocabulary.__post_init__` gains its fifth invariant: every key of `taken` is either `name_key` or
  one of `keys`. The map cannot drift from the table beside it, which is the hazard that shipped four
  unpinned descriptor values in part 14 and was found by a review rather than by a gate.

**A judge takes the entry and the cache as well as the value.**
`Callable[[Index, str | None, str, dict[Path, Document]], str | None]` — the index, the entry whose
key is being set or `None` where there is none yet, the wanted value, and the document cache.

The entry is there because an event needs it. A panel asks for a plan on every keystroke, so a reader
re-typing the `3` their raster already claims would otherwise be told that `3` is taken — by
themselves. A name judge ignores it: part 14 settled that renaming a name to itself is refused and
says nothing about a reader's real mistake either way, so ignoring it preserves a decision.

The cache is there because `Index.rasters` maps a name to a `Site` and **not to its event**. Asking
which raster claims event 3 means reading each entry's own text, which is what `text_of` and
`string_of` already do and what they already take a cache for. A name judge ignores this too — a name
is in the index — so both name judges carry two arguments they do not read, which is the price of one
map over two fields. `set_entry` and `add_entry` both hold a cache already and pass their own.

## 4 What is refused, and what is reported

Part 14's §4.6 table stands. Its raster row is the one this part delivers:

| The reader asks for | `ddd check` on the result | The interface |
| --- | --- | --- |
| an `event` another raster claims | `error[duplicate-event]`, the file loads | **refuses** |

This is the refuse/report line applied, not an exception to it: the interface refuses what it can see
is wrong and the reader can trivially avoid. `duplicate-event` is a check rather than a schema error —
the format permits two rasters on one event — so the file would load and the project would be wrong in
a way only the analysis names. The interface can see it coming, and the reader can pick another
channel.

`duplicate-raster` and `unknown-raster` behave as their section equivalents do, which part 14 settled.

## 5 The screens

A raster's panel is a section's panel with different fields: `event` a number, `cycle` text, both
judged by their own model's rules, and its uses listing every definition naming it **and every
component naming it as a default**. The table gains raster rows and its title a third word, both
through code that already takes a vocabulary. The add form's chooser gains a third entry.

Nothing in `gui/src/components` or `gui/src/screens` may learn what a raster is: those files are
`.tsx`, which no gate in this repository executes, and part 14 shipped four defects there that every
gate passed. Decisions live in `gui/src/lib` behind the Vitest gate.

## 6 Out of scope

- **Go to definition**, per §2.
- **The project's `includes` and new files**, which are milestone 6's remaining items after this.
- **Extracting `Offer`.** Three panels declare it identically and two carry written arguments against
  sharing it. A fourth copy arrives with this part, which is the count the review that raised it asked
  to revisit at — so this part may extract it, having four shapes to read, or record why not.

## 7 Testing

Part 14's gates exactly: Python at 100 % line and branch with `ruff` and bare `mypy` clean; Vitest at
100 % over `src/api`, `src/lib` and `src/state`; the screenshot references; the journeys; the docs
under `-W`. Two practices from part 14 earned their place and carry over:

- **Ablate each new descriptor value and confirm a named test dies.** Four of `SECTIONS`' values
  shipped pinned by nothing, because every line that reads them is covered through `CONSTANTS`. A
  coverage gate cannot see data.
- **A survival under ablation deserves a second seed.** Python randomises string hashing per process,
  which made one reviewer's conclusion on part 14 a coin toss. A death proves the point; a survival
  does not.

## 8 Documentation

The `ddd gui` row of `docs/command_line_interface.rst` gains rasters beside constants and sections,
in the register of the rows around it: what it does, what it refuses, the reason where a reader would
otherwise ask. `docs/editor_integration.rst`'s Rename paragraph gains a raster beside the section,
including that none of the c identifier refusals it lists applies to either.

## 9 Evidence

Measured on this checkout rather than assumed:

- `RasterDeclaration.event` is `Field(strict=True, ge=0, le=EVENT_MAX)` and `raster` is a
  `RasterName`; `cycle` is `str | None = None` and `description` is `str = ""`, so `event` is the
  only key the model requires. `RastersFile.rasters` carries the same `Field(min_length=1)` that
  makes a removal refusable.
- `duplicate-event` is raised in `analysis.py` by scanning `workspace.rasters` for a repeated event,
  filed at the second with a note at the first.
- `Index.rasters` and `Index.raster_uses` are populated by `index()` today, and `_RASTER_KEY` already
  matches both `component.raster` and a definition's own.
- `rename_problem(built, "10ms", "raster")` answers *"'10ms' is not a usable c identifier"* today.
- `_judged` takes no `Index`; `name_judge` does.
