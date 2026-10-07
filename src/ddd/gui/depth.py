"""How deep json may nest in ``ddd gui``, and every rule that keeps a request and an answer within
it.

Two counts, each without recursion, so that no value is too deep to count. :func:`text_depth`
counts json text before anything parses it - a query's value, an edit's - against
:data:`MAX_DEPTH`. :func:`nesting` counts a value already parsed the way pydantic-core's serializer
counts it, against :data:`SERIALIZED_DEPTH`: the most levels that serializer writes on every
system ``ddd gui`` runs on, past which it gives up writing an answer - ``ValueError: Circular
reference detected (depth exceeded)`` - which was answered ``500``.

Every answer is written through :func:`written`, which counts it first and refuses one deeper than
that. A test reads ``api.py``'s syntax tree, and fails on a ``Reply`` there whose body is neither
one the net wrote nor ``_error``'s two strings, and on any naming there of pydantic's dumps -
``model_dump``, ``model_dump_json``, ``dump_python`` or ``dump_json`` as an attribute of
anything, called or not, as a name or as a string, and pydantic 1's ``dict`` and ``json`` as an
attribute - but two reading a plan's own query: so a route added later is held to the net as
every route there is, in whichever of these ways it would dump its answer. It does not read
pydantic-core's own functions, a model's ``__pydantic_serializer__``, pydantic 1's dumps asked for
by a string, or a dump's name put together at run time. Where a description file is to blame, its
own route refuses it first, naming the file: ``GET /api/file`` past :data:`FILE_DEPTH`
(:func:`file_too_deep`), and ``GET /api/dictionary`` for an extension block past
:data:`PROJECT_BLOCK_DEPTH` or :data:`OBJECT_BLOCK_DEPTH` (:func:`block_too_deep`).
"""

from __future__ import annotations

import types
import typing
from collections.abc import Iterable, Sequence
from enum import Enum
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from pydantic import BaseModel

from ddd.editing import INVALID, EditError, not_one_value
from ddd.loading import NESTED_TOO_DEEPLY, read_json_document

if TYPE_CHECKING:
    from ddd.gui import contract
    from ddd.gui.session import Revision
    from ddd.ir import ResolvedInstance, ResolvedObject

MAX_DEPTH: Final = 64
"""The deepest json a query carries, and the deepest value an edit writes (``POST /api/edit``):
a description nests a value five or six levels down."""

SERIALIZED_DEPTH: Final = 99
"""How many levels of an answer pydantic-core's serializer writes on every system ``ddd gui`` runs
on, counted as :func:`nesting` counts them: 99 on Windows, 255 elsewhere - its recursion guard is
set per platform (``recursion_guard.rs``) - and so 99 everywhere, as the device names are refused
on every system alike. A test measures the running serializer against it on each CI leg."""

FILE_DEPTH: Final = SERIALIZED_DEPTH
"""The deepest description file ``GET /api/file`` answers: :data:`SERIALIZED_DEPTH`, less the
levels its answer puts around the file's json, which are none -
:attr:`~ddd.gui.contract.FileContent.data` is the untyped field itself. Measured: a file 255 levels
deep was answered on Linux and one 256 deep was not, and the running serializer is measured to
carry 99 on every system."""

PROJECT_BLOCK_DEPTH: Final = SERIALIZED_DEPTH - 1
"""The deepest extension block of the project's own settings ``GET /api/dictionary`` answers:
:data:`SERIALIZED_DEPTH`, less the one level its answer puts around such a block - the
dictionary's ``extensions``, keyed by plugin; the dictionary itself is a typed mapping of the
answer, which the serializer does not count. Measured on Linux: 254 answered, 255 not."""

OBJECT_BLOCK_DEPTH: Final = SERIALIZED_DEPTH - 3
"""The deepest extension block of an object ``GET /api/dictionary`` answers:
:data:`SERIALIZED_DEPTH`, less the three levels its answer puts around such a block - the
dictionary's ``objects``, or its ``instances`` for a structured object, the object itself, and its
``extensions``. Measured on Linux: 252 answered, 253 not."""

TOO_DEEP: Final = "deeper than ddd gui can show"
"""How every refusal of a value too deep to answer ends."""


class TooDeepError(Exception):
    """An answer nested deeper than the serializer writes, refused before anything writes it:
    ``409``, in this one sentence."""

    def __init__(self) -> None:
        super().__init__(
            f"this answer is nested more than {SERIALIZED_DEPTH} levels deep, {TOO_DEEP}"
        )


def text_depth(text: str) -> int:
    """How deep ``text``'s brackets nest, outside its strings: counted in one pass over the
    characters, so a text of any depth costs no stack. A backslash in a string escapes the
    character after it, a quote included."""
    deepest = depth = 0
    quoted = escaped = False
    for character in text:
        if quoted:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
        elif character == '"':
            quoted = True
        elif character in "[{":
            depth += 1
            deepest = max(deepest, depth)
        elif character in "]}":
            depth -= 1
    return deepest


def nesting(value: object) -> int:
    """How many levels pydantic-core's serializer counts writing ``value`` in an untyped field:
    every value along the deepest way down, a number, a string or ``None`` as much as an array or
    an object, and no key. ``0`` and ``[]`` are one level each, ``[0]`` and ``{"a": 0}`` two."""
    deepest = 0
    unseen: list[tuple[object, int]] = [(value, 1)]
    while unseen:
        item, level = unseen.pop()
        deepest = max(deepest, level)
        if isinstance(item, dict):
            unseen.extend((child, level + 1) for child in item.values())
        elif isinstance(item, list | tuple | set | frozenset):
            unseen.extend((child, level + 1) for child in item)
    return deepest


_UNTYPED: Final = object()
"""What a value in an untyped field is read as: every value of it counted."""


def counted(answer: BaseModel) -> int:
    """How many levels the serializer counts writing ``answer``, or more - never fewer.

    An untyped field - ``Any``, the values of a ``dict[str, Any]`` - is counted as :func:`nesting`
    counts it, as the serializer does. A typed mapping, tuple or list is not counted, nor a typed
    number, string or literal, as the serializer counts none of them. A model nested in another is
    counted one level, which the serializer counts only where it reaches the model through a
    definition it shares with another field: always counting it is what makes this a bound rather
    than an estimate, and so is reading a union of several kinds as an untyped value. The answer
    itself is not counted, as the serializer does not count the model it was asked to write.

    The serializer counts a shared definition that is not a model as well - a type alias a model
    uses in more than one place - a level at each place it passes through one, and this counts
    none. So the bound rests on the models an answer is written from sharing no such definition
    but ``InitElement`` and ``InitScalar``, an object's ``init``, which this reads as unions of
    several kinds, untyped, every value under them counted: a test lists every one there is, and
    fails when another appears."""
    deepest = 0
    unseen: list[tuple[object, object, int]] = _fields_of(answer, 0)
    while unseen:
        value, annotation, above = unseen.pop()
        kind = _kind(annotation)
        if kind is _UNTYPED:
            level = above + 1
            deepest = max(deepest, level)
            if isinstance(value, BaseModel):
                unseen.extend(_fields_of(value, level))
            elif isinstance(value, dict):
                unseen.extend((child, _UNTYPED, level) for child in value.values())
            elif isinstance(value, list | tuple | set | frozenset):
                unseen.extend((child, _UNTYPED, level) for child in value)
        elif isinstance(value, BaseModel):
            deepest = max(deepest, above + 1)
            unseen.extend(_fields_of(value, above + 1))
        elif isinstance(value, dict):
            unseen.extend(_typed(value.values(), (_argument(kind, 1),), above))
        elif isinstance(value, list | tuple | set | frozenset):
            unseen.extend(_typed(value, _items(kind), above))
    return deepest


def written(answer: BaseModel, **options: Any) -> dict[str, Any]:
    """``answer`` as json, the way every answer of ``ddd gui`` is written: counted first
    (:func:`counted`), and refused - :class:`TooDeepError` - where it nests deeper than
    :data:`SERIALIZED_DEPTH`, rather than failing half-way through being written. ``options`` are
    the dump's own, ``by_alias`` among them."""
    if counted(answer) > SERIALIZED_DEPTH:
        raise TooDeepError
    return answer.model_dump(mode="json", **options)


def file_too_deep(path: Path, data: object) -> str | None:
    """The refusal of a description file nested deeper than ``GET /api/file`` answers
    (:data:`FILE_DEPTH`), naming it - or ``None`` where it fits."""
    if nesting(data) > FILE_DEPTH:
        return f"{path.name} is nested more than {FILE_DEPTH} levels deep, {TOO_DEEP}"
    return None


def block_too_deep(revision: Revision) -> str | None:
    """The refusal of the first extension block of ``revision``'s dictionary nested deeper than
    ``GET /api/dictionary`` answers one, naming the file that states it - or ``None`` where every
    block fits, as where there is no dictionary.

    The blocks are the part of a dictionary a description file writes as it likes - carried as
    the file states it where no plugin owns it, and as the plugin's model reads it otherwise - and
    the refusal of one can name the file to blame. Any other part too deep to answer, an init
    nested deeper than its shape among them, is refused by the net every answer is written through
    (:func:`written`)."""
    resolved = revision.resolved
    if resolved is None:
        return None
    dictionary = resolved.dictionary
    for plugin, settings in dictionary.extensions.items():
        if nesting(settings) > PROJECT_BLOCK_DEPTH:
            stating = _stating(revision, plugin)
            if stating is None:
                return (
                    f"the settings of plugin '{plugin}', which no project file states any more, "
                    f"are nested more than {PROJECT_BLOCK_DEPTH} levels deep, {TOO_DEEP}"
                )
            return (
                f"{stating.name} holds an extension block nested more than "
                f"{PROJECT_BLOCK_DEPTH} levels deep, {TOO_DEEP}"
            )
    entries: list[ResolvedObject | ResolvedInstance] = [*dictionary.objects, *dictionary.instances]
    for entry in entries:
        if any(nesting(block) > OBJECT_BLOCK_DEPTH for block in entry.extensions.values()):
            located = resolved.locate(entry.name)
            # Every object and structured object of a dictionary is a name a component of it
            # declares, which `locate` answers with the declaration a block may be stated on.
            assert located is not None
            return (
                f"{located.path.name} holds an extension block nested more than "
                f"{OBJECT_BLOCK_DEPTH} levels deep, {TOO_DEEP}"
            )
    return None


def within_depth(changes: Sequence[contract.Change]) -> None:
    """Refuse an edit writing a value nested more than :data:`MAX_DEPTH` deep, the deepest json a
    query carries, in the words the engine refuses a value it cannot lay out with, the file first.

    So every value the page writes stays within what a query carries. It bounds a value, not a
    file: values written one inside another can still nest a file deeper than its answer carries,
    which ``GET /api/file`` then refuses when it is read (:data:`FILE_DEPTH`). The engine's own
    bound, python's stack, lies hundreds of levels deeper, and stays for its other callers."""
    for change in changes:
        for operation in change.operations:
            if operation.raw is not None and text_depth(operation.raw) > MAX_DEPTH:
                refused = not_one_value(operation.raw, NESTED_TOO_DEEPLY)
                raise EditError(INVALID, f"{Path(change.file)}: {refused}")


def _stating(revision: Revision, plugin: str) -> Path | None:
    """The project file of ``revision`` stating the settings of ``plugin``, as the files read now:
    one file of the tree states them, a second being refused, and the dictionary keeps the
    settings but not where they were written. ``None`` where none states them any more, the file
    having changed since the analysis read it."""
    for file in revision.files:
        if file.kind == "project" and _states(file.path, plugin):
            return file.path
    return None


def _states(path: Path, plugin: str) -> bool:
    """Whether the project file at ``path`` states the settings of ``plugin``, as it reads now."""
    document = read_json_document(path)
    if document is None:
        return False
    described = document.get("project")
    if not isinstance(described, dict):
        return False
    settings = described.get("extensions")
    return isinstance(settings, dict) and plugin in settings


def _fields_of(model: BaseModel, level: int) -> list[tuple[object, object, int]]:
    """Each field of ``model`` the serializer could count anything of, with its annotation."""
    return [(getattr(model, name), annotation, level) for name, annotation in _deep(type(model))]


@cache
def _deep(model: type[BaseModel]) -> tuple[tuple[str, object], ...]:
    """The fields of ``model`` that can hold anything the serializer counts: every one but a
    number, a string, a truth value, a literal or an enumeration, alone or beside ``None``."""
    return tuple(
        (name, field.annotation)
        for name, field in model.model_fields.items()
        if not _flat(field.annotation)
    )


def _flat(annotation: object) -> bool:
    kind = _kind(annotation)
    if kind is _UNTYPED:
        return False
    if kind in (str, int, float, bool, type(None)):
        return True
    if isinstance(kind, type) and issubclass(kind, Enum):
        return True
    return typing.get_origin(kind) is typing.Literal


def _kind(annotation: object) -> object:
    """``annotation`` as the walk reads it: an alias or an ``Annotated`` taken off, ``X | None``
    read as ``X``, and :data:`_UNTYPED` for ``Any``, ``object`` or a union of several kinds."""
    while True:
        if isinstance(annotation, typing.TypeAliasType):
            annotation = annotation.__value__
        elif typing.get_origin(annotation) is typing.Annotated:
            annotation = typing.get_args(annotation)[0]
        else:
            break
    if annotation is Any or annotation is object or annotation is _UNTYPED:
        return _UNTYPED
    if typing.get_origin(annotation) in (typing.Union, types.UnionType):
        members = [m for m in typing.get_args(annotation) if m is not type(None)]
        if len(members) == 1:
            return _kind(members[0])
        if all(_flat(member) for member in members):
            return members[0]
        return _UNTYPED
    return annotation


def _typed(
    children: Iterable[object], annotations: tuple[object, ...], level: int
) -> list[tuple[object, object, int]]:
    """The children of a typed mapping or sequence, each with its annotation - one for them all,
    or one each, in a tuple of fixed length - and none whose annotation is flat, which the
    serializer counts nothing of: a grid's thousands of numbers are not visited one by one."""
    if len(annotations) == 1:
        if _flat(annotations[0]):
            return []
        return [(child, annotations[0], level) for child in children]
    return [
        (child, annotation, level)
        for child, annotation in zip(children, annotations, strict=False)
        if not _flat(annotation)
    ]


def _argument(kind: object, position: int) -> object:
    """Argument ``position`` of a generic annotation, or :data:`_UNTYPED` where it has none."""
    arguments = typing.get_args(kind)
    return arguments[position] if len(arguments) > position else _UNTYPED


def _items(kind: object) -> tuple[object, ...]:
    """What the items of a typed tuple, list or set are annotated as: one annotation for every item,
    or one each, in a tuple of fixed length."""
    arguments = typing.get_args(kind)
    if typing.get_origin(kind) is tuple and len(arguments) > 1 and arguments[-1] is not Ellipsis:
        return arguments
    return (_argument(kind, 0),)
