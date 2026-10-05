"""One thread at a time in :mod:`difflib`: the lock each of ddd's calls into it holds.

``ddd gui`` analyses a project on a thread of its own and answers its requests on others, and
both reach difflib: an analysis to suggest the name meant where one no file declares is written
(:func:`ddd.analysis.close_units`, and ``get_close_matches`` in ``ddd.analysis._did_you_mean``),
a request for the lines a planned change replaces (:func:`ddd.variables.hunks`). On Python
3.14.4 - Ubuntu's 3.14.4-1ubuntu0.2, a build with the GIL, its JIT built and off - two threads in
difflib at once have broken it, for a reason nobody has found:

- twice, a plan asked for while an analysis ran - ``GET /api/declaration-plan``, then
  ``GET /api/settle`` - answered 500 with ``TypeError: '>=' not supported between instances of
  'int' and 'SequenceMatcher'``, raised at ``if j >= bhi:`` in ``find_longest_match`` under the
  request's ``get_opcodes()``: an int argument read as the matcher;
- a probe running ``ratio()`` on one thread and ``get_opcodes()`` on another, both in difflib's
  one module, ended in a segmentation fault once within 60 s;
- run forty times for 60 s, the same probe raised ``TypeError: '<' not supported between
  instances of 'int' and 'SequenceMatcher'`` at ``if j < blo:`` once, and ``AttributeError:
  'dict' object has no attribute 'a'`` - the matcher read as a dict - once; run six times for
  600 s, as six of eighteen busy processes at once, never.

Each of those had one thread in difflib's ``get_opcodes()`` while another was making calls into
difflib: in a 500, the analysis making a suggestion. The probe ran clean with each of its two
threads holding a copy of difflib of its own, sharing no code object, forty times for 60 s and
six times for 600 s; with its other thread in Python that is not difflib, ten times for 60 s and
six times for 600 s; and on Python 3.12.14, ten times for 60 s. That is consistent with the fault
needing two threads in the same difflib code, and proves nothing: it is rare, and with the
machine busy it was not seen at all.

This lock keeps that pairing from happening, and fixes nothing in the interpreter. Each call
holds it for itself alone - one ``ratio()`` of a suggestion, one ``get_close_matches``, one
file's ``get_opcodes()`` - and lets it go as it returns, never around a loop of calls: an
analysis lets it go after each comparison it makes, and a plan after each file it diffs.
"""

from __future__ import annotations

import threading
from typing import Final

ONE_THREAD_IN_DIFFLIB: Final = threading.Lock()
"""Held around each call into :mod:`difflib`, by whichever thread makes it."""
