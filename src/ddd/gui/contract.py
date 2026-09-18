"""The contract of the ``ddd gui`` api: every request and response, declared once.

``src/ddd/gui/api.py`` used to hand-check every request and hand-build every response body,
and ``gui/src/api/types.ts`` was a hand-written TypeScript mirror of those bodies kept in step
by eye - two definitions of one contract, exactly the problem the description files themselves
would have if a project hand-wrote its json schema beside its loader. The package already turns
a pydantic model into a json schema for those files, and the frontend already turns a json
schema into TypeScript for them; the models here let the api travel the same road.

Three things follow from that:

* A request model is strict (:data:`_Request`): an unknown key, a string where an index
  belongs or a boolean where an integer belongs is refused before a handler ever sees it,
  which is what replaces the hand-written checks ``api.py`` used to make.
* A response model is built once a request is answered, then ``model_dump(mode="json")`` -
  never hand-assembled into a ``dict`` - so the shape a test asserts on is the shape the schema
  below describes.
* :func:`api_schema` is the one json schema of the whole api, the way ``ddd schema`` is the one
  json schema of a description file; :mod:`gui.scripts.schemas` turns it into
  ``gui/src/generated/api.ts`` the same way it turns ``ddd schema all`` into the types of the
  description files, so a model added here without a page type fails the suite rather than the
  frontend build.

The api is internal - the page and the server ship in one wheel - so this is not published by
``ddd schema``: see spec section 6.5.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.json_schema import GenerateJsonSchema, models_json_schema

from ddd.diagnostics import Severity
from ddd.ir import DataDictionary

__all__ = [
    "BuildSummary",
    "Change",
    "Changes",
    "CheckInfo",
    "ChecksReply",
    "DictionaryReply",
    "EditReply",
    "EditedFile",
    "FileContent",
    "Finding",
    "FindingCounts",
    "Found",
    "FoundProject",
    "GraphDisagreement",
    "GraphFlow",
    "GraphModule",
    "GraphReply",
    "Note",
    "OpenProject",
    "OpenRequest",
    "Operation",
    "RefusedBuild",
    "SessionInfo",
    "SourceFile",
    "State",
    "api_schema",
]


class _Frozen(BaseModel):
    """Base of every contract model: immutable, and refusing a key it does not declare."""

    model_config = ConfigDict(frozen=True, extra="forbid", use_attribute_docstrings=True)


class _Request(_Frozen):
    """Base of a request body: on top of :class:`_Frozen`, no value is coerced to fit.

    ``strict=True`` is what keeps ``"3"`` from being an index and ``true`` from being an
    integer: a caller's mistake is refused rather than silently reinterpreted. It still accepts
    a field that is left out and one written as json's own ``null`` alike, since both mean the
    same default to a flat operation like :class:`Operation`.
    """

    model_config = ConfigDict(strict=True)


# --- GET /api/session, POST /api/open --------------------------------------------------------


class OpenProject(_Frozen):
    """The project a session has open."""

    path: str
    """Absolute, posix-separated path of the project description."""

    name: str | None
    """Name the project description gives it, or ``None`` when the file did not load that far."""


class BuildSummary(_Frozen):
    """One build record applying to the open project."""

    image: str
    """Build target the record was written for; ``""`` when it named none."""

    strict: bool
    """Whether the build reports warnings as errors."""

    severity: tuple[str, ...]
    """Severity overrides the build applies, as ``check=severity``, in the order given."""


class SessionInfo(_Frozen):
    """What ``GET /api/session`` and ``POST /api/open`` answer."""

    version: str
    """DDD's own version, so the page can show a mismatch with what it was built against."""

    preview: bool
    """Always ``true``: ``ddd gui`` is a preview command, and the page says so."""

    root: str
    """Absolute, posix-separated path of the directory ``ddd gui`` searches for projects."""

    project: OpenProject | None
    """The open project, or ``None`` while none is."""

    builds: tuple[BuildSummary, ...]
    """The build records analysing the open project; empty while none names it or none is open."""


# --- GET /api/projects -------------------------------------------------------------------------


class FoundProject(_Frozen):
    """One project the start page can open."""

    path: str
    """Absolute, posix-separated path of the project description."""

    name: str | None
    """Name its description gives it, or ``None`` when the file did not load that far."""

    images: tuple[str, ...]
    """Build images a build record names this project for; empty for a file found alone."""


class RefusedBuild(_Frozen):
    """A build record found but not usable, and why."""

    record: str
    """Absolute, posix-separated path of the record."""

    reason: str
    """Why it could not be used, as the language server would log it."""


class Found(_Frozen):
    """What ``GET /api/projects`` answers."""

    root: str
    """Absolute, posix-separated path of the directory searched."""

    projects: tuple[FoundProject, ...]
    """Every project found, sorted by path."""

    refused: tuple[RefusedBuild, ...]
    """Every build record found but not usable, sorted by path."""


# --- GET /api/state ------------------------------------------------------------------------


class FindingCounts(_Frozen):
    """How many findings of each severity a file has."""

    error: int
    """How many errors are filed on the file."""

    warning: int
    """How many warnings are filed on the file."""

    info: int
    """How many informational findings are filed on the file."""


class SourceFile(_Frozen):
    """One file the analysis read: what it is, whether it loaded, how much it has to fix."""

    path: str
    """Absolute, posix-separated path of the file."""

    kind: str
    """The top level key that says what the file is, or ``"unknown"`` or ``"plugin"``."""

    name: str | None
    """Name its description gives it, or ``None`` when it has none or the file did not load."""

    loaded: bool
    """Whether the file parsed and matched the shape its kind requires."""

    fingerprint: str
    """The sha-256 of the bytes last read, in hex: what an edit of this file is checked against."""

    findings: FindingCounts
    """How many findings of each severity are filed on this file."""


class Note(_Frozen):
    """An additional hint attached to a finding, e.g. the conflicting declaration site."""

    message: str
    """What the hint says."""

    file: str | None
    """Absolute, posix-separated path the hint points at, or ``None`` when it points nowhere."""

    pointer: str
    """Dotted path inside that file's json document, or ``""`` when the hint names no place."""


class Finding(_Frozen):
    """A single finding, filed on the file it is shown on: both sides of a disagreement are
    filed, one finding per file."""

    file: str
    """Absolute, posix-separated path of the file this copy is filed on."""

    check: str
    """The check that filed this finding, e.g. ``"missing-id"``."""

    severity: Severity
    """How this finding is reported."""

    message: str
    """What the finding says."""

    pointer: str
    """Dotted path inside the file's json document, or ``""`` when the finding names no place."""

    notes: tuple[Note, ...]
    """Additional hints, e.g. the site a definition disagrees with."""


class State(_Frozen):
    """What ``GET /api/state`` answers: one revision of the open project."""

    revision: int
    """Counts up from 1 at every analysis; what a later ``?after=`` waits past."""

    project: str
    """Absolute, posix-separated path of the project description this revision analysed."""

    files: tuple[SourceFile, ...]
    """Every file the analysis read, sorted by path."""

    findings: tuple[Finding, ...]
    """Every finding of the analysis, grouped by the file it is filed on."""


# --- GET /api/file -------------------------------------------------------------------------


class FileContent(_Frozen):
    """What ``GET /api/file`` answers: a description file parsed, or the reason it cannot be.

    ``data`` is the file's own json value, or ``None`` when ``error`` says why there is none;
    it carries no docstring of its own; one would give pydantic a reason to describe it, and a
    described field is no longer the empty schema that turns into ``unknown`` rather than an
    object typed to hold only what today's file happens to be.
    """

    path: str
    """Absolute, posix-separated path of the file."""

    fingerprint: str
    """The sha-256 of the bytes read, in hex, whether or not they parsed."""

    data: Any
    error: str | None
    """Why ``data`` is ``None``, or ``None`` when it parsed."""


# --- GET /api/dictionary -------------------------------------------------------------------


class DictionaryReply(_Frozen):
    """What ``GET /api/dictionary`` answers."""

    revision: int
    """The revision this dictionary was resolved for."""

    dictionary: DataDictionary | None
    """The resolved dictionary, as ``ddd dump`` writes it, or ``None`` when it did not resolve."""


# --- GET /api/graph ------------------------------------------------------------------------


class GraphModule(_Frozen):
    """One module of the project graph: a component, as the canvas draws it."""

    path: str
    """Absolute, posix-separated path of the component's description file."""

    name: str
    """The component's name, or the file's stem when it did not load that far."""

    loaded: bool
    """Whether the file parsed and matched the shape its kind requires."""

    findings: FindingCounts
    """How many findings of each severity are filed on this module."""


class GraphDisagreement(_Frozen):
    """One finding that says the two modules of a flow describe an object differently."""

    object: str | None
    """Name of the object this is about, or ``None`` when it could not be resolved."""

    check: str
    """The check that filed this finding."""

    severity: Severity
    """How this disagreement is reported."""

    message: str
    """What the disagreement says."""


class GraphFlow(_Frozen):
    """Everything one module produces for another."""

    model_config = ConfigDict(populate_by_name=True)

    source: str = Field(alias="from")
    """Absolute, posix-separated path of the module that owns the objects that flow.

    Named ``source`` here - ``from`` is a python keyword - and carried under its alias, so
    that the json this answers with spells the key the way spec section 4.5 does.
    """

    to: str
    """Absolute, posix-separated path of the module that reads them."""

    objects: tuple[str, ...]
    """Names of the objects that flow from the source to the target, sorted."""

    severity: Severity | None
    """The worst of the flow's disagreements, or ``None`` when the two modules agree."""

    disagreements: tuple[GraphDisagreement, ...]
    """Every disagreement between the two modules; empty when they agree."""


class GraphReply(_Frozen):
    """What ``GET /api/graph`` answers: one revision's modules and the flows between them."""

    revision: int
    """The revision this graph was built from."""

    dictionary: bool
    """Whether the revision resolved a dictionary.

    ``False`` is a plugin that raised or a file that did not parse, and it is the only thing
    that tells that apart from a project whose modules genuinely share nothing: both answer
    their modules and no flows, and spec section 5.6 asks the page to say so only for the
    first.
    """

    modules: tuple[GraphModule, ...]
    """Every component of the project, sorted by path."""

    flows: tuple[GraphFlow, ...]
    """Every flow between two modules, sorted by source then target."""


# --- GET /api/checks -----------------------------------------------------------------------


class CheckInfo(_Frozen):
    """Static description of one consistency check, built in or a plugin's own."""

    check: str
    """The check's identifier, e.g. ``"unused-output"``, or a plugin's own prefixed with its
    name and ``/``."""

    default_severity: Severity
    """Severity the check is reported at unless a build or a project overrides it."""

    description: str
    """What the check verifies."""

    overridable: bool
    """Whether a build or a project may change the severity this check is reported at."""

    needs_every_component: bool
    """Whether the check reaches the wrong answer when a component is missing."""

    comparison: bool
    """Whether the check grades a difference between two deliveries rather than one project."""


class ChecksReply(_Frozen):
    """What ``GET /api/checks`` answers."""

    checks: tuple[CheckInfo, ...]
    """The built-in checks, in the order :data:`ddd.diagnostics.CHECKS` declares them, followed
    by the open project's plugin checks."""


# --- POST /api/open ------------------------------------------------------------------------


class OpenRequest(_Request):
    """What ``POST /api/open`` takes: the project to open."""

    path: str
    """Absolute path of one of the projects ``GET /api/projects`` found, or the one named on
    the command line."""


# --- POST /api/edit ------------------------------------------------------------------------


class Operation(_Request):
    """One change at one pointer.

    Flat rather than one shape per ``op``, the way :class:`ddd.editing.Operation` already is:
    ``raw`` and ``to`` are left out (or given as json's own ``null``) by whichever operation
    does not use them, and the engine - not this contract - is what refuses one that needed a
    value it was not given.
    """

    op: Literal["set", "remove", "insert", "move"]
    """Which of the four operations this is."""

    pointer: str
    """Dotted path to the value this operation acts on."""

    raw: str | None = None
    """The value ``set`` or ``insert`` writes, as json text - never parsed here, so that ``1.0``
    reaches the engine as the three characters it was typed as, not the integer ``1``."""

    to: int | None = None
    """The index ``move`` sends the element to."""


class Change(_Request):
    """The operations for one file, and the fingerprint of the bytes they were computed for."""

    file: str
    """Absolute, posix-separated path of the file this change is made to."""

    fingerprint: str
    """The fingerprint the file was read at; refused as ``stale`` if it has since changed."""

    operations: tuple[Operation, ...] = Field(min_length=1)
    """The operations to apply to the file, in order."""


class Changes(_Request):
    """What ``POST /api/edit`` takes: every file it changes, in one all-or-nothing edit."""

    changes: tuple[Change, ...] = Field(min_length=1)
    """Every file this edit changes; made all at once, or not at all."""


class EditedFile(_Frozen):
    """One file an edit wrote, and the fingerprint to check it against next."""

    path: str
    """Absolute, posix-separated path of the file that was written."""

    fingerprint: str
    """The file's new fingerprint."""


class EditReply(_Frozen):
    """What ``POST /api/edit`` answers: the new revision, and each file it wrote."""

    revision: int
    """The revision the edit produced."""

    files: tuple[EditedFile, ...]
    """Every file the edit wrote."""


# --- The one schema of the whole api ---------------------------------------------------------


class _ApiSchema(GenerateJsonSchema):
    """The json schema generator behind :func:`api_schema`.

    Pydantic titles every property by default, which is meant for a field with no model of its
    own to name it - ``age`` becomes ``"title": "Age"``. Applied to a bag of models that are
    all properties of *something*, it instead turns a one-line ``file: str`` into its own
    hoisted type - ``File``, ``File1``, ``File2`` for every model that happens to have a field
    of that name - the moment ``json-schema-to-typescript`` sees it, which is noise a property
    name already is. A model or an enum keeps its own title, which is the name each of them is
    published under.
    """

    def field_title_should_be_set(self, schema: Any) -> bool:
        return False


_ENDPOINTS: tuple[tuple[type[BaseModel], Literal["validation", "serialization"]], ...] = (
    (SessionInfo, "serialization"),
    (Found, "serialization"),
    (OpenRequest, "validation"),
    (State, "serialization"),
    (FileContent, "serialization"),
    (DictionaryReply, "serialization"),
    (GraphReply, "serialization"),
    (ChecksReply, "serialization"),
    (Changes, "validation"),
    (EditReply, "serialization"),
)
"""Every request and response of spec section 6.5, with the schema pydantic builds for each:
``"validation"`` for a request, read for the shape a caller must send; ``"serialization"`` for
a response, read for the shape ``model_dump(mode="json")`` produces - the two differ wherever a
field has a default, :class:`DictionaryReply`'s nested dictionary included.

Nothing else needs listing: every other model above is reachable from one of these and is
published under ``$defs`` regardless, :class:`Operation` and :class:`Severity` included.
"""


def api_schema() -> dict[str, Any]:
    """The json schema of the whole ``ddd gui`` api, every model of it under ``$defs``.

    What :mod:`gui.scripts.schemas` reads to write ``gui/src/generated/api.ts``, the way it
    reads ``ddd schema all`` to write the types of the description files. Not one schema per
    endpoint: a page building one request out of several answers, an edit out of a finding's
    pointer, needs the whole vocabulary in one file with one name per shape, which is what a
    single document under ``$defs`` gives it and eight separate ones would not.
    """
    _, schema = models_json_schema(
        _ENDPOINTS,
        title="ddd gui API",
        description=(
            "The internal json api of `ddd gui`, a preview command: it changes with the "
            "package and is not a contract published to `ddd schema`."
        ),
        schema_generator=_ApiSchema,
    )
    return schema
