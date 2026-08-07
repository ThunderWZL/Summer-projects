"""Run rate-limited YOLO inference with persistent ByteTrack identities."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Sequence


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
    """One sampled frame and its tracking result."""

    frame_index: int
    timestamp_ms: int
    image_width: int
    image_height: int
    detections: tuple[TrackedDetection, ...]
    annotated_frame: Any

    @property
    def person_track_ids(self) -> tuple[int, ...]:
        return tuple(
            detection.track_id
            for detection in self.detections
            if detection.class_name.lower() == "person"
            and detection.track_id is not None
        )


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


class VideoInferenceRunner:
    """Decode a video, sample it at a fixed rate, and preserve ByteTrack state."""

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
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not 0 <= confidence <= 1:
            raise ValueError("confidence must be within [0, 1]")
        if image_size <= 0:
            raise ValueError("image_size must be greater than zero")
        if playback_speed <= 0:
            raise ValueError("playback_speed must be greater than zero")
        self.model = model
        self.cv2 = cv2_module
        self.target_fps = target_fps
        self.confidence = confidence
        self.image_size = image_size
        self.tracker = tracker
        self.device = device
        self.playback_speed = playback_speed
        self.monotonic = monotonic
        self.sleep = sleep

    @classmethod
    def from_weights(cls, weights: Path, **kwargs: Any) -> VideoInferenceRunner:
        import cv2
        from ultralytics import YOLO

        if not weights.is_file():
            raise FileNotFoundError(f"model weights not found: {weights}")
        return cls(YOLO(str(weights)), cv2_module=cv2, **kwargs)

    def iter_video(
        self,
        video_path: Path,
        *,
        realtime: bool = False,
        max_inference_frames: int | None = None,
    ) -> Iterator[InferenceFrame]:
        if max_inference_frames is not None and max_inference_frames <= 0:
            raise ValueError("max_inference_frames must be greater than zero")

        capture = self.cv2.VideoCapture(str(video_path))
        if not capture.isOpened():
            capture.release()
            raise ValueError(f"unable to open video: {video_path}")

        source_fps = float(capture.get(self.cv2.CAP_PROP_FPS))
        if source_fps <= 0:
            capture.release()
            raise ValueError(f"video reports an invalid frame rate: {source_fps}")

        sampler = FrameRateSampler(min(self.target_fps, source_fps))
        started_at = self.monotonic()
        frame_index = 0
        inference_frames = 0
        try:
            while True:
                available, frame = capture.read()
                if not available:
                    break
                timestamp_ms = frame_index * 1000.0 / source_fps
                current_frame_index = frame_index
                frame_index += 1
                if not sampler.accepts(timestamp_ms):
                    continue

                if realtime:
                    target_elapsed = timestamp_ms / 1000.0 / self.playback_speed
                    remaining = target_elapsed - (self.monotonic() - started_at)
                    if remaining > 0:
                        self.sleep(remaining)

                results = self.model.track(
                    source=frame,
                    persist=True,
                    tracker=self.tracker,
                    conf=self.confidence,
                    imgsz=self.image_size,
                    device=self.device,
                    verbose=False,
                )
                result = results[0]
                image_height, image_width = frame.shape[:2]
                yield InferenceFrame(
                    frame_index=current_frame_index,
                    timestamp_ms=round(timestamp_ms),
                    image_width=image_width,
                    image_height=image_height,
                    detections=extract_detections(result),
                    annotated_frame=result.plot(),
                )
                inference_frames += 1
                if (
                    max_inference_frames is not None
                    and inference_frames >= max_inference_frames
                ):
                    break
        finally:
            capture.release()


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
    )
    for frame in runner.iter_video(
        args.video,
        realtime=args.realtime,
        max_inference_frames=args.max_frames,
    ):
        print(
            json.dumps(
                {
                    "frame_index": frame.frame_index,
                    "timestamp_ms": frame.timestamp_ms,
                    "detections": len(frame.detections),
                    "person_track_ids": frame.person_track_ids,
                }
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
