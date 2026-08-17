from __future__ import annotations

from datetime import datetime, timedelta

from app.contracts import CaseSnapshot, CaseStatus, Citation, PpeType
from app.domain.inmemory.case_store import InMemoryCaseStore
from app.domain.inmemory.fake_investigation import FixtureInvestigation
from app.domain.inmemory.fixture_candidates import build_fixture_candidate
from app.domain.inmemory.site_context import MemorySiteContext
from app.domain.resolver import DeterministicInvestigationResolver
from app.domain.requirements_rag import RequirementQuery
from app.modules.investigation.agent import AgentInvestigationContext
from app.modules.investigation.fake import FixedInvestigationAgent
from app.modules.investigation.service import InvestigationService
from app.modules.investigation.tools import InvestigationTools


OCCURRED_AT = datetime.fromisoformat("2026-08-07T10:00:00+08:00")


class RecordingRetriever:
    def __init__(self, citations: list[Citation]) -> None:
        self.citations = citations
        self.queries: list[RequirementQuery] = []

    def search(self, query: RequirementQuery) -> list[Citation]:
        self.queries.append(query)
        return self.citations


def make_citation() -> Citation:
    return Citation(
        document_title="个体防护装备配备规范",
        section="手部防护",
        source_url="https://example.test/standard",
        excerpt="木板装订应根据风险配备手部防护。",
    )


def make_context(
    *,
    zone_id: str = "zone-03",
    zone_name: str = "无手套1装订木板区",
    task: str = "BOARD_FASTENING",
    hazards: list[str] | None = None,
    required_ppe: list[PpeType] | None = None,
    exception_note: str | None = None,
    window: int = 30,
) -> AgentInvestigationContext:
    return AgentInvestigationContext(
        case_id="case-fixed",
        zone_id=zone_id,
        zone_name=zone_name,
        occurred_at=OCCURRED_AT,
        ppe_type=PpeType.GLOVES,
        applicable_task=task,
        hazards=hazards if hazards is not None else ["木刺", "钉装伤害"],
        required_ppe=(
            required_ppe
            if required_ppe is not None
            else [PpeType.HELMET, PpeType.GLOVES, PpeType.VEST]
        ),
        exception_note=exception_note,
        rectification_window_minutes=window,
    )


def test_fixed_agent_uses_both_real_controlled_tools() -> None:
    retriever = RecordingRetriever([make_citation()])
    agent = FixedInvestigationAgent(
        InvestigationTools(MemorySiteContext(), retriever)
    )

    result = agent.investigate(make_context())

    assert result.tool_trace == [
        "list_eligible_responsible_parties",
        "search_authoritative_requirements",
    ]
    assert result.rectification_recommendation is not None
    assert result.citations == [make_citation()]


def test_fixed_agent_query_is_derived_from_task_and_ppe_not_camera_id() -> None:
    retriever = RecordingRetriever([make_citation()])
    agent = FixedInvestigationAgent(
        InvestigationTools(MemorySiteContext(), retriever)
    )

    agent.investigate(make_context())

    assert len(retriever.queries) == 1
    assert "BOARD_FASTENING" in retriever.queries[0].q
    assert "gloves" in retriever.queries[0].q
    assert "CAM-" not in retriever.queries[0].q


def test_fixed_agent_responsibility_selection_is_stable() -> None:
    agent = FixedInvestigationAgent(
        InvestigationTools(MemorySiteContext(), RecordingRetriever([make_citation()]))
    )

    first = agent.investigate(make_context())
    second = agent.investigate(make_context())

    assert first.rectification_recommendation is not None
    assert second.rectification_recommendation is not None
    assert first.rectification_recommendation.responsible_party_id == (
        second.rectification_recommendation.responsible_party_id
    )
    assert first.rectification_recommendation.responsible_party_id == (
        "team-carpentry-01"
    )


def test_fixed_agent_due_at_uses_resolver_rectification_window() -> None:
    agent = FixedInvestigationAgent(
        InvestigationTools(MemorySiteContext(), RecordingRetriever([make_citation()]))
    )

    result = agent.investigate(make_context(window=45))

    assert result.rectification_recommendation is not None
    assert result.rectification_recommendation.due_at == OCCURRED_AT + timedelta(
        minutes=45
    )


def test_fixed_agent_does_not_invent_citation_when_rag_returns_empty() -> None:
    agent = FixedInvestigationAgent(
        InvestigationTools(MemorySiteContext(), RecordingRetriever([]))
    )

    result = agent.investigate(make_context())

    assert result.citations == []


def test_fixed_agent_distinguishes_default_cam_03_and_cam_04_business_contexts() -> None:
    agent = FixedInvestigationAgent(
        InvestigationTools(MemorySiteContext(), RecordingRetriever([make_citation()]))
    )

    cam03 = agent.investigate(make_context())
    cam04 = agent.investigate(
        make_context(
            zone_id="zone-04",
            zone_name="无背心无手套2攀爬作业区",
            task="CLIMBING_WORK",
            hazards=["高处坠落", "物体打击"],
            required_ppe=[PpeType.HELMET, PpeType.GLOVES, PpeType.VEST],
            exception_note="视频中的其他穿戴不计作高可视安全背心",
        )
    )

    assert "应落实 gloves" in (cam03.recommendation or "")
    assert "应落实 gloves" in (cam04.recommendation or "")
    assert cam03.recommendation != cam04.recommendation


def fixture_investigation(camera_id: str, *, human_facts: dict | None = None):
    context = MemorySiteContext()
    candidate = build_fixture_candidate(camera_id, f"session-{camera_id.lower()}")
    if candidate is None and camera_id == "CAM-01":
        candidate = build_fixture_candidate(
            camera_id,
            f"session-{camera_id.lower()}",
            ppe_type=PpeType.HELMET,
        )
    assert candidate is not None
    snapshot = CaseSnapshot(
        case_id=f"case-{camera_id.lower()}",
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
    store = InMemoryCaseStore()
    store.create(snapshot)
    agent = FixedInvestigationAgent(
        InvestigationTools(context, RecordingRetriever([make_citation()]))
    )
    delegate = InvestigationService(
        store,
        DeterministicInvestigationResolver(context),
        agent,
    )
    return FixtureInvestigation(delegate), snapshot.case_id


def test_cam02_is_complete_from_its_frozen_permit_context() -> None:
    port, case_id = fixture_investigation("CAM-02")

    result = port.investigate(case_id)

    assert result.facts["task_code"] == "MATERIAL_CUTTING"
    assert result.applicable_task == "MATERIAL_CUTTING"
    assert PpeType.HELMET in result.required_ppe
    assert result.missing_fields == []
    assert result.conflicts == []
    assert result.recommendation
    assert result.rectification_recommendation is not None
    assert result.citations == [make_citation()]


def test_non_whitelisted_site_note_does_not_change_cam02_resolution() -> None:
    port, case_id = fixture_investigation(
        "CAM-02", human_facts={"site_note": "切割作业正在进行"}
    )

    result = port.investigate(case_id)

    assert result.missing_fields == []
    assert result.conflicts == []
    assert result.recommendation
    assert result.rectification_recommendation is not None
    assert result.citations == [make_citation()]


def test_cam03_and_cam04_keep_their_distinct_tasks() -> None:
    cam03, case03 = fixture_investigation("CAM-03")
    cam04, case04 = fixture_investigation("CAM-04")

    result03 = cam03.investigate(case03)
    result04 = cam04.investigate(case04)

    assert PpeType.GLOVES in result03.required_ppe
    assert PpeType.GLOVES in result04.required_ppe
    assert result03.applicable_task == "BOARD_FASTENING"
    assert result04.applicable_task == "CLIMBING_WORK"


def test_cam01_safe_cutting_context_remains_complete_if_a_candidate_is_supplied() -> None:
    port, case_id = fixture_investigation("CAM-01")

    result = port.investigate(case_id)

    assert result.missing_fields == []
    assert result.applicable_task == "MATERIAL_CUTTING"
    assert set(result.required_ppe) == {
        PpeType.HELMET,
        PpeType.GLOVES,
        PpeType.VEST,
    }
