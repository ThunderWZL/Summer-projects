import asyncio

from httpx import ASGITransport, AsyncClient

from app.api.deps import get_site_context
from app.domain.inmemory.site_context import MemorySiteContext
from app.main import app


async def get(path: str):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        return await client.get(path)


async def request_with_context(
    method: str,
    path: str,
    *,
    context: MemorySiteContext,
    json: dict[str, object] | None = None,
):
    app.dependency_overrides[get_site_context] = lambda: context
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            return await client.request(method, path, json=json)
    finally:
        app.dependency_overrides.pop(get_site_context, None)


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


def test_worksite_configurations_expose_labels_instead_of_internal_task_codes() -> None:
    response = asyncio.run(
        request_with_context(
            "GET",
            "/api/v1/demo/worksite-configurations",
            context=MemorySiteContext(),
        )
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["cameras"]) == 6
    assert body["cameras"][0] == {
        "camera_id": "CAM-01",
        "mode": "PRESET",
        "preset_id": "MATERIAL_CUTTING",
        "name": "物料切割",
        "required_ppe": ["helmet", "gloves", "vest"],
    }
    assert body["presets"][0]["name"] == "物料切割"
    assert "task_code" not in response.text


def test_camera_accepts_a_custom_runtime_worksite_configuration() -> None:
    context = MemorySiteContext()
    response = asyncio.run(
        request_with_context(
            "PATCH",
            "/api/v1/demo/worksite-configurations/CAM-04",
            context=context,
            json={
                "mode": "CUSTOM",
                "name": "临时高处检修区",
                "required_ppe": ["helmet", "vest"],
            },
        )
    )

    assert response.status_code == 200
    assert response.json() == {
        "camera_id": "CAM-04",
        "mode": "CUSTOM",
        "preset_id": None,
        "name": "临时高处检修区",
        "required_ppe": ["helmet", "vest"],
    }
    configured = context.get_camera_worksite_configuration("CAM-04")
    assert configured is not None
    assert configured.name == "临时高处检修区"


def test_camera_configuration_rejects_non_demo_ppe_and_unknown_camera() -> None:
    context = MemorySiteContext()
    invalid_ppe = asyncio.run(
        request_with_context(
            "PATCH",
            "/api/v1/demo/worksite-configurations/CAM-01",
            context=context,
            json={
                "mode": "CUSTOM",
                "name": "测试区域",
                "required_ppe": ["boots"],
            },
        )
    )
    missing_camera = asyncio.run(
        request_with_context(
            "PATCH",
            "/api/v1/demo/worksite-configurations/CAM-99",
            context=context,
            json={"mode": "PRESET", "preset_id": "MATERIAL_CUTTING"},
        )
    )

    assert invalid_ppe.status_code == 422
    assert missing_camera.status_code == 404
    assert missing_camera.json()["code"] == "CAMERA_NOT_FOUND"
