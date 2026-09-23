# Adding and removing declarations

`ddd gui` can repair almost anything a project gets wrong. It settles what a variable's
declarations disagree about (#52), maintains the vocabulary (#51), stamps a missing id (#53),
puts any change back (#55) and changes what a type fixes (#56). It cannot create a variable, and
it cannot take one away. Every project the interface has ever shown was written somewhere else
first.

This adds the verb. It is part 7 of the GUI's growth by field, and the rest of the original
design's milestone 4 - the component editor, whose other half, the key chooser, part 3 built.

## 1 What this adds

Three verbs on a component's interface, all in the panels beside its table. No new screen, no new
pattern, no new route.

1. **Read an object the project already has.** Choose a variable another component declares,
   choose a scope, and the declaration is written **carrying the producer's own keys** - its
   kind, datatype, unit, conversion, limits. That is the point of doing it here rather than by
   hand: a reader added this way agrees with its producer by construction, so the project is no
   less consistent after the edit than before it. It needs no name, no identity and no per-kind
   form.
2. **Declare a new object.** A name, one of the six kinds, a scope, and the keys that kind
   requires - measured, not assumed: `kind`, `name` and `volatile` for every kind, plus
   `dimensions` for a value block, `size` for an axis, `axis` for a curve, and `x_axis` and
   `y_axis` for a map. A declaration whose scope is `output` is stamped with an id, because
   `ddd.identity` already says only a producing declaration is.
3. **Remove a declaration**, with the panel naming first who is left reading the variable.

## 2 Decisions already taken

- **A new name is checked by the rules a rename already uses.** `rename_problem`
  (`src/ddd/lsp/navigation.py:662`) refuses a name that is not a usable c identifier, one c or a
  generated header reserves, one spelling a base datatype, one the project already declares and
  one `Index.occupied` records. A new declaration lands in that same namespace, so it is refused
  in the same words rather than in a second set derived here.
- **The form is the chooser the page already has.** `definition_keys(kind)`
  (`src/ddd/models/objects.py:877`) answers which keys a kind accepts and which it must state,
  from the kind alone. `offer_for(built, key, raw, required=...)`
  (`src/ddd/variable_keys.py:129`) turns one key into a `KeyOffer`. Part 6 added that function so
  that one chooser could draw both a variable's keys and a type's; a new declaration's form is
  the same thing with no value yet. That includes the `editor: "name"` case, which already
  offers a curve's `axis` and a map's `x_axis` from the project's objects of the right kind, and
  the `size` case, a combobox of the project's constants that also takes any whole number typed
  (`gui/src/lib/variableKeys.ts:358`).
- **`dimensions` is that `size` field repeated.** A value block requires it, and `EDITORS`
  (`src/ddd/variable_keys.py:54`) spells it `none` - so the form states it with one `size` row
  per dimension, added and removed by the reader, because a `Dimension` is exactly what a `size`
  is: a whole number of at least 1, or the name of a constant the project declares
  (`src/ddd/models/objects.py:685`). The two treatments do not contradict each other. `none` is
  there because settling `dimensions` across several declarations that already state it is the
  hazardous act; stating a required key once, on a declaration that does not exist yet, settles
  nothing.
- **Both verbs are operations the edit engine already has.** A declaration is `insert` at
  `component.interface[N]` with `N` the list's current length, which appends
  (`src/ddd/editing.py:283`); a removal is `remove` at its index, and `removal`
  (`src/ddd/editing.py:297`) already handles the comma of a last or an only entry.
- **Declaring a producer does not offer to add its consumers.** Declare it here, then open the
  other component and read it. One verb per action, and the second verb is the first one on this
  list.
- **Removal writes, and the checks report.** The panel says what will be left behind, but the
  edit is applied - a unit outside the vocabulary already works that way. Undo is one press.
- **The scope menu offers only what would not be a finding on sight.** `input` always; `output`
  only when nothing produces the name yet, so the menu cannot manufacture `multiple-producers` -
  and when something is missing a producer, this is the repair; `local` only for a name nothing
  else declares, because `local-conflict` is exactly a local beside another declaration
  (`src/ddd/analysis.py:2815`).

## 3 Out of scope

- **Duplicating and reordering declarations.** Milestone 4's other two verbs. Nobody has asked
  for them, and a project's interface order is the author's, not the interface's.
- **Creating a component, or a file.** A declaration goes into a component that exists.
- **Stating a `conversion` from the form.** `EDITORS` spells it `none` - four kinds of conversion
  are a second loader's worth of form, and a text editor writes them better than a panel would.
  No kind requires one, so a new declaration is complete without it, and part 3's chooser is
  where a reader already knows to add one afterwards.
- **Any change to `ddd check`, the language server or the generators.** This writes the same
  files a person writes by hand.

## 4 The server

### 4.1 What is already there

Nothing of part 7's reading side has to be built. The component page has `GET /api/file`, which
answers the file parsed with the fingerprint it was read at. The variable's panel has
`GET /api/variable`, whose `VariableReply.declarations` carry each declaration's `component` and
its `role` (`src/ddd/gui/contract.py:448`) - which is everything a removal's warning needs.

### 4.2 What the panel reads

`GET /api/declarable?file=` answers what this component may add:

- every variable the project declares that this file does not - its name, its kind, and the
  component that produces it;
- per kind, the keys it accepts and the keys it must state, each as a `KeyOffer` with no value
  in play.

One endpoint rather than two, because the form needs both halves at once and asks for them once,
when the panel opens.

### 4.3 What each verb takes

`GET /api/declaration-plan?action=read|declare|remove&file=...` answers a `PlanReply`
(`src/ddd/gui/contract.py:768`), previewed and applied through `POST /api/edit` exactly as the
units and the types are.

- `read` takes `name=` and `scope=`. The server reads the producer's own definition, so nothing
  else is passed.
- `remove` takes `name=`.
- `declare` takes `scope=` and **`definition=`, the whole definition as one json parameter.**

That last one is the only new shape here, and it is what keeps the plan a `GET` and `/api/edit`
the one thing that writes. The panel is already composing a json object key by key; it sends the
object rather than spreading six keys, two of which are json themselves, across a query string.
The server validates it against the models before planning anything.

`id` is minted with `new_id()` (`src/ddd/identity.py:77`) when the plan is made, so the preview
shows the id that will be written. The plan is therefore not idempotent - asked twice it proposes
two ids - which is the rule `identity.insertions` already states in so many words: the caller
applies the answer it was given rather than asking again. The alternative, leaving the id out and
letting `missing-id` report it afterwards, hands the reader a finding for an action they have
just completed.

### 4.4 The module

`src/ddd/declaration_plans.py`, shaped like `src/ddd/type_plans.py`: a `DeclarationPlan` of
edits, a `RefusalError` carrying a code, and one function per verb. There is no companion
reading module, because 4.1 is why there does not need to be.

### 4.5 What is refused

- `invalid`: a name `rename_problem` refuses, reported in its sentence; a kind outside the six; a
  scope outside `input`, `output` and `local`; a key the kind does not have; a required key left
  out; a variable this component already declares; a scope section 2's rule does not offer
  for that name.
- `not-found`: a file that is not a component of this project, or a name nothing declares.
- `unreadable`: a file did not load, so there is no index to plan against - the answer
  `/api/type-plan` already gives.
- `stale` and `unwritable` arrive from the edit engine, as they do today.

## 5 The screens

### 5.1 Adding, from the component page

One control above the table opens a panel in the slot beside it - the slot the variable's panel
uses. The panel is page state, not an address. `Route` gains nothing: `?variable=X` names
something that exists and is worth reloading into, and a half-filled form for a thing that does
not exist yet has no name to put in an address. The adoption preview on the Units tab already
opens this way.

### 5.2 One name field, not two verbs

The panel's first field offers the variables the project declares that this component does not,
and takes a name that matches none - the idiom part 1 taught with units, which the journeys word
as "a unit typed and confirmed with Enter is the unit chosen, listed or not".

- **A listed name** means reading it. The form asks for a scope and nothing else, because the
  keys come from the producer.
- **A name the project has never seen** means declaring it. The form grows: the six kinds, then
  that kind's keys, each drawn by `KeyChooser` - and, for a value block, the row of `size` fields
  section 2 describes.

Then the consequence sentence, Show changes and Apply, as every panel of this interface has.

**The hazard, stated rather than hidden.** A typo of an existing name silently becomes a new
object instead of a read. Nothing can catch it - the name is new, so no rule fires. What stands
against it is the consequence sentence naming which of the two this is ("Reads ValueA as
SensorHub declares it" against "Declares ValueA, a new measurement") and the preview showing the
json before anything is written. The unit picker carries the same property, and the project has
lived with it since part 1.

### 5.3 Removal, in the variable's panel

One more `<section className="panel-offer" aria-label="Remove the declaration">`, the shape
`UnitPanelView` already uses four times over (`gui/src/components/UnitPanelView.tsx:126`, `:140`,
`:145`, `:149`), each with its own consequence sentence, Show changes and Apply. The warning -
"Controller and UserInterface read ValueA" - is written from `VariableReply.declarations`, which
is already on screen.

Part 6's task 9 is the thing to watch: two write paths in one panel, each able to be dirty at
once. A success in one clears what the other holds.

### 5.4 What the reader sees when something goes wrong

Refusals render where the unit and type panels already render theirs - the `panel-refusal`
paragraph with `role="status"`. A stale refusal is held by `shownRefusal` until the analysis
moves past the revision it was refused at, so choosing again works rather than being refused
twice.

A removal that takes the last declaration of a variable closes its own panel: the variable panel
already has that path - `onUndeclared` fires when no file declares the name any more, and the
component page names it above the table until another row is chosen. Removing the only
declaration is that path arriving on purpose instead of by surprise.

**One gap stated rather than closed.** A name is checked against the project when the plan is
made, and `POST /api/edit` verifies fingerprints per file and nothing else. If another editor
declares the same name in a *different* file between preview and Apply, this file's fingerprint
is unchanged, the write goes through, and the duplicate becomes a finding on the next check. That
window is not new: a rename has had exactly the same one since part 6, for the same reason.
Closing it would mean the edit endpoint re-deriving project-wide invariants it has never derived,
to catch a race between two people editing one project by hand. The checks report it, part 4
leads to it, undo takes it back.

## 6 Stories and screenshot tests

Ladle stories for `DeclarePanelView` - a name not yet chosen, a listed name chosen, a new name
with a measurement's keys, a new name with a curve's keys and its object references, a value
block's dimensions row, and a refusal - and for the removal offer, with and without readers left
behind. A story imports nothing from `@ladle/react`. Screenshots are written and taken in
`mcr.microsoft.com/playwright:v1.63.0-noble`, through `docker compose run --rm gui-screenshots`.

## 7 Testing

- **Python**, at the 100 % line-and-branch gate, no `pragma: no cover` and no skips:
  `tests/test_declaration_plans.py` for the three verbs and every refusal of 4.5; the two new
  endpoints added to `TestEveryEndpointOnTheDemo` in `tests/test_gui_server.py`, which drives
  them through real HTTP on a copy of `examples/demo`; and the contract test that fails the build
  for a model no endpoint reaches.
- **The page**: `gui/src/lib/declarations.ts` holds what is testable without a browser - which
  keys a kind asks for, which scopes a name may take, the json a row of `size` fields makes, and
  the consequence sentence that tells reading from declaring - under Vitest at 100 % over
  `src/lib`. No Vitest for a component or a
  screen, as the house rule has it.
- **Journeys**, `gui/e2e/declarations.spec.ts`: read a variable another component produces and
  see the producer's keys arrive with it; declare a new measurement; declare a **curve**, which
  is what exercises the object-reference chooser; declare a **value block**, which is what
  exercises the dimensions row; remove a declaration and undo it; and a name the project refuses,
  in `rename_problem`'s own words. `examples/demo` already declares a curve,
  a map, an axis and a value block, so no new example is needed. The content-security-policy
  journey gains the new panel, as every part has added its screen to that walk.

## 8 Documentation and where it lands

- New: `src/ddd/declaration_plans.py`, `gui/src/lib/declarations.ts`,
  `gui/src/components/DeclarePanelView.tsx` and its story.
- Extended: `src/ddd/gui/contract.py` and `src/ddd/gui/api.py`; `gui/src/api/types.ts`, whose
  export list is sorted case-insensitively; `gui/src/screens/ComponentPage.tsx` and
  `gui/src/components/VariablePanelView.tsx`.
- Unchanged: `gui/src/lib/route.ts`; `ddd check`, the language server and the generators.
- The GUI's page in `docs/` gains the verb, and `ddd gui` stays labelled preview.
- The branch is `feature/gui-declarations`, off `master` at the merge of #56.

## 9 Evidence

- `src/ddd/models/objects.py:877`: `definition_keys`, which answers a kind's accepted and
  required keys from the kind alone - derived from the pydantic variants, so a key added to a
  model is covered the moment it exists.
- `src/ddd/models/component.py:16`: `Scope`, whose three values are `input`, `output` and
  `local`; and `:112`, `Component.interface`, required with no default, so a loaded component
  always has the array a declaration is inserted into.
- `src/ddd/variable_keys.py:129`: `offer_for`, added in part 6 so one chooser could draw a
  variable's keys and a type's; `:29` `KEY_ORDER`; and `:54` `EDITORS`, which spells `axis`,
  `x_axis`, `y_axis` and `input` as `name`, `size` as `size`, and `conversion` and `dimensions`
  as `none`.
- `definition_keys` run against all six kinds rather than read from the models: `value_block`
  requires `dimensions`, `axis` requires `size`, `curve` requires `axis`, `map` requires `x_axis`
  and `y_axis`, and every kind requires `kind`, `name` and `volatile`.
- `src/ddd/lsp/navigation.py:662`: `rename_problem`, whose five refusals this reuses rather than
  re-deriving.
- `src/ddd/editing.py:283` and `:297`: `insertion`, which appends when the index is the list's
  length, and `removal`, which leaves no comma trailing.
- `src/ddd/identity.py:77`: `new_id`, and `:138` `insertions`, which states in its docstring why
  a caller applies the answer it was given rather than asking again.
- `src/ddd/analysis.py:2815`, `:2825`, `:2834`: `local-conflict`, `multiple-producers` and
  `missing-producer` - the three findings the scope menu is shaped around.
- `src/ddd/gui/contract.py:448`: `VariableDeclaration`, carrying `component` and `role`, which is
  why a removal's warning needs no new server field; and `:768` `PlanReply`, reused as it stands.
- `src/ddd/gui/api.py:622`: `_type_plan`, the endpoint this one is shaped after, refusals and
  `previewed` included.
- `gui/src/components/UnitPanelView.tsx:126`: the `panel-offer` section, four to a panel.
- `examples/demo`: declares `axis`, `curve`, `map`, `value_block`, `measurement` and `parameter` -
  every kind the form offers except the ones it shares with `parameter`.
