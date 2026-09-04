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
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from pydantic import BaseModel, ValidationError

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
        # found", the second is a plugin that exists and does not work. The boundary is the
        # dotted path, not a raw prefix - "reqplugin" must not match a missing "req".
        if error.name is not None and (
            spelling == error.name or spelling.startswith(error.name + ".")
        ):
            msg = f"plugin '{spelling}' is not an importable module"
            raise PluginNotFoundError(msg) from error
        msg = f"plugin '{spelling}' failed to import: {error}"
        raise PluginInvalidError(msg) from error
    except Exception as error:
        msg = f"plugin '{spelling}' failed to import: {error}"
        raise PluginInvalidError(msg) from error


def resolve_blocks(
    plugins: Mapping[str, Plugin],
    blocks: Mapping[str, Mapping[str, Any]],
    *,
    on_project: bool,
) -> dict[str, dict[str, Any]]:
    """Every block in its resolved form, keyed by plugin name in sorted order.

    Validated against the plugin's model and dumped back to json, so defaults are filled in
    and two dumps compare on one shape. A block no loaded plugin owns, or one the plugin
    declares no model for, is carried as written: the loader has already reported it, and a
    project that relaxed ``unknown-extension`` asked for exactly that.
    """
    resolved: dict[str, dict[str, Any]] = {}
    for name in sorted(blocks):
        plugin = plugins.get(name)
        model = None if plugin is None else _model_of(plugin, on_project=on_project)
        if model is None:
            resolved[name] = dict(blocks[name])
        else:
            resolved[name] = model.model_validate(blocks[name]).model_dump(mode="json")
    return resolved


def _model_of(plugin: Plugin, *, on_project: bool) -> type[BaseModel] | None:
    return plugin.project_model if on_project else plugin.object_model


class PluginError(ValueError):
    """A hook raised, or a plugin's own data does not validate: a defect of the plugin.

    A ``ValueError`` so that the cli reports it the way it reports a template that does not
    render - one line naming the plugin and the hook, exit code 2, no half-written output.
    """


def settings_of(plugin: Plugin, extensions: Mapping[str, Mapping[str, Any]]) -> BaseModel | None:
    """The project block validated against the plugin's project model.

    Built from ``{}`` when the project states none, so that defaults apply; ``None`` for a
    plugin that declares no project model. The loader has validated a stated block already,
    so a failure here comes from a dump - one archived before the plugin required a setting.
    """
    if plugin.project_model is None:
        return None
    try:
        return plugin.project_model.model_validate(extensions.get(plugin.name, {}))
    except ValidationError as error:
        msg = f"the settings of plugin '{plugin.name}' are invalid: {error}"
        raise PluginError(msg) from error


def run_check_hooks(
    plugins: Sequence[Plugin],
    dictionary: DataDictionary,
    bag: DiagnosticBag,
    locate: Callable[[str], Location | None],
) -> None:
    """Run every check hook over the dictionary, in the order the project lists the plugins."""
    for plugin in plugins:
        if plugin.check is not None:
            settings = settings_of(plugin, dictionary.extensions)
            _call(plugin, "check", plugin.check, CheckContext(dictionary, settings, bag, locate))


def _call[C, R](plugin: Plugin, hook: str, function: Callable[[C], R], context: C) -> R:
    try:
        return function(context)
    except Exception as error:
        msg = f"plugin '{plugin.name}' failed in its {hook} hook: {error}"
        raise PluginError(msg) from error
