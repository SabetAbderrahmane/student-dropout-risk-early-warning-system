"""Independently verified stage runtimes, selected through explicit model identity."""

from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from app.core.config import get_settings
from app.core.exceptions import ApplicationError
from app.ml.outcomes.contracts import MODEL_VERSIONS, PredictionStage
from app.ml.outcomes.deployment import verify


@dataclass(frozen=True)
class OutcomeRuntime:
    bundle: object
    metadata: dict
    evaluation: dict
    manifest: dict

    def predict(self, row):
        probabilities = self.bundle.predict_proba(row)[0]
        labels = self.bundle.class_labels
        values = {name: float(probabilities[i]) for i, name in enumerate(labels)}
        return labels[int(probabilities.argmax())], values


_lock = Lock()
_runtimes = {}


def get_outcome_runtime(stage: PredictionStage, *, version=None):
    if version is not None and version != MODEL_VERSIONS[stage]:
        raise ApplicationError(
            409,
            "INCOMPATIBLE_STAGE_MODEL",
            "The requested model is not registered for this stage.",
        )
    root = Path(get_settings().ml_outcome_root).resolve()
    key = (root, stage)
    with _lock:
        if key not in _runtimes:
            _runtimes[key] = OutcomeRuntime(*verify(stage, root=root))
        return _runtimes[key]


def reset_outcome_runtimes():
    with _lock:
        _runtimes.clear()
