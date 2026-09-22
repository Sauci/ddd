# Undo in the GUI

`ddd gui` writes description files from four places now - a key settled on every declaration of a
variable, a unit renamed, described, added, removed or adopted across a project, an identity given
to a declaration that had none, and the project description that an adoption includes a new file in
- and every one of those parts deferred undo. The only way back from a change applied by mistake is
git, which a reader who would rather not edit JSON is not obviously reaching for either.

This gives the interface an undo: one stack per open project, in the server that did the writing,
walked back one edit at a time, previewed before anything is put back. It is part 5 of the GUI's
growth by field, after units (#49), the project's units (#51), the other keys (#52) and the
findings (#53).

## 1 What this adds

1. **A stack of what was replaced**, in the session: every edit the interface applies remembers each
   file's previous bytes - or that the file did not exist - and the fingerprint the edit left it at,
   beside a sentence naming what was done.
2. **`POST /api/edit` carries that sentence**, written by the screen that applies: *the unit of
   ValueA*, *the rename of 'rpm' to 'RPM'*, *the identity of ValueA*, *the vocabulary adopted*. A
   noun phrase, so that a control can read "Undo the unit of ValueA".
3. **`GET /api/state` says whether there is anything to undo**, and what, so the control appears
   from the answer the page already polls.
4. **`GET /api/undo` previews the top of the stack** and **`POST /api/undo` puts it back**, in the
   shapes the other previews and writes already use.
5. **An Undo button beside the project's name**, on every screen where a project is open: pressing
   it shows the files and the lines it would put back, pressing again writes them.
6. **Nothing is left in the reader's tree.** The stack is the running server's memory of what it
   wrote; stopping `ddd gui` ends it.

## 2 Decisions already taken

- **A stack, not a single step.** Undo walks back one edit at a time for as long as the server
  runs, because that is what the word promises and because the fingerprints make each step as safe
  as the last.
- **The bytes, not the inverse operations.** `apply_changes` already computes each file's previous
  bytes on its way through; keeping them makes an undo exact - the file returns to what its author
  wrote, whatever the edit did to its layout - and needs no special reasoning for a key that did not
  exist, a container the engine re-laid-out, or a file the edit created.
- **The page says what each edit was.** The server knows which files it wrote and where; only the
  screen knows that it was "the rename of 'rpm' to 'RPM'". A control that cannot say what it would
  undo is a lever in the dark.
- **An undo is previewed like every other write.** Nothing in this interface is written without the
  reader seeing the lines first, and it matters more here than elsewhere: there is no redo, so an
  undo pressed by accident cannot be taken back.
- **A refused undo keeps its place.** An entry whose file has changed since is not dropped: the
  reader may put that file back and try again, and dropping it silently would be the tool deciding
  their change is unrecoverable.
- **The stack is capped at fifty edits**, the oldest falling off, so a long session does not grow
  without bound.

## 3 Out of scope

- **Redo.** Undo is previewed, which is the guard against an accidental press; a second stack and
  what it would mean once the files have moved on can wait for somebody to want it.
- Undoing anything but a whole edit: an edit is written all-or-nothing and is undone the same way.
- Surviving a restart. The stack dies with the server rather than leaving copies in the project.
- A history of what was applied, beyond the one entry the control names.

## 4 The server

### 4.1 What the session keeps

`Session.edit` applies every edit the interface makes, under a lock, and re-analyses. It gains a
stack beside the revision:

| Field | What it holds |
| --- | --- |
| `at` | a number the session counts up as it pushes, which an undo names |
| `label` | the sentence the page sent, shown by the control |
| `files` | one entry per file the edit wrote |

and each file entry holds its path, the bytes it had before the edit - `None` for a file the edit
created - and the fingerprint the edit left it at, which is what says whether it may still be put
back.

`apply_changes` already computes exactly those bytes: it stages `(change, original, new)` per file
before writing anything, and answers the new fingerprints. It answers the previous bytes with them
now. Its one caller is `Session.edit`.

### 4.2 Putting the bytes back

`ddd.editing` gains `restore`, a sibling of `apply_changes` sharing its staging: every file checked
against the fingerprint the edit left it at before anything is written, each previous version
written through the same stage-and-rename that keeps a file's access, a file the edit created
removed again, and the same rollback when one of several files cannot be written - those already
put back are written forward again, and the refusal names any that could not be.

Its refusals are the ones the interface already says: `stale` for a file that has changed since,
`unwritable` for one that cannot be written, `unreadable` for one that cannot be read.

### 4.3 The endpoints

- **`GET /api/state`** gains `undoable`: the `at` and the label of the top of the stack, or nothing
  when it is empty. It costs one string on an answer the page already polls, and it is what makes the control
  appear and disappear without a request of its own.
- **`GET /api/undo`** answers `{revision, at, label, changes}`, where each change names a file and
  carries the lines it would get back. It does **not** carry operations, and the page does not send
  them back: an undo is bytes the server is holding, not an edit the page composes, which is the one
  place this differs from every other preview in the interface. Nothing is written.
- **`POST /api/undo`** takes `{at}` - the entry the preview was made from, which the session numbers
  as it pushes - puts that entry back, re-analyses and publishes as an edit does, and pops it. The
  number is what stops a second window undoing something else in between and this one putting back a
  change its reader never saw: an `at` that is no longer the top is refused as `stale`, and the page
  asks again.
- **`POST /api/edit`** gains `label`, a sentence of at most 120 characters, required. Every screen
  that writes supplies it.

An undo that is refused leaves the stack as it was, and the refusal names the file.

## 5 The screens

### 5.1 The control

Beside the project's name, in the heading the project screen and a component's page already draw:
absent while the stack is empty, and otherwise a button reading **Undo the unit of ValueA** - the
label the edit was applied with.

### 5.2 Pressing it

The button expands a strip below the heading, built from what every other write already uses:

- part 1's consequence line - *Puts back 2 files: controller.ddd.json, sensor_hub.ddd.json*;
- **Show changes**, printing the lines each file would get back;
- a second press, which writes.

Afterwards the analysis re-runs as it does after any edit, every screen updates itself, and the
button offers the edit before that one or goes away.

### 5.3 What the reader sees when something goes wrong

- **A file changed since the edit**: the strip names it and offers nothing. Putting the old bytes
  back would throw away what the reader wrote in their own editor, and the entry stays on the stack
  so they may put the file back and try again.
- **A file cannot be written**: the engine's own sentence, and the stack unchanged.
- **The server stopped**: milestone 1's banner, and no write.
- **The stack is empty**: no button.

## 6 Stories and screenshot tests

One story per state, photographed in Playwright's Linux image as parts 1 to 4 are: the button alone;
the strip open with its consequence line; the strip with its changes shown; and the strip refusing,
naming the file that changed.

## 7 Testing

- **Python**, under the 100 % line and branch gate, ruff and strict mypy:
  - `restore`: a file put back exactly, a created file removed again, a file that changed since
    refused before anything is written, the rollback when the second file of an edit cannot be
    written, and a restored file keeping its access;
  - the session's stack: pushed by an edit, popped by an undo, capped at fifty with the oldest
    falling off, and a refused undo leaving it as it was;
  - the endpoints over copies of `examples/demo` and `examples/vocabulary`, including the two that
    exercise the bytes properly - undoing an adoption, which removes the units file it created *and*
    restores the project description that included it in one write, and undoing a settle, which puts
    a container the engine re-laid-out back exactly as its author wrote it;
  - every refusal, and every `400`, `404` and `409`.
- **The page's logic** under Vitest's 100 % gate: when the button shows, what it says, and the edit
  a preview comes to.
- **End to end**, in Chromium on Windows and Linux: settle a key, undo it, and read the file back;
  adopt a vocabulary, undo it, and find the file gone again; an undo refused because a file was
  changed by hand; and the Content-Security-Policy journey with the strip open.
- **The gate** as parts 1 to 4 ran it, the real application included, with screenshots for the pull
  request.

## 8 Documentation and where it lands

- The changelog and the command page say that a change applied in the interface can be undone, one
  at a time, while the server runs. The developer page describes the stack, `restore`, and the two
  endpoints. `docs/editor_integration.rst` needs nothing: the language server is untouched.
- On `feature/gui-undo`, from master after #54.

## 9 Evidence

- `src/ddd/editing.py`: `apply_changes`, which stages `(change, original, new)` per file and answers
  the new fingerprints - the previous bytes an undo needs are already in its hand; `_stage_and_replace`
  and `_keep_access`, which `restore` shares; `FileChange`, whose `fingerprint` is `None` for a file
  a change creates.
- `src/ddd/gui/session.py`: `Session.edit`, the one caller of `apply_changes`, which holds the lock,
  writes, re-analyses and publishes - where the stack is pushed; `SourceFile.fingerprint`, the same
  hash `restore` checks against.
- `src/ddd/variables.py`: `hunks(before, after)`, which turns two texts into the lines a preview
  shows.
- `src/ddd/gui/contract.py`: `Changes`, which gains the label; `State`, which gains `undoable`;
  `PlanReply` and `FixReply`, the shape `GET /api/undo` follows.
- `gui/src/app/App.tsx` and `gui/src/screens/ComponentPage.tsx`: the two headings the button joins.
- `gui/src/components/Changes.tsx`: Show changes, drawn from the same hunks.
