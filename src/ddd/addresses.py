"""A build's address information: where each symbol of a dictionary sits in the target.

Reading it is core rather than a backend's business: the a2l only consumes the result, and
``SPEC.md`` gives address information a section of its own. Two sources answer the one
question: the map a build writes after the link, ``{"Symbol": "0x20000100"}``, which
:func:`load_address_map` reads, and the linked image itself, whose DWARF
:func:`addresses_from_image` reads through ``ddd.elf`` - objects by name, structure members by
access path. Whether an address fits the field it is written into is the a2l's own question,
which ``ddd.backends.a2l.options.weigh_addresses`` answers for both.

``ddd.elf`` is imported where an image is read and nowhere else: ``generate`` imports this
module on every run, and a broken installation that lacks pyelftools, which the reader needs,
still reads a map.
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from ddd.elf import CType, Image, Variable

ADDRESS_PATTERN: Final = re.compile(r"^(?:0[xX][0-9A-Fa-f]+|[0-9]+)$")
"""The two spellings an address may be written in: ``0x20000100`` or ``536871168``.

The grammar of section 6, rather than python's ``int()``, which the reader used to hand the
text to: that accepts a digit separator (``0x1_0000`` became ``0x00010000``), a leading
``+``, and any Unicode decimal digit at all - the Arabic-Indic ``١٢`` became ``0x0000000C``.
None of those is a spelling anything writes on purpose, and a map is written by a linker
script or a patch tool nobody is looking at, which is the argument for reading exactly what
is documented and refusing the rest.
"""


def load_address_map(path: Path) -> dict[str, int]:
    """Read a ``{"Symbol": "0x20000100"}`` json file produced by the build.

    Read ``utf-8-sig`` for the reason every other file this tool reads is: a build step on
    Windows, or somebody's editor, writes a byte order mark in front of the text, and read as
    plain utf-8 that mark was a json syntax error carrying python's advice to a programmer.

    A symbol stated twice is refused rather than resolved to the last of the two, which is
    what json readers do and what the description loader already refuses: the two addresses
    of one symbol cannot both be right, and the map that carries them was merged from two
    sources or written twice by the same one.

    Every entry is kept as it is written, whatever its value: the documented recipe extracts
    *every* defined symbol of the image (``docs/build_integration.rst``), most of which the a2l
    never states, and those are counted among the entries the a2l does not carry and named in
    the ``address-missing`` note rather than dropped in silence. Which addresses an
    ``ECU_ADDRESS`` must hold is weighed by the a2l backend, for the symbols it carries.

    Every complaint spells the path forward-slashed, as every path this tool prints is: the
    same message about a description file has always been an ``as_posix()`` one, and a map
    named on the command line of a Windows build came back in the other spelling.
    """
    where = path.as_posix()
    try:
        data = json.loads(
            path.read_text(encoding="utf-8-sig"),
            object_pairs_hook=_no_repeats,
            parse_int=_whole,
        )
    except UnicodeDecodeError:
        # What Windows PowerShell's `>` writes is UTF-16, which is where a map written by a
        # build step on Windows most often comes from; python's own words name a byte.
        msg = (
            f"the address map '{where}' is not valid json: it is not UTF-8 text, and Windows "
            "PowerShell's > writes UTF-16; write the map as UTF-8"
        )
        raise ValueError(msg) from None
    except RecursionError:
        msg = (
            f"the address map '{where}' is not valid json: it is nested more deeply than this "
            "tool reads"
        )
        raise ValueError(msg) from None
    except _TooManyDigitsError:
        msg = (
            f"{where}: the address map holds a number of more than "
            f"{sys.get_int_max_str_digits()} digits, which this tool does not read"
        )
        raise ValueError(msg) from None
    except json.JSONDecodeError as error:
        # The bare json message names neither file nor purpose, and this one is typically
        # written by a linker script or a patch tool nobody is looking at.
        msg = f"the address map '{where}' is not valid json: {error}"
        raise ValueError(msg) from None
    except OSError as error:
        # The same reasoning one step earlier: `--address-map nosuch.json` answered
        # `[Errno 2] No such file or directory: 'nosuch.json'`, which names neither the
        # option that asked for the file nor what the run wanted it for.
        msg = f"cannot read the address map '{where}': {error.strerror or error}"
        raise OSError(msg) from None
    except _RepeatedSymbolError as error:
        msg = f"{where}: the address map names '{error.symbol}' twice, with two addresses"
        raise ValueError(msg) from None
    if not isinstance(data, dict):
        msg = f"{where}: expected a json object mapping symbol names to addresses"
        raise ValueError(msg)
    addresses: dict[str, int] = {}
    for symbol, value in data.items():
        addresses[symbol] = _address(where, symbol, value)
    return addresses


class _TooManyDigitsError(ValueError):
    """A number of the map document has more digits than python converts to an integer."""


def _whole(text: str) -> int:
    """The ``parse_int`` of the reader: ``int(text)``, with python's digit limit as an error of
    this module's, which its caller words."""
    try:
        return int(text)
    except ValueError:
        raise _TooManyDigitsError from None


class _RepeatedSymbolError(ValueError):
    """One key of the map document appears twice; raised from inside the json reader."""

    def __init__(self, symbol: str) -> None:
        super().__init__(symbol)
        self.symbol = symbol


def _no_repeats(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """The ``object_pairs_hook`` of the reader: every object of the document, keys unique."""
    seen: dict[str, object] = {}
    for key, value in pairs:
        if key in seen:
            raise _RepeatedSymbolError(key)
        seen[key] = value
    return seen


def _address(where: str, symbol: str, value: object) -> int:
    # "integer" rather than "number" every time: 12.5 is a perfectly good number, and telling
    # its author so would leave the actual rule - an address is a whole number - unsaid.
    if isinstance(value, bool) or not isinstance(value, int | str):
        msg = f"{where}: address of '{symbol}' is not an integer: {value!r}"
        raise ValueError(msg)
    if isinstance(value, int):
        return value
    # Stripped first: the grammar is about how the number is written, and a space around
    # one a machine got right is not what it is there to catch.
    text = value.strip()
    if not ADDRESS_PATTERN.match(text):
        msg = (
            f"{where}: address of '{symbol}' is not an integer written in decimal or "
            f"with a '0x' prefix: {value!r}"
        )
        raise ValueError(msg)
    try:
        return int(text, 16 if text.lower().startswith("0x") else 10)
    except ValueError:
        # The grammar above was met, so only python's digit limit refuses a decimal number.
        msg = (
            f"{where}: address of '{symbol}' has more than {sys.get_int_max_str_digits()} "
            "digits, which this tool does not read"
        )
        raise ValueError(msg) from None


_ROOT: Final = re.compile(r"\w+")
"""The name an access path starts with, the variable's."""
_STEP: Final = re.compile(r"\.(\w+)|\[(\d+)\]")
"""One step of an access path after its name: ``.member``, or ``[index]`` per dimension."""

_UNKNOWN: Final = "where '{}' lies cannot be worked out from the image's debug information"

_WITHOUT_G: Final = (
    "; the symbol table holds it, so the unit defining it was built without debug information (-g)"
)
"""The ending of a reason the symbol table answers: it holds a name whose definition the debug
information does not describe, so the unit defining it was compiled without ``-g``."""

_SPLIT: Final = (
    "; the symbol table holds it, and the debug information of this image is in separate .dwo "
    "files (-gsplit-dwarf), which this tool does not read"
)
"""The same ending for an image whose debug information is split: the unit was built with ``-g``,
and what it describes is in the ``.dwo`` files the image holds a skeleton of."""

_UNTYPED: Final = (
    "the image's debug information gives '{}' no type, as -g1 leaves it, so no path into it can "
    "be followed"
)


@dataclass(frozen=True, slots=True)
class _Absent:
    """The reason a variable has no address when the image holds no definition of it at all."""

    reason: str


@dataclass(frozen=True, slots=True)
class Held:
    """What the image holds of one symbol it places: the variable it is or belongs to, and the
    type its path ends at, which the description is held to."""

    variable: Variable
    """The variable of the image the symbol is, or belongs to."""

    ctype: CType
    """The type the symbol's path ends at: the variable's own for an object, a member's or an
    element's for a path."""

    apart: tuple[Variable, ...] = ()
    """Every unit's description of the variable, where the units do not agree on its size: the
    variable is then one the image describes in two ways, and none of them stands for it."""


@dataclass(frozen=True, slots=True)
class Placed:
    """Where an image puts each symbol it places, and why it places none of the others."""

    addresses: dict[str, int]
    """Every symbol placed, at its address."""

    reasons: dict[str, str]
    """Every symbol not placed, and why, in one sentence naming the part of it that failed."""

    absent: frozenset[str] = frozenset()
    """The symbols of ``reasons`` whose variable the image does not define: no variable of the
    name, no symbol of it, or a declaration alone, as a header's ``extern`` stays where the
    unit that defines the variable removed it. What a build without a feature looks like; the
    other reasons say the image holds the variable, or something of its name."""

    held: dict[str, Held] = field(default_factory=dict, compare=False)
    """What the image holds of every symbol of ``addresses``, for the comparison with the
    description (:mod:`ddd.agreement`). Left out of an equality: it says what the image states,
    where the rest says where, and ``addresses`` are what a caller compares."""


def addresses_from_image(image: Image, symbols: Collection[str]) -> Placed:
    """Place each symbol in ``image``: an object by its name, a member by its access path.

    The variable is the one of that name with external linkage, since every object a dictionary
    describes is a global: a ``static`` of the name never stands for it, and the units that
    describe one variable at one address, as ``-fcommon`` makes them, describe one variable.
    Each step of the path sees through typedefs and qualifiers first; ``.member`` adds the
    member's offset within its structure, and ``[index]``, one per dimension, the index times
    the size of the element, in C's row-major order. The type the path ends at comes back with
    the address, in :attr:`Placed.held`, for the caller to hold to the description.
    """
    named: dict[str, list[Variable]] = {}
    for variable in image.variables:
        named.setdefault(variable.name, []).append(variable)
    addresses: dict[str, int] = {}
    reasons: dict[str, str] = {}
    absent: set[str] = set()
    held: dict[str, Held] = {}
    for symbol in symbols:
        placed = _placed(symbol, image, named)
        if isinstance(placed, tuple):
            addresses[symbol], held[symbol] = placed
        elif isinstance(placed, _Absent):
            reasons[symbol] = placed.reason
            absent.add(symbol)
        else:
            reasons[symbol] = placed
    return Placed(addresses, reasons, frozenset(absent), held)


def _placed(
    symbol: str, image: Image, named: Mapping[str, list[Variable]]
) -> tuple[int, Held] | str | _Absent:
    """The address of ``symbol`` and what the image holds there, or why it gives none."""
    root = _ROOT.match(symbol)
    # The symbols of an a2l are those addressed_symbols lists: an object's identifier, or a
    # member's path, which ddd.analysis writes starting with the variable's identifier.
    assert root is not None
    found = _variable(root.group(), image, named.get(root.group(), []))
    if isinstance(found, str | _Absent):
        return found
    address, variable, apart = found
    reached = _walk(symbol, root.end(), address, variable.type)
    if isinstance(reached, str):
        return reached
    return reached[0], Held(variable, reached[1], apart)


def _variable(
    name: str, image: Image, named: Sequence[Variable]
) -> tuple[int, Variable, tuple[Variable, ...]] | str | _Absent:
    """The address and the variable of the global ``name``, and every description of it where
    the units that describe it disagree on its size, or why the image holds none."""
    from ddd.elf import DECLARED_ONLY, described_apart, without_address

    external = [variable for variable in named if variable.external]
    if not external:
        if named:
            return (
                f"the image holds '{name}' only as a static, and every object a dictionary "
                "describes is a global"
            )
        missing = f"the image's debug information holds no variable named '{name}'"
        if name in image.symbols:
            return missing + _ending(image)
        return _Absent(missing)
    located: dict[int, Variable] = {}
    for variable in external:
        if variable.address is not None:
            located.setdefault(variable.address, variable)
    if not located:
        # A unit compiled with -g and reading the global declares it, where the one defining
        # it, compiled without, describes nothing: the reader keeps the declaration alone.
        if external[0].missing == DECLARED_ONLY and name in image.symbols:
            return f"the image's debug information only declares '{name}'{_ending(image)}"
        reason = without_address(name, external[0].missing)
        # Declared and not defined, with no symbol of the name either: the unit that defines
        # it is not in the image.
        return _Absent(reason) if external[0].missing == DECLARED_ONLY else reason
    if len(located) > 1:
        listed = ", ".join(f"0x{address:X}" for address in sorted(located))
        return f"'{name}' names globals at {len(located)} addresses of the image, {listed}"
    ((address, variable),) = located.items()
    if not image.has_object(name, address):
        return (
            f"the symbol table holds no object named '{name}' at {address:#x}, where its debug "
            "information puts it, as a linker leaves a variable of a unit it discarded"
        )
    if image.section_of(address) is None:
        return image.unheld(name, address)
    apart = described_apart(external, image).get(address, [])
    return address, variable, tuple(apart)


def _ending(image: Image) -> str:
    """Why the symbol table holds a name the debug information does not describe."""
    return _SPLIT if image.split_dwarf else _WITHOUT_G


def _walk(symbol: str, at: int, address: int, ctype: CType) -> tuple[int, CType] | str:
    """``address`` moved along the steps of ``symbol`` from ``at``, with the type it ends at,
    or why it cannot be."""
    from ddd.elf import Array, Struct, Unsupported, core_of, size_of

    while at < len(symbol):
        step = _STEP.match(symbol, at)
        # ddd.analysis writes a member's path as identifiers joined by dots, an index per
        # dimension after an array of structures (_element_paths), and nothing else.
        assert step is not None
        reached = symbol[:at]
        at = step.end()
        core = core_of(ctype)
        if core == Unsupported("void"):
            return _UNTYPED.format(reached)
        member, index = step.groups()
        if member is not None:
            if not isinstance(core, Struct):
                return f"'{reached}' is not a structure, so it has no member named '{member}'"
            found = next((entry for entry in core.members if entry.name == member), None)
            if found is None:
                return f"'{reached}' has no member named '{member}' in the image"
            if found.bit_size is not None:
                return f"'{symbol[:at]}' is a bitfield, which an address cannot describe"
            if found.bit_offset is None:
                return _UNKNOWN.format(symbol[:at])
            address += found.bit_offset // 8
            ctype = found.type
            continue
        position = int(index)
        if not isinstance(core, Array):
            return f"'{reached}' is not an array, so it has no element [{position}]"
        extent, *rest = core.dimensions
        if position >= extent:
            return f"'{reached}' has an extent of {extent}, so it has no element [{position}]"
        element = Array(core.element, tuple(rest)) if rest else core.element
        size = size_of(element)
        if size is None:
            return _UNKNOWN.format(symbol[:at])
        address += position * size
        ctype = element
    return address, ctype
