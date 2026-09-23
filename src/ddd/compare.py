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
guard that stops either table from silently falling behind its models. Both tables read a
conversion through :func:`~ddd.models.conversion.conversion_identity`, and an enum is the one
place they part: :mod:`ddd.analysis` narrows it to its name, because ``enum-conflict`` already
owns the enumerators inside a project and a second finding about them said nothing, while a
comparison has no ``enum-conflict`` of its own and so compares them here. That is a decision
like the others, not a drift.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass

from ddd.diagnostics import DiagnosticBag, Location
from ddd.ir import Comparable, DataDictionary, ResolvedInstance, ResolvedLeaf, ResolvedObject
from ddd.models import (
    Conversion,
    EnumConversion,
    PointCounts,
    conversion_identity,
    format_number,
    format_shape,
    is_above,
    is_below,
)


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

    detail: Callable[[T, T], str | None] | None = None
    """What else the finding says about this field, when the two values do not say it alone.

    ``spell_out`` renders a difference as ``name: after != before``, which is the whole story
    for a datatype and not for an init: a hundred thousand element block with one element
    changed spelled both sides whole - 600 kB in one warning, in the text report and in the
    json - and the reader still had to find the element that moved. Spelling the head of each
    instead would print two lists that look identical on a finding whose entire content is
    that they differ, so the index they part at is the rest of the sentence. Handed both
    sides, because where two values part is not a property of either one.
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
    return ", ".join(_spell_field(field, reference, other) for field in fields)


def _spell_field[T](field: ComparedField[T], reference: T, other: T) -> str:
    """One field's half of that message, with whatever :attr:`ComparedField.detail` adds.

    Parenthesised rather than appended behind a semicolon, so that the clause stays inside
    the one field it belongs to when several fields differ at once and the message joins them
    with commas.
    """
    spelled = f"{field.name}: {field.describe(other)} != {field.describe(reference)}"
    detail = None if field.detail is None else field.detail(reference, other)
    return spelled if detail is None else f"{spelled} ({detail})"


def describe_references(references: Mapping[str, str]) -> str:
    """``axis=Speed, input=Raw``, or ``none``: what an object refers to, for a finding.

    Here rather than in each of the two tables that compare the field, because it is one
    rule about one field of one model: :mod:`ddd.analysis` asks whether two components
    describing an object agree about its references and this module whether a delivery kept
    them, and a reader meeting both answers in one report reads one spelling.
    """
    if not references:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(references.items()))


def describe_condition(condition: str | None) -> str:
    """``'defined(FEATURE_X)'``, or ``none``: the condition a declaration is written under.

    Shared for the reason :func:`describe_references` is: two findings mention a condition -
    that two components disagree about one, and that a delivery changed one - and an absent
    condition is the same absence in both. ``none``, as every unstated value a finding of
    this module spells is ``none``.
    """
    return f"'{condition}'" if condition else "none"


def _describe_conversion(conversion: Conversion) -> str:
    """The conversion as a finding spells it: an enum with its enumerators.

    ``describe()`` names an enum and nothing else, which is what the in-project table wants -
    there ``enum-conflict`` owns the enumerators - but a delivery comparison has no such
    finding to leave them to, and ``enum(Mode_t) != enum(Mode_t)`` told the reader nothing
    about what had changed.
    """
    if isinstance(conversion, EnumConversion):
        return f"enum({conversion.name}: {conversion.spell_enumerators()})"
    return conversion.describe()


_MOST_INIT_ELEMENTS = 4
"""How many elements of a list a finding spells before it says how many there are."""

_MOST_INIT_CHARACTERS = 32
"""How much of a text init a finding spells before it says how long the text is."""


def _describe_init(value: object) -> str:
    """The init as the file spells it, cut short where spelling it whole says nothing.

    json throughout, because that is what a description file, ``ddd list`` and the hover all
    write: ``repr`` gave a list python's tuple - ``(7, 7, 7, 8)`` where every other reading of
    the same value is ``[7, 7, 7, 8]`` - a bool python's ``True``, and a string python's
    single quotes.

    Cut short because an init is as large as the array it fills, and a finding is a sentence:
    a ``uint8[100000]`` block spelled both sides of one warning at 600 017 characters, and a
    16 x 16 map about 1.6 kB per changed table. What a reader needs from a long one is enough
    of the head to recognise it and the count; where two of them part is
    :func:`_where_the_inits_part`'s half of the message.
    """
    if value is None:
        return "none"
    if isinstance(value, str):
        if len(value) <= _MOST_INIT_CHARACTERS:
            return json.dumps(value)
        return f"{json.dumps(value[:_MOST_INIT_CHARACTERS] + '...')} ({len(value)} characters)"
    if isinstance(value, tuple):
        head = ", ".join(_describe_init(element) for element in value[:_MOST_INIT_ELEMENTS])
        if len(value) > _MOST_INIT_ELEMENTS:
            return f"[{head}, ... {len(value)} values]"
        return f"[{head}]"
    return json.dumps(value)


def _where_the_inits_part(old: Comparable, new: Comparable) -> str | None:
    """``first differs at [3][7]: 8 != 7``, or nothing when the spellings already say it.

    Asked of the *stored* inits, which is what the comparison decided on: a scalar stands for
    every element of the array it fills, so ``7`` against ``[7, 7, 7, 8]`` parts at ``[3]``
    and not at the top. Silent when neither side is a list - two scalars, or one side with no
    init at all, are both spelled whole beside this - and silent when two lists agree as far
    as the shorter one goes, where the difference is the length and the two counts state it.
    """
    found = _first_difference(_stored_init(old), _stored_init(new))
    if found is None:
        return None
    path, spelled = found
    return f"first differs at {path}: {spelled}"


def _first_difference(before: object, after: object) -> tuple[str, str] | None:
    """The access path of the first element two stored inits disagree on, and the two values.

    A string never reaches here as text: :func:`_stored_init` has already turned it into the
    character codes it stores, so every value below is a number, a bool or a list of them.
    """
    pairs: Iterable[tuple[object, object]]
    if isinstance(before, tuple) and isinstance(after, tuple):
        pairs = zip(before, after, strict=False)
    elif isinstance(before, tuple):
        pairs = ((element, after) for element in before)
    elif isinstance(after, tuple):
        pairs = ((before, element) for element in after)
    else:
        return None
    for index, (mine, theirs) in enumerate(pairs):
        if mine == theirs:
            continue
        deeper = _first_difference(mine, theirs)
        if deeper is not None:
            path, spelled = deeper
            return f"[{index}]{path}", spelled
        return f"[{index}]", f"{_describe_init(theirs)} != {_describe_init(mine)}"
    return None


def _stored_init(entry: Comparable) -> object:
    """The init as the bytes it stores, which is what two deliveries compare.

    An init has more than one spelling for one piece of storage, and the tool offers both:
    a scalar init fills every element of an array - the c backend broadcasts it to render
    the initialiser, and the dictionary deliberately keeps it as the description wrote it
    (``ddd.analysis``) so that an archive says what was stated - and a string object takes
    either its text or the character codes of it. Compared as written, ``7`` on a
    ``uint8[4]`` and ``[7, 7, 7, 7]`` were a ``changed-storage`` warning and, under the
    ``--strict`` gate the comparison page recommends, a delivery that "cannot replace" its
    predecessor over generated code that is byte for byte the same file.

    So both spellings are reduced to one before they are compared, by collapsing the
    repetition rather than by expanding it - ``[7, 7, 7, 7]`` reads as ``7`` where ``7``
    would have had to become ``(7, 7, 7, 7)``. Same equality, and the collapse needs no
    shape, which is what keeps two things from going wrong. A delivery that resized the
    array - already a ``changed-interface`` for its shape - would otherwise compare four
    sevens against eight and report a second finding reading ``init: 7 != 7``, true of the
    bytes and nonsense on the page. And expanding a scalar means building one element per
    element of the array to compare it, ten million of them at the cap a shape may reach,
    every time the object is compared.

    A string is the one case that does need the shape: its bytes are its characters and
    then the zeros c writes after them, up to the length of the array. The analysis has
    already refused a string that is not one dimensional and refused text that leaves no
    room for the terminator, so the padding here only fills what the array has left.
    """
    init = entry.init
    if init is None:
        return None
    if isinstance(init, str):
        codes = tuple(ord(character) for character in init)
        width = entry.shape[0] if entry.shape else len(codes)
        return _uniform(codes + (0,) * (width - len(codes)))
    return _uniform(init)


def _uniform(value: object) -> object:
    """A nested init reduced to the one value it repeats, or left as it is.

    The whole init may be written as a single scalar, and that is the only abbreviation the
    file format offers - a scalar inside a nested list is refused - so a list every element
    of which is the same value is the long spelling of exactly that scalar, at every depth.
    """
    if not isinstance(value, tuple):
        return value
    collapsed = tuple(_uniform(element) for element in value)
    repeated = set(collapsed)
    return repeated.pop() if len(repeated) == 1 else collapsed


def _point_counts(entry: Comparable) -> str:
    """The convention of a plain object; a structure member is never a table, so ``none``."""
    return entry.point_counts.value if isinstance(entry, ResolvedObject) else PointCounts.NONE.value


# Change any of these and the consumers of the object are wrong, whether or not they still
# compile: a widened datatype breaks the abi, a rescaled conversion falsifies every value,
# and an object turning local takes itself out of reach.
_INTERFACE_FIELDS: tuple[ComparedField[Comparable], ...] = (
    ComparedField("kind", lambda o: o.kind.value, lambda o: o.kind.value),
    ComparedField("datatype", lambda o: o.datatype.value, lambda o: o.datatype.value),
    # The width of a bitfield is part of the layout, which is why it is interface and not
    # storage: narrowing one changes the value every reader gets out of the word, widening one
    # moves every member after it, and the c the consumers compile against is a different
    # structure either way. ``None`` on a plain object, which is never a bitfield.
    ComparedField(
        "bits", lambda o: o.bits, lambda o: str(o.bits) if o.bits is not None else "none"
    ),
    ComparedField("unit", lambda o: o.unit, lambda o: f"'{o.unit}'"),
    # Compared through the same description free identity the in-project comparison reads,
    # because descriptions are not compared anywhere: a delivery that only documents an
    # enumerator changes no interface, while reordering or revaluing one changes every reader.
    ComparedField(
        "conversion",
        lambda o: conversion_identity(o.conversion),
        lambda o: _describe_conversion(o.conversion),
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
    # Where a table keeps its point counts is layout, for the reason a bitfield's width is:
    # the size every reader declares changes, and the data moves behind the counts, so every
    # reader and every interpolation over it reads the wrong element whether or not it compiles.
    ComparedField("point_counts", _point_counts, _point_counts),
    # ``references`` is compared by hand below rather than from this table, for the reason
    # ``limits`` is: the answer is not a property of the entry alone. A referent is named, and
    # two deliveries name it differently the moment it is renamed - so the comparison resolves
    # each name to the referent's identity first, which no lambda over one entry can do.
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


# Changing these alters behaviour or the generated files, but no consumer becomes wrong.
_STORAGE_FIELDS: tuple[ComparedField[Comparable], ...] = (
    # Compared as the storage it produces and described as it was written: the value the two
    # deliveries have to agree on is the bytes, while a reader of the finding is looking for
    # the line to edit, which is the spelling in front of them.
    ComparedField(
        "init", _stored_init, lambda o: _describe_init(o.init), detail=_where_the_inits_part
    ),
    ComparedField("volatile", lambda o: o.volatile, lambda o: str(o.volatile).lower()),
    ComparedField(
        "section", lambda o: o.section, lambda o: o.section if o.section is not None else "none"
    ),
    ComparedField(
        "raster", lambda o: o.raster, lambda o: o.raster if o.raster is not None else "none"
    ),
)

_OF_THE_VARIABLE = frozenset({"local", "volatile", "section", "raster"})
"""The fields a leaf only carries because its variable does, compared at the variable instead.

``ddd.analysis`` copies these onto every leaf of a structured variable from the instance, so
a project that flips one of them flips it on every member at once: comparing them per leaf
turned one edit into one finding per member - three for a three member structure, and one for
every element of an array of them - each saying the same thing about the same declaration.
:func:`_compare_instances` compares them once, where they are written. What is left on a leaf
is what the *member* states: its storage, its meaning, its shape, its width in bits and the
a2l entry it asks for.
"""

_LEAF_INTERFACE_FIELDS: tuple[ComparedField[Comparable], ...] = tuple(
    field for field in _INTERFACE_FIELDS if field.name not in _OF_THE_VARIABLE
)
_DEFERRED_LEAF_INTERFACE_FIELDS: tuple[ComparedField[Comparable], ...] = tuple(
    field for field in _DEFERRED_INTERFACE_FIELDS if field.name not in _OF_THE_VARIABLE
)
_LEAF_STORAGE_FIELDS: tuple[ComparedField[Comparable], ...] = tuple(
    field for field in _STORAGE_FIELDS if field.name not in _OF_THE_VARIABLE
)


def _spells_dimensions(entry: Comparable | ResolvedInstance) -> bool:
    """Whether the entry records how its dimensions are spelled; a format 3 one does not."""
    return bool(entry.dimensions) or not entry.shape


def _interface_fields(old: Comparable, new: Comparable) -> tuple[ComparedField[Comparable], ...]:
    """The interface table for this pair: spelling aware only when both sides spell.

    A leaf is compared with the same table minus what belongs to its variable, which
    :func:`_compare_instances` answers for once instead of once per member.
    """
    spelled = _spells_dimensions(old) and _spells_dimensions(new)
    if isinstance(old, ResolvedLeaf):
        return _LEAF_INTERFACE_FIELDS if spelled else _DEFERRED_LEAF_INTERFACE_FIELDS
    return _INTERFACE_FIELDS if spelled else _DEFERRED_INTERFACE_FIELDS


def _storage_fields(old: Comparable) -> tuple[ComparedField[Comparable], ...]:
    """The storage table for this entry, for the reason :func:`_interface_fields` has two."""
    return _LEAF_STORAGE_FIELDS if isinstance(old, ResolvedLeaf) else _STORAGE_FIELDS


# What a structured variable is, as against what each of its members is. ``type`` is the whole
# of it: a variable of a renamed structure declares a different c type in every consumer's
# header - the in-project table calls two declarations disagreeing about it
# ``definition-mismatch`` - while the members underneath it can be identical to the byte, so
# no leaf of it has anything to report.
_INSTANCE_INTERFACE_FIELDS: tuple[ComparedField[ResolvedInstance], ...] = (
    ComparedField("type", lambda o: o.type, lambda o: f"'{o.type}'"),
    ComparedField(
        "shape", lambda o: o.written_shape, lambda o: format_shape(o.spelled_shape) or "scalar"
    ),
    ComparedField("local", lambda o: o.local, lambda o: str(o.local).lower()),
)

_VALUE_SHAPE_INSTANCE_FIELD: ComparedField[ResolvedInstance] = ComparedField(
    "shape", lambda o: tuple(o.shape), lambda o: format_shape(o.spelled_shape) or "scalar"
)
"""What :data:`_VALUE_SHAPE_FIELD` is, for the array dimensions of a structured variable."""

_DEFERRED_INSTANCE_INTERFACE_FIELDS: tuple[ComparedField[ResolvedInstance], ...] = tuple(
    _VALUE_SHAPE_INSTANCE_FIELD if field.name == "shape" else field
    for field in _INSTANCE_INTERFACE_FIELDS
)

_INSTANCE_STORAGE_FIELDS: tuple[ComparedField[ResolvedInstance], ...] = (
    ComparedField("volatile", lambda o: o.volatile, lambda o: str(o.volatile).lower()),
    ComparedField(
        "section", lambda o: o.section, lambda o: o.section if o.section is not None else "none"
    ),
    ComparedField(
        "raster", lambda o: o.raster, lambda o: o.raster if o.raster is not None else "none"
    ),
)


def _instance_interface_fields(
    old: ResolvedInstance, new: ResolvedInstance
) -> tuple[ComparedField[ResolvedInstance], ...]:
    """The instance interface table for this pair, deferring as the object one does."""
    if _spells_dimensions(old) and _spells_dimensions(new):
        return _INSTANCE_INTERFACE_FIELDS
    return _DEFERRED_INSTANCE_INTERFACE_FIELDS


type _Joined = Comparable | ResolvedInstance
"""What the pairing works on: a plain object, a member of a structured one, or the variable.

The three are joined by exactly one rule - an id where there is one, a name otherwise - so
the pairing is written once and asked three times rather than copied.
"""


def _identity(entry: _Joined) -> tuple[str, str] | None:
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


def _joinable[T: _Joined](side: Mapping[str, T]) -> dict[tuple[str, str], T]:
    """One side's entries, keyed by identity - excluding any identity claimed more than once.

    ``duplicate-id`` refuses two objects sharing an identity, but a *baseline* is read back
    rather than re-checked, so an archived dictionary written with that check relaxed, or
    edited by hand, can carry a collision anyway. Indexed naively the later entry would win
    and the earlier one would fall through to a removal - an object vanishing from the report
    because of a defect in the file it was read from, with nothing said about it.

    A colliding identity is therefore no identity at all here: both entries are left out of
    the index and pair on their names in the second pass, which is what they would have done
    before ids existed. Degrading to the older behaviour is the safe direction; silently
    dropping one of them is not.
    """
    seen: dict[tuple[str, str], T] = {}
    collided: set[tuple[str, str]] = set()
    for entry in side.values():
        key = _identity(entry)
        if key is None:
            continue
        if key in seen:
            collided.add(key)
        seen[key] = entry
    return {key: entry for key, entry in seen.items() if key not in collided}


def _states_different_identities(old: _Joined, new: _Joined) -> bool:
    """Whether two entries' identities both exist and disagree.

    One rule with two readers, which is why it is a function rather than a condition written
    out twice. :func:`_pair` refuses to pair such a couple, and :func:`compare` reports the
    shared spelling as ``reused-name``: the refusal and the finding are two halves of one
    statement - that these are different objects wearing one name - and they have to agree
    forever. An entry that states no identity is not evidence either way, so a couple where
    either side is silent is not this case.
    """
    before, after = _identity(old), _identity(new)
    return before is not None and after is not None and before != after


def _pair[T: _Joined](
    was: Mapping[str, T], now: Mapping[str, T]
) -> tuple[list[tuple[T, T]], list[T], list[T]]:
    """Pair on identity first, then on name, and say what is left on each side.

    Two passes rather than one so that both regimes coexist while a project migrates. The
    first pairs on identity: an object that carries one pairs on it whatever it is called,
    which is what makes a rename a rename rather than a removal and an addition.

    The second pairs by name whatever the first left over, exactly as this worked before ids
    existed - and it is the pass that carries the half-migrated project, where one side of a
    delivery states an id and the other does not yet. It refuses one case: two entries whose
    identities *both* exist and differ are not paired, because the ids say outright that they
    are different objects, and running the whole interface comparison between two unrelated
    things would bury the ``reused-name`` that is the real finding.
    """
    was_by_id = _joinable(was)
    now_by_id = _joinable(now)

    paired: list[tuple[T, T]] = []
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
        if _states_different_identities(was[name], now[name]):
            continue  # two different objects that happen to share a spelling
        paired.append((was[name], now[name]))
        old_done.add(name)
        new_done.add(name)

    paired.sort(key=lambda pair: pair[0].name)
    removed = [was[name] for name in sorted(was) if name not in old_done]
    added = [now[name] for name in sorted(now) if name not in new_done]
    return paired, removed, added


def renames(paired: Sequence[tuple[Comparable, Comparable]]) -> list[dict[str, str]]:
    """The old-to-new name pairs of a comparison, for migrating what DDD cannot see.

    Takes the pairing :func:`compare` returns rather than the two dictionaries, so the map is
    a second reading of one comparison instead of a second comparison.

    Sorted by the new name, so two runs of one comparison produce the same file and a diff of
    two such files means something.
    """
    # A member of a structured variable is its instance's id followed by its member path,
    # ``k7m2q9xr4t8w.value``: one id per row, so a tool keying on it keeps every member.
    moved = [
        {"id": "".join(key), "from": old.name, "to": new.name}
        for old, new in paired
        if old.name != new.name and (key := _identity(old)) is not None
    ]
    return sorted(moved, key=lambda entry: entry["to"])


def compare(
    baseline: DataDictionary,
    candidate: DataDictionary,
    bag: DiagnosticBag,
    *,
    location: Location | None = None,
) -> list[tuple[Comparable, Comparable]]:
    """Report how far ``candidate`` can stand in for ``baseline``, and hand back the pairing.

    The pairing is returned because it is a genuine product of comparing and the migration map
    is a second view of it: ``renames`` reading it back costs nothing, where re-deriving it
    would build both side maps and run :func:`_pair` a second time over identical input.

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

    _compare_layouts(baseline, candidate, bag, location)
    _compare_instances(baseline, candidate, bag, location)

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
        _compare_object(old, new, bag, location, was, now)

    renamed = {old.name: new.name for old, new in paired if old.name != new.name}
    claimed = {new: old for old, new in renamed.items()}
    for name in sorted(was.keys() & now.keys()):
        # Proof does not need both sides to have adopted an id, and a rename proves it from
        # either end. Pairing (above) may have matched the baseline's object under this name
        # to a *different* name in the candidate, which proves whatever still answers to the
        # name there is not it; or it may have matched a *different* baseline object onto this
        # name, which proves the same thing from the other side - the entry the candidate
        # publishes here is one the baseline called something else. Either way the entry that
        # is silent about its identity is the one whose id nobody has to read (design 5.3).
        moved = renamed.get(name)
        taken = claimed.get(name)
        if (
            moved is None
            and taken is None
            and not _states_different_identities(was[name], now[name])
        ):
            continue
        # The failure that compiles, links, runs and reads the wrong storage: a dataset or a
        # recording keyed by this spelling binds to the new object as readily as to the old.
        notes = [(f"'{name}' is now called '{moved}'", None)] if moved else []
        if taken is not None:
            notes.append((f"the object now under it is the baseline's '{taken}'", None))
        bag.add(
            "reused-name",
            f"'{name}' now names a different object; a calibration dataset or a recording "
            f"keyed by that spelling will bind to it",
            location,
            notes=notes,
        )

    candidates = _by_discriminators(added)
    for old in removed:
        _report_removal(old, bag, location, candidates, was, now)

    for new in added:
        bag.add(
            "added-object",
            f"'{new.name}' is new in {candidate.name} "
            f"({new.kind.value}, produced by {new.owner or 'nobody'})",
            location,
        )

    return paired


def _compare_layouts(
    baseline: DataDictionary,
    candidate: DataDictionary,
    bag: DiagnosticBag,
    location: Location | None,
) -> None:
    """Report a structure whose members were reordered, which its leaves cannot say.

    Reordering the members of a released structure moves every address after the first change
    - which is what the ``Member`` docstring published in two schemas has always promised a
    comparison reports - and yet every leaf of the reordered type is untouched: same path,
    same datatype, same conversion, same limits. A comparison that walks only the leaves
    therefore says nothing at all, and the delivery that silently moved every offset of every
    variable of that type "can replace" its predecessor.

    Reported at the structure rather than at a leaf or at a variable, because the order is a
    property of the type: the edit was one edit, one line moved in one types file, while a
    project with three variables of a six member structure would otherwise print the same
    sentence three or eighteen times and leave the reader to work out that it is one thing.

    Only the members both sides declare are lined up. A member that arrived or left is
    already an addition or a removal of the leaf it contributes, in a finding that names the
    path; what this adds is the part no such finding carries - that the members which stayed
    are not where they were.
    """
    was = {entry.name: entry.members for entry in baseline.types}
    now = {entry.name: entry.members for entry in candidate.types}
    for name in sorted(was.keys() & now.keys()):
        shared = {member.name for member in was[name]} & {member.name for member in now[name]}
        before = [member.name for member in was[name] if member.name in shared]
        after = [member.name for member in now[name] if member.name in shared]
        if before != after:
            bag.add(
                "changed-interface",
                f"'{name}' is not the same structure any more (members: {', '.join(after)} "
                f"!= {', '.join(before)}); reordering moves every address after the first "
                f"change, so every variable of it holds its members somewhere else",
                location,
            )


_MOST_CANDIDATES = 8
"""How many additions one bucket may hold before :func:`_lost_identity_note` gives up on it.

The note names a candidate only when exactly one addition is identical to the removal, so a
bucket - whose entries already agree on every hashable field the note compares - holding a
crowd of them was almost never going to produce one. What the bound actually buys is the
guarantee the key alone cannot give: whatever a delivery does, the work per removal is
bounded, so the note can no longer cost more than the comparison it annotates. Small enough
that a bucket at the limit is a handful of comparisons, large enough that the couple of
plausible candidates a real rename produces are all still weighed.
"""


def _hashable(value: object) -> object:
    """A compared value as something a dict key can hold, without changing what equals what.

    Every value a field table yields is hashable except the conversion, which
    :func:`~ddd.models.conversion.conversion_identity` renders as a dumped mapping for
    everything but an enum. Turned into its sorted items rather than into text, because the
    key has to agree with ``!=`` exactly: ``{"factor": 1}`` and ``{"factor": 1.0}`` are one
    conversion, and any spelling that told them apart would file a removal and its candidate
    in different buckets and lose the note with nothing said.
    """
    if isinstance(value, dict):
        return tuple(sorted(value.items()))
    return value


def _bucket_key(entry: Comparable, *, of_a_leaf: bool) -> tuple[object, ...]:
    """Everything hashable :func:`_lost_identity_note` compares, as one key.

    Read out of the field tables themselves rather than listed again, so that a field added to
    a table is in the key the day it is added - a key that had fallen behind its table would
    not fail anything, it would quietly stop offering notes that are still earned.

    The *deferred* interface table is the one to key on: it compares a dimension by its value
    where the other compares the (spelling, value) pair, and which of the two a pair gets
    depends on whether both sides record spellings. Equal pairs imply equal values, so the
    value is the half that is necessary under either table, and keying on the pair would
    separate a format 3 baseline from the candidate it is deferring to.

    ``references`` is not in either table - a referent is not a property of the entry alone,
    which is why the note compares it through :func:`_compare_references` - but the *names* of
    the reference fields are, and two entries whose keys differ can never be the same object.

    ``of_a_leaf`` is asked rather than read off the entry because it is the *removal* that
    decides which table the note runs (a leaf is compared without the fields it carries only
    because its variable does), and an addition has to be filed under both readings so that a
    removal of either sort finds it.
    """
    interface = _DEFERRED_LEAF_INTERFACE_FIELDS if of_a_leaf else _DEFERRED_INTERFACE_FIELDS
    storage = _LEAF_STORAGE_FIELDS if of_a_leaf else _STORAGE_FIELDS
    return (
        of_a_leaf,
        *(_hashable(field.value(entry)) for field in (*interface, *storage)),
        tuple(sorted(entry.references)),
    )


def _by_discriminators(added: Sequence[Comparable]) -> dict[tuple[object, ...], list[Comparable]]:
    """The additions grouped by everything hashable a candidate must agree on.

    :func:`_lost_identity_note` asks of every removal which additions are identical to it, and
    answering that by walking every addition for every removal is quadratic - each step running
    two field tables and a referent comparison. Grouping on three cheap fields was a filter and
    not a complexity fix: a naming-convention sweep over a project that has no ids yet, which is
    the migration ``--renames`` exists for, renames every object at once and puts every
    measurement of one datatype in one bucket. 5 300 objects took ten seconds and 53 000 took
    longer than anybody waits.

    Keying on the whole of what is comparable without resolving a referent leaves a bucket
    holding genuine candidates, and :data:`_MOST_CANDIDATES` bounds what is left. Each addition
    is filed twice, once under each reading of the tables, because whether the member fields
    count is the removal's question and not the addition's.
    """
    buckets: dict[tuple[object, ...], list[Comparable]] = {}
    for new in added:
        for of_a_leaf in (False, True):
            buckets.setdefault(_bucket_key(new, of_a_leaf=of_a_leaf), []).append(new)
    return buckets


def _lost_identity_note(
    old: Comparable,
    candidates: Sequence[Comparable],
    was: Mapping[str, Comparable],
    now: Mapping[str, Comparable],
) -> list[tuple[str, Location | None]]:
    """A note naming an addition identical to this removal, if there is exactly one.

    It asserts nothing and pairs nothing - the two really may be different objects. What it
    catches is the case no check can: an id edited by hand or mangled by a merge, after which
    the object is two unrelated objects again and every finding about it is technically true
    and completely unhelpful. Exactly one candidate, because naming several would be a guess
    dressed as a list.

    Referents are compared too, through :func:`_compare_references` rather than the fields
    table: ``references`` left that table (see its comment above) because a referent is not a
    property of the entry alone, and the same reasoning applies here - a curve over axis A and
    one over axis B would otherwise read as identical. Going through the identity-resolving
    helper rather than the written names keeps this correct whether or not either side has
    adopted ids yet, exactly like the comparison it borrows it from.

    A same-named candidate is excluded too. The only way an unpaired removal and an unpaired
    addition still share a name is ruling 3's pairing skip - two known ids that differ - and
    there the name never changed at all, so there is no rename to hypothesise: ``reused-name``
    already says exactly what happened, and this note would only contradict it right beside
    the highest-severity finding the whole feature produces.

    A crowded bucket is given up on rather than worked through: see :data:`_MOST_CANDIDATES`.
    """
    if len(candidates) > _MOST_CANDIDATES:
        return []
    same = [
        new
        for new in candidates
        if new.name != old.name
        and not differing(_interface_fields(old, new), old, new)
        and not differing(_storage_fields(old), old, new)
        and _compare_references(old, new, was, now) is None
    ]
    if len(same) != 1:
        return []
    return [
        (
            f"'{same[0].name}' was added with an identical interface; if that was a rename, "
            f"the id did not travel with it",
            None,
        )
    ]


def _report_removal(
    old: Comparable,
    bag: DiagnosticBag,
    location: Location | None,
    candidates: Mapping[tuple[object, ...], Sequence[Comparable]],
    was: Mapping[str, Comparable],
    now: Mapping[str, Comparable],
) -> None:
    bucket = candidates.get(_bucket_key(old, of_a_leaf=isinstance(old, ResolvedLeaf)), ())
    notes = _lost_identity_note(old, bucket, was, now)
    if old.consumers:
        bag.add(
            "removed-object",
            f"'{old.name}' is gone, but was read by {', '.join(old.consumers)}",
            location,
            notes=notes,
        )
    else:
        bag.add(
            "removed-unused-object",
            f"'{old.name}' is gone; no component read it, but a calibration dataset or an "
            f"external tool still might",
            location,
            notes=notes,
        )


def _referent_identity(name: str, side: Mapping[str, Comparable]) -> tuple[str, str] | None:
    """The identity of the object a reference names on one side, or nothing when it has none."""
    entry = side.get(name)
    return _identity(entry) if entry is not None else None


def _same_referent(
    before: str, was: Mapping[str, Comparable], after: str, now: Mapping[str, Comparable]
) -> bool:
    """Whether two written referent names name the same object across the two deliveries.

    Resolved by identity when *both* referents carry one; falls back to comparing the written
    names the moment either side's referent has none (design section 5.4). Resolving each side
    on its own and comparing the two answers - what an earlier version of this function did -
    does not implement that fallback: an id and a bare name never compare equal, so the moment
    only one side of a project had adopted ids, every reference to the object that had would
    read as changed whether or not it actually was, reporting a stray `changed-interface` on
    every curve, map and axis that named it.
    """
    before_key = _referent_identity(before, was)
    after_key = _referent_identity(after, now)
    if before_key is None or after_key is None:
        return before == after
    return before_key == after_key


def _compare_references(
    old: Comparable,
    new: Comparable,
    was: Mapping[str, Comparable],
    now: Mapping[str, Comparable],
) -> str | None:
    """How the referents differ, or nothing when they are the same objects.

    Compared as identities so that renaming one axis reports the axis and not every curve and
    map over it: a reference that follows a rename is the same reference.
    """
    if old.references.keys() != new.references.keys():
        return _describe_reference_change(old, new, was, now)
    for field, before in old.references.items():
        if not _same_referent(before, was, new.references[field], now):
            return _describe_reference_change(old, new, was, now)
    return None


def _describe_reference_change(
    old: Comparable,
    new: Comparable,
    was: Mapping[str, Comparable],
    now: Mapping[str, Comparable],
) -> str:
    """Phrase how the referents differ.

    A field whose written name is unchanged but whose referent is not - a name freed by a
    rename and claimed by something else in the same delivery - says so explicitly, rather than
    printing that one name on both sides of ``!=``. That would read as nothing having changed,
    which is exactly backwards: it is the line telling the reader their object is now silently
    bound to the wrong one, in the one check this whole feature exists to get right.
    """
    if old.references.keys() != new.references.keys():
        return (
            f"references: {describe_references(new.references)} != "
            f"{describe_references(old.references)}"
        )
    news: list[str] = []
    olds: list[str] = []
    for field in sorted(old.references):
        before, after = old.references[field], new.references[field]
        if before == after and not _same_referent(before, was, after, now):
            news.append(f"{field}={after} (now names a different object)")
        else:
            news.append(f"{field}={after}")
        olds.append(f"{field}={before}")
    return f"references: {', '.join(news)} != {', '.join(olds)}"


def _compare_object(
    old: Comparable,
    new: Comparable,
    bag: DiagnosticBag,
    location: Location | None,
    was: Mapping[str, Comparable],
    now: Mapping[str, Comparable],
) -> None:
    interface = differing(_interface_fields(old, new), old, new)
    references = _compare_references(old, new, was, now)
    if interface or references:
        readers = f", read by {', '.join(old.consumers)}" if old.consumers else ""
        spelled = spell_out(interface, old, new) if interface else ""
        both = ", ".join(part for part in (spelled, references or "") if part)
        bag.add(
            "changed-interface",
            f"'{old.name}' is not the same object any more ({both}){readers}",
            location,
        )

    storage = differing(_storage_fields(old), old, new)
    if storage:
        bag.add(
            "changed-storage",
            f"'{old.name}': {spell_out(storage, old, new)}",
            location,
        )

    # Limits are the one field where the direction decides: a wider range still accepts every
    # value the baseline allowed, a narrower one can invalidate data that was calibrated.
    # When the interface already changed - references included - tighter limits are a
    # consequence of it - reporting both would bury the cause under its own symptom.
    #
    # Weighed with the tolerance the analysis weighs a derived limit with, because most
    # limits are derived and deriving one goes through a float: a baseline archived before
    # the derived ends were rounded carries 3276.7000000000003 where a candidate that states
    # the limits its datatype implies writes 3276.7, and an exact comparison called that a
    # narrowing of 3e-13 on every rescaled object of every old delivery. One spelling of the
    # tolerance keeps this check and ``limits-out-of-range`` agreeing about which two numbers
    # are the same number.
    narrowed = is_above(new.limits.min, old.limits.min) or is_below(new.limits.max, old.limits.max)
    if narrowed and not interface and references is None:
        bag.add(
            "narrowed-limits",
            f"'{old.name}': limits tightened from "
            f"[{format_number(old.limits.min)}, {format_number(old.limits.max)}] to "
            f"[{format_number(new.limits.min)}, {format_number(new.limits.max)}]",
            location,
        )

    if not isinstance(old, ResolvedLeaf):
        # A member has no producer and no condition of its own: both are the variable's, and
        # are compared there once rather than repeated under every member's path.
        _compare_declaration(old, new, bag, location)

    # Compared as it will actually be rather than as it was written: a baseline that
    # simply omits the block is not asking for the object to be dropped from the a2l.
    if old.a2l.effective != new.a2l.effective:
        bag.add(
            "changed-a2l",
            f"'{old.name}': the a2l entry changed ({_a2l_difference(old, new)})",
            location,
        )


def _compare_declaration(
    old: _Joined, new: _Joined, bag: DiagnosticBag, location: Location | None
) -> None:
    """Who produces the thing, and under which condition: two findings of their own.

    Graded apart from the interface and the storage - ``changed-owner`` and
    ``changed-condition`` - and phrased by hand, which is why neither is a table entry. Shared
    between a plain object and a structured variable because a structure's members carry the
    producer and the condition of the variable and have nothing to add to either.
    """
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
            f"'{old.name}': condition {describe_condition(old.condition)} became "
            f"{describe_condition(new.condition)}, so {_condition_consequence(old, new)}",
            location,
        )


def _compare_instances(
    baseline: DataDictionary,
    candidate: DataDictionary,
    bag: DiagnosticBag,
    location: Location | None,
) -> None:
    """Compare the structured variables themselves, which their members cannot answer for.

    ``DataDictionary.comparable`` offers the plain objects and the leaves and never the
    instances, so a structured variable used to be compared only through its members - and
    two things fell between the two.

    What no member carries at all: the ``type``. Renaming ``Sensor_t`` to ``Sensor2_t`` with
    the members untouched changes what every consumer's header declares - ``extern Sensor2_t
    Inlet`` - which the in-project table already calls ``definition-mismatch``, while every
    leaf compares clean to the byte and the comparison said nothing whatsoever.

    What every member carries because the variable does: ``volatile``, ``section``,
    ``raster``, the producer and the condition. One flip of the variable's ``volatile`` was
    one ``changed-storage`` per member, three lines for a three member structure and one per
    element of an array of them, each naming a member for an edit that is on the variable.
    They are compared here once and left out of the leaf tables.

    Pairing is the pairing every other entry gets - an id where there is one, a name
    otherwise - and nothing is reported about what the pairing leaves over: an instance that
    went is every one of its leaves removed, an instance that arrived is every one of them
    added, and an instance renamed is every one of them renamed, each already said under the
    path that a dataset or a recording is actually keyed by.
    """
    was = {entry.name: entry for entry in baseline.instances}
    now = {entry.name: entry for entry in candidate.instances}
    paired, _removed, _added = _pair(was, now)
    for old, new in paired:
        interface = differing(_instance_interface_fields(old, new), old, new)
        if interface:
            readers = f", read by {', '.join(old.consumers)}" if old.consumers else ""
            bag.add(
                "changed-interface",
                f"'{old.name}' is not the same object any more "
                f"({spell_out(interface, old, new)}){readers}",
                location,
            )

        storage = differing(_INSTANCE_STORAGE_FIELDS, old, new)
        if storage:
            bag.add(
                "changed-storage",
                f"'{old.name}': {spell_out(storage, old, new)}",
                location,
            )

        _compare_declaration(old, new, bag, location)


def _condition_consequence(old: _Joined, new: _Joined) -> str:
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
