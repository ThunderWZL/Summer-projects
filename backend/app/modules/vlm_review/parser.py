from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from app.contracts import VlmReviewResult
from app.modules.vlm_review.port import VlmRawResponse


class VlmParseError(Exception):
    """Model raw output cannot be interpreted as a structured review."""

    code = "VLM_PARSE_ERROR"

    def __init__(self, detail: str) -> None:
        super().__init__(f"VLM 输出无法解析为复核结果: {detail}")
        self.detail = detail


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

    return review
