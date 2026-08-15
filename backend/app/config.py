from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """集中所有环境变量配置，密钥只从环境变量读取，仓库只保留 .env.example。

    VLM_* 与后续的 AGENT_LLM_* / EMBEDDING_* 严格隔离，互不复用。
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./siteppe.db"
    database_echo: bool = False
    vlm_provider: str = "fixed"
    vlm_api_base_url: str | None = None
    vlm_api_key: str | None = None
    vlm_model: str = "fixed-reviewer"
    vlm_timeout_seconds: float = 30.0
    vlm_max_frames: int = 8
    vlm_max_image_edge: int = 1280
    vlm_max_output_tokens: int = 512
    vlm_max_retries: int = Field(default=2, ge=0)
    vlm_retry_delay_seconds: float = Field(default=0.5, ge=0)
    deepseek_api_key: str | None = None
    agent_llm_model: str = "deepseek-v4-flash"
    agent_llm_timeout_seconds: float = Field(default=30, gt=0)
    agent_llm_max_retries: int = Field(default=2, ge=0)
    agent_max_tool_rounds: int = Field(default=6, ge=1)
    agent_llm_temperature: float = Field(default=0, ge=0, le=2)
    embedding_api_key: str | None = None
    embedding_base_url: str | None = None
    embedding_model: str = "text-embedding-3-small"
    chroma_path: str = "chroma_db"
    offline_rag_path: str = ".data/requirements-rag-offline.json"
    rag_top_k: int = Field(default=5, ge=1, le=20)


@lru_cache
def get_settings() -> Settings:
    return Settings()
