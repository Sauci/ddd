"""Comparing data objects, and comparing whole dictionaries across two deliveries.

Two questions are asked with the same machinery but are not the same question:

* :mod:`ddd.analysis` compares two *declarations of one object inside one project* - they
  have to agree, full stop.
* :func:`compare` compares *one object in two versions of a project* - the question is
  directional ("can the candidate replace the baseline?") and graded, because growing a
  limit is harmless while rescaling a conversion silently falsifies every reading.

The mechanism is shared - :class:`ComparedField`, :func:`differing` and :func:`spell_out`
live here and :mod:`ddd.analysis` imports them - but each module keeps its own table,
because the same property lands in different places. ``limits`` is a field there but a
directional branch here; ``a2l`` is a table field there but its own check here; ``local``
exists only here. Those differences are decisions, and
``TestComparisonTables`` in ``tests/test_comparison_tables.py`` records each one, next to the
guard that stops either table from silently falling behind its models. The one value both
tables read identically is what a conversion *is* -
:func:`~ddd.models.conversion.conversion_identity` - because an enumerator's description is
documentation to both questions, and two answers to that would be a drift, not a decision.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from ddd.diagnostics import DiagnosticBag, Location
from ddd.ir import Comparable, DataDictionary, ResolvedLeaf
from ddd.models import conversion_identity, format_number, format_shape


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
    optional: bool = False
    """When set, a side that omits the property agrees with whatever the other says.

    Used for properties that have a derived default: a consumer that simply does not repeat
    the producer's limits is not disagreeing with them. Only the in-project table sets it -
    between two deliveries there is no producer to defer to.
    """


def differing[T](
    fields: Sequence[ComparedField[T]], reference: T, other: T
) -> list[ComparedField[T]]:
    """The fields on which the two disagree."""
    found = []
    for field in fields:
        mine, theirs = field.value(reference), field.value(other)
        if field.optional and (mine is None or theirs is None):
            continue
        if mine != theirs:
            found.append(field)
    return found


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
    # Compared through the same description free identity the in-project comparison reads,
    # because descriptions are not compared anywhere: a delivery that only documents an
    # enumerator changes no interface, while reordering or revaluing one changes every reader.
    ComparedField(
        "conversion",
        lambda o: conversion_identity(o.conversion),
        lambda o: o.conversion.describe(),
    ),
    # A dimension compares as its (spelling, value) pair: a name and its value are different
    # spellings of one size, and the spelling is what the generated code carries, so a
    # dimension that changes either half is a changed interface. Against a baseline dumped
    # before format 4, which recorded no spellings, the comparison defers to the values
    # alone - see :data:`_VALUE_SHAPE_FIELD`.
    ComparedField(
        "shape",
        lambda o: o.written_shape,
        lambda o: format_shape(o.spelled_shape) or "scalar",
    ),
    ComparedField("references", lambda o: o.references, _describe_references),
    ComparedField("local", lambda o: o.local, lambda o: str(o.local).lower()),
)

_VALUE_SHAPE_FIELD: ComparedField[Comparable] = ComparedField(
    "shape",
    lambda o: tuple(o.shape),
    lambda o: format_shape(o.spelled_shape) or "scalar",
)
"""The shape comparison a baseline without spellings falls back to: values only.

A dictionary dumped before format 4 recorded no ``dimensions``, so its spellings are not
"the numbers" - they are unknown. Against such a baseline only the values can disagree:
adopting a constant for a dimension that keeps its size is silent, while a changed size is
still a changed interface. Two format 4 dictionaries keep comparing spelling and value.
"""

_DEFERRED_INTERFACE_FIELDS: tuple[ComparedField[Comparable], ...] = tuple(
    _VALUE_SHAPE_FIELD if field.name == "shape" else field for field in _INTERFACE_FIELDS
)


def _spells_dimensions(entry: Comparable) -> bool:
    """Whether the entry records how its dimensions are spelled; a format 3 one does not."""
    return bool(entry.dimensions) or not entry.shape


def _interface_fields(old: Comparable, new: Comparable) -> tuple[ComparedField[Comparable], ...]:
    """The interface table for this pair: spelling aware only when both sides spell."""
    if _spells_dimensions(old) and _spells_dimensions(new):
        return _INTERFACE_FIELDS
    return _DEFERRED_INTERFACE_FIELDS


# Changing these alters behaviour or the generated files, but no consumer becomes wrong.
_STORAGE_FIELDS: tuple[ComparedField[Comparable], ...] = (
    ComparedField("init", lambda o: o.init, lambda o: "none" if o.init is None else repr(o.init)),
    ComparedField("volatile", lambda o: o.volatile, lambda o: str(o.volatile).lower()),
    ComparedField(
        "section", lambda o: o.section, lambda o: o.section if o.section is not None else "none"
    ),
    ComparedField(
        "raster", lambda o: o.raster, lambda o: o.raster if o.raster is not None else "none"
    ),
)


def identity(entry: Comparable) -> tuple[str, str] | None:
    """What two deliveries join this object on, or nothing when it carries no id.

    A plain object is its id. A leaf is its instance's id together with the part of its path
    below the instance, because a member has no declaration of its own to carry one: renaming
    the instance keeps the pair, and renaming a member of the *type* changes the second half
    and is therefore not tracked - which section 2 of the design records as a known gap.
    """
    if isinstance(entry, ResolvedLeaf):
        if entry.instance_id is None:
            return None
        return (entry.instance_id, entry.path[len(entry.instance) :])
    return None if entry.id is None else (entry.id, "")


def _pair(
    was: Mapping[str, Comparable], now: Mapping[str, Comparable]
) -> tuple[list[tuple[Comparable, Comparable]], list[Comparable], list[Comparable]]:
    """Pair on identity first, then on name, and say what is left on each side.

    Two passes rather than one so that both regimes coexist while a project migrates: an
    object that carries an id pairs on it whatever it is called, and one that does not pairs
    on its name exactly as it did before ids existed.
    """
    was_by_id = {key: entry for entry in was.values() if (key := identity(entry)) is not None}
    now_by_id = {key: entry for entry in now.values() if (key := identity(entry)) is not None}

    paired: list[tuple[Comparable, Comparable]] = []
    old_done: set[str] = set()
    new_done: set[str] = set()
    for key in sorted(was_by_id.keys() & now_by_id.keys()):
        old, new = was_by_id[key], now_by_id[key]
        paired.append((old, new))
        old_done.add(old.name)
        new_done.add(new.name)

    for name in sorted(was):
        if name in old_done or name in new_done or name not in now:
            continue
        before, after = identity(was[name]), identity(now[name])
        if before is not None and after is not None and before != after:
            continue  # two different objects that happen to share a spelling
        paired.append((was[name], now[name]))
        old_done.add(name)
        new_done.add(name)

    paired.sort(key=lambda pair: pair[0].name)
    removed = [was[name] for name in sorted(was) if name not in old_done]
    added = [now[name] for name in sorted(now) if name not in new_done]
    return paired, removed, added


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
    paired, removed, added = _pair(was, now)

    for old, new in paired:
        if old.name != new.name:
            readers = f", read by {', '.join(old.consumers)}" if old.consumers else ""
            bag.add(
                "renamed-object",
                f"'{old.name}' is now called '{new.name}'{readers}; every dataset, recording "
                f"and script keyed by the old spelling needs migrating",
                location,
            )
        _compare_object(old, new, bag, location)

    for name in sorted(was.keys() & now.keys()):
        before, after = identity(was[name]), identity(now[name])
        if before is None or after is None or before == after:
            continue
        # The failure that compiles, links, runs and reads the wrong storage: a dataset or a
        # recording keyed by this spelling binds to the new object as readily as to the old.
        moved = next((new.name for old, new in paired if old.name == name), None)
        notes = [(f"'{name}' is now called '{moved}'", None)] if moved else []
        bag.add(
            "reused-name",
            f"'{name}' now names a different object; a calibration dataset or a recording "
            f"keyed by that spelling will bind to it",
            location,
            notes=notes,
        )

    for old in removed:
        _report_removal(old, bag, location)

    for new in added:
        bag.add(
            "added-object",
            f"'{new.name}' is new in {candidate.name} "
            f"({new.kind.value}, produced by {new.owner or 'nobody'})",
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
    interface = differing(_interface_fields(old, new), old, new)
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
