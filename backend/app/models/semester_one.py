from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.student import Student


class FirstSemesterRecord(Base):
    __tablename__ = "first_semester_records"
    __table_args__ = (
        CheckConstraint("credited_units >= 0", name="credited_units_nonnegative"),
        CheckConstraint("enrolled_units >= 0", name="enrolled_units_nonnegative"),
        CheckConstraint("evaluations >= 0", name="evaluations_nonnegative"),
        CheckConstraint("approved_units >= 0", name="approved_units_nonnegative"),
        CheckConstraint("average_grade >= 0", name="average_grade_nonnegative"),
        CheckConstraint("average_grade <= 20", name="average_grade_maximum"),
        CheckConstraint(
            "without_evaluations IS NULL OR without_evaluations >= 0",
            name="without_evaluations_nonnegative",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), unique=True, index=True
    )
    credited_units: Mapped[int] = mapped_column(Integer)
    enrolled_units: Mapped[int] = mapped_column(Integer)
    evaluations: Mapped[int] = mapped_column(Integer)
    approved_units: Mapped[int] = mapped_column(Integer)
    average_grade: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    without_evaluations: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    student: Mapped[Student] = relationship(back_populates="first_semester_record")
