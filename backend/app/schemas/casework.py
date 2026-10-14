import enum
from datetime import date, datetime
from math import ceil
from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from app.models.casework import (
    FollowUpMethod,
    FollowUpOutcome,
    FollowUpStatus,
    InterventionOutcome,
    InterventionStatus,
    InterventionType,
)
from app.models.warning import WarningPriority, WarningReviewState
from app.schemas.warning import AdvisorSummary, StudentSummary


def nonblank(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("This field must not be blank.")
    return value


NonBlank = Annotated[str, AfterValidator(nonblank)]


class InterventionCreate(BaseModel):
    student_id: UUID
    warning_id: UUID
    type: InterventionType
    title: NonBlank = Field(max_length=250)
    description: NonBlank = Field(max_length=4000)
    priority: WarningPriority
    assigned_to: UUID
    start_date: date
    target_date: date | None = None

    @model_validator(mode="after")
    def valid_dates(self):
        if self.target_date is not None and self.target_date < self.start_date:
            raise ValueError("Target date cannot precede start date.")
        return self


class InterventionUpdate(BaseModel):
    expected_revision: int | None = Field(default=None, ge=0)
    title: NonBlank | None = Field(default=None, max_length=250)
    description: NonBlank | None = Field(default=None, max_length=4000)
    priority: WarningPriority | None = None
    assigned_to: UUID | None = None
    target_date: date | None = None
    status: InterventionStatus | None = None


class InterventionComplete(BaseModel):
    expected_revision: int | None = Field(default=None, ge=0)
    outcome: InterventionOutcome
    completion_notes: NonBlank = Field(max_length=4000)


class CancellationRequest(BaseModel):
    expected_revision: int | None = Field(default=None, ge=0)
    reason: NonBlank = Field(max_length=4000)


class InterventionNoteCreate(BaseModel):
    expected_revision: int | None = Field(default=None, ge=0)
    note: NonBlank = Field(max_length=4000)


class InterventionNoteResponse(BaseModel):
    id: UUID
    intervention_id: UUID
    author_id: UUID
    author_name: str
    note: str
    created_at: datetime


class WarningLink(BaseModel):
    id: UUID
    prediction_id: UUID
    review_state: WarningReviewState


class InterventionRow(BaseModel):
    revision: int
    id: UUID
    student: StudentSummary
    warning: WarningLink
    type: InterventionType
    title: str
    description: str
    priority: WarningPriority
    status: InterventionStatus
    assigned_advisor: AdvisorSummary
    start_date: date
    target_date: date | None
    completed_at: datetime | None
    completion_outcome: InterventionOutcome | None
    completion_notes: str | None
    created_by: UUID
    created_at: datetime
    updated_at: datetime


class InterventionDetail(InterventionRow):
    notes: list[InterventionNoteResponse]
    follow_ups: list["FollowUpRow"]


class InterventionPage(BaseModel):
    items: list[InterventionRow]
    page: int
    page_size: int
    total: int
    total_pages: int

    @classmethod
    def create(
        cls, items: list[InterventionRow], page: int, page_size: int, total: int
    ):
        return cls(
            items=items,
            page=page,
            page_size=page_size,
            total=total,
            total_pages=ceil(total / page_size) if total else 0,
        )


class FollowUpCreate(BaseModel):
    expected_revision: int | None = Field(default=None, ge=0)
    scheduled_for: datetime
    method: FollowUpMethod
    purpose: NonBlank = Field(max_length=2000)
    assigned_to: UUID

    @model_validator(mode="after")
    def timezone_required(self):
        if self.scheduled_for.tzinfo is None or self.scheduled_for.utcoffset() is None:
            raise ValueError("scheduled_for must include a timezone offset.")
        return self


class FollowUpUpdate(BaseModel):
    expected_revision: int | None = Field(default=None, ge=0)
    scheduled_for: datetime | None = None
    method: FollowUpMethod | None = None
    purpose: NonBlank | None = Field(default=None, max_length=2000)
    assigned_to: UUID | None = None

    @model_validator(mode="after")
    def timezone_required(self):
        if self.scheduled_for is not None and (
            self.scheduled_for.tzinfo is None or self.scheduled_for.utcoffset() is None
        ):
            raise ValueError("scheduled_for must include a timezone offset.")
        return self


class FollowUpComplete(BaseModel):
    expected_revision: int | None = Field(default=None, ge=0)
    outcome: FollowUpOutcome
    notes: NonBlank = Field(max_length=4000)
    next_follow_up_at: datetime | None = None

    @model_validator(mode="after")
    def timezone_required(self):
        if self.next_follow_up_at is not None and (
            self.next_follow_up_at.tzinfo is None
            or self.next_follow_up_at.utcoffset() is None
        ):
            raise ValueError("next_follow_up_at must include a timezone offset.")
        return self


class EffectiveFollowUpStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    DUE = "DUE"
    OVERDUE = "OVERDUE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class FollowUpRow(BaseModel):
    revision: int
    id: UUID
    intervention_id: UUID
    warning_id: UUID
    prediction_id: UUID
    parent_status: InterventionStatus
    parent_assigned_to: UUID
    integrity_issues: list[str]
    student: StudentSummary
    assigned_advisor: AdvisorSummary
    scheduled_for: datetime
    method: FollowUpMethod
    purpose: str
    stored_status: FollowUpStatus
    status: EffectiveFollowUpStatus
    effective_status: EffectiveFollowUpStatus
    outcome: FollowUpOutcome | None
    notes: str | None
    completed_at: datetime | None
    created_by: UUID
    created_at: datetime
    updated_at: datetime


class FollowUpPage(BaseModel):
    items: list[FollowUpRow]
    page: int
    page_size: int
    total: int
    total_pages: int

    @classmethod
    def create(cls, items: list[FollowUpRow], page: int, page_size: int, total: int):
        return cls(
            items=items,
            page=page,
            page_size=page_size,
            total=total,
            total_pages=ceil(total / page_size) if total else 0,
        )


class InterventionTransfer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assigned_to: UUID
    reason: NonBlank = Field(max_length=4000)
    expected_revision: int = Field(ge=0)


class FollowUpRecovery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: str = Field(pattern="^(ALIGN|COMPLETE|CANCEL)$")
    reason: NonBlank = Field(max_length=4000)
    expected_revision: int = Field(ge=0)
    outcome: FollowUpOutcome | None = None
    notes: NonBlank | None = Field(default=None, max_length=4000)
