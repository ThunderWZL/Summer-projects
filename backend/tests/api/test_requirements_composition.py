from app.api import deps
from app.config import Settings
from app.modules.requirements_rag.chroma import ChromaVectorStore


def test_configured_embedding_uses_chroma_store(monkeypatch) -> None:
    selected: dict[str, object] = {}

    class FakeChroma:
        def __init__(self, path):
            selected["path"] = path

    monkeypatch.setattr(deps, "ChromaVectorStore", FakeChroma)
    monkeypatch.setattr(
        deps,
        "get_settings",
        lambda: Settings(
            embedding_api_key="secret",
            embedding_base_url="https://embedding.example/v1",
            embedding_model="embed-v1",
            chroma_path="chroma_db",
        ),
    )
    deps.get_requirement_retriever.cache_clear()
    try:
        retriever = deps.get_requirement_retriever()
    finally:
        deps.get_requirement_retriever.cache_clear()

    assert selected["path"] == "chroma_db"
    assert retriever.store.__class__.__name__ == "FakeChroma"
