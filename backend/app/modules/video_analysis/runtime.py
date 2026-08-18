from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

from app.config import Settings
from app.contracts import PpeType
from app.domain.site_context import SiteContextPort
from app.domain.video_analysis import scenario_started_at_on_analysis_date
from app.modules.video_analysis.candidate_aggregator import CandidateAggregator
from app.modules.video_analysis.evidence_store import FileEvidenceStore
from app.modules.video_analysis.observation import CandidateAggregationConfig
from app.modules.video_analysis.video_analysis import VisionVideoAnalysis
from app.services.case_pipeline import CasePipeline

_ML_MODULE_NAME = "siteppe_ml_video_inference"


def build_vision_video_analysis(
    settings: Settings,
    context: SiteContextPort,
    pipeline: CasePipeline,
) -> VisionVideoAnalysis:
    if not settings.yolo_weights_path:
        raise ValueError("YOLO_WEIGHTS_PATH is required when VISION_PROVIDER=yolo")
    weights = Path(settings.yolo_weights_path).expanduser().resolve()
    if not weights.is_file():
        raise FileNotFoundError(f"model weights not found: {weights}")
    weights_sha256 = _sha256(weights)
    config = _aggregation_config(settings)

    def runner_factory():
        runner_class = _load_video_inference_module().VideoInferenceRunner
        return runner_class.from_weights(
            weights,
            target_fps=settings.vision_target_fps,
            confidence=settings.vision_confidence,
            image_size=settings.vision_image_size,
            tracker=settings.vision_tracker,
            device=_parse_device(settings.vision_device),
        )

    def aggregator_factory(session, video):
        return CandidateAggregator(
            session_id=session.session_id,
            camera_id=video.camera_id,
            scene_started_at=scenario_started_at_on_analysis_date(
                video.scenario_started_at,
                session.started_at,
            ),
            model_name=settings.vision_model_name,
            model_version=settings.vision_model_version,
            weights_sha256=weights_sha256,
            config=config,
        )

    return VisionVideoAnalysis(
        context,
        pipeline,
        runner_factory=runner_factory,
        aggregator_factory=aggregator_factory,
        evidence_store=FileEvidenceStore(Path(settings.vision_evidence_root)),
        jpeg_encoder=_encode_jpeg,
        inference_fps=settings.vision_target_fps,
    )


def _aggregation_config(settings: Settings) -> CandidateAggregationConfig:
    negative = settings.vision_minimum_negative_observations
    return CandidateAggregationConfig(
        minimum_person_height_px=settings.vision_minimum_person_height_px,
        boundary_margin_px=settings.vision_boundary_margin_px,
        maximum_person_overlap_iou=settings.vision_maximum_person_overlap_iou,
        minimum_track_observations=settings.vision_minimum_track_observations,
        minimum_valid_observations=settings.vision_minimum_valid_observations,
        maximum_observation_gap_ms=settings.vision_maximum_observation_gap_ms,
        minimum_negative_observations={
            PpeType.HELMET: negative,
            PpeType.GLOVES: negative,
            PpeType.VEST: negative,
        },
        class_confidence_thresholds={
            "person": 0.5,
            "helmet": 0.5,
            "no_helmet": 0.6,
            "gloves": 0.5,
            "vest": 0.5,
        },
    )


def _encode_jpeg(frame: Any) -> bytes:
    import cv2

    encoded, buffer = cv2.imencode(".jpg", frame)
    if not encoded:
        raise ValueError("unable to encode annotated frame as JPEG")
    return bytes(buffer)


def _load_video_inference_module() -> ModuleType:
    existing = sys.modules.get(_ML_MODULE_NAME)
    if existing is not None:
        return existing
    module_path = Path(__file__).resolve().parents[4] / "ml" / "video_inference.py"
    spec = importlib.util.spec_from_file_location(_ML_MODULE_NAME, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"unable to load video inference module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[_ML_MODULE_NAME] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(_ML_MODULE_NAME, None)
        raise
    return module


def _parse_device(value: str) -> str | int | None:
    if value.lower() == "auto":
        return None
    try:
        return int(value)
    except ValueError:
        return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
