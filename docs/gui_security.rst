GUI security
============

``ddd gui`` serves one project's description files to a browser, over plain HTTP, on this
computer by default. This page is the threat model its security review settled on: who
``ddd gui`` is built to keep out, who it trusts instead because the alternative costs more
than it is worth, and what is deliberately left open.

What it defends against
-----------------------

* **Another page open in the same browser,** even one served from a different port of
  ``127.0.0.1``. A browser treats every port of one address as the same site, but the
  token is no cookie: the page keeps it in ``localStorage`` for its own origin, port
  included, and sends it as ``Authorization: Bearer`` itself, rather than a browser
  attaching it unasked. For a request to the API, a page elsewhere has no token to send,
  and cannot send ``Authorization`` at all without a CORS preflight, which this server
  never grants - the first defence, in any browser; the gate is the second, refusing a
  request marked, with ``Sec-Fetch-Site``, anything but ``same-origin`` or ``none``, or
  naming an ``Origin`` that is not this server's own, before it reaches a handler -
  ``GET /open`` excepted, which answers the page itself, needing no credential. For a
  navigation to a page, which likewise needs no credential, the gate above is the only
  defence: see *The browsers it protects*, below, for what the one kind of request that
  still reaches a handler with neither header can do there. A refused sign-in, or any
  answer to ``POST /open`` but ``200``, leaves a token the page already holds as it was;
  only a ``401`` from the API clears it, and the page then says it is signed out, other
  tabs on their next request. So no page can sign the reader out by sending a tab to
  ``/open`` with a wrong code. And no page of ``ddd gui`` can be shown inside another: the
  content security policy's ``frame-ancestors 'none'`` refuses every attempt to frame it, so
  another page cannot embed it and act through it.

* **Another server on another port of** ``127.0.0.1`` that the reader's browser is pointed
  at - on an address typed or bookmarked there, or on whatever a page served there asks of
  its own server, a page any site can send the browser to. It is sent nothing: no cookie
  exists to carry the token there, and it cannot read this page's own ``localStorage``, which
  another origin never reaches. A server that used the *same* port before is a different
  case, under *What it does not defend against*: the browser counts it as this very origin.

* **Any other local process or user that reaches the port without the token.** Past the
  check above, every request to the API still needs the token as ``Authorization: Bearer``,
  which no cookie carries any more, and one that changes anything needs this server's own
  ``Origin`` and a json body besides. The token is minted fresh each run and compared in
  constant time; it is never placed on a command line, where any local user could read
  it - the browser ``ddd gui`` opens for the reader is launched on a one-time code
  instead, good for sixty seconds or one use, whichever comes first.

* **Malformed input, from anyone, including the reader's own browser.** No malformed
  input - in a route's query, in a request's body, or in a page's own path - is answered
  ``500``, and no request this server reads in full is left hanging: each is answered with
  a status and a sentence. (A request that stops arriving partway through - its headers, or
  a ``POST``'s promised body, once the server has begun to read it - is closed unanswered
  when its connection has been idle thirty seconds.) In a route's query or body, a path
  holding a NUL character or a lone surrogate, a number many thousands of digits long, and
  a network or device path such as ``\\server\share`` that does not name a path under a
  directory ``ddd gui`` serves are each refused with a plain ``400``, ``404`` or ``409``,
  and so is json nested more than 64 levels deep or holding a number too large to be
  finite, such as ``1e999``, in a query or as the value an edit writes - except a number
  this server's own long poll reads as "wait for a later version": there, anything that is
  not a clean number is treated as none given, and answered at once rather than refused.
  Such a network or device path is refused before anything resolves it, and so is one
  holding a dot segment. On Windows, so is a path holding a name Windows keeps for a device
  (below) as any of its names, refused ``400``: resolving it would ask Windows about every
  directory along it, and Windows opens the device for such a name in whatever directory it
  is written. A path through a loop of links, which python 3.12 cannot resolve, is answered
  as one naming no file ``ddd gui`` can read, on every python. A file an edit would create
  is refused ``409`` before anything looks its name up, let alone writes the file, and so
  is ``GET /api/files-plan``'s plan of one, where the name is longer than 243 bytes, holds
  a character Windows keeps out of a file's name - a control character, or one of
  ``< > : " / \ | ? *`` - ends in a dot or a space, which Windows drops from a file's name,
  or is one Windows keeps for a device (below), on every system - on Windows, an edit
  naming a device's file is refused ``400`` before that, as any path naming a device is:
  the file is staged under its name and ``.ddd-staging`` first, ext4 takes a name of at
  most 255 bytes and NTFS one of at most 255 UTF-16 units, which a name of 255 bytes never
  exceeds, and Windows opens the device in the place of a file named like it. An answer
  carrying json nested more than 99 levels deep - a file's contents, or a part of the
  project's dictionary, each array, object and value in it counted - is refused ``409``
  instead of sent, by whatever route would send it: 99 levels are the most its serializer
  writes on Windows, and so the bound on every system. Two of these refusals name the file
  to blame: ``GET /api/file``'s, of a file nested more than 99 levels deep, and
  ``GET /api/dictionary``'s, of the file stating an extension block nested more than 96
  levels deep, or 98 among the project's own settings. Any other answer too deep is refused
  without naming one. A ``POST`` whose ``Content-Length`` is no length is refused
  ``400``, and one promising more than 1,048,576 bytes ``413``, however many digits it
  is written with, short of a header line too long to be read at all (below). Such a
  refusal closes its connection behind the answer, reading and throwing away what still
  arrives until the client closes, two seconds pass, or 1,048,576 bytes are read,
  whichever is first: closing with bytes still unread resets a connection on Windows,
  which can erase the refusal before the browser reads it. That close follows an answer
  already given, unlike the thirty seconds above, which follows none at all.
  ``POST /open``, which anyone who reaches the port may send without the token, takes at
  most 1,024 bytes - a sign-in body is a few dozen - and a longer one is refused ``413``
  before it is parsed, so no json parser ever runs on a body large or deep enough to
  trouble one. A page's own path is never resolved: it is read as plain names under the
  compiled pages, and a name holding a NUL character, a backslash or a colon, or a dot
  segment, names no file and is never looked up, so neither a network path nor a
  ``\\.\`` device path can be spelled in one. A name Windows keeps for a device names no
  file either, on any system, and is never looked up: ``CON``, ``PRN``, ``AUX`` or
  ``NUL``, or ``COM`` or ``LPT`` followed by a digit from ``0`` to ``9`` or a
  superscript ``¹``, ``²`` or ``³``, in any case and whatever extension it carries, or a
  colon and what follows it. So are ``CONIN$`` and ``CONOUT$``, the console's own input
  and output. A path naming no file is answered the page itself, as any other unknown
  page address is. The standard library itself refuses three shapes before this server
  sees them at all: a request line over 65,536 bytes answers ``414``, and a header line
  over 65,536 bytes, or a request carrying 100 header lines or more - the blank line
  that ends them counted - answers ``431``; ninety-nine is the most ``ddd gui`` ever
  reads.

* **The address printed, opened as ``localhost``.** When it listens on loopback, as it
  does by default, ``ddd gui`` binds an IPv6 address beside its IPv4 socket, on the very
  same port, and never listens on it: ``[::1]`` on Linux and macOS, or, on Windows, the
  wildcard ``[::]`` alone in its place - bound there exclusively
  (``SO_EXCLUSIVEADDRUSE``), as its IPv4 socket is too. So no other program can listen on
  ``localhost`` at that port: a browser trying ``[::1]`` first, which resolving
  ``localhost`` may do, is refused and falls back to ``127.0.0.1``, rather than reaching
  a stranger there - the program that an address rewritten from ``127.0.0.1`` to
  ``localhost`` would otherwise have handed the token to, and that owns the ``localhost``
  origin's storage besides. Measured on Linux and Windows, in Chromium and Edge: what
  macOS refuses beside the hold was not. A fixed ``--port`` already held by another
  program is refused before ``ddd gui`` starts, naming the address ``ddd gui`` tried to
  hold - ``[::1]``, or on Windows ``[::]``; left to the system, ``--port 0`` tries
  another port instead.

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

* **The page's own origin.** The token is kept in its ``localStorage``, readable only by
  script running in this origin; the content security policy's ``default-src 'self'`` runs no
  script but one served from this origin. What may have served this origin before ``ddd gui``
  did - a server on the same port, earlier - is *What it does not defend against*, below.

The table of every route, below, marks which ones may run a project's or a baseline's
plugins: opening a project, comparing against one, an edit or an undo - each re-analysed
afterwards - and a plan whose judgement re-analyses the project with its includes changed.

The browsers it protects
------------------------

The gate above - the check of ``Sec-Fetch-Site`` and ``Origin`` - depends on the browser
sending ``Sec-Fetch-Site``. Chrome 76, Firefox 90, Safari 16.4 and every later release do,
on every request; the last of them, Safari 16.4, shipped in March 2023.

An older browser sends neither header on a plain request - a navigation, or a request
with no ``Origin``, such as an image - so the gate lets it through. Sent to the API, it
carries no credential either: the token is in this page's own ``localStorage``, which a
page on another port cannot read, and such a page cannot send ``Authorization`` without a
CORS preflight, which this server never grants - and it is answered ``401``, like any
other refusal. Sent to a page, it is answered the page itself, which signs itself in from
its own storage and asks for whatever its address names: a site that knows the port - the
system picks a fresh one each run, unless ``--port`` names one - and the path of a file
the project includes can so open a Files row's Remove panel. There it waits, saying only
that taking it out of the includes is planned when asked, until the reader presses for
the plan, which then re-analyses the project, running its plugins. Nothing is written
without the reader's own click, and nothing that runs plugins is asked on arrival. Use
one of the browsers above.

In every browser, the gate lets through by design a navigation marked
``Sec-Fetch-Site: none``, which a browser sends for a navigation it begins itself - an
address typed, or chosen from a bookmark - and an older browser marks such a navigation
with nothing. Either way it lands, signed in, on the page its address names, just as above,
as it did when the token was a cookie: a ``SameSite=Strict`` cookie rode the same
navigations. Open ``ddd gui``'s pages from the address it prints, or from the page itself,
rather than from a link someone else wrote.

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

* **A local denial of service.** ``ddd gui`` answers at most sixty-four connections at
  once, each on a thread of its own; the sixty-fifth is refused before a thread is even
  started for it, ``503``. That keeps the machine's threads from being exhausted, not the
  page available: anyone who can reach the port, token or not, can still open and hold
  sixty-four connections, and so deny the page its server - though a connection idle for
  thirty seconds is closed and gives its slot back, so holding one takes writing to it at
  least that often. A browser never comes near that limit by itself - six connections to
  one host, across every tab - so this is a risk from another local process or user, not
  from ordinary use.

* **The moment of launch.** ``GET /open`` answers the page itself and spends nothing, so
  a browser's prefetch of the launch address cannot spend the code; the page then posts
  the code, or the token from a pasted address, to ``POST /open`` and keeps the token it
  is answered. The browser is handed a one-time code instead of the long-lived token, so
  the token itself never sits on a command line. But a local process reading the
  launcher's command line - polling ``/proc``, on Linux - and presenting that code before
  the reader's browser does is signed in with the token for as long as this run of
  ``ddd gui`` lasts - not merely ahead of the reader once. Two things show this happened:
  the reader's own browser shows it is signed out instead of landing on the project, and
  presenting that same code again prints one line on the terminal, saying so and to
  restart ``ddd gui`` rather than open the address it printed - a restart takes the token
  from the winner, and the printed address would not. The same two signs also follow an
  innocent cause: the first ``POST /open`` reaches the server and spends the code, but
  its answer is lost on the way back, so the page sends the same code once more; the
  server refuses it as already spent, and the terminal prints the very same line - no
  other process involved. Either way, its advice is the same: restart ``ddd gui``. A code
  that expired unused signed nobody in, and prints nothing.

* **A server that used the same port before.** The page's origin is its address and port,
  and the browser keeps what a server on them left behind into any later run on that port.
  Unless ``--port`` names one, the system picks a port that is free when ``ddd gui``
  starts, which an earlier server may still have used; a fixed ``--port``, as a container
  needs, is the same origin every run. A service worker an earlier server registered there
  survives it, and nothing ``ddd gui`` answers removes it: it sees the launch's code, the
  token the page is answered, and every request the page sends. So does a script an
  earlier server answered one of the compiled pages' own hashed asset paths with, under a
  long ``max-age``: the browser runs that cached script when a page ``ddd gui`` later
  serves names that path, because the content security policy admits any script from this
  origin and cannot tell one the browser cached from one ``ddd gui`` served. Either one can
  take the token. Open ``ddd gui`` in a browser profile of its own, one nothing else is
  browsed in, above all with a fixed ``--port``.

* **Beyond loopback, as in a container.** There ``ddd gui`` listens on
  ``--host 0.0.0.0``, published on the host's ``127.0.0.1`` alone, as *Running it in a
  container* above describes, and the IPv6 hold, being loopback's alone, holds nothing
  there. The host's ``[::1]`` at that port is open all the same, to a program already
  listening on it, which may receive ``localhost:<port>/open?token=<the token>`` in the
  container's place. Open the address exactly as ``ddd gui`` prints it.

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
for something to change. It lists the api alone: ``GET /open``, which the gate does not
check, answers the page, and ``POST /open`` trades a code or the token for the token;
neither needs a credential, and the ``POST`` passes the gate and a ``POST``'s rules. The
pages need none either; every route below needs the token as a header.

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
