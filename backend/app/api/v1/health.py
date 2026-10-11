from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import ApplicationError
from app.db.session import get_db
from app.ml.runtime import get_model_runtime
from app.schemas.common import HealthResponse
from app.services.prediction_service import PredictionService

router = APIRouter(tags=["health"])


@router.get("/health/live")
def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
def readiness(db: Session = Depends(get_db)) -> JSONResponse:
    database = {"status": "connected", "code": None}
    model = {"status": "ready", "code": None}
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        db.rollback()
        database = {"status": "unavailable", "code": "DATABASE_UNAVAILABLE"}
    try:
        runtime = get_model_runtime()
        if database["status"] == "connected":
            # A loaded binary alone cannot predict if the persisted registry conflicts.
            PredictionService(db).synchronize_registry(runtime)
    except ApplicationError as exc:
        model = {
            "status": "unavailable"
            if exc.code == "MODEL_ARTIFACT_UNAVAILABLE"
            else "mismatch",
            "code": exc.code,
        }
    except SQLAlchemyError:
        db.rollback()
        database = {"status": "unavailable", "code": "DATABASE_UNAVAILABLE"}
    ready = database["status"] == "connected" and model["status"] == "ready"
    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "ready" if ready else "not_ready",
            "database": database,
            "model": model,
        },
    )


@router.get("/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)) -> HealthResponse:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "DATABASE_UNAVAILABLE",
                "message": "Database connectivity check failed.",
            },
        ) from None

    return HealthResponse(
        status="ok",
        database="connected",
        app_name=get_settings().app_name,
    )
