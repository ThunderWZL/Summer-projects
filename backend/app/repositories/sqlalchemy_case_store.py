from __future__ import annotations

from typing import Any

from sqlalchemy import Select, and_, case, delete, func, or_, select, update
from sqlalchemy.orm import Session, sessionmaker
from pydantic import TypeAdapter

from app.adapters.database.mappers import (
    investigation_record_values,
    investigation_result_from_record,
)
from app.adapters.database.models import (
    CaseEvidenceModel,
    CaseModel,
    CaseTransitionModel,
    CitationModel,
    HumanSubmissionModel,
    InvestigationModel,
    VlmReviewModel,
)
from app.adapters.database.session import session_scope
from app.contracts import (
    CandidateEvidence,
    CaseSnapshot,
    CaseStatus,
    CaseTransition,
    HumanSubmissionRecord,
    HumanSubmissionType,
    InvestigationResult,
    RectificationEvidence,
    VlmReviewResult,
)
from app.domain.case_store import CasePage, CaseQuery
from app.domain.case_workflow import StaleCaseVersion


TERMINAL_STATUSES = (
    CaseStatus.VLM_REJECTED,
    CaseStatus.HUMAN_REJECTED,
    CaseStatus.CLOSED,
)
HUMAN_ACTION_STATUSES = (
    CaseStatus.NEEDS_HUMAN_FACTS,
    CaseStatus.PENDING_REVIEW,
    CaseStatus.RECTIFICATION_OPEN,
    CaseStatus.RECHECK_PENDING,
)
_SNAPSHOT_JSON_FORMAT = "case-snapshot-fields-v1"
_HUMAN_SUBMISSION_ADAPTER = TypeAdapter(HumanSubmissionRecord)


class SqlAlchemyCaseStore:
    """Persist complete case aggregates behind the frozen ``CaseStorePort``."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def create(self, snapshot: CaseSnapshot) -> CaseSnapshot:
        with session_scope(self._session_factory) as session:
            session.add(self._case_record(snapshot))
            self._replace_candidate_evidence(session, snapshot)
            self._replace_vlm_review(session, snapshot)
            self._replace_investigation(session, snapshot)
            for index, transition in enumerate(snapshot.transitions, start=1):
                session.add(
                    self._transition_record(snapshot.case_id, index, transition)
                )
            session.flush()
            return self._load_snapshot(session, snapshot.case_id)

    def get(self, case_id: str) -> CaseSnapshot | None:
        with self._session_factory() as session:
            if session.get(CaseModel, case_id) is None:
                return None
            return self._load_snapshot(session, case_id)

    def commit(
        self,
        snapshot: CaseSnapshot,
        expected_version: int,
        transition: CaseTransition,
    ) -> CaseSnapshot:
        with session_scope(self._session_factory) as session:
            values = self._case_values(snapshot)
            values.update(
                version=expected_version + 1,
                updated_at=transition.occurred_at,
            )
            result = session.execute(
                update(CaseModel)
                .where(
                    CaseModel.id == snapshot.case_id,
                    CaseModel.version == expected_version,
                )
                .values(**values)
            )
            if result.rowcount != 1:
                current = session.scalar(
                    select(CaseModel.version).where(
                        CaseModel.id == snapshot.case_id
                    )
                )
                if current is None:
                    raise KeyError(snapshot.case_id)
                raise StaleCaseVersion(expected_version, current)

            self._replace_candidate_evidence(session, snapshot)
            self._replace_vlm_review(session, snapshot)
            self._replace_investigation(session, snapshot)
            session.add(
                self._transition_record(
                    snapshot.case_id,
                    expected_version + 1,
                    transition,
                )
            )
            session.flush()
            return self._load_snapshot(session, snapshot.case_id)

    def list(self, query: CaseQuery) -> CasePage:
        with self._session_factory() as session:
            statement = self._apply_filters(select(CaseModel), query)
            total_items = session.scalar(
                select(func.count()).select_from(statement.subquery())
            )
            ordered = self._apply_ordering(statement, query)
            records = session.scalars(
                ordered.offset((query.page - 1) * query.page_size).limit(
                    query.page_size
                )
            ).all()
            return CasePage(
                items=tuple(
                    self._load_snapshot(session, record.id)
                    for record in records
                ),
                total_items=total_items or 0,
            )

    def find_by_candidate(self, candidate_id: str) -> CaseSnapshot | None:
        with self._session_factory() as session:
            case_id = session.scalar(
                select(CaseModel.id).where(
                    CaseModel.candidate_id == candidate_id
                )
            )
            return (
                self._load_snapshot(session, case_id)
                if case_id is not None
                else None
            )

    def add_submission(
        self, submission: HumanSubmissionRecord
    ) -> HumanSubmissionRecord:
        payload = submission.model_dump(mode="json")
        with session_scope(self._session_factory) as session:
            session.add(
                HumanSubmissionModel(
                    id=submission.submission_id,
                    case_id=submission.case_id,
                    actor_id=submission.actor_id,
                    kind=HumanSubmissionType(submission.submission_type),
                    payload_json=payload,
                    created_at=submission.created_at,
                )
            )
            session.flush()
        return submission.model_copy(deep=True)

    def list_submissions(self, case_id: str) -> list[HumanSubmissionRecord]:
        with self._session_factory() as session:
            records = session.scalars(
                select(HumanSubmissionModel)
                .where(HumanSubmissionModel.case_id == case_id)
                .order_by(
                    HumanSubmissionModel.created_at,
                    HumanSubmissionModel.id,
                )
            ).all()
            return [
                _HUMAN_SUBMISSION_ADAPTER.validate_python(record.payload_json)
                for record in records
            ]

    @staticmethod
    def _case_values(snapshot: CaseSnapshot) -> dict[str, Any]:
        candidate = snapshot.candidate
        return {
            "candidate_id": candidate.candidate_id,
            "session_id": snapshot.session_id,
            "camera_id": snapshot.camera_id,
            "person_track_id": snapshot.person_track_id,
            "ppe_type": snapshot.ppe_type,
            "evidence_kind": candidate.evidence_kind,
            "confidence": candidate.confidence,
            "model_name": candidate.model_name,
            "model_version": candidate.model_version,
            "weights_sha256": candidate.weights_sha256,
            "aggregation_method": candidate.aggregation_method,
            "aggregation_parameters_json": candidate.aggregation_parameters,
            "occurred_at": candidate.occurred_at,
            "first_seen_ms": candidate.first_seen_ms,
            "last_seen_ms": candidate.last_seen_ms,
            "status": snapshot.status,
            "human_facts_json": {
                "format": _SNAPSHOT_JSON_FORMAT,
                "human_facts": snapshot.human_facts,
                "rectification_evidence": [
                    item.model_dump(mode="json")
                    for item in snapshot.rectification_evidence
                ],
            },
            "rectification_responsible_party_id": (
                snapshot.rectification_responsible_party_id
            ),
            "rectification_due_at": snapshot.rectification_due_at,
            "rectification_description": snapshot.rectification_description,
            "recheck_conclusion": snapshot.recheck_conclusion,
            "created_at": snapshot.created_at,
        }

    @classmethod
    def _case_record(cls, snapshot: CaseSnapshot) -> CaseModel:
        return CaseModel(
            id=snapshot.case_id,
            version=snapshot.version,
            updated_at=snapshot.updated_at,
            **cls._case_values(snapshot),
        )

    @staticmethod
    def _replace_candidate_evidence(
        session: Session, snapshot: CaseSnapshot
    ) -> None:
        session.execute(
            delete(CaseEvidenceModel).where(
                CaseEvidenceModel.case_id == snapshot.case_id
            )
        )
        for index, frame in enumerate(snapshot.candidate.frames, start=1):
            dumped = frame.model_dump(mode="json")
            session.add(
                CaseEvidenceModel(
                    id=f"{snapshot.case_id}-candidate-frame-{index}",
                    case_id=snapshot.case_id,
                    kind=frame.frame_role,
                    timestamp_ms=frame.timestamp_ms,
                    path=frame.image_url,
                    metadata_json={
                        key: dumped[key]
                        for key in (
                            "image_width",
                            "image_height",
                            "person_box",
                            "observation_box",
                            "observation_confidence",
                        )
                    },
                )
            )

    @staticmethod
    def _replace_vlm_review(session: Session, snapshot: CaseSnapshot) -> None:
        session.execute(
            delete(VlmReviewModel).where(
                VlmReviewModel.case_id == snapshot.case_id
            )
        )
        review = snapshot.vlm_review
        if review is not None:
            session.add(
                VlmReviewModel(
                    case_id=snapshot.case_id,
                    verdict=review.verdict,
                    result_json=review.model_dump(mode="json"),
                    model_name=review.model_name,
                    created_at=review.reviewed_at,
                )
            )

    @staticmethod
    def _replace_investigation(
        session: Session, snapshot: CaseSnapshot
    ) -> None:
        session.execute(
            delete(CitationModel).where(
                CitationModel.case_id == snapshot.case_id
            )
        )
        session.execute(
            delete(InvestigationModel).where(
                InvestigationModel.case_id == snapshot.case_id
            )
        )
        investigation = snapshot.investigation
        if investigation is None:
            return
        session.add(
            InvestigationModel(
                id=f"{snapshot.case_id}-investigation",
                case_id=snapshot.case_id,
                **investigation_record_values(investigation),
            )
        )
        for index, citation in enumerate(investigation.citations, start=1):
            session.add(
                CitationModel(
                    id=f"{snapshot.case_id}-citation-{index}",
                    case_id=snapshot.case_id,
                    **citation.model_dump(),
                )
            )

    @staticmethod
    def _transition_record(
        case_id: str, sequence: int, transition: CaseTransition
    ) -> CaseTransitionModel:
        return CaseTransitionModel(
            id=f"{case_id}-transition-{sequence}",
            case_id=case_id,
            from_status=transition.from_status,
            to_status=transition.to_status,
            actor_id=transition.actor_id,
            actor_role=transition.actor_role,
            reason=transition.reason,
            created_at=transition.occurred_at,
        )

    def _load_snapshot(self, session: Session, case_id: str) -> CaseSnapshot:
        record = session.get(CaseModel, case_id)
        if record is None:
            raise KeyError(case_id)

        evidence = session.scalars(
            select(CaseEvidenceModel)
            .where(CaseEvidenceModel.case_id == case_id)
            .order_by(CaseEvidenceModel.timestamp_ms, CaseEvidenceModel.id)
        ).all()
        candidate = CandidateEvidence.model_validate(
            {
                "candidate_id": record.candidate_id,
                "session_id": record.session_id,
                "camera_id": record.camera_id,
                "person_track_id": record.person_track_id,
                "ppe_type": record.ppe_type,
                "evidence_kind": record.evidence_kind,
                "confidence": record.confidence,
                "model_name": record.model_name,
                "model_version": record.model_version,
                "weights_sha256": record.weights_sha256,
                "aggregation_method": record.aggregation_method,
                "aggregation_parameters": record.aggregation_parameters_json,
                "occurred_at": record.occurred_at,
                "first_seen_ms": record.first_seen_ms,
                "last_seen_ms": record.last_seen_ms,
                "frames": [
                    {
                        "timestamp_ms": item.timestamp_ms,
                        "image_url": item.path,
                        "frame_role": item.kind,
                        **item.metadata_json,
                    }
                    for item in evidence
                ],
            }
        )

        review_record = session.get(VlmReviewModel, case_id)
        vlm_review = (
            VlmReviewResult.model_validate(review_record.result_json)
            if review_record is not None
            else None
        )
        investigation_record = session.scalar(
            select(InvestigationModel).where(
                InvestigationModel.case_id == case_id
            )
        )
        investigation: InvestigationResult | None = None
        if investigation_record is not None:
            citations = session.scalars(
                select(CitationModel)
                .where(CitationModel.case_id == case_id)
                .order_by(CitationModel.id)
            ).all()
            investigation = investigation_result_from_record(
                investigation_record, citations
            )

        transitions = session.scalars(
            select(CaseTransitionModel)
            .where(CaseTransitionModel.case_id == case_id)
            .order_by(
                CaseTransitionModel.created_at,
                CaseTransitionModel.id,
            )
        ).all()
        human_facts, rectification_evidence = self._snapshot_json_fields(
            record.human_facts_json
        )
        return CaseSnapshot(
            case_id=record.id,
            session_id=record.session_id,
            camera_id=record.camera_id,
            person_track_id=record.person_track_id,
            ppe_type=record.ppe_type,
            status=record.status,
            version=record.version,
            candidate=candidate,
            vlm_review=vlm_review,
            investigation=investigation,
            human_facts=human_facts,
            rectification_responsible_party_id=(
                record.rectification_responsible_party_id
            ),
            rectification_due_at=record.rectification_due_at,
            rectification_evidence=rectification_evidence,
            rectification_description=record.rectification_description,
            recheck_conclusion=record.recheck_conclusion,
            created_at=record.created_at,
            updated_at=record.updated_at,
            transitions=[
                CaseTransition(
                    from_status=item.from_status,
                    to_status=item.to_status,
                    actor_id=item.actor_id,
                    actor_role=item.actor_role,
                    reason=item.reason,
                    occurred_at=item.created_at,
                )
                for item in transitions
            ],
        )

    @staticmethod
    def _snapshot_json_fields(
        value: dict[str, Any],
    ) -> tuple[dict[str, Any], list[RectificationEvidence]]:
        if value.get("format") != _SNAPSHOT_JSON_FORMAT:
            return value, []
        return (
            value.get("human_facts", {}),
            [
                RectificationEvidence.model_validate(item)
                for item in value.get("rectification_evidence", [])
            ],
        )

    @staticmethod
    def _apply_filters(
        statement: Select[tuple[CaseModel]], query: CaseQuery
    ) -> Select[tuple[CaseModel]]:
        if query.status is not None:
            statement = statement.where(CaseModel.status == query.status)
        if query.ppe_type is not None:
            statement = statement.where(CaseModel.ppe_type == query.ppe_type)
        if query.camera_ids is not None:
            statement = statement.where(CaseModel.camera_id.in_(query.camera_ids))
        if query.responsible_party_id is not None:
            statement = statement.where(
                CaseModel.rectification_responsible_party_id
                == query.responsible_party_id
            )
        if query.occurred_from is not None:
            statement = statement.where(
                CaseModel.occurred_at >= query.occurred_from
            )
        if query.occurred_to is not None:
            statement = statement.where(CaseModel.occurred_at <= query.occurred_to)
        if query.overdue_only:
            statement = statement.where(
                SqlAlchemyCaseStore._overdue_expression(query)
            )
        if query.keyword:
            keyword = f"%{query.keyword.casefold()}%"
            statement = statement.where(
                or_(
                    func.lower(CaseModel.id).like(keyword),
                    func.lower(CaseModel.camera_id).like(keyword),
                    func.lower(CaseModel.person_track_id).like(keyword),
                    func.lower(
                        CaseModel.rectification_responsible_party_id
                    ).like(keyword),
                )
            )
        return statement

    @staticmethod
    def _apply_ordering(
        statement: Select[tuple[CaseModel]], query: CaseQuery
    ) -> Select[tuple[CaseModel]]:
        return statement.order_by(
            case(
                (SqlAlchemyCaseStore._overdue_expression(query), 0),
                else_=1,
            ),
            case((CaseModel.status.in_(HUMAN_ACTION_STATUSES), 0), else_=1),
            CaseModel.occurred_at,
            CaseModel.id,
        )

    @staticmethod
    def _overdue_expression(query: CaseQuery) -> Any:
        if query.as_of is None:
            return False
        return and_(
            CaseModel.rectification_due_at.is_not(None),
            CaseModel.rectification_due_at < query.as_of,
            CaseModel.status.not_in(TERMINAL_STATUSES),
        )
