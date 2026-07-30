import pytest
from fastapi import HTTPException

from app.api.deps import get_bearer_token, get_postgrest_client, get_powabase_client
from app.clients.postgrest_client import PostgrestClient
from app.clients.powabase_client import PowabaseClient


def test_get_powabase_client_uses_settings(monkeypatch):
    import app.core.config as config_module

    monkeypatch.setattr(config_module.settings, "powabase_base_url", "https://x.p.powabase.ai")
    monkeypatch.setattr(config_module.settings, "powabase_api_key", "key-123")

    client = get_powabase_client()

    assert isinstance(client, PowabaseClient)
    assert client.base_url == "https://x.p.powabase.ai"
    assert client.headers["apikey"] == "key-123"


def test_get_postgrest_client_uses_settings(monkeypatch):
    import app.core.config as config_module

    monkeypatch.setattr(config_module.settings, "powabase_base_url", "https://x.p.powabase.ai")
    monkeypatch.setattr(config_module.settings, "powabase_api_key", "key-123")

    client = get_postgrest_client()

    assert isinstance(client, PostgrestClient)
    assert client.base_url == "https://x.p.powabase.ai"
    assert client.api_key == "key-123"


def test_get_bearer_token_extracts_token():
    token = get_bearer_token(authorization="Bearer abc123")

    assert token == "abc123"


def test_get_bearer_token_rejects_missing_header():
    with pytest.raises(HTTPException) as exc_info:
        get_bearer_token(authorization=None)

    assert exc_info.value.status_code == 401


def test_get_bearer_token_rejects_non_bearer_scheme():
    with pytest.raises(HTTPException) as exc_info:
        get_bearer_token(authorization="Basic abc123")

    assert exc_info.value.status_code == 401
