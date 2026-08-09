import asyncio

from httpx import ASGITransport, AsyncClient

from app.main import app


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
