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
        "reason": "确认违规：目标装备缺失；头部持续可见且未检测到安全帽",
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


def test_negative_evidence_timestamps_are_rejected() -> None:
    payload = {**valid_content(), "evidence_timestamps_ms": [-1, 100]}
    raw = make_raw(json.dumps(payload))

    with pytest.raises(VlmParseError):
        parse(
            raw,
            model_provider="fixture",
            model_parameters={},
            reviewed_at=REVIEWED_AT,
        )


def test_semantically_conflicting_rejected_review_is_rejected() -> None:
    payload = {
        **valid_content(),
        "verdict": "REJECTED",
        "association": "AMBIGUOUS",
        "reason": (
            "候选框主要覆盖人员腰部工具带区域，未包含手部。"
            "观察帧中人员双手裸露，未见手套，判定为缺失手套，"
            "故拒绝该PPE佩戴关联。"
        ),
    }
    raw = make_raw(json.dumps(payload, ensure_ascii=False))

    with pytest.raises(VlmParseError, match="结论与理由语义不一致"):
        parse(
            raw,
            model_provider="openai_compat",
            model_parameters={"temperature": 0},
            reviewed_at=REVIEWED_AT,
        )


def test_rejected_review_accepts_explicit_exclusion_semantics() -> None:
    payload = {
        **valid_content(),
        "verdict": "REJECTED",
        "evidence_sufficient": True,
        "reason": "排除违规：目标装备已佩戴；人员已正确佩戴安全帽",
    }

    review = parse(
        make_raw(json.dumps(payload, ensure_ascii=False)),
        model_provider="openai_compat",
        model_parameters={"temperature": 0},
        reviewed_at=REVIEWED_AT,
    )

    assert review.verdict is VlmVerdict.REJECTED


def test_rejected_review_cannot_use_ambiguous_person_association() -> None:
    payload = {
        **valid_content(),
        "verdict": "REJECTED",
        "association": "AMBIGUOUS",
        "evidence_sufficient": True,
        "reason": "排除违规：目标装备已佩戴；人员已正确佩戴安全帽",
    }

    with pytest.raises(VlmParseError, match="REJECTED.*MATCHED"):
        parse(
            make_raw(json.dumps(payload, ensure_ascii=False)),
            model_provider="openai_compat",
            model_parameters={},
            reviewed_at=REVIEWED_AT,
        )


def test_rejected_review_cannot_describe_missing_ppe_after_valid_prefix() -> None:
    payload = {
        **valid_content(),
        "verdict": "REJECTED",
        "evidence_sufficient": True,
        "reason": "排除违规：候选人员双手裸露，未佩戴手套。",
    }

    with pytest.raises(VlmParseError, match="REJECTED.*目标装备已佩戴"):
        parse(
            make_raw(json.dumps(payload, ensure_ascii=False)),
            model_provider="openai_compat",
            model_parameters={},
            reviewed_at=REVIEWED_AT,
        )


def test_rejected_review_rejects_missing_ppe_in_reason_detail() -> None:
    payload = {
        **valid_content(),
        "verdict": "REJECTED",
        "evidence_sufficient": True,
        "reason": (
            "排除违规：目标装备已佩戴；"
            "候选人员双手裸露，实际未佩戴手套。"
        ),
    }

    with pytest.raises(VlmParseError, match="REJECTED.*理由正文"):
        parse(
            make_raw(json.dumps(payload, ensure_ascii=False)),
            model_provider="openai_compat",
            model_parameters={},
            reviewed_at=REVIEWED_AT,
        )


def test_confirmed_review_rejects_worn_ppe_in_reason_detail() -> None:
    payload = {
        **valid_content(),
        "reason": (
            "确认违规：目标装备缺失；"
            "候选人员身穿高可视度反光背心。"
        ),
    }

    with pytest.raises(VlmParseError, match="CONFIRMED.*理由正文"):
        parse(
            make_raw(json.dumps(payload, ensure_ascii=False)),
            model_provider="openai_compat",
            model_parameters={},
            reviewed_at=REVIEWED_AT,
        )


def test_confirmed_review_requires_decisive_evidence_flags() -> None:
    payload = {
        **valid_content(),
        "evidence_sufficient": False,
    }

    with pytest.raises(VlmParseError, match="CONFIRMED"):
        parse(
            make_raw(json.dumps(payload, ensure_ascii=False)),
            model_provider="openai_compat",
            model_parameters={},
            reviewed_at=REVIEWED_AT,
        )


def test_uncertain_review_requires_insufficient_evidence() -> None:
    payload = {
        **valid_content(),
        "verdict": "UNCERTAIN",
        "association": "AMBIGUOUS",
        "reason": "无法确认：证据不足；手部受到遮挡",
    }

    with pytest.raises(VlmParseError, match="UNCERTAIN"):
        parse(
            make_raw(json.dumps(payload, ensure_ascii=False)),
            model_provider="openai_compat",
            model_parameters={},
            reviewed_at=REVIEWED_AT,
        )
