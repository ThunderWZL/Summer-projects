from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from app.contracts import (
    AssociationVerdict,
    CaseSnapshot,
    VlmReviewResult,
    VlmVerdict,
)
from app.domain.case_workflow import CaseWorkflow, CaseStorePort, RecordVlmReview
from app.modules.vlm_review.parser import VlmParseError, parse
from app.modules.vlm_review.port import VlmModelPort, VlmRequest, VlmRawResponse


class CandidateNotFound(Exception):
    code = "CANDIDATE_NOT_FOUND"

    def __init__(self, candidate_id: str) -> None:
        super().__init__(f"candidate {candidate_id} has no case yet")
        self.candidate_id = candidate_id


class VlmReviewService:
    """把“候选 → 模型复核 → 解析 → 状态机”串起来。

    只依赖 VlmModelPort 协议，换真实模型时替换 model 即可，
    service 与状态机一行不改。解析失败统一落成“不确定”复核，
    走状态机的 VLM_REJECTED，不让脏输出进入事件状态。
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
    ) -> None:
        self._store = store
        self._model = model
        self._workflow = workflow
        self._model_provider = model_provider
        self._model_parameters = model_parameters
        self._clock = clock

    async def review_candidate(self, candidate_id: str) -> VlmReviewResult:
        case = self._store.find_by_candidate(candidate_id)
        if case is None:
            raise CandidateNotFound(candidate_id)
        raw = await self._model.complete(self._build_request(case))
        try:
            review = parse(
                raw,
                model_provider=self._model_provider,
                model_parameters=self._model_parameters,
                reviewed_at=self._clock(),
            )
        except VlmParseError:
            review = self._uncertain_review(raw, case)
        self._workflow.apply(case.case_id, RecordVlmReview(case.version, review))
        return review

    def _build_request(self, case: CaseSnapshot) -> VlmRequest:
        return VlmRequest(
            candidate=case.candidate,
            prompt=self._PROMPT,
            images=[frame.image_url for frame in case.candidate.frames],
        )

    def _uncertain_review(
        self, raw: VlmRawResponse, case: CaseSnapshot
    ) -> VlmReviewResult:
        return VlmReviewResult(
            candidate_id=case.candidate.candidate_id,
            verdict=VlmVerdict.UNCERTAIN,
            person_track_id=case.candidate.person_track_id,
            ppe_type=case.candidate.ppe_type,
            association=AssociationVerdict.AMBIGUOUS,
            body_part_visible=False,
            persistent=False,
            poster_or_reflection=False,
            evidence_sufficient=False,
            evidence_timestamps_ms=[],
            reason="模型输出无法解析，按不确定处理",
            model_name=raw.model_name,
            model_provider=self._model_provider,
            model_parameters=self._model_parameters,
            reviewed_at=self._clock(),
        )
