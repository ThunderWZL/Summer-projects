from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.contracts import Citation
from app.domain.requirements_rag import RequirementQuery, RequirementRetrieverPort
from app.domain.site_context import ResponsibleParty, SiteContextPort


class InvestigationToolModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EligibleResponsiblePartiesInput(InvestigationToolModel):
    zone_id: str = Field(min_length=1)


class EligibleResponsiblePartiesOutput(InvestigationToolModel):
    parties: list[ResponsibleParty]


class AuthoritativeRequirementsInput(InvestigationToolModel):
    q: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)


class AuthoritativeRequirementsOutput(InvestigationToolModel):
    citations: list[Citation]


class InvestigationTools:
    """The only two side-effect-free tools available to the investigation agent."""

    def __init__(
        self,
        site_context: SiteContextPort,
        requirement_retriever: RequirementRetrieverPort,
    ) -> None:
        self._site_context = site_context
        self._requirement_retriever = requirement_retriever

    def list_eligible_responsible_parties(
        self, payload: EligibleResponsiblePartiesInput
    ) -> EligibleResponsiblePartiesOutput:
        parties = self._site_context.list_eligible_responsible_parties(payload.zone_id)
        return EligibleResponsiblePartiesOutput(
            parties=sorted(parties, key=lambda party: party.party_id)
        )

    def search_authoritative_requirements(
        self, payload: AuthoritativeRequirementsInput
    ) -> AuthoritativeRequirementsOutput:
        return AuthoritativeRequirementsOutput(
            citations=self._requirement_retriever.search(
                RequirementQuery(q=payload.q, top_k=payload.top_k)
            )
        )
