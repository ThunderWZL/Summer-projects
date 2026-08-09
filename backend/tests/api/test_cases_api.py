import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_case_store
from app.main import app


def setup_function() -> None:
    get_case_store.cache_clear()


async def request(method: str, path: str, json: dict | None = None):
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        return await client.request(method, path, json=json)


def test_case_list_filters_paginates_and_returns_backend_statistics() -> None:
    response = asyncio.run(
        request(
            "GET",
            "/api/v1/cases?status=RECTIFICATION_OPEN"
            "&ppe_type=gloves&zone_id=zone-03"
            "&responsible_party_id=team-structure-01"
            "&occurred_from=2026-08-07T00:00:00%2B08:00"
            "&occurred_to=2026-08-08T00:00:00%2B08:00"
            "&overdue_only=true&page=1&page_size=1",
        )
    )

    assert response.status_code == 200
    body = response.json()
    assert body["pagination"] == {
        "page": 1,
        "page_size": 1,
        "total_items": 1,
        "total_pages": 1,
    }
    assert body["items"][0]["case_id"] == "case-overdue-01"
    assert body["items"][0]["overdue"] is True
    assert body["items"][0]["urgency"] == "HIGH"
    assert body["statistics"] == {
        "open_count": 4,
        "needs_human_facts_count": 1,
        "pending_review_count": 1,
        "rectification_open_count": 1,
        "recheck_pending_count": 1,
        "overdue_count": 1,
        "average_closure_minutes": 1488.6,
        "top_repeat_risk": {
            "zone_id": "zone-01",
            "zone_name": "脚手架区",
            "ppe_type": "helmet",
            "case_count": 1,
        },
    }


def test_case_detail_aggregates_context_citations_submissions_and_timeline() -> None:
    response = asyncio.run(request("GET", "/api/v1/cases/case-01"))

    assert response.status_code == 200
    body = response.json()
    assert body["snapshot"]["case_id"] == "case-01"
    assert body["camera_name"] == "切割机位"
    assert (body["zone_id"], body["zone_name"], body["zone_type"]) == (
        "zone-02",
        "切割区",
        "CUTTING",
    )
    assert (body["video_id"], body["video_title"]) == (
        "video-02",
        "切割区",
    )
    assert body["citations"][0]["standard_no"] == "GB 39800.12-2025"
    assert body["human_submissions"] == []
    assert [
        (item["source"], item["to_status"]) for item in body["timeline"]
    ] == [
        ("YOLO", "YOLO_CANDIDATE"),
        ("VLM", "VLM_REVIEWED"),
        ("AGENT", "INVESTIGATING"),
        ("AGENT", "PENDING_REVIEW"),
    ]


def test_officer_facts_command_updates_version_timeline_and_submission_history() -> None:
    response = asyncio.run(
        request(
            "POST",
            "/api/v1/cases/case-facts-01/facts",
            {
                "command_type": "SUBMIT_FACTS",
                "actor_id": "officer-01",
                "expected_version": 4,
                "reason": "确认现场正在进行脚手架搭设",
                "facts": {"task_code": "SCAFFOLD_ASSEMBLY"},
            },
        )
    )

    assert response.status_code == 200
    assert (
        response.json()["snapshot"]["status"],
        response.json()["version"],
        len(response.json()["snapshot"]["transitions"]),
    ) == ("REINVESTIGATE", 5, 4)

    detail = asyncio.run(request("GET", "/api/v1/cases/case-facts-01")).json()
    assert len(detail["timeline"]) == 5
    assert detail["human_submissions"][0]["submission_type"] == "FACTS"
    assert detail["human_submissions"][0]["facts"] == {
        "task_code": "SCAFFOLD_ASSEMBLY"
    }


def test_reviewer_and_officer_complete_review_rectification_and_recheck() -> None:
    review = asyncio.run(
        request(
            "POST",
            "/api/v1/cases/case-01/review",
            {
                "command_type": "APPROVE_RECTIFICATION",
                "actor_id": "reviewer-01",
                "expected_version": 4,
                "reason": "证据和依据完整，同意进入整改",
                "responsible_party_id": "team-electric-01",
                "rectification_due_at": "2026-08-20T18:00:00+08:00",
            },
        )
    )
    assert (
        review.status_code,
        review.json()["snapshot"]["status"],
        review.json()["version"],
        len(review.json()["snapshot"]["transitions"]),
    ) == (200, "RECTIFICATION_OPEN", 5, 4)

    evidence = asyncio.run(
        request(
            "POST",
            "/api/v1/cases/case-01/rectification-evidence",
            {
                "command_type": "SUBMIT_RECTIFICATION_EVIDENCE",
                "actor_id": "officer-01",
                "expected_version": 5,
                "reason": "现场已完成整改",
                "description": "已佩戴护目镜并完成班前检查",
                "evidence": [
                    {
                        "evidence_id": "evidence-after-01",
                        "image_url": "/evidence/case-01/after.jpg",
                        "captured_at": "2026-08-09T12:00:00+08:00",
                    }
                ],
            },
        )
    )
    assert (
        evidence.status_code,
        evidence.json()["snapshot"]["status"],
        evidence.json()["version"],
        len(evidence.json()["snapshot"]["transitions"]),
    ) == (200, "RECHECK_PENDING", 6, 5)

    recheck = asyncio.run(
        request(
            "POST",
            "/api/v1/cases/case-01/recheck",
            {
                "command_type": "APPROVE_CLOSURE",
                "actor_id": "reviewer-01",
                "expected_version": 6,
                "reason": "整改前后证据完整",
                "recheck_conclusion": "复查通过，可以关闭",
            },
        )
    )
    assert (
        recheck.status_code,
        recheck.json()["snapshot"]["status"],
        recheck.json()["version"],
        len(recheck.json()["snapshot"]["transitions"]),
    ) == (200, "CLOSED", 7, 6)

    detail = asyncio.run(request("GET", "/api/v1/cases/case-01")).json()
    assert len(detail["timeline"]) == 7
    assert [item["submission_type"] for item in detail["human_submissions"]] == [
        "RECTIFICATION_EVIDENCE"
    ]


@pytest.mark.parametrize(
    ("path", "payload", "status_code", "expected"),
    [
        (
            "/api/v1/cases/missing-case/facts",
            {
                "command_type": "SUBMIT_FACTS",
                "actor_id": "officer-01",
                "expected_version": 1,
                "reason": "补充事实",
                "facts": {"task": "cutting"},
            },
            404,
            {
                "code": "CASE_NOT_FOUND",
                "message": "case missing-case was not found",
                "current_version": None,
            },
        ),
        (
            "/api/v1/cases/case-01/review",
            {
                "command_type": "REJECT_CASE",
                "actor_id": "reviewer-01",
                "expected_version": 3,
                "reason": "旧页面操作",
            },
            409,
            {
                "code": "STALE_CASE_VERSION",
                "message": "expected version 3, current 4",
                "current_version": 4,
            },
        ),
        (
            "/api/v1/cases/case-01/review",
            {
                "command_type": "REJECT_CASE",
                "actor_id": "officer-01",
                "expected_version": 4,
                "reason": "越权驳回",
            },
            403,
            {
                "code": "PERMISSION_DENIED",
                "message": "actor officer-01 cannot execute this command",
                "current_version": None,
            },
        ),
        (
            "/api/v1/cases/case-01/recheck",
            {
                "command_type": "APPROVE_CLOSURE",
                "actor_id": "reviewer-01",
                "expected_version": 4,
                "reason": "跨状态关闭",
                "recheck_conclusion": "复查通过",
            },
            400,
            {
                "code": "COMMAND_NOT_ALLOWED",
                "message": (
                    "APPROVE_CLOSURE is not allowed from PENDING_REVIEW"
                ),
                "current_version": None,
            },
        ),
        (
            "/api/v1/cases/case-01/review",
            {
                "command_type": "APPROVE_RECTIFICATION",
                "actor_id": "reviewer-01",
                "expected_version": 4,
                "reason": "期限错误",
                "responsible_party_id": "team-electric-01",
                "rectification_due_at": "2026-08-01T18:00:00+08:00",
            },
            400,
            {
                "code": "INVALID_DEADLINE",
                "message": "rectification deadline must be in the future",
                "current_version": None,
            },
        ),
        (
            "/api/v1/cases/case-recheck-no-evidence/recheck",
            {
                "command_type": "APPROVE_CLOSURE",
                "actor_id": "reviewer-01",
                "expected_version": 6,
                "reason": "缺少证据仍尝试关闭",
                "recheck_conclusion": "复查通过",
            },
            400,
            {
                "code": "EVIDENCE_REQUIRED",
                "message": "rectification evidence is required",
                "current_version": None,
            },
        ),
    ],
)
def test_workflow_errors_have_stable_http_responses(
    path: str,
    payload: dict,
    status_code: int,
    expected: dict,
) -> None:
    response = asyncio.run(request("POST", path, payload))

    assert response.status_code == status_code
    assert response.json() == expected
