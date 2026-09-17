"""Base agent interface — abstract base class for all agent implementations."""

import abc


class AgentError(Exception):
    """Base exception for agent-related errors."""


class BaseAgent(abc.ABC):
    """Common interface for all agent implementations.

    Agents are created per-execution (not singletons).
    """

    @property
    @abc.abstractmethod
    def agent_name(self) -> str:
        """Return the canonical name of this agent (e.g. 'claude_code')."""

    @abc.abstractmethod
    async def run(self, prompt: str, working_dir: str) -> tuple[int, str, str]:
        """Execute the agent with the given prompt.

        Returns (exit_code, stdout, stderr).
        """

    @abc.abstractmethod
    async def cancel(self) -> None:
        """Cancel the running agent process."""

    @abc.abstractmethod
    def status(self) -> str:
        """Return the current status string."""

    @abc.abstractmethod
    def elapsed_seconds(self) -> float | None:
        """Return elapsed time in seconds, or None if not started."""
