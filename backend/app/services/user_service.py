"""Transactional account administration and assignment-preserving safeguards."""

from math import ceil
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.core.security import hash_password, verify_password
from app.models import (
    FollowUp,
    FollowUpStatus,
    Intervention,
    InterventionStatus,
    User,
    UserRole,
    Warning,
    WarningReviewState,
)
from app.repositories.user_repository import UserRepository
from app.schemas.user import AdvisorDirectoryPage, UserCreate, UserPage, UserUpdate


class UserService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = UserRepository(db)

    def get(self, user_id: UUID, *, lock: bool = False) -> User:
        user = (
            self.repository.lock_by_id(user_id)
            if lock
            else self.repository.get_by_id(user_id)
        )
        if user is None:
            raise ApplicationError(
                404, "USER_NOT_FOUND", "The requested account does not exist."
            )
        return user

    def _administrator(self, actor: User) -> User:
        expected_version = actor.token_version
        self.repository.lock_administration()
        actor = self.get(actor.id, lock=True)
        if actor.token_version != expected_version or not actor.is_active:
            raise ApplicationError(
                401, "AUTHENTICATION_REQUIRED", "Sign in again to continue."
            )
        if actor.must_change_password:
            raise ApplicationError(
                403,
                "PASSWORD_CHANGE_REQUIRED",
                "Change your temporary password before using the application.",
            )
        if actor.role != UserRole.SYSTEM_ADMIN:
            raise ApplicationError(
                403,
                "INSUFFICIENT_PERMISSIONS",
                "Only System Admins may manage accounts.",
            )
        return actor

    def _commit(self) -> None:
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise ApplicationError(
                409,
                "USER_IDENTIFIER_CONFLICT",
                "That username or email is already used as a login identifier.",
            ) from None

    def _identifiers(
        self, username: str, email: str, *, exclude: UUID | None = None
    ) -> None:
        if self.repository.identifier_conflict(
            {username.lower(), email.lower()}, exclude
        ):
            raise ApplicationError(
                409,
                "USER_IDENTIFIER_CONFLICT",
                "That username or email is already used as a login identifier.",
            )

    def list(self, **params) -> UserPage:
        items, total = self.repository.list(**params)
        return UserPage(
            items=items,
            total=total,
            total_pages=ceil(total / params["page_size"]),
            page=params["page"],
            page_size=params["page_size"],
            counts=self.repository.counts(),
        )

    def advisors(
        self, *, page: int, page_size: int, search: str | None
    ) -> AdvisorDirectoryPage:
        items, total = self.repository.list(
            page=page,
            page_size=page_size,
            search=search,
            role=UserRole.ACADEMIC_ADVISOR,
            is_active=True,
        )
        return AdvisorDirectoryPage(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=ceil(total / page_size),
        )

    def create(self, actor: User, payload: UserCreate) -> User:
        try:
            actor = self._administrator(actor)
            self._identifiers(payload.username, str(payload.email))
            target = self.repository.add(
                User(
                    username=payload.username,
                    email=str(payload.email),
                    full_name=payload.full_name,
                    role=payload.role,
                    password_hash=hash_password(
                        payload.initial_password.get_secret_value()
                    ),
                    is_active=True,
                    must_change_password=True,
                )
            )
            self.repository.claim_identifiers(target)
            self.repository.audit(
                actor,
                target,
                "USER_CREATED",
                {
                    field: getattr(target, field)
                    for field in (
                        "username",
                        "email",
                        "full_name",
                        "role",
                        "is_active",
                        "must_change_password",
                    )
                },
            )
            self._commit()
            self.db.refresh(target)
            return target
        except IntegrityError:
            self.db.rollback()
            raise ApplicationError(
                409,
                "USER_IDENTIFIER_CONFLICT",
                "That username or email is already used as a login identifier.",
            ) from None
        except Exception:
            self.db.rollback()
            raise

    def _active_assignments(self, target: User) -> dict[str, int]:
        conditions = (
            ("warnings", Warning, Warning.review_state != WarningReviewState.DISMISSED),
            (
                "interventions",
                Intervention,
                Intervention.status.not_in(
                    [InterventionStatus.COMPLETED, InterventionStatus.CANCELLED]
                ),
            ),
            ("follow_ups", FollowUp, FollowUp.status == FollowUpStatus.SCHEDULED),
        )
        return {
            name: self.db.scalar(
                select(func.count())
                .select_from(model)
                .where(model.assigned_to == target.id, condition)
            )
            or 0
            for name, model, condition in conditions
        }

    def _safeguards(
        self, actor: User, target: User, *, role: UserRole, active: bool
    ) -> None:
        if not active and target.id == actor.id:
            raise ApplicationError(
                409,
                "SELF_DEACTIVATION_FORBIDDEN",
                "You cannot deactivate your own account.",
            )
        if (
            target.role == UserRole.SYSTEM_ADMIN
            and target.is_active
            and (role != UserRole.SYSTEM_ADMIN or not active)
        ):
            if self.repository.active_admin_count() <= 1:
                raise ApplicationError(
                    409,
                    "LAST_ACTIVE_SYSTEM_ADMIN",
                    "The last active System Admin cannot be deactivated or demoted.",
                )
        if target.role == UserRole.ACADEMIC_ADVISOR and (
            role != target.role or (target.is_active and not active)
        ):
            assignments = self._active_assignments(target)
            if any(assignments.values()):
                raise ApplicationError(
                    409,
                    "ADVISOR_HAS_ACTIVE_ASSIGNMENTS",
                    "Transfer or complete active warning, intervention and follow-up assignments before changing this advisor's role or deactivating the account.",
                    assignments,
                )

    def update(self, actor: User, user_id: UUID, payload: UserUpdate) -> User:
        try:
            actor = self._administrator(actor)
            target = self.get(user_id, lock=True)
            values = payload.model_dump(exclude_unset=True)
            self._safeguards(
                actor,
                target,
                role=values.get("role", target.role),
                active=target.is_active,
            )
            self._identifiers(
                values.get("username", target.username),
                str(values.get("email", target.email)),
                exclude=target.id,
            )
            changes = {}
            for field, value in values.items():
                old = getattr(target, field)
                if old != value:
                    changes[field] = {"before": old, "after": value}
                    setattr(target, field, value)
            if "username" in changes or "email" in changes:
                self.repository.claim_identifiers(target)
            if {"role", "username", "email"} & changes.keys():
                target.token_version += 1
            if "role" in changes:
                self.repository.audit(
                    actor, target, "ROLE_CHANGED", {"role": changes.pop("role")}
                )
            if changes:
                self.repository.audit(actor, target, "USER_UPDATED", changes)
            self._commit()
            self.db.refresh(target)
            return target
        except IntegrityError:
            self.db.rollback()
            raise ApplicationError(
                409,
                "USER_IDENTIFIER_CONFLICT",
                "That username or email is already used as a login identifier.",
            ) from None
        except Exception:
            self.db.rollback()
            raise

    def set_active(self, actor: User, user_id: UUID, active: bool) -> User:
        try:
            actor = self._administrator(actor)
            target = self.get(user_id, lock=True)
            self._safeguards(actor, target, role=target.role, active=active)
            if target.is_active != active:
                old = target.is_active
                target.is_active = active
                target.token_version += 1
                self.repository.audit(
                    actor,
                    target,
                    "USER_ACTIVATED" if active else "USER_DEACTIVATED",
                    {"is_active": {"before": old, "after": active}},
                )
            self._commit()
            self.db.refresh(target)
            return target
        except Exception:
            self.db.rollback()
            raise

    def reset_password(
        self, actor: User, user_id: UUID, temporary_password: str
    ) -> User:
        try:
            actor = self._administrator(actor)
            target = self.get(user_id, lock=True)
            if verify_password(temporary_password, target.password_hash):
                raise ApplicationError(
                    422, "PASSWORD_REUSE", "Choose a different temporary password."
                )
            target.password_hash = hash_password(temporary_password)
            target.must_change_password = True
            target.token_version += 1
            self.repository.audit(
                actor, target, "PASSWORD_RESET", {"must_change_password": True}
            )
            self._commit()
            self.db.refresh(target)
            return target
        except Exception:
            self.db.rollback()
            raise
