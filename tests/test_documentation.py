"""Checks that the documentation still describes the tool that exists.

Prose rots quietly. These tests pin the few facts that are cheap to verify mechanically -
the names of the checks, the commands, the object kinds - so a rename cannot leave the
README and the SPEC describing a previous version of DDD.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pytest

from ddd.cli import _build_parser
from ddd.diagnostics import CHECKS
from ddd.models import Datatype, ObjectKind

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")
SPEC = (ROOT / "SPEC.md").read_text(encoding="utf-8")


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
            "name",
            "complete",
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
