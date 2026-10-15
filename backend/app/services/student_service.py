from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.models.admission import AdmissionRecord
from app.models.semester_one import FirstSemesterRecord
from app.models.student import Student
from app.models.user import User
from app.repositories.student_repository import StudentRepository
from app.schemas.student import (
    AdmissionRecordUpsert,
    FirstSemesterRecordUpsert,
    StudentCreate,
    StudentPage,
    StudentResponse,
    StudentUpdate,
)
from app.services.mutation_authorization import academic_mutation


class StudentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = StudentRepository(db)

    def list_students(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None,
    ) -> StudentPage:
        students, total = self.repository.list_paginated(
            page=page,
            page_size=page_size,
            search=search,
        )
        return StudentPage.create(
            items=[StudentResponse.model_validate(student) for student in students],
            page=page,
            page_size=page_size,
            total=total,
        )

    def get_student(self, student_id: UUID) -> Student:
        student = self.repository.get_by_id(student_id)
        if student is None:
            raise ApplicationError(
                404, "STUDENT_NOT_FOUND", "The requested student does not exist."
            )
        return student

    @academic_mutation
    def create_student(self, payload: StudentCreate, *, actor: User) -> Student:
        if self.repository.get_by_student_number(payload.student_number):
            self._raise_duplicate_student_number()

        student = Student(**payload.model_dump())
        try:
            self.repository.add(student)
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            self._raise_duplicate_student_number()
        self.db.refresh(student)
        return student

    @academic_mutation
    def update_student(
        self, student_id: UUID, payload: StudentUpdate, *, actor: User
    ) -> Student:
        student = self.get_student(student_id)
        values = payload.model_dump(exclude_unset=True)
        new_student_number = values.get("student_number")
        if (
            isinstance(new_student_number, str)
            and new_student_number != student.student_number
        ):
            existing = self.repository.get_by_student_number(new_student_number)
            if existing is not None and existing.id != student.id:
                self._raise_duplicate_student_number()

        try:
            self.repository.update(student, values)
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            self._raise_duplicate_student_number()
        self.db.refresh(student)
        return student

    @academic_mutation
    def delete_student(self, student_id: UUID, *, actor: User) -> None:
        student = self.get_student(student_id)
        self.repository.delete(student)
        self.db.commit()

    def get_admission(self, student_id: UUID) -> AdmissionRecord:
        self.get_student(student_id)
        record = self.repository.get_admission(student_id)
        if record is None:
            raise ApplicationError(
                404,
                "ADMISSION_RECORD_NOT_FOUND",
                "The requested admission record does not exist.",
            )
        return record

    @academic_mutation
    def upsert_admission(
        self,
        student_id: UUID,
        payload: AdmissionRecordUpsert,
        *,
        actor: User,
    ) -> AdmissionRecord:
        self.get_student(student_id)
        try:
            record = self.repository.upsert_admission(student_id, payload.model_dump())
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise ApplicationError(
                409,
                "ADMISSION_RECORD_CONFLICT",
                "The admission record could not be saved because of a data conflict.",
            ) from None
        self.db.refresh(record)
        return record

    def get_first_semester(self, student_id: UUID) -> FirstSemesterRecord:
        self.get_student(student_id)
        record = self.repository.get_first_semester(student_id)
        if record is None:
            raise ApplicationError(
                404,
                "SEMESTER_RECORD_NOT_FOUND",
                "The requested first-semester record does not exist.",
            )
        return record

    @academic_mutation
    def upsert_first_semester(
        self,
        student_id: UUID,
        payload: FirstSemesterRecordUpsert,
        *,
        actor: User,
    ) -> FirstSemesterRecord:
        self.get_student(student_id)
        try:
            record = self.repository.upsert_first_semester(
                student_id, payload.model_dump()
            )
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise ApplicationError(
                409,
                "SEMESTER_RECORD_CONFLICT",
                "The first-semester record could not be saved because of a data conflict.",
            ) from None
        self.db.refresh(record)
        return record

    @staticmethod
    def _raise_duplicate_student_number() -> None:
        raise ApplicationError(
            409,
            "STUDENT_NUMBER_ALREADY_EXISTS",
            "A student with this student number already exists.",
        )
