"""The language server: what an editor needs that a json schema cannot say.

A schema is per file and static. It cannot know that an ``axis`` has to name an axis declared
in another component's file, that exactly one component may produce a name, or that a unit has
to match what every other declarer says. Those are the checks, and the checks need the whole
project resolved - which is what this package brings into the editor.

It does not replace the published schemas. They keep doing structure, this does meaning, and
an editor runs both against one document without either knowing about the other.
"""

from ddd.lsp.diagnostics import analyse, analyse_standalone, collect
from ddd.lsp.discovery import build_files, discover, load_builds
from ddd.lsp.ranges import Document
from ddd.lsp.server import Server, serve, uri_to_path

__all__ = [
    "Document",
    "Server",
    "analyse",
    "analyse_standalone",
    "build_files",
    "collect",
    "discover",
    "load_builds",
    "serve",
    "uri_to_path",
]
