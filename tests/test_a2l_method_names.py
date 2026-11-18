"""The names of the a2l's compu methods: told apart by a suffix, in time linear in the methods.

A name is the first free one of its base, so the second method of a unit is ``_2`` and the
third ``_3``. Finding the first free one by counting up from ``_2`` each time made a project
with a conversion of its own per object in one unit pay the square of the objects.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from ddd.backends.a2l.model import _CompuMethodBuilder
from ddd.ir import ResolvedLeaf
from ddd.models import (
    IDENTIFIER_MAX_LENGTH,
    Datatype,
    EnumConversion,
    Enumerator,
    LinearConversion,
)

LONG = "u" * 1100
"""A unit longer than an a2l identifier may be."""


class Probe(set[str]):
    """The names taken so far, counting every time one is asked after."""

    asked = 0

    def __contains__(self, item: object) -> bool:
        self.asked += 1
        return super().__contains__(item)


def entry(conversion: object, unit: str = "V") -> ResolvedLeaf:
    return cast(
        ResolvedLeaf,
        SimpleNamespace(conversion=conversion, unit=unit, datatype=Datatype.UINT16),
    )


def scaled(factor: float, unit: str = "V") -> ResolvedLeaf:
    return entry(LinearConversion(factor=factor, offset=0.0), unit)


def named(name: str) -> ResolvedLeaf:
    return entry(EnumConversion(name=name, enumerators=[Enumerator(name="A", value=0)]))


class TestTheNamesAreUnchanged:
    def test_the_conversions_of_a_unit_count_up(self) -> None:
        builder = _CompuMethodBuilder()
        names = [builder.reference(scaled(factor)) for factor in (1.0, 2.0, 3.0, 4.0)]
        assert names == ["CM_LIN_V", "CM_LIN_V_2", "CM_LIN_V_3", "CM_LIN_V_4"]

    def test_a_name_taken_by_another_base_is_stepped_over(self) -> None:
        """An enumeration named ``LIN_V_2`` is ``CM_LIN_V_2`` before the second scaling of
        ``V`` asks for it, and the third comes after the one that was taken."""
        builder = _CompuMethodBuilder()
        names = [
            builder.reference(named("LIN_V_2")),
            builder.reference(scaled(1.0)),
            builder.reference(scaled(2.0)),
            builder.reference(scaled(3.0)),
        ]
        assert names == ["CM_LIN_V_2", "CM_LIN_V", "CM_LIN_V_3", "CM_LIN_V_4"]

    def test_a_base_asked_after_the_suffix_that_took_its_name(self) -> None:
        builder = _CompuMethodBuilder()
        names = [
            builder.reference(scaled(1.0)),
            builder.reference(scaled(2.0)),
            builder.reference(named("LIN_V_2")),
            builder.reference(named("LIN_V")),
        ]
        assert names == ["CM_LIN_V", "CM_LIN_V_2", "CM_LIN_V_2_2", "CM_LIN_V_3"]

    def test_the_next_suffix_taken_after_the_count_is_stepped_over_too(self) -> None:
        builder = _CompuMethodBuilder()
        names = [
            builder.reference(scaled(1.0)),
            builder.reference(scaled(2.0)),
            builder.reference(named("LIN_V_3")),
            builder.reference(scaled(3.0)),
        ]
        assert names == ["CM_LIN_V", "CM_LIN_V_2", "CM_LIN_V_3", "CM_LIN_V_4"]

    def test_a_base_cut_to_the_limit_keeps_its_suffixes_inside_it(self) -> None:
        builder = _CompuMethodBuilder()
        names = [builder.reference(scaled(factor, LONG)) for factor in (1.0, 2.0, 3.0)]
        assert [len(name) for name in names] == [IDENTIFIER_MAX_LENGTH] * 3
        assert [name[-2:] for name in names] == ["UU", "_2", "_3"]


class TestTheWorkGrowsWithTheMethods:
    def test_a_name_is_not_found_by_counting_up_from_the_second_again(self) -> None:
        """Each of N scalings in one unit asked the names taken about every suffix below its
        own, N squared in all; a count per base asks about the one it takes."""
        count = 400
        builder = _CompuMethodBuilder()
        taken = Probe()
        builder._names = taken  # the stand-in that counts what is asked of it
        for index in range(count):
            builder.reference(scaled(1.0 + index))
        assert len(taken) == count
        assert taken.asked <= 3 * count, (
            f"{taken.asked} questions for {count} methods of one unit: the work is "
            f"quadratic in the methods that share a unit"
        )
