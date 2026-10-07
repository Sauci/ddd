# The GUI's Token out of the Cookie Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `ddd gui`'s token is never a cookie. The page keeps it in `localStorage` for its own origin and sends it as `Authorization: Bearer`, so no server on another port of `127.0.0.1` is ever sent it.

**Architecture:**
- **The sign-in moves into the page.** `GET /open` answers the app itself. A module of the page reads the code or the token from its own address, posts it to `POST /open`, and keeps the token it is answered.
- **The API reads the header alone.** Every request to it carries `Authorization: Bearer <token>`, added in `request()`, the one function every request goes through. The compiled pages need no credential. A cookie is no credential any more.
- **Three steps, so that no commit leaves a gate red.**
  1. Expand: the server takes the header beside the cookie.
  2. Switch: the page signs itself in and sends the header.
  3. Contract: the cookie is no longer read.

**Tech Stack:**
- **Server:** Python 3.14, the standard library's `http.server`, `hmac.compare_digest`, pytest at 100 % line and branch.
- **Page:** React 19 + TypeScript, `localStorage`, `useSyncExternalStore`, Vitest at 100 % over `src/api`, `src/lib` and `src/state`.
- **Around it:** Playwright journeys, Ladle stories with Docker screenshot references, and Sphinx docs under `-W`.

**Spec:** `docs/superpowers/specs/2026-10-07-gui-token-out-of-cookie-design.md`. Read it before any task. Where this plan departs from it, the departure is a ruling in *Rulings taken* at the end, with its reason.

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

- **Never route around a refusal.** If the permission check refuses a command, stop and say so in your report. Never reach the same effect another way.
- **Delete only what you created,** each by its exact path, and never with a glob outside the session scratchpad.

**Gates**

- **Python:** `.venv/bin/python -m pytest` at **100 % line and branch**, `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, and `.venv/bin/mypy` run **bare** (it checks `src/ddd` and `tools`, strictly).
- **Page:** `npm run lint && npm run typecheck && npm test && npm run build && npm run ladle:build`, with Vitest at 100 % on statements, branches, functions **and** lines over `src/api`, `src/lib` and `src/state`.
- No `pragma: no cover`, no skips, no xfails.
- **No commit leaves a gate red.** A change to the contract lands with the page that reads it, in one commit.
- **CI runs more than the development PC does:**
  - **Python versions and runners.** Python 3.12, 3.13 and 3.14, on ubuntu **and** windows runners. On 3.12 and 3.13, coverage traces with `sys.settrace`, which spends stack on every traced call: a test that measures recursion depth must take the tracer out of what it measures (part 17's `deepest` in `tests/test_lsp.py`).
  - **Windows file locks.** Windows refuses to rename over, or delete, a file that another handle holds open (`ddd.editing.REPLACE_TRIES`).
  - **Windows path rules.** A path rule written for Windows runs for real there. On the Linux PC, it must be tested with spellings that mean the same thing on every platform.

  - **Windows reads `a:b` as a drive.** A name built with a colon as its second character, joined to a Windows path, is that drive's own path.
  - **Python 3.12's pathlib** raises `RuntimeError` on a loop of links, and `RecursionError` on a long chain of them, where 3.13 and later walk past both. Anything a request names is resolved through `loading.resolve_path`.
  - **pydantic-core's serializer stops at 99 levels on Windows**, and at 255 elsewhere.

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

- **The suite forbids skips** (`test_nothing_in_the_suite_skips`). A branch only one platform takes is covered by a module flag monkeypatched both ways, as `queries._CASELESS` and `queries._OPENS_DEVICES` are.
- **`json.loads` raises `RecursionError` on nesting past its depth,** and that is no `ValueError`. Where a request's body is parsed by hand, catch both.

**Prose**

- **A sentence stating a measurement gets the measurement run as it is written,** against the file it names, with the exit status copied from *that* run. A sentence saying "nothing else does X" is a whole-repository claim, and gets a whole-repository grep.
- **A probe is quoted with the machine, the commit, the project and the run it came from.**
- **Cite by name, not by line number.** Line numbers in this plan were measured at `5b50948`, and go stale the moment an earlier task edits the file.
- **Before ruling on a trade-off, confirm that both sides of it can actually happen.**

**Conventions**

- **Commits:** a lowercase imperative subject on **one line**, with no `feat:`-style prefix, and a body saying why. The trailer is `Co-Authored-By: <your model> <noreply@anthropic.com>`. Never `--amend`, never rebase.
- **Every UI pull request carries a screenshot of what it added,** the maintainer's standing rule. Open each new or changed reference and say what it shows, quoting from the image. "Updated N references" is not a report.
- **Subagents do not write report files;** they return findings as text.
- **If a brief or this plan is wrong, say so in your report** rather than working around it silently.
- **Bidi characters.** A unicode escape typed through the tools can land as the character itself: a right-to-left override did, twice, in part 18. Write such a character as words ("U+202E"), or build it in code with `chr()`. Before any push, scan the commit messages and the changed files for U+202A to U+202E and U+2066 to U+2069.

## Prerequisites

1. **The branch.** The work is on `feature/gui-token-header`, made from master `ee8a7eb` (part 18, PR #79). Its first commit is the spec, `5b50948`. Work in the main checkout `/home/sauci/Documents/Github/ddd`: Docker cannot see the session scratchpad.
2. **The baseline gate.** Run the milestone gate (below) once at `5b50948`, before Task 1, so that every later red is this part's own.
3. **Read the spec,** whose §1 and §2 say what the cookie was and what was read to find it.

## Review Focus

- **The asynchronous sign-in against the journeys.** 69 journeys open the printed address with `page.goto` and then act. The page now signs itself in after it has loaded, so the first element a journey waits for must come after the sign-in. No journey may act before the landing.
- **No `401` loop.** A `401` clears the token and marks the page signed out, and nothing asks again on its own. The long poll in flight then ends, and no second banner says why.
- **Every fetch stub.** Every Vitest test that checks what `request()` sent expects `credentials: "omit"`, and expects the header only where a token is kept.
- **The gate around `POST /open`.** It needs no credential, but it passes the gate and a `POST`'s rules. `GET /open` stays exempt from the gate, as it is today, and spends nothing.
- **The P18-10 warning on a `POST`.** A code that already signed a browser in prints the terminal's warning when it is presented again. An expired code, or one never issued, prints nothing.
- **A body nested past `json.loads`'s depth** is a malformed body (`400`), not a failure.
- **Part 18's hostile journey.** Its red case, the gate taken out, no longer shows the marker, because no credential reaches the server at all. The new journey is the one that shows the cookie's leak, red with the cookie put back (ruling 9).
- **Two origins.** `localhost:<port>` and `127.0.0.1:<port>` have separate storage. A reader who visits the other one is signed out there.
- **The screenshots.** One reference is added (`components--signedoutview--signed-out.png`), and none other moves.
- **CI's windows legs.** The server tests run there on Python 3.12, 3.13 and 3.14. The journeys run on Linux, with Chrome.

## File Structure

| File | Task | What |
| --- | --- | --- |
| `src/ddd/gui/server.py` | 1, 2, 3, 4 | the header, `POST /open`, `GET /open` answering the app, the pages credential-free, the cookie gone, the docstring |
| `tests/test_gui_server.py` | 1, 2, 3 | the sign-in, the header, the pages and the cookie, through real HTTP |
| `gui/src/api/token.ts`, `token.test.ts` | 2 | where the token is kept, and whether the server refused it |
| `gui/src/api/signIn.ts`, `signIn.test.ts` | 2 | the sign-in from the page's own address, and where it lands |
| `gui/src/api/client.ts`, `client.test.ts` | 2 | `request()` sending the header and no cookie, and a `401` signing the page out |
| `gui/src/components/SignedOutView.tsx`, `SignedOutView.stories.tsx` | 2 | what the page shows once signed out |
| `gui/screenshots/references/components--signedoutview--signed-out.png` | 2 | its reference |
| `gui/src/app/App.tsx`, `gui/src/main.tsx` | 2 | glue: sign in before rendering, and render the signed-out view |
| `gui/e2e/fixtures.ts` | 2 | the fixture asks with the header |
| `gui/e2e/loopback.spec.ts` | 3 | another server on `127.0.0.1` is sent nothing |
| `gui/e2e/hostile.spec.ts` | 3 | its comments: two defences now |
| `docs/gui_security.rst`, `CHANGELOG.md` | 4 | what is true after this part |

## Interfaces Between Tasks

**Task 1 produces:**
- `POST /open`, taking a json body of exactly one of `{"code": "<code>"}` and `{"token": "<token>"}`. It answers one of:
  - `200 {"token": "<token>"}`;
  - `403 {"error": "forbidden", "message": _SIGN_IN}`;
  - `400 {"error": "bad-request", "message": _OPEN_TAKES}`.
- The API taking `Authorization: Bearer <token>`: the scheme in any case, one space, then the token.
- In `server.py`: `_OPEN_TAKES: Final`, `_secret_of(body: bytes) -> tuple[str, str] | None`, `_Handler._exchange(body: bytes) -> None` and `_Handler._bearer() -> bool`.
- In `tests/test_gui_server.py`: `exchange(server, given, **keywords)` and `REFUSED`.

**Task 2 consumes Task 1's `POST /open`, and produces:**
- In `gui/src/api/token.ts`:
  - `TOKEN_KEY = "ddd-gui-token"`;
  - `interface Keeper { get(): string | null; set(token: string): void; clear(): void }`;
  - `keeperOver(storage: () => Storage): Keeper`, and its instance `token`;
  - `interface SignedOut { subscribe(listener: () => void): () => void; current(): boolean; mark(): void }`;
  - `signedOutStore(): SignedOut`, and its instance `signedOut`.
- In `gui/src/api/signIn.ts`:
  - `type Secret = { code: string } | { token: string }`;
  - `secretOf(pathname: string, search: string): Secret | null`;
  - `landingOf(session: SessionInfo): "/project" | "/"`;
  - `signInFrom(address: { pathname: string; search: string }, replace: (path: string) => void, kept?: Keeper, fetchImpl?: Fetch): Promise<void>`.
- In `gui/src/api/client.ts`: `request<T>(path, init?, fetchImpl?, kept?: Keeper, out?: SignedOut)`.
- `SignedOutView()`, with no props.
- On the server: `GET /open` answering `index.html` with `no-store`, and the pages served with no credential. `ask()` sends the bearer by default.

**Task 3 consumes `ask()`'s bearer default, and produces:**
- `_Handler._signed_in()`, which reads the header alone;
- the `loopback.spec.ts` journey.

**Task 4 consumes** the behaviour of Tasks 1 to 3, and describes it.

---

### Task 1: the server takes the token as a header, and trades a code for it

**Model:** opus (the sign-in's security edges). **Files:** `src/ddd/gui/server.py`, `tests/test_gui_server.py`.

**This is the expand step.** The cookie is still set by `GET /open` and still read. The server *also* takes `Authorization: Bearer`, and `POST /open` trades a code or the token for the token. Every existing test and journey stays green.

- [ ] **Step 1: Write the failing tests** in `tests/test_gui_server.py`.
  - Import `_OPEN_TAKES` from `ddd.gui.server`, beside the refusal sentences already imported.
  - Add, after `ask()`, which Task 2 turns to the header:

```python
def exchange(
    server: GuiServer, given: object, **keywords: Any
) -> tuple[http.client.HTTPResponse, bytes]:
    """``POST /open`` as the page posts it: from this server's own origin, as json, with no
    credential, since the sign-in is where the page gets one."""
    return ask(
        server,
        "POST",
        "/open",
        body=json.dumps(given).encode("utf-8"),
        origin=f"http://127.0.0.1:{server.port}",
        signed_in=False,
        **keywords,
    )


REFUSED: Final = {"error": "forbidden", "message": _SIGN_IN}
"""What ``POST /open`` answers a secret that signs nothing in."""
```

  - Add the two classes:

```python
class TestTheSignInExchange:
    """``POST /open``: the token, or a launch code, traded for the token the page then keeps
    and sends as ``Authorization: Bearer``."""

    def test_the_token_is_answered_with_itself(self, server) -> None:
        response, data = exchange(server, {"token": server.token})
        assert (response.status, json.loads(data)) == (200, {"token": server.token})
        assert response.getheader("Cache-Control") == "no-store"
        assert response.getheader("Set-Cookie") is None

    def test_a_launch_code_is_traded_for_the_token_once(self, server, capsys) -> None:
        code = server.issue_code()
        response, data = exchange(server, {"code": code})
        assert (response.status, json.loads(data)) == (200, {"token": server.token})
        assert capsys.readouterr().err == ""
        again, data = exchange(server, {"code": code})
        assert (again.status, json.loads(data)) == (403, REFUSED)
        assert capsys.readouterr().err == f"{_CODE_REUSED}\n"

    def test_a_wrong_code_is_refused_and_leaves_the_right_one_waiting(
        self, server, capsys
    ) -> None:
        code = server.issue_code()
        response, data = exchange(server, {"code": "wrong"})
        assert (response.status, json.loads(data)) == (403, REFUSED)
        assert capsys.readouterr().err == ""
        assert exchange(server, {"code": code})[0].status == 200

    def test_the_tokens_own_value_is_no_code(self, server) -> None:
        server.issue_code()
        response, data = exchange(server, {"code": server.token})
        assert (response.status, json.loads(data)) == (403, REFUSED)

    def test_a_code_to_a_server_that_issued_none_is_refused_without_a_word(
        self, server, capsys
    ) -> None:
        response, data = exchange(server, {"code": "anything"})
        assert (response.status, json.loads(data)) == (403, REFUSED)
        assert capsys.readouterr().err == ""

    def test_an_expired_code_is_refused_without_a_word(self, project_file, pages, capsys) -> None:
        clock = FakeClock()
        for started in serving(Api(Session(project_file.parent)), pages, clock=clock):
            code = started.issue_code()
            clock.now += CODE_SECONDS
            response, data = exchange(started, {"code": code})
            assert (response.status, json.loads(data)) == (403, REFUSED)
            assert capsys.readouterr().err == ""

    def test_a_code_still_signs_in_a_moment_before_its_60_seconds(
        self, project_file, pages
    ) -> None:
        clock = FakeClock()
        for started in serving(Api(Session(project_file.parent)), pages, clock=clock):
            code = started.issue_code()
            clock.now += CODE_SECONDS - 1
            assert exchange(started, {"code": code})[0].status == 200

    def test_a_wrong_token_is_refused(self, server) -> None:
        response, data = exchange(server, {"token": "wrong"})
        assert (response.status, json.loads(data)) == (403, REFUSED)

    @pytest.mark.parametrize(
        "given",
        [{}, {"code": "a", "token": "b"}, {"code": 1}, {"other": "x"}, ["code"], "code", None],
        ids=["empty", "both", "a-number", "a-stray-key", "a-list", "a-string", "null"],
    )
    def test_anything_but_one_secret_is_refused(self, server, given) -> None:
        response, data = exchange(server, given)
        assert (response.status, json.loads(data)) == (
            400,
            {"error": "bad-request", "message": _OPEN_TAKES},
        )

    @pytest.mark.parametrize(
        "body",
        [b"code=x", b"\xc3\x28", b"[" * 100_000 + b"]" * 100_000],
        ids=["a-form", "not-utf-8", "nested-past-the-parser"],
    )
    def test_a_body_that_is_no_json_object_is_refused_not_failed(self, server, body) -> None:
        response, data = ask(
            server,
            "POST",
            "/open",
            body=body,
            origin=f"http://127.0.0.1:{server.port}",
            signed_in=False,
        )
        assert (response.status, json.loads(data)) == (
            400,
            {"error": "bad-request", "message": _OPEN_TAKES},
        )

    def test_another_page_is_refused_at_the_gate(self, server) -> None:
        response, data = exchange(server, {"token": server.token}, headers={"Sec-Fetch-Site": "same-site"})
        assert (response.status, json.loads(data)) == (
            403,
            {"error": "forbidden", "message": _ELSEWHERE},
        )

    @pytest.mark.parametrize(
        ("origin", "kind"),
        [(None, "application/json"), ("own", "text/plain")],
        ids=["no-origin", "not-json"],
    )
    def test_it_is_a_post_like_any_other(self, server, origin, kind) -> None:
        response, data = ask(
            server,
            "POST",
            "/open",
            body=json.dumps({"token": server.token}).encode("utf-8"),
            origin=None if origin is None else f"http://127.0.0.1:{server.port}",
            content_type=kind,
            signed_in=False,
        )
        assert (response.status, json.loads(data)) == (
            403,
            {"error": "forbidden", "message": _FORBIDDEN},
        )


class TestTheBearerHeader:
    """The API takes the token as ``Authorization: Bearer``: the scheme in any case, as HTTP
    has it, then one space, then the token, compared in constant time."""

    @pytest.mark.parametrize("scheme", ["Bearer", "bearer", "BEARER"])
    def test_the_token_as_a_bearer_signs_a_request_in(self, server, scheme) -> None:
        response, _ = ask(
            server,
            "GET",
            "/api/session",
            signed_in=False,
            headers={"Authorization": f"{scheme} {server.token}"},
        )
        assert response.status == 200

    @pytest.mark.parametrize(
        "spelled",
        ["Bearer wrong", "Bearer  {token}", "Basic {token}", "{token}", "Bearer"],
        ids=["a-wrong-token", "two-spaces", "another-scheme", "no-scheme", "no-token"],
    )
    def test_anything_else_is_unauthorised(self, server, spelled) -> None:
        response, data = ask(
            server,
            "GET",
            "/api/session",
            signed_in=False,
            headers={"Authorization": spelled.format(token=server.token)},
        )
        assert (response.status, json.loads(data)) == (
            401,
            {"error": "unauthorised", "message": _SIGN_IN},
        )

    def test_no_cross_origin_preflight_is_answered(self, server) -> None:
        """A page on another origin can send ``Authorization`` only past a CORS preflight,
        which this server answers with nothing a browser accepts."""
        response, _ = ask(
            server,
            "OPTIONS",
            "/api/session",
            signed_in=False,
            headers={
                "Origin": "http://127.0.0.1:9",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )
        assert response.status == 501
        assert [n for n, _ in response.getheaders() if n.lower().startswith("access-control-")] == []
```

  `ruff format` will rewrap the long lines. Read every expected sentence off the running code.

- [ ] **Step 2: Run them, and watch them fail.**
  - Run: `.venv/bin/python -m pytest tests/test_gui_server.py -k "SignInExchange or BearerHeader" --no-cov -p no:cacheprovider`.
  - The collection fails first, on `_OPEN_TAKES`. Add the constant (Step 3's first block) and run again.
  - Expected: the exchange tests fail with `401` (no cookie), and the header tests that expect `200` fail. `test_no_cross_origin_preflight_is_answered` and the `401` cases pass already: they pin what holds today.

- [ ] **Step 3: Implement.**
  - **The constants,** in `server.py`, beside `_SIGN_IN`:

```python
_OPEN_TAKES: Final = "/open takes json naming one of code and token, and nothing else"
```

  - **Reading the body,** at module level:

```python
def _secret_of(body: bytes) -> tuple[str, str] | None:
    """What ``POST /open`` was given: ``("code", <code>)`` or ``("token", <token>)``, or
    ``None`` for anything but a json object of exactly one of the two, its value text. A body
    nested deeper than python's own parser goes raises ``RecursionError``, which is no
    ``ValueError``, and is refused as any other malformed body."""
    try:
        given = json.loads(body)
    except (ValueError, RecursionError):
        return None
    if not isinstance(given, dict) or len(given) != 1:
        return None
    ((kind, value),) = given.items()
    if kind not in ("code", "token") or not isinstance(value, str):
        return None
    return kind, value
```

  - **The header,** on `_Handler`:

```python
    def _bearer(self) -> bool:
        """Whether the request carries this server's token as ``Authorization: Bearer``: the
        scheme in any case, as HTTP has it, then one space, then the token, compared in
        constant time."""
        scheme, _, given = self.headers.get("Authorization", "").partition(" ")
        return scheme.lower() == "bearer" and hmac.compare_digest(
            given.encode("utf-8"), self._gui.token.encode("utf-8")
        )
```

  - **`_signed_in`:** rename the method that reads the cookie to `_cookie_holds_token`, keeping its docstring, and make `_signed_in` take either:

```python
    def _signed_in(self) -> bool:
        """Whether the request carries the token: as ``Authorization: Bearer``, which the page
        is to send, or in this server's cookie, which ``/open`` still sets until the page sends
        the header."""
        return self._bearer() or self._cookie_holds_token()
```

  - **The exchange,** on `_Handler`:

```python
    def _exchange(self, body: bytes) -> None:
        """``POST /open``: a launch code, or the token itself, traded for the token the page
        keeps and sends as ``Authorization: Bearer``. A code is spent the moment its value
        matches. One that already signed a browser in prints the terminal's warning when it is
        presented again, since the page that won it cleans it from its address and never
        presents it twice."""
        secret = _secret_of(body)
        if secret is None:
            self._send_json(400, {"error": "bad-request", "message": _OPEN_TAKES})
            return
        kind, given = secret
        if kind == "token":
            signed_in = hmac.compare_digest(
                given.encode("utf-8"), self._gui.token.encode("utf-8")
            )
        else:
            signed_in = self._gui.redeem_code(given)
            if not signed_in and self._gui.code_redeemed(given):
                print(_CODE_REUSED, file=sys.stderr)
        if signed_in:
            self._send_json(200, {"token": self._gui.token})
        else:
            self._send_json(403, {"error": "forbidden", "message": _SIGN_IN})
```

  - **The route.** In `_route`, after the gate's `if self._from_elsewhere(): ...` block and before `if not self._signed_in():`:

```python
        if url.path == "/open":
            # A POST alone: GET /open was answered above, before the gate. The sign-in needs
            # no credential, being where the page gets one, but it is a POST like any other:
            # this server's own page, as json.
            if not self._from_this_page():
                self._send_json(403, {"error": "forbidden", "message": _FORBIDDEN})
                return
            body = self._body()
            if body is not None:
                self._exchange(body)
            return
```

- [ ] **Step 4: Run the tests, then the whole Python gate.** They must pass, and so must everything else. The cookie still signs in.

- [ ] **Step 5: Ablate, in a scratch worktree** (`PYTHONDONTWRITEBYTECODE=1`, pytest run from inside it). Each must fail a named test:
  - (a) `_bearer` without its scheme check;
  - (b) the scheme compared with its case;
  - (c) `_exchange` without its warning;
  - (d) `_secret_of` catching `ValueError` alone;
  - (e) the `POST /open` branch moved before the gate;
  - (f) `_OPEN_TAKES` reworded.

- [ ] **Step 6: Commit.** Subject: `take the token as a bearer header beside the cookie, and trade a code for it at post /open`.

---

### Task 2: the page signs itself in, and sends the token as a header

**Model:** opus (server, page, journeys and a screenshot, in one commit). **Files:**
- Create: `gui/src/api/token.ts`, `gui/src/api/token.test.ts`, `gui/src/api/signIn.ts`, `gui/src/api/signIn.test.ts`, `gui/src/components/SignedOutView.tsx`, `gui/src/components/SignedOutView.stories.tsx`, `gui/screenshots/references/components--signedoutview--signed-out.png`
- Modify: `gui/src/api/client.ts`, `gui/src/api/client.test.ts`, `gui/src/app/App.tsx`, `gui/src/main.tsx`, `gui/e2e/fixtures.ts`, `src/ddd/gui/server.py`, `tests/test_gui_server.py`

**This is the switch, in one commit,** since a page that sends the header and a server that answers `GET /open` with the page only work together:
- the page signs itself in, and sends the header and no cookie;
- `GET /open` answers the page itself;
- the pages need no credential;
- nothing sets the cookie any more.

The server still *reads* a cookie, until Task 3.

- [ ] **Step 1: Write `gui/src/api/token.test.ts`.**

```ts
import { describe, expect, test, vi } from "vitest";
import { keeperOver, signedOutStore, TOKEN_KEY } from "./token";

/** A Storage keeping what it is given, as the browser's does. */
function memoryStorage(): Storage {
  const items = new Map<string, string>();
  return {
    get length() {
      return items.size;
    },
    clear: () => items.clear(),
    getItem: (key) => items.get(key) ?? null,
    key: (index) => [...items.keys()][index] ?? null,
    removeItem: (key) => {
      items.delete(key);
    },
    setItem: (key, value) => {
      items.set(key, value);
    },
  };
}

describe("where the token is kept", () => {
  test("in storage, under the page's own key", () => {
    const storage = memoryStorage();
    const kept = keeperOver(() => storage);
    expect(kept.get()).toBeNull();
    kept.set("t");
    expect(storage.getItem(TOKEN_KEY)).toBe("t");
    expect(kept.get()).toBe("t");
    kept.clear();
    expect(storage.getItem(TOKEN_KEY)).toBeNull();
    expect(kept.get()).toBeNull();
  });

  test("in the tab's memory once the browser refuses storage", () => {
    const kept = keeperOver(() => {
      throw new DOMException("denied", "SecurityError");
    });
    expect(kept.get()).toBeNull();
    kept.set("t");
    expect(kept.get()).toBe("t");
    kept.clear();
    expect(kept.get()).toBeNull();
  });

  test("a write storage refuses moves the token to memory, and keeps it there", () => {
    const storage = memoryStorage();
    storage.setItem = () => {
      throw new DOMException("full", "QuotaExceededError");
    };
    const kept = keeperOver(() => storage);
    kept.set("t");
    expect(kept.get()).toBe("t");
  });
});

describe("whether the server refused the token", () => {
  test("is false until marked, and tells each listener once", () => {
    const out = signedOutStore();
    const heard = vi.fn();
    const stop = out.subscribe(heard);
    expect(out.current()).toBe(false);
    out.mark();
    out.mark();
    expect(out.current()).toBe(true);
    expect(heard).toHaveBeenCalledTimes(1);
    stop();
  });

  test("a listener that stopped hears nothing", () => {
    const out = signedOutStore();
    const heard = vi.fn();
    out.subscribe(heard)();
    out.mark();
    expect(heard).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Write `gui/src/api/signIn.test.ts`.** Build the session as the contract has it: `version`, `preview`, `root`, and a `project` of `path` and `name`, or `null`.

```ts
import { describe, expect, test, vi } from "vitest";
import { landingOf, secretOf, signInFrom } from "./signIn";
import { keeperOver } from "./token";
import type { SessionInfo } from "./types";

const STARTED: SessionInfo = { version: "0.11.0", preview: true, root: "/w", project: null };
const OPENED: SessionInfo = { ...STARTED, project: { path: "/w/p.ddd.json", name: "P" } };

/** A keeper of the tab's own memory, as a browser refusing storage leaves the page. */
const remembering = () =>
  keeperOver(() => {
    throw new Error("no storage here");
  });

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status });

describe("the secret an address carries", () => {
  test("a launch's code", () => expect(secretOf("/open", "?code=c")).toEqual({ code: "c" }));
  test("the printed address's token", () =>
    expect(secretOf("/open", "?token=t")).toEqual({ token: "t" }));
  test("the code, where an address carries both", () =>
    expect(secretOf("/open", "?token=t&code=c")).toEqual({ code: "c" }));
  test("nothing, where both are blank", () =>
    expect(secretOf("/open", "?code=&token=")).toBeNull());
  test("nothing, anywhere but /open", () => expect(secretOf("/project", "?token=t")).toBeNull());
});

describe("where the page lands once signed in", () => {
  test("on the open project", () => expect(landingOf(OPENED)).toBe("/project"));
  test("on the start page, with no project open", () => expect(landingOf(STARTED)).toBe("/"));
});

describe("signing in from the page's own address", () => {
  test("the address is cleaned before the secret is sent anywhere", async () => {
    const order: string[] = [];
    const replace = vi.fn((path: string) => order.push(`replace ${path}`));
    const fetchImpl = vi.fn(async (path: string) => {
      order.push(`fetch ${path}`);
      return path === "/open" ? json(200, { token: "t" }) : json(200, STARTED);
    });
    await signInFrom({ pathname: "/open", search: "?code=c" }, replace, remembering(), fetchImpl);
    expect(order.slice(0, 2)).toEqual(["replace /", "fetch /open"]);
  });

  test("the secret is posted as json, with no cookie", async () => {
    const fetchImpl = vi.fn(async (path: string) =>
      path === "/open" ? json(200, { token: "t" }) : json(200, STARTED),
    );
    await signInFrom({ pathname: "/open", search: "?code=c" }, vi.fn(), remembering(), fetchImpl);
    expect(fetchImpl).toHaveBeenNthCalledWith(1, "/open", {
      method: "POST",
      credentials: "omit",
      headers: { "Content-Type": "application/json" },
      body: '{"code":"c"}',
    });
  });

  test("the token answered is kept, and the page lands on the open project", async () => {
    const kept = remembering();
    const replace = vi.fn();
    const fetchImpl = vi.fn(async (path: string) =>
      path === "/open" ? json(200, { token: "t" }) : json(200, OPENED),
    );
    await signInFrom({ pathname: "/open", search: "?token=t" }, replace, kept, fetchImpl);
    expect(kept.get()).toBe("t");
    expect(replace.mock.calls).toEqual([["/"], ["/project"]]);
    expect(fetchImpl).toHaveBeenNthCalledWith(2, "/api/session", {
      credentials: "omit",
      headers: { Authorization: "Bearer t" },
    });
  });

  test("with no project open, the page lands on the start page", async () => {
    const replace = vi.fn();
    const fetchImpl = vi.fn(async (path: string) =>
      path === "/open" ? json(200, { token: "t" }) : json(200, STARTED),
    );
    await signInFrom({ pathname: "/open", search: "?token=t" }, replace, remembering(), fetchImpl);
    expect(replace.mock.calls).toEqual([["/"], ["/"]]);
  });

  test("a refusal clears whatever token was kept", async () => {
    const kept = remembering();
    kept.set("stale");
    const fetchImpl = vi.fn(async () =>
      json(403, { error: "forbidden", message: "open the address ddd gui printed in its terminal" }),
    );
    await signInFrom({ pathname: "/open", search: "?code=c" }, vi.fn(), kept, fetchImpl);
    expect(kept.get()).toBeNull();
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  test("an answer that holds no token keeps none", async () => {
    const kept = remembering();
    await signInFrom({ pathname: "/open", search: "?code=c" }, vi.fn(), kept, async () =>
      json(200, { other: "x" }),
    );
    expect(kept.get()).toBeNull();
  });

  test("a server not answering leaves what was kept as it was", async () => {
    const kept = remembering();
    kept.set("t");
    await signInFrom({ pathname: "/open", search: "?code=c" }, vi.fn(), kept, async () => {
      throw new TypeError("Failed to fetch");
    });
    expect(kept.get()).toBe("t");
  });

  test("a session that does not answer keeps the token, and lands nowhere new", async () => {
    const kept = remembering();
    const replace = vi.fn();
    const fetchImpl = vi.fn(async (path: string) => {
      if (path === "/open") return json(200, { token: "t" });
      throw new TypeError("Failed to fetch");
    });
    await signInFrom({ pathname: "/open", search: "?token=t" }, replace, kept, fetchImpl);
    expect(kept.get()).toBe("t");
    expect(replace.mock.calls).toEqual([["/"]]);
  });

  test("/open with no secret is cleaned, and nothing is asked", async () => {
    const replace = vi.fn();
    const fetchImpl = vi.fn();
    await signInFrom({ pathname: "/open", search: "" }, replace, remembering(), fetchImpl);
    expect(replace.mock.calls).toEqual([["/"]]);
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  test("any other address is left alone, and nothing is asked", async () => {
    const replace = vi.fn();
    const fetchImpl = vi.fn();
    await signInFrom({ pathname: "/project", search: "" }, replace, remembering(), fetchImpl);
    expect(replace).not.toHaveBeenCalled();
    expect(fetchImpl).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 3: Change `gui/src/api/client.test.ts`.**
  - Every expectation of `{ credentials: "same-origin" }` becomes `{ credentials: "omit" }`. The module's own `token` keeper is never set by a test, and in Node, where Vitest runs, it keeps nothing.
  - The first test is renamed "a success is its parsed body, asked for with no cookie".
  - Add:

```ts
describe("the token, as a header", () => {
  const remembering = () =>
    keeperOver(() => {
      throw new Error("no storage here");
    });

  test("goes with every request once the page keeps one", async () => {
    const kept = remembering();
    kept.set("t");
    const fetchImpl = answering(200, "{}");
    await request("/api/session", {}, fetchImpl, kept);
    expect(fetchImpl).toHaveBeenCalledWith("/api/session", {
      credentials: "omit",
      headers: { Authorization: "Bearer t" },
    });
  });

  test("goes beside a post's own header", async () => {
    const kept = remembering();
    kept.set("t");
    const fetchImpl = answering(200, "{}");
    await request(
      "/api/undo",
      { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" },
      fetchImpl,
      kept,
    );
    expect(fetchImpl).toHaveBeenCalledWith("/api/undo", {
      method: "POST",
      credentials: "omit",
      headers: { "Content-Type": "application/json", Authorization: "Bearer t" },
      body: "{}",
    });
  });

  test("a 401 clears it and signs the page out, and nothing asks again", async () => {
    const kept = remembering();
    kept.set("stale");
    const out = signedOutStore();
    const fetchImpl = answering(
      401,
      '{"error": "unauthorised", "message": "open the address ddd gui printed in its terminal"}',
    );
    await expect(request("/api/state", {}, fetchImpl, kept, out)).rejects.toMatchObject({
      status: 401,
      code: "unauthorised",
      message: "open the address ddd gui printed in its terminal",
    });
    expect(kept.get()).toBeNull();
    expect(out.current()).toBe(true);
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  test("any other refusal leaves the page signed in", async () => {
    const kept = remembering();
    kept.set("t");
    const out = signedOutStore();
    await expect(
      request("/api/state", {}, answering(409, '{"error": "no-project", "message": "m"}'), kept, out),
    ).rejects.toMatchObject({ status: 409 });
    expect(kept.get()).toBe("t");
    expect(out.current()).toBe(false);
  });
});
```

  Import `keeperOver` and `signedOutStore` from `./token`.

- [ ] **Step 4: Run the page's tests, and watch them fail.** Run `cd gui && npm test`. The two new files fail to import their modules, and the client's expectations fail on `same-origin`.

- [ ] **Step 5: Write `gui/src/api/token.ts`.**

```ts
/** Where the page keeps the token `ddd gui` traded for its address, and whether the server has
 * since refused it.
 *
 * Kept in `localStorage` for the page's own origin, `http://127.0.0.1:<port>`, port included: no
 * server on another port of 127.0.0.1 is sent it, or can read it. A cookie, which `ddd gui`
 * signed a page in with before, is sent to every port of the address (part 18b's spec, §1). */

/** The key the token is kept under. The origin, port and all, keeps two servers' tokens apart. */
export const TOKEN_KEY = "ddd-gui-token";

export interface Keeper {
  get(): string | null;
  set(token: string): void;
  clear(): void;
}

/** A keeper over `storage()`, which moves to the tab's own memory the first time storage
 * throws: in a private window, under a policy, or with its quota full. The tab then stays
 * signed in until it closes. */
export function keeperOver(storage: () => Storage): Keeper {
  let usable = true;
  let memory: string | null = null;
  function using<T>(stored: (store: Storage) => T, remembered: () => T): T {
    if (usable) {
      try {
        return stored(storage());
      } catch {
        usable = false;
      }
    }
    return remembered();
  }
  return {
    get: () => using((store) => store.getItem(TOKEN_KEY), () => memory),
    set: (token) =>
      using(
        (store) => store.setItem(TOKEN_KEY, token),
        () => {
          memory = token;
        },
      ),
    clear: () =>
      using(
        (store) => store.removeItem(TOKEN_KEY),
        () => {
          memory = null;
        },
      ),
  };
}

/** The page's own keeper. */
export const token: Keeper = keeperOver(() => window.localStorage);

export interface SignedOut {
  subscribe(listener: () => void): () => void;
  current(): boolean;
  mark(): void;
}

/** Whether the server has refused the page's token since the page loaded. Once marked, the
 * page shows it is signed out and asks nothing more: nothing retries. */
export function signedOutStore(): SignedOut {
  let out = false;
  const listeners = new Set<() => void>();
  return {
    subscribe(listener) {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    current: () => out,
    mark() {
      if (out) return;
      out = true;
      for (const listener of listeners) listener();
    },
  };
}

/** The page's own. */
export const signedOut: SignedOut = signedOutStore();
```

- [ ] **Step 6: Change `request()` in `gui/src/api/client.ts`.**
  - The init it takes has plain-record headers. `post()` already builds them so, and needs only its new return type.
  - The header goes beside them, and `credentials` is always `"omit"`.
  - A `401` clears the token and signs the page out.

```ts
import { type Keeper, type SignedOut, signedOut, token } from "./token";

/** What `request` is asked with: a `RequestInit` whose headers are a plain record, as every
 * caller here builds them, so that the token's header is added beside them. */
export type Ask = Omit<RequestInit, "headers"> & { headers?: Record<string, string> };

export async function request<T>(
  path: string,
  init: Ask = {},
  fetchImpl: Fetch = fetch,
  kept: Keeper = token,
  out: SignedOut = signedOut,
): Promise<T> {
  // The token goes as a header, and no cookie goes at all: a browser sends a cookie to every
  // port of 127.0.0.1, so to every other server there too (part 18b).
  const held = kept.get();
  const headers = held === null ? init.headers : { ...init.headers, Authorization: `Bearer ${held}` };
  let response: Response;
  try {
    response = await fetchImpl(path, {
      ...init,
      credentials: "omit",
      ...(headers === undefined ? {} : { headers }),
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ServerUnreachable(error);
  }
  const body: unknown = await response.json().catch(() => NOT_JSON);
  if (!response.ok) {
    if (response.status === 401) {
      // Refused: the token kept is stale, or there is none. It is cleared, and the page says
      // it is signed out. Nothing asks again on its own, and other tabs follow on their next
      // ask, since they read the same storage.
      kept.clear();
      out.mark();
    }
    // ...the rest of the refusal, as before
```

  `post()` returns `Ask` rather than `RequestInit`.

- [ ] **Step 7: Write `gui/src/api/signIn.ts`.**

```ts
import { request } from "./client";
import { type Keeper, token } from "./token";
import type { SessionInfo } from "./types";

type Fetch = (path: string, init?: RequestInit) => Promise<Response>;

/** What an address at /open signs the page in with. */
export type Secret = { code: string } | { token: string };

/** The secret an address at /open carries: its code if it has one, which is the launch's, and
 * its token otherwise, which is the printed address, pasted. */
export function secretOf(pathname: string, search: string): Secret | null {
  if (pathname !== "/open") return null;
  const query = new URLSearchParams(search);
  const code = query.get("code");
  if (code) return { code };
  const token = query.get("token");
  if (token) return { token };
  return null;
}

/** Where the page lands once signed in: the open project's page, or the start page, as the
 * page `/open` answered with before part 18b refreshed to. */
export function landingOf(session: SessionInfo): "/project" | "/" {
  return session.project === null ? "/" : "/project";
}

function isTokenReply(body: unknown): body is { token: string } {
  return (
    typeof body === "object" && body !== null && "token" in body && typeof body.token === "string"
  );
}

/** Sign the page in from its own address, before it asks the server anything else.
 *
 * An address at /open loses its secret the moment it is read, before the secret is sent
 * anywhere, so that it stays in no history. The secret is posted to /open, and the token
 * answered is kept. A refusal clears any token kept: the page then asks as it is, is answered
 * 401, and says it is signed out. */
export async function signInFrom(
  address: { pathname: string; search: string },
  replace: (path: string) => void,
  kept: Keeper = token,
  fetchImpl: Fetch = fetch,
): Promise<void> {
  if (address.pathname !== "/open") return;
  const secret = secretOf(address.pathname, address.search);
  replace("/");
  if (secret === null) return;
  let response: Response;
  try {
    response = await fetchImpl("/open", {
      method: "POST",
      credentials: "omit",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(secret),
    });
  } catch {
    // Not answering: the page's first ask says so.
    return;
  }
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok || !isTokenReply(body)) {
    kept.clear();
    return;
  }
  kept.set(body.token);
  try {
    replace(landingOf(await request<SessionInfo>("/api/session", {}, fetchImpl, kept)));
  } catch {
    // The page's own first ask meets the same failure, and says so.
  }
}
```

- [ ] **Step 8: Run the page's tests until they pass,** with Vitest at 100 % on all four metrics over `src/api`, `src/lib` and `src/state`.

- [ ] **Step 9: Write `gui/src/components/SignedOutView.tsx` and its story.**

```tsx
import { Banner } from "../ui/Banner";

/** What the page shows once the server has refused its token, or it kept none: the address
 * `ddd gui` printed signs it in again. The sentence is the server's own refusal's. */
export function SignedOutView() {
  return (
    <main>
      <Banner tone="warning">
        Open the address <code>ddd gui</code> printed in its terminal.
      </Banner>
    </main>
  );
}
```

```tsx
import { SignedOutView } from "./SignedOutView";

export default { title: "Components / SignedOutView" };

/** The page once the server has refused its token. */
export const SignedOut = () => <SignedOutView />;
```

- [ ] **Step 10: The glue.** No decision goes here.
  - **`gui/src/main.tsx`** signs in before it renders, so that no ask goes out without the token:

```tsx
import { signInFrom } from "./api/signIn";
// ...
void signInFrom(window.location, (path) => window.history.replaceState(null, "", path)).then(
  () => {
    createRoot(root).render(
      // ...the same tree as before
    );
  },
);
```

  - **`gui/src/app/App.tsx`:**
    - Read `const out = useSyncExternalStore(signedOut.subscribe, signedOut.current);` among its other hooks.
    - After its last hook, and before `let page: ReactNode;`, add `if (out) return <SignedOutView />;`.
    - Check that no hook follows that line.

- [ ] **Step 11: The server, `GET /open` answering the page.** In `server.py`:
  - **`_page`** takes `headers: dict[str, str] | None = None` and hands them to `_send`.
  - **The `GET /open` branch** of `_route` becomes:

```python
        if method == "GET" and url.path == "/open":
            # The page itself, which signs itself in: it reads the code or the token from this
            # address, posts it to /open, and keeps the token it is answered. Nothing is checked
            # or spent on a GET, so a browser's prefetch of the launch address spends no code.
            # The address holds a secret, so the answer is never stored.
            self._page("/", {"Cache-Control": "no-store"})
            return
```

  - **The pages need no credential.** Move the `if not api:` block above the `_signed_in()` check, so that the check and its `401` concern the API alone. The `401` sign-in page for a page goes, and so does every use of `SIGN_IN_PAGE` but the gate's `403`.
  - **Delete `_sign_in` and `SIGNED_IN_PAGE`.** Nothing sets the cookie now.

- [ ] **Step 12: The server's tests.**
  - **`ask()`'s `signed_in=True`** sends `Authorization: Bearer <token>` and no cookie.
  - **Delete the tests of the `GET` sign-in,** which Task 1's `TestTheSignInExchange` replaces:
    - `test_the_token_is_swapped_for_a_strict_cookie_and_the_project_page`;
    - `test_the_page_refreshes_to_its_target_without_a_script`;
    - `test_a_project_being_analysed_signs_in_to_its_own_page`;
    - `test_without_an_open_project_the_page_refreshes_to_the_start_page`;
    - `test_a_wrong_or_missing_token_is_refused`;
    - `test_a_code_is_as_strong_as_the_token`;
    - `test_a_code_signs_a_browser_in_exactly_as_the_token_does`;
    - `test_a_code_signs_in_once_and_a_second_presentation_is_refused`;
    - `test_a_wrong_code_is_refused_and_leaves_the_right_one_waiting`;
    - `test_a_spent_code_already_signed_in_answers_the_page_not_a_refusal`;
    - `test_the_tokens_own_value_is_not_accepted_as_a_code`;
    - `test_an_unused_code_expires_after_60_seconds`;
    - `test_a_code_to_a_server_that_never_issued_one_is_refused_without_a_word`;
    - `test_a_code_that_signed_a_browser_in_says_why_to_restart_when_presented_again`;
    - `test_a_code_still_signs_in_a_moment_before_60_seconds`;
    - `test_a_page_without_the_cookie_says_where_to_sign_in`.
  - **Keep** `redeem_code`'s two lock tests.
  - **Rewrite `TestTheLaunch`'s one `GET /open?code=` ask** as `exchange(server, {"code": code})`.
  - **Add:**

```python
class TestTheAddressPrinted:
    """``GET /open`` answers the page itself, which signs itself in, and checks and spends
    nothing: a browser's prefetch of the launch address spends no code."""

    @pytest.mark.parametrize(
        "query",
        ["code={code}", "token={token}", "code=wrong", ""],
        ids=["the-launch", "the-printed-address", "a-wrong-code", "nothing"],
    )
    def test_open_answers_the_page_and_spends_nothing(self, server, pages, query) -> None:
        code = server.issue_code()
        response, data = ask(
            server,
            "GET",
            "/open?" + query.format(code=code, token=server.token),
            signed_in=False,
        )
        assert response.status == 200
        assert data == (pages / "index.html").read_bytes()
        assert response.getheader("Cache-Control") == "no-store"
        assert response.getheader("Set-Cookie") is None
        assert exchange(server, {"code": code})[0].status == 200

    @pytest.mark.parametrize("path", ["/", "/project", "/app.js"])
    def test_a_page_needs_no_credential(self, server, pages, path) -> None:
        response, _ = ask(server, "GET", path, signed_in=False)
        assert response.status == 200

    def test_no_answer_sets_a_cookie(self, server) -> None:
        answers = [
            ask(server, "GET", f"/open?token={server.token}", signed_in=False)[0],
            exchange(server, {"token": server.token})[0],
            ask(server, "GET", "/project", signed_in=False)[0],
            ask(server, "GET", "/api/session")[0],
        ]
        assert [answer.getheader("Set-Cookie") for answer in answers] == [None] * 4
```

- [ ] **Step 13: The journeys' fixture.** `analysed()` in `gui/e2e/fixtures.ts` asks with the header, read off the printed address:

```ts
async function analysed(address: string): Promise<void> {
  // The token the printed address carries, sent as the page sends it. Nothing sets a cookie
  // any more (part 18b).
  const token = new URL(address).searchParams.get("token");
  if (token === null) throw new Error(`ddd gui printed an address with no token: ${address}`);
  const headers = { authorization: `Bearer ${token}` };
  let after: number | null = null;
  // ...the loop as before
```

- [ ] **Step 14: The screenshot reference.**
  1. Run `UPDATE=1 docker compose run --rm gui-screenshots`.
  2. `git status --short gui/screenshots/references` must show `components--signedoutview--signed-out.png` alone.
  3. Open it, and say what it shows, quoting from the image.
  4. Run without `UPDATE=1`: 160 passed, none moved.

- [ ] **Step 15: Every gate.**
  - the Python gate;
  - the page gate: lint, typecheck, Vitest at 100 %, build and ladle;
  - `npm run build`, then every journey, alone: the 88 must pass with the page signing itself in;
  - the screenshots, as in Step 14.

- [ ] **Step 16: Ablate.**
  - The page in place, checking `git status --porcelain` before every restore. Each must fail a named test:
    - (a) `request()` without the header;
    - (b) `signInFrom` cleaning the address after the `POST`, not before;
    - (c) a `401` leaving the token;
    - (d) `landingOf` the other way round.
  - The server in a scratch worktree: (e) `GET /open` spending the code, by calling `redeem_code`, must fail a named test.

- [ ] **Step 17: Commit.** Subject: `sign the page in itself and send the token as a header, the pages needing none`.

---

### Task 3: a cookie is no credential, and another server on 127.0.0.1 is sent nothing

**Model:** opus. **Files:** `src/ddd/gui/server.py`, `tests/test_gui_server.py`, `gui/e2e/loopback.spec.ts` (new), `gui/e2e/hostile.spec.ts`.

**This is the contract step.** The server stops reading the cookie, and its leftovers go. A journey pins what this part is for: another server on `127.0.0.1` is sent nothing of `ddd gui`'s.

- [ ] **Step 1: Write the journey `gui/e2e/loopback.spec.ts`.**

```ts
import type { IncomingHttpHeaders } from "node:http";
import { createServer } from "node:http";
import type { AddressInfo } from "node:net";
import { expect, test } from "./fixtures";

// Part 18b's reason: a browser sends a cookie to every port of 127.0.0.1, and ddd gui's cookie
// was its token. Signed in through the printed address, the browser is taken to a server of
// its own on another port of the address, whose page then asks that server again, as any page
// landed on there may. That server records every header of every request, and the token is in
// none of them: no cookie carries it, and the page's own storage is out of this origin's reach.
test("another server on 127.0.0.1 is sent nothing of ddd gui's", async ({ page, gui }) => {
  const token = new URL(gui.address).searchParams.get("token");
  if (token === null) throw new Error(`ddd gui printed an address with no token: ${gui.address}`);
  await page.goto(gui.address);
  await page.waitForURL(/\/project$/);

  const seen: IncomingHttpHeaders[] = [];
  const other = createServer((request, response) => {
    seen.push(request.headers);
    if (request.url === "/") {
      response.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
      response.end(
        '<!doctype html><title>other</title><script>fetch("/again", { credentials: "include" })' +
          '.finally(() => { document.title = "asked"; });</script>',
      );
    } else {
      response.writeHead(204);
      response.end();
    }
  });
  await new Promise<void>((resolve) => other.listen(0, "127.0.0.1", resolve));
  try {
    const { port } = other.address() as AddressInfo;
    await page.goto(`http://127.0.0.1:${port}/`);
    await expect(page).toHaveTitle("asked");
    expect(seen.map((headers) => headers.host)).toContain(`127.0.0.1:${port}`);
    expect(seen.length).toBeGreaterThanOrEqual(2);
    for (const headers of seen) expect(JSON.stringify(headers)).not.toContain(token);
  } finally {
    other.closeAllConnections();
    await new Promise<void>((resolve) => other.close(() => resolve()));
  }
});
```

- [ ] **Step 2: Watch it red with the cookie set again, in place.**
  - **Why not master's `server.py` whole:** it reads no header, so the fixture's own poll of `/api/state`, which sends the header since Task 2, would fail before the journey ran.
  - The red is therefore the cookie put back, alone:
    1. With Task 2 committed and the tree clean, add to the `GET /open` branch of `_route`, in place, the cookie master's `/open` set:

```python
            self._page(
                "/",
                {
                    "Cache-Control": "no-store",
                    "Set-Cookie": (
                        f"ddd-gui-{self._gui.port}={self._gui.token}; HttpOnly; SameSite=Strict; Path=/"
                    ),
                },
            )
```

    2. The journeys start the server from the source, so no build is needed. Run the journey alone: `PLAYWRIGHT_CHANNEL=chrome DDD_PYTHON="$PWD/../.venv/bin/python" npx playwright test e2e/loopback.spec.ts --output=<scratch>`. It must fail, the token showing up in a `cookie` header.
    3. Quote the failing run.
    4. Run `git status --porcelain`: only `src/ddd/gui/server.py` may show. Restore it with `git checkout HEAD -- src/ddd/gui/server.py`, and grep for `Set-Cookie`, which must be gone.

- [ ] **Step 3: Write the failing server test.**

```python
class TestACookie:
    """A cookie is no credential: a browser sends every cookie of 127.0.0.1 to every port of
    it, and so to every other server there (part 18b)."""

    @pytest.mark.parametrize(
        "cookie",
        ["ddd-gui-{port}={token}", "ddd-gui={token}", "{foreign}; ddd-gui-{port}={token}"],
        ids=["this-servers-old-name", "the-name-before-ports", "beside-others"],
    )
    def test_a_cookie_holding_the_token_is_no_credential(self, server, cookie) -> None:
        response, data = ask(
            server,
            "GET",
            "/api/session",
            signed_in=False,
            headers={
                "Cookie": cookie.format(
                    port=server.port, token=server.token, foreign='prefs={"lang":"en"}'
                )
            },
        )
        assert (response.status, json.loads(data)) == (
            401,
            {"error": "unauthorised", "message": _SIGN_IN},
        )

    def test_cookies_beside_the_header_are_passed_over(self, server) -> None:
        response, _ = ask(
            server, "GET", "/api/session", headers={"Cookie": "; ".join(FOREIGN_COOKIES)}
        )
        assert response.status == 200
```

  It fails at Task 2's head, where the cookie still signs a request in: `200` for `401`.

- [ ] **Step 4: Implement.**
  - **`_signed_in` reads the header alone.** It becomes what `_bearer` was. `_bearer` and `_cookie_holds_token` go.

```python
    def _signed_in(self) -> bool:
        """Whether the request carries this server's token as ``Authorization: Bearer``: the
        scheme in any case, as HTTP has it, then one space, then the token, compared in
        constant time. A cookie is no credential: a browser sends every cookie of 127.0.0.1 to
        every port of it, and so to every other server there."""
        scheme, _, given = self.headers.get("Authorization", "").partition(" ")
        return scheme.lower() == "bearer" and hmac.compare_digest(
            given.encode("utf-8"), self._gui.token.encode("utf-8")
        )
```

  - **What goes with the cookie:**
    - `COOKIE` and `GuiServer.cookie`;
    - the sentence of `GuiServer.address`'s docstring about the cookie. It now says the token in the address is what the page signs in with.
  - **The tests that read the cookie** go:
    - `test_a_cookie_with_another_value_is_not_signed_in`;
    - `test_a_second_server_signs_in_under_a_name_of_its_own`;
    - `test_a_cookie_another_app_set_does_not_get_in_the_way`;
    - `test_cookies_of_other_apps_alone_are_not_signed_in`;
    - `test_a_stale_cookie_of_this_servers_name_beside_the_right_one_signs_in`;
    - the `cookie()` helper.

    `FOREIGN_COOKIES` stays, for the test above.
  - **Rename** `test_the_api_without_the_cookie_is_unauthorised` to `test_the_api_without_the_token_is_unauthorised`.
  - **Any other test that names the cookie** in its body or docstring is made true, or goes. Grep `tests/test_gui_server.py` for `cookie`.

- [ ] **Step 5: Part 18's hostile journey.** `gui/e2e/hostile.spec.ts` keeps its assertion. Its comments say that two defences now hold it, and say what is true:
  - the page on another port carries no credential, since no cookie exists and the token is out of its origin's reach;
  - the gate refuses the request anyway.

  Its red case, the gate taken out, no longer shows the marker. The leak it guarded against is pinned by `loopback.spec.ts`.

- [ ] **Step 6: Every gate.** The Python gate, then `npm run build` and every journey alone: 89, with the new one.

- [ ] **Step 7: Ablate, in a scratch worktree** for the server: (a) `_signed_in` reading the cookie again must fail `test_a_cookie_holding_the_token_is_no_credential`.

- [ ] **Step 8: Commit.** Subject: `read the token from the header alone, and prove another server on 127.0.0.1 is sent nothing`.

---

### Task 4: what the security page, the CHANGELOG and the server's docstring say

**Model:** sonnet. **Files:** `docs/gui_security.rst`, `CHANGELOG.md`, `src/ddd/gui/server.py` (its module docstring).

Every sentence must be true of the code at the task's head. Read `server.py` and `gui/src/api/signIn.ts` and `token.ts` before writing.

- [ ] **Step 1: `docs/gui_security.rst`.**
  - **What it defends against:**
    - The page on another port. A browser treats every port of an address as the same site, but the token is no cookie. The page keeps it in storage of its own origin, port included, and sends it as a header. A page elsewhere cannot send that header without a CORS preflight, which `ddd gui` never grants. So in any browser, old ones included, such a page's request reaches the API with no credential, and is answered `401`. The gate (`Sec-Fetch-Site`, `Origin`) stays as a second defence.
    - The bullet *Another server on* `127.0.0.1` moves here from *What it does not defend against*. Such a server is sent nothing, since no cookie exists, and it cannot read another origin's storage.
  - **What it trusts:** the page's own origin. The token is in its `localStorage`, readable by its scripts alone, and the content security policy lets no script but `ddd gui`'s own run there.
  - **The browsers it protects.** The paragraph on older browsers says what holds now: such a browser's cross-site request carries no credential. The note on browsers older than SameSite goes, with the cookie it was about.
  - **The launch:**
    - `/open` answers the page, which posts the code or the token to `/open` and keeps the token it is answered.
    - Nothing is spent on a `GET`, so a prefetch spends no code.
    - The launch-code race stays as it is written.
  - **Every route:** the sentence on `/open` covers both methods. `GET /open` answers the page; `POST /open` trades a code or the token for the token. Neither needs a credential, and the `POST` passes the gate and a `POST`'s rules. The pages need none either; every route of the API needs the token as a header.
- [ ] **Step 2: `CHANGELOG.md`,** under `## Unreleased`.
  - Make part 18's entries true. The gate's entry says the token, not the cookie. The launch's entry stands.
  - Add one entry, in the file's own style (two spaces after the bold lead and between sentences):

```markdown
* **`ddd gui`'s token is no longer a cookie.**  A browser sends a cookie to every port of
  `127.0.0.1`, so any other server there that the reader's browser visited was sent the token.
  The page now keeps the token in the browser's storage for its own address, port included, and
  sends it as a header; a page elsewhere cannot send that header at all, in any browser.  The
  pages themselves need no credential, and a cookie is no credential any more.
```

- [ ] **Step 3: `server.py`'s module docstring.** Its first bullet says what is true now:
  - the address carries the token;
  - the page trades it, or the launch's code, at `/open` for the token it keeps;
  - it sends the token as `Authorization: Bearer` on every request to the API;
  - no cookie is set or read, since a browser sends a cookie to every port of `127.0.0.1`.

  The gate's bullet drops "before the cookie".

- [ ] **Step 4: Every gate:** the Python gate, including the route table's test, then the docs build, alone.

- [ ] **Step 5: Commit.** Subject: `say what ddd gui defends now that its token is no cookie`.

---

### Task 5: the figures after, and the milestone gate

**Model:** the controller's own.

- [ ] **Step 1: Run the probes** below, before (`ee8a7eb`) and after (the branch's head), on the Linux development PC, against a scratch `ddd gui` over a copy of `examples/demo`. Record each in *Figures*.
- [ ] **Step 2: Run the milestone gate,** with every exit status captured.
- [ ] **Step 3: Close the plan out:**
  - the *As built* note under the header;
  - the progress log;
  - *What was left open*;
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

Before any push, scan the branch's commit messages and changed files for bidi characters (Global Constraints).

## Figures

### Probes, before and after

Asked against a scratch `ddd gui demo/demo.ddd.json --no-browser` over a copy of `examples/demo`, signed in as each commit signs in, on the Linux development PC. "Before" is master `ee8a7eb`; "after" is the branch's head. Filled in by Task 5.

| asked | before | after |
| --- | --- | --- |
| `GET /open?token=<token>`: does its answer set a cookie holding the token? | | |
| `GET /api/session` with that cookie alone | | |
| An older browser's cross-site `GET /api/compare?baseline=<the demo's description>`: the cookie, no `Sec-Fetch-Site`, no `Origin` | | |
| A prefetch of the launch address, then the browser's own sign-in with the same code | | |
| `loopback.spec.ts`: another server on `127.0.0.1` sent the token | | |
| `ddd gui` started with `BROWSER` naming a stub: what the stub is handed | | |

## Progress log

| Task | Commits | Review | Notes |
| --- | --- | --- | --- |

## What was left open

Filled in as the work goes. Known before execution:
- **The launch-code race** (part 18's P18-9). A local process that reads the opener's command line and presents the code before the browser does is signed in. The terminal's warning is how it shows.
- **A local process can hold the 64 connections,** and so deny the page its server.
- **Transport security.** `ddd gui` speaks plain HTTP over loopback.
- **The token in `localStorage` can be read by any script of the page's own origin.** That would take an injected script, which the content security policy's `default-src 'self'` keeps out.
- **Two origins.** `localhost:<port>` and `127.0.0.1:<port>` have separate storage. A reader who visits the one they did not sign in at is signed out there.
- **Part 18's Windows leftovers, part 19's:** draining a refused `POST`'s body (P18-31), and the check of a project on a mapped drive by hand (P18-12).

## Rulings taken

Taken while planning; execution adds its own below them.

1. **Expand, switch, contract.** The server takes the header beside the cookie (Task 1), the page moves to it (Task 2), and the cookie goes (Task 3). No commit leaves a gate red — cost if wrong: for one commit, `_signed_in` reads both.
2. **`POST /open` lives in `server.py`,** not the API's route table: the token and the codes are the server's, not the project's — cost if wrong: the route table does not list it, though the page's sentence does.
3. **The signed-out view replaces the whole page.** `App` returns it before anything else draws, so no screen keeps asking behind it — cost if wrong: a reader signed out mid-edit loses that screen's state, though they must sign in again anyway.
4. **The sign-in runs in `main.tsx`, before React renders,** so that no ask goes out without the token — cost if wrong: the first paint waits one round trip to `/open` at launch.
5. **The `401` is handled in `request()`,** the one function every ask goes through — cost if wrong: none.
6. **The keeper moves to the tab's memory on the first storage error, and stays there** — cost if wrong: a tab whose storage recovers keeps using memory until it is reloaded.
7. **Old cookies are not cleared by the server.** They hold earlier runs' tokens, which no longer sign anything in, and die with the browser's session — cost if wrong: a dead token rides along to every loopback port until the browser closes.
8. **`json.loads`'s `RecursionError` on a nested `POST /open` body is a malformed body,** answered `400`: part 18's lesson from its walk — cost if wrong: none.
9. **The new journey's red is the cookie put back on Task 2's server,** not master's whole `server.py`, as the spec's §6 has it. Since Task 2, the journeys' fixture asks with the header, which master's server does not read — cost if wrong: the red shows the cookie's leak alongside the page's new sign-in, rather than through master's whole flow.
10. **The keeper and the signed-out flag live in `gui/src/api/token.ts`, beside `signIn.ts`,** not in `signIn.ts` alone as the spec's §5 has it. `client.ts` needs them for every request, and `signIn.ts` needs `client.ts`, so one module would import itself in a loop — cost if wrong: two modules where the spec named one.

### Taken during execution
