"""Ordered, timing-conservative B1 feature and class contracts."""

from enum import StrEnum
from types import MappingProxyType

from app.ml.feature_schema import PREDICTION_FEATURES, SourceStage


class PredictionStage(StrEnum):
    ENROLLMENT = "ENROLLMENT"
    FIRST_SEMESTER = "FIRST_SEMESTER"


class ModelTargetType(StrEnum):
    BINARY_DROPOUT = "BINARY_DROPOUT"
    MULTICLASS_OUTCOME = "MULTICLASS_OUTCOME"


class AcademicOutcome(StrEnum):
    DROPOUT = "DROPOUT"
    ENROLLED = "ENROLLED"
    GRADUATE = "GRADUATE"


OUTCOME_ENCODING = MappingProxyType({"Dropout": 0, "Enrolled": 1, "Graduate": 2})
CLASS_LABELS = tuple(item.value for item in AcademicOutcome)
STAGE_FEATURES = MappingProxyType(
    {
        stage: tuple(
            feature
            for feature in PREDICTION_FEATURES
            if feature.source_stage == SourceStage.ENROLLMENT
            or (
                stage == PredictionStage.FIRST_SEMESTER
                and feature.source_stage == SourceStage.FIRST_SEMESTER
            )
        )
        for stage in PredictionStage
    }
)
SCHEMA_VERSIONS = MappingProxyType(
    {
        PredictionStage.ENROLLMENT: "uci697-enrollment-outcome-v1",
        PredictionStage.FIRST_SEMESTER: "uci697-first-semester-outcome-v1",
    }
)
MODEL_VERSIONS = MappingProxyType(
    {
        PredictionStage.ENROLLMENT: "enrollment-outcome-v1",
        PredictionStage.FIRST_SEMESTER: "first-semester-outcome-v1",
    }
)


def feature_names(stage: PredictionStage) -> tuple[str, ...]:
    return tuple(feature.name for feature in STAGE_FEATURES[stage])
