from uuid import UUID

from sqlalchemy import case, delete, func, or_, select, text
from sqlalchemy.orm import Session

from app.models.user import User, UserAdministrationAudit, UserLoginIdentifier, UserRole


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, user_id: UUID) -> User | None:
        return self.db.get(User, user_id)

    def lock_by_id(self, user_id: UUID) -> User | None:
        return self.db.scalar(
            select(User)
            .where(User.id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def lock_administration(self) -> None:
        # Serialize account mutations, including the last-active-admin invariant.
        # Namespace uniqueness is also enforced independently by database keys.
        if self.db.get_bind().dialect.name == "postgresql":
            self.db.execute(text("SET LOCAL lock_timeout = '5s'"))
            self.db.execute(text("SELECT pg_advisory_xact_lock(610110009)"))

    def get_by_username_or_email(self, identifier: str) -> User | None:
        normalized = identifier.strip().lower()
        statement = select(User).where(
            or_(
                func.lower(func.trim(User.username)) == normalized,
                func.lower(func.trim(User.email)) == normalized,
            )
        )
        # Refuse ambiguous legacy rows rather than authenticating an arbitrary one.
        users = list(self.db.scalars(statement.with_for_update()).all())
        return users[0] if len(users) == 1 else None

    def identifier_conflict(
        self, identifiers: set[str], exclude: UUID | None = None
    ) -> bool:
        user_query = select(User.id).where(
            or_(
                func.lower(func.trim(User.username)).in_(identifiers),
                func.lower(func.trim(User.email)).in_(identifiers),
            )
        )
        alias_query = select(UserLoginIdentifier.identifier).where(
            UserLoginIdentifier.identifier.in_(identifiers)
        )
        if exclude is not None:
            user_query = user_query.where(User.id != exclude)
            alias_query = alias_query.where(UserLoginIdentifier.user_id != exclude)
        return (
            self.db.scalar(user_query.limit(1)) is not None
            or self.db.scalar(alias_query.limit(1)) is not None
        )

    def claim_identifiers(self, user: User) -> None:
        self.db.execute(
            delete(UserLoginIdentifier).where(UserLoginIdentifier.user_id == user.id)
        )
        self.db.add_all(
            [
                UserLoginIdentifier(identifier=value, user_id=user.id)
                for value in {user.username.strip().lower(), user.email.strip().lower()}
            ]
        )
        self.db.flush()

    def audit(self, actor: User, target: User, action: str, changes: dict) -> None:
        self.db.add(
            UserAdministrationAudit(
                actor_id=actor.id,
                target_id=target.id,
                action=action,
                changed_fields=changes,
            )
        )

    def active_admin_count(self) -> int:
        return (
            self.db.scalar(
                select(func.count())
                .select_from(User)
                .where(User.role == UserRole.SYSTEM_ADMIN, User.is_active.is_(True))
            )
            or 0
        )

    def counts(self) -> dict[str, int]:
        row = self.db.execute(
            select(
                func.count(User.id),
                func.sum(case((User.is_active.is_(True), 1), else_=0)),
                func.sum(case((User.role == UserRole.ACADEMIC_ADMIN, 1), else_=0)),
                func.sum(case((User.role == UserRole.ACADEMIC_ADVISOR, 1), else_=0)),
            )
        ).one()
        return dict(
            zip(
                ("total", "active", "academic_admins", "advisors"),
                (int(value or 0) for value in row),
            )
        )

    def list(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None,
        role: UserRole | None,
        is_active: bool | None,
    ):
        query = select(User)
        if search and search.strip():
            term = search.strip().lower()
            query = query.where(
                or_(
                    *(
                        func.lower(column).contains(term, autoescape=True)
                        for column in (User.username, User.email, User.full_name)
                    )
                )
            )
        if role is not None:
            query = query.where(User.role == role)
        if is_active is not None:
            query = query.where(User.is_active == is_active)
        total = self.db.scalar(select(func.count()).select_from(query.subquery())) or 0
        items = list(
            self.db.scalars(
                query.order_by(User.created_at.desc(), User.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return items, total

    def add(self, user: User) -> User:
        self.db.add(user)
        self.db.flush()
        return user
