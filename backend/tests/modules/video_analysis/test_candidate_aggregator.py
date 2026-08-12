from __future__ import annotations

from datetime import datetime

from app.contracts import BoundingBox, EvidenceKind, FrameRole, PpeType
from app.modules.video_analysis.candidate_aggregator import CandidateAggregator
from app.modules.video_analysis.observation import (
    CandidateAggregationConfig,
    DetectionObservation,
    PersonFrameObservation,
)


def config() -> CandidateAggregationConfig:
    return CandidateAggregationConfig(
        minimum_person_height_px=120,
        boundary_margin_px=5,
        maximum_person_overlap_iou=0.5,
        minimum_track_observations=2,
        minimum_valid_observations=2,
        maximum_observation_gap_ms=400,
        minimum_negative_observations={
            PpeType.HELMET: 3,
            PpeType.GLOVES: 3,
            PpeType.VEST: 3,
        },
        class_confidence_thresholds={
            "person": 0.5,
            "helmet": 0.5,
            "no_helmet": 0.6,
            "gloves": 0.5,
            "no_gloves": 0.6,
            "vest": 0.5,
        },
    )


def detection(
    class_name: str,
    *,
    confidence: float = 0.8,
    box: tuple[float, float, float, float] = (120, 60, 180, 110),
) -> DetectionObservation:
    return DetectionObservation(
        class_name=class_name,
        confidence=confidence,
        box=BoundingBox(x1=box[0], y1=box[1], x2=box[2], y2=box[3]),
    )


def frame(
    timestamp_ms: int,
    *,
    ppe: tuple[DetectionObservation, ...] | None = None,
    person_box: tuple[float, float, float, float] = (100, 40, 300, 400),
    other_person_boxes: tuple[BoundingBox, ...] = (),
) -> PersonFrameObservation:
    if ppe is None:
        ppe = (detection("vest"),)
    return PersonFrameObservation(
        timestamp_ms=timestamp_ms,
        image_url=f"/evidence/session-01/{timestamp_ms}.jpg",
        image_width=640,
        image_height=480,
        person_track_id="17",
        person=detection("Person", confidence=0.8, box=person_box),
        associated_ppe=ppe,
        other_person_boxes=other_person_boxes,
    )


def aggregator() -> CandidateAggregator:
    return CandidateAggregator(
        session_id="session-01",
        camera_id="CAM-03",
        scene_started_at=datetime.fromisoformat("2026-08-11T09:00:00+08:00"),
        model_name="ppe-yolo11n",
        model_version="construction-ppe-baseline",
        weights_sha256="a" * 64,
        config=config(),
    )


def stabilize(instance: CandidateAggregator) -> None:
    assert instance.observe(frame(0)) == ()


def test_missing_gloves_produce_one_traceable_candidate() -> None:
    instance = aggregator()
    stabilize(instance)

    assert instance.observe(frame(200)) == ()
    assert instance.observe(frame(400)) == ()
    candidates = instance.observe(frame(600))
    assert instance.observe(frame(800)) == ()

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.ppe_type is PpeType.GLOVES
    assert candidate.evidence_kind is EvidenceKind.MISSING_POSITIVE_ASSOCIATION
    assert candidate.person_track_id == "17"
    assert (candidate.first_seen_ms, candidate.last_seen_ms) == (200, 600)
    assert candidate.occurred_at == datetime.fromisoformat(
        "2026-08-11T09:00:00.400000+08:00"
    )
    assert [item.frame_role for item in candidate.frames] == [
        FrameRole.BEFORE,
        FrameRole.REPRESENTATIVE,
        FrameRole.AFTER,
    ]
    assert [item.timestamp_ms for item in candidate.frames] == [200, 400, 600]
    assert all(item.observation_box is None for item in candidate.frames)
    assert candidate.aggregation_parameters["sample_count"] == 3


def test_replaying_the_same_session_window_keeps_the_candidate_id() -> None:
    first = aggregator()
    second = aggregator()
    for instance in (first, second):
        stabilize(instance)

    first_candidate = [
        *first.observe(frame(200)),
        *first.observe(frame(400)),
        *first.observe(frame(600)),
    ][0]
    second_candidate = [
        *second.observe(frame(200)),
        *second.observe(frame(400)),
        *second.observe(frame(600)),
    ][0]

    assert first_candidate.candidate_id == second_candidate.candidate_id


def test_positive_gloves_reset_the_missing_sequence() -> None:
    instance = aggregator()
    stabilize(instance)

    assert instance.observe(frame(200)) == ()
    assert instance.observe(frame(400, ppe=(detection("gloves"),))) == ()
    assert instance.observe(frame(600)) == ()
    assert instance.observe(frame(800)) == ()
    candidates = instance.observe(frame(1_000))

    assert [item.ppe_type for item in candidates] == [PpeType.GLOVES]
    assert candidates[0].first_seen_ms == 600


def test_a_single_no_gloves_detection_cannot_trigger_a_candidate() -> None:
    instance = aggregator()
    stabilize(instance)

    candidates = instance.observe(frame(200, ppe=(detection("no_gloves"),)))

    assert candidates == ()


def test_helmet_candidate_keeps_only_real_negative_detection_boxes() -> None:
    instance = aggregator()
    negative = (detection("no_helmet", confidence=0.7),)
    stabilize(instance)

    assert instance.observe(frame(200, ppe=negative)) == ()
    assert instance.observe(frame(400, ppe=negative)) == ()
    candidates = instance.observe(frame(600, ppe=negative))

    helmet = next(item for item in candidates if item.ppe_type is PpeType.HELMET)
    assert helmet.evidence_kind is EvidenceKind.NEGATIVE_CLASS_DETECTION
    assert all(item.observation_box is not None for item in helmet.frames)
    assert all(item.observation_confidence == 0.7 for item in helmet.frames)


def test_missing_helmet_without_no_helmet_never_produces_a_candidate() -> None:
    instance = aggregator()
    stabilize(instance)

    output = [
        *instance.observe(frame(200)),
        *instance.observe(frame(400)),
        *instance.observe(frame(600)),
        *instance.observe(frame(800)),
    ]

    assert all(item.ppe_type is not PpeType.HELMET for item in output)


def test_unevaluable_frames_never_accumulate_a_candidate() -> None:
    instance = aggregator()
    stabilize(instance)
    overlapping = (
        BoundingBox(x1=110, y1=50, x2=310, y2=410),
    )

    output = [
        *instance.observe(frame(200, other_person_boxes=overlapping)),
        *instance.observe(frame(400, other_person_boxes=overlapping)),
        *instance.observe(frame(600, other_person_boxes=overlapping)),
        *instance.observe(frame(800, other_person_boxes=overlapping)),
    ]

    assert output == []


def test_tool_occlusion_remains_missing_positive_evidence_for_vlm() -> None:
    instance = aggregator()
    stabilize(instance)

    instance.observe(frame(200))
    instance.observe(frame(400))
    candidates = instance.observe(frame(600))

    gloves = next(item for item in candidates if item.ppe_type is PpeType.GLOVES)
    assert gloves.evidence_kind is EvidenceKind.MISSING_POSITIVE_ASSOCIATION
    assert all(item.observation_box is None for item in gloves.frames)


def test_missing_vest_produces_an_independent_candidate() -> None:
    instance = aggregator()
    protected_hands = (detection("gloves"),)
    stabilize(instance)

    instance.observe(frame(200, ppe=protected_hands))
    instance.observe(frame(400, ppe=protected_hands))
    candidates = instance.observe(frame(600, ppe=protected_hands))

    assert [item.ppe_type for item in candidates] == [PpeType.VEST]
    assert candidates[0].evidence_kind is EvidenceKind.MISSING_POSITIVE_ASSOCIATION
