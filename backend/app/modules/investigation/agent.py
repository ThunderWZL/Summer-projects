from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Protocol

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from app.contracts import Citation, PpeType, RectificationRecommendation
from app.domain.investigation import (
    InvestigationAgentFailed,
    InvestigationAgentOutputInvalid,
    InvestigationToolRoundsExceeded,
)
from app.modules.investigation.tools import (
    AuthoritativeRequirementsInput,
    InvestigationTools,
    EligibleResponsiblePartiesInput,
)


class _AgentModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class AgentInvestigationContext(_AgentModel):
    case_id: str = Field(min_length=1)
    zone_id: str = Field(min_length=1)
    zone_name: str = Field(min_length=1)
    occurred_at: datetime
    ppe_type: PpeType
    applicable_task: str = Field(min_length=1)
    hazards: list[str]
    required_ppe: list[PpeType]
    exception_note: str | None = None
    rectification_window_minutes: int = Field(gt=0)


class AgentInvestigationDraft(BaseModel):
    """Untrusted model draft. Extra fields never become resolver facts."""

    model_config = ConfigDict(extra="ignore")

    recommendation: str | None = None
    responsible_party_id: str | None = None
    due_at: datetime | None = None
    rectification_reason: str | None = None
    citation_indexes: list[int] = Field(default_factory=list)

    @field_validator("citation_indexes")
    @classmethod
    def indexes_must_be_unique_and_non_negative(cls, value: list[int]) -> list[int]:
        if any(index < 0 for index in value):
            raise ValueError("citation indexes must be non-negative")
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def rectification_fields_must_be_together(self) -> AgentInvestigationDraft:
        values = (
            self.responsible_party_id,
            self.due_at,
            self.rectification_reason,
        )
        if any(value is not None for value in values) and not all(
            value is not None for value in values
        ):
            raise ValueError("rectification fields must be set together")
        return self


class AgentRunResult(_AgentModel):
    recommendation: str | None = None
    rectification_recommendation: RectificationRecommendation | None = None
    citations: list[Citation]
    tool_trace: list[str]


class AgentToolCall(_AgentModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    arguments: str | dict[str, Any]


class AgentModelResponse(_AgentModel):
    content: str | None = None
    tool_calls: list[AgentToolCall] = Field(default_factory=list)


class InvestigationChatModelPort(Protocol):
    def complete(
        self,
        messages: list[dict[str, Any]],
        tool_schemas: list[dict[str, Any]],
    ) -> AgentModelResponse: ...


class InvestigationAgentPort(Protocol):
    def investigate(self, context: AgentInvestigationContext) -> AgentRunResult: ...


class ScriptedFakeChatModel:
    """Deterministic test chat model which returns the supplied responses in order."""

    def __init__(self, responses: list[AgentModelResponse | dict[str, Any]]) -> None:
        self._responses = [AgentModelResponse.model_validate(item) for item in responses]
        self.messages: list[list[dict[str, Any]]] = []
        self.tool_schemas: list[list[dict[str, Any]]] = []

    def complete(
        self,
        messages: list[dict[str, Any]],
        tool_schemas: list[dict[str, Any]],
    ) -> AgentModelResponse:
        self.messages.append(list(messages))
        self.tool_schemas.append(tool_schemas)
        if not self._responses:
            raise InvestigationAgentFailed("scripted chat model has no response")
        return self._responses.pop(0)


class DeepSeekChatModelAdapter:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        temperature: float,
        timeout: float,
        max_retries: int,
        max_output_tokens: int,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._temperature = temperature
        self._timeout = timeout
        self._max_retries = max_retries
        self._max_output_tokens = max_output_tokens
        self._client: Any | None = None

    def complete(
        self,
        messages: list[dict[str, Any]],
        tool_schemas: list[dict[str, Any]],
    ) -> AgentModelResponse:
        if self._client is None:
            try:
                from langchain_deepseek import ChatDeepSeek
            except ImportError as exc:
                raise InvestigationAgentFailed(
                    "langchain-deepseek is required when DEEPSEEK_API_KEY is configured"
                ) from exc
            self._client = ChatDeepSeek(
                api_key=self._api_key,
                base_url="https://api.deepseek.com",
                model=self._model,
                temperature=self._temperature,
                timeout=self._timeout,
                max_retries=self._max_retries,
                max_tokens=self._max_output_tokens,
                model_kwargs={"response_format": {"type": "json_object"}},
                extra_body={"thinking": {"type": "disabled"}},
            )
        strict_tool_schemas = [
            {
                **schema,
                "function": {
                    **schema["function"],
                    "strict": True,
                },
            }
            for schema in tool_schemas
        ]
        model_with_tools = self._client.bind_tools(
            strict_tool_schemas,
            tool_choice="auto",
            strict=True,
        )
        try:
            response = model_with_tools.invoke(messages)
        except Exception as exc:
            raise InvestigationAgentFailed("DeepSeek request failed") from exc
        try:
            calls = [
                AgentToolCall(
                    id=call["id"],
                    name=call["name"],
                    arguments=call.get("args", {}),
                )
                for call in (getattr(response, "tool_calls", None) or [])
            ]
        except (KeyError, TypeError, ValidationError) as exc:
            raise InvestigationAgentOutputInvalid(
                "DeepSeek returned an invalid tool call"
            ) from exc
        content = response.content
        if not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False)
        return AgentModelResponse(content=content, tool_calls=calls)


def _investigation_tool_schemas() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "list_eligible_responsible_parties",
                "description": (
                    "List the active responsible parties eligible for the given zone."
                ),
                "parameters": EligibleResponsiblePartiesInput.model_json_schema(),
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_authoritative_requirements",
                "description": (
                    "Search authoritative PPE requirements and return traceable citations."
                ),
                "parameters": AuthoritativeRequirementsInput.model_json_schema(),
            },
        },
    ]


_AGENT_SYSTEM_PROMPT = """You are the explanation agent for a PPE investigation.
The resolver fields facts, conflicts, missing_fields, applicable_task, hazards, and
required_ppe are authoritative. You must not alter, reinterpret, or replace them.
You may use only list_eligible_responsible_parties and
search_authoritative_requirements. Never invent a responsible party or citation.
When the investigation is ready, output one JSON object and no Markdown. The object
may contain only recommendation, responsible_party_id, due_at,
rectification_reason, and citation_indexes. responsible_party_id, due_at, and
rectification_reason must be supplied together or all be null. citation_indexes
are zero-based indexes into citations returned by the requirements tool.
"""

_AGENT_JSON_CORRECTION_PROMPT = """Your previous response was not a valid JSON
object. Return only one JSON object with exactly this shape and no Markdown:
{"recommendation": "text or null", "responsible_party_id": "id or null",
"due_at": "ISO 8601 datetime or null", "rectification_reason": "text or null",
"citation_indexes": [0]}. The three rectification fields must all be non-null or
all be null. Use only citation indexes and responsible party IDs returned by tools.
"""


class InvestigationAgent:
    def __init__(
        self,
        chat_model: InvestigationChatModelPort,
        tools: InvestigationTools,
        *,
        max_tool_rounds: int = 6,
        max_output_retries: int = 2,
    ) -> None:
        self._chat_model = chat_model
        self._tools = tools
        self._max_tool_rounds = max_tool_rounds
        self._max_output_retries = max_output_retries

    def investigate(self, context: AgentInvestigationContext) -> AgentRunResult:
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": _AGENT_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": json.dumps(
                    context.model_dump(mode="json"),
                    ensure_ascii=False,
                ),
            },
        ]
        tool_schemas = _investigation_tool_schemas()
        citations: list[Citation] = []
        eligible_party_ids: set[str] = set()
        tool_trace: list[str] = []
        tool_rounds = 0
        output_retries = 0
        searched_requirements = False
        while True:
            response = self._chat_model.complete(messages, tool_schemas)
            if response.tool_calls:
                tool_rounds += 1
                if tool_rounds > self._max_tool_rounds:
                    raise InvestigationToolRoundsExceeded("agent tool round limit exceeded")
                messages.append(
                    {
                        "role": "assistant",
                        "content": response.content or "",
                        "tool_calls": [
                            {
                                "id": call.id,
                                "type": "function",
                                "function": {
                                    "name": call.name,
                                    "arguments": (
                                        call.arguments
                                        if isinstance(call.arguments, str)
                                        else json.dumps(
                                            call.arguments,
                                            ensure_ascii=False,
                                        )
                                    ),
                                },
                            }
                            for call in response.tool_calls
                        ],
                    }
                )
                for call in response.tool_calls:
                    result = self._execute_tool(call)
                    if call.name == "list_eligible_responsible_parties":
                        eligible_party_ids.update(p.party_id for p in result.parties)
                    else:
                        citations.extend(result.citations)
                        searched_requirements = True
                    tool_trace.append(call.name)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": result.model_dump_json(),
                        }
                    )
                continue
            try:
                draft = self._parse_draft(response.content)
            except InvestigationAgentOutputInvalid:
                if output_retries >= self._max_output_retries:
                    raise
                output_retries += 1
                messages.extend(
                    [
                        {
                            "role": "assistant",
                            "content": response.content or "",
                        },
                        {
                            "role": "user",
                            "content": _AGENT_JSON_CORRECTION_PROMPT,
                        },
                    ]
                )
                continue
            has_recommendation = (
                draft.recommendation is not None
                or draft.responsible_party_id is not None
            )
            if has_recommendation and not searched_requirements:
                raise InvestigationAgentOutputInvalid("recommendation requires a requirements query")
            if draft.responsible_party_id is not None and draft.responsible_party_id not in eligible_party_ids:
                raise InvestigationAgentOutputInvalid("responsible party is not eligible")
            try:
                selected = [citations[index] for index in draft.citation_indexes]
            except IndexError as exc:
                raise InvestigationAgentOutputInvalid("citation index is out of range") from exc
            recommendation = None
            if draft.responsible_party_id is not None:
                recommendation = RectificationRecommendation(
                    responsible_party_id=draft.responsible_party_id,
                    due_at=draft.due_at,
                    reason=draft.rectification_reason,
                )
            return AgentRunResult(
                recommendation=draft.recommendation,
                rectification_recommendation=recommendation,
                citations=selected,
                tool_trace=tool_trace,
            )

    def _execute_tool(self, call: AgentToolCall):
        try:
            arguments = json.loads(call.arguments) if isinstance(call.arguments, str) else call.arguments
        except (TypeError, json.JSONDecodeError) as exc:
            raise InvestigationAgentOutputInvalid("tool arguments must be JSON") from exc
        try:
            if call.name == "list_eligible_responsible_parties":
                return self._tools.list_eligible_responsible_parties(
                    EligibleResponsiblePartiesInput.model_validate(arguments)
                )
            if call.name == "search_authoritative_requirements":
                return self._tools.search_authoritative_requirements(
                    AuthoritativeRequirementsInput.model_validate(arguments)
                )
        except ValidationError as exc:
            raise InvestigationAgentOutputInvalid("invalid tool arguments") from exc
        raise InvestigationAgentOutputInvalid("unknown tool")

    @staticmethod
    def _parse_draft(content: str | None) -> AgentInvestigationDraft:
        if not content:
            raise InvestigationAgentOutputInvalid("agent response has no JSON draft")
        try:
            payload = json.loads(content)
            return AgentInvestigationDraft.model_validate(payload)
        except Exception as exc:
            raise InvestigationAgentOutputInvalid("agent output is not a valid draft") from exc
