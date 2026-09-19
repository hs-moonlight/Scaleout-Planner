"""Database engine + session.

Local dev uses SQLite (default). In Azure, set DATABASE_URL to a PostgreSQL
connection string; `postgres://` / `postgresql://` are normalized to the
psycopg (v3) driver automatically. Nothing else in the app changes.
"""
from sqlmodel import SQLModel, create_engine, Session
from .config import settings


def _normalize(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


DATABASE_URL = _normalize(settings.database_url)
_is_sqlite = DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False} if _is_sqlite else {}
engine = create_engine(
    DATABASE_URL, echo=False,
    pool_pre_ping=not _is_sqlite,   # recover dropped cloud-DB connections
    connect_args=connect_args,
)


def init_db() -> None:
    from . import models  # noqa: F401  (register tables before create_all)
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
