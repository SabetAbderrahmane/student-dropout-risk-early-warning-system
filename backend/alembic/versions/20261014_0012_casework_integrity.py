"""Adopt revisions and structured actions without rewriting domain history."""

import sqlalchemy as sa
from alembic import op

revision = "20261014_0012"
down_revision = "20261013_0011"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("warnings", "interventions", "follow_ups"):
        op.add_column(
            table,
            sa.Column("revision", sa.Integer(), server_default="0", nullable=False),
        )
        op.create_check_constraint("revision_nonnegative", table, "revision >= 0")
    op.create_table(
        "casework_action_audit",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "actor_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column(
            "warning_id", sa.Uuid(), sa.ForeignKey("warnings.id", ondelete="RESTRICT")
        ),
        sa.Column(
            "intervention_id",
            sa.Uuid(),
            sa.ForeignKey("interventions.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "follow_up_id",
            sa.Uuid(),
            sa.ForeignKey("follow_ups.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("reason", sa.String(4000)),
        sa.Column("before_values", sa.JSON(), nullable=False),
        sa.Column("after_values", sa.JSON(), nullable=False),
        sa.Column("correlation_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "action IN ('ASSIGN', 'REVIEW', 'RECONSIDER', 'CREATE_INTERVENTION', 'UPDATE_INTERVENTION', 'ADD_NOTE', 'COMPLETE_INTERVENTION', 'CANCEL_INTERVENTION', 'CREATE_FOLLOW_UP', 'UPDATE_FOLLOW_UP', 'COMPLETE_FOLLOW_UP', 'CANCEL_FOLLOW_UP', 'TRANSFER_INTERVENTION', 'RECOVER_FOLLOW_UP')",
            name="valid_action",
        ),
    )
    for entity in ("actor", "warning", "intervention", "follow_up"):
        op.create_index(
            f"ix_casework_audit_{entity}_time",
            "casework_action_audit",
            [f"{entity}_id", "created_at"],
        )
    op.create_index(
        "ix_casework_action_audit_correlation_id",
        "casework_action_audit",
        ["correlation_id"],
    )


def downgrade():
    op.drop_table("casework_action_audit")
    for table in ("follow_ups", "interventions", "warnings"):
        op.drop_constraint(
            op.f(f"ck_{table}_revision_nonnegative"), table, type_="check"
        )
        op.drop_column(table, "revision")
