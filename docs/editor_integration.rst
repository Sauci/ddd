Editor integration
==================

A json schema validates one file, statically, and that is where its usefulness ends: whether
an ``axis`` names an axis some component declares, whether exactly one component produces a
variable, whether two components agree on a unit - none of that is visible from a single
file. Those questions need the whole project resolved, which is what ``ddd lsp`` brings into
the editor: a language server that runs the same loader, the same analysis and the same
severity policy as ``ddd check``, so the editor never disagrees with the build about what is
wrong.

.. The '-b' invocation line is elided: argparse spells it differently on python 3.12 and 3.13.

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
     ...
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
on open, on save, and when the editor reports that a description file it watches changed on
disk - a build writes them and a branch switch rewrites them all, and neither is something
a document event would report. Each is drawn over the key it is about rather than over the
whole file. The
server publishes for **every** file of the project rather than only the one on screen,
because half of a disagreement is always in the other component, and each finding is also
published at the locations of its notes - of two components declaring the same output,
neither is the innocent one, so both carry a mark. A component linked into two images is
checked under both, and one mistake in it is drawn once: two images reporting the same
finding in the same words are not two mistakes. Where their severities differ they are
saying two different things, and both are published.

Everything the server publishes, answers and edits is spelled the way the client spelled the
document it opened, and resolved for every file it never opened. An editor matches a
publication to what is on screen by comparing the uri *string*, and a workspace opened
through a junction, a substituted or mapped drive, a symlinked directory or with a different
case spells every path in it differently from the way the loader resolves it.

**Hover.** A summary of the data object under the cursor, resolved against the whole
project rather than read off the file: the shape a curve took from its axis, the limits
derived from a datatype and a conversion nobody wrote down, its producer and its consumers,
what an enum's numbers are called, the physical reading of a scalar ``init`` beside the raw
value the file states, and the initial values as a sparkline. Those are the *initial*
values - DDD describes an interface, and what an engineer calibrates lives in the
calibration tool. A dimension spelled as the name of a
:doc:`declared constant <file_formats/constants>` hovers as the constant itself - its value
and its description - because the number is declared somewhere else, next to the one
statement of what is being counted. A name that names a declared type and no data object -
a type's own entry, or a ``typename`` on a structure member inside a
:doc:`types file <file_formats/types>` - hovers as the type: a structure and its members, a
scalar type's storage and conversion, an external type and the header that defines it.

**Go to definition and find references.** From anywhere in a declaration - or from an
``axis``, ``x_axis``, ``y_axis`` or ``input`` reference - go to definition lands on the
declaration that *writes* the object, in whichever component that is, and find references
lists every declaration of it. The same works from a type name to the structure it names and
back, from a dimension spelled as a constant name to the entry that declares it - in a
constants file, or inside the component that publishes it - and back to every shape that
spells it, and from an ``includes`` entry to the files it matches, wildcards included.

**Rename.** ``F2`` on a variable renames it in every declaration and in every reference that
names it, across as many files as that takes. A declared type is renamed the same way, from
the ``name`` of its entry or from any ``typename`` spelling it, in the file declaring it and
in every definition and structure member naming it; a declared constant from its entry or from
any dimension or axis ``size`` spelling it. A name c reserves, one that is not a usable
identifier, or one the project already uses - for another object, an enum, an enumerator, a
type or a declared constant - is refused with the reason before anything is written, because
a rename that silently merges two objects compiles, links, and shares storage nobody
intended to share; a type may not take the spelling of a base datatype either, which the
loader would refuse. A unit is renamed from any place it is stated, or from its entry in a
units file; renaming onto a unit that already exists merges the two instead of refusing the
collision, as a variable's rename would. It is refused, naming the file, only while a file of
the project does not load at all - a unit listed twice, reported as ``duplicate-unit``, does
not stop it, because renaming may be how such a mistake is fixed. Only the characters between
the quotes are replaced, so formatting survives and free text is left alone.

A variable's, a type's or a constant's rename, and every quick fix below, is also refused -
naming the file, and before anything is written - while the project on disk is not the
project the edit would be computed from: while an open document has unsaved changes that
moved a declaration the edit would touch, and while a file of the project reported an error
that stopped it being read. A project is indexed from what loaded, so a file a ``schema``
error dropped mid edit declares nothing as far as the index knows: the rename would rewrite
every other file and leave that one holding the old name, and a fix would offer to remove a
key "no other declaration has" while the unloaded producer states exactly that key. Fix the
file and ask again.

**Quick fixes.** On a key the declarations of one object have to agree on - a ``unit``, a
``conversion``, a ``datatype`` - a ``definition-mismatch`` offers every way of reconciling
it: take the producing component's value, spread this one to the others, or, when nobody
else states the key, remove it. ``limits`` are the exception to the last: a declaration that
leaves them out defers to the one that states them, which the checker counts as agreement, so
only two stated ranges that differ are offered a fix. A declaration naming a declared type is
an exception of its own: the type fixes its ``unit``, ``conversion`` and ``limits``, which may
not be stated beside the ``typename``, so none of the three is offered to it, and spreading
one of them to the other declarations leaves it out. The value is copied as source text rather
than re-serialised, so the project's formatting survives the fix.

A ``missing-id`` offers one fix of its own: give this object an identity. It writes the same
key ``ddd id --assign`` would write, in the same place, decided by the same code - the command
stamps a whole file, the fix stamps the declaration you are looking at. It is offered only
where the finding is: a project that has silenced ``missing-id`` has said it is not adopting
ids yet, and the editor does not argue with that.

An ``unknown-unit`` finding, which only a project with a vocabulary reports, offers two fixes
of its own: "Add 'RPM' to the vocabulary", and, for each spelling close enough to suggest,
"Rename 'RPM' to 'rpm' everywhere" - the same rename ``F2`` makes, merging into a unit that
exists. Both are the plans ``ddd gui`` previews and applies, so the editor and the page never
disagree about what either does; a plan that is refused is not offered.

Which project a file belongs to
-------------------------------

A description file cannot say which project it belongs to - in the collected CMake mode the
project description exists only in the build tree - so the server reads the
``ddd-build.json`` record that ``ddd_generate()`` writes at configure time (see
:doc:`build_integration`), and applies the severities the build applies. The search runs in
three stages:

* **Build records.** The directories named with ``-b`` are searched recursively for
  ``ddd-build.json``; unconfigured, the conventional directories ``build``, ``out`` and
  ``cmake-build-*`` under the workspace are. A ``-b`` path is taken as written, so a relative
  one is relative to the directory the server was started in - the workspace folder, where
  the VS Code extension starts it, which is what makes a bare ``build`` mean the one beside
  the sources. A file claimed by several builds is checked under each of them and the
  findings are published together - a component linked into two images is in two projects,
  and the answer to which one the reader cares about is both. Each record is counted under
  the path it resolves to, so a link inside a build tree does not turn one record into a
  record per way of spelling it.
  The records a search discovers are announced as log messages, and a record written by a
  newer DDD, or that names a check this version of DDD has not got, is skipped and the reason
  announced with it - skipped in silence, a record nothing can use looks exactly like a
  workspace nobody ever configured a build in. A file that is not a build record at all is
  skipped without a word: a build wrote it, and nobody fixes it in an editor. A record whose
  severities name a *plugin's* check that no plugin of the project registers is reported as a
  ``plugin-invalid`` finding on the project file, which is what ``ddd check`` refuses the
  same ``-W`` for.
* **A containing project.** A file no build record claims is looked for in a containing
  project instead: the server walks from the file's directory up to the workspace root and
  checks the file under the project descriptions of the nearest directory that include it.
  A file that is itself a project description is checked as the project it is, rather than
  searched for above: it lists its components, so every check has what it needs, and the
  checks that need the whole project are exactly the ones somebody opening a project file is
  asking about.
  This stage applies the **default** severities of the :doc:`checks <consistency_checks>` -
  no ``-W``, no ``--strict`` - because those are properties of a build and no build record
  named this file.
  A description the server cannot read, because a plugin of its own raises, is named as a
  ``plugin-invalid`` finding on that description, and the opened file falls through to the
  standalone checks below - so the thinner answer is never given silently.
* **Standalone.** A file belonging to no build, to no such project, and declaring no project
  of its own is still checked, on
  its own, but only for what one file can decide. The nine checks that need every component
  of a project - ``unknown-type``, ``unknown-unit``, ``unknown-section``,
  ``unknown-constant``, ``unknown-raster``, ``unknown-extension``, ``missing-producer``,
  ``unknown-reference`` and ``unused-output`` - are held back, because a component read alone
  has inputs nobody produces and outputs nobody reads by construction rather than by mistake.
  A declaration one of them drops is dropped in silence too: ``incomplete-project`` says that
  the dictionary is a variable short, and the file that declares the constant, the raster or
  the type is simply one this server was not shown. Each check declares whether it needs the
  whole project, so the two modes cannot drift apart.

What the server runs
--------------------

A project names its :doc:`plugins <plugins>` in its description, and the server runs the
plugins of every project it analyses: the ones the build records name, the ones lying at or
above an opened file that turn out to include it, and, in the asking, every description file
it opens at or above that file to find out whether it does:
a plugin is imported when its project is read, whether or not that project is then analysed.
Opening a description file in a checked out repository is therefore running the python that
repository ships, exactly as ``ddd check`` on it would - the difference is that nobody typed
the command. Open a repository in the editor only when you would run its build. The VS Code
extension declines a workspace that has not been trusted (VS Code's *Restricted Mode*), so
the server starts only once you have said so; an editor that launches the server itself has
to make the same decision.

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
       ``ddd-build.json``; a relative entry is relative to the workspace folder, which is
       where the extension starts the server. Left empty, the conventional build directory
       names next to the workspace are searched.

The command is **DDD: Restart Language Server**, for picking up a newly installed tool
without reloading the window.

Every release attaches a ``ddd-<version>.vsix`` to its `GitHub release
<https://github.com/Sauci/ddd/releases>`_, which is a permanent link needing no account and
no network policy exception. That installs with ``code --install-extension
ddd-<version>.vsix`` or through **Install from VSIX...** in the Extensions view, and updates
no more automatically than any other file, so reinstall it when the python package is
upgraded - the extension and the python package share a version number, and an update to one
is worth the other.
