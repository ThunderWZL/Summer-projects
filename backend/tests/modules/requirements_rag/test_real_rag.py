import pytest

from app.config import get_settings


@pytest.mark.real_rag
def test_real_rag_requires_explicit_credentials() -> None:
    if not get_settings().embedding_api_key:
        pytest.skip("EMBEDDING_API_KEY is not configured")
