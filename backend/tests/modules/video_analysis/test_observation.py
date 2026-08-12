from __future__ import annotations

import pytest

from app.contracts import BoundingBox, PpeType
from app.modules.video_analysis.observation import (
    CandidateAggregationConfig,
    DetectionObservation,
    EvaluabilityGate,
    PersonFrameObservation,
    PpeObservationState,
    build_person_frame_observations,
    classify_ppe,
)


def config(**overrides: object) -> CandidateAggregationConfig:
    values = {
        "minimum_person_height_px": 120,
        "boundary_margin_px": 5,
        "maximum_person_overlap_iou": 0.5,
        "minimum_track_observations": 2,
        "minimum_valid_observations": 2,
        "maximum_observation_gap_ms": 400,
        "minimum_negative_observations": {
            PpeType.HELMET: 3,
            PpeType.GLOVES: 3,
            PpeType.VEST: 3,
        },
        "class_confidence_thresholds": {
            "person": 0.5,
            "helmet": 0.5,
            "no_helmet": 0.6,
            "gloves": 0.5,
            "no_gloves": 0.6,
            "vest": 0.5,
        },
    }
    values.update(overrides)
    return CandidateAggregationConfig(**values)


def detection(
    class_name: str,
    box: tuple[float, float, float, float] = (100, 50, 300, 350),
    confidence: float = 0.9,
) -> DetectionObservation:
    return DetectionObservation(
        class_name=class_name,
        confidence=confidence,
        box=BoundingBox(x1=box[0], y1=box[1], x2=box[2], y2=box[3]),
    )


def frame(
    timestamp_ms: int,
    *,
    person_box: tuple[float, float, float, float] = (100, 50, 300, 350),
    associated_ppe: tuple[DetectionObservation, ...] = (),
    other_person_boxes: tuple[BoundingBox, ...] = (),
) -> PersonFrameObservation:
    return PersonFrameObservation(
        timestamp_ms=timestamp_ms,
        image_url=f"/evidence/{timestamp_ms}.jpg",
        image_width=640,
        image_height=480,
        person_track_id="17",
        person=detection("Person", person_box),
        associated_ppe=associated_ppe,
        other_person_boxes=other_person_boxes,
    )


def make_stable(gate: EvaluabilityGate) -> None:
    assert not gate.evaluate(frame(0)).evaluable


def test_gate_requires_a_stable_track_and_consecutive_valid_frames() -> None:
    gate = EvaluabilityGate(config())

    first = gate.evaluate(frame(0))
    second = gate.evaluate(frame(200))

    assert first.reasons == ("TRACK_UNSTABLE", "INSUFFICIENT_VALID_FRAMES")
    assert second.evaluable


@pytest.mark.parametrize(
    ("person_box", "other_person_boxes", "reason"),
    [
        ((100, 50, 300, 150), (), "PERSON_TOO_SMALL"),
        ((0, 50, 200, 350), (), "PERSON_TOUCHES_BOUNDARY"),
        (
            (100, 50, 300, 350),
            (BoundingBox(x1=110, y1=60, x2=310, y2=360),),
            "SEVERE_PERSON_OVERLAP",
        ),
    ],
)
def test_gate_rejects_geometrically_unevaluable_people(
    person_box: tuple[float, float, float, float],
    other_person_boxes: tuple[BoundingBox, ...],
    reason: str,
) -> None:
    gate = EvaluabilityGate(config())
    make_stable(gate)

    result = gate.evaluate(
        frame(200, person_box=person_box, other_person_boxes=other_person_boxes)
    )

    assert not result.evaluable
    assert reason in result.reasons


def test_gap_resets_track_stability() -> None:
    gate = EvaluabilityGate(config())
    make_stable(gate)
    assert gate.evaluate(frame(200)).evaluable

    result = gate.evaluate(frame(1_000))

    assert not result.evaluable
    assert result.reasons == ("TRACK_UNSTABLE", "INSUFFICIENT_VALID_FRAMES")


def test_gate_rejects_a_low_confidence_person() -> None:
    gate = EvaluabilityGate(config())
    make_stable(gate)
    low_confidence = frame(200)
    low_confidence = PersonFrameObservation(
        timestamp_ms=low_confidence.timestamp_ms,
        image_url=low_confidence.image_url,
        image_width=low_confidence.image_width,
        image_height=low_confidence.image_height,
        person_track_id=low_confidence.person_track_id,
        person=detection("Person", confidence=0.4),
    )

    result = gate.evaluate(low_confidence)

    assert not result.evaluable
    assert "PERSON_CONFIDENCE_LOW" in result.reasons


def test_gate_rejects_non_increasing_track_timestamps() -> None:
    gate = EvaluabilityGate(config())
    gate.evaluate(frame(200))

    with pytest.raises(ValueError, match="strictly increasing"):
        gate.evaluate(frame(200))


def test_clear_bare_hands_are_negative_after_the_coarse_gate() -> None:
    gate = EvaluabilityGate(config())
    make_stable(gate)
    bare_hands = frame(200, associated_ppe=(detection("no_gloves"),))
    evaluability = gate.evaluate(bare_hands)

    assert classify_ppe(
        bare_hands, PpeType.GLOVES, evaluability, gate.config
    ) is PpeObservationState.NEGATIVE


def test_detected_gloves_win_over_the_auxiliary_negative_class() -> None:
    gate = EvaluabilityGate(config())
    make_stable(gate)
    wearing_gloves = frame(
        200,
        associated_ppe=(detection("gloves"), detection("no_gloves")),
    )
    evaluability = gate.evaluate(wearing_gloves)

    assert classify_ppe(
        wearing_gloves, PpeType.GLOVES, evaluability, gate.config
    ) is PpeObservationState.POSITIVE


def test_tool_occlusion_is_not_claimed_as_hand_visibility() -> None:
    gate = EvaluabilityGate(config())
    make_stable(gate)
    tool_occluded = frame(200)
    evaluability = gate.evaluate(tool_occluded)

    assert evaluability.evaluable
    assert classify_ppe(
        tool_occluded, PpeType.GLOVES, evaluability, gate.config
    ) is PpeObservationState.NEGATIVE


def test_helmet_requires_a_real_negative_detection() -> None:
    gate = EvaluabilityGate(config())
    make_stable(gate)
    no_head_observation = frame(200)
    evaluability = gate.evaluate(no_head_observation)

    assert classify_ppe(
        no_head_observation, PpeType.HELMET, evaluability, gate.config
    ) is PpeObservationState.UNKNOWN


def test_only_the_three_real_ppe_types_can_be_enabled() -> None:
    with pytest.raises(ValueError, match="enabled_ppe"):
        config(
            enabled_ppe=frozenset({PpeType.HELMET, PpeType.GOGGLES}),
            minimum_negative_observations={
                PpeType.HELMET: 3,
                PpeType.GOGGLES: 3,
            },
        )


def test_w03_detections_are_associated_with_the_containing_person() -> None:
    class RawDetection:
        def __init__(
            self,
            class_name: str,
            box: tuple[float, float, float, float],
            track_id: int | None,
        ) -> None:
            self.class_name = class_name
            self.confidence = 0.9
            self.box = box
            self.track_id = track_id

    observations = build_person_frame_observations(
        timestamp_ms=200,
        image_url="/evidence/200.jpg",
        image_width=640,
        image_height=480,
        detections=(
            RawDetection("Person", (50, 30, 300, 450), 17),
            RawDetection("Person", (350, 30, 600, 450), 23),
            RawDetection("helmet", (100, 40, 180, 100), None),
            RawDetection("vest", (420, 120, 540, 300), None),
        ),
    )

    assert [item.person_track_id for item in observations] == ["17", "23"]
    assert [
        detection.class_name for detection in observations[0].associated_ppe
    ] == ["helmet"]
    assert [
        detection.class_name for detection in observations[1].associated_ppe
    ] == ["vest"]
