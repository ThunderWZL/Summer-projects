from datetime import timedelta

from app.contracts import CandidateEvidence, EvidenceKind, FrameRole, PpeType
from app.domain.inmemory.site_context import SCENARIO_STARTED_AT
from app.domain.site_context import VideoInfo


_SCENES: dict[str, tuple[PpeType, EvidenceKind, int]] = {
    "CAM-01": (PpeType.HELMET, EvidenceKind.NEGATIVE_CLASS_DETECTION, 90_000),
    "CAM-02": (PpeType.HELMET, EvidenceKind.NEGATIVE_CLASS_DETECTION, 150_000),
    "CAM-03": (PpeType.GLOVES, EvidenceKind.MISSING_POSITIVE_ASSOCIATION, 210_000),
    "CAM-04": (PpeType.GLOVES, EvidenceKind.MISSING_POSITIVE_ASSOCIATION, 270_000),
    "CAM-05": (PpeType.VEST, EvidenceKind.MISSING_POSITIVE_ASSOCIATION, 330_000),
}


def build_fixture_candidate(
    camera_id: str,
    session_id: str,
    namespace: str = "analysis",
    candidate_suffix: str = "primary",
) -> CandidateEvidence | None:
    scene = _SCENES.get(camera_id)
    if scene is None:
        return None
    ppe_type, evidence_kind, representative_ms = scene
    timestamps = (representative_ms - 1_000, representative_ms, representative_ms + 1_000)
    frames = []
    roles = (FrameRole.BEFORE, FrameRole.REPRESENTATIVE, FrameRole.AFTER)
    for timestamp_ms, role in zip(timestamps, roles, strict=True):
        observation = evidence_kind is EvidenceKind.NEGATIVE_CLASS_DETECTION
        frames.append(
            {
                "timestamp_ms": timestamp_ms,
                "image_url": (
                    f"/evidence/{namespace}/{camera_id.lower()}/"
                    f"{ppe_type.value}-{timestamp_ms}.jpg"
                ),
                "image_width": 1920,
                "image_height": 1080,
                "frame_role": role,
                "person_box": {
                    "x1": 720,
                    "y1": 210,
                    "x2": 980,
                    "y2": 930,
                },
                "observation_box": (
                    {"x1": 760, "y1": 230, "x2": 900, "y2": 390}
                    if observation
                    else None
                ),
                "observation_confidence": 0.92 if observation else None,
            }
        )
    return CandidateEvidence.model_validate(
        {
            "candidate_id": (
                f"candidate-{namespace}-{camera_id.lower()}-{ppe_type.value}-"
                f"{representative_ms}-{candidate_suffix}"
            ),
            "session_id": session_id,
            "camera_id": camera_id,
            "person_track_id": f"track-{camera_id.lower()}-{ppe_type.value}",
            "ppe_type": ppe_type,
            "evidence_kind": evidence_kind,
            "confidence": 0.91,
            "model_name": "fixture-yolo",
            "weights_sha256": "a" * 64,
            "aggregation_method": "fixture_three_frame_window",
            "aggregation_parameters": {
                "minimum_frames": 3,
                "window_ms": 2_000,
            },
            "occurred_at": SCENARIO_STARTED_AT
            + timedelta(milliseconds=representative_ms),
            "first_seen_ms": representative_ms - 500,
            "last_seen_ms": representative_ms + 500,
            "frames": frames,
        }
    )


def candidate_for_video(
    video: VideoInfo,
    session_id: str,
) -> CandidateEvidence | None:
    return build_fixture_candidate(video.camera_id, session_id)
