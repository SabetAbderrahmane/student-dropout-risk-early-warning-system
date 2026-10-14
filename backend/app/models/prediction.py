from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.ml.outcomes.contracts import AcademicOutcome, ModelTargetType, PredictionStage

if TYPE_CHECKING:
    from app.models.student import Student
    from app.models.user import User

JSON_TYPE = JSON().with_variant(JSONB, "postgresql")

# PostgreSQL independently validates persisted class probabilities. SQLite unit
# tests exercise the same contract through Pydantic/runtime validation.
CLASS_PROBABILITY_CHECK = """
class_probabilities IS NULL OR CASE WHEN
jsonb_typeof(class_probabilities) = 'object' AND
class_probabilities - 'DROPOUT' - 'ENROLLED' - 'GRADUATE' = '{}'::jsonb AND
jsonb_typeof(class_probabilities->'DROPOUT') = 'number' AND
jsonb_typeof(class_probabilities->'ENROLLED') = 'number' AND
jsonb_typeof(class_probabilities->'GRADUATE') = 'number'
THEN
(class_probabilities->>'DROPOUT')::double precision BETWEEN 0 AND 1 AND
(class_probabilities->>'ENROLLED')::double precision BETWEEN 0 AND 1 AND
(class_probabilities->>'GRADUATE')::double precision BETWEEN 0 AND 1 AND
abs((class_probabilities->>'DROPOUT')::double precision +
    (class_probabilities->>'ENROLLED')::double precision +
    (class_probabilities->>'GRADUATE')::double precision - 1) <= 0.000001 AND
abs((class_probabilities->>'DROPOUT')::double precision - probability) <= 0.000000000001 AND
predicted_outcome = CASE
WHEN (class_probabilities->>'DROPOUT')::double precision >= (class_probabilities->>'ENROLLED')::double precision
 AND (class_probabilities->>'DROPOUT')::double precision >= (class_probabilities->>'GRADUATE')::double precision THEN 'DROPOUT'
WHEN (class_probabilities->>'ENROLLED')::double precision >= (class_probabilities->>'GRADUATE')::double precision THEN 'ENROLLED'
ELSE 'GRADUATE' END
ELSE FALSE END
"""


def contract_enum(kind):
    return Enum(
        kind,
        native_enum=False,
        length=32,
        values_callable=lambda cls: [item.value for item in cls],
    )


class RiskLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ModelVersion(Base):
    __tablename__ = "model_versions"
    __table_args__ = (
        CheckConstraint(
            "low_threshold >= 0 AND low_threshold < high_threshold",
            name="thresholds_ordered",
        ),
        CheckConstraint("high_threshold <= 1", name="high_threshold_maximum"),
        Index(
            "uq_model_versions_one_active_per_scope",
            "prediction_stage",
            "model_target_type",
            unique=True,
            postgresql_where=text("is_active"),
            sqlite_where=text("is_active = 1"),
        ),
        UniqueConstraint(
            "id",
            "prediction_stage",
            "model_target_type",
            name="uq_model_versions_prediction_contract",
        ),
        CheckConstraint(
            "prediction_stage IN ('ENROLLMENT', 'FIRST_SEMESTER')",
            name="prediction_stage_valid",
        ),
        CheckConstraint(
            "model_target_type IN ('BINARY_DROPOUT', 'MULTICLASS_OUTCOME')",
            name="model_target_type_valid",
        ),
        CheckConstraint(
            "model_target_type <> 'BINARY_DROPOUT' OR prediction_stage = 'FIRST_SEMESTER'",
            name="binary_stage_compatible",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    model_name: Mapped[str] = mapped_column(String(100))
    model_version: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    feature_schema_version: Mapped[str] = mapped_column(String(150))
    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    low_threshold: Mapped[float] = mapped_column(Float)
    high_threshold: Mapped[float] = mapped_column(Float)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON_TYPE)
    artifact_path: Mapped[str] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", index=True
    )
    prediction_stage: Mapped[PredictionStage] = mapped_column(
        contract_enum(PredictionStage),
        default=PredictionStage.FIRST_SEMESTER,
        server_default="FIRST_SEMESTER",
    )
    model_target_type: Mapped[ModelTargetType] = mapped_column(
        contract_enum(ModelTargetType),
        default=ModelTargetType.BINARY_DROPOUT,
        server_default="BINARY_DROPOUT",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    predictions: Mapped[list[PredictionResult]] = relationship(
        back_populates="model_version"
    )


class PredictionResult(Base):
    __tablename__ = "prediction_results"
    __table_args__ = (
        Index("ix_predictions_student_stage", "student_id", "prediction_stage"),
        Index(
            "ix_predictions_student_model_latest",
            "student_id",
            "model_version_id",
            text("predicted_at DESC"),
            text("id DESC"),
        ),
        Index(
            "ix_predictions_student_latest",
            "student_id",
            text("predicted_at DESC"),
            text("id DESC"),
        ),
        CheckConstraint(
            "probability >= 0 AND probability <= 1", name="probability_range"
        ),
        UniqueConstraint(
            "id",
            "student_id",
            "risk_level",
            name="uq_prediction_results_warning_identity",
        ),
        ForeignKeyConstraint(
            ["model_version_id", "prediction_stage", "model_target_type"],
            [
                "model_versions.id",
                "model_versions.prediction_stage",
                "model_versions.model_target_type",
            ],
            name="fk_prediction_results_model_contract_model_versions",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "prediction_stage IN ('ENROLLMENT', 'FIRST_SEMESTER')",
            name="prediction_stage_valid",
        ),
        CheckConstraint(
            "model_target_type IN ('BINARY_DROPOUT', 'MULTICLASS_OUTCOME')",
            name="model_target_type_valid",
        ),
        CheckConstraint(
            "predicted_outcome IS NULL OR predicted_outcome IN ('DROPOUT', 'ENROLLED', 'GRADUATE')",
            name="predicted_outcome_valid",
        ),
        CheckConstraint(
            "(model_target_type = 'BINARY_DROPOUT' AND prediction_stage = 'FIRST_SEMESTER' AND predicted_outcome IS NULL AND class_probabilities IS NULL) OR (model_target_type = 'MULTICLASS_OUTCOME' AND predicted_outcome IS NOT NULL AND class_probabilities IS NOT NULL)",
            name="classification_fields_compatible",
        ),
        CheckConstraint(
            CLASS_PROBABILITY_CHECK, name="class_probabilities_valid"
        ).ddl_if(dialect="postgresql"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="RESTRICT"), index=True
    )
    model_version_id: Mapped[uuid.UUID] = mapped_column(index=True)
    prediction_stage: Mapped[PredictionStage] = mapped_column(
        contract_enum(PredictionStage),
        default=PredictionStage.FIRST_SEMESTER,
        server_default="FIRST_SEMESTER",
        index=True,
    )
    model_target_type: Mapped[ModelTargetType] = mapped_column(
        contract_enum(ModelTargetType),
        default=ModelTargetType.BINARY_DROPOUT,
        server_default="BINARY_DROPOUT",
    )
    predicted_outcome: Mapped[AcademicOutcome | None] = mapped_column(
        contract_enum(AcademicOutcome), nullable=True
    )
    class_probabilities: Mapped[dict[str, float] | None] = mapped_column(
        JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), "postgresql"),
        nullable=True,
    )
    probability: Mapped[float] = mapped_column(Float)
    risk_level: Mapped[RiskLevel] = mapped_column(
        Enum(
            RiskLevel,
            name="risk_level",
            values_callable=lambda enum_class: [item.value for item in enum_class],
        ),
        index=True,
    )
    feature_snapshot: Mapped[dict[str, int | float]] = mapped_column(JSON_TYPE)
    explanation: Mapped[list[dict[str, Any]]] = mapped_column(JSON_TYPE)
    predicted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    student: Mapped[Student] = relationship()
    model_version: Mapped[ModelVersion] = relationship(back_populates="predictions")
    creator: Mapped[User | None] = relationship()


class ModelValidation(Base):
    __tablename__ = "model_validations"
    __table_args__ = (
        CheckConstraint("length(artifact_sha256) = 64", name="artifact_sha256_length"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    model_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("model_versions.id", ondelete="RESTRICT"), index=True
    )
    artifact_sha256: Mapped[str] = mapped_column(String(64))
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="RESTRICT")
    )
    validated_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    checks: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE)
    validated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ModelActivationEvent(Base):
    __tablename__ = "model_activation_events"
    __table_args__ = (
        CheckConstraint(
            "action IN ('MIGRATED_ACTIVE', 'ACTIVATED')", name="action_valid"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    model_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("model_versions.id", ondelete="RESTRICT"), index=True
    )
    previous_model_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("model_versions.id", ondelete="RESTRICT"), nullable=True
    )
    validation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("model_validations.id", ondelete="RESTRICT"), nullable=True
    )
    acted_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
