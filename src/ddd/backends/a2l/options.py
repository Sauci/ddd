"""Options of the a2l backend, and nothing else."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


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


def load_address_map(path: Path) -> dict[str, int]:
    """Read a ``{"Symbol": "0x20000100"}`` json file produced by the build.

    Every entry is range checked here rather than at formatting time. A negative value would
    otherwise render as ``0x-0000010`` and a wider one as a 33 bit literal, and either makes
    the whole a2l unreadable - from a file that a linker script or a patch tool wrote, where
    a wrong entry is exactly the kind of thing that happens unnoticed.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        # The bare json message names neither file nor purpose, and this one is typically
        # written by a linker script or a patch tool nobody is looking at.
        msg = f"the address map '{path}' is not valid json: {error}"
        raise ValueError(msg) from None
    if not isinstance(data, dict):
        msg = f"{path}: expected a json object mapping symbol names to addresses"
        raise ValueError(msg)
    addresses: dict[str, int] = {}
    for symbol, value in data.items():
        addresses[symbol] = _address(path, symbol, value)
    return addresses


def _address(path: Path, symbol: str, value: object) -> int:
    # "integer" rather than "number" both times: 12.5 is a perfectly good number, and telling
    # its author so would leave the actual rule - an address is a whole number - unsaid.
    if isinstance(value, bool) or not isinstance(value, int | str):
        msg = f"{path}: address of '{symbol}' is not an integer: {value!r}"
        raise ValueError(msg)
    if isinstance(value, int):
        number = value
    else:
        text = value.strip()
        base = 16 if text.lower().startswith(("0x", "-0x")) else 10
        try:
            number = int(text, base)
        except ValueError:
            msg = f"{path}: address of '{symbol}' is not an integer: {value!r}"
            raise ValueError(msg) from None
    if not 0 <= number <= ADDRESS_MAX:
        msg = (
            f"{path}: address of '{symbol}' is {number}, outside the range "
            f"0 .. 0x{ADDRESS_MAX:08X} that an a2l address can hold"
        )
        raise ValueError(msg)
    return number
