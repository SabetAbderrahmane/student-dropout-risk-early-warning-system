from datetime import datetime
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)

from app.models.user import UserRole


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime
    must_change_password: bool


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(
        min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.@+\-]*$"
    )
    email: EmailStr = Field(max_length=320)
    full_name: str = Field(min_length=1, max_length=200)
    role: UserRole
    initial_password: SecretStr = Field(min_length=12, max_length=1024)

    @field_validator("username", "email", "full_name", mode="before")
    @classmethod
    def normalize(cls, value: object, info):
        if isinstance(value, str):
            value = value.strip()
            if info.field_name != "full_name":
                value = value.lower()
        return value


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str | None = Field(
        default=None,
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.@+\-]*$",
    )
    email: EmailStr | None = Field(default=None, max_length=320)
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    role: UserRole | None = None

    @field_validator("username", "email", "full_name", mode="before")
    @classmethod
    def normalize(cls, value: object, info):
        return UserCreate.normalize(value, info)

    @model_validator(mode="after")
    def nonempty(self):
        if not self.model_fields_set or any(
            getattr(self, field) is None for field in self.model_fields_set
        ):
            raise ValueError("Provide at least one non-null permitted field")
        return self


class PasswordResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    temporary_password: SecretStr = Field(min_length=12, max_length=1024)


class UserCounts(BaseModel):
    total: int
    active: int
    academic_admins: int
    advisors: int


class UserPage(BaseModel):
    items: list[UserResponse]
    page: int
    page_size: int
    total: int
    total_pages: int
    counts: UserCounts


class AdvisorDirectoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    full_name: str


class AdvisorDirectoryPage(BaseModel):
    items: list[AdvisorDirectoryEntry]
    page: int
    page_size: int
    total: int
    total_pages: int
