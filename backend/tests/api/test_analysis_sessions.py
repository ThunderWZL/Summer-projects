import asyncio

from httpx import ASGITransport, AsyncClient

from app.api.deps import (
    get_case_store,
    get_case_pipeline,
    get_event_hub,
    get_inmemory_video_analysis,
    get_session_manager,
    get_investigation_port,
)
from app.main import app


def setup_function() -> None:
    get_session_manager.cache_clear()
    get_inmemory_video_analysis.cache_clear()
    get_event_hub.cache_clear()
    get_case_pipeline.cache_clear()
    get_investigation_port.cache_clear()
    get_case_store.cache_clear()


async def request(method: str, path: str, json: dict | None = None):
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        return await client.request(method, path, json=json)


def test_start_and_idempotent_stop_return_session_transport_urls() -> None:
    async def scenario():
        start = await request(
            "POST", "/api/v1/analysis-sessions", {"video_id": "video-02"}
        )
        session_id = start.json()["session_id"]
        first = await request(
            "POST", f"/api/v1/analysis-sessions/{session_id}/stop"
        )
        second = await request(
            "POST", f"/api/v1/analysis-sessions/{session_id}/stop"
        )
        return start, first, second

    start, first, second = asyncio.run(scenario())

    assert 200 <= start.status_code < 300
    body = start.json()
    session_id = body["session_id"]
    assert body == {
        "session_id": session_id,
        "video_id": "video-02",
        "stage": "STARTING",
        "stream_url": f"/api/v1/analysis-sessions/{session_id}/stream.mjpg",
        "events_url": f"/ws/v1/analysis-sessions/{session_id}/events",
    }
    assert "local_path" not in start.text

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert first.json()["stage"] == "STOPPING"


def test_start_request_rejects_extra_fields() -> None:
    response = asyncio.run(
        request(
            "POST",
            "/api/v1/analysis-sessions",
            {"video_id": "video-02", "local_path": "/private/demo.mp4"},
        )
    )

    assert response.status_code == 422
    assert response.json() == {
        "code": "VALIDATION_ERROR",
        "message": "request validation failed",
        "current_version": None,
    }


def test_unknown_video_and_session_return_stable_error_responses() -> None:
    async def scenario():
        video = await request(
            "POST", "/api/v1/analysis-sessions", {"video_id": "video-99"}
        )
        session = await request(
            "POST", "/api/v1/analysis-sessions/session-99/stop"
        )
        return video, session

    video, session = asyncio.run(scenario())

    assert video.status_code == 404
    assert video.json() == {
        "code": "ANALYSIS_VIDEO_NOT_FOUND",
        "message": "analysis video video-99 was not found",
        "current_version": None,
    }
    assert session.status_code == 404
    assert session.json() == {
        "code": "ANALYSIS_SESSION_NOT_FOUND",
        "message": "analysis session session-99 was not found",
        "current_version": None,
    }


def test_mjpeg_endpoint_has_a_finite_multipart_jpeg_without_private_paths() -> None:
    async def scenario():
        start = await request(
            "POST", "/api/v1/analysis-sessions", {"video_id": "video-02"}
        )
        stream = await request("GET", start.json()["stream_url"])
        return stream

    stream = asyncio.run(scenario())

    assert stream.status_code == 200
    assert stream.headers["content-type"].startswith(
        "multipart/x-mixed-replace; boundary=frame"
    )
    assert stream.content.startswith(
        b"--frame\r\nContent-Type: image/jpeg\r\n\r\n\xff\xd8"
    )
    assert stream.content.endswith(b"\xff\xd9\r\n--frame--\r\n")
    assert b"local_path" not in stream.content
    assert b"/data/" not in stream.content


def test_unknown_mjpeg_session_returns_error_response_instead_of_a_stream() -> None:
    response = asyncio.run(
        request("GET", "/api/v1/analysis-sessions/session-99/stream.mjpg")
    )

    assert response.status_code == 404
    assert response.json()["code"] == "ANALYSIS_SESSION_NOT_FOUND"


def test_stopped_session_mjpeg_returns_conflict_instead_of_a_stream() -> None:
    async def scenario():
        start = await request(
            "POST", "/api/v1/analysis-sessions", {"video_id": "video-01"}
        )
        session_id = start.json()["session_id"]
        await request("POST", f"/api/v1/analysis-sessions/{session_id}/stop")
        return await request(
            "GET", f"/api/v1/analysis-sessions/{session_id}/stream.mjpg"
        )

    response = asyncio.run(scenario())

    assert response.status_code == 409
    assert response.json()["code"] == "ANALYSIS_SESSION_NOT_ACTIVE"


def test_finished_fake_session_stream_remains_available_until_stop() -> None:
    async def scenario():
        start = await request(
            "POST", "/api/v1/analysis-sessions", {"video_id": "video-01"}
        )
        session_id = start.json()["session_id"]
        events = get_session_manager().subscribe_events(session_id)
        while True:
            event = await anext(events)
            if event.event_type == "SESSION_FINISHED":
                break
        await events.aclose()
        stream = await request("GET", start.json()["stream_url"])
        await request("POST", f"/api/v1/analysis-sessions/{session_id}/stop")
        return stream

    response = asyncio.run(scenario())

    assert response.status_code == 200
    assert response.content.startswith(b"--frame\r\nContent-Type: image/jpeg")


def test_rest_can_query_the_case_announced_by_the_finished_session() -> None:
    async def scenario():
        start = await request(
            "POST", "/api/v1/analysis-sessions", {"video_id": "video-02"}
        )
        session_id = start.json()["session_id"]
        events = get_session_manager().subscribe_events(session_id)
        received = []
        while True:
            event = await anext(events)
            received.append(event)
            if event.event_type.value == "SESSION_FINISHED":
                break
        await events.aclose()
        created = next(
            event for event in received if event.event_type.value == "CANDIDATE_CREATED"
        )
        detail = await request("GET", f"/api/v1/cases/{created.case_id}")
        return created, received, detail

    created, received, detail = asyncio.run(scenario())
    finished = received[-1]

    assert created.case_id
    assert [event.event_type.value for event in received] == [
        "SESSION_PROGRESS",
        "SESSION_PROGRESS",
        "SESSION_PROGRESS",
        "CANDIDATE_CREATED",
        "VLM_REVIEWED",
        "CASE_UPDATED",
        "CASE_UPDATED",
        "SESSION_FINISHED",
    ]
    assert received[4].payload.status == "VLM_REVIEWED"
    assert received[4].payload.version == 2
    assert [event.payload.status for event in received[5:7]] == [
        "INVESTIGATING",
        "PENDING_REVIEW",
    ]
    assert [event.payload.version for event in received[5:7]] == [3, 4]
    assert (finished.payload.candidate_count, finished.payload.case_count) == (1, 1)
    assert detail.status_code == 200
    assert detail.json()["snapshot"]["case_id"] == created.case_id
    assert detail.json()["snapshot"]["candidate"]["candidate_id"] == (
        created.payload.candidate_id
    )


def test_analysis_session_openapi_freezes_success_and_error_responses() -> None:
    schema = app.openapi()
    paths = schema["paths"]
    error_schema = {"$ref": "#/components/schemas/ErrorResponse"}

    start_responses = paths["/api/v1/analysis-sessions"]["post"]["responses"]
    stop_responses = paths[
        "/api/v1/analysis-sessions/{session_id}/stop"
    ]["post"]["responses"]
    stream_responses = paths[
        "/api/v1/analysis-sessions/{session_id}/stream.mjpg"
    ]["get"]["responses"]

    for responses, error_statuses in (
        (start_responses, ("404", "422")),
        (stop_responses, ("404", "422")),
        (stream_responses, ("404", "409", "422")),
    ):
        for status_code in error_statuses:
            assert responses[status_code]["content"]["application/json"][
                "schema"
            ] == error_schema

    assert stream_responses["200"]["content"] == {
        "multipart/x-mixed-replace": {
            "schema": {"type": "string", "format": "binary"}
        }
    }
