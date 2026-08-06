from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.contracts import CandidateEvidence


class VlmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate: CandidateEvidence
    prompt: str
    images: list[str] = Field(min_length=1)


class VlmRawResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_name: str
    content: str
    latency_ms: int = Field(ge=0)


class VlmModelPort(Protocol):
    async def complete(self, request: VlmRequest) -> VlmRawResponse: ...
