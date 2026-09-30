"""Dataset retrieval, schema validation, target encoding, and frozen splitting."""

from dataclasses import dataclass
from typing import Any

import pandas as pd
from sklearn.model_selection import train_test_split
from ucimlrepo import fetch_ucirepo

from app.ml.feature_schema import (
    BINARY_TARGET_ENCODING,
    EXCLUDED_SECOND_SEMESTER_OFFICIAL_NAMES,
    PREDICTION_FEATURES,
)

DATASET_ID = 697
DATASET_NAME = "Predict Students' Dropout and Academic Success"
RANDOM_SEED = 42
FINAL_TEST_SIZE = 0.20

CANONICAL_FEATURE_NAMES = tuple(feature.name for feature in PREDICTION_FEATURES)
OFFICIAL_TO_CANONICAL = {
    feature.official_name: feature.name for feature in PREDICTION_FEATURES
}
EXPECTED_UCI_FEATURE_COLUMNS = frozenset(OFFICIAL_TO_CANONICAL) | frozenset(
    EXCLUDED_SECOND_SEMESTER_OFFICIAL_NAMES
)


@dataclass(frozen=True, slots=True)
class DatasetSplit:
    X_development: pd.DataFrame
    X_final_test: pd.DataFrame
    y_development: pd.Series
    y_final_test: pd.Series
    development_indices: tuple[int, ...]
    final_test_indices: tuple[int, ...]


def validate_uci_schema(features: pd.DataFrame, targets: pd.DataFrame) -> None:
    """Fail if UCI changes the official feature or target schema."""
    if not features.columns.is_unique:
        raise ValueError("UCI feature columns are not unique")
    actual = frozenset(str(column) for column in features.columns)
    missing = sorted(EXPECTED_UCI_FEATURE_COLUMNS - actual)
    unexpected = sorted(actual - EXPECTED_UCI_FEATURE_COLUMNS)
    if missing or unexpected or len(features.columns) != len(EXPECTED_UCI_FEATURE_COLUMNS):
        raise ValueError(
            "UCI dataset 697 schema mismatch: "
            f"missing={missing}, unexpected={unexpected}"
        )
    if list(targets.columns) != ["Target"]:
        raise ValueError(
            f"UCI target schema mismatch: expected ['Target'], got {list(targets.columns)}"
        )


def map_uci_features(features: pd.DataFrame) -> pd.DataFrame:
    """Select and rename only the canonical 30 features in canonical order."""
    selected = features.loc[:, list(OFFICIAL_TO_CANONICAL)].rename(
        columns=OFFICIAL_TO_CANONICAL
    )
    selected = selected.loc[:, list(CANONICAL_FEATURE_NAMES)]
    if tuple(selected.columns) != CANONICAL_FEATURE_NAMES:
        raise AssertionError("Canonical feature ordering was not preserved")
    return selected


def encode_binary_target(target: pd.Series) -> pd.Series:
    """Encode the frozen Dropout-vs-not-Dropout target."""
    unknown = sorted(set(target.dropna().unique()) - set(BINARY_TARGET_ENCODING))
    if unknown or target.isna().any():
        raise ValueError(f"Unexpected or missing target values: {unknown}")
    encoded = target.map(BINARY_TARGET_ENCODING)
    if encoded.isna().any():
        raise ValueError("Target encoding produced missing values")
    return encoded.astype("int8").rename("dropout")


def load_uci_dataset() -> tuple[pd.DataFrame, pd.Series, dict[str, Any]]:
    """Retrieve UCI 697 and return canonical features, binary target, and source info."""
    dataset = fetch_ucirepo(id=DATASET_ID)
    features = dataset.data.features.copy()
    targets = dataset.data.targets.copy()
    validate_uci_schema(features, targets)
    X = map_uci_features(features)
    y = encode_binary_target(targets["Target"])
    if len(X) != len(y):
        raise ValueError("Feature and target row counts differ")
    source = {
        "name": DATASET_NAME,
        "dataset_id": DATASET_ID,
        "repository": "UCI Machine Learning Repository",
        "retrieval_library": "ucimlrepo",
        "homepage": "https://archive.ics.uci.edu/dataset/697/",
    }
    return X, y, source


def make_final_split(
    X: pd.DataFrame,
    y: pd.Series,
    *,
    random_seed: int = RANDOM_SEED,
) -> DatasetSplit:
    """Create the deterministic stratified 80/20 development/final split."""
    if tuple(X.columns) != CANONICAL_FEATURE_NAMES:
        raise ValueError("Input features are not in canonical order")
    development_indices, final_test_indices = train_test_split(
        X.index.to_numpy(),
        test_size=FINAL_TEST_SIZE,
        random_state=random_seed,
        stratify=y,
    )
    development_indices = tuple(int(index) for index in development_indices)
    final_test_indices = tuple(int(index) for index in final_test_indices)
    return DatasetSplit(
        X_development=X.loc[list(development_indices)].copy(),
        X_final_test=X.loc[list(final_test_indices)].copy(),
        y_development=y.loc[list(development_indices)].copy(),
        y_final_test=y.loc[list(final_test_indices)].copy(),
        development_indices=development_indices,
        final_test_indices=final_test_indices,
    )


def class_counts(target: pd.Series) -> dict[str, int]:
    counts = target.value_counts().to_dict()
    return {"non_dropout": int(counts.get(0, 0)), "dropout": int(counts.get(1, 0))}
