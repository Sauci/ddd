# Fixing a disagreement from its finding

- **Part:** 11 of the GUI work, the first half of milestone 7
- **Status:** design approved; to be planned
- **Builds on:** the findings tab, shipped as part 4
  ([`2026-09-22-gui-findings-design.md`](2026-09-22-gui-findings-design.md)), and the settlement
  `ddd gui` already offers from a variable's panel

## 1 Why

Ten parts have each added a way to change something, and part 10 added a way to see. The
findings tab has told a reader what is wrong since part 4, and takes them to the exact
field. Then it stops.

`definition-mismatch` is the finding that earns this the most. It is the tool's own subject -
two components describing one variable differently - and today pressing it opens the variable's
panel, where the reader settles the key themselves. The tool has diagnosed the problem, named
the two declarations, worked out which keys disagree, and then asked the reader to do it.

**The editor already does not.** `ddd.lsp.edits` is 783 lines that offer exactly this fix as a
quick fix, with a rule stated in its own comment: *"A consumer is offered the producer's value
first; the producer is offered its own, outward. Which side owns the variable is not a matter of
taste here - it is the rule the whole tool is built on."* An engineer with an editor gets the fix;
an engineer with the page gets a link.

This part brings the same fix to the page. Not a second implementation of it - the same
decisions, spelled differently.

## 2 What it is not

- **Not a new policy.** The direction a fix flows is the rule `ddd.lsp.edits._from_producer`
  already states and `PRODUCER_KEYS` already encodes. This part restates nothing and invents
  nothing.
- **Not the editor's whole catalogue.** The editor offers up to two actions per key - somebody
  else's answer brought here, and this one's answer sent out. The page offers the **first of that
  ordered pair only** (section 3). The second is available in the editor for a reader who means
  it, and from the variable's panel, which settles any value the reader picks.
- **Not the other checks.** `unknown-unit` and its family, the `PRODUCER_KEYS` removals and the
  rest keep their empty tuple. Each is a part of its own; this one is chosen first because the
  refactor it pays for is what the others will build on.
- **No page change.** `FindingPanelView` already draws every fix a finding carries as its own
  button with a preview and an `Apply to N files`. This part adds fixes, not a place to put them.

## 3 What a reader sees

**One button per key that disagrees**, beside the link the panel already has.

> `Use the datatype declared in controller`   `Use the unit declared in controller`

Pressing one reveals what the panel already draws for `missing-id`: the consequence sentence,
`Show changes`, and `Apply to N files`. The file stem names the owner, which is also what the
panel's own meta line shows for a finding.

**The direction is never the reader's problem.** On a consumer's finding the button takes the
producing component's value; on the producer's own finding it sends that value out. One button
per key either way, and the reader never chooses a direction, because the tool already knows
which component owns the variable.

**The reach is the whole variable.** `settle` makes every declaration of the object state the
value, so one press clears the finding on every file that carried it rather than leaving its
siblings behind. That is also what the variable's panel already means by settling a key: the page
keeps one meaning for the word.

## 4 One decision, two spellings

The five action builders of `ddd.lsp.edits` - `_from_producer`, `_adopt`, `_remove_here`,
`_propagate`, `_remove_elsewhere` - stop returning protocol dictionaries and return a decision:

```python
@dataclass(frozen=True, slots=True)
class Reconciliation:
    title: str
    key: str
    settlement: Settlement   # changes: tuple[Settled, ...], unsettled: tuple[Unsettled, ...]
```

`Settled(site, raw)` is the vocabulary the rest of the tool already speaks, and both clients
spell it:

- The **editor** spells each `Settled` as a `TextEdit`. `_assign`, `_insert` and `_erase` keep
  the hard parts, which are genuinely about text: a value copied verbatim so it arrives looking
  the way its author wrote it, a new member taking the indentation of the one above, and a
  removal taking exactly one comma with it.
- The **page** spells the same tuple through `variables.preview()`, which already turns
  `Settled` into `Operation("set")` or `Operation("remove")` across files. The edit engine adds
  a missing member itself - `set` "writes `raw` at `pointer`, adding the member when its object
  lacks it" - so none of the editor's text machinery is needed twice.

**Three refusals move with the decision, because they are decisions.** `_assign` declines a key
the declaration's kind does not accept, declines a meaning key a named type fixes, and declines
a value that already means what is there; its own comment says these are "the same question
`settle` asks of every declaration it reaches, asked through the same function". `_erase`
declines an only child, "a decision about what a quick fix offers". Left in the spelling layer,
the page would offer fixes the editor refuses.

`fixes_for` gains one parameter, the `Index`, which `Api._fix` already holds beside it as
`revision.index`. The `Finding` contract does not change: the keys that disagree are worked out
from the files as they stand now rather than read off an analysis that may have moved on, which
is what `fixes_for` exists to do.

## 5 Which keys, and what is not offered

The candidates are the propagatable keys this declaration states, plus the ones the other
declarations state and it lacks, less `limits`.

- **`limits` defers.** A declaration that leaves them out is agreeing with whoever states them,
  so spreading a range into it, or stripping the one range anybody stated, would be a fix on a
  declaration the checker calls clean.
- **`kind` is never offered.** `definition-mismatch` compares it, but it is absent from
  `PROPAGATED_KEYS` for a reason the index states: "declarations disagreeing about their kind are
  two objects under one name - which `definition-mismatch` reports and no chooser can settle". A
  mismatch differing only in `kind` gets no button, and the finding still says what is wrong.
- **No producer, or several: nothing is offered.** `_from_producer` already declines there -
  "which is its own finding, and not one to guess through" - and both situations carry an error
  of their own. Measured: `examples/inconsistent` is exactly this case. `SharedValue` is written
  by `ComponentA` **and** `ComponentB`, so its `definition-mismatch` against `ComponentC` -
  `datatype: uint16 != sint16, conversion: identity != linear(factor=0.5, offset=0)` - offers
  **no fix at all**. The repository's own inconsistent example is the one that gets nothing.
- **A settlement that cannot complete is not offered either.** The page refuses partial
  settlements, because its reader chose a value for the variable and a change reaching only some
  of its declarations is not the one they chose; the editor offers the reachable part. This part
  does not erase that difference - it is deliberate and `settle`'s own docstring says so - so the
  decision carries `unsettled` as well as `changes` and each client applies its own policy.
  Rather than a button that always refuses, the page shows none: "a fix that does nothing teaches
  a reader to stop reading the lightbulb" is the editor's rule, and it binds a button harder than
  a lightbulb. The reader who wants the reason follows the link the panel already has, where the
  variable's panel gives the refusal in full.

## 6 Where it lives

- `src/ddd/lsp/edits.py`: the five builders return `Reconciliation`; a thin layer spells them as
  protocol actions. The module keeps its text machinery and loses its monopoly on the decisions.
- `src/ddd/finding_fixes.py`: `definition-mismatch` joins `missing-id`. `Fix` grows from one file
  to the settlement's own files.
- `src/ddd/gui/api.py`: `_fix` passes `revision.index` and previews a multi-file fix. The reply
  shape is unchanged - `FixReply.fixes` is already a tuple and `FixOffered.changes` already a
  list of files.
- **No TypeScript.** `FindingPanelView` draws this today.

## 7 Testing

- **The extraction lands first, on its own, with the editor's answers proved byte-identical.**
  `actions()` captured over the example projects before and after and diffed, on top of the 332
  tests of `tests/test_lsp.py`, 25 places in which assert the action titles. If the refactor is
  wrong, it is wrong in a commit that changed nothing else.
- **Python at 100 % of lines and branches** over the decision layer and `finding_fixes.py`. A
  conditional expression registers no branch at all with coverage.py, which cost part 9 five
  defects: where an arm needs a test, write a statement or early returns.
- `tests/test_finding_fixes.py:72` asserts `fixes_for("definition-mismatch", …) == ()` today.
  That test inverts, which is the marker that the behaviour really changed.
- **Stories and screenshots** on `FindingPanelView`: a mismatch offering two keys, and one
  offering none.
- **One journey**, over a copy of `examples/demo`. `ValueE` is the fixture: written by
  `Controller`, read by `UserInterface` and `EventLogger`, `uint16` in `Hz`. Plant a wrong unit
  in one consumer and the fix changes one file; plant it in both and it changes two, which is
  what proves the preview's count is the settlement's and not the finding's.
- **No Vitest test for a component or a screen**, as since part 1.
- No existing screenshot reference may change: this part adds stories and touches no drawn
  component.
