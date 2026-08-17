from __future__ import annotations

import pytest

from app.modules.video_analysis.evidence_store import (
    EvidenceCollision,
    FileEvidenceStore,
)


JPEG = b"\xff\xd8encoded-jpeg\xff\xd9"
PNG = b"\x89PNG\r\n\x1a\nencoded-png"


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
    assert store.resolve_jpeg("session-01", 400) == (
        tmp_path / "session-01" / "400.jpg"
    )
    assert store.resolve_jpeg("../outside", 400) is None


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


def test_store_writes_uploaded_rectification_image_with_a_stable_url(tmp_path) -> None:
    store = FileEvidenceStore(tmp_path)

    url = store.store_rectification_image(
        case_id="case-01",
        evidence_id="manual-01",
        image_bytes=PNG,
        media_type="image/png",
    )

    assert url == "/evidence/rectification/case-01/manual-01"
    assert store.resolve_rectification_image("case-01", "manual-01") == (
        tmp_path / "rectification" / "case-01" / "manual-01.png",
        "image/png",
    )


@pytest.mark.parametrize(
    ("case_id", "evidence_id"),
    [("../outside", "manual-01"), ("case-01", "../outside")],
)
def test_store_rejects_unsafe_rectification_image_identifiers(
    tmp_path, case_id: str, evidence_id: str
) -> None:
    store = FileEvidenceStore(tmp_path)

    with pytest.raises(ValueError, match="unsafe path"):
        store.store_rectification_image(
            case_id=case_id,
            evidence_id=evidence_id,
            image_bytes=JPEG,
            media_type="image/jpeg",
        )


def test_store_rejects_rectification_image_with_mismatched_content(tmp_path) -> None:
    store = FileEvidenceStore(tmp_path)

    with pytest.raises(ValueError, match="does not match"):
        store.store_rectification_image(
            case_id="case-01",
            evidence_id="manual-01",
            image_bytes=b"not-an-image",
            media_type="image/jpeg",
        )
