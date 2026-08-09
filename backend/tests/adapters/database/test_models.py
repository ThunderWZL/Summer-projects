from datetime import datetime, timedelta

import pytest
from sqlalchemy import inspect

from app.adapters.database.models import TimezoneAwareDateTime
from app.adapters.database.session import (
    create_database_engine,
    initialize_schema,
)


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


def test_schema_contains_the_designed_tables_and_candidate_uniqueness() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    initialize_schema(engine)
    inspector = inspect(engine)

    assert set(inspector.get_table_names()) == EXPECTED_TABLES
    unique_constraints = inspector.get_unique_constraints("cases")
    assert any(
        constraint["column_names"] == ["candidate_id"]
        for constraint in unique_constraints
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
