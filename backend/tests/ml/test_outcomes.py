"""Stage contracts, actual multiclass candidates, verification and calibration."""

import json
import shutil

import numpy as np
import pandas as pd
import pytest
from app.core.exceptions import ApplicationError
from app.ml.deployment import registry_sha256
from app.ml.feature_schema import (
    BINARY_TARGET_ENCODING,
    PREDICTION_FEATURES,
    SourceStage,
)
from app.ml.outcomes import deployment
from app.ml.outcomes.contracts import (
    CLASS_LABELS,
    MODEL_VERSIONS,
    OUTCOME_ENCODING,
    PredictionStage,
    feature_names,
)
from app.ml.outcomes.data import encode_target, make_split, select_features
from app.ml.outcomes.metrics import evaluate, validate_probabilities
from app.ml.outcomes.modeling import (
    candidates,
    preprocessor,
    select_winner,
    train_candidates,
)
from app.ml.outcomes.training import calibrate_thresholds

from tests.ml.test_training_pipeline import _synthetic_features


@pytest.mark.parametrize(
    "stage,count",
    [(PredictionStage.ENROLLMENT, 21), (PredictionStage.FIRST_SEMESTER, 27)],
)
def test_ordered_stage_features_exclude_future_and_unverified_macro(stage, count):
    names = feature_names(stage)
    assert len(names) == count
    assert names == tuple(
        f.name
        for f in PREDICTION_FEATURES
        if f.source_stage == SourceStage.ENROLLMENT
        or (
            stage == PredictionStage.FIRST_SEMESTER
            and f.source_stage == SourceStage.FIRST_SEMESTER
        )
    )
    assert not {"unemployment_rate", "inflation_rate", "gdp", "Target"}.intersection(
        names
    )
    assert all("second" not in name for name in names)
    assert tuple(select_features(_synthetic_features(), stage).columns) == names
    assert len(PREDICTION_FEATURES) == 30
    assert dict(BINARY_TARGET_ENCODING) == {"Dropout": 1, "Enrolled": 0, "Graduate": 0}


def test_separate_encoding_and_deterministic_disjoint_partitions():
    y = encode_target(pd.Series(["Dropout", "Enrolled", "Graduate"] * 100))
    assert y.iloc[:3].tolist() == [0, 1, 2]
    assert dict(OUTCOME_ENCODING) == {"Dropout": 0, "Enrolled": 1, "Graduate": 2}
    for bad in (pd.Series(["Unknown"]), pd.Series([None])):
        with pytest.raises(ValueError):
            encode_target(bad)
    X = _synthetic_features(300)
    first, second = make_split(X, y), make_split(X, y)
    assert first == second
    groups = [
        set(getattr(first, key))
        for key in (
            "fitting",
            "probability_calibration",
            "threshold_calibration",
            "final_test",
        )
    ]
    assert set.union(*groups) == set(range(300))
    assert sum(len(g) for g in groups) == 300
    assert len(first.final_test) == 60
    assert all(set(y.loc[list(group)]) == {0, 1, 2} for group in groups)


def test_preprocessor_learns_only_fitting_rows_and_handles_unknown_categories():
    X = select_features(_synthetic_features(100), PredictionStage.ENROLLMENT)
    fit = X.iloc[:50].copy()
    transform = preprocessor(PredictionStage.ENROLLMENT).fit(fit)
    numeric = transform.named_transformers_["numeric"]
    columns = transform.transformers_[0][2]
    assert np.allclose(numeric.named_steps["scaler"].mean_, fit[columns].mean())
    unseen = X.iloc[[99]].copy()
    unseen["course_code"] = 123456
    before = numeric.named_steps["scaler"].mean_.copy()
    transformed = transform.transform(unseen)
    assert transformed.shape[0] == 1
    assert np.array_equal(before, numeric.named_steps["scaler"].mean_)


@pytest.mark.parametrize("stage", list(PredictionStage))
def test_three_candidate_families_train_actual_multiclass_pipelines(stage):
    X = select_features(_synthetic_features(150), stage)
    y = pd.Series([0, 1, 2] * 50)
    results = train_candidates(X, y, stage, iterations=1, jobs=1)
    assert {item["name"] for item in results} == {
        "Logistic Regression",
        "Random Forest",
        "XGBoost",
    }
    for item in results:
        estimator = item["estimator"]
        assert tuple(estimator.classes_) == (0, 1, 2)
        assert validate_probabilities(estimator.predict_proba(X.iloc[:3])).shape == (
            3,
            3,
        )
    xgb = candidates(stage)["XGBoost"][0].named_steps["model"]
    assert xgb.objective == "multi:softprob" and xgb.get_params()["num_class"] == 3


def test_selection_uses_constraints_and_dropout_score_not_accuracy():
    results = []
    for name, recall, pr, f1, precision, accuracy in (
        ("Logistic Regression", 0.80, 0.75, 0.65, 0.60, 0.70),
        ("Random Forest", 0.50, 0.90, 0.80, 0.90, 0.95),
        ("XGBoost", 0.60, 0.70, 0.60, 0.70, 0.85),
    ):
        results.append(
            {
                "name": name,
                "cv_metrics": {
                    "dropout_recall": recall,
                    "dropout_pr_auc": pr,
                    "macro_f1": f1,
                    "dropout_precision": precision,
                    "accuracy": accuracy,
                },
            }
        )
    assert select_winner(results)["name"] == "Logistic Regression"
    for result in results:
        result["cv_metrics"]["dropout_recall"] = 0.10
    with pytest.raises(ValueError, match="No candidate"):
        select_winner(results)


def test_calibration_order_recall_targets_and_constant_probability_failure():
    y = np.array([0] * 20 + [1] * 20 + [2] * 20)
    p = np.r_[
        np.linspace(0.1, 0.9, 20),
        np.linspace(0.01, 0.6, 20),
        np.linspace(0.01, 0.5, 20),
    ]
    result = calibrate_thresholds(y, p)
    assert result["low_threshold"] < result["high_threshold"]
    assert result["low_achieved_recall"] >= 0.90
    assert result["high_achieved_recall"] >= 0.70
    with pytest.raises(ValueError, match="Ordered"):
        calibrate_thresholds(y, np.full(60, 0.3))


@pytest.mark.parametrize(
    "values", [[[0.2, 0.3, 0.3]], [[np.nan, 0.2, 0.8]], [[1.1, -0.1, 0]], [[0.2, 0.8]]]
)
def test_invalid_probability_contract(values):
    with pytest.raises(ValueError):
        validate_probabilities(values)


def test_metrics_report_class_order_and_calibration():
    report = evaluate([0, 1, 2], np.eye(3), scope="FINAL_TEST_SET")
    assert report["macro_f1"] == 1 and report["dropout_recall"] == 1
    assert report["confusion_matrix"]["labels"] == list(CLASS_LABELS)
    assert (
        report["confusion_matrix"]["rows_actual_columns_predicted"]
        == np.eye(3, dtype=int).tolist()
    )
    assert report["calibration"]["dropout_brier_score"] == 0


@pytest.mark.parametrize("stage", list(PredictionStage))
def test_real_verified_b1_bundles_verify_and_explain_exact_probability_perturbation(
    stage,
):
    bundle, metadata, _, manifest = deployment.verify(stage)
    row = pd.DataFrame([bundle.explanation_reference], columns=bundle.feature_names)
    assert bundle.predict_proba(row).shape == (1, 3)
    assert manifest["prediction_stage"] == stage
    assert bundle.model_version == MODEL_VERSIONS[stage]
    row.loc[0, "admission_grade"] = 120
    factors = bundle.explain_local(row, top_k=None)
    observed = float(bundle.predict_proba(row)[0, 0])
    for factor in factors:
        perturbed = row.astype(float).copy()
        perturbed.loc[0, factor["feature"]] = factor["reference_value"]
        assert factor["contribution"] == pytest.approx(
            observed - float(bundle.predict_proba(perturbed)[0, 0])
        )
    assert metadata["thresholds"]["low_threshold"] == bundle.low_threshold
    assert "not SHAP" in bundle.explanation_method


def _copy_registry(tmp_path, stage):
    version = MODEL_VERSIONS[stage]
    shutil.copytree(
        deployment.ML_ROOT / "model_registry" / version,
        tmp_path / "model_registry" / version,
    )
    directory = tmp_path / "artifacts" / version
    directory.mkdir(parents=True)
    (directory / "model.joblib").write_bytes(
        (deployment.ML_ROOT / "artifacts" / version / "model.joblib").read_bytes()
    )
    return directory / "model.joblib"


def test_checksum_is_checked_before_deserialization(monkeypatch, tmp_path):
    stage = PredictionStage.ENROLLMENT
    artifact = _copy_registry(tmp_path, stage)
    artifact.write_bytes(b"untrusted pickle bytes")

    def forbidden(*args, **kwargs):
        pytest.fail("Deserialization occurred before checksum rejection")

    monkeypatch.setattr(deployment.joblib, "load", forbidden)
    with pytest.raises(ApplicationError) as raised:
        deployment.verify(stage, root=tmp_path)
    assert raised.value.code == "MODEL_CHECKSUM_MISMATCH"


def test_missing_stage_artifact_never_falls_back(tmp_path):
    artifact = _copy_registry(tmp_path, PredictionStage.FIRST_SEMESTER)
    artifact.unlink()
    with pytest.raises(ApplicationError) as raised:
        deployment.verify(PredictionStage.FIRST_SEMESTER, root=tmp_path)
    assert raised.value.code == "MODEL_ARTIFACT_UNAVAILABLE"


def test_mapping_mismatch_rejected_even_if_manifest_hash_is_updated(tmp_path):
    stage = PredictionStage.ENROLLMENT
    _copy_registry(tmp_path, stage)
    registry = tmp_path / "model_registry" / MODEL_VERSIONS[stage]
    metadata = json.loads((registry / "metadata.json").read_bytes())
    metadata["target_mapping"] = {"Dropout": 1, "Enrolled": 0, "Graduate": 2}
    (registry / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    manifest = json.loads((registry / "artifact_manifest.json").read_bytes())
    manifest["registry_sha256"]["metadata.json"] = registry_sha256(
        (registry / "metadata.json").read_bytes()
    )
    (registry / "artifact_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    with pytest.raises(ApplicationError) as raised:
        deployment.verify(stage, root=tmp_path)
    assert raised.value.code == "MODEL_REGISTRY_MISMATCH"


@pytest.mark.parametrize("field", ["selection_score", "final_test"])
def test_inconsistent_candidate_audit_rejected_with_matching_document_hashes(tmp_path, field):
    stage = PredictionStage.ENROLLMENT
    _copy_registry(tmp_path, stage)
    registry = tmp_path / "model_registry" / MODEL_VERSIONS[stage]
    selection = json.loads((registry / "model_selection.json").read_bytes())
    winner = next(c for c in selection["candidates"] if c["name"] == selection["winner"])
    if field == "selection_score":
        winner[field] = 0.99
    else:
        winner[field]["accuracy"] = 0.99
    evaluation = json.loads((registry / "evaluation.json").read_bytes())
    evaluation["candidate_comparison"] = selection["candidates"]
    manifest = json.loads((registry / "artifact_manifest.json").read_bytes())
    for filename, document in (("model_selection.json", selection), ("evaluation.json", evaluation)):
        (registry / filename).write_text(json.dumps(document), encoding="utf-8")
        manifest["registry_sha256"][filename] = registry_sha256((registry / filename).read_bytes())
    (registry / "artifact_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ApplicationError) as raised:
        deployment.verify(stage, root=tmp_path)
    assert raised.value.code == "MODEL_REGISTRY_MISMATCH"
