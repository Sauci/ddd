"""The names no file can be created under, on any system: the names Windows keeps for its
devices, the characters it keeps out of a file's name, and the length a file staged under its
name leaves it.

A project is checked out on more than one system, so a name one of them cannot hold a file
under is refused on all of them alike: by ``ddd gui``'s server of a page's path, and of a path a
request names on Windows (:func:`device_named`), and by every edit or plan that creates a file
(:func:`uncreatable`). Apart from the edit engine, which stages every write under
:data:`STAGING_SUFFIX`: what reads a name's rule need not import the engine for it.
"""

from __future__ import annotations

from typing import Final

STAGING_SUFFIX: Final = ".ddd-staging"
"""What a file's new bytes are staged under beside it: the name ``ddd id`` and the artefact
writer stage under, which no project gives a file of its own."""

NAME_MAX: Final = 255
"""The longest name of a file a file system takes, in the bytes utf-8 spells it with: what ext4
counts, and never fewer than the utf-16 units NTFS counts, so a name within it is one both take."""

CREATED_NAME_MAX: Final = NAME_MAX - len(STAGING_SUFFIX)
"""The longest name a file can be created under: staged first under the name and
:data:`STAGING_SUFFIX`, it must fit :data:`NAME_MAX`."""

DEVICE_NAMES: Final = frozenset(
    {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
    | {f"{port}{digit}" for port in ("COM", "LPT") for digit in "0123456789¹²³"}
)
"""The names Windows keeps for its devices: the console, the printer, the auxiliary port and
the null device, the console's own input and output, and the serial and parallel ports, ``COM``
and ``LPT`` followed by a digit, the superscripts one, two and three among them. Windows reads
such a name as the device in whatever directory it is written, so that opening it opens the
device rather than a file (:func:`device_named`); python's own ``ntpath.isreserved``, from
3.13, counts ``CONIN$`` and ``CONOUT$`` among them too. Asked of a page's path by ``ddd gui``'s
server, of every name of a path a request names where Windows opens a device for it
(``ddd.gui.queries``), and of the name of every file an edit or the plan of a new file creates
(:func:`uncreatable`)."""

RESERVED_CHARACTERS: Final = '<>:"/\\|?*'
"""The characters Windows keeps out of a file's name, besides the control characters below
U+0020 (:func:`uncreatable`): every one a part of a path's own syntax there, and a colon what
names a stream of the file before it."""


def uncreatable(name: str) -> str | None:
    """Why no file can be created under ``name``, on any system, or ``None`` where one can: a
    name Windows reads as a device (:func:`device_named`); one holding a character Windows keeps
    out of a file's name - a control character, or one of :data:`RESERVED_CHARACTERS` - or ending
    in a dot or a space, which Windows drops from a file's name, creating the file under another
    than the one the includes give it; or one longer than :data:`CREATED_NAME_MAX` bytes. Each is
    the request's to answer for, not a failure to write.

    Asked before anything looks the name up: by ``ddd gui`` of every file an edit creates before
    it confines any change of the edit (``ddd.gui.session``), and by the plan of a new file
    before it asks whether one is there (``ddd.file_plans``); the edit engine asks it again
    (:func:`ddd.editing._created`) before it looks for the file, for any caller that has not.
    A name too long to stage was staged regardless before, the file system refused it, and the
    edit was answered as a write that failed, ``500``, with the files already written put back;
    on Linux python 3.12's own ``Path.exists`` raised on a name past :data:`NAME_MAX` first. A
    file staged under a device's name on Windows would have opened the device, and one under a
    character Windows keeps out failed there as the staged write did, ``500``. Refused on every
    system alike, as a page's path is, since a project is checked out on more than one.
    """
    device = device_named(name)
    if device is not None:
        return (
            f"Windows reads its name as the device {device}, which it would open instead of a file"
        )
    kept_out = _kept_out(name)
    if kept_out is not None:
        return f"its name holds {kept_out}, which Windows keeps out of a file's name"
    if name.endswith("."):
        return "its name ends in a dot, which Windows drops from a file's name"
    if name.endswith(" "):
        return "its name ends in a space, which Windows drops from a file's name"
    length = len(name.encode("utf-8", "surrogatepass"))
    if length > CREATED_NAME_MAX:
        return (
            f"its name is {length} bytes long, and a name is at most {CREATED_NAME_MAX} - the "
            f"file is staged under the name and '{STAGING_SUFFIX}' first, and ext4 takes a name of "
            f"at most {NAME_MAX} bytes, NTFS one of at most {NAME_MAX} UTF-16 units, which "
            f"{NAME_MAX} bytes never exceed"
        )
    return None


def _kept_out(name: str) -> str | None:
    """The first character of ``name`` Windows keeps out of a file's name, as a refusal names it
    - a control character by its code point, never as itself, any other in quotes - or ``None``
    where it holds none."""
    for character in name:
        if ord(character) < 0x20:
            return f"the control character U+{ord(character):04X}"
        if character in RESERVED_CHARACTERS:
            return f"'{character}'"
    return None


def device_named(name: str) -> str | None:
    """The device of :data:`DEVICE_NAMES` Windows reads ``name`` as, or ``None``: such a name
    before the name's first dot, in any case, less any spaces it ends in. ``nul.js``,
    ``Lpt9.txt``, ``aux.`` and ``con .x`` each name a device there, and ``console`` and ``com10``
    do not. Asked on every system, so that a name is answered alike on all of them."""
    device = name.partition(".")[0].rstrip(" ").upper()
    if device in DEVICE_NAMES:
        return device
    return None
