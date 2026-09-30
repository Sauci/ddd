"""The C variables of a linked ELF image, read from its DWARF debug information.

This module knows nothing of DDD. It imports pyelftools and the standard library and nothing
else, so that reading an address map straight out of an image - planned in section 6 of
``SPEC.md`` - can use it without the toolbox; ``tests/test_backends.py`` holds it to that.

What it offers is a small model of C types - :class:`Base`, :class:`Enum`, :class:`Struct`,
:class:`Array`, :class:`Qualified`, :class:`Typedef` and :class:`Unsupported` - and the
variables of static storage an image holds, each with its type, its address and where its
source declared it. Every variation of DWARF stops here: versions 2 to 5, gcc's spellings and
clang's, compressed sections. A type this module cannot describe becomes an
:class:`Unsupported` node where it occurs rather than an exception, so a caller can name the
place and go on with everything else.

The readers work on two narrow protocols, :class:`Entry` and :class:`Unit`. pyelftools' DIEs
satisfy the first and :class:`_PyelftoolsUnit` the second, and so do a test's doubles: the
branches no C compiler produces are reached that way.
"""

from __future__ import annotations

import io
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Final, Literal, Protocol

from elftools.common.exceptions import DWARFError, ELFError
from elftools.dwarf.dwarf_expr import DWARFExprParser
from elftools.elf.constants import SH_FLAGS
from elftools.elf.elffile import ELFFile
from elftools.elf.sections import SymbolTableSection

DW_ATE_BOOLEAN: Final = 0x02
DW_ATE_COMPLEX_FLOAT: Final = 0x03
DW_ATE_FLOAT: Final = 0x04
DW_ATE_SIGNED: Final = 0x05
DW_ATE_SIGNED_CHAR: Final = 0x06
DW_ATE_UNSIGNED: Final = 0x07
DW_ATE_UNSIGNED_CHAR: Final = 0x08

SIGNED_ENCODINGS: Final = frozenset({DW_ATE_SIGNED, DW_ATE_SIGNED_CHAR})

DECLARED_ONLY: Final = "it is only declared here, and defined nowhere in the image"
FOLDED: Final = "the compiler replaced it by its value, and gave it no storage"
REMOVED: Final = "the compiler removed its storage"
THREAD_LOCAL: Final = "it is thread-local, with an address of its own in every thread"
NOT_AN_ADDRESS: Final = "its location is not a fixed address"

_DW_OP_PLUS_UCONST: Final = 0x23
_TLS_OPERATIONS: Final = frozenset({"DW_OP_form_tls_address", "DW_OP_GNU_push_tls_address"})
_DATA_WIDTHS: Final = {
    "DW_FORM_data1": 8,
    "DW_FORM_data2": 16,
    "DW_FORM_data4": 32,
    "DW_FORM_data8": 64,
}
"""The forms whose constant carries no sign of its own, by width in bits: an enumerator of a
signed enum written in one of them is sign-extended from that width."""

_UNSUPPORTED: Final = {
    "DW_TAG_pointer_type": "a pointer",
    "DW_TAG_union_type": "a union",
    "DW_TAG_class_type": "a class",
    "DW_TAG_reference_type": "a reference",
    "DW_TAG_rvalue_reference_type": "a reference",
    "DW_TAG_subroutine_type": "a function",
    "DW_TAG_ptr_to_member_type": "a pointer to member",
    "DW_TAG_atomic_type": "an _Atomic type",
    "DW_TAG_unspecified_type": "an unspecified type",
}


class ElfReadError(ValueError):
    """An image this module cannot read at all; the message names the file and says why."""


@dataclass(frozen=True, slots=True)
class Declared:
    """Where a source declared something: the file as DWARF names it, and the line."""

    path: str
    line: int


@dataclass(frozen=True, slots=True)
class Base:
    """A base type: DWARF's spelling of it, its ``DW_ATE_*`` encoding and its size in bytes."""

    name: str
    encoding: int
    size: int


@dataclass(frozen=True, slots=True)
class Enum:
    """An enumeration: its tag, if it has one, its size, its sign and its enumerators in order."""

    tag: str | None
    size: int
    signed: bool
    enumerators: tuple[tuple[str, int], ...]
    declared_at: Declared | None = None


@dataclass(frozen=True, slots=True)
class Member:
    """One member of a structure, where it starts in bits, and its width if it is a bitfield."""

    name: str | None
    type: CType
    bit_offset: int | None
    """From the start of the structure; None where DWARF gives an offset this module cannot
    read, which only the layout warnings of a caller need."""

    bit_size: int | None = None
    alignment: int | None = None
    declared_at: Declared | None = None


@dataclass(frozen=True, slots=True)
class Struct:
    """A structure: its tag, if it has one, its size, its members in declaration order."""

    tag: str | None
    size: int
    members: tuple[Member, ...]
    alignment: int | None = None
    declared_at: Declared | None = None


@dataclass(frozen=True, slots=True)
class Array:
    """An array of ``element``, one extent per dimension in C order."""

    element: CType
    dimensions: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class Qualified:
    """``const`` or ``volatile`` on ``inner``; DWARF states each as an entry of its own."""

    inner: CType
    const: bool = False
    volatile: bool = False


@dataclass(frozen=True, slots=True)
class Typedef:
    """A typedef: its name, and the type it stands for."""

    name: str
    inner: CType


@dataclass(frozen=True, slots=True)
class Unsupported:
    """A type this module does not describe, ``what`` saying which, as "a pointer" does."""

    what: str


type CType = Base | Enum | Struct | Array | Qualified | Typedef | Unsupported


@dataclass(frozen=True, slots=True)
class Variable:
    """A variable of static storage a unit's DWARF describes at its top level."""

    name: str
    unit: str
    type: CType
    declared_at: Declared | None = None
    address: int | None = None
    missing: str = ""
    """Why ``address`` is None, as one of the constants of this module says it."""


@dataclass(frozen=True, slots=True)
class Section:
    """An allocated section: where it lies in memory, and where its bytes start in the file."""

    name: str
    address: int
    size: int
    offset: int | None
    """None for a section without contents (``SHT_NOBITS``), whose bytes the startup code
    provides rather than the image."""


@dataclass(frozen=True, slots=True)
class Image:
    """What a linked ELF image says about its C variables; :func:`open_image` fills it."""

    path: Path
    byte_order: Literal["little", "big"]
    variables: tuple[Variable, ...]
    sections: tuple[Section, ...]
    """The allocated sections, the thread-local ones left out: their addresses are offsets
    into a thread's block, and they overlap the sections that follow them in memory."""

    symbols: frozenset[str]
    """The names of the object symbols of the symbol table."""

    contents: bytes

    def section_of(self, address: int) -> Section | None:
        """The section holding ``address``, or None where none does."""
        for section in self.sections:
            if section.address <= address < section.address + section.size:
                return section
        return None

    def read(self, address: int, size: int) -> bytes | None:
        """The ``size`` bytes at ``address``, or None where the image does not hold them."""
        section = self.section_of(address)
        if section is None or section.offset is None:
            return None
        if address + size > section.address + section.size:
            return None
        start = section.offset + address - section.address
        return self.contents[start : start + size]


class Entry(Protocol):
    """What the readers ask of a DWARF entry. pyelftools' ``DIE`` is one."""

    @property
    def tag(self) -> str | int | None: ...

    @property
    def offset(self) -> int: ...

    @property
    def attributes(self) -> Mapping[str, Any]: ...

    def iter_children(self) -> Iterator[Entry]: ...

    def get_DIE_from_attribute(self, name: str) -> Entry: ...  # noqa: N802 - pyelftools' name


class Unit(Protocol):
    """What the variable reader asks of a compilation unit."""

    @property
    def name(self) -> str: ...

    @property
    def top(self) -> Entry: ...

    def operations(self, expression: Sequence[int]) -> list[tuple[str, list[Any]]]:
        """A location expression, as ``(operation name, arguments)`` pairs."""
        ...

    def indexed_address(self, index: int) -> int:
        """The address ``.debug_addr`` holds at ``index`` for this unit."""
        ...

    def file(self, index: int) -> str | None:
        """The path ``DW_AT_decl_file`` ``index`` names, or None where the table has none."""
        ...


@dataclass(frozen=True, slots=True)
class FileTable:
    """A unit's file table, as plain data: the entries, the directories and the unit's own
    directory, whose meaning depends on the DWARF version."""

    version: int
    files: tuple[tuple[str, int], ...]
    """Each file's name and the index of its directory."""

    directories: tuple[str, ...]
    compilation_directory: str


def file_path(table: FileTable | None, index: int) -> str | None:
    """The path a ``DW_AT_decl_file`` names, forward-slashed; None where the table has none.

    DWARF 5 counts files from 0, and its directory 0 is the compilation directory itself.
    Versions 2 to 4 count files from 1, with 0 meaning no file, and a directory index of 0
    meaning the unit's ``DW_AT_comp_dir``.
    """
    if table is None:
        return None
    if table.version >= 5:
        position = index
        directories = table.directories
    else:
        position = index - 1
        directories = (table.compilation_directory, *table.directories)
    if not 0 <= position < len(table.files):
        return None
    name, directory_index = table.files[position]
    name = name.replace("\\", "/")
    if name.startswith("/") or PureWindowsPath(name).is_absolute():
        return name
    directory = ""
    if 0 <= directory_index < len(directories):
        directory = directories[directory_index].replace("\\", "/")
    return str(PurePosixPath(directory, name))


def size_of(ctype: CType) -> int | None:
    """The size of ``ctype`` in bytes, or None for a type this module does not describe."""
    if isinstance(ctype, Base | Enum | Struct):
        return ctype.size
    if isinstance(ctype, Qualified | Typedef):
        return size_of(ctype.inner)
    if isinstance(ctype, Array):
        element = size_of(ctype.element)
        if element is None:
            return None
        count = 1
        for extent in ctype.dimensions:
            count *= extent
        return element * count
    return None


def read_variables(
    units: Iterable[Unit], *, big_endian: bool, thread_local: frozenset[str] = frozenset()
) -> tuple[Variable, ...]:
    """The variables at the top of every unit, each with its type, address and declaration.

    A name that is only ever declared is kept, as a variable without storage, so that a
    caller asking for it can say why it is not there; a name that some unit defines drops
    every declaration of it. ``thread_local`` names the thread-local symbols of the image: a
    target whose DWARF cannot state a thread-local address gives such a variable no location
    at all, and only the symbol table still says what it is.
    """
    types = _Types(big_endian=big_endian)
    defined: list[Variable] = []
    declared: dict[str, Variable] = {}
    for unit in units:
        for entry in unit.top.iter_children():
            if entry.tag != "DW_TAG_variable":
                continue
            variable = _variable(entry, unit, types, thread_local)
            if variable is None:
                continue
            if variable.missing == DECLARED_ONLY:
                declared.setdefault(variable.name, variable)
                continue
            defined.append(variable)
    names = {variable.name for variable in defined}
    defined.extend(variable for name, variable in declared.items() if name not in names)
    return tuple(defined)


def open_image(path: Path) -> Image:
    """Read a linked ELF image and its DWARF; :class:`ElfReadError` says why one cannot be."""
    shown = path.as_posix()
    try:
        contents = path.read_bytes()
    except OSError as error:
        msg = f"cannot read '{shown}': {error.strerror}"
        raise ElfReadError(msg) from None
    try:
        return _image(path, contents)
    except (ELFError, DWARFError) as error:
        msg = f"'{shown}' is not an ELF image this tool can read: {error}"
        raise ElfReadError(msg) from None


def _image(path: Path, contents: bytes) -> Image:
    shown = path.as_posix()
    elf = ELFFile(io.BytesIO(contents))
    kind = elf.header["e_type"]
    if kind == "ET_REL":
        msg = (
            f"'{shown}' is a relocatable object, not a linked image: its addresses and its "
            f"initial values are not final until it is linked"
        )
        raise ElfReadError(msg)
    if kind not in ("ET_EXEC", "ET_DYN"):
        msg = f"'{shown}' is an ELF file of type {kind}, not a linked image"
        raise ElfReadError(msg)
    if not elf.has_dwarf_info(strict=True):
        msg = f"'{shown}' carries no DWARF debug information: build it with -g"
        raise ElfReadError(msg)
    sections = _sections(elf)
    for section in sections:
        if section.offset is not None and section.offset + section.size > len(contents):
            msg = (
                f"'{shown}' is not an ELF image this tool can read: its section "
                f"'{section.name}' runs past the end of the file"
            )
            raise ElfReadError(msg)
    dwarf = elf.get_dwarf_info(relocate_dwarf_sections=False, follow_links=False)
    units = [_PyelftoolsUnit(cu, dwarf) for cu in dwarf.iter_CUs()]
    variables = read_variables(
        units, big_endian=not elf.little_endian, thread_local=_symbols(elf, "STT_TLS")
    )
    return Image(
        path=path,
        byte_order="little" if elf.little_endian else "big",
        variables=variables,
        sections=sections,
        symbols=_symbols(elf, "STT_OBJECT"),
        contents=contents,
    )


def _sections(elf: ELFFile) -> tuple[Section, ...]:
    sections: list[Section] = []
    for section in elf.iter_sections():
        flags = section["sh_flags"]
        if not flags & SH_FLAGS.SHF_ALLOC or flags & SH_FLAGS.SHF_TLS:
            continue
        offset = None if section["sh_type"] == "SHT_NOBITS" else section["sh_offset"]
        sections.append(Section(section.name, section["sh_addr"], section["sh_size"], offset))
    return tuple(sections)


def _symbols(elf: ELFFile, kind: str) -> frozenset[str]:
    """The names of the symbols of type ``kind`` (``STT_OBJECT``, ``STT_TLS``) in any table."""
    names: set[str] = set()
    for section in elf.iter_sections():
        if isinstance(section, SymbolTableSection):
            names.update(
                symbol.name
                for symbol in section.iter_symbols()
                if symbol["st_info"]["type"] == kind
            )
    return frozenset(names)


class _PyelftoolsUnit:
    """A pyelftools compilation unit, as :class:`Unit` asks for one."""

    def __init__(self, cu: Any, dwarf: Any) -> None:
        self._cu = cu
        self._dwarf = dwarf
        self._parser = DWARFExprParser(cu.structs)
        self.top: Entry = cu.get_top_DIE()
        self.name = _text(self.top.attributes.get("DW_AT_name")) or ""
        self._files = file_table(
            dwarf.line_program_for_CU(cu), _text(self.top.attributes.get("DW_AT_comp_dir")) or ""
        )

    def operations(self, expression: Sequence[int]) -> list[tuple[str, list[Any]]]:
        return [(op.op_name, list(op.args)) for op in self._parser.parse_expr(expression)]

    def indexed_address(self, index: int) -> int:
        return int(self._dwarf.get_addr(self._cu, index))

    def file(self, index: int) -> str | None:
        return file_path(self._files, index)


def file_table(program: Any, compilation_directory: str) -> FileTable | None:
    """A pyelftools line program's file table as plain data; None for a unit without one."""
    if program is None:
        return None
    return FileTable(
        version=int(program["version"]),
        files=tuple(
            (_decoded(entry.name), int(entry.dir_index)) for entry in program["file_entry"]
        ),
        directories=tuple(_decoded(directory) for directory in program["include_directory"]),
        compilation_directory=compilation_directory,
    )


def _variable(
    entry: Entry, unit: Unit, types: _Types, thread_local: frozenset[str]
) -> Variable | None:
    named = entry
    if "DW_AT_specification" in entry.attributes:
        named = entry.get_DIE_from_attribute("DW_AT_specification")
    name = _text(named.attributes.get("DW_AT_name"))
    if name is None:
        return None
    ctype = types.inner(named, unit)
    declared_at = _declared(entry, named, unit)
    attributes = entry.attributes
    address: int | None = None
    missing = ""
    if "DW_AT_location" in attributes:
        address, missing = _address(attributes["DW_AT_location"].value, unit)
    elif "DW_AT_const_value" in attributes:
        missing = FOLDED
    elif "DW_AT_declaration" in attributes:
        missing = DECLARED_ONLY
    elif name in thread_local:
        # aarch64's gcc 14 and clang 19 state no location at all for a thread-local variable
        # (the trial build); its symbol, of type STT_TLS, still says what it is.
        missing = THREAD_LOCAL
    else:
        missing = REMOVED
    return Variable(name, unit.name, ctype, declared_at, address, missing)


def _address(value: Any, unit: Unit) -> tuple[int | None, str]:
    if not isinstance(value, list):
        return None, NOT_AN_ADDRESS
    operations = unit.operations(value)
    names = [name for name, _ in operations]
    if names and names[-1] in _TLS_OPERATIONS:
        return None, THREAD_LOCAL
    if names == ["DW_OP_addr"]:
        return int(operations[0][1][0]), ""
    if names == ["DW_OP_addrx"]:
        return unit.indexed_address(int(operations[0][1][0])), ""
    return None, NOT_AN_ADDRESS


def _declared(entry: Entry, named: Entry, unit: Unit) -> Declared | None:
    """Where a variable is declared: the definition's own line and file where it states them,
    else those of the declaration it completes."""
    line = _either(entry, named, "DW_AT_decl_line")
    index = _either(entry, named, "DW_AT_decl_file")
    if not isinstance(line, int) or not isinstance(index, int):
        return None
    path = unit.file(index)
    if path is None:
        return None
    return Declared(path, line)


class _Types:
    """C types out of DWARF entries, each entry built once."""

    def __init__(self, *, big_endian: bool) -> None:
        self._big_endian = big_endian
        self._built: dict[int, CType] = {}

    def of(self, entry: Entry, unit: Unit) -> CType:
        built = self._built.get(entry.offset)
        if built is None:
            built = self._build(entry, unit)
            self._built[entry.offset] = built
        return built

    def inner(self, entry: Entry, unit: Unit) -> CType:
        """The type ``entry``'s ``DW_AT_type`` names; C's ``void`` where it names none."""
        if "DW_AT_type" not in entry.attributes:
            return Unsupported("void")
        return self.of(entry.get_DIE_from_attribute("DW_AT_type"), unit)

    def _build(self, entry: Entry, unit: Unit) -> CType:
        tag = entry.tag
        if tag == "DW_TAG_base_type":
            return Base(
                _text(entry.attributes.get("DW_AT_name")) or "",
                int(_value(entry, "DW_AT_encoding")),
                int(_value(entry, "DW_AT_byte_size")),
            )
        if tag == "DW_TAG_typedef":
            return Typedef(_text(entry.attributes.get("DW_AT_name")) or "", self.inner(entry, unit))
        if tag == "DW_TAG_const_type":
            return Qualified(self.inner(entry, unit), const=True)
        if tag == "DW_TAG_volatile_type":
            return Qualified(self.inner(entry, unit), volatile=True)
        if tag == "DW_TAG_restrict_type":
            # restrict qualifies a pointer only, and a pointer is refused whatever qualifies it.
            return self.inner(entry, unit)
        if tag == "DW_TAG_array_type":
            return self._array(entry, unit)
        if tag == "DW_TAG_enumeration_type":
            return self._enum(entry, unit)
        if tag == "DW_TAG_structure_type":
            return self._struct(entry, unit)
        return Unsupported(_UNSUPPORTED.get(str(tag), f"a type DWARF tags {tag}"))

    def _array(self, entry: Entry, unit: Unit) -> CType:
        dimensions: list[int] = []
        for child in entry.iter_children():
            if child.tag != "DW_TAG_subrange_type":
                continue
            extent = _extent(child)
            if extent is None or extent < 1:
                return Unsupported("an array without a fixed size of at least one element")
            dimensions.append(extent)
        if not dimensions:
            return Unsupported("an array without a fixed size of at least one element")
        return Array(self.inner(entry, unit), tuple(dimensions))

    def _enum(self, entry: Entry, unit: Unit) -> CType:
        if "DW_AT_declaration" in entry.attributes:
            return Unsupported("an enum declared but never defined")
        children = [child for child in entry.iter_children() if child.tag == "DW_TAG_enumerator"]
        signed = self._signed(entry, children, unit)
        return Enum(
            tag=_text(entry.attributes.get("DW_AT_name")),
            size=int(_value(entry, "DW_AT_byte_size")),
            signed=signed,
            enumerators=tuple(_enumerator(child, signed=signed) for child in children),
            declared_at=_declared(entry, entry, unit),
        )

    def _signed(self, entry: Entry, children: Sequence[Entry], unit: Unit) -> bool:
        """An enum's sign: its underlying type's, else its encoding's, else whether an
        enumerator is negative - which an old producer states and nothing else."""
        if "DW_AT_type" in entry.attributes:
            underlying = _core(self.inner(entry, unit))
            if isinstance(underlying, Base):
                return underlying.encoding in SIGNED_ENCODINGS
        encoding = _value(entry, "DW_AT_encoding")
        if isinstance(encoding, int):
            return encoding in SIGNED_ENCODINGS
        for child in children:
            attribute = child.attributes["DW_AT_const_value"]
            if attribute.form == "DW_FORM_sdata" and attribute.value < 0:
                return True
        return False

    def _struct(self, entry: Entry, unit: Unit) -> CType:
        if "DW_AT_declaration" in entry.attributes:
            return Unsupported("a structure declared but never defined")
        members = tuple(
            self._member(child, unit)
            for child in entry.iter_children()
            if child.tag == "DW_TAG_member"
        )
        return Struct(
            tag=_text(entry.attributes.get("DW_AT_name")),
            size=int(_value(entry, "DW_AT_byte_size")),
            members=members,
            alignment=_value(entry, "DW_AT_alignment"),
            declared_at=_declared(entry, entry, unit),
        )

    def _member(self, entry: Entry, unit: Unit) -> Member:
        ctype = self.inner(entry, unit)
        bit_size = _value(entry, "DW_AT_bit_size")
        return Member(
            name=_text(entry.attributes.get("DW_AT_name")),
            type=ctype,
            bit_offset=self._bit_offset(entry, ctype, bit_size),
            bit_size=bit_size,
            alignment=_value(entry, "DW_AT_alignment"),
            declared_at=_declared(entry, entry, unit),
        )

    def _bit_offset(self, entry: Entry, ctype: CType, bit_size: int | None) -> int | None:
        """Where a member starts, in bits from the start of its structure.

        DWARF 4 and later may state it outright. Before that, a bitfield states the byte its
        storage unit starts at, the unit's size, and its offset inside the unit counted from
        the unit's most significant bit - so from its first byte on a big endian target and
        from its last on a little endian one.
        """
        data_bit_offset = _value(entry, "DW_AT_data_bit_offset")
        if isinstance(data_bit_offset, int):
            return data_bit_offset
        location = _member_location(entry)
        if location is None:
            return None
        old = _value(entry, "DW_AT_bit_offset")
        if not isinstance(old, int) or bit_size is None:
            return location * 8
        storage = _value(entry, "DW_AT_byte_size")
        if not isinstance(storage, int):
            storage = size_of(ctype) or 0
        if self._big_endian:
            return location * 8 + old
        return location * 8 + storage * 8 - old - bit_size


def _member_location(entry: Entry) -> int | None:
    attribute = entry.attributes.get("DW_AT_data_member_location")
    if attribute is None:
        return 0
    value = attribute.value
    if isinstance(value, int):
        return value
    if isinstance(value, list) and len(value) >= 2 and value[0] == _DW_OP_PLUS_UCONST:
        return _uleb128(value[1:])
    return None


def _uleb128(data: Sequence[int]) -> int:
    result = 0
    for shift, byte in enumerate(data):
        result |= (byte & 0x7F) << (7 * shift)
        if not byte & 0x80:
            break
    return result


def _extent(entry: Entry) -> int | None:
    count = _value(entry, "DW_AT_count")
    if isinstance(count, int):
        return count
    upper = _value(entry, "DW_AT_upper_bound")
    lower = _value(entry, "DW_AT_lower_bound")
    if lower is None:
        lower = 0
    if not isinstance(upper, int) or not isinstance(lower, int):
        return None
    return upper - lower + 1


def _enumerator(entry: Entry, *, signed: bool) -> tuple[str, int]:
    attribute = entry.attributes["DW_AT_const_value"]
    value = int(attribute.value)
    width = _DATA_WIDTHS.get(attribute.form)
    if signed and width is not None and value >= 1 << (width - 1):
        value -= 1 << width
    return _text(entry.attributes.get("DW_AT_name")) or "", value


def _core(ctype: CType) -> CType:
    while isinstance(ctype, Qualified | Typedef):
        ctype = ctype.inner
    return ctype


def _either(first: Entry, second: Entry, name: str) -> Any:
    if name in first.attributes:
        return first.attributes[name].value
    return _value(second, name)


def _value(entry: Entry, name: str) -> Any:
    attribute = entry.attributes.get(name)
    if attribute is None:
        return None
    return attribute.value


def _text(attribute: Any) -> str | None:
    if attribute is None:
        return None
    return _decoded(attribute.value)


def _decoded(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)
