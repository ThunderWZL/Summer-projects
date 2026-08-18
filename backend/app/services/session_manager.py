from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import suppress
from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4

from app.contracts import (
    AnalysisEvent,
    AnalysisEventType,
    AnalysisStage,
    CandidateCreatedPayload,
    CaseUpdatedPayload,
    SessionFailedPayload,
    SessionFinishedPayload,
    SessionProgressPayload,
    VlmReviewedPayload,
)
from app.domain.investigation import InvestigationError
from app.domain.video_analysis import (
    AnalysisSession,
    AnalysisSessionNotActive,
    AnalysisSessionNotFound,
    AnalysisVideoNotFound,
    VideoAnalysisProcessingFailed,
    VideoAnalysisPort,
)
from app.domain.site_context import VideoInfo
from app.modules.vlm_review.errors import VlmProcessingFailed
from app.services.event_hub import EventHub

VideoLookup = Callable[[str], VideoInfo | None]
StreamProvider = Callable[[str], AsyncIterator[bytes]]
SessionRunner = Callable[[AnalysisSession, "SessionManager"], Awaitable[None]]
SessionSaver = Callable[[AnalysisSession, int], None]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ignore_session_save(
    _session: AnalysisSession,
    _playback_ms: int,
) -> None:
    return None


class SessionManager(VideoAnalysisPort):
    def __init__(
        self,
        event_hub: EventHub,
        get_video: VideoLookup,
        get_stream: StreamProvider,
        run_session: SessionRunner,
        *,
        save_session: SessionSaver = _ignore_session_save,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._event_hub = event_hub
        self._get_video = get_video
        self._get_stream = get_stream
        self._run_session = run_session
        self._save_session = save_session
        self._clock = clock
        self._sessions: dict[str, AnalysisSession] = {}
        self._active_session_id: str | None = None
        self._streamable_session_ids: set[str] = set()
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._lifecycle_lock = asyncio.Lock()

    async def start_session(self, video_id: str) -> AnalysisSession:
        async with self._lifecycle_lock:
            if self._get_video(video_id) is None:
                raise AnalysisVideoNotFound(video_id)
            if self._active_session_id is not None:
                await self._stop_session(self._active_session_id)
            session = AnalysisSession(
                session_id=f"analysis-session-{uuid4().hex}",
                video_id=video_id,
                stage=AnalysisStage.STARTING,
                started_at=self._clock(),
            )
            self._save_session(session, 0)
            self._sessions[session.session_id] = session
            self._active_session_id = session.session_id
            self._streamable_session_ids.add(session.session_id)
            task = asyncio.create_task(self._execute(session))
            self._tasks[session.session_id] = task
            return session

    def get_stream(self, session_id: str) -> AsyncIterator[bytes]:
        self._require_session(session_id)
        if session_id not in self._streamable_session_ids:
            raise AnalysisSessionNotActive(session_id)
        return self._get_stream(session_id)

    def subscribe_events(self, session_id: str) -> AsyncIterator[AnalysisEvent]:
        self._require_session(session_id)
        return self._event_hub.subscribe(session_id)

    async def stop_session(self, session_id: str) -> AnalysisSession:
        async with self._lifecycle_lock:
            return await self._stop_session(session_id)

    async def _stop_session(self, session_id: str) -> AnalysisSession:
        session = self._require_session(session_id)
        if session.stage is AnalysisStage.STOPPING:
            return session
        stopped = replace(session, stage=AnalysisStage.STOPPING)
        await self.publish_progress(
            session_id,
            stage=AnalysisStage.STOPPING,
            progress=1.0,
            message="analysis session stopping",
        )
        self._streamable_session_ids.discard(session_id)
        self._clear_active_session(session_id)
        task = self._tasks.get(session_id)
        if task is not None and not task.done() and task is not asyncio.current_task():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            self._tasks.pop(session_id, None)
        return stopped

    async def publish_progress(
        self,
        session_id: str,
        *,
        stage: AnalysisStage,
        progress: float,
        message: str | None,
        inference_fps: float = 0.0,
        candidate_count: int = 0,
        case_count: int = 0,
        playback_ms: int = 0,
    ) -> AnalysisEvent:
        self._update_stage(session_id, stage, playback_ms)
        return await self._event_hub.publish(
            session_id,
            AnalysisEventType.SESSION_PROGRESS,
            SessionProgressPayload(
                stage=stage,
                progress=progress,
                message=message,
                inference_fps=inference_fps,
                candidate_count=candidate_count,
                case_count=case_count,
            ),
            playback_ms=playback_ms,
        )

    async def publish_candidate(
        self,
        session_id: str,
        *,
        case_id: str,
        payload: CandidateCreatedPayload,
        playback_ms: int = 0,
    ) -> AnalysisEvent:
        return await self._event_hub.publish(
            session_id,
            AnalysisEventType.CANDIDATE_CREATED,
            payload,
            case_id=case_id,
            playback_ms=playback_ms,
        )

    async def publish_vlm_reviewed(
        self,
        session_id: str,
        *,
        case_id: str,
        payload: VlmReviewedPayload,
        playback_ms: int = 0,
    ) -> AnalysisEvent:
        return await self._event_hub.publish(
            session_id,
            AnalysisEventType.VLM_REVIEWED,
            payload,
            case_id=case_id,
            playback_ms=playback_ms,
        )

    async def publish_case_updated(
        self,
        session_id: str,
        *,
        case_id: str,
        payload: CaseUpdatedPayload,
        playback_ms: int = 0,
    ) -> AnalysisEvent:
        return await self._event_hub.publish(
            session_id,
            AnalysisEventType.CASE_UPDATED,
            payload,
            case_id=case_id,
            playback_ms=playback_ms,
        )

    async def finish_session(
        self, session_id: str, *, candidate_count: int, case_count: int
    ) -> AnalysisEvent:
        event = await self._event_hub.publish(
            session_id,
            AnalysisEventType.SESSION_FINISHED,
            SessionFinishedPayload(
                candidate_count=candidate_count, case_count=case_count
            ),
        )
        self._clear_active_session(session_id)
        return event

    async def handle_vlm_processing_failed(
        self, session_id: str, error: VlmProcessingFailed
    ) -> AnalysisEvent:
        return await self._handle_processing_failed(session_id, error)

    async def _handle_processing_failed(
        self,
        session_id: str,
        error: (
            VlmProcessingFailed
            | VideoAnalysisProcessingFailed
            | InvestigationError
        ),
    ) -> AnalysisEvent:
        self._require_session(session_id)
        self._streamable_session_ids.discard(session_id)
        event = await self._event_hub.publish(
            session_id,
            AnalysisEventType.SESSION_FAILED,
            SessionFailedPayload(
                error_code=error.code,
                message=str(error),
                retryable=error.retryable,
            ),
        )
        self._clear_active_session(session_id)
        return event

    async def _execute(self, session: AnalysisSession) -> None:
        try:
            await self._run_session(session, self)
        except asyncio.CancelledError:
            return
        except VlmProcessingFailed as error:
            await self.handle_vlm_processing_failed(session.session_id, error)
        except VideoAnalysisProcessingFailed as error:
            await self._handle_processing_failed(session.session_id, error)
        except InvestigationError as error:
            await self._handle_processing_failed(session.session_id, error)

    def _require_session(self, session_id: str) -> AnalysisSession:
        try:
            return self._sessions[session_id]
        except KeyError as error:
            raise AnalysisSessionNotFound(session_id) from error

    def _update_stage(
        self,
        session_id: str,
        stage: AnalysisStage,
        playback_ms: int,
    ) -> None:
        session = self._require_session(session_id)
        updated = replace(session, stage=stage)
        self._save_session(updated, playback_ms)
        self._sessions[session_id] = updated

    def _clear_active_session(self, session_id: str) -> None:
        if self._active_session_id == session_id:
            self._active_session_id = None
