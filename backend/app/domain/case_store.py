from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.contracts import (
    CaseSnapshot,
    CaseStatus,
    CaseTransition,
    HumanSubmissionRecord,
    PpeType,
)


@dataclass(frozen=True, slots=True)
class CaseQuery:
    status: CaseStatus | None = None
    ppe_type: PpeType | None = None
    camera_ids: frozenset[str] | None = None
    responsible_party_id: str | None = None
    occurred_from: datetime | None = None
    occurred_to: datetime | None = None
    overdue_only: bool = False
    keyword: str | None = None
    as_of: datetime | None = None
    page: int = 1
    page_size: int = 20


@dataclass(frozen=True, slots=True)
class CasePage:
    items: tuple[CaseSnapshot, ...]
    total_items: int


class CaseStorePort(Protocol):
    def create(self, snapshot: CaseSnapshot) -> CaseSnapshot: ...

    def get(self, case_id: str) -> CaseSnapshot | None: ...

    def commit(
        self,
        snapshot: CaseSnapshot,
        expected_version: int,
        transition: CaseTransition,
    ) -> CaseSnapshot: ...

    def list(self, query: CaseQuery) -> CasePage: ...

    def find_by_candidate(self, candidate_id: str) -> CaseSnapshot | None: ...

    def add_submission(
        self, submission: HumanSubmissionRecord
    ) -> HumanSubmissionRecord: ...

    def list_submissions(self, case_id: str) -> list[HumanSubmissionRecord]: ...
