import asyncio

from app.contracts import AnalysisEvent, AnalysisStage, SessionProgressPayload
from app.services.event_hub import EventHub


def _progress(stage: AnalysisStage = AnalysisStage.INFERENCING) -> SessionProgressPayload:
    return SessionProgressPayload(
        stage=stage,
        progress=0.5,
        message=None,
        inference_fps=12.0,
        candidate_count=0,
        case_count=0,
    )


async def _start_receive(iterator) -> asyncio.Task[AnalysisEvent]:
    task = asyncio.create_task(anext(iterator))
    await asyncio.wait({task}, timeout=0)
    return task


def test_sequences_are_strictly_increasing_and_scoped_per_session() -> None:
    async def scenario() -> tuple[list[int], list[int]]:
        hub = EventHub()
        first = [
            await hub.publish("session-01", "SESSION_PROGRESS", _progress()),
            await hub.publish("session-01", "SESSION_PROGRESS", _progress()),
        ]
        second = [
            await hub.publish("session-02", "SESSION_PROGRESS", _progress()),
            await hub.publish("session-02", "SESSION_PROGRESS", _progress()),
        ]
        return [event.sequence for event in first], [event.sequence for event in second]

    first, second = asyncio.run(scenario())

    assert first == [1, 2]
    assert second == [1, 2]


def test_each_subscriber_independently_receives_new_events() -> None:
    async def scenario() -> tuple[AnalysisEvent, AnalysisEvent]:
        hub = EventHub()
        left = hub.subscribe("session-01")
        right = hub.subscribe("session-01")
        left_receive = await _start_receive(left)
        right_receive = await _start_receive(right)

        published = await hub.publish("session-01", "SESSION_PROGRESS", _progress())
        received = await asyncio.gather(left_receive, right_receive)
        await left.aclose()
        await right.aclose()
        assert received[0].event_id == published.event_id
        assert received[1].event_id == published.event_id
        return received[0], received[1]

    left, right = asyncio.run(scenario())

    assert left.model_dump() == right.model_dump()


def test_subscription_is_live_only_and_does_not_replay_old_events() -> None:
    async def scenario() -> AnalysisEvent:
        hub = EventHub()
        await hub.publish("session-01", "SESSION_PROGRESS", _progress())
        events = hub.subscribe("session-01")
        receive = await _start_receive(events)

        await hub.publish(
            "session-01",
            "SESSION_PROGRESS",
            _progress(AnalysisStage.STOPPING),
        )
        event = await receive
        await events.aclose()
        return event

    event = asyncio.run(scenario())

    assert event.sequence == 2
    assert event.payload.stage is AnalysisStage.STOPPING


def test_cancelled_subscription_does_not_break_later_publish_or_subscribe() -> None:
    async def scenario() -> AnalysisEvent:
        hub = EventHub()
        disconnected = hub.subscribe("session-01")
        pending = await _start_receive(disconnected)
        pending.cancel()
        try:
            await pending
        except asyncio.CancelledError:
            pass

        await hub.publish("session-01", "SESSION_PROGRESS", _progress())
        connected = hub.subscribe("session-01")
        receive = await _start_receive(connected)
        await hub.publish(
            "session-01",
            "SESSION_PROGRESS",
            _progress(AnalysisStage.STOPPING),
        )
        event = await receive
        await connected.aclose()
        return event

    event = asyncio.run(scenario())

    assert event.sequence == 2
    assert event.payload.stage is AnalysisStage.STOPPING
