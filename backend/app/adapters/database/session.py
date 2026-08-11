from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.adapters.database.models import Base


def create_database_engine(database_url: str, *, echo: bool = False) -> Engine:
    """Create an engine; SQLite connections enforce foreign keys.

    ``database_url`` is passed to SQLAlchemy unchanged. Connection and driver
    errors propagate to the caller; this function does not create the schema.
    """
    connect_args = (
        {"check_same_thread": False}
        if database_url.startswith("sqlite")
        else {}
    )
    engine = create_engine(
        database_url,
        echo=echo,
        connect_args=connect_args,
    )
    if database_url.startswith("sqlite"):
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    return engine


def _enable_sqlite_foreign_keys(
    connection: sqlite3.Connection, connection_record: object
) -> None:
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Bind the shared session factory to ``engine`` without opening a session.

    Callers own session lifetime unless they use ``session_scope``. SQLAlchemy
    configuration errors propagate unchanged.
    """
    return sessionmaker(
        bind=engine,
        class_=Session,
        expire_on_commit=False,
    )


def initialize_schema(engine: Engine) -> None:
    """Create the initial schema in a new database.

    This is bootstrap-only. ``create_all`` may create missing tables but cannot
    migrate or validate an existing schema; after the D-09 freeze callers must
    not use it as a schema upgrade mechanism. DDL errors propagate unchanged.
    """
    Base.metadata.create_all(engine)


@contextmanager
def session_scope(
    session_factory: sessionmaker[Session],
) -> Iterator[Session]:
    """Commit one unit of work, or roll it back and re-raise on any exception."""
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
