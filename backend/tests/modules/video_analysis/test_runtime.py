from pathlib import Path

import pytest

from app.config import Settings
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
