from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.admission import AdmissionRecord
from app.models.import_job import ImportJob, ImportValidationError
from app.models.semester_one import FirstSemesterRecord
from app.models.student import Student
from app.utils.csv_import import RowValidationIssue, ValidatedImportRow


class ImportRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add_job(self, job: ImportJob) -> ImportJob:
        self.db.add(job)
        self.db.flush()
        return job

    def get_job(self, import_id: UUID) -> ImportJob | None:
        return self.db.get(ImportJob, import_id)

    def list_jobs(self, *, page: int, page_size: int) -> tuple[list[ImportJob], int]:
        total = self.db.scalar(select(func.count(ImportJob.id))) or 0
        statement = (
            select(ImportJob)
            .order_by(ImportJob.created_at.desc(), ImportJob.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self.db.scalars(statement)), total

    def list_errors(
        self, import_id: UUID, *, page: int, page_size: int
    ) -> tuple[list[ImportValidationError], int]:
        condition = ImportValidationError.import_job_id == import_id
        total = (
            self.db.scalar(
                select(func.count(ImportValidationError.id)).where(condition)
            )
            or 0
        )
        statement = (
            select(ImportValidationError)
            .where(condition)
            .order_by(
                ImportValidationError.row_number,
                ImportValidationError.created_at,
                ImportValidationError.id,
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self.db.scalars(statement)), total

    def existing_student_numbers(self, student_numbers: set[str]) -> set[str]:
        if not student_numbers:
            return set()
        return set(
            self.db.scalars(
                select(Student.student_number).where(
                    Student.student_number.in_(student_numbers)
                )
            )
        )

    def add_error(self, import_job_id: UUID, issue: RowValidationIssue) -> None:
        self.db.add(
            ImportValidationError(
                import_job_id=import_job_id,
                row_number=issue.row_number,
                field_name=issue.field_name,
                error_code=issue.error_code,
                error_message=issue.error_message,
            )
        )

    def add_student_graph(self, row: ValidatedImportRow) -> None:
        student = Student(**row.values_by_table["students"])
        admission = AdmissionRecord(
            student=student, **row.values_by_table["admission_records"]
        )
        semester = FirstSemesterRecord(
            student=student, **row.values_by_table["first_semester_records"]
        )
        self.db.add_all((student, admission, semester))
        self.db.flush()
