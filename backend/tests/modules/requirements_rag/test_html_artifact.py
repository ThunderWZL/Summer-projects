import hashlib
import json

from app.modules.requirements_rag.embedding import DeterministicEmbeddingClient
from app.modules.requirements_rag.service import RequirementsRagService
from app.modules.requirements_rag.store import PersistentVectorStore


def test_reviewed_html_corpus_uses_artifact_hash_not_pdf_hash(tmp_path) -> None:
    pages = [{"pdf_page": 1, "content": "重点劳动防护用品应按标准验收。"}]
    corpus = tmp_path / "normalized.json"
    corpus.write_text(json.dumps(pages, ensure_ascii=False), encoding="utf-8")
    derived = hashlib.sha256(pages[0]["content"].encode()).hexdigest()
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            [
                {
                    "document_id": "html-source",
                    "title": "HTML 来源",
                    "publisher": "发布机关",
                    "source_url": "https://example.test/source.html",
                    "publication_date": "2025-09-02",
                    "effective_date": None,
                    "status": "公开发布",
                    "hash_strategy": "sha256-normalized-html-main-node",
                    "local_path": "normalized.json",
                    "role": "enforcement_context",
                    "source_level": "background",
                    "extraction_status": "ready",
                    "source_artifact_sha256": "b" * 64,
                    "parser_version": "html-parser-1",
                    "derived_text_sha256": derived,
                    "human_review_status": "reviewed",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    service = RequirementsRagService(
        store=PersistentVectorStore(tmp_path / "index.json"),
        embedder=DeterministicEmbeddingClient(dimension=8),
    )

    report = service.index_documents(manifest)

    assert report.indexed_chunks == 1
