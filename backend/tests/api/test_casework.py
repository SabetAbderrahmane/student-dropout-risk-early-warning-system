from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from app.ml.runtime import ModelRuntime
from app.models import FollowUp, Intervention, InterventionNote, UserRole, Warning
from app.services.casework_service import CaseworkService
from tests.api.test_predictions import create_ready_student


def setup(client, db, create_user, auth_headers, monkeypatch):
    accounts = {
        name: create_user(username=name, role=role)
        for name, role in (
            ("academic", UserRole.ACADEMIC_ADMIN),
            ("advisor", UserRole.ACADEMIC_ADVISOR),
            ("other", UserRole.ACADEMIC_ADVISOR),
            ("system", UserRole.SYSTEM_ADMIN),
        )
    }
    headers = {name: auth_headers(name) for name in accounts}
    student = create_ready_student(db, "CASE-1")
    monkeypatch.setattr(ModelRuntime, "classify", lambda self, probability: "HIGH")
    prediction = client.post(
        f"/api/v1/students/{student.id}/predictions", headers=headers["academic"]
    )
    assert prediction.status_code == 201, prediction.text
    warning = db.scalar(
        select(Warning).where(Warning.prediction_id == UUID(prediction.json()["id"]))
    )
    assert (
        client.patch(
            f"/api/v1/warnings/{warning.id}/assignment",
            json={"assigned_to": str(accounts["advisor"].id)},
            headers=headers["academic"],
        ).status_code
        == 200
    )
    return accounts, headers, student, warning


def intervention_payload(student, warning, assignee):
    return {
        "student_id": str(student.id),
        "warning_id": str(warning.id),
        "type": "ACADEMIC_TUTORING",
        "title": "  Academic support  ",
        "description": "  Structured plan  ",
        "priority": "P2_ELEVATED",
        "assigned_to": str(assignee.id),
        "start_date": "2026-10-01",
        "target_date": "2026-10-15",
    }


def confirm(client, warning, headers):
    response = client.post(
        f"/api/v1/warnings/{warning.id}/reviews",
        json={"decision": "CONFIRMED", "note": "Confirmed after review"},
        headers=headers["advisor"],
    )
    assert response.status_code == 201, response.text


def create_intervention(client, student, warning, accounts, headers, role="academic"):
    response = client.post(
        "/api/v1/interventions",
        json=intervention_payload(student, warning, accounts["advisor"]),
        headers=headers[role],
    )
    assert response.status_code == 201, response.text
    return response.json()


def follow_up_payload(assignee, scheduled_for=None):
    return {
        "scheduled_for": (
            scheduled_for or datetime.now(timezone.utc) + timedelta(days=2)
        ).isoformat(),
        "method": "IN_PERSON",
        "purpose": "  Review progress  ",
        "assigned_to": str(assignee.id),
    }


def assert_error(response, status, code):
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code


def test_intervention_creation_gates_and_ownership(
    client: TestClient, db_session: Session, create_user, auth_headers, monkeypatch
):
    accounts, headers, student, warning = setup(
        client, db_session, create_user, auth_headers, monkeypatch
    )
    payload = intervention_payload(student, warning, accounts["advisor"])
    assert_error(
        client.post("/api/v1/interventions", json=payload, headers=headers["academic"]),
        409,
        "INTERVENTION_REQUIRES_CONFIRMED_WARNING",
    )
    confirm(client, warning, headers)
    wrong = dict(payload, student_id=str(uuid4()))
    assert_error(
        client.post("/api/v1/interventions", json=wrong, headers=headers["academic"]),
        409,
        "INTERVENTION_WARNING_STUDENT_MISMATCH",
    )
    assert_error(
        client.post("/api/v1/interventions", json=payload, headers=headers["system"]),
        403,
        "INSUFFICIENT_PERMISSIONS",
    )
    assert_error(
        client.post("/api/v1/interventions", json=payload, headers=headers["other"]),
        403,
        "INTERVENTION_ASSIGNED_TO_DIFFERENT_ADVISOR",
    )
    inactive = create_user(
        username="inactive", role=UserRole.ACADEMIC_ADVISOR, is_active=False
    )
    for assignee in (inactive, accounts["system"], accounts["academic"]):
        invalid = dict(payload, assigned_to=str(assignee.id))
        assert_error(
            client.post(
                "/api/v1/interventions", json=invalid, headers=headers["academic"]
            ),
            422,
            "INVALID_INTERVENTION_ASSIGNEE",
        )
    for changed in (
        dict(payload, title="  "),
        dict(payload, description="  "),
        dict(payload, target_date="2026-09-30"),
    ):
        assert_error(
            client.post(
                "/api/v1/interventions", json=changed, headers=headers["academic"]
            ),
            422,
            "VALIDATION_ERROR",
        )
    created = create_intervention(
        client, student, warning, accounts, headers, role="advisor"
    )
    assert created["title"] == "Academic support"
    assert created["description"] == "Structured plan"
    assert created["student"]["id"] == str(student.id)
    assert created["warning"]["prediction_id"] == str(warning.prediction_id)
    assert created["status"] == "PLANNED"
    assert created["created_by"] == str(accounts["advisor"].id)
    assert (
        create_intervention(client, student, warning, accounts, headers)["id"]
        != created["id"]
    )
    assert db_session.scalar(select(func.count(Intervention.id))) == 2


def test_dismissed_warning_and_missing_warning_rejected(
    client: TestClient, db_session: Session, create_user, auth_headers, monkeypatch
):
    accounts, headers, student, warning = setup(
        client, db_session, create_user, auth_headers, monkeypatch
    )
    payload = intervention_payload(student, warning, accounts["advisor"])
    assert_error(
        client.post(
            "/api/v1/interventions",
            json=dict(payload, warning_id=str(uuid4())),
            headers=headers["academic"],
        ),
        404,
        "WARNING_NOT_FOUND",
    )
    assert (
        client.post(
            f"/api/v1/warnings/{warning.id}/reviews",
            json={"decision": "DISMISSED", "note": "No case needed"},
            headers=headers["advisor"],
        ).status_code
        == 201
    )
    assert_error(
        client.post("/api/v1/interventions", json=payload, headers=headers["academic"]),
        409,
        "INTERVENTION_REQUIRES_CONFIRMED_WARNING",
    )


def test_notes_are_append_only_and_rbac(
    client: TestClient, db_session: Session, create_user, auth_headers, monkeypatch
):
    accounts, headers, student, warning = setup(
        client, db_session, create_user, auth_headers, monkeypatch
    )
    confirm(client, warning, headers)
    intervention = create_intervention(client, student, warning, accounts, headers)
    url = f"/api/v1/interventions/{intervention['id']}/notes"
    assert_error(
        client.post(url, json={"note": "Note"}, headers=headers["system"]),
        403,
        "INSUFFICIENT_PERMISSIONS",
    )
    assert_error(
        client.post(url, json={"note": "Note"}, headers=headers["other"]),
        403,
        "INTERVENTION_ASSIGNED_TO_DIFFERENT_ADVISOR",
    )
    assert_error(
        client.post(url, json={"note": "  "}, headers=headers["advisor"]),
        422,
        "VALIDATION_ERROR",
    )
    first = client.post(
        url, json={"note": "  Advisor note  "}, headers=headers["advisor"]
    )
    second = client.post(url, json={"note": "Admin note"}, headers=headers["academic"])
    assert first.status_code == second.status_code == 201
    assert first.json()["author_id"] == str(accounts["advisor"].id)
    assert first.json()["note"] == "Advisor note"
    assert first.json()["created_at"]
    assert second.json()["id"] != first.json()["id"]
    assert db_session.scalar(select(func.count(InterventionNote.id))) == 2
    for role in headers:
        assert client.get(url, headers=headers[role]).status_code == 200
    assert [n["id"] for n in client.get(url, headers=headers["system"]).json()] == [
        second.json()["id"],
        first.json()["id"],
    ]
    assert (
        client.get(
            f"/api/v1/interventions/{intervention['id']}", headers=headers["system"]
        ).json()["notes"][0]["id"]
        == second.json()["id"]
    )


def test_intervention_transitions_completion_and_cancellation(
    client: TestClient, db_session: Session, create_user, auth_headers, monkeypatch
):
    accounts, headers, student, warning = setup(
        client, db_session, create_user, auth_headers, monkeypatch
    )
    confirm(client, warning, headers)
    intervention = create_intervention(client, student, warning, accounts, headers)
    url = f"/api/v1/interventions/{intervention['id']}"
    assert_error(
        client.patch(url, json={"status": "COMPLETED"}, headers=headers["advisor"]),
        409,
        "INVALID_INTERVENTION_TRANSITION",
    )
    assert_error(
        client.patch(url, json={"title": "Other"}, headers=headers["other"]),
        403,
        "INTERVENTION_ASSIGNED_TO_DIFFERENT_ADVISOR",
    )
    assert_error(
        client.patch(url, json={"title": "Other"}, headers=headers["system"]),
        403,
        "INSUFFICIENT_PERMISSIONS",
    )
    assert_error(
        client.patch(
            url,
            json={"assigned_to": str(accounts["other"].id)},
            headers=headers["advisor"],
        ),
        403,
        "INTERVENTION_ASSIGNED_TO_DIFFERENT_ADVISOR",
    )
    for state in ("IN_PROGRESS", "ACTION_REQUIRED", "IN_PROGRESS"):
        response = client.patch(url, json={"status": state}, headers=headers["advisor"])
        assert response.status_code == 200 and response.json()["status"] == state
    assert_error(
        client.post(
            url + "/complete",
            json={"outcome": "SUPPORT_COMPLETED", "completion_notes": "  "},
            headers=headers["advisor"],
        ),
        422,
        "VALIDATION_ERROR",
    )
    completed = client.post(
        url + "/complete",
        json={"outcome": "SUPPORT_COMPLETED", "completion_notes": "Goals met"},
        headers=headers["advisor"],
    )
    assert completed.status_code == 200 and completed.json()["status"] == "COMPLETED"
    assert (
        completed.json()["completed_at"]
        and completed.json()["completion_outcome"] == "SUPPORT_COMPLETED"
    )
    assert (
        client.get(
            f"/api/v1/warnings/{warning.id}", headers=headers["academic"]
        ).json()["review_state"]
        == "CONFIRMED"
    )
    assert_error(
        client.post(
            url + "/complete",
            json={"outcome": "OTHER", "completion_notes": "Again"},
            headers=headers["advisor"],
        ),
        409,
        "INVALID_INTERVENTION_TRANSITION",
    )
    assert_error(
        client.patch(url, json={"title": "Changed"}, headers=headers["academic"]),
        409,
        "INVALID_INTERVENTION_TRANSITION",
    )
    another = create_intervention(client, student, warning, accounts, headers)
    cancelled = client.post(
        f"/api/v1/interventions/{another['id']}/cancel",
        json={"reason": "Plan withdrawn"},
        headers=headers["academic"],
    )
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "CANCELLED"
    assert_error(
        client.patch(
            f"/api/v1/interventions/{another['id']}",
            json={"status": "IN_PROGRESS"},
            headers=headers["academic"],
        ),
        409,
        "INVALID_INTERVENTION_TRANSITION",
    )


def test_admin_reassignment_changes_case_owner(
    client: TestClient, db_session: Session, create_user, auth_headers, monkeypatch
):
    accounts, headers, student, warning = setup(
        client, db_session, create_user, auth_headers, monkeypatch
    )
    confirm(client, warning, headers)
    intervention = create_intervention(client, student, warning, accounts, headers)
    url = f"/api/v1/interventions/{intervention['id']}"
    changed = client.patch(
        url,
        json={"assigned_to": str(accounts["other"].id)},
        headers=headers["academic"],
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["assigned_advisor"]["id"] == str(accounts["other"].id)
    assert_error(
        client.patch(url, json={"title": "Old owner"}, headers=headers["advisor"]),
        403,
        "INTERVENTION_ASSIGNED_TO_DIFFERENT_ADVISOR",
    )
    assert (
        client.patch(
            url, json={"title": "New owner"}, headers=headers["other"]
        ).status_code
        == 200
    )


def test_follow_up_intervention_completed_outcome_does_not_auto_complete_case(
    client: TestClient, db_session: Session, create_user, auth_headers, monkeypatch
):
    accounts, headers, student, warning = setup(
        client, db_session, create_user, auth_headers, monkeypatch
    )
    confirm(client, warning, headers)
    intervention = create_intervention(client, student, warning, accounts, headers)
    follow_up = client.post(
        f"/api/v1/interventions/{intervention['id']}/follow-ups",
        json=follow_up_payload(accounts["advisor"]),
        headers=headers["advisor"],
    ).json()
    result = client.post(
        f"/api/v1/follow-ups/{follow_up['id']}/complete",
        json={
            "outcome": "INTERVENTION_COMPLETED",
            "notes": "Recommend case completion",
        },
        headers=headers["advisor"],
    )
    assert (
        result.status_code == 200
        and result.json()["outcome"] == "INTERVENTION_COMPLETED"
    )
    detail = client.get(
        f"/api/v1/interventions/{intervention['id']}", headers=headers["academic"]
    ).json()
    assert detail["status"] == "PLANNED" and detail["completed_at"] is None


def test_follow_up_creation_status_and_filters(
    client: TestClient, db_session: Session, create_user, auth_headers, monkeypatch
):
    accounts, headers, student, warning = setup(
        client, db_session, create_user, auth_headers, monkeypatch
    )
    confirm(client, warning, headers)
    intervention = create_intervention(client, student, warning, accounts, headers)
    url = f"/api/v1/interventions/{intervention['id']}/follow-ups"
    inactive = create_user(
        username="inactive", role=UserRole.ACADEMIC_ADVISOR, is_active=False
    )
    for assignee in (inactive, accounts["system"]):
        assert_error(
            client.post(
                url, json=follow_up_payload(assignee), headers=headers["academic"]
            ),
            422,
            "INVALID_FOLLOW_UP_ASSIGNEE",
        )
    assert_error(
        client.post(
            url,
            json=dict(follow_up_payload(accounts["advisor"]), purpose="  "),
            headers=headers["academic"],
        ),
        422,
        "VALIDATION_ERROR",
    )
    assert_error(
        client.post(
            url, json=follow_up_payload(accounts["advisor"]), headers=headers["other"]
        ),
        403,
        "INTERVENTION_ASSIGNED_TO_DIFFERENT_ADVISOR",
    )
    assert_error(
        client.post(
            url, json=follow_up_payload(accounts["advisor"]), headers=headers["system"]
        ),
        403,
        "INSUFFICIENT_PERMISSIONS",
    )
    now = datetime.now(timezone.utc)
    day_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    dates = (day_start - timedelta(seconds=1), day_start, day_start + timedelta(days=1))
    statuses = []
    ids = []
    for scheduled in dates:
        response = client.post(
            url,
            json=follow_up_payload(accounts["advisor"], scheduled),
            headers=headers["advisor"],
        )
        assert response.status_code == 201, response.text
        statuses.append(response.json()["effective_status"])
        ids.append(response.json()["id"])
        assert response.json()["student"]["id"] == str(student.id)
        assert response.json()["warning_id"] == str(warning.id)
        assert response.json()["prediction_id"] == str(warning.prediction_id)
        assert response.json()["purpose"] == "Review progress"
    assert statuses == ["OVERDUE", "DUE", "SCHEDULED"]
    for state in statuses:
        result = client.get(
            "/api/v1/follow-ups", params={"status": state}, headers=headers["academic"]
        )
        assert result.status_code == 200 and result.json()["total"] == 1
    for role in headers:
        assert (
            client.get("/api/v1/follow-ups", headers=headers[role]).json()["total"] == 3
        )
        assert (
            client.get(
                f"/api/v1/follow-ups/{ids[0]}", headers=headers[role]
            ).status_code
            == 200
        )
        assert client.get(url, headers=headers[role]).json()["total"] == 3
    for params in (
        {"assigned_to": str(accounts["advisor"].id)},
        {"student_id": str(student.id)},
        {"intervention_id": intervention["id"]},
        {"search": "CASE-1"},
        {"from": dates[0].isoformat(), "to": dates[1].isoformat()},
    ):
        result = client.get(
            "/api/v1/follow-ups", params=params, headers=headers["academic"]
        )
        assert result.status_code == 200 and result.json()["total"] >= 2
    page = client.get(
        "/api/v1/follow-ups",
        params={"page": 2, "page_size": 1},
        headers=headers["academic"],
    ).json()
    assert page["total_pages"] == 3 and len(page["items"]) == 1


def test_follow_up_update_complete_next_and_terminal(
    client: TestClient, db_session: Session, create_user, auth_headers, monkeypatch
):
    accounts, headers, student, warning = setup(
        client, db_session, create_user, auth_headers, monkeypatch
    )
    confirm(client, warning, headers)
    intervention = create_intervention(client, student, warning, accounts, headers)
    url = f"/api/v1/interventions/{intervention['id']}/follow-ups"
    created = client.post(
        url, json=follow_up_payload(accounts["advisor"]), headers=headers["academic"]
    ).json()
    endpoint = f"/api/v1/follow-ups/{created['id']}"
    assert_error(
        client.patch(endpoint, json={"purpose": "New"}, headers=headers["other"]),
        403,
        "FOLLOW_UP_ASSIGNED_TO_DIFFERENT_ADVISOR",
    )
    assert_error(
        client.patch(endpoint, json={"purpose": "New"}, headers=headers["system"]),
        403,
        "INSUFFICIENT_PERMISSIONS",
    )
    assert_error(
        client.patch(
            endpoint,
            json={"assigned_to": str(accounts["other"].id)},
            headers=headers["advisor"],
        ),
        403,
        "FOLLOW_UP_ASSIGNED_TO_DIFFERENT_ADVISOR",
    )
    updated = client.patch(
        endpoint,
        json={"purpose": "  New purpose  ", "method": "PHONE"},
        headers=headers["advisor"],
    )
    assert updated.status_code == 200 and updated.json()["purpose"] == "New purpose"
    assert updated.json()["method"] == "PHONE"
    assert_error(
        client.post(
            endpoint + "/complete",
            json={"outcome": "PROGRESS_OBSERVED", "notes": "  "},
            headers=headers["advisor"],
        ),
        422,
        "VALIDATION_ERROR",
    )
    next_at = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
    completed = client.post(
        endpoint + "/complete",
        json={
            "outcome": "PROGRESS_OBSERVED",
            "notes": "Attended",
            "next_follow_up_at": next_at,
        },
        headers=headers["advisor"],
    )
    assert completed.status_code == 200, completed.text
    assert (
        completed.json()["stored_status"] == "COMPLETED"
        and completed.json()["effective_status"] == "COMPLETED"
    )
    assert (
        completed.json()["completed_at"]
        and completed.json()["outcome"] == "PROGRESS_OBSERVED"
    )
    rows = list(db_session.scalars(select(FollowUp).order_by(FollowUp.created_at)))
    assert len(rows) == 2 and {row.status.value for row in rows} == {
        "SCHEDULED",
        "COMPLETED",
    }
    next_row = next(row for row in rows if row.status.value == "SCHEDULED")
    completed_row = next(row for row in rows if row.status.value == "COMPLETED")
    assert (
        next_row.intervention_id == completed_row.intervention_id
        and next_row.student_id == student.id
    )
    assert_error(
        client.patch(endpoint, json={"purpose": "Changed"}, headers=headers["advisor"]),
        409,
        "INVALID_FOLLOW_UP_TRANSITION",
    )
    assert_error(
        client.post(
            endpoint + "/complete",
            json={"outcome": "COMPLETED", "notes": "Again"},
            headers=headers["advisor"],
        ),
        409,
        "INVALID_FOLLOW_UP_TRANSITION",
    )
    assert client.get(
        f"/api/v1/interventions/{intervention['id']}", headers=headers["system"]
    ).json()["follow_ups"]


def test_next_follow_up_failure_rolls_back_completion(
    client: TestClient, db_session: Session, create_user, auth_headers, monkeypatch
):
    accounts, headers, student, warning = setup(
        client, db_session, create_user, auth_headers, monkeypatch
    )
    confirm(client, warning, headers)
    intervention = create_intervention(client, student, warning, accounts, headers)
    created = client.post(
        f"/api/v1/interventions/{intervention['id']}/follow-ups",
        json=follow_up_payload(accounts["advisor"]),
        headers=headers["advisor"],
    ).json()

    def fail_next(session, flush_context, instances):
        if any(isinstance(item, FollowUp) for item in session.new):
            raise RuntimeError("simulated next follow-up persistence failure")

    event.listen(db_session, "before_flush", fail_next)
    try:
        with pytest.raises(RuntimeError):
            client.post(
                f"/api/v1/follow-ups/{created['id']}/complete",
                json={
                    "outcome": "PROGRESS_OBSERVED",
                    "notes": "Reviewed",
                    "next_follow_up_at": (
                        datetime.now(timezone.utc) + timedelta(days=3)
                    ).isoformat(),
                },
                headers=headers["advisor"],
            )
    finally:
        event.remove(db_session, "before_flush", fail_next)
    db_session.expire_all()
    saved = db_session.get(FollowUp, UUID(created["id"]))
    assert saved.status.value == "SCHEDULED" and saved.completed_at is None
    assert db_session.scalar(select(func.count(FollowUp.id))) == 1


def test_follow_up_cancellation_and_intervention_cancel_gate(
    client: TestClient, db_session: Session, create_user, auth_headers, monkeypatch
):
    accounts, headers, student, warning = setup(
        client, db_session, create_user, auth_headers, monkeypatch
    )
    confirm(client, warning, headers)
    intervention = create_intervention(client, student, warning, accounts, headers)
    url = f"/api/v1/interventions/{intervention['id']}/follow-ups"
    follow_up = client.post(
        url, json=follow_up_payload(accounts["advisor"]), headers=headers["advisor"]
    ).json()
    endpoint = f"/api/v1/follow-ups/{follow_up['id']}"
    assert_error(
        client.post(
            endpoint + "/cancel", json={"reason": "  "}, headers=headers["advisor"]
        ),
        422,
        "VALIDATION_ERROR",
    )
    cancelled = client.post(
        endpoint + "/cancel",
        json={"reason": "Student unavailable"},
        headers=headers["advisor"],
    )
    assert (
        cancelled.status_code == 200
        and cancelled.json()["effective_status"] == "CANCELLED"
    )
    assert_error(
        client.patch(endpoint, json={"method": "EMAIL"}, headers=headers["advisor"]),
        409,
        "INVALID_FOLLOW_UP_TRANSITION",
    )
    assert (
        client.post(
            f"/api/v1/interventions/{intervention['id']}/cancel",
            json={"reason": "Plan withdrawn"},
            headers=headers["academic"],
        ).status_code
        == 200
    )
    assert_error(
        client.post(
            url,
            json=follow_up_payload(accounts["advisor"]),
            headers=headers["academic"],
        ),
        409,
        "INVALID_FOLLOW_UP_TRANSITION",
    )


def test_intervention_read_filters_and_pagination(
    client: TestClient, db_session: Session, create_user, auth_headers, monkeypatch
):
    accounts, headers, student, warning = setup(
        client, db_session, create_user, auth_headers, monkeypatch
    )
    confirm(client, warning, headers)
    first = create_intervention(client, student, warning, accounts, headers)
    second = create_intervention(client, student, warning, accounts, headers)
    assert (
        client.patch(
            f"/api/v1/interventions/{first['id']}",
            json={"status": "IN_PROGRESS", "priority": "P1_URGENT"},
            headers=headers["advisor"],
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/v1/interventions/{first['id']}",
            json={"status": "ACTION_REQUIRED"},
            headers=headers["advisor"],
        ).status_code
        == 200
    )
    for role in headers:
        assert (
            client.get("/api/v1/interventions", headers=headers[role]).json()["total"]
            == 2
        )
        assert (
            client.get(
                f"/api/v1/interventions/{first['id']}", headers=headers[role]
            ).status_code
            == 200
        )
        assert (
            client.get(
                f"/api/v1/students/{student.id}/interventions", headers=headers[role]
            ).json()["total"]
            == 2
        )
    result = client.get("/api/v1/interventions", headers=headers["academic"]).json()
    assert result["items"][0]["id"] == first["id"]
    for params in (
        {"search": "Academic support"},
        {"status": "ACTION_REQUIRED"},
        {"priority": "P1_URGENT"},
        {"type": "ACADEMIC_TUTORING"},
        {"assigned_to": str(accounts["advisor"].id)},
        {"student_id": str(student.id)},
        {"warning_id": str(warning.id)},
    ):
        response = client.get(
            "/api/v1/interventions", params=params, headers=headers["academic"]
        )
        assert response.status_code == 200 and response.json()["total"] >= 1
    page = client.get(
        "/api/v1/interventions",
        params={"page": 2, "page_size": 1},
        headers=headers["academic"],
    ).json()
    assert page["total_pages"] == 2 and len(page["items"]) == 1
    assert_error(
        client.get(f"/api/v1/interventions/{uuid4()}", headers=headers["academic"]),
        404,
        "INTERVENTION_NOT_FOUND",
    )
    assert_error(
        client.get(f"/api/v1/follow-ups/{uuid4()}", headers=headers["academic"]),
        404,
        "FOLLOW_UP_NOT_FOUND",
    )
