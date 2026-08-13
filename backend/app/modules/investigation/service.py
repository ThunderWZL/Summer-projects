from __future__ import annotations

from app.contracts import InvestigationResult
from app.domain.case_store import CaseStorePort
from app.domain.investigation import InvestigationCaseNotFound, InvestigationPort
from app.domain.resolver import InvestigationResolverPort
from app.modules.investigation.agent import (
    AgentInvestigationContext,
    InvestigationAgentPort,
)


class InvestigationService(InvestigationPort):
    def __init__(
        self,
        store: CaseStorePort,
        resolver: InvestigationResolverPort,
        agent: InvestigationAgentPort,
    ) -> None:
        self._store = store
        self._resolver = resolver
        self._agent = agent

    def investigate(self, case_id: str) -> InvestigationResult:
        snapshot = self._store.get(case_id)
        if snapshot is None:
            raise InvestigationCaseNotFound(case_id)
        resolved = self._resolver.resolve(snapshot.candidate, snapshot.human_facts)
        if (
            resolved.missing_fields
            or resolved.conflicts
            or resolved.applicable_task is None
            or resolved.rectification_window_minutes is None
            or resolved.zone_id is None
            or resolved.zone_name is None
        ):
            return InvestigationResult.model_validate(
                {
                    "facts": resolved.facts,
                    "conflicts": resolved.conflicts,
                    "missing_fields": resolved.missing_fields,
                    "applicable_task": resolved.applicable_task,
                    "hazards": resolved.hazards,
                    "required_ppe": resolved.required_ppe,
                    "recommendation": None,
                    "rectification_recommendation": None,
                    "citations": [],
                    "tool_trace": [],
                }
            )
        result = self._agent.investigate(
            AgentInvestigationContext(
                case_id=snapshot.case_id,
                zone_id=resolved.zone_id,
                zone_name=resolved.zone_name,
                occurred_at=snapshot.candidate.occurred_at,
                ppe_type=snapshot.ppe_type,
                applicable_task=resolved.applicable_task,
                hazards=list(resolved.hazards),
                required_ppe=list(resolved.required_ppe),
                exception_note=resolved.exception_note,
                rectification_window_minutes=resolved.rectification_window_minutes,
            )
        )
        return InvestigationResult.model_validate(
            {
                "facts": resolved.facts,
                "conflicts": resolved.conflicts,
                "missing_fields": resolved.missing_fields,
                "applicable_task": resolved.applicable_task,
                "hazards": resolved.hazards,
                "required_ppe": resolved.required_ppe,
                "recommendation": result.recommendation,
                "rectification_recommendation": result.rectification_recommendation,
                "citations": result.citations,
                "tool_trace": result.tool_trace,
            }
        )
