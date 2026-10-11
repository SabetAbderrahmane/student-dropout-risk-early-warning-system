"""Validated, process-wide loading of the frozen Phase 5A inference bundle."""

import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from app.core.config import get_settings
from app.core.exceptions import ApplicationError
from app.ml.deployment import load_verified_model
from app.ml.training.artifact import ModelBundle


@dataclass(frozen=True, slots=True)
class ModelRuntime:
    bundle: ModelBundle
    metadata: dict[str, Any]
    evaluation: dict[str, Any]

    @property
    def feature_names(self) -> tuple[str, ...]:
        return self.bundle.feature_names

    def predict_probability(self, row: pd.DataFrame) -> float:
        return float(self.bundle.predict_proba(row)[0])

    def classify(self, probability: float) -> str:
        return self.bundle.classify_risk(probability)

    def explain(self, row: pd.DataFrame, *, top_k: int = 5) -> list[dict[str, Any]]:
        return self.bundle.explain_local(row, top_k=top_k)


_lock = threading.Lock()
_runtime: ModelRuntime | None = None
_load_error: ApplicationError | None = None
logger = logging.getLogger(__name__)


def _load_runtime() -> ModelRuntime:
    settings = get_settings()
    bundle, metadata, evaluation = load_verified_model(
        Path(settings.ml_model_path),
        Path(settings.ml_metadata_path),
        Path(settings.ml_evaluation_path),
        Path(settings.ml_manifest_path),
    )
    return ModelRuntime(bundle=bundle, metadata=metadata, evaluation=evaluation)


def initialize_model_runtime() -> ModelRuntime | None:
    """Attempt startup loading without taking unrelated API routes down."""
    global _runtime, _load_error
    with _lock:
        if _runtime is not None:
            return _runtime
        if _load_error is not None:
            if (
                get_settings().ml_model_required
                or get_settings().app_env == "production"
            ):
                raise _load_error
            return None
        try:
            _runtime = _load_runtime()
        except ApplicationError as exc:
            _load_error = exc
            logger.error("Prediction model startup failed: %s", exc.code)
        if _load_error is not None and (
            get_settings().ml_model_required or get_settings().app_env == "production"
        ):
            raise _load_error
        return _runtime


def get_model_runtime() -> ModelRuntime:
    initialize_model_runtime()
    if _runtime is not None:
        return _runtime
    assert _load_error is not None
    raise _load_error


def reset_model_runtime() -> None:
    """Clear cached runtime state for tests and explicit configuration reloads."""
    global _runtime, _load_error
    with _lock:
        _runtime = None
        _load_error = None
