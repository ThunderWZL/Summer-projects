from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.contracts import Citation
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
