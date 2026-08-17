from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.contracts import PpeType
from app.domain.site_context import (
    CameraInfo,
    ResponsibleParty,
    TaskPpeMatrix,
    VideoInfo,
    WorkPermit,
    WorkPermitStatus,
    ZoneInfo,
)

_RESOURCE_DIR = Path(__file__).resolve().parents[2] / "resources" / "demo"


class _ConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _TaskRule(_ConfigModel):
    task_code: str = Field(min_length=1)
    hazards: list[str]
    required_ppe: list[PpeType]
    exception_note: str | None = None
    rectification_window_minutes: int = Field(gt=0)


class _TaskRules(_ConfigModel):
    tasks: list[_TaskRule]

    @model_validator(mode="after")
    def task_codes_must_be_unique(self) -> _TaskRules:
        codes = [task.task_code for task in self.tasks]
        if len(codes) != len(set(codes)):
            raise ValueError("task_code must be unique")
        return self


class _SceneAssignment(_ConfigModel):
    camera_id: str = Field(min_length=1)
    camera_name: str = Field(min_length=1)
    zone_id: str = Field(min_length=1)
    zone_name: str = Field(min_length=1)
    zone_type: str = Field(min_length=1)
    video_id: str = Field(min_length=1)
    video_title: str = Field(min_length=1)
    video_local_path: str = Field(min_length=1)
    duration_ms: int = Field(gt=0)
    task_code: str | None = None
    responsible_party_id: str = Field(min_length=1)
    responsible_party_name: str = Field(min_length=1)
    responsible_party_kind: str = Field(min_length=1)


class _SceneAssignments(_ConfigModel):
    scenario_started_at: datetime
    permit_starts_at: datetime
    permit_ends_at: datetime
    scenes: list[_SceneAssignment]

    @model_validator(mode="after")
    def permit_window_must_be_ordered(self) -> _SceneAssignments:
        if self.permit_ends_at <= self.permit_starts_at:
            raise ValueError("permit_ends_at must be after permit_starts_at")
        return self

    @model_validator(mode="after")
    def camera_and_video_ids_must_be_unique(self) -> _SceneAssignments:
        for field in ("camera_id", "video_id"):
            values = [getattr(scene, field) for scene in self.scenes]
            if len(values) != len(set(values)):
                raise ValueError(f"{field} must be unique")
        return self


class MemorySiteContext:
    """Configuration-backed deterministic site context for the six demo scenes."""

    def __init__(
        self,
        task_rules_path: str | Path | None = None,
        scene_assignments_path: str | Path | None = None,
    ) -> None:
        rules = _TaskRules.model_validate(
            self._load_json(task_rules_path or _RESOURCE_DIR / "task_ppe_rules.json")
        )
        assignments = _SceneAssignments.model_validate(
            self._load_json(
                scene_assignments_path or _RESOURCE_DIR / "scene_assignments.json"
            )
        )
        self._matrices = {
            rule.task_code: TaskPpeMatrix(
                task_code=rule.task_code,
                hazards=list(rule.hazards),
                required_ppe=list(rule.required_ppe),
                exception_note=rule.exception_note,
                rectification_window_minutes=rule.rectification_window_minutes,
            )
            for rule in rules.tasks
        }
        unknown_tasks = {
            scene.task_code
            for scene in assignments.scenes
            if scene.task_code is not None and scene.task_code not in self._matrices
        }
        if unknown_tasks:
            raise ValueError("scene task_code must exist in task rules")
        self._zones = {
            scene.zone_id: ZoneInfo(
                zone_id=scene.zone_id,
                name=scene.zone_name,
                zone_type=scene.zone_type,
            )
            for scene in assignments.scenes
        }
        self._cameras = {
            scene.camera_id: CameraInfo(
                camera_id=scene.camera_id,
                name=scene.camera_name,
                zone_id=scene.zone_id,
            )
            for scene in assignments.scenes
        }
        self._videos = [
            VideoInfo(
                video_id=scene.video_id,
                camera_id=scene.camera_id,
                title=scene.video_title,
                local_path=scene.video_local_path,
                duration_ms=scene.duration_ms,
                scenario_started_at=assignments.scenario_started_at,
            )
            for scene in assignments.scenes
        ]
        self._parties = [
            ResponsibleParty(
                party_id=scene.responsible_party_id,
                name=scene.responsible_party_name,
                kind=scene.responsible_party_kind,
                zone_id=scene.zone_id,
            )
            for scene in assignments.scenes
        ]
        self._permits = [
            WorkPermit(
                permit_id=f"wp-{scene.camera_id.removeprefix('CAM-')}01",
                zone_id=scene.zone_id,
                task_code=scene.task_code,
                hazards=list(self._matrices[scene.task_code].hazards),
                responsible_party_id=scene.responsible_party_id,
                starts_at=assignments.permit_starts_at,
                ends_at=assignments.permit_ends_at,
                status=WorkPermitStatus.ACTIVE,
            )
            for scene in assignments.scenes
            if scene.task_code is not None
        ]

    @staticmethod
    def _load_json(path: str | Path) -> object:
        return json.loads(Path(path).read_text(encoding="utf-8"))

    def get_zone_at(self, camera_id: str) -> ZoneInfo | None:
        camera = self._cameras.get(camera_id)
        return self._zones.get(camera.zone_id) if camera else None

    def find_active_work_permits(
        self, zone_id: str, occurred_at: datetime
    ) -> list[WorkPermit]:
        return [
            permit
            for permit in self._permits
            if permit.zone_id == zone_id
            and permit.status is WorkPermitStatus.ACTIVE
            and permit.starts_at <= occurred_at <= permit.ends_at
        ]

    def get_task_ppe_matrix(self, task_code: str) -> TaskPpeMatrix | None:
        return self._matrices.get(task_code)

    def list_eligible_responsible_parties(
        self, zone_id: str
    ) -> list[ResponsibleParty]:
        return [
            party
            for party in self._parties
            if party.zone_id == zone_id and party.active
        ]

    def list_videos(self) -> list[VideoInfo]:
        return list(self._videos)

    def get_video(self, video_id: str) -> VideoInfo | None:
        return next((video for video in self._videos if video.video_id == video_id), None)
