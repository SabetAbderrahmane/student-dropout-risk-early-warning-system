"""Bounded, fold-isolated three-family search and dropout-oriented selection."""

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import RandomizedSearchCV, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier

from app.ml.feature_schema import FeatureKind
from app.ml.outcomes.contracts import STAGE_FEATURES
from app.ml.outcomes.metrics import evaluate, meets_constraints, selection_score

FAMILIES = ("Logistic Regression", "Random Forest", "XGBoost")
CV_METRICS = (
    "accuracy",
    "macro_precision",
    "macro_recall",
    "macro_f1",
    "weighted_f1",
    "dropout_pr_auc",
    "dropout_precision",
    "dropout_recall",
    "log_loss",
)
SELECTION_METHOD = (
    "0.40 dropout recall + 0.30 dropout PR-AUC + 0.20 macro F1 + 0.10 dropout precision"
)


class FoldWeightedXGBClassifier(XGBClassifier):
    """Compute balanced weights only from the labels visible in this fit/fold."""

    def __init__(self, *, weight_strategy=None, **kwargs):
        self.weight_strategy = weight_strategy
        super().__init__(**kwargs)

    def get_xgb_params(self):
        params = super().get_xgb_params()
        params.pop("weight_strategy", None)
        return params

    def fit(self, X, y, **kwargs):
        if self.weight_strategy not in (None, "balanced"):
            raise ValueError("Unknown sample weighting strategy")
        if self.weight_strategy == "balanced":
            kwargs["sample_weight"] = compute_sample_weight("balanced", y)
        return super().fit(X, y, **kwargs)


def preprocessor(stage):
    features = STAGE_FEATURES[stage]
    numeric = [f.name for f in features if f.kind == FeatureKind.NUMERIC]
    categorical = [f.name for f in features if f.kind != FeatureKind.NUMERIC]
    return ColumnTransformer(
        [
            (
                "numeric",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler()),
                    ]
                ),
                numeric,
            ),
            (
                "categorical",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        (
                            "encoder",
                            OneHotEncoder(handle_unknown="ignore", sparse_output=True),
                        ),
                    ]
                ),
                categorical,
            ),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )


def candidates(stage):
    def pipeline(model):
        return Pipeline([("preprocess", preprocessor(stage)), ("model", model)])

    return {
        "Logistic Regression": (
            pipeline(
                LogisticRegression(solver="lbfgs", max_iter=2000, random_state=42)
            ),
            {
                "model__C": [0.05, 0.2, 1.0, 5.0],
                "model__class_weight": [None, "balanced"],
            },
        ),
        "Random Forest": (
            pipeline(RandomForestClassifier(random_state=42, n_jobs=1)),
            {
                "model__n_estimators": [150, 250],
                "model__max_depth": [None, 8, 16],
                "model__min_samples_leaf": [1, 3, 6],
                "model__class_weight": [None, "balanced"],
            },
        ),
        "XGBoost": (
            pipeline(
                FoldWeightedXGBClassifier(
                    objective="multi:softprob",
                    num_class=3,
                    eval_metric="mlogloss",
                    random_state=42,
                    n_jobs=1,
                    tree_method="hist",
                )
            ),
            {
                "model__n_estimators": [120, 220],
                "model__max_depth": [2, 3, 4],
                "model__learning_rate": [0.04, 0.10],
                "model__reg_lambda": [1.0, 5.0],
                "model__weight_strategy": [None, "balanced"],
            },
        ),
    }


def _scoring(estimator, X, y):
    if tuple(estimator.classes_) != (0, 1, 2):
        raise ValueError("Candidate class ordering is invalid")
    metrics = evaluate(y, estimator.predict_proba(X))
    return {name: metrics[name] for name in CV_METRICS}


def _refit(results):
    metrics = [
        {key: float(results[f"mean_test_{key}"][i]) for key in CV_METRICS}
        for i in range(len(results["params"]))
    ]
    eligible = [i for i, item in enumerate(metrics) if meets_constraints(item)]
    return max(
        eligible or range(len(metrics)),
        key=lambda i: (
            selection_score(metrics[i]),
            metrics[i]["dropout_pr_auc"],
            metrics[i]["macro_f1"],
            -i,
        ),
    )


def train_candidates(X, y, stage, *, iterations=6, jobs=2):
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    results = []
    for family, (pipeline, space) in candidates(stage).items():
        print(
            f"{stage}: searching {family}, {iterations} candidates x 5 folds",
            flush=True,
        )
        search = RandomizedSearchCV(
            pipeline,
            space,
            n_iter=iterations,
            scoring=_scoring,
            refit=_refit,
            cv=cv,
            random_state=42,
            n_jobs=jobs,
            error_score="raise",
        )
        search.fit(X, y)
        index = search.best_index_
        metrics = {
            key: float(search.cv_results_[f"mean_test_{key}"][index])
            for key in CV_METRICS
        }
        results.append(
            {
                "name": family,
                "estimator": search.best_estimator_,
                "search_space": space,
                "best_hyperparameters": search.best_params_,
                "cv_metrics": metrics,
                "cv_metric_std": {
                    key: float(search.cv_results_[f"std_test_{key}"][index])
                    for key in CV_METRICS
                },
                "selection_score": selection_score(metrics),
                "meets_constraints": meets_constraints(metrics),
            }
        )
    return results


def select_winner(results):
    if len(results) != 3 or {r["name"] for r in results} != set(FAMILIES):
        raise ValueError("Exactly the three candidate families are required")
    eligible = [r for r in results if meets_constraints(r["cv_metrics"])]
    if not eligible:
        raise ValueError(
            "No candidate meets the predeclared dropout recall/macro F1 constraints"
        )
    return max(
        eligible,
        key=lambda r: (
            selection_score(r["cv_metrics"]),
            r["cv_metrics"]["dropout_pr_auc"],
            r["cv_metrics"]["macro_f1"],
            -FAMILIES.index(r["name"]),
        ),
    )
