"""Final-test evaluation and development-only global explanations."""

from typing import Any

import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline

from app.ml.feature_schema import FEATURES_BY_NAME
from app.ml.training.data import CANONICAL_FEATURE_NAMES, class_counts


def evaluate_final_test(
    pipeline: Pipeline, X: pd.DataFrame, y: pd.Series
) -> dict[str, Any]:
    """Perform the one final-test scoring pass after all choices are frozen."""
    probabilities = np.asarray(pipeline.predict_proba(X)[:, 1])
    predictions = (probabilities >= 0.5).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, predictions, labels=[0, 1]).ravel()
    return {
        "evaluation_scope": "FINAL_TEST_SET",
        "binary_decision_threshold": 0.5,
        "sample_size": int(len(y)),
        "class_distribution": class_counts(y),
        "accuracy": float(accuracy_score(y, predictions)),
        "precision": float(precision_score(y, predictions, zero_division=0)),
        "recall": float(recall_score(y, predictions, zero_division=0)),
        "f1": float(f1_score(y, predictions, zero_division=0)),
        "roc_auc": float(roc_auc_score(y, probabilities)),
        "pr_auc": float(average_precision_score(y, probabilities)),
        "brier_score": float(brier_score_loss(y, probabilities)),
        "confusion_matrix": {
            "tp": int(tp),
            "fp": int(fp),
            "tn": int(tn),
            "fn": int(fn),
        },
        "probability_min": float(probabilities.min()),
        "probability_max": float(probabilities.max()),
    }


def global_feature_importance(
    pipeline: Pipeline,
    X_development: pd.DataFrame,
    y_development: pd.Series,
    *,
    random_seed: int,
) -> list[dict[str, Any]]:
    """Compute model-agnostic permutation importance without using final-test data."""
    result = permutation_importance(
        pipeline,
        X_development,
        y_development,
        scoring="average_precision",
        n_repeats=8,
        random_state=random_seed,
        n_jobs=-1,
    )
    importances = np.maximum(result.importances_mean, 0)
    total = float(importances.sum())
    normalized = importances / total if total else importances
    rows = [
        {
            "feature": feature,
            "label": FEATURES_BY_NAME[feature].official_name,
            "importance": float(importance),
        }
        for feature, importance in zip(CANONICAL_FEATURE_NAMES, normalized, strict=True)
    ]
    return sorted(rows, key=lambda row: row["importance"], reverse=True)
