from collections.abc import Callable
from datetime import datetime, timezone
from functools import lru_cache

from fastapi import Depends

from app.domain.case_store import CaseStorePort
from app.domain.case_workflow import CaseWorkflow
from app.domain.inmemory.actor_roles import DemoUserDirectory
from app.domain.inmemory.case_store import InMemoryCaseStore
from app.domain.inmemory.fixture_cases import demo_cases, demo_submissions
from app.domain.inmemory.site_context import MemorySiteContext
from app.domain.site_context import SiteContextPort, UserDirectoryPort
from app.modules.requirements_rag.embedding import (
    DeterministicEmbeddingClient,
    EmbeddingClientPort,
    OpenAIEmbeddingClient,
)
from app.modules.requirements_rag.service import RequirementsRagService
from app.modules.requirements_rag.store import PersistentVectorStore
from app.config import get_settings


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
    return RequirementsRagService(
        store=PersistentVectorStore(settings.chroma_path),
        embedder=embedder,
        default_top_k=settings.rag_top_k,
    )


def get_case_workflow(
    store: CaseStorePort = Depends(get_case_store),
    users: UserDirectoryPort = Depends(get_user_directory),
    context: SiteContextPort = Depends(get_site_context),
    clock: Clock = Depends(get_clock),
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
