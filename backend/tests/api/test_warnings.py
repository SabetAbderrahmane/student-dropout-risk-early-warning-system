from uuid import uuid4

import pytest
from app.ml.runtime import ModelRuntime
from app.models import PredictionResult, UserRole, Warning, WarningReview
from app.models.warning import WarningPriority
from app.services.prediction_service import PredictionService
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from tests.api.test_predictions import create_ready_student


def users(create_user, auth_headers):
    created = {
        role: create_user(username=role, role=enum)
        for role, enum in (
            ("academic", UserRole.ACADEMIC_ADMIN),
            ("system", UserRole.SYSTEM_ADMIN),
            ("advisor", UserRole.ACADEMIC_ADVISOR),
            ("other", UserRole.ACADEMIC_ADVISOR),
        )
    }
    return created, {name: auth_headers(name) for name in created}


def force_risks(monkeypatch, *risks):
    sequence = iter(risks)
    monkeypatch.setattr(
        ModelRuntime, "classify", lambda self, probability: next(sequence)
    )


def count(db, model):
    return db.scalar(select(func.count(model.id)))


def error(response, status_code, code):
    assert response.status_code == status_code, response.text
    assert response.json()["error"]["code"] == code


def test_single_generation_mapping_history_and_duplicate_guard(
    client: TestClient, db_session: Session, create_user, auth_headers, monkeypatch
):
    _, headers = users(create_user, auth_headers)
    student = create_ready_student(db_session)
    force_risks(monkeypatch, "LOW", "MEDIUM", "HIGH", "HIGH")
    url = f"/api/v1/students/{student.id}/predictions"
    predictions = [
        client.post(url, headers=headers["academic"]).json() for _ in range(4)
    ]
    assert [p["risk_level"] for p in predictions] == ["LOW", "MEDIUM", "HIGH", "HIGH"]
    warnings = list(
        db_session.scalars(select(Warning).order_by(Warning.created_at, Warning.id))
    )
    assert count(db_session, PredictionResult) == 4
    assert len(warnings) == 3
    assert {str(w.prediction_id) for w in warnings} == {
        p["id"] for p in predictions[1:]
    }
    assert all(
        w.student_id == student.id
        and w.risk_level.value
        == next(p["risk_level"] for p in predictions if p["id"] == str(w.prediction_id))
        for w in warnings
    )
    assert {w.risk_level.value: w.priority for w in warnings} == {
        "MEDIUM": WarningPriority.P2_ELEVATED,
        "HIGH": WarningPriority.P1_URGENT,
    }
    duplicate = Warning(
        prediction_id=warnings[0].prediction_id,
        student_id=student.id,
        risk_level=warnings[0].risk_level,
        priority=warnings[0].priority,
    )
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
    assert count(db_session, Warning) == 3


def test_batch_counts_and_appends(
    client: TestClient, db_session: Session, create_user, auth_headers, monkeypatch
):
    _, headers = users(create_user, auth_headers)
    for index in range(3):
        create_ready_student(db_session, f"B-{index}")
    force_risks(monkeypatch, "LOW", "MEDIUM", "HIGH", "LOW", "MEDIUM", "HIGH")
    responses = [
        client.post("/api/v1/predictions/batch", headers=headers["academic"])
        for _ in range(2)
    ]
    assert all(r.status_code == 200 for r in responses)
    assert [r.json()["created_warnings"] for r in responses] == [2, 2]
    assert count(db_session, PredictionResult) == 6
    assert count(db_session, Warning) == 4
    assert len({w.prediction_id for w in db_session.scalars(select(Warning))}) == 4


def test_warning_failure_rolls_back_prediction(
    client: TestClient, db_session: Session, create_user, auth_headers, monkeypatch
):
    _, headers = users(create_user, auth_headers)
    student = create_ready_student(db_session)
    force_risks(monkeypatch, "HIGH")

    def fail(self, prediction):
        raise RuntimeError("simulated warning persistence failure")

    monkeypatch.setattr(PredictionService, "_add_warning_for_prediction", fail)
    with pytest.raises(RuntimeError):
        client.post(
            f"/api/v1/students/{student.id}/predictions", headers=headers["academic"]
        )
    assert count(db_session, PredictionResult) == 0
    assert count(db_session, Warning) == 0


def test_batch_warning_failure_rolls_back_all_predictions(
    client: TestClient, db_session: Session, create_user, auth_headers, monkeypatch
):
    _, headers = users(create_user, auth_headers)
    create_ready_student(db_session, "B-1")
    create_ready_student(db_session, "B-2")
    force_risks(monkeypatch, "HIGH", "HIGH")
    original = PredictionService._add_warning_for_prediction
    calls = 0

    def fail_second(self, prediction):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("simulated second warning failure")
        return original(self, prediction)

    monkeypatch.setattr(PredictionService, "_add_warning_for_prediction", fail_second)
    with pytest.raises(RuntimeError):
        client.post("/api/v1/predictions/batch", headers=headers["academic"])
    assert count(db_session, PredictionResult) == 0
    assert count(db_session, Warning) == 0


def test_warning_database_rejects_prediction_identity_mismatch(
    client: TestClient, db_session: Session, create_user, auth_headers, monkeypatch
):
    _, headers = users(create_user, auth_headers)
    student = create_ready_student(db_session, "IDENTITY-1")
    other = create_ready_student(db_session, "IDENTITY-2")
    force_risks(monkeypatch, "HIGH")
    assert (
        client.post(
            f"/api/v1/students/{student.id}/predictions", headers=headers["academic"]
        ).status_code
        == 201
    )
    original = db_session.scalar(select(Warning))
    db_session.delete(original)
    db_session.commit()
    for student_id, risk in ((other.id, original.risk_level), (student.id, "MEDIUM")):
        db_session.add(
            Warning(
                prediction_id=original.prediction_id,
                student_id=student_id,
                risk_level=risk,
                priority=original.priority,
            )
        )
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()


def test_assignment_review_rbac_and_append_only(
    client: TestClient, db_session: Session, create_user, auth_headers, monkeypatch
):
    accounts, headers = users(create_user, auth_headers)
    inactive = create_user(
        username="inactive", role=UserRole.ACADEMIC_ADVISOR, is_active=False
    )
    student = create_ready_student(db_session)
    force_risks(monkeypatch, "HIGH", "MEDIUM")
    for _ in range(2):
        assert (
            client.post(
                f"/api/v1/students/{student.id}/predictions",
                headers=headers["academic"],
            ).status_code
            == 201
        )
    warnings = list(
        db_session.scalars(select(Warning).order_by(Warning.created_at, Warning.id))
    )
    warning_id = warnings[0].id
    assignment = f"/api/v1/warnings/{warning_id}/assignment"
    review = f"/api/v1/warnings/{warning_id}/reviews"
    body = {"assigned_to": str(accounts["advisor"].id)}
    for role in ("system", "advisor"):
        error(
            client.patch(assignment, json=body, headers=headers[role]),
            403,
            "INSUFFICIENT_PERMISSIONS",
        )
    for target in (
        uuid4(),
        inactive.id,
        accounts["system"].id,
        accounts["academic"].id,
    ):
        error(
            client.patch(
                assignment,
                json={"assigned_to": str(target)},
                headers=headers["academic"],
            ),
            422,
            "INVALID_WARNING_ASSIGNEE",
        )
    for role in ("system", "academic"):
        error(
            client.post(
                review,
                json={"decision": "CONFIRMED", "note": "Reviewed"},
                headers=headers[role],
            ),
            403,
            "INSUFFICIENT_PERMISSIONS",
        )
    error(
        client.post(
            review,
            json={"decision": "CONFIRMED", "note": "Reviewed"},
            headers=headers["advisor"],
        ),
        409,
        "WARNING_REQUIRES_ASSIGNMENT",
    )
    assert (
        client.patch(assignment, json=body, headers=headers["academic"]).status_code
        == 200
    )
    error(
        client.post(
            review,
            json={"decision": "CONFIRMED", "note": "Reviewed"},
            headers=headers["other"],
        ),
        403,
        "WARNING_ASSIGNED_TO_DIFFERENT_ADVISOR",
    )
    error(
        client.post(
            review,
            json={"decision": "CONFIRMED", "note": "  "},
            headers=headers["advisor"],
        ),
        422,
        "VALIDATION_ERROR",
    )
    for decision in ("CONFIRMED", "DISMISSED"):
        response = client.post(
            review
            if decision == "CONFIRMED"
            else f"/api/v1/warnings/{warning_id}/reconsider",
            json={
                "decision": decision,
                "note": f"Review {decision}",
                **(
                    {
                        "reason": "New evidence",
                        "expected_revision": client.get(
                            f"/api/v1/warnings/{warning_id}",
                            headers=headers["academic"],
                        ).json()["revision"],
                    }
                    if decision == "DISMISSED"
                    else {}
                ),
            },
            headers=headers["advisor"],
        )
        assert response.status_code == 201, response.text
        assert response.json()["review_state"] == decision
    detail = response.json()
    assert len(detail["review_history"]) == 2
    assert [item["decision"] for item in detail["review_history"]] == [
        "DISMISSED",
        "CONFIRMED",
    ]
    assert count(db_session, WarningReview) == 2
    assert detail["prediction_id"] == str(warnings[0].prediction_id)
    assert len(detail["prediction_explanation"]) == 5
    assert detail["model_version"]
    # Assignment changes do not create reviews.
    assert (
        client.patch(
            assignment,
            json={"assigned_to": str(accounts["other"].id)},
            headers=headers["academic"],
        ).status_code
        == 200
    )
    assert count(db_session, WarningReview) == 2
    assert (
        client.patch(
            assignment, json={"assigned_to": None}, headers=headers["academic"]
        ).status_code
        == 200
    )


def test_read_filters_ordering_and_history(
    client: TestClient, db_session: Session, create_user, auth_headers, monkeypatch
):
    accounts, headers = users(create_user, auth_headers)
    first = create_ready_student(db_session, "A-SEARCH")
    second = create_ready_student(db_session, "B-SEARCH")
    force_risks(monkeypatch, "MEDIUM", "HIGH", "HIGH")
    for student in (first, second, first):
        assert (
            client.post(
                f"/api/v1/students/{student.id}/predictions",
                headers=headers["academic"],
            ).status_code
            == 201
        )
    listing = client.get("/api/v1/warnings", headers=headers["system"])
    assert listing.status_code == 200
    assert [row["priority"] for row in listing.json()["items"]] == [
        "P1_URGENT",
        "P1_URGENT",
        "P2_ELEVATED",
    ]
    high = listing.json()["items"][0]
    assert high["top_explanation_factors"]
    assert (
        client.patch(
            f"/api/v1/warnings/{high['id']}/assignment",
            json={"assigned_to": str(accounts["advisor"].id)},
            headers=headers["academic"],
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/warnings/{high['id']}/reviews",
            json={"decision": "CONFIRMED", "note": "Reviewed"},
            headers=headers["advisor"],
        ).status_code
        == 201
    )
    for role in ("system", "academic", "advisor"):
        assert (
            client.get("/api/v1/warnings", headers=headers[role]).json()["total"] == 3
        )
        assert (
            client.get(
                f"/api/v1/warnings/{high['id']}", headers=headers[role]
            ).status_code
            == 200
        )
        assert (
            client.get(
                f"/api/v1/students/{first.id}/warnings", headers=headers[role]
            ).json()["total"]
            == 2
        )
    for params, expected in (
        ({"search": "B-SEARCH"}, 1),
        ({"risk_level": "MEDIUM"}, 1),
        ({"priority": "P2_ELEVATED"}, 1),
        ({"review_state": "CONFIRMED"}, 1),
        ({"assigned_to": str(accounts["advisor"].id)}, 1),
    ):
        assert (
            client.get(
                "/api/v1/warnings", params=params, headers=headers["advisor"]
            ).json()["total"]
            == expected
        )
    page = client.get(
        "/api/v1/warnings",
        params={"page": 2, "page_size": 1},
        headers=headers["advisor"],
    ).json()
    assert len(page["items"]) == 1 and page["total_pages"] == 3
    history = client.get(
        f"/api/v1/students/{first.id}/warnings", headers=headers["advisor"]
    ).json()["items"]
    assert (
        len(history) == 2 and history[0]["prediction_id"] != history[1]["prediction_id"]
    )
    assert history[0]["created_at"] >= history[1]["created_at"]
    error(
        client.get(f"/api/v1/warnings/{uuid4()}", headers=headers["advisor"]),
        404,
        "WARNING_NOT_FOUND",
    )
