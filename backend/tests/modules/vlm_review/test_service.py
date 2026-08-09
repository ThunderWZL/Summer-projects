import asyncio
from datetime import datetime

import pytest

from app.contracts import (
    CandidateEvidence,
    CaseSnapshot,
    CaseStatus,
    CaseTransition,
    VlmReviewResult,
    VlmVerdict,
)
from app.domain.case_workflow import CaseWorkflow
from app.modules.vlm_review.adapters.fixed import FixedVlmAdapter, FixedVlmScenario
from app.modules.vlm_review.port import VlmRawResponse
from app.modules.vlm_review.service import CandidateNotFound, VlmReviewService

NOW = datetime.fromisoformat("2026-08-07T10:35:00+08:00")


def make_candidate(
    *,
    confidence: float = 0.91,
    evidence_kind: str = "NEGATIVE_CLASS_DETECTION",
) -> CandidateEvidence:
    frame: dict = {
        "timestamp_ms": 1_500,
        "image_url": "/evidence/candidate-01/key.jpg",
        "image_width": 1920,
        "image_height": 1080,
        "frame_role": "REPRESENTATIVE",
        "person_box": {"x1": 10, "y1": 20, "x2": 110, "y2": 220},
    }
    if evidence_kind == "NEGATIVE_CLASS_DETECTION":
        frame["observation_box"] = {"x1": 30, "y1": 20, "x2": 80, "y2": 60}
        frame["observation_confidence"] = 0.93
    return CandidateEvidence.model_validate(
        {
            "candidate_id": "candidate-01",
            "session_id": "session-01",
            "camera_id": "CAM-01",
            "person_track_id": "track-17",
            "ppe_type": "helmet",
            "evidence_kind": evidence_kind,
            "confidence": confidence,
            "model_name": "ppe-yolo",
            "weights_sha256": "a" * 64,
            "aggregation_method": "weighted_mean",
            "aggregation_parameters": {"minimum_frames": 3},
            "occurred_at": "2026-08-07T10:31:24+08:00",
            "first_seen_ms": 1_000,
            "last_seen_ms": 2_000,
            "frames": [frame],
        }
    )


class MemoryCaseStore:
    def __init__(self, case: CaseSnapshot) -> None:
        self.case = case

    def get(self, case_id: str) -> CaseSnapshot | None:
        return self.case if case_id == self.case.case_id else None

    def find_by_candidate(self, candidate_id: str) -> CaseSnapshot | None:
        if candidate_id == self.case.candidate.candidate_id:
            return self.case
        return None

    def commit(
        self,
        snapshot: CaseSnapshot,
        expected_version: int,
        transition: CaseTransition,
    ) -> CaseSnapshot:
        stored = snapshot.model_copy(
            update={
                "version": expected_version + 1,
                "updated_at": transition.occurred_at,
                "transitions": [*self.case.transitions, transition],
            }
        )
        self.case = stored
        return stored


def make_service(case: CaseSnapshot, model):
    store = MemoryCaseStore(case)
    workflow = CaseWorkflow(
        store=store,
        actor_roles=lambda actor_id: None,
        clock=lambda: NOW,
    )
    service = VlmReviewService(
        store=store,
        model=model,
        workflow=workflow,
        model_provider="fixture",
        model_parameters={"temperature": 0},
        clock=lambda: NOW,
    )
    return service, store


class GarbageModel:
    async def complete(self, request) -> VlmRawResponse:
        return VlmRawResponse(
            model_name="garbage-model",
            content="完全不是 JSON 的自然语言",
            latency_ms=1,
        )


def test_confirmed_review_moves_case_to_vlm_reviewed() -> None:
    case = CaseSnapshot(
        case_id="case-01",
        session_id="session-01",
        camera_id="CAM-01",
        person_track_id="track-17",
        ppe_type="helmet",
        status=CaseStatus.YOLO_CANDIDATE,
        version=1,
        candidate=make_candidate(),
        created_at=NOW,
        updated_at=NOW,
    )
    service, store = make_service(case, FixedVlmAdapter())

    review = asyncio.run(service.review_candidate("candidate-01"))

    assert review.verdict is VlmVerdict.CONFIRMED
    assert store.case.status is CaseStatus.VLM_REVIEWED
    assert store.case.version == 2
    assert store.case.vlm_review == review
    assert store.case.transitions[-1].to_status is CaseStatus.VLM_REVIEWED


def test_insufficient_evidence_moves_case_to_vlm_rejected() -> None:
    case = CaseSnapshot(
        case_id="case-01",
        session_id="session-01",
        camera_id="CAM-01",
        person_track_id="track-17",
        ppe_type="helmet",
        status=CaseStatus.YOLO_CANDIDATE,
        version=1,
        candidate=make_candidate(evidence_kind="MISSING_POSITIVE_ASSOCIATION"),
        created_at=NOW,
        updated_at=NOW,
    )
    service, store = make_service(case, FixedVlmAdapter())

    review = asyncio.run(service.review_candidate("candidate-01"))

    assert review.verdict is VlmVerdict.REJECTED
    assert store.case.status is CaseStatus.VLM_REJECTED


def test_unparseable_output_becomes_uncertain_rejected() -> None:
    case = CaseSnapshot(
        case_id="case-01",
        session_id="session-01",
        camera_id="CAM-01",
        person_track_id="track-17",
        ppe_type="helmet",
        status=CaseStatus.YOLO_CANDIDATE,
        version=1,
        candidate=make_candidate(),
        created_at=NOW,
        updated_at=NOW,
    )
    service, store = make_service(case, GarbageModel())

    review = asyncio.run(service.review_candidate("candidate-01"))

    assert review.verdict is VlmVerdict.UNCERTAIN
    assert store.case.status is CaseStatus.VLM_REJECTED
    assert store.case.vlm_review.verdict is VlmVerdict.UNCERTAIN


def test_swapping_adapter_changes_outcome_without_service_change() -> None:
    case = CaseSnapshot(
        case_id="case-01",
        session_id="session-01",
        camera_id="CAM-01",
        person_track_id="track-17",
        ppe_type="helmet",
        status=CaseStatus.YOLO_CANDIDATE,
        version=1,
        candidate=make_candidate(confidence=0.21),
        created_at=NOW,
        updated_at=NOW,
    )
    confirm_service, _ = make_service(
        case, FixedVlmAdapter(scenario=FixedVlmScenario.CONFIRM)
    )
    confirm_review = asyncio.run(
        confirm_service.review_candidate("candidate-01")
    )
    assert confirm_review.verdict is VlmVerdict.CONFIRMED

    reject_service, reject_store = make_service(
        case, FixedVlmAdapter(scenario=FixedVlmScenario.REJECT)
    )
    reject_review = asyncio.run(reject_service.review_candidate("candidate-01"))
    assert reject_review.verdict is VlmVerdict.REJECTED
    assert reject_store.case.status is CaseStatus.VLM_REJECTED


def test_unknown_candidate_raises_domain_error() -> None:
    case = CaseSnapshot(
        case_id="case-01",
        session_id="session-01",
        camera_id="CAM-01",
        person_track_id="track-17",
        ppe_type="helmet",
        status=CaseStatus.YOLO_CANDIDATE,
        version=1,
        candidate=make_candidate(),
        created_at=NOW,
        updated_at=NOW,
    )
    service, _ = make_service(case, FixedVlmAdapter())

    with pytest.raises(CandidateNotFound, match="candidate-missing"):
        asyncio.run(service.review_candidate("candidate-missing"))
