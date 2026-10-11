from app.core.config import get_settings
from app.db.session import get_db
from app.main import app
from app.ml.runtime import reset_model_runtime
from app.models.prediction import ModelVersion
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import OperationalError


def test_health_reports_database_connectivity(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "connected",
        "app_name": "student-dropout-warning-system",
    }


def test_liveness_without_model(client, monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "ml_model_path", str(tmp_path / "absent"))
    reset_model_runtime()
    assert client.get("/api/v1/health/live").json() == {"status": "ok"}
    assert client.get("/api/v1/health").status_code == 200


def test_ready_with_model_and_database(client):
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "database": {"status": "connected", "code": None},
        "model": {"status": "ready", "code": None},
    }


def test_ready_without_model(client, monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "ml_model_path", str(tmp_path / "absent"))
    reset_model_runtime()
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json()["model"] == {
        "status": "unavailable",
        "code": "MODEL_ARTIFACT_UNAVAILABLE",
    }
    assert response.json()["database"]["status"] == "connected"


def test_ready_with_model_mismatch(client, monkeypatch, tmp_path):
    bad = tmp_path / "model.joblib"
    bad.write_bytes(b"bad")
    monkeypatch.setattr(get_settings(), "ml_model_path", str(bad))
    reset_model_runtime()
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json()["model"] == {
        "status": "mismatch",
        "code": "MODEL_CHECKSUM_MISMATCH",
    }
    assert str(tmp_path) not in response.text


def test_ready_with_database_unavailable(client):
    class UnavailableDatabase:
        def execute(self, _):
            raise OperationalError(
                "SELECT 1", {}, Exception("private database details")
            )

        def rollback(self):
            pass

    app.dependency_overrides[get_db] = lambda: UnavailableDatabase()
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json()["database"] == {
        "status": "unavailable",
        "code": "DATABASE_UNAVAILABLE",
    }
    assert response.json()["model"]["status"] == "ready"
    assert "private" not in response.text
    assert client.get("/api/v1/health").status_code == 503
    assert client.get("/api/v1/health/live").status_code == 200


def test_ready_detects_persisted_model_registry_conflict(client, db_session):
    assert client.get("/api/v1/health/ready").status_code == 200
    model = db_session.scalar(select(ModelVersion))
    model.model_name = "Conflicting model"
    db_session.commit()
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json()["model"] == {
        "status": "mismatch",
        "code": "MODEL_REGISTRY_MISMATCH",
    }
