"""Run smooth video playback with rate-limited YOLO and ByteTrack analysis."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Full, Queue
from threading import Lock, Thread
from typing import Any, Callable, Iterator, Mapping, Sequence

import numpy as np
from numpy.typing import NDArray


FrameArray = NDArray[np.uint8]


@dataclass(frozen=True)
class TrackedDetection:
    """A detection expressed in original-frame pixel coordinates."""

    class_id: int
    class_name: str
    confidence: float
    box: tuple[float, float, float, float]
    track_id: int | None


@dataclass(frozen=True)
class InferenceFrame:
    """One full-rate playback frame with the latest available AI overlay."""

    frame_index: int
    timestamp_ms: int
    image_width: int
    image_height: int
    source_fps: float
    detections: tuple[TrackedDetection, ...]
    analysis_timestamp_ms: int | None
    analysis_updated: bool
    annotated_frame: FrameArray

    @property
    def person_track_ids(self) -> tuple[int, ...]:
        return tuple(
            detection.track_id
            for detection in self.detections
            if detection.class_name.lower() == "person"
            and detection.track_id is not None
        )


@dataclass(frozen=True)
class VideoOutputSummary:
    output_path: str
    frame_count: int
    image_width: int
    image_height: int
    fps: float


@dataclass(frozen=True)
class _InferenceRequest:
    frame: FrameArray
    timestamp_ms: int


@dataclass(frozen=True)
class _AnalysisSnapshot:
    version: int
    timestamp_ms: int
    detections: tuple[TrackedDetection, ...]


class FrameRateSampler:
    """Select timestamps at a stable target rate without cumulative rounding drift."""

    def __init__(self, target_fps: float) -> None:
        if target_fps <= 0:
            raise ValueError("target_fps must be greater than zero")
        self.interval_ms = 1000.0 / target_fps
        self.next_timestamp_ms = 0.0

    def accepts(self, timestamp_ms: float) -> bool:
        if timestamp_ms + 1e-9 < self.next_timestamp_ms:
            return False
        while self.next_timestamp_ms <= timestamp_ms + 1e-9:
            self.next_timestamp_ms += self.interval_ms
        return True


class RealtimePacer:
    """Pace frames without emitting a burst to catch up after a late frame."""

    def __init__(
        self,
        source_fps: float,
        playback_speed: float,
        *,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if source_fps <= 0:
            raise ValueError("source_fps must be greater than zero")
        if playback_speed <= 0:
            raise ValueError("playback_speed must be greater than zero")
        self.interval_seconds = 1.0 / (source_fps * playback_speed)
        self.monotonic = monotonic
        self.sleep = sleep
        self.next_deadline: float | None = None

    def wait(self) -> None:
        now = self.monotonic()
        if self.next_deadline is None:
            self.next_deadline = now + self.interval_seconds
            return

        remaining = self.next_deadline - now
        if remaining > 0:
            self.sleep(remaining)
            self.next_deadline += self.interval_seconds
            return

        # Rebase after a late frame instead of immediately emitting catch-up frames.
        self.next_deadline = now + self.interval_seconds


def _to_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "tolist"):
        value = value.tolist()
    return list(value)


def extract_detections(result: Any) -> tuple[TrackedDetection, ...]:
    """Convert an Ultralytics result into dependency-free tracking records."""

    boxes = getattr(result, "boxes", None)
    if boxes is None:
        return ()

    coordinates = _to_list(getattr(boxes, "xyxy", None))
    confidences = _to_list(getattr(boxes, "conf", None))
    class_ids = _to_list(getattr(boxes, "cls", None))
    raw_track_ids = getattr(boxes, "id", None)
    track_ids = _to_list(raw_track_ids) if raw_track_ids is not None else []
    names: Mapping[int, str] | Sequence[str] = getattr(result, "names", {})

    detections = []
    for index, (coordinate, confidence, class_id) in enumerate(
        zip(coordinates, confidences, class_ids)
    ):
        integer_class_id = int(class_id)
        if isinstance(names, Mapping):
            class_name = str(names.get(integer_class_id, integer_class_id))
        else:
            class_name = str(names[integer_class_id])
        track_id = int(track_ids[index]) if index < len(track_ids) else None
        detections.append(
            TrackedDetection(
                class_id=integer_class_id,
                class_name=class_name,
                confidence=float(confidence),
                box=tuple(float(value) for value in coordinate),
                track_id=track_id,
            )
        )
    return tuple(detections)


class _LatestInferenceWorker:
    """Run inference off the playback path and keep only the newest pending sample."""

    _STOP = object()

    def __init__(
        self,
        infer: Callable[[FrameArray], tuple[TrackedDetection, ...]],
    ) -> None:
        self.infer = infer
        self.requests: Queue[_InferenceRequest | object] = Queue(maxsize=1)
        self.lock = Lock()
        self.snapshot: _AnalysisSnapshot | None = None
        self.error: Exception | None = None
        self.version = 0
        self.thread = Thread(target=self._run, name="video-inference", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def submit_latest(self, frame: FrameArray, timestamp_ms: int) -> None:
        request = _InferenceRequest(frame=frame.copy(), timestamp_ms=timestamp_ms)
        try:
            self.requests.put_nowait(request)
            return
        except Full:
            pass

        try:
            self.requests.get_nowait()
        except Empty:
            pass
        self.requests.put_nowait(request)

    def latest_after(self, version: int) -> _AnalysisSnapshot | None:
        with self.lock:
            self._raise_if_failed()
            if self.snapshot is None or self.snapshot.version <= version:
                return None
            return self.snapshot

    def close(self, timeout_seconds: float) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        while True:
            try:
                self.requests.get_nowait()
            except Empty:
                break
        self.requests.put_nowait(self._STOP)
        self.thread.join(timeout_seconds)
        if self.thread.is_alive():
            raise RuntimeError(
                "background video inference did not stop within "
                f"{timeout_seconds:g} seconds"
            )
        with self.lock:
            self._raise_if_failed()

    def _raise_if_failed(self) -> None:
        if self.error is not None:
            raise RuntimeError("background video inference failed") from self.error

    def _run(self) -> None:
        while True:
            request = self.requests.get()
            if request is self._STOP:
                return
            assert isinstance(request, _InferenceRequest)
            try:
                detections = self.infer(request.frame)
            except Exception as exc:
                with self.lock:
                    self.error = exc
                return
            with self.lock:
                self.version += 1
                self.snapshot = _AnalysisSnapshot(
                    version=self.version,
                    timestamp_ms=request.timestamp_ms,
                    detections=detections,
                )


class VideoInferenceRunner:
    """Play every source frame while analyzing only rate-limited samples."""

    def __init__(
        self,
        model: Any,
        *,
        cv2_module: Any,
        target_fps: float = 5.0,
        confidence: float = 0.25,
        image_size: int = 640,
        tracker: str = "bytetrack.yaml",
        device: str | int | None = None,
        playback_speed: float = 1.0,
        renderer: Callable[
            [FrameArray, tuple[TrackedDetection, ...]], FrameArray
        ]
        | None = None,
        worker_shutdown_timeout_seconds: float = 10.0,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if target_fps <= 0:
            raise ValueError("target_fps must be greater than zero")
        if not 0 <= confidence <= 1:
            raise ValueError("confidence must be within [0, 1]")
        if image_size <= 0:
            raise ValueError("image_size must be greater than zero")
        if playback_speed <= 0:
            raise ValueError("playback_speed must be greater than zero")
        if worker_shutdown_timeout_seconds <= 0:
            raise ValueError(
                "worker_shutdown_timeout_seconds must be greater than zero"
            )
        self.model = model
        self.cv2 = cv2_module
        self.target_fps = target_fps
        self.confidence = confidence
        self.image_size = image_size
        self.tracker = tracker
        self.device = device
        self.playback_speed = playback_speed
        self.renderer = renderer or self._render_detections
        self.worker_shutdown_timeout_seconds = worker_shutdown_timeout_seconds
        self.monotonic = monotonic
        self.sleep = sleep

    @classmethod
    def from_weights(cls, weights: Path, **kwargs: Any) -> VideoInferenceRunner:
        import cv2
        from ultralytics import YOLO

        if not weights.is_file():
            raise FileNotFoundError(f"model weights not found: {weights}")
        return cls(YOLO(str(weights)), cv2_module=cv2, **kwargs)

    def _infer(self, frame: FrameArray) -> tuple[TrackedDetection, ...]:
        results = self.model.track(
            source=frame,
            persist=True,
            tracker=self.tracker,
            conf=self.confidence,
            imgsz=self.image_size,
            device=self.device,
            verbose=False,
        )
        if not results:
            return ()
        return extract_detections(results[0])

    def _render_detections(
        self,
        frame: FrameArray,
        detections: tuple[TrackedDetection, ...],
    ) -> FrameArray:
        annotated = frame.copy()
        for detection in detections:
            x1, y1, x2, y2 = (round(value) for value in detection.box)
            color = (
                (0, 200, 0)
                if detection.class_name.lower() == "person"
                else (0, 0, 255)
            )
            self.cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            identity = (
                f" #{detection.track_id}" if detection.track_id is not None else ""
            )
            label = f"{detection.class_name}{identity} {detection.confidence:.2f}"
            self.cv2.putText(
                annotated,
                label,
                (x1, max(18, y1 - 6)),
                self.cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                1,
                self.cv2.LINE_AA,
            )
        return annotated

    def iter_video(
        self,
        video_path: Path,
        *,
        realtime: bool = False,
        max_playback_frames: int | None = None,
    ) -> Iterator[InferenceFrame]:
        if max_playback_frames is not None and max_playback_frames <= 0:
            raise ValueError("max_playback_frames must be greater than zero")

        capture = self.cv2.VideoCapture(str(video_path))
        if not capture.isOpened():
            capture.release()
            raise ValueError(f"unable to open video: {video_path}")

        source_fps = float(capture.get(self.cv2.CAP_PROP_FPS))
        if source_fps <= 0:
            capture.release()
            raise ValueError(f"video reports an invalid frame rate: {source_fps}")

        sampler = FrameRateSampler(min(self.target_fps, source_fps))
        pacer = (
            RealtimePacer(
                source_fps,
                self.playback_speed,
                monotonic=self.monotonic,
                sleep=self.sleep,
            )
            if realtime
            else None
        )
        worker = _LatestInferenceWorker(self._infer) if realtime else None
        if worker is not None:
            worker.start()

        frame_index = 0
        playback_frames = 0
        snapshot_version = 0
        detections: tuple[TrackedDetection, ...] = ()
        analysis_timestamp_ms: int | None = None
        try:
            while True:
                available, frame = capture.read()
                if not available:
                    break
                timestamp_ms = round(frame_index * 1000.0 / source_fps)
                current_frame_index = frame_index
                frame_index += 1
                analysis_updated = False

                if sampler.accepts(timestamp_ms):
                    if worker is None:
                        detections = self._infer(frame)
                        analysis_timestamp_ms = timestamp_ms
                        analysis_updated = True
                    elif analysis_timestamp_ms is None:
                        # Warm model and tracker before the playback clock starts.
                        detections = self._infer(frame)
                        analysis_timestamp_ms = timestamp_ms
                        analysis_updated = True
                    else:
                        worker.submit_latest(frame, timestamp_ms)

                if worker is not None:
                    snapshot = worker.latest_after(snapshot_version)
                    if snapshot is not None:
                        snapshot_version = snapshot.version
                        detections = snapshot.detections
                        analysis_timestamp_ms = snapshot.timestamp_ms
                        analysis_updated = True

                annotated = self.renderer(frame, detections)
                if pacer is not None:
                    pacer.wait()
                playback_frames += 1
                yield InferenceFrame(
                    frame_index=current_frame_index,
                    timestamp_ms=timestamp_ms,
                    image_width=int(frame.shape[1]),
                    image_height=int(frame.shape[0]),
                    source_fps=source_fps,
                    detections=detections,
                    analysis_timestamp_ms=analysis_timestamp_ms,
                    analysis_updated=analysis_updated,
                    annotated_frame=annotated,
                )
                if (
                    max_playback_frames is not None
                    and playback_frames >= max_playback_frames
                ):
                    break
        finally:
            try:
                if worker is not None:
                    worker.close(self.worker_shutdown_timeout_seconds)
            finally:
                capture.release()


def write_annotated_video(
    runner: VideoInferenceRunner,
    video_path: Path,
    output_path: Path,
    *,
    realtime: bool = False,
    max_playback_frames: int | None = None,
) -> VideoOutputSummary:
    """Write every annotated playback frame to a new MP4 file."""

    if video_path.resolve() == output_path.resolve():
        raise ValueError("output video must not overwrite the input video")
    if output_path.exists():
        raise FileExistsError(f"output video already exists: {output_path}")
    if not output_path.parent.is_dir():
        raise FileNotFoundError(
            f"output video directory does not exist: {output_path.parent}"
        )

    writer: Any | None = None
    frame_count = 0
    image_width = 0
    image_height = 0
    source_fps = 0.0
    try:
        for frame in runner.iter_video(
            video_path,
            realtime=realtime,
            max_playback_frames=max_playback_frames,
        ):
            if writer is None:
                image_width = frame.image_width
                image_height = frame.image_height
                source_fps = frame.source_fps
                codec = runner.cv2.VideoWriter_fourcc(*"mp4v")
                writer = runner.cv2.VideoWriter(
                    str(output_path),
                    codec,
                    source_fps,
                    (image_width, image_height),
                )
                if not writer.isOpened():
                    raise ValueError(f"unable to open output video: {output_path}")
            writer.write(frame.annotated_frame)
            frame_count += 1
    finally:
        if writer is not None:
            writer.release()

    if frame_count == 0:
        raise ValueError(f"input video contains no frames: {video_path}")
    return VideoOutputSummary(
        output_path=str(output_path),
        frame_count=frame_count,
        image_width=image_width,
        image_height=image_height,
        fps=source_fps,
    )


def _parse_device(value: str) -> str | int | None:
    if value.lower() == "auto":
        return None
    try:
        return int(value)
    except ValueError:
        return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--fps", type=float, default=5.0)
    parser.add_argument("--confidence", type=float, default=0.25)
    parser.add_argument("--image-size", type=int, default=640)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--tracker", default="bytetrack.yaml")
    parser.add_argument("--playback-speed", type=float, default=1.0)
    parser.add_argument("--realtime", action="store_true")
    parser.add_argument("--max-frames", type=int)
    parser.add_argument("--shutdown-timeout", type=float, default=10.0)
    parser.add_argument("--output-video", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runner = VideoInferenceRunner.from_weights(
        args.weights,
        target_fps=args.fps,
        confidence=args.confidence,
        image_size=args.image_size,
        tracker=args.tracker,
        device=_parse_device(args.device),
        playback_speed=args.playback_speed,
        worker_shutdown_timeout_seconds=args.shutdown_timeout,
    )
    if args.output_video is not None:
        summary = write_annotated_video(
            runner,
            args.video,
            args.output_video,
            realtime=args.realtime,
            max_playback_frames=args.max_frames,
        )
        print(json.dumps(summary.__dict__))
    else:
        for frame in runner.iter_video(
            args.video,
            realtime=args.realtime,
            max_playback_frames=args.max_frames,
        ):
            print(
                json.dumps(
                    {
                        "frame_index": frame.frame_index,
                        "timestamp_ms": frame.timestamp_ms,
                        "analysis_timestamp_ms": frame.analysis_timestamp_ms,
                        "analysis_updated": frame.analysis_updated,
                        "detections": len(frame.detections),
                        "person_track_ids": frame.person_track_ids,
                    }
                )
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
