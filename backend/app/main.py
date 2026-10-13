import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import (
    ApplicationError,
    application_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from app.core.logging import configure_logging
from app.db.session import SessionLocal
from app.ml.runtime import initialize_model_runtime
from app.services.model_catalog_service import ModelCatalogService
from app.services.prediction_service import PredictionService

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    runtime = initialize_model_runtime()
    if runtime is not None:
        try:
            with SessionLocal() as db:
                PredictionService(db).synchronize_registry(runtime)
                ModelCatalogService(db).register_new_models()
        except (ApplicationError, SQLAlchemyError):
            logger.warning("Model registry startup synchronization was deferred.")
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(ApplicationError, application_exception_handler)
app.include_router(api_router, prefix="/api/v1")
