"""The output side of DDD: one package per output format.

Every backend consumes a :class:`~ddd.ir.DataDictionary` and produces files. None of them
imports the loader, the analysis or another backend.
"""

from ddd.backends.a2l import (
    A2lBackend,
    A2lOptions,
    ByteOrder,
    addressed_symbols,
    load_address_map,
)
from ddd.backends.base import (
    DICTIONARY_ARTEFACT,
    MANIFEST_NAME,
    Backend,
    GeneratedFile,
    Manifest,
    RemovalError,
    WriteResult,
    WriteStatus,
    describe_write_failure,
    render,
    write,
)
from ddd.backends.c import CBackend, COptions, example_template_directory

__all__ = [
    "DICTIONARY_ARTEFACT",
    "MANIFEST_NAME",
    "A2lBackend",
    "A2lOptions",
    "Backend",
    "ByteOrder",
    "CBackend",
    "COptions",
    "GeneratedFile",
    "Manifest",
    "RemovalError",
    "WriteResult",
    "WriteStatus",
    "addressed_symbols",
    "describe_write_failure",
    "example_template_directory",
    "load_address_map",
    "render",
    "write",
]
