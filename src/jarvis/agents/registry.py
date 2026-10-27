"""Agent registry — maps agent names to factory callables."""

import logging
import os
from collections.abc import Callable

from jarvis.agents.base import AgentError, BaseAgent
from jarvis.config import AgentsConfig

logger = logging.getLogger(__name__)

AgentFactory = Callable[[AgentsConfig], BaseAgent]


class AgentNotFoundError(AgentError):
    """Raised when a requested agent name is not registered."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"No agent registered with name: {name!r}")


class AgentRegistry:
    """Registry mapping agent names to factory callables.

    Agents are created per-execution — the registry stores factories, not instances.
    """

    def __init__(self) -> None:
        self._factories: dict[str, AgentFactory] = {}

    def register(self, name: str, factory: AgentFactory) -> None:
        """Register a factory callable for the given agent name."""
        self._factories[name] = factory

    def create(self, name: str, config: AgentsConfig) -> BaseAgent:
        """Create an agent instance by name using the registered factory."""
        factory = self._factories.get(name)
        if factory is None:
            raise AgentNotFoundError(name)
        return factory(config)

    def list_agents(self) -> list[str]:
        """Return a sorted list of registered agent names."""
        return sorted(self._factories)

    def has(self, name: str) -> bool:
        """Check if an agent name is registered."""
        return name in self._factories


def claude_code_backend(config: AgentsConfig) -> tuple[str | None, dict[str, str]]:
    """Return (model, extra_env) that route Claude Code to the configured provider."""
    if config.claude_code_provider != "ollama":
        return (config.claude_code_model or None), {}

    api_key = config.ollama_api_key or os.environ.get("OLLAMA_API_KEY", "")
    if not api_key:
        logger.warning("claude_code_provider=ollama but no OLLAMA_API_KEY is set")
    env = {
        # Ollama serves an Anthropic-compatible /v1/messages endpoint.
        "ANTHROPIC_BASE_URL": config.ollama_base_url.rstrip("/"),
        "ANTHROPIC_AUTH_TOKEN": api_key,
        # Never forward a real Anthropic key to a third-party endpoint.
        "ANTHROPIC_API_KEY": "",
        "CLAUDE_API_KEY": "",
        # Claude Code's background "fast model" calls must also hit an Ollama model.
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": config.ollama_fast_model,
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        "CLAUDE_CODE_AUTO_COMPACT_WINDOW": str(config.ollama_context_window),
    }
    return config.ollama_coding_model, env


def _claude_code_factory(config: AgentsConfig) -> BaseAgent:
    from jarvis.agents.claude_code import ClaudeCodeAgent

    model, extra_env = claude_code_backend(config)
    return ClaudeCodeAgent(
        claude_command=config.claude_command,
        timeout=config.default_timeout,
        model=model,
        extra_env=extra_env,
    )


def _antigravity_factory(config: AgentsConfig) -> BaseAgent:
    from jarvis.agents.antigravity import AntigravityAgent

    return AntigravityAgent(
        antigravity_command=config.antigravity_command,
        timeout=config.default_timeout,
    )


def create_default_registry() -> AgentRegistry:
    """Create an AgentRegistry pre-loaded with the default agents."""
    registry = AgentRegistry()
    registry.register("claude_code", _claude_code_factory)
    registry.register("antigravity", _antigravity_factory)
    return registry
