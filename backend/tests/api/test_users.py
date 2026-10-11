import json
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from app.core.security import create_access_token, verify_password
from app.models import User, UserAdministrationAudit, UserLoginIdentifier, UserRole
from sqlalchemy import select
from tests.api.test_casework import (
    confirm,
    create_intervention,
    follow_up_payload,
    setup,
)

INITIAL = "Temporary-password-123!"
CHANGED = "Owner-chosen-password-456!"
RESET = "Reset-password-789!"


def payload(username="new_user", role="ACADEMIC_ADMIN", **values):
    return {
        "username": username,
        "email": username + "@example.edu",
        "full_name": "New Account",
        "role": role,
        "initial_password": INITIAL,
        **values,
    }


def error(response, status, code):
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code


def sign_in(client, username, password):
    response = client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


@pytest.fixture()
def administrator(create_user, auth_headers):
    user = create_user(username="system_admin", role=UserRole.SYSTEM_ADMIN)
    return user, auth_headers(user.username)


@pytest.mark.parametrize("role", ["ACADEMIC_ADMIN", "ACADEMIC_ADVISOR", "SYSTEM_ADMIN"])
def test_system_admin_provisions_fixed_roles(client, administrator, db_session, role):
    actor, headers = administrator
    response = client.post(
        "/api/v1/users",
        headers=headers,
        json=payload(
            "NEW_USER", role, email=" New.User@EXAMPLE.EDU ", full_name=" New Account "
        ),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["username"] == "new_user"
    assert body["email"] == "new.user@example.edu"
    assert body["role"] == role and body["must_change_password"]
    assert body["full_name"] == "New Account"
    assert (
        "password_hash" not in response.text
        and INITIAL not in response.text
        and "token_version" not in response.text
    )
    user = db_session.get(User, UUID(body["id"]))
    assert user.password_hash.startswith("$argon2") and verify_password(
        INITIAL, user.password_hash
    )
    audit = db_session.scalar(
        select(UserAdministrationAudit).where(
            UserAdministrationAudit.target_id == user.id
        )
    )
    assert audit.action == "USER_CREATED" and audit.actor_id == actor.id
    assert db_session.scalar(
        select(UserLoginIdentifier).where(UserLoginIdentifier.identifier == "new_user")
    )


@pytest.mark.parametrize(
    "role", [UserRole.ACADEMIC_ADMIN, UserRole.ACADEMIC_ADVISOR, None]
)
def test_all_management_endpoints_enforce_rbac(client, create_user, auth_headers, role):
    headers = {}
    if role:
        create_user(username="unauthorized", role=role)
        headers = auth_headers("unauthorized")
    target = uuid4()
    operations = [
        ("get", "/users", None),
        ("get", f"/users/{target}", None),
        ("post", "/users", payload()),
        ("patch", f"/users/{target}", {"role": "SYSTEM_ADMIN"}),
        ("post", f"/users/{target}/activate", None),
        ("post", f"/users/{target}/deactivate", None),
        ("post", f"/users/{target}/reset-password", {"temporary_password": RESET}),
    ]
    for method, path, body in operations:
        kwargs = {"headers": headers}
        if body is not None:
            kwargs["json"] = body
        response = getattr(client, method)("/api/v1" + path, **kwargs)
        error(
            response,
            403 if role else 401,
            "INSUFFICIENT_PERMISSIONS" if role else "AUTHENTICATION_REQUIRED",
        )
    assert client.post("/api/v1/auth/register", json=payload()).status_code == 404


@pytest.mark.parametrize(
    "values",
    [
        {"username": "DUPLICATE"},
        {"email": "DUPLICATE@EXAMPLE.EDU"},
        {"username": "duplicate@example.edu", "email": "different@example.edu"},
        {"email": "ambiguous@example.edu"},
    ],
)
def test_identifier_namespace_conflicts(client, administrator, create_user, values):
    create_user(username="duplicate", role=UserRole.ACADEMIC_ADVISOR)
    create_user(username="ambiguous@example.edu", role=UserRole.ACADEMIC_ADVISOR)
    error(
        client.post("/api/v1/users", headers=administrator[1], json=payload(**values)),
        409,
        "USER_IDENTIFIER_CONFLICT",
    )


@pytest.mark.parametrize(
    "values",
    [
        {"username": "  "},
        {"full_name": " "},
        {"email": "invalid"},
        {"role": "CUSTOM_ROLE"},
        {"initial_password": "short"},
        {"is_active": False},
        {"must_change_password": False},
    ],
)
def test_provisioning_validates_fields(client, administrator, values):
    response = client.post(
        "/api/v1/users", headers=administrator[1], json=payload(**values)
    )
    error(response, 422, "VALIDATION_ERROR")
    assert "input" not in response.json()["error"].get("details", [{}])[0]


def test_initial_change_and_secure_reset(client, administrator, db_session):
    created = client.post(
        "/api/v1/users", headers=administrator[1], json=payload()
    ).json()
    user_id = created["id"]
    temporary_headers = sign_in(client, "new_user", INITIAL)
    assert client.get("/api/v1/auth/me", headers=temporary_headers).json()[
        "must_change_password"
    ]
    error(
        client.get("/api/v1/students", headers=temporary_headers),
        403,
        "PASSWORD_CHANGE_REQUIRED",
    )
    error(
        client.get("/api/v1/users/advisors", headers=temporary_headers),
        403,
        "PASSWORD_CHANGE_REQUIRED",
    )
    error(
        client.post(
            "/api/v1/auth/change-password",
            headers=temporary_headers,
            json={"current_password": "incorrect", "new_password": CHANGED},
        ),
        400,
        "CURRENT_PASSWORD_INCORRECT",
    )
    error(
        client.post(
            "/api/v1/auth/change-password",
            headers=temporary_headers,
            json={"current_password": INITIAL, "new_password": INITIAL},
        ),
        422,
        "PASSWORD_REUSE",
    )
    changed = client.post(
        "/api/v1/auth/change-password",
        headers=temporary_headers,
        json={"current_password": INITIAL, "new_password": CHANGED},
    )
    assert changed.status_code == 200 and not changed.json()["must_change_password"]
    headers = {"Authorization": "Bearer " + changed.json()["access_token"]}
    error(
        client.get("/api/v1/auth/me", headers=temporary_headers),
        401,
        "AUTHENTICATION_REQUIRED",
    )
    assert client.get("/api/v1/students", headers=headers).status_code == 200
    error(
        client.post(
            "/api/v1/auth/login", json={"username": "new_user", "password": INITIAL}
        ),
        401,
        "INVALID_CREDENTIALS",
    )
    reset = client.post(
        f"/api/v1/users/{user_id}/reset-password",
        headers=administrator[1],
        json={"temporary_password": RESET},
    )
    assert reset.status_code == 200 and reset.json()["must_change_password"]
    assert RESET not in reset.text
    error(
        client.get("/api/v1/students", headers=headers), 401, "AUTHENTICATION_REQUIRED"
    )
    error(
        client.post(
            "/api/v1/auth/login", json={"username": "new_user", "password": CHANGED}
        ),
        401,
        "INVALID_CREDENTIALS",
    )
    reset_headers = sign_in(client, "new_user", RESET)
    error(
        client.get("/api/v1/students", headers=reset_headers),
        403,
        "PASSWORD_CHANGE_REQUIRED",
    )
    audit = list(
        db_session.scalars(
            select(UserAdministrationAudit).where(
                UserAdministrationAudit.target_id == UUID(user_id)
            )
        )
    )
    assert {entry.action for entry in audit} == {
        "USER_CREATED",
        "PASSWORD_CHANGED",
        "PASSWORD_RESET",
    }
    serialized = json.dumps([entry.changed_fields for entry in audit])
    for secret in (INITIAL, CHANGED, RESET, "password_hash", "access_token"):
        assert secret not in serialized


def test_account_activation_role_and_identity_changes_invalidate_tokens(
    client, administrator, create_user, auth_headers
):
    target = create_user(username="academic", role=UserRole.ACADEMIC_ADMIN)
    headers = auth_headers(target.username)
    assert (
        client.post(
            "/api/v1/students",
            headers=headers,
            json={"student_number": "A2-1", "name": "Student"},
        ).status_code
        == 201
    )
    assert (
        client.patch(
            f"/api/v1/users/{target.id}",
            headers=administrator[1],
            json={"role": "ACADEMIC_ADVISOR"},
        ).status_code
        == 200
    )
    error(
        client.get("/api/v1/students", headers=headers), 401, "AUTHENTICATION_REQUIRED"
    )
    headers = auth_headers(target.username)
    error(
        client.post(
            "/api/v1/students",
            headers=headers,
            json={"student_number": "A2-2", "name": "Student"},
        ),
        403,
        "INSUFFICIENT_PERMISSIONS",
    )
    assert (
        client.patch(
            f"/api/v1/users/{target.id}",
            headers=administrator[1],
            json={
                "username": "renamed",
                "email": "renamed@example.edu",
                "full_name": "New Name",
            },
        ).status_code
        == 200
    )
    error(
        client.get("/api/v1/auth/me", headers=headers), 401, "AUTHENTICATION_REQUIRED"
    )
    headers = auth_headers("renamed")
    assert (
        client.post(
            f"/api/v1/users/{target.id}/deactivate", headers=administrator[1]
        ).status_code
        == 200
    )
    error(
        client.get("/api/v1/students", headers=headers), 401, "AUTHENTICATION_REQUIRED"
    )
    error(
        client.post(
            "/api/v1/auth/login",
            json={"username": "renamed", "password": "CorrectHorseBatteryStaple!"},
        ),
        401,
        "INVALID_CREDENTIALS",
    )
    assert (
        client.post(
            f"/api/v1/users/{target.id}/activate", headers=administrator[1]
        ).status_code
        == 200
    )
    assert (
        client.get("/api/v1/students", headers=auth_headers("renamed")).status_code
        == 200
    )
    error(
        client.get("/api/v1/students", headers=headers), 401, "AUTHENTICATION_REQUIRED"
    )


def test_last_admin_and_self_deactivation(client, administrator, create_user):
    actor, headers = administrator
    error(
        client.post(f"/api/v1/users/{actor.id}/deactivate", headers=headers),
        409,
        "SELF_DEACTIVATION_FORBIDDEN",
    )
    error(
        client.patch(
            f"/api/v1/users/{actor.id}",
            headers=headers,
            json={"role": "ACADEMIC_ADMIN"},
        ),
        409,
        "LAST_ACTIVE_SYSTEM_ADMIN",
    )
    create_user(username="inactive_system", role=UserRole.SYSTEM_ADMIN, is_active=False)
    error(
        client.patch(
            f"/api/v1/users/{actor.id}",
            headers=headers,
            json={"role": "ACADEMIC_ADMIN"},
        ),
        409,
        "LAST_ACTIVE_SYSTEM_ADMIN",
    )
    create_user(username="backup_system", role=UserRole.SYSTEM_ADMIN)
    assert (
        client.patch(
            f"/api/v1/users/{actor.id}",
            headers=headers,
            json={"role": "ACADEMIC_ADMIN"},
        ).status_code
        == 200
    )
    error(client.get("/api/v1/users", headers=headers), 401, "AUTHENTICATION_REQUIRED")


def test_list_filters_pagination_and_global_counts(client, administrator, create_user):
    create_user(username="advisor_one", role=UserRole.ACADEMIC_ADVISOR)
    create_user(username="advisor_two", role=UserRole.ACADEMIC_ADVISOR, is_active=False)
    create_user(username="academic", role=UserRole.ACADEMIC_ADMIN)
    response = client.get(
        "/api/v1/users",
        headers=administrator[1],
        params={
            "page_size": 1,
            "role": "ACADEMIC_ADVISOR",
            "is_active": "true",
            "search": "ONE",
        },
    )
    body = response.json()
    assert response.status_code == 200 and body["total"] == 1
    assert len(body["items"]) == 1 and body["items"][0]["username"] == "advisor_one"
    assert body["counts"] == {
        "total": 4,
        "active": 3,
        "academic_admins": 1,
        "advisors": 2,
    }
    assert (
        client.get(
            "/api/v1/users", headers=administrator[1], params={"search": "%"}
        ).json()["total"]
        == 0
    )


def test_advisor_directory_minimal_and_authorized(client, create_user, auth_headers):
    for role in UserRole:
        create_user(username=role.value.lower(), role=role)
    create_user(
        username="inactive_advisor", role=UserRole.ACADEMIC_ADVISOR, is_active=False
    )
    for role in UserRole:
        response = client.get(
            "/api/v1/users/advisors", headers=auth_headers(role.value.lower())
        )
        assert response.status_code == 200
        assert response.json()["total"] == 1
        assert set(response.json()["items"][0]) == {"id", "full_name"}
    error(client.get("/api/v1/users/advisors"), 401, "AUTHENTICATION_REQUIRED")


def test_assigned_advisor_cannot_be_orphaned(
    client, db_session, create_user, auth_headers, monkeypatch
):
    accounts, headers, student, warning = setup(
        client, db_session, create_user, auth_headers, monkeypatch
    )
    target = accounts["advisor"]
    for method, suffix, body in (
        ("post", "/deactivate", None),
        ("patch", "", {"role": "ACADEMIC_ADMIN"}),
    ):
        kwargs = {"headers": headers["system"]}
        if body:
            kwargs["json"] = body
        response = getattr(client, method)(
            f"/api/v1/users/{target.id}" + suffix, **kwargs
        )
        error(response, 409, "ADVISOR_HAS_ACTIVE_ASSIGNMENTS")
        assert response.json()["error"]["details"]["warnings"] == 1
    confirm(client, warning, headers)
    case = create_intervention(client, student, warning, accounts, headers)
    follow = client.post(
        f"/api/v1/interventions/{case['id']}/follow-ups",
        headers=headers["academic"],
        json=follow_up_payload(target),
    )
    assert follow.status_code == 201, follow.text
    assert (
        client.patch(
            f"/api/v1/warnings/{warning.id}/assignment",
            headers=headers["academic"],
            json={"assigned_to": None},
        ).status_code
        == 200
    )
    blocked = client.post(
        f"/api/v1/users/{target.id}/deactivate", headers=headers["system"]
    )
    error(blocked, 409, "ADVISOR_HAS_ACTIVE_ASSIGNMENTS")
    assert blocked.json()["error"]["details"] == {
        "warnings": 0,
        "interventions": 1,
        "follow_ups": 1,
    }
    assert target.is_active

    # Legacy inactive accounts may retain assignments. Profile edits must not
    # pretend to be a new deactivation or modify those existing assignments.
    target.is_active = False
    db_session.commit()
    edited = client.patch(
        f"/api/v1/users/{target.id}",
        headers=headers["system"],
        json={"full_name": "Updated legacy advisor profile"},
    )
    assert edited.status_code == 200, edited.text
    assert not target.is_active and warning.assigned_to is None
    error(
        client.patch(
            f"/api/v1/users/{target.id}",
            headers=headers["system"],
            json={"role": "ACADEMIC_ADMIN"},
        ),
        409,
        "ADVISOR_HAS_ACTIVE_ASSIGNMENTS",
    )


def test_expired_password_change_and_hidden_security_fields(client, administrator):
    token = create_access_token(
        str(administrator[0].id), expires_delta=timedelta(seconds=-10)
    )
    error(
        client.post(
            "/api/v1/auth/change-password",
            headers={"Authorization": "Bearer " + token},
            json={"current_password": INITIAL, "new_password": CHANGED},
        ),
        401,
        "AUTHENTICATION_REQUIRED",
    )
    error(
        client.patch(
            f"/api/v1/users/{administrator[0].id}",
            headers=administrator[1],
            json={"token_version": 0},
        ),
        422,
        "VALIDATION_ERROR",
    )
