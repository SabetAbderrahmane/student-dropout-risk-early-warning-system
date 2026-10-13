"""Inactive registration, reversible integration probes and audited explicit activation."""

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select, text

from app.core.config import get_settings
from app.core.exceptions import ApplicationError
from app.ml.outcomes.contracts import (
    CLASS_LABELS,
    MODEL_VERSIONS,
    ModelTargetType,
    PredictionStage,
)
from app.ml.outcomes.deployment import read_registry, verify
from app.ml.outcomes.features import assemble
from app.ml.outcomes.runtime import OutcomeRuntime, get_outcome_runtime
from app.ml.runtime import get_model_runtime
from app.models.prediction import ModelActivationEvent, ModelValidation, ModelVersion
from app.schemas.prediction import ModelCatalog, ModelCatalogEntry
from app.services.outcome_prediction_service import OutcomePredictionService
from app.services.prediction_service import PredictionService
from app.services.user_service import UserService


class ModelCatalogService(PredictionService):
    def _lock_registry(self):
        if self.db.get_bind().dialect.name == "postgresql":
            self.db.execute(text("SELECT pg_advisory_xact_lock(610110010)"))

    def register_stage(self, stage):
        self._lock_registry()
        metadata, _, _ = read_registry(stage, root=Path(get_settings().ml_outcome_root))
        model = self.repository.get_model_by_version(metadata["model_version"])
        if model is None:
            model = self.repository.add_model(
                ModelVersion(
                    model_name=metadata["model_name"],
                    model_version=metadata["model_version"],
                    prediction_stage=stage,
                    model_target_type=ModelTargetType.MULTICLASS_OUTCOME,
                    feature_schema_version=metadata["feature_schema_version"],
                    trained_at=datetime.fromisoformat(metadata["trained_at"]),
                    low_threshold=metadata["thresholds"]["low_threshold"],
                    high_threshold=metadata["thresholds"]["high_threshold"],
                    metrics=metadata["final_test_metrics"],
                    metadata_json=metadata,
                    artifact_path=metadata["artifact_path"],
                    is_active=False,
                )
            )
        else:
            trained = (
                model.trained_at
                if model.trained_at.tzinfo
                else model.trained_at.replace(tzinfo=timezone.utc)
            )
            if (
                model.metadata_json != metadata
                or model.prediction_stage != stage
                or model.model_target_type != ModelTargetType.MULTICLASS_OUTCOME
                or model.model_name != metadata["model_name"]
                or model.feature_schema_version != metadata["feature_schema_version"]
                or model.low_threshold != metadata["thresholds"]["low_threshold"]
                or model.high_threshold != metadata["thresholds"]["high_threshold"]
                or model.metrics != metadata["final_test_metrics"]
                or model.artifact_path != metadata["artifact_path"]
                or trained != datetime.fromisoformat(metadata["trained_at"])
            ):
                raise ApplicationError(
                    503,
                    "MODEL_REGISTRY_MISMATCH",
                    "The persisted stage model conflicts with the trusted registry.",
                )
        return model

    def register_new_models(self):
        try:
            for stage in PredictionStage:
                self.register_stage(stage)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def _validation(self, model, checksum):
        if checksum is None:
            return None
        return self.db.scalar(
            select(ModelValidation)
            .where(
                ModelValidation.model_version_id == model.id,
                ModelValidation.artifact_sha256 == checksum,
            )
            .order_by(ModelValidation.validated_at.desc(), ModelValidation.id.desc())
        )

    def entry(self, model):
        available = True
        availability_error = None
        checksum = None
        if model.model_target_type == ModelTargetType.MULTICLASS_OUTCOME:
            try:
                runtime = get_outcome_runtime(
                    model.prediction_stage, version=model.model_version
                )
                metadata, evaluation = runtime.metadata, runtime.evaluation
                checksum = runtime.manifest["artifact_sha256"]
            except ApplicationError as exc:
                available = False
                availability_error = exc.code
                metadata, evaluation = (
                    model.metadata_json,
                    {"final_test": model.metrics},
                )
            labels = list(CLASS_LABELS)
        else:
            metadata = model.metadata_json
            labels = ["NON_DROPOUT", "DROPOUT"]
            try:
                runtime = get_model_runtime()
                evaluation = runtime.evaluation
                manifest = json_manifest(Path(get_settings().ml_manifest_path))
                checksum = manifest["artifact_sha256"]
            except ApplicationError as exc:
                available = False
                availability_error = exc.code
                evaluation = {"final_test": model.metrics}
        validation = self._validation(model, checksum)
        return ModelCatalogEntry(
            id=model.id,
            name=model.model_name,
            version=model.model_version,
            prediction_stage=model.prediction_stage,
            model_target_type=model.model_target_type,
            feature_schema_version=model.feature_schema_version,
            feature_count=len(metadata["features"]),
            class_labels=labels,
            trained_at=model.trained_at,
            low_threshold=model.low_threshold,
            high_threshold=model.high_threshold,
            is_active=model.is_active,
            artifact_available=available,
            availability_error=availability_error,
            artifact_sha256=checksum,
            validation_id=validation.id if validation else None,
            validated_at=validation.validated_at if validation else None,
            evaluation=evaluation,
            selection=metadata["selection"],
            probability_calibration=metadata.get("probability_calibration"),
            threshold_calibration=metadata["thresholds"],
            explanation_method=metadata["explanation_method"],
        )

    def catalog(self):
        self.synchronize_registry()
        self.register_new_models()
        models = self.db.scalars(
            select(ModelVersion).order_by(
                ModelVersion.model_target_type,
                ModelVersion.prediction_stage,
                ModelVersion.model_version,
            )
        ).all()
        return ModelCatalog(items=[self.entry(model) for model in models])

    def _stage_model(self, version):
        stages = [stage for stage, known in MODEL_VERSIONS.items() if known == version]
        if not stages:
            raise ApplicationError(
                409,
                "INCOMPATIBLE_STAGE_MODEL",
                "Only a registered B1 stage model supports this operation.",
            )
        return self.register_stage(stages[0])

    def validate_model(self, version, student_id, actor):
        try:
            actor = UserService(self.db)._administrator(actor)
            model = self._stage_model(version)
            service = OutcomePredictionService(self.db)
            student = service._student(student_id)
            assembly = assemble(student, model.prediction_stage)
            if not assembly.ready:
                raise ApplicationError(
                    409,
                    "PREDICTION_NOT_READY",
                    "Integration validation needs a real student with complete stage inputs.",
                    {
                        "prediction_stage": model.prediction_stage.value,
                        "missing_features": assembly.missing_features,
                        "invalid_features": assembly.invalid_features,
                    },
                )
            runtime = OutcomeRuntime(
                *verify(
                    model.prediction_stage, root=Path(get_settings().ml_outcome_root)
                )
            )
            probe = service.build_prediction(
                student, assembly, runtime, model, actor.id
            )
            # Exercise actual database persistence and the unchanged warning rule,
            # then roll back the probe without any academic decision/history entry.
            with self.db.begin_nested() as transaction:
                self.repository.add_prediction(probe)
                warning_created = service._add_warning_for_prediction(probe)
                transaction.rollback()
            record = ModelValidation(
                model_version_id=model.id,
                artifact_sha256=runtime.manifest["artifact_sha256"],
                student_id=student.id,
                validated_by=actor.id,
                checks={
                    "verified_inference": True,
                    "prediction_insert": True,
                    "warning_transaction": True,
                    "rolled_back_probe": True,
                    "database_dialect": self.db.get_bind().dialect.name,
                    "predicted_outcome": probe.predicted_outcome.value,
                    "class_probabilities": probe.class_probabilities,
                    "risk_level": probe.risk_level.value,
                    "warning_created": warning_created,
                },
            )
            self.db.add(record)
            self.db.commit()
            return self.entry(model)
        except Exception:
            self.db.rollback()
            raise

    def activate_model(self, version, actor):
        try:
            actor = UserService(self.db)._administrator(actor)
            model = self._stage_model(version)
            # Fresh verification at activation, rather than trusting an old process cache.
            _, _, _, manifest = verify(
                model.prediction_stage, root=Path(get_settings().ml_outcome_root)
            )
            validation = self._validation(model, manifest["artifact_sha256"])
            required = (
                "verified_inference",
                "prediction_insert",
                "warning_transaction",
                "rolled_back_probe",
            )
            if validation is None or not all(
                validation.checks.get(key) is True for key in required
            ):
                raise ApplicationError(
                    409,
                    "MODEL_VALIDATION_REQUIRED",
                    "Validate this exact artifact with a real stage-ready student before activation.",
                )
            previous = self.repository.get_active_model(
                stage=model.prediction_stage,
                target_type=ModelTargetType.MULTICLASS_OUTCOME,
            )
            if previous is None or previous.id != model.id:
                self.repository.activate_only(model)
                self.db.add(
                    ModelActivationEvent(
                        model_version_id=model.id,
                        previous_model_id=previous.id if previous else None,
                        validation_id=validation.id,
                        acted_by=actor.id,
                        action="ACTIVATED",
                    )
                )
            self.db.commit()
            return self.entry(model)
        except Exception:
            self.db.rollback()
            raise


def json_manifest(path):
    import json

    try:
        return json.loads(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise ApplicationError(
            503,
            "MODEL_ARTIFACT_UNAVAILABLE",
            "The legacy model manifest is unavailable.",
        ) from exc
