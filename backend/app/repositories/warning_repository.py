from uuid import UUID

from sqlalchemy import asc, case, desc, func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.prediction import PredictionResult, RiskLevel
from app.models.student import Student
from app.models.warning import (
    Warning,
    WarningPriority,
    WarningReview,
    WarningReviewState,
)


class WarningRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _options():
        return (
            joinedload(Warning.student),
            joinedload(Warning.assignee),
            joinedload(Warning.prediction).joinedload(PredictionResult.model_version),
            selectinload(Warning.reviews).joinedload(WarningReview.reviewer),
        )

    def get(self, warning_id: UUID, *, lock: bool = False) -> Warning | None:
        statement = (
            select(Warning)
            .options(*self._options())
            .where(Warning.id == warning_id)
            .execution_options(populate_existing=True)
        )
        if lock:
            statement = statement.with_for_update(of=Warning)
        return self.db.scalar(statement)

    def list(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None,
        risk_level: RiskLevel | None,
        review_state: WarningReviewState | None,
        priority: WarningPriority | None,
        assigned_to: UUID | None,
        student_id: UUID | None,
        sort: str,
        order: str,
    ) -> tuple[list[Warning], int]:
        filters = []
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(
                or_(Student.student_number.ilike(pattern), Student.name.ilike(pattern))
            )
        if risk_level:
            filters.append(Warning.risk_level == risk_level)
        if review_state:
            filters.append(Warning.review_state == review_state)
        if priority:
            filters.append(Warning.priority == priority)
        if assigned_to:
            filters.append(Warning.assigned_to == assigned_to)
        if student_id:
            filters.append(Warning.student_id == student_id)
        base = (
            select(Warning)
            .join(Warning.student)
            .join(Warning.prediction)
            .where(*filters)
        )
        total = (
            self.db.scalar(
                select(func.count(Warning.id))
                .join(Warning.student)
                .join(Warning.prediction)
                .where(*filters)
            )
            or 0
        )
        priority_rank = case(
            (Warning.priority == WarningPriority.P1_URGENT, 1),
            (Warning.priority == WarningPriority.P2_ELEVATED, 2),
            else_=3,
        )
        columns = {
            "priority": priority_rank,
            "created_at": Warning.created_at,
            "probability": PredictionResult.probability,
            "risk_level": Warning.risk_level,
            "review_state": Warning.review_state,
            "student_number": Student.student_number,
        }
        if sort == "priority":
            ordering = (
                priority_rank.asc() if order == "asc" else priority_rank.desc(),
                Warning.created_at.desc(),
                Warning.id.desc(),
            )
        else:
            direction = asc if order == "asc" else desc
            ordering = (
                direction(columns[sort]),
                Warning.created_at.desc(),
                Warning.id.desc(),
            )
        statement = (
            base.options(*self._options())
            .order_by(*ordering)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self.db.scalars(statement).unique()), total
