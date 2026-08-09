from collections.abc import Callable
from datetime import datetime, timezone
from functools import lru_cache

from fastapi import Depends

from app.domain.case_store import CaseStorePort
from app.domain.case_workflow import CaseWorkflow
from app.domain.inmemory.actor_roles import DemoUserDirectory
from app.domain.inmemory.case_store import InMemoryCaseStore
from app.domain.inmemory.fixture_cases import demo_cases
from app.domain.inmemory.site_context import MemorySiteContext
from app.domain.site_context import SiteContextPort, UserDirectoryPort


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
    return store


def get_clock() -> Clock:
    return lambda: datetime.now(timezone.utc)


def get_case_workflow(
    store: CaseStorePort = Depends(get_case_store),
    users: UserDirectoryPort = Depends(get_user_directory),
    clock: Clock = Depends(get_clock),
) -> CaseWorkflow:
    return CaseWorkflow(store=store, actor_roles=users, clock=clock)
