from copy import deepcopy
from datetime import datetime

import pytest
from pydantic import TypeAdapter, ValidationError

from app.contracts import (
    AnalysisEvent,
    ApproveClosure,
    ApproveRectification,
    CandidateEvidence,
    CaseCommand,
    CaseSnapshot,
    RejectCase,
    RejectRecheck,
    RequestReinvestigation,
    SubmitFacts,
    SubmitRectificationEvidence,
    VlmReviewResult,
)


def candidate_data() -> dict[str, object]:
    return {
        "candidate_id": "candidate-01",
        "session_id": "session-01",
        "camera_id": "CAM-01",
        "person_track_id": "track-17",
        "ppe_type": "helmet",
        "evidence_kind": "NEGATIVE_CLASS_DETECTION",
        "confidence": 0.91,
        "model_name": "ppe-yolo",
        "weights_sha256": "a" * 64,
        "aggregation_method": "weighted_mean",
        "aggregation_parameters": {"minimum_frames": 3},
        "occurred_at": "2026-08-07T10:31:24+08:00",
        "first_seen_ms": 1_000,
        "last_seen_ms": 2_000,
        "frames": [
            {
                "timestamp_ms": 1_500,
                "image_url": "/evidence/candidate-01/key.jpg",
                "image_width": 1920,
                "image_height": 1080,
                "frame_role": "REPRESENTATIVE",
                "person_box": {"x1": 10, "y1": 20, "x2": 110, "y2": 220},
                "observation_box": {
                    "x1": 30,
                    "y1": 20,
                    "x2": 80,
                    "y2": 60,
                },
                "observation_confidence": 0.93,
            }
        ],
    }


def case_data() -> dict[str, object]:
    return {
        "case_id": "case-01",
        "session_id": "session-01",
        "camera_id": "CAM-01",
        "person_track_id": "track-17",
        "ppe_type": "helmet",
        "status": "YOLO_CANDIDATE",
        "version": 1,
        "candidate": candidate_data(),
        "created_at": "2026-08-07T10:31:24+08:00",
        "updated_at": "2026-08-07T10:31:24+08:00",
    }


def test_candidate_accepts_business_timestamp() -> None:
    candidate = CandidateEvidence.model_validate(candidate_data())

    assert candidate.occurred_at == datetime.fromisoformat(
        "2026-08-07T10:31:24+08:00"
    )


def test_candidate_rejects_a_reversed_playback_window() -> None:
    data = candidate_data()
    data["first_seen_ms"] = 2_000
    data["last_seen_ms"] = 1_000

    with pytest.raises(ValidationError, match="last_seen_ms"):
        CandidateEvidence.model_validate(data)


def test_candidate_rejects_a_box_outside_the_original_frame() -> None:
    data = candidate_data()
    data["frames"][0]["person_box"]["x2"] = 2_000

    with pytest.raises(ValidationError, match="image_width"):
        CandidateEvidence.model_validate(data)


def test_candidate_rejects_a_box_with_reversed_edges() -> None:
    data = candidate_data()
    data["frames"][0]["observation_box"]["x2"] = 20

    with pytest.raises(ValidationError, match="x2 must be greater than x1"):
        CandidateEvidence.model_validate(data)


def test_negative_detection_requires_a_real_representative_observation() -> None:
    data = candidate_data()
    data["frames"][0]["observation_box"] = None
    data["frames"][0]["observation_confidence"] = None

    with pytest.raises(ValidationError, match="representative observation"):
        CandidateEvidence.model_validate(data)


def test_context_frame_observation_and_confidence_must_be_recorded_together() -> None:
    data = candidate_data()
    before = deepcopy(data["frames"][0])
    before["timestamp_ms"] = 500
    before["frame_role"] = "BEFORE"
    before["observation_confidence"] = None
    data["frames"].insert(0, before)

    with pytest.raises(ValidationError, match="observation_confidence"):
        CandidateEvidence.model_validate(data)


def test_missing_positive_association_forbids_observation_boxes() -> None:
    data = candidate_data()
    data["evidence_kind"] = "MISSING_POSITIVE_ASSOCIATION"

    with pytest.raises(ValidationError, match="must not contain observations"):
        CandidateEvidence.model_validate(data)


def test_candidate_requires_one_representative_frame() -> None:
    data = candidate_data()
    data["frames"][0]["frame_role"] = "BEFORE"

    with pytest.raises(ValidationError, match="exactly one REPRESENTATIVE"):
        CandidateEvidence.model_validate(data)


def test_candidate_rejects_unsorted_or_duplicate_frame_timestamps() -> None:
    data = candidate_data()
    after = deepcopy(data["frames"][0])
    after["frame_role"] = "AFTER"
    data["frames"].insert(0, after)

    with pytest.raises(ValidationError, match="strictly increasing"):
        CandidateEvidence.model_validate(data)


def test_representative_frame_must_be_inside_the_violation_window() -> None:
    data = candidate_data()
    data["frames"][0]["timestamp_ms"] = 2_500

    with pytest.raises(ValidationError, match="violation window"):
        CandidateEvidence.model_validate(data)


def test_candidate_requires_model_version_or_weights_digest() -> None:
    data = candidate_data()
    data.pop("weights_sha256")

    with pytest.raises(ValidationError, match="model_version or weights_sha256"):
        CandidateEvidence.model_validate(data)


def test_vlm_review_preserves_model_trace_metadata() -> None:
    review = VlmReviewResult.model_validate(
        {
            "candidate_id": "candidate-01",
            "verdict": "CONFIRMED",
            "person_track_id": "track-17",
            "ppe_type": "helmet",
            "association": "MATCHED",
            "body_part_visible": True,
            "persistent": True,
            "poster_or_reflection": False,
            "evidence_sufficient": True,
            "evidence_timestamps_ms": [1_000, 1_500, 2_000],
            "reason": "头部持续可见且未检测到安全帽",
            "model_name": "fixed-reviewer",
            "model_provider": "fixture",
            "model_parameters": {"temperature": 0},
            "reviewed_at": "2026-08-07T10:31:30+08:00",
        }
    )

    assert review.model_parameters == {"temperature": 0}


def test_case_rejects_identity_that_disagrees_with_its_candidate() -> None:
    data = case_data()
    data["camera_id"] = "CAM-02"

    with pytest.raises(ValidationError, match="camera_id"):
        CaseSnapshot.model_validate(data)


def test_case_rejects_a_timestamp_without_timezone() -> None:
    data = case_data()
    data["created_at"] = "2026-08-07T10:31:24"

    with pytest.raises(ValidationError, match="created_at"):
        CaseSnapshot.model_validate(data)


def test_analysis_event_rejects_non_json_payload() -> None:
    with pytest.raises(ValidationError, match="payload"):
        AnalysisEvent.model_validate(
            {
                "event_id": "event-01",
                "event_type": "CANDIDATE_CREATED",
                "session_id": "session-01",
                "occurred_at": "2026-08-07T10:31:24+08:00",
                "case_id": "case-01",
                "playback_ms": 1_500,
                "payload": {"invalid": {"not", "json"}},
            }
        )


def test_analysis_event_rejects_a_timestamp_without_timezone() -> None:
    with pytest.raises(ValidationError, match="occurred_at"):
        AnalysisEvent.model_validate(
            {
                "event_id": "event-01",
                "event_type": "SESSION_PROGRESS",
                "session_id": "session-01",
                "occurred_at": "2026-08-07T10:31:24",
                "playback_ms": 1_500,
            }
        )


def test_submit_facts_requires_at_least_one_fact() -> None:
    with pytest.raises(ValidationError, match="facts"):
        SubmitFacts.model_validate(
            {
                "command_type": "SUBMIT_FACTS",
                "actor_id": "officer-01",
                "expected_version": 1,
                "reason": "补充现场作业情况",
                "facts": {},
            }
        )


def test_approve_rectification_requires_an_aware_deadline() -> None:
    with pytest.raises(ValidationError, match="rectification_due_at"):
        ApproveRectification.model_validate(
            {
                "command_type": "APPROVE_RECTIFICATION",
                "actor_id": "reviewer-01",
                "expected_version": 3,
                "reason": "证据和依据完整",
                "responsible_party_id": "team-electric-01",
                "rectification_due_at": "2026-08-08T18:00:00",
            }
        )


def test_submit_rectification_requires_evidence() -> None:
    with pytest.raises(ValidationError, match="evidence"):
        SubmitRectificationEvidence.model_validate(
            {
                "command_type": "SUBMIT_RECTIFICATION_EVIDENCE",
                "actor_id": "officer-01",
                "expected_version": 4,
                "reason": "现场已完成整改",
                "description": "补戴安全帽并完成班前检查",
                "evidence": [],
            }
        )


def test_new_case_has_an_empty_transition_timeline() -> None:
    case = CaseSnapshot.model_validate(case_data())

    assert case.transitions == []


def test_new_case_has_no_human_facts() -> None:
    case = CaseSnapshot.model_validate(case_data())

    assert case.human_facts == {}


def test_new_case_has_no_rectification_evidence() -> None:
    case = CaseSnapshot.model_validate(case_data())

    assert case.rectification_evidence == []


def test_new_case_has_no_rectification_or_recheck_conclusion() -> None:
    case = CaseSnapshot.model_validate(case_data())

    assert (case.rectification_description, case.recheck_conclusion) == (
        None,
        None,
    )


@pytest.mark.parametrize(
    ("payload", "expected_type"),
    [
        (
            {
                "command_type": "SUBMIT_FACTS",
                "actor_id": "officer-01",
                "expected_version": 1,
                "reason": "补充事实",
                "facts": {"task": "cutting"},
            },
            SubmitFacts,
        ),
        (
            {
                "command_type": "APPROVE_RECTIFICATION",
                "actor_id": "reviewer-01",
                "expected_version": 1,
                "reason": "同意整改",
                "responsible_party_id": "team-01",
                "rectification_due_at": "2026-08-08T18:00:00+08:00",
            },
            ApproveRectification,
        ),
        (
            {
                "command_type": "REJECT_CASE",
                "actor_id": "reviewer-01",
                "expected_version": 1,
                "reason": "不是现场人员",
            },
            RejectCase,
        ),
        (
            {
                "command_type": "REQUEST_REINVESTIGATION",
                "actor_id": "reviewer-01",
                "expected_version": 1,
                "reason": "许可信息冲突",
            },
            RequestReinvestigation,
        ),
        (
            {
                "command_type": "SUBMIT_RECTIFICATION_EVIDENCE",
                "actor_id": "officer-01",
                "expected_version": 1,
                "reason": "已完成整改",
                "description": "已补戴安全帽",
                "evidence": [
                    {
                        "evidence_id": "evidence-after-01",
                        "image_url": "/evidence/after.jpg",
                        "captured_at": "2026-08-07T12:00:00+08:00",
                    }
                ],
            },
            SubmitRectificationEvidence,
        ),
        (
            {
                "command_type": "APPROVE_CLOSURE",
                "actor_id": "reviewer-01",
                "expected_version": 1,
                "reason": "整改证据有效",
                "recheck_conclusion": "复查通过",
            },
            ApproveClosure,
        ),
        (
            {
                "command_type": "REJECT_RECHECK",
                "actor_id": "reviewer-01",
                "expected_version": 1,
                "reason": "证据无法证明整改完成",
                "recheck_conclusion": "需要重新提交清晰照片",
            },
            RejectRecheck,
        ),
    ],
)
def test_case_command_discriminator_selects_the_declared_command(
    payload: dict[str, object], expected_type: type[object]
) -> None:
    command = TypeAdapter(CaseCommand).validate_python(payload)

    assert type(command) is expected_type
