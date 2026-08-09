"""The comparison tables are an allowlist, so something has to watch the list.

Two declarations of one object are compared field by field, against a table
(:data:`ddd.analysis._INTERFACE_FIELDS` and ``_STORAGE_FIELDS`` inside a project,
:data:`ddd.compare._INTERFACE_FIELDS` and ``_STORAGE_FIELDS`` between two deliveries).
A table is an allowlist, and an allowlist fails open: add a field to a model and nothing
compares it, nothing fails, and two components disagreeing about it are reported consistent.

The tests below close that hole. Every field of every data object, and every field of the
resolved form the backends receive, has to be accounted for in exactly one of three ways:

* it is named in a comparison table,
* it reaches a table through a derived property under another name - ``dimensions`` is
  compared as ``shape``, ``axis``/``x_axis``/``y_axis``/``input`` as ``references`` - and the
  mapping below records which,
* it is deliberately not compared, and :data:`_NOT_COMPARED` says why in one line.

Adding a field to a model therefore fails here until somebody has decided which of the three
it is. That decision is the point; the test only insists that it is taken.

The second half of the file pins the deliberate *differences* between the two tables, which
are otherwise indistinguishable from oversights - and were, until they were written down.
"""

from __future__ import annotations

import pytest

from ddd import analysis, compare
from ddd.ir import ResolvedObject
from ddd.models import Axis, Curve, DataObject, Map, Measurement, Parameter, ValueBlock

OBJECT_KINDS = (Measurement, Parameter, ValueBlock, Axis, Curve, Map)


def table_names(*tables: tuple[object, ...]) -> set[str]:
    """The ``name`` of every field in the given comparison tables."""
    return {field.name for table in tables for field in table}  # type: ignore[attr-defined]


# A model field that is compared under a different name, and the name it is compared under.
# The value extractor of that table entry has to actually read this field - which is what
# makes the mapping a claim rather than a comment.
DERIVED_AS: dict[str, str] = {
    "dimensions": "shape",
    "size": "shape",
    "input": "references",
    "axis": "references",
    "x_axis": "references",
    "y_axis": "references",
    # The datatype comparison reads whichever of the two storage keys is stated, so a
    # declaration naming a structure disagrees with one spelling a base datatype.
    "typename": "datatype",
}

# Fields that are deliberately not compared, and the reason.
_NOT_COMPARED: dict[str, str] = {
    "name": "the name is what identifies the object; two declarations that differ in it are "
    "two different objects, not one object described twice",
    "description": "documentation. Two components may describe the same variable in their own "
    "words without disagreeing about it, and the producer's text is the one generated",
    "kind": "compared, but as a table field of its own - listed here only for ResolvedObject, "
    "see below",
    "init": "only a producer may state one, so there are never two to compare. A component "
    "that reads a variable has no say in what it starts as, and stating one is reported "
    "where it is written as consumer-storage rather than reconciled here afterwards",
    "section": "only a producer may state one, exactly like init: a consumer stating a "
    "section claims storage it does not own and is reported as consumer-storage where the "
    "claim is written",
}

# ResolvedObject carries the *result* of the analysis as well as the declaration, and the
# derived parts are not compared because they are not claims anybody makes.
_NOT_COMPARED_RESOLVED: dict[str, str] = {
    "name": _NOT_COMPARED["name"],
    "description": _NOT_COMPARED["description"],
    "consumers": "derived: who reads the object is a fact about the project, not a property "
    "of the object that could disagree",
    "owner": "compared by _report_owner_change, which phrases it as changed-owner rather "
    "than as an interface change",
    "condition": "compared by a hand-written branch, because the finding is graded "
    "differently (changed-condition) and its message depends on the direction of the change",
    "a2l": "compared by a hand-written branch so that the finding is changed-a2l rather than "
    "changed-interface",
    "limits": "compared by a hand-written directional branch: narrowing warns, widening is "
    "deliberately silent, and neither is expressible as an equality",
}


class TestEveryModelFieldIsAccountedFor:
    """The guard against the allowlist failing open."""

    @pytest.mark.parametrize("model", OBJECT_KINDS, ids=lambda m: m.__name__)
    def test_every_field_of_every_object_kind(self, model: type[DataObject]) -> None:
        compared = table_names(analysis._INTERFACE_FIELDS, analysis._STORAGE_FIELDS)
        for name in model.model_fields:
            accounted = (
                name in compared or DERIVED_AS.get(name) in compared or name in _NOT_COMPARED
            )
            assert accounted, (
                f"{model.__name__}.{name} is compared by nothing: two components could "
                f"declare it differently and DDD would report them consistent. Add it to "
                f"_INTERFACE_FIELDS or _STORAGE_FIELDS in ddd/analysis.py, or to "
                f"DERIVED_AS/_NOT_COMPARED here with the reason."
            )

    def test_every_field_of_the_resolved_object(self) -> None:
        compared = table_names(compare._INTERFACE_FIELDS, compare._STORAGE_FIELDS)
        for name in ResolvedObject.model_fields:
            accounted = (
                name in compared
                or DERIVED_AS.get(name) in compared
                or name in _NOT_COMPARED_RESOLVED
            )
            assert accounted, (
                f"ResolvedObject.{name} is compared by nothing: a delivery could change it "
                f"and 'ddd compare' would report the candidate a valid replacement. Add it "
                f"to a table in ddd/compare.py, or to _NOT_COMPARED_RESOLVED here."
            )

    def test_the_derived_mapping_is_not_stale(self) -> None:
        """A name in DERIVED_AS has to still be a field, and its target still a table entry."""
        fields = {name for model in OBJECT_KINDS for name in model.model_fields}
        compared = table_names(
            analysis._INTERFACE_FIELDS,
            analysis._STORAGE_FIELDS,
            compare._INTERFACE_FIELDS,
            compare._STORAGE_FIELDS,
        )
        for name, target in DERIVED_AS.items():
            assert name in fields, f"DERIVED_AS names '{name}', which no model declares"
            assert target in compared, f"DERIVED_AS maps '{name}' to '{target}', not a table"

    def test_the_excuses_are_not_stale(self) -> None:
        fields = {name for model in OBJECT_KINDS for name in model.model_fields}
        for name in _NOT_COMPARED:
            assert name in fields, f"_NOT_COMPARED names '{name}', which no model declares"
        for name in _NOT_COMPARED_RESOLVED:
            assert name in ResolvedObject.model_fields, (
                f"_NOT_COMPARED_RESOLVED names '{name}', which ResolvedObject does not declare"
            )


class TestComparisonTables:
    """Why the two tables differ, which is otherwise indistinguishable from an oversight.

    :mod:`ddd.analysis` asks whether several components agree about one object *now*.
    :mod:`ddd.compare` asks whether one delivery can replace another, which is directional and
    graded. The same property therefore lands in different places, and every difference below
    is a decision rather than an accident.
    """

    def test_limits_are_a_field_inside_a_project_and_a_direction_between_deliveries(
        self,
    ) -> None:
        """Inside a project two stated limits must match; between deliveries the direction
        decides, so compare.py handles limits by hand instead of by table."""
        inside = {field.name: field for field in analysis._INTERFACE_FIELDS}
        assert "limits" in inside
        # And a declaration that omits them agrees with one that states them.
        assert inside["limits"].optional
        assert "limits" not in table_names(compare._INTERFACE_FIELDS, compare._STORAGE_FIELDS)

    def test_volatile_is_an_interface_field_and_unlike_limits_is_not_optional(self) -> None:
        """Both are stated by hand, and only one of them may be left out of a definition.

        ``limits`` are derived from the datatype and the conversion when a declaration omits
        them, so omitting them is asking for the derivation, and the table relaxes the
        comparison to match. Nothing derives ``volatile``, which is why the key is required on
        every definition - so there is never a silence to interpret here either, and the entry
        is not optional.
        """
        inside = {field.name: field for field in analysis._INTERFACE_FIELDS}
        assert "volatile" in inside
        assert not inside["volatile"].optional
        assert inside["limits"].optional

    def test_volatile_is_an_interface_field_inside_a_project_and_storage_between_deliveries(
        self,
    ) -> None:
        """The same property, graded by who is left describing the object wrongly.

        Inside a project the declarations are compiled together, so one component saying
        ``volatile`` and another not gives two headers that describe one piece of storage
        differently, and the component that was not told may hold a value that changes under
        it. That is an interface disagreement and an error.

        Between two deliveries there is only ever one answer at a time: every consumer is
        regenerated and recompiled against the new headers, so nobody is left wrong. What
        changed is how the object behaves, which is ``changed-storage`` - the same grade as a
        changed initial value, and deliberately not ``changed-interface``.
        """
        assert "volatile" in table_names(analysis._INTERFACE_FIELDS)
        assert "volatile" not in table_names(analysis._STORAGE_FIELDS)
        assert "volatile" in table_names(compare._STORAGE_FIELDS)
        assert "volatile" not in table_names(compare._INTERFACE_FIELDS)

    def test_init_is_not_compared_inside_a_project_and_is_storage_between_deliveries(
        self,
    ) -> None:
        """The mirror of volatile, and the reason the two are not one rule.

        Only a producer may state an initial value, so inside a project there are never two of
        them to compare - a consumer that states one is told so as ``consumer-storage`` where
        it wrote it. Between deliveries the producer's own answer may well have changed, and
        that is a behaviour change consumers should hear about.
        """
        assert "init" not in table_names(analysis._INTERFACE_FIELDS, analysis._STORAGE_FIELDS)
        assert "init" in _NOT_COMPARED
        assert "init" in table_names(compare._STORAGE_FIELDS)

    def test_a2l_is_a_storage_field_inside_a_project_and_its_own_check_between_deliveries(
        self,
    ) -> None:
        """A consumer disagreeing about the a2l block loses to the producer with a warning;
        a delivery changing it earns the separate changed-a2l finding."""
        assert "a2l" in table_names(analysis._STORAGE_FIELDS)
        assert "a2l" not in table_names(compare._INTERFACE_FIELDS, compare._STORAGE_FIELDS)

    def test_locality_is_only_a_question_between_deliveries(self) -> None:
        """Inside a project, scope conflicts are caught by local-conflict while ownership is
        being settled; between deliveries, an object turning local takes itself out of reach
        of everyone who read it, which is an interface change."""
        assert "local" in table_names(compare._INTERFACE_FIELDS)
        assert "local" not in table_names(analysis._INTERFACE_FIELDS, analysis._STORAGE_FIELDS)

    def test_only_the_analysis_table_relaxes_an_omitted_property(self) -> None:
        """`optional` exists because a consumer may leave a derived property to the producer.
        Between two deliveries there is no producer to defer to, so nothing is optional."""
        assert any(field.optional for field in analysis._INTERFACE_FIELDS)
        assert not any(getattr(field, "optional", False) for field in compare._INTERFACE_FIELDS)

    def test_shape_is_declared_in_one_and_resolved_in_the_other(self) -> None:
        """analysis compares what the author wrote, before the axes of a curve or map are
        resolved; compare works on the dictionary, where the shape is already known."""
        assert "shape" in table_names(analysis._INTERFACE_FIELDS)
        assert "shape" in table_names(compare._INTERFACE_FIELDS)
        declared = next(f for f in analysis._INTERFACE_FIELDS if f.name == "shape")
        curve = Curve(
            kind="curve", name="C", datatype="uint8", conversion={}, axis="Ax", volatile=False
        )
        assert declared.value(curve) is None  # not known yet, it comes from the axis
