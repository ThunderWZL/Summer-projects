from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from app.contracts import AssociationVerdict, VlmReviewResult, VlmVerdict
from app.modules.vlm_review.port import VlmRawResponse


class VlmParseError(Exception):
    """Model raw output cannot be interpreted as a structured review."""

    code = "VLM_PARSE_ERROR"

    def __init__(self, detail: str) -> None:
        super().__init__(f"VLM 输出无法解析为复核结果: {detail}")
        self.detail = detail


_REASON_OPENINGS = {
    VlmVerdict.CONFIRMED: ("确认违规：目标装备缺失；",),
    VlmVerdict.REJECTED: (
        "排除违规：目标装备已佩戴；",
        "排除违规：候选为伪影；",
    ),
    VlmVerdict.UNCERTAIN: ("无法确认：证据不足；",),
}
_MISSING_PPE_MARKERS = (
    "未佩戴",
    "未戴",
    "未穿",
    "未见",
    "缺失",
    "裸露",
    "没有佩戴",
    "未检测到",
)
_PRESENT_PPE_MARKERS = (
    "已佩戴",
    "正确佩戴",
    "佩戴正确",
    "身穿",
    "穿着",
    "戴着",
)


def parse(
    raw: VlmRawResponse,
    *,
    model_provider: str,
    model_parameters: dict[str, Any],
    reviewed_at: datetime,
) -> VlmReviewResult:
    """Strictly validate model raw output into a VlmReviewResult.

    模型身份字段（model_name/provider/parameters）一律取自请求上下文，
    绝不信任模型自由文本里的自报值；content 必须是合法 JSON 对象，
    且不能包含契约之外的字段。任何一步失败都抛 VlmParseError，
    由调用方按技术失败重试，禁止脏文本进入状态机。
    """
    try:
        payload = json.loads(raw.content)
    except json.JSONDecodeError as exc:
        raise VlmParseError(f"content 不是合法 JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise VlmParseError("content 必须是 JSON 对象")

    try:
        review = VlmReviewResult.model_validate(
            {
                **payload,
                "model_name": raw.model_name,
                "model_provider": model_provider,
                "model_parameters": model_parameters,
                "reviewed_at": reviewed_at,
            }
        )
    except ValidationError as exc:
        raise VlmParseError(str(exc)) from exc

    # 契约约定播放位置为非负整数毫秒；冻结契约未对 evidence_timestamps_ms
    # 加 ge=0 约束，这里由解析层兜底，防止负数进入状态机。
    if any(timestamp_ms < 0 for timestamp_ms in review.evidence_timestamps_ms):
        raise VlmParseError("evidence_timestamps_ms 必须是非负整数毫秒")

    _validate_semantics(review)

    return review


def _validate_semantics(review: VlmReviewResult) -> None:
    reason = review.reason.strip()
    expected_openings = _REASON_OPENINGS[review.verdict]
    if not reason.startswith(expected_openings):
        expected = " 或 ".join(f"“{opening}”" for opening in expected_openings)
        raise VlmParseError(
            "结论与理由语义不一致："
            f"{review.verdict.value} 的 reason 必须以{expected}开头"
        )
    reason_detail = reason.split("；", maxsplit=1)[1]

    if review.verdict is VlmVerdict.CONFIRMED:
        decisive_violation = (
            review.association is AssociationVerdict.MATCHED
            and review.body_part_visible
            and review.persistent
            and not review.poster_or_reflection
            and review.evidence_sufficient
        )
        if not decisive_violation:
            raise VlmParseError(
                "CONFIRMED 必须表示同一人员、目标部位可见、缺失持续、"
                "已排除伪影且证据充分"
            )
        if any(marker in reason_detail for marker in _PRESENT_PPE_MARKERS):
            raise VlmParseError(
                "CONFIRMED 的理由正文不能描述目标装备已经佩戴"
            )
    elif review.verdict is VlmVerdict.REJECTED:
        if review.association is not AssociationVerdict.MATCHED:
            raise VlmParseError(
                "REJECTED 必须确认关联对象为同一人员（MATCHED）；"
                "人员关联不明确应使用 UNCERTAIN"
            )
        if not review.evidence_sufficient:
            raise VlmParseError(
                "REJECTED 必须有充分证据排除违规；证据不足应使用 UNCERTAIN"
            )
        if any(marker in reason_detail for marker in _MISSING_PPE_MARKERS):
            raise VlmParseError(
                "REJECTED 的理由正文不能描述目标装备缺失或人员未佩戴"
            )
    elif review.evidence_sufficient:
        raise VlmParseError("UNCERTAIN 必须表示证据不足")
