"""Opt-in real model + migrated PostgreSQL API workflow in a disposable database."""

import os
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import get_db
from app.main import app
from app.models import PredictionResult, Student, User, UserRole, Warning
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from tests.api.test_imports import csv_bytes, valid_row


@pytest.mark.model_integration
def test_migrated_postgres_real_prediction_and_warning(monkeypatch):
    url = os.environ.get("MODEL_TEST_DATABASE_URL")
    if os.environ.get("RUN_MODEL_INTEGRATION") != "1" or not url:
        pytest.skip(
            "Set RUN_MODEL_INTEGRATION=1 and MODEL_TEST_DATABASE_URL (PostgreSQL with CREATE DATABASE)"
        )
    root = create_engine(url, isolation_level="AUTOCOMMIT")
    assert root.dialect.name == "postgresql"
    database = "model_a1_test_" + uuid4().hex
    with root.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{database}"'))
    test_url = make_url(url).set(database=database)
    engine = create_engine(test_url)
    sessions = sessionmaker(engine, expire_on_commit=False)
    try:
        monkeypatch.setattr(
            get_settings(),
            "database_url",
            test_url.render_as_string(hide_password=False),
        )
        monkeypatch.setattr(get_settings(), "ml_model_required", True)
        from app import main

        monkeypatch.setattr(main, "SessionLocal", sessions)
        command.upgrade(Config("alembic.ini"), "head")
        with engine.connect() as connection:
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "20261004_0008"
            )
        with Session(engine) as db:
            db.add(
                User(
                    username="a1_academic",
                    email="a1@example.edu",
                    password_hash=hash_password("A1-integration-test-password!"),
                    full_name="A1 Academic Admin",
                    role=UserRole.ACADEMIC_ADMIN,
                    is_active=True,
                )
            )
            db.commit()

        def override_db():
            with sessions() as db:
                yield db

        app.dependency_overrides[get_db] = override_db
        with TestClient(app) as client:
            assert client.get("/api/v1/health/live").status_code == 200
            assert client.get("/api/v1/health").status_code == 200
            ready = client.get("/api/v1/health/ready")
            assert ready.status_code == 200, ready.text
            login = client.post(
                "/api/v1/auth/login",
                json={
                    "username": "a1_academic",
                    "password": "A1-integration-test-password!",
                },
            )
            assert login.status_code == 200, login.text
            headers = {"Authorization": "Bearer " + login.json()["access_token"]}
            row = valid_row("A1-REAL-MODEL")
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
                headers=headers,
                files={"file": ("a1.csv", csv_bytes([row]), "text/csv")},
            )
            assert imported.status_code == 200, imported.text
            assert imported.json()["valid_rows"] == 1
            students = client.get("/api/v1/students", headers=headers).json()["items"]
            student_id = students[0]["id"]
            predicted = client.post(
                f"/api/v1/students/{student_id}/predictions", headers=headers
            )
            assert predicted.status_code == 201, predicted.text
            body = predicted.json()
            assert body["model_version"] == "dropout-logistic-regression-v1"
            assert 0 <= body["probability"] <= 1
            assert body["risk_level"] in {"HIGH", "MEDIUM"}
            assert len(body["top_explanation_factors"]) == 5
            with Session(engine) as db:
                saved = db.get(PredictionResult, UUID(body["id"]))
                assert saved is not None
                assert len(saved.feature_snapshot) == 30
                warning = db.scalar(
                    select(Warning).where(Warning.prediction_id == saved.id)
                )
                assert warning is not None
                assert warning.student_id == db.scalar(select(Student.id))
            history = client.get(
                f"/api/v1/students/{student_id}/predictions", headers=headers
            )
            assert history.json()["items"][0]["id"] == body["id"]
            print(
                f"Real model prediction: probability={body['probability']}, risk={body['risk_level']}; prediction and warning persisted"
            )
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
        with root.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{database}" WITH (FORCE)'))
        root.dispose()
