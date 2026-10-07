"""What every route of the ddd gui api takes in its query, and the types its values are read as.

A query arrives as text, one value a key (:func:`ddd.gui.routes.one_value_each`). Each route's
model says which keys it takes, and reads each value as the type it is: the model answers for
form - a number's digits, a path's shape, json's depth - and the route's handler for meaning, as
before. Every refusal a model makes is one sentence: the route's own, word for word, where it
already said one about that key (Appendix A of ``docs/superpowers/plans/2026-10-05-gui-
security.md``).

A plan route that takes one of several actions reads its query as one model per action, the
``action`` given choosing which (:class:`_Actions`): each action's model says what that action
takes, and a key another action takes is one it does not.

A path is read against the directories ``ddd gui`` serves (:class:`Serving`), which each
request hands its models: a network path is a path like any other under one of them, and refused
anywhere else before anything resolves it.

A compared baseline is the one path read as the reader typed it, relative to the directory
``ddd gui`` was started in or absolute: its model refuses only what must not reach
:mod:`ddd.gui.compare`, and compare.py refuses the rest in its own words, as it always has - a
NUL in it, a path outside that directory, a file it cannot read.
"""

from __future__ import annotations

import json
import math
import re
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Annotated, ClassVar, Final, Literal, get_args

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    RootModel,
    ValidationInfo,
    model_validator,
)
from pydantic.json_schema import SkipJsonSchema
from pydantic_core import PydanticCustomError

from ddd.diagnostics import Severity
from ddd.editing import EditError, device_named, not_one_value, parse_raw
from ddd.gui.depth import MAX_DEPTH, text_depth
from ddd.loading import NESTED_TOO_DEEPLY
from ddd.lsp.edits import PROPAGATED_KEYS

MAX_DIGITS: Final = 9
"""The most digits a whole number of a query has: a page offset, a version, a cell's index -
every one far below a billion, and ``int()`` of more than 4,300 digits raises."""

MAX_PATH: Final = 4096
"""The longest path a query names; ``PATH_MAX`` on Linux, beyond any project's."""

MAX_NAME: Final = 1024
"""The longest name a query gives: a variable, a unit, a type."""

LISTED: Final = (Severity.ERROR, Severity.WARNING, Severity.INFO)
"""The severities a finding is reported at, and so the ones ``GET /api/findings`` filters by:
``ignore`` means a finding is not reported at all."""

_DRIVE: Final = re.compile(r"[A-Za-z]:[\\/]")
"""A Windows path's drive and root: ``C:/`` or ``C:\\``."""

_NETWORK: Final = re.compile(r"[\\/]{2}")
"""Two separators first, either way round: ``\\\\server\\share``, ``//server/share``, and the
device forms ``\\\\?\\`` and ``\\\\.\\`` - each opened over the network, or as a device, on
Windows, which treats ``/`` as a separator as well."""

_CASELESS: Final = sys.platform == "win32"
"""Whether a path is compared with another without its case: on Windows, which finds a file's
name so."""

_OPENS_DEVICES: Final = sys.platform == "win32"
"""Whether the system opens a device for a name it keeps for one (:func:`ddd.editing.device_named`)
in whatever directory the name is written: Windows does, and resolving a path asks it about every
directory along the way - so a path holding such a name, in any of its names, is no path to read
there. Linux keeps a file or a directory of such a name like any other."""

_SEPARATORS: Final = re.compile(r"[\\/]")
"""Either separator, as Windows reads both: what splits a path into its names."""

_REFUSED: Final = object()
"""What a blank value of a type is read as where the route lets none through: refused, with the
type's sentence, as anything else it cannot read is."""


@dataclass(frozen=True, slots=True)
class Serving:
    """What a request's paths are read against: the directory ``ddd gui`` was started in, and
    every directory it serves - that one, and the open project's own where it lies outside it
    (:attr:`ddd.gui.session.Revision.served`) - each posix-separated, as the server names a
    path. Handed to a request's models as pydantic's validation context by
    :meth:`ddd.gui.api.Api.handle`; a model read without one serves no directory."""

    root: str
    served: tuple[str, ...]


_NOTHING_SERVED: Final = Serving("", ())


def refusal(sentence: str) -> PydanticCustomError:
    """A refusal whose message is ``sentence`` exactly: braces in it are not a template. A lone
    surrogate in it, echoed from what was typed, is said as its escape, ``\\ud800``: pydantic
    cannot carry the character itself in a message, and every other one stays as it is."""
    said = sentence.encode("utf-8", "backslashreplace").decode("utf-8")
    return PydanticCustomError("query", "{sentence}", {"sentence": said})


type _Reader = Callable[[object, ValidationInfo], object]


def _validator(read: _Reader, blank: object) -> BeforeValidator:
    """``read`` as a field's validator, a blank value read as ``blank`` without asking it - unless
    ``blank`` is :data:`_REFUSED`, which leaves the blank to ``read`` like any other value."""
    if blank is _REFUSED:
        return BeforeValidator(read)

    def letting(value: object, info: ValidationInfo) -> object:
        if value == "":
            return blank
        return read(value, info)

    return BeforeValidator(letting)


def _serving(info: ValidationInfo) -> Serving:
    """What the request being read is served: its context, or nothing for a model read without
    one."""
    context = info.context
    if isinstance(context, Serving):
        return context
    return _NOTHING_SERVED


def _folded(text: str) -> str:
    """``text`` as a path is compared with another as text: every separator a ``/``, and on
    Windows (:data:`_CASELESS`) every letter in one case - ``lower()``'s, the case pathlib's own
    Windows comparison folds to (``ntpath.normcase``), and so :func:`ddd.gui.session._served` and
    :mod:`ddd.gui.compare`. ``casefold()`` would match spellings Windows tells apart: a sharp s
    with ``ss``, a long s with ``s``."""
    folded = text.replace("\\", "/")
    if _CASELESS:
        return folded.lower()
    return folded


def _under(text: str, directories: Iterable[str]) -> bool:
    """Whether ``text`` names one of ``directories``, or a path under one: compared as text, so
    that nothing is resolved - and no network asked - to tell. A path holding a ``.`` or ``..``
    segment names none of them, wherever it would lead: only resolving it would say where, and
    the server never answers with such a path."""
    given = _folded(text)
    if any(segment in (".", "..") for segment in given.split("/")):
        return False
    for directory in directories:
        served = _folded(directory).rstrip("/")
        if given == served or given.startswith(f"{served}/"):
            return True
    return False


def _encodable(text: str) -> bool:
    """Whether ``text`` holds no lone surrogate: a query arrives over HTTP decoded with
    replacement, so only a caller in the process can hand one over."""
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _digits(value: object) -> int | None:
    """``value`` read as a whole number of at most :data:`MAX_DIGITS` ascii digits, or ``None``
    for anything else: a sign, a point, an underscore, a space, a digit of another script."""
    if (
        isinstance(value, str)
        and value.isascii()
        and value.isdecimal()
        and len(value) <= MAX_DIGITS
    ):
        return int(value)
    return None


def whole(sentence: str, *, least: int = 0) -> BeforeValidator:
    """A whole number written in ASCII digits, at most :data:`MAX_DIGITS` of them, from
    ``least``; anything else is refused with ``sentence``."""

    def read(value: object) -> int:
        number = _digits(value)
        if number is None or number < least:
            raise refusal(sentence)
        return number

    return BeforeValidator(read)


def file_path(sentence: str, *, blank: object = _REFUSED) -> BeforeValidator:
    """A file's absolute path, as the page names every file it asks about; anything else is
    refused with ``sentence``.

    Absolute on every platform alike: from ``/``, or from a drive and its root, ``C:/`` or
    ``C:\\``, which is what the server answers a file's path as on Windows. Refused, whatever the
    platform: an empty path; one of more than :data:`MAX_PATH` characters; one holding a NUL,
    which ``Path.resolve`` raises on, or a lone surrogate, which no path the page sends holds;
    and a network or device form naming no path under a directory served (:class:`Serving`),
    which Windows would open for the asking - a ``.`` or ``..`` segment in one included. One
    under such a directory is the network path a mapped drive resolves to there, and is read
    like any other. Refused on Windows alone (:data:`_OPENS_DEVICES`): a path holding a name it
    keeps for a device, in any of its names. Whether the path is a file of the project is the
    handler's question, as before.
    """

    def read(value: object, info: ValidationInfo) -> str:
        if isinstance(value, str) and _absolute(value, _serving(info).served):
            return value
        raise refusal(sentence)

    return _validator(read, blank)


def _readable(text: str) -> bool:
    """Whether ``text`` can be a path at all: not empty, at most :data:`MAX_PATH` characters,
    holding no NUL and no lone surrogate - and where the system opens a device for its name
    (:data:`_OPENS_DEVICES`), no such name. A statement a rule, rather than one condition, so that
    the coverage gate sees each rule decide."""
    if not text:
        return False
    if len(text) > MAX_PATH:
        return False
    if "\x00" in text:
        return False
    if _names_a_device(text):
        return False
    return _encodable(text)


def _names_a_device(text: str) -> bool:
    """Whether a name of ``text``, at either separator, is one the system opens a device for
    (:data:`_OPENS_DEVICES`): never where it opens none. Judged as text, before anything looks the
    path up - looking it up is what opens the device."""
    if not _OPENS_DEVICES:
        return False
    return any(device_named(name) is not None for name in _SEPARATORS.split(text))


def _absolute(text: str, served: Iterable[str]) -> bool:
    """Whether ``text`` is a path :func:`file_path` takes, ``served`` the directories a network
    path may name one under."""
    if not _readable(text):
        return False
    if _NETWORK.match(text):
        return _under(text, served)
    return text.startswith("/") or _DRIVE.match(text) is not None


def named(sentence: str, *, blank: object = _REFUSED) -> BeforeValidator:
    """A name: not empty, at most :data:`MAX_NAME` characters, no NUL. Whether anything goes by
    it is the handler's question; anything else is refused with ``sentence``."""

    def read(value: object, info: ValidationInfo) -> str:
        if isinstance(value, str) and value and len(value) <= MAX_NAME and "\x00" not in value:
            return value
        raise refusal(sentence)

    return _validator(read, blank)


def any_text(sentence: str) -> BeforeValidator:
    """Text of any kind but the empty one, left for the route's handler to read, which refuses
    in words of its own whatever it cannot: the empty text, and anything that is not text, are
    refused with ``sentence``. No length is bounded and no character refused: the handler's
    reading answers for those."""

    def read(value: object) -> str:
        if isinstance(value, str) and value:
            return value
        raise refusal(sentence)

    return BeforeValidator(read)


def json_text(sentence: str | None = None, *, blank: object = _REFUSED) -> BeforeValidator:
    """Json text: one value, read by the loader's rule (:func:`ddd.editing.parse_raw`), nested at
    most :data:`MAX_DEPTH` deep and holding no number too large to be finite.

    Answered as the text itself, never as the value it stands for: an edit writes a value into a
    file as the reader typed it, ``1.0`` as those three characters. The depth is counted over the
    text before anything parses it, so that no parser - ``json``'s, or the edit engine's own -
    recurses into a value deeper than that.

    Refused with ``sentence``; or, where none is given, in the words :func:`~ddd.editing.parse_raw`
    refuses a value with, which is how settle and the shared plans have always answered one.
    """

    def read(value: object, info: ValidationInfo) -> str:
        try:
            return _json(value)
        except EditError as refused:
            if sentence is None:
                raise refusal(str(refused)) from None
            raise refusal(sentence) from None

    return _validator(read, blank)


def json_value(text: str) -> object:
    """The value ``text`` stands for, where it is json text :func:`json_text` takes - its depth
    counted before anything parses it, read by the loader's rule, its numbers finite - or the
    :class:`~ddd.editing.EditError` refusing it in :func:`~ddd.editing.parse_raw`'s words.

    What ``GET /api/declaration-plan`` reads a definition with, in its handler rather than its
    query: it refuses one in a sentence of its own, ``409``, which the declare panel shows as an
    offer's refusal (ruling 5 of the security review's plan)."""
    return parse_raw(_json(text))


def _json(value: object) -> str:
    """``value``, where it is json text :func:`json_text` takes, or the refusal of it in
    :func:`~ddd.editing.parse_raw`'s words."""
    if isinstance(value, str) and text_depth(value) > MAX_DEPTH:
        raise not_one_value(value, NESTED_TOO_DEEPLY)
    parse_raw(value)
    assert isinstance(value, str)  # parse_raw refuses anything that is not text
    try:
        json.loads(value, parse_float=_finite)
    except ValueError as error:
        raise not_one_value(value, error) from None
    return value


def _finite(number: str) -> float:
    """A json number with a fraction or an exponent, read as python reads it, and refused where
    that is not finite: ``1e999`` reads as infinity, which DDD can no more carry through to its
    outputs than ``Infinity`` itself, which the loader refuses."""
    read = float(number)
    if not math.isfinite(read):
        raise ValueError(f"'{number}' is not a finite number; DDD has no representation for it")
    return read


def actions_of(model: type[BaseModel]) -> dict[str, type[_Query]]:
    """The model of each action a query of one model per action takes, by its action: the
    members of a ``RootModel`` over a union discriminated by ``action``. None for the query of a
    route that has one model."""
    if not issubclass(model, RootModel):
        return {}
    members = get_args(model.model_fields["root"].annotation)
    return {get_args(member.model_fields["action"].annotation)[0]: member for member in members}


class _Query(BaseModel):
    """A route's query: the keys it takes, each read as its type; closed, frozen and strict, as
    a request's body is. Every value arrives as text, and its type's validator reads it into
    what it is: strict, a value no validator read is never coerced, ``1.0`` into a number or
    ``on`` into ``true``."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", strict=True, use_attribute_docstrings=True
    )

    missing: ClassVar[str] = ""
    """What the route answers when a key it requires is left out or blank."""


class NoQuery(_Query):
    """The query of a route that takes none."""


class _Actions[T](RootModel[T]):
    """The query of a route that takes one of several actions, each with parts of its own: a
    ``RootModel`` over a union of one model per action, discriminated by ``action``.

    The action is read first, before the union: one the route does not take - or none - is
    refused in the route's own words, naming every action it does take, in the order of its
    union. The model of the action given then reads the rest, so that a part that action
    requires, left out, answers its ``missing``, and a key it does not take - another action's
    included - answers that it takes no such key (:func:`ddd.gui.api._query_message`)."""

    model_config = ConfigDict(frozen=True)

    route: ClassVar[str] = ""
    """The route's name, as its refusals say it: ``unit-plan``."""

    @model_validator(mode="before")
    @classmethod
    def _taken(cls, value: object) -> object:
        """``value``, where its ``action`` is one the route takes; else the route's refusal."""
        taken = actions_of(cls)
        action = None
        if isinstance(value, dict):
            action = value.get("action")
        if isinstance(action, str) and action in taken:
            return value
        raise refusal(f"{cls.route} takes ?action= one of {', '.join(taken)}")


class StateQuery(_Query):
    """What ``GET /api/state`` takes."""

    after: Annotated[int | SkipJsonSchema[None], BeforeValidator(_digits)] = None
    """Answer once the version is past this one, or the wait runs out. At once without it, and
    for anything but a whole number of at most nine digits, as for anything that was not a
    number before: never refused."""


def _severity(value: object) -> str:
    if value in LISTED:
        return str(value)
    raise refusal("findings takes ?severity= as error, warning or info")


class FindingsQuery(_Query):
    """What ``GET /api/findings`` takes: which of the newest revision's findings to answer."""

    offset: Annotated[int, whole("findings takes ?offset= as a whole number from 0")] = 0
    """The first finding to answer, counted from ``0`` in the Findings tab's order."""

    limit: Annotated[
        int | SkipJsonSchema[None],
        whole("findings takes ?limit= as a whole number from 1", least=1),
    ] = None
    """How many findings to answer at most; every one from ``offset`` on without it."""

    severity: Annotated[str | SkipJsonSchema[None], BeforeValidator(_severity)] = None
    """Only the findings of this severity: ``error``, ``warning`` or ``info``."""

    file: Annotated[
        str | SkipJsonSchema[None], file_path("findings takes ?file= as a file's path", blank="")
    ] = None
    """Only the findings filed on this file, however its path is spelled; blank, none."""

    check: Annotated[
        str | SkipJsonSchema[None], named("findings takes ?check= as a check's name", blank="")
    ] = None
    """Only the findings this check reported; blank, none."""


class FileQuery(_Query):
    """What ``GET /api/file`` takes."""

    missing: ClassVar[str] = "file takes ?path="

    path: Annotated[str, file_path("file takes ?path= as a file's path")]
    """The description file to read, a file of the open project."""


class VariableQuery(_Query):
    """What ``GET /api/variable`` takes."""

    missing: ClassVar[str] = "variable takes ?name="

    name: Annotated[str, named("variable takes ?name= as a variable's name")]
    """The variable whose declarations to answer."""


class UnitQuery(_Query):
    """What ``GET /api/unit`` takes."""

    missing: ClassVar[str] = "unit takes ?name="

    name: Annotated[str, named("unit takes ?name= as a unit's name")]
    """The unit to answer, stated or listed."""


class TypeQuery(_Query):
    """What ``GET /api/type`` takes."""

    missing: ClassVar[str] = "type takes ?name="

    name: Annotated[str, named("type takes ?name= as a type's name")]
    """The type to answer."""


class ConstantQuery(_Query):
    """What ``GET /api/constant`` takes."""

    missing: ClassVar[str] = "constant takes ?name="

    name: Annotated[str, named("constant takes ?name= as a constant's name")]
    """The constant to answer."""


class SectionQuery(_Query):
    """What ``GET /api/section`` takes."""

    missing: ClassVar[str] = "section takes ?name="

    name: Annotated[str, named("section takes ?name= as a section's name")]
    """The section to answer."""


class RasterQuery(_Query):
    """What ``GET /api/raster`` takes."""

    missing: ClassVar[str] = "raster takes ?name="

    name: Annotated[str, named("raster takes ?name= as a raster's name")]
    """The raster to answer."""


class ValuesQuery(_Query):
    """What ``GET /api/values`` takes."""

    missing: ClassVar[str] = "values takes ?name="

    name: Annotated[str, named("values takes ?name= as an object's name")]
    """The object whose grid of values to answer."""


def _shared_key(value: object) -> str:
    if isinstance(value, str) and value in PROPAGATED_KEYS:
        return value
    raise refusal(f"'{value}' is not a key the declarations of a variable share")


class SettleQuery(_Query):
    """What ``GET /api/settle`` takes: one key every declaration of a variable is to state."""

    missing: ClassVar[str] = "settle takes ?name= and ?key=, and ?raw= unless the key goes"

    name: Annotated[str, named("settle takes ?name= as a variable's name")]
    """The variable whose declarations to settle."""

    key: Annotated[str, BeforeValidator(_shared_key)]
    """The key to settle, one the declarations of a variable share."""

    raw: Annotated[str | SkipJsonSchema[None], json_text(blank=None)] = None
    """The value each declaration is to state, as json text; left out or blank, the key goes
    from every declaration."""


class FixQuery(_Query):
    """What ``GET /api/fix`` takes: the finding whose fixes to answer."""

    missing: ClassVar[str] = "fix takes ?file=, ?pointer= and ?check="

    file: Annotated[str, file_path("fix takes ?file= as a file's path")]
    """The file the finding is filed on."""

    pointer: Annotated[str, named("fix takes ?pointer= as a place in the file", blank="")]
    """Where in the file the finding is; blank, the whole file."""

    check: Annotated[str, named("fix takes ?check= as a check's name")]
    """The check that reported the finding."""


class DeclarableQuery(_Query):
    """What ``GET /api/declarable`` takes."""

    missing: ClassVar[str] = "declarable takes ?file="

    file: Annotated[str, file_path("declarable takes ?file= as a file's path")]
    """The component whose declarable names to answer."""


_BASELINE: Final = "compare takes ?baseline= as a file's path"


def _baseline(value: object, info: ValidationInfo) -> str:
    """A baseline as the reader typed it, for :mod:`ddd.gui.compare` to read, refused here only
    where it must not reach compare.py: nothing at all; a lone surrogate; where the system opens
    a device for its name (:data:`_OPENS_DEVICES`), a path holding such a name, which resolving
    would open; and a network or device form naming no path under a directory served, which
    resolving would open on Windows. That one lies outside the root as written, and is refused
    in the words compare.py refuses a path outside it with, before anything resolves it."""
    if not isinstance(value, str) or not value or not _encodable(value):
        raise refusal(_BASELINE)
    if _names_a_device(value):
        raise refusal(_BASELINE)
    serving = _serving(info)
    if _NETWORK.match(value) and not _under(value, serving.served):
        raise refusal(f"the baseline '{value}' is outside the session root '{serving.root}'")
    return value


class CompareQuery(_Query):
    """What ``GET /api/compare`` takes."""

    missing: ClassVar[str] = "compare takes ?baseline="

    baseline: Annotated[str, BeforeValidator(_baseline)]
    """The delivery to compare the open project against: a dumped dictionary, or a project or
    component description, at a path under the directory ``ddd gui`` serves - relative to it, or
    absolute."""


class RenameUnit(_Query):
    """A unit spelled anew wherever it is stated or listed: ``GET /api/unit-plan``'s
    ``rename``."""

    missing: ClassVar[str] = "rename takes ?unit= and ?to="

    action: Literal["rename"]

    unit: Annotated[str, named("rename takes ?unit= as a unit's name")]
    """The unit, as it is spelled now."""

    to: Annotated[str, named("rename takes ?to= as a unit's name", blank="")]
    """Its new spelling; blank, the empty unit, which the plan refuses as no unit."""


class AddUnit(_Query):
    """A unit added to the vocabulary: ``GET /api/unit-plan``'s ``add``."""

    missing: ClassVar[str] = "add takes ?unit="

    action: Literal["add"]

    unit: Annotated[str, named("add takes ?unit= as a unit's name")]
    """The unit, as it is to be spelled."""


class DescribeUnit(_Query):
    """The vocabulary's description of a unit set: ``GET /api/unit-plan``'s ``describe``."""

    missing: ClassVar[str] = "describe takes ?unit= and ?description="

    action: Literal["describe"]

    unit: Annotated[str, named("describe takes ?unit= as a unit's name")]
    """The unit to describe."""

    description: str
    """Its description; blank, the empty text, which is how one is cleared."""


class RemoveUnit(_Query):
    """A unit nothing states taken out of the vocabulary: ``GET /api/unit-plan``'s
    ``remove``."""

    missing: ClassVar[str] = "remove takes ?unit="

    action: Literal["remove"]

    unit: Annotated[str, named("remove takes ?unit= as a unit's name")]
    """The unit to take out."""


class AdoptUnits(_Query):
    """A vocabulary for a project whose units files list no unit, of every unit it states:
    ``GET /api/unit-plan``'s ``adopt``."""

    action: Literal["adopt"]


class UnitPlanQuery(
    _Actions[
        Annotated[
            RenameUnit | AddUnit | DescribeUnit | RemoveUnit | AdoptUnits,
            Field(discriminator="action"),
        ]
    ]
):
    """What ``GET /api/unit-plan`` takes: one change of the project's units, by its action."""

    route: ClassVar[str] = "unit-plan"


class SetTypeKey(_Query):
    """One key of a type set, or taken away: ``GET /api/type-plan``'s ``set``."""

    missing: ClassVar[str] = "set takes ?name= and ?key="

    action: Literal["set"]

    name: Annotated[str, named("set takes ?name= as a type's name")]
    """The type."""

    key: Annotated[str, named("set takes ?key= as a key's name", blank="")]
    """The key to set; whether the type's kind has one of that name is the plan's question."""

    raw: Annotated[str | SkipJsonSchema[None], json_text(blank=None)] = None
    """The value to set it to, as json text; left out or blank, the key is taken away."""


class RenameType(_Query):
    """A type renamed, and every ``typename`` reaching it: ``GET /api/type-plan``'s
    ``rename``."""

    missing: ClassVar[str] = "rename takes ?name= and ?to="

    action: Literal["rename"]

    name: Annotated[str, named("rename takes ?name= as a type's name")]
    """The type."""

    to: Annotated[str, named("rename takes ?to= as a type's name", blank="")]
    """Its new name; whether it may be used is the plan's question, a blank one included."""


class TypePlanQuery(_Actions[Annotated[SetTypeKey | RenameType, Field(discriminator="action")]]):
    """What ``GET /api/type-plan`` takes: one change of a type, by its action."""

    route: ClassVar[str] = "type-plan"


class SetConstantKey(_Query):
    """One key of a constant set, or taken away: ``GET /api/constant-plan``'s ``set``."""

    missing: ClassVar[str] = "set takes ?name= and ?key="

    action: Literal["set"]

    name: Annotated[str, named("set takes ?name= as a constant's name")]
    """The constant."""

    key: Annotated[str, named("set takes ?key= as a key's name", blank="")]
    """The key to set; whether a constant has one of that name is the plan's question."""

    raw: Annotated[str | SkipJsonSchema[None], json_text(blank=None)] = None
    """The value to set it to, as json text; left out or blank, the key is taken away."""


class RenameConstant(_Query):
    """A constant renamed, and every shape spelling it: ``GET /api/constant-plan``'s
    ``rename``."""

    missing: ClassVar[str] = "rename takes ?name= and ?to="

    action: Literal["rename"]

    name: Annotated[str, named("rename takes ?name= as a constant's name")]
    """The constant."""

    to: Annotated[str, named("rename takes ?to= as a constant's name", blank="")]
    """Its new name; whether it may be used is the plan's question, a blank one included."""


class AddConstant(_Query):
    """A constant declared: ``GET /api/constant-plan``'s ``add``."""

    missing: ClassVar[str] = "add takes ?name= and ?raw="

    action: Literal["add"]

    name: Annotated[str, named("add takes ?name= as a constant's name")]
    """The new constant's name."""

    raw: Annotated[str, json_text()]
    """Its value, as json text: required, where ``set``'s may be left out - a constant declared
    with no value is not what ``add`` means."""


class RemoveConstant(_Query):
    """A constant nothing names taken out: ``GET /api/constant-plan``'s ``remove``."""

    missing: ClassVar[str] = "remove takes ?name="

    action: Literal["remove"]

    name: Annotated[str, named("remove takes ?name= as a constant's name")]
    """The constant."""


class ConstantPlanQuery(
    _Actions[
        Annotated[
            SetConstantKey | RenameConstant | AddConstant | RemoveConstant,
            Field(discriminator="action"),
        ]
    ]
):
    """What ``GET /api/constant-plan`` takes: one change of a constant, by its action."""

    route: ClassVar[str] = "constant-plan"


class SetSectionKey(_Query):
    """One key of a section set, or taken away: ``GET /api/section-plan``'s ``set``."""

    missing: ClassVar[str] = "set takes ?name= and ?key="

    action: Literal["set"]

    name: Annotated[str, named("set takes ?name= as a section's name")]
    """The section."""

    key: Annotated[str, named("set takes ?key= as a key's name", blank="")]
    """The key to set; whether a section has one of that name is the plan's question."""

    raw: Annotated[str | SkipJsonSchema[None], json_text(blank=None)] = None
    """The value to set it to, as json text; left out or blank, the key is taken away."""


class RenameSection(_Query):
    """A section renamed, and every shape spelling it: ``GET /api/section-plan``'s
    ``rename``."""

    missing: ClassVar[str] = "rename takes ?name= and ?to="

    action: Literal["rename"]

    name: Annotated[str, named("rename takes ?name= as a section's name")]
    """The section."""

    to: Annotated[str, named("rename takes ?to= as a section's name", blank="")]
    """Its new name; whether it may be used is the plan's question, a blank one included."""


class AddSection(_Query):
    """A section declared: ``GET /api/section-plan``'s ``add``.

    One part per key of :attr:`ddd.project_shared.SECTIONS.required`, in the order the panel
    draws them, which is the order a refusal of two names the first in: a section the model gives
    no default for ``access`` or ``alignment`` is one whose file would not load the moment it was
    written. Each is json text, as ``set``'s ``raw`` is: ``?access="read-only"&alignment=4``.
    ``description`` is not among them, having a default, and is set from the panel afterwards."""

    missing: ClassVar[str] = "add takes ?name= and ?access= and ?alignment="

    action: Literal["add"]

    name: Annotated[str, named("add takes ?name= as a section's name")]
    """The new section's name."""

    access: Annotated[str, json_text()]
    """Its access, as json text: ``"read-only"`` or ``"read-write"``, in their quotes."""

    alignment: Annotated[str, json_text()]
    """Its alignment, as json text."""


class RemoveSection(_Query):
    """A section nothing names taken out: ``GET /api/section-plan``'s ``remove``."""

    missing: ClassVar[str] = "remove takes ?name="

    action: Literal["remove"]

    name: Annotated[str, named("remove takes ?name= as a section's name")]
    """The section."""


class SectionPlanQuery(
    _Actions[
        Annotated[
            SetSectionKey | RenameSection | AddSection | RemoveSection,
            Field(discriminator="action"),
        ]
    ]
):
    """What ``GET /api/section-plan`` takes: one change of a section, by its action."""

    route: ClassVar[str] = "section-plan"


class SetRasterKey(_Query):
    """One key of a raster set, or taken away: ``GET /api/raster-plan``'s ``set``."""

    missing: ClassVar[str] = "set takes ?name= and ?key="

    action: Literal["set"]

    name: Annotated[str, named("set takes ?name= as a raster's name")]
    """The raster."""

    key: Annotated[str, named("set takes ?key= as a key's name", blank="")]
    """The key to set; whether a raster has one of that name is the plan's question."""

    raw: Annotated[str | SkipJsonSchema[None], json_text(blank=None)] = None
    """The value to set it to, as json text; left out or blank, the key is taken away."""


class RenameRaster(_Query):
    """A raster renamed, and every shape spelling it: ``GET /api/raster-plan``'s
    ``rename``."""

    missing: ClassVar[str] = "rename takes ?name= and ?to="

    action: Literal["rename"]

    name: Annotated[str, named("rename takes ?name= as a raster's name")]
    """The raster."""

    to: Annotated[str, named("rename takes ?to= as a raster's name", blank="")]
    """Its new name; whether it may be used is the plan's question, a blank one included."""


class AddRaster(_Query):
    """A raster declared: ``GET /api/raster-plan``'s ``add``.

    One part per key of :attr:`ddd.project_shared.RASTERS.required`, which is ``event`` alone:
    a raster's ``cycle`` may be left out and its ``description`` has a default, so both are set
    from the panel afterwards. Named for the key rather than carried as ``?raw=``, as a section's
    are, so that :func:`ddd.gui.api._declared` builds the entry off the vocabulary's descriptor."""

    missing: ClassVar[str] = "add takes ?name= and ?event="

    action: Literal["add"]

    name: Annotated[str, named("add takes ?name= as a raster's name")]
    """The new raster's name."""

    event: Annotated[str, json_text()]
    """Its event, as json text: a whole number."""


class RemoveRaster(_Query):
    """A raster nothing names taken out: ``GET /api/raster-plan``'s ``remove``."""

    missing: ClassVar[str] = "remove takes ?name="

    action: Literal["remove"]

    name: Annotated[str, named("remove takes ?name= as a raster's name")]
    """The raster."""


class RasterPlanQuery(
    _Actions[
        Annotated[
            SetRasterKey | RenameRaster | AddRaster | RemoveRaster,
            Field(discriminator="action"),
        ]
    ]
):
    """What ``GET /api/raster-plan`` takes: one change of a raster, by its action."""

    route: ClassVar[str] = "raster-plan"


def outside_served(entry: str, served: Iterable[str]) -> str:
    """Why ``entry``, a file outside every directory ``ddd gui`` serves, cannot be added to the
    includes - named as the reader typed it, beside each directory served. Said by the query of
    a network path (:class:`AddFile`), before anything resolves it, and by the plan
    (:func:`ddd.gui.api._addition`) of any other path once resolved."""
    return (
        f"{entry} lies outside what ddd gui serves, {' and '.join(served)}; start it in a "
        "directory holding this file to add it here"
    )


def _included(value: object, info: ValidationInfo) -> str:
    """A file to add to the includes, as the reader typed its entry: relative to the description
    or absolute. Refused where it can be no path at all (:func:`_readable`); and a network or
    device form naming no path under a directory served, before anything resolves it - which on
    Windows would open it - in the words a file outside them is refused with
    (:func:`outside_served`). Whether the file is there, and of a kind a project includes, is the
    plan's question."""
    if not isinstance(value, str) or not _readable(value):
        raise refusal("add takes ?path= as a file's path")
    served = _serving(info).served
    if _NETWORK.match(value) and not _under(value, served):
        raise refusal(outside_served(value, served))
    return value


_ROW_KEY: Final = "remove takes ?path= as a row's key"


def _row_key(value: object, info: ValidationInfo) -> str:
    """A row's key, as ``GET /api/files`` answers one: a path :func:`file_path` takes. One that
    is in every other way a path, but relative, is refused in the words the route always refused
    it with, which echo it: read against the server's own working directory, it named another
    file. Anything else is no row's key at all."""
    if not isinstance(value, str):
        raise refusal(_ROW_KEY)
    if _absolute(value, _serving(info).served):
        return value
    if _readable(value) and _NETWORK.match(value) is None:
        raise refusal(f"{_ROW_KEY}, which is absolute, and '{value}' is not")
    raise refusal(_ROW_KEY)


class CreateFile(_Query):
    """A new description file, and the entry that includes it: ``GET /api/files-plan``'s
    ``create``."""

    missing: ClassVar[str] = "create takes ?kind= and ?name="

    action: Literal["create"]

    kind: Annotated[str, named("create takes ?kind= as a kind of file")]
    """The kind of file: one of ``FilesReply.creatable``, which the plan checks."""

    name: Annotated[str, named("create takes ?name= as a file's name")]
    """The new file's name, without its ``.ddd.json``."""

    component: Annotated[
        str | SkipJsonSchema[None],
        named("create takes ?component= as a component's name", blank=None),
    ] = None
    """A new component's own name: read for a ``kind`` of ``component`` alone, which the plan
    refuses without one, and ignored for every other. Left out or blank, none."""


class AddFile(_Query):
    """A file there already appended to the includes, and the errors it is counted to bring:
    ``GET /api/files-plan``'s ``add``."""

    missing: ClassVar[str] = "add takes ?path="

    action: Literal["add"]

    path: Annotated[str, BeforeValidator(_included)]
    """The file, as the includes' new entry is to name it: relative to the project description,
    or absolute."""


class RemoveFile(_Query):
    """Every entry of the includes reaching a file taken out: ``GET /api/files-plan``'s
    ``remove``."""

    missing: ClassVar[str] = "remove takes ?path="

    action: Literal["remove"]

    path: Annotated[str, BeforeValidator(_row_key)]
    """A row's key - ``IncludedEntryReply.key``, or one of a pattern's own ``files`` - which is
    absolute."""


class FilesPlanQuery(
    _Actions[Annotated[CreateFile | AddFile | RemoveFile, Field(discriminator="action")]]
):
    """What ``GET /api/files-plan`` takes: one change of the project's own files, by its
    action."""

    route: ClassVar[str] = "files-plan"


class ReadDeclaration(_Query):
    """An object the project has declared in one more component, its definition the producer's:
    ``GET /api/declaration-plan``'s ``read``. Every part is read by its handler, a blank one
    included, as it always was."""

    missing: ClassVar[str] = "read takes ?file= and ?name= and ?scope="

    action: Literal["read"]

    file: Annotated[str, file_path("read takes ?file= as a file's path", blank="")]
    """The component to declare it in."""

    name: Annotated[str, named("read takes ?name= as an object's name", blank="")]
    """The object."""

    scope: Annotated[str, named("read takes ?scope= as a declaration's scope", blank="")]
    """The scope to declare it with: ``output``, ``input`` or ``local``."""


class DeclareObject(_Query):
    """A new object declared in a component: ``GET /api/declaration-plan``'s ``declare``.
    Every part is read by its handler, a blank one included, as it always was."""

    missing: ClassVar[str] = "declare takes ?file= and ?scope= and ?definition="

    action: Literal["declare"]

    file: Annotated[str, file_path("declare takes ?file= as a file's path", blank="")]
    """The component to declare it in."""

    scope: Annotated[str, named("declare takes ?scope= as a declaration's scope", blank="")]
    """The scope to declare it with: ``output``, ``input`` or ``local``."""

    definition: str
    """Its definition, as json text: refused by the handler, as an offer's refusal, where it is
    not one json object read by :func:`json_value`."""


class RemoveDeclaration(_Query):
    """A declaration taken out of a component: ``GET /api/declaration-plan``'s ``remove``.
    Every part is read by its handler, a blank one included, as it always was."""

    missing: ClassVar[str] = "remove takes ?file= and ?name="

    action: Literal["remove"]

    file: Annotated[str, file_path("remove takes ?file= as a file's path", blank="")]
    """The component."""

    name: Annotated[str, named("remove takes ?name= as an object's name", blank="")]
    """The object whose declaration to take out."""


class DeclarationPlanQuery(
    _Actions[
        Annotated[
            ReadDeclaration | DeclareObject | RemoveDeclaration, Field(discriminator="action")
        ]
    ]
):
    """What ``GET /api/declaration-plan`` takes: one change of a component's interface, by its
    action."""

    route: ClassVar[str] = "declaration-plan"


class ValuePlanQuery(_Query):
    """What ``GET /api/value-plan`` takes: one element of an object's values set."""

    missing: ClassVar[str] = "value-plan takes ?name= and ?at= and ?raw="

    name: Annotated[str, named("value-plan takes ?name= as an object's name")]
    """The object."""

    at: Annotated[str, named("value-plan takes ?at= as an element's indices")]
    """The element, as a json pointer's suffix: ``[2]``, or ``[1][3]``. Its length bounded here,
    so that no index of it holds more digits than a number does; whether it names an element of
    the object is the handler's question."""

    raw: Annotated[str, any_text("value-plan takes ?raw= as a number")]
    """The raw count to store; whether it is a number is the handler's question, answered as a
    refusal of the count."""


class ValuesPlanQuery(_Query):
    """What ``GET /api/values-plan`` takes: every value of an object set at once."""

    missing: ClassVar[str] = "values-plan takes ?name= and ?raw="

    name: Annotated[str, named("values-plan takes ?name= as an object's name")]
    """The object."""

    raw: Annotated[str, any_text("values-plan takes ?raw= as numbers joined by commas")]
    """Every raw count, row-major, joined by commas; whether each is a number is the handler's
    question, answered as a refusal of the count."""
