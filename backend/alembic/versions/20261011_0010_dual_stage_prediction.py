"""Stage-scoped models and additive multiclass prediction history."""

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261011_0010"
down_revision = "20261011_0009"
branch_labels = None
depends_on = None

# Freeze the persisted contract here so later application changes cannot alter history.
CLASS_PROBABILITY_CHECK = """
class_probabilities IS NULL OR CASE WHEN
jsonb_typeof(class_probabilities) = 'object' AND
class_probabilities - 'DROPOUT' - 'ENROLLED' - 'GRADUATE' = '{}'::jsonb AND
jsonb_typeof(class_probabilities->'DROPOUT') = 'number' AND
jsonb_typeof(class_probabilities->'ENROLLED') = 'number' AND
jsonb_typeof(class_probabilities->'GRADUATE') = 'number'
THEN
(class_probabilities->>'DROPOUT')::double precision BETWEEN 0 AND 1 AND
(class_probabilities->>'ENROLLED')::double precision BETWEEN 0 AND 1 AND
(class_probabilities->>'GRADUATE')::double precision BETWEEN 0 AND 1 AND
abs((class_probabilities->>'DROPOUT')::double precision +
    (class_probabilities->>'ENROLLED')::double precision +
    (class_probabilities->>'GRADUATE')::double precision - 1) <= 0.000001 AND
abs((class_probabilities->>'DROPOUT')::double precision - probability) <= 0.000000000001 AND
predicted_outcome = CASE
WHEN (class_probabilities->>'DROPOUT')::double precision >= (class_probabilities->>'ENROLLED')::double precision
 AND (class_probabilities->>'DROPOUT')::double precision >= (class_probabilities->>'GRADUATE')::double precision THEN 'DROPOUT'
WHEN (class_probabilities->>'ENROLLED')::double precision >= (class_probabilities->>'GRADUATE')::double precision THEN 'ENROLLED'
ELSE 'GRADUATE' END
ELSE FALSE END
"""


def upgrade():
    op.execute(
        "LOCK TABLE model_versions, prediction_results IN SHARE ROW EXCLUSIVE MODE"
    )
    for table in ("model_versions", "prediction_results"):
        op.add_column(
            table,
            sa.Column(
                "prediction_stage",
                sa.String(32),
                nullable=False,
                server_default="FIRST_SEMESTER",
            ),
        )
        op.add_column(
            table,
            sa.Column(
                "model_target_type",
                sa.String(32),
                nullable=False,
                server_default="BINARY_DROPOUT",
            ),
        )
        op.create_check_constraint(
            "prediction_stage_valid",
            table,
            "prediction_stage IN ('ENROLLMENT', 'FIRST_SEMESTER')",
        )
        op.create_check_constraint(
            "model_target_type_valid",
            table,
            "model_target_type IN ('BINARY_DROPOUT', 'MULTICLASS_OUTCOME')",
        )
    op.create_check_constraint(
        "binary_stage_compatible",
        "model_versions",
        "model_target_type <> 'BINARY_DROPOUT' OR prediction_stage = 'FIRST_SEMESTER'",
    )
    op.drop_index("uq_model_versions_one_active", table_name="model_versions")
    op.create_index(
        "uq_model_versions_one_active_per_scope",
        "model_versions",
        ["prediction_stage", "model_target_type"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.create_unique_constraint(
        "uq_model_versions_prediction_contract",
        "model_versions",
        ["id", "prediction_stage", "model_target_type"],
    )
    op.drop_constraint(
        "fk_prediction_results_model_version_id_model_versions",
        "prediction_results",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_prediction_results_model_contract_model_versions",
        "prediction_results",
        "model_versions",
        ["model_version_id", "prediction_stage", "model_target_type"],
        ["id", "prediction_stage", "model_target_type"],
        ondelete="RESTRICT",
    )
    op.add_column(
        "prediction_results",
        sa.Column("predicted_outcome", sa.String(32), nullable=True),
    )
    op.add_column(
        "prediction_results",
        sa.Column("class_probabilities", postgresql.JSONB(), nullable=True),
    )
    op.create_index(
        "ix_prediction_results_prediction_stage",
        "prediction_results",
        ["prediction_stage"],
    )
    op.create_check_constraint(
        "predicted_outcome_valid",
        "prediction_results",
        "predicted_outcome IS NULL OR predicted_outcome IN ('DROPOUT', 'ENROLLED', 'GRADUATE')",
    )
    op.create_check_constraint(
        "classification_fields_compatible",
        "prediction_results",
        "(model_target_type = 'BINARY_DROPOUT' AND prediction_stage = 'FIRST_SEMESTER' AND predicted_outcome IS NULL AND class_probabilities IS NULL) OR (model_target_type = 'MULTICLASS_OUTCOME' AND predicted_outcome IS NOT NULL AND class_probabilities IS NOT NULL)",
    )
    op.create_check_constraint(
        "class_probabilities_valid", "prediction_results", CLASS_PROBABILITY_CHECK
    )
    op.create_table(
        "model_validations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "model_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("model_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("artifact_sha256", sa.String(64), nullable=False),
        sa.Column(
            "student_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("students.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "validated_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("checks", postgresql.JSONB(), nullable=False),
        sa.Column(
            "validated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "length(artifact_sha256) = 64", name="artifact_sha256_length"
        ),
    )
    op.create_index(
        "ix_model_validations_model_version_id",
        "model_validations",
        ["model_version_id"],
    )
    op.create_table(
        "model_activation_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "model_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("model_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "previous_model_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("model_versions.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "validation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("model_validations.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "acted_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "action IN ('MIGRATED_ACTIVE', 'ACTIVATED')", name="action_valid"
        ),
    )
    op.create_index(
        "ix_model_activation_events_model_version_id",
        "model_activation_events",
        ["model_version_id"],
    )
    connection = op.get_bind()
    for model_id in connection.scalars(
        sa.text("SELECT id FROM model_versions WHERE is_active")
    ):
        connection.execute(
            sa.text(
                "INSERT INTO model_activation_events (id, model_version_id, action) VALUES (:id,:model,'MIGRATED_ACTIVE')"
            ),
            {"id": uuid.uuid4(), "model": model_id},
        )


def downgrade():
    # Refuse a lossy rollback instead of silently dropping multiclass outcomes.
    connection = op.get_bind()
    op.execute(
        "LOCK TABLE model_versions, prediction_results IN SHARE ROW EXCLUSIVE MODE"
    )
    if connection.scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM model_versions WHERE model_target_type = 'MULTICLASS_OUTCOME')"
        )
    ):
        raise RuntimeError(
            "B1 models or predictions exist. Archive and explicitly resolve them before rollback; no data were deleted."
        )
    op.drop_table("model_activation_events")
    op.drop_table("model_validations")
    op.drop_constraint("class_probabilities_valid", "prediction_results", type_="check")
    op.drop_constraint(
        "classification_fields_compatible", "prediction_results", type_="check"
    )
    op.drop_constraint("predicted_outcome_valid", "prediction_results", type_="check")
    op.drop_index(
        "ix_prediction_results_prediction_stage", table_name="prediction_results"
    )
    op.drop_column("prediction_results", "class_probabilities")
    op.drop_column("prediction_results", "predicted_outcome")
    op.drop_constraint(
        "fk_prediction_results_model_contract_model_versions",
        "prediction_results",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_prediction_results_model_version_id_model_versions",
        "prediction_results",
        "model_versions",
        ["model_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_constraint(
        "uq_model_versions_prediction_contract", "model_versions", type_="unique"
    )
    op.drop_index("uq_model_versions_one_active_per_scope", table_name="model_versions")
    op.create_index(
        "uq_model_versions_one_active",
        "model_versions",
        ["is_active"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.drop_constraint("binary_stage_compatible", "model_versions", type_="check")
    for table in ("prediction_results", "model_versions"):
        op.drop_constraint("prediction_stage_valid", table, type_="check")
        op.drop_constraint("model_target_type_valid", table, type_="check")
        op.drop_column(table, "model_target_type")
        op.drop_column(table, "prediction_stage")
