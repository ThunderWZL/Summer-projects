from datetime import date
import json
import hashlib
import pytest

from app.domain.requirements_rag import RequirementChunk, RequirementQuery
from app.modules.requirements_rag.embedding import DeterministicEmbeddingClient
from app.modules.requirements_rag.service import RequirementsRagService
from app.modules.requirements_rag.store import PersistentVectorStore


def _chunk(chunk_id: str, content: str) -> RequirementChunk:
    import hashlib

    return RequirementChunk(
        chunk_id=chunk_id,
        document_id="fixture",
        title="施工 PPE 规范",
        standard_no="GB TEST",
        clause="第 3 条",
        page=1,
        source_url="https://example.test/fixture",
        effective_date=date(2025, 1, 1),
        content_hash=hashlib.sha256(content.encode()).hexdigest(),
        content=content,
    )


def test_fake_embedding_is_deterministic_and_fixed_dimension() -> None:
    embedder = DeterministicEmbeddingClient(model="fake-v1", dimension=8)

    first = embedder.embed_documents(["安全帽"])[0]
    second = embedder.embed_documents(["安全帽"])[0]

    assert first == second
    assert len(first) == 8
    assert embedder.embed_query("安全帽") == first


def test_service_indexes_searches_idempotently_and_rebuilds_on_model_change(tmp_path) -> None:
    store = PersistentVectorStore(tmp_path / "rag.json")
    service = RequirementsRagService(
        store=store,
        embedder=DeterministicEmbeddingClient(model="fake-v1", dimension=8),
    )
    chunks = [_chunk("one", "施工现场应佩戴安全帽。"), _chunk("two", "施工现场应佩戴防护手套。")]

    first = service.index(chunks, manifest_fingerprint="a" * 64)
    duplicate = service.index(chunks, manifest_fingerprint="a" * 64)
    citations = service.search(RequirementQuery(q="安全帽", top_k=1))

    assert first.indexed_chunks == 2
    assert duplicate.indexed_chunks == 0
    assert duplicate.skipped_duplicates == 2
    assert citations[0].document_title == "施工 PPE 规范"
    assert citations[0].section == "第 3 条；PDF第1页"
    assert citations[0].excerpt == "施工现场应佩戴安全帽。"

    rebuilt = RequirementsRagService(
        store=store,
        embedder=DeterministicEmbeddingClient(model="fake-v2", dimension=4),
    ).index(chunks, manifest_fingerprint="a" * 64)
    assert rebuilt.rebuilt is True
    assert rebuilt.embedding_model == "fake-v2"
    assert rebuilt.vector_dimension == 4


def test_service_can_delete_and_rebuild_index(tmp_path) -> None:
    store = PersistentVectorStore(tmp_path / "rag.json")
    service = RequirementsRagService(
        store=store,
        embedder=DeterministicEmbeddingClient(model="fake-v1", dimension=8),
    )
    chunks = [_chunk("one", "施工现场应佩戴安全鞋。")]

    service.index(chunks, manifest_fingerprint="b" * 64)
    assert service.search(RequirementQuery(q="安全鞋"))
    service.delete_index()
    assert service.search(RequirementQuery(q="安全鞋")) == []
    report = service.index(chunks, manifest_fingerprint="b" * 64)
    assert report.indexed_chunks == 1


def test_index_documents_reads_only_manifest_declared_static_files(tmp_path) -> None:
    text_path = tmp_path / "standard.json"
    text_path.write_text(
        json.dumps([{"pdf_page": 1, "printed_page": 1, "content": "第一条\n\n施工现场应佩戴安全帽。"}], ensure_ascii=False),
        encoding="utf-8",
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            [
                {
                    "document_id": "fixture",
                    "title": "Fixture",
                    "standard_no": "GB TEST",
                    "publisher": "Test authority",
                    "source_url": "https://example.test/fixture",
                        "effective_date": "2025-01-01",
                        "publication_date": "2025-01-01",
                    "status": "official",
                    "hash_strategy": "sha256-normalized-utf8-content",
                        "local_path": "standard.json",
                        "role": "building_ppe",
                        "source_level": "main",
                        "extraction_status": "ready",
                        "source_pdf_sha256": "a" * 64,
                        "parser_version": "fixture-parser-1",
                        "derived_text_sha256": hashlib.sha256("第一条\n\n施工现场应佩戴安全帽。".encode()).hexdigest(),
                        "human_review_status": "reviewed",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    service = RequirementsRagService(
        store=PersistentVectorStore(tmp_path / "rag.json"),
        embedder=DeterministicEmbeddingClient(dimension=8),
    )

    report = service.index_documents(manifest_path)

    assert report.indexed_chunks == 2
    assert service.search(RequirementQuery(q="安全帽"))[0].source_url == "https://example.test/fixture"


def test_search_can_filter_citations_by_effective_date(tmp_path) -> None:
    service = RequirementsRagService(
        store=PersistentVectorStore(tmp_path / "rag.json"),
        embedder=DeterministicEmbeddingClient(dimension=8),
    )
    service.index([_chunk("one", "施工现场应佩戴安全帽。")], manifest_fingerprint="d" * 64)

    assert service.search(RequirementQuery(q="安全帽", as_of=date(2024, 12, 31))) == []
    assert service.search(RequirementQuery(q="安全帽", as_of=date(2025, 1, 1)))


def test_index_rejects_incomplete_vectors_and_rebuilds_on_content_change(tmp_path) -> None:
    class BadEmbedder(DeterministicEmbeddingClient):
        def embed_documents(self, texts):
            return [vector[:-1] for vector in super().embed_documents(texts)]

    service = RequirementsRagService(
        store=PersistentVectorStore(tmp_path / "rag.json"),
        embedder=BadEmbedder(dimension=8),
    )
    with pytest.raises(ValueError, match="dimension"):
        service.index([_chunk("one", "安全帽")], manifest_fingerprint="e" * 64)

    store = PersistentVectorStore(tmp_path / "changed.json")
    good = RequirementsRagService(store=store, embedder=DeterministicEmbeddingClient(dimension=8))
    good.index([_chunk("one", "旧安全帽条款")], manifest_fingerprint="f" * 64)
    report = good.index([_chunk("one", "新安全帽条款")], manifest_fingerprint="f" * 64)
    assert report.rebuilt is True
    assert [citation.excerpt for citation in good.search(RequirementQuery(q="新安全帽条款"))] == ["新安全帽条款"]


def test_source_level_filter_happens_before_top_k_cutoff() -> None:
    background = _chunk("background", "背景条款").model_copy(update={"source_level": "background"})
    main = _chunk("main", "主证据").model_copy(update={"source_level": "main"})

    class OrderedStore:
        def index(self, chunks, vectors, metadata):
            return (0, 0, False)

        def search(self, vector, top_k, *, as_of=None, include_background=False):
            candidates = [background, main]
            if not include_background:
                candidates = [chunk for chunk in candidates if chunk.source_level != "background"]
            return candidates[:top_k] if top_k is not None else candidates

        def clear(self):
            pass

    service = RequirementsRagService(
        store=OrderedStore(),
        embedder=DeterministicEmbeddingClient(dimension=8),
    )

    citations = service.search(RequirementQuery(q="PPE", top_k=1))

    assert len(citations) == 1
    assert citations[0].excerpt == "主证据"


def test_search_rejects_embedder_model_mismatch(tmp_path) -> None:
    store = PersistentVectorStore(tmp_path / "model.json")
    RequirementsRagService(
        store=store,
        embedder=DeterministicEmbeddingClient(model="model-a", dimension=8),
    ).index([_chunk("one", "安全帽")], manifest_fingerprint="1" * 64)
    changed = RequirementsRagService(
        store=store,
        embedder=DeterministicEmbeddingClient(model="model-b", dimension=8),
    )

    with pytest.raises(ValueError, match="model"):
        changed.search(RequirementQuery(q="安全帽"))


def test_filtering_is_applied_inside_store_before_top_k_cutoff() -> None:
    future = [
        _chunk(f"future-{index}", f"未来条款{index}").model_copy(
            update={"source_level": "main", "effective_date": date(2030, 1, 1)}
        )
        for index in range(21)
    ]
    background = _chunk("background", "背景条款").model_copy(update={"source_level": "background"})
    valid = _chunk("valid", "已生效主证据").model_copy(update={"source_level": "main", "effective_date": date(2024, 1, 1)})

    class LimitedStore:
        def index(self, chunks, vectors, metadata):
            return (0, 0, False)

        def search(self, vector, top_k, *, as_of=None, include_background=False):
            candidates = [*future, background, valid]
            if as_of is not None:
                candidates = [chunk for chunk in candidates if chunk.effective_date and chunk.effective_date <= as_of]
            if not include_background:
                candidates = [chunk for chunk in candidates if chunk.source_level != "background"]
            return candidates[:top_k] if top_k is not None else candidates

        def clear(self):
            pass

    service = RequirementsRagService(
        store=LimitedStore(),
        embedder=DeterministicEmbeddingClient(dimension=8),
    )

    citations = service.search(RequirementQuery(q="PPE", top_k=1, as_of=date(2025, 1, 1)))

    assert [citation.excerpt for citation in citations] == ["已生效主证据"]
