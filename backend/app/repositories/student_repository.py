from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.admission import AdmissionRecord
from app.models.semester_one import FirstSemesterRecord
from app.models.student import Student


class StudentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, student_id: UUID) -> Student | None:
        return self.db.get(Student, student_id)

    def get_by_student_number(self, student_number: str) -> Student | None:
        return self.db.scalar(
            select(Student).where(Student.student_number == student_number)
        )

    def add(self, student: Student) -> Student:
        self.db.add(student)
        self.db.flush()
        return student

    def update(self, student: Student, values: dict[str, object]) -> Student:
        for field, value in values.items():
            setattr(student, field, value)
        self.db.flush()
        return student

    def delete(self, student: Student) -> None:
        self.db.delete(student)
        self.db.flush()

    def list_paginated(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None = None,
    ) -> tuple[list[Student], int]:
        filters = []
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(
                or_(
                    Student.student_number.ilike(pattern),
                    Student.name.ilike(pattern),
                )
            )

        count_statement = select(func.count(Student.id)).where(*filters)
        total = self.db.scalar(count_statement) or 0
        statement = (
            select(Student)
            .where(*filters)
            .order_by(Student.student_number, Student.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self.db.scalars(statement)), total

    def get_admission(self, student_id: UUID) -> AdmissionRecord | None:
        return self.db.scalar(
            select(AdmissionRecord).where(AdmissionRecord.student_id == student_id)
        )

    def upsert_admission(
        self,
        student_id: UUID,
        values: dict[str, object],
    ) -> AdmissionRecord:
        record = self.get_admission(student_id)
        if record is None:
            record = AdmissionRecord(student_id=student_id, **values)
            self.db.add(record)
        else:
            for field, value in values.items():
                setattr(record, field, value)
        self.db.flush()
        return record
    def get_first_semester(self, student_id: UUID) -> FirstSemesterRecord | None:
        return self.db.scalar(
            select(FirstSemesterRecord).where(FirstSemesterRecord.student_id == student_id)
        )

    def upsert_first_semester(
        self,
        student_id: UUID,
        values: dict[str, object],
    ) -> FirstSemesterRecord:
        record = self.get_first_semester(student_id)
        if record is None:
            record = FirstSemesterRecord(student_id=student_id, **values)
            self.db.add(record)
        else:
            for field, value in values.items():
                setattr(record, field, value)
        self.db.flush()
        return record
