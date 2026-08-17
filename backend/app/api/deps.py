from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from fastapi import Depends
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.adapters.database.seed import initialize_database
from app.adapters.database.session import (
    create_database_engine,
    create_session_factory,
)
from app.domain.case_store import CaseStorePort
from app.domain.case_workflow import CaseWorkflow
from app.domain.investigation import InvestigationPort
from app.domain.resolver import DeterministicInvestigationResolver, InvestigationResolverPort
from app.domain.inmemory.actor_roles import DemoUserDirectory
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
from app.modules.vlm_review.adapters.openai_compat import (
    OpenAICompatibleVlmAdapter,
)
from app.modules.vlm_review.port import VlmModelPort
from app.modules.vlm_review.service import VlmReviewService
from app.modules.video_analysis.evidence_store import FileEvidenceStore
from app.modules.video_analysis.runtime import build_vision_video_analysis
from app.modules.video_analysis.video_analysis import VisionVideoAnalysis
from app.services.case_pipeline import CasePipeline
from app.config import Settings, get_settings
from app.services.event_hub import EventHub
from app.services.session_manager import SessionManager
from app.repositories import (
    SqlAlchemyAnalysisSessionStore,
    SqlAlchemyCaseStore,
)


Clock = Callable[[], datetime]


@dataclass(frozen=True, slots=True)
class DatabaseRuntime:
    engine: Engine
    session_factory: sessionmaker[Session]


_database_runtime: DatabaseRuntime | None = None


def initialize_database_runtime() -> DatabaseRuntime:
    global _database_runtime
    if _database_runtime is not None:
        return _database_runtime
    settings = get_settings()
    engine = create_database_engine(
        settings.database_url,
        echo=settings.database_echo,
    )
    try:
        initialize_database(engine)
    except Exception:
        engine.dispose()
        raise
    _database_runtime = DatabaseRuntime(
        engine=engine,
        session_factory=create_session_factory(engine),
    )
    return _database_runtime


def shutdown_database_runtime() -> None:
    global _database_runtime
    for dependency in (
        get_session_manager,
        get_inmemory_video_analysis,
        get_vision_video_analysis,
        get_evidence_store,
        get_case_pipeline,
        get_investigation_port,
        get_analysis_session_store,
        get_case_store,
    ):
        dependency.cache_clear()
    if _database_runtime is not None:
        _database_runtime.engine.dispose()
        _database_runtime = None


@lru_cache
def get_site_context() -> SiteContextPort:
    return MemorySiteContext()


@lru_cache
def get_user_directory() -> UserDirectoryPort:
    return DemoUserDirectory()


@lru_cache
def get_case_store() -> CaseStorePort:
    return SqlAlchemyCaseStore(
        initialize_database_runtime().session_factory
    )


@lru_cache
def get_analysis_session_store() -> SqlAlchemyAnalysisSessionStore:
    return SqlAlchemyAnalysisSessionStore(
        initialize_database_runtime().session_factory,
        clock=get_clock(),
    )


def get_clock() -> Clock:
    return lambda: datetime.now(timezone.utc)


@lru_cache
def get_event_hub() -> EventHub:
    return EventHub()


@lru_cache
def get_inmemory_video_analysis() -> InMemoryVideoAnalysis:
    return InMemoryVideoAnalysis(get_site_context(), get_case_pipeline())


@lru_cache
def get_evidence_store() -> FileEvidenceStore:
    return FileEvidenceStore(Path(get_settings().vision_evidence_root))


async def get_evidence_store_port() -> FileEvidenceStore:
    return get_evidence_store()


@lru_cache
def get_vision_video_analysis() -> VisionVideoAnalysis:
    return build_vision_video_analysis(
        get_settings(),
        get_site_context(),
        get_case_pipeline(),
    )


@lru_cache
def get_session_manager() -> SessionManager:
    settings = get_settings()
    analysis = (
        get_vision_video_analysis()
        if settings.vision_provider == "yolo"
        else get_inmemory_video_analysis()
    )
    return SessionManager(
        get_event_hub(),
        get_site_context().get_video,
        analysis.get_stream,
        analysis.run_session,
        save_session=get_analysis_session_store().save,
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
    return build_fixture_investigation_port(
        get_case_store(),
        get_site_context(),
        get_investigation_resolver(),
    )


def build_fixture_investigation_port(
    store: CaseStorePort,
    context: SiteContextPort,
    resolver: InvestigationResolverPort,
) -> InvestigationPort:
    tools = InvestigationTools(
        context,
        FixtureRequirementRetriever(),
    )
    delegate = InvestigationService(
        store,
        resolver,
        FixedInvestigationAgent(tools),
    )
    return FixtureInvestigation(delegate)


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
    return build_fixture_case_pipeline(
        store,
        get_user_directory(),
        get_site_context(),
        clock,
        investigation=get_investigation_port(),
    )


def build_vlm_adapter(settings: Settings) -> VlmModelPort:
    if settings.vlm_provider == "fixed":
        return FixedVlmAdapter()
    if settings.vlm_provider == "openai_compat":
        return OpenAICompatibleVlmAdapter(
            api_key=settings.vlm_api_key or "",
            base_url=settings.vlm_api_base_url or "",
            model=settings.vlm_model,
            evidence_root=Path(settings.vision_evidence_root),
            timeout_seconds=settings.vlm_timeout_seconds,
            max_frames=settings.vlm_max_frames,
            max_image_edge=settings.vlm_max_image_edge,
            max_output_tokens=settings.vlm_max_output_tokens,
        )
    raise ValueError(f"unsupported VLM_PROVIDER: {settings.vlm_provider}")


def build_fixture_case_pipeline(
    store: CaseStorePort,
    users: UserDirectoryPort,
    context: SiteContextPort,
    clock: Clock,
    investigation: InvestigationPort | None = None,
) -> CasePipeline:
    workflow = build_case_workflow(
        store,
        users,
        context,
        clock,
    )
    settings = get_settings()
    vlm = VlmReviewService(
        store,
        build_vlm_adapter(settings),
        workflow,
        model_provider=settings.vlm_provider,
        model_parameters={
            "temperature": 0,
            "max_frames": settings.vlm_max_frames,
            "max_output_tokens": settings.vlm_max_output_tokens,
        },
        clock=clock,
        max_retries=settings.vlm_max_retries,
        retry_delay_seconds=settings.vlm_retry_delay_seconds,
    )
    if investigation is None:
        investigation = build_fixture_investigation_port(
            store,
            context,
            DeterministicInvestigationResolver(context),
        )
    return CasePipeline(
        store,
        workflow,
        vlm,
        investigation,
    )


def get_case_workflow(
    store: CaseStorePort = Depends(get_case_store),
    users: UserDirectoryPort = Depends(get_user_directory),
    context: SiteContextPort = Depends(get_site_context),
    clock: Clock = Depends(get_clock),
) -> CaseWorkflow:
    return build_case_workflow(store, users, context, clock)
