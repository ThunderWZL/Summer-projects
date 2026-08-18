from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.config import Settings
from app.domain.site_context import VideoInfo
from app.modules.video_analysis.runtime import (
    _load_video_inference_module,
    build_vision_video_analysis,
)


def test_runtime_loads_the_real_video_inference_runner_from_ml_source() -> None:
    module = _load_video_inference_module()

    assert module.VideoInferenceRunner.__name__ == "VideoInferenceRunner"
    assert Path(module.__file__).as_posix().endswith("/ml/video_inference.py")


def test_real_provider_requires_existing_model_weights(tmp_path) -> None:
    settings = Settings(
        vision_provider="yolo",
        yolo_weights_path=str(tmp_path / "missing.pt"),
    )

    with pytest.raises(FileNotFoundError, match="model weights not found"):
        build_vision_video_analysis(settings, object(), object())


def test_real_provider_anchors_candidate_time_to_analysis_start(tmp_path) -> None:
    weights = tmp_path / "best.pt"
    weights.write_bytes(b"test-weights")
    settings = Settings(
        vision_provider="yolo",
        yolo_weights_path=str(weights),
    )
    analysis_started_at = datetime.fromisoformat("2026-08-18T16:00:00+08:00")
    video = VideoInfo(
        video_id="video-real",
        camera_id="CAM-01",
        title="real video",
        local_path="/configured/input.mp4",
        duration_ms=1_000,
        scenario_started_at=datetime.fromisoformat("2026-08-07T09:00:00+08:00"),
    )
    analysis = build_vision_video_analysis(settings, object(), object())

    aggregator = analysis._aggregator_factory(
        SimpleNamespace(
            session_id="analysis-session-real",
            started_at=analysis_started_at,
        ),
        video,
    )

    assert aggregator.scene_started_at == analysis_started_at
