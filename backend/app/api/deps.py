from collections.abc import Callable
from datetime import datetime, timezone
from functools import lru_cache

from fastapi import Depends

from app.domain.case_store import CaseStorePort
from app.domain.case_workflow import CaseWorkflow
from app.domain.investigation import InvestigationPort
from app.domain.resolver import DeterministicInvestigationResolver, InvestigationResolverPort
from app.domain.inmemory.actor_roles import DemoUserDirectory
from app.domain.inmemory.case_store import InMemoryCaseStore
from app.domain.inmemory.fixture_cases import demo_cases, demo_submissions
from app.domain.inmemory.site_context import MemorySiteContext
from app.domain.inmemory.video_analysis import InMemoryVideoAnalysis
from app.domain.inmemory.fake_investigation import (
    FixtureInvestigation,
    FixtureRequirementRetriever,
)
from app.domain.site_context import SiteContextPort, UserDirectoryPort
from app.domain.video_analysis import VideoAnalysisPort
from app.modules.requirements_rag.embedding import (
    DeterministicEmbeddingClient,
    EmbeddingClientPort,
    OpenAIEmbeddingClient,
)
from app.modules.requirements_rag.service import RequirementsRagService
from app.modules.requirements_rag.store import PersistentVectorStore
from app.modules.requirements_rag.chroma import ChromaVectorStore
from app.modules.investigation.agent import DeepSeekChatModelAdapter, InvestigationAgent, InvestigationAgentPort
from app.modules.investigation.fake import FixedInvestigationAgent
from app.modules.investigation.service import InvestigationService
from app.modules.investigation.tools import InvestigationTools
from app.modules.vlm_review.adapters.fixed import FixedVlmAdapter
from app.modules.vlm_review.service import VlmReviewService
from app.services.case_pipeline import CasePipeline
from app.config import get_settings
from app.services.event_hub import EventHub
from app.services.session_manager import SessionManager


Clock = Callable[[], datetime]


@lru_cache
def get_site_context() -> SiteContextPort:
    return MemorySiteContext()


@lru_cache
def get_user_directory() -> UserDirectoryPort:
    return DemoUserDirectory()


@lru_cache
def get_case_store() -> CaseStorePort:
    store = InMemoryCaseStore()
    for case in demo_cases():
        store.create(case)
    for submission in demo_submissions():
        store.add_submission(submission)
    return store


def get_clock() -> Clock:
    return lambda: datetime.now(timezone.utc)


@lru_cache
def get_event_hub() -> EventHub:
    return EventHub()


@lru_cache
def get_inmemory_video_analysis() -> InMemoryVideoAnalysis:
    return InMemoryVideoAnalysis(get_site_context(), get_case_pipeline())


@lru_cache
def get_session_manager() -> SessionManager:
    fake = get_inmemory_video_analysis()
    return SessionManager(
        get_event_hub(),
        get_site_context().get_video,
        fake.get_stream,
        fake.run_session,
    )


async def get_video_analysis_port() -> VideoAnalysisPort:
    return get_session_manager()


@lru_cache
def get_requirement_retriever() -> RequirementsRagService:
    settings = get_settings()
    if settings.embedding_api_key:
        embedder: EmbeddingClientPort = OpenAIEmbeddingClient(
            api_key=settings.embedding_api_key,
            base_url=settings.embedding_base_url,
            model=settings.embedding_model,
        )
    else:
        embedder = DeterministicEmbeddingClient(model="fake-v1", dimension=32)
    store = (
        ChromaVectorStore(settings.chroma_path)
        if settings.embedding_api_key
        else PersistentVectorStore(settings.offline_rag_path)
    )
    return RequirementsRagService(
        store=store,
        embedder=embedder,
        default_top_k=settings.rag_top_k,
    )


@lru_cache
def get_investigation_resolver() -> InvestigationResolverPort:
    return DeterministicInvestigationResolver(get_site_context())


@lru_cache
def get_investigation_tools() -> InvestigationTools:
    return InvestigationTools(get_site_context(), get_requirement_retriever())


@lru_cache
def get_investigation_agent() -> InvestigationAgentPort:
    settings = get_settings()
    tools = get_investigation_tools()
    if not settings.deepseek_api_key:
        return FixedInvestigationAgent(tools)
    return InvestigationAgent(
        DeepSeekChatModelAdapter(
            api_key=settings.deepseek_api_key,
            model=settings.agent_llm_model,
            temperature=settings.agent_llm_temperature,
            timeout=settings.agent_llm_timeout_seconds,
            max_retries=settings.agent_llm_max_retries,
        ),
        tools,
        max_tool_rounds=settings.agent_max_tool_rounds,
    )


@lru_cache
def get_investigation_port() -> InvestigationPort:
    return InvestigationService(
        get_case_store(), get_investigation_resolver(), get_investigation_agent()
    )


def get_fixture_investigation_port() -> InvestigationPort:
    store = get_case_store()
    tools = InvestigationTools(
        get_site_context(),
        FixtureRequirementRetriever(),
    )
    delegate = InvestigationService(
        store,
        get_investigation_resolver(),
        FixedInvestigationAgent(tools),
    )
    return FixtureInvestigation(delegate, store)


def build_case_workflow(
    store: CaseStorePort,
    users: UserDirectoryPort,
    context: SiteContextPort,
    clock: Clock,
) -> CaseWorkflow:
    def responsible_party_is_eligible(snapshot, party_id: str) -> bool:
        zone = context.get_zone_at(snapshot.camera_id)
        return bool(
            zone is not None
            and any(
                party.party_id == party_id
                for party in context.list_eligible_responsible_parties(
                    zone.zone_id
                )
            )
        )

    return CaseWorkflow(
        store=store,
        actor_roles=users,
        clock=clock,
        responsible_party_is_eligible=responsible_party_is_eligible,
    )


@lru_cache
def get_case_pipeline() -> CasePipeline:
    store = get_case_store()
    clock = get_clock()
    workflow = build_case_workflow(
        store,
        get_user_directory(),
        get_site_context(),
        clock,
    )
    settings = get_settings()
    vlm = VlmReviewService(
        store,
        FixedVlmAdapter(),
        workflow,
        model_provider="fixture",
        model_parameters={"temperature": 0},
        clock=clock,
        max_retries=settings.vlm_max_retries,
        retry_delay_seconds=settings.vlm_retry_delay_seconds,
    )
    return CasePipeline(
        store,
        workflow,
        vlm,
        get_fixture_investigation_port(),
    )


def get_case_workflow(
    store: CaseStorePort = Depends(get_case_store),
    users: UserDirectoryPort = Depends(get_user_directory),
    context: SiteContextPort = Depends(get_site_context),
    clock: Clock = Depends(get_clock),
) -> CaseWorkflow:
    return build_case_workflow(store, users, context, clock)
