"""Multiclass evaluation with explicit dropout and calibration diagnostics."""

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    log_loss,
    precision_recall_fscore_support,
    precision_score,
    recall_score,
    roc_auc_score,
)

from app.ml.outcomes.contracts import CLASS_LABELS


def validate_probabilities(probabilities, *, rows=None):
    values = np.asarray(probabilities, dtype=float)
    if (
        values.ndim != 2
        or values.shape[1] != 3
        or (rows is not None and len(values) != rows)
    ):
        raise ValueError("Expected one three-class probability row per input")
    if not np.isfinite(values).all() or ((values < 0) | (values > 1)).any():
        raise ValueError("Class probabilities must be finite and within [0, 1]")
    # XGBoost emits float32 softmax values; retain them without rounding/renormalizing.
    if not np.allclose(values.sum(axis=1), 1, rtol=0, atol=1e-6):
        raise ValueError("Class probabilities must sum to one")
    return values


def evaluate(y, probabilities, *, scope="DEVELOPMENT"):
    y = np.asarray(y, dtype=int)
    probabilities = validate_probabilities(probabilities, rows=len(y))
    predicted = probabilities.argmax(axis=1)
    precision, recall, f1, support = precision_recall_fscore_support(
        y, predicted, labels=[0, 1, 2], zero_division=0
    )
    dropout = (y == 0).astype(int)
    bins = []
    ece = 0.0
    for index in range(10):
        lower, upper = index / 10, (index + 1) / 10
        selected = (probabilities[:, 0] >= lower) & (
            (probabilities[:, 0] < upper)
            if index < 9
            else (probabilities[:, 0] <= upper)
        )
        count = int(selected.sum())
        mean = float(probabilities[selected, 0].mean()) if count else None
        observed = float(dropout[selected].mean()) if count else None
        if count:
            ece += count / len(y) * abs(mean - observed)
        bins.append(
            {
                "lower": lower,
                "upper": upper,
                "count": count,
                "mean_probability": mean,
                "observed_dropout_rate": observed,
            }
        )
    auc = (
        float(
            roc_auc_score(
                y, probabilities, multi_class="ovr", average="macro", labels=[0, 1, 2]
            )
        )
        if len(np.unique(y)) == 3
        else None
    )
    return {
        "evaluation_scope": scope,
        "sample_size": len(y),
        "accuracy": float(accuracy_score(y, predicted)),
        "macro_precision": float(
            precision_score(y, predicted, average="macro", zero_division=0)
        ),
        "macro_recall": float(
            recall_score(y, predicted, average="macro", zero_division=0)
        ),
        "macro_f1": float(f1_score(y, predicted, average="macro", zero_division=0)),
        "weighted_f1": float(
            f1_score(y, predicted, average="weighted", zero_division=0)
        ),
        "per_class": {
            name: {
                "precision": float(precision[i]),
                "recall": float(recall[i]),
                "f1": float(f1[i]),
                "support": int(support[i]),
            }
            for i, name in enumerate(CLASS_LABELS)
        },
        "confusion_matrix": {
            "labels": list(CLASS_LABELS),
            "rows_actual_columns_predicted": confusion_matrix(
                y, predicted, labels=[0, 1, 2]
            ).tolist(),
        },
        "multiclass_roc_auc_ovr": auc,
        "log_loss": float(log_loss(y, probabilities, labels=[0, 1, 2])),
        "dropout_pr_auc": float(average_precision_score(dropout, probabilities[:, 0])),
        "dropout_recall": float(recall[0]),
        "dropout_precision": float(precision[0]),
        "calibration": {
            "multiclass_brier_score": float(
                np.mean(np.sum((probabilities - np.eye(3)[y]) ** 2, axis=1))
            ),
            "dropout_brier_score": float(
                brier_score_loss(dropout, probabilities[:, 0])
            ),
            "dropout_ece_10_bins": float(ece),
            "dropout_reliability_bins": bins,
        },
    }


def selection_score(metrics):
    return (
        0.40 * metrics["dropout_recall"]
        + 0.30 * metrics["dropout_pr_auc"]
        + 0.20 * metrics["macro_f1"]
        + 0.10 * metrics["dropout_precision"]
    )


def meets_constraints(metrics):
    return metrics["dropout_recall"] >= 0.55 and metrics["macro_f1"] >= 0.45
