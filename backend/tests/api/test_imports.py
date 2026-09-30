import csv
import io
from decimal import Decimal

import pytest
from app.ml.feature_schema import (
    EXCLUDED_SECOND_SEMESTER_OFFICIAL_NAMES,
    PREDICTION_FEATURES,
    FeatureDataType,
)
from app.models import (
    AdmissionRecord,
    FirstSemesterRecord,
    ImportJob,
    ImportValidationError,
    Student,
    UserRole,
)
from app.utils.csv_import import CSV_HEADERS, MAX_DATA_ROWS, MAX_UPLOAD_BYTES
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def valid_row(student_number: str = "CSV-001") -> dict[str, str]:
    row = {
        "student_number": student_number,
        "name": "CSV Student",
        "admission_method": "General admission",
        "previous_qualification": "Secondary education",
    }
    for feature in PREDICTION_FEATURES:
        if feature.allowed_values:
            value: int | float = min(feature.allowed_values)
        elif feature.minimum is not None:
            value = feature.minimum
        elif feature.data_type is FeatureDataType.INTEGER:
            value = 1
        else:
            value = -0.5
        row[feature.name] = str(value)
    return row


def csv_bytes(rows: list[dict[str, str]], headers=CSV_HEADERS) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=headers, lineterminator="\r\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return stream.getvalue().encode("utf-8")


def upload(
    client: TestClient,
    headers: dict[str, str],
    content: bytes,
    filename: str = "students.csv",
):
    return client.post(
        "/api/v1/imports/csv",
        headers=headers,
        files={"file": (filename, content, "text/csv")},
    )


@pytest.fixture()
def academic_admin_headers(client: TestClient, create_user, auth_headers):
    create_user(username="import_admin", role=UserRole.ACADEMIC_ADMIN)
    return auth_headers("import_admin")


@pytest.fixture()
def system_admin_headers(client: TestClient, create_user, auth_headers):
    create_user(username="import_system", role=UserRole.SYSTEM_ADMIN)
    return auth_headers("import_system")


@pytest.fixture()
def advisor_headers(client: TestClient, create_user, auth_headers):
    create_user(username="import_advisor", role=UserRole.ACADEMIC_ADVISOR)
    return auth_headers("import_advisor")


def test_template_has_exact_deterministic_contract(
    client: TestClient, academic_admin_headers
) -> None:
    first = client.get("/api/v1/imports/template", headers=academic_admin_headers)
    second = client.get("/api/v1/imports/template", headers=academic_admin_headers)
    parsed = next(csv.reader(io.StringIO(first.text)))

    assert first.status_code == 200
    assert first.content == second.content
    assert tuple(parsed) == CSV_HEADERS
    assert len(parsed) == 34
    assert parsed[:4] == [
        "student_number",
        "name",
        "admission_method",
        "previous_qualification",
    ]
    assert parsed[4:] == [feature.name for feature in PREDICTION_FEATURES]
    assert len(parsed[4:]) == len(set(parsed[4:])) == 30
    assert "Target" not in parsed and "target" not in parsed
    assert all("2nd" not in header for header in parsed)
    assert set(EXCLUDED_SECOND_SEMESTER_OFFICIAL_NAMES).isdisjoint(parsed)


def test_template_and_import_authorization(
    client: TestClient,
    academic_admin_headers,
    system_admin_headers,
    advisor_headers,
) -> None:
    assert client.get("/api/v1/imports/template").status_code == 401
    assert (
        client.get("/api/v1/imports/template", headers=system_admin_headers).status_code
        == 200
    )
    assert (
        client.get("/api/v1/imports/template", headers=advisor_headers).status_code
        == 403
    )
    assert (
        upload(client, academic_admin_headers, csv_bytes([valid_row()])).status_code
        == 200
    )
    assert (
        upload(
            client, system_admin_headers, csv_bytes([valid_row("SYS-1")])
        ).status_code
        == 403
    )
    assert (
        upload(client, advisor_headers, csv_bytes([valid_row("ADV-1")])).status_code
        == 403
    )
    assert (
        client.get("/api/v1/imports", headers=system_admin_headers).status_code == 200
    )
    assert client.get("/api/v1/imports", headers=advisor_headers).status_code == 403


@pytest.mark.parametrize(
    ("content", "expected_code"),
    [
        (b"", "CSV_EMPTY"),
        (b"\xff\xfe", "CSV_INVALID_ENCODING"),
        (b'"unclosed', "CSV_PARSE_ERROR"),
    ],
)
def test_invalid_file_structure_imports_nothing(
    content: bytes,
    expected_code: str,
    client: TestClient,
    academic_admin_headers,
    db_session: Session,
) -> None:
    response = upload(client, academic_admin_headers, content)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == expected_code
    assert db_session.scalar(select(func.count(Student.id))) == 0
    assert db_session.scalar(select(func.count(ImportJob.id))) == 0


@pytest.mark.parametrize(
    ("headers", "expected_code"),
    [
        (CSV_HEADERS[:-1], "CSV_MISSING_COLUMNS"),
        (CSV_HEADERS + ("mystery",), "CSV_UNKNOWN_COLUMNS"),
        (CSV_HEADERS + (CSV_HEADERS[-1],), "CSV_DUPLICATE_HEADER"),
    ],
)
def test_invalid_header_contract_imports_nothing(
    headers,
    expected_code: str,
    client: TestClient,
    academic_admin_headers,
    db_session: Session,
) -> None:
    stream = io.StringIO(newline="")
    csv.writer(stream).writerow(headers)
    response = upload(client, academic_admin_headers, stream.getvalue().encode())

    assert response.status_code == 400
    assert response.json()["error"]["code"] == expected_code
    assert db_session.scalar(select(func.count(Student.id))) == 0


def test_column_order_may_differ_and_utf8_bom_is_accepted(
    client: TestClient, academic_admin_headers
) -> None:
    reversed_headers = tuple(reversed(CSV_HEADERS))
    content = b"\xef\xbb\xbf" + csv_bytes([valid_row()], reversed_headers)

    response = upload(client, academic_admin_headers, content)

    assert response.status_code == 200
    assert response.json()["valid_rows"] == 1


def test_more_than_5000_rows_is_rejected_before_persistence(
    client: TestClient, academic_admin_headers, db_session: Session
) -> None:
    rows = [valid_row(f"LIMIT-{index}") for index in range(MAX_DATA_ROWS + 1)]

    response = upload(client, academic_admin_headers, csv_bytes(rows))

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "CSV_TOO_MANY_ROWS"
    assert db_session.scalar(select(func.count(Student.id))) == 0
    assert db_session.scalar(select(func.count(ImportJob.id))) == 0


def test_non_csv_extension_is_rejected(
    client: TestClient, academic_admin_headers
) -> None:
    response = upload(
        client,
        academic_admin_headers,
        csv_bytes([valid_row()]),
        filename="students.txt",
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "CSV_INVALID_FILE_TYPE"


def test_file_size_limit_is_enforced(
    client: TestClient, academic_admin_headers, db_session: Session
) -> None:
    response = upload(client, academic_admin_headers, b"x" * (MAX_UPLOAD_BYTES + 1))

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "CSV_FILE_TOO_LARGE"
    assert db_session.scalar(select(func.count(ImportJob.id))) == 0


@pytest.mark.parametrize(
    ("field_name", "invalid_value", "expected_code"),
    [
        ("name", "", "REQUIRED_VALUE_MISSING"),
        ("age_at_enrollment", "1.5", "INVALID_INTEGER"),
        ("admission_grade", "not-a-number", "INVALID_NUMBER"),
        ("marital_status_code", "999", "INVALID_FEATURE_VALUE"),
        ("displaced", "2", "INVALID_FEATURE_VALUE"),
        ("application_order", "10", "INVALID_FEATURE_VALUE"),
    ],
)
def test_row_validation_codes_are_persisted(
    field_name: str,
    invalid_value: str,
    expected_code: str,
    client: TestClient,
    academic_admin_headers,
) -> None:
    row = valid_row()
    row[field_name] = invalid_value

    imported = upload(client, academic_admin_headers, csv_bytes([row]))
    body = imported.json()
    errors = client.get(
        f"/api/v1/imports/{body['id']}/errors", headers=academic_admin_headers
    ).json()

    assert imported.status_code == 200
    assert body["valid_rows"] == 0 and body["invalid_rows"] == 1
    assert errors["total"] >= 1
    assert any(
        error["field_name"] == field_name and error["error_code"] == expected_code
        for error in errors["items"]
    )


def test_duplicate_student_number_in_file_marks_both_rows_invalid(
    client: TestClient, academic_admin_headers
) -> None:
    response = upload(
        client,
        academic_admin_headers,
        csv_bytes([valid_row("DUP-1"), valid_row("DUP-1")]),
    )
    body = response.json()
    errors = client.get(
        f"/api/v1/imports/{body['id']}/errors?page_size=100",
        headers=academic_admin_headers,
    ).json()

    assert body["total_rows"] == 2
    assert body["valid_rows"] == 0
    assert body["invalid_rows"] == 2
    assert {error["row_number"] for error in errors["items"]} == {2, 3}
    assert {error["error_code"] for error in errors["items"]} == {
        "DUPLICATE_STUDENT_NUMBER_IN_FILE"
    }


def test_existing_student_is_create_only_row_error(
    client: TestClient,
    academic_admin_headers,
    db_session: Session,
) -> None:
    existing = Student(student_number="EXISTS-1", name="Original")
    db_session.add(existing)
    db_session.commit()

    response = upload(
        client, academic_admin_headers, csv_bytes([valid_row("EXISTS-1")])
    )
    body = response.json()
    errors = client.get(
        f"/api/v1/imports/{body['id']}/errors", headers=academic_admin_headers
    ).json()

    assert body["valid_rows"] == 0 and body["invalid_rows"] == 1
    assert errors["items"][0]["error_code"] == "STUDENT_NUMBER_ALREADY_EXISTS"
    assert db_session.scalar(select(func.count(Student.id))) == 1
    assert (
        db_session.scalar(
            select(Student.name).where(Student.student_number == "EXISTS-1")
        )
        == "Original"
    )


def test_partial_import_persists_errors_and_keeps_valid_row(
    client: TestClient,
    academic_admin_headers,
    db_session: Session,
) -> None:
    invalid = valid_row("PARTIAL-BAD")
    invalid["course_code"] = "999"

    response = upload(
        client,
        academic_admin_headers,
        csv_bytes([valid_row("PARTIAL-GOOD"), invalid]),
    )
    body = response.json()

    assert body["status"] == "IMPORTED"
    assert body["total_rows"] == 2
    assert body["valid_rows"] == 1
    assert body["invalid_rows"] == 1
    assert db_session.scalar(select(func.count(Student.id))) == 1
    assert db_session.scalar(select(func.count(AdmissionRecord.id))) == 1
    assert db_session.scalar(select(func.count(FirstSemesterRecord.id))) == 1
    error = db_session.scalar(select(ImportValidationError))
    assert error is not None
    assert error.row_number == 3
    assert error.field_name == "course_code"
    assert error.error_code == "INVALID_FEATURE_VALUE"


def test_all_valid_rows_and_all_30_features_round_trip(
    client: TestClient,
    academic_admin_headers,
    db_session: Session,
) -> None:
    row = valid_row("ROUNDTRIP-1")
    response = upload(client, academic_admin_headers, csv_bytes([row]))

    assert response.status_code == 200
    assert response.json()["valid_rows"] == 1
    student = db_session.scalar(
        select(Student).where(Student.student_number == "ROUNDTRIP-1")
    )
    assert student is not None
    admission = db_session.scalar(
        select(AdmissionRecord).where(AdmissionRecord.student_id == student.id)
    )
    semester = db_session.scalar(
        select(FirstSemesterRecord).where(FirstSemesterRecord.student_id == student.id)
    )
    records = {
        "students": student,
        "admission_records": admission,
        "first_semester_records": semester,
    }
    for feature in PREDICTION_FEATURES:
        stored = getattr(records[feature.storage_table], feature.storage_column)
        expected = row[feature.name]
        if feature.data_type is FeatureDataType.INTEGER:
            assert stored == int(expected)
        else:
            assert Decimal(str(stored)) == Decimal(expected)


def test_import_history_detail_and_error_pagination(
    client: TestClient, academic_admin_headers
) -> None:
    invalid = valid_row("PAGE-BAD")
    invalid["name"] = ""
    invalid["gdp"] = ""
    created = upload(client, academic_admin_headers, csv_bytes([invalid])).json()

    history = client.get(
        "/api/v1/imports?page=1&page_size=1", headers=academic_admin_headers
    ).json()
    detail = client.get(
        f"/api/v1/imports/{created['id']}", headers=academic_admin_headers
    ).json()
    errors = client.get(
        f"/api/v1/imports/{created['id']}/errors?page=1&page_size=1",
        headers=academic_admin_headers,
    ).json()

    assert history["total"] == 1 and len(history["items"]) == 1
    assert detail["id"] == created["id"]
    assert errors["total"] == 2 and len(errors["items"]) == 1
