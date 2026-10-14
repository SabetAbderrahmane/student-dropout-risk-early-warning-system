"""C1 regression acceptance on real disposable PostgreSQL databases.

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
from alembic import command
from alembic.config import Config
from app.core.config import get_settings
from app.core.security import create_access_token, hash_password
from app.db.session import get_db
from app.main import app
from app.models import ModelVersion, PredictionResult, Student, User, UserRole, Warning
from app.repositories.casework_repository import CaseworkRepository
from app.repositories.user_repository import UserRepository
from app.repositories.warning_repository import WarningRepository
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

pytestmark = pytest.mark.model_integration
FIXTURE_PASSWORD_HASH = hash_password("CaseworkFixture!42")


@pytest.fixture(autouse=True)
def isolated_model_runtime():
    # Override the suite's synthetic-training autouse fixture: this is casework
    # auditing only, and the user explicitly prohibited retraining models.
    yield


class AuditContext(SimpleNamespace):
    def __repr__(self):
        return "<Disposable PostgreSQL casework fixture>"


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
                == "20261014_0012"
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
                    password_hash=FIXTURE_PASSWORD_HASH,
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
        env = AuditContext(engine=engine, client=client, ids=ids, headers=headers)
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


def case(audit):
    return checked(
        audit.client.get(
            f"/api/v1/interventions/{audit.ids['intervention']}",
            headers=audit.headers["academic"],
        )
    )


def contact(audit):
    return checked(
        audit.client.get(
            f"/api/v1/follow-ups/{audit.ids['follow_up']}",
            headers=audit.headers["academic"],
        )
    )


def transfer(audit, expected=None):
    return audit.client.post(
        f"/api/v1/interventions/{audit.ids['intervention']}/transfer",
        headers=audit.headers["academic"],
        json={
            "assigned_to": audit.ids["other"],
            "reason": "Transfer support",
            "expected_revision": case(audit)["revision"]
            if expected is None
            else expected,
        },
    )


def reconsider(audit, decision="DISMISSED", role="advisor", expected=None):
    warning = checked(
        audit.client.get(
            f"/api/v1/warnings/{audit.ids['warning']}",
            headers=audit.headers["academic"],
        )
    )
    return audit.client.post(
        f"/api/v1/warnings/{audit.ids['warning']}/reconsider",
        headers=audit.headers[role],
        json={
            "decision": decision,
            "note": "New human decision",
            "reason": "New evidence",
            "expected_revision": warning["revision"] if expected is None else expected,
        },
    )


def legacy(audit, *, terminal=False, mismatch=False, dismissed=False):
    # Explicit historical fixtures, never a production cleanup path.
    with audit.engine.begin() as db:
        if terminal:
            db.execute(
                text(
                    "UPDATE interventions SET status='CANCELLED', completion_notes='Historical cancellation' WHERE id=:id"
                ),
                {"id": audit.ids["intervention"]},
            )
        if mismatch:
            db.execute(
                text("UPDATE follow_ups SET assigned_to=:owner WHERE id=:id"),
                {"owner": audit.ids["other"], "id": audit.ids["follow_up"]},
            )
        if dismissed:
            db.execute(
                text("UPDATE warnings SET review_state='DISMISSED' WHERE id=:id"),
                {"id": audit.ids["warning"]},
            )


def recover(audit, action="ALIGN", role="academic", **extra):
    return audit.client.post(
        f"/api/v1/follow-ups/{audit.ids['follow_up']}/recover",
        headers=audit.headers[role],
        json={
            "action": action,
            "reason": "Verified historical obligation",
            "expected_revision": contact(audit)["revision"],
            **extra,
        },
    )


def test_atomic_transfer_preserves_terminal_history_and_authorization(audit):
    # Stored SCHEDULED spans future, due and overdue dates.
    for offset in (-2, 0, 3):
        payload = follow_payload(audit)
        payload["scheduled_for"] = (
            datetime.now(UTC) + timedelta(days=offset)
        ).isoformat()
        checked(
            audit.client.post(
                f"/api/v1/interventions/{audit.ids['intervention']}/follow-ups",
                headers=audit.headers["academic"],
                json=payload,
            ),
            201,
        )
    cancelled = checked(
        audit.client.post(
            f"/api/v1/interventions/{audit.ids['intervention']}/follow-ups",
            headers=audit.headers["academic"],
            json=follow_payload(audit),
        ),
        201,
    )
    cancelled = checked(
        audit.client.post(
            f"/api/v1/follow-ups/{cancelled['id']}/cancel",
            headers=audit.headers["academic"],
            json={"reason": "Historical cancelled appointment"},
        )
    )
    historical_id = audit.ids["follow_up"]
    historical = checked(fu(audit))
    before = case(audit)
    transferred = checked(transfer(audit))
    assert transferred["revision"] == before["revision"] + 1
    for row in transferred["follow_ups"]:
        if row["id"] in (historical_id, cancelled["id"]):
            terminal_record = historical if row["id"] == historical_id else cancelled
            assert {
                key: value for key, value in row.items() if key != "parent_assigned_to"
            } == {
                key: value
                for key, value in terminal_record.items()
                if key != "parent_assigned_to"
            }
        else:
            original = next(
                item for item in before["follow_ups"] if item["id"] == row["id"]
            )
            assert row["assigned_advisor"]["id"] == audit.ids["other"]
            assert row["revision"] == original["revision"] + 1
            assert row["created_by"] == original["created_by"]
    scheduled = next(
        item
        for item in transferred["follow_ups"]
        if item["stored_status"] == "SCHEDULED"
    )
    audit.ids["follow_up"] = scheduled["id"]
    checked(fu(audit, "advisor"), 403, "FOLLOW_UP_ASSIGNED_TO_DIFFERENT_ADVISOR")
    checked(fu(audit, "other"))
    with audit.engine.connect() as db:
        events = (
            db.execute(
                text(
                    "SELECT * FROM casework_action_audit WHERE action='TRANSFER_INTERVENTION'"
                )
            )
            .mappings()
            .all()
        )
        assert len(events) == 4 and len({row["correlation_id"] for row in events}) == 1
        assert all(
            str(row["actor_id"]) == audit.ids["academic"]
            and row["reason"] == "Transfer support"
            for row in events
        )
        assert all(
            row["before_values"]["assigned_to"] == audit.ids["advisor"]
            and row["after_values"]["assigned_to"] == audit.ids["other"]
            for row in events
        )
        assert db.scalar(text("SELECT probability FROM prediction_results")) == 0.8


def test_transfer_rejects_stale_invalid_targets_and_patch_bypass(audit):
    revision = case(audit)["revision"]
    checked(transfer(audit, revision - 1), 409, "STALE_RESOURCE_REVISION")
    checked(
        audit.client.patch(
            f"/api/v1/interventions/{audit.ids['intervention']}",
            headers=audit.headers["academic"],
            json={"assigned_to": audit.ids["other"]},
        ),
        409,
        "EXPLICIT_TRANSFER_REQUIRED",
    )
    for role in ("advisor", "system"):
        checked(
            audit.client.post(
                f"/api/v1/interventions/{audit.ids['intervention']}/transfer",
                headers=audit.headers[role],
                json={
                    "assigned_to": audit.ids["other"],
                    "reason": "Transfer",
                    "expected_revision": revision,
                },
            ),
            403,
            "INSUFFICIENT_PERMISSIONS",
        )
    for body in (
        {"reason": " "},
        {"assigned_to": audit.ids["system"]},
        {"assigned_to": audit.ids["advisor"]},
    ):
        response = audit.client.post(
            f"/api/v1/interventions/{audit.ids['intervention']}/transfer",
            headers=audit.headers["academic"],
            json={
                "assigned_to": audit.ids["other"],
                "reason": "Transfer",
                "expected_revision": revision,
                **body,
            },
        )
        assert response.status_code in (409, 422), response.text
    assert case(audit)["revision"] == revision


def test_independent_delegation_and_child_patch_rejected(audit):
    checked(
        audit.client.post(
            f"/api/v1/interventions/{audit.ids['intervention']}/follow-ups",
            headers=audit.headers["academic"],
            json=follow_payload(audit, "other"),
        ),
        409,
        "INDEPENDENT_FOLLOW_UP_DELEGATION",
    )
    checked(
        audit.client.patch(
            f"/api/v1/follow-ups/{audit.ids['follow_up']}",
            headers=audit.headers["academic"],
            json={"assigned_to": audit.ids["other"]},
        ),
        409,
        "EXPLICIT_RECOVERY_REQUIRED",
    )


def test_explicit_reconsideration_blocks_dismissal_until_support_resolved(audit):
    checked(
        audit.client.post(
            f"/api/v1/warnings/{audit.ids['warning']}/reviews",
            headers=audit.headers["advisor"],
            json={"decision": "DISMISSED", "note": "Repeated review"},
        ),
        409,
        "EXPLICIT_RECONSIDERATION_REQUIRED",
    )
    blocked = checked(reconsider(audit), 409, "WARNING_HAS_ACTIVE_SUPPORT")["error"][
        "details"
    ]
    assert blocked == {
        "interventions": 1,
        "intervention_ids": [audit.ids["intervention"]],
        "follow_ups": 1,
        "follow_up_ids": [audit.ids["follow_up"]],
    }
    checked(
        reconsider(audit, role="other"), 403, "WARNING_ASSIGNED_TO_DIFFERENT_ADVISOR"
    )
    checked(reconsider(audit, expected=0), 409, "STALE_RESOURCE_REVISION")
    checked(fu(audit))
    checked(close_case(audit, "cancel"))
    dismissed = checked(reconsider(audit), 201)
    assert (
        dismissed["review_state"] == "DISMISSED"
        and len(dismissed["review_history"]) == 2
    )
    reconfirmed = checked(reconsider(audit, "CONFIRMED"), 201)
    assert len(reconfirmed["review_history"]) == 3
    with audit.engine.connect() as db:
        assert (
            db.scalar(
                text(
                    "SELECT count(*) FROM casework_action_audit WHERE action='RECONSIDER'"
                )
            )
            == 2
        )
    # Reconfirmation permits future cases without rewriting previous support.
    checked(create_case(audit), 201)


@pytest.mark.parametrize("terminal", ["complete", "cancel"])
def test_strict_closure_requires_explicit_follow_up_resolution(audit, terminal):
    details = checked(
        close_case(audit, terminal), 409, "INTERVENTION_HAS_SCHEDULED_FOLLOW_UPS"
    )["error"]["details"]
    assert details == {"follow_ups": 1, "follow_up_ids": [audit.ids["follow_up"]]}
    checked(fu(audit))
    assert case(audit)["status"] == "PLANNED"
    checked(close_case(audit, terminal))
    checked(
        audit.client.post(
            f"/api/v1/interventions/{audit.ids['intervention']}/follow-ups",
            headers=audit.headers["advisor"],
            json=follow_payload(audit),
        ),
        409,
        "INVALID_FOLLOW_UP_TRANSITION",
    )


@pytest.mark.parametrize(
    "status", ["PLANNED", "IN_PROGRESS", "ACTION_REQUIRED", "COMPLETED", "CANCELLED"]
)
def test_direct_and_successor_share_parent_lifecycle_gate(audit, status):
    with audit.engine.begin() as db:
        db.execute(
            text(
                "UPDATE interventions SET status=CAST(:status AS intervention_status), completed_at=CASE WHEN CAST(:status AS text)='COMPLETED' THEN now() ELSE NULL END, completion_outcome=CASE WHEN CAST(:status AS text)='COMPLETED' THEN 'SUPPORT_COMPLETED'::intervention_outcome ELSE NULL END, completion_notes='Historical evidence'"
            ),
            {"status": status},
        )
    terminal = status in {"COMPLETED", "CANCELLED"}
    direct = audit.client.post(
        f"/api/v1/interventions/{audit.ids['intervention']}/follow-ups",
        headers=audit.headers["advisor"],
        json=follow_payload(audit),
    )
    successor = fu(audit, next_item=True)
    checked(
        direct,
        409 if terminal else 201,
        "INVALID_FOLLOW_UP_TRANSITION" if terminal else None,
    )
    checked(
        successor,
        409 if terminal else 200,
        "INVALID_FOLLOW_UP_TRANSITION" if terminal else None,
    )
    assert case(audit)["status"] == status


@pytest.mark.parametrize("action", ["ALIGN", "COMPLETE", "CANCEL"])
def test_audited_narrow_recovery_and_legacy_visibility(audit, action):
    legacy(audit, terminal=action != "ALIGN", mismatch=True, dismissed=True)
    original_case = case(audit)
    original_contact = contact(audit)
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
    diagnostic = checked(
        audit.client.get("/api/v1/casework/integrity", headers=audit.headers["system"])
    )
    assert diagnostic[0]["id"] == audit.ids["follow_up"]
    checked(recover(audit, action, role="advisor"), 403, "INSUFFICIENT_PERMISSIONS")
    checked(fu(audit, "academic"), 409, "CASEWORK_RECOVERY_REQUIRED")
    if action == "ALIGN":
        checked(recover(audit, "CANCEL"), 409, "INVALID_RECOVERY_ACTION")
    else:
        checked(recover(audit, "ALIGN"), 409, "INVALID_FOLLOW_UP_TRANSITION")
        checked(reconsider(audit), 409, "WARNING_HAS_ACTIVE_SUPPORT")
    extra = (
        {"outcome": "PROGRESS_OBSERVED", "notes": "Actual recorded attendance"}
        if action == "COMPLETE"
        else {}
    )
    resolved = checked(recover(audit, action, **extra))
    assert resolved["revision"] == original_contact["revision"] + 1
    assert resolved["created_by"] == original_contact["created_by"]
    assert case(audit)["assigned_advisor"] == original_case["assigned_advisor"]
    assert case(audit)["status"] == original_case["status"]
    assert (
        checked(
            audit.client.get(
                "/api/v1/casework/integrity", headers=audit.headers["academic"]
            )
        )
        == []
    )
    with audit.engine.connect() as db:
        event = (
            db.execute(
                text(
                    "SELECT * FROM casework_action_audit WHERE action='RECOVER_FOLLOW_UP'"
                )
            )
            .mappings()
            .one()
        )
        assert event["before_values"]["assigned_to"] == audit.ids["other"]
        assert event["reason"] == "Verified historical obligation"
        assert db.scalar(text("SELECT count(*) FROM follow_ups")) == 1


@pytest.mark.parametrize("retained", ["warning", "intervention", "follow_up"])
@pytest.mark.parametrize("change", ["deactivate", "role"])
def test_each_existing_assignment_safeguard_is_preserved(audit, retained, change):
    with audit.engine.begin() as db:
        if retained != "warning":
            db.execute(text("UPDATE warnings SET review_state='DISMISSED'"))
        if retained != "intervention":
            db.execute(
                text(
                    "UPDATE interventions SET status='CANCELLED', completion_notes='Historical cancellation'"
                )
            )
        if retained != "follow_up":
            db.execute(
                text(
                    "UPDATE follow_ups SET status='CANCELLED', notes='Explicitly resolved'"
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
    checked(fu(audit))
    checked(close_case(audit, "cancel"))
    checked(reconsider(audit), 201)
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


def create_case(audit):
    return audit.client.post(
        "/api/v1/interventions",
        headers=audit.headers["academic"],
        json={
            "student_id": audit.ids["student"],
            "warning_id": audit.ids["warning"],
            "type": "ACADEMIC_TUTORING",
            "title": "Further support",
            "description": "New plan",
            "priority": "P1_URGENT",
            "assigned_to": audit.ids["advisor"],
            "start_date": "2026-10-14",
        },
    )


def race(audit, monkeypatch, winner, loser, repository, method, identifier):
    ready, release = pause_locked_read(monkeypatch, repository, method, identifier)
    with ThreadPoolExecutor(max_workers=2) as pool:
        one = pool.submit(winner)
        try:
            assert ready.wait(5), "Winner never acquired its transaction lock"
            two = pool.submit(loser)
            wait_for_pg_lock(audit.engine)
        finally:
            release.set()
        return one.result(timeout=10), two.result(timeout=10)


@pytest.mark.parametrize("child_action", ["edit", "complete", "cancel", "successor"])
@pytest.mark.parametrize("first", ["child", "transfer"])
def test_transfer_and_child_actions_serialize_both_orders(
    audit, monkeypatch, child_action, first
):
    def child():
        path = f"/api/v1/follow-ups/{audit.ids['follow_up']}"
        if child_action == "edit":
            return audit.client.patch(
                path,
                headers=audit.headers["advisor"],
                json={"purpose": "Updated obligation"},
            )
        if child_action == "cancel":
            return audit.client.post(
                path + "/cancel",
                headers=audit.headers["advisor"],
                json={"reason": "Resolved"},
            )
        return fu(audit, next_item=child_action == "successor")

    winner, loser = (
        (child, lambda: transfer(audit))
        if first == "child"
        else (lambda: transfer(audit), child)
    )
    one, two = race(
        audit,
        monkeypatch,
        winner,
        loser,
        CaseworkRepository,
        "intervention",
        audit.ids["intervention"],
    )
    checked(one)
    checked(
        two,
        409 if first == "child" else 403,
        "STALE_RESOURCE_REVISION"
        if first == "child"
        else "FOLLOW_UP_ASSIGNED_TO_DIFFERENT_ADVISOR",
    )
    if first == "child":
        # Explicit new submission after the stale form was rejected.
        checked(transfer(audit))
    result = case(audit)
    assert result["assigned_advisor"]["id"] == audit.ids["other"]
    assert all(
        row["assigned_advisor"]["id"] == audit.ids["other"]
        for row in result["follow_ups"]
        if row["stored_status"] == "SCHEDULED"
    )


@pytest.mark.parametrize("scheduling", ["direct", "successor"])
@pytest.mark.parametrize("first", ["closure", "scheduling"])
def test_closure_and_scheduling_serialize_both_orders(
    audit, monkeypatch, scheduling, first
):
    # Successor needs an existing pending obligation, so strict closure must fail.
    if scheduling == "direct":
        checked(fu(audit))

    def schedule():
        return (
            fu(audit, next_item=True)
            if scheduling == "successor"
            else audit.client.post(
                f"/api/v1/interventions/{audit.ids['intervention']}/follow-ups",
                headers=audit.headers["advisor"],
                json=follow_payload(audit),
            )
        )

    def close():
        return close_case(audit, "cancel")

    winner, loser = (close, schedule) if first == "closure" else (schedule, close)
    one, two = race(
        audit,
        monkeypatch,
        winner,
        loser,
        CaseworkRepository,
        "intervention",
        audit.ids["intervention"],
    )
    if scheduling == "direct" and first == "closure":
        checked(one)
        checked(two, 409, "INVALID_FOLLOW_UP_TRANSITION")
    elif first == "closure":
        checked(one, 409, "INTERVENTION_HAS_SCHEDULED_FOLLOW_UPS")
        checked(two)
    else:
        checked(one, 201 if scheduling == "direct" else 200)
        checked(two, 409, "INTERVENTION_HAS_SCHEDULED_FOLLOW_UPS")


@pytest.mark.parametrize("action", ["complete", "cancel"])
def test_competing_terminal_child_actions(audit, monkeypatch, action):
    def cancel():
        return audit.client.post(
            f"/api/v1/follow-ups/{audit.ids['follow_up']}/cancel",
            headers=audit.headers["advisor"],
            json={"reason": "Resolved"},
        )

    winner = (lambda: fu(audit, next_item=True)) if action == "complete" else cancel
    one, two = race(
        audit,
        monkeypatch,
        winner,
        lambda: fu(audit, next_item=True),
        CaseworkRepository,
        "follow_up",
        audit.ids["follow_up"],
    )
    checked(one)
    checked(two, 409, "INVALID_FOLLOW_UP_TRANSITION")
    with audit.engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM follow_ups")) == (
            2 if action == "complete" else 1
        )


@pytest.mark.parametrize("first", ["review", "assignment"])
def test_warning_assignment_and_review_serialize(audit, monkeypatch, first):
    # Restore a pending historical fixture for the initial review action.
    with audit.engine.begin() as db:
        db.execute(text("UPDATE warnings SET review_state='PENDING_REVIEW'"))

    def review():
        return audit.client.post(
            f"/api/v1/warnings/{audit.ids['warning']}/reviews",
            headers=audit.headers["advisor"],
            json={"decision": "CONFIRMED", "note": "Concurrent review"},
        )

    def assign():
        return audit.client.patch(
            f"/api/v1/warnings/{audit.ids['warning']}/assignment",
            headers=audit.headers["academic"],
            json={"assigned_to": audit.ids["other"]},
        )

    one, two = race(
        audit,
        monkeypatch,
        review if first == "review" else assign,
        assign if first == "review" else review,
        WarningRepository,
        "get",
        audit.ids["warning"],
    )
    checked(one, 201 if first == "review" else 200)
    checked(
        two,
        200 if first == "review" else 403,
        None if first == "review" else "WARNING_ASSIGNED_TO_DIFFERENT_ADVISOR",
    )


@pytest.mark.parametrize("first", ["dismiss", "create"])
def test_dismissal_and_case_creation_serialize(audit, monkeypatch, first):
    checked(fu(audit))
    checked(close_case(audit, "cancel"))
    dismiss = lambda: reconsider(audit)
    create = lambda: create_case(audit)
    one, two = race(
        audit,
        monkeypatch,
        dismiss if first == "dismiss" else create,
        create if first == "dismiss" else dismiss,
        WarningRepository,
        "get",
        audit.ids["warning"],
    )
    checked(one, 201)
    checked(
        two,
        409,
        "INTERVENTION_REQUIRES_CONFIRMED_WARNING"
        if first == "dismiss"
        else "STALE_RESOURCE_REVISION",
    )


@pytest.mark.parametrize("change", ["deactivate", "role", "reset"])
@pytest.mark.parametrize("first", ["assignment", "account"])
def test_assignment_and_account_changes_serialize(audit, monkeypatch, change, first):
    target = audit.ids["spare"]
    assign = lambda: audit.client.patch(
        f"/api/v1/warnings/{audit.ids['warning']}/assignment",
        headers=audit.headers["academic"],
        json={"assigned_to": target},
    )
    account = lambda: account_change(audit, target, change)
    one, two = race(
        audit,
        monkeypatch,
        assign if first == "assignment" else account,
        account if first == "assignment" else assign,
        UserRepository,
        "lock_by_id",
        target,
    )
    checked(one)
    if change == "reset":
        checked(two)  # Password reset does not demote/deactivate an assignment target.
    else:
        checked(
            two,
            409 if first == "assignment" else 422,
            "ADVISOR_HAS_ACTIVE_ASSIGNMENTS"
            if first == "assignment"
            else "INVALID_WARNING_ASSIGNEE",
        )


def account_change(audit, target, change):
    if change == "deactivate":
        return audit.client.post(
            f"/api/v1/users/{target}/deactivate", headers=audit.headers["system"]
        )
    if change == "reset":
        return audit.client.post(
            f"/api/v1/users/{target}/reset-password",
            headers=audit.headers["system"],
            json={"temporary_password": "NewTemporaryPassword!42"},
        )
    return audit.client.patch(
        f"/api/v1/users/{target}",
        headers=audit.headers["system"],
        json={"role": "SYSTEM_ADMIN"},
    )


@pytest.mark.parametrize("change", ["deactivate", "role", "reset"])
@pytest.mark.parametrize("write", ["case", "child", "review"])
@pytest.mark.parametrize("first", ["casework", "account"])
def test_authenticated_writes_and_revocation_ordering(
    audit, monkeypatch, change, write, first
):
    if write == "review":
        checked(fu(audit))
        checked(close_case(audit, "cancel"))
        checked(reconsider(audit), 201)
    role = "advisor" if write == "review" else "academic"
    target = audit.ids[role]

    def work():
        if write == "review":
            return reconsider(audit, "CONFIRMED")
        if write == "child":
            return fu(audit, role="academic")
        return audit.client.patch(
            f"/api/v1/interventions/{audit.ids['intervention']}",
            headers=audit.headers["academic"],
            json={"title": "Guarded mutation"},
        )

    if first == "casework":
        repo, method, identifier = (WarningRepository, "get", audit.ids["warning"])
        one, two = race(
            audit,
            monkeypatch,
            work,
            lambda: account_change(audit, target, change),
            repo,
            method,
            identifier,
        )
        checked(one, 201 if write == "review" else 200)
        if write == "review" and change != "reset":
            checked(two, 409, "ADVISOR_HAS_ACTIVE_ASSIGNMENTS")
        else:
            checked(two)
    else:
        # Pause request AFTER authentication but BEFORE guard entry, then revoke.
        # This gate does not hold the mutex or replace service results.
        from app.services.casework_mutation import Mutation

        ready, release = Event(), Event()
        original = Mutation.__init__

        def delayed(self, service, action, actor, *args, **kwargs):
            if str(actor.id) == target and action in {
                "update_intervention",
                "complete_follow_up",
                "reconsider",
            }:
                ready.set()
                assert release.wait(8)
            return original(self, service, action, actor, *args, **kwargs)

        monkeypatch.setattr(Mutation, "__init__", delayed)
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(work)
            try:
                assert ready.wait(5)
                result = account_change(audit, target, change)
                checked(result)
            finally:
                release.set()
            response = pending.result(timeout=10)
            checked(response, 401, "AUTHENTICATION_REQUIRED")


def test_transfer_rollback_includes_revisions_assignments_and_events(
    audit, monkeypatch
):
    from app.models import CaseworkActionAudit
    from sqlalchemy import event

    checked(
        audit.client.post(
            f"/api/v1/interventions/{audit.ids['intervention']}/follow-ups",
            headers=audit.headers["academic"],
            json=follow_payload(audit),
        ),
        201,
    )
    before = case(audit)
    with audit.engine.connect() as db:
        count = db.scalar(text("SELECT count(*) FROM casework_action_audit"))

    def fail(session, *_):
        if any(
            isinstance(row, CaseworkActionAudit)
            and row.action == "TRANSFER_INTERVENTION"
            for row in session.new
        ):
            raise RuntimeError("Injected audit persistence failure")

    event.listen(Session, "before_flush", fail)
    try:
        with pytest.raises(RuntimeError, match="Injected"):
            transfer(audit)
    finally:
        event.remove(Session, "before_flush", fail)
    assert case(audit) == before
    with audit.engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM casework_action_audit")) == count


def test_populated_migration_roundtrip_preserves_domain_history(audit):
    tables = [
        "warnings",
        "warning_reviews",
        "interventions",
        "follow_ups",
        "prediction_results",
    ]

    def snapshot():
        with audit.engine.connect() as db:
            return {
                table: [
                    {key: value for key, value in row.items() if key != "revision"}
                    for row in db.execute(
                        text(f"SELECT * FROM {table} ORDER BY id")
                    ).mappings()
                ]
                for table in tables
            }

    before = snapshot()
    # Downgrade intentionally discards only new C1 revisions/events, never history.
    command.downgrade(Config("alembic.ini"), "20261013_0011")
    assert snapshot() == before
    command.upgrade(Config("alembic.ini"), "head")
    assert snapshot() == before
    with audit.engine.connect() as db:
        for table in ("warnings", "interventions", "follow_ups"):
            assert db.scalar(text(f"SELECT max(revision) FROM {table}")) == 0
        assert db.scalar(text("SELECT count(*) FROM casework_action_audit")) == 0


def test_structured_action_history_retains_existing_audits(audit):
    checked(transfer(audit))
    checked(fu(audit, "other"))
    checked(
        audit.client.post(
            f"/api/v1/interventions/{audit.ids['intervention']}/complete",
            headers=audit.headers["academic"],
            json={
                "outcome": "SUPPORT_COMPLETED",
                "completion_notes": "Genuine evidence",
            },
        )
    )
    with audit.engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM user_administration_audit")) == 0
        assert db.scalar(text("SELECT count(*) FROM warning_reviews")) == 1
        assert db.scalar(text("SELECT count(*) FROM intervention_notes")) == 0
        assert db.scalar(text("SELECT count(*) FROM casework_action_audit")) >= 8
        assert db.scalar(text("SELECT probability FROM prediction_results")) == 0.8


@pytest.mark.parametrize(
    "field,value,status,code",
    [
        ("role", "SYSTEM_ADMIN", 403, "INSUFFICIENT_PERMISSIONS"),
        ("must_change_password", True, 403, "PASSWORD_CHANGE_REQUIRED"),
        ("is_active", False, 401, "AUTHENTICATION_REQUIRED"),
    ],
)
def test_guard_refreshes_actor_fields_even_without_token_increment(
    audit, monkeypatch, field, value, status, code
):
    from app.services.casework_mutation import Mutation

    ready, release = Event(), Event()
    original = Mutation.__init__

    def delayed(self, *args, **kwargs):
        ready.set()
        assert release.wait(8)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Mutation, "__init__", delayed)
    before = case(audit)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            audit.client.patch,
            f"/api/v1/interventions/{audit.ids['intervention']}",
            headers=audit.headers["academic"],
            json={"title": "Must not commit"},
        )
        try:
            assert ready.wait(5)
            # Simulate a legacy account writer that did not increment token version.
            with audit.engine.begin() as db:
                db.execute(
                    text(f"UPDATE users SET {field}=:value WHERE id=:id"),
                    {"value": value, "id": audit.ids["academic"]},
                )
        finally:
            release.set()
        checked(future.result(timeout=10), status, code)
    after = checked(
        audit.client.get(
            f"/api/v1/interventions/{audit.ids['intervention']}",
            headers=audit.headers["system"],
        )
    )
    assert before == after


@pytest.mark.parametrize("child_action", ["complete", "cancel"])
@pytest.mark.parametrize("first", ["closure", "child"])
def test_closure_and_child_resolution_serialize(
    audit, monkeypatch, child_action, first
):
    close = lambda: close_case(audit, "complete")
    child = (
        (lambda: fu(audit))
        if child_action == "complete"
        else lambda: audit.client.post(
            f"/api/v1/follow-ups/{audit.ids['follow_up']}/cancel",
            headers=audit.headers["advisor"],
            json={"reason": "Resolved"},
        )
    )
    one, two = race(
        audit,
        monkeypatch,
        close if first == "closure" else child,
        child if first == "closure" else close,
        CaseworkRepository,
        "intervention",
        audit.ids["intervention"],
    )
    checked(
        one,
        409 if first == "closure" else 200,
        "INTERVENTION_HAS_SCHEDULED_FOLLOW_UPS" if first == "closure" else None,
    )
    checked(two)
    if first == "closure":
        checked(close())
    assert case(audit)["status"] == "COMPLETED"


@pytest.mark.parametrize("first", ["recovery", "completion"])
def test_recovery_and_completion_serialize(audit, monkeypatch, first):
    legacy(audit, mismatch=True)
    align = lambda: recover(audit)
    complete = lambda: fu(audit, "academic")
    one, two = race(
        audit,
        monkeypatch,
        align if first == "recovery" else complete,
        complete if first == "recovery" else align,
        CaseworkRepository,
        "intervention",
        audit.ids["intervention"],
    )
    checked(
        one,
        200 if first == "recovery" else 409,
        None if first == "recovery" else "CASEWORK_RECOVERY_REQUIRED",
    )
    checked(two)


def test_lock_timeout_is_retryable_without_partial_changes(audit):
    before = case(audit)
    with audit.engine.connect() as blocker:
        blocker.execute(text("SELECT pg_advisory_xact_lock(610110009)"))
        with ThreadPoolExecutor(max_workers=1) as pool:
            response = pool.submit(transfer, audit).result(timeout=9)
        details = checked(response, 409, "CASEWORK_RETRYABLE_CONFLICT")["error"][
            "details"
        ]
        assert details == {"retryable": True}
        blocker.rollback()
    assert case(audit) == before
    with audit.engine.connect() as db:
        assert (
            db.scalar(
                text(
                    "SELECT count(*) FROM casework_action_audit WHERE action='TRANSFER_INTERVENTION'"
                )
            )
            == 0
        )


def test_recovery_requires_version_genuine_outcome_and_no_successor(audit):
    legacy(audit, terminal=True)
    checked(recover(audit, "COMPLETE"), 422, "RECOVERY_OUTCOME_REQUIRED")
    checked(
        recover(audit, "CANCEL", expected_revision=0), 409, "STALE_RESOURCE_REVISION"
    )
    checked(
        recover(audit, "CANCEL", next_follow_up_at=datetime.now(UTC).isoformat()),
        422,
        "VALIDATION_ERROR",
    )
    assert contact(audit)["stored_status"] == "SCHEDULED"
    with audit.engine.connect() as db:
        assert (
            db.scalar(
                text(
                    "SELECT count(*) FROM casework_action_audit WHERE action='RECOVER_FOLLOW_UP'"
                )
            )
            == 0
        )


def test_postgres_completion_successor_and_audit_rollback(audit):
    from app.models import CaseworkActionAudit
    from sqlalchemy import event

    before = case(audit)

    def fail(session, *_):
        if any(
            isinstance(item, CaseworkActionAudit)
            and item.action == "COMPLETE_FOLLOW_UP"
            for item in session.new
        ):
            raise RuntimeError("Successor audit rollback")

    event.listen(Session, "before_flush", fail)
    try:
        with pytest.raises(RuntimeError, match="Successor audit rollback"):
            fu(audit, next_item=True)
    finally:
        event.remove(Session, "before_flush", fail)
    assert case(audit) == before
    with audit.engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM follow_ups")) == 1
        assert (
            db.scalar(
                text(
                    "SELECT count(*) FROM casework_action_audit WHERE action='COMPLETE_FOLLOW_UP'"
                )
            )
            == 0
        )


def test_initial_review_dismissal_also_blocks_historical_support(audit):
    with audit.engine.begin() as db:
        db.execute(text("UPDATE warnings SET review_state='PENDING_REVIEW'"))
    checked(
        audit.client.post(
            f"/api/v1/warnings/{audit.ids['warning']}/reviews",
            headers=audit.headers["advisor"],
            json={
                "decision": "DISMISSED",
                "note": "Initial dismissal with historical support",
            },
        ),
        409,
        "WARNING_HAS_ACTIVE_SUPPORT",
    )
    with audit.engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM warning_reviews")) == 1
        assert (
            db.scalar(
                text("SELECT count(*) FROM casework_action_audit WHERE action='REVIEW'")
            )
            == 1
        )
