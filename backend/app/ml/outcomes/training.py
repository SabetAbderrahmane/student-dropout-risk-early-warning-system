"""Explicit offline B1 training; never runs during application startup or HTTP."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
from sklearn.metrics import precision_recall_curve

from app.ml.deployment import registry_sha256, runtime_versions, sha256
from app.ml.outcomes.bundle import (
    EXPLANATION_METHOD,
    OutcomeBundle,
    explanation_reference,
)
from app.ml.outcomes.contracts import (
    CLASS_LABELS,
    MODEL_VERSIONS,
    OUTCOME_ENCODING,
    SCHEMA_VERSIONS,
    PredictionStage,
    feature_names,
)
from app.ml.outcomes.data import load_dataset, make_split, select_features
from app.ml.outcomes.metrics import evaluate
from app.ml.outcomes.modeling import SELECTION_METHOD, select_winner, train_candidates
from app.ml.training.metadata import split_index_hash, write_json

ML_ROOT = Path(__file__).resolve().parents[1]


def calibrate_thresholds(y, probabilities):
    probabilities = np.asarray(probabilities, dtype=float)
    binary = (np.asarray(y) == 0).astype(int)
    if not len(binary) or len(binary) != len(probabilities) or set(binary) != {0, 1}:
        raise ValueError(
            "Threshold calibration needs aligned dropout and non-dropout samples"
        )
    if (
        not np.isfinite(probabilities).all()
        or ((probabilities < 0) | (probabilities > 1)).any()
    ):
        raise ValueError("Threshold calibration probabilities are invalid")
    precision, recall, thresholds = precision_recall_curve(binary, probabilities)
    low_indices = np.flatnonzero(recall[:-1] >= 0.90)
    if not len(low_indices):
        raise ValueError("The LOW recall target cannot be achieved")
    low_index = int(low_indices[-1])
    high_indices = np.flatnonzero(
        (recall[:-1] >= 0.70) & (thresholds > thresholds[low_index])
    )
    if not len(high_indices):
        raise ValueError("Ordered risk thresholds cannot meet the recall targets")
    high_index = int(max(high_indices, key=lambda i: (precision[i], thresholds[i])))
    return {
        "low_threshold": float(thresholds[low_index]),
        "high_threshold": float(thresholds[high_index]),
        "low_target_recall": 0.90,
        "high_target_recall": 0.70,
        "low_achieved_recall": float(recall[low_index]),
        "low_achieved_precision": float(precision[low_index]),
        "high_achieved_recall": float(recall[high_index]),
        "high_achieved_precision": float(precision[high_index]),
        "sample_size": len(binary),
        "dropout_count": int(binary.sum()),
        "calibration_source": "Disjoint development risk-threshold partition; not final test",
        "method": "LOW largest threshold retaining >=90% dropout recall; HIGH maximum precision retaining >=70% recall and greater than LOW; no fallback",
    }


def run_training(*, csv_path=None, root=ML_ROOT, iterations=6, jobs=2):
    # Refuse partial or complete version reuse, including overwrite of a trusted manifest.
    for version in MODEL_VERSIONS.values():
        if (root / "model_registry" / version).exists() or (
            root / "artifacts" / version
        ).exists():
            raise ValueError(
                f"Version {version} already exists; use a new immutable version"
            )
    X, y, audit = load_dataset(csv_path)
    split = make_split(X, y)
    manifest = split.manifest()
    split_hashes = {
        key: split_index_hash(value)
        for key, value in manifest.items()
        if isinstance(value, list)
    }
    outputs = []
    # Freeze all choices for both stages before any final-test evaluation is visible.
    for stage in PredictionStage:
        frame = select_features(X, stage)
        subset = lambda indices: frame.loc[list(indices)]
        labels = lambda indices: y.loc[list(indices)]
        candidates = train_candidates(
            subset(split.fitting),
            labels(split.fitting),
            stage,
            iterations=iterations,
            jobs=jobs,
        )
        winner = select_winner(candidates)
        print(
            f"{stage}: frozen winner {winner['name']}; calibrating on separate development rows",
            flush=True,
        )
        for candidate in candidates:
            base = candidate["estimator"]
            calibrated = CalibratedClassifierCV(FrozenEstimator(base), method="sigmoid")
            calibrated.fit(
                subset(split.probability_calibration),
                labels(split.probability_calibration),
            )
            candidate["calibrated_estimator"] = calibrated
            candidate["calibration_before"] = evaluate(
                labels(split.threshold_calibration),
                base.predict_proba(subset(split.threshold_calibration)),
                scope="DEVELOPMENT_THRESHOLD_HOLDOUT",
            )
            candidate["calibration_after"] = evaluate(
                labels(split.threshold_calibration),
                calibrated.predict_proba(subset(split.threshold_calibration)),
                scope="DEVELOPMENT_THRESHOLD_HOLDOUT",
            )
        calibrated = winner["calibrated_estimator"]
        thresholds = calibrate_thresholds(
            labels(split.threshold_calibration),
            calibrated.predict_proba(subset(split.threshold_calibration))[:, 0],
        )
        version = MODEL_VERSIONS[stage]
        thresholds["model_version"] = version
        bundle = OutcomeBundle(
            estimator=calibrated,
            model_name=winner["name"],
            model_version=version,
            prediction_stage=stage,
            feature_schema_version=SCHEMA_VERSIONS[stage],
            feature_names=feature_names(stage),
            low_threshold=thresholds["low_threshold"],
            high_threshold=thresholds["high_threshold"],
            explanation_reference=explanation_reference(subset(split.fitting), stage),
        )
        outputs.append((stage, frame, candidates, winner, thresholds, bundle))
    result = []
    for stage, frame, candidates, winner, thresholds, bundle in outputs:
        # Exactly one final-test evaluation of each frozen candidate. No decisions below use these scores.
        for candidate in candidates:
            candidate["final_test"] = evaluate(
                y.loc[list(split.final_test)],
                candidate["calibrated_estimator"].predict_proba(
                    frame.loc[list(split.final_test)]
                ),
                scope="FINAL_TEST_SET",
            )
        version = MODEL_VERSIONS[stage]
        registry = root / "model_registry" / version
        artifact = root / "artifacts" / version / "model.joblib"
        registry.mkdir(parents=True)
        artifact.parent.mkdir(parents=True)
        joblib.dump(bundle, artifact, compress=3)
        serialized = [
            {key: value for key, value in candidate.items() if "estimator" not in key}
            for candidate in candidates
        ]
        selection = {
            "method": SELECTION_METHOD,
            "cv_folds": 5,
            "search_iterations_per_family": iterations,
            "constraints": {"minimum_dropout_recall": 0.55, "minimum_macro_f1": 0.45},
            "winner": winner["name"],
            "score": winner["selection_score"],
            "selected_hyperparameters": winner["best_hyperparameters"],
            "reason": "Maximum eligible dropout-oriented development CV score; final test unavailable during selection",
            "candidates": serialized,
        }
        metadata = {
            "model_name": winner["name"],
            "model_version": version,
            "prediction_stage": stage.value,
            "model_target_type": "MULTICLASS_OUTCOME",
            "trained_at": datetime.now(UTC).isoformat(),
            "feature_schema_version": SCHEMA_VERSIONS[stage],
            "features": list(feature_names(stage)),
            "class_labels": list(CLASS_LABELS),
            "target_mapping": dict(OUTCOME_ENCODING),
            "dataset": audit,
            "random_seed": 42,
            "counts": {
                key: len(value)
                for key, value in manifest.items()
                if isinstance(value, list)
            },
            "split_sha256": split_hashes,
            "selected_hyperparameters": winner["best_hyperparameters"],
            "selection": {
                key: value for key, value in selection.items() if key != "candidates"
            },
            "probability_calibration": {
                "method": "sigmoid, frozen base estimator, separate development probability-calibration partition",
                "sample_size": len(split.probability_calibration),
                "before": winner["calibration_before"],
                "after": winner["calibration_after"],
            },
            "thresholds": thresholds,
            "final_test_metrics": winner["final_test"],
            "preprocessing": "Fold-local median imputation/scaling and mode imputation/one-hot encoding, unknown categories ignored",
            "explanation_method": EXPLANATION_METHOD,
            "explanation_reference": bundle.explanation_reference,
            "artifact_path": f"app/ml/artifacts/{version}/model.joblib",
            "runtime_versions": runtime_versions(),
        }
        evaluation = {
            "model_version": version,
            "prediction_stage": stage.value,
            "final_test": winner["final_test"],
            "candidate_comparison": serialized,
            "threshold_calibration": thresholds,
        }
        for name, document in (
            ("metadata.json", metadata),
            ("evaluation.json", evaluation),
            ("split_manifest.json", manifest),
            ("model_selection.json", selection),
            ("threshold_calibration.json", thresholds),
            ("data_audit.json", audit),
        ):
            write_json(registry / name, document)
        write_json(
            registry / "artifact_manifest.json",
            {
                "format_version": 2,
                "model_version": version,
                "prediction_stage": stage.value,
                "artifact_sha256": sha256(artifact.read_bytes()),
                "registry_sha256": {
                    name: registry_sha256((registry / name).read_bytes())
                    for name in (
                        "metadata.json",
                        "evaluation.json",
                        "split_manifest.json",
                        "model_selection.json",
                        "threshold_calibration.json",
                        "data_audit.json",
                    )
                },
                "runtime_versions": runtime_versions(),
            },
        )
        from app.ml.outcomes.deployment import verify

        verify(stage, root=root)
        result.append(
            {
                "stage": stage.value,
                "version": version,
                "winner": winner["name"],
                "thresholds": thresholds,
                "final_test": winner["final_test"],
                "artifact_sha256": sha256(artifact.read_bytes()),
            }
        )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path)
    parser.add_argument("--root", type=Path, default=ML_ROOT)
    parser.add_argument("--iterations", type=int, default=6)
    parser.add_argument("--jobs", type=int, default=2)
    args = parser.parse_args()
    print(
        json.dumps(
            run_training(
                csv_path=args.csv,
                root=args.root,
                iterations=args.iterations,
                jobs=args.jobs,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
