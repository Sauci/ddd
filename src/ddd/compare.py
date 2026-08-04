"""Comparing data objects, and comparing whole dictionaries across two deliveries.

Two questions are asked with the same machinery but are not the same question:

* :mod:`ddd.analysis` compares two *declarations of one object inside one project* - they
  have to agree, full stop.
* :func:`compare` compares *one object in two versions of a project* - the question is
  directional ("can the candidate replace the baseline?") and graded, because growing a
  limit is harmless while rescaling a conversion silently falsifies every reading.

Only the idea is shared - a field, how to read it, how to phrase it - not the code: each
module keeps its own table, because the same property lands in different places. ``limits``
is a field here but a directional branch there; ``a2l`` is a table field there but its own
check here; ``local`` exists only here. Those differences are decisions, and
``TestComparisonTables`` in ``tests/test_comparison_tables.py`` records each one, next to the
guard that stops either table from silently falling behind its models.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from ddd.diagnostics import DiagnosticBag, Location
from ddd.ir import Comparable, DataDictionary
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


def _describe_references(entry: Comparable) -> str:
    if not entry.references:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(entry.references.items()))


# Change any of these and the consumers of the object are wrong, whether or not they still
# compile: a widened datatype breaks the abi, a rescaled conversion falsifies every value,
# and an object turning local takes itself out of reach.
_INTERFACE_FIELDS: tuple[ComparedField[Comparable], ...] = (
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
_STORAGE_FIELDS: tuple[ComparedField[Comparable], ...] = (
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
    if baseline.name != candidate.name:
        # Two deliveries of one project share its name, so a mismatch usually means the
        # wrong archived dump was picked up - and the report that follows would otherwise be
        # a confident, fully formed list of hundreds of removals that means nothing.
        bag.add(
            "project-mismatch",
            f"the baseline describes project '{baseline.name}' and the candidate describes "
            f"'{candidate.name}'; the comparison below only makes sense if that rename was "
            f"intended",
            location,
        )

    was = baseline.comparable
    now = candidate.comparable

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


def _report_removal(old: Comparable, bag: DiagnosticBag, location: Location | None) -> None:
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
    old: Comparable,
    new: Comparable,
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
            f"{_condition(new.condition)}, so {_condition_consequence(old, new)}",
            location,
        )

    # Compared as it will actually be rather than as it was written: a baseline that
    # simply omits the block is not asking for the object to be dropped from the a2l.
    if old.a2l.effective != new.a2l.effective:
        bag.add(
            "changed-a2l",
            f"'{old.name}': the a2l entry changed ({_a2l_difference(old, new)})",
            location,
        )


def _condition(condition: str | None) -> str:
    return f"'{condition}'" if condition else "none"


def _condition_consequence(old: Comparable, new: Comparable) -> str:
    """What the change of a condition costs, which depends on its direction.

    Wrapping an object that was always there is the damaging direction and has to say so:
    every build where the new condition is false loses the object, its consumers stop
    linking and a calibration dataset loses the label. The message used to describe every
    direction as a widening, which read as reassurance exactly when it was least warranted.
    """
    if old.condition is None:
        return "it is now absent from every build where that condition is false"
    if new.condition is None:
        return "it is now present in every build"
    return "the builds it is present in have changed"


_A2L_PROPERTIES = ("export", "format", "display_identifier")


def _a2l_difference(old: Comparable, new: Comparable) -> str:
    """Name only the a2l properties that actually differ.

    Rendering the whole record on both sides made a change to one property read as a change
    to all of them: adding a display identifier reported ``export=true -> export=true,
    display_identifier='FiltGain'``, which invites the reader to go looking for what happened
    to ``export``.
    """
    # Named as they are written in the file, compared as they will act: an ``export`` that
    # went from unstated to ``true`` changed nothing and has no business in the message.
    return ", ".join(
        f"{name}: {_a2l_value(before)} -> {_a2l_value(after)}"
        for name, before, after in zip(
            _A2L_PROPERTIES, old.a2l.effective, new.a2l.effective, strict=True
        )
        if before != after
    )


def _a2l_value(value: object) -> str:
    if value is None:
        return "none"
    if isinstance(value, bool):
        return str(value).lower()
    return f"'{value}'"
