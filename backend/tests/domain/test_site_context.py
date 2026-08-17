from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.contracts import ActorRole, PpeType
from app.domain.inmemory.actor_roles import DemoUserDirectory
from app.domain.inmemory.site_context import MemorySiteContext
from app.domain.site_context import CameraInfo, TaskPpeMatrix, ZoneInfo

SCENARIO_TIME = datetime.fromisoformat("2026-08-07T10:00:00+08:00")


def make_context() -> MemorySiteContext:
    return MemorySiteContext()


def test_each_camera_maps_to_its_zone() -> None:
    context = make_context()

    zone = context.get_zone_at("CAM-02")

    assert zone is not None
    assert isinstance(zone, ZoneInfo)
    assert zone.zone_id == "zone-02"
    assert zone.zone_type == "CUTTING"


def test_camera_info_exposes_camera_name_and_zone() -> None:
    context = make_context()

    camera = context.get_zone_at("CAM-01")

    assert camera is not None
    assert camera.name
    assert camera.zone_id == "zone-01"


def test_unknown_camera_has_no_zone() -> None:
    context = make_context()

    assert context.get_zone_at("CAM-99") is None


def test_cam_01_zone_has_material_cutting_permit() -> None:
    context = make_context()

    permits = context.find_active_work_permits("zone-01", SCENARIO_TIME)

    assert [permit.task_code for permit in permits] == ["MATERIAL_CUTTING"]


def test_permit_is_found_only_within_its_window() -> None:
    context = make_context()

    inside = context.find_active_work_permits(
        "zone-02", datetime.fromisoformat("2026-08-07T10:00:00+08:00")
    )
    outside = context.find_active_work_permits(
        "zone-02", datetime.fromisoformat("2026-08-07T20:00:00+08:00")
    )

    assert [permit.permit_id for permit in inside] == ["wp-0201"]
    assert outside == []


def test_operational_tasks_require_the_three_available_ppe_types() -> None:
    context = make_context()

    for task_code in (
        "MATERIAL_CUTTING",
        "BOARD_FASTENING",
        "CLIMBING_WORK",
        "TIMBER_ASSEMBLY",
        "GENERAL_SITE_ACTIVITY",
    ):
        matrix = context.get_task_ppe_matrix(task_code)
        assert isinstance(matrix, TaskPpeMatrix)
        assert set(matrix.required_ppe) == {
            PpeType.HELMET,
            PpeType.GLOVES,
            PpeType.VEST,
        }


def test_matrix_uses_frozen_ppe_enum() -> None:
    context = make_context()

    cutting = context.get_task_ppe_matrix("MATERIAL_CUTTING")

    assert cutting is not None
    assert {ppe.value for ppe in cutting.required_ppe} == {
        "helmet",
        "gloves",
        "vest",
    }


def test_unknown_task_code_has_no_matrix() -> None:
    context = make_context()

    assert context.get_task_ppe_matrix("NO_SUCH_TASK") is None


@pytest.mark.parametrize("minutes", [0, -1])
def test_task_ppe_matrix_requires_positive_rectification_window(
    minutes: int,
) -> None:
    with pytest.raises(ValidationError):
        TaskPpeMatrix(
            task_code="BOARD_FASTENING",
            hazards=["手部伤害风险"],
            required_ppe=[PpeType.GLOVES],
            rectification_window_minutes=minutes,
        )


def test_default_video_inventory_matches_the_six_selected_clips() -> None:
    context = make_context()

    videos = context.list_videos()

    assert [
        (video.video_id, video.title, Path(video.local_path).name)
        for video in videos
    ] == [
        ("video-safe-01", "安全1｜切割物料｜防护齐全", "安全1.mp4"),
        ("video-no-vest-02", "无背心2｜切割物料", "无背心2.mp4"),
        ("video-no-gloves-01", "无手套1｜装订木板", "无手套1.mp4"),
        (
            "video-no-vest-gloves-02",
            "无背心无手套2｜攀爬作业",
            "无背心无手套2.mp4",
        ),
        (
            "video-no-ppe",
            "无头盔无手套无背心｜组装木料",
            "无头盔无手套无背心.mp4",
        ),
        ("video-mixed-wearing", "符合｜多人混合穿戴", "符合.mp4"),
    ]

    operational_ppe = {"helmet", "gloves", "vest"}
    for video in videos:
        zone = context.get_zone_at(video.camera_id)
        assert zone is not None
        permits = context.find_active_work_permits(zone.zone_id, SCENARIO_TIME)
        assert len(permits) == 1
        matrix = context.get_task_ppe_matrix(permits[0].task_code)
        assert matrix is not None
        assert {ppe.value for ppe in matrix.required_ppe} == operational_ppe


def test_get_video_returns_its_camera_and_scenario_time() -> None:
    context = make_context()

    video = context.get_video("video-safe-01")

    assert video is not None
    assert video.camera_id == "CAM-01"
    assert video.scenario_started_at.tzinfo is not None
    assert video.duration_ms > 0


def test_responsible_parties_are_filtered_by_zone() -> None:
    context = make_context()

    parties = context.list_eligible_responsible_parties("zone-02")

    assert [party.party_id for party in parties] == ["team-cutting-02"]
    assert parties[0].kind == "班组"


def test_user_directory_matches_actor_roles() -> None:
    directory = DemoUserDirectory()

    officer = directory.get("officer-01")
    reviewer = directory.get("reviewer-01")

    assert officer is not None
    assert officer.role is ActorRole.SITE_SAFETY_OFFICER
    assert reviewer is not None
    assert reviewer.role is ActorRole.PROJECT_SAFETY_REVIEWER
    assert directory.role_for("officer-01") is ActorRole.SITE_SAFETY_OFFICER
    assert directory.role_for("reviewer-01") is ActorRole.PROJECT_SAFETY_REVIEWER
    assert directory.role_for("nobody-01") is None
    assert directory.get("nobody-01") is None


def test_camera_info_is_a_strict_shared_value_model() -> None:
    camera = CameraInfo(camera_id="CAM-01", name="测试", zone_id="zone-01")

    assert camera.zone_id == "zone-01"
