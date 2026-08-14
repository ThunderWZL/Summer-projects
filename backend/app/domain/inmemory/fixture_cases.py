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
from app.domain.inmemory.fixture_candidates import build_fixture_candidate
from app.domain.inmemory.site_context import MemorySiteContext
from app.domain.resolver import DeterministicInvestigationResolver


_RESOLVER = DeterministicInvestigationResolver(MemorySiteContext())


def _candidate(
    case_id: str,
    camera_id: str,
    ppe_type: str,
    occurred_at: str,
) -> CandidateEvidence:
    candidate = build_fixture_candidate(
        camera_id,
        "session-demo-01",
        namespace="seed",
        candidate_suffix=case_id,
    )
    if candidate is None or candidate.ppe_type.value != ppe_type:
        raise ValueError(f"unsupported seed candidate for {camera_id} {ppe_type}")
    return candidate.model_copy(
        update={
            "candidate_id": f"candidate-seed-{case_id}",
            "person_track_id": f"track-seed-{case_id}",
            "occurred_at": datetime.fromisoformat(occurred_at),
        },
        deep=True,
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


def _resolved_investigation(
    candidate: CandidateEvidence,
    *,
    recommendation: str | None,
    responsible_party_id: str | None = None,
    due_at: str | None = None,
    citation: dict[str, str | None] | None = None,
) -> InvestigationResult:
    resolved = _RESOLVER.resolve(candidate, {})
    rectification = None
    if recommendation and responsible_party_id and due_at:
        rectification = {
            "responsible_party_id": responsible_party_id,
            "due_at": due_at,
            "reason": recommendation,
        }
    return InvestigationResult.model_validate(
        {
            "facts": resolved.facts,
            "conflicts": resolved.conflicts,
            "missing_fields": resolved.missing_fields,
            "applicable_task": resolved.applicable_task,
            "hazards": resolved.hazards,
            "required_ppe": resolved.required_ppe,
            "recommendation": recommendation,
            "rectification_recommendation": rectification,
            "citations": [citation] if citation else [],
            "tool_trace": (
                [
                    "list_eligible_responsible_parties",
                    "search_authoritative_requirements",
                ]
                if recommendation
                else []
            ),
        }
    )


def _cutting_helmet_investigation(
    candidate: CandidateEvidence,
) -> InvestigationResult:
    return _resolved_investigation(
        candidate,
        recommendation="切割作业要求佩戴安全帽，确认责任主体与期限后进入整改",
        responsible_party_id="team-electric-01",
        due_at="2026-08-10T18:00:00+08:00",
        citation={
            "document_title": "个体防护装备配备规范 第12部分：建筑",
            "standard_no": "GB 39800.12-2025",
            "section": "建筑作业个体防护装备配备",
            "source_url": (
                "https://openstd.samr.gov.cn/bzgk/std/newGbInfo?"
                "hcno=225DB0D16D458885C1C984AB6AA44012"
            ),
            "excerpt": "应依据建筑作业危害配备适用的个体防护装备。",
        },
    )


def _vehicle_vest_investigation(
    candidate: CandidateEvidence,
) -> InvestigationResult:
    return _resolved_investigation(
        candidate,
        recommendation="车辆作业区人员应佩戴高可视背心",
        responsible_party_id="team-logistics-01",
        due_at="2026-08-08T10:00:00+08:00",
        citation={
            "document_title": "建筑工人施工现场劳动保护基本配置指南",
            "standard_no": None,
            "section": "高可视警示服",
            "source_url": (
                "https://www.gov.cn/zhengce/zhengceku/2021-01/19/"
                "5580999/files/10d98ecac8cd4c68a887b0519b56768b.pdf"
            ),
            "excerpt": "车辆作业区域应按风险配备高可视警示服。",
        },
    )


def _missing_facts_investigation(
    candidate: CandidateEvidence,
) -> InvestigationResult:
    return _resolved_investigation(
        candidate,
        recommendation=None,
    )


def _rebar_gloves_investigation(
    candidate: CandidateEvidence,
) -> InvestigationResult:
    return _resolved_investigation(
        candidate,
        recommendation="钢筋搬运作业应按任务要求佩戴防护手套",
        responsible_party_id="team-structure-01",
        due_at="2026-08-08T18:00:00+08:00",
        citation={
            "document_title": "个体防护装备配备规范 第12部分：建筑",
            "standard_no": "GB 39800.12-2025",
            "section": "手部防护",
            "source_url": (
                "https://openstd.samr.gov.cn/bzgk/std/newGbInfo?"
                "hcno=225DB0D16D458885C1C984AB6AA44012"
            ),
            "excerpt": "存在手部伤害风险时应配备适用的手部防护装备。",
        },
    )


def _rotating_equipment_investigation(
    candidate: CandidateEvidence,
) -> InvestigationResult:
    return _resolved_investigation(
        candidate,
        recommendation="不应简单要求佩戴手套，应优先落实防卷入措施",
        responsible_party_id="team-mechanical-01",
        due_at="2026-08-10T18:00:00+08:00",
        citation={
            "document_title": "建筑与市政施工现场安全卫生与职业健康通用规范",
            "standard_no": "GB 55034-2022",
            "section": "机械设备作业",
            "source_url": (
                "https://www.mohurd.gov.cn/gongkai/fdzdgknr/"
                "zfhcxjsbwj/202211/20221117_768953.html"
            ),
            "excerpt": "机械设备作业应采取防止人员卷入的安全措施。",
        },
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
            "investigation_factory": _missing_facts_investigation,
        },
        {
            "case_id": "case-01",
            "camera_id": "CAM-02",
            "ppe_type": "helmet",
            "status": CaseStatus.PENDING_REVIEW,
            "occurred_at": "2026-08-07T10:00:00+08:00",
            "investigation_factory": _cutting_helmet_investigation,
        },
        {
            "case_id": "case-overdue-01",
            "camera_id": "CAM-03",
            "ppe_type": "gloves",
            "status": CaseStatus.RECTIFICATION_OPEN,
            "occurred_at": "2026-08-07T10:30:00+08:00",
            "rectification_responsible_party_id": "team-structure-01",
            "rectification_due_at": "2026-08-08T18:00:00+08:00",
            "investigation_factory": _rebar_gloves_investigation,
        },
        {
            "case_id": "case-recheck-no-evidence",
            "camera_id": "CAM-04",
            "ppe_type": "gloves",
            "status": CaseStatus.PENDING_REVIEW,
            "occurred_at": "2026-08-07T11:00:00+08:00",
            "investigation_factory": _rotating_equipment_investigation,
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
                investigation=item["investigation_factory"](candidate),
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
            investigation=_vehicle_vest_investigation(closed_candidate),
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
