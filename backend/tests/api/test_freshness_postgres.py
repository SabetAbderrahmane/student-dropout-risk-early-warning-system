"""Real PostgreSQL B2 migration, input, snapshot, paging and concurrency evidence."""

import os
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from app.core.config import get_settings
from app.core.security import hash_password
from tests.auth_context import authenticated_actor
from app.ml.outcomes.contracts import MODEL_VERSIONS, PredictionStage
from app.models import (
    FollowUp,
    Intervention,
    ModelVersion,
    PredictionResult,
    User,
    UserRole,
    Warning,
)
from app.models.casework import (
    FollowUpMethod,
    FollowUpStatus,
    InterventionStatus,
    InterventionType,
)
from app.models.user import UserLoginIdentifier
from app.models.warning import (
    ReviewDecision,
    WarningReview,
    WarningReviewState,
)
from app.services.assessment_service import (
    prediction_metadata,
    projection,
)
from app.services.model_catalog_service import ModelCatalogService
from app.services.prediction_service import PredictionService
from app.services.read_model_service import ReadModelService
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from tests.api.test_freshness import add_semester, fact, predict, source_student

pytestmark = pytest.mark.model_integration


@pytest.fixture()
def freshness_pg(monkeypatch):
    url = os.environ.get("FRESHNESS_TEST_DATABASE_URL")
    if not url or os.environ.get("RUN_MODEL_INTEGRATION") != "1":
        pytest.skip(
            "Set FRESHNESS_TEST_DATABASE_URL and RUN_MODEL_INTEGRATION=1 to use disposable PostgreSQL databases"
        )
    root = create_engine(url, isolation_level="AUTOCOMMIT")
    assert root.dialect.name == "postgresql"
    name = "freshness_b2_test_" + uuid4().hex
    with root.connect() as db:
        db.execute(text(f'CREATE DATABASE "{name}"'))
    target = make_url(url).set(database=name)
    engine = create_engine(target)
    monkeypatch.setattr(
        get_settings(), "database_url", target.render_as_string(hide_password=False)
    )
    try:
        yield engine
    finally:
        engine.dispose()
        with root.connect() as db:
            db.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        root.dispose()


def seed(db, *, activate=True):
    users = []
    for name, role in [
        ("pg_system", UserRole.SYSTEM_ADMIN),
        ("pg_academic", UserRole.ACADEMIC_ADMIN),
        ("pg_advisor", UserRole.ACADEMIC_ADVISOR),
    ]:
        user = User(
            username=name,
            email=name + "@example.edu",
            full_name=name,
            role=role,
            password_hash=hash_password("Freshness-test-password-123!"),
        )
        db.add(user)
        db.flush()
        db.add_all(
            [
                UserLoginIdentifier(identifier=value, user_id=user.id)
                for value in (user.username, user.email)
            ]
        )
        users.append(user)
    db.commit()
    student = source_student(db)
    catalog = ModelCatalogService(db)
    catalog.catalog()
    if activate:
        probe = source_student(db, "PG-PROBE", semester=True)
        for stage in PredictionStage:
            catalog.validate_model(
                MODEL_VERSIONS[stage], probe.id, authenticated_actor(db, users[0])
            )
            catalog.activate_model(
                MODEL_VERSIONS[stage], authenticated_actor(db, users[0])
            )
    return student, users


def migrate(revision="head"):
    command.upgrade(Config("alembic.ini"), revision)


def add_support(db, student, prediction, users):
    warning = db.scalar(select(Warning).where(Warning.prediction_id == prediction.id))
    assert warning is not None
    warning.assigned_to = users[2].id
    warning.review_state = WarningReviewState.CONFIRMED
    db.add(
        WarningReview(
            warning_id=warning.id,
            reviewer_id=users[2].id,
            decision=ReviewDecision.CONFIRMED,
            note="Keep the original academic decision",
        )
    )
    intervention = Intervention(
        student_id=student.id,
        warning_id=warning.id,
        type=InterventionType.ACADEMIC_ADVISING,
        title="Original support plan",
        description="Historical decision",
        priority=warning.priority,
        status=InterventionStatus.IN_PROGRESS,
        assigned_to=users[2].id,
        start_date=date.today(),
        created_by=users[1].id,
    )
    db.add(intervention)
    db.flush()
    db.add(
        FollowUp(
            intervention_id=intervention.id,
            student_id=student.id,
            assigned_to=users[2].id,
            scheduled_for=datetime.now(UTC) - timedelta(days=1),
            method=FollowUpMethod.IN_PERSON,
            purpose="Original follow-up",
            status=FollowUpStatus.SCHEDULED,
            created_by=users[1].id,
        )
    )
    db.commit()


def historical_dump(engine):
    with engine.connect() as connection:
        return {
            table: connection.execute(
                text(f"SELECT row_to_json(t)::text FROM {table} t ORDER BY id")
            )
            .scalars()
            .all()
            for table in (
                "model_versions",
                "prediction_results",
                "warnings",
                "warning_reviews",
                "interventions",
                "follow_ups",
            )
        }


def test_populated_b1_migration_is_index_only_and_roundtrips(freshness_pg):
    # Seed using current ORM, then remove later additive schema before testing B2.
    migrate()
    with Session(freshness_pg, expire_on_commit=False) as db:
        student, users = seed(db)
        enrollment = predict(db, student, users[1])
        add_support(db, student, enrollment, users)
        add_semester(db, student)
        predict(db, student, users[1], PredictionStage.FIRST_SEMESTER)
        PredictionService(db).predict_student(
            student.id, actor=authenticated_actor(db, users[1])
        )
    command.downgrade(Config("alembic.ini"), "20261011_0010")
    original = historical_dump(freshness_pg)
    migrate("20261013_0011")
    assert historical_dump(freshness_pg) == original
    with freshness_pg.connect() as db:
        assert (
            db.scalar(text("SELECT version_num FROM alembic_version"))
            == "20261013_0011"
        )
        names = (
            db.execute(
                text(
                    "SELECT indexname FROM pg_indexes WHERE tablename='prediction_results'"
                )
            )
            .scalars()
            .all()
        )
        assert {
            "ix_predictions_student_model_latest",
            "ix_predictions_student_latest",
            "ix_predictions_student_stage",
        } <= set(names)
    command.downgrade(Config("alembic.ini"), "20261011_0010")
    assert historical_dump(freshness_pg) == original
    migrate()


@pytest.mark.parametrize(
    "record,field,value,expected",
    [
        ("student", "name", "Corrected name", "CURRENT"),
        ("student", "debtor", 1, "INPUTS_CHANGED"),
        ("student", "scholarship_holder", None, "INPUTS_INCOMPLETE"),
        ("admission_record", "admission_grade", Decimal("125.50000000"), "CURRENT"),
        ("admission_record", "admission_grade", Decimal("125.504"), "CURRENT"),
        ("admission_record", "admission_grade", Decimal("125.505"), "INPUTS_CHANGED"),
        ("first_semester_record", "average_grade", Decimal("11.25"), "INPUTS_CHANGED"),
        ("first_semester_record", "without_evaluations", None, "INPUTS_INCOMPLETE"),
    ],
)
def test_postgres_numeric_and_stage_input_changes(
    freshness_pg, record, field, value, expected
):
    migrate()
    with Session(freshness_pg, expire_on_commit=False) as db:
        student, users = seed(db)
        enrollment = predict(db, student, users[1])
        if record == "first_semester_record":
            add_semester(db, student)
            result = predict(db, student, users[1], PredictionStage.FIRST_SEMESTER)
        else:
            result = enrollment
        setattr(
            student if record == "student" else getattr(student, record), field, value
        )
        db.commit()
        db.expire_all()
        metadata = prediction_metadata(db, [result.id])[result.id]
        assert metadata["prediction_freshness"] == expected
        assert fact(db, student)["operational_id"] == (
            result.id if expected == "CURRENT" else None
        )
        assert db.get(PredictionResult, result.id).probability == result.probability
        if record == "first_semester_record":
            from app.services.assessment_service import input_changes

            assert (
                input_changes(student, db.get(PredictionResult, enrollment.id))[
                    "changed_features"
                ]
                == []
            )


def test_stage_precedence_consistency_support_and_sql_pagination(
    freshness_pg, monkeypatch
):
    migrate()
    with Session(freshness_pg, expire_on_commit=False) as db:
        student, users = seed(db)
        enrollment = predict(db, student, users[1])
        add_support(db, student, enrollment, users)
        add_semester(db, student)
        assert fact(db, student)["assessment_status"] == "STAGE_REASSESSMENT_REQUIRED"
        semester = predict(db, student, users[1], PredictionStage.FIRST_SEMESTER)
        later = predict(db, student, users[1])
        assert fact(db, student)["operational_id"] == semester.id
        # Two decimal grades and original support facts survive a newer LOW result.
        before = historical_dump(freshness_pg)
        profile = ReadModelService(db).profile(student.id)
        assert (
            profile.operational_prediction.id == semester.id
            and profile.latest_historical_prediction.id == later.id
        )
        assert (
            profile.interventions[0].status == "IN_PROGRESS"
            and profile.follow_ups[0].effective_status == "OVERDUE"
        )
        assert (
            profile.warning_history[-1].reviews[0].note
            == "Keep the original academic decision"
        )
        for n in range(1000):
            db.add(
                __import__("app.models", fromlist=["Student"]).Student(
                    student_number=f"EMPTY-{n:04d}", name="Unassessed"
                )
            )
        db.commit()
        # Warm trusted verification, then forbid inference while querying freshness.
        fact(db, student)
        from app.ml.outcomes.bundle import OutcomeBundle

        monkeypatch.setattr(
            OutcomeBundle,
            "predict_proba",
            lambda *a, **k: pytest.fail("Freshness reran model inference"),
        )
        statements = []
        event.listen(
            freshness_pg,
            "before_cursor_execute",
            lambda *args: statements.append(args[2]),
        )
        params = dict(
            page=1,
            page_size=25,
            search=None,
            course_code=None,
            risk_level=None,
            warning_state=None,
            intervention_state=None,
            prediction_readiness=None,
            sort="risk_probability",
            order="desc",
        )
        rows = ReadModelService(db).registry(**params)
        assert (
            rows.total == 1002
            and len(rows.items) == 25
            and rows.items[0].operational_prediction.id == semester.id
        )
        assert len(statements) <= 16
        dashboard = ReadModelService(db).dashboard()
        assert (
            dashboard.students.current_assessed
            == sum(dashboard.risk_distribution.model_dump().values())
            == 1
        )
        assert dashboard.students.without_predictions == 1001
        assert (
            ReadModelService(db)
            .registry(**{**params, "assessment_state": "CURRENT"})
            .total
            == 1
        )
        assert (
            ReadModelService(db).registry(**{**params, "current_risk": "NONE"}).total
            == 1001
        )
        assert (
            ReadModelService(db)
            .registry(**{**params, "prediction_stage": PredictionStage.FIRST_SEMESTER})
            .total
            == 1
        )
        assert historical_dump(freshness_pg) == before


def test_repeatable_read_does_not_mix_concurrent_input_or_activation_versions(
    freshness_pg,
):
    migrate()
    with Session(freshness_pg, expire_on_commit=False) as db:
        student, users = seed(db)
        result = predict(db, student, users[1])
        student_id = student.id
    with Session(
        bind=freshness_pg.execution_options(isolation_level="REPEATABLE READ")
    ) as reader:
        state = (
            reader.execute(select(projection(reader, student_ids=[student_id])))
            .mappings()
            .one()
        )
        assert state["operational_id"] == result.id
        with Session(freshness_pg) as writer:
            from app.models import AdmissionRecord

            admission = writer.scalar(
                select(AdmissionRecord).where(AdmissionRecord.student_id == student_id)
            )
            admission.admission_grade = Decimal("124.00")
            writer.commit()
        snapshot = ReadModelService(reader).profile(student_id)
        assert (
            snapshot.assessment_status == "CURRENT"
            and snapshot.admission.admission_grade == 125.5
        )
        assert snapshot.assessment_as_of is not None
    with Session(freshness_pg) as reader:
        snapshot = ReadModelService(reader).profile(student_id)
        assert (
            snapshot.assessment_status == "INPUTS_CHANGED"
            and snapshot.operational_prediction is None
        )
    with Session(
        bind=freshness_pg.execution_options(isolation_level="REPEATABLE READ")
    ) as reader:
        reader.execute(select(projection(reader, student_ids=[student_id]))).all()
        with Session(freshness_pg) as writer:
            model = writer.scalar(
                select(ModelVersion).where(
                    ModelVersion.model_version
                    == MODEL_VERSIONS[PredictionStage.ENROLLMENT]
                )
            )
            model.is_active = False
            writer.commit()
        assert (
            prediction_metadata(reader, [result.id])[result.id]["prediction_freshness"]
            == "INPUTS_CHANGED"
        )
    with Session(freshness_pg) as reader:
        assert (
            ReadModelService(reader).profile(student_id).recommended_model_available
            is False
        )
