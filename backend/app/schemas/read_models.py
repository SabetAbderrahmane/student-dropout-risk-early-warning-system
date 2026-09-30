"""Stable response contracts for the Phase 8 Stitch read endpoints."""

from datetime import date, datetime
from math import ceil
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class Counts(BaseModel):
    total: int
    prediction_ready: int
    with_latest_prediction: int


class RiskCounts(BaseModel):
    low: int
    medium: int
    high: int


class WarningCounts(BaseModel):
    active: int
    pending_review: int
    confirmed: int
    dismissed: int


class InterventionCounts(BaseModel):
    active: int
    planned: int
    in_progress: int
    action_required: int
    completed: int


class FollowUpCounts(BaseModel):
    due_today: int
    overdue: int


class ModelSummary(BaseModel):
    version: str | None = None
    name: str | None = None
    trained_at: datetime | None = None
    low_threshold: float | None = None
    high_threshold: float | None = None


class DataFreshness(BaseModel):
    last_import_at: datetime | None = None
    last_prediction_at: datetime | None = None


class WarningActivity(BaseModel):
    date: date
    created: int
    confirmed: int
    dismissed: int


class InterventionActivity(BaseModel):
    date: date
    created: int
    completed: int


class Advisor(BaseModel):
    user_id: UUID
    full_name: str


class AttentionStudent(BaseModel):
    student_id: UUID
    student_number: str
    name: str
    probability: float
    risk_level: str
    warning_id: UUID
    priority: str
    review_state: str
    assigned_advisor: Advisor | None
    predicted_at: datetime
    top_explanation_factors: list[dict[str, Any]]


class DashboardOverview(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    students: Counts
    risk_distribution: RiskCounts
    warnings: WarningCounts
    interventions: InterventionCounts
    follow_ups: FollowUpCounts
    model: ModelSummary
    data_freshness: DataFreshness
    warning_activity: list[WarningActivity]
    intervention_activity: list[InterventionActivity]
    attention_students: list[AttentionStudent]


class Course(BaseModel):
    code: int
    label: str


class RegistryAdmission(BaseModel):
    method: str
    admission_grade: float


class SemesterOne(BaseModel):
    credited_units: int
    enrolled_units: int
    evaluations: int
    approved_units: int
    average_grade: float
    without_evaluations: int | None
    approval_rate: float | None


class RegistrySemesterOne(BaseModel):
    average_grade: float
    enrolled_units: int
    approved_units: int
    approval_rate: float | None


class PredictionSummary(BaseModel):
    id: UUID
    probability: float
    risk_level: str
    predicted_at: datetime


class RegistryWarning(BaseModel):
    id: UUID
    state: str
    priority: str


class RegistryIntervention(BaseModel):
    id: UUID
    status: str


class RegistryRow(BaseModel):
    student_id: UUID
    student_number: str
    name: str
    course: Course | None
    admission: RegistryAdmission | None
    semester_one: RegistrySemesterOne | None
    prediction_readiness: Literal["READY", "NOT_READY"]
    latest_prediction: PredictionSummary | None
    warning: RegistryWarning | None
    case_owner: Advisor | None
    intervention: RegistryIntervention | None
    last_activity_at: datetime | None


class RegistryPage(BaseModel):
    items: list[RegistryRow]
    page: int
    page_size: int
    total: int
    total_pages: int

    @classmethod
    def create(cls, *, items: list[RegistryRow], page: int, page_size: int, total: int):
        return cls(items=items, page=page, page_size=page_size, total=total,
                   total_pages=ceil(total / page_size) if total else 0)


class ProfileStudent(BaseModel):
    id: UUID
    student_number: str
    name: str
    gender: str | None
    marital_status_code: int | None
    nationality_code: int | None
    displaced: int | None
    educational_special_needs: int | None
    debtor: int | None
    tuition_fees_up_to_date: int | None
    gender_code: int | None
    scholarship_holder: int | None
    age_at_enrollment: int | None
    international_student: int | None


class ProfileAdmission(BaseModel):
    admission_method: str
    admission_grade: float
    previous_qualification: str
    previous_qualification_grade: float
    application_mode_code: int | None
    application_mode_label: str | None
    application_order: int | None
    course_code: int | None
    course_label: str | None
    daytime_evening_attendance: int | None
    previous_qualification_code: int | None
    previous_qualification_label: str | None
    mother_qualification_code: int | None
    father_qualification_code: int | None
    mother_occupation_code: int | None
    father_occupation_code: int | None
    unemployment_rate: float | None
    inflation_rate: float | None
    gdp: float | None


class Readiness(BaseModel):
    status: Literal["READY", "NOT_READY"]
    required_feature_count: int
    available_feature_count: int
    missing_features: list[str]


class ProfilePrediction(PredictionSummary):
    model_version: str
    explanation: list[dict[str, Any]]


class ProfileReview(BaseModel):
    id: UUID
    decision: str
    note: str
    reviewer: Advisor | None
    reviewed_at: datetime


class ProfileWarning(BaseModel):
    id: UUID
    prediction_id: UUID
    risk_level: str
    priority: str
    review_state: str
    assigned_advisor: Advisor | None
    created_at: datetime
    reviews: list[ProfileReview]


class ProfileIntervention(BaseModel):
    id: UUID
    warning_id: UUID
    type: str
    title: str
    priority: str
    status: str
    assigned_advisor: Advisor | None
    start_date: date
    target_date: date | None
    created_at: datetime
    completed_at: datetime | None
    completion_outcome: str | None


class ProfileFollowUp(BaseModel):
    id: UUID
    intervention_id: UUID
    scheduled_for: datetime
    method: str
    purpose: str
    effective_status: str
    outcome: str | None
    assigned_advisor: Advisor | None
    completed_at: datetime | None


class TimelineEvent(BaseModel):
    type: str
    occurred_at: datetime
    title: str
    summary: str
    entity_id: UUID


class StudentProfile(BaseModel):
    student: ProfileStudent
    admission: ProfileAdmission | None
    semester_one: SemesterOne | None
    prediction_readiness: Readiness
    latest_prediction: ProfilePrediction | None
    prediction_history: list[ProfilePrediction]
    active_warning: ProfileWarning | None
    warning_history: list[ProfileWarning]
    interventions: list[ProfileIntervention]
    follow_ups: list[ProfileFollowUp]
    timeline: list[TimelineEvent]
