from datetime import datetime
from math import ceil
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.import_job import (
    ImportJob,
    ImportStatus,
    ImportValidationError,
)


class ImportJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    uploaded_by: UUID
    filename: str
    total_rows: int
    valid_rows: int
    invalid_rows: int
    status: ImportStatus
    created_at: datetime
    completed_at: datetime | None


class ImportJobPage(BaseModel):
    items: list[ImportJobResponse]
    page: int
    page_size: int
    total: int
    total_pages: int

    @classmethod
    def create(
        cls,
        *,
        items: list[ImportJob],
        page: int,
        page_size: int,
        total: int,
    ) -> "ImportJobPage":
        return cls(
            items=[ImportJobResponse.model_validate(item) for item in items],
            page=page,
            page_size=page_size,
            total=total,
            total_pages=ceil(total / page_size) if total else 0,
        )


class ImportErrorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    import_job_id: UUID
    row_number: int
    field_name: str | None
    error_code: str
    error_message: str
    created_at: datetime


class ImportErrorPage(BaseModel):
    items: list[ImportErrorResponse]
    page: int
    page_size: int
    total: int
    total_pages: int

    @classmethod
    def create(
        cls,
        *,
        items: list[ImportValidationError],
        page: int,
        page_size: int,
        total: int,
    ) -> "ImportErrorPage":
        return cls(
            items=[ImportErrorResponse.model_validate(item) for item in items],
            page=page,
            page_size=page_size,
            total=total,
            total_pages=ceil(total / page_size) if total else 0,
        )
