import csv
from datetime import datetime
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    field_validator,
    model_validator,
)

from app.models.staged_import import StagedImportStatus
from app.schemas.import_job import ImportJobResponse
from app.utils.csv_import import CSV_HEADERS


class VersionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_batch_version: int = Field(ge=1)


class RowCorrection(VersionRequest):
    expected_row_version: int = Field(ge=1)
    values: dict[str, StrictStr] | None = None
    included: bool | None = None

    @field_validator("values")
    @classmethod
    def canonical_values(cls, values):
        if values is not None:
            if not set(values).issubset(CSV_HEADERS):
                raise ValueError("Only official CSV columns may be corrected.")
            if any(len(value) > csv.field_size_limit() for value in values.values()):
                raise ValueError("Corrected values exceed the CSV field size limit.")
        return values

    @model_validator(mode="after")
    def has_change(self):
        if not self.values and self.included is None:
            raise ValueError("Provide canonical values and/or included.")
        return self


class StagedIssue(BaseModel):
    row_number: int
    field_name: str | None
    error_code: str
    error_message: str


class StagedRowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    batch_id: UUID
    row_number: int
    version: int
    original_values: dict[str, str]
    edited_values: dict[str, str]
    included: bool
    is_valid: bool
    issues: list[StagedIssue]


class StagedBatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    uploaded_by: UUID
    filename: str
    status: StagedImportStatus
    version: int
    total_rows: int
    included_rows: int
    excluded_rows: int
    valid_rows: int
    invalid_rows: int
    valid_included_rows: int
    invalid_included_rows: int
    validation_issue_count: int
    included_issue_count: int
    last_commit_error: str | None
    import_job_id: UUID | None
    import_job: ImportJobResponse | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    cancelled_at: datetime | None


class StagedBatchPage(BaseModel):
    items: list[StagedBatchResponse]
    page: int
    page_size: int
    total: int
    total_pages: int


class StagedRowPage(BaseModel):
    items: list[StagedRowResponse]
    batch_version: int
    page: int
    page_size: int
    total: int
    total_pages: int


class CorrectionResponse(BaseModel):
    batch: StagedBatchResponse
    row: StagedRowResponse


class StagedActionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    batch_id: UUID
    row_id: UUID | None
    actor_id: UUID
    action: str
    batch_version: int
    changes: dict[str, object]
    created_at: datetime


class StagedActionPage(BaseModel):
    items: list[StagedActionResponse]
    page: int
    page_size: int
    total: int
    total_pages: int
