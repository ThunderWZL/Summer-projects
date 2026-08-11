from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from app.contracts import BoundingBox, PpeType


SUPPORTED_PPE = frozenset({PpeType.HELMET, PpeType.GLOVES, PpeType.VEST})


class PpeObservationState(str, Enum):
    """Internal visual result; UNKNOWN never crosses the shared contract."""

    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class DetectionObservation:
    class_name: str
    confidence: float
    box: BoundingBox

    def __post_init__(self) -> None:
        if not self.class_name:
            raise ValueError("class_name must not be empty")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be within [0, 1]")


@dataclass(frozen=True)
class PersonFrameObservation:
    timestamp_ms: int
    image_url: str
    image_width: int
    image_height: int
    person_track_id: str
    person: DetectionObservation
    associated_ppe: tuple[DetectionObservation, ...] = ()
    other_person_boxes: tuple[BoundingBox, ...] = ()

    def __post_init__(self) -> None:
        if self.timestamp_ms < 0:
            raise ValueError("timestamp_ms must not be negative")
        if self.image_width <= 0 or self.image_height <= 0:
            raise ValueError("image dimensions must be greater than zero")
        if not self.image_url:
            raise ValueError("image_url must not be empty")
        if not self.person_track_id:
            raise ValueError("person_track_id must not be empty")
        for name, box in (
            ("person", self.person.box),
            *[("associated_ppe", item.box) for item in self.associated_ppe],
            *[("other_person", item) for item in self.other_person_boxes],
        ):
            if box.x2 > self.image_width or box.y2 > self.image_height:
                raise ValueError(f"{name} box exceeds image dimensions")


@dataclass(frozen=True)
class CandidateAggregationConfig:
    """Session-frozen thresholds used by the visual coarse gate."""

    minimum_person_height_px: int
    boundary_margin_px: int
    maximum_person_overlap_iou: float
    minimum_track_observations: int
    minimum_valid_observations: int
    maximum_observation_gap_ms: int
    minimum_negative_observations: Mapping[PpeType, int]
    class_confidence_thresholds: Mapping[str, float]
    enabled_ppe: frozenset[PpeType] = SUPPORTED_PPE

    def __post_init__(self) -> None:
        if self.minimum_person_height_px <= 0:
            raise ValueError("minimum_person_height_px must be greater than zero")
        if self.boundary_margin_px < 0:
            raise ValueError("boundary_margin_px must not be negative")
        if not 0 <= self.maximum_person_overlap_iou <= 1:
            raise ValueError("maximum_person_overlap_iou must be within [0, 1]")
        if self.minimum_track_observations <= 0:
            raise ValueError("minimum_track_observations must be greater than zero")
        if self.minimum_valid_observations <= 0:
            raise ValueError("minimum_valid_observations must be greater than zero")
        if self.maximum_observation_gap_ms <= 0:
            raise ValueError("maximum_observation_gap_ms must be greater than zero")
        if not self.enabled_ppe or not self.enabled_ppe <= SUPPORTED_PPE:
            raise ValueError("enabled_ppe may contain only helmet, gloves, and vest")
        if set(self.minimum_negative_observations) != set(self.enabled_ppe):
            raise ValueError(
                "minimum_negative_observations must cover exactly enabled_ppe"
            )
        if any(value <= 0 for value in self.minimum_negative_observations.values()):
            raise ValueError("minimum negative observations must be greater than zero")
        required_classes = {"person", "helmet", "no_helmet", "gloves", "vest"}
        if not required_classes <= {
            name.lower() for name in self.class_confidence_thresholds
        }:
            raise ValueError("class_confidence_thresholds is missing a required class")
        if any(
            not 0 <= value <= 1
            for value in self.class_confidence_thresholds.values()
        ):
            raise ValueError("class confidence thresholds must be within [0, 1]")
        object.__setattr__(
            self,
            "minimum_negative_observations",
            MappingProxyType(dict(self.minimum_negative_observations)),
        )
        object.__setattr__(
            self,
            "class_confidence_thresholds",
            MappingProxyType(
                {
                    name.lower(): value
                    for name, value in self.class_confidence_thresholds.items()
                }
            ),
        )


@dataclass(frozen=True)
class EvaluabilityResult:
    evaluable: bool
    reasons: tuple[str, ...]


@dataclass
class _TrackGateState:
    observations: int = 0
    valid_streak: int = 0
    last_timestamp_ms: int | None = None


@dataclass
class EvaluabilityGate:
    config: CandidateAggregationConfig
    _tracks: dict[str, _TrackGateState] = field(default_factory=dict, init=False)

    def evaluate(self, frame: PersonFrameObservation) -> EvaluabilityResult:
        state = self._tracks.setdefault(frame.person_track_id, _TrackGateState())
        if (
            state.last_timestamp_ms is not None
            and frame.timestamp_ms - state.last_timestamp_ms
            > self.config.maximum_observation_gap_ms
        ):
            state.observations = 0
            state.valid_streak = 0
        state.last_timestamp_ms = frame.timestamp_ms
        state.observations += 1

        reasons = self._geometry_reasons(frame)
        if reasons:
            state.valid_streak = 0
            return EvaluabilityResult(False, tuple(reasons))

        state.valid_streak += 1
        if state.observations < self.config.minimum_track_observations:
            reasons.append("TRACK_UNSTABLE")
        if state.valid_streak < self.config.minimum_valid_observations:
            reasons.append("INSUFFICIENT_VALID_FRAMES")
        return EvaluabilityResult(not reasons, tuple(reasons))

    def reset(self, person_track_id: str) -> None:
        self._tracks.pop(person_track_id, None)

    def _geometry_reasons(self, frame: PersonFrameObservation) -> list[str]:
        person_box = frame.person.box
        reasons: list[str] = []
        if person_box.y2 - person_box.y1 < self.config.minimum_person_height_px:
            reasons.append("PERSON_TOO_SMALL")
        margin = self.config.boundary_margin_px
        if (
            person_box.x1 <= margin
            or person_box.y1 <= margin
            or person_box.x2 >= frame.image_width - margin
            or person_box.y2 >= frame.image_height - margin
        ):
            reasons.append("PERSON_TOUCHES_BOUNDARY")
        if any(
            _intersection_over_union(person_box, other)
            >= self.config.maximum_person_overlap_iou
            for other in frame.other_person_boxes
        ):
            reasons.append("SEVERE_PERSON_OVERLAP")
        return reasons


def classify_ppe(
    frame: PersonFrameObservation,
    ppe_type: PpeType,
    evaluability: EvaluabilityResult,
    config: CandidateAggregationConfig,
) -> PpeObservationState:
    """Classify one PPE only after the coarse gate accepts the frame."""

    if ppe_type not in config.enabled_ppe or not evaluability.evaluable:
        return PpeObservationState.UNKNOWN
    detections = {
        item.class_name.lower(): item
        for item in frame.associated_ppe
        if item.confidence
        >= config.class_confidence_thresholds.get(item.class_name.lower(), 1.0)
    }
    positive_class = ppe_type.value
    if positive_class in detections:
        return PpeObservationState.POSITIVE
    if ppe_type is PpeType.HELMET:
        return (
            PpeObservationState.NEGATIVE
            if "no_helmet" in detections
            else PpeObservationState.UNKNOWN
        )
    return PpeObservationState.NEGATIVE


def _intersection_over_union(first: BoundingBox, second: BoundingBox) -> float:
    x1 = max(first.x1, second.x1)
    y1 = max(first.y1, second.y1)
    x2 = min(first.x2, second.x2)
    y2 = min(first.y2, second.y2)
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    if intersection == 0:
        return 0.0
    first_area = (first.x2 - first.x1) * (first.y2 - first.y1)
    second_area = (second.x2 - second.x1) * (second.y2 - second.y1)
    return intersection / (first_area + second_area - intersection)
