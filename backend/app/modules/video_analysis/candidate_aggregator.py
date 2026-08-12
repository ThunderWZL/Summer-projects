from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from uuid import NAMESPACE_URL, uuid5

from app.contracts import (
    CandidateEvidence,
    EvidenceFrame,
    EvidenceKind,
    FrameRole,
    PpeType,
)
from app.modules.video_analysis.observation import (
    CandidateAggregationConfig,
    DetectionObservation,
    EvaluabilityGate,
    PersonFrameObservation,
    PpeObservationState,
    classify_ppe,
)


AGGREGATION_METHOD = "consecutive-evaluable-observations-v1"


@dataclass
class _NegativeSequence:
    frames: list[PersonFrameObservation] = field(default_factory=list)
    emitted: bool = False


class CandidateAggregator:
    """Aggregate one deduplicated candidate per continuous track/PPE sequence."""

    def __init__(
        self,
        *,
        session_id: str,
        camera_id: str,
        scene_started_at: datetime,
        model_name: str,
        config: CandidateAggregationConfig,
        model_version: str | None = None,
        weights_sha256: str | None = None,
    ) -> None:
        if not session_id or not camera_id or not model_name:
            raise ValueError("session_id, camera_id, and model_name must not be empty")
        if scene_started_at.tzinfo is None or scene_started_at.utcoffset() is None:
            raise ValueError("scene_started_at must include a UTC offset")
        if model_version is None and weights_sha256 is None:
            raise ValueError("model_version or weights_sha256 is required")
        self.session_id = session_id
        self.camera_id = camera_id
        self.scene_started_at = scene_started_at
        self.model_name = model_name
        self.model_version = model_version
        self.weights_sha256 = weights_sha256
        self.config = config
        self.gate = EvaluabilityGate(config)
        self._sequences: dict[tuple[str, PpeType], _NegativeSequence] = {}

    def observe(
        self, frame: PersonFrameObservation
    ) -> tuple[CandidateEvidence, ...]:
        evaluability = self.gate.evaluate(frame)
        candidates = []
        for ppe_type in sorted(self.config.enabled_ppe, key=lambda item: item.value):
            key = (frame.person_track_id, ppe_type)
            state = classify_ppe(frame, ppe_type, evaluability, self.config)
            if state is not PpeObservationState.NEGATIVE:
                self._sequences.pop(key, None)
                continue
            sequence = self._sequences.setdefault(key, _NegativeSequence())
            if sequence.emitted:
                continue
            sequence.frames.append(frame)
            required = self.config.minimum_negative_observations[ppe_type]
            if len(sequence.frames) < required:
                continue
            candidate = self._build_candidate(ppe_type, sequence.frames)
            sequence.emitted = True
            sequence.frames.clear()
            candidates.append(candidate)
        return tuple(candidates)

    def reset_track(self, person_track_id: str) -> None:
        self.gate.reset(person_track_id)
        for key in [key for key in self._sequences if key[0] == person_track_id]:
            self._sequences.pop(key)

    def _build_candidate(
        self,
        ppe_type: PpeType,
        observations: list[PersonFrameObservation],
    ) -> CandidateEvidence:
        selected = (
            observations[0],
            observations[len(observations) // 2],
            observations[-1],
        )
        representative = selected[1]
        evidence_kind = (
            EvidenceKind.NEGATIVE_CLASS_DETECTION
            if ppe_type is PpeType.HELMET
            else EvidenceKind.MISSING_POSITIVE_ASSOCIATION
        )
        confidences = self._aggregation_confidences(ppe_type, observations)
        confidence = (
            sum(confidences) / len(confidences)
            * len(confidences)
            / (len(confidences) + 1)
        )
        first_seen_ms = observations[0].timestamp_ms
        last_seen_ms = observations[-1].timestamp_ms
        candidate_id = self._candidate_id(
            representative.person_track_id,
            ppe_type,
            first_seen_ms,
            last_seen_ms,
        )
        return CandidateEvidence(
            candidate_id=candidate_id,
            session_id=self.session_id,
            camera_id=self.camera_id,
            person_track_id=representative.person_track_id,
            ppe_type=ppe_type,
            evidence_kind=evidence_kind,
            confidence=confidence,
            model_name=self.model_name,
            model_version=self.model_version,
            weights_sha256=self.weights_sha256,
            aggregation_method=AGGREGATION_METHOD,
            aggregation_parameters=self._aggregation_parameters(
                ppe_type, observations
            ),
            occurred_at=self.scene_started_at
            + timedelta(milliseconds=representative.timestamp_ms),
            first_seen_ms=first_seen_ms,
            last_seen_ms=last_seen_ms,
            frames=[
                self._evidence_frame(selected[0], ppe_type, FrameRole.BEFORE),
                self._evidence_frame(
                    selected[1], ppe_type, FrameRole.REPRESENTATIVE
                ),
                self._evidence_frame(selected[2], ppe_type, FrameRole.AFTER),
            ],
        )

    def _evidence_frame(
        self,
        observation: PersonFrameObservation,
        ppe_type: PpeType,
        role: FrameRole,
    ) -> EvidenceFrame:
        negative_detection = (
            self._negative_helmet_detection(observation)
            if ppe_type is PpeType.HELMET
            else None
        )
        return EvidenceFrame(
            timestamp_ms=observation.timestamp_ms,
            image_url=observation.image_url,
            image_width=observation.image_width,
            image_height=observation.image_height,
            frame_role=role,
            person_box=observation.person.box,
            observation_box=(
                negative_detection.box if negative_detection is not None else None
            ),
            observation_confidence=(
                negative_detection.confidence
                if negative_detection is not None
                else None
            ),
        )

    def _aggregation_confidences(
        self,
        ppe_type: PpeType,
        observations: list[PersonFrameObservation],
    ) -> list[float]:
        if ppe_type is PpeType.HELMET:
            return [
                self._negative_helmet_detection(item).confidence
                for item in observations
            ]
        return [item.person.confidence for item in observations]

    def _negative_helmet_detection(
        self, observation: PersonFrameObservation
    ) -> DetectionObservation:
        threshold = self.config.class_confidence_thresholds["no_helmet"]
        detections = [
            item
            for item in observation.associated_ppe
            if item.class_name.lower() == "no_helmet"
            and item.confidence >= threshold
        ]
        if not detections:
            raise ValueError("helmet negative sequence lacks a real no_helmet box")
        return max(detections, key=lambda item: item.confidence)

    def _aggregation_parameters(
        self,
        ppe_type: PpeType,
        observations: list[PersonFrameObservation],
    ) -> dict[str, object]:
        return {
            "minimum_person_height_px": self.config.minimum_person_height_px,
            "boundary_margin_px": self.config.boundary_margin_px,
            "maximum_person_overlap_iou": self.config.maximum_person_overlap_iou,
            "minimum_track_observations": self.config.minimum_track_observations,
            "minimum_valid_observations": self.config.minimum_valid_observations,
            "maximum_observation_gap_ms": self.config.maximum_observation_gap_ms,
            "minimum_negative_observations": (
                self.config.minimum_negative_observations[ppe_type]
            ),
            "sample_count": len(observations),
            "confidence_formula": (
                "mean_support_confidence*sample_count/(sample_count+1)"
            ),
            "class_confidence_thresholds": dict(
                self.config.class_confidence_thresholds
            ),
            "no_gloves_auxiliary_count": sum(
                any(
                    detection.class_name.lower() == "no_gloves"
                    for detection in item.associated_ppe
                )
                for item in observations
            ),
        }

    def _candidate_id(
        self,
        person_track_id: str,
        ppe_type: PpeType,
        first_seen_ms: int,
        last_seen_ms: int,
    ) -> str:
        key = ":".join(
            (
                self.session_id,
                self.camera_id,
                person_track_id,
                ppe_type.value,
                str(first_seen_ms),
                str(last_seen_ms),
            )
        )
        return f"candidate-{uuid5(NAMESPACE_URL, key)}"
