"""Reading structured datatype files, and checking the graph they form.

The model level rules are in ``test_types.py``; these are the ones that need more than one
file, or the rest of the project, to have any meaning.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from conftest import (
    checks,
    component,
    declare,
    messages,
    project,
    render_files,
    run_analysis,
    write_tree,
)
from ddd.diagnostics import DiagnosticBag
from ddd.loading import LoadedType, load_workspace


def val(name: str, datatype: str = "uint16", **extra: Any) -> dict[str, Any]:
    storage: dict[str, Any] = (
        {} if "typename" in extra else {"datatype": datatype, "conversion": {"kind": "identity"}}
    )
    return {"name": name, "member": "value", **storage, **extra}


def nest(name: str, type_name: str) -> dict[str, Any]:
    """A member that nests another structure, which is a value member naming it."""
    return val(name, typename=type_name)


def struct(name: str, *members: dict[str, Any]) -> dict[str, Any]:
    return {"type": "struct", "name": name, "members": list(members) or [val("value")]}


def scalar(name: str, datatype: str = "uint16", **extra: Any) -> dict[str, Any]:
    meaning: dict[str, Any] = {} if "conversion" in extra else {"conversion": {"kind": "identity"}}
    return {"type": "scalar", "name": name, "datatype": datatype, **meaning, **extra}


def types(*entries: dict[str, Any]) -> dict[str, Any]:
    return {"types": list(entries)}


def ladder(depth: int) -> list[dict[str, Any]]:
    """``L{i}_t`` nests ``A{i}_t`` and ``B{i}_t``; both nest ``L{i+1}_t`` in turn.

    The last rung's ``A`` and ``B`` hold a value instead of nesting a further ``L``, so the
    ladder bottoms out on its own. Three types a rung, and two routes down every rung: the
    walks over it are what :class:`TestDiamondShapedNesting` is about, and the ``2 ** depth``
    leaves an instance of ``L0_t`` would contribute are what :class:`TestTooManyLeaves` is.
    """
    entries: list[dict[str, Any]] = []
    for index in range(depth):
        entries.append(struct(f"L{index}_t", nest("a", f"A{index}_t"), nest("b", f"B{index}_t")))
        tail = nest("down", f"L{index + 1}_t") if index + 1 < depth else val("value")
        entries.append(struct(f"A{index}_t", tail))
        entries.append(struct(f"B{index}_t", tail))
    return entries


def load(tree: Path, files: dict[str, Any], root: str = "project.ddd.json") -> Any:
    bag = DiagnosticBag()
    write_tree(tree, files)
    workspace = load_workspace(tree / root, bag)
    return workspace, bag


def first(bag: DiagnosticBag) -> Any:
    return next(iter(bag))


class TestReadingTypes:
    def test_a_project_collects_the_structures_it_includes(self, tree: Path) -> None:
        workspace, bag = load(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json"),
                "types.ddd.json": types(struct("B_t"), struct("A_t")),
            },
        )
        assert not checks(bag)
        assert workspace is not None
        # sorted by name, so the include order cannot change the generated output
        assert [entry.name for entry in workspace.types] == ["A_t", "B_t"]

    def test_the_file_is_reported_as_a_source(self, tree: Path) -> None:
        """A build has to run DDD again when a structure changes."""
        workspace, _ = load(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json"),
                "types.ddd.json": types(struct("A_t")),
            },
        )
        assert workspace is not None
        assert any(path.name == "types.ddd.json" for path in workspace.sources())

    def test_two_files_cannot_declare_the_same_structure(self, tree: Path) -> None:
        _, bag = load(
            tree,
            {
                "project.ddd.json": project("P", "one.ddd.json", "two.ddd.json"),
                "one.ddd.json": types(struct("A_t")),
                "two.ddd.json": types(struct("A_t")),
            },
        )
        assert checks(bag) == ["duplicate-type"]
        assert "is already declared" in first(bag).render()
        assert first(bag).notes, "the first declaration has to be pointed at as well"

    def test_a_malformed_types_file_is_reported_against_its_keys(self, tree: Path) -> None:
        _, bag = load(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json"),
                "types.ddd.json": {"types": [{"name": "A_t", "members": [{"name": "x"}]}]},
            },
        )
        assert checks(bag) == ["schema"]

    def test_an_enum_on_a_non_integer_is_refused_where_it_is_written(self, tree: Path) -> None:
        """The rule of a definition holds on a scalar type and on a structure member alike.

        Both used to slip through: only a definition refused an enum conversion on a
        non-integer datatype, so a types file could smuggle one in for every component that
        named the type.
        """
        _, bag = load(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json"),
                "types.ddd.json": types(
                    scalar(
                        "Bad_t",
                        "float32",
                        conversion={"kind": "enum", "name": "E_t", "enumerators": {"A": 0}},
                    ),
                    struct(
                        "S_t",
                        val(
                            "flag",
                            "boolean",
                            conversion={"kind": "enum", "name": "F_t", "enumerators": {"B": 0}},
                        ),
                    ),
                ),
            },
        )
        assert checks(bag) == ["schema", "schema"]
        # The union tags are not keys of the document, so the pointers carry no '.scalar' or
        # '.struct' segment - an editor resolves them against what is actually written.
        pointers = [diagnostic.location.pointer for diagnostic in bag if diagnostic.location]
        assert pointers == ["types[0]", "types[1].members[0]"]
        assert "enum conversion 'E_t' requires an integer datatype, got 'float32'" in messages(bag)
        assert "enum conversion 'F_t' requires an integer datatype, got 'boolean'" in messages(bag)

    def test_a_types_file_is_not_analysed_on_its_own(self, tree: Path) -> None:
        """It declares no variable, so there is nothing to resolve or generate from it."""
        workspace, bag = load(tree, {"types.ddd.json": types(struct("A_t"))}, root="types.ddd.json")
        assert workspace is None
        assert checks(bag) == ["file-kind"]
        assert "list it in the 'includes'" in first(bag).render()

    def test_a_file_cannot_be_two_kinds_at_once(self, tree: Path) -> None:
        _, bag = load(
            tree,
            {"both.ddd.json": {"component": {"name": "X"}, "types": [struct("A_t")]}},
            root="both.ddd.json",
        )
        assert checks(bag) == ["file-kind"]
        assert "'component' and 'types'" in first(bag).render()

    def test_a_file_of_no_known_kind_lists_what_it_should_have(self, tree: Path) -> None:
        _, bag = load(tree, {"stray.ddd.json": {"stuff": 1}}, root="stray.ddd.json")
        assert checks(bag) == ["file-kind"]
        rendered = first(bag).render()
        assert "'project', 'component', 'types', 'units'" in rendered
        assert "found: stuff" in rendered


class TestTypeGraph:
    def test_a_sound_graph_reports_nothing(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json"),
                "types.ddd.json": types(
                    struct("Inner_t", val("value")),
                    struct("Outer_t", nest("inner", "Inner_t"), val("count", "uint32")),
                ),
            },
        )
        assert not checks(bag)

    def test_a_member_nesting_an_undeclared_structure(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json"),
                "types.ddd.json": types(struct("A_t", nest("gone", "Missing_t"))),
            },
        )
        assert checks(bag) == ["unknown-type"]
        rendered = first(bag).render()
        assert "'Missing_t'" in rendered
        assert "types[0].members[0]" in rendered

    def test_two_structures_nesting_each_other(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json"),
                "types.ddd.json": types(
                    struct("A_t", nest("b", "B_t")), struct("B_t", nest("a", "A_t"))
                ),
            },
        )
        # once, not once per participant: the chain names them all
        assert checks(bag) == ["type-cycle"]
        assert "A_t -> B_t -> A_t" in first(bag).render()

    def test_a_structure_nested_twice_is_not_a_cycle(self, tree: Path) -> None:
        """A diamond is not a cycle: the resolvability walk meets ``Inner_t`` a second time,
        already cleared, and simply does not follow it again."""
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json", "a.ddd.json"),
                "types.ddd.json": types(
                    struct("Inner_t", val("v")),
                    struct("S_t", nest("first", "Inner_t"), nest("second", "Inner_t")),
                ),
                "a.ddd.json": component("A", declare("local", "X", typename="S_t")),
            },
        )
        assert checks(bag) == []
        assert dictionary is not None
        assert [leaf.path for leaf in dictionary.leaves] == ["X.first.v", "X.second.v"]

    def test_a_structure_nesting_itself(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json"),
                "types.ddd.json": types(struct("A_t", nest("self", "A_t"))),
            },
        )
        assert checks(bag) == ["type-cycle"]
        assert "A_t -> A_t" in first(bag).render()

    def test_a_sound_structure_leading_to_a_cycle_is_reported_at_the_cycle(
        self, tree: Path
    ) -> None:
        """``Head_t`` is not itself recursive, so the finding belongs to the pair that is."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json"),
                "types.ddd.json": types(
                    struct("Head_t", nest("down", "A_t")),
                    struct("A_t", nest("b", "B_t")),
                    struct("B_t", nest("a", "A_t")),
                ),
            },
        )
        assert checks(bag) == ["type-cycle"]
        rendered = first(bag).render()
        assert "A_t -> B_t -> A_t" in rendered
        assert "types.ddd.json#types[1]" in rendered

    def test_a_variable_of_a_structure_with_an_unknown_member_type_is_dropped(
        self, tree: Path
    ) -> None:
        """The finding at the member is the report; instantiating the structure adds none.

        The declarations are dropped the way ones naming a recursive structure are - a
        structure with an unresolvable leaf cannot be flattened - and the rest of the
        project still resolves.
        """
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json", "a.ddd.json"),
                "types.ddd.json": types(
                    struct("Broken_t", nest("ghost", "Missing_t")),
                    struct("Wrap_t", nest("broken", "Broken_t")),
                ),
                "a.ddd.json": component(
                    "A",
                    declare("output", "Direct", typename="Broken_t"),
                    declare("output", "Nested", typename="Wrap_t"),
                    declare("local", "Fine", "uint8"),
                ),
            },
        )
        assert checks(bag) == ["unknown-type"]
        assert dictionary is not None
        assert not dictionary.instances
        assert not dictionary.leaves
        assert [entry.name for entry in dictionary.objects] == ["Fine"]


class TestNestingTooDeep:
    """A structure nesting deeper than DDD reads is refused at the type that crosses the limit.

    Everything that walks a structure used to follow it as deep as it was written, so a chain
    a few hundred long ended ``ddd check`` in a ``RecursionError`` traceback - at whatever
    walk ran out of stack first - instead of in a finding anybody could act on. The cap turns
    that into one finding, at the innermost type that is already too deep to read; every type
    nesting it is unusable for the same reason and is dropped without a second finding.
    """

    @staticmethod
    def chain(depth: int) -> list[dict[str, Any]]:
        """``T1_t`` holds a value and ``Tn_t`` nests ``T(n-1)_t``, so ``Tn_t`` is ``n`` deep."""
        return [
            struct("T1_t", val("value")),
            *(
                struct(f"T{index}_t", nest("down", f"T{index - 1}_t"))
                for index in range(2, depth + 1)
            ),
        ]

    def files(self, depth: int, *includes: str, **extra: Any) -> dict[str, Any]:
        """The chain, and one variable of the type at the top of it."""
        return {
            "project.ddd.json": project("P", "types.ddd.json", *includes, "a.ddd.json"),
            "types.ddd.json": types(*self.chain(depth)),
            "a.ddd.json": component("A", declare("local", "X", typename=f"T{depth}_t", **extra)),
        }

    def test_a_structure_at_the_limit_still_resolves(self, tree: Path) -> None:
        """Sixty four levels is the deepest structure there is, and it flattens as any does."""
        dictionary, bag = run_analysis(tree, self.files(64))
        assert checks(bag) == []
        assert dictionary is not None
        assert [leaf.path for leaf in dictionary.leaves] == ["X" + ".down" * 63 + ".value"]

    def test_one_level_deeper_is_refused_at_the_type_that_crosses_the_limit(
        self, tree: Path
    ) -> None:
        dictionary, bag = run_analysis(tree, self.files(65))
        assert checks(bag) == ["schema"]
        rendered = first(bag).render()
        assert "types.ddd.json#types[64]" in rendered
        assert "structure 'T65_t' nests 65 levels deep; DDD reads at most 64" in rendered
        # The variable of it is dropped, the way one of any other unusable type is; `schema`
        # cannot be silenced, so there is no `incomplete-project` to report its absence.
        assert dictionary is not None
        assert not dictionary.instances
        assert not dictionary.leaves

    def test_the_types_nesting_the_offender_are_dropped_without_a_second_finding(
        self, tree: Path
    ) -> None:
        """Reported once, where the nesting first goes over; ``T70_t`` inherits the cause.

        Variables pinned either side of the limit, not only at the outermost type: ``T63_t``
        and ``T64_t`` are still within it and keep their instances, while ``T65_t`` - the one
        the finding names - and everything nesting it, ``T66_t`` and ``T70_t`` among them,
        are dropped without a finding of their own.
        """
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json", "a.ddd.json"),
                "types.ddd.json": types(*self.chain(70)),
                "a.ddd.json": component(
                    "A",
                    declare("local", "X63", typename="T63_t"),
                    declare("local", "X64", typename="T64_t"),
                    declare("local", "X65", typename="T65_t"),
                    declare("local", "X66", typename="T66_t"),
                    declare("local", "X70", typename="T70_t"),
                ),
            },
        )
        assert checks(bag) == ["schema"]
        assert "'T65_t' nests 65 levels deep" in messages(bag)
        assert dictionary is not None
        assert [instance.name for instance in dictionary.instances] == ["X63", "X64"]

    def test_a_variable_of_an_over_deep_type_is_placed_without_walking_it(self, tree: Path) -> None:
        """The alignment a section guarantees is compared against a walk of the structure.

        It is asked of every declaration that states a section, dropped ones included, which
        is the one walk that still starts at a type the cap refused.
        """
        _, bag = run_analysis(
            tree,
            {
                **self.files(500, "sections.ddd.json", section=".data"),
                "sections.ddd.json": {
                    "sections": [{"section": ".data", "access": "read-write", "alignment": 1}]
                },
            },
        )
        assert checks(bag) == ["schema"]

    def test_five_hundred_levels_are_a_finding_rather_than_a_traceback(self, tree: Path) -> None:
        dictionary, bag = run_analysis(tree, self.files(500))
        assert checks(bag) == ["schema"]
        assert "'T65_t' nests 65 levels deep" in messages(bag)
        assert dictionary is not None
        assert not dictionary.instances

    def test_a_deep_chain_that_closes_into_a_cycle_is_left_to_type_cycle(self, tree: Path) -> None:
        """No depth is reported on a cycle: a structure that contains itself has no depth.

        Characterises the finding alone - ``type-cycle`` and nothing else - at a depth
        chosen to be cheap rather than to prove anything about the walk: three hundred is
        comfortably past :data:`_MAX_TYPE_NESTING`, so the cycle is the only thing left to
        report. That the walk behind this finding is iterative, and copes with a chain far
        longer than any real project would write, is proved directly and far more cheaply
        by ``test_nesting_cycle_walks_a_three_thousand_deep_ring_in_one_call`` below, which
        calls ``_nesting_cycle`` once instead of running a whole analysis over the ring.
        """
        entries = self.chain(300)
        entries[0] = struct("T1_t", nest("up", "T300_t"))
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json", "a.ddd.json"),
                "types.ddd.json": types(*entries),
                "a.ddd.json": component("A", declare("local", "X", typename="T300_t")),
            },
        )
        assert checks(bag) == ["type-cycle"]

    def test_nesting_cycle_walks_a_three_thousand_deep_ring_in_one_call(self, tree: Path) -> None:
        """A direct call, once, proves the walk itself is iterative - the pass over it does not.

        A recursive ``_nesting_cycle`` survived to somewhere around a thousand levels on the
        machine the cap was measured on (see the task 3 report); three thousand is
        comfortably past that, so surviving it here is evidence the walk no longer recurses.
        Called once, directly, rather than through :func:`run_analysis`: ``_check_types``
        calls it once per declared type, which is quadratic over a ring where nothing ever
        settles, and that pass is already characterised - cheaply, at a depth of three
        hundred - by the test above. One call is linear in the ring's length, so proving the
        walk itself needs no more than that.
        """
        # Private: the walk this proves iterative is `_check_types`'s alone to call; nothing
        # public exposes it.
        from ddd.analysis import _nesting_cycle

        entries = self.chain(3000)
        entries[0] = struct("T1_t", nest("up", "T3000_t"))
        workspace, bag = load(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json"),
                "types.ddd.json": types(*entries),
            },
        )
        assert not checks(bag)
        assert workspace is not None
        # Built the way `_Analysis.__init__` builds `self._types`, which is what
        # `_check_types` passes as `declared`.
        declared: dict[str, LoadedType] = {entry.name: entry for entry in workspace.types}
        cycle = _nesting_cycle("T1_t", declared, set())
        # The cycle is the chain from the first repeated name back to it (see the
        # docstring), so a ring of 3000 distinct types comes back as all 3000 names plus
        # `T1_t` once more, closing the loop it started.
        assert len(cycle) == 3001
        assert cycle[0] == cycle[-1] == "T1_t"
        assert len(set(cycle)) == 3000

    def test_a_cyclic_chain_with_a_variable_in_a_section_does_not_recurse_without_bound(
        self, tree: Path
    ) -> None:
        """A cycle has no depth, so the old guard - keyed on depth alone - let it through.

        ``_reaches_external`` had no guard of its own, and ``_check_sections`` asks the
        alignment of every declaration naming a declared section, dropped ones included: a
        variable of a type that closes a long chain into a cycle used to walk the whole
        chain, unguarded, looking for an external member, and ran out of stack before
        ``_check_types`` ever reported the cycle. The type is left to ``type-cycle``, and
        there is no alignment estimate to give.
        """
        entries = self.chain(400)
        entries[0] = struct("T1_t", nest("up", "T400_t"))
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project(
                    "P", "types.ddd.json", "sections.ddd.json", "a.ddd.json"
                ),
                "types.ddd.json": types(*entries),
                "sections.ddd.json": {
                    "sections": [{"section": ".data", "access": "read-write", "alignment": 1}]
                },
                "a.ddd.json": component(
                    "A", declare("local", "X", typename="T400_t", section=".data")
                ),
            },
        )
        assert checks(bag) == ["type-cycle"]

    def test_a_self_nesting_type_over_a_deep_chain_does_not_recurse_without_bound(
        self, tree: Path
    ) -> None:
        """Two defects, not one: the self-nest is ``type-cycle``, the chain is ``schema``.

        ``Self_t`` is unusable for its own reason and never reaches the cap-based guard at
        all - it has no depth, being cyclic - so before the fix, asking its alignment still
        walked ``_reaches_external`` down its *other* member into a five hundred level chain
        with nothing to stop it. The chain crosses the limit on its own and is reported
        exactly as it would be without ``Self_t`` nesting it.
        """
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project(
                    "P", "types.ddd.json", "sections.ddd.json", "a.ddd.json"
                ),
                "types.ddd.json": types(
                    struct("Self_t", nest("self", "Self_t"), nest("chain", "T500_t")),
                    *self.chain(500),
                ),
                "sections.ddd.json": {
                    "sections": [{"section": ".data", "access": "read-write", "alignment": 1}]
                },
                "a.ddd.json": component(
                    "A", declare("local", "X", typename="Self_t", section=".data")
                ),
            },
        )
        assert checks(bag) == ["schema", "type-cycle"]


class TestDiamondShapedNesting:
    """A name two members of one structure nest is walked once, not once per member.

    Nesting is not a tree: ``L{i}_t`` nests ``A{i}_t`` and ``B{i}_t``, and both nest
    ``L{i+1}_t`` in turn, so a ladder of these diamonds shares one name between two routes
    at every rung. A walk with no memory of where it has already been re-explores a shared
    name from the second route exactly as it did from the first, and everything shared
    beneath *that* besides - doubling the work at every rung of diamond stacked on the last,
    so a ladder of them only a couple of dozen rungs deep used to take minutes rather than
    the fraction of a second it costs once a name already cleared is remembered instead of
    walked again.
    """

    def test_a_deep_ladder_of_diamonds_is_answered_in_a_fraction_of_a_second(
        self, tree: Path
    ) -> None:
        """No instance of any of it - ``_check_types`` walks every declared type regardless.

        Depth 24 is the seventy-two types the performance report measures; before a walk
        remembered a name it had already cleared, this did not return inside two minutes.
        Nothing about the time is asserted here - a timing assertion is a flaky test waiting
        to happen - report the duration with ``--durations=5`` instead.

        The one finding is the leaf count of :class:`TestTooManyLeaves`: a rung doubles the
        leaves of the rung below it, so twenty-four of them are 16 777 216 leaves and the
        ladder is refused whether or not anything declares a variable of it - at ``L7_t``,
        the innermost rung that is already over the limit. It says nothing about what this
        test is about: every one of the seventy-two types is still walked, by the depth walk
        and the cycle walk before the count and by the count itself.
        """
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json"),
                "types.ddd.json": types(*ladder(24)),
            },
        )
        assert checks(bag) == ["schema"]
        assert "structure 'L7_t' has 131072 leaves" in messages(bag)

    def test_a_cycle_behind_the_diamond_is_still_reported_once(self, tree: Path) -> None:
        """The last rung also nests ``L0_t``, closing every route down the ladder into a cycle.

        Settling a name a walk has cleared must never stop a *later* start from finding a
        cycle a route through that name reaches - and none of these seventy-two types is
        ever settled, since every one of them sits on the single cycle the extra member
        closes: reaching a name at all means walking it, and a name is only settled once its
        own walk found no cycle. What keeps this to one finding rather than one per starting
        type is not new here either: ``_check_types`` keys the finding on the cycle's
        participants, not on the type whose walk found it, exactly as it did before this
        change for a cycle two starts both happened to reach.
        """
        entries = ladder(24)
        entries[-3] = struct(
            "L23_t", nest("a", "A23_t"), nest("b", "B23_t"), nest("closes", "L0_t")
        )
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json"),
                "types.ddd.json": types(*entries),
            },
        )
        assert checks(bag) == ["type-cycle"]


class TestTooManyLeaves:
    """An array of structures larger than the outputs could carry is refused before it is spread.

    A structure reaches the dictionary and the a2l one leaf per member per element - there is
    no single address describing ``cell[0].raw`` and ``cell[1].raw`` - so a hundred thousand
    by a thousand array of a two member structure is two hundred million leaves to build,
    sort and write. It used to be built: ``ddd check`` on that project returned no answer at
    all, and the diamond ladder above reached a million leaves through a types file of sixty
    lines. Both are now refused, the array where its dimensions are written and the type
    where it is declared.
    """

    CELL = struct("Cell_t", val("a"), val("b"))

    def files(self, *entries: dict[str, Any], **definition: Any) -> dict[str, Any]:
        """The types, and one variable declared over them."""
        return {
            "project.ddd.json": project("P", "types.ddd.json", "a.ddd.json"),
            "types.ddd.json": types(*entries),
            "a.ddd.json": component("A", declare("local", "V", **definition)),
        }

    def test_an_array_of_structures_larger_than_the_outputs_carry_is_refused(
        self, tree: Path
    ) -> None:
        dictionary, bag = run_analysis(
            tree, self.files(self.CELL, typename="Cell_t", dimensions=[100000, 1000])
        )
        assert checks(bag) == ["schema"]
        rendered = first(bag).render()
        assert "a.ddd.json#component.interface[0].definition.dimensions" in rendered
        assert "'V' would contribute 200000000 leaves; DDD carries at most 100000" in rendered
        # Dropped like any other declaration that cannot resolve: `schema` cannot be
        # silenced, so nothing has to report the absence a second time.
        assert dictionary is not None
        assert not dictionary.instances
        assert not dictionary.leaves

    def test_an_array_of_structures_at_the_limit_is_flattened_whole(self, tree: Path) -> None:
        """Sixty four by sixty four of a twenty member structure: 81 920 leaves, all kept."""
        wide = struct("Wide_t", *(val(f"m{index}") for index in range(20)))
        dictionary, bag = run_analysis(
            tree, self.files(wide, typename="Wide_t", dimensions=[64, 64])
        )
        assert checks(bag) == []
        assert dictionary is not None
        assert len(dictionary.leaves) == 81920

    def test_a_structure_with_no_leaves_of_its_own_is_still_capped_by_its_elements(
        self, tree: Path
    ) -> None:
        """Every member opaque: no leaf to count, and one element path each all the same.

        The leaf cap says nothing about an array of these - it contributes none - so the cap
        that answers is the one every array has.
        """
        _, bag = run_analysis(
            tree,
            self.files(
                {"type": "external", "name": "Opaque_t", "header": "opaque.h"},
                struct("Box_t", nest("held", "Opaque_t")),
                typename="Box_t",
                dimensions=[20000000],
            ),
        )
        assert checks(bag) == ["schema"]
        assert "'V' has 20000000 elements; DDD carries at most 10000000" in messages(bag)

    def test_a_type_of_more_leaves_than_the_outputs_carry_is_refused_where_it_is_declared(
        self, tree: Path
    ) -> None:
        """Twenty rungs of diamond: 1 048 576 leaves out of a types file of sixty lines.

        Counted over the nesting graph rather than by spreading an instance out, which is
        what makes the answer immediate: every rung is counted once, where walking the
        routes an instance takes would be the two-to-the-depth the ladder is built to be.
        Before the count, ``ddd check`` on this project took the best part of a minute and
        then reported a million perfectly consistent leaves.

        At ``L3_t`` rather than at the ``L0_t`` the variable names, for the reason the
        nesting cap reports at the type that crosses it: a rung doubles the rung below it,
        so ``L4_t`` is 65 536 leaves and still within the limit while ``L3_t`` is 131 072 and
        is the innermost type that is already over it. Every rung above it is over it for
        that same reason and is dropped without a finding of its own.
        """
        dictionary, bag = run_analysis(tree, self.files(*ladder(20), typename="L0_t"))
        assert checks(bag) == ["schema"]
        rendered = first(bag).render()
        assert "types.ddd.json#types[9]" in rendered
        assert "structure 'L3_t' has 131072 leaves; DDD carries at most 100000" in rendered
        assert dictionary is not None
        assert not dictionary.instances

    def test_a_type_nesting_the_offender_is_dropped_without_a_second_finding(
        self, tree: Path
    ) -> None:
        """One mistake, one finding, at the innermost type that is already over the limit.

        A type nesting it has at least as many leaves for exactly the same reason, so it
        takes the cause of the type it nests rather than making one of its own - which holds
        for the rungs of the ladder above ``L3_t`` and for the ``Wrap_t`` declared over the
        whole of it alike. A variable of any of them is dropped.
        """
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json", "a.ddd.json"),
                "types.ddd.json": types(*ladder(20), struct("Wrap_t", nest("held", "L0_t"))),
                "a.ddd.json": component(
                    "A",
                    declare("local", "V", typename="L0_t"),
                    declare("local", "W", typename="Wrap_t"),
                ),
            },
        )
        assert checks(bag) == ["schema"]
        assert "structure 'L3_t' has 131072 leaves" in messages(bag)
        assert dictionary is not None
        assert not dictionary.instances


class TestInfiniteDerivedLimits:
    """A datatype and conversion pair whose derived limits are not finite is refused.

    The pair is refused as ``schema`` at its ``conversion`` key, on each of the three places
    it can be written; the definition path is covered in ``test_analysis.py``. Resolving it
    instead used to overflow the limits into infinity, which aborted the whole run.
    """

    def test_on_a_scalar_type(self, tree: Path) -> None:
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json", "a.ddd.json"),
                "types.ddd.json": types(
                    scalar("Huge_t", "float64", conversion={"factor": 1.8}),
                    scalar("Fine_t", "uint8"),
                ),
                "a.ddd.json": component(
                    "A",
                    declare("local", "V", typename="Huge_t"),
                    declare("local", "W", typename="Fine_t"),
                ),
            },
        )
        assert checks(bag) == ["schema"]
        rendered = first(bag).render()
        assert "types[0].conversion" in rendered
        assert "the limits derived from 'float64' and this conversion are not finite" in rendered
        # The variable naming the refused type is dropped; the run resolves the rest.
        assert dictionary is not None
        assert [entry.name for entry in dictionary.objects] == ["W"]

    def test_on_a_structure_member(self, tree: Path) -> None:
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json", "a.ddd.json"),
                "types.ddd.json": types(
                    struct(
                        "S_t",
                        val("ok", "uint8"),
                        val("big", "float64", conversion={"offset": -1.0, "factor": 1.8}),
                    ),
                ),
                "a.ddd.json": component("A", declare("output", "V", typename="S_t")),
            },
        )
        assert checks(bag) == ["schema"]
        rendered = first(bag).render()
        assert "types[0].members[1].conversion" in rendered
        assert dictionary is not None
        assert not dictionary.instances
        assert not dictionary.leaves


class TestNamingAType:
    """A declaration whose ``datatype`` names a type the project declares.

    One key names a type everywhere, so this is the same key a structure member uses. What the
    analysis does with it is fill the declaration in and hand an ordinary definition on, which
    is why nothing downstream - the comparison tables, the backends, ``compare`` - had to learn
    anything about types at all.
    """

    def project_with(self, tree: Path, *entries: dict[str, Any], **definition: Any) -> Any:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json", "a.ddd.json"),
                "types.ddd.json": types(*entries),
                "a.ddd.json": component(
                    "A", declare("local", "X", **{"typename": "Speed_t", **definition})
                ),
            },
        )
        return bag

    def test_a_scalar_type_fills_in_what_it_fixes(self, tree: Path) -> None:
        """The point of the feature: agreement by naming rather than by copying.

        Three components consuming an engine speed used to write the datatype, the unit, the
        scaling and the limits out in full and leave DDD to notice when one of them was wrong.
        Naming ``Speed_t`` leaves nothing to disagree about.
        """
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json", "a.ddd.json", "b.ddd.json"),
                "types.ddd.json": types(
                    scalar(
                        "Speed_t",
                        "uint16",
                        unit="rpm",
                        conversion={"factor": 0.25},
                        limits={"min": 0, "max": 8000},
                    )
                ),
                "a.ddd.json": component("A", declare("output", "EngSpd", typename="Speed_t")),
                "b.ddd.json": component("B", declare("input", "EngSpd", typename="Speed_t")),
            },
        )
        assert checks(bag) == []
        assert dictionary is not None
        (engine_speed,) = dictionary.objects
        assert engine_speed.datatype.value == "uint16"
        assert engine_speed.unit == "rpm"
        assert engine_speed.conversion.describe() == "linear(factor=0.25, offset=0)"
        assert engine_speed.limits.as_tuple() == (0, 8000)

    def test_a_scalar_type_may_leave_its_limits_to_be_derived(self, tree: Path) -> None:
        """A type states what it wants to state; the rest follows as it does for any object."""
        bag = self.project_with(tree, scalar("Speed_t", "uint8", unit="rpm"))
        assert checks(bag) == []

    def test_a_name_no_file_declares_is_reported_where_it_is_written(self, tree: Path) -> None:
        """Which is also where a typo in a base datatype now lands.

        One key naming a type is what costs this: ``uint166`` is no longer refused by the
        contract as it is typed, because it is a perfectly well formed *name*. It is caught
        here instead, at the same pointer and with a message that says what was looked for.
        """
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X", typename="Nowhere_t")),
            },
        )
        assert checks(bag) == ["unknown-type"]
        rendered = first(bag).render()
        assert "neither a base datatype nor a type" in rendered
        assert "a.ddd.json#component.interface[0].definition.typename" in rendered

    def test_restating_what_the_type_fixes_is_refused_by_the_contract(self, tree: Path) -> None:
        """An error rather than an override, so there is one answer to where a unit is written.

        Refused by the definition itself, so it surfaces under ``schema`` with a pointer, the
        same route the member shape rules take - no check identifier of its own.
        """
        bag = self.project_with(tree, scalar("Speed_t", "uint16", unit="rpm"), unit="1/min")
        assert checks(bag) == ["schema"]
        assert "already fixes what this value means" in first(bag).render()

    def test_a_scalar_type_nests_nothing_and_is_not_walked_for_members(self, tree: Path) -> None:
        """The type graph is about structures; a scalar has no members to follow."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json"),
                "types.ddd.json": types(
                    scalar("Speed_t", "uint16"), struct("S_t", val("v", typename="Speed_t"))
                ),
            },
        )
        assert checks(bag) == []

    def test_naming_a_structure_makes_the_variable_one(self, tree: Path) -> None:
        """The variable becomes an instance, and its members become the leaves of the a2l."""
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json", "a.ddd.json"),
                "types.ddd.json": types(struct("Speed_t", val("raw", "uint16", unit="rpm"))),
                "a.ddd.json": component("A", declare("local", "X", typename="Speed_t")),
            },
        )
        assert checks(bag) == []
        assert dictionary is not None
        assert dictionary.objects == ()
        (instance,) = dictionary.instances
        assert (instance.name, instance.type) == ("X", "Speed_t")
        (leaf,) = dictionary.leaves
        assert leaf.path == "X.raw"
        assert leaf.unit == "rpm"


class TestBaseAndDeclaredNamesAreKeptApart:
    """What the two storage keys buy.

    ``datatype`` is one of eleven values, so a mistyped base datatype dies in the contract as
    it is typed; ``typename`` refuses a name spelling a base datatype in any case, so a type
    cannot wear the name of storage it is not; and a name that merely dresses like one -
    ``Int16_t`` - is unambiguous, because the key already says it is declared.
    """

    def test_a_mistyped_base_datatype_is_refused_by_the_contract(self, tree: Path) -> None:
        """Refused where it is typed rather than reported a build later.

        ``uint166`` under ``datatype`` is not one of the eleven, so the editor refuses it as
        it is written instead of a check reporting a type nobody declares a build later.
        """
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X", datatype="uint166")),
            },
        )
        assert checks(bag) == ["schema"]
        rendered = first(bag).render()
        assert "a.ddd.json#component.interface[0].definition.datatype" in rendered
        assert "Input should be" in rendered

    def test_a_typename_spelling_a_base_datatype_is_refused(self, tree: Path) -> None:
        """In any case: a type called ``UINT16`` reads as storage it is not."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X", typename="UINT16")),
            },
        )
        assert checks(bag) == ["schema"]
        assert "spells a base datatype" in first(bag).render()

    def test_storage_is_named_exactly_once_on_a_definition(self, tree: Path) -> None:
        """Both keys at once is a contradiction, refused where it is written."""
        definition = {
            "name": "X",
            "kind": "measurement",
            "volatile": False,
            "datatype": "uint8",
            "typename": "S_t",
        }
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": {
                    "component": {
                        "name": "A",
                        "interface": [{"scope": "local", "definition": definition}],
                    }
                },
            },
        )
        assert checks(bag) == ["schema"]
        assert "storage is named exactly once" in first(bag).render()

    def test_a_name_dressed_like_a_datatype_is_just_a_name(self, tree: Path) -> None:
        """``Int16_t`` under ``typename`` is unambiguous: the key says it is declared."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json", "types.ddd.json"),
                "types.ddd.json": types(scalar("Int16_t", "sint16")),
                "a.ddd.json": component("A", declare("local", "X", typename="Int16_t")),
            },
        )
        assert checks(bag) == []

    def test_the_eleven_ways_to_fail_at_one_key_are_one_finding(self, tree: Path) -> None:
        """A union that is not discriminated fails once per branch; a reader wants it once.

        The branch kept is the first declared, which is why ``datatype`` puts the base
        datatypes first: "one of these eleven" says far more than a regular expression does.
        """
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X", datatype="float3")),
            },
        )
        assert checks(bag) == ["schema"]
        assert "should match pattern" not in first(bag).render()

    def test_a_type_may_not_be_declared_under_a_datatype_like_name(self, tree: Path) -> None:
        """Otherwise it would be a type nothing could ever name: the base datatype wins."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json"),
                "types.ddd.json": types(scalar("uint16", "uint16")),
            },
        )
        assert checks(bag) == ["schema"]

    def test_a_transposition_is_answered_with_the_nearest_name(self, tree: Path) -> None:
        """``unit16`` is not a storage stem, so the contract lets it through as a name.

        What catches it is the check, asking the question this project asks everywhere a name
        does not resolve.
        """
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X", typename="unit16")),
            },
        )
        assert checks(bag) == ["unknown-type"]
        assert "did you mean 'uint16'" in first(bag).render()

    def test_a_misremembered_type_name_suggests_the_declared_one(self, tree: Path) -> None:
        """The declared types are candidates too, which is the more common mistake by far."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json", "a.ddd.json"),
                "types.ddd.json": types(scalar("Speed_t", "uint16", unit="rpm")),
                "a.ddd.json": component("A", declare("local", "X", typename="Sped_t")),
            },
        )
        assert checks(bag) == ["unknown-type"]
        assert "did you mean 'Speed_t'?" in first(bag).render()

    def test_a_name_close_to_nothing_is_left_without_a_guess(self, tree: Path) -> None:
        """A wrong guess reads as authoritative, so no guess is better than a poor one."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component("A", declare("local", "X", typename="Quantity")),
            },
        )
        assert checks(bag) == ["unknown-type"]
        assert "did you mean" not in first(bag).render()


class TestDeclaringAStructure:
    """A variable whose datatype is a structure: one c object, many a2l ones."""

    def resolve(self, tree: Path, *entries: dict[str, Any], **definition: Any) -> Any:
        return run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json", "a.ddd.json"),
                "types.ddd.json": types(*entries),
                "a.ddd.json": component(
                    "A", declare("local", "X", **{"typename": "S_t", **definition})
                ),
            },
        )

    def test_a_structured_variable_is_not_an_object(self, tree: Path) -> None:
        """It has no single datatype and no limits, so it is not one of those.

        Widening ``ResolvedObject`` to hold it would turn every reader of ``datatype`` and
        ``limits`` into a branch, and they are read unconditionally in a dozen places on the
        strength of always being there.
        """
        dictionary, bag = self.resolve(tree, struct("S_t", val("a"), val("b", "uint32")))
        assert checks(bag) == []
        assert dictionary is not None and dictionary.objects == ()
        (instance,) = dictionary.instances
        assert instance.type == "S_t"
        assert [leaf.path for leaf in dictionary.leaves] == ["X.a", "X.b"]

    def test_a_nested_structure_lengthens_the_path(self, tree: Path) -> None:
        dictionary, bag = self.resolve(
            tree, struct("Inner_t", val("v")), struct("S_t", val("inner", typename="Inner_t"))
        )
        assert checks(bag) == []
        assert dictionary is not None
        assert [leaf.path for leaf in dictionary.leaves] == ["X.inner.v"]

    def test_an_array_of_structures_contributes_one_set_per_element(self, tree: Path) -> None:
        """There is no one address describing ``cell[0].v`` and ``cell[1].v`` at the same time.

        An array of *values* is left whole, because a ``MATRIX_DIM`` describes exactly that:
        contiguous elements of one datatype. The members of two structures are a structure
        apart, so no single record can cover both.
        """
        dictionary, bag = self.resolve(
            tree,
            struct("Inner_t", val("v")),
            struct(
                "S_t",
                val("cell", typename="Inner_t", dimensions=[2]),
                val("flat", "uint8", dimensions=[4]),
            ),
        )
        assert checks(bag) == []
        assert dictionary is not None
        assert [leaf.path for leaf in dictionary.leaves] == [
            "X.cell[0].v",
            "X.cell[1].v",
            "X.flat",
        ]
        flat = next(leaf for leaf in dictionary.leaves if leaf.path == "X.flat")
        assert flat.shape == (4,)

    def test_the_variable_itself_may_be_an_array(self, tree: Path) -> None:
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json", "a.ddd.json"),
                "types.ddd.json": types(struct("S_t", val("v"))),
                "a.ddd.json": component("A", declare("local", "X", typename="S_t", dimensions=[2])),
            },
        )
        assert checks(bag) == []
        assert dictionary is not None
        assert [leaf.path for leaf in dictionary.leaves] == ["X[0].v", "X[1].v"]

    def test_a_member_takes_its_meaning_from_the_type_it_names(self, tree: Path) -> None:
        dictionary, bag = self.resolve(
            tree,
            scalar("Speed_t", "uint16", unit="rpm", conversion={"factor": 0.25}),
            struct("S_t", val("engine", typename="Speed_t")),
        )
        assert checks(bag) == []
        assert dictionary is not None
        (leaf,) = dictionary.leaves
        assert (leaf.unit, leaf.datatype.value) == ("rpm", "uint16")
        assert leaf.limits.as_tuple() == (0, 16383.75)

    def test_the_limits_a_scalar_type_states_reach_the_member(self, tree: Path) -> None:
        """Stated on the type once, rather than on every member and variable that uses it."""
        dictionary, bag = self.resolve(
            tree,
            scalar("Speed_t", "uint16", unit="rpm", limits={"min": 0, "max": 8000}),
            struct("S_t", val("engine", typename="Speed_t")),
        )
        assert checks(bag) == []
        assert dictionary is not None
        (leaf,) = dictionary.leaves
        assert leaf.limits.as_tuple() == (0, 8000)

    def test_a_scalar_type_that_states_no_limits_has_them_derived(self, tree: Path) -> None:
        """A type states what it wants to; the rest follows as it does for any other object."""
        dictionary, bag = self.resolve(
            tree,
            scalar("Speed_t", "uint8", unit="rpm"),
            struct("S_t", val("engine", typename="Speed_t")),
        )
        assert checks(bag) == []
        assert dictionary is not None
        (leaf,) = dictionary.leaves
        assert leaf.limits.as_tuple() == (0, 255)

    def test_an_instance_kept_out_of_the_a2l_marks_every_leaf_so(self, tree: Path) -> None:
        """The whole object's answer reaches its members, the way the storage class does.

        A leaf that carried only the member's own opinion split the export decision across two
        records, and only the a2l backend put the halves back together. Everything else read
        one half and believed it: a delivery that stopped exporting a structure compared clean
        against its predecessor while every one of its members left the file.
        """
        dictionary, bag = self.resolve(
            tree, struct("S_t", val("a"), val("b")), a2l={"export": False}
        )
        assert checks(bag) == []
        assert dictionary is not None
        assert [leaf.a2l.export for leaf in dictionary.leaves] == [False, False]

    def test_a_member_may_be_kept_out_of_an_exported_structure(self, tree: Path) -> None:
        """The member's own no still counts; resolving the two is an and, not a replacement."""
        dictionary, bag = self.resolve(
            tree, struct("S_t", val("a", a2l={"export": False}), val("b"))
        )
        assert checks(bag) == []
        assert dictionary is not None
        assert [(leaf.path, leaf.a2l.export) for leaf in dictionary.leaves] == [
            ("X.a", False),
            ("X.b", True),
        ]

    def test_a_leaf_knows_whether_it_is_calibration_data(self, tree: Path) -> None:
        """Taken from the variable: every member of one object has its storage class."""
        dictionary, bag = self.resolve(tree, struct("S_t", val("v")), kind="parameter")
        assert checks(bag) == []
        assert dictionary is not None
        (leaf,) = dictionary.leaves
        assert leaf.is_calibration
        (instance,) = dictionary.instances
        assert instance.is_calibration

    def test_a_member_states_its_own_meaning_when_it_has_one(self, tree: Path) -> None:
        dictionary, bag = self.resolve(
            tree, struct("S_t", val("t", "uint16", unit="ms", limits={"min": 0, "max": 1000}))
        )
        assert checks(bag) == []
        assert dictionary is not None
        (leaf,) = dictionary.leaves
        assert (leaf.unit, leaf.limits.as_tuple()) == ("ms", (0, 1000))

    def test_the_structures_come_out_in_an_order_c_can_be_written_in(self, tree: Path) -> None:
        """Alphabetical order does not do it, and this is the case that proves it.

        ``Sensor_t`` sorts before ``Status_t`` and nests it, so a template looping over the
        list in name order would declare a member of an incomplete type.
        """
        dictionary, bag = self.resolve(
            tree,
            struct("Status_t", val("flag", "uint8")),
            struct("Sensor_t", val("status", typename="Status_t")),
            struct("S_t", val("sensor", typename="Sensor_t")),
        )
        assert checks(bag) == []
        assert dictionary is not None
        assert [entry.name for entry in dictionary.types] == ["Status_t", "Sensor_t", "S_t"]

    def test_the_members_keep_the_order_they_were_written_in(self, tree: Path) -> None:
        """That order is the one the compiler lays out, so nothing may reorder it."""
        dictionary, bag = self.resolve(tree, struct("S_t", val("zulu"), val("alpha"), val("mike")))
        assert checks(bag) == []
        assert dictionary is not None
        (structure,) = dictionary.types
        assert [member.name for member in structure.members] == ["zulu", "alpha", "mike"]

    @pytest.mark.parametrize(
        ("definition", "because"),
        [
            ({"kind": "curve", "axis": "Ax"}, "refers to other objects"),
            ({"init": 3}, "written by the code that starts it"),
        ],
    )
    def test_what_a_structured_declaration_may_not_be(
        self, tree: Path, definition: dict[str, Any], because: str
    ) -> None:
        """Each refused rather than ignored, and located where it is written."""
        _, bag = self.resolve(tree, struct("S_t", val("v")), **definition)
        assert "type-kind" in checks(bag)
        assert because in first(bag).render()

    def test_a_datatype_the_project_declares_is_compared_by_name(self, tree: Path) -> None:
        """The message names the mistake instead of one of its symptoms."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json", "a.ddd.json", "b.ddd.json"),
                "types.ddd.json": types(struct("A_t", val("v")), struct("B_t", val("v"))),
                "a.ddd.json": component("A", declare("output", "X", typename="A_t")),
                "b.ddd.json": component("B", declare("input", "X", typename="B_t")),
            },
        )
        assert "definition-mismatch" in checks(bag)
        assert "datatype: B_t != A_t" in messages(bag)


class TestAnUnownedStructure:
    """``missing-producer`` relaxed: the project wide file defines what nobody owns.

    SPEC section 5.1: the objects no component owns arise whenever the check is relaxed, and
    the project wide file defines them like any other. A structured variable used to fall out
    of that group - the consumer headers declared it ``extern`` over storage that nowhere
    existed, while the a2l went on describing its member paths.
    """

    def resolved(self, tree: Path) -> Any:
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("Device", "types.ddd.json", "reader.ddd.json"),
                "types.ddd.json": types(struct("S_t", val("raw", "uint16", dimensions=[4]))),
                "reader.ddd.json": component(
                    "Reader",
                    declare("input", "Inlet", typename="S_t"),
                    declare("input", "Speed", "uint16"),
                    description="a component",
                ),
            },
            severities=["missing-producer=warning"],
        )
        assert dictionary is not None, [d.render() for d in bag]
        assert not bag.has_errors, [d.render() for d in bag]
        return dictionary

    def test_the_model_puts_the_instance_in_the_unresolved_group(self, tree: Path) -> None:
        from ddd.backends import COptions
        from ddd.backends.c.model import UNRESOLVED_GROUP, build_code_model

        model = build_code_model(self.resolved(tree), COptions(), "test")
        unresolved = next(group for group in model.groups if group.name == UNRESOLVED_GROUP)
        assert {variable.name for variable in unresolved.variables} == {"Inlet", "Speed"}

    def test_the_project_wide_file_defines_it_like_any_other(self, tree: Path) -> None:
        dictionary = self.resolved(tree)
        files = {f.path.name: f.content for f in render_files(dictionary, tree / "gen")}
        assert "S_t Inlet;" in files["ddd_globals.c"]
        assert "uint16_t Speed;" in files["ddd_globals.c"]
        # The consumer header still declares both, which is what made a missing definition a
        # link error; and the a2l member paths now name storage that exists.
        assert "extern S_t Inlet;" in files["Reader.h"]
        assert 'SYMBOL_LINK "Inlet.raw" 0' in files["Device.a2l"]


class TestTheDescriptionsOwnSpelling:
    """The views carry the type in the dictionary's vocabulary next to the ISO one.

    A platform whose header already spells the types - AUTOSAR's ``Platform_Types.h`` uses
    exactly the datatype names - renders ``datatype`` where the example templates render
    ``c_type``, and needs no mapping in its templates at all.
    """

    def test_every_view_offers_both_spellings(self, tree: Path) -> None:
        from ddd.backends import COptions
        from ddd.backends.c.model import build_code_model

        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "t.ddd.json", "a.ddd.json"),
                "t.ddd.json": types(
                    {"type": "external", "name": "Drv_t", "header": "drv.h"},
                    struct(
                        "S_t",
                        val("raw", "uint16"),
                        val("on", "boolean"),
                        val("drv", typename="Drv_t"),
                    ),
                ),
                "a.ddd.json": component(
                    "A",
                    declare("local", "Speed", "uint16"),
                    declare("local", "Inlet", typename="S_t"),
                ),
            },
        )
        assert dictionary is not None and not bag.has_errors, [d.render() for d in bag]

        model = build_code_model(dictionary, COptions(), "test")
        variables = {v.name: v for group in model.groups for v in group.variables}
        assert (variables["Speed"].c_type, variables["Speed"].datatype) == ("uint16_t", "uint16")
        # A structured variable and the non-base members spell both fields the same way,
        # because their spelling was the project's own to begin with.
        assert (variables["Inlet"].c_type, variables["Inlet"].datatype) == ("S_t", "S_t")
        members = {m.name: m for s in model.structures for m in s.members}
        assert (members["raw"].c_type, members["raw"].datatype) == ("uint16_t", "uint16")
        assert (members["on"].c_type, members["on"].datatype) == ("bool", "boolean")
        assert (members["drv"].c_type, members["drv"].datatype) == ("Drv_t", "Drv_t")


class TestGeneratingAStructure:
    """What a structured declaration turns into: one c object, an a2l object per member."""

    def render(self, tree: Path, *entries: dict[str, Any], **definition: Any) -> dict[str, str]:
        files = {
            "project.ddd.json": project("Device", "types.ddd.json", "a.ddd.json"),
            "types.ddd.json": types(*entries),
            "a.ddd.json": component(
                "A",
                declare("local", "X", **{"typename": "S_t", **definition}),
                description="a component",
            ),
        }
        dictionary, bag = run_analysis(tree, files)
        assert dictionary is not None, [d.render() for d in bag]
        assert not bag.has_errors, [d.render() for d in bag]
        rendered = render_files(dictionary, tree / "gen")
        return {file.path.name: file.content for file in rendered}

    def test_the_types_header_declares_the_structure(self, tree: Path) -> None:
        files = self.render(
            tree,
            struct(
                "S_t",
                val("plain", "uint16"),
                val("table", "uint8", dimensions=[4]),
                {
                    "name": "flag",
                    "member": "bits",
                    "datatype": "uint16",
                    "bits": 1,
                    "conversion": {},
                },
            ),
        )
        header = files["ddd_types.h"]
        assert "typedef struct" in header
        assert "uint16_t plain;" in header
        assert "uint8_t table[4];" in header
        # The width goes after the declarator, not after the type: a rule about c, which is
        # why the model composes the whole declaration rather than leaving it to a template.
        assert "uint16_t flag : 1;" in header
        assert "} S_t;" in header

    def test_a_nested_structure_is_declared_before_the_one_that_holds_it(self, tree: Path) -> None:
        """c needs it complete first, and the name order would have put it second."""
        files = self.render(
            tree,
            struct("Status_t", val("f", "uint8")),
            struct("S_t", val("status", typename="Status_t")),
        )
        header = files["ddd_types.h"]
        assert header.index("} Status_t;") < header.index("Status_t status;")

    def test_the_variable_declares_like_any_other(self, tree: Path) -> None:
        files = self.render(tree, struct("S_t", val("v")))
        assert "S_t X;" in files["ddd_globals.c"]
        assert "extern S_t X;" in files["ddd_globals.h"]

    def test_a_calibratable_structure_is_const_volatile(self, tree: Path) -> None:
        """The qualifier belongs to the whole object; a member cannot differ from it."""
        files = self.render(tree, struct("S_t", val("v")), kind="parameter", volatile=True)
        assert "const volatile S_t X;" in files["ddd_globals.c"]

    def test_every_member_becomes_an_a2l_object_at_its_own_path(self, tree: Path) -> None:
        """Flattened rather than described as an a2l structure.

        The name is the c expression that reads the member, so the a2l, the generated c and a
        map file all spell one thing one way.
        """
        files = self.render(
            tree,
            struct("Inner_t", val("v", "uint16", unit="degC")),
            struct("S_t", val("inner", typename="Inner_t"), val("table", "uint8", dimensions=[4])),
        )
        content = files["Device.a2l"]
        assert "/begin MEASUREMENT X.inner.v" in content
        assert 'SYMBOL_LINK "X.inner.v" 0' in content
        assert "/begin MEASUREMENT X.table" in content
        assert "MATRIX_DIM 4 1 1" in content
        # The group has to name the members, since there is no record called 'X' to name.
        assert "X.inner.v" in content.split("/begin GROUP")[1]

    def test_a_calibratable_member_is_a_characteristic(self, tree: Path) -> None:
        files = self.render(
            tree,
            struct("S_t", val("gain", "uint16"), val("table", "uint8", dimensions=[2])),
            kind="parameter",
        )
        content = files["Device.a2l"]
        assert "/begin CHARACTERISTIC X.gain" in content
        assert "VALUE 0x00000000" in content
        assert "/begin CHARACTERISTIC X.table" in content
        assert "VAL_BLK 0x00000000" in content

    def test_a_bitfield_member_reaches_no_a2l(self, tree: Path) -> None:
        """``&s.flag`` does not compile, so no build can report where that member is.

        A ``SYMBOL_LINK`` carries a byte offset and has nowhere to put a bit position; leaving
        the mask out would claim the whole word and writing zero would claim nothing. Both are
        wrong answers dressed as output, so the member waits for a build that can say.
        """
        files = self.render(
            tree,
            struct(
                "S_t",
                val("plain", "uint16"),
                {
                    "name": "flag",
                    "member": "bits",
                    "datatype": "uint16",
                    "bits": 1,
                    "conversion": {},
                },
            ),
        )
        content = files["Device.a2l"]
        assert "X.plain" in content
        assert "X.flag" not in content

    def test_a_member_may_be_kept_out_of_the_a2l_on_its_own(self, tree: Path) -> None:
        files = self.render(
            tree,
            struct("S_t", val("shown"), val("hidden", "uint16", a2l={"export": False})),
        )
        content = files["Device.a2l"]
        assert "X.shown" in content
        assert "X.hidden" not in content

    def test_keeping_the_whole_object_out_keeps_every_member_out(self, tree: Path) -> None:
        files = self.render(tree, struct("S_t", val("v")), a2l={"export": False})
        assert "X.v" not in files["Device.a2l"]

    def test_a_structured_output_nobody_reads_is_reported(self, tree: Path) -> None:
        """The same finding any other unread output gets, and for the same reason."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json", "a.ddd.json"),
                "types.ddd.json": types(struct("S_t", val("v"))),
                "a.ddd.json": component("A", declare("output", "X", typename="S_t")),
            },
        )
        assert checks(bag) == ["unused-output"]

    def test_the_stdint_include_counts_the_members(self, tree: Path) -> None:
        """A project whose only integer sits inside a structure still needs the header.

        Counting only the plain objects left a header that spelled ``uint16_t`` and never
        included ``<stdint.h>`` - a generated file that does not compile.
        """
        files = self.render(tree, struct("S_t", val("v", "uint16")))
        assert "#include <stdint.h>" in files["ddd_types.h"]


class TestTypeNamesInTheCNamespace:
    """Every declared type becomes a typedef, which c keeps with the variables at file scope."""

    def test_a_type_named_after_a_c_keyword_is_refused(self, tree: Path) -> None:
        """A structure called ``register`` generates a header that does not compile."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json"),
                "types.ddd.json": types(struct("register", val("v"))),
            },
        )
        assert checks(bag) == ["reserved-identifier"]
        assert "reserved by the c language" in first(bag).render()

    def test_a_variable_may_not_share_a_name_with_a_type(self, tree: Path) -> None:
        """The same argument the enum names already go through, one level along."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json", "a.ddd.json"),
                "types.ddd.json": types(scalar("Speed", "uint16")),
                "a.ddd.json": component("A", declare("local", "Speed", "uint16")),
            },
        )
        assert "name-collision" in checks(bag)
        assert "type declared here" in first(bag).render()

    def test_a_member_named_after_a_c_keyword_is_refused(self, tree: Path) -> None:
        """``uint16_t int;`` inside the generated struct compiles no better than outside it."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json"),
                "types.ddd.json": types(struct("S_t", val("int"))),
            },
        )
        assert checks(bag) == ["reserved-identifier"]
        finding = first(bag)
        assert "member 'int' of structure 'S_t' is reserved by the c language" in finding.render()
        assert finding.location.pointer == "types[0].members[0].name"

    def test_a_member_of_a_nested_structure_is_screened_as_well(self, tree: Path) -> None:
        """Every structure of the types file is walked, so nesting hides no member.

        The finding points at the member's own name in its file, however deep the structure
        sits in the object tree.
        """
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json"),
                "types.ddd.json": types(
                    struct("Outer_t", nest("inner", "Inner_t")),
                    struct("Inner_t", val("__x")),
                ),
            },
        )
        assert checks(bag) == ["reserved-identifier"]
        finding = first(bag)
        assert "member '__x' of structure 'Inner_t'" in finding.render()
        assert finding.location.pointer == "types[1].members[0].name"


class TestStructuresReachEverythingElse:
    """A structured variable is an object to the rest of the tool, not a special case."""

    def project(self, tree: Path) -> Any:
        return run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json", "a.ddd.json"),
                "types.ddd.json": types(
                    struct(
                        "S_t",
                        val("plain", "uint16", unit="rpm"),
                        {
                            "name": "mode",
                            "member": "bits",
                            "datatype": "uint8",
                            "bits": 2,
                            "conversion": {
                                "kind": "enum",
                                "name": "Mode_t",
                                "enumerators": [{"name": "M_OFF", "value": 0}],
                            },
                        },
                    )
                ),
                "a.ddd.json": component("A", declare("local", "X", typename="S_t")),
            },
        )

    def test_an_enum_a_member_names_reaches_the_types_header(self, tree: Path) -> None:
        """Its enumerators are c identifiers like any others, and need the same typedef.

        Registering it here is also what screens its enumerators against every other name the
        project takes; a member's enum used to reach the a2l and nothing else.
        """
        dictionary, bag = self.project(tree)
        assert checks(bag) == []
        assert dictionary is not None
        assert [enum.name for enum in dictionary.enums] == ["Mode_t"]

    def test_a_structured_object_counts_for_name_similar(self, tree: Path) -> None:
        """A measurement ``sensor`` beside a structured ``Sensor`` is exactly the confusion
        the check names, and it fires once, on the later of the two names."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json", "a.ddd.json"),
                "types.ddd.json": types(struct("S_t", val("v"))),
                "a.ddd.json": component(
                    "A",
                    declare("local", "Sensor", typename="S_t"),
                    declare("local", "sensor", "uint16"),
                ),
            },
        )
        assert checks(bag) == ["name-similar"]
        assert "'sensor' and 'Sensor' differ only in upper/lower case" in messages(bag)

    def test_two_structured_objects_differing_only_in_case_are_reported(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json", "a.ddd.json"),
                "types.ddd.json": types(struct("S_t", val("v"))),
                "a.ddd.json": component(
                    "A",
                    declare("local", "Inlet", typename="S_t"),
                    declare("local", "inlet", typename="S_t"),
                ),
            },
        )
        assert checks(bag) == ["name-similar"]
        assert "'inlet' and 'Inlet' differ only in upper/lower case" in messages(bag)

    def test_the_members_are_counted_and_listed_as_objects(self, tree: Path) -> None:
        """A summary that counted only the plain objects told a project of two that it had none."""
        dictionary, _ = self.project(tree)
        assert dictionary is not None
        assert [entry.name for entry in dictionary.listed] == ["X.mode", "X.plain"]

    def test_a_delivery_that_drops_a_structure_does_not_pass_unnoticed(self, tree: Path) -> None:
        """The one thing ``ddd compare`` exists to prevent.

        The members are compared as the objects they are: leaving them out of the comparison
        made a delivery that dropped every structure look identical to the one before it.
        """
        from ddd.compare import compare
        from ddd.diagnostics import DiagnosticBag

        dictionary, _ = self.project(tree)
        assert dictionary is not None
        stripped = dictionary.model_copy(update={"instances": (), "leaves": ()})
        bag = DiagnosticBag()
        compare(dictionary, stripped, bag)
        assert {finding.check for finding in bag} == {"removed-unused-object"}
        assert "X.plain" in messages(bag)

    def test_a_delivery_that_drops_a_structure_from_the_a2l_is_reported(self, tree: Path) -> None:
        """Turning ``export`` off on the whole object empties it out of the file.

        The instance itself is not a record - it reaches the a2l as its members - so the
        comparison never sees it, and the answer has to travel on the leaves or not at all.
        """
        from ddd.compare import compare
        from ddd.diagnostics import DiagnosticBag

        def delivery(where: Path, **definition: Any) -> Any:
            resolved, _ = run_analysis(
                where,
                {
                    "project.ddd.json": project("P", "types.ddd.json", "a.ddd.json"),
                    "types.ddd.json": types(struct("S_t", val("plain", "uint16", unit="rpm"))),
                    "a.ddd.json": component(
                        "A", declare("local", "X", **{"typename": "S_t", **definition})
                    ),
                },
            )
            return resolved

        before = delivery(tree / "before")
        after = delivery(tree / "after", a2l={"export": False})
        assert before is not None and after is not None
        bag = DiagnosticBag()
        compare(before, after, bag)
        assert "changed-a2l" in {finding.check for finding in bag}
        assert "export: true -> false" in messages(bag)

    def test_a_member_that_changes_datatype_is_an_interface_change(self, tree: Path) -> None:
        from ddd.compare import compare
        from ddd.diagnostics import DiagnosticBag
        from ddd.models import Datatype

        dictionary, _ = self.project(tree)
        assert dictionary is not None
        widened = dictionary.model_copy(
            update={
                "leaves": tuple(
                    leaf.model_copy(update={"datatype": Datatype.UINT32})
                    if leaf.path == "X.plain"
                    else leaf
                    for leaf in dictionary.leaves
                )
            }
        )
        bag = DiagnosticBag()
        compare(dictionary, widened, bag)
        assert "changed-interface" in {finding.check for finding in bag}

    def test_a_member_states_no_initial_value_and_refers_to_nothing(self, tree: Path) -> None:
        """Both are what let a leaf be compared as an ordinary object without a second rule."""
        dictionary, _ = self.project(tree)
        assert dictionary is not None
        leaf = dictionary.comparable["X.plain"]
        assert leaf.init is None
        assert leaf.references == {}


def test_a_leaf_carries_the_identity_of_its_instance(tree: Path) -> None:
    """A leaf has no declaration to carry an id, so it borrows its instance's."""
    dictionary, bag = run_analysis(
        tree,
        {
            "project.ddd.json": project("P", "t.ddd.json", "a.ddd.json"),
            "t.ddd.json": types(struct("S_t", val("value"), val("raw"))),
            "a.ddd.json": component(
                "A", declare("local", "Inlet", typename="S_t", id="k7m2q9xr4t8w")
            ),
        },
    )
    assert dictionary is not None, messages(bag)
    assert {leaf.path for leaf in dictionary.leaves} == {"Inlet.value", "Inlet.raw"}
    assert {leaf.instance_id for leaf in dictionary.leaves} == {"k7m2q9xr4t8w"}


def test_the_dump_carries_and_nulls_instance_and_leaf_identity(tree: Path) -> None:
    """The same rule as a plain object (see test_cli.py), on a structured one.

    An instance with an id dumps it, and the leaves it flattens into borrow it as
    ``instance_id``; an instance with none states ``null`` for the key on itself and on
    every leaf, like any other unstated optional field.
    """
    dictionary, bag = run_analysis(
        tree,
        {
            "project.ddd.json": project("P", "t.ddd.json", "a.ddd.json"),
            "t.ddd.json": types(struct("S_t", val("value"))),
            "a.ddd.json": component(
                "A",
                declare("local", "Inlet", typename="S_t", id="k7m2q9xr4t8w"),
                declare("local", "Outlet", typename="S_t"),
            ),
        },
    )
    assert dictionary is not None, messages(bag)
    dumped = json.loads(dictionary.model_dump_json())
    instances = {entry["name"]: entry for entry in dumped["instances"]}
    leaves = {entry["path"]: entry for entry in dumped["leaves"]}
    assert instances["Inlet"]["id"] == "k7m2q9xr4t8w"
    assert leaves["Inlet.value"]["instance_id"] == "k7m2q9xr4t8w"
    assert instances["Outlet"]["id"] is None
    assert leaves["Outlet.value"]["instance_id"] is None


class TestMemberStorageChecks:
    def enum_member(self) -> dict[str, Any]:
        return {
            "name": "mode",
            "member": "value",
            "datatype": "uint8",
            "conversion": {
                "kind": "enum",
                "name": "Mode_t",
                "enumerators": {"OFF": 0, "HUGE_ONE": 300},
            },
        }

    def wide_member(self) -> dict[str, Any]:
        return {
            "name": "wide",
            "member": "value",
            "datatype": "uint8",
            "conversion": {"kind": "identity"},
            "limits": {"min": 0, "max": 1000},
        }

    def test_an_enumerator_that_does_not_fit_the_member_is_refused(self, tree: Path) -> None:
        """The check a plain declaration gets; a member is storage of the same width."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "t.ddd.json", "a.ddd.json"),
                "t.ddd.json": types(struct("S_t", self.enum_member())),
                "a.ddd.json": component("A", declare("local", "X", typename="S_t")),
            },
        )
        assert "init-invalid" in checks(bag)
        assert "HUGE_ONE=300" in messages(bag)
        assert "uint8" in messages(bag)

    def test_member_limits_beyond_the_datatype_are_reported(self, tree: Path) -> None:
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "t.ddd.json", "a.ddd.json"),
                "t.ddd.json": types(struct("S_t", self.wide_member())),
                "a.ddd.json": component("A", declare("local", "X", typename="S_t")),
            },
        )
        assert "limits-out-of-range" in checks(bag)
        assert "[0, 1000] exceed the range [0, 255]" in messages(bag)


class TestScalarTypeChecks:
    """What a scalar type fixes is answered at the type, the way a member's keys are.

    A declaration naming a scalar type restates none of what the type fixes - the contract
    refuses it - so a finding about the unit, the conversion or the limits at a declaration
    would point at a key that is not written there, once per component naming the type, and
    a type nobody has started naming yet would be checked by nobody at all.
    """

    def wide(self) -> dict[str, Any]:
        """``Pct_t`` offers 300 percent of a ``uint8`` that stops counting at 255."""
        return scalar("Pct_t", "uint8", limits={"min": 0, "max": 300})

    def test_the_limits_are_reported_once_where_the_type_is_declared(self, tree: Path) -> None:
        """Two components naming the type are two copies of one mistake in a third file."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json", "a.ddd.json", "b.ddd.json"),
                "types.ddd.json": types(self.wide()),
                "a.ddd.json": component("A", declare("local", "X", typename="Pct_t")),
                "b.ddd.json": component("B", declare("local", "Y", typename="Pct_t")),
            },
        )
        assert checks(bag) == ["limits-out-of-range"]
        finding = first(bag)
        assert finding.location.path.name == "types.ddd.json"
        assert finding.location.pointer == "types[0].limits"
        assert "[0, 300] exceed the range [0, 255]" in finding.render()

    def test_a_type_nobody_names_yet_is_checked_all_the_same(self, tree: Path) -> None:
        """A type is written before the first component names it, which is when to say so."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json"),
                "types.ddd.json": types(self.wide()),
            },
        )
        assert checks(bag) == ["limits-out-of-range"]
        assert first(bag).location.pointer == "types[0].limits"

    def test_an_enumerator_is_screened_at_the_conversion_declaring_it(self, tree: Path) -> None:
        """As a member's enumerators are: the enum reaches the types header either way."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json"),
                "types.ddd.json": types(
                    scalar(
                        "Mode_t",
                        "uint8",
                        conversion={
                            "kind": "enum",
                            "name": "Mode_e",
                            "enumerators": {"register": 0, "RUNNING": 1},
                        },
                    )
                ),
            },
        )
        assert checks(bag) == ["reserved-identifier"]
        finding = first(bag)
        assert "enumerator 'register' of enum 'Mode_e' is reserved" in finding.render()
        assert finding.location.pointer == "types[0].conversion"

    def test_a_declaration_still_answers_for_its_own_init(self, tree: Path) -> None:
        """The ``init`` belongs to the variable rather than to the type, so it stays here."""
        _, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json", "a.ddd.json"),
                "types.ddd.json": types(scalar("Level_t", "uint8")),
                "a.ddd.json": component("A", declare("local", "X", typename="Level_t", init=300)),
            },
        )
        assert checks(bag) == ["init-invalid"]
        finding = first(bag)
        assert "does not fit into uint8" in finding.render()
        assert finding.location.pointer == "component.interface[0].definition.init"

    def test_a_declared_types_enum_reaches_the_types_header(self, tree: Path) -> None:
        """A structure member's enum reaches the a2l as the instance's ``COMPU_VTAB``, so a
        header that omitted the matching ``typedef enum`` would leave the two disagreeing
        about what the name means; a scalar type's own enum is registered on the same terms,
        whether or not anything yet exists to name it.
        """
        mode_t = scalar(
            "Mode_t",
            "uint8",
            conversion={
                "kind": "enum",
                "name": "Mode_e",
                "enumerators": {"MODE_IDLE": 0, "MODE_RUNNING": 1},
            },
        )

        # (a) the type on its own, named by no declaration.
        lone, bag = run_analysis(
            tree / "lone",
            {
                "project.ddd.json": project("P", "types.ddd.json"),
                "types.ddd.json": types(mode_t),
            },
        )
        assert lone is not None, messages(bag)
        header = {f.path.name: f.content for f in render_files(lone, tree / "lone" / "gen")}
        assert "typedef enum" in header["ddd_types.h"]
        assert "Mode_e" in header["ddd_types.h"]

        # (b) a structure member naming the type, with an instance of the structure.
        instantiated, bag = run_analysis(
            tree / "member",
            {
                "project.ddd.json": project("P", "types.ddd.json", "s.ddd.json"),
                "types.ddd.json": types(mode_t, struct("Sensor_t", val("mode", typename="Mode_t"))),
                "s.ddd.json": component("S", declare("local", "X", typename="Sensor_t")),
            },
        )
        assert instantiated is not None, messages(bag)
        header = {
            f.path.name: f.content for f in render_files(instantiated, tree / "member" / "gen")
        }
        assert "typedef enum" in header["ddd_types.h"]
        assert "Mode_e" in header["ddd_types.h"]

    def test_an_inline_enum_disagreeing_with_a_types_enum_is_a_conflict(self, tree: Path) -> None:
        """Silent before 7415032: a type's enum reached no registry for an inline one to
        disagree with. Now it does, and the disagreement is real - the header carries the
        type's spelling while this declaration's own a2l ``COMPU_VTAB`` would carry the other.
        """
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "types.ddd.json", "a.ddd.json"),
                "types.ddd.json": types(
                    scalar(
                        "Mode_t",
                        "uint8",
                        conversion={
                            "kind": "enum",
                            "name": "Mode_e",
                            "enumerators": {"MODE_IDLE": 0, "MODE_RUNNING": 1},
                        },
                    )
                ),
                "a.ddd.json": component(
                    "A",
                    declare(
                        "local",
                        "X",
                        conversion={
                            "kind": "enum",
                            "name": "Mode_e",
                            "enumerators": {"MODE_IDLE": 0, "MODE_RUNNING": 7},
                        },
                    ),
                ),
            },
        )
        assert checks(bag) == ["enum-conflict"]
        finding = first(bag)
        assert finding.location.path.name == "a.ddd.json"
        assert finding.location.pointer == "component.interface[0].definition.conversion"
        note_text, note_location = finding.notes[1]
        assert note_text == "first defined as: MODE_IDLE=0, MODE_RUNNING=1"
        assert note_location.path.name == "types.ddd.json"
        assert note_location.pointer == "types[0].conversion"

        # The registry keeps the type's spelling; the header has no way to carry both.
        assert dictionary is not None, messages(bag)
        header = {f.path.name: f.content for f in render_files(dictionary, tree / "gen")}
        assert "MODE_RUNNING = 1" in header["ddd_types.h"]
        assert "MODE_RUNNING = 7" not in header["ddd_types.h"]
