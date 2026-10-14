import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.warning import WarningPriority, enum_column


class InterventionType(str, enum.Enum):
    ACADEMIC_TUTORING = "ACADEMIC_TUTORING"
    ACADEMIC_ADVISING = "ACADEMIC_ADVISING"
    STUDY_PERFORMANCE_PLAN = "STUDY_PERFORMANCE_PLAN"
    FINANCIAL_SUPPORT_REFERRAL = "FINANCIAL_SUPPORT_REFERRAL"
    ADMINISTRATIVE_SUPPORT_REFERRAL = "ADMINISTRATIVE_SUPPORT_REFERRAL"
    OTHER = "OTHER"


class InterventionStatus(str, enum.Enum):
    PLANNED = "PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    ACTION_REQUIRED = "ACTION_REQUIRED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class InterventionOutcome(str, enum.Enum):
    SUPPORT_COMPLETED = "SUPPORT_COMPLETED"
    GOALS_PARTIALLY_MET = "GOALS_PARTIALLY_MET"
    REFERRED_FOR_ADDITIONAL_SUPPORT = "REFERRED_FOR_ADDITIONAL_SUPPORT"
    STUDENT_UNRESPONSIVE = "STUDENT_UNRESPONSIVE"
    OTHER = "OTHER"


class FollowUpMethod(str, enum.Enum):
    IN_PERSON = "IN_PERSON"
    PHONE = "PHONE"
    EMAIL = "EMAIL"
    ONLINE_MEETING = "ONLINE_MEETING"
    OTHER = "OTHER"


class FollowUpStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class FollowUpOutcome(str, enum.Enum):
    COMPLETED = "COMPLETED"
    PROGRESS_OBSERVED = "PROGRESS_OBSERVED"
    NO_RESPONSE = "NO_RESPONSE"
    RESCHEDULED = "RESCHEDULED"
    ESCALATION_REQUIRED = "ESCALATION_REQUIRED"
    INTERVENTION_COMPLETED = "INTERVENTION_COMPLETED"


class Intervention(Base):
    __tablename__ = "interventions"
    __table_args__ = (
        CheckConstraint("revision >= 0", name="revision_nonnegative"),
        UniqueConstraint(
            "id", "student_id", name="uq_interventions_follow_up_identity"
        ),
        ForeignKeyConstraint(
            ["warning_id", "student_id"],
            ["warnings.id", "warnings.student_id"],
            name="fk_interventions_warning_identity_warnings",
            ondelete="RESTRICT",
        ),
        CheckConstraint("length(trim(title)) > 0", name="title_not_blank"),
        CheckConstraint("length(trim(description)) > 0", name="description_not_blank"),
        CheckConstraint(
            "target_date IS NULL OR target_date >= start_date", name="valid_date_range"
        ),
        CheckConstraint(
            "(status = 'COMPLETED' AND completed_at IS NOT NULL AND completion_outcome IS NOT NULL AND completion_notes IS NOT NULL) OR (status <> 'COMPLETED' AND completed_at IS NULL AND completion_outcome IS NULL)",
            name="completion_metadata",
        ),
    )

    revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="RESTRICT"), index=True
    )
    warning_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("warnings.id", ondelete="RESTRICT"), index=True
    )
    type: Mapped[InterventionType] = mapped_column(
        enum_column(InterventionType, "intervention_type"), index=True
    )
    title: Mapped[str] = mapped_column(String(250))
    description: Mapped[str] = mapped_column(String(4000))
    priority: Mapped[WarningPriority] = mapped_column(
        enum_column(WarningPriority, "warning_priority"), index=True
    )
    status: Mapped[InterventionStatus] = mapped_column(
        enum_column(InterventionStatus, "intervention_status"),
        default=InterventionStatus.PLANNED,
        server_default="PLANNED",
        index=True,
    )
    assigned_to: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    start_date: Mapped[date] = mapped_column(Date)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completion_outcome: Mapped[InterventionOutcome | None] = mapped_column(
        enum_column(InterventionOutcome, "intervention_outcome"), nullable=True
    )
    completion_notes: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        index=True,
    )

    student = relationship("Student", foreign_keys=[student_id])
    warning = relationship("Warning", foreign_keys=[warning_id])
    assignee = relationship("User", foreign_keys=[assigned_to])
    creator = relationship("User", foreign_keys=[created_by])
    intervention_notes: Mapped[list["InterventionNote"]] = relationship(
        back_populates="intervention", order_by="InterventionNote.created_at.desc()"
    )
    follow_ups: Mapped[list["FollowUp"]] = relationship(
        back_populates="intervention",
        foreign_keys="FollowUp.intervention_id",
        order_by="FollowUp.scheduled_for.desc()",
    )


class InterventionNote(Base):
    __tablename__ = "intervention_notes"
    __table_args__ = (CheckConstraint("length(trim(note)) > 0", name="note_not_blank"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    intervention_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("interventions.id", ondelete="RESTRICT"), index=True
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    note: Mapped[str] = mapped_column(String(4000))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    intervention: Mapped[Intervention] = relationship(
        back_populates="intervention_notes"
    )
    author = relationship("User")


class FollowUp(Base):
    __tablename__ = "follow_ups"
    __table_args__ = (
        CheckConstraint("revision >= 0", name="revision_nonnegative"),
        ForeignKeyConstraint(
            ["intervention_id", "student_id"],
            ["interventions.id", "interventions.student_id"],
            name="fk_follow_ups_intervention_identity_interventions",
            ondelete="RESTRICT",
        ),
        CheckConstraint("length(trim(purpose)) > 0", name="purpose_not_blank"),
        CheckConstraint(
            "(status = 'COMPLETED' AND outcome IS NOT NULL AND notes IS NOT NULL AND completed_at IS NOT NULL) OR (status <> 'COMPLETED' AND outcome IS NULL AND completed_at IS NULL)",
            name="completion_metadata",
        ),
    )

    revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    intervention_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("interventions.id", ondelete="RESTRICT"), index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="RESTRICT"), index=True
    )
    assigned_to: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    method: Mapped[FollowUpMethod] = mapped_column(
        enum_column(FollowUpMethod, "follow_up_method")
    )
    purpose: Mapped[str] = mapped_column(String(2000))
    status: Mapped[FollowUpStatus] = mapped_column(
        enum_column(FollowUpStatus, "follow_up_status"),
        default=FollowUpStatus.SCHEDULED,
        server_default="SCHEDULED",
        index=True,
    )
    outcome: Mapped[FollowUpOutcome | None] = mapped_column(
        enum_column(FollowUpOutcome, "follow_up_outcome"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    intervention: Mapped[Intervention] = relationship(
        back_populates="follow_ups", foreign_keys=[intervention_id]
    )
    student = relationship("Student", foreign_keys=[student_id])
    assignee = relationship("User", foreign_keys=[assigned_to])
    creator = relationship("User", foreign_keys=[created_by])
