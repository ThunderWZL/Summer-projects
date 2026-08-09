import sys

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
