from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import (
    build_case_workflow,
    get_case_pipeline,
    get_case_store,
    get_case_workflow,
    get_clock,
    get_event_hub,
    get_inmemory_video_analysis,
    get_investigation_port,
    get_site_context,
    get_session_manager,
    get_user_directory,
    shutdown_database_runtime,
)
from app.config import get_settings
from app.contracts import Citation, InvestigationResult, PpeType
from app.domain.case_workflow import CaseWorkflow
from app.domain.inmemory.case_store import InMemoryCaseStore
from app.domain.inmemory.fixture_candidates import build_fixture_candidate
from app.main import app
from app.modules.vlm_review.adapters.fixed import FixedVlmAdapter
from app.modules.vlm_review.service import VlmReviewService
from app.services.case_pipeline import CasePipeline


NOW = datetime.fromisoformat("2026-08-15T10:00:00+08:00")


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch: pytest.MonkeyPatch):
    shutdown_database_runtime()
    monkeypatch.setenv(
        "DATABASE_URL",
        f"sqlite:///{tmp_path / 'end-to-end.db'}",
    )
    get_settings.cache_clear()
    yield
    shutdown_database_runtime()
    get_settings.cache_clear()


class FactsCompletingInvestigation:
    """Independent integration fixture for the human-facts workflow branch."""

    def __init__(self, store: InMemoryCaseStore) -> None:
        self._store = store

    def investigate(self, case_id: str) -> InvestigationResult:
        snapshot = self._store.get(case_id)
        assert snapshot is not None
        complete = snapshot.human_facts.get("task_code") == "SCAFFOLD_INSPECTION"
        return InvestigationResult(
            facts={"task_code": "SCAFFOLD_INSPECTION"} if complete else {},
            conflicts=[],
            missing_fields=[] if complete else ["task_code"],
            applicable_task="SCAFFOLD_INSPECTION" if complete else None,
            hazards=["高处坠落"] if complete else [],
            required_ppe=["helmet"] if complete else [],
            recommendation="脚手架巡检应佩戴安全帽" if complete else None,
            rectification_recommendation=None,
            citations=(
                [
                    Citation(
                        document_title="测试上下文安全要求",
                        section="脚手架巡检",
                        source_url="https://example.test/scaffold",
                        excerpt="脚手架巡检应按风险佩戴安全帽。",
                    )
                ]
                if complete
                else []
            ),
            tool_trace=["search_authoritative_requirements"] if complete else [],
        )


def facts_workflow_fixture() -> tuple[CasePipeline, InMemoryCaseStore, CaseWorkflow]:
    store = InMemoryCaseStore()
    workflow = build_case_workflow(
        store,
        get_user_directory(),
        get_site_context(),
        lambda: NOW,
    )
    vlm = VlmReviewService(
        store,
        FixedVlmAdapter(),
        workflow,
        model_provider="fixture",
        model_parameters={"temperature": 0},
        clock=lambda: NOW,
        max_retries=0,
        retry_delay_seconds=0,
    )
    pipeline = CasePipeline(
        store,
        workflow,
        vlm,
        FactsCompletingInvestigation(store),
        lambda: NOW,
    )
    return pipeline, store, workflow


def setup_function() -> None:
    for dependency in (
        get_session_manager,
        get_inmemory_video_analysis,
        get_event_hub,
        get_case_pipeline,
        get_investigation_port,
        get_case_store,
    ):
        dependency.cache_clear()
    app.dependency_overrides[get_clock] = lambda: lambda: NOW


def teardown_function() -> None:
    app.dependency_overrides.pop(get_clock, None)


async def request(method: str, path: str, payload: dict | None = None):
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        return await client.request(method, path, json=payload)


async def analyze(video_id: str):
    started = await request(
        "POST", "/api/v1/analysis-sessions", {"video_id": video_id}
    )
    assert started.status_code == 201
    events = get_session_manager().subscribe_events(started.json()["session_id"])
    received = []
    while True:
        event = await anext(events)
        received.append(event)
        if event.event_type.value in {"SESSION_FINISHED", "SESSION_FAILED"}:
            break
    await events.aclose()
    return received


def test_new_demo_case_uses_system_time_and_current_permit() -> None:
    started_before = datetime.now(timezone.utc)

    async def scenario():
        events = await analyze("video-no-vest-02")
        created = next(
            event
            for event in events
            if event.event_type.value == "CANDIDATE_CREATED"
        )
        snapshot = get_case_store().get(created.case_id)
        assert snapshot is not None
        return snapshot

    snapshot = asyncio.run(scenario())
    finished_after = datetime.now(timezone.utc)

    assert started_before <= snapshot.created_at <= finished_after
    assert timedelta(0) <= (
        snapshot.candidate.occurred_at - snapshot.created_at
    ) <= timedelta(minutes=10)
    assert snapshot.investigation is not None
    assert snapshot.investigation.facts["active_permit_ids"] == ["wp-0201"]


def test_independent_facts_context_closes_through_public_commands_v1_to_v10() -> None:
    async def scenario():
        pipeline, store, workflow = facts_workflow_fixture()
        candidate = build_fixture_candidate(
            "CAM-02",
            "session-facts-workflow",
            namespace="integration",
            ppe_type=PpeType.HELMET,
        )
        assert candidate is not None
        initial_snapshot = await pipeline.process_candidate(candidate)
        app.dependency_overrides[get_case_store] = lambda: store
        app.dependency_overrides[get_case_pipeline] = lambda: pipeline
        app.dependency_overrides[get_case_workflow] = lambda: workflow
        try:
            case_id = initial_snapshot.case_id
            initial = await request("GET", f"/api/v1/cases/{case_id}")
            facts = await request(
                "POST",
                f"/api/v1/cases/{case_id}/facts",
                {
                    "command_type": "SUBMIT_FACTS",
                    "actor_id": "officer-01",
                    "expected_version": 4,
                    "reason": "确认脚手架巡检任务",
                    "facts": {"task_code": "SCAFFOLD_INSPECTION"},
                },
            )
            review = await request(
                "POST",
                f"/api/v1/cases/{case_id}/review",
                {
                    "command_type": "APPROVE_RECTIFICATION",
                    "actor_id": "reviewer-01",
                    "expected_version": 7,
                    "reason": "安全帽要求适用，批准整改",
                    "responsible_party_id": "team-cutting-02",
                    "rectification_due_at": "2026-09-01T18:00:00+08:00",
                },
            )
            evidence = await request(
                "POST",
                f"/api/v1/cases/{case_id}/rectification-evidence",
                {
                    "command_type": "SUBMIT_RECTIFICATION_EVIDENCE",
                    "actor_id": "officer-01",
                    "expected_version": 8,
                    "reason": "现场已完成整改",
                    "description": "人员已正确佩戴安全帽",
                    "evidence": [
                        {
                            "evidence_id": "evidence-facts-after",
                            "image_url": "/evidence/integration/after.jpg",
                            "captured_at": "2026-08-15T11:00:00+08:00",
                        }
                    ],
                },
            )
            closed = await request(
                "POST",
                f"/api/v1/cases/{case_id}/recheck",
                {
                    "command_type": "APPROVE_CLOSURE",
                    "actor_id": "reviewer-01",
                    "expected_version": 9,
                    "reason": "整改证据完整",
                    "recheck_conclusion": "复查通过，事件关闭",
                },
            )
            detail = await request("GET", f"/api/v1/cases/{case_id}")
            return initial, facts, review, evidence, closed, detail
        finally:
            for dependency in (get_case_store, get_case_pipeline, get_case_workflow):
                app.dependency_overrides.pop(dependency, None)

    initial, facts, review, evidence, closed, detail_response = asyncio.run(scenario())

    assert initial.json()["snapshot"]["status"] == "NEEDS_HUMAN_FACTS"
    assert [item["to_status"] for item in initial.json()["timeline"]] == [
        "YOLO_CANDIDATE",
        "VLM_REVIEWED",
        "INVESTIGATING",
        "NEEDS_HUMAN_FACTS",
    ]
    assert facts.status_code == 200
    assert (facts.json()["snapshot"]["status"], facts.json()["version"]) == (
        "PENDING_REVIEW",
        7,
    )
    assert review.status_code == 200, review.text
    assert evidence.status_code == 200, evidence.text
    assert closed.status_code == 200, closed.text
    assert [(response.status_code, response.json()["version"]) for response in (review, evidence, closed)] == [
        (200, 8), (200, 9), (200, 10),
    ]
    detail = detail_response.json()
    assert detail["snapshot"]["status"] == "CLOSED"
    assert [item["to_status"] for item in detail["timeline"]] == [
        "YOLO_CANDIDATE",
        "VLM_REVIEWED",
        "INVESTIGATING",
        "NEEDS_HUMAN_FACTS",
        "REINVESTIGATE",
        "INVESTIGATING",
        "PENDING_REVIEW",
        "RECTIFICATION_OPEN",
        "RECHECK_PENDING",
        "CLOSED",
    ]
    assert [item["source"] for item in detail["timeline"]] == [
        "YOLO", "VLM", "AGENT", "AGENT", "HUMAN",
        "AGENT", "AGENT", "HUMAN", "HUMAN", "HUMAN",
    ]
    occurred = [datetime.fromisoformat(item["occurred_at"]) for item in detail["timeline"]]
    assert occurred == sorted(occurred)
    assert [item["submission_type"] for item in detail["human_submissions"]] == [
        "FACTS",
        "RECTIFICATION_EVIDENCE",
    ]
    assert detail["human_submissions"][0]["facts"] == {
        "task_code": "SCAFFOLD_INSPECTION"
    }


def test_six_demo_channels_expose_the_frozen_explainable_outcomes() -> None:
    async def scenario():
        video_ids = (
            "video-safe-01",
            "video-no-vest-02",
            "video-no-gloves-01",
            "video-no-vest-gloves-02",
            "video-no-ppe",
            "video-mixed-wearing",
        )
        results = []
        details = []
        for video_id in video_ids:
            events = await analyze(video_id)
            created = [
                event
                for event in events
                if event.event_type.value == "CANDIDATE_CREATED"
            ]
            results.append((events, created))
            details.append(
                [
                    (await request("GET", f"/api/v1/cases/{event.case_id}")).json()
                    for event in created
                ]
            )
        return results, details

    results, details = asyncio.run(scenario())

    expected_counts = (0, 1, 1, 2, 3, 7)
    assert [len(created) for _, created in results] == list(expected_counts)
    assert [
        (events[-1].payload.candidate_count, events[-1].payload.case_count)
        for events, _ in results
    ] == [(count, count) for count in expected_counts]
    assert details[0] == []
    statuses = [
        detail["snapshot"]["status"]
        for channel in details[1:]
        for detail in channel
    ]
    assert statuses == ["NEEDS_HUMAN_FACTS"] * sum(expected_counts[1:])
    assert all(
        set(detail["snapshot"]["investigation"]["required_ppe"])
        == {"helmet", "gloves", "vest"}
        for channel in details[1:]
        for detail in channel
    )
    assert len(details[1][0]["snapshot"]["candidate"]["frames"]) == 3
