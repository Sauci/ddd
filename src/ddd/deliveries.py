"""Reading a side of a comparison: a delivery as it was handed over.

``ddd compare`` and ``ddd check --baseline`` take a baseline and a candidate, each of which is
either a dictionary somebody archived or a project description that has to be analysed to become
one. ``ddd gui`` compares the open project against a baseline the reader names, and needs the
same reading of what a baseline is - so it lives here rather than in the command, where the page
would have had to copy it.

What makes the copy dangerous is not the reading but the policy around it: a baseline is analysed
in a bag of its own, without ``--strict`` however strict the run asking is, and only its errors
are carried over. :func:`read_baseline` says why at length. A second implementation would have
drifted from that the first time either side changed.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from ddd.diagnostics import (
    STANDALONE_POLICY,
    DiagnosticBag,
    Location,
    Severity,
    SeverityPolicy,
    where,
)

if TYPE_CHECKING:
    from ddd.ir import DataDictionary
    from ddd.plugins import Plugin

BASELINE_PREFIX: Final = "in the baseline: "
"""What marks an error carried over from the baseline's own analysis, so that it reads as the
predecessor's rather than as this run's. Named here rather than spelled twice: a caller putting
one of these into a sentence that has already said which delivery it is about
(:mod:`ddd.gui.compare`'s refusal banner) has to take it off again, and matching a prefix nobody
owns is how that sort of thing goes wrong."""


class Refusal(StrEnum):
    """Why a reader came back with nothing, as the reader itself knows it: which of the two
    readers the file reached, and how far it got.

    What a caller has to have in order to tell a person why the file they named is not a
    delivery. Re-derived instead - by classifying one diagnostic out of a bag the caller did not
    fill - a description whose ``includes`` names a file that is not there was called "neither a
    dictionary nor a description", which reads as *you named the wrong file* and is answered by
    replacing one whose only fault is the missing include.
    """

    NOT_JSON = "not-json"
    """The file holds no json object at all, or none this tool will read - a duplicate key, a
    ``NaN``, bytes that are not utf-8.

    A file whose bytes could not be read at all comes back as this too:
    :func:`~ddd.loading.read_json_document` answers ``None`` for both "without saying a word
    about why not", and it is the *reader* the caller is asking, not the filesystem. A caller
    that has to tell those two apart settles it before asking, by opening the file itself -
    which is what :mod:`ddd.gui.compare` does to answer *unreadable*.
    """

    DESCRIPTION = "description"
    """A project or component description that did not become a dictionary: a file it includes
    that is not there, a name that does not validate, a plugin that refused, an analysis that
    reported an error. It is the right kind of file, and it is broken."""

    DICTIONARY = "dictionary"
    """A dumped dictionary this DDD could not read: one from a newer DDD, or one whose fields do
    not match the contract. Also the right kind of file - :func:`holds_a_dictionary` says how
    that is known before anything is validated."""

    NEITHER = "neither"
    """Valid json and neither of the two: no ``project``, no ``component``, no ``format``. The
    one refusal that really does mean the reader named the wrong file."""


@dataclass(slots=True)
class Reading:
    """What one read of a delivery turned out to be, beside the findings it reported.

    Filled in as the read goes, the way ``bag`` is, and for the same reason: the reader is the
    only thing that knows, and a caller working it out afterwards is guessing. A caller with
    nothing to say about a refusal passes none and pays nothing.
    """

    refusal: Refusal | None = None
    """Why nothing came back, or ``None`` while nothing has been refused."""


@dataclass(frozen=True, slots=True)
class Resolved:
    """A dictionary and what a plugin's hook needs beside it.

    A description resolved on the spot keeps its plugins and can point a finding at a
    declaration; an archived dump has neither, so its plugins come from ``--plugin`` and a
    finding points at the file.
    """

    dictionary: DataDictionary
    plugins: tuple[Plugin, ...]
    locate: Callable[[str], Location | None]
    from_description: bool
    sources: tuple[Path, ...]
    """Every file this side was read out of, resolved: a project and its whole include tree,
    or the single file an archived dump was read from. What :func:`_refuse_a_source` holds an
    output path against."""


def read_dictionary(
    path: Path, bag: DiagnosticBag, reading: Reading | None = None
) -> Resolved | None:
    """A dumped dictionary, or a project/component description resolved into one.

    Accepting both is what makes the command usable in a pipeline: the baseline is normally
    an archived dump, while the candidate is the project sitting in the working tree.

    ``reading`` is where this says *why* it answers ``None``, for a caller that has to put that
    in words - which of the two readers met the file, and how far it got. A caller with nothing
    to say about a refusal leaves it out.
    """
    from ddd.analysis import analyze
    from ddd.loading import load_dictionary, load_workspace, read_json_document

    account = Reading() if reading is None else reading
    document = read_json_document(path)
    if holds_a_description(document):
        workspace = load_workspace(path, bag)
        if workspace is None or bag.has_errors:
            account.refusal = Refusal.DESCRIPTION
            return None
        return Resolved(
            analyze(workspace, bag),
            workspace.plugins,
            workspace.locate,
            True,
            workspace.sources(),
        )
    # Handed the document this already read rather than leaving the reader to read it again:
    # a dumped dictionary is the file a build archives whole, and the 45 MB one of a thousand
    # object project costs about a third of a second per pass, twice over in a comparison.
    dictionary = load_dictionary(path, bag, document)
    if dictionary is None:
        account.refusal = _unread(document)
        return None
    archived = where(path)
    return Resolved(dictionary, (), lambda _: archived, False, (archived.path,))


def _unread(document: dict[str, Any] | None) -> Refusal:
    """Which refusal a file the dump reader could not read is: the sniff again, now that the
    reader has had its say, and never a classification of what it happened to report."""
    if document is None:
        return Refusal.NOT_JSON
    if holds_a_dictionary(document):
        return Refusal.DICTIONARY
    return Refusal.NEITHER


def read_baseline(
    path: Path, bag: DiagnosticBag, standalone: bool = False, reading: Reading | None = None
) -> Resolved | None:
    """Resolve the baseline side of a comparison, in a bag of its own.

    A baseline given as a project description has to be analysed to become a dictionary, and
    that analysis produces findings about *that* delivery: files that are not part of the
    project under check, an output nobody read two releases ago. Reported here they would be
    attributed to this run, printed twice when both sides are the same tree, and would fail a
    clean project because of its predecessor. Its warnings are its own, however strict this
    run is, so the baseline is analysed without ``--strict``; only its errors are carried over,
    prefixed, so that a broken baseline is visible. A candidate given as a dump is still
    compared against whatever resolved, because a delivery that cannot be accepted still needs
    its differences listed; a candidate given as a description is not analysed once the shared
    bag holds an error, so a broken baseline stops that run at the errors.

    ``-W`` does not reach it either, for the same reason and against the same objection: the
    overrides used to be shared, so ``-W unused-output=error`` - a run asking to be told about
    *its own* unread outputs - promoted a warning about a predecessor into an error, carried
    it over as ``in the baseline:`` and refused a verdict about the delivery. What does reach
    it is ``standalone``, the floor a component read on its own sets: that is a statement
    about how the file was handed over, and the baseline was handed over the same way.
    """
    floor = STANDALONE_POLICY if standalone else ()
    own = DiagnosticBag(SeverityPolicy.from_strings(floor, strict=False, standalone=standalone))
    resolved = read_dictionary(path, own, reading)
    for diagnostic in own.sorted:
        if diagnostic.severity is Severity.ERROR:
            bag.add(
                diagnostic.check,
                f"{BASELINE_PREFIX}{diagnostic.message}",
                diagnostic.location,
                diagnostic.notes,
                # At the severity the baseline's own analysis gave it: "the run fails on
                # them" (4.1) is what makes a comparison against an untrustworthy dictionary
                # visible, and a `-W` of this run relaxing the check would leave the run
                # reporting no verdict and exiting 0.
                severity=diagnostic.severity,
            )
    return resolved


def holds_a_description(document: dict[str, Any] | None) -> bool:
    """True for a project or component file; a broken file is left to the reader to report.

    A file :func:`read_json_document` could not read at all answers ``False`` rather than
    raising, because this is only a sniff: whichever reader the file actually reaches is what
    has something to say about it, and it reads the file again to say it.
    """
    return document is not None and ("project" in document or "component" in document)


def holds_a_dictionary(document: dict[str, Any] | None) -> bool:
    """True for a file ``ddd dump`` wrote, by the one key every dump stamps.

    ``format`` is what a dictionary declares itself with, and the only field
    :func:`~ddd.loading.load_dictionary` reads before validating anything - so that a dictionary
    from a newer DDD is told it is one rather than judged against a contract it was never
    written to. A file carrying it is that reader's, however badly it reads; one carrying
    neither it nor a description's own key belongs to nobody, which is what a reader who has
    simply named the wrong file is told. Like :func:`holds_a_description`, only a sniff: it
    decides whose refusal a file's is, never whether it loads.
    """
    return document is not None and "format" in document
