from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.permissions import require_roles
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.student import (
    AdmissionRecordResponse,
    AdmissionRecordUpsert,
    FirstSemesterRecordResponse,
    FirstSemesterRecordUpsert,
    StudentCreate,
    StudentPage,
    StudentResponse,
    StudentUpdate,
)
from app.services.student_service import StudentService

router = APIRouter(prefix="/students", tags=["students"])

student_read_access = require_roles(
    UserRole.SYSTEM_ADMIN,
    UserRole.ACADEMIC_ADMIN,
    UserRole.ACADEMIC_ADVISOR,
)
student_write_access = require_roles(UserRole.ACADEMIC_ADMIN)


@router.get("", response_model=StudentPage)
def list_students(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    search: str | None = Query(default=None, max_length=200),
    _: User = Depends(student_read_access),
    db: Session = Depends(get_db),
) -> StudentPage:
    return StudentService(db).list_students(
        page=page, page_size=page_size, search=search
    )


@router.post("", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
def create_student(
    payload: StudentCreate,
    actor: User = Depends(student_write_access),
    db: Session = Depends(get_db),
):
    return StudentService(db).create_student(payload, actor=actor)


@router.get("/{student_id}", response_model=StudentResponse)
def get_student(
    student_id: UUID,
    _: User = Depends(student_read_access),
    db: Session = Depends(get_db),
):
    return StudentService(db).get_student(student_id)


@router.patch("/{student_id}", response_model=StudentResponse)
def update_student(
    student_id: UUID,
    payload: StudentUpdate,
    actor: User = Depends(student_write_access),
    db: Session = Depends(get_db),
):
    return StudentService(db).update_student(student_id, payload, actor=actor)


@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_student(
    student_id: UUID,
    actor: User = Depends(student_write_access),
    db: Session = Depends(get_db),
) -> Response:
    StudentService(db).delete_student(student_id, actor=actor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{student_id}/admission", response_model=AdmissionRecordResponse)
def get_admission(
    student_id: UUID,
    _: User = Depends(student_read_access),
    db: Session = Depends(get_db),
):
    return StudentService(db).get_admission(student_id)


@router.put("/{student_id}/admission", response_model=AdmissionRecordResponse)
def upsert_admission(
    student_id: UUID,
    payload: AdmissionRecordUpsert,
    actor: User = Depends(student_write_access),
    db: Session = Depends(get_db),
):
    return StudentService(db).upsert_admission(student_id, payload, actor=actor)


@router.get("/{student_id}/semester-1", response_model=FirstSemesterRecordResponse)
def get_first_semester(
    student_id: UUID,
    _: User = Depends(student_read_access),
    db: Session = Depends(get_db),
):
    return StudentService(db).get_first_semester(student_id)


@router.put("/{student_id}/semester-1", response_model=FirstSemesterRecordResponse)
def upsert_first_semester(
    student_id: UUID,
    payload: FirstSemesterRecordUpsert,
    actor: User = Depends(student_write_access),
    db: Session = Depends(get_db),
):
    return StudentService(db).upsert_first_semester(student_id, payload, actor=actor)
