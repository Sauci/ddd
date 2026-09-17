"""What every backend is and what every backend gets.

A backend turns a :class:`~ddd.ir.DataDictionary` into files. It may know everything about
its own output format and nothing about the others: the c backend does not know that a2l
exists, the a2l backend does not know what a ``uint16_t`` is called. Adding a third output -
a header for another language, a csv, an ARXML - means adding a package next to them,
exporting it from :mod:`ddd.backends`, registering the artefact in :mod:`ddd.cli` and naming
it in the suites that enumerate the artefacts; "Adding an output format" in the developer
documentation lists the steps. Neither existing backend is touched by any of them.
"""

from __future__ import annotations

import contextlib
import errno
import json
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Any, Final, Protocol, runtime_checkable

from jinja2 import (
    Environment,
    FileSystemLoader,
    StrictUndefined,
    TemplateError,
    TemplateSyntaxError,
)

from ddd.ir import DataDictionary

STAGING_SUFFIX: Final = ".ddd-staging"
"""What :func:`write` appends to a target's name to stage that target's bytes beside it.

A staging file is overwritten and deleted without asking, so the name has to be one no
artefact would ever carry: ``.tmp`` is a name people give real files, and a project keeping a
hand-written ``ddd_globals.c.tmp`` beside the generated ``ddd_globals.c`` - or a backend
emitting an ``x.h.tmp`` of its own beside ``x.h`` - would have watched a plain run overwrite
it and then delete it. This spelling nobody else picks is what makes the reservation logic
that would otherwise be needed unnecessary; a leftover of a crashed earlier run still carries
it, and overwriting that one is right, because it is ours by construction."""


MANIFEST_NAME: Final = ".ddd-manifest.json"
"""What :func:`write` records a run's own files in, inside the directory it writes them to.

One file per output directory rather than one per project, because what it answers is a
question about the directory: which of the files in it did DDD write, and for which artefact.
The name is out of the way of everything a project compiles - a leading dot keeps it out of
the ``*.c`` and ``*.h`` globs a build collects sources with, and no template renders to a
name starting with one - and the extension says what a reader opening it will find."""

MANIFEST_FORMAT: Final = 1
"""The shape of the manifest document; a reader declines one it does not know.

A manifest is read to decide what to *delete*, so misreading a future version of it would
delete the wrong files. An unknown format therefore removes nothing and is overwritten with
this one, which costs one run's worth of leftovers and no file anybody wanted."""


@dataclass(frozen=True, slots=True)
class GeneratedFile:
    """One artefact, fully rendered but not yet written.

    ``artefact`` names what produced it - ``c``, ``a2l``, a plugin's name, or
    :data:`DICTIONARY_ARTEFACT` - which is what :class:`Manifest` records beside the path so
    that a later run removes only the files of the artefacts it produced itself. A backend
    does not fill it in: :func:`render` stamps every file with the name of the backend it
    came from, which is the one place that knows.
    """

    path: Path
    content: str
    artefact: str = ""


@runtime_checkable
class Backend(Protocol):
    """Turns a data dictionary into files."""

    name: str

    def generate(self, dictionary: DataDictionary, output_dir: Path) -> list[GeneratedFile]:
        """Render every artefact of this backend; nothing is written to disk."""
        ...


class WriteStatus(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    UNCHANGED = "unchanged"
    REMOVED = "removed"


@dataclass(frozen=True, slots=True)
class WriteResult:
    path: Path
    status: WriteStatus


class RemovalError(OSError):
    """A file an earlier run wrote could not be removed; ``filename`` names it.

    Its own class because the sentence a caller prints for it is not the one it prints for a
    write: "cannot write" about a file this run was deleting reads as the opposite of what
    happened, and the advice a failed write carries - the path is too long - is advice about
    a path that does not exist yet, which this one certainly does.
    """


DICTIONARY_ARTEFACT: Final = "--dictionary"
"""The artefact name of the dictionary a ``generate`` run is asked to write beside the others.

Spelled as the option that asks for it, because a plugin's artefact is asked for by the
plugin's name and a plugin name is a lowercase identifier: no plugin can ever be called this,
so the dictionary's entries in the manifest cannot be taken for a plugin's."""


@dataclass(frozen=True, slots=True)
class Manifest:
    """The output directory a ``generate`` run owns, and the artefacts it produced into it.

    ``ddd generate`` writes what it renders; what it renders follows from the descriptions,
    so a component dropped from a project - or renamed, or compiled out - simply stops being
    rendered, and used to leave its header behind. On the include path of every component, in
    a directory a build system cannot clean either, because the per-component file names are
    exactly the ones it cannot know at configure time. So a run records the files it wrote
    here, and the next one removes those it no longer writes.

    Two rules bound that. **Only what this tool wrote is ever removed**: a file the manifest
    does not name - a hand-written header beside the artefacts, an object file, a note - is
    not ours, and is left alone however stale it looks. And **only the artefacts this run
    produced** are weighed: ``ddd generate a2l`` into the directory a ``generate all`` filled
    regenerates the A2L "without touching the sources the image was built from"
    (``SPEC.md`` section 6), so the c entries of the manifest are carried over untouched
    rather than read as files that have gone away. The same holds for ``--without c``, for
    ``NO_A2L``, and for a plugin a project stopped naming.
    """

    directory: Path
    artefacts: Iterable[str]

    def __post_init__(self) -> None:
        # Resolved once, here: the paths a run writes are resolved (:func:`render` resolves
        # the output directory before any backend sees it), and a relative spelling of the
        # same directory would make every one of them look like a file outside it.
        object.__setattr__(self, "directory", self.directory.resolve())
        object.__setattr__(self, "artefacts", frozenset(self.artefacts))

    @property
    def path(self) -> Path:
        return self.directory / MANIFEST_NAME

    def previous(self) -> dict[str, str]:
        """What the last run recorded: relative POSIX path to the artefact that wrote it.

        Empty for a directory no run has owned yet - the first run after an upgrade removes
        nothing and records what it wrote - and empty for a document this version cannot
        read, for the reason :data:`MANIFEST_FORMAT` gives.
        """
        try:
            document: Any = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        if not isinstance(document, dict) or document.get("format") != MANIFEST_FORMAT:
            return {}
        files = document.get("files")
        if not isinstance(files, dict) or not all(
            isinstance(artefact, str) for artefact in files.values()
        ):
            return {}
        return dict(files)

    def stale(self, previous: dict[str, str], written: set[Path]) -> list[Path]:
        """The recorded files this run no longer writes, in the order they will be removed."""
        found: list[Path] = []
        for name, artefact in sorted(previous.items()):
            if artefact not in self.artefacts:
                continue
            path = (self.directory / name).resolve()
            # A name that climbs out of the directory, or an absolute one, comes from a hand
            # edit of the record rather than from a run: the directory is what this owns.
            if not path.is_relative_to(self.directory) or path in written or not path.is_file():
                continue
            found.append(path)
        return found

    def record(self, previous: dict[str, str], files: Iterable[GeneratedFile]) -> str:
        """The document to write: what this run wrote, and what earlier runs wrote of the
        artefacts this one did not produce."""
        entries = {
            name: artefact for name, artefact in previous.items() if artefact not in self.artefacts
        }
        for file in files:
            # Resolved rather than taken as written: a backend's paths already are, but the
            # dictionary's is the one the caller typed, and a relative spelling of a file
            # inside this directory is one this run wrote here like any other.
            path = file.path.resolve()
            if path.is_relative_to(self.directory):
                entries[path.relative_to(self.directory).as_posix()] = file.artefact
        document = {"format": MANIFEST_FORMAT, "files": dict(sorted(entries.items()))}
        return json.dumps(document, indent=2) + "\n"


def render(
    dictionary: DataDictionary, backends: Iterable[Backend], output_dir: Path
) -> list[GeneratedFile]:
    """Run every backend, keep every file inside ``output_dir``, and refuse two that clash.

    ``output_dir`` is resolved once, here, before any backend runs - not resolved again later
    against each path a backend hands back. The guarantee this function makes is only
    checkable against a single fixed root, and a backend echoes the directory it was handed
    straight back into the paths it builds - every built-in backend, and the worked example,
    do exactly this - so the root a backend echoes and the root its files are measured against
    have to be the same resolved directory. Resolved only after the backends have already run,
    a bare relative climb a plugin computes from ``output_dir`` - ``output_dir.parent``, say -
    would still be relative when it left the backend and could resolve to somewhere that looks
    anchored under ``output_dir`` by the time it is checked, even though it never was. Resolved
    first, a path a backend hands back is either already absolute - built from the resolved
    directory, or an escape stated outright - or bare, in which case it can only mean
    ``output_dir / name`` and never wherever the process happens to be running from. Either
    way, ``sub/../ddd_globals.h`` is the same claim as ``ddd_globals.h`` and not a second one,
    and a spelling that resolves outside ``output_dir`` - a climb through enough ``..``, or an
    absolute path elsewhere entirely - is refused before it, or whatever it would have
    collided with, reaches disk.
    """
    output_dir = output_dir.resolve()
    files: list[GeneratedFile] = []
    produced_by: dict[Path, str] = {}
    for backend in backends:
        for file in backend.generate(dictionary, output_dir):
            path = (file.path if file.path.is_absolute() else output_dir / file.path).resolve()
            if not path.is_relative_to(output_dir):
                msg = (
                    f"backend '{backend.name}' writes outside the output directory: "
                    f"{path.as_posix()}"
                )
                raise ValueError(msg)
            if path == output_dir / MANIFEST_NAME:
                # The record of what this run owns cannot also be one of the files it owns:
                # written over by a backend it would name whatever that backend rendered, and
                # the next run would delete the directory's real contents for want of them.
                msg = (
                    f"backend '{backend.name}' would write '{MANIFEST_NAME}', which is the "
                    f"record ddd keeps of the files it wrote here; rename the template"
                )
                raise ValueError(msg)
            previous = produced_by.get(path)
            if previous is not None:
                who = (
                    f"the {backend.name} backend would write '{path.name}' twice"
                    if previous == backend.name
                    else f"the {backend.name} and {previous} backends would both write "
                    f"'{path.name}'"
                )
                msg = f"{who}; rename the component or the template"
                raise ValueError(msg)
            produced_by[path] = backend.name
            files.append(GeneratedFile(path, file.content, backend.name))
    return files


def write(
    files: Iterable[GeneratedFile], *, dry_run: bool = False, manifest: Manifest | None = None
) -> list[WriteResult]:
    """Write every file that needs it, all of them or none, skipping those already current.

    Every file's status - unchanged, created or updated - is decided first, against the bytes
    already on disk, before anything is written: an unchanged file is left alone and keeps its
    mtime, which is what lets a build system that watches mtimes skip work a rerun did not
    actually change.

    What needs writing is then written twice over. By the time this function runs every payload
    is already a rendered ``str`` - :func:`render_template` produced it, and the decide loop
    above already encoded it to bytes - so staging cannot catch a mistake in the render itself;
    that would already have raised before ``write`` was ever called. What staging buys instead:
    each payload is first written to a sibling ``<name>.ddd-staging`` - a fixed name
    (:data:`STAGING_SUFFIX` says why it is that one and not ``.tmp``), so it overwrites any
    stale staging file an earlier run left behind, and two concurrent runs into the same
    directory race on it exactly as they always raced on the real targets - and only once every
    temporary exists does the function start renaming them onto their real targets in turn.
    A filesystem failure on file *N* - no space left, a parent directory that cannot be created,
    a target that cannot be replaced - therefore happens while file 1's target is still
    untouched, so the run fails before it has committed to anything rather than partway through
    it, and what staging leaves behind is a sequence of renames rather than a sequence of writes.

    The rename itself is :meth:`~pathlib.Path.replace` (``os.replace`` underneath), which trades
    a silent partial write for a clean all-or-nothing failure - and the trade has a cost on at
    least one platform this runs on. On Windows, replacing a target that another handle holds
    open with default sharing raises ``PermissionError``, in a case where ``write_bytes`` writing
    straight onto that same target would have gone through; and where the target is one name of a
    hard link, replace detaches this name from the shared file and points it at the temporary's
    data instead, so the other name keeps the old bytes rather than seeing the update - again
    unlike ``write_bytes``, which writes through the shared file and so updates every name linked
    to it. A target that is a directory - or any other permission problem, on either half -
    raises from wherever it happens, and the error that escapes always carries the real target's
    path in ``filename``, never the temporary's, because that is the path the caller typed and
    recognises.

    On that failure, every temporary file this call made is removed, and so is every target
    this call had already renamed into place if nothing existed there before it ran: undoing a
    fresh creation costs nothing, so a caller never sees only part of what a run would have
    produced. A target this call *updated*, though, is left with the new content once its
    rename has gone through - the bytes it held before are already gone, overwritten by that
    rename, and there is nothing left to put back. That window holds only renames, which is
    why it is small, and is accepted rather than solved by first moving every existing target
    aside on the chance that a later file fails.

    ``manifest`` hands ``write`` the output directory the run owns (:class:`Manifest`). The
    record of what this run wrote is then staged with the artefacts and renamed **after** them
    and after the files it says are no longer generated have been removed, which is what makes
    the ownership survive every way a run can fail: a run that could not write leaves the
    previous record describing what is still there, and a file that could not be removed stays
    named in it, so the next run tries again instead of losing sight of it. The record is not
    a result: what a run reports is what it generated, and this is the bookkeeping underneath.

    ``dry_run`` returns the decided statuses - the removals included, so that a dry run says
    what a real one would delete - without writing or removing anything, not even a temporary
    file, checked before any of them is created.
    """
    rendered = list(files)
    results: list[WriteResult] = []
    pending: list[tuple[GeneratedFile, bytes, WriteStatus]] = []
    for file in rendered:
        payload = file.content.encode("utf-8")
        existing = file.path.read_bytes() if file.path.is_file() else None
        if existing == payload:
            results.append(WriteResult(file.path, WriteStatus.UNCHANGED))
            continue
        status = WriteStatus.UPDATED if existing is not None else WriteStatus.CREATED
        results.append(WriteResult(file.path, status))
        pending.append((file, payload, status))

    stale: list[Path] = []
    record: list[tuple[Path, bytes]] = []
    if manifest is not None:
        previous = manifest.previous()
        stale = manifest.stale(previous, {file.path.resolve() for file in rendered})
        results.extend(WriteResult(path, WriteStatus.REMOVED) for path in stale)
        document = manifest.record(previous, rendered).encode("utf-8")
        current = manifest.path.read_bytes() if manifest.path.is_file() else None
        if current != document:
            record.append((manifest.path, document))
    if dry_run or not (pending or record):
        return results

    temporaries: list[Path] = []
    staged_record: list[Path] = []
    renamed: list[tuple[Path, WriteStatus]] = []
    try:
        for file, payload, _ in pending:
            target = file.path
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(target.name + STAGING_SUFFIX)
            # Recorded before writing, not after: a write that fails once the file already
            # exists on disk - a full disk partway through, an I/O error - must still be found
            # and removed below. The unlink there is already wrapped in
            # contextlib.suppress(OSError), so recording a temporary that, in some other
            # failure, was never created costs nothing.
            temporaries.append(temporary)
            temporary.write_bytes(payload)
        for target, payload in record:
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(target.name + STAGING_SUFFIX)
            staged_record.append(temporary)
            temporary.write_bytes(payload)
        for (file, _, status), temporary in zip(pending, temporaries, strict=True):
            target = file.path
            temporary.replace(target)
            renamed.append((target, status))
        for target in stale:
            try:
                target.unlink()
            except OSError as error:
                raise RemovalError(error.errno, error.strerror, str(target)) from None
        for (target, _), temporary in zip(record, staged_record, strict=True):
            temporary.replace(target)
    except OSError as error:
        for temporary in (*temporaries, *staged_record):
            with contextlib.suppress(OSError):
                temporary.unlink()
        for already_renamed, status in renamed:
            if status is WriteStatus.CREATED:
                with contextlib.suppress(OSError):
                    already_renamed.unlink()
        # `target` is bound fresh at the top of each loop iteration above, rather than read
        # off whichever `for` last left `file` bound, so a line later added to either loop -
        # or between them - cannot silently misname the file here.
        error.filename = str(target)
        # A failed `Path.replace` leaves `filename2` set to this same target (`filename` was
        # the temporary, now overwritten above); left alone, `str(error)` would read
        # 'target' -> 'target'. `= None` is not enough - the attribute would still print as
        # ' -> None' - so it is removed outright.
        del error.filename2
        raise
    return results


def describe_write_failure(error: OSError, shown: str) -> str:
    """One line for a write that failed: the file, and what was really refused.

    ``strerror`` is the whole of what an errno carries, and for one ordinary mistake it says
    the opposite of what happened. A path longer than the platform accepts comes back from
    Windows as ``ENOENT`` - "No such file or directory" - about a file that was never
    supposed to exist yet, and the reader goes looking for a directory that is sitting right
    there. :func:`write` creates that directory itself, immediately before writing into it,
    so a missing element of the path is not a thing that happens here: the directory being
    there is the evidence that the path itself is what was refused, and its length is the
    thing to look at. Said beside the errno rather than instead of it, because the errno is
    what the platform answered and the sentence after it is a reading of it.

    ``shown`` is the path the way the caller typed it, which is not always ``error.filename``
    - a generated file is reported relative to the ``-o`` that was given - so both are used:
    the spelling to print, and the real path to weigh.
    """
    detail = error.strerror or str(error)
    if error.errno == errno.ENOENT and error.filename is not None:
        written = Path(error.filename)
        if written.parent.is_dir():
            detail += (
                f" - the directory it goes in exists, so it is the path itself that was "
                f"refused: {len(str(written))} characters, and "
                f"{len(str(written)) + len(STAGING_SUFFIX)} while it is staged beside its "
                f"target"
            )
    return f"cannot write '{shown}': {detail}"


def make_environment(template_dir: Path) -> Environment:
    """A jinja environment configured the way generated source files want it."""
    return Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
        undefined=StrictUndefined,
    )


def render_template(
    environment: Environment,
    template_name: str,
    path: Path,
    *,
    component: str | None = None,
    **context: object,
) -> GeneratedFile:
    """Render one template, turning what it raises into something an author can act on.

    The templates are the project's own files, so a mistake in one is a usage mistake and not
    a defect of the tool: it is reported as one line naming the template rather than escaping
    as a python traceback through a library the author never imported. Jinja does not wrap
    every such mistake as a ``TemplateError`` - ``{{ 1 / 0 }}`` raises a bare
    ``ZeroDivisionError``, a filter handed the wrong type a bare ``TypeError`` - so both kinds
    are caught here and described alike: jinja rewrites the traceback of either the same way,
    so :func:`describe_template_error` finds the failing line regardless of which it is.
    ``component`` names the component a per-component template is being rendered for, so a
    failure that only one component's data provokes says which one.
    """
    try:
        template = environment.get_template(template_name)
        content = template.render(**context)
    except TemplateError as error:
        raise ValueError(
            describe_template_error(template_name, error, component=component)
        ) from None
    except Exception as error:
        # Not a TemplateError, but no less the template author's mistake than one is: raised
        # from inside the template's own body, over data this run supplied, not from ddd's own
        # code. Left uncaught here it would print as a python traceback through jinja - a
        # library the author never imported - rather than the one line every other template
        # mistake is reported as.
        raise ValueError(
            describe_template_error(template_name, error, component=component)
        ) from None
    if not content.endswith("\n"):
        content += "\n"
    return GeneratedFile(path, content)


def describe_template_error(
    template_name: str, error: Exception, *, component: str | None = None
) -> str:
    """One line: the template, the line in it, and what went wrong.

    A syntax error knows its own line. A runtime error - an undefined name under
    ``StrictUndefined``, or a bare python exception a template's own body raised - does not,
    but jinja rewrites its traceback with a frame per template line it passed through, and the
    deepest of those is where it happened. A ``{component}`` template is rendered once per
    component, with data that differs per run, so the message carries the component the
    failing render was for.

    A line belongs to the file the failing frame came from, which is not always the template
    being rendered: a macro imported from a helper fails on the helper's line, and a helper
    that does not parse is reported while the template that imports it is being loaded. Named
    under the rendered template alone, such a line points at whatever that file happens to
    carry there - usually nothing at all - so the file is named beside the line whenever the
    two differ, and left unsaid when they do not.
    """
    if isinstance(error, TemplateSyntaxError):
        line: int | None = error.lineno
        source = error.name
        reason = error.message or str(error)
    else:
        line, source = _template_frame(error)
        reason = str(error)
    where = f"template '{template_name}'"
    if component is not None:
        where += f" for component '{component}'"
    if line is not None:
        where += f", line {line}"
        if source is not None and _file_name(source) != _file_name(template_name):
            where += f" of '{_file_name(source)}'"
    return f"cannot render {where}: {reason}"


def _file_name(spelling: str) -> str:
    """The last segment of a template name or of the path jinja compiled it from.

    A template is named to jinja with ``/`` whatever the platform is, and jinja names the code
    it compiles by the path the loader read it from, so the two spellings of one file never
    match as written. Comparing and printing the last segment is what makes them comparable;
    a template directory holding two files of the same name in different subdirectories is
    the one arrangement this cannot tell apart, and it reports the name they share.
    """
    return PurePosixPath(spelling.replace("\\", "/")).name


def _template_frame(error: Exception) -> tuple[int | None, str | None]:
    """The template line a runtime error was raised from, and the file it is a line of.

    jinja marks the frames it fabricates with ``__jinja_exception__`` in their globals,
    whether it is fabricating them for one of its own exceptions or for a bare python one a
    template's body raised; the last one on the stack is the line of the template that
    actually failed, and the code object it belongs to carries that template's own path.
    ``None`` when there is no such frame to read, in which case the message goes out without
    a line rather than not at all.
    """
    line: int | None = None
    source: str | None = None
    trace = error.__traceback__
    while trace is not None:
        if trace.tb_frame.f_globals.get("__jinja_exception__") is not None:
            line = trace.tb_lineno
            source = trace.tb_frame.f_code.co_filename
        trace = trace.tb_next
    return line, source
