from __future__ import annotations

import asyncio
from datetime import datetime

import pytest

from app.contracts import (
    ActorRole,
    CaseStatus,
    Citation,
    InvestigationResult,
)
from app.domain.case_workflow import CaseWorkflow, CommandNotAllowed
from app.domain.inmemory.case_store import InMemoryCaseStore
from app.domain.inmemory.fixture_candidates import build_fixture_candidate
from app.modules.vlm_review.adapters.fixed import FixedVlmAdapter, FixedVlmScenario
from app.modules.vlm_review.errors import VlmProcessingFailed
from app.modules.vlm_review.service import VlmReviewService
from app.services.case_pipeline import CasePipeline


NOW = datetime.fromisoformat("2026-08-07T10:40:00+08:00")


class DemoActors:
    def role_for(self, actor_id: str) -> ActorRole | None:
        return {
            "officer-01": ActorRole.SITE_SAFETY_OFFICER,
            "reviewer-01": ActorRole.PROJECT_SAFETY_REVIEWER,
        }.get(actor_id)


class FixedInvestigation:
    def __init__(self, result: InvestigationResult) -> None:
        self.result = result
        self.case_ids: list[str] = []

    def investigate(self, case_id: str) -> InvestigationResult:
        self.case_ids.append(case_id)
        return self.result


class FailingVlmModel:
    async def complete(self, _request):
        raise VlmProcessingFailed("fixture unavailable", retryable=False, attempts=1)


def investigation(*, complete: bool = True) -> InvestigationResult:
    return InvestigationResult(
        facts={"task_code": "HOT_WORK_CUTTING"},
        conflicts=[],
        missing_fields=[] if complete else ["site_note"],
        applicable_task="HOT_WORK_CUTTING",
        hazards=["飞溅物"],
        required_ppe=["helmet"],
        recommendation="切割作业应佩戴安全帽" if complete else None,
        rectification_recommendation=None,
        citations=(
            [
                Citation(
                    document_title="个体防护装备配备规范",
                    section="头部防护",
                    source_url="https://example.test/helmet",
                    excerpt="切割作业应根据风险配备头部防护。",
                )
            ]
            if complete
            else []
        ),
        tool_trace=[] if not complete else ["search_authoritative_requirements"],
    )


def make_pipeline(
    *,
    scenario: FixedVlmScenario = FixedVlmScenario.AUTO,
    investigation_result: InvestigationResult | None = None,
    model=None,
) -> tuple[CasePipeline, InMemoryCaseStore, CaseWorkflow, FixedInvestigation]:
    store = InMemoryCaseStore()
    workflow = CaseWorkflow(
        store=store,
        actor_roles=DemoActors(),
        clock=lambda: NOW,
        responsible_party_is_eligible=lambda _snapshot, _party_id: True,
    )
    agent = FixedInvestigation(investigation_result or investigation())
    vlm = VlmReviewService(
        store,
        model or FixedVlmAdapter(scenario),
        workflow,
        model_provider="fixture",
        model_parameters={},
        clock=lambda: NOW,
        max_retries=0,
        retry_delay_seconds=0,
    )
    return CasePipeline(store, workflow, vlm, agent), store, workflow, agent


def candidate(camera_id: str = "CAM-02", suffix: str = "primary"):
    result = build_fixture_candidate(
        camera_id,
        session_id="session-pipeline",
        namespace="pipeline",
        candidate_suffix=suffix,
    )
    assert result is not None
    return result


def test_new_candidate_is_created_at_version_one_then_reaches_review_gate() -> None:
    pipeline, store, _, _ = make_pipeline(investigation_result=investigation(complete=False))
    evidence = candidate()

    created = pipeline.ensure_case(evidence)
    result = asyncio.run(pipeline.process_candidate(evidence))

    assert (created.status, created.version, created.transitions) == (
        CaseStatus.YOLO_CANDIDATE,
        1,
        [],
    )
    assert (result.status, result.version) == (CaseStatus.NEEDS_HUMAN_FACTS, 4)
    assert [transition.to_status for transition in result.transitions] == [
        CaseStatus.VLM_REVIEWED,
        CaseStatus.INVESTIGATING,
        CaseStatus.NEEDS_HUMAN_FACTS,
    ]
    assert store.find_by_candidate(evidence.candidate_id) == result


def test_processing_the_same_candidate_twice_does_not_duplicate_case_or_transition() -> None:
    pipeline, store, _, investigation_adapter = make_pipeline()
    evidence = candidate()

    first = asyncio.run(pipeline.process_candidate(evidence))
    second = asyncio.run(pipeline.process_candidate(evidence))

    assert second == first
    assert second.version == 4
    assert len(second.transitions) == 3
    assert len(store.list_submissions(second.case_id)) == 0
    assert investigation_adapter.case_ids == [second.case_id]


@pytest.mark.parametrize("scenario", [FixedVlmScenario.REJECT, FixedVlmScenario.UNCERTAIN])
def test_semantic_vlm_rejection_stops_without_investigation(scenario) -> None:
    pipeline, _, _, investigation_adapter = make_pipeline(scenario=scenario)

    result = asyncio.run(pipeline.process_candidate(candidate()))

    assert (result.status, result.version, result.investigation) == (
        CaseStatus.VLM_REJECTED,
        2,
        None,
    )
    assert investigation_adapter.case_ids == []


def test_vlm_technical_failure_preserves_candidate_and_business_timeline() -> None:
    pipeline, store, _, investigation_adapter = make_pipeline(model=FailingVlmModel())
    evidence = candidate()

    with pytest.raises(VlmProcessingFailed, match="fixture unavailable"):
        asyncio.run(pipeline.process_candidate(evidence))

    stored = store.find_by_candidate(evidence.candidate_id)
    assert stored is not None
    assert (stored.status, stored.version, stored.vlm_review, stored.transitions) == (
        CaseStatus.YOLO_CANDIDATE,
        1,
        None,
        [],
    )
    assert investigation_adapter.case_ids == []


@pytest.mark.parametrize(
    ("complete", "expected_status"),
    [(True, CaseStatus.PENDING_REVIEW), (False, CaseStatus.NEEDS_HUMAN_FACTS)],
)
def test_investigation_completeness_selects_the_human_gate(complete, expected_status) -> None:
    pipeline, _, _, _ = make_pipeline(investigation_result=investigation(complete=complete))

    result = asyncio.run(pipeline.process_candidate(candidate()))

    assert (result.status, result.version) == (expected_status, 4)


def test_resume_reinvestigates_and_illegal_start_is_rejected_by_workflow() -> None:
    pipeline, store, workflow, investigation_adapter = make_pipeline(
        investigation_result=investigation(complete=False)
    )
    needs_facts = asyncio.run(pipeline.process_candidate(candidate()))
    from app.contracts import SubmitFacts

    reinvestigate = workflow.apply(
        needs_facts.case_id,
        SubmitFacts(
            actor_id="officer-01",
            expected_version=needs_facts.version,
            reason="补充现场说明",
            facts={"site_note": "切割区域正在作业"},
        ),
    )
    investigation_adapter.result = investigation(complete=True)

    result = pipeline.resume_investigation(reinvestigate.case_id)

    assert [transition.to_status for transition in result.transitions[-3:]] == [
        CaseStatus.REINVESTIGATE,
        CaseStatus.INVESTIGATING,
        CaseStatus.PENDING_REVIEW,
    ]
    assert result.version == 7

    with pytest.raises(CommandNotAllowed, match="RESTART_INVESTIGATION"):
        pipeline.resume_investigation(result.case_id)
    assert store.get(result.case_id) == result
