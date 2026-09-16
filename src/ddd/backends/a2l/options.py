"""Options of the a2l backend, and nothing else."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Final


class ByteOrder(StrEnum):
    LITTLE = "little"
    BIG = "big"

    @property
    def a2l(self) -> str:
        return "MSB_LAST" if self is ByteOrder.LITTLE else "MSB_FIRST"


@dataclass(frozen=True, slots=True)
class A2lOptions:
    """Everything the a2l backend lets a project decide."""

    byte_order: ByteOrder = ByteOrder.LITTLE
    version: str = "1 61"
    addresses: dict[str, int] = field(default_factory=dict)
    """Symbol to address map; a symbol that is missing gets address 0."""

    def filename(self, project: str) -> str:
        return f"{project}.a2l"

    def address_of(self, symbol: str) -> str:
        return f"0x{self.addresses.get(symbol, 0):08X}"


ADDRESS_MAX = 0xFFFFFFFF
"""Widest address the ``ECU_ADDRESS`` field of a2l holds: it is an unsigned 32 bit value."""

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

    Every entry is range checked here rather than at formatting time. A negative value would
    otherwise render as ``0x-0000010`` and a wider one as a 33 bit literal, and either makes
    the whole a2l unreadable - from a file that a linker script or a patch tool wrote, where
    a wrong entry is exactly the kind of thing that happens unnoticed.

    Every complaint spells the path forward-slashed, as every path this tool prints is: the
    same message about a description file has always been an ``as_posix()`` one, and a map
    named on the command line of a Windows build came back in the other spelling.
    """
    where = path.as_posix()
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=_no_repeats)
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
        number = value
    else:
        # Stripped first: the grammar is about how the number is written, and a space around
        # one a machine got right is not what it is there to catch.
        text = value.strip()
        if not ADDRESS_PATTERN.match(text):
            msg = (
                f"{where}: address of '{symbol}' is not an integer written in decimal or "
                f"with a '0x' prefix: {value!r}"
            )
            raise ValueError(msg)
        number = int(text, 16 if text.lower().startswith("0x") else 10)
    if not 0 <= number <= ADDRESS_MAX:
        msg = (
            f"{where}: address of '{symbol}' is {number}, outside the range "
            f"0 .. 0x{ADDRESS_MAX:08X} that an a2l address can hold"
        )
        raise ValueError(msg)
    return number
