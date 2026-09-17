"""Agent registry — maps agent names to factory callables."""

from collections.abc import Callable

from jarvis.agents.base import AgentError, BaseAgent
from jarvis.config import AgentsConfig

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


def _claude_code_factory(config: AgentsConfig) -> BaseAgent:
    from jarvis.agents.claude_code import ClaudeCodeAgent

    return ClaudeCodeAgent(
        claude_command=config.claude_command,
        timeout=config.default_timeout,
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
