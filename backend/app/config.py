from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """集中所有环境变量配置，密钥只从环境变量读取，仓库只保留 .env.example。

    VLM_* 与后续的 AGENT_LLM_* / EMBEDDING_* 严格隔离，互不复用。
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    vlm_provider: str = "fixed"
    vlm_api_base_url: str | None = None
    vlm_api_key: str | None = None
    vlm_model: str = "fixed-reviewer"
    vlm_timeout_seconds: float = 30.0
    vlm_max_frames: int = 8
    vlm_max_image_edge: int = 1280
    vlm_max_output_tokens: int = 512


@lru_cache
def get_settings() -> Settings:
    return Settings()
