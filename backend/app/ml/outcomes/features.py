"""Stage readiness with explicit missing/invalid reasons; no academic fabrication."""

from dataclasses import dataclass
from decimal import Decimal
from math import isfinite

import pandas as pd

from app.ml.feature_schema import FeatureDataType, validate_feature_value
from app.ml.outcomes.contracts import STAGE_FEATURES, PredictionStage, feature_names


@dataclass(frozen=True)
class StageAssembly:
    prediction_stage: PredictionStage
    values: dict[str, int | float]
    missing_features: tuple[str, ...]
    invalid_features: dict[str, str]

    @property
    def ready(self):
        return not self.missing_features and not self.invalid_features

    def dataframe(self):
        if not self.ready:
            raise ValueError("Stage features are incomplete or invalid")
        return pd.DataFrame([self.values], columns=feature_names(self.prediction_stage))


def assemble(student, stage):
    sources = {
        "students": student,
        "admission_records": student.admission_record,
        "first_semester_records": student.first_semester_record,
    }
    values, missing, invalid = {}, [], {}
    for feature in STAGE_FEATURES[stage]:
        source = sources[feature.storage_table]
        value = (
            getattr(source, feature.storage_column, None)
            if source is not None
            else None
        )
        if value is None:
            missing.append(feature.name)
            continue
        if isinstance(value, Decimal):
            value = float(value)
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not isfinite(value)
        ):
            invalid[feature.name] = "Must be a finite numeric measurement"
            continue
        if (
            feature.data_type == FeatureDataType.INTEGER
            and not float(value).is_integer()
        ):
            invalid[feature.name] = "Must be an integer measurement"
            continue
        try:
            validate_feature_value(feature.name, value)
        except (ValueError, TypeError) as exc:
            invalid[feature.name] = str(exc)
            continue
        values[feature.name] = (
            int(value) if feature.data_type == FeatureDataType.INTEGER else float(value)
        )
    return StageAssembly(stage, values, tuple(missing), invalid)
