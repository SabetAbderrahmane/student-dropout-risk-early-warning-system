"""One transaction boundary for casework authorization, revisions and auditing.

Lock order: administration mutex 610110009, sorted users, warning, parent
intervention, sorted follow-ups. Identity reads locate locks only. The mutex is
also held by account administration and password changes until commit/rollback.
"""

from datetime import UTC, date, datetime
from enum import Enum
from functools import wraps
from inspect import signature
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

from app.core.exceptions import ApplicationError
from app.models import CaseworkActionAudit, FollowUp, Intervention, UserRole, Warning
from app.repositories.casework_repository import CaseworkRepository
from app.repositories.user_repository import UserRepository
from app.repositories.warning_repository import WarningRepository

RESOURCES = (Warning, Intervention, FollowUp)


def values(resource):
    # Domain columns only: never user credentials, JWTs or inferred actor history.
    def safe(value):
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, (UUID, datetime, date)):
            return str(value)
        return value

    return {
        column.key: safe(getattr(resource, column.key))
        for column in resource.__table__.columns
    }


def check_revision(resource, expected):
    if expected is not None and resource.revision != expected:
        raise ApplicationError(
            409,
            "STALE_RESOURCE_REVISION",
            "This record changed. Refresh before submitting again.",
            {
                "entity_id": str(resource.id),
                "expected_revision": expected,
                "current_revision": resource.revision,
                "retryable": False,
            },
        )


def retryable_error(exc):
    code = getattr(exc.orig, "sqlstate", None) or getattr(exc.orig, "pgcode", None)
    if code in {"55P03", "40P01", "40001"}:
        return ApplicationError(
            409,
            "CASEWORK_RETRYABLE_CONFLICT",
            "Another transaction is busy. Refresh and retry the entire action.",
            {"retryable": True},
        )
    return None


class Mutation:
    def __init__(self, service, action, actor, payload, params, roles):
        self.db = service.db
        self.action = action.upper()
        self.reason = getattr(payload, "reason", None)
        self.correlation = uuid4()
        self.before = {}
        self.root = None
        presented_id, presented_version = self.db.info.get(
            "presented_auth", (actor.id, actor.token_version)
        )
        users = UserRepository(self.db)
        users.lock_administration()
        warning_id = params.get("warning_id") or getattr(payload, "warning_id", None)
        parent_id = params.get("intervention_id")
        child_id = params.get("follow_up_id")
        # Identity reads occur after the mutex, before any authorization decision.
        child = (
            self.db.get(FollowUp, child_id, populate_existing=True)
            if child_id
            else None
        )
        if child:
            parent_id = child.intervention_id
        parent = (
            self.db.get(Intervention, parent_id, populate_existing=True)
            if parent_id
            else None
        )
        if parent:
            warning_id = parent.warning_id
        user_ids = {presented_id}
        for identifier in (
            getattr(payload, "assigned_to", None),
            parent.assigned_to if parent else None,
            child.assigned_to if child else None,
        ):
            if identifier:
                user_ids.add(identifier)
        locked_users = {
            identifier: users.lock_by_id(identifier)
            for identifier in sorted(user_ids, key=str)
        }
        actor = locked_users[presented_id]
        if (
            actor is None
            or not actor.is_active
            or actor.token_version != presented_version
        ):
            raise ApplicationError(
                401, "AUTHENTICATION_REQUIRED", "Sign in again to continue."
            )
        if actor.must_change_password:
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
        self.actor = actor
        if warning_id:
            self.root = WarningRepository(self.db).get(warning_id, lock=True)
        if parent_id:
            self.root = CaseworkRepository(self.db).intervention(parent_id, lock=True)
        if child_id:
            self.root = CaseworkRepository(self.db).follow_up(child_id, lock=True)
        if self.action == "TRANSFER_INTERVENTION" and parent:
            for item in self.db.scalars(
                select(FollowUp)
                .where(
                    FollowUp.intervention_id == parent_id,
                    FollowUp.status == "SCHEDULED",
                )
                .order_by(FollowUp.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            ):
                self.before[item] = values(item)
        for item in list(self.db.identity_map.values()):
            if isinstance(item, RESOURCES):
                self.before[item] = values(item)
        if self.root:
            check_revision(self.root, getattr(payload, "expected_revision", None))

    def commit(self):
        # Child writes also advance parent version; case creation advances warning.
        touched = set()
        if self.root:
            touched.add(self.root)
            if isinstance(self.root, FollowUp) and self.action != "RECOVER_FOLLOW_UP":
                touched.add(self.root.intervention)
        pending = [item for item in self.db.new if isinstance(item, RESOURCES)]
        self.db.flush()
        resources = set(self.before) | set(pending) | touched
        for item in sorted(resources, key=lambda x: (x.__tablename__, str(x.id))):
            before = self.before.get(item, {})
            after = values(item)
            if before == after and item not in touched:
                continue
            item.revision = (item.revision or 0) + 1
            item.updated_at = datetime.now(UTC)
            self.db.add(
                CaseworkActionAudit(
                    actor_id=self.actor.id,
                    action=self.action,
                    reason=self.reason,
                    warning_id=(
                        item.id
                        if isinstance(item, Warning)
                        else item.warning_id
                        if isinstance(item, Intervention)
                        else item.intervention.warning_id
                    ),
                    intervention_id=(
                        item.id
                        if isinstance(item, Intervention)
                        else item.intervention_id
                        if isinstance(item, FollowUp)
                        else None
                    ),
                    follow_up_id=item.id if isinstance(item, FollowUp) else None,
                    before_values=before,
                    after_values=values(item),
                    correlation_id=self.correlation,
                )
            )
        self.db.commit()


def guarded(*roles):
    """Rollback the entire write on any failure, including lock acquisition."""

    def decorate(method):
        @wraps(method)
        def wrapped(self, *args, **kwargs):
            params = signature(method).bind(self, *args, **kwargs).arguments
            actor_key = "reviewer" if "reviewer" in params else "actor"
            try:
                self._mutation = Mutation(
                    self,
                    method.__name__,
                    params[actor_key],
                    params["payload"],
                    params,
                    roles,
                )
                params[actor_key] = self._mutation.actor
                return method(**params)
            except DBAPIError as exc:
                self.db.rollback()
                conflict = retryable_error(exc)
                if conflict:
                    raise conflict from None
                raise
            except Exception:
                self.db.rollback()
                raise

        return wrapped

    return decorate


CASEWORK_ROLES = (UserRole.ACADEMIC_ADMIN, UserRole.ACADEMIC_ADVISOR)
