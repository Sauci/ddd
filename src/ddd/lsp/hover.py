"""What a variable actually is, once the whole project has been resolved.

The file under the cursor says what one component asked for. This says what the project made
of it, which is a different and usually more interesting thing: the shape a curve got from its
axis, the limits derived from a datatype and a conversion nobody wrote down, who produces the
value and who reads it. None of that is in the file being hovered, and none of it is reachable
from a json schema, which sees one file at a time.

The init values are drawn as a sparkline where there is something to see. Two limits are worth
knowing about it:

* **These are initial values, not calibration data.** DDD describes an interface; what an
  engineer actually calibrates lives in the calibration tool, the hex file and the a2l. A
  curve whose ``init`` is a single scalar is flat here because that is genuinely all the
  project says about it.
* **A flat line is not drawn at all.** A row of identical bars looks like information and is
  not; the value is stated instead.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from ddd.analysis import analyze
from ddd.diagnostics import DiagnosticBag
from ddd.ir import DataDictionary, ResolvedInstance, ResolvedLeaf, ResolvedObject
from ddd.loading import Workspace
from ddd.models.common import format_number
from ddd.models.conversion import EnumConversion, conversion_range, raw_reading
from ddd.models.objects import ObjectKind, broadcast, flatten, format_shape
from ddd.models.types import ExternalType

BARS: Final = "▁▂▃▄▅▆▇█"
"""Eight levels, which is as much as a proportional font renders evenly."""

MAX_ENUMERATORS: Final = 12
"""Past this many, a hover is a wall of text rather than a reminder."""

_AXIS_KEYS: Final = ("axis", "x_axis", "y_axis", "input")


def sparkline(values: list[float], low: float, high: float) -> str:
    """One bar per value, against a scale given from outside.

    The scale is passed in rather than taken from ``values`` so that the rows of a map share
    one: a row drawn against its own minimum and maximum says nothing about whether it sits
    above or below its neighbour, which is most of what there is to see in a map.

    ``high`` above ``low`` is the caller's promise; a set with no variation in it is not drawn
    at all, because a row of identical bars looks like a reading of the data rather than the
    absence of one.
    """
    span = high - low
    return "".join(
        BARS[min(int((value - low) / span * len(BARS)), len(BARS) - 1)] for value in values
    )


def rows(entry: ResolvedObject) -> list[list[float]]:
    """The init values in physical units, one list per row of the object.

    A map is stored row wise, so the last dimension is the width of a row: that is the
    direction the x axis runs in, and drawing it that way puts the picture the same way round
    as the calibration tool shows it.
    """
    if entry.init is None:
        return []
    values = [
        entry.conversion.to_physical(value)
        for value in flatten(broadcast(entry.init, tuple(entry.shape)))
    ]
    width = entry.shape[-1] if entry.shape else len(values)
    return [values[start : start + width] for start in range(0, len(values), width)]


def resolve(projects: Sequence[Workspace]) -> DataDictionary | None:
    """The first of these projects, resolved, or nothing when there are none.

    Takes the loaded projects rather than the build records that lead to them, because
    finding them is the expensive half and the caller asks several questions of one answer:
    this and :func:`describe_external` used to walk the file tree from scratch apiece, for
    one hover.

    A project that did not read cleanly is still resolved here, unlike in a run of the checks.
    The findings will already be saying what is wrong with it; refusing to answer what a
    variable is on top of that helps nobody.
    """
    for workspace in projects:
        return analyze(workspace, DiagnosticBag())
    return None


def describe_constant(dictionary: DataDictionary, name: str) -> str | None:
    """The markdown for one declared constant, or nothing when nothing declares it.

    The value is the whole point of hovering the name: the file under the cursor spells
    ``"PRESSURE_CELLS"`` and the number lives in another file, next to the one description
    of what is being counted.
    """
    entry = next((constant for constant in dictionary.constants if constant.name == name), None)
    if entry is None:
        return None
    lines = [f"**{entry.name}** = {entry.value} — declared constant"]
    if entry.description:
        lines += ["", entry.description]
    return "\n".join(lines)


def describe_external(projects: Sequence[Workspace], name: str) -> str | None:
    """The markdown for one external type, or nothing when no project declares that name so.

    Answered from the loaded workspace rather than from the resolved dictionary, because an
    external type deliberately resolves to nothing: DDD knows neither its layout nor its
    meaning, so what there is to say - the name, the header that defines it, the free text -
    is exactly what the description states, and the header is the half that lives in another
    file from the member naming the type.
    """
    for workspace in projects:
        for entry in workspace.types:
            declared = entry.declared
            if isinstance(declared, ExternalType) and declared.name == name:
                lines = [f"**{declared.name}** — external type, defined by `{declared.header}`"]
                if declared.description:
                    lines += ["", declared.description]
                return "\n".join(lines)
    return None


def describe(dictionary: DataDictionary, name: str) -> str | None:
    """The markdown an editor shows for one data object, or nothing if it has none."""
    instance = next((entry for entry in dictionary.instances if entry.name == name), None)
    if instance is not None:
        return _describe_instance(dictionary, instance)
    entry = dictionary.by_name.get(name)
    if entry is None:
        return None
    lines = [f"**{entry.name}** — {entry.kind.value}, `{entry.datatype.value}`", ""]
    if entry.description:
        lines += [entry.description, ""]
    lines += [_ownership(entry), "", *_facts(entry, dictionary)]
    drawn = _drawing(entry)
    if drawn:
        lines += ["", *drawn]
    return "\n".join(lines)


def _describe_instance(dictionary: DataDictionary, entry: ResolvedInstance) -> str:
    """What a structured variable is: the type it names, and what that type holds.

    The members are the whole point of hovering one. The file under the cursor says
    ``"typename": "Sensor_t"`` and nothing else; what a reader wants is what is inside it,
    which lives in another file - and, for each member, the unit and limits the project worked
    out rather than the ones anybody wrote down.
    """
    lines = [f"**{entry.name}** — {entry.kind.value}, `{entry.type}`", ""]
    if entry.description:
        lines += [entry.description, ""]
    lines += [_ownership(entry), ""]
    facts = [("type", f"`{entry.type}`")]
    if entry.shape:
        facts.append(("shape", f"`{format_shape(entry.spelled_shape)}`"))
    if entry.condition:
        facts.append(("condition", f"`{entry.condition}`"))
    facts.append(("volatile", "yes" if entry.volatile else "no"))
    lines += ["| | |", "|---|---|"]
    lines += [f"| {label} | {value} |" for label, value in facts]

    # The value holding members: a member of an external type contributes no leaf - DDD
    # knows neither its layout nor its meaning - so a structure of only external members
    # honestly reports zero, and the count below spells that without a branch.
    leaves = [leaf for leaf in dictionary.leaves if leaf.instance == entry.name]
    lines += ["", f"**{len(leaves)} member{'s' if len(leaves) != 1 else ''}**", ""]
    lines += ["| member | type | unit | limits |", "|---|---|---|---|"]
    lines += [
        f"| `{leaf.path.removeprefix(entry.name).lstrip('.')}` "
        f"| `{_member_storage(leaf)}` "
        f"| {leaf.unit or '*none*'} "
        f"| {format_number(leaf.limits.min)} .. {format_number(leaf.limits.max)} |"
        for leaf in leaves
    ]
    return "\n".join(lines)


def _member_storage(leaf: ResolvedLeaf) -> str:
    """``uint16``, ``uint16[8]`` or ``uint16:2``, which is how the c spells it."""
    if leaf.bits is not None:
        return f"{leaf.datatype.value}:{leaf.bits}"
    return (
        f"{leaf.datatype.value}{format_shape(leaf.spelled_shape)}"
        if leaf.shape
        else (leaf.datatype.value)
    )


def _ownership(entry: ResolvedObject | ResolvedInstance) -> str:
    """Who writes it and who reads it, which is the whole point of a data dictionary."""
    if entry.owner is None:
        return "*No component produces this.*"
    if entry.local:
        return f"Local to **{entry.owner}**."
    readers = ", ".join(f"**{name}**" for name in entry.consumers) or "*nobody*"
    return f"Written by **{entry.owner}**, read by {readers}."


def _facts(entry: ResolvedObject, dictionary: DataDictionary) -> list[str]:
    """The resolved properties, as a table an editor renders."""
    rendered = [("unit", f"`{entry.unit}`" if entry.unit else "*none*")]
    low, high = conversion_range(entry.conversion, entry.datatype)
    limits = f"{format_number(entry.limits.min)} .. {format_number(entry.limits.max)}"
    if (entry.limits.min, entry.limits.max) == (low, high):
        # Said rather than guessed at: the dictionary has resolved away whether this was
        # written down or worked out, but that it *is* the whole range is worth knowing,
        # because it means nothing has been narrowed for the calibration tool.
        limits += " — the full range of the datatype"
    rendered.append(("limits", limits))
    rendered.append(("conversion", f"`{entry.conversion.describe()}`"))
    if entry.shape:
        # Spelled as the project writes it: a constant-dimensioned array names its constant.
        rendered.append(("shape", f"`{format_shape(entry.spelled_shape)}`"))
    for key in _AXIS_KEYS:
        target = entry.references.get(key)
        if target is not None:
            rendered.append((key, f"`{target}`{_axis_range(dictionary, target)}"))
    if entry.condition:
        rendered.append(("condition", f"`{entry.condition}`"))
    # Always, unlike the rows above it: every definition states this one, so leaving it out
    # when it is false would be the reader's only way of confusing "no" with "not asked".
    rendered.append(("volatile", "yes" if entry.volatile else "no"))
    table = ["| | |", "|---|---|"]
    table += [f"| {label} | {value} |" for label, value in rendered]
    return table + _enumerators(entry)


def _axis_range(dictionary: DataDictionary, target: str) -> str:
    """The span an axis covers, which is what makes its name mean something.

    Only for an axis, and only when it has points. The ``input`` of an axis names a
    measurement rather than an axis, and its init is one value, so a range of it would be a
    number repeated twice.
    """
    axis = dictionary.by_name.get(target)
    if axis is None or axis.kind is not ObjectKind.AXIS or axis.init is None:
        return ""
    points = [
        axis.conversion.to_physical(value)
        for value in flatten(broadcast(axis.init, tuple(axis.shape)))
    ]
    span = f"{format_number(min(points))} .. {format_number(max(points))} {axis.unit}"
    return f" — {span.rstrip()}"


def _enumerators(entry: ResolvedObject) -> list[str]:
    """The verbal values, when the conversion has any; the reason the datatype is an integer."""
    conversion = entry.conversion
    if not isinstance(conversion, EnumConversion):
        return []
    shown = conversion.enumerators[:MAX_ENUMERATORS]
    listed = [f"`{item.value}` {item.name}" for item in shown]
    if len(conversion.enumerators) > len(shown):
        listed.append(f"… {len(conversion.enumerators) - len(shown)} more")
    return ["", f"**{conversion.name}**: " + " · ".join(listed)]


def _drawing(entry: ResolvedObject) -> list[str]:
    """The init values, drawn if there is anything to see in them."""
    if entry.init is not None and not isinstance(entry.init, tuple):
        return [_stated_init(entry, entry.init)]
    drawn = rows(entry)
    if not drawn:
        return []
    flat = [value for row in drawn for value in row]
    low, high = min(flat), max(flat)
    if low == high:
        # Every element the same. A row of equal bars would look like a reading of the data
        # rather than the absence of one.
        return [f"init `{format_number(low)}` {entry.unit}".rstrip()]
    return [
        "```text",
        *(sparkline(row, low, high) for row in drawn),
        f"{format_number(low)} .. {format_number(high)} {entry.unit}".rstrip(),
        "```",
    ]


def _stated_init(entry: ResolvedObject, raw: float) -> str:
    """One scalar init: the raw value the file states, and what it reads as.

    The raw value first, because raw is what ``init`` *is* - the generated c carries it
    verbatim. The reading beside it is the forward conversion, which every raw value has;
    under the identity the two are one number, and an enum whose table does not name the
    value has no reading to add - both state the raw value alone, as before.
    """
    stated = f"init `{format_number(raw)}`"
    reading = raw_reading(entry.conversion, raw, entry.unit)
    if reading is None:
        return f"{stated} {entry.unit}".rstrip()
    return f"{stated} = {reading}"
