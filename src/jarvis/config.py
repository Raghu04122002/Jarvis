"""Application configuration loaded from TOML files and environment variables."""

import logging
import tomllib
from pathlib import Path
from typing import Self

from pydantic import BaseModel, model_validator

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_CONFIG = _PROJECT_ROOT / "config" / "default.toml"


class ServerConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False


class DatabaseConfig(BaseModel):
    host: str = "localhost"
    port: int = 5432
    name: str = "jarvis"
    username: str = ""
    password: str = ""

    @property
    def async_url(self) -> str:
        if not self.username:
            return f"postgresql+asyncpg://{self.host}:{self.port}/{self.name}"
        return (
            f"postgresql+asyncpg://{self.username}:{self.password}"
            f"@{self.host}:{self.port}/{self.name}"
        )


class LoggingConfig(BaseModel):
    level: str = "INFO"
    format: str = "text"


class AgentsConfig(BaseModel):
    claude_command: str = "claude"
    antigravity_command: str = "antigravity"
    default_timeout: int = 300
    preferred_agent: str = "claude_code"


class BrowserConfig(BaseModel):
    headless: bool = True
    default_timeout_ms: int = 30000
    viewport_width: int = 1280
    viewport_height: int = 720
    allowed_domains: list[str] = []
    blocked_domains: list[str] = [
        "*.bank.*",
        "*.paypal.com",
        "pay.google.com",
        "venmo.com",
    ]


class MemoryConfig(BaseModel):
    max_context_memories: int = 10
    search_limit: int = 20


class JarvisConfig(BaseModel):
    server: ServerConfig = ServerConfig()
    database: DatabaseConfig = DatabaseConfig()
    logging: LoggingConfig = LoggingConfig()
    agents: AgentsConfig = AgentsConfig()
    browser: BrowserConfig = BrowserConfig()
    memory: MemoryConfig = MemoryConfig()

    @model_validator(mode="after")
    def _validate_logging_level(self) -> Self:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if self.logging.level.upper() not in valid:
            raise ValueError(
                f"Invalid logging level: {self.logging.level!r}. Must be one of {valid}"
            )
        self.logging.level = self.logging.level.upper()
        return self


def _deep_merge(base: dict, override: dict) -> dict:  # type: ignore[type-arg]
    """Merge override into base, recursively for nested dicts."""
    merged = base.copy()
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _env_overrides() -> dict[str, dict[str, str]]:
    """Read JARVIS_SECTION__KEY env vars and return nested dict."""
    import os

    overrides: dict[str, dict[str, str]] = {}
    prefix = "JARVIS_"
    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue
        parts = key[len(prefix) :].lower().split("__")
        if len(parts) == 2:
            section, field = parts
            overrides.setdefault(section, {})[field] = value
        elif len(parts) == 1:
            # Top-level override — skip for now (all config is nested)
            pass
    return overrides


def load_config(config_path: Path | None = None) -> JarvisConfig:
    """Load configuration from TOML file, then apply environment variable overrides."""
    data: dict = {}  # type: ignore[type-arg]

    # Load default config
    if _DEFAULT_CONFIG.exists():
        with open(_DEFAULT_CONFIG, "rb") as f:
            data = tomllib.load(f)

    # Load user-specified override file
    if config_path and config_path.exists():
        with open(config_path, "rb") as f:
            data = _deep_merge(data, tomllib.load(f))

    # Apply environment variable overrides
    env = _env_overrides()
    if env:
        data = _deep_merge(data, env)

    return JarvisConfig.model_validate(data)
