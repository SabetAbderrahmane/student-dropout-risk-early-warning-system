from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.permissions import require_roles
from app.db.session import get_read_db
from app.ml.outcomes.contracts import PredictionStage
from app.models.casework import InterventionStatus
from app.models.prediction import RiskLevel
from app.models.user import User, UserRole
from app.schemas.read_models import DashboardOverview, RegistryPage, StudentProfile
from app.services.read_model_service import ReadModelService

router = APIRouter(tags=["read models"])
read_access = require_roles(
    UserRole.SYSTEM_ADMIN, UserRole.ACADEMIC_ADMIN, UserRole.ACADEMIC_ADVISOR
)


@router.get("/dashboard/overview", response_model=DashboardOverview)
def dashboard_overview(
    prediction_scope: Literal[
        "OPERATIONAL_CURRENT", "LEGACY_BINARY_FIRST_SEMESTER"
    ] = "OPERATIONAL_CURRENT",
    _: User = Depends(read_access),
    db: Session = Depends(get_read_db),
):
    return ReadModelService(db).dashboard(prediction_scope)


@router.get("/student-registry", response_model=RegistryPage)
def student_registry(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    search: str | None = Query(default=None, max_length=200),
    course_code: int | None = None,
    risk_level: RiskLevel | None = None,
    warning_state: Literal["PENDING_REVIEW", "CONFIRMED", "DISMISSED", "NONE"]
    | None = None,
    intervention_state: InterventionStatus | None = None,
    prediction_readiness: Literal["READY", "NOT_READY"] | None = None,
    assessment_state: Literal["CURRENT", "REASSESSMENT_REQUIRED", "NOT_ASSESSED"]
    | None = None,
    prediction_stage: PredictionStage | None = None,
    stage_readiness: Literal["READY", "NOT_READY"] | None = None,
    current_risk: Literal["LOW", "MEDIUM", "HIGH", "NONE"] | None = None,
    sort: Literal[
        "student_number", "name", "risk_probability", "updated_at"
    ] = "student_number",
    order: Literal["asc", "desc"] = "asc",
    _: User = Depends(read_access),
    db: Session = Depends(get_read_db),
):
    return ReadModelService(db).registry(
        page=page,
        page_size=page_size,
        search=search,
        course_code=course_code,
        risk_level=risk_level,
        warning_state=warning_state,
        intervention_state=intervention_state,
        prediction_readiness=prediction_readiness,
        sort=sort,
        order=order,
        assessment_state=assessment_state,
        prediction_stage=prediction_stage,
        stage_readiness=stage_readiness,
        current_risk=current_risk,
    )


@router.get("/students/{student_id}/profile", response_model=StudentProfile)
def student_profile(
    student_id: UUID, _: User = Depends(read_access), db: Session = Depends(get_read_db)
):
    return ReadModelService(db).profile(student_id)
