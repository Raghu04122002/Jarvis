"""Tests for configuration loading and validation."""

from pathlib import Path

import pytest

from jarvis.config import JarvisConfig, load_config


def test_default_config_loads() -> None:
    config = load_config()
    assert config.server.host == "127.0.0.1"
    assert config.server.port == 8000
    assert config.database.name == "jarvis"
    assert config.logging.level == "INFO"


def test_config_defaults_without_file() -> None:
    config = load_config(config_path=Path("/nonexistent/path.toml"))
    assert config.server.port == 8000


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JARVIS_SERVER__PORT", "9000")
    config = load_config()
    assert config.server.port == 9000


def test_env_override_database_username(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JARVIS_DATABASE__USERNAME", "testuser")
    config = load_config()
    assert config.database.username == "testuser"


def test_invalid_log_level() -> None:
    with pytest.raises(ValueError, match="Invalid logging level"):
        JarvisConfig(logging={"level": "INVALID"})  # type: ignore[arg-type]


def test_database_async_url_without_auth() -> None:
    config = JarvisConfig()
    assert "asyncpg" in config.database.async_url
    assert config.database.async_url.endswith("/jarvis")


def test_database_async_url_with_auth() -> None:
    config = JarvisConfig(database={"username": "user", "password": "pass"})  # type: ignore[arg-type]
    assert "user:pass@" in config.database.async_url
