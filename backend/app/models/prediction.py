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
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.student import Student
    from app.models.user import User

JSON_TYPE = JSON().with_variant(JSONB, "postgresql")


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
            "uq_model_versions_one_active",
            "is_active",
            unique=True,
            postgresql_where=text("is_active"),
            sqlite_where=text("is_active = 1"),
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    predictions: Mapped[list[PredictionResult]] = relationship(
        back_populates="model_version"
    )


class PredictionResult(Base):
    __tablename__ = "prediction_results"
    __table_args__ = (
        CheckConstraint(
            "probability >= 0 AND probability <= 1", name="probability_range"
        ),
        UniqueConstraint(
            "id",
            "student_id",
            "risk_level",
            name="uq_prediction_results_warning_identity",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="RESTRICT"), index=True
    )
    model_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("model_versions.id", ondelete="RESTRICT"), index=True
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
