"""Authorization locks shared by account, academic and casework mutations.

The caller owns commit/rollback. Never manufacture authentication from a User
object: request authentication must already have captured immutable presented
claims in the session. Ordering is administration mutex, sorted users, domain.
"""

from contextlib import contextmanager
from functools import wraps
from inspect import signature
from uuid import UUID

from sqlalchemy.exc import DBAPIError

from app.core.exceptions import ApplicationError
from app.models.user import UserRole
from app.repositories.user_repository import UserRepository


class MutationAuthorization:
    def __init__(self, db, actor):
        self.db = db
        claims = db.info.get("presented_auth")
        if (
            not isinstance(claims, tuple)
            or len(claims) != 2
            or not isinstance(claims[0], UUID)
            or type(claims[1]) is not int
            or claims[1] < 0
            or actor is None
            or claims[0] != actor.id
        ):
            raise ApplicationError(
                401, "AUTHENTICATION_REQUIRED", "Sign in again to continue."
            )
        # Capture before populate_existing can refresh actor.token_version.
        self.subject, self.version = claims
        self.users = UserRepository(db)
        self.users.lock_administration()

    def lock_users(self, roles, related_ids=(), *, allow_password_change=False):
        identifiers = {self.subject, *related_ids} - {None}
        locked = {
            identifier: self.users.lock_by_id(identifier)
            for identifier in sorted(identifiers, key=str)
        }
        actor = locked[self.subject]
        if actor is None or not actor.is_active or actor.token_version != self.version:
            raise ApplicationError(
                401, "AUTHENTICATION_REQUIRED", "Sign in again to continue."
            )
        if actor.must_change_password and not allow_password_change:
            raise ApplicationError(
                403,
                "PASSWORD_CHANGE_REQUIRED",
                "Change your temporary password before using the application.",
            )
        if actor.role not in roles:
            raise ApplicationError(
                403,
                "INSUFFICIENT_PERMISSIONS",
                "You do not have permission to perform this action.",
            )
        return actor


def retryable_conflict(exc, *, code):
    state = getattr(exc.orig, "sqlstate", None) or getattr(exc.orig, "pgcode", None)
    if state in {"55P03", "40P01", "40001"}:
        return ApplicationError(
            409,
            code,
            "Another transaction is busy. Refresh and retry the entire action.",
            {"retryable": True},
        )
    return None


@contextmanager
def academic_write(db, actor):
    """Guard one committing transaction; reacquire after any internal commit."""
    try:
        yield MutationAuthorization(db, actor).lock_users((UserRole.ACADEMIC_ADMIN,))
    except DBAPIError as exc:
        db.rollback()
        conflict = retryable_conflict(exc, code="ACADEMIC_WRITE_RETRYABLE_CONFLICT")
        if conflict:
            raise conflict from None
        raise
    except Exception:
        db.rollback()
        raise


def academic_mutation(method):
    """Synchronous persistence only: async uploads parse before entering here."""
    binding = signature(method)

    @wraps(method)
    def wrapped(self, *args, **kwargs):
        params = binding.bind(self, *args, **kwargs).arguments
        with academic_write(self.db, params["actor"]) as actor:
            params["actor"] = actor
            return method(**params)

    return wrapped
