from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.permissions import require_roles
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.prediction import CurrentModelResponse, ModelPerformanceResponse
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
