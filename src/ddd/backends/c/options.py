"""Options of the c backend, and nothing else."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class COptions:
    """Everything the c backend lets a project decide: nothing.

    What used to be an option is a property of the templates the project writes: what the
    generated files are called, what their include guards are and how a variable is commented
    are decided by naming and writing a template, not by a flag. The class stays so that a
    backend is built the way every other one is, and an option can be added to it.
    """
