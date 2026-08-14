from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from app.contracts import (
    AnalysisStage,
    CandidateCreatedPayload,
    CaseStatus,
    CaseUpdatedPayload,
    VlmReviewedPayload,
)
from app.domain.inmemory.fixture_candidates import candidate_for_video
from app.domain.site_context import SiteContextPort
from app.domain.video_analysis import AnalysisSession
from app.services.session_manager import SessionManager
from app.services.case_pipeline import CasePipeline


_JPEG = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    b"\xff\xdb\x00C\x00" + b"\x08" * 64
    + b"\xff\xc0\x00\x11\x08\x00\x01\x00\x01\x03\x01\x11\x00\x02\x11\x00\x03\x11\x00"
    + b"\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x08"
    + b"\xff\xda\x00\x0c\x03\x01\x00\x02\x11\x03\x11\x00\x3f\x00\x00\xff\xd9"
)

_PIPELINE_ACTIONS = {
    CaseStatus.INVESTIGATING: "START_INVESTIGATION",
    CaseStatus.NEEDS_HUMAN_FACTS: "RECORD_INVESTIGATION",
    CaseStatus.PENDING_REVIEW: "RECORD_INVESTIGATION",
}


class InMemoryVideoAnalysis:
    """Deterministic demo analysis that feeds fixtures through the case pipeline."""

    def __init__(
        self,
        context: SiteContextPort,
        pipeline: CasePipeline,
    ) -> None:
        self._context = context
        self._pipeline = pipeline

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
        candidate = candidate_for_video(video, session.session_id)
        if candidate is not None:
            case = self._pipeline.ensure_case(candidate)
            is_new_candidate = (
                case.status is CaseStatus.YOLO_CANDIDATE and not case.transitions
            )
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
            result = await self._pipeline.process_candidate(candidate)
            if is_new_candidate and result.vlm_review is not None:
                await manager.publish_vlm_reviewed(
                    session.session_id,
                    case_id=result.case_id,
                    payload=VlmReviewedPayload(
                        verdict=result.vlm_review.verdict,
                        evidence_sufficient=result.vlm_review.evidence_sufficient,
                        reason=result.vlm_review.reason,
                        status=result.transitions[0].to_status,
                        version=2,
                    ),
                    playback_ms=candidate.last_seen_ms,
                )
                for version, transition in enumerate(result.transitions[1:], start=3):
                    await manager.publish_case_updated(
                        session.session_id,
                        case_id=result.case_id,
                        payload=CaseUpdatedPayload(
                            status=transition.to_status,
                            version=version,
                            updated_at=transition.occurred_at,
                            action=_PIPELINE_ACTIONS[transition.to_status],
                        ),
                        playback_ms=candidate.last_seen_ms,
                    )
        case_count = 1 if candidate is not None else 0
        await manager.finish_session(
            session.session_id,
            candidate_count=case_count,
            case_count=case_count,
        )
