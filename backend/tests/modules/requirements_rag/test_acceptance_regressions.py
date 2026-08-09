import json
from datetime import date

import pytest

from app.domain.requirements_rag import RequirementDocument, RequirementPage
from app.modules.requirements_rag.chunker import RequirementChunker
from app.modules.requirements_rag.manifest import load_manifest
from app.modules.requirements_rag.service import CorpusNotReady, RequirementsRagService
from app.modules.requirements_rag.embedding import DeterministicEmbeddingClient
from app.modules.requirements_rag.store import PersistentVectorStore


MANIFEST = "app/modules/requirements_rag/manifests/authoritative_sources.json"


def test_shipped_manifest_loads_with_real_provenance_metadata() -> None:
    sources = load_manifest(MANIFEST)

    assert len(sources) == 5
    assert next(item for item in sources if item.role == "enforcement_context").effective_date is None
    assert next(item for item in sources if item.document_id == "gb-39800-1-2020").source_pdf_sha256
    assert "国家市场监督管理总局" in next(item for item in sources if item.document_id == "gb-39800-12-2025").publisher
    assert next(item for item in sources if item.document_id == "gb-39800-12-2025").publication_date == date(2025, 6, 30)
    assert next(item for item in sources if item.document_id == "gb-39800-1-2020").publication_date == date(2020, 12, 24)
    assert next(item for item in sources if item.document_id == "gb-55034-2022").publication_date == date(2022, 10, 31)
    assert next(item for item in sources if item.document_id == "samr-ppe-enforcement-2025-77").publication_date == date(2025, 9, 2)
    assert len(load_manifest()) == 5


def test_table_rows_without第项_prefix_are_kept_separate() -> None:
    document = RequirementDocument(
        document_id="table",
        title="表1",
        source_url="https://example.test/table",
        pages=[
            RequirementPage(
                pdf_page=4,
                printed_page=2,
                content="1 钢筋人工搬运：机械手套\n2 转动机械/金属切割：眼面防护\n3 车辆作业：高可视服",
            )
        ],
    )

    chunks = RequirementChunker().split(document)

    assert len(chunks) == 3
    assert "机械手套" in chunks[0].content
    assert "机械手套" not in chunks[1].content
    assert chunks[1].pdf_page == 4
    assert chunks[1].printed_page == 2


def test_unprepared_manifest_is_not_reported_as_empty_success(tmp_path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            [
                {
                    "document_id": "not-ready",
                    "title": "未准备来源",
                    "publisher": "测试发布机关",
                    "source_url": "https://example.test/not-ready",
                    "publication_date": "2025-01-01",
                    "effective_date": None,
                    "status": "official",
                    "hash_strategy": "sha256-normalized-utf8-content",
                    "role": "building_ppe",
                    "source_level": "main",
                    "extraction_status": "not_downloaded",
                    "local_path": None,
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    service = RequirementsRagService(
        store=PersistentVectorStore(tmp_path / "index.json"),
        embedder=DeterministicEmbeddingClient(),
    )

    with pytest.raises(CorpusNotReady):
        service.index_documents(manifest)
