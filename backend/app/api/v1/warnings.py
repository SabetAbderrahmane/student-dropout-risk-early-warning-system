from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.permissions import require_roles
from app.db.session import get_db
from app.models.prediction import RiskLevel
from app.models.user import User, UserRole
from app.models.warning import WarningPriority, WarningReviewState
from app.schemas.warning import (
    AssignmentRequest,
    ReviewRequest,
    WarningDetail,
    WarningPage,
)
from app.services.warning_service import WarningService

router = APIRouter(tags=["warnings"])
read_access = require_roles(
    UserRole.SYSTEM_ADMIN, UserRole.ACADEMIC_ADMIN, UserRole.ACADEMIC_ADVISOR
)
assign_access = require_roles(UserRole.ACADEMIC_ADMIN)
review_access = require_roles(UserRole.ACADEMIC_ADVISOR)


@router.get("/warnings", response_model=WarningPage)
def list_warnings(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    search: str | None = Query(default=None, max_length=200),
    risk_level: RiskLevel | None = None,
    review_state: WarningReviewState | None = None,
    priority: WarningPriority | None = None,
    assigned_to: UUID | None = None,
    sort: Literal[
        "priority",
        "created_at",
        "probability",
        "risk_level",
        "review_state",
        "student_number",
    ] = "priority",
    order: Literal["asc", "desc"] = "asc",
    _: User = Depends(read_access),
    db: Session = Depends(get_db),
) -> WarningPage:
    return WarningService(db).list(
        page=page,
        page_size=page_size,
        search=search,
        risk_level=risk_level,
        review_state=review_state,
        priority=priority,
        assigned_to=assigned_to,
        student_id=None,
        sort=sort,
        order=order,
    )


@router.get("/students/{student_id}/warnings", response_model=WarningPage)
def student_warning_history(
    student_id: UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    _: User = Depends(read_access),
    db: Session = Depends(get_db),
) -> WarningPage:
    return WarningService(db).student_history(
        student_id, page=page, page_size=page_size
    )


@router.get("/warnings/{warning_id}", response_model=WarningDetail)
def get_warning(
    warning_id: UUID, _: User = Depends(read_access), db: Session = Depends(get_db)
) -> WarningDetail:
    return WarningService(db).detail(warning_id)


@router.patch("/warnings/{warning_id}/assignment", response_model=WarningDetail)
def assign_warning(
    warning_id: UUID,
    payload: AssignmentRequest,
    _: User = Depends(assign_access),
    db: Session = Depends(get_db),
) -> WarningDetail:
    return WarningService(db).assign(warning_id, payload)


@router.post(
    "/warnings/{warning_id}/reviews",
    response_model=WarningDetail,
    status_code=status.HTTP_201_CREATED,
)
def review_warning(
    warning_id: UUID,
    payload: ReviewRequest,
    reviewer: User = Depends(review_access),
    db: Session = Depends(get_db),
) -> WarningDetail:
    return WarningService(db).review(warning_id, payload, reviewer)
