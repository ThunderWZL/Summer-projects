from collections.abc import AsyncIterator
from datetime import datetime

import asyncio
from starlette.websockets import WebSocketDisconnect

from app.api.ws import analysis_session_events
from app.contracts import AnalysisEvent, CandidateCreatedPayload
from app.domain.video_analysis import (
    AnalysisSession,
    AnalysisSessionNotFound,
)


class ScriptedVideoAnalysis:
    def __init__(self) -> None:
        self.disconnected = False

    async def start_session(self, video_id: str) -> AnalysisSession:
        raise NotImplementedError

    async def get_stream(self, session_id: str) -> AsyncIterator[bytes]:
        raise NotImplementedError
        yield b""

    async def stop_session(self, session_id: str) -> AnalysisSession:
        raise NotImplementedError

    def subscribe_events(self, session_id: str) -> AsyncIterator[AnalysisEvent]:
        if session_id != "session-01":
            raise AnalysisSessionNotFound(session_id)

        async def events() -> AsyncIterator[AnalysisEvent]:
            try:
                yield AnalysisEvent(
                    event_id="event-01",
                    sequence=1,
                    event_type="CANDIDATE_CREATED",
                    session_id=session_id,
                    occurred_at=datetime.fromisoformat(
                        "2026-08-07T10:31:24+08:00"
                    ),
                    case_id="case-01",
                    playback_ms=1500,
                    payload=CandidateCreatedPayload(
                        candidate_id="candidate-case-01",
                        ppe_type="helmet",
                        confidence=0.91,
                        candidate_occurred_at=datetime.fromisoformat(
                            "2026-08-07T10:31:24+08:00"
                        ),
                        person_track_id="track-case-01",
                    ),
                )
            finally:
                self.disconnected = True

        return events()


def test_websocket_sends_a_valid_analysis_event_summary() -> None:
    class RecordingWebSocket:
        def __init__(self) -> None:
            self.accepted = False
            self.events: list[dict] = []

        async def accept(self) -> None:
            self.accepted = True

        async def send_json(self, event: dict) -> None:
            self.events.append(event)
            raise WebSocketDisconnect(code=1000)

        async def receive(self) -> dict:
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

        async def close(self, code: int) -> None:
            raise AssertionError(f"unexpected close: {code}")

    analysis = ScriptedVideoAnalysis()
    websocket = RecordingWebSocket()

    asyncio.run(
        analysis_session_events(
            websocket,  # type: ignore[arg-type]
            "session-01",
            analysis,
        )
    )
    event = websocket.events[0]

    assert websocket.accepted is True
    assert event["sequence"] == 1
    assert event["session_id"] == "session-01"
    assert event["case_id"] == "case-01"
    assert event["event_type"] == "CANDIDATE_CREATED"
    assert set(event["payload"]) == {
        "candidate_id",
        "ppe_type",
        "confidence",
        "candidate_occurred_at",
        "person_track_id",
    }
    assert "frames" not in event["payload"]
    assert "local_path" not in str(event)
    assert analysis.disconnected is True


def test_unknown_websocket_session_closes_with_policy_violation() -> None:
    class ClosingWebSocket:
        def __init__(self) -> None:
            self.accepted = False
            self.close_code: int | None = None

        async def accept(self) -> None:
            self.accepted = True

        async def send_json(self, _event: dict) -> None:
            raise AssertionError("unknown session must not send an event")

        async def receive(self) -> dict:
            raise AssertionError("unknown session must close before receiving")

        async def close(self, code: int) -> None:
            self.close_code = code

    analysis = ScriptedVideoAnalysis()
    websocket = ClosingWebSocket()

    asyncio.run(
        analysis_session_events(
            websocket,  # type: ignore[arg-type]
            "session-99",
            analysis,
        )
    )

    assert websocket.accepted is True
    assert websocket.close_code == 1008
