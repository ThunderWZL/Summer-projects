from __future__ import annotations

import copy
import builtins
import importlib
import json
import sys
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.api import deps
from app.config import Settings
from app.domain.investigation import InvestigationAgentFailed
from app.domain.inmemory.site_context import MemorySiteContext
from app.modules.investigation.agent import (
    DeepSeekChatModelAdapter,
    InvestigationAgent,
)
from app.modules.investigation.fake import FixedInvestigationAgent


SCENARIO_TIME = datetime.fromisoformat("2026-08-07T10:00:00+08:00")
RESOURCE_DIR = Path(__file__).resolve().parents[3] / "app" / "resources" / "demo"
BACKEND_DIR = Path(__file__).resolve().parents[3]


def read_default(name: str) -> dict[str, object]:
    return json.loads((RESOURCE_DIR / name).read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


def assigned_task(context: MemorySiteContext, camera_id: str) -> str | None:
    zone = context.get_zone_at(camera_id)
    assert zone is not None
    permits = context.find_active_work_permits(zone.zone_id, SCENARIO_TIME)
    return permits[0].task_code if permits else None


def test_default_configuration_loads_all_six_demo_channels() -> None:
    context = MemorySiteContext()

    assert [video.camera_id for video in context.list_videos()] == [
        "CAM-01",
        "CAM-02",
        "CAM-03",
        "CAM-04",
        "CAM-05",
        "CAM-06",
    ]


def test_default_configuration_is_resolved_relative_to_package_not_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    context = MemorySiteContext()

    assert len(context.list_videos()) == 6
    assert assigned_task(context, "CAM-03") == "HANDLING_REBAR"


def test_swapping_only_cam_03_and_cam_04_assignments_swaps_permit_tasks(
    tmp_path: Path,
) -> None:
    assignments = read_default("scene_assignments.json")
    scenes = assignments["scenes"]
    assert isinstance(scenes, list)
    cam03 = next(scene for scene in scenes if scene["camera_id"] == "CAM-03")
    cam04 = next(scene for scene in scenes if scene["camera_id"] == "CAM-04")
    cam03["task_code"], cam04["task_code"] = (
        cam04["task_code"],
        cam03["task_code"],
    )
    path = write_json(tmp_path / "swapped-scenes.json", assignments)

    context = MemorySiteContext(scene_assignments_path=path)

    assert assigned_task(context, "CAM-03") == "ROTATING_EQUIPMENT_OPERATION"
    assert assigned_task(context, "CAM-04") == "HANDLING_REBAR"


def test_duplicate_task_codes_fail_configuration_loading(tmp_path: Path) -> None:
    rules = read_default("task_ppe_rules.json")
    tasks = rules["tasks"]
    assert isinstance(tasks, list)
    tasks.append(copy.deepcopy(tasks[0]))
    path = write_json(tmp_path / "duplicate-task.json", rules)

    with pytest.raises(ValidationError, match="task_code"):
        MemorySiteContext(task_rules_path=path)


def test_unknown_ppe_value_fails_configuration_loading(tmp_path: Path) -> None:
    rules = read_default("task_ppe_rules.json")
    tasks = rules["tasks"]
    assert isinstance(tasks, list)
    tasks[0]["required_ppe"] = ["safety_shoes"]
    path = write_json(tmp_path / "unknown-ppe.json", rules)

    with pytest.raises(ValidationError, match="required_ppe"):
        MemorySiteContext(task_rules_path=path)


@pytest.mark.parametrize("minutes", [0, -15])
def test_non_positive_rectification_window_fails_configuration_loading(
    tmp_path: Path, minutes: int
) -> None:
    rules = read_default("task_ppe_rules.json")
    tasks = rules["tasks"]
    assert isinstance(tasks, list)
    tasks[0]["rectification_window_minutes"] = minutes
    path = write_json(tmp_path / f"bad-window-{minutes}.json", rules)

    with pytest.raises(ValidationError, match="rectification_window_minutes"):
        MemorySiteContext(task_rules_path=path)


@pytest.mark.parametrize("field", ["camera_id", "video_id"])
def test_duplicate_camera_or_video_fails_configuration_loading(
    tmp_path: Path, field: str
) -> None:
    assignments = read_default("scene_assignments.json")
    scenes = assignments["scenes"]
    assert isinstance(scenes, list)
    scenes[1][field] = scenes[0][field]
    path = write_json(tmp_path / f"duplicate-{field}.json", assignments)

    with pytest.raises(ValidationError, match=field):
        MemorySiteContext(scene_assignments_path=path)


def test_assignment_referencing_unknown_task_fails_loading(tmp_path: Path) -> None:
    assignments = read_default("scene_assignments.json")
    scenes = assignments["scenes"]
    assert isinstance(scenes, list)
    scenes[2]["task_code"] = "NOT_IN_RULE_LIBRARY"
    path = write_json(tmp_path / "unknown-task.json", assignments)

    with pytest.raises(ValueError, match="task_code"):
        MemorySiteContext(scene_assignments_path=path)


AGENT_ENV_KEYS = (
    "DEEPSEEK_API_KEY",
    "AGENT_LLM_MODEL",
    "AGENT_LLM_TIMEOUT_SECONDS",
    "AGENT_LLM_MAX_RETRIES",
    "AGENT_MAX_TOOL_ROUNDS",
    "AGENT_LLM_TEMPERATURE",
)
DATABASE_ENV_KEYS = ("DATABASE_URL", "DATABASE_ECHO")


def test_agent_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in AGENT_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    settings = Settings()

    assert settings.deepseek_api_key is None
    assert settings.agent_llm_model == "deepseek-v4-flash"
    assert settings.agent_llm_timeout_seconds == 30
    assert settings.agent_llm_max_retries == 2
    assert settings.agent_max_tool_rounds == 6
    assert settings.agent_llm_temperature == 0


def test_database_settings_load_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite:////tmp/siteppe-test.db")
    monkeypatch.setenv("DATABASE_ECHO", "true")

    settings = Settings()

    assert settings.database_url == "sqlite:////tmp/siteppe-test.db"
    assert settings.database_echo is True


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("agent_llm_timeout_seconds", 0),
        ("agent_llm_max_retries", -1),
        ("agent_max_tool_rounds", 0),
        ("agent_llm_temperature", -0.01),
        ("agent_llm_temperature", 2.01),
    ],
)
def test_agent_settings_reject_invalid_boundaries(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        Settings(**{field: value})


def test_env_example_lists_agent_configuration_without_secret_values() -> None:
    values = {
        key: value
        for line in (BACKEND_DIR / ".env.example").read_text(
            encoding="utf-8"
        ).splitlines()
        if line and not line.startswith("#") and "=" in line
        for key, value in [line.split("=", 1)]
    }

    assert set(AGENT_ENV_KEYS) <= values.keys()
    assert set(DATABASE_ENV_KEYS) <= values.keys()
    assert values["DEEPSEEK_API_KEY"] == ""
    assert values["VLM_API_KEY"] == ""
    assert values["EMBEDDING_API_KEY"] == ""


def test_vlm_and_embedding_keys_are_never_reused_for_deepseek(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        deepseek_api_key=None,
        vlm_api_key="vlm-only-secret",
        embedding_api_key="embedding-only-secret",
    )
    monkeypatch.setattr(deps, "get_settings", lambda: settings)
    monkeypatch.setattr(deps, "get_investigation_tools", lambda: object())
    deps.get_investigation_agent.cache_clear()
    try:
        agent = deps.get_investigation_agent()
    finally:
        deps.get_investigation_agent.cache_clear()

    assert isinstance(agent, FixedInvestigationAgent)


def test_deepseek_key_selects_real_investigation_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    constructed: dict[str, object] = {}

    class FakeDeepSeekModel:
        def __init__(self, **kwargs: object) -> None:
            constructed.update(kwargs)

        def complete(self, messages, tool_schemas):
            raise AssertionError("selection test must not call the model")

    settings = Settings(deepseek_api_key="deepseek-only-secret")
    monkeypatch.setattr(deps, "get_settings", lambda: settings)
    monkeypatch.setattr(deps, "get_investigation_tools", lambda: object())
    monkeypatch.setattr(deps, "DeepSeekChatModelAdapter", FakeDeepSeekModel)
    deps.get_investigation_agent.cache_clear()
    try:
        agent = deps.get_investigation_agent()
    finally:
        deps.get_investigation_agent.cache_clear()

    assert isinstance(agent, InvestigationAgent)
    assert constructed["api_key"] == "deepseek-only-secret"
    assert constructed["model"] == "deepseek-v4-flash"


def test_configured_deepseek_without_ai_extra_fails_explicitly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "langchain_deepseek":
            raise ImportError("optional AI dependency unavailable")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    adapter = DeepSeekChatModelAdapter(
        api_key="configured-secret",
        model="deepseek-v4-flash",
        temperature=0,
        timeout=30,
        max_retries=2,
    )

    with pytest.raises(InvestigationAgentFailed, match="langchain-deepseek is required"):
        adapter.complete([], [])


def test_app_main_imports_without_langchain_when_deepseek_key_is_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.startswith("langchain"):
            raise ImportError("LangChain intentionally unavailable")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    sys.modules.pop("app.main", None)

    module = importlib.import_module("app.main")

    assert module.app.title == "SitePPE Agent"
