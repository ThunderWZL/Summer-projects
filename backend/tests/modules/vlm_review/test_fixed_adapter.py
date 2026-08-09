import asyncio
import json

from app.contracts import CandidateEvidence
from app.modules.vlm_review.adapters.fixed import FixedVlmAdapter, FixedVlmScenario
from app.modules.vlm_review.port import VlmRequest


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


def make_request(candidate: CandidateEvidence) -> VlmRequest:
    return VlmRequest(
        candidate=candidate,
        prompt="请判断该人员是否未佩戴安全帽",
        images=[frame.image_url for frame in candidate.frames],
    )


async def complete(candidate: CandidateEvidence, scenario: FixedVlmScenario):
    adapter = FixedVlmAdapter(scenario=scenario)
    return await adapter.complete(make_request(candidate))


def test_auto_confirms_sufficient_evidence() -> None:
    response = asyncio.run(
        complete(make_candidate(confidence=0.91), FixedVlmScenario.AUTO)
    )

    payload = json.loads(response.content)
    assert payload["verdict"] == "CONFIRMED"
    assert payload["evidence_sufficient"] is True


def test_auto_rejects_low_confidence() -> None:
    response = asyncio.run(
        complete(make_candidate(confidence=0.21), FixedVlmScenario.AUTO)
    )

    payload = json.loads(response.content)
    assert payload["verdict"] == "REJECTED"
    assert payload["evidence_sufficient"] is False


def test_auto_rejects_missing_observation() -> None:
    response = asyncio.run(
        complete(
            make_candidate(evidence_kind="MISSING_POSITIVE_ASSOCIATION"),
            FixedVlmScenario.AUTO,
        )
    )

    payload = json.loads(response.content)
    assert payload["verdict"] == "REJECTED"
    assert "证据不足" in payload["reason"]


def test_confirm_scenario_forces_confirmed() -> None:
    response = asyncio.run(
        complete(make_candidate(confidence=0.21), FixedVlmScenario.CONFIRM)
    )

    payload = json.loads(response.content)
    assert payload["verdict"] == "CONFIRMED"
    assert payload["evidence_sufficient"] is True


def test_reject_scenario_forces_rejected() -> None:
    response = asyncio.run(
        complete(make_candidate(confidence=0.91), FixedVlmScenario.REJECT)
    )

    payload = json.loads(response.content)
    assert payload["verdict"] == "REJECTED"
    assert payload["evidence_sufficient"] is False


def test_uncertain_scenario_returns_uncertain() -> None:
    response = asyncio.run(
        complete(make_candidate(confidence=0.91), FixedVlmScenario.UNCERTAIN)
    )

    payload = json.loads(response.content)
    assert payload["verdict"] == "UNCERTAIN"
    assert payload["evidence_sufficient"] is False


def test_same_candidate_always_produces_identical_output() -> None:
    adapter = FixedVlmAdapter()
    request = make_request(make_candidate(confidence=0.91))

    first = asyncio.run(adapter.complete(request))
    second = asyncio.run(adapter.complete(request))

    assert first.content == second.content
    assert first.model_name == second.model_name
