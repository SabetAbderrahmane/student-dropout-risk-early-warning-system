"""Validated, process-wide loading of the frozen Phase 5A inference bundle."""

import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from app.core.config import get_settings
from app.core.exceptions import ApplicationError
from app.ml.training.artifact import ModelBundle
from app.ml.training.metadata import validate_artifact_consistency, validate_metadata


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


def _unavailable(message: str) -> ApplicationError:
    return ApplicationError(503, "MODEL_ARTIFACT_UNAVAILABLE", message)


def _mismatch(message: str) -> ApplicationError:
    return ApplicationError(503, "MODEL_REGISTRY_MISMATCH", message)


def _load_runtime() -> ModelRuntime:
    settings = get_settings()
    paths = [
        Path(settings.ml_model_path),
        Path(settings.ml_metadata_path),
        Path(settings.ml_evaluation_path),
    ]
    if any(not path.is_file() for path in paths):
        raise _unavailable("The configured prediction model is not available.")
    try:
        metadata = json.loads(paths[1].read_text(encoding="utf-8"))
        evaluation = json.loads(paths[2].read_text(encoding="utf-8"))
        validate_metadata(metadata)
        bundle = joblib.load(paths[0])
        if not isinstance(bundle, ModelBundle):
            raise TypeError("Unexpected model artifact type")
        validate_artifact_consistency(bundle, metadata)
        if evaluation.get("model_name") != metadata["model_name"]:
            raise ValueError("Evaluation model name differs from metadata")
        if evaluation.get("model_version") != metadata["model_version"]:
            raise ValueError("Evaluation model version differs from metadata")
        if evaluation.get("threshold_calibration") != metadata["thresholds"]:
            raise ValueError("Evaluation thresholds differ from metadata")
        if evaluation.get("final_test") != metadata["final_test_metrics"]:
            raise ValueError("Evaluation metrics differ from metadata")
        return ModelRuntime(bundle=bundle, metadata=metadata, evaluation=evaluation)
    except ApplicationError:
        raise
    except Exception as exc:
        raise _mismatch(
            "The prediction artifact does not match its registry record."
        ) from exc


def initialize_model_runtime() -> ModelRuntime | None:
    """Attempt startup loading without taking unrelated API routes down."""
    global _runtime, _load_error
    with _lock:
        if _runtime is not None:
            return _runtime
        if _load_error is not None:
            return None
        try:
            _runtime = _load_runtime()
        except ApplicationError as exc:
            _load_error = exc
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
