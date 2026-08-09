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
