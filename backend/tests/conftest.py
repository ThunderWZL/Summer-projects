"""Force deterministic/offline adapters in the test suite.

``.env`` may carry real credentials (DEEPSEEK_API_KEY, EMBEDDING_API_KEY, …).
pydantic-settings reads the ``.env`` file after environment variables, so a bare
``delenv`` in a test still leaves the file value visible. Overriding with empty
strings keeps the runtime on its deterministic fallbacks and keeps tests offline.
"""

import os

import pytest

from app.config import get_settings

_OFFLINE_KEYS = (
    "DEEPSEEK_API_KEY",
    "EMBEDDING_API_KEY",
    "EMBEDDING_BASE_URL",
    "VLM_API_KEY",
    "VLM_API_BASE_URL",
)


@pytest.fixture(autouse=True, scope="session")
def _force_offline_ai_adapters() -> None:
    for key in _OFFLINE_KEYS:
        os.environ[key] = ""
    get_settings.cache_clear()
    yield
