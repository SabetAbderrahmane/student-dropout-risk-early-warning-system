from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.permissions import require_roles, require_system_admin
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.prediction import (
    CurrentModelResponse,
    ModelCatalog,
    ModelCatalogEntry,
    ModelPerformanceResponse,
    ModelValidationRequest,
)
from app.services.model_catalog_service import ModelCatalogService
from app.services.prediction_service import PredictionService

router = APIRouter(prefix="/models", tags=["models"])

model_read_access = require_roles(
    UserRole.SYSTEM_ADMIN, UserRole.ACADEMIC_ADMIN, UserRole.ACADEMIC_ADVISOR
)


@router.get("/current", response_model=CurrentModelResponse)
def current_model(
    _: User = Depends(model_read_access),
    db: Session = Depends(get_db),
) -> CurrentModelResponse:
    return PredictionService(db).current_model()


@router.get("/current/performance", response_model=ModelPerformanceResponse)
def current_model_performance(
    _: User = Depends(model_read_access),
    db: Session = Depends(get_db),
) -> ModelPerformanceResponse:
    return PredictionService(db).current_performance()


@router.get("", response_model=ModelCatalog)
def model_catalog(_: User = Depends(model_read_access), db: Session = Depends(get_db)):
    return ModelCatalogService(db).catalog()


@router.post("/{model_version}/validate", response_model=ModelCatalogEntry)
def validate_model(
    model_version: str,
    payload: ModelValidationRequest,
    actor: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
):
    return ModelCatalogService(db).validate_model(
        model_version, payload.student_id, actor
    )


@router.post("/{model_version}/activate", response_model=ModelCatalogEntry)
def activate_model(
    model_version: str,
    actor: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
):
    return ModelCatalogService(db).activate_model(model_version, actor)
