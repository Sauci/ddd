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

__all__ = [
    "BuildSummary",
    "Change",
    "Changes",
    "CheckInfo",
    "ChecksReply",
    "CompareReply",
    "ConstantReply",
    "ConstantUse",
    "DeclarableName",
    "DeclarableReply",
    "DictionaryReply",
    "EditReply",
    "EditedFile",
    "FileContent",
    "Finding",
    "FindingCounts",
    "FindingRoute",
    "FixOffered",
    "FixReply",
    "Found",
    "FoundProject",
    "GraphDisagreement",
    "GraphFlow",
    "GraphModule",
    "GraphReply",
    "GridAxis",
    "Hunk",
    "KindForm",
    "Note",
    "OpenProject",
    "OpenRequest",
    "Operation",
    "PlanReply",
    "PlannedChange",
    "PlannedOperation",
    "ProjectType",
    "ProjectUnit",
    "RefusedBuild",
    "Renamed",
    "SessionInfo",
    "SettleReply",
    "SharedEntry",
    "SharedReply",
    "SourceFile",
    "State",
    "TypeMember",
    "TypeReply",
    "TypeUse",
    "TypesReply",
    "UndoPreview",
    "UndoReply",
    "UndoRequest",
    "UndoableEdit",
    "UndoneChange",
    "UnitEntry",
    "UnitPlace",
    "UnitReply",
    "UnitsReply",
    "UsedUnit",
    "ValuesReply",
    "VariableDeclaration",
    "VariableKeyCarried",
    "VariableKeyOffer",
    "VariableKeyValue",
    "VariableReply",
    "VocabularyUnit",
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


class FindingRoute(_Frozen):
    """What the page can open for a finding."""

    kind: Literal[
        "variable", "unit", "component", "type", "values", "constant", "section", "raster"
    ]
    """Which screen: a variable's panel, a unit's panel, the component's own page, the type's
    own panel on the Types tab, an object's values grid, or a constant's, a section's or a
    raster's own panel on the Shared files tab.

    Every kind :class:`ddd.finding_routes.Route` answers has to be a member here: ``_finding``
    in :mod:`ddd.gui.api` builds this model for every finding of every request, so a kind left
    out raises a :class:`pydantic.ValidationError` rather than merely leading nowhere.
    """

    name: str | None
    """The variable's name, the unit's spelling or the type's name; ``None`` for a component,
    which the finding's own ``file`` already names."""


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

    route: FindingRoute | None
    """Where pressing this finding leads, or ``None`` when the page has nothing to open: its
    file did not load, its file is not a component and has no screen yet, or it names no place
    at all."""


class UndoableEdit(_Frozen):
    """The edit an undo would put back: what the control on the page offers."""

    at: int
    """What the session numbered that edit, which ``POST /api/undo`` takes back."""

    label: str
    """What the page called it when it applied it."""


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

    undoable: UndoableEdit | None
    """The last edit the interface made and has not put back, or ``None`` when it has made
    none: what makes the Undo control appear without a request of its own."""


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

    dictionary: dict[str, Any] | None
    """The resolved dictionary, or ``None`` when it did not resolve.

    Left untyped rather than declared as :class:`ddd.ir.DataDictionary`: this is that model's
    own ``model_dump(mode="json")`` payload, so its schema is the one ``ddd schema dictionary``
    already publishes and its TypeScript type is the one the page already generates as
    ``dictionary.ts`` - declaring it here too would carry the whole file format's ``$defs`` into
    the api schema a second time, under a second name, which is exactly the duplication this
    contract exists to remove."""


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


# --- GET /api/variable ----------------------------------------------------------------------


class VariableDeclaration(_Frozen):
    """One declaration of a variable, as its file states it now."""

    path: str
    """Absolute, posix-separated path of the file declaring it."""

    pointer: str
    """Dotted path of the declaration's definition inside that file."""

    component: str
    """Name of the component declaring it."""

    role: Literal["produces", "reads", "local"]
    """What the component does with the variable, by the declaration's scope."""

    stated: dict[str, str]
    """The json text of ``kind`` and of every key the declarations of a variable agree on that
    this one states, spelled as the file spells it."""

    type: str | None
    """The declared type it names, or ``None``."""

    fixed: dict[str, str]
    """The json text of each key that type fixes (``datatype``, ``unit``, ``conversion``,
    ``limits``), empty without a type."""


class VariableKeyCarried(_Frozen):
    """What one declaration's kind does with a key."""

    allowed: bool
    """Its kind has the key at all: ``dimensions`` on a measurement, never on a parameter."""

    required: bool
    """It cannot be left without it, so the panel offers no "state nothing" for the key."""


class VariableKeyValue(_Frozen):
    """One value a key has among the declarations, and who has it."""

    raw: str
    """The json text, as the file that carries it spells it.

    One entry per value rather than per spelling: two files writing one conversion with its keys
    in a different order state the same conversion, and this is the producer's spelling of it.
    """

    components: tuple[str, ...]
    """The components stating it, in the order the project lists them."""

    producer: bool
    """The producer is one of them; the panel marks that entry."""


class VariableKeyOffer(_Frozen):
    """What one key of a variable offers: a row of the panel, and the chooser the row opens."""

    key: str
    """One of the twelve keys every declaration of an object has to agree on."""

    carried: tuple[VariableKeyCarried, ...]
    """One per declaration, aligned with ``VariableReply.declarations``."""

    values: tuple[VariableKeyValue, ...]
    """Every distinct value in play, the producer's first."""

    disagrees: bool
    """The declarations do not all say the same thing about the key."""

    editor: Literal["unit", "datatype", "typename", "volatile", "limits", "size", "name", "none"]
    """Which field the page offers beside the values in play.

    ``none`` is not "nothing may be chosen": a value in play is always offered, and for a
    ``conversion`` or a ``dimensions`` that is all - an editor composes those better than a
    panel would.
    """

    choices: tuple[str, ...]
    """What that field names, sorted: the datatypes, the project's types, its declared constants
    or its objects of the kind the key takes. Empty for a field that names nothing."""


class VariableReply(_Frozen):
    """What ``GET /api/variable`` answers: one variable's declarations and the findings filed on
    them."""

    revision: int
    """The revision this answer was read from."""

    name: str
    """The variable named in the request."""

    declarations: tuple[VariableDeclaration, ...]
    """Every declaration the file still holds, in the order the project lists its components."""

    keys: tuple[VariableKeyOffer, ...]
    """What every shared key offers for these declarations, in the order a definition spells
    them (``ddd.variable_keys.KEY_ORDER``). The page groups the rows it draws; the order here
    is what it keeps inside each group."""

    findings: tuple[Finding, ...]
    """Every finding located on one of them, both sides of a disagreement included."""


# --- GET /api/units -------------------------------------------------------------------------


class VocabularyUnit(_Frozen):
    """One unit a project's units files declare."""

    unit: str
    """A spelling the project declares."""

    description: str | None
    """What it means, or ``None``."""


class UsedUnit(_Frozen):
    """One unit a declaration states, and how widely."""

    unit: str
    """A unit a declaration states."""

    variables: int
    """How many variables state it."""


class ProjectUnit(_Frozen):
    """One row of the Units tab: a spelling the project states or its vocabulary lists."""

    unit: str
    """The spelling, exactly: ``rpm`` and ``RPM`` are two units."""

    description: str | None
    """What the vocabulary says it means, or ``None`` outside the vocabulary, without one, or
    for an entry that is a spelling alone."""

    files: tuple[str, ...]
    """Absolute, posix-separated paths of the units files listing it; empty outside the
    vocabulary."""

    variables: int
    """How many variables state it."""

    types: int
    """How many scalar types state it."""

    members: int
    """How many structure members state it."""

    findings: int
    """How many ``unknown-unit`` and ``duplicate-unit`` findings are filed on the places stating
    it and the entries listing it."""


class UnitsReply(_Frozen):
    """What ``GET /api/units`` answers: the project's declared vocabulary, its units in use, and
    the Units tab's rows."""

    revision: int
    """The revision this answer was read from."""

    vocabulary: tuple[VocabularyUnit, ...] | None
    """The units the project's units files declare, or ``None`` when it has none, which keeps
    its units free."""

    used: tuple[UsedUnit, ...]
    """Every unit in use, most used first."""

    units: tuple[ProjectUnit, ...]
    """Every unit the project states or its vocabulary lists, by spelling."""

    adoptable: int | None
    """How many units adopting a vocabulary would list - every unit in use - or ``None`` when
    the project has a units file."""


# --- GET /api/unit --------------------------------------------------------------------------


class UnitEntry(_Frozen):
    """One entry of the vocabulary listing a unit."""

    file: str
    """Absolute, posix-separated path of the units file."""

    pointer: str
    """Dotted path of the entry inside that file, ``units[i]``."""


class UnitPlace(_Frozen):
    """One place a unit is stated: a variable's declaration, a scalar type or a structure member."""

    path: str
    """Absolute, posix-separated path of the file stating it."""

    pointer: str
    """Dotted path of the unit's own string inside that file."""

    kind: Literal["variable", "type", "member"]
    """What states it."""

    name: str
    """The variable's name, the type's, or ``Type.member`` for a structure member."""

    component: str | None
    """The component declaring the variable; ``None`` for a type or a member."""

    role: str | None
    """What that component does with the variable - ``produces``, ``reads`` or ``local`` - by the
    declaration's scope; ``None`` for a type or a member."""


class UnitReply(_Frozen):
    """What ``GET /api/unit`` answers: one unit's panel."""

    revision: int
    """The revision this answer was read from."""

    unit: str
    """The unit named in the request."""

    description: str | None
    """What the vocabulary says it means, or ``None`` outside the vocabulary, without one, or for
    an entry that is a spelling alone."""

    entries: tuple[UnitEntry, ...]
    """Every vocabulary entry listing it; more than one is a ``duplicate-unit``."""

    sites: tuple[UnitPlace, ...]
    """Every place stating it, in the order the navigation index recorded them."""

    findings: tuple[Finding, ...]
    """Every ``unknown-unit`` and ``duplicate-unit`` finding filed on one of its places or
    entries."""


# --- GET /api/settle ------------------------------------------------------------------------


class PlannedOperation(_Frozen):
    """One change at one pointer, as a preview comes to it."""

    op: Literal["set", "remove", "insert"]
    """Which operation this is: a settlement sets and removes, and a unit's plan inserts too."""

    pointer: str
    """Dotted path to the value this operation acts on."""

    raw: str | None
    """The json text ``set`` writes, or ``None`` for ``remove``."""


class Hunk(_Frozen):
    """Lines of one file a change replaces, numbered as the file stands before it."""

    line: int
    """The first line replaced, counting from 1, as the file stands."""

    before: tuple[str, ...]
    """The lines the change replaces."""

    after: tuple[str, ...]
    """The lines that replace them."""


class PlannedChange(_Frozen):
    """The edit of one file a preview comes to, and the lines it changes."""

    file: str
    """Absolute, posix-separated path of the file this change is made to."""

    fingerprint: str | None
    """What the file was read at, which ``POST /api/edit`` checks; ``None`` for a file the
    change creates."""

    operations: tuple[PlannedOperation, ...]
    """The operations to apply to the file, in order."""

    hunks: tuple[Hunk, ...]
    """The lines the operations change; the page drops these and posts the rest to
    ``POST /api/edit``."""


class SettleReply(_Frozen):
    """What ``GET /api/settle`` answers: the preview of making a variable's declarations agree."""

    revision: int
    """The revision this preview was computed from."""

    changes: tuple[PlannedChange, ...]
    """One per file, sorted by path; empty when every declaration already agrees."""


# --- GET /api/fix ---------------------------------------------------------------------------


class FixOffered(_Frozen):
    """One fix a finding carries, previewed."""

    title: str
    """What the button says."""

    changes: tuple[PlannedChange, ...]
    """One per file, as ``POST /api/edit`` takes them, beside the lines each would change."""


class FixReply(_Frozen):
    """What ``GET /api/fix`` answers: every fix one finding carries."""

    revision: int
    """The revision the previews were computed from."""

    fixes: tuple[FixOffered, ...]
    """Empty for a finding that carries none, which is most of them."""


# --- GET /api/unit-plan ---------------------------------------------------------------------


class PlanReply(_Frozen):
    """What ``GET /api/unit-plan`` answers: the preview of one change of the project's units."""

    revision: int
    """The revision this preview was computed from."""

    changes: tuple[PlannedChange, ...]
    """One per file, sorted by path; a file the change creates has no fingerprint, and one hunk
    at line 1 that is the whole of it."""


# --- GET /api/types, GET /api/type -----------------------------------------------------------


class ProjectType(_Frozen):
    """One row of the Types tab."""

    name: str
    """The type's name, as its entry spells it."""

    kind: str
    """``scalar``, ``external`` or ``struct``; ``""`` for an entry whose file has drifted."""

    description: str
    """What the entry says it is; ``""`` where it says nothing."""

    uses: int
    """How many declarations and structure members name it."""

    findings: int
    """How many findings are filed inside its entry."""


class TypesReply(_Frozen):
    """What ``GET /api/types`` answers: every type the project declares, sorted by name."""

    revision: int
    types: tuple[ProjectType, ...]


class TypeUse(_Frozen):
    """One place a type is named."""

    path: str
    """Absolute, posix-separated path of the file naming it."""

    pointer: str
    """Dotted path of the ``typename`` inside that file."""

    kind: Literal["variable", "member"]
    """A declaration's ``typename``, or a structure member's."""

    name: str
    """The variable's name, or ``Sensor_t.latest`` for a member."""

    component: str | None
    """The component declaring the variable; ``None`` for a member."""

    role: str | None
    """``produces``, ``reads`` or ``local``; ``None`` for a member."""


class TypeMember(_Frozen):
    """One member of a structure, as its panel lists it."""

    name: str
    member: Literal["value", "bits"]
    """Whether it holds a value or a field of bits."""

    typename: str | None
    """The type it names, or ``None`` when it carries a datatype of its own."""

    datatype: str | None
    unit: str | None
    bits: int | None
    dimensions: tuple[str, ...]
    """Each dimension as text: an integer, or the name of a declared constant."""


class TypeReply(_Frozen):
    """What ``GET /api/type`` answers: one type's panel."""

    revision: int
    name: str
    kind: str
    file: str
    """Absolute, posix-separated path of the file declaring it: a types file, or a component
    that declares it inline alongside its interface."""

    pointer: str
    """Dotted path of its entry: ``types[i]`` in a types file, or ``component.types[i]`` in a
    component that declares it inline."""

    description: str
    header: str | None
    """An external type's header; ``None`` for the other two kinds."""

    keys: tuple[VariableKeyOffer, ...]
    """What a scalar fixes - ``datatype``, ``unit``, ``conversion``, ``limits`` - in that order,
    each offering what part 3's chooser draws. Empty for a structure and an external, which fix
    nothing a chooser edits."""

    uses: tuple[TypeUse, ...]
    members: tuple[TypeMember, ...]
    """A structure's members in the file's order; empty for the other two kinds."""

    findings: tuple[Finding, ...]


# --- GET /api/shared, GET /api/constant, GET /api/section, GET /api/raster -------------------


class SharedEntry(_Frozen):
    """One row of the Shared files tab."""

    kind: str
    """Which vocabulary the row belongs to: ``constant``, ``section`` or ``raster``.

    A plain ``str`` and not a ``Literal``, which is why no generic function had to change when
    sections joined the tab, nor when rasters did: the table holds whatever
    :data:`ddd.project_shared.HELD` holds, and the word is the descriptor's own
    :attr:`~ddd.project_shared.Vocabulary.kind`.
    """

    name: str
    """Its name, as its entry spells it."""

    states: str
    """What the entry states, in the one cell the table gives a row for it: a constant its value
    as the json text its file spells (``16``, ``2.0``), a section its access and its alignment
    together (``read-only, align 4``), a raster its event and its cycle (``event 1, 10ms``).

    Composed per vocabulary on the server, by
    :attr:`ddd.project_shared.Vocabulary.states`, so the table learns nothing about what any one
    kind holds. ``value`` was the name while constants were alone in the tab and described a
    section's cell wrongly on both counts - it is neither one value nor json text."""

    uses: int
    """How many shapes name it."""

    findings: int
    """How many findings are filed inside its entry or at a shape naming it."""


class SharedReply(_Frozen):
    """What ``GET /api/shared`` answers: every entry the project declares, across the kinds this
    tab holds, sorted by kind then name."""

    revision: int
    """The revision this answer was read from."""

    entries: tuple[SharedEntry, ...]


class ConstantUse(_Frozen):
    """One shape that names a constant."""

    path: str
    """Absolute, posix-separated path of the file naming it."""

    pointer: str
    """Dotted path of the constant's own string inside that file: a declaration's ``dimensions``
    entry or its axis ``size``, or a structure member's ``dimensions`` entry."""

    kind: Literal["variable", "member"]
    """A declaration's dimension or axis size, or a structure member's dimension."""

    name: str
    """The variable's name, or ``Sample_t.history`` for a structure member."""

    component: str | None
    """The component declaring the variable; ``None`` for a member, whose structure may be
    declared in a types file no component owns."""


class ConstantReply(_Frozen):
    """What ``GET /api/constant`` answers: one constant's panel."""

    revision: int
    """The revision this answer was read from."""

    name: str
    """The constant named in the request."""

    value: str
    """The json text its entry states as ``value``, exactly as its file spells it: ``16``,
    ``2.0`` - never re-serialised, so a whole constant and a fractional one keep the spelling
    that tells them apart."""

    description: str
    """What its entry states as ``description``; ``""`` where it states none."""

    file: str
    """Absolute, posix-separated path of the file declaring it: a constants file, or a component
    that declares it inline alongside its interface."""

    pointer: str
    """Dotted path of its entry: ``constants[i]`` in a constants file, or
    ``component.constants[i]`` in a component that declares it inline."""

    uses: tuple[ConstantUse, ...]
    """Every shape naming it, in the order the navigation index recorded them."""

    findings: tuple[Finding, ...]
    """Every finding filed inside its entry or at a shape naming it."""


class SectionUse(_Frozen):
    """One definition that places its data in a section."""

    path: str
    """Absolute, posix-separated path of the component declaring it."""

    pointer: str
    """Dotted path of the definition's own ``section`` key inside that file:
    ``component.interface[i].definition.section``, the one shape that names a section."""

    kind: Literal["variable"]
    """Always a variable, unlike :class:`ConstantUse`: a section is named by a definition and
    nowhere else, so the reader is being shown which variable sits there. :class:`RasterUse.kind`
    is where that stopped being true of every vocabulary, a component naming a raster directly for
    everything it produces."""

    name: str
    """The variable's name."""

    component: str | None
    """The component declaring the variable, or ``None`` where its file no longer declares it
    under that name at the site the analysis read - the same drift
    :class:`ConstantUse.component` reports, rather than a home a section can be named from."""


class SectionReply(_Frozen):
    """What ``GET /api/section`` answers: one memory section's panel.

    Beside :class:`ConstantReply` rather than folded into it: a constant's panel edits one value
    and a section's three keys, and a model carrying whichever of them the kind happened to have
    would make every field optional on the page for the sake of sharing a name.
    """

    revision: int
    """The revision this answer was read from."""

    name: str
    """The section named in the request, as its entry spells it: ``.calib``."""

    access: str
    """What its entry states as ``access`` - ``read-only`` or ``read-write`` - without its json
    quotes, so the panel's chooser is given the value and not its source."""

    alignment: str
    """The json text its entry states as ``alignment``, exactly as its file spells it: ``4``.

    Text and not a number, for the reason a constant's ``value`` is text: the model wants a whole
    number, and a value that travelled as one of python's own would come back ``4.0`` and stop the
    file loading."""

    description: str
    """What its entry states as ``description``; ``""`` where it states none."""

    file: str
    """Absolute, posix-separated path of the sections file declaring it. Always a sections file,
    where a constant may also be declared inline by a component: a section has the one home."""

    pointer: str
    """Dotted path of its entry: ``sections[i]``."""

    uses: tuple[SectionUse, ...]
    """Every definition placing its data in it, in the order the navigation index recorded
    them."""

    findings: tuple[Finding, ...]
    """Every finding filed inside its entry or at a definition placing data in it."""


class RasterUse(_Frozen):
    """One shape that names a raster: a definition measured in it, or a component measuring
    everything it produces in it."""

    path: str
    """Absolute, posix-separated path of the component naming it."""

    pointer: str
    """Dotted path of the ``raster`` key inside that file: ``component.raster`` for a component's
    own default, ``component.interface[i].definition.raster`` for a definition's own - the two
    shapes :data:`ddd.lsp.navigation._RASTER_KEY` spells."""

    kind: Literal["variable", "component"]
    """Which of the two the use is. Wider than :class:`SectionUse.kind`, and the widening is the
    one :class:`SectionUse.kind`'s own docstring predicted: a component's default sits inside no
    definition at all, so unlike a placement it names no variable. Not nested with
    :class:`ConstantUse.kind` either way, though, and no ``kind`` literal here is nested with
    another: each names the shapes its own vocabulary is named at, and those are different
    questions. A constant's second word is ``member``, which this one never carries - a structure
    member states a unit and a dimension, and nothing samples it."""

    name: str
    """The variable's name, or the component's own where it names the raster directly: there is
    no variable between a component and its default to name instead."""

    component: str | None
    """The component the use was read in: the one declaring the variable, or the one naming the
    raster as its own default.

    Optional because :attr:`ddd.project_shared.Use.component` is - a constant's structure member
    has no component - and never absent in an answer about a raster. A definition whose file no
    longer declares that variable where the analysis read it is left out of ``uses`` altogether
    rather than listed without one, and a component's own default is named by its file when the
    file itself has dropped its ``name``, which :func:`ddd.variables.component_of` falls back
    to."""


class RasterReply(_Frozen):
    """What ``GET /api/raster`` answers: one measurement raster's panel.

    Beside :class:`SectionReply` rather than folded into it, for the reason that model gives
    about :class:`ConstantReply`: the three vocabularies state different keys, and a model
    carrying whichever the kind happened to have would make every field optional on the page.
    """

    revision: int
    """The revision this answer was read from."""

    name: str
    """The raster named in the request, as its entry spells it: ``10ms``."""

    event: str
    """The json text its entry states as ``event``, exactly as its file spells it: ``1``.

    Text and not a number, for the reason :attr:`SectionReply.alignment` is text: the model wants
    a whole number written without a decimal point, and a value that travelled as one of python's
    own would come back ``1.0`` and stop the file loading."""

    cycle: str
    """What its entry states as ``cycle`` - ``10ms`` - without its json quotes; ``""`` where it
    states none, and ``""`` too where it states an explicit ``null``, which
    :attr:`ddd.project_shared.RASTERS.strings` is what decides. An event that is not cyclic is a
    real kind of raster rather than an omission."""

    description: str
    """What its entry states as ``description``; ``""`` where it states none."""

    file: str
    """Absolute, posix-separated path of the rasters file declaring it. Always a rasters file,
    where a constant may also be declared inline by a component: a raster has the one home, as a
    section does."""

    pointer: str
    """Dotted path of its entry: ``rasters[i]``."""

    uses: tuple[RasterUse, ...]
    """Every shape naming it, in the order the navigation index recorded them: per component, its
    own default ahead of its own definitions'."""

    findings: tuple[Finding, ...]
    """Every finding filed inside its entry or at a shape naming it, less the ones
    :data:`ddd.finding_routes.ABOUT_THE_DECLARATION` says are the declaration's."""


# --- GET /api/declarable ---------------------------------------------------------------------


class DeclarableName(_Frozen):
    """One variable a component could read, as its name field offers it."""

    name: str
    kind: str
    """``measurement`` … ``axis``, or empty when no declaration of it states one."""

    producer: str | None
    """The component producing it; ``null`` when nothing does."""

    scopes: tuple[str, ...]
    """Which scopes this name may be declared with here, in the form's own order: reading
    always, producing only while nothing produces it, and never a local beside another
    declaration."""


class KindForm(_Frozen):
    """What one kind of object asks for when it is declared new."""

    kind: str
    keys: tuple[VariableKeyOffer, ...]
    """One offer per key the kind accepts, with no value in play: the same shape a variable's
    panel draws, so one chooser draws both."""


class DeclarableReply(_Frozen):
    """What ``GET /api/declarable`` answers: what this component may add to its interface."""

    revision: int
    file: str
    """Absolute, posix-separated path of the component asked about."""

    names: tuple[DeclarableName, ...]
    kinds: tuple[KindForm, ...]
    scopes: tuple[str, ...]
    """What a name the project has never seen may be declared with."""

    constants: tuple[str, ...]
    """Every constant the project declares, by name, sorted: what a ``dimensions`` row offers
    beside a whole number typed.

    Its own field rather than the ``choices`` of the ``dimensions`` offer, which ``KeyOffer``
    leaves empty: ``variable_keys`` answers the same offer to a variable's panel, where
    ``dimensions`` is the key that panel deliberately does not edit, and widening a shared
    answer to serve one caller would change what the other is told. A value block's shape is
    the one place this form asks for a size per dimension, and the names it may use are a fact
    about the project rather than about any one key."""


# --- GET /api/values, GET /api/value-plan ----------------------------------------------------


class GridAxis(_Frozen):
    """One axis a grid is laid against."""

    position: str
    """Which of ``axis``, ``x_axis`` or ``y_axis`` names it."""

    name: str
    unit: str

    breakpoints: tuple[float, ...]
    """Raw, as the axis's own producer writes them; the page reads them through
    ``conversion``, which is the axis's and not the object's."""

    conversion: dict[str, Any]
    """The axis's own conversion, in the file format's own shape: left untyped rather than a
    model, exactly as :attr:`DictionaryReply.dictionary` is, so its schema is not published
    under ``$defs`` a second time."""


class ValuesReply(_Frozen):
    """What ``GET /api/values`` answers: one object's grid, and everything needed to read it."""

    revision: int
    """The revision this answer was read from."""

    name: str
    """The object named in the request."""

    kind: str
    datatype: str
    unit: str

    conversion: dict[str, Any]
    """The object's own conversion, carried the same way :attr:`GridAxis.conversion` is."""

    minimum: float
    """The resolved physical limits. Shown, never enforced: nothing in the analysis weighs an
    init against them, and refusing here would leave cells a person wrote by hand that this
    cannot edit."""

    maximum: float

    shape: tuple[int, ...]
    """Fully numeric, whatever a dimension is spelled with in the file."""

    rows: tuple[tuple[float, ...], ...]
    """Always rows: a one dimensional object is one row, so one shape serves both."""

    stated: Literal["array", "scalar", "text", "none"]
    """What the producer writes: the values themselves, one value standing for every element,
    text - which is no grid - or nothing, which the startup code zeroes."""

    axes: tuple[GridAxis, ...]
    """One entry per axis this object references, in the order a grid lays them out."""

    owner: str | None
    """Component owning the object; ``None`` only when nothing produces it at all, which is
    what tells that read-only grid from the one more than one producer leaves."""

    file: str | None
    """Absolute, posix-separated path of the producing declaration; ``None`` where there is not
    exactly one of them, which is a grid that can be read and not changed."""

    findings: tuple[Finding, ...]
    """Every finding filed on the object's own ``init``."""


# --- GET /api/compare ------------------------------------------------------------------------


class Renamed(_Frozen):
    """One object the baseline and the candidate agree is the same, called differently now."""

    id: str
    """The object's persistent id - a structure member's is its instance's id followed by its
    path below the instance, so one row still names each member of a renamed variable."""

    old: str
    """The name the baseline gave it."""

    new: str
    """What the candidate calls it now."""


class CompareReply(_Frozen):
    """What ``GET /api/compare`` answers: whether the open project can replace a baseline."""

    revision: int
    """The revision this comparison was read from."""

    verdict: bool
    """Whether the candidate can replace the baseline: no finding of severity error survived
    the session's own severity policy."""

    findings: tuple[Finding, ...]
    """Every finding ``compare`` itself reported, sorted by file: the interface and storage
    differences between the two deliveries. Always carries ``route: null`` - ``route_of``
    answers only for a component file, and every one of these is filed on the candidate's own
    project file, with an empty pointer."""

    baseline_findings: tuple[Finding, ...]
    """Every error the baseline's own analysis reported, forwarded here, sorted by file - still
    captioned ``"in the baseline: "`` for a reader's own sake, exactly as ``read_baseline``
    wrote it. Always carries ``route: null``: a finding is the baseline's because it is in
    *this* field, never because of where its file happens to resolve to, which a baseline that
    is also a file of the open project (the reader's own project, read a second time as its own
    baseline) would answer wrong. A page must not tell the two fields' findings apart by
    matching that prefix - this field is what that would be re-deriving, unreliably, from text
    a message is free to change."""

    renames: tuple[Renamed, ...]
    """Every object the two sides agree is one and the same but call differently now, sorted
    by the new name: what ``ddd compare --renames`` would write for this pair."""


# --- GET /api/undo and POST /api/undo -------------------------------------------------------


class UndoneChange(_Frozen):
    """One file an undo puts back, and the lines it would get."""

    file: str
    """Absolute, posix-separated path of the file."""

    gone: bool
    """``True`` for a file the edit created, which the undo takes away again."""

    hunks: tuple[Hunk, ...]
    """The lines the undo changes, numbered as the file stands now."""


class UndoPreview(_Frozen):
    """What ``GET /api/undo`` answers: what putting the last edit back would do.

    It carries no operations, and the page sends none back: an undo is bytes the server is
    holding, not an edit the page composes, which is the one place this differs from every
    other preview of the api.
    """

    revision: int
    """The revision this preview was read at."""

    at: int
    """The edit it would put back, which ``POST /api/undo`` takes back."""

    label: str
    """What the page called that edit."""

    changes: tuple[UndoneChange, ...]
    """One per file the edit wrote, in the order it wrote them."""


class UndoRequest(_Request):
    """What ``POST /api/undo`` takes: the edit the preview was made from."""

    at: int
    """Refused as ``stale`` when it is no longer the one to undo."""


class UndoReply(_Frozen):
    """What ``POST /api/undo`` answers: the revision the undo produced."""

    revision: int


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

    fingerprint: str | None
    """The fingerprint the file was read at; refused as ``stale`` if it has since changed.
    ``None`` creates the file, which must not exist yet, from one ``set`` of its whole document
    at the pointer ``""``."""

    operations: tuple[Operation, ...] = Field(min_length=1)
    """The operations to apply to the file, in order."""


class Changes(_Request):
    """What ``POST /api/edit`` takes: every file it changes, in one all-or-nothing edit."""

    changes: tuple[Change, ...] = Field(min_length=1)
    """Every file this edit changes; made all at once, or not at all."""

    label: str = Field(min_length=1, max_length=120)
    """What this edit is, as a noun phrase: "the unit of ValueA", "the rename of 'rpm' to
    'RPM'". The page writes it, because only the screen that applies knows what it did, and an
    undo of this edit offers to put back what it names."""


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
    (UndoPreview, "serialization"),
    (UndoRequest, "validation"),
    (UndoReply, "serialization"),
    (VariableReply, "serialization"),
    (UnitsReply, "serialization"),
    (SettleReply, "serialization"),
    (FixReply, "serialization"),
    (UnitReply, "serialization"),
    (TypesReply, "serialization"),
    (TypeReply, "serialization"),
    (SharedReply, "serialization"),
    (ConstantReply, "serialization"),
    (SectionReply, "serialization"),
    (RasterReply, "serialization"),
    (DeclarableReply, "serialization"),
    (PlanReply, "serialization"),
    (ValuesReply, "serialization"),
    (CompareReply, "serialization"),
)
"""Every request and response of spec section 6.5, with the schema pydantic builds for each:
``"validation"`` for a request, read for the shape a caller must send; ``"serialization"`` for
a response, read for the shape ``model_dump(mode="json")`` produces - the two differ wherever a
field has a default.

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
