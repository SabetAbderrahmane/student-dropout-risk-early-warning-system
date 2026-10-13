"""UCI multiclass encoding and shared independent development partitions."""

import hashlib
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split
from ucimlrepo import fetch_ucirepo

from app.ml.outcomes.contracts import OUTCOME_ENCODING, feature_names
from app.ml.training.data import map_uci_features, validate_uci_schema


def encode_target(target):
    if target.isna().any() or not set(target.unique()) <= set(OUTCOME_ENCODING):
        raise ValueError("Unexpected or missing three-class target")
    return target.map(OUTCOME_ENCODING).astype("int8").rename("outcome")


def load_dataset(csv_path: Path | None = None):
    if csv_path is None:
        dataset = fetch_ucirepo(id=697)
        frame = pd.concat([dataset.data.features, dataset.data.targets], axis=1)
    else:
        frame = pd.read_csv(csv_path, float_precision="round_trip")
    features = frame.drop(columns=["Target"])
    targets = frame[["Target"]]
    validate_uci_schema(features, targets)
    if frame.duplicated().any():
        raise ValueError(
            "Exact duplicate source rows require investigation before splitting"
        )
    payload = frame.to_csv(index=False, lineterminator="\n").encode()
    audit = {
        "dataset_id": 697,
        "name": "Predict Students' Dropout and Academic Success",
        "homepage": "https://archive.ics.uci.edu/dataset/697/",
        "license": "CC BY 4.0",
        "canonical_csv_sha256": hashlib.sha256(payload).hexdigest(),
        "rows": len(frame),
        "missing_values": int(frame.isna().sum().sum()),
        "exact_duplicate_rows": int(frame.duplicated().sum()),
        "class_counts": {
            str(k): int(v) for k, v in frame.Target.value_counts().items()
        },
        "excluded_macroeconomic_reason": "Observation/release vintage is unavailable at either stage cutoff",
        "independence_limitation": "Student rows have no identity/group/time fields for temporal or institutional validation",
    }
    return map_uci_features(features), encode_target(frame.Target), audit


@dataclass(frozen=True)
class OutcomeSplit:
    fitting: tuple[int, ...]
    probability_calibration: tuple[int, ...]
    threshold_calibration: tuple[int, ...]
    final_test: tuple[int, ...]

    def manifest(self):
        return {
            "random_seed": 42,
            "stratified": True,
            **{
                key: list(getattr(self, key))
                for key in (
                    "fitting",
                    "probability_calibration",
                    "threshold_calibration",
                    "final_test",
                )
            },
        }


def make_split(X, y):
    if not X.index.is_unique or not X.index.equals(y.index):
        raise ValueError("Source row identities must be unique and aligned")
    development, final = train_test_split(
        X.index, test_size=0.20, random_state=42, stratify=y
    )
    fitting, calibration = train_test_split(
        development, test_size=0.40, random_state=42, stratify=y.loc[development]
    )
    probability, threshold = train_test_split(
        calibration, test_size=0.50, random_state=42, stratify=y.loc[calibration]
    )
    return OutcomeSplit(
        *(
            tuple(int(i) for i in rows)
            for rows in (fitting, probability, threshold, final)
        )
    )


def select_features(X, stage):
    return X.loc[:, list(feature_names(stage))].copy()
