from datetime import datetime, timedelta

from app.contracts import (
    CandidateEvidence,
    CaseSnapshot,
    CaseStatus,
    CaseTransition,
    InvestigationResult,
    RectificationEvidence,
    RectificationEvidenceSubmissionRecord,
    VlmReviewResult,
)


def _candidate(
    case_id: str,
    camera_id: str,
    ppe_type: str,
    occurred_at: str,
) -> CandidateEvidence:
    uses_missing_association = ppe_type == "vest"
    return CandidateEvidence.model_validate(
        {
            "candidate_id": f"candidate-{case_id}",
            "session_id": "session-demo-01",
            "camera_id": camera_id,
            "person_track_id": f"track-{case_id}",
            "ppe_type": ppe_type,
            "evidence_kind": (
                "MISSING_POSITIVE_ASSOCIATION"
                if uses_missing_association
                else "NEGATIVE_CLASS_DETECTION"
            ),
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
                    "observation_box": (
                        None
                        if uses_missing_association
                        else {
                            "x1": 30,
                            "y1": 20,
                            "x2": 80,
                            "y2": 60,
                        }
                    ),
                    "observation_confidence": (
                        None if uses_missing_association else 0.93
                    ),
                }
            ],
        }
    )


def _confirmed_review(candidate: CandidateEvidence) -> VlmReviewResult:
    return VlmReviewResult(
        candidate_id=candidate.candidate_id,
        verdict="CONFIRMED",
        person_track_id=candidate.person_track_id,
        ppe_type=candidate.ppe_type,
        association="MATCHED",
        body_part_visible=True,
        persistent=True,
        poster_or_reflection=False,
        evidence_sufficient=True,
        evidence_timestamps_ms=[
            frame.timestamp_ms for frame in candidate.frames
        ],
        reason=f"人员持续可见且确认缺少 {candidate.ppe_type.value}",
        model_name="fixed-reviewer",
        model_provider="fixture",
        model_parameters={"temperature": 0},
        reviewed_at=candidate.occurred_at + timedelta(minutes=1),
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


def _vehicle_vest_investigation() -> InvestigationResult:
    return InvestigationResult.model_validate(
        {
            "facts": {"task_code": "VEHICLE_ZONE_OPERATION"},
            "conflicts": [],
            "missing_fields": [],
            "applicable_task": "VEHICLE_ZONE_OPERATION",
            "hazards": ["车辆碰撞"],
            "required_ppe": ["vest"],
            "recommendation": "车辆作业区人员应佩戴高可视背心",
            "rectification_recommendation": {
                "responsible_party_id": "team-logistics-01",
                "due_at": "2026-08-08T10:00:00+08:00",
                "reason": "车辆作业区需要提高人员可见性",
            },
            "citations": [
                {
                    "document_title": "建筑工人施工现场劳动保护基本配置指南",
                    "section": "高可视警示服",
                    "source_url": (
                        "https://www.gov.cn/zhengce/zhengceku/"
                        "2021-01/19/5580999/"
                    ),
                    "excerpt": "车辆作业区域应按风险配备高可视警示服。",
                }
            ],
            "tool_trace": [
                "get_zone_at",
                "find_active_work_permits",
                "get_task_ppe_matrix",
                "search_authoritative_requirements",
            ],
        }
    )


def _missing_facts_investigation() -> InvestigationResult:
    return InvestigationResult.model_validate(
        {
            "facts": {"camera_id": "CAM-01", "zone_type": "SCAFFOLD"},
            "conflicts": [],
            "missing_fields": ["active_work_permit", "actual_task_code"],
            "applicable_task": None,
            "hazards": ["高处作业"],
            "required_ppe": [],
            "recommendation": None,
            "rectification_recommendation": None,
            "citations": [],
            "tool_trace": [
                "get_zone_at",
                "find_active_work_permits",
            ],
        }
    )


def _rebar_gloves_investigation() -> InvestigationResult:
    return InvestigationResult.model_validate(
        {
            "facts": {"task_code": "HANDLING_REBAR"},
            "conflicts": [],
            "missing_fields": [],
            "applicable_task": "HANDLING_REBAR",
            "hazards": ["手部伤害风险"],
            "required_ppe": ["gloves"],
            "recommendation": "钢筋搬运作业应按任务要求佩戴防护手套",
            "rectification_recommendation": {
                "responsible_party_id": "team-structure-01",
                "due_at": "2026-08-08T18:00:00+08:00",
                "reason": "钢筋搬运存在手部伤害风险",
            },
            "citations": [
                {
                    "document_title": "个体防护装备配备规范",
                    "standard_no": "GB 39800.12-2025",
                    "section": "手部防护",
                    "source_url": "https://openstd.samr.gov.cn/example",
                    "excerpt": "存在手部伤害风险时应配备适用的手部防护装备。",
                }
            ],
            "tool_trace": [
                "get_zone_at",
                "find_active_work_permits",
                "get_task_ppe_matrix",
                "search_authoritative_requirements",
            ],
        }
    )


def _rotating_equipment_investigation() -> InvestigationResult:
    return InvestigationResult.model_validate(
        {
            "facts": {"task_code": "ROTATING_EQUIPMENT_OPERATION"},
            "conflicts": [],
            "missing_fields": [],
            "applicable_task": "ROTATING_EQUIPMENT_OPERATION",
            "hazards": ["卷入风险"],
            "required_ppe": ["helmet"],
            "recommendation": "不应简单要求佩戴手套，应优先落实防卷入措施",
            "rectification_recommendation": {
                "responsible_party_id": "team-mechanical-01",
                "due_at": "2026-08-10T18:00:00+08:00",
                "reason": "旋转设备作业需控制卷入风险并复核 PPE 要求",
            },
            "citations": [
                {
                    "document_title": "建筑与市政施工现场安全卫生与职业健康通用规范",
                    "standard_no": "GB 55034-2022",
                    "section": "机械设备作业",
                    "source_url": "https://policy.mofcom.gov.cn/example",
                    "excerpt": "机械设备作业应采取防止人员卷入的安全措施。",
                }
            ],
            "tool_trace": [
                "get_zone_at",
                "find_active_work_permits",
                "get_task_ppe_matrix",
                "search_authoritative_requirements",
            ],
        }
    )


def _recheck_evidence() -> RectificationEvidence:
    return RectificationEvidence(
        evidence_id="evidence-case-recheck-01",
        image_url="/evidence/case-recheck-no-evidence/after.jpg",
        captured_at="2026-08-07T11:04:00+08:00",
        note="整改后的旋转设备作业现场",
    )


def _closed_evidence() -> RectificationEvidence:
    return RectificationEvidence(
        evidence_id="evidence-case-closed-01",
        image_url="/evidence/case-closed-01/after.jpg",
        captured_at="2026-08-07T12:00:00+08:00",
        note="整改后的车辆作业区人员高可视背心",
    )


def _transitions_to(
    candidate: CandidateEvidence,
    target_status: CaseStatus,
    closed_at: datetime | None = None,
    evidence_submitted_at: datetime | None = None,
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
                occurred_at=(
                    evidence_submitted_at
                    or occurred_at + timedelta(minutes=5)
                ),
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
            "investigation": _missing_facts_investigation(),
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
            "investigation": _rebar_gloves_investigation(),
        },
        {
            "case_id": "case-recheck-no-evidence",
            "camera_id": "CAM-04",
            "ppe_type": "gloves",
            "status": CaseStatus.RECHECK_PENDING,
            "occurred_at": "2026-08-07T11:00:00+08:00",
            "rectification_responsible_party_id": "team-mechanical-01",
            "rectification_due_at": "2026-08-10T18:00:00+08:00",
            "rectification_description": "已完成防卷入整改并复核作业要求",
            "rectification_evidence": [_recheck_evidence()],
            "investigation": _rotating_equipment_investigation(),
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
                vlm_review=_confirmed_review(candidate),
                investigation=item.get("investigation"),
                rectification_responsible_party_id=item.get(
                    "rectification_responsible_party_id"
                ),
                rectification_due_at=item.get("rectification_due_at"),
                rectification_description=item.get(
                    "rectification_description"
                ),
                rectification_evidence=item.get(
                    "rectification_evidence", []
                ),
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
        evidence_submitted_at=datetime.fromisoformat(
            "2026-08-07T12:01:00+08:00"
        ),
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
            vlm_review=_confirmed_review(closed_candidate),
            investigation=_vehicle_vest_investigation(),
            rectification_responsible_party_id="team-logistics-01",
            rectification_due_at="2026-08-08T10:00:00+08:00",
            rectification_evidence=[_closed_evidence()],
            rectification_description="已佩戴高可视背心",
            recheck_conclusion="整改证据充分，复查通过",
            created_at=closed_candidate.occurred_at,
            updated_at=closed_at,
            transitions=closed_transitions,
        )
    )
    return cases


def demo_submissions() -> list[RectificationEvidenceSubmissionRecord]:
    return [
        RectificationEvidenceSubmissionRecord(
            submission_id="submission-case-recheck-no-evidence-6",
            case_id="case-recheck-no-evidence",
            actor_id="officer-01",
            actor_name="现场安全员",
            actor_role="SITE_SAFETY_OFFICER",
            reason="现场已完成整改",
            created_at="2026-08-07T11:05:00+08:00",
            description="已完成防卷入整改并复核作业要求",
            evidence=[_recheck_evidence()],
        ),
        RectificationEvidenceSubmissionRecord(
            submission_id="submission-case-closed-01-6",
            case_id="case-closed-01",
            actor_id="officer-01",
            actor_name="现场安全员",
            actor_role="SITE_SAFETY_OFFICER",
            reason="现场已完成整改",
            created_at="2026-08-07T12:01:00+08:00",
            description="已佩戴高可视背心",
            evidence=[_closed_evidence()],
        ),
    ]
