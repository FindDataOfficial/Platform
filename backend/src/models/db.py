"""SQLAlchemy engine + session factory (T007). PostgreSQL prod / SQLite dev."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker, declarative_base

from src.config import get_settings

settings = get_settings()

connect_args = {"check_same_thread": False} if settings.database_url.startswith(
    "sqlite"
) else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def db_session() -> Iterator[Session]:
    """Context manager for non-request code (agent loop, scheduler)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
