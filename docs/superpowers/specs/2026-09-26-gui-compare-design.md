# Comparing a delivery in the browser

- **Part:** 12 of the GUI work, the second half of milestone 7
- **Status:** design approved; to be planned
- **Builds on:** the findings tab, shipped as part 4
  ([`2026-09-22-gui-findings-design.md`](2026-09-22-gui-findings-design.md)), and the one-click
  fixes of part 11
  ([`2026-09-25-gui-mismatch-fix-design.md`](2026-09-25-gui-mismatch-fix-design.md))

## 1 Why

`ddd check` answers **do these components fit together**, and eleven parts of the GUI have been
built around that answer. `ddd compare` answers a different question - **can this delivery replace
the one already out there** - and the browser interface has nothing for it at all: no route, no
screen, not a word.

[`comparing_deliveries.rst`](../../comparing_deliveries.rst) opens by insisting the two are not
one question. They are wrong in different ways: a project that passes every consistency check can
still turn a `uint16` into a `uint32` and break the software already running in the field.
Thirteen checks exist for that second question, `CHECKS` already flags each of them
`comparison=True`, and `ddd gui`'s own `/api/checks` already reports that flag to the page. The tool knows these checks
exist. The interface has never run one.

This part runs one.

## 2 What it is not

- **Not a second way to check.** The Compare tab answers the replacement question only. The
  Findings tab keeps the consistency question, and neither borrows the other's findings.
- **Not a file browser.** A baseline is named by a path under the session's own root, and a path
  that escapes it is refused with its reason.
- **Not a download.** The rename map is drawn as a table. Saving it as a file needs a route the
  server does not have, and that is a part of its own.
- **Not a change to what an editor reports.** `ddd check --baseline` already exists and would
  have given the comparison to the session for free, through `ddd.lsp.diagnostics`' runners -
  but those runners are the **language server's**, and a comparison screen has no business
  changing what an editor says.
- **Not two deliveries of the reader's choosing.** The candidate is always the open project.

## 3 What a baseline may be

**A path under the session root**, naming either a published dictionary or a project description,
exactly as the command accepts.

The tool cannot discover baselines. Nothing records where a delivery was published; `ddd dump -o`
writes wherever it is pointed. So the reader names one, and the only question is how far the page
may reach to read it.

Every file the page reads today belongs to the open project: `Session.read_file` resolves through
`_source(self._required(), path)`, which is the restriction that keeps the page from being a file
browser. `ddd gui --host` widens the bind beyond loopback "for a container", so a path field that
reads anywhere would be a file-read primitive for whoever can reach the port.

Resolving under the root is the smallest widening that does the real job: a delivery's dictionary
usually sits near the project - a `deliveries/` folder, a build output - and a delivery archived
elsewhere is copied into the tree, which a release engineer can do and understand.

**A description has to be analysed to become a dictionary**, and that analysis has findings of its
own: files outside the project under test, an output nobody read two releases ago.
`cli._read_baseline` already knows the policy that makes this safe - its own bag, never
`--strict` however strict this run is, and only its errors carried over, prefixed, so a broken
baseline is visible without
failing a clean project. **That policy moves out of `cli.py` so both callers share it.** The GUI
reimplementing it would be two readings of one rule, which is the drift part 11 spent itself
removing.

## 4 How it runs

**`GET /api/compare?baseline=<path>`**, stateless, answering one comparison.

The page holds the baseline path and asks again whenever the revision changes - which it already
watches, because every other panel does. So the comparison is live: fixing a `changed-interface`
turns the verdict green while the reader watches, and the server keeps no comparison state to
invalidate.

Holding a comparison in the session was the alternative, and its invalidation is the part that
would go wrong: a comparison depends on **both** sides and the session watches only one.

**The resolved baseline is cached by path and fingerprint.** Re-asking after an edit costs a
dictionary comparison rather than a reload, which matters because a project-description baseline
is a full load and analysis. It is a cache in the strict sense: discarding it changes speed and
nothing else.

**The severity policy is the session's own.** A comparison run in the GUI reports what the same
project's `ddd check --baseline` would, and there is no new control.

## 5 What the reply carries

- **The verdict** - whether the candidate can stand in for the baseline, by the rule the command's
  exit code already uses.
- **The findings**, as `Finding`s exactly as the Findings tab receives them: comparison
  diagnostics carry locations in the candidate, so they route to what they name.
- **The rename rows**, `{id, from, to}`, which `compare` hands back as the pairing it made rather
  than a second comparison of the same two sides.

## 6 What the reader sees

A **Compare tab**, beside Findings.

- **Empty until a baseline is named**, with a field that says what it accepts.
- **The verdict leads.** A list of differences without an answer makes the reader do the
  arithmetic the command already does for them.
- **The findings below it**, drawn by `FindingsTableView` and `FindingPanelView` unchanged.
- **The renames as a table.** "What moved?" is half of what a reader wants, and the pairing is
  already in hand.
- **A refused baseline says why** - outside the root, unreadable, not json, or json that is
  neither a dictionary nor a description.

## 7 Testing

- **Python at 100 % of lines and branches** over the route and the shared baseline reader. A
  conditional expression registers no branch at all with `coverage.py`; where an arm needs a test,
  write a statement or early returns.
- **The shared `_read_baseline` keeps its CLI tests passing unchanged**, which is the proof that
  moving it changed nothing. Where a test must move, each edit is justified on its own.
- **Vitest at 100 %** over whatever lands in `gui/src/lib` and `gui/src/api`, and **no Vitest for
  a component or a screen**, as since part 1.
- **Stories and screenshots** for the tab: empty, a comparison with findings and renames, a
  comparison that passes, and a refused baseline.
- **One journey**: open a copy of the demo, compare it against a dumped dictionary of itself -
  which must pass - then drift a datatype and watch the verdict turn.
- No new dependency, page or server. The rule has held since part 1.
