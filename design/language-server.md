# A language server for `*.ddd.json`

**Status**: proposal, nothing implemented.

## What it is for

A json schema is per-file and static. It can say a declaration has a `datatype` and that the
value is one of eleven strings. It can never say that `"axis": "EngSpdAxis"` has to name an
axis declared in a *different component's file*, that exactly one component may produce a
name, that a unit has to match what every other declarer says, or that a name has to follow
the project's convention. Every one of those is a `ddd check` finding today, and every one of
them arrives at build time rather than while the line is being typed.

The gap is not new and named types do not create it - they only add one more thing to it.

## Division of labour with the published schema

The server does not replace the schema, and neither one is redundant:

| | provides |
| --- | --- |
| json schema | structure: which keys exist, which are required, closed objects, the eleven datatypes, the documentation we publish on every key and value |
| language server | meaning: everything that needs the whole project resolved |

Editors run both against one document without conflict - diagnostics from several sources
coexist and completions merge. The schema keeps working for anyone who never installs the
server, including a ci job that validates files without running DDD.

## What it offers, in value order

Each entry names the machinery that already exists, because almost none of this is new logic.

**1. Diagnostics.** The whole of `ddd check`, in the editor. `load_workspace` + `analyze`
already produce a `DiagnosticBag`, and `Diagnostic` already carries everything LSP wants:
`check` maps to the diagnostic code, `severity` maps directly, `CHECKS[check].description`
gives the code description, and `notes` - `(text, Location)` pairs, already used for "the
conflicting declaration is here" - map exactly onto `relatedInformation`. The severity policy
is already configurable through `SeverityPolicy.from_strings`, which is what a workspace
setting would feed.

**2. Go to definition.** From an `input` declaration to the `output` that produces it, and
from `axis` / `x_axis` / `y_axis` / `input` to the declaration of the object referred to.
`Variable.producer` is a `DeclarationRef`, and `DeclarationRef.location(suffix)` already
resolves to the exact pointer in the exact file. This is the feature no schema can ever
provide and the one most likely to be used every day.

**3. Find all references.** `Variable.declarations` is already every site that declares the
object. Reverse of the above, same data.

**4. Completion.** Project-aware, so genuinely additive to what the schema offers:

- object names for a reference field, filtered by the kind that field requires - `_lookup`
  already knows the expected `ObjectKind` per field, so the filter is not new;
- names for the `name` of a new declaration, from `complete(prefix, convention)` in
  `ddd.naming`, which already exists and already returns convention-driven candidates. This
  is a strong one: it turns the naming convention from something that judges a name after the
  fact into something that writes it;
- units, enum names and declared type names already used elsewhere in the project.

**5. Hover.** The resolved object rather than the authored text: producer, consumers, the
shape a curve got from its axis, the limits that were derived rather than stated,
`conversion.describe()`. None of it is in the file being hovered.

**6. Rename.** A variable renamed across every component that declares it, from the same
`Variable.declarations` list.

**7. Quick fixes.** `Inspection.suggestions` already computes "did you mean" for a name that
misses the convention. Those become code actions almost directly.

Stages 1 and 2 are most of the value. Everything below 4 is optional.

## The three hard problems

### Which project does this file belong to?

The real one. `load_workspace` goes project → files, and `Workspace.sources()` already lists
them. A server has the inverse problem: the engineer opened `sensor_hub.ddd.json`, and a
component on its own is not a project - its inputs have no producers, so analysing it alone
reports nonsense.

**The obvious answer does not work.** Scanning the workspace for files whose top level key is
`project` and inverting `sources()` fails for the mode most CMake projects are in.
`ddd_generate` without `PROJECT` *synthesizes* the project description, into
`${OUTPUT_DIRECTORY}/${NAME}.ddd.json` in the build tree, with its `includes` coming from
`$<TARGET_PROPERTY:${image},DDD_JSON>` - the c link closure, resolved at generate time. In
that mode the source tree contains no project file at all, and which components belong
together is a property of the **build**, not of any `*.ddd.json`. No amount of reading
description files recovers it.

**So the build system is asked, and CMake is assumed.** This is a deliberate narrowing of
scope for the first version, and it is smaller than it sounds: both branches of
`ddd_generate` end with one `project_file` variable holding an absolute path - the
hand-written `PROJECT` in one, the generated description in the other - so one hand-off covers
both modes. A hand-written project description keeps working, provided it is wired in through
`ddd_generate(PROJECT ...)`.

What is genuinely dropped is a project no CMake build references at all. Those fall back to
standalone mode, below.

There is precedent for CMake telling the editor things, in this same module:
`_ddd_write_schemas` writes the json schemas at configure time purely so an editor can
validate - nothing in the build consumes them - and `_ddd_project_sources` already shells out
to `ddd sources` at configure time to learn structure.

Proposed shape: each `ddd_generate` writes a sidecar into its own `OUTPUT_DIRECTORY`,
naming the resolved project description and the severity options the build uses:

```json
{ "image": "firmware.elf",
  "project": "/abs/path/to/firmware/ddd/firmware.ddd.json",
  "strict": false,
  "severity": ["unused-output=info"] }
```

The severity options matter as much as the path: `--strict` and each `-W` are arguments to
`ddd_generate`, and a server that does not read them reports a different set of findings than
the build does, which is worse than reporting none.

It **cannot** be named `*.ddd.json`. That extension means "a DDD description file" - the
`file-extension` check enforces it and `file-kind` would reject this content.

**Implemented** as `ddd-build.json` - named for what writes it rather than for the one tool
that happens to read it first, since any build system can write one and anything can read it.
The contract is `ddd.build_info.BuildInfo` and `ddd build-info` writes it; the `format` key
carries a version, so fields can be added later as a defined change. `executable` was
considered and left out: the server has no use for it until a client needs to launch a
matching DDD, and that is stage 3's problem.

One sidecar per `ddd_generate` rather than one index for the build: it avoids accumulating
state across directories in CMake, and it falls out correctly when several images exist.

Three cases follow:

- **A file in several images.** Now the common case rather than a curiosity - a component
  linked into both the firmware and a test binary is in two projects. Proposed: analyse under
  each, deduplicate identical findings, and name the image on those that differ.
- **A file in no configured project.** Legitimate - `ddd check` accepts a lone component.
  Proposed: analyse standalone and suppress `missing-producer`, which in single-file mode
  says nothing true.
- **A stale sidecar.** In the collected mode the project description is only as current as
  the last configure, so a component added since then is invisible to the server. It is also
  invisible to the build, which is the honest defence; `CMAKE_CONFIGURE_DEPENDS` already
  covers the hand-written case. The server should watch the sidecar and reload rather than
  cache it for the session.

### Finding the build directory

Consequence of the above, and the one piece with no precedent to lean on. The editor's
workspace root is the *source* directory; the sidecars are in the build tree, which may be
`build/`, `out/`, `cmake-build-debug/` or somewhere else entirely.

Proposed: a `ddd.buildDirectory` setting, defaulting to a search for `ddd-build.json` under
the common build directory names beneath the workspace root. Reading `CMakeCache.txt` or the
CMake file API is more correct and more machinery than a first version justifies.

### Json pointer to text range

Findings point at `component.declarations[2].definition.unit`, which the documentation
defends on purpose: a line number in a file that is often generated or reformatted means very
little. LSP needs a range.

`Location` already has optional `line` and `column` fields, populated today for json syntax
errors - so the shape is right and the work is populating them for every finding. That needs
a position-preserving parse, which the standard library's `json` does not offer. Proposed: a
small scanner that maps pointer → offset span over the raw text, in the server layer only, so
nothing in the loader or the analysis changes. Bounded work, no new dependency.

Worth noting the fallback: a diagnostic whose pointer cannot be resolved goes on line 1 rather
than being dropped. A finding in the wrong place beats a finding nobody sees.

### Re-analysis cost

Every keystroke cannot re-resolve a project. Proposed: analyse on save and on open, debounced,
never on keystroke, and measure before optimising - a project of a few thousand variables is
pure python but is also not much work. If it turns out to be too slow, the cheap first move is
caching parsed files by mtime inside the loader, not incrementalising the analysis.

Note the two-phase design shows through here: `_analyze` returns early when loading reported
an error, so while a file is mid-edit and unparseable the server has no semantic findings to
give. That is correct - it is the same reason `ddd check` does it - but it means the editor
falls back to schema-only feedback exactly while someone is typing. Worth keeping the last
good analysis and serving hover and completion from it.

## Architecture and the coverage gate

The gate is 100% of statements and branches, and the documented stance on unreachable code is
that the fix is deleting it, not testing it. Protocol glue is where that goes wrong, so:

- `ddd/lsp/services.py` - pure, no protocol types. Workspace resolution, pointer → range,
  completion candidates, hover text. Ordinary unit tests, ordinary coverage.
- `ddd/lsp/server.py` - the adapter. As thin as it can be made: receive, call a service,
  translate the result.

If the adapter cannot be brought to 100% with an in-process test client, the honest response
is to make it thinner, not to add a coverage exclusion. That is the same conclusion the
project already reached once.

The layering test in `tests/test_backends.py` walks the import graph; the server imports the
front end and must not be imported by it, which is worth asserting there too.

## Packaging

Three existing tests make the cost of this precise:

- `test_the_runtime_requirements_are_what_the_package_imports` asserts `requirements.txt` is
  exactly `{pydantic, jinja2}`. So the server dependency is an **extra**: a
  `requirements-lsp.txt`, an `lsp` entry under
  `[tool.hatch.metadata.hooks.requirements_txt.optional-dependencies]`, and the file added to
  the sdist `include` list - which `test_every_requirements_file_is_declared_and_shipped`
  will check. `pip install ddd-tool[lsp]`.
- `test_the_command_list_is_what_the_spec_promises` pins the exact set of subcommands, so
  `ddd lsp` means updating that test, `README.md` and `SPEC.md`. A subcommand rather than a
  second console script keeps one entry point.
- `test_no_help_string_carries_markup_characters` - the help text cannot contain `*`, backtick
  or `|`.

`ddd lsp` speaks over stdio, which is what every editor expects and what makes it testable
without a socket.

## The part that does not stay small

I criticised the GUI for exactly this, so it has to be said here too.

Neovim, Helix and Emacs users point their config at `ddd lsp` and are done. **VS Code cannot
launch a language server without an extension**, and an extension is a second artefact: a
TypeScript project, an npm build, a marketplace listing or a `.vsix` to distribute, and its
own version to keep in step with the python package.

The difference in degree is real - a `vscode-languageclient` wrapper is on the order of fifty
lines and never grows, where a GUI editor is an application - but it is a second thing to
release, and if VS Code is the main audience it should be planned for rather than discovered.

## Staging

0. **The CMake sidecar.** `ddd_generate` writes the resolved project path and severity
   options. Independently useful and independently testable - `tests/test_cli.py` and the
   CMake example project already exercise this integration - and everything else needs it.
1. **`ddd lsp` with diagnostics only.** Sidecar discovery, pointer → range, publish on save.
   This is the whole reason to do it and it is testable end to end.
2. **Go to definition and find references.** No new analysis, only location plumbing.
3. **Minimal VS Code extension** - **done**, in `editors/vscode`. A launcher and nothing more:
   two settings, one restart command, no status bar and no views, so that whether the extras
   are wanted can be decided after seeing the plain thing used.

   Two decisions came out of building it. It is **not published to the marketplace** - every
   release attaches a `.vsix`, which for a commercial tool is a normal channel and costs no
   publisher account or public cadence. And it is **not in the docker image**: ci puts python
   and node side by side with two actions, where a second toolchain in the image would be paid
   for by everyone who only wants to compile c. The price of that is that the one test worth
   having - which starts the real server through the command the extension builds - runs in ci
   rather than locally.
4. **Hover** - **done**, in `ddd/lsp/hover.py`. The resolved object rather than the authored
   text, plus the init values as a sparkline where there is variation to see.

   Two things were settled by building it. The dictionary has resolved away *whether* limits
   were stated or derived, so the hover says what is knowable instead - that they are the full
   range of the datatype, which is what matters to whoever reads it. And a flat set is stated
   rather than drawn: a scalar ``init`` broadcast over an array is genuinely all the project
   says, and a row of identical bars reads as data rather than as its absence.

   **Completion** is what is left of this stage. Convention-driven name completion, from
   ``complete(prefix, convention)``, is the piece worth having.
5. **Rename** - **done**. `textDocument/rename` with `prepareRename`, rewriting the name
   string in every declaration and every reference key that names the object.

   Narrow where hover and navigation are wide, and for a concrete reason rather than caution:
   an editor opens its rename box *over the range prepareRename returns*, so answering from a
   datatype would put the box several lines from the pointer. Refusals are json-rpc errors
   rather than empty edits, because an empty edit reads as a rename that silently did nothing.

6. **Quick fixes** - **done**, in `ddd/lsp/edits.py`. `textDocument/codeAction` offers to
   give every other declaration of an object the value under the cursor.

   Insertion was the work, as expected: the usual mismatch is a declaration omitting the key,
   so the edit adds `"unit": "Hz"` beside the last member, taking its indentation, and staying
   on one line when the object is written on one. Two rules keep it safe - the value is copied
   as *source text* rather than re-serialised, and a value is only ever written, never removed,
   which is what keeps the comma juggling of a deletion out of the picture entirely.

   **Completion** is what remains of the plan.

## Open questions

1. **Does the server report `schema` findings, or leave structure to the json schema?**
   Leaving them out avoids reporting an unknown key twice, but the `schema` check also carries
   the cross-field rules the json schema cannot express - which member shape takes which keys,
   `min` not above `max`, what a condition may contain. Proposed: report them, accept the
   overlap on plain structural mistakes, and revisit once it has been seen in practice.
2. ~~Where does the severity policy come from?~~ **Settled**: from the CMake sidecar, so the
   server and the build agree by construction. A project-level severity file would be a
   better answer still - it would mean everyone checking the project sees the same severities,
   which is the argument the `naming` key on a project already makes - but that is a change to
   a released file format and is not needed here.
3. **Is VS Code the audience?** Decides whether stage 3 is optional or central.
4. **Does a non-CMake build system need an equivalent?** Assumed no for now. If one does, the
   sidecar is a plain json file any build system can write, so the server side does not
   change - only who writes it.
5. **`pygls`, or hand-rolled?** A dependency in an extra is cheap, and json-rpc over stdio is
   not hard; but hand-rolling it means owning a protocol implementation forever. Proposed:
   `pygls`.
