import json
from datetime import datetime

import pytest

from app.contracts import VlmReviewResult, VlmVerdict
from app.modules.vlm_review.parser import VlmParseError, parse
from app.modules.vlm_review.port import VlmRawResponse

REVIEWED_AT = datetime.fromisoformat("2026-08-07T10:35:00+08:00")


def valid_content() -> dict:
    return {
        "candidate_id": "candidate-01",
        "verdict": "CONFIRMED",
        "person_track_id": "track-17",
        "ppe_type": "helmet",
        "association": "MATCHED",
        "body_part_visible": True,
        "persistent": True,
        "poster_or_reflection": False,
        "evidence_sufficient": True,
        "evidence_timestamps_ms": [1_000, 1_500, 2_000],
        "reason": "头部持续可见且未检测到安全帽",
    }


def make_raw(content: str, model_name: str = "model-x") -> VlmRawResponse:
    return VlmRawResponse(model_name=model_name, content=content, latency_ms=120)


def test_parse_valid_json_into_review_result() -> None:
    raw = make_raw(json.dumps(valid_content()))

    review = parse(
        raw,
        model_provider="fixture",
        model_parameters={"temperature": 0},
        reviewed_at=REVIEWED_AT,
    )

    assert isinstance(review, VlmReviewResult)
    assert review.verdict is VlmVerdict.CONFIRMED
    assert review.evidence_sufficient is True
    assert review.model_name == "model-x"
    assert review.model_provider == "fixture"
    assert review.model_parameters == {"temperature": 0}
    assert review.reviewed_at == REVIEWED_AT


def test_model_identity_comes_from_context_not_model_text() -> None:
    payload = {**valid_content(), "model_name": "fake", "model_provider": "fake"}
    raw = make_raw(json.dumps(payload), model_name="trusted-model")

    review = parse(
        raw,
        model_provider="fixture",
        model_parameters={},
        reviewed_at=REVIEWED_AT,
    )

    assert review.model_name == "trusted-model"
    assert review.model_provider == "fixture"


def test_non_json_content_is_rejected() -> None:
    raw = make_raw("这不是 JSON")

    with pytest.raises(VlmParseError):
        parse(
            raw,
            model_provider="fixture",
            model_parameters={},
            reviewed_at=REVIEWED_AT,
        )


def test_missing_required_fields_are_rejected() -> None:
    payload = {**valid_content()}
    del payload["reason"]
    raw = make_raw(json.dumps(payload))

    with pytest.raises(VlmParseError):
        parse(
            raw,
            model_provider="fixture",
            model_parameters={},
            reviewed_at=REVIEWED_AT,
        )


def test_unknown_extra_fields_are_rejected() -> None:
    payload = {**valid_content(), "suspicious": "extra"}
    raw = make_raw(json.dumps(payload))

    with pytest.raises(VlmParseError):
        parse(
            raw,
            model_provider="fixture",
            model_parameters={},
            reviewed_at=REVIEWED_AT,
        )
