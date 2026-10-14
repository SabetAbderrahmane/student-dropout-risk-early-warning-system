"""One read-only, indexed operational policy for all B2 read contracts."""

import json
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from functools import lru_cache
from math import isfinite
from pathlib import Path

from sqlalchemy import (
    Float,
    Numeric,
    String,
    and_,
    case,
    cast,
    func,
    literal,
    or_,
    select,
)
from sqlalchemy.orm import aliased

from app.core.config import get_settings
from app.core.exceptions import ApplicationError
from app.ml.feature_schema import PREDICTION_FEATURES
from app.ml.outcomes.contracts import (
    SCHEMA_VERSIONS,
    STAGE_FEATURES,
    ModelTargetType,
    PredictionStage,
)
from app.ml.training.metadata import FEATURE_SCHEMA_VERSION
from app.models import (
    AdmissionRecord,
    FirstSemesterRecord,
    ModelVersion,
    PredictionResult,
    Student,
)


class PredictionFreshness(StrEnum):
    CURRENT = "CURRENT"
    NOT_SELECTED = "NOT_SELECTED"
    INPUTS_CHANGED = "INPUTS_CHANGED"
    INPUTS_INCOMPLETE = "INPUTS_INCOMPLETE"
    MODEL_SUPERSEDED = "MODEL_SUPERSEDED"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    STAGE_REASSESSMENT_REQUIRED = "STAGE_REASSESSMENT_REQUIRED"
    NO_PREDICTION = "NO_PREDICTION"


SCOPES = (
    (PredictionStage.FIRST_SEMESTER, ModelTargetType.MULTICLASS_OUTCOME),
    (PredictionStage.FIRST_SEMESTER, ModelTargetType.BINARY_DROPOUT),
    (PredictionStage.ENROLLMENT, ModelTargetType.MULTICLASS_OUTCOME),
)


def features_for(stage, target):
    return (
        PREDICTION_FEATURES
        if target == ModelTargetType.BINARY_DROPOUT
        else STAGE_FEATURES[stage]
    )


def column_for(feature):
    table = {
        "students": Student,
        "admission_records": AdmissionRecord,
        "first_semester_records": FirstSemesterRecord,
    }[feature.storage_table]
    return getattr(table, feature.storage_column)


def ready_condition(features):
    conditions = []
    for f in features:
        col = column_for(f)
        conditions.extend(
            [
                col.is_not(None),
                cast(col, String).not_in(("NaN", "Infinity", "-Infinity")),
            ]
        )
        if f.allowed_values is not None:
            conditions.append(col.in_(f.allowed_values))
        if f.minimum is not None:
            conditions.append(col >= f.minimum)
        if f.maximum is not None:
            conditions.append(col <= f.maximum)
    return func.coalesce(and_(*conditions), False)


def snapshot_matches(prediction, features, dialect):
    conditions = []
    for f in features:
        col = column_for(f)
        value = prediction.feature_snapshot[f.name]
        numeric = (
            (func.jsonb_typeof(value) == "number")
            if dialect == "postgresql"
            else func.json_type(prediction.feature_snapshot, "$." + f.name).in_(
                ("integer", "real")
            )
        )
        # Guard casts: malformed historical JSON yields mismatch, never an SQL error.
        number = case((numeric, cast(value.as_string(), Float)), else_=None)
        scale = getattr(col.type, "scale", None)
        if scale is not None:
            # NUMERIC(8,2) storage rounding is authoritative, not submitted precision.
            number = cast(func.round(cast(number, Numeric), scale), Float)
        conditions.append(
            func.coalesce(and_(numeric, number == cast(col, Float)), False)
        )
    return and_(*conditions)


@lru_cache(maxsize=32)
def _artifact_available(stage, target, version, root, signature, persisted):
    try:
        if target == ModelTargetType.BINARY_DROPOUT:
            from app.ml.deployment import load_verified_model

            bundle, metadata, _ = load_verified_model(*(Path(p) for p in root))
        else:
            from app.ml.outcomes.deployment import verify

            bundle, metadata, _, _ = verify(stage, root=Path(root[0]))
        return (
            bundle.model_version == version
            and metadata == json.loads(persisted[0])
            and bundle.model_name == persisted[1]
            and metadata["feature_schema_version"] == persisted[2]
            and bundle.low_threshold == persisted[3]
            and bundle.high_threshold == persisted[4]
        )
    except (ApplicationError, OSError, ValueError, KeyError):
        return False


def available_models(db):
    """DB activation is never cached; trusted bytes are cached by file stat identity."""
    settings = get_settings()
    models = db.scalars(
        select(ModelVersion).where(ModelVersion.is_active.is_(True))
    ).all()
    result = {}
    for model in models:
        scope = (model.prediction_stage, model.model_target_type)
        if scope not in SCOPES:
            continue
        if model.model_target_type == ModelTargetType.BINARY_DROPOUT:
            root = tuple(
                str(Path(p).resolve())
                for p in (
                    settings.ml_model_path,
                    settings.ml_metadata_path,
                    settings.ml_evaluation_path,
                    settings.ml_manifest_path,
                )
            )
            paths = list(root) + [str(Path(root[1]).parent / "split_manifest.json")]
        else:
            root = (str(Path(settings.ml_outcome_root).resolve()),)
            base = Path(root[0])
            paths = [str(base / "artifacts" / model.model_version / "model.joblib")]
            paths += [
                str(p)
                for p in (base / "model_registry" / model.model_version).glob("*.json")
            ]
        try:
            signature = tuple(
                (p, Path(p).stat().st_mtime_ns, Path(p).stat().st_size)
                for p in sorted(paths)
            )
            available = _artifact_available(
                *scope,
                model.model_version,
                root,
                signature,
                (
                    json.dumps(model.metadata_json, sort_keys=True),
                    model.model_name,
                    model.feature_schema_version,
                    model.low_threshold,
                    model.high_threshold,
                ),
            )
        except OSError:
            available = False
        result[scope] = (model, available)
    return result


def projection(db, *, student_ids=None, availability=None):
    """Compute each input condition once, then select through layered SQL projections."""
    dialect = db.get_bind().dialect.name
    availability = available_models(db) if availability is None else availability
    history = aliased(PredictionResult, name="assessment_history")
    latest_id = (
        select(PredictionResult.id)
        .where(PredictionResult.student_id == Student.id)
        .order_by(PredictionResult.predicted_at.desc(), PredictionResult.id.desc())
        .limit(1)
        .correlate(Student)
        .scalar_subquery()
    )
    had_semester = (
        select(PredictionResult.id)
        .where(
            PredictionResult.student_id == Student.id,
            PredictionResult.prediction_stage == PredictionStage.FIRST_SEMESTER,
        )
        .limit(1)
        .correlate(Student)
        .exists()
    )
    query = (
        select(
            Student.id.label("student_id"),
            history.id.label("historical_id"),
            history.prediction_stage.label("historical_stage"),
            had_semester.label("had_semester"),
        )
        .select_from(Student)
        .outerjoin(AdmissionRecord, AdmissionRecord.student_id == Student.id)
        .outerjoin(FirstSemesterRecord, FirstSemesterRecord.student_id == Student.id)
        .outerjoin(history, history.id == latest_id)
    )
    for index, scope in enumerate(SCOPES):
        stage, target = scope
        model = aliased(ModelVersion, name=f"assessment_model_{index}")
        pred = aliased(PredictionResult, name=f"assessment_candidate_{index}")
        query = query.outerjoin(
            model,
            and_(
                model.is_active.is_(True),
                model.prediction_stage == stage,
                model.model_target_type == target,
            ),
        )
        candidate_id = (
            select(PredictionResult.id)
            .where(
                PredictionResult.student_id == Student.id,
                PredictionResult.model_version_id == model.id,
            )
            .order_by(PredictionResult.predicted_at.desc(), PredictionResult.id.desc())
            .limit(1)
            .correlate(Student, model)
            .scalar_subquery()
        )
        query = query.outerjoin(pred, pred.id == candidate_id)
        schema = (
            FEATURE_SCHEMA_VERSION
            if target == ModelTargetType.BINARY_DROPOUT
            else SCHEMA_VERSIONS[stage]
        )
        query = query.add_columns(
            pred.id.label(f"candidate_{index}"),
            pred.risk_level.label(f"risk_{index}"),
            pred.probability.label(f"probability_{index}"),
            ready_condition(features_for(*scope)).label(f"ready_{index}"),
            snapshot_matches(pred, features_for(*scope), dialect).label(
                f"matches_{index}"
            ),
            model.id.label(f"active_model_{index}"),
            model.model_version.label(f"model_version_{index}"),
            func.coalesce(model.feature_schema_version == schema, False).label(
                f"schema_{index}"
            ),
            literal(availability.get(scope, (None, False))[1]).label(
                f"available_{index}"
            ),
        )
    if student_ids is not None:
        query = query.where(Student.id.in_(student_ids))
    inputs = query.cte("assessment_inputs")
    c = inputs.c
    eligible = select(inputs)
    for i in range(3):
        ready, matches, available, schema = (
            c[f"ready_{i}"],
            c[f"matches_{i}"],
            c[f"available_{i}"],
            c[f"schema_{i}"],
        )
        candidate, model = c[f"candidate_{i}"], c[f"active_model_{i}"]
        eligible = eligible.add_columns(
            and_(
                ready,
                matches,
                available,
                schema,
                model.is_not(None),
                candidate.is_not(None),
            ).label(f"valid_{i}"),
            case(
                (~ready, "INPUTS_INCOMPLETE"),
                (model.is_(None), "MODEL_SUPERSEDED"),
                (~available, "MODEL_UNAVAILABLE"),
                (~schema, "MODEL_SUPERSEDED"),
                (candidate.is_(None), "NO_PREDICTION"),
                (~matches, "INPUTS_CHANGED"),
                else_="CURRENT",
            ).label(f"candidate_state_{i}"),
        )
    eligible = eligible.add_columns(
        or_(c.ready_0, c.had_semester).label("progressed")
    ).cte("assessment_eligible")
    c = eligible.c
    selected = (
        select(eligible)
        .add_columns(
            case(
                (c.valid_0, c.candidate_0),
                (c.valid_1, c.candidate_1),
                (and_(~c.progressed, c.valid_2), c.candidate_2),
                else_=None,
            ).label("operational_id"),
            case(
                (c.valid_0, c.risk_0),
                (c.valid_1, c.risk_1),
                (and_(~c.progressed, c.valid_2), c.risk_2),
                else_=None,
            ).label("risk_level"),
            case(
                (c.valid_0, c.probability_0),
                (c.valid_1, c.probability_1),
                (and_(~c.progressed, c.valid_2), c.probability_2),
                else_=None,
            ).label("probability"),
            case(
                (and_(c.progressed, c.active_model_0.is_not(None), c.available_0), 0),
                (
                    and_(
                        c.progressed,
                        c.ready_1,
                        c.active_model_1.is_not(None),
                        or_(c.available_1, c.active_model_0.is_(None)),
                    ),
                    1,
                ),
                (c.progressed, 0),
                else_=2,
            ).label("preferred"),
        )
        .cte("assessment_selected")
    )
    c = selected.c
    chosen_state = case(
        (c.preferred == 0, c.candidate_state_0),
        (c.preferred == 1, c.candidate_state_1),
        else_=c.candidate_state_2,
    )
    status = case(
        (c.operational_id.is_not(None), "CURRENT"),
        (c.historical_id.is_(None), "NO_PREDICTION"),
        (and_(c.progressed, ~c.ready_0), "INPUTS_INCOMPLETE"),
        (
            and_(c.progressed, c.historical_stage == PredictionStage.ENROLLMENT),
            "STAGE_REASSESSMENT_REQUIRED",
        ),
        (
            chosen_state == "NO_PREDICTION",
            case(
                (c.candidate_0.is_not(None), c.candidate_state_0),
                (c.candidate_1.is_not(None), c.candidate_state_1),
                (and_(~c.progressed, c.candidate_2.is_not(None)), c.candidate_state_2),
                else_="MODEL_SUPERSEDED",
            ),
        ),
        else_=chosen_state,
    )
    return (
        select(selected)
        .add_columns(
            (
                func.transaction_timestamp()
                if dialect == "postgresql"
                else func.current_timestamp()
            ).label("assessment_as_of"),
            status.label("assessment_status"),
            and_(c.historical_id.is_not(None), c.operational_id.is_(None)).label(
                "reassessment_required"
            ),
            case((c.progressed, "FIRST_SEMESTER"), else_="ENROLLMENT").label(
                "recommended_stage"
            ),
            case(
                (c.preferred == 1, "BINARY_DROPOUT"), else_="MULTICLASS_OUTCOME"
            ).label("recommended_target_type"),
            case(
                (c.preferred == 0, c.active_model_0),
                (c.preferred == 1, c.active_model_1),
                else_=c.active_model_2,
            ).label("recommended_model_id"),
            case(
                (c.preferred == 0, c.model_version_0),
                (c.preferred == 1, c.model_version_1),
                else_=c.model_version_2,
            ).label("recommended_model_version"),
            case(
                (c.preferred == 0, c.available_0),
                (c.preferred == 1, c.available_1),
                else_=c.available_2,
            ).label("recommended_model_available"),
            c.ready_2.label("enrollment_ready"),
            c.ready_0.label("first_semester_ready"),
            c.ready_1.label("legacy_ready"),
        )
        .subquery("operational_assessment")
    )


def assessment_fields(row):
    return {
        key: row[key]
        for key in (
            "assessment_as_of",
            "assessment_status",
            "reassessment_required",
            "recommended_stage",
            "recommended_target_type",
            "recommended_model_version",
            "recommended_model_available",
            "enrollment_ready",
            "first_semester_ready",
            "legacy_ready",
        )
    }


def input_changes(student, prediction):
    """Bounded detail diagnostics using the same NUMERIC-storage normalization."""
    sources = {
        "students": student,
        "admission_records": student.admission_record,
        "first_semester_records": student.first_semester_record,
    }
    missing, changed = [], []
    for f in features_for(prediction.prediction_stage, prediction.model_target_type):
        value = getattr(sources[f.storage_table], f.storage_column, None)
        if value is None:
            missing.append(f.name)
            continue
        previous = prediction.feature_snapshot.get(f.name)

        def normalize(v, feature=f):
            if (
                isinstance(v, bool)
                or not isinstance(v, (int, float, Decimal))
                or not isfinite(float(v))
            ):
                return None
            scale = getattr(column_for(feature).type, "scale", None)
            return (
                float(
                    Decimal(str(v)).quantize(
                        Decimal(1).scaleb(-scale), rounding=ROUND_HALF_UP
                    )
                )
                if scale is not None
                else float(v)
            )

        if normalize(previous) != normalize(value):
            changed.append(f.name)
    return {"missing_features": missing, "changed_features": changed}


def prediction_metadata(db, prediction_ids, *, assessment=None):
    """Compare only requested history/page records; never load all histories."""
    if not prediction_ids:
        return {}
    assessment = projection(db) if assessment is None else assessment
    pred = PredictionResult
    model = ModelVersion
    dialect = db.get_bind().dialect.name
    ready, matches = [], []
    for scope in SCOPES:
        condition = and_(
            pred.prediction_stage == scope[0], pred.model_target_type == scope[1]
        )
        ready.append((condition, ready_condition(features_for(*scope))))
        matches.append(
            (condition, snapshot_matches(pred, features_for(*scope), dialect))
        )
    inputs = case(*ready, else_=False)
    same = case(*matches, else_=False)
    available_ids = [
        model.id for model, available in available_models(db).values() if available
    ]
    state = case(
        (~inputs, "INPUTS_INCOMPLETE"),
        (~same, "INPUTS_CHANGED"),
        (~model.is_active, "MODEL_SUPERSEDED"),
        (~model.id.in_(available_ids), "MODEL_UNAVAILABLE"),
        (
            and_(
                pred.prediction_stage == PredictionStage.ENROLLMENT,
                assessment.c.reassessment_required,
                assessment.c.recommended_stage == "FIRST_SEMESTER",
            ),
            "STAGE_REASSESSMENT_REQUIRED",
        ),
        (
            or_(
                assessment.c.operational_id.is_(None),
                pred.id != assessment.c.operational_id,
            ),
            "NOT_SELECTED",
        ),
        else_="CURRENT",
    )
    rows = (
        db.execute(
            select(
                pred.id,
                state.label("prediction_freshness"),
                (pred.id == assessment.c.operational_id).label(
                    "is_operational_current"
                ),
                assessment.c.reassessment_required.label("requires_reassessment"),
            )
            .join(model, model.id == pred.model_version_id)
            .join(Student, Student.id == pred.student_id)
            .outerjoin(AdmissionRecord, AdmissionRecord.student_id == Student.id)
            .outerjoin(
                FirstSemesterRecord, FirstSemesterRecord.student_id == Student.id
            )
            .join(assessment, assessment.c.student_id == Student.id)
            .where(pred.id.in_(prediction_ids))
        )
        .mappings()
        .all()
    )
    return {
        row["id"]: {
            key: row[key] if row[key] is not None else False
            for key in (
                "prediction_freshness",
                "is_operational_current",
                "requires_reassessment",
            )
        }
        for row in rows
    }
