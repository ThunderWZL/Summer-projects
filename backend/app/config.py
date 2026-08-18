from __future__ import annotations

from functools import lru_cache
from typing import Literal

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
    vlm_timeout_seconds: float = 90.0
    vlm_max_frames: int = 8
    vlm_max_image_edge: int = 1280
    vlm_max_output_tokens: int = 2048
    vlm_max_retries: int = Field(default=2, ge=0)
    vlm_retry_delay_seconds: float = Field(default=0.5, ge=0)
    deepseek_api_key: str | None = None
    agent_llm_model: str = "deepseek-v4-flash"
    agent_llm_timeout_seconds: float = Field(default=30, gt=0)
    agent_llm_max_retries: int = Field(default=2, ge=0)
    agent_llm_max_output_tokens: int = Field(default=1024, gt=0)
    agent_max_tool_rounds: int = Field(default=6, ge=1)
    agent_llm_temperature: float = Field(default=0, ge=0, le=2)
    embedding_api_key: str | None = None
    embedding_base_url: str | None = None
    embedding_model: str = "text-embedding-3-small"
    chroma_path: str = "chroma_db"
    offline_rag_path: str = ".data/requirements-rag-offline.json"
    rag_top_k: int = Field(default=5, ge=1, le=20)
    vision_provider: Literal["fixture", "yolo"] = "fixture"
    yolo_weights_path: str | None = None
    vision_device: str = "auto"
    vision_target_fps: float = Field(default=5.0, gt=0)
    vision_confidence: float = Field(default=0.25, ge=0, le=1)
    vision_image_size: int = Field(default=640, gt=0)
    vision_tracker: str = "bytetrack.yaml"
    vision_model_name: str = "yolo11n-ppe"
    vision_model_version: str = "w02"
    vision_evidence_root: str = ".data/evidence"
    vision_minimum_person_height_px: int = Field(default=120, gt=0)
    vision_boundary_margin_px: int = Field(default=5, ge=0)
    vision_maximum_person_overlap_iou: float = Field(default=0.5, gt=0, le=1)
    vision_minimum_track_observations: int = Field(default=3, gt=0)
    vision_minimum_valid_observations: int = Field(default=3, gt=0)
    vision_maximum_observation_gap_ms: int = Field(default=500, gt=0)
    vision_minimum_negative_observations: int = Field(default=3, ge=3)


@lru_cache
def get_settings() -> Settings:
    return Settings()
