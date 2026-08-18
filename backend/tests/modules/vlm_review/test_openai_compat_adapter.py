from __future__ import annotations

import asyncio
import base64
from io import BytesIO
import json
from types import SimpleNamespace

import pytest
from PIL import Image

from app.contracts import CandidateEvidence
from app.modules.vlm_review.adapters.openai_compat import (
    OpenAICompatibleVlmAdapter,
)
from app.modules.vlm_review.errors import VlmProcessingFailed
from app.modules.vlm_review.port import VlmRequest


class FakeCompletions:
    def __init__(self, content: object) -> None:
        self.content = content
        self.calls: list[dict[str, object]] = []

    async def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))]
        )


class FakeClient:
    def __init__(self, content: object) -> None:
        self.completions = FakeCompletions(content)
        self.chat = SimpleNamespace(completions=self.completions)


def make_candidate() -> CandidateEvidence:
    return CandidateEvidence.model_validate(
        {
            "candidate_id": "candidate-01",
            "session_id": "session-01",
            "camera_id": "CAM-02",
            "person_track_id": "track-17",
            "ppe_type": "vest",
            "evidence_kind": "MISSING_POSITIVE_ASSOCIATION",
            "confidence": 0.91,
            "model_name": "ppe-yolo",
            "weights_sha256": "a" * 64,
            "aggregation_method": "weighted_mean",
            "aggregation_parameters": {"minimum_frames": 3},
            "occurred_at": "2026-08-17T10:31:24+08:00",
            "first_seen_ms": 1_000,
            "last_seen_ms": 2_000,
            "frames": [
                {
                    "timestamp_ms": timestamp,
                    "image_url": f"/evidence/session-01/{timestamp}.jpg",
                    "image_width": 640,
                    "image_height": 360,
                    "frame_role": role,
                    "person_box": {"x1": 10, "y1": 20, "x2": 110, "y2": 220},
                }
                for timestamp, role in (
                    (1_000, "BEFORE"),
                    (1_500, "REPRESENTATIVE"),
                    (2_000, "AFTER"),
                )
            ],
        }
    )


def make_request() -> VlmRequest:
    candidate = make_candidate()
    return VlmRequest(
        candidate=candidate,
        prompt="你是施工安全 PPE 复核助手。只输出 JSON。",
        images=[frame.image_url for frame in candidate.frames],
    )


def write_evidence_files(root, *, count: int = 3) -> None:
    session = root / "session-01"
    session.mkdir(parents=True)
    for index, timestamp in enumerate((1_000, 1_500, 2_000)[:count]):
        Image.new("RGB", (32, 24), color=(index * 50, 20, 40)).save(
            session / f"{timestamp}.jpg",
            format="JPEG",
        )


def test_complete_sends_local_evidence_as_bounded_base64_images(tmp_path) -> None:
    write_evidence_files(tmp_path)
    content = json.dumps(
        {
            "candidate_id": "candidate-01",
            "verdict": "CONFIRMED",
        }
    )
    client = FakeClient(content)
    adapter = OpenAICompatibleVlmAdapter(
        api_key="configured-secret",
        base_url="https://dashscope.example/v1",
        model="qwen3.6-27b",
        evidence_root=tmp_path,
        timeout_seconds=30,
        max_frames=2,
        max_image_edge=1280,
        max_output_tokens=512,
        client=client,
    )

    response = asyncio.run(adapter.complete(make_request()))

    assert response.model_name == "qwen3.6-27b"
    assert response.content == content
    assert response.latency_ms >= 0
    call = client.completions.calls[0]
    assert call["model"] == "qwen3.6-27b"
    assert call["response_format"] == {"type": "json_object"}
    assert call["max_tokens"] == 512
    messages = call["messages"]
    assert messages[0]["content"].endswith("只输出 JSON。")
    user_content = messages[1]["content"]
    images = [part for part in user_content if part["type"] == "image_url"]
    assert len(images) == 2
    assert all(
        part["image_url"]["url"].startswith("data:image/jpeg;base64,")
        for part in images
    )
    prompt = next(part["text"] for part in user_content if part["type"] == "text")
    assert "candidate-01" in prompt
    assert "track-17" in prompt
    assert "vest" in prompt
    assert "CONFIRMED 表示确认候选人员缺少目标防护装备" in prompt
    assert "REJECTED 表示确认候选并非违规" in prompt
    assert "association 只表示证据帧是否属于同一名候选人员" in prompt
    assert "确认违规：目标装备缺失；" in prompt
    assert "排除违规：目标装备已佩戴；" in prompt
    assert "无法确认：证据不足；" in prompt
    assert "荧光色短袖或长袖上衣不能算作安全背心" in prompt
    assert "必须清楚看到双手均由防护手套覆盖" in prompt
    assert "普通帽子、兜帽不能算作安全头盔" in prompt
    assert "不得把画面中的检测框、类别文字或颜色当作佩戴证据" in prompt


def test_missing_evidence_is_a_non_retryable_failure(tmp_path) -> None:
    client = FakeClient("{}")
    adapter = OpenAICompatibleVlmAdapter(
        api_key="configured-secret",
        base_url="https://dashscope.example/v1",
        model="qwen3.6-27b",
        evidence_root=tmp_path,
        timeout_seconds=30,
        max_frames=3,
        max_image_edge=1280,
        max_output_tokens=512,
        client=client,
    )

    with pytest.raises(VlmProcessingFailed) as exc_info:
        asyncio.run(adapter.complete(make_request()))

    assert exc_info.value.retryable is False
    assert client.completions.calls == []


def test_evidence_path_cannot_escape_the_configured_root(tmp_path) -> None:
    write_evidence_files(tmp_path)
    client = FakeClient("{}")
    adapter = OpenAICompatibleVlmAdapter(
        api_key="configured-secret",
        base_url="https://dashscope.example/v1",
        model="qwen3.6-27b",
        evidence_root=tmp_path,
        timeout_seconds=30,
        max_frames=3,
        max_image_edge=1280,
        max_output_tokens=512,
        client=client,
    )
    request = make_request().model_copy(
        update={"images": ["/evidence/../outside.jpg"]}
    )

    with pytest.raises(VlmProcessingFailed) as exc_info:
        asyncio.run(adapter.complete(request))

    assert exc_info.value.retryable is False
    assert client.completions.calls == []


@pytest.mark.parametrize("content", [None, [], {"unexpected": "shape"}])
def test_invalid_api_content_is_retryable(tmp_path, content: object) -> None:
    write_evidence_files(tmp_path)
    adapter = OpenAICompatibleVlmAdapter(
        api_key="configured-secret",
        base_url="https://dashscope.example/v1",
        model="qwen3.6-27b",
        evidence_root=tmp_path,
        timeout_seconds=30,
        max_frames=3,
        max_image_edge=1280,
        max_output_tokens=512,
        client=FakeClient(content),
    )

    with pytest.raises(VlmProcessingFailed) as exc_info:
        asyncio.run(adapter.complete(make_request()))

    assert exc_info.value.retryable is True


def test_complete_downscales_large_evidence_before_upload(tmp_path) -> None:
    write_evidence_files(tmp_path)
    Image.new("RGB", (1920, 1080), color=(80, 120, 160)).save(
        tmp_path / "session-01" / "1000.jpg",
        format="JPEG",
    )
    client = FakeClient("{}")
    adapter = OpenAICompatibleVlmAdapter(
        api_key="configured-secret",
        base_url="https://dashscope.example/v1",
        model="qwen3.6-27b",
        evidence_root=tmp_path,
        timeout_seconds=30,
        max_frames=1,
        max_image_edge=640,
        max_output_tokens=512,
        client=client,
    )

    asyncio.run(adapter.complete(make_request()))

    content = client.completions.calls[0]["messages"][1]["content"]
    data_url = next(
        part["image_url"]["url"]
        for part in content
        if part["type"] == "image_url"
    )
    encoded = data_url.removeprefix("data:image/jpeg;base64,")
    with Image.open(BytesIO(base64.b64decode(encoded))) as image:
        assert image.size == (640, 360)
