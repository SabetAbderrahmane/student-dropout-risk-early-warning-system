"""add interventions and follow-ups

Revision ID: 20260930_0007
Revises: 20260930_0006
Create Date: 2026-09-30 22:39:59.500746
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260930_0007"
down_revision: Union[str, None] = "20260930_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

new_enums = (
    postgresql.ENUM(
        "ACADEMIC_TUTORING",
        "ACADEMIC_ADVISING",
        "STUDY_PERFORMANCE_PLAN",
        "FINANCIAL_SUPPORT_REFERRAL",
        "ADMINISTRATIVE_SUPPORT_REFERRAL",
        "OTHER",
        name="intervention_type",
        create_type=False,
    ),
    postgresql.ENUM(
        "PLANNED",
        "IN_PROGRESS",
        "ACTION_REQUIRED",
        "COMPLETED",
        "CANCELLED",
        name="intervention_status",
        create_type=False,
    ),
    postgresql.ENUM(
        "SUPPORT_COMPLETED",
        "GOALS_PARTIALLY_MET",
        "REFERRED_FOR_ADDITIONAL_SUPPORT",
        "STUDENT_UNRESPONSIVE",
        "OTHER",
        name="intervention_outcome",
        create_type=False,
    ),
    postgresql.ENUM(
        "IN_PERSON",
        "PHONE",
        "EMAIL",
        "ONLINE_MEETING",
        "OTHER",
        name="follow_up_method",
        create_type=False,
    ),
    postgresql.ENUM(
        "SCHEDULED",
        "COMPLETED",
        "CANCELLED",
        name="follow_up_status",
        create_type=False,
    ),
    postgresql.ENUM(
        "COMPLETED",
        "PROGRESS_OBSERVED",
        "NO_RESPONSE",
        "RESCHEDULED",
        "ESCALATION_REQUIRED",
        "INTERVENTION_COMPLETED",
        name="follow_up_outcome",
        create_type=False,
    ),
)


def upgrade() -> None:
    for enum in new_enums:
        enum.create(op.get_bind(), checkfirst=True)
    op.create_unique_constraint(
        "uq_warnings_intervention_identity", "warnings", ["id", "student_id"]
    )
    op.create_table(
        "interventions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("warning_id", sa.Uuid(), nullable=False),
        sa.Column(
            "type",
            postgresql.ENUM(
                "ACADEMIC_TUTORING",
                "ACADEMIC_ADVISING",
                "STUDY_PERFORMANCE_PLAN",
                "FINANCIAL_SUPPORT_REFERRAL",
                "ADMINISTRATIVE_SUPPORT_REFERRAL",
                "OTHER",
                name="intervention_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=250), nullable=False),
        sa.Column("description", sa.String(length=4000), nullable=False),
        sa.Column(
            "priority",
            postgresql.ENUM(
                "P1_URGENT",
                "P2_ELEVATED",
                "P3_STANDARD",
                name="warning_priority",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "PLANNED",
                "IN_PROGRESS",
                "ACTION_REQUIRED",
                "COMPLETED",
                "CANCELLED",
                name="intervention_status",
                create_type=False,
            ),
            server_default="PLANNED",
            nullable=False,
        ),
        sa.Column("assigned_to", sa.Uuid(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "completion_outcome",
            postgresql.ENUM(
                "SUPPORT_COMPLETED",
                "GOALS_PARTIALLY_MET",
                "REFERRED_FOR_ADDITIONAL_SUPPORT",
                "STUDENT_UNRESPONSIVE",
                "OTHER",
                name="intervention_outcome",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column("completion_notes", sa.String(length=4000), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(status = 'COMPLETED' AND completed_at IS NOT NULL AND completion_outcome IS NOT NULL AND completion_notes IS NOT NULL) OR (status <> 'COMPLETED' AND completed_at IS NULL AND completion_outcome IS NULL)",
            name=op.f("ck_interventions_completion_metadata"),
        ),
        sa.CheckConstraint(
            "length(trim(description)) > 0",
            name=op.f("ck_interventions_description_not_blank"),
        ),
        sa.CheckConstraint(
            "length(trim(title)) > 0", name=op.f("ck_interventions_title_not_blank")
        ),
        sa.CheckConstraint(
            "target_date IS NULL OR target_date >= start_date",
            name=op.f("ck_interventions_valid_date_range"),
        ),
        sa.ForeignKeyConstraint(
            ["assigned_to"],
            ["users.id"],
            name=op.f("fk_interventions_assigned_to_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_interventions_created_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["students.id"],
            name=op.f("fk_interventions_student_id_students"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["warning_id", "student_id"],
            ["warnings.id", "warnings.student_id"],
            name="fk_interventions_warning_identity_warnings",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["warning_id"],
            ["warnings.id"],
            name=op.f("fk_interventions_warning_id_warnings"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_interventions")),
        sa.UniqueConstraint(
            "id", "student_id", name="uq_interventions_follow_up_identity"
        ),
    )
    op.create_index(
        op.f("ix_interventions_assigned_to"),
        "interventions",
        ["assigned_to"],
        unique=False,
    )
    op.create_index(
        op.f("ix_interventions_created_at"),
        "interventions",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_interventions_priority"), "interventions", ["priority"], unique=False
    )
    op.create_index(
        op.f("ix_interventions_status"), "interventions", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_interventions_student_id"),
        "interventions",
        ["student_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_interventions_type"), "interventions", ["type"], unique=False
    )
    op.create_index(
        op.f("ix_interventions_updated_at"),
        "interventions",
        ["updated_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_interventions_warning_id"),
        "interventions",
        ["warning_id"],
        unique=False,
    )
    op.create_table(
        "follow_ups",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("intervention_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("assigned_to", sa.Uuid(), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "method",
            postgresql.ENUM(
                "IN_PERSON",
                "PHONE",
                "EMAIL",
                "ONLINE_MEETING",
                "OTHER",
                name="follow_up_method",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("purpose", sa.String(length=2000), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "SCHEDULED",
                "COMPLETED",
                "CANCELLED",
                name="follow_up_status",
                create_type=False,
            ),
            server_default="SCHEDULED",
            nullable=False,
        ),
        sa.Column(
            "outcome",
            postgresql.ENUM(
                "COMPLETED",
                "PROGRESS_OBSERVED",
                "NO_RESPONSE",
                "RESCHEDULED",
                "ESCALATION_REQUIRED",
                "INTERVENTION_COMPLETED",
                name="follow_up_outcome",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column("notes", sa.String(length=4000), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(status = 'COMPLETED' AND outcome IS NOT NULL AND notes IS NOT NULL AND completed_at IS NOT NULL) OR (status <> 'COMPLETED' AND outcome IS NULL AND completed_at IS NULL)",
            name=op.f("ck_follow_ups_completion_metadata"),
        ),
        sa.CheckConstraint(
            "length(trim(purpose)) > 0", name=op.f("ck_follow_ups_purpose_not_blank")
        ),
        sa.ForeignKeyConstraint(
            ["assigned_to"],
            ["users.id"],
            name=op.f("fk_follow_ups_assigned_to_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_follow_ups_created_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["intervention_id", "student_id"],
            ["interventions.id", "interventions.student_id"],
            name="fk_follow_ups_intervention_identity_interventions",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["intervention_id"],
            ["interventions.id"],
            name=op.f("fk_follow_ups_intervention_id_interventions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["students.id"],
            name=op.f("fk_follow_ups_student_id_students"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_follow_ups")),
    )
    op.create_index(
        op.f("ix_follow_ups_assigned_to"), "follow_ups", ["assigned_to"], unique=False
    )
    op.create_index(
        op.f("ix_follow_ups_created_at"), "follow_ups", ["created_at"], unique=False
    )
    op.create_index(
        op.f("ix_follow_ups_intervention_id"),
        "follow_ups",
        ["intervention_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_follow_ups_scheduled_for"),
        "follow_ups",
        ["scheduled_for"],
        unique=False,
    )
    op.create_index(
        op.f("ix_follow_ups_status"), "follow_ups", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_follow_ups_student_id"), "follow_ups", ["student_id"], unique=False
    )
    op.create_table(
        "intervention_notes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("intervention_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("note", sa.String(length=4000), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(trim(note)) > 0", name=op.f("ck_intervention_notes_note_not_blank")
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["users.id"],
            name=op.f("fk_intervention_notes_author_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["intervention_id"],
            ["interventions.id"],
            name=op.f("fk_intervention_notes_intervention_id_interventions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_intervention_notes")),
    )
    op.create_index(
        op.f("ix_intervention_notes_author_id"),
        "intervention_notes",
        ["author_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_intervention_notes_created_at"),
        "intervention_notes",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_intervention_notes_intervention_id"),
        "intervention_notes",
        ["intervention_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_intervention_notes_intervention_id"), table_name="intervention_notes"
    )
    op.drop_index(
        op.f("ix_intervention_notes_created_at"), table_name="intervention_notes"
    )
    op.drop_index(
        op.f("ix_intervention_notes_author_id"), table_name="intervention_notes"
    )
    op.drop_table("intervention_notes")
    op.drop_index(op.f("ix_follow_ups_student_id"), table_name="follow_ups")
    op.drop_index(op.f("ix_follow_ups_status"), table_name="follow_ups")
    op.drop_index(op.f("ix_follow_ups_scheduled_for"), table_name="follow_ups")
    op.drop_index(op.f("ix_follow_ups_intervention_id"), table_name="follow_ups")
    op.drop_index(op.f("ix_follow_ups_created_at"), table_name="follow_ups")
    op.drop_index(op.f("ix_follow_ups_assigned_to"), table_name="follow_ups")
    op.drop_table("follow_ups")
    op.drop_index(op.f("ix_interventions_warning_id"), table_name="interventions")
    op.drop_index(op.f("ix_interventions_updated_at"), table_name="interventions")
    op.drop_index(op.f("ix_interventions_type"), table_name="interventions")
    op.drop_index(op.f("ix_interventions_student_id"), table_name="interventions")
    op.drop_index(op.f("ix_interventions_status"), table_name="interventions")
    op.drop_index(op.f("ix_interventions_priority"), table_name="interventions")
    op.drop_index(op.f("ix_interventions_created_at"), table_name="interventions")
    op.drop_index(op.f("ix_interventions_assigned_to"), table_name="interventions")
    op.drop_table("interventions")
    op.drop_constraint("uq_warnings_intervention_identity", "warnings", type_="unique")
    for enum in reversed(new_enums):
        enum.drop(op.get_bind(), checkfirst=True)
