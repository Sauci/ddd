"""Options of the a2l backend, and the range of the addresses it states."""

from __future__ import annotations

import re
from collections.abc import Collection, Mapping
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
class ModuleFragment:
    """A project's own text for the head of the a2l's ``MODULE``, and the file it was read from."""

    where: str
    """The file, spelled forward-slashed as every path this tool prints is."""

    text: str

    @property
    def holds_a_mod_par(self) -> bool:
        """Whether the text opens a ``MOD_PAR``, which a comment or a string naming one does not."""
        return _MOD_PAR.search(_ONLY_TEXT.sub(" ", self.text)) is not None


_ONLY_TEXT: Final = re.compile(r'"(?:[^"\\]|\\.)*"|/\*.*?\*/|//[^\n]*', re.DOTALL)
"""A string, or a comment of either spelling: the places ``/begin MOD_PAR`` is only text. The
strings are matched so that a ``//`` inside one is not taken for a comment."""

_MOD_PAR: Final = re.compile(r"/begin\s+MOD_PAR\b")


def load_module_fragment(path: Path) -> ModuleFragment:
    """Read the file ``--a2l-module-fragment`` names.

    Read ``utf-8-sig`` for the reason the address map is: an editor on Windows writes a byte
    order mark in front of the text, and the a2l carries exactly one of its own. A file that is
    not UTF-8 text, or that cannot be read, is refused naming it, in the words the address map
    is refused in, and never in Python's own.
    """
    where = path.as_posix()
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        msg = (
            f"the a2l module fragment '{where}' is not UTF-8 text, and Windows PowerShell's > "
            "writes UTF-16; write the fragment as UTF-8"
        )
        raise ValueError(msg) from None
    except OSError as error:
        msg = f"cannot read the a2l module fragment '{where}': {error.strerror or error}"
        raise OSError(msg) from None
    return ModuleFragment(where, text)


@dataclass(frozen=True, slots=True)
class A2lOptions:
    """Everything the a2l backend lets a project decide."""

    byte_order: ByteOrder = ByteOrder.LITTLE
    version: str = "1 61"
    addresses: dict[str, int] = field(default_factory=dict)
    """Symbol to address map; a symbol that is missing gets address 0."""

    links: dict[str, tuple[str, int]] = field(default_factory=dict)
    """Symbol to the linker symbol it lies in and its byte offset from it, as the linked image
    placed it (``Placed.links``): ``Inlet.latest.value`` is ``("Inlet", 8)``. A map gives a
    symbol's address and nothing of a member's offset, so only an image states one; a symbol
    that is missing names itself at offset 0."""

    has_address_source: bool = False
    """Whether the run had a source of addresses: the linked image, or an address map with an
    entry. Without one every address is 0 and no ``address-missing`` says so, an empty map
    naming nothing to miss, and ``--strict`` does not fail it, so the file says it itself,
    under its version."""

    left_out: frozenset[str] = frozenset()
    """The symbols of the objects the build compiled out, which the a2l does not write: each
    states a condition, and the image defines none of it or the map names none of it. A curve
    or a map over an axis among them goes too, since its reference would name a record the
    file lacks; an axis whose input is among them is written indexed by nothing."""

    module_fragment: ModuleFragment | None = None
    """What the project pastes at the head of the ``MODULE``: the ``A2ML`` its ``IF_DATA`` are
    written in, a module level ``IF_DATA``, and in a project that declares no named constant
    the ``MOD_PAR`` carrying ``EPK``, ``ADDR_EPK`` and ``MEMORY_SEGMENT``. ddd models none of it."""

    def filename(self, project: str) -> str:
        return f"{project}.a2l"

    def link_of(self, symbol: str) -> tuple[str, int]:
        """What ``SYMBOL_LINK`` states for ``symbol``: the linker symbol and the offset from it.

        The image's, where it placed the symbol. Otherwise the symbol's own name at offset 0,
        which for a variable that is not a member is the right answer and for a member is the
        path no map holds: DDD cannot state the member's offset without predicting a layout
        only the image knows.
        """
        return self.links.get(symbol, (symbol, 0))

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
