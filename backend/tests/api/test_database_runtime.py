from __future__ import annotations

import asyncio

import pytest

from app.api.deps import (
    get_case_store,
    initialize_database_runtime,
    shutdown_database_runtime,
)
from app.config import get_settings
from app.domain.case_store import CaseQuery
from app.main import app
from app.repositories import SqlAlchemyCaseStore


def test_application_lifespan_initializes_an_empty_sql_case_store(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        f"sqlite:///{tmp_path / 'runtime.db'}",
    )
    get_settings.cache_clear()
    shutdown_database_runtime()

    async def scenario() -> tuple[object, int]:
        async with app.router.lifespan_context(app):
            initialize_database_runtime()
            store = get_case_store()
            return store, store.list(CaseQuery()).total_items

    try:
        store, total_items = asyncio.run(scenario())
        assert isinstance(store, SqlAlchemyCaseStore)
        assert total_items == 0
    finally:
        shutdown_database_runtime()
        get_settings.cache_clear()
