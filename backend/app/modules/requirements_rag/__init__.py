"""Adapters and services for authoritative requirements retrieval."""

from app.modules.requirements_rag.chunker import RequirementChunker
from app.modules.requirements_rag.manifest import AUTHORITATIVE_SOURCES

__all__ = ["AUTHORITATIVE_SOURCES", "RequirementChunker"]
