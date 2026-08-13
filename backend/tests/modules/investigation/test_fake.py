from __future__ import annotations

from datetime import datetime, timedelta

from app.contracts import Citation, PpeType
from app.domain.inmemory.site_context import MemorySiteContext
from app.domain.requirements_rag import RequirementQuery
from app.modules.investigation.agent import AgentInvestigationContext
from app.modules.investigation.fake import FixedInvestigationAgent
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
        excerpt="钢筋搬运应根据风险配备手部防护。",
    )


def make_context(
    *,
    zone_id: str = "zone-03",
    zone_name: str = "钢筋区",
    task: str = "HANDLING_REBAR",
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
        hazards=hazards if hazards is not None else ["手部伤害风险"],
        required_ppe=(
            required_ppe if required_ppe is not None else [PpeType.GLOVES]
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
    assert "HANDLING_REBAR" in retriever.queries[0].q
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
        "team-structure-01"
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
            zone_name="旋转设备区",
            task="ROTATING_EQUIPMENT_OPERATION",
            hazards=["卷入风险"],
            required_ppe=[PpeType.HELMET],
            exception_note="旋转设备旁不宜简单要求佩戴手套",
            window=60,
        )
    )

    assert "应落实 gloves" in (cam03.recommendation or "")
    assert "gloves 不属于适用" in (cam04.recommendation or "")
    assert cam03.recommendation != cam04.recommendation
