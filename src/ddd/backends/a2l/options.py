"""Options of the a2l backend, and the range of the addresses it states."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
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


ADDRESS_MAX: Final = 0xFFFFFFFF
"""Widest address the ``ECU_ADDRESS`` field of a2l holds: it is an unsigned 32 bit value."""


def weigh_addresses(addresses: Mapping[str, int], carried: Collection[str], where: str) -> None:
    """Refuse an address the a2l would state that its ``ECU_ADDRESS`` cannot hold.

    Only the symbols ``carried`` names are weighed - the ones the a2l states an
    ``ECU_ADDRESS`` for. For one of those, a negative value would render as ``0x-0000010`` and
    a wider one as a 33 bit literal, either of which makes the whole a2l unreadable, so it is a
    usage error naming the symbol and ``where`` its address came from. Every other address is
    never formatted at all: the documented recipe extracts *every* defined symbol of the image
    (``docs/build_integration.rst``), which on a 64 bit host means a hundred entries of the c
    runtime sitting above 4 GB, and refusing those made the two-run flow impossible to
    complete on the very host the page tells the reader to try it on.

    The first symbol out of range is named, in the order of ``addresses``.
    """
    # A set rather than the tuple the a2l lists them in: every entry of a map is looked up,
    # and the recipe's map holds every symbol of the image (measured, 0.27 s against a tuple
    # of 5000 symbols for 25000 entries, 0.5 ms against a set).
    weighed = frozenset(carried)
    for symbol, address in addresses.items():
        if symbol in weighed and not 0 <= address <= ADDRESS_MAX:
            msg = (
                f"{where}: address of '{symbol}' is {address}, outside the range "
                f"0 .. 0x{ADDRESS_MAX:08X} that an a2l address can hold"
            )
            raise ValueError(msg)
