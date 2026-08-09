from __future__ import annotations

from datetime import datetime

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

SCENARIO_STARTED_AT = datetime.fromisoformat("2026-08-07T09:00:00+08:00")


class MemorySiteContext:
    """按设计文档 §8.1 六路通道种子化的内存业务上下文。

    六路不是六个独立产品流程，而是演示 Agent 会根据业务上下文给出不同
    调查结论：CAM-04 旋转设备与 CAM-03 搬运钢筋对手套的矩阵结论必须不同。
    关键业务事实全部由这里确定性产出，禁止运行时随机生成。
    """

    def __init__(self) -> None:
        self._zones = {
            "zone-01": ZoneInfo(
                zone_id="zone-01", name="脚手架区", zone_type="SCAFFOLD"
            ),
            "zone-02": ZoneInfo(
                zone_id="zone-02", name="切割区", zone_type="CUTTING"
            ),
            "zone-03": ZoneInfo(
                zone_id="zone-03", name="钢筋区", zone_type="REBAR"
            ),
            "zone-04": ZoneInfo(
                zone_id="zone-04",
                name="旋转设备区",
                zone_type="ROTATING_EQUIPMENT",
            ),
            "zone-05": ZoneInfo(
                zone_id="zone-05", name="车辆作业区", zone_type="VEHICLE"
            ),
            "zone-06": ZoneInfo(
                zone_id="zone-06", name="普通作业区", zone_type="GENERAL"
            ),
        }
        self._cameras = {
            "CAM-01": CameraInfo(
                camera_id="CAM-01", name="脚手架机位", zone_id="zone-01"
            ),
            "CAM-02": CameraInfo(
                camera_id="CAM-02", name="切割机位", zone_id="zone-02"
            ),
            "CAM-03": CameraInfo(
                camera_id="CAM-03", name="钢筋机位", zone_id="zone-03"
            ),
            "CAM-04": CameraInfo(
                camera_id="CAM-04", name="旋转设备机位", zone_id="zone-04"
            ),
            "CAM-05": CameraInfo(
                camera_id="CAM-05", name="车辆作业机位", zone_id="zone-05"
            ),
            "CAM-06": CameraInfo(
                camera_id="CAM-06", name="普通作业机位", zone_id="zone-06"
            ),
        }
        self._videos = [
            VideoInfo(
                video_id=f"video-0{index}",
                camera_id=camera_id,
                title=title,
                local_path=f"/data/demo/{camera_id.lower()}.mp4",
                source_url=None,
                duration_ms=600_000,
                scenario_started_at=SCENARIO_STARTED_AT,
            )
            for index, (camera_id, title) in enumerate(
                [
                    ("CAM-01", "脚手架区"),
                    ("CAM-02", "切割区"),
                    ("CAM-03", "钢筋区"),
                    ("CAM-04", "旋转设备区"),
                    ("CAM-05", "车辆作业区"),
                    ("CAM-06", "普通作业区"),
                ],
                start=1,
            )
        ]
        self._permits = [
            WorkPermit(
                permit_id="wp-0201",
                zone_id="zone-02",
                task_code="HOT_WORK_CUTTING",
                hazards=["飞溅", "强光"],
                responsible_party_id="team-electric-01",
                starts_at=datetime.fromisoformat("2026-08-07T08:00:00+08:00"),
                ends_at=datetime.fromisoformat("2026-08-07T18:00:00+08:00"),
            ),
            WorkPermit(
                permit_id="wp-0301",
                zone_id="zone-03",
                task_code="HANDLING_REBAR",
                hazards=["手部伤害风险"],
                responsible_party_id="team-structure-01",
                starts_at=datetime.fromisoformat("2026-08-07T08:00:00+08:00"),
                ends_at=datetime.fromisoformat("2026-08-07T18:00:00+08:00"),
            ),
            WorkPermit(
                permit_id="wp-0401",
                zone_id="zone-04",
                task_code="ROTATING_EQUIPMENT_OPERATION",
                hazards=["卷入风险"],
                responsible_party_id="team-mechanical-01",
                starts_at=datetime.fromisoformat("2026-08-07T08:00:00+08:00"),
                ends_at=datetime.fromisoformat("2026-08-07T18:00:00+08:00"),
            ),
            WorkPermit(
                permit_id="wp-0501",
                zone_id="zone-05",
                task_code="VEHICLE_ZONE_OPERATION",
                hazards=["车辆碰撞"],
                responsible_party_id="team-logistics-01",
                starts_at=datetime.fromisoformat("2026-08-07T08:00:00+08:00"),
                ends_at=datetime.fromisoformat("2026-08-07T18:00:00+08:00"),
            ),
            WorkPermit(
                permit_id="wp-0601",
                zone_id="zone-06",
                task_code="GENERAL_DUTY",
                hazards=[],
                responsible_party_id="team-general-01",
                starts_at=datetime.fromisoformat("2026-08-07T08:00:00+08:00"),
                ends_at=datetime.fromisoformat("2026-08-07T18:00:00+08:00"),
            ),
            # zone-01（CAM-01）故意没有许可，用于“区域无有效许可 → 请求人工补充事实”。
        ]
        self._matrices = {
            "HOT_WORK_CUTTING": TaskPpeMatrix(
                task_code="HOT_WORK_CUTTING",
                hazards=["飞溅", "强光"],
                required_ppe=[PpeType.GOGGLES, PpeType.HELMET],
                rectification_window_minutes=60,
            ),
            "HANDLING_REBAR": TaskPpeMatrix(
                task_code="HANDLING_REBAR",
                hazards=["手部伤害风险"],
                required_ppe=[PpeType.GLOVES],
                rectification_window_minutes=30,
            ),
            "ROTATING_EQUIPMENT_OPERATION": TaskPpeMatrix(
                task_code="ROTATING_EQUIPMENT_OPERATION",
                hazards=["卷入风险"],
                required_ppe=[PpeType.HELMET],
                exception_note="旋转设备旁不宜简单要求佩戴手套，应评估卷入风险并采取防卷入措施",
                rectification_window_minutes=60,
            ),
            "VEHICLE_ZONE_OPERATION": TaskPpeMatrix(
                task_code="VEHICLE_ZONE_OPERATION",
                hazards=["车辆碰撞"],
                required_ppe=[PpeType.VEST],
                rectification_window_minutes=30,
            ),
            "GENERAL_DUTY": TaskPpeMatrix(
                task_code="GENERAL_DUTY",
                hazards=[],
                required_ppe=[],
                exception_note="普通作业无额外防护要求",
                rectification_window_minutes=60,
            ),
        }
        self._parties = [
            ResponsibleParty(
                party_id="team-scaffold-01",
                name="架子班组",
                kind="班组",
                zone_id="zone-01",
            ),
            ResponsibleParty(
                party_id="team-electric-01",
                name="电气班组",
                kind="班组",
                zone_id="zone-02",
            ),
            ResponsibleParty(
                party_id="team-structure-01",
                name="结构班组",
                kind="班组",
                zone_id="zone-03",
            ),
            ResponsibleParty(
                party_id="team-mechanical-01",
                name="机械班组",
                kind="班组",
                zone_id="zone-04",
            ),
            ResponsibleParty(
                party_id="team-logistics-01",
                name="物流班组",
                kind="班组",
                zone_id="zone-05",
            ),
            ResponsibleParty(
                party_id="team-general-01",
                name="综合班组",
                kind="班组",
                zone_id="zone-06",
            ),
        ]

    def get_zone_at(self, camera_id: str) -> ZoneInfo | None:
        camera = self._cameras.get(camera_id)
        if camera is None:
            return None
        return self._zones.get(camera.zone_id)

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
        return next(
            (video for video in self._videos if video.video_id == video_id),
            None,
        )
