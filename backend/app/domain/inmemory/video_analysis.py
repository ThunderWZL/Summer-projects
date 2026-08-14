from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from app.contracts import AnalysisStage, CandidateCreatedPayload
from app.domain.case_store import CaseQuery, CaseStorePort
from app.domain.site_context import SiteContextPort
from app.domain.video_analysis import AnalysisSession
from app.modules.video_analysis.observation import SUPPORTED_PPE
from app.services.session_manager import SessionManager


_JPEG = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    b"\xff\xdb\x00C\x00" + b"\x08" * 64
    + b"\xff\xc0\x00\x11\x08\x00\x01\x00\x01\x03\x01\x11\x00\x02\x11\x00\x03\x11\x00"
    + b"\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x08"
    + b"\xff\xda\x00\x0c\x03\x01\x00\x02\x11\x03\x11\x00\x3f\x00\x00\xff\xd9"
)


class InMemoryVideoAnalysis:
    """Deterministic demo analysis that reads fixtures without changing them."""

    def __init__(self, context: SiteContextPort, cases: CaseStorePort) -> None:
        self._context = context
        self._cases = cases

    async def get_stream(self, session_id: str) -> AsyncIterator[bytes]:
        del session_id
        yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + _JPEG + b"\r\n"
        yield b"--frame--\r\n"

    async def run_session(
        self, session: AnalysisSession, manager: SessionManager
    ) -> None:
        await asyncio.sleep(0.01)
        video = self._context.get_video(session.video_id)
        if video is None:
            return
        await manager.publish_progress(
            session.session_id,
            stage=AnalysisStage.STARTING,
            progress=0.0,
            message="analysis session started",
        )
        await manager.publish_progress(
            session.session_id,
            stage=AnalysisStage.READING,
            progress=0.25,
            message="reading demo video",
        )
        await manager.publish_progress(
            session.session_id,
            stage=AnalysisStage.INFERENCING,
            progress=0.75,
            message="running deterministic demo inference",
            inference_fps=12.0,
        )
        case = next(
            (
                item
                for item in self._cases.list(CaseQuery(page_size=1_000_000)).items
                if item.camera_id == video.camera_id
                and item.ppe_type in SUPPORTED_PPE
            ),
            None,
        )
        if case is not None:
            candidate = case.candidate
            await manager.publish_candidate(
                session.session_id,
                case_id=case.case_id,
                payload=CandidateCreatedPayload(
                    candidate_id=candidate.candidate_id,
                    ppe_type=candidate.ppe_type,
                    confidence=candidate.confidence,
                    candidate_occurred_at=candidate.occurred_at,
                    person_track_id=candidate.person_track_id,
                ),
                playback_ms=candidate.last_seen_ms,
            )
        await manager.finish_session(
            session.session_id,
            candidate_count=1 if case is not None else 0,
            case_count=1 if case is not None else 0,
        )
