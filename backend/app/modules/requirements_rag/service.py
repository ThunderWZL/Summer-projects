from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path

from app.contracts import Citation
from app.domain.requirements_rag import (
    IndexMetadata,
    IndexReport,
    RequirementChunk,
    RequirementQuery,
)
from app.modules.requirements_rag.embedding import EmbeddingClientPort
from app.modules.requirements_rag.chunker import RequirementChunker
from app.modules.requirements_rag.manifest import load_manifest, manifest_fingerprint
from app.modules.requirements_rag.store import PersistentVectorStore


class RequirementsRagService:
    def __init__(
        self,
        store: PersistentVectorStore,
        embedder: EmbeddingClientPort,
        default_top_k: int = 5,
    ) -> None:
        self.store = store
        self.embedder = embedder
        self.default_top_k = default_top_k

    def index(
        self,
        chunks: Sequence[RequirementChunk],
        *,
        manifest_fingerprint: str,
    ) -> IndexReport:
        if len(manifest_fingerprint) != 64:
            raise ValueError("manifest_fingerprint must be a SHA-256 hex digest")
        vectors = self.embedder.embed_documents([chunk.content for chunk in chunks])
        metadata = IndexMetadata(
            embedding_model=self.embedder.model,
            vector_dimension=self.embedder.dimension,
            manifest_fingerprint=manifest_fingerprint,
        )
        indexed, skipped, rebuilt = self.store.index(chunks, vectors, metadata)
        return IndexReport(
            indexed_chunks=indexed,
            skipped_duplicates=skipped,
            rebuilt=rebuilt,
            manifest_fingerprint=manifest_fingerprint,
            embedding_model=self.embedder.model,
            vector_dimension=self.embedder.dimension,
        )

    def search(self, query: RequirementQuery) -> list[Citation]:
        vector = self.embedder.embed_query(query.q)
        chunks = self.store.search(vector, query.top_k or self.default_top_k)
        if query.as_of is not None:
            chunks = [
                chunk
                for chunk in chunks
                if chunk.effective_date is None or chunk.effective_date <= query.as_of
            ]
        return [self._citation(chunk) for chunk in chunks]

    def delete_index(self) -> None:
        self.store.clear()

    def index_documents(self, manifest_path: str | Path) -> IndexReport:
        """Index only local static files declared by a source manifest."""
        path = Path(manifest_path)
        sources = load_manifest(path)
        chunks: list[RequirementChunk] = []
        chunker = RequirementChunker()
        for source in sources:
            if not source.local_path:
                continue
            content_path = Path(source.local_path)
            if not content_path.is_absolute():
                content_path = path.parent / content_path
            if not content_path.exists():
                continue
            content = content_path.read_text(encoding="utf-8")
            from app.domain.requirements_rag import RequirementDocument

            chunks.extend(
                chunker.split(
                    RequirementDocument(
                        document_id=source.document_id,
                        title=source.title,
                        standard_no=source.standard_no,
                        source_url=source.source_url,
                        effective_date=source.effective_date,
                        pages=[(1, content)],
                    )
                )
            )
        return self.index(chunks, manifest_fingerprint=manifest_fingerprint(sources))

    @staticmethod
    def _citation(chunk: RequirementChunk) -> Citation:
        return Citation(
            document_title=chunk.title,
            standard_no=chunk.standard_no,
            section=f"{chunk.clause}；标准印刷页{chunk.page}（PDF第{chunk.page}页）",
            effective_date=chunk.effective_date.isoformat() if chunk.effective_date else None,
            source_url=chunk.source_url,
            excerpt=chunk.content,
        )
