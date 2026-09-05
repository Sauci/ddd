# Plugins in the build - implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A plugin the project names is a first-class citizen of the build: `ddd generate all` produces its artefact, `ddd sources` lists its module, and `ddd_generate` takes `PLUGINS`, writes them into the generated project, closes the editor schemas over them and depends on them.

**Architecture:** Three increments, each leaving the suite green and the pages true. The loader records each plugin's file beside the spelling and origin it already keeps, and the workspace's sorted source list gains them. The generate command's artefact table gains a `with_plugins` column that only `all` sets, and the command appends the plugins' backends after the built-in ones through the existing collision-refusing renderer. The CMake module gains a `PLUGINS` multi-value argument, writes it into the generated project description, passes `--plugin` to its schema step, and refuses `PLUGINS` beside `PROJECT`.

**Tech Stack:** Python 3.12 (pydantic, argparse), pytest with 100% branch coverage, CMake 3.20+ module, Sphinx docs, `tests/test_documentation.py` pins.

**Spec:** `docs/superpowers/specs/2026-09-05-plugins-in-the-build-design.md`

## Global Constraints

- `ruff check`, `ruff format --check`, `mypy src` clean; `pytest -q` at 100% coverage on 3.12/3.13 (the local 3.14 venv has one known unrelated failure).
- Every doc statement that can be pinned is pinned in `tests/test_documentation.py`; transcripts over shipped examples stay true under `tests/test_transcripts.py`.
- Commit messages: lowercase imperative subject, prose body saying why; `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- No option is added anywhere except `PLUGINS` on `ddd_generate`.

---

### Task 1: `ddd sources` lists the plugin modules

**Files:**
- Modify: `src/ddd/plugins.py` (a `plugin_source` lookup beside `load_plugin`)
- Modify: `src/ddd/loading.py` (`LoadedPlugin.source`, `Workspace.plugin_paths`, `Workspace.sources`)
- Modify: `SPEC.md` (section 7, the `ddd sources` sentence), `docs/command_line_interface.rst` (sources row), `docs/plugins.rst`, `docs/build_integration.rst` (the hand-written project paragraph on `ddd sources`), `CHANGELOG.md`
- Test: `tests/test_cli.py`, `tests/test_plugins.py`

**Interfaces:**
- Produces: `ddd.plugins.plugin_source(spelling: str, base: Path) -> Path | None`; `Workspace.plugin_paths: tuple[Path, ...]`; `Workspace.sources()` includes them.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cli.py, in the class holding the sources tests (or a new TestSources)
LAYOUT = EXAMPLES / "layout" / "project.ddd.json"
PLUGIN_FILE = (EXAMPLES / "plugins" / "ddd_layout.py").resolve()

def test_the_plugin_modules_are_among_the_sources(self, capsys) -> None:
    """A build that does not re-run when a plugin changes generates with yesterday's rules."""
    assert main(["sources", str(LAYOUT)]) == EXIT_OK
    listed = capsys.readouterr().out.splitlines()
    assert PLUGIN_FILE.as_posix() in listed
    assert listed == sorted(listed)

def test_the_plugin_modules_are_in_the_json_list_too(self, capsys) -> None:
    assert main(["sources", str(LAYOUT), "--format", "json"]) == EXIT_OK
    assert PLUGIN_FILE.as_posix() in json.loads(capsys.readouterr().out)["sources"]

def test_a_plugin_that_did_not_load_contributes_no_source(self, tmp_path, capsys) -> None:
    root = write_tree(tmp_path, {"p.ddd.json": project("P", plugins=["missing.py"])})
    assert main(["sources", str(root)]) == EXIT_OK
    assert not any(line.endswith(".py") for line in capsys.readouterr().out.splitlines())

# tests/test_plugins.py
def test_a_module_named_by_dotted_name_lists_its_file(tmp_path, monkeypatch, capsys) -> None:
    write_plugin(tmp_path / "site", "tag_plugin.py")
    monkeypatch.syspath_prepend(str(tmp_path / "site"))
    root = write_tree(tmp_path, {"p.ddd.json": project("P", plugins=["tag_plugin"])})
    assert main(["sources", str(root)]) == EXIT_OK
    assert (tmp_path / "site" / "tag_plugin.py").resolve().as_posix() in capsys.readouterr().out

def test_a_module_without_a_file_contributes_nothing(tmp_path, monkeypatch, capsys) -> None:
    """Only a module planted without a file - nothing importlib loads from disk lacks one."""
    module = types.ModuleType("planted_plugin"); module.PLUGIN = Plugin(name="planted")
    monkeypatch.setitem(sys.modules, "planted_plugin", module)
    root = write_tree(tmp_path, {"p.ddd.json": project("P", plugins=["planted_plugin"])})
    assert main(["sources", str(root)]) == EXIT_OK
    assert ".py" not in capsys.readouterr().out
```

- [ ] **Step 2: Run them, expect failures** (`pytest tests/test_cli.py tests/test_plugins.py -k "sources or contributes"`)

- [ ] **Step 3: Implement**

```python
# src/ddd/plugins.py
def _path_of(spelling: str, base: Path) -> Path:
    raw = Path(spelling)
    return (raw if raw.is_absolute() else base / raw).resolve()

def plugin_source(spelling: str, base: Path) -> Path | None:
    """The file a loaded plugin came from, for the dependency list of a build system.

    A path spelling names its file; a module spelling has the file its import recorded, which
    only a module planted into ``sys.modules`` without one lacks. Nothing is imported here:
    this answers for a plugin ``load_plugin`` has already loaded.
    """
    if spelling.endswith(".py"):
        return _path_of(spelling, base)
    source = getattr(sys.modules.get(spelling), "__file__", None)
    return Path(source).resolve() if source else None
```
`_load_from_path` uses `_path_of`. In `loading.py`: `LoadedPlugin` gains `source: Path | None`; `_load_plugin` stores `plugin_source(spelling, base)`; `Workspace.plugin_paths: tuple[Path, ...] = ()` with a docstring saying why a plugin is a source; `sources()` returns `tuple(sorted({self.root, *self.read_paths, *self.plugin_paths}))`; both `Workspace(...)` constructions pass `plugin_paths=self._plugin_paths`, a property collecting `loaded.source` where not None, in project order, deduplicated.

- [ ] **Step 4: Run the suite** - green, 100% coverage.

- [ ] **Step 5: Spec and pages**: SPEC.md section 7 sources sentence (the plugin modules are listed, by their files); `command_line_interface.rst` sources row; `plugins.rst` one sentence after the loading paragraph; `build_integration.rst` hand-written paragraph ("and the plugin modules it names"); CHANGELOG bullet under Unreleased ("**Plugins in the build.** `ddd sources` lists the modules of the plugins a project names ...").

- [ ] **Step 6: Commit**: `list the plugin modules among a project's sources`

### Task 2: `ddd generate all` runs the plugins' backends

**Files:**
- Modify: `src/ddd/cli.py` (artefact table, `_add_generate_arguments`, `_command_generate`, the generate description)
- Modify: `SPEC.md` (3.11 backend sentence; 7 generate sentence), `docs/plugins.rst` (146-150), `docs/command_line_interface.rst` (generate row), `README.md` (plugins section if it says "by that name alone"), `CHANGELOG.md`
- Test: `tests/test_cli.py`, `tests/test_plugins.py`

- [ ] **Step 1: Failing tests**

```python
# tests/test_cli.py TestGenerate
def test_all_produces_the_plugins_artefact_too(self, tmp_path, capsys) -> None:
    code = main(["generate", "all", str(LAYOUT), "-o", str(tmp_path), "-t", str(EXAMPLES / "templates"),
                 "-W", "missing-id=ignore", "--format", "json"])
    assert code == EXIT_OK
    written = [entry["path"] for entry in json.loads(capsys.readouterr().out)["generated"]]
    assert written[-1].endswith("ddd_layout.h")           # after the built-in files
    assert (tmp_path / "ddd_layout.h").is_file()

@pytest.mark.parametrize("artefact", ["c", "a2l"])
def test_a_single_built_in_artefact_runs_no_plugin(self, tmp_path, artefact) -> None: ...  # no ddd_layout.h

# tests/test_plugins.py
def test_all_runs_the_plugins_in_project_order(tmp_path, capsys) -> None:
    # two plugins whose backends write first.h / second.h; project names ["b.py", "a.py"]; assert the
    # generated list ends with the b file then the a file.

def test_a_plugin_file_colliding_with_a_built_in_one_is_refused(tmp_path, capsys) -> None:
    # a plugin backend writing ddd_globals.c: exit EXIT_USAGE, stderr names both backends, nothing written.
```

- [ ] **Step 2: Run, expect failures.**

- [ ] **Step 3: Implement**

```python
# the artefact table
for name, description, with_c, with_a2l, with_plugins in (
    ("c", "render the c sources from the project's jinja2 templates", True, False, False),
    ("a2l", "write the a2l file, with the addresses --address-map carries", False, True, False),
    ("all", "render the c sources, write the a2l file and produce the plugins' artefacts", True, True, True),
):
    _add_generate_arguments(artefacts.add_parser(name, help=description), with_c=with_c, with_a2l=with_a2l, with_plugins=with_plugins)
# _add_generate_arguments(..., with_plugins: bool = False) -> set_defaults(..., render_plugins=with_plugins)
# _command_generate, after the a2l backend:
if getattr(args, "render_plugins", False):
    backends.extend(backend_of(plugin, dictionary, GENERATOR) for plugin in resolved.plugins if plugin.backend is not None)
```
The generate description's "'all' produces both in one run" becomes "'all' produces both and the artefact of every plugin the project names that provides one".

- [ ] **Step 4: Run the suite** - green; `tests/test_transcripts.py` unaffected (the demo names no plugin).

- [ ] **Step 5: Spec and pages**: SPEC 3.11 ("selected as `ddd generate <name>` and produced by `ddd generate all` after the built-in artefacts, in the order the project names the plugins; two artefacts claiming one path are refused before anything is written"); SPEC 7 generate sentence if it says `all` is the pair; `plugins.rst` 150 ("``all`` runs them after the built-in pair, in the order the project names the plugins"); `command_line_interface.rst` generate row; README plugins section; CHANGELOG bullet extended.

- [ ] **Step 6: Commit**: `produce the plugins' artefacts under ddd generate all`

### Task 3: the CMake module

**Files:**
- Modify: `cmake/Ddd.cmake` (header comment, `cmake_parse_arguments`, `_ddd_write_project_file`, `_ddd_write_schemas`, a `_ddd_plugin_specs` helper, a `_ddd_project_plugins` helper, the DEPENDS)
- Modify: `docs/build_integration.rst`, `docs/getting_started.rst`, `README.md`, `SPEC.md` 7.1, `CHANGELOG.md`
- Test: `tests/test_documentation.py` (TestTheBuildIntegrationPage)

- [ ] **Step 1: Failing pins**

```python
def parsed_options(module: str) -> set[str]:
    """Every keyword ddd_generate's cmake_parse_arguments accepts."""
    lists = re.search(r'cmake_parse_arguments\(PARSE_ARGV 1 arg\s+"([^"]*)"\s+"([^"]*)"\s+"([^"]*)"\)', module)
    return {name for group in lists.groups() for name in group.split(";") if name}

def test_every_option_of_ddd_generate_has_a_row_on_the_page(self):   # PLUGINS missing -> red
def test_every_option_of_ddd_generate_is_named_in_the_readme(self):  # README:784 list
def test_the_generated_project_names_its_plugins(self):              # '"plugins"' in the file(GENERATE) template
def test_the_schema_step_closes_over_the_plugins(self):              # "--plugin" between "schema all" and RESULT_VARIABLE
def test_plugins_and_project_exclude_each_other(self):               # FATAL_ERROR text naming both
```

- [ ] **Step 2: Run, expect the five to fail.**

- [ ] **Step 3: Implement the module**
  - header comment: `[PLUGINS <spec>...]  # plugins of the collected project: a .py path or a module name`
  - `cmake_parse_arguments(... "SEVERITY;LINK_LIBRARIES;DEPENDS;PLUGINS")`
  - `if(arg_PLUGINS AND arg_PROJECT) message(FATAL_ERROR "ddd_generate: PLUGINS cannot be given with PROJECT: the project description names its own plugins.")`
  - `function(_ddd_plugin_specs variable specs base)`: each spec matching `\.py$` goes through `_ddd_absolute_input`, others pass through; also returns the path specs in a second variable for DEPENDS.
  - `function(_ddd_project_plugins variable project_file)`: `string(JSON count ERROR_VARIABLE error LENGTH "${content}" project plugins)`; loop `string(JSON spec GET ...)`; resolve `.py` against the project file's directory.
  - `_ddd_write_project_file(output name description components plugins)`: a `"plugins": [ "a", "b" ]` line built with `list(JOIN)`, `[]` when empty.
  - `_ddd_write_schemas(directory plugins)`: `--plugin ${spec}` per entry, via `COMMAND_EXPAND_LISTS`-free list expansion (build a `plugin_arguments` list).
  - DEPENDS gains `${plugin_files}` in collected mode.

- [ ] **Step 4: Run the pins** - green. Sanity: `cmake -P` is not available for functions; rely on the pins and on a manual `cmake -S examples/cmake -B /tmp/x` if cmake is installed locally (skip if not).

- [ ] **Step 5: Pages and spec**: `build_integration.rst` PLUGINS row (after PROJECT), SCHEMA_DIRECTORY row ("closed over the project's plugins"), the artefact/consumer sentence, the hand-written paragraph (drop "or because it names plugins"); `getting_started.rst` paragraph (drop the "keeps a file of its own" clause); README options list + one sentence; SPEC 7.1 first paragraph and the SCHEMA_DIRECTORY sentence and keyword list; CHANGELOG bullet extended.

- [ ] **Step 6: Commit**: `name a collected project's plugins from cmake`

### Task 4: verification and pull request

- [ ] full suite, ruff, mypy, sphinx; `git push -u origin feature/plugins-in-the-build`; `gh pr create` with summary and test plan; watch CI.
