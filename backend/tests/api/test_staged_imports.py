import csv
import io

import pytest
from app.models import (
    AdmissionRecord,
    FirstSemesterRecord,
    ImportJob,
    StagedImportAction,
    StagedImportBatch,
    Student,
    UserRole,
)
from app.repositories.import_repository import ImportRepository
from app.utils.csv_import import CSV_HEADERS, MAX_DATA_ROWS, MAX_UPLOAD_BYTES
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from tests.api.test_imports import csv_bytes, valid_row

ROOT = "/api/v1/imports/staged"


@pytest.fixture()
def staged_admin(create_user, auth_headers):
    create_user(username="staged_admin", role=UserRole.ACADEMIC_ADMIN)
    return auth_headers("staged_admin")


def stage(client, headers, rows):
    response = client.post(
        ROOT + "/csv",
        headers=headers,
        files={"file": ("students.csv", csv_bytes(rows), "text/csv")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def rows_for(client, headers, batch, query=""):
    response = client.get(f"{ROOT}/{batch['id']}/rows{query}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def patch(client, headers, batch, row, **changes):
    return client.patch(
        f"{ROOT}/{batch['id']}/rows/{row['id']}",
        headers=headers,
        json={
            "expected_batch_version": batch["version"],
            "expected_row_version": row["version"],
            **changes,
        },
    )


def commit(client, headers, batch):
    return client.post(
        f"{ROOT}/{batch['id']}/commit",
        headers=headers,
        json={"expected_batch_version": batch["version"]},
    )


def test_stage_no_domain_persistence_and_issue_counts(client, staged_admin, db_session):
    invalid = valid_row("BAD")
    invalid.update(name="", gdp="")
    batch = stage(client, staged_admin, [valid_row(), invalid])
    assert batch["status"] == "REVIEW_REQUIRED"
    assert (
        batch["total_rows"],
        batch["valid_rows"],
        batch["invalid_rows"],
        batch["validation_issue_count"],
    ) == (2, 1, 1, 2)
    for model in (Student, AdmissionRecord, FirstSemesterRecord, ImportJob):
        assert db_session.scalar(select(func.count(model.id))) == 0
    assert (
        rows_for(client, staged_admin, batch)["items"][1]["original_values"] == invalid
    )
    assert (
        client.get("/api/v1/dashboard/overview", headers=staged_admin).json()[
            "data_freshness"
        ]["last_import_at"]
        is None
    )


def test_correction_revalidates_entire_batch_and_preserves_original(
    client, staged_admin
):
    batch = stage(client, staged_admin, [valid_row("DUP"), valid_row("DUP")])
    rows = rows_for(client, staged_admin, batch)["items"]
    assert batch["invalid_included_rows"] == 2
    result = patch(
        client, staged_admin, batch, rows[1], values={"student_number": "UNIQUE"}
    )
    assert result.status_code == 200
    batch = result.json()["batch"]
    assert batch["status"] == "READY_TO_COMMIT" and batch["version"] == 2
    changed = rows_for(client, staged_admin, batch)["items"]
    assert all(not row["issues"] and row["version"] == 2 for row in changed)
    assert changed[1]["original_values"]["student_number"] == "DUP"
    result = patch(
        client,
        staged_admin,
        batch,
        changed[1],
        values={"student_number": "DUP", "gdp": "nan"},
    ).json()
    assert result["batch"]["invalid_included_rows"] == 2
    assert result["batch"]["validation_issue_count"] == 3
    actions = client.get(f"{ROOT}/{batch['id']}/actions", headers=staged_admin).json()
    assert actions["total"] == 3
    assert actions["items"][1]["changes"]["values"]["student_number"] == {
        "before": "DUP",
        "after": "UNIQUE",
    }
    assert len(actions["items"][1]["changes"]["validation_changes"]) == 2
    assert all(
        action["actor_id"] and action["created_at"] for action in actions["items"]
    )


def test_exclusion_restoration_and_no_included_rows(client, staged_admin):
    batch = stage(client, staged_admin, [valid_row("DUP"), valid_row("DUP")])
    row = rows_for(client, staged_admin, batch)["items"][1]
    batch = patch(client, staged_admin, batch, row, included=False).json()["batch"]
    assert batch["status"] == "READY_TO_COMMIT"
    assert (batch["included_rows"], batch["excluded_rows"], batch["invalid_rows"]) == (
        1,
        1,
        0,
    )
    row = rows_for(client, staged_admin, batch)["items"][1]
    batch = patch(client, staged_admin, batch, row, included=True).json()["batch"]
    assert batch["invalid_included_rows"] == 2 and batch["status"] == "REVIEW_REQUIRED"
    for row in rows_for(client, staged_admin, batch)["items"]:
        # Reload because duplicate revalidation may have changed a sibling's version.
        row = next(
            item
            for item in rows_for(client, staged_admin, batch)["items"]
            if item["id"] == row["id"]
        )
        batch = patch(client, staged_admin, batch, row, included=False).json()["batch"]
    assert batch["included_rows"] == 0 and batch["status"] == "REVIEW_REQUIRED"
    assert (
        commit(client, staged_admin, batch).json()["error"]["code"]
        == "STAGED_IMPORT_NOT_READY"
    )


def test_excluded_invalid_issues_do_not_block_readiness(client, staged_admin):
    invalid = valid_row("BAD")
    invalid["name"] = ""
    batch = stage(client, staged_admin, [valid_row("GOOD"), invalid])
    row = rows_for(client, staged_admin, batch)["items"][1]
    batch = patch(client, staged_admin, batch, row, included=False).json()["batch"]
    assert batch["invalid_rows"] == 1 and batch["invalid_included_rows"] == 0
    assert batch["validation_issue_count"] == 1 and batch["included_issue_count"] == 0
    assert batch["status"] == "READY_TO_COMMIT"


def test_stale_edits_and_commits_never_persist(client, staged_admin, db_session):
    old = stage(client, staged_admin, [valid_row()])
    row = rows_for(client, staged_admin, old)["items"][0]
    new = patch(client, staged_admin, old, row, values={"name": "Corrected"}).json()[
        "batch"
    ]
    assert (
        patch(client, staged_admin, old, row, values={"name": "Stale"}).json()["error"][
            "code"
        ]
        == "STAGED_IMPORT_STALE"
    )
    assert (
        patch(client, staged_admin, new, row, included=False).json()["error"]["code"]
        == "STAGED_ROW_STALE"
    )
    assert (
        commit(client, staged_admin, old).json()["error"]["code"]
        == "STAGED_IMPORT_STALE"
    )
    current = client.get(f"{ROOT}/{old['id']}", headers=staged_admin).json()
    assert current["version"] == new["version"]
    assert db_session.scalar(select(func.count(Student.id))) == 0


def test_commit_graphs_retry_terminal_history_and_freshness(
    client, staged_admin, db_session
):
    source = valid_row("ROUNDTRIP")
    batch = stage(client, staged_admin, [source, valid_row("EXCLUDED")])
    row = rows_for(client, staged_admin, batch)["items"][1]
    batch = patch(client, staged_admin, batch, row, included=False).json()["batch"]
    response = commit(client, staged_admin, batch)
    assert response.status_code == 200, response.text
    committed = response.json()
    assert committed["status"] == "COMMITTED"
    assert (
        committed["import_job"]["total_rows"]
        == committed["import_job"]["valid_rows"]
        == 1
    )
    assert committed["import_job"]["invalid_rows"] == 0
    assert commit(client, staged_admin, batch).json() == committed
    for model in (Student, AdmissionRecord, FirstSemesterRecord, ImportJob):
        assert db_session.scalar(select(func.count(model.id))) == 1
    job = client.get(
        f"/api/v1/imports/{committed['import_job_id']}", headers=staged_admin
    )
    assert job.status_code == 200 and job.json() == committed["import_job"]
    assert client.get("/api/v1/imports", headers=staged_admin).json()["total"] == 1
    assert (
        client.get(
            f"/api/v1/imports/{committed['import_job_id']}/errors", headers=staged_admin
        ).json()["total"]
        == 0
    )
    assert (
        client.get("/api/v1/dashboard/overview", headers=staged_admin).json()[
            "data_freshness"
        ]["last_import_at"]
        is not None
    )
    current_row = rows_for(client, staged_admin, committed)["items"][0]
    assert (
        patch(
            client, staged_admin, committed, current_row, values={"name": "Overwrite"}
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"{ROOT}/{batch['id']}/cancel",
            headers=staged_admin,
            json={"expected_batch_version": committed["version"]},
        ).status_code
        == 409
    )
    actions = client.get(f"{ROOT}/{batch['id']}/actions", headers=staged_admin).json()[
        "items"
    ]
    assert sum(action["action"] == "COMMITTED" for action in actions) == 1


def test_new_database_conflict_after_upload_is_persisted_and_correctable(
    client, staged_admin, db_session
):
    batch = stage(client, staged_admin, [valid_row("RACE"), valid_row("SAFE")])
    db_session.add(Student(student_number="RACE", name="Existing student"))
    db_session.commit()
    response = commit(client, staged_admin, batch)
    assert response.status_code == 409
    current = response.json()["error"]["details"]
    assert (
        current["status"] == "REVIEW_REQUIRED" and current["invalid_included_rows"] == 1
    )
    assert current["version"] == batch["version"] + 1
    assert db_session.scalar(select(func.count(Student.id))) == 1
    assert db_session.scalar(select(func.count(AdmissionRecord.id))) == 0
    row = rows_for(client, staged_admin, current)["items"][0]
    assert row["issues"][0]["error_code"] == "STUDENT_NUMBER_ALREADY_EXISTS"
    corrected = patch(
        client, staged_admin, current, row, values={"student_number": "CORRECTED"}
    ).json()["batch"]
    assert commit(client, staged_admin, corrected).status_code == 200


def test_integrity_failure_rolls_back_all_graphs_and_history(
    client, staged_admin, db_session, monkeypatch
):
    batch = stage(client, staged_admin, [valid_row("FIRST"), valid_row("SECOND")])
    original = ImportRepository.add_student_graph
    calls = 0

    def failing(self, row):
        nonlocal calls
        calls += 1
        original(self, row)
        if calls == 2:
            raise IntegrityError("injected constraint race", {}, Exception("conflict"))

    monkeypatch.setattr(ImportRepository, "add_student_graph", failing)
    response = commit(client, staged_admin, batch)
    assert response.status_code == 409
    current = response.json()["error"]["details"]
    assert current["import_job_id"] is None and current["last_commit_error"]
    for model in (Student, AdmissionRecord, FirstSemesterRecord, ImportJob):
        assert db_session.scalar(select(func.count(model.id))) == 0
    monkeypatch.setattr(ImportRepository, "add_student_graph", original)
    assert commit(client, staged_admin, current).status_code == 200


def test_cancellation_is_immutable_and_preserves_source_audit(
    client, staged_admin, db_session
):
    batch = stage(client, staged_admin, [valid_row()])
    response = client.post(
        f"{ROOT}/{batch['id']}/cancel",
        headers=staged_admin,
        json={"expected_batch_version": batch["version"]},
    )
    cancelled = response.json()
    assert cancelled["status"] == "CANCELLED" and cancelled["cancelled_at"]
    row = rows_for(client, staged_admin, cancelled)["items"][0]
    assert (
        patch(client, staged_admin, cancelled, row, included=False).status_code == 409
    )
    assert commit(client, staged_admin, cancelled).status_code == 409
    assert db_session.scalar(select(func.count(Student.id))) == 0
    assert db_session.scalar(select(func.count(StagedImportAction.id))) == 2
    assert (
        client.get(f"{ROOT}/{batch['id']}/export", headers=staged_admin).status_code
        == 200
    )


@pytest.mark.parametrize("role", [UserRole.SYSTEM_ADMIN, UserRole.ACADEMIC_ADVISOR])
def test_staged_rbac_every_endpoint(
    role, client, staged_admin, create_user, auth_headers
):
    batch = stage(client, staged_admin, [valid_row()])
    row = rows_for(client, staged_admin, batch)["items"][0]
    create_user(username="staged_reader", role=role)
    headers = auth_headers("staged_reader")
    for suffix in (
        "",
        f"/{batch['id']}",
        f"/{batch['id']}/rows",
        f"/{batch['id']}/actions",
        f"/{batch['id']}/export",
    ):
        assert client.get(ROOT + suffix, headers=headers).status_code == (
            200 if role == UserRole.SYSTEM_ADMIN else 403
        )
        assert client.get(ROOT + suffix).status_code == 401
    assert client.get("/api/v1/imports/template", headers=headers).status_code == (
        200 if role == UserRole.SYSTEM_ADMIN else 403
    )
    assert (
        client.post(
            ROOT + "/csv",
            headers=headers,
            files={"file": ("students.csv", csv_bytes([valid_row()]))},
        ).status_code
        == 403
    )
    assert patch(client, headers, batch, row, included=False).status_code == 403
    for action in ("commit", "cancel"):
        assert (
            client.post(
                f"{ROOT}/{batch['id']}/{action}",
                headers=headers,
                json={"expected_batch_version": 1},
            ).status_code
            == 403
        )


def test_pagination_filters_and_exact_canonical_export(client, staged_admin):
    batch = stage(
        client, staged_admin, [valid_row("S-1"), valid_row("S-2"), valid_row("S-3")]
    )
    rows = rows_for(client, staged_admin, batch)["items"]
    result = patch(
        client,
        staged_admin,
        batch,
        rows[0],
        values={"name": "=Source formula text", "gdp": "-0.5"},
    ).json()
    batch = result["batch"]
    row = rows_for(client, staged_admin, batch)["items"][1]
    batch = patch(client, staged_admin, batch, row, included=False).json()["batch"]
    page = rows_for(client, staged_admin, batch, "?page=2&page_size=1&included=true")
    assert (
        page["page"],
        page["total"],
        page["total_pages"],
        page["batch_version"],
    ) == (2, 2, 2, batch["version"])
    assert page["items"][0]["edited_values"]["student_number"] == "S-3"
    assert rows_for(client, staged_admin, batch, "?search=s-1&valid=true")["total"] == 1
    assert rows_for(client, staged_admin, batch, "?search=%")["total"] == 0
    exported = client.get(f"{ROOT}/{batch['id']}/export", headers=staged_admin)
    parsed = list(csv.DictReader(io.StringIO(exported.text)))
    assert tuple(parsed[0]) == CSV_HEADERS
    assert [row["student_number"] for row in parsed] == ["S-1", "S-3"]
    assert parsed[0]["name"] == "=Source formula text" and parsed[0]["gdp"] == "-0.5"
    assert (
        client.get(
            ROOT + "?page_size=1&status=READY_TO_COMMIT", headers=staged_admin
        ).json()["total"]
        == 1
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"values": {"email": "fake"}},
        {"values": {"gdp": 2}},
        {"values": {}},
        {"values": {"name": "x"}, "extra": True},
    ],
)
def test_reject_noncanonical_or_malformed_corrections(payload, client, staged_admin):
    batch = stage(client, staged_admin, [valid_row()])
    row = rows_for(client, staged_admin, batch)["items"][0]
    assert patch(client, staged_admin, batch, row, **payload).status_code == 422


@pytest.mark.parametrize(
    "content,code,status",
    [
        (b"", "CSV_EMPTY", 400),
        (b"\xff", "CSV_INVALID_ENCODING", 400),
        (b"unknown\r\nvalue", "CSV_MISSING_COLUMNS", 400),
        (b"x" * (MAX_UPLOAD_BYTES + 1), "CSV_FILE_TOO_LARGE", 413),
    ],
    ids=["empty", "encoding", "columns", "oversize"],
)
def test_staged_upload_preserves_structure_and_size_limits(
    content, code, status, client, staged_admin, db_session
):
    response = client.post(
        ROOT + "/csv", headers=staged_admin, files={"file": ("students.csv", content)}
    )
    assert response.status_code == status and response.json()["error"]["code"] == code
    assert db_session.scalar(select(func.count(StagedImportBatch.id))) == 0


def test_staged_row_limit_and_header_only_batch(client, staged_admin):
    response = client.post(
        ROOT + "/csv",
        headers=staged_admin,
        files={
            "file": (
                "students.csv",
                csv_bytes([valid_row(str(i)) for i in range(MAX_DATA_ROWS + 1)]),
            )
        },
    )
    assert (
        response.status_code == 400
        and response.json()["error"]["code"] == "CSV_TOO_MANY_ROWS"
    )
    batch = stage(client, staged_admin, [])
    assert batch["status"] == "REVIEW_REQUIRED" and batch["total_rows"] == 0
    assert commit(client, staged_admin, batch).status_code == 409


def test_existing_db_duplicate_cannot_overwrite(client, staged_admin, db_session):
    db_session.add(Student(student_number="EXISTS", name="Keep original"))
    db_session.commit()
    batch = stage(client, staged_admin, [valid_row("EXISTS")])
    assert batch["invalid_included_rows"] == 1
    assert commit(client, staged_admin, batch).status_code == 409
    assert db_session.scalar(select(Student.name)) == "Keep original"
