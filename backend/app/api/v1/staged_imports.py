from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.permissions import require_roles
from app.db.session import get_db
from app.models.staged_import import StagedImportStatus
from app.models.user import User, UserRole
from app.schemas.staged_import import (
    CorrectionResponse,
    RowCorrection,
    StagedActionPage,
    StagedBatchPage,
    StagedBatchResponse,
    StagedRowPage,
    VersionRequest,
)
from app.services.staged_import_service import StagedImportService

router = APIRouter(prefix="/staged", tags=["staged imports"])
read_access = require_roles(UserRole.SYSTEM_ADMIN, UserRole.ACADEMIC_ADMIN)
write_access = require_roles(UserRole.ACADEMIC_ADMIN)


@router.post("/csv", response_model=StagedBatchResponse, status_code=201)
async def stage_csv(
    file: UploadFile = File(...),
    actor: User = Depends(write_access),
    db: Session = Depends(get_db),
):
    return await StagedImportService(db).stage(file, actor)


@router.get("", response_model=StagedBatchPage)
def list_batches(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    status: StagedImportStatus | None = None,
    _: User = Depends(read_access),
    db: Session = Depends(get_db),
):
    return StagedImportService(db).list_batches(
        page=page, page_size=page_size, status=status
    )


@router.get("/{batch_id}", response_model=StagedBatchResponse)
def get_batch(
    batch_id: UUID, _: User = Depends(read_access), db: Session = Depends(get_db)
):
    return StagedImportService(db).get_batch(batch_id)


@router.get("/{batch_id}/rows", response_model=StagedRowPage)
def list_rows(
    batch_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    included: bool | None = None,
    valid: bool | None = None,
    search: str | None = Query(None, max_length=200),
    _: User = Depends(read_access),
    db: Session = Depends(get_db),
):
    return StagedImportService(db).list_rows(
        batch_id,
        page=page,
        page_size=page_size,
        included=included,
        valid=valid,
        search=search,
    )


@router.patch("/{batch_id}/rows/{row_id}", response_model=CorrectionResponse)
def correct_row(
    batch_id: UUID,
    row_id: UUID,
    request: RowCorrection,
    actor: User = Depends(write_access),
    db: Session = Depends(get_db),
):
    return StagedImportService(db).correct(batch_id, row_id, request, actor)


@router.post("/{batch_id}/commit", response_model=StagedBatchResponse)
def commit_batch(
    batch_id: UUID,
    request: VersionRequest,
    actor: User = Depends(write_access),
    db: Session = Depends(get_db),
):
    return StagedImportService(db).commit(
        batch_id, request.expected_batch_version, actor
    )


@router.post("/{batch_id}/cancel", response_model=StagedBatchResponse)
def cancel_batch(
    batch_id: UUID,
    request: VersionRequest,
    actor: User = Depends(write_access),
    db: Session = Depends(get_db),
):
    return StagedImportService(db).cancel(
        batch_id, request.expected_batch_version, actor
    )


@router.get("/{batch_id}/actions", response_model=StagedActionPage)
def list_actions(
    batch_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    _: User = Depends(read_access),
    db: Session = Depends(get_db),
):
    return StagedImportService(db).actions(batch_id, page=page, page_size=page_size)


@router.get("/{batch_id}/export")
def export_batch(
    batch_id: UUID, _: User = Depends(read_access), db: Session = Depends(get_db)
):
    # Machine-readable canonical CSV, not a spreadsheet-oriented diagnostics export.
    return Response(
        content=StagedImportService(db).export(batch_id),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="staged-import-{batch_id}.csv"',
            "X-Content-Type-Options": "nosniff",
        },
    )
