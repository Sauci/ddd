# The Security Review of the GUI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `ddd gui` answers only its own page and only well-formed requests. A page served from another port of `127.0.0.1` is refused before any handler runs. No query value can make a route answer 500. The server cannot be made to spawn threads without bound. The token never reaches a command line. A `SECURITY.md` and a security page say what is defended and what is trusted.

**Architecture:**
- **One gate in the request handler.** It checks the Host, then where the request came from (`Sec-Fetch-Site`, `Origin`), then the cookie, then a `POST`'s rules, before routing.
- **One route table in the API.** Every route is a record with a strict pydantic model for its query, and the dispatcher validates the query before any handler runs, so handlers parse nothing by hand. Shared value types do the parsing: a whole number, a path, JSON text, a name.
- **One semaphore in the server.** It caps concurrent connections, refusing past the cap from the accepting thread itself.
- **A private launch file.** The browser is opened on a private `file://` page that refreshes to the address, and `/open` answers with a page that refreshes to the project.

**Tech Stack:**
- **Server:** Python 3.14, the standard library's `http.server` and `ThreadingHTTPServer`, pydantic v2 (strict models, `Annotated` value types), pytest at 100 % line and branch.
- **Page:** React 19 + TypeScript, its API types generated from pydantic's schema, Vitest at 100 % over `src/api`, `src/lib` and `src/state`.
- **Around it:** Playwright journeys, Ladle stories with Docker screenshot references, and Sphinx docs under `-W`.

**Spec:** `docs/superpowers/specs/2026-10-05-gui-security-design.md`. Read it before any task. Where this plan departs from it, the departure is a ruling in *Rulings taken* at the end, with its reason.

## Global Constraints

Every task's requirements include this section.

**Running things**

- **Interpreters.** There is no `python` on PATH: always use `.venv/bin/python`. Node is not on PATH either; it is at `~/.local/node-v24.21.0/bin`.
- **Never add `-q` to pytest.** `pyproject.toml` already sets it in `addopts`. A second one removes the `N passed` line while pytest-cov still prints its coverage line, so the output looks fine and says nothing.
- **A pipeline reports its last command's exit status.** Capture each tool's own: `.venv/bin/python -m pytest > gate.txt 2>&1; echo "EXIT=$?"; tail -3 gate.txt`. A run that finished ends with its **summary line**; a tail ending in a stack trace did not finish, whatever the exit code says.
- **A stale `.coverage` file.** Once it made pytest answer `4445 passed` with exit 3 and **no coverage line**. If the coverage summary is missing, delete `.coverage*` (gitignored) and run again.
- **Journeys:**
  1. Run `cd gui && npm run build` first, because the journeys drive the **compiled** pages in `src/ddd/gui/static`.
  2. Then run `PLAYWRIGHT_CHANNEL=chrome DDD_PYTHON="$PWD/../.venv/bin/python" npx playwright test --output=<a path outside the repository>`. Writing `--output` inside `gui/` fails with `EACCES`.
- **Never run the journeys while the Docker screenshot run is running.** Both drive Playwright over the same `gui/` checkout, and the journeys then fail with "Playwright Test did not expect test() to be called here". Run one after the other.
- **Screenshots and docs** run from the repository root, in Docker, which cannot see the session scratchpad:
  - `UPDATE=1 docker compose run --rm gui-screenshots` rewrites the references; without `UPDATE=1` it compares.
  - `docker compose run --rm -e JAVA_TOOL_OPTIONS=-Duser.home=/tmp docs` builds the docs.
- **Page schemas:** run `cd gui && DDD=../.venv/bin/ddd DDD_PYTHON=../.venv/bin/python npm run schemas`. `gui/src/generated/` is gitignored, so grep the generated file and let `npm run typecheck` prove the page agrees.
- **Stopping a server you started.** List its PID by process name, then kill it in a **separate** command:
  1. `ps -eo pid,comm,args | awk '$2 ~ /^python/ && /<pattern>/'`
  2. `kill <pid>`

  Never `pkill -f` and never `pgrep -f`: the shell running the command holds the pattern in its own command line, so `pkill -f` kills that shell, and a `pgrep -f` wait loop never ends. Leave nothing of yours running.

**Gates**

- **Python:** `.venv/bin/python -m pytest` at **100 % line and branch**, `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, and `.venv/bin/mypy` run **bare** (it checks `src/ddd` and `tools`, strictly).
- **Page:** `npm run lint && npm run typecheck && npm test && npm run build && npm run ladle:build`, with Vitest at 100 % on statements, branches, functions **and** lines over `src/api`, `src/lib` and `src/state`.
- No `pragma: no cover`, no skips, no xfails.
- **No commit leaves a gate red.** A change to the contract lands with the page that reads it, in one commit.
- **CI runs more than the development PC does:**
  - **Python versions and runners.** Python 3.12, 3.13 and 3.14, on ubuntu **and** windows runners. On 3.12 and 3.13, coverage traces with `sys.settrace`, which spends stack on every traced call: a test that measures recursion depth must take the tracer out of what it measures (part 17's `deepest` in `tests/test_lsp.py`).
  - **Windows file locks.** Windows refuses to rename over, or delete, a file that another handle holds open (`ddd.editing.REPLACE_TRIES`).
  - **Windows path rules.** A path rule written for Windows runs for real there. On the Linux PC, it must be tested with spellings that mean the same thing on every platform.

**What the gates cannot see**

- **Some code registers no branch with coverage.py.** A conditional expression registers zero branches, and so does a comprehension filter. A short-circuit `and`/`or` inside an `if` records one branch pair for the whole `if`, not one per operand. Write statements where a branch matters.
- **A coverage gate cannot see data.** Ablate every new data value (a limit, a sentence, a header, a default) and confirm that a **named** test dies. If none does, write the one that does.
- **Ablate Python in a scratch `git worktree`, with pytest run from inside that worktree.**
  - `pyproject.toml` sets `pythonpath = ["src", "tools", "docker"]`, resolved against *rootdir* and placed ahead of any `PYTHONPATH` you export. A run started from the main repository measures the main repository: every rot "survives", and the reading is that nothing pins anything. The tell is pytest's own `rootdir:` line.
  - **Confirm one ablation kills something before trusting that another kills nothing.**
  - Before a survival is believed, run it again under `PYTHONHASHSEED=0`, `1`, `4` and `7`.
  - A `cp` into the worktree, or a `sed -i` in the same second, can leave a stale `.pyc`: set `PYTHONDONTWRITEBYTECODE=1`.
- **Ablate the page in place,** because a fresh worktree has no `node_modules`.
  - Run `git status --porcelain <file>` **immediately before every restore**, not once at the start: `git checkout -- <file>` reverts to HEAD and silently eats any fix made in that file since.
  - After each restore, grep for something you expect still to be there.
- **Never conclude what *else* pins something from a narrowed run** (no `-k`, no path argument). That is a whole-suite question; copy the summary line in rather than paraphrasing it.
- **No decision may live in a `.tsx` file.** Every judgement lives in `gui/src/lib` or `gui/src/state`, under the Vitest gate; a `src/app` hook is glue only.
- **A refusal test asserts the whole sentence with `==`.** A code and a substring leave the explanatory clause pinned by nothing. Read every expected sentence off the running code, never out of this plan.
- **A test never sleeps to coordinate.** It uses `threading.Event`s, real sockets and timeouts. Every wait passes a timeout, so that a hold that lasts too long fails the test instead of hanging the suite.
- **A journey leaves no visible window between a write and its stamp.** A file written from outside and meant to be unseen by the watcher is staged under its own times and renamed in one step (`driftMaxUnseen` in `gui/e2e/demo.ts`).

**Prose**

- **A sentence stating a measurement gets the measurement run as it is written,** against the file it names, with the exit status copied from *that* run. A sentence saying "nothing else does X" is a whole-repository claim, and gets a whole-repository grep.
- **A probe is quoted with the machine, the commit, the project and the run it came from.**
- **Cite by name, not by line number.** Line numbers in this plan were measured on master `a1da6ce`, and go stale the moment an earlier task edits the file.
- **Before ruling on a trade-off, confirm that both sides of it can actually happen.**

**Conventions**

- **Commits:** a lowercase imperative subject on **one line**, with no `feat:`-style prefix, and a body saying why. The trailer is `Co-Authored-By: <your model> <noreply@anthropic.com>`. Never `--amend`, never rebase.
- **Every UI pull request carries a screenshot of what it added,** the maintainer's standing rule. Open each new or changed reference and say what it shows, quoting from the image. "Updated N references" is not a report.
- **Subagents do not write report files;** they return findings as text.
- **If a brief or this plan is wrong, say so in your report** rather than working around it silently.

## Prerequisites

1. **The branch is `feature/gui-security`, in the main checkout.** It holds the spec (`f99d471`) and this plan, on master `a1da6ce`.
2. **Gate the tree before Task 1,** with the milestone gate's commands and each exit status captured. Every gate green there is the baseline each task is compared against.
3. **The probes of spec §2.**
   - The scripts that reproduce them are in the session scratchpad, under `sec-probe/`: a scratch `ddd gui` over a copy of `examples/demo`, driven by `curl`.
   - Task 9 runs them again as the "after" figures.

## Review Focus

These are the inputs most likely to bite that no task's happy path reaches. Each is pinned by a test in the task that owns it.

1. **The gate and the requests the suite makes itself** (Task 2).
   - **Requests that send neither header pass to the cookie.** That covers `urllib` in `tests/test_gui_server.py`, Node's `fetch` in the journeys' fixtures, `curl`, and the benchmark's in-process API.
   - **Requests from the page pass.** Its own fetches are `same-origin`, and a typed address or Playwright's `page.goto` is `none`.
   - **Everything else is refused before the cookie is read,** so the refusal answers 403 rather than 401.
2. **`/open`'s page and the cookie** (Task 1).
   - From a `file://` launch, the `SameSite=Strict` cookie must be sent with the refresh to `/project`, checked by hand in Chrome and Firefox before anything else is built.
   - The content security policy must allow `<meta http-equiv="refresh">`. It does, being no script, but the by-hand check is what proves it.
3. **Refusals the page shows** (Tasks 3 to 5). A sentence a panel shows keeps its words exactly, so no screenshot reference and no journey moves. The screenshots run in compare mode at the end of every task that touches a route.
4. **The plan routes' per-action queries** (Task 4). One model per action, chosen by `action`. An unknown action is refused with the sentence the route answers today, and a key another action takes is refused as a key this action does not take.
5. **Windows paths on the Linux PC** (Task 3).
   - **What is refused, on every platform:** `\\server\share`, `//server/share` and `\\?\` forms.
   - **What the test spells:** each form as a string, never through `Path`, whose meaning changes with the platform.
6. **The cap and the existing long-poll and keep-alive tests** (Task 6).
   - The cap counts connections, not requests: a kept-alive connection holds one slot for its whole life.
   - The refusal is written on the accepting thread, with a timeout, so a client that never reads cannot hold that thread.
   - `TestOneConnectionCarriesManyAsks` must still pass.
7. **The generated query types and the page's typecheck** (Tasks 3 to 5). A query model that names a key differently from what `client.ts` sends fails `npm run typecheck` in the same commit, never later.
8. **The marker journey's baseline plugin** (Task 8). It must run when loaded: before the gate, so the journey fails first. The comparison has to happen under the session root, as `/api/compare` requires, and the plugin file must be loaded through `project.plugins`.

## File Structure

| File | Responsibility | Tasks |
| --- | --- | --- |
| `src/ddd/gui/server.py` | **Modify.** The gate (`_from_elsewhere`, `_ELSEWHERE`); `/open`'s refresh page (`SIGNED_IN_PAGE`); the launch file (`launched`, `LAUNCH_PAGE`); the cap (`MAX_CONNECTIONS`, `GuiServer.process_request`, `BUSY`); the module docstring | 1, 2, 6, 7 |
| `src/ddd/gui/routes.py` | **Create.** A route's record: `Policy` and `Route`, and the dispatcher's query reading (`one_value_each`). `ROUTES` itself is filled in `api.py`, after `Api`, whose methods answer them | 3, 4 |
| `src/ddd/gui/queries.py` | **Create.** The shared value types (`WholeNumber`, `QueryPath`, `JsonText`, `Name`) and every route's query model | 3, 4 |
| `src/ddd/gui/api.py` | **Modify.** `Api.handle` dispatches through `ROUTES`; every handler takes its typed query; `_single`, `_integer` and the hand parsing go | 3, 4 |
| `src/ddd/gui/contract.py` | **Modify.** The query models join `_ENDPOINTS`, so that the page's generated types carry them | 3, 4 |
| `gui/src/api/client.ts` | **Modify.** The query builders take the generated query types | 3, 4 |
| `tests/test_gui_server.py` | **Modify.** The gate, `/open`'s page, the launch file, the cap | 1, 2, 6 |
| `tests/test_gui_queries.py` | **Create.** The value types, and every query model's refusals | 3, 4 |
| `tests/test_gui_hostile.py` | **Create.** The walk of hostile values over the route table | 5 |
| `tests/test_gui_api.py` | **Modify.** Refusal sentences that move from handlers into the models, kept word for word | 4 |
| `tests/test_gui_docs.py` | **Create.** The security page's route table checked against `ROUTES` | 7 |
| `SECURITY.md` | **Create.** How to report a vulnerability | 7 |
| `docs/gui_security.rst` | **Create.** The threat model, container guidance, and the route table | 7 |
| `docs/index.rst` | **Modify.** The new page in the toctree | 7 |
| `CHANGELOG.md` | **Modify.** This part's entries under `## Unreleased` | 7 |
| `gui/e2e/hostile.spec.ts` | **Create.** A page on another port cannot make `ddd gui` run a baseline's plugin | 8 |
| `gui/e2e/demo.ts` | **Modify.** The fixture project for the marker journey | 8 |

## Interfaces Between Tasks

**Task 1 produces**, in `src/ddd/gui/server.py`:
- `LAUNCH_PAGE: Final[str]`: the launch file's HTML, with one `{address}` placeholder.
- `SIGNED_IN_PAGE: Final[str]`: `/open`'s answer, with one `{target}` placeholder.
- `launched(address: str, opener: Callable[[str], object]) -> Path`: writes the launch file in a fresh private directory, hands `opener` its `file://` URI, and answers the directory, which the caller removes.
- `run()` calls `launched(server.address, webbrowser.open)` where it called `webbrowser.open(server.address)`, and removes the directory in its `finally`.

**Task 2 produces**, in `src/ddd/gui/server.py`:
- `_Handler._from_elsewhere(self) -> bool`.
- `_ELSEWHERE: Final[str]`, the sentence of a refused API request.
- A refused page answers `SIGN_IN_PAGE` with status 403.

**Task 3 produces:**
- **In `src/ddd/gui/queries.py`:**
  - `WholeNumber`, `QueryPath`, `JsonText` and `Name`: `Annotated` string types with `BeforeValidator`s. `JsonText`'s value is the parsed JSON.
  - `NoQuery`: the model of a route that takes no query.
  - `_Query`: the base of every query model; frozen, `extra="forbid"`, no `strict` (values arrive as strings).
  - The query models of the reading routes (Task 3's list).
- **In `src/ddd/gui/routes.py`:**
  - `Policy(writes: bool, opens: bool, runs_plugins: bool, waits: bool)`.
  - `Route(path: str, method: str, query: type[BaseModel], body: type[BaseModel] | None, answer: Answer, policy: Policy)`.
  - `ROUTES: Final[tuple[Route, ...]]`, in `src/ddd/gui/api.py`.
  - `one_value_each(query: Mapping[str, Sequence[str]]) -> dict[str, str] | str`: the values, or the sentence naming the first key given twice.
- **In `Api.handle`:** looks a route up, reads the query with `one_value_each`, validates it with `_validated_query(model, values)`, and calls `route.answer(self, typed, body)`.

**Task 4 consumes** Task 3's types and routes, and **produces** the query models of every remaining route, including the per-action unions of the plan routes, and handlers that read only typed queries.

**Task 5 consumes** `ROUTES` and every model's fields, through `model_fields`.

**Task 6 produces**, in `src/ddd/gui/server.py`:
- `MAX_CONNECTIONS: Final = 64`.
- `GuiServer.__init__(..., connections: int = MAX_CONNECTIONS)`.
- `BUSY: Final[str]`, the 503's sentence.

**Task 7 consumes** `ROUTES` and each route's `Policy`.

**Task 8 consumes** the gate (Task 2), and the journeys' fixtures in `gui/e2e/fixtures.ts`.

---

### Task 1: the browser launched without the token, and `/open` answering a page

**Model:** sonnet. **Files:** `src/ddd/gui/server.py`, `tests/test_gui_server.py`.

The spec's first risk comes first (§8): whether the `SameSite=Strict` cookie follows a navigation that started from a `file://` page, through `/open`'s refresh, in Chrome and in Firefox. Build `/open`'s page and the launch file, then check them by hand in both browsers **before committing**. If either browser does not arrive signed in, stop and report: the controller rules on the alternative.

- [ ] **Step 1: Write the failing tests for `/open`'s page.**

In `tests/test_gui_server.py`, change `TestSigningIn`'s three redirect tests. `/open` now answers 200 with a page that refreshes to the target, and sets the cookie:

```python
    def test_the_token_is_swapped_for_a_strict_cookie_and_the_project_page(self, server) -> None:
        response, data = ask(server, "GET", f"/open?token={server.token}", signed_in=False)
        assert response.status == 200
        assert response.getheader("Location") is None
        assert response.getheader("Set-Cookie") == (
            f"ddd-gui-{server.port}={server.token}; HttpOnly; SameSite=Strict; Path=/"
        )
        assert data == SIGNED_IN_PAGE.format(target="/project").encode("utf-8")

    def test_the_page_refreshes_to_its_target_without_a_script(self) -> None:
        """A navigation that began at a file:// page is cross-site to the browser, and a
        SameSite=Strict cookie does not follow a redirect out of it; a refresh this page makes
        is a navigation of this origin's own, which it does follow. A meta refresh, not a
        script, so the content security policy - default-src 'self' - lets it run."""
        page = SIGNED_IN_PAGE.format(target="/project")
        assert '<meta http-equiv="refresh" content="0; url=/project">' in page
        assert "<script" not in page
```

In `test_a_project_being_analysed_signs_in_to_its_own_page`, assert `(response.status, data) == (200, SIGNED_IN_PAGE.format(target="/project").encode("utf-8"))`.

In `test_without_an_open_project_the_redirect_is_to_the_start_page`, rename the test to `..._the_page_refreshes_to_the_start_page` and assert `data == SIGNED_IN_PAGE.format(target="/").encode("utf-8")`.

Import `SIGNED_IN_PAGE` from `ddd.gui.server`.

- [ ] **Step 2: Write the failing tests for the launch.**

In `TestRunning`, every test that monkeypatches `module.webbrowser.open` with `opened.append` and asserts `opened == [address]` now asserts the launch file instead. Add a helper beside `ask`:

```python
def launch_file(opened: list[str], address: str) -> Path:
    """The file a launch handed the browser: a file:// uri, holding no token, whose page
    refreshes to the address; answers its path."""
    (uri,) = opened
    assert uri.startswith("file://")
    assert "token" not in uri
    path = Path(urllib.request.url2pathname(urlsplit(uri).path))
    assert html.escape(address) in path.read_text(encoding="utf-8")
    return path
```

`test_it_prints_its_address_serves_and_exits_cleanly_when_interrupted` becomes:

```python
        if open_browser:
            page = launch_file(opened, line.rsplit(" ", 1)[1])
            assert not page.parent.exists()   # removed once the server stopped
        else:
            assert opened == []
```

Make the same change in `test_localhost_resolving_to_loopback_is_loopback` and in every other test asserting `opened == [line.rsplit(" ", 1)[1]]`. Grep for that expression, and change every hit.

Add the test of the file itself:

```python
class TestTheLaunch:
    def test_the_browser_is_handed_a_private_page_and_never_the_token(self) -> None:
        address = "http://127.0.0.1:8123/open?token=abc&x=<y>"
        opened: list[str] = []
        directory = launched(address, opened.append)
        try:
            page = launch_file(opened, address)
            assert page.parent == directory
            assert page.read_text(encoding="utf-8") == LAUNCH_PAGE.format(
                address=html.escape(address)
            )
            if os.name != "nt":
                assert stat.S_IMODE(page.stat().st_mode) == 0o600
                assert stat.S_IMODE(directory.stat().st_mode) == 0o700
        finally:
            shutil.rmtree(directory)
```

- [ ] **Step 3: Run them and watch them fail.**

```bash
.venv/bin/python -m pytest tests/test_gui_server.py -k "SigningIn or Running or Launch" -p no:cacheprovider --no-cov
```

Expected: `ImportError` for `SIGNED_IN_PAGE`, `LAUNCH_PAGE` and `launched`.

- [ ] **Step 4: Implement `/open`'s page.**

In `src/ddd/gui/server.py`, add beside `SIGN_IN_PAGE`:

```python
SIGNED_IN_PAGE: Final = (
    '<!doctype html><html lang="en"><meta charset="utf-8">'
    '<meta http-equiv="refresh" content="0; url={target}"><title>ddd gui</title>'
    '<p><a href="{target}">Open ddd gui</a></p></html>'
)
"""What ``/open`` answers once it has set the cookie: a page that refreshes to the project, or
to the start page. Not a redirect: a navigation that began at the ``file://`` page a launch
opens (:data:`LAUNCH_PAGE`) is cross-site to the browser, and a ``SameSite=Strict`` cookie does
not follow a redirect out of it, where a refresh this page makes is a navigation of this
server's own origin, which it does. A meta refresh rather than a script, so that the content
security policy lets it run."""
```

In `_sign_in`, replace the 303 with:

```python
        page = SIGNED_IN_PAGE.format(target=target).encode("utf-8")
        self._send(200, page, CONTENT_TYPES[".html"], {"Set-Cookie": cookie})
```

- [ ] **Step 5: Implement the launch file.**

Add the imports `html`, `os`, `shutil` and `tempfile`, and `Callable` from `collections.abc`. Then add:

```python
LAUNCH_PAGE: Final = (
    '<!doctype html><html lang="en"><meta charset="utf-8">'
    '<meta http-equiv="refresh" content="0; url={address}"><title>ddd gui</title>'
    '<p><a href="{address}">Open ddd gui</a></p></html>'
)
"""The page a launch hands the browser, refreshing to the address with its token."""


def launched(address: str, opener: Callable[[str], object]) -> Path:
    """Open ``address`` in a browser without putting it on a command line; answer the directory
    the page that does so was written in, which the caller removes once the server stops.

    ``webbrowser.open(address)`` starts the browser with the address as an argument, and a
    process's arguments are readable by every user of the computer, in ``/proc`` on Linux:
    the token in the address was theirs for the asking while the launch ran. The browser is
    handed instead the ``file://`` path of a page holding it, readable by its owner alone:
    the directory ``tempfile.mkdtemp`` makes is ``0o700``, and the page is created ``0o600``.
    On windows both live in the user's own temporary directory, which only that user may read
    unless someone changed it.
    """
    directory = Path(tempfile.mkdtemp(prefix="ddd-gui-"))
    page = directory / "open.html"
    descriptor = os.open(page, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as file:
        file.write(LAUNCH_PAGE.format(address=html.escape(address)))
    opener(page.as_uri())
    return directory
```

In `run()`, replace `webbrowser.open(server.address)`:

```python
        launch: Path | None = None
        if beyond_loopback:
            ...                                   # the warning, unchanged
        elif open_browser:
            launch = launched(server.address, webbrowser.open)
        try:
            with contextlib.suppress(KeyboardInterrupt):
                server.serve_forever()
        finally:
            server.server_close()
            if launch is not None:
                shutil.rmtree(launch, ignore_errors=True)
```

- [ ] **Step 6: Run the tests and the Python gate.**

Run them; they pass. Then run the whole Python gate, with every exit status captured.

- [ ] **Step 7: Check by hand in Chrome and in Firefox, before committing.**

Start a scratch server over a copy of `examples/demo` in the scratchpad. Use a scratch subclass of `_Handler`, with `log_message` restored, that also prints each request's path and whether it carried the cookie:

```python
# scratchpad/launch_probe.py - a ddd gui whose handler prints each request and its cookie.
import sys
from pathlib import Path
from ddd.gui import server as module

class Logged(module._Handler):
    def _route(self, method):
        print(method, self.path.split("?")[0], "cookie" if self._signed_in() else "no cookie",
              self.headers.get("Sec-Fetch-Site"), flush=True)
        super()._route(method)

module._Handler = Logged
sys.exit(module.run(Path(sys.argv[1]), [], 0, open_browser=True))
```

`webbrowser` opens what the `BROWSER` environment variable names, so the browser is chosen there:

```bash
BROWSER="google-chrome --headless=new --user-data-dir=<scratch>/chrome %s" .venv/bin/python <scratch>/launch_probe.py demo/demo.ddd.json
BROWSER="firefox --headless --profile <scratch>/firefox %s" .venv/bin/python <scratch>/launch_probe.py demo/demo.ddd.json
```

Run it twice from the copy's directory: once with Chrome and once with the system Firefox, each headless and in a throwaway profile. Each run must print a `GET /project cookie same-origin` line after `GET /open no cookie`. Quote both runs' lines in your report. If either browser never sends the cookie with `/project`, **do not commit**: report what each printed, and stop.

- [ ] **Step 8: Commit.**

```bash
git add src/ddd/gui/server.py tests/test_gui_server.py
git commit
```

Use the subject `open the browser on a private page, and answer /open with a page the cookie follows`. The body says why (the token on a command line, the cookie across a `file://` launch) and quotes the by-hand runs.

---

### Task 2: one gate for where a request comes from

**Model:** sonnet. **Files:** `src/ddd/gui/server.py`, `tests/test_gui_server.py`.

- [ ] **Step 1: Write the failing tests.**

In `TestWhoMayAsk`:

```python
    @pytest.mark.parametrize("site", ["same-site", "cross-site"])
    @pytest.mark.parametrize("path", ["/api/session", "/api/compare?baseline=x"])
    def test_an_api_request_from_another_page_is_refused(self, server, site, path) -> None:
        """A page served from another port of 127.0.0.1 is the same site to a browser, which
        sends it this server's SameSite=Strict cookie: probed against a1da6ce, its GET of
        /api/compare ran the comparison, plugins and all."""
        response, data = ask(server, "GET", path, headers={"Sec-Fetch-Site": site})
        assert (response.status, json.loads(data)) == (
            403,
            {"error": "forbidden", "message": _ELSEWHERE},
        )

    def test_a_page_requested_from_another_page_says_where_to_sign_in(self, server) -> None:
        response, data = ask(server, "GET", "/project", headers={"Sec-Fetch-Site": "same-site"})
        assert (response.status, data) == (403, SIGN_IN_PAGE)

    @pytest.mark.parametrize("origin", ["http://127.0.0.1:1", "http://evil.example", "null"])
    def test_a_get_carrying_another_origin_is_refused(self, server, origin) -> None:
        response, data = ask(server, "GET", "/api/session", origin=origin)
        assert (response.status, json.loads(data)["message"]) == (403, _ELSEWHERE)

    @pytest.mark.parametrize("site", ["same-origin", "none"])
    def test_this_page_and_an_address_typed_are_answered(self, server, site) -> None:
        response, _ = ask(server, "GET", "/api/session", headers={"Sec-Fetch-Site": site})
        assert response.status == 200

    @pytest.mark.parametrize("host", ["127.0.0.1", "localhost"])
    def test_this_servers_own_origin_is_answered(self, server, host) -> None:
        response, _ = ask(server, "GET", "/api/session", origin=f"http://{host}:{server.port}")
        assert response.status == 200

    def test_another_page_is_refused_before_the_cookie_is_read(self, server) -> None:
        response, _ = ask(
            server, "GET", "/api/session", signed_in=False, headers={"Sec-Fetch-Site": "same-site"}
        )
        assert response.status == 403

    def test_signing_in_is_answered_wherever_the_address_was_opened_from(self, server) -> None:
        """A launch opens the address from a file:// page, which a browser calls cross-site;
        the token is what ``/open`` checks."""
        response, _ = ask(
            server,
            "GET",
            f"/open?token={server.token}",
            signed_in=False,
            headers={"Sec-Fetch-Site": "cross-site"},
        )
        assert response.status == 200
```

Import `_ELSEWHERE`.

- [ ] **Step 2: Run them, and watch the refusals fail** (the answers are 200 today).

- [ ] **Step 3: Implement the gate.**

Add:

```python
_ELSEWHERE: Final = "ddd gui answers its own page alone, opened from the address it printed"
```

```python
    def _from_elsewhere(self) -> bool:
        """Whether the request says it came from somewhere other than this server's own page.

        A browser marks every request it sends with ``Sec-Fetch-Site``: ``same-origin`` from
        this server's own page, ``none`` for an address typed or a bookmark, and ``same-site``
        from a page served on another port of this address - which also carries this server's
        ``SameSite=Strict`` cookie, a cookie belonging to an address and not to a port. Every
        browser sends it since 2023 (Chrome 76, Firefox 90, Safari 16.4). An ``Origin`` other
        than this server's is refused too, for a browser older than those. A client that sends
        neither - a script, ``curl``, these tests - goes on to the cookie, so the token still
        decides.
        """
        site = self.headers.get("Sec-Fetch-Site")
        if site is not None and site not in ("same-origin", "none"):
            return True
        origin = self.headers.get("Origin")
        if origin is None:
            return False
        port = self._gui.port
        return origin not in (f"http://127.0.0.1:{port}", f"http://localhost:{port}")
```

In `_route`, after the `/open` branch and before the cookie, insert the gate:

```python
        api = url.path.startswith("/api/")
        if self._from_elsewhere():
            if api:
                self._send_json(403, {"error": "forbidden", "message": _ELSEWHERE})
            else:
                self._send(403, SIGN_IN_PAGE, CONTENT_TYPES[".html"])
            return
        if not self._signed_in():
```

(`api` moves up from where `_route` computes it today.)

- [ ] **Step 4: Run the tests, then the Python gate.**

- [ ] **Step 5: Run the journeys alone.**

Run `npm run build` first. Every journey must pass: the page's own requests are `same-origin`, and `page.goto` is `none`.

- [ ] **Step 6: Ablate, in a scratch worktree, with pytest run from inside it.** Each of these mutations must fail a named test:
  - (a) `same-site` let through;
  - (b) `none` refused;
  - (c) the `Origin` check removed;
  - (d) the gate placed after the cookie;
  - (e) `/open` put behind the gate;
  - (f) the page answered with the JSON refusal.

- [ ] **Step 7: Commit.**

Subject: `refuse a request that did not come from this server's own page, before reading its cookie`. The body names the probe of spec §2 and its run.

---

### Task 3: the route table, the value types, and the routes that take a plain query

**Model:** opus. **Files:**
- `src/ddd/gui/routes.py` and `src/ddd/gui/queries.py` (created);
- `src/ddd/gui/api.py`, `src/ddd/gui/contract.py` and `src/ddd/gui/server.py`;
- `gui/src/api/client.ts`;
- `tests/test_gui_queries.py` (created);
- `tests/test_gui_api.py` and `tests/test_gui_server.py`.

Read *Appendix A* first. It is every route's query as `a1da6ce` reads it: its keys, what a blank value means, which comes first between a missing project and a malformed query, and every refusal sentence, word for word. **The query models answer for form:**
- which keys may be given, and that each is given once;
- a value's length, and that it holds no NUL;
- that a number is digits;
- a path's shape;
- JSON's depth, and that its numbers are finite.

**The handlers keep answering for meaning** (whether a name is declared, whether a unit is known, whether a value fits) with their sentences unchanged. A sentence a handler answers today about form moves into its model **word for word**.

This task covers:
- **The mechanism:** `Route`, `Policy`, `ROUTES`, `one_value_each`, the dispatcher and the value types.
- **Every route with no query:**
  - session, projects, dictionary, graph, checks, units, types, shared, files, and undo's `GET`, with `NoQuery`;
  - open, edit, and undo's `POST`, whose bodies already have models.
- **The routes whose query is plain:** state, findings, file, variable, unit, type, constant, section, raster, values, settle, fix, declarable and compare.
- **The `POST` bodies' paths:** `OpenRequest.path` and `Change.file` take the path type too, because a NUL there reaches the same `resolve` (Appendix A, *Bodies*).

- [ ] **Step 1: Write the failing tests of the value types,** in `tests/test_gui_queries.py`:

```python
"""The types a query's values are read as, and every query model's refusals."""

from typing import Annotated

import pytest
from pydantic import BaseModel, ValidationError

from ddd.gui.queries import MAX_DEPTH, MAX_DIGITS, MAX_NAME, MAX_PATH, json_text, name, path, whole

SAID = "this route takes ?it= as a whole number from 0"


class Whole(BaseModel):
    it: Annotated[int, whole(SAID)]


@pytest.mark.parametrize("text", ["0", "7", "007", "9" * MAX_DIGITS])
def test_a_whole_number_is_its_ascii_digits(text) -> None:
    assert Whole.model_validate({"it": text}).it == int(text)


@pytest.mark.parametrize("text", ["", "-1", "+1", "1.5", "1_000", " 1", "\u0663", "1" * (MAX_DIGITS + 1), "1" * 4301])
def test_anything_else_is_refused_with_the_routes_own_sentence(text) -> None:
    with pytest.raises(ValidationError) as refused:
        Whole.model_validate({"it": text})
    assert refused.value.errors()[0]["msg"] == SAID
```

Write the same shape of tests for the other three types:
- **`path(sentence)`:**
  - refused: empty, `\x00` inside, `\ud800` inside, a relative path, `\\server\share\a`, `//server/share/a`, `\\?\C:\a`, and `MAX_PATH + 1` characters;
  - accepted: `/a/b.ddd.json` and `C:/a/b.ddd.json`. The second is absolute on Windows and not on Linux, so it is accepted when `Path(text).is_absolute()` or it matches `^[A-Za-z]:[\\/]`. Both spellings are tested on every platform.
- **`json_text(sentence)`:**
  - valid text answers the parsed value;
  - `1e999`, `NaN` and `Infinity` are refused;
  - an array nested `MAX_DEPTH + 1` deep is refused, and one nested `MAX_DEPTH` deep is accepted;
  - 3,000 levels are refused **without** a `RecursionError`, so the depth is counted before parsing;
  - 4,301 digits are refused.
- **`name(sentence)`:** refused when empty, when it holds a NUL, or past `MAX_NAME` characters.

Pin each limit by its literal:

```python
def test_the_limits() -> None:
    assert (MAX_DIGITS, MAX_PATH, MAX_NAME, MAX_DEPTH) == (9, 4096, 1024, 64)
```

- [ ] **Step 2: Write the failing tests of the mechanism**, in `tests/test_gui_api.py`, through `Api.handle`:

```python
class TestTheQueryIsReadOnce:
    def test_a_key_given_twice_is_refused(self, demo_api) -> None:
        reply = demo_api.handle("GET", "/api/variable", {"name": ["ValueA", "ValueB"]}, None)
        assert reply == Reply(400, {"error": "bad-request", "message": "variable takes ?name= once"})

    def test_a_key_the_route_does_not_take_is_refused(self, demo_api) -> None:
        reply = demo_api.handle("GET", "/api/variable", {"name": ["ValueA"], "x": ["1"]}, None)
        assert reply == Reply(400, {"error": "bad-request", "message": "variable takes no ?x="})

    def test_a_route_with_no_query_refuses_one(self, demo_api) -> None:
        reply = demo_api.handle("GET", "/api/session", {"x": ["1"]}, None)
        assert reply == Reply(400, {"error": "bad-request", "message": "session takes no ?x="})
```

The new sentences are of the forms `"{route} takes ?{key}= once"` and `"{route} takes no ?{key}="`. `{route}` is the path's last segment, as every existing sentence spells it ("findings", "unit-plan").

`demo_api` stands for the `Api` over the demo's analysed session that `tests/test_gui_api.py`'s own tests use: use its real name.

A body's json depth stays pydantic's own limit (spec §6): a `POST /api/edit` whose body nests an array 3,000 deep answers 400 through `_validated`, never a `RecursionError`. Pin it with a test.

Each 500 of spec §2 that is reached through these routes gets its failing test:
- `findings?file=` holding a NUL answers 400 `"findings takes ?file= as a file's path"`;
- `findings?offset=` of 4,301 digits answers the existing offset sentence;
- `state?after=` of 4,301 digits answers at once, 200, as a non-number does;
- `file?path=` holding a NUL answers 400 `"file takes ?path= as a file's path"`;
- `settle?raw=` nested 3,000 deep answers 400 `parse_raw`'s own sentence for too deep a value. Read that sentence off `ddd.loading`, which says `"the json is nested too deeply to read"`, wrapped as `parse_raw` wraps every refusal;
- `/api/open` with a NUL in its body's `path` answers 400 through `_validated`.

Read every expected sentence off the code (*Global Constraints*), and copy the ones Appendix A lists.

- [ ] **Step 3: Run them, and watch them fail.**

- [ ] **Step 4: Write `src/ddd/gui/queries.py`.** The shape:

```python
"""What every route of the ddd gui api takes in its query, and the types its values are read as.

A query arrives as text, one value a key (``routes.one_value_each``). Each route's model says
which keys it takes, and reads each value as the type it is: the model answers for form - a
number's digits, a path's shape, json's depth - and the route's handler for meaning, as before.
Every refusal a model makes is one sentence: the route's own, word for word, where it already
said one about that key (Appendix A of ``docs/superpowers/plans/2026-10-05-gui-security.md``).
"""

from __future__ import annotations

import json
import math
import re
from typing import Annotated, Any, ClassVar, Final

from pydantic import BaseModel, BeforeValidator, ConfigDict
from pydantic_core import PydanticCustomError

MAX_DIGITS: Final = 9
"""The most digits a whole number of a query has: a page offset, a version, a cell's index -
every one far below a billion, and ``int()`` of more than 4,300 digits raises."""

MAX_PATH: Final = 4096
"""The longest path a query names; ``PATH_MAX`` on Linux, beyond any project's."""

MAX_NAME: Final = 1024
"""The longest name a query gives: a variable, a unit, a type."""

MAX_DEPTH: Final = 64
"""The deepest json a query carries: a description nests a value five or six levels down."""

_DRIVE: Final = re.compile(r"[A-Za-z]:[\\/]")


def refusal(sentence: str) -> PydanticCustomError:
    """A refusal whose message is ``sentence`` exactly: braces in it are not a template."""
    return PydanticCustomError("query", "{sentence}", {"sentence": sentence})


def whole(sentence: str, *, least: int = 0) -> BeforeValidator:
    """A whole number written in ASCII digits, at most :data:`MAX_DIGITS` of them, from
    ``least``; anything else is refused with ``sentence``."""

    def read(value: object) -> int:
        if isinstance(value, str) and value.isascii() and value.isdecimal():
            if len(value) <= MAX_DIGITS and int(value) >= least:
                return int(value)
        raise refusal(sentence)

    return BeforeValidator(read)
```

Write `path`, `json_text` and `name` the same way:
- **`json_text`** counts the brackets' depth over the text before parsing it, and then parses with `ddd.editing.parse_raw` where the route answers `parse_raw`'s sentences today (settle, the shared plans). It refuses with that same sentence.
- **`path` and `name`** refuse with the route's sentence.

Then define the models, a base and one model per route:

```python
class _Query(BaseModel):
    """A route's query: the keys it takes, each read as its type; closed and frozen."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    missing: ClassVar[str] = ""
    """What the route answers when a key it requires is left out or blank."""


class NoQuery(_Query):
    """The query of a route that takes none."""


class FindingsQuery(_Query):
    offset: Annotated[int, whole("findings takes ?offset= as a whole number from 0")] = 0
    limit: Annotated[int, whole("findings takes ?limit= as a whole number from 1", least=1)] | None = None
    severity: Annotated[str, BeforeValidator(_severity)] | None = None
    file: Annotated[str, path("findings takes ?file= as a file's path")] | None = None
    check: Annotated[str, name("findings takes ?check= as a check's name")] | None = None
```

Every other plain route follows Appendix A, keeping what a blank value means there:
- for findings, a blank `file` or `check` filters to nothing, as today, so the model lets `""` through for those two;
- for fix, a blank `pointer` is the whole file;
- for settle, a blank `raw` takes the key away;
- `state`'s `after` stays lenient: any value that is not a whole number of at most nine digits answers at once (`test_gui_api.py`'s non-numbers, pinned).

- [ ] **Step 5: Write `src/ddd/gui/routes.py`.**

```python
"""The routes of the ddd gui api: what each takes and does, in one table the dispatcher, the
hostile-value walk and the security page all read."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel

if TYPE_CHECKING:
    from ddd.gui.api import Api, Reply


@dataclass(frozen=True, slots=True)
class Policy:
    """What a route does besides answering: what the security page's table says of it."""

    writes: bool = False
    opens: bool = False
    runs_plugins: bool = False
    waits: bool = False


@dataclass(frozen=True, slots=True)
class Route:
    path: str
    method: str
    query: type[BaseModel]
    body: type[BaseModel] | None
    answer: Callable[[Api, BaseModel, BaseModel | None], Reply]
    policy: Policy = Policy()

    @property
    def name(self) -> str:
        """How the route's sentences call it: its path's last segment."""
        return self.path.rsplit("/", 1)[1]


def one_value_each(query: Mapping[str, Sequence[str]], route: str) -> dict[str, str] | str:
    """The query's values, one a key, or the sentence refusing the first key given twice."""
    values: dict[str, str] = {}
    for key, given in query.items():
        if len(given) != 1:
            return f"{route} takes ?{key}= once"
        values[key] = given[0]
    return values
```

`ROUTES` is filled in `api.py`, after `Api`, because each `answer` is an `Api` method. It is a tuple in `_ROUTES`' order today, and it replaces `_ROUTES`.

The policies:
- **`/api/open`:** `opens=True, runs_plugins=True`.
- **`/api/edit` and `POST /api/undo`:** `writes=True`.
- **`/api/compare`:** `runs_plugins=True`.
- **`/api/state`:** `waits=True`.

- [ ] **Step 6: The dispatcher.** In `Api.handle`, run these steps in order:
  1. Look the route up by path and method, and answer 404 or 405 with today's sentences.
  2. Read the values with `one_value_each`.
  3. Validate them against `route.query`, refusing the first problem as one sentence (see below).
  4. Validate the body, for a `POST`, with `_validated` as today.
  5. Call `route.answer(self, typed, body)`.

  The first problem becomes one sentence through `_query_message`:
  - a `query` error's own sentence;
  - for `missing`, the model's `missing`;
  - for `extra_forbidden`, `"{route} takes no ?{key}="`.

  The query is validated **before** the project is looked at, on every route. That is the order the six query-first routes already follow (Appendix A). The two tests pinning the other order, compare without a baseline and file without a project, change to it, as ruling 4 records.

- [ ] **Step 7: Convert each handler of this task.** Each takes its typed query instead of `query: Query`: `def _findings(self, query: FindingsQuery, body: None) -> Reply:`. Delete every `_single(query.get(...))` and every form refusal that moved into a model. In this task, `_integer` keeps only the callers Task 4 converts.

- [ ] **Step 8: The page's types.**
  - Add every query model of this task to `contract.py`'s `_ENDPOINTS` as `"validation"`.
  - Regenerate the schemas.
  - Make `client.ts`'s builders for these routes take the generated types. `FindingsQuery`, for one, is today a type of `client.ts`'s own, and is replaced by the generated one, its fields unchanged.
  - `npm run typecheck`, `npm test` and every `client.test.ts` query string must stay green and unchanged.

- [ ] **Step 9: Run the gates.**
  - The Python gate.
  - The page gate.
  - The journeys, alone, after `npm run build`.
  - The screenshots in compare mode, with no reference moving.

- [ ] **Step 10: Ablate, in a scratch worktree.** Each must fail a named test:
  - (a) `MAX_DIGITS` at 10;
  - (b) a path's NUL let through;
  - (c) a network path let through;
  - (d) the depth counted after parsing;
  - (e) `extra="forbid"` removed;
  - (f) `one_value_each` keeping the first of two;
  - (g) one moved sentence reworded.

- [ ] **Step 11: Commit.** Subject: `read every plain query through one route table and a model of its own`.

---

### Task 4: the plan routes, one model per action

**Model:** opus. **Files:** `src/ddd/gui/queries.py`, `src/ddd/gui/api.py`, `src/ddd/gui/contract.py`, `gui/src/api/client.ts`, `tests/test_gui_queries.py`, `tests/test_gui_api.py`.

The routes: unit-plan, type-plan, constant-plan, section-plan, raster-plan, files-plan, declaration-plan, value-plan and values-plan (Appendix A).

**Each action route's query is a union of one model per action, discriminated by `action`.**
- An action the route does not take answers the route's `"{route} takes ?action= one of ..."` sentence word for word, through a model-level check run before the union is read.
- A part an action requires that is left out answers that action's `"{action} takes ..."` sentence word for word: the action model's `missing`.
- A key another action takes, given to this one, answers `"{action} takes no ?{key}="`. Today such a key is read and ignored, or, for `raw` on the shared plans, JSON-checked though unused. The page never sends one (Appendix A, *the page*).

**Blank values keep their meaning:**
- `description=` clears a unit's description.
- A blank `raw` takes a key away (type-plan `set`, the shared plans' `set`).
- A blank `to` reaches the handler's own refusal: unit-plan answers 409 `invalid`, "the empty unit is no unit" (pinned).
- A blank `component` on files-plan's `create` is no component.
- A blank part of declaration-plan reaches the handler as it does today.

**The 500s of these routes become refusals:**
- value-plan's `at` and `raw`, and values-plan's `raw`, of 4,301 digits;
- declaration-plan's `definition` nested 3,000 deep or of 4,301 digits;
- declaration-plan's `file` holding a NUL.

value-plan and values-plan keep their 409 `"'…' is not a number"`, which the handler answers. Its `_number` catches the `ValueError` of too many digits and answers that sentence.

declaration-plan's `definition` keeps its 409 `invalid`, `"the definition is not json"`. The model reads it as JSON text of at most `MAX_DEPTH` levels and **refuses with that same status and sentence**, through a check in the handler rather than in the model. This is the one form refusal that stays a 409, because the page's declare panel shows it as an offer's refusal (ruling 5).

- [ ] **Step 1: Write the failing tests,** one per action of every route:
  - an unknown action;
  - each action's missing part;
  - a key another action takes;
  - each 500 above, now refused.

  Every sentence is asserted whole, and read off the code.
- [ ] **Step 2: Run them, and watch them fail.**
- [ ] **Step 3: Write the models, and convert the handlers.** The `takes` dicts (api.py's `_unit_plan`, `_type_plan`, `_shared_plan`, `_files_plan` and `_declaration_plan`) go, and so do `_single` and `_integer`.
- [ ] **Step 4: Update the page's types,** as Task 3 Step 8 did. A plan builder's request type becomes the generated union, and every `client.test.ts` query string stays unchanged.
- [ ] **Step 5: Run the gates,** as in Task 3 Step 9, the screenshots included. `rename-refused`, `event-already-claimed`, `new-file-refused` and the other refusal references of Appendix A must not move.
- [ ] **Step 6: Ablate, in a scratch worktree.** Each must fail a named test:
  - (a) one action's model accepting another's key;
  - (b) one `missing` sentence reworded;
  - (c) the unknown-action sentence reworded;
  - (d) `description=` refused as blank;
  - (e) `_number`'s digit guard removed.
- [ ] **Step 7: Commit.** Subject: `read every plan's query through one model per action`.

---

### Task 5: no route answers a hostile value with 500

**Model:** sonnet. **Files:** `tests/test_gui_hostile.py`.

- [ ] **Step 1: Write the walk.**

```python
"""Every parameter of every route, sent every hostile value spec §5 names: none is a 500."""

import json

import pytest

from ddd.gui.api import ROUTES

HOSTILE = (
    "\x00",
    "a\x00b",
    "\ud800",
    "1" * 4301,
    "[" * 3000 + "]" * 3000,
    "1e999",
    "\\\\server\\share\\a.ddd.json",
    "//server/share/a.ddd.json",
    "",
    "x" * 65536,
)
```

For each route, take the keys its model takes from `model_fields`, through every model of a union. A route with no query gets one stray key. Send each key each hostile value, with every other required key given a well-formed value from the route's own tests, through `Api.handle` on the demo's analysed session. Assert:

```python
        assert reply.status != 500, (route.path, key, value[:20], reply.body)
```

`POST` bodies go through `_validated`. Each string field of `OpenRequest`, `Changes`, `Change`, `Operation` and `UndoRequest` gets the same values, in an otherwise well-formed body.

A value meant to wait is the one exception. The state route's `after` never waits for a hostile value, since none of them is a whole number, and the walk passes `wait_seconds=0`, as the API's tests construct it.

- [ ] **Step 2: Run it against the head before Tasks 3 and 4, and watch it fail.** In a scratch worktree at the commit before Task 3, it must find the 500s of spec §2. Quote the failing parameters.
- [ ] **Step 3: Run it at the head; every answer must be a refusal or an answer, never a 500.**
- [ ] **Step 4: Commit.** Subject: `walk every route's every parameter with hostile values, none answered 500`.

---


---

### Task 6: a cap of 64 connections

**Model:** opus (concurrency). **Files:** `src/ddd/gui/server.py`, `tests/test_gui_server.py`.

The tests use real sockets and events, never a sleep. A stand-in API, whose `handle` waits on a `threading.Event` with a timeout, holds a connection's slot for as long as the test chooses. The refusal is read off a `socket.socketpair()` handed to `process_request` directly, so that no network race decides whether the refused client reads its 503.

- [ ] **Step 1: Write the failing tests.**

```python
class Held:
    """A stand-in for the API: every request waits until the test lets it go."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.asked = threading.Semaphore(0)
        self.release = threading.Event()

    def handle(self, method, path, query, body):
        self.asked.release()
        assert self.release.wait(10), "the test never let the request go"
        return Reply(200, {"held": True})


class TestTheCap:
    def test_the_cap_is_sixty_four_connections(self) -> None:
        assert MAX_CONNECTIONS == 64

    def test_a_connection_past_the_cap_is_answered_503_by_the_accepting_thread(
        self, project_file, pages
    ) -> None:
        api = Held(Session(project_file.parent))
        server = GuiServer(api, pages, connections=2)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            held = [
                threading.Thread(target=ask, args=(server, "GET", "/api/session"), daemon=True)
                for _ in range(2)
            ]
            for each in held:
                each.start()
            for _ in held:
                assert api.asked.acquire(timeout=10)
            threads = threading.active_count()
            ours, theirs = socket.socketpair()
            with ours, theirs:
                theirs.sendall(b"GET /api/session HTTP/1.1\r\nHost: x\r\n\r\n")
                server.process_request(ours, ("127.0.0.1", 0))
                ours.settimeout(None)
                answer = theirs.makefile("rb").read()
            assert threading.active_count() == threads    # no thread was started for it
            head, _, data = answer.partition(b"\r\n\r\n")
            assert head.split(b"\r\n")[0] == b"HTTP/1.1 503 Service Unavailable"
            assert b"Retry-After: 1" in head.split(b"\r\n")
            assert json.loads(data) == {"error": "busy", "message": BUSY}
            api.release.set()
            for each in held:
                each.join(10)
            response, _ = ask(server, "GET", "/api/session")   # a slot is free again
            assert response.status == 200
        finally:
            api.release.set()
            server.shutdown()
            server.server_close()

    def test_a_thread_that_cannot_start_gives_its_slot_back(
        self, project_file, pages, monkeypatch
    ) -> None:
        server = GuiServer(Held(Session(project_file.parent)), pages, connections=1)
        try:
            monkeypatch.setattr(threading.Thread, "start", _cannot_start)
            ours, theirs = socket.socketpair()
            with ours, theirs, pytest.raises(RuntimeError):
                server.process_request(ours, ("127.0.0.1", 0))
            monkeypatch.undo()
            assert server.slots.acquire(blocking=False)   # the one slot is free
        finally:
            server.server_close()


def _cannot_start(self) -> None:
    raise RuntimeError("can't start new thread")
```

Import `MAX_CONNECTIONS`, `BUSY` and `Reply` (from `ddd.gui.api`), and `socket`.

Pin the standard library's own limits, which spec §6 names, beside them: a request line of more than 65,536 bytes is answered 414, and a request of 101 headers 431, both through a raw socket.

- [ ] **Step 2: Run them, and watch them fail.** The two standard-library pins pass at once, since they already hold; they guard against a server that stops answering them.

- [ ] **Step 3: Implement the cap.**

```python
MAX_CONNECTIONS: Final = 64
"""How many connections are answered at once, each on a thread of its own; the next is refused.

A browser opens at most six connections to one host, across all its tabs, so the page never
comes near this: sixty-four leaves room for ten browser profiles and some scripts. Without
it, the threads grew with whatever was asked: probed against ``a1da6ce``, three hundred long
polls took the server from 31 threads to 293."""

BUSY: Final = "ddd gui is answering as many connections as it takes at once; ask again in a moment"
```

In `GuiServer`:

```python
    def __init__(
        self,
        api: Api,
        static: Path,
        port: int = 0,
        host: str = "127.0.0.1",
        connections: int = MAX_CONNECTIONS,
    ) -> None:
        super().__init__((host, port), _Handler)
        ...
        self.slots = threading.BoundedSemaphore(connections)

    def process_request(self, request: Any, client_address: Any) -> None:
        """Answer on a thread of its own if a slot is free; else refuse from this thread.

        The refusal is written here, on the thread that accepts, so that a connection past the
        cap starts no thread: what it reads first is drained without waiting, so that closing
        does not reset the connection before the client reads its answer."""
        if not self.slots.acquire(blocking=False):
            _refuse(request)
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request: Any, client_address: Any) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()
```

At module level:

```python
def _refuse(request: socket.socket) -> None:
    """Write the 503 a connection past the cap gets, and give up on one that will not take it."""
    data = json.dumps({"error": "busy", "message": BUSY}).encode("utf-8")
    headers = {
        **SECURITY_HEADERS,
        "Cache-Control": "no-store",
        "Retry-After": "1",
        "Content-Type": CONTENT_TYPES[".json"],
        "Content-Length": str(len(data)),
        "Connection": "close",
    }
    head = "".join(f"{name}: {value}\r\n" for name, value in headers.items())
    request.settimeout(1)
    with contextlib.suppress(OSError):
        request.setblocking(False)
        with contextlib.suppress(BlockingIOError):
            request.recv(65536)
        request.settimeout(1)
        request.sendall(f"HTTP/1.1 503 Service Unavailable\r\n{head}\r\n".encode("latin-1") + data)
```

The implementer adjusts `_refuse` so that every line is covered by a test. A client that resets mid-write is one test, through `socketpair` with the far end closed first.

- [ ] **Step 4: Run the tests and the whole Python gate.** `TestOneConnectionCarriesManyAsks` and the long-poll tests must still pass.

- [ ] **Step 5: Probe it.** Run spec §2's long-poll probe again against a scratch `ddd gui`: 300 long polls at once, with the thread count read from `/proc/<pid>/status`. The count must stay at or under the server's own threads plus 64. Quote the counts, with the machine and the commit.

- [ ] **Step 6: Ablate, in a scratch worktree.** Each must fail a named test:
  - (a) `MAX_CONNECTIONS` at 65;
  - (b) the slot never released;
  - (c) the slot not released when the thread cannot start;
  - (d) the refusal answered on a thread of its own;
  - (e) the `Retry-After` line dropped.

- [ ] **Step 7: Commit.** Subject: `cap the connections answered at once at sixty-four, refusing the next from the accepting thread`.

---

### Task 7: SECURITY.md, the security page, and the dependency audit

**Model:** sonnet. **Files:**
- `SECURITY.md`
- `docs/gui_security.rst`
- `docs/index.rst`
- `tests/test_gui_docs.py`
- `src/ddd/gui/server.py` (its docstring)
- `CHANGELOG.md`

- [ ] **Step 1: Write the failing test of the page's route table.**

```python
"""The security page's table of routes, held against the server's own route table."""

from pathlib import Path

from ddd.gui.api import ROUTES

PAGE = Path(__file__).parents[1] / "docs" / "gui_security.rst"


def _rows() -> list[tuple[str, ...]]:
    """The list-table's rows under ``.. _gui-security-routes:``, each cell stripped of its
    literal markup."""
    lines = PAGE.read_text(encoding="utf-8").split(".. _gui-security-routes:", 1)[1].splitlines()
    rows: list[list[str]] = []
    for line in lines:
        if line.startswith("   * - "):
            rows.append([line[7:].strip().strip("`")])
        elif line.startswith("     - ") and rows:
            rows[-1].append(line[7:].strip().strip("`"))
        elif rows and line and not line.startswith(" "):
            break
    return [tuple(row) for row in rows[1:]]   # the header row left out


def _yes(flag: bool) -> str:
    return "yes" if flag else ""


def test_the_page_names_every_route_with_its_policy() -> None:
    expected = [
        (
            route.method,
            route.path,
            _yes(route.policy.writes),
            _yes(route.policy.opens),
            _yes(route.policy.runs_plugins),
            _yes(route.policy.waits),
        )
        for route in ROUTES
    ]
    assert _rows() == expected
```

- [ ] **Step 2: Write `docs/gui_security.rst`, then run the test until it passes.** The page has these sections:
  1. **What `ddd gui` defends against:** spec §1's three, in the reader's terms.
  2. **What it trusts:** the project and its plugins, a compared baseline's plugins, the directory it was started in, and the token's holder.
  3. **The browsers it protects:** Chrome 76, Firefox 90, Safari 16.4 and later, which send `Sec-Fetch-Site`.
  4. **Running it in a container:** publish on `127.0.0.1` only (`-p 127.0.0.1:8123:8123`), since beyond the loopback the token is the only barrier.
  5. **What it does not defend against:** a local process that fills the 64 connections can deny the page its server, and transport security.
  6. **Reporting a vulnerability:** see `SECURITY.md`.
  7. **Every route:** a `list-table` under the label `.. _gui-security-routes:`, with the columns *Method*, *Path*, *Writes*, *Opens a project*, *Runs plugins* and *Waits*. Each flag column holds `yes` or is left empty.

Add `gui_security` to `docs/index.rst`'s *Using DDD* toctree, after `editor_integration`.

- [ ] **Step 3: Write `SECURITY.md`.** It covers:
  - the supported versions: the latest release, with `ddd gui` marked preview;
  - how to report: privately, from the repository's **Security** tab, with **Report a vulnerability**;
  - what a report should hold: the version, the steps, and what an attacker gains;
  - a pointer to `docs/gui_security.rst`.

  It promises no response time.

- [ ] **Step 4: Update the module docstring of `server.py`, and `CHANGELOG.md`.**
  - **The docstring:** its bullet list gains the gate (where a request comes from), the cap, and the launch.
  - **`CHANGELOG.md`:** under `## Unreleased`, one line each for the gate, the typed queries (no route answers malformed input with 500), the cap, the launch, `SECURITY.md` and the page.

- [ ] **Step 5: Run the dependency audit, once.**

```bash
python3 -m venv <scratch>/audit && <scratch>/audit/bin/pip install pip-audit
<scratch>/audit/bin/pip-audit -r <(.venv/bin/pip freeze --exclude-editable) --desc > <scratch>/pip-audit.txt; echo "PIP_AUDIT=$?"
(cd gui && npm audit > <scratch>/npm-audit.txt; echo "NPM_AUDIT=$?")
```

- Report each finding with its package, version, advisory and severity.
- Upgrade a high or critical finding that has a compatible fix in this task, gates green.
- Put any other finding in your report, for the plan's *What was left open*.
- Quote the date and the commit you audited.

- [ ] **Step 6: Run the gates.** Run the Python gate, then the documentation build in Docker, under `-W`.

- [ ] **Step 7: Ablate, in place for the page and in a worktree for the test.**
  - (a) Remove one route's row from the page.
  - (b) Flip one `yes`.

  Each must fail `test_the_page_names_every_route_with_its_policy`.

- [ ] **Step 8: Commit.** Subject: `say what ddd gui defends and trusts, and how to report a vulnerability`.

---

### Task 8: a page on another port cannot make ddd gui run a baseline's plugin

**Model:** sonnet. **Files:** `gui/e2e/hostile.spec.ts`, `gui/e2e/demo.ts`.

- [ ] **Step 1: Write the journey.**
  1. **The baseline.** In the served copy (`gui.directory`), write a baseline description `baseline/baseline.ddd.json`: a project naming one component file and `"plugins": ["marker.py"]`. Beside it goes `marker.py`, whose body is:

     ```python
     from pathlib import Path
     Path(__file__).with_name("ran").write_text("the plugin ran", encoding="utf-8")
     ```

     The plugin is invalid past that line, which does not matter: its module body runs on import (`ddd.plugins`), before it is validated.
  2. **Sign in.** Open `gui.address` in the browser context, which stores the cookie.
  3. **The hostile page.** Start a Node `http` server on a free port of `127.0.0.1`, serving one page whose script runs:

     ```js
     fetch("http://127.0.0.1:<gui port>/api/compare?baseline=<the baseline's path, encoded>",
           { credentials: "include", mode: "no-cors" })
       .finally(() => { document.title = "asked"; });
     ```

  4. Open that page in the **same** context, and wait for its title to be `asked`.
  5. **The assertion:** `existsSync(join(gui.directory, "baseline", "ran"))` is `false`.
  6. Stop the Node server in a `finally`.

- [ ] **Step 2: Run it against the gate taken out, and watch the marker appear.**
  - Take Task 2's gate out of `src/ddd/gui/server.py` in place, run `npm run build`, then run this journey: the marker must appear.
  - Run `git status --porcelain src/ddd/gui/server.py`, then restore the file, and grep for `_from_elsewhere`.
  - Quote the failing run.

- [ ] **Step 3: Run it with the gate, then every journey, alone.** The marker never appears, and all journeys pass.

- [ ] **Step 4: Commit.** Subject: `prove in a browser that a page on another port cannot make ddd gui run a baseline's plugin`.

---

### Task 9: the figures after, and the milestone gate

**Model:** the controller's own.

- [ ] **Step 1: Run spec §2's probes again** against a scratch `ddd gui`, over a copy of `examples/demo`, on the Linux development PC, at the branch's head. Record each answer, before and after, in *Figures* below.
- [ ] **Step 2: Run the milestone gate** (below), with every exit status captured.
- [ ] **Step 3: Close the plan out:**
  - the *As built* note under the header;
  - the progress log;
  - *What was left open*, including the audit's leftovers;
  - *Rulings taken*.

## Milestone gate

Every command, each exit status captured on its own line:

```bash
rm -f .coverage .coverage.*
.venv/bin/python -m pytest > gate/pytest.txt 2>&1; echo "PYTEST=$?"
.venv/bin/ruff check . ; echo "RUFF=$?"
.venv/bin/ruff format --check . ; echo "FMT=$?"
.venv/bin/mypy ; echo "MYPY=$?"
cd gui
DDD=../.venv/bin/ddd DDD_PYTHON=../.venv/bin/python npm run schemas; echo "SCHEMAS=$?"
npm run lint; echo "LINT=$?"
npm run typecheck; echo "TSC=$?"
npm test; echo "VITEST=$?"
npm run build; echo "BUILD=$?"
npm run ladle:build; echo "LADLE=$?"
cd ..
docker compose run --rm gui-screenshots; echo "SHOTS=$?"
git status --short gui/screenshots/references      # must be empty
docker compose run --rm -e JAVA_TOOL_OPTIONS=-Duser.home=/tmp docs; echo "DOCS=$?"
cd gui && PLAYWRIGHT_CHANNEL=chrome DDD_PYTHON="$PWD/../.venv/bin/python" \
  npx playwright test --output=<scratch>/e2e; echo "E2E=$?"
```

## Figures

### Probes, before

These are spec §2's, on the Linux development PC, against master `a1da6ce`, on 2026-10-05. See the spec for the table.

### Probes, after

Filled in by Task 9.

### Dependency audit

Filled in by Task 7.

## Progress log

| Task | Commits | Review | Notes |
| --- | --- | --- | --- |

## What was left open

Filled in as the work goes. Known before execution:
- **Untrusted projects** (spec §10): no gate before a project's plugins run.
- **A browser older than Chrome 76, Firefox 90 or Safari 16.4** sends neither `Sec-Fetch-Site` nor, on a plain `GET`, `Origin`. A page on another port can still make such a browser ask one `GET`.
- **A local process can fill the 64 connections,** and so deny the page its server.

## Rulings taken

Taken while planning; execution adds its own below them.

1. **The route table and the value types live in modules of their own**, `routes.py` and `queries.py`, rather than in `api.py`. `api.py` is 2,537 lines, the table is consumed by the docs test and the walk as well as the dispatcher, and the value types are consumed by the page's generated types — cost if wrong: two imports more.
2. **The cap's refusal is tested through `process_request` on a `socketpair`,** not through a 65th network connection. Whether a refused client reads its 503 before the close would otherwise depend on whether its request bytes had arrived when the server accepted it, a race that no assertion can pin — cost if wrong: the accept loop's own call into `process_request` is reached by the existing tests, not this one.
3. **`/open`'s page carries a link as well as the refresh,** so that a browser set not to follow refreshes still offers the way in — cost if wrong: one line of HTML.
4. **A query is validated before the project is looked at, on every route.** Six routes already read their query first, and the rest looked for an open project first, so that a malformed query met with no project open answered 409 there and 400 here. One order for all of them is what one dispatcher can do. The two tests pinning the other order change: compare without a baseline, and file without a project — cost if wrong: a script that asked a malformed question with no project open reads 400 where it read 409.
5. **declaration-plan's `definition` keeps its 409 `invalid`, "the definition is not json".** It is checked in the handler, with the depth and finite-number rules of `json_text`, rather than refused 400 by the model like every other form refusal. The declare panel shows a declaration plan's refusal as its offer's, and the sentence and status it shows today stay — cost if wrong: one form refusal answered by a handler.
6. **The walk sends the `POST` bodies' string fields the hostile values too,** beyond spec §5's query parameters. A NUL in `/api/open`'s `path` or an edit's `file` reached the same `resolve` that answered 500 through the queries — cost if wrong: a few more cases in one test.
7. **The walk asserts no 500, rather than one of 400, 404 and 409.** The state route's `after` is lenient by design, and pinned: anything not a whole number answers the state at once, 200 — cost if wrong: none; a 200 is neither a 500 nor a hang.
8. **The routes are 35, not the 34 the inventory counted.** `_ROUTES` has 35 paths, and `/api/undo` takes both `GET` and `POST`.

### Taken during execution

## Appendix A: every route's query, as `a1da6ce` reads it

Read off `src/ddd/gui/api.py`, `server.py` and `gui/src/api/client.ts` while planning. Line numbers are `a1da6ce`'s.

**How a query arrives.**
- `server.py` reads it with `parse_qs(url.query, keep_blank_values=True)`. The defaults apply: `encoding='utf-8'` and `errors='replace'`. So invalid UTF-8, and any surrogate spelled in UTF-8, arrive as U+FFFD, and **no lone surrogate can arrive over HTTP**. Only an in-process caller can pass one, and the path type refuses it for them.
- `%00` arrives as NUL, `+` as a space.
- A repeated key arrives as a list, of which `_single` keeps the first.
- No route refuses an unknown key today.

**Which comes first today.** Every route looks for an open project (`_opened()`, 409) before reading its query, except file, declarable, declaration-plan, values, value-plan and values-plan, which read the query first. Task 3 makes the query first everywhere (ruling 4).

**The page.**
- It never repeats a key.
- It never sends `severity`.
- It never calls `/api/dictionary` or `/api/checks`.
- Its builders send no blank required value: route values pass through `|| undefined`, a builder answers `null` while a field is blank, and Compare is disabled while blank.
- `client.test.ts` pins every query string it builds.

| Route | Keys | Blank means | Form sentences to keep, word for word | Notes |
| --- | --- | --- | --- | --- |
| state | `after` | lenient: anything not a whole number answers at once | none | its leniency is pinned (`""`, `-1`, `one`, `٣`) |
| findings | `offset`, `limit`, `severity`, `file`, `check` | `offset`, `limit` and `severity`: refused; `file` and `check`: filter to nothing | "findings takes ?offset= as a whole number from 0"; "findings takes ?limit= as a whole number from 1"; "findings takes ?severity= as error, warning or info" | `file` holding a NUL: 500 |
| file | `path`, required | missing | "file takes ?path=" | query first; NUL: 500 |
| variable, unit, type, constant, section, raster, values | `name`, required | missing | "variable takes ?name=", "unit takes ?name=", "type takes ?name=", "constant takes ?name=", "section takes ?name=", "raster takes ?name=", "values takes ?name=" | values reads its query first |
| settle | `name`, `key` required; `raw` optional | `raw`: take the key away | "settle takes ?name= and ?key=, and ?raw= unless the key goes"; f"'{key}' is not a key the declarations of a variable share"; `parse_raw`'s f"{raw!r} is not one json value: {error}" | nesting 3,000 deep: 500 (spec §2) |
| fix | `file`, `pointer`, `check`, all required | `pointer`: the whole file | "fix takes ?file=, ?pointer= and ?check="; f"{file} is not a file of the open project" (404) | `file` holding a NUL: 500 |
| unit-plan | `action`; rename: `unit`, `to`; add: `unit`; describe: `unit`, `description`; remove: `unit`; adopt: none | `description`: the empty text; `to`: reaches "the empty unit is no unit" (409) | "unit-plan takes ?action= one of rename, add, describe, remove, adopt"; "rename takes ?unit= and ?to="; "add takes ?unit="; "describe takes ?unit= and ?description="; "remove takes ?unit=" | |
| type-plan | `action`; set: `name`, `key`, optional `raw`; rename: `name`, `to` | `raw`: take the key away | "type-plan takes ?action= one of set, rename"; "set takes ?name= and ?key="; "rename takes ?name= and ?to=" | a malformed `raw` is answered 409 `invalid` by the edit engine today |
| constant-plan, section-plan, raster-plan | `action`; set: `name`, `key`, optional `raw`; rename: `name`, `to`; remove: `name`; add: `name` plus `raw` (constant), `access` and `alignment` (section), `event` (raster) | `raw`: take the key away (set) | "constant-plan takes ?action= one of set, rename, add, remove" (and the same with section-plan, raster-plan); "set takes ?name= and ?key="; "rename takes ?name= and ?to="; "remove takes ?name="; "add takes ?name= and ?raw=", "add takes ?name= and ?access= and ?alignment=", "add takes ?name= and ?event="; `parse_raw`'s sentence for `raw`, `access`, `alignment`, `event` | the page shows `parse_raw`'s sentence for a value typed that is not json |
| files-plan | `action`; create: `kind`, `name`, optional `component`; add: `path`; remove: `path` | `component`: none; others: missing | "files-plan takes ?action= one of create, add, remove"; "create takes ?kind= and ?name="; "add takes ?path="; "remove takes ?path="; f"remove takes ?path= as a row's key, which is absolute, and '{path}' is not" | |
| declarable | `file`, required | missing | "declarable takes ?file=" | query first; NUL: 500 |
| declaration-plan | `action`; read: `file`, `name`, `scope`; declare: `file`, `scope`, `definition`; remove: `file`, `name` | passes to the handler | "declaration-plan takes ?action= one of read, declare, remove"; "read takes ?file= and ?name= and ?scope="; "declare takes ?file= and ?scope= and ?definition="; "remove takes ?file= and ?name="; 409 `invalid` "the definition is not json" | query first; `definition` read with plain `json.loads`; 4,301 digits: 500 |
| value-plan | `name`, `at`, `raw`, all required | missing | "value-plan takes ?name= and ?at= and ?raw="; 409 f"'{text}' is not a number" | query first; 4,301 digits in `raw`: 500 |
| values-plan | `name`, `raw`, required | missing | "values-plan takes ?name= and ?raw="; 409 f"'{text}' is not a number" | query first |
| compare | `baseline`, required | missing | "compare takes ?baseline="; the baseline sentences of `compare.py` | its NUL is already refused 400 |
| session, projects, dictionary, graph, checks, units, types, shared, files, undo (GET) | none | | | |
| open, edit, undo (POST) | bodies: `OpenRequest`, `Changes`, `UndoRequest` | | `_validated`'s sentences | `OpenRequest.path` and `Change.file` holding a NUL: 500 |
