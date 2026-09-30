"""create CSV import job and error tables

Revision ID: 20260929_0004
Revises: 20260929_0003
Create Date: 2026-09-29 22:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260929_0004"
down_revision: str | None = "20260929_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

import_status = postgresql.ENUM(
    "UPLOADED",
    "VALIDATING",
    "IMPORTED",
    "FAILED",
    name="import_status",
    create_type=False,
)


def upgrade() -> None:
    import_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "import_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False),
        sa.Column("valid_rows", sa.Integer(), nullable=False),
        sa.Column("invalid_rows", sa.Integer(), nullable=False),
        sa.Column("status", import_status, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("length(trim(filename)) > 0", name="filename_not_blank"),
        sa.CheckConstraint("total_rows >= 0", name="total_rows_nonnegative"),
        sa.CheckConstraint("valid_rows >= 0", name="valid_rows_nonnegative"),
        sa.CheckConstraint("invalid_rows >= 0", name="invalid_rows_nonnegative"),
        sa.CheckConstraint(
            "valid_rows + invalid_rows = total_rows", name="row_counts_consistent"
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by"], ["users.id"], name="fk_import_jobs_uploaded_by_users"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_import_jobs"),
    )
    op.create_index("ix_import_jobs_uploaded_by", "import_jobs", ["uploaded_by"])
    op.create_index("ix_import_jobs_status", "import_jobs", ["status"])
    op.create_index("ix_import_jobs_created_at", "import_jobs", ["created_at"])

    op.create_table(
        "import_errors",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("import_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("field_name", sa.String(length=100), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=False),
        sa.Column("error_message", sa.String(length=500), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("row_number >= 2", name="row_number_valid"),
        sa.CheckConstraint("length(trim(error_code)) > 0", name="error_code_not_blank"),
        sa.CheckConstraint(
            "length(trim(error_message)) > 0", name="error_message_not_blank"
        ),
        sa.ForeignKeyConstraint(
            ["import_job_id"],
            ["import_jobs.id"],
            name="fk_import_errors_import_job_id_import_jobs",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_import_errors"),
    )
    op.create_index(
        "ix_import_errors_import_job_id", "import_errors", ["import_job_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_import_errors_import_job_id", table_name="import_errors")
    op.drop_table("import_errors")
    op.drop_index("ix_import_jobs_created_at", table_name="import_jobs")
    op.drop_index("ix_import_jobs_status", table_name="import_jobs")
    op.drop_index("ix_import_jobs_uploaded_by", table_name="import_jobs")
    op.drop_table("import_jobs")
    import_status.drop(op.get_bind(), checkfirst=True)
