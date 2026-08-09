from datetime import datetime, timedelta

from app.contracts import (
    CandidateEvidence,
    CaseSnapshot,
    CaseStatus,
    CaseTransition,
    InvestigationResult,
    RectificationEvidence,
)


def _candidate(
    case_id: str,
    camera_id: str,
    ppe_type: str,
    occurred_at: str,
) -> CandidateEvidence:
    return CandidateEvidence.model_validate(
        {
            "candidate_id": f"candidate-{case_id}",
            "session_id": "session-demo-01",
            "camera_id": camera_id,
            "person_track_id": f"track-{case_id}",
            "ppe_type": ppe_type,
            "evidence_kind": "NEGATIVE_CLASS_DETECTION",
            "confidence": 0.91,
            "model_name": "ppe-yolo",
            "weights_sha256": "a" * 64,
            "aggregation_method": "weighted_mean",
            "aggregation_parameters": {"minimum_frames": 3},
            "occurred_at": occurred_at,
            "first_seen_ms": 1_000,
            "last_seen_ms": 2_000,
            "frames": [
                {
                    "timestamp_ms": 1_500,
                    "image_url": f"/evidence/{case_id}/key.jpg",
                    "image_width": 1920,
                    "image_height": 1080,
                    "frame_role": "REPRESENTATIVE",
                    "person_box": {
                        "x1": 10,
                        "y1": 20,
                        "x2": 110,
                        "y2": 220,
                    },
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
    )


def _investigation() -> InvestigationResult:
    return InvestigationResult.model_validate(
        {
            "facts": {"task_code": "HOT_WORK_CUTTING"},
            "conflicts": [],
            "missing_fields": [],
            "applicable_task": "HOT_WORK_CUTTING",
            "hazards": ["飞溅", "强光"],
            "required_ppe": ["goggles", "helmet"],
            "recommendation": "确认责任主体与期限后进入整改",
            "rectification_recommendation": {
                "responsible_party_id": "team-electric-01",
                "due_at": "2026-08-10T18:00:00+08:00",
                "reason": "切割作业存在眼部伤害风险",
            },
            "citations": [
                {
                    "document_title": "个体防护装备配备规范",
                    "standard_no": "GB 39800.12-2025",
                    "section": "建筑作业防护",
                    "source_url": "https://openstd.samr.gov.cn/example",
                    "excerpt": "切割作业应根据危害配备眼部防护装备。",
                }
            ],
            "tool_trace": [
                "get_zone_at",
                "find_active_work_permits",
                "search_authoritative_requirements",
            ],
        }
    )


def _transitions_to(
    candidate: CandidateEvidence,
    target_status: CaseStatus,
    closed_at: datetime | None = None,
) -> list[CaseTransition]:
    occurred_at = candidate.occurred_at
    investigation_target = (
        CaseStatus.NEEDS_HUMAN_FACTS
        if target_status is CaseStatus.NEEDS_HUMAN_FACTS
        else CaseStatus.PENDING_REVIEW
    )
    transitions = [
        CaseTransition(
            from_status=CaseStatus.YOLO_CANDIDATE,
            to_status=CaseStatus.VLM_REVIEWED,
            reason="VLM 确认候选证据充分",
            occurred_at=occurred_at + timedelta(minutes=1),
        ),
        CaseTransition(
            from_status=CaseStatus.VLM_REVIEWED,
            to_status=CaseStatus.INVESTIGATING,
            reason="启动 Agent 调查",
            occurred_at=occurred_at + timedelta(minutes=2),
        ),
        CaseTransition(
            from_status=CaseStatus.INVESTIGATING,
            to_status=investigation_target,
            reason=(
                "调查缺少现场事实"
                if investigation_target is CaseStatus.NEEDS_HUMAN_FACTS
                else "调查结果完整，等待人工审核"
            ),
            occurred_at=occurred_at + timedelta(minutes=3),
        ),
    ]
    if target_status in {
        CaseStatus.RECTIFICATION_OPEN,
        CaseStatus.RECHECK_PENDING,
        CaseStatus.CLOSED,
    }:
        transitions.append(
            CaseTransition(
                from_status=CaseStatus.PENDING_REVIEW,
                to_status=CaseStatus.RECTIFICATION_OPEN,
                actor_id="reviewer-01",
                actor_role="PROJECT_SAFETY_REVIEWER",
                reason="证据和依据完整，同意整改",
                occurred_at=occurred_at + timedelta(minutes=4),
            )
        )
    if target_status in {CaseStatus.RECHECK_PENDING, CaseStatus.CLOSED}:
        transitions.append(
            CaseTransition(
                from_status=CaseStatus.RECTIFICATION_OPEN,
                to_status=CaseStatus.RECHECK_PENDING,
                actor_id="officer-01",
                actor_role="SITE_SAFETY_OFFICER",
                reason="现场已完成整改",
                occurred_at=occurred_at + timedelta(minutes=5),
            )
        )
    if target_status is CaseStatus.CLOSED:
        transitions.append(
            CaseTransition(
                from_status=CaseStatus.RECHECK_PENDING,
                to_status=CaseStatus.CLOSED,
                actor_id="reviewer-01",
                actor_role="PROJECT_SAFETY_REVIEWER",
                reason="整改证据充分",
                occurred_at=closed_at or occurred_at + timedelta(minutes=6),
            )
        )
    return transitions


def demo_cases() -> list[CaseSnapshot]:
    data = [
        {
            "case_id": "case-facts-01",
            "camera_id": "CAM-01",
            "ppe_type": "helmet",
            "status": CaseStatus.NEEDS_HUMAN_FACTS,
            "occurred_at": "2026-08-07T09:30:00+08:00",
        },
        {
            "case_id": "case-01",
            "camera_id": "CAM-02",
            "ppe_type": "goggles",
            "status": CaseStatus.PENDING_REVIEW,
            "occurred_at": "2026-08-07T10:00:00+08:00",
            "investigation": _investigation(),
        },
        {
            "case_id": "case-overdue-01",
            "camera_id": "CAM-03",
            "ppe_type": "gloves",
            "status": CaseStatus.RECTIFICATION_OPEN,
            "occurred_at": "2026-08-07T10:30:00+08:00",
            "rectification_responsible_party_id": "team-structure-01",
            "rectification_due_at": "2026-08-08T18:00:00+08:00",
        },
        {
            "case_id": "case-recheck-no-evidence",
            "camera_id": "CAM-04",
            "ppe_type": "gloves",
            "status": CaseStatus.RECHECK_PENDING,
            "occurred_at": "2026-08-07T11:00:00+08:00",
            "rectification_responsible_party_id": "team-mechanical-01",
            "rectification_due_at": "2026-08-10T18:00:00+08:00",
        },
    ]
    cases = []
    for item in data:
        candidate = _candidate(
            item["case_id"],
            item["camera_id"],
            item["ppe_type"],
            item["occurred_at"],
        )
        transitions = _transitions_to(candidate, item["status"])
        cases.append(
            CaseSnapshot(
                case_id=item["case_id"],
                session_id=candidate.session_id,
                camera_id=candidate.camera_id,
                person_track_id=candidate.person_track_id,
                ppe_type=candidate.ppe_type,
                status=item["status"],
                version=1 + len(transitions),
                candidate=candidate,
                investigation=item.get("investigation"),
                rectification_responsible_party_id=item.get(
                    "rectification_responsible_party_id"
                ),
                rectification_due_at=item.get("rectification_due_at"),
                created_at=candidate.occurred_at,
                updated_at=transitions[-1].occurred_at,
                transitions=transitions,
            )
        )

    closed_candidate = _candidate(
        "case-closed-01",
        "CAM-05",
        "vest",
        "2026-08-07T10:31:24+08:00",
    )
    closed_at = datetime.fromisoformat("2026-08-08T11:20:00+08:00")
    closed_transitions = _transitions_to(
        closed_candidate,
        CaseStatus.CLOSED,
        closed_at=closed_at,
    )
    cases.append(
        CaseSnapshot(
            case_id="case-closed-01",
            session_id=closed_candidate.session_id,
            camera_id=closed_candidate.camera_id,
            person_track_id=closed_candidate.person_track_id,
            ppe_type=closed_candidate.ppe_type,
            status=CaseStatus.CLOSED,
            version=1 + len(closed_transitions),
            candidate=closed_candidate,
            investigation=_investigation(),
            rectification_responsible_party_id="team-logistics-01",
            rectification_due_at="2026-08-08T10:00:00+08:00",
            rectification_evidence=[
                RectificationEvidence(
                    evidence_id="evidence-case-closed-01",
                    image_url="/evidence/case-closed-01/after.jpg",
                    captured_at="2026-08-07T12:00:00+08:00",
                )
            ],
            rectification_description="已佩戴高可视背心",
            recheck_conclusion="整改证据充分，复查通过",
            created_at=closed_candidate.occurred_at,
            updated_at=closed_at,
            transitions=closed_transitions,
        )
    )
    return cases
