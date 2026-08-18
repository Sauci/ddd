"""What every backend is and what every backend gets.

A backend turns a :class:`~ddd.ir.DataDictionary` into files. It may know everything about
its own output format and nothing about the others: the c backend does not know that a2l
exists, the a2l backend does not know what a ``uint16_t`` is called. Adding a third output -
a header for another language, a csv, an ARXML - means adding a package next to them,
exporting it from :mod:`ddd.backends`, and adding it to the list ``_command_generate``
assembles in :mod:`ddd.cli`. Nothing else has to change.
"""

from __future__ import annotations

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
    """Run every backend and refuse two artefacts claiming the same path."""
    files: list[GeneratedFile] = []
    produced_by: dict[Path, str] = {}
    for backend in backends:
        for file in backend.generate(dictionary, output_dir):
            previous = produced_by.get(file.path)
            if previous is not None:
                who = (
                    f"the {backend.name} backend would write '{file.path.name}' twice"
                    if previous == backend.name
                    else f"the {backend.name} and {previous} backends would both write "
                    f"'{file.path.name}'"
                )
                msg = f"{who}; rename the component or choose a different prefix"
                raise ValueError(msg)
            produced_by[file.path] = backend.name
            files.append(file)
    return files


def write(files: Iterable[GeneratedFile], *, dry_run: bool = False) -> list[WriteResult]:
    """Write the rendered files, skipping those that are already up to date."""
    results: list[WriteResult] = []
    for file in files:
        payload = file.content.encode("utf-8")
        existing = file.path.read_bytes() if file.path.is_file() else None
        if existing == payload:
            results.append(WriteResult(file.path, WriteStatus.UNCHANGED))
            continue
        status = WriteStatus.UPDATED if existing is not None else WriteStatus.CREATED
        if not dry_run:
            file.path.parent.mkdir(parents=True, exist_ok=True)
            file.path.write_bytes(payload)
        results.append(WriteResult(file.path, status))
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
    """Render one template, turning what jinja says into something an author can act on.

    The templates are the project's own files, so a typo in one is a usage mistake and not a
    defect of the tool: it is reported as one line naming the template rather than escaping
    as a python traceback through a library the author never imported. ``component`` names
    the component a per-component template is being rendered for, so a failure that only
    one component's data provokes says which one.
    """
    try:
        template = environment.get_template(template_name)
        content = template.render(**context)
    except TemplateError as error:
        raise ValueError(
            describe_template_error(template_name, error, component=component)
        ) from None
    if not content.endswith("\n"):
        content += "\n"
    return GeneratedFile(path, content)


def describe_template_error(
    template_name: str, error: TemplateError, *, component: str | None = None
) -> str:
    """One line: the template, the line in it, and what jinja had to say.

    A syntax error knows its own line. A runtime error - an undefined name under
    ``StrictUndefined``, most of the time - does not, but jinja rewrites its traceback with a
    frame per template line it passed through, and the deepest of those is where it happened.
    A ``{component}`` template is rendered once per component, with data that differs per
    run, so the message carries the component the failing render was for.
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


def _template_line(error: TemplateError) -> int | None:
    """The template line a runtime error was raised from, read off the traceback.

    jinja marks the frames it fabricates with ``__jinja_exception__`` in their globals; the
    last one on the stack is the line of the template that actually failed. ``None`` when
    there is no such frame to read, in which case the message goes out without a line rather
    than not at all.
    """
    line: int | None = None
    trace = error.__traceback__
    while trace is not None:
        if trace.tb_frame.f_globals.get("__jinja_exception__") is not None:
            line = trace.tb_lineno
        trace = trace.tb_next
    return line
