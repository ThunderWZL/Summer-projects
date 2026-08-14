from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_video_analysis_port
from app.api.errors import error_response
from app.api.schemas import AnalysisSessionResponse, StartAnalysisSessionRequest
from app.domain.video_analysis import (
    AnalysisSession,
    AnalysisSessionNotActive,
    AnalysisSessionNotFound,
    AnalysisVideoNotFound,
    VideoAnalysisPort,
)


router = APIRouter(prefix="/api/v1/analysis-sessions", tags=["analysis-sessions"])


def _response(session: AnalysisSession) -> AnalysisSessionResponse:
    return AnalysisSessionResponse(
        session_id=session.session_id,
        video_id=session.video_id,
        stage=session.stage,
        stream_url=f"/api/v1/analysis-sessions/{session.session_id}/stream.mjpg",
        events_url=f"/ws/v1/analysis-sessions/{session.session_id}/events",
    )


@router.post("", response_model=AnalysisSessionResponse, status_code=201)
async def start_analysis_session(
    request: StartAnalysisSessionRequest,
    analysis: VideoAnalysisPort = Depends(get_video_analysis_port),
) -> AnalysisSessionResponse:
    try:
        return _response(await analysis.start_session(request.video_id))
    except AnalysisVideoNotFound as error:
        return error_response(404, error.code, str(error))


@router.post("/{session_id}/stop", response_model=AnalysisSessionResponse)
async def stop_analysis_session(
    session_id: str,
    analysis: VideoAnalysisPort = Depends(get_video_analysis_port),
) -> AnalysisSessionResponse:
    try:
        return _response(await analysis.stop_session(session_id))
    except AnalysisSessionNotFound as error:
        return error_response(404, error.code, str(error))


@router.get("/{session_id}/stream.mjpg")
async def analysis_stream(
    session_id: str,
    analysis: VideoAnalysisPort = Depends(get_video_analysis_port),
) -> StreamingResponse:
    try:
        stream = analysis.get_stream(session_id)
        return StreamingResponse(
            stream,
            media_type="multipart/x-mixed-replace; boundary=frame",
        )
    except AnalysisSessionNotFound as error:
        return error_response(404, error.code, str(error))
    except AnalysisSessionNotActive as error:
        return error_response(409, error.code, str(error))
