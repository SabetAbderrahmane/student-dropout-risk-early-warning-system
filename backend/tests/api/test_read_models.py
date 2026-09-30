from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import event

from app.models import (
    FollowUp, FollowUpMethod, FollowUpStatus, ImportJob, ImportStatus,
    Intervention, InterventionStatus, InterventionType, ModelVersion,
    PredictionResult, RiskLevel, Student, UserRole, Warning, WarningPriority,
    WarningReview, WarningReviewState, ReviewDecision,
)
from tests.api.test_predictions import create_ready_student


def _data(db, create_user):
    admin = create_user(username="readeradmin", role=UserRole.ACADEMIC_ADMIN)
    advisor = create_user(username="readeradvisor", role=UserRole.ACADEMIC_ADVISOR)
    create_user(username="readersystem", role=UserRole.SYSTEM_ADMIN)
    ready = create_ready_student(db, "READ-1")
    empty = Student(student_number="READ-2", name="Incomplete Student")
    db.add(empty)
    model = ModelVersion(model_name="Fixture model", model_version="fixture-v1",
        feature_schema_version="fixture-schema", trained_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        low_threshold=0.3, high_threshold=0.7, metrics={}, metadata_json={},
        artifact_path="fixture", is_active=True)
    db.add(model)
    db.flush()
    t = datetime.now(timezone.utc).replace(microsecond=0)
    old = PredictionResult(student_id=ready.id, model_version_id=model.id,
        probability=0.9, risk_level=RiskLevel.HIGH, feature_snapshot={}, explanation=[],
        predicted_at=t - timedelta(days=2))
    current = PredictionResult(student_id=ready.id, model_version_id=model.id,
        probability=0.6, risk_level=RiskLevel.MEDIUM, feature_snapshot={},
        explanation=[{"feature": "debtor", "contribution": 0.3}], predicted_at=t)
    db.add_all([old, current])
    db.flush()
    old_warning = Warning(prediction_id=old.id, student_id=ready.id,
        risk_level=RiskLevel.HIGH, priority=WarningPriority.P1_URGENT,
        review_state=WarningReviewState.CONFIRMED, assigned_to=advisor.id,
        created_at=t - timedelta(days=2))
    warning = Warning(prediction_id=current.id, student_id=ready.id,
        risk_level=RiskLevel.MEDIUM, priority=WarningPriority.P2_ELEVATED,
        review_state=WarningReviewState.CONFIRMED, assigned_to=advisor.id,
        created_at=t)
    db.add_all([old_warning, warning])
    db.flush()
    review = WarningReview(warning_id=warning.id, reviewer_id=advisor.id,
        decision=ReviewDecision.CONFIRMED, note="Reviewed", reviewed_at=t + timedelta(minutes=1))
    intervention = Intervention(student_id=ready.id, warning_id=warning.id,
        type=InterventionType.ACADEMIC_ADVISING, title="Advising", description="Plan",
        priority=WarningPriority.P2_ELEVATED, status=InterventionStatus.IN_PROGRESS,
        assigned_to=advisor.id, start_date=date.today(), created_by=admin.id,
        created_at=t + timedelta(minutes=2))
    db.add_all([review, intervention])
    db.flush()
    day = datetime(t.year, t.month, t.day, tzinfo=timezone.utc)
    due = FollowUp(intervention_id=intervention.id, student_id=ready.id,
        assigned_to=advisor.id, scheduled_for=day + timedelta(hours=10),
        method=FollowUpMethod.IN_PERSON, purpose="Check in", status=FollowUpStatus.SCHEDULED,
        created_by=admin.id)
    overdue = FollowUp(intervention_id=intervention.id, student_id=ready.id,
        assigned_to=advisor.id, scheduled_for=day - timedelta(hours=1),
        method=FollowUpMethod.IN_PERSON, purpose="Old check in", status=FollowUpStatus.SCHEDULED,
        created_by=admin.id)
    imported = ImportJob(uploaded_by=admin.id, filename="data.csv", total_rows=0,
        valid_rows=0, invalid_rows=0, status=ImportStatus.IMPORTED,
        completed_at=t - timedelta(hours=1))
    db.add_all([due, overdue, imported])
    db.commit()
    return ready, empty, current, warning, t


def test_dashboard_aggregates_current_facts(client, db_session, create_user, auth_headers):
    ready, _, current, warning, t = _data(db_session, create_user)
    response = client.get("/api/v1/dashboard/overview", headers=auth_headers("readeradvisor"))
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["students"] == {"total": 2, "prediction_ready": 1, "with_latest_prediction": 1}
    assert result["risk_distribution"] == {"low": 0, "medium": 1, "high": 0}
    assert result["warnings"] == {"active": 2, "pending_review": 0,
                                  "confirmed": 2, "dismissed": 0}
    assert result["interventions"]["active"] == 1
    assert result["follow_ups"] == {"due_today": 1, "overdue": 1}
    assert result["model"]["version"] == "fixture-v1"
    assert result["data_freshness"]["last_import_at"] is not None
    assert result["data_freshness"]["last_prediction_at"] is not None
    assert [row["warning_id"] for row in result["attention_students"]] == [str(warning.id)]
    assert result["warning_activity"] and result["intervention_activity"]


def test_registry_filters_linkage_and_profile(client, db_session, create_user, auth_headers):
    ready, empty, current, warning, _ = _data(db_session, create_user)
    headers = auth_headers("readersystem")
    url = "/api/v1/student-registry"
    response = client.get(url, headers=headers)
    assert response.status_code == 200, response.text
    page = response.json()
    assert page["total"] == 2
    assert page["total_pages"] == 1
    row = next(row for row in page["items"] if row["student_number"] == "READ-1")
    assert row["latest_prediction"]["id"] == str(current.id)
    assert row["warning"]["id"] == str(warning.id)
    assert row["intervention"]["status"] == "IN_PROGRESS"
    assert row["case_owner"]["full_name"]
    assert row["semester_one"]["approval_rate"] is not None
    assert row["prediction_readiness"] == "READY"
    empty_row = next(row for row in page["items"] if row["student_number"] == "READ-2")
    assert empty_row["warning"] is None and empty_row["semester_one"] is None
    for params, expected in [({"prediction_readiness": "READY"}, 1),
                             ({"warning_state": "NONE"}, 1),
                             ({"intervention_state": "IN_PROGRESS"}, 1),
                             ({"risk_level": "LOW"}, 0),
                             ({"course_code": 33}, 1),
                             ({"search": "Incomplete"}, 1)]:
        filtered = client.get(url, params=params, headers=headers)
        assert filtered.status_code == 200, filtered.text
        assert filtered.json()["total"] == expected
    assert client.get(url, params={"page_size": 1, "page": 2}, headers=headers).json()["total_pages"] == 2
    profile = client.get(f"/api/v1/students/{ready.id}/profile", headers=headers)
    assert profile.status_code == 200, profile.text
    body = profile.json()
    assert body["prediction_readiness"]["status"] == "READY"
    assert body["latest_prediction"]["id"] == str(current.id)
    assert [p["risk_level"] for p in body["prediction_history"]] == ["MEDIUM", "HIGH"]
    assert body["active_warning"]["id"] == str(warning.id)
    assert len(body["warning_history"]) == 2
    assert len(body["follow_ups"]) == 2
    assert {e["type"] for e in body["timeline"]} >= {"PREDICTION_CREATED", "WARNING_REVIEWED", "FOLLOW_UP_SCHEDULED"}
    assert all(body["timeline"][i]["occurred_at"] >= body["timeline"][i+1]["occurred_at"]
               for i in range(len(body["timeline"]) - 1))
    assert client.get(f"/api/v1/students/{uuid4()}/profile", headers=headers).status_code == 404


def test_all_roles_read_and_anonymous_rejected(client, db_session, create_user, auth_headers):
    ready, *_ = _data(db_session, create_user)
    for path in ("/api/v1/dashboard/overview", "/api/v1/student-registry",
                 f"/api/v1/students/{ready.id}/profile"):
        assert client.get(path).status_code == 401
        for username in ("readeradmin", "readeradvisor", "readersystem"):
            response = client.get(path, headers=auth_headers(username))
            assert response.status_code == 200, response.text


def test_low_latest_prediction_does_not_resurface_historical_warning(
        client, db_session, create_user, auth_headers):
    ready, _, current, _, t = _data(db_session, create_user)
    low = PredictionResult(student_id=ready.id, model_version_id=current.model_version_id,
        probability=0.1, risk_level=RiskLevel.LOW, feature_snapshot={}, explanation=[],
        predicted_at=t + timedelta(minutes=5))
    db_session.add(low)
    db_session.commit()
    headers = auth_headers("readeradvisor")
    dashboard = client.get("/api/v1/dashboard/overview", headers=headers).json()
    assert dashboard["risk_distribution"] == {"low": 1, "medium": 0, "high": 0}
    assert dashboard["attention_students"] == []
    registry = client.get("/api/v1/student-registry", params={"warning_state": "NONE"},
                          headers=headers).json()
    assert registry["total"] == 2
    row = next(row for row in registry["items"] if row["student_id"] == str(ready.id))
    assert row["latest_prediction"]["id"] == str(low.id)
    assert row["warning"] is None and row["intervention"] is None
    profile = client.get(f"/api/v1/students/{ready.id}/profile", headers=headers).json()
    assert profile["active_warning"] is None
    assert len(profile["warning_history"]) == 2


def test_registry_current_filters_sort_and_bounded_queries(
        client, db_session, create_user, auth_headers):
    ready, _, _, warning, _ = _data(db_session, create_user)
    headers = auth_headers("readeradmin")
    engine = db_session.get_bind()
    statements = []
    def record(*args):
        statements.append(args[2])
    event.listen(engine, "before_cursor_execute", record)
    try:
        result = client.get("/api/v1/student-registry",
            params={"sort": "risk_probability", "order": "desc", "page_size": 2},
            headers=headers)
    finally:
        event.remove(engine, "before_cursor_execute", record)
    assert result.status_code == 200, result.text
    assert result.json()["items"][0]["student_id"] == str(ready.id)
    assert len(statements) <= 12
    for params, expected in [({"warning_state": "CONFIRMED"}, 1),
                             ({"warning_state": "PENDING_REVIEW"}, 0),
                             ({"prediction_readiness": "NOT_READY"}, 1),
                             ({"intervention_state": "PLANNED"}, 0)]:
        response = client.get("/api/v1/student-registry", params=params, headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["total"] == expected
    warning.review_state = WarningReviewState.DISMISSED
    db_session.commit()
    dismissed = client.get("/api/v1/student-registry",
        params={"warning_state": "DISMISSED"}, headers=headers).json()
    assert dismissed["total"] == 1
    profile = client.get(f"/api/v1/students/{ready.id}/profile", headers=headers).json()
    assert profile["active_warning"] is None
    dashboard = client.get("/api/v1/dashboard/overview", headers=headers).json()
    assert dashboard["warnings"]["active"] == 1
