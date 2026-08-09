from __future__ import annotations

import importlib
from datetime import date
from pathlib import Path
from typing import Any, Sequence

from app.domain.requirements_rag import IndexMetadata, RequirementChunk


class ChromaDependencyUnavailable(RuntimeError):
    """Raised only when a Chroma-backed index is explicitly requested."""


class ChromaVectorStore:
    """Chroma adapter with a deliberately lazy optional dependency import."""

    def __init__(self, path: str | Path, collection_name: str = "requirements") -> None:
        self.path = str(path)
        self.collection_name = collection_name
        self._client: Any = None
        self._collection: Any = None

    def connect(self, metadata: dict[str, Any] | None = None) -> Any:
        if self._client is None:
            try:
                chromadb = importlib.import_module("chromadb")
            except ImportError as exc:
                raise ChromaDependencyUnavailable(
                    "chromadb is required only for a real RAG index"
                ) from exc
            self._client = chromadb.PersistentClient(path=self.path)
        if self._collection is None:
            collection_metadata = {"hnsw:space": "cosine"}
            if metadata:
                collection_metadata.update(metadata)
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata=collection_metadata,
            )
        return self._collection

    def clear(self) -> None:
        if self._client is None:
            self.connect()
        self._client.delete_collection(self.collection_name)
        self._collection = None

    def metadata(self):
        if self._client is None:
            self.connect()
        collection = self.connect()
        values = collection.metadata or {}
        if "embedding_model" not in values:
            return None
        return IndexMetadata.model_validate(
            {key: values[key] for key in ("embedding_model", "vector_dimension", "manifest_fingerprint", "corpus_fingerprint")}
        )

    def index(
        self,
        chunks: Sequence[RequirementChunk],
        vectors: Sequence[Sequence[float]],
        metadata: IndexMetadata,
    ) -> tuple[int, int, bool]:
        metadata_json = metadata.model_dump(mode="json")
        collection = self.connect(metadata_json)
        current_metadata = collection.metadata or {}
        if any(str(current_metadata.get(key)) != str(value) for key, value in metadata_json.items()):
            self._client.delete_collection(self.collection_name)
            self._collection = None
            collection = self.connect(metadata_json)
            rebuilt = True
        else:
            rebuilt = False
        existing = collection.get(include=["metadatas"])
        hashes = {
            (str(item.get("document_id")), str(item.get("content_hash")))
            for item in (existing.get("metadatas") or [])
            if item
        }
        pending = [
            (chunk, vector)
            for chunk, vector in zip(chunks, vectors)
            if (chunk.document_id, chunk.content_hash) not in hashes
        ]
        skipped = len(chunks) - len(pending)
        if pending:
            collection.add(
                ids=[chunk.chunk_id for chunk, _ in pending],
                embeddings=[list(vector) for _, vector in pending],
                documents=[chunk.content for chunk, _ in pending],
                metadatas=[self._metadata(chunk) for chunk, _ in pending],
            )
        return len(pending), skipped, rebuilt

    def search(
        self,
        vector: Sequence[float],
        top_k: int | None,
        *,
        as_of=None,
        include_background: bool = False,
    ) -> list[RequirementChunk]:
        collection = self.connect()
        count = collection.count()
        if count == 0:
            return []
        result = collection.query(query_embeddings=[list(vector)], n_results=count)
        metadatas = (result.get("metadatas") or [[]])[0]
        chunks: list[RequirementChunk] = []
        for metadata in metadatas:
            if not metadata:
                continue
            data = dict(metadata)
            effective = data.get("effective_date")
            data["effective_date"] = date.fromisoformat(effective) if effective else None
            data["standard_no"] = data.get("standard_no") or None
            data["page"] = int(data["page"])
            data["pdf_page"] = int(data.get("pdf_page") or data["page"])
            data["printed_page"] = int(data["printed_page"]) if data.get("printed_page") else None
            chunk = RequirementChunk.model_validate(data)
            if as_of is not None and (chunk.effective_date is None or chunk.effective_date > as_of):
                continue
            if not include_background and chunk.source_level == "background":
                continue
            chunks.append(chunk)
        return chunks[:top_k] if top_k is not None else chunks

    @staticmethod
    def _metadata(chunk: RequirementChunk) -> dict[str, Any]:
        return {
            "chunk_id": chunk.chunk_id,
            "document_id": chunk.document_id,
            "title": chunk.title,
            "standard_no": chunk.standard_no or "",
            "clause": chunk.clause,
            "page": chunk.page,
            "pdf_page": chunk.pdf_page,
            "printed_page": chunk.printed_page or "",
            "source_url": chunk.source_url,
            "effective_date": chunk.effective_date.isoformat() if chunk.effective_date else "",
            "content_hash": chunk.content_hash,
            "content": chunk.content,
            "source_level": chunk.source_level,
            "role": chunk.role,
        }
