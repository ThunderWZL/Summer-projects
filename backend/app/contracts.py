from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PpeType(str, Enum):
    HELMET = "helmet"
    GOGGLES = "goggles"
    GLOVES = "gloves"
    BOOTS = "boots"
    VEST = "vest"


class BoundingBox(ContractModel):
    x1: float = Field(ge=0)
    y1: float = Field(ge=0)
    x2: float = Field(ge=0)
    y2: float = Field(ge=0)


class EvidenceFrame(ContractModel):
    timestamp_ms: int = Field(ge=0)
    image_url: str
    person_box: BoundingBox
    ppe_box: BoundingBox | None = None


class CandidateEvidence(ContractModel):
    candidate_id: str
    session_id: str
    camera_id: str
    person_track_id: str
    ppe_type: PpeType
    confidence: float = Field(ge=0, le=1)
    first_seen_ms: int = Field(ge=0)
    last_seen_ms: int = Field(ge=0)
    frames: list[EvidenceFrame] = Field(min_length=1)


class VlmVerdict(str, Enum):
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    UNCERTAIN = "UNCERTAIN"


class AssociationVerdict(str, Enum):
    MATCHED = "MATCHED"
    AMBIGUOUS = "AMBIGUOUS"


class VlmReviewResult(ContractModel):
    candidate_id: str
    verdict: VlmVerdict
    person_track_id: str
    ppe_type: PpeType
    association: AssociationVerdict
    body_part_visible: bool
    persistent: bool
    poster_or_reflection: bool
    evidence_sufficient: bool
    evidence_timestamps_ms: list[int]
    reason: str
    model_name: str


class CaseStatus(str, Enum):
    YOLO_CANDIDATE = "YOLO_CANDIDATE"
    VLM_REVIEWED = "VLM_REVIEWED"
    VLM_REJECTED = "VLM_REJECTED"
    INVESTIGATING = "INVESTIGATING"
    NEEDS_HUMAN_FACTS = "NEEDS_HUMAN_FACTS"
    REINVESTIGATE = "REINVESTIGATE"
    PENDING_REVIEW = "PENDING_REVIEW"
    HUMAN_REJECTED = "HUMAN_REJECTED"
    RECTIFICATION_OPEN = "RECTIFICATION_OPEN"
    RECHECK_PENDING = "RECHECK_PENDING"
    CLOSED = "CLOSED"


class Citation(ContractModel):
    document_title: str
    standard_no: str | None = None
    section: str
    effective_date: str | None = None
    source_url: str
    excerpt: str


class RectificationRecommendation(ContractModel):
    responsible_party_id: str
    due_at: datetime
    reason: str


class InvestigationResult(ContractModel):
    facts: dict[str, Any]
    conflicts: list[str]
    missing_fields: list[str]
    applicable_task: str | None = None
    hazards: list[str]
    required_ppe: list[PpeType]
    recommendation: str | None = None
    rectification_recommendation: RectificationRecommendation | None = None
    citations: list[Citation]
    tool_trace: list[str]


class CaseSnapshot(ContractModel):
    case_id: str
    session_id: str
    camera_id: str
    person_track_id: str
    ppe_type: PpeType
    status: CaseStatus
    version: int = Field(ge=1)
    candidate: CandidateEvidence
    vlm_review: VlmReviewResult | None = None
    investigation: InvestigationResult | None = None
    rectification_responsible_party_id: str | None = None
    rectification_due_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AnalysisEventType(str, Enum):
    SESSION_PROGRESS = "SESSION_PROGRESS"
    CANDIDATE_CREATED = "CANDIDATE_CREATED"
    VLM_REVIEWED = "VLM_REVIEWED"
    CASE_UPDATED = "CASE_UPDATED"
    SESSION_FINISHED = "SESSION_FINISHED"
    SESSION_FAILED = "SESSION_FAILED"


class AnalysisEvent(ContractModel):
    event_id: str
    event_type: AnalysisEventType
    session_id: str
    occurred_at: datetime
    case_id: str | None = None
    playback_ms: int = Field(ge=0)
    payload: dict[str, Any] = Field(default_factory=dict)


SHARED_CONTRACTS = (
    CandidateEvidence,
    VlmReviewResult,
    InvestigationResult,
    CaseSnapshot,
    AnalysisEvent,
)
