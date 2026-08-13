from __future__ import annotations

from datetime import datetime

import pytest

from app.contracts import (
    CandidateEvidence,
    CaseSnapshot,
    CaseStatus,
    InvestigationResult,
    PpeType,
)
from app.domain.case_workflow import CaseWorkflow, RecordInvestigation
from app.domain.inmemory.case_store import InMemoryCaseStore
from app.domain.inmemory.site_context import MemorySiteContext
from app.domain.resolver import DeterministicInvestigationResolver
from app.domain.site_context import WorkPermit


SCENARIO_TIME = datetime.fromisoformat("2026-08-07T10:00:00+08:00")


def make_candidate(camera_id: str) -> CandidateEvidence:
    return CandidateEvidence.model_validate(
        {
            "candidate_id": f"candidate-{camera_id}",
            "session_id": "session-01",
            "camera_id": camera_id,
            "person_track_id": "track-17",
            "ppe_type": "gloves",
            "evidence_kind": "MISSING_POSITIVE_ASSOCIATION",
            "confidence": 0.91,
            "model_name": "ppe-yolo",
            "weights_sha256": "a" * 64,
            "aggregation_method": "weighted_mean",
            "aggregation_parameters": {"minimum_frames": 3},
            "occurred_at": SCENARIO_TIME.isoformat(),
            "first_seen_ms": 1_000,
            "last_seen_ms": 2_000,
            "frames": [
                {
                    "timestamp_ms": 1_500,
                    "image_url": "/evidence/key.jpg",
                    "image_width": 1920,
                    "image_height": 1080,
                    "frame_role": "REPRESENTATIVE",
                    "person_box": {"x1": 10, "y1": 20, "x2": 110, "y2": 220},
                }
            ],
        }
    )


def test_default_profile_resolves_rebar_and_rotating_equipment_differently() -> None:
    resolver = DeterministicInvestigationResolver(MemorySiteContext())

    rebar = resolver.resolve(make_candidate("CAM-03"))
    rotating = resolver.resolve(make_candidate("CAM-04"))

    assert rebar.applicable_task == "HANDLING_REBAR"
    assert PpeType.GLOVES in rebar.required_ppe
    assert rotating.applicable_task == "ROTATING_EQUIPMENT_OPERATION"
    assert PpeType.GLOVES not in rotating.required_ppe
    assert rotating.exception_note


def test_same_resolver_input_is_deterministic() -> None:
    resolver = DeterministicInvestigationResolver(MemorySiteContext())
    candidate = make_candidate("CAM-03")

    first = resolver.resolve(candidate, {"required_ppe": ["helmet"]})
    second = resolver.resolve(candidate, {"required_ppe": ["helmet"]})

    assert first == second


def test_unknown_camera_reports_only_missing_zone() -> None:
    result = DeterministicInvestigationResolver(MemorySiteContext()).resolve(
        make_candidate("CAM-99")
    )

    assert result.missing_fields == ["zone"]
    assert result.conflicts == []
    assert result.applicable_task is None
    assert result.hazards == []
    assert result.required_ppe == []


def test_zone_without_permit_or_human_task_requests_both_facts() -> None:
    result = DeterministicInvestigationResolver(MemorySiteContext()).resolve(
        make_candidate("CAM-01")
    )

    assert result.missing_fields == ["active_work_permit", "task_code"]
    assert result.applicable_task is None


def test_valid_human_task_is_resolved_but_does_not_replace_missing_permit() -> None:
    result = DeterministicInvestigationResolver(MemorySiteContext()).resolve(
        make_candidate("CAM-01"), {"task_code": "HANDLING_REBAR"}
    )

    assert result.missing_fields == ["active_work_permit"]
    assert result.conflicts == []
    assert result.applicable_task == "HANDLING_REBAR"
    assert result.required_ppe == [PpeType.GLOVES]


def test_human_task_matching_active_permit_has_no_conflict() -> None:
    result = DeterministicInvestigationResolver(MemorySiteContext()).resolve(
        make_candidate("CAM-03"), {"task_code": "HANDLING_REBAR"}
    )

    assert result.conflicts == []
    assert result.applicable_task == "HANDLING_REBAR"


def test_active_permit_wins_when_human_task_conflicts() -> None:
    result = DeterministicInvestigationResolver(MemorySiteContext()).resolve(
        make_candidate("CAM-03"),
        {"task_code": "ROTATING_EQUIPMENT_OPERATION"},
    )

    assert result.conflicts == ["human_task_conflicts_with_active_permit"]
    assert result.applicable_task == "HANDLING_REBAR"
    assert result.required_ppe == [PpeType.GLOVES]


def test_non_whitelisted_human_fields_cannot_change_resolver_output() -> None:
    resolver = DeterministicInvestigationResolver(MemorySiteContext())

    baseline = resolver.resolve(make_candidate("CAM-04"))
    forged = resolver.resolve(
        make_candidate("CAM-04"),
        {
            "required_ppe": ["gloves"],
            "hazards": ["伪造危害"],
            "applicable_task": "HANDLING_REBAR",
        },
    )

    assert forged == baseline


@pytest.mark.parametrize("task_code", [123, "", "   "])
def test_invalid_human_task_code_is_a_fixed_conflict(task_code: object) -> None:
    result = DeterministicInvestigationResolver(MemorySiteContext()).resolve(
        make_candidate("CAM-01"), {"task_code": task_code}
    )

    assert result.conflicts == ["invalid_human_task_code"]
    assert result.missing_fields == ["active_work_permit", "task_code"]
    assert result.applicable_task is None


class MultiplePermitContext(MemorySiteContext):
    def find_active_work_permits(
        self, zone_id: str, occurred_at: datetime
    ) -> list[WorkPermit]:
        original = super().find_active_work_permits(zone_id, occurred_at)
        if zone_id != "zone-03":
            return original
        return [
            *original,
            WorkPermit(
                permit_id="wp-0302",
                zone_id="zone-03",
                task_code="ROTATING_EQUIPMENT_OPERATION",
                hazards=["卷入风险"],
                responsible_party_id="team-mechanical-01",
                starts_at=datetime.fromisoformat("2026-08-07T08:00:00+08:00"),
                ends_at=datetime.fromisoformat("2026-08-07T18:00:00+08:00"),
            ),
        ]


def test_multiple_different_permit_tasks_report_conflict_without_selecting_task() -> None:
    result = DeterministicInvestigationResolver(MultiplePermitContext()).resolve(
        make_candidate("CAM-03")
    )

    assert result.conflicts == ["multiple_active_permit_tasks"]
    assert result.applicable_task is None
    assert result.hazards == []
    assert result.required_ppe == []


class MissingMatrixContext(MemorySiteContext):
    def get_task_ppe_matrix(self, task_code: str):
        if task_code == "HANDLING_REBAR":
            return None
        return super().get_task_ppe_matrix(task_code)


def test_missing_matrix_retains_task_but_has_no_derived_applicability() -> None:
    result = DeterministicInvestigationResolver(MissingMatrixContext()).resolve(
        make_candidate("CAM-03")
    )

    assert result.missing_fields == ["task_ppe_matrix"]
    assert result.applicable_task == "HANDLING_REBAR"
    assert result.hazards == []
    assert result.required_ppe == []


def test_results_do_not_share_mutable_lists_with_context_or_each_other() -> None:
    context = MemorySiteContext()
    resolver = DeterministicInvestigationResolver(context)
    first = resolver.resolve(make_candidate("CAM-03"))

    first.hazards.append("被测试修改")
    first.required_ppe.append(PpeType.HELMET)
    second = resolver.resolve(make_candidate("CAM-03"))
    matrix = context.get_task_ppe_matrix("HANDLING_REBAR")

    assert matrix is not None
    assert second.hazards == ["手部伤害风险"]
    assert second.required_ppe == [PpeType.GLOVES]
    assert matrix.hazards == ["手部伤害风险"]
    assert matrix.required_ppe == [PpeType.GLOVES]


class ChangedCurrentContext(MemorySiteContext):
    def find_active_work_permits(
        self, zone_id: str, occurred_at: datetime
    ) -> list[WorkPermit]:
        permits = super().find_active_work_permits(zone_id, occurred_at)
        if zone_id != "zone-03":
            return permits
        return [
            permit.model_copy(
                update={"task_code": "ROTATING_EQUIPMENT_OPERATION"}, deep=True
            )
            for permit in permits
        ]


class NoActorRoles:
    def role_for(self, actor_id: str):
        return None


def test_recorded_investigation_keeps_old_applicability_after_config_changes() -> None:
    candidate = make_candidate("CAM-03")
    old = DeterministicInvestigationResolver(MemorySiteContext()).resolve(candidate)
    investigation = InvestigationResult(
        facts=old.facts,
        conflicts=old.conflicts,
        missing_fields=old.missing_fields,
        applicable_task=old.applicable_task,
        hazards=old.hazards,
        required_ppe=old.required_ppe,
        recommendation="钢筋搬运时应佩戴手套",
        citations=[
            {
                "document_title": "个体防护装备配备规范",
                "section": "手部防护",
                "source_url": "https://example.test/ppe",
                "excerpt": "存在手部伤害风险时应配备手部防护。",
            }
        ],
        tool_trace=["search_authoritative_requirements"],
    )
    store = InMemoryCaseStore()
    store.create(
        CaseSnapshot(
            case_id="case-history",
            session_id=candidate.session_id,
            camera_id=candidate.camera_id,
            person_track_id=candidate.person_track_id,
            ppe_type=candidate.ppe_type,
            status=CaseStatus.INVESTIGATING,
            version=3,
            candidate=candidate,
            created_at=candidate.occurred_at,
            updated_at=candidate.occurred_at,
        )
    )
    workflow = CaseWorkflow(
        store=store,
        actor_roles=NoActorRoles(),
        clock=lambda: SCENARIO_TIME,
        responsible_party_is_eligible=lambda _case, _party_id: True,
    )

    workflow.apply("case-history", RecordInvestigation(3, investigation))
    current = DeterministicInvestigationResolver(ChangedCurrentContext()).resolve(
        candidate
    )
    stored = store.get("case-history")

    assert current.applicable_task == "ROTATING_EQUIPMENT_OPERATION"
    assert stored is not None
    assert stored.investigation is not None
    assert stored.investigation.applicable_task == "HANDLING_REBAR"
    assert stored.investigation.hazards == ["手部伤害风险"]
    assert stored.investigation.required_ppe == [PpeType.GLOVES]
