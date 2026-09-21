"""What each key of a variable offers the panel of ``ddd gui``.

The panel settles one key of a variable at a time, on every declaration of it at once. What it
may offer for a key is the loader's own knowledge - which kinds carry which key, which of them
have to state it, what is already in play, and what a name may be - so it is worked out here,
once, and the page draws what it is given. No GUI and no HTTP: :mod:`ddd.gui.api` turns these
into the shape ``GET /api/variable`` answers, and nothing else reads them.

The values are raw json text throughout, as everywhere else in this interface: what the file
says, spelled the way it says it, which is what :func:`ddd.lsp.edits.settle` compares and what
an edit writes back.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final

from pydantic import TypeAdapter, ValidationError

from ddd.lsp.edits import DEFERRED_KEYS
from ddd.lsp.navigation import Index
from ddd.models import definition_keys
from ddd.models.common import Datatype
from ddd.models.conversion import Conversion, conversion_interface_value
from ddd.models.objects import Limits, ObjectKind
from ddd.variables import Declared

KEY_ORDER: Final = (
    "datatype",
    "typename",
    "unit",
    "conversion",
    "limits",
    "dimensions",
    "size",
    "volatile",
    "axis",
    "x_axis",
    "y_axis",
    "input",
)
"""Every key of :data:`ddd.lsp.edits.PROPAGATED_KEYS`, in the order a definition spells them:
what it is made of, what it means, what shape it has, and what it refers to.

An order rather than the frozenset itself, because an answer has to list them somehow and a
page cannot sort what it does not understand. The page groups the rows it draws - what the
declarations disagree about first - and keeps this order inside each group.
"""

DATATYPES: Final = tuple(datatype.value for datatype in Datatype)
"""The eleven names a ``datatype`` may be, from the models rather than a copy of them."""

EDITORS: Final = {
    "datatype": "datatype",
    "typename": "typename",
    "unit": "unit",
    "conversion": "none",
    "limits": "limits",
    "dimensions": "none",
    "size": "size",
    "volatile": "volatile",
    "axis": "name",
    "x_axis": "name",
    "y_axis": "name",
    "input": "name",
}
"""Which field the page offers beside the values already in play, per key.

``none`` is not "nothing may be chosen": a value in play is always offered, and for a
``conversion`` or a ``dimensions`` that is all - four kinds of conversion, an enumeration's
enumerators and a list of dimensions are a second loader's worth of form, and an editor writes
them better than a panel would. The rest are one field wide: a name, a number, a truth value,
a range, or part 1's unit picker.
"""


@dataclass(frozen=True, slots=True)
class Carried:
    """What one declaration's kind does with a key."""

    allowed: bool
    """Its kind has this key at all: ``dimensions`` on a measurement, never on a parameter."""

    required: bool
    """It cannot be left without it - so the panel offers no "state nothing"."""


@dataclass(frozen=True, slots=True)
class InPlay:
    """One value a key has among the declarations, and who has it."""

    raw: str
    """The json text, as the file spells it."""

    components: tuple[str, ...]
    """The components stating it, in the order the project lists them."""

    producer: bool
    """The producer is one of them."""


@dataclass(frozen=True, slots=True)
class KeyOffer:
    """What one key offers for one variable."""

    key: str
    carried: tuple[Carried, ...]
    """One per declaration, in the order they were passed in."""

    values: tuple[InPlay, ...]
    """Every distinct value in play, the producer's first."""

    disagrees: bool
    """The declarations do not all say the same thing about the key."""

    editor: str
    """One of :data:`EDITORS`."""

    choices: tuple[str, ...]
    """What that editor names, sorted: datatypes, types, constants or objects."""


def offers(built: Index, declared: Sequence[Declared]) -> tuple[KeyOffer, ...]:
    """What every key offers for these declarations of one variable, in :data:`KEY_ORDER`."""
    return tuple(_offer(built, declared, key) for key in KEY_ORDER)


def _offer(built: Index, declared: Sequence[Declared], key: str) -> KeyOffer:
    carried = tuple(_carried(entry, key) for entry in declared)
    values = _in_play(declared, key)
    return KeyOffer(
        key=key,
        carried=carried,
        values=values,
        disagrees=_disagrees(declared, carried, values, key),
        editor=EDITORS[key],
        choices=_choices(built, key),
    )


def _disagrees(
    declared: Sequence[Declared],
    carried: Sequence[Carried],
    values: Sequence[InPlay],
    key: str,
) -> bool:
    """Whether the declarations say different things about the key.

    Two values in play are a disagreement, and so is one value beside a declaration that may
    hold the key and states none: silence is a value, which is what ``definition-mismatch``
    reports. Except for a deferred key - a declaration stating no ``limits`` leaves them to
    whoever states them, and the check compares limits only where both sides state them. A
    declaration whose kind cannot hold the key at all is not part of the question, and a key
    nobody states is not a disagreement but an interface nobody has written down yet.
    """
    if len(values) > 1:
        return True
    if not values or key in DEFERRED_KEYS:
        return False
    stating = sum(1 for entry in declared if key in entry.stated or key in entry.fixed)
    return stating < sum(1 for may in carried if may.allowed)


def _carried(entry: Declared, key: str) -> Carried:
    accepted, required = definition_keys(_kind_of(entry))
    return Carried(allowed=key in accepted, required=key in required or key in _storage_of(entry))


def _kind_of(entry: Declared) -> str:
    """The kind the declaration states, or ``""`` when its file states none.

    The index was built from files that loaded; what a declaration states is read again from
    the file as it stands, which may have moved on since. A kind the models do not know means
    "offer nothing", which is what :func:`ddd.models.definition_keys` answers for it.
    """
    raw = entry.stated.get("kind")
    # Raw text of a parsed document: json, always, so there is nothing here to fail on.
    value = None if raw is None else json.loads(raw)
    return value if isinstance(value, str) else ""


def _storage_of(entry: Declared) -> frozenset[str]:
    """The storage keys this declaration cannot be left without.

    :func:`ddd.models.definition_keys` derives what a kind requires from the models' own
    fields, where ``datatype``, ``typename`` and ``conversion`` are each optional: a definition
    states either a datatype with the conversion that goes with it, or the name of a type that
    fixes both, and the models check the pair after the fact. Offering to strip the one a
    declaration actually uses would write a file the loader refuses, so the panel does not
    offer it.
    """
    if "typename" in entry.stated:
        return frozenset({"typename"})
    if "datatype" in entry.stated:
        return frozenset({"datatype", "conversion"})
    return frozenset()


def _in_play(declared: Sequence[Declared], key: str) -> tuple[InPlay, ...]:
    """Every distinct value the key has, the producer's first, then in the project's own order.

    A declaration naming a type has the value that type fixes, counted with the rest: the
    chooser lists what the variable means today, not what each file happens to spell.

    One value, however it is written - grouped by :func:`_same`, so that two spellings of one
    conversion or one range of limits count as one value here exactly as they do in
    :mod:`ddd.analysis`. The spelling carried is the producer's where the producer has the
    value, so that applying what the producer already states leaves its file alone.
    """
    stating: dict[str, list[str]] = {}
    spelling: dict[str, str] = {}
    produced: set[str] = set()
    for entry in declared:
        raw = entry.stated.get(key, entry.fixed.get(key))
        if raw is None:
            continue
        same = _same(key, raw)
        stating.setdefault(same, []).append(entry.component)
        if same not in spelling or entry.role == "produces":
            spelling[same] = raw
        if entry.role == "produces":
            produced.add(same)
    # Stable, so the producer's value leads and the others keep the order the project lists them.
    ordered = sorted(stating, key=lambda same: same not in produced)
    return tuple(
        InPlay(raw=spelling[same], components=tuple(stating[same]), producer=same in produced)
        for same in ordered
    )


_CONVERSION: Final[TypeAdapter[Conversion]] = TypeAdapter(Conversion)
"""Built once: a :class:`~pydantic.TypeAdapter` compiles a core schema from the annotation,
which is not free, and :func:`_same` asks it once for every declaration stating a conversion."""


def _same(key: str, raw: str) -> str:
    """What two spellings of ``key`` have to share to count as one value in play.

    Canonical json text for every key but the two :mod:`ddd.analysis` resolves before it
    compares them - a definition may leave out what the models complete, and the panel has to
    group values the way the checker does, or a row reads as a disagreement the checker files
    no finding about. A ``conversion`` groups by
    :func:`~ddd.models.conversion.conversion_interface_value`, the same rule
    ``definition-mismatch`` applies: an enum by its name, everything else by what the models
    resolve it to, so ``{"factor": 2}`` groups with ``{"kind": "linear", "factor": 2, "offset":
    0}``. ``limits`` group by the two numbers :class:`~ddd.models.objects.Limits` resolves them
    to, so ``{"min": 0, "max": 100}`` groups with ``{"min": 0.0, "max": 100.0}``. Text the
    models refuse outright - a file may hold a half-written conversion - falls back to its
    canonical json text like any other key: the panel still has to draw a row for what is on
    disk.
    """
    # Raw text of a parsed document: json, always, so there is nothing here to fail on.
    value = json.loads(raw)
    if key == "conversion":
        conversion = _parsed_conversion(value)
        if conversion is not None:
            return json.dumps(conversion_interface_value(conversion), sort_keys=True)
    elif key == "limits":
        limits = _parsed_limits(value)
        if limits is not None:
            return json.dumps([float(bound) for bound in limits.as_tuple()])
    return json.dumps(value, sort_keys=True)


def _parsed_conversion(value: Any) -> Conversion | None:
    """``value`` as the models would resolve it, or ``None`` where they refuse it outright."""
    try:
        return _CONVERSION.validate_python(value)
    except ValidationError:
        return None


def _parsed_limits(value: Any) -> Limits | None:
    """``value`` as the models would resolve it, or ``None`` where they refuse it outright."""
    try:
        return Limits.model_validate(value)
    except ValidationError:
        return None


def _choices(built: Index, key: str) -> tuple[str, ...]:
    """What the key's editor names, for the editors that name something."""
    if key == "datatype":
        return DATATYPES
    if key == "typename":
        return tuple(sorted(built.types))
    if key == "size":
        return tuple(sorted(built.constants))
    if key in ("axis", "x_axis", "y_axis"):
        return _objects(built, ObjectKind.AXIS)
    if key == "input":
        return _objects(built, ObjectKind.MEASUREMENT)
    return ()


def _objects(built: Index, kind: ObjectKind) -> tuple[str, ...]:
    """Every object of that kind the project declares, by name.

    A measurement that is an instance of a declared structure is listed with the rest, although
    an ``input`` may not name one: what a name may refer to beyond its kind is the loader's
    answer, and it gives it on the next analysis, exactly as it does for a file edited by hand.
    """
    return tuple(sorted(name for name, stated in built.kinds.items() if stated == kind.value))
