"""Contract for the measurement raster vocabulary file.

A ``rasters`` file declares the DAQ events the target offers.  An event channel number is a
property of the ecu's XCP configuration - one number, one event - so a definition names a
raster the way it names a memory section: a reference to something declared once, project
wide, rather than a number every component restates and none of them decides.

A declaration carries what an ``EVENT`` needs and nothing about the transport that reaches
it.  DDD describes the data; how a calibration tool connects to the target stays the business
of whatever configures the XCP stack.
"""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from ddd.models.common import FileRoot

EVENT_NAME_LENGTH = 8
"""Longest raster name: the width of the short name an a2l ``EVENT`` carries.

Not a protocol limit. The protocol layer length-prefixes an event channel name with a byte and
forbids a terminator, so it carries far more than eight. The eight is from the a2l, whose
``EVENT`` block declares ``EVENT_CHANNEL_SHORT_NAME`` as ``char[9]`` - eight characters and a
terminator - beside the ``char[101]`` long name that ``description`` supplies. That is where a
raster name goes once the module level ``DAQ`` block is written. Nothing writes one yet, and
the limit is enforced anyway, so that a rasters file which loads today still loads then - the
reason the cycle rule below is enforced ahead of its use as well.
"""

EVENT_MAX = 0xFFFF
"""Widest event channel number XCP addresses."""

CYCLE_COUNT_MAX = 255
"""Widest cycle count an event carries: it is an unsigned 8 bit value."""

CYCLE_DECADES = 10
"""Time units an event offers: the decades from 1 ns to 1 s."""

_CYCLE = re.compile(r"^([0-9]+)(ns|us|ms|s)$")

_NANOSECONDS = {"ns": 1, "us": 1_000, "ms": 1_000_000, "s": 1_000_000_000}


def _nanoseconds(cycle: str) -> int | None:
    """The period in nanoseconds, or nothing when it is not a count and a unit at all."""
    match = _CYCLE.fullmatch(cycle)
    if match is None:
        return None
    return int(match.group(1)) * _NANOSECONDS[match.group(2)]


def _is_an_event_period(nanoseconds: int) -> bool:
    """Whether XCP can carry the period: a count of 1 to 255 times a decade from 1 ns to 1 s.

    Checked although this version writes no period, so that a rasters file which loads today
    still loads once the module level ``DAQ`` block is written: a rule added later would turn
    a file that was accepted into one that is refused, which is the migration nobody wants.
    """
    if nanoseconds < 1:
        return False
    return any(
        nanoseconds % decade == 0 and nanoseconds // decade <= CYCLE_COUNT_MAX
        for decade in (10**exponent for exponent in range(CYCLE_DECADES))
    )


class RasterDeclaration(BaseModel):
    """One DAQ event the target offers, named so that a definition can refer to it."""

    model_config = ConfigDict(frozen=True, extra="forbid", use_attribute_docstrings=True)

    raster: Annotated[
        str, StringConstraints(min_length=1, max_length=EVENT_NAME_LENGTH, pattern=r"^\S+$")
    ]
    """The name a definition refers to, which is also the short name of the XCP event.

    The a2l writes that short name into a field eight characters wide, so a longer name is
    refused rather than shortened: two names shortened to the same eight would collide in a
    calibration tool rather than here, where the author could still do something about it.
    """

    event: int = Field(strict=True, ge=0, le=EVENT_MAX)
    """The XCP event channel number, distinct across the project.

    The one field of a declaration the generated a2l carries today; the rest wait for the
    module level ``DAQ`` block that defines the events themselves.
    """

    cycle: str | None = None
    """The period, written as an integer and a unit: ``100us``, ``10ms``, ``1s``.

    No space and no fractional part - write ``1500us`` rather than ``1.5ms``. Left out, the
    event is not cyclic: crank synchronous, on change, on demand. That is a real kind of
    raster rather than an omission, which is why the key has no derived default.
    """

    description: str = ""
    """Free text saying what the event is, e.g. ``the 10 ms control task``."""

    @property
    def cycle_ns(self) -> int | None:
        """The period in nanoseconds, or nothing when the event is not cyclic."""
        if self.cycle is None:
            return None
        nanoseconds = _nanoseconds(self.cycle)
        assert nanoseconds is not None  # the validator refused every other spelling
        return nanoseconds

    @model_validator(mode="after")
    def _cycle_is_a_period_xcp_carries(self) -> RasterDeclaration:
        if self.cycle is None:
            return self
        nanoseconds = _nanoseconds(self.cycle)
        if nanoseconds is None:
            msg = (
                f"'{self.cycle}' is not a period: write a whole number and a unit, one of "
                f"'ns', 'us', 'ms' or 's', for example '10ms'"
            )
            raise ValueError(msg)
        if not _is_an_event_period(nanoseconds):
            msg = (
                f"'{self.cycle}' is no xcp event period: one is a count of 1 to "
                f"{CYCLE_COUNT_MAX} times a decade from 1ns to 1s, so '1500us' is one and "
                f"'1234ms' is not"
            )
            raise ValueError(msg)
        return self


class RastersFile(FileRoot):
    """Root object of a ``*.ddd.json`` measurement raster description.

    ``rasters`` is the top level key that makes this a rasters file; DDD decides what a file
    is from that key alone.  The file is listed in the ``includes`` of a project like any
    other description.
    """

    model_config = ConfigDict(title="DDD measurement rasters")

    rasters: Annotated[tuple[RasterDeclaration, ...], Field(min_length=1)]
    """The DAQ events the target offers; an empty list is no file at all."""
