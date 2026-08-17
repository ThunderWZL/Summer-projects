import asyncio

from httpx import ASGITransport, AsyncClient

from app.main import app


async def get(path: str):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        return await client.get(path)


def test_demo_videos_expose_six_traceable_channels() -> None:
    response = asyncio.run(get("/api/v1/demo/videos"))

    assert response.status_code == 200
    videos = response.json()
    assert len(videos) == 6
    assert videos[1] == {
        "video_id": "video-no-vest-02",
        "camera_id": "CAM-02",
        "camera_name": "无背心2切割物料机位",
        "zone_id": "zone-02",
        "zone_name": "无背心2切割物料区",
        "title": "无背心2｜切割物料",
        "duration_ms": 600000,
        "scenario_started_at": "2026-08-07T09:00:00+08:00",
        "content_url": "/api/v1/demo/videos/video-no-vest-02/content",
    }


def test_demo_context_exposes_business_data_without_private_file_paths() -> None:
    response = asyncio.run(get("/api/v1/demo/context"))

    assert response.status_code == 200
    context = response.json()
    assert len(context["cameras"]) == 6
    assert len(context["zones"]) == 6
    assert {item["permit_id"] for item in context["work_permits"]} == {
        "wp-0101",
        "wp-0201",
        "wp-0301",
        "wp-0401",
        "wp-0501",
        "wp-0601",
    }
    assert {item["actor_id"] for item in context["users"]} == {
        "officer-01",
        "reviewer-01",
    }
    assert "local_path" not in response.text


def test_unknown_demo_video_returns_stable_error_body() -> None:
    response = asyncio.run(get("/api/v1/demo/videos/video-99/content"))

    assert response.status_code == 404
    assert response.json() == {
        "code": "DEMO_VIDEO_NOT_FOUND",
        "message": "demo video video-99 was not found",
        "current_version": None,
    }
