from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, user_id: UUID) -> User | None:
        return self.db.get(User, user_id)

    def get_by_username_or_email(self, identifier: str) -> User | None:
        normalized = identifier.strip().lower()
        statement = select(User).where(
            or_(
                func.lower(User.username) == normalized,
                func.lower(User.email) == normalized,
            )
        )
        return self.db.scalar(statement)

    def add(self, user: User) -> User:
        self.db.add(user)
        self.db.flush()
        return user

