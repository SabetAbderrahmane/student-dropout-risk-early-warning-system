"""Negative controls for the release gate itself, outside application behavior."""

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from docker_smoke import require_ownership
from provision_models import CHECKSUMS, main as provision, verify_bytes
from release_backend import URLS, NoSkips, preflight


def valid_environment(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("ML_MODEL_REQUIRED", "false")
    monkeypatch.setenv("RUN_MODEL_INTEGRATION", "1")
    monkeypatch.setenv("RELEASE_DISPOSABLE_POSTGRES", "1")
    for name in URLS:
        monkeypatch.setenv(
            name, "postgresql+psycopg://test:test@localhost/release_gate"
        )


@pytest.mark.parametrize("name", URLS)
def test_missing_postgres_suite_is_fatal(monkeypatch, name):
    valid_environment(monkeypatch)
    monkeypatch.delenv(name)
    with pytest.raises(SystemExit, match="All seven"):
        preflight()


def test_disabled_real_models_are_fatal(monkeypatch):
    valid_environment(monkeypatch)
    monkeypatch.setenv("RUN_MODEL_INTEGRATION", "0")
    with pytest.raises(SystemExit, match="RUN_MODEL_INTEGRATION"):
        preflight()


def test_inherited_production_test_setting_is_fatal(monkeypatch):
    valid_environment(monkeypatch)
    monkeypatch.setenv("ML_MODEL_REQUIRED", "true")
    with pytest.raises(SystemExit, match="Backend test fixtures"):
        preflight()


def test_missing_artifact_secret_is_fatal(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["provision_models.py"])
    monkeypatch.delenv("LEGACY_MODEL_BASE64", raising=False)
    with pytest.raises(SystemExit, match="secret is unavailable"):
        provision()


@pytest.mark.parametrize(
    "labels",
    [
        {},
        {
            "com.docker.compose.project": "shared",
            "org.student-warning.release-run": "ours",
        },
        {
            "com.docker.compose.project": "ours",
            "org.student-warning.release-run": "another",
        },
    ],
)
def test_cleanup_refuses_unidentified_or_other_docker_resources(labels):
    with pytest.raises(RuntimeError, match="Refusing cleanup"):
        require_ownership(labels, "ours", "ours")


@pytest.mark.parametrize(
    "test_body,expected",
    [
        ("def test_probe(): pass", 0),
        ("def test_probe(): pytest.skip('deliberate negative control')", 1),
        (
            "@pytest.fixture\ndef setup_probe(): pytest.skip('setup negative control')\ndef test_probe(setup_probe): pass",
            1,
        ),
    ],
)
def test_real_pytest_process_cannot_report_skips_as_success(
    tmp_path, test_body, expected
):
    (tmp_path / "test_probe.py").write_text("import pytest\n" + test_body + "\n")
    script = Path(__file__).resolve().parent
    program = (
        "import sys; from pathlib import Path; "
        f"sys.path.insert(0, {str(script)!r}); "
        "import pytest, release_backend; "
        "release_backend.REQUIRED_MODULES={'test_probe.py'}; "
        "raise SystemExit(pytest.main(['-q','test_probe.py'], "
        "plugins=[release_backend.NoSkips(Path('summary.json'))]))"
    )
    result = subprocess.run(
        [sys.executable, "-c", program],
        cwd=tmp_path,
        env=dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD="1"),
        capture_output=True,
        text=True,
    )
    assert result.returncode == expected, result.stdout + result.stderr
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["exit_code"] == expected
    assert bool(summary["skipped"]) == bool(expected)


@pytest.mark.parametrize("version", CHECKSUMS)
def test_corrupt_artifact_rejected_before_deserialization(version):
    with pytest.raises(SystemExit, match="checksum mismatch"):
        verify_bytes(version, b"untrusted pickle bytes")


@pytest.mark.parametrize(
    "skipped,passed,collected,expected",
    [
        (["test_skipped"], 1, 2, 1),
        ([], 0, 0, 1),
        ([], 1, 2, 1),
        ([], 2, 2, 0),
    ],
)
def test_skips_empty_or_incomplete_runs_cannot_pass(
    tmp_path, skipped, passed, collected, expected
):
    guard = NoSkips(tmp_path / "summary.json")
    guard.skipped, guard.passed, guard.collected = skipped, passed, collected
    session = SimpleNamespace(exitstatus=0)
    guard.pytest_sessionfinish(session, 0)
    assert session.exitstatus == expected


def test_missing_required_module_is_fatal(tmp_path):
    guard = NoSkips(tmp_path / "summary.json")
    with pytest.raises(pytest.UsageError, match="Mandatory suites absent"):
        guard.pytest_collection_finish(SimpleNamespace(items=[]))
