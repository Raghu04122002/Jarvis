"""User-editable runtime settings.

Settings changed in the desktop app are stored as overrides in a local JSON
file (gitignored) and layered on top of the TOML/env configuration. Applying
them reconfigures the AI service and the chat tools in place, so no restart
is needed.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field

from jarvis.config import AIConfig
from jarvis.services.chat_tools import make_search_backend

if TYPE_CHECKING:
    from jarvis.orchestrator.orchestrator import Orchestrator
    from jarvis.services.ai_service import AIService

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_SETTINGS_PATH = _PROJECT_ROOT / "data" / "settings.json"

# Secret name -> (AIConfig field or env var, kind)
KEY_NAMES = ("anthropic", "ollama", "tavily", "brave")
_ENV_KEYS = {"tavily": "TAVILY_API_KEY", "brave": "BRAVE_API_KEY"}

Provider = Literal["anthropic", "ollama"]
SearchProvider = Literal["auto", "ollama", "tavily", "brave", "none"]
Think = Literal["", "low", "medium", "high", "true", "false"]


class StoredSettings(BaseModel):
    """What is persisted. ``None`` means "use the config file / env value"."""

    provider: Provider | None = None
    model: str | None = None
    ollama_model: str | None = None
    ollama_think: str | None = None
    web_search_provider: SearchProvider | None = None
    keys: dict[str, str] = Field(default_factory=dict)
    disabled_tools: list[str] = Field(default_factory=list)
    persona: str = ""


class SettingsUpdate(BaseModel):
    """PATCH body. Omitted fields are unchanged; an empty key string clears it."""

    provider: Provider | None = None
    model: str | None = Field(default=None, max_length=200)
    ollama_model: str | None = Field(default=None, max_length=200)
    ollama_think: Think | None = None
    web_search_provider: SearchProvider | None = None
    keys: dict[str, str] | None = None
    disabled_tools: list[str] | None = None
    persona: str | None = Field(default=None, max_length=4000)


class KeyStatus(BaseModel):
    set: bool
    hint: str = ""  # last 4 characters, never the full key
    source: Literal["settings", "config", "none"] = "none"


class ToolSetting(BaseModel):
    name: str
    label: str
    description: str
    enabled: bool


class SettingsView(BaseModel):
    provider: Provider
    model: str
    ollama_model: str
    ollama_think: str
    web_search_provider: str
    web_search_connected: bool
    keys: dict[str, KeyStatus]
    tools: list[ToolSetting]
    persona: str
    ai_available: bool


def mask(value: str) -> KeyStatus:
    if not value:
        return KeyStatus(set=False)
    return KeyStatus(set=True, hint=value[-4:] if len(value) >= 12 else "")


class SettingsService:
    """Loads, saves and applies runtime settings."""

    def __init__(
        self,
        base: AIConfig,
        ai_service: AIService | None,
        orchestrator: Orchestrator | None,
        path: Path = DEFAULT_SETTINGS_PATH,
    ) -> None:
        self._base = base
        self._base_env = {name: os.environ.get(env, "") for name, env in _ENV_KEYS.items()}
        self._ai = ai_service
        self._orch = orchestrator
        self._path = path
        self._stored = self._load()

    # --- persistence ---

    def _load(self) -> StoredSettings:
        if not self._path.exists():
            return StoredSettings()
        try:
            return StoredSettings.model_validate_json(self._path.read_text())
        except (OSError, ValueError):
            logger.exception("Ignoring unreadable settings file %s", self._path)
            return StoredSettings()

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._stored.model_dump(), indent=2))
        tmp.chmod(0o600)  # contains API keys
        tmp.replace(self._path)

    # --- effective values ---

    def _key(self, name: str) -> tuple[str, Literal["settings", "config", "none"]]:
        stored = self._stored.keys.get(name)
        if stored:
            return stored, "settings"
        if name == "anthropic":
            base = self._base.api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        elif name == "ollama":
            base = self._base.ollama_api_key
        else:
            base = self._base_env.get(name, "")
        return base, ("config" if base else "none")

    def effective_ai_config(self) -> AIConfig:
        s = self._stored
        update: dict[str, Any] = {
            "api_key": self._key("anthropic")[0],
            "ollama_api_key": self._key("ollama")[0],
        }
        for field in ("provider", "model", "ollama_model", "ollama_think", "web_search_provider"):
            value = getattr(s, field)
            if value is not None:
                update[field] = value
        return self._base.model_copy(update=update)

    def apply(self) -> None:
        """Push the effective settings into the running services."""
        cfg = self.effective_ai_config()
        for name, env in _ENV_KEYS.items():
            value = self._key(name)[0]
            if value:
                os.environ[env] = value
            else:
                os.environ.pop(env, None)
        if self._ai is not None:
            self._ai.reconfigure(cfg)
        if self._orch is not None:
            self._orch.apply_chat_settings(
                search_backend=make_search_backend(cfg.web_search_provider, cfg.ollama_api_key),
                disabled_tools=frozenset(self._stored.disabled_tools),
                persona=self._stored.persona,
            )

    def view(self) -> SettingsView:
        cfg = self.effective_ai_config()
        disabled = set(self._stored.disabled_tools)
        tools: list[ToolSetting] = []
        if self._orch is not None:
            tools = [
                ToolSetting(name=n, label=lbl, description=d, enabled=n not in disabled)
                for n, lbl, d in self._orch.chat_tool_catalog()
            ]
        keys = {}
        for name in KEY_NAMES:
            value, source = self._key(name)
            status = mask(value)
            status.source = source
            keys[name] = status
        search = make_search_backend(cfg.web_search_provider, cfg.ollama_api_key)
        return SettingsView(
            provider=cfg.provider,
            model=cfg.model,
            ollama_model=cfg.ollama_model,
            ollama_think=cfg.ollama_think,
            web_search_provider=cfg.web_search_provider,
            web_search_connected=search is not None,
            keys=keys,
            tools=tools,
            persona=self._stored.persona,
            ai_available=self._ai.available if self._ai is not None else False,
        )

    def update(self, patch: SettingsUpdate) -> SettingsView:
        data = patch.model_dump(exclude_unset=True)
        stored = self._stored.model_copy(deep=True)
        for field in ("provider", "model", "ollama_model", "ollama_think", "web_search_provider"):
            if field in data:
                value = data[field]
                setattr(stored, field, value.strip() or None if isinstance(value, str) else value)
        if data.get("keys") is not None:
            for name, value in data["keys"].items():
                if name not in KEY_NAMES:
                    raise ValueError(f"Unknown key '{name}'")
                value = value.strip()
                if value:
                    stored.keys[name] = value
                else:
                    stored.keys.pop(name, None)
        if data.get("disabled_tools") is not None:
            stored.disabled_tools = sorted(set(data["disabled_tools"]))
        if data.get("persona") is not None:
            stored.persona = data["persona"]
        self._stored = stored
        self._save()
        self.apply()
        return self.view()
