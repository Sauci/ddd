GUI security
============

``ddd gui`` serves one project's description files to a browser, over plain HTTP, on this
computer by default. This page is the threat model its security review settled on: who
``ddd gui`` is built to keep out, who it trusts instead because the alternative costs more
than it is worth, and what is deliberately left open.

What it defends against
------------------------

* **Another page open in the same browser,** even one served from a different port of
  ``127.0.0.1``. A browser treats every port of one address as the same site, and sends
  such a page this server's own cookie regardless, so every request is marked with
  ``Sec-Fetch-Site`` and checked before the cookie is even read: one marked anything but
  ``same-origin`` or ``none``, or naming an ``Origin`` that is not this server's own, is
  refused - a page on another port, cookie and all, never reaches a handler.

* **Any other local process or user that reaches the port without the token.** Past the
  check above, every request still needs the cookie ``/open`` traded the token for, and
  one that changes anything needs this server's own ``Origin`` and a json body besides.
  The token is minted fresh each run and compared in constant time; it is never placed on
  a command line, where any local user could read it - the browser ``ddd gui`` opens for
  the reader is launched on a one-time code instead, good for sixty seconds or one use,
  whichever comes first.

* **Malformed input, from anyone, including the reader's own browser.** Every request is
  answered with a status and a sentence - never a ``500``, and never a hang. A path
  holding a NUL character or a lone surrogate, a number many thousands of digits long,
  JSON nested thousands of levels deep, and a network or device path such as
  ``\\server\share`` that does not name a path under a directory ``ddd gui`` serves are
  each refused with a plain ``400``, ``404`` or ``409``. So are the shapes the standard
  library itself refuses before this server sees them at all: a request line over 65,536
  bytes answers ``414``, and a request carrying 100 header lines or more - the blank line
  that ends them counted - answers ``431``; ninety-nine is the most ``ddd gui`` ever
  reads.

What it trusts
---------------

* **The project the reader opens, and its plugins.** They run when the project is
  analysed, exactly as they run under ``ddd check``.

* **A baseline the reader compares against, and its plugins.** They run exactly as they
  run under ``ddd compare``.

* **The directory ``ddd gui`` was started in.** The project's own files may name files
  above that directory, and ``ddd gui`` reads them.

* **Whoever holds the token.** It is the key: whoever started ``ddd gui`` holds it, and so
  does anyone its terminal, its process list, or the address once pasted is shown to.

The table of every route, below, marks which ones may run a project's or a baseline's
plugins: opening a project, comparing against one, an edit or an undo - each re-analysed
afterwards - and a plan whose judgement re-analyses the project with its includes changed.

The browsers it protects
--------------------------

The gate above - the check of ``Sec-Fetch-Site`` and ``Origin`` that runs before the
cookie - depends on the browser sending ``Sec-Fetch-Site``. Chrome 76, Firefox 90, Safari
16.4 and every later release do, on every request; all three have shipped since 2023.

An older browser sends neither header on a plain navigation, so a page on another port can
still make it ask ``ddd gui`` something. A reader on such a browser is protected the way
any other local process is kept out: by the token alone.

Running it in a container
---------------------------

Publish the port on the host's loopback alone, never wider: ``-p 127.0.0.1:8123:8123``. A
different number on the host side would misdirect the ``Host`` header ``ddd gui`` checks,
answered ``421``. Published beyond the host's own loopback, the token in the printed
address is the only barrier left: a client that merely reaches the port can forge both
``Host`` and ``Origin``. ``ddd gui`` says so on its own terminal the moment it is asked to
listen beyond loopback.

What it does not defend against
---------------------------------

* **A local denial of service.** ``ddd gui`` answers at most sixty-four connections at
  once, each on a thread of its own; the sixty-fifth is refused before a thread is even
  started for it. That keeps the machine's threads from being exhausted, not the page
  available: anyone who can reach the port, token or not, can still open and hold
  sixty-four connections, and so deny the page its server for as long as they keep them
  open. A browser never comes near that limit by itself - six connections to one host,
  across every tab - so this is a risk from another local process or user, not from
  ordinary use.

* **The moment of launch.** The browser is handed a one-time code instead of the
  long-lived token, so the token itself never sits on a command line. But a local process
  that reads the launcher's own command line, or that polls for a connection, and presents
  that code before the reader's browser does is signed in with the token for as long as
  this run of ``ddd gui`` lasts - not merely ahead of the reader once. The only sign this
  happened is on the terminal: presenting that same code again without the cookie its
  winner was given prints one line there, saying so.

* **Transport security.** ``ddd gui`` speaks plain HTTP, trusting the loopback interface
  or, in a container, the host's own. Nothing here signs or encrypts what crosses it.

Reporting a vulnerability
---------------------------

See `SECURITY.md <https://github.com/Sauci/ddd/blob/master/SECURITY.md>`_, at the root of
the repository, to report a vulnerability privately.

Every route
------------

Every request that reaches a handler has already passed the gate above. The table below
adds, route by route, what each one does once it has: whether it writes a file of the open
project, opens a project, may run a plugin's code, or may hold its answer open, waiting
for something to change.

.. _gui-security-routes:

.. list-table::
   :header-rows: 1
   :widths: 8 22 10 16 14 10

   * - Method
     - Path
     - Writes
     - Opens a project
     - Runs plugins
     - Waits
   * - ``GET``
     - ``/api/session``
     - 
     - 
     - 
     - 
   * - ``GET``
     - ``/api/projects``
     - 
     - 
     - 
     - 
   * - ``POST``
     - ``/api/open``
     - 
     - yes
     - yes
     - 
   * - ``GET``
     - ``/api/state``
     - 
     - 
     - 
     - yes
   * - ``GET``
     - ``/api/findings``
     - 
     - 
     - 
     - 
   * - ``GET``
     - ``/api/file``
     - 
     - 
     - 
     - 
   * - ``GET``
     - ``/api/dictionary``
     - 
     - 
     - 
     - 
   * - ``GET``
     - ``/api/graph``
     - 
     - 
     - 
     - 
   * - ``GET``
     - ``/api/checks``
     - 
     - 
     - 
     - 
   * - ``POST``
     - ``/api/edit``
     - yes
     - 
     - yes
     - 
   * - ``GET``
     - ``/api/undo``
     - 
     - 
     - 
     - 
   * - ``POST``
     - ``/api/undo``
     - yes
     - 
     - yes
     - 
   * - ``GET``
     - ``/api/variable``
     - 
     - 
     - 
     - 
   * - ``GET``
     - ``/api/units``
     - 
     - 
     - 
     - 
   * - ``GET``
     - ``/api/settle``
     - 
     - 
     - 
     - 
   * - ``GET``
     - ``/api/fix``
     - 
     - 
     - 
     - 
   * - ``GET``
     - ``/api/unit``
     - 
     - 
     - 
     - 
   * - ``GET``
     - ``/api/unit-plan``
     - 
     - 
     - 
     - 
   * - ``GET``
     - ``/api/types``
     - 
     - 
     - 
     - 
   * - ``GET``
     - ``/api/type``
     - 
     - 
     - 
     - 
   * - ``GET``
     - ``/api/type-plan``
     - 
     - 
     - 
     - 
   * - ``GET``
     - ``/api/shared``
     - 
     - 
     - 
     - 
   * - ``GET``
     - ``/api/constant``
     - 
     - 
     - 
     - 
   * - ``GET``
     - ``/api/constant-plan``
     - 
     - 
     - 
     - 
   * - ``GET``
     - ``/api/section``
     - 
     - 
     - 
     - 
   * - ``GET``
     - ``/api/section-plan``
     - 
     - 
     - 
     - 
   * - ``GET``
     - ``/api/raster``
     - 
     - 
     - 
     - 
   * - ``GET``
     - ``/api/raster-plan``
     - 
     - 
     - 
     - 
   * - ``GET``
     - ``/api/files``
     - 
     - 
     - 
     - 
   * - ``GET``
     - ``/api/files-plan``
     - 
     - 
     - yes
     - 
   * - ``GET``
     - ``/api/declarable``
     - 
     - 
     - 
     - 
   * - ``GET``
     - ``/api/declaration-plan``
     - 
     - 
     - 
     - 
   * - ``GET``
     - ``/api/values``
     - 
     - 
     - 
     - 
   * - ``GET``
     - ``/api/value-plan``
     - 
     - 
     - 
     - 
   * - ``GET``
     - ``/api/values-plan``
     - 
     - 
     - 
     - 
   * - ``GET``
     - ``/api/compare``
     - 
     - 
     - yes
     - 
