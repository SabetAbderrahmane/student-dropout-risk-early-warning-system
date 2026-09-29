from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.permissions import require_roles
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.import_job import ImportErrorPage, ImportJobPage, ImportJobResponse
from app.services.import_service import ImportService

router = APIRouter(prefix="/imports", tags=["imports"])

import_read_access = require_roles(UserRole.SYSTEM_ADMIN, UserRole.ACADEMIC_ADMIN)
import_write_access = require_roles(UserRole.ACADEMIC_ADMIN)


@router.get("/template")
def download_template(_: User = Depends(import_read_access)) -> Response:
    return Response(
        content=ImportService.template(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="student-import-template.csv"'
        },
    )


@router.post("/csv", response_model=ImportJobResponse)
async def upload_csv(
    file: UploadFile = File(...),
    current_user: User = Depends(import_write_access),
    db: Session = Depends(get_db),
):
    return await ImportService(db).import_csv(file, current_user)


@router.get("", response_model=ImportJobPage)
def list_imports(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    _: User = Depends(import_read_access),
    db: Session = Depends(get_db),
) -> ImportJobPage:
    return ImportService(db).list_jobs(page=page, page_size=page_size)


@router.get("/{import_id}", response_model=ImportJobResponse)
def get_import(
    import_id: UUID,
    _: User = Depends(import_read_access),
    db: Session = Depends(get_db),
):
    return ImportService(db).get_job(import_id)


@router.get("/{import_id}/errors", response_model=ImportErrorPage)
def list_import_errors(
    import_id: UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    _: User = Depends(import_read_access),
    db: Session = Depends(get_db),
) -> ImportErrorPage:
    return ImportService(db).list_errors(import_id, page=page, page_size=page_size)
