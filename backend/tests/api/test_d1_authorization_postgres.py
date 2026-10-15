"""D1 unresolved authorization-race characterization on real PostgreSQL.

Passing tests confirm the defect still exists. Timing hooks pause service entry
only; real HTTP dependencies, account revocation, import writes and DB locks run.
No deployment artifact or model inference is involved.
"""

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from app.core.config import get_settings
from app.core.security import create_access_token, hash_password
from app.db.session import get_db
from app.main import app
from app.models import User, UserRole
from app.repositories.user_repository import UserRepository
from app.services.staged_import_service import StagedImportService
from app.services.student_service import StudentService
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from tests.api.test_imports import csv_bytes, valid_row


@pytest.fixture(autouse=True)
def isolated_model_runtime():
    yield  # Override unrelated synthetic-model training for this DB-only module.


@pytest.fixture()
def d1_database(monkeypatch):
    url = os.environ.get("D1_AUDIT_TEST_DATABASE_URL")
    if not url:
        pytest.skip(
            "Set D1_AUDIT_TEST_DATABASE_URL to a disposable PostgreSQL CREATE DATABASE server"
        )
    root = create_engine(url, isolation_level="AUTOCOMMIT")
    assert root.dialect.name == "postgresql"
    name = "d1_security_" + uuid4().hex
    with root.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    target = make_url(url).set(database=name)
    engine = create_engine(
        target,
        connect_args={"options": "-c statement_timeout=15000 -c lock_timeout=5000"},
    )
    previous = dict(app.dependency_overrides)
    try:
        monkeypatch.setattr(
            get_settings(), "database_url", target.render_as_string(hide_password=False)
        )
        command.upgrade(Config("alembic.ini"), "head")
        ids = {}
        with Session(engine) as db:
            for key, role in [
                ("system", UserRole.SYSTEM_ADMIN),
                ("academic", UserRole.ACADEMIC_ADMIN),
            ]:
                user = User(
                    username="d1_" + key,
                    email=key + "@example.edu",
                    full_name="D1 " + key,
                    password_hash=hash_password(uuid4().hex),
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
        headers = {
            key: {"Authorization": "Bearer " + create_access_token(value)}
            for key, value in ids.items()
        }
        client = TestClient(
            app
        )  # No lifespan/model initialization for this DB-only audit.
        try:
            yield client, engine, ids, headers
        finally:
            client.close()
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
        engine.dispose()
        with root.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        root.dispose()


@pytest.mark.parametrize("operation", ["staged_commit", "student_create"])
@pytest.mark.parametrize("revocation", ["deactivate", "demote", "password_reset"])
def test_characterization_revocation_can_finish_before_academic_write(
    d1_database, monkeypatch, operation, revocation
):
    client, engine, ids, headers = d1_database
    entered, resume = Event(), Event()
    if operation == "staged_commit":
        response = client.post(
            "/api/v1/imports/staged/csv",
            headers=headers["academic"],
            files={
                "file": ("fixture.csv", csv_bytes([valid_row("D1-RACE")]), "text/csv")
            },
        )
        assert response.status_code == 201
        batch = response.json()
        service, method = StagedImportService, "commit"

        def submit():
            return client.post(
                f"/api/v1/imports/staged/{batch['id']}/commit",
                headers=headers["academic"],
                json={"expected_batch_version": batch["version"]},
            )
    else:
        service, method = StudentService, "create_student"

        def submit():
            return client.post(
                "/api/v1/students",
                headers=headers["academic"],
                json={"student_number": "D1-RACE", "name": "D1 after-revocation write"},
            )

    original = getattr(service, method)

    def paused(self, *args, **kwargs):
        entered.set()  # Authentication/role dependency already completed.
        assert resume.wait(15), "Timing gate not released"
        return original(self, *args, **kwargs)

    monkeypatch.setattr(service, method, paused)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(submit)
        try:
            assert entered.wait(15), "Request did not reach service entry"
            path = f"/api/v1/users/{ids['academic']}"
            if revocation == "demote":
                changed = client.patch(
                    path, headers=headers["system"], json={"role": "ACADEMIC_ADVISOR"}
                )
            elif revocation == "password_reset":
                changed = client.post(
                    path + "/reset-password",
                    headers=headers["system"],
                    json={"temporary_password": uuid4().hex},
                )
            else:
                changed = client.post(path + "/deactivate", headers=headers["system"])
            assert changed.status_code == 200
            with engine.connect() as connection:
                assert (
                    connection.scalar(
                        text(
                            "SELECT token_version FROM users WHERE id=CAST(:id AS uuid)"
                        ),
                        {"id": ids["academic"]},
                    )
                    == 1
                )
        finally:
            resume.set()
        result = future.result(timeout=20)
    # Unsafe characterization: revocation committed first, yet the write succeeds.
    assert result.status_code == (200 if operation == "staged_commit" else 201)
    with engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT count(*) FROM students WHERE student_number='D1-RACE'")
            )
            == 1
        )
    # Fresh requests with the revoked token are rejected; this is an in-flight race.
    assert (
        client.get("/api/v1/students", headers=headers["academic"]).status_code == 401
    )
