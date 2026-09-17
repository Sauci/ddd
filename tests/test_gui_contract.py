"""The contract behind ``ddd gui``'s api: the pydantic models of ``src/ddd/gui/contract.py``."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from ddd.gui import contract


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
        """A model reachable from none of the eight endpoints would have no entry here, which
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
