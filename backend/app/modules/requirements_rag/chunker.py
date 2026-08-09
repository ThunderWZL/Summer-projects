from __future__ import annotations

import hashlib
import re

from app.domain.requirements_rag import RequirementChunk, RequirementDocument


_HEADING = re.compile(r"^(?:第[^\s]{1,20}[章节条]|\d+(?:\.\d+)*\s+\S+)")
_TABLE_ITEM = re.compile(r"^(?:第\s*\d+\s*项|\d+\s*[、.])")


class RequirementChunker:
    """Split static source text at headings and semantic paragraphs."""

    def split(self, document: RequirementDocument) -> list[RequirementChunk]:
        if document.extraction_status != "ready":
            raise ValueError(
                f"document extraction is not safe for indexing: {document.extraction_status}"
            )
        seen: set[str] = set()
        chunks: list[RequirementChunk] = []
        for page, raw_text in document.pages:
            if page < 1:
                raise ValueError("page must be greater than zero")
            text = raw_text.replace("\r\n", "\n").strip()
            if not text:
                continue
            blocks: list[str] = []
            for paragraph in re.split(r"\n\s*\n", text):
                lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
                if any(_TABLE_ITEM.match(line) for line in lines):
                    current: list[str] = []
                    for line in lines:
                        if current and _TABLE_ITEM.match(line):
                            blocks.append("\n".join(current))
                            current = []
                        current.append(line)
                    if current:
                        blocks.append("\n".join(current))
                else:
                    blocks.append(paragraph)
            for block in blocks:
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
