import os
from collections.abc import Generator

os.environ.setdefault(
    "JWT_SECRET_KEY", "test-secret-key-that-is-at-least-32-characters-long"
)
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("ML_MODEL_PATH", "app/ml/artifacts/dropout-risk-v1/model.joblib")
os.environ.setdefault(
    "ML_METADATA_PATH", "app/ml/model_registry/dropout-risk-v1/metadata.json"
)
os.environ.setdefault(
    "ML_EVALUATION_PATH", "app/ml/model_registry/dropout-risk-v1/evaluation.json"
)

import pytest
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import User, UserRole
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture(scope="session")
def verified_model_fixture(tmp_path_factory):
    """Fit a small real pipeline locally; routine tests never need UCI or a personal artifact."""
    import json

    import joblib
    import pandas as pd
    from app.ml.deployment import DEFAULT_REGISTRY, write_manifest
    from app.ml.training.artifact import build_bundle
    from app.ml.training.modeling import candidate_definitions

    from tests.ml.test_training_pipeline import _synthetic_features

    directory = tmp_path_factory.mktemp("verified-model")
    for name in ("metadata.json", "evaluation.json", "split_manifest.json"):
        (directory / name).write_bytes((DEFAULT_REGISTRY / name).read_bytes())
    metadata = json.loads((directory / "metadata.json").read_bytes())
    X = _synthetic_features()
    y = pd.Series([0, 1] * 50)
    pipeline = candidate_definitions(y)["Logistic Regression"][0]
    pipeline.set_params(**metadata["selected_hyperparameters"]).fit(X, y)
    bundle = build_bundle(
        pipeline,
        model_name=metadata["model_name"],
        model_version=metadata["model_version"],
        low_threshold=metadata["thresholds"]["low_threshold"],
        high_threshold=metadata["thresholds"]["high_threshold"],
        X_development=X,
    )
    joblib.dump(bundle, directory / "model.joblib")
    write_manifest(directory / "model.joblib", directory)
    return directory


@pytest.fixture(autouse=True)
def isolated_model_runtime(request, monkeypatch, verified_model_fixture):
    from app.core.config import get_settings
    from app.ml.runtime import reset_model_runtime

    settings = get_settings()
    reset_model_runtime()
    if request.node.get_closest_marker("model_integration") is None:
        for field, name in (
            ("ml_model_path", "model.joblib"),
            ("ml_metadata_path", "metadata.json"),
            ("ml_evaluation_path", "evaluation.json"),
            ("ml_manifest_path", "artifact_manifest.json"),
        ):
            monkeypatch.setattr(settings, field, str(verified_model_fixture / name))
    yield
    reset_model_runtime()


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, _) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    TestingSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )
    Base.metadata.create_all(engine)

    with TestingSessionLocal() as session:
        yield session

    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def create_user(db_session: Session):
    def factory(
        *,
        username: str,
        role: UserRole,
        password: str = "CorrectHorseBatteryStaple!",
        is_active: bool = True,
    ) -> User:
        user = User(
            username=username,
            email=f"{username}@example.edu",
            password_hash=hash_password(password),
            full_name=f"{username.replace('_', ' ').title()} User",
            role=role,
            is_active=is_active,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return factory


@pytest.fixture()
def auth_headers(client: TestClient):
    def factory(
        username: str, password: str = "CorrectHorseBatteryStaple!"
    ) -> dict[str, str]:
        response = client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        assert response.status_code == 200
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    return factory
