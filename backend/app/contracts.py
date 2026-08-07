from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    ValidationInfo,
    field_validator,
    model_validator,
)


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PpeType(str, Enum):
    HELMET = "helmet"
    GOGGLES = "goggles"
    GLOVES = "gloves"
    BOOTS = "boots"
    VEST = "vest"


class EvidenceKind(str, Enum):
    NEGATIVE_CLASS_DETECTION = "NEGATIVE_CLASS_DETECTION"
    MISSING_POSITIVE_ASSOCIATION = "MISSING_POSITIVE_ASSOCIATION"


class FrameRole(str, Enum):
    BEFORE = "BEFORE"
    REPRESENTATIVE = "REPRESENTATIVE"
    AFTER = "AFTER"


class BoundingBox(ContractModel):
    x1: float = Field(ge=0)
    y1: float = Field(ge=0)
    x2: float = Field(ge=0)
    y2: float = Field(ge=0)

    @model_validator(mode="after")
    def edges_must_define_an_area(self) -> BoundingBox:
        if self.x2 <= self.x1:
            raise ValueError("x2 must be greater than x1")
        if self.y2 <= self.y1:
            raise ValueError("y2 must be greater than y1")
        return self


class EvidenceFrame(ContractModel):
    timestamp_ms: int = Field(ge=0)
    image_url: str
    image_width: int = Field(gt=0)
    image_height: int = Field(gt=0)
    frame_role: FrameRole
    person_box: BoundingBox
    observation_box: BoundingBox | None = None
    observation_confidence: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def boxes_must_match_the_original_frame(self) -> EvidenceFrame:
        for field_name, box in (
            ("person_box", self.person_box),
            ("observation_box", self.observation_box),
        ):
            if box is None:
                continue
            if box.x2 > self.image_width:
                raise ValueError(f"{field_name} exceeds image_width")
            if box.y2 > self.image_height:
                raise ValueError(f"{field_name} exceeds image_height")
        has_box = self.observation_box is not None
        has_confidence = self.observation_confidence is not None
        if has_box != has_confidence:
            raise ValueError(
                "observation_box and observation_confidence must be set together"
            )
        return self


class CandidateEvidence(ContractModel):
    candidate_id: str
    session_id: str
    camera_id: str
    person_track_id: str
    ppe_type: PpeType
    evidence_kind: EvidenceKind
    confidence: float = Field(ge=0, le=1)
    model_name: str = Field(min_length=1)
    model_version: Annotated[str, Field(min_length=1)] | None = None
    weights_sha256: str | None = Field(
        default=None, pattern=r"^[0-9a-fA-F]{64}$"
    )
    aggregation_method: str = Field(min_length=1)
    aggregation_parameters: dict[str, JsonValue]
    occurred_at: AwareDatetime
    first_seen_ms: int = Field(ge=0)
    last_seen_ms: int = Field(ge=0)
    frames: list[EvidenceFrame] = Field(min_length=1)

    @field_validator("last_seen_ms")
    @classmethod
    def end_must_not_precede_start(
        cls, value: int, info: ValidationInfo
    ) -> int:
        first_seen_ms = info.data.get("first_seen_ms")
        if first_seen_ms is not None and value < first_seen_ms:
            raise ValueError("last_seen_ms must not precede first_seen_ms")
        return value

    @model_validator(mode="after")
    def evidence_must_be_traceable_and_consistent(self) -> CandidateEvidence:
        if self.model_version is None and self.weights_sha256 is None:
            raise ValueError("model_version or weights_sha256 is required")

        timestamps = [frame.timestamp_ms for frame in self.frames]
        if any(
            current >= following
            for current, following in zip(timestamps, timestamps[1:])
        ):
            raise ValueError("frame timestamps must be strictly increasing")

        representatives = [
            frame
            for frame in self.frames
            if frame.frame_role is FrameRole.REPRESENTATIVE
        ]
        if len(representatives) != 1:
            raise ValueError("candidate must contain exactly one REPRESENTATIVE frame")
        representative = representatives[0]
        if not (
            self.first_seen_ms
            <= representative.timestamp_ms
            <= self.last_seen_ms
        ):
            raise ValueError("representative frame must be inside violation window")

        if self.evidence_kind is EvidenceKind.NEGATIVE_CLASS_DETECTION:
            if representative.observation_box is None:
                raise ValueError(
                    "negative detection requires a representative observation"
                )
        elif any(frame.observation_box is not None for frame in self.frames):
            raise ValueError(
                "missing positive association must not contain observations"
            )
        return self


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
    model_provider: str
    model_parameters: dict[str, JsonValue]
    reviewed_at: AwareDatetime


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


class HumanCaseCommand(ContractModel):
    actor_id: str = Field(min_length=1)
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1)


class SubmitFacts(HumanCaseCommand):
    command_type: Literal["SUBMIT_FACTS"] = "SUBMIT_FACTS"
    facts: dict[str, JsonValue] = Field(min_length=1)


class ApproveRectification(HumanCaseCommand):
    command_type: Literal["APPROVE_RECTIFICATION"] = "APPROVE_RECTIFICATION"
    responsible_party_id: str = Field(min_length=1)
    rectification_due_at: AwareDatetime


class RectificationEvidence(ContractModel):
    evidence_id: str = Field(min_length=1)
    image_url: str = Field(min_length=1)
    captured_at: AwareDatetime
    note: str | None = None


class SubmitRectificationEvidence(HumanCaseCommand):
    command_type: Literal["SUBMIT_RECTIFICATION_EVIDENCE"] = (
        "SUBMIT_RECTIFICATION_EVIDENCE"
    )
    description: str = Field(min_length=1)
    evidence: list[RectificationEvidence] = Field(min_length=1)


class RejectCase(HumanCaseCommand):
    command_type: Literal["REJECT_CASE"] = "REJECT_CASE"


class RequestReinvestigation(HumanCaseCommand):
    command_type: Literal["REQUEST_REINVESTIGATION"] = (
        "REQUEST_REINVESTIGATION"
    )


class ApproveClosure(HumanCaseCommand):
    command_type: Literal["APPROVE_CLOSURE"] = "APPROVE_CLOSURE"
    recheck_conclusion: str = Field(min_length=1)


class RejectRecheck(HumanCaseCommand):
    command_type: Literal["REJECT_RECHECK"] = "REJECT_RECHECK"
    recheck_conclusion: str = Field(min_length=1)


CaseCommand = Annotated[
    SubmitFacts
    | ApproveRectification
    | RejectCase
    | RequestReinvestigation
    | SubmitRectificationEvidence
    | ApproveClosure
    | RejectRecheck,
    Field(discriminator="command_type"),
]


class Citation(ContractModel):
    document_title: str
    standard_no: str | None = None
    section: str
    effective_date: str | None = None
    source_url: str
    excerpt: str


class RectificationRecommendation(ContractModel):
    responsible_party_id: str
    due_at: AwareDatetime
    reason: str


class InvestigationResult(ContractModel):
    facts: dict[str, JsonValue]
    conflicts: list[str]
    missing_fields: list[str]
    applicable_task: str | None = None
    hazards: list[str]
    required_ppe: list[PpeType]
    recommendation: str | None = None
    rectification_recommendation: RectificationRecommendation | None = None
    citations: list[Citation]
    tool_trace: list[str]


class ActorRole(str, Enum):
    SITE_SAFETY_OFFICER = "SITE_SAFETY_OFFICER"
    PROJECT_SAFETY_REVIEWER = "PROJECT_SAFETY_REVIEWER"


class HumanSubmissionType(str, Enum):
    FACTS = "FACTS"
    RECTIFICATION_EVIDENCE = "RECTIFICATION_EVIDENCE"


class HumanSubmissionBase(ContractModel):
    submission_id: str
    case_id: str
    actor_id: str
    actor_name: str
    actor_role: ActorRole
    reason: str
    created_at: AwareDatetime


class FactsSubmissionRecord(HumanSubmissionBase):
    submission_type: Literal["FACTS"] = "FACTS"
    facts: dict[str, JsonValue]


class RectificationEvidenceSubmissionRecord(HumanSubmissionBase):
    submission_type: Literal["RECTIFICATION_EVIDENCE"] = (
        "RECTIFICATION_EVIDENCE"
    )
    description: str
    evidence: list[RectificationEvidence]


HumanSubmissionRecord = Annotated[
    FactsSubmissionRecord | RectificationEvidenceSubmissionRecord,
    Field(discriminator="submission_type"),
]


class TimelineSource(str, Enum):
    YOLO = "YOLO"
    VLM = "VLM"
    AGENT = "AGENT"
    HUMAN = "HUMAN"


class CaseTimelineItem(ContractModel):
    timeline_item_id: str
    source: TimelineSource
    action: str
    from_status: CaseStatus | None = None
    to_status: CaseStatus
    actor_id: str | None = None
    actor_name: str | None = None
    actor_role: ActorRole | None = None
    reason: str | None = None
    occurred_at: AwareDatetime


class CaseTransition(ContractModel):
    from_status: CaseStatus
    to_status: CaseStatus
    actor_id: str | None = None
    actor_role: ActorRole | None = None
    reason: str = Field(min_length=1)
    occurred_at: AwareDatetime


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
    human_facts: dict[str, JsonValue] = Field(default_factory=dict)
    rectification_responsible_party_id: str | None = None
    rectification_due_at: AwareDatetime | None = None
    rectification_evidence: list[RectificationEvidence] = Field(
        default_factory=list
    )
    rectification_description: str | None = None
    recheck_conclusion: str | None = None
    created_at: AwareDatetime
    updated_at: AwareDatetime
    transitions: list[CaseTransition] = Field(default_factory=list)

    @model_validator(mode="after")
    def identity_must_match_candidate(self) -> CaseSnapshot:
        compared_fields = (
            "session_id",
            "camera_id",
            "person_track_id",
            "ppe_type",
        )
        mismatched = [
            field_name
            for field_name in compared_fields
            if getattr(self, field_name) != getattr(self.candidate, field_name)
        ]
        if mismatched:
            raise ValueError(
                "case identity must match candidate fields: "
                + ", ".join(mismatched)
            )
        return self


class CaseUrgency(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class CaseListItem(ContractModel):
    case_id: str
    ppe_type: PpeType
    status: CaseStatus
    version: int = Field(ge=1)
    occurred_at: AwareDatetime
    updated_at: AwareDatetime
    camera_id: str
    camera_name: str
    zone_id: str
    zone_name: str
    responsible_party_id: str | None = None
    responsible_party_name: str | None = None
    rectification_due_at: AwareDatetime | None = None
    overdue: bool
    urgency: CaseUrgency


class Pagination(ContractModel):
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total_items: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class RepeatRiskSummary(ContractModel):
    zone_id: str
    zone_name: str
    ppe_type: PpeType
    case_count: int = Field(ge=1)


class CaseStatistics(ContractModel):
    open_count: int = Field(ge=0)
    needs_human_facts_count: int = Field(ge=0)
    pending_review_count: int = Field(ge=0)
    rectification_open_count: int = Field(ge=0)
    recheck_pending_count: int = Field(ge=0)
    overdue_count: int = Field(ge=0)
    average_closure_minutes: float | None = Field(default=None, ge=0)
    top_repeat_risk: RepeatRiskSummary | None = None


class CaseListResponse(ContractModel):
    items: list[CaseListItem]
    pagination: Pagination
    statistics: CaseStatistics


class CaseDetailResponse(ContractModel):
    snapshot: CaseSnapshot
    camera_name: str
    zone_id: str
    zone_name: str
    zone_type: str
    video_id: str
    video_title: str
    responsible_party_name: str | None = None
    responsible_party_kind: str | None = None
    citations: list[Citation]
    human_submissions: list[HumanSubmissionRecord]
    timeline: list[CaseTimelineItem]


class ErrorResponse(ContractModel):
    code: str
    message: str
    current_version: int | None = Field(default=None, ge=1)


class CaseCommandResponse(ContractModel):
    snapshot: CaseSnapshot
    version: int = Field(ge=1)

    @model_validator(mode="after")
    def version_must_match_snapshot(self) -> CaseCommandResponse:
        if self.version != self.snapshot.version:
            raise ValueError("version must match snapshot.version")
        return self


class AnalysisEventType(str, Enum):
    SESSION_PROGRESS = "SESSION_PROGRESS"
    CANDIDATE_CREATED = "CANDIDATE_CREATED"
    VLM_REVIEWED = "VLM_REVIEWED"
    CASE_UPDATED = "CASE_UPDATED"
    SESSION_FINISHED = "SESSION_FINISHED"
    SESSION_FAILED = "SESSION_FAILED"


class AnalysisStage(str, Enum):
    STARTING = "STARTING"
    READING = "READING"
    INFERENCING = "INFERENCING"
    STOPPING = "STOPPING"


class SessionProgressPayload(ContractModel):
    stage: AnalysisStage
    progress: float = Field(ge=0, le=1)
    message: str | None
    inference_fps: float = Field(ge=0)
    candidate_count: int = Field(ge=0)
    case_count: int = Field(ge=0)


class SessionFailedPayload(ContractModel):
    error_code: str
    message: str
    retryable: bool


class CandidateCreatedPayload(ContractModel):
    candidate_id: str
    ppe_type: PpeType
    confidence: float = Field(ge=0, le=1)
    candidate_occurred_at: AwareDatetime
    person_track_id: str


class VlmReviewedPayload(ContractModel):
    verdict: VlmVerdict
    evidence_sufficient: bool
    reason: str
    status: CaseStatus
    version: int = Field(ge=1)


class CaseUpdatedPayload(ContractModel):
    status: CaseStatus
    version: int = Field(ge=1)
    updated_at: AwareDatetime
    action: str


class SessionFinishedPayload(ContractModel):
    candidate_count: int = Field(ge=0)
    case_count: int = Field(ge=0)


AnalysisEventPayload = (
    SessionProgressPayload
    | SessionFailedPayload
    | CandidateCreatedPayload
    | VlmReviewedPayload
    | CaseUpdatedPayload
    | SessionFinishedPayload
)


class AnalysisEvent(ContractModel):
    event_id: str
    sequence: int = Field(ge=1)
    event_type: AnalysisEventType
    session_id: str
    occurred_at: AwareDatetime
    case_id: str | None
    playback_ms: int = Field(ge=0)
    payload: AnalysisEventPayload

    @model_validator(mode="after")
    def payload_must_match_event_type(self) -> AnalysisEvent:
        payload_types: dict[AnalysisEventType, type[ContractModel]] = {
            AnalysisEventType.SESSION_PROGRESS: SessionProgressPayload,
            AnalysisEventType.SESSION_FAILED: SessionFailedPayload,
            AnalysisEventType.CANDIDATE_CREATED: CandidateCreatedPayload,
            AnalysisEventType.VLM_REVIEWED: VlmReviewedPayload,
            AnalysisEventType.CASE_UPDATED: CaseUpdatedPayload,
            AnalysisEventType.SESSION_FINISHED: SessionFinishedPayload,
        }
        expected_payload = payload_types[self.event_type]
        if not isinstance(self.payload, expected_payload):
            raise ValueError("payload must match event_type")
        if self.event_type in {
            AnalysisEventType.CANDIDATE_CREATED,
            AnalysisEventType.VLM_REVIEWED,
            AnalysisEventType.CASE_UPDATED,
        } and self.case_id is None:
            raise ValueError("case_id is required for case events")
        return self


SHARED_CONTRACTS = (
    CandidateEvidence,
    VlmReviewResult,
    InvestigationResult,
    CaseSnapshot,
    CaseListResponse,
    CaseDetailResponse,
    AnalysisEvent,
    ErrorResponse,
    CaseCommandResponse,
)

SHARED_COMMANDS = (
    SubmitFacts,
    ApproveRectification,
    RejectCase,
    RequestReinvestigation,
    SubmitRectificationEvidence,
    ApproveClosure,
    RejectRecheck,
)
