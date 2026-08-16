from __future__ import annotations

import hashlib
import math
from typing import Protocol, Sequence, runtime_checkable


@runtime_checkable
class EmbeddingClientPort(Protocol):
    model: str
    dimension: int

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class DeterministicEmbeddingClient:
    """Offline embedder used by tests and demos without AI optional extras."""

    def __init__(self, model: str = "fake-v1", dimension: int = 32) -> None:
        if not model:
            raise ValueError("embedding model is required")
        if dimension <= 0:
            raise ValueError("embedding dimension must be positive")
        self.model = model
        self.dimension = dimension

    def _embed(self, text: str) -> list[float]:
        values: list[float] = []
        counter = 0
        while len(values) < self.dimension:
            digest = hashlib.sha256(f"{self.model}\0{text}\0{counter}".encode("utf-8")).digest()
            for offset in range(0, len(digest), 4):
                raw = int.from_bytes(digest[offset : offset + 4], "big")
                values.append((raw / 2**32) * 2 - 1)
                if len(values) == self.dimension:
                    break
            counter += 1
        norm = math.sqrt(sum(value * value for value in values)) or 1.0
        return [value / norm for value in values]

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class OpenAIEmbeddingClient:
    """OpenAI-compatible embedding boundary; import the optional SDK lazily."""

    def __init__(self, *, api_key: str, base_url: str | None, model: str) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.dimension = 0
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise RuntimeError("openai is required for a real embedding index") from exc
            kwargs = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._client = OpenAI(**kwargs)
        return self._client

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        # DashScope 等 OpenAI 兼容端点限制单次请求 input 不超过 20 条，分批嵌入。
        batch_size = 20
        values: list[list[float]] = []
        for start in range(0, len(texts), batch_size):
            batch = list(texts[start : start + batch_size])
            response = self._get_client().embeddings.create(model=self.model, input=batch)
            values.extend(list(item.embedding) for item in response.data)
        if values:
            self.dimension = len(values[0])
        return values

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]
