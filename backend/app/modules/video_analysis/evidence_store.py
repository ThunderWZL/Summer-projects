from __future__ import annotations

import os
import re
from pathlib import Path
from tempfile import NamedTemporaryFile


_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9._-]+$")
_UPLOAD_MEDIA_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


class EvidenceCollision(RuntimeError):
    """The same evidence key was reused with different image bytes."""


class FileEvidenceStore:
    """Persist encoded evidence frames and return stable relative URLs."""

    def __init__(self, root_directory: Path, *, url_prefix: str = "/evidence") -> None:
        if not url_prefix.startswith("/") or url_prefix.endswith("/"):
            raise ValueError(
                "url_prefix must be an absolute relative URL without / suffix"
            )
        self.root_directory = root_directory
        self.url_prefix = url_prefix

    def store_jpeg(
        self,
        *,
        session_id: str,
        timestamp_ms: int,
        jpeg_bytes: bytes,
    ) -> str:
        if not _SAFE_IDENTIFIER.fullmatch(session_id):
            raise ValueError("session_id contains an unsafe path character")
        if timestamp_ms < 0:
            raise ValueError("timestamp_ms must not be negative")
        if not jpeg_bytes.startswith(b"\xff\xd8") or not jpeg_bytes.endswith(
            b"\xff\xd9"
        ):
            raise ValueError("jpeg_bytes must contain an encoded JPEG image")
        session_directory = self.root_directory / session_id
        session_directory.mkdir(parents=True, exist_ok=True)
        target = session_directory / f"{timestamp_ms}.jpg"
        if target.exists():
            if target.read_bytes() != jpeg_bytes:
                raise EvidenceCollision(
                    f"evidence {session_id}/{timestamp_ms}.jpg already has other bytes"
                )
            return self._url(session_id, timestamp_ms)

        with NamedTemporaryFile(
            dir=session_directory,
            prefix=f".{timestamp_ms}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary.write(jpeg_bytes)
            temporary_path = Path(temporary.name)
        try:
            try:
                os.link(temporary_path, target)
            except FileExistsError:
                if target.read_bytes() != jpeg_bytes:
                    raise EvidenceCollision(
                        f"evidence {session_id}/{timestamp_ms}.jpg "
                        "already has other bytes"
                    )
        finally:
            temporary_path.unlink(missing_ok=True)
        return self._url(session_id, timestamp_ms)

    def _url(self, session_id: str, timestamp_ms: int) -> str:
        return f"{self.url_prefix}/{session_id}/{timestamp_ms}.jpg"

    def resolve_jpeg(self, session_id: str, timestamp_ms: int) -> Path | None:
        if not _SAFE_IDENTIFIER.fullmatch(session_id) or timestamp_ms < 0:
            return None
        path = self.root_directory / session_id / f"{timestamp_ms}.jpg"
        return path if path.is_file() else None

    def store_rectification_image(
        self,
        *,
        case_id: str,
        evidence_id: str,
        image_bytes: bytes,
        media_type: str,
    ) -> str:
        self._validate_identifier(case_id)
        self._validate_identifier(evidence_id)
        extension = _UPLOAD_MEDIA_EXTENSIONS.get(media_type)
        if extension is None:
            raise ValueError("unsupported rectification image media type")
        if not self._matches_media_type(image_bytes, media_type):
            raise ValueError("rectification image content does not match media type")

        directory = self.root_directory / "rectification" / case_id
        directory.mkdir(parents=True, exist_ok=True)
        for known_extension in _UPLOAD_MEDIA_EXTENSIONS.values():
            existing = directory / f"{evidence_id}.{known_extension}"
            if not existing.exists():
                continue
            if existing.suffix == f".{extension}" and existing.read_bytes() == image_bytes:
                return self._rectification_url(case_id, evidence_id)
            raise EvidenceCollision(
                f"rectification evidence {case_id}/{evidence_id} already has other bytes"
            )

        target = directory / f"{evidence_id}.{extension}"
        with NamedTemporaryFile(
            dir=directory,
            prefix=f".{evidence_id}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary.write(image_bytes)
            temporary_path = Path(temporary.name)
        try:
            try:
                os.link(temporary_path, target)
            except FileExistsError:
                if target.read_bytes() != image_bytes:
                    raise EvidenceCollision(
                        f"rectification evidence {case_id}/{evidence_id} "
                        "already has other bytes"
                    )
        finally:
            temporary_path.unlink(missing_ok=True)
        return self._rectification_url(case_id, evidence_id)

    def resolve_rectification_image(
        self, case_id: str, evidence_id: str
    ) -> tuple[Path, str] | None:
        if not (
            _SAFE_IDENTIFIER.fullmatch(case_id)
            and _SAFE_IDENTIFIER.fullmatch(evidence_id)
        ):
            return None
        directory = self.root_directory / "rectification" / case_id
        for media_type, extension in _UPLOAD_MEDIA_EXTENSIONS.items():
            path = directory / f"{evidence_id}.{extension}"
            if path.is_file():
                return path, media_type
        return None

    @staticmethod
    def _validate_identifier(identifier: str) -> None:
        if not _SAFE_IDENTIFIER.fullmatch(identifier):
            raise ValueError("identifier contains an unsafe path character")

    @staticmethod
    def _matches_media_type(image_bytes: bytes, media_type: str) -> bool:
        if media_type == "image/jpeg":
            return image_bytes.startswith(b"\xff\xd8") and image_bytes.endswith(b"\xff\xd9")
        if media_type == "image/png":
            return image_bytes.startswith(b"\x89PNG\r\n\x1a\n")
        if media_type == "image/webp":
            return (
                len(image_bytes) >= 12
                and image_bytes.startswith(b"RIFF")
                and image_bytes[8:12] == b"WEBP"
            )
        return False

    def _rectification_url(self, case_id: str, evidence_id: str) -> str:
        return f"{self.url_prefix}/rectification/{case_id}/{evidence_id}"
