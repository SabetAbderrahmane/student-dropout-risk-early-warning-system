import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from app.ml.feature_schema import (
    BINARY_TARGET_ENCODING,
    EXCLUDED_SECOND_SEMESTER_OFFICIAL_NAMES,
    FeatureKind,
    PREDICTION_FEATURES,
)
from app.ml.training.artifact import EXPLANATION_METHOD, build_bundle
from app.ml.training.data import (
    CANONICAL_FEATURE_NAMES,
    EXPECTED_UCI_FEATURE_COLUMNS,
    OFFICIAL_TO_CANONICAL,
    encode_binary_target,
    make_final_split,
    map_uci_features,
    validate_uci_schema,
)
from app.ml.training.metadata import (
    FEATURE_SCHEMA_VERSION,
    split_index_hash,
    validate_artifact_consistency,
    validate_metadata,
    validate_registry_consistency,
)
from app.ml.training.modeling import candidate_definitions, make_preprocessor
from app.ml.training.thresholds import calibrate_thresholds, risk_level
from app.ml.training.train import (
    DEFAULT_ARTIFACT_DIRECTORY,
    DEFAULT_REGISTRY_DIRECTORY,
)


def _synthetic_features(rows: int = 100) -> pd.DataFrame:
    data: dict[str, np.ndarray] = {}
    for feature in PREDICTION_FEATURES:
        if feature.allowed_values:
            allowed = sorted(feature.allowed_values)
            data[feature.name] = np.array(
                [allowed[index % len(allowed)] for index in range(rows)]
            )
        else:
            lower = float(feature.minimum or 0)
            upper = float(feature.maximum or lower + 20)
            if upper == lower:
                upper += 1
            values = np.linspace(lower, upper, rows)
            data[feature.name] = (
                values.astype(int) if feature.data_type.value == "INTEGER" else values
            )
    return pd.DataFrame(data, columns=CANONICAL_FEATURE_NAMES)


def _fitted_bundle() -> tuple[object, pd.DataFrame]:
    X = _synthetic_features()
    y = pd.Series(([0, 1] * 50), name="dropout")
    pipeline = Pipeline(
        [
            ("preprocess", make_preprocessor()),
            (
                "model",
                LogisticRegression(class_weight="balanced", max_iter=1000),
            ),
        ]
    ).fit(X, y)
    return (
        build_bundle(
            pipeline,
            model_name="Logistic Regression",
            model_version="test-v1",
            low_threshold=0.3,
            high_threshold=0.7,
            X_development=X,
        ),
        X,
    )


def _valid_metadata() -> dict[str, object]:
    development_indices = list(range(80))
    final_test_indices = list(range(80, 100))
    return {
        "model_name": "Logistic Regression",
        "model_version": "test-v1",
        "trained_at": "2026-09-30T00:00:00+00:00",
        "dataset": {"dataset_id": 697},
        "target_mapping": dict(BINARY_TARGET_ENCODING),
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "features": list(CANONICAL_FEATURE_NAMES),
        "random_seed": 42,
        "counts": {
            "total": 100,
            "training": 80,
            "development": 80,
            "final_test": 20,
        },
        "class_distribution": {},
        "preprocessing": "test",
        "selected_hyperparameters": {},
        "split_manifest": {
            "path": "split_manifest.json",
            "development_index_sha256": split_index_hash(development_indices),
            "final_test_index_sha256": split_index_hash(final_test_indices),
        },
        "thresholds": {"low_threshold": 0.3, "high_threshold": 0.7},
        "final_test_metrics": {
            "evaluation_scope": "FINAL_TEST_SET",
            "sample_size": 20,
            "confusion_matrix": {"tp": 5, "fp": 5, "tn": 5, "fn": 5},
        },
        "explanation_method": EXPLANATION_METHOD,
        "artifact_path": "app/ml/artifacts/dropout-risk-v1/model.joblib",
        "library_versions": {},
    }


def test_official_uci_columns_map_to_exact_canonical_order() -> None:
    official = pd.DataFrame(
        {column: [index] for index, column in enumerate(EXPECTED_UCI_FEATURE_COLUMNS)}
    )
    target = pd.DataFrame({"Target": ["Dropout"]})
    validate_uci_schema(official, target)

    mapped = map_uci_features(official)

    assert tuple(mapped.columns) == CANONICAL_FEATURE_NAMES
    assert len(mapped.columns) == 30
    assert "Target" not in mapped
    assert not set(EXCLUDED_SECOND_SEMESTER_OFFICIAL_NAMES) & set(mapped.columns)
    for official_name, canonical_name in OFFICIAL_TO_CANONICAL.items():
        assert mapped.loc[0, canonical_name] == official.loc[0, official_name]


def test_uci_schema_mismatch_fails_loudly() -> None:
    official = pd.DataFrame({column: [0] for column in EXPECTED_UCI_FEATURE_COLUMNS})
    official = official.drop(columns=[next(iter(EXPECTED_UCI_FEATURE_COLUMNS))])
    with pytest.raises(ValueError, match="schema mismatch"):
        validate_uci_schema(official, pd.DataFrame({"Target": ["Dropout"]}))


def test_binary_target_encoding_is_exact() -> None:
    target = pd.Series(["Dropout", "Graduate", "Enrolled"])
    assert encode_binary_target(target).tolist() == [1, 0, 0]
    assert dict(BINARY_TARGET_ENCODING) == {
        "Dropout": 1,
        "Graduate": 0,
        "Enrolled": 0,
    }


def test_binary_target_rejects_unknown_label() -> None:
    with pytest.raises(ValueError, match="Unexpected"):
        encode_binary_target(pd.Series(["Dropout", "Withdrawn"]))


def test_final_split_is_deterministic_stratified_and_seeded() -> None:
    X = _synthetic_features()
    y = pd.Series(([0, 1] * 50), index=X.index)
    first = make_final_split(X, y)
    second = make_final_split(X, y)

    assert first.development_indices == second.development_indices
    assert first.final_test_indices == second.final_test_indices
    assert len(first.X_development) == 80
    assert len(first.X_final_test) == 20
    assert first.y_final_test.value_counts().to_dict() == {0: 10, 1: 10}
    assert not set(first.development_indices) & set(first.final_test_indices)


def test_preprocessing_and_model_pipeline_probability_range() -> None:
    bundle, X = _fitted_bundle()
    probabilities = bundle.predict_proba(X.iloc[:8])
    assert probabilities.shape == (8,)
    assert np.all((0 <= probabilities) & (probabilities <= 1))
    assert bundle.feature_names == CANONICAL_FEATURE_NAMES


def test_artifact_reload_predict_and_local_explanation_schema(tmp_path: Path) -> None:
    bundle, X = _fitted_bundle()
    artifact_path = tmp_path / "model.joblib"
    joblib.dump(bundle, artifact_path)

    reloaded = joblib.load(artifact_path)
    probability = reloaded.predict_proba(X.iloc[[0]])[0]
    explanation = reloaded.explain_local(X.iloc[0], top_k=5)

    assert 0 <= probability <= 1
    assert len(explanation) == 5
    assert all(
        set(item) == {"feature", "label", "value", "contribution"}
        for item in explanation
    )
    assert all(item["feature"] in CANONICAL_FEATURE_NAMES for item in explanation)


def test_artifact_rejects_wrong_feature_order() -> None:
    bundle, X = _fitted_bundle()
    reversed_columns = X.loc[:, list(reversed(X.columns))]
    with pytest.raises(ValueError, match="canonical feature order"):
        bundle.predict_proba(reversed_columns.iloc[:1])


def test_risk_threshold_boundaries() -> None:
    assert risk_level(0.29, 0.3, 0.7) == "LOW"
    assert risk_level(0.30, 0.3, 0.7) == "MEDIUM"
    assert risk_level(0.69, 0.3, 0.7) == "MEDIUM"
    assert risk_level(0.70, 0.3, 0.7) == "HIGH"


def test_threshold_calibration_is_reproducible_and_ordered() -> None:
    y = np.array([0, 0, 0, 0, 1, 1, 1, 1])
    probabilities = np.array([0.05, 0.10, 0.30, 0.40, 0.25, 0.55, 0.80, 0.95])
    first = calibrate_thresholds(y, probabilities)
    second = calibrate_thresholds(y, probabilities)
    assert first == second
    assert 0 <= first.low_threshold < first.high_threshold <= 1


def test_candidate_families_and_algorithm_level_weighting() -> None:
    y = pd.Series([0] * 60 + [1] * 40)
    candidates = candidate_definitions(y)
    assert set(candidates) == {"Logistic Regression", "Random Forest", "XGBoost"}
    assert candidates["Logistic Regression"][0]["model"].class_weight == "balanced"
    assert candidates["Random Forest"][0]["model"].class_weight == "balanced"
    assert candidates["XGBoost"][0]["model"].scale_pos_weight == pytest.approx(1.5)


def test_metadata_validation_accepts_complete_consistent_document() -> None:
    validate_metadata(_valid_metadata())


def test_registry_and_artifact_records_agree_without_training() -> None:
    metadata = _valid_metadata()
    bundle, _ = _fitted_bundle()
    evaluation = {
        "model_name": metadata["model_name"],
        "model_version": metadata["model_version"],
        "threshold_calibration": metadata["thresholds"],
        "final_test": metadata["final_test_metrics"],
    }
    split_manifest = {
        "random_seed": 42,
        "stratified": True,
        "development_indices": list(range(80)),
        "final_test_indices": list(range(80, 100)),
    }

    validate_registry_consistency(metadata, evaluation, split_manifest)
    validate_artifact_consistency(bundle, metadata)


def test_default_binary_and_registry_destinations_are_separate() -> None:
    assert DEFAULT_ARTIFACT_DIRECTORY.name == "dropout-risk-v1"
    assert DEFAULT_ARTIFACT_DIRECTORY.parent.name == "artifacts"
    assert DEFAULT_REGISTRY_DIRECTORY.name == "dropout-risk-v1"
    assert DEFAULT_REGISTRY_DIRECTORY.parent.name == "model_registry"
    assert DEFAULT_ARTIFACT_DIRECTORY != DEFAULT_REGISTRY_DIRECTORY


def test_tracked_registry_snapshot_is_complete_and_consistent() -> None:
    metadata = json.loads(
        (DEFAULT_REGISTRY_DIRECTORY / "metadata.json").read_text(encoding="utf-8")
    )
    evaluation = json.loads(
        (DEFAULT_REGISTRY_DIRECTORY / "evaluation.json").read_text(encoding="utf-8")
    )
    split_manifest = json.loads(
        (DEFAULT_REGISTRY_DIRECTORY / "split_manifest.json").read_text(
            encoding="utf-8"
        )
    )

    validate_registry_consistency(metadata, evaluation, split_manifest)
    assert metadata["dataset"]["dataset_id"] == 697
    assert tuple(metadata["features"]) == CANONICAL_FEATURE_NAMES
    assert (DEFAULT_REGISTRY_DIRECTORY / "training_report.md").is_file()


def test_metadata_validation_rejects_noncanonical_features() -> None:
    metadata = {
        key: value
        for key, value in {
            "model_name": "Logistic Regression",
            "model_version": "x",
            "trained_at": "x",
            "dataset": {"dataset_id": 697},
            "target_mapping": dict(BINARY_TARGET_ENCODING),
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "features": list(reversed(CANONICAL_FEATURE_NAMES)),
            "random_seed": 42,
            "counts": {
                "total": 2,
                "training": 1,
                "development": 1,
                "final_test": 1,
            },
            "class_distribution": {},
            "preprocessing": "x",
            "selected_hyperparameters": {},
            "split_manifest": {
                "path": "split_manifest.json",
                "development_index_sha256": "present",
                "final_test_index_sha256": "present",
            },
            "thresholds": {"low_threshold": 0.3, "high_threshold": 0.7},
            "final_test_metrics": {
                "evaluation_scope": "FINAL_TEST_SET",
                "sample_size": 1,
                "confusion_matrix": {"tp": 1, "fp": 0, "tn": 0, "fn": 0},
            },
            "explanation_method": "x",
            "artifact_path": "x",
            "library_versions": {},
        }.items()
    }
    with pytest.raises(ValueError, match="canonical order"):
        validate_metadata(metadata)
