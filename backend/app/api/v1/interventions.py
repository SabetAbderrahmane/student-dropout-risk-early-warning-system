from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.permissions import require_roles
from app.db.session import get_db
from app.models.casework import InterventionStatus, InterventionType
from app.models.user import User, UserRole
from app.models.warning import WarningPriority
from app.schemas.casework import (
    CancellationRequest,
    FollowUpCreate,
    FollowUpPage,
    FollowUpRow,
    InterventionComplete,
    InterventionCreate,
    InterventionDetail,
    InterventionNoteCreate,
    InterventionNoteResponse,
    InterventionPage,
    InterventionUpdate,
)
from app.services.casework_service import CaseworkService

router = APIRouter(tags=["interventions"])
read_access = require_roles(
    UserRole.SYSTEM_ADMIN, UserRole.ACADEMIC_ADMIN, UserRole.ACADEMIC_ADVISOR
)
write_access = require_roles(UserRole.ACADEMIC_ADMIN, UserRole.ACADEMIC_ADVISOR)


@router.get("/interventions", response_model=InterventionPage)
def list_interventions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    search: str | None = Query(default=None, max_length=200),
    status: InterventionStatus | None = None,
    priority: WarningPriority | None = None,
    type: InterventionType | None = None,
    assigned_to: UUID | None = None,
    student_id: UUID | None = None,
    warning_id: UUID | None = None,
    sort: Literal[
        "urgency",
        "status",
        "priority",
        "updated_at",
        "created_at",
        "start_date",
        "target_date",
        "student_number",
    ] = "urgency",
    order: Literal["asc", "desc"] = "asc",
    _: User = Depends(read_access),
    db: Session = Depends(get_db),
) -> InterventionPage:
    return CaseworkService(db).list_interventions(
        page=page,
        page_size=page_size,
        search=search,
        status=status,
        priority=priority,
        type=type,
        assigned_to=assigned_to,
        student_id=student_id,
        warning_id=warning_id,
        sort=sort,
        order=order,
    )


@router.post(
    "/interventions",
    response_model=InterventionDetail,
    status_code=status.HTTP_201_CREATED,
)
def create_intervention(
    payload: InterventionCreate,
    actor: User = Depends(write_access),
    db: Session = Depends(get_db),
) -> InterventionDetail:
    return CaseworkService(db).create_intervention(payload, actor)


@router.get("/students/{student_id}/interventions", response_model=InterventionPage)
def student_interventions(
    student_id: UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    _: User = Depends(read_access),
    db: Session = Depends(get_db),
) -> InterventionPage:
    return CaseworkService(db).student_interventions(
        student_id, page=page, page_size=page_size
    )


@router.get("/interventions/{intervention_id}", response_model=InterventionDetail)
def intervention_detail(
    intervention_id: UUID, _: User = Depends(read_access), db: Session = Depends(get_db)
) -> InterventionDetail:
    return CaseworkService(db).intervention_detail(intervention_id)


@router.patch("/interventions/{intervention_id}", response_model=InterventionDetail)
def update_intervention(
    intervention_id: UUID,
    payload: InterventionUpdate,
    actor: User = Depends(write_access),
    db: Session = Depends(get_db),
) -> InterventionDetail:
    return CaseworkService(db).update_intervention(intervention_id, payload, actor)


@router.post(
    "/interventions/{intervention_id}/notes",
    response_model=InterventionNoteResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_note(
    intervention_id: UUID,
    payload: InterventionNoteCreate,
    actor: User = Depends(write_access),
    db: Session = Depends(get_db),
) -> InterventionNoteResponse:
    return CaseworkService(db).add_note(intervention_id, payload, actor)


@router.get(
    "/interventions/{intervention_id}/notes",
    response_model=list[InterventionNoteResponse],
)
def list_notes(
    intervention_id: UUID, _: User = Depends(read_access), db: Session = Depends(get_db)
) -> list[InterventionNoteResponse]:
    return CaseworkService(db).list_notes(intervention_id)


@router.post(
    "/interventions/{intervention_id}/complete", response_model=InterventionDetail
)
def complete_intervention(
    intervention_id: UUID,
    payload: InterventionComplete,
    actor: User = Depends(write_access),
    db: Session = Depends(get_db),
) -> InterventionDetail:
    return CaseworkService(db).complete_intervention(intervention_id, payload, actor)


@router.post(
    "/interventions/{intervention_id}/cancel", response_model=InterventionDetail
)
def cancel_intervention(
    intervention_id: UUID,
    payload: CancellationRequest,
    actor: User = Depends(write_access),
    db: Session = Depends(get_db),
) -> InterventionDetail:
    return CaseworkService(db).cancel_intervention(intervention_id, payload, actor)


@router.post(
    "/interventions/{intervention_id}/follow-ups",
    response_model=FollowUpRow,
    status_code=status.HTTP_201_CREATED,
)
def create_follow_up(
    intervention_id: UUID,
    payload: FollowUpCreate,
    actor: User = Depends(write_access),
    db: Session = Depends(get_db),
) -> FollowUpRow:
    return CaseworkService(db).create_follow_up(intervention_id, payload, actor)


@router.get("/interventions/{intervention_id}/follow-ups", response_model=FollowUpPage)
def intervention_follow_ups(
    intervention_id: UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    _: User = Depends(read_access),
    db: Session = Depends(get_db),
) -> FollowUpPage:
    return CaseworkService(db).intervention_follow_ups(
        intervention_id, page=page, page_size=page_size
    )
