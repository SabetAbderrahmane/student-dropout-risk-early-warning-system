from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_name: str = "student-dropout-warning-system"
    database_url: str = "postgresql+psycopg://user:password@localhost:5432/dropout_system"

    jwt_secret_key: str = Field(min_length=32)
    jwt_algorithm: Literal["HS256"] = "HS256"
    access_token_expire_minutes: int = Field(default=30, ge=1, le=1440)

    cors_origins: str = "http://localhost:3000"
    ml_model_path: str = "app/ml/artifacts/dropout-risk-v1/model.joblib"
    ml_metadata_path: str = "app/ml/model_registry/dropout-risk-v1/metadata.json"
    ml_evaluation_path: str = "app/ml/model_registry/dropout-risk-v1/evaluation.json"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
