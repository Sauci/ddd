"""What every route of the ddd gui api takes in its query, and the types its values are read as.

A query arrives as text, one value a key (:func:`ddd.gui.routes.one_value_each`). Each route's
model says which keys it takes, and reads each value as the type it is: the model answers for
form - a number's digits, a path's shape, json's depth - and the route's handler for meaning, as
before. Every refusal a model makes is one sentence: the route's own, word for word, where it
already said one about that key (Appendix A of ``docs/superpowers/plans/2026-10-05-gui-
security.md``).

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
from typing import Annotated, ClassVar, Final, get_args

from pydantic import BaseModel, BeforeValidator, ConfigDict, RootModel, ValidationInfo
from pydantic.json_schema import SkipJsonSchema
from pydantic_core import PydanticCustomError

from ddd.diagnostics import Severity
from ddd.editing import EditError, not_one_value, parse_raw
from ddd.loading import NESTED_TOO_DEEPLY
from ddd.lsp.edits import PROPAGATED_KEYS

MAX_DIGITS: Final = 9
"""The most digits a whole number of a query has: a page offset, a version, a cell's index -
every one far below a billion, and ``int()`` of more than 4,300 digits raises."""

MAX_PATH: Final = 4096
"""The longest path a query names; ``PATH_MAX`` on Linux, beyond any project's."""

MAX_NAME: Final = 1024
"""The longest name a query gives: a variable, a unit, a type."""

MAX_DEPTH: Final = 64
"""The deepest json a query carries: a description nests a value five or six levels down."""

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
    Windows (:data:`_CASELESS`) every letter in one case."""
    folded = text.replace("\\", "/")
    if _CASELESS:
        return folded.casefold()
    return folded


def _under(text: str, directories: Iterable[str]) -> bool:
    """Whether ``text`` names one of ``directories``, or a path under one: compared as text, so
    that nothing is resolved - and no network asked - to tell."""
    given = _folded(text)
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
    which Windows would open for the asking. One under such a directory is the network path a
    mapped drive resolves to there, and is read like any other. Whether the path is a file of
    the project is the handler's question, as before.
    """

    def read(value: object, info: ValidationInfo) -> str:
        if isinstance(value, str) and _absolute(value, _serving(info).served):
            return value
        raise refusal(sentence)

    return _validator(read, blank)


def _absolute(text: str, served: Iterable[str]) -> bool:
    """Whether ``text`` is a path :func:`file_path` takes, ``served`` the directories a network
    path may name one under. A statement a rule, rather than one condition, so that the coverage
    gate sees each rule decide."""
    if not text:
        return False
    if len(text) > MAX_PATH:
        return False
    if "\x00" in text:
        return False
    if not _encodable(text):
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


def _json(value: object) -> str:
    """``value``, where it is json text :func:`json_text` takes, or the refusal of it in
    :func:`~ddd.editing.parse_raw`'s words."""
    if isinstance(value, str) and _depth(value) > MAX_DEPTH:
        raise not_one_value(value, NESTED_TOO_DEEPLY)
    parse_raw(value)
    assert isinstance(value, str)  # parse_raw refuses anything that is not text
    try:
        json.loads(value, parse_float=_finite)
    except ValueError as error:
        raise not_one_value(value, error) from None
    return value


def _depth(text: str) -> int:
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


class Unread(_Query):
    """Every key given, one value each, left for the route's handler to read: the query of the
    plan routes, which read theirs by hand still. Takes any key."""

    model_config = ConfigDict(extra="allow")

    @property
    def values(self) -> dict[str, str]:
        """The values given, by their key."""
        return dict(self.model_extra or {})


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
    where it must not reach compare.py: nothing at all; a lone surrogate; and a network or device
    form naming no path under a directory served, which resolving would open on Windows. That
    one lies outside the root as written, and is refused in the words compare.py refuses a path
    outside it with, before anything resolves it."""
    if not isinstance(value, str) or not value or not _encodable(value):
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
