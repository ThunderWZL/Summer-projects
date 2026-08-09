import asyncio
from datetime import date
import hashlib

from httpx import ASGITransport, AsyncClient

from app.api.deps import get_requirement_retriever
from app.main import app
from app.domain.requirements_rag import RequirementChunk
from app.modules.requirements_rag.embedding import DeterministicEmbeddingClient
from app.modules.requirements_rag.service import RequirementsRagService
from app.modules.requirements_rag.store import PersistentVectorStore


async def get(path: str):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        return await client.get(path)


def test_requirements_search_is_available_before_rag_is_connected() -> None:
    response = asyncio.run(
        get("/api/v1/requirements/search?q=护目镜&top_k=3")
    )

    assert response.status_code == 200
    assert response.json() == {
        "query": "护目镜",
        "top_k": 3,
        "citations": [],
    }


def test_requirements_search_returns_service_citations_when_indexed(tmp_path) -> None:
    content = "施工现场应佩戴护目镜。"
    service = RequirementsRagService(
        store=PersistentVectorStore(tmp_path / "rag.json"),
        embedder=DeterministicEmbeddingClient(dimension=8),
    )
    service.index(
        [
            RequirementChunk(
                chunk_id="fixture",
                document_id="fixture",
                title="施工 PPE 规范",
                standard_no="GB TEST",
                clause="第 4 条",
                page=2,
                source_url="https://example.test/fixture",
                effective_date=date(2025, 1, 1),
                content_hash=hashlib.sha256(content.encode()).hexdigest(),
                content=content,
            )
        ],
        manifest_fingerprint="c" * 64,
    )
    app.dependency_overrides[get_requirement_retriever] = lambda: service
    try:
        response = asyncio.run(get("/api/v1/requirements/search?q=护目镜&top_k=1"))
    finally:
        app.dependency_overrides.pop(get_requirement_retriever, None)

    assert response.status_code == 200
    body = response.json()
    assert body["citations"][0]["section"] == "第 4 条；标准印刷页2（PDF第2页）"
    assert body["citations"][0]["source_url"] == "https://example.test/fixture"
