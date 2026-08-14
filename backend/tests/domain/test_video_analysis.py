import asyncio
from inspect import signature
from typing import get_type_hints

from app.contracts import AnalysisEvent, AnalysisStage
from app.domain.case_store import CaseQuery
from app.domain.inmemory.case_store import InMemoryCaseStore
from app.domain.inmemory.fixture_cases import demo_cases
from app.domain.inmemory.site_context import MemorySiteContext
from app.domain.inmemory.video_analysis import InMemoryVideoAnalysis
from app.domain.video_analysis import AnalysisSession, VideoAnalysisPort
from app.services.event_hub import EventHub
from app.services.session_manager import SessionManager


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


def test_fake_stream_is_finite_multipart_mjpeg_with_a_jpeg_frame() -> None:
    async def scenario() -> bytes:
        fake = InMemoryVideoAnalysis(MemorySiteContext(), _case_store())
        return b"".join([chunk async for chunk in fake.get_stream("session-01")])

    stream = asyncio.run(scenario())

    assert stream.startswith(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n\xff\xd8")
    assert stream.endswith(b"\xff\xd9\r\n--frame--\r\n")
    assert b"local_path" not in stream
    assert b"/data/" not in stream


def test_fake_publishes_the_existing_camera_case_without_mutating_case_store() -> None:
    async def scenario() -> tuple[list[AnalysisEvent], list[object], list[object]]:
        store = _case_store()
        context = MemorySiteContext()
        fake = InMemoryVideoAnalysis(context, store)
        release = asyncio.Event()

        async def run(session: AnalysisSession, manager: SessionManager) -> None:
            await release.wait()
            await fake.run_session(session, manager)

        manager = SessionManager(EventHub(), context.get_video, fake.get_stream, run)
        before = list(store.list(CaseQuery(page_size=100)).items)
        session = await manager.start_session("video-01")
        events = manager.subscribe_events(session.session_id)
        pending = asyncio.create_task(anext(events))
        await _let_subscription_start(pending)
        release.set()
        received = [await pending]
        for _ in range(4):
            received.append(await anext(events))
        await events.aclose()
        after = list(store.list(CaseQuery(page_size=100)).items)
        return received, before, after

    events, before, after = asyncio.run(scenario())
    candidate = next(event for event in events if event.event_type == "CANDIDATE_CREATED")

    assert candidate.session_id == events[0].session_id
    assert candidate.case_id == "case-facts-01"
    assert candidate.payload.candidate_id == "candidate-case-facts-01"
    assert [item.model_dump() for item in after] == [item.model_dump() for item in before]


def test_fake_does_not_publish_a_candidate_for_an_unenabled_ppe_type() -> None:
    async def scenario() -> list[AnalysisEvent]:
        store = _case_store()
        context = MemorySiteContext()
        fake = InMemoryVideoAnalysis(context, store)
        release = asyncio.Event()

        async def run(session: AnalysisSession, manager: SessionManager) -> None:
            await release.wait()
            await fake.run_session(session, manager)

        manager = SessionManager(EventHub(), context.get_video, fake.get_stream, run)
        session = await manager.start_session("video-02")
        events = manager.subscribe_events(session.session_id)
        pending = asyncio.create_task(anext(events))
        await _let_subscription_start(pending)
        release.set()
        received = [await pending]
        for _ in range(3):
            received.append(await anext(events))
        await events.aclose()
        return received

    events = asyncio.run(scenario())

    assert all(event.event_type != "CANDIDATE_CREATED" for event in events)
    assert events[-1].payload.candidate_count == 0
    assert events[-1].payload.case_count == 0


def test_fake_does_not_invent_a_candidate_without_a_matching_camera_case() -> None:
    async def scenario() -> list[AnalysisEvent]:
        store = _case_store()
        context = MemorySiteContext()
        fake = InMemoryVideoAnalysis(context, store)
        release = asyncio.Event()

        async def run(session: AnalysisSession, manager: SessionManager) -> None:
            await release.wait()
            await fake.run_session(session, manager)

        manager = SessionManager(EventHub(), context.get_video, fake.get_stream, run)
        session = await manager.start_session("video-06")
        events = manager.subscribe_events(session.session_id)
        pending = asyncio.create_task(anext(events))
        await _let_subscription_start(pending)
        release.set()
        received = [await pending]
        for _ in range(3):
            received.append(await anext(events))
        await events.aclose()
        return received

    events = asyncio.run(scenario())

    assert [event.event_type.value for event in events] == [
        "SESSION_PROGRESS",
        "SESSION_PROGRESS",
        "SESSION_PROGRESS",
        "SESSION_FINISHED",
    ]
    assert events[-1].payload.candidate_count == 0
    assert events[-1].payload.case_count == 0
