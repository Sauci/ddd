"""What changing one entry of one of the Shared files tab's vocabularies takes, planned and never
written.

Transport-neutral, like :mod:`ddd.project_shared` beside it: nothing here knows about http or the
session. A rename is the editor's rename - :func:`ddd.lsp.navigation.rename_sites` says which
strings it has to rewrite, :func:`~ddd.lsp.navigation.rename_problem` says why a name may not be
used - for the reason :mod:`ddd.type_plans` borrows them both: two clients that renamed a constant
differently would disagree about what a project means, and the one reaching fewer files would
leave it broken across several at once.

Every value travels as the json text its author wrote. :data:`ddd.models.constants.ConstantValue`
is strict on both arms and refuses a whole number in the fractional one, so ``2`` and ``2.0`` are
two different constants; a plan that parsed a value and wrote it back would retype one nobody
asked it to.

The four verbs below - and :func:`project_of`, which reads the context :func:`add_entry` needs -
take a :class:`~ddd.project_shared.Vocabulary` first, the way part 13's read side already takes
one, and everywhere a constant's own reach differed from a section's or a raster's - the settable
keys, the required ones, the judge of a value, the file created, the noun a removal names, the
sentence a name is refused with - now comes off the descriptor instead of being written into the
verb. The constants-named bindings that carried the api across that change -
``set_constant``, ``rename_constant``, ``add_constant``, ``remove_constant`` and
``shared_project`` - are gone: the api asks for the verb and the vocabulary it means, so a
project's sections are planned by the same five functions and neither client can get a different
answer for the two.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

from ddd.editing import Operation
from ddd.loading import included_files, resolve_path
from ddd.lsp.navigation import Index, Site, rename_sites
from ddd.lsp.ranges import Document, read
from ddd.lsp.units import PlannedEdit, appended_at, created_beside
from ddd.pointers import parent_pointer
from ddd.project_shared import CONSTANTS, Vocabulary

_VOWELS: Final = frozenset("aeio")
"""The letters :func:`_article` writes ``an`` in front of. ``u`` is not one of them, for the reason
that function gives."""

CONSTANTS_FILE: Final = CONSTANTS.filename
"""The constants file ``add_entry`` writes for a project that has none, beside its description.

Named as :data:`ddd.lsp.units.ADOPTED` names the units file adoption writes, and for the same
reason: whoever opens the checkout afterwards should be able to tell what the file is from its
name. :data:`~ddd.project_shared.CONSTANTS`'s own
:attr:`~ddd.project_shared.Vocabulary.filename`, kept under its old name for the tests that still
import it by it.
"""


@dataclass(frozen=True, slots=True)
class SharedProject:
    """What a plan has to know of the project besides its index: where its vocabulary's own files
    are kept, which of its files could not be told apart from a place they are kept, and which of
    its files did not load."""

    project: Path
    """The project description, resolved."""

    files: tuple[Path, ...]
    """Its vocabulary's own files, in the order its ``project.includes`` lists them, each listed
    once: the first is where a new entry goes, so that it lands in the file a run of ``ddd check``
    reads first."""

    untellable: tuple[Path, ...]
    """The files it includes that are there and do not parse, in ``includes`` order, each listed
    once: what each one is cannot be told, so each of them might be one of the vocabulary's own.

    Kept apart from ``files`` because nothing may be appended to a file nobody could read, and
    kept at all because ``files`` being empty otherwise reads as "this project has none of this
    vocabulary's files" - and :func:`add_entry` would answer that by writing a second one beside
    the description, unasked, while the first sat there mid-save.

    A file the project includes and does not have is not one of them: it declares nothing, so it
    hides no name a new file could collide with."""

    unread: tuple[Path, ...]
    """The project's files that did not load, resolved and sorted."""


@dataclass(frozen=True, slots=True)
class SharedPlan:
    """Everything one change of an entry takes: one edit per file, sorted by path."""

    edits: tuple[PlannedEdit, ...]


class SharedRefusalError(Exception):
    """A change of an entry that cannot be planned, and the code both clients refuse it with."""

    code: Literal["unreadable", "invalid", "not-found"]
    """``unreadable``: a file the change has to see did not load. ``invalid``: the change cannot
    be made - a key a constant has not, a name that may not be used, a constant a shape still
    names. ``not-found``: no file of the project declares a constant of that name."""

    message: str
    """The sentence the refusal is shown with, naming the file it concerns."""

    def __init__(self, code: Literal["unreadable", "invalid", "not-found"], message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def project_of(
    vocabulary: Vocabulary, project: Path, unread: Sequence[Path], cache: dict[Path, Document]
) -> SharedProject:
    """The project ``vocabulary``'s plans are made in: its description, its own files, the files
    it includes whose kind cannot be told, and the files of it that did not load.

    Its files come out of the description's own ``includes``, each entry expanded by the loader's
    rule, so that the first of them is the first a run of ``ddd check`` reads. One of them is a
    document with ``vocabulary.containers[0]`` at its top, which is how the loader tells one; a
    file that does not parse is none, since what it is cannot be told - and a new entry must not
    be appended to a file nobody could read.

    That answer is not the whole of it, which is what this function used to leave unsaid: a file
    whose kind cannot be told might be one of the vocabulary's, and counting it as none left
    ``files`` empty - which :func:`add_entry` read as "this project has none of this vocabulary's
    files" and answered by creating a second one. So such a file is named in ``untellable``
    instead of being passed over in silence, and ``add`` refuses rather than creates while one is
    there.
    """
    path = resolve_path(project)
    found: list[Path] = []
    untellable: list[Path] = []
    listed = read(path, cache).value_at("project.includes")
    for entry in listed if isinstance(listed, list) else ():
        for file in included_files(path, entry):
            document = read(file, cache).data
            if (
                file not in found
                and isinstance(document, dict)
                and vocabulary.containers[0] in document
            ):
                found.append(file)
            elif document is None and file not in untellable and file.exists():
                untellable.append(file)
    return SharedProject(
        path,
        tuple(found),
        tuple(untellable),
        tuple(sorted({resolve_path(file) for file in unread}, key=Path.as_posix)),
    )


def set_entry(
    vocabulary: Vocabulary,
    built: Index,
    name: str,
    key: str,
    raw: str | None,
    cache: dict[Path, Document],
) -> SharedPlan:
    """``key`` of that entry of ``vocabulary`` set to the json text ``raw``, or taken away where
    ``raw`` is ``None``.

    ``raw`` is trusted to be json: the api parses it with :func:`ddd.editing.parse_raw` and answers
    ``bad-request`` for text that is not, the way ``GET /api/settle`` already does - a malformed
    request is not a refusal about the project.

    A key of :attr:`~ddd.project_shared.Vocabulary.required` may not be taken away, and one the
    format would refuse is refused here: written, the file would stop loading and every tab would
    empty because of one keystroke in this one. Any other key given is checked the same way,
    against the same consequence: unguarded, ``?action=set&key=description&raw=123`` planned
    ``"description": 123`` - a number where the model wants a string - and the file it landed in
    stopped loading, emptying every tab in the page over one keystroke, exactly the failure the
    required check exists to prevent. A key already left out answers no edit at all rather than a
    removal, as :func:`ddd.type_plans.set_key` also does for a type: there is nothing to remove,
    and a reader who has only selected the row - not typed anything - must not be refused before
    they have.

    A value the format would take may still be one the project has already given away, which is
    what :func:`_untaken` asks :attr:`~ddd.project_shared.Vocabulary.taken` about. The two verbs
    that write a name have always asked it for that one; this asks it for every key a descriptor
    names, which is what a raster's ``event`` needs - it is settable *and* the project's alone,
    where a name is only ever the second. Asked after :func:`_judged`, so that text the model
    would refuse meets the model's refusal and not a second one about who holds it.

    The two arms this function had - the required key's and the ordinary one's - ended in the same
    two lines apiece, a ``_judged`` and a ``return _plan(...)``, and the consult would have had to
    be written into both. Turned inside out instead, on ``raw is None`` rather than on
    ``required``, so that judging and asking happen in exactly one place. The refusal of a required
    key taken away still comes before any judging, since nothing is judged on that arm at all, and
    its sentence is untouched.
    """
    entry = _entry(vocabulary, built, name)
    _settable(vocabulary, key, entry.path)
    if raw is None:
        if key in vocabulary.required:
            raise SharedRefusalError(
                "invalid",
                f"{_article(vocabulary.kind)} {vocabulary.kind} states {_article(key)} {key}, so "
                f"'{name}' cannot be left without one in {entry.path.name}",
            )
        if read(entry.path, cache).value_at(f"{entry.pointer}.{key}") is None:
            return SharedPlan(())
        return _plan({entry.path: [Operation("remove", f"{entry.pointer}.{key}")]})
    _judged(vocabulary, key, raw, name, entry.path)
    _untaken(vocabulary, built, name, key, raw, cache)
    return _plan({entry.path: [Operation("set", f"{entry.pointer}.{key}", raw)]})


def rename_entry(
    vocabulary: Vocabulary, built: Index, name: str, to: str, cache: dict[Path, Document]
) -> SharedPlan:
    """What renaming that entry of ``vocabulary`` takes: its own ``name`` and every shape spelling
    it.

    The editor's rename, asked for rather than reimplemented. :func:`ddd.lsp.navigation.
    rename_sites` knows the three places a shape is written and
    :attr:`~ddd.project_shared.Vocabulary.taken` knows why a name may not be used - a
    constant's asks :func:`~ddd.lsp.navigation.rename_problem`, with ``Index.occupied`` already
    holding *the name of the declared constant* - so the tab and the editor cannot disagree about
    what a rename reaches or which names it refuses.

    Refused before a file is touched: a rename writes into every file naming the entry, and a
    name that turned out to be unusable would leave the project broken across all of them at once.
    """
    _entry(vocabulary, built, name)
    problem = vocabulary.taken[vocabulary.name_key](built, name, to, cache)
    if problem is not None:
        raise SharedRefusalError("invalid", problem)
    by_file: dict[Path, list[Operation]] = {}
    for site in rename_sites(built, vocabulary.kind, name):
        by_file.setdefault(site.path, []).append(Operation("set", site.pointer, _raw(to)))
    return _plan(by_file)


def add_entry(
    vocabulary: Vocabulary,
    built: Index,
    project: SharedProject,
    name: str,
    raws: Mapping[str, str],
    cache: dict[Path, Document],
) -> SharedPlan:
    """``name`` declared with ``raws`` - one json text per key of ``vocabulary`` - appended to the
    first of the vocabulary's own files the project includes, or written into a new one beside the
    project description where it includes none.

    One verb, where the units vocabulary has two. :func:`ddd.lsp.units.adopt_units` harvests the
    units already in use into a units file - a new one, or one declaring nothing; the entries in
    use are exactly the ones an ``unknown-*`` finding already complains about, and a value cannot
    be harvested - nothing in the project says what the length of an array is. So this creates
    the file when there is none, and there is nothing to adopt.

    Each raw text is embedded as it was given rather than parsed and reprinted: ``2.0`` declares a
    fractional constant and ``2`` a whole one, and a reader asking for one would otherwise get the
    other.

    Creating is refused while the project includes a file whose kind cannot be told, because
    "this project has none of this vocabulary's files" is then not something anyone knows:
    measured through the endpoint, a project including a ``sizes.ddd.json`` truncated mid-save
    answered a two-edit create plan for a second ``constants.ddd.json`` and an ``includes`` entry
    naming it, unasked. The harm is the one the unreadable guard below exists to prevent - what
    that file declares is unknown, so the new entry can collide with a name in it the moment it is
    saved - and :func:`ddd.lsp.units.add_unit` refuses the same situation, having no creating arm
    to fall into. Only the creating arm is refused: where a file of the vocabulary did load, this
    knows both where the entry goes and what that file already declares.

    Every raw the appending path writes is asked of :func:`_untaken` as well as of
    :func:`_judged`, in the loop that already settles and judges them: a value the project has
    already given away is refused on declaring for the same reason :func:`set_entry` refuses it on
    edit. Asked in one verb and not the other, the interface would refuse a raster's event on edit
    and write the collision on declaring - the reader reaching the same wrong project by the
    longer route. ``None`` is passed for the entry, there being none yet for one to be exempt
    from.

    The creating path - :func:`_created` - does not ask, and today cannot need to. It is reached
    only where ``project.files`` is empty, which is to say where the project includes no file of
    this vocabulary; an entry a judge could answer about would then have to have come from some
    other home. Only :data:`~ddd.project_shared.CONSTANTS` has one (``component.constants``), and
    a constant's :attr:`~ddd.project_shared.Vocabulary.taken` holds its name alone, which
    ``add_entry`` asks above this loop and not in it. So on that path every judge that could be
    asked would answer ``None``: a fallback agreeing with its guard, which no test can tell from
    its absence and which would cost :func:`_created` an :class:`~ddd.lsp.navigation.Index`
    parameter it has no other use for. Written down rather than written, and the exception stated
    rather than the claim overstated.

    **What reopens it:** a vocabulary with both a second home and a key of its own in ``taken``.
    That one reaches :func:`_created` with entries already in the index, and would write on
    declaring the collision it is refused on editing - the failure this paragraph's first half
    exists to prevent, arriving by the third route. Wire the call then; it is one line and the
    parameter.
    """
    problem = vocabulary.taken[vocabulary.name_key](built, None, name, cache)
    if problem is not None:
        raise SharedRefusalError("invalid", problem)
    if not project.files:
        if project.untellable:
            raise SharedRefusalError(
                "unreadable",
                f"{_names(project.untellable)} did not parse, so whether this project already "
                f"keeps its {vocabulary.kind}s there is unknown and '{name}' cannot be declared "
                "into a new file",
            )
        return _created(vocabulary, project, name, raws, cache)
    file = project.files[0]
    if file in project.unread:
        raise SharedRefusalError(
            "unreadable",
            f"{file.name} did not load, so what it declares is unknown and '{name}' cannot be "
            "added to it",
        )
    for key, raw in raws.items():
        _settable(vocabulary, key, file)
        _judged(vocabulary, key, raw, name, file)
        _untaken(vocabulary, built, None, key, raw, cache)
    listed = read(file, cache).value_at(vocabulary.containers[0])
    position = appended_at(listed)
    operation = Operation(
        "insert", f"{vocabulary.containers[0]}[{position}]", _entry_text(vocabulary, name, raws)
    )
    return _plan({file: [operation]})


def remove_entry(
    vocabulary: Vocabulary, built: Index, name: str, cache: dict[Path, Document]
) -> SharedPlan:
    """That entry of ``vocabulary`` taken out of the list holding it - or, where that list is
    nested and the entry is its last, the key holding the list.

    Refused while any shape names it. Removed, each of those shapes would name nothing, which is
    an ``unknown-*`` finding apiece in files the reader was not looking at - a worse answer than
    saying no. What is in use is asked of the index, never of a file's text: reading text to answer
    a question about meaning is the mistake part 11 filed against ``variable_keys._storage_of``.

    Otherwise the entry goes, and what that leaves depends on which list held it - told from the
    descriptor alone, the list's pointer against the first of
    :attr:`~ddd.project_shared.Vocabulary.containers`, so that nothing here learns which
    vocabulary it is serving:

    * In the vocabulary file's own list, the last entry goes like any other and leaves the file
      declaring nothing, which loads and is reported as ``empty-vocabulary``. This used to be
      refused, on the rule that declaring nothing is done by not writing the file; the rule is
      reversed on purpose, because ``ddd gui`` cannot delete a file, so under it no reader could
      take a project from one entry to none.
    * In a nested list - a component's own ``constants``, the only one today - the list is still
      ``min_length=1``, since leaving the key out is how a component publishes none. ``[]``
      written there would stop the component loading, and every variable it declares would go
      out of the project with the constant, so the last entry takes the key with it instead.

    A Remove of the last constant a component declares is therefore a different edit from every
    other Remove - the key holding the entry rather than the entry - which the version before this
    one refused to make, reading the design's "the entry, and nothing else" as forbidding it. Each
    edit leaves the list's home in the format's own spelling of none, which is what taking the
    entry out means.

    A nested list is read from the file rather than counted off the index, because the index holds
    the project's entries by name across every file, not the entries of one list; ``cache`` is the
    one this plan's other reads already share.
    """
    entry = _entry(vocabulary, built, name)
    used = vocabulary.used(built).get(name, ())
    # Asked before what taking the entry out leaves, and not the other way round: on the last
    # entry of a nested list that answer is a plan taking the whole key away, which would leave
    # every shape naming the entry naming nothing - and this refusal names a place the reader can
    # go to and undo.
    if used:
        raise SharedRefusalError(
            "invalid",
            f"'{name}' is named by {_plural(len(used), 'shape')}, the first in "
            f"{used[0].path.name}; nothing may name it before it goes",
        )
    holding = parent_pointer(entry.pointer)
    if holding != vocabulary.containers[0]:
        listed = read(entry.path, cache).value_at(holding)
        if isinstance(listed, list) and len(listed) <= 1:
            return _plan({entry.path: [Operation("remove", holding)]})
    return _plan({entry.path: [Operation("remove", entry.pointer)]})


def _entry(vocabulary: Vocabulary, built: Index, name: str) -> Site:
    """Where that entry of ``vocabulary`` is declared, or a refusal saying nothing declares it."""
    entry = vocabulary.entries(built).get(name)
    if entry is None:
        raise SharedRefusalError(
            "not-found",
            f"no file of this project declares {_article(vocabulary.kind)} {vocabulary.kind} "
            f"called '{name}'",
        )
    return entry


def _settable(vocabulary: Vocabulary, key: str, file: Path) -> None:
    """Refuse a key ``vocabulary`` does not let the interface touch, naming the file it would
    have been written to or read at, and every key it does allow instead.

    ``set_entry`` asks this of the one key it is given; ``add_entry`` asks it of every key
    ``raws`` carries, before ``_judged`` ever sees it - a raw key outside ``vocabulary.keys`` is
    not a value the format would refuse, it is a key the interface does not offer at all, and the
    two must not be confused in what a reader is told.

    The two words this sentence takes from the descriptor go through :func:`_article` and
    :func:`_listed`: the article for the same reason the other three refusals need it, and the list
    because ``' and '.join`` had only ever met the two keys of one vocabulary and read "access and
    alignment and description" for the first that has three.
    """
    if key not in vocabulary.keys:
        raise SharedRefusalError(
            "invalid",
            f"{_article(vocabulary.kind)} {vocabulary.kind} has no '{key}' to set in "
            f"{file.name}: it states {_listed(sorted(vocabulary.keys))}",
        )


def _judged(vocabulary: Vocabulary, key: str, raw: str, name: str, file: Path) -> None:
    """Refuse json text ``key``'s model would not take, naming the file it would have been
    written to.

    One sentence shape, shared by every key of every vocabulary and differing only in the tail
    :attr:`~ddd.project_shared.Judgement.tail` supplies - a constant's ``value`` and its
    ``description`` shared this shape and differed only there before this was written once for
    both. Its two indefinite articles come from :func:`_article`, because a key is a word a
    descriptor supplies and two of a section's three begin with a vowel."""
    judgement = vocabulary.judge[key]
    try:
        judgement.adapter.validate_python(json.loads(raw))
    except (ValueError, TypeError) as refused:
        raise SharedRefusalError(
            "invalid",
            f"{raw} is not {_article(key)} {key} {_article(vocabulary.kind)} {vocabulary.kind} "
            f"may state, so '{name}' cannot take it in {file.name}: {judgement.tail}",
        ) from refused


def _untaken(
    vocabulary: Vocabulary,
    built: Index,
    entry: str | None,
    key: str,
    raw: str,
    cache: dict[Path, Document],
) -> None:
    """Refuse a value another entry of ``vocabulary`` has already got, where ``key`` is one whose
    value is the project's alone.

    The one place either verb that writes a value asks
    :attr:`~ddd.project_shared.Vocabulary.taken`, so that a collision is refused in the same words
    however a reader arrives at it. What a key's own :class:`~ddd.project_shared.Judgement` can
    say and what this can say are different questions asked of different things:
    :func:`_judged` takes no :class:`Index` and settles what the format permits at all, and this
    one settles what is still free in *this* project.

    A key with no judge is the ordinary case and returns at once - a constant's ``value`` and a
    section's ``alignment`` are nobody's to hold, and ``taken`` names only the keys that are.
    Written as two early returns rather than one nested ``if`` so that each is its own branch:
    the arm neither of the first two vocabularies can reach - a settable key that *is* in
    ``taken`` - is then one the gate can tell apart from the arm every constant and section takes.

    ``entry`` is the entry being changed, which a judge may exempt from itself, and ``None`` from
    an ``add``, which has no entry yet. All three name judges read neither it nor ``cache``; a
    raster's event judge reads both, for the reason
    :attr:`~ddd.project_shared.Vocabulary.taken` gives.

    ``"invalid"`` is the code, which is what the ``taken`` refusals in :func:`rename_entry` and
    :func:`add_entry` already raise: the change cannot be made, and no file failed to load.
    """
    judge = vocabulary.taken.get(key)
    if judge is None:
        return
    problem = judge(built, entry, raw, cache)
    if problem is None:
        return
    raise SharedRefusalError("invalid", problem)


def _plan(operations: Mapping[Path, Sequence[Operation]]) -> SharedPlan:
    """One edit per file, sorted by path, as :class:`SharedPlan` promises and the interface applies
    them."""
    return SharedPlan(
        tuple(
            PlannedEdit(path, tuple(operations[path]))
            for path in sorted(operations, key=Path.as_posix)
        )
    )


def _names(files: Sequence[Path]) -> str:
    """The files a refusal is about, by name, as :func:`ddd.lsp.units._names` spells them: a
    refusal names the file it concerns, and a project can include more than one nobody could
    read."""
    return ", ".join(file.name for file in files)


def _plural(count: int, noun: str) -> str:
    """ "1 shape", "2 shapes" - the wording `remove_entry` names a blocking use's count with."""
    return f"{count} {noun}{'' if count == 1 else 's'}"


def _article(word: str) -> str:
    """``a`` or ``an``, for a word a descriptor supplies rather than this module: a key of
    :attr:`~ddd.project_shared.Vocabulary.keys`, or a vocabulary's own
    :attr:`~ddd.project_shared.Vocabulary.kind`.

    Four refusals below write an indefinite article in front of such a word, and each had ``a``
    written into it. That was grammatical by luck rather than by rule: every word the one
    vocabulary of the day could put there - ``constant``, ``value``, ``description`` - begins with
    a consonant, and the second vocabulary brought two that do not, so a reader setting an
    alignment was told ``3 is not a alignment a section may state``. Nothing about the word's
    vocabulary is consulted here, and nothing needs to be: this is the English rule the sentences
    always meant, written once instead of assumed four times.

    The four: :func:`_judged`, twice in one sentence; :func:`set_entry`'s refusal of a required key
    taken away, also twice; :func:`_entry`'s not-found; and :func:`_settable`'s. Only the first two
    say anything different today, because every ``kind`` begins with a consonant and only a key
    can begin with a vowel - but the point of a rule written once is that the next vocabulary's
    words are not a fifth thing to remember.

    ``u`` is deliberately not a vowel here. The rule English follows is about sound, not spelling,
    and every word a descriptor could put in these sentences that starts with one is said with a
    consonant - ``a unit``, ``a uint16`` - so counting it in would fix two words and break the
    next. Written as an early return rather than a conditional expression, which coverage.py
    counts no branch in: the arm the keys of one vocabulary never reach would pass the gate unseen,
    which is exactly how the missing ``an`` survived this long.
    """
    if word[:1].lower() in _VOWELS:
        return "an"
    return "a"


def _listed(words: Sequence[str]) -> str:
    """The words of a set as a sentence names them: ``value``, ``description and value``,
    ``access, alignment and description``.

    :func:`_settable` tells a reader every key the vocabulary does offer, and wrote
    ``' and '.join`` for it - which reads correctly for the one and two word cases the constants
    vocabulary could produce and says "access and alignment and description" for the first
    vocabulary with three keys. The same oversight as the article beside it, and found the same
    way: a generic sentence met a second vocabulary.

    Not a conditional expression, for the reason :func:`_article` is not one either: the three word
    arm would be a path no test of a two key vocabulary reaches, and coverage.py counts no branch
    in a conditional expression to say so.
    """
    if len(words) < 3:
        return " and ".join(words)
    return f"{', '.join(words[:-1])} and {words[-1]}"


def _raw(value: Any) -> str:
    """A value as the json text an operation carries, every character as written: a description
    holding a degree sign arrives in the file as one, where json's default would write an
    escape."""
    return json.dumps(value, ensure_ascii=False)


def _created(
    vocabulary: Vocabulary,
    project: SharedProject,
    name: str,
    raws: Mapping[str, str],
    cache: dict[Path, Document],
) -> SharedPlan:
    """The file of ``vocabulary`` a project without one gets, and the ``includes`` entry naming
    it.

    Follows :func:`ddd.lsp.units.adopt_units`, the only other plan in the repo that creates a
    file: laid out with :func:`ddd.editing.lay_out` so the new file reads like one a person
    wrote, and carried in the same plan as the ``includes`` entry so that a project can never
    list a file that was not written - which is also the only shape of creation
    :func:`ddd.gui.session._confined` allows.
    """
    created = project.project.parent / vocabulary.filename
    if created.exists():
        raise SharedRefusalError(
            "invalid",
            f"declaring '{name}' writes {vocabulary.filename} beside {project.project.name}, "
            "and a file of that name is there already",
        )
    for key, raw in raws.items():
        _settable(vocabulary, key, created)
        _judged(vocabulary, key, raw, name, created)
    text = f'{{"{vocabulary.containers[0]}": [{_entry_text(vocabulary, name, raws)}]}}'
    edits = created_beside(project.project, vocabulary.filename, text, cache)
    return SharedPlan(tuple(sorted(edits, key=lambda edit: edit.path.as_posix())))


def _entry_text(vocabulary: Vocabulary, name: str, raws: Mapping[str, str]) -> str:
    """One entry of ``vocabulary`` as json text, its name and every value in ``raws`` embedded
    exactly as given, in the order :attr:`~ddd.project_shared.Vocabulary.keys` lists them.

    The ``if key in raws`` filter is for a key ``raws`` leaves out, never for one it should not
    have had: :func:`add_entry` has already refused any key outside ``vocabulary.keys`` through
    :func:`_settable`, so by the time this runs, a key of ``vocabulary.keys`` missing from
    ``raws`` is one the caller simply did not give a value - ``GET /api/raster-plan`` gives an
    ``add`` no ``cycle``, and the entry it declares states none.

    A raster is what that filter is for, and until it existed this sentence named ``description``
    instead, which was wrong: :func:`ddd.gui.api._declared` supplies an empty ``description``
    itself for every vocabulary, so it is never the key that is missing, and the section an
    ``add`` writes does carry one. ``cycle`` is the key that is missing - ``str | None`` in the
    model, with an event that is not cyclic a real kind of raster rather than an omission - so a
    declared raster states no ``cycle`` at all, which ``test_declaring_one_takes_a_json_text_per
    _key_the_model_gives_no_default`` asserts in the written bytes.

    Built as text rather than dumped from a dict, for the reason :func:`_raw` keeps a value's own
    spelling: a dict would carry a number through python's own types, and ``1e3`` would come back
    ``1000.0``. Every value here has passed :func:`_judged`, so what is built is json.
    """
    fields = [f"{_raw(vocabulary.name_key)}: {_raw(name)}"]
    fields.extend(f"{_raw(key)}: {raws[key]}" for key in vocabulary.keys if key in raws)
    return f"{{{', '.join(fields)}}}"
