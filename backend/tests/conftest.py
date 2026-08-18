"""Force deterministic/offline adapters in the test suite.

``.env`` may carry real credentials (DEEPSEEK_API_KEY, EMBEDDING_API_KEY, …).
Tests disable dotenv loading and clear integration keys so local configuration
cannot select paid providers or change configuration assertions.
"""

import asyncio
import os

import pytest

from app.config import Settings, get_settings

try:
    import uvloop
except ImportError:  # pragma: no cover - uvloop is unavailable on Windows
    uvloop = None
else:
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

_OFFLINE_KEYS = (
    "DEEPSEEK_API_KEY",
    "EMBEDDING_API_KEY",
    "EMBEDDING_BASE_URL",
    "VLM_API_KEY",
    "VLM_API_BASE_URL",
)


@pytest.fixture(autouse=True, scope="session")
def _force_offline_ai_adapters() -> None:
    original_env_file = Settings.model_config.get("env_file")
    Settings.model_config["env_file"] = None
    for key in _OFFLINE_KEYS:
        os.environ[key] = ""
    os.environ["VLM_PROVIDER"] = "fixed"
    os.environ["VISION_PROVIDER"] = "fixture"
    get_settings.cache_clear()
    yield
    Settings.model_config["env_file"] = original_env_file
