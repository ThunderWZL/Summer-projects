from datetime import date

import pytest

from app.modules.requirements_rag.chunker import RequirementChunker
from app.modules.requirements_rag.manifest import AUTHORITATIVE_SOURCES
from app.domain.requirements_rag import RequirementDocument


def test_manifest_contains_five_sources_with_non_overlapping_roles() -> None:
    assert len(AUTHORITATIVE_SOURCES) == 5
    assert {source.role for source in AUTHORITATIVE_SOURCES} == {
        "building_ppe",
        "general_ppe",
        "field_reference",
        "safety_general",
        "enforcement_context",
    }
    assert all(source.source_url.startswith("https://") for source in AUTHORITATIVE_SOURCES)
    assert all(source.hash_strategy for source in AUTHORITATIVE_SOURCES)
    levels = {source.document_id: source.source_level for source in AUTHORITATIVE_SOURCES}
    assert levels["gb-39800-12-2025"] == "main"
    assert levels["construction-worker-ppe-guide-2021"] == "supplemental"
    assert levels["samr-ppe-enforcement-2025-77"] == "background"
    assert next(source for source in AUTHORITATIVE_SOURCES if source.role == "field_reference").effective_date is None


def test_chunker_splits_sections_and_produces_stable_traceable_hashes() -> None:
    document = RequirementDocument(
        document_id="fixture-standard",
        title="施工现场 PPE 要求",
        standard_no="GB TEST",
        source_url="https://example.test/standard",
        effective_date=date(2025, 1, 1),
        pages=[
            (1, "第一章 总则\n1.1 施工单位应提供劳动防护用品。\n\n重复段落。"),
            (2, "第二章 防护\n2.1 作业人员应佩戴安全帽。\n\n重复段落。"),
        ],
    )

    chunks = RequirementChunker().split(document)
    again = RequirementChunker().split(document)

    assert [chunk.chunk_id for chunk in chunks] == [chunk.chunk_id for chunk in again]
    assert [chunk.content_hash for chunk in chunks] == [chunk.content_hash for chunk in again]
    assert {chunk.page for chunk in chunks} == {1, 2}
    assert any("安全帽" in chunk.content for chunk in chunks)
    assert len({chunk.content_hash for chunk in chunks}) == len(chunks)
    assert all(chunk.clause for chunk in chunks)


def test_chunker_rejects_empty_document_and_missing_page_metadata() -> None:
    with pytest.raises(ValueError, match="empty"):
        RequirementChunker().split(
            RequirementDocument(
                document_id="empty",
                title="Empty",
                source_url="https://example.test/empty",
                pages=[(1, "   ")],
            )
        )


def test_chunker_keeps_table_items_separate_and_rejects_unsafe_extraction() -> None:
    document = RequirementDocument(
        document_id="table",
        title="建筑 PPE 表",
        source_url="https://example.test/table",
        pages=[
            (
                1,
                "第4项 钢筋人工搬运：应使用机械手套。\n"
                "第6项 转动机械/金属切割：应使用眼面防护。\n"
                "第11项 车辆作业：应穿高可视服。",
            )
        ],
    )
    chunks = RequirementChunker().split(document)
    assert len(chunks) == 3
    assert any("机械手套" in chunk.content for chunk in chunks)
    assert any("眼面防护" in chunk.content for chunk in chunks)
    assert any("高可视服" in chunk.content for chunk in chunks)

    unsafe = document.model_copy(update={"extraction_status": "needs_ocr"})
    with pytest.raises(ValueError, match="extraction"):
        RequirementChunker().split(unsafe)
    with pytest.raises(ValueError, match="page"):
        RequirementChunker().split(
            RequirementDocument(
                document_id="bad-page",
                title="Bad page",
                source_url="https://example.test/bad",
                pages=[(0, "text")],
            )
        )
