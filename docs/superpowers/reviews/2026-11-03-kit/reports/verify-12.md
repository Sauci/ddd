### Verification of pass 12

By a reader who did not find these, on 2026-11-06, on the tree at master 2b4bae6c. Scratch:
`SCRATCH/verify-11-12/`. 12 CONFIRMED, 3 PLAUSIBLE (I1, M9, M10). No grade changes.

| id | verdict | grade (was -> now) | duplicate of | evidence | note |
| --- | --- | --- | --- | --- | --- |
| I1 | PLAUSIBLE | Important -> Important | - | verify-11-12/p12/i1-loopback.txt; read off src/ddd/gui/server.py:351-374, tests/test_gui_server.py:3218-3262, gui/e2e/localhost.spec.ts:5-23 | the loopback half reproduced: ddd gui's own hold shows as [::]:P Bound beside 127.0.0.1:P Listen; a stranger on [::1] (9 combinations of IPV6_V6ONLY and SO_REUSEADDR / SO_EXCLUSIVEADDRUSE), on ::ffff:127.0.0.1 (9) and on 127.0.0.1 (3) is refused every time, and a connection to [::1]:P is refused, so a browser falls back to ddd gui; the trigger itself, a dual-stack bind of the wildcard [::], is outside the brief's loopback rule and was not made: it rests on the code (the hold sets IPV6_V6ONLY=1) and on pass 12's p06_dual.txt; the suite's strangers all set IPV6_V6ONLY=1 and the journey listens on ::1 alone |
| I2 | CONFIRMED | Important -> Important | - | verify-11-12/p12/i2.txt | reproduced: an edit labelled 'harmless' setting project.plugins to a plugin outside what is served answers 200, and the next analysis imports it in ddd gui's own process (its marker written), while GET /api/file of that plugin stays 404; an edit also created fresh.py and fresh.bat beside the project; docs/gui_security.rst:135-138 calls the token "the key" and never says what it opens, where spec 2026-10-07:27-28 says "The token is code execution as the reader" |
| I3 | CONFIRMED | Important -> Important | - | verify-11-12/p12/i3.txt | the server's half reproduced with a stub browser named by BROWSER: the opener is handed the one-time code and not the token; a GET spends nothing; the first POST /open of the code is answered the long-lived token, which then works on the API; the second presentation is 403 and the terminal prints the reused-code line; reading another user's command line was not tried; KNOWN holds: plans/2026-10-05-gui-security.md:1396, plans/2026-10-07-gui-token-out-of-cookie.md's What was left open |
| I4 | CONFIRMED | Important -> Important | - | verify-11-12/p12/i4.txt | reproduced on a start directory holding build/ddd-build.json, before anything is opened: a project path over loopback SMB (\\127.0.0.1\C$\...) is read on the start page's first GET /api/projects and offered as //127.0.0.1/C$/... with its name FarAway, and opening it is then refused 400; CON and CONIN$ leave the request unanswered for 40 s; a NUL in the path answers 500 with a traceback on the terminal; C:/Windows/win.ini, C:/Windows and "" are offered as projects; no other host was named |
| M1 | CONFIRMED | Minor -> Minor | - | verify-11-12/p12/m1.txt | reproduced: GET /api/compare?baseline= %00, a%00b and base%00.ddd.json each answer 500, the terminal showing ValueError: embedded null character, against docs/gui_security.rst:47-56 and queries.py:18-21; run always serves from its working directory, so every real run is hit |
| M2 | CONFIRMED | Minor -> Minor | - | verify-11-12/p12/m2.txt; verify-11-12/p12/m2c.txt | reproduced: an outside description put in the includes by an edit is 404 on /api/file, yet its description, unit and init come back from /api/dictionary and its unit from /api/variable, /api/units and /api/values; a component-shaped json outside has its values quoted by the findings (a plain json with no component key was not); a build record naming a project in another directory, opened from the start page, makes that directory served and an edit there writes |
| M3 | CONFIRMED | Minor -> Minor | - | verify-11-12/p12/m3.txt | reproduced: 64 long polls whose sockets were closed at once keep the server refusing new connections, a 503 or a reset, until 24.3 s, the first 200 at 25.4 s; the Edge reload measurement was not repeated |
| M4 | CONFIRMED | Minor -> Minor | - | verify-11-12/p12/m4.txt | reproduced on 127.0.0.1 port 80: the printed address is http://127.0.0.1:80/open?token=..., and a Host of 127.0.0.1 or localhost without the port answers 421 while 127.0.0.1:80 answers 200; a browser drops the default port from Host; not tried in a browser |
| M5 | CONFIRMED | Minor -> Minor | 9:M8 | verify-11-12/p12/m5.txt | reproduced on the refused path: --host "" and --host "$UNSET" say "--host resolves to 10.27.230.65, beyond this computer's loopback", exit 2 for want of a port; getaddrinfo('', AF_INET) answers that address; the bind that would follow with a --port was not made (not loopback); related to pass 9 M8 rather than the same defect |
| M6 | CONFIRMED | Minor -> Minor | 1:I15 | verify-11-12/p12/m6.txt; read off gui/src/components/CompareView.tsx:83-86 | reproduced: the start page's list runs nothing, its one press (POST /api/open) imports the project's plugin, Compare's one press imports the baseline's plugin, and ddd gui PROJECT imports before any request; the form says "Accepts a dumped dictionary, or a project or component description" and no more; pass 1 I15's undisclosed plugin execution, adding the page's two presses and the baseline's plugins |
| M7 | CONFIRMED | Minor -> Minor | - | verify-11-12/p12/m7.txt | reproduced: the 400, 414, 431, 501 and 505 http.server writes carry no Content-Security-Policy, nosniff or Referrer-Policy, and ddd gui's own 421 and 403 carry no Cache-Control; KNOWN holds: plans/2026-10-05-gui-security.md:1407-1408 |
| M8 | CONFIRMED | Minor -> Minor | - | verify-11-12/p12/m8.txt | reproduced without the token: 64 connections each writing one byte every 20 s still hold every slot at 36 s, the 65th refused; 64 idle ones are let go and the 65th is answered 200; documented at docs/gui_security.rst:198-206; KNOWN holds: plans/2026-10-07-gui-token-out-of-cookie.md's What was left open |
| M9 | PLAUSIBLE | Minor -> Minor | - | read off docs/gui_security.rst:226-238, src/ddd/gui/server.py:175-182, plans/2026-10-07-gui-token-out-of-cookie.md (What was left open) | documented residual: nothing in the server or the page removes what an earlier server on the port left (no Clear-Site-Data, no service worker handling in gui/src or src/ddd/gui); not reproduced: it needs a browser profile to plant a worker in, and the person's own browser profile is no place for one; a run in a throwaway Edge profile on a fixed port would settle it; KNOWN holds (P18b-11, P18b-13) |
| M10 | PLAUSIBLE | Minor -> Minor | - | read off docs/superpowers/specs/2026-10-05-gui-security-design.md:305, .github/workflows/, gui/package-lock.json | the half that can be read holds: the spec says "The audit runs once", no workflow runs an audit, and the lockfile's vite 8.3.0, vitest and @vitest/* 5.0.1 and decode-uri-component 0.5.0 (all development) lie inside the ranges of pass 12's npm_audit.json; npm audit itself was not run, since it sends the dependency tree to the registry, which the brief rules out; KNOWN holds (spec section 10) |
| M11 | CONFIRMED | Minor -> Minor | - | verify-11-12/p12/m11.txt | reproduced in a fresh, temporary Edge profile from Playwright, with my own server on 127.0.0.1 and my own redirector on 127.0.0.2: a navigation begun at an address of the other site, redirected to a Files row, reaches ddd gui with Sec-Fetch-Site: none and lands signed in; a link on that site, clicked, arrives cross-site and is answered the sign-in page; docs/gui_security.rst:177-183 names only an address typed or a bookmark |

No candidate of pass 12 is refuted, and no grade changes. Three are left plausible: I1, M9 and
M10. M2, M5 and M6 carry corrections or relations.

Every run was mine. I started `ddd gui` from the review tree's venv on its default `127.0.0.1`,
and once on `127.0.0.1:80` (M4). Every other socket I opened was on a loopback address:
`127.0.0.1`, `127.0.0.2`, `::1`, `::ffff:127.0.0.1`. The only browser was a temporary Playwright
Edge profile (M11). Pass 12's scripts and transcripts told me what to try. Its `p06_dual.txt` and
`npm_audit.json` are the only evidence I rest on, for I1 and M10, and those rows say so.

**I1, plausible: the trigger needs a wildcard bind, which the brief rules out; Important kept.**
- Reproduced on loopback:
  - On Windows `ddd gui` itself holds `[::]` on its port, shown `Bound` beside its `127.0.0.1`
    listener.
  - Every stranger bound on a loopback address at that port is refused, whatever its options.
  - A connection to `[::1]` at the port is refused, which is the fallback the page relies on.
- Not reproduced: the finding's own trigger, a dual-stack socket binding the wildcard `[::]` with
  `IPV6_V6ONLY=0`. That is a wildcard bind, outside the brief's loopback rule.
- What it rests on instead:
  - `_held_beside` sets `IPV6_V6ONLY=1` on its hold (`server.py:363`).
  - The suite's strangers all set it too (`tests/test_gui_server.py:3218-3229, 3250-3262`), and
    the journey listens on `::1` alone (`gui/e2e/localhost.spec.ts:5-23`). So nothing in the tree
    tries a dual-stack listener.
  - Pass 12's `p06_dual.txt` records such a bind succeeding beside the hold, two combinations of
    eighteen, and receiving a `localhost` request.
- What would settle it: the same bind on a machine where a wildcard listener is acceptable, a CI
  runner say, and a request to `localhost` at the port.
- If real, I keep the pass's reading: it is a stated defence failing, and only the need for a
  second local program and a rewritten address keeps it from Critical.

**M9 and M10, plausible: one needs a browser profile, the other a call to the npm registry.**
- M9 is a residual the security page states itself, and nothing in the code removes what an
  earlier server left behind. I did not plant a service worker in a browser to show it.
- For M10 I checked offline the half that can be checked: "runs once", and the installed
  versions. The advisory counts are pass 12's.

**Confirmations with corrections or relations.**
- M2:
  - The values are quoted for a component-shaped json; a plain json without a `component` key
    gave no quoted value.
  - Through `/api/dictionary` an outside description's text comes back only while the project
    still loads.
- M5: confirmed on the refused path only. It is related to pass 9 M8, both about `--host`, but is
  a different defect.
- M6 is pass 1 I15's defect met in the page. It adds the start page's open, the Compare press and
  a baseline's plugins to what pass 1 named.

```verdicts
12|I1|PLAUSIBLE|Important|Important|-|loopback half reproduced: ddd gui holds [::] Bound beside 127.0.0.1 Listen, every loopback stranger ([::1], ::ffff:127.0.0.1, 127.0.0.1, all option combinations) is refused and [::1] refuses connections; the dual-stack wildcard bind the finding needs is outside the brief and rests on server.py:363 (IPV6_V6ONLY=1), the suite's IPV6_V6ONLY=1 strangers and pass 12's p06_dual.txt
12|I2|CONFIRMED|Important|Important|-|an edit labelled harmless naming a plugin outside what is served answers 200 and the next analysis imports it in ddd gui's process while /api/file of it is 404; fresh.py and fresh.bat created beside the project; the security page never says the token is code execution, spec 2026-10-07:27 does
12|I3|CONFIRMED|Important|Important|-|stub browser via BROWSER: the opener gets the one-time code, the first POST /open of it gets the long-lived token which works on the API, the reader's second is 403 and the terminal prints the reused-code line; command-line reading not tried; KNOWN holds (plans 2026-10-05:1396, 2026-10-07)
12|I4|CONFIRMED|Important|Important|-|a build record under the start directory is read on the first GET /api/projects: a loopback SMB path read and offered with its name, CON and CONIN$ unanswered for 40 s, a NUL 500 with a traceback, win.ini, C:/Windows and "" offered; no other host named
12|M1|CONFIRMED|Minor|Minor|-|GET /api/compare?baseline= %00, a%00b, base%00.ddd.json answer 500, ValueError embedded null character, on every real run (the root is the cwd)
12|M2|CONFIRMED|Minor|Minor|-|an outside description in the includes is 404 on /api/file but its description, unit and init come back through dictionary, variable, units and values; a component-shaped outside json has its values quoted by findings; a build record's project elsewhere becomes served and editable
12|M3|CONFIRMED|Minor|Minor|-|64 long polls with their sockets closed keep new connections refused (503 or reset) until 24.3 s, first 200 at 25.4 s; Edge reload loop not repeated
12|M4|CONFIRMED|Minor|Minor|-|--port 80 on 127.0.0.1 prints http://127.0.0.1:80/...; Host 127.0.0.1 and localhost without the port answer 421, 127.0.0.1:80 answers 200
12|M5|CONFIRMED|Minor|Minor|9:M8|--host "" and an unset "$VAR" resolve to 10.27.230.65 and are refused only for want of a port, exit 2; the bind with --port not made; related to pass 9 M8, a different defect
12|M6|CONFIRMED|Minor|Minor|1:I15|the start page's open imports the project's plugin, Compare imports the baseline's, ddd gui PROJECT imports before any request; the form says nothing of it; adds the page's two presses and baselines to pass 1 I15
12|M7|CONFIRMED|Minor|Minor|-|http.server's 400, 414, 431, 501, 505 carry no CSP, nosniff or Referrer-Policy; ddd gui's 421 and 403 no Cache-Control; KNOWN holds (plan 2026-10-05:1407)
12|M8|CONFIRMED|Minor|Minor|-|64 tokenless connections writing a byte every 20 s hold every slot at 36 s, the 65th refused; idle ones are released; documented; KNOWN holds (plan 2026-10-07)
12|M9|PLAUSIBLE|Minor|Minor|-|documented residual (gui_security.rst:226-238); nothing in the server or page clears what an earlier server left; not reproduced, it needs a browser profile to plant a worker in; KNOWN holds (P18b-11, P18b-13)
12|M10|PLAUSIBLE|Minor|Minor|-|spec 2026-10-05:305 'The audit runs once', no workflow audits, the lockfile's dev versions sit in the transcript's ranges; npm audit not run (it sends the tree to the registry); KNOWN holds
12|M11|CONFIRMED|Minor|Minor|-|fresh Edge profile: an address of another loopback site redirecting to a Files row arrives Sec-Fetch-Site none and lands signed in; a clicked link arrives cross-site and gets the sign-in page; the page's sentence names only a typed address or a bookmark
```
