import asyncio

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.errors import case_workflow_exception_handler
from app.domain.case_workflow import (
    CaseWorkflowError,
    EvidenceRequired,
    PpeNotRequired,
    ReviewMismatch,
)
from app.main import app


def test_vlm_review_mismatch_uses_the_frozen_workflow_error_response() -> None:
    test_app = FastAPI()
    test_app.add_exception_handler(
        CaseWorkflowError,
        case_workflow_exception_handler,
    )

    @test_app.get("/error")
    def raise_review_mismatch() -> None:
        raise ReviewMismatch(["candidate_id", "ppe_type"])

    async def get_error():
        async with AsyncClient(
            transport=ASGITransport(
                app=test_app,
                raise_app_exceptions=False,
            ),
            base_url="http://test",
        ) as client:
            return await client.get("/error")

    response = asyncio.run(get_error())

    assert response.status_code == 400
    assert response.json() == {
        "code": "VLM_REVIEW_MISMATCH",
        "message": "VLM review disagrees with case: candidate_id, ppe_type",
        "current_version": None,
    }


def test_missing_evidence_uses_the_frozen_workflow_error_response() -> None:
    test_app = FastAPI()
    test_app.add_exception_handler(
        CaseWorkflowError,
        case_workflow_exception_handler,
    )

    @test_app.get("/error")
    def raise_missing_evidence() -> None:
        raise EvidenceRequired("rectification evidence")

    async def get_error():
        async with AsyncClient(
            transport=ASGITransport(
                app=test_app,
                raise_app_exceptions=False,
            ),
            base_url="http://test",
        ) as client:
            return await client.get("/error")

    response = asyncio.run(get_error())

    assert response.status_code == 400
    assert response.json() == {
        "code": "EVIDENCE_REQUIRED",
        "message": "rectification evidence is required",
        "current_version": None,
    }


def test_ppe_not_required_uses_strict_422_error_response() -> None:
    test_app = FastAPI()
    test_app.add_exception_handler(
        CaseWorkflowError,
        case_workflow_exception_handler,
    )

    @test_app.get("/error")
    def raise_ppe_not_required() -> None:
        raise PpeNotRequired()

    async def get_error():
        async with AsyncClient(
            transport=ASGITransport(app=test_app, raise_app_exceptions=False),
            base_url="http://test",
        ) as client:
            return await client.get("/error")

    response = asyncio.run(get_error())

    assert response.status_code == 422
    assert response.json() == {
        "code": "PPE_NOT_REQUIRED",
        "message": "candidate PPE is not required for the investigated task",
        "current_version": None,
    }


def test_human_command_openapi_declares_all_workflow_error_responses() -> None:
    async def get_openapi():
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            return await client.get("/openapi.json")

    schema = asyncio.run(get_openapi()).json()
    for path in (
        "/api/v1/cases/{case_id}/facts",
        "/api/v1/cases/{case_id}/review",
        "/api/v1/cases/{case_id}/rectification-evidence",
        "/api/v1/cases/{case_id}/recheck",
    ):
        responses = schema["paths"][path]["post"]["responses"]
        assert {"200", "400", "403", "404", "409", "422"} <= set(
            responses
        )
        for status_code in ("400", "403", "404", "409"):
            assert responses[status_code]["content"]["application/json"][
                "schema"
            ] == {"$ref": "#/components/schemas/ErrorResponse"}
