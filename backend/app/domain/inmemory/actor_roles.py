from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.contracts import ActorRole
from app.domain.site_context import DemoUser

_RESOURCE_DIR = Path(__file__).resolve().parents[2] / "resources" / "demo"


class _ConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _User(_ConfigModel):
    actor_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    role: ActorRole
    active: bool = True


class _Users(_ConfigModel):
    users: list[_User]

    @model_validator(mode="after")
    def actor_ids_must_be_unique(self) -> "_Users":
        ids = [user.actor_id for user in self.users]
        if len(ids) != len(set(ids)):
            raise ValueError("actor_id must be unique")
        return self


class DemoUserDirectory:
    """配置驱动的演示用户目录：同一份数据同时满足 UserDirectoryPort 与 ActorRolePort。"""

    def __init__(self, users_path: str | Path | None = None) -> None:
        raw = json.loads(
            Path(users_path or _RESOURCE_DIR / "users.json").read_text(encoding="utf-8")
        )
        users = _Users.model_validate(raw).users
        self._users = {
            user.actor_id: DemoUser(
                actor_id=user.actor_id,
                name=user.name,
                role=user.role,
                active=user.active,
            )
            for user in users
        }

    def get(self, actor_id: str) -> DemoUser | None:
        return self._users.get(actor_id)

    def role_for(self, actor_id: str) -> ActorRole | None:
        user = self._users.get(actor_id)
        return user.role if user is not None else None
