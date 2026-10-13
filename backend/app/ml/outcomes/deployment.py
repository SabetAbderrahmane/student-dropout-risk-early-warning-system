"""Trusted multi-model verification: checksum bytes before any deserialization."""

import argparse
import io
import json
import tempfile
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.exceptions import InconsistentVersionWarning

from app.core.exceptions import ApplicationError
from app.ml.deployment import runtime_versions, sha256
from app.ml.outcomes.bundle import EXPLANATION_METHOD, OutcomeBundle
from app.ml.outcomes.contracts import (
    CLASS_LABELS,
    MODEL_VERSIONS,
    OUTCOME_ENCODING,
    SCHEMA_VERSIONS,
    PredictionStage,
    feature_names,
)
from app.ml.outcomes.metrics import meets_constraints, selection_score
from app.ml.outcomes.modeling import FAMILIES, SELECTION_METHOD, select_winner
from app.ml.training.metadata import split_index_hash

ML_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_FILES = (
    "metadata.json",
    "evaluation.json",
    "split_manifest.json",
    "model_selection.json",
    "threshold_calibration.json",
    "data_audit.json",
)


def error(code, message):
    return ApplicationError(503, code, message)


def read_registry(stage: PredictionStage, *, root=ML_ROOT):
    directory = root / "model_registry" / MODEL_VERSIONS[stage]
    try:
        manifest = json.loads((directory / "artifact_manifest.json").read_bytes())
        documents = {
            name: json.loads((directory / name).read_bytes()) for name in REGISTRY_FILES
        }
    except (OSError, ValueError) as exc:
        raise error(
            "MODEL_ARTIFACT_UNAVAILABLE", "The stage model registry is unavailable."
        ) from exc
    try:
        if (
            manifest["format_version"] != 2
            or manifest["model_version"] != MODEL_VERSIONS[stage]
            or manifest["prediction_stage"] != stage
        ):
            raise ValueError("Manifest identity mismatch")
        checksum = manifest["artifact_sha256"]
        if (
            not isinstance(checksum, str)
            or len(checksum) != 64
            or any(c not in "0123456789abcdef" for c in checksum)
        ):
            raise ValueError("Invalid artifact checksum")
        for name, document in documents.items():
            payload = json.dumps(
                document, sort_keys=True, separators=(",", ":")
            ).encode()
            if sha256(payload) != manifest["registry_sha256"][name]:
                raise ValueError("Registry document checksum mismatch")
        metadata = documents["metadata.json"]
        evaluation = documents["evaluation.json"]
        split = documents["split_manifest.json"]
        selection = documents["model_selection.json"]
        thresholds = documents["threshold_calibration.json"]
        if (
            metadata["model_version"] != MODEL_VERSIONS[stage]
            or metadata["prediction_stage"] != stage
            or metadata["model_target_type"] != "MULTICLASS_OUTCOME"
            or metadata["feature_schema_version"] != SCHEMA_VERSIONS[stage]
            or tuple(metadata["features"]) != feature_names(stage)
            or metadata["target_mapping"] != dict(OUTCOME_ENCODING)
            or tuple(metadata["class_labels"]) != CLASS_LABELS
            or metadata["model_name"] not in FAMILIES
            or metadata["explanation_method"] != EXPLANATION_METHOD
        ):
            raise ValueError("Model contract mismatch")
        if metadata["runtime_versions"] != manifest["runtime_versions"]:
            raise ValueError("Runtime metadata mismatch")
        if (
            metadata["dataset"] != documents["data_audit.json"]
            or metadata["dataset"]["dataset_id"] != 697
        ):
            raise ValueError("Data provenance mismatch")
        if (
            metadata["random_seed"] != 42
            or split["random_seed"] != 42
            or split["stratified"] is not True
        ):
            raise ValueError("Split contract mismatch")
        seen = set()
        for partition in (
            "fitting",
            "probability_calibration",
            "threshold_calibration",
            "final_test",
        ):
            indices = split[partition]
            if (
                len(indices) != metadata["counts"][partition]
                or len(set(indices)) != len(indices)
                or seen.intersection(indices)
            ):
                raise ValueError("Split membership overlaps or count mismatch")
            if split_index_hash(indices) != metadata["split_sha256"][partition]:
                raise ValueError("Split fingerprint mismatch")
            if any(type(i) is not int or i < 0 for i in indices):
                raise ValueError("Invalid source row index")
            seen.update(indices)
        if seen != set(range(metadata["dataset"]["rows"])):
            raise ValueError("Split does not cover the source data")
        if (
            metadata["thresholds"] != thresholds
            or evaluation["threshold_calibration"] != thresholds
        ):
            raise ValueError("Risk calibration records disagree")
        if not 0 <= thresholds["low_threshold"] < thresholds["high_threshold"] <= 1:
            raise ValueError("Risk thresholds invalid")
        if (
            thresholds["model_version"] != metadata["model_version"]
            or thresholds["sample_size"] != metadata["counts"]["threshold_calibration"]
        ):
            raise ValueError("Calibration sample mismatch")
        if (
            thresholds["low_achieved_recall"] < 0.90
            or thresholds["high_achieved_recall"] < 0.70
        ):
            raise ValueError("Risk calibration targets not achieved")
        if (
            selection["method"] != SELECTION_METHOD
            or selection["winner"] != metadata["model_name"]
        ):
            raise ValueError("Model selection record mismatch")
        if metadata["selection"] != {
            k: v for k, v in selection.items() if k != "candidates"
        }:
            raise ValueError("Model selection metadata disagree")
        if evaluation["candidate_comparison"] != selection["candidates"] or {
            c["name"] for c in selection["candidates"]
        } != set(FAMILIES):
            raise ValueError("Candidate reports disagree")
        if selection["cv_folds"] != 5 or selection["constraints"] != {
            "minimum_dropout_recall": 0.55,
            "minimum_macro_f1": 0.45,
        }:
            raise ValueError("Selection protocol differs from the frozen contract")
        for candidate in selection["candidates"]:
            if not np.isclose(
                candidate["selection_score"],
                selection_score(candidate["cv_metrics"]),
                rtol=0,
                atol=1e-12,
            ) or candidate["meets_constraints"] != meets_constraints(
                candidate["cv_metrics"]
            ):
                raise ValueError("Candidate selection score or eligibility disagrees")
        winner = select_winner(selection["candidates"])
        if (
            winner["name"] != selection["winner"]
            or winner["selection_score"] != selection["score"]
            or winner["best_hyperparameters"] != metadata["selected_hyperparameters"]
            or winner["final_test"] != evaluation["final_test"]
            or winner["calibration_before"] != metadata["probability_calibration"]["before"]
            or winner["calibration_after"] != metadata["probability_calibration"]["after"]
        ):
            raise ValueError("Winner reports disagree with development selection")
        if (
            evaluation["model_version"] != metadata["model_version"]
            or evaluation["prediction_stage"] != stage
        ):
            raise ValueError("Evaluation identity mismatch")
        if evaluation["final_test"] != metadata["final_test_metrics"]:
            raise ValueError("Evaluation metrics disagree")
        final = metadata["final_test_metrics"]
        matrix = final["confusion_matrix"]
        if (
            final["evaluation_scope"] != "FINAL_TEST_SET"
            or final["sample_size"] != metadata["counts"]["final_test"]
        ):
            raise ValueError("Final-test sample mismatch")
        if (
            matrix["labels"] != list(CLASS_LABELS)
            or np.asarray(matrix["rows_actual_columns_predicted"]).shape != (3, 3)
            or sum(map(sum, matrix["rows_actual_columns_predicted"]))
            != final["sample_size"]
        ):
            raise ValueError("Confusion matrix inconsistent")
    except (KeyError, ValueError, TypeError) as exc:
        raise error(
            "MODEL_REGISTRY_MISMATCH", "The stage model registry is inconsistent."
        ) from exc
    return metadata, evaluation, manifest


def verify(stage: PredictionStage, *, root=ML_ROOT, model=None):
    metadata, evaluation, manifest = read_registry(stage, root=root)
    path = model or root / "artifacts" / MODEL_VERSIONS[stage] / "model.joblib"
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise error(
            "MODEL_ARTIFACT_UNAVAILABLE", "The stage model artifact is unavailable."
        ) from exc
    if sha256(payload) != manifest["artifact_sha256"]:
        raise error(
            "MODEL_CHECKSUM_MISMATCH",
            "The stage artifact differs from its trusted SHA-256 manifest.",
        )
    if runtime_versions() != manifest["runtime_versions"]:
        raise error(
            "MODEL_RUNTIME_INCOMPATIBLE",
            "The stage model requires its recorded runtime dependency versions.",
        )
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", InconsistentVersionWarning)
            bundle = joblib.load(io.BytesIO(payload))
    except Exception as exc:
        raise error(
            "MODEL_ARTIFACT_CORRUPTED", "The verified stage artifact cannot be loaded."
        ) from exc
    try:
        if not isinstance(bundle, OutcomeBundle):
            raise TypeError("Unexpected bundle type")
        for attribute, key in (
            ("model_name", "model_name"),
            ("model_version", "model_version"),
            ("prediction_stage", "prediction_stage"),
            ("feature_schema_version", "feature_schema_version"),
            ("explanation_method", "explanation_method"),
            ("explanation_reference", "explanation_reference"),
        ):
            if getattr(bundle, attribute) != metadata[key]:
                raise ValueError("Bundle metadata disagree")
        if (
            tuple(bundle.feature_names) != tuple(metadata["features"])
            or bundle.class_labels != CLASS_LABELS
        ):
            raise ValueError("Bundle feature/class contracts disagree")
        if (
            bundle.low_threshold != metadata["thresholds"]["low_threshold"]
            or bundle.high_threshold != metadata["thresholds"]["high_threshold"]
        ):
            raise ValueError("Bundle risk thresholds disagree")
        base = bundle.estimator.estimator.estimator
        if (
            tuple(base.classes_) != (0, 1, 2)
            or tuple(base.feature_names_in_) != bundle.feature_names
        ):
            raise ValueError("Trained pipeline contracts disagree")
        params = base.get_params()
        if any(
            params[key] != value
            for key, value in metadata["selected_hyperparameters"].items()
        ):
            raise ValueError("Trained hyperparameters disagree")
        reference = pd.DataFrame(
            [bundle.explanation_reference], columns=bundle.feature_names
        )
        bundle.predict_proba(reference)
        bundle.explain_local(reference, top_k=1)
    except Exception as exc:
        raise error(
            "MODEL_REGISTRY_MISMATCH",
            "The stage bundle differs from its trusted registry.",
        ) from exc
    return bundle, metadata, evaluation, manifest


def install(stage, source, *, root=ML_ROOT):
    destination = root / "artifacts" / MODEL_VERSIONS[stage] / "model.joblib"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
        staged = Path(temporary) / "model.joblib"
        staged.write_bytes(source.read_bytes())
        verify(stage, root=root, model=staged)
        staged.replace(destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("verify", "install"))
    parser.add_argument("--stage", type=PredictionStage, choices=list(PredictionStage))
    parser.add_argument("--root", type=Path, default=ML_ROOT)
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()
    if args.action == "install" and (args.stage is None or args.source is None):
        parser.error("install requires --stage and --source")
    try:
        for stage in [args.stage] if args.stage else list(PredictionStage):
            if args.action == "install":
                install(stage, args.source, root=args.root)
            bundle, _, _, manifest = verify(stage, root=args.root)
            print(
                f"Verified {stage}: {bundle.model_version} SHA-256 {manifest['artifact_sha256']}"
            )
    except ApplicationError as exc:
        parser.exit(1, f"{exc.code}: {exc.message}\n")


if __name__ == "__main__":
    main()
