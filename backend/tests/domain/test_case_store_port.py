from datetime import datetime
from inspect import signature
from typing import get_type_hints

from app.contracts import (
    CaseSnapshot,
    CaseStatus,
    CaseTransition,
    HumanSubmissionRecord,
    PpeType,
)
from app.domain.case_store import CasePage, CaseQuery, CaseStorePort


def test_case_store_port_exposes_complete_repository_contract() -> None:
    assert {
        "create",
        "get",
        "commit",
        "list",
        "find_by_candidate",
        "add_submission",
        "list_submissions",
    } <= set(CaseStorePort.__dict__)

    assert get_type_hints(CaseStorePort.create)["snapshot"] is CaseSnapshot
    assert get_type_hints(CaseStorePort.commit)["transition"] is CaseTransition
    assert get_type_hints(CaseStorePort.commit, include_extras=True)[
        "submission"
    ] == HumanSubmissionRecord | None
    assert get_type_hints(CaseStorePort.add_submission, include_extras=True)[
        "submission"
    ] == HumanSubmissionRecord
    assert signature(CaseStorePort.list).parameters["query"].annotation in {
        "CaseQuery",
        CaseQuery,
    }


def test_case_query_carries_repository_filters_and_pagination() -> None:
    occurred_from = datetime.fromisoformat("2026-08-01T00:00:00+08:00")
    occurred_to = datetime.fromisoformat("2026-08-08T00:00:00+08:00")
    as_of = datetime.fromisoformat("2026-08-09T00:00:00+08:00")

    query = CaseQuery(
        status=CaseStatus.PENDING_REVIEW,
        ppe_type=PpeType.GOGGLES,
        camera_ids=frozenset({"CAM-02"}),
        responsible_party_id="team-electric-01",
        occurred_from=occurred_from,
        occurred_to=occurred_to,
        overdue_only=True,
        keyword="case-01",
        as_of=as_of,
        page=2,
        page_size=10,
    )

    assert query.page == 2
    assert query.page_size == 10
    assert query.camera_ids == frozenset({"CAM-02"})
    assert CasePage(items=(), total_items=0).total_items == 0
