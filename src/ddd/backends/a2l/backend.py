"""The a2l backend: one ASAM MCD-2 MC description of the whole dictionary."""

from __future__ import annotations

from pathlib import Path
from typing import Final

from ddd.backends.a2l.model import a2l_string, build_a2l_model
from ddd.backends.a2l.options import A2lOptions
from ddd.backends.base import GeneratedFile, make_environment, render_template
from ddd.ir import DataDictionary

TEMPLATE_DIR = Path(__file__).parent / "templates"

BYTE_ORDER_MARK: Final = "﻿"
"""What the a2l opens with, and the only encoding declaration the format has.

ASAP2 1.6.1 section 1.5 gives a reader one rule: take the encoding from a byte order mark at
the head of the file, and fall back to ISO-8859-1 where there is none. The version after it
adds an ``ENCODING`` keyword; 1.6.1, which is the version this file states, has nothing else.
So a tool handed the utf-8 DDD writes reads it as ISO-8859-1 unless the mark is there, and
``"°C"`` - the most ordinary non-ASCII unit there is - arrives as ``"Â°C"`` or stops the parse.

The mark belongs to this backend rather than to :func:`~ddd.backends.base.write`, which writes
utf-8 with no mark and lf for every artefact: the c sources and the dumped dictionary are read
by a compiler and by json, and both of those already know their encoding. Only the a2l has to
carry it in the bytes.
"""


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
        rendered = render_template(
            environment,
            "project.a2l.jinja",
            output_dir / filename,
            filename=filename,
            model=build_a2l_model(dictionary, self.options, self.generator),
        )
        # Added here rather than at the head of the template, where it would be an invisible
        # character in a file an author edits and a decoder could drop on the way in.
        return [GeneratedFile(rendered.path, BYTE_ORDER_MARK + rendered.content)]
