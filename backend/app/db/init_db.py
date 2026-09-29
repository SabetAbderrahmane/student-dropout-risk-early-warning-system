import os

from email_validator import EmailNotValidError, validate_email
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository


def bootstrap_system_admin(db: Session) -> bool:
    username = os.getenv("BOOTSTRAP_ADMIN_USERNAME", "").strip()
    email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
    full_name = os.getenv("BOOTSTRAP_ADMIN_FULL_NAME", "").strip()

    provided = [username, email, password, full_name]
    if not any(provided):
        return False
    if not all(provided):
        raise RuntimeError("All BOOTSTRAP_ADMIN_* values are required when bootstrapping an account")
    if len(password) < 12:
        raise RuntimeError("BOOTSTRAP_ADMIN_PASSWORD must contain at least 12 characters")
    try:
        email = validate_email(email, check_deliverability=False).normalized
    except EmailNotValidError as exc:
        raise RuntimeError("BOOTSTRAP_ADMIN_EMAIL is invalid") from exc

    repository = UserRepository(db)
    if repository.get_by_username_or_email(username) or repository.get_by_username_or_email(email):
        return False

    repository.add(
        User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            role=UserRole.SYSTEM_ADMIN,
            is_active=True,
        )
    )
    db.commit()
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

