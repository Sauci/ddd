# Language server: Windows URIs, buffer-based edits, trust boundary - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `ddd lsp` usable from VS Code on Windows, make its edits safe against an unsaved buffer, and state the trust boundary that opening a description file runs the plugins its project names.

**Architecture:** Three contained changes in `src/ddd/lsp/server.py` and its neighbours: (1) `uri_to_path` normalises the percent-encoded drive colon a Windows client sends before handing the path to `url2pathname`; (2) the server keeps the text of every open document (full-content sync) and seeds the document cache from it, so positions and edits are computed against what the editor shows, and answers rename and quick-fix edits as versioned `documentChanges` when the client supports them; (3) the extension manifest declines untrusted workspaces and three pages plus the spec say why.

**Tech Stack:** Python 3.12 (stdlib only in `src/ddd/lsp`), pytest, VS Code extension manifest (JSON), Sphinx RST, Markdown.

**Spec:** `docs/superpowers/reviews/2026-09-08-complete-review.md`, pass 8 Critical 1, 2 and 3 (on branch `review/complete-review-2026-09-08`; read it with `git show review/complete-review-2026-09-08:docs/superpowers/reviews/2026-09-08-complete-review.md`).

## Global Constraints

- Branch: `fix/lsp-windows-uris-and-buffers`, off `master`. Push after every task (`git push -u origin fix/lsp-windows-uris-and-buffers`). Do not open a pull request.
- Run this checkout, never the `ddd` on PATH: from the repository root, `PYTHONPATH=src python -m ddd ...`; tests as `python -m pytest <file> -k <name> --no-cov -q` while developing, and the full `python -m pytest` (coverage gate at 100%, configured in `pyproject.toml`) before the last commit of the branch. The 12 environmental failures listed in the review's baseline (`tests/test_cmake.py` without cmake beside the interpreter, and `TestSymlinkedWorkspace`) are known; nothing else may fail.
- Static checks, with the venv at `C:/Users/lmbsog0/AppData/Local/Temp/claude/C--git-ac11-ddd/ab815568-8224-42f5-b802-44dd98973875/scratchpad/venv/Scripts/python.exe`: `-m ruff check .`, `-m ruff format --check .` (run `-m ruff format .` to fix), `-m mypy`. All three must be clean before the last commit.
- `src/ddd/lsp` takes no dependency beyond the standard library (`src/ddd/lsp/protocol.py` docstring; a test enforces the two runtime dependencies).
- Commit messages: a lowercase sentence saying what the change does, no prefix (see `git log --oneline -20`), body optional, and the trailer `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Docstrings and comments in the house style: say why, not what; British spelling ("artefact", "behaviour"); no em dashes (the code base writes ` - ` with spaces).
- Every behaviour change gets a bullet in `CHANGELOG.md` under `## Unreleased`, in the style of the entries there (bold lead phrase, then prose, `**Migration:**` where a user has to act).
- Node is not installed on this machine, so `npm test` for the extension cannot run here; CI runs it. Keep the TypeScript untouched.

---

## File Structure

- Modify: `src/ddd/lsp/server.py` - `uri_to_path` (drive colon), the document store (`_open`), `_cache()`, `didChange`/`didClose` handling, `_capabilities` (`change: 1`), `_workspace_edit`, versioned edits in `_answer_rename` and `_actions`, docstrings.
- Modify: `src/ddd/lsp/navigation.py` - `rename_edits` skips a site whose document no longer names the subject at the pointer.
- Modify: `src/ddd/lsp/edits.py` - `_at_site` guard for the reconcile actions' reads of other files.
- Modify: `tests/test_lsp.py` - URI spellings, a server test opening a `%3A` URI, buffer tests, versioned-edit tests.
- Modify: `editors/vscode/package.json` - `capabilities.untrustedWorkspaces`.
- Modify: `docs/editor_integration.rst`, `editors/vscode/README.md`, `docs/plugins.rst`, `SPEC.md` (3.11 and 7.2) - the trust boundary.
- Modify: `tests/test_documentation.py` - the manifest declines untrusted workspaces; the pages say so.
- Modify: `CHANGELOG.md`.

---

### Task 1: Decode the URI spelling a Windows client sends

**Files:**
- Modify: `src/ddd/lsp/server.py:76-90` (`uri_to_path`)
- Test: `tests/test_lsp.py` (`TestRanges`, and a new server test in `TestServer`)

**Interfaces:**
- Produces: `uri_to_path(uri: str) -> Path` unchanged in signature; `file:///c%3A/x/y.ddd.json` now names the same file as `file:///C:/x/y.ddd.json` (on Windows an absolute `WindowsPath`).

- [ ] **Step 1: Write the failing tests**

Add to `class TestRanges` in `tests/test_lsp.py`, after `test_a_uri_still_decodes_the_escaping_a_client_applies`:

```python
    @pytest.mark.parametrize("spelling", ["c%3A", "C%3A", "c:", "C:"])
    def test_the_drive_spellings_a_windows_client_sends_name_one_file(self, spelling: str) -> None:
        """VS Code sends ``file:///c%3A/...``: a lower-case drive with the colon escaped.

        ``url2pathname`` looks for a literal colon before it unquotes, so the escaped one was
        read as no drive at all, and the path came back relative - ``/c:/git/x`` - which names
        no file and cannot be turned back into a uri. The server died on the first didOpen.
        """
        decoded = uri_to_path(f"file:///{spelling}/git/x/a.ddd.json")
        assert decoded == uri_to_path("file:///C:/git/x/a.ddd.json")
        if os.name == "nt":
            assert decoded.is_absolute()
            # ``as_uri`` keeps the drive letter's case, so compare case-blind.
            assert decoded.as_uri().lower() == "file:///c:/git/x/a.ddd.json"
```

Add `import os` to the imports of `tests/test_lsp.py`.

Add to `class TestServer` (find it with `grep -n "^class TestServer" tests/test_lsp.py`; put the test right after the class docstring, before the first test, using the helpers `framed`, `sent`, `published` and the fixtures `project`, `component`, `declare`, `write_tree` the module already imports):

```python
    def test_a_document_opened_under_the_clients_spelling_of_its_uri_is_analysed(
        self, tmp_path: Path
    ) -> None:
        """The uri a client sends is not the one ``Path.as_uri()`` writes.

        VS Code on Windows opens ``file:///c%3A/...``; read as a relative path, the server
        analysed a file that does not exist and then exited trying to publish under it. The
        answer has to be diagnostics for the real file, under a uri naming that file, and a
        server that is still running afterwards.
        """
        write_tree(
            tmp_path,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("input", "X")),
            },
        )
        path = tmp_path / "a.ddd.json"
        # The client's spelling: the drive lower-cased and its colon escaped. Without a drive
        # (posix) there is nothing to respell and the uri is the server's own.
        spelled = re.sub(
            r"^file:///([A-Za-z]):", lambda m: f"file:///{m.group(1).lower()}%3A", path.as_uri()
        )
        stream = framed(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"rootUri": spelled.rsplit("/", 1)[0]}},
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didOpen",
                "params": {"textDocument": {"uri": spelled, "languageId": "json", "version": 1, "text": path.read_text(encoding="utf-8")}},
            },
            {"jsonrpc": "2.0", "id": 2, "method": "shutdown"},
            {"jsonrpc": "2.0", "method": "exit"},
        )
        writer = io.BytesIO()
        assert Server(stream, writer, root=tmp_path).run() == 0
        findings = published(writer)["a.ddd.json"]
        assert [finding["code"] for finding in findings] == ["missing-producer"]
        assert [uri_to_path(m["params"]["uri"]).resolve() for m in sent(writer) if m.get("method") == "textDocument/publishDiagnostics"] == [path.resolve()]
```

(`missing-producer` is reported because the project declares `X` as an input nobody produces; with a build record absent the file is found through the containing project `project.ddd.json`, which is what makes the whole-project check run.)

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_lsp.py -k "drive_spellings or clients_spelling" --no-cov -q`
Expected: on Windows the four parametrised cases fail on `decoded == uri_to_path("file:///C:/...")` for the two `%3A` spellings, and the server test fails with `ValueError: relative path can't be expressed as a file URI` (or an assertion on the published uri). On Linux the `%3A` cases pass trivially; that is fine.

- [ ] **Step 3: Implement**

Replace `uri_to_path` in `src/ddd/lsp/server.py` with:

```python
_ESCAPED_DRIVE: Final = re.compile(r"^/([A-Za-z])%3[Aa](?=/|$)")
"""``/c%3A/...``: a drive letter whose colon the client escaped, which VS Code always does."""


def uri_to_path(uri: str) -> Path:
    """The file a ``file://`` uri names, undoing the escaping a client applies to it.

    ``url2pathname`` unescapes on its way, so nothing may unescape before it: doing both
    decoded a percent sequence twice and named a different file, which made this the inverse
    of ``Path.as_uri()`` for every path except the ones that actually needed escaping. A
    document called ``a%20b.ddd.json`` came back as ``a b.ddd.json``, and the diagnostics
    published for it went out under a uri the client could match to nothing on screen.

    The one exception is the drive colon. ``Path.as_uri()`` writes ``file:///C:/...`` and
    VS Code sends ``file:///c%3A/...``, and ``url2pathname`` decides whether there is a drive
    by looking for a literal colon *before* it unquotes - so the escaped spelling was read as
    no drive at all and came back as the relative path ``/c:/...``, which names no file and
    cannot be turned back into a uri. The server died on the first document a Windows client
    opened. Only that colon is restored here; everything else stays escaped for the call.
    """
    parsed = urlparse(uri)
    path = url2pathname(_ESCAPED_DRIVE.sub(r"/\1:", parsed.path))
    if parsed.netloc and parsed.netloc != "localhost":
        # file://server/share/...: a network share, whose host is the start of the path.
        path = f"//{parsed.netloc}{path}"
    return Path(path)
```

Add `import re` to the module's imports (keep them sorted; ruff's isort rule `I` is enabled).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_lsp.py -k "TestRanges or TestServer or TestUriHosts or TestWorkspaceFolders" --no-cov -q`
Expected: all pass, including the existing round-trip and UNC tests.

- [ ] **Step 5: Commit and push**

```bash
git add src/ddd/lsp/server.py tests/test_lsp.py
git commit -m "decode the drive colon a windows client escapes in a file uri" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push -u origin fix/lsp-windows-uris-and-buffers
```

---

### Task 2: Keep the text of every open document and read positions from it

**Files:**
- Modify: `src/ddd/lsp/server.py` (module docstring, `Server.__init__`, `_handle`, `_capabilities`, every handler that builds a `cache`)
- Test: `tests/test_lsp.py` (`TestServer`)

**Interfaces:**
- Produces on `Server`: `self._open: dict[Path, tuple[str, int | None]]` keyed by the resolved path (text, version); `Server._cache() -> dict[Path, Document]` seeded with one `Document` per open document under both its resolved path and the path the client spelled; `Server._version_of(path: Path) -> int | None`.
- Produces on the wire: `textDocumentSync.change` is `1` (full content); the server accepts `textDocument/didChange` and `textDocument/didClose`.

- [ ] **Step 1: Write the failing tests**

Add to `class TestServer`:

```python
    def test_a_position_is_read_from_the_editors_buffer_not_the_disk(self, tmp_path: Path) -> None:
        """The client applies an edit to what is on screen, so that is what the edit must be
        computed against. The disk is what the *analysis* reads - that promise stays - but a
        rename computed from a stale file and applied to a buffer with one extra line rewrote
        five characters of an unrelated line."""
        write_tree(
            tmp_path,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed")),
                "b.ddd.json": component("B", declare("input", "Speed")),
            },
        )
        disk = (tmp_path / "b.ddd.json").read_text(encoding="utf-8")
        on_disk = Document(disk).text_range_of("component.interface[0].definition.name")
        assert on_disk is not None
        # The unsaved buffer: one blank line inserted at the top, nothing else changed.
        buffer = "\n" + disk
        in_buffer = {"line": on_disk["start"]["line"] + 1, "character": on_disk["start"]["character"]}
        uri = (tmp_path / "b.ddd.json").as_uri()
        stream = framed(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"rootUri": tmp_path.as_uri()}},
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didOpen",
                "params": {"textDocument": {"uri": uri, "languageId": "json", "version": 3, "text": buffer}},
            },
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "textDocument/prepareRename",
                "params": {"textDocument": {"uri": uri}, "position": in_buffer},
            },
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "textDocument/rename",
                "params": {"textDocument": {"uri": uri}, "position": in_buffer, "newName": "Velocity"},
            },
            {"jsonrpc": "2.0", "id": 4, "method": "shutdown"},
            {"jsonrpc": "2.0", "method": "exit"},
        )
        writer = io.BytesIO()
        assert Server(stream, writer, root=tmp_path).run() == 0
        answers = {m["id"]: m for m in sent(writer) if "id" in m}
        # prepareRename answers at the buffer's line, and the placeholder is the name there.
        assert answers[2]["result"]["placeholder"] == "Speed"
        assert answers[2]["result"]["range"]["start"]["line"] == in_buffer["line"]
        edits = answers[3]["result"]["changes"]
        # b.ddd.json is edited where the buffer has the name, one line below the disk.
        edit_in_b = edits[uri][0]
        assert edit_in_b["range"]["start"]["line"] == on_disk["start"]["line"] + 1
        assert edit_in_b["newText"] == "Velocity"
        # a.ddd.json is not open, so its edit is computed from the disk.
        on_disk_a = Document((tmp_path / "a.ddd.json").read_text(encoding="utf-8")).text_range_of(
            "component.interface[0].definition.name"
        )
        assert edits[(tmp_path / "a.ddd.json").as_uri()][0]["range"] == on_disk_a

    def test_a_change_notification_replaces_the_buffer_and_a_close_forgets_it(self, tmp_path: Path) -> None:
        write_tree(
            tmp_path,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "Speed")),
            },
        )
        disk = (tmp_path / "a.ddd.json").read_text(encoding="utf-8")
        on_disk = Document(disk).text_range_of("component.interface[0].definition.name")
        assert on_disk is not None
        uri = (tmp_path / "a.ddd.json").as_uri()
        two_lines_down = {"line": on_disk["start"]["line"] + 2, "character": on_disk["start"]["character"]}
        stream = framed(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"rootUri": tmp_path.as_uri()}},
            {"jsonrpc": "2.0", "method": "textDocument/didOpen", "params": {"textDocument": {"uri": uri, "languageId": "json", "version": 1, "text": disk}}},
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didChange",
                "params": {"textDocument": {"uri": uri, "version": 2}, "contentChanges": [{"text": "\n\n" + disk}]},
            },
            {"jsonrpc": "2.0", "id": 2, "method": "textDocument/prepareRename", "params": {"textDocument": {"uri": uri}, "position": two_lines_down}},
            {"jsonrpc": "2.0", "method": "textDocument/didClose", "params": {"textDocument": {"uri": uri}}},
            {"jsonrpc": "2.0", "id": 3, "method": "textDocument/prepareRename", "params": {"textDocument": {"uri": uri}, "position": two_lines_down}},
            {"jsonrpc": "2.0", "id": 4, "method": "shutdown"},
            {"jsonrpc": "2.0", "method": "exit"},
        )
        writer = io.BytesIO()
        assert Server(stream, writer, root=tmp_path).run() == 0
        answers = {m["id"]: m for m in sent(writer) if "id" in m}
        assert answers[2]["result"]["placeholder"] == "Speed"  # the changed buffer
        assert answers[3]["result"] is None  # closed: the disk again, where that line is not a name

    def test_the_server_asks_for_the_full_text_on_every_change(self, tmp_path: Path) -> None:
        stream = framed(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"rootUri": tmp_path.as_uri()}},
            {"jsonrpc": "2.0", "method": "exit"},
        )
        writer = io.BytesIO()
        Server(stream, writer, root=tmp_path).run()
        sync = sent(writer)[0]["result"]["capabilities"]["textDocumentSync"]
        assert sync == {"openClose": True, "change": 1, "save": True}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_lsp.py -k "editors_buffer or replaces_the_buffer or full_text_on_every_change" --no-cov -q`
Expected: three failures (the prepareRename at the buffer's line answers `null`, the sync kind is `0`).

- [ ] **Step 3: Implement**

In `src/ddd/lsp/server.py`:

1. Module docstring: replace the last paragraph ("Only ``didOpen`` and ``didSave`` refresh...") with:

```
Only ``didOpen`` and ``didSave`` refresh. Nothing is analysed per keystroke: the analysis
reads the files from disk, so the editor and the server agree exactly at the moment of a
save, and a half-typed document never produces a screenful of findings about a mistake
nobody has finished making yet. The *text* of every open document is nonetheless kept, and
kept current through ``didChange``: a position the client sends, and an edit the client
will apply, are about what is on screen, and an edit computed from a stale file and applied
to a buffer with one extra line rewrote an unrelated line.
```

2. Add the constants beside `_REFRESHING`:

```python
_DID_OPEN: Final = "textDocument/didOpen"
_DID_CHANGE: Final = "textDocument/didChange"
_DID_CLOSE: Final = "textDocument/didClose"
```

3. In `Server.__init__`, after `self._projects`:

```python
        self._open: dict[Path, tuple[str, int | None]] = {}
        """The text and version of every open document, keyed by its resolved path.

        What positions and edits are computed against. The analysis still reads the disk - a
        finding is about what is saved - but a rename box opens where the caret is, and the
        edit that follows is applied to the buffer, so both have to be read from it.
        """
```

4. In `_handle`, before the `elif method in _REFRESHING:` branch, insert handling so that `didOpen` remembers before refreshing:

```python
        elif method == _DID_OPEN:
            self._remember(message)
            self.refresh(self._document(message))
        elif method == _DID_CHANGE:
            self._remember(message)
        elif method == _DID_CLOSE:
            self._open.pop(self._document(message).resolve(), None)
```

and keep `elif method in _REFRESHING:` for `didSave` (leave `_REFRESHING` as it is; `didOpen` is now matched by its own branch first).

5. Add the methods after `_document`:

```python
    def _remember(self, message: dict[str, Any]) -> None:
        """Keep what the client says the document now contains.

        ``didOpen`` carries the whole text; ``didChange`` carries it too, because the server
        asks for full-content synchronisation (``change: 1``): a description file is small,
        and applying incremental edits to a kept copy is a second place to get a position
        wrong. A notification without text - a client that sends none - leaves the disk copy
        in charge, which is what the server did for everything before it kept buffers.
        """
        params = _field(message.get("params"), dict, "params")
        target = _field(params.get("textDocument"), dict, "params.textDocument")
        path = uri_to_path(_field(target.get("uri"), str, "params.textDocument.uri")).resolve()
        version = target.get("version")
        text = target.get("text")
        changes = params.get("contentChanges")
        if isinstance(changes, list) and changes and isinstance(changes[-1], dict):
            text = changes[-1].get("text")
        if isinstance(text, str):
            self._open[path] = (text, version if isinstance(version, int) else None)

    def _cache(self, path: Path | None = None) -> dict[Path, Document]:
        """A document cache seeded with every open buffer, under both spellings of its path.

        The index is built from resolved paths and a request names the path the client
        spelled, so the buffer is filed under both; anything not open is read from disk on
        first use, as before.
        """
        cache: dict[Path, Document] = {}
        for resolved, (text, _) in self._open.items():
            cache[resolved] = Document(text)
        if path is not None and path.resolve() in cache:
            cache[path] = cache[path.resolve()]
        return cache

    def _version_of(self, path: Path) -> int | None:
        """The version the client last announced for a document, or ``None`` if it is not open."""
        entry = self._open.get(path.resolve())
        return entry[1] if entry is not None else None
```

6. Replace every `cache: dict[Path, Document] = {}` and `read(path, {})` in `_navigate`, `_hover`, `_prepare_rename`, `_answer_rename`, `_actions` with `cache = self._cache(path)` followed by `document = read(path, cache)`. (`_hover` and `_prepare_rename` currently call `read(path, {})`; both become `read(path, self._cache(path))`.)

7. In `_capabilities`, change the comment and the sync kind:

```python
            # change 1 is TextDocumentSyncKind.Full: the analysis reads from disk on open and
            # save, but positions and edits are computed against the buffer, so the server
            # has to be told what the buffer holds. Full rather than incremental because a
            # description file is small and applying deltas is a second place to be wrong.
            "capabilities": {
                "textDocumentSync": {"openClose": True, "change": 1, "save": True},
```

8. `_forget` docstring: leave; the buffers are not forgotten there (they are the client's truth, not the disk's).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_lsp.py --no-cov -q --deselect tests/test_lsp.py::TestSymlinkedWorkspace`
Expected: all pass. If an existing test asserts `"change": 0`, update it to `1` (search `"change": 0` in `tests/test_lsp.py`).

- [ ] **Step 5: Commit and push**

```bash
git add src/ddd/lsp/server.py tests/test_lsp.py
git commit -m "read positions and edits from the editor's buffer rather than the disk" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push
```

---

### Task 3: An edit is skipped where a drifted buffer no longer names the subject

**Files:**
- Modify: `src/ddd/lsp/navigation.py:450-464` (`rename_edits`)
- Modify: `src/ddd/lsp/edits.py` (the reads of other files' sites in `_missing`, `_adopt`, `_from_producer`, `_remove_here`, `_remove_elsewhere`, `_propagate`)
- Test: `tests/test_lsp.py`

**Interfaces:**
- Produces: `edits._at_site(site: Site, name: str, cache: dict[Path, Document]) -> Document | None`.

The index the server answers from is built from the files on disk, so a site's pointer (`component.interface[0]...`) describes the disk. An open buffer may have a declaration inserted above, in which case the same pointer names a different declaration in the buffer. An edit computed at that pointer would land on the wrong object; a skipped edit is the honest answer.

- [ ] **Step 1: Write the failing tests**

Add to `class TestServer`:

```python
    def test_a_rename_skips_a_buffer_where_the_pointer_no_longer_names_the_object(self, tmp_path: Path) -> None:
        """The index describes the disk; a buffer with a declaration inserted above has the
        object one entry further down. Editing at the disk's pointer would rename whatever now
        sits there, so that file is left alone rather than rewritten wrong."""
        write_tree(
            tmp_path,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed")),
                "b.ddd.json": component("B", declare("input", "Speed")),
            },
        )
        a_uri = (tmp_path / "a.ddd.json").as_uri()
        b_uri = (tmp_path / "b.ddd.json").as_uri()
        a_disk = (tmp_path / "a.ddd.json").read_text(encoding="utf-8")
        at_name = Document(a_disk).text_range_of("component.interface[0].definition.name")
        assert at_name is not None
        # B's buffer gained a declaration in front of the one the index knows.
        drifted = json.dumps(component("B", declare("input", "Other"), declare("input", "Speed")), indent=2)
        stream = framed(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"rootUri": tmp_path.as_uri()}},
            {"jsonrpc": "2.0", "method": "textDocument/didOpen", "params": {"textDocument": {"uri": b_uri, "languageId": "json", "version": 1, "text": drifted}}},
            {"jsonrpc": "2.0", "id": 2, "method": "textDocument/rename", "params": {"textDocument": {"uri": a_uri}, "position": at_name["start"], "newName": "Velocity"}},
            {"jsonrpc": "2.0", "id": 3, "method": "shutdown"},
            {"jsonrpc": "2.0", "method": "exit"},
        )
        writer = io.BytesIO()
        assert Server(stream, writer, root=tmp_path).run() == 0
        answer = next(m for m in sent(writer) if m.get("id") == 2)
        changes = answer["result"]["changes"]
        assert a_uri in changes
        assert b_uri not in changes, "the drifted buffer would have had 'Other' renamed"
```

And for the reconcile actions (uses the same drift; the propagate action from A must not touch B's first declaration):

```python
    def test_a_quick_fix_skips_a_buffer_where_the_pointer_no_longer_names_the_object(self, tmp_path: Path) -> None:
        write_tree(
            tmp_path,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed", unit="rpm")),
                "b.ddd.json": component("B", declare("input", "Speed", unit="Hz")),
            },
        )
        a_uri = (tmp_path / "a.ddd.json").as_uri()
        b_uri = (tmp_path / "b.ddd.json").as_uri()
        a_disk = (tmp_path / "a.ddd.json").read_text(encoding="utf-8")
        at_unit = Document(a_disk).range_of("component.interface[0].definition.unit")
        drifted = json.dumps(component("B", declare("input", "Other", unit="Hz"), declare("input", "Speed", unit="Hz")), indent=2)
        stream = framed(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"rootUri": tmp_path.as_uri()}},
            {"jsonrpc": "2.0", "method": "textDocument/didOpen", "params": {"textDocument": {"uri": b_uri, "languageId": "json", "version": 1, "text": drifted}}},
            {"jsonrpc": "2.0", "id": 2, "method": "textDocument/codeAction", "params": {"textDocument": {"uri": a_uri}, "range": at_unit, "context": {"diagnostics": []}}},
            {"jsonrpc": "2.0", "id": 3, "method": "shutdown"},
            {"jsonrpc": "2.0", "method": "exit"},
        )
        writer = io.BytesIO()
        assert Server(stream, writer, root=tmp_path).run() == 0
        answer = next(m for m in sent(writer) if m.get("id") == 2)
        for action in answer["result"]:
            assert b_uri not in action["edit"].get("changes", {}), action["title"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_lsp.py -k "no_longer_names" --no-cov -q`
Expected: both fail with an edit present for `b_uri`.

- [ ] **Step 3: Implement**

In `src/ddd/lsp/navigation.py`, `rename_edits`:

```python
    subject = renameable_at(document, pointer)
    changes: dict[str, list[dict[str, Any]]] = {}
    for site in rename_sites(built, *subject) if subject is not None else ():
        target = read(site.path, cache)
        if target.value_at(site.pointer) != subject[1]:
            # The index describes the disk; an open buffer may have moved the declaration.
            # Editing at the old pointer would rename whatever now sits there.
            continue
        span = target.text_range_of(site.pointer)
        if span is not None:
            changes.setdefault(site.path.as_uri(), []).append({"range": span, "newText": name})
    return changes
```

(Confirm with `sed -n '384,420p' src/ddd/lsp/navigation.py` that `renameable_at` returns `(kind, name)` and that a rename site's pointer points at the string holding the name - for a variable its `definition.name`, for a reference the reference key, for a type its `name` or a `typename`, for a constant its `name` or a dimension entry - so `value_at(site.pointer)` is the spelled name in every case.)

In `src/ddd/lsp/edits.py`, add after `interface_keys`:

```python
def _at_site(site: Site, name: str, cache: dict[Path, Document]) -> Document | None:
    """The document a site lies in, provided the site still names the object there.

    The index is built from the files on disk and a site's pointer describes them; an open
    buffer may have a declaration inserted above, after which the same pointer names a
    different object. Reading a value from there, or inserting one, would reconcile the
    wrong declaration - so a site that has drifted is treated as absent.
    """
    document = read(site.path, cache)
    return document if document.value_at(f"{site.pointer}.name") == name else None
```

Then in each of `_missing`, `_adopt`, `_from_producer`, `_remove_here`, `_remove_elsewhere` and `_propagate`, replace every `read(site.path, cache)` (and `read(producer.path, cache)`) over another declaration's site with `_at_site(site, name, cache)`, skipping the site when it returns `None`. Read those six functions in full first (`sed -n '249,522p' src/ddd/lsp/edits.py`); each already receives `name`. Keep the reads of `document` (the file the request is about) as they are: that document *is* the buffer.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_lsp.py --no-cov -q --deselect tests/test_lsp.py::TestSymlinkedWorkspace`
Expected: all pass.

- [ ] **Step 5: Commit and push**

```bash
git add src/ddd/lsp/navigation.py src/ddd/lsp/edits.py tests/test_lsp.py
git commit -m "leave a buffer alone where the index's pointer no longer names the object" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push
```

---

### Task 4: Answer edits as versioned document changes where the client supports them

**Files:**
- Modify: `src/ddd/lsp/server.py` (`_initialise`, `_answer_rename`, `_actions`, new `_workspace_edit`)
- Test: `tests/test_lsp.py`

**Interfaces:**
- Produces: `Server._workspace_edit(changes: dict[str, list[dict[str, Any]]]) -> dict[str, Any]`: `{"documentChanges": [{"textDocument": {"uri", "version"}, "edits": [...]}, ...]}` when the client announced `capabilities.workspace.workspaceEdit.documentChanges`, else `{"changes": changes}` as today. The version is the one the client last announced for an open document and `null` for a document that is not open.

- [ ] **Step 1: Write the failing test**

Add to `class TestServer`:

```python
    def test_a_client_that_takes_versioned_edits_is_told_which_version_they_are_for(self, tmp_path: Path) -> None:
        """Without a version the client applies the edit to whatever the buffer holds by the
        time it arrives; with one it refuses an edit computed for a text it no longer has."""
        write_tree(
            tmp_path,
            {
                "project.ddd.json": project("P", "a.ddd.json", "b.ddd.json"),
                "a.ddd.json": component("A", declare("output", "Speed")),
                "b.ddd.json": component("B", declare("input", "Speed")),
            },
        )
        a_uri = (tmp_path / "a.ddd.json").as_uri()
        b_uri = (tmp_path / "b.ddd.json").as_uri()
        b_text = (tmp_path / "b.ddd.json").read_text(encoding="utf-8")
        at_name = Document((tmp_path / "a.ddd.json").read_text(encoding="utf-8")).text_range_of("component.interface[0].definition.name")
        assert at_name is not None
        stream = framed(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"rootUri": tmp_path.as_uri(), "capabilities": {"workspace": {"workspaceEdit": {"documentChanges": True}}}}},
            {"jsonrpc": "2.0", "method": "textDocument/didOpen", "params": {"textDocument": {"uri": b_uri, "languageId": "json", "version": 7, "text": b_text}}},
            {"jsonrpc": "2.0", "id": 2, "method": "textDocument/rename", "params": {"textDocument": {"uri": a_uri}, "position": at_name["start"], "newName": "Velocity"}},
            {"jsonrpc": "2.0", "id": 3, "method": "shutdown"},
            {"jsonrpc": "2.0", "method": "exit"},
        )
        writer = io.BytesIO()
        assert Server(stream, writer, root=tmp_path).run() == 0
        answer = next(m for m in sent(writer) if m.get("id") == 2)
        assert "changes" not in answer["result"]
        versions = {change["textDocument"]["uri"]: change["textDocument"]["version"] for change in answer["result"]["documentChanges"]}
        assert versions == {a_uri: None, b_uri: 7}
        assert all(change["edits"] for change in answer["result"]["documentChanges"])
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_lsp.py -k "versioned_edits" --no-cov -q`
Expected: fails on `"changes" not in answer["result"]`.

- [ ] **Step 3: Implement**

In `Server.__init__` add `self._versioned_edits = False` with the docstring `"""Whether the client takes ``documentChanges``, which carry the version an edit is for."""`.

In `_initialise`, after the folders:

```python
        capabilities = params.get("capabilities")
        workspace = capabilities.get("workspace") if isinstance(capabilities, dict) else None
        edit = workspace.get("workspaceEdit") if isinstance(workspace, dict) else None
        self._versioned_edits = isinstance(edit, dict) and edit.get("documentChanges") is True
```

Add the method:

```python
    def _workspace_edit(self, changes: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
        """The edits in the shape the client asked for.

        ``documentChanges`` names, for each file, the version of the text the edit was
        computed against, so a client that has typed since refuses the edit instead of
        applying it to a text it was not meant for. A document that is not open has no
        version, which the protocol spells ``null``. The plain ``changes`` form stays for a
        client that did not announce the other, because it is the only one it can apply.
        """
        if not self._versioned_edits:
            return {"changes": changes}
        return {
            "documentChanges": [
                {
                    "textDocument": {"uri": uri, "version": self._version_of(uri_to_path(uri))},
                    "edits": edits,
                }
                for uri, edits in changes.items()
            ]
        }
```

In `_answer_rename`, the final line becomes `write_message(self.writer, response(request_id, self._workspace_edit(changes)))`.

In `_actions`, after `offered.extend(...)`, convert every action's edit: 

```python
        for action in offered:
            action["edit"] = self._workspace_edit(action["edit"]["changes"])
        return offered
```

(Every action `edits.py` builds carries `"edit": {"changes": {...}}`; confirm with `grep -n '"edit"' src/ddd/lsp/edits.py`.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_lsp.py --no-cov -q --deselect tests/test_lsp.py::TestSymlinkedWorkspace`
Expected: all pass (the existing tests do not announce the capability, so they keep receiving `changes`).

- [ ] **Step 5: Commit and push**

```bash
git add src/ddd/lsp/server.py tests/test_lsp.py
git commit -m "tell a client which version of a document an edit was computed for" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push
```

---

### Task 5: State the trust boundary and decline an untrusted workspace

**Files:**
- Modify: `editors/vscode/package.json`
- Modify: `docs/editor_integration.rst`, `editors/vscode/README.md`, `docs/plugins.rst`, `SPEC.md`
- Test: `tests/test_documentation.py` (`TestPackaging`)

- [ ] **Step 1: Write the failing test**

Add to `class TestPackaging` in `tests/test_documentation.py`:

```python
    def test_the_extension_declines_an_untrusted_workspace_and_the_pages_say_why(self) -> None:
        """A description file names the plugins the server runs, and the server runs the
        plugins of every project it finds above an opened file. Opening a repository is
        therefore running its python, which VS Code's workspace trust exists to gate: the
        manifest has to opt out of restricted mode, and the reader has to be told."""
        manifest = json.loads(
            (ROOT / "editors" / "vscode" / "package.json").read_text(encoding="utf-8")
        )
        assert manifest["capabilities"]["untrustedWorkspaces"]["supported"] is False
        for page in (
            ROOT / "docs" / "editor_integration.rst",
            ROOT / "editors" / "vscode" / "README.md",
            ROOT / "docs" / "plugins.rst",
            ROOT / "SPEC.md",
        ):
            text = page.read_text(encoding="utf-8").lower()
            assert "trust" in text and "plugin" in text, f"{page.name} does not state the trust boundary"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_documentation.py -k untrusted --no-cov -q`
Expected: fails with `KeyError: 'capabilities'`.

- [ ] **Step 3: Implement**

`editors/vscode/package.json`: after `"activationEvents"`, add

```json
  "capabilities": {
    "untrustedWorkspaces": {
      "supported": false,
      "description": "A description file names the plugins the DDD language server runs, so the server only starts in a workspace you trust."
    }
  },
```

`docs/editor_integration.rst`: after the section "Which project a file belongs to" (before "VS Code"), add:

```
What the server runs
--------------------

A project names its :doc:`plugins <plugins>` in its description, and the server runs the
plugins of every project it analyses: the ones the build records name, and the ones lying
above an opened file that turn out to include it. Opening a description file in a checked
out repository is therefore running the python that repository ships, exactly as ``ddd
check`` on it would - the difference is that nobody typed the command. Open a repository in
the editor only when you would run its build. The VS Code extension declines a workspace
that has not been trusted (VS Code's *Restricted Mode*), so the server starts only once you
have said so; an editor that launches the server itself has to make the same decision.
```

`editors/vscode/README.md`: after the "Requirements" section, add:

```
## Trust

A description file names the plugins the server runs, and the server runs the plugins of
every project it finds above a file you open. Opening a repository is therefore running its
python, the way `ddd check` on it would. The extension does not start in a workspace VS Code
has not been told to trust (*Restricted Mode*): trust the workspace when you would run its
build, and not before.
```

`docs/plugins.rst`: find the paragraph saying a module is imported once per process (`grep -n "once per process" docs/plugins.rst`) and add after it:

```
Naming a plugin runs it. That is true of every ``ddd`` command on the project, and of the
language server, which runs the plugins of every project it analyses when a file is opened
or saved; the :doc:`editor page <editor_integration>` says what that means for a repository
you did not write.
```

`SPEC.md` 3.11: after the sentence ending "the hooks run in the order the project files name the plugins, a module named twice keeping its first place." (inside the `"plugins"` bullet), add: `Naming a plugin runs its module: on every command over the project, and in the language server whenever a file of the project is opened or saved ([section 7.2](#72-editor-integration)).`

`SPEC.md` 7.2, last paragraph: replace

```
An editor extension **shall** do no more than launch the server and point it at the build
directories: everything a reader sees is the tool's answer, so that an editor DDD ships
nothing for is not at a disadvantage.
```

with

```
An editor extension **shall** do no more than launch the server and point it at the build
directories: everything a reader sees is the tool's answer, so that an editor DDD ships
nothing for is not at a disadvantage. It **shall** launch the server only in a workspace the
reader has trusted, where the editor has such a notion: the server runs the plugins of every
project it analyses ([section 3.11](#311-plugins)), so opening a repository is running its
python, and that is a decision the reader makes, not the extension.
```

`CHANGELOG.md`, under `## Unreleased`, three bullets at the top:

```
* **The language server decodes the uri VS Code sends on Windows.**  A client spells a
  Windows file as `file:///c%3A/...`, drive lower-cased and colon escaped, and the server read
  that as the relative path `/c:/...`: it analysed a file that does not exist and exited on
  the first `didOpen`, trying to publish under a uri it could not form.  The escaped drive
  colon is now restored before the path is decoded, and the extension works on Windows.

* **Edits are computed against the editor's buffer.**  Rename and the quick fixes read
  positions from, and wrote edits for, the file on disk, while the client applies an edit to
  what is on screen; one unsaved line above a declaration was enough to rewrite an unrelated
  line.  The server now keeps the text of every open document (`textDocumentSync.change` is
  `1`, full content), computes positions and edits against it, leaves a file alone where an
  open buffer has moved the declaration the index knew, and answers a client that takes
  `documentChanges` with the version each edit was computed for.  The analysis still reads
  the disk on open and save, as before.

* **Opening a repository runs its plugins, and the pages now say so.**  A description names
  the plugins the server runs, and the server runs the plugins of every project it finds above
  an opened file.  The VS Code extension declines a workspace that has not been trusted
  (Restricted Mode), and the editor page, the extension's README, the plugins page and the
  specification state the boundary.
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_documentation.py --no-cov -q`
Expected: all pass (this file also checks the spec's anchors and table of contents; no heading was added to `SPEC.md`, so nothing else moves).

- [ ] **Step 5: Full verification and final commit**

Run, from the repository root:
- `python -m pytest` (expect only the 12 known environmental failures; coverage 100%)
- `<venv>/Scripts/python.exe -m ruff check .`, `-m ruff format --check .`, `-m mypy`

```bash
git add editors/vscode/package.json docs/editor_integration.rst editors/vscode/README.md docs/plugins.rst SPEC.md CHANGELOG.md tests/test_documentation.py
git commit -m "say that opening a repository runs its plugins, and decline an untrusted workspace" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push
```
