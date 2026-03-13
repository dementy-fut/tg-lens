import pytest
from src.config import Settings


def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_API_ID", "12345")
    monkeypatch.setenv("TELEGRAM_API_HASH", "abc123")
    monkeypatch.setenv("TELEGRAM_PHONE", "+1234567890")
    monkeypatch.setenv("SUPABASE_URL", "https://xxx.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key123")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-xxx")

    settings = Settings()
    assert settings.telegram_api_id == 12345
    assert settings.telegram_api_hash == "abc123"
    assert settings.supabase_url == "https://xxx.supabase.co"


def test_settings_fails_without_required(monkeypatch):
    monkeypatch.delenv("TELEGRAM_API_ID", raising=False)
    monkeypatch.delenv("TELEGRAM_API_HASH", raising=False)
    monkeypatch.delenv("TELEGRAM_PHONE", raising=False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(Exception):
        Settings()
