from fastapi.testclient import TestClient


def test_health_reports_database_connectivity(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "connected",
        "app_name": "student-dropout-warning-system",
    }

