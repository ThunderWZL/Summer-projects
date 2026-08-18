from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, Response

from app.api.deps import get_site_context, get_user_directory
from app.api.errors import error_response
from app.api.schemas import (
    CameraWorksiteConfigurationRequest,
    CustomWorksiteConfigurationRequest,
    DemoContextResponse,
    DemoVideoItem,
    WorksiteConfigurationsResponse,
)
from app.contracts import ErrorResponse
from app.domain.site_context import (
    CameraNotFound,
    CameraInfo,
    CameraWorksiteConfiguration,
    SiteContextPort,
    UserDirectoryPort,
    WorksitePresetNotFound,
)


router = APIRouter(prefix="/api/v1/demo", tags=["demo"])
ERROR_RESPONSE_CONTENT = {"model": ErrorResponse}


def _camera_name(zone_name: str) -> str:
    return f"{zone_name.removesuffix('区')}机位"


@router.get("/videos", response_model=list[DemoVideoItem])
def list_demo_videos(
    context: SiteContextPort = Depends(get_site_context),
) -> list[DemoVideoItem]:
    items = []
    for video in context.list_videos():
        zone = context.get_zone_at(video.camera_id)
        if zone is None:
            continue
        items.append(
            DemoVideoItem(
                video_id=video.video_id,
                camera_id=video.camera_id,
                camera_name=_camera_name(zone.name),
                zone_id=zone.zone_id,
                zone_name=zone.name,
                title=video.title,
                duration_ms=video.duration_ms,
                scenario_started_at=video.scenario_started_at,
                content_url=(
                    f"/api/v1/demo/videos/{video.video_id}/content"
                ),
            )
        )
    return items


@router.get("/videos/{video_id}/content", response_class=FileResponse)
def get_demo_video_content(
    video_id: str,
    context: SiteContextPort = Depends(get_site_context),
) -> Response:
    video = context.get_video(video_id)
    if video is None or not Path(video.local_path).is_file():
        return error_response(
            404,
            "DEMO_VIDEO_NOT_FOUND",
            f"demo video {video_id} was not found",
        )
    return FileResponse(video.local_path, media_type="video/mp4")


@router.get("/context", response_model=DemoContextResponse)
def get_demo_context(
    context: SiteContextPort = Depends(get_site_context),
    users: UserDirectoryPort = Depends(get_user_directory),
) -> DemoContextResponse:
    cameras: dict[str, CameraInfo] = {}
    zones = {}
    permits = {}
    matrices = {}
    parties = {}
    for video in context.list_videos():
        zone = context.get_zone_at(video.camera_id)
        if zone is None:
            continue
        cameras[video.camera_id] = CameraInfo(
            camera_id=video.camera_id,
            name=_camera_name(zone.name),
            zone_id=zone.zone_id,
        )
        zones[zone.zone_id] = zone
        for permit in context.find_active_work_permits(
            zone.zone_id, video.scenario_started_at
        ):
            permits[permit.permit_id] = permit
            matrix = context.get_task_ppe_matrix(permit.task_code)
            if matrix is not None:
                matrices[matrix.task_code] = matrix
        for party in context.list_eligible_responsible_parties(zone.zone_id):
            parties[party.party_id] = party
    demo_users = [
        user
        for actor_id in ("officer-01", "reviewer-01")
        if (user := users.get(actor_id)) is not None
    ]
    return DemoContextResponse(
        cameras=list(cameras.values()),
        zones=list(zones.values()),
        work_permits=list(permits.values()),
        task_ppe_matrix=list(matrices.values()),
        responsible_parties=list(parties.values()),
        users=demo_users,
    )


@router.get(
    "/worksite-configurations",
    response_model=WorksiteConfigurationsResponse,
)
def list_worksite_configurations(
    context: SiteContextPort = Depends(get_site_context),
) -> WorksiteConfigurationsResponse:
    return WorksiteConfigurationsResponse(
        presets=context.list_worksite_presets(),
        cameras=context.list_camera_worksite_configurations(),
    )


@router.patch(
    "/worksite-configurations/{camera_id}",
    response_model=CameraWorksiteConfiguration,
    responses={
        404: {**ERROR_RESPONSE_CONTENT, "description": "监控通道不存在"},
        422: {**ERROR_RESPONSE_CONTENT, "description": "场地配置无效"},
    },
)
def configure_camera_worksite(
    camera_id: str,
    request: CameraWorksiteConfigurationRequest,
    context: SiteContextPort = Depends(get_site_context),
) -> CameraWorksiteConfiguration:
    try:
        if isinstance(request, CustomWorksiteConfigurationRequest):
            return context.configure_camera_worksite(
                camera_id,
                mode="CUSTOM",
                name=request.name,
                required_ppe=request.required_ppe,
            )
        return context.configure_camera_worksite(
            camera_id,
            mode="PRESET",
            preset_id=request.preset_id,
        )
    except CameraNotFound as error:
        return error_response(404, error.code, str(error))
    except WorksitePresetNotFound as error:
        return error_response(422, error.code, str(error))
