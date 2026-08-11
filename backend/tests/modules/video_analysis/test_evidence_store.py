from __future__ import annotations

import pytest

from app.modules.video_analysis.evidence_store import (
    EvidenceCollision,
    FileEvidenceStore,
)


JPEG = b"\xff\xd8encoded-jpeg\xff\xd9"


def test_store_writes_evidence_and_returns_a_stable_url(tmp_path) -> None:
    store = FileEvidenceStore(tmp_path)

    first_url = store.store_jpeg(
        session_id="session-01",
        timestamp_ms=400,
        jpeg_bytes=JPEG,
    )
    second_url = store.store_jpeg(
        session_id="session-01",
        timestamp_ms=400,
        jpeg_bytes=JPEG,
    )

    assert first_url == second_url == "/evidence/session-01/400.jpg"
    assert (tmp_path / "session-01" / "400.jpg").read_bytes() == JPEG


def test_store_rejects_different_bytes_for_the_same_evidence_key(tmp_path) -> None:
    store = FileEvidenceStore(tmp_path)
    store.store_jpeg(
        session_id="session-01",
        timestamp_ms=400,
        jpeg_bytes=b"\xff\xd8first\xff\xd9",
    )

    with pytest.raises(EvidenceCollision, match="already has other bytes"):
        store.store_jpeg(
            session_id="session-01",
            timestamp_ms=400,
            jpeg_bytes=b"\xff\xd8second\xff\xd9",
        )


def test_store_rejects_path_traversal_in_session_id(tmp_path) -> None:
    store = FileEvidenceStore(tmp_path)

    with pytest.raises(ValueError, match="unsafe path"):
        store.store_jpeg(
            session_id="../outside",
            timestamp_ms=400,
            jpeg_bytes=JPEG,
        )


def test_store_rejects_bytes_that_are_not_jpeg_encoded(tmp_path) -> None:
    store = FileEvidenceStore(tmp_path)

    with pytest.raises(ValueError, match="encoded JPEG"):
        store.store_jpeg(
            session_id="session-01",
            timestamp_ms=400,
            jpeg_bytes=b"not-an-image",
        )
