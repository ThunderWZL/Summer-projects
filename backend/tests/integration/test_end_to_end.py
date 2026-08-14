from __future__ import annotations

import asyncio
from datetime import datetime

from httpx import ASGITransport, AsyncClient

from app.api.deps import (
    get_case_pipeline,
    get_case_store,
    get_clock,
    get_event_hub,
    get_inmemory_video_analysis,
    get_investigation_port,
    get_session_manager,
)
from app.main import app


NOW = datetime.fromisoformat("2026-08-15T10:00:00+08:00")


def setup_function() -> None:
    for dependency in (
        get_session_manager,
        get_inmemory_video_analysis,
        get_event_hub,
        get_case_pipeline,
        get_investigation_port,
        get_case_store,
    ):
        dependency.cache_clear()
    app.dependency_overrides[get_clock] = lambda: lambda: NOW


def teardown_function() -> None:
    app.dependency_overrides.pop(get_clock, None)


async def request(method: str, path: str, payload: dict | None = None):
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        return await client.request(method, path, json=payload)


async def analyze(video_id: str):
    started = await request(
        "POST", "/api/v1/analysis-sessions", {"video_id": video_id}
    )
    assert started.status_code == 201
    events = get_session_manager().subscribe_events(started.json()["session_id"])
    received = []
    while True:
        event = await anext(events)
        received.append(event)
        if event.event_type.value in {"SESSION_FINISHED", "SESSION_FAILED"}:
            break
    await events.aclose()
    return received


def test_cam02_closes_through_the_public_commands_with_versions_one_to_ten() -> None:
    async def scenario():
        events = await analyze("video-02")
        created = next(event for event in events if event.event_type.value == "CANDIDATE_CREATED")
        case_id = created.case_id
        assert case_id is not None
        initial = await request("GET", f"/api/v1/cases/{case_id}")
        facts = await request(
            "POST",
            f"/api/v1/cases/{case_id}/facts",
            {
                "command_type": "SUBMIT_FACTS",
                "actor_id": "officer-01",
                "expected_version": 4,
                "reason": "确认切割作业现场信息",
                "facts": {"site_note": "切割作业正在进行，许可与现场一致"},
            },
        )
        review = await request(
            "POST",
            f"/api/v1/cases/{case_id}/review",
            {
                "command_type": "APPROVE_RECTIFICATION",
                "actor_id": "reviewer-01",
                "expected_version": 7,
                "reason": "安全帽要求适用，批准整改",
                "responsible_party_id": "team-electric-01",
                "rectification_due_at": "2026-09-01T18:00:00+08:00",
            },
        )
        evidence = await request(
            "POST",
            f"/api/v1/cases/{case_id}/rectification-evidence",
            {
                "command_type": "SUBMIT_RECTIFICATION_EVIDENCE",
                "actor_id": "officer-01",
                "expected_version": 8,
                "reason": "现场已完成整改",
                "description": "人员已正确佩戴安全帽",
                "evidence": [
                    {
                        "evidence_id": "evidence-cam02-after",
                        "image_url": "/evidence/cam02/after.jpg",
                        "captured_at": "2026-08-15T11:00:00+08:00",
                    }
                ],
            },
        )
        closed = await request(
            "POST",
            f"/api/v1/cases/{case_id}/recheck",
            {
                "command_type": "APPROVE_CLOSURE",
                "actor_id": "reviewer-01",
                "expected_version": 9,
                "reason": "整改证据完整",
                "recheck_conclusion": "复查通过，事件关闭",
            },
        )
        detail = await request("GET", f"/api/v1/cases/{case_id}")
        return initial, facts, review, evidence, closed, detail

    initial, facts, review, evidence, closed, detail_response = asyncio.run(scenario())

    assert initial.json()["snapshot"]["status"] == "NEEDS_HUMAN_FACTS"
    assert [item["to_status"] for item in initial.json()["timeline"]] == [
        "YOLO_CANDIDATE",
        "VLM_REVIEWED",
        "INVESTIGATING",
        "NEEDS_HUMAN_FACTS",
    ]
    assert facts.status_code == 200
    assert (facts.json()["snapshot"]["status"], facts.json()["version"]) == (
        "PENDING_REVIEW",
        7,
    )
    assert [(response.status_code, response.json()["version"]) for response in (review, evidence, closed)] == [
        (200, 8), (200, 9), (200, 10),
    ]
    detail = detail_response.json()
    assert detail["snapshot"]["status"] == "CLOSED"
    assert [item["to_status"] for item in detail["timeline"]] == [
        "YOLO_CANDIDATE",
        "VLM_REVIEWED",
        "INVESTIGATING",
        "NEEDS_HUMAN_FACTS",
        "REINVESTIGATE",
        "INVESTIGATING",
        "PENDING_REVIEW",
        "RECTIFICATION_OPEN",
        "RECHECK_PENDING",
        "CLOSED",
    ]
    assert [item["source"] for item in detail["timeline"]] == [
        "YOLO", "VLM", "AGENT", "AGENT", "HUMAN",
        "AGENT", "AGENT", "HUMAN", "HUMAN", "HUMAN",
    ]
    occurred = [datetime.fromisoformat(item["occurred_at"]) for item in detail["timeline"]]
    assert occurred == sorted(occurred)
    assert [item["submission_type"] for item in detail["human_submissions"]] == [
        "FACTS",
        "RECTIFICATION_EVIDENCE",
    ]
    assert detail["human_submissions"][0]["facts"] == {
        "site_note": "切割作业正在进行，许可与现场一致"
    }


def test_six_demo_channels_expose_the_frozen_explainable_outcomes() -> None:
    async def scenario():
        results = {}
        for number in range(1, 7):
            events = await analyze(f"video-{number:02d}")
            created = next(
                (event for event in events if event.event_type.value == "CANDIDATE_CREATED"),
                None,
            )
            results[number] = (events, created)
        details = {}
        for number in range(1, 6):
            case_id = results[number][1].case_id
            details[number] = (await request("GET", f"/api/v1/cases/{case_id}")).json()
        return results, details

    results, details = asyncio.run(scenario())

    assert details[1]["snapshot"]["status"] == "NEEDS_HUMAN_FACTS"
    assert details[1]["snapshot"]["investigation"]["missing_fields"]
    assert details[2]["snapshot"]["candidate"]["last_seen_ms"] - details[2]["snapshot"]["candidate"]["first_seen_ms"] == 1000
    assert len(details[2]["snapshot"]["candidate"]["frames"]) == 3
    assert "gloves" in details[3]["snapshot"]["investigation"]["required_ppe"]
    assert "gloves" not in details[4]["snapshot"]["investigation"]["required_ppe"]
    assert "vest" in details[5]["snapshot"]["investigation"]["required_ppe"]
    assert results[5][1].case_id
    assert results[6][1] is None
    assert (results[6][0][-1].payload.candidate_count, results[6][0][-1].payload.case_count) == (0, 0)
