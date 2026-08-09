from datetime import datetime

import pytest

from app.contracts import (
    CandidateEvidence,
    CaseSnapshot,
    CaseStatus,
    CaseTransition,
    FactsSubmissionRecord,
)
from app.domain.case_workflow import StaleCaseVersion
from app.domain.case_store import CaseQuery
from app.domain.inmemory.case_store import InMemoryCaseStore


NOW = datetime.fromisoformat("2026-08-09T10:00:00+08:00")


def make_case(
    case_id: str = "case-01",
    *,
    status: CaseStatus = CaseStatus.NEEDS_HUMAN_FACTS,
    version: int = 1,
    camera_id: str = "CAM-01",
    ppe_type: str = "helmet",
    occurred_at: str = "2026-08-07T10:31:24+08:00",
    responsible_party_id: str | None = None,
    due_at: str | None = None,
) -> CaseSnapshot:
    candidate = CandidateEvidence.model_validate(
        {
            "candidate_id": f"candidate-{case_id}",
            "session_id": "session-01",
            "camera_id": camera_id,
            "person_track_id": f"track-{case_id}",
            "ppe_type": ppe_type,
            "evidence_kind": "NEGATIVE_CLASS_DETECTION",
            "confidence": 0.91,
            "model_name": "ppe-yolo",
            "weights_sha256": "a" * 64,
            "aggregation_method": "weighted_mean",
            "aggregation_parameters": {"minimum_frames": 3},
            "occurred_at": occurred_at,
            "first_seen_ms": 1_000,
            "last_seen_ms": 2_000,
            "frames": [
                {
                    "timestamp_ms": 1_500,
                    "image_url": f"/evidence/{case_id}/key.jpg",
                    "image_width": 1920,
                    "image_height": 1080,
                    "frame_role": "REPRESENTATIVE",
                    "person_box": {
                        "x1": 10,
                        "y1": 20,
                        "x2": 110,
                        "y2": 220,
                    },
                    "observation_box": {
                        "x1": 30,
                        "y1": 20,
                        "x2": 80,
                        "y2": 60,
                    },
                    "observation_confidence": 0.93,
                }
            ],
        }
    )
    return CaseSnapshot(
        case_id=case_id,
        session_id="session-01",
        camera_id=camera_id,
        person_track_id=f"track-{case_id}",
        ppe_type=ppe_type,
        status=status,
        version=version,
        candidate=candidate,
        rectification_responsible_party_id=responsible_party_id,
        rectification_due_at=due_at,
        created_at=occurred_at,
        updated_at=occurred_at,
    )


def test_created_case_is_retrievable_without_exposing_mutable_store_state() -> None:
    store = InMemoryCaseStore()
    created = store.create(make_case())

    created.human_facts["task"] = "mutated outside store"

    stored = store.get("case-01")
    assert stored is not None
    assert stored.human_facts == {}


def test_commit_checks_version_and_appends_one_transition_atomically() -> None:
    store = InMemoryCaseStore()
    original = store.create(make_case())
    transition = CaseTransition(
        from_status=CaseStatus.NEEDS_HUMAN_FACTS,
        to_status=CaseStatus.REINVESTIGATE,
        actor_id="officer-01",
        actor_role="SITE_SAFETY_OFFICER",
        reason="补充现场事实",
        occurred_at=NOW,
    )
    changed = original.model_copy(
        update={"status": CaseStatus.REINVESTIGATE}
    )

    committed = store.commit(changed, 1, transition)

    assert (
        committed.status,
        committed.version,
        committed.updated_at,
        len(committed.transitions),
    ) == (CaseStatus.REINVESTIGATE, 2, NOW, 1)
    with pytest.raises(StaleCaseVersion, match="expected version 1, current 2"):
        store.commit(changed, 1, transition)


def test_case_can_be_found_by_candidate_without_exposing_store_state() -> None:
    store = InMemoryCaseStore()
    case = make_case()
    store.create(case)

    found = store.find_by_candidate(case.candidate.candidate_id)

    assert found is not None
    assert found.case_id == "case-01"
    found.human_facts["outside"] = True
    assert store.find_by_candidate(case.candidate.candidate_id).human_facts == {}


def test_human_submissions_are_recorded_in_creation_order_and_isolated() -> None:
    store = InMemoryCaseStore()
    first = FactsSubmissionRecord(
        submission_id="submission-01",
        case_id="case-01",
        actor_id="officer-01",
        actor_name="现场安全员",
        actor_role="SITE_SAFETY_OFFICER",
        reason="补充班组信息",
        facts={"team": "电气班组"},
        created_at="2026-08-09T09:00:00+08:00",
    )
    second = first.model_copy(
        update={
            "submission_id": "submission-02",
            "created_at": datetime.fromisoformat("2026-08-09T09:01:00+08:00"),
        }
    )

    store.add_submission(second)
    stored_first = store.add_submission(first)
    stored_first.facts["outside"] = True

    submissions = store.list_submissions("case-01")
    assert [item.submission_id for item in submissions] == [
        "submission-01",
        "submission-02",
    ]
    assert submissions[0].facts == {"team": "电气班组"}


def test_list_applies_business_filters_before_pagination() -> None:
    store = InMemoryCaseStore()
    matching = make_case(
        "case-match",
        status=CaseStatus.PENDING_REVIEW,
        camera_id="CAM-02",
        ppe_type="goggles",
        occurred_at="2026-08-07T10:00:00+08:00",
        responsible_party_id="team-electric-01",
        due_at="2026-08-08T18:00:00+08:00",
    )
    for case in (
        matching,
        make_case(
            "case-wrong-status",
            status=CaseStatus.CLOSED,
            camera_id="CAM-02",
            ppe_type="goggles",
            occurred_at="2026-08-07T11:00:00+08:00",
            responsible_party_id="team-electric-01",
            due_at="2026-08-08T18:00:00+08:00",
        ),
        make_case(
            "case-not-overdue",
            status=CaseStatus.PENDING_REVIEW,
            camera_id="CAM-02",
            ppe_type="goggles",
            occurred_at="2026-08-07T12:00:00+08:00",
            responsible_party_id="team-electric-01",
            due_at="2026-08-10T18:00:00+08:00",
        ),
    ):
        store.create(case)

    page = store.list(
        CaseQuery(
            status=CaseStatus.PENDING_REVIEW,
            ppe_type=matching.ppe_type,
            camera_ids=frozenset({"CAM-02"}),
            responsible_party_id="team-electric-01",
            occurred_from=datetime.fromisoformat("2026-08-07T00:00:00+08:00"),
            occurred_to=datetime.fromisoformat("2026-08-08T00:00:00+08:00"),
            overdue_only=True,
            keyword="MATCH",
            as_of=NOW,
            page=1,
            page_size=20,
        )
    )

    assert page.total_items == 1
    assert [case.case_id for case in page.items] == ["case-match"]


def test_list_sorts_overdue_then_human_work_then_oldest_and_paginates() -> None:
    store = InMemoryCaseStore()
    for case in (
        make_case(
            "case-system",
            status=CaseStatus.INVESTIGATING,
            occurred_at="2026-08-07T08:00:00+08:00",
        ),
        make_case(
            "case-review-later",
            status=CaseStatus.PENDING_REVIEW,
            occurred_at="2026-08-07T11:00:00+08:00",
        ),
        make_case(
            "case-overdue",
            status=CaseStatus.RECTIFICATION_OPEN,
            occurred_at="2026-08-07T12:00:00+08:00",
            due_at="2026-08-08T18:00:00+08:00",
        ),
        make_case(
            "case-review-earlier",
            status=CaseStatus.PENDING_REVIEW,
            occurred_at="2026-08-07T09:00:00+08:00",
        ),
    ):
        store.create(case)

    page = store.list(CaseQuery(as_of=NOW, page=2, page_size=2))

    assert page.total_items == 4
    assert [case.case_id for case in page.items] == [
        "case-review-later",
        "case-system",
    ]
