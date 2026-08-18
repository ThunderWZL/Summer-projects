import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Event
from types import SimpleNamespace

from app.contracts import AnalysisStage, CaseStatus, PpeType
from app.domain.site_context import VideoInfo
from app.domain.video_analysis import AnalysisSession
from app.modules.video_analysis.candidate_aggregator import CandidateAggregator
from app.modules.video_analysis.evidence_store import FileEvidenceStore
from app.modules.video_analysis.observation import CandidateAggregationConfig
from app.modules.video_analysis.video_analysis import VisionVideoAnalysis
from app.services.event_hub import EventHub
from app.services.session_manager import SessionManager


@dataclass(frozen=True)
class _Detection:
    class_name: str
    confidence: float
    box: tuple[float, float, float, float]
    track_id: int | None


@dataclass(frozen=True)
class _Frame:
    timestamp_ms: int
    image_width: int
    image_height: int
    detections: tuple[_Detection, ...]
    analysis_updated: bool
    annotated_frame: int


class _Context:
    video = VideoInfo(
        video_id="video-real",
        camera_id="CAM-01",
        title="real video",
        local_path="/configured/input.mp4",
        duration_ms=1_000,
        scenario_started_at=datetime(2026, 8, 17, tzinfo=timezone.utc),
    )

    def get_video(self, video_id: str):
        return self.video if video_id == self.video.video_id else None


class _Runner:
    def __init__(self, frames: list[_Frame], release: Event) -> None:
        self.frames = frames
        self.release = release
        self.calls = []

    def iter_video(self, video_path: Path, **kwargs):
        self.calls.append((video_path, kwargs))
        self.release.wait(timeout=1)
        for frame in self.frames:
            if kwargs["stop_requested"]():
                return
            yield frame


class _Pipeline:
    def __init__(self) -> None:
        self.candidates = []

    def ensure_case(self, candidate):
        self.candidates.append(candidate)
        return SimpleNamespace(
            case_id=f"case-{candidate.candidate_id}",
            status=CaseStatus.YOLO_CANDIDATE,
            transitions=[],
        )

    async def process_candidate(self, candidate):
        return SimpleNamespace(
            case_id=f"case-{candidate.candidate_id}",
            vlm_review=None,
            transitions=[],
        )


class _RecordingManager:
    def __init__(self) -> None:
        self.events = []

    async def publish_progress(self, session_id, **kwargs):
        self.events.append(("SESSION_PROGRESS", session_id, kwargs))

    async def publish_candidate(self, session_id, **kwargs):
        self.events.append(("CANDIDATE_CREATED", session_id, kwargs))

    async def publish_vlm_reviewed(self, session_id, **kwargs):
        self.events.append(("VLM_REVIEWED", session_id, kwargs))

    async def publish_case_updated(self, session_id, **kwargs):
        self.events.append(("CASE_UPDATED", session_id, kwargs))

    async def finish_session(self, session_id, **kwargs):
        self.events.append(("SESSION_FINISHED", session_id, kwargs))

def _config() -> CandidateAggregationConfig:
    return CandidateAggregationConfig(
        minimum_person_height_px=100,
        boundary_margin_px=5,
        maximum_person_overlap_iou=0.5,
        minimum_track_observations=1,
        minimum_valid_observations=1,
        maximum_observation_gap_ms=500,
        minimum_negative_observations={PpeType.HELMET: 3},
        class_confidence_thresholds={
            "person": 0.5,
            "helmet": 0.5,
            "no_helmet": 0.6,
            "gloves": 0.5,
            "vest": 0.5,
        },
        enabled_ppe=frozenset({PpeType.HELMET}),
    )


def _frames() -> list[_Frame]:
    detections = (
        _Detection("person", 0.95, (40, 10, 180, 230), 7),
        _Detection("no_helmet", 0.9, (80, 15, 140, 65), None),
    )
    return [
        _Frame(index * 200, 320, 240, detections, True, index)
        for index in range(4)
    ]


def test_one_inference_pass_drives_live_mjpeg_candidate_and_finish(tmp_path) -> None:
    async def scenario():
        release = Event()
        runner = _Runner(_frames(), release)
        pipeline = _Pipeline()
        evidence = FileEvidenceStore(tmp_path)
        context = _Context()
        analysis = VisionVideoAnalysis(
            context,
            pipeline,
            runner_factory=lambda: runner,
            aggregator_factory=lambda session, video: CandidateAggregator(
                session_id=session.session_id,
                camera_id=video.camera_id,
                scene_started_at=video.scenario_started_at,
                model_name="test-yolo",
                model_version="test-v1",
                config=_config(),
            ),
            evidence_store=evidence,
            jpeg_encoder=lambda frame: b"\xff\xd8" + bytes([frame]) + b"\xff\xd9",
            inference_fps=5.0,
        )
        session = AnalysisSession(
            session_id="analysis-session-real",
            video_id="video-real",
            stage=AnalysisStage.STARTING,
            started_at=datetime(2026, 8, 18, tzinfo=timezone.utc),
        )
        manager = _RecordingManager()
        stream_task = asyncio.create_task(_collect_stream(analysis, session.session_id))
        run_task = asyncio.create_task(analysis.run_session(session, manager))
        await asyncio.sleep(0)
        release.set()
        await _wait_task(run_task)
        stream = await _wait_task(stream_task)
        return runner, pipeline, manager.events, stream

    runner, pipeline, events, stream = asyncio.run(scenario())

    assert len(runner.calls) == 1
    assert runner.calls[0][0] == Path("/configured/input.mp4")
    assert runner.calls[0][1]["realtime"] is True
    assert stream.count(b"Content-Type: image/jpeg") >= 1
    assert stream.endswith(b"--frame--\r\n")
    assert len(pipeline.candidates) == 1
    candidate = pipeline.candidates[0]
    assert candidate.ppe_type is PpeType.HELMET
    assert all(frame.image_url.startswith("/evidence/") for frame in candidate.frames)
    assert [event[0] for event in events][-2:] == [
        "CANDIDATE_CREATED",
        "SESSION_FINISHED",
    ]
    assert events[-1][2]["candidate_count"] == 1


def test_stop_waits_until_runner_observes_stop_request(tmp_path) -> None:
    class BlockingRunner:
        def __init__(self) -> None:
            self.started = Event()
            self.stopped = Event()

        def iter_video(self, _video_path: Path, **kwargs):
            self.started.set()
            index = 0
            while not kwargs["stop_requested"]():
                yield _Frame(index, 320, 240, (), False, 0)
                index += 1
                time.sleep(0.005)
            self.stopped.set()

    async def scenario():
        runner = BlockingRunner()
        context = _Context()
        analysis = VisionVideoAnalysis(
            context,
            _Pipeline(),
            runner_factory=lambda: runner,
            aggregator_factory=lambda session, video: CandidateAggregator(
                session_id=session.session_id,
                camera_id=video.camera_id,
                scene_started_at=video.scenario_started_at,
                model_name="test-yolo",
                model_version="test-v1",
                config=_config(),
            ),
            evidence_store=FileEvidenceStore(tmp_path),
            jpeg_encoder=lambda _frame: b"\xff\xd8\xff\xd9",
            inference_fps=5.0,
        )
        manager = SessionManager(
            EventHub(),
            context.get_video,
            analysis.get_stream,
            analysis.run_session,
        )
        session = await manager.start_session("video-real")
        for _ in range(100):
            if runner.started.is_set():
                break
            await asyncio.sleep(0.01)
        assert runner.started.is_set()
        await manager.stop_session(session.session_id)
        return runner.stopped.is_set()

    assert asyncio.run(scenario()) is True


async def _collect_stream(analysis, session_id: str) -> bytes:
    chunks = []
    async for chunk in analysis.get_stream(session_id):
        chunks.append(chunk)
    return b"".join(chunks)


async def _wait_task(task):
    for _ in range(200):
        if task.done():
            return await task
        await asyncio.sleep(0.01)
    raise TimeoutError("async task did not finish")
