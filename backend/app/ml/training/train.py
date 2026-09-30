"""Run the complete Phase 5A offline training pipeline.

From ``backend``:

    python -m app.ml.training.train
"""

import argparse
import importlib.metadata
import json
import platform
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
from sklearn.base import clone

from app.ml.feature_schema import BINARY_TARGET_ENCODING
from app.ml.training.artifact import EXPLANATION_METHOD, build_bundle
from app.ml.training.data import (
    CANONICAL_FEATURE_NAMES,
    RANDOM_SEED,
    class_counts,
    load_uci_dataset,
    make_final_split,
)
from app.ml.training.evaluation import evaluate_final_test, global_feature_importance
from app.ml.training.metadata import (
    FEATURE_SCHEMA_VERSION,
    split_index_hash,
    validate_artifact_consistency,
    validate_metadata,
    validate_registry_consistency,
    write_json,
)
from app.ml.training.modeling import CandidateResult, select_winner, train_candidates
from app.ml.training.report import render_report
from app.ml.training.thresholds import calibrate_thresholds

ML_DIRECTORY = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACT_DIRECTORY = ML_DIRECTORY / "artifacts" / "dropout-risk-v1"
DEFAULT_REGISTRY_DIRECTORY = ML_DIRECTORY / "model_registry" / "dropout-risk-v1"


def _serialize_candidate(candidate: CandidateResult) -> dict[str, Any]:
    return {
        "name": candidate.name,
        "search_space": candidate.search_space,
        "best_hyperparameters": candidate.best_params,
        "cv_metrics": candidate.cv_metrics,
        "cv_metric_std": candidate.cv_metric_std,
        "confusion_matrix_at_0_5": candidate.confusion_matrix,
        "selection_score": candidate.selection_score,
    }


def _library_versions() -> dict[str, str]:
    packages = ("joblib", "numpy", "pandas", "scikit-learn", "ucimlrepo", "xgboost")
    return {
        "python": platform.python_version(),
        **{package: importlib.metadata.version(package) for package in packages},
    }


def run_training(
    artifact_directory: Path = DEFAULT_ARTIFACT_DIRECTORY,
    registry_directory: Path = DEFAULT_REGISTRY_DIRECTORY,
) -> dict[str, Any]:
    artifact_directory.mkdir(parents=True, exist_ok=True)
    registry_directory.mkdir(parents=True, exist_ok=True)

    X, y, dataset_source = load_uci_dataset()
    split = make_final_split(X, y)

    # Only development data is visible during search, selection, and calibration.
    candidates = train_candidates(split.X_development, split.y_development)
    winner = select_winner(candidates)
    thresholds = calibrate_thresholds(
        split.y_development.to_numpy(), winner.oof_probabilities
    )

    # Model family, hyperparameters, preprocessing, and thresholds are now frozen.
    final_pipeline = clone(winner.best_estimator)
    final_pipeline.fit(split.X_development, split.y_development)
    importance = global_feature_importance(
        final_pipeline,
        split.X_development,
        split.y_development,
        random_seed=RANDOM_SEED,
    )

    # This is the only final-test evaluation call in the training pipeline.
    final_test_metrics = evaluate_final_test(
        final_pipeline, split.X_final_test, split.y_final_test
    )

    slug = winner.name.lower().replace(" ", "-")
    model_version = f"dropout-{slug}-v1"
    bundle = build_bundle(
        final_pipeline,
        model_name=winner.name,
        model_version=model_version,
        low_threshold=thresholds.low_threshold,
        high_threshold=thresholds.high_threshold,
        X_development=split.X_development,
    )
    artifact_path = artifact_directory / "model.joblib"
    joblib.dump(bundle, artifact_path)

    # Reload verification uses development rows, never another final-test scoring pass.
    reloaded = joblib.load(artifact_path)
    reload_probabilities = reloaded.predict_proba(split.X_development.iloc[:10])
    if not ((reload_probabilities >= 0) & (reload_probabilities <= 1)).all():
        raise ValueError("Reloaded artifact produced an out-of-range probability")

    relative_artifact_path = artifact_path.relative_to(Path(__file__).resolve().parents[3])
    metadata = {
        "model_name": winner.name,
        "model_version": model_version,
        "trained_at": datetime.now(UTC).isoformat(),
        "dataset": dataset_source,
        "target_mapping": dict(BINARY_TARGET_ENCODING),
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "features": list(CANONICAL_FEATURE_NAMES),
        "random_seed": RANDOM_SEED,
        "counts": {
            "total": int(len(X)),
            "training": int(len(split.X_development)),
            "development": int(len(split.X_development)),
            "final_test": int(len(split.X_final_test)),
        },
        "class_distribution": {
            "total": class_counts(y),
            "development": class_counts(split.y_development),
            "final_test": class_counts(split.y_final_test),
        },
        "split_manifest": {
            "path": "split_manifest.json",
            "development_index_sha256": split_index_hash(split.development_indices),
            "final_test_index_sha256": split_index_hash(split.final_test_indices),
            "stratified_final_test_fraction": 0.20,
        },
        "preprocessing": (
            "ColumnTransformer inside every CV/model pipeline: numeric features use "
            "median imputation plus StandardScaler; categorical and binary codes use "
            "most-frequent imputation plus one-hot encoding with unknown-category "
            "handling. Input is checked against the canonical ordered 30 features."
        ),
        "selected_hyperparameters": winner.best_params,
        "selection": {
            "method": "0.50 recall + 0.30 PR-AUC + 0.20 precision",
            "score": winner.selection_score,
            "cv_folds": 5,
            "refit_metric": "PR-AUC",
            "reason": (
                "Highest recall-weighted selection score across the three locked "
                "candidate families, with PR-AUC and precision as guardrails."
            ),
        },
        "thresholds": {
            "low_threshold": thresholds.low_threshold,
            "high_threshold": thresholds.high_threshold,
            "method": thresholds.method,
            "low_target_recall": thresholds.low_target_recall,
            "high_target_recall": thresholds.high_target_recall,
            "calibration_source": "development 5-fold out-of-fold probabilities",
        },
        "final_test_metrics": final_test_metrics,
        "explanation_method": EXPLANATION_METHOD,
        "artifact_path": str(relative_artifact_path).replace("\\", "/"),
        "library_versions": _library_versions(),
    }
    validate_metadata(metadata)

    evaluation = {
        "model_name": winner.name,
        "model_version": model_version,
        "development_model_selection": [
            _serialize_candidate(candidate) for candidate in candidates
        ],
        "selection": metadata["selection"],
        "threshold_calibration": metadata["thresholds"],
        "final_test": final_test_metrics,
        "global_feature_importance": importance,
        "global_feature_importance_source": (
            "Permutation importance scored by PR-AUC on development data only; "
            "negative sampling noise is clipped to zero and values are normalized."
        ),
    }
    split_manifest = {
        "random_seed": RANDOM_SEED,
        "stratified": True,
        "development_indices": list(split.development_indices),
        "final_test_indices": list(split.final_test_indices),
    }

    metadata_path = registry_directory / "metadata.json"
    evaluation_path = registry_directory / "evaluation.json"
    manifest_path = registry_directory / "split_manifest.json"
    report_path = registry_directory / "training_report.md"
    write_json(metadata_path, metadata)
    write_json(evaluation_path, evaluation)
    write_json(manifest_path, split_manifest)
    report_path.write_text(render_report(metadata, evaluation), encoding="utf-8")

    persisted_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    persisted_evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
    persisted_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    validate_registry_consistency(
        persisted_metadata, persisted_evaluation, persisted_manifest
    )
    validate_artifact_consistency(reloaded, persisted_metadata)

    return {
        "metadata": metadata,
        "evaluation": evaluation,
        "paths": {
            "artifact": str(artifact_path),
            "metadata": str(metadata_path),
            "evaluation": str(evaluation_path),
            "split_manifest": str(manifest_path),
            "report": str(report_path),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=DEFAULT_ARTIFACT_DIRECTORY,
        help="Ignored binary artifact directory (default: %(default)s)",
    )
    parser.add_argument(
        "--registry-dir",
        type=Path,
        default=DEFAULT_REGISTRY_DIRECTORY,
        help="Tracked auditable registry directory (default: %(default)s)",
    )
    args = parser.parse_args()
    result = run_training(args.artifact_dir.resolve(), args.registry_dir.resolve())
    summary = {
        "model_name": result["metadata"]["model_name"],
        "model_version": result["metadata"]["model_version"],
        "thresholds": result["metadata"]["thresholds"],
        "final_test_metrics": result["metadata"]["final_test_metrics"],
        "paths": result["paths"],
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
