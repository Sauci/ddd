# Web GUI

- **Date:** 2026-09-17
- **Status:** design approved; milestone 1 to be planned
- **Touches:** a new `ddd gui` command and `ddd.gui` package, a new edit engine shared with the
  language server and `ddd id`, a new `gui/` frontend project, the CI and publish workflows,
  packaging, the documentation

## 1 What this adds

Most of the developers who declare variables in DDD work in Simulink. Writing `*.ddd.json` by
hand, and reading the checks in an IDE, is exactly the part of the tool they are least at ease
with. This design adds a browser GUI for them: `ddd gui` starts a small web server on the
developer's own PC, opens the browser on it, and lets them read and change a project's
description files through screens instead of JSON.

The GUI is one more editor of the same files. It holds no data of its own: every change is
written into the `*.ddd.json` files, in their own layout, and checked by the same loader and
analysis as `ddd check` and the build. Somebody editing the same files in VS Code, a `git
checkout` switching them underneath, and CMake reading them are all unaffected.

The cost of this was estimated before any design work, in a page shared on 2026-09-16
(https://claude.ai/artifact/HT1HxkAp8Cg2rAqbYb7EL6). That estimate is the source of the
milestone split and the figures in section 5.

## 2 Decisions already taken

These were settled while scoping the estimate and are not reopened here.

- **Local, not hosted.** The server runs on each developer's PC, from the installed package,
  and listens only there. A hosted service would add hosting, company sign-in, concurrent
  editing of one repository and an IT approval, several times the cost; a page that runs DDD
  inside the browser through WebAssembly would need no installation but depends on browser
  file access and an unverified toolchain. Every PC therefore needs Python 3.12 or newer and
  `ddd-tool`.
- **Hand-designed screens.** Forms generated from the JSON schemas were rejected: the schemas
  mark every optional key as "a value or null", which renders as nested technical forms - the
  JSON the GUI exists to hide. A custom editor inside VS Code was rejected because VS Code is
  the barrier being removed.
- **The same engine.** The checks are never reimplemented in JavaScript. The server calls the
  existing loader, analysis, comparison, rename and quick fixes, so the GUI cannot disagree with
  the build.
- **Edits change only the lines they touch.** A GUI user and a VS Code user share files, and a
  review of a GUI change reads like a review of a hand edit.
- **The variables are declared only in DDD.** Simulink models do not hold a second copy as
  Simulink.Signal or Simulink.Parameter objects, so there is no import from Simulink.
- **The first version is complete.** Beside editing a component and reading the findings, it
  has the curve, map and axis tables, the shared project files, one-click fixes and rename, and
  the comparison of deliveries.
- **Delivered in milestones, merged as they land.** Each milestone merges to master through
  its own pull request, with `ddd gui` labelled *preview* until the last one. Master stays
  releasable, and a release in between ships a GUI that works for what it has and says it is
  unfinished. A branch held open until the end was rejected: the file format keeps moving on
  master, and every week of divergence is merge work.

## 3 Out of scope for the whole GUI

- Hosting, sign-in, several people on one server.
- Git operations. Developers commit with the tool they already use.
- Running `ddd generate`. The build does that.
- An import from Simulink (section 2).
- Translations. The interface is English, like the rest of DDD.
- A packaged executable that needs no Python. It is the fallback if IT cannot install Python on
  the developers' PCs, and would be designed then.

## 4 Architecture

### 4.1 The pieces

```text
On the developer's PC

  Edge or Chrome                ddd gui (Python)
  +-----------------+   JSON    +---------------------------------------+
  | the GUI         | --------> | server   security, the compiled pages |
  | (React, shipped | <-------- | session  the open project, revisions  |
  |  in the wheel)  |           | api      requests to the code below   |
  +-----------------+           +---------------------------------------+
                                   |                                |
                                   v                                v
                  loader, checks, dictionary, compare,         edit engine
                  rename, fixes (existing code)                     |
                                   |                                |
                                   v                                v
  VS Code (optional) -------> *.ddd.json files in the git checkout
                                   |
                                   v
                          CMake build (unchanged)
```

- **The frontend** (`gui/`) is a React application in TypeScript. It is compiled once, in CI,
  into static files shipped inside the wheel; nothing is fetched from the network at run time.
- **The server** (`src/ddd/gui/`) is Python's standard-library HTTP server, bound to the
  loopback address by default. It serves the compiled pages and a JSON API, and adds no runtime
  dependency to the package: like `ddd lsp`, it runs on what Python already has.
- **The session** holds the one open project and the result of its last analysis, numbered as
  a revision.
- **The edit engine** (`src/ddd/editing.py`) turns an operation at a pointer into a text edit in
  the file's own layout, and verifies it before anything is written.

### 4.2 What is reused

The language server already answers most of what the GUI asks, and the GUI calls the same code
rather than a copy of it:

| Question | Existing code |
| --- | --- |
| Which build records exist, and which are usable | `ddd.lsp.discovery.build_files`, `load_builds` |
| The findings of a project, under its build's severities | `ddd.lsp.diagnostics.analyse`, `_run` |
| Both sides of a disagreement marked, duplicates across images dropped | `ddd.lsp.diagnostics._group`, `_mirrors` |
| Which files of a project did not load | `ddd.lsp.navigation.Loaded` |
| The resolved dictionary | `ddd.analysis.analyze`, `ddd.ir.DataDictionary` |
| Where a pointer is in a file's text | `ddd.lsp.ranges.Document` |
| Rename and its refusals | `ddd.lsp.navigation.rename_edits`, `rename_problem` |
| One-click reconciliation of a mismatch | `ddd.lsp.edits.actions` |
| Comparison of two deliveries | `ddd.compare.compare` |

Where one of these is private today, the milestone that needs it makes it public under a name
that says what it does, and the language server calls it by that name too. The protocol-neutral
parts stay in `ddd.lsp` for now; moving them into a package of their own is a rename for later
(section 8).

Pointers are DDD's own spelling, the one every finding already carries in `Location.pointer`:
`component.interface[3].definition.unit`. The API uses no other.

### 4.3 Trust

Opening a project runs the plugins it names, exactly as `ddd check` and `ddd lsp` do. The GUI
opens only a project the user named on the command line or one found under the directory the
server was started in, so it trusts what the user already trusts by running the tool there.

## 5 Milestones

Each milestone gets its own plan, its own branch and its own pull request. The later ones get a
spec section of their own when they are reached, because what milestone 2 learns from the
usability sessions will shape them.

| # | Delivers | Builds on | Days with Claude, likely |
| --- | --- | --- | --- |
| 1 | Walking skeleton: the command, server, session, edit engine, frontend build, CI, packaging, one path from end to end (section 6) | - | 7 |
| 2 | Design: user journeys, mockups, the visual style and component library, usability sessions with Simulink developers | 1 | 6 |
| 3 | Project home, the variables browser, the findings in plain language with a jump to the field, a raw-text fallback for a file that does not parse | 2 | 5 |
| 4 | The component editor: the six kinds, conversions, choices filled from the project, "read an existing output", derived values, adding, duplicating, removing and reordering declarations, undo | 3 | 6 |
| 5 | Curve, map and axis tables: a grid against the breakpoints, paste from Excel, raw or physical values, plots | 4 | 5 |
| 6 | Shared project files: types and structures, units, sections, constants, rasters, the project's includes, new files | 4 | 3.5 |
| 7 | One-click fixes and rename with a preview of every file changed, and the comparison of deliveries | 3, 4 | 4 |
| 8 | Hardening (large projects, security review, end-to-end breadth), the user guide, an independent review, the pilot, removing *preview* | all | 13.5 |

The days are the estimate's likely case. Milestone 1 replaces the throwaway spike the estimate
recommended: it measures the same thing (section 6.13) and keeps its code.

## 6 Milestone 1: the walking skeleton

### 6.1 What it delivers

A path through every layer, thin enough to build in about a week and real enough to measure:

1. `ddd gui examples/demo/demo.ddd.json` prints the address it serves on and opens the browser
   there.
2. The page shows the project's name, its components, and how many findings each has.
3. Choosing a component shows its declarations as a table - scope, name, kind, datatype or
   type name, unit - and the findings located in it.
4. A declaration's unit can be changed in the table. Confirming writes the file, and the only
   difference in the file is the unit's value. Giving a consumer a unit its producer does not
   have shows `definition-mismatch` on both declarations; putting it back withdraws it.
5. Saving the file from another editor while the page is open updates the page within two
   seconds. An edit made from the page before it updated is refused, and the page reloads the
   file and says so.
6. `ddd gui` with no project lists the projects found under the directory it was started in,
   and opens the one chosen.

Nothing else is editable yet, and the screens are plain: their look is milestone 2's.

### 6.2 The command

```text
ddd gui [PROJECT] [-b DIR]... [--host ADDRESS] [--port N] [--no-browser]
```

- `PROJECT` is a project description. Without it, the start page lists the projects of the build
  records found the way `ddd lsp` finds them, and the project descriptions found under the
  current directory: every `*.ddd.json` whose top-level key is `project`, at most four
  directories deep, skipping hidden directories, `node_modules` and the build directory names
  `ddd lsp` searches.
- `-b DIR` names a build directory, repeatable, exactly as for `ddd lsp`.
- `--host ADDRESS` binds another address than the default, `127.0.0.1` - `0.0.0.0` in a
  container. See 6.3 for what answering beyond loopback changes.
- `--port N` fixes the port. The default, 0, lets the system pick a free one, which is refused
  together with a `--host` beyond loopback: a port a container's own system picks cannot be
  published on the host in advance.
- `--no-browser` prints the address without opening it.

The command prints one line to stdout, `ddd gui (preview) serving <address>`, and, beyond
loopback, one more to stderr warning about it (6.3); it runs until it is interrupted, which
exits 0. It exits 2 when the project is not a project description, when `--host` cannot be
resolved to an address or a fixed port is taken, when `--port 0` is combined with a `--host`
beyond loopback, or when the installation has no compiled pages (section 6.8).

The findings of an open project are those of every build record that names it, merged the way
the language server merges them. With no record naming it, the project is analysed with the
default severities, as the language server analyses a project file nobody configured a build
for.

### 6.3 The server

The server is `http.server.ThreadingHTTPServer`, bound to `127.0.0.1` by default, not
`localhost`, which resolves to an IPv6 address on some machines. `--host` names another address
instead, resolved once with `socket.getaddrinfo` (the server is IPv4 only) before anything else
is decided from it, so a hosts file that redefines `localhost` is judged by what it resolves to
and not by its spelling - in both directions - and the numeric result is what is actually
bound. For a container that address is `0.0.0.0`, with `docker compose` publishing the same
port number on the host's loopback alone, `-p 127.0.0.1:8123:8123`: a different number there
would have the Host header `ddd gui` sees name a port it does not listen on, answered `421
misdirected request`, since the Host check below names this server's own port.

The address the command prints still says `127.0.0.1`, so it pastes into a browser on the host
as is, and the Host and Origin allow-lists below are unchanged - refusing what they always
refused, whatever address is actually bound. Beyond loopback that leaves the token in the
printed address as the only barrier, since a client that merely reaches the port can forge a
`Host` or `Origin` header; `ddd gui` prints one warning there, naming the port to publish, and
does not open a browser - there is none in a container.

Any web page open in the same browser can send requests to a local server, so the server trusts
nothing it did not hand out itself:

- **A token.** The address the command prints carries a random token
  (`secrets.token_urlsafe(32)`) valid while the server runs. `GET /open?token=...` answers with a
  cookie holding that token - `HttpOnly`, `SameSite=Strict`, path `/` - and a redirect to `/`.
  Every other request needs the cookie. Without it, an API request is answered `401` with
  `{"error": "unauthorised"}`, and any other request with a short page saying to open the address
  `ddd gui` printed.
- **The Host header** must be the server's own `127.0.0.1:<port>` or `localhost:<port>`. That
  refuses a page whose domain was re-pointed at the loopback address (DNS rebinding).
- **A request that changes anything** must be a `POST` with `Content-Type: application/json` and
  an `Origin` of `http://127.0.0.1:<port>` or `http://localhost:<port>`.
- **Headers on every response:** a `Content-Security-Policy` allowing only the server's own
  scripts, styles and requests, with `frame-ancestors 'none'`; `X-Content-Type-Options:
  nosniff`; `Referrer-Policy: no-referrer`; and `Cache-Control: no-store` on the API.
- **Files.** A request names a file by its resolved path, and only a source of the open project
  is served or edited.

Static files come from the package (`importlib.resources`), with an explicit content type for
each extension served. The platform's guess is not used: on Windows `mimetypes` reads the
registry, which can map `.js` to `text/plain`, and a browser under `nosniff` then refuses to run
the page. A path that names no file and is not under `/api/` answers with `index.html`, so the
page's own routes survive a reload.

### 6.4 The session

The session holds one open project. Opening another replaces it.

An analysis of the project yields a **revision**, numbered from 1:

- the findings, grouped by file, both sides of a disagreement marked, each with its check,
  severity, message, pointer and notes;
- every source file of the project, whether it loaded, and a fingerprint of its bytes (SHA-256);
- the resolved dictionary, when resolution got that far.

A new revision is made after every edit, before the edit is answered, and whenever a source
changes on disk. A background thread compares each source's modification time and size once a
second; a change starts an analysis. The standard library has no file watcher, and at the
re-check times measured for the estimate - 49 ms for 720 declarations, 569 ms for 7,080 - a
poll is cheap enough.

The page learns about a revision by asking for anything newer than the one it has
(`GET /api/state?after=N`). The request returns at once when there is one, and otherwise waits
up to 25 seconds and returns the current state; the page asks again. This keeps a page current
without server-sent events or WebSockets, which the standard-library server does not help with.

One lock guards the session: analyses and edits run one at a time. A state request waiting for a
revision does not hold it.

### 6.5 The API

The API is internal. The page and the server ship in one wheel, so the API changes with the
package and is not part of the public interface.

The contract behind it is declared once, as pydantic models in `src/ddd/gui/contract.py`: one
model per request and per response of the table below. `api.py` reads a request with
`model_validate_json` - closed to a key the model does not declare and strict about the type of
every value it does, so a string never becomes an index and an edit's `raw` is never parsed as
the json it holds - and answers with a response model's own `model_dump(mode="json")`, never a
hand-built `dict`. `contract.api_schema()` turns every one of those models into one json schema,
every model under its own name in `$defs`, which `gui/scripts/schemas.mjs` reads to write
`gui/src/generated/api.ts`. A model the eight endpoints never reach would be missing there, which
a test of `contract.py` itself refuses to let past - a model added to the contract without a page
type of its own fails that suite, not a frontend silently left behind what the server sends. Not
part of `ddd schema`: that command publishes the file formats a project's own files are checked
against, and the api answers no file.

| Request | Answer |
| --- | --- |
| `GET /api/session` | the DDD version, `preview: true`, the open project (path and name) or none, and the build records applied |
| `GET /api/projects` | the directory searched, and each project found: path, name, and the build record it came from if any, with the reason when a record was refused |
| `POST /api/open` `{path}` | opens one of the projects found, or the one given on the command line; answers like `/api/session` |
| `GET /api/state?after=N` | the revision number, every source (path, kind, loaded, fingerprint, finding counts) and every finding |
| `GET /api/file?path=P` | the file's parsed content, or the reason it does not parse, and its fingerprint |
| `GET /api/dictionary` | the resolved dictionary of the current revision, as `ddd dump` writes it, or `null` |
| `GET /api/checks` | the checks, as `ddd checks --format json` lists them, with the open project's plugin checks |
| `POST /api/edit` | see below |

An error answers with a status code and `{"error": <code>, "message": <sentence>}`. A request
that does not read as its model - `POST /api/open`'s or `POST /api/edit`'s - answers `400` as
`bad-request`, its message the first problem the model found, trimmed to one sentence.

An edit names every file it changes, the fingerprint each was read at, and the operations to
apply to it in order:

```json
{
  "changes": [
    {
      "file": "C:/work/demo/components/controller.ddd.json",
      "fingerprint": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
      "operations": [
        { "op": "set", "pointer": "component.interface[0].definition.unit", "raw": "\"rpm\"" }
      ]
    }
  ]
}
```

| Operation | Does |
| --- | --- |
| `set` `{pointer, raw}` | replaces the value at `pointer`, or adds the member when its object lacks it |
| `remove` `{pointer}` | removes a member or an element |
| `insert` `{pointer, raw}` | inserts an element before index `i` of the array, `pointer` ending in `[i]`; `i` may be the array's length |
| `move` `{pointer, to}` | moves an element of an array to index `to` |

**Values are raw JSON text,** never JavaScript values. DDD reads `1.0` as fractional and `1` as
an integer, and `JSON.stringify(1.0)` is `"1"`: a value typed by the user travels as the text
they typed, and the server checks it is exactly one JSON value.

The whole edit is applied or none of it is. It answers `200` with the new revision and each
file's new fingerprint, or `409` with one of:

- `stale` - a file's fingerprint is not the one on disk;
- `unreadable` - a file the edit changes is not valid JSON, so there is no position in it for a
  pointer to name;
- `invalid` - a pointer names nothing, an operation does not fit what it names, or a raw value
  is not one JSON value;
- `unverified` - the edited text did not read back as the intended document (section 6.6).

The milestone 1 page uses `set` alone. The engine and the API take all four now, because they
are one piece of work and later milestones need them.

### 6.6 The edit engine

`src/ddd/editing.py` works on the text of one file through the existing `Document` scanner and
produces edits as offsets: `TextEdit(start, end, text)`.

**Layout.** An edit follows the file it lands in:

- A replaced value is its span alone; the key, the spacing around it and everything else on the
  line stay as they were.
- A member added to an object goes after its last member: on the same line after `", "` when the
  object is written on one line, otherwise on a new line with the indentation of the last
  member's line.
- An element inserted into an array follows the same rule, before the element it is inserted
  at, or after the last one.
- A value added to an empty container is written between its brackets, on their line.
- Removing a member or an element takes exactly one comma with it: the one after it, or, for the
  last one, the one before it. Removing the only one leaves `{}` or `[]`.
- A structured value is laid out by re-indenting its tokens, never by parsing and serialising it
  again, so every literal keeps its spelling. It goes on one line into a container written on
  one line, and one member per line into one that is not. An empty container takes the layout of
  the container around it.
- The indentation unit is the difference between the indentation of the first nested member in
  the file and that of its parent; two spaces when the file nests nothing on separate lines.
- New line breaks use the file's line ending. A byte-order mark at the start of the file is kept.

**Verification.** The engine applies the same operations to the parsed document, reads the
edited text back, and compares the two. Anything but equality refuses the edit as `unverified`
and writes nothing. It is a cheap check on a description file, and it turns a layout rule that
misjudged a file into a refusal instead of a corrupted file.

**Writing.** All files of an edit are checked against their fingerprints first, then each is
written to a temporary file beside it and moved over it with `os.replace`. If a replacement
fails partway, the files already replaced are written back from the bytes read before the edit,
and the answer names any that could not be restored.

**One implementation.** The layout rules above exist today as private helpers: adding and
removing a member in `ddd.lsp.edits` (`_insert`, `_erase`), and the line ending and indentation
of a new line in `ddd.identity` (`_newline_at`, `_indent_of_line_at`). They move into the engine,
and the language server's quick fixes and `ddd id --assign` call it. The language server keeps
the decisions that are its own - it still refuses to remove an only member - and turns offsets
into protocol ranges through a public `Document.position`. The existing tests of both are the
guard that nothing they do changes.

### 6.7 The frontend

`gui/` is a Vite project: React, TypeScript in strict mode, and TanStack Query holding what
the page fetched from the server and invalidating it when a new revision arrives.

- **Types** for the description files and the dictionary are generated from `ddd schema all` at
  build time (`json-schema-to-typescript`), so a file-format change that the page has not caught
  up with fails the build. The api's own types are generated the same way, from
  `ddd.gui.contract.api_schema()` rather than a file on disk (section 6.5); `gui/src/api/types.ts`
  re-exports them under the names the screens import, so a screen imports one contract whichever
  of the two it came from.
- **Pointers** are parsed and built by a TypeScript twin of `ddd.lsp.ranges.segments`, tested
  against the same spellings, escaped keys included.
- **Screens:** the start page (the projects found), the project (its components and finding
  counts), and the component (its declarations, the unit editor, its findings). A banner reports
  a server that stopped, an edit refused as `stale` (with the file reloaded), and any other
  refusal with its message. The unit editor confirms on Enter and cancels on Escape.
- **Styling** is plain CSS on a small set of tokens: colours, spacing, type sizes. There is no
  component library yet; milestone 2 chooses one and the visual style, so the skeleton is not
  styled twice.
- **Lint and format** are Biome, pinned, one tool doing what ruff does for the Python.

The compiled pages go to `src/ddd/gui/static/`. For frontend work, `npm run watch` rebuilds
them on every change and a reload of the page served by `ddd gui` shows the result. There is no
proxying development server: it would need the server's origin check relaxed, and a rebuild is
fast enough.

### 6.8 Packaging

- `src/ddd/gui/static/` is ignored by git and declared a build artifact, so hatch puts it into
  the source distribution and the wheel although git does not track it. The `gui/` sources and
  their lock file go into the source distribution like `editors/vscode` does.
- The compiled pages include `third-party-licenses.txt`, the licence of every package bundled
  into them, written by the build. The build fails on a licence outside MIT, ISC, Apache-2.0 and
  the BSD licences.
- The publish workflow installs the package (the types are generated by `ddd schema`), compiles
  the pages before `python -m build`, and fails when the wheel it built has no
  `ddd/gui/static/index.html`.
- An installation without the compiled pages - an editable install where nobody has run the
  build - makes `ddd gui` exit 2 with the two commands that build them. A released `ddd-tool`
  always has them.
- No runtime dependency is added to the Python package.

### 6.9 CI

A new `gui` job in `ci.yml`, on Ubuntu and Windows, with Python 3.12 and Node 24 (the version
the extension job already uses):

1. `pip install -e .`
2. `npm ci`, then the type generation, the Biome check, the type check and Vitest with its
   coverage gate
3. `npm run build`
4. install Playwright's Chromium, then the end-to-end tests
5. on failure, upload the Playwright report

The existing `test` job is unchanged: the server's Python tests use a small stand-in page, so
the Python suite needs no Node. Dependabot gains an npm entry for `/gui`.

### 6.10 What the user sees when something goes wrong

- **A file does not parse, or fails its schema.** The project still opens, the file is marked as
  not loaded, and its findings say why. A file that is not valid JSON has no positions to edit,
  so an edit to it is refused as `unreadable`; editing its raw text in the GUI is milestone 3. A
  file that parses but fails its schema can still be edited.
- **A plugin raises.** The finding the language server reports (`plugin-invalid`) is shown on
  the project, and the project opens without a dictionary.
- **A build record is refused** - written by a newer DDD, or naming a check this one does not
  have. The start page lists it with the reason, as the language server logs it.
- **The page is out of date.** An edit is refused as `stale`; the page reloads the file and
  says the file changed on disk.
- **The server stopped.** The page says so and disables editing; starting `ddd gui` again and
  opening its new address restores it.

### 6.11 Testing

The Python suite keeps its 100% line and branch gate, ruff and strict mypy.

- **The edit engine** is tested operation by operation over a set of layouts: an object on one
  line and one member per line, tabs and spaces, `\r\n` and `\n`, a byte-order mark, nested
  containers, escaped keys, empty containers, the first, last and only member or element. Every
  test states the exact text expected, not only the parsed result, and literals such as `1.0` and
  `1e3` keep their spelling. Verification is shown refusing a text that reads back differently,
  and a write is shown restoring the files already replaced when a later replacement fails.
- **The server** is tested through real HTTP requests against a stand-in page: the token
  exchange, a missing cookie, a foreign `Host`, a foreign `Origin`, a non-JSON body, the response
  headers, the content type of `.js`, the fallback to `index.html`, confinement to the project's
  sources, every endpoint on `examples/demo` and on a project with a file that does not parse, an
  edit whose written file differs from the original by exactly the unit's value, the `stale`,
  `unreadable`, `invalid` and `unverified` refusals, a revision made by a change on disk (with the
  poll interval shortened), a waiting state request woken by a new revision, the missing pages,
  and a taken port.
- **The command** is tested for its options and its exit codes.
- **The language server and `ddd id`** keep every existing test, unchanged, across the move of
  their helpers into the engine.

The frontend has two layers:

- **Vitest**, with a 100% gate on the logic modules: the API client, the pointers, and the state
  that follows the revisions. Screens are left to the next layer.
- **Playwright**, in Chromium on Windows and Linux, against the real `ddd gui` serving a
  temporary copy of `examples/demo`: every step of section 6.1, the file's bytes compared before
  and after an edit, a change written to disk by the test appearing on the page, a stale edit
  refused, and the page's message when the server is stopped.

### 6.12 Documentation

- The command-line reference, generated from the argument parser, describes `ddd gui` as a
  preview.
- The README's command table gains `ddd gui [PROJECT]`, marked preview.
- SPEC.md lists the command, and says its options are not yet part of the stable interface.
- CHANGELOG.md records it under the next release as a preview.
- The developer documentation says how to build, test and watch the frontend.

The user guide is milestone 8's: until the screens exist, a guide would describe mockups.

### 6.13 Measuring

The estimate's figure with Claude rests on how fast the frontend work goes, which DDD had never
measured. Each implementation task of this milestone records its duration and token count in the
plan's progress log. At the end of the milestone the speed-ups for the server, the edit engine
and the frontend foundation are computed from those records, and the estimate page is updated
through its address.

## 7 Out of scope for milestone 1

- Editing anything but a declaration's unit.
- The visual style, a component library, the findings in plain language.
- Undo.
- The raw-text editor for a file that does not parse.
- Switching between the build records that name one project.

## 8 Deferred

- **A package for the protocol-neutral parts of `ddd.lsp`.** Discovery, the analysis wrapper,
  navigation and ranges serve the GUI as much as the language server. Moving them is a pure
  rename with nothing to gain until a third client exists.
- **Server-sent events** instead of the long-polled state request, if polling ever shows in a
  profile.
- **A development server with hot reloading**, if `npm run watch` proves too slow.
- **A single Windows executable** that needs no Python (section 3).

## 9 Evidence

- The estimate: https://claude.ai/artifact/HT1HxkAp8Cg2rAqbYb7EL6, with its measured re-check
  times (49 ms, 569 ms and 4,002 ms for 720, 7,080 and 35,200 declarations in a running process)
  and the repository history its speed-ups are drawn from.
- The four answers that set the scope, given while scoping the estimate: local deployment; the
  complete first version; variables declared only in DDD; hand-designed screens over the
  existing engine.
- The code section 4.2 names, read at `db0df30` (release 0.10.0).
