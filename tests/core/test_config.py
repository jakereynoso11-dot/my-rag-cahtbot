import importlib
import os

import pytest


def _reload_settings(monkeypatch, **env):
    for key in [
        "powabase_base_url", "powabase_api_key", "powabase_kb_id", "powabase_agent_id",
    ]:
        monkeypatch.delenv(key.upper(), raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key.upper(), value)
    monkeypatch.setenv("PYDANTIC_SETTINGS_ENV_FILE", "")

    import app.core.config as config_module
    importlib.reload(config_module)
    return config_module


def test_settings_load_powabase_fields(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "POWABASE_BASE_URL=https://example.p.powabase.ai\n"
        "POWABASE_API_KEY=secret-key\n"
        "POWABASE_KB_ID=kb-123\n"
        "POWABASE_AGENT_ID=agent-456\n"
    )
    monkeypatch.chdir(tmp_path)

    import app.core.config as config_module
    importlib.reload(config_module)

    assert config_module.settings.powabase_base_url == "https://example.p.powabase.ai"
    assert config_module.settings.powabase_api_key == "secret-key"
    assert config_module.settings.powabase_kb_id == "kb-123"
    assert config_module.settings.powabase_agent_id == "agent-456"
