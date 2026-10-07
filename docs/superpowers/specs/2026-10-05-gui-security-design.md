# The security review of the GUI

- **Part:** 18 of the GUI work, and the second of milestone 8
- **Status:** design approved section by section; to be planned
- **Depends on:** part 17 (pull request #77, merged into master as `a1da6ce`)

Milestone 8 of `2026-09-17-web-gui-design.md` §5 is *"Hardening (large projects, security review,
end-to-end breadth), the user guide, an independent review, the pilot, removing preview"*, in the parts
`2026-09-30-gui-large-projects-design.md` §1 lists. This part is its security review.

It reviews the whole surface of the `ddd gui` server:
- the token;
- the Host and Origin checks;
- the content security policy;
- the served directories;
- edits, plugins and the file endpoints.

It fixes what it finds, so that the parts after it (end-to-end breadth, the user guide, removing
*preview*) lock in behaviour that has already been reviewed.

## 1 Who it defends against

**Defended:**
- **Any web page open in the reader's browser.** That includes a page served from another port of
  `127.0.0.1`. A browser counts every port of an address as the same site, so it sends such a page's
  requests the `SameSite=Strict` cookie of `ddd gui`.
- **Any other local process or user** that reaches the port without the token. The server may be on
  loopback, or published from a container on the host's loopback.
- **Malformed input from anyone.** Every request is answered with a status and a sentence, never with
  a 500 and never with a hang.

**Trusted, and documented rather than defended:**
- **The project the reader opens.** Its plugins run when it is analysed, as they run under
  `ddd check` (`2026-09-17-web-gui-design.md` §4.3).
- **A baseline the reader compares against.** Its plugins run, as they run under `ddd compare`.
- **The directory `ddd gui` was started in,** whose project files may name files above it.
- **Whoever holds the token.** It is the key, and whoever started `ddd gui` holds it.

**Out of scope** (§10): untrusted projects, transport security, and the page's own code beyond its
content security policy.

## 2 What was found

The server was read whole for this design: `src/ddd/gui/server.py`, `api.py`, `session.py`,
`compare.py` and `contract.py`, at master `a1da6ce`.

Its existing defences hold as `2026-09-17-web-gui-design.md` §6.3 describes them, and are kept:
- the token is made by `secrets.token_urlsafe(32)` and compared in constant time;
- the exchange `GET /open?token=` sets an `HttpOnly`, `SameSite=Strict`, port-named cookie;
- every other request needs that cookie;
- the Host header must be `127.0.0.1:<port>` or `localhost:<port>`, against DNS rebinding;
- a `POST` needs this server's `Origin` and a JSON body of at most 1 MiB;
- every response carries a content security policy of `default-src 'self'` with
  `frame-ancestors 'none'`, plus `nosniff` and `no-referrer`;
- static files are confined to the package's pages after resolving the path;
- a file read or edited must be a source of the open project, inside the directory served;
- an edit is staged and renamed into place;
- an unexpected failure answers 500 with a sentence, its traceback printed on the terminal alone.

What is wrong was probed on 2026-10-05, on the Linux development PC, against master `a1da6ce`. Each
probe was one run against `ddd gui demo/demo.ddd.json --no-browser`, over a copy of `examples/demo`,
driven by `curl` with the signed-in cookie:

| asked | answered | because |
| --- | --- | --- |
| `GET /api/compare?baseline=<the demo's description>`, with `Sec-Fetch-Site: same-site` - what a browser sends for a page on another port | 200: the baseline read and analysed, and so its plugins run | nothing checks where a `GET` comes from |
| `GET /api/state` with `Origin: http://127.0.0.1:9999` | 200 | the same |
| `GET /api/findings?file=%00` | 500 | `ValueError: lstat: embedded null character in path` |
| `GET /api/findings?offset=` or `?limit=` of 4,301 digits, and `GET /api/state?after=` of 4,301 digits | 500 | `ValueError: Exceeds the limit (4300 digits) for integer string conversion` |
| `GET /api/settle?...&raw=` holding 3,000 nested arrays, 6 KB of query | 500 | `RecursionError` in `json.loads` |
| 300 long polls (`GET /api/state?after=999999`) at once, each client giving up after 20 s | the server's threads went from 31 to 221 while they were open, and to 293 after the clients gave up | one thread per connection, with no cap; each long poll keeps its thread for its 25 s, whether its client is still there or not |
| `ddd gui` started without `--no-browser`, `BROWSER` naming a stub that records its arguments | the stub's arguments, and its `/proc/<pid>/cmdline` that any local user may read, held the address with its token | `webbrowser.open(address)` hands the browser the address the terminal prints |

Not reproduced as asked:
- a lone surrogate sent by `curl` as `%ED%A0%80` in `?file=` answered 200;
- `raw=1e999` answered `/api/settle` 400;
- 20,000 nested arrays were refused by the request line's own limit, 414, before any parser.

Found by reading, not probed:
- **Beyond loopback, the token is the only barrier.** A client that reaches the port can forge `Host`
  and `Origin`. This is as `2026-09-17-web-gui-design.md` §6.3 states it, and `ddd gui` says so when it
  starts.
- **Paths above the starting directory reach the compare reply.** A compared baseline's includes may
  name files above that directory, and their names appear in the reply. The directory is trusted (§1).
- **A network path is opened on Windows.** Part 17's final review found that a `?file=` naming a UNC
  path is opened there.

## 3 What this part delivers

- **One request gate,** refusing any request that did not come from the page itself (§4).
- **The token never on a command line:** the browser is launched without it (§4).
- **One route table and a typed query for every route.** No route answers malformed input with a 500
  (§5).
- **A cap on concurrent connections** (§6).
- **`SECURITY.md`, a security page in the documentation, and a dependency audit** (§7).

## 4 The request gate

Every request passes one gate in the server, in this order:

1. **Host.** It must be `127.0.0.1:<port>` or `localhost:<port>`, as today; otherwise `421`.
2. **`GET /open?token=`** is the only request exempt from the rest.
3. **Where it comes from.** A request carrying `Sec-Fetch-Site` must say `same-origin`, or `none`,
   which a browser sends only for an address the reader typed or a bookmark. A request carrying
   `Origin` must name this server: `http://127.0.0.1:<port>` or `http://localhost:<port>`. Anything
   else is refused `403` with one sentence: an API request as JSON, a page as a short HTML page
   saying to open the address `ddd gui` printed. A client that sends neither header, such as a
   script, `curl` or the test suite, goes on to the cookie, so the token still decides.
4. **The cookie,** as today: an API request without it is answered `401`, a page with the sign-in
   page.
5. **A `POST`** needs this server's `Origin` and a JSON body, as today.

**A page on another port is refused at step 3.** Its `GET` and its `POST` alike arrive marked
`same-site`, and are refused before any handler runs.

**The token never reaches a command line.** `ddd gui` no longer hands the browser the printed address:
- it writes a small HTML file, readable and writable by the reader alone, in a temporary directory of
  its own;
- the file redirects to the address;
- the browser is launched on that file's `file://` path, which holds no token;
- the directory is removed when the server stops.

The terminal still prints the address, token and all, for the reader to paste.

**`/open` answers with a page, not a 303.** A navigation that starts from a `file://` page is
cross-site to the browser, and a `SameSite=Strict` cookie does not follow a redirect from it. So
`GET /open?token=` sets the cookie and answers with a small page that refreshes to the project, or to
the start page with no project open. That refresh is a same-origin navigation, which the cookie
follows. The page is `<meta http-equiv="refresh">`, so the content security policy allows it, no
script being needed.

**Bound beyond loopback, nothing changes:** the token remains the barrier, and the documentation
says so (§7). A browser on another machine is refused by the Host check already.

## 5 One route table, a typed query for every route

`_ROUTES` in `api.py` becomes one list of `Route` records. Each holds:
- the path and the method;
- the model of its query and the model of its body;
- its handler;
- its policy: whether it writes, opens a project, runs plugins, or waits (the long poll).

**The dispatcher:**
1. Reads the query string into one value per key. A key given twice, or a key the route does not take,
   is refused `400`.
2. Validates the values against the route's query model, which is strict and closed like the models
   of today's `POST` bodies.
3. Turns the first problem into one sentence, through the same `_message` the bodies use.
4. Hands the handler the typed query. No handler parses a query value by hand any more.

A route whose parameters depend on its `action` - the plan routes, which read a different set for each
action today - has one query model per action, the one chosen by the `action` given. Every route reads
one value per key today, and the page never repeats one, so refusing a repeated key changes nothing
the page sends.

**The values' types,** in `contract.py`, do the parsing:
- **A whole number:** ASCII digits only, at most nine of them, so no sign, underscore or non-ASCII
  digit. Each field adds its own bounds: an `offset` from 0, a `limit` from 1.
- **A path:**
  - non-empty, at most 4,096 characters;
  - absolute;
  - no NUL character, and no lone surrogate;
  - no network or device form, `\\server\share`, `//server/share` or `\\?\...`, refused on every
    platform.

  Whether the path is a file of the project stays the handler's question, as today.
- **JSON text** (`raw=`, `definition=`): parsed with a depth limit of 64 levels, and numbers must be
  finite.
- **A name:** non-empty, at most 1,024 characters, no NUL.
- **An enumeration** (a severity, an action, a kind): a literal.

**The page.** The query models join the models `contract.py` publishes, and so `gui/src/generated/
api.ts`. The functions of `gui/src/api/client.ts` take those types, so that a parameter the server
does not take, or a required one left out, fails `npm run typecheck`. The strings the page sends do
not change.

**Refusals.** A refusal the page already shows keeps its sentence word for word, so that no screenshot
reference and no journey moves. A new refusal names the parameter and what it takes.

**No route answers malformed input with a 500.** A test walks the route table and sends every
parameter of every route a set of hostile values:
- a NUL character;
- a lone surrogate;
- 4,301 digits;
- JSON nested 3,000 levels;
- `1e999`;
- a network path;
- an empty string;
- 64 KB of text.

Each answer must be `400`, `404` or `409`. A route added later is walked without a test of its own.

## 6 Resource limits

**A cap of 64 concurrent connections.**
- A connection takes a slot before it gets its thread.
- With no slot free, the accepting thread answers `503`, with `Retry-After: 1` and one sentence, and
  closes the connection. No thread is spawned.
- A browser opens at most six connections per host, across all its tabs, so the page cannot reach the
  cap: 64 leaves room for ten browser profiles and some scripts.
- The 300 long polls of §2 cannot take the server past 64 threads answering requests.
- An idle connection still gives up its slot after the 30 s it is given today.

Someone without the token can still fill the cap, and so deny the page its server. That stays a local
risk, documented (§7). The machine's threads cannot be exhausted any more.

**Long polls** are unchanged: one per tab, each up to 25 s, inside the cap.

**Sizes:**
- A request line is limited to 64 KB and a request to 100 headers, by the standard library, answering
  `414` and `431`.
- A `POST` body is limited to 1 MiB, answered `413` beyond that, as today.
- JSON in a query is limited to 64 levels (§5). JSON in a body keeps the depth limit of pydantic's
  parser, which a test pins.

**A request without the cookie does no work.** It costs the Host check, the gate, a constant-time
comparison and an answer of `401` or `403`. `/api/compare` and `/api/open`, the two routes that run
an analysis and plugins, need the cookie and the gate, and `/api/open` the `POST` rules too.

## 7 Documentation and reporting

- **`SECURITY.md`,** at the repository's root:
  - which versions are supported: the latest release, `ddd gui` marked preview;
  - how to report a vulnerability: privately, through the repository's Security tab and its "Report a
    vulnerability" button. The maintainer switches GitHub's private vulnerability reporting on, which
    is off as this is written;
  - what a report should hold;
  - a pointer to the security page;
  - nothing promised that the maintainer has not promised, such as a response time.
- **`docs/gui_security.rst`,** the security page:
  - the threat model of §1, in the reader's terms;
  - running in a container: publish on `127.0.0.1` only, since beyond that the token is the only
    barrier;
  - the local denial of service the cap leaves;
  - a table of every route: its method, what it reads, writes or runs, and whether it opens a project
    or runs plugins.

  A test checks that the table names exactly the routes of the server's route table, with their
  policies, so that the page cannot drift from the code.
- **`server.py`'s module docstring** states the gate and the cap.
- **The CHANGELOG** gets this part's entries under `## Unreleased`.
- **The dependency audit:** `pip-audit` over the Python environment and `npm audit` over the page's
  lockfile, run once during execution. The results go in the plan with their dates. A high or critical
  finding with a compatible fix is upgraded in this part, and any other is recorded as left open.

`2026-09-17-web-gui-design.md` stays as it was written. This spec, and the plan's *As built* note, say
where its §6.3 changed.

## 8 What can go wrong

- **A browser that will not carry the cookie** from the `file://` launch through `/open`'s refresh.
  This is the plan's first risk. It is checked by hand in Chrome and in Firefox before anything else is
  built on it. If a browser refuses, the alternative is chosen then and recorded.
- **A browser too old to send `Sec-Fetch-Site`:** Chrome before 76, Firefox before 90, Safari before
  16.4. Such a browser sends no `Origin` on a plain `GET` either, so a page on another port can still
  make it ask one. The security page says which browsers the gate protects.
- **A refusal the page shows, worded differently:** kept word for word (§5), and the screenshots run in
  compare mode to show it.
- **The page sending a parameter the strict queries refuse:** the generated types fail the page's
  typecheck, and the journeys drive every screen against the real server.
- **Legitimate use reaching the cap** cannot happen from one browser profile (§6). If it ever does, the
  sentence the `503` carries says what happened.
- **The launch file on Windows:** it is written in the reader's own temporary directory, which only that
  reader may read by default.

## 9 Testing

- **Every finding fails first.** Each row of §2 becomes a test that fails before its fix. It runs
  through real HTTP against a stand-in page, as `tests/test_gui_server.py` does, or through the API:
  - a request marked `same-site` or `cross-site`, or carrying another `Origin`, is refused with its
    sentence; `same-origin`, `none` and a request with neither header pass;
  - each 500 becomes a `400` with its sentence;
  - **the cap:** connections held open by a handler waiting on an event fill all 64 slots; the 65th is
    answered `503`; freeing one serves the next. Real sockets with timeouts are used, never a sleep;
  - **the launch:** the browser is handed a `file://` path that never holds the token. The file holds
    the address, is readable by the reader alone (checked on POSIX), and is gone once the server has
    stopped. A stub opener stands in for the browser;
  - `/open` answers with its refresh page, and the tests that pinned its 303 change with it.
- **The walk of hostile values** over the route table (§5), and the documentation's table checked
  against the route table (§7).
- **A journey in a real browser.** A page served from another port of `127.0.0.1` asks `ddd gui` to
  compare a baseline whose plugin writes a marker file when it is loaded. Before the gate, the marker
  appears; after it, it never does.
- **By hand:** the `file://` launch signs in, in Chrome and in Firefox (§8).
- **Ablation.** Each rule of the gate, the cap, each value type's refusal and the launch file is taken
  out in turn, and each must fail a named test. The Python ablations run in a scratch worktree, with
  pytest run from inside it.
- **Everything else passes as before:**
  - Python at 100 % line and branch, with ruff and bare mypy;
  - Vitest at 100 % over `src/api`, `src/lib` and `src/state`;
  - every journey;
  - the screenshots in compare mode, no reference moving;
  - the documentation built under `-W`.

  The Windows jobs of CI run the network-path refusals on Windows itself.

## 10 Out of scope

- **Untrusted projects.** A gate before a project's plugins run, like an editor's workspace trust, is
  a part of its own if the pilot asks for one.
- **Transport security,** and serving beyond loopback other than the published container. The token
  stays the barrier there (§4).
- **The page's own code.** No review of the page for script injection, beyond the content security
  policy holding.
- **Scanners in CI.** `bandit`, `pip-audit` and `npm audit` are not added as jobs. The audit runs once
  (§7).
- **Rate limiting beyond the cap.**
- **The independent review and the pilot,** which the maintainer organises.

## 11 Decisions taken

The maintainer's answers while this was designed:

- **The threat model of §1:** web pages and other local processes, with malformed input from anyone.
  The project, its plugins and a compared baseline are trusted, as `ddd check` and `ddd compare` trust
  them. Chosen over defending against untrusted projects, and over checking only the existing defences.
- **The method:** a review, a probe for each suspected weakness, a fix pinned by a test, and a
  dependency audit run once, with CI unchanged. Chosen over adding scanners to CI, and over a review
  by reading alone.
- **Reporting:** `SECURITY.md`, through GitHub's private vulnerability reporting, which the maintainer
  switches on. Chosen over an email address, and over no reporting policy.
- **The approach:** one route table, with a typed query for every route. Chosen over one gate with one
  shared parsing layer, and over fixing each finding where it arose.
- **The design,** section by section: the scope and threat model, the request gate, the route table
  and typed queries, the resource limits, documentation and reporting, and testing.
