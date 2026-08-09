from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.adapters.database.models import Base


def create_database_engine(database_url: str, *, echo: bool = False) -> Engine:
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
    return sessionmaker(
        bind=engine,
        class_=Session,
        expire_on_commit=False,
    )


def initialize_schema(engine: Engine) -> None:
    Base.metadata.create_all(engine)


@contextmanager
def session_scope(
    session_factory: sessionmaker[Session],
) -> Iterator[Session]:
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
