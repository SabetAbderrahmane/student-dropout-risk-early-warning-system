from dataclasses import dataclass
from decimal import Decimal
from math import isfinite

import pandas as pd

from app.ml.feature_schema import PREDICTION_FEATURES, validate_feature_value
from app.models.student import Student


@dataclass(frozen=True, slots=True)
class FeatureAssembly:
    values: dict[str, int | float]
    missing_features: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return not self.missing_features

    def dataframe(self) -> pd.DataFrame:
        if not self.ready:
            raise ValueError("Cannot create inference row with missing features")
        return pd.DataFrame(
            [[self.values[name] for name in self.values]], columns=list(self.values)
        )


def assemble_prediction_features(student: Student) -> FeatureAssembly:
    sources = {
        "students": student,
        "admission_records": student.admission_record,
        "first_semester_records": student.first_semester_record,
    }
    values: dict[str, int | float] = {}
    missing: list[str] = []
    for feature in PREDICTION_FEATURES:
        source = sources[feature.storage_table]
        value = (
            None if source is None else getattr(source, feature.storage_column, None)
        )
        if isinstance(value, Decimal):
            value = float(value)
        if value is None or isinstance(value, float) and not isfinite(value):
            missing.append(feature.name)
            continue
        try:
            validated = validate_feature_value(feature.name, value)
        except (TypeError, ValueError):
            missing.append(feature.name)
            continue
        assert validated is not None
        values[feature.name] = validated
    return FeatureAssembly(values=values, missing_features=tuple(missing))
