"""Add staged CSV batches, rows and immutable action audit.

Revision ID: 20261004_0008
Revises: 20260930_0007
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261004_0008"
down_revision = "20260930_0007"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "staged_import_batches",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("uploaded_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "REVIEW_REQUIRED",
                "READY_TO_COMMIT",
                "COMMITTED",
                "CANCELLED",
                native_enum=False,
                create_constraint=True,
                name="staged_import_status",
            ),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        *[
            sa.Column(name, sa.Integer(), nullable=False)
            for name in (
                "total_rows",
                "included_rows",
                "excluded_rows",
                "valid_rows",
                "invalid_rows",
                "valid_included_rows",
                "invalid_included_rows",
                "validation_issue_count",
                "included_issue_count",
            )
        ],
        sa.Column(
            "import_job_id", sa.Uuid(), sa.ForeignKey("import_jobs.id"), unique=True
        ),
        sa.Column("last_commit_error", sa.String(500)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("version >= 1", name="version_positive"),
        sa.CheckConstraint(
            "total_rows >= 0 AND included_rows >= 0 AND excluded_rows >= 0",
            name="counts_nonnegative",
        ),
        sa.CheckConstraint(
            "included_rows + excluded_rows = total_rows",
            name="inclusion_counts_consistent",
        ),
        sa.CheckConstraint(
            "valid_rows >= 0 AND invalid_rows >= 0 AND valid_rows + invalid_rows = total_rows",
            name="validation_counts_consistent",
        ),
        sa.CheckConstraint(
            "valid_included_rows >= 0 AND invalid_included_rows >= 0 AND valid_included_rows + invalid_included_rows = included_rows",
            name="included_validation_consistent",
        ),
        sa.CheckConstraint(
            "validation_issue_count >= 0 AND included_issue_count >= 0",
            name="issue_counts_nonnegative",
        ),
    )
    op.create_index(
        "ix_staged_import_batches_status", "staged_import_batches", ["status"]
    )
    op.create_index(
        "ix_staged_import_batches_created_at", "staged_import_batches", ["created_at"]
    )
    op.create_table(
        "staged_import_rows",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "batch_id",
            sa.Uuid(),
            sa.ForeignKey("staged_import_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "original_values",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "edited_values",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column("student_number", sa.String(131072), nullable=False),
        sa.Column("student_name", sa.String(131072), nullable=False),
        sa.Column("included", sa.Boolean(), nullable=False),
        sa.Column("is_valid", sa.Boolean(), nullable=False),
        sa.Column(
            "issues",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.UniqueConstraint("batch_id", "row_number"),
        sa.CheckConstraint("row_number >= 2", name="row_number_valid"),
        sa.CheckConstraint("version >= 1", name="version_positive"),
    )
    op.create_index(
        "ix_staged_import_rows_batch_id", "staged_import_rows", ["batch_id"]
    )
    op.create_table(
        "staged_import_actions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "batch_id",
            sa.Uuid(),
            sa.ForeignKey("staged_import_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("row_id", sa.Uuid(), sa.ForeignKey("staged_import_rows.id")),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("batch_version", sa.Integer(), nullable=False),
        sa.Column(
            "changes",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_staged_import_actions_batch_id", "staged_import_actions", ["batch_id"]
    )


def downgrade():
    op.drop_table("staged_import_actions")
    op.drop_table("staged_import_rows")
    op.drop_table("staged_import_batches")
