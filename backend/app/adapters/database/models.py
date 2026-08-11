from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum as PythonEnum
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from app.contracts import (
    ActorRole,
    AnalysisStage,
    CaseStatus,
    EvidenceKind,
    FrameRole,
    HumanSubmissionType,
    PpeType,
    VlmVerdict,
)
from app.domain.site_context import WorkPermitStatus


class TimezoneAwareDateTime(TypeDecorator[datetime]):
    """Store aware datetimes as ISO-8601 text so SQLite preserves offsets."""

    impl = String(40)
    cache_ok = True

    def process_bind_param(
        self, value: datetime | None, dialect: Any
    ) -> str | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timezone-aware datetime is required")
        return value.astimezone(timezone.utc).isoformat()

    def process_result_value(
        self, value: str | None, dialect: Any
    ) -> datetime | None:
        return datetime.fromisoformat(value) if value is not None else None


def enum_column_type(
    enum_class: type[PythonEnum], name: str
) -> Enum:
    return Enum(
        enum_class,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda members: [member.value for member in members],
    )


class Base(DeclarativeBase):
    pass


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[ActorRole] = mapped_column(
        enum_column_type(ActorRole, "actor_role"), nullable=False
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ZoneModel(Base):
    __tablename__ = "zones"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    zone_type: Mapped[str] = mapped_column(String(64), nullable=False)


class CameraModel(Base):
    __tablename__ = "cameras"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    zone_id: Mapped[str] = mapped_column(
        ForeignKey("zones.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )


class VideoModel(Base):
    __tablename__ = "videos"
    __table_args__ = (
        CheckConstraint("duration_ms > 0", name="ck_videos_duration_positive"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    camera_id: Mapped[str] = mapped_column(
        ForeignKey("cameras.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    local_path: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    scenario_started_at: Mapped[datetime] = mapped_column(
        TimezoneAwareDateTime(), nullable=False
    )


class ResponsiblePartyModel(Base):
    __tablename__ = "responsible_parties"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    zone_id: Mapped[str] = mapped_column(
        ForeignKey("zones.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class TaskPpeMatrixModel(Base):
    __tablename__ = "task_ppe_matrix"
    __table_args__ = (
        CheckConstraint(
            "rectification_window_minutes > 0",
            name="ck_task_ppe_matrix_window_positive",
        ),
    )

    task_code: Mapped[str] = mapped_column(String(100), primary_key=True)
    hazards_json: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    required_ppe_json: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    exception_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    rectification_window_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False
    )


class WorkPermitModel(Base):
    __tablename__ = "work_permits"
    __table_args__ = (
        CheckConstraint(
            "ends_at > starts_at", name="ck_work_permits_window_ordered"
        ),
        Index(
            "ix_work_permits_zone_status_window",
            "zone_id",
            "status",
            "starts_at",
            "ends_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    zone_id: Mapped[str] = mapped_column(
        ForeignKey("zones.id", ondelete="RESTRICT"), nullable=False
    )
    task_code: Mapped[str] = mapped_column(
        ForeignKey("task_ppe_matrix.task_code", ondelete="RESTRICT"),
        nullable=False,
    )
    hazards_json: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    responsible_party_id: Mapped[str] = mapped_column(
        ForeignKey("responsible_parties.id", ondelete="RESTRICT"),
        nullable=False,
    )
    starts_at: Mapped[datetime] = mapped_column(
        TimezoneAwareDateTime(), nullable=False
    )
    ends_at: Mapped[datetime] = mapped_column(
        TimezoneAwareDateTime(), nullable=False
    )
    status: Mapped[WorkPermitStatus] = mapped_column(
        enum_column_type(WorkPermitStatus, "work_permit_status"),
        nullable=False,
        default=WorkPermitStatus.ACTIVE,
    )


class AnalysisSessionModel(Base):
    __tablename__ = "analysis_sessions"
    __table_args__ = (
        CheckConstraint(
            "playback_ms >= 0", name="ck_analysis_sessions_playback_nonnegative"
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    video_id: Mapped[str] = mapped_column(
        ForeignKey("videos.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[AnalysisStage] = mapped_column(
        enum_column_type(AnalysisStage, "analysis_stage"),
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        TimezoneAwareDateTime(), nullable=False
    )
    playback_ms: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )


class CaseModel(Base):
    __tablename__ = "cases"
    __table_args__ = (
        UniqueConstraint("candidate_id", name="uq_cases_candidate_id"),
        CheckConstraint("version >= 1", name="ck_cases_version_positive"),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_cases_confidence_range",
        ),
        CheckConstraint(
            "last_seen_ms >= first_seen_ms",
            name="ck_cases_candidate_window_ordered",
        ),
        Index("ix_cases_status_occurred_at", "status", "occurred_at"),
        Index("ix_cases_ppe_type_occurred_at", "ppe_type", "occurred_at"),
        Index(
            "ix_cases_responsible_due_at",
            "rectification_responsible_party_id",
            "rectification_due_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    candidate_id: Mapped[str] = mapped_column(String(100), nullable=False)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_sessions.id", ondelete="RESTRICT"), nullable=False
    )
    camera_id: Mapped[str] = mapped_column(
        ForeignKey("cameras.id", ondelete="RESTRICT"), nullable=False
    )
    person_track_id: Mapped[str] = mapped_column(String(100), nullable=False)
    ppe_type: Mapped[PpeType] = mapped_column(
        enum_column_type(PpeType, "ppe_type"), nullable=False
    )
    evidence_kind: Mapped[EvidenceKind] = mapped_column(
        enum_column_type(EvidenceKind, "evidence_kind"), nullable=False
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    model_name: Mapped[str] = mapped_column(String(200), nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(200), nullable=True)
    weights_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    aggregation_method: Mapped[str] = mapped_column(String(200), nullable=False)
    aggregation_parameters_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    occurred_at: Mapped[datetime] = mapped_column(
        TimezoneAwareDateTime(), nullable=False
    )
    first_seen_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    last_seen_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[CaseStatus] = mapped_column(
        enum_column_type(CaseStatus, "case_status"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    human_facts_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    rectification_responsible_party_id: Mapped[str | None] = mapped_column(
        ForeignKey("responsible_parties.id", ondelete="RESTRICT"), nullable=True
    )
    rectification_due_at: Mapped[datetime | None] = mapped_column(
        TimezoneAwareDateTime(), nullable=True
    )
    rectification_description: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    recheck_conclusion: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TimezoneAwareDateTime(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TimezoneAwareDateTime(), nullable=False
    )


class CaseEvidenceModel(Base):
    __tablename__ = "case_evidence"
    __table_args__ = (
        CheckConstraint(
            "timestamp_ms >= 0", name="ck_case_evidence_timestamp_nonnegative"
        ),
        Index("ix_case_evidence_case_timestamp", "case_id", "timestamp_ms"),
    )

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[FrameRole] = mapped_column(
        enum_column_type(FrameRole, "case_evidence_frame_role"), nullable=False
    )
    timestamp_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )


class VlmReviewModel(Base):
    __tablename__ = "vlm_reviews"

    case_id: Mapped[str] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), primary_key=True
    )
    verdict: Mapped[VlmVerdict] = mapped_column(
        enum_column_type(VlmVerdict, "vlm_verdict"), nullable=False
    )
    result_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    model_name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TimezoneAwareDateTime(), nullable=False
    )


class InvestigationModel(Base):
    __tablename__ = "investigations"
    __table_args__ = (
        Index("ix_investigations_case_id", "case_id"),
    )

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    facts_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    conflicts_json: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    missing_fields_json: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    trace_json: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )


class CitationModel(Base):
    __tablename__ = "citations"
    __table_args__ = (Index("ix_citations_case_id", "case_id"),)

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    document_title: Mapped[str] = mapped_column(String(300), nullable=False)
    standard_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    section: Mapped[str] = mapped_column(String(200), nullable=False)
    effective_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)


class HumanSubmissionModel(Base):
    __tablename__ = "human_submissions"
    __table_args__ = (
        Index(
            "ix_human_submissions_case_created_at",
            "case_id",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    actor_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    kind: Mapped[HumanSubmissionType] = mapped_column(
        enum_column_type(HumanSubmissionType, "human_submission_type"),
        nullable=False,
    )
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TimezoneAwareDateTime(), nullable=False
    )


class CaseTransitionModel(Base):
    __tablename__ = "case_transitions"
    __table_args__ = (
        Index(
            "ix_case_transitions_case_created_at",
            "case_id",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    from_status: Mapped[CaseStatus] = mapped_column(
        enum_column_type(CaseStatus, "case_transition_from_status"),
        nullable=False,
    )
    to_status: Mapped[CaseStatus] = mapped_column(
        enum_column_type(CaseStatus, "case_transition_to_status"), nullable=False
    )
    actor_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    actor_role: Mapped[ActorRole | None] = mapped_column(
        enum_column_type(ActorRole, "case_transition_actor_role"), nullable=True
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TimezoneAwareDateTime(), nullable=False
    )
