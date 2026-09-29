from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.admission import AdmissionRecord
    from app.models.semester_one import FirstSemesterRecord


class Student(Base):
    __tablename__ = "students"
    __table_args__ = (
        CheckConstraint("length(trim(student_number)) > 0", name="student_number_not_blank"),
        CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    student_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    gender: Mapped[str | None] = mapped_column(String(50), nullable=True)
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

