"""extend schema for the prediction feature contract

Revision ID: 20260929_0003
Revises: 20260929_0002
Create Date: 2026-09-29 01:30:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260929_0003"
down_revision: str | None = "20260929_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "students", sa.Column("marital_status_code", sa.Integer(), nullable=True)
    )
    op.add_column(
        "students", sa.Column("nationality_code", sa.Integer(), nullable=True)
    )
    op.add_column("students", sa.Column("displaced", sa.Integer(), nullable=True))
    op.add_column(
        "students", sa.Column("educational_special_needs", sa.Integer(), nullable=True)
    )
    op.add_column("students", sa.Column("debtor", sa.Integer(), nullable=True))
    op.add_column(
        "students", sa.Column("tuition_fees_up_to_date", sa.Integer(), nullable=True)
    )
    op.add_column("students", sa.Column("gender_code", sa.Integer(), nullable=True))
    op.add_column(
        "students", sa.Column("scholarship_holder", sa.Integer(), nullable=True)
    )
    op.add_column(
        "students", sa.Column("age_at_enrollment", sa.Integer(), nullable=True)
    )
    op.add_column(
        "students", sa.Column("international_student", sa.Integer(), nullable=True)
    )

    op.create_check_constraint(
        "marital_status_code_valid",
        "students",
        "marital_status_code IS NULL OR marital_status_code IN (1, 2, 3, 4, 5, 6)",
    )
    for column in (
        "displaced",
        "educational_special_needs",
        "debtor",
        "tuition_fees_up_to_date",
        "gender_code",
        "scholarship_holder",
        "international_student",
    ):
        op.create_check_constraint(
            f"{column}_binary", "students", f"{column} IS NULL OR {column} IN (0, 1)"
        )
    op.create_check_constraint(
        "age_at_enrollment_nonnegative",
        "students",
        "age_at_enrollment IS NULL OR age_at_enrollment >= 0",
    )

    for column in (
        "application_mode_code",
        "application_order",
        "course_code",
        "daytime_evening_attendance",
        "previous_qualification_code",
        "mother_qualification_code",
        "father_qualification_code",
        "mother_occupation_code",
        "father_occupation_code",
    ):
        op.add_column(
            "admission_records", sa.Column(column, sa.Integer(), nullable=True)
        )
    for column in ("unemployment_rate", "inflation_rate", "gdp"):
        op.add_column(
            "admission_records", sa.Column(column, sa.Numeric(), nullable=True)
        )
    op.create_check_constraint(
        "admission_grade_maximum", "admission_records", "admission_grade <= 200"
    )
    op.create_check_constraint(
        "previous_qualification_grade_maximum",
        "admission_records",
        "previous_qualification_grade <= 200",
    )
    op.create_check_constraint(
        "application_order_valid",
        "admission_records",
        "application_order IS NULL OR application_order BETWEEN 0 AND 9",
    )
    op.create_check_constraint(
        "daytime_evening_attendance_binary",
        "admission_records",
        "daytime_evening_attendance IS NULL OR daytime_evening_attendance IN (0, 1)",
    )

    op.add_column(
        "first_semester_records",
        sa.Column("without_evaluations", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "average_grade_maximum", "first_semester_records", "average_grade <= 20"
    )
    op.create_check_constraint(
        "without_evaluations_nonnegative",
        "first_semester_records",
        "without_evaluations IS NULL OR without_evaluations >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_first_semester_records_without_evaluations_nonnegative"),
        "first_semester_records",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_first_semester_records_average_grade_maximum"),
        "first_semester_records",
        type_="check",
    )
    op.drop_column("first_semester_records", "without_evaluations")

    op.drop_constraint(
        op.f("ck_admission_records_daytime_evening_attendance_binary"),
        "admission_records",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_admission_records_application_order_valid"),
        "admission_records",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_admission_records_previous_qualification_grade_maximum"),
        "admission_records",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_admission_records_admission_grade_maximum"),
        "admission_records",
        type_="check",
    )
    for column in (
        "gdp",
        "inflation_rate",
        "unemployment_rate",
        "father_occupation_code",
        "mother_occupation_code",
        "father_qualification_code",
        "mother_qualification_code",
        "previous_qualification_code",
        "daytime_evening_attendance",
        "course_code",
        "application_order",
        "application_mode_code",
    ):
        op.drop_column("admission_records", column)

    op.drop_constraint(
        op.f("ck_students_age_at_enrollment_nonnegative"), "students", type_="check"
    )
    for column in (
        "international_student",
        "scholarship_holder",
        "gender_code",
        "tuition_fees_up_to_date",
        "debtor",
        "educational_special_needs",
        "displaced",
    ):
        op.drop_constraint(
            op.f(f"ck_students_{column}_binary"), "students", type_="check"
        )
    op.drop_constraint(
        op.f("ck_students_marital_status_code_valid"), "students", type_="check"
    )
    for column in (
        "international_student",
        "age_at_enrollment",
        "scholarship_holder",
        "gender_code",
        "tuition_fees_up_to_date",
        "debtor",
        "educational_special_needs",
        "displaced",
        "nationality_code",
        "marital_status_code",
    ):
        op.drop_column("students", column)
