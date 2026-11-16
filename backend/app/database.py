
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, settings


def build_database_url(config: Settings) -> URL:
    if config.database_url:
        return make_url(config.database_url).set(
            drivername="postgresql+psycopg"
        )
    return URL.create(
        drivername="postgresql+psycopg",
        username=config.database_user,
        password=config.database_password,
        host=config.database_host,
        port=config.database_port,
        database=config.database_name,
    )


database_url = build_database_url(settings)

engine = create_engine(
    database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
)

SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """Provide a database session for one request."""
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
