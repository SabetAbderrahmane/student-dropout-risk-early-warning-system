from datetime import datetime
from math import ceil
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _strip_required(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("Value must not be blank")
    return stripped


class StudentCreate(BaseModel):
    student_number: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    gender: str | None = Field(default=None, max_length=50)

    _normalize_required = field_validator("student_number", "name")(_strip_required)

    @field_validator("gender")
    @classmethod
    def normalize_gender(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class StudentUpdate(BaseModel):
    student_number: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    gender: str | None = Field(default=None, max_length=50)

    @field_validator("student_number", "name")
    @classmethod
    def normalize_required(cls, value: str | None) -> str | None:
        return None if value is None else _strip_required(value)

    @field_validator("gender")
    @classmethod
    def normalize_gender(cls, value: str | None) -> str | None:
        return None if value is None else value.strip() or None

    @model_validator(mode="after")
    def validate_patch(self) -> "StudentUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        for field in ("student_number", "name"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} may not be null")
        return self


class StudentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    student_number: str
    name: str
    gender: str | None
    created_at: datetime
    updated_at: datetime


class StudentPage(BaseModel):
    items: list[StudentResponse]
    page: int
    page_size: int
    total: int
    total_pages: int

    @classmethod
    def create(
        cls,
        *,
        items: list[StudentResponse],
        page: int,
        page_size: int,
        total: int,
    ) -> "StudentPage":
        return cls(
            items=items,
            page=page,
            page_size=page_size,
            total=total,
            total_pages=ceil(total / page_size) if total else 0,
        )


class AdmissionRecordUpsert(BaseModel):
    admission_method: str = Field(min_length=1, max_length=100)
    admission_grade: float = Field(ge=0)
    previous_qualification: str = Field(min_length=1, max_length=200)
    previous_qualification_grade: float = Field(ge=0)

    _normalize_text = field_validator("admission_method", "previous_qualification")(
        _strip_required
    )


class AdmissionRecordResponse(AdmissionRecordUpsert):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    student_id: UUID
    created_at: datetime
    updated_at: datetime


class FirstSemesterRecordUpsert(BaseModel):
    credited_units: int = Field(ge=0)
    enrolled_units: int = Field(ge=0)
    evaluations: int = Field(ge=0)
    approved_units: int = Field(ge=0)
    average_grade: float = Field(ge=0)


class FirstSemesterRecordResponse(FirstSemesterRecordUpsert):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    student_id: UUID
    created_at: datetime
    updated_at: datetime

