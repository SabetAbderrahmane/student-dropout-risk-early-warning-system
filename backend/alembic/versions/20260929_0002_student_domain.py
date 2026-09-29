"""create student domain tables

Revision ID: 20260929_0002
Revises: 20260929_0001
Create Date: 2026-09-29 00:30:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260929_0002"
down_revision: str | None = "20260929_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "students",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_number", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("gender", sa.String(length=50), nullable=True),
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
        sa.CheckConstraint(
            "length(trim(student_number)) > 0", name="student_number_not_blank"
        ),
        sa.CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
        sa.PrimaryKeyConstraint("id", name="pk_students"),
    )
    op.create_index("ix_students_student_number", "students", ["student_number"], unique=True)
    op.create_index("ix_students_name", "students", ["name"], unique=False)

    op.create_table(
        "admission_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("admission_method", sa.String(length=100), nullable=False),
        sa.Column("admission_grade", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column("previous_qualification", sa.String(length=200), nullable=False),
        sa.Column(
            "previous_qualification_grade",
            sa.Numeric(precision=8, scale=2),
            nullable=False,
        ),
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
        sa.CheckConstraint(
            "length(trim(admission_method)) > 0", name="method_not_blank"
        ),
        sa.CheckConstraint(
            "length(trim(previous_qualification)) > 0",
            name="previous_qualification_not_blank",
        ),
        sa.CheckConstraint(
            "admission_grade >= 0", name="admission_grade_nonnegative"
        ),
        sa.CheckConstraint(
            "previous_qualification_grade >= 0",
            name="previous_qualification_grade_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["students.id"],
            name="fk_admission_records_student_id_students",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_admission_records"),
    )
    op.create_index(
        "ix_admission_records_student_id",
        "admission_records",
        ["student_id"],
        unique=True,
    )

    op.create_table(
        "first_semester_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("credited_units", sa.Integer(), nullable=False),
        sa.Column("enrolled_units", sa.Integer(), nullable=False),
        sa.Column("evaluations", sa.Integer(), nullable=False),
        sa.Column("approved_units", sa.Integer(), nullable=False),
        sa.Column("average_grade", sa.Numeric(precision=8, scale=2), nullable=False),
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
        sa.CheckConstraint("credited_units >= 0", name="credited_units_nonnegative"),
        sa.CheckConstraint("enrolled_units >= 0", name="enrolled_units_nonnegative"),
        sa.CheckConstraint("evaluations >= 0", name="evaluations_nonnegative"),
        sa.CheckConstraint("approved_units >= 0", name="approved_units_nonnegative"),
        sa.CheckConstraint("average_grade >= 0", name="average_grade_nonnegative"),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["students.id"],
            name="fk_first_semester_records_student_id_students",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_first_semester_records"),
    )
    op.create_index(
        "ix_first_semester_records_student_id",
        "first_semester_records",
        ["student_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_first_semester_records_student_id",
        table_name="first_semester_records",
    )
    op.drop_table("first_semester_records")
    op.drop_index("ix_admission_records_student_id", table_name="admission_records")
    op.drop_table("admission_records")
    op.drop_index("ix_students_name", table_name="students")
    op.drop_index("ix_students_student_number", table_name="students")
    op.drop_table("students")
