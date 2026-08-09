"""Public contracts for authoritative requirements retrieval.

The domain module intentionally knows nothing about Chroma, HTTP clients, or
filesystem layouts.  Adapters may implement these protocols while callers
only exchange validated Pydantic values.
"""

from __future__ import annotations

from datetime import date
from typing import Protocol, Sequence, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, StrictStr

from app.contracts import Citation


class RequirementsModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class RequirementQuery(RequirementsModel):
    q: StrictStr = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)
    as_of: date | None = None


class RequirementChunk(RequirementsModel):
    """A reproducible, traceable piece of an authoritative document."""

    chunk_id: StrictStr = Field(min_length=1)
    document_id: StrictStr = Field(min_length=1)
    title: StrictStr = Field(min_length=1)
    standard_no: StrictStr | None = None
    clause: StrictStr = Field(min_length=1)
    page: int = Field(ge=1)
    source_url: StrictStr = Field(min_length=1)
    effective_date: date | None = None
    content_hash: StrictStr = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    content: StrictStr = Field(min_length=1)


class IndexMetadata(RequirementsModel):
    embedding_model: StrictStr = Field(min_length=1)
    vector_dimension: int = Field(gt=0)
    manifest_fingerprint: StrictStr = Field(
        min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"
    )


class IndexReport(RequirementsModel):
    indexed_chunks: int = Field(ge=0)
    skipped_duplicates: int = Field(ge=0)
    rebuilt: bool
    manifest_fingerprint: StrictStr = Field(
        min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"
    )
    embedding_model: StrictStr = Field(min_length=1)
    vector_dimension: int = Field(gt=0)


class RequirementManifestEntry(RequirementsModel):
    document_id: StrictStr = Field(min_length=1)
    title: StrictStr = Field(min_length=1)
    standard_no: StrictStr | None = None
    publisher: StrictStr = Field(min_length=1)
    source_url: StrictStr = Field(min_length=1)
    publication_date: date | None = None
    effective_date: date | None = None
    status: StrictStr = Field(min_length=1)
    hash_strategy: StrictStr = Field(min_length=1)
    local_path: StrictStr | None = None


class RequirementDocument(RequirementsModel):
    document_id: StrictStr = Field(min_length=1)
    title: StrictStr = Field(min_length=1)
    standard_no: StrictStr | None = None
    source_url: StrictStr = Field(min_length=1)
    effective_date: date | None = None
    pages: list[tuple[int, str]] = Field(min_length=1)
    extraction_status: StrictStr = "ready"
    source_pdf_sha256: StrictStr | None = None
    parser_version: StrictStr | None = None
    derived_text_sha256: StrictStr | None = None
    human_review_status: StrictStr | None = None


@runtime_checkable
class RequirementRetrieverPort(Protocol):
    def search(self, query: RequirementQuery) -> list[Citation]:
        """Return only citations whose source metadata came from indexed chunks."""


@runtime_checkable
class IndexerPort(Protocol):
    def index(
        self,
        chunks: Sequence[RequirementChunk],
        *,
        manifest_fingerprint: str,
    ) -> IndexReport:
        """Idempotently index chunks, rebuilding on embedding metadata changes."""
