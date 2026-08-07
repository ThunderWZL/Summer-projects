from datetime import datetime

import pytest

from app.contracts import (
    ActorRole,
    ApproveClosure,
    ApproveRectification,
    CandidateEvidence,
    CaseSnapshot,
    CaseStatus,
    CaseTransition,
    InvestigationResult,
    RejectCase,
    RejectRecheck,
    RequestReinvestigation,
    SubmitFacts,
    SubmitRectificationEvidence,
    VlmReviewResult,
)
from app.domain.case_workflow import (
    CaseNotFound,
    CaseWorkflow,
    CommandNotAllowed,
    EvidenceRequired,
    InvalidDeadline,
    PermissionDenied,
    RecordInvestigation,
    RecordVlmReview,
    RestartInvestigation,
    ReviewMismatch,
    StartInvestigation,
    StaleCaseVersion,
)


NOW = datetime.fromisoformat("2026-08-07T10:40:00+08:00")


def make_case(status: CaseStatus, version: int = 1) -> CaseSnapshot:
    candidate = CandidateEvidence.model_validate(
        {
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
    return CaseSnapshot(
        case_id="case-01",
        session_id="session-01",
        camera_id="CAM-01",
        person_track_id="track-17",
        ppe_type="helmet",
        status=status,
        version=version,
        candidate=candidate,
        created_at=candidate.occurred_at,
        updated_at=candidate.occurred_at,
    )


class MemoryCaseStore:
    def __init__(self, case: CaseSnapshot) -> None:
        self.case = case

    def get(self, case_id: str) -> CaseSnapshot | None:
        return self.case if case_id == self.case.case_id else None

    def commit(
        self,
        snapshot: CaseSnapshot,
        expected_version: int,
        transition: CaseTransition,
    ) -> CaseSnapshot:
        stored = snapshot.model_copy(
            update={
                "version": expected_version + 1,
                "updated_at": transition.occurred_at,
                "transitions": [*self.case.transitions, transition],
            }
        )
        self.case = stored
        return stored


class FixedActorRoles:
    def role_for(self, actor_id: str) -> ActorRole | None:
        return {
            "officer-01": ActorRole.SITE_SAFETY_OFFICER,
            "reviewer-01": ActorRole.PROJECT_SAFETY_REVIEWER,
        }.get(actor_id)


def make_workflow(case: CaseSnapshot) -> CaseWorkflow:
    return CaseWorkflow(
        store=MemoryCaseStore(case),
        actor_roles=FixedActorRoles(),
        clock=lambda: NOW,
    )


def test_officer_can_submit_facts_requested_by_investigation() -> None:
    workflow = make_workflow(
        make_case(CaseStatus.NEEDS_HUMAN_FACTS, version=3)
    )
    command = SubmitFacts(
        actor_id="officer-01",
        expected_version=3,
        reason="确认正在进行切割作业",
        facts={"task_code": "HOT_WORK_CUTTING"},
    )

    result = workflow.apply("case-01", command)

    assert (result.status, result.version, result.human_facts) == (
        CaseStatus.REINVESTIGATE,
        4,
        {"task_code": "HOT_WORK_CUTTING"},
    )


def test_command_with_an_old_version_is_rejected() -> None:
    workflow = make_workflow(
        make_case(CaseStatus.NEEDS_HUMAN_FACTS, version=4)
    )
    command = SubmitFacts(
        actor_id="officer-01",
        expected_version=3,
        reason="基于旧页面提交",
        facts={"task_code": "HOT_WORK_CUTTING"},
    )

    with pytest.raises(StaleCaseVersion, match="expected version 3, current 4"):
        workflow.apply("case-01", command)


def test_reviewer_cannot_submit_site_facts() -> None:
    workflow = make_workflow(make_case(CaseStatus.NEEDS_HUMAN_FACTS))
    command = SubmitFacts(
        actor_id="reviewer-01",
        expected_version=1,
        reason="尝试代替现场补充",
        facts={"task_code": "HOT_WORK_CUTTING"},
    )

    with pytest.raises(PermissionDenied, match="reviewer-01"):
        workflow.apply("case-01", command)


def test_facts_cannot_be_submitted_from_an_unrelated_state() -> None:
    workflow = make_workflow(make_case(CaseStatus.PENDING_REVIEW))
    command = SubmitFacts(
        actor_id="officer-01",
        expected_version=1,
        reason="状态不允许时提交",
        facts={"task_code": "HOT_WORK_CUTTING"},
    )

    with pytest.raises(CommandNotAllowed, match="PENDING_REVIEW"):
        workflow.apply("case-01", command)


def test_reviewer_can_approve_rectification_with_owner_and_deadline() -> None:
    workflow = make_workflow(make_case(CaseStatus.PENDING_REVIEW, version=3))
    command = ApproveRectification(
        actor_id="reviewer-01",
        expected_version=3,
        reason="证据和依据完整",
        responsible_party_id="team-electric-01",
        rectification_due_at="2026-08-08T18:00:00+08:00",
    )

    result = workflow.apply("case-01", command)

    assert (
        result.status,
        result.version,
        result.rectification_responsible_party_id,
        result.rectification_due_at,
    ) == (
        CaseStatus.RECTIFICATION_OPEN,
        4,
        "team-electric-01",
        datetime.fromisoformat("2026-08-08T18:00:00+08:00"),
    )


@pytest.mark.parametrize(
    ("command", "expected_status"),
    [
        (
            RejectCase(
                actor_id="reviewer-01",
                expected_version=2,
                reason="确认是海报中的人物",
            ),
            CaseStatus.HUMAN_REJECTED,
        ),
        (
            RequestReinvestigation(
                actor_id="reviewer-01",
                expected_version=2,
                reason="许可与任务信息冲突",
            ),
            CaseStatus.REINVESTIGATE,
        ),
    ],
)
def test_reviewer_can_resolve_a_pending_case(
    command: RejectCase | RequestReinvestigation,
    expected_status: CaseStatus,
) -> None:
    workflow = make_workflow(make_case(CaseStatus.PENDING_REVIEW, version=2))

    result = workflow.apply("case-01", command)

    assert (result.status, result.version) == (expected_status, 3)


def test_officer_can_submit_rectification_evidence() -> None:
    workflow = make_workflow(
        make_case(CaseStatus.RECTIFICATION_OPEN, version=4)
    )
    command = SubmitRectificationEvidence.model_validate(
        {
            "actor_id": "officer-01",
            "expected_version": 4,
            "reason": "现场已完成整改",
            "description": "已补戴安全帽并完成班前检查",
            "evidence": [
                {
                    "evidence_id": "evidence-after-01",
                    "image_url": "/evidence/after.jpg",
                    "captured_at": "2026-08-07T12:00:00+08:00",
                }
            ],
        }
    )

    result = workflow.apply("case-01", command)

    assert (
        result.status,
        result.version,
        result.rectification_description,
        [item.evidence_id for item in result.rectification_evidence],
    ) == (
        CaseStatus.RECHECK_PENDING,
        5,
        "已补戴安全帽并完成班前检查",
        ["evidence-after-01"],
    )


def test_reviewer_can_close_a_case_after_evidence_is_submitted() -> None:
    workflow = make_workflow(
        make_case(CaseStatus.RECTIFICATION_OPEN, version=4)
    )
    workflow.apply(
        "case-01",
        SubmitRectificationEvidence.model_validate(
            {
                "actor_id": "officer-01",
                "expected_version": 4,
                "reason": "现场已完成整改",
                "description": "已补戴安全帽",
                "evidence": [
                    {
                        "evidence_id": "evidence-after-01",
                        "image_url": "/evidence/after.jpg",
                        "captured_at": "2026-08-07T12:00:00+08:00",
                    }
                ],
            }
        ),
    )

    result = workflow.apply(
        "case-01",
        ApproveClosure(
            actor_id="reviewer-01",
            expected_version=5,
            reason="整改前后证据完整",
            recheck_conclusion="复查通过，可以关闭",
        ),
    )

    assert (result.status, result.version, result.recheck_conclusion) == (
        CaseStatus.CLOSED,
        6,
        "复查通过，可以关闭",
    )


def test_case_without_rectification_evidence_cannot_be_closed() -> None:
    workflow = make_workflow(make_case(CaseStatus.RECHECK_PENDING, version=5))
    command = ApproveClosure(
        actor_id="reviewer-01",
        expected_version=5,
        reason="尝试关闭",
        recheck_conclusion="复查通过",
    )

    with pytest.raises(EvidenceRequired, match="rectification evidence"):
        workflow.apply("case-01", command)


def test_reviewer_can_return_failed_recheck_to_rectification() -> None:
    workflow = make_workflow(make_case(CaseStatus.RECHECK_PENDING, version=5))
    command = RejectRecheck(
        actor_id="reviewer-01",
        expected_version=5,
        reason="照片无法证明整改完成",
        recheck_conclusion="重新拍摄包含人员和安全帽的现场照片",
    )

    result = workflow.apply("case-01", command)

    assert (result.status, result.version, result.recheck_conclusion) == (
        CaseStatus.RECTIFICATION_OPEN,
        6,
        "重新拍摄包含人员和安全帽的现场照片",
    )


def test_confirmed_candidate_can_run_and_restart_investigation() -> None:
    workflow = make_workflow(make_case(CaseStatus.YOLO_CANDIDATE))
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
            "reviewed_at": "2026-08-07T10:35:00+08:00",
        }
    )
    investigation = InvestigationResult.model_validate(
        {
            "facts": {"task_code": "HOT_WORK_CUTTING"},
            "conflicts": [],
            "missing_fields": [],
            "applicable_task": "HOT_WORK_CUTTING",
            "hazards": ["飞溅"],
            "required_ppe": ["helmet", "goggles"],
            "recommendation": "进入整改审核",
            "rectification_recommendation": {
                "responsible_party_id": "team-electric-01",
                "due_at": "2026-08-08T18:00:00+08:00",
                "reason": "切割作业必须佩戴规定防护装备",
            },
            "citations": [
                {
                    "document_title": "个体防护装备配备规范",
                    "standard_no": "GB 39800.12-2025",
                    "section": "建筑作业防护",
                    "source_url": "https://openstd.samr.gov.cn/example",
                    "excerpt": "切割作业应根据危害配备防护装备。",
                }
            ],
            "tool_trace": ["get_zone_at", "search_authoritative_requirements"],
        }
    )

    reviewed = workflow.apply("case-01", RecordVlmReview(1, review))
    investigating = workflow.apply("case-01", StartInvestigation(2))
    pending = workflow.apply(
        "case-01", RecordInvestigation(3, investigation)
    )
    returned = workflow.apply(
        "case-01",
        RequestReinvestigation(
            actor_id="reviewer-01",
            expected_version=4,
            reason="需要复核许可时间",
        ),
    )
    restarted = workflow.apply("case-01", RestartInvestigation(5))

    assert [
        reviewed.status,
        investigating.status,
        pending.status,
        returned.status,
        restarted.status,
    ] == [
        CaseStatus.VLM_REVIEWED,
        CaseStatus.INVESTIGATING,
        CaseStatus.PENDING_REVIEW,
        CaseStatus.REINVESTIGATE,
        CaseStatus.INVESTIGATING,
    ]


def test_insufficient_vlm_evidence_cannot_start_investigation() -> None:
    workflow = make_workflow(make_case(CaseStatus.YOLO_CANDIDATE))
    review = VlmReviewResult.model_validate(
        {
            "candidate_id": "candidate-01",
            "verdict": "CONFIRMED",
            "person_track_id": "track-17",
            "ppe_type": "helmet",
            "association": "AMBIGUOUS",
            "body_part_visible": False,
            "persistent": False,
            "poster_or_reflection": False,
            "evidence_sufficient": False,
            "evidence_timestamps_ms": [1_500],
            "reason": "头部被遮挡，证据不足",
            "model_name": "fixed-reviewer",
            "model_provider": "fixture",
            "model_parameters": {"temperature": 0},
            "reviewed_at": "2026-08-07T10:35:00+08:00",
        }
    )

    rejected = workflow.apply("case-01", RecordVlmReview(1, review))

    with pytest.raises(CommandNotAllowed, match="VLM_REJECTED"):
        workflow.apply("case-01", StartInvestigation(2))
    assert rejected.status is CaseStatus.VLM_REJECTED


def test_incomplete_investigation_requests_human_facts() -> None:
    workflow = make_workflow(make_case(CaseStatus.INVESTIGATING, version=3))
    investigation = InvestigationResult.model_validate(
        {
            "facts": {},
            "conflicts": ["许可任务与现场任务不一致"],
            "missing_fields": ["actual_task_code"],
            "hazards": [],
            "required_ppe": [],
            "recommendation": None,
            "rectification_recommendation": None,
            "citations": [],
            "tool_trace": ["find_active_work_permits"],
        }
    )

    result = workflow.apply(
        "case-01", RecordInvestigation(3, investigation)
    )

    assert result.status is CaseStatus.NEEDS_HUMAN_FACTS


def test_unknown_case_is_reported_with_a_domain_error() -> None:
    workflow = make_workflow(make_case(CaseStatus.NEEDS_HUMAN_FACTS))
    command = SubmitFacts(
        actor_id="officer-01",
        expected_version=1,
        reason="补充事实",
        facts={"task_code": "HOT_WORK_CUTTING"},
    )

    with pytest.raises(CaseNotFound, match="missing-case"):
        workflow.apply("missing-case", command)


def test_vlm_review_for_another_candidate_is_rejected() -> None:
    workflow = make_workflow(make_case(CaseStatus.YOLO_CANDIDATE))
    review = VlmReviewResult.model_validate(
        {
            "candidate_id": "candidate-other",
            "verdict": "CONFIRMED",
            "person_track_id": "track-17",
            "ppe_type": "helmet",
            "association": "MATCHED",
            "body_part_visible": True,
            "persistent": True,
            "poster_or_reflection": False,
            "evidence_sufficient": True,
            "evidence_timestamps_ms": [1_500],
            "reason": "复核结果属于另一候选",
            "model_name": "fixed-reviewer",
            "model_provider": "fixture",
            "model_parameters": {},
            "reviewed_at": "2026-08-07T10:35:00+08:00",
        }
    )

    with pytest.raises(ReviewMismatch, match="candidate_id"):
        workflow.apply("case-01", RecordVlmReview(1, review))


def test_rectification_deadline_must_be_in_the_future() -> None:
    workflow = make_workflow(make_case(CaseStatus.PENDING_REVIEW))
    command = ApproveRectification(
        actor_id="reviewer-01",
        expected_version=1,
        reason="设置了过期时间",
        responsible_party_id="team-electric-01",
        rectification_due_at="2026-08-07T09:00:00+08:00",
    )

    with pytest.raises(InvalidDeadline, match="future"):
        workflow.apply("case-01", command)


@pytest.mark.parametrize(
    ("status", "command"),
    [
        (
            CaseStatus.PENDING_REVIEW,
            ApproveRectification(
                actor_id="officer-01",
                expected_version=1,
                reason="越权批准整改",
                responsible_party_id="team-electric-01",
                rectification_due_at="2026-08-08T18:00:00+08:00",
            ),
        ),
        (
            CaseStatus.RECHECK_PENDING,
            ApproveClosure(
                actor_id="officer-01",
                expected_version=1,
                reason="越权关闭事件",
                recheck_conclusion="尝试关闭",
            ),
        ),
    ],
)
def test_officer_cannot_approve_or_close(
    status: CaseStatus,
    command: ApproveRectification | ApproveClosure,
) -> None:
    workflow = make_workflow(make_case(status))

    with pytest.raises(PermissionDenied, match="officer-01"):
        workflow.apply("case-01", command)


def test_human_action_is_returned_in_the_case_timeline() -> None:
    workflow = make_workflow(make_case(CaseStatus.NEEDS_HUMAN_FACTS))

    result = workflow.apply(
        "case-01",
        SubmitFacts(
            actor_id="officer-01",
            expected_version=1,
            reason="确认现场任务",
            facts={"task_code": "HOT_WORK_CUTTING"},
        ),
    )

    assert result.transitions[-1].model_dump() == {
        "from_status": CaseStatus.NEEDS_HUMAN_FACTS,
        "to_status": CaseStatus.REINVESTIGATE,
        "actor_id": "officer-01",
        "actor_role": ActorRole.SITE_SAFETY_OFFICER,
        "reason": "确认现场任务",
        "occurred_at": NOW,
    }
