from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.admission import AdmissionRecord
    from app.models.semester_one import FirstSemesterRecord


class Student(Base):
    __tablename__ = "students"
    __table_args__ = (
        CheckConstraint(
            "length(trim(student_number)) > 0", name="student_number_not_blank"
        ),
        CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
        CheckConstraint(
            "marital_status_code IS NULL OR marital_status_code IN (1, 2, 3, 4, 5, 6)",
            name="marital_status_code_valid",
        ),
        CheckConstraint(
            "displaced IS NULL OR displaced IN (0, 1)", name="displaced_binary"
        ),
        CheckConstraint(
            "educational_special_needs IS NULL OR educational_special_needs IN (0, 1)",
            name="educational_special_needs_binary",
        ),
        CheckConstraint("debtor IS NULL OR debtor IN (0, 1)", name="debtor_binary"),
        CheckConstraint(
            "tuition_fees_up_to_date IS NULL OR tuition_fees_up_to_date IN (0, 1)",
            name="tuition_fees_up_to_date_binary",
        ),
        CheckConstraint(
            "gender_code IS NULL OR gender_code IN (0, 1)",
            name="gender_code_binary",
        ),
        CheckConstraint(
            "scholarship_holder IS NULL OR scholarship_holder IN (0, 1)",
            name="scholarship_holder_binary",
        ),
        CheckConstraint(
            "age_at_enrollment IS NULL OR age_at_enrollment >= 0",
            name="age_at_enrollment_nonnegative",
        ),
        CheckConstraint(
            "international_student IS NULL OR international_student IN (0, 1)",
            name="international_student_binary",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    student_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    gender: Mapped[str | None] = mapped_column(String(50), nullable=True)
    marital_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    nationality_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    displaced: Mapped[int | None] = mapped_column(Integer, nullable=True)
    educational_special_needs: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    debtor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tuition_fees_up_to_date: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gender_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scholarship_holder: Mapped[int | None] = mapped_column(Integer, nullable=True)
    age_at_enrollment: Mapped[int | None] = mapped_column(Integer, nullable=True)
    international_student: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    admission_record: Mapped[AdmissionRecord | None] = relationship(
        back_populates="student",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
    first_semester_record: Mapped[FirstSemesterRecord | None] = relationship(
        back_populates="student",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
