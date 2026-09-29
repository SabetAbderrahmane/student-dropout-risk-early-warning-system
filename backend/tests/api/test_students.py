from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AdmissionRecord, FirstSemesterRecord, Student, UserRole

STUDENT_PAYLOAD = {
    "student_number": "STU-001",
    "name": "Amina Rahal",
    "gender": "Female",
}
ADMISSION_PAYLOAD = {
    "admission_method": "General admission",
    "admission_grade": 15.75,
    "previous_qualification": "High school diploma",
    "previous_qualification_grade": 16.25,
}
SEMESTER_PAYLOAD = {
    "credited_units": 0,
    "enrolled_units": 6,
    "evaluations": 6,
    "approved_units": 5,
    "average_grade": 14.5,
}


@pytest.fixture()
def academic_admin_headers(
    client: TestClient, create_user, auth_headers
) -> dict[str, str]:
    create_user(username="academic_admin", role=UserRole.ACADEMIC_ADMIN)
    return auth_headers("academic_admin")


@pytest.fixture()
def advisor_headers(client: TestClient, create_user, auth_headers) -> dict[str, str]:
    create_user(username="advisor", role=UserRole.ACADEMIC_ADVISOR)
    return auth_headers("advisor")


def create_student(client: TestClient, headers: dict[str, str], **overrides) -> dict:
    response = client.post(
        "/api/v1/students",
        headers=headers,
        json={**STUDENT_PAYLOAD, **overrides},
    )
    assert response.status_code == 201
    return response.json()


def test_academic_admin_can_create_and_retrieve_student(
    client: TestClient, academic_admin_headers
) -> None:
    student = create_student(client, academic_admin_headers)

    response = client.get(
        f"/api/v1/students/{student['id']}", headers=academic_admin_headers
    )

    assert response.status_code == 200
    assert response.json()["student_number"] == "STU-001"
    assert response.json()["name"] == "Amina Rahal"


def test_duplicate_student_number_is_rejected(
    client: TestClient, academic_admin_headers
) -> None:
    create_student(client, academic_admin_headers)

    response = client.post(
        "/api/v1/students",
        headers=academic_admin_headers,
        json={**STUDENT_PAYLOAD, "name": "Another Student"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "STUDENT_NUMBER_ALREADY_EXISTS"


def test_student_can_be_updated(client: TestClient, academic_admin_headers) -> None:
    student = create_student(client, academic_admin_headers)

    response = client.patch(
        f"/api/v1/students/{student['id']}",
        headers=academic_admin_headers,
        json={"student_number": "STU-002", "name": "Amina El Rahal", "gender": None},
    )

    assert response.status_code == 200
    assert response.json()["student_number"] == "STU-002"
    assert response.json()["name"] == "Amina El Rahal"
    assert response.json()["gender"] is None


def test_student_delete_cascades_related_records(
    client: TestClient,
    academic_admin_headers,
    db_session: Session,
) -> None:
    student = create_student(client, academic_admin_headers)
    client.put(
        f"/api/v1/students/{student['id']}/admission",
        headers=academic_admin_headers,
        json=ADMISSION_PAYLOAD,
    )
    client.put(
        f"/api/v1/students/{student['id']}/semester-1",
        headers=academic_admin_headers,
        json=SEMESTER_PAYLOAD,
    )

    response = client.delete(
        f"/api/v1/students/{student['id']}", headers=academic_admin_headers
    )

    assert response.status_code == 204
    assert db_session.scalar(select(func.count(AdmissionRecord.id))) == 0
    assert db_session.scalar(select(func.count(FirstSemesterRecord.id))) == 0


def test_nonexistent_student_returns_controlled_404(
    client: TestClient, academic_admin_headers
) -> None:
    response = client.get(f"/api/v1/students/{uuid4()}", headers=academic_admin_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "STUDENT_NOT_FOUND"


def test_advisor_can_view_but_cannot_create_student(
    client: TestClient, academic_admin_headers, advisor_headers
) -> None:
    student = create_student(client, academic_admin_headers)

    read_response = client.get(
        f"/api/v1/students/{student['id']}", headers=advisor_headers
    )
    create_response = client.post(
        "/api/v1/students", headers=advisor_headers, json=STUDENT_PAYLOAD
    )

    assert read_response.status_code == 200
    assert create_response.status_code == 403
    assert create_response.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"


@pytest.mark.parametrize("method", ["patch", "delete"])
def test_advisor_cannot_modify_or_delete_student(
    method: str,
    client: TestClient,
    academic_admin_headers,
    advisor_headers,
) -> None:
    student = create_student(client, academic_admin_headers)

    if method == "patch":
        response = client.patch(
            f"/api/v1/students/{student['id']}",
            headers=advisor_headers,
            json={"name": "Unauthorized Change"},
        )
    else:
        response = client.delete(
            f"/api/v1/students/{student['id']}", headers=advisor_headers
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"


def test_system_admin_has_read_only_student_access(
    client: TestClient, academic_admin_headers, create_user, auth_headers
) -> None:
    create_student(client, academic_admin_headers)
    create_user(username="system_admin", role=UserRole.SYSTEM_ADMIN)
    headers = auth_headers("system_admin")

    assert client.get("/api/v1/students", headers=headers).status_code == 200
    assert (
        client.post(
            "/api/v1/students", headers=headers, json=STUDENT_PAYLOAD
        ).status_code
        == 403
    )


def test_admission_record_is_created_updated_and_retrieved(
    client: TestClient, academic_admin_headers, db_session: Session
) -> None:
    student = create_student(client, academic_admin_headers)
    endpoint = f"/api/v1/students/{student['id']}/admission"

    created = client.put(
        endpoint, headers=academic_admin_headers, json=ADMISSION_PAYLOAD
    )
    updated = client.put(
        endpoint,
        headers=academic_admin_headers,
        json={**ADMISSION_PAYLOAD, "admission_grade": 17.0},
    )
    retrieved = client.get(endpoint, headers=academic_admin_headers)

    assert created.status_code == 200
    assert updated.status_code == 200
    assert created.json()["id"] == updated.json()["id"]
    assert retrieved.json()["admission_grade"] == 17.0
    assert db_session.scalar(select(func.count(AdmissionRecord.id))) == 1


def test_missing_admission_record_returns_controlled_404(
    client: TestClient, academic_admin_headers
) -> None:
    student = create_student(client, academic_admin_headers)

    response = client.get(
        f"/api/v1/students/{student['id']}/admission",
        headers=academic_admin_headers,
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ADMISSION_RECORD_NOT_FOUND"


def test_admission_for_nonexistent_student_returns_student_404(
    client: TestClient, academic_admin_headers
) -> None:
    response = client.put(
        f"/api/v1/students/{uuid4()}/admission",
        headers=academic_admin_headers,
        json=ADMISSION_PAYLOAD,
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "STUDENT_NOT_FOUND"


def test_advisor_can_read_but_not_modify_admission(
    client: TestClient, academic_admin_headers, advisor_headers
) -> None:
    student = create_student(client, academic_admin_headers)
    endpoint = f"/api/v1/students/{student['id']}/admission"
    client.put(endpoint, headers=academic_admin_headers, json=ADMISSION_PAYLOAD)

    assert client.get(endpoint, headers=advisor_headers).status_code == 200
    assert (
        client.put(
            endpoint, headers=advisor_headers, json=ADMISSION_PAYLOAD
        ).status_code
        == 403
    )


def test_first_semester_record_is_created_updated_and_retrieved(
    client: TestClient, academic_admin_headers, db_session: Session
) -> None:
    student = create_student(client, academic_admin_headers)
    endpoint = f"/api/v1/students/{student['id']}/semester-1"

    created = client.put(
        endpoint, headers=academic_admin_headers, json=SEMESTER_PAYLOAD
    )
    updated = client.put(
        endpoint,
        headers=academic_admin_headers,
        json={**SEMESTER_PAYLOAD, "approved_units": 6, "average_grade": 15.0},
    )
    retrieved = client.get(endpoint, headers=academic_admin_headers)

    assert created.status_code == 200
    assert updated.status_code == 200
    assert created.json()["id"] == updated.json()["id"]
    assert retrieved.json()["approved_units"] == 6
    assert db_session.scalar(select(func.count(FirstSemesterRecord.id))) == 1


def test_invalid_semester_numeric_values_are_rejected(
    client: TestClient, academic_admin_headers
) -> None:
    student = create_student(client, academic_admin_headers)

    response = client.put(
        f"/api/v1/students/{student['id']}/semester-1",
        headers=academic_admin_headers,
        json={**SEMESTER_PAYLOAD, "approved_units": -1},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("marital_status_code", 7),
        ("nationality_code", 999),
        ("displaced", 2),
        ("gender_code", -1),
    ],
)
def test_invalid_student_prediction_codes_are_rejected(
    field: str,
    value: int,
    client: TestClient,
    academic_admin_headers,
) -> None:
    response = client.post(
        "/api/v1/students",
        headers=academic_admin_headers,
        json={**STUDENT_PAYLOAD, field: value},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("application_mode_code", 3),
        ("application_order", 10),
        ("course_code", 999),
        ("daytime_evening_attendance", 2),
        ("previous_qualification_code", 999),
        ("mother_occupation_code", 999),
        ("admission_grade", 201),
    ],
)
def test_invalid_admission_prediction_values_are_rejected(
    field: str,
    value: int,
    client: TestClient,
    academic_admin_headers,
) -> None:
    student = create_student(client, academic_admin_headers)
    response = client.put(
        f"/api/v1/students/{student['id']}/admission",
        headers=academic_admin_headers,
        json={**ADMISSION_PAYLOAD, field: value},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_extended_prediction_fields_round_trip_without_becoming_required(
    client: TestClient,
    academic_admin_headers,
) -> None:
    student = create_student(
        client,
        academic_admin_headers,
        marital_status_code=1,
        nationality_code=41,
        gender_code=0,
        age_at_enrollment=19,
    )
    admission = client.put(
        f"/api/v1/students/{student['id']}/admission",
        headers=academic_admin_headers,
        json={
            **ADMISSION_PAYLOAD,
            "application_mode_code": 1,
            "application_order": 0,
            "course_code": 9500,
            "daytime_evening_attendance": 1,
            "unemployment_rate": 10.8,
            "inflation_rate": -0.8,
            "gdp": -3.12,
        },
    )
    semester = client.put(
        f"/api/v1/students/{student['id']}/semester-1",
        headers=academic_admin_headers,
        json={**SEMESTER_PAYLOAD, "without_evaluations": 1},
    )

    assert student["nationality_code"] == 41
    assert admission.status_code == 200
    assert admission.json()["course_code"] == 9500
    assert admission.json()["inflation_rate"] == -0.8
    assert semester.status_code == 200
    assert semester.json()["without_evaluations"] == 1


def test_missing_semester_record_returns_controlled_404(
    client: TestClient, academic_admin_headers
) -> None:
    student = create_student(client, academic_admin_headers)

    response = client.get(
        f"/api/v1/students/{student['id']}/semester-1",
        headers=academic_admin_headers,
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SEMESTER_RECORD_NOT_FOUND"


def test_advisor_can_read_but_not_modify_first_semester(
    client: TestClient, academic_admin_headers, advisor_headers
) -> None:
    student = create_student(client, academic_admin_headers)
    endpoint = f"/api/v1/students/{student['id']}/semester-1"
    client.put(endpoint, headers=academic_admin_headers, json=SEMESTER_PAYLOAD)

    assert client.get(endpoint, headers=advisor_headers).status_code == 200
    assert (
        client.put(endpoint, headers=advisor_headers, json=SEMESTER_PAYLOAD).status_code
        == 403
    )


def test_pagination_metadata_and_page_size(
    client: TestClient, academic_admin_headers
) -> None:
    for index in range(5):
        create_student(
            client,
            academic_admin_headers,
            student_number=f"STU-{index:03d}",
            name=f"Student {index}",
        )

    response = client.get(
        "/api/v1/students?page=2&page_size=2", headers=academic_admin_headers
    )

    assert response.status_code == 200
    assert len(response.json()["items"]) == 2
    assert response.json() | {"items": []} == {
        "items": [],
        "page": 2,
        "page_size": 2,
        "total": 5,
        "total_pages": 3,
    }


@pytest.mark.parametrize(
    ("search", "expected_number"),
    [("ZX-991", "ZX-991"), ("Nadia", "NM-100")],
)
def test_student_number_and_name_search(
    search: str,
    expected_number: str,
    client: TestClient,
    academic_admin_headers,
) -> None:
    create_student(
        client,
        academic_admin_headers,
        student_number="ZX-991",
        name="Omar Idrissi",
    )
    create_student(
        client,
        academic_admin_headers,
        student_number="NM-100",
        name="Nadia Mansouri",
    )

    response = client.get(
        f"/api/v1/students?search={search}", headers=academic_admin_headers
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["student_number"] == expected_number
