from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event, Thread
from typing import Any, Protocol

from app.contracts import (
    AnalysisStage,
    CandidateCreatedPayload,
    CaseStatus,
    CaseUpdatedPayload,
    VlmReviewedPayload,
)
from app.domain.site_context import SiteContextPort, VideoInfo
from app.domain.video_analysis import (
    AnalysisSession,
    VideoAnalysisProcessingFailed,
)
from app.modules.video_analysis.candidate_aggregator import CandidateAggregator
from app.modules.video_analysis.evidence_store import FileEvidenceStore
from app.modules.video_analysis.observation import build_person_frame_observations
from app.services.case_pipeline import CasePipeline
from app.services.session_manager import SessionManager


class TrackedDetectionLike(Protocol):
    class_name: str
    confidence: float
    box: tuple[float, float, float, float]
    track_id: int | None


class InferenceFrameLike(Protocol):
    timestamp_ms: int
    image_width: int
    image_height: int
    detections: tuple[TrackedDetectionLike, ...]
    analysis_updated: bool
    annotated_frame: Any


class VisionRunnerPort(Protocol):
    def iter_video(
        self,
        video_path: Path,
        *,
        realtime: bool = False,
        stop_requested: Callable[[], bool] | None = None,
    ) -> Iterator[InferenceFrameLike]: ...


RunnerFactory = Callable[[], VisionRunnerPort]
AggregatorFactory = Callable[[AnalysisSession, VideoInfo], CandidateAggregator]
JpegEncoder = Callable[[Any], bytes]

_FRAME_HEADER = b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
_STREAM_END = b"--frame--\r\n"
_PRODUCER_FINISHED = object()
_PIPELINE_ACTIONS = {
    CaseStatus.INVESTIGATING: "START_INVESTIGATION",
    CaseStatus.NEEDS_HUMAN_FACTS: "RECORD_INVESTIGATION",
    CaseStatus.PENDING_REVIEW: "RECORD_INVESTIGATION",
}


@dataclass
class _SessionState:
    changed: asyncio.Event = field(default_factory=asyncio.Event)
    stop_requested: Event = field(default_factory=Event)
    latest_jpeg: bytes | None = None
    version: int = 0
    finished: bool = False

    def publish_frame(self, jpeg: bytes) -> None:
        self.latest_jpeg = jpeg
        self.version += 1
        self.changed.set()

    def finish(self) -> None:
        self.finished = True
        self.changed.set()


class VisionVideoAnalysis:
    """Run one YOLO/ByteTrack pass and fan it out to stream and case events."""

    def __init__(
        self,
        context: SiteContextPort,
        pipeline: CasePipeline,
        *,
        runner_factory: RunnerFactory,
        aggregator_factory: AggregatorFactory,
        evidence_store: FileEvidenceStore,
        jpeg_encoder: JpegEncoder,
        inference_fps: float,
    ) -> None:
        if inference_fps <= 0:
            raise ValueError("inference_fps must be greater than zero")
        self._context = context
        self._pipeline = pipeline
        self._runner_factory = runner_factory
        self._aggregator_factory = aggregator_factory
        self._evidence_store = evidence_store
        self._jpeg_encoder = jpeg_encoder
        self._inference_fps = inference_fps
        self._states: dict[str, _SessionState] = {}

    async def get_stream(self, session_id: str) -> AsyncIterator[bytes]:
        state = self._state(session_id)
        seen_version = 0
        while True:
            while state.version == seen_version and not state.finished:
                state.changed.clear()
                await state.changed.wait()
            if state.version != seen_version and state.latest_jpeg is not None:
                seen_version = state.version
                yield _FRAME_HEADER + state.latest_jpeg + b"\r\n"
            if state.finished:
                break
        yield _STREAM_END

    async def run_session(
        self,
        session: AnalysisSession,
        manager: SessionManager,
    ) -> None:
        video = self._context.get_video(session.video_id)
        if video is None:
            raise VideoAnalysisProcessingFailed(
                f"analysis video {session.video_id} disappeared before processing"
            )
        state = self._state(session.session_id)
        candidate_queue: asyncio.Queue[object] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        await manager.publish_progress(
            session.session_id,
            stage=AnalysisStage.STARTING,
            progress=0.0,
            message="analysis session started",
        )
        await manager.publish_progress(
            session.session_id,
            stage=AnalysisStage.READING,
            progress=0.1,
            message="reading configured video",
        )
        await manager.publish_progress(
            session.session_id,
            stage=AnalysisStage.INFERENCING,
            progress=0.2,
            message="running YOLO and ByteTrack inference",
            inference_fps=self._inference_fps,
        )

        producer_errors: list[BaseException] = []
        producer = Thread(
            target=self._produce_safely,
            args=(
                producer_errors,
                loop,
                state,
                candidate_queue,
                session,
                video,
            ),
            name=f"vision-{session.session_id}",
            daemon=True,
        )
        producer.start()
        candidate_count = 0
        case_ids: set[str] = set()
        try:
            while True:
                item = await candidate_queue.get()
                if item is _PRODUCER_FINISHED:
                    break
                candidate_count += 1
                case_id = await self._process_candidate(
                    session.session_id,
                    item,
                    manager,
                )
                case_ids.add(case_id)
            await self._wait_for_thread(producer)
            if producer_errors:
                error = producer_errors[0]
                raise VideoAnalysisProcessingFailed(str(error)) from error
            await manager.finish_session(
                session.session_id,
                candidate_count=candidate_count,
                case_count=len(case_ids),
            )
        except asyncio.CancelledError:
            state.stop_requested.set()
            await self._wait_for_thread(producer)
            raise
        except Exception:
            state.stop_requested.set()
            await self._wait_for_thread(producer)
            raise
        finally:
            state.finish()

    def _produce_safely(
        self,
        errors: list[BaseException],
        loop: asyncio.AbstractEventLoop,
        state: _SessionState,
        candidate_queue: asyncio.Queue[object],
        session: AnalysisSession,
        video: VideoInfo,
    ) -> None:
        try:
            self._produce(loop, state, candidate_queue, session, video)
        except BaseException as error:
            errors.append(error)

    @staticmethod
    async def _wait_for_thread(thread: Thread) -> None:
        while thread.is_alive():
            await asyncio.sleep(0.01)
        thread.join()

    def _produce(
        self,
        loop: asyncio.AbstractEventLoop,
        state: _SessionState,
        candidate_queue: asyncio.Queue[object],
        session: AnalysisSession,
        video: VideoInfo,
    ) -> None:
        try:
            runner = self._runner_factory()
            aggregator = self._aggregator_factory(session, video)
            for frame in runner.iter_video(
                Path(video.local_path),
                realtime=True,
                stop_requested=state.stop_requested.is_set,
            ):
                jpeg = self._jpeg_encoder(frame.annotated_frame)
                loop.call_soon_threadsafe(state.publish_frame, jpeg)
                if not frame.analysis_updated:
                    continue
                image_url = self._evidence_store.store_jpeg(
                    session_id=session.session_id,
                    timestamp_ms=frame.timestamp_ms,
                    jpeg_bytes=jpeg,
                )
                observations = build_person_frame_observations(
                    timestamp_ms=frame.timestamp_ms,
                    image_url=image_url,
                    image_width=frame.image_width,
                    image_height=frame.image_height,
                    detections=frame.detections,
                )
                for observation in observations:
                    for candidate in aggregator.observe(observation):
                        loop.call_soon_threadsafe(
                            candidate_queue.put_nowait,
                            candidate,
                        )
        finally:
            loop.call_soon_threadsafe(
                candidate_queue.put_nowait,
                _PRODUCER_FINISHED,
            )

    async def _process_candidate(
        self,
        session_id: str,
        candidate: Any,
        manager: SessionManager,
    ) -> str:
        case = self._pipeline.ensure_case(candidate)
        is_new_candidate = (
            case.status is CaseStatus.YOLO_CANDIDATE and not case.transitions
        )
        await manager.publish_candidate(
            session_id,
            case_id=case.case_id,
            payload=CandidateCreatedPayload(
                candidate_id=candidate.candidate_id,
                ppe_type=candidate.ppe_type,
                confidence=candidate.confidence,
                candidate_occurred_at=candidate.occurred_at,
                person_track_id=candidate.person_track_id,
            ),
            playback_ms=candidate.last_seen_ms,
        )
        result = await self._pipeline.process_candidate(candidate)
        if is_new_candidate and result.vlm_review is not None:
            await manager.publish_vlm_reviewed(
                session_id,
                case_id=result.case_id,
                payload=VlmReviewedPayload(
                    verdict=result.vlm_review.verdict,
                    evidence_sufficient=result.vlm_review.evidence_sufficient,
                    reason=result.vlm_review.reason,
                    status=result.transitions[0].to_status,
                    version=2,
                ),
                playback_ms=candidate.last_seen_ms,
            )
            for version, transition in enumerate(result.transitions[1:], start=3):
                await manager.publish_case_updated(
                    session_id,
                    case_id=result.case_id,
                    payload=CaseUpdatedPayload(
                        status=transition.to_status,
                        version=version,
                        updated_at=transition.occurred_at,
                        action=_PIPELINE_ACTIONS[transition.to_status],
                    ),
                    playback_ms=candidate.last_seen_ms,
                )
        return result.case_id

    def _state(self, session_id: str) -> _SessionState:
        return self._states.setdefault(session_id, _SessionState())
