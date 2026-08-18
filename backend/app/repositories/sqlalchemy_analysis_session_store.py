from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.adapters.database.models import AnalysisSessionModel
from app.adapters.database.session import session_scope
from app.domain.video_analysis import AnalysisSession


class SqlAlchemyAnalysisSessionStore:
    """Persist analysis-session identity before cases reference it."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
    ) -> None:
        self._session_factory = session_factory

    def save(
        self,
        analysis_session: AnalysisSession,
        playback_ms: int = 0,
    ) -> None:
        with session_scope(self._session_factory) as database_session:
            record = database_session.get(
                AnalysisSessionModel,
                analysis_session.session_id,
            )
            if record is None:
                database_session.add(
                    AnalysisSessionModel(
                        id=analysis_session.session_id,
                        video_id=analysis_session.video_id,
                        status=analysis_session.stage,
                        started_at=analysis_session.started_at,
                        playback_ms=playback_ms,
                    )
                )
                return
            if record.video_id != analysis_session.video_id:
                raise ValueError(
                    "analysis session video_id cannot change after creation"
                )
            record.status = analysis_session.stage
            record.playback_ms = playback_ms
