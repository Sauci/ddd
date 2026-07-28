"""Comparing data objects, and comparing whole dictionaries across two deliveries.

Two questions are asked with the same machinery but are not the same question:

* :mod:`ddd.analysis` compares two *declarations of one object inside one project* - they
  have to agree, full stop.
* :func:`compare` compares *one object in two versions of a project* - the question is
  directional ("can the candidate replace the baseline?") and graded, because growing a
  limit is harmless while rescaling a conversion silently falsifies every reading.

Only the primitive - a field, how to read it, how to phrase it - is shared. The two field
sets deliberately differ, and :class:`TestComparisonTables` in the test suite records why.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from ddd.diagnostics import DiagnosticBag, Location
from ddd.ir import DataDictionary, ResolvedObject
from ddd.models import format_number, format_shape


@dataclass(frozen=True, slots=True)
class ComparedField[T]:
    """One property two things are compared on.

    ``value`` is what has to match, ``describe`` is how the finding phrases it. Keeping the
    two together is the point: a field cannot be compared without being explainable, and
    adding one is a single entry instead of an edit in three places.
    """

    name: str
    value: Callable[[T], object]
    describe: Callable[[T], str]


def differing[T](
    fields: Sequence[ComparedField[T]], reference: T, other: T
) -> list[ComparedField[T]]:
    """The fields on which the two disagree."""
    return [field for field in fields if field.value(reference) != field.value(other)]


def spell_out[T](fields: Sequence[ComparedField[T]], reference: T, other: T) -> str:
    """``datatype: uint16 != uint8, unit: 'V' != 'Hz'``, for a diagnostic message."""
    return ", ".join(
        f"{field.name}: {field.describe(other)} != {field.describe(reference)}" for field in fields
    )


def _describe_references(entry: ResolvedObject) -> str:
    if not entry.references:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(entry.references.items()))


# -- what makes a candidate incompatible with its baseline -------------------

# Change any of these and the consumers of the object are wrong, whether or not they still
# compile: a widened datatype breaks the abi, a rescaled conversion falsifies every value,
# and an object turning local takes itself out of reach.
_INTERFACE_FIELDS: tuple[ComparedField[ResolvedObject], ...] = (
    ComparedField("kind", lambda o: o.kind.value, lambda o: o.kind.value),
    ComparedField("datatype", lambda o: o.datatype.value, lambda o: o.datatype.value),
    ComparedField("unit", lambda o: o.unit, lambda o: f"'{o.unit}'"),
    ComparedField(
        "conversion",
        lambda o: o.conversion.model_dump(mode="json"),
        lambda o: o.conversion.describe(),
    ),
    ComparedField("shape", lambda o: o.shape, lambda o: format_shape(o.shape) or "scalar"),
    ComparedField("references", lambda o: o.references, _describe_references),
    ComparedField("local", lambda o: o.local, lambda o: str(o.local).lower()),
)

# Changing these alters behaviour or the generated files, but no consumer becomes wrong.
_STORAGE_FIELDS: tuple[ComparedField[ResolvedObject], ...] = (
    ComparedField("init", lambda o: o.init, lambda o: "none" if o.init is None else repr(o.init)),
    ComparedField("volatile", lambda o: o.volatile, lambda o: str(o.volatile).lower()),
)


def compare(
    baseline: DataDictionary,
    candidate: DataDictionary,
    bag: DiagnosticBag,
    *,
    location: Location | None = None,
) -> None:
    """Report how far ``candidate`` can stand in for ``baseline``.

    The comparison is directional: everything the baseline offered has to still be there and
    still mean the same thing, while anything the candidate adds is its own business.
    """
    was = baseline.by_name
    now = candidate.by_name

    for name in sorted(was):
        old = was[name]
        new = now.get(name)
        if new is None:
            _report_removal(old, bag, location)
        else:
            _compare_object(old, new, bag, location)

    for name in sorted(now.keys() - was.keys()):
        added = now[name]
        bag.add(
            "added-object",
            f"'{name}' is new in {candidate.name} "
            f"({added.kind.value}, produced by {added.owner or 'nobody'})",
            location,
        )


def _report_removal(old: ResolvedObject, bag: DiagnosticBag, location: Location | None) -> None:
    if old.consumers:
        bag.add(
            "removed-object",
            f"'{old.name}' is gone, but was read by {', '.join(old.consumers)}",
            location,
        )
    else:
        bag.add(
            "removed-unused-object",
            f"'{old.name}' is gone; no component read it, but a calibration dataset or an "
            f"external tool still might",
            location,
        )


def _compare_object(
    old: ResolvedObject,
    new: ResolvedObject,
    bag: DiagnosticBag,
    location: Location | None,
) -> None:
    interface = differing(_INTERFACE_FIELDS, old, new)
    if interface:
        readers = f", read by {', '.join(old.consumers)}" if old.consumers else ""
        bag.add(
            "changed-interface",
            f"'{old.name}' is not the same object any more ({spell_out(interface, old, new)})"
            f"{readers}",
            location,
        )

    storage = differing(_STORAGE_FIELDS, old, new)
    if storage:
        bag.add(
            "changed-storage",
            f"'{old.name}': {spell_out(storage, old, new)}",
            location,
        )

    # Limits are the one field where the direction decides: a wider range still accepts every
    # value the baseline allowed, a narrower one can invalidate data that was calibrated.
    # When the interface already changed, tighter limits are a consequence of it - reporting
    # both would bury the cause under its own symptom.
    narrowed = new.limits.min > old.limits.min or new.limits.max < old.limits.max
    if narrowed and not interface:
        bag.add(
            "narrowed-limits",
            f"'{old.name}': limits tightened from "
            f"[{format_number(old.limits.min)}, {format_number(old.limits.max)}] to "
            f"[{format_number(new.limits.min)}, {format_number(new.limits.max)}]",
            location,
        )

    if old.owner != new.owner:
        bag.add(
            "changed-owner",
            f"'{old.name}' is now produced by {new.owner or 'nobody'} "
            f"instead of {old.owner or 'nobody'}",
            location,
        )

    if old.condition != new.condition:
        bag.add(
            "changed-condition",
            f"'{old.name}': condition {_condition(old.condition)} became "
            f"{_condition(new.condition)}, so the object may be present in other builds now",
            location,
        )

    if old.a2l != new.a2l:
        bag.add(
            "changed-a2l",
            f"'{old.name}': the a2l entry changed "
            f"({old.a2l.model_dump(mode='json')} -> {new.a2l.model_dump(mode='json')})",
            location,
        )


def _condition(condition: str | None) -> str:
    return f"'{condition}'" if condition else "none"
