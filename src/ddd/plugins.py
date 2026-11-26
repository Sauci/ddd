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
``Backend`` protocol is structural and is only named here under ``TYPE_CHECKING``: where
``backend_of`` and ``_GuardedBackend.generate`` need to check that a hook kept the promise its
own return type made, they check the same shape by hand instead - a ``name`` and a callable
``generate``, a ``path`` and a ``content`` - rather than importing ``Backend`` or
``GeneratedFile`` just to ask, which would be exactly the runtime coupling this paragraph
says the module has none of.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib
import importlib.util
import inspect
import re
import sys
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from pydantic import BaseModel, ValidationError

from ddd.diagnostics import PLUGIN_CHECK_SEPARATOR, CheckInfo, DiagnosticBag, Location
from ddd.ir import DataDictionary
from ddd.names import BUILT_IN_ARTEFACTS, PLUGIN_NAME_PATTERN

if TYPE_CHECKING:
    from ddd.backends.base import Backend, GeneratedFile

_PLUGIN_NAME: Final = re.compile(PLUGIN_NAME_PATTERN)
"""A plugin name is the key of its block, so it is a lowercase identifier.

Compiled from the spelling the block key itself is held to, so that a name a plugin may
register and a key a description may write it under cannot drift apart."""

_CHECK_PATTERN: Final = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
"""The grammar of the part after the separator: the grammar of a built-in identifier."""


@dataclass(frozen=True, slots=True)
class CheckContext:
    """What a check hook receives; a field is added here rather than an argument."""

    dictionary: DataDictionary
    settings: BaseModel | None
    """The block the project states, validated against the plugin's ``project_model`` - not the
    dictionary's dump of it read back - and built from ``{}`` where the project states none;
    ``None`` for a plugin that declares no project model. Validated once, into the instance
    the dictionary's dump of the settings is written from, of which every hook is handed a
    shallow copy: a field a hook assigns is its own, a nested value it changes in place is
    not, so a hook should change neither."""
    bag: DiagnosticBag
    locate: Callable[[str], Location | None]
    """Where a finding about the named object belongs: the producing declaration under
    ``ddd check``, the dump file when the dictionary was read back from one."""


@dataclass(frozen=True, slots=True)
class CompareContext:
    """What a compare hook receives. ``settings`` are the candidate's: validated from the block a
    candidate project states, and from the block an archived candidate carries."""

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
        if not _PLUGIN_NAME.fullmatch(self.name):
            msg = f"plugin name '{self.name}' is not a lowercase identifier"
            raise ValueError(msg)
        if self.name in BUILT_IN_ARTEFACTS:
            msg = f"plugin name '{self.name}' is the name of a built-in artefact of ddd generate"
            raise ValueError(msg)
        prefix = f"{self.name}{PLUGIN_CHECK_SEPARATOR}"
        seen: set[str] = set()
        for info in self.checks:
            identifier = info.identifier
            rest = identifier.removeprefix(prefix)
            if rest == identifier or not _CHECK_PATTERN.fullmatch(rest):
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
    try:
        # A module may compute its attributes (`__getattr__`), and that is plugin code, run here
        # as much as its body was at import: what it raises is the plugin's failure. An
        # attribute it does not have is the default, as `getattr` gives it.
        with _stdout_on_stderr():
            plugin = getattr(module, "PLUGIN", None)
    except KeyboardInterrupt:
        raise
    except BaseException as error:
        detail = _exit_text(error) if isinstance(error, SystemExit) else str(error)
        msg = f"plugin '{spelling}' failed to read PLUGIN: {detail}"
        raise PluginInvalidError(msg) from error
    if not isinstance(plugin, Plugin):
        msg = f"plugin '{spelling}' exposes no PLUGIN that is a ddd.plugins.Plugin"
        raise PluginInvalidError(msg)
    return plugin


def plugin_files(spelling: str, base: Path, *, run_plugins: bool = True) -> tuple[Path, ...]:
    """The files a plugin the project names is made of, for the dependency list of a build system.

    What the project names, whether or not the import went well: a path spelling names its
    file, which a build has to keep watching while it does not import - the edit that repairs
    it is the one to run the generation again - and a module spelling has the file its import
    recorded, which a module that failed to import, or one planted into ``sys.modules`` without
    one, lacks; where the import failed, the file the finder locates for it stands in, which
    a top level name gives without running it. A package is every ``.py`` file under its
    directory, not its ``__init__.py`` alone: the module its ``PLUGIN`` comes from, and the
    shared code a plugin keeps beside it, are plugin code as much as the file that imports
    them. Nothing of the plugin is imported here.

    ``run_plugins`` false is a run that runs no plugin (``--no-plugins``), where nothing may run
    to find a file either: a module spelling is the file the finder locates for a top level
    name, and nothing for a dotted one, whose packages the finder imports to locate it.
    """
    if spelling.endswith(".py"):
        try:
            source: Path | None = _path_of(spelling, base)
        except PluginNotFoundError:
            source = None
    elif not run_plugins:
        located = None if "." in spelling else _located(spelling)
        source = Path(located).resolve() if located else None
    else:
        recorded = getattr(sys.modules.get(spelling), "__file__", None) or _located(spelling)
        source = Path(recorded).resolve() if recorded else None
    if source is None:
        return ()
    if source.name != "__init__.py":
        return (source,)
    return tuple(sorted(path.resolve() for path in source.parent.rglob("*.py")))


_RUN_FROM: Final[dict[str, str]] = {}
"""The SHA-256, in hex, of the bytes each module :func:`_load_from_path` ran was read from, by the
name ``sys.modules`` holds it under: what :func:`changed_since_imported` compares its file with.
Kept once the module has run, so that one whose body failed, which no load hands out, has none."""


def changed_since_imported(path: Path) -> bool:
    """Whether a load of the plugin file ``path`` - resolved, as :func:`plugin_files` names a path
    spelling's file - hands out a module run from other bytes than the file holds now.

    A module is imported once per process: the first load of a file runs it, and every later one,
    whatever spelling reaches the file, hands that module out again (:func:`_load_from_path`), so
    a plugin edited since runs its old code until the process starts again. ``ddd gui``, which
    runs for as long as its reader works, asks this of every plugin its project names by its path
    and says so (``plugin-changed``); ``ddd check`` imports afresh, in a process of its own.

    Told by the bytes, never by a stamp: the same bytes written again are no change. False for a
    file no module was run from - never loaded, or one whose module failed to run, which the next
    load runs afresh - and for one that is gone, which a load reports as not found rather than
    hand its module out; true for one that cannot be read now, whose module a load still hands out
    where an import afresh would fail to read it. Two statements rather than one condition for the
    first two, so that coverage counts a branch for each.
    """
    imported = _RUN_FROM.get(_module_name(path))
    if imported is None:
        return False
    if not path.is_file():
        return False
    try:
        held = path.read_bytes()
    except OSError:
        return True
    return hashlib.sha256(held).hexdigest() != imported


def _located(spelling: str) -> str | None:
    """Where the finder says the module ``spelling`` is, without running it.

    A module that failed to import is in no ``sys.modules``, and the file it is in is what a
    build has to go on watching. A dotted name imports its parents to be located, which runs
    their code, so whatever that raises - a parent that does not import either - is no
    location: nothing is known of it.
    """
    try:
        found = importlib.util.find_spec(spelling)
    except (Exception, SystemExit):
        return None
    origin = None if found is None else found.origin
    return origin if origin is not None and origin.endswith(".py") else None


def _path_of(spelling: str, base: Path) -> Path:
    """The file a path spelling names, resolved; a path the system refuses to resolve - one
    holding a NUL, or a loop of links - names none, as a path to nothing does."""
    raw = Path(spelling)
    try:
        return (raw if raw.is_absolute() else base / raw).resolve()
    except (OSError, ValueError, RuntimeError) as error:
        msg = f"plugin '{spelling}' names a path that cannot be resolved: {error}"
        raise PluginNotFoundError(msg) from error


def _exit_text(error: SystemExit) -> str:
    """``SystemExit(0)``, ``SystemExit(None)`` or ``SystemExit('bye')`` - ``str()`` alone
    loses the distinction: ``str(SystemExit(0))`` is just ``'0'``, indistinguishable from a
    hook that raised ``ValueError('0')``."""
    return f"SystemExit({error.code!r})"


def _module_name(path: Path) -> str:
    """The name ``sys.modules`` holds the module of the plugin file ``path`` under, ``path``
    resolved (:func:`_load_from_path` says why it is this one).

    Digested as UTF-8 with lone surrogates passed through, so that a path naming a directory or a
    file in no UTF-8 - one named in Latin-1, as an old archive leaves one, which python spells with
    a lone surrogate on a POSIX system, and NTFS can hold - names a module as any other does, where
    a strict encode raised; the name of every other path is what that encode gave."""
    digest = hashlib.sha256(path.as_posix().encode("utf-8", "surrogatepass")).hexdigest()[:16]
    return f"ddd_plugin_{re.sub(r'\W', '_', path.stem)}_{digest}"


@contextlib.contextmanager
def _stdout_on_stderr() -> Iterator[None]:
    """Bind ``sys.stdout`` to ``sys.stderr`` while a plugin's own code runs.

    stdout is a document wherever DDD writes one there - the ``--format json`` report, the
    dictionary ``dump`` prints, the list ``sources`` prints - and ``dump -o`` promises it empty,
    so a ``print`` of the plugin's would otherwise be read as part of one. It is redirected
    rather than swallowed: what a plugin says is still its author's to read, on the stream every
    other word this tool writes about a run goes to. Every place DDD runs a plugin's code is
    held to it: the import of the module, each validation against, and copy of, one of its
    models, the rendering of their schema, and each hook (:func:`_call`). ``sys.stderr`` is read
    on entry, so a caller that replaced either stream is followed rather than bypassed.

    ``contextlib.redirect_stdout`` rebinds ``sys.stdout`` for every thread, not only the
    caller's, for as long as it lasts, and rebinds no more: a child process, ``os.write(1, ...)``
    and ``sys.__stdout__`` are the plugin's to keep off stdout.
    """
    with contextlib.redirect_stdout(sys.stderr):
        yield


def _load_from_path(spelling: str, base: Path) -> Any:
    path = _path_of(spelling, base)
    if not path.is_file():
        msg = f"plugin '{spelling}' names '{path.as_posix()}', which does not exist"
        raise PluginNotFoundError(msg)
    # One module object per file, whatever spelling reached it: a second project naming the
    # same file gets the same PLUGIN, which is what lets the loader tell "named twice" from
    # "two plugins claiming one name".
    # Keyed on a digest of the path rather than on a sanitised spelling of it, which folded
    # 'my-plugin.py' and 'my_plugin.py' into one name and handed the second the first's module.
    name = _module_name(path)
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Registered before it runs, as importlib's own recipe does: a module body that needs
    # itself in sys.modules already - a dataclass under `from __future__ import annotations`
    # resolving its own forward references, for one - would otherwise find nothing there.
    sys.modules[name] = module
    try:
        # Read before the module runs, for the bytes it is kept as run from (`_RUN_FROM`): a
        # save landing between this read and the loader's own is then told a change the module
        # does not hold - a restart asked for in vain - and never a change it holds told as none.
        # Inside the guard, so that a file that cannot be read fails to import as it always has.
        source = path.read_bytes()
        with _stdout_on_stderr():
            spec.loader.exec_module(module)
    except KeyboardInterrupt:
        # Not this plugin's error to own, and still has to interrupt. Only the cache is this
        # function's business: left registered, a second load in the same process (the language
        # server re-analysing after every keystroke) would find a module that never finished
        # running and skip re-running its body at all, rather than trying again.
        sys.modules.pop(name, None)
        raise
    except BaseException as error:
        # Not left cached half-run: a second load must retry it and report again, rather than
        # hand out a module whose body never finished. Everything else a body can raise, more
        # than `Exception`, is the plugin's failure and is reported as one: `SystemExit`, from a
        # body that calls sys.exit(...) - deliberately, or by copying a script's own __main__
        # guard - naming the code it exited with rather than the empty or misleading text
        # str(SystemExit(...)) would give, and a `BaseException` of any other kind, an
        # `asyncio.CancelledError` or one the plugin declared itself, which ended `ddd check` in
        # a traceback under the findings exit code.
        sys.modules.pop(name, None)
        raise PluginInvalidError(_import_failure(spelling, error)) from error
    _RUN_FROM[name] = hashlib.sha256(source).hexdigest()
    return module


def _import(spelling: str) -> Any:
    try:
        with _stdout_on_stderr():
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
    except KeyboardInterrupt:
        raise
    except BaseException as error:
        # More than `Exception`, as in `_load_from_path`: a plugin package whose __init__ calls
        # sys.exit(...), or raises a `BaseException` of its own, is reported as the plugin's
        # failure and no other way. Unlike there, nothing here has registered the module into
        # sys.modules by hand, so there is no cache to unwind on the way out - import_module
        # leaves none behind itself, on a failure of either kind.
        raise PluginInvalidError(_import_failure(spelling, error)) from error


def _import_failure(spelling: str, error: BaseException) -> str:
    """What an import that raised ``error`` is reported as: the code a ``SystemExit`` carries, or
    the text of any other."""
    if isinstance(error, SystemExit):
        return f"plugin '{spelling}' exited during import: {_exit_text(error)}"
    return f"plugin '{spelling}' failed to import: {error}"


def resolve_blocks(
    plugins: Mapping[str, Plugin],
    blocks: Mapping[str, Mapping[str, Any]],
    *,
    on_project: bool,
    validated: Mapping[str, BaseModel] | None = None,
) -> dict[str, dict[str, Any]]:
    """Every block in its resolved form, keyed by plugin name in sorted order.

    Validated against the plugin's model and dumped back to json, so defaults are filled in
    and two dumps compare on one shape. Dumped by alias, so that a block is keyed in the
    dictionary as its file keys it, and for a round trip, which leaves a computed field out:
    a hook reading a block from the dictionary, and a comparison reading an archived one back,
    hand the model what it reads. A block no loaded plugin owns, or one the plugin
    declares no model for, is carried as written: the loader has already reported it, or the
    plugins a run did not run (``plugin-skipped``), one of which may own it, and a project that
    relaxed ``unknown-extension`` asked for exactly that. On the project, every
    plugin that declares a project model appears, with its defaults, whether or not the
    project stated a block for it: the dictionary carries each plugin's settings.

    ``validated`` are the instances the loader validated a project's blocks into, by plugin
    name (:attr:`~ddd.loading.Workspace.project_settings`): a block one of them holds is dumped
    from it rather than validated again, so that the dictionary holds the value every hook is
    handed, a default drawn afresh included. Any other block is validated here: a definition's,
    whose instance no hook is handed, and a project's that the loader holds none of, which only
    a hover over a project that did not read cleanly meets.
    """
    held: Mapping[str, BaseModel] = {} if validated is None else validated
    resolved: dict[str, dict[str, Any]] = {}
    try:
        for name in blocks:
            plugin = plugins.get(name)
            model = None if plugin is None else block_model(plugin, on_project=on_project)
            if model is None:
                resolved[name] = dict(blocks[name])
            else:
                with guarding_plugin_model(name, "validating a block against its own model"):
                    instance = held[name] if name in held else model.model_validate(blocks[name])
                    resolved[name] = instance.model_dump(
                        mode="json", by_alias=True, round_trip=True
                    )
        if on_project:
            for name, plugin in plugins.items():
                if name not in resolved and plugin.project_model is not None:
                    with guarding_plugin_model(name, "building the defaults of its settings"):
                        instance = (
                            held[name] if name in held else plugin.project_model.model_validate({})
                        )
                        resolved[name] = instance.model_dump(
                            mode="json", by_alias=True, round_trip=True
                        )
    except ValidationError as error:
        # The loader has validated every block a run of the checks reaches; a hover resolves
        # a project that did not read cleanly, and its blocks are then the plugin's problem.
        msg = f"a block of plugin '{name}' does not validate: {error}"
        raise PluginError(msg) from error
    return dict(sorted(resolved.items()))


def block_model(plugin: Plugin, *, on_project: bool) -> type[BaseModel] | None:
    """The model a plugin validates a block with: the project's, or a definition's."""
    return plugin.project_model if on_project else plugin.object_model


class PluginError(ValueError):
    """A hook raised, or a plugin's own data does not validate: a defect of the plugin.

    A ``ValueError`` so that the cli reports it the way it reports a template that does not
    render - one line naming the plugin and the hook, exit code 2, no half-written output.
    """


@contextlib.contextmanager
def guarding_plugin_model(name: str, what: str) -> Iterator[None]:
    """Run a plugin's own pydantic model, turning a defect in it into a :class:`PluginError`.

    A model is plugin code as much as a hook is: a ``@field_validator`` runs whenever DDD
    validates a block against it, and it may do anything a hook may do. Only the two verdicts
    pydantic itself defines - a ``ValueError`` or an ``AssertionError`` from a validator - come
    back as a ``ValidationError``; that one is the plugin *user's* mistake, a finding about
    their block, and is re-raised untouched for the caller to report as one. Anything else the
    model raises is the plugin author's mistake and reached the caller raw: a ``RuntimeError``
    ended ``ddd check`` in a traceback, and a ``sys.exit`` in a validator ended it with the
    plugin's own exit code, printing none of the findings, and took the language server down
    with it. Both are wrapped here the way :func:`_call` wraps a hook - and so is a
    ``BaseException`` of any other kind, for the same reason - so that the cli reports one
    line and exit 2 and the server reports ``plugin-invalid`` and keeps running.
    ``KeyboardInterrupt`` is deliberately re-raised, exactly as in :func:`_call`.
    """
    try:
        with _stdout_on_stderr():
            yield
    except (ValidationError, KeyboardInterrupt):
        raise
    except BaseException as error:
        detail = _exit_text(error) if isinstance(error, SystemExit) else str(error)
        msg = f"plugin '{name}' failed {what}: {detail}"
        raise PluginError(msg) from error


def settings_of(plugin: Plugin, extensions: Mapping[str, Mapping[str, Any]]) -> BaseModel | None:
    """The plugin's block in ``extensions`` validated against its project model.

    ``extensions`` are the blocks an archived dictionary carries, by plugin name, which are all
    there is of its settings: a project's blocks are validated once, by the loader, and every
    hook over the project is handed a copy of that instance
    (:meth:`~ddd.loading.Workspace.settings`).
    Built from ``{}`` where the plugin has none there, so that defaults apply; ``None`` for a
    plugin that declares no project model. A failure here therefore comes from an archive: one
    dumped before the plugin required a setting, or by a model that does not read back its own
    dump.
    """
    if plugin.project_model is None:
        return None
    try:
        with guarding_plugin_model(plugin.name, "validating its settings"):
            return plugin.project_model.model_validate(extensions.get(plugin.name, {}))
    except ValidationError as error:
        msg = f"the settings of plugin '{plugin.name}' are invalid: {error}"
        raise PluginError(msg) from error


def run_check_hooks(
    plugins: Sequence[Plugin],
    dictionary: DataDictionary,
    settings: Callable[[Plugin], BaseModel | None],
    bag: DiagnosticBag,
    locate: Callable[[str], Location | None],
) -> None:
    """Run every check hook over the dictionary, in the order the project lists the plugins.

    ``settings`` is what each hook is handed for its plugin: a copy of the instance the
    project's block was validated into, once (:meth:`~ddd.loading.Workspace.settings`),
    never the dictionary's dump of it read back - a model reads its dump back only as far as
    the dump keeps what it read, and the block the loader took is what the hook is owed.
    """
    for plugin in plugins:
        if plugin.check is not None:
            context = CheckContext(dictionary, settings(plugin), bag, locate)
            _returns_nothing(plugin, "check", _call(plugin, "check", plugin.check, context))


def run_compare_hooks(
    plugins: Sequence[Plugin],
    baseline: DataDictionary,
    candidate: DataDictionary,
    settings: Callable[[Plugin], BaseModel | None],
    bag: DiagnosticBag,
    locate: Callable[[str], Location | None],
    location: Location | None,
    baseline_location: Location | None = None,
    *,
    skipped: Sequence[str] = (),
) -> None:
    """Run every compare hook, after saying which recorded plugin is not among ``plugins``.

    ``settings`` is what each hook is handed for its plugin, the candidate's: a copy of the
    instance its project's block was validated into, or, for an archived dictionary, the
    block it carries validated against the plugin's project model (:func:`settings_of`).

    A comparison that silently skipped a rule would be a confident "can replace" with a hole
    in it; ``missing-plugin`` is what closes the hole, once per plugin and side. Each side's
    finding is located at the file that records the plugin - ``baseline_location`` is the
    baseline's, and defaults to the candidate's for a caller that has no separate place for
    it - because a finding about the baseline pointing at the candidate sends the reader to a
    file that does not name the plugin the message is about.

    The comparison hooks are the candidate's, so a plugin the baseline names and the
    candidate does not is one this run may perfectly well have loaded - it ran for the
    baseline's own analysis - and whose comparison rules still did not run. That side's
    message says what is not in play rather than claiming the run never loaded it; the
    candidate's side, where the run really has not, says so.

    ``skipped`` are the plugins the candidate names and its read did not run, as ``--no-plugins``
    asks (:attr:`~ddd.deliveries.Resolved.skipped`). A plugin's name is known once it ran, so
    while one was skipped any plugin the baseline records may be it, and none is said to be
    missing from the candidate; ``plugin-skipped`` has said that it did not run.
    """
    loaded = {plugin.name for plugin in plugins}
    sides = (
        # The baseline's own plugins may perfectly well have been loaded - by its analysis,
        # when it is given as a description - and their comparison rules still did not run,
        # because the rules in play are the candidate's. Saying "this run has not loaded" of
        # a plugin the run had just imported and run is what the wording avoids; on the
        # candidate's side the run really has not loaded it, and says so.
        (
            "baseline",
            baseline,
            baseline_location or location,
            "is not among the candidate's plugins",
        ),
        ("candidate", candidate, location, "this run has not loaded"),
    )
    for side, dictionary, where, why in sides:
        if side == "baseline" and skipped:
            continue
        for name in dictionary.plugins:
            if name not in loaded:
                bag.add(
                    "missing-plugin",
                    f"the {side} was produced with plugin '{name}', which {why}; its "
                    f"comparison rules did not run",
                    where,
                )
    for plugin in plugins:
        if plugin.compare is not None:
            context = CompareContext(baseline, candidate, settings(plugin), bag, locate)
            _returns_nothing(plugin, "compare", _call(plugin, "compare", plugin.compare, context))


def backend_of(plugin: Plugin, settings: BaseModel | None, generator: str) -> Backend:
    """The backend a plugin provides, or a usage error saying it provides none or provides one
    only in name.

    The hook is handed ``settings``, a copy of the instance the project's block was validated
    into, as a check hook is (:func:`run_check_hooks`).

    A hook's own signature says it returns a ``Backend``, but nothing stops it returning
    ``None`` - the shape a hook that only checks its settings and forgets to build one tends
    to take - or returning something else entirely; python does not enforce a return type at
    runtime. Both are the plugin's own mistake rather than ddd's, so both are reported the way
    a hook that raised already is, rather than surfacing later as an ``AttributeError`` out of
    :class:`_GuardedBackend` or :func:`~ddd.backends.base.render`. The check below is the
    ``Backend`` protocol's own check, written out by hand rather than as
    ``isinstance(backend, Backend)`` - see the module docstring for why.
    """
    if plugin.backend is None:
        msg = f"plugin '{plugin.name}' provides no artefact"
        raise ValueError(msg)
    context = GenerateContext(settings, generator)
    backend = _call(plugin, "backend", plugin.backend, context)
    if backend is None:
        msg = f"plugin '{plugin.name}' returned no backend from its backend hook"
        raise PluginError(msg)
    name = _read(plugin, backend, "name")
    if not isinstance(name, str) or not callable(_read(plugin, backend, "generate")):
        msg = (
            f"plugin '{plugin.name}' returned something other than a backend from its "
            f"backend hook: {type(backend).__name__}"
        )
        raise PluginError(msg)
    return _GuardedBackend(plugin, backend, name)


def _read(plugin: Plugin, backend: object, attribute: str) -> object:
    """``backend.attribute`` as ``getattr`` reads it, ``None`` for one it has not; a read is plugin
    code too - a property runs - and what it raises is the plugin's failure, a
    :class:`PluginError`, as the hook's own is. The interrupt still interrupts."""
    try:
        with _stdout_on_stderr():
            return getattr(backend, attribute, None)
    except KeyboardInterrupt:
        raise
    except BaseException as error:
        detail = _exit_text(error) if isinstance(error, SystemExit) else str(error)
        msg = f"plugin '{plugin.name}' failed reading the {attribute} of its backend: {detail}"
        raise PluginError(msg) from error


def _has_the_shape_of_a_generated_file(item: object) -> bool:
    """The ``GeneratedFile`` protocol check, written out by hand for the same reason
    ``backend_of`` writes the ``Backend`` one out by hand: a ``path`` that is a real ``Path``
    and a ``content`` that is a real ``str`` is everything the dataclass is, and everything
    :func:`~ddd.backends.base.render` and :func:`~ddd.backends.base.write` go on to use."""
    return isinstance(getattr(item, "path", None), Path) and isinstance(
        getattr(item, "content", None), str
    )


class _GuardedBackend:
    """A plugin's backend, with ``generate`` guarded the way its other hooks already are.

    ``backend_of`` wraps the factory in ``_call``, but the backend it returns used to run
    unwrapped under :func:`ddd.backends.base.render` - the one place a plugin's own code
    executed outside a hook. This closes that gap: ``generate`` runs through ``_call`` too, so
    a defect there is reported the same way, as a ``PluginError`` naming the plugin and the
    hook rather than a raw traceback. ``name`` and ``generate`` are exactly what the
    ``Backend`` protocol asks for, so this satisfies it structurally without naming it.
    """

    def __init__(self, plugin: Plugin, backend: Backend, name: str) -> None:
        self._plugin = plugin
        self._backend = backend
        self.name = name

    def generate(self, dictionary: DataDictionary, output_dir: Path) -> list[GeneratedFile]:
        result = _call(
            self._plugin,
            "generate",
            lambda _: self._backend.generate(dictionary, output_dir),
            None,
        )
        # Checked here, outside _call, rather than inside the lambda: raised from there, a
        # PluginError would be caught by _call's own except clause and rewrapped as "failed in
        # its generate hook", burying this message inside that one instead of standing alone.
        if not isinstance(result, list) or not all(
            _has_the_shape_of_a_generated_file(item) for item in result
        ):
            msg = (
                f"plugin '{self._plugin.name}' returned something other than a list of "
                "generated files from its generate hook"
            )
            raise PluginError(msg)
        return result


def _returns_nothing(plugin: Plugin, hook: str, returned: object) -> None:
    """Refuse what a ``check`` or a ``compare`` hook returned, which is nothing: it reports through
    the bag.

    Python does not enforce a return type, and a hook that returns its findings, that is a
    generator or that is ``async`` ran none of what it was written to run - calling one only makes
    the list, the generator or the coroutine - so the rule it was meant to apply never did, and a
    run that passes reads as one the rule passed. A coroutine is closed first, so that no
    "never awaited" warning follows the failure that explains it.
    """
    if returned is None:
        return
    reason = "a hook reports with context.bag.add, and returns nothing"
    if inspect.iscoroutine(returned):
        returned.close()
        what = "a coroutine"
        reason = "a hook is called and never awaited, so declare it with def, not async def"
    elif inspect.isgenerator(returned):
        what = "a generator"
        reason = "a hook is called and never iterated, so its body does not run: do not yield"
    else:
        what = _article(type(returned).__name__)
    msg = f"plugin '{plugin.name}' returned {what} from its {hook} hook: {reason}"
    raise PluginError(msg)


def _article(name: str) -> str:
    return f"{'an' if name[:1] in 'aeiouAEIOU' else 'a'} {name}"


def _call[C, R](plugin: Plugin, hook: str, function: Callable[[C], R], context: C) -> R:
    try:
        # A hook runs with stdout bound to stderr, which is the arrangement `ddd lsp` already
        # makes before a plugin can reach the json-rpc wire (`serve`). stdout is a document on
        # the command line too - the `--format json` report, the dictionary `dump` prints - and
        # is promised empty by `dump -o`; a `print` left in a hook would otherwise land inside
        # one of them and a build's `json.loads` would fail on it. Redirected rather than
        # swallowed: what a plugin says is still its author's to read, on the stream every
        # other word this tool writes about a run goes to. `sys.stderr` is read here, at each
        # call, so a caller that replaced either stream is followed rather than bypassed.
        with _stdout_on_stderr():
            return function(context)
    except KeyboardInterrupt:
        # The user's own Ctrl-C, and never the plugin's error to be blamed for: it has to
        # keep stopping the run. `main` turns it into one line and exit 130.
        raise
    except BaseException as error:
        # Everything else a hook can raise, which is more than `Exception`: `SystemExit` from
        # a hook calling sys.exit() - deliberately, or by copying a script's own __main__
        # guard - would otherwise take ddd check's exit code and print none of the run's
        # findings, and kill the language server outright; and a BaseException of a third
        # kind, `asyncio.CancelledError` or one the plugin declared itself, escaped as a
        # traceback under the findings exit code. Both are a defect of the plugin like any
        # other here, and are reported as one.
        detail = _exit_text(error) if isinstance(error, SystemExit) else str(error)
        msg = f"plugin '{plugin.name}' failed in its {hook} hook: {detail}"
        raise PluginError(msg) from error
