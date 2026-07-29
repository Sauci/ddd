"""The output side of DDD: one package per output format.

Every backend consumes a :class:`~ddd.ir.DataDictionary` and produces files. None of them
imports the loader, the analysis or another backend.
"""

from ddd.backends.a2l import A2lBackend, A2lOptions, ByteOrder, load_address_map
from ddd.backends.base import (
    Backend,
    GeneratedFile,
    WriteResult,
    WriteStatus,
    render,
    write,
)
from ddd.backends.c import CBackend, COptions, example_template_directory

__all__ = [
    "A2lBackend",
    "A2lOptions",
    "Backend",
    "ByteOrder",
    "CBackend",
    "COptions",
    "GeneratedFile",
    "WriteResult",
    "WriteStatus",
    "example_template_directory",
    "load_address_map",
    "render",
    "write",
]
