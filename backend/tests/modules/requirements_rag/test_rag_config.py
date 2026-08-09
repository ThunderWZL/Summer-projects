from app.config import Settings


def test_rag_configuration_is_separate_from_vlm_configuration(monkeypatch) -> None:
    monkeypatch.setenv("EMBEDDING_API_KEY", "embedding-secret")
    monkeypatch.setenv("EMBEDDING_BASE_URL", "https://embedding.example/v1")
    monkeypatch.setenv("EMBEDDING_MODEL", "embedding-test")
    monkeypatch.setenv("CHROMA_PATH", "/tmp/rag-index")
    monkeypatch.setenv("RAG_TOP_K", "7")
    monkeypatch.delenv("VLM_API_KEY", raising=False)

    settings = Settings()

    assert settings.embedding_api_key == "embedding-secret"
    assert settings.embedding_base_url == "https://embedding.example/v1"
    assert settings.embedding_model == "embedding-test"
    assert settings.chroma_path == "/tmp/rag-index"
    assert settings.rag_top_k == 7
    assert settings.vlm_api_key is None
