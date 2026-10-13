"""Serializable calibrated multiclass inference and auditable reference perturbation."""

from dataclasses import dataclass
from typing import Any

import numpy as np

from app.ml.feature_schema import FEATURES_BY_NAME
from app.ml.outcomes.contracts import CLASS_LABELS, PredictionStage, feature_names
from app.ml.outcomes.metrics import validate_probabilities
from app.ml.training.thresholds import risk_level

EXPLANATION_METHOD = (
    "Model-agnostic single-feature reference perturbation of calibrated P(Dropout): "
    "observed probability minus probability after replacing one feature with its "
    "fitting-partition median (numeric) or mode (categorical). Non-causal; not SHAP."
)


@dataclass(slots=True)
class OutcomeBundle:
    estimator: Any
    model_name: str
    model_version: str
    prediction_stage: PredictionStage
    feature_schema_version: str
    feature_names: tuple[str, ...]
    low_threshold: float
    high_threshold: float
    explanation_reference: dict[str, int | float]
    class_labels: tuple[str, ...] = CLASS_LABELS
    explanation_method: str = EXPLANATION_METHOD

    def predict_proba(self, frame):
        if tuple(
            frame.columns
        ) != self.feature_names or self.feature_names != feature_names(
            self.prediction_stage
        ):
            raise ValueError(
                "Inference features do not match the ordered stage contract"
            )
        if not np.isfinite(frame.to_numpy(dtype=float)).all():
            raise ValueError("Inference inputs must be finite and complete")
        if (
            tuple(self.estimator.classes_) != (0, 1, 2)
            or self.class_labels != CLASS_LABELS
        ):
            raise ValueError(
                "Estimator class order differs from the public class contract"
            )
        return validate_probabilities(
            self.estimator.predict_proba(frame), rows=len(frame)
        )

    def classify_risk(self, probability):
        return risk_level(probability, self.low_threshold, self.high_threshold)

    def explain_local(self, row, *, top_k=5):
        if len(row) != 1:
            raise ValueError("Local explanations require exactly one row")
        observed = float(self.predict_proba(row)[0, 0])
        factors = []
        for name in self.feature_names:
            reference = row.astype(float).copy()
            reference.loc[reference.index[0], name] = self.explanation_reference[name]
            value = row.iloc[0][name]
            factors.append(
                {
                    "feature": name,
                    "label": FEATURES_BY_NAME[name].official_name,
                    "value": value.item() if isinstance(value, np.generic) else value,
                    "reference_value": self.explanation_reference[name],
                    "contribution": observed
                    - float(self.predict_proba(reference)[0, 0]),
                }
            )
        factors.sort(key=lambda item: abs(item["contribution"]), reverse=True)
        return factors if top_k is None else factors[:top_k]


def explanation_reference(frame, stage):
    return {
        name: float(
            frame[name].median()
            if FEATURES_BY_NAME[name].kind.value == "NUMERIC"
            else frame[name].mode().iloc[0]
        )
        for name in feature_names(stage)
    }
