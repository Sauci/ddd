"""The c backend package."""

from ddd.backends.c.backend import (
    COMPONENT_PLACEHOLDER,
    TEMPLATE_SUFFIX,
    CBackend,
    example_template_directory,
    is_rendered,
)
from ddd.backends.c.options import COptions

__all__ = [
    "COMPONENT_PLACEHOLDER",
    "TEMPLATE_SUFFIX",
    "CBackend",
    "COptions",
    "example_template_directory",
    "is_rendered",
]
