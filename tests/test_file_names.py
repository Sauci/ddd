"""The names no file can be created under, on any system: each rule, and the sentence it says."""

from __future__ import annotations

import pytest

from ddd.file_names import uncreatable

KEPT_OUT = "which Windows keeps out of a file's name"


@pytest.mark.parametrize("character", list('<>:"/\\|?*'))
def test_a_character_windows_keeps_out_of_a_name_is_refused(character: str) -> None:
    """On every system, as a page's path is: a project is checked out on more than one, and on
    Windows the staged write of such a name failed, answered ``500``, where a colon named a
    stream of another file instead."""
    assert uncreatable(f"a{character}b.ddd.json") == f"its name holds '{character}', {KEPT_OUT}"


@pytest.mark.parametrize("code", range(0x20))
def test_a_control_character_is_refused_by_its_code_point(code: int) -> None:
    """Named by its code point, U+0000 to U+001F, never written into the sentence as itself."""
    assert uncreatable(f"a{chr(code)}b.ddd.json") == (
        f"its name holds the control character U+{code:04X}, {KEPT_OUT}"
    )


def test_the_first_character_kept_out_is_the_one_named() -> None:
    assert uncreatable("a?b\x01c<d.ddd.json") == f"its name holds '?', {KEPT_OUT}"


@pytest.mark.parametrize(
    ("name", "said"),
    [
        ("units.ddd.json.", "its name ends in a dot, which Windows drops from a file's name"),
        ("units.ddd.json ", "its name ends in a space, which Windows drops from a file's name"),
        ("..", "its name ends in a dot, which Windows drops from a file's name"),
    ],
    ids=["a-dot", "a-space", "dots-alone"],
)
def test_a_name_ending_in_what_windows_drops_is_refused(name: str, said: str) -> None:
    """Windows drops a dot or a space a name ends in, and would create the file under another
    name than the one the includes give it."""
    assert uncreatable(name) == said


@pytest.mark.parametrize(
    "name",
    [
        "units.ddd.json",
        "a b.ddd.json",
        ".hidden.ddd.json",
        "a..b.ddd.json",
        "\u00e9t\u00e9.ddd.json",
        "a\x7fb.ddd.json",
        "a\u00a0b.ddd.json",
    ],
    ids=[
        "plain",
        "a-space-inside",
        "a-leading-dot",
        "two-dots-inside",
        "letters-beyond-ascii",
        "delete-which-is-no-c0-control",
        "a-no-break-space-inside",
    ],
)
def test_any_other_name_can_be_created(name: str) -> None:
    assert uncreatable(name) is None


def test_a_device_is_named_before_a_character_kept_out() -> None:
    """A name both a device's and holding such a character is refused as the device: the
    graver of the two, and the sentence the page already shows for one."""
    assert uncreatable("con.a<b") == (
        "Windows reads its name as the device CON, which it would open instead of a file"
    )
