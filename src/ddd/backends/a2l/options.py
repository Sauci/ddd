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


def load_address_map(path: Path) -> dict[str, int]:
    """Read a ``{"Symbol": "0x20000100"}`` json file produced by the build."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        msg = f"{path}: expected a json object mapping symbol names to addresses"
        raise ValueError(msg)
    addresses: dict[str, int] = {}
    for symbol, value in data.items():
        if isinstance(value, bool) or not isinstance(value, int | str):
            msg = f"{path}: address of '{symbol}' is not a number: {value!r}"
            raise ValueError(msg)
        if isinstance(value, int):
            addresses[symbol] = value
            continue
        text = value.strip()
        base = 16 if text.lower().startswith(("0x", "-0x")) else 10
        try:
            addresses[symbol] = int(text, base)
        except ValueError:
            msg = f"{path}: address of '{symbol}' is not a number: {value!r}"
            raise ValueError(msg) from None
    return addresses
