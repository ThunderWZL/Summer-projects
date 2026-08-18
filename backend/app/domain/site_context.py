from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.contracts import ActorRole, PpeType


class SiteContextModel(BaseModel):
    """共享业务上下文值模型：拒绝未声明字段，字段语义与设计文档 §6.2 对齐。

    这是 Thxnks 种子数据（X-01）必须按此产出的值模型集合；端口只读，
    禁止通过端口写入任何业务数据。
    """

    model_config = ConfigDict(extra="forbid")


class ZoneInfo(SiteContextModel):
    zone_id: str
    name: str
    zone_type: str


class CameraInfo(SiteContextModel):
    camera_id: str
    name: str
    zone_id: str


class VideoInfo(SiteContextModel):
    video_id: str
    camera_id: str
    title: str
    local_path: str
    source_url: str | None = None
    duration_ms: int
    scenario_started_at: datetime


class WorkPermitStatus(str, Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"


class WorkPermit(SiteContextModel):
    permit_id: str
    zone_id: str
    task_code: str
    hazards: list[str]
    responsible_party_id: str
    starts_at: datetime
    ends_at: datetime
    status: WorkPermitStatus = WorkPermitStatus.ACTIVE

    @model_validator(mode="after")
    def window_must_be_ordered(self) -> WorkPermit:
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class TaskPpeMatrix(SiteContextModel):
    task_code: str
    name: str
    hazards: list[str]
    required_ppe: list[PpeType]
    exception_note: str | None = None
    rectification_window_minutes: int = Field(gt=0)


class WorksitePreset(SiteContextModel):
    preset_id: str
    name: str
    required_ppe: list[PpeType]


class CameraWorksiteConfiguration(SiteContextModel):
    camera_id: str
    mode: Literal["PRESET", "CUSTOM"]
    preset_id: str | None = None
    name: str
    required_ppe: list[PpeType]


class CameraNotFound(ValueError):
    code = "CAMERA_NOT_FOUND"

    def __init__(self, camera_id: str) -> None:
        super().__init__(f"camera {camera_id} was not found")


class WorksitePresetNotFound(ValueError):
    code = "WORKSITE_PRESET_NOT_FOUND"

    def __init__(self, preset_id: str) -> None:
        super().__init__(f"worksite preset {preset_id} was not found")


class ResponsibleParty(SiteContextModel):
    party_id: str
    name: str
    kind: str
    zone_id: str
    active: bool = True


class DemoUser(SiteContextModel):
    actor_id: str
    name: str
    role: ActorRole
    active: bool = True


class SiteContextPort(Protocol):
    """Agent 业务工具与 /api/v1/demo/* 的运行期业务上下文。"""

    def get_zone_at(self, camera_id: str) -> ZoneInfo | None: ...

    def find_active_work_permits(
        self, zone_id: str, occurred_at: datetime
    ) -> list[WorkPermit]: ...

    def get_task_ppe_matrix(self, task_code: str) -> TaskPpeMatrix | None: ...

    def list_eligible_responsible_parties(
        self, zone_id: str
    ) -> list[ResponsibleParty]: ...

    def list_videos(self) -> list[VideoInfo]: ...

    def get_video(self, video_id: str) -> VideoInfo | None: ...

    def list_worksite_presets(self) -> list[WorksitePreset]: ...

    def list_camera_worksite_configurations(
        self,
    ) -> list[CameraWorksiteConfiguration]: ...

    def get_camera_worksite_configuration(
        self, camera_id: str
    ) -> CameraWorksiteConfiguration | None: ...

    def configure_camera_worksite(
        self,
        camera_id: str,
        *,
        mode: Literal["PRESET", "CUSTOM"],
        preset_id: str | None = None,
        name: str | None = None,
        required_ppe: list[PpeType] | None = None,
    ) -> CameraWorksiteConfiguration: ...


class UserDirectoryPort(Protocol):
    def get(self, actor_id: str) -> DemoUser | None: ...
