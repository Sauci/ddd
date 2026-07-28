"""The c backend: the definition file, the shared headers and one header per component."""

from __future__ import annotations

from pathlib import Path

from ddd.backends.base import GeneratedFile, make_environment, render_template
from ddd.backends.c.model import build_code_model
from ddd.backends.c.options import COptions
from ddd.ir import DataDictionary

TEMPLATE_DIR = Path(__file__).parent / "templates"


class CBackend:
    """Renders the c sources of a data dictionary."""

    name = "c"

    def __init__(self, options: COptions | None = None, generator: str = "ddd") -> None:
        self.options = options or COptions()
        self.generator = generator

    def generate(self, dictionary: DataDictionary, output_dir: Path) -> list[GeneratedFile]:
        environment = make_environment(TEMPLATE_DIR)
        options = self.options
        model = build_code_model(dictionary, options, self.generator)

        files = [
            render_template(
                environment,
                template,
                output_dir / filename,
                filename=filename,
                model=model,
            )
            for template, filename in (
                ("types.h.jinja", options.types_header),
                ("globals.h.jinja", options.globals_header),
                ("globals.c.jinja", options.globals_source),
            )
        ]
        files.extend(
            render_template(
                environment,
                "component.h.jinja",
                output_dir / header.filename,
                filename=header.filename,
                model=model,
                header=header,
            )
            for header in model.headers
        )
        return files
