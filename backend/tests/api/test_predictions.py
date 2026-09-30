from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ml.feature_schema import PREDICTION_FEATURES
from app.models import (
    AdmissionRecord,
    FirstSemesterRecord,
    PredictionResult,
    Student,
    UserRole,
)


def _feature_value(feature):
    if feature.allowed_values:
        return min(feature.allowed_values)
    if feature.name == "first_semester_average_grade":
        return Decimal("12.0")
    if "grade" in feature.name:
        return Decimal("120.0")
    return 1


def create_ready_student(db: Session, number: str = "S-READY") -> Student:
    student_values = {}
    admission_values = {}
    semester_values = {}
    targets = {
        "students": student_values,
        "admission_records": admission_values,
        "first_semester_records": semester_values,
    }
    for feature in PREDICTION_FEATURES:
        targets[feature.storage_table][feature.storage_column] = _feature_value(feature)
    student = Student(student_number=number, name=f"Student {number}", **student_values)
    db.add(student)
    db.flush()
    db.add(
        AdmissionRecord(
            student_id=student.id,
            admission_method="General",
            previous_qualification="Secondary",
            **admission_values,
        )
    )
    db.add(FirstSemesterRecord(student_id=student.id, **semester_values))
    db.commit()
    db.refresh(student)
    return student


def _users(create_user, auth_headers):
    create_user(username="academic", role=UserRole.ACADEMIC_ADMIN)
    create_user(username="system", role=UserRole.SYSTEM_ADMIN)
    create_user(username="advisor", role=UserRole.ACADEMIC_ADVISOR)
    return {role: auth_headers(role) for role in ("academic", "system", "advisor")}


def test_readiness_reports_complete_and_missing_features(
    client: TestClient, db_session: Session, create_user, auth_headers
) -> None:
    headers = _users(create_user, auth_headers)["advisor"]
    ready = create_ready_student(db_session)
    response = client.get(
        f"/api/v1/students/{ready.id}/prediction-readiness", headers=headers
    )
    assert response.status_code == 200
    assert response.json() == {
        "status": "READY",
        "required_feature_count": 30,
        "available_feature_count": 30,
        "missing_features": [],
    }

    ready.first_semester_record.without_evaluations = None
    db_session.commit()
    response = client.get(
        f"/api/v1/students/{ready.id}/prediction-readiness", headers=headers
    )
    assert response.json()["status"] == "NOT_READY"
    assert response.json()["missing_features"] == ["first_semester_without_evaluations"]


@pytest.mark.parametrize(
    ("record", "field", "expected"),
    [
        ("student", "debtor", "debtor"),
        ("admission_record", "course_code", "course_code"),
        (
            "first_semester_record",
            "without_evaluations",
            "first_semester_without_evaluations",
        ),
    ],
)
def test_readiness_identifies_missing_fields_across_source_tables(
    record: str,
    field: str,
    expected: str,
    client: TestClient,
    db_session: Session,
    create_user,
    auth_headers,
) -> None:
    create_user(username="advisor", role=UserRole.ACADEMIC_ADVISOR)
    student = create_ready_student(db_session)
    target = student if record == "student" else getattr(student, record)
    setattr(target, field, None)
    db_session.commit()
    response = client.get(
        f"/api/v1/students/{student.id}/prediction-readiness",
        headers=auth_headers("advisor"),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "NOT_READY"
    assert expected in response.json()["missing_features"]


def test_single_prediction_is_admin_only_append_only_and_explained(
    client: TestClient, db_session: Session, create_user, auth_headers
) -> None:
    headers = _users(create_user, auth_headers)
    student = create_ready_student(db_session)
    url = f"/api/v1/students/{student.id}/predictions"
    assert client.post(url, headers=headers["system"]).status_code == 403
    assert client.post(url, headers=headers["advisor"]).status_code == 403

    first = client.post(url, headers=headers["academic"])
    second = client.post(url, headers=headers["academic"])
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    assert 0 <= first.json()["probability"] <= 1
    assert first.json()["risk_level"] in {"LOW", "MEDIUM", "HIGH"}
    assert len(first.json()["feature_snapshot"]) == 30
    assert list(first.json()["feature_snapshot"]) == [
        feature.name for feature in PREDICTION_FEATURES
    ]
    assert len(first.json()["top_explanation_factors"]) == 5
    assert all(
        "contribution" in item for item in first.json()["top_explanation_factors"]
    )
    assert db_session.scalar(select(func.count(PredictionResult.id))) == 2


def test_not_ready_prediction_is_controlled_and_not_persisted(
    client: TestClient, db_session: Session, create_user, auth_headers
) -> None:
    create_user(username="academic", role=UserRole.ACADEMIC_ADMIN)
    headers = auth_headers("academic")
    student = create_ready_student(db_session)
    student.admission_record.gdp = None
    db_session.commit()
    response = client.post(
        f"/api/v1/students/{student.id}/predictions", headers=headers
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PREDICTION_NOT_READY"
    assert response.json()["error"]["details"]["missing_features"] == ["gdp"]
    assert db_session.scalar(select(func.count(PredictionResult.id))) == 0


def test_batch_skips_not_ready_and_repeated_runs_append(
    client: TestClient, db_session: Session, create_user, auth_headers
) -> None:
    create_user(username="academic", role=UserRole.ACADEMIC_ADMIN)
    headers = auth_headers("academic")
    create_ready_student(db_session, "S-1")
    incomplete = create_ready_student(db_session, "S-2")
    incomplete.marital_status_code = None
    db_session.commit()

    first = client.post("/api/v1/predictions/batch", headers=headers)
    second = client.post("/api/v1/predictions/batch", headers=headers)
    assert first.status_code == second.status_code == 200
    assert first.json()["assessed"] == 1
    assert first.json()["skipped_not_ready"] == 1
    assert first.json()["created_predictions"] == 1
    assert first.json()["created_warnings"] == 0
    assert db_session.scalar(select(func.count(PredictionResult.id))) == 2


def test_registry_filters_history_and_model_endpoints(
    client: TestClient, db_session: Session, create_user, auth_headers
) -> None:
    headers = _users(create_user, auth_headers)
    student = create_ready_student(db_session)
    created = client.post(
        f"/api/v1/students/{student.id}/predictions", headers=headers["academic"]
    ).json()

    registry = client.get(
        "/api/v1/predictions",
        params={
            "risk_level": created["risk_level"],
            "model_version": created["model_version"],
            "search": student.student_number,
            "student_id": str(student.id),
        },
        headers=headers["system"],
    )
    assert registry.status_code == 200
    assert registry.json()["total"] == 1
    history = client.get(
        f"/api/v1/students/{student.id}/predictions", headers=headers["advisor"]
    )
    assert history.status_code == 200
    assert history.json()["items"][0]["id"] == created["id"]

    current = client.get("/api/v1/models/current", headers=headers["advisor"])
    assert current.status_code == 200
    assert current.json()["name"] == "Logistic Regression"
    assert current.json()["version"] == "dropout-logistic-regression-v1"
    assert current.json()["dataset"]["dataset_id"] == 697
    assert current.json()["artifact_available"] is True

    performance = client.get(
        "/api/v1/models/current/performance", headers=headers["system"]
    )
    assert performance.status_code == 200
    assert performance.json()["evaluation_scope"] == "FINAL_TEST_SET"
    assert performance.json()["sample_size"] == 885
    assert performance.json()["confusion_matrix"] == {
        "tp": 230,
        "fp": 70,
        "tn": 531,
        "fn": 54,
    }
    assert len(performance.json()["global_feature_importance"]) == 30


def test_missing_prediction_returns_stable_error(
    client: TestClient, create_user, auth_headers
) -> None:
    user = create_user(username="advisor", role=UserRole.ACADEMIC_ADVISOR)
    response = client.get(
        f"/api/v1/predictions/{user.id}", headers=auth_headers("advisor")
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PREDICTION_NOT_FOUND"
