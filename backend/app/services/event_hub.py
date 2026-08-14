from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from uuid import uuid4

from app.contracts import AnalysisEvent, AnalysisEventPayload, AnalysisEventType


class EventHub:
    """Best-effort, live-only event fan-out scoped to an analysis session."""

    def __init__(self) -> None:
        self._sequences: dict[str, int] = defaultdict(int)
        self._subscribers: dict[str, set[asyncio.Queue[AnalysisEvent]]] = defaultdict(set)

    async def publish(
        self,
        session_id: str,
        event_type: AnalysisEventType,
        payload: AnalysisEventPayload,
        *,
        case_id: str | None = None,
        playback_ms: int = 0,
    ) -> AnalysisEvent:
        self._sequences[session_id] += 1
        event = AnalysisEvent(
            event_id=f"analysis-event-{uuid4().hex}",
            sequence=self._sequences[session_id],
            event_type=event_type,
            session_id=session_id,
            occurred_at=datetime.now(timezone.utc),
            case_id=case_id,
            playback_ms=playback_ms,
            payload=payload,
        )
        for queue in tuple(self._subscribers[session_id]):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                continue
        return event

    def subscribe(self, session_id: str) -> AsyncIterator[AnalysisEvent]:
        queue: asyncio.Queue[AnalysisEvent] = asyncio.Queue(maxsize=100)
        self._subscribers[session_id].add(queue)

        async def events() -> AsyncIterator[AnalysisEvent]:
            try:
                while True:
                    yield await queue.get()
            finally:
                subscribers = self._subscribers.get(session_id)
                if subscribers is not None:
                    subscribers.discard(queue)
                    if not subscribers:
                        self._subscribers.pop(session_id, None)

        return events()
