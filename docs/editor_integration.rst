Editor integration
==================

A json schema validates one file, statically, and that is where its usefulness ends: whether
an ``axis`` names an axis some component declares, whether exactly one component produces a
variable, whether two components agree on a unit - none of that is visible from a single
file. Those questions need the whole project resolved, which is what ``ddd lsp`` brings into
the editor: a language server that runs the same loader, the same analysis and the same
severity policy as ``ddd check``, so the editor never disagrees with the build about what is
wrong.

.. code-block:: text

   $ ddd lsp --help
   usage: ddd lsp [-h] [-b DIR]

   Speaks the Language Server Protocol on stdin and stdout. It reports the
   consistency checks while a description file is being written, which a json
   schema cannot do: whether an axis names a declared axis, whether exactly one
   component produces a name, whether two components agree on a unit. Which
   project a file belongs to is read from the 'ddd-build.json' that ddd_generate
   writes, so the editor and the build apply the same severities.

   options:
     -h, --help            show this help message and exit
     -b, --build-directory DIR
                           directory holding a build of this project; repeatable.
                           Without it the usual build directory names next to the
                           workspace are searched

The command is not meant to be run by hand: it speaks the Language Server Protocol on stdin
and stdout and expects an editor on the other end. Editors that launch language servers
themselves - Neovim, Helix, Emacs - need only the command; VS Code needs the extension
described at the bottom of this page.

What the server offers
----------------------

**Diagnostics.** The findings of the :doc:`consistency checks <consistency_checks>`, reported
on open and on save, each drawn over the key it is about rather than over the whole file. The
server publishes for **every** file of the project rather than only the one on screen,
because half of a disagreement is always in the other component, and each finding is also
published at the locations of its notes - of two components declaring the same output,
neither is the innocent one, so both carry a mark.

**Hover.** A summary of the data object under the cursor, resolved against the whole
project rather than read off the file: the shape a curve took from its axis, the limits
derived from a datatype and a conversion nobody wrote down, its producer and its consumers,
what an enum's numbers are called, the physical reading of a scalar ``init`` beside the raw
value the file states, and the initial values as a sparkline. Those are the *initial*
values - DDD describes an interface, and what an engineer calibrates lives in the
calibration tool. A dimension spelled as the name of a
:doc:`declared constant <file_formats/constants>` hovers as the constant itself - its value
and its description - because the number is declared somewhere else, next to the one
statement of what is being counted.

**Go to definition and find references.** From anywhere in a declaration - or from an
``axis``, ``x_axis``, ``y_axis`` or ``input`` reference - go to definition lands on the
declaration that *writes* the object, in whichever component that is, and find references
lists every declaration of it. The same works from a type name to the structure it names and
back, from a dimension spelled as a constant name to the entry that declares it - in a
constants file, or inside the component that publishes it - and back to every shape that
spells it, and from an ``includes`` entry to the files it matches, wildcards included.

**Rename.** ``F2`` on a variable renames it in every declaration and in every reference that
names it, across as many files as that takes. A name c reserves, one that is not a usable
identifier, or one the project already uses - for another object, an enum, an enumerator, a
type or a declared constant - is refused with the reason before anything is written, because
a rename that silently merges two objects compiles, links, and shares storage nobody
intended to share. Renaming starts from a variable; a type or a constant is renamed where
it is declared, which is one file rather than a project wide rewrite. Only the characters
between the quotes are replaced, so formatting survives and free text is left alone.

**Quick fixes.** On a key the declarations of one object have to agree on - a ``unit``, a
``conversion``, a ``datatype`` - a ``definition-mismatch`` offers every way of reconciling
it: take the producing component's value, spread this one to the others, or, when nobody
else states the key, remove it. The value is copied as source text rather than
re-serialised, so the project's formatting survives the fix.

A ``missing-id`` offers one fix of its own: give this object an identity. It writes the same
key ``ddd id --assign`` would write, in the same place, decided by the same code - the command
stamps a whole file, the fix stamps the declaration you are looking at. It is offered only
where the finding is: a project that has silenced ``missing-id`` has said it is not adopting
ids yet, and the editor does not argue with that.

Which project a file belongs to
-------------------------------

A description file cannot say which project it belongs to - in the collected CMake mode the
project description exists only in the build tree - so the server reads the
``ddd-build.json`` record that ``ddd_generate()`` writes at configure time (see
:doc:`build_integration`), and applies the severities the build applies. The search runs in
three stages:

* **Build records.** The directories named with ``-b`` are searched recursively for
  ``ddd-build.json``; unconfigured, the conventional directories ``build``, ``out`` and
  ``cmake-build-*`` under the workspace are. A file claimed by several builds is checked
  under each of them and the findings are published together - a component linked into two
  images is in two projects, and the answer to which one the reader cares about is both.
  The records a search discovers are announced as log messages, and a record that cannot be
  read is skipped.
* **A containing project.** A file no build record claims is looked for in a containing
  project instead: the server walks from the file's directory up to the workspace root and
  checks the file under the project descriptions of the nearest directory that include it.
* **Standalone.** A file belonging to no build and to no such project is still checked, on
  its own, but only for what one file can decide. The ten checks that need every component
  of a project - ``unknown-type``, ``unknown-unit``, ``unknown-section``,
  ``unknown-constant``, ``unknown-raster``, ``unknown-extension``, ``missing-producer``,
  ``unknown-reference``, ``unused-output`` and ``incomplete-project`` - are held back,
  because a component read alone has inputs nobody produces and outputs nobody reads by
  construction rather than by mistake. Each check declares whether it needs the whole
  project, so the two modes cannot drift apart.

VS Code
-------

VS Code cannot start a language server without an extension, so one is shipped in
``editors/vscode``. It is a launcher and deliberately nothing more - everything a reader
sees is the server's answer, so an editor DDD ships nothing for is not at a disadvantage.
It contributes two settings and one command:

.. list-table::
   :header-rows: 1
   :widths: 34 66

   * - setting
     - meaning
   * - ``ddd.executable``
     - the ``ddd`` command to run the server with. Left as the bare name it is looked up on
       the ``PATH``; set it to an absolute path to use the interpreter of a virtual
       environment.
   * - ``ddd.buildDirectories``
     - the directories handed to the server as ``-b``, each searched for a
       ``ddd-build.json``. Left empty, the conventional build directory names next to the
       workspace are searched.

The command is **DDD: Restart Language Server**, for picking up a newly installed tool
without reloading the window.

Every release attaches a ``ddd-<version>.vsix`` to its `GitHub release
<https://github.com/Sauci/ddd/releases>`_, which is a permanent link needing no account and
no network policy exception. That installs with ``code --install-extension
ddd-<version>.vsix`` or through **Install from VSIX...** in the Extensions view, and updates
no more automatically than any other file, so reinstall it when the python package is
upgraded - the extension and the python package share a version number, and an update to one
is worth the other.
