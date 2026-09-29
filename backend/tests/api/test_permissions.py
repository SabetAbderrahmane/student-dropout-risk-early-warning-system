from collections.abc import Generator

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.permissions import require_roles
from app.db.session import get_db
from app.models import User, UserRole


def _permission_test_app(db_session: Session) -> FastAPI:
    application = FastAPI()

    @application.get("/system-admin-only")
    def system_admin_only(
        _: User = Depends(require_roles(UserRole.SYSTEM_ADMIN)),
    ) -> dict[str, bool]:
        return {"allowed": True}

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    application.dependency_overrides[get_db] = override_get_db
    return application


def test_role_enum_contains_exactly_three_architecture_roles() -> None:
    assert {role.value for role in UserRole} == {
        "SYSTEM_ADMIN",
        "ACADEMIC_ADMIN",
        "ACADEMIC_ADVISOR",
    }


def test_system_admin_role_is_allowed_through_http_dependency(
    db_session, create_user, auth_headers
) -> None:
    create_user(username="sysadmin", role=UserRole.SYSTEM_ADMIN)
    headers = auth_headers("sysadmin")

    with TestClient(_permission_test_app(db_session)) as protected_client:
        response = protected_client.get("/system-admin-only", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"allowed": True}


def test_academic_roles_are_denied_system_admin_permission_through_http(
    db_session, create_user, auth_headers
) -> None:
    with TestClient(_permission_test_app(db_session)) as protected_client:
        for role, username in (
            (UserRole.ACADEMIC_ADMIN, "academic_admin"),
            (UserRole.ACADEMIC_ADVISOR, "academic_advisor"),
        ):
            create_user(username=username, role=role)
            response = protected_client.get(
                "/system-admin-only",
                headers=auth_headers(username),
            )

            assert response.status_code == 403
            assert response.json()["detail"]["code"] == "INSUFFICIENT_PERMISSIONS"


def test_protected_role_route_rejects_unauthenticated_request(db_session) -> None:
    with TestClient(_permission_test_app(db_session)) as protected_client:
        response = protected_client.get("/system-admin-only")

    assert response.status_code == 401


def test_require_roles_rejects_empty_role_set() -> None:
    try:
        require_roles()
    except ValueError as exc:
        assert "At least one" in str(exc)
    else:
        raise AssertionError("require_roles accepted an empty role set")
