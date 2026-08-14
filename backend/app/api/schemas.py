from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.contracts import AnalysisStage, Citation
from app.domain.site_context import (
    CameraInfo,
    DemoUser,
    ResponsibleParty,
    TaskPpeMatrix,
    WorkPermit,
    ZoneInfo,
)


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DemoVideoItem(ApiModel):
    video_id: str
    camera_id: str
    camera_name: str
    zone_id: str
    zone_name: str
    title: str
    duration_ms: int = Field(gt=0)
    scenario_started_at: AwareDatetime
    content_url: str


class DemoContextResponse(ApiModel):
    cameras: list[CameraInfo]
    zones: list[ZoneInfo]
    work_permits: list[WorkPermit]
    task_ppe_matrix: list[TaskPpeMatrix]
    responsible_parties: list[ResponsibleParty]
    users: list[DemoUser]


class RequirementSearchResponse(ApiModel):
    query: str
    top_k: int = Field(ge=1)
    citations: list[Citation]


class StartAnalysisSessionRequest(ApiModel):
    video_id: str = Field(min_length=1)


class AnalysisSessionResponse(ApiModel):
    session_id: str
    video_id: str
    stage: AnalysisStage
    stream_url: str
    events_url: str
