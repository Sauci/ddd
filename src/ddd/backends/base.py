"""What every backend is and what every backend gets.

A backend turns a :class:`~ddd.ir.DataDictionary` into files. It may know everything about
its own output format and nothing about the others: the c backend does not know that a2l
exists, the a2l backend does not know what a ``uint16_t`` is called. Adding a third output -
a header for another language, a csv, an ARXML - means adding a package next to them and
listing it in :func:`ddd.backends.build_backends`, and touching nothing else.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol, runtime_checkable

from jinja2 import Environment, FileSystemLoader, StrictUndefined

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
                msg = (
                    f"the {backend.name} and {previous} backends would both write "
                    f"'{file.path.name}'; rename the component or choose a different prefix"
                )
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
    environment: Environment, template_name: str, path: Path, **context: object
) -> GeneratedFile:
    template = environment.get_template(template_name)
    content = template.render(**context)
    if not content.endswith("\n"):
        content += "\n"
    return GeneratedFile(path, content)
