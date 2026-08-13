from __future__ import annotations

from typing import Protocol

from app.contracts import InvestigationResult


class InvestigationError(RuntimeError):
    """Base error raised while producing an investigation result."""


class InvestigationCaseNotFound(InvestigationError):
    pass


class InvestigationAgentFailed(InvestigationError):
    pass


class InvestigationAgentOutputInvalid(InvestigationAgentFailed):
    pass


class InvestigationToolRoundsExceeded(InvestigationAgentFailed):
    pass


class InvestigationPort(Protocol):
    def investigate(self, case_id: str) -> InvestigationResult: ...
