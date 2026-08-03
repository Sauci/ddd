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
from pathlib import Path
from typing import Final

from ddd.analysis import analyze
from ddd.build_info import BuildInfo
from ddd.diagnostics import DiagnosticBag
from ddd.ir import DataDictionary, ResolvedObject
from ddd.lsp.navigation import workspaces
from ddd.models.common import format_number
from ddd.models.conversion import EnumConversion, conversion_range
from ddd.models.objects import ObjectKind, broadcast, flatten, format_shape

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


def resolve(builds: Sequence[BuildInfo], document: Path) -> DataDictionary | None:
    """The resolved project containing the document, or nothing if none resolves.

    Resolved on the spot rather than kept, for the reason navigation is: a hover is something
    a person asked for by putting the pointer somewhere and waiting, so the work lands on a
    gesture they chose to make.

    A project that did not read cleanly is still resolved here, unlike in a run of the checks.
    The findings will already be saying what is wrong with it; refusing to answer what a
    variable is on top of that helps nobody.
    """
    for workspace in workspaces(builds, document):
        return analyze(workspace, DiagnosticBag())
    return None


def describe(dictionary: DataDictionary, name: str) -> str | None:
    """The markdown an editor shows for one data object, or nothing if it has none."""
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


def _ownership(entry: ResolvedObject) -> str:
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
        rendered.append(("shape", f"`{format_shape(tuple(entry.shape))}`"))
    for key in _AXIS_KEYS:
        target = entry.references.get(key)
        if target is not None:
            rendered.append((key, f"`{target}`{_axis_range(dictionary, target)}"))
    if entry.condition:
        rendered.append(("condition", f"`{entry.condition}`"))
    if entry.volatile:
        rendered.append(("volatile", "yes"))
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
    drawn = rows(entry)
    if not drawn:
        return []
    flat = [value for row in drawn for value in row]
    low, high = min(flat), max(flat)
    if low == high:
        # Every element the same, which is what a scalar init on an array object means. A row
        # of equal bars would look like a reading of the data rather than the absence of one.
        return [f"init `{format_number(low)}` {entry.unit}".rstrip()]
    return [
        "```text",
        *(sparkline(row, low, high) for row in drawn),
        f"{format_number(low)} .. {format_number(high)} {entry.unit}".rstrip(),
        "```",
    ]
