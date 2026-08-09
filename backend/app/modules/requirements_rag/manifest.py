from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr

from app.domain.requirements_rag import RequirementManifestEntry


class AuthoritativeSource(RequirementManifestEntry):
    role: StrictStr = Field(min_length=1)
    source_level: Literal["main", "supplemental", "background"]
    extraction_status: StrictStr = "not_downloaded"
    source_pdf_sha256: StrictStr | None = None
    parser_version: StrictStr | None = None
    derived_text_sha256: StrictStr | None = None
    human_review_status: StrictStr | None = None


AUTHORITATIVE_SOURCES: tuple[AuthoritativeSource, ...] = (
    AuthoritativeSource(
        document_id="gb-39800-12-2025",
        title="个体防护装备配备规范 第12部分：建筑",
        standard_no="GB 39800.12-2025",
        publisher="国家标准全文公开系统",
        source_url="https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=225DB0D16D458885C1C984AB6AA44012",
        effective_date=date(2026, 7, 1),
        status="official",
        hash_strategy="sha256-normalized-utf8-content",
        role="building_ppe",
        source_level="main",
    ),
    AuthoritativeSource(
        document_id="gb-39800-1-2020",
        title="个体防护装备配备规范 第1部分：总则",
        standard_no="GB 39800.1-2020",
        publisher="国家标准全文公开系统",
        source_url="https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=B8071B9B0A429EB6067597A7C98629C9",
        effective_date=date(2022, 1, 1),
        status="official",
        hash_strategy="sha256-normalized-utf8-content",
        role="general_ppe",
        source_level="supplemental",
    ),
    AuthoritativeSource(
        document_id="construction-worker-ppe-guide-2021",
        title="建筑工人施工现场劳动保护基本配置指南",
        publisher="中华人民共和国中央人民政府",
        source_url="https://www.gov.cn/zhengce/zhengceku/2021-01/19/5580999/files/10d98ecac8cd4c68a887b0519b56768b.pdf",
        effective_date=None,
        status="official",
        hash_strategy="sha256-normalized-utf8-content",
        role="field_reference",
        source_level="supplemental",
    ),
    AuthoritativeSource(
        document_id="gb-55034-2022",
        title="建筑与市政施工现场安全卫生与职业健康通用规范",
        standard_no="GB 55034-2022",
        publisher="国家标准全文公开系统",
        source_url="https://policy.mofcom.gov.cn/claw/clawContent.shtml?id=96208",
        effective_date=date(2023, 6, 1),
        status="official",
        hash_strategy="sha256-normalized-utf8-content",
        role="safety_general",
        source_level="supplemental",
    ),
    AuthoritativeSource(
        document_id="samr-ppe-enforcement-2025-77",
        title="市监质监发〔2025〕77号专项整治方案",
        publisher="国家市场监督管理总局",
        source_url="https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/zljds/art/2025/art_06f5f34df2f44ba9ae240f3498bc73af.html",
        effective_date=date(2025, 1, 1),
        status="official",
        hash_strategy="sha256-normalized-utf8-content",
        role="enforcement_context",
        source_level="background",
    ),
)


def manifest_fingerprint(sources: tuple[AuthoritativeSource, ...] = AUTHORITATIVE_SOURCES) -> str:
    payload = [source.model_dump(mode="json") for source in sources]
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def write_manifest(path: str | Path) -> None:
    Path(path).write_text(
        json.dumps(
            [source.model_dump(mode="json") for source in AUTHORITATIVE_SOURCES],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def load_manifest(path: str | Path) -> tuple[AuthoritativeSource, ...]:
    raw: Any = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("manifest must contain a list")
    return tuple(AuthoritativeSource.model_validate_strings(item) for item in raw)
