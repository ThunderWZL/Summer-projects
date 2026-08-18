from collections import Counter
from datetime import datetime
from math import ceil
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import Response
from pydantic import AwareDatetime, Field

from app.api.deps import (
    Clock,
    get_case_store,
    get_case_pipeline,
    get_case_workflow,
    get_clock,
    get_evidence_store_port,
    get_site_context,
    get_user_directory,
)
from app.api.errors import error_response
from app.api.schemas import RectificationImageUploadResponse
from app.contracts import (
    ApproveClosure,
    ApproveRectification,
    CaseCommandResponse,
    CaseDetailResponse,
    CaseListItem,
    CaseListResponse,
    CaseSnapshot,
    CaseStatistics,
    CaseStatus,
    CaseTimelineItem,
    CaseUrgency,
    ActorRole,
    ErrorResponse,
    FactsSubmissionRecord,
    Pagination,
    PpeType,
    RectificationEvidenceSubmissionRecord,
    RejectCase,
    RejectRecheck,
    RepeatRiskSummary,
    RequestReinvestigation,
    SubmitFacts,
    SubmitRectificationEvidence,
    TimelineSource,
)
from app.domain.case_store import CaseQuery, CaseStorePort
from app.domain.case_workflow import (
    CaseNotFound,
    CaseWorkflow,
    CommandNotAllowed,
    PermissionDenied,
)
from app.modules.video_analysis.evidence_store import FileEvidenceStore
from app.services.case_pipeline import CasePipeline
from app.domain.site_context import (
    ResponsibleParty,
    SiteContextPort,
    UserDirectoryPort,
    ZoneInfo,
)


router = APIRouter(prefix="/api/v1/cases", tags=["cases"])
MAX_RECTIFICATION_IMAGE_BYTES = 5 * 1024 * 1024

HIGH_RISK_ZONE_TYPES = {
    "SCAFFOLD",
    "CUTTING",
    "ROTATING_EQUIPMENT",
    "VEHICLE",
}
HIGH_CONSEQUENCE_PPE = {PpeType.HELMET, PpeType.GOGGLES, PpeType.VEST}
TERMINAL_STATUSES = {
    CaseStatus.VLM_REJECTED,
    CaseStatus.HUMAN_REJECTED,
    CaseStatus.CLOSED,
}
WORKFLOW_ERROR_RESPONSES = {
    400: {"model": ErrorResponse, "description": "命令业务校验失败"},
    403: {"model": ErrorResponse, "description": "当前角色无权执行命令"},
    404: {"model": ErrorResponse, "description": "事件不存在"},
    409: {"model": ErrorResponse, "description": "事件版本冲突"},
    422: {"model": ErrorResponse, "description": "个人防护装备不适用"},
}
ReviewCommand = Annotated[
    ApproveRectification | RejectCase | RequestReinvestigation,
    Field(discriminator="command_type"),
]
RecheckCommand = Annotated[
    ApproveClosure | RejectRecheck,
    Field(discriminator="command_type"),
]


def _zones_by_camera(context: SiteContextPort) -> dict[str, ZoneInfo]:
    return {
        video.camera_id: zone
        for video in context.list_videos()
        if (zone := context.get_zone_at(video.camera_id)) is not None
    }


def _is_overdue(snapshot: CaseSnapshot, now: datetime) -> bool:
    return bool(
        snapshot.rectification_due_at is not None
        and snapshot.rectification_due_at < now
        and snapshot.status not in TERMINAL_STATUSES
    )


def _urgency(
    snapshot: CaseSnapshot,
    zone: ZoneInfo,
    now: datetime,
) -> CaseUrgency:
    if _is_overdue(snapshot, now):
        return CaseUrgency.HIGH
    risky_zone = zone.zone_type in HIGH_RISK_ZONE_TYPES
    consequential_ppe = snapshot.ppe_type in HIGH_CONSEQUENCE_PPE
    if risky_zone and consequential_ppe:
        return CaseUrgency.HIGH
    if risky_zone or consequential_ppe:
        return CaseUrgency.MEDIUM
    return CaseUrgency.LOW


def _responsible_party(
    context: SiteContextPort,
    zone_id: str,
    party_id: str | None,
) -> ResponsibleParty | None:
    if party_id is None:
        return None
    return next(
        (
            party
            for party in context.list_eligible_responsible_parties(zone_id)
            if party.party_id == party_id
        ),
        None,
    )


@router.get("", response_model=CaseListResponse)
def list_cases(
    status: CaseStatus | None = None,
    ppe_type: PpeType | None = None,
    zone_id: str | None = None,
    responsible_party_id: str | None = None,
    occurred_from: AwareDatetime | None = None,
    occurred_to: AwareDatetime | None = None,
    overdue_only: bool = False,
    keyword: str | None = Query(default=None, min_length=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    store: CaseStorePort = Depends(get_case_store),
    context: SiteContextPort = Depends(get_site_context),
    clock: Clock = Depends(get_clock),
) -> CaseListResponse:
    now = clock()
    zones = _zones_by_camera(context)
    camera_ids = None
    if zone_id is not None:
        camera_ids = frozenset(
            camera_id
            for camera_id, zone in zones.items()
            if zone.zone_id == zone_id
        )
    query = CaseQuery(
        status=status,
        ppe_type=ppe_type,
        camera_ids=camera_ids,
        responsible_party_id=responsible_party_id,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
        overdue_only=overdue_only,
        keyword=keyword,
        as_of=now,
        page=page,
        page_size=page_size,
    )
    result = store.list(query)
    all_cases = store.list(CaseQuery(as_of=now, page_size=1_000_000)).items
    items = []
    for snapshot in result.items:
        zone = zones[snapshot.camera_id]
        party = _responsible_party(
            context,
            zone.zone_id,
            snapshot.rectification_responsible_party_id,
        )
        items.append(
            CaseListItem(
                case_id=snapshot.case_id,
                ppe_type=snapshot.ppe_type,
                status=snapshot.status,
                version=snapshot.version,
                occurred_at=snapshot.candidate.occurred_at,
                updated_at=snapshot.updated_at,
                camera_id=snapshot.camera_id,
                camera_name=f"{zone.name.removesuffix('区')}机位",
                zone_id=zone.zone_id,
                zone_name=zone.name,
                responsible_party_id=(
                    snapshot.rectification_responsible_party_id
                ),
                responsible_party_name=party.name if party else None,
                rectification_due_at=snapshot.rectification_due_at,
                overdue=_is_overdue(snapshot, now),
                urgency=_urgency(snapshot, zone, now),
            )
        )

    repeat_counts = Counter(
        (zones[case.camera_id].zone_id, case.ppe_type)
        for case in all_cases
        if case.status
        not in {CaseStatus.YOLO_CANDIDATE, CaseStatus.VLM_REJECTED}
        and case.vlm_review is not None
        and case.vlm_review.verdict.value == "CONFIRMED"
        and case.investigation is not None
        and case.ppe_type in case.investigation.required_ppe
    )
    repeat_risk = None
    if repeat_counts:
        (repeat_zone_id, repeat_ppe), count = sorted(
            repeat_counts.items(),
            key=lambda item: (
                -item[1],
                item[0][0],
                item[0][1].value,
            ),
        )[0]
        repeat_zone = next(
            zone for zone in zones.values() if zone.zone_id == repeat_zone_id
        )
        repeat_risk = RepeatRiskSummary(
            zone_id=repeat_zone_id,
            zone_name=repeat_zone.name,
            ppe_type=repeat_ppe,
            case_count=count,
        )
    closure_minutes = [
        (transition.occurred_at - case.created_at).total_seconds() / 60
        for case in all_cases
        for transition in case.transitions
        if transition.to_status is CaseStatus.CLOSED
    ]
    statistics = CaseStatistics(
        open_count=sum(case.status not in TERMINAL_STATUSES for case in all_cases),
        needs_human_facts_count=sum(
            case.status is CaseStatus.NEEDS_HUMAN_FACTS for case in all_cases
        ),
        pending_review_count=sum(
            case.status is CaseStatus.PENDING_REVIEW for case in all_cases
        ),
        rectification_open_count=sum(
            case.status is CaseStatus.RECTIFICATION_OPEN for case in all_cases
        ),
        recheck_pending_count=sum(
            case.status is CaseStatus.RECHECK_PENDING for case in all_cases
        ),
        overdue_count=sum(_is_overdue(case, now) for case in all_cases),
        average_closure_minutes=(
            round(sum(closure_minutes) / len(closure_minutes), 1)
            if closure_minutes
            else None
        ),
        top_repeat_risk=repeat_risk,
    )
    return CaseListResponse(
        items=items,
        pagination=Pagination(
            page=page,
            page_size=page_size,
            total_items=result.total_items,
            total_pages=ceil(result.total_items / page_size),
        ),
        statistics=statistics,
    )


@router.get("/{case_id}", response_model=CaseDetailResponse)
def get_case_detail(
    case_id: str,
    store: CaseStorePort = Depends(get_case_store),
    context: SiteContextPort = Depends(get_site_context),
    users: UserDirectoryPort = Depends(get_user_directory),
) -> CaseDetailResponse | Response:
    snapshot = store.get(case_id)
    if snapshot is None:
        return error_response(
            404,
            "CASE_NOT_FOUND",
            f"case {case_id} was not found",
        )
    zone = context.get_zone_at(snapshot.camera_id)
    video = next(
        (
            item
            for item in context.list_videos()
            if item.camera_id == snapshot.camera_id
        ),
        None,
    )
    if zone is None or video is None:
        return error_response(
            404,
            "CASE_CONTEXT_NOT_FOUND",
            f"business context for case {case_id} was not found",
        )
    party = _responsible_party(
        context,
        zone.zone_id,
        snapshot.rectification_responsible_party_id,
    )
    timeline = [
        CaseTimelineItem(
            timeline_item_id=f"{case_id}-created",
            source=TimelineSource.YOLO,
            action="CANDIDATE_CREATED",
            to_status=CaseStatus.YOLO_CANDIDATE,
            occurred_at=snapshot.created_at,
        )
    ]
    for index, transition in enumerate(snapshot.transitions, start=1):
        user = users.get(transition.actor_id) if transition.actor_id else None
        if transition.actor_id is not None:
            source = TimelineSource.HUMAN
        elif transition.to_status in {
            CaseStatus.VLM_REVIEWED,
            CaseStatus.VLM_REJECTED,
        }:
            source = TimelineSource.VLM
        else:
            source = TimelineSource.AGENT
        timeline.append(
            CaseTimelineItem(
                timeline_item_id=f"{case_id}-transition-{index}",
                source=source,
                action=transition.to_status.value,
                from_status=transition.from_status,
                to_status=transition.to_status,
                actor_id=transition.actor_id,
                actor_name=user.name if user else None,
                actor_role=transition.actor_role,
                reason=transition.reason,
                occurred_at=transition.occurred_at,
            )
        )
    citations = (
        snapshot.investigation.citations if snapshot.investigation else []
    )
    return CaseDetailResponse(
        snapshot=snapshot,
        camera_name=f"{zone.name.removesuffix('区')}机位",
        zone_id=zone.zone_id,
        zone_name=zone.name,
        zone_type=zone.zone_type,
        video_id=video.video_id,
        video_title=video.title,
        responsible_party_name=party.name if party else None,
        responsible_party_kind=party.kind if party else None,
        citations=citations,
        human_submissions=store.list_submissions(case_id),
        timeline=timeline,
    )


@router.post(
    "/{case_id}/facts",
    response_model=CaseCommandResponse,
    responses=WORKFLOW_ERROR_RESPONSES,
)
def submit_facts(
    case_id: str,
    command: SubmitFacts,
    workflow: CaseWorkflow = Depends(get_case_workflow),
    users: UserDirectoryPort = Depends(get_user_directory),
    pipeline: CasePipeline = Depends(get_case_pipeline),
    clock: Clock = Depends(get_clock),
) -> CaseCommandResponse:
    user = users.get(command.actor_id)
    if user is None:
        raise PermissionDenied(command.actor_id)
    submission = FactsSubmissionRecord(
        submission_id=f"submission-{case_id}-{command.expected_version + 1}",
        case_id=case_id,
        actor_id=user.actor_id,
        actor_name=user.name,
        actor_role=user.role,
        reason=command.reason,
        facts=command.facts,
        created_at=clock(),
    )
    snapshot = workflow.apply(case_id, command, submission=submission)
    snapshot = pipeline.resume_investigation(case_id)
    return CaseCommandResponse(snapshot=snapshot, version=snapshot.version)


@router.post(
    "/{case_id}/review",
    response_model=CaseCommandResponse,
    responses=WORKFLOW_ERROR_RESPONSES,
)
def review_case(
    case_id: str,
    command: ReviewCommand,
    workflow: CaseWorkflow = Depends(get_case_workflow),
    pipeline: CasePipeline = Depends(get_case_pipeline),
) -> CaseCommandResponse:
    snapshot = workflow.apply(case_id, command)
    if isinstance(command, RequestReinvestigation):
        snapshot = pipeline.resume_investigation(case_id)
    return CaseCommandResponse(snapshot=snapshot, version=snapshot.version)


@router.post(
    "/{case_id}/rectification-evidence",
    response_model=CaseCommandResponse,
    responses=WORKFLOW_ERROR_RESPONSES,
)
def submit_rectification_evidence(
    case_id: str,
    command: SubmitRectificationEvidence,
    workflow: CaseWorkflow = Depends(get_case_workflow),
    users: UserDirectoryPort = Depends(get_user_directory),
    clock: Clock = Depends(get_clock),
) -> CaseCommandResponse:
    user = users.get(command.actor_id)
    if user is None:
        raise PermissionDenied(command.actor_id)
    submission = RectificationEvidenceSubmissionRecord(
        submission_id=f"submission-{case_id}-{command.expected_version + 1}",
        case_id=case_id,
        actor_id=user.actor_id,
        actor_name=user.name,
        actor_role=user.role,
        reason=command.reason,
        description=command.description,
        evidence=command.evidence,
        created_at=clock(),
    )
    snapshot = workflow.apply(case_id, command, submission=submission)
    return CaseCommandResponse(snapshot=snapshot, version=snapshot.version)


@router.post(
    "/{case_id}/rectification-evidence/images/{evidence_id}",
    response_model=RectificationImageUploadResponse,
    status_code=status.HTTP_201_CREATED,
    responses=WORKFLOW_ERROR_RESPONSES,
)
async def upload_rectification_image(
    case_id: str,
    evidence_id: str,
    request: Request,
    actor_id: str = Query(min_length=1),
    cases: CaseStorePort = Depends(get_case_store),
    users: UserDirectoryPort = Depends(get_user_directory),
    images: FileEvidenceStore = Depends(get_evidence_store_port),
) -> RectificationImageUploadResponse | Response:
    user = users.get(actor_id)
    if (
        user is None
        or not user.active
        or user.role is not ActorRole.SITE_SAFETY_OFFICER
    ):
        raise PermissionDenied(actor_id)
    snapshot = cases.get(case_id)
    if snapshot is None:
        raise CaseNotFound(case_id)
    if snapshot.status is not CaseStatus.RECTIFICATION_OPEN:
        raise CommandNotAllowed("UPLOAD_RECTIFICATION_IMAGE", snapshot.status)

    image_bytes = await request.body()
    if len(image_bytes) > MAX_RECTIFICATION_IMAGE_BYTES:
        return error_response(413, "IMAGE_TOO_LARGE", "image must not exceed 5 MB")
    media_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
    try:
        image_url = images.store_rectification_image(
            case_id=case_id,
            evidence_id=evidence_id,
            image_bytes=image_bytes,
            media_type=media_type,
        )
    except ValueError:
        return error_response(
            422,
            "INVALID_IMAGE",
            "image must be a JPEG, PNG, or WebP file with valid content",
        )
    return RectificationImageUploadResponse(
        evidence_id=evidence_id,
        image_url=image_url,
    )


@router.post(
    "/{case_id}/recheck",
    response_model=CaseCommandResponse,
    responses=WORKFLOW_ERROR_RESPONSES,
)
def recheck_case(
    case_id: str,
    command: RecheckCommand,
    workflow: CaseWorkflow = Depends(get_case_workflow),
) -> CaseCommandResponse:
    snapshot = workflow.apply(case_id, command)
    return CaseCommandResponse(snapshot=snapshot, version=snapshot.version)
