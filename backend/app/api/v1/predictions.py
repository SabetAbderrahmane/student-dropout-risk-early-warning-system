from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.permissions import require_roles
from app.db.session import get_db
from app.models.prediction import RiskLevel
from app.models.user import User, UserRole
from app.schemas.prediction import (
    BatchPredictionResponse,
    PredictionDetail,
    PredictionPage,
    PredictionReadiness,
)
from app.services.prediction_service import PredictionService

router = APIRouter(tags=["predictions"])

prediction_read_access = require_roles(
    UserRole.SYSTEM_ADMIN, UserRole.ACADEMIC_ADMIN, UserRole.ACADEMIC_ADVISOR
)
prediction_execute_access = require_roles(UserRole.ACADEMIC_ADMIN)


@router.get(
    "/students/{student_id}/prediction-readiness", response_model=PredictionReadiness
)
def prediction_readiness(
    student_id: UUID,
    _: User = Depends(prediction_read_access),
    db: Session = Depends(get_db),
) -> PredictionReadiness:
    return PredictionService(db).readiness(student_id)


@router.post(
    "/students/{student_id}/predictions",
    response_model=PredictionDetail,
    status_code=status.HTTP_201_CREATED,
)
def predict_student(
    student_id: UUID,
    current_user: User = Depends(prediction_execute_access),
    db: Session = Depends(get_db),
) -> PredictionDetail:
    return PredictionService(db).predict_student(student_id, created_by=current_user.id)


@router.get("/students/{student_id}/predictions", response_model=PredictionPage)
def student_prediction_history(
    student_id: UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    _: User = Depends(prediction_read_access),
    db: Session = Depends(get_db),
) -> PredictionPage:
    return PredictionService(db).student_history(
        student_id, page=page, page_size=page_size
    )


@router.post("/predictions/batch", response_model=BatchPredictionResponse)
def predict_batch(
    current_user: User = Depends(prediction_execute_access),
    db: Session = Depends(get_db),
) -> BatchPredictionResponse:
    return PredictionService(db).predict_batch(created_by=current_user.id)


@router.get("/predictions", response_model=PredictionPage)
def list_predictions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    search: str | None = Query(default=None, max_length=200),
    risk_level: RiskLevel | None = None,
    model_version: str | None = Query(default=None, max_length=150),
    student_id: UUID | None = None,
    sort: Literal[
        "predicted_at", "probability", "risk_level", "student_number", "model_version"
    ] = "predicted_at",
    order: Literal["asc", "desc"] = "desc",
    _: User = Depends(prediction_read_access),
    db: Session = Depends(get_db),
) -> PredictionPage:
    return PredictionService(db).list_predictions(
        page=page,
        page_size=page_size,
        search=search,
        risk_level=risk_level,
        model_version=model_version,
        student_id=student_id,
        sort=sort,
        order=order,
    )


@router.get("/predictions/{prediction_id}", response_model=PredictionDetail)
def get_prediction(
    prediction_id: UUID,
    _: User = Depends(prediction_read_access),
    db: Session = Depends(get_db),
) -> PredictionDetail:
    return PredictionService(db).get_prediction(prediction_id)
