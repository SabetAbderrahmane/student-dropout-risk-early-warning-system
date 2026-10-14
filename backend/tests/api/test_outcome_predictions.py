"""Real trained B1 models behind the existing protected API and academic workflow."""

from uuid import UUID

import pytest
from app.ml.outcomes.contracts import MODEL_VERSIONS, PredictionStage
from app.models import (
    FirstSemesterRecord,
    ModelActivationEvent,
    ModelValidation,
    ModelVersion,
    PredictionResult,
    UserRole,
    Warning,
)
from sqlalchemy import func, select
from tests.api.test_predictions import create_ready_student


def identities(create_user, auth_headers):
    return {
        role: auth_headers(create_user(username=role.value.lower(), role=role).username)
        for role in UserRole
    }


def provision_models(client, student, headers):
    response = client.get("/api/v1/models", headers=headers[UserRole.SYSTEM_ADMIN])
    assert response.status_code == 200
    for version in MODEL_VERSIONS.values():
        url = f"/api/v1/models/{version}"
        assert (
            client.post(
                url + "/activate", headers=headers[UserRole.SYSTEM_ADMIN]
            ).status_code
            == 409
        )
        validated = client.post(
            url + "/validate",
            json={"student_id": str(student.id)},
            headers=headers[UserRole.SYSTEM_ADMIN],
        )
        assert validated.status_code == 200, validated.text
        assert validated.json()["validation_id"] is not None
        assert validated.json()["is_active"] is False
        activated = client.post(
            url + "/activate", headers=headers[UserRole.SYSTEM_ADMIN]
        )
        assert activated.status_code == 200, activated.text
        assert activated.json()["is_active"] is True


def test_registration_is_inactive_validation_is_reversible_and_legacy_stays_active(
    client, db_session, create_user, auth_headers
):
    headers = identities(create_user, auth_headers)
    student = create_ready_student(db_session)
    catalog = client.get("/api/v1/models", headers=headers[UserRole.ACADEMIC_ADVISOR])
    assert catalog.status_code == 200
    entries = catalog.json()["items"]
    assert len(entries) == 3
    assert all(
        not item["is_active"]
        for item in entries
        if item["model_target_type"] == "MULTICLASS_OUTCOME"
    )
    provision_models(client, student, headers)
    assert db_session.scalar(select(func.count(PredictionResult.id))) == 0
    assert db_session.scalar(select(func.count(Warning.id))) == 0
    assert db_session.scalar(select(func.count(ModelValidation.id))) == 2
    assert db_session.scalar(select(func.count(ModelActivationEvent.id))) == 2
    assert (
        db_session.scalar(
            select(func.count(ModelVersion.id)).where(ModelVersion.is_active.is_(True))
        )
        == 3
    )
    assert (
        client.get(
            "/api/v1/models/current", headers=headers[UserRole.ACADEMIC_ADVISOR]
        ).json()["version"]
        == "dropout-logistic-regression-v1"
    )


def test_genuine_enrollment_without_semester_and_first_semester_reassessment(
    client, db_session, create_user, auth_headers
):
    headers = identities(create_user, auth_headers)
    validation_student = create_ready_student(db_session, "VALIDATION")
    provision_models(client, validation_student, headers)
    student = create_ready_student(db_session, "ENROLLMENT")
    semester = student.first_semester_record
    db_session.delete(semester)
    db_session.commit()
    db_session.expire_all()
    url = f"/api/v1/students/{student.id}"
    readiness = client.get(
        url + "/prediction-readiness/stages", headers=headers[UserRole.ACADEMIC_ADMIN]
    ).json()
    assert [item["status"] for item in readiness["stages"]] == ["READY", "NOT_READY"]
    assert len(readiness["stages"][1]["missing_features"]) == 6
    assert (
        client.post(
            url + "/predictions?prediction_stage=FIRST_SEMESTER",
            headers=headers[UserRole.ACADEMIC_ADMIN],
        ).status_code
        == 409
    )
    enrollment = client.post(
        url + "/predictions?prediction_stage=ENROLLMENT",
        headers=headers[UserRole.ACADEMIC_ADMIN],
    )
    assert enrollment.status_code == 201, enrollment.text
    body = enrollment.json()
    assert len(body["feature_snapshot"]) == 21
    assert body["prediction_stage"] == "ENROLLMENT"
    assert body["model_version"] == MODEL_VERSIONS[PredictionStage.ENROLLMENT]
    assert set(body["class_probabilities"]) == {"DROPOUT", "ENROLLED", "GRADUATE"}
    assert sum(body["class_probabilities"].values()) == pytest.approx(1)
    assert (
        body["probability"]
        == body["dropout_probability"]
        == body["class_probabilities"]["DROPOUT"]
    )
    db_session.add(
        FirstSemesterRecord(
            student_id=student.id,
            credited_units=0,
            enrolled_units=6,
            evaluations=6,
            approved_units=4,
            average_grade=12,
            without_evaluations=0,
        )
    )
    db_session.commit()
    db_session.expire_all()
    later = client.post(
        url + "/predictions?prediction_stage=FIRST_SEMESTER",
        headers=headers[UserRole.ACADEMIC_ADMIN],
    )
    assert later.status_code == 201, later.text
    assert len(later.json()["feature_snapshot"]) == 27
    assert (
        later.json()["model_version"] == MODEL_VERSIONS[PredictionStage.FIRST_SEMESTER]
    )
    history = client.get(
        url + "/predictions?prediction_stage=ENROLLMENT",
        headers=headers[UserRole.ACADEMIC_ADVISOR],
    ).json()
    assert history["total"] == 1 and history["items"][0]["id"] == body["id"]
    for prediction in (body, later.json()):
        warning = db_session.scalar(
            select(Warning).where(Warning.prediction_id == UUID(prediction["id"]))
        )
        assert (warning is not None) == (prediction["risk_level"] != "LOW")
        if warning:
            assert warning.risk_level.value == prediction["risk_level"]
    profile = client.get(
        url + "/profile", headers=headers[UserRole.ACADEMIC_ADVISOR]
    ).json()
    assert {item["prediction_stage"] for item in profile["prediction_history"]} == {
        "ENROLLMENT",
        "FIRST_SEMESTER",
    }
    overview = client.get(
        "/api/v1/dashboard/overview?prediction_scope=LEGACY_BINARY_FIRST_SEMESTER", headers=headers[UserRole.ACADEMIC_ADMIN]
    ).json()
    assert overview["prediction_scope"] == "LEGACY_BINARY_FIRST_SEMESTER"
    assert overview["students"]["with_latest_prediction"] == 0
    assert sum(overview["risk_distribution"].values()) == 0


@pytest.mark.parametrize("role", [UserRole.SYSTEM_ADMIN, UserRole.ACADEMIC_ADVISOR])
def test_stage_prediction_execution_remains_academic_admin_only(
    role, client, db_session, create_user, auth_headers
):
    headers = identities(create_user, auth_headers)
    student = create_ready_student(db_session)
    url = f"/api/v1/students/{student.id}/predictions?prediction_stage=ENROLLMENT"
    assert client.post(url, headers=headers[role]).status_code == 403
    assert client.post(url).status_code == 401
    assert (
        client.post(
            "/api/v1/predictions/batch?prediction_stage=FIRST_SEMESTER",
            headers=headers[role],
        ).status_code
        == 403
    )


@pytest.mark.parametrize("role", [UserRole.ACADEMIC_ADMIN, UserRole.ACADEMIC_ADVISOR])
def test_activation_and_validation_are_system_admin_only(
    role, client, db_session, create_user, auth_headers
):
    headers = identities(create_user, auth_headers)
    student = create_ready_student(db_session)
    for version in MODEL_VERSIONS.values():
        assert (
            client.post(
                f"/api/v1/models/{version}/validate",
                json={"student_id": str(student.id)},
                headers=headers[role],
            ).status_code
            == 403
        )
        assert (
            client.post(
                f"/api/v1/models/{version}/activate", headers=headers[role]
            ).status_code
            == 403
        )


def test_inactive_incompatible_and_invalid_stages_are_explicit(
    client, db_session, create_user, auth_headers
):
    headers = identities(create_user, auth_headers)
    student = create_ready_student(db_session)
    url = f"/api/v1/students/{student.id}/predictions"
    assert (
        client.post(
            url + "?prediction_stage=ENROLLMENT",
            headers=headers[UserRole.ACADEMIC_ADMIN],
        ).json()["error"]["code"]
        == "STAGE_MODEL_INACTIVE"
    )
    assert (
        client.post(
            url + "?prediction_stage=SECOND_SEMESTER",
            headers=headers[UserRole.ACADEMIC_ADMIN],
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/models/dropout-logistic-regression-v1/activate",
            headers=headers[UserRole.SYSTEM_ADMIN],
        ).json()["error"]["code"]
        == "INCOMPATIBLE_STAGE_MODEL"
    )
    student.admission_record.application_order = 99
    # Database constraints independently reject this value; validate the pure
    # assembler before attempting persistence of an impossible fixture.
    from app.ml.outcomes.features import assemble

    assembly = assemble(student, PredictionStage.ENROLLMENT)
    assert "application_order" in assembly.invalid_features
    assert not assembly.ready


def test_legacy_api_omission_keeps_binary_semantics(
    client, db_session, create_user, auth_headers
):
    headers = identities(create_user, auth_headers)
    student = create_ready_student(db_session)
    response = client.post(
        f"/api/v1/students/{student.id}/predictions",
        headers=headers[UserRole.ACADEMIC_ADMIN],
    )
    assert response.status_code == 201
    body = response.json()
    assert (
        body["model_target_type"] == "BINARY_DROPOUT"
        and body["prediction_stage"] == "FIRST_SEMESTER"
    )
    assert body["predicted_outcome"] is None and body["class_probabilities"] is None
    assert len(body["feature_snapshot"]) == 30


@pytest.mark.model_integration
@pytest.mark.parametrize("case_index", [0, 1, 2])
def test_frozen_real_inference_and_enrolled_dropout_warning(
    case_index, client, db_session, create_user, auth_headers
):
    import json
    from pathlib import Path

    from app.ml.feature_schema import PREDICTION_FEATURES

    case = json.loads(
        (
            Path(__file__).parents[1] / "fixtures/outcome_inference_cases.json"
        ).read_bytes()
    )["cases"][case_index]
    headers = identities(create_user, auth_headers)
    student = create_ready_student(db_session)
    provision_models(client, student, headers)
    records = {
        "students": student,
        "admission_records": student.admission_record,
        "first_semester_records": student.first_semester_record,
    }
    for feature in PREDICTION_FEATURES:
        setattr(
            records[feature.storage_table],
            feature.storage_column,
            case["canonical_features"][feature.name],
        )
    db_session.commit()
    db_session.expire_all()
    stage = case.get("prediction_stage")
    query = f"?prediction_stage={stage}" if case_index != 2 else ""
    response = client.post(
        f"/api/v1/students/{student.id}/predictions" + query,
        headers=headers[UserRole.ACADEMIC_ADMIN],
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["probability"] == pytest.approx(
        case.get("persisted_class_probabilities", case.get("class_probabilities", {}))[
            "DROPOUT"
        ]
        if case_index != 2
        else case["dropout_probability"],
        abs=1e-12,
    )
    assert body["risk_level"] == case["risk_level"]
    warning = db_session.scalar(
        select(Warning).where(Warning.prediction_id == UUID(body["id"]))
    )
    assert warning is not None
    if case_index == 2:
        assert body["model_version"] == "dropout-logistic-regression-v1"
        assert body["class_probabilities"] is None and body["predicted_outcome"] is None
    else:
        assert body["predicted_outcome"] == "ENROLLED"
        assert body["class_probabilities"] == pytest.approx(
            case.get("persisted_class_probabilities", case["class_probabilities"]),
            abs=1e-12,
        )
        assert warning.risk_level.value == "MEDIUM"
