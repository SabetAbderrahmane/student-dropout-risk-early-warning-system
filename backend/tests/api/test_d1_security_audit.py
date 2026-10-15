"""D1 evidence only: characterization tests describe unresolved behavior.

A passing ``test_characterization_*`` reproduces current behavior, not a fix.
The suite's synthetic model fixture stays outside deployment artifact paths.
"""

import csv
import io
from datetime import timedelta

import jwt
import pytest
from app.core.config import Settings, get_settings
from app.core.security import create_access_token
from app.ml.outcomes.runtime import reset_outcome_runtimes
from app.models import UserRole
from tests.api.test_imports import csv_bytes, valid_row


@pytest.mark.parametrize(
    "kind", ["missing", "malformed", "expired", "revoked", "unsigned", "wrong-scheme"]
)
def test_authentication_boundary_matrix(client, create_user, kind):
    user = create_user(username="d1_boundary", role=UserRole.ACADEMIC_ADMIN)
    headers = {}
    if kind == "malformed":
        headers = {"Authorization": "Bearer malformed"}
    elif kind == "expired":
        headers = {
            "Authorization": "Bearer "
            + create_access_token(str(user.id), timedelta(seconds=-1))
        }
    elif kind == "revoked":
        headers = {
            "Authorization": "Bearer "
            + create_access_token(str(user.id), token_version=1)
        }
    elif kind == "unsigned":
        token = jwt.encode({"sub": str(user.id)}, key="", algorithm="none")
        headers = {"Authorization": "Bearer " + token}
    elif kind == "wrong-scheme":
        headers = {"Authorization": "Basic malformed"}
    response = client.get("/api/v1/students", headers=headers)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
    assert response.headers["www-authenticate"] == "Bearer"


def test_characterization_production_accepts_low_entropy_signing_key():
    settings = Settings(_env_file=None, app_env="production", jwt_secret_key="x" * 64)
    assert settings.app_env == "production"


def test_characterization_login_burst_and_unknown_identifier_hash_bypass(
    client, create_user, monkeypatch
):
    from app.services import auth_service

    create_user(username="d1_login", role=UserRole.ACADEMIC_ADMIN)
    actual = auth_service.verify_password
    calls = []

    def observed(password, hashed):
        calls.append(True)  # Record only work count, never credential material.
        return actual(password, hashed)

    monkeypatch.setattr(auth_service, "verify_password", observed)
    known = [
        client.post(
            "/api/v1/auth/login", json={"username": "d1_login", "password": "invalid"}
        )
        for _ in range(12)
    ]
    count = len(calls)
    unknown = client.post(
        "/api/v1/auth/login", json={"username": "d1_absent", "password": "invalid"}
    )
    assert len(calls) == count == 12
    assert all(response.status_code == 401 for response in [*known, unknown])
    assert all("retry-after" not in response.headers for response in known)
    assert known[0].json() == unknown.json()  # Message disclosure is mitigated.


def test_characterization_public_docs_and_unrestricted_host(client):
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/docs").status_code == 200
    assert (
        client.get(
            "/api/v1/health/live", headers={"Host": "untrusted.invalid"}
        ).status_code
        == 200
    )
    allowed = client.options(
        "/api/v1/students",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    rejected = client.options(
        "/api/v1/students",
        headers={
            "Origin": "https://untrusted.invalid",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "access-control-allow-origin" not in rejected.headers


def test_characterization_legacy_readiness_ignores_unavailable_stage_models(
    client, create_user, auth_headers, monkeypatch, tmp_path
):
    create_user(username="d1_readiness", role=UserRole.ACADEMIC_ADMIN)
    headers = auth_headers("d1_readiness")
    monkeypatch.setattr(
        get_settings(), "ml_outcome_root", str(tmp_path / "absent-stages")
    )
    reset_outcome_runtimes()
    try:
        response = client.post(
            "/api/v1/students",
            headers=headers,
            json={"student_number": "D1-READY", "name": "D1 readiness fixture"},
        )
        assert response.status_code == 201
        sid = response.json()["id"]
        stages = client.get(
            f"/api/v1/students/{sid}/prediction-readiness/stages", headers=headers
        )
        assert stages.status_code == 200
        assert all(
            stage["model_status"] == "UNAVAILABLE" for stage in stages.json()["stages"]
        )
        ready = client.get("/api/v1/health/ready")
        assert ready.status_code == 200
        assert ready.json()["status"] == "ready"
    finally:
        reset_outcome_runtimes()


def test_characterization_canonical_export_preserves_formula_source(
    client, create_user, auth_headers
):
    create_user(username="d1_export", role=UserRole.ACADEMIC_ADMIN)
    headers = auth_headers("d1_export")
    row = valid_row("D1-EXPORT")
    row["name"] = (
        "=1+1"  # Harmless formula; no external calls or spreadsheet execution.
    )
    staged = client.post(
        "/api/v1/imports/staged/csv",
        headers=headers,
        files={"file": ("source.csv", csv_bytes([row]), "text/csv")},
    )
    assert staged.status_code == 201
    response = client.get(
        f"/api/v1/imports/staged/{staged.json()['id']}/export", headers=headers
    )
    assert response.status_code == 200
    assert list(csv.DictReader(io.StringIO(response.text)))[0]["name"] == "=1+1"
    # This is an intentional lossless re-import contract; a spreadsheet display
    # copy or UI warning is a separate recommendation, not a silent data rewrite.
