from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.student import Student


class AdmissionRecord(Base):
    __tablename__ = "admission_records"
    __table_args__ = (
        CheckConstraint("length(trim(admission_method)) > 0", name="method_not_blank"),
        CheckConstraint(
            "length(trim(previous_qualification)) > 0",
            name="previous_qualification_not_blank",
        ),
        CheckConstraint("admission_grade >= 0", name="admission_grade_nonnegative"),
        CheckConstraint(
            "previous_qualification_grade >= 0",
            name="previous_qualification_grade_nonnegative",
        ),
        CheckConstraint("admission_grade <= 200", name="admission_grade_maximum"),
        CheckConstraint(
            "previous_qualification_grade <= 200",
            name="previous_qualification_grade_maximum",
        ),
        CheckConstraint(
            "application_order IS NULL OR application_order BETWEEN 0 AND 9",
            name="application_order_valid",
        ),
        CheckConstraint(
            "daytime_evening_attendance IS NULL OR daytime_evening_attendance IN (0, 1)",
            name="daytime_evening_attendance_binary",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), unique=True, index=True
    )
    admission_method: Mapped[str] = mapped_column(String(100))
    admission_grade: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    previous_qualification: Mapped[str] = mapped_column(String(200))
    previous_qualification_grade: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    application_mode_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    application_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    course_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    daytime_evening_attendance: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    previous_qualification_code: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    mother_qualification_code: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    father_qualification_code: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    mother_occupation_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    father_occupation_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unemployment_rate: Mapped[Decimal | None] = mapped_column(Numeric(), nullable=True)
    inflation_rate: Mapped[Decimal | None] = mapped_column(Numeric(), nullable=True)
    gdp: Mapped[Decimal | None] = mapped_column(Numeric(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    student: Mapped[Student] = relationship(back_populates="admission_record")
