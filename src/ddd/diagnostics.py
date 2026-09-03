"""Diagnostics, check registry and severity policy."""

from __future__ import annotations

import contextlib
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Final, Self


class Severity(StrEnum):
    """How a finding is reported."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    IGNORE = "ignore"

    @property
    def rank(self) -> int:
        return _SEVERITY_RANK[self]


_NOTE_INDENT: Final = "    note: "

_SEVERITY_RANK: Final[dict[Severity, int]] = {
    Severity.ERROR: 0,
    Severity.WARNING: 1,
    Severity.INFO: 2,
    Severity.IGNORE: 3,
}


@dataclass(frozen=True, slots=True)
class CheckInfo:
    """Static description of one consistency check."""

    identifier: str
    default_severity: Severity
    description: str
    overridable: bool = True

    needs_every_component: bool = False
    """Whether the check reaches the *wrong* answer when a component is missing.

    Most checks read one file and are right about it whatever else exists. A few conclude
    something from the absence of a declaration - an input nobody produces, an output nobody
    reads, a reference to an object no component declares - and those are wrong by
    construction about a project only some of which is present. Anything that reads one file
    on its own, as the language server does when no build claims it, has to leave them out
    rather than report a finding whose only cause is what it was not shown.
    """


def _check(
    identifier: str,
    severity: Severity,
    description: str,
    *,
    overridable: bool = True,
    needs_every_component: bool = False,
) -> CheckInfo:
    return CheckInfo(identifier, severity, description, overridable, needs_every_component)


CHECKS: Final[dict[str, CheckInfo]] = {
    check.identifier: check
    for check in (
        _check("file-not-found", Severity.ERROR, "a referenced file does not exist",
               overridable=False),
        _check("json-syntax", Severity.ERROR, "a file is not valid json", overridable=False),
        _check("file-kind", Severity.ERROR,
               "the top level key of a file names no description kind, or several",
               overridable=False),
        _check("file-extension", Severity.ERROR,
               "a description file is not named '*.ddd.json'"),
        _check("schema", Severity.ERROR, "a file does not match the DDD contract",
               overridable=False),
        _check("include-cycle", Severity.ERROR, "projects include each other recursively",
               overridable=False),
        _check("include-empty", Severity.ERROR, "an include pattern matches no file"),
        _check("duplicate-component", Severity.ERROR,
               "two different files declare the same component name"),
        _check("duplicate-type", Severity.ERROR,
               "two different files declare the same type name"),
        _check("duplicate-unit", Severity.ERROR,
               "a unit is declared more than once, in one file or across files"),
        _check("duplicate-section", Severity.ERROR,
               "a memory section is declared more than once, in one file or across files"),
        _check("duplicate-constant", Severity.ERROR,
               "a constant is declared more than once, in one file or across files"),
        _check("duplicate-raster", Severity.ERROR,
               "a measurement raster is declared more than once, in one file or across files"),
        _check("duplicate-id", Severity.ERROR,
               "two data objects of one project carry the same id"),
        _check("duplicate-event", Severity.ERROR,
               "two measurement rasters claim the same event channel number"),
        _check("unknown-type", Severity.ERROR,
               "a typename names no type any file declares",
               needs_every_component=True),
        _check("unknown-unit", Severity.ERROR,
               "a unit is not in the vocabulary the project declares",
               needs_every_component=True),
        _check("unknown-section", Severity.ERROR,
               "a definition names a memory section no file declares",
               needs_every_component=True),
        _check("unknown-constant", Severity.ERROR,
               "a shape names a constant no file of the project declares",
               needs_every_component=True),
        _check("unknown-raster", Severity.ERROR,
               "a definition or a component names a measurement raster no file declares",
               needs_every_component=True),
        _check("section-access", Severity.ERROR,
               "a measurement is placed in a section the software cannot write"),
        _check("raster-kind", Severity.ERROR,
               "a raster is stated on a calibration object, which no daq list carries"),
        _check("type-kind", Severity.ERROR,
               "a declared type is used where its shape does not fit"),
        _check("type-cycle", Severity.ERROR,
               "structures nest each other, directly or through others"),
        _check("reserved-identifier", Severity.ERROR, "a name collides with a c keyword"),
        _check("name-collision", Severity.ERROR,
               "two generated names collide in the same c namespace or file name"),
        _check("duplicate-declaration", Severity.ERROR,
               "a component declares the same variable more than once"),
        _check("consumer-storage", Severity.ERROR,
               "an input declaration states storage that only the producing component decides"),
        _check("consumer-raster", Severity.ERROR,
               "an input declaration states a measurement raster only the producer decides"),
        _check("consumer-identity", Severity.ERROR,
               "a declaration that reads a variable states its identity"),
        _check("multiple-producers", Severity.ERROR,
               "a variable is written by more than one component"),
        _check("missing-producer", Severity.ERROR, "an input variable is written by nobody",
               needs_every_component=True),
        _check("local-conflict", Severity.ERROR,
               "a component local variable is also used by another component"),
        _check("definition-mismatch", Severity.ERROR,
               "components disagree on kind, datatype, unit, scaling, shape, volatility, "
               "stated limits or referenced axes"),
        _check("enum-conflict", Severity.ERROR,
               "the same enum name is defined with different enumerators"),
        _check("unknown-reference", Severity.ERROR,
               "a curve, map or axis refers to an object that no component declares",
               needs_every_component=True),
        _check("reference-kind", Severity.ERROR,
               "a reference points at an object of the wrong kind"),
        _check("init-invalid", Severity.ERROR,
               "an initial value does not fit the datatype of the variable"),
        _check("storage-mismatch", Severity.WARNING,
               "components disagree on how the a2l presents the object; the producer wins"),
        _check("condition-mismatch", Severity.WARNING,
               "declarations of one variable use different preprocessor conditions"),
        _check("unused-output", Severity.WARNING, "an output variable is read by no component",
               needs_every_component=True),
        _check("enum-duplicate-value", Severity.WARNING,
               "two enumerators of one enum share the same value"),
        _check("section-alignment", Severity.WARNING,
               "an object needs stricter alignment than its section guarantees"),
        _check("limits-out-of-range", Severity.WARNING,
               "the physical limits exceed what the datatype can represent"),
        _check("name-similar", Severity.WARNING,
               "two variables differ only in upper/lower case"),
        _check("a2l-unrepresentable", Severity.WARNING,
               "an object cannot be described by the a2l version that is generated"),
        _check("address-missing", Severity.WARNING,
               "an object reaching the a2l has no entry in the address map the run was given"),
        _check("empty-component", Severity.INFO, "a component declares no variable at all"),
        _check("incomplete-project", Severity.INFO,
               "a declaration is missing from the dictionary and the finding that explains "
               "why is not reported",
               needs_every_component=True),
        _check("missing-id", Severity.INFO,
               "a declaration that produces a variable states no identity for it"),
        _check("renamed-object", Severity.WARNING,
               "an object of the baseline is offered under a different name"),
        _check("removed-object", Severity.ERROR,
               "an object of the baseline is gone and somebody read it"),
        _check("changed-interface", Severity.ERROR,
               "kind, datatype, unit, scaling, shape, axes or locality of an object changed"),
        _check("removed-unused-object", Severity.WARNING,
               "an object of the baseline is gone; no component read it"),
        _check("changed-storage", Severity.WARNING,
               "the initial value, volatility or memory section of an object changed"),
        _check("narrowed-limits", Severity.WARNING,
               "the physical limits of an object got tighter, so calibrated data may not fit"),
        _check("changed-owner", Severity.WARNING,
               "another component produces the object now"),
        _check("changed-condition", Severity.WARNING,
               "the preprocessor condition of an object changed"),
        _check("changed-a2l", Severity.WARNING, "the a2l entry of an object changed"),
        _check("project-mismatch", Severity.WARNING,
               "the two sides of a comparison describe differently named projects"),
        _check("added-object", Severity.INFO, "the candidate declares an object the baseline "
               "did not"),
    )
}  # fmt: skip


def _pointer_order(pointer: str) -> tuple[int | str, ...]:
    """Sort key for a json pointer, with the indices ordered as numbers.

    Sorted as plain text, ``interface[10]`` comes before ``interface[2]`` and the
    findings of one file are listed in an order that has nothing to do with the file.
    """
    return tuple(
        int(part) if part.isdigit() else part for part in re.split(r"\[(\d+)\]", pointer) if part
    )


@dataclass(frozen=True, slots=True, order=True)
class Location:
    """Where a diagnostic comes from."""

    path: Path
    pointer: str = ""
    """Dotted path inside the json document, e.g. ``component.interface[2].definition``."""

    line: int | None = None
    column: int | None = None

    def render(self, root: Path | None = None) -> str:
        path = self.path
        if root is not None:
            with contextlib.suppress(ValueError):
                path = path.relative_to(root)
        text = path.as_posix()
        if self.line is not None:
            text += f":{self.line}"
            if self.column is not None:
                text += f":{self.column}"
        if self.pointer:
            text += f"#{self.pointer}"
        return text

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path.as_posix(),
            "pointer": self.pointer or None,
            "line": self.line,
            "column": self.column,
        }


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """A single finding."""

    check: str
    severity: Severity
    message: str
    location: Location | None = None
    notes: tuple[tuple[str, Location | None], ...] = ()
    """Additional ``(text, location)`` hints, e.g. the conflicting declaration site."""

    @property
    def sort_key(self) -> tuple[int, str, tuple[int | str, ...], str]:
        location = self.location
        return (
            self.severity.rank,
            location.path.as_posix() if location else "",
            _pointer_order(location.pointer) if location else (),
            self.check,
        )

    def render(self, root: Path | None = None) -> str:
        where = self.location.render(root) if self.location else "<project>"
        lines = [f"{where}: {self.severity.value}[{self.check}]: {self.message}"]
        for text, location in self.notes:
            prefix = f"{location.render(root)}: " if location else ""
            first, *rest = f"{prefix}{text}".splitlines() or [""]
            lines.append(f"{_NOTE_INDENT}{first}")
            # A note may run over several lines - an underlined name, for one - and the
            # continuation has to keep the column, or the carets point at the wrong letters.
            lines.extend(f"{' ' * len(_NOTE_INDENT)}{line}" for line in rest)
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "check": self.check,
            "severity": self.severity.value,
            "message": self.message,
            "location": self.location.to_dict() if self.location else None,
            "notes": [
                {"message": text, "location": location.to_dict() if location else None}
                for text, location in self.notes
            ],
        }


class UnknownCheckError(ValueError):
    """Raised when a severity override names a check that does not exist."""


@dataclass(frozen=True, slots=True)
class SeverityPolicy:
    """Maps check identifiers to the severity they are reported with."""

    overrides: dict[str, Severity] = field(default_factory=dict)
    strict: bool = False
    """Report warnings as errors."""

    @classmethod
    def from_strings(cls, values: Iterable[str], *, strict: bool = False) -> Self:
        """Build a policy from ``check=severity`` strings (as given on the command line)."""
        overrides: dict[str, Severity] = {}
        for value in values:
            name, separator, severity = value.partition("=")
            name = name.strip()
            if not separator:
                msg = f"expected 'check=severity', got '{value}'"
                raise UnknownCheckError(msg)
            info = CHECKS.get(name)
            if info is None:
                msg = f"unknown check '{name}'"
                raise UnknownCheckError(msg)
            if not info.overridable:
                msg = f"the severity of check '{name}' cannot be changed"
                raise UnknownCheckError(msg)
            try:
                overrides[name] = Severity(severity.strip().lower())
            except ValueError:
                choices = ", ".join(s.value for s in Severity)
                msg = f"unknown severity '{severity}' for check '{name}', expected one of {choices}"
                raise UnknownCheckError(msg) from None
        return cls(overrides, strict)

    def resolve(self, check: str) -> Severity:
        info = CHECKS.get(check)
        if info is None:
            severity = Severity.ERROR
        elif info.overridable:
            severity = self.overrides.get(check, info.default_severity)
        else:
            severity = info.default_severity
        if self.strict and severity is Severity.WARNING:
            return Severity.ERROR
        return severity


class DiagnosticBag:
    """Collects diagnostics and applies the severity policy."""

    def __init__(self, policy: SeverityPolicy | None = None) -> None:
        self.policy = policy or SeverityPolicy()
        self._items: list[Diagnostic] = []

    def add(
        self,
        check: str,
        message: str,
        location: Location | None = None,
        notes: Iterable[tuple[str, Location | None]] = (),
    ) -> Diagnostic | None:
        """Record a finding; returns ``None`` when the check is ignored."""
        severity = self.policy.resolve(check)
        if severity is Severity.IGNORE:
            return None
        diagnostic = Diagnostic(check, severity, message, location, tuple(notes))
        self._items.append(diagnostic)
        return diagnostic

    def __iter__(self) -> Iterator[Diagnostic]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    @property
    def sorted(self) -> list[Diagnostic]:
        return sorted(self._items, key=lambda d: d.sort_key)

    def count(self, severity: Severity) -> int:
        return sum(1 for item in self._items if item.severity is severity)

    @property
    def has_errors(self) -> bool:
        return any(item.severity is Severity.ERROR for item in self._items)

    def summary(self) -> str:
        parts = []
        for severity in (Severity.ERROR, Severity.WARNING, Severity.INFO):
            count = self.count(severity)
            if count:
                parts.append(f"{count} {severity.value}{'s' if count != 1 else ''}")
        return ", ".join(parts) if parts else "no findings"
