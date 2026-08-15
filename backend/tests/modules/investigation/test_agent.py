from __future__ import annotations

import json
import sys
from datetime import datetime
from types import SimpleNamespace

import pytest

from app.contracts import Citation, PpeType
from app.domain.inmemory.site_context import MemorySiteContext
from app.domain.investigation import (
    InvestigationAgentOutputInvalid,
    InvestigationToolRoundsExceeded,
)
from app.domain.requirements_rag import RequirementQuery
from app.modules.investigation.agent import (
    AgentInvestigationContext,
    InvestigationAgent,
    DeepSeekChatModelAdapter,
    ScriptedFakeChatModel,
)
from app.modules.investigation.tools import InvestigationTools


def make_context() -> AgentInvestigationContext:
    return AgentInvestigationContext(
        case_id="case-03",
        zone_id="zone-03",
        zone_name="钢筋区",
        occurred_at=datetime.fromisoformat("2026-08-07T10:00:00+08:00"),
        ppe_type=PpeType.GLOVES,
        applicable_task="HANDLING_REBAR",
        hazards=["手部伤害风险"],
        required_ppe=[PpeType.GLOVES],
        rectification_window_minutes=30,
    )


def make_citation(excerpt: str = "钢筋搬运应根据风险配备手部防护。") -> Citation:
    return Citation(
        document_title="个体防护装备配备规范",
        standard_no="GB 39800.12-2025",
        section="手部防护",
        source_url="https://example.test/standard",
        excerpt=excerpt,
    )


class FixedRetriever:
    def __init__(self, citations: list[Citation]) -> None:
        self.citations = citations

    def search(self, query: RequirementQuery) -> list[Citation]:
        return self.citations


def make_tools(citations: list[Citation] | None = None) -> InvestigationTools:
    return InvestigationTools(
        MemorySiteContext(),
        FixedRetriever(citations if citations is not None else [make_citation()]),
    )


def tool_call(name: str, arguments: dict[str, object] | str) -> dict[str, object]:
    return {"id": f"call-{name}", "name": name, "arguments": arguments}


def final_draft(**overrides: object) -> str:
    draft: dict[str, object] = {
        "recommendation": "钢筋搬运存在手部伤害风险，应按要求佩戴手套。",
        "responsible_party_id": "team-structure-01",
        "due_at": "2026-08-07T10:30:00+08:00",
        "rectification_reason": "在规则时限内完成手部防护整改",
        "citation_indexes": [0],
    }
    draft.update(overrides)
    return json.dumps(draft, ensure_ascii=False)


def test_scripted_agent_runs_party_then_rag_then_returns_final_json() -> None:
    model = ScriptedFakeChatModel(
        [
            {
                "tool_calls": [
                    tool_call(
                        "list_eligible_responsible_parties",
                        {"zone_id": "zone-03"},
                    )
                ]
            },
            {
                "tool_calls": [
                    tool_call(
                        "search_authoritative_requirements",
                        {"q": "钢筋搬运手套要求", "top_k": 3},
                    )
                ]
            },
            {"content": final_draft()},
        ]
    )

    result = InvestigationAgent(model, make_tools()).investigate(make_context())

    assert result.recommendation == "钢筋搬运存在手部伤害风险，应按要求佩戴手套。"
    assert result.rectification_recommendation is not None
    assert result.rectification_recommendation.responsible_party_id == "team-structure-01"
    assert result.citations == [make_citation()]
    assert result.tool_trace == [
        "list_eligible_responsible_parties",
        "search_authoritative_requirements",
    ]


def test_agent_supplies_frozen_prompt_and_exact_tool_schemas() -> None:
    model = ScriptedFakeChatModel(
        [{"content": json.dumps({"citation_indexes": []})}]
    )

    InvestigationAgent(model, make_tools()).investigate(make_context())

    first_messages = model.messages[0]
    system_prompt = first_messages[0]["content"]
    assert "resolver" in system_prompt
    assert "must not" in system_prompt
    assert "required_ppe" in system_prompt
    assert "citation_indexes" in system_prompt
    assert isinstance(first_messages[1]["content"], str)
    assert json.loads(first_messages[1]["content"])["applicable_task"] == "HANDLING_REBAR"
    assert [schema["function"]["name"] for schema in model.tool_schemas[0]] == [
        "list_eligible_responsible_parties",
        "search_authoritative_requirements",
    ]


def test_tool_result_message_references_the_model_tool_call_id() -> None:
    model = ScriptedFakeChatModel(
        [
            {
                "tool_calls": [
                    {
                        "id": "call-rag-123",
                        "name": "search_authoritative_requirements",
                        "arguments": {"q": "手套要求"},
                    }
                ]
            },
            {
                "content": json.dumps(
                    {"recommendation": "解释", "citation_indexes": [0]}
                )
            },
        ]
    )

    InvestigationAgent(model, make_tools()).investigate(make_context())

    second_messages = model.messages[1]
    assistant_message = second_messages[-2]
    tool_message = second_messages[-1]
    assert assistant_message["tool_calls"][0]["id"] == "call-rag-123"
    assert assistant_message["tool_calls"][0]["function"]["name"] == (
        "search_authoritative_requirements"
    )
    assert tool_message["tool_call_id"] == "call-rag-123"


def test_deepseek_adapter_uses_official_non_thinking_tool_calling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    class FakeBoundModel:
        def invoke(self, messages):
            observed["messages"] = messages
            return SimpleNamespace(
                content="",
                tool_calls=[
                    {
                        "id": "call-party-456",
                        "name": "list_eligible_responsible_parties",
                        "args": {"zone_id": "zone-03"},
                    }
                ],
            )

    class FakeChatDeepSeek:
        def __init__(self, **kwargs: object) -> None:
            observed["constructor"] = kwargs

        def bind_tools(self, schemas, **kwargs):
            observed["schemas"] = schemas
            observed["bind_options"] = kwargs
            return FakeBoundModel()

    monkeypatch.setitem(
        sys.modules,
        "langchain_deepseek",
        SimpleNamespace(ChatDeepSeek=FakeChatDeepSeek),
    )
    adapter = DeepSeekChatModelAdapter(
        api_key="configured-secret",
        model="deepseek-v4-flash",
        temperature=0,
        timeout=30,
        max_retries=2,
    )
    schemas = [
        {
            "type": "function",
            "function": {
                "name": "list_eligible_responsible_parties",
                "description": "List eligible parties.",
                "parameters": {"type": "object"},
            },
        }
    ]

    response = adapter.complete([{"role": "user", "content": "test"}], schemas)

    assert observed["constructor"] == {
        "api_key": "configured-secret",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-v4-flash",
        "temperature": 0,
        "timeout": 30,
        "max_retries": 2,
        "extra_body": {"thinking": {"type": "disabled"}},
    }
    assert observed["schemas"] == schemas
    assert observed["bind_options"] == {
        "tool_choice": "auto",
        "strict": False,
    }
    assert response.tool_calls[0].id == "call-party-456"


def test_repeated_tool_calls_are_preserved_in_trace() -> None:
    model = ScriptedFakeChatModel(
        [
            {
                "tool_calls": [
                    tool_call(
                        "search_authoritative_requirements",
                        {"q": "第一次查询"},
                    )
                ]
            },
            {
                "tool_calls": [
                    tool_call(
                        "search_authoritative_requirements",
                        {"q": "第二次查询"},
                    )
                ]
            },
            {
                "content": json.dumps(
                    {"recommendation": "解释", "citation_indexes": [0, 1]}
                )
            },
        ]
    )

    result = InvestigationAgent(model, make_tools()).investigate(make_context())

    assert result.tool_trace == [
        "search_authoritative_requirements",
        "search_authoritative_requirements",
    ]
    assert len(result.citations) == 2


def test_multiple_calls_in_one_response_execute_in_declared_order() -> None:
    model = ScriptedFakeChatModel(
        [
            {
                "tool_calls": [
                    tool_call(
                        "list_eligible_responsible_parties",
                        {"zone_id": "zone-03"},
                    ),
                    tool_call(
                        "search_authoritative_requirements",
                        {"q": "手套要求"},
                    ),
                ]
            },
            {"content": final_draft()},
        ]
    )

    result = InvestigationAgent(model, make_tools()).investigate(make_context())

    assert result.tool_trace == [
        "list_eligible_responsible_parties",
        "search_authoritative_requirements",
    ]


def test_unknown_tool_is_rejected() -> None:
    model = ScriptedFakeChatModel(
        [{"tool_calls": [tool_call("run_python", {"code": "pass"})]}]
    )

    with pytest.raises(InvestigationAgentOutputInvalid, match="unknown tool"):
        InvestigationAgent(model, make_tools()).investigate(make_context())


def test_invalid_tool_arguments_are_rejected() -> None:
    model = ScriptedFakeChatModel(
        [
            {
                "tool_calls": [
                    tool_call(
                        "list_eligible_responsible_parties",
                        {"zone_id": "zone-03", "store": "forged"},
                    )
                ]
            }
        ]
    )

    with pytest.raises(InvestigationAgentOutputInvalid, match="invalid tool arguments"):
        InvestigationAgent(model, make_tools()).investigate(make_context())


def test_tool_round_limit_is_enforced() -> None:
    model = ScriptedFakeChatModel(
        [
            {
                "tool_calls": [
                    tool_call(
                        "search_authoritative_requirements", {"q": "第一次"}
                    )
                ]
            },
            {
                "tool_calls": [
                    tool_call(
                        "search_authoritative_requirements", {"q": "第二次"}
                    )
                ]
            },
        ]
    )

    with pytest.raises(InvestigationToolRoundsExceeded):
        InvestigationAgent(model, make_tools(), max_tool_rounds=1).investigate(
            make_context()
        )


def test_non_json_final_response_is_rejected() -> None:
    model = ScriptedFakeChatModel([{"content": "这不是 JSON"}])

    with pytest.raises(InvestigationAgentOutputInvalid, match="valid draft"):
        InvestigationAgent(model, make_tools()).investigate(make_context())


def test_citation_index_out_of_range_is_rejected() -> None:
    model = ScriptedFakeChatModel(
        [
            {
                "tool_calls": [
                    tool_call(
                        "search_authoritative_requirements", {"q": "手套要求"}
                    )
                ]
            },
            {
                "content": json.dumps(
                    {"recommendation": "解释", "citation_indexes": [1]}
                )
            },
        ]
    )

    with pytest.raises(InvestigationAgentOutputInvalid, match="out of range"):
        InvestigationAgent(model, make_tools()).investigate(make_context())


def test_responsibility_recommendation_requires_party_tool_call() -> None:
    model = ScriptedFakeChatModel(
        [
            {
                "tool_calls": [
                    tool_call(
                        "search_authoritative_requirements", {"q": "手套要求"}
                    )
                ]
            },
            {"content": final_draft()},
        ]
    )

    with pytest.raises(InvestigationAgentOutputInvalid, match="not eligible"):
        InvestigationAgent(model, make_tools()).investigate(make_context())


def test_nonexistent_party_cannot_be_recommended() -> None:
    model = ScriptedFakeChatModel(
        [
            {
                "tool_calls": [
                    tool_call(
                        "list_eligible_responsible_parties",
                        {"zone_id": "zone-03"},
                    ),
                    tool_call(
                        "search_authoritative_requirements", {"q": "手套要求"}
                    ),
                ]
            },
            {"content": final_draft(responsible_party_id="team-does-not-exist")},
        ]
    )

    with pytest.raises(InvestigationAgentOutputInvalid, match="not eligible"):
        InvestigationAgent(model, make_tools()).investigate(make_context())


def test_forged_resolver_fields_and_tool_trace_do_not_enter_agent_result() -> None:
    model = ScriptedFakeChatModel(
        [
            {
                "tool_calls": [
                    tool_call(
                        "list_eligible_responsible_parties",
                        {"zone_id": "zone-03"},
                    ),
                    tool_call(
                        "search_authoritative_requirements", {"q": "手套要求"}
                    ),
                ]
            },
            {
                "content": final_draft(
                    required_ppe=["helmet"],
                    hazards=["伪造危害"],
                    applicable_task="ROTATING_EQUIPMENT_OPERATION",
                    tool_trace=["run_shell"],
                )
            },
        ]
    )

    result = InvestigationAgent(model, make_tools()).investigate(make_context())

    assert not hasattr(result, "required_ppe")
    assert not hasattr(result, "hazards")
    assert not hasattr(result, "applicable_task")
    assert result.tool_trace == [
        "list_eligible_responsible_parties",
        "search_authoritative_requirements",
    ]


def test_citations_can_only_come_from_actual_rag_tool_results() -> None:
    actual = make_citation("实际 RAG 返回")
    forged = make_citation("模型自行伪造")
    model = ScriptedFakeChatModel(
        [
            {
                "tool_calls": [
                    tool_call(
                        "search_authoritative_requirements", {"q": "手套要求"}
                    )
                ]
            },
            {
                "content": json.dumps(
                    {
                        "recommendation": "解释",
                        "citation_indexes": [0],
                        "citations": [forged.model_dump(mode="json")],
                    },
                    ensure_ascii=False,
                )
            },
        ]
    )

    result = InvestigationAgent(model, make_tools([actual])).investigate(make_context())

    assert result.citations == [actual]
    assert forged not in result.citations
