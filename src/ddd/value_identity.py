"""What two spellings of a key have to share to count as one value.

One rule, two callers that must not disagree about it. :mod:`ddd.variable_keys` groups the
panel's rows by it - two conversions or two ranges of limits written differently are one row,
one value in play, exactly as :mod:`ddd.analysis` treats them for ``definition-mismatch``.
:mod:`ddd.variables` narrows a settlement by it - a declaration already stating a value that
means what is being set to has nothing left to change, however differently the two are spelled.

A small module of its own rather than living with the values it compares: the rule needs
:func:`~ddd.models.conversion.conversion_interface_value` beside
:class:`~ddd.models.objects.Limits`, and :mod:`ddd.models.objects` imports
:mod:`ddd.models.conversion` back, so a home in :mod:`ddd.models.conversion` would close that
cycle. It is no better off in a caller: :mod:`ddd.variable_keys` already imports
:class:`~ddd.variables.Declared` from :mod:`ddd.variables`, so the rule put in
:mod:`ddd.variable_keys` would close a cycle the moment :mod:`ddd.variables` imported it back to
narrow a settlement. Neither caller depends on the other for it.
"""

from __future__ import annotations

import json
from typing import Any, Final

from pydantic import TypeAdapter, ValidationError

from ddd.models.conversion import Conversion, conversion_interface_value
from ddd.models.objects import Limits

_CONVERSION: Final[TypeAdapter[Conversion]] = TypeAdapter(Conversion)
"""Built once: a :class:`~pydantic.TypeAdapter` compiles a core schema from the annotation,
which is not free, and :func:`same_value` asks it once for every declaration stating a
conversion."""


def same_value(key: str, raw: str) -> str:
    """What two spellings of ``key`` have to share to count as one value.

    Canonical json text for every key but the two :mod:`ddd.analysis` resolves before it
    compares them - a definition may leave out what the models complete, and a caller has to
    group values the way the checker does, or a row reads as a disagreement the checker files
    no finding about, or a settlement proposes to change a declaration that already means what
    it is being set to. A ``conversion`` groups by
    :func:`~ddd.models.conversion.conversion_interface_value`, the same rule
    ``definition-mismatch`` applies: an enum by its name, everything else by what the models
    resolve it to, so ``{"factor": 2}`` groups with ``{"kind": "linear", "factor": 2, "offset":
    0}``. ``limits`` group by the two numbers :class:`~ddd.models.objects.Limits` resolves them
    to, so ``{"min": 0, "max": 100}`` groups with ``{"min": 0.0, "max": 100.0}``. Text the
    models refuse outright - a file may hold a half-written conversion - falls back to its
    canonical json text like any other key: a caller still has to do something with what is on
    disk.
    """
    # Raw text of a parsed document: json, always, so there is nothing here to fail on.
    value = json.loads(raw)
    if key == "conversion":
        conversion = _parsed_conversion(value)
        if conversion is not None:
            return json.dumps(conversion_interface_value(conversion), sort_keys=True)
    elif key == "limits":
        limits = _parsed_limits(value)
        if limits is not None:
            return json.dumps([float(bound) for bound in limits.as_tuple()])
    return json.dumps(value, sort_keys=True)


def _parsed_conversion(value: Any) -> Conversion | None:
    """``value`` as the models would resolve it, or ``None`` where they refuse it outright."""
    try:
        return _CONVERSION.validate_python(value)
    except ValidationError:
        return None


def _parsed_limits(value: Any) -> Limits | None:
    """``value`` as the models would resolve it, or ``None`` where they refuse it outright."""
    try:
        return Limits.model_validate(value)
    except ValidationError:
        return None
