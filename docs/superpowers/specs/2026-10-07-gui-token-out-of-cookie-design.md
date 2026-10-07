# The GUI's token out of the cookie

- **Part:** 18b of the GUI work, in milestone 8, between the security review (part 18) and end-to-end
  breadth (part 19)
- **Status:** design approved section by section; to be planned
- **Depends on:** part 18 (pull request #79, merged into master as `ee8a7eb`)

Part 18's final review found the one hole its own fixes left: `ddd gui`'s cookie is its token, and a
browser hands the cookie to every server on `127.0.0.1`. The review documented it, on the security page
and in part 18's plan, under *What was left open*. This part closes it before part 19 locks behaviour
into journeys and part 20 documents it, so that neither has to be redone around a new sign-in.

## 1 The problem

`GET /open` answers a browser that brings the token, or a launch code, with
`Set-Cookie: ddd-gui-<port>=<token>; HttpOnly; SameSite=Strict; Path=/`. That is a host-only cookie
whose value is the long-lived token itself.
- **Cookies are not isolated by port** (RFC 6265 §8.5), and SameSite's *site* for an IP address ignores
  the port. So every request the reader's browser makes to any server on `127.0.0.1` carries the cookie.
- **This holds for a top-level navigation** the reader types or bookmarks, and for a page landed on there
  that fetches itself. Part 18's final review saw it happen: a one-off log in the hostile journey's own
  server showed the typed navigation, and the landed page's `/favicon.ico`, arriving with
  `ddd-gui-<port>=<token>`.
- **A local user who can listen on a loopback port** therefore gets the token once the reader's browser
  lands on their server. That could be another account on a shared machine, a container or WSL2 distro
  forwarding loopback, or a sandboxed app.
- **The token is code execution as the reader.** An edit can name a plugin by an absolute path, which
  `plugins._path_of` accepts, and the next analysis imports it.

Cookies carry a second weakness, which part 18 left open as well. A browser older than Chrome 76,
Firefox 90 or Safari 16.4 sends no `Sec-Fetch-Site`. A page on another port can make such a browser send
a `GET` that carries the cookie, and the server answers it, plugins run and all.

## 2 What was read

At master `ee8a7eb`:
- **The cookie:**
  - `server.py`'s `COOKIE` and `GuiServer.cookie` name it per port;
  - `_sign_in` sets it on `GET /open`, as a session cookie with no `Max-Age`;
  - `_signed_in` reads the `Cookie` header by hand and compares in constant time.
- **The token is minted fresh each run** (`GuiServer.__init__`, `secrets.token_urlsafe`). The launch code
  is single-use and expires after 60 s (P18-8 to P18-10). A spent code that carries the cookie is answered
  the signed-in page, so that a browser's prefetch of the launch address does not lose the reader their
  sign-in.
- **The pages need the cookie as the API does:** `_route` answers a page asked without it `401` with the
  sign-in page.
- **Every request the page makes goes through one function,** `request()` in `gui/src/api/client.ts`,
  which passes `credentials: "same-origin"`. Nothing in `gui/src` reaches `/api/` by a link, a download
  or `window.open`. The layout worker asks the server nothing.
- **The page has a router of its own** in `App.tsx`, and no development proxy.
- **The journeys' fixture** (`gui/e2e/fixtures.ts`, `analysed`) fetches the printed address, keeps the
  cookie it is set, and polls `/api/state` with it.

## 3 The answer

The token stops being a cookie. It becomes a value the page keeps in `localStorage` for its own origin,
`http://127.0.0.1:<port>`, port included. The page sends it as `Authorization: Bearer <token>` on every
request to the API.

| Who | At `ee8a7eb` | After this part |
| --- | --- | --- |
| A server on another loopback port that the reader's browser visits | receives the cookie, which is the token | receives nothing: no cookie exists, and another origin's storage is out of its reach |
| A page on another port, in a browser without `Sec-Fetch-Site` | can make it send a `GET` that carries the cookie | cannot: `Authorization` is no header a cross-origin request may carry without a CORS preflight, which the server never grants |
| The page's own requests | carry the cookie, sent by the browser | carry the header, added in one place |
| The compiled pages (`/`, `/project`, their assets) | need the cookie | are served with no credential: they hold no project data |

**Unchanged:**
- the launch code, its expiry and the terminal's warning for a code presented again;
- the printed address, with its token, for pasting;
- the request gate, in the same order, kept as defence in depth;
- the Host check against DNS rebinding;
- the cap of 64 connections, the typed queries, and every answer's security headers.

**Still open:**
- **The launch-code race.** A local process that reads the opener's command line and presents the code
  before the browser does is signed in.
- **A local process can still hold the 64 connections.**
- **The token in `localStorage` can be read by a script running in the page's own origin.** That would
  take an injected script, which the content security policy's `default-src 'self'` keeps out.

## 4 The server

| Request | Answered |
| --- | --- |
| `GET /open?code=…` or `GET /open?token=…` | The app itself, its `index.html`, with `Cache-Control: no-store`. Nothing is checked or spent on a `GET`, so a browser's prefetch can no longer spend a launch code. It stays exempt from the gate, as `/open` is today, since the address is reached however the reader got it. |
| `POST /open`, with a json body of exactly one of `{"code": "…"}` and `{"token": "…"}` | The sign-in. It needs no credential, since it is where the page gets one, but it passes the gate and a `POST`'s rules: this server's `Origin`, json, and at most 1 MiB. A matching token, or a code redeemed within its 60 s and spent atomically under its lock, answers `200 {"token": "<token>"}`, with `no-store`. Anything else answers `403` with one sentence. A code that already signed a browser in prints the terminal's warning, as P18-10 has it. A body that is not exactly one of the two answers `400`. |
| A page: `/`, `/project`, an asset | Served after the gate with no credential, as `_page` serves it. |
| `/api/…` | Needs `Authorization: Bearer <token>`: the scheme in any case, as HTTP says, then one space, then the token, compared in constant time. A request without the header, or with any other value, answers `401` with today's sentence. |

**What goes:**
- the `Set-Cookie`, the cookie's name per port, and `_signed_in`'s reading of the `Cookie` header;
- the signed-in page, with its refresh, which `GET /open` answered once it had set the cookie;
- the `401` sign-in page for a page asked without a cookie. The page now says it is signed out itself (§5).
- the special case that answered a spent code carrying the cookie with the signed-in page.

A cookie that holds the right token is no credential any more.

The server still answers no `OPTIONS` and sends no CORS header. A cross-origin request that carries
`Authorization` therefore dies in its preflight, which the standard library answers `501`.

`POST /open` lives in `server.py` beside `GET /open`, not in the API's route table, because the token
and the codes are the server's, not the project's. The route table and its test stay as they are. The
security page's sentence about `/open` covers both methods.

## 5 The page

All of the sign-in lives in one module, `gui/src/api/signIn.ts`, under Vitest's 100 % over `src/api`.
No decision goes in a `.tsx` file.

| Moment | What happens |
| --- | --- |
| The app starts at `/open` with a `code` or a `token` | The module reads the secret: the code if the address holds one, the token otherwise. It then at once replaces the address with one that holds no secret (`history.replaceState`), before anything else runs. It posts the secret to `/open`. On `200` it keeps the token under `ddd-gui-token` in `localStorage`. The app then lands where the signed-in page sends a browser today: `/project` if a project is open, `/` otherwise. That choice is a pure function of `/api/session`'s answer. |
| The app starts anywhere else, `/open` with neither included | It uses the stored token if there is one, and is signed out otherwise. |
| Every request to the API | `request()` adds `Authorization: Bearer <token>` from storage, and sends no cookie (`credentials: "omit"`). |
| A `401` from any request, or a refused sign-in | The stored token is cleared, and the app shows a signed-out screen. Its sentence tells the reader to open the address `ddd gui` printed, as the sign-in page says today. Nothing retries. Other tabs follow on their next request, since they read the same storage. |
| The browser refuses storage, as a private window or a policy may | The token is kept in memory for the tab, which stays signed in until it closes. |

The token is never put into a URL the page builds, a log or an error's message. With no cookie and the
address cleaned at once, it is kept nowhere a browser keeps things by itself. The one exception is the
printed address, when the reader pastes it.

## 6 Testing

Every change fails first: through real HTTP for the server, through Vitest for the page, and in a
browser for the journeys.

- **`tests/test_gui_server.py`.** The `ask()` helper sends the header, not the cookie. Each refusal is
  asserted as a whole sentence.
  - `GET /open` answers the app with `no-store`, and spends nothing: the code still redeems after it.
  - `POST /open` with a code answers `200` with the token, once. Presented again, it answers `403` and
    prints the terminal's warning.
  - An expired code answers `403` with no warning. A wrong code answers `403` and leaves the right one
    waiting.
  - A wrong token answers `403`. Both keys, neither, or a stray key answer `400`.
  - The gate and a `POST`'s rules apply to `POST /open`.
  - The API answers `401` to a request with no header, to a wrong token, and to a cookie holding the
    right token. It answers `200` to the right token, with the scheme in any case.
  - A page needs no credential.
  - No answer anywhere carries `Set-Cookie`.
  - An `OPTIONS` preflight gets `501` and no `Access-Control-*` header.
- **`gui/src/api/signIn.test.ts` and `client.test.ts`.**
  - The address is cleaned before the `POST` is sent.
  - The token is kept on `200`, and cleared on `401` or `403`.
  - The token falls back to memory when storage is refused.
  - The landing is chosen from `/api/session`.
  - Every request carries the header and `credentials: "omit"`.
- **`gui/e2e/fixtures.ts`.** The fixture reads the token from the printed address and sends the header.
  It waits for the landing, at `/project` or `/`, before a journey acts.
- **A new journey: another server on `127.0.0.1` is sent nothing.**
  - The journey signs in through the printed address.
  - It then takes the same browser to a Node server on another loopback port, whose page fetches itself.
  - That server records every header of every request, and the token is in none of them.
  - It is red at `ee8a7eb`, where the cookie arrives.
- **Part 18's journey stays:** a page on another port cannot make `ddd gui` run a baseline's plugin.
  - Two defences now hold it: no credential reaches the server, and the gate. Its comments say so.
  - Its red case, the gate taken out, no longer shows the marker. The new journey is the one that shows
    the cookie's leak.
- **A Ladle story for the signed-out screen,** with its screenshot reference taken in Docker.
- **Ablations in a scratch worktree.** Each of these must fail a named test:
  - the server accepting the cookie again;
  - `request()` without the header;
  - the address left uncleaned;
  - `GET /open` spending the code;
  - the cookie set again, which the new journey catches.
- **Every gate as before,** with the one new screenshot reference and the journeys passing.

## 7 Documentation

- **`docs/gui_security.rst`** says what is true after this part.
  - The other loopback server moves from *What it does not defend against* to *What it defends against*.
  - The older-browser caveat closes: such a page's request reaches the API with no credential, and is
    answered `401`.
  - *What it trusts* gains the page's own origin. The token is in its `localStorage`, readable by its
    scripts alone, which the content security policy limits to `ddd gui`'s own.
  - The note on browsers older than SameSite goes, with the cookie it was about.
  - The sentence on `/open` covers `GET` and `POST`.
- **`CHANGELOG.md`.** Part 18's entries are still unreleased. Each one that speaks of the cookie is made
  true after this part, and one entry is added: the token is no longer a cookie.
- **`server.py`'s module docstring** states the sign-in.
- **`SECURITY.md`** is unchanged.

## 8 Risks

- **The sign-in is asynchronous now.** Between `goto(address)` and the landing, the page signs itself in.
  A journey that acts before the landing would race it, so the fixture and the journeys wait for it.
- **No loops.** A `401` must clear the token and stop. A long poll in flight when that happens must end
  without an error on the screen.
- **Every page test that stubs `fetch`** must now expect the header and `credentials: "omit"`.
- **The hostile journey's red run changes meaning** (§6).
- **Two origins.** `localhost:<port>` and `127.0.0.1:<port>` are different origins with different
  storage. A reader who signed in through the printed address, which uses `127.0.0.1`, and then visits
  `localhost:<port>` is signed out there until they open the address again.

## 9 Out of scope

- **The launch-code race, the local denial of service through the cap, and transport security,** as part
  18 left them.
- **Part 18's two Windows leftovers**, which belong to part 19: draining a refused `POST`'s body
  (P18-31), and the check of a project on a mapped drive by hand (P18-12).
- **Session secrets per browser, and revoking them.** The token is minted fresh each run, which is what a
  secret per session would add.

## 10 Decisions taken

The maintainer's answers while this was designed:
- **This part comes before part 19** ("18b first").
- **The sign-in is kept in `localStorage`, for every tab, for the run.** It is not kept per tab in
  `sessionStorage`.
- **The page signs itself in and sends a header** (approach A). Rejected were `/open` handing the token
  over in a page of its own (B), and a host name per run that would keep the cookie (C), which only
  narrows the leak.

Taken in the design:
- **The stored value is the token itself, not a session secret per browser** (§9).
- **`POST /open` is the sign-in,** in `server.py`, kept out of the API's route table.
- **The gate stays as it is,** as defence in depth.
- **The pages are served with no credential.**
