from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict, JsonValue

from app.contracts import CandidateEvidence, PpeType
from app.domain.site_context import SiteContextPort


class ResolvedInvestigationContext(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    facts: dict[str, JsonValue]
    conflicts: list[str]
    missing_fields: list[str]
    applicable_task: str | None = None
    hazards: list[str]
    required_ppe: list[PpeType]
    zone_id: str | None = None
    zone_name: str | None = None
    exception_note: str | None = None
    rectification_window_minutes: int | None = None


class InvestigationResolverPort(Protocol):
    def resolve(
        self, candidate: CandidateEvidence, human_facts: dict[str, JsonValue]
    ) -> ResolvedInvestigationContext: ...


class DeterministicInvestigationResolver:
    def __init__(self, context: SiteContextPort) -> None:
        self._context = context

    def resolve(
        self,
        candidate: CandidateEvidence,
        human_facts: dict[str, JsonValue] | None = None,
    ) -> ResolvedInvestigationContext:
        facts: dict[str, JsonValue] = {
            "camera_id": candidate.camera_id,
            "occurred_at": candidate.occurred_at.isoformat(),
        }
        conflicts: list[str] = []
        missing: list[str] = []
        human_facts = human_facts or {}

        def append_unique(items: list[str], value: str) -> None:
            if value not in items:
                items.append(value)

        zone = self._context.get_zone_at(candidate.camera_id)
        if zone is None:
            append_unique(missing, "zone")
            return ResolvedInvestigationContext(
                facts=facts,
                conflicts=conflicts,
                missing_fields=missing,
                hazards=[],
                required_ppe=[],
            )

        facts.update(
            zone_id=zone.zone_id,
            zone_name=zone.name,
            zone_type=zone.zone_type,
        )
        human_task: str | None = None
        if "task_code" in human_facts:
            raw_task = human_facts["task_code"]
            if not isinstance(raw_task, str) or not raw_task.strip():
                append_unique(conflicts, "invalid_human_task_code")
            else:
                human_task = raw_task.strip()

        permits = sorted(
            self._context.find_active_work_permits(
                zone.zone_id, candidate.occurred_at
            ),
            key=lambda permit: permit.permit_id,
        )
        facts["active_permit_ids"] = [permit.permit_id for permit in permits]
        permit_tasks = list(dict.fromkeys(permit.task_code for permit in permits))
        task: str | None = None
        task_source: str | None = None
        if not permits:
            append_unique(missing, "active_work_permit")
            if human_task is None:
                append_unique(missing, "task_code")
            else:
                task, task_source = human_task, "human_fact"
        elif len(permit_tasks) == 1:
            task, task_source = permit_tasks[0], "active_work_permit"
            if human_task is not None and human_task != task:
                append_unique(conflicts, "human_task_conflicts_with_active_permit")
        else:
            append_unique(conflicts, "multiple_active_permit_tasks")

        if task is None:
            return ResolvedInvestigationContext(
                facts=facts,
                conflicts=conflicts,
                missing_fields=missing,
                hazards=[],
                required_ppe=[],
                zone_id=zone.zone_id,
                zone_name=zone.name,
            )

        facts["task_code"] = task
        facts["task_source"] = task_source
        matrix = self._context.get_task_ppe_matrix(task)
        if matrix is None:
            append_unique(missing, "task_ppe_matrix")
            return ResolvedInvestigationContext(
                facts=facts,
                conflicts=conflicts,
                missing_fields=missing,
                applicable_task=task,
                hazards=[],
                required_ppe=[],
                zone_id=zone.zone_id,
                zone_name=zone.name,
            )
        return ResolvedInvestigationContext(
            facts=facts,
            conflicts=conflicts,
            missing_fields=missing,
            applicable_task=task,
            hazards=list(matrix.hazards),
            required_ppe=list(matrix.required_ppe),
            zone_id=zone.zone_id,
            zone_name=zone.name,
            exception_note=matrix.exception_note,
            rectification_window_minutes=matrix.rectification_window_minutes,
        )
