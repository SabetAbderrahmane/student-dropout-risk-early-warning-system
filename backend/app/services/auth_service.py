from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import ApplicationError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.services.mutation_authorization import MutationAuthorization


@dataclass(frozen=True)
class AuthenticationResult:
    user: User
    access_token: str
    expires_in: int


class InvalidCredentialsError(ValueError):
    pass


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = UserRepository(db)

    def authenticate(self, identifier: str, password: str) -> AuthenticationResult:
        user = self.repository.get_by_username_or_email(identifier)
        if (
            user is None
            or not verify_password(password, user.password_hash)
            or not user.is_active
        ):
            raise InvalidCredentialsError("Invalid credentials")

        settings = get_settings()
        return AuthenticationResult(
            user=user,
            access_token=create_access_token(
                str(user.id), token_version=user.token_version
            ),
            expires_in=settings.access_token_expire_minutes * 60,
        )

    def change_password(
        self, current_user: User, current_password: str, new_password: str
    ) -> AuthenticationResult:
        try:
            user = MutationAuthorization(self.db, current_user).lock_users(
                tuple(UserRole), allow_password_change=True
            )
            if not verify_password(current_password, user.password_hash):
                raise ApplicationError(
                    400,
                    "CURRENT_PASSWORD_INCORRECT",
                    "The current password is incorrect.",
                )
            if verify_password(new_password, user.password_hash):
                raise ApplicationError(
                    422,
                    "PASSWORD_REUSE",
                    "Choose a new password different from your current password.",
                )
            required = user.must_change_password
            user.password_hash = hash_password(new_password)
            user.must_change_password = False
            user.token_version += 1
            self.repository.audit(
                user,
                user,
                "PASSWORD_CHANGED",
                {"must_change_password": {"before": required, "after": False}},
            )
            self.db.commit()
            self.db.refresh(user)
            return AuthenticationResult(
                user=user,
                access_token=create_access_token(
                    str(user.id), token_version=user.token_version
                ),
                expires_in=get_settings().access_token_expire_minutes * 60,
            )
        except Exception:
            self.db.rollback()
            raise
