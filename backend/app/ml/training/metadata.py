"""Metadata construction, validation, and JSON serialization."""

import hashlib
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
    "split_manifest",
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
    split_fingerprints = metadata["split_manifest"]
    if not split_fingerprints.get("development_index_sha256") or not split_fingerprints.get(
        "final_test_index_sha256"
    ):
        raise ValueError("Metadata split fingerprints are missing")


def split_index_hash(indices: list[int] | tuple[int, ...]) -> str:
    payload = ",".join(str(index) for index in indices).encode()
    return hashlib.sha256(payload).hexdigest()


def validate_registry_consistency(
    metadata: dict[str, Any],
    evaluation: dict[str, Any],
    split_manifest: dict[str, Any],
) -> None:
    """Verify that all tracked records describe one internally consistent run."""
    validate_metadata(metadata)
    if evaluation.get("model_name") != metadata["model_name"]:
        raise ValueError("Registry model names disagree")
    if evaluation.get("model_version") != metadata["model_version"]:
        raise ValueError("Registry model versions disagree")
    if evaluation.get("threshold_calibration") != metadata["thresholds"]:
        raise ValueError("Registry thresholds disagree")
    if evaluation.get("final_test") != metadata["final_test_metrics"]:
        raise ValueError("Registry final-test metrics disagree")

    development_indices = split_manifest.get("development_indices", [])
    final_test_indices = split_manifest.get("final_test_indices", [])
    if split_manifest.get("random_seed") != metadata["random_seed"]:
        raise ValueError("Split manifest random seed disagrees with metadata")
    if split_manifest.get("stratified") is not True:
        raise ValueError("Split manifest must record a stratified split")
    if len(set(development_indices)) != len(development_indices):
        raise ValueError("Development split contains duplicate indices")
    if len(set(final_test_indices)) != len(final_test_indices):
        raise ValueError("Final-test split contains duplicate indices")
    if set(development_indices) & set(final_test_indices):
        raise ValueError("Development and final-test indices overlap")
    if len(development_indices) != metadata["counts"]["development"]:
        raise ValueError("Development split count disagrees with metadata")
    if len(final_test_indices) != metadata["counts"]["final_test"]:
        raise ValueError("Final-test split count disagrees with metadata")
    fingerprints = metadata["split_manifest"]
    if split_index_hash(development_indices) != fingerprints[
        "development_index_sha256"
    ]:
        raise ValueError("Development split fingerprint disagrees")
    if split_index_hash(final_test_indices) != fingerprints["final_test_index_sha256"]:
        raise ValueError("Final-test split fingerprint disagrees")


def validate_artifact_consistency(bundle: Any, metadata: dict[str, Any]) -> None:
    """Verify the ignored binary and tracked metadata describe the same model."""
    if bundle.model_name != metadata["model_name"]:
        raise ValueError("Artifact and metadata model names disagree")
    if bundle.model_version != metadata["model_version"]:
        raise ValueError("Artifact and metadata model versions disagree")
    if list(bundle.feature_names) != metadata["features"]:
        raise ValueError("Artifact and metadata feature lists disagree")
    thresholds = metadata["thresholds"]
    if bundle.low_threshold != thresholds["low_threshold"]:
        raise ValueError("Artifact and metadata low thresholds disagree")
    if bundle.high_threshold != thresholds["high_threshold"]:
        raise ValueError("Artifact and metadata high thresholds disagree")
    if bundle.explanation_method != metadata["explanation_method"]:
        raise ValueError("Artifact explanation method disagrees")
    if set(bundle.explanation_reference) != set(metadata["features"]):
        raise ValueError("Artifact explanation reference schema disagrees")
    if tuple(bundle.pipeline.feature_names_in_) != tuple(metadata["features"]):
        raise ValueError("Pipeline feature schema disagrees")
    params = bundle.pipeline.get_params()
    for name, value in metadata["selected_hyperparameters"].items():
        if params.get(name) != value:
            raise ValueError("Artifact hyperparameters disagree")
    if list(bundle.pipeline.classes_) != [0, 1]:
        raise ValueError("Artifact binary target encoding disagrees")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
