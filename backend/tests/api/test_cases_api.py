import asyncio
from datetime import datetime

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_case_store, get_clock
from app.main import app


NOW = datetime.fromisoformat("2026-08-09T10:00:00+08:00")


def setup_function() -> None:
    get_case_store.cache_clear()
    app.dependency_overrides[get_clock] = lambda: lambda: NOW


def teardown_function() -> None:
    app.dependency_overrides.pop(get_clock, None)


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


def test_review_rejects_ineligible_responsible_party_without_changing_case() -> None:
    before = asyncio.run(request("GET", "/api/v1/cases/case-01")).json()

    response = asyncio.run(
        request(
            "POST",
            "/api/v1/cases/case-01/review",
            {
                "command_type": "APPROVE_RECTIFICATION",
                "actor_id": "reviewer-01",
                "expected_version": 4,
                "reason": "尝试指定不存在的责任主体",
                "responsible_party_id": "party-does-not-exist",
                "rectification_due_at": "2026-08-20T18:00:00+08:00",
            },
        )
    )
    after = asyncio.run(request("GET", "/api/v1/cases/case-01")).json()

    assert response.status_code == 400
    assert response.json() == {
        "code": "INVALID_RESPONSIBLE_PARTY",
        "message": (
            "responsible party party-does-not-exist is not eligible "
            "for case case-01"
        ),
        "current_version": None,
    }
    assert after["snapshot"] == before["snapshot"]
    assert after["timeline"] == before["timeline"]
    assert after["human_submissions"] == before["human_submissions"]

    reinvestigation = asyncio.run(
        request(
            "POST",
            "/api/v1/cases/case-01/review",
            {
                "command_type": "REQUEST_REINVESTIGATION",
                "actor_id": "reviewer-01",
                "expected_version": 4,
                "reason": "许可信息需要重新核对",
            },
        )
    )
    assert (
        reinvestigation.status_code,
        reinvestigation.json()["snapshot"]["status"],
        reinvestigation.json()["version"],
    ) == (200, "REINVESTIGATE", 5)


def test_closed_vehicle_case_investigation_matches_its_vest_candidate() -> None:
    response = asyncio.run(
        request("GET", "/api/v1/cases/case-closed-01")
    )

    assert response.status_code == 200
    snapshot = response.json()["snapshot"]
    assert (snapshot["camera_id"], snapshot["ppe_type"]) == (
        "CAM-05",
        "vest",
    )
    assert snapshot["candidate"]["evidence_kind"] == (
        "MISSING_POSITIVE_ASSOCIATION"
    )
    assert snapshot["candidate"]["frames"][0]["observation_box"] is None
    assert snapshot["candidate"]["frames"][0][
        "observation_confidence"
    ] is None
    assert snapshot["investigation"] == {
        "facts": {"task_code": "VEHICLE_ZONE_OPERATION"},
        "conflicts": [],
        "missing_fields": [],
        "applicable_task": "VEHICLE_ZONE_OPERATION",
        "hazards": ["车辆碰撞"],
        "required_ppe": ["vest"],
        "recommendation": "车辆作业区人员应佩戴高可视背心",
        "rectification_recommendation": {
            "responsible_party_id": "team-logistics-01",
            "due_at": "2026-08-08T10:00:00+08:00",
            "reason": "车辆作业区需要提高人员可见性",
        },
        "citations": [
            {
                "document_title": "建筑工人施工现场劳动保护基本配置指南",
                "standard_no": None,
                "section": "高可视警示服",
                "effective_date": None,
                "source_url": "https://www.gov.cn/zhengce/zhengceku/2021-01/19/5580999/",
                "excerpt": "车辆作业区域应按风险配备高可视警示服。",
            }
        ],
        "tool_trace": [
            "get_zone_at",
            "find_active_work_permits",
            "get_task_ppe_matrix",
            "search_authoritative_requirements",
        ],
    }


def test_recheck_fixture_has_matching_evidence_submission_and_timeline() -> None:
    response = asyncio.run(
        request("GET", "/api/v1/cases/case-recheck-no-evidence")
    )

    assert response.status_code == 200
    body = response.json()
    snapshot = body["snapshot"]
    assert snapshot["status"] == "RECHECK_PENDING"
    assert snapshot["rectification_description"] == "已完成防卷入整改并复核作业要求"
    assert snapshot["rectification_evidence"] == [
        {
            "evidence_id": "evidence-case-recheck-01",
            "image_url": "/evidence/case-recheck-no-evidence/after.jpg",
            "captured_at": "2026-08-07T11:04:00+08:00",
            "note": "整改后的旋转设备作业现场",
        }
    ]
    assert body["human_submissions"] == [
        {
            "submission_id": "submission-case-recheck-no-evidence-6",
            "case_id": "case-recheck-no-evidence",
            "actor_id": "officer-01",
            "actor_name": "现场安全员",
            "actor_role": "SITE_SAFETY_OFFICER",
            "reason": "现场已完成整改",
            "created_at": "2026-08-07T11:05:00+08:00",
            "submission_type": "RECTIFICATION_EVIDENCE",
            "description": "已完成防卷入整改并复核作业要求",
            "evidence": snapshot["rectification_evidence"],
        }
    ]
    assert body["timeline"][-1] == {
        "timeline_item_id": "case-recheck-no-evidence-transition-5",
        "source": "HUMAN",
        "action": "RECHECK_PENDING",
        "from_status": "RECTIFICATION_OPEN",
        "to_status": "RECHECK_PENDING",
        "actor_id": "officer-01",
        "actor_name": "现场安全员",
        "actor_role": "SITE_SAFETY_OFFICER",
        "reason": "现场已完成整改",
        "occurred_at": "2026-08-07T11:05:00+08:00",
    }


@pytest.mark.parametrize(
    (
        "case_id",
        "task_code",
        "required_ppe",
        "recommended_party_id",
    ),
    [
        ("case-facts-01", None, [], None),
        (
            "case-01",
            "HOT_WORK_CUTTING",
            ["goggles", "helmet"],
            "team-electric-01",
        ),
        (
            "case-overdue-01",
            "HANDLING_REBAR",
            ["gloves"],
            "team-structure-01",
        ),
        (
            "case-recheck-no-evidence",
            "ROTATING_EQUIPMENT_OPERATION",
            ["helmet"],
            "team-mechanical-01",
        ),
        (
            "case-closed-01",
            "VEHICLE_ZONE_OPERATION",
            ["vest"],
            "team-logistics-01",
        ),
    ],
)
def test_progressed_demo_cases_expose_identity_consistent_machine_results(
    case_id: str,
    task_code: str | None,
    required_ppe: list[str],
    recommended_party_id: str | None,
) -> None:
    response = asyncio.run(request("GET", f"/api/v1/cases/{case_id}"))

    assert response.status_code == 200
    snapshot = response.json()["snapshot"]
    candidate = snapshot["candidate"]
    review = snapshot["vlm_review"]
    investigation = snapshot["investigation"]
    assert (
        review["candidate_id"],
        review["person_track_id"],
        review["ppe_type"],
        review["verdict"],
        review["association"],
        review["evidence_sufficient"],
    ) == (
        candidate["candidate_id"],
        candidate["person_track_id"],
        candidate["ppe_type"],
        "CONFIRMED",
        "MATCHED",
        True,
    )
    assert investigation["applicable_task"] == task_code
    assert investigation["required_ppe"] == required_ppe
    recommendation = investigation["rectification_recommendation"]
    assert (
        recommendation["responsible_party_id"] if recommendation else None
    ) == recommended_party_id


def test_closed_fixture_preserves_its_rectification_submission_audit() -> None:
    response = asyncio.run(
        request("GET", "/api/v1/cases/case-closed-01")
    )

    assert response.status_code == 200
    body = response.json()
    evidence = body["snapshot"]["rectification_evidence"]
    assert evidence == [
        {
            "evidence_id": "evidence-case-closed-01",
            "image_url": "/evidence/case-closed-01/after.jpg",
            "captured_at": "2026-08-07T12:00:00+08:00",
            "note": "整改后的车辆作业区人员高可视背心",
        }
    ]
    assert body["human_submissions"] == [
        {
            "submission_id": "submission-case-closed-01-6",
            "case_id": "case-closed-01",
            "actor_id": "officer-01",
            "actor_name": "现场安全员",
            "actor_role": "SITE_SAFETY_OFFICER",
            "reason": "现场已完成整改",
            "created_at": "2026-08-07T12:01:00+08:00",
            "submission_type": "RECTIFICATION_EVIDENCE",
            "description": "已佩戴高可视背心",
            "evidence": evidence,
        }
    ]
    evidence_transition = body["timeline"][-2]
    assert (
        evidence_transition["actor_id"],
        evidence_transition["actor_role"],
        evidence_transition["reason"],
        evidence_transition["occurred_at"],
    ) == (
        "officer-01",
        "SITE_SAFETY_OFFICER",
        "现场已完成整改",
        "2026-08-07T12:01:00+08:00",
    )


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
