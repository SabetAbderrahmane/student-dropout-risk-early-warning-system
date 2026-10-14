from collections.abc import Generator

from fastapi import Depends
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_read_db(db: Session = Depends(get_db)) -> Generator[Session, None, None]:
    """Independent repeatable PostgreSQL snapshot after normal authorization."""
    bind = db.get_bind()
    if bind.dialect.name != "postgresql":
        yield db
        return
    with Session(
        bind=bind.execution_options(isolation_level="REPEATABLE READ")
    ) as reader:
        reader.execute(text("SET TRANSACTION READ ONLY"))
        yield reader
