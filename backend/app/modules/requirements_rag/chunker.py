from __future__ import annotations

import hashlib
import re

from app.domain.requirements_rag import RequirementChunk, RequirementDocument


_HEADING = re.compile(r"^(?:第[^\s]{1,20}[章节条]|\d+(?:\.\d+)*\s+\S+)")


class RequirementChunker:
    """Split static source text at headings and semantic paragraphs."""

    def split(self, document: RequirementDocument) -> list[RequirementChunk]:
        seen: set[str] = set()
        chunks: list[RequirementChunk] = []
        for page, raw_text in document.pages:
            if page < 1:
                raise ValueError("page must be greater than zero")
            text = raw_text.replace("\r\n", "\n").strip()
            if not text:
                continue
            for block in re.split(r"\n\s*\n", text):
                normalized = " ".join(block.split())
                if not normalized:
                    continue
                if normalized in seen:
                    continue
                seen.add(normalized)
                first_line = normalized.split(" ", 1)[0]
                clause = first_line if _HEADING.match(block.strip()) else "正文"
                content_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
                chunk_id = hashlib.sha256(
                    f"{document.document_id}|{clause}|{page}|{content_hash}".encode("utf-8")
                ).hexdigest()[:24]
                chunks.append(
                    RequirementChunk(
                        chunk_id=chunk_id,
                        document_id=document.document_id,
                        title=document.title,
                        standard_no=document.standard_no,
                        clause=clause,
                        page=page,
                        source_url=document.source_url,
                        effective_date=document.effective_date,
                        content_hash=content_hash,
                        content=normalized,
                    )
                )
        if not chunks:
            raise ValueError("document is empty")
        return chunks
