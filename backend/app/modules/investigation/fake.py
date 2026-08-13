from __future__ import annotations

from datetime import timedelta

from app.contracts import RectificationRecommendation
from app.modules.investigation.agent import (
    AgentInvestigationContext,
    AgentRunResult,
    InvestigationAgentPort,
)
from app.modules.investigation.tools import (
    AuthoritativeRequirementsInput,
    EligibleResponsiblePartiesInput,
    InvestigationTools,
)


class FixedInvestigationAgent(InvestigationAgentPort):
    """Offline deterministic agent which still exercises the two controlled tools."""

    def __init__(self, tools: InvestigationTools) -> None:
        self._tools = tools

    def investigate(self, context: AgentInvestigationContext) -> AgentRunResult:
        trace: list[str] = []
        parties = self._tools.list_eligible_responsible_parties(
            EligibleResponsiblePartiesInput(zone_id=context.zone_id)
        ).parties
        trace.append("list_eligible_responsible_parties")
        query = f"{context.applicable_task} 作业 {context.ppe_type.value} 个体防护装备要求"
        citations = self._tools.search_authoritative_requirements(
            AuthoritativeRequirementsInput(q=query)
        ).citations
        trace.append("search_authoritative_requirements")
        applicable = context.ppe_type in context.required_ppe
        recommendation = (
            f"{context.applicable_task} 作业应落实 {context.ppe_type.value} 个体防护装备"
            if applicable
            else f"{context.applicable_task} 作业中 {context.ppe_type.value} 不属于适用个体防护装备"
        )
        if context.exception_note:
            recommendation = f"{recommendation}；{context.exception_note}"
        rectification = None
        if parties:
            rectification = RectificationRecommendation(
                responsible_party_id=parties[0].party_id,
                due_at=context.occurred_at
                + timedelta(minutes=context.rectification_window_minutes),
                reason=recommendation,
            )
        return AgentRunResult(
            recommendation=recommendation,
            rectification_recommendation=rectification,
            citations=list(citations),
            tool_trace=trace,
        )
