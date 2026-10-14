from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.permissions import require_roles
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.casework import (
    CancellationRequest,
    EffectiveFollowUpStatus,
    FollowUpComplete,
    FollowUpPage,
    FollowUpRecovery,
    FollowUpRow,
    FollowUpUpdate,
)
from app.services.casework_service import CaseworkService

router = APIRouter(prefix="/follow-ups", tags=["follow-ups"])
read_access = require_roles(
    UserRole.SYSTEM_ADMIN, UserRole.ACADEMIC_ADMIN, UserRole.ACADEMIC_ADVISOR
)
write_access = require_roles(UserRole.ACADEMIC_ADMIN, UserRole.ACADEMIC_ADVISOR)


@router.get("", response_model=FollowUpPage)
def list_follow_ups(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    status: EffectiveFollowUpStatus | None = None,
    assigned_to: UUID | None = None,
    student_id: UUID | None = None,
    intervention_id: UUID | None = None,
    from_date: datetime | None = Query(default=None, alias="from"),
    to_date: datetime | None = Query(default=None, alias="to"),
    search: str | None = Query(default=None, max_length=200),
    sort: Literal[
        "scheduled_for", "created_at", "updated_at", "student_number"
    ] = "scheduled_for",
    order: Literal["asc", "desc"] = "asc",
    _: User = Depends(read_access),
    db: Session = Depends(get_db),
) -> FollowUpPage:
    return CaseworkService(db).list_follow_ups(
        page=page,
        page_size=page_size,
        status=status,
        assigned_to=assigned_to,
        student_id=student_id,
        intervention_id=intervention_id,
        from_date=from_date,
        to_date=to_date,
        search=search,
        sort=sort,
        order=order,
    )


@router.get("/{follow_up_id}", response_model=FollowUpRow)
def follow_up_detail(
    follow_up_id: UUID, _: User = Depends(read_access), db: Session = Depends(get_db)
) -> FollowUpRow:
    return CaseworkService(db).follow_up_detail(follow_up_id)


@router.patch("/{follow_up_id}", response_model=FollowUpRow)
def update_follow_up(
    follow_up_id: UUID,
    payload: FollowUpUpdate,
    actor: User = Depends(write_access),
    db: Session = Depends(get_db),
) -> FollowUpRow:
    return CaseworkService(db).update_follow_up(follow_up_id, payload, actor)


@router.post("/{follow_up_id}/complete", response_model=FollowUpRow)
def complete_follow_up(
    follow_up_id: UUID,
    payload: FollowUpComplete,
    actor: User = Depends(write_access),
    db: Session = Depends(get_db),
) -> FollowUpRow:
    return CaseworkService(db).complete_follow_up(follow_up_id, payload, actor)


@router.post("/{follow_up_id}/cancel", response_model=FollowUpRow)
def cancel_follow_up(
    follow_up_id: UUID,
    payload: CancellationRequest,
    actor: User = Depends(write_access),
    db: Session = Depends(get_db),
) -> FollowUpRow:
    return CaseworkService(db).cancel_follow_up(follow_up_id, payload, actor)


@router.post("/{follow_up_id}/recover", response_model=FollowUpRow)
def recover_follow_up(
    follow_up_id: UUID,
    payload: FollowUpRecovery,
    actor: User = Depends(require_roles(UserRole.ACADEMIC_ADMIN)),
    db: Session = Depends(get_db),
) -> FollowUpRow:
    return CaseworkService(db).recover_follow_up(follow_up_id, payload, actor)
