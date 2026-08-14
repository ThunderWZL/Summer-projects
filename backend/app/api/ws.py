import asyncio
from contextlib import suppress

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.api.deps import get_video_analysis_port
from app.domain.video_analysis import AnalysisSessionNotFound, VideoAnalysisPort


router = APIRouter()


async def _wait_for_disconnect(websocket: WebSocket) -> None:
    while True:
        message = await websocket.receive()
        if message["type"] == "websocket.disconnect":
            return


@router.websocket("/ws/v1/analysis-sessions/{session_id}/events")
async def analysis_session_events(
    websocket: WebSocket,
    session_id: str,
    analysis: VideoAnalysisPort = Depends(get_video_analysis_port),
) -> None:
    await websocket.accept()
    try:
        events = analysis.subscribe_events(session_id)
    except AnalysisSessionNotFound:
        await websocket.close(code=1008)
        return

    disconnect = asyncio.create_task(_wait_for_disconnect(websocket))
    try:
        while True:
            next_event = asyncio.create_task(anext(events))
            done, _ = await asyncio.wait(
                {disconnect, next_event},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if disconnect in done:
                next_event.cancel()
                with suppress(asyncio.CancelledError):
                    await next_event
                return
            try:
                event = next_event.result()
            except StopAsyncIteration:
                return
            await websocket.send_json(event.model_dump(mode="json"))
    except WebSocketDisconnect:
        return
    except Exception:
        # WebSocket delivery is best-effort and must not affect case workflows.
        return
    finally:
        disconnect.cancel()
        with suppress(asyncio.CancelledError):
            await disconnect
        await events.aclose()
