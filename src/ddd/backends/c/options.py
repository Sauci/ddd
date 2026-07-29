"""Options of the c backend, and nothing else."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class COptions:
    """Everything the c backend lets a project decide.

    Short, because most of what used to be an option is now a property of the templates the
    project writes: what the generated files are called, what their include guards are and
    how a variable is commented are decided by naming and writing a template, not by a flag.
    """

    const_inputs: bool = False
    """Declare input objects ``const`` in the consumer headers.

    This makes a write access to a foreign variable a compile error. The variable is still
    *defined* without ``const`` in the global definition file, which strictly speaking is a
    constraint violation in c; every common embedded toolchain accepts it, but the option is
    therefore opt-in.

    Not left to the templates: it changes what the *analysis* hands them, not how it is
    spelled, and a template cannot make a declaration const without knowing the scope rules.
    """
