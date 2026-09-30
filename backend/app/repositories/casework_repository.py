from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import asc, case, desc, func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.casework import (
    FollowUp,
    FollowUpStatus,
    Intervention,
    InterventionNote,
    InterventionStatus,
)
from app.models.student import Student
from app.models.warning import WarningPriority
from app.schemas.casework import EffectiveFollowUpStatus


class CaseworkRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _intervention_options():
        return (
            joinedload(Intervention.student),
            joinedload(Intervention.warning),
            joinedload(Intervention.assignee),
            selectinload(Intervention.intervention_notes).joinedload(
                InterventionNote.author
            ),
            selectinload(Intervention.follow_ups).joinedload(FollowUp.assignee),
        )

    @staticmethod
    def _follow_up_options():
        return (
            joinedload(FollowUp.student),
            joinedload(FollowUp.assignee),
            joinedload(FollowUp.intervention).joinedload(Intervention.warning),
        )

    def intervention(
        self, intervention_id: UUID, *, lock: bool = False
    ) -> Intervention | None:
        statement = (
            select(Intervention)
            .options(*self._intervention_options())
            .where(Intervention.id == intervention_id)
            .execution_options(populate_existing=True)
        )
        if lock:
            statement = statement.with_for_update(of=Intervention)
        return self.db.scalar(statement)

    def follow_up(self, follow_up_id: UUID, *, lock: bool = False) -> FollowUp | None:
        statement = (
            select(FollowUp)
            .options(*self._follow_up_options())
            .where(FollowUp.id == follow_up_id)
            .execution_options(populate_existing=True)
        )
        if lock:
            statement = statement.with_for_update(of=FollowUp)
        return self.db.scalar(statement)

    def list_interventions(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None,
        status: InterventionStatus | None,
        priority: WarningPriority | None,
        type: str | None,
        assigned_to: UUID | None,
        student_id: UUID | None,
        warning_id: UUID | None,
        sort: str,
        order: str,
    ):
        filters = []
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(
                or_(
                    Student.student_number.ilike(pattern),
                    Student.name.ilike(pattern),
                    Intervention.title.ilike(pattern),
                )
            )
        if status:
            filters.append(Intervention.status == status)
        if priority:
            filters.append(Intervention.priority == priority)
        if type:
            filters.append(Intervention.type == type)
        if assigned_to:
            filters.append(Intervention.assigned_to == assigned_to)
        if student_id:
            filters.append(Intervention.student_id == student_id)
        if warning_id:
            filters.append(Intervention.warning_id == warning_id)
        base = select(Intervention).join(Intervention.student).where(*filters)
        total = (
            self.db.scalar(
                select(func.count(Intervention.id))
                .join(Intervention.student)
                .where(*filters)
            )
            or 0
        )
        status_rank = case(
            (Intervention.status == InterventionStatus.ACTION_REQUIRED, 1),
            (Intervention.status == InterventionStatus.IN_PROGRESS, 2),
            (Intervention.status == InterventionStatus.PLANNED, 3),
            else_=4,
        )
        priority_rank = case(
            (Intervention.priority == WarningPriority.P1_URGENT, 1),
            (Intervention.priority == WarningPriority.P2_ELEVATED, 2),
            else_=3,
        )
        columns = {
            "status": Intervention.status,
            "priority": Intervention.priority,
            "updated_at": Intervention.updated_at,
            "created_at": Intervention.created_at,
            "start_date": Intervention.start_date,
            "target_date": Intervention.target_date,
            "student_number": Student.student_number,
        }
        if sort == "urgency":
            ordering = (
                status_rank.asc(),
                priority_rank.asc(),
                Intervention.updated_at.desc(),
                Intervention.id.desc(),
            )
        else:
            direction = asc if order == "asc" else desc
            ordering = (
                direction(columns[sort]),
                Intervention.updated_at.desc(),
                Intervention.id.desc(),
            )
        statement = (
            base.options(*self._intervention_options())
            .order_by(*ordering)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self.db.scalars(statement).unique()), total

    @staticmethod
    def effective_status_expression(now: datetime):
        start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        return case(
            (
                FollowUp.status == FollowUpStatus.COMPLETED,
                EffectiveFollowUpStatus.COMPLETED.value,
            ),
            (
                FollowUp.status == FollowUpStatus.CANCELLED,
                EffectiveFollowUpStatus.CANCELLED.value,
            ),
            (FollowUp.scheduled_for < start, EffectiveFollowUpStatus.OVERDUE.value),
            (FollowUp.scheduled_for < end, EffectiveFollowUpStatus.DUE.value),
            else_=EffectiveFollowUpStatus.SCHEDULED.value,
        )

    def list_follow_ups(
        self,
        *,
        page: int,
        page_size: int,
        status: EffectiveFollowUpStatus | None,
        assigned_to: UUID | None,
        student_id: UUID | None,
        intervention_id: UUID | None,
        from_date: datetime | None,
        to_date: datetime | None,
        search: str | None,
        sort: str,
        order: str,
        now: datetime,
    ):
        filters = []
        if status:
            filters.append(self.effective_status_expression(now) == status.value)
        if assigned_to:
            filters.append(FollowUp.assigned_to == assigned_to)
        if student_id:
            filters.append(FollowUp.student_id == student_id)
        if intervention_id:
            filters.append(FollowUp.intervention_id == intervention_id)
        if from_date:
            filters.append(FollowUp.scheduled_for >= from_date)
        if to_date:
            filters.append(FollowUp.scheduled_for <= to_date)
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(
                or_(
                    Student.student_number.ilike(pattern),
                    Student.name.ilike(pattern),
                    FollowUp.purpose.ilike(pattern),
                )
            )
        base = select(FollowUp).join(FollowUp.student).where(*filters)
        total = (
            self.db.scalar(
                select(func.count(FollowUp.id)).join(FollowUp.student).where(*filters)
            )
            or 0
        )
        columns = {
            "scheduled_for": FollowUp.scheduled_for,
            "created_at": FollowUp.created_at,
            "updated_at": FollowUp.updated_at,
            "student_number": Student.student_number,
        }
        direction = asc if order == "asc" else desc
        statement = (
            base.options(*self._follow_up_options())
            .order_by(direction(columns[sort]), FollowUp.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self.db.scalars(statement).unique()), total
