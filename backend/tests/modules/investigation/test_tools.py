from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.contracts import Citation
from app.domain.inmemory.site_context import MemorySiteContext
from app.domain.requirements_rag import RequirementQuery
from app.domain.site_context import ResponsibleParty
from app.modules.investigation.tools import (
    AuthoritativeRequirementsInput,
    EligibleResponsiblePartiesInput,
    InvestigationTools,
)


class RecordingRetriever:
    def __init__(self, citations: list[Citation]) -> None:
        self.citations = citations
        self.queries: list[RequirementQuery] = []

    def search(self, query: RequirementQuery) -> list[Citation]:
        self.queries.append(query)
        return self.citations


class UnsortedPartyContext(MemorySiteContext):
    def list_eligible_responsible_parties(
        self, zone_id: str
    ) -> list[ResponsibleParty]:
        return [
            ResponsibleParty(
                party_id="team-z",
                name="后序班组",
                kind="班组",
                zone_id=zone_id,
            ),
            ResponsibleParty(
                party_id="team-a",
                name="前序班组",
                kind="班组",
                zone_id=zone_id,
            ),
        ]


def make_citation() -> Citation:
    return Citation(
        document_title="个体防护装备配备规范",
        standard_no="GB 39800.12-2025",
        section="手部防护",
        effective_date="2026-01-01",
        source_url="https://example.test/standard",
        excerpt="存在手部伤害风险时应配备手部防护。",
    )


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (EligibleResponsiblePartiesInput, {"zone_id": "zone-03", "extra": True}),
        (
            AuthoritativeRequirementsInput,
            {"q": "钢筋手套要求", "top_k": 2, "extra": True},
        ),
    ],
)
def test_tool_inputs_reject_extra_fields(model, payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(payload)


def test_party_tool_filters_by_zone_with_real_context() -> None:
    tools = InvestigationTools(MemorySiteContext(), RecordingRetriever([]))

    output = tools.list_eligible_responsible_parties(
        EligibleResponsiblePartiesInput(zone_id="zone-03")
    )

    assert [party.party_id for party in output.parties] == ["team-carpentry-01"]
    assert all(party.zone_id == "zone-03" for party in output.parties)


def test_party_tool_sorts_results_by_party_id() -> None:
    tools = InvestigationTools(UnsortedPartyContext(), RecordingRetriever([]))

    output = tools.list_eligible_responsible_parties(
        EligibleResponsiblePartiesInput(zone_id="zone-03")
    )

    assert [party.party_id for party in output.parties] == ["team-a", "team-z"]


def test_rag_tool_passes_q_and_top_k_in_requirement_query_and_preserves_citation() -> None:
    citation = make_citation()
    retriever = RecordingRetriever([citation])
    tools = InvestigationTools(MemorySiteContext(), retriever)

    output = tools.search_authoritative_requirements(
        AuthoritativeRequirementsInput(q="钢筋手套要求", top_k=2)
    )

    assert retriever.queries == [RequirementQuery(q="钢筋手套要求", top_k=2)]
    assert output.citations == [citation]
    assert output.citations[0].model_dump() == citation.model_dump()


def test_rag_tool_does_not_disguise_retrieval_failure() -> None:
    class FailingRetriever:
        def search(self, query: RequirementQuery) -> list[Citation]:
            raise LookupError("RAG index unavailable")

    tools = InvestigationTools(MemorySiteContext(), FailingRetriever())

    with pytest.raises(LookupError, match="RAG index unavailable"):
        tools.search_authoritative_requirements(
            AuthoritativeRequirementsInput(q="安全帽要求")
        )


def test_agent_tool_surface_exposes_only_two_read_only_capabilities() -> None:
    public_callables = {
        name
        for name in dir(InvestigationTools)
        if not name.startswith("_") and callable(getattr(InvestigationTools, name))
    }

    assert public_callables == {
        "list_eligible_responsible_parties",
        "search_authoritative_requirements",
    }
    assert not public_callables & {
        "store",
        "workflow",
        "execute",
        "run_python",
        "run_shell",
        "write_file",
    }
