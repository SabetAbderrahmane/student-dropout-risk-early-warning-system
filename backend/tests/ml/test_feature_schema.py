from app.db.base import Base
from app.ml.feature_schema import (
    BINARY_TARGET_ENCODING,
    EXCLUDED_SECOND_SEMESTER_OFFICIAL_NAMES,
    EXCLUDED_TARGET_OFFICIAL_NAMES,
    PREDICTION_FEATURES,
    SourceStage,
)
from app.models import AdmissionRecord, FirstSemesterRecord, Student  # noqa: F401

EXPECTED_CANONICAL_NAMES = (
    "marital_status_code",
    "application_mode_code",
    "application_order",
    "course_code",
    "daytime_evening_attendance",
    "previous_qualification_code",
    "previous_qualification_grade",
    "nationality_code",
    "mother_qualification_code",
    "father_qualification_code",
    "mother_occupation_code",
    "father_occupation_code",
    "admission_grade",
    "displaced",
    "educational_special_needs",
    "debtor",
    "tuition_fees_up_to_date",
    "gender_code",
    "scholarship_holder",
    "age_at_enrollment",
    "international_student",
    "first_semester_credited_units",
    "first_semester_enrolled_units",
    "first_semester_evaluations",
    "first_semester_approved_units",
    "first_semester_average_grade",
    "first_semester_without_evaluations",
    "unemployment_rate",
    "inflation_rate",
    "gdp",
)


def test_contract_contains_every_eligible_feature_once_in_canonical_order() -> None:
    assert (
        tuple(feature.name for feature in PREDICTION_FEATURES)
        == EXPECTED_CANONICAL_NAMES
    )
    assert len(PREDICTION_FEATURES) == 30


def test_normalized_and_official_names_are_unique() -> None:
    normalized = [feature.name for feature in PREDICTION_FEATURES]
    official = [feature.official_name for feature in PREDICTION_FEATURES]

    assert len(normalized) == len(set(normalized))
    assert len(official) == len(set(official))


def test_second_semester_and_target_are_absent_from_prediction_inputs() -> None:
    official = {feature.official_name for feature in PREDICTION_FEATURES}

    assert len(EXCLUDED_SECOND_SEMESTER_OFFICIAL_NAMES) == 6
    assert official.isdisjoint(EXCLUDED_SECOND_SEMESTER_OFFICIAL_NAMES)
    assert len(EXCLUDED_TARGET_OFFICIAL_NAMES) == 1
    assert official.isdisjoint(EXCLUDED_TARGET_OFFICIAL_NAMES)
    assert all(
        feature.source_stage not in {SourceStage.SECOND_SEMESTER, SourceStage.TARGET}
        for feature in PREDICTION_FEATURES
    )


def test_system_identifiers_are_not_prediction_features() -> None:
    names = {feature.name for feature in PREDICTION_FEATURES}

    assert names.isdisjoint({"id", "student_id", "student_number", "name", "gender"})


def test_database_schema_can_store_every_prediction_feature() -> None:
    for feature in PREDICTION_FEATURES:
        table = Base.metadata.tables[feature.storage_table]
        assert feature.storage_column in table.c, (
            f"{feature.name} has no storage column "
            f"{feature.storage_table}.{feature.storage_column}"
        )


def test_binary_target_encoding_is_frozen() -> None:
    assert dict(BINARY_TARGET_ENCODING) == {
        "Dropout": 1,
        "Graduate": 0,
        "Enrolled": 0,
    }
