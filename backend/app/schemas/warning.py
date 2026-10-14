from datetime import datetime
from math import ceil
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.prediction import RiskLevel
from app.models.warning import ReviewDecision, WarningPriority, WarningReviewState
from app.schemas.prediction import ExplanationFactor


class AdvisorSummary(BaseModel):
    id: UUID
    full_name: str


class StudentSummary(BaseModel):
    id: UUID
    student_number: str
    name: str


class WarningRow(BaseModel):
    revision: int
    model_config = ConfigDict(protected_namespaces=())

    id: UUID
    student_id: UUID
    student_number: str
    student_name: str
    prediction_id: UUID
    probability: float
    risk_level: RiskLevel
    priority: WarningPriority
    review_state: WarningReviewState
    assigned_advisor: AdvisorSummary | None
    predicted_at: datetime
    created_at: datetime
    updated_at: datetime
    top_explanation_factors: list[ExplanationFactor]


class ReviewResponse(BaseModel):
    id: UUID
    warning_id: UUID
    reviewer_id: UUID
    reviewer_name: str
    decision: ReviewDecision
    note: str
    reviewed_at: datetime


class WarningDetail(WarningRow):
    student: StudentSummary
    model_version: str
    prediction_explanation: list[ExplanationFactor]
    review_history: list[ReviewResponse]


class WarningPage(BaseModel):
    items: list[WarningRow]
    page: int
    page_size: int
    total: int
    total_pages: int

    @classmethod
    def create(
        cls, items: list[WarningRow], page: int, page_size: int, total: int
    ) -> "WarningPage":
        return cls(
            items=items,
            page=page,
            page_size=page_size,
            total=total,
            total_pages=ceil(total / page_size) if total else 0,
        )


class AssignmentRequest(BaseModel):
    expected_revision: int | None = Field(default=None, ge=0)
    assigned_to: UUID | None


class ReviewRequest(BaseModel):
    expected_revision: int | None = Field(default=None, ge=0)
    decision: ReviewDecision
    note: str = Field(max_length=4000)

    @field_validator("note")
    @classmethod
    def nonblank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Review note must not be blank.")
        return value


class ReconsiderationRequest(ReviewRequest):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=0)
    reason: str = Field(min_length=1, max_length=4000)

    @field_validator("reason")
    @classmethod
    def reason_nonblank(cls, value):
        return cls.nonblank(value)
