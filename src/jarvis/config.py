"""Application configuration loaded from TOML files and environment variables."""

import logging
import os
import tomllib
from pathlib import Path
from typing import Literal, Self

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

    # Backend for the Claude Code agent. "ollama" runs Claude Code against
    # Ollama's Anthropic-compatible API using an open model instead of Claude.
    claude_code_provider: Literal["anthropic", "ollama"] = "anthropic"
    claude_code_model: str = ""  # Anthropic model override; "" = CLI default
    ollama_coding_model: str = "gpt-oss:120b"
    ollama_fast_model: str = "gpt-oss:20b"
    ollama_base_url: str = "https://ollama.com"
    ollama_api_key: str = ""  # falls back to OLLAMA_API_KEY
    # Real context window of the Ollama model (gpt-oss = 128k). Claude Code
    # assumes 200k for unknown models, so it must compact earlier.
    ollama_context_window: int = 128000


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


class SchedulerConfig(BaseModel):
    enabled: bool = True
    poll_interval_seconds: int = 30


class NotificationConfig(BaseModel):
    desktop_enabled: bool = True


class ComputerConfig(BaseModel):
    enabled: bool = True
    screenshot_dir: str = "/tmp/jarvis_screenshots"
    allowed_applications: list[str] = []  # empty = all allowed
    blocked_applications: list[str] = [
        "Terminal",
        "iTerm",
        "System Preferences",
        "System Settings",
    ]
    mouse_move_delay: float = 0.1


class AIConfig(BaseModel):
    # Which LLM backend powers chat: "anthropic" or "ollama"
    provider: Literal["anthropic", "ollama"] = "anthropic"

    # Anthropic settings
    api_key: str = ""
    model: str = "claude-sonnet-4-6"
    base_url: str = "http://127.0.0.1:47821"
    pxpipe_enabled: bool = True
    max_tokens: int = 1024

    # Ollama settings. Defaults target Ollama Cloud (https://ollama.com/api).
    # For a local Ollama daemon, set ollama_base_url = "http://localhost:11434"
    # and use a "-cloud" model tag (e.g. "gpt-oss:120b-cloud") or a local model.
    ollama_api_key: str = ""
    # gpt-oss:20b is fast and cheap on usage-metered (free tier) cloud plans.
    ollama_model: str = "gpt-oss:20b"
    ollama_base_url: str = "https://ollama.com"
    ollama_timeout: float = 120.0
    # Reasoning effort for thinking models: "low" | "medium" | "high" for gpt-oss,
    # "true"/"false" for others, "" to leave the model default. Low saves quota.
    ollama_think: str = "low"

    # Web search tool for chat: "auto" picks Tavily (TAVILY_API_KEY), Brave
    # (BRAVE_API_KEY), or Ollama web search (OLLAMA_API_KEY), in that order.
    # "none" disables it — Jarvis will then say it can't fetch live info.
    web_search_provider: str = "auto"

    # Supervisor: the AI model plans each task, picks the agent, reviews the
    # agent's output, and sends follow-ups until the work is done.
    supervisor_enabled: bool = True
    supervisor_model: str = ""  # "" = same model as chat
    # Follow-up attempts after a failed review (each costs one agent run).
    review_max_rounds: int = 1

    @model_validator(mode="after")
    def _resolve_ollama_key(self) -> Self:
        if not self.ollama_api_key:
            self.ollama_api_key = os.environ.get("OLLAMA_API_KEY", "")
        return self


class VoiceConfig(BaseModel):
    whisper_api_key: str = ""
    whisper_model: str = "whisper-1"
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"
    elevenlabs_model_id: str = "eleven_monolingual_v1"
    tts_enabled: bool = True
    stt_enabled: bool = True

    @model_validator(mode="after")
    def _apply_env_fallbacks(self) -> Self:
        if not self.whisper_api_key:
            self.whisper_api_key = os.environ.get("OPENAI_API_KEY", "")
        if not self.elevenlabs_api_key:
            self.elevenlabs_api_key = os.environ.get("ELEVENLABS_API_KEY", "")
        return self


class WorkflowConfig(BaseModel):
    max_implementation_retries: int = 3
    max_ci_fix_retries: int = 2
    test_command: str = "pytest"
    ci_poll_interval_seconds: int = 30
    ci_poll_max_attempts: int = 40
    branch_prefix: str = "jarvis"
    require_approval_before_push: bool = True


class JarvisConfig(BaseModel):
    server: ServerConfig = ServerConfig()
    database: DatabaseConfig = DatabaseConfig()
    logging: LoggingConfig = LoggingConfig()
    agents: AgentsConfig = AgentsConfig()
    browser: BrowserConfig = BrowserConfig()
    memory: MemoryConfig = MemoryConfig()
    scheduler: SchedulerConfig = SchedulerConfig()
    notification: NotificationConfig = NotificationConfig()
    computer: ComputerConfig = ComputerConfig()
    ai: AIConfig = AIConfig()
    voice: VoiceConfig = VoiceConfig()
    workflow: WorkflowConfig = WorkflowConfig()

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


def _load_dotenv(path: Path) -> None:
    """Load KEY=VALUE lines from a .env file into os.environ (existing vars win)."""
    if not path.is_file():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.removeprefix("export ").partition("=")
        key, value = key.strip(), value.strip().strip("'\"")
        if key:
            os.environ.setdefault(key, value)


def load_config(config_path: Path | None = None) -> JarvisConfig:
    """Load configuration from TOML file, then apply environment variable overrides."""
    _load_dotenv(_PROJECT_ROOT / ".env")

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
