GUI security
============

``ddd gui`` serves one project's description files to a browser, over plain HTTP, on this
computer by default. This page is the threat model its security review settled on: who
``ddd gui`` is built to keep out, who it trusts instead because the alternative costs more
than it is worth, and what is deliberately left open.

What it defends against
-----------------------

* **Another page open in the same browser,** even one served from a different port of
  ``127.0.0.1``. A browser treats every port of one address as the same site, and sends
  such a page this server's own cookie regardless. In a browser that marks every request
  with ``Sec-Fetch-Site`` - Chrome 76, Firefox 90, Safari 16.4 and later - that is checked
  before the cookie is even read: a request marked anything but ``same-origin`` or ``none``,
  or naming an ``Origin`` that is not this server's own, is refused before it reaches a
  handler. An older browser sends neither header on a plain request; see *The browsers it
  protects*, below, for what still holds there and what does not. The server of a page on
  another port of ``127.0.0.1`` is another matter: it receives the cookie itself
  (*Another server on* ``127.0.0.1``, below).

* **Any other local process or user that reaches the port without the token** - short of
  one running a server on ``127.0.0.1`` that the reader's browser is pointed at, which
  receives the token in the cookie (*Another server on* ``127.0.0.1``, below). Past the
  check above, every request still needs the cookie ``/open`` traded the token for, and
  one that changes anything needs this server's own ``Origin`` and a json body besides.
  The token is minted fresh each run and compared in constant time; it is never placed on
  a command line, where any local user could read it - the browser ``ddd gui`` opens for
  the reader is launched on a one-time code instead, good for sixty seconds or one use,
  whichever comes first.

* **Malformed input, from anyone, including the reader's own browser.** No malformed
  input - in a route's query, in a request's body, or in a page's own path - is answered
  ``500``, and no request this server reads in full is left hanging: each is answered with
  a status and a sentence. (A request that stops arriving partway through - its headers, or
  a ``POST``'s promised body, once the server has begun to read it - is closed unanswered
  when its connection has been idle thirty seconds.) In a route's query or body, a path
  holding a NUL character or a lone surrogate, a number many thousands of digits long, and
  a network or device path such as ``\\server\share`` that does not name a path under a
  directory ``ddd gui`` serves are each refused with a plain ``400``, ``404`` or ``409``,
  and so is json nested more than 64 levels deep, in a query or as the value an edit
  writes - except a number this server's own long poll reads as "wait for a later version":
  there, anything that is not a clean number is treated as none given, and answered at once
  rather than refused. Such a network or device path is refused before anything resolves
  it, and so is one holding a dot segment. A file an edit would create is refused ``409``
  before anything looks its name up, let alone writes the file, and so is
  ``GET /api/files-plan``'s plan of one, where the name is longer than 243 bytes or is one
  Windows keeps for a device (below), on every system: the file is staged under its name
  and ``.ddd-staging`` first, ext4 takes a name of at most 255 bytes and NTFS one of at
  most 255 UTF-16 units, which a name of 255 bytes never exceeds, and Windows opens the
  device in the place of a file named like it. An answer carrying json nested more than 99
  levels deep - a file's contents, or a part of the project's dictionary, each array,
  object and value in it counted - is refused ``409`` instead of sent, by whatever route
  would send it: 99 levels are the most its serializer writes on Windows, and so the bound
  on every system. Two of these refusals name the file to blame: ``GET /api/file``'s, of a
  file nested more than 99 levels deep, and ``GET /api/dictionary``'s, of the file stating
  an extension block nested more than 96 levels deep, or 98 among the project's own
  settings. Any other answer too deep is refused without naming one. A ``POST`` whose
  ``Content-Length`` is no length is refused ``400``, and one promising more than 1,048,576
  bytes ``413``, however many digits it is written with, short of a header line too long to
  be read at all (below). A page's own path is never resolved: it is read as plain names
  under the compiled pages, and a name holding a NUL character, a backslash or a colon, or
  a dot segment, names no file and is never looked up, so neither a network path nor a
  ``\\.\`` device path can be spelled in one. A name Windows keeps for a device names no
  file either, on any system, and is never looked up: ``CON``, ``PRN``, ``AUX`` or ``NUL``,
  or ``COM`` or ``LPT`` followed by a digit from ``0`` to ``9`` or a superscript ``¹``,
  ``²`` or ``³``, in any case and whatever extension it carries. So are ``CONIN$`` and
  ``CONOUT$``, the console's own input and output. A path naming no file is answered the
  page itself, as any other unknown page address is. The standard library itself refuses
  three shapes before this server sees them at all: a request line over 65,536 bytes
  answers ``414``, and a header line over 65,536 bytes, or a request carrying 100 header
  lines or more - the blank line that ends them counted - answers ``431``; ninety-nine is
  the most ``ddd gui`` ever reads.

What it trusts
--------------

* **The project the reader opens, and its plugins.** They run when the project is
  analysed, exactly as they run under ``ddd check``.

* **A baseline the reader compares against, and its plugins.** They run exactly as they
  run under ``ddd compare``.

* **The directory** ``ddd gui`` **was started in.** The project's own files may name files
  above that directory, and ``ddd gui`` reads them.

* **Whoever holds the token.** It is the key: whoever started ``ddd gui`` holds it, and so
  does anyone its terminal shows it to. The printed address is for pasting into a browser's
  own address bar; clicked in the terminal instead, it is handed to an opener such as
  ``xdg-open`` on its command line, which any local user can read while it runs.

The table of every route, below, marks which ones may run a project's or a baseline's
plugins: opening a project, comparing against one, an edit or an undo - each re-analysed
afterwards - and a plan whose judgement re-analyses the project with its includes changed.

The browsers it protects
------------------------

The gate above - the check of ``Sec-Fetch-Site`` and ``Origin`` that runs before the
cookie - depends on the browser sending ``Sec-Fetch-Site``. Chrome 76, Firefox 90, Safari
16.4 and every later release do, on every request; the last of them, Safari 16.4, shipped
in March 2023.

An older browser sends neither header on a plain request, so the gate lets it through; the
browser still attaches the cookie, since every port of ``127.0.0.1`` is one site to it, so
the request is answered as if it came from this server's own page. What still holds there:
that page cannot read the answer, and it cannot ``POST``, which needs this server's own
``Origin`` and a json body, neither of which it can forge. What does not: a ``GET`` that
runs plugin code is still answered - ``/api/compare``, for a baseline under the directory
``ddd gui`` was started in, and ``/api/files-plan`` - so its side effect happens whether or
not the page ever reads the reply. Use one of the browsers above.

Running it in a container
-------------------------

Publish the port on the host's loopback alone, never wider: ``-p 127.0.0.1:8123:8123``. A
different number on the host side would misdirect the ``Host`` header ``ddd gui`` checks,
answered ``421``. Published beyond the host's own loopback, the token in the printed
address is the only barrier left: a client that merely reaches the port can forge both
``Host`` and ``Origin``. ``ddd gui`` says so on its own terminal the moment it is asked to
listen beyond loopback.

What it does not defend against
-------------------------------

* **Another server on** ``127.0.0.1``. A browser keeps no cookie apart by port, so the
  reader's browser sends ``ddd gui``'s cookie to any other server on ``127.0.0.1`` it is
  pointed at: on an address typed or bookmarked there, and on whatever a page served there
  asks of its own server - a page any site can send the browser to. The cookie's value is
  the token, so whoever runs such a server - another user of this computer, a container or
  a virtual machine with a port on this computer's loopback, a sandboxed application -
  receives the token, and can then do whatever the reader can do with ``ddd gui``: run code
  as the reader among it, since an edit can name a plugin of theirs, which the next
  analysis runs. So keep ``ddd gui`` in a browser profile of its own, browse nothing else
  on ``127.0.0.1`` in that profile, and stop ``ddd gui`` when done with it.

* **A local denial of service.** ``ddd gui`` answers at most sixty-four connections at
  once, each on a thread of its own; the sixty-fifth is refused before a thread is even
  started for it, ``503``. That keeps the machine's threads from being exhausted, not the
  page available: anyone who can reach the port, token or not, can still open and hold
  sixty-four connections, and so deny the page its server - though a connection idle for
  thirty seconds is closed and gives its slot back, so holding one takes writing to it at
  least that often. A browser never comes near that limit by itself - six connections to
  one host, across every tab - so this is a risk from another local process or user, not
  from ordinary use.

* **The moment of launch.** The browser is handed a one-time code instead of the
  long-lived token, so the token itself never sits on a command line. But a local process
  reading the launcher's command line - polling ``/proc``, on Linux - and presenting that
  code before the reader's browser does is signed in with the token for as long as this
  run of ``ddd gui`` lasts - not merely ahead of the reader once. Two things show this
  happened: the reader's own browser lands on the sign-in page instead of the project, and
  presenting that same code again without the cookie its winner was given prints one line
  on the terminal, saying so.

* **Transport security.** ``ddd gui`` speaks plain HTTP, trusting the loopback interface
  or, in a container, the host's own. Nothing here signs or encrypts what crosses it.

Reporting a vulnerability
-------------------------

See `SECURITY.md <https://github.com/Sauci/ddd/blob/master/SECURITY.md>`_, at the root of
the repository, to report a vulnerability privately.

Every route
-----------

Every request that reaches a handler has already passed the gate above. The table below
adds, route by route, what each one does once it has: whether it writes a file of the open
project, opens a project, may run a plugin's code, or may hold its answer open, waiting
for something to change. It lists the api alone: ``GET /open`` trades the token or a code
for the cookie, and is not checked by the gate; the pages need the cookie, as every route
below does.

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
