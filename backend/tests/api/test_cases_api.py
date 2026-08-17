import asyncio
from datetime import datetime

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import (
    build_fixture_case_pipeline,
    get_case_pipeline,
    get_case_store,
    get_clock,
    get_evidence_store_port,
    get_investigation_port,
    get_site_context,
    get_user_directory,
)
from app.contracts import CaseStatus
from app.domain.inmemory.case_store import InMemoryCaseStore
from app.domain.inmemory.fixture_cases import demo_cases, demo_submissions
from app.main import app
from app.modules.video_analysis.evidence_store import FileEvidenceStore


NOW = datetime.fromisoformat("2026-08-09T10:00:00+08:00")


def setup_function() -> None:
    get_case_pipeline.cache_clear()
    get_investigation_port.cache_clear()
    get_case_store.cache_clear()
    store = InMemoryCaseStore()
    for snapshot in demo_cases():
        store.create(snapshot)
    for submission in demo_submissions():
        store.add_submission(submission)
    pipeline = build_fixture_case_pipeline(
        store,
        get_user_directory(),
        get_site_context(),
        lambda: NOW,
    )
    app.dependency_overrides[get_case_store] = lambda: store
    app.dependency_overrides[get_case_pipeline] = lambda: pipeline
    app.dependency_overrides[get_clock] = lambda: lambda: NOW


def teardown_function() -> None:
    app.dependency_overrides.pop(get_clock, None)
    app.dependency_overrides.pop(get_case_store, None)
    app.dependency_overrides.pop(get_case_pipeline, None)


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
            "&responsible_party_id=team-carpentry-01"
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
        "pending_review_count": 2,
        "rectification_open_count": 1,
        "recheck_pending_count": 0,
        "overdue_count": 1,
        "average_closure_minutes": 1488.6,
        "top_repeat_risk": {
            "zone_id": "zone-02",
            "zone_name": "无背心2切割物料区",
            "ppe_type": "vest",
            "case_count": 2,
        },
    }


def test_case_detail_aggregates_context_citations_submissions_and_timeline() -> None:
    response = asyncio.run(request("GET", "/api/v1/cases/case-01"))

    assert response.status_code == 200
    body = response.json()
    assert body["snapshot"]["case_id"] == "case-01"
    assert body["camera_name"] == "无背心2切割物料机位"
    assert (body["zone_id"], body["zone_name"], body["zone_type"]) == (
        "zone-02",
        "无背心2切割物料区",
        "CUTTING",
    )
    assert (body["video_id"], body["video_title"]) == (
        "video-no-vest-02",
        "无背心2｜切割物料",
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


def test_officer_facts_command_saves_once_and_returns_latest_reinvestigation() -> None:
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
    assert response.json()["snapshot"]["status"] == "NEEDS_HUMAN_FACTS"
    assert response.json()["version"] == response.json()["snapshot"]["version"]
    assert response.json()["version"] == 7

    detail = asyncio.run(request("GET", "/api/v1/cases/case-facts-01")).json()
    assert len(detail["timeline"]) == 7
    assert [item["to_status"] for item in detail["timeline"][-3:]] == [
        "REINVESTIGATE",
        "INVESTIGATING",
        "NEEDS_HUMAN_FACTS",
    ]
    assert len(detail["human_submissions"]) == 1
    assert detail["human_submissions"][0]["submission_type"] == "FACTS"
    assert detail["human_submissions"][0]["facts"] == {
        "task_code": "SCAFFOLD_ASSEMBLY"
    }


@pytest.mark.parametrize(
    ("case_id", "path_suffix", "payload"),
    [
        (
            "case-facts-01",
            "facts",
            {
                "command_type": "SUBMIT_FACTS",
                "reason": "补充现场事实",
                "facts": {"task_code": "SCAFFOLD_ASSEMBLY"},
            },
        ),
        (
            "case-overdue-01",
            "rectification-evidence",
            {
                "command_type": "SUBMIT_RECTIFICATION_EVIDENCE",
                "reason": "提交整改证据",
                "description": "已整改",
                "evidence": [
                    {
                        "evidence_id": "unknown-actor-evidence",
                        "image_url": "/evidence/after.jpg",
                        "captured_at": "2026-08-09T09:00:00+08:00",
                    }
                ],
            },
        ),
    ],
)
def test_audited_submissions_reject_unknown_actor_without_transition(
    case_id: str,
    path_suffix: str,
    payload: dict,
) -> None:
    before = asyncio.run(request("GET", f"/api/v1/cases/{case_id}")).json()
    payload.update(
        actor_id="missing-officer",
        expected_version=before["snapshot"]["version"],
    )

    response = asyncio.run(
        request("POST", f"/api/v1/cases/{case_id}/{path_suffix}", payload)
    )
    after = asyncio.run(request("GET", f"/api/v1/cases/{case_id}")).json()

    assert response.status_code == 403
    assert response.json()["code"] == "PERMISSION_DENIED"
    assert after["snapshot"] == before["snapshot"]
    assert after["human_submissions"] == before["human_submissions"]


def test_top_repeat_risk_counts_only_confirmed_applicable_cases() -> None:
    base = next(case for case in demo_cases() if case.case_id == "case-01")
    store = InMemoryCaseStore()

    def variant(
        suffix: str,
        *,
        status: CaseStatus,
        investigation,
        vlm_review=True,
    ):
        evidence = base.candidate.model_copy(
            update={"candidate_id": f"candidate-repeat-{suffix}"}, deep=True
        )
        return base.model_copy(
            update={
                "case_id": f"case-repeat-{suffix}",
                "candidate": evidence,
                "status": status,
                "vlm_review": base.vlm_review if vlm_review else None,
                "investigation": investigation,
            },
            deep=True,
        )

    applicable = base.investigation
    assert applicable is not None
    inapplicable = applicable.model_copy(update={"required_ppe": ["gloves"]})
    for snapshot in (
        variant("one", status=CaseStatus.PENDING_REVIEW, investigation=applicable),
        variant("two", status=CaseStatus.CLOSED, investigation=applicable),
        variant("vlm-rejected", status=CaseStatus.VLM_REJECTED, investigation=applicable),
        variant("no-investigation", status=CaseStatus.VLM_REVIEWED, investigation=None),
        variant("not-applicable", status=CaseStatus.PENDING_REVIEW, investigation=inapplicable),
    ):
        store.create(snapshot)
    app.dependency_overrides[get_case_store] = lambda: store

    response = asyncio.run(request("GET", "/api/v1/cases"))

    assert response.status_code == 200
    assert response.json()["statistics"]["top_repeat_risk"] == {
        "zone_id": "zone-02",
        "zone_name": "无背心2切割物料区",
        "ppe_type": "vest",
        "case_count": 2,
    }


def test_cam04_gloves_can_be_approved_through_rest() -> None:
    response = asyncio.run(
        request(
            "POST",
            "/api/v1/cases/case-recheck-no-evidence/review",
            {
                "command_type": "APPROVE_RECTIFICATION",
                "actor_id": "reviewer-01",
                "expected_version": 4,
                "reason": "攀爬作业手套要求适用，同意进入整改",
                "responsible_party_id": "team-climbing-01",
                "rectification_due_at": "2026-08-20T18:00:00+08:00",
            },
        )
    )

    assert response.status_code == 200
    assert response.json()["snapshot"]["status"] == "RECTIFICATION_OPEN"


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
                "responsible_party_id": "team-cutting-02",
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


def test_officer_uploads_a_rectification_image_that_can_be_displayed(tmp_path) -> None:
    store = FileEvidenceStore(tmp_path)

    async def override_store():
        return store

    app.dependency_overrides[get_evidence_store_port] = override_store

    async def upload_and_read():
        async with AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
        ) as client:
            uploaded = await client.post(
                "/api/v1/cases/case-overdue-01/rectification-evidence/images/manual-01",
                params={"actor_id": "officer-01"},
                content=b"\xff\xd8rectified\xff\xd9",
                headers={"Content-Type": "image/jpeg"},
            )
            image = await client.get(uploaded.json()["image_url"])
            return uploaded, image

    try:
        uploaded, image = asyncio.run(upload_and_read())
    finally:
        app.dependency_overrides.pop(get_evidence_store_port, None)

    assert uploaded.status_code == 201
    assert uploaded.json() == {
        "evidence_id": "manual-01",
        "image_url": "/evidence/rectification/case-overdue-01/manual-01",
    }
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/jpeg"
    assert image.content == b"\xff\xd8rectified\xff\xd9"


def test_rectification_image_upload_rejects_reviewer(tmp_path) -> None:
    store = FileEvidenceStore(tmp_path)

    async def override_store():
        return store

    app.dependency_overrides[get_evidence_store_port] = override_store

    async def upload():
        async with AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
        ) as client:
            return await client.post(
                "/api/v1/cases/case-overdue-01/rectification-evidence/images/manual-01",
                params={"actor_id": "reviewer-01"},
                content=b"\xff\xd8rectified\xff\xd9",
                headers={"Content-Type": "image/jpeg"},
            )

    try:
        response = asyncio.run(upload())
    finally:
        app.dependency_overrides.pop(get_evidence_store_port, None)

    assert response.status_code == 403
    assert store.resolve_rectification_image("case-overdue-01", "manual-01") is None


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
    ) == (200, "PENDING_REVIEW", 7)


def test_closed_timber_case_investigation_matches_its_vest_candidate() -> None:
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
    investigation = snapshot["investigation"]
    assert investigation["facts"]["task_code"] == "TIMBER_ASSEMBLY"
    assert investigation["facts"]["task_source"] == "active_work_permit"
    assert investigation["conflicts"] == []
    assert investigation["missing_fields"] == []
    assert investigation["applicable_task"] == "TIMBER_ASSEMBLY"
    assert investigation["hazards"] == ["木料碰撞", "手部伤害"]
    assert investigation["required_ppe"] == ["helmet", "gloves", "vest"]
    assert investigation["recommendation"] == (
        "木料组装作业人员应穿戴安全背心"
    )
    assert investigation["rectification_recommendation"][
        "responsible_party_id"
    ] == "team-carpentry-02"
    assert len(investigation["citations"]) == 1
    assert investigation["tool_trace"] == [
        "list_eligible_responsible_parties",
        "search_authoritative_requirements",
    ]


def test_cam04_fixture_stays_pending_without_inapplicable_rectification_audit() -> None:
    response = asyncio.run(
        request("GET", "/api/v1/cases/case-recheck-no-evidence")
    )

    assert response.status_code == 200
    body = response.json()
    snapshot = body["snapshot"]
    assert snapshot["status"] == "PENDING_REVIEW"
    assert snapshot["rectification_description"] is None
    assert snapshot["rectification_evidence"] == []
    assert body["human_submissions"] == []
    assert body["timeline"][-1]["to_status"] == "PENDING_REVIEW"


@pytest.mark.parametrize(
    (
        "case_id",
        "task_code",
        "required_ppe",
        "recommended_party_id",
    ),
    [
        (
            "case-facts-01",
            "MATERIAL_CUTTING",
            ["helmet", "gloves", "vest"],
            None,
        ),
        (
            "case-01",
            "MATERIAL_CUTTING",
            ["helmet", "gloves", "vest"],
            "team-cutting-02",
        ),
        (
            "case-overdue-01",
            "BOARD_FASTENING",
            ["helmet", "gloves", "vest"],
            "team-carpentry-01",
        ),
        (
            "case-recheck-no-evidence",
            "CLIMBING_WORK",
            ["helmet", "gloves", "vest"],
            "team-climbing-01",
        ),
        (
            "case-closed-01",
            "TIMBER_ASSEMBLY",
            ["helmet", "gloves", "vest"],
            "team-carpentry-02",
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
            "note": "整改后的木料组装作业人员安全背心",
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
            "description": "已穿戴安全背心",
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
                "responsible_party_id": "team-cutting-02",
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
