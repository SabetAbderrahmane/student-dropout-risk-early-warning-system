"""Canonical, ordered prediction feature contract for UCI dataset 697.

This module defines inputs only. System identifiers, second-semester variables,
and the outcome target are deliberately outside ``PREDICTION_FEATURES``.
"""

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final


class SourceStage(StrEnum):
    ENROLLMENT = "ENROLLMENT"
    FIRST_SEMESTER = "FIRST_SEMESTER"
    SECOND_SEMESTER = "SECOND_SEMESTER"
    MACROECONOMIC = "MACROECONOMIC"
    TARGET = "TARGET"


class FeatureDataType(StrEnum):
    INTEGER = "INTEGER"
    FLOAT = "FLOAT"


class FeatureKind(StrEnum):
    CATEGORICAL = "CATEGORICAL"
    NUMERIC = "NUMERIC"
    BINARY = "BINARY"


@dataclass(frozen=True, slots=True)
class PredictionFeature:
    name: str
    official_name: str
    data_type: FeatureDataType
    kind: FeatureKind
    required: bool
    source_stage: SourceStage
    storage_table: str
    storage_column: str
    allowed_values: frozenset[int] | None = None
    minimum: int | float | None = None
    maximum: int | float | None = None


def _feature(
    name: str,
    official_name: str,
    data_type: FeatureDataType,
    kind: FeatureKind,
    source_stage: SourceStage,
    storage_table: str,
    storage_column: str | None = None,
    *,
    allowed_values: set[int] | None = None,
    minimum: int | float | None = None,
    maximum: int | float | None = None,
) -> PredictionFeature:
    return PredictionFeature(
        name=name,
        official_name=official_name,
        data_type=data_type,
        kind=kind,
        required=True,
        source_stage=source_stage,
        storage_table=storage_table,
        storage_column=storage_column or name,
        allowed_values=(
            frozenset(allowed_values) if allowed_values is not None else None
        ),
        minimum=minimum,
        maximum=maximum,
    )


I = FeatureDataType.INTEGER
F = FeatureDataType.FLOAT
C = FeatureKind.CATEGORICAL
N = FeatureKind.NUMERIC
B = FeatureKind.BINARY
E = SourceStage.ENROLLMENT
S1 = SourceStage.FIRST_SEMESTER
M = SourceStage.MACROECONOMIC

_BINARY_CODES = {0, 1}
_MARITAL_STATUS_CODES = {1, 2, 3, 4, 5, 6}
_APPLICATION_MODE_CODES = {
    1,
    2,
    5,
    7,
    10,
    15,
    16,
    17,
    18,
    26,
    27,
    39,
    42,
    43,
    44,
    51,
    53,
    57,
}
_COURSE_CODES = {
    33,
    171,
    8014,
    9003,
    9070,
    9085,
    9119,
    9130,
    9147,
    9238,
    9254,
    9500,
    9556,
    9670,
    9773,
    9853,
    9991,
}
_PREVIOUS_QUALIFICATION_CODES = {
    1,
    2,
    3,
    4,
    5,
    6,
    9,
    10,
    12,
    14,
    15,
    19,
    38,
    39,
    40,
    42,
    43,
}
_NATIONALITY_CODES = {
    1,
    2,
    6,
    11,
    13,
    14,
    17,
    21,
    22,
    24,
    25,
    26,
    32,
    41,
    62,
    100,
    101,
    103,
    105,
    108,
    109,
}
_MOTHER_QUALIFICATION_CODES = {
    1,
    2,
    3,
    4,
    5,
    6,
    9,
    10,
    11,
    12,
    14,
    18,
    19,
    22,
    26,
    27,
    29,
    30,
    34,
    35,
    36,
    37,
    38,
    39,
    40,
    41,
    42,
    43,
    44,
}
_FATHER_QUALIFICATION_CODES = _MOTHER_QUALIFICATION_CODES | {13, 20, 25, 31, 33}
_MOTHER_OCCUPATION_CODES = {
    0,
    1,
    2,
    3,
    4,
    5,
    6,
    7,
    8,
    9,
    10,
    90,
    99,
    122,
    123,
    125,
    131,
    132,
    134,
    141,
    143,
    144,
    151,
    152,
    153,
    171,
    173,
    175,
    191,
    192,
    193,
    194,
}
_FATHER_OCCUPATION_CODES = {
    0,
    1,
    2,
    3,
    4,
    5,
    6,
    7,
    8,
    9,
    10,
    90,
    99,
    101,
    102,
    103,
    112,
    114,
    121,
    122,
    123,
    124,
    131,
    132,
    134,
    135,
    141,
    143,
    144,
    151,
    152,
    153,
    154,
    161,
    163,
    171,
    172,
    174,
    175,
    181,
    182,
    183,
    192,
    193,
    194,
    195,
}


PREDICTION_FEATURES: Final[tuple[PredictionFeature, ...]] = (
    _feature(
        "marital_status_code",
        "Marital Status",
        I,
        C,
        E,
        "students",
        allowed_values=_MARITAL_STATUS_CODES,
    ),
    _feature(
        "application_mode_code",
        "Application mode",
        I,
        C,
        E,
        "admission_records",
        allowed_values=_APPLICATION_MODE_CODES,
    ),
    _feature(
        "application_order",
        "Application order",
        I,
        N,
        E,
        "admission_records",
        minimum=0,
        maximum=9,
    ),
    _feature(
        "course_code",
        "Course",
        I,
        C,
        E,
        "admission_records",
        allowed_values=_COURSE_CODES,
    ),
    _feature(
        "daytime_evening_attendance",
        "Daytime/evening attendance",
        I,
        B,
        E,
        "admission_records",
        allowed_values=_BINARY_CODES,
    ),
    _feature(
        "previous_qualification_code",
        "Previous qualification",
        I,
        C,
        E,
        "admission_records",
        allowed_values=_PREVIOUS_QUALIFICATION_CODES,
    ),
    _feature(
        "previous_qualification_grade",
        "Previous qualification (grade)",
        F,
        N,
        E,
        "admission_records",
        minimum=0,
        maximum=200,
    ),
    _feature(
        "nationality_code",
        "Nacionality",
        I,
        C,
        E,
        "students",
        allowed_values=_NATIONALITY_CODES,
    ),
    _feature(
        "mother_qualification_code",
        "Mother's qualification",
        I,
        C,
        E,
        "admission_records",
        allowed_values=_MOTHER_QUALIFICATION_CODES,
    ),
    _feature(
        "father_qualification_code",
        "Father's qualification",
        I,
        C,
        E,
        "admission_records",
        allowed_values=_FATHER_QUALIFICATION_CODES,
    ),
    _feature(
        "mother_occupation_code",
        "Mother's occupation",
        I,
        C,
        E,
        "admission_records",
        allowed_values=_MOTHER_OCCUPATION_CODES,
    ),
    _feature(
        "father_occupation_code",
        "Father's occupation",
        I,
        C,
        E,
        "admission_records",
        allowed_values=_FATHER_OCCUPATION_CODES,
    ),
    _feature(
        "admission_grade",
        "Admission grade",
        F,
        N,
        E,
        "admission_records",
        minimum=0,
        maximum=200,
    ),
    _feature(
        "displaced", "Displaced", I, B, E, "students", allowed_values=_BINARY_CODES
    ),
    _feature(
        "educational_special_needs",
        "Educational special needs",
        I,
        B,
        E,
        "students",
        allowed_values=_BINARY_CODES,
    ),
    _feature("debtor", "Debtor", I, B, E, "students", allowed_values=_BINARY_CODES),
    _feature(
        "tuition_fees_up_to_date",
        "Tuition fees up to date",
        I,
        B,
        E,
        "students",
        allowed_values=_BINARY_CODES,
    ),
    _feature(
        "gender_code", "Gender", I, B, E, "students", allowed_values=_BINARY_CODES
    ),
    _feature(
        "scholarship_holder",
        "Scholarship holder",
        I,
        B,
        E,
        "students",
        allowed_values=_BINARY_CODES,
    ),
    _feature("age_at_enrollment", "Age at enrollment", I, N, E, "students", minimum=0),
    _feature(
        "international_student",
        "International",
        I,
        B,
        E,
        "students",
        allowed_values=_BINARY_CODES,
    ),
    _feature(
        "first_semester_credited_units",
        "Curricular units 1st sem (credited)",
        I,
        N,
        S1,
        "first_semester_records",
        "credited_units",
        minimum=0,
    ),
    _feature(
        "first_semester_enrolled_units",
        "Curricular units 1st sem (enrolled)",
        I,
        N,
        S1,
        "first_semester_records",
        "enrolled_units",
        minimum=0,
    ),
    _feature(
        "first_semester_evaluations",
        "Curricular units 1st sem (evaluations)",
        I,
        N,
        S1,
        "first_semester_records",
        "evaluations",
        minimum=0,
    ),
    _feature(
        "first_semester_approved_units",
        "Curricular units 1st sem (approved)",
        I,
        N,
        S1,
        "first_semester_records",
        "approved_units",
        minimum=0,
    ),
    _feature(
        "first_semester_average_grade",
        "Curricular units 1st sem (grade)",
        F,
        N,
        S1,
        "first_semester_records",
        "average_grade",
        minimum=0,
        maximum=20,
    ),
    _feature(
        "first_semester_without_evaluations",
        "Curricular units 1st sem (without evaluations)",
        I,
        N,
        S1,
        "first_semester_records",
        "without_evaluations",
        minimum=0,
    ),
    _feature("unemployment_rate", "Unemployment rate", F, N, M, "admission_records"),
    _feature("inflation_rate", "Inflation rate", F, N, M, "admission_records"),
    _feature("gdp", "GDP", F, N, M, "admission_records"),
)

FEATURES_BY_NAME: Final = MappingProxyType(
    {feature.name: feature for feature in PREDICTION_FEATURES}
)

EXCLUDED_SECOND_SEMESTER_OFFICIAL_NAMES: Final[tuple[str, ...]] = (
    "Curricular units 2nd sem (credited)",
    "Curricular units 2nd sem (enrolled)",
    "Curricular units 2nd sem (evaluations)",
    "Curricular units 2nd sem (approved)",
    "Curricular units 2nd sem (grade)",
    "Curricular units 2nd sem (without evaluations)",
)
EXCLUDED_TARGET_OFFICIAL_NAMES: Final[tuple[str, ...]] = ("Target",)

# The future binary classifier must use these exact labels and values.
BINARY_TARGET_ENCODING: Final = MappingProxyType(
    {"Dropout": 1, "Graduate": 0, "Enrolled": 0}
)


def validate_feature_value(name: str, value: int | float | None) -> int | float | None:
    """Validate one API value against the same canonical contract used by ML."""
    if value is None:
        return None
    feature = FEATURES_BY_NAME[name]
    if feature.allowed_values is not None and value not in feature.allowed_values:
        raise ValueError(f"{name} must be one of {sorted(feature.allowed_values)}")
    if feature.minimum is not None and value < feature.minimum:
        raise ValueError(f"{name} must be greater than or equal to {feature.minimum}")
    if feature.maximum is not None and value > feature.maximum:
        raise ValueError(f"{name} must be less than or equal to {feature.maximum}")
    return value
