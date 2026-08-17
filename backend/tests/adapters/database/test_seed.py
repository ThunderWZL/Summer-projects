from datetime import datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.adapters.database import seed as seed_module
from app.adapters.database.models import (
    CameraModel,
    ResponsiblePartyModel,
    TaskPpeMatrixModel,
    UserModel,
    VideoModel,
    WorkPermitModel,
    ZoneModel,
)
from app.adapters.database.seed import initialize_database, seed_database
from app.adapters.database.session import (
    create_database_engine,
    create_session_factory,
)
from app.contracts import ActorRole
from app.domain.inmemory.actor_roles import DemoUserDirectory
from app.domain.inmemory.site_context import MemorySiteContext
from app.domain.site_context import WorkPermitStatus


def make_seeded_session(tmp_path):
    database_path = tmp_path / "siteppe-test.db"
    engine = create_database_engine(f"sqlite:///{database_path.as_posix()}")
    report = initialize_database(engine)
    return engine, create_session_factory(engine), report


def test_seed_creates_the_six_deterministic_channels(tmp_path) -> None:
    engine, session_factory, report = make_seeded_session(tmp_path)

    assert report.zones == 6
    assert report.cameras == 6
    assert report.videos == 6
    assert report.work_permits == 6
    assert report.task_ppe_matrices == 5
    assert report.responsible_parties == 6
    assert report.users == 2

    with session_factory() as session:
        cameras = session.scalars(
            select(CameraModel).order_by(CameraModel.id)
        ).all()
        videos = session.scalars(
            select(VideoModel).order_by(VideoModel.id)
        ).all()

    assert [(camera.id, camera.zone_id) for camera in cameras] == [
        (f"CAM-0{index}", f"zone-0{index}") for index in range(1, 7)
    ]
    assert {video.id for video in videos} == {
        "video-safe-01",
        "video-no-vest-02",
        "video-no-gloves-01",
        "video-no-vest-gloves-02",
        "video-no-ppe",
        "video-mixed-wearing",
    }
    assert all(video.duration_ms == 600_000 for video in videos)
    assert all(video.scenario_started_at.tzinfo is not None for video in videos)
    engine.dispose()


def test_seed_preserves_the_recomposed_ppe_rules(tmp_path) -> None:
    engine, session_factory, _ = make_seeded_session(tmp_path)

    with session_factory() as session:
        zone_01_permits = session.scalars(
            select(WorkPermitModel).where(WorkPermitModel.zone_id == "zone-01")
        ).all()
        cutting = session.get(TaskPpeMatrixModel, "MATERIAL_CUTTING")
        climbing = session.get(TaskPpeMatrixModel, "CLIMBING_WORK")

    assert [permit.task_code for permit in zone_01_permits] == [
        "MATERIAL_CUTTING"
    ]
    assert cutting is not None
    assert set(cutting.required_ppe_json) == {"helmet", "gloves", "vest"}
    assert climbing is not None
    assert set(climbing.required_ppe_json) == {"helmet", "gloves", "vest"}
    assert climbing.exception_note == (
        "视频中的其他穿戴不计作高可视安全背心"
    )
    engine.dispose()


def test_seed_uses_closed_active_permit_windows_and_frozen_users(tmp_path) -> None:
    engine, session_factory, _ = make_seeded_session(tmp_path)
    boundary_start = datetime.fromisoformat("2026-08-07T08:00:00+08:00")
    boundary_end = datetime.fromisoformat("2026-08-07T18:00:00+08:00")

    with session_factory() as session:
        permit = session.get(WorkPermitModel, "wp-0201")
        officer = session.get(UserModel, "officer-01")
        reviewer = session.get(UserModel, "reviewer-01")

    assert permit is not None
    assert permit.status is WorkPermitStatus.ACTIVE
    assert permit.starts_at == boundary_start
    assert permit.ends_at == boundary_end
    assert permit.starts_at <= boundary_start <= permit.ends_at
    assert permit.starts_at <= boundary_end <= permit.ends_at
    assert officer is not None
    assert officer.role is ActorRole.SITE_SAFETY_OFFICER
    assert reviewer is not None
    assert reviewer.role is ActorRole.PROJECT_SAFETY_REVIEWER
    engine.dispose()


def test_seed_is_idempotent(tmp_path) -> None:
    engine, session_factory, _ = make_seeded_session(tmp_path)

    second_report = initialize_database(engine)

    with session_factory() as session:
        counts = {
            model.__tablename__: session.scalar(
                select(func.count()).select_from(model)
            )
            for model in (
                ZoneModel,
                CameraModel,
                VideoModel,
                WorkPermitModel,
                TaskPpeMatrixModel,
                ResponsiblePartyModel,
                UserModel,
            )
        }

    assert second_report.zones == 6
    assert counts == {
        "zones": 6,
        "cameras": 6,
        "videos": 6,
        "work_permits": 6,
        "task_ppe_matrix": 5,
        "responsible_parties": 6,
        "users": 2,
    }
    engine.dispose()


def test_seed_rejects_a_video_without_a_zone(monkeypatch) -> None:
    class MissingZoneContext(MemorySiteContext):
        def get_zone_at(self, camera_id: str):
            return None

    monkeypatch.setattr(seed_module, "MemorySiteContext", MissingZoneContext)

    with Session() as session:
        with pytest.raises(ValueError, match="CAM-01 has no zone"):
            seed_database(session)


def test_seed_rejects_a_permit_without_a_task_matrix(monkeypatch) -> None:
    class MissingMatrixContext(MemorySiteContext):
        def get_task_ppe_matrix(self, task_code: str):
            return None

    monkeypatch.setattr(seed_module, "MemorySiteContext", MissingMatrixContext)

    with Session() as session:
        with pytest.raises(ValueError, match="wp-0101 has no task matrix"):
            seed_database(session)


def test_seed_rejects_a_missing_frozen_demo_user(monkeypatch) -> None:
    class MissingUserDirectory(DemoUserDirectory):
        def get(self, actor_id: str):
            if actor_id == "officer-01":
                return None
            return super().get(actor_id)

    monkeypatch.setattr(
        seed_module, "DemoUserDirectory", MissingUserDirectory
    )

    with Session() as session:
        with pytest.raises(ValueError, match="demo user officer-01 is missing"):
            seed_database(session)
