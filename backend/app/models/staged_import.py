import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.import_job import ImportJob


class StagedImportStatus(str, enum.Enum):
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    READY_TO_COMMIT = "READY_TO_COMMIT"
    COMMITTED = "COMMITTED"
    CANCELLED = "CANCELLED"


class StagedImportBatch(Base):
    __tablename__ = "staged_import_batches"
    __table_args__ = (
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint(
            "total_rows >= 0 AND included_rows >= 0 AND excluded_rows >= 0",
            name="counts_nonnegative",
        ),
        CheckConstraint(
            "included_rows + excluded_rows = total_rows",
            name="inclusion_counts_consistent",
        ),
        CheckConstraint(
            "valid_rows >= 0 AND invalid_rows >= 0 AND valid_rows + invalid_rows = total_rows",
            name="validation_counts_consistent",
        ),
        CheckConstraint(
            "valid_included_rows >= 0 AND invalid_included_rows >= 0 AND valid_included_rows + invalid_included_rows = included_rows",
            name="included_validation_consistent",
        ),
        CheckConstraint(
            "validation_issue_count >= 0 AND included_issue_count >= 0",
            name="issue_counts_nonnegative",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    filename: Mapped[str] = mapped_column(String(255))
    status: Mapped[StagedImportStatus] = mapped_column(
        Enum(
            StagedImportStatus,
            native_enum=False,
            create_constraint=True,
            name="staged_import_status",
        ),
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    total_rows: Mapped[int] = mapped_column(Integer)
    included_rows: Mapped[int] = mapped_column(Integer, default=0)
    excluded_rows: Mapped[int] = mapped_column(Integer, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, default=0)
    invalid_rows: Mapped[int] = mapped_column(Integer, default=0)
    valid_included_rows: Mapped[int] = mapped_column(Integer, default=0)
    invalid_included_rows: Mapped[int] = mapped_column(Integer, default=0)
    validation_issue_count: Mapped[int] = mapped_column(Integer, default=0)
    included_issue_count: Mapped[int] = mapped_column(Integer, default=0)
    import_job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("import_jobs.id"), unique=True
    )
    last_commit_error: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    import_job: Mapped[ImportJob | None] = relationship(lazy="selectin")


class StagedImportRow(Base):
    __tablename__ = "staged_import_rows"
    __table_args__ = (
        UniqueConstraint("batch_id", "row_number"),
        CheckConstraint("row_number >= 2", name="row_number_valid"),
        CheckConstraint("version >= 1", name="version_positive"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("staged_import_batches.id", ondelete="CASCADE"), index=True
    )
    row_number: Mapped[int] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer, default=1)
    original_values: Mapped[dict[str, str]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql")
    )
    edited_values: Mapped[dict[str, str]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql")
    )
    student_number: Mapped[str] = mapped_column(String(131072))
    student_name: Mapped[str] = mapped_column(String(131072))
    included: Mapped[bool] = mapped_column(Boolean, default=True)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    issues: Mapped[list[dict[str, object]]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), default=list
    )


class StagedImportAction(Base):
    __tablename__ = "staged_import_actions"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("staged_import_batches.id", ondelete="CASCADE"), index=True
    )
    row_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("staged_import_rows.id")
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(40))
    batch_version: Mapped[int] = mapped_column(Integer)
    changes: Mapped[dict[str, object]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
