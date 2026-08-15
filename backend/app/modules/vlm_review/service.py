from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from app.contracts import (
    CaseSnapshot,
    VlmReviewResult,
)
from app.domain.case_store import CaseStorePort
from app.domain.case_workflow import CaseWorkflow, RecordVlmReview
from app.modules.vlm_review.errors import VlmProcessingFailed
from app.modules.vlm_review.parser import parse
from app.modules.vlm_review.port import VlmModelPort, VlmRequest


class CandidateNotFound(Exception):
    code = "CANDIDATE_NOT_FOUND"

    def __init__(self, candidate_id: str) -> None:
        super().__init__(f"candidate {candidate_id} has no case yet")
        self.candidate_id = candidate_id


class VlmReviewService:
    """把“候选 → 模型复核 → 解析 → 状态机”串起来。

    只依赖 VlmModelPort 协议，换真实模型时替换 model 即可，
    service 与状态机一行不改。技术失败在内部有限重试；重试耗尽
    抛 VlmProcessingFailed，不构造语义结论，也不触发状态迁移。
    """

    _PROMPT = (
        "你是施工安全 PPE 复核助手。请仔细观察证据帧，严格按 JSON 输出复核结论，"
        "字段必须与候选证据一致，不要输出任何额外解释。"
    )

    def __init__(
        self,
        store: CaseStorePort,
        model: VlmModelPort,
        workflow: CaseWorkflow,
        *,
        model_provider: str,
        model_parameters: dict[str, Any],
        clock: Callable[[], datetime],
        max_retries: int,
        retry_delay_seconds: float,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must be greater than or equal to 0")
        if retry_delay_seconds < 0:
            raise ValueError(
                "retry_delay_seconds must be greater than or equal to 0"
            )
        self._store = store
        self._model = model
        self._workflow = workflow
        self._model_provider = model_provider
        self._model_parameters = model_parameters
        self._clock = clock
        self._max_retries = max_retries
        self._retry_delay_seconds = retry_delay_seconds
        self._sleep = sleep

    async def review_candidate(self, candidate_id: str) -> VlmReviewResult:
        case = self._store.find_by_candidate(candidate_id)
        if case is None:
            raise CandidateNotFound(candidate_id)
        review = await self._complete_and_parse(self._build_request(case))
        self._workflow.apply(case.case_id, RecordVlmReview(case.version, review))
        return review

    async def _complete_and_parse(self, request: VlmRequest) -> VlmReviewResult:
        total_attempts = self._max_retries + 1
        last_failure: Exception | None = None

        for attempt in range(1, total_attempts + 1):
            try:
                raw = await self._model.complete(request)
                return parse(
                    raw,
                    model_provider=self._model_provider,
                    model_parameters=self._model_parameters,
                    reviewed_at=self._clock(),
                )
            except VlmProcessingFailed as exc:
                if not exc.retryable:
                    raise
                last_failure = exc
            except Exception as exc:
                last_failure = exc

            if attempt < total_attempts:
                await self._sleep(self._retry_delay_seconds)

        raise VlmProcessingFailed(
            "VLM 技术处理失败，重试耗尽",
            retryable=True,
            attempts=total_attempts,
        ) from last_failure

    def _build_request(self, case: CaseSnapshot) -> VlmRequest:
        return VlmRequest(
            candidate=case.candidate,
            prompt=self._PROMPT,
            images=[frame.image_url for frame in case.candidate.frames],
        )
