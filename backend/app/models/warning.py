import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.prediction import RiskLevel


class WarningPriority(str, enum.Enum):
    P1_URGENT = "P1_URGENT"
    P2_ELEVATED = "P2_ELEVATED"
    P3_STANDARD = "P3_STANDARD"


class WarningReviewState(str, enum.Enum):
    PENDING_REVIEW = "PENDING_REVIEW"
    CONFIRMED = "CONFIRMED"
    DISMISSED = "DISMISSED"


class ReviewDecision(str, enum.Enum):
    CONFIRMED = "CONFIRMED"
    DISMISSED = "DISMISSED"


def enum_column(enum_type: type[enum.Enum], name: str):
    return Enum(
        enum_type, name=name, values_callable=lambda cls: [v.value for v in cls]
    )


class Warning(Base):
    __tablename__ = "warnings"
    __table_args__ = (
        CheckConstraint("revision >= 0", name="revision_nonnegative"),
        CheckConstraint("risk_level <> 'LOW'", name="qualifying_risk"),
        UniqueConstraint("id", "student_id", name="uq_warnings_intervention_identity"),
        ForeignKeyConstraint(
            ["prediction_id", "student_id", "risk_level"],
            [
                "prediction_results.id",
                "prediction_results.student_id",
                "prediction_results.risk_level",
            ],
            name="fk_warnings_prediction_identity_prediction_results",
            ondelete="RESTRICT",
        ),
    )

    revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    prediction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("prediction_results.id", ondelete="RESTRICT"), unique=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="RESTRICT"), index=True
    )
    risk_level: Mapped[RiskLevel] = mapped_column(
        enum_column(RiskLevel, "risk_level"), index=True
    )
    priority: Mapped[WarningPriority] = mapped_column(
        enum_column(WarningPriority, "warning_priority"), index=True
    )
    review_state: Mapped[WarningReviewState] = mapped_column(
        enum_column(WarningReviewState, "warning_review_state"),
        default=WarningReviewState.PENDING_REVIEW,
        server_default="PENDING_REVIEW",
        index=True,
    )
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    prediction = relationship("PredictionResult", foreign_keys=[prediction_id])
    student = relationship("Student")
    assignee = relationship("User")
    reviews: Mapped[list["WarningReview"]] = relationship(
        back_populates="warning", order_by="WarningReview.reviewed_at.desc()"
    )


class WarningReview(Base):
    __tablename__ = "warning_reviews"
    __table_args__ = (CheckConstraint("length(trim(note)) > 0", name="note_not_blank"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    warning_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("warnings.id", ondelete="RESTRICT"), index=True
    )
    reviewer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    decision: Mapped[ReviewDecision] = mapped_column(
        enum_column(ReviewDecision, "warning_review_decision")
    )
    note: Mapped[str] = mapped_column(String(4000))
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    warning: Mapped[Warning] = relationship(back_populates="reviews")
    reviewer = relationship("User")
