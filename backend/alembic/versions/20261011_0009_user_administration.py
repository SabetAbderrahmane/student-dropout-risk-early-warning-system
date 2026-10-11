"""Secure account lifecycle, unique login namespace and administration audit."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261011_0009"
down_revision = "20261004_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    # Freeze populated accounts until validation and namespace backfill finish.
    connection.execute(sa.text("LOCK TABLE users IN SHARE ROW EXCLUSIVE MODE"))
    collision = connection.scalar(
        sa.text("""
        SELECT identifier FROM (
            SELECT id, lower(trim(username)) AS identifier FROM users
            UNION
            SELECT id, lower(trim(email)) AS identifier FROM users
        ) AS identifiers GROUP BY identifier HAVING count(DISTINCT id) > 1 LIMIT 1
    """)
    )
    if collision is not None:
        raise RuntimeError(
            "Conflicting case-insensitive username/email login identifiers exist. "
            "Resolve the conflicting accounts explicitly before retrying; no accounts were changed."
        )
    op.add_column(
        "users",
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "users",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_check_constraint(
        "token_version_nonnegative", "users", "token_version >= 0"
    )
    op.create_index(
        "uq_users_username_ci",
        "users",
        [sa.text("lower(ltrim(rtrim(username)))")],
        unique=True,
    )
    op.create_index(
        "uq_users_email_ci",
        "users",
        [sa.text("lower(ltrim(rtrim(email)))")],
        unique=True,
    )
    op.create_table(
        "user_login_identifiers",
        sa.Column("identifier", sa.String(320), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_user_login_identifiers_user_id", "user_login_identifiers", ["user_id"]
    )
    connection.execute(
        sa.text("""
        INSERT INTO user_login_identifiers (identifier, user_id)
        SELECT lower(trim(username)), id FROM users UNION SELECT lower(trim(email)), id FROM users
    """)
    )
    op.create_table(
        "user_administration_audit",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "target_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("changed_fields", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "action IN ('USER_CREATED', 'USER_UPDATED', 'ROLE_CHANGED', 'USER_ACTIVATED', 'USER_DEACTIVATED', 'PASSWORD_RESET', 'PASSWORD_CHANGED')",
            name="valid_action",
        ),
    )
    for column in ("actor_id", "target_id", "created_at"):
        op.create_index(
            "ix_user_administration_audit_" + column,
            "user_administration_audit",
            [column],
        )


def downgrade() -> None:
    op.drop_table("user_administration_audit")
    op.drop_table("user_login_identifiers")
    op.drop_index("uq_users_email_ci", table_name="users")
    op.drop_index("uq_users_username_ci", table_name="users")
    op.drop_constraint("token_version_nonnegative", "users", type_="check")
    op.drop_column("users", "token_version")
    op.drop_column("users", "must_change_password")
