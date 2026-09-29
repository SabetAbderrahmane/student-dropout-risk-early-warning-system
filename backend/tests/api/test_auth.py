from fastapi.testclient import TestClient

from app.models import UserRole


def test_login_succeeds_with_username(client: TestClient, create_user) -> None:
    create_user(username="admin", role=UserRole.SYSTEM_ADMIN)

    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "CorrectHorseBatteryStaple!"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["access_token"]
    assert payload["expires_in"] == 1800


def test_login_succeeds_with_email_case_insensitively(client: TestClient, create_user) -> None:
    create_user(username="advisor", role=UserRole.ACADEMIC_ADVISOR)

    response = client.post(
        "/api/v1/auth/login",
        json={
            "username": "ADVISOR@EXAMPLE.EDU",
            "password": "CorrectHorseBatteryStaple!",
        },
    )

    assert response.status_code == 200


def test_login_rejects_incorrect_password(client: TestClient, create_user) -> None:
    create_user(username="admin", role=UserRole.SYSTEM_ADMIN)

    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "wrong"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_login_does_not_reveal_inactive_account(client: TestClient, create_user) -> None:
    create_user(username="inactive", role=UserRole.ACADEMIC_ADMIN, is_active=False)

    response = client.post(
        "/api/v1/auth/login",
        json={"username": "inactive", "password": "CorrectHorseBatteryStaple!"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_me_returns_authenticated_user(client: TestClient, create_user, auth_headers) -> None:
    user = create_user(username="advisor", role=UserRole.ACADEMIC_ADVISOR)

    response = client.get("/api/v1/auth/me", headers=auth_headers("advisor"))

    assert response.status_code == 200
    assert response.json() == {
        "id": str(user.id),
        "username": "advisor",
        "email": "advisor@example.edu",
        "full_name": "Advisor User",
        "role": "ACADEMIC_ADVISOR",
        "is_active": True,
        "created_at": user.created_at.isoformat().replace("+00:00", "Z"),
        "updated_at": user.updated_at.isoformat().replace("+00:00", "Z"),
    }


def test_me_rejects_missing_token(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_me_rejects_invalid_token(client: TestClient) -> None:
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not-a-valid-token"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_login_validation_uses_standard_error_shape(client: TestClient) -> None:
    response = client.post("/api/v1/auth/login", json={"username": "", "password": ""})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"

