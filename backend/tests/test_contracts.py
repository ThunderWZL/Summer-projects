from copy import deepcopy
from datetime import datetime

import pytest
from pydantic import TypeAdapter, ValidationError

from app.contracts import (
    AnalysisEvent,
    ApproveClosure,
    ApproveRectification,
    CandidateEvidence,
    CandidateCreatedPayload,
    CaseCommand,
    CaseCommandResponse,
    CaseDetailResponse,
    CaseListResponse,
    CaseSnapshot,
    ErrorResponse,
    InvestigationResult,
    RectificationRecommendation,
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


def test_case_rejects_a_rectification_deadline_without_timezone() -> None:
    data = case_data()
    data["rectification_due_at"] = "2026-08-08T18:00:00"

    with pytest.raises(ValidationError, match="rectification_due_at"):
        CaseSnapshot.model_validate(data)


def test_rectification_recommendation_requires_an_aware_deadline() -> None:
    with pytest.raises(ValidationError, match="due_at"):
        RectificationRecommendation.model_validate(
            {
                "responsible_party_id": "team-01",
                "due_at": "2026-08-08T18:00:00",
                "reason": "尽快完成整改",
            }
        )


def test_investigation_facts_accept_only_json_values() -> None:
    with pytest.raises(ValidationError, match="facts"):
        InvestigationResult.model_validate(
            {
                "facts": {"invalid": {"not", "json"}},
                "conflicts": [],
                "missing_fields": [],
                "hazards": [],
                "required_ppe": ["helmet"],
                "citations": [],
                "tool_trace": [],
            }
        )


def test_case_list_response_exposes_backend_computed_fields() -> None:
    response = CaseListResponse.model_validate(
        {
            "items": [
                {
                    "case_id": "case-01",
                    "ppe_type": "helmet",
                    "status": "RECTIFICATION_OPEN",
                    "version": 4,
                    "occurred_at": "2026-08-07T10:31:24+08:00",
                    "updated_at": "2026-08-07T11:00:00+08:00",
                    "camera_id": "CAM-01",
                    "camera_name": "东门摄像头",
                    "zone_id": "zone-01",
                    "zone_name": "东门作业区",
                    "responsible_party_id": "team-01",
                    "responsible_party_name": "土建一班",
                    "rectification_due_at": "2026-08-08T18:00:00+08:00",
                    "overdue": False,
                    "urgency": "HIGH",
                }
            ],
            "pagination": {
                "page": 1,
                "page_size": 20,
                "total_items": 1,
                "total_pages": 1,
            },
            "statistics": {
                "open_count": 1,
                "needs_human_facts_count": 0,
                "pending_review_count": 0,
                "rectification_open_count": 1,
                "recheck_pending_count": 0,
                "overdue_count": 0,
                "average_closure_minutes": None,
                "top_repeat_risk": {
                    "zone_id": "zone-01",
                    "zone_name": "东门作业区",
                    "ppe_type": "helmet",
                    "case_count": 3,
                },
            },
        }
    )

    assert response.items[0].urgency.value == "HIGH"
    assert response.statistics.top_repeat_risk.case_count == 3


def test_case_detail_uses_typed_submissions_and_unified_timeline() -> None:
    response = CaseDetailResponse.model_validate(
        {
            "snapshot": case_data(),
            "camera_name": "东门摄像头",
            "zone_id": "zone-01",
            "zone_name": "东门作业区",
            "zone_type": "HIGH_RISK",
            "video_id": "video-01",
            "video_title": "东门上午巡检",
            "responsible_party_name": None,
            "responsible_party_kind": None,
            "citations": [],
            "human_submissions": [
                {
                    "submission_id": "submission-01",
                    "case_id": "case-01",
                    "submission_type": "FACTS",
                    "actor_id": "officer-01",
                    "actor_name": "安全员甲",
                    "actor_role": "SITE_SAFETY_OFFICER",
                    "reason": "补充作业内容",
                    "created_at": "2026-08-07T10:40:00+08:00",
                    "facts": {"task": "cutting"},
                },
                {
                    "submission_id": "submission-02",
                    "case_id": "case-01",
                    "submission_type": "RECTIFICATION_EVIDENCE",
                    "actor_id": "officer-01",
                    "actor_name": "安全员甲",
                    "actor_role": "SITE_SAFETY_OFFICER",
                    "reason": "提交整改证据",
                    "created_at": "2026-08-07T12:00:00+08:00",
                    "description": "已补戴安全帽",
                    "evidence": [
                        {
                            "evidence_id": "evidence-01",
                            "image_url": "/evidence/after.jpg",
                            "captured_at": "2026-08-07T11:58:00+08:00",
                        }
                    ],
                },
            ],
            "timeline": [
                {
                    "timeline_item_id": "candidate-01",
                    "source": "YOLO",
                    "action": "CANDIDATE_CREATED",
                    "from_status": None,
                    "to_status": "YOLO_CANDIDATE",
                    "actor_id": None,
                    "actor_name": None,
                    "actor_role": None,
                    "reason": None,
                    "occurred_at": "2026-08-07T10:31:24+08:00",
                }
            ],
        }
    )

    assert response.human_submissions[0].submission_type == "FACTS"
    assert response.human_submissions[1].submission_type == (
        "RECTIFICATION_EVIDENCE"
    )
    assert response.timeline[0].source.value == "YOLO"


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


def test_analysis_event_uses_the_payload_for_its_event_type() -> None:
    event = AnalysisEvent.model_validate(
        {
            "event_id": "event-01",
            "sequence": 1,
            "event_type": "CANDIDATE_CREATED",
            "session_id": "session-01",
            "occurred_at": "2026-08-07T10:31:24+08:00",
            "case_id": "case-01",
            "playback_ms": 1_500,
            "payload": {
                "candidate_id": "candidate-01",
                "ppe_type": "helmet",
                "confidence": 0.91,
                "candidate_occurred_at": "2026-08-07T10:31:24+08:00",
                "person_track_id": "track-17",
            },
        }
    )

    assert type(event.payload) is CandidateCreatedPayload


@pytest.mark.parametrize(
    ("event_type", "case_id", "payload", "expected_payload_type"),
    [
        (
            "SESSION_PROGRESS",
            None,
            {
                "stage": "INFERENCING",
                "progress": 0.5,
                "message": None,
                "inference_fps": 24.0,
                "candidate_count": 2,
                "case_count": 1,
            },
            "SessionProgressPayload",
        ),
        (
            "SESSION_FAILED",
            None,
            {
                "error_code": "MODEL_LOAD_FAILED",
                "message": "无法加载模型",
                "retryable": False,
            },
            "SessionFailedPayload",
        ),
        (
            "VLM_REVIEWED",
            "case-01",
            {
                "verdict": "CONFIRMED",
                "evidence_sufficient": True,
                "reason": "证据充分",
                "status": "VLM_REVIEWED",
                "version": 2,
            },
            "VlmReviewedPayload",
        ),
        (
            "CASE_UPDATED",
            "case-01",
            {
                "status": "PENDING_REVIEW",
                "version": 3,
                "updated_at": "2026-08-07T10:35:00+08:00",
                "action": "INVESTIGATION_COMPLETED",
            },
            "CaseUpdatedPayload",
        ),
        (
            "SESSION_FINISHED",
            None,
            {"candidate_count": 3, "case_count": 2},
            "SessionFinishedPayload",
        ),
    ],
)
def test_analysis_event_accepts_each_fixed_payload(
    event_type: str,
    case_id: str | None,
    payload: dict[str, object],
    expected_payload_type: str,
) -> None:
    event = AnalysisEvent.model_validate(
        {
            "event_id": f"event-{event_type.lower()}",
            "sequence": 1,
            "event_type": event_type,
            "session_id": "session-01",
            "occurred_at": "2026-08-07T10:31:24+08:00",
            "case_id": case_id,
            "playback_ms": 1_500,
            "payload": payload,
        }
    )

    assert type(event.payload).__name__ == expected_payload_type


def test_analysis_event_rejects_a_payload_for_another_event_type() -> None:
    with pytest.raises(ValidationError, match="event_type"):
        AnalysisEvent.model_validate(
            {
                "event_id": "event-01",
                "sequence": 1,
                "event_type": "SESSION_FAILED",
                "session_id": "session-01",
                "occurred_at": "2026-08-07T10:31:24+08:00",
                "case_id": None,
                "playback_ms": 1_500,
                "payload": {
                    "candidate_id": "candidate-01",
                    "ppe_type": "helmet",
                    "confidence": 0.91,
                    "candidate_occurred_at": "2026-08-07T10:31:24+08:00",
                    "person_track_id": "track-17",
                },
            }
        )


def test_case_specific_analysis_event_requires_a_case_id() -> None:
    with pytest.raises(ValidationError, match="case_id"):
        AnalysisEvent.model_validate(
            {
                "event_id": "event-01",
                "sequence": 1,
                "event_type": "CASE_UPDATED",
                "session_id": "session-01",
                "occurred_at": "2026-08-07T10:31:24+08:00",
                "case_id": None,
                "playback_ms": 1_500,
                "payload": {
                    "status": "PENDING_REVIEW",
                    "version": 3,
                    "updated_at": "2026-08-07T10:31:24+08:00",
                    "action": "INVESTIGATION_COMPLETED",
                },
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


def test_error_response_can_report_the_current_version() -> None:
    error = ErrorResponse.model_validate(
        {
            "code": "CASE_VERSION_CONFLICT",
            "message": "事件已被其他操作更新",
            "current_version": 4,
        }
    )

    assert error.current_version == 4


def test_case_command_response_version_must_match_the_snapshot() -> None:
    with pytest.raises(ValidationError, match="version"):
        CaseCommandResponse.model_validate(
            {"snapshot": case_data(), "version": 2}
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
