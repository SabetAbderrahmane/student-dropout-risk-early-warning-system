"""Metadata construction, validation, and JSON serialization."""

import json
from pathlib import Path
from typing import Any

from app.ml.feature_schema import BINARY_TARGET_ENCODING
from app.ml.training.data import CANONICAL_FEATURE_NAMES, DATASET_ID

FEATURE_SCHEMA_VERSION = "uci697-first-semester-v1"
REQUIRED_METADATA_KEYS = {
    "model_name",
    "model_version",
    "trained_at",
    "dataset",
    "target_mapping",
    "feature_schema_version",
    "features",
    "random_seed",
    "counts",
    "class_distribution",
    "preprocessing",
    "selected_hyperparameters",
    "thresholds",
    "final_test_metrics",
    "explanation_method",
    "artifact_path",
    "library_versions",
}


def validate_metadata(metadata: dict[str, Any]) -> None:
    missing = sorted(REQUIRED_METADATA_KEYS - metadata.keys())
    if missing:
        raise ValueError(f"Metadata is missing required keys: {missing}")
    if metadata["dataset"].get("dataset_id") != DATASET_ID:
        raise ValueError("Metadata dataset ID is not 697")
    if metadata["model_name"] not in {
        "Logistic Regression",
        "Random Forest",
        "XGBoost",
    }:
        raise ValueError("Metadata model name is not a locked candidate")
    if dict(metadata["target_mapping"]) != dict(BINARY_TARGET_ENCODING):
        raise ValueError("Metadata target mapping does not match the frozen contract")
    if metadata["feature_schema_version"] != FEATURE_SCHEMA_VERSION:
        raise ValueError("Metadata feature schema version is invalid")
    if tuple(metadata["features"]) != CANONICAL_FEATURE_NAMES:
        raise ValueError("Metadata features do not match canonical order")
    if metadata["random_seed"] != 42:
        raise ValueError("Metadata random seed must be 42")
    counts = metadata["counts"]
    if counts.get("training") != counts.get("development"):
        raise ValueError("Training and development counts must match")
    if counts.get("total") != counts.get("development", 0) + counts.get(
        "final_test", 0
    ):
        raise ValueError("Metadata split counts do not add up")
    thresholds = metadata["thresholds"]
    if not 0 <= thresholds["low_threshold"] < thresholds["high_threshold"] <= 1:
        raise ValueError("Metadata thresholds are invalid")
    final = metadata["final_test_metrics"]
    if final.get("evaluation_scope") != "FINAL_TEST_SET":
        raise ValueError("Final-test metrics have the wrong evaluation scope")
    matrix_total = sum(final["confusion_matrix"].values())
    if matrix_total != final["sample_size"]:
        raise ValueError("Final-test confusion matrix does not match sample size")
    if final["sample_size"] != counts["final_test"]:
        raise ValueError("Final-test metrics and split counts disagree")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
