import asyncio

import pytest

from app.contracts import AnalysisEvent, AnalysisStage
from app.domain.case_store import CaseQuery
from app.domain.inmemory.case_store import InMemoryCaseStore
from app.domain.inmemory.fixture_cases import demo_cases
from app.domain.investigation import InvestigationAgentFailed
from app.domain.video_analysis import (
    AnalysisSession,
    AnalysisSessionNotActive,
    AnalysisSessionNotFound,
    AnalysisVideoNotFound,
    VideoAnalysisProcessingFailed,
)
from app.modules.vlm_review.errors import VlmProcessingFailed
from app.services.event_hub import EventHub
from app.services.session_manager import SessionManager


def _manager(started: asyncio.Queue[str] | None = None) -> SessionManager:
    async def stream(_session_id: str):
        yield b"frame"

    async def run(session: AnalysisSession, _manager: SessionManager) -> None:
        if started is not None:
            started.put_nowait(session.session_id)
        await asyncio.Event().wait()

    return SessionManager(
        EventHub(),
        lambda video_id: object() if video_id in {"video-01", "video-02"} else None,
        stream,
        run,
    )


async def _start_receive(iterator) -> asyncio.Task[AnalysisEvent]:
    task = asyncio.create_task(anext(iterator))
    await asyncio.wait({task}, timeout=0)
    return task


def test_starting_another_video_stops_but_preserves_the_old_session() -> None:
    async def scenario() -> tuple[AnalysisSession, AnalysisSession, AnalysisEvent]:
        started: asyncio.Queue[str] = asyncio.Queue()
        manager = _manager(started)
        first = await manager.start_session("video-01")
        assert await started.get() == first.session_id
        old_events = manager.subscribe_events(first.session_id)
        receive = await _start_receive(old_events)

        second = await manager.start_session("video-02")
        assert await started.get() == second.session_id
        stop_event = await receive
        preserved = await manager.stop_session(first.session_id)
        await old_events.aclose()
        await manager.stop_session(second.session_id)
        return preserved, second, stop_event

    old, new, event = asyncio.run(scenario())

    assert old.stage is AnalysisStage.STOPPING
    assert new.video_id == "video-02"
    assert new.session_id != old.session_id
    assert event.event_type == "SESSION_PROGRESS"
    assert event.payload.stage is AnalysisStage.STOPPING


def test_stop_is_idempotent_and_unknown_inputs_have_stable_domain_errors() -> None:
    async def scenario() -> tuple[AnalysisSession, AnalysisSession]:
        manager = _manager()
        with pytest.raises(AnalysisVideoNotFound, match="video-99") as video_error:
            await manager.start_session("video-99")
        assert video_error.value.code == "ANALYSIS_VIDEO_NOT_FOUND"

        session = await manager.start_session("video-01")
        first = await manager.stop_session(session.session_id)
        second = await manager.stop_session(session.session_id)
        with pytest.raises(AnalysisSessionNotFound, match="session-99") as session_error:
            await manager.stop_session("session-99")
        assert session_error.value.code == "ANALYSIS_SESSION_NOT_FOUND"
        return first, second

    first, second = asyncio.run(scenario())

    assert first.stage is AnalysisStage.STOPPING
    assert second == first


def test_stop_waits_for_the_session_runner_to_release_resources() -> None:
    async def scenario() -> bool:
        started = asyncio.Event()
        released = asyncio.Event()

        async def stream(_session_id: str):
            yield b"frame"

        async def run(
            _session: AnalysisSession, _manager: SessionManager
        ) -> None:
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                released.set()

        manager = SessionManager(
            EventHub(),
            lambda _video_id: object(),
            stream,
            run,
        )
        session = await manager.start_session("video-01")
        await started.wait()
        await manager.stop_session(session.session_id)
        return released.is_set()

    assert asyncio.run(scenario()) is True


def test_concurrent_switches_never_overlap_session_runners() -> None:
    async def scenario() -> int:
        running = 0
        maximum_running = 0
        first_started = asyncio.Event()
        first_releasing = asyncio.Event()
        allow_first_release = asyncio.Event()

        async def stream(_session_id: str):
            yield b"frame"

        async def run(session: AnalysisSession, _manager: SessionManager) -> None:
            nonlocal running, maximum_running
            running += 1
            maximum_running = max(maximum_running, running)
            if session.video_id == "video-01":
                first_started.set()
            try:
                await asyncio.Event().wait()
            finally:
                if session.video_id == "video-01":
                    first_releasing.set()
                    await allow_first_release.wait()
                running -= 1

        manager = SessionManager(
            EventHub(),
            lambda video_id: object()
            if video_id in {"video-01", "video-02", "video-03"}
            else None,
            stream,
            run,
        )
        first = await manager.start_session("video-01")
        await first_started.wait()
        left_switch = asyncio.create_task(manager.start_session("video-02"))
        await first_releasing.wait()
        right_switch = asyncio.create_task(manager.start_session("video-03"))
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        allow_first_release.set()
        left, right = await asyncio.gather(left_switch, right_switch)
        await asyncio.sleep(0)
        await manager.stop_session(first.session_id)
        await manager.stop_session(left.session_id)
        await manager.stop_session(right.session_id)
        return maximum_running

    assert asyncio.run(scenario()) == 1


def test_stopped_session_cannot_open_a_new_stream() -> None:
    async def scenario() -> None:
        manager = _manager()
        session = await manager.start_session("video-01")
        await manager.stop_session(session.session_id)
        with pytest.raises(AnalysisSessionNotActive) as error:
            manager.get_stream(session.session_id)
        assert error.value.code == "ANALYSIS_SESSION_NOT_ACTIVE"

    asyncio.run(scenario())


def test_progress_events_report_the_public_session_stage() -> None:
    async def scenario() -> AnalysisEvent:
        manager = _manager()
        session = await manager.start_session("video-01")
        events = manager.subscribe_events(session.session_id)
        receive = await _start_receive(events)
        await manager.publish_progress(
            session.session_id,
            stage=AnalysisStage.INFERENCING,
            progress=0.75,
            message="running",
            inference_fps=12.0,
        )
        event = await receive
        await events.aclose()
        await manager.stop_session(session.session_id)
        return event

    event = asyncio.run(scenario())

    assert event.event_type == "SESSION_PROGRESS"
    assert event.payload.stage is AnalysisStage.INFERENCING
    assert event.payload.progress == 0.75


@pytest.mark.parametrize("retryable", [True, False])
def test_vlm_processing_failure_becomes_session_failed_without_case_transition(
    retryable: bool,
) -> None:
    async def scenario() -> tuple[AnalysisEvent, list[dict], list[dict]]:
        store = InMemoryCaseStore()
        for case in demo_cases():
            store.create(case)
        before = [
            case.model_dump() for case in store.list(CaseQuery(page_size=100)).items
        ]
        release = asyncio.Event()

        async def stream(_session_id: str):
            yield b"frame"

        async def fail(
            _session: AnalysisSession, _manager: SessionManager
        ) -> None:
            await release.wait()
            raise VlmProcessingFailed(
                "review unavailable", retryable=retryable
            )

        manager = SessionManager(
            EventHub(),
            lambda video_id: object() if video_id == "video-01" else None,
            stream,
            fail,
        )
        session = await manager.start_session("video-01")
        events = manager.subscribe_events(session.session_id)
        receive = await _start_receive(events)
        release.set()
        event = await receive
        await events.aclose()
        after = [
            case.model_dump() for case in store.list(CaseQuery(page_size=100)).items
        ]
        return event, before, after

    event, before, after = asyncio.run(scenario())

    assert event.event_type == "SESSION_FAILED"
    assert event.payload.error_code == "VLM_PROCESSING_FAILED"
    assert event.payload.message == "review unavailable"
    assert event.payload.retryable is retryable
    assert after == before


def test_video_processing_failure_becomes_retryable_session_failed() -> None:
    async def scenario() -> AnalysisEvent:
        release = asyncio.Event()

        async def stream(_session_id: str):
            yield b"frame"

        async def fail(
            _session: AnalysisSession, _manager: SessionManager
        ) -> None:
            await release.wait()
            raise VideoAnalysisProcessingFailed("unable to read configured video")

        manager = SessionManager(
            EventHub(),
            lambda _video_id: object(),
            stream,
            fail,
        )
        session = await manager.start_session("video-01")
        events = manager.subscribe_events(session.session_id)
        receive = await _start_receive(events)
        release.set()
        event = await receive
        await events.aclose()
        return event

    event = asyncio.run(scenario())

    assert event.event_type == "SESSION_FAILED"
    assert event.payload.error_code == "VIDEO_ANALYSIS_PROCESSING_FAILED"
    assert event.payload.message == "unable to read configured video"
    assert event.payload.retryable is True


def test_investigation_failure_becomes_retryable_session_failed() -> None:
    async def scenario() -> AnalysisEvent:
        release = asyncio.Event()

        async def stream(_session_id: str):
            yield b"frame"

        async def fail(
            _session: AnalysisSession, _manager: SessionManager
        ) -> None:
            await release.wait()
            raise InvestigationAgentFailed("DeepSeek request failed")

        manager = SessionManager(
            EventHub(),
            lambda _video_id: object(),
            stream,
            fail,
        )
        session = await manager.start_session("video-01")
        events = manager.subscribe_events(session.session_id)
        receive = await _start_receive(events)
        release.set()
        event = await asyncio.wait_for(receive, timeout=0.2)
        await events.aclose()
        return event

    event = asyncio.run(scenario())

    assert event.event_type == "SESSION_FAILED"
    assert event.payload.error_code == "INVESTIGATION_PROCESSING_FAILED"
    assert event.payload.message == "DeepSeek request failed"
    assert event.payload.retryable is True
