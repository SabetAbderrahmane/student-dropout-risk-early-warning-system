"""D1.1 transaction authorization regressions on disposable PostgreSQL.

Real login, HTTP role/account endpoints, independent request sessions, immutable
claims and actual PostgreSQL locks. Hooks control timing or inject a database
failure; no successful authorization, persistence or inference is substituted.
"""

import asyncio
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from app.core.config import get_settings
from app.core.exceptions import ApplicationError
from app.core.security import hash_password
from app.db.session import get_db
from app.main import app
from app.ml.feature_schema import PREDICTION_FEATURES, FeatureDataType
from app.models import User, UserRole
from app.repositories.import_repository import ImportRepository
from app.repositories.prediction_repository import PredictionRepository
from app.repositories.student_repository import StudentRepository
from app.repositories.user_repository import UserRepository
from app.schemas.student import StudentCreate
from app.services.import_service import ImportService
from app.services.mutation_authorization import MutationAuthorization
from app.services.outcome_prediction_service import OutcomePredictionService
from app.services.prediction_service import PredictionService
from app.services.staged_import_service import StagedImportService
from app.services.student_service import StudentService
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from tests.api.test_imports import csv_bytes

OPERATIONS = (
    "student_create",
    "student_update",
    "student_delete",
    "admission_insert",
    "admission_update",
    "semester_insert",
    "semester_update",
    "import_csv",
    "staged_upload",
    "staged_correct",
    "staged_exclude",
    "staged_restore",
    "staged_commit",
    "staged_cancel",
    "staged_invalid_commit",
    "legacy_single",
    "enrollment_single",
    "semester_single",
    "legacy_batch",
    "enrollment_batch",
    "semester_batch",
)
PREDICTIONS = tuple(name for name in OPERATIONS if name.endswith(("_single", "_batch")))
REVOCATIONS = ("deactivate", "demote", "password_reset")


class Environment(SimpleNamespace):
    def __repr__(self):
        return "<Disposable D1.1 PostgreSQL fixture>"

    def request(self, method, path, *, role="academic", status=200, **kwargs):
        response = getattr(self.client, method)(
            "/api/v1" + path, headers=self.headers[role], **kwargs
        )
        assert response.status_code == status, (method, path, response.status_code)
        return response

    def models(self):
        if self.models_ready:
            return
        if os.environ.get("RUN_MODEL_INTEGRATION") != "1":
            pytest.fail("D1.1 prediction regressions require RUN_MODEL_INTEGRATION=1")
        self.request("get", "/models/current", role="system")
        for version in ("enrollment-outcome-v1", "first-semester-outcome-v1"):
            self.request(
                "post",
                f"/models/{version}/validate",
                role="system",
                json={"student_id": self.student},
            )
            self.request("post", f"/models/{version}/activate", role="system")
        self.models_ready = True


@pytest.fixture()
def d1_database(monkeypatch):
    url = os.environ.get("D1_AUDIT_TEST_DATABASE_URL")
    if not url:
        pytest.skip(
            "Set D1_AUDIT_TEST_DATABASE_URL to a dedicated PostgreSQL CREATE DATABASE server"
        )
    root = create_engine(url, isolation_level="AUTOCOMMIT")
    assert root.dialect.name == "postgresql"
    name = "d11_authorization_" + uuid4().hex
    with root.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    target = make_url(url).set(database=name)
    engine = create_engine(
        target,
        connect_args={
            "options": "-c statement_timeout=20000 -c lock_timeout=5000 -c application_name=d11-authorization"
        },
    )
    previous = dict(app.dependency_overrides)
    client = TestClient(app)  # No lifespan using an unrelated global database.
    try:
        monkeypatch.setattr(
            get_settings(), "database_url", target.render_as_string(hide_password=False)
        )
        command.upgrade(Config("alembic.ini"), "head")
        ids, passwords = {}, {}
        with Session(engine) as db:
            for key, role in [
                ("system", UserRole.SYSTEM_ADMIN),
                ("academic", UserRole.ACADEMIC_ADMIN),
                ("advisor", UserRole.ACADEMIC_ADVISOR),
            ]:
                passwords[key] = uuid4().hex
                user = User(
                    username="d11_" + key,
                    email=key + "@example.edu",
                    full_name="D1.1 " + key,
                    password_hash=hash_password(passwords[key]),
                    role=role,
                    is_active=True,
                )
                db.add(user)
                db.flush()
                UserRepository(db).claim_identifiers(user)
                ids[key] = str(user.id)
            db.commit()

        def request_db():
            with Session(engine, expire_on_commit=False) as db:
                yield db

        app.dependency_overrides[get_db] = request_db
        headers = {}
        for key in ids:
            response = client.post(
                "/api/v1/auth/login",
                json={"username": "d11_" + key, "password": passwords[key]},
            )
            assert response.status_code == 200
            headers[key] = {
                "Authorization": "Bearer " + response.json()["access_token"]
            }
        fixture = json.loads(
            (
                Path(__file__).parents[1] / "fixtures/outcome_inference_cases.json"
            ).read_text()
        )["cases"][0]["canonical_features"]
        source = {
            "student_number": "D11-PRIMARY",
            "name": "D1.1 source fixture",
            "admission_method": "Published anonymized fixture",
            "previous_qualification": "Published source",
            **{
                key: str(int(value)) if float(value).is_integer() else str(value)
                for key, value in fixture.items()
            },
        }
        env = Environment(
            client=client,
            engine=engine,
            ids=ids,
            headers=headers,
            source=source,
            models_ready=False,
        )
        env.request(
            "post",
            "/imports/csv",
            files={"file": ("source.csv", csv_bytes([source]), "text/csv")},
        )
        env.student = env.request("get", "/students").json()["items"][0]["id"]
        env.bare = env.request(
            "post",
            "/students",
            status=201,
            json={"student_number": "D11-BARE", "name": "D1.1 bare fixture"},
        ).json()["id"]
        yield env
    finally:
        client.close()
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
        engine.dispose()
        with root.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        root.dispose()


def snapshot(env):
    """All non-account data, including versions, diagnostics and action history."""
    excluded = {"users", "user_login_identifiers", "user_administration_audit"}
    with env.engine.connect() as connection:
        tables = connection.scalars(
            text(
                "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
            )
        ).all()
        return {
            table: sorted(
                connection.scalars(
                    text(f'SELECT row_to_json(t)::text FROM "{table}" t')
                ).all()
            )
            for table in tables
            if table not in excluded
        }


def operation(env, kind):
    """Prepare fixtures before timing gates; return an actual HTTP mutation."""
    sid = env.bare if kind.endswith("insert") else env.student
    if kind == "student_create":
        return lambda: env.client.post(
            "/api/v1/students",
            headers=env.headers["academic"],
            json={"student_number": "D11-CREATED", "name": "D1.1 guarded creation"},
        ), 201
    if kind == "student_update":
        return lambda: env.client.patch(
            f"/api/v1/students/{sid}",
            headers=env.headers["academic"],
            json={"name": "D1.1 guarded edit"},
        ), 200
    if kind == "student_delete":
        return lambda: env.client.delete(
            f"/api/v1/students/{env.bare}", headers=env.headers["academic"]
        ), 204
    if kind in (
        "admission_insert",
        "admission_update",
        "semester_insert",
        "semester_update",
    ):
        suffix = "admission" if kind.startswith("admission") else "semester-1"
        table = (
            "admission_records" if suffix == "admission" else "first_semester_records"
        )
        fields = {
            feature.storage_column: (
                int if feature.data_type == FeatureDataType.INTEGER else float
            )(env.source[feature.name])
            for feature in PREDICTION_FEATURES
            if feature.storage_table == table
        }
        payload = (
            {
                **fields,
                "admission_method": "Guarded",
                "previous_qualification": "Guarded",
                "admission_grade": 124.25,
            }
            if suffix == "admission"
            else {**fields, "average_grade": 11}
        )
        return lambda: env.client.put(
            f"/api/v1/students/{sid}/{suffix}",
            headers=env.headers["academic"],
            json=payload,
        ), 200
    if kind in ("import_csv", "staged_upload"):
        row = {**env.source, "student_number": "D11-UPLOAD"}
        path = "/imports/csv" if kind == "import_csv" else "/imports/staged/csv"
        return lambda: env.client.post(
            "/api/v1" + path,
            headers=env.headers["academic"],
            files={"file": ("upload.csv", csv_bytes([row]), "text/csv")},
        ), 200 if kind == "import_csv" else 201
    if kind.startswith("staged_"):
        row = {**env.source, "student_number": "D11-STAGED"}
        if kind == "staged_invalid_commit":
            row["name"] = ""
        batch = env.request(
            "post",
            "/imports/staged/csv",
            status=201,
            files={"file": ("stage.csv", csv_bytes([row]), "text/csv")},
        ).json()
        path = "/api/v1/imports/staged/" + batch["id"]
        item = env.request("get", "/imports/staged/" + batch["id"] + "/rows").json()[
            "items"
        ][0]
        if kind == "staged_restore":
            changed = env.request(
                "patch",
                "/imports/staged/" + batch["id"] + "/rows/" + item["id"],
                json={
                    "expected_batch_version": batch["version"],
                    "expected_row_version": item["version"],
                    "included": False,
                },
            ).json()
            batch, item = changed["batch"], changed["row"]
        env.batch_id = batch["id"]
        if kind in ("staged_commit", "staged_invalid_commit", "staged_cancel"):
            action = "cancel" if kind == "staged_cancel" else "commit"
            return lambda: env.client.post(
                path + "/" + action,
                headers=env.headers["academic"],
                json={"expected_batch_version": batch["version"]},
            ), 409 if kind == "staged_invalid_commit" else 200
        payload = {
            "expected_batch_version": batch["version"],
            "expected_row_version": item["version"],
        }
        payload.update(
            {"values": {"name": "D1.1 corrected"}}
            if kind == "staged_correct"
            else {"included": kind == "staged_restore"}
        )
        return lambda: env.client.patch(
            path + "/rows/" + item["id"], headers=env.headers["academic"], json=payload
        ), 200
    assert kind in PREDICTIONS
    env.models()
    if kind.endswith("batch"):
        env.request(
            "post",
            "/imports/csv",
            files={
                "file": (
                    "second.csv",
                    csv_bytes([{**env.source, "student_number": "D11-SECOND"}]),
                    "text/csv",
                )
            },
        )
    family = kind.split("_")[0]
    query = (
        ""
        if family == "legacy"
        else "?prediction_stage="
        + ("ENROLLMENT" if family == "enrollment" else "FIRST_SEMESTER")
    )
    path = (
        "/predictions/batch"
        if kind.endswith("batch")
        else f"/students/{env.student}/predictions"
    )
    return lambda: env.client.post(
        "/api/v1" + path + query, headers=env.headers["academic"]
    ), 200 if kind.endswith("batch") else 201


def revoke(env, change):
    path = "/users/" + env.ids["academic"]
    if change == "demote":
        return env.request(
            "patch", path, role="system", json={"role": "ACADEMIC_ADVISOR"}
        )
    if change == "password_reset":
        return env.request(
            "post",
            path + "/reset-password",
            role="system",
            json={"temporary_password": uuid4().hex},
        )
    return env.request("post", path + "/deactivate", role="system")


def pause_authorization(
    env, monkeypatch, *, after_lock=False, lock_number=1, refresh=False
):
    ready, release = Event(), Event()
    count = 0
    method = "lock_users" if after_lock else "__init__"
    original = getattr(MutationAuthorization, method)

    def paused(self, *args, **kwargs):
        nonlocal count
        target = str(self.subject if after_lock else args[1].id) == env.ids["academic"]
        result = original(self, *args, **kwargs) if after_lock else None
        if target:
            count += 1
            if count == lock_number:
                ready.set()
                assert release.wait(12), (
                    "Controlled authorization gate was not released"
                )
                if refresh:
                    args[0].refresh(args[1])  # Cannot replace immutable JWT version.
        return result if after_lock else original(self, *args, **kwargs)

    monkeypatch.setattr(MutationAuthorization, method, paused)
    return ready, release


def wait_for_lock(env):
    deadline = time.monotonic() + 4
    with env.engine.connect() as connection:
        while time.monotonic() < deadline:
            waiting = connection.scalar(
                text(
                    "SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND application_name='d11-authorization' AND wait_event_type='Lock')"
                )
            )
            connection.commit()
            if waiting:
                return
            time.sleep(0.02)
    pytest.fail("Actual PostgreSQL lock wait was not observed")


@pytest.mark.parametrize("kind", OPERATIONS)
@pytest.mark.parametrize("change", REVOCATIONS)
def test_revocation_commits_first_denies_without_domain_or_audit_changes(
    d1_database, monkeypatch, kind, change
):
    env = d1_database
    submit, _ = operation(env, kind)
    before = snapshot(env)
    ready, release = pause_authorization(env, monkeypatch, refresh=True)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(submit)
        try:
            assert ready.wait(8)
            revoke(env, change)
            with env.engine.connect() as connection:
                assert (
                    connection.scalar(
                        text(
                            "SELECT token_version FROM users WHERE id=CAST(:id AS uuid)"
                        ),
                        {"id": env.ids["academic"]},
                    )
                    == 1
                )
        finally:
            release.set()
        response = pending.result(timeout=15)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
    assert snapshot(env) == before
    env.request("get", "/students", status=401)


@pytest.mark.parametrize("kind", OPERATIONS)
@pytest.mark.parametrize("change", REVOCATIONS)
def test_guarded_mutation_commits_before_revocation_can_finish(
    d1_database, monkeypatch, kind, change
):
    env = d1_database
    submit, status = operation(env, kind)
    before = snapshot(env)
    ready, release = pause_authorization(
        env,
        monkeypatch,
        after_lock=True,
        lock_number=2 if kind.startswith("legacy_") else 1,
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(submit)
        try:
            assert ready.wait(8)
            account = pool.submit(revoke, env, change)
            wait_for_lock(env)
            assert not account.done()
        finally:
            release.set()
        response = pending.result(timeout=15)
        assert account.result(timeout=15).status_code == 200
    assert response.status_code == status
    assert snapshot(env) != before
    if kind in PREDICTIONS:
        expected_model = (
            "dropout-logistic-regression-v1"
            if kind.startswith("legacy_")
            else "enrollment-outcome-v1"
            if kind.startswith("enrollment_")
            else "first-semester-outcome-v1"
        )
        assert response.json()["model_version"] == expected_model
    if kind.endswith("batch"):
        assert response.json()["assessed"] == 2
        assert response.json()["skipped_not_ready"] == 1
    with env.engine.connect() as connection:
        assert (
            connection.scalar(text("SELECT count(*) FROM casework_action_audit")) == 0
        )


@pytest.mark.parametrize("kind", ["legacy_single", "legacy_batch"])
@pytest.mark.parametrize("change", REVOCATIONS)
def test_legacy_registry_commit_does_not_authorize_next_transaction(
    d1_database, monkeypatch, kind, change
):
    env = d1_database
    submit, _ = operation(env, kind)
    before = snapshot(env)
    ready, release = Event(), Event()
    original = PredictionService.synchronize_registry

    def between(self, *args, **kwargs):
        model = original(self, *args, **kwargs)
        ready.set()
        assert release.wait(12)
        return model

    monkeypatch.setattr(PredictionService, "synchronize_registry", between)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(submit)
        try:
            assert ready.wait(8)
            revoke(env, change)
        finally:
            release.set()
        response = pending.result(timeout=15)
    assert response.status_code == 401
    assert snapshot(env) == before


@pytest.mark.parametrize("kind", ["import_csv", "staged_upload"])
@pytest.mark.parametrize("change", REVOCATIONS)
def test_upload_wait_holds_no_authorization_lock_and_revalidates_after_read(
    d1_database, monkeypatch, kind, change
):
    env = d1_database
    submit, _ = operation(env, kind)
    before = snapshot(env)
    ready, release = Event(), Event()
    original = ImportService.parse_upload

    async def delayed(upload):
        ready.set()
        assert await asyncio.to_thread(release.wait, 12)
        return await original(upload)

    monkeypatch.setattr(ImportService, "parse_upload", staticmethod(delayed))
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(submit)
        try:
            assert ready.wait(8)
            with env.engine.connect() as connection:
                assert not connection.scalar(
                    text(
                        "SELECT EXISTS (SELECT 1 FROM pg_locks l JOIN pg_stat_activity a ON a.pid=l.pid WHERE a.datname=current_database() AND l.locktype='advisory' AND l.granted)"
                    )
                )
            revoke(env, change)
        finally:
            release.set()
        response = pending.result(timeout=15)
    assert response.status_code == 401
    assert snapshot(env) == before


@pytest.mark.parametrize(
    "kind", ["student_update", "staged_correct", "enrollment_single"]
)
@pytest.mark.parametrize(
    "state,code",
    [
        ("must_change_password", "PASSWORD_CHANGE_REQUIRED"),
        ("role", "INSUFFICIENT_PERMISSIONS"),
        ("is_active", "AUTHENTICATION_REQUIRED"),
    ],
)
def test_current_role_and_required_password_are_revalidated_without_version_change(
    d1_database, monkeypatch, kind, state, code
):
    env = d1_database
    submit, _ = operation(env, kind)
    before = snapshot(env)
    ready, release = pause_authorization(env, monkeypatch)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(submit)
        try:
            assert ready.wait(8)
            # Fixture-only change isolates these checks from token revocation.
            with env.engine.begin() as connection:
                sql = (
                    "UPDATE users SET must_change_password=true WHERE id=CAST(:id AS uuid)"
                    if state == "must_change_password"
                    else "UPDATE users SET role='ACADEMIC_ADVISOR' WHERE id=CAST(:id AS uuid)"
                    if state == "role"
                    else "UPDATE users SET is_active=false WHERE id=CAST(:id AS uuid)"
                )
                connection.execute(text(sql), {"id": env.ids["academic"]})
        finally:
            release.set()
        response = pending.result(timeout=15)
    assert response.status_code == (401 if state == "is_active" else 403)
    assert response.json()["error"]["code"] == code
    assert snapshot(env) == before


@pytest.mark.parametrize(
    "kind",
    [
        "student_create",
        "import_rows",
        "staged_rows",
        "legacy_single",
        "enrollment_single",
        "semester_single",
    ],
)
def test_direct_service_has_no_orm_actor_authentication_bypass(d1_database, kind):
    env = d1_database
    before = snapshot(env)
    with Session(env.engine) as db:
        actor = db.get(User, UUID(env.ids["academic"]))
        with pytest.raises(ApplicationError) as error:
            if kind == "student_create":
                StudentService(db).create_student(
                    StudentCreate(student_number="NO-BYPASS", name="No bypass"),
                    actor=actor,
                )
            elif kind == "import_rows":
                ImportService(db)._persist_rows("empty.csv", [], actor=actor)
            elif kind == "staged_rows":
                StagedImportService(db)._persist_stage("empty.csv", [], actor=actor)
            elif kind == "legacy_single":
                PredictionService(db).predict_student(UUID(env.student), actor=actor)
            else:
                from app.ml.outcomes.contracts import PredictionStage

                stage = (
                    PredictionStage.ENROLLMENT
                    if kind == "enrollment_single"
                    else PredictionStage.FIRST_SEMESTER
                )
                OutcomePredictionService(db).predict_stage(
                    UUID(env.student), stage, actor=actor
                )
        assert error.value.code == "AUTHENTICATION_REQUIRED"
    assert snapshot(env) == before


@pytest.mark.parametrize("lock", ["administration", "actor", "staged_batch"])
def test_real_lock_timeout_rolls_back_and_can_be_manually_retried(d1_database, lock):
    env = d1_database
    submit, status = operation(
        env, "staged_correct" if lock == "staged_batch" else "student_update"
    )
    before = snapshot(env)
    with env.engine.connect() as blocker:
        if lock == "administration":
            blocker.execute(text("SELECT pg_advisory_xact_lock(610110009)"))
        elif lock == "actor":
            blocker.execute(
                text("SELECT id FROM users WHERE id=CAST(:id AS uuid) FOR UPDATE"),
                {"id": env.ids["academic"]},
            )
        else:
            blocker.execute(
                text(
                    "SELECT id FROM staged_import_batches WHERE id=CAST(:id AS uuid) FOR UPDATE"
                ),
                {"id": env.batch_id},
            )
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(submit)
            wait_for_lock(env)
            response = pending.result(timeout=12)
        blocker.rollback()
    assert response.status_code == 409
    expected = (
        "STAGED_IMPORT_BUSY"
        if lock == "staged_batch"
        else "ACADEMIC_WRITE_RETRYABLE_CONFLICT"
    )
    assert response.json()["error"]["code"] == expected
    if lock != "staged_batch":
        assert response.json()["error"]["details"]["retryable"] is True
    assert snapshot(env) == before
    assert submit().status_code == status


@pytest.mark.parametrize(
    "kind",
    [
        "student_update",
        "import_csv",
        "staged_commit",
        "legacy_batch",
        "enrollment_batch",
        "semester_batch",
    ],
)
def test_database_failure_rolls_back_all_writes_versions_and_actions(
    d1_database, monkeypatch, kind
):
    env = d1_database
    submit, _ = operation(env, kind)
    before = snapshot(env)
    repository, name = (
        (StudentRepository, "update")
        if kind == "student_update"
        else (ImportRepository, "add_student_graph")
        if kind in ("import_csv", "staged_commit")
        else (PredictionRepository, "add_prediction")
    )
    original = getattr(repository, name)

    def fail_after_write(self, *args, **kwargs):
        original(self, *args, **kwargs)
        self.db.execute(text("SELECT 1 / 0"))

    monkeypatch.setattr(repository, name, fail_after_write)
    response = submit()
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "DATABASE_ERROR"
    assert snapshot(env) == before


def test_authorized_staged_unique_collision_keeps_only_rejected_commit_diagnostics(
    d1_database, monkeypatch
):
    env = d1_database
    rows = [
        {**env.source, "student_number": "D11-FIRST-ONLY"},
        {**env.source, "student_number": "D11-SHARED"},
    ]
    batch = env.request(
        "post",
        "/imports/staged/csv",
        status=201,
        files={"file": ("collision.csv", csv_bytes(rows), "text/csv")},
    ).json()
    original = ImportRepository.existing_student_numbers
    inserted = False

    def external_writer_after_validation(self, numbers):
        nonlocal inserted
        existing = original(self, numbers)
        if not inserted:
            inserted = True
            # Deliberate external fixture writer, outside the HTTP mutex, forces
            # the real unique-constraint/savepoint branch after validation.
            with env.engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO students (id, student_number, name) VALUES (:id, 'D11-SHARED', 'External fixture')"
                    ),
                    {"id": uuid4()},
                )
        return existing

    monkeypatch.setattr(
        ImportRepository, "existing_student_numbers", external_writer_after_validation
    )
    response = env.request(
        "post",
        "/imports/staged/" + batch["id"] + "/commit",
        status=409,
        json={"expected_batch_version": batch["version"]},
    )
    assert response.json()["error"]["code"] == "STAGED_IMPORT_COMMIT_CONFLICT"
    current = env.request("get", "/imports/staged/" + batch["id"]).json()
    assert current["version"] == batch["version"] + 1
    assert current["status"] == "REVIEW_REQUIRED"
    assert current["invalid_included_rows"] == 1
    with env.engine.connect() as connection:
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM students WHERE student_number='D11-FIRST-ONLY'"
                )
            )
            == 0
        )
        assert (
            connection.scalar(text("SELECT count(*) FROM import_jobs")) == 1
        )  # Initial source fixture only.
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM staged_import_actions WHERE action='COMMIT_REJECTED'"
                )
            )
            == 1
        )
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM staged_import_actions WHERE action='COMMITTED'"
                )
            )
            == 0
        )
