"""The C variables of a linked ELF image, read from its DWARF debug information.

This module knows nothing of DDD. It imports pyelftools and the standard library and nothing
else, so that :mod:`ddd.addresses`, which places the symbols of an a2l in an image (section 6
of ``SPEC.md``), reads images with it without the toolbox; ``tests/test_backends.py`` holds
it to that.

What it offers is a small model of C types - :class:`Base`, :class:`Enum`, :class:`Struct`,
:class:`Array`, :class:`Qualified`, :class:`Typedef` and :class:`Unsupported` - and the
variables of static storage an image holds, each with its type, its address and where its
source declared it. The DWARF it reads is versions 2 to 5 as gcc and clang write them,
compressed with zlib; an image it cannot read - type units, gcc's link-time optimisation, zstd,
no program contents - is refused with a message naming why. A type this module cannot describe
becomes an :class:`Unsupported` node where it occurs rather than an exception, so a caller can
name the place and go on with everything else. It is for the C that gcc and clang write, and a
C++ shape it would describe wrongly - a base class, a static member, a variable of a namespace -
is refused where it occurs.

The readers work on two narrow protocols, :class:`Entry` and :class:`Unit`. pyelftools' DIEs
satisfy the first and :class:`_PyelftoolsUnit` the second, and so do a test's doubles: the
branches no C compiler produces are reached that way.
"""

from __future__ import annotations

import io
import re
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Final, Literal, Protocol, cast, overload

import elftools
from elftools.common.exceptions import DWARFError, ELFError
from elftools.common.utils import struct_parse
from elftools.dwarf.dwarf_expr import DWARFExprParser
from elftools.dwarf.enums import DW_FORM_raw2name
from elftools.elf.constants import SH_FLAGS
from elftools.elf.elffile import ELFFile
from elftools.elf.enums import ENUM_E_MACHINE
from elftools.elf.sections import SymbolTableSection

DW_ATE_BOOLEAN: Final = 0x02
DW_ATE_COMPLEX_FLOAT: Final = 0x03
DW_ATE_FLOAT: Final = 0x04
DW_ATE_SIGNED: Final = 0x05
DW_ATE_SIGNED_CHAR: Final = 0x06
DW_ATE_UNSIGNED: Final = 0x07
DW_ATE_UNSIGNED_CHAR: Final = 0x08

_SIGNED_ENCODINGS: Final = frozenset({DW_ATE_SIGNED, DW_ATE_SIGNED_CHAR})

DECLARED_ONLY: Final = "it is only declared here, and defined nowhere in the image"
FOLDED: Final = "the compiler replaced it by its value, and gave it no storage"
REMOVED: Final = "the compiler removed its storage"
THREAD_LOCAL: Final = "it is thread-local, with an address of its own in every thread"
NOT_AN_ADDRESS: Final = "its location is not a fixed address"
DISCARDED: Final = "the linker discarded its storage"
WITHOUT_G: Final = (
    "; the symbol table holds it, so the unit defining it was built without debug information (-g)"
)
"""The ending of a reason the symbol table answers: it holds a name whose definition the debug
information does not describe, so the unit defining it was compiled without ``-g``."""
SPLIT: Final = (
    "; the symbol table holds it, and the debug information of this image is in separate .dwo "
    "files (-gsplit-dwarf), which this tool does not read"
)
"""The same ending for an image whose debug information is split: the unit was built with ``-g``,
and what it describes is in the ``.dwo`` files the image holds a skeleton of."""
OTHER_SCOPE: Final = (
    "a variable of a C++ namespace or class, which DDD does not read: it reads C, and a "
    "short name does not say which one it is"
)

_PYELFTOOLS_FLOOR: Final = (0, 32)
"""The oldest pyelftools this reader reads with: 0.32 is the first whose ``has_dwarf_info``
takes ``strict``. An older one still imports, and every image then raised a ``TypeError`` -
which the refusal of a damaged image named as the image's fault (seen on a maintainer's venv
holding 0.31 from before ddd was installed)."""

_DW_OP_PLUS_UCONST: Final = 0x23
_CONTROL: Final = re.compile(r"[\x00-\x1f\x7f-\x9f]")
"""The control characters, C0, DEL and C1."""
_ELFCOMPRESS_ZSTD: Final = 2
_LTO_PRODUCER: Final = "GNU GIMPLE"
"""The producer gcc names in the units its link-time optimisation writes, as ``GNU GIMPLE
15.2.0``."""
_TLS_OPERATIONS: Final = frozenset({"DW_OP_form_tls_address", "DW_OP_GNU_push_tls_address"})
_DATA_WIDTHS: Final = {
    "DW_FORM_data1": 8,
    "DW_FORM_data2": 16,
    "DW_FORM_data4": 32,
    "DW_FORM_data8": 64,
}
"""The forms whose constant carries no sign of its own, by width in bits: an enumerator of a
signed enum written in one of them is sign-extended from that width only where that is the
enum's whole width (gcc writes a positive enumerator as the ``dataN`` that holds it, so a
narrower one is positive)."""

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


_BASE_CLASS: Final = "a structure with a base class"
_STATIC_MEMBER: Final = "a structure with a static member"


class ElfReadError(ValueError):
    """An image this module cannot read at all; the message names the file and says why."""


class Deferred[T]:
    """A value built on demand: a field of :class:`Variable` holds one until it is read, so the
    reader hands back a variable without paying for what no caller asks of it."""

    __slots__ = ("_build",)

    def __init__(self, build: Callable[[], T]) -> None:
        self._build = build

    def __call__(self) -> T:
        return self._build()


class _Lazy[T]:
    """A field of a frozen dataclass that holds either a value or a :class:`Deferred` of one,
    and resolves and caches a deferred on first read. A plain value passed by hand is kept as
    it is, so a variable built without the reader - a test's, or a project's own - costs the
    same as before, and two variables compare and hash by their resolved values."""

    _default: tuple[T, ...]
    _name: str

    def __init__(self, *default: T) -> None:
        self._default = default

    def __set_name__(self, owner: type, name: str) -> None:
        self._name = f"__lazy_{name}"

    @overload
    def __get__(self, instance: None, owner: type) -> T: ...
    @overload
    def __get__(self, instance: object, owner: type | None = None) -> T: ...
    def __get__(self, instance: object, owner: type | None = None) -> T:
        if instance is None:
            # Class access: the dataclass machinery reads it to learn the field's default. A
            # field given none raises, which marks it required, as an ordinary field does.
            if self._default:
                return self._default[0]
            raise AttributeError(self._name)
        stored = instance.__dict__[self._name]
        if isinstance(stored, Deferred):
            value: T = stored()
            instance.__dict__[self._name] = value
            return value
        return cast("T", stored)

    def __set__(self, instance: object, value: T | Deferred[T]) -> None:
        instance.__dict__[self._name] = value


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
    vector: bool = False
    """Whether DWARF marks it a GNU vector (``DW_AT_GNU_vector``, as ``vector_size`` writes it):
    described as the array it holds, and aligned by the target as a whole."""


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


@dataclass(frozen=True)
class Variable:
    """A variable of static storage a unit's DWARF describes at its top level.

    ``type`` and ``declared_at`` are lazy (:class:`_Lazy`): the reader defers them, so a run
    builds a variable's type, and reads the line table for its declaration, only for the
    variables a caller asks about. A variable built by hand with plain values is unaffected.
    """

    name: str
    unit: str
    type: _Lazy[CType] = _Lazy()
    declared_at: _Lazy[Declared | None] = _Lazy(None)
    address: int | None = None
    missing: str = ""
    """Why ``address`` is None, as one of the constants of this module says it."""

    external: bool = True
    """Whether the variable has external linkage, as ``DW_AT_external`` states: False for a
    ``static``. True by default, so that a variable built by hand stands for a global, as an
    object of a project is; the reader always states it."""

    alignment: int | None = None
    """The alignment in bytes the source states on the variable (``_Alignas``, as
    ``DW_AT_alignment`` writes it); None where DWARF states none."""


@dataclass(frozen=True, slots=True)
class Section:
    """An allocated section: where it lies in memory, and where its bytes start in the file."""

    name: str
    address: int
    size: int
    offset: int | None
    """None for a section without contents (``SHT_NOBITS``), whose bytes the startup code
    provides rather than the image."""

    note: bool = False
    """Whether the section is a note (``SHT_NOTE``), which describes the file rather than holds
    the program: the build id of a debug-only companion has contents there."""

    index: int | None = None
    """Its index in the section header table, which the ``st_shndx`` of a symbol names; None
    where a caller built the section by hand and states none."""


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

    objects: frozenset[tuple[str, int]] = frozenset()
    """The name and address of every object symbol of the symbol table, which is where a linker
    says a variable is: the one it discarded has debug information and no symbol."""

    local_objects: frozenset[tuple[str, int]] = frozenset()
    """The name and address of the object symbols of local binding: empty where the link dropped
    them (``-Wl,-x``), and then the symbol table says nothing of a ``static``."""

    machine: int | None = None
    """The header's ``e_machine``, which names the machine, and with ``flags`` the ABI the
    structures are laid out by; None where a caller built the image by hand and states none."""

    flags: int = 0
    """The header's ``e_flags``: which ABI of the machine the image was built for, where a
    machine has more than one (ARM's EABI version, RISC-V's reduced register set)."""

    object_sizes: dict[tuple[str, int], int] = field(default_factory=dict)
    """The ``st_size`` of every object symbol, by its name and address: how large the linker
    says the variable is, which is what a description of it is held against."""

    object_sections: dict[tuple[str, int], int | str] = field(default_factory=dict)
    """The section every object symbol names (``st_shndx``), by its name and address, as the
    index of the section or as the name of a special one (``SHN_ABS``): which of several sections
    holding an address the variable is in."""

    load_relative: bool = False
    """Whether the image is position independent (``ET_DYN``, as ``-static-pie`` or ``-pie``
    links it): every address in it is an offset from where the image is loaded, which only the
    loader knows."""

    declarations: tuple[Variable, ...] = ()
    """What the units that only declare a variable some unit defines say of it, one entry per
    declaration - a consumer's ``extern``, as its header spells it. Not among ``variables``,
    which hold a name once, as its definition has it."""

    split_dwarf: bool = False
    """Whether the debug information is split (``-gsplit-dwarf``): the image holds a skeleton of
    each unit, and the unit itself is in a ``.dwo`` file beside it, which this module does not
    read."""

    @property
    def without_contents(self) -> bool:
        """Whether the image has allocated sections of the program, code and data alike, and
        none of them has contents in the file: what ``objcopy --only-keep-debug`` leaves. Its
        addresses are the image's, and none of its initial values is there to read. An image
        whose code alone is without contents (a ``NOLOAD`` region) keeps its data, and is read."""
        program = [section for section in self.sections if not section.note]
        return bool(program) and all(section.offset is None for section in program)

    def has_object(self, name: str, address: int) -> bool:
        """Whether the symbol table holds an object symbol ``name`` at ``address``."""
        return (name, address) in self.objects

    def keeps(self, name: str, address: int, *, external: bool) -> bool:
        """Whether the symbol table leaves a variable where its debug information puts it: an
        external needs an object symbol of its name there, and a ``static`` needs one of local
        binding wherever the image holds any, since a link made with ``-Wl,-x`` holds none."""
        if external:
            return self.has_object(name, address)
        return not self.local_objects or (name, address) in self.local_objects

    def section_of(self, address: int) -> Section | None:
        """The first section holding ``address``, or None where none does."""
        held = self.sections_at(address)
        return held[0] if held else None

    def sections_at(self, address: int) -> tuple[Section, ...]:
        """Every section holding ``address``: more than one where a linker script overlays
        sections, as it does for a banked memory."""
        return tuple(
            section
            for section in self.sections
            if section.address <= address < section.address + section.size
        )

    def sections_of(self, name: str, address: int) -> tuple[Section, ...]:
        """The sections that may be the variable ``name`` at ``address``'s: the one its symbol
        names where that section holds the address, else every section that does."""
        index = self.object_sections.get((name, address))
        held = self.sections_at(address)
        if index is not None:
            named = [section for section in held if section.index == index]
            if named:
                return tuple(named)
        return held

    def unheld(self, name: str, address: int) -> str:
        """The sentence for a variable ``name`` at an ``address`` that no section holds."""
        return f"'{name}' has an address, {address:#x}, that no section of the image holds"

    def read(self, address: int, size: int, section: Section | None = None) -> bytes | None:
        """The ``size`` bytes at ``address``, or None where the image does not hold them; in
        ``section`` where the caller knows which of several holding the address is meant."""
        if section is None:
            section = self.section_of(address)
        if section is None or section.offset is None:
            return None
        if address + size > section.address + section.size:
            return None
        start = section.offset + address - section.address
        return self.contents[start : start + size]


class Entry(Protocol):
    """What the readers ask of a DWARF entry. pyelftools' ``DIE`` is one. Its children are
    reached through :meth:`Unit.children`, not the library's own walk, so a damaged sibling
    pointer cannot send the reader in a circle."""

    @property
    def tag(self) -> str | int | None: ...

    @property
    def offset(self) -> int: ...

    @property
    def attributes(self) -> Mapping[str, Any]: ...

    def get_DIE_from_attribute(self, name: str) -> Entry: ...  # noqa: N802 - pyelftools' name


class Unit(Protocol):
    """What the variable reader asks of a compilation unit."""

    @property
    def name(self) -> str: ...

    @property
    def top(self) -> Entry: ...

    def children(self, entry: Entry) -> Iterator[Entry]:
        """The children of ``entry``, walked with a forward-only cursor that refuses a sibling
        pointer leading to an entry that does not lie past the one it leaves."""
        ...

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


def without_address(name: str, missing: str) -> str:
    """The sentence for a variable ``name`` that has no address, for the reason ``missing``: a
    variable of another scope is not one that lacks an address, it is one that is not read."""
    if missing == OTHER_SCOPE:
        return f"'{name}' is {missing}"
    return f"'{name}' has no address in the image: {missing}"


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


def described_apart(candidates: Sequence[Variable], image: Image) -> dict[int, list[Variable]]:
    """The variables of one name, ``candidates``, at each address where what is known of their
    size is not one number: units whose descriptions differ in it, or a description and the
    symbol table's own size for the name there (a symbol of size 0 states none).

    One name at one address is one variable, however many units describe it, so what is asked
    is every unit of the image that describes the name, and not only the ones a caller chose:
    a unit prefix on a command line chooses the unit and nothing more.
    """
    apart: dict[int, list[Variable]] = {}
    for address in {variable.address for variable in candidates if variable.address is not None}:
        variables = [variable for variable in candidates if variable.address == address]
        sizes = {size for variable in variables if (size := size_of(variable.type)) is not None}
        symbol = image.object_sizes.get((variables[0].name, address))
        if symbol:
            sizes.add(symbol)
        if len(sizes) > 1:
            apart[address] = variables
    return apart


def read_variables(
    units: Iterable[Unit],
    *,
    big_endian: bool,
    thread_local: frozenset[str] = frozenset(),
    objects: frozenset[tuple[str, int]] = frozenset(),
    address_size: int = 4,
    shown: str = "",
    declarations: list[Variable] | None = None,
) -> tuple[Variable, ...]:
    """The variables at the top of every unit, each with its type, address and declaration.

    A name that is only ever declared is kept, as a variable without storage, so that a
    caller asking for it can say why it is not there; a name that some unit defines drops
    every declaration of it. A variable of another scope, a C++ namespace's or a class's, is
    kept the same way, and a C variable of its short name drops it. ``thread_local`` names the
    thread-local symbols of the image: a target whose DWARF cannot state a thread-local address
    gives such a variable no location at all, and only the symbol table still says what it is.

    ``objects`` holds the name and address of every object symbol of the image, and
    ``address_size`` the width of its addresses in bytes. A linker keeps the entry of a variable
    it discarded and resolves its address to a tombstone: GNU ld and lld 19 write 0, and lld
    all ones when told to (``-z dead-reloc-in-nonalloc``). A variable at 0, or at all ones at
    the image's width, is one the linker discarded, unless a symbol of its name sits there.

    Each variable's type and declaration are deferred (:class:`Deferred`), so this builds no
    type and reads no line table of its own; ``shown`` names the image in the refusal a
    deferred build raises, since that build happens after :func:`open_image` has returned.

    ``declarations``, where a caller gives a list, receives every declaration a unit makes of
    a name that some other unit defines - the ones dropped above - so that a caller holding a unit's
    own spelling of a variable to what the definition says has them, which are not variables.
    """
    types = _Types(big_endian=big_endian)
    symbols = _Symbols(thread_local, objects, frozenset({0, (1 << (8 * address_size)) - 1}))
    defined: list[Variable] = []
    declared: dict[str, Variable] = {}
    every: list[Variable] = []
    for unit in units:
        entries = [entry for entry in unit.children(unit.top) if entry.tag == "DW_TAG_variable"]
        # A definition completes the declaration it names where that sits beside it at the top
        # of the unit, as C writes one; gcc writes a C++ namespace's or a class's the same way,
        # with the declaration inside the scope, and that variable is not one a short name names.
        here = frozenset(entry.offset for entry in entries)
        for entry in entries:
            variable = _variable(entry, unit, types, symbols, shown, here)
            if variable is None:
                continue
            if variable.missing in (DECLARED_ONLY, OTHER_SCOPE):
                declared.setdefault(variable.name, variable)
                if variable.missing == DECLARED_ONLY:
                    every.append(variable)
                continue
            defined.append(variable)
    names = {variable.name for variable in defined}
    homes = {(variable.name, variable.unit) for variable in defined}
    defined.extend(variable for name, variable in declared.items() if name not in names)
    if declarations is not None:
        # A unit that defines a name states the declaration its definition completes as well,
        # which is the unit's own header, and not another unit's reading of the variable.
        declarations.extend(
            variable
            for variable in every
            if variable.name in names and (variable.name, variable.unit) not in homes
        )
    return tuple(defined)


def open_image(path: Path) -> Image:
    """Read a linked ELF image and its DWARF; :class:`ElfReadError` says why one cannot be.

    An image is untrusted input, and pyelftools answers a damaged one with whatever its parse
    runs into - a KeyError, a zlib.error, a failed assertion - as often as with an error of its
    own. :func:`_guarded` turns any such exception into a refusal that names it, so that a
    damaged file is a usage error rather than a traceback. The same net wraps each deferred
    type and declaration a caller asks of a variable later, since those are built outside this
    call.
    """
    installed = elftools.__version__
    if tuple(int(part) for part in re.findall(r"\d+", installed)[:2]) < _PYELFTOOLS_FLOOR:
        floor = ".".join(str(part) for part in _PYELFTOOLS_FLOOR)
        msg = (
            f"pyelftools {installed} is installed, and reading an ELF image needs {floor} or "
            f"newer: pip install --upgrade 'pyelftools>={floor}'"
        )
        raise ElfReadError(msg)
    shown = path.as_posix()
    try:
        contents = path.read_bytes()
    except OSError as error:
        msg = f"cannot read '{shown}': {error.strerror}"
        raise ElfReadError(msg) from None
    return _guarded(shown, lambda: _image(path, contents))


def _guarded[T](shown: str, build: Callable[[], T]) -> T:
    """``build()``, with any exception it runs into turned into an :class:`ElfReadError` that
    names the image: the one net both :func:`open_image` and a deferred build pass through, so
    that a damaged image is a usage error wherever the reader meets it, not a traceback."""
    try:
        return build()
    except ElfReadError:
        raise
    except (ELFError, DWARFError) as error:
        msg = f"'{shown}' is not an ELF image this tool can read: {error}"
        raise ElfReadError(msg) from None
    except Exception as error:
        msg = f"'{shown}' is not an ELF image this tool can read: {_named(error)}"
        raise ElfReadError(msg) from None


def _machine(stored: object) -> int:
    """``e_machine`` as its number: pyelftools names the machines it knows and leaves the rest as
    the number they are."""
    if isinstance(stored, int):
        return stored
    return int(ENUM_E_MACHINE[str(stored)])


def _named(error: Exception) -> str:
    """An exception as a refusal names it: its type, qualified by its module unless it is a
    builtin - ``zlib.error`` says more than ``error`` - and its message, where it has one."""
    kind = type(error)
    name = kind.__qualname__
    if kind.__module__ != "builtins":
        name = f"{kind.__module__}.{name}"
    message = str(error)
    if not message:
        return name
    return f"{name}: {message}"


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
    byte_order: Literal["little", "big"] = "little" if elf.little_endian else "big"
    for stored in elf.iter_sections():
        if not stored["sh_flags"] & SH_FLAGS.SHF_COMPRESSED:
            continue
        # A compressed section starts with its compression header, whose first word, in
        # ELF32 and ELF64 alike, is the compression's type.
        start = stored["sh_offset"]
        if int.from_bytes(contents[start : start + 4], byte_order) == _ELFCOMPRESS_ZSTD:
            msg = (
                f"'{shown}' is not an ELF image this tool can read: its debug information is "
                f"compressed with zstd, which this tool does not read; build it with -gz=zlib"
            )
            raise ElfReadError(msg)
    dwarf = elf.get_dwarf_info(relocate_dwarf_sections=False, follow_links=False)
    compile_units = list(dwarf.iter_CUs())
    # A DWARF 4 type unit's entries count their offsets from .debug_types's own start, which
    # collides with .debug_info's; a DWARF 5 one sits in .debug_info with ordinary offsets, but
    # pyelftools resolves no signature at all. gcc's -fdebug-types-section read as it is gave wrong
    # types at DWARF 4 and a KeyError at 5 (measured with gcc 15.2).
    if elf.get_section_by_name(".debug_types") is not None or any(
        cu.header.get("unit_type") == "DW_UT_type" for cu in compile_units
    ):
        msg = (
            f"'{shown}' is not an ELF image this tool can read: its DWARF holds type units, "
            f"which -fdebug-types-section writes and this tool does not read; build it without "
            f"-fdebug-types-section"
        )
        raise ElfReadError(msg)
    units = [_PyelftoolsUnit(cu, dwarf, shown) for cu in compile_units]
    # gcc -flto names a variable in the unit of its source, without a location, and locates it
    # in a unit of GNU GIMPLE's, without a name: read as it is, every variable was removed.
    if any(unit.producer.startswith(_LTO_PRODUCER) for unit in units):
        msg = (
            f"'{shown}' is not an ELF image this tool can read: its DWARF comes from gcc's "
            f"link-time optimisation, which this tool does not read; build it without -flto"
        )
        raise ElfReadError(msg)
    objects = _symbols(elf, "STT_OBJECT")
    sizes, homes = _object_facts(elf)
    declarations: list[Variable] = []
    variables = read_variables(
        units,
        big_endian=not elf.little_endian,
        thread_local=frozenset(name for name, _ in _symbols(elf, "STT_TLS")),
        objects=objects,
        address_size=elf.elfclass // 8,
        shown=shown,
        declarations=declarations,
    )
    return Image(
        path=path,
        load_relative=kind == "ET_DYN",
        split_dwarf=any(
            "DW_AT_dwo_name" in unit.top.attributes or "DW_AT_GNU_dwo_name" in unit.top.attributes
            for unit in units
        ),
        byte_order=byte_order,
        variables=variables,
        sections=sections,
        symbols=frozenset(name for name, _ in objects),
        contents=contents,
        objects=objects,
        local_objects=_symbols(elf, "STT_OBJECT", local=True),
        machine=_machine(elf.header["e_machine"]),
        flags=int(elf.header["e_flags"]),
        object_sizes=sizes,
        object_sections=homes,
        declarations=tuple(declarations),
    )


def _sections(elf: ELFFile) -> tuple[Section, ...]:
    sections: list[Section] = []
    for index, section in enumerate(elf.iter_sections()):
        flags = section["sh_flags"]
        if not flags & SH_FLAGS.SHF_ALLOC or flags & SH_FLAGS.SHF_TLS:
            continue
        offset = None if section["sh_type"] == "SHT_NOBITS" else section["sh_offset"]
        # A section's name comes from .shstrtab, not DWARF, but reaches the same places a
        # DWARF string does - a refusal, a finding, the output - so it is untrusted the same
        # way: _decoded() writes out its control characters here, as it does for DWARF's.
        sections.append(
            Section(
                _decoded(section.name),
                section["sh_addr"],
                section["sh_size"],
                offset,
                note=section["sh_type"] == "SHT_NOTE",
                index=index,
            )
        )
    return tuple(sections)


def _symbols(elf: ELFFile, kind: str, *, local: bool = False) -> frozenset[tuple[str, int]]:
    """The name and address of every symbol of type ``kind`` (``STT_OBJECT``, ``STT_TLS``), in
    any table, global and local alike; of local binding alone where ``local`` says so."""
    found: set[tuple[str, int]] = set()
    for section in elf.iter_sections():
        if isinstance(section, SymbolTableSection):
            found.update(
                (symbol.name, symbol["st_value"])
                for symbol in section.iter_symbols()
                if symbol["st_info"]["type"] == kind
                and (not local or symbol["st_info"]["bind"] == "STB_LOCAL")
            )
    return frozenset(found)


def _object_facts(
    elf: ELFFile,
) -> tuple[dict[tuple[str, int], int], dict[tuple[str, int], int | str]]:
    """The size, and the section (``st_shndx``), of every object symbol of any table, by its
    name and address."""
    sizes: dict[tuple[str, int], int] = {}
    homes: dict[tuple[str, int], int | str] = {}
    for section in elf.iter_sections():
        if not isinstance(section, SymbolTableSection):
            continue
        for symbol in section.iter_symbols():
            if symbol["st_info"]["type"] != "STT_OBJECT":
                continue
            key = (symbol.name, symbol["st_value"])
            sizes[key] = symbol["st_size"]
            homes[key] = symbol["st_shndx"]
    return sizes, homes


class _PyelftoolsUnit:
    """A pyelftools compilation unit, as :class:`Unit` asks for one."""

    def __init__(self, cu: Any, dwarf: Any, shown: str) -> None:
        self._cu = cu
        self._dwarf = dwarf
        self._shown = shown
        self._parser = DWARFExprParser(cu.structs)
        self.top: Entry = cu.get_top_DIE()
        self.name = _text(self.top.attributes.get("DW_AT_name")) or ""
        self.producer = _text(self.top.attributes.get("DW_AT_producer")) or ""
        self._compilation_directory = _text(self.top.attributes.get("DW_AT_comp_dir")) or ""
        # The line table is read only when a declaration a caller asks about needs a path, and
        # once per unit: pyelftools' own eager read of every unit's at open time is what let a
        # crafted line header allocate before anyone looked.
        self._files: FileTable | None = None
        self._files_read = False

    def children(self, entry: Entry) -> Iterator[Entry]:
        parent = self._node_at(entry.offset)
        for node in _children(parent, self._node_at, self._shown):
            yield node.entry

    def _node_at(self, offset: int) -> _Node:
        die = self._cu.get_DIE_from_refaddr(offset)
        sibling = None
        if die.has_children and "DW_AT_sibling" in die.attributes:
            sibling = die.get_DIE_from_attribute("DW_AT_sibling").offset
        return _Node(die.offset, die.size, die.is_null(), bool(die.has_children), sibling, die)

    def operations(self, expression: Sequence[int]) -> list[tuple[str, list[Any]]]:
        return [(op.op_name, list(op.args)) for op in self._parser.parse_expr(expression)]

    def indexed_address(self, index: int) -> int:
        return int(self._dwarf.get_addr(self._cu, index))

    def file(self, index: int) -> str | None:
        if not self._files_read:
            self._files = self._read_file_table()
            self._files_read = True
        return file_path(self._files, index)

    def _read_file_table(self) -> FileTable | None:
        stmt_list = self.top.attributes.get("DW_AT_stmt_list")
        if stmt_list is not None:
            _bound_line_counts(
                self._dwarf.debug_line_sec.stream, stmt_list.value, self._cu.structs, self._shown
            )
        program = self._dwarf.line_program_for_CU(self._cu)
        return file_table(program, self._compilation_directory)


@dataclass(frozen=True, slots=True)
class _Node:
    """One entry of a unit, as the forward-only cursor sees it: where it lies, how far it runs,
    whether it is the null entry that ends a child list, whether it has children, and the
    offset its ``DW_AT_sibling`` points to, if any."""

    offset: int
    size: int
    is_null: bool
    has_children: bool
    sibling: int | None
    entry: Any = None
    """The entry itself, which :meth:`_PyelftoolsUnit.children` yields; the cursor navigates by
    the fields above alone, so a test drives it with plain stand-ins."""


def _children(parent: _Node, fetch: Callable[[int], _Node], shown: str) -> Iterator[_Node]:
    """The children of ``parent``, read one after the next by a cursor of the reader's own.

    ``fetch`` reads the entry at a byte offset. The cursor starts just past ``parent`` and
    moves to each next sibling only where it lies past the entry it leaves; a sibling pointer
    that does not advance is a damaged image, refused at once. pyelftools' own walk follows the
    pointer unchecked, which a file that points an entry back at itself sends round forever.
    """
    if not parent.has_children:
        return
    cursor = parent.offset + parent.size
    while True:
        node = fetch(cursor)
        if node.is_null:
            return
        yield node
        cursor = _after(node, fetch, shown)


def _after(node: _Node, fetch: Callable[[int], _Node], shown: str) -> int:
    """Where the entry after ``node`` begins: the next byte for a leaf, the stated sibling where
    the producer wrote one, else the far side of ``node``'s own subtree. Any of these that does
    not lie past ``node`` is refused, naming the offset of the entry whose walk cannot go on."""
    end = node.offset + node.size
    if not node.has_children:
        nxt = end
    elif node.sibling is not None:
        nxt = node.sibling
    else:
        nxt = _past(node, fetch, shown)
    if nxt < end:
        msg = (
            f"'{shown}' is not an ELF image this tool can read: the entry at {node.offset:#x} "
            f"points to a next sibling at {nxt:#x}, which does not lie past it, so its debug "
            f"information cannot be walked"
        )
        raise ElfReadError(msg)
    return nxt


def _past(parent: _Node, fetch: Callable[[int], _Node], shown: str) -> int:
    """The offset just past ``parent``'s whole subtree, for an entry with children that states
    no sibling: walk its children to their null terminator, the same forward rule throughout."""
    cursor = parent.offset + parent.size
    while True:
        node = fetch(cursor)
        if node.is_null:
            return node.offset + node.size
        cursor = _after(node, fetch, shown)


def _bound_line_counts(stream: Any, offset: int, structs: Any, shown: str) -> None:
    """Refuse a DWARF 5 line program whose directory or file table names more entries than the
    bytes after it could hold, before pyelftools allocates for them (finding 11:I6's line
    header). Earlier line tables count neither table and so cannot overpromise this way.
    """
    stream.seek(offset)
    program_end = struct_parse(structs.Dwarf_initial_length("length"), stream) + stream.tell()
    if struct_parse(structs.the_Dwarf_uint16, stream) < 5:  # the line program's own version
        return
    for _ in range(2):  # address_size, segment_selector_size
        struct_parse(structs.the_Dwarf_uint8, stream)
    struct_parse(structs.the_Dwarf_offset, stream)  # header_length
    for _ in range(5):  # minimum_instruction_length .. line_range
        struct_parse(structs.the_Dwarf_uint8, stream)
    for _ in range(struct_parse(structs.the_Dwarf_uint8, stream) - 1):  # standard opcode lengths
        struct_parse(structs.the_Dwarf_uint8, stream)
    directory_forms = _line_entry_format(stream, structs)
    directories = struct_parse(structs.the_Dwarf_uleb128, stream)
    _require_line_entries_fit(directories, program_end - stream.tell(), shown)
    for _ in range(directories):  # bounded now, so reaching the file count is bounded work
        for form in directory_forms:
            struct_parse(structs.Dwarf_dw_form[form], stream)
    _line_entry_format(stream, structs)
    files = struct_parse(structs.the_Dwarf_uleb128, stream)
    _require_line_entries_fit(files, program_end - stream.tell(), shown)


def _line_entry_format(stream: Any, structs: Any) -> list[str]:
    """One ``directory_entry_format`` or ``file_name_entry_format``: its ``(content, form)``
    pairs, as the form names a later entry is parsed by. The count is a single byte, so this
    reads at most 255 pairs whatever the image."""
    forms = []
    for _ in range(struct_parse(structs.the_Dwarf_uint8, stream)):
        struct_parse(structs.the_Dwarf_uleb128, stream)  # content type code
        forms.append(DW_FORM_raw2name[struct_parse(structs.the_Dwarf_uleb128, stream)])
    return forms


def _require_line_entries_fit(count: int, bytes_left: int, shown: str) -> None:
    """Refuse a line header that promises ``count`` entries where only ``bytes_left`` bytes
    follow it: an entry is at least one byte, so a count past that cannot be met and the header
    is damaged. Checked before the array is allocated, so the count alone is the whole cost."""
    if count > bytes_left:
        msg = (
            f"'{shown}' is not an ELF image this tool can read: a line program's header names "
            f"{count} directory or file entries, more than the {bytes_left} bytes after it can "
            f"hold"
        )
        raise ElfReadError(msg)


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


@dataclass(frozen=True, slots=True)
class _Symbols:
    """What the symbol table says of the variables DWARF describes."""

    thread_local: frozenset[str]
    objects: frozenset[tuple[str, int]]
    discarded_at: frozenset[int]
    """The addresses a linker gives a variable it discarded."""


def _variable(
    entry: Entry,
    unit: Unit,
    types: _Types,
    symbols: _Symbols,
    shown: str,
    here: frozenset[int],
) -> Variable | None:
    named = entry
    if "DW_AT_specification" in entry.attributes:
        named = entry.get_DIE_from_attribute("DW_AT_specification")
    name = _text(named.attributes.get("DW_AT_name"))
    if name is None:
        return None
    if named is not entry and named.offset not in here:
        return Variable(
            name,
            unit.name,
            Deferred(lambda: _guarded(shown, lambda: types.inner(named, unit))),
            Deferred(lambda: _guarded(shown, lambda: _declared(entry, named, unit))),
            None,
            OTHER_SCOPE,
            bool(_either(entry, named, "DW_AT_external")),
        )
    # The type and the declaration are deferred, each behind the reader's net, so a run pays
    # for them only where a caller reads them, and a build that trips on a damaged image is
    # still the usage error open_image would have raised. A definition states a type of its own
    # where it completes the declaration's - the size of an array a header declared without one
    # - and takes the declaration's otherwise.
    type_entry = entry if "DW_AT_type" in entry.attributes else named
    ctype = Deferred(lambda: _guarded(shown, lambda: types.inner(type_entry, unit)))
    declared_at = Deferred(lambda: _guarded(shown, lambda: _declared(entry, named, unit)))
    attributes = entry.attributes
    address: int | None = None
    missing = ""
    if "DW_AT_location" in attributes:
        address, missing = _address(attributes["DW_AT_location"].value, unit)
        if address in symbols.discarded_at and (name, address) not in symbols.objects:
            address, missing = None, DISCARDED
    elif "DW_AT_const_value" in attributes:
        missing = FOLDED
    elif "DW_AT_declaration" in attributes:
        missing = DECLARED_ONLY
    elif name in symbols.thread_local:
        # aarch64's gcc 14 and clang 19 state no location at all for a thread-local variable
        # (the trial build); its symbol, of type STT_TLS, still says what it is.
        missing = THREAD_LOCAL
    else:
        missing = REMOVED
    # Read where the name is: gcc states DW_AT_external on the declaration a definition
    # completes and not on the definition, clang on the one entry it writes (measured over the
    # fixture matrix). DWARF 2 and 3 spell it as a flag byte, whose 0 says it is absent.
    external = bool(_either(entry, named, "DW_AT_external"))
    alignment = _either(entry, named, "DW_AT_alignment")
    return Variable(
        name,
        unit.name,
        ctype,
        declared_at,
        address,
        missing,
        external,
        alignment if isinstance(alignment, int) else None,
    )


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
        for child in unit.children(entry):
            if child.tag != "DW_TAG_subrange_type":
                continue
            extent = _extent(child)
            if extent is None or extent < 1:
                return Unsupported("an array without a fixed size of at least one element")
            dimensions.append(extent)
        if not dimensions:
            return Unsupported("an array without a fixed size of at least one element")
        return Array(
            self.inner(entry, unit),
            tuple(dimensions),
            vector=bool(_value(entry, "DW_AT_GNU_vector")),
        )

    def _enum(self, entry: Entry, unit: Unit) -> CType:
        if "DW_AT_declaration" in entry.attributes:
            return Unsupported("an enum declared but never defined")
        children = [child for child in unit.children(entry) if child.tag == "DW_TAG_enumerator"]
        signed = self._signed(entry, children, unit)
        size = int(_value(entry, "DW_AT_byte_size"))
        return Enum(
            tag=_text(entry.attributes.get("DW_AT_name")),
            size=size,
            signed=signed,
            enumerators=tuple(_enumerator(child, signed=signed, size=size) for child in children),
            declared_at=_declared(entry, entry, unit),
        )

    def _signed(self, entry: Entry, children: Sequence[Entry], unit: Unit) -> bool:
        """An enum's sign: its underlying type's, else its encoding's, else whether an
        enumerator is negative - which an old producer states and nothing else."""
        if "DW_AT_type" in entry.attributes:
            underlying = core_of(self.inner(entry, unit))
            if isinstance(underlying, Base):
                return underlying.encoding in _SIGNED_ENCODINGS
        encoding = _value(entry, "DW_AT_encoding")
        if isinstance(encoding, int):
            return encoding in _SIGNED_ENCODINGS
        for child in children:
            attribute = child.attributes["DW_AT_const_value"]
            if attribute.form == "DW_FORM_sdata" and attribute.value < 0:
                return True
        return False

    def _struct(self, entry: Entry, unit: Unit) -> CType:
        if "DW_AT_declaration" in entry.attributes:
            return Unsupported("a structure declared but never defined")
        children = list(unit.children(entry))
        # C++ shapes the reader would describe wrongly: a base class's members are the
        # structure's own storage, a static member is none of it.
        if any(child.tag == "DW_TAG_inheritance" for child in children):
            return Unsupported(_BASE_CLASS)
        fields = [child for child in children if child.tag == "DW_TAG_member"]
        if any(_static(child) for child in fields):
            return Unsupported(_STATIC_MEMBER)
        members = tuple(self._member(child, unit) for child in fields)
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


def _static(member: Entry) -> bool:
    """Whether a member of a structure is a static one, which has no place in the structure: DWARF
    4 writes it as a member that is only declared (with ``DW_AT_external``). It is told by those
    marks and not by a missing location, since a member at the start of its structure may state
    none. DWARF 5 writes the static apart, as a ``DW_TAG_variable`` child, which is no member."""
    return "DW_AT_declaration" in member.attributes or "DW_AT_external" in member.attributes


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


def _enumerator(entry: Entry, *, signed: bool, size: int) -> tuple[str, int]:
    attribute = entry.attributes["DW_AT_const_value"]
    value = int(attribute.value)
    width = _DATA_WIDTHS.get(attribute.form)
    if signed and width == 8 * size and value >= 1 << (width - 1):
        value -= 1 << width
    return _text(entry.attributes.get("DW_AT_name")) or "", value


def core_of(ctype: CType) -> CType:
    """``ctype`` without the typedefs and qualifiers around it."""
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
    """A string of the image's as text a terminal can show: an image is untrusted, and its
    names and paths reach standard error, so every control character - the escape that opens
    a terminal sequence among them - is written out as ``\\xNN``."""
    text = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else str(value)
    return _CONTROL.sub(lambda control: f"\\x{ord(control.group()):02x}", text)
