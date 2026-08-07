import asyncio

from httpx import ASGITransport, AsyncClient

from app.main import app


async def get(path: str):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        return await client.get(path)


def test_health() -> None:
    response = asyncio.run(get("/health"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_shared_contract_schema_is_exposed() -> None:
    response = asyncio.run(get("/api/v1/contracts/schema"))

    assert response.status_code == 200
    assert {
        "CandidateEvidence",
        "VlmReviewResult",
        "InvestigationResult",
        "CaseSnapshot",
        "CaseListResponse",
        "CaseDetailResponse",
        "AnalysisEvent",
        "ErrorResponse",
        "CaseCommandResponse",
    } <= set(response.json())


def test_case_command_schemas_are_exposed() -> None:
    response = asyncio.run(get("/api/v1/contracts/schema"))

    assert {
        "SubmitFacts",
        "ApproveRectification",
        "RejectCase",
        "RequestReinvestigation",
        "SubmitRectificationEvidence",
        "ApproveClosure",
        "RejectRecheck",
    } <= set(response.json())
