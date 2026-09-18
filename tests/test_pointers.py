"""The shared spelling of a pointer: what ``ddd.lsp.ranges`` and ``ddd.editing`` both read."""

from __future__ import annotations

import pytest

from ddd.pointers import parent_pointer, segments


class TestSegments:
    @pytest.mark.parametrize(
        ("pointer", "parts"),
        [
            ("a.b[2].c", ["a", "b", 2, "c"]),
            ("[0]", [0]),
            ("", []),
        ],
    )
    def test_a_pointer_is_taken_apart_into_its_keys_and_indices(self, pointer, parts):
        assert segments(pointer) == parts


class TestParentPointer:
    @pytest.mark.parametrize(
        ("pointer", "parents"),
        [
            ("a.b[2].c", ["a.b[2]", "a.b", "a", ""]),
            ("[0]", [""]),
            ("", [""]),
        ],
    )
    def test_a_pointer_walks_up_to_the_top_of_the_file(self, pointer, parents):
        walked = []
        current = pointer
        for _ in parents:
            current = parent_pointer(current)
            walked.append(current)
        assert walked == parents
