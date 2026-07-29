"""Names a c compiler claims for itself, and which DDD therefore cannot allocate.

This is the one place in :mod:`ddd.models` that spells out c. It has to be: generating c is
not optional - it is the reason DDD exists (SPEC 1.3) - so "this name is usable" is a
property of the *input contract*, checked before any backend runs, rather than something the
c backend discovers while rendering. Keeping the spellings in a module of their own means
the rest of the contract stays free of any output format, and the layering test can say so.

Three families are covered:

* the keywords of C11 and C23, plus what ``<stdbool.h>`` defines,
* everything ``<stdint.h>`` declares, because the generated types header includes it - a
  variable named ``uint16_t`` would produce the definition ``uint16_t uint16_t;``,
* the identifiers C11 7.1.3 reserves for the implementation.
"""

from __future__ import annotations

import re
from typing import Final

C_KEYWORDS: Final[frozenset[str]] = frozenset(
    {
        "alignas", "alignof", "auto", "bool", "break", "case", "char", "const",
        "constexpr", "continue", "default", "do", "double", "else", "enum", "extern",
        "false", "float", "for", "goto", "if", "inline", "int", "long", "nullptr",
        "register", "restrict", "return", "short", "signed", "sizeof", "static",
        "static_assert", "struct", "switch", "thread_local", "true", "typedef",
        "typeof", "typeof_unqual", "union", "unsigned", "void", "volatile", "while",
        "_Alignas", "_Alignof", "_Atomic", "_BitInt", "_Bool", "_Complex", "_Decimal32",
        "_Decimal64", "_Decimal128", "_Generic", "_Imaginary", "_Noreturn",
        "_Static_assert", "_Thread_local",
    }
)  # fmt: skip

# The exact width, least width and fast width sets follow the same three shapes, so they are
# matched by pattern instead of listed one by one.
_STANDARD_TYPE_PATTERN: Final = re.compile(
    r"^u?int(?:_least|_fast)?(?:8|16|32|64)_t$|^u?int(?:max|ptr)_t$"
)
_STANDARD_MACRO_PATTERN: Final = re.compile(
    r"^U?INT(?:_LEAST|_FAST)?(?:8|16|32|64)_(?:MIN|MAX|C)$"
    r"|^U?INT(?:MAX|PTR)_(?:MIN|MAX|C)$"
    r"|^(?:PTRDIFF|SIG_ATOMIC|WCHAR|WINT)_(?:MIN|MAX)$"
    r"|^SIZE_MAX$"
)


def is_reserved_identifier(name: str) -> bool:
    """Return ``True`` for names a c compiler or a header DDD includes reserves."""
    if name in C_KEYWORDS:
        return True
    if _STANDARD_TYPE_PATTERN.match(name) or _STANDARD_MACRO_PATTERN.match(name):
        return True
    # C11 7.1.3: an identifier containing a double underscore, or starting with an
    # underscore followed by an uppercase letter, belongs to the implementation.
    if "__" in name:
        return True
    return len(name) >= 2 and name[0] == "_" and name[1].isupper()
