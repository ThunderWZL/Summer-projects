from __future__ import annotations

import argparse
from dataclasses import dataclass

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.adapters.database.models import (
    CameraModel,
    ResponsiblePartyModel,
    TaskPpeMatrixModel,
    UserModel,
    VideoModel,
    WorkPermitModel,
    ZoneModel,
)
from app.adapters.database.session import (
    create_database_engine,
    create_session_factory,
    initialize_schema,
    session_scope,
)
from app.domain.inmemory.actor_roles import DemoUserDirectory
from app.domain.inmemory.site_context import MemorySiteContext
from app.domain.site_context import CameraInfo


DEFAULT_DATABASE_URL = "sqlite:///./siteppe.db"
DEMO_ACTOR_IDS = ("officer-01", "reviewer-01")


@dataclass(frozen=True, slots=True)
class SeedReport:
    zones: int
    cameras: int
    videos: int
    work_permits: int
    task_ppe_matrices: int
    responsible_parties: int
    users: int


def seed_database(session: Session) -> SeedReport:
    context = MemorySiteContext()
    directory = DemoUserDirectory()
    videos = context.list_videos()

    zones = {}
    cameras = {}
    permits = {}
    matrices = {}
    parties = {}
    for video in videos:
        zone = context.get_zone_at(video.camera_id)
        if zone is None:
            raise ValueError(f"camera {video.camera_id} has no zone")
        zones[zone.zone_id] = zone
        cameras[video.camera_id] = CameraInfo(
            camera_id=video.camera_id,
            name=f"{zone.name.removesuffix('区')}机位",
            zone_id=zone.zone_id,
        )
        for permit in context.find_active_work_permits(
            zone.zone_id, video.scenario_started_at
        ):
            permits[permit.permit_id] = permit
            matrix = context.get_task_ppe_matrix(permit.task_code)
            if matrix is None:
                raise ValueError(f"permit {permit.permit_id} has no task matrix")
            matrices[matrix.task_code] = matrix
        for party in context.list_eligible_responsible_parties(zone.zone_id):
            parties[party.party_id] = party

    users = []
    for actor_id in DEMO_ACTOR_IDS:
        user = directory.get(actor_id)
        if user is None:
            raise ValueError(f"demo user {actor_id} is missing")
        users.append(user)

    for zone in zones.values():
        session.merge(
            ZoneModel(id=zone.zone_id, name=zone.name, zone_type=zone.zone_type)
        )
    session.flush()

    for camera in cameras.values():
        session.merge(
            CameraModel(
                id=camera.camera_id,
                name=camera.name,
                zone_id=camera.zone_id,
            )
        )
    for party in parties.values():
        session.merge(
            ResponsiblePartyModel(
                id=party.party_id,
                name=party.name,
                kind=party.kind,
                zone_id=party.zone_id,
                active=party.active,
            )
        )
    for matrix in matrices.values():
        session.merge(
            TaskPpeMatrixModel(
                task_code=matrix.task_code,
                hazards_json=list(matrix.hazards),
                required_ppe_json=[ppe.value for ppe in matrix.required_ppe],
                exception_note=matrix.exception_note,
                rectification_window_minutes=(
                    matrix.rectification_window_minutes
                ),
            )
        )
    for user in users:
        session.merge(
            UserModel(
                id=user.actor_id,
                name=user.name,
                role=user.role,
                active=user.active,
            )
        )
    session.flush()

    for video in videos:
        session.merge(
            VideoModel(
                id=video.video_id,
                camera_id=video.camera_id,
                title=video.title,
                local_path=video.local_path,
                source_url=video.source_url,
                duration_ms=video.duration_ms,
                scenario_started_at=video.scenario_started_at,
            )
        )
    for permit in permits.values():
        session.merge(
            WorkPermitModel(
                id=permit.permit_id,
                zone_id=permit.zone_id,
                task_code=permit.task_code,
                hazards_json=list(permit.hazards),
                responsible_party_id=permit.responsible_party_id,
                starts_at=permit.starts_at,
                ends_at=permit.ends_at,
                status=permit.status,
            )
        )
    session.flush()

    return SeedReport(
        zones=len(zones),
        cameras=len(cameras),
        videos=len(videos),
        work_permits=len(permits),
        task_ppe_matrices=len(matrices),
        responsible_parties=len(parties),
        users=len(users),
    )


def initialize_database(engine: Engine) -> SeedReport:
    initialize_schema(engine)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        return seed_database(session)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create the SitePPE SQLite schema and deterministic seed data."
    )
    parser.add_argument(
        "--database-url",
        default=DEFAULT_DATABASE_URL,
        help="SQLAlchemy database URL (default: sqlite:///./siteppe.db)",
    )
    args = parser.parse_args()
    engine = create_database_engine(args.database_url)
    report = initialize_database(engine)
    print(report)


if __name__ == "__main__":
    main()
