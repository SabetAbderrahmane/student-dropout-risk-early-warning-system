from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.repositories.user_repository import UserRepository


@dataclass(frozen=True)
class AuthenticationResult:
    user: User
    access_token: str
    expires_in: int


class InvalidCredentialsError(ValueError):
    pass


class AuthService:
    def __init__(self, db: Session) -> None:
        self.repository = UserRepository(db)

    def authenticate(self, identifier: str, password: str) -> AuthenticationResult:
        user = self.repository.get_by_username_or_email(identifier)
        if user is None or not verify_password(password, user.password_hash) or not user.is_active:
            raise InvalidCredentialsError("Invalid credentials")

        settings = get_settings()
        return AuthenticationResult(
            user=user,
            access_token=create_access_token(str(user.id)),
            expires_in=settings.access_token_expire_minutes * 60,
        )

