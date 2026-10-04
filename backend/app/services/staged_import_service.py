import csv
import io
from dataclasses import asdict
from datetime import UTC, datetime
from math import ceil
from uuid import UUID, uuid4

from fastapi import UploadFile
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.models.import_job import ImportJob, ImportStatus
from app.models.staged_import import (
    StagedImportAction,
    StagedImportBatch,
    StagedImportRow,
    StagedImportStatus,
)
from app.models.user import User
from app.repositories.import_repository import ImportRepository
from app.schemas.staged_import import (
    CorrectionResponse,
    RowCorrection,
    StagedActionPage,
    StagedBatchPage,
    StagedBatchResponse,
    StagedRowPage,
    StagedRowResponse,
)
from app.services.import_service import ImportService
from app.utils.csv_import import CSV_HEADERS, CsvDataRow, validate_rows

TERMINAL = (StagedImportStatus.COMMITTED, StagedImportStatus.CANCELLED)


class StagedImportService:
    def __init__(self, db: Session):
        self.db = db
        self.imports = ImportRepository(db)

    def get_batch(self, batch_id: UUID, *, lock=False) -> StagedImportBatch:
        statement = (
            select(StagedImportBatch)
            .where(StagedImportBatch.id == batch_id)
            .execution_options(populate_existing=True)
        )
        if lock:
            statement = statement.with_for_update(read=lock == "read")
        batch = self.db.scalar(statement)
        if batch is None:
            raise ApplicationError(
                404, "STAGED_IMPORT_NOT_FOUND", "The staged batch does not exist."
            )
        return batch

    def _rows(self, batch_id: UUID):
        return list(
            self.db.scalars(
                select(StagedImportRow)
                .where(StagedImportRow.batch_id == batch_id)
                .order_by(StagedImportRow.row_number)
                .execution_options(populate_existing=True)
            )
        )

    def _reserve(self, batch_id: UUID, version: int, *, commit_retry=False):
        # PostgreSQL row lock serializes writers; CAS also protects dialects without FOR UPDATE.
        try:
            batch = self.get_batch(batch_id, lock=True)
            if commit_retry and batch.status == StagedImportStatus.COMMITTED:
                return batch
            if batch.status in TERMINAL:
                raise ApplicationError(
                    409,
                    "STAGED_IMPORT_IMMUTABLE",
                    "Committed and cancelled batches cannot be changed.",
                )
            if batch.version != version:
                raise ApplicationError(
                    409,
                    "STAGED_IMPORT_STALE",
                    "Reload the batch before retrying.",
                    {"batch_version": batch.version},
                )
            result = self.db.execute(
                update(StagedImportBatch)
                .where(
                    StagedImportBatch.id == batch_id,
                    StagedImportBatch.version == version,
                    StagedImportBatch.status.not_in(TERMINAL),
                )
                .values(version=version + 1, updated_at=datetime.now(UTC))
                .execution_options(synchronize_session=False)
            )
            if result.rowcount != 1:
                self.db.rollback()
                raise ApplicationError(
                    409,
                    "STAGED_IMPORT_STALE",
                    "Another request changed this batch. Reload before retrying.",
                )
            self.db.refresh(batch)
            return batch
        except OperationalError as exc:
            self.db.rollback()
            raise ApplicationError(
                409,
                "STAGED_IMPORT_BUSY",
                "Another transaction is modifying this batch. Reload and retry.",
            ) from exc

    def _audit(self, batch, actor, action, changes, row_id=None):
        self.db.add(
            StagedImportAction(
                batch_id=batch.id,
                actor_id=actor.id,
                action=action,
                row_id=row_id,
                batch_version=batch.version,
                changes=changes,
            )
        )

    def _revalidate(self, batch, rows, *, initial=False, edited_id=None):
        included = [
            CsvDataRow(row.row_number, row.edited_values)
            for row in rows
            if row.included
        ]
        numbers = {row.edited_values["student_number"].strip() for row in rows}
        existing = self.imports.existing_student_numbers(numbers)
        valid, issues = validate_rows(included, existing)
        # Excluded rows retain field/database issues, but do not participate in batch duplicates.
        for row in rows:
            if not row.included:
                _, excluded_issues = validate_rows(
                    [CsvDataRow(row.row_number, row.edited_values)], existing
                )
                issues.extend(excluded_issues)
        grouped = {}
        for issue in issues:
            grouped.setdefault(issue.row_number, []).append(asdict(issue))
        validation_changes = []
        for row in rows:
            new_issues = grouped.get(row.row_number, [])
            if row.issues != new_issues:
                validation_changes.append(
                    {"row_id": str(row.id), "before": row.issues, "after": new_issues}
                )
                if not initial and row.id != edited_id:
                    row.version += 1
            row.issues = new_issues
            row.is_valid = not new_issues
            row.student_number = row.edited_values["student_number"].strip()
            row.student_name = row.edited_values["name"].strip()
        batch.included_rows = sum(row.included for row in rows)
        batch.excluded_rows = len(rows) - batch.included_rows
        batch.valid_rows = sum(row.is_valid for row in rows)
        batch.invalid_rows = len(rows) - batch.valid_rows
        batch.valid_included_rows = len(valid)
        batch.invalid_included_rows = batch.included_rows - len(valid)
        batch.validation_issue_count = len(issues)
        batch.included_issue_count = sum(
            len(row.issues) for row in rows if row.included
        )
        batch.status = (
            StagedImportStatus.READY_TO_COMMIT
            if batch.included_rows and not batch.invalid_included_rows
            else StagedImportStatus.REVIEW_REQUIRED
        )
        return valid, validation_changes

    async def stage(self, upload: UploadFile, actor: User):
        filename, source = await ImportService.parse_upload(upload)
        batch = StagedImportBatch(
            id=uuid4(),
            uploaded_by=actor.id,
            filename=filename,
            total_rows=len(source),
            version=1,
        )
        rows = [
            StagedImportRow(
                id=uuid4(),
                batch_id=batch.id,
                row_number=row.row_number,
                version=1,
                original_values=dict(row.values),
                edited_values=dict(row.values),
                included=True,
                is_valid=False,
                issues=[],
            )
            for row in source
        ]
        self._revalidate(batch, rows, initial=True)
        self.db.add(batch)
        self.db.flush()
        self.db.add_all(rows)
        self._audit(batch, actor, "UPLOADED", {"total_rows": len(rows)})
        self.db.commit()
        return batch

    def list_batches(self, *, page, page_size, status=None):
        conditions = [StagedImportBatch.status == status] if status else []
        total = (
            self.db.scalar(select(func.count(StagedImportBatch.id)).where(*conditions))
            or 0
        )
        items = self.db.scalars(
            select(StagedImportBatch)
            .where(*conditions)
            .order_by(StagedImportBatch.created_at.desc(), StagedImportBatch.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return StagedBatchPage(
            items=[StagedBatchResponse.model_validate(batch) for batch in items],
            page=page,
            page_size=page_size,
            total=total,
            total_pages=ceil(total / page_size),
        )

    def list_rows(
        self, batch_id, *, page, page_size, included=None, valid=None, search=None
    ):
        batch = self.get_batch(batch_id, lock="read")
        conditions = [StagedImportRow.batch_id == batch_id]
        if included is not None:
            conditions.append(StagedImportRow.included == included)
        if valid is not None:
            conditions.append(StagedImportRow.is_valid == valid)
        if search:
            escaped = (
                search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            )
            conditions.append(
                StagedImportRow.student_number.ilike(f"%{escaped}%", escape="\\")
                | StagedImportRow.student_name.ilike(f"%{escaped}%", escape="\\")
            )
        total = (
            self.db.scalar(select(func.count(StagedImportRow.id)).where(*conditions))
            or 0
        )
        items = self.db.scalars(
            select(StagedImportRow)
            .where(*conditions)
            .order_by(StagedImportRow.row_number)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return StagedRowPage(
            items=[StagedRowResponse.model_validate(row) for row in items],
            batch_version=batch.version,
            page=page,
            page_size=page_size,
            total=total,
            total_pages=ceil(total / page_size),
        )

    def correct(
        self, batch_id: UUID, row_id: UUID, request: RowCorrection, actor: User
    ):
        batch = self._reserve(batch_id, request.expected_batch_version)
        rows = self._rows(batch_id)
        row = next((row for row in rows if row.id == row_id), None)
        if row is None:
            self.db.rollback()
            raise ApplicationError(
                404, "STAGED_ROW_NOT_FOUND", "The row does not belong to this batch."
            )
        if row.version != request.expected_row_version:
            self.db.rollback()
            raise ApplicationError(
                409,
                "STAGED_ROW_STALE",
                "Reload the row before retrying.",
                {"row_version": row.version},
            )
        changes = {}
        if request.values:
            changes["values"] = {
                key: {"before": row.edited_values[key], "after": value}
                for key, value in request.values.items()
                if row.edited_values[key] != value
            }
            row.edited_values = {**row.edited_values, **request.values}
        if request.included is not None:
            changes["included"] = {"before": row.included, "after": request.included}
            row.included = request.included
        row.version += 1
        _, validation_changes = self._revalidate(batch, rows, edited_id=row.id)
        batch.last_commit_error = None
        changes["validation_changes"] = validation_changes
        action = (
            "CORRECTED"
            if request.values
            else "RESTORED"
            if row.included
            else "EXCLUDED"
        )
        self._audit(batch, actor, action, changes, row.id)
        self.db.commit()
        return CorrectionResponse(
            batch=StagedBatchResponse.model_validate(batch),
            row=StagedRowResponse.model_validate(row),
        )

    def commit(self, batch_id: UUID, version: int, actor: User):
        batch = self._reserve(batch_id, version, commit_retry=True)
        if batch.status == StagedImportStatus.COMMITTED:
            return batch
        rows = self._rows(batch_id)
        valid, validation_changes = self._revalidate(batch, rows)
        if not batch.included_rows or batch.invalid_included_rows:
            batch.last_commit_error = (
                "Include at least one row and resolve all included validation issues."
            )
            self._audit(
                batch,
                actor,
                "COMMIT_REJECTED",
                {
                    "validation_changes": validation_changes,
                    "reason": batch.last_commit_error,
                },
            )
            self.db.commit()
            raise ApplicationError(
                409,
                "STAGED_IMPORT_NOT_READY",
                batch.last_commit_error,
                StagedBatchResponse.model_validate(batch).model_dump(mode="json"),
            )
        try:
            # One savepoint around the entire graph set, never one per row.
            with self.db.begin_nested():
                job = self.imports.add_job(
                    ImportJob(
                        uploaded_by=batch.uploaded_by,
                        filename=batch.filename,
                        total_rows=len(valid),
                        valid_rows=len(valid),
                        invalid_rows=0,
                        status=ImportStatus.IMPORTED,
                        completed_at=datetime.now(UTC),
                    )
                )
                for row in valid:
                    self.imports.add_student_graph(row)
        except IntegrityError as exc:
            _, race_changes = self._revalidate(batch, rows)
            batch.last_commit_error = "Commit rolled back; no students were imported. Review conflicts and retry."
            self._audit(
                batch,
                actor,
                "COMMIT_REJECTED",
                {
                    "validation_changes": validation_changes + race_changes,
                    "reason": batch.last_commit_error,
                },
            )
            self.db.commit()
            raise ApplicationError(
                409,
                "STAGED_IMPORT_COMMIT_CONFLICT",
                batch.last_commit_error,
                StagedBatchResponse.model_validate(batch).model_dump(mode="json"),
            ) from exc
        batch.import_job = job
        batch.status = StagedImportStatus.COMMITTED
        batch.completed_at = job.completed_at
        batch.last_commit_error = None
        self._audit(
            batch,
            actor,
            "COMMITTED",
            {
                "import_job_id": str(job.id),
                "imported_rows": len(valid),
                "validation_changes": validation_changes,
            },
        )
        self.db.commit()
        self.db.refresh(job)
        self.db.refresh(batch)
        return batch

    def cancel(self, batch_id, version, actor):
        batch = self._reserve(batch_id, version)
        batch.status = StagedImportStatus.CANCELLED
        batch.cancelled_at = datetime.now(UTC)
        self._audit(batch, actor, "CANCELLED", {"pending_operation_discarded": True})
        self.db.commit()
        return batch

    def actions(self, batch_id, *, page, page_size):
        self.get_batch(batch_id)
        condition = StagedImportAction.batch_id == batch_id
        total = (
            self.db.scalar(select(func.count(StagedImportAction.id)).where(condition))
            or 0
        )
        items = list(
            self.db.scalars(
                select(StagedImportAction)
                .where(condition)
                .order_by(StagedImportAction.batch_version, StagedImportAction.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return StagedActionPage(
            items=items,
            page=page,
            page_size=page_size,
            total=total,
            total_pages=ceil(total / page_size),
        )

    def export(self, batch_id):
        self.get_batch(batch_id, lock="read")
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=CSV_HEADERS, lineterminator="\r\n")
        writer.writeheader()
        for row in self._rows(batch_id):
            if row.included:
                writer.writerow(row.edited_values)
        return stream.getvalue().encode("utf-8")
