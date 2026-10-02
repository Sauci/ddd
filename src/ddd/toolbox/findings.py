"""The findings ``ddd tool from-elf`` reports of its own, and where it shows them.

They are not checks of the project catalogue: ``ddd checks`` does not list them and ``-W``
does not take them, because they judge an image rather than a description. Each goes into the
run's bag with its severity stated, which is what keeps a severity policy off it, and the
documentation lists every one of them (``tests/test_documentation.py`` holds it to this
table).
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Final

from ddd.diagnostics import DiagnosticBag, Location, Severity, where
from ddd.elf import Declared, Image

FINDINGS: Final[dict[str, Severity]] = {
    "elf-symbol-missing": Severity.ERROR,
    "elf-symbol-ambiguous": Severity.ERROR,
    "elf-no-storage": Severity.ERROR,
    "elf-type-unsupported": Severity.ERROR,
    "elf-type-conflict": Severity.ERROR,
    "elf-init-unsupported": Severity.ERROR,
    "elf-init-dropped": Severity.WARNING,
    "elf-bitfield-gap": Severity.WARNING,
    "elf-alignment": Severity.WARNING,
    "elf-qualifier-dropped": Severity.WARNING,
    "elf-section": Severity.WARNING,
    "elf-name-synthesized": Severity.WARNING,
    "elf-types-omitted": Severity.WARNING,
    "elf-boolean-bitfield": Severity.INFO,
    "elf-not-inferred": Severity.INFO,
}


def place(image: Image, declared: Declared | None) -> Location:
    """Where a finding about something the image describes is shown: at its declaration in
    the C source, or at the image itself where DWARF names none.

    The declaration's path is the one the image recorded, so it is relative wherever the build
    mapped its prefix to a relative one; DDD cannot resolve it against a directory it does not
    know, and a finding that claimed an absolute path would name a file that is not there.
    """
    if declared is None:
        return where(image.path)
    return Location(Path(declared.path), line=declared.line)


def report(
    bag: DiagnosticBag,
    check: str,
    message: str,
    location: Location,
    notes: Iterable[tuple[str, Location | None]] = (),
) -> None:
    """Add one of this module's findings, with the severity :data:`FINDINGS` gives it."""
    bag.add(check, message, location, notes, severity=FINDINGS[check])
