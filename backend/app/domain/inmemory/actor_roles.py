from __future__ import annotations

from app.contracts import ActorRole
from app.domain.site_context import DemoUser


class DemoUserDirectory:
    """演示用户目录：同一份数据同时满足 UserDirectoryPort 与 ActorRolePort。"""

    def __init__(self) -> None:
        self._users = {
            "officer-01": DemoUser(
                actor_id="officer-01",
                name="现场安全员",
                role=ActorRole.SITE_SAFETY_OFFICER,
            ),
            "reviewer-01": DemoUser(
                actor_id="reviewer-01",
                name="项目安全审核人",
                role=ActorRole.PROJECT_SAFETY_REVIEWER,
            ),
        }

    def get(self, actor_id: str) -> DemoUser | None:
        return self._users.get(actor_id)

    def role_for(self, actor_id: str) -> ActorRole | None:
        user = self._users.get(actor_id)
        return user.role if user is not None else None
