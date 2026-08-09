import sys
import types

import pytest

from app.modules.requirements_rag.chroma import (
    ChromaDependencyUnavailable,
    ChromaVectorStore,
)


def test_chroma_dependency_is_not_imported_until_adapter_is_used() -> None:
    assert "chromadb" not in sys.modules

    store = ChromaVectorStore("/tmp/siteppe-rag-test")
    assert store is not None
    if "chromadb" not in sys.modules:
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
