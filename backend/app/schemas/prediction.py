from datetime import datetime
from math import ceil
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

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
    created_warnings: Literal[0] = 0
    model_version: str
    completed_at: datetime


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
