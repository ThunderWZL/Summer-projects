from __future__ import annotations

import asyncio
from datetime import datetime

from app.adapters.database.seed import initialize_database
from app.adapters.database.session import (
    create_database_engine,
    create_session_factory,
)
from app.contracts import CaseSnapshot, CaseStatus
from app.domain.inmemory.fixture_candidates import build_fixture_candidate
from app.domain.video_analysis import AnalysisSession
from app.repositories import (
    SqlAlchemyAnalysisSessionStore,
    SqlAlchemyCaseStore,
)
from app.services.event_hub import EventHub
from app.services.session_manager import SessionManager


NOW = datetime.fromisoformat("2026-08-16T10:00:00+08:00")


def test_start_persists_session_before_runner_creates_case() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    session_store = SqlAlchemyAnalysisSessionStore(
        session_factory,
        clock=lambda: NOW,
    )
    case_store = SqlAlchemyCaseStore(session_factory)
    created_case: asyncio.Future[CaseSnapshot]

    async def stream(_session_id: str):
        yield b"frame"

    async def run(session: AnalysisSession, _manager: SessionManager) -> None:
        candidate = build_fixture_candidate("CAM-02", session.session_id)
        assert candidate is not None
        snapshot = CaseSnapshot(
            case_id=f"case-{session.session_id}",
            session_id=session.session_id,
            camera_id=candidate.camera_id,
            person_track_id=candidate.person_track_id,
            ppe_type=candidate.ppe_type,
            status=CaseStatus.YOLO_CANDIDATE,
            version=1,
            candidate=candidate,
            created_at=candidate.occurred_at,
            updated_at=candidate.occurred_at,
        )
        created_case.set_result(case_store.create(snapshot))

    async def scenario() -> CaseSnapshot:
        nonlocal created_case
        created_case = asyncio.get_running_loop().create_future()
        manager = SessionManager(
            EventHub(),
            lambda video_id: object() if video_id == "video-02" else None,
            stream,
            run,
            save_session=session_store.save,
        )
        await manager.start_session("video-02")
        return await asyncio.wait_for(created_case, timeout=1)

    try:
        persisted = asyncio.run(scenario())
        assert case_store.get(persisted.case_id) == persisted
    finally:
        engine.dispose()
