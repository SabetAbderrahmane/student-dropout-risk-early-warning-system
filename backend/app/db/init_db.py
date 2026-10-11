import os

from email_validator import EmailNotValidError, validate_email
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate


def bootstrap_system_admin(db: Session) -> bool:
    username = os.getenv("BOOTSTRAP_ADMIN_USERNAME", "").strip().lower()
    email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
    full_name = os.getenv("BOOTSTRAP_ADMIN_FULL_NAME", "").strip()

    provided = [username, email, password, full_name]
    if not any(provided):
        return False
    if not all(provided):
        raise RuntimeError(
            "All BOOTSTRAP_ADMIN_* values are required when bootstrapping an account"
        )
    if len(password) < 12:
        raise RuntimeError(
            "BOOTSTRAP_ADMIN_PASSWORD must contain at least 12 characters"
        )
    try:
        email = validate_email(email, check_deliverability=False).normalized
    except EmailNotValidError as exc:
        raise RuntimeError("BOOTSTRAP_ADMIN_EMAIL is invalid") from exc

    repository = UserRepository(db)
    repository.lock_administration()
    if repository.get_by_username_or_email(
        username
    ) or repository.get_by_username_or_email(email):
        return False

    try:
        payload = UserCreate(
            username=username,
            email=email,
            full_name=full_name,
            role=UserRole.SYSTEM_ADMIN,
            initial_password=password,
        )
    except ValidationError:
        raise RuntimeError(
            "Bootstrap account fields are invalid. Check username, email, full name and the 12-character minimum password."
        ) from None
    try:
        user = repository.add(
            User(
                username=payload.username,
                email=str(payload.email),
                password_hash=hash_password(password),
                full_name=payload.full_name,
                role=UserRole.SYSTEM_ADMIN,
                is_active=True,
                must_change_password=True,
            )
        )
        repository.claim_identifiers(user)
        repository.audit(
            user,
            user,
            "USER_CREATED",
            {
                "source": "bootstrap",
                "role": UserRole.SYSTEM_ADMIN,
                "must_change_password": True,
            },
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise RuntimeError(
            "The bootstrap username or email conflicts with an existing login identifier."
        ) from None
    return True


def main() -> None:
    with SessionLocal() as db:
        created = bootstrap_system_admin(db)
    if created:
        print("Bootstrap system administrator created.")
    else:
        print("No bootstrap administrator was created.")


if __name__ == "__main__":
    main()
