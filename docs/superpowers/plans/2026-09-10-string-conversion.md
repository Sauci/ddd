# String Conversion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fourth conversion kind, `{"kind": "string"}`, so that a byte array holding text is declared as text, initialised from a string, checked, compared, and described to the calibration tool as far as the a2l format allows.

**Architecture:** The conversion is a fourth variant of the tagged union in `src/ddd/models/conversion.py`; its rules live beside the enum rule in `src/ddd/models/objects.py` and are shared by definitions, structure members and scalar types. The analysis adds the init checks and the checks for a declaration or member naming a string scalar type. The c backend renders a string init as a literal; the a2l backend writes an `ASCII` characteristic with `NUMBER` for a calibration string and a byte-array `MEASUREMENT` with an `ANNOTATION` for a measured one. The dictionary format becomes 8.

**Tech Stack:** Python 3.12, pydantic v2, jinja2, pytest with a 100% coverage gate, ruff, mypy (strict, pydantic plugin).

**Spec:** `docs/superpowers/specs/2026-09-10-string-conversion-design.md` - the plan argues from it; read it first.

## Global Constraints

- Branch `feature/string-conversion` already exists and tracks `origin`; every task ends with a commit and a `git push`. Stage files by path, never `git add -A`: `docs/superpowers/ASAP2.pdf` is a paid specification, git-ignored, and must never be committed.
- The datatype under a string is `uint8` or `sint8`; the shape is exactly one dimension; no `unit`, no `limits`, no `a2l.format`; the kinds are `measurement` and `value_block`, plus a `value` member and a scalar type. All refused as `schema`. No new check identifier anywhere.
- A string init is printable ASCII, 0x20 to 0x7E, and **shorter than the dimension**; the empty string is allowed; a string init on a non-string object is `init-invalid`.
- The a2l is 1.6.1: a calibration string is `ASCII ... NUMBER n`, no `MATRIX_DIM` beside it; a string measurement is the byte array with `MATRIX_DIM n 1 1` plus an `ANNOTATION` labelled `string`; both use `NO_COMPU_METHOD` and the raw range of the datatype as limits.
- `DICTIONARY_FORMAT` becomes `8`.
- Tests run with a full coverage gate: `pytest` alone fails below 100% line coverage. Use `pytest <file> -q --no-cov -k <name>` while iterating and `pytest -q` (whole suite, with coverage) before every commit. `tests/test_cmake.py` needs cmake, ninja and a c compiler; on the maintainer's Windows machine put CLion's MinGW `bin` on `PATH`. One test, the symlink workspace test in `tests/test_lsp.py`, always fails on that machine and is not this feature's business.
- Before every commit: `ruff format src tests && ruff check src tests && mypy`.
- Commit messages are one lowercase imperative sentence, no prefix, followed by the trailer `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Prose in `SPEC.md` and `docs/` follows the house style: British spelling (`initialiser`), ` - ` as the dash, reasons stated beside rules.

---

### Task 1: The `StringConversion` variant

**Files:**
- Modify: `src/ddd/models/conversion.py` (module docstring, new class after `EnumConversion`, the `Conversion` union)
- Modify: `src/ddd/models/__init__.py` (import and `__all__`)
- Test: `tests/test_models.py` (class `TestConversions`)

**Interfaces:**
- Produces: `ddd.models.StringConversion`, a frozen pydantic model with `kind: Literal["string"]` (required, no default), `to_physical(raw) -> raw`, `to_raw(physical) -> physical`, `describe() -> "string"`. `conversion_identity(StringConversion(kind="string")) == {"kind": "string"}`; `raw_reading` answers `None` for it; `physical_range` needs no change.

- [ ] **Step 1: Write the failing tests**

Add to `class TestConversions` in `tests/test_models.py`:

```python
    def test_a_string_conversion_is_spelled_with_its_kind(self) -> None:
        """A string has no key of its own to be inferred from, so ``{}`` stays the identity."""
        from ddd.models import StringConversion

        parsed = definition(conversion={"kind": "string"}, dimensions=[8])
        assert isinstance(parsed.conversion, StringConversion)
        assert isinstance(parsed.conversion, ConversionRule)
        assert parsed.conversion.describe() == "string"
        assert isinstance(definition(conversion={}).conversion, IdentityConversion)

    def test_a_string_conversion_takes_no_other_key(self) -> None:
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            definition(conversion={"kind": "string", "factor": 2}, dimensions=[8])

    def test_a_string_is_the_identity_on_one_byte(self) -> None:
        """Compared as written, ranged as its datatype, and one byte reads as nothing."""
        from ddd.models import StringConversion, conversion_identity, physical_range, raw_reading

        conversion = StringConversion(kind="string")
        assert conversion.to_physical(86) == 86
        assert conversion.to_raw(86) == 86
        assert conversion_identity(conversion) == {"kind": "string"}
        assert physical_range(conversion, 0, 255) == (0, 255)
        assert raw_reading(conversion, 86) is None
```

- [ ] **Step 2: Run them to verify they fail**

Run: `pytest tests/test_models.py -q --no-cov -k "string_conversion or one_byte"`
Expected: FAIL, `ImportError: cannot import name 'StringConversion'` and, for the first test, a validation error about `kind` being `'string'`.

- [ ] **Step 3: Add the variant**

In `src/ddd/models/conversion.py`, change the module docstring's first sentence of the second paragraph from "The three variants form a tagged union" to "The four variants form a tagged union". After `class EnumConversion` (before `def _infer_kind`) add:

```python
class StringConversion(_Frozen):
    """Bytes read as text: each element of the array holds one character code.

    Stated on a ``uint8`` or ``sint8`` array of one dimension; the rules sit beside the
    datatype, in :func:`ddd.models.objects.refuse_string_misuse`, because the same pair is
    written in three places. ``kind`` is required here, unlike on the other three kinds: a
    string has no key of its own for :func:`_infer_kind` to read it off, and ``{}`` is the
    identity.

    The two mappings are the identity on one byte, so that the derived limits of a string
    are the raw range of its datatype - which is what the a2l record states - and no caller
    of :func:`physical_range` has to know that a string exists. A byte has no reading of its
    own, so :func:`raw_reading` answers nothing for it, as for the identity.
    """

    kind: Literal["string"]

    def to_physical(self, raw: float) -> float:
        return raw

    def to_raw(self, physical: float) -> float:
        return physical

    def describe(self) -> str:
        return "string"
```

Change the union to:

```python
Conversion = Annotated[
    IdentityConversion | LinearConversion | EnumConversion | StringConversion,
    Field(discriminator="kind"),
    BeforeValidator(_infer_kind),
]
"""Raw to physical conversion; ``kind`` may be omitted when the shape is unambiguous, which
a string never is."""
```

In `src/ddd/models/__init__.py` add `StringConversion` to the `from ddd.models.conversion import (...)` list and to `__all__`, both in alphabetical position (after `"Shape"` in `__all__`).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_models.py -q --no-cov`
Expected: all PASS.

- [ ] **Step 5: Lint, full suite, commit, push**

```bash
ruff format src tests && ruff check src tests && mypy
pytest -q
git add src/ddd/models/conversion.py src/ddd/models/__init__.py tests/test_models.py
git commit -m "add the string conversion to the contract" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push
```

---

### Task 2: The string rules, shared by definitions, members and scalar types

**Files:**
- Modify: `src/ddd/models/objects.py` (imports; new constants and functions after `refuse_enum_on_non_integer`; a validator on `DataObject`)
- Modify: `src/ddd/models/types.py` (imports; `check_string_member_shape`; validators on `Member` and `ScalarType`)
- Modify: `src/ddd/models/__init__.py` (exports)
- Test: `tests/test_models.py`, `tests/test_types.py`

**Interfaces:**
- Produces: `refuse_string_misuse(datatype, conversion, *, unit, limits, display_format) -> None` raising `ValueError`; `check_string_shape(kind: ObjectKind, shape: WrittenShape | None) -> None` raising `ValueError`; `check_string_member_shape(member: MemberKind, dimensions: WrittenShape) -> None` raising `ValueError`; `STRING_DATATYPES`, `STRING_OBJECT_KINDS`. Task 5 calls the two `check_*` functions from the analysis.

- [ ] **Step 1: Write the failing tests for definitions**

Add to the imports of `tests/test_models.py`: `DataObject` (from `ddd.models`) and `from typing import Any`. Add a helper after `definition()`:

```python
def declared(**definition: Any) -> DataObject:
    """A definition of any kind, validated the way a component file validates it."""
    parsed = ComponentFile.model_validate(component("A", declare("output", "X", **definition)))
    return parsed.component.interface[0].definition
```

Add a new class at the end of the file:

```python
class TestStringRules:
    """A string is a one dimensional byte array read as text, and states nothing text lacks."""

    def test_a_string_is_a_measurement_or_a_value_block_of_one_dimension(self) -> None:
        for kind in ("measurement", "value_block"):
            parsed = declared(kind=kind, conversion={"kind": "string"}, dimensions=[16])
            assert parsed.conversion is not None
            assert parsed.conversion.describe() == "string"

    def test_sint8_is_a_byte_too(self) -> None:
        declared(datatype="sint8", conversion={"kind": "string"}, dimensions=[16])

    @pytest.mark.parametrize("datatype", ["uint16", "boolean", "float32"])
    def test_a_string_needs_a_byte_datatype(self, datatype: str) -> None:
        with pytest.raises(ValidationError, match="needs a byte datatype"):
            declared(datatype=datatype, conversion={"kind": "string"}, dimensions=[16])

    @pytest.mark.parametrize(
        ("kind", "extra"),
        [
            ("parameter", {}),
            ("axis", {"size": 4}),
            ("curve", {"axis": "A"}),
            ("map", {"x_axis": "A", "y_axis": "B"}),
        ],
    )
    def test_a_string_is_no_table_and_no_scalar(self, kind: str, extra: dict[str, Any]) -> None:
        with pytest.raises(ValidationError, match="one dimensional array of bytes"):
            declared(kind=kind, conversion={"kind": "string"}, **extra)

    @pytest.mark.parametrize("dimensions", [[], [4, 4]])
    def test_a_string_states_exactly_one_dimension(self, dimensions: list[int]) -> None:
        with pytest.raises(ValidationError, match="exactly one dimension"):
            declared(conversion={"kind": "string"}, dimensions=dimensions)

    @pytest.mark.parametrize(
        ("key", "value", "expected"),
        [
            ("unit", "s", "has no unit"),
            ("limits", {"min": 0, "max": 9}, "has no limits"),
            ("a2l", {"format": "%8.3"}, "has no display format"),
        ],
    )
    def test_a_string_states_nothing_text_lacks(
        self, key: str, value: Any, expected: str
    ) -> None:
        with pytest.raises(ValidationError, match=expected):
            declared(conversion={"kind": "string"}, dimensions=[16], **{key: value})
```

- [ ] **Step 2: Write the failing tests for members and scalar types**

Add to `tests/test_types.py`, at the end:

```python
class TestStringMembersAndTypes:
    """The same rules as on a definition, where a datatype and a conversion meet in a type."""

    def string(self, **extra: Any) -> dict[str, Any]:
        return value("label", datatype="uint8", conversion={"kind": "string"}, dimensions=[16], **extra)

    def test_a_string_member_is_a_value_member_of_one_dimension(self) -> None:
        member = Member.model_validate(self.string())
        assert member.conversion is not None
        assert member.conversion.describe() == "string"

    def test_a_bitfield_holds_no_string(self) -> None:
        with pytest.raises(ValidationError, match="holds no string"):
            Member.model_validate(bits("flag", datatype="uint8", conversion={"kind": "string"}))

    @pytest.mark.parametrize("dimensions", [[], [2, 8]])
    def test_a_string_member_states_exactly_one_dimension(self, dimensions: list[int]) -> None:
        with pytest.raises(ValidationError, match="exactly one dimension"):
            Member.model_validate(self.string(dimensions=dimensions))

    def test_a_string_member_needs_a_byte_datatype(self) -> None:
        with pytest.raises(ValidationError, match="needs a byte datatype"):
            Member.model_validate(self.string(datatype="uint16"))

    @pytest.mark.parametrize(
        ("key", "stated", "expected"),
        [
            ("unit", "s", "has no unit"),
            ("limits", {"min": 0, "max": 9}, "has no limits"),
            ("a2l", {"format": "%8.3"}, "has no display format"),
        ],
    )
    def test_a_string_member_states_nothing_text_lacks(
        self, key: str, stated: Any, expected: str
    ) -> None:
        with pytest.raises(ValidationError, match=expected):
            Member.model_validate(self.string(**{key: stated}))

    def test_a_scalar_type_may_be_a_string(self) -> None:
        parsed = ScalarType.model_validate(
            scalar("Label_t", datatype="uint8", conversion={"kind": "string"})
        )
        assert parsed.conversion.describe() == "string"

    def test_a_string_type_is_held_to_the_same_rules(self) -> None:
        with pytest.raises(ValidationError, match="needs a byte datatype"):
            ScalarType.model_validate(scalar("Label_t", conversion={"kind": "string"}))
        with pytest.raises(ValidationError, match="has no unit"):
            ScalarType.model_validate(
                scalar("Label_t", datatype="uint8", unit="s", conversion={"kind": "string"})
            )
        with pytest.raises(ValidationError, match="has no limits"):
            ScalarType.model_validate(
                scalar(
                    "Label_t",
                    datatype="uint8",
                    limits={"min": 0, "max": 9},
                    conversion={"kind": "string"},
                )
            )
```

- [ ] **Step 3: Run them to verify they fail**

Run: `pytest tests/test_models.py tests/test_types.py -q --no-cov -k "StringRules or StringMembers"`
Expected: FAIL - the accepting tests pass, every refusal test fails with `DID NOT RAISE`.

- [ ] **Step 4: Add the rules to the object model**

In `src/ddd/models/objects.py`, extend the conversion import to `from ddd.models.conversion import Conversion, EnumConversion, StringConversion, conversion_range`. After `refuse_enum_on_non_integer` add:

```python
STRING_DATATYPES: Final = frozenset({Datatype.UINT8, Datatype.SINT8})
"""What a string may be stored in: one byte per character, of either signedness.

Vector's checker accepts a ``UBYTE`` or an ``SBYTE`` record layout for an ASCII string and
nothing else, and c lets a string literal initialise an array of either character type.
"""

STRING_OBJECT_KINDS: Final = frozenset({ObjectKind.MEASUREMENT, ObjectKind.VALUE_BLOCK})
"""The kinds a string may be: the two that state their own dimensions.

A ``parameter`` has no dimensions to hold characters in, and an ``axis``, a ``curve`` and a
``map`` are tables of numbers.
"""


def refuse_string_misuse(
    datatype: Datatype | None,
    conversion: Conversion | None,
    *,
    unit: str,
    limits: Limits | None,
    display_format: str | None,
) -> None:
    """Refuse what a string cannot sit on or carry, wherever a datatype and a conversion meet.

    Shared between a definition, a structure member and a scalar type the way
    :func:`refuse_enum_on_non_integer` is, so that the verdict cannot depend on where the
    same pair happens to be written. The shape rule is not here: what "one dimension" is
    spelled as differs between a definition and a member, and a scalar type has no shape,
    so each states it in its own words - :func:`check_string_shape` for a definition.

    Text has no unit, no physical range and no display format, which is why all three are
    refused rather than ignored: a unit would reach the a2l as the unit of a method that
    cannot exist, limits would offer a calibration tool a range over character codes, and
    a format would claim decimals of a string.
    """
    if not isinstance(conversion, StringConversion):
        return
    if isinstance(datatype, Datatype) and datatype not in STRING_DATATYPES:
        msg = f"a string conversion needs a byte datatype, uint8 or sint8, got '{datatype.value}'"
        raise ValueError(msg)
    if unit:
        msg = f"a string has no unit, got '{unit}'"
        raise ValueError(msg)
    if limits is not None:
        msg = "a string has no limits; its range is the byte range of its datatype"
        raise ValueError(msg)
    if display_format is not None:
        msg = f"a string has no display format, got a2l.format '{display_format}'"
        raise ValueError(msg)


def check_string_shape(kind: ObjectKind, shape: WrittenShape | None) -> None:
    """Refuse a string that is not a one dimensional measurement or value block.

    A function raising ``ValueError`` rather than a validator, because the rule is answered
    twice: by the contract for a definition that states the conversion itself, and by the
    analysis for a declaration naming a scalar type that carries it, once the type is known.
    A second dimension would be an array of strings, which the a2l format cannot describe -
    Vector's generator splits one into single string objects for that reason - and an array
    of structures with a string member is how DDD writes it.
    """
    if kind not in STRING_OBJECT_KINDS:
        msg = (
            f"a string is a one dimensional array of bytes, which a '{kind.value}' is not; "
            f"declare it as a 'measurement' or a 'value_block'"
        )
        raise ValueError(msg)
    if shape is None or len(shape) != 1:
        spelled = "none" if not shape else str(len(shape))
        msg = (
            f"a string states exactly one dimension, its length in bytes, got {spelled}; an "
            f"array of strings is written as an array of structures with a string member"
        )
        raise ValueError(msg)
```

In `class DataObject`, after `_enum_requires_integer`, add:

```python
    @model_validator(mode="after")
    def _a_string_is_a_one_dimensional_byte_array(self) -> DataObject:
        refuse_string_misuse(
            self.datatype,
            self.conversion,
            unit=self.unit,
            limits=self.limits,
            display_format=self.a2l.format,
        )
        if isinstance(self.conversion, StringConversion):
            check_string_shape(self.kind, self.declared_shape)
        return self
```

- [ ] **Step 5: Add the rules to the type model**

In `src/ddd/models/types.py`, extend the imports: `from ddd.models.conversion import Conversion, StringConversion, physical_range`, and add `WrittenShape` and `refuse_string_misuse` to the names imported from `ddd.models.objects`. After the `Member` class's helper functions section - right before `class Member` - add:

```python
def check_string_member_shape(member: MemberKind, dimensions: WrittenShape) -> None:
    """Refuse a string member that is not a ``value`` member of one dimension.

    The member's spelling of the rule :func:`~ddd.models.objects.check_string_shape` states
    for a definition, raised as ``ValueError`` for the same reason: the contract answers it
    for a member stating the conversion, and the analysis for one naming a scalar type that
    carries it. A bitfield holds no string, and a second dimension would be an array of
    strings, which the a2l format cannot describe.
    """
    if member is MemberKind.BITS:
        msg = "a 'bits' member holds no string; a string is a 'value' member of one dimension"
        raise ValueError(msg)
    if len(dimensions) != 1:
        spelled = "none" if not dimensions else str(len(dimensions))
        msg = (
            f"a string member states exactly one dimension, its length in bytes, got "
            f"{spelled}; an array of strings is written as an array of structures with a "
            f"string member"
        )
        raise ValueError(msg)
```

(`MemberKind` must be defined above it; if it is defined after the helpers, place the function directly after the `MemberKind` enum.) In `class Member`, after `_enum_requires_integer`, add:

```python
    @model_validator(mode="after")
    def _a_string_member_is_a_one_dimensional_byte_array(self) -> Member:
        refuse_string_misuse(
            self.datatype,
            self.conversion,
            unit=self.unit,
            limits=self.limits,
            display_format=self.a2l.format,
        )
        if isinstance(self.conversion, StringConversion):
            check_string_member_shape(self.member, self.dimensions)
        return self
```

In `class ScalarType`, after `_enum_requires_integer`, add:

```python
    @model_validator(mode="after")
    def _a_string_type_is_bytes(self) -> ScalarType:
        refuse_string_misuse(
            self.datatype, self.conversion, unit=self.unit, limits=self.limits, display_format=None
        )
        return self
```

In `src/ddd/models/__init__.py` export `STRING_DATATYPES`, `STRING_OBJECT_KINDS`, `check_string_shape`, `refuse_string_misuse` from `ddd.models.objects` and `check_string_member_shape` from `ddd.models.types`, each in its import list and in `__all__`.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `pytest tests/test_models.py tests/test_types.py -q --no-cov`
Expected: all PASS.

- [ ] **Step 7: Lint, full suite, commit, push**

```bash
ruff format src tests && ruff check src tests && mypy
pytest -q
git add src/ddd/models/objects.py src/ddd/models/types.py src/ddd/models/__init__.py tests/test_models.py tests/test_types.py
git commit -m "hold a string to a byte array of one dimension" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push
```

---

### Task 3: The string spelling of `init` in the contract

**Files:**
- Modify: `src/ddd/models/objects.py` (`InitValue`, `flatten`, `broadcast`, `check_shape`, `DataObject.scalar_values` docstring)
- Test: `tests/test_models.py`

**Interfaces:**
- Produces: `InitValue` accepts `str`; `flatten("abc") == []`; `broadcast("abc", shape) == "abc"`; `check_shape("abc", shape) is None`; `DataObject.scalar_values()` is `()` for a string init. Tasks 4, 6 and 10 rely on exactly these.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_models.py`:

```python
class TestStringInit:
    """The third spelling of ``init``: the text of a string object."""

    def test_a_string_init_is_kept_as_text(self) -> None:
        parsed = definition(conversion={"kind": "string"}, dimensions=[8], init="V1.2")
        assert parsed.init == "V1.2"
        assert parsed.scalar_values() == ()

    def test_a_quoted_number_is_text_rather_than_the_number(self) -> None:
        """The arm is picked by the exact type of the value, so a quoted init no longer reads
        as a number; the analysis refuses it on anything but a string object."""
        assert definition(init="12").init == "12"

    def test_a_string_is_neither_broadcast_nor_flattened(self) -> None:
        from ddd.models.objects import check_shape, flatten

        assert broadcast("abc", (8,)) == "abc"
        assert flatten("abc") == []
        assert check_shape("abc", (8,)) is None
```

- [ ] **Step 2: Run them to verify they fail**

Run: `pytest tests/test_models.py -q --no-cov -k StringInit`
Expected: FAIL - the first two with a validation error on `init`, the third with `AttributeError: 'str' object has no attribute ...` or a wrong value.

- [ ] **Step 3: Widen the type and its readers**

In `src/ddd/models/objects.py` change `InitValue` to:

```python
type InitValue = Annotated[
    Annotated[int, Field(ge=-(2**63), le=2**64 - 1)] | bool | Real | str | tuple[InitValue, ...],
    BeforeValidator(within_64_bits),
]
```

and append to its docstring:

```
The ``str`` arm is for a string object, whose init is its text; the analysis refuses it on
any other object (``init-invalid``), because only there is the conversion known - a
declaration naming a scalar type learns its conversion from the type. pydantic picks an arm
by the exact type of the value before it tries to coerce, so a quoted number ``"12"`` is
now text, refused where a number was meant, where it used to be read as the number: the one
place the quoted-spelling question left open on :data:`Number` is answered.
```

Change the three helpers:

```python
def check_shape(value: InitValue, shape: Shape) -> str | None:
    """Validate a nested init value against an array shape.

    A string is not judged here: whether it fits is a question about the object's
    conversion as much as its shape, and the analysis answers both at once.
    """
    if isinstance(value, str):
        return None
    if not shape:
        ...  # unchanged from here on


def flatten(value: InitValue) -> list[float | int | bool]:
    """Every raw scalar of an init, in storage order; a string contributes none.

    A string's bytes are its characters, which the string rules check and the c literal
    spells; nothing that converts or draws raw numbers has any business with them.
    """
    if isinstance(value, str):
        return []
    if isinstance(value, tuple):
        return [scalar for element in value for scalar in flatten(element)]
    return [value]


def broadcast(value: InitValue, shape: Shape) -> InitValue:
    """Expand a scalar init over ``shape``; a nested value or a string is returned unchanged."""
    if isinstance(value, tuple | str):
        return value
    if not shape:
        return value
    return tuple(broadcast(value, shape[1:]) for _ in range(shape[0]))
```

Change the docstring of `DataObject.scalar_values` to: `"""All raw init values, flattened; empty when no init is given, or when it is text."""`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_models.py -q --no-cov`
Expected: all PASS.

- [ ] **Step 5: Lint, full suite, commit, push**

```bash
ruff format src tests && ruff check src tests && mypy
pytest -q
git add src/ddd/models/objects.py tests/test_models.py
git commit -m "let a string object state its init as text" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push
```

---

### Task 4: The analysis checks a string init

**Files:**
- Modify: `src/ddd/analysis.py` (import; `_check_init_shape`; new `_check_string_init`)
- Test: `tests/test_analysis.py`

**Interfaces:**
- Consumes: `StringConversion` (Task 1); `check_shape` skipping strings (Task 3).
- Produces: `init-invalid` findings for the three string init mistakes, at `definition.init`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_analysis.py`:

```python
class TestStringInit:
    """A string init is the text of a string object, printable, with room for the terminator."""

    def string_object(self, **extra: object) -> dict[str, object]:
        return declare(
            "local",
            "Label",
            "uint8",
            kind="value_block",
            conversion={"kind": "string"},
            dimensions=[8],
            **extra,
        )

    def one(self, tree: Path, declaration: dict[str, object]) -> tuple[object, list[str], str]:
        dictionary, bag = run_analysis(
            tree,
            {"project.ddd.json": project("P", "a.ddd.json"), "a.ddd.json": component("A", declaration)},
        )
        return dictionary, checks(bag), messages(bag)

    def test_a_string_init_that_fits_is_no_finding(self, tree: Path) -> None:
        dictionary, found, _ = self.one(tree, self.string_object(init="V1.2.3"))
        assert found == []
        assert dictionary is not None
        assert dictionary.by_name["Label"].init == "V1.2.3"

    def test_the_empty_string_is_an_initialiser(self, tree: Path) -> None:
        _, found, _ = self.one(tree, self.string_object(init=""))
        assert found == []

    def test_a_string_init_leaves_room_for_the_terminator(self, tree: Path) -> None:
        _, found, text = self.one(tree, self.string_object(init="12345678"))
        assert found == ["init-invalid"]
        assert "8 characters long, but the string holds 8 bytes" in text
        assert "at most 7 fit" in text

    def test_a_string_init_is_printable_ascii(self, tree: Path) -> None:
        _, found, text = self.one(tree, self.string_object(init="V1\t2é"))
        assert found == ["init-invalid"]
        assert "U+0009, U+00E9" in text

    def test_a_string_init_on_a_number_is_refused(self, tree: Path) -> None:
        _, found, text = self.one(
            tree,
            declare("local", "Speed", "uint16", unit="Hz", conversion={"factor": 0.25}, init="12"),
        )
        assert found == ["init-invalid"]
        assert (
            "initialised with text, but its conversion is linear(factor=0.25, offset=0)" in text
        )

    def test_bytes_and_text_disagree(self, tree: Path) -> None:
        """A byte array in one component and a string in another is a mismatch, as written."""
        _, bag = run_analysis(
            tree,
            two_components(
                a=[
                    declare(
                        "output",
                        "Label",
                        "uint8",
                        kind="value_block",
                        dimensions=[8],
                        conversion={"kind": "string"},
                    )
                ],
                b=[
                    declare(
                        "input",
                        "Label",
                        "uint8",
                        kind="value_block",
                        dimensions=[8],
                        conversion={"kind": "identity"},
                    )
                ],
            ),
        )
        assert checks(bag) == ["definition-mismatch"]
        assert "conversion: identity != string" in messages(bag)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `pytest tests/test_analysis.py -q --no-cov -k StringInit`
Expected: the three refusal tests FAIL (no finding is raised: a string is not a tuple, so today's shape check returns early); the others PASS.

- [ ] **Step 3: Add the check**

In `src/ddd/analysis.py`, add `StringConversion` to the names imported from `ddd.models`. Replace the body of `_check_init_shape` up to the `check_shape` call with:

```python
        init = ref.definition.init
        if not isinstance(init, tuple | str):
            # A scalar init fills every element of whatever the shape is; nothing to check.
            return
        declared = ref.definition.declared_shape
        # The declaration's own shape, resolved to numbers: an init is counted against the
        # value of a dimension, however that dimension happens to be spelled.
        shape = self._numeric_shape(declared) if declared is not None else resolved
        if isinstance(init, str):
            self._check_string_init(ref, init, shape)
            return
        problem = check_shape(init, shape)
```

(the rest of the method stays as it is). Directly after `_check_init_shape` add:

```python
    def _check_string_init(self, ref: DeclarationRef, init: str, shape: Shape) -> None:
        """A string init is the text of a string object, printable, with room for its zero.

        Three ways to be wrong, one identifier - ``init-invalid``, as every wrong init is.
        The conversion is asked here rather than in the contract because a declaration
        naming a scalar type only learns it from the type; the length is counted against the
        resolved dimension, so a length spelled as a constant name is resolved first. The
        content is printable ASCII, 0x20 to 0x7E, because neither the c literal nor the a2l
        could carry anything else unambiguously; and the text is shorter than the array so
        that the terminating zero fits - a string that exactly fills its array is legal c,
        refused by C++, and indistinguishable in the generated file from one that was meant
        to be terminated.
        """
        conversion = ref.definition.conversion
        assert conversion is not None  # a structured declaration refuses an init before this
        location = ref.location("definition.init")
        if not isinstance(conversion, StringConversion):
            self._bag.add(
                "init-invalid",
                f"'{ref.name}' is initialised with text, but its conversion is "
                f"{conversion.describe()}; only a string object takes a string init",
                location,
            )
            return
        unprintable = sorted({character for character in init if not " " <= character <= "~"})
        if unprintable:
            spelled = ", ".join(f"U+{ord(character):04X}" for character in unprintable)
            self._bag.add(
                "init-invalid",
                f"the init of '{ref.name}' contains {spelled}, which is not printable ASCII; "
                f"a string init is written in the characters 0x20 to 0x7E",
                location,
            )
        # One dimension is what the string rules guarantee by the time an object resolves.
        if len(init) >= shape[0]:
            self._bag.add(
                "init-invalid",
                f"the init of '{ref.name}' is {len(init)} characters long, but the string "
                f"holds {shape[0]} bytes and needs one for the terminator; at most "
                f"{shape[0] - 1} fit",
                location,
            )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_analysis.py -q --no-cov`
Expected: all PASS.

- [ ] **Step 5: Lint, full suite, commit, push**

```bash
ruff format src tests && ruff check src tests && mypy
pytest -q
git add src/ddd/analysis.py tests/test_analysis.py
git commit -m "check a string init for its content, its length and its object" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push
```

---

### Task 5: A declaration or member naming a string type

**Files:**
- Modify: `src/ddd/analysis.py` (imports; `_resolve_type`; new `_string_type_fits`; `_check_types`; new `_check_string_members`)
- Test: `tests/test_analysis.py`

**Interfaces:**
- Consumes: `check_string_shape`, `check_string_member_shape` (Task 2), `StringConversion` (Task 1).
- Produces: `schema` findings, with a `declared here` note at the type, for a declaration or a member naming a string scalar type with the wrong kind, shape or an `a2l.format`; the declaration is dropped, the structure poisoned.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_analysis.py`:

```python
STRING_TYPE: dict[str, object] = {
    "type": "scalar",
    "name": "Label_t",
    "datatype": "uint8",
    "conversion": {"kind": "string"},
}


class TestStringTypes:
    """A scalar type fixes that bytes are text; what names it states how many."""

    def typed(self, tree: Path, *declarations: dict[str, object], types: list[dict[str, object]] | None = None) -> tuple[object, list[str], str]:
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "t.ddd.json", "a.ddd.json"),
                "t.ddd.json": {"types": [STRING_TYPE, *(types or [])]},
                "a.ddd.json": component("A", *declarations),
            },
        )
        return dictionary, checks(bag), messages(bag)

    def test_a_declaration_naming_a_string_type_states_its_length(self, tree: Path) -> None:
        dictionary, found, _ = self.typed(
            tree, declare("local", "Label", typename="Label_t", kind="value_block", dimensions=[16])
        )
        assert found == []
        assert dictionary is not None
        entry = dictionary.by_name["Label"]
        assert entry.conversion.describe() == "string"
        assert entry.datatype.value == "uint8"
        assert entry.shape == (16,)
        assert entry.limits.as_tuple() == (0, 255)

    @pytest.mark.parametrize(
        ("definition", "expected"),
        [
            ({"kind": "parameter"}, "one dimensional array of bytes"),
            ({"kind": "measurement"}, "exactly one dimension"),
            ({"kind": "value_block", "dimensions": [2, 8]}, "exactly one dimension"),
            (
                {"kind": "value_block", "dimensions": [8], "a2l": {"format": "%8.3"}},
                "has no display format",
            ),
        ],
    )
    def test_a_declaration_naming_a_string_type_is_held_to_the_string_rules(
        self, tree: Path, definition: dict[str, object], expected: str
    ) -> None:
        dictionary, found, text = self.typed(
            tree, declare("local", "Label", typename="Label_t", **definition)
        )
        assert found == ["schema"]
        assert expected in text
        assert "declared here" in text
        assert dictionary is not None
        assert "Label" not in dictionary.by_name

    def structure(self, member: dict[str, object]) -> dict[str, object]:
        return {"type": "struct", "name": "Info_t", "members": [member]}

    def test_a_member_naming_a_string_type_states_its_length(self, tree: Path) -> None:
        dictionary, found, _ = self.typed(
            tree,
            declare("local", "Info", typename="Info_t", kind="parameter"),
            types=[
                self.structure(
                    {"name": "label", "member": "value", "typename": "Label_t", "dimensions": [16]}
                )
            ],
        )
        assert found == []
        assert dictionary is not None
        leaf = dictionary.comparable["Info.label"]
        assert leaf.conversion.describe() == "string"
        assert leaf.shape == (16,)

    @pytest.mark.parametrize(
        ("member", "expected"),
        [
            ({"name": "label", "member": "value", "typename": "Label_t"}, "exactly one dimension"),
            (
                {"name": "label", "member": "value", "typename": "Label_t", "dimensions": [16], "a2l": {"format": "%8.3"}},
                "has no display format",
            ),
        ],
    )
    def test_a_member_naming_a_string_type_without_a_length_poisons_the_structure(
        self, tree: Path, member: dict[str, object], expected: str
    ) -> None:
        dictionary, found, text = self.typed(
            tree,
            declare("local", "Info", typename="Info_t", kind="parameter"),
            types=[self.structure(member)],
        )
        assert found == ["schema"]
        assert expected in text
        assert "declared here" in text
        assert dictionary is not None
        assert "Info.label" not in dictionary.comparable
        assert not dictionary.instances
```

- [ ] **Step 2: Run them to verify they fail**

Run: `pytest tests/test_analysis.py -q --no-cov -k StringTypes`
Expected: the two accepting tests PASS; the refusal tests FAIL with `found == []`.

- [ ] **Step 3: Refuse at the declaration**

In `src/ddd/analysis.py` add `check_string_member_shape` and `check_string_shape` to the names imported from `ddd.models`. In `_resolve_type`, replace the final `return replace(ref, resolved=...)` with:

```python
        if isinstance(entry.conversion, StringConversion) and not self._string_type_fits(
            ref, named, declared
        ):
            return None
        # A scalar type fixes what the value means and nothing about the variable, so only the
        # four it fixes are filled in. The definition already refused to restate any of them.
        return replace(
            ref,
            resolved=definition.model_copy(
                update={
                    "datatype": entry.datatype,
                    "unit": entry.unit,
                    "conversion": entry.conversion,
                    "limits": entry.limits,
                }
            ),
        )
```

and after `_resolve_type` add:

```python
    def _string_type_fits(self, ref: DeclarationRef, named: str, declared: LoadedType) -> bool:
        """A declaration naming a string type is a one dimensional measurement or value block.

        The type fixes that the bytes are text and the declaration states how many there
        are, so the shape rule a definition stating the conversion itself answers in the
        contract - :func:`check_string_shape` - is answered here, where the declaration is,
        with the type it names beside it; a display format is refused for the same reason
        the contract refuses one. Refused rather than resolved: a string with no dimension
        or on a table kind is nothing the a2l backend has a record for.
        """
        definition = ref.declaration.definition
        try:
            check_string_shape(definition.kind, definition.declared_shape)
            if definition.a2l.format is not None:
                msg = f"a string has no display format, got a2l.format '{definition.a2l.format}'"
                raise ValueError(msg)
        except ValueError as error:
            self._refuse(
                "schema",
                f"'{ref.name}' is declared as '{named}', which is a string: {error}",
                ref.location("definition"),
                ref,
                notes=[("declared here", declared.location())],
            )
            return False
        return True
```

- [ ] **Step 4: Refuse at the member**

In `_check_types`, after the line `self._check_scalar_type(entry)` add `self._check_string_members(entry)`. After `_check_scalar_type` add:

```python
    def _check_string_members(self, entry: LoadedType) -> None:
        """A member naming a string type is a ``value`` member of one dimension.

        The rule a member stating the conversion itself answers in the contract, answered
        here for the member that names the type, and the structure is poisoned the way one
        of unknown size is: a string member with no length has no size, so no variable can
        resolve as the structure.
        """
        structure = entry.structure
        if structure is None:
            return
        for index, member in enumerate(structure.members):
            declared = self._declared_of(member)
            if not isinstance(declared, ScalarType) or not isinstance(
                declared.conversion, StringConversion
            ):
                continue
            try:
                check_string_member_shape(member.member, member.dimensions)
                if member.a2l.format is not None:
                    msg = f"a string has no display format, got a2l.format '{member.a2l.format}'"
                    raise ValueError(msg)
            except ValueError as error:
                assert member.typename is not None  # it named the scalar type found above
                location = entry.location(f"members[{index}]")
                reported = (
                    self._bag.add(
                        "schema",
                        f"member '{member.name}' of structure '{entry.name}' names "
                        f"'{member.typename}', which is a string: {error}",
                        location,
                        notes=[("declared here", self._types[member.typename].location())],
                    )
                    is not None
                )
                self._poisoned_types.setdefault(entry.name, _Cause("schema", reported, location))
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/test_analysis.py -q --no-cov`
Expected: all PASS.

- [ ] **Step 6: Lint, full suite, commit, push**

```bash
ruff format src tests && ruff check src tests && mypy
pytest -q
git add src/ddd/analysis.py tests/test_analysis.py
git commit -m "hold what names a string type to the string rules" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push
```

---

### Task 6: The c string literal

**Files:**
- Modify: `src/ddd/backends/c/literals.py` (new `c_string_literal`; `c_initializer`)
- Test: `tests/test_generation.py`

**Interfaces:**
- Consumes: `broadcast` returning a string unchanged (Task 3).
- Produces: `c_string_literal(text: str) -> str`; `c_initializer` renders a `str` as that literal.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_generation.py`:

```python
class TestStringInitialisers:
    """A string init is a c string literal; c fills the rest of the array with zero."""

    def string(self, init: object, *, datatype: str = "uint8", kind: str = "value_block", size: int = 16) -> dict[str, Any]:
        return simple(
            declare(
                "local",
                "Label",
                datatype,
                kind=kind,
                conversion={"kind": "string"},
                dimensions=[size],
                init=init,
            )
        )

    def test_a_string_init_is_a_string_literal(self, tree: Path) -> None:
        files = generate(tree, self.string("V1.2.3"))
        assert 'const uint8_t Label[16] = "V1.2.3";' in files["ddd_globals.c"]

    def test_the_literal_escapes_what_c_reads_specially(self, tree: Path) -> None:
        """A quote, a backslash, and ``?`` - two of which before ``=`` form a trigraph."""
        files = generate(tree, self.string('a "b" \\ ??=', size=32))
        assert r'const uint8_t Label[32] = "a \"b\" \\ \?\?=";' in files["ddd_globals.c"]

    def test_the_empty_string_is_an_explicit_initialiser(self, tree: Path) -> None:
        files = generate(tree, self.string("", kind="measurement"))
        assert 'uint8_t Label[16] = "";' in files["ddd_globals.c"]

    def test_a_list_init_on_a_string_object_renders_as_bytes(self, tree: Path) -> None:
        files = generate(tree, self.string([86, 49, 0, 0], size=4))
        assert "const uint8_t Label[4] = { 86U, 49U, 0U, 0U };" in files["ddd_globals.c"]

    def test_a_signed_byte_string_takes_the_same_literal(self, tree: Path) -> None:
        files = generate(tree, self.string("abc", datatype="sint8", size=8))
        assert 'const int8_t Label[8] = "abc";' in files["ddd_globals.c"]
```

- [ ] **Step 2: Run them to verify they fail**

Run: `pytest tests/test_generation.py -q --no-cov -k StringInitialisers`
Expected: the literal tests FAIL (today `c_literal` is handed a string and raises `TypeError` or `ValueError` from `int(value)`); the list test PASSES.

- [ ] **Step 3: Render the literal**

In `src/ddd/backends/c/literals.py`, after `c_literal` add:

```python
def c_string_literal(text: str) -> str:
    """Render a string init as a c string literal.

    Only ``"`` and ``\\`` need escaping in printable ASCII, and ``?`` gets it too: two of
    them before ``=``, ``/`` or ``(`` form a trigraph under a pedantic pre-C23 dialect, and
    ``\\?`` is the escape c provides for exactly that. The analysis has refused anything
    outside 0x20 to 0x7E, so no other escape is ever needed, and it has left room for the
    terminator, which c writes along with the zeros that fill the rest of the array.
    """
    escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace("?", "\\?")
    return f'"{escaped}"'
```

and make `c_initializer` start with:

```python
    if isinstance(value, str):
        return c_string_literal(value)
    if not isinstance(value, tuple):
        return c_literal(value, datatype)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_generation.py -q --no-cov`
Expected: all PASS.

- [ ] **Step 5: Lint, full suite, commit, push**

```bash
ruff format src tests && ruff check src tests && mypy
pytest -q
git add src/ddd/backends/c/literals.py tests/test_generation.py
git commit -m "write a string init as a c string literal" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push
```

---

### Task 7: The ASCII characteristic

**Files:**
- Modify: `src/ddd/backends/a2l/model.py` (docstring; `CharacteristicView`; `_leaf_characteristic`; `_characteristic`; `_CompuMethodBuilder.reference`)
- Modify: `src/ddd/backends/a2l/templates/project.a2l.jinja` (the `CHARACTERISTIC` record)
- Test: `tests/test_a2l.py`

**Interfaces:**
- Produces: `CharacteristicView.number: int | None` (last field, default `None`); the template writes `NUMBER n` when set. `_CompuMethodBuilder.reference` answers `NO_COMPU_METHOD` for a string before building any key - Task 8 relies on that too.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_a2l.py`:

```python
class TestStrings:
    """A calibration string is an ASCII characteristic; the format has nothing else for text."""

    def block(self, datatype: str = "uint8", size: int = 16, **extra: Any) -> dict[str, Any]:
        return declare(
            "local",
            "Label",
            datatype,
            kind="value_block",
            conversion={"kind": "string"},
            dimensions=[size],
            description="Software label",
            **extra,
        )

    def test_a_string_parameter_is_an_ascii_characteristic(self, tree: Path) -> None:
        content = a2l(tree, self.block())
        assert '/begin CHARACTERISTIC Label "Software label"' in content
        assert "ASCII 0x00000000 RL_VALUES_UBYTE 0 NO_COMPU_METHOD 0 255" in content
        assert "NUMBER 16" in content
        assert "MATRIX_DIM" not in content
        assert "FORMAT" not in content
        assert "/begin COMPU_METHOD" not in content
        assert "FNC_VALUES 1 UBYTE ROW_DIR DIRECT" in content

    def test_a_signed_string_deposits_as_sbyte(self, tree: Path) -> None:
        content = a2l(tree, self.block(datatype="sint8", size=8))
        assert "ASCII 0x00000000 RL_VALUES_SBYTE 0 NO_COMPU_METHOD -128 127" in content
        assert "NUMBER 8" in content

    def test_a_string_member_of_a_parameter_is_an_ascii_characteristic_at_its_path(
        self, tree: Path
    ) -> None:
        files = {
            "project.ddd.json": project("Device", "t.ddd.json", "a.ddd.json"),
            "t.ddd.json": {
                "types": [
                    {
                        "type": "struct",
                        "name": "Info_t",
                        "members": [
                            {
                                "name": "label",
                                "member": "value",
                                "datatype": "uint8",
                                "conversion": {"kind": "string"},
                                "dimensions": [16],
                            },
                            {
                                "name": "revision",
                                "member": "value",
                                "datatype": "uint16",
                                "conversion": {},
                            },
                        ],
                    }
                ]
            },
            "a.ddd.json": component(
                "A",
                declare("local", "Info", typename="Info_t", kind="parameter"),
                description="a component",
            ),
        }
        dictionary, bag = run_analysis(tree, files)
        assert dictionary is not None, [d.render() for d in bag]
        rendered = render_files(dictionary, tree / "gen")
        content = next(file.content for file in rendered if file.path.name == "Device.a2l")
        assert '/begin CHARACTERISTIC Info.label "Info.label"' in content
        assert "ASCII 0x00000000 RL_VALUES_UBYTE 0 NO_COMPU_METHOD 0 255" in content
        assert "NUMBER 16" in content
        assert '/begin CHARACTERISTIC Info.revision "Info.revision"' in content
        assert "VALUE 0x00000000 RL_VALUES_UWORD 0 NO_COMPU_METHOD 0 65535" in content
```

- [ ] **Step 2: Run them to verify they fail**

Run: `pytest tests/test_a2l.py -q --no-cov -k TestStrings`
Expected: FAIL - today the record says `VAL_BLK`, carries a `MATRIX_DIM`, and a `CM_IDENT_NONE` method is created for the string.

- [ ] **Step 3: Write the record**

In `src/ddd/backends/a2l/model.py` add `StringConversion` to the names imported from `ddd.models`. Add to the module docstring's bullet list:

```
* a string parameter - a value block under a string conversion - becomes a ``CHARACTERISTIC``
  of type ``ASCII`` whose length is a ``NUMBER``, over the ordinary value layout of its
  datatype and with no compu method, which is the 1.6.1 form Vector's own files use; a
  string measurement is the byte array it is, with an ``ANNOTATION`` saying so, because no
  version of the format has a string measurement
```

Add to `CharacteristicView`, after `condition`:

```python
    number: int | None = None
    """The length of an ``ASCII`` characteristic in bytes; ``None`` for every other type.

    ``NUMBER`` rather than ``MATRIX_DIM``: the 1.51 text already prefers the latter, but the
    1.61 demo file and Vector's generator both emit ``NUMBER`` for a string and every reader
    of a 1.6.1 file understands it. The two are never written together.
    """
```

Rewrite `_leaf_characteristic`'s return as:

```python
        string = isinstance(leaf.conversion, StringConversion)
        return CharacteristicView(
            name=leaf.path,
            description=leaf.description or leaf.path,
            type="ASCII" if string else ("VAL_BLK" if leaf.shape else "VALUE"),
            address=self._options.address_of(leaf.path),
            deposit=self._layouts.values(leaf.datatype),
            compu_method=self._methods.reference(leaf),
            lower=format_number(leaf.limits.min),
            upper=format_number(leaf.limits.max),
            matrix_dim=_matrix_dim(leaf) if leaf.shape and not string else None,
            format=leaf.a2l.format,
            display_identifier=leaf.a2l.display_identifier,
            axis_descrs=(),
            condition=leaf.condition,
            number=leaf.shape[0] if string else None,
        )
```

and in `_characteristic` set `string = isinstance(entry.conversion, StringConversion)` first, then use `type="ASCII" if string else _CHARACTERISTIC_TYPE[entry.kind]`, `matrix_dim=_matrix_dim(entry) if entry.kind is ObjectKind.VALUE_BLOCK and not string else None`, and add `number=entry.shape[0] if string else None`.

In `_CompuMethodBuilder.reference`, before the identity early return:

```python
        if isinstance(conversion, StringConversion):
            # Text has no method: no unit may be stated, and no rational function or table
            # reads a byte as a character. Answered before any key is built, so that the
            # identity's early return below is not the only way a string could avoid one.
            return NO_COMPU_METHOD
```

In the template, after the `MATRIX_DIM` block of the `CHARACTERISTIC` record add:

```
{% if characteristic.number is not none %}
      NUMBER {{ characteristic.number }}
{% endif %}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_a2l.py -q --no-cov`
Expected: all PASS.

- [ ] **Step 5: Lint, full suite, commit, push**

```bash
ruff format src tests && ruff check src tests && mypy
pytest -q
git add src/ddd/backends/a2l/model.py src/ddd/backends/a2l/templates/project.a2l.jinja tests/test_a2l.py
git commit -m "describe a calibration string as an ascii characteristic" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push
```

---

### Task 8: The string measurement and its annotation

**Files:**
- Modify: `src/ddd/backends/a2l/model.py` (`MeasurementView`; `_measurement`; new `_string_note`)
- Modify: `src/ddd/backends/a2l/templates/project.a2l.jinja` (the `MEASUREMENT` record)
- Test: `tests/test_a2l.py`

**Interfaces:**
- Consumes: the string early return of `_CompuMethodBuilder.reference` (Task 7).
- Produces: `MeasurementView.annotation: str | None` (last field, default `None`); the template writes an `ANNOTATION` block when set.

- [ ] **Step 1: Write the failing tests**

Add to `class TestStrings` in `tests/test_a2l.py`:

```python
    def test_a_string_measurement_is_a_byte_array_with_a_note(self, tree: Path) -> None:
        content = a2l(
            tree,
            declare(
                "local",
                "StateName",
                "uint8",
                conversion={"kind": "string"},
                dimensions=[16],
                description="Name of the current state",
            ),
        )
        assert '/begin MEASUREMENT StateName "Name of the current state"' in content
        assert "UBYTE NO_COMPU_METHOD 0 0 0 255" in content
        assert "MATRIX_DIM 16 1 1" in content
        assert 'ANNOTATION_LABEL "string"' in content
        assert (
            '"16 bytes of text; ASAP2 1.6.1 has no string measurement, so the tool shows the bytes"'
            in content
        )
        assert content.count("/begin ANNOTATION") == 2  # the block and its ANNOTATION_TEXT
        assert content.count("/begin") == content.count("/end")
        assert "/begin COMPU_METHOD" not in content

    def test_a_numeric_measurement_carries_no_annotation(self, tree: Path) -> None:
        assert "ANNOTATION" not in a2l(tree, declare("local", "X", dimensions=[16]))
```

and to `class TestMeasurementRasters`:

```python
    def test_a_string_measurement_keeps_its_event(self, tree: Path) -> None:
        content = self.a2l_with_rasters(
            tree,
            declare(
                "local", "StateName", "uint8", conversion={"kind": "string"}, dimensions=[16],
                raster="10ms",
            ),
        )
        assert 'ANNOTATION_LABEL "string"' in content
        assert "/begin IF_DATA XCP" in content
        assert "EVENT 1" in content
        assert content.count("/begin") == content.count("/end")
```

- [ ] **Step 2: Run them to verify they fail**

Run: `pytest tests/test_a2l.py -q --no-cov -k "string_measurement or no_annotation"`
Expected: the two string tests FAIL on the missing annotation; the numeric one PASSES.

- [ ] **Step 3: Write the annotation**

In `src/ddd/backends/a2l/model.py` add to `MeasurementView`, after `condition`:

```python
    annotation: str | None = None
    """The note a string measurement carries, and ``None`` for every other measurement.

    The format has no string measurement in any version, so the record is the byte array it
    is; ``ANNOTATION`` is the documented place for "an application note which explains the
    function of an identifier for the calibration engineer", which tools show in the
    object's properties, and no finding is raised for what the author cannot change.
    """
```

In `_measurement` add the argument `annotation=_string_note(entry) if isinstance(entry.conversion, StringConversion) else None,` and after `_matrix_dim` add:

```python
def _string_note(entry: ResolvedObject | ResolvedLeaf) -> str:
    """What the annotation of a string measurement says: the one fact the record cannot."""
    return (
        f"{entry.shape[0]} bytes of text; ASAP2 1.6.1 has no string measurement, "
        f"so the tool shows the bytes"
    )
```

In the template's `MEASUREMENT` record, after the `DISPLAY_IDENTIFIER` block and before the `IF_DATA XCP` block, add:

```
{% if measurement.annotation %}
      /begin ANNOTATION
        ANNOTATION_LABEL "string"
        /begin ANNOTATION_TEXT
          "{{ measurement.annotation | a2l }}"
        /end ANNOTATION_TEXT
      /end ANNOTATION
{% endif %}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_a2l.py -q --no-cov`
Expected: all PASS.

- [ ] **Step 5: Lint, full suite, commit, push**

```bash
ruff format src tests && ruff check src tests && mypy
pytest -q
git add src/ddd/backends/a2l/model.py src/ddd/backends/a2l/templates/project.a2l.jinja tests/test_a2l.py
git commit -m "annotate a string measurement the format cannot describe" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push
```

---

### Task 9: Dictionary format 8 and the published schemas

**Files:**
- Modify: `src/ddd/ir.py` (`DICTIONARY_FORMAT` and its docstring)
- Regenerate: `schemas/ddd_component.schema.json`, `schemas/ddd_types.schema.json`, `schemas/ddd_dictionary.schema.json` (run the command; never hand-edit)
- Modify: `tests/test_constants.py:667`, `tests/test_external.py:197`, `tests/test_plugins.py:927` (the `== 7` assertions)
- Modify: `docs/data_dictionary.rst` (lines 37, 179 and 190), `SPEC.md` section 5.3 (the `format` sentence)
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_models.py` (import `DataDictionary` and `DICTIONARY_FORMAT` from `ddd.ir` at the top):

```python
class TestDictionaryFormat:
    def test_a_string_object_round_trips_through_the_dump(self, tree: Path) -> None:
        """The fourth kind and the string init are new shapes of the document: format 8."""
        dictionary, bag = run_analysis(
            tree,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    declare(
                        "local",
                        "Label",
                        "uint8",
                        kind="value_block",
                        conversion={"kind": "string"},
                        dimensions=[8],
                        init="V1.2",
                    ),
                ),
            },
        )
        assert dictionary is not None, messages(bag)
        payload = dictionary.model_dump(mode="json")
        assert payload["format"] == DICTIONARY_FORMAT == 8
        entry = next(o for o in payload["objects"] if o["name"] == "Label")
        assert entry["conversion"] == {"kind": "string"}
        assert entry["init"] == "V1.2"
        read_back = DataDictionary.model_validate(payload).by_name["Label"]
        assert read_back.conversion.describe() == "string"
        assert read_back.init == "V1.2"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/test_models.py -q --no-cov -k DictionaryFormat`
Expected: FAIL on `payload["format"] == 8`.

- [ ] **Step 3: Bump the format and regenerate the schemas**

In `src/ddd/ir.py` set `DICTIONARY_FORMAT = 8` and append to its docstring:

```
Format 8 added the ``string`` conversion kind and the string spelling of ``init``. A format
7 dictionary carries neither, and reads back unchanged.
```

Then run, from the repository root:

```bash
ddd schema all -o schemas
git diff --stat schemas
```

Expected: exactly the component, types and dictionary schemas change. Update the three `== 7` assertions to `== 8`. In `docs/data_dictionary.rst` change `"format": 7,` in the dump transcript to `8`, "currently ``7``" to "currently ``8``", and the shown compare transcript to `this dictionary is in format 9, and this DDD understands up to 8` (that command quotes the demo under its own name, so the runner shows it rather than runs it). In `SPEC.md` section 5.3 change "Its `format` is `7`" to "Its `format` is `8`".

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_models.py tests/test_documentation.py tests/test_constants.py tests/test_external.py tests/test_plugins.py -q --no-cov`
Expected: all PASS, including `TestCommittedSchemas`.

- [ ] **Step 5: Lint, full suite, commit, push**

```bash
ruff format src tests && ruff check src tests && mypy
pytest -q
git add src/ddd/ir.py schemas/ddd_component.schema.json schemas/ddd_types.schema.json schemas/ddd_dictionary.schema.json tests/test_models.py tests/test_constants.py tests/test_external.py tests/test_plugins.py docs/data_dictionary.rst SPEC.md
git commit -m "stamp the dictionary format 8 and publish the string in the schemas" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push
```

---

### Task 10: The list cell and the hover

**Files:**
- Modify: `src/ddd/cli.py` (`_init_cell`)
- Modify: `src/ddd/lsp/hover.py` (`import json`; `rows`; `_drawing`)
- Test: `tests/test_cli.py` (`TestList`), `tests/test_lsp.py` (`TestHover`)

**Interfaces:**
- Consumes: `flatten`/`broadcast` behaviour for strings (Task 3).

- [ ] **Step 1: Write the failing tests**

Add to `class TestList` in `tests/test_cli.py`:

```python
    def test_a_string_init_is_quoted_and_has_no_reading(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write_tree(
            tmp_path,
            {
                "project.ddd.json": project("P", "a.ddd.json"),
                "a.ddd.json": component(
                    "A",
                    declare(
                        "local",
                        "Label",
                        "uint8",
                        kind="value_block",
                        conversion={"kind": "string"},
                        dimensions=[8],
                        init="V1.2",
                    ),
                ),
            },
        )
        assert main(["list", str(tmp_path / "project.ddd.json")]) == EXIT_OK
        out = capsys.readouterr().out
        assert '"V1.2"' in out
        assert "(=" not in out
```

Add to `class TestHover` in `tests/test_lsp.py`:

```python
    def test_a_string_init_is_stated_as_text(self, tmp_path: Path) -> None:
        """Quoted as the file spells it; no reading to add, nothing to draw."""
        from ddd.lsp.hover import describe

        dictionary = self.resolved(
            tmp_path,
            declare(
                "output",
                "Label",
                datatype="uint8",
                kind="value_block",
                conversion={"kind": "string"},
                dimensions=[16],
                init="V1.2.3",
            ),
        )
        described = describe(dictionary, "Label")
        assert "| conversion | `string` |" in described
        assert described.endswith('init `"V1.2.3"`')
        assert "```" not in described
```

- [ ] **Step 2: Run them to verify they fail**

Run: `pytest tests/test_cli.py tests/test_lsp.py -q --no-cov -k "string_init"`
Expected: FAIL - the list cell raises inside `format_number` (a `str` has no `is_integer`), and so does the hover's `_stated_init`.

- [ ] **Step 3: State the text**

In `src/ddd/cli.py`, in `_init_cell`, after the `isinstance(init, tuple)` branch add:

```python
    if isinstance(init, str):
        # Quoted, so that text cannot be mistaken for a number, and spelled the way json
        # spells it, which is the way the file does; a string has no reading to add.
        return json.dumps(init)
```

In `src/ddd/lsp/hover.py` add `import json` to the imports, change the first line of `rows` to `if entry.init is None or isinstance(entry.init, str): return []` (with the docstring gaining "a string is drawn as nothing: its init is stated as text"), and make `_drawing` start with:

```python
    if isinstance(entry.init, str):
        # Text, stated as the file spells it: there is no reading to add and nothing to draw.
        return [f"init `{json.dumps(entry.init)}`"]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_cli.py tests/test_lsp.py -q --no-cov`
Expected: all PASS except, on the maintainer's Windows machine, the pre-existing symlink workspace test.

- [ ] **Step 5: Lint, full suite, commit, push**

```bash
ruff format src tests && ruff check src tests && mypy
pytest -q
git add src/ddd/cli.py src/ddd/lsp/hover.py tests/test_cli.py tests/test_lsp.py
git commit -m "state a string init as text in the listing and the hover" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push
```

---

### Task 11: Two deliveries compare a string as written

**Files:**
- Test: `tests/test_compare.py` (`TestBreakingChanges`)

No production code is expected: `conversion_identity` already compares the dumped model. If a test fails, the fix belongs in `src/ddd/compare.py`, not in the test.

- [ ] **Step 1: Write the tests**

Add to `class TestBreakingChanges` in `tests/test_compare.py`:

```python
    def test_bytes_becoming_text_is_breaking(self, tree: Path) -> None:
        """A consumer reading numbers is handed characters: a changed conversion, as written."""
        old = one_component(
            tree,
            "old",
            declare("local", "Label", "uint8", kind="value_block", dimensions=[16], conversion={}),
        )
        new = one_component(
            tree,
            "new",
            declare(
                "local",
                "Label",
                "uint8",
                kind="value_block",
                dimensions=[16],
                conversion={"kind": "string"},
            ),
        )
        bag = verdict(old, new)
        assert checks(bag) == ["changed-interface"]
        assert "conversion: string != identity" in messages(bag)
        assert bag.has_errors

    def test_two_deliveries_of_one_string_compare_clean(self, tree: Path) -> None:
        string = declare(
            "local",
            "Label",
            "uint8",
            kind="value_block",
            dimensions=[16],
            conversion={"kind": "string"},
            init="V1.2",
        )
        assert checks(verdict(one_component(tree, "old", string), one_component(tree, "new", string))) == []
```

- [ ] **Step 2: Run them**

Run: `pytest tests/test_compare.py -q --no-cov -k "bytes_becoming_text or one_string"`
Expected: PASS. If the message reads differently, fix the assertion only if the printed form is the `describe()` text of the two conversions; anything else is a bug in `compare.py`.

- [ ] **Step 3: Lint, full suite, commit, push**

```bash
ruff format src tests && ruff check src tests && mypy
pytest -q
git add tests/test_compare.py
git commit -m "compare a string between deliveries as written" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push
```

---

### Task 12: The demo shows a string, and its transcripts and compiled c follow

**Files:**
- Modify: `examples/demo/components/controller.ddd.json`, `examples/demo/components/user_interface.ddd.json`
- Modify: every documentation page whose transcript counts or lists the demo - known: `docs/getting_started.rst` (the `ok: 21 variables` line), `docs/consistency_checks.rst` (same), `docs/file_formats/project.rst` (same), `docs/concept.rst` (the `ddd list` table), `docs/file_formats/conversions.rst` (the elided list), `docs/file_formats/variable_definition.rst` (the list), `docs/data_dictionary.rst` (the dump excerpt, if it shows an affected part), `docs/generated_artefacts.rst` (a2l excerpts and the sentence "its twenty-one objects share eight compu methods")
- Test: `tests/test_transcripts.py`, `tests/test_cmake.py`, `tests/test_documentation.py`, `tests/test_cli.py` (`TestList.test_table` and the json payload test, which read the demo)

- [ ] **Step 1: Add the two objects**

In `examples/demo/components/controller.ddd.json` insert, after the `StateA` entry:

```json
      {
        "scope": "output",
        "definition": {
          "name": "StateName",
          "kind": "measurement",
          "description": "Name of the current state, as text",
          "datatype": "uint8",
          "conversion": { "kind": "string" },
          "dimensions": [16],
          "init": "OFF",
          "volatile": false
        }
      },
```

and after the `ParameterA` entry:

```json
      {
        "scope": "local",
        "definition": {
          "kind": "value_block",
          "name": "SoftwareLabel",
          "description": "Software label of the controller, as text",
          "datatype": "uint8",
          "conversion": { "kind": "string" },
          "dimensions": [16],
          "init": "V1.2.3",
          "volatile": false
        }
      },
```

In `examples/demo/components/user_interface.ddd.json` insert, after the `StateA` input, in that file's expanded layout:

```json
      {
        "scope": "input",
        "definition": {
          "name": "StateName",
          "kind": "measurement",
          "description": "Name of the current state, as text",
          "datatype": "uint8",
          "conversion": {
            "kind": "string"
          },
          "dimensions": [
            16
          ],
          "volatile": false
        }
      },
```

Then stamp identities on the two new producing declarations, which is what keeps `missing-id` quiet on the demo:

```bash
ddd id --assign examples/demo/components/controller.ddd.json
ddd check examples/demo/demo.ddd.json
```

Expected: the second command prints `ok: 23 variables in 4 components are consistent`, and `git diff examples/` shows only the two new entries plus their `id` lines.

- [ ] **Step 2: Re-run the transcripts and update the pages**

Run: `pytest tests/test_transcripts.py -q --no-cov`
Expected: FAIL on every page listed above. For each failure, run the command the page shows (for example `ddd list examples/demo/demo.ddd.json`) and replace the shown lines with what it prints, keeping the page's `...` elisions where the page had them; the variable count lines become `ok: 23 variables in 4 components are consistent`. In `docs/generated_artefacts.rst` change "its twenty-one objects share eight compu methods" to "its twenty-three objects share eight compu methods" (a string adds none). Re-run until the file passes.

- [ ] **Step 3: Compile the demo and run the documentation tests**

Run: `pytest tests/test_cmake.py tests/test_documentation.py tests/test_cli.py -q --no-cov`
Expected: PASS. The compile is what proves the literal `"V1.2.3"` and `"OFF"` build under `-Wall -Wextra -Wpedantic -Werror`.

- [ ] **Step 4: Lint, full suite, commit, push**

```bash
ruff format src tests && ruff check src tests && mypy
pytest -q
git add examples/demo docs
git commit -m "show a string measurement and a string parameter in the demo" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push
```

(`git add docs` is safe: the PDF under `docs/superpowers/` is ignored. Confirm with `git status --short docs/superpowers` showing nothing before committing.)

---

### Task 13: `SPEC.md` states the rules

**Files:**
- Modify: `SPEC.md` sections 3.3, 3.4, 3.7, 4, 5.1, 5.2 (5.3 was done in Task 9)

- [ ] **Step 1: Section 3.3, the key table**

Change four rows:

- `unit`: append `; a \`string\` has none (\`schema\`)`.
- `limits`: append `; a \`string\` states none, its range being the byte range of its datatype (\`schema\`)`.
- `init`: replace the meaning with `raw initial value, or the text of a \`string\` ([section 3.4](#34-conversions)); \`null\` means implicit zero initialisation`.
- `a2l`: replace the meaning with `` `export`, `format`, `display_identifier`; a `string` takes no `format` (`schema`) ``.

- [ ] **Step 2: Section 3.3, the `init` bullet**

After the sentence ending "nor against the enumerators of an enum conversion." insert:

```
  A `string` object ([section 3.4](#34-conversions)) **may** state its `init` as a JSON
  string instead: printable ASCII, code points 0x20 to 0x7E, and shorter than its dimension
  so that the terminating zero fits, else `init-invalid`; the integer and the list spelling
  stay open to it, the list being how a fixed width field without a terminator is written.
  A string spelling on any other object is `init-invalid`, and a quoted number is text, not
  the number.
```

- [ ] **Step 3: Section 3.4**

Add `{ "kind": "string" }` as a fourth line of the json block. After the `enum` bullet insert:

```
- `string` reads a one dimensional array of `uint8` or `sint8` as text, one byte per
  character. `kind` **must** be stated, because the conversion has no key of its own to be
  inferred from. It sits on a `measurement` or a `value_block` stating exactly one
  dimension, on a `value` member of one dimension ([section 3.7](#37-type-description)), or
  on a scalar type, whose declarations and members then state the dimension. Any other
  datatype, kind or shape, a `bits` member, and a `unit`, `limits` or `a2l.format` beside
  it are `schema`, where they are written; for a declaration or member naming a string
  type, at that declaration or member, with a note at the type. Physical and raw value
  coincide, so the limits of a string are the raw range of its datatype. An array of
  strings is written as an array of structures with a string member, because the A2L
  format has no string arrays.
```

In the `kind` **may** be omitted bullet, change "and one stating nothing, `{}`, is the identity." to "and one stating nothing, `{}`, is the identity; a `string` is never inferred."

- [ ] **Step 4: Section 3.7**

In the struct bullet, after "a `bits` member takes no `dimensions`." add: "A `value` member under a `string` conversion, stated or fixed by the scalar type it names, states exactly one dimension, and a `bits` member carries no string (`schema`)." In the scalar bullet, after "`unit`, `limits` and `description` are optional." add: "It **may** carry a `string` conversion, under the rules of [section 3.4](#34-conversions), the length being the naming declaration's or member's to state."

- [ ] **Step 5: Section 4**

In the `schema` paragraph change "such as a zero `factor`, an enum conversion on a non-integer datatype, or a key restated" to "such as a zero `factor`, an enum conversion on a non-integer datatype, a `string` conversion where [section 3.4](#34-conversions) refuses one, or a key restated". Change the `init-invalid` line to:

```
- `init-invalid`: an initial value or an enumerator does not fit the datatype or the shape,
  or a string init is not printable ASCII, leaves no room for its terminator, or is written
  on an object that is not a string.
```

- [ ] **Step 6: Sections 5.1 and 5.2**

In 5.1, after the sentence ending "the `typedef enum` being for the enumerators alone." add: "A `string` object is declared as the byte array it is, and a text `init` is offered as a C string literal with `"`, `\` and `?` escaped, the rest of the array being zero by the rules of C." In 5.2, change the first bullet to:

```
- `MEASUREMENT` for every measurement, `CHARACTERISTIC` for parameters, value blocks,
  curves and maps, `AXIS_PTS` for axes. A value block under a `string` conversion is a
  `CHARACTERISTIC` of type `ASCII` whose length is a `NUMBER`, deposited through the value
  layout of its datatype, with `NO_COMPU_METHOD`, the raw range of the datatype as limits
  and no `MATRIX_DIM`; a string measurement is the `UBYTE` or `SBYTE` array it is, with its
  `MATRIX_DIM` and an `ANNOTATION` labelled `string` saying that the format has no string
  measurement, which no version of it has.
```

and in the `COMPU_METHOD` bullet append "; a string gets no method".

- [ ] **Step 7: Verify, commit, push**

Run: `pytest tests/test_documentation.py tests/test_transcripts.py -q --no-cov`
Expected: PASS.

```bash
git add SPEC.md
git commit -m "specify the string conversion" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push
```

---

### Task 14: The documentation pages, the README and the changelog

**Files:**
- Modify: `docs/file_formats/conversions.rst`, `docs/file_formats/variable_definition.rst`, `docs/file_formats/types.rst`, `docs/generated_artefacts.rst`, `docs/consistency_checks.rst`, `docs/concept.rst`, `README.md`, `CHANGELOG.md`
- Test: `tests/test_transcripts.py`, `tests/test_documentation.py`

- [ ] **Step 1: The conversions page**

In `docs/file_formats/conversions.rst`: add `{ "kind": "string" }` to the json block near the top; in the "``kind`` may be omitted" paragraph append "A string is the one kind that is always spelled out: a conversion with no key of its own is the identity."; change "All three kinds are at work in that demo" to "All four kinds are at work in that demo" and extend the sentence with "and the quoted text of ``SoftwareLabel`` for the string" (the transcript beneath it was refreshed in Task 12). Insert a new section between `enum` and "Limits, and where they come from":

```rst
string
------

Some byte arrays are not numbers at all: a software label, a vehicle identification number, a
part number in calibration memory, the name of the current state written into RAM for a
display. A string conversion says so. The storage stays what it is - a ``uint8`` or ``sint8``
array of one dimension, its length in bytes - and the conversion says the bytes are read as
text, one character per byte, which is what a consumer has to agree with to read them at all.

.. code-block:: json

   {
     "name": "SoftwareLabel",
     "kind": "value_block",
     "description": "Software label of the controller, as text",
     "datatype": "uint8",
     "conversion": { "kind": "string" },
     "dimensions": [16],
     "init": "V1.2.3",
     "volatile": false
   }

``kind`` is always written for a string, since the conversion has no key of its own to be
recognised by, and ``{}`` is the identity. Four rules hold wherever a string is stated - on a
definition, on a :doc:`structure member <types>` or on a scalar type - and a file breaking one
is refused when it is read:

* the datatype is ``uint8`` or ``sint8``, one byte per character;
* the shape is exactly one dimension, so the kind is ``measurement`` or ``value_block``, and
  a member is a ``value`` member with one dimension; an array of strings is written as an
  array of structures with a string member, because the a2l format has no string arrays;
* no ``unit``, no ``limits`` and no ``a2l.format``: text has none of them, and the limits of
  a string are the byte range of its datatype;
* a scalar type may be a string, and the declarations and members naming it state the
  length.

The ``init`` of a string may be written as text: printable ASCII, and shorter than the
dimension so that the terminating zero fits - a string that exactly fills its array is legal
c and refused by C++, and nobody reading the generated file can tell that the terminator is
missing. The integer and list spellings stay available, the list being how a fixed width field
without a terminator is written. In c the text becomes a string literal and the compiler fills
the rest of the array with zero:

.. code-block:: c

   /** Software label of the controller, as text (calibration value block) */
   const uint8_t SoftwareLabel[16] = "V1.2.3";

In the a2l a calibration string is a ``CHARACTERISTIC`` of type ``ASCII``, the form Vector's
own files use, over the ordinary record layout of its datatype, with no compu method and the
length as a ``NUMBER``:

.. code-block:: text

   /begin CHARACTERISTIC SoftwareLabel "Software label of the controller, as text"
     ASCII 0x00000000 RL_VALUES_UBYTE 0 NO_COMPU_METHOD 0 255
     SYMBOL_LINK "SoftwareLabel" 0
     NUMBER 16
   /end CHARACTERISTIC

A string *measurement* is a different matter, and the difference is the format's: no version
of ASAP2 has a string measurement, its datatypes being numbers only. DDD therefore describes
one as the byte array it is, with a ``MATRIX_DIM``, and adds an ``ANNOTATION`` - the
documented place for a note to the calibration engineer, which tools show in the object's
properties - so that nobody wonders why the tool shows numbers:

.. code-block:: text

   /begin MEASUREMENT StateName "Name of the current state, as text"
     UBYTE NO_COMPU_METHOD 0 0 0 255
     ECU_ADDRESS 0x00000000
     SYMBOL_LINK "StateName" 0
     MATRIX_DIM 16 1 1
     /begin ANNOTATION
       ANNOTATION_LABEL "string"
       /begin ANNOTATION_TEXT
         "16 bytes of text; ASAP2 1.6.1 has no string measurement, so the tool shows the bytes"
       /end ANNOTATION_TEXT
     /end ANNOTATION
   /end MEASUREMENT

No finding is raised for it: the author cannot change what the format lacks. Everything else
reads the string as text - the dictionary carries it, the generated c initialises it, and a
component that reads the bytes as numbers while another writes text is ``definition-mismatch``,
exactly as any other disagreement about a conversion.
```

(Paste the two a2l blocks from `ddd generate a2l examples/demo/demo.ddd.json -o <scratch>` rather than trusting the text above; the runner does not check these blocks, the reader does.) In the "Limits, and where they come from" list add `* **string** - the byte range of the datatype, 0 .. 255 for a ``uint8``; nobody may state others.` and in "One compu method per conversion, unit and format" append "A string gets no method at all: it has no unit, and no method reads a byte as a character."

- [ ] **Step 2: The other pages**

- `docs/file_formats/variable_definition.rst`: in the key table, append to the ``unit`` row "A string has none.", to the ``limits`` row "A string states none; its range is the byte range of its datatype.", to the ``init`` row "A string object may write it as text; see :doc:`conversions`.", and to the ``a2l`` row "A string takes no ``format``.". In "Initial values", after the first paragraph add: "A string object may state its ``init`` as text instead - printable ASCII, shorter than the dimension so that the terminator fits - and the c carries it as a string literal; the :doc:`conversions page <conversions>` shows one."
- `docs/file_formats/types.rst`: in the scalar type's ``conversion`` row append "A scalar type may be a string, in which case the declarations and members naming it state the length." In the paragraph beginning "A member says what its bytes *mean*" append: "A member under a string conversion, its own or its type's, is a ``value`` member of exactly one dimension, and states no unit, limits or format, as a definition would not."
- `docs/generated_artefacts.rst`: in the "What is emitted for what" table change the ``MEASUREMENT`` row to "every ``measurement``; a string one as the byte array it is, with an ``ANNOTATION``", the ``VAL_BLK`` row to "every ``value_block`` that is not a string", and add a row ``CHARACTERISTIC ... ASCII`` / "every ``value_block`` under a string conversion, with a ``NUMBER``". After the "Enumerations" section add a short "Strings" section pointing at the :doc:`conversions page <file_formats/conversions>` for both records, with the ``SoftwareLabel`` record pasted from the generated demo.
- `docs/consistency_checks.rst`: append to the ``schema`` row "It is also what refuses a string conversion on anything but a one dimensional byte array, or beside a unit, limits or a display format."; append to the ``init-invalid`` row "or a string init that is not printable ASCII, leaves no room for its terminator, or sits on an object that is not a string."
- `docs/concept.rst` line 267: "reads: the identity, a linear factor and offset, an enumeration, or text."

- [ ] **Step 3: The README and the changelog**

In `README.md`, under "Conversions", add `{ "kind": "string" }` to the json block and the bullet "* `string` reads a one dimensional `uint8` or `sint8` array as text; `kind` is always written for it, and its `init` may be a string". In the a2l bullets add "* a value block under a string conversion becomes a `CHARACTERISTIC` of type `ASCII` with a `NUMBER`; a string measurement stays the byte array it is, with an `ANNOTATION` saying so, because the format has no string measurement".

In `CHANGELOG.md`, insert before `## 0.9.0`:

```markdown
## Unreleased

* **Strings.**  A fourth conversion kind, `{"kind": "string"}`, reads a one dimensional
  `uint8` or `sint8` array as text, on a measurement, a value block, a structure member or a
  scalar type; its `init` may be written as a string, printable ASCII shorter than the
  dimension, and the generated c carries it as a string literal.  A calibration string
  reaches the a2l as a `CHARACTERISTIC` of type `ASCII` with a `NUMBER`; a string measurement
  stays the byte array it is, with an `ANNOTATION` saying so, because no version of the
  format has a string measurement.  A string states no unit, limits or display format, and
  the rules are `schema` where they are broken; a wrong string init is `init-invalid`.
  **Migration:** none for a description file - no existing file carries the kind, and `{}`
  is the identity it always was.  The dumped dictionary is format 8, for the new kind and the
  string `init`; a format 7 dictionary reads back unchanged, and a reader that only knows 7
  refuses a format 8 file as it refuses any newer one.  One spelling changes meaning: a
  quoted number as an `init`, `"12"`, used to be read as the number and is now text, refused
  on anything but a string object as `init-invalid` - spell the number as a number.
```

- [ ] **Step 4: Verify, commit, push**

Run: `pytest tests/test_transcripts.py tests/test_documentation.py -q --no-cov`, then the sphinx build the way the developer page describes it (with `JAVA` and `PLANTUML_JAR` set on the maintainer's machine), and finally `pytest -q`.
Expected: PASS, and the docs build without warnings.

```bash
ruff format src tests && ruff check src tests && mypy
git add docs/file_formats/conversions.rst docs/file_formats/variable_definition.rst docs/file_formats/types.rst docs/generated_artefacts.rst docs/consistency_checks.rst docs/concept.rst README.md CHANGELOG.md
git commit -m "document the string conversion" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push
```

---

## Self-review against the spec

- Spec 3.1 spelling and model: Task 1. Spec 3.2 rules in three places, shared: Task 2. Spec 3.2 rules for a declaration or member naming a string type, with the note and the drop: Task 5. Spec 3.3 leaves: Tasks 5 and 7. Spec 4 init spelling, content, length, wrong object, every reader: Tasks 3, 4, 6, 10. Spec 5 limits, comparison, readings: Tasks 1, 4, 11. Spec 6 c literal and escapes: Task 6. Spec 7.1 and 7.2 records, 7.3 no method: Tasks 7 and 8. Spec 8 format 8 and schemas: Task 9. Spec 9 editor and command line: Task 10 (completion follows from the regenerated schemas of Task 9). Spec 10 checks: no identifier added, verified by the assertions on `checks(bag)` throughout. Spec 11 tests: one task per file named there. Spec 12 documentation and demo: Tasks 12, 13, 14.
- Names used across tasks: `StringConversion` (Task 1) in Tasks 2, 4, 5, 7, 8; `refuse_string_misuse`, `check_string_shape` (Task 2) in Task 5; `check_string_member_shape` (Task 2) in Task 5; `c_string_literal` (Task 6) only there; `CharacteristicView.number` and `MeasurementView.annotation` (Tasks 7 and 8) in their templates.
