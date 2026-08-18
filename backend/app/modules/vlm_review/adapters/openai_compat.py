from __future__ import annotations

import base64
from io import BytesIO
import json
from pathlib import Path, PurePosixPath
from time import monotonic
from typing import Any
from urllib.parse import urlsplit

from app.modules.vlm_review.errors import VlmProcessingFailed
from app.modules.vlm_review.port import VlmRawResponse, VlmRequest


class OpenAICompatibleVlmAdapter:
    """Send local evidence frames to an OpenAI-compatible vision model."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        evidence_root: Path,
        timeout_seconds: float,
        max_frames: int,
        max_image_edge: int,
        max_output_tokens: int,
        client: Any | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("VLM_API_KEY is required for openai_compat")
        if not base_url:
            raise ValueError("VLM_API_BASE_URL is required for openai_compat")
        if not model:
            raise ValueError("VLM_MODEL is required for openai_compat")
        if timeout_seconds <= 0:
            raise ValueError("VLM_TIMEOUT_SECONDS must be positive")
        if max_frames <= 0:
            raise ValueError("VLM_MAX_FRAMES must be positive")
        if max_image_edge <= 0:
            raise ValueError("VLM_MAX_IMAGE_EDGE must be positive")
        if max_output_tokens <= 0:
            raise ValueError("VLM_MAX_OUTPUT_TOKENS must be positive")
        self._api_key = api_key
        self._base_url = base_url
        self._model = model
        self._evidence_root = evidence_root.resolve()
        self._timeout_seconds = timeout_seconds
        self._max_frames = max_frames
        self._max_image_edge = max_image_edge
        self._max_output_tokens = max_output_tokens
        self._client = client

    async def complete(self, request: VlmRequest) -> VlmRawResponse:
        content = self._build_content(request)
        started = monotonic()
        try:
            response = await self._get_client().chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": request.prompt},
                    {"role": "user", "content": content},
                ],
                temperature=0,
                max_tokens=self._max_output_tokens,
                response_format={"type": "json_object"},
                **self._provider_options(),
            )
        except VlmProcessingFailed:
            raise
        except Exception as exc:
            status_code = getattr(exc, "status_code", None)
            retryable = status_code not in {400, 401, 403, 404, 422}
            raise VlmProcessingFailed(
                "VLM API 调用失败",
                retryable=retryable,
            ) from exc

        raw_content = self._response_content(response)
        return VlmRawResponse(
            model_name=self._model,
            content=raw_content,
            latency_ms=max(0, round((monotonic() - started) * 1000)),
        )

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError as exc:
                raise VlmProcessingFailed(
                    "openai 依赖未安装，无法调用真实 VLM",
                    retryable=False,
                ) from exc
            self._client = AsyncOpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
                timeout=self._timeout_seconds,
                max_retries=0,
            )
        return self._client

    def _build_content(self, request: VlmRequest) -> list[dict[str, Any]]:
        images = request.images[: self._max_frames]
        encoded_images = [self._encode_local_image(image) for image in images]
        return [
            {
                "type": "text",
                "text": self._review_instruction(request),
            },
            *[
                {
                    "type": "image_url",
                    "image_url": {"url": data_url},
                }
                for data_url in encoded_images
            ],
        ]

    def _encode_local_image(self, image_url: str) -> str:
        parsed = urlsplit(image_url)
        if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
            raise VlmProcessingFailed(
                "VLM 证据图片地址无效",
                retryable=False,
            )
        parts = PurePosixPath(parsed.path).parts
        if len(parts) < 4 or parts[:2] != ("/", "evidence"):
            raise VlmProcessingFailed(
                "VLM 证据图片地址无效",
                retryable=False,
            )
        path = (self._evidence_root / Path(*parts[2:])).resolve()
        try:
            path.relative_to(self._evidence_root)
        except ValueError as exc:
            raise VlmProcessingFailed(
                "VLM 证据图片地址越界",
                retryable=False,
            ) from exc
        if not path.is_file():
            raise VlmProcessingFailed(
                "VLM 证据图片不存在",
                retryable=False,
            )
        image = path.read_bytes()
        if not image.startswith(b"\xff\xd8") or not image.endswith(b"\xff\xd9"):
            raise VlmProcessingFailed(
                "VLM 证据图片不是有效 JPEG",
                retryable=False,
            )
        encoded = base64.b64encode(self._prepare_image(image)).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"

    def _prepare_image(self, image: bytes) -> bytes:
        try:
            from PIL import Image
        except ImportError as exc:
            raise VlmProcessingFailed(
                "Pillow 依赖未安装，无法处理 VLM 证据图片",
                retryable=False,
            ) from exc
        try:
            with Image.open(BytesIO(image)) as source:
                source.load()
                if max(source.size) <= self._max_image_edge:
                    return image
                resized = source.convert("RGB")
                resized.thumbnail(
                    (self._max_image_edge, self._max_image_edge),
                    Image.Resampling.LANCZOS,
                )
                output = BytesIO()
                resized.save(output, format="JPEG", quality=85, optimize=True)
                return output.getvalue()
        except OSError as exc:
            raise VlmProcessingFailed(
                "VLM 证据图片无法解码",
                retryable=False,
            ) from exc

    def _review_instruction(self, request: VlmRequest) -> str:
        candidate = request.candidate
        evidence = {
            "candidate_id": candidate.candidate_id,
            "person_track_id": candidate.person_track_id,
            "ppe_type": candidate.ppe_type.value,
            "evidence_kind": candidate.evidence_kind.value,
            "confidence": candidate.confidence,
            "first_seen_ms": candidate.first_seen_ms,
            "last_seen_ms": candidate.last_seen_ms,
            "frames": [
                {
                    "timestamp_ms": frame.timestamp_ms,
                    "frame_role": frame.frame_role.value,
                    "person_box": frame.person_box.model_dump(),
                    "observation_box": (
                        frame.observation_box.model_dump()
                        if frame.observation_box is not None
                        else None
                    ),
                }
                for frame in candidate.frames[: self._max_frames]
            ],
        }
        schema = {
            "candidate_id": candidate.candidate_id,
            "verdict": "CONFIRMED | REJECTED | UNCERTAIN",
            "person_track_id": candidate.person_track_id,
            "ppe_type": candidate.ppe_type.value,
            "association": "MATCHED | AMBIGUOUS",
            "body_part_visible": True,
            "persistent": True,
            "poster_or_reflection": False,
            "evidence_sufficient": True,
            "evidence_timestamps_ms": [
                frame.timestamp_ms
                for frame in candidate.frames[: self._max_frames]
            ],
            "reason": "简短中文理由",
        }
        return (
            "候选元数据："
            + json.dumps(evidence, ensure_ascii=False)
            + "\n复核对象始终是：候选人员是否缺少目标防护装备。"
            + "目标装备判定标准："
            + "helmet 必须是正确佩戴在头部的工业安全头盔，"
            + "普通帽子、兜帽不能算作安全头盔；"
            + "gloves 只有在必须清楚看到双手均由防护手套覆盖时，"
            + "才能判定已佩戴；任何清楚可见的裸露手部都表示手套缺失；"
            + "vest 必须能看出无袖外穿背心结构，并具有独立背心边缘、"
            + "开襟或反光条等可识别特征；荧光色短袖或长袖上衣不能算作安全背心，"
            + "攀爬安全带、工具带也不能算作安全背心。"
            + "不得只凭服装颜色判断 PPE 是否存在，"
            + "不得把画面中的检测框、类别文字或颜色当作佩戴证据。"
            + "只有至少两帧清楚显示同一人员正确佩戴目标装备时，"
            + "才能使用 REJECTED；目标部位太小、模糊、被遮挡或不能跨帧确认时，"
            + "必须使用 UNCERTAIN。"
            + "CONFIRMED 表示确认候选人员缺少目标防护装备；"
            + "REJECTED 表示确认候选并非违规，例如已正确佩戴目标装备或属于伪影；"
            + "UNCERTAIN 表示遮挡、部位不可见或证据不足，无法作出结论。"
            + "association 只表示证据帧是否属于同一名候选人员，"
            + "不得用它表示防护装备是否存在；同一人员应填写 MATCHED。"
            + "person_box 是人员跟踪框，不是目标防护装备框；"
            + "即使人员框覆盖范围较大，也必须观察完整画面中的目标身体部位。"
            + "evidence_sufficient 表示证据是否足以支持当前 verdict；"
            + "证据不足时必须使用 UNCERTAIN，不能使用 REJECTED。"
            + "reason 必须采用以下精确开头之一："
            + "CONFIRMED 使用“确认违规：目标装备缺失；”；"
            + "REJECTED 使用“排除违规：目标装备已佩戴；”或"
            + "“排除违规：候选为伪影；”；"
            + "UNCERTAIN 使用“无法确认：证据不足；”。"
            + "分号后的理由正文不得反转开头结论，不得使用双重否定。"
            + "请逐帧排除海报、镜像和遮挡。"
            + "只能输出一个 JSON 对象，不得添加 Markdown 或额外字段。输出结构："
            + json.dumps(schema, ensure_ascii=False)
        )

    def _provider_options(self) -> dict[str, Any]:
        if self._model.lower().startswith("qwen"):
            return {"extra_body": {"enable_thinking": True}}
        return {}

    @staticmethod
    def _response_content(response: Any) -> str:
        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError, TypeError) as exc:
            raise VlmProcessingFailed(
                "VLM API 返回结构无效",
                retryable=True,
            ) from exc
        if not isinstance(content, str) or not content.strip():
            raise VlmProcessingFailed(
                "VLM API 未返回有效文本",
                retryable=True,
            )
        return content
