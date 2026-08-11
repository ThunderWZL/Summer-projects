from datetime import datetime

from sqlalchemy import select

from app.adapters.database.mappers import (
    investigation_record_values,
    investigation_result_from_record,
)
from app.adapters.database.models import (
    AnalysisSessionModel,
    AnalysisSessionStatus,
    CameraModel,
    CaseModel,
    CitationModel,
    InvestigationModel,
    VideoModel,
    ZoneModel,
)
from app.adapters.database.session import (
    create_database_engine,
    create_session_factory,
    initialize_schema,
)
from app.contracts import (
    CaseStatus,
    Citation,
    EvidenceKind,
    InvestigationResult,
    PpeType,
    RectificationRecommendation,
)


def test_investigation_result_round_trips_without_new_schema_fields() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    initialize_schema(engine)
    session_factory = create_session_factory(engine)
    occurred_at = datetime.fromisoformat("2026-08-07T09:00:05+08:00")
    expected = InvestigationResult(
        facts={
            "task_code": "HOT_WORK_CUTTING",
            "required_ppe": "untrusted human value",
        },
        conflicts=["人工描述与有效作业许可不一致"],
        missing_fields=[],
        applicable_task="HOT_WORK_CUTTING",
        hazards=["飞溅", "强光"],
        required_ppe=[PpeType.HELMET],
        recommendation="立即补戴安全帽",
        rectification_recommendation=RectificationRecommendation(
            responsible_party_id="team-electric-01",
            due_at=datetime.fromisoformat("2026-08-07T10:00:00+08:00"),
            reason="切割作业要求佩戴安全帽",
        ),
        citations=[
            Citation(
                document_title="施工现场安全规范",
                standard_no="SITE-PPE-001",
                section="第 3 条（第 8 页）",
                effective_date="2026-01-01",
                source_url="https://example.test/site-ppe-001",
                excerpt="切割作业人员应按要求佩戴安全帽。",
            )
        ],
        tool_trace=["site_context", "requirements_search"],
    )

    with session_factory() as session:
        session.add(
            ZoneModel(id="zone-02", name="切割区", zone_type="CUTTING")
        )
        session.flush()
        session.add(
            CameraModel(id="CAM-02", name="切割机位", zone_id="zone-02")
        )
        session.flush()
        session.add(
            VideoModel(
                id="video-02",
                camera_id="CAM-02",
                title="切割区",
                local_path="/data/demo/cam-02.mp4",
                source_url=None,
                duration_ms=600_000,
                scenario_started_at=occurred_at,
            )
        )
        session.flush()
        session.add(
            AnalysisSessionModel(
                id="session-02",
                video_id="video-02",
                status=AnalysisSessionStatus.FINISHED,
                started_at=occurred_at,
                playback_ms=5_000,
            )
        )
        session.flush()
        session.add(
            CaseModel(
                id="case-02",
                candidate_id="candidate-02",
                session_id="session-02",
                camera_id="CAM-02",
                person_track_id="track-02",
                ppe_type=PpeType.HELMET,
                evidence_kind=EvidenceKind.MISSING_POSITIVE_ASSOCIATION,
                confidence=0.91,
                model_name="fixture-yolo",
                model_version="1",
                weights_sha256=None,
                aggregation_method="fixture",
                aggregation_parameters_json={},
                occurred_at=occurred_at,
                first_seen_ms=1_000,
                last_seen_ms=5_000,
                status=CaseStatus.PENDING_REVIEW,
                version=1,
                human_facts_json={},
                created_at=occurred_at,
                updated_at=occurred_at,
            )
        )
        session.flush()
        session.add(
            InvestigationModel(
                id="investigation-02",
                case_id="case-02",
                **investigation_record_values(expected),
            )
        )
        session.add(
            CitationModel(
                id="citation-02",
                case_id="case-02",
                **expected.citations[0].model_dump(),
            )
        )
        session.commit()

    with session_factory() as session:
        investigation = session.get(InvestigationModel, "investigation-02")
        citations = session.scalars(
            select(CitationModel)
            .where(CitationModel.case_id == "case-02")
            .order_by(CitationModel.id)
        ).all()
        assert investigation is not None
        restored = investigation_result_from_record(investigation, citations)

    assert restored == expected
    assert restored.facts["required_ppe"] == "untrusted human value"
    assert restored.required_ppe == [PpeType.HELMET]
    engine.dispose()
