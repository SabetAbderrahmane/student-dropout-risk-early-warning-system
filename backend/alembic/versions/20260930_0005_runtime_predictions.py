"""persist runtime model versions and append-only predictions

Revision ID: 20260930_0005
Revises: 20260929_0004
Create Date: 2026-09-30 23:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260930_0005"
down_revision: str | None = "20260929_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

risk_level = postgresql.ENUM(
    "LOW", "MEDIUM", "HIGH", name="risk_level", create_type=False
)


def upgrade() -> None:
    risk_level.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "model_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("model_version", sa.String(length=150), nullable=False),
        sa.Column("feature_schema_version", sa.String(length=150), nullable=False),
        sa.Column("trained_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("low_threshold", sa.Float(), nullable=False),
        sa.Column("high_threshold", sa.Float(), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("artifact_path", sa.String(length=500), nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "low_threshold >= 0 AND low_threshold < high_threshold",
            name="thresholds_ordered",
        ),
        sa.CheckConstraint("high_threshold <= 1", name="high_threshold_maximum"),
        sa.PrimaryKeyConstraint("id", name="pk_model_versions"),
    )
    op.create_index(
        "ix_model_versions_model_version",
        "model_versions",
        ["model_version"],
        unique=True,
    )
    op.create_index("ix_model_versions_is_active", "model_versions", ["is_active"])
    op.create_index(
        "uq_model_versions_one_active",
        "model_versions",
        ["is_active"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )

    op.create_table(
        "prediction_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("probability", sa.Float(), nullable=False),
        sa.Column("risk_level", risk_level, nullable=False),
        sa.Column(
            "feature_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "explanation", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "predicted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint(
            "probability >= 0 AND probability <= 1", name="probability_range"
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["students.id"],
            name="fk_prediction_results_student_id_students",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["model_version_id"],
            ["model_versions.id"],
            name="fk_prediction_results_model_version_id_model_versions",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_prediction_results_created_by_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_prediction_results"),
    )
    op.create_index(
        "ix_prediction_results_student_id", "prediction_results", ["student_id"]
    )
    op.create_index(
        "ix_prediction_results_model_version_id",
        "prediction_results",
        ["model_version_id"],
    )
    op.create_index(
        "ix_prediction_results_risk_level", "prediction_results", ["risk_level"]
    )
    op.create_index(
        "ix_prediction_results_predicted_at", "prediction_results", ["predicted_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_prediction_results_predicted_at", table_name="prediction_results")
    op.drop_index("ix_prediction_results_risk_level", table_name="prediction_results")
    op.drop_index(
        "ix_prediction_results_model_version_id", table_name="prediction_results"
    )
    op.drop_index("ix_prediction_results_student_id", table_name="prediction_results")
    op.drop_table("prediction_results")
    op.drop_index("uq_model_versions_one_active", table_name="model_versions")
    op.drop_index("ix_model_versions_is_active", table_name="model_versions")
    op.drop_index("ix_model_versions_model_version", table_name="model_versions")
    op.drop_table("model_versions")
    risk_level.drop(op.get_bind(), checkfirst=True)
