from datetime import datetime
from math import ceil
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.ml.feature_schema import validate_feature_value


def _strip_required(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("Value must not be blank")
    return stripped


def _validate_contract_value(value: int | float | None, info):
    return validate_feature_value(info.field_name, value)


class StudentCreate(BaseModel):
    student_number: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    gender: str | None = Field(default=None, max_length=50)
    marital_status_code: int | None = None
    nationality_code: int | None = None
    displaced: int | None = None
    educational_special_needs: int | None = None
    debtor: int | None = None
    tuition_fees_up_to_date: int | None = None
    gender_code: int | None = None
    scholarship_holder: int | None = None
    age_at_enrollment: int | None = None
    international_student: int | None = None

    _normalize_required = field_validator("student_number", "name")(_strip_required)
    _validate_prediction_fields = field_validator(
        "marital_status_code",
        "nationality_code",
        "displaced",
        "educational_special_needs",
        "debtor",
        "tuition_fees_up_to_date",
        "gender_code",
        "scholarship_holder",
        "age_at_enrollment",
        "international_student",
    )(_validate_contract_value)

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
    marital_status_code: int | None = None
    nationality_code: int | None = None
    displaced: int | None = None
    educational_special_needs: int | None = None
    debtor: int | None = None
    tuition_fees_up_to_date: int | None = None
    gender_code: int | None = None
    scholarship_holder: int | None = None
    age_at_enrollment: int | None = None
    international_student: int | None = None

    _validate_prediction_fields = field_validator(
        "marital_status_code",
        "nationality_code",
        "displaced",
        "educational_special_needs",
        "debtor",
        "tuition_fees_up_to_date",
        "gender_code",
        "scholarship_holder",
        "age_at_enrollment",
        "international_student",
    )(_validate_contract_value)

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
    marital_status_code: int | None
    nationality_code: int | None
    displaced: int | None
    educational_special_needs: int | None
    debtor: int | None
    tuition_fees_up_to_date: int | None
    gender_code: int | None
    scholarship_holder: int | None
    age_at_enrollment: int | None
    international_student: int | None
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
    application_mode_code: int | None = None
    application_order: int | None = None
    course_code: int | None = None
    daytime_evening_attendance: int | None = None
    previous_qualification_code: int | None = None
    mother_qualification_code: int | None = None
    father_qualification_code: int | None = None
    mother_occupation_code: int | None = None
    father_occupation_code: int | None = None
    unemployment_rate: float | None = None
    inflation_rate: float | None = None
    gdp: float | None = None

    _normalize_text = field_validator("admission_method", "previous_qualification")(
        _strip_required
    )
    _validate_prediction_fields = field_validator(
        "admission_grade",
        "previous_qualification_grade",
        "application_mode_code",
        "application_order",
        "course_code",
        "daytime_evening_attendance",
        "previous_qualification_code",
        "mother_qualification_code",
        "father_qualification_code",
        "mother_occupation_code",
        "father_occupation_code",
        "unemployment_rate",
        "inflation_rate",
        "gdp",
    )(_validate_contract_value)


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
    without_evaluations: int | None = None

    @field_validator(
        "credited_units",
        "enrolled_units",
        "evaluations",
        "approved_units",
        "average_grade",
        "without_evaluations",
    )
    @classmethod
    def validate_prediction_fields(cls, value: int | float | None, info):
        normalized_name = {
            "credited_units": "first_semester_credited_units",
            "enrolled_units": "first_semester_enrolled_units",
            "evaluations": "first_semester_evaluations",
            "approved_units": "first_semester_approved_units",
            "average_grade": "first_semester_average_grade",
            "without_evaluations": "first_semester_without_evaluations",
        }[info.field_name]
        return validate_feature_value(normalized_name, value)


class FirstSemesterRecordResponse(FirstSemesterRecordUpsert):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    student_id: UUID
    created_at: datetime
    updated_at: datetime
