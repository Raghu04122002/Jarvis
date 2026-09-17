"""Agent router — selects which agent to use for a given task."""

from jarvis.agents.registry import AgentRegistry
from jarvis.config import AgentsConfig
from jarvis.models.task import Task

_ANTIGRAVITY_KEYWORDS: frozenset[str] = frozenset({
    "browser",
    "ui",
    "visual",
    "screenshot",
    "selenium",
    "playwright",
    "click",
    "navigate",
    "webpage",
    "web page",
})

# Bidirectional fallback mapping.
_FALLBACK_MAP: dict[str, str] = {
    "claude_code": "antigravity",
    "antigravity": "claude_code",
}


class AgentRouter:
    """Selects which agent to use for a task.

    Selection logic (in priority order):
    1. Explicit override via task.metadata["agent_name"]
    2. User preference via config.preferred_agent
    3. Keyword matching on task.request
    4. Default: claude_code
    """

    def __init__(self, registry: AgentRegistry, config: AgentsConfig) -> None:
        self._registry = registry
        self._config = config

    def select(self, task: Task) -> str:
        """Return the agent name to use for the given task."""
        # 1. Explicit override in task metadata
        explicit = task.metadata.get("agent_name")
        if explicit and self._registry.has(explicit):
            return explicit

        # 2. User preference
        preferred = self._config.preferred_agent
        if preferred != "claude_code" and self._registry.has(preferred):
            return preferred

        # 3. Keyword matching
        request_lower = task.request.lower()
        for keyword in _ANTIGRAVITY_KEYWORDS:
            if keyword in request_lower:
                return "antigravity"

        # 4. Default
        return "claude_code"

    def fallback_for(self, agent_name: str) -> str | None:
        """Return the fallback agent name, or None if no fallback exists."""
        fallback = _FALLBACK_MAP.get(agent_name)
        if fallback and self._registry.has(fallback):
            return fallback
        return None
