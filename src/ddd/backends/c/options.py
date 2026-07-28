"""Options of the c backend, and nothing else."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class COptions:
    """Everything the c backend lets a project decide."""

    prefix: str = "ddd"
    """Base name of the shared files and of the include guards."""

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
