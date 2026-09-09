"""What every backend is and what every backend gets.

A backend turns a :class:`~ddd.ir.DataDictionary` into files. It may know everything about
its own output format and nothing about the others: the c backend does not know that a2l
exists, the a2l backend does not know what a ``uint16_t`` is called. Adding a third output -
a header for another language, a csv, an ARXML - means adding a package next to them,
exporting it from :mod:`ddd.backends`, and adding it to the list ``_command_generate``
assembles in :mod:`ddd.cli`. Nothing else has to change.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol, runtime_checkable

from jinja2 import (
    Environment,
    FileSystemLoader,
    StrictUndefined,
    TemplateError,
    TemplateSyntaxError,
)

from ddd.ir import DataDictionary


@dataclass(frozen=True, slots=True)
class GeneratedFile:
    """One artefact, fully rendered but not yet written."""

    path: Path
    content: str


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


@dataclass(frozen=True, slots=True)
class WriteResult:
    path: Path
    status: WriteStatus


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
            previous = produced_by.get(path)
            if previous is not None:
                who = (
                    f"the {backend.name} backend would write '{path.name}' twice"
                    if previous == backend.name
                    else f"the {backend.name} and {previous} backends would both write "
                    f"'{path.name}'"
                )
                msg = f"{who}; rename the component or choose a different prefix"
                raise ValueError(msg)
            produced_by[path] = backend.name
            files.append(GeneratedFile(path, file.content))
    return files


def write(files: Iterable[GeneratedFile], *, dry_run: bool = False) -> list[WriteResult]:
    """Write every file that needs it, all of them or none, skipping those already current.

    Every file's status - unchanged, created or updated - is decided first, against the bytes
    already on disk, before anything is written: an unchanged file is left alone and keeps its
    mtime, which is what lets a build system that watches mtimes skip work a rerun did not
    actually change.

    What needs writing is then written twice over. First every one of them is rendered to a
    sibling ``<name>.tmp``, so that a mistake in the render itself, or a parent directory that
    cannot be created, is found while every real target is still exactly as it was. Only once
    every temporary file exists is each renamed onto its real target in turn, with
    :meth:`~pathlib.Path.replace`, which succeeds over an existing file on every platform this
    runs on. A target that is a directory - or any other permission problem, on either half -
    raises from wherever it happens, and the error that escapes always carries the real
    target's path in ``filename``, never the temporary's, because that is the path the caller
    typed and recognises.

    On that failure, every temporary file this call made is removed, and so is every target
    this call had already renamed into place if nothing existed there before it ran: undoing a
    fresh creation costs nothing, so a caller never sees only part of what a run would have
    produced. A target this call *updated*, though, is left with the new content once its
    rename has gone through - the bytes it held before are already gone, overwritten by that
    rename, and there is nothing left to put back. That window holds only renames, which is
    why it is small, and is accepted rather than solved by first moving every existing target
    aside on the chance that a later file fails.

    ``dry_run`` returns the decided statuses without writing anything, not even a temporary
    file - checked before any of them is created.
    """
    results: list[WriteResult] = []
    pending: list[tuple[GeneratedFile, bytes, WriteStatus]] = []
    for file in files:
        payload = file.content.encode("utf-8")
        existing = file.path.read_bytes() if file.path.is_file() else None
        if existing == payload:
            results.append(WriteResult(file.path, WriteStatus.UNCHANGED))
            continue
        status = WriteStatus.UPDATED if existing is not None else WriteStatus.CREATED
        results.append(WriteResult(file.path, status))
        pending.append((file, payload, status))
    if dry_run or not pending:
        return results

    temporaries: list[Path] = []
    renamed: list[tuple[Path, WriteStatus]] = []
    try:
        for file, payload, _ in pending:
            file.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = file.path.with_name(file.path.name + ".tmp")
            temporary.write_bytes(payload)
            temporaries.append(temporary)
        for (file, _, status), temporary in zip(pending, temporaries, strict=True):
            temporary.replace(file.path)
            renamed.append((file.path, status))
    except OSError as error:
        for temporary in temporaries:
            with contextlib.suppress(OSError):
                temporary.unlink()
        for target, status in renamed:
            if status is WriteStatus.CREATED:
                with contextlib.suppress(OSError):
                    target.unlink()
        error.filename = str(file.path)
        raise
    return results


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
    """
    if isinstance(error, TemplateSyntaxError):
        line: int | None = error.lineno
        reason = error.message or str(error)
    else:
        line = _template_line(error)
        reason = str(error)
    where = f"template '{template_name}'"
    if component is not None:
        where += f" for component '{component}'"
    if line is not None:
        where += f", line {line}"
    return f"cannot render {where}: {reason}"


def _template_line(error: Exception) -> int | None:
    """The template line a runtime error was raised from, read off the traceback.

    jinja marks the frames it fabricates with ``__jinja_exception__`` in their globals,
    whether it is fabricating them for one of its own exceptions or for a bare python one a
    template's body raised; the last one on the stack is the line of the template that
    actually failed. ``None`` when there is no such frame to read, in which case the message
    goes out without a line rather than not at all.
    """
    line: int | None = None
    trace = error.__traceback__
    while trace is not None:
        if trace.tb_frame.f_globals.get("__jinja_exception__") is not None:
            line = trace.tb_lineno
        trace = trace.tb_next
    return line
