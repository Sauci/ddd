"""Checks that the documentation still describes the tool that exists.

Prose rots quietly. These tests pin the few facts that are cheap to verify mechanically -
the names of the checks, the commands, the object kinds - so a rename cannot leave the
README and the SPEC describing a previous version of DDD.
"""

from __future__ import annotations

import argparse
import json
import re
import tomllib
from pathlib import Path

import jsonschema
import pytest

from ddd import __version__
from ddd.cli import _build_parser
from ddd.diagnostics import CHECKS
from ddd.models import Datatype, ObjectKind

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")
SPEC = (ROOT / "SPEC.md").read_text(encoding="utf-8")
DOCS_WORKFLOW = (ROOT / ".github" / "workflows" / "docs.yml").read_text(encoding="utf-8")
DOCS_URL = "https://sauci.github.io/ddd/"


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
            "no-a2l",
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
            "schema",
            "checks",
            "cmake-dir",
            "templates-dir",
            "name",
            "complete",
            "sources",
        }


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


class TestPackaging:
    """What a customer receives has to match what the sources say it is."""

    def test_the_version_is_the_same_in_both_places(self) -> None:
        """The banner of every generated file carries it, and the release tag is checked
        against it, so a drift between the package and the module is a released lie."""
        metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        assert metadata["project"]["version"] == __version__

    def test_the_declared_license_file_exists(self) -> None:
        metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        license_file = metadata["project"]["license"]["file"]
        assert (ROOT / license_file).is_file(), "the declared license file is not in the tree"

    def test_everything_the_readme_tells_the_user_to_install_is_shipped(self) -> None:
        """`ddd cmake-dir` and the completion setup are documented, so both have to travel
        in the wheel rather than existing only in a git checkout."""
        metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        wheel = metadata["tool"]["hatch"]["build"]["targets"]["wheel"]
        for source in ("cmake/Ddd.cmake", "completion/ddd.bash"):
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


class TestPublishedSchemas:
    """The schemas are the editor integration, so what they carry is a promise."""

    def test_the_file_roots_allow_the_editor_binding(self) -> None:
        from ddd.models import ComponentFile, NamingFile, ProjectFile

        for model in (ProjectFile, ComponentFile, NamingFile):
            schema = model.model_json_schema(by_alias=True)
            assert "$schema" in schema["properties"], f"{model.__name__} rejects $schema"

    def test_every_authored_field_carries_hover_documentation(self) -> None:
        """A field without a description is a blank tooltip in every editor.

        The discriminator ``kind`` is exempt: it is a fixed value per variant, so the value
        itself is the documentation.
        """
        from ddd.models import ComponentFile

        schema = ComponentFile.model_json_schema(by_alias=True)
        undocumented = [
            f"{name}.{field}"
            for name, definition in schema["$defs"].items()
            for field, spec in definition.get("properties", {}).items()
            if "description" not in spec and field != "kind"
        ]
        assert not undocumented, (
            f"fields with a blank editor tooltip: {undocumented}. Add an attribute "
            f"docstring; use_attribute_docstrings carries it into the schema."
        )


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
            kind = next(key for key in ("project", "component", "naming") if key in document)
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

    def test_only_master_is_ever_published(self) -> None:
        """The deploy job is conditional on the branch rather than only on the event.

        A pull request from a fork proposes arbitrary content and runs on this workflow
        definition. Guarding the deployment by event alone would leave opening one enough to
        publish somebody else's revision as the product's documentation.
        """
        assert "if: github.ref == 'refs/heads/master'" in DOCS_WORKFLOW
