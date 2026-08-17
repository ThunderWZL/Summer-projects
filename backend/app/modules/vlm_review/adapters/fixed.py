from __future__ import annotations

import json
from enum import Enum

from app.contracts import AssociationVerdict, EvidenceKind, FrameRole
from app.modules.vlm_review.port import VlmRawResponse, VlmRequest


class FixedVlmScenario(str, Enum):
    AUTO = "auto"
    CONFIRM = "confirm"
    REJECT = "reject"
    UNCERTAIN = "uncertain"


class FixedVlmAdapter:
    """确定性 VLM 适配器，用于测试与契约验证。

    AUTO 模式下按候选证据质量决定结论（confidence 过低、或代表帧缺少
    观察框 → “证据不足”不确定，否则确认）；其余场景强制返回指定结论，
    供测试精确复现 confirm / reject / uncertain 三条状态机路径。
    输出结构可被 parser 严格解析，绝不放自然语言。
    """

    def __init__(
        self,
        scenario: FixedVlmScenario = FixedVlmScenario.AUTO,
        *,
        min_confidence: float = 0.5,
        model_name: str = "fixed-reviewer",
        model_provider: str = "fixture",
    ) -> None:
        self._scenario = scenario
        self._min_confidence = min_confidence
        self._model_name = model_name
        self._model_provider = model_provider

    async def complete(self, request: VlmRequest) -> VlmRawResponse:
        payload = self._payload(request)
        return VlmRawResponse(
            model_name=self._model_name,
            content=json.dumps(payload, ensure_ascii=False),
            latency_ms=0,
        )

    def _payload(self, request: VlmRequest) -> dict:
        candidate = request.candidate
        evidence_sufficient = self._evidence_is_sufficient(candidate)

        if self._scenario is FixedVlmScenario.CONFIRM:
            verdict, association, sufficient = (
                "CONFIRMED",
                AssociationVerdict.MATCHED,
                True,
            )
            reason = "确认违规：目标装备缺失；确认未佩戴安全装备"
        elif self._scenario is FixedVlmScenario.REJECT:
            verdict, association, sufficient = (
                "REJECTED",
                AssociationVerdict.MATCHED,
                True,
            )
            reason = "排除违规：目标装备已佩戴；确认人员已正确佩戴安全装备"
        elif self._scenario is FixedVlmScenario.UNCERTAIN:
            verdict, association, sufficient = (
                "UNCERTAIN",
                AssociationVerdict.AMBIGUOUS,
                False,
            )
            reason = "无法确认：证据不足；画面无法明确判断"
        elif evidence_sufficient:
            verdict, association, sufficient = (
                "CONFIRMED",
                AssociationVerdict.MATCHED,
                True,
            )
            reason = "确认违规：目标装备缺失；确认未佩戴安全装备"
        else:
            verdict, association, sufficient = (
                "UNCERTAIN",
                AssociationVerdict.AMBIGUOUS,
                False,
            )
            reason = "无法确认：证据不足；画面信息不足"

        return {
            "candidate_id": candidate.candidate_id,
            "verdict": verdict,
            "person_track_id": candidate.person_track_id,
            "ppe_type": candidate.ppe_type.value,
            "association": association.value,
            "body_part_visible": sufficient,
            "persistent": sufficient,
            "poster_or_reflection": False,
            "evidence_sufficient": sufficient,
            "evidence_timestamps_ms": [
                frame.timestamp_ms for frame in candidate.frames
            ],
            "reason": reason,
        }

    def _evidence_is_sufficient(self, candidate) -> bool:
        if candidate.confidence < self._min_confidence:
            return False
        if candidate.evidence_kind is EvidenceKind.MISSING_POSITIVE_ASSOCIATION:
            return (
                len(candidate.frames) == 3
                and {frame.frame_role for frame in candidate.frames}
                == {FrameRole.BEFORE, FrameRole.REPRESENTATIVE, FrameRole.AFTER}
                and all(
                    frame.observation_box is None
                    and frame.observation_confidence is None
                    for frame in candidate.frames
                )
            )
        representative = next(
            frame
            for frame in candidate.frames
            if frame.frame_role is FrameRole.REPRESENTATIVE
        )
        return (
            representative.observation_box is not None
            and representative.observation_confidence is not None
        )
