"""Mandatory backend gate. Run from backend with a disposable PostgreSQL server."""

import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

URLS = (
    "MODEL_TEST_DATABASE_URL",
    "DUAL_STAGE_TEST_DATABASE_URL",
    "STAGED_IMPORT_TEST_DATABASE_URL",
    "USER_MANAGEMENT_TEST_DATABASE_URL",
    "FRESHNESS_TEST_DATABASE_URL",
    "C1_CASEWORK_TEST_DATABASE_URL",
    "D1_AUDIT_TEST_DATABASE_URL",
)
REQUIRED_MODULES = {
    "tests/ml/test_deployment_postgres.py",
    "tests/ml/test_deployment.py",
    "tests/api/test_outcomes_postgres.py",
    "tests/api/test_staged_imports_postgres.py",
    "tests/api/test_users_postgres.py",
    "tests/api/test_freshness_postgres.py",
    "tests/api/test_casework_integrity_audit_postgres.py",
    "tests/api/test_d1_authorization_postgres.py",
}


def run(*args, env=None):
    subprocess.run([sys.executable, *args], check=True, env=env)


def preflight():
    if platform.python_version() != "3.11.9":
        raise SystemExit("Release requires Python 3.11.9")
    if os.environ.get("RUN_MODEL_INTEGRATION") != "1":
        raise SystemExit("Release requires RUN_MODEL_INTEGRATION=1")
    if (
        os.environ.get("APP_ENV") != "test"
        or os.environ.get("ML_MODEL_REQUIRED", "false").lower() != "false"
    ):
        raise SystemExit(
            "Backend test fixtures require APP_ENV=test and ML_MODEL_REQUIRED=false"
        )
    if os.environ.get("RELEASE_DISPOSABLE_POSTGRES") != "1":
        raise SystemExit("Explicit disposable PostgreSQL acknowledgement required")
    urls = [os.environ.get(name) for name in URLS]
    if not all(urls) or len(set(urls)) != 1:
        raise SystemExit(
            "All seven PostgreSQL URLs must select the same disposable server"
        )
    url = make_url(urls[0])
    if url.drivername != "postgresql+psycopg" or url.database != "release_gate":
        raise SystemExit(
            "Use PostgreSQL psycopg and the disposable release_gate database"
        )
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            assert connection.scalar(
                text(
                    "SELECT rolcreatedb OR rolsuper FROM pg_roles WHERE rolname=current_user"
                )
            ), "Disposable test role requires CREATE DATABASE"
    finally:
        engine.dispose()
    return url


def migrations(url):
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    heads = ScriptDirectory.from_config(Config("alembic.ini")).get_heads()
    if heads != ["20261014_0012"]:
        raise SystemExit("Expected the single reviewed Alembic head 20261014_0012")
    name = "release_migrations_" + uuid4().hex
    engine = create_engine(url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{name}"'))
        target = url.set(database=name)
        env = dict(
            os.environ, DATABASE_URL=target.render_as_string(hide_password=False)
        )
        run("-m", "alembic", "heads", env=env)
        run("-m", "alembic", "upgrade", "head", env=env)
        migrated = create_engine(target)
        try:
            with migrated.connect() as connection:
                assert (
                    connection.scalar(text("SELECT version_num FROM alembic_version"))
                    == heads[0]
                )
        finally:
            migrated.dispose()
        run("-m", "alembic", "current", env=env)
        run("-m", "alembic", "check", env=env)
        run("-m", "alembic", "downgrade", "base", env=env)
        run("-m", "alembic", "upgrade", "head", env=env)
        run("-m", "alembic", "check", env=env)
    finally:
        with engine.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        engine.dispose()


class NoSkips:
    def __init__(self, output):
        self.output = output
        self.collected = 0
        self.passed = 0
        self.skipped = []

    def pytest_collection_finish(self, session):
        self.collected = len(session.items)
        modules = {
            item.nodeid.split("::")[0].replace("\\", "/") for item in session.items
        }
        missing = REQUIRED_MODULES - modules
        if missing:
            raise pytest.UsageError(
                "Mandatory suites absent: " + ", ".join(sorted(missing))
            )

    def pytest_runtest_logreport(self, report):
        if report.skipped:
            self.skipped.append(report.nodeid)
        if report.when == "call" and report.passed:
            self.passed += 1

    def pytest_collectreport(self, report):
        if report.skipped:
            self.skipped.append(report.nodeid)

    @pytest.hookimpl(trylast=True)
    def pytest_sessionfinish(self, session, exitstatus):
        if self.skipped or not self.collected or self.passed != self.collected:
            session.exitstatus = pytest.ExitCode.TESTS_FAILED
        self.output.write_text(
            json.dumps(
                {
                    "python": platform.python_version(),
                    "collected": self.collected,
                    "passed": self.passed,
                    "skipped": self.skipped,
                    "exit_code": int(session.exitstatus),
                },
                indent=2,
            )
            + "\n"
        )


def main():
    output = Path(
        os.environ.get("RELEASE_EVIDENCE_DIR", "../.venv/release-evidence")
    ).resolve()
    output.mkdir(parents=True, exist_ok=True)
    url = preflight()
    run("../scripts/ci/provision_models.py", "--verify-only")
    run("-m", "app.ml.deployment", "verify")
    run("-m", "app.ml.outcomes.deployment", "verify")
    run("-m", "pip", "check")
    migrations(url)
    result = pytest.main(
        [
            "-q",
            "tests",
            "--junitxml=" + str(output / "backend.xml"),
        ],
        plugins=[NoSkips(output / "backend-summary.json")],
    )
    raise SystemExit(result)


if __name__ == "__main__":
    main()
