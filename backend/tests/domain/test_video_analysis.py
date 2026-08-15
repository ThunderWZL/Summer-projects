import asyncio
from inspect import signature
from typing import get_type_hints

import pytest

from app.contracts import AnalysisEvent, AnalysisStage
from app.domain.case_store import CaseQuery
from app.domain.inmemory.case_store import InMemoryCaseStore
from app.domain.inmemory.fixture_cases import demo_cases
from app.domain.inmemory.site_context import MemorySiteContext
from app.domain.inmemory.video_analysis import InMemoryVideoAnalysis
from app.domain.video_analysis import AnalysisSession, VideoAnalysisPort
from app.services.event_hub import EventHub
from app.services.session_manager import SessionManager
from app.api.deps import (
    get_case_pipeline,
    get_case_store,
    get_event_hub,
    get_inmemory_video_analysis,
    get_investigation_port,
    get_session_manager,
    shutdown_database_runtime,
)
from app.config import get_settings


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch: pytest.MonkeyPatch):
    shutdown_database_runtime()
    monkeypatch.setenv(
        "DATABASE_URL",
        f"sqlite:///{tmp_path / 'video-analysis.db'}",
    )
    get_settings.cache_clear()
    yield
    shutdown_database_runtime()
    get_settings.cache_clear()


def _case_store() -> InMemoryCaseStore:
    store = InMemoryCaseStore()
    for snapshot in demo_cases():
        store.create(snapshot)
    return store


async def _let_subscription_start(task: asyncio.Task[AnalysisEvent]) -> None:
    await asyncio.wait({task}, timeout=0)


def test_analysis_session_and_port_expose_the_frozen_contract() -> None:
    session = AnalysisSession(
        session_id="session-01",
        video_id="video-02",
        stage=AnalysisStage.INFERENCING,
    )

    assert session == AnalysisSession(
        session_id="session-01",
        video_id="video-02",
        stage=AnalysisStage.INFERENCING,
    )
    assert {
        "start_session",
        "get_stream",
        "subscribe_events",
        "stop_session",
    } <= set(VideoAnalysisPort.__dict__)
    assert get_type_hints(VideoAnalysisPort.start_session)["return"] is AnalysisSession
    assert signature(VideoAnalysisPort.start_session).parameters["video_id"].annotation in {
        "str",
        str,
    }


def _reset_composition() -> None:
    get_session_manager.cache_clear()
    get_inmemory_video_analysis.cache_clear()
    get_event_hub.cache_clear()
    get_case_pipeline.cache_clear()
    get_investigation_port.cache_clear()
    get_case_store.cache_clear()


def test_fake_stream_is_finite_multipart_mjpeg_with_a_jpeg_frame() -> None:
    async def scenario() -> bytes:
        _reset_composition()
        fake = get_inmemory_video_analysis()
        return b"".join([chunk async for chunk in fake.get_stream("session-01")])

    stream = asyncio.run(scenario())

    assert stream.startswith(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n\xff\xd8")
    assert stream.endswith(b"\xff\xd9\r\n--frame--\r\n")
    assert b"local_path" not in stream
    assert b"/data/" not in stream


async def _run_demo(video_id: str) -> tuple[list[AnalysisEvent], object]:
    manager = get_session_manager()
    session = await manager.start_session(video_id)
    stream = manager.subscribe_events(session.session_id)
    received: list[AnalysisEvent] = []
    while True:
        event = await anext(stream)
        received.append(event)
        if event.event_type.value in {"SESSION_FINISHED", "SESSION_FAILED"}:
            break
    await stream.aclose()
    return received, get_case_store()


def test_cam01_to_cam05_publish_candidates_with_nonempty_case_ids_and_cam06_is_zero() -> None:
    async def scenario():
        _reset_composition()
        results = []
        for number in range(1, 7):
            results.append(await _run_demo(f"video-{number:02d}"))
        return results

    results = asyncio.run(scenario())

    for events, store in results[:5]:
        created = next(event for event in events if event.event_type.value == "CANDIDATE_CREATED")
        finished = events[-1]
        assert created.case_id
        assert store.get(created.case_id) is not None
        assert (finished.payload.candidate_count, finished.payload.case_count) == (1, 1)
        assert all(
            event.payload.candidate_count == 0 and event.payload.case_count == 0
            for event in events
            if event.event_type.value == "SESSION_PROGRESS"
        )
    cam06_events, _ = results[5]
    assert all(event.event_type.value != "CANDIDATE_CREATED" for event in cam06_events)
    assert (cam06_events[-1].payload.candidate_count, cam06_events[-1].payload.case_count) == (0, 0)


def test_replaying_a_demo_video_reuses_the_case_without_duplicate_transitions() -> None:
    async def scenario():
        _reset_composition()
        first_events, store = await _run_demo("video-03")
        first_id = next(event.case_id for event in first_events if event.event_type.value == "CANDIDATE_CREATED")
        first = store.get(first_id)
        second_events, _ = await _run_demo("video-03")
        second_id = next(event.case_id for event in second_events if event.event_type.value == "CANDIDATE_CREATED")
        return first_id, second_id, first, store.get(second_id)

    first_id, second_id, first, second = asyncio.run(scenario())

    assert first_id == second_id
    assert second == first
