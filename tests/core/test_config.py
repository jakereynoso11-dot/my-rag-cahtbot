import importlib


def test_settings_load_powabase_fields(monkeypatch, tmp_path):
    for key in ["POWABASE_BASE_URL", "POWABASE_API_KEY"]:
        monkeypatch.delenv(key, raising=False)

    env_file = tmp_path / ".env"
    env_file.write_text(
        "POWABASE_BASE_URL=https://example.p.powabase.ai\n"
        "POWABASE_API_KEY=secret-key\n"
    )
    monkeypatch.chdir(tmp_path)

    import app.core.config as config_module
    importlib.reload(config_module)

    assert config_module.settings.powabase_base_url == "https://example.p.powabase.ai"
    assert config_module.settings.powabase_api_key == "secret-key"
