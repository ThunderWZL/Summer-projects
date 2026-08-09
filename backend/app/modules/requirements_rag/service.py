from __future__ import annotations

import hashlib
import json
import re
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
from app.modules.requirements_rag.store import PersistentVectorStore, VectorStorePort


class CorpusNotReady(RuntimeError):
    """Manifest or derived corpus cannot be safely indexed yet."""


CorpusNotReadyError = CorpusNotReady


class RequirementsRagService:
    def __init__(
        self,
        store: VectorStorePort,
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
        corpus_fingerprint: str | None = None,
    ) -> IndexReport:
        if len(manifest_fingerprint) != 64:
            raise ValueError("manifest_fingerprint must be a SHA-256 hex digest")
        vectors = self.embedder.embed_documents([chunk.content for chunk in chunks])
        if len(vectors) != len(chunks):
            raise ValueError("embedding client returned a vector count mismatch")
        if any(len(vector) != self.embedder.dimension for vector in vectors):
            raise ValueError("embedding client returned a vector dimension mismatch")
        corpus_fingerprint = corpus_fingerprint or self._corpus_fingerprint(chunks)
        metadata = IndexMetadata(
            embedding_model=self.embedder.model,
            vector_dimension=self.embedder.dimension,
            manifest_fingerprint=manifest_fingerprint,
            corpus_fingerprint=corpus_fingerprint,
        )
        indexed, skipped, rebuilt = self.store.index(chunks, vectors, metadata)
        return IndexReport(
            indexed_chunks=indexed,
            skipped_duplicates=skipped,
            rebuilt=rebuilt,
            manifest_fingerprint=manifest_fingerprint,
            embedding_model=self.embedder.model,
            vector_dimension=self.embedder.dimension,
            corpus_fingerprint=corpus_fingerprint,
        )

    def search(self, query: RequirementQuery) -> list[Citation]:
        vector = self.embedder.embed_query(query.q)
        if self.embedder.dimension and len(vector) != self.embedder.dimension:
            raise ValueError("query embedding dimension does not match embedder")
        metadata_reader = getattr(self.store, "metadata", None)
        index_metadata = metadata_reader() if metadata_reader else None
        if index_metadata is not None:
            if index_metadata.embedding_model != self.embedder.model:
                raise ValueError("query embedder model does not match stored index")
            if len(vector) != index_metadata.vector_dimension:
                raise ValueError("query embedding dimension does not match stored index")
        chunks = self.store.search(vector, 20)
        if query.as_of is not None:
            chunks = [
                chunk
                for chunk in chunks
                if chunk.effective_date is not None and chunk.effective_date <= query.as_of
            ]
        if not query.include_background:
            chunks = [chunk for chunk in chunks if chunk.source_level != "background"]
        chunks = chunks[: query.top_k or self.default_top_k]
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
            if source.extraction_status not in {"ready", "reviewed"}:
                raise CorpusNotReady(f"{source.document_id}: extraction status {source.extraction_status}")
            if not source.local_path:
                raise CorpusNotReady(f"{source.document_id}: local_path is required")
            for field_name in ("source_pdf_sha256", "derived_text_sha256", "parser_version", "human_review_status"):
                if not getattr(source, field_name):
                    raise CorpusNotReady(f"{source.document_id}: {field_name} is required")
            if source.human_review_status not in {"reviewed", "approved"}:
                raise CorpusNotReady(f"{source.document_id}: human review is not complete")
            content_path = Path(source.local_path)
            if not content_path.is_absolute():
                content_path = path.parent / content_path
            if not content_path.exists():
                raise CorpusNotReady(f"{source.document_id}: corpus file is missing")
            pages = self._load_pages(content_path, source.document_id)
            normalized_content = "\n".join(page.content.strip() for page in pages)
            derived_hash = hashlib.sha256(normalized_content.encode("utf-8")).hexdigest()
            if derived_hash != source.derived_text_sha256:
                raise CorpusNotReady(f"{source.document_id}: derived text hash mismatch")
            from app.domain.requirements_rag import RequirementDocument

            chunks.extend(
                chunker.split(
                    RequirementDocument(
                        document_id=source.document_id,
                        title=source.title,
                        standard_no=source.standard_no,
                        source_url=source.source_url,
                        effective_date=source.effective_date,
                        pages=pages,
                        extraction_status="ready",
                        source_pdf_sha256=source.source_pdf_sha256,
                        parser_version=source.parser_version,
                        derived_text_sha256=source.derived_text_sha256,
                        human_review_status=source.human_review_status,
                        source_level=source.source_level,
                        role=source.role,
                    )
                )
            )
        if not chunks:
            raise CorpusNotReady("manifest yielded no verified chunks")
        return self.index(
            chunks,
            manifest_fingerprint=manifest_fingerprint(sources),
            corpus_fingerprint=self._corpus_fingerprint(chunks),
        )

    @staticmethod
    def _load_pages(path: Path, document_id: str):
        from app.domain.requirements_rag import RequirementPage

        try:
            if path.suffix.lower() == ".json":
                payload = json.loads(path.read_text(encoding="utf-8"))
                raw_pages = payload.get("pages") if isinstance(payload, dict) else payload
                pages = [RequirementPage.model_validate(item) for item in raw_pages]
            else:
                raw_pages = path.read_text(encoding="utf-8").split("\f")
                pages = [RequirementPage(pdf_page=index, content=text) for index, text in enumerate(raw_pages, 1)]
        except (UnicodeDecodeError, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise CorpusNotReady(f"{document_id}: corpus pagination is unreadable") from exc
        if not pages or any(not page.content.strip() for page in pages):
            raise CorpusNotReady(f"{document_id}: corpus contains blank pages")
        if any("�" in page.content for page in pages):
            raise CorpusNotReady(f"{document_id}: corpus contains replacement characters")
        return pages

    @staticmethod
    def _corpus_fingerprint(chunks: Sequence[RequirementChunk]) -> str:
        payload = "\n".join(
            f"{chunk.document_id}|{chunk.content_hash}|{chunk.pdf_page}|{chunk.content}"
            for chunk in sorted(chunks, key=lambda item: (item.document_id, item.chunk_id))
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _citation(chunk: RequirementChunk) -> Citation:
        if chunk.printed_page is not None:
            section = f"{chunk.clause}；标准印刷页{chunk.printed_page}（PDF第{chunk.pdf_page}页）"
        else:
            section = f"{chunk.clause}；PDF第{chunk.pdf_page}页"
        return Citation(
            document_title=chunk.title,
            standard_no=chunk.standard_no,
            section=section,
            effective_date=chunk.effective_date.isoformat() if chunk.effective_date else None,
            source_url=chunk.source_url,
            excerpt=chunk.content,
        )
