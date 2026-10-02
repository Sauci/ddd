"""``ddd tool from-elf``: the DDD declarations of the C variables a linked ELF image describes.

Section 7.3 of ``SPEC.md`` states the rules, and the design they came from is
``docs/superpowers/specs/2026-09-30-toolbox-from-elf-design.md``. :func:`describe` selects the
variables (:mod:`~ddd.toolbox.selection`), maps their types (:mod:`~ddd.toolbox.mapping`),
reads their initial values (:mod:`~ddd.toolbox.values`) and has DDD check the result
(:mod:`~ddd.toolbox.checked`).
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final

from ddd.diagnostics import DiagnosticBag, Location, where
from ddd.elf import Image, Variable
from ddd.toolbox.checked import Candidate, checked, component_file
from ddd.toolbox.findings import place, report
from ddd.toolbox.mapping import Mapper, Typed
from ddd.toolbox.selection import select, wanted
from ddd.toolbox.values import UnstatableValueError, initial_value

DEFAULT_SECTIONS: Final = frozenset(
    {
        ".data",
        ".bss",
        ".rodata",
        ".sdata",
        ".sbss",
        ".sdata2",
        ".sbss2",
        ".srodata",
        ".data1",
        ".rodata1",
    }
)
"""The sections a toolchain places a variable in by default: a variable in one states no
``section``, and is placed by the defaults as it was."""

PRODUCER_SCOPES: Final = frozenset({"output", "local"})
CHECKED_COMPONENT: Final = "FromElf"
"""The name the list output's entries are checked under; it never reaches the output."""

NOT_INFERRED: Final = (
    "an image states no unit, description, limits, scaling or id, so the output states none: "
    "every conversion but an enum's is the identity, the limits are the ones DDD derives, and "
    "'ddd id --assign' writes the ids"
)
VALUE_BLOCKS: Final = (
    "; and a const array is a value block, since nothing in an image tells a curve, a map or "
    "an axis from any other array"
)


@dataclass(frozen=True, slots=True)
class Description:
    """What ``from-elf`` prints: the interface entries, and the types they name."""

    interface: tuple[dict[str, Any], ...]
    types: tuple[dict[str, Any], ...]


def describe(
    image: Image,
    arguments: Sequence[str],
    *,
    scope: str,
    component: str | None,
    bag: DiagnosticBag,
) -> Description:
    """The declarations of the variables ``arguments`` name, every finding reported into
    ``bag``; a malformed argument raises ``ValueError`` before anything is read."""
    wanted_ = [wanted(text) for text in arguments]
    chosen = select(image, wanted_, bag)
    mapper = Mapper(image, bag)
    producer = scope in PRODUCER_SCOPES
    candidates: list[Candidate] = []
    for variable in chosen:
        typed = mapper.typed(variable)
        if typed is None:
            continue
        definition = _definition(image, variable, typed, producer=producer, bag=bag)
        if definition is not None:
            candidates.append(Candidate(variable, definition, typed.reaches))
    candidates = _without_conflicts(candidates, mapper, image, bag)
    kept = checked(
        candidates,
        mapper.types,
        image=image,
        scope=scope,
        component=component or CHECKED_COMPONENT,
        bag=bag,
    )
    _report_sections(kept, image, bag)
    _report_run(kept, image, bag, component=component)
    interface = tuple({"scope": scope, "definition": c.definition} for c in kept)
    reached: set[str] = set().union(*(candidate.reaches for candidate in kept))
    return Description(interface, tuple(mapper.types(reached)))


def document_text(description: Description, component: str | None) -> str:
    """The json ``from-elf`` prints: the list of entries, or the component file ``component``
    names."""
    if component is None:
        document: Any = list(description.interface)
    else:
        document = component_file(component, description.types, description.interface)
    return json.dumps(document, indent=2) + "\n"


def _definition(
    image: Image, variable: Variable, typed: Typed, *, producer: bool, bag: DiagnosticBag
) -> dict[str, Any] | None:
    definition: dict[str, Any] = {"name": variable.name, "kind": typed.kind}
    if typed.typename is not None:
        definition["typename"] = typed.typename
    else:
        definition["datatype"] = typed.datatype
    if typed.dimensions:
        definition["dimensions"] = list(typed.dimensions)
    if typed.conversion is not None:
        definition["conversion"] = typed.conversion
    if producer and not _storage(image, variable, typed, definition, bag):
        return None
    definition["volatile"] = typed.volatile
    return definition


def _storage(
    image: Image, variable: Variable, typed: Typed, definition: dict[str, Any], bag: DiagnosticBag
) -> bool:
    """Add the storage keys a producer states; False, reported, where they cannot be read."""
    assert variable.address is not None  # selection keeps a variable with an address only
    location = place(image, variable.declared_at)
    section = image.section_of(variable.address)
    if section is None:
        report(
            bag,
            "elf-no-storage",
            f"'{variable.name}' has an address, {variable.address:#x}, that no section of the "
            f"image holds",
            location,
        )
        return False
    if section.offset is not None:
        raw = image.read(variable.address, typed.element_size * math.prod(typed.dimensions))
        if raw is None:
            report(
                bag,
                "elf-init-unsupported",
                f"'{variable.name}' runs past the end of section '{section.name}', so its "
                f"initial value cannot be read",
                location,
            )
            return False
        if typed.datatype is not None:
            try:
                definition["init"] = initial_value(
                    raw, typed.datatype, typed.dimensions, image.byte_order
                )
            except UnstatableValueError as error:
                report(
                    bag,
                    "elf-init-unsupported",
                    f"'{variable.name}' starts as {error}, which DDD cannot state as an "
                    f"initial value",
                    location,
                )
                return False
        elif any(raw):
            report(
                bag,
                "elf-init-dropped",
                f"'{variable.name}' starts with values the image holds, which DDD does not "
                f"carry: a structured object is zero-initialised, and its values reach it from "
                f"the running software or from the calibration tool",
                location,
            )
    if section.name not in DEFAULT_SECTIONS:
        definition["section"] = section.name
    return True


def _without_conflicts(
    candidates: list[Candidate], mapper: Mapper, image: Image, bag: DiagnosticBag
) -> list[Candidate]:
    conflicts = mapper.conflicts()
    kept: list[Candidate] = []
    for candidate in candidates:
        clashing = sorted(candidate.reaches & conflicts.keys())
        if not clashing:
            kept.append(candidate)
            continue
        name = clashing[0]
        notes: list[tuple[str, Location | None]] = [
            (f"'{name}' is defined one way here", place(image, declared_at))
            for declared_at in conflicts[name]
        ]
        report(
            bag,
            "elf-type-conflict",
            f"'{candidate.variable.name}' reaches '{name}', which the image defines "
            f"{len(conflicts[name])} different ways, so no one description of it is right",
            place(image, candidate.variable.declared_at),
            notes,
        )
    return kept


def _report_sections(kept: Sequence[Candidate], image: Image, bag: DiagnosticBag) -> None:
    seen: set[str] = set()
    for candidate in kept:
        name = candidate.definition.get("section")
        if name is None or name in seen:
            continue
        seen.add(name)
        report(
            bag,
            "elf-section",
            f"'{candidate.variable.name}' is placed in '{name}', the name of the image's output "
            f"section: DDD's section is the one the source places it in, which the linker "
            f"script may have renamed, and the project has to declare it in a sections file, "
            f"or 'ddd check' reports unknown-section",
            place(image, candidate.variable.declared_at),
        )


def _report_run(
    kept: Sequence[Candidate], image: Image, bag: DiagnosticBag, *, component: str | None
) -> None:
    if not kept:
        return
    message = NOT_INFERRED
    if any(candidate.definition["kind"] == "value_block" for candidate in kept):
        message += VALUE_BLOCKS
    report(bag, "elf-not-inferred", message, where(image.path))
    if component is None and any("typename" in candidate.definition for candidate in kept):
        report(
            bag,
            "elf-types-omitted",
            "the list output has no place for the types its structured objects name: "
            "'--component NAME' prints a component file that holds them",
            where(image.path),
        )
