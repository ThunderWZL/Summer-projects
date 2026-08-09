from datetime import date

import pytest
from pydantic import ValidationError

from app.domain.requirements_rag import (
    IndexMetadata,
    IndexReport,
    RequirementChunk,
    RequirementQuery,
)


def test_requirement_query_is_strict_and_bounded() -> None:
    query = RequirementQuery(q="建筑施工现场护目镜要求", top_k=3)

    assert query.q == "建筑施工现场护目镜要求"
    assert query.top_k == 3

    with pytest.raises(ValidationError):
        RequirementQuery(q="", top_k=3)
    with pytest.raises(ValidationError):
        RequirementQuery(q="护目镜", top_k=0)
    with pytest.raises(ValidationError):
        RequirementQuery(q="护目镜", top_k=21)


def test_chunk_and_index_report_reject_unknown_fields() -> None:
    chunk = RequirementChunk(
        chunk_id="gb12:abc",
        document_id="gb-39800-12",
        title="建筑个体防护装备",
        standard_no="GB 39800.12-2025",
        clause="第 3 条",
        page=2,
        source_url="https://example.test/gb12",
        effective_date=date(2026, 7, 1),
        content_hash="a" * 64,
        content="施工人员应按危害因素选用个人防护装备。",
    )

    assert chunk.page == 2
    assert chunk.effective_date == date(2026, 7, 1)
    with pytest.raises(ValidationError):
        RequirementChunk.model_validate({**chunk.model_dump(), "unexpected": True})

    report = IndexReport(
        indexed_chunks=1,
        skipped_duplicates=0,
        rebuilt=False,
        manifest_fingerprint="b" * 64,
        embedding_model="fake",
        vector_dimension=8,
        corpus_fingerprint="c" * 64,
    )
    assert report.indexed_chunks == 1
    with pytest.raises(ValidationError):
        IndexMetadata.model_validate({"embedding_model": "fake", "vector_dimension": 8})
