import json
import os
import shutil

import joblib
import pandas as pd
import pytest
from app.core.config import get_settings
from app.core.exceptions import ApplicationError
from app.ml import deployment, runtime


@pytest.fixture()
def registry(tmp_path, verified_model_fixture, monkeypatch):
    shutil.copytree(verified_model_fixture, tmp_path, dirs_exist_ok=True)
    for field, name in (
        ("ml_model_path", "model.joblib"),
        ("ml_metadata_path", "metadata.json"),
        ("ml_evaluation_path", "evaluation.json"),
        ("ml_manifest_path", "artifact_manifest.json"),
    ):
        monkeypatch.setattr(get_settings(), field, str(tmp_path / name))
    return tmp_path


def edit_json(path, change):
    value = json.loads(path.read_bytes())
    change(value)
    path.write_text(json.dumps(value), encoding="utf-8")


def expect_error(code):
    with pytest.raises(ApplicationError) as raised:
        runtime.get_model_runtime()
    assert raised.value.code == code
    assert str(get_settings().ml_model_path) not in raised.value.message


def test_valid_inference_after_verified_load():
    model = runtime.get_model_runtime()
    row = pd.DataFrame(
        [model.bundle.explanation_reference], columns=model.feature_names
    )
    assert 0 <= model.predict_probability(row) <= 1
    assert len(model.explain(row)) == 5


@pytest.mark.parametrize(
    "content,code",
    [(b"", "MODEL_ARTIFACT_CORRUPTED"), (b"tampered", "MODEL_CHECKSUM_MISMATCH")],
)
def test_invalid_bytes_never_deserialized(registry, monkeypatch, content, code):
    (registry / "model.joblib").write_bytes(content)
    monkeypatch.setattr(
        deployment.joblib,
        "load",
        lambda _: pytest.fail("Unverified pickle deserialized"),
    )
    expect_error(code)


def test_corrupt_but_checksum_verified_bytes(registry):
    # This imitates a malformed artifact from the trusted publisher.
    (registry / "model.joblib").write_bytes(b"not a pickle")
    deployment.write_manifest(registry / "model.joblib", registry)
    expect_error("MODEL_ARTIFACT_CORRUPTED")


@pytest.mark.parametrize(
    "field,value",
    [
        ("model_version", "wrong-v2"),
        ("feature_schema_version", "wrong-schema"),
        ("features", ["wrong-feature"]),
    ],
)
def test_registry_contract_mismatch(registry, field, value):
    edit_json(registry / "metadata.json", lambda d: d.update({field: value}))
    deployment.write_manifest(registry / "model.joblib", registry)
    expect_error("MODEL_REGISTRY_MISMATCH")


def test_changed_registry_detected_before_deserialization(registry, monkeypatch):
    edit_json(
        registry / "metadata.json", lambda d: d.update(trained_at="different-run")
    )
    monkeypatch.setattr(
        deployment.joblib,
        "load",
        lambda _: pytest.fail("Registry mismatch deserialized"),
    )
    expect_error("MODEL_REGISTRY_MISMATCH")


@pytest.mark.parametrize(
    "field,value",
    [
        ("model_version", "wrong-v2"),
        ("feature_names", ("wrong",)),
        ("low_threshold", 0.1),
    ],
)
def test_loaded_bundle_mismatch(registry, field, value):
    bundle, _, _ = deployment.verify(registry / "model.joblib", registry)
    setattr(bundle, field, value)
    joblib.dump(bundle, registry / "model.joblib")
    deployment.write_manifest(registry / "model.joblib", registry)
    expect_error("MODEL_REGISTRY_MISMATCH")


@pytest.mark.parametrize("package", ["python", "scikit-learn", "numpy", "scipy"])
def test_incompatible_runtime_not_deserialized(registry, monkeypatch, package):
    versions = deployment.runtime_versions()
    versions[package] = "0.0.0"
    monkeypatch.setattr(deployment, "runtime_versions", lambda: versions)
    monkeypatch.setattr(
        deployment.joblib,
        "load",
        lambda _: pytest.fail("Incompatible pickle deserialized"),
    )
    expect_error("MODEL_RUNTIME_INCOMPATIBLE")


def test_install_rejects_untrusted_source_without_replacing_valid_model(registry):
    source = registry / "untrusted.joblib"
    source.write_bytes(b"bad")
    destination = registry / "model.joblib"
    original = destination.read_bytes()
    with pytest.raises(ApplicationError, match="checksum"):
        deployment.install(source, destination, registry)
    assert destination.read_bytes() == original


def test_install_valid_source(registry, tmp_path):
    destination = tmp_path / "installed" / "model.joblib"
    deployment.install(registry / "model.joblib", destination, registry)
    assert destination.read_bytes() == (registry / "model.joblib").read_bytes()
    assert deployment.verify(destination, registry)[0]


@pytest.mark.parametrize(
    "name", ["model.joblib", "artifact_manifest.json", "split_manifest.json"]
)
def test_missing_artifact_or_required_record(registry, name):
    (registry / name).unlink()
    expect_error("MODEL_ARTIFACT_UNAVAILABLE")


def test_registry_hash_is_stable_across_json_formatting(registry):
    for name in ("metadata.json", "evaluation.json", "split_manifest.json"):
        path = registry / name
        path.write_bytes(json.dumps(json.loads(path.read_bytes())).encode())
    assert deployment.verify(registry / "model.joblib", registry)[0]


@pytest.mark.parametrize("production", [False, True])
def test_required_model_fails_startup_even_with_cached_error(
    registry, monkeypatch, production
):
    (registry / "model.joblib").unlink()
    assert runtime.initialize_model_runtime() is None
    monkeypatch.setattr(get_settings(), "ml_model_required", not production)
    monkeypatch.setattr(
        get_settings(), "app_env", "production" if production else "development"
    )
    with pytest.raises(ApplicationError):
        runtime.initialize_model_runtime()


@pytest.mark.model_integration
def test_actual_trained_artifact():
    if os.environ.get("RUN_MODEL_INTEGRATION") != "1":
        pytest.skip("Run offline preparation then set RUN_MODEL_INTEGRATION=1")
    model = runtime.get_model_runtime()
    assert model.bundle.model_version == "dropout-logistic-regression-v1"
    row = pd.DataFrame(
        [model.bundle.explanation_reference], columns=model.feature_names
    )
    assert 0 <= model.predict_probability(row) <= 1
    assert len(model.explain(row)) == 5
