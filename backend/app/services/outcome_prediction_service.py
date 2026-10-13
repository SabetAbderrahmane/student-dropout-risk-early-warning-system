"""Explicit stage execution with independently active, verified multiclass models."""

from datetime import datetime, timezone

from sqlalchemy import select

from app.core.exceptions import ApplicationError
from app.ml.outcomes.contracts import (
    MODEL_VERSIONS,
    STAGE_FEATURES,
    ModelTargetType,
)
from app.ml.outcomes.features import assemble
from app.ml.outcomes.runtime import get_outcome_runtime
from app.models.prediction import (
    AcademicOutcome,
    ModelVersion,
    PredictionResult,
    RiskLevel,
)
from app.schemas.prediction import BatchPredictionResponse, StageReadiness
from app.services.prediction_service import PredictionService


class OutcomePredictionService(PredictionService):
    def stage_readiness(self, student_id, stage):
        assembly = assemble(self._student(student_id), stage)
        version = MODEL_VERSIONS[stage]
        model = self.repository.get_model_by_version(version)
        model_error = None
        try:
            get_outcome_runtime(stage, version=version)
            model_status = (
                "ACTIVE" if model is not None and model.is_active else "INACTIVE"
            )
        except ApplicationError as exc:
            model_status = "UNAVAILABLE"
            model_error = exc.code
        return StageReadiness(
            status="READY"
            if assembly.ready and model_status == "ACTIVE"
            else "NOT_READY",
            feature_status="READY" if assembly.ready else "NOT_READY",
            prediction_stage=stage,
            required_feature_count=len(STAGE_FEATURES[stage]),
            available_feature_count=len(assembly.values),
            missing_features=list(assembly.missing_features),
            invalid_features=assembly.invalid_features,
            model_status=model_status,
            model_version=version,
            model_error=model_error,
        )

    def _active_runtime(self, stage):
        model = self.repository.get_active_model(
            stage=stage, target_type=ModelTargetType.MULTICLASS_OUTCOME
        )
        if model is None:
            raise ApplicationError(
                409,
                "STAGE_MODEL_INACTIVE",
                "No validated model is active for this prediction stage.",
                {
                    "prediction_stage": stage.value,
                    "model_version": MODEL_VERSIONS[stage],
                },
            )
        # Hold activation metadata stable for the prediction transaction.
        model = self.db.scalar(
            select(ModelVersion)
            .where(ModelVersion.id == model.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if (
            not model.is_active
            or model.prediction_stage != stage
            or model.model_target_type != ModelTargetType.MULTICLASS_OUTCOME
        ):
            raise ApplicationError(
                409,
                "INCOMPATIBLE_STAGE_MODEL",
                "The selected stage model is no longer active.",
            )
        runtime = get_outcome_runtime(stage, version=model.model_version)
        if model.metadata_json != runtime.metadata:
            raise ApplicationError(
                503,
                "MODEL_REGISTRY_MISMATCH",
                "The persisted stage model differs from its trusted registry.",
            )
        return model, runtime

    @staticmethod
    def build_prediction(student, assembly, runtime, model, created_by):
        row = assembly.dataframe()
        outcome, probabilities = runtime.predict(row)
        probability = probabilities["DROPOUT"]
        return PredictionResult(
            student_id=student.id,
            model_version_id=model.id,
            prediction_stage=assembly.prediction_stage,
            model_target_type=ModelTargetType.MULTICLASS_OUTCOME,
            predicted_outcome=AcademicOutcome(outcome),
            class_probabilities=probabilities,
            probability=probability,
            risk_level=RiskLevel(runtime.bundle.classify_risk(probability)),
            feature_snapshot=assembly.values,
            explanation=runtime.bundle.explain_local(row, top_k=5),
            predicted_at=datetime.now(timezone.utc),
            created_by=created_by,
        )

    def predict_stage(self, student_id, stage, *, created_by):
        student = self._student(student_id)
        assembly = assemble(student, stage)
        if not assembly.ready:
            raise ApplicationError(
                409,
                "PREDICTION_NOT_READY",
                "Required stage features are missing or invalid.",
                self.stage_readiness(student_id, stage).model_dump(mode="json"),
            )
        try:
            model, runtime = self._active_runtime(stage)
            prediction = self.repository.add_prediction(
                self.build_prediction(student, assembly, runtime, model, created_by)
            )
            self._add_warning_for_prediction(prediction)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.get_prediction(prediction.id)

    def predict_stage_batch(self, stage, *, created_by):
        created, skipped, warnings = 0, 0, 0
        try:
            model, runtime = self._active_runtime(stage)
            for student in self.repository.list_student_graphs():
                assembly = assemble(student, stage)
                if not assembly.ready:
                    skipped += 1
                    continue
                prediction = self.repository.add_prediction(
                    self.build_prediction(student, assembly, runtime, model, created_by)
                )
                warnings += self._add_warning_for_prediction(prediction)
                created += 1
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return BatchPredictionResponse(
            assessed=created,
            skipped_not_ready=skipped,
            created_predictions=created,
            created_warnings=warnings,
            model_version=model.model_version,
            prediction_stage=stage,
            model_target_type=ModelTargetType.MULTICLASS_OUTCOME,
            completed_at=datetime.now(timezone.utc),
        )
