from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path
from typing import Any, Protocol, Sequence

from app.domain.requirements_rag import IndexMetadata, RequirementChunk


class VectorStorePort(Protocol):
    def index(
        self,
        chunks: Sequence[RequirementChunk],
        vectors: Sequence[Sequence[float]],
        metadata: IndexMetadata,
    ) -> tuple[int, int, bool]: ...

    def search(
        self,
        vector: Sequence[float],
        top_k: int | None,
        *,
        as_of: date | None = None,
        include_background: bool = False,
    ) -> list[RequirementChunk]: ...

    def clear(self) -> None: ...

    def metadata(self) -> IndexMetadata | None: ...


class PersistentVectorStore:
    """Small JSON-backed vector store used when Chroma is unavailable."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def _read(self) -> dict[str, Any] | None:
        if not self.path.exists():
            return None
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, value: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        temporary.replace(self.path)

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()

    def metadata(self) -> IndexMetadata | None:
        current = self._read()
        if not current or not current.get("metadata"):
            return None
        return IndexMetadata.model_validate(current["metadata"])

    def index(
        self,
        chunks: Sequence[RequirementChunk],
        vectors: Sequence[Sequence[float]],
        metadata: IndexMetadata,
    ) -> tuple[int, int, bool]:
        if len(chunks) != len(vectors):
            raise ValueError("each chunk must have one embedding")
        current = self._read()
        rebuilt = False
        if current is None or current.get("metadata") != metadata.model_dump(mode="json"):
            records: dict[str, Any] = {}
            rebuilt = current is not None
        else:
            records = current.get("records", {})
        content_keys = {
            (record["chunk"]["document_id"], record["chunk"]["content_hash"])
            for record in records.values()
        }
        indexed = 0
        skipped = 0
        for chunk, vector in zip(chunks, vectors):
            if (chunk.document_id, chunk.content_hash) in content_keys:
                skipped += 1
                continue
            records[chunk.chunk_id] = {
                "chunk": chunk.model_dump(mode="json"),
                "vector": list(vector),
            }
            content_keys.add((chunk.document_id, chunk.content_hash))
            indexed += 1
        self._write({"metadata": metadata.model_dump(mode="json"), "records": records})
        return indexed, skipped, rebuilt

    def search(
        self,
        vector: Sequence[float],
        top_k: int | None,
        *,
        as_of: date | None = None,
        include_background: bool = False,
    ) -> list[RequirementChunk]:
        current = self._read()
        if not current:
            return []
        scored: list[tuple[float, str, RequirementChunk]] = []
        for chunk_id, record in current.get("records", {}).items():
            stored = record["vector"]
            if len(stored) != len(vector):
                raise ValueError("query vector dimension does not match stored index")
            norm = math.sqrt(sum(value * value for value in stored)) or 1.0
            score = sum(a * b for a, b in zip(vector, stored)) / norm
            raw_chunk = dict(record["chunk"])
            if raw_chunk.get("effective_date"):
                raw_chunk["effective_date"] = date.fromisoformat(raw_chunk["effective_date"])
            chunk = RequirementChunk.model_validate(raw_chunk)
            if as_of is not None and (
                chunk.effective_date is None or chunk.effective_date > as_of
            ):
                continue
            if not include_background and chunk.source_level == "background":
                continue
            scored.append((score, chunk_id, chunk))
        scored.sort(key=lambda item: (-item[0], item[1]))
        ordered = [chunk for _, _, chunk in scored]
        return ordered if top_k is None else ordered[:top_k]
