"""Development-only probability threshold calibration and risk classification."""

from dataclasses import dataclass

import numpy as np
from sklearn.metrics import precision_recall_curve


@dataclass(frozen=True, slots=True)
class CalibratedThresholds:
    low_threshold: float
    high_threshold: float
    method: str
    low_target_recall: float
    high_target_recall: float


def calibrate_thresholds(
    y_true: np.ndarray,
    probabilities: np.ndarray,
    *,
    low_target_recall: float = 0.90,
    high_target_recall: float = 0.70,
) -> CalibratedThresholds:
    """Calibrate LOW exclusion and HIGH action thresholds from OOF predictions.

    LOW is bounded by the largest threshold retaining at least 90% dropout
    recall. HIGH is the precision-maximizing threshold that retains at least
    70% recall. Both targets and deterministic fallbacks are persisted.
    """
    probabilities = np.asarray(probabilities, dtype=float)
    y_true = np.asarray(y_true, dtype=int)
    if len(y_true) != len(probabilities) or len(y_true) == 0:
        raise ValueError("Targets and probabilities must be non-empty and aligned")
    if not np.isfinite(probabilities).all() or ((probabilities < 0) | (probabilities > 1)).any():
        raise ValueError("Probabilities must be finite values in [0, 1]")

    precision, recall, thresholds = precision_recall_curve(y_true, probabilities)
    threshold_precision = precision[:-1]
    threshold_recall = recall[:-1]
    low_candidates = np.flatnonzero(threshold_recall >= low_target_recall)
    high_candidates = np.flatnonzero(threshold_recall >= high_target_recall)
    if not len(low_candidates) or not len(high_candidates):
        raise ValueError("Unable to calibrate thresholds for requested recall targets")

    low_threshold = float(thresholds[low_candidates[-1]])
    high_precision = threshold_precision[high_candidates]
    best_precision = np.max(high_precision)
    tied = high_candidates[np.flatnonzero(high_precision == best_precision)]
    high_index = tied[np.argmax(thresholds[tied])]
    high_threshold = float(thresholds[high_index])

    if high_threshold <= low_threshold:
        eligible = thresholds[thresholds > low_threshold]
        high_threshold = float(np.quantile(probabilities, 0.75))
        if high_threshold <= low_threshold and len(eligible):
            high_threshold = float(eligible[0])
    if not 0 <= low_threshold < high_threshold <= 1:
        raise ValueError(
            f"Invalid calibrated thresholds: low={low_threshold}, high={high_threshold}"
        )
    return CalibratedThresholds(
        low_threshold=low_threshold,
        high_threshold=high_threshold,
        method=(
            "Development-set 5-fold out-of-fold predictions: low is the largest "
            "threshold retaining >=90% dropout recall; high maximizes precision "
            "while retaining >=70% dropout recall."
        ),
        low_target_recall=low_target_recall,
        high_target_recall=high_target_recall,
    )


def risk_level(probability: float, low_threshold: float, high_threshold: float) -> str:
    if not 0 <= probability <= 1:
        raise ValueError("Probability must be in [0, 1]")
    if not 0 <= low_threshold < high_threshold <= 1:
        raise ValueError("Thresholds must satisfy 0 <= low < high <= 1")
    if probability < low_threshold:
        return "LOW"
    if probability < high_threshold:
        return "MEDIUM"
    return "HIGH"
