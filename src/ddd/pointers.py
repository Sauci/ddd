"""The spelling of a ddd pointer, such as ``component.interface[2].definition.unit``.

Both the language server's scanner (:mod:`ddd.lsp.ranges`) and the edit engine
(:mod:`ddd.editing`) need to take a pointer apart or find its parent, and the two must agree on
what a pointer means - so the grammar lives here, once, rather than in either of them. This
module imports nothing but the standard library, so both can import it at module level without
either pulling the other in.
"""

from __future__ import annotations

import re
from typing import Final

_SEGMENT: Final = re.compile(r"\[(\d+)\]|([^.\[\]]+)")


def segments(pointer: str) -> list[str | int]:
    """``a.b[2].c`` -> ``['a', 'b', 2, 'c']``, the way into a parsed document."""
    return [
        int(index) if index is not None else key
        for index, key in (match.group(1, 2) for match in _SEGMENT.finditer(pointer))
    ]


def parent_pointer(pointer: str) -> str:
    """``a.b[2].c`` -> ``a.b[2]`` -> ``a.b`` -> ``a`` -> ``''``."""
    cut = max(pointer.rfind("."), pointer.rfind("["))
    return pointer[:cut] if cut > 0 else ""
