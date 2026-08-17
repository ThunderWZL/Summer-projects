import sys
import types
from datetime import date

import pytest

from app.modules.requirements_rag.chroma import (
    ChromaDependencyUnavailable,
    ChromaVectorStore,
)


def test_chroma_dependency_is_not_imported_until_adapter_is_used(monkeypatch) -> None:
    assert "chromadb" not in sys.modules

    store = ChromaVectorStore("/tmp/siteppe-rag-test")
    assert store is not None

    def missing_chromadb(name: str):
        assert name == "chromadb"
        raise ImportError(name)

    monkeypatch.setattr("importlib.import_module", missing_chromadb)

    with pytest.raises(ChromaDependencyUnavailable):
        store.connect()


def test_chroma_metadata_connects_on_cold_start(monkeypatch) -> None:
    metadata = {
        "hnsw:space": "cosine",
        "embedding_model": "embed-v1",
        "vector_dimension": 8,
        "manifest_fingerprint": "a" * 64,
        "corpus_fingerprint": "b" * 64,
    }

    class Collection:
        def __init__(self):
            self.metadata = metadata

    collection = Collection()

    class Client:
        def __init__(self, path):
            self.path = path

        def get_or_create_collection(self, name, metadata):
            return collection

    fake_module = types.SimpleNamespace(PersistentClient=Client)
    monkeypatch.setattr("importlib.import_module", lambda name: fake_module)
    store = ChromaVectorStore("chroma_db")

    actual = store.metadata()

    assert actual is not None
    assert actual.embedding_model == "embed-v1"
    assert actual.vector_dimension == 8


def test_chroma_search_queries_all_rows_before_filtering_top_k() -> None:
    queried: dict[str, int] = {}

    def metadata_for(index: int, effective_date: str, level: str = "main") -> dict[str, object]:
        return {
            "chunk_id": f"chunk-{index}",
            "document_id": "fixture",
            "title": "Fixture",
            "standard_no": "GB TEST",
            "clause": f"第 {index} 条",
            "page": index,
            "pdf_page": index,
            "printed_page": "",
            "source_url": "https://example.test/fixture",
            "effective_date": effective_date,
            "content_hash": f"{index:064x}",
            "content": f"条款 {index}",
            "source_level": level,
            "role": "building_ppe",
        }

    metadatas = [metadata_for(index + 1, "2030-01-01") for index in range(21)]
    metadatas.append(metadata_for(22, "2024-01-01"))

    class Collection:
        metadata = {}

        def count(self):
            return len(metadatas)

        def query(self, *, query_embeddings, n_results):
            queried["n_results"] = n_results
            return {"metadatas": [metadatas[:n_results]]}

    store = ChromaVectorStore("chroma_db")
    store._collection = Collection()
    store._client = object()

    chunks = store.search(
        [0.0] * 8,
        1,
        as_of=date(2025, 1, 1),
        include_background=False,
    )

    assert queried["n_results"] == 22
    assert [chunk.content for chunk in chunks] == ["条款 22"]


def test_chroma_search_empty_collection_returns_without_querying() -> None:
    class Collection:
        metadata = {}

        def count(self):
            return 0

        def query(self, **kwargs):
            raise AssertionError("empty collections must not be queried")

    store = ChromaVectorStore("chroma_db")
    store._collection = Collection()
    store._client = object()

    assert store.search([0.0] * 8, 1) == []
