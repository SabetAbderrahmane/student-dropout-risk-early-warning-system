"""C1 audit characterization: existing behavior, not acceptance of these defects.

Real endpoint/RBAC/transaction evidence on disposable PostgreSQL databases.
No model training or prediction execution, SQLite, or service-result substitutions.
Pause hooks control timing only; PostgreSQL still acquires the actual row locks.
"""

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from uuid import uuid4

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from alembic import command
from app.core.config import get_settings
from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models import ModelVersion, PredictionResult, Student, User, UserRole, Warning
from app.repositories.casework_repository import CaseworkRepository
from app.repositories.user_repository import UserRepository
from app.repositories.warning_repository import WarningRepository

pytestmark = pytest.mark.model_integration


@pytest.fixture(autouse=True)
def isolated_model_runtime():
    # Override the suite's synthetic-training autouse fixture: this is casework
    # auditing only, and the user explicitly prohibited retraining models.
    yield


def checked(response, status=200, code=None):
    assert response.status_code == status, response.text
    body = response.json()
    if code:
        assert body["error"]["code"] == code, body
    return body


@pytest.fixture()
def audit(monkeypatch):
    url = os.environ.get("C1_CASEWORK_TEST_DATABASE_URL")
    if not url:
        pytest.skip(
            "Set C1_CASEWORK_TEST_DATABASE_URL to a dedicated PostgreSQL CREATE DATABASE server"
        )
    root = create_engine(url, isolation_level="AUTOCOMMIT")
    assert root.dialect.name == "postgresql", (
        "PostgreSQL is required; no SQLite fallback"
    )
    name = "casework_c1_audit_" + uuid4().hex
    with root.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    target = make_url(url).set(database=name)
    engine = create_engine(
        target,
        connect_args={
            "options": "-c lock_timeout=5000 -c statement_timeout=10000 -c application_name=c1-casework-audit"
        },
    )
    prior = dict(app.dependency_overrides)
    client = TestClient(app)  # No lifespan startup or unrelated model registration.
    try:
        monkeypatch.setattr(
            get_settings(), "database_url", target.render_as_string(hide_password=False)
        )
        command.upgrade(Config("alembic.ini"), "head")
        with engine.connect() as connection:
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "20261013_0011"
            )
        ids = {}
        with Session(engine) as db:
            for key, role in [
                ("system", UserRole.SYSTEM_ADMIN),
                ("academic", UserRole.ACADEMIC_ADMIN),
                ("advisor", UserRole.ACADEMIC_ADVISOR),
                ("other", UserRole.ACADEMIC_ADVISOR),
                ("spare", UserRole.ACADEMIC_ADVISOR),
            ]:
                user = User(
                    username="c1_" + key,
                    email=key + "@example.edu",
                    full_name=key,
                    role=role,
                    password_hash="unused-token-fixture",
                    is_active=True,
                )
                db.add(user)
                db.flush()
                UserRepository(db).claim_identifiers(user)
                ids[key] = str(user.id)
            metadata = json.loads(
                Path("app/ml/model_registry/dropout-risk-v1/metadata.json").read_bytes()
            )
            model = ModelVersion(
                model_name=metadata["model_name"],
                model_version=metadata["model_version"],
                feature_schema_version=metadata["feature_schema_version"],
                trained_at=datetime.fromisoformat(metadata["trained_at"]),
                low_threshold=metadata["thresholds"]["low_threshold"],
                high_threshold=metadata["thresholds"]["high_threshold"],
                metrics=metadata["final_test_metrics"],
                metadata_json=metadata,
                artifact_path=metadata["artifact_path"],
                is_active=True,
            )
            student = Student(
                student_number="C1-AUDIT", name="Disposable casework fixture"
            )
            db.add_all([model, student])
            db.flush()
            # Historical prediction fixture, not an inferred model output.
            prediction = PredictionResult(
                student_id=student.id,
                model_version_id=model.id,
                probability=0.8,
                risk_level="HIGH",
                feature_snapshot={},
                explanation=[],
                created_by=ids["academic"],
            )
            db.add(prediction)
            db.flush()
            warning = Warning(
                student_id=student.id,
                prediction_id=prediction.id,
                risk_level="HIGH",
                priority="P1_URGENT",
            )
            db.add(warning)
            db.flush()
            ids.update(
                student=str(student.id),
                warning=str(warning.id),
                prediction=str(prediction.id),
            )
            db.commit()

        def request_db():
            with Session(engine, expire_on_commit=False) as db:
                yield db

        app.dependency_overrides[get_db] = request_db
        headers = {
            key: {"Authorization": "Bearer " + create_access_token(value)}
            for key, value in ids.items()
            if key in {"system", "academic", "advisor", "other", "spare"}
        }
        env = SimpleNamespace(engine=engine, client=client, ids=ids, headers=headers)
        checked(
            client.patch(
                f"/api/v1/warnings/{ids['warning']}/assignment",
                headers=headers["academic"],
                json={"assigned_to": ids["advisor"]},
            )
        )
        checked(
            client.post(
                f"/api/v1/warnings/{ids['warning']}/reviews",
                headers=headers["advisor"],
                json={"decision": "CONFIRMED", "note": "Original human decision"},
            ),
            201,
        )
        result = checked(
            client.post(
                "/api/v1/interventions",
                headers=headers["academic"],
                json={
                    "student_id": ids["student"],
                    "warning_id": ids["warning"],
                    "type": "ACADEMIC_TUTORING",
                    "title": "Original support",
                    "description": "Audited case",
                    "priority": "P1_URGENT",
                    "assigned_to": ids["advisor"],
                    "start_date": "2026-10-14",
                },
            ),
            201,
        )
        ids["intervention"] = result["id"]
        ids["follow_up"] = checked(
            client.post(
                f"/api/v1/interventions/{ids['intervention']}/follow-ups",
                headers=headers["academic"],
                json=follow_payload(env),
            ),
            201,
        )["id"]
        yield env
    finally:
        client.close()
        app.dependency_overrides.clear()
        app.dependency_overrides.update(prior)
        engine.dispose()
        # Only this fixture's generated UUID database is dropped.
        with root.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        root.dispose()


def follow_payload(audit, owner="advisor"):
    return {
        "assigned_to": audit.ids[owner],
        "scheduled_for": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
        "method": "IN_PERSON",
        "purpose": "Original support obligation",
    }


def complete_payload(next_item=False):
    body = {"outcome": "PROGRESS_OBSERVED", "notes": "Original follow-up evidence"}
    if next_item:
        body["next_follow_up_at"] = (datetime.now(UTC) + timedelta(days=4)).isoformat()
    return body


def fu(audit, role="advisor", next_item=False):
    return audit.client.post(
        f"/api/v1/follow-ups/{audit.ids['follow_up']}/complete",
        headers=audit.headers[role],
        json=complete_payload(next_item),
    )


def close_case(audit, terminal):
    payload = (
        {"reason": "Explicit cancellation"}
        if terminal == "cancel"
        else {"outcome": "SUPPORT_COMPLETED", "completion_notes": "Explicit completion"}
    )
    return audit.client.post(
        f"/api/v1/interventions/{audit.ids['intervention']}/{terminal}",
        headers=audit.headers["advisor"],
        json=payload,
    )


def transfer(audit):
    return audit.client.patch(
        f"/api/v1/interventions/{audit.ids['intervention']}",
        headers=audit.headers["academic"],
        json={"assigned_to": audit.ids["other"]},
    )


def test_transfer_strands_follow_up_until_academic_admin_recovers_it(audit):
    case = checked(transfer(audit))
    assert case["assigned_advisor"]["id"] == audit.ids["other"]
    assert case["follow_ups"][0]["assigned_advisor"]["id"] == audit.ids["advisor"]
    for role in ("advisor", "other"):
        checked(fu(audit, role), 403, "FOLLOW_UP_ASSIGNED_TO_DIFFERENT_ADVISOR")
    checked(
        audit.client.patch(
            f"/api/v1/follow-ups/{audit.ids['follow_up']}",
            headers=audit.headers["academic"],
            json={"assigned_to": audit.ids["other"]},
        )
    )
    checked(fu(audit, "other"))


def test_admin_can_create_an_immediately_unactionable_delegated_follow_up(audit):
    result = checked(
        audit.client.post(
            f"/api/v1/interventions/{audit.ids['intervention']}/follow-ups",
            headers=audit.headers["academic"],
            json=follow_payload(audit, "other"),
        ),
        201,
    )
    for role in ("advisor", "other"):
        checked(
            audit.client.post(
                f"/api/v1/follow-ups/{result['id']}/cancel",
                headers=audit.headers[role],
                json={"reason": "Cannot act"},
            ),
            403,
            "FOLLOW_UP_ASSIGNED_TO_DIFFERENT_ADVISOR",
        )


def test_repeated_review_can_dismiss_confirmed_warning_with_active_support(audit):
    result = checked(
        audit.client.post(
            f"/api/v1/warnings/{audit.ids['warning']}/reviews",
            headers=audit.headers["advisor"],
            json={"decision": "DISMISSED", "note": "Revised decision"},
        ),
        201,
    )
    assert result["review_state"] == "DISMISSED" and len(result["review_history"]) == 2
    case = checked(
        audit.client.get(
            f"/api/v1/interventions/{audit.ids['intervention']}",
            headers=audit.headers["advisor"],
        )
    )
    assert (
        case["status"] == "PLANNED"
        and case["follow_ups"][0]["stored_status"] == "SCHEDULED"
    )
    checked(
        audit.client.patch(
            f"/api/v1/interventions/{audit.ids['intervention']}",
            headers=audit.headers["advisor"],
            json={"status": "IN_PROGRESS"},
        )
    )
    profile = checked(
        audit.client.get(
            f"/api/v1/students/{audit.ids['student']}/profile",
            headers=audit.headers["academic"],
        )
    )
    assert (
        len(profile["warning_history"])
        == len(profile["interventions"])
        == len(profile["follow_ups"])
        == 1
    )


@pytest.mark.parametrize("terminal", ["complete", "cancel"])
def test_terminal_parent_retains_follow_ups_and_completion_can_create_successor(
    audit, terminal
):
    checked(close_case(audit, terminal))
    direct = audit.client.post(
        f"/api/v1/interventions/{audit.ids['intervention']}/follow-ups",
        headers=audit.headers["advisor"],
        json=follow_payload(audit),
    )
    checked(
        direct,
        409 if terminal == "cancel" else 201,
        "INVALID_FOLLOW_UP_TRANSITION" if terminal == "cancel" else None,
    )
    result = checked(fu(audit, next_item=True))
    assert result["stored_status"] == "COMPLETED"
    case = checked(
        audit.client.get(
            f"/api/v1/interventions/{audit.ids['intervention']}",
            headers=audit.headers["academic"],
        )
    )
    assert case["status"] == ("CANCELLED" if terminal == "cancel" else "COMPLETED")
    assert sum(row["stored_status"] == "SCHEDULED" for row in case["follow_ups"]) == (
        1 if terminal == "cancel" else 2
    )


@pytest.mark.parametrize("retained", ["warning", "intervention", "follow_up"])
@pytest.mark.parametrize("change", ["deactivate", "role"])
def test_each_existing_assignment_safeguard_is_preserved(audit, retained, change):
    if retained != "warning":
        checked(
            audit.client.post(
                f"/api/v1/warnings/{audit.ids['warning']}/reviews",
                headers=audit.headers["advisor"],
                json={"decision": "DISMISSED", "note": "Historical only"},
            ),
            201,
        )
    if retained != "intervention":
        checked(close_case(audit, "cancel"))
    if retained != "follow_up":
        checked(
            audit.client.post(
                f"/api/v1/follow-ups/{audit.ids['follow_up']}/cancel",
                headers=audit.headers["advisor"],
                json={"reason": "Resolved"},
            )
        )
    target = audit.ids["advisor"]
    response = (
        audit.client.post(
            f"/api/v1/users/{target}/deactivate", headers=audit.headers["system"]
        )
        if change == "deactivate"
        else audit.client.patch(
            f"/api/v1/users/{target}",
            headers=audit.headers["system"],
            json={"role": "ACADEMIC_ADMIN"},
        )
    )
    result = checked(response, 409, "ADVISOR_HAS_ACTIVE_ASSIGNMENTS")
    assert result["error"]["details"] == {
        "warnings": int(retained == "warning"),
        "interventions": int(retained == "intervention"),
        "follow_ups": int(retained == "follow_up"),
    }


@pytest.mark.parametrize("change", ["deactivate", "role"])
def test_historical_ownership_survives_account_change_and_token_is_revoked(
    audit, change
):
    checked(
        audit.client.post(
            f"/api/v1/warnings/{audit.ids['warning']}/reviews",
            headers=audit.headers["advisor"],
            json={"decision": "DISMISSED", "note": "History retained"},
        ),
        201,
    )
    checked(close_case(audit, "cancel"))
    checked(
        audit.client.post(
            f"/api/v1/follow-ups/{audit.ids['follow_up']}/cancel",
            headers=audit.headers["advisor"],
            json={"reason": "History retained"},
        )
    )
    target = audit.ids["advisor"]
    response = (
        audit.client.post(
            f"/api/v1/users/{target}/deactivate", headers=audit.headers["system"]
        )
        if change == "deactivate"
        else audit.client.patch(
            f"/api/v1/users/{target}",
            headers=audit.headers["system"],
            json={"role": "ACADEMIC_ADMIN"},
        )
    )
    checked(response)
    checked(
        audit.client.get(
            f"/api/v1/warnings/{audit.ids['warning']}", headers=audit.headers["advisor"]
        ),
        401,
        "AUTHENTICATION_REQUIRED",
    )
    case = checked(
        audit.client.get(
            f"/api/v1/interventions/{audit.ids['intervention']}",
            headers=audit.headers["academic"],
        )
    )
    assert (
        case["assigned_advisor"]["id"] == target
        and case["follow_ups"][0]["assigned_advisor"]["id"] == target
    )
    with audit.engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM user_administration_audit")) == 1
        assert db.scalar(text("SELECT count(*) FROM warning_reviews")) == 2


def test_current_rbac_and_system_self_last_admin_safeguards(audit):
    for role in ("system", "academic"):
        checked(
            audit.client.post(
                f"/api/v1/warnings/{audit.ids['warning']}/reviews",
                headers=audit.headers[role],
                json={"decision": "DISMISSED", "note": "Forbidden"},
            ),
            403,
            "INSUFFICIENT_PERMISSIONS",
        )
    for role in ("advisor", "system"):
        checked(
            audit.client.patch(
                f"/api/v1/warnings/{audit.ids['warning']}/assignment",
                headers=audit.headers[role],
                json={"assigned_to": audit.ids["other"]},
            ),
            403,
            "INSUFFICIENT_PERMISSIONS",
        )
    checked(fu(audit, "system"), 403, "INSUFFICIENT_PERMISSIONS")
    for role in ("advisor", "academic"):
        checked(
            audit.client.post(
                f"/api/v1/users/{audit.ids['spare']}/deactivate",
                headers=audit.headers[role],
            ),
            403,
            "INSUFFICIENT_PERMISSIONS",
        )
    checked(
        audit.client.post(
            f"/api/v1/users/{audit.ids['system']}/deactivate",
            headers=audit.headers["system"],
        ),
        409,
        "SELF_DEACTIVATION_FORBIDDEN",
    )
    checked(
        audit.client.patch(
            f"/api/v1/users/{audit.ids['system']}",
            headers=audit.headers["system"],
            json={"role": "ACADEMIC_ADMIN"},
        ),
        409,
        "LAST_ACTIVE_SYSTEM_ADMIN",
    )


def pause_locked_read(monkeypatch, repository, method, target):
    ready, release = Event(), Event()
    original = getattr(repository, method)

    def paused(self, identifier, *args, **kwargs):
        value = original(self, identifier, *args, **kwargs)
        is_locked = method == "lock_by_id" or kwargs.get("lock", False)
        if is_locked and str(identifier) == target and not ready.is_set():
            ready.set()
            assert release.wait(8), "Controlled request was not released"
        return value

    monkeypatch.setattr(repository, method, paused)
    return ready, release


def wait_for_pg_lock(engine):
    deadline = time.monotonic() + 4
    with engine.connect() as db:
        while time.monotonic() < deadline:
            waiting = db.scalar(
                text(
                    "SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND application_name='c1-casework-audit' AND wait_event_type='Lock')"
                )
            )
            db.commit()  # A fresh statistics snapshot on each observation.
            if waiting:
                return
            time.sleep(0.03)
    pytest.fail("Expected PostgreSQL lock wait was not observed")


@pytest.mark.parametrize("parent_change", ["transfer", "cancel"])
def test_follow_up_completion_can_commit_after_parent_changes(
    audit, monkeypatch, parent_change
):
    ready, release = pause_locked_read(
        monkeypatch, CaseworkRepository, "follow_up", audit.ids["follow_up"]
    )
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="c1_first") as pool:
        future = pool.submit(fu, audit, "advisor", True)
        try:
            assert ready.wait(5)
            # Parent commits while the child remains locked.
            checked(
                transfer(audit)
                if parent_change == "transfer"
                else close_case(audit, "cancel")
            )
        finally:
            release.set()
        checked(future.result(timeout=10))
    case = checked(
        audit.client.get(
            f"/api/v1/interventions/{audit.ids['intervention']}",
            headers=audit.headers["academic"],
        )
    )
    if parent_change == "transfer":
        assert case["assigned_advisor"]["id"] == audit.ids["other"]
    else:
        assert case["status"] == "CANCELLED"
    assert any(
        row["stored_status"] == "SCHEDULED"
        and row["assigned_advisor"]["id"] == audit.ids["advisor"]
        for row in case["follow_ups"]
    )


def test_two_completions_are_serialized_and_create_only_one_successor(
    audit, monkeypatch
):
    ready, release = pause_locked_read(
        monkeypatch, CaseworkRepository, "follow_up", audit.ids["follow_up"]
    )
    with (
        ThreadPoolExecutor(max_workers=1, thread_name_prefix="c1_first") as first,
        ThreadPoolExecutor(max_workers=1, thread_name_prefix="c1_second") as second,
    ):
        one = first.submit(fu, audit, "advisor", True)
        try:
            assert ready.wait(5)
            two = second.submit(fu, audit, "advisor", True)
            wait_for_pg_lock(audit.engine)
        finally:
            release.set()
        checked(one.result(timeout=10))
        checked(two.result(timeout=10), 409, "INVALID_FOLLOW_UP_TRANSITION")
    with audit.engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM follow_ups")) == 2


@pytest.mark.parametrize("first_operation", ["assignment", "deactivation"])
def test_assignment_and_deactivation_target_lock_preserves_guard(
    audit, monkeypatch, first_operation
):
    target = audit.ids["spare"]
    ready, release = pause_locked_read(
        monkeypatch, UserRepository, "lock_by_id", target
    )

    def assign():
        return audit.client.patch(
            f"/api/v1/warnings/{audit.ids['warning']}/assignment",
            headers=audit.headers["academic"],
            json={"assigned_to": target},
        )

    def deactivate():
        return audit.client.post(
            f"/api/v1/users/{target}/deactivate", headers=audit.headers["system"]
        )

    winner, loser = (
        (assign, deactivate)
        if first_operation == "assignment"
        else (deactivate, assign)
    )
    with (
        ThreadPoolExecutor(max_workers=1, thread_name_prefix="c1_first") as first,
        ThreadPoolExecutor(max_workers=1, thread_name_prefix="c1_second") as second,
    ):
        one = first.submit(winner)
        try:
            assert ready.wait(5)
            two = second.submit(loser)
            wait_for_pg_lock(audit.engine)
        finally:
            release.set()
        checked(one.result(timeout=10))
        checked(
            two.result(timeout=10),
            409 if first_operation == "assignment" else 422,
            "ADVISOR_HAS_ACTIVE_ASSIGNMENTS"
            if first_operation == "assignment"
            else "INVALID_WARNING_ASSIGNEE",
        )


@pytest.mark.parametrize("first_operation", ["review", "assignment"])
def test_warning_assignment_and_review_share_a_real_parent_lock(
    audit, monkeypatch, first_operation
):
    ready, release = pause_locked_read(
        monkeypatch, WarningRepository, "get", audit.ids["warning"]
    )

    def review():
        return audit.client.post(
            f"/api/v1/warnings/{audit.ids['warning']}/reviews",
            headers=audit.headers["advisor"],
            json={"decision": "DISMISSED", "note": "Concurrent decision"},
        )

    def assign():
        return audit.client.patch(
            f"/api/v1/warnings/{audit.ids['warning']}/assignment",
            headers=audit.headers["academic"],
            json={"assigned_to": audit.ids["other"]},
        )

    winner, loser = (
        (review, assign) if first_operation == "review" else (assign, review)
    )
    with (
        ThreadPoolExecutor(max_workers=1, thread_name_prefix="c1_first") as first,
        ThreadPoolExecutor(max_workers=1, thread_name_prefix="c1_second") as second,
    ):
        one = first.submit(winner)
        try:
            assert ready.wait(5)
            two = second.submit(loser)
            wait_for_pg_lock(audit.engine)
        finally:
            release.set()
        checked(one.result(timeout=10), 201 if first_operation == "review" else 200)
        checked(
            two.result(timeout=10),
            200 if first_operation == "review" else 403,
            None
            if first_operation == "review"
            else "WARNING_ASSIGNED_TO_DIFFERENT_ADVISOR",
        )


@pytest.mark.parametrize("change", ["deactivate", "role"])
def test_already_authorized_casework_write_survives_actor_revocation(
    audit, monkeypatch, change
):
    ready, release = pause_locked_read(
        monkeypatch, CaseworkRepository, "intervention", audit.ids["intervention"]
    )
    target = audit.ids["academic"]
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="c1_first") as pool:
        future = pool.submit(
            audit.client.patch,
            f"/api/v1/interventions/{audit.ids['intervention']}",
            headers=audit.headers["academic"],
            json={"title": "Write after revocation"},
        )
        try:
            assert ready.wait(5)  # Endpoint authentication already passed.
            response = (
                audit.client.post(
                    f"/api/v1/users/{target}/deactivate",
                    headers=audit.headers["system"],
                )
                if change == "deactivate"
                else audit.client.patch(
                    f"/api/v1/users/{target}",
                    headers=audit.headers["system"],
                    json={"role": "SYSTEM_ADMIN"},
                )
            )
            checked(response)
        finally:
            release.set()
        assert checked(future.result(timeout=10))["title"] == "Write after revocation"
    checked(
        audit.client.get(
            f"/api/v1/interventions/{audit.ids['intervention']}",
            headers=audit.headers["academic"],
        ),
        401,
        "AUTHENTICATION_REQUIRED",
    )
    with audit.engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM user_administration_audit")) == 1


def test_assignment_and_terminal_actions_have_no_structured_casework_audit(audit):
    checked(transfer(audit))
    checked(
        audit.client.patch(
            f"/api/v1/follow-ups/{audit.ids['follow_up']}",
            headers=audit.headers["academic"],
            json={"assigned_to": audit.ids["other"]},
        )
    )
    checked(fu(audit, "other"))
    checked(
        audit.client.post(
            f"/api/v1/interventions/{audit.ids['intervention']}/complete",
            headers=audit.headers["academic"],
            json={"outcome": "SUPPORT_COMPLETED", "completion_notes": "Audit evidence"},
        )
    )
    with audit.engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM user_administration_audit")) == 0
        assert db.scalar(text("SELECT count(*) FROM warning_reviews")) == 1
        assert db.scalar(text("SELECT count(*) FROM intervention_notes")) == 0
        prediction = db.execute(
            text("SELECT probability, feature_snapshot FROM prediction_results")
        ).one()
        assert prediction.probability == 0.8 and prediction.feature_snapshot == {}
