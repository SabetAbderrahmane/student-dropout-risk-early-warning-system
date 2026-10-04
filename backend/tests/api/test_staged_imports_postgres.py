"""Real PostgreSQL locking/race checks. Set STAGED_IMPORT_TEST_DATABASE_URL.

Every test creates and removes only its own randomly named test schema.
"""

import asyncio
import io
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from app.core.exceptions import ApplicationError
from app.db.base import Base
from app.models import (
    AdmissionRecord,
    FirstSemesterRecord,
    ImportJob,
    StagedImportAction,
    StagedImportBatch,
    Student,
    User,
    UserRole,
)
from app.repositories.import_repository import ImportRepository
from app.services.staged_import_service import StagedImportService
from fastapi import UploadFile
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema
from tests.api.test_imports import csv_bytes, valid_row


@pytest.fixture()
def pg_engine():
    url = os.environ.get("STAGED_IMPORT_TEST_DATABASE_URL")
    if not url:
        pytest.skip(
            "Set STAGED_IMPORT_TEST_DATABASE_URL for PostgreSQL concurrency tests."
        )
    root_engine = create_engine(url)
    if root_engine.dialect.name != "postgresql":
        pytest.fail("STAGED_IMPORT_TEST_DATABASE_URL must be PostgreSQL.")
    schema = "staged_test_" + uuid4().hex
    with root_engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    engine = create_engine(
        url,
        connect_args={
            "options": f"-csearch_path={schema} -clock_timeout=10000 -cstatement_timeout=20000"
        },
    )
    try:
        Base.metadata.create_all(engine)
        yield engine
    finally:
        engine.dispose()
        with root_engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        root_engine.dispose()


def setup_batch(engine, numbers):
    with Session(engine, expire_on_commit=False) as db:
        actor = User(
            username="pg_" + uuid4().hex,
            email=uuid4().hex + "@example.test",
            full_name="Test Admin",
            password_hash="not-used",
            role=UserRole.ACADEMIC_ADMIN,
            is_active=True,
        )
        db.add(actor)
        db.commit()
        batch = asyncio.run(
            StagedImportService(db).stage(
                UploadFile(
                    filename="postgres.csv",
                    file=io.BytesIO(
                        csv_bytes([valid_row(number) for number in numbers])
                    ),
                ),
                actor,
            )
        )
        return batch.id, batch.version, actor.id


def run_commit(engine, batch_id, version, actor_id, barrier=None):
    with Session(engine, expire_on_commit=False) as db:
        actor = db.get(User, actor_id)
        if barrier:
            barrier.wait(timeout=10)
        try:
            batch = StagedImportService(db).commit(batch_id, version, actor)
            return {"status": batch.status.value, "job": str(batch.import_job_id)}
        except ApplicationError as error:
            return {"error": error.code, "details": error.details}


def test_same_batch_concurrent_commits_return_one_result(pg_engine):
    batch_id, version, actor_id = setup_batch(
        pg_engine, ["CONCURRENT-1", "CONCURRENT-2"]
    )
    barrier = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [
            workers.submit(run_commit, pg_engine, batch_id, version, actor_id, barrier)
            for _ in range(2)
        ]
        results = [future.result(timeout=30) for future in futures]
    assert results[0] == results[1] and results[0]["status"] == "COMMITTED"
    with Session(pg_engine) as db:
        for model, count in (
            (Student, 2),
            (AdmissionRecord, 2),
            (FirstSemesterRecord, 2),
            (ImportJob, 1),
        ):
            assert db.scalar(select(func.count(model.id))) == count
        assert (
            db.scalar(
                select(func.count(StagedImportAction.id)).where(
                    StagedImportAction.action == "COMMITTED"
                )
            )
            == 1
        )


def test_different_batches_unique_race_rolls_back_loser(pg_engine, monkeypatch):
    first = setup_batch(pg_engine, ["FIRST-ONLY", "SHARED"])
    second = setup_batch(pg_engine, ["SECOND-ONLY", "SHARED"])
    barrier = Barrier(2)
    original = ImportRepository.existing_student_numbers

    def synchronize_validation(self, numbers):
        existing = original(self, numbers)
        if not existing:
            barrier.wait(timeout=10)
        return existing

    monkeypatch.setattr(
        ImportRepository, "existing_student_numbers", synchronize_validation
    )
    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [
            workers.submit(run_commit, pg_engine, *params) for params in (first, second)
        ]
        results = [future.result(timeout=30) for future in futures]
    assert sum(result.get("status") == "COMMITTED" for result in results) == 1
    loser = next(result for result in results if "error" in result)
    assert loser["error"] == "STAGED_IMPORT_COMMIT_CONFLICT"
    assert loser["details"]["status"] == "REVIEW_REQUIRED"
    assert loser["details"]["invalid_included_rows"] == 1
    with Session(pg_engine) as db:
        for model, count in (
            (Student, 2),
            (AdmissionRecord, 2),
            (FirstSemesterRecord, 2),
            (ImportJob, 1),
        ):
            assert db.scalar(select(func.count(model.id))) == count
        assert (
            db.scalar(
                select(func.count(StagedImportBatch.id)).where(
                    StagedImportBatch.import_job_id.is_not(None)
                )
            )
            == 1
        )


def test_competing_stale_corrections_only_one_wins(pg_engine):
    from app.models import StagedImportRow
    from app.schemas.staged_import import RowCorrection

    batch_id, version, actor_id = setup_batch(pg_engine, ["EDIT"])
    with Session(pg_engine) as db:
        row = db.scalar(
            select(StagedImportRow).where(StagedImportRow.batch_id == batch_id)
        )
        row_id, row_version = row.id, row.version
    barrier = Barrier(2)

    def edit(name):
        with Session(pg_engine) as db:
            actor = db.get(User, actor_id)
            barrier.wait(timeout=10)
            try:
                StagedImportService(db).correct(
                    batch_id,
                    row_id,
                    RowCorrection(
                        expected_batch_version=version,
                        expected_row_version=row_version,
                        values={"name": name},
                    ),
                    actor,
                )
                return "corrected"
            except ApplicationError as error:
                return error.code

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(edit, ["Editor A", "Editor B"]))
    assert sorted(results) == ["STAGED_IMPORT_STALE", "corrected"]
    with Session(pg_engine) as db:
        assert db.get(StagedImportBatch, batch_id).version == version + 1
        assert db.scalar(select(func.count(StagedImportAction.id))) == 2


def test_migration_upgrade_downgrade_preserves_historical_import(monkeypatch):
    from pathlib import Path

    from alembic import command
    from alembic.autogenerate import compare_metadata
    from alembic.config import Config
    from alembic.migration import MigrationContext
    from app.core.config import get_settings
    from app.models import ImportStatus
    from sqlalchemy.engine import make_url

    url = os.environ.get("STAGED_IMPORT_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set STAGED_IMPORT_TEST_DATABASE_URL for migration roundtrip.")
    schema = "staged_test_" + uuid4().hex
    root_engine = create_engine(url)
    with root_engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    isolated_url = make_url(url).update_query_dict(
        {"options": f"-csearch_path={schema}"}
    )
    engine = create_engine(isolated_url)
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.set_main_option(
        "script_location", str(Path(__file__).resolve().parents[2] / "alembic")
    )
    monkeypatch.setattr(
        get_settings(),
        "database_url",
        isolated_url.render_as_string(hide_password=False),
    )
    try:
        command.upgrade(config, "20260930_0007")
        with Session(engine) as db:
            actor = User(
                username="historical",
                email="historical@example.test",
                full_name="Historical",
                password_hash="not-used",
                role=UserRole.ACADEMIC_ADMIN,
                is_active=True,
            )
            db.add(actor)
            db.flush()
            job = ImportJob(
                uploaded_by=actor.id,
                filename="historical.csv",
                total_rows=3,
                valid_rows=2,
                invalid_rows=1,
                status=ImportStatus.IMPORTED,
            )
            db.add(job)
            db.commit()
            job_id = job.id
        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert (
                compare_metadata(
                    MigrationContext.configure(connection, opts={"compare_type": True}),
                    Base.metadata,
                )
                == []
            )
        command.downgrade(config, "20260930_0007")
        with Session(engine) as db:
            job = db.get(ImportJob, job_id)
            assert (job.total_rows, job.valid_rows, job.invalid_rows) == (3, 2, 1)
        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert (
                compare_metadata(
                    MigrationContext.configure(connection, opts={"compare_type": True}),
                    Base.metadata,
                )
                == []
            )
    finally:
        engine.dispose()
        with root_engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        root_engine.dispose()
