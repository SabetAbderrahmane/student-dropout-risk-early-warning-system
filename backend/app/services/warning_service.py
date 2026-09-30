from typing import Any
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.models.user import User, UserRole
from app.models.warning import Warning, WarningReview, WarningReviewState
from app.repositories.warning_repository import WarningRepository
from app.schemas.warning import (
    AdvisorSummary,
    AssignmentRequest,
    ReviewRequest,
    ReviewResponse,
    StudentSummary,
    WarningDetail,
    WarningPage,
    WarningRow,
)


class WarningService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = WarningRepository(db)

    @staticmethod
    def _row(warning: Warning) -> WarningRow:
        prediction = warning.prediction
        return WarningRow(
            id=warning.id,
            student_id=warning.student_id,
            student_number=warning.student.student_number,
            student_name=warning.student.name,
            prediction_id=warning.prediction_id,
            probability=prediction.probability,
            risk_level=warning.risk_level,
            priority=warning.priority,
            review_state=warning.review_state,
            assigned_advisor=(
                AdvisorSummary(
                    id=warning.assignee.id, full_name=warning.assignee.full_name
                )
                if warning.assignee
                else None
            ),
            predicted_at=prediction.predicted_at,
            created_at=warning.created_at,
            updated_at=warning.updated_at,
            top_explanation_factors=prediction.explanation,
        )

    @staticmethod
    def _review(review: WarningReview) -> ReviewResponse:
        return ReviewResponse(
            id=review.id,
            warning_id=review.warning_id,
            reviewer_id=review.reviewer_id,
            reviewer_name=review.reviewer.full_name,
            decision=review.decision,
            note=review.note,
            reviewed_at=review.reviewed_at,
        )

    def _get(self, warning_id: UUID, *, lock: bool = False) -> Warning:
        warning = self.repository.get(warning_id, lock=lock)
        if warning is None:
            raise ApplicationError(
                404, "WARNING_NOT_FOUND", "The requested warning does not exist."
            )
        return warning

    def detail(self, warning_id: UUID) -> WarningDetail:
        warning = self._get(warning_id)
        row = self._row(warning).model_dump()
        return WarningDetail(
            **row,
            student=StudentSummary(
                id=warning.student.id,
                student_number=warning.student.student_number,
                name=warning.student.name,
            ),
            model_version=warning.prediction.model_version.model_version,
            prediction_explanation=warning.prediction.explanation,
            review_history=[
                self._review(review)
                for review in sorted(
                    warning.reviews,
                    key=lambda item: (item.reviewed_at, item.id),
                    reverse=True,
                )
            ],
        )

    def list(self, **kwargs: Any) -> WarningPage:
        rows, total = self.repository.list(**kwargs)
        return WarningPage.create(
            [self._row(row) for row in rows], kwargs["page"], kwargs["page_size"], total
        )

    def student_history(
        self, student_id: UUID, *, page: int, page_size: int
    ) -> WarningPage:
        from app.models.student import Student

        if self.db.get(Student, student_id) is None:
            raise ApplicationError(
                404, "STUDENT_NOT_FOUND", "The requested student does not exist."
            )
        return self.list(
            page=page,
            page_size=page_size,
            search=None,
            risk_level=None,
            review_state=None,
            priority=None,
            assigned_to=None,
            student_id=student_id,
            sort="created_at",
            order="desc",
        )

    def assign(self, warning_id: UUID, payload: AssignmentRequest) -> WarningDetail:
        warning = self._get(warning_id, lock=True)
        if payload.assigned_to is not None:
            user = self.db.get(User, payload.assigned_to)
            if (
                user is None
                or not user.is_active
                or user.role != UserRole.ACADEMIC_ADVISOR
            ):
                raise ApplicationError(
                    422,
                    "INVALID_WARNING_ASSIGNEE",
                    "The assignee must be an active Academic Advisor.",
                )
        warning.assigned_to = payload.assigned_to
        warning.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        return self.detail(warning_id)

    def review(
        self, warning_id: UUID, payload: ReviewRequest, reviewer: User
    ) -> WarningDetail:
        warning = self._get(warning_id, lock=True)
        if warning.assigned_to is None:
            raise ApplicationError(
                409, "WARNING_REQUIRES_ASSIGNMENT", "Assign this warning before review."
            )
        if warning.assigned_to != reviewer.id:
            raise ApplicationError(
                403,
                "WARNING_ASSIGNED_TO_DIFFERENT_ADVISOR",
                "Only the assigned advisor may review this warning.",
            )
        review = WarningReview(
            warning_id=warning.id,
            reviewer_id=reviewer.id,
            decision=payload.decision,
            note=payload.note,
            reviewed_at=datetime.now(timezone.utc),
        )
        self.db.add(review)
        warning.review_state = WarningReviewState(payload.decision.value)
        warning.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        return self.detail(warning_id)
