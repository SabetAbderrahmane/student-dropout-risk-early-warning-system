"""Index-only B2 migration; no prediction or support records are rewritten."""

from alembic import op
import sqlalchemy as sa

revision = "20261013_0011"
down_revision = "20261011_0010"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "ix_predictions_student_stage",
        "prediction_results",
        ["student_id", "prediction_stage"],
    )
    op.create_index(
        "ix_predictions_student_model_latest",
        "prediction_results",
        [
            "student_id",
            "model_version_id",
            sa.text("predicted_at DESC"),
            sa.text("id DESC"),
        ],
    )
    op.create_index(
        "ix_predictions_student_latest",
        "prediction_results",
        ["student_id", sa.text("predicted_at DESC"), sa.text("id DESC")],
    )


def downgrade():
    op.drop_index("ix_predictions_student_stage", table_name="prediction_results")
    op.drop_index("ix_predictions_student_latest", table_name="prediction_results")
    op.drop_index(
        "ix_predictions_student_model_latest", table_name="prediction_results"
    )
