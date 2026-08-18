from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from app.contracts import AnalysisStage, Citation, PpeType
from app.domain.site_context import (
    CameraWorksiteConfiguration,
    CameraInfo,
    DemoUser,
    ResponsibleParty,
    TaskPpeMatrix,
    WorkPermit,
    WorksitePreset,
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


class WorksiteConfigurationsResponse(ApiModel):
    presets: list[WorksitePreset]
    cameras: list[CameraWorksiteConfiguration]


class PresetWorksiteConfigurationRequest(ApiModel):
    mode: Literal["PRESET"]
    preset_id: str = Field(min_length=1)


class CustomWorksiteConfigurationRequest(ApiModel):
    mode: Literal["CUSTOM"]
    name: str = Field(min_length=1, max_length=40)
    required_ppe: list[PpeType]

    @field_validator("required_ppe")
    @classmethod
    def only_demo_ppe(cls, values: list[PpeType]) -> list[PpeType]:
        allowed = {PpeType.HELMET, PpeType.GLOVES, PpeType.VEST}
        if any(value not in allowed for value in values):
            raise ValueError("only helmet, gloves, and vest are configurable")
        if len(values) != len(set(values)):
            raise ValueError("required_ppe values must be unique")
        return values


CameraWorksiteConfigurationRequest = Annotated[
    PresetWorksiteConfigurationRequest | CustomWorksiteConfigurationRequest,
    Field(discriminator="mode"),
]


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


class RectificationImageUploadResponse(ApiModel):
    evidence_id: str
    image_url: str
