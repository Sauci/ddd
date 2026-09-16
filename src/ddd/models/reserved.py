"""Names a c compiler claims for itself, and which DDD therefore cannot allocate.

This is the one place in :mod:`ddd.models` that spells out c. It has to be: generating c is
not optional - it is the reason DDD exists (SPEC 1.3) - so "this name is usable" is a
property of the *input contract*, checked before any backend runs, rather than something the
c backend discovers while rendering. Keeping the spellings in a module of their own means
the rest of the contract stays free of any output format, and the layering test can say so.

Three families are covered:

* the keywords of C11 and C23, plus what ``<stdbool.h>`` defines,
* everything ``<stdint.h>`` declares, because a project's types header may include it - the
  example templates' one does - and a variable named ``uint16_t`` would then produce the
  definition ``uint16_t uint16_t;``; with it the handful of ``<stddef.h>`` names it pulls in
  on the common toolchains, which are refused for the same reason and were reaching the
  compiler as ``size_t size_t;``,
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

STDDEF_NAMES: Final[frozenset[str]] = frozenset(
    {"NULL", "max_align_t", "offsetof", "ptrdiff_t", "size_t", "wchar_t"}
)
"""What ``<stddef.h>`` declares, which ``<stdint.h>`` brings in with it.

The standard does not require the one header to include the other, so the promise above is
read as what a project's types header actually ends up with: MinGW's ``<stdint.h>`` reaches
these through ``<crtdefs.h>``, and glibc's through ``__need_size_t``. A measurement named
``size_t`` passed every check and then stopped the build with ``'size_t' redeclared as a
different kind of symbol``, which is the compiler saying what belongs here instead.
``errno`` is ``<errno.h>``'s and stays a project's own risk.
"""

# The exact width, least width and fast width sets follow the same three shapes, so they are
# matched by pattern instead of listed one by one. ``_WIDTH`` is C23's; it is reserved here
# although this toolchain does not define it, because the promise is what <stdint.h>
# declares rather than what one compiler got round to.
_STANDARD_TYPE_PATTERN: Final = re.compile(
    r"^u?int(?:_least|_fast)?(?:8|16|32|64)_t$|^u?int(?:max|ptr)_t$"
)
_STANDARD_MACRO_PATTERN: Final = re.compile(
    r"^U?INT(?:_LEAST|_FAST)?(?:8|16|32|64)_(?:MIN|MAX|C|WIDTH)$"
    r"|^U?INT(?:MAX|PTR)_(?:MIN|MAX|C|WIDTH)$"
    r"|^(?:PTRDIFF|SIG_ATOMIC|WCHAR|WINT)_(?:MIN|MAX|WIDTH)$"
    r"|^SIZE_(?:MAX|WIDTH)$"
)


def is_reserved_identifier(name: str) -> bool:
    """Return ``True`` for names a c compiler or a header DDD includes reserves."""
    if name in C_KEYWORDS or name in STDDEF_NAMES:
        return True
    if _STANDARD_TYPE_PATTERN.match(name) or _STANDARD_MACRO_PATTERN.match(name):
        return True
    # C11 7.1.3: an identifier containing a double underscore, or starting with an
    # underscore followed by an uppercase letter, belongs to the implementation.
    if "__" in name:
        return True
    return len(name) >= 2 and name[0] == "_" and name[1].isupper()
