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

A request the server fails on, through a defect of its own rather than anything in the files,
is answered with the protocol's internal error, and the session goes on with every finding on
screen. A client shows such a request as a failed request - VS Code with a notification - and
the trace is in the server's log, its standard error, which VS Code shows in the **DDD**
output channel.

What the server offers
----------------------

**Diagnostics.** The findings of the :doc:`consistency checks <consistency_checks>`, reported
on open, on save, and when a description file or a build record changes on disk - a build
writes them and a branch switch rewrites them all, and neither is something a document event
would report. Each is drawn over the key it is about rather than over the whole file. The
findings are the disk's, and an open document's are drawn in its text as the editor holds it:
over the key a finding is about where the unsaved buffer holds it, over the nearest key around
it that the buffer holds where it does not, and at the top of a buffer that is not json. A
finding names its key by its place in the file, so a declaration typed above the one it is
about, in the same list, takes the finding's place until the file is saved. Opens, saves and
watched changes that arrive together are checked together, each project once for all of them:
the server checks the documents they name once it has handled every message already waiting
behind the first of them, and before it answers a request that came after them, never waiting
for a message not yet sent. A save and the change the editor's watcher reports for it,
arriving together, are one analysis of the project however many of its documents are open. The
server publishes for **every** file of the project rather than only the one on screen,
because half of a disagreement is always in the other component, and each finding is also
published at the locations of its notes - of two components declaring the same output,
neither is the innocent one, so both carry a mark. A component linked into two images is
checked under both, and one mistake in it is drawn once: two images reporting the same
finding in the same words are not two mistakes. Where their severities differ they are
saying two different things, and both are published.

The server asks the editor to watch every description file and every build record of the
workspace, once the editor has said it is initialized, where its client takes such a
registration while the session runs, as VS Code's does; a client that does not is asked for
nothing, and a file changed behind it is read again at the next open or save. A build record
changing is a change of which projects there are and of their severities: the open documents
are checked again under the records as they now read, or, while none is open, every file
whose findings are on screen.

Everything the server publishes, answers and edits is spelled the way the client spelled the
document it opened, and resolved for every file it never opened. An editor matches a
publication to what is on screen by comparing the uri *string*, and a workspace opened
through a junction, a substituted or mapped drive, a symlinked directory or with a different
case spells every path in it differently from the way the loader resolves it. A file's findings
are on screen under one spelling at a time: published under its resolved path before it was
opened, they are withdrawn there once they go out under the spelling it was opened with.

**Hover.** A summary of the data object under the cursor, resolved against the whole
project rather than read off the file: the shape a curve took from its axis, the limits
derived from a datatype and a conversion nobody wrote down, who writes it and who reads it in
every project holding the file, what an enum's numbers are called, the physical reading of a
scalar ``init`` beside the raw value the file states, and the initial values as a sparkline.
Those are the *initial* values - DDD describes an interface, and what an engineer calibrates
lives in the calibration tool. A component linked into two images is in two projects, and a
variable it writes is read by the readers of both: the hover names each component once, and
both components where two write one variable. Where it says that no component produces the
variable, or that none reads it, it names under that line every file of those projects that
did not load, since what such a file declares is in no project's answer. Where a plugin stops
the analysis of a project holding the file, the hover names that project under the line -
by its image, or by its description where no build record names one - since who writes the
variable there, and who reads it, is in no answer. A dimension spelled as the name of a
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
names it, across as many files as that takes once the server knows the project holding
them - a ``local`` variable needs none. A declared type is renamed the same way, from
the ``name`` of its entry or from any ``typename`` spelling it, in the file declaring it and
in every definition and structure member naming it; a declared constant from its entry or from
any dimension or axis ``size`` spelling it, in its entry, in every one of those and in every
``condition`` spelling it as a word, where that word alone is rewritten: ``#if`` reads a name
nothing defines as 0, so a condition left spelling the old name would compile its object out
with every check clean. For those three, a name c reserves, one that is not a usable
identifier, or one a project it reaches already uses - for another object, an enum, an
enumerator, a type or a declared constant - is refused with the reason before anything is
written, because a rename that silently merges two objects compiles, links, and shares
storage nobody intended to share; a type may not take the spelling of a base datatype
either, which the loader would refuse. An external type is not renamed at all, from its entry or
from any ``typename``: its name is the one the header defining it spells, which no edit of a
description reaches, so a rename would leave that header defining the old name and stop the build
at its first compile. It is refused, naming the header, wherever a project the rename reaches
declares the type so. A memory section is renamed from its entry in a
:doc:`sections file <file_formats/sections>`, or from the ``section`` key of any definition
placing its data there, and both ends are rewritten together: a rename reaching the entry
alone would leave every one of those definitions naming a section nothing declares. A
measurement raster is renamed the same way, from its entry in a
:doc:`rasters file <file_formats/rasters>`, from the ``raster`` key of any definition
measured in it, or from a component's own ``raster`` default naming it for everything it
produces, and every one of those is rewritten together too: a rename reaching the entry
alone would leave the definitions, or the default, naming a raster nothing declares. One no
file declares - what ``unknown-section`` reports - is renamed at its uses alone, so that the
definitions naming it go on agreeing with each other; what ``unknown-raster`` reports is
renamed the same way, at every definition and every component default naming it, so that
those go on agreeing with each other too. None of the refusals above is about either: a
section's name is a linker string spliced into an attribute rather than a c identifier
emitted as one - letters, digits, ``.``, ``_`` and ``$``, and no length limit - so a leading
dot is an ordinary spelling, and a section may be spelled exactly as a variable is, sharing
no namespace with it; a raster's name is the short name of its XCP event rather than a c
identifier either - printable ASCII with no space, eight characters at most - and it may be
spelled exactly as a variable is too, sharing no namespace with it. What is refused is a
name those characters do not spell, and one a project it reaches already declares as a
section: the format permits two, reporting them as ``duplicate-section``, but each carries
its own ``access`` and ``alignment``, and a rename that merged them would move data into
memory with different properties. A raster answers the same way: a name outside its own
alphabet, or one a project it reaches already declares as a raster, is refused - the format
permits two there as well, reporting them as ``duplicate-raster``, but each carries its own
``event`` and ``cycle``, and a rename that merged them would sample one signal on another's
channel. A unit is renamed from any place it is stated, or from its entry in a units file;
renaming onto a unit that already exists merges the two instead of refusing the collision, as
a variable's rename would. It is refused, naming the file, while a file of a project it reaches
does not load at all, and for no lesser error of a file - a unit listed twice, reported as
``duplicate-unit``, does not stop it, because renaming may be how such a mistake is fixed. A file
that no longer holds the unit where the project was read - an open document with unsaved changes
that moved or respelled it, or a closed file changed on disk since - refuses it as well, naming
the file. Only
the characters between the quotes are replaced - in a ``condition``, the constant's own word,
never a longer identifier holding it - and the new name is written there as json spells it,
escaping the quote or the backslash a raster's name may hold, so formatting survives and free
text is left alone.

A variable's, a type's, a constant's, a section's or a raster's rename is also refused - naming
the file, and before anything is written - and a quick fix below is not offered, while the
project on disk is not the project the edit would be computed from: while an open document has
unsaved changes that moved a declaration the edit would touch, or a closed file changed on disk
since the project was read has moved one, and while a file of the project did not load, or
loaded with an error that stops the project being analysed. A project is indexed from what
loaded, so a file a ``schema`` error dropped mid edit declares nothing as far as the index knows:
the rename would rewrite every other file and leave that one holding the old name, and a fix would
offer to remove a key "no other declaration has" while the unloaded producer states exactly that
key.
In the first state a quick fix is not offered rather than offered for the declarations a buffer, or
a closed file changed on disk, left in place, and nothing is said: a buffer is the reader's own, and
saving it brings the fix back, as the server's reading the file again does for the other. A rename
refused for a closed file changed on disk says so, and goes through once the server has read the
project again: at the next open or save of a document, or when the editor reports the change. In the
second state a request for the quick fixes, which the editor makes at every move of the caret, is
answered with none rather than with an error, which it would show as a failed request each time: an
empty lightbulb in such a project has its reason in the finding of the file that did not load, or
loaded with an error, and in the server's log, which says it once for as long as it stands.
A rename is refused as well, naming the document, while an open document of a project it
reaches holds what its file on disk does not, since the rename is planned from the files and a
mention typed and not saved is one it cannot see; and it is refused when it would rewrite
nothing, which an editor applies without a word. Fix or save the file and ask again.
A rename of anything but a local variable is refused as well, saying that no project is known,
while none is: a component that no build record claims, that no description above it includes
and that declares no project itself is read on its own, and renaming what it shares would
rewrite that one file and leave every other file spelling the name holding it. Put a project
file above it that includes it, or configure the build. And a rename is refused, naming the
description and why, where a description it needs could not be read - one a plugin stops,
whether a build record names it or the search above a file found it: the files it holds would
be rewritten for no image, and the others left reading a name nothing declares.

A rename reaches every project that holds a file it rewrites: the projects of the file it
starts from, then every project holding a file their edits rewrite, until none is new. A
component linked into two images is in two projects where both are found for it, as
*Which project a file belongs to* below says - by their build records, or, where no record
claims it, by the search above it - and a variable it writes is then renamed in the readers of
both images, whichever of the two the file the rename starts from is in; so is a type, a
constant, a section, a raster or a unit that a file of both spells. Every project the rename
reaches is asked each refusal above before anything is written. Where a project the file it
starts from does not belong to already uses the name, declares the type an external one, or
holds a file that did not load, the refusal names that project's image, or its description
where no build record names it -
asked from one image, a name "already declared by this project" in the other sends the reader
looking in the wrong one; unsaved changes are refused naming the file that holds them,
wherever it is. A unit's rename is refused as well, naming both, where two projects it reaches
would rewrite a units file they share two ways: the one listing the unit renamed onto merges the
old spelling into it, and the other respells it.

An edit reaching two files or more, a rename's or a quick fix's, is sent marked
``needsConfirmation`` to a client that announced both ``documentChanges`` and
``changeAnnotationSupport``, so that the client shows it before applying and saving it. The reader
can then leave a file out of the edit, which applies it in part, by the reader's choice; a client
that announced only one of the two is sent the edit unmarked, and applies it at once.

**Quick fixes.** They change descriptions: the code of the components that read the variable is
not touched, and the title of each fix reconciling a ``definition-mismatch`` says so, as the one
a finding of ``ddd gui`` carries does. On a key the declarations of one object have to agree on -
a ``unit``, a ``conversion``, a ``datatype`` - a ``definition-mismatch`` offers every way of
reconciling it: take the producing component's value, spread this one to the others, or, when
nobody else states the key, remove it. ``limits`` are the exception to the last: a declaration
that leaves them out defers to the one that states them, which the checker counts as agreement,
so only two stated ranges that differ are offered a fix. A declaration naming a declared type is
an exception of its own: the type fixes its ``datatype``, ``unit``, ``conversion`` and
``limits``, which may not be stated beside the ``typename``, so none of them is offered to it,
and spreading one of them to the other declarations leaves it out. It states them all the same,
as the checker reads it: the producing component's value is the one its type states, where it
names one, and no key is offered for removal while a type one of the declarations names states
it, since that declaration would go on stating it and the removal would settle nothing. Neither
taking a value nor spreading one writes to a declaration that already means it, however
differently spelled: a conversion written over four lines and the same conversion written on one
are one value, as the checks have always counted them. The value is copied as source text rather
than re-serialised, so the project's formatting survives the fix. The fixes are listed by which
component owns the variable: a component that reads it is offered the producer's value first,
and the producer its own, sent out. The first is marked as the preferred fix, the one the
editor's automatic fix applies, only where it goes the owner's way: where that way is not
offered, none is marked, rather than the other way round, and none is where two components write
the variable, or none does, which leaves it no owner.

A fix is offered only where every file it writes still loads, as far as the declaration and the
type it names can say. Some rules hold between keys, and the models say them: an enumeration needs
an integer datatype, and a string a byte datatype, one dimension, no unit and no limits. Three
more are the analysis's, and need no more of the project to be asked: the limits a datatype and a
conversion derive have to stay finite, which a ``float64`` under a factor of two does not; a shape
written in numbers stays within the caps on its dimensions and elements; and a declaration naming
a string type states exactly one dimension and no display format, which only the type says. A fix
that would write a ``float32`` under an enumeration, a unit beside a string, or a ``float64``
under a factor of two, or take the one dimension out of a declaration naming a string type, would
leave a file the project refuses - a ``schema`` error, which no severity turns down, after which
the project is no longer analysed and every further fix is refused - so it is not offered. A fix
that reaches several declarations is offered for those that load. What needs more of the project
than the declaration and its type is not asked: the leaves of an array of structures, the
elements of a map over its axes, the constant a dimension names, a plugin's ``extensions``. A fix
may reach one of those, and the next analysis reports it - as it reports a range wider than the
datatype, which only loads.

A component linked into two images is in two projects, and a fix the two offer alike is offered
once. A fix sending this declaration's value out, or taking a key out of the others, reaches the
declarations of both images, and of every image holding a file it writes, until none is new, as a
rename does. Where two images offer one fix under one title with different edits - two values one
type states in two images, say - neither is offered; and every fix is withheld where one reaches
an image holding a file that did not load, or a description, beyond the document's own images,
that cannot be read.

A ``missing-id`` offers one fix of its own: give this object an identity. It writes the same
key ``ddd id --assign`` would write, in the same place - right after the declaration's ``name``
- and which declarations want one is decided by the same code: the command stamps a whole file,
the fix stamps the declaration you are looking at. It is offered only
where the finding is: a project that has silenced ``missing-id`` has said it is not adopting
ids yet, and the editor does not argue with that.

An ``unknown-unit`` finding, which only a project with a units file reports, offers two fixes
of its own: "Add 'RPM' to the vocabulary", and, for each spelling close enough to suggest,
"Rename 'RPM' to 'rpm' everywhere" - the same rename ``F2`` makes, merging into a unit that
exists. Both are the plans ``ddd gui`` previews and applies, made as text edits: for one project
the editor and the page do the same, but the page plans over the one project it is open on and
the editor's rename over every image it reaches, so across images the editor's reaches files the
page's does not; a plan that is refused is not offered. The rename is the one ``F2`` makes from
the unit, over every image it reaches, and is not offered where that rename is refused; the unit
is added only where every image planning it adds it to the same file, since an image holding both
files would list it twice.

Which project a file belongs to
-------------------------------

A description file cannot say which project it belongs to - in the collected CMake mode the
project description exists only in the build tree - so the server reads the
``ddd-build.json`` record that ``ddd_generate()`` writes at configure time (see
:doc:`build_integration`), and applies the severities the build applies. The search runs in
three stages:

* **Build records.** The directories named with ``-b`` are searched recursively for
  ``ddd-build.json``; unconfigured, the conventional directories ``build``, ``out`` and
  ``cmake-build-*`` under each workspace folder are. A relative ``-b`` path is read against
  each workspace folder, which is what makes a bare ``build`` mean the one beside the sources
  of each, a folder added later included, and against the directory the server was started in
  only while the editor names no folder. A file claimed by several builds is checked under
  each of them and the findings are published together - a component linked into two images is
  in two projects, and the answer to which one the reader cares about is both. Each record is
  counted under the path it resolves to, and once however many folders reach it, so a link
  inside a build tree does not turn one record into a record per way of spelling it.
  The records a search discovers are announced as log messages, and a record written by a
  newer DDD, that names a check this version of DDD has not got, or that names its project by
  a relative path, which a build never writes, is skipped and the reason announced with it -
  skipped in silence, a record nothing can use looks exactly like a workspace nobody ever
  configured a build in. A file that is not a build record at all is skipped without a word:
  a build wrote it, and nobody fixes it in an editor. A record whose
  severities name a *plugin's* check that no plugin of the project registers is reported as a
  ``plugin-invalid`` finding on the project file, which is what ``ddd check`` refuses the
  same ``-W`` for.
* **A containing project.** A file no build record claims is looked for in a containing
  project instead: the server walks from the file's directory up to the workspace folder
  holding it and checks the file under the project descriptions of the outermost directory
  that include it.
  A description nearer the file that includes it as well is a sub-project of the outer one
  and is dropped: it does not know what the rest of the outer project produces, so the file
  shows what ``ddd check`` of the outer project shows.
  A file that is itself a project description is searched for above like any file, and is
  checked as the project it is where no description above includes it: it lists its
  components, so every check has what it needs, and the checks that need the whole project
  are exactly the ones somebody opening a project file is asking about.
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

The workspace folders are those the editor names when it starts the server, and those it adds
and removes afterwards, which the server says it follows: a folder added is searched as one
named from the start, its build records found and the open documents checked again; a folder
removed is answered as if it had never been named - what was published under it alone is
withdrawn, and an open document under it is checked as one outside every folder.

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
``editors/vscode``. It is a launcher and deliberately nothing more - everything a reader sees
is the server's answer, so an editor DDD ships nothing for is not at a disadvantage. It starts
the server once a description file is open or the workspace holds one, so that a json file of
another name starts nothing, and it watches nothing itself: the server asks for the watcher it
needs, as it asks any other editor that announced it takes such a registration while the
session runs. It contributes two settings and one command:

.. list-table::
   :header-rows: 1
   :widths: 34 66

   * - setting
     - meaning
   * - ``ddd.executable``
     - the ``ddd`` command to run the server with. Left as the bare name it is looked up on
       the ``PATH``; set it to an absolute path to use the interpreter of a virtual
       environment. A change takes effect once the server is restarted.
   * - ``ddd.buildDirectories``
     - the directories handed to the server as ``-b``, each searched for a
       ``ddd-build.json``; a relative entry is read against each workspace folder. Left
       empty, the conventional build directory names in each workspace folder are searched.
       A change takes effect once the server is restarted.

The command is **DDD: Restart Language Server**, for picking up a newly installed tool, or a
change of the settings, without reloading the window.

Every release attaches a ``ddd-<version>.vsix`` to its `GitHub release
<https://github.com/Sauci/ddd/releases>`_, which is a permanent link needing no account and
no network policy exception. That installs with ``code --install-extension
ddd-<version>.vsix`` or through **Install from VSIX...** in the Extensions view, and updates
no more automatically than any other file, so reinstall it when the python package is
upgraded - the extension and the python package share a version number, and an update to one
is worth the other.
