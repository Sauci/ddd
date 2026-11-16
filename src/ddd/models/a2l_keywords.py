"""The words ASAP2 1.6.1 keeps for itself, which a name reaching the a2l may not be.

Table 5 of the standard says identifiers must not match the keywords and enumeration values of
its index. This module is DDD's own list of them, written from the 1.6.1 grammar rather than
copied from a file: the standard's text is not part of this project. It holds

* every block and attribute keyword the grammar defines, ``/begin`` blocks and the attributes
  of each alike, with the per axis families (``X``, ``Y``, ``Z``, ``4`` and ``5``) spelled out,
* the values the grammar fixes: the datatypes, the object and axis types, the conversion
  types, the byte orders, the index modes, the monotony values, the memory types and the like.

The words inside an ``IF_DATA`` block (``XCP``, ``DAQ_EVENT``, ``EVENT`` and the rest of what
DDD writes for an object's event) belong to the interface's own metalanguage, not to ASAP2,
and are not here: a measurement called ``EVENT`` is a name.

Like :mod:`ddd.models.reserved`, which does the same for c, it is the one place in
:mod:`ddd.models` that spells out an output format, and the layering test names it: the a2l is
an output DDD always writes, and "this name is usable" is a property of the names a project
gives, checked before any backend runs.

A word of this list is matched exactly - the format is case sensitive, so ``Map`` is a name and
``MAP`` is the keyword. The list is the standard's and not the template's, but every word the
a2l template (outside its ``IF_DATA`` blocks), the record layouts and the writer's own code
spell is in it (``tests/test_a2l_names.py`` reads them off).
"""

from __future__ import annotations

from typing import Final

_AXIS_FAMILIES: Final = ("X", "Y", "Z", "4", "5")

_PER_AXIS: Final = (
    "AXIS_PTS_{}",
    "AXIS_RESCALE_{}",
    "DIST_OP_{}",
    "FIX_NO_AXIS_PTS_{}",
    "NO_AXIS_PTS_{}",
    "NO_RESCALE_{}",
    "OFFSET_{}",
    "RIP_ADDR_{}",
    "SHIFT_OP_{}",
    "SRC_ADDR_{}",
)

_KEYWORDS: Final = """
A2ML A2ML_VERSION ADDR_EPK ALIGNMENT_BYTE ALIGNMENT_FLOAT32_IEEE ALIGNMENT_FLOAT64_IEEE
ALIGNMENT_INT64 ALIGNMENT_LONG ALIGNMENT_WORD ALTERNATE_CURVES ALTERNATE_MAPS ALTERNATE_VALUES
ANNOTATION ANNOTATION_LABEL ANNOTATION_ORIGIN ANNOTATION_TEXT ARRAY_SIZE ASAP2_VERSION
AXIS_DESCR AXIS_PTS AXIS_PTS_REF BIT_MASK BIT_OPERATION BYTE_ORDER CALIBRATION_ACCESS
CALIBRATION_HANDLE CALIBRATION_HANDLE_TEXT CALIBRATION_METHOD CHARACTERISTIC COEFFS
COEFFS_LINEAR COMPARISON_QUANTITY COMPU_METHOD COMPU_TAB COMPU_TAB_REF COMPU_VTAB
COMPU_VTAB_RANGE CPU_TYPE CURVE_AXIS_REF CUSTOMER CUSTOMER_NO DATA_SIZE DEFAULT_VALUE
DEPENDENT_CHARACTERISTIC DEPOSIT DISCRETE DISPLAY_IDENTIFIER ECU ECU_ADDRESS
ECU_ADDRESS_EXTENSION ECU_CALIBRATION_OFFSET EPK ERROR_MASK EXTENDED_LIMITS FIX_AXIS_PAR
FIX_AXIS_PAR_DIST FIX_AXIS_PAR_LIST FNC_VALUES FORMAT FORMULA FORMULA_INV FRAME
FRAME_MEASUREMENT FUNCTION FUNCTION_LIST FUNCTION_VERSION GROUP GUARD_RAILS HEADER
IDENTIFICATION IF_DATA IN_MEASUREMENT INPUT_QUANTITY LAYOUT LEFT_SHIFT LOC_MEASUREMENT
MAP_LIST MATRIX_DIM MAX_GRAD MAX_REFRESH MEASUREMENT MEMORY_LAYOUT MEMORY_SEGMENT MOD_COMMON
MOD_PAR MODULE MONOTONY NO_OF_INTERFACES NUMBER OUT_MEASUREMENT PHONE_NO PHYS_UNIT PROJECT
PROJECT_NO READ_ONLY READ_WRITE RECORD_LAYOUT REF_CHARACTERISTIC REF_GROUP REF_MEASUREMENT
REF_MEMORY_SEGMENT REF_UNIT RES_AXIS RIGHT_SHIFT ROOT SIGN_EXTEND SI_EXPONENTS
STATIC_RECORD_LAYOUT STATUS_STRING_REF STEP_SIZE SUB_FUNCTION SUB_GROUP SUPPLIER SYMBOL_LINK
SYSTEM_CONSTANT UNIT UNIT_CONVERSION USER VAR_ADDRESS VAR_CHARACTERISTIC VAR_CRITERION
VAR_FORBIDDEN_COMB VAR_MEASUREMENT VAR_NAMING VAR_SELECTOR VAR_SEPARATOR VARIANT_CODING
VERSION VIRTUAL VIRTUAL_CHARACTERISTIC USER_RIGHTS

CALIBRATION NO_CALIBRATION NOT_IN_MCD_SYSTEM OFFLINE_CALIBRATION NUMERIC ALPHA

UBYTE SBYTE UWORD SWORD ULONG SLONG A_UINT64 A_INT64 FLOAT32_IEEE FLOAT64_IEEE

VALUE CURVE MAP CUBOID CUBE_4 CUBE_5 VAL_BLK ASCII

STD_AXIS FIX_AXIS COM_AXIS CURVE_AXIS

IDENTICAL FORM LINEAR RAT_FUNC TAB_INTP TAB_NOINTP TAB_VERB

MSB_FIRST MSB_LAST LITTLE_ENDIAN BIG_ENDIAN

COLUMN_DIR ROW_DIR ALTERNATE_WITH_X ALTERNATE_WITH_Y INDEX_INCR INDEX_DECR
DIRECT PBYTE PWORD PLONG PLONGLONG

MON_INCREASE MON_DECREASE STRICT_INCREASE STRICT_DECREASE MONOTONOUS STRICT_MON NOT_MON
ABSOLUTE DIFFERENT

CODE DATA OFFLINE_DATA VARIABLES SERAM RESERVED CALIBRATION_VARIABLES EXCLUDE_FROM_FLASH
PRG_CODE PRG_DATA PRG_RESERVED ROM RAM EEPROM EPROM FLASH REGISTER INTERN EXTERN
DERIVED EXTENDED_SI

"""


def _words() -> frozenset[str]:
    words = set(_KEYWORDS.split())
    for family in _PER_AXIS:
        words.update(family.format(axis) for axis in _AXIS_FAMILIES)
    return frozenset(words)


IDENTITY_METHOD_PREFIX: Final = "physical value in "
"""What the description of the ``COMPU_METHOD`` of an identity conversion opens with, the unit
following it: a string of the a2l, so the unit it holds is held to ``MAX_STRING`` less this."""

A2L_KEYWORDS: Final[frozenset[str]] = _words()
"""Every keyword and enumeration value the module's docstring names, spelled as in the file."""


def is_a2l_keyword(name: str) -> bool:
    """Return ``True`` for a word a name reaching the a2l may not be."""
    return name in A2L_KEYWORDS
