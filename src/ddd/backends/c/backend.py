"""The c backend: renders the templates a project provides.

DDD does not decide what the generated c looks like. Which comment style, which include
guards, which banner, whether a variable is commented at all - that is a house style, it
differs between projects, and none of it follows from the data. So the templates come from
the project and DDD supplies only the resolved data they render.

The naming rules below are what lets a build system derive the set of generated files from
the template directory alone, without running the tool first:

* every ``*.jinja2`` file directly inside the template directory is rendered,
* the generated file is named like its template without the ``.jinja2`` extension, so
  ``ddd_globals.c.jinja2`` produces ``ddd_globals.c``,
* a template whose name starts with an underscore is a **helper**: it produces no file of
  its own and exists to be imported by the others,
* a template whose name contains ``{component}`` is rendered **once per component**, with
  the placeholder replaced by the component name - ``{component}.h.jinja2`` produces
  ``Controller.h``, ``SensorHub.h`` and so on.
"""

from __future__ import annotations

from pathlib import Path

from ddd.backends.base import GeneratedFile, make_environment, render_template
from ddd.backends.c.model import build_code_model
from ddd.backends.c.options import COptions
from ddd.ir import DataDictionary

TEMPLATE_SUFFIX = ".jinja2"

COMPONENT_PLACEHOLDER = "{component}"
"""Marks a template that is rendered once per component rather than once per project."""


def package_root() -> Path:
    """The ``ddd`` package directory, wherever it is installed.

    Named and tested rather than counted inline: this module sits two levels below it, and
    getting that arithmetic wrong is invisible in a source checkout, where the fallback below
    finds the templates anyway. See ``test_the_package_root_is_the_ddd_package``.
    """
    return Path(__file__).resolve().parents[2]


def example_template_directory() -> Path | None:
    """The example templates, inside the installed package or in a source checkout.

    A starting point to copy from, not a default: nothing falls back to it, and
    ``ddd templates-dir`` prints the path so that a project can take a copy.
    """
    root = package_root()
    candidates = (
        root / "templates",  # a wheel, where they are force-included as ddd/templates
        root.parents[1] / "examples" / "templates",  # a source checkout: <repo>/examples
    )
    return next(
        (path for path in candidates if path.is_dir() and any(path.glob(f"*{TEMPLATE_SUFFIX}"))),
        None,
    )


def is_rendered(name: str) -> bool:
    """Whether a template of the directory produces a file of its own."""
    return (
        name.endswith(TEMPLATE_SUFFIX)
        # Only the directory itself: what a project keeps in a subdirectory is its own
        # business, and stays importable without being rendered.
        and "/" not in name
        and not name.startswith("_")
    )


class CBackend:
    """Renders the c sources of a data dictionary from a project's templates."""

    name = "c"

    def __init__(
        self,
        template_dir: Path,
        options: COptions | None = None,
        generator: str = "ddd",
    ) -> None:
        self.template_dir = template_dir
        self.options = options or COptions()
        self.generator = generator

    def generate(self, dictionary: DataDictionary, output_dir: Path) -> list[GeneratedFile]:
        self._check_template_dir()
        environment = make_environment(self.template_dir)
        model = build_code_model(dictionary, self.options, self.generator)

        templates = sorted(environment.list_templates(filter_func=is_rendered))
        if not templates:
            msg = (
                f"no template to render in '{self.template_dir.as_posix()}': the c sources "
                f"are generated from templates the project provides, and a '{TEMPLATE_SUFFIX}' "
                f"file whose name starts with an underscore is a helper that renders nothing "
                f"on its own. 'ddd templates-dir' prints a set to copy from."
            )
            raise ValueError(msg)

        files: list[GeneratedFile] = []
        for template in templates:
            stem = template[: -len(TEMPLATE_SUFFIX)]
            if COMPONENT_PLACEHOLDER in stem:
                for header in model.headers:
                    filename = stem.replace(COMPONENT_PLACEHOLDER, header.name)
                    files.append(
                        render_template(
                            environment,
                            template,
                            output_dir / filename,
                            component=header.name,
                            filename=filename,
                            model=model,
                            header=header,
                        )
                    )
            else:
                files.append(
                    render_template(
                        environment,
                        template,
                        output_dir / stem,
                        filename=stem,
                        model=model,
                    )
                )
        return files

    def _check_template_dir(self) -> None:
        """Answer for the ``-t`` itself before answering for what is in it.

        jinja's loader treats a path that is not a directory as a directory holding nothing,
        so a misspelled ``-t``, and a ``-t`` naming one template rather than the directory it
        sits in, both came out as "no template to render in ..." - which sends the author
        looking through a directory for the file that is missing from it, when the directory
        is the mistake. Two sentences for two mistakes, each ending in the same advice,
        because the answer to all three is the same set of example templates.
        """
        spelling = self.template_dir.as_posix()
        if not self.template_dir.exists():
            msg = (
                f"no template directory at '{spelling}': -t/--template-dir names the "
                f"directory holding the jinja2 templates of the c sources. "
                f"'ddd templates-dir' prints a set to copy from."
            )
            raise ValueError(msg)
        if not self.template_dir.is_dir():
            msg = (
                f"'{spelling}' is not a directory: -t/--template-dir names the directory "
                f"holding the jinja2 templates of the c sources, not one of the templates. "
                f"'ddd templates-dir' prints a set to copy from."
            )
            raise ValueError(msg)
