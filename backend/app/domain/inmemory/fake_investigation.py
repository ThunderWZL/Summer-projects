from app.contracts import Citation, InvestigationResult
from app.domain.investigation import InvestigationPort
from app.domain.requirements_rag import RequirementQuery


class FixtureRequirementRetriever:
    """Deterministic authoritative citation source for the offline demo."""

    def search(self, query: RequirementQuery) -> list[Citation]:
        del query
        return [
            Citation(
                document_title="个体防护装备配备规范 第12部分：建筑",
                standard_no="GB 39800.12-2025",
                section="建筑作业个体防护装备配备",
                source_url=(
                    "https://openstd.samr.gov.cn/bzgk/std/newGbInfo?"
                    "hcno=225DB0D16D458885C1C984AB6AA44012"
                ),
                excerpt="应依据建筑作业危害为作业人员配备适用的个体防护装备。",
            )
        ]


class FixtureInvestigation(InvestigationPort):
    """Fixture policy layered over the real resolver/agent investigation service."""

    def __init__(self, delegate: InvestigationPort, store) -> None:
        self._delegate = delegate
        self._store = store

    def investigate(self, case_id: str) -> InvestigationResult:
        result = self._delegate.investigate(case_id)
        snapshot = self._store.get(case_id)
        if (
            snapshot is not None
            and snapshot.camera_id == "CAM-02"
            and not snapshot.human_facts.get("site_note")
        ):
            return result.model_copy(
                update={
                    "recommendation": None,
                    "rectification_recommendation": None,
                    "citations": [],
                }
            )
        return result
