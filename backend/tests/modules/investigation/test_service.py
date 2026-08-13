from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from app.contracts import (
    CandidateEvidence,
    CaseSnapshot,
    CaseStatus,
    Citation,
    InvestigationResult,
    PpeType,
    RectificationRecommendation,
)
from app.domain.case_workflow import CaseWorkflow, RecordInvestigation
from app.domain.inmemory.case_store import InMemoryCaseStore
from app.domain.inmemory.site_context import MemorySiteContext
from app.domain.investigation import InvestigationCaseNotFound
from app.domain.resolver import DeterministicInvestigationResolver
from app.modules.investigation.agent import (
    AgentInvestigationContext,
    AgentRunResult,
)
from app.modules.investigation.service import InvestigationService


OCCURRED_AT = datetime.fromisoformat("2026-08-07T10:00:00+08:00")


def make_candidate(camera_id: str) -> CandidateEvidence:
    return CandidateEvidence.model_validate(
        {
            "candidate_id": f"candidate-{camera_id}",
            "session_id": "session-01",
            "camera_id": camera_id,
            "person_track_id": "track-17",
            "ppe_type": "gloves",
            "evidence_kind": "MISSING_POSITIVE_ASSOCIATION",
            "confidence": 0.91,
            "model_name": "ppe-yolo",
            "weights_sha256": "a" * 64,
            "aggregation_method": "weighted_mean",
            "aggregation_parameters": {"minimum_frames": 3},
            "occurred_at": OCCURRED_AT.isoformat(),
            "first_seen_ms": 1_000,
            "last_seen_ms": 2_000,
            "frames": [
                {
                    "timestamp_ms": 1_500,
                    "image_url": "/evidence/key.jpg",
                    "image_width": 1920,
                    "image_height": 1080,
                    "frame_role": "REPRESENTATIVE",
                    "person_box": {"x1": 10, "y1": 20, "x2": 110, "y2": 220},
                }
            ],
        }
    )


def make_case(
    camera_id: str,
    *,
    case_id: str = "case-investigation",
    human_facts: dict[str, object] | None = None,
) -> CaseSnapshot:
    candidate = make_candidate(camera_id)
    return CaseSnapshot(
        case_id=case_id,
        session_id=candidate.session_id,
        camera_id=candidate.camera_id,
        person_track_id=candidate.person_track_id,
        ppe_type=candidate.ppe_type,
        status=CaseStatus.INVESTIGATING,
        version=3,
        candidate=candidate,
        human_facts=human_facts or {},
        created_at=candidate.occurred_at,
        updated_at=candidate.occurred_at,
    )


def make_citation() -> Citation:
    return Citation(
        document_title="个体防护装备配备规范",
        section="手部防护",
        source_url="https://example.test/standard",
        excerpt="钢筋搬运应根据风险配备手部防护。",
    )


def make_agent_result(*, citations: list[Citation] | None = None) -> AgentRunResult:
    return AgentRunResult(
        recommendation="钢筋搬运存在手部伤害风险，应佩戴手套。",
        rectification_recommendation=RectificationRecommendation(
            responsible_party_id="team-structure-01",
            due_at=datetime.fromisoformat("2026-08-07T10:30:00+08:00"),
            reason="在规则时限内完成手部防护整改",
        ),
        citations=[make_citation()] if citations is None else citations,
        tool_trace=[
            "list_eligible_responsible_parties",
            "search_authoritative_requirements",
        ],
    )


class SpyStore:
    def __init__(self, snapshot: CaseSnapshot | None) -> None:
        self.snapshot = snapshot
        self.commit_calls = 0

    def get(self, case_id: str) -> CaseSnapshot | None:
        if self.snapshot is None or self.snapshot.case_id != case_id:
            return None
        return self.snapshot.model_copy(deep=True)

    def commit(self, *args, **kwargs):
        self.commit_calls += 1
        raise AssertionError("InvestigationService must not commit workflow state")


class CountingAgent:
    def __init__(self, result: object) -> None:
        self.result = result
        self.calls: list[AgentInvestigationContext] = []

    def investigate(self, context: AgentInvestigationContext):
        self.calls.append(context)
        return self.result


def make_service(store: SpyStore, agent: CountingAgent) -> InvestigationService:
    return InvestigationService(
        store=store,
        resolver=DeterministicInvestigationResolver(MemorySiteContext()),
        agent=agent,
    )


def test_missing_case_raises_typed_investigation_error() -> None:
    store = SpyStore(None)
    agent = CountingAgent(make_agent_result())

    with pytest.raises(InvestigationCaseNotFound, match="missing-case"):
        make_service(store, agent).investigate("missing-case")


def test_incomplete_resolver_result_does_not_invoke_agent() -> None:
    store = SpyStore(make_case("CAM-01"))
    agent = CountingAgent(make_agent_result())

    result = make_service(store, agent).investigate("case-investigation")

    assert agent.calls == []
    assert result.missing_fields == ["active_work_permit", "task_code"]
    assert result.recommendation is None
    assert result.citations == []


def test_complete_resolver_result_invokes_agent_exactly_once_without_committing() -> None:
    store = SpyStore(make_case("CAM-03"))
    agent = CountingAgent(make_agent_result())

    result = make_service(store, agent).investigate("case-investigation")

    assert len(agent.calls) == 1
    assert store.commit_calls == 0
    assert result.applicable_task == "HANDLING_REBAR"


def test_final_applicability_fields_only_come_from_resolver() -> None:
    forged_agent_output = SimpleNamespace(
        recommendation="伪造适用性字段不应生效",
        rectification_recommendation=None,
        citations=[make_citation()],
        tool_trace=["search_authoritative_requirements"],
        applicable_task="ROTATING_EQUIPMENT_OPERATION",
        hazards=["伪造危害"],
        required_ppe=[PpeType.HELMET],
    )
    store = SpyStore(make_case("CAM-03"))

    result = make_service(store, CountingAgent(forged_agent_output)).investigate(
        "case-investigation"
    )

    assert result.applicable_task == "HANDLING_REBAR"
    assert result.hazards == ["手部伤害风险"]
    assert result.required_ppe == [PpeType.GLOVES]


def test_valid_agent_responsibility_is_mapped_to_rectification_recommendation() -> None:
    expected = make_agent_result().rectification_recommendation
    store = SpyStore(make_case("CAM-03"))

    result = make_service(store, CountingAgent(make_agent_result())).investigate(
        "case-investigation"
    )

    assert result.rectification_recommendation == expected


class NoActorRoles:
    def role_for(self, actor_id: str):
        return None


def record_with_workflow(investigation: InvestigationResult) -> CaseSnapshot:
    store = InMemoryCaseStore()
    store.create(make_case("CAM-03"))
    workflow = CaseWorkflow(
        store=store,
        actor_roles=NoActorRoles(),
        clock=lambda: OCCURRED_AT,
        responsible_party_is_eligible=lambda _case, _party_id: True,
    )
    return workflow.apply(
        "case-investigation", RecordInvestigation(3, investigation)
    )


def test_empty_agent_citations_remain_empty_and_workflow_marks_incomplete() -> None:
    service_result = make_service(
        SpyStore(make_case("CAM-03")),
        CountingAgent(make_agent_result(citations=[])),
    ).investigate("case-investigation")

    recorded = record_with_workflow(service_result)

    assert service_result.citations == []
    assert recorded.status is CaseStatus.NEEDS_HUMAN_FACTS


def test_complete_service_result_enters_pending_review_through_workflow() -> None:
    service_result = make_service(
        SpyStore(make_case("CAM-03")), CountingAgent(make_agent_result())
    ).investigate("case-investigation")

    recorded = record_with_workflow(service_result)

    assert recorded.status is CaseStatus.PENDING_REVIEW
