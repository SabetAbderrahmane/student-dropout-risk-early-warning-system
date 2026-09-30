"""Serializable inference bundle and explanation helpers for future Phase 5B use."""

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

from app.ml.feature_schema import FEATURES_BY_NAME, PREDICTION_FEATURES
from app.ml.training.data import CANONICAL_FEATURE_NAMES
from app.ml.training.thresholds import risk_level

EXPLANATION_METHOD = (
    "Model-agnostic single-feature reference perturbation: contribution is the "
    "change in dropout probability when one observed feature is replaced by its "
    "development-set median (numeric) or mode (categorical)."
)


def _python_value(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    return value


def make_explanation_reference(X: pd.DataFrame) -> dict[str, int | float]:
    reference: dict[str, int | float] = {}
    for feature in PREDICTION_FEATURES:
        series = X[feature.name].dropna()
        if series.empty:
            raise ValueError(f"Cannot build explanation reference for {feature.name}")
        value = series.median() if feature.kind.value == "NUMERIC" else series.mode().iloc[0]
        reference[feature.name] = _python_value(value)
    return reference


@dataclass(slots=True)
class ModelBundle:
    """One reloadable object containing preprocessing, estimator, and inference rules."""

    pipeline: Pipeline
    model_name: str
    model_version: str
    feature_names: tuple[str, ...]
    low_threshold: float
    high_threshold: float
    explanation_reference: dict[str, int | float]
    explanation_method: str = EXPLANATION_METHOD

    def _validate(self, X: pd.DataFrame) -> pd.DataFrame:
        if tuple(X.columns) != self.feature_names:
            raise ValueError(
                "Inference columns must exactly match the canonical feature order"
            )
        return X

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        probabilities = np.asarray(self.pipeline.predict_proba(self._validate(X))[:, 1])
        if not np.isfinite(probabilities).all() or (
            (probabilities < 0) | (probabilities > 1)
        ).any():
            raise ValueError("Model produced invalid probabilities")
        return probabilities

    def classify_risk(self, probability: float) -> str:
        return risk_level(probability, self.low_threshold, self.high_threshold)

    def explain_local(
        self, row: pd.DataFrame | pd.Series, *, top_k: int | None = None
    ) -> list[dict[str, Any]]:
        """Return compact local contributions with the Phase 5B-compatible schema."""
        if isinstance(row, pd.Series):
            row = row.to_frame().T
        if len(row) != 1:
            raise ValueError("Local explanations require exactly one row")
        row = self._validate(row.loc[:, list(self.feature_names)])
        observed_probability = float(self.predict_proba(row)[0])
        explanations: list[dict[str, Any]] = []
        for feature_name in self.feature_names:
            perturbed = row.copy()
            perturbed.loc[perturbed.index[0], feature_name] = self.explanation_reference[
                feature_name
            ]
            reference_probability = float(self.predict_proba(perturbed)[0])
            explanations.append(
                {
                    "feature": feature_name,
                    "label": FEATURES_BY_NAME[feature_name].official_name,
                    "value": _python_value(row.iloc[0][feature_name]),
                    "contribution": observed_probability - reference_probability,
                }
            )
        explanations.sort(key=lambda item: abs(item["contribution"]), reverse=True)
        return explanations if top_k is None else explanations[:top_k]


def build_bundle(
    pipeline: Pipeline,
    *,
    model_name: str,
    model_version: str,
    low_threshold: float,
    high_threshold: float,
    X_development: pd.DataFrame,
) -> ModelBundle:
    return ModelBundle(
        pipeline=pipeline,
        model_name=model_name,
        model_version=model_version,
        feature_names=CANONICAL_FEATURE_NAMES,
        low_threshold=low_threshold,
        high_threshold=high_threshold,
        explanation_reference=make_explanation_reference(X_development),
    )
