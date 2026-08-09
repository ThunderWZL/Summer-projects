from app.config import Settings

VLM_ENV_KEYS = (
    "VLM_PROVIDER",
    "VLM_API_BASE_URL",
    "VLM_API_KEY",
    "VLM_MODEL",
    "VLM_TIMEOUT_SECONDS",
    "VLM_MAX_FRAMES",
    "VLM_MAX_IMAGE_EDGE",
    "VLM_MAX_OUTPUT_TOKENS",
)


def test_defaults_are_used_without_vlm_env(monkeypatch) -> None:
    for key in VLM_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    settings = Settings()

    assert settings.vlm_provider == "fixed"
    assert settings.vlm_model == "fixed-reviewer"
    assert settings.vlm_api_base_url is None
    assert settings.vlm_api_key is None
    assert settings.vlm_timeout_seconds == 30.0
    assert settings.vlm_max_frames == 8
    assert settings.vlm_max_image_edge == 1280
    assert settings.vlm_max_output_tokens == 512


def test_vlm_env_vars_override_defaults(monkeypatch) -> None:
    monkeypatch.setenv("VLM_PROVIDER", "openai_compat")
    monkeypatch.setenv("VLM_API_BASE_URL", "https://vlm.example.com/v1")
    monkeypatch.setenv("VLM_API_KEY", "test-key")
    monkeypatch.setenv("VLM_MODEL", "qwen-vl-plus")
    monkeypatch.setenv("VLM_TIMEOUT_SECONDS", "60")
    monkeypatch.setenv("VLM_MAX_FRAMES", "4")
    monkeypatch.setenv("VLM_MAX_IMAGE_EDGE", "1024")
    monkeypatch.setenv("VLM_MAX_OUTPUT_TOKENS", "256")

    settings = Settings()

    assert settings.vlm_provider == "openai_compat"
    assert settings.vlm_api_base_url == "https://vlm.example.com/v1"
    assert settings.vlm_api_key == "test-key"
    assert settings.vlm_model == "qwen-vl-plus"
    assert settings.vlm_timeout_seconds == 60.0
    assert settings.vlm_max_frames == 4
    assert settings.vlm_max_image_edge == 1024
    assert settings.vlm_max_output_tokens == 256
