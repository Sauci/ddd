"""The a2l backend: one ASAM MCD-2 MC description of the whole dictionary."""

from __future__ import annotations

from pathlib import Path

from ddd.backends.a2l.model import a2l_string, build_a2l_model
from ddd.backends.a2l.options import A2lOptions
from ddd.backends.base import GeneratedFile, make_environment, render_template
from ddd.ir import DataDictionary

TEMPLATE_DIR = Path(__file__).parent / "templates"


class A2lBackend:
    """Renders the a2l description of a data dictionary."""

    name = "a2l"

    def __init__(self, options: A2lOptions | None = None, generator: str = "ddd") -> None:
        self.options = options or A2lOptions()
        self.generator = generator

    def generate(self, dictionary: DataDictionary, output_dir: Path) -> list[GeneratedFile]:
        environment = make_environment(TEMPLATE_DIR)
        environment.filters["a2l"] = a2l_string
        filename = self.options.filename(dictionary.name)
        return [
            render_template(
                environment,
                "project.a2l.jinja",
                output_dir / filename,
                filename=filename,
                model=build_a2l_model(dictionary, self.options, self.generator),
            )
        ]
