from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.permissions import require_roles, require_system_admin
from app.db.session import get_db
from app.models import User, UserRole
from app.schemas.user import (
    AdvisorDirectoryPage,
    PasswordResetRequest,
    UserCreate,
    UserPage,
    UserResponse,
    UserUpdate,
)
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["user administration"])
directory_access = require_roles(
    UserRole.SYSTEM_ADMIN, UserRole.ACADEMIC_ADMIN, UserRole.ACADEMIC_ADVISOR
)


@router.get("", response_model=UserPage)
def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    search: str | None = Query(default=None, max_length=200),
    role: UserRole | None = None,
    is_active: bool | None = None,
    _: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> UserPage:
    return UserService(db).list(
        page=page, page_size=page_size, search=search, role=role, is_active=is_active
    )


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    actor: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> User:
    return UserService(db).create(actor, payload)


@router.get("/advisors", response_model=AdvisorDirectoryPage)
def advisors(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    search: str | None = Query(default=None, max_length=200),
    _: User = Depends(directory_access),
    db: Session = Depends(get_db),
) -> AdvisorDirectoryPage:
    return UserService(db).advisors(page=page, page_size=page_size, search=search)


@router.get("/{user_id}", response_model=UserResponse)
def read_user(
    user_id: UUID,
    _: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> User:
    return UserService(db).get(user_id)


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: UUID,
    payload: UserUpdate,
    actor: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> User:
    return UserService(db).update(actor, user_id, payload)


@router.post("/{user_id}/activate", response_model=UserResponse)
def activate(
    user_id: UUID,
    actor: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> User:
    return UserService(db).set_active(actor, user_id, True)


@router.post("/{user_id}/deactivate", response_model=UserResponse)
def deactivate(
    user_id: UUID,
    actor: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> User:
    return UserService(db).set_active(actor, user_id, False)


@router.post("/{user_id}/reset-password", response_model=UserResponse)
def reset_password(
    user_id: UUID,
    payload: PasswordResetRequest,
    actor: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> User:
    return UserService(db).reset_password(
        actor, user_id, payload.temporary_password.get_secret_value()
    )
