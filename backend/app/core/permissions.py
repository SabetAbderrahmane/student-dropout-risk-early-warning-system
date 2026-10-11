from collections.abc import Callable
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import TokenValidationError, decode_access_token
from app.db.session import get_db
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository

bearer_scheme = HTTPBearer(auto_error=False)


def _authentication_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "code": "AUTHENTICATION_REQUIRED",
            "message": "Valid authentication is required.",
        },
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _authentication_error()

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = UUID(payload["sub"])
    except (TokenValidationError, ValueError, TypeError):
        raise _authentication_error() from None

    user = UserRepository(db).get_by_id(user_id)
    if user is None or payload.get("ver", 0) != user.token_version:
        raise _authentication_error()
    return user


def get_active_user_allow_password_change(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "USER_INACTIVE",
                "message": "This user account is inactive.",
            },
        )
    return current_user


def get_current_active_user(
    current_user: User = Depends(get_active_user_allow_password_change),
) -> User:
    if current_user.must_change_password:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "PASSWORD_CHANGE_REQUIRED",
                "message": "Change your temporary password before using the application.",
            },
        )
    return current_user


def require_roles(*allowed_roles: UserRole) -> Callable[..., User]:
    allowed = frozenset(allowed_roles)
    if not allowed:
        raise ValueError("At least one allowed role is required")

    def role_dependency(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "INSUFFICIENT_PERMISSIONS",
                    "message": "You do not have permission to perform this action.",
                },
            )
        return current_user

    return role_dependency


require_system_admin = require_roles(UserRole.SYSTEM_ADMIN)
require_academic_admin = require_roles(UserRole.ACADEMIC_ADMIN)
require_academic_advisor = require_roles(UserRole.ACADEMIC_ADVISOR)
