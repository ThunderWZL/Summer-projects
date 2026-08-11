from __future__ import annotations

import os
import re
from pathlib import Path
from tempfile import NamedTemporaryFile


_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9._-]+$")


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
