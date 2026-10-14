"""Real PostgreSQL migration, class constraints and supported dual-stage workflow."""

import json
import os
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from app.core.config import get_settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.init_db import bootstrap_system_admin
from app.db.session import get_db
from app.main import app
from app.ml.feature_schema import PREDICTION_FEATURES, SourceStage
from app.ml.outcomes.contracts import MODEL_VERSIONS, ModelTargetType, PredictionStage
from app.models import (
    ModelActivationEvent,
    ModelValidation,
    ModelVersion,
    PredictionResult,
    User,
    UserRole,
    Warning,
)
from app.services.model_catalog_service import ModelCatalogService
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from tests.api.test_predictions import create_ready_student

INITIAL = "B1-temporary-password-123!"
CHANGED = "B1-owner-chosen-password-456!"
CASES = json.loads(
    (Path(__file__).parents[1] / "fixtures/outcome_inference_cases.json").read_bytes()
)["cases"]


@pytest.fixture()
def pg_outcomes(monkeypatch):
    url = os.environ.get("DUAL_STAGE_TEST_DATABASE_URL")
    if not url:
        pytest.skip(
            "Set DUAL_STAGE_TEST_DATABASE_URL to a dedicated PostgreSQL server with CREATE DATABASE"
        )
    root = create_engine(url, isolation_level="AUTOCOMMIT")
    assert root.dialect.name == "postgresql"
    name = "outcomes_b1_test_" + uuid4().hex
    with root.connect() as db:
        db.execute(text(f'CREATE DATABASE "{name}"'))
    test_url = make_url(url).set(database=name)
    engine = create_engine(test_url)
    monkeypatch.setattr(
        get_settings(), "database_url", test_url.render_as_string(hide_password=False)
    )
    try:
        yield engine
    finally:
        engine.dispose()
        with root.connect() as db:
            db.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        root.dispose()


def migrate(revision="head"):
    command.upgrade(Config("alembic.ini"), revision)


def test_populated_binary_migration_preserves_decisions_and_roundtrips(pg_outcomes):
    migrate("20261011_0009")
    ids = {
        key: uuid4()
        for key in ("user", "student", "model", "prediction", "warning", "review")
    }
    metadata = json.loads(
        Path("app/ml/model_registry/dropout-risk-v1/metadata.json").read_bytes()
    )
    features = CASES[-1]["canonical_features"]
    with pg_outcomes.begin() as db:
        db.execute(
            text(
                "INSERT INTO users (id,username,email,password_hash,full_name,role) VALUES (:user,'historical','historical@example.edu',:hash,'Historical Advisor','ACADEMIC_ADVISOR')"
            ),
            {**ids, "hash": hash_password(INITIAL)},
        )
        db.execute(
            text(
                "INSERT INTO students (id,student_number,name) VALUES (:student,'HISTORY','Historical Student')"
            ),
            ids,
        )
        db.execute(
            text(
                "INSERT INTO model_versions (id,model_name,model_version,feature_schema_version,trained_at,low_threshold,high_threshold,metrics,metadata,artifact_path,is_active) VALUES (:model,:name,:version,:schema,:trained,:low,:high,CAST(:metrics AS jsonb),CAST(:metadata AS jsonb),:artifact,true)"
            ),
            {
                **ids,
                "name": metadata["model_name"],
                "version": metadata["model_version"],
                "schema": metadata["feature_schema_version"],
                "trained": metadata["trained_at"],
                "low": metadata["thresholds"]["low_threshold"],
                "high": metadata["thresholds"]["high_threshold"],
                "metrics": json.dumps(metadata["final_test_metrics"]),
                "metadata": json.dumps(metadata),
                "artifact": metadata["artifact_path"],
            },
        )
        db.execute(
            text(
                "INSERT INTO prediction_results (id,student_id,model_version_id,probability,risk_level,feature_snapshot,explanation,created_by) VALUES (:prediction,:student,:model,.9,'HIGH',CAST(:features AS jsonb),'[]'::jsonb,:user)"
            ),
            {**ids, "features": json.dumps(features)},
        )
        db.execute(
            text(
                "INSERT INTO warnings (id,prediction_id,student_id,risk_level,priority,review_state,assigned_to) VALUES (:warning,:prediction,:student,'HIGH','P1_URGENT','CONFIRMED',:user)"
            ),
            ids,
        )
        db.execute(
            text(
                "INSERT INTO warning_reviews (id,warning_id,reviewer_id,decision,note) VALUES (:review,:warning,:user,'CONFIRMED','Historical academic decision')"
            ),
            ids,
        )
        old_prediction = dict(
            db.execute(
                text("SELECT * FROM prediction_results WHERE id=:prediction"), ids
            )
            .mappings()
            .one()
        )
        old_model = dict(
            db.execute(text("SELECT * FROM model_versions WHERE id=:model"), ids)
            .mappings()
            .one()
        )
        old_warning = dict(
            db.execute(text("SELECT * FROM warnings WHERE id=:warning"), ids)
            .mappings()
            .one()
        )
    migrate()
    with pg_outcomes.connect() as db:
        prediction = dict(
            db.execute(
                text("SELECT * FROM prediction_results WHERE id=:prediction"), ids
            )
            .mappings()
            .one()
        )
        model = dict(
            db.execute(text("SELECT * FROM model_versions WHERE id=:model"), ids)
            .mappings()
            .one()
        )
        assert {key: prediction[key] for key in old_prediction} == old_prediction
        assert {key: model[key] for key in old_model} == old_model
        assert (
            prediction["prediction_stage"] == "FIRST_SEMESTER"
            and prediction["model_target_type"] == "BINARY_DROPOUT"
        )
        assert (
            prediction["class_probabilities"] is None
            and prediction["predicted_outcome"] is None
        )
        assert {
            key: value
            for key, value in db.execute(
                text("SELECT * FROM warnings WHERE id=:warning"), ids
            )
            .mappings()
            .one()
            .items()
            if key in old_warning
        } == old_warning
        assert (
            db.scalar(text("SELECT note FROM warning_reviews WHERE id=:review"), ids)
            == "Historical academic decision"
        )
        assert (
            db.scalar(
                text(
                    "SELECT count(*) FROM model_activation_events WHERE action='MIGRATED_ACTIVE'"
                )
            )
            == 1
        )
        assert compare_metadata(MigrationContext.configure(db), Base.metadata) == []
    command.downgrade(Config("alembic.ini"), "20261011_0009")
    with pg_outcomes.connect() as db:
        assert (
            dict(
                db.execute(
                    text("SELECT * FROM prediction_results WHERE id=:prediction"), ids
                )
                .mappings()
                .one()
            )
            == old_prediction
        )
        assert (
            dict(
                db.execute(text("SELECT * FROM model_versions WHERE id=:model"), ids)
                .mappings()
                .one()
            )
            == old_model
        )
    migrate()


@pytest.mark.parametrize(
    "mutation",
    [
        {"prediction_stage": "FIRST_SEMESTER"},
        {"model_target_type": "BINARY_DROPOUT"},
        {"class_probabilities": None},
        {
            "class_probabilities": {
                "DROPOUT": 0.4,
                "ENROLLED": 0.5,
                "GRADUATE": 0.1,
                "EXTRA": 0,
            }
        },
        {"class_probabilities": {"DROPOUT": 0.4, "ENROLLED": 0.5, "GRADUATE": 0.2}},
        {"probability": 0.3},
        {"predicted_outcome": "DROPOUT"},
        {"class_probabilities": {"DROPOUT": 0.4, "ENROLLED": 1.1, "GRADUATE": -0.5}},
        {"class_probabilities": {"DROPOUT": 0.4, "ENROLLED": ".5", "GRADUATE": 0.1}},
    ],
)
def test_database_enforces_model_stage_and_class_probability_contracts(
    pg_outcomes, mutation
):
    migrate()
    with Session(pg_outcomes) as db:
        student = create_ready_student(db)
        catalog = ModelCatalogService(db)
        catalog.register_new_models()
        model = catalog.repository.get_model_by_version(
            MODEL_VERSIONS[PredictionStage.ENROLLMENT]
        )
        values = {
            "student_id": student.id,
            "model_version_id": model.id,
            "probability": 0.4,
            "risk_level": "MEDIUM",
            "prediction_stage": "ENROLLMENT",
            "model_target_type": "MULTICLASS_OUTCOME",
            "predicted_outcome": "ENROLLED",
            "class_probabilities": {"DROPOUT": 0.4, "ENROLLED": 0.5, "GRADUATE": 0.1},
            "feature_snapshot": {},
            "explanation": [],
        }
        values.update(mutation)
        db.add(PredictionResult(**values))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        assert db.scalar(select(func.count(PredictionResult.id))) == 0


def owner_login(client, username):
    login = client.post(
        "/api/v1/auth/login", json={"username": username, "password": INITIAL}
    )
    assert login.status_code == 200 and login.json()["must_change_password"]
    headers = {"Authorization": "Bearer " + login.json()["access_token"]}
    changed = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"current_password": INITIAL, "new_password": CHANGED},
    )
    assert changed.status_code == 200
    return {"Authorization": "Bearer " + changed.json()["access_token"]}


def create_supported_student(client, headers, case, number):
    values = case["canonical_features"]
    student_values = {
        f.storage_column: values[f.name]
        for f in PREDICTION_FEATURES
        if f.storage_table == "students"
    }
    response = client.post(
        "/api/v1/students",
        headers=headers,
        json={
            "student_number": number,
            "name": "UCI Example Student",
            **student_values,
        },
    )
    assert response.status_code == 201, response.text
    student_id = response.json()["id"]
    admission = {
        f.storage_column: values[f.name]
        for f in PREDICTION_FEATURES
        if f.storage_table == "admission_records"
        and f.source_stage == SourceStage.ENROLLMENT
    }
    response = client.put(
        f"/api/v1/students/{student_id}/admission",
        headers=headers,
        json={
            "admission_method": "UCI example",
            "previous_qualification": "UCI qualification",
            **admission,
        },
    )
    assert response.status_code == 200, response.text
    return student_id


@pytest.mark.model_integration
def test_supported_postgres_dual_stage_workflow_uses_real_models(
    pg_outcomes, monkeypatch
):
    if os.environ.get("RUN_MODEL_INTEGRATION") != "1":
        pytest.skip("Set RUN_MODEL_INTEGRATION=1 for all three real models")
    migrate()
    for suffix, value in {
        "USERNAME": "b1_system",
        "EMAIL": "b1_system@example.edu",
        "FULL_NAME": "B1 System Admin",
        "PASSWORD": INITIAL,
    }.items():
        monkeypatch.setenv("BOOTSTRAP_ADMIN_" + suffix, value)
    with Session(pg_outcomes) as db:
        assert bootstrap_system_admin(db)
    sessions = sessionmaker(pg_outcomes, expire_on_commit=False)
    from app import main

    monkeypatch.setattr(main, "SessionLocal", sessions)

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            admin = owner_login(client, "b1_system")
            users = {}
            headers = {"SYSTEM_ADMIN": admin}
            for role, name in (
                ("ACADEMIC_ADMIN", "b1_academic"),
                ("ACADEMIC_ADVISOR", "b1_advisor"),
            ):
                created = client.post(
                    "/api/v1/users",
                    headers=admin,
                    json={
                        "username": name,
                        "email": name + "@example.edu",
                        "full_name": name,
                        "role": role,
                        "initial_password": INITIAL,
                    },
                )
                assert created.status_code == 201
                users[role] = created.json()
                headers[role] = owner_login(client, name)
            academic = headers["ACADEMIC_ADMIN"]
            student_id = create_supported_student(
                client, academic, CASES[0], "B1-ENROLLMENT"
            )
            url = f"/api/v1/students/{student_id}"
            readiness = client.get(
                url + "/prediction-readiness/stages", headers=academic
            ).json()
            assert readiness["stages"][0]["feature_status"] == "READY"
            assert readiness["stages"][0]["model_status"] == "INACTIVE"
            assert len(readiness["stages"][1]["missing_features"]) == 6
            for stage in PredictionStage:
                version = MODEL_VERSIONS[stage]
                if stage == PredictionStage.FIRST_SEMESTER:
                    sem = {
                        f.storage_column: CASES[0]["canonical_features"][f.name]
                        for f in PREDICTION_FEATURES
                        if f.source_stage == SourceStage.FIRST_SEMESTER
                    }
                    assert (
                        client.put(
                            url + "/semester-1", headers=academic, json=sem
                        ).status_code
                        == 200
                    )
                assert (
                    client.post(
                        f"/api/v1/models/{version}/activate", headers=admin
                    ).json()["error"]["code"]
                    == "MODEL_VALIDATION_REQUIRED"
                )
                validated = client.post(
                    f"/api/v1/models/{version}/validate",
                    headers=admin,
                    json={"student_id": student_id},
                )
                assert validated.status_code == 200, validated.text
                assert not validated.json()["is_active"]
                assert (
                    client.post(
                        f"/api/v1/models/{version}/activate", headers=admin
                    ).status_code
                    == 200
                )
                result = client.post(
                    url + f"/predictions?prediction_stage={stage.value}",
                    headers=academic,
                )
                assert result.status_code == 201, result.text
                body = result.json()
                assert (
                    body["model_version"] == version
                    and body["prediction_stage"] == stage
                )
                assert sum(body["class_probabilities"].values()) == pytest.approx(1)
                assert body["probability"] == body["class_probabilities"]["DROPOUT"]
                if stage == PredictionStage.ENROLLMENT:
                    assert (
                        body["predicted_outcome"] == "ENROLLED"
                        and body["risk_level"] == "MEDIUM"
                    )
                    assert body["class_probabilities"] == pytest.approx(
                        CASES[0]["class_probabilities"]
                    )
                    assert (
                        client.get(url + "/semester-1", headers=academic).status_code
                        == 404
                    )
                    with Session(pg_outcomes) as db:
                        warning = db.scalar(
                            select(Warning).where(
                                Warning.prediction_id == UUID(body["id"])
                            )
                        )
                        warning_id = str(warning.id)
                    assert (
                        client.patch(
                            f"/api/v1/warnings/{warning_id}/assignment",
                            headers=academic,
                            json={"assigned_to": users["ACADEMIC_ADVISOR"]["id"]},
                        ).status_code
                        == 200
                    )
                    reviewed = client.post(
                        f"/api/v1/warnings/{warning_id}/reviews",
                        headers=headers["ACADEMIC_ADVISOR"],
                        json={
                            "decision": "CONFIRMED",
                            "note": "Genuine enrollment warning reviewed",
                        },
                    )
                    assert reviewed.status_code == 201, reviewed.text
            with Session(pg_outcomes) as db:
                assert db.scalar(select(func.count(PredictionResult.id))) == 2
                assert db.scalar(select(func.count(ModelValidation.id))) == 2
                assert (
                    db.get(Warning, UUID(warning_id)).review_state.value == "CONFIRMED"
                )
                assert (
                    db.scalar(
                        select(func.count(ModelVersion.id)).where(
                            ModelVersion.is_active.is_(True)
                        )
                    )
                    == 3
                )
            history = client.get(
                url + "/predictions?prediction_stage=ENROLLMENT",
                headers=headers["ACADEMIC_ADVISOR"],
            ).json()
            assert history["total"] == 1
            for role in ("SYSTEM_ADMIN", "ACADEMIC_ADVISOR"):
                assert (
                    client.post(
                        url + "/predictions?prediction_stage=ENROLLMENT",
                        headers=headers[role],
                    ).status_code
                    == 403
                )
            overview = client.get("/api/v1/dashboard/overview", headers=academic).json()
            assert overview["model"]["version"] == "dropout-logistic-regression-v1"
            assert overview["students"]["current_assessed"] == 1
            profile = client.get(url + "/profile", headers=academic).json()
            assert any(
                w["id"] == warning_id and w["review_state"] == "CONFIRMED"
                for w in profile["warning_history"]
            )
            # Rollback must refuse to discard genuine B1 models/predictions.
            with pytest.raises(RuntimeError, match="Archive"):
                command.downgrade(Config("alembic.ini"), "20261011_0009")
            with Session(pg_outcomes) as db:
                assert db.scalar(select(func.count(PredictionResult.id))) == 2
    finally:
        app.dependency_overrides.clear()


def test_concurrent_activation_is_audited_once_and_scope_uniqueness_is_enforced(
    pg_outcomes,
):
    from concurrent.futures import ThreadPoolExecutor

    migrate()
    with Session(pg_outcomes) as db:
        actor = User(
            username="activation_admin",
            email="activation_admin@example.edu",
            password_hash=hash_password(INITIAL),
            full_name="Activation Admin",
            role=UserRole.SYSTEM_ADMIN,
        )
        db.add(actor)
        db.commit()
        actor_id = actor.id
        student = create_ready_student(db)
        catalog = ModelCatalogService(db)
        catalog.register_new_models()
        version = MODEL_VERSIONS[PredictionStage.ENROLLMENT]
        catalog.validate_model(version, student.id, actor)

    def activate():
        with Session(pg_outcomes) as db:
            return (
                ModelCatalogService(db)
                .activate_model(version, db.get(User, actor_id))
                .is_active
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert list(executor.map(lambda _: activate(), range(2))) == [True, True]
    with Session(pg_outcomes) as db:
        assert db.scalar(select(func.count(ModelActivationEvent.id))) == 1
        enrollment = db.scalar(
            select(ModelVersion).where(ModelVersion.model_version == version)
        )
        first = db.scalar(
            select(ModelVersion).where(
                ModelVersion.model_version
                == MODEL_VERSIONS[PredictionStage.FIRST_SEMESTER]
            )
        )
        first.is_active = True
        db.commit()  # A different multiclass stage has an independent activation scope.
        duplicate = ModelVersion(
            model_name=enrollment.model_name,
            model_version="duplicate-enrollment",
            feature_schema_version=enrollment.feature_schema_version,
            trained_at=enrollment.trained_at,
            low_threshold=enrollment.low_threshold,
            high_threshold=enrollment.high_threshold,
            metrics=enrollment.metrics,
            metadata_json=enrollment.metadata_json,
            artifact_path=enrollment.artifact_path,
            prediction_stage=PredictionStage.ENROLLMENT,
            model_target_type=ModelTargetType.MULTICLASS_OUTCOME,
            is_active=True,
        )
        db.add(duplicate)
        with pytest.raises(IntegrityError, match="one_active_per_scope"):
            db.commit()
        db.rollback()
        assert (
            db.scalar(
                select(func.count(ModelVersion.id)).where(
                    ModelVersion.is_active.is_(True)
                )
            )
            == 2
        )
