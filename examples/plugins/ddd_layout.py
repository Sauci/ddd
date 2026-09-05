"""A plugin that stamps an object with a key and a version, and ties the version to its layout.

The worked example of the plugin api, and nothing more: every rule in here is the smallest
one that exercises one thing the api offers - the settings, an in-project check, a comparison
paired on the plugin's own key and on the DDD ``id``, the locator, and a backend. A project
copies it and replaces the rules with its own.

The block on a definition is ``{"key": 0..65535, "version": >= 1}``, both required. The block
on the project is ``{"max_key": 0..65535}``, defaulting to 65535. The layout is what
``changed-interface`` compares - kind, datatype or type, shape, unit and conversion - and for a
structured variable it is its leaves plus the declared order of its members.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from ddd.backends import GeneratedFile
from ddd.diagnostics import CheckInfo, Severity
from ddd.ir import DataDictionary, ResolvedInstance, ResolvedObject
from ddd.models import conversion_identity
from ddd.plugins import CheckContext, CompareContext, GenerateContext, Plugin

KEY_MAX = 65535

Stamped = ResolvedObject | ResolvedInstance


class Entry(BaseModel):
    """The block on a definition."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: int = Field(ge=0, le=KEY_MAX)
    """The key of this object; distinct across the project."""

    version: int = Field(ge=1)
    """The version of its layout; increased whenever the layout changes, and only then."""


class Settings(BaseModel):
    """The block on the project."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_key: int = Field(default=KEY_MAX, ge=0, le=KEY_MAX)
    """The highest key a definition may claim; the range above is the project's to reserve."""


def _stamped(dictionary: DataDictionary) -> list[tuple[Stamped, Entry]]:
    """Every object carrying a block, with the block, sorted by key."""
    found: list[tuple[Stamped, Entry]] = []
    for entry in (*dictionary.objects, *dictionary.instances):
        block = entry.extensions.get("layout")
        if block is not None:
            found.append((entry, Entry.model_validate(block)))
    return sorted(found, key=lambda pair: pair[1].key)


def _member_order(type_name: str, dictionary: DataDictionary) -> tuple[object, ...]:
    """The members of the named structure, in declared order, nested structures recursively.

    ``dictionary.leaves`` is sorted by path, so two structures that swap two members compare
    equal there even though the swap is a real layout change in c; this is what tells them
    apart. ``()`` when ``type_name`` does not name a structure in ``dictionary.types``.
    """
    struct = next((t for t in dictionary.types if t.name == type_name), None)
    if struct is None:
        return ()
    return tuple(
        (member.name, _member_order(member.type, dictionary) if member.type else ())
        for member in struct.members
    )


def _layout(entry: Stamped, dictionary: DataDictionary) -> tuple[object, ...]:
    """The layout of one stamped object: leaves carry the datatypes, units and conversions of
    a structured variable; ``_member_order`` carries where each one sits. Both are needed - the
    leaves alone sort by path and miss a swap of two members, which changes the c layout."""
    if isinstance(entry, ResolvedObject):
        return (
            entry.kind,
            entry.datatype,
            entry.shape,
            entry.unit,
            conversion_identity(entry.conversion),
        )
    leaves = tuple(
        (
            leaf.path.removeprefix(entry.name),
            leaf.datatype,
            leaf.shape,
            leaf.bits,
            leaf.unit,
            conversion_identity(leaf.conversion),
        )
        for leaf in dictionary.leaves
        if leaf.instance == entry.name
    )
    return (entry.kind, entry.type, entry.shape, leaves, _member_order(entry.type, dictionary))


def _same_object(old: Stamped, new: Stamped) -> bool:
    """Told apart by the DDD id where both sides state one, by name otherwise."""
    if old.id is not None and new.id is not None:
        return old.id == new.id
    return old.name == new.name


def check(context: CheckContext) -> None:
    assert isinstance(context.settings, Settings)
    seen: dict[int, str] = {}
    for entry, stamp in _stamped(context.dictionary):
        if stamp.key > context.settings.max_key:
            context.bag.add(
                "layout/key-out-of-range",
                f"'{entry.name}' claims key {stamp.key}, above the project's max_key of "
                f"{context.settings.max_key}",
                context.locate(entry.name),
            )
        first = seen.get(stamp.key)
        if first is None:
            seen[stamp.key] = entry.name
            continue
        context.bag.add(
            "layout/duplicate-key",
            f"'{entry.name}' claims key {stamp.key}, which '{first}' already claims",
            context.locate(entry.name),
            notes=[("first claimed here", context.locate(first))],
        )


def _by_key(
    context: CompareContext, dictionary: DataDictionary, side: str
) -> dict[int, tuple[Stamped, Entry]]:
    """One side's entries by key, refusing a key claimed twice.

    A dump is read back rather than re-checked, so an archived baseline can carry the
    collision ``layout/duplicate-key`` would have refused in a live project. Keeping one of
    the two would silently drop the other from the comparison; both are reported and left
    out instead.
    """
    found: dict[int, tuple[Stamped, Entry]] = {}
    collided: dict[int, list[str]] = {}
    for entry, stamp in _stamped(dictionary):
        if stamp.key in found:
            collided.setdefault(stamp.key, [found[stamp.key][0].name]).append(entry.name)
        else:
            found[stamp.key] = (entry, stamp)
    for key, names in sorted(collided.items()):
        listed = ", ".join(f"'{name}'" for name in names)
        context.bag.add(
            "layout/duplicate-key",
            f"in the {side}: key {key} is claimed by {listed}; none of them is compared",
            context.locate(names[0]),
        )
        del found[key]
    return found


def compare(context: CompareContext) -> None:
    was = _by_key(context, context.baseline, "baseline")
    now = _by_key(context, context.candidate, "candidate")

    # One object, paired on the DDD id, under a different key: its entry is orphaned.
    old_key_by_id = {entry.id: stamp.key for entry, stamp in was.values() if entry.id}
    moved: set[int] = set()
    for entry, stamp in now.values():
        old_key = old_key_by_id.get(entry.id) if entry.id else None
        if old_key is not None and old_key != stamp.key:
            moved.add(old_key)
            context.bag.add(
                "layout/key-changed",
                f"'{entry.name}' carried key {old_key} and now carries {stamp.key}; its entry "
                f"under {old_key} is orphaned",
                context.locate(entry.name),
            )

    for key in sorted(was):
        old_entry, old = was[key]
        if key not in now:
            if key not in moved:
                context.bag.add(
                    "layout/removed-entry",
                    f"key {key} ('{old_entry.name}') is gone",
                    context.locate(old_entry.name),
                )
            continue
        new_entry, new = now[key]
        if not _same_object(old_entry, new_entry):
            context.bag.add(
                "layout/reused-key",
                f"key {key} was '{old_entry.name}' and is now '{new_entry.name}', a different "
                f"object",
                context.locate(new_entry.name),
            )
            continue
        changed = _layout(old_entry, context.baseline) != _layout(new_entry, context.candidate)
        if changed and new.version <= old.version:
            moved_version = (
                f"kept version {new.version}"
                if new.version == old.version
                else f"went from version {old.version} to {new.version}"
            )
            context.bag.add(
                "layout/version-not-bumped",
                f"'{new_entry.name}' (key {key}) changed its layout and {moved_version}",
                context.locate(new_entry.name),
            )
        elif not changed and new.version != old.version:
            context.bag.add(
                "layout/needless-version",
                f"'{new_entry.name}' (key {key}) went from version {old.version} to "
                f"{new.version} with the same layout",
                context.locate(new_entry.name),
            )


class LayoutBackend:
    """One header, one table entry per stamped object, sorted by key.

    An entry follows the condition of its object: the c templates compile the object out
    under ``#if``, and a table naming it then would not compile at all.
    """

    name = "layout"

    def __init__(self, settings: Settings, generator: str) -> None:
        self._settings = settings
        self._generator = generator

    def generate(self, dictionary: DataDictionary, output_dir: Path) -> list[GeneratedFile]:
        lines = [
            f"/* generated by {self._generator}: one entry per stamped object, by key */",
            "#ifndef DDD_LAYOUT_H",
            "#define DDD_LAYOUT_H",
            "",
            "#include <stddef.h>",
            "#include <stdint.h>",
            "",
            f"#define DDD_LAYOUT_MAX_KEY {self._settings.max_key}u",
            "",
            "typedef struct {",
            "    uint16_t key;",
            "    uint16_t version;",
            "    size_t size;",
            "    const void *address;",
            "} ddd_layout_entry_t;",
            "",
            "static const ddd_layout_entry_t ddd_layout_entries[] = {",
        ]
        for entry, stamp in _stamped(dictionary):
            row = f"    {{ {stamp.key}u, {stamp.version}u, sizeof({entry.name}), &{entry.name} }},"
            if entry.condition:
                lines.extend([f"#if {entry.condition}", row, f"#endif /* {entry.condition} */"])
            else:
                lines.append(row)
        lines.extend(["};", "", "#endif /* DDD_LAYOUT_H */"])
        return [GeneratedFile(output_dir / "ddd_layout.h", "\n".join(lines) + "\n")]


def backend(context: GenerateContext) -> LayoutBackend:
    assert isinstance(context.settings, Settings)
    return LayoutBackend(context.settings, context.generator)


PLUGIN = Plugin(
    name="layout",
    object_model=Entry,
    project_model=Settings,
    checks=(
        CheckInfo("layout/duplicate-key", Severity.ERROR, "two objects claim one key"),
        CheckInfo(
            "layout/key-out-of-range", Severity.ERROR, "a key is above the project's max_key"
        ),
        CheckInfo(
            "layout/version-not-bumped",
            Severity.ERROR,
            "the layout of an entry changed and its version did not increase",
        ),
        CheckInfo(
            "layout/reused-key",
            Severity.ERROR,
            "a key of the baseline now belongs to a different object",
        ),
        CheckInfo(
            "layout/key-changed",
            Severity.ERROR,
            "an object of the baseline carries a different key",
        ),
        CheckInfo(
            "layout/needless-version",
            Severity.WARNING,
            "the version of an entry changed while its layout did not",
        ),
        CheckInfo("layout/removed-entry", Severity.WARNING, "a key of the baseline is gone"),
    ),
    check=check,
    compare=compare,
    backend=backend,
)
