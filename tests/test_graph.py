"""Tests for the graph of one revision: its modules, and the flows and disagreements between
them - the transport neutral heart of the project screen's canvas.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from ddd.diagnostics import Diagnostic, Location, Severity
from ddd.graph import Disagreement, Flow, Module, graph_of
from ddd.ir import (
    DICTIONARY_FORMAT,
    ComponentDeclaration,
    DataDictionary,
    ResolvedComponent,
    ResolvedObject,
)


def a_module(
    path: str,
    name: str | None = None,
    *,
    loaded: bool = True,
    errors: int = 0,
    warnings: int = 0,
    infos: int = 0,
) -> Module:
    """A node of the graph, named after its file's stem by default - the way a file that did
    not load is named, since it has no component to be named after."""
    return Module(
        PurePosixPath(path), name or PurePosixPath(path).stem, loaded, errors, warnings, infos
    )


def a_component(name: str, *declarations: ComponentDeclaration) -> ResolvedComponent:
    return ResolvedComponent(name=name, declarations=declarations)


def declared(name: str, scope: str = "output") -> ComponentDeclaration:
    return ComponentDeclaration(name=name, scope=scope)


def an_object(name: str, owner: str | None, *consumers: str, local: bool = False) -> ResolvedObject:
    """A resolved object naming its owner and its consumers; everything else about it is fixed
    to whatever is simplest, since no graph rule reads it."""
    return ResolvedObject(
        name=name,
        kind="measurement",
        datatype="uint8",
        conversion={"kind": "identity"},
        limits={"min": 0, "max": 255},
        owner=owner,
        consumers=consumers,
        local=local,
    )


def a_dictionary(
    components: tuple[ResolvedComponent, ...] = (), objects: tuple[ResolvedObject, ...] = ()
) -> DataDictionary:
    return DataDictionary(
        format=DICTIONARY_FORMAT, name="P", components=components, objects=objects
    )


def a_finding(
    file: str,
    pointer: str,
    check: str = "definition-mismatch",
    severity: Severity = Severity.ERROR,
    *,
    notes: tuple[tuple[str, Location | None], ...] = (),
    message: str = "they disagree",
) -> tuple[PurePosixPath, Diagnostic]:
    """A finding filed on ``file`` at ``pointer``, paired with its file the way ``graph_of``
    wants findings handed to it."""
    location = Location(path=Path(file), pointer=pointer)
    return PurePosixPath(file), Diagnostic(check, severity, message, location, notes)


def a_note_at(file: str, pointer: str = "") -> tuple[str, Location | None]:
    """A note locating a declaration of ``file``, the shape every disagreement's note has."""
    return ("declared differently here", Location(path=Path(file), pointer=pointer))


class TestFlows:
    """Step 2's rule 1 and rule 2: which pairs of modules a flow joins."""

    def test_a_flow_per_pair(self) -> None:
        a, b = a_module("a.ddd.json", "A"), a_module("b.ddd.json", "B")
        dictionary = a_dictionary(objects=(an_object("Speed", "A", "B"),))
        graph = graph_of(dictionary, [a, b], [])
        assert graph.flows == (
            Flow(PurePosixPath("a.ddd.json"), PurePosixPath("b.ddd.json"), ("Speed",), ()),
        )
        assert graph.flows[0].severity is None

    def test_several_objects_on_one_flow(self) -> None:
        a, b = a_module("a.ddd.json", "A"), a_module("b.ddd.json", "B")
        dictionary = a_dictionary(
            objects=(an_object("Torque", "A", "B"), an_object("Speed", "A", "B"))
        )
        graph = graph_of(dictionary, [a, b], [])
        assert len(graph.flows) == 1
        assert graph.flows[0].objects == ("Speed", "Torque")

    def test_a_local_object_makes_no_flow(self) -> None:
        a, b = a_module("a.ddd.json", "A"), a_module("b.ddd.json", "B")
        dictionary = a_dictionary(objects=(an_object("Internal", "A", local=True),))
        graph = graph_of(dictionary, [a, b], [])
        assert graph.flows == ()

    def test_a_local_object_with_a_consumer_still_makes_no_flow(self) -> None:
        """``local=True`` does not imply empty ``consumers``: a component declaring a local
        object as ``input`` is exactly the ``local-conflict`` the analysis reports, and that
        finding leaves the declaration - and so the consumer - in place."""
        a, b = a_module("a.ddd.json", "A"), a_module("b.ddd.json", "B")
        dictionary = a_dictionary(objects=(an_object("Internal", "A", "B", local=True),))
        graph = graph_of(dictionary, [a, b], [])
        assert graph.flows == ()

    def test_an_unread_object_makes_no_flow(self) -> None:
        a, b = a_module("a.ddd.json", "A"), a_module("b.ddd.json", "B")
        dictionary = a_dictionary(objects=(an_object("Unread", "A"),))
        graph = graph_of(dictionary, [a, b], [])
        assert graph.flows == ()

    def test_an_object_with_no_owner_makes_no_flow(self) -> None:
        a, b = a_module("a.ddd.json", "A"), a_module("b.ddd.json", "B")
        dictionary = a_dictionary(objects=(an_object("Orphan", None, "B"),))
        graph = graph_of(dictionary, [a, b], [])
        assert graph.flows == ()
        assert graph.modules == (a, b)

    def test_both_directions_between_one_pair_make_two_flows(self) -> None:
        a, b = a_module("a.ddd.json", "A"), a_module("b.ddd.json", "B")
        dictionary = a_dictionary(
            objects=(an_object("Speed", "A", "B"), an_object("Torque", "B", "A"))
        )
        graph = graph_of(dictionary, [a, b], [])
        assert [(flow.source, flow.target, flow.objects) for flow in graph.flows] == [
            (PurePosixPath("a.ddd.json"), PurePosixPath("b.ddd.json"), ("Speed",)),
            (PurePosixPath("b.ddd.json"), PurePosixPath("a.ddd.json"), ("Torque",)),
        ]

    def test_a_module_that_did_not_load_takes_part_in_no_flow(self) -> None:
        a, b = a_module("a.ddd.json", "A"), a_module("b.ddd.json", "B")
        broken = a_module("z.ddd.json", loaded=False)
        dictionary = a_dictionary(objects=(an_object("Speed", "A", "B"),))
        graph = graph_of(dictionary, [a, b, broken], [])
        assert graph.modules == (a, b, broken)
        assert graph.flows == (
            Flow(PurePosixPath("a.ddd.json"), PurePosixPath("b.ddd.json"), ("Speed",), ()),
        )

    def test_a_consumer_equal_to_the_owner_is_skipped(self) -> None:
        """A component cannot be its own consumer: an object owned by A that also lists A
        among its consumers still makes only the flow to a real reader."""
        a, b = a_module("a.ddd.json", "A"), a_module("b.ddd.json", "B")
        dictionary = a_dictionary(objects=(an_object("Speed", "A", "A", "B"),))
        graph = graph_of(dictionary, [a, b], [])
        assert [(flow.source, flow.target) for flow in graph.flows] == [
            (PurePosixPath("a.ddd.json"), PurePosixPath("b.ddd.json"))
        ]

    def test_an_owner_naming_no_module_makes_no_flow(self) -> None:
        """Rule 1's other half: a component the dictionary names but no module has is ignored."""
        b = a_module("b.ddd.json", "B")
        dictionary = a_dictionary(objects=(an_object("Speed", "Ghost", "B"),))
        graph = graph_of(dictionary, [b], [])
        assert graph.flows == ()
        assert graph.modules == (b,)

    def test_a_consumer_naming_no_module_makes_no_flow_for_it(self) -> None:
        a, b = a_module("a.ddd.json", "A"), a_module("b.ddd.json", "B")
        dictionary = a_dictionary(objects=(an_object("Speed", "A", "Ghost", "B"),))
        graph = graph_of(dictionary, [a, b], [])
        assert [(flow.source, flow.target) for flow in graph.flows] == [
            (PurePosixPath("a.ddd.json"), PurePosixPath("b.ddd.json"))
        ]


class TestDisagreements:
    """Step 2's rules 3 and 4: which finding colours which flow, and with which object."""

    def test_a_disagreement_colours_its_flow(self) -> None:
        a, b = a_module("a.ddd.json", "A"), a_module("b.ddd.json", "B")
        dictionary = a_dictionary(
            components=(a_component("B", declared("Speed", "input")),),
            objects=(an_object("Speed", "A", "B"),),
        )
        findings = [
            a_finding(
                "b.ddd.json", "component.interface[0].definition", notes=(a_note_at("a.ddd.json"),)
            )
        ]
        graph = graph_of(dictionary, [a, b], findings)
        assert graph.flows[0].disagreements == (
            Disagreement("Speed", "definition-mismatch", Severity.ERROR, "they disagree"),
        )
        assert graph.flows[0].severity is Severity.ERROR

    def test_the_worst_severity_wins(self) -> None:
        a, b = a_module("a.ddd.json", "A"), a_module("b.ddd.json", "B")
        dictionary = a_dictionary(
            components=(a_component("B", declared("Speed", "input")),),
            objects=(an_object("Speed", "A", "B"),),
        )
        findings = [
            a_finding(
                "b.ddd.json",
                "component.interface[0].definition",
                severity=Severity.WARNING,
                notes=(a_note_at("a.ddd.json"),),
                message="storage",
            ),
            a_finding(
                "b.ddd.json",
                "component.interface[0].definition",
                severity=Severity.ERROR,
                notes=(a_note_at("a.ddd.json"),),
                message="definition",
            ),
        ]
        graph = graph_of(dictionary, [a, b], findings)
        assert len(graph.flows[0].disagreements) == 2
        assert graph.flows[0].severity is Severity.ERROR

    def test_a_finding_with_no_note_is_not_a_disagreement(self) -> None:
        a, b = a_module("a.ddd.json", "A"), a_module("b.ddd.json", "B")
        dictionary = a_dictionary(
            components=(a_component("B", declared("Speed", "input")),),
            objects=(an_object("Speed", "A", "B"),),
        )
        findings = [a_finding("b.ddd.json", "component.interface[0].definition")]
        graph = graph_of(dictionary, [a, b], findings)
        assert graph.flows[0].disagreements == ()
        assert graph.flows[0].severity is None

    def test_a_note_pointing_outside_the_modules_is_not_a_disagreement(self) -> None:
        """A note may locate a shared types file, which is never a module of its own."""
        a, b = a_module("a.ddd.json", "A"), a_module("b.ddd.json", "B")
        dictionary = a_dictionary(
            components=(a_component("B", declared("Speed", "input")),),
            objects=(an_object("Speed", "A", "B"),),
        )
        findings = [
            a_finding(
                "b.ddd.json",
                "component.interface[0].definition",
                notes=(a_note_at("types.ddd.json"),),
            )
        ]
        graph = graph_of(dictionary, [a, b], findings)
        assert graph.flows[0].disagreements == ()

    def test_a_note_with_no_location_is_not_a_disagreement(self) -> None:
        """A note can be plain text with nowhere it points, which locates no module either."""
        a, b = a_module("a.ddd.json", "A"), a_module("b.ddd.json", "B")
        dictionary = a_dictionary(
            components=(a_component("B", declared("Speed", "input")),),
            objects=(an_object("Speed", "A", "B"),),
        )
        findings = [
            a_finding(
                "b.ddd.json", "component.interface[0].definition", notes=(("a plain remark", None),)
            )
        ]
        graph = graph_of(dictionary, [a, b], findings)
        assert graph.flows[0].disagreements == ()

    def test_an_unresolved_declaration_index_still_colours_with_no_object(self) -> None:
        a, b = a_module("a.ddd.json", "A"), a_module("b.ddd.json", "B")
        dictionary = a_dictionary(
            components=(a_component("B", declared("Speed", "input"), declared("Torque", "input")),),
            objects=(an_object("Speed", "A", "B"),),
        )
        findings = [
            a_finding(
                "b.ddd.json", "component.interface[9].definition", notes=(a_note_at("a.ddd.json"),)
            )
        ]
        graph = graph_of(dictionary, [a, b], findings)
        disagreement = graph.flows[0].disagreements[0]
        assert disagreement.object is None
        assert graph.flows[0].severity is Severity.ERROR

    def test_a_finding_not_on_a_declaration_still_colours_with_no_object(self) -> None:
        """The pointer resolution can fail before an index is even in view - an empty pointer
        names no ``interface`` entry at all - and the disagreement still carries, unnamed."""
        a, b = a_module("a.ddd.json", "A"), a_module("b.ddd.json", "B")
        dictionary = a_dictionary(
            components=(a_component("B", declared("Speed", "input")),),
            objects=(an_object("Speed", "A", "B"),),
        )
        findings = [a_finding("b.ddd.json", "", notes=(a_note_at("a.ddd.json"),))]
        graph = graph_of(dictionary, [a, b], findings)
        disagreement = graph.flows[0].disagreements[0]
        assert disagreement.object is None

    def test_a_module_with_no_matching_component_still_colours_with_no_object(self) -> None:
        """A loaded module's name reaches a flow through an object's ``owner``/``consumers``,
        which is a separate list from the dictionary's ``components`` - so a name with no
        entry there must not crash the lookup, only leave the object unnamed."""
        a, b = a_module("a.ddd.json", "A"), a_module("b.ddd.json", "B")
        dictionary = a_dictionary(
            components=(a_component("B", declared("Speed", "input")),),
            objects=(an_object("Speed", "A", "B"),),
        )
        findings = [
            a_finding(
                "a.ddd.json", "component.interface[0].definition", notes=(a_note_at("b.ddd.json"),)
            )
        ]
        graph = graph_of(dictionary, [a, b], findings)
        disagreement = graph.flows[0].disagreements[0]
        assert disagreement.object is None

    def test_both_directions_between_one_pair(self) -> None:
        a, b = a_module("a.ddd.json", "A"), a_module("b.ddd.json", "B")
        dictionary = a_dictionary(
            components=(
                a_component("A", declared("Torque", "input")),
                a_component("B", declared("Speed", "input")),
            ),
            objects=(an_object("Speed", "A", "B"), an_object("Torque", "B", "A")),
        )
        findings = [
            a_finding(
                "a.ddd.json", "component.interface[0].definition", notes=(a_note_at("b.ddd.json"),)
            )
        ]
        graph = graph_of(dictionary, [a, b], findings)
        by_pair = {(flow.source, flow.target): flow for flow in graph.flows}
        a_to_b = by_pair[(PurePosixPath("a.ddd.json"), PurePosixPath("b.ddd.json"))]
        b_to_a = by_pair[(PurePosixPath("b.ddd.json"), PurePosixPath("a.ddd.json"))]
        assert a_to_b.disagreements == ()
        assert b_to_a.disagreements == (
            Disagreement("Torque", "definition-mismatch", Severity.ERROR, "they disagree"),
        )


class TestGraphOf:
    """The whole answer: no dictionary, and the order every tuple comes back in."""

    def test_no_dictionary_at_all_still_lists_the_modules(self) -> None:
        a, b = a_module("a.ddd.json", "A"), a_module("b.ddd.json", "B")
        graph = graph_of(None, [b, a], [])
        assert graph.modules == (a, b)
        assert graph.flows == ()

    def test_modules_and_flows_come_back_in_a_deterministic_order(self) -> None:
        a, b, c = (
            a_module("a.ddd.json", "A"),
            a_module("b.ddd.json", "B"),
            a_module("c.ddd.json", "C"),
        )
        dictionary = a_dictionary(objects=(an_object("X", "A", "C"), an_object("Y", "B", "A")))
        graph = graph_of(dictionary, [c, a, b], [])
        assert graph.modules == (a, b, c)
        assert graph.flows == (
            Flow(PurePosixPath("a.ddd.json"), PurePosixPath("c.ddd.json"), ("X",), ()),
            Flow(PurePosixPath("b.ddd.json"), PurePosixPath("a.ddd.json"), ("Y",), ()),
        )
