import asyncio

from httpx import ASGITransport, AsyncClient

from app.api.deps import get_evidence_store_port
from app.main import app
from app.modules.video_analysis.evidence_store import FileEvidenceStore


def test_evidence_url_serves_the_persisted_jpeg(tmp_path) -> None:
    store = FileEvidenceStore(tmp_path)
    jpeg = b"\xff\xd8evidence\xff\xd9"
    url = store.store_jpeg(
        session_id="analysis-session-01",
        timestamp_ms=400,
        jpeg_bytes=jpeg,
    )
    async def override_store():
        return store

    app.dependency_overrides[get_evidence_store_port] = override_store

    async def request():
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            found = await client.get(url)
            missing = await client.get("/evidence/analysis-session-01/401.jpg")
            return found, missing

    try:
        found, missing = asyncio.run(request())
    finally:
        app.dependency_overrides.pop(get_evidence_store_port, None)

    assert found.status_code == 200
    assert found.headers["content-type"] == "image/jpeg"
    assert found.content == jpeg
    assert missing.status_code == 404
