"""The contract behind ``ddd gui``'s api: the pydantic models of ``src/ddd/gui/contract.py``."""

from __future__ import annotations

import inspect

import pytest
from pydantic import BaseModel, ValidationError

from ddd.gui import contract, queries


def _public_models() -> list[type[BaseModel]]:
    """Every model this module declares for the page, its private bases left out."""
    return [
        value
        for value in vars(contract).values()
        if isinstance(value, type)
        and issubclass(value, BaseModel)
        and value.__module__ == contract.__name__
        and not value.__name__.startswith("_")
    ]


class TestApiSchema:
    def test_every_model_declared_here_has_a_defs_entry(self) -> None:
        """A model reachable from none of the nine endpoints would have no entry here, which
        is what turns a model added without a page type into a failure of this suite instead
        of a frontend silently left behind the contract it was supposed to describe."""
        schema = contract.api_schema()
        models = _public_models()
        assert models, "expected contract.py to declare at least one model"
        assert all(model.__name__ in schema["$defs"] for model in models)

    def test_the_document_names_itself_as_the_api_of_a_preview_command(self) -> None:
        schema = contract.api_schema()
        assert schema["title"] == "ddd gui API"
        assert "preview command" in schema["description"]

    def test_the_dictionary_field_does_not_repeat_the_file_formats_definitions(self) -> None:
        """Review finding: ``dictionary`` used to be typed as :class:`ddd.ir.DataDictionary`,
        pulling that model and its 22 nested ones into ``$defs`` a second time, beside the shape
        ``dictionary.ts`` already generates from ``ddd schema dictionary``. Pinned by the tree's
        absence and by the field's own schema, rather than by a count of ``$defs`` that every
        model the api adds would have to bump."""
        schema = contract.api_schema()
        assert "DataDictionary" not in schema["$defs"]
        assert "$ref" not in schema["$defs"]["DictionaryReply"]["properties"]["dictionary"]


class TestRequestsAreStrict:
    """``extra="forbid", strict=True``: what the hand-written ``_changes``/``_operation``/
    ``_single``/``_integer`` used to check is now the model's own configuration."""

    def test_an_unknown_field_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            contract.OpenRequest.model_validate_json('{"path": "a.ddd.json", "extra": 1}')

    def test_a_string_is_not_an_integer(self) -> None:
        with pytest.raises(ValidationError):
            contract.Operation.model_validate_json('{"op": "move", "pointer": "a[0]", "to": "1"}')

    def test_a_boolean_is_not_an_integer(self) -> None:
        """A bool is an int in python, which is exactly why the hand-written check had to name
        it separately from every other non-integer - strict mode already refuses it."""
        with pytest.raises(ValidationError):
            contract.Operation.model_validate_json('{"op": "move", "pointer": "a[0]", "to": true}')

    def test_a_field_left_out_and_one_given_as_null_are_both_accepted(self) -> None:
        left_out = contract.Operation.model_validate_json('{"op": "remove", "pointer": "a"}')
        assert (left_out.raw, left_out.to) == (None, None)
        given_null = contract.Operation.model_validate_json(
            '{"op": "remove", "pointer": "a", "raw": null, "to": null}'
        )
        assert (given_null.raw, given_null.to) == (None, None)

    def test_an_edit_needs_at_least_one_change_and_one_operation(self) -> None:
        with pytest.raises(ValidationError):
            contract.Changes.model_validate_json('{"changes": []}')
        with pytest.raises(ValidationError):
            contract.Change.model_validate_json(
                '{"file": "a", "fingerprint": "x", "operations": []}'
            )


class TestRawIsNeverParsed:
    def test_a_fractional_number_stays_the_text_it_was_typed_as(self) -> None:
        """``1.0`` must not become ``1``: parsed and put back, the trailing zero the author
        typed would be gone before the edit engine - which reads ``1.0`` and ``1`` as two
        different kinds of number - ever saw it."""
        operation = contract.Operation.model_validate_json(
            '{"op": "set", "pointer": "a", "raw": "1.0"}'
        )
        assert operation.raw == "1.0"
        assert isinstance(operation.raw, str)


def _described(model: str) -> dict[str, str]:
    """Each field of ``model`` as the page's types describe it: its docstring, as one line."""
    properties = contract.api_schema()["$defs"][model]["properties"]
    return {
        name: " ".join(field.get("description", "").split()) for name, field in properties.items()
    }


class TestThePageFollowsTheAnalyser:
    """What ``npm run schemas`` turns into the page's own types: the fields an edit and the state
    answer now that an edit is answered once written and its analysis follows."""

    def test_the_state_says_its_version_whether_it_analyses_and_the_edits_it_includes(
        self,
    ) -> None:
        state = contract.api_schema()["$defs"]["State"]
        assert list(state["properties"]) == [
            "revision",
            "version",
            "project",
            "files",
            "counts",
            "statements",
            "failed",
            "refused",
            "undoable",
            "analysing",
            "edits",
        ]
        assert state["required"] == list(state["properties"])
        typed = {name: state["properties"][name]["type"] for name in ("version", "analysing")}
        assert typed == {"version": "integer", "analysing": "boolean"}
        assert state["properties"]["edits"]["type"] == "integer"
        described = _described("State")
        assert described["version"] == (
            "Counts up at every change of what this reply says - an analysis asked for, "
            "published or failed, an edit or an undo written: what a later ``?after=`` waits "
            "past."
        )
        assert described["analysing"] == (
            "Whether an analysis is asked for or running: the findings may be about to change."
        )
        assert described["edits"] == (
            "The last edit or undo this revision's analysis includes - every one numbered up to "
            "it was on disk when the analysis read the files - ``0`` where there is none."
        )

    def test_the_state_says_why_the_last_analysis_failed(self) -> None:
        """14:M7: an analysis that raised was told in the terminal alone, and the page read the
        revision before it, or none, as though nothing had gone wrong."""
        state = contract.api_schema()["$defs"]["State"]
        assert state["properties"]["failed"]["anyOf"] == [{"type": "string"}, {"type": "null"}]
        assert _described("State")["failed"] == (
            "Why the last analysis of the open project raised, in the words the terminal prints "
            "it in - never empty - or ``None`` where it finished: the revision before it stands "
            "meanwhile, ``revision`` being ``0`` where there is none, the next poll asks for "
            "another analysis, and the first to succeed clears it."
        )

    def test_the_state_lists_the_build_records_refused_as_the_start_page_does(self) -> None:
        """14:M11: a record this DDD cannot use was listed on the start page alone, and a project
        opened on the command line was analysed without it in silence."""
        state = contract.api_schema()["$defs"]["State"]
        assert state["properties"]["refused"]["items"] == {"$ref": "#/$defs/RefusedBuild"}
        assert (
            contract.State.model_fields["refused"].annotation == tuple[contract.RefusedBuild, ...]
        )
        assert _described("State")["refused"] == (
            "Every build record the search for builds found and this DDD cannot use - written by "
            "a newer DDD, or naming a check it has not got - with why, sorted by path, as "
            "``GET /api/projects`` lists them: the search this revision's analysis made, so none "
            "before the first. No analysis applies their severities."
        )

    def test_the_revision_is_nought_before_the_open_projects_first_analysis(self) -> None:
        described = _described("State")
        assert described["revision"] == (
            "Counts up from 1 at every analysis this session publishes; ``0`` before the open "
            "project's first analysis, when ``files`` is empty and every count ``0``."
        )
        assert described["project"] == (
            "Absolute, posix-separated path of the open project's description: the one this "
            "revision analysed, or the one its first analysis is reading while ``revision`` is "
            "``0``."
        )

    @pytest.mark.parametrize(
        ("model", "fields"), [("EditReply", ["edit", "files"]), ("UndoReply", ["edit"])]
    )
    def test_an_edit_and_an_undo_answer_the_number_each_took(
        self, model: str, fields: list[str]
    ) -> None:
        reply = contract.api_schema()["$defs"][model]
        assert list(reply["properties"]) == fields
        assert reply["properties"]["edit"]["type"] == "integer"
        taken = "edit" if model == "EditReply" else "undo"
        assert _described(model)["edit"] == (
            f"The number the session gave this {taken}: a revision whose ``edits`` has reached "
            "it includes it."
        )


class TestAnEditSaysWhatARefusalGuaranteesAndWhatAKillCanLeave:
    """What ``npm run schemas`` turns into the page's own type of an edit: an edit was said to be
    made all at once or not at all, which a refusal keeps to and a server killed while it writes
    does not - the files it had renamed stay renamed, and the next server has nothing to say
    about them."""

    def test_an_edit_is_refused_as_a_whole_and_a_kill_can_leave_part_of_one(self) -> None:
        edit = contract.api_schema()["$defs"]["Changes"]
        assert " ".join(edit["description"].split()) == (
            "What ``POST /api/edit`` takes: every file it changes, in one edit that is refused "
            "as a whole."
        )
        assert _described("Changes")["changes"] == (
            "Every file this edit changes. A refusal leaves every one of them as it was, or "
            "names the ones it could not put back; a server killed while it writes - a closed "
            "terminal, ``kill``, a power cut - can leave some of them written and the rest not, "
            "with nothing to undo."
        )


class TestFindingsComeAPageAtATime:
    """What the page reads of a revision's findings now that ``GET /api/state`` counts them and
    ``GET /api/findings`` answers them a page at a time, each with a key of its own."""

    def test_the_state_counts_the_findings_of_each_severity_and_carries_none(self) -> None:
        state = contract.api_schema()["$defs"]["State"]
        assert "findings" not in state["properties"]
        assert _described("State")["counts"] == (
            "How many findings of each severity the revision files, in all: a disagreement once "
            "on each file it concerns, as ``GET /api/findings`` lists them."
        )
        assert contract.State.model_fields["counts"].annotation is contract.FindingCounts

    def test_the_state_counts_each_statement_once_as_ddd_check_does(self) -> None:
        """What the page's lines say (decision 14.3): each finding once, where ``counts`` counts
        a disagreement on each of its files, which the Findings tab's table lists."""
        assert _described("State")["statements"] == (
            "How many findings of each severity the revision makes, in all: each once, however "
            "many files it is filed on, as ``ddd check`` counts them."
        )
        assert contract.State.model_fields["statements"].annotation is contract.FindingCounts

    def test_a_comparison_counts_each_statement_once_as_ddd_compare_does(self) -> None:
        """The Compare tab's line too (decision 14.3): a baseline's disagreement is filed on each
        of its files, and listed so, and is one statement."""
        reply = contract.api_schema()["$defs"]["CompareReply"]
        assert list(reply["properties"]) == [
            "revision",
            "verdict",
            "own_errors",
            "findings",
            "baseline_findings",
            "statements",
            "renames",
        ]
        assert reply["required"] == list(reply["properties"])
        assert _described("CompareReply")["statements"] == (
            "How many findings of each severity ``findings`` and ``baseline_findings`` make, in "
            "all: each once, however many files it is filed on, as ``ddd compare`` counts them."
        )
        assert contract.CompareReply.model_fields["statements"].annotation is (
            contract.FindingCounts
        )

    def test_a_count_says_nothing_of_a_file_it_may_not_be_about(self) -> None:
        """One model counts a file's findings, a module's and a whole revision's: its words are
        true of each, and the field holding it says which."""
        schema = contract.api_schema()["$defs"]["FindingCounts"]
        assert " ".join(schema["description"].split()) == (
            "How many findings of each severity there are - on a file, a module or a whole "
            "revision: the field holding the counts says which."
        )
        assert _described("FindingCounts") == {
            "error": "How many are errors.",
            "warning": "How many are warnings.",
            "info": "How many are informational.",
        }

    def test_a_finding_always_says_its_line_and_column_even_as_null(self) -> None:
        finding = contract.api_schema()["$defs"]["Finding"]
        assert {"line", "column"} <= set(finding["required"])
        assert finding["required"] == list(finding["properties"])
        assert finding["properties"]["line"]["anyOf"] == [{"type": "integer"}, {"type": "null"}]
        assert finding["properties"]["column"]["anyOf"] == [{"type": "integer"}, {"type": "null"}]

    def test_a_listed_finding_is_a_finding_with_a_key(self) -> None:
        defs = contract.api_schema()["$defs"]
        assert list(defs["ListedFinding"]["properties"]) == [*defs["Finding"]["properties"], "key"]
        assert defs["ListedFinding"]["required"] == list(defs["ListedFinding"]["properties"])
        assert _described("ListedFinding")["key"] == (
            "Its file, severity, check, place and words, and which repeat of those it is, "
            "counted over the whole revision in the Findings tab's order: a finding keeps its "
            "key on every page, under every filter, and into the next revision where it stays."
        )

    def test_a_page_says_its_revision_how_many_the_filters_leave_and_where_it_starts(
        self,
    ) -> None:
        reply = contract.api_schema()["$defs"]["FindingsReply"]
        assert list(reply["properties"]) == ["revision", "total", "offset", "findings"]
        assert reply["required"] == list(reply["properties"])
        assert reply["properties"]["findings"]["items"] == {"$ref": "#/$defs/ListedFinding"}
        assert _described("FindingsReply")["total"] == (
            "How many findings the filters leave, in all."
        )

    def test_a_page_is_asked_for_under_four_filters_a_text_among_them(self) -> None:
        """16:I14: the Findings tab's filter is the server's, its rows being the server's pages."""
        query = contract.api_schema()["$defs"]["FindingsQuery"]
        assert list(query["properties"]) == ["offset", "limit", "severity", "file", "check", "text"]
        assert "required" not in query
        assert " ".join(query["properties"]["text"]["description"].split()) == (
            "Only the findings whose check, words or file's own name hold this text, whatever its "
            "case; blank, every one."
        )

    def test_both_are_published_beside_every_other_model(self) -> None:
        assert {"FindingsReply", "ListedFinding"} <= set(contract.__all__)


class TestAFindingLeadsToAPanelThatListsIt:
    """14:M8: what the panels a finding leads to list, which the page's types publish."""

    def test_the_values_grid_lists_the_findings_at_every_producer_s_init(self) -> None:
        """A grid two declarations produce has no one file and listed nothing, though a finding
        at either producer's ``init`` leads there."""
        assert _described("ValuesReply")["findings"] == (
            "Every finding filed at the ``init`` of a declaration producing the object - of each "
            "one, where several do and ``file`` is ``None`` - which is where a finding at a "
            "producer's ``init`` leads; a reader's leads to the variable's panel instead."
        )


def _said(model: str) -> str:
    """What ``model`` says of itself in the page's types: its docstring, as one line."""
    return " ".join(contract.api_schema()["$defs"][model].get("description", "").split())


def _flat(text: str | None) -> str:
    return " ".join((text or "").split())


class TestTheContractSaysWhatHolds:
    """14:M15: sentences of the contract, and of the module answering it, that were untrue at the
    head, as the page's types publish them."""

    def test_a_file_loaded_where_no_load_error_is_filed_on_it(self) -> None:
        """A missing include is the file it names that did not load, and the description holding
        the entry parsed and matched its shape: ``loaded`` is no longer that."""
        said = _described("SourceFile")["loaded"]
        assert said == (
            "Whether the file loaded: no ``file-not-found``, ``json-syntax``, ``file-kind`` or "
            "``schema`` error is filed on it. The loader reports a file it could not read at the "
            "entry of the ``includes`` naming it, and where an entry names a single file that "
            "error is about it, the description holding the entry staying loaded; an entry "
            "naming several leaves the error on the description."
        )
        assert _described("GraphModule")["loaded"] == (
            "Whether the file loaded, as :attr:`SourceFile.loaded` says."
        )

    def test_a_name_is_what_a_parsed_file_gives_and_not_what_a_loaded_one_does(self) -> None:
        """A file that matched no schema can still state a name, so ``None`` is not told by the
        file not loading."""
        assert _described("SourceFile")["name"] == (
            "Name its description gives it, or ``None`` when it has none: a file that did not "
            "parse has none, and a plugin never does."
        )
        assert _described("OpenProject")["name"] == (
            "Name the project description gives it, or ``None`` when it gives none: a file that "
            "does not parse gives none."
        )
        assert _described("FoundProject")["name"] == (
            "Name its description gives it, or ``None`` when it gives none: a file that does not "
            "parse gives none."
        )
        assert _described("GraphModule")["name"] == (
            "The component's name, or the file's stem when it did not load or states none."
        )

    def test_a_graph_without_a_dictionary_is_any_read_that_reported_an_error(self) -> None:
        assert _described("GraphReply")["dictionary"] == (
            "Whether the revision resolved a dictionary. ``False`` is a read that reported an "
            "error in every run the revision was made from - a plugin that raised, a file that "
            "did not parse or match its shape, a constant declared twice - and it is the only "
            "thing that tells that apart from a project whose modules genuinely share nothing: "
            "both answer their modules and no flows, and spec section 5.6 asks the page to say "
            "so only for the first."
        )

    def test_a_finding_says_where_it_leads_and_where_it_leads_nowhere(self) -> None:
        assert _described("Finding")["route"] == (
            "Where pressing this finding leads, or ``None`` when the page has nothing to open "
            "for it: its file is not one the analysis listed, or did not load; it names no place "
            "in a component; or it is in a file that is not a component, at no entry of a unit, "
            "a type, a constant, a section, a raster, the project's includes or a whole file - "
            "or at a place the file no longer holds. The page draws where such a finding is "
            "instead: its line and column where the loader gave them, its ``pointer`` otherwise."
        )
        assert _described("FindingRoute")["name"] == (
            "What the kind opens, by name: the variable, the unit's spelling, the type, the "
            "object whose values grid, the constant, the section or the raster; for a file, the "
            "absolute, posix-separated path of the entry or the file the finding is about - of "
            "the root's own, an entry's :attr:`IncludedEntryReply.key` or one of its "
            ":attr:`~IncludedEntryReply.files`; ``None`` for a component, which the finding's "
            "own ``file`` already names."
        )

    def test_a_comparison_finding_carries_the_route_its_place_has(self) -> None:
        """A plugin's comparison rule files at a place of the project, and is routed as a finding
        there is (``test_a_plugins_comparison_finding_leads_to_the_declaration_it_names``); the
        baseline's own are carried in their own field, which never routes."""
        said = _described("CompareReply")
        assert said["findings"] == (
            "Every finding ``compare`` itself reported, sorted by file: the interface and storage "
            "differences between the two deliveries, and what a plugin's comparison rules file. "
            "The comparison's own are filed on the candidate's project file with an empty "
            "pointer, which leads nowhere (``route: null``); a plugin's may be filed at any "
            "place of the project and carry the route that place has, as any finding does."
        )
        assert said["baseline_findings"].startswith(
            "Every error the baseline's own analysis reported, forwarded here, sorted by file"
        )
        assert (
            "Always carries ``route: null``: a finding is the baseline's"
            in (said["baseline_findings"])
        )

    def test_the_comparison_counts_the_errors_the_state_counts_as_rows(self) -> None:
        """``own_errors`` is ``State.counts``' error, a disagreement once on each file it
        concerns, and not ``State.statements``'."""
        assert _described("CompareReply")["own_errors"] == (
            "How many errors the open project has of its own, which the verdict counts: the "
            "number ``State.counts`` gives for ``error``, a disagreement once on each file it "
            "concerns, and not the one ``State.statements`` gives - so that a disagreement is 2 "
            "here and 1 there. It is a reason for a verdict that refuses a project whose "
            "comparison found nothing, which asks only whether it is above ``0``; ``0`` for a "
            "project with none."
        )

    def test_every_plan_route_but_the_files_tab_s_answers_the_one_plan_reply(self) -> None:
        from ddd.gui.api import ROUTES

        plans = sorted(
            route.path for route in ROUTES if route.path.endswith("-plan") and route.method == "GET"
        )
        assert len(plans) == 11
        said = _said("PlanReply")
        for path in plans:
            if path != "/api/files-plan":
                assert f"``{path.removeprefix('/api/')}``" in said or f"``GET {path}``" in said
        assert said.startswith(
            "What each plan route answers - ``GET /api/unit-plan``, ``type-plan``, "
            "``constant-plan``, ``section-plan``, ``raster-plan``, ``declaration-plan``, "
            "``description-plan``, ``value-plan``, ``cells-plan`` and ``values-plan`` - the "
            "preview of one change of what the route plans."
        )

    def test_a_shared_entry_s_findings_are_the_ones_its_panel_lists(self) -> None:
        """14:M8: a later entry repeating the name is listed on the first's panel, and what a
        declaration is about is left to it."""
        repeated = "the loader's refusal of a later entry repeating its name"
        about = ":data:`ddd.finding_routes.ABOUT_THE_DECLARATION`"
        for model in ("ConstantReply", "SectionReply", "RasterReply"):
            said = _described(model)["findings"]
            assert repeated in said, model
            assert about in said, model
        entry = _described("SharedEntry")["findings"]
        assert repeated in entry
        assert about in entry
        assert repeated in _described("ProjectType")["findings"]

    def test_the_plan_routes_taking_no_action_are_the_four_the_endpoints_list_as_such(self) -> None:
        """``_ENDPOINTS`` says which plan routes read their query as one model per action."""
        from ddd.gui.api import ROUTES

        single = sorted(
            route.path
            for route in ROUTES
            if route.path.endswith("-plan") and not issubclass(route.query, queries._Actions)
        )
        assert single == [
            "/api/cells-plan",
            "/api/description-plan",
            "/api/value-plan",
            "/api/values-plan",
        ]
        source = _flat(inspect.getsource(contract))
        assert (
            "every plan route but description-plan, value-plan, cells-plan and values-plan, the "
            "union of one model per action"
        ) in source

    def test_the_script_that_writes_the_page_s_types_is_named_as_the_file_it_is(self) -> None:
        source = _flat(inspect.getsource(contract))
        assert "gui.scripts.schemas" not in source
        assert source.count("``gui/scripts/schemas.mjs``") == 2

    def test_an_answer_is_a_model_and_a_refusal_is_two_strings(self) -> None:
        from ddd.gui import api

        said = _flat(api.__doc__)
        assert said.startswith(
            "The JSON API of ``ddd gui``: each request answered from the session, as a status "
            "and a body."
        )
        assert (
            "Every request and every answer but a refusal is a model of :mod:`ddd.gui.contract`"
        ) in said
        assert (
            'A refusal is the one body that is no model: ``{"error": code, "message": text}``, '
            "two strings that ``_error`` alone builds, which the page reads as its ``ApiError`` "
            "and ``gui/src/generated/api.ts`` does not declare."
        ) in said
        assert (
            "never hand-assembled into a ``dict``, a refusal alone excepted: "
            '``{"error": code, "message": text}``, two strings no model declares'
        ) in _flat(contract.__doc__)
