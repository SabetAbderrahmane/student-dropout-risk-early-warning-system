from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class ImportStatus(str, enum.Enum):
    UPLOADED = "UPLOADED"
    VALIDATING = "VALIDATING"
    IMPORTED = "IMPORTED"
    FAILED = "FAILED"


class ImportJob(Base):
    __tablename__ = "import_jobs"
    __table_args__ = (
        CheckConstraint("length(trim(filename)) > 0", name="filename_not_blank"),
        CheckConstraint("total_rows >= 0", name="total_rows_nonnegative"),
        CheckConstraint("valid_rows >= 0", name="valid_rows_nonnegative"),
        CheckConstraint("invalid_rows >= 0", name="invalid_rows_nonnegative"),
        CheckConstraint(
            "valid_rows + invalid_rows = total_rows", name="row_counts_consistent"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, default=0)
    invalid_rows: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[ImportStatus] = mapped_column(
        Enum(
            ImportStatus,
            name="import_status",
            values_callable=lambda enum_class: [status.value for status in enum_class],
        ),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    uploader: Mapped[User] = relationship()
    errors: Mapped[list[ImportValidationError]] = relationship(
        back_populates="import_job",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ImportValidationError(Base):
    __tablename__ = "import_errors"
    __table_args__ = (
        CheckConstraint("row_number >= 2", name="row_number_valid"),
        CheckConstraint("length(trim(error_code)) > 0", name="error_code_not_blank"),
        CheckConstraint(
            "length(trim(error_message)) > 0", name="error_message_not_blank"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    import_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("import_jobs.id", ondelete="CASCADE"), index=True
    )
    row_number: Mapped[int] = mapped_column(Integer)
    field_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_code: Mapped[str] = mapped_column(String(100))
    error_message: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    import_job: Mapped[ImportJob] = relationship(back_populates="errors")
