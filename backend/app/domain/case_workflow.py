from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.contracts import (
    ActorRole,
    AssociationVerdict,
    ApproveClosure,
    ApproveRectification,
    CaseCommand,
    CaseSnapshot,
    CaseStatus,
    CaseTransition,
    InvestigationResult,
    RejectCase,
    RejectRecheck,
    RequestReinvestigation,
    SubmitFacts,
    SubmitRectificationEvidence,
    VlmReviewResult,
    VlmVerdict,
)
from app.domain.case_store import CaseStorePort


class ActorRolePort(Protocol):
    def role_for(self, actor_id: str) -> ActorRole | None: ...


@dataclass(frozen=True)
class RecordVlmReview:
    expected_version: int
    review: VlmReviewResult
    command_type: str = "RECORD_VLM_REVIEW"


@dataclass(frozen=True)
class StartInvestigation:
    expected_version: int
    command_type: str = "START_INVESTIGATION"


@dataclass(frozen=True)
class RecordInvestigation:
    expected_version: int
    investigation: InvestigationResult
    command_type: str = "RECORD_INVESTIGATION"


@dataclass(frozen=True)
class RestartInvestigation:
    expected_version: int
    command_type: str = "RESTART_INVESTIGATION"


WorkflowCommand = (
    CaseCommand
    | RecordVlmReview
    | StartInvestigation
    | RecordInvestigation
    | RestartInvestigation
)


class CaseWorkflowError(Exception):
    code = "CASE_WORKFLOW_ERROR"


class CaseNotFound(CaseWorkflowError):
    code = "CASE_NOT_FOUND"

    def __init__(self, case_id: str) -> None:
        super().__init__(f"case {case_id} was not found")


class StaleCaseVersion(CaseWorkflowError):
    code = "STALE_CASE_VERSION"

    def __init__(self, expected: int, current: int) -> None:
        super().__init__(f"expected version {expected}, current {current}")


class PermissionDenied(CaseWorkflowError):
    code = "PERMISSION_DENIED"

    def __init__(self, actor_id: str) -> None:
        super().__init__(f"actor {actor_id} cannot execute this command")


class CommandNotAllowed(CaseWorkflowError):
    code = "COMMAND_NOT_ALLOWED"

    def __init__(self, command_type: str, status: CaseStatus) -> None:
        super().__init__(f"{command_type} is not allowed from {status.value}")


class EvidenceRequired(CaseWorkflowError):
    code = "EVIDENCE_REQUIRED"

    def __init__(self, evidence_name: str) -> None:
        super().__init__(f"{evidence_name} is required")


class ReviewMismatch(CaseWorkflowError):
    code = "VLM_REVIEW_MISMATCH"

    def __init__(self, fields: list[str]) -> None:
        super().__init__("VLM review disagrees with case: " + ", ".join(fields))


class InvalidDeadline(CaseWorkflowError):
    code = "INVALID_DEADLINE"

    def __init__(self) -> None:
        super().__init__("rectification deadline must be in the future")


class CaseWorkflow:
    def __init__(
        self,
        store: CaseStorePort,
        actor_roles: ActorRolePort,
        clock: Callable[[], datetime],
    ) -> None:
        self._store = store
        self._actor_roles = actor_roles
        self._clock = clock

    def apply(self, case_id: str, command: WorkflowCommand) -> CaseSnapshot:
        snapshot = self._store.get(case_id)
        if snapshot is None:
            raise CaseNotFound(case_id)

        if command.expected_version != snapshot.version:
            raise StaleCaseVersion(command.expected_version, snapshot.version)

        if isinstance(command, RecordVlmReview):
            if snapshot.status is not CaseStatus.YOLO_CANDIDATE:
                raise CommandNotAllowed(command.command_type, snapshot.status)
            review = command.review
            mismatched = [
                field_name
                for field_name in (
                    "candidate_id",
                    "person_track_id",
                    "ppe_type",
                )
                if getattr(review, field_name)
                != getattr(snapshot.candidate, field_name)
            ]
            if mismatched:
                raise ReviewMismatch(mismatched)
            confirmed = (
                review.verdict is VlmVerdict.CONFIRMED
                and review.association is AssociationVerdict.MATCHED
                and review.body_part_visible
                and review.persistent
                and not review.poster_or_reflection
                and review.evidence_sufficient
            )
            target_status = (
                CaseStatus.VLM_REVIEWED
                if confirmed
                else CaseStatus.VLM_REJECTED
            )
            return self._commit_system_transition(
                snapshot,
                command.expected_version,
                target_status,
                review.reason,
                {"vlm_review": review},
            )

        if isinstance(command, StartInvestigation):
            if snapshot.status is not CaseStatus.VLM_REVIEWED:
                raise CommandNotAllowed(command.command_type, snapshot.status)
            return self._commit_system_transition(
                snapshot,
                command.expected_version,
                CaseStatus.INVESTIGATING,
                "启动 Agent 调查",
            )

        if isinstance(command, RecordInvestigation):
            if snapshot.status is not CaseStatus.INVESTIGATING:
                raise CommandNotAllowed(command.command_type, snapshot.status)
            investigation = command.investigation
            complete = (
                not investigation.missing_fields
                and not investigation.conflicts
                and bool(investigation.recommendation)
                and bool(investigation.citations)
            )
            target_status = (
                CaseStatus.PENDING_REVIEW
                if complete
                else CaseStatus.NEEDS_HUMAN_FACTS
            )
            return self._commit_system_transition(
                snapshot,
                command.expected_version,
                target_status,
                investigation.recommendation or "调查结果需要补充事实",
                {"investigation": investigation},
            )

        if isinstance(command, RestartInvestigation):
            if snapshot.status is not CaseStatus.REINVESTIGATE:
                raise CommandNotAllowed(command.command_type, snapshot.status)
            return self._commit_system_transition(
                snapshot,
                command.expected_version,
                CaseStatus.INVESTIGATING,
                "根据补充信息重新启动 Agent 调查",
            )

        if isinstance(command, ApproveRectification):
            if snapshot.status is not CaseStatus.PENDING_REVIEW:
                raise CommandNotAllowed(command.command_type, snapshot.status)
            actor_role = self._actor_roles.role_for(command.actor_id)
            if actor_role is not ActorRole.PROJECT_SAFETY_REVIEWER:
                raise PermissionDenied(command.actor_id)
            if command.rectification_due_at <= self._clock():
                raise InvalidDeadline()
            updated = snapshot.model_copy(
                update={
                    "status": CaseStatus.RECTIFICATION_OPEN,
                    "rectification_responsible_party_id": (
                        command.responsible_party_id
                    ),
                    "rectification_due_at": command.rectification_due_at,
                }
            )
            transition = CaseTransition(
                from_status=snapshot.status,
                to_status=CaseStatus.RECTIFICATION_OPEN,
                actor_id=command.actor_id,
                actor_role=actor_role,
                reason=command.reason,
                occurred_at=self._clock(),
            )
            return self._store.commit(
                updated,
                expected_version=command.expected_version,
                transition=transition,
            )

        if isinstance(command, (RejectCase, RequestReinvestigation)):
            if snapshot.status is not CaseStatus.PENDING_REVIEW:
                raise CommandNotAllowed(command.command_type, snapshot.status)
            actor_role = self._actor_roles.role_for(command.actor_id)
            if actor_role is not ActorRole.PROJECT_SAFETY_REVIEWER:
                raise PermissionDenied(command.actor_id)
            target_status = (
                CaseStatus.HUMAN_REJECTED
                if isinstance(command, RejectCase)
                else CaseStatus.REINVESTIGATE
            )
            updated = snapshot.model_copy(update={"status": target_status})
            transition = CaseTransition(
                from_status=snapshot.status,
                to_status=target_status,
                actor_id=command.actor_id,
                actor_role=actor_role,
                reason=command.reason,
                occurred_at=self._clock(),
            )
            return self._store.commit(
                updated,
                expected_version=command.expected_version,
                transition=transition,
            )

        if isinstance(command, SubmitRectificationEvidence):
            if snapshot.status is not CaseStatus.RECTIFICATION_OPEN:
                raise CommandNotAllowed(command.command_type, snapshot.status)
            actor_role = self._actor_roles.role_for(command.actor_id)
            if actor_role is not ActorRole.SITE_SAFETY_OFFICER:
                raise PermissionDenied(command.actor_id)
            updated = snapshot.model_copy(
                update={
                    "status": CaseStatus.RECHECK_PENDING,
                    "rectification_description": command.description,
                    "rectification_evidence": [
                        *snapshot.rectification_evidence,
                        *command.evidence,
                    ],
                }
            )
            transition = CaseTransition(
                from_status=snapshot.status,
                to_status=CaseStatus.RECHECK_PENDING,
                actor_id=command.actor_id,
                actor_role=actor_role,
                reason=command.reason,
                occurred_at=self._clock(),
            )
            return self._store.commit(
                updated,
                expected_version=command.expected_version,
                transition=transition,
            )

        if isinstance(command, ApproveClosure):
            if snapshot.status is not CaseStatus.RECHECK_PENDING:
                raise CommandNotAllowed(command.command_type, snapshot.status)
            actor_role = self._actor_roles.role_for(command.actor_id)
            if actor_role is not ActorRole.PROJECT_SAFETY_REVIEWER:
                raise PermissionDenied(command.actor_id)
            if not snapshot.rectification_evidence:
                raise EvidenceRequired("rectification evidence")
            updated = snapshot.model_copy(
                update={
                    "status": CaseStatus.CLOSED,
                    "recheck_conclusion": command.recheck_conclusion,
                }
            )
            transition = CaseTransition(
                from_status=snapshot.status,
                to_status=CaseStatus.CLOSED,
                actor_id=command.actor_id,
                actor_role=actor_role,
                reason=command.reason,
                occurred_at=self._clock(),
            )
            return self._store.commit(
                updated,
                expected_version=command.expected_version,
                transition=transition,
            )

        if isinstance(command, RejectRecheck):
            if snapshot.status is not CaseStatus.RECHECK_PENDING:
                raise CommandNotAllowed(command.command_type, snapshot.status)
            actor_role = self._actor_roles.role_for(command.actor_id)
            if actor_role is not ActorRole.PROJECT_SAFETY_REVIEWER:
                raise PermissionDenied(command.actor_id)
            updated = snapshot.model_copy(
                update={
                    "status": CaseStatus.RECTIFICATION_OPEN,
                    "recheck_conclusion": command.recheck_conclusion,
                }
            )
            transition = CaseTransition(
                from_status=snapshot.status,
                to_status=CaseStatus.RECTIFICATION_OPEN,
                actor_id=command.actor_id,
                actor_role=actor_role,
                reason=command.reason,
                occurred_at=self._clock(),
            )
            return self._store.commit(
                updated,
                expected_version=command.expected_version,
                transition=transition,
            )

        if not isinstance(command, SubmitFacts):
            raise NotImplementedError(command.command_type)

        if snapshot.status is not CaseStatus.NEEDS_HUMAN_FACTS:
            raise CommandNotAllowed(command.command_type, snapshot.status)

        actor_role = self._actor_roles.role_for(command.actor_id)
        if actor_role is not ActorRole.SITE_SAFETY_OFFICER:
            raise PermissionDenied(command.actor_id)

        updated = snapshot.model_copy(
            update={
                "status": CaseStatus.REINVESTIGATE,
                "human_facts": {**snapshot.human_facts, **command.facts},
            }
        )
        transition = CaseTransition(
            from_status=snapshot.status,
            to_status=CaseStatus.REINVESTIGATE,
            actor_id=command.actor_id,
            actor_role=actor_role,
            reason=command.reason,
            occurred_at=self._clock(),
        )
        return self._store.commit(
            updated,
            expected_version=command.expected_version,
            transition=transition,
        )

    def _commit_system_transition(
        self,
        snapshot: CaseSnapshot,
        expected_version: int,
        target_status: CaseStatus,
        reason: str,
        updates: dict[str, object] | None = None,
    ) -> CaseSnapshot:
        updated = snapshot.model_copy(
            update={"status": target_status, **(updates or {})}
        )
        transition = CaseTransition(
            from_status=snapshot.status,
            to_status=target_status,
            reason=reason,
            occurred_at=self._clock(),
        )
        return self._store.commit(
            updated,
            expected_version=expected_version,
            transition=transition,
        )
