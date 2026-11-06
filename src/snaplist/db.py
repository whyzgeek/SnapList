"""Database setup: engine, session scope, and table creation.

A module-level engine is built from settings so the rest of the app can call
init_db() and session_scope() without threading Settings through every module.
Tests can override the engine via init_db(settings) to use a temp file.
"""
from __future__ import annotations

import contextlib
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import Settings, get_settings


class Base(DeclarativeBase):
    pass


_ENGINE = None
_SESSION = None


def _make_engine(settings: Settings):
    path = settings.db_path
    if path != ":memory:" and path:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    connect_args = {"check_same_thread": False} if path == ":memory:" else {}
    return create_engine(
        f"sqlite:///{path}" if path else "sqlite://",
        connect_args=connect_args, future=True,
    )


@contextlib.contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations."""
    global _SESSION
    if _SESSION is None:
        raise RuntimeError("database not initialized; call init_db() first")
    session = _SESSION()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db(settings: Settings | None = None) -> tuple:
    global _ENGINE, _SESSION
    settings = settings or get_settings()
    engine = _make_engine(settings)
    _ENGINE = engine
    _SESSION = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(engine)
    _add_missing_columns(engine)
    return engine, _SESSION


def _add_missing_columns(engine) -> None:
    """Tiny forward-only migration so existing SQLite files keep their data."""
    from sqlalchemy import inspect, text
    insp = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not insp.has_table(table.name):
                continue
            have = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name not in have:
                    ddl = col.type.compile(engine.dialect)
                    conn.execute(text(f'ALTER TABLE {table.name} ADD COLUMN {col.name} {ddl}'))


def set_session(sessionmaker) -> None:
    """Allow tests to point session_scope at an in-memory engine."""
    global _SESSION
    _SESSION = sessionmaker
