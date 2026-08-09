from datetime import datetime

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


def test_cam_01_zone_has_no_active_permit() -> None:
    context = make_context()

    permits = context.find_active_work_permits("zone-01", SCENARIO_TIME)

    assert permits == []


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


def test_cam_04_and_cam_03_gloves_matrix_differ() -> None:
    context = make_context()

    rebar = context.get_task_ppe_matrix("HANDLING_REBAR")
    rotating = context.get_task_ppe_matrix("ROTATING_EQUIPMENT_OPERATION")

    assert rebar is not None
    assert rotating is not None
    assert PpeType.GLOVES in rebar.required_ppe
    assert PpeType.GLOVES not in rotating.required_ppe
    assert rotating.exception_note
    assert isinstance(rebar, TaskPpeMatrix)


def test_matrix_uses_frozen_ppe_enum() -> None:
    context = make_context()

    cutting = context.get_task_ppe_matrix("HOT_WORK_CUTTING")

    assert cutting is not None
    assert {ppe.value for ppe in cutting.required_ppe} == {
        "goggles",
        "helmet",
    }


def test_unknown_task_code_has_no_matrix() -> None:
    context = make_context()

    assert context.get_task_ppe_matrix("NO_SUCH_TASK") is None


def test_list_videos_returns_six_channels() -> None:
    context = make_context()

    videos = context.list_videos()

    assert [video.video_id for video in videos] == [
        "video-01",
        "video-02",
        "video-03",
        "video-04",
        "video-05",
        "video-06",
    ]


def test_get_video_returns_its_camera_and_scenario_time() -> None:
    context = make_context()

    video = context.get_video("video-01")

    assert video is not None
    assert video.camera_id == "CAM-01"
    assert video.scenario_started_at.tzinfo is not None
    assert video.duration_ms > 0


def test_responsible_parties_are_filtered_by_zone() -> None:
    context = make_context()

    parties = context.list_eligible_responsible_parties("zone-02")

    assert [party.party_id for party in parties] == ["team-electric-01"]
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
