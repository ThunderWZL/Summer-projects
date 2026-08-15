from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol

from app.contracts import AnalysisEvent, AnalysisStage


class VideoAnalysisError(Exception):
    code: str


class AnalysisVideoNotFound(VideoAnalysisError):
    code = "ANALYSIS_VIDEO_NOT_FOUND"

    def __init__(self, video_id: str) -> None:
        super().__init__(f"analysis video {video_id} was not found")


class AnalysisSessionNotFound(VideoAnalysisError):
    code = "ANALYSIS_SESSION_NOT_FOUND"

    def __init__(self, session_id: str) -> None:
        super().__init__(f"analysis session {session_id} was not found")


class AnalysisSessionNotActive(VideoAnalysisError):
    code = "ANALYSIS_SESSION_NOT_ACTIVE"

    def __init__(self, session_id: str) -> None:
        super().__init__(f"analysis session {session_id} is not active")


@dataclass(frozen=True, slots=True)
class AnalysisSession:
    session_id: str
    video_id: str
    stage: AnalysisStage


class VideoAnalysisPort(Protocol):
    async def start_session(self, video_id: str) -> AnalysisSession: ...

    def get_stream(self, session_id: str) -> AsyncIterator[bytes]: ...

    def subscribe_events(self, session_id: str) -> AsyncIterator[AnalysisEvent]: ...

    async def stop_session(self, session_id: str) -> AnalysisSession: ...
