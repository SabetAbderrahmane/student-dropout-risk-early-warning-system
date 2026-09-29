from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.models.import_job import ImportJob, ImportStatus
from app.models.user import User
from app.repositories.import_repository import ImportRepository
from app.schemas.import_job import ImportErrorPage, ImportJobPage
from app.utils.csv_import import (
    MAX_UPLOAD_BYTES,
    CsvStructureError,
    RowValidationIssue,
    csv_template_bytes,
    parse_csv,
    validate_rows,
)


class ImportService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = ImportRepository(db)

    @staticmethod
    def template() -> bytes:
        return csv_template_bytes()

    async def import_csv(self, upload: UploadFile, uploaded_by: User) -> ImportJob:
        filename = Path(upload.filename or "").name
        if not filename.lower().endswith(".csv"):
            raise ApplicationError(
                400, "CSV_INVALID_FILE_TYPE", "Only .csv files are accepted."
            )
        if len(filename) > 255:
            raise ApplicationError(
                400,
                "CSV_INVALID_FILENAME",
                "The CSV filename may not exceed 255 characters.",
            )
        content = await upload.read(MAX_UPLOAD_BYTES + 1)
        if len(content) > MAX_UPLOAD_BYTES:
            raise ApplicationError(
                413,
                "CSV_FILE_TOO_LARGE",
                f"CSV files may not exceed {MAX_UPLOAD_BYTES} bytes.",
            )
        try:
            rows = parse_csv(content)
        except CsvStructureError as exc:
            raise ApplicationError(400, exc.code, exc.message, exc.details) from exc

        job = self.repository.add_job(
            ImportJob(
                uploaded_by=uploaded_by.id,
                filename=filename,
                total_rows=len(rows),
                valid_rows=0,
                invalid_rows=len(rows),
                status=ImportStatus.VALIDATING,
            )
        )
        numbers = {row.values["student_number"].strip() for row in rows}
        existing = self.repository.existing_student_numbers(numbers)
        valid_rows, issues = validate_rows(rows, existing)
        for issue in issues:
            self.repository.add_error(job.id, issue)

        invalid_row_numbers = {issue.row_number for issue in issues}
        imported_count = 0
        for row in valid_rows:
            try:
                with self.db.begin_nested():
                    self.repository.add_student_graph(row)
            except IntegrityError:
                conflict = RowValidationIssue(
                    row.row_number,
                    "student_number",
                    "STUDENT_NUMBER_ALREADY_EXISTS",
                    "A student with this student_number already exists.",
                )
                self.repository.add_error(job.id, conflict)
                invalid_row_numbers.add(row.row_number)
            else:
                imported_count += 1

        job.valid_rows = imported_count
        job.invalid_rows = len(invalid_row_numbers)
        job.status = ImportStatus.IMPORTED
        job.completed_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(job)
        return job

    def get_job(self, import_id: UUID) -> ImportJob:
        job = self.repository.get_job(import_id)
        if job is None:
            raise ApplicationError(
                404, "IMPORT_NOT_FOUND", "The requested import job does not exist."
            )
        return job

    def list_jobs(self, *, page: int, page_size: int) -> ImportJobPage:
        jobs, total = self.repository.list_jobs(page=page, page_size=page_size)
        return ImportJobPage.create(
            items=jobs, page=page, page_size=page_size, total=total
        )

    def list_errors(
        self, import_id: UUID, *, page: int, page_size: int
    ) -> ImportErrorPage:
        self.get_job(import_id)
        errors, total = self.repository.list_errors(
            import_id, page=page, page_size=page_size
        )
        return ImportErrorPage.create(
            items=errors, page=page, page_size=page_size, total=total
        )
