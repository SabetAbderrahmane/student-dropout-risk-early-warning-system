from datetime import datetime
from math import ceil
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

from app.ml.outcomes.contracts import (
    CLASS_LABELS,
    AcademicOutcome,
    ModelTargetType,
    PredictionStage,
)
from app.models.prediction import RiskLevel


class PredictionReadiness(BaseModel):
    status: Literal["READY", "NOT_READY"]
    required_feature_count: int
    available_feature_count: int
    missing_features: list[str]


class ExplanationFactor(BaseModel):
    feature: str
    label: str
    value: int | float
    contribution: float
    reference_value: int | float | None = None


class PredictionResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    id: UUID
    student_id: UUID
    student_number: str
    student_name: str
    probability: float
    risk_level: RiskLevel
    model_version: str
    top_explanation_factors: list[ExplanationFactor]
    predicted_at: datetime
    prediction_stage: PredictionStage = PredictionStage.FIRST_SEMESTER
    model_target_type: ModelTargetType = ModelTargetType.BINARY_DROPOUT
    predicted_outcome: AcademicOutcome | None = None
    class_probabilities: dict[str, float] | None = None
    dropout_probability: float

    @model_validator(mode="after")
    def validate_classification(self):
        from math import isfinite

        if (
            self.dropout_probability != self.probability
            or not isfinite(self.probability)
            or not 0 <= self.probability <= 1
        ):
            raise ValueError("Dropout probability must be finite and consistent")
        if self.model_target_type == ModelTargetType.BINARY_DROPOUT:
            if (
                self.predicted_outcome is not None
                or self.class_probabilities is not None
                or self.prediction_stage != PredictionStage.FIRST_SEMESTER
            ):
                raise ValueError(
                    "Binary records cannot have multiclass fields or enrollment stage"
                )
        else:
            values = self.class_probabilities
            if (
                values is None
                or set(values) != set(CLASS_LABELS)
                or self.predicted_outcome is None
            ):
                raise ValueError(
                    "Multiclass predictions require all three outcome probabilities"
                )
            if (
                any(not isfinite(p) or not 0 <= p <= 1 for p in values.values())
                or abs(sum(values.values()) - 1) > 1e-6
            ):
                raise ValueError("Class probabilities must be valid and sum to one")
            if values["DROPOUT"] != self.probability or self.predicted_outcome != max(
                CLASS_LABELS, key=lambda label: values[label]
            ):
                raise ValueError(
                    "Outcome and dropout probability must match the class probabilities"
                )
        return self


class PredictionDetail(PredictionResponse):
    feature_snapshot: dict[str, int | float]
    explanation_method: str
    created_by: UUID | None


class PredictionPage(BaseModel):
    items: list[PredictionResponse]
    page: int
    page_size: int
    total: int
    total_pages: int

    @classmethod
    def create(
        cls, *, items: list[PredictionResponse], page: int, page_size: int, total: int
    ) -> "PredictionPage":
        return cls(
            items=items,
            page=page,
            page_size=page_size,
            total=total,
            total_pages=ceil(total / page_size) if total else 0,
        )


class BatchPredictionResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    assessed: int
    skipped_not_ready: int
    created_predictions: int
    created_warnings: int
    model_version: str
    completed_at: datetime
    prediction_stage: PredictionStage = PredictionStage.FIRST_SEMESTER
    model_target_type: ModelTargetType = ModelTargetType.BINARY_DROPOUT


class DatasetSummary(BaseModel):
    name: str
    dataset_id: int


class CurrentModelResponse(BaseModel):
    id: UUID
    name: str
    version: str
    trained_at: datetime
    dataset: DatasetSummary
    feature_schema_version: str
    low_threshold: float
    high_threshold: float
    artifact_available: bool


class ConfusionMatrix(BaseModel):
    tp: int
    fp: int
    tn: int
    fn: int


class ModelPerformanceResponse(BaseModel):
    evaluation_scope: Literal["FINAL_TEST_SET"]
    sample_size: int
    accuracy: float
    precision: float
    recall: float
    f1: float
    roc_auc: float
    pr_auc: float
    brier_score: float
    confusion_matrix: ConfusionMatrix
    global_feature_importance: list[dict[str, Any]]


class StageReadiness(PredictionReadiness):
    prediction_stage: PredictionStage
    model_target_type: ModelTargetType = ModelTargetType.MULTICLASS_OUTCOME
    invalid_features: dict[str, str]
    feature_status: Literal["READY", "NOT_READY"]
    model_status: Literal["ACTIVE", "INACTIVE", "UNAVAILABLE"]
    model_version: str
    model_error: str | None = None


class StageReadinessPage(BaseModel):
    legacy: PredictionReadiness
    stages: list[StageReadiness]


class ModelValidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    student_id: UUID


class ModelCatalogEntry(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    id: UUID
    name: str
    version: str
    prediction_stage: PredictionStage
    model_target_type: ModelTargetType
    feature_schema_version: str
    feature_count: int
    class_labels: list[str]
    trained_at: datetime
    low_threshold: float
    high_threshold: float
    is_active: bool
    artifact_available: bool
    availability_error: str | None = None
    artifact_sha256: str | None = None
    validation_id: UUID | None = None
    validated_at: datetime | None = None
    evaluation: dict[str, Any]
    selection: dict[str, Any]
    probability_calibration: dict[str, Any] | None = None
    threshold_calibration: dict[str, Any]
    explanation_method: str


class ModelCatalog(BaseModel):
    items: list[ModelCatalogEntry]
