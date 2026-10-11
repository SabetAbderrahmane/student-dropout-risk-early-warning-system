import json
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.core.exceptions import ApplicationError
from app.ml import runtime
from app.ml import deployment


@pytest.fixture(autouse=True)
def clean_runtime_cache():
    runtime.reset_model_runtime()
    yield
    runtime.reset_model_runtime()


def test_runtime_loads_once_and_matches_registry(monkeypatch) -> None:
    calls = 0
    original_load = deployment.joblib.load

    def counted_load(path):
        nonlocal calls
        calls += 1
        return original_load(path)

    monkeypatch.setattr(deployment.joblib, "load", counted_load)
    first = runtime.get_model_runtime()
    second = runtime.get_model_runtime()
    assert first is second
    assert calls == 1
    assert first.bundle.model_version == first.metadata["model_version"]
    assert list(first.bundle.feature_names) == first.metadata["features"]
    assert first.bundle.low_threshold == first.metadata["thresholds"]["low_threshold"]
    assert first.bundle.high_threshold == first.metadata["thresholds"]["high_threshold"]


def test_missing_artifact_is_controlled(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        get_settings(), "ml_model_path", str(tmp_path / "missing.joblib")
    )
    with pytest.raises(ApplicationError) as raised:
        runtime.get_model_runtime()
    assert raised.value.code == "MODEL_ARTIFACT_UNAVAILABLE"


def test_mismatched_metadata_is_controlled(monkeypatch, tmp_path: Path) -> None:
    settings = get_settings()
    metadata = json.loads(Path(settings.ml_metadata_path).read_text(encoding="utf-8"))
    metadata["thresholds"]["low_threshold"] = 0.1
    mismatched = tmp_path / "metadata.json"
    mismatched.write_text(json.dumps(metadata), encoding="utf-8")
    (tmp_path / "split_manifest.json").write_bytes(
        (Path(settings.ml_metadata_path).parent / "split_manifest.json").read_bytes()
    )
    monkeypatch.setattr(settings, "ml_metadata_path", str(mismatched))
    with pytest.raises(ApplicationError) as raised:
        runtime.get_model_runtime()
    assert raised.value.code == "MODEL_REGISTRY_MISMATCH"
