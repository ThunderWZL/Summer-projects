import pytest

from app.api import deps
from app.config import Settings
from app.modules.vlm_review.adapters.fixed import FixedVlmAdapter

VLM_ENV_KEYS = (
    "VLM_PROVIDER",
    "VLM_API_BASE_URL",
    "VLM_API_KEY",
    "VLM_MODEL",
    "VLM_TIMEOUT_SECONDS",
    "VLM_MAX_FRAMES",
    "VLM_MAX_IMAGE_EDGE",
    "VLM_MAX_OUTPUT_TOKENS",
    "VLM_MAX_RETRIES",
    "VLM_RETRY_DELAY_SECONDS",
)


def test_defaults_are_used_without_vlm_env(monkeypatch) -> None:
    for key in VLM_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    settings = Settings(_env_file=None)

    assert settings.vlm_provider == "fixed"
    assert settings.vlm_model == "fixed-reviewer"
    assert settings.vlm_api_base_url is None
    assert settings.vlm_api_key is None
    assert settings.vlm_timeout_seconds == 90.0
    assert settings.vlm_max_frames == 8
    assert settings.vlm_max_image_edge == 1280
    assert settings.vlm_max_output_tokens == 2048
    assert settings.vlm_max_retries == 2
    assert settings.vlm_retry_delay_seconds == 0.5


def test_vlm_env_vars_override_defaults(monkeypatch) -> None:
    monkeypatch.setenv("VLM_PROVIDER", "openai_compat")
    monkeypatch.setenv("VLM_API_BASE_URL", "https://vlm.example.com/v1")
    monkeypatch.setenv("VLM_API_KEY", "test-key")
    monkeypatch.setenv("VLM_MODEL", "qwen-vl-plus")
    monkeypatch.setenv("VLM_TIMEOUT_SECONDS", "60")
    monkeypatch.setenv("VLM_MAX_FRAMES", "4")
    monkeypatch.setenv("VLM_MAX_IMAGE_EDGE", "1024")
    monkeypatch.setenv("VLM_MAX_OUTPUT_TOKENS", "256")
    monkeypatch.setenv("VLM_MAX_RETRIES", "4")
    monkeypatch.setenv("VLM_RETRY_DELAY_SECONDS", "1.25")

    settings = Settings(_env_file=None)

    assert settings.vlm_provider == "openai_compat"
    assert settings.vlm_api_base_url == "https://vlm.example.com/v1"
    assert settings.vlm_api_key == "test-key"
    assert settings.vlm_model == "qwen-vl-plus"
    assert settings.vlm_timeout_seconds == 60.0
    assert settings.vlm_max_frames == 4
    assert settings.vlm_max_image_edge == 1024
    assert settings.vlm_max_output_tokens == 256
    assert settings.vlm_max_retries == 4
    assert settings.vlm_retry_delay_seconds == 1.25


def test_fixed_provider_builds_the_deterministic_adapter() -> None:
    adapter = deps.build_vlm_adapter(
        Settings(vlm_provider="fixed", _env_file=None)
    )

    assert isinstance(adapter, FixedVlmAdapter)


def test_openai_compatible_provider_passes_isolated_vlm_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    constructed: dict[str, object] = {}

    class FakeOpenAICompatibleVlmAdapter:
        def __init__(self, **kwargs: object) -> None:
            constructed.update(kwargs)

    monkeypatch.setattr(
        deps,
        "OpenAICompatibleVlmAdapter",
        FakeOpenAICompatibleVlmAdapter,
    )
    settings = Settings(
        vlm_provider="openai_compat",
        vlm_api_key="vlm-only-secret",
        vlm_api_base_url="https://dashscope.example/v1",
        vlm_model="qwen3.6-27b",
        vision_evidence_root=".data/evidence",
        vlm_timeout_seconds=45,
        vlm_max_frames=3,
        vlm_max_output_tokens=256,
        _env_file=None,
    )

    adapter = deps.build_vlm_adapter(settings)

    assert isinstance(adapter, FakeOpenAICompatibleVlmAdapter)
    assert constructed == {
        "api_key": "vlm-only-secret",
        "base_url": "https://dashscope.example/v1",
        "model": "qwen3.6-27b",
        "evidence_root": deps.Path(".data/evidence"),
        "timeout_seconds": 45,
        "max_frames": 3,
        "max_image_edge": 1280,
        "max_output_tokens": 256,
    }


def test_openai_compatible_provider_rejects_missing_credentials() -> None:
    settings = Settings(
        vlm_provider="openai_compat",
        vlm_api_key=None,
        vlm_api_base_url="https://dashscope.example/v1",
        vlm_model="qwen3.6-27b",
        _env_file=None,
    )

    with pytest.raises(ValueError, match="VLM_API_KEY"):
        deps.build_vlm_adapter(settings)


def test_unknown_vlm_provider_is_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported VLM_PROVIDER"):
        deps.build_vlm_adapter(
            Settings(vlm_provider="unknown", _env_file=None)
        )
