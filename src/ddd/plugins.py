"""What a plugin is, how one is found, and how its hooks are run.

DDD is generic: it knows what a global variable is, who produces it, who reads it and what
the generated c and a2l need to say about it. A project regularly needs one more thing per
variable - a key for a mechanism of its own target, a version tied to the layout, a tag
another tool reads - and that thing is true of that project and of no other. A plugin is how
a project adds it without DDD learning it: a python module the project names, owning one
``extensions`` block on a definition and one on the project, and contributing checks,
comparison rules and an artefact of its own.

This module imports the dictionary and the diagnostics and nothing else at runtime - not the
loader, not the analysis, not a backend - so a plugin sees exactly what a backend sees. The
``Backend`` protocol is structural and is only named here under ``TYPE_CHECKING``.
"""

from __future__ import annotations

import importlib
import importlib.util
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from pydantic import BaseModel

from ddd.diagnostics import PLUGIN_CHECK_SEPARATOR, CheckInfo, DiagnosticBag, Location
from ddd.ir import DataDictionary

if TYPE_CHECKING:
    from ddd.backends.base import Backend

PLUGIN_NAME_PATTERN: Final = re.compile(r"^[a-z][a-z0-9_]*$")
"""A plugin name is the key of its block, so it is a lowercase identifier."""

_CHECK_PATTERN: Final = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
"""The grammar of the part after the separator: the grammar of a built-in identifier."""


@dataclass(frozen=True, slots=True)
class CheckContext:
    """What a check hook receives; a field is added here rather than an argument."""

    dictionary: DataDictionary
    settings: BaseModel | None
    """The project block validated against the plugin's ``project_model``; ``None`` for a
    plugin that declares no project model."""
    bag: DiagnosticBag
    locate: Callable[[str], Location | None]
    """Where a finding about the named object belongs: the producing declaration under
    ``ddd check``, the dump file when the dictionary was read back from one."""


@dataclass(frozen=True, slots=True)
class CompareContext:
    """What a compare hook receives. ``settings`` are the candidate's."""

    baseline: DataDictionary
    candidate: DataDictionary
    settings: BaseModel | None
    bag: DiagnosticBag
    locate: Callable[[str], Location | None]


@dataclass(frozen=True, slots=True)
class GenerateContext:
    """What a backend hook receives; the backend it returns gets the dictionary itself."""

    settings: BaseModel | None
    generator: str
    """The tool name and version the built-in backends put into their banners."""


@dataclass(frozen=True, slots=True)
class Plugin:
    """What a plugin module exposes as ``PLUGIN``.

    Every hook and every model is optional: a plugin with neither model states no block and
    only contributes hooks. The check identifiers are validated here, so a malformed plugin
    fails while its module is imported and is reported as ``plugin-invalid`` with the reason.
    """

    name: str
    """The extension key: the block of this plugin is ``"extensions": {"<name>": {...}}``."""

    object_model: type[BaseModel] | None = None
    """The pydantic model of the block on a definition, or ``None`` for no block there."""

    project_model: type[BaseModel] | None = None
    """The pydantic model of the block on the project, or ``None`` for no block there."""

    checks: tuple[CheckInfo, ...] = ()
    """The checks the hooks report, each identifier spelled ``<name>/<check>``."""

    check: Callable[[CheckContext], None] | None = None
    compare: Callable[[CompareContext], None] | None = None
    backend: Callable[[GenerateContext], Backend] | None = None

    def __post_init__(self) -> None:
        if not PLUGIN_NAME_PATTERN.match(self.name):
            msg = f"plugin name '{self.name}' is not a lowercase identifier"
            raise ValueError(msg)
        prefix = f"{self.name}{PLUGIN_CHECK_SEPARATOR}"
        seen: set[str] = set()
        for info in self.checks:
            identifier = info.identifier
            rest = identifier.removeprefix(prefix)
            if rest == identifier or not _CHECK_PATTERN.match(rest):
                msg = (
                    f"check '{identifier}' of plugin '{self.name}' is not spelled '{prefix}<check>'"
                )
                raise ValueError(msg)
            if identifier in seen:
                msg = f"plugin '{self.name}' registers check '{identifier}' twice"
                raise ValueError(msg)
            seen.add(identifier)


class PluginNotFoundError(Exception):
    """The module a project names cannot be found at all."""


class PluginInvalidError(Exception):
    """The module was found and is not a usable plugin; the message says why."""


def load_plugin(spelling: str, base: Path) -> Plugin:
    """The plugin a project names, by a ``.py`` path relative to ``base`` or a module name.

    The two spellings are the two ways a project keeps a plugin: in its own repository, next
    to the description files, or installed as a distribution. Both go through ``importlib``,
    so nothing is added to the runtime dependencies.
    """
    module = _load_from_path(spelling, base) if spelling.endswith(".py") else _import(spelling)
    plugin = getattr(module, "PLUGIN", None)
    if not isinstance(plugin, Plugin):
        msg = f"plugin '{spelling}' exposes no PLUGIN that is a ddd.plugins.Plugin"
        raise PluginInvalidError(msg)
    return plugin


def _load_from_path(spelling: str, base: Path) -> Any:
    raw = Path(spelling)
    path = (raw if raw.is_absolute() else base / raw).resolve()
    if not path.is_file():
        msg = f"plugin '{spelling}' names '{path.as_posix()}', which does not exist"
        raise PluginNotFoundError(msg)
    # One module object per file, whatever spelling reached it: a second project naming the
    # same file gets the same PLUGIN, which is what lets the loader tell "named twice" from
    # "two plugins claiming one name".
    name = "ddd_plugin_" + re.sub(r"\W", "_", path.as_posix())
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as error:
        msg = f"plugin '{spelling}' failed to import: {error}"
        raise PluginInvalidError(msg) from error
    sys.modules[name] = module
    return module


def _import(spelling: str) -> Any:
    try:
        return importlib.import_module(spelling)
    except ModuleNotFoundError as error:
        # The module itself is missing, or something it imports is: the first is "not
        # found", the second is a plugin that exists and does not work.
        if error.name is not None and spelling.startswith(error.name):
            msg = f"plugin '{spelling}' is not an importable module"
            raise PluginNotFoundError(msg) from error
        msg = f"plugin '{spelling}' failed to import: {error}"
        raise PluginInvalidError(msg) from error
    except Exception as error:
        msg = f"plugin '{spelling}' failed to import: {error}"
        raise PluginInvalidError(msg) from error
