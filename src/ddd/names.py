"""The handful of names the command line is *built* out of, and nothing else.

``ddd --version`` and ``ddd --help`` answer before any file is read, and a cmake configure
step and a pre-commit hook pay for that answer once per project and once per file. Everything
else in the package reaches :mod:`ddd.models` sooner or later, and building those contracts is
about a third of a second of work an answer this size has no use for - so the values argparse
needs while it is still deciding what the user asked for live here, in a module that imports
nothing at all.

Each is the one definition of its name rather than a copy of one: the modules that own the
behaviour import their spelling from here, so there is nothing to drift.
"""

from __future__ import annotations

from typing import Final

PLUGIN_NAME_PATTERN: Final = r"^[a-z][a-z0-9_]*$"
"""What a plugin may be called, and therefore how an ``extensions`` block may be keyed.

Lowercase so that the key of a block reads as one word in a description file however the
project spells its own identifiers, and an identifier so that the key is a segment of a
pointer rather than something a consumer has to guess how to split.
"""

BUILT_IN_GENERATED: Final = ("c", "a2l")
"""The artefacts DDD writes itself, each naming one backend of its own.

These are what ``all`` composes beside the plugins', and therefore what a run can be asked to
leave out: subtracting one of them still leaves something to write.
"""

BUILT_IN_ARTEFACTS: Final = (*BUILT_IN_GENERATED, "all")
"""Everything ``ddd generate`` accepts on its own; a plugin's artefact is asked for by the
plugin's name, so a plugin cannot be called any of these."""

SCHEMA_KINDS: Final = (
    "component",
    "constants",
    "dictionary",
    "project",
    "rasters",
    "sections",
    "types",
    "units",
)
"""The file formats ``ddd schema`` publishes, as ``ddd schema <kind>`` spells them.

The models themselves are what ``schema_text`` reads; only their names are needed to build
the parser, and a test holds the two lists together.
"""

BYTE_ORDERS: Final = ("little", "big")
"""What ``ddd generate --byte-order`` accepts, in the order the help offers them.

The first is the default. :class:`ddd.backends.ByteOrder` is the enum that turns one of these
into what the a2l writes, and a test holds the two together.
"""
