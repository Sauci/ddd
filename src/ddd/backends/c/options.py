"""Options of the c backend, and nothing else."""

from __future__ import annotations

import re
from dataclasses import dataclass

PREFIX_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
"""What a prefix may look like: it becomes part of a file name and of an include guard."""


@dataclass(frozen=True, slots=True)
class COptions:
    """Everything the c backend lets a project decide."""

    prefix: str = "ddd"
    """Base name of the shared files and of the include guards."""

    def __post_init__(self) -> None:
        # The prefix ends up in a path, so anything with a separator or a '..' in it would
        # write outside the output directory the caller asked for; an empty one would
        # produce '_globals.c' and the guard '_H'.
        if not PREFIX_PATTERN.match(self.prefix):
            msg = (
                f"prefix '{self.prefix}' is not usable as a file name: it has to start with a "
                f"letter or an underscore and contain only letters, digits and underscores"
            )
            raise ValueError(msg)

    const_inputs: bool = False
    """Declare input objects ``const`` in the consumer headers.

    This makes a write access to a foreign variable a compile error. The variable is still
    *defined* without ``const`` in the global definition file, which strictly speaking is a
    constraint violation in c; every common embedded toolchain accepts it, but the option is
    therefore opt-in.
    """

    @property
    def types_header(self) -> str:
        return f"{self.prefix}_types.h"

    @property
    def globals_header(self) -> str:
        return f"{self.prefix}_globals.h"

    @property
    def globals_source(self) -> str:
        return f"{self.prefix}_globals.c"

    def component_header(self, component: str) -> str:
        return f"{component}.h"
