from __future__ import annotations

from datetime import datetime

from app.contracts import (
    CaseSnapshot,
    CaseStatus,
    CaseTransition,
    HumanSubmissionRecord,
)
from app.domain.case_store import CasePage, CaseQuery
from app.domain.case_workflow import StaleCaseVersion


TERMINAL_STATUSES = {
    CaseStatus.VLM_REJECTED,
    CaseStatus.HUMAN_REJECTED,
    CaseStatus.CLOSED,
}
HUMAN_ACTION_STATUSES = {
    CaseStatus.NEEDS_HUMAN_FACTS,
    CaseStatus.PENDING_REVIEW,
    CaseStatus.RECTIFICATION_OPEN,
    CaseStatus.RECHECK_PENDING,
}


class InMemoryCaseStore:
    def __init__(self) -> None:
        self._cases: dict[str, CaseSnapshot] = {}
        self._submissions: list[HumanSubmissionRecord] = []

    def create(self, snapshot: CaseSnapshot) -> CaseSnapshot:
        stored = snapshot.model_copy(deep=True)
        self._cases[snapshot.case_id] = stored
        return stored.model_copy(deep=True)

    def get(self, case_id: str) -> CaseSnapshot | None:
        snapshot = self._cases.get(case_id)
        return snapshot.model_copy(deep=True) if snapshot is not None else None

    def commit(
        self,
        snapshot: CaseSnapshot,
        expected_version: int,
        transition: CaseTransition,
        submission: HumanSubmissionRecord | None = None,
    ) -> CaseSnapshot:
        current = self._cases[snapshot.case_id]
        if current.version != expected_version:
            raise StaleCaseVersion(expected_version, current.version)
        committed = snapshot.model_copy(
            update={
                "version": current.version + 1,
                "updated_at": transition.occurred_at,
                "transitions": [*current.transitions, transition],
            },
            deep=True,
        )
        self._cases[snapshot.case_id] = committed
        if submission is not None:
            self._submissions.append(submission.model_copy(deep=True))
        return committed.model_copy(deep=True)

    def find_by_candidate(self, candidate_id: str) -> CaseSnapshot | None:
        snapshot = next(
            (
                case
                for case in self._cases.values()
                if case.candidate.candidate_id == candidate_id
            ),
            None,
        )
        return snapshot.model_copy(deep=True) if snapshot is not None else None

    def add_submission(
        self, submission: HumanSubmissionRecord
    ) -> HumanSubmissionRecord:
        stored = submission.model_copy(deep=True)
        self._submissions.append(stored)
        return stored.model_copy(deep=True)

    def list_submissions(self, case_id: str) -> list[HumanSubmissionRecord]:
        submissions = sorted(
            (
                item
                for item in self._submissions
                if item.case_id == case_id
            ),
            key=lambda item: (item.created_at, item.submission_id),
        )
        return [item.model_copy(deep=True) for item in submissions]

    def list(self, query: CaseQuery) -> CasePage:
        filtered = [
            case
            for case in self._cases.values()
            if self._matches(case, query)
        ]
        filtered.sort(
            key=lambda case: (
                not self._is_overdue(case, query.as_of),
                case.status not in HUMAN_ACTION_STATUSES,
                case.candidate.occurred_at,
                case.case_id,
            )
        )
        start = (query.page - 1) * query.page_size
        items = filtered[start : start + query.page_size]
        return CasePage(
            items=tuple(item.model_copy(deep=True) for item in items),
            total_items=len(filtered),
        )

    @staticmethod
    def _matches(case: CaseSnapshot, query: CaseQuery) -> bool:
        occurred_at = case.candidate.occurred_at
        if query.status is not None and case.status is not query.status:
            return False
        if query.ppe_type is not None and case.ppe_type is not query.ppe_type:
            return False
        if query.camera_ids is not None and case.camera_id not in query.camera_ids:
            return False
        if (
            query.responsible_party_id is not None
            and case.rectification_responsible_party_id
            != query.responsible_party_id
        ):
            return False
        if query.occurred_from is not None and occurred_at < query.occurred_from:
            return False
        if query.occurred_to is not None and occurred_at > query.occurred_to:
            return False
        if query.overdue_only and not InMemoryCaseStore._is_overdue(
            case, query.as_of
        ):
            return False
        if query.keyword:
            searchable = " ".join(
                value
                for value in (
                    case.case_id,
                    case.camera_id,
                    case.person_track_id,
                    case.rectification_responsible_party_id,
                )
                if value is not None
            ).casefold()
            if query.keyword.casefold() not in searchable:
                return False
        return True

    @staticmethod
    def _is_overdue(
        case: CaseSnapshot, as_of: datetime | None
    ) -> bool:
        return bool(
            as_of is not None
            and case.rectification_due_at is not None
            and case.rectification_due_at < as_of
            and case.status not in TERMINAL_STATUSES
        )
