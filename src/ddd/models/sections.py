"""Contract for the memory section vocabulary file.

A ``sections`` file declares the linker sections a project places its data in.  Placement is
a property of one object - one address, one section - so a definition names a section the
way it names a declared type: a reference to something declared once, not free text.  A
section carries the two properties the checks need: whether the running software can write
it, and the alignment it guarantees.

Whether a calibration tool can write a ``read-only`` section - an emulation overlay, a
calibratable flash - is the target's business and deliberately not modelled here: DDD cannot
tell a plain ROM from a calibratable one, and the object's ``volatile`` already states what
the software has to assume.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from ddd.models.common import SECTION_NAME_PATTERN, FileRoot


class SectionAccess(StrEnum):
    """What the running software may do with a section, which is all DDD can check."""

    READ_WRITE = "read-write"
    """The software reads and writes it: RAM, NVM."""

    READ_ONLY = "read-only"
    """The software only reads it: flash, ROM - calibratable or not, which is the target's
    secret."""


class SectionDeclaration(BaseModel):
    """One linker section, with the properties the checks need."""

    model_config = ConfigDict(frozen=True, extra="forbid", use_attribute_docstrings=True)

    section: Annotated[str, StringConstraints(min_length=1, pattern=SECTION_NAME_PATTERN)]
    """The name as the linker script spells it: ``.calib``, ``.nvm``.

    A linker name rather than a C identifier, so a leading dot is a normal spelling: letters,
    digits, ``.``, ``_`` and ``$``, and nothing that could end the string literal the generated
    c writes it into.
    """

    access: SectionAccess
    """``read-write`` or ``read-only``, from the running software's point of view."""

    alignment: int = Field(ge=1)
    """The alignment the section guarantees, in bytes; a power of two.

    What it is checked against: an object whose datatype needs stricter alignment than the
    section guarantees would be padded or faulting, and either is worth a finding.
    """

    description: str = ""
    """Free text saying what the section is for, e.g. ``calibration flash behind the
    emulation overlay``."""

    @property
    def writable(self) -> bool:
        """Whether the running software can write the section."""
        return self.access is SectionAccess.READ_WRITE

    @model_validator(mode="after")
    def _alignment_is_a_power_of_two(self) -> SectionDeclaration:
        if self.alignment & (self.alignment - 1):
            msg = f"alignment {self.alignment} is not a power of two"
            raise ValueError(msg)
        return self


class SectionsFile(FileRoot):
    """Root object of a ``*.ddd.json`` memory section description.

    ``sections`` is the top level key that makes this a sections file; DDD decides what a
    file is from that key alone.  The file is listed in the ``includes`` of a project like
    any other description.
    """

    model_config = ConfigDict(title="DDD memory sections")

    sections: Annotated[tuple[SectionDeclaration, ...], Field(min_length=1)]
    """The sections this project places data in; an empty list is no file at all."""
