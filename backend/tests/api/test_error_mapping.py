import asyncio

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.errors import case_workflow_exception_handler
from app.domain.case_workflow import CaseWorkflowError, ReviewMismatch


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
