from app.contracts import CandidateEvidence, CaseSnapshot, CaseStatus
from app.domain.case_store import CaseStorePort
from app.domain.case_workflow import (
    CaseNotFound,
    CaseWorkflow,
    RecordInvestigation,
    RestartInvestigation,
    StartInvestigation,
)
from app.domain.investigation import InvestigationPort
from app.modules.vlm_review.service import VlmReviewService


class CasePipeline:
    def __init__(
        self,
        store: CaseStorePort,
        workflow: CaseWorkflow,
        vlm: VlmReviewService,
        investigation: InvestigationPort,
    ) -> None:
        self._store = store
        self._workflow = workflow
        self._vlm = vlm
        self._investigation = investigation

    def ensure_case(self, candidate: CandidateEvidence) -> CaseSnapshot:
        existing = self._store.find_by_candidate(candidate.candidate_id)
        if existing is not None:
            return existing
        snapshot = CaseSnapshot(
            case_id=f"case-{candidate.candidate_id}",
            session_id=candidate.session_id,
            camera_id=candidate.camera_id,
            person_track_id=candidate.person_track_id,
            ppe_type=candidate.ppe_type,
            status=CaseStatus.YOLO_CANDIDATE,
            version=1,
            candidate=candidate,
            created_at=candidate.occurred_at,
            updated_at=candidate.occurred_at,
        )
        return self._store.create(snapshot)

    async def process_candidate(self, candidate: CandidateEvidence) -> CaseSnapshot:
        snapshot = self.ensure_case(candidate)
        if snapshot.status is CaseStatus.YOLO_CANDIDATE:
            await self._vlm.review_candidate(candidate.candidate_id)
            refreshed = self._store.get(snapshot.case_id)
            if refreshed is None:
                raise CaseNotFound(snapshot.case_id)
            snapshot = refreshed
        if snapshot.status is CaseStatus.VLM_REJECTED:
            return snapshot
        if snapshot.status is CaseStatus.VLM_REVIEWED:
            snapshot = self._workflow.apply(snapshot.case_id, StartInvestigation(snapshot.version))
        if snapshot.status is CaseStatus.INVESTIGATING:
            result = self._investigation.investigate(snapshot.case_id)
            snapshot = self._workflow.apply(
                snapshot.case_id,
                RecordInvestigation(snapshot.version, result),
            )
        return snapshot

    def resume_investigation(self, case_id: str) -> CaseSnapshot:
        snapshot = self._store.get(case_id)
        if snapshot is None:
            raise CaseNotFound(case_id)
        snapshot = self._workflow.apply(
            case_id,
            RestartInvestigation(snapshot.version),
        )
        result = self._investigation.investigate(case_id)
        return self._workflow.apply(
            case_id,
            RecordInvestigation(snapshot.version, result),
        )
