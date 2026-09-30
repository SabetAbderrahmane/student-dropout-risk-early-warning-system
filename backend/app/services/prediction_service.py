from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.ml.feature_schema import PREDICTION_FEATURES
from app.ml.inference_features import FeatureAssembly, assemble_prediction_features
from app.ml.runtime import ModelRuntime, get_model_runtime
from app.models.prediction import ModelVersion, PredictionResult, RiskLevel
from app.models.student import Student
from app.repositories.prediction_repository import PredictionRepository
from app.schemas.prediction import (
    BatchPredictionResponse,
    CurrentModelResponse,
    DatasetSummary,
    ModelPerformanceResponse,
    PredictionDetail,
    PredictionPage,
    PredictionReadiness,
    PredictionResponse,
)


class PredictionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = PredictionRepository(db)

    def _student(self, student_id: UUID) -> Student:
        student = self.repository.get_student_graph(student_id)
        if student is None:
            raise ApplicationError(
                404, "STUDENT_NOT_FOUND", "The requested student does not exist."
            )
        return student

    @staticmethod
    def _readiness(assembly: FeatureAssembly) -> PredictionReadiness:
        required = len(PREDICTION_FEATURES)
        return PredictionReadiness(
            status="READY" if assembly.ready else "NOT_READY",
            required_feature_count=required,
            available_feature_count=required - len(assembly.missing_features),
            missing_features=list(assembly.missing_features),
        )

    def readiness(self, student_id: UUID) -> PredictionReadiness:
        return self._readiness(assemble_prediction_features(self._student(student_id)))

    def synchronize_registry(self, runtime: ModelRuntime | None = None) -> ModelVersion:
        runtime = runtime or get_model_runtime()
        metadata = runtime.metadata
        thresholds = metadata["thresholds"]
        existing = self.repository.get_model_by_version(metadata["model_version"])
        frozen = {
            "model_name": metadata["model_name"],
            "feature_schema_version": metadata["feature_schema_version"],
            "low_threshold": thresholds["low_threshold"],
            "high_threshold": thresholds["high_threshold"],
            "metrics": metadata["final_test_metrics"],
            "metadata_json": metadata,
            "artifact_path": metadata["artifact_path"],
        }
        if existing is None:
            existing = ModelVersion(
                model_version=metadata["model_version"],
                trained_at=datetime.fromisoformat(metadata["trained_at"]),
                is_active=False,
                **frozen,
            )
            self.repository.add_model(existing)
        else:
            conflicts = [
                key for key, value in frozen.items() if getattr(existing, key) != value
            ]
            expected_trained_at = datetime.fromisoformat(metadata["trained_at"])
            actual_trained_at = existing.trained_at
            if actual_trained_at.tzinfo is None:
                actual_trained_at = actual_trained_at.replace(tzinfo=timezone.utc)
            if actual_trained_at != expected_trained_at or conflicts:
                self.db.rollback()
                raise ApplicationError(
                    503,
                    "MODEL_REGISTRY_MISMATCH",
                    "The persisted model version conflicts with its tracked registry record.",
                )
        self.repository.activate_only(existing)
        self.db.commit()
        self.db.refresh(existing)
        return existing

    def _build_prediction(
        self,
        *,
        student: Student,
        assembly: FeatureAssembly,
        runtime: ModelRuntime,
        model: ModelVersion,
        created_by: UUID | None,
    ) -> PredictionResult:
        row = assembly.dataframe().loc[:, list(runtime.feature_names)]
        probability = runtime.predict_probability(row)
        explanation = runtime.explain(row, top_k=5)
        return PredictionResult(
            student_id=student.id,
            model_version_id=model.id,
            probability=probability,
            risk_level=RiskLevel(runtime.classify(probability)),
            feature_snapshot={
                name: assembly.values[name] for name in runtime.feature_names
            },
            explanation=explanation,
            predicted_at=datetime.now(timezone.utc),
            created_by=created_by,
        )

    @staticmethod
    def _summary(prediction: PredictionResult) -> PredictionResponse:
        return PredictionResponse(
            id=prediction.id,
            student_id=prediction.student_id,
            student_number=prediction.student.student_number,
            student_name=prediction.student.name,
            probability=prediction.probability,
            risk_level=prediction.risk_level,
            model_version=prediction.model_version.model_version,
            top_explanation_factors=prediction.explanation,
            predicted_at=prediction.predicted_at,
        )

    def predict_student(
        self, student_id: UUID, *, created_by: UUID
    ) -> PredictionDetail:
        student = self._student(student_id)
        assembly = assemble_prediction_features(student)
        readiness = self._readiness(assembly)
        if not assembly.ready:
            raise ApplicationError(
                409,
                "PREDICTION_NOT_READY",
                "The student does not have all required prediction features.",
                readiness.model_dump(),
            )
        runtime = get_model_runtime()
        model = self.synchronize_registry(runtime)
        prediction = self._build_prediction(
            student=student,
            assembly=assembly,
            runtime=runtime,
            model=model,
            created_by=created_by,
        )
        self.repository.add_prediction(prediction)
        self.db.commit()
        return self.get_prediction(prediction.id)

    def predict_batch(self, *, created_by: UUID) -> BatchPredictionResponse:
        runtime = get_model_runtime()
        model = self.synchronize_registry(runtime)
        students = self.repository.list_student_graphs()
        created = 0
        skipped = 0
        for student in students:
            assembly = assemble_prediction_features(student)
            if not assembly.ready:
                skipped += 1
                continue
            self.repository.add_prediction(
                self._build_prediction(
                    student=student,
                    assembly=assembly,
                    runtime=runtime,
                    model=model,
                    created_by=created_by,
                )
            )
            created += 1
        self.db.commit()
        return BatchPredictionResponse(
            assessed=created,
            skipped_not_ready=skipped,
            created_predictions=created,
            created_warnings=0,
            model_version=model.model_version,
            completed_at=datetime.now(timezone.utc),
        )

    def get_prediction(self, prediction_id: UUID) -> PredictionDetail:
        prediction = self.repository.get_prediction(prediction_id)
        if prediction is None:
            raise ApplicationError(
                404, "PREDICTION_NOT_FOUND", "The requested prediction does not exist."
            )
        summary = self._summary(prediction).model_dump()
        return PredictionDetail(
            **summary,
            feature_snapshot={
                name: prediction.feature_snapshot[name]
                for name in (item.name for item in PREDICTION_FEATURES)
            },
            explanation_method=prediction.model_version.metadata_json[
                "explanation_method"
            ],
            created_by=prediction.created_by,
        )

    def list_predictions(self, **kwargs: Any) -> PredictionPage:
        page = kwargs["page"]
        page_size = kwargs["page_size"]
        predictions, total = self.repository.list_predictions(**kwargs)
        return PredictionPage.create(
            items=[self._summary(item) for item in predictions],
            page=page,
            page_size=page_size,
            total=total,
        )

    def student_history(
        self, student_id: UUID, *, page: int, page_size: int
    ) -> PredictionPage:
        self._student(student_id)
        predictions, total = self.repository.list_student_history(
            student_id, page=page, page_size=page_size
        )
        return PredictionPage.create(
            items=[self._summary(item) for item in predictions],
            page=page,
            page_size=page_size,
            total=total,
        )

    def current_model(self) -> CurrentModelResponse:
        runtime = get_model_runtime()
        model = self.synchronize_registry(runtime)
        dataset = runtime.metadata["dataset"]
        return CurrentModelResponse(
            id=model.id,
            name=model.model_name,
            version=model.model_version,
            trained_at=model.trained_at,
            dataset=DatasetSummary(
                name=dataset["name"], dataset_id=dataset["dataset_id"]
            ),
            feature_schema_version=model.feature_schema_version,
            low_threshold=model.low_threshold,
            high_threshold=model.high_threshold,
            artifact_available=True,
        )

    def current_performance(self) -> ModelPerformanceResponse:
        runtime = get_model_runtime()
        self.synchronize_registry(runtime)
        final = runtime.evaluation["final_test"]
        return ModelPerformanceResponse(
            evaluation_scope=final["evaluation_scope"],
            sample_size=final["sample_size"],
            accuracy=final["accuracy"],
            precision=final["precision"],
            recall=final["recall"],
            f1=final["f1"],
            roc_auc=final["roc_auc"],
            pr_auc=final["pr_auc"],
            brier_score=final["brier_score"],
            confusion_matrix=final["confusion_matrix"],
            global_feature_importance=runtime.evaluation["global_feature_importance"],
        )
