from fastapi import APIRouter

from app.api.v1 import auth, health, imports, models, predictions, students

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(imports.router)
api_router.include_router(students.router)
api_router.include_router(predictions.router)
api_router.include_router(models.router)
