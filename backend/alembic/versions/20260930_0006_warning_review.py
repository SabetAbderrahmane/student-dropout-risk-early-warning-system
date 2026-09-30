"""add warnings and append-only advisor reviews

Revision ID: 20260930_0006
Revises: 20260930_0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "20260930_0006"
down_revision: str | None = "20260930_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

priority = postgresql.ENUM(
    "P1_URGENT",
    "P2_ELEVATED",
    "P3_STANDARD",
    name="warning_priority",
    create_type=False,
)
state = postgresql.ENUM(
    "PENDING_REVIEW",
    "CONFIRMED",
    "DISMISSED",
    name="warning_review_state",
    create_type=False,
)
decision = postgresql.ENUM(
    "CONFIRMED", "DISMISSED", name="warning_review_decision", create_type=False
)
risk = postgresql.ENUM("LOW", "MEDIUM", "HIGH", name="risk_level", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    for enum in (priority, state, decision):
        enum.create(bind, checkfirst=True)
    op.create_unique_constraint(
        "uq_prediction_results_warning_identity",
        "prediction_results",
        ["id", "student_id", "risk_level"],
    )
    op.create_table(
        "warnings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("prediction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("risk_level", risk, nullable=False),
        sa.Column("priority", priority, nullable=False),
        sa.Column(
            "review_state", state, server_default="PENDING_REVIEW", nullable=False
        ),
        sa.Column("assigned_to", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.CheckConstraint("risk_level <> 'LOW'", name="qualifying_risk"),
        sa.ForeignKeyConstraint(
            ["prediction_id"],
            ["prediction_results.id"],
            name="fk_warnings_prediction_id_prediction_results",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["prediction_id", "student_id", "risk_level"],
            [
                "prediction_results.id",
                "prediction_results.student_id",
                "prediction_results.risk_level",
            ],
            name="fk_warnings_prediction_identity_prediction_results",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["students.id"],
            name="fk_warnings_student_id_students",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["assigned_to"],
            ["users.id"],
            name="fk_warnings_assigned_to_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_warnings"),
        sa.UniqueConstraint("prediction_id", name="uq_warnings_prediction_id"),
    )
    for field in (
        "student_id",
        "risk_level",
        "priority",
        "review_state",
        "assigned_to",
        "created_at",
    ):
        op.create_index(f"ix_warnings_{field}", "warnings", [field])
    op.create_table(
        "warning_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("warning_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reviewer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("decision", decision, nullable=False),
        sa.Column("note", sa.String(length=4000), nullable=False),
        sa.Column(
            "reviewed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("length(trim(note)) > 0", name="note_not_blank"),
        sa.ForeignKeyConstraint(
            ["warning_id"],
            ["warnings.id"],
            name="fk_warning_reviews_warning_id_warnings",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_id"],
            ["users.id"],
            name="fk_warning_reviews_reviewer_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_warning_reviews"),
    )
    for field in ("warning_id", "reviewer_id", "reviewed_at"):
        op.create_index(f"ix_warning_reviews_{field}", "warning_reviews", [field])


def downgrade() -> None:
    for field in ("reviewed_at", "reviewer_id", "warning_id"):
        op.drop_index(f"ix_warning_reviews_{field}", table_name="warning_reviews")
    op.drop_table("warning_reviews")
    for field in (
        "created_at",
        "assigned_to",
        "review_state",
        "priority",
        "risk_level",
        "student_id",
    ):
        op.drop_index(f"ix_warnings_{field}", table_name="warnings")
    op.drop_table("warnings")
    op.drop_constraint(
        "uq_prediction_results_warning_identity", "prediction_results", type_="unique"
    )
    for enum in (decision, state, priority):
        enum.drop(op.get_bind(), checkfirst=True)
