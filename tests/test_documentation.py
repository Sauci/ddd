"""Checks that the documentation still describes the tool that exists.

Prose rots quietly. These tests pin the few facts that are cheap to verify mechanically -
the names of the checks, the commands, the object kinds - so a rename cannot leave the
README and the SPEC describing a previous version of DDD.
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import io
import json
import re
import tomllib
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

import jsonschema
import pytest
from pydantic import BaseModel

from ddd import __version__
from ddd.backends.c.model import CodeModel, MemberView, ObjectView
from ddd.cli import _SCHEMA_MODELS, _build_parser
from ddd.diagnostics import CHECKS
from ddd.loading import FILE_KINDS
from ddd.models import Component, DataObject, Datatype, ObjectKind, ScalarType

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")
SPEC = (ROOT / "SPEC.md").read_text(encoding="utf-8")
EDITOR_INTEGRATION = (ROOT / "docs" / "editor_integration.rst").read_text(encoding="utf-8")
DOCS_WORKFLOW = (ROOT / ".github" / "workflows" / "docs.yml").read_text(encoding="utf-8")
PUBLISH_WORKFLOW = (ROOT / ".github" / "workflows" / "publish.yml").read_text(encoding="utf-8")
DOCS_URL = "https://sauci.github.io/ddd/"
CONSISTENCY_CHECKS = (ROOT / "docs" / "consistency_checks.rst").read_text(encoding="utf-8")
COMPARING_DELIVERIES = (ROOT / "docs" / "comparing_deliveries.rst").read_text(encoding="utf-8")
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
    """The number word of every "N checks ... need every component" claim of one document."""
    return re.findall(r"(\w+) checks(?: that)? need every component of a project", flattened(text))


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
            "const-inputs",
            "dry-run",
            "address-map",
            "byte-order",
            "output-dir",
            "cmake-dir",
            "no-cov",
            "cov-fail-under",
            "no-propagate-headers",
            "ddd-compile",
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

    @pytest.mark.parametrize("page", sorted(PAGES))
    def test_the_fixed_checks_are_counted_as_the_registry_counts_them(self, page: str) -> None:
        """ "The five checks whose severity cannot be changed" went stale when two more joined.

        Any page may count them, so every page is read; a sentence that counts them in words
        has to count what the registry marks as not overridable.
        """
        expected = sum(1 for info in CHECKS.values() if not info.overridable)
        text = flattened(PAGES[page])
        counted = re.findall(
            r"\b(\w+) (?:load time )?(?:checks )?whose severity\b", text, flags=re.I
        ) + re.findall(r"\b(\w+) checks cannot be relaxed", text, flags=re.I)
        for word in counted:
            if word.lower() in NUMBER_WORDS:
                assert NUMBER_WORDS[word.lower()] == expected, (
                    f"{page} counts {word} checks with a fixed severity; "
                    f"the registry has {expected}"
                )


class TestTheFileKinds:
    """A seventh file kind was added, and the lists of them written in prose stayed at six."""

    @pytest.mark.parametrize("page", sorted(PAGES))
    def test_the_description_kinds_are_counted_as_the_loader_counts_them(self, page: str) -> None:
        for word in re.findall(r"\b(\w+) description kinds", flattened(PAGES[page]), flags=re.I):
            if word.lower() in NUMBER_WORDS:
                assert NUMBER_WORDS[word.lower()] == len(FILE_KINDS), (
                    f"{page} counts {word} description kinds; the loader knows {len(FILE_KINDS)}"
                )

    def test_the_file_kind_row_names_every_kind(self) -> None:
        """The row explaining the check enumerates what a top level key may be, in full."""
        row = re.search(r"\* - ``file-kind``\n(.*?)\n   \* - ``", CONSISTENCY_CHECKS, flags=re.S)
        assert row is not None
        for kind in FILE_KINDS:
            assert f"``{kind}``" in row.group(1), f"the file-kind row does not name {kind}"


class TestCommands:
    @pytest.mark.parametrize("command", commands())
    def test_every_command_is_documented_in_the_readme(self, command: str) -> None:
        assert f"ddd {command}" in README or f"`{command}`" in README

    def test_the_command_list_is_what_the_spec_promises(self) -> None:
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
            "checks",
            "cmake-dir",
            "templates-dir",
            "sources",
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
        assert set(re.findall(r"``([a-z]+)``", listed.group(1))) == set(_SCHEMA_MODELS)

    def test_the_readme_lists_the_same_schema_kinds(self) -> None:
        listed = re.search(r"\| `ddd schema ([a-z|\\]+)`", README)
        assert listed is not None
        assert set(listed.group(1).replace("\\", "").split("|")) == {*_SCHEMA_MODELS, "all"}

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
        for target in re.findall(r"\]\((?!https?:)([^)#]+)", README):
            assert (ROOT / target).exists(), f"README links to a missing path: {target}"

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

    def test_the_runtime_requirements_are_what_the_package_imports(self) -> None:
        """The two runtime dependencies are a deliberate claim of the README, so a third one
        appearing in requirements.txt has to be a decision rather than a drive-by addition."""
        listed = {
            re.split(r"[<>=!~ ]", line, maxsplit=1)[0].lower()
            for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        }
        assert listed == {"pydantic", "jinja2"}


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


def published_kinds() -> list[str]:
    """The file formats ``ddd schema`` publishes, which is what these tests are about."""
    from ddd.cli import _SCHEMA_MODELS

    return sorted(_SCHEMA_MODELS)


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

    def test_the_file_roots_allow_the_editor_binding(self) -> None:
        """Every root, not a hand-kept list of them: a new file kind joins the guard by
        subclassing ``FileRoot``, instead of silently shipping without the ``$schema`` key."""
        from ddd.models.common import FileRoot

        roots = FileRoot.__subclasses__()
        assert len(roots) >= 6, f"expected every file root, found {roots}"
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

        ``kind`` is exempt only where it is a fixed tag with nothing behind it: the ones that
        select a data object are documented, and checked below.
        """
        undocumented = [
            f"{name}.{field}"
            for name, definition in objects_in(published(kind))
            for field, spec in definition.get("properties", {}).items()
            if "description" not in spec and field != "kind"
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
        "name", sorted({*view_attributes(ObjectView), *view_attributes(MemberView)})
    )
    def test_every_attribute_of_a_view_is_documented(self, name: str) -> None:
        assert f"``.{name}" in self.TEMPLATES


class TestTheBuildIntegrationPage:
    """The cmake module is what a build runs, so the page and the module are held together."""

    CMAKE_MODULE = (ROOT / "cmake" / "Ddd.cmake").read_text(encoding="utf-8")

    def test_the_component_target_holds_back_what_the_registry_says(self) -> None:
        """A hand-kept list of two checks silenced two of the ten; the flag derives them."""
        command = re.search(
            r"\$\{DDD_EXECUTABLE\} check \"\$\{description\}\"(.*?)\n", self.CMAKE_MODULE
        )
        assert command is not None, "the module no longer checks a component on its own"
        assert "--standalone" in command.group(1), command.group(1)
        assert "-W" not in command.group(1), "a check named by hand beside the derived flag"

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
        from ddd.cli import _SCHEMA_MODELS, SCHEMA_FILENAME, schema_text

        for kind in sorted(_SCHEMA_MODELS):
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


class TestPublishedDocumentation:
    """The documentation is a deliverable with an address, published by ci.

    The two properties pinned here are the ones that fail silently. Everything else about
    ``docs.yml`` announces itself: a build that cannot find its input, or an upload of a
    directory that was never written, is a red run.
    """

    def test_the_published_address_is_the_same_everywhere(self) -> None:
        """A customer reaches the documentation through the package metadata on the index.

        Nothing resolves that url at build time, so a wrong one is a 404 with the product's
        name on it, found by whoever was trying to read the manual.
        """
        metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        developer_documentation = (ROOT / "docs" / "developer_documentation.rst").read_text(
            encoding="utf-8"
        )
        assert metadata["project"]["urls"]["Documentation"] == DOCS_URL
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

    def test_only_master_and_a_release_are_ever_published(self) -> None:
        """The deploy job names the two things it publishes rather than only an event.

        A pull request from a fork proposes arbitrary content and runs on this workflow
        definition. Guarding the deployment by event alone would leave opening one enough to
        publish somebody else's revision as the product's documentation - and ``pull_request``
        is neither of the two conditions below, which is the whole point of spelling them out.
        """
        deploy = DOCS_WORKFLOW.split("\n  deploy:\n", 1)[1]
        condition = next(line for line in deploy.splitlines() if line.strip().startswith("if:"))
        assert "github.ref == 'refs/heads/master'" in condition, (
            f"the deployment is not guarded by the branch: {condition.strip()}"
        )
        assert "github.event_name == 'release'" in condition, (
            f"a release does not deploy its own documentation: {condition.strip()}"
        )

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
