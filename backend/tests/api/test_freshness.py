"""B2 policy tests use genuine fitted B1 models and complete source snapshots."""

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select, func, event

from app.ml.feature_schema import PREDICTION_FEATURES, FeatureDataType
from app.ml.inference_features import assemble_prediction_features
from app.ml.outcomes.contracts import PredictionStage, ModelTargetType, MODEL_VERSIONS
from app.models import (
    Student,
    AdmissionRecord,
    FirstSemesterRecord,
    UserRole,
    PredictionResult,
    ModelVersion,
    Warning,
)
from app.services.assessment_service import projection, prediction_metadata
from app.services.model_catalog_service import ModelCatalogService
from app.services.prediction_service import PredictionService
from app.services.outcome_prediction_service import OutcomePredictionService
from app.services.read_model_service import ReadModelService
from tests.api.test_read_models import _data

CASES = json.loads(
    (Path(__file__).parents[1] / "fixtures/outcome_inference_cases.json").read_bytes()
)["cases"]


def source_student(db, number="FRESH-1", *, semester=False, case=0):
    fields = {"students": {}, "admission_records": {}, "first_semester_records": {}}
    for feature in PREDICTION_FEATURES:
        value = CASES[case]["canonical_features"][feature.name]
        fields[feature.storage_table][feature.storage_column] = (
            int(value) if feature.data_type == FeatureDataType.INTEGER else value
        )
    student = Student(
        student_number=number, name="Freshness Example", **fields["students"]
    )
    db.add(student)
    db.flush()
    db.add(
        AdmissionRecord(
            student_id=student.id,
            admission_method="UCI example",
            previous_qualification="Source qualification",
            **fields["admission_records"],
        )
    )
    if semester:
        db.add(
            FirstSemesterRecord(
                student_id=student.id, **fields["first_semester_records"]
            )
        )
    db.commit()
    db.refresh(student)
    return student


def add_semester(db, student):
    fields = {
        feature.storage_column: CASES[0]["canonical_features"][feature.name]
        for feature in PREDICTION_FEATURES
        if feature.storage_table == "first_semester_records"
    }
    db.add(FirstSemesterRecord(student_id=student.id, **fields))
    db.commit()
    db.expire(student)


def fact(db, student):
    return db.execute(select(projection(db, student_ids=[student.id]))).mappings().one()


@pytest.fixture()
def freshness_setup(db_session, create_user):
    actor = create_user(username="fresh_academic", role=UserRole.ACADEMIC_ADMIN)
    owner = create_user(username="fresh_system", role=UserRole.SYSTEM_ADMIN)
    student = source_student(db_session)
    catalog = ModelCatalogService(db_session)
    catalog.catalog()
    for stage in PredictionStage:
        # Genuine validation of semester model uses a separate semester-ready student.
        probe = (
            student
            if stage == PredictionStage.ENROLLMENT
            else source_student(db_session, "FRESH-PROBE", semester=True)
        )
        catalog.validate_model(MODEL_VERSIONS[stage], probe.id, owner)
        catalog.activate_model(MODEL_VERSIONS[stage], owner)
    return student, actor, owner


def predict(db, student, actor, stage=PredictionStage.ENROLLMENT):
    return OutcomePredictionService(db).predict_stage(
        student.id, stage, created_by=actor.id
    )


@pytest.mark.parametrize(
    "field,value,expected",
    [
        ("name", "Corrected Display Name", "CURRENT"),
        ("debtor", 1, "INPUTS_CHANGED"),
        ("scholarship_holder", 1, "INPUTS_CHANGED"),
        ("tuition_fees_up_to_date", 0, "INPUTS_CHANGED"),
        ("age_at_enrollment", None, "INPUTS_INCOMPLETE"),
    ],
)
def test_student_mutations_are_input_aware(
    db_session, freshness_setup, field, value, expected
):
    student, actor, _ = freshness_setup
    result = predict(db_session, student, actor)
    original = db_session.get(PredictionResult, result.id)
    before = (
        original.probability,
        original.predicted_at,
        dict(original.feature_snapshot),
    )
    setattr(student, field, value)
    db_session.commit()
    metadata = prediction_metadata(db_session, [result.id])[result.id]
    assert metadata["prediction_freshness"] == expected
    assert metadata["is_operational_current"] == (expected == "CURRENT")
    assert (
        original.probability,
        original.predicted_at,
        original.feature_snapshot,
    ) == before


def test_admission_decimal_roundtrip_relevant_and_unchanged_updates(
    db_session, freshness_setup
):
    student, actor, _ = freshness_setup
    result = predict(db_session, student, actor)
    student.admission_record.admission_grade = Decimal("125.500000")
    db_session.commit()
    db_session.expire_all()
    assert fact(db_session, student)["assessment_status"] == "CURRENT"
    student.admission_record.admission_grade = Decimal("124.25")
    db_session.commit()
    profile = ReadModelService(db_session).profile(student.id)
    assert (
        profile.assessment_status == "INPUTS_CHANGED"
        and profile.operational_prediction is None
    )
    assert profile.latest_historical_prediction.changed_features == ["admission_grade"]
    assert len(profile.warning_history) == 1
    predict(db_session, student, actor)
    assert fact(db_session, student)["assessment_status"] == "CURRENT"


def test_progression_precedence_and_later_enrollment_does_not_replace_semester(
    db_session, freshness_setup
):
    student, actor, _ = freshness_setup
    enrollment = predict(db_session, student, actor)
    assert fact(db_session, student)["operational_id"] == enrollment.id
    add_semester(db_session, student)
    state = fact(db_session, student)
    assert (
        state["operational_id"] is None
        and state["assessment_status"] == "STAGE_REASSESSMENT_REQUIRED"
    )
    assert (
        prediction_metadata(db_session, [enrollment.id])[enrollment.id][
            "prediction_freshness"
        ]
        == "STAGE_REASSESSMENT_REQUIRED"
    )
    semester = predict(db_session, student, actor, PredictionStage.FIRST_SEMESTER)
    later = predict(db_session, student, actor)
    state = fact(db_session, student)
    assert state["historical_id"] == later.id and state["operational_id"] == semester.id
    assert (
        prediction_metadata(db_session, [later.id])[later.id]["prediction_freshness"]
        == "NOT_SELECTED"
    )
    student.first_semester_record.average_grade = Decimal("10.00")
    db_session.commit()
    states = prediction_metadata(db_session, [semester.id, later.id])
    assert states[semester.id]["prediction_freshness"] == "INPUTS_CHANGED"
    assert states[later.id]["prediction_freshness"] == "STAGE_REASSESSMENT_REQUIRED"
    assert not states[later.id]["is_operational_current"]
    predict(db_session, student, actor, PredictionStage.FIRST_SEMESTER)
    student.first_semester_record.without_evaluations = None
    db_session.commit()
    assert fact(db_session, student)["assessment_status"] == "INPUTS_INCOMPLETE"


def test_binary_fallback_and_activation_changes_eligibility(
    db_session, freshness_setup
):
    student, actor, _ = freshness_setup
    enrollment = predict(db_session, student, actor)
    add_semester(db_session, student)
    binary = PredictionService(db_session).predict_student(
        student.id, created_by=actor.id
    )
    assert fact(db_session, student)["operational_id"] == binary.id
    student.first_semester_record.average_grade = Decimal("11.00")
    db_session.commit()
    assert fact(db_session, student)["assessment_status"] == "INPUTS_CHANGED"
    student.first_semester_record.average_grade = Decimal("12.00")
    db_session.commit()
    assert fact(db_session, student)["operational_id"] == binary.id
    semester = predict(db_session, student, actor, PredictionStage.FIRST_SEMESTER)
    assert fact(db_session, student)["operational_id"] == semester.id
    model = db_session.get(
        ModelVersion, db_session.get(PredictionResult, semester.id).model_version_id
    )
    model.is_active = False
    db_session.commit()
    assert fact(db_session, student)["operational_id"] == binary.id
    assert (
        prediction_metadata(db_session, [semester.id])[semester.id][
            "prediction_freshness"
        ]
        == "MODEL_SUPERSEDED"
    )
    # Disable both semester scopes: enrollment is context, not up-to-date semester risk.
    db_session.get(
        ModelVersion, db_session.get(PredictionResult, binary.id).model_version_id
    ).is_active = False
    db_session.commit()
    assert fact(db_session, student)["operational_id"] is None
    assert (
        db_session.scalar(
            select(func.count(PredictionResult.id)).where(
                PredictionResult.student_id == student.id
            )
        )
        == 3
    )


def test_equal_timestamp_tie_break_and_missing_snapshot_input(
    db_session, freshness_setup
):
    student, actor, _ = freshness_setup
    first = predict(db_session, student, actor)
    second = predict(db_session, student, actor)
    rows = [db_session.get(PredictionResult, r.id) for r in (first, second)]
    stamp = datetime.now(timezone.utc)
    for row in rows:
        row.predicted_at = stamp
    db_session.commit()
    chosen = max(rows, key=lambda p: str(p.id))
    assert fact(db_session, student)["operational_id"] == chosen.id
    chosen.feature_snapshot = {
        k: v for k, v in chosen.feature_snapshot.items() if k != "debtor"
    }
    db_session.commit()
    assert fact(db_session, student)["operational_id"] is None
    assert (
        prediction_metadata(db_session, [chosen.id])[chosen.id]["prediction_freshness"]
        == "INPUTS_CHANGED"
    )


def test_dashboard_registry_profile_and_server_filters_agree(
    client, db_session, freshness_setup, auth_headers
):
    student, actor, _ = freshness_setup
    result = predict(db_session, student, actor)
    headers = auth_headers(actor.username)
    dashboard = client.get("/api/v1/dashboard/overview", headers=headers).json()
    registry = client.get(
        "/api/v1/student-registry",
        params={"assessment_state": "CURRENT"},
        headers=headers,
    ).json()
    profile = client.get(
        f"/api/v1/students/{student.id}/profile", headers=headers
    ).json()
    assert (
        dashboard["students"]["current_assessed"]
        == sum(dashboard["risk_distribution"].values())
        == registry["total"]
        == 1
    )
    assert (
        profile["operational_prediction"]["id"]
        == registry["items"][0]["operational_prediction"]["id"]
        == str(result.id)
    )
    assert (
        client.get(
            "/api/v1/student-registry",
            params={"prediction_stage": "ENROLLMENT", "stage_readiness": "READY"},
            headers=headers,
        ).json()["total"]
        == 2
    )
    assert (
        client.get(
            "/api/v1/student-registry",
            params={"stage_readiness": "READY"},
            headers=headers,
        ).status_code
        == 422
    )
    student.admission_record.admission_grade = Decimal("124")
    db_session.commit()
    dashboard = client.get("/api/v1/dashboard/overview", headers=headers).json()
    assert (
        dashboard["students"]["current_assessed"]
        == sum(dashboard["risk_distribution"].values())
        == 0
    )
    assert dashboard["students"]["reassessment_required"] == 1
    assert dashboard["attention_students"][0]["probability"] is None
    assert (
        client.get(
            "/api/v1/student-registry", params={"current_risk": "NONE"}, headers=headers
        ).json()["total"]
        == 2
    )
    assert (
        client.get(
            "/api/v1/student-registry",
            params={"current_risk": result.risk_level.value},
            headers=headers,
        ).json()["total"]
        == 0
    )


def test_legacy_snapshot_without_hash_and_historical_support_survive(
    db_session, create_user
):
    student, _, current, warning, _ = _data(db_session, create_user)
    assert fact(db_session, student)["operational_id"] == current.id
    before = {
        table: db_session.scalar(select(func.count(table.id)))
        for table in (PredictionResult, Warning)
    }
    student.first_semester_record.average_grade = Decimal("10")
    db_session.commit()
    profile = ReadModelService(db_session).profile(student.id)
    assert (
        profile.operational_prediction is None
        and profile.assessment_status == "INPUTS_CHANGED"
    )
    assert len(profile.interventions) == 1 and len(profile.follow_ups) == 2
    assert all(w.review_state == "CONFIRMED" for w in profile.warning_history)
    for table, count in before.items():
        assert db_session.scalar(select(func.count(table.id))) == count


def test_unavailable_stage_artifact_is_reported_without_inference(
    db_session, freshness_setup, monkeypatch, tmp_path
):
    from app.core.config import get_settings

    student, actor, _ = freshness_setup
    predict(db_session, student, actor)
    monkeypatch.setattr(get_settings(), "ml_outcome_root", str(tmp_path))
    state = fact(db_session, student)
    assert (
        state["assessment_status"] == "MODEL_UNAVAILABLE"
        and state["operational_id"] is None
    )
    assert not state["recommended_model_available"]


def test_supported_crud_routes_update_freshness_without_touching_history(
    client, db_session, freshness_setup, auth_headers
):
    student, actor, _ = freshness_setup
    enrollment = predict(db_session, student, actor)
    headers = auth_headers(actor.username)
    assert (
        client.patch(
            f"/api/v1/students/{student.id}",
            headers=headers,
            json={"name": "Corrected Display"},
        ).status_code
        == 200
    )
    assert client.get(f"/api/v1/predictions/{enrollment.id}", headers=headers).json()[
        "is_operational_current"
    ]
    admission = {
        f.storage_column: CASES[0]["canonical_features"][f.name]
        for f in PREDICTION_FEATURES
        if f.storage_table == "admission_records"
    }
    response = client.put(
        f"/api/v1/students/{student.id}/admission",
        headers=headers,
        json={
            "admission_method": "UCI example",
            "previous_qualification": "Source qualification",
            **admission,
            "admission_grade": 124.25,
        },
    )
    assert response.status_code == 200, response.text
    detail = client.get(f"/api/v1/predictions/{enrollment.id}", headers=headers).json()
    assert detail["prediction_freshness"] == "INPUTS_CHANGED" and detail[
        "changed_features"
    ] == ["admission_grade"]
    assert detail["probability"] == enrollment.probability
    assert (
        client.post(
            f"/api/v1/students/{student.id}/predictions?prediction_stage=ENROLLMENT",
            headers=headers,
        ).status_code
        == 201
    )
    semester = {
        f.storage_column: CASES[0]["canonical_features"][f.name]
        for f in PREDICTION_FEATURES
        if f.storage_table == "first_semester_records"
    }
    assert (
        client.put(
            f"/api/v1/students/{student.id}/semester-1", headers=headers, json=semester
        ).status_code
        == 200
    )
    profile = client.get(
        f"/api/v1/students/{student.id}/profile", headers=headers
    ).json()
    assert (
        profile["assessment_status"] == "STAGE_REASSESSMENT_REQUIRED"
        and profile["operational_prediction"] is None
    )
    assert len(profile["open_warnings"]) >= 1


def test_both_import_paths_create_assessable_inputs_and_preserve_existing_predictions(
    client, db_session, freshness_setup, auth_headers
):
    from tests.api.test_imports import upload, csv_bytes, valid_row
    from tests.api.test_staged_imports import stage, commit

    student, actor, _ = freshness_setup
    original = predict(db_session, student, actor)
    headers = auth_headers(actor.username)
    response = upload(client, headers, csv_bytes([valid_row("FRESH-CSV")]))
    assert response.status_code == 200, response.text
    batch = stage(client, headers, [valid_row("FRESH-STAGED")])
    response = commit(client, headers, batch)
    assert response.status_code == 200, response.text
    for number in ("FRESH-CSV", "FRESH-STAGED"):
        imported = db_session.scalar(
            select(Student).where(Student.student_number == number)
        )
        state = fact(db_session, imported)
        assert (
            state["first_semester_ready"]
            and state["assessment_status"] == "NO_PREDICTION"
        )
        result = predict(db_session, imported, actor, PredictionStage.FIRST_SEMESTER)
        assert result.is_operational_current
        imported.scholarship_holder = 1 - imported.scholarship_holder
        db_session.commit()
        assert fact(db_session, imported)["assessment_status"] == "INPUTS_CHANGED"
    assert fact(db_session, student)["operational_id"] == original.id
    assert (
        db_session.get(PredictionResult, original.id).probability
        == original.probability
    )


def test_corrupt_snapshot_is_historical_and_no_current_low_is_invented(
    db_session, freshness_setup
):
    student, actor, _ = freshness_setup
    result = predict(db_session, student, actor)
    pred = db_session.get(PredictionResult, result.id)
    pred.feature_snapshot = {**pred.feature_snapshot, "debtor": "invalid"}
    db_session.commit()
    profile = ReadModelService(db_session).profile(student.id)
    assert (
        profile.operational_prediction is None
        and profile.latest_historical_prediction.prediction_freshness
        == "INPUTS_CHANGED"
    )
    assert profile.latest_historical_prediction.feature_snapshot["debtor"] == "invalid"
    empty = source_student(db_session, "FRESH-NEVER-ASSESSED")
    assert fact(db_session, empty)["assessment_status"] == "NO_PREDICTION"
