"""Disposable migrated PostgreSQL databases for account invariants and supported flows."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from app.core.config import get_settings
from app.core.exceptions import ApplicationError
from app.core.security import hash_password
from app.db.init_db import bootstrap_system_admin
from app.db.session import get_db
from app.main import app
from app.models import (
    User,
    UserAdministrationAudit,
    UserLoginIdentifier,
    UserRole,
    Warning,
)
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate, UserUpdate
from app.schemas.warning import AssignmentRequest
from app.services.user_service import UserService
from app.services.warning_service import WarningService
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from tests.api.test_imports import csv_bytes, valid_row
from tests.api.test_users import CHANGED, INITIAL, payload, sign_in


@pytest.fixture()
def postgres_accounts(monkeypatch):
    url = os.environ.get("USER_MANAGEMENT_TEST_DATABASE_URL")
    if not url:
        pytest.skip(
            "Set USER_MANAGEMENT_TEST_DATABASE_URL to a dedicated PostgreSQL server with CREATE DATABASE"
        )
    root = create_engine(url, isolation_level="AUTOCOMMIT")
    assert root.dialect.name == "postgresql"
    database = "users_a2_test_" + uuid4().hex
    with root.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{database}"'))
    test_url = make_url(url).set(database=database)
    engine = create_engine(test_url)
    monkeypatch.setattr(
        get_settings(), "database_url", test_url.render_as_string(hide_password=False)
    )
    try:
        yield engine
    finally:
        engine.dispose()
        with root.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{database}" WITH (FORCE)'))
        root.dispose()


def migrate(revision="head"):
    command.upgrade(Config("alembic.ini"), revision)


def seed_admins(engine, count=1):
    ids = []
    with Session(engine) as db:
        for index in range(count):
            user = User(
                username=f"admin{index}",
                email=f"admin{index}@example.edu",
                full_name="System Admin",
                role=UserRole.SYSTEM_ADMIN,
                password_hash=hash_password(INITIAL),
                is_active=True,
            )
            db.add(user)
            db.flush()
            UserRepository(db).claim_identifiers(user)
            ids.append(user.id)
        db.commit()
    return ids


def parallel(engine, jobs):
    barrier = Barrier(len(jobs))

    def run(job):
        with Session(engine, expire_on_commit=False) as db:
            actor = db.get(User, job[0])
            barrier.wait(timeout=10)
            try:
                job[1](UserService(db), actor)
                return "saved"
            except ApplicationError as exc:
                return exc.code

    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        return list(pool.map(run, jobs))


@pytest.mark.parametrize("cross_namespace", [False, True])
def test_concurrent_identifier_creation(postgres_accounts, cross_namespace):
    engine = postgres_accounts
    migrate()
    actor = seed_admins(engine)[0]
    first = payload("race", email="shared@example.edu")
    second = payload(
        "SHARED@example.edu" if cross_namespace else "RACE", email="second@example.edu"
    )
    results = parallel(
        engine,
        [
            (actor, lambda service, user: service.create(user, UserCreate(**first))),
            (actor, lambda service, user: service.create(user, UserCreate(**second))),
        ],
    )
    assert sorted(results) == ["USER_IDENTIFIER_CONFLICT", "saved"]
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(User)) == 2
        assert db.scalar(select(func.count()).select_from(UserAdministrationAudit)) == 1
        assert db.scalar(select(func.count()).select_from(UserLoginIdentifier)) == 4


def test_concurrent_last_admin_demotion(postgres_accounts):
    engine = postgres_accounts
    migrate()
    ids = seed_admins(engine, 2)
    results = parallel(
        engine,
        [
            (
                identifier,
                lambda service, user: service.update(
                    user, user.id, UserUpdate(role=UserRole.ACADEMIC_ADMIN)
                ),
            )
            for identifier in ids
        ],
    )
    assert sorted(results) == ["LAST_ACTIVE_SYSTEM_ADMIN", "saved"]
    with Session(engine) as db:
        assert UserRepository(db).active_admin_count() == 1
        assert db.scalar(select(func.count()).select_from(UserAdministrationAudit)) == 1


def test_database_namespace_and_case_constraints(postgres_accounts):
    engine = postgres_accounts
    migrate()
    seed_admins(engine, 2)
    with Session(engine) as db:
        users = list(db.scalars(select(User).order_by(User.username)))
        db.add(UserLoginIdentifier(identifier=users[0].email, user_id=users[1].id))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        users[1].username = " ADMIN0 "
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        assert db.scalar(select(func.count()).select_from(User)) == 2


def legacy_user(connection, username, email):
    identifier = uuid4()
    connection.execute(
        text(
            "INSERT INTO users (id, username, email, password_hash, full_name, role, is_active) VALUES (:id,:username,:email,:hash,'Legacy Account','SYSTEM_ADMIN',true)"
        ),
        {
            "id": identifier,
            "username": username,
            "email": email,
            "hash": "preserved-legacy-hash",
        },
    )
    return identifier


def test_populated_migration_preserves_accounts_and_round_trip(postgres_accounts):
    engine = postgres_accounts
    migrate("20261004_0008")
    with engine.begin() as connection:
        identifier = legacy_user(connection, " LegacyUser ", "LEGACY@EXAMPLE.EDU")
        same = legacy_user(connection, "same@example.edu", "same@example.edu")
    migrate()
    with Session(engine) as db:
        user = db.get(User, identifier)
        assert user.username == " LegacyUser " and user.email == "LEGACY@EXAMPLE.EDU"
        assert user.password_hash == "preserved-legacy-hash"
        assert not user.must_change_password and user.token_version == 0
        assert set(
            db.scalars(
                select(UserLoginIdentifier.identifier).where(
                    UserLoginIdentifier.user_id == identifier
                )
            )
        ) == {"legacyuser", "legacy@example.edu"}
        assert (
            db.scalar(
                select(func.count())
                .select_from(UserLoginIdentifier)
                .where(UserLoginIdentifier.user_id == same)
            )
            == 1
        )
    command.downgrade(Config("alembic.ini"), "20261004_0008")
    assert "token_version" not in {
        column["name"] for column in inspect(engine).get_columns("users")
    }
    migrate()
    with Session(engine) as db:
        assert db.get(User, identifier).password_hash == "preserved-legacy-hash"


@pytest.mark.parametrize(
    "username,email",
    [
        ("LEGACY", "other@example.edu"),
        ("other", "FIRST@EXAMPLE.EDU"),
        ("first@example.edu", "other@example.edu"),
    ],
)
def test_populated_migration_conflicts_fail_atomically(
    postgres_accounts, username, email
):
    engine = postgres_accounts
    migrate("20261004_0008")
    with engine.begin() as connection:
        legacy_user(connection, "legacy", "first@example.edu")
        legacy_user(connection, username, email)
    with pytest.raises(RuntimeError, match="Conflicting case-insensitive"):
        migrate()
    with engine.connect() as connection:
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "20261004_0008"
        )
        assert connection.scalar(text("SELECT count(*) FROM users")) == 2
    assert "must_change_password" not in {
        column["name"] for column in inspect(engine).get_columns("users")
    }
    assert "user_administration_audit" not in inspect(engine).get_table_names()


@pytest.mark.model_integration
def test_supported_bootstrap_provisioning_and_assignment_race(
    postgres_accounts, monkeypatch
):
    if os.environ.get("RUN_MODEL_INTEGRATION") != "1":
        pytest.skip("Set RUN_MODEL_INTEGRATION=1 for the verified A1 artifact")
    engine = postgres_accounts
    migrate()
    sessions = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setenv("BOOTSTRAP_ADMIN_USERNAME", "fresh_system")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "fresh_system@example.edu")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_FULL_NAME", "Fresh System Admin")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", INITIAL)
    with sessions() as db:
        assert bootstrap_system_admin(db)
        assert not bootstrap_system_admin(db)
    from app import main

    monkeypatch.setattr(main, "SessionLocal", sessions)
    monkeypatch.setattr(get_settings(), "ml_model_required", True)

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            system = sign_in(client, "fresh_system", INITIAL)
            assert (
                client.get("/api/v1/users", headers=system).json()["error"]["code"]
                == "PASSWORD_CHANGE_REQUIRED"
            )

            def change(headers):
                result = client.post(
                    "/api/v1/auth/change-password",
                    headers=headers,
                    json={"current_password": INITIAL, "new_password": CHANGED},
                )
                assert result.status_code == 200, result.text
                return {"Authorization": "Bearer " + result.json()["access_token"]}

            system = change(system)
            accounts = {}
            for name, role in (
                ("academic", "ACADEMIC_ADMIN"),
                ("advisor", "ACADEMIC_ADVISOR"),
            ):
                result = client.post(
                    "/api/v1/users", headers=system, json=payload(name, role)
                )
                assert result.status_code == 201, result.text
                accounts[name] = result.json()
            academic = change(sign_in(client, "academic", INITIAL))
            advisor = change(sign_in(client, "advisor", INITIAL))
            assert client.get("/api/v1/users", headers=academic).status_code == 403
            assert client.get("/api/v1/users", headers=advisor).status_code == 403
            directory = client.get("/api/v1/users/advisors", headers=academic).json()
            assert directory["items"] == [
                {"id": accounts["advisor"]["id"], "full_name": "New Account"}
            ]
            row = valid_row("A2-REAL-MODEL")
            row.update(
                debtor="1",
                tuition_fees_up_to_date="0",
                age_at_enrollment="30",
                first_semester_enrolled_units="6",
                first_semester_evaluations="6",
                first_semester_approved_units="0",
                first_semester_average_grade="0",
            )
            imported = client.post(
                "/api/v1/imports/csv",
                headers=academic,
                files={"file": ("a2.csv", csv_bytes([row]), "text/csv")},
            )
            assert imported.status_code == 200, imported.text
            student = client.get("/api/v1/students", headers=academic).json()["items"][
                0
            ]
            predicted = client.post(
                f"/api/v1/students/{student['id']}/predictions", headers=academic
            )
            assert predicted.status_code == 201, predicted.text
            with sessions() as db:
                warning_id = db.scalar(
                    select(Warning.id).where(
                        Warning.prediction_id == UUID(predicted.json()["id"])
                    )
                )
                admin_id = db.scalar(
                    select(User.id).where(User.username == "fresh_system")
                )
            advisor_id = UUID(accounts["advisor"]["id"])
            # Actual assignment vs deactivation: either assignment is rejected or administration is blocked.
            barrier = Barrier(2)

            def assign():
                with sessions() as db:
                    barrier.wait(timeout=10)
                    try:
                        WarningService(db).assign(
                            warning_id,
                            AssignmentRequest(assigned_to=advisor_id),
                            db.get(User, UUID(accounts["academic"]["id"])),
                        )
                        return "saved"
                    except ApplicationError as exc:
                        return exc.code

            def deactivate():
                with sessions() as db:
                    actor = db.get(User, admin_id)
                    barrier.wait(timeout=10)
                    try:
                        UserService(db).set_active(actor, advisor_id, False)
                        return "saved"
                    except ApplicationError as exc:
                        return exc.code

            with ThreadPoolExecutor(max_workers=2) as pool:
                assignment, deactivation = pool.submit(assign), pool.submit(deactivate)
                results = assignment.result(timeout=20), deactivation.result(timeout=20)
            assert results in [
                ("saved", "ADVISOR_HAS_ACTIVE_ASSIGNMENTS"),
                ("INVALID_WARNING_ASSIGNEE", "saved"),
            ]
            if results[1] == "saved":
                assert (
                    client.post(
                        f"/api/v1/users/{advisor_id}/activate", headers=system
                    ).status_code
                    == 200
                )
                advisor = sign_in(client, "advisor", CHANGED)
            assigned = client.patch(
                f"/api/v1/warnings/{warning_id}/assignment",
                headers=academic,
                json={"assigned_to": str(advisor_id)},
            )
            assert assigned.status_code == 200, assigned.text
            reviewed = client.post(
                f"/api/v1/warnings/{warning_id}/reviews",
                headers=advisor,
                json={
                    "decision": "DISMISSED",
                    "note": "Supported account workflow review",
                },
            )
            assert reviewed.status_code == 201, reviewed.text
            assert (
                client.post(
                    f"/api/v1/users/{advisor_id}/deactivate", headers=system
                ).status_code
                == 200
            )
            assert client.get("/api/v1/students", headers=advisor).status_code == 401
            assert (
                client.post(
                    "/api/v1/auth/login",
                    json={"username": "advisor", "password": CHANGED},
                ).status_code
                == 401
            )
            with sessions() as db:
                assert (
                    db.get(Warning, warning_id).assigned_to == advisor_id
                )  # Historical reference retained.
                audits = list(db.scalars(select(UserAdministrationAudit)))
                assert {audit.action for audit in audits} >= {
                    "USER_CREATED",
                    "PASSWORD_CHANGED",
                    "USER_DEACTIVATED",
                }
                serialized = json.dumps([audit.changed_fields for audit in audits])
                assert (
                    INITIAL not in serialized
                    and CHANGED not in serialized
                    and "access_token" not in serialized
                )
    finally:
        app.dependency_overrides.clear()
