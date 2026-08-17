from dataclasses import dataclass
from datetime import datetime, timedelta

from app.contracts import CandidateEvidence, EvidenceKind, FrameRole, PpeType
from app.domain.site_context import VideoInfo

_SCENARIO_STARTED_AT = datetime.fromisoformat("2026-08-07T09:00:00+08:00")


@dataclass(frozen=True, slots=True)
class _ScenarioCandidate:
    ppe_type: PpeType
    representative_ms: int
    person_key: str


_SCENES: dict[str, tuple[_ScenarioCandidate, ...]] = {
    "CAM-01": (),
    "CAM-02": (_ScenarioCandidate(PpeType.VEST, 150_000, "person-01"),),
    "CAM-03": (_ScenarioCandidate(PpeType.GLOVES, 210_000, "person-01"),),
    "CAM-04": (
        _ScenarioCandidate(PpeType.VEST, 270_000, "person-01"),
        _ScenarioCandidate(PpeType.GLOVES, 270_000, "person-01"),
    ),
    "CAM-05": (
        _ScenarioCandidate(PpeType.HELMET, 300_000, "person-01"),
        _ScenarioCandidate(PpeType.GLOVES, 300_000, "person-01"),
        _ScenarioCandidate(PpeType.VEST, 300_000, "person-01"),
    ),
    "CAM-06": (
        _ScenarioCandidate(PpeType.HELMET, 330_000, "person-01"),
        _ScenarioCandidate(PpeType.GLOVES, 330_000, "person-01"),
        _ScenarioCandidate(PpeType.HELMET, 360_000, "person-02"),
        _ScenarioCandidate(PpeType.GLOVES, 360_000, "person-02"),
        _ScenarioCandidate(PpeType.HELMET, 390_000, "person-03"),
        _ScenarioCandidate(PpeType.GLOVES, 390_000, "person-03"),
        _ScenarioCandidate(PpeType.VEST, 390_000, "person-03"),
    ),
}


def _evidence_kind(ppe_type: PpeType) -> EvidenceKind:
    if ppe_type is PpeType.HELMET:
        return EvidenceKind.NEGATIVE_CLASS_DETECTION
    return EvidenceKind.MISSING_POSITIVE_ASSOCIATION


def build_fixture_candidate(
    camera_id: str,
    session_id: str,
    namespace: str = "analysis",
    candidate_suffix: str = "primary",
    *,
    ppe_type: PpeType | None = None,
    representative_ms: int | None = None,
    person_track_id: str | None = None,
) -> CandidateEvidence | None:
    if ppe_type is None:
        scenarios = _SCENES.get(camera_id, ())
        if not scenarios:
            return None
        scenario = scenarios[0]
        ppe_type = scenario.ppe_type
        representative_ms = scenario.representative_ms
        person_track_id = f"track-{camera_id.lower()}-{scenario.person_key}"
    else:
        representative_ms = representative_ms or 90_000
    evidence_kind = _evidence_kind(ppe_type)
    timestamps = (
        representative_ms - 1_000,
        representative_ms,
        representative_ms + 1_000,
    )
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
            "person_track_id": (
                person_track_id
                or f"track-{camera_id.lower()}-{ppe_type.value}"
            ),
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
            "occurred_at": _SCENARIO_STARTED_AT
            + timedelta(milliseconds=representative_ms),
            "first_seen_ms": representative_ms - 500,
            "last_seen_ms": representative_ms + 500,
            "frames": frames,
        }
    )


def candidates_for_video(
    video: VideoInfo,
    session_id: str,
) -> list[CandidateEvidence]:
    candidates = []
    for scenario in _SCENES.get(video.camera_id, ()):
        candidate = build_fixture_candidate(
            video.camera_id,
            session_id,
            candidate_suffix=scenario.person_key,
            ppe_type=scenario.ppe_type,
            representative_ms=scenario.representative_ms,
            person_track_id=(
                f"track-{video.camera_id.lower()}-{scenario.person_key}"
            ),
        )
        if candidate is not None:
            candidates.append(candidate)
    return candidates
