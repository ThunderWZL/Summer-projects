from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.adapters.database.models import CitationModel, InvestigationModel
from app.contracts import InvestigationResult


def investigation_record_values(
    result: InvestigationResult,
) -> dict[str, Any]:
    """Map the frozen investigation contract onto existing ORM columns.

    ``facts_json`` is an explicit envelope instead of a flat merge so arbitrary
    fact keys cannot overwrite deterministic resolver output. Citations remain
    in the dedicated ``citations`` table and are therefore not duplicated here.
    """

    return {
        "facts_json": {
            "facts": result.facts,
            "applicable_task": result.applicable_task,
            "hazards": result.hazards,
            "required_ppe": [ppe.value for ppe in result.required_ppe],
            "rectification_recommendation": (
                result.rectification_recommendation.model_dump(mode="json")
                if result.rectification_recommendation is not None
                else None
            ),
        },
        "conflicts_json": result.conflicts,
        "missing_fields_json": result.missing_fields,
        "recommendation": result.recommendation,
        "trace_json": result.tool_trace,
    }


def investigation_result_from_record(
    investigation: InvestigationModel,
    citations: Sequence[CitationModel],
) -> InvestigationResult:
    """Rebuild the frozen investigation contract from persisted ORM records."""

    envelope = investigation.facts_json
    return InvestigationResult.model_validate(
        {
            "facts": envelope["facts"],
            "conflicts": investigation.conflicts_json,
            "missing_fields": investigation.missing_fields_json,
            "applicable_task": envelope["applicable_task"],
            "hazards": envelope["hazards"],
            "required_ppe": envelope["required_ppe"],
            "recommendation": investigation.recommendation,
            "rectification_recommendation": envelope[
                "rectification_recommendation"
            ],
            "citations": [
                {
                    "document_title": citation.document_title,
                    "standard_no": citation.standard_no,
                    "section": citation.section,
                    "effective_date": citation.effective_date,
                    "source_url": citation.source_url,
                    "excerpt": citation.excerpt,
                }
                for citation in citations
            ],
            "tool_trace": investigation.trace_json,
        }
    )
