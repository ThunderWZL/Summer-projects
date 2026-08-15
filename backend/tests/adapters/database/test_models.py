from datetime import datetime, timedelta

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import StatementError

from app.adapters.database.models import (
    AnalysisSessionModel,
    CaseEvidenceModel,
    TimezoneAwareDateTime,
    UserModel,
)
from app.adapters.database.session import (
    create_database_engine,
    create_session_factory,
    initialize_schema,
    session_scope,
)
from app.contracts import ActorRole


EXPECTED_TABLES = {
    "users",
    "responsible_parties",
    "zones",
    "cameras",
    "videos",
    "work_permits",
    "task_ppe_matrix",
    "analysis_sessions",
    "cases",
    "case_evidence",
    "vlm_reviews",
    "investigations",
    "citations",
    "human_submissions",
    "case_transitions",
}


def test_schema_contains_the_designed_tables_and_business_uniqueness() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    initialize_schema(engine)
    inspector = inspect(engine)

    assert set(inspector.get_table_names()) == EXPECTED_TABLES
    case_constraints = inspector.get_unique_constraints("cases")
    assert any(
        constraint["column_names"] == ["candidate_id"]
        for constraint in case_constraints
    )

    investigation_constraints = inspector.get_unique_constraints(
        "investigations"
    )
    assert any(
        constraint["column_names"] == ["case_id"]
        for constraint in investigation_constraints
    )

    evidence_constraints = inspector.get_unique_constraints("case_evidence")
    assert any(
        constraint["column_names"] == ["case_id", "timestamp_ms"]
        for constraint in evidence_constraints
    )


def test_aware_datetime_normalizes_to_utc_without_changing_the_instant() -> None:
    value = datetime.fromisoformat("2026-08-07T09:00:00+08:00")
    column_type = TimezoneAwareDateTime()

    stored = column_type.process_bind_param(value, None)
    restored = column_type.process_result_value(stored, None)

    assert restored == value
    assert restored is not None
    assert restored.utcoffset() == timedelta(0)
    assert stored == "2026-08-07T01:00:00+00:00"


def test_aware_datetime_rejects_a_naive_value() -> None:
    column_type = TimezoneAwareDateTime()

    with pytest.raises(ValueError, match="timezone-aware"):
        column_type.process_bind_param(datetime(2026, 8, 7, 9), None)


@pytest.mark.parametrize(
    ("model", "message"),
    [
        (
            AnalysisSessionModel(
                id="session-invalid",
                video_id="missing-video",
                status="UNKNOWN",
                started_at=datetime.fromisoformat(
                    "2026-08-07T09:00:00+08:00"
                ),
                playback_ms=0,
            ),
            "analysis_stage",
        ),
        (
            CaseEvidenceModel(
                id="evidence-invalid",
                case_id="missing-case",
                kind="UNKNOWN",
                timestamp_ms=0,
                path="/evidence/invalid.jpg",
                metadata_json={},
            ),
            "case_evidence_frame_role",
        ),
    ],
)
def test_domain_strings_are_validated_before_database_write(
    model, message
) -> None:
    engine = create_database_engine("sqlite:///:memory:")
    initialize_schema(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        session.add(model)
        with pytest.raises(StatementError, match=message):
            session.flush()

    engine.dispose()


def test_session_scope_rolls_back_the_whole_unit_of_work() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    initialize_schema(engine)
    session_factory = create_session_factory(engine)

    with pytest.raises(RuntimeError, match="force rollback"):
        with session_scope(session_factory) as session:
            session.add(
                UserModel(
                    id="rolled-back-user",
                    name="不会提交的用户",
                    role=ActorRole.SITE_SAFETY_OFFICER,
                    active=True,
                )
            )
            raise RuntimeError("force rollback")

    with session_factory() as session:
        assert session.scalar(
            select(UserModel).where(UserModel.id == "rolled-back-user")
        ) is None

    engine.dispose()
