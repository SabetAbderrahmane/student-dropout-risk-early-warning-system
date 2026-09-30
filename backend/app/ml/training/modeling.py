"""Leakage-safe preprocessing, bounded model searches, and model selection."""

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import RandomizedSearchCV, StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

from app.ml.feature_schema import FeatureKind, PREDICTION_FEATURES
from app.ml.training.data import RANDOM_SEED

CV_FOLDS = 5
SCORING = {
    "accuracy": "accuracy",
    "precision": "precision",
    "recall": "recall",
    "f1": "f1",
    "roc_auc": "roc_auc",
    "pr_auc": "average_precision",
}

NUMERIC_FEATURES = tuple(
    feature.name for feature in PREDICTION_FEATURES if feature.kind == FeatureKind.NUMERIC
)
CATEGORICAL_FEATURES = tuple(
    feature.name for feature in PREDICTION_FEATURES if feature.kind != FeatureKind.NUMERIC
)


@dataclass(frozen=True, slots=True)
class CandidateResult:
    name: str
    search_space: dict[str, list[Any]]
    best_params: dict[str, Any]
    cv_metrics: dict[str, float]
    cv_metric_std: dict[str, float]
    confusion_matrix: dict[str, int]
    selection_score: float
    best_estimator: Pipeline
    oof_probabilities: np.ndarray


def make_preprocessor() -> ColumnTransformer:
    """Create preprocessing whose learned state is fit inside each CV fold."""
    numeric = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    categorical = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="most_frequent")),
            (
                "encoder",
                OneHotEncoder(handle_unknown="ignore", sparse_output=True),
            ),
        ]
    )
    return ColumnTransformer(
        [
            ("numeric", numeric, list(NUMERIC_FEATURES)),
            ("categorical", categorical, list(CATEGORICAL_FEATURES)),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )


def _pipeline(estimator: Any) -> Pipeline:
    return Pipeline([("preprocess", make_preprocessor()), ("model", estimator)])


def candidate_definitions(y: pd.Series) -> dict[str, tuple[Pipeline, dict[str, list[Any]], int]]:
    negative, positive = np.bincount(y.astype(int), minlength=2)
    scale_pos_weight = float(negative / positive)
    return {
        "Logistic Regression": (
            _pipeline(
                LogisticRegression(
                    class_weight="balanced",
                    max_iter=2000,
                    random_state=RANDOM_SEED,
                    solver="liblinear",
                )
            ),
            {
                "model__C": [0.01, 0.1, 0.5, 1.0, 5.0, 10.0, 100.0],
                "model__penalty": ["l1", "l2"],
            },
            12,
        ),
        "Random Forest": (
            _pipeline(
                RandomForestClassifier(
                    class_weight="balanced",
                    random_state=RANDOM_SEED,
                    n_jobs=1,
                )
            ),
            {
                "model__n_estimators": [200, 350, 500],
                "model__max_depth": [None, 8, 14, 20],
                "model__min_samples_split": [2, 5, 10],
                "model__min_samples_leaf": [1, 2, 4],
                "model__max_features": ["sqrt", 0.5, 0.8],
            },
            12,
        ),
        "XGBoost": (
            _pipeline(
                XGBClassifier(
                    objective="binary:logistic",
                    eval_metric="logloss",
                    random_state=RANDOM_SEED,
                    n_jobs=1,
                    tree_method="hist",
                    scale_pos_weight=scale_pos_weight,
                )
            ),
            {
                "model__n_estimators": [150, 250, 400, 550],
                "model__max_depth": [2, 3, 4, 5],
                "model__learning_rate": [0.02, 0.05, 0.1, 0.2],
                "model__subsample": [0.7, 0.85, 1.0],
                "model__colsample_bytree": [0.7, 0.85, 1.0],
                "model__min_child_weight": [1, 3, 5],
                "model__reg_lambda": [1.0, 5.0, 10.0],
            },
            12,
        ),
    }


def _probability_metrics(y: pd.Series, probabilities: np.ndarray) -> tuple[dict[str, float], dict[str, int]]:
    predictions = (probabilities >= 0.5).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, predictions, labels=[0, 1]).ravel()
    metrics = {
        "accuracy": float(accuracy_score(y, predictions)),
        "precision": float(precision_score(y, predictions, zero_division=0)),
        "recall": float(recall_score(y, predictions, zero_division=0)),
        "f1": float(f1_score(y, predictions, zero_division=0)),
        "roc_auc": float(roc_auc_score(y, probabilities)),
        "pr_auc": float(average_precision_score(y, probabilities)),
    }
    matrix = {"tp": int(tp), "fp": int(fp), "tn": int(tn), "fn": int(fn)}
    return metrics, matrix


def train_candidates(X: pd.DataFrame, y: pd.Series) -> list[CandidateResult]:
    cv = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_SEED)
    results: list[CandidateResult] = []
    for name, (pipeline, parameters, iterations) in candidate_definitions(y).items():
        search = RandomizedSearchCV(
            pipeline,
            param_distributions=parameters,
            n_iter=iterations,
            scoring=SCORING,
            refit="pr_auc",
            cv=cv,
            random_state=RANDOM_SEED,
            n_jobs=-1,
            error_score="raise",
            return_train_score=False,
        )
        search.fit(X, y)
        best_index = search.best_index_
        cv_metrics = {
            metric: float(search.cv_results_[f"mean_test_{metric}"][best_index])
            for metric in SCORING
        }
        cv_stds = {
            metric: float(search.cv_results_[f"std_test_{metric}"][best_index])
            for metric in SCORING
        }
        oof = cross_val_predict(
            search.best_estimator_,
            X,
            y,
            cv=cv,
            method="predict_proba",
            n_jobs=-1,
        )[:, 1]
        _, matrix = _probability_metrics(y, oof)
        selection_score = (
            0.50 * cv_metrics["recall"]
            + 0.30 * cv_metrics["pr_auc"]
            + 0.20 * cv_metrics["precision"]
        )
        results.append(
            CandidateResult(
                name=name,
                search_space=parameters,
                best_params=search.best_params_,
                cv_metrics=cv_metrics,
                cv_metric_std=cv_stds,
                confusion_matrix=matrix,
                selection_score=float(selection_score),
                best_estimator=search.best_estimator_,
                oof_probabilities=oof,
            )
        )
    return results


def select_winner(results: list[CandidateResult]) -> CandidateResult:
    """Select by recall-weighted score with PR-AUC and precision guardrails."""
    if {result.name for result in results} != {
        "Logistic Regression",
        "Random Forest",
        "XGBoost",
    }:
        raise ValueError("Exactly the three locked candidate families are required")
    return max(
        results,
        key=lambda result: (
            result.selection_score,
            result.cv_metrics["recall"],
            result.cv_metrics["pr_auc"],
            result.cv_metrics["precision"],
        ),
    )
