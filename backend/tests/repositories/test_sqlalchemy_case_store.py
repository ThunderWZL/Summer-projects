from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError

from app.adapters.database.models import (
    AnalysisSessionModel,
    CameraModel,
    ResponsiblePartyModel,
    UserModel,
    VideoModel,
    ZoneModel,
)
from app.adapters.database.session import (
    create_database_engine,
    create_session_factory,
    initialize_schema,
    session_scope,
)
from app.contracts import (
    ActorRole,
    AnalysisStage,
    CandidateEvidence,
    CaseSnapshot,
    CaseStatus,
    CaseTransition,
    Citation,
    FactsSubmissionRecord,
    InvestigationResult,
    PpeType,
    RectificationEvidence,
    RectificationRecommendation,
    VlmReviewResult,
)
from app.domain.case_store import CaseQuery
from app.domain.case_workflow import StaleCaseVersion
from app.repositories import SqlAlchemyCaseStore


NOW = datetime.fromisoformat("2026-08-09T10:00:00+08:00")


@pytest.fixture
def store() -> SqlAlchemyCaseStore:
    engine = create_database_engine("sqlite:///:memory:")
    initialize_schema(engine)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        session.add(ZoneModel(id="zone-01", name="作业区", zone_type="WORK"))
        session.flush()
        for camera_id in ("CAM-01", "CAM-02"):
            session.add(
                CameraModel(
                    id=camera_id,
                    name=f"{camera_id} 机位",
                    zone_id="zone-01",
                )
            )
        session.add(
            ResponsiblePartyModel(
                id="team-electric-01",
                name="电气班组",
                kind="TEAM",
                zone_id="zone-01",
                active=True,
            )
        )
        session.add(
            UserModel(
                id="officer-01",
                name="现场安全员",
                role=ActorRole.SITE_SAFETY_OFFICER,
                active=True,
            )
        )
        session.flush()
        for suffix, camera_id in (("01", "CAM-01"), ("02", "CAM-02")):
            session.add(
                VideoModel(
                    id=f"video-{suffix}",
                    camera_id=camera_id,
                    title=f"演示视频 {suffix}",
                    local_path=f"/data/video-{suffix}.mp4",
                    source_url=None,
                    duration_ms=60_000,
                    scenario_started_at=NOW,
                )
            )
        session.flush()
        for suffix in ("01", "02"):
            session.add(
                AnalysisSessionModel(
                    id=f"session-{suffix}",
                    video_id=f"video-{suffix}",
                    status=AnalysisStage.STOPPING,
                    started_at=NOW,
                    playback_ms=0,
                )
            )
    yield SqlAlchemyCaseStore(session_factory)
    engine.dispose()


def make_case(
    case_id: str = "case-01",
    *,
    status: CaseStatus = CaseStatus.NEEDS_HUMAN_FACTS,
    version: int = 1,
    camera_id: str = "CAM-01",
    occurred_at: str = "2026-08-07T10:31:24+08:00",
    due_at: str | None = None,
    responsible_party_id: str | None = None,
) -> CaseSnapshot:
    suffix = camera_id.removeprefix("CAM-")
    candidate = CandidateEvidence.model_validate(
        {
            "candidate_id": f"candidate-{case_id}",
            "session_id": f"session-{suffix}",
            "camera_id": camera_id,
            "person_track_id": f"track-{case_id}",
            "ppe_type": "helmet",
            "evidence_kind": "NEGATIVE_CLASS_DETECTION",
            "confidence": 0.91,
            "model_name": "ppe-yolo",
            "weights_sha256": "a" * 64,
            "aggregation_method": "weighted_mean",
            "aggregation_parameters": {"minimum_frames": 3},
            "occurred_at": occurred_at,
            "first_seen_ms": 1_000,
            "last_seen_ms": 2_000,
            "frames": [
                {
                    "timestamp_ms": 1_500,
                    "image_url": f"/evidence/{case_id}/key.jpg",
                    "image_width": 1920,
                    "image_height": 1080,
                    "frame_role": "REPRESENTATIVE",
                    "person_box": {"x1": 10, "y1": 20, "x2": 110, "y2": 220},
                    "observation_box": {
                        "x1": 30,
                        "y1": 20,
                        "x2": 80,
                        "y2": 60,
                    },
                    "observation_confidence": 0.93,
                }
            ],
        }
    )
    return CaseSnapshot(
        case_id=case_id,
        session_id=candidate.session_id,
        camera_id=camera_id,
        person_track_id=candidate.person_track_id,
        ppe_type=candidate.ppe_type,
        status=status,
        version=version,
        candidate=candidate,
        human_facts={"task_code": "HOT_WORK_CUTTING"},
        rectification_responsible_party_id=responsible_party_id,
        rectification_due_at=due_at,
        rectification_evidence=[
            RectificationEvidence(
                evidence_id=f"{case_id}-after",
                image_url=f"/evidence/{case_id}/after.jpg",
                captured_at="2026-08-08T09:00:00+08:00",
                note="整改后现场",
            )
        ],
        rectification_description="已完成整改",
        created_at=occurred_at,
        updated_at=occurred_at,
    )


def test_complete_snapshot_and_submission_round_trip(
    store: SqlAlchemyCaseStore,
) -> None:
    base = make_case()
    expected = base.model_copy(
        update={
            "vlm_review": VlmReviewResult(
                candidate_id=base.candidate.candidate_id,
                verdict="CONFIRMED",
                person_track_id=base.person_track_id,
                ppe_type=base.ppe_type,
                association="MATCHED",
                body_part_visible=True,
                persistent=True,
                poster_or_reflection=False,
                evidence_sufficient=True,
                evidence_timestamps_ms=[1_500],
                reason="连续帧证据充分",
                model_name="fixture-vlm",
                model_provider="fixture",
                model_parameters={"temperature": 0},
                reviewed_at="2026-08-07T10:32:00+08:00",
            ),
            "investigation": InvestigationResult(
                facts={"task_code": "HOT_WORK_CUTTING"},
                conflicts=[],
                missing_fields=[],
                applicable_task="HOT_WORK_CUTTING",
                hazards=["飞溅"],
                required_ppe=[PpeType.HELMET],
                recommendation="立即补戴安全帽",
                rectification_recommendation=RectificationRecommendation(
                    responsible_party_id="team-electric-01",
                    due_at="2026-08-08T18:00:00+08:00",
                    reason="切割作业必须佩戴安全帽",
                ),
                citations=[
                    Citation(
                        document_title="现场安全规范",
                        section="第 3 条",
                        source_url="https://example.test/rule",
                        excerpt="切割作业人员应佩戴安全帽。",
                    )
                ],
                tool_trace=["site_context", "requirements_search"],
            ),
        }
    )

    created = store.create(expected)
    found = store.find_by_candidate(expected.candidate.candidate_id)

    assert created == expected
    assert found == expected
    submission = FactsSubmissionRecord(
        submission_id="submission-01",
        case_id=expected.case_id,
        actor_id="officer-01",
        actor_name="现场安全员",
        actor_role=ActorRole.SITE_SAFETY_OFFICER,
        reason="补充作业类型",
        facts={"task_code": "HOT_WORK_CUTTING"},
        created_at=NOW,
    )
    stored_submission = store.add_submission(submission)
    stored_submission.facts["outside"] = True

    assert store.list_submissions(expected.case_id) == [submission]


def test_commit_is_optimistic_and_appends_transition_atomically(
    store: SqlAlchemyCaseStore,
) -> None:
    original = store.create(make_case())
    transition = CaseTransition(
        from_status=CaseStatus.NEEDS_HUMAN_FACTS,
        to_status=CaseStatus.REINVESTIGATE,
        actor_id="officer-01",
        actor_role=ActorRole.SITE_SAFETY_OFFICER,
        reason="补充现场事实",
        occurred_at=NOW,
    )
    changed = original.model_copy(
        update={"status": CaseStatus.REINVESTIGATE}
    )

    committed = store.commit(changed, 1, transition)

    assert (
        committed.status,
        committed.version,
        committed.updated_at,
        committed.transitions,
    ) == (CaseStatus.REINVESTIGATE, 2, NOW, [transition])
    with pytest.raises(StaleCaseVersion, match="expected version 1, current 2"):
        store.commit(changed, 1, transition)


def test_failed_transition_insert_rolls_back_case_update(
    store: SqlAlchemyCaseStore,
) -> None:
    original = store.create(make_case())
    transition = CaseTransition(
        from_status=original.status,
        to_status=CaseStatus.REINVESTIGATE,
        actor_id="missing-user",
        actor_role=ActorRole.SITE_SAFETY_OFFICER,
        reason="外键失败应回滚",
        occurred_at=NOW,
    )
    changed = original.model_copy(
        update={"status": CaseStatus.REINVESTIGATE}
    )

    with pytest.raises(IntegrityError):
        store.commit(changed, 1, transition)

    assert store.get(original.case_id) == original


def test_failed_submission_insert_rolls_back_case_and_transition(
    store: SqlAlchemyCaseStore,
) -> None:
    original = store.create(make_case())
    submission = FactsSubmissionRecord(
        submission_id="submission-duplicate",
        case_id=original.case_id,
        actor_id="officer-01",
        actor_name="现场安全员",
        actor_role=ActorRole.SITE_SAFETY_OFFICER,
        reason="补充作业类型",
        facts={"task_code": "HOT_WORK_CUTTING"},
        created_at=NOW,
    )
    store.add_submission(submission)
    transition = CaseTransition(
        from_status=original.status,
        to_status=CaseStatus.REINVESTIGATE,
        actor_id="officer-01",
        actor_role=ActorRole.SITE_SAFETY_OFFICER,
        reason="重复审计记录应回滚",
        occurred_at=NOW,
    )
    changed = original.model_copy(
        update={"status": CaseStatus.REINVESTIGATE}
    )

    with pytest.raises(IntegrityError):
        store.commit(changed, 1, transition, submission=submission)

    assert store.get(original.case_id) == original
    assert store.list_submissions(original.case_id) == [submission]


def test_list_filters_sorts_and_paginates_in_sql(
    store: SqlAlchemyCaseStore,
) -> None:
    for snapshot in (
        make_case(
            "case-system",
            status=CaseStatus.INVESTIGATING,
            occurred_at="2026-08-07T08:00:00+08:00",
        ),
        make_case(
            "case-review-later",
            status=CaseStatus.PENDING_REVIEW,
            camera_id="CAM-02",
            occurred_at="2026-08-07T11:00:00+08:00",
            responsible_party_id="team-electric-01",
        ),
        make_case(
            "case-overdue",
            status=CaseStatus.RECTIFICATION_OPEN,
            camera_id="CAM-02",
            occurred_at="2026-08-07T12:00:00+08:00",
            responsible_party_id="team-electric-01",
            due_at="2026-08-08T18:00:00+08:00",
        ),
        make_case(
            "case-review-earlier",
            status=CaseStatus.PENDING_REVIEW,
            occurred_at="2026-08-07T09:00:00+08:00",
        ),
    ):
        store.create(snapshot)

    overdue = store.list(
        CaseQuery(
            status=CaseStatus.RECTIFICATION_OPEN,
            camera_ids=frozenset({"CAM-02"}),
            responsible_party_id="team-electric-01",
            occurred_from=datetime.fromisoformat("2026-08-07T00:00:00+08:00"),
            occurred_to=datetime.fromisoformat("2026-08-08T00:00:00+08:00"),
            overdue_only=True,
            keyword="OVERDUE",
            as_of=NOW,
        )
    )
    second_page = store.list(CaseQuery(as_of=NOW, page=2, page_size=2))

    assert overdue.total_items == 1
    assert [item.case_id for item in overdue.items] == ["case-overdue"]
    assert second_page.total_items == 4
    assert [item.case_id for item in second_page.items] == [
        "case-review-later",
        "case-system",
    ]
